@echo off
rem XCOM Map Workshop: starts the editor (a small server on this computer only) and opens it in the browser.
rem The installer's shortcuts start it; from the zip, run it directly (its first start asks for the game folder).
rem Keep this window open while you use the editor; close it to stop the editor.
setlocal
cd /d "%~dp0"
if not exist "python\python.exe" (
  echo The editor's Python is missing. Install the editor again, or unpack the whole release zip again.
  pause
  exit /b 1
)
title XCOM Map Workshop
echo XCOM Map Workshop opens in your browser at http://127.0.0.1:8768/
echo Keep this window open while you use it; close it to stop the editor.
echo.
"python\python.exe" -B tools\viewer\viewer.py serve --reuse
if errorlevel 1 pause
