@echo off
chcp 65001 >nul
cd /d %~dp0
echo 织识 KnowWeave 启动中...
set "PYEXE=python"
python --version >nul 2>&1
if errorlevel 1 set "PYEXE=py -3"
%PYEXE% --version >nul 2>&1
if errorlevel 1 (
  echo [错误] 没检测到 Python。请先到 https://www.python.org 下载安装（安装时勾选 Add to PATH）
  pause
  exit /b
)
if not exist .venv (
  echo 首次运行，安装依赖约 1-3 分钟...
  %PYEXE% -m venv .venv && .venv\Scripts\pip install -q -r requirements.txt
)
echo 启动后浏览器会自动打开产品页面 http://127.0.0.1:8000
start "" http://127.0.0.1:8000
.venv\Scripts\python -m app.main
pause
