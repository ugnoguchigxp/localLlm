#!/usr/bin/env python3
"""
Gemma 4 Chat Client with MCP Integration
MCP経由でツールを呼び出す版
"""
import argparse
import sys
import re
import json
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler
from mcp import ClientSession, StdioServerParameters, stdio_client

class MCPToolClient:
    """MCP クライアント"""
    
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.session = None
        self.read = None
        self.write = None
        self.tools = []
        self.stdio_context = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー: 接続開始"""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script_path],
            env=None
        )
        
        # stdio_clientはコンテキストマネージャー
        self.stdio_context = stdio_client(server_params)
        self.read, self.write = await self.stdio_context.__aenter__()
        self.session = ClientSession(self.read, self.write)
        
        await self.session.initialize()
        
        # ツールリストを取得
        response = await self.session.list_tools()
        self.tools = response.tools
        print(f"[MCP] Connected. Available tools: {[t.name for t in self.tools]}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー: 接続終了"""
        if self.stdio_context:
            await self.stdio_context.__aexit__(exc_type, exc_val, exc_tb)
    
    async def call_tool(self, name: str, arguments: dict) -> str:
        """ツールを実行"""
        if not self.session:
            return "Error: MCP session not initialized"
        
        try:
            result = await self.session.call_tool(name, arguments)
            if result.content and len(result.content) > 0:
                return result.content[0].text
            return "No result returned"
        except Exception as e:
            return f"Error: {str(e)}"

def parse_tool_call(text):
    """Gemma 4 のツール呼び出しを抽出"""
    pattern = r"<\|tool_call\|?>call:(\w+)\{(.*?)\}<tool_call\|?>"
    match = re.search(pattern, text)
    if not match: 
        return None
    func_name, args_str = match.group(1), match.group(2)
    args = {}
    arg_matches = re.finditer(r"(\w+):<\|\"\|>(.*?)<\|\"\|>", args_str)
    for am in arg_matches: 
        args[am.group(1)] = am.group(2)
    return {"name": func_name, "arguments": args}

async def chat_loop(model, tokenizer, mcp_client: MCPToolClient, max_tokens: int):
    """チャットループ"""
    sys_instr = "有能な助手。日本語で答えて。形式：<|tool_call|>call:関数名{引数名:<|\"|>値<|\"|>}<tool_call|>"
    messages = [{"role": "system", "content": sys_instr}]
    
    print("\nChat session started (MCP-enabled). Stable Filtering Active.")

    while True:
        try:
            u_inp = input("You: ").strip()
        except EOFError: 
            break
        if not u_inp: 
            continue
        if u_inp.lower() in ["exit", "reset"]:
            if u_inp == "reset": 
                messages = [{"role": "system", "content": sys_instr}]
                print("Reset.")
            else: 
                break
            continue

        messages.append({"role": "user", "content": u_inp})

        turn_done = False
        while not turn_done:
            prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            
            print("Assistant: ", end="", flush=True)
            full_resp = ""
            is_thinking = False
            is_tool_calling = False
            
            buffer = ""

            for chunk in generate(model, tokenizer, prompt=prompt, sampler=make_sampler(0.0), max_tokens=max_tokens):
                full_resp += chunk
                buffer += chunk

                # 思考タグ
                if "<|channel>thought" in buffer:
                    if not is_thinking:
                        is_thinking = True
                        print("[Thinking...]", end="", flush=True)
                    buffer = ""
                    continue
                if "<channel|>" in buffer:
                    if is_thinking:
                        is_thinking = False
                        print(" Done.\nAssistant: ", end="", flush=True)
                    buffer = ""
                    continue
                
                # ツールタグ
                if "<|tool_call" in buffer or "<tool_call" in buffer:
                    if ">" in chunk:
                        is_tool_calling = True
                        print("[Searching...]", end="", flush=True)
                        break
                    continue

                # タグの開始判定
                if "<" in buffer:
                    safe_idx = buffer.find("<")
                    if safe_idx > 0:
                        print(buffer[:safe_idx], end="", flush=True)
                        buffer = buffer[safe_idx:]
                    if len(buffer) > 30:
                        print(buffer, end="", flush=True)
                        buffer = ""
                else:
                    print(buffer, end="", flush=True)
                    buffer = ""

            if is_tool_calling:
                call = parse_tool_call(full_resp)
                if call:
                    # MCPツール名に変換
                    tool_name_map = {
                        "search_web": "web_search",
                        "fetch_content": "fetch_content"
                    }
                    mcp_tool_name = tool_name_map.get(call["name"], call["name"])
                    
                    # MCP経由でツール実行
                    import asyncio
                    res = await mcp_client.call_tool(mcp_tool_name, call["arguments"])
                    
                    messages.append({"role": "assistant", "content": full_resp.strip()})
                    messages.append({"role": "user", "content": f"（検索結果）\n{res}\n回答を続けてください。"})
                else: 
                    turn_done = True
            else:
                messages.append({"role": "assistant", "content": full_resp.strip()})
                turn_done = True
        print("\n")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mlx-community/gemma-4-e4b-it-4bit")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--mcp-server", default="./mcp_server.py", help="Path to MCP server script")
    args = parser.parse_args()

    print(f"Loading model: {args.model}...")
    model, tokenizer = load(args.model)

    # MCPクライアント初期化（コンテキストマネージャーとして使用）
    async with MCPToolClient(args.mcp_server) as mcp_client:
        await chat_loop(model, tokenizer, mcp_client, args.max_tokens)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
