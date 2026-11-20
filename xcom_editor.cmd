@echo off
rem Starts the editor (XCOM Map Workshop) from this repository: the main viewer/editor server, on port 8768
rem (AGENTS.md), serving the whole cache folder. (A release starts it with its own XCOM Map Workshop.cmd.)
rem   xcom_editor.cmd           start it, or restart it if it is running (a re-export or a server change needs
rem                             that: it picks its exports and its code when it starts); it opens the browser
rem   xcom_editor.cmd start     start it only if it is not running, else just open the browser
rem   xcom_editor.cmd restart   the same as no argument
rem   xcom_editor.cmd stop      stop it
rem   xcom_editor.cmd status    say whether it is running
rem Before it stops a running editor it asks it whether it is building (tools\viewer\launch_check.py): when it is, or
rem does not answer, it asks here first, and stops it only on a "y". After a start it waits for the editor to answer
rem on its port, which the main server does once it has prepared its cache.
rem It serves the cache setting (python tools\viewer\viewer.py settings shows it), or VIEWER_CACHE when set.
rem Only a process that is this server (viewer.py serve) is ever stopped. For tests, VIEWER_PORT picks
rem another port (8790-8799), VIEWER_NO_OPEN=1 opens no browser and VIEWER_ARGS adds arguments to serve (scratch
rem folders: --projects, --builds, --squad, --dry-play, --install).
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
if not defined PID goto launch
call :kill && goto launch
rem not stopped: when that was the answer, the running editor is opened instead
if "%DECLINED%"=="1" if not "%VIEWER_NO_OPEN%"=="1" start "" "%URL%"
exit /b 1

:stop
if not defined PID (echo No editor is running on port %VIEWER_PORT%. & exit /b 0)
call :kill || exit /b 1
exit /b 0

:launch
set OPEN=
if "%VIEWER_NO_OPEN%"=="1" set OPEN=--no-open
set VIEWER_CACHE_ARG=
rem (a folder ending in \ gets it doubled, or the \ escapes the closing quote)
if defined VIEWER_CACHE set VIEWER_CACHE_ARG="%VIEWER_CACHE%"
if defined VIEWER_CACHE if "%VIEWER_CACHE:~-1%"=="\" set VIEWER_CACHE_ARG="%VIEWER_CACHE%\"
rem Its own window, titled, so it can be found and closed later. The server opens the browser itself.
start "XCOM Map Workshop (port %VIEWER_PORT%)" python tools\viewer\viewer.py serve %VIEWER_CACHE_ARG% --port %VIEWER_PORT% %OPEN% %VIEWER_ARGS%
rem Wait for it to answer on its port (it prepares its cache first), or for its process to end.
python tools\viewer\launch_check.py wait --port %VIEWER_PORT%
if errorlevel 1 exit /b 1
call :find
echo Started the editor at %URL% ^(process %PID%^).
exit /b 0

rem PID of the process listening on 127.0.0.1:VIEWER_PORT, or empty.
:find
set PID=
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:"127\.0\.0\.1:%VIEWER_PORT% .*LISTENING"') do set PID=%%p
exit /b 0

rem Succeeds when PID is this server (viewer.py serve).
:isviewer
powershell -NoProfile -Command "exit [int](-not ((Get-CimInstance Win32_Process -Filter 'ProcessId=%PID%').CommandLine -match 'viewer\.py\s+serve'))"
exit /b %errorlevel%

rem Succeeds when the editor may be stopped: it is building nothing, or it is and the answer here is yes.
:busy
python tools\viewer\launch_check.py busy --port %VIEWER_PORT%
if not errorlevel 1 exit /b 0
set ANSWER=
set /p ANSWER=Stop the editor anyway? [y/N]
if /i "%ANSWER%"=="y" exit /b 0
if /i "%ANSWER%"=="yes" exit /b 0
set DECLINED=1
echo The editor keeps running at %URL%.
exit /b 1

rem Stops PID only if it is this server, it may be stopped (busy) and its port is free afterwards.
:kill
call :isviewer
if errorlevel 1 (
  echo Port %VIEWER_PORT% is held by process %PID%, which is not the editor; not stopping it.
  exit /b 1
)
call :busy || exit /b 1
set KILLED=%PID%
taskkill /PID %PID% /F >nul
if errorlevel 1 (
  echo The editor ^(process %KILLED%^) could not be stopped.
  exit /b 1
)
for /l %%i in (1,1,10) do (
  call :find
  if not defined PID (echo Stopped the editor ^(process !KILLED!^). & exit /b 0)
  ping -n 2 127.0.0.1 >nul
)
echo The editor ^(process %KILLED%^) was stopped, but port %VIEWER_PORT% is still held ^(process %PID%^); nothing more is started.
exit /b 1
