#!/usr/bin/env python3
import argparse
import sys
import re
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler
from tools import search_web, fetch_content

def parse_tool_call(text):
    """Gemma 4 のツール呼び出しを抽出"""
    pattern = r"<\|tool_call\|?>call:(\w+)\{(.*?)\}<tool_call\|?>"
    match = re.search(pattern, text)
    if not match: return None
    func_name, args_str = match.group(1), match.group(2)
    args = {}
    arg_matches = re.finditer(r"(\w+):<\|\"\|>(.*?)<\|\"\|>", args_str)
    for am in arg_matches: args[am.group(1)] = am.group(2)
    return {"name": func_name, "arguments": args}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mlx-community/gemma-4-e4b-it-4bit")
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    print(f"Loading model: {args.model}...")
    model, tokenizer = load(args.model)

    sys_instr = "有能な助手。日本語で答えて。形式：<|tool_call|>call:関数名{引数名:<|\"|>値<|\"|>}<tool_call|>"
    messages = [{"role": "system", "content": sys_instr}]
    
    print("\nChat session started. Stable Filtering Active.")

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
            
            # 最小かつ堅牢なストリームフィルタ
            # 特殊タグの候補
            tags = ["<|channel>thought", "<channel|>", "<|tool_call|>", "<|tool_call>", "<tool_call"]
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
                
                # ツールタグ (閉じタグが来るか、タグではないと確定するまでバッファ)
                if "<|tool_call" in buffer or "<tool_call" in buffer:
                    if ">" in chunk:
                        is_tool_calling = True
                        print("[Searching...]", end="", flush=True)
                        break # ツール実行へ
                    continue

                # タグの開始（'<'）が含まれる場合は、タグが確定するまで待機
                if "<" in buffer:
                    # 確定した安全な部分だけを出す
                    safe_idx = buffer.find("<")
                    if safe_idx > 0:
                        print(buffer[:safe_idx], end="", flush=True)
                        buffer = buffer[safe_idx:]
                    # タグとしては長すぎればバグと見なして放出
                    if len(buffer) > 30:
                        print(buffer, end="", flush=True)
                        buffer = ""
                else:
                    # 全くタグの気配がないので即座に表示
                    print(buffer, end="", flush=True)
                    buffer = ""

            if is_tool_calling:
                call = parse_tool_call(full_resp)
                if call:
                    res = search_web(call["arguments"].get("query", "")) if call["name"]=="search_web" else fetch_content(call["arguments"].get("url", ""))
                    messages.append({"role": "assistant", "content": full_resp.strip()})
                    messages.append({"role": "user", "content": f"（検索結果）\n{res}\n回答を続けてください。"})
                else: turn_done = True
            else:
                messages.append({"role": "assistant", "content": full_resp.strip()})
                turn_done = True
        print("\n")

if __name__ == "__main__":
    main()
