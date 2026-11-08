#!/bin/bash
cd "$(dirname "$0")"
echo "🧶 织识 KnowWeave 启动中…（首次运行需 1-3 分钟装依赖）"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
echo "✅ 启动后请在浏览器打开: http://127.0.0.1:8000"
( sleep 3; open http://127.0.0.1:8000 ) &
.venv/bin/python -m app.main
