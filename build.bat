@echo off
REM Run this on Windows, in the same folder as notify.py, to build Notify.exe
REM Requires Python installed and added to PATH.

echo Installing dependencies...
pip install -r requirements.txt

echo Building Notify.exe (no console window, single file)...
pyinstaller --onefile --noconsole --name Notify notify.py

echo.
echo Done. Your exe is in the "dist" folder: dist\Notify.exe
echo Copy dist\Notify.exe and config.ini into whatever folder you want to run it from.
pause
