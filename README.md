# Gemma on Apple M4 (ANE/MLX)

このフォルダは、Apple M4 で **Gemma 4** を効率的に動かすための作業ディレクトリです。  
32GB RAM を搭載した M4 Mac 用に最適化されており、**MLX** フレームワークを使用して Gemma 4 モデル (E4B / 26B) を実行します。

## 1) セットアップ (Gemma 4 / MLX)

```bash
# 依存関係のインストール
pip install -r requirements.txt

# MLX 環境の構築とモデルのダウンロード
./scripts/run_mlx_chat.sh
```

初回実行時にモデル (`mlx-community/gemma-4-e4b-it-4bit`) が自動的にダウンロードされます。

### 環境変数の設定

`.env` ファイルを作成し、Brave Search API キーを設定してください：

```bash
BRAVE_SEARCH_API_KEY=your_api_key_here
```

## 2) 起動 (Gemma 4 対話)

### 従来版（ツール直接実行）

ターミナルで以下のコマンドを入力します：

```bash
gemma4
# または
python mlx_chat.py
```

### MCP版（推奨）

MCP (Model Context Protocol) 経由でツールを実行する版：

```bash
python mlx_chat_mcp.py
```

**メリット:**
- ツールロジックが独立し、メンテナンス性が向上
- 将来的な拡張（Playwright等）が容易
- 他のクライアントからもツールを再利用可能

以前の Core ML版を動かしたい場合は、以下を実行してください：

```bash
gemma4 chat
```

## アーキテクチャ

### ファイル構成

```
.
├── mlx_chat.py           # 従来版チャットクライアント（ツール直接実行）
├── mlx_chat_mcp.py       # MCP対応チャットクライアント
├── mcp_server.py         # MCPツールサーバー
├── tools.py              # ツール実装（Brave Search, スクレイピング）
└── requirements.txt      # Python依存関係
```

### MCP構成

```
┌─────────────────┐
│ mlx_chat_mcp.py │  ← Gemma 4 チャットクライアント
└────────┬────────┘
         │ MCP Protocol (stdio)
         ↓
┌─────────────────┐
│  mcp_server.py  │  ← ツールサーバー
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│    tools.py     │  ← Brave Search API / BeautifulSoup4
└─────────────────┘
```

## 備考

- **Gemma 4**: 最新の Google モデルで、MLX を使用することで Apple Silicon の性能を最大限に引き出します。
- **Memory**: 32GB RAM 環境では Gemma 4 E4B (4-bit) が非常に高速に動作します。
- **Intelligence**: 以前の 270M モデルと比較して、推論能力が飛躍的に向上しています。
- **MCP**: Model Context Protocol により、ツールの標準化と拡張性を実現しています。
