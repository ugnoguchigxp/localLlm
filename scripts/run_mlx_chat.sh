#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_NAME="mlx-community/gemma-4-e4b-it-4bit"

source "${ROOT_DIR}/.venv/bin/activate"

# クリーンなツールアーキテクチャ版を使用
python "${ROOT_DIR}/mlx_chat_clean.py" --model "${MODEL_NAME}" "$@"
