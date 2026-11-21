@echo off
REM Installs the free extras: natural voices, PDF/Word upload and video export.
pip install -r requirements.txt
playwright install chromium
echo.
echo Also install ffmpeg (needed for video):  winget install ffmpeg   (or download from https://ffmpeg.org)
pause
