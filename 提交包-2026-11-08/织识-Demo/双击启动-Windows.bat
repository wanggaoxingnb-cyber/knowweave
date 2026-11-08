@echo off
cd /d %~dp0
echo 织识 KnowWeave 启动中...（首次运行需 1-3 分钟装依赖）
if not exist .venv (
  python -m venv .venv && .venv\Scripts\pip install -q -r requirements.txt
)
echo 启动后请在浏览器打开: http://127.0.0.1:8000
start "" http://127.0.0.1:8000
.venv\Scripts\python -m app.main
pause
