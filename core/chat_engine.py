from __future__ import annotations

import re
from typing import Any, Iterable

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
    """Gemma chat engine with optional tool execution."""

    def __init__(self, model_manager: MLXModelManager | None = None, max_tool_rounds: int = 3) -> None:
        self.model_manager = model_manager or get_model_manager()
        self.max_tool_rounds = max_tool_rounds

    @staticmethod
    def parse_tool_call(text: str) -> dict[str, Any] | None:
        match = TOOL_CALL_RE.search(text)
        if not match:
            return None

        func_name, args_str = match.group(1), match.group(2)
        args: dict[str, str] = {}
        for arg_match in TOOL_ARGS_RE.finditer(args_str):
            args[arg_match.group(1)] = arg_match.group(2)

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

    def _run_tool(self, tool_call: dict[str, Any]) -> str:
        name = _normalize_tool_name(tool_call["name"])
        arguments = tool_call.get("arguments", {})

        if name == "search_web":
            return search_web(arguments.get("query", ""))
        if name == "fetch_content":
            return fetch_content(arguments.get("url", ""))

        return f"Error: Unknown tool '{name}'"

    def run_chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tools: list[str] | None = None,
    ) -> str:
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
                tool_result = self._run_tool(tool_call)
                prepared_messages.append({"role": "assistant", "content": raw_response.strip()})
                prepared_messages.append(
                    {
                        "role": "user",
                        "content": f"（検索結果）\n{tool_result}\n回答を続けてください。",
                    }
                )
                continue

            sanitized = self.sanitize_response(raw_response)
            if sanitized:
                return sanitized

            if tool_call:
                return f"Tool '{tool_call['name']}' is unavailable for this request."

            if not retried_plain_answer:
                retried_plain_answer = True
                prepared_messages.append({"role": "assistant", "content": raw_response.strip()})
                prepared_messages.append(
                    {
                        "role": "user",
                        "content": "思考過程やタグを出力せず、最終回答のみを返してください。",
                    }
                )
                continue

            return "回答を生成できませんでした。max_tokens を増やして再実行してください。"

        return "ツール呼び出しの上限に達したため終了しました。"
