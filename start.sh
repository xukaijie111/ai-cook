#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  trap - SIGINT SIGTERM EXIT
  echo ""
  echo "正在停止服务..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "已停止"
}

trap cleanup SIGINT SIGTERM

# ── 后端 ──
echo ">>> 启动后端 (http://127.0.0.1:8000)"
cd "$ROOT/backend"

if [[ ! -d .venv ]]; then
  echo "    创建 Python 虚拟环境..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if [[ ! -f .venv/.deps_installed ]]; then
  echo "    安装 Python 依赖..."
  pip install -r requirements.txt -q
  touch .venv/.deps_installed
fi

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# ── 前端 ──
echo ">>> 启动前端 (http://localhost:5173)"
cd "$ROOT/frontend"

if [[ ! -d node_modules ]]; then
  echo "    安装 npm 依赖..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  后端 API : http://127.0.0.1:8000"
echo "  Admin UI : http://localhost:5173"
echo "  按 Ctrl+C 停止"
echo "========================================="
echo ""

wait
