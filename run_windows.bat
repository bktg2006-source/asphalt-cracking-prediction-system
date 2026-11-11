@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua tim thay moi truong .venv. Hay lam theo README.md de cai dat dependencies.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m streamlit run app.py
