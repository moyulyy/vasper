#!/usr/bin/env bash
# Vasper 启动脚本：优先使用项目内的 conda 环境。
set -euo pipefail
cd "$(dirname "$0")"

ENV_PY="$PWD/.conda/envs/vasper/bin/python"
if [ -x "$ENV_PY" ]; then
  PY="$ENV_PY"
elif [ -n "${VASPER_PYTHON:-}" ]; then
  PY="$VASPER_PYTHON"
else
  PY="$(command -v python3)"
fi

# 无独显/虚拟机环境：允许 Chromium 使用 SwiftShader 兜底渲染 3D。
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:---enable-unsafe-swiftshader --ignore-gpu-blocklist --disable-gpu-compositing}"

exec "$PY" "$PWD/main.py" "$@"
