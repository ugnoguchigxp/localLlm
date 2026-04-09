#!/usr/bin/env python3
"""
Gemma 4 Chat Client with Simplified Tool Architecture
ツール実行をクリーンに分離した版
"""
import argparse
import sys
import re
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

# ツールの定義と実装をインポート
from tools import search_web, fetch_content

# 利用可能なツールのマッピング
TOOLS = {
    "search_web": {
        "function": search_web,
        "description": "最新の情報を取得するためにウェブ検索を行います",
    },
    "fetch_content": {
        "function": fetch_content,
        "description": "指定されたURLから詳細なテキスト情報を取得します",
    },
}

def parse_tool_call(text):
    """Gemma 4 のツール呼び出しを抽出（寛容なパーサー）"""
    print(f"\n[DEBUG] Parsing text: {text[-200:]}")
    
    # パターン1: 完全な形式
    pattern1 = r"<\|tool_call\|?>call:(\w+)\{(.*?)\}<tool_call\|?>"
    match = re.search(pattern1, text)
    
    if match:
        func_name, args_str = match.group(1), match.group(2)
        print(f"[DEBUG] Matched (full format) function: {func_name}, args: {args_str}")
    else:
        # パターン2: 簡略形式 - call:関数名のみを検出
        pattern2 = r"call:(\w+)"
        match = re.search(pattern2, text)
        if match:
            func_name = match.group(1)
            print(f"[DEBUG] Matched (simple format) function: {func_name}")
            # 引数を推測
            # ユーザーの直前の質問からクエリを抽出
            args_str = ""
        else:
            print(f"[DEBUG] No tool call pattern found")
            return None
    
    # 引数をパース
    args = {}
    if args_str:
        arg_matches = re.finditer(r"(\w+):<\|\"\|>(.*?)<\|\"\|>", args_str)
        for am in arg_matches: 
            args[am.group(1)] = am.group(2)
    
    print(f"[DEBUG] Parsed: function={func_name}, arguments={args}")
    return {"name": func_name, "arguments": args}

def execute_tool(tool_name: str, arguments: dict) -> str:
    """ツールを実行（同期版）"""
    if tool_name not in TOOLS:
        return f"Error: Unknown tool '{tool_name}'"
    
    tool_func = TOOLS[tool_name]["function"]
    
    try:
        # 引数に応じて呼び出し
        if tool_name == "search_web":
            return tool_func(arguments.get("query", ""))
        elif tool_name == "fetch_content":
            return tool_func(arguments.get("url", ""))
        else:
            return "Error: Tool execution failed"
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mlx-community/gemma-4-e4b-it-4bit")
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    print(f"Loading model: {args.model}...")
    model, tokenizer = load(args.model)

    sys_instr = """あなたは有能なアシスタントです。日本語で答えてください。

利用可能なツール:
- search_web: 最新の情報をウェブ検索で取得します
- fetch_content: URLから詳細な情報を取得します

ツールを使う場合は、必ず以下の形式で呼び出してください:
<|tool_call|>call:search_web{query:<|"|>検索クエリ<|"|>}<tool_call|>
<|tool_call|>call:fetch_content{url:<|"|>https://example.com<|"|>}<tool_call|>

最新情報や天気、ニュースなどの質問には、必ず search_web ツールを使用してください。"""
    
    # Few-shot例を追加（モデルに正しいツール呼び出し形式を教える）
    messages = [
        {"role": "system", "content": sys_instr},
        {"role": "user", "content": "今日のニュースを教えて"},
        {"role": "assistant", "content": '<|tool_call|>call:search_web{query:<|"|>今日のニュース<|"|>}<tool_call|>'},
        {"role": "user", "content": "（検索結果）\n- 最新ニュース1\n- 最新ニュース2\n回答を続けてください。"},
        {"role": "assistant", "content": "今日の主なニュースは以下の通りです：\n- 最新ニュース1\n- 最新ニュース2"},
    ]
    
    print("\nChat session started. Clean Tool Architecture.")
    print(f"Available tools: {', '.join(TOOLS.keys())}\n")

    while True:
        try:
            u_inp = input("You: ").strip()
        except EOFError: break
        if not u_inp: continue
        if u_inp.lower() in ["exit", "reset"]:
            if u_inp == "reset": messages = [{"role": "system", "content": sys_instr}]; print("Reset.")
            else: break
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

            for chunk in generate(model, tokenizer, prompt=prompt, sampler=make_sampler(0.0), max_tokens=args.max_tokens):
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
                        print("[Tool Execution...]", end="", flush=True)
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
                print(f"\n[DEBUG] Parsed call: {call}")
                if call:
                    # 引数が空の場合、ユーザーの質問から推測
                    if not call["arguments"] and call["name"] == "search_web":
                        call["arguments"] = {"query": last_user_message}
                        print(f"[DEBUG] Using user message as query: {last_user_message}")
                    
                    print(f"\n[DEBUG] Executing tool: {call['name']} with args: {call['arguments']}")
                    res = execute_tool(call["name"], call["arguments"])
                    print(f"\n[DEBUG] Tool result length: {len(res)} chars")
                    print(f"\n[DEBUG] Tool result preview: {res[:200]}...")
                    messages.append({"role": "assistant", "content": full_resp.strip()})
                    messages.append({"role": "user", "content": f"（検索結果）\n{res}\n回答を続けてください。"})
                else: 
                    print("\n[DEBUG] Failed to parse tool call")
                    turn_done = True
            else:
                messages.append({"role": "assistant", "content": full_resp.strip()})
                turn_done = True
        print("\n")

if __name__ == "__main__":
    main()
