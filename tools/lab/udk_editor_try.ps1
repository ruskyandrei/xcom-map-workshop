<#
Starts the authoring UDK editor and retries when it freezes during startup.

With the LiQuiD911 tree the editor often spins forever while loading Engine.u (LiQuiD911 needed about ten
restarts in 2015; seen again on 3 November 2026). Each try runs with -forcelogflush, waits up to -Timeout
seconds for "Initial startup" in Launch.log (and, when a map is named, for its MAP LOAD to finish), and kills
the editor if it never gets there. Every try's log is kept as <Logs>\udk-try-<time>-<n>.log. -Udk defaults to the
udk setting, -Logs to <lab>\logs (the lab setting), or UDK's own UDKGame\Logs without one (tools\lab\LabSettings.ps1).

  pwsh -File tools\lab\udk_editor_try.ps1 -Map patch_bar
  pwsh -File tools\lab\udk_editor_try.ps1 -Map patch_bar -Bits Win64 -Cores 4 -Tries 5
  pwsh -File tools\lab\udk_editor_try.ps1 -Map patch_bar -Close   # end the editor again once it has opened (unsaved changes are discarded)

-Dx11 starts the editor with its DirectX 11 renderer. It is needed on a desktop that is not displayed
(tools\lab\HiddenRun.cs): there DirectX 9 finds no hardware, and the editor stops at a "does not support floating
point render targets" box.
#>
param([string]$Map = '', [ValidateSet('Win32', 'Win64')][string]$Bits = 'Win32', [int]$Cores = 0,
      [int]$Tries = 3, [int]$Timeout = 60, [string]$Udk = '', [string]$Logs = '', [switch]$Dx11, [switch]$Close)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
if (-not $Udk) { $Udk = Get-LabUdk }
if (-not $Logs) { $labRoot = Get-LabSetting 'lab'; $Logs = if ($labRoot) { Join-Path $labRoot 'logs' } else { Join-Path $Udk 'UDKGame\Logs' } }
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { throw 'A UDK process is already running; close it first.' }
$log = Join-Path $Udk 'UDKGame\Logs\Launch.log'
$stamp = Get-Date -Format 'HHmmss'
$editorArgs = (@('editor', $Map, '-forcelogflush', $(if ($Dx11) { '-dx11' })) | Where-Object { $_ }) -join ' '

for ($n = 1; $n -le $Tries; $n++) {
    $t0 = Get-Date
    $p = Start-Process -FilePath (Join-Path $Udk "Binaries\$Bits\UDK.exe") -ArgumentList $editorArgs -WorkingDirectory (Join-Path $Udk "Binaries\$Bits") -PassThru
    if ($Cores -gt 0) { Start-Sleep -Milliseconds 300; $p.ProcessorAffinity = [IntPtr]([int64][math]::Pow(2, $Cores) - 1) }
    $state = 'timeout'
    while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
        Start-Sleep -Seconds 1
        if ($p.HasExited) { $state = "exited ($($p.ExitCode))"; break }
        $text = if (Test-Path $log) { Get-Content $log -Raw -ErrorAction SilentlyContinue } else { '' }
        if ($text -match 'Initial startup' -and (-not $Map -or $text -match 'MAP CHECKDEP')) { $state = 'opened'; break }
    }
    $secs = [int]((Get-Date) - $t0).TotalSeconds
    $keep = Join-Path $Logs "udk-try-$stamp-$n.log"
    if (Test-Path $log) { Copy-Item $log $keep }
    $last = if (Test-Path $keep) { (Get-Content $keep | Where-Object { $_.Trim() } | Select-Object -Last 1) } else { '' }
    Write-Host ("try {0}: {1} after {2} s ({3}{4}{5}) last log line: {6}" -f $n, $state, $secs, $Bits, $(if ($Dx11) { ', DX11' } else { '' }), $(if ($Cores) { ", $Cores cores" } else { '' }), $last)
    if ($state -eq 'opened') {
        if ($Close) { $p.Kill(); $null = $p.WaitForExit(10000) }   # a normal close can stop on a "save changes?" prompt
        return
    }
    if (-not $p.HasExited) { $p.Kill(); $null = $p.WaitForExit(10000) }
    Start-Sleep -Seconds 2
}
Write-Warning "The editor did not open in $Tries tries."
exit 1
