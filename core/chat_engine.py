from __future__ import annotations

import re
import asyncio
from typing import Any, Iterable, Generator, List, Dict

from core.model import MLXModelManager, get_model_manager
from tools import fetch_content, search_web

TOOL_CALL_RE = re.compile(r"<\|tool_call\|?>call:(\w+)\{(.*?)\}<tool_call\|?>", re.DOTALL)
TOOL_ARGS_RE = re.compile(r"(\w+):<\|\"\|>(.*?)<\|\"\|>", re.DOTALL)
THINK_BLOCK_RE = re.compile(r"<\|channel>thought.*?(?:<channel\|>|$)", re.DOTALL)
LEGACY_THINK_BLOCK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL)
INCOMPLETE_TOOL_CALL_RE = re.compile(r"<\|tool_call\|?>call:.*$", re.DOTALL)


def _extract_text_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
        return "\n".join(c for c in chunks if c)
    return str(content)


def _normalize_tool_name(name: str) -> str:
    aliases = {
        "web_search": "search_web",
        "search_web": "search_web",
        "fetch_content": "fetch_content",
    }
    return aliases.get(name, name)


class ChatEngine:
    """Gemma chat engine with optional tool execution and streaming support."""

    def __init__(self, model_manager: Any | None = None, verbose: bool = False, max_tool_rounds: int = 3) -> None:
        # model_manager can be MLXModelManager or a backend object from backends/*.py
        self.model_manager = model_manager
        self.verbose = verbose
        self.max_tool_rounds = max_tool_rounds
        self.messages = []

    def reset(self, sys_instr: str):
        self.messages = [{"role": "system", "content": sys_instr}]

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    @staticmethod
    def parse_tool_call(text: str) -> dict[str, Any] | None:
        match = TOOL_CALL_RE.search(text)
        if not match:
            # Try alternative format
            pattern_alt = r"<\|tool_call\|?>\s*call:(\w+)\s*\{(.*?)\}\s*<tool_call\|?>"
            match = re.search(pattern_alt, text, re.DOTALL)
        
        if not match:
            return None

        func_name, args_str = match.group(1), match.group(2)
        args: dict[str, str] = {}
        # Try primary arg pattern
        for arg_match in TOOL_ARGS_RE.finditer(args_str):
            args[arg_match.group(1)] = arg_match.group(2)
        
        # Fallback for simple key:value if TOOL_ARGS_RE failed
        if not args and ":" in args_str:
            arg_matches = re.finditer(r"(\w+)\s*:\s*<\|\"\|>(.*?)<\|\"\|>", args_str, re.DOTALL)
            for am in arg_matches: 
                args[am.group(1)] = am.group(2)

        return {"name": func_name, "arguments": args}

    @staticmethod
    def sanitize_response(text: str) -> str:
        sanitized = THINK_BLOCK_RE.sub("", text)
        sanitized = LEGACY_THINK_BLOCK_RE.sub("", sanitized)
        sanitized = TOOL_CALL_RE.sub("", sanitized)
        sanitized = INCOMPLETE_TOOL_CALL_RE.sub("", sanitized)
        sanitized = sanitized.replace("<channel|>", "").replace("<|channel>thought", "")
        return sanitized.strip()

    def _prepare_messages(self, messages: Iterable[dict[str, Any]], allow_tools: bool) -> list[dict[str, str]]:
        prepared: list[dict[str, str]] = []
        has_system = False

        for message in messages:
            role = str(message.get("role", "user"))
            content = _extract_text_content(message.get("content", ""))

            if role == "tool":
                role = "user"
                content = f"ツール結果:\n{content}"
            elif role not in {"system", "user", "assistant"}:
                role = "user"

            prepared.append({"role": role, "content": content})
            if role == "system":
                has_system = True

        if allow_tools:
            tool_instruction = (
                "必要な場合のみツールを呼び出してください。\n"
                "形式: <|tool_call|>call:関数名{引数名:<|\"|>値<|\"|>}<tool_call|>\n"
                "利用可能ツール: search_web(query) / web_search(query), fetch_content(url)"
            )
            if has_system and prepared:
                prepared[0]["content"] = f"{prepared[0]['content']}\n\n{tool_instruction}".strip()
            else:
                prepared.insert(0, {"role": "system", "content": tool_instruction})

        return prepared

    async def _run_tool_async(self, tool_call: dict[str, Any]) -> str:
        name = _normalize_tool_name(tool_call["name"])
        arguments = tool_call.get("arguments", {})

        try:
            if name == "search_web":
                query = arguments.get("query") or arguments.get("q")
                return await asyncio.to_thread(search_web, query)
            if name == "fetch_content":
                url = arguments.get("url")
                return await asyncio.to_thread(fetch_content, url)
            return f"Error: Unknown tool '{name}'"
        except Exception as e:
            return f"Error: Local tool execution failed ({str(e)})"

    # API 用 (同期/一括生成)
    def run_chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tools: list[str] | None = None,
    ) -> str:
        if self.model_manager is None:
            self.model_manager = get_model_manager()
            
        allowed_tools = {_normalize_tool_name(tool) for tool in (tools or [])}
        prepared_messages = self._prepare_messages(messages, allow_tools=bool(allowed_tools))
        retried_plain_answer = False

        for _ in range(self.max_tool_rounds + 1):
            raw_response = "".join(
                self.model_manager.generate_stream(
                    prepared_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )

            tool_call = self.parse_tool_call(raw_response)
            if tool_call and _normalize_tool_name(tool_call["name"]) in allowed_tools:
                # API context uses sync tool call (already threaded in API route normally, but here we use search_web directly)
                name = _normalize_tool_name(tool_call["name"])
                args = tool_call.get("arguments", {})
                if name == "search_web": tool_result = search_web(args.get("query", ""))
                elif name == "fetch_content": tool_result = fetch_content(args.get("url", ""))
                else: tool_result = f"Error: Unknown tool {name}"
                
                prepared_messages.append({"role": "assistant", "content": raw_response.strip()})
                prepared_messages.append({"role": "user", "content": f"（検索結果）\n{tool_result}\n回答を続けてください。"})
                continue

            sanitized = self.sanitize_response(raw_response)
            if sanitized: return sanitized
            if tool_call: return f"Tool '{tool_call['name']}' is unavailable for this request."

            if not retried_plain_answer:
                retried_plain_answer = True
                prepared_messages.append({"role": "assistant", "content": raw_response.strip()})
                prepared_messages.append({"role": "user", "content": "思考過程やタグを出力せず、最終回答のみを返してください。"})
                continue
            return "回答を生成できませんでした。"
        return "上限に達しました。"

    # CLI 用 (ストリーミング対話)
    async def chat_loop(self, user_input: str, **kwargs):
        self.add_message("user", user_input)
        
        while True:
            print("Assistant: ", end="", flush=True)
            full_resp = ""
            is_thinking = False
            is_tool_calling_detected = False
            
            think_start_tags = ["<|channel>thought", "<think>"]
            think_end_tags = ["<channel|>", "</think>"]
            tool_start_tag = "<|tool_call|>"
            tool_end_tag = "<tool_call|>"
            buffer = ""
            
            # self.model_manager が generate_stream を持っていることを期待 (Backends or ModelManager)
            for chunk in self.model_manager.generate_stream(self.messages, **kwargs):
                full_resp += chunk
                buffer += chunk

                for t in think_start_tags:
                    if t in buffer:
                        if not is_thinking:
                            pre_text = buffer[:buffer.find(t)]
                            if pre_text: print(pre_text, end="", flush=True)
                            is_thinking = True
                            if self.verbose: print(f"\n[Raw Thought Start]", flush=True)
                            else: print("[Thinking...]", end="", flush=True)
                        buffer = buffer[buffer.find(t) + len(t):]

                for t in think_end_tags:
                    if t in buffer:
                        if is_thinking:
                            is_thinking = False
                            if self.verbose: print(f"\n[Raw Thought End]", flush=True)
                            else: print(" Done.\nAssistant: ", end="", flush=True)
                        buffer = buffer[buffer.find(t) + len(t):]

                if tool_start_tag in buffer:
                    if tool_end_tag in buffer:
                        is_tool_calling_detected = True
                        if not self.verbose: print("[Searching...]", end="", flush=True)
                        break
                    else: continue

                if is_thinking and not self.verbose:
                    if len(buffer) > 100: buffer = buffer[-50:]
                else:
                    if "<" in buffer:
                        safe_idx = buffer.find("<")
                        if safe_idx > 0:
                            print(buffer[:safe_idx], end="", flush=True)
                            buffer = buffer[safe_idx:]
                    else:
                        print(buffer, end="", flush=True)
                        buffer = ""
                await asyncio.sleep(0)

            print("", flush=True)
            if is_tool_calling_detected:
                call = self.parse_tool_call(full_resp)
                if call:
                    tool_res = await self._run_tool_async(call)
                    self.add_message("assistant", full_resp.strip())
                    self.add_message("user", f"（検索結果）\n{tool_res}\nこの結果をもとに、回答を日本語で生成してください。")
                    continue
            
            self.add_message("assistant", full_resp.strip())
            break
        print("\n")

