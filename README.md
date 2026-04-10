# Gemma 4 Local Runtime (MLX + OpenAI-Compatible API)

このリポジトリは、Gemma 4 (MLX) を以下の2つで利用できる構成です。

- OpenAI互換 REST API (`/v1/chat/completions`, `/v1/models`)
- MCP Tools Server (`web_search`, `fetch_content`)

既存の CLI チャット (`mlx_chat.py`, `mlx_chat_mcp.py`, `scripts/gemma4`) も維持しています。

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` には最低限 `BRAVE_SEARCH_API_KEY` を設定してください（Web検索ツールを使う場合）。

## ディレクトリ構成

```text
gemma4/
├── core/
│   ├── model.py          # MLXモデル管理
│   └── chat_engine.py    # ツール呼び出し対応チャット実行
├── api/
│   ├── main.py           # FastAPIアプリ
│   ├── schemas.py        # OpenAI互換スキーマ
│   └── routes/
│       ├── chat.py       # /v1/chat/completions
│       └── models.py     # /v1/models
├── mcp/
│   └── tools_server.py   # MCP tools server 実体
├── mcp_server.py         # 互換エントリーポイント
├── tools.py              # Web検索・スクレイピング実装
├── mlx_chat.py           # 既存CLI (直接ツール実行)
└── mlx_chat_mcp.py       # 既存CLI (MCP経由)
```

## OpenAI互換 API の起動

```bash
./scripts/run_openai_api.sh
# または
uvicorn api.main:app --host 0.0.0.0 --port 44448
```

OpenAPI は以下で確認できます。

- [http://localhost:44448/docs](http://localhost:44448/docs)

## API 利用例

### モデル一覧

```bash
curl http://localhost:44448/v1/models
```

### Chat Completions (非ストリーム)

```bash
curl http://localhost:44448/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e4b-it",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

### Chat Completions (ストリーム)

```bash
curl -N http://localhost:44448/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e4b-it",
    "messages": [{"role": "user", "content": "Pythonの最新情報を教えて"}],
    "stream": true
  }'
```

### ツール呼び出しを許可するリクエスト

```bash
curl http://localhost:44448/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e4b-it",
    "messages": [{"role": "user", "content": "最新のLLMニュースを調べて"}],
    "stream": false,
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "search_web",
          "description": "Search the web",
          "parameters": {
            "type": "object",
            "properties": {
              "query": {"type": "string"}
            },
            "required": ["query"]
          }
        }
      }
    ]
  }'
```

## IDE 設定例

### Zed

```json
{
  "language_models": {
    "gemma4-local": {
      "provider": "openai",
      "api_url": "http://localhost:44448/v1",
      "model": "gemma-4-e4b-it"
    }
  }
}
```

### VSCode / Continue

```json
{
  "continue.models": [
    {
      "title": "Gemma 4 Local",
      "provider": "openai",
      "baseUrl": "http://localhost:44448/v1",
      "model": "gemma-4-e4b-it"
    }
  ]
}
```

## MCP Tools Server

既存と同じ起動方法です。

```bash
python mcp_server.py
```

`mcp_server.py` は互換エントリーポイントで、実体は `mcp/tools_server.py` です。

## 既存CLI

```bash
gemma4
python mlx_chat.py
python mlx_chat_mcp.py
```
