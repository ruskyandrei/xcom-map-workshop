<#
The folders of this computer that the lab scripts use, from the editor settings (as tools/lab/labpaths.py reads them
for Python): <Documents>\XCOM Map Workshop\settings.json, or the file XCOM_MAP_WORKSHOP_SETTINGS names, set with
python tools/viewer/viewer.py settings --lab <folder> --udk <folder> --lwr <folder>. Dot-source it after a script's
param block, and fill the folder parameters left empty from it (an explicit parameter wins):

  . (Join-Path $PSScriptRoot 'LabSettings.ps1')            # from tools\lab; ..\lab\LabSettings.ps1 elsewhere
  if (-not $Udk) { $Udk = Get-LabUdk }

  Get-LabSetting <key>   a setting's folder (lab, udk, lwr, cache, ...), or $null when unset
  Get-LabRoot            our lab's working folder (lab): logs, snapshots, patchtool work, compiled helpers in bin
  Get-LabUdk             UDK 2011-09 (udk)
  Get-SteamCommon        the folder holding the installs side by side: lwr when it holds game folders, else the
                         parent of the game folder it names
  Get-ActiveGame         <Steam common>\XCom-Enemy-Unknown, the folder Steam runs (the lab copy while its root holds
                         XComLab-copy.txt)
  Get-LabPython          python on PATH (else the py launcher)
  Get-SteamFolder        Steam's own folder, from the registry (HKCU:\Software\Valve\Steam, SteamPath)
  Get-Csc                the .NET Framework 4 C# compiler under %WINDIR%
The required ones throw, saying how to set the setting, when it is missing.
#>

function Get-LabSettingsPath {
    if ($env:XCOM_MAP_WORKSHOP_SETTINGS) { return $env:XCOM_MAP_WORKSHOP_SETTINGS }
    # the Documents folder Windows reports (it can be redirected), as tools/viewer/settings.py finds it
    $documents = [Environment]::GetFolderPath('MyDocuments')
    if (-not $documents) { $documents = Join-Path $HOME 'Documents' }
    Join-Path $documents 'XCOM Map Workshop\settings.json'
}

function Get-LabSetting([string]$Key) {
    $path = Get-LabSettingsPath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    $data = Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
    # the game install was the lwr setting before 8 November 2026 (settings.py ALIASES): either name finds it
    $names = if ($Key -in 'lwr', 'game') { 'game', 'lwr' } else { @($Key) }
    foreach ($name in $names) {
        $entry = $data.PSObject.Properties[$name]
        if ($entry -and -not [string]::IsNullOrWhiteSpace([string]$entry.Value)) { return [string]$entry.Value }
    }
    $null
}

function Get-RequiredLabSetting([string]$Key) {
    $value = Get-LabSetting $Key
    if (-not $value) { throw "The $Key setting is not set ($(Get-LabSettingsPath)): python tools/viewer/viewer.py settings --$Key <folder>" }
    $value
}

function Get-LabRoot { Get-RequiredLabSetting 'lab' }

function Get-LabUdk { Get-RequiredLabSetting 'udk' }

function Get-SteamCommon {
    $lwr = (Get-RequiredLabSetting 'lwr').TrimEnd('\', '/')
    if (Test-Path -LiteralPath (Join-Path $lwr 'XEW\XComGame\CookedPCConsole') -PathType Container) { Split-Path -Parent $lwr }
    else { $lwr }
}

function Get-ActiveGame { Join-Path (Get-SteamCommon) 'XCom-Enemy-Unknown' }

function Get-LabPython {
    foreach ($name in 'python', 'py') {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { return $cmd.Source }
    }
    throw 'no python on PATH (python or py)'
}

function Get-SteamFolder {
    $steam = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -Name SteamPath -ErrorAction SilentlyContinue).SteamPath
    if (-not $steam) { throw 'Steam is not installed for this user (no SteamPath in HKCU:\Software\Valve\Steam)' }
    $steam -replace '/', '\'
}

function Get-Csc { Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe' }
