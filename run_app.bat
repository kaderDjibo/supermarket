@echo off
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
  echo Virtual environment not found. Creating venv...
  python -m venv venv
)
call venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -r requirements.txt
python -m streamlit run app.py --server.port 8505
pause