# Gemma 4 Local Runtime (MLX + Ollama + Bonsai)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

このプロジェクトは、Apple Silicon (MLX) や Ollama を活用して、高性能な LLM ローカル実行環境および自律型エージェント機能を提供します。

## ✨ 特徴

- **マルチバックエンド対応**: MLX (Gemma 4, Bonsai) と Ollama をシームレスに切り替え。
- **自律型エージェント**: Web検索 (`Brave Search`) やウェブスクレイピング機能を搭載したツール実行機能。
- **OpenAI 互換 API**: `/v1/chat/completions` エンドポイントを提供し、Zed, VSCode (Continue) 等の IDE から利用可能。
- **MCP (Model Context Protocol)**: 外部ツールを標準化されたプロトコルで呼び出し可能。
- **高速な CLI**: ターミナルから直接モデルと対話できる専用スクリプト群。

---

## 🚀 クイックスタート

### 1. プロジェクトの準備

```bash
git clone https://github.com/YOUR_USERNAME/localLlm.git
cd localLlm

# 仮想環境の作成とライブラリのインストール
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 環境設定
cp .env.example .env
```

`.env` 内の `BRAVE_SEARCH_API_KEY` を設定すると、Web検索ツールが有効になります。

### 2. インストール手順 (バックエンド別)

#### 🦙 Ollama
[Ollama 公式サイト](https://ollama.com/) からアプリをダウンロードしてインストールしてください。

```bash
# 推奨モデルのプル
ollama pull llama3
```

#### 💎 Gemma 4 (MLX)
Apple Silicon Mac を使用している場合、MLX バックエンドを推奨します。

```bash
# MLX 版 Gemma 4 のセットアップ（初回実行時に自動ダウンロードされます）
./scripts/gemma4 "Hello, who are you?"
```

#### 🌳 Bonsai (MLX)
Bonsai は MLX 最適化された高性能 8B モデルです。

```bash
# Bonsai の実行（初回実行時に自動ダウンロードされます）
./scripts/bonsai "複雑なアルゴリズムについて解説して"
```

### 3. PATH の設定 (推奨)

以下のスクリプトを実行することで、どこからでも `gemma4` などのコマンドを実行できるようになります。

```bash
bash scripts/install_path.sh
# 実行後、指示に従って shell を再起動または source してください
```

---

## 🛠️ ディレクトリ構成

```text
.
├── scripts/            # 実行用ショートカットスクリプト (gemma4, bonsai, ollama-v4)
├── core/               # モデル制御・チャットエンジンのコアロジック
├── api/                # OpenAI 互換 FastAPI 実装
├── backends/           # MLX, Ollama などのバックエンド抽象化
├── mcp/                # MCP Server 実装
├── tools.py            # Web検索・スクレイピングツールの実装
└── main.py             # メインエントリポイント
```

---

## 🌐 OpenAI 互換 API の利用

API サーバーを起動することで、既存の OpenAI クライアントや IDE 拡張からローカル LLM を利用できます。

```bash
./scripts/run_openai_api.sh
```

### IDE 設定例 (Zed)

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

---

## 🔌 MCP Tools Server

MCP 対応クライアントからツールを利用する場合：

```bash
python mcp_server.py
```

---

## 📜 ライセンス

[MIT License](LICENSE)
