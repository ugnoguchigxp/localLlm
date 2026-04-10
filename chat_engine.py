import re
import asyncio
import sys
import os
from typing import List, Dict, Any, Generator
from backends.base import BaseBackend

# ツール（直接実行用）のインポート
try:
    from tools import search_web, fetch_content
except ImportError:
    def search_web(q): return "Error: search_web not found"
    def fetch_content(u): return "Error: fetch_content not found"

class ChatEngine:
    """
    LLMバックエンドとローカルツールを統合するエンジン。
    """
    def __init__(self, backend: BaseBackend, verbose: bool = False, **kwargs):
        self.backend = backend
        self.messages = []
        self.verbose = verbose
        
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def reset(self, sys_instr: str):
        self.messages = [{"role": "system", "content": sys_instr}]

    def parse_tool_call(self, text: str):
        """
        Gemma 4 等のタグ形式からツール呼び出しを抽出。
        """
        pattern = r"<\|tool_call\|?>\s*call:(\w+)\s*\{(.*?)\}\s*<tool_call\|?>"
        match = re.search(pattern, text, re.DOTALL)
        if not match: 
            pattern_alt = r"<tool_call>\s*call:(\w+)\s*\{(.*?)\}\s*</tool_call>"
            match = re.search(pattern_alt, text, re.DOTALL)
        if not match: return None
        
        func_name, args_str = match.group(1), match.group(2)
        args = {}
        arg_matches = re.finditer(r"(\w+)\s*:\s*<\|\"\|>(.*?)<\|\"\|>", args_str, re.DOTALL)
        for am in arg_matches: 
            args[am.group(1)] = am.group(2)
        return {"name": func_name, "arguments": args}

    async def run_tool_locally(self, name: str, args: dict) -> str:
        if self.verbose:
            print(f"\n[Local Tool] Executing {name} with {args}...", flush=True)
        try:
            if name in ["search_web", "web_search"]:
                query = args.get("query") or args.get("q")
                if not query: return "Error: Missing query"
                return await asyncio.to_thread(search_web, query)
            elif name == "fetch_content":
                url = args.get("url")
                if not url: return "Error: Missing url"
                return await asyncio.to_thread(fetch_content, url)
            else:
                return f"Error: Tool '{name}' not found"
        except Exception as e:
            return f"Error: Local tool execution failed ({str(e)})"

    async def chat_loop(self, user_input: str, **kwargs):
        """
        メインの対話ループ。
        """
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
            
            for chunk in self.backend.generate_stream(self.messages, **kwargs):
                full_resp += chunk
                buffer += chunk

                # --- 状態変化の検知 (思考開始) ---
                for t in think_start_tags:
                    if t in buffer:
                        if not is_thinking:
                            # タグより前の通常テキストがあれば出力
                            pre_text = buffer[:buffer.find(t)]
                            if pre_text: print(pre_text, end="", flush=True)
                            
                            is_thinking = True
                            if self.verbose: print(f"\n[Raw Thought Start]", flush=True)
                            else: print("[Thinking...]", end="", flush=True)
                        
                        buffer = buffer[buffer.find(t) + len(t):]

                # --- 状態変化の検知 (思考終了) ---
                for t in think_end_tags:
                    if t in buffer:
                        if is_thinking:
                            is_thinking = False
                            if self.verbose: print(f"\n[Raw Thought End]", flush=True)
                            else: print(" Done.\nAssistant: ", end="", flush=True)
                        
                        # 思考タグとその前（思考内容）を切り捨てる
                        buffer = buffer[buffer.find(t) + len(t):]

                # --- ツール呼び出し検知 ---
                # ※重要: 思考終了直後の同じバッファ内に含まれている可能性があるため
                # continue 等で飛ばさずに必ず評価する
                if tool_start_tag in buffer:
                    if tool_end_tag in buffer:
                        is_tool_calling_detected = True
                        if not self.verbose: print("[Searching...]", end="", flush=True)
                        break # タグが完成したので生成を打ち切る
                    else:
                        # ツール開始タグ以降は、閉じタグが出るまで出力を保留
                        continue

                # --- 画面出力処理 ---
                if is_thinking and not self.verbose:
                    # 思考内容は出力しないが、バッファは（タグ検知のために）少量保持
                    if len(buffer) > 100: buffer = buffer[-50:]
                else:
                    # 通常テキストの出力
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
                    tool_res = await self.run_tool_locally(call["name"], call["arguments"])
                    self.add_message("assistant", full_resp.strip())
                    self.add_message("user", f"（検索結果）\n{tool_res}\nこの結果をもとに、ユーザーの質問に対する回答を日本語で生成してください。")
                    continue
                else:
                    self.add_message("assistant", full_resp.strip())
                    break
            else:
                self.add_message("assistant", full_resp.strip())
                break
        
        print("\n")
