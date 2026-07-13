@echo off
cd /d "D:\Projects Claude Code\SPORTS_REFEREE"
git config merge.ff false
set GIT_MERGE_AUTOEDIT=no

echo [1/4] Stop Flask...
taskkill /f /im python.exe 1>nul 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Git pull...
git checkout --theirs templates/ 2>nul
git add templates/ 2>nul
git commit -m "Auto-resolve conflicts" 2>nul
git pull --no-edit origin main
git checkout --theirs templates/ 2>nul
git add templates/ 2>nul
git commit -m "Auto-resolve post-pull conflicts" --no-edit 2>nul

echo [3/4] pip install...
pip install -r requirements.txt --quiet

echo [4/4] Start Flask...
start http://localhost:5002
python app.py
pause