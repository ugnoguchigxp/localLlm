#!/usr/bin/env python3
"""
Gemma 4 Chat Client with Simplified Tool Architecture
"""
import argparse
import sys
import re
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler
from tools import search_web, fetch_content

TOOLS = {
    "search_web": {
        "function": search_web,
        "description": "最新の情報をウェブ検索で取得します",
    },
    "fetch_content": {
        "function": fetch_content,
        "description": "指定されたURLから詳細な情報を取得します",
    },
}

def parse_tool_call(text):
    """Gemma 4 のツール呼び出しを抽出（寛容なパーサー）"""
    pattern1 = r"<\|tool_call\|?>call:(\w+)\{(.*?)\}<tool_call\|?>"
    match = re.search(pattern1, text)
    
    if match:
        func_name, args_str = match.group(1), match.group(2)
    else:
        pattern2 = r"call:(\w+)"
        match = re.search(pattern2, text)
        if match:
            func_name = match.group(1)
            args_str = ""
        else:
            if "<|tool_call" in text or "<tool_call" in text:
                func_name = "search_web"
                args_str = ""
            else:
                return None
    
    args = {}
    if args_str:
        arg_matches = re.finditer(r"(\w+):<\|\"\|>(.*?)<\|\"\|>", args_str)
        for am in arg_matches: 
            args[am.group(1)] = am.group(2)
    
    return {"name": func_name, "arguments": args}

def execute_tool(tool_name: str, arguments: dict) -> str:
    """ツールを実行（同期版）"""
    if tool_name not in TOOLS:
        return f"Error: Unknown tool '{tool_name}'"
    
    tool_func = TOOLS[tool_name]["function"]
    
    try:
        if tool_name == "search_web":
            return tool_func(arguments.get("query", ""))
        elif tool_name == "fetch_content":
            return tool_func(arguments.get("url", ""))
        else:
            return "Error: Tool execution failed"
    except Exception as e:
        return f"Error: {str(e)}"

def remove_thinking_process(text: str, show_thinking: bool = False) -> str:
    """思考プロセスを除去"""
    if show_thinking:
        return text
    
    # パターン: <|channel>thought ... <channel|> を削除
    pattern = r"<\|channel>thought.*?<channel\|>"
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    
    # パターン2: <channel>thought ... channel|> も削除
    pattern2 = r"<channel>thought.*?channel\|>"
    cleaned = re.sub(pattern2, "", cleaned, flags=re.DOTALL)
    
    return cleaned.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mlx-community/gemma-4-e4b-it-4bit")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--show-thinking", action="store_true", help="思考プロセスを表示")
    args = parser.parse_args()

    print(f"Loading model: {args.model}...")
    model, tokenizer = load(args.model)

    sys_instr = """あなたは有能なアシスタントです。

**出力形式の厳守:**
- 回答は必ずMarkdown形式で記述してください
- 見出しは ## または ### を使用
- リストは - または 1. を使用
- コードブロックは ```言語名 で囲む
- 強調は **太字** や *斜体* を使用

**利用可能なツール:**
- search_web: 最新の情報をウェブ検索で取得します
- fetch_content: URLから詳細な情報を取得します

**ツール呼び出し形式:**
<|tool_call|>call:search_web{query:<|"|>検索クエリ<|"|>}<tool_call|>
<|tool_call|>call:fetch_content{url:<|"|>https://example.com<|"|>}<tool_call|>

最新情報や天気、ニュースなどの質問には、必ず search_web ツールを使用してください。"""
    
    messages = [
        {"role": "system", "content": sys_instr},
        {"role": "user", "content": "今日のニュースを教えて"},
        {"role": "assistant", "content": '<|tool_call|>call:search_web{query:<|"|>今日のニュース<|"|>}<tool_call|>'},
        {"role": "user", "content": "（検索結果）\n- 最新ニュース1\n- 最新ニュース2\n回答を続けてください。"},
        {"role": "assistant", "content": "今日の主なニュースは以下の通りです：\n- 最新ニュース1\n- 最新ニュース2"},
    ]
    
    print("\nChat session started. Clean Tool Architecture.")
    print(f"Available tools: {', '.join(TOOLS.keys())}\n")

    last_user_message = ""

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

        last_user_message = u_inp
        messages.append({"role": "user", "content": u_inp})

        turn_done = False
        while not turn_done:
            prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            
            # 生成実行（バッファリングなし、全て取得）
            full_resp = ""
            for chunk in generate(model, tokenizer, prompt=prompt, sampler=make_sampler(0.0), max_tokens=args.max_tokens):
                full_resp += chunk
            
            # ツール呼び出しチェック
            if "<|tool_call" in full_resp or "call:" in full_resp:
                call = parse_tool_call(full_resp)
                if call:
                    if not call["arguments"] and call["name"] == "search_web":
                        call["arguments"] = {"query": last_user_message}
                    
                    res = execute_tool(call["name"], call["arguments"])
                    messages.append({"role": "assistant", "content": full_resp.strip()})
                    messages.append({"role": "user", "content": f"（検索結果）\n{res}\n回答を続けてください。"})
                else:
                    turn_done = True
            else:
                # 思考プロセスを除去して出力
                cleaned_resp = remove_thinking_process(full_resp, args.show_thinking)
                print(f"Assistant: {cleaned_resp}", flush=True)
                messages.append({"role": "assistant", "content": full_resp.strip()})
                turn_done = True
        print("\n")

if __name__ == "__main__":
    main()
