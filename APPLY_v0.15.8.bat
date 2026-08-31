@echo off
setlocal
cd /d "%~dp0"
python apply_v0_15_8.py
if errorlevel 1 (
  echo.
  echo Patch failed. Leave this window open and send the error to ChatGPT.
  pause
  exit /b 1
)
del /q apply_v0_15_8.py
del /q "%~f0"
