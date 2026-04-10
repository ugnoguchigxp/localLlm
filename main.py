#!/usr/bin/env python3
import warnings
import os

# 全ての警告を抑制（特に multiprocessing の resource_tracker 対策）
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

import argparse
import sys
import asyncio
from core.chat_engine import ChatEngine

async def main():
    parser = argparse.ArgumentParser(description="Multi-Backend AI Chat Agent (Local Direct Tooling)")
    parser.add_argument("--backend", choices=["mlx", "ollama", "bonsai", "mock"], default="mlx", help="Inference backend")
    parser.add_argument("--model", type=str, help="Model path or name")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temp", type=float, default=0.0)
    parser.add_argument("--verbose", "-v", action="store_true", help="Display debug logs and raw model output")
    args = parser.parse_args()

    # バックエンドの動的インポート
    if args.backend == "mlx":
        from backends.mlx import MLXBackend
        backend = MLXBackend(verbose=args.verbose)
        model_path = args.model or "mlx-community/gemma-4-e4b-it-4bit"
    elif args.backend == "ollama":
        from backends.ollama import OllamaBackend
        backend = OllamaBackend(verbose=args.verbose)
        model_path = args.model or "llama3"
    elif args.backend == "bonsai":
        from backends.bonsai import BonsaiBackend
        backend = BonsaiBackend(verbose=args.verbose)
        model_path = args.model or "prism-ml/Bonsai-8B-mlx-1bit"
    elif args.backend == "mock":
        from backends.mock_backend import MockBackend
        backend = MockBackend(verbose=args.verbose)
        model_path = args.model or "test-mock-model"

    # モデルのロード
    try:
        if args.verbose:
            print(f"[Debug] Loading backend: {args.backend} with model: {model_path}")
        backend.load_model(model_path)
    except Exception as e:
        print(f"Failed to load model: {e}")
        sys.exit(1)

    # Engineの初期化
    engine = ChatEngine(backend, verbose=args.verbose)
    
    # バックエンドに応じたコンテキスト設定
    if args.backend == "bonsai":
        sys_instr = (
            "あなたは有能な助手です。必ず日本語で答えてください。\n"
            "【重要】最新情報やあなたの知らない事柄を聞かれた場合は、必ず以下のツールを呼び出してください。\n\n"
            "- 検索: <|tool_call|>call:search_web{query:<|\"|>検索ワード<|\"|>}<tool_call|>\n\n"
            "例: 「今日の東京の天気」→回答の代わりに以下を出力:\n"
            "<|tool_call|>call:search_web{query:<|\"|>今日の東京の天気<|\"|>}<tool_call|>"
        )
    elif args.backend == "mlx":
        sys_instr = (
            "あなたは有能なアシスタントです。日本語で回答してください。\n"
            "最新の情報を回答するため、必要に応じて以下の検索ツールを使用してください。\n"
            "ツールを使用する際は、思考プロセスの直後に必ず指定のタグを出力してください。\n\n"
            "1. search_web(query): ウェブ検索。形式: <|tool_call|>call:search_web{query:<|\"|>検索語<|\"|>}<tool_call|>\n"
            "2. fetch_content(url): コンテンツ取得。形式: <|tool_call|>call:fetch_content{url:<|\"|>URL<|\"|>}<tool_call|>\n"
        )
    else:
        sys_instr = "優秀なAI助手。日本語で答えて。<|tool_call|>形式で検索ツールを使用可能。"
    
    engine.reset(sys_instr)

    print(f"\n--- Chat session started [Backend: {args.backend}] ---")
    print("Commands: 'exit' to quit, 'reset' to clear history.\n")

    # メインループ
    try:
        while True:
            try:
                loop = asyncio.get_event_loop()
                u_inp = await loop.run_in_executor(None, lambda: input("You: "))
                u_inp = u_inp.strip()
            except EOFError:
                break
            
            if not u_inp: continue
            if u_inp.lower() == "exit": break
            if u_inp.lower() == "reset":
                engine.reset(sys_instr)
                print("Chat history reset.")
                continue

            # チャット実行
            await engine.chat_loop(u_inp, max_tokens=args.max_tokens, temperature=args.temp)
            
    finally:
        # 終了時にリソースを適切に解放
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print(f"\n[Fatal Error] {e}")
        sys.exit(1)
