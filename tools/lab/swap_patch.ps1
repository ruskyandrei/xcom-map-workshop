<#
Puts one variant of a streamed patch map into the lab copy's CookedPCConsole, for EXP-03.

  pwsh -File tools\lab\swap_patch.ps1 status
  pwsh -File tools\lab\swap_patch.ps1 shipped    # LWR's own file (verified against the baseline manifest)
  pwsh -File tools\lab\swap_patch.ps1 rebuilt    # our cook, <lab>\builds\exp01-cook-2026-11-03\PC\patch_bar.udk
  pwsh -File tools\lab\swap_patch.ps1 none       # no patch file at all (control: the patch's effects must vanish)

Works on the lab copy wherever it is (active or parked as XCom-Enemy-Unknown.Lab), never on the LWR install.
The shipped file is saved once to <lab>\snapshots\exp03\, after its hash is checked against the baseline.
<lab> and the Steam library folder come from the settings (tools\lab\LabSettings.ps1).
#>
param([Parameter(Mandatory)][ValidateSet('status', 'shipped', 'rebuilt', 'none')][string]$Variant,
      [string]$Patch = 'patch_bar',
      [string]$Rebuilt = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
$labRoot = Get-LabRoot
if (-not $Rebuilt) { $Rebuilt = Join-Path $labRoot 'builds\exp01-cook-2026-11-03\PC\patch_bar.udk' }
$common = Get-SteamCommon
$manifest = Join-Path $labRoot 'snapshots\runtime-baseline-2026-11-03.sha256'
$store = Join-Path $labRoot 'snapshots\exp03'
$log = Join-Path $labRoot 'logs\swap_patch.log'

$lab = @("$common\XCom-Enemy-Unknown", "$common\XCom-Enemy-Unknown.Lab") | Where-Object { Test-Path "$_\XComLab-copy.txt" } | Select-Object -First 1
if (-not $lab) { throw 'Lab copy not found (no XComLab-copy.txt in XCom-Enemy-Unknown or XCom-Enemy-Unknown.Lab).' }
$target = "$lab\XEW\XComGame\CookedPCConsole\$Patch.upk"
$saved = "$store\$Patch.shipped.upk"
$rel = "XEW/XComGame/CookedPCConsole/$Patch.upk"
$baseline = (Select-String -Path $manifest -SimpleMatch "  $rel" | Select-Object -First 1).Line -split '\s+' | Select-Object -First 1
if (-not $baseline) { throw "$rel is not in the baseline manifest" }
function Hash($f) { if (Test-Path $f) { (Get-FileHash $f -Algorithm SHA256).Hash.ToLower() } }
function Which($h) {
    if (-not $h) { return 'none (no file)' }
    if ($h -eq $baseline) { return 'shipped' }
    if (Test-Path $Rebuilt) { if ($h -eq (Hash $Rebuilt)) { return 'rebuilt' } }
    return 'unknown'
}

if ($Variant -ne 'status') {
    if (Get-Process | Where-Object { $_.Path -and $_.Path -like "$common\XCom-Enemy-Unknown*" }) { throw 'XCOM is running; quit it first.' }
    New-Item -ItemType Directory -Force $store, (Split-Path $log) | Out-Null
    if (-not (Test-Path $saved)) {
        if ((Hash $target) -ne $baseline) { throw "No saved shipped copy yet and $target is not the shipped file." }
        Copy-Item $target $saved
    }
    if ((Hash $saved) -ne $baseline) { throw "$saved does not match the baseline hash" }
    switch ($Variant) {
        'shipped' { Copy-Item $saved $target -Force }
        'rebuilt' { if (-not (Test-Path $Rebuilt)) { throw "Missing $Rebuilt" }; Copy-Item $Rebuilt $target -Force }
        'none'    { if (Test-Path $target) { [IO.File]::Delete($target) } }
    }
    Add-Content $log ("{0}  {1} -> {2} in {3}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Patch, $Variant, $lab)
}
$h = Hash $target
"{0} in {1}: {2}{3}" -f $Patch, $lab, (Which $h), $(if ($h) { "  (sha256 $($h.Substring(0, 16))…)" })
