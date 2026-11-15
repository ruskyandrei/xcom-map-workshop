<#
Starts XCOM through Steam (steam://rungameid/200510, so the launch-option wrapper runs), clicks Enemy Within in
the launcher (where the install still has it), waits for the main menu, closes the game normally and reports what ran and what changed.

  pwsh -File tools\lab\switch_install.ps1 lab ; pwsh -File tools\lab\steam_launch_test.ps1
  pwsh -File tools\lab\steam_launch_test.ps1 -MenuWait 30 -NoClick   # leave the launcher click to a person

Reports: new wrapper.log lines, Steam's tracked processes, the game's Command line / Base directory and whether
the shell (main menu) loaded, changes in the shared profile, and (when the lab copy is active) the parked LWR
install against the baseline.
#>
param([int]$MenuWait = 25, [int]$StartTimeout = 120, [switch]$NoClick)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')     # the folders, from the settings
$common = Get-SteamCommon
$active = Join-Path $common 'XCom-Enemy-Unknown'
$profileDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\XCOM - Enemy Within'
$labRoot = Get-LabRoot
$wrapperLog = Join-Path $labRoot 'logs\wrapper.log'
$gameLog = Join-Path (Get-SteamFolder) 'logs\gameprocess_log.txt'
$python = Get-LabPython
$manifest = Join-Path $labRoot 'snapshots\runtime-baseline-2026-11-03.sha256'

if (Get-Process | Where-Object { $_.Path -like "$common\XCom-Enemy-Unknown*" }) { throw 'XCOM is running; close it first.' }
function Get-State($dir) { $s = @{}; Get-ChildItem $dir -Recurse -File -Force | ForEach-Object { $s[$_.FullName] = '{0}|{1}' -f $_.Length, $_.LastWriteTimeUtc.Ticks }; $s }
function LineCount($f) { if (Test-Path $f) { (Get-Content $f).Count } else { 0 } }

$mode = if (Test-Path (Join-Path $active 'XComLab-copy.txt')) { 'lab copy' } else { 'live LWR' }
$before = Get-State $profileDir
$w0 = LineCount $wrapperLog; $g0 = LineCount $gameLog
$started = Get-Date
Write-Host "Active install: $mode. Starting XCOM through Steam..."
Start-Process 'steam://rungameid/200510'
# An install whose launcher is the stand-in (tools\lab\XComLauncherSkip.cs, the real one kept as XCOMLauncher_backup.exe)
# starts the game at once: nothing to click.
$noLauncher = Test-Path (Join-Path $active 'XEW\Binaries\Win32\XCOMLauncher_backup.exe')
if ($noLauncher) { Write-Host 'The launcher is replaced here: no click.' }
elseif (-not $NoClick) { & (Join-Path $PSScriptRoot 'click_launcher.ps1') -TimeoutSeconds 60 }

$game = $null
while (-not $game -and ((Get-Date) - $started).TotalSeconds -lt $StartTimeout) {
    Start-Sleep -Milliseconds 500
    $game = Get-Process -Name XComEW -ErrorAction SilentlyContinue | Where-Object { $_.Path } | Select-Object -First 1
}
if ($game) {
    Write-Host "XComEW started: $($game.Path) (PID $($game.Id))"
    if ($game.WaitForExit($MenuWait * 1000)) { Write-Host "XComEW exited by itself within $MenuWait s" }
    else { Write-Host "Still running after $MenuWait s: closing the window"; $null = $game.CloseMainWindow(); $null = $game.WaitForExit(30000) }
} else { Write-Host "No XComEW process within $StartTimeout s" }
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Process | Where-Object { $_.Path -like "$common\XCom-Enemy-Unknown*" -or $_.Path -like '*XComLabWrapper*' }) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
Get-Process | Where-Object { $_.Path -like "$common\XCom-Enemy-Unknown*" -or $_.Path -like '*XComLabWrapper*' } | ForEach-Object { Write-Warning "Still running: $($_.Path)" }

Write-Host "`n=== wrapper.log"; Get-Content $wrapperLog -ErrorAction SilentlyContinue | Select-Object -Skip $w0
Write-Host "`n=== Steam gameprocess_log"; Get-Content $gameLog | Select-Object -Skip $g0 | Where-Object { $_ -match '200510' }
Write-Host "`n=== Game logs written since launch"
foreach ($log in @("$active\XEW\XComGame\Logs\Launch.log", "$profileDir\XComGame\Logs\Launch.log", "$active\XComGame\Logs\Launch.log")) {
    if ((Test-Path $log) -and (Get-Item $log).LastWriteTime -ge $started) {
        Write-Host $log
        Select-String -Path $log -Pattern 'Command line:|Base directory:|Initial startup|LoadMap: XComShell|Exit: Preparing|Closing by request' | Select-Object -First 7 | ForEach-Object { '  ' + $_.Line.Trim() }
    }
}
Write-Host "`n=== Changes under $profileDir"
$after = Get-State $profileDir
$changed = @($after.Keys | Where-Object { $before[$_] -ne $after[$_] } | Sort-Object)
if (-not $changed) { Write-Host '  none' } else { $changed | ForEach-Object { "  $_" } }

$lwr = if ($mode -eq 'lab copy') { Join-Path $common 'XCom-Enemy-Unknown.LWR' } else { $active }
Write-Host "`n=== LWR install ($lwr) vs baseline manifest"
& $python -I (Join-Path $PSScriptRoot 'verify_tree.py') $lwr $manifest
