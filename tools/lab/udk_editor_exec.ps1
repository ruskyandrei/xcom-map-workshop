<#
Runs editor commands in the authoring UDK without anyone using the GUI.

Starts UDK.exe editor <map> -EXEC=<command file> -forcelogflush, waits until the log shows that the file ran
(and an optional extra log pattern), optionally saves the clipboard text (for EDIT COPY, which copies the selected
actors as T3D), then ends the editor. Put QUIT_EDITOR last in the command file to let the editor close itself
after saving; otherwise it is ended once the wait is over (unsaved changes are discarded).

  pwsh -File tools\lab\udk_editor_exec.ps1 -Map patch_exp04 -Commands <lab>\exp04\export.txt -Clipboard <lab>\exp04\patch_exp04.t3d
  pwsh -File tools\lab\udk_editor_exec.ps1 -Map patch_exp04 -Commands <lab>\exp04\import.txt -WaitFor 'Correctly saved|Saving'

The user's clipboard text is saved first and put back afterwards. Logs: <lab>\logs\udk-exec-<time>.log.
<lab> and -Udk come from the settings (tools\lab\LabSettings.ps1).
#>
param([Parameter(Mandatory)][string]$Map, [Parameter(Mandatory)][string]$Commands, [string]$Clipboard = '',
      [string]$WaitFor = '', [int]$Timeout = 120, [string]$Udk = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
if (-not $Udk) { $Udk = Get-LabUdk }
if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { throw 'A UDK process is already running; close it first.' }
if (-not (Test-Path $Commands)) { throw "Missing $Commands" }
$log = Join-Path $Udk 'UDKGame\Logs\Launch.log'
$keep = Join-Path (Get-LabRoot) "logs\udk-exec-$(Get-Date -Format 'HHmmss').log"
$savedClip = try { Get-Clipboard -Raw } catch { $null }
if ($Clipboard) { Set-Clipboard -Value 'udk_editor_exec: waiting for EDIT COPY' }

$t0 = Get-Date
$p = Start-Process -FilePath "$Udk\Binaries\Win32\UDK.exe" -ArgumentList "editor $Map -EXEC=`"$Commands`" -forcelogflush" -WorkingDirectory "$Udk\Binaries\Win32" -PassThru
$state = 'timeout'
while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
    Start-Sleep -Seconds 1
    if ($p.HasExited) { $state = "editor exited ($($p.ExitCode))"; break }
    $text = if (Test-Path $log) { Get-Content $log -Raw -ErrorAction SilentlyContinue } else { '' }
    if ($text -notmatch 'Execing file') { continue }
    if ($WaitFor -and $text -notmatch $WaitFor) { continue }
    if ($Clipboard -and ((Get-Clipboard -Raw) -like 'udk_editor_exec:*')) { continue }
    $state = 'done'; Start-Sleep -Seconds 2; break
}
$secs = [int]((Get-Date) - $t0).TotalSeconds
if ($Clipboard -and $state -eq 'done') { Get-Clipboard -Raw | Set-Content -Path $Clipboard -Encoding utf8NoBOM; Write-Host "clipboard saved to $Clipboard ($((Get-Item $Clipboard).Length) bytes)" }
if (-not $p.HasExited) { $p.Kill(); $null = $p.WaitForExit(10000) }
if (Test-Path $log) { Copy-Item $log $keep }
if ($null -ne $savedClip) { Set-Clipboard -Value $savedClip } elseif ($Clipboard) { Set-Clipboard -Value $null }
Write-Host "$state after $secs s; log $keep"
if ($state -ne 'done' -and $state -notlike 'editor exited (0)') { exit 1 }
