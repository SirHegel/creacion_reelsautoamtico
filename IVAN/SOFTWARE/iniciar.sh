#!/usr/bin/env bash
set -euo pipefail
studio_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$studio_dir"
mkdir -p .estado/tmp .estado/cache .estado/config .estado/models
export TMPDIR="$studio_dir/.estado/tmp"
export XDG_CACHE_HOME="$studio_dir/.estado/cache"
export XDG_CONFIG_HOME="$studio_dir/.estado/config"
export HF_HOME="$studio_dir/.estado/models/huggingface"
export PIP_CACHE_DIR="$studio_dir/.estado/cache/pip"
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=''
studio_python="python3"
if [[ -x .estado/venv/bin/python ]]; then studio_python="$studio_dir/.estado/venv/bin/python"; fi
exec nice -n 10 "$studio_python" -B -m studio serve --port "${1:-8765}"
