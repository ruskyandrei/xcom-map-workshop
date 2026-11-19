<#
Switches which XCOM install Steam runs: the live LWR install, the lab copy or the third copy (LWR v3 beta).

All of them live side by side in Steam's steamapps\common (the lwr setting, or the folder holding the game folder it
names: tools\lab\LabSettings.ps1). The active one is always named XCom-Enemy-Unknown (the folder Steam launches);
the parked ones are XCom-Enemy-Unknown.LWR, XCom-Enemy-Unknown.Lab and XCom-Enemy-Unknown.LWR3.
The copies are recognised by XComLab-copy.txt in their root, which also makes XComLabWrapper.exe add -nohomedir so
their settings and saves stay inside the copy; a line "copy=lwr3" in it marks the third copy (LWR v3 beta, made
19 November 2026), a marker without a copy= line is the lab copy.

  pwsh -File tools\lab\switch_install.ps1 status
  pwsh -File tools\lab\switch_install.ps1 lab    # Steam now runs the lab copy
  pwsh -File tools\lab\switch_install.ps1 lwr3   # Steam now runs the third copy (LWR v3 beta)
  pwsh -File tools\lab\switch_install.ps1 lwr    # back to normal play; verifies LWR against the baseline

Recovers a half-finished switch (no active folder) by completing it towards the requested target.
#>
param([Parameter(Mandatory)][ValidateSet('status', 'lab', 'lwr', 'lwr3')][string]$Target)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
$common = Get-SteamCommon
$active = Join-Path $common 'XCom-Enemy-Unknown'
$parked = [ordered]@{
    lwr  = Join-Path $common 'XCom-Enemy-Unknown.LWR'
    lab  = Join-Path $common 'XCom-Enemy-Unknown.Lab'
    lwr3 = Join-Path $common 'XCom-Enemy-Unknown.LWR3'
}
$marker = 'XComLab-copy.txt'

function Kind($dir) {
    if (-not (Test-Path $dir)) { return 'absent' }
    $file = Join-Path $dir $marker
    if (-not (Test-Path $file)) { return 'lwr' }
    $line = Get-Content -LiteralPath $file | Where-Object { $_ -match '^\s*copy\s*=' } | Select-Object -First 1
    if ($line) { ($line -split '=', 2)[1].Trim().ToLowerInvariant() } else { 'lab' }
}
function State {
    $parts = @('active={0}' -f (Kind $active))
    foreach ($k in $parked.Keys) { $parts += 'parked.{0}={1}' -f (Split-Path $parked[$k] -Extension).TrimStart('.'), (Kind $parked[$k]) }
    $parts -join ' '
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

$state = State
if ($Target -eq 'status') { Write-Host $state; return }
$labRoot = Get-LabRoot
$switchLog = Join-Path $labRoot 'logs\switch.log'
$manifest = Join-Path $labRoot 'snapshots\runtime-baseline-2026-11-03.sha256'
foreach ($k in $parked.Keys) {
    $kind = Kind $parked[$k]
    if ($kind -ne 'absent' -and $kind -ne $k) { throw "Folders are mislabelled ($state); sort them out by hand." }
}
if (Get-Process | Where-Object { $_.Path -and ($_.Path -like "$common\XCom-Enemy-Unknown*" -or $_.Path -like '*XComLabWrapper*') }) {
    throw 'XCOM is running; quit it first.'
}

$wantFrom = $parked[$Target]   # what becomes active
$current = Kind $active
switch ($current) {
    { $_ -eq $Target } { Write-Host "Already active: $Target ($state)" }
    'absent' {
        if ((Kind $wantFrom) -ne $Target) { throw "No active folder and no parked $Target folder ($state)" }
        Note "recovering a half-finished switch towards $Target"
        Rename $wantFrom $active
    }
    default {
        if (-not $parked.Contains($current)) { throw "The active folder is an unknown copy '$current' ($state); sort it out by hand." }
        if ((Kind $wantFrom) -ne $Target) { throw "Parked $Target folder not found ($state)" }
        $wantPark = $parked[$current]   # where the current active folder goes
        Rename $active $wantPark
        try { Rename $wantFrom $active }
        catch { Note "second rename failed: $($_.Exception.Message); undoing"; Rename $wantPark $active; throw }
    }
}
Note ("now: {0}" -f (State))

if ($Target -eq 'lwr') {
    Write-Host 'Verifying the LWR install against the baseline...'
    & (Get-LabPython) -I (Join-Path $PSScriptRoot 'verify_tree.py') $active $manifest
    if ($LASTEXITCODE -ne 0) { Write-Warning 'The LWR install differs from the baseline: check it before playing.'; exit 1 }
}
