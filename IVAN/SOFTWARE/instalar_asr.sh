#!/usr/bin/env bash
set -euo pipefail
studio_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$studio_dir"
mkdir -p .estado/tmp .estado/cache/pip .estado/config .estado/models
export TMPDIR="$studio_dir/.estado/tmp"
export PIP_CACHE_DIR="$studio_dir/.estado/cache/pip"
export XDG_CACHE_HOME="$studio_dir/.estado/cache"
export XDG_CONFIG_HOME="$studio_dir/.estado/config"
export HF_HOME="$studio_dir/.estado/models/huggingface"
export PYTHONDONTWRITEBYTECODE=1
if [[ ! -x .estado/venv/bin/python ]]; then python3 -B -m venv --system-site-packages .estado/venv; fi
.estado/venv/bin/python -B -m pip install --disable-pip-version-check -r requirements-asr.txt
