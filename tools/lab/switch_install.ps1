<#
Switches which XCOM install Steam runs: the live LWR install or the lab copy.

Both live side by side in Steam's steamapps\common (the lwr setting, or the folder holding the game folder it names:
tools\lab\LabSettings.ps1). The active one is always named XCom-Enemy-Unknown
(the folder Steam launches); the parked one is XCom-Enemy-Unknown.LWR or
XCom-Enemy-Unknown.Lab. The lab copy is recognised by XComLab-copy.txt in its root, which also makes
XComLabWrapper.exe add -nohomedir so its settings and saves stay inside the copy.

  pwsh -File tools\lab\switch_install.ps1 status
  pwsh -File tools\lab\switch_install.ps1 lab    # Steam now runs the lab copy
  pwsh -File tools\lab\switch_install.ps1 lwr    # back to normal play; verifies LWR against the baseline

Recovers a half-finished switch (no active folder) by completing it towards the requested target.
#>
param([Parameter(Mandatory)][ValidateSet('status', 'lab', 'lwr')][string]$Target)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
$common = Get-SteamCommon
$active = Join-Path $common 'XCom-Enemy-Unknown'
$parkedLwr = Join-Path $common 'XCom-Enemy-Unknown.LWR'
$parkedLab = Join-Path $common 'XCom-Enemy-Unknown.Lab'
$marker = 'XComLab-copy.txt'

function Kind($dir) {
    if (-not (Test-Path $dir)) { return 'absent' }
    if (Test-Path (Join-Path $dir $marker)) { 'lab' } else { 'lwr' }
}
function Note($text) {
    Write-Host $text
    New-Item -ItemType Directory -Force (Split-Path $switchLog) | Out-Null
    Add-Content $switchLog ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $text)
}
function Rename($from, $to) {
    if (Test-Path $to) { throw "Refusing to rename onto existing $to" }
    [IO.Directory]::Move($from, $to)
    Note "renamed $(Split-Path $from -Leaf) -> $(Split-Path $to -Leaf)"
}

$state = 'active={0} parked.LWR={1} parked.Lab={2}' -f (Kind $active), (Kind $parkedLwr), (Kind $parkedLab)
if ($Target -eq 'status') { Write-Host $state; return }
$labRoot = Get-LabRoot
$switchLog = Join-Path $labRoot 'logs\switch.log'
$manifest = Join-Path $labRoot 'snapshots\runtime-baseline-2026-11-03.sha256'
if ((Kind $parkedLwr) -eq 'lab' -or (Kind $parkedLab) -eq 'lwr') { throw "Folders are mislabelled ($state); sort them out by hand." }
if (Get-Process | Where-Object { $_.Path -and ($_.Path -like "$common\XCom-Enemy-Unknown*" -or $_.Path -like '*XComLabWrapper*') }) {
    throw 'XCOM is running; quit it first.'
}

$wantPark = if ($Target -eq 'lab') { $parkedLwr } else { $parkedLab }   # where the current active folder goes
$wantFrom = if ($Target -eq 'lab') { $parkedLab } else { $parkedLwr }   # what becomes active
switch (Kind $active) {
    { $_ -eq $Target } { Write-Host "Already active: $Target ($state)" }
    'absent' {
        if ((Kind $wantFrom) -ne $Target) { throw "No active folder and no parked $Target folder ($state)" }
        Note "recovering a half-finished switch towards $Target"
        Rename $wantFrom $active
    }
    default {
        if ((Kind $wantFrom) -ne $Target) { throw "Parked $Target folder not found ($state)" }
        Rename $active $wantPark
        try { Rename $wantFrom $active }
        catch { Note "second rename failed: $($_.Exception.Message); undoing"; Rename $wantPark $active; throw }
    }
}
Note ("now: active={0} parked.LWR={1} parked.Lab={2}" -f (Kind $active), (Kind $parkedLwr), (Kind $parkedLab))

if ($Target -eq 'lwr') {
    Write-Host 'Verifying the LWR install against the baseline...'
    & (Get-LabPython) -I (Join-Path $PSScriptRoot 'verify_tree.py') $active $manifest
    if ($LASTEXITCODE -ne 0) { Write-Warning 'The LWR install differs from the baseline: check it before playing.'; exit 1 }
}
