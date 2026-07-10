@echo off
chcp 65001 >nul
cd /d "D:\Projects Claude Code\REGTEAM"
git config merge.ff false
set GIT_MERGE_AUTOEDIT=no

echo [1/4] Останавливаем старый Flask...
taskkill /f /im python.exe 1>nul 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Получаем обновления с GitHub...
git checkout --theirs templates/ 2>nul
git add templates/ 2>nul
git commit -m "Auto-resolve conflicts" 2>nul
git pull --no-edit origin main
git checkout --theirs templates/ 2>nul
git add templates/ 2>nul
git commit -m "Auto-resolve post-pull conflicts" --no-edit 2>nul

echo [3/4] Проверяем зависимости...
pip install -r requirements.txt --quiet

echo [4/4] Запускаем Flask...
python app.py
pause