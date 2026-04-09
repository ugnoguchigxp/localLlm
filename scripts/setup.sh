#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_REPO="${1:-anemll/anemll-google-gemma-3-270m-it-ctx4096_0.3.5}"
MODEL_NAME="${MODEL_REPO##*/}"
MODEL_DIR="${ROOT_DIR}/models/${MODEL_NAME}"

echo "[1/4] Checking prerequisites"
if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

if ! command -v git-lfs >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "git-lfs not found. Installing with Homebrew..."
    brew install git-lfs
  else
    echo "git-lfs is required. Install it first." >&2
    exit 1
  fi
fi
git lfs install >/dev/null

echo "[2/4] Preparing Python virtual environment"
if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  python3 -m venv "${ROOT_DIR}/.venv"
fi
source "${ROOT_DIR}/.venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install \
  coremltools \
  transformers \
  "torch==2.7.0" \
  pyyaml \
  sentencepiece \
  huggingface_hub

echo "[3/4] Downloading model: ${MODEL_REPO}"
mkdir -p "${ROOT_DIR}/models"
if [[ -d "${MODEL_DIR}/.git" ]]; then
  git -C "${MODEL_DIR}" pull --ff-only
  git -C "${MODEL_DIR}" lfs pull
else
  git clone "https://huggingface.co/${MODEL_REPO}" "${MODEL_DIR}"
fi

echo "[4/4] Expanding model archives if present"
if ls "${MODEL_DIR}"/*.zip >/dev/null 2>&1; then
  unzip -o "${MODEL_DIR}"/*.zip -d "${MODEL_DIR}" >/dev/null
fi

cat <<EOF

Setup completed.
Model directory: ${MODEL_DIR}

Run:
  ./scripts/run_chat.sh ${MODEL_NAME}

EOF
