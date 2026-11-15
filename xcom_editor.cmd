@echo off
rem Starts the editor (XCOM Map Workshop) from this repository: the main viewer/editor server, on port 8768
rem (AGENTS.md), serving the whole cache folder. (A release starts it with its own XCOM Map Workshop.cmd.)
rem   xcom_editor.cmd           start it, or restart it if it is running (a re-export or a server change needs
rem                             that: it picks its exports and its code when it starts); it opens the browser
rem   xcom_editor.cmd start     start it only if it is not running, else just open the browser
rem   xcom_editor.cmd restart   the same as no argument
rem   xcom_editor.cmd stop      stop it
rem   xcom_editor.cmd status    say whether it is running
rem It serves the cache setting (python tools\viewer\viewer.py settings shows it), or VIEWER_CACHE when set.
rem Only a process that is this server (viewer.py serve) is ever stopped. For tests, VIEWER_PORT picks
rem another port (8790-8799) and VIEWER_NO_OPEN=1 opens no browser.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not defined VIEWER_PORT set VIEWER_PORT=8768
set URL=http://127.0.0.1:%VIEWER_PORT%/
set ACTION=%~1
if "%ACTION%"=="" set ACTION=restart

call :find
if /i "%ACTION%"=="status" goto status
if /i "%ACTION%"=="stop" goto stop
if /i "%ACTION%"=="restart" goto restart
if /i "%ACTION%"=="start" goto start
echo Unknown action "%ACTION%". Use start, restart, stop or status.
exit /b 2

:status
if not defined PID (echo No editor is running on port %VIEWER_PORT%. & exit /b 0)
call :isviewer || (echo Port %VIEWER_PORT% is in use by process %PID%, which is not the editor. & exit /b 1)
echo The editor is running at %URL% ^(process %PID%^).
exit /b 0

:start
if not defined PID goto launch
call :isviewer || (echo Port %VIEWER_PORT% is in use by process %PID%, which is not the editor. & exit /b 1)
echo The editor is already running at %URL% ^(process %PID%^).
if not "%VIEWER_NO_OPEN%"=="1" start "" "%URL%"
exit /b 0

:restart
if defined PID call :kill || exit /b 1
goto launch

:stop
if not defined PID (echo No editor is running on port %VIEWER_PORT%. & exit /b 0)
call :kill || exit /b 1
exit /b 0

:launch
set OPEN=
if "%VIEWER_NO_OPEN%"=="1" set OPEN=--no-open
set VIEWER_CACHE_ARG=
if defined VIEWER_CACHE set VIEWER_CACHE_ARG="%VIEWER_CACHE%"
rem Its own window, titled, so it can be found and closed later. The server opens the browser itself.
start "XCOM Map Workshop (port %VIEWER_PORT%)" python tools\viewer\viewer.py serve %VIEWER_CACHE_ARG% --port %VIEWER_PORT% %OPEN%
rem Wait up to 15 seconds for it to listen.
for /l %%i in (1,1,15) do (
  call :find
  if defined PID (echo Started the editor at %URL% ^(process !PID!^). & exit /b 0)
  ping -n 2 127.0.0.1 >nul
)
echo The editor did not start; see its window for the error.
exit /b 1

rem PID of the process listening on 127.0.0.1:VIEWER_PORT, or empty.
:find
set PID=
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:"127\.0\.0\.1:%VIEWER_PORT% .*LISTENING"') do set PID=%%p
exit /b 0

rem Succeeds when PID is this server (viewer.py serve).
:isviewer
powershell -NoProfile -Command "exit [int](-not ((Get-CimInstance Win32_Process -Filter 'ProcessId=%PID%').CommandLine -match 'viewer\.py\s+serve'))"
exit /b %errorlevel%

rem Stops PID only if it is this server.
:kill
call :isviewer
if errorlevel 1 (
  echo Port %VIEWER_PORT% is held by process %PID%, which is not the editor; not stopping it.
  exit /b 1
)
taskkill /PID %PID% /F >nul
echo Stopped the editor ^(process %PID%^).
for /l %%i in (1,1,10) do (
  call :find
  if not defined PID exit /b 0
  ping -n 2 127.0.0.1 >nul
)
exit /b 0
