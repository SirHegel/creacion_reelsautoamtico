#!/usr/bin/env bash
set -euo pipefail
studio_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$studio_dir"
mkdir -p .estado/tmp .estado/cache/pip .estado/config
export TMPDIR="$studio_dir/.estado/tmp"
export PIP_CACHE_DIR="$studio_dir/.estado/cache/pip"
export XDG_CACHE_HOME="$studio_dir/.estado/cache"
export XDG_CONFIG_HOME="$studio_dir/.estado/config"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m venv --system-site-packages .estado/venv
.estado/venv/bin/python -B -m pip install --disable-pip-version-check -r requirements.txt
if [[ "${1:-}" == "--runtime" ]]; then
  mkdir -p .estado/herramientas .estado/cache/npm
  export npm_config_cache="$studio_dir/.estado/cache/npm"
  export npm_config_userconfig="$studio_dir/.estado/config/npmrc"
  export npm_config_globalconfig="$studio_dir/.estado/config/npm-globalrc"
  if [[ ! -f "$npm_config_userconfig" ]]; then : > "$npm_config_userconfig"; fi
  if [[ ! -f "$npm_config_globalconfig" ]]; then : > "$npm_config_globalconfig"; fi
  npm install --prefix "$studio_dir/.estado/herramientas" --no-audit --no-fund --ignore-scripts --save-exact hyperframes@0.8.147 gsap@3.15.0
fi
.estado/venv/bin/python -B -m studio preflight
