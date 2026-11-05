@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title MUSE AI MV Studio

echo ===================================================
echo     MUSE AI MV STUDIO - DIRECTORIAL SUITE
echo ===================================================
echo.

if exist ".venv\Scripts\python.exe" goto RUN_APP

echo [*] Khoi tao moi truong ao Python .venv...
python -m venv .venv
echo [*] Cai dat cac thu vien can thiet...
".venv\Scripts\pip.exe" install -r requirements.txt

:RUN_APP
echo [*] Mo trinh duyet tai http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"

echo [*] May chu dang chay tai http://127.0.0.1:8000 (Nhan Ctrl+C de dung)...
".venv\Scripts\python.exe" app.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Co loi xay ra khi chay ung dung.
    pause
)
