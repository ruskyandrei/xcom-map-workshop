"""The scripts a map pack's zip carries (manager.pack), so that whoever gets the pack installs it with a double-click
and takes it out again the same way, without the editor: Install.cmd and Uninstall.cmd, which run pack-tools\\pack.ps1
with Windows' own PowerShell (5.1 or later).

Install asks for the game folder (or takes it as its argument; it offers the Steam installs it finds), refuses while
XCOM runs, keeps copies of DefaultMaps.ini and DefaultLZMutator.ini as they are, copies the pack's files, adds each
map's records after its base map's (and, for a map made to replace its original, comments the base map's own records
out: each map says which in pack.json, so one pack can hold both kinds), adds its landing zones where the install has Long War's file, and writes down what it did in
<game>\\XCOM Map Workshop\\packs\\<pack id>.json. Uninstall undoes exactly that: the lines it added go, the lines it
commented out come back, the files it copied are deleted if unchanged; it says whether DefaultMaps.ini is then byte
for byte as it was before the pack (it is, unless something else changed the file meanwhile, whose changes stay).

The lines come from pack.json, worked out from the install the pack was made from (installs.rotation_plan): a map whose
base map has no record in the target install is left out, and so is one that already has a record of its name there.
The files are read and written as bytes (Latin-1, CRLF), as the editor's own install step does.
"""

CMD = r'''@echo off
rem {what} this map pack. Double-click it, or give the game folder: {name}.cmd "D:\Steam\steamapps\common\XCom-Enemy-Unknown"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack-tools\pack.ps1" {action} %*
set code=%errorlevel%
if "%~1"=="" pause
exit /b %code%
'''

INSTALL_CMD = CMD.format(what='Installs', name='Install', action='install').replace('\n', '\r\n')
UNINSTALL_CMD = CMD.format(what='Takes out', name='Uninstall', action='uninstall').replace('\n', '\r\n')

PS1 = r'''# Installs a map pack made with the XCOM Map Workshop into a game folder, or takes it out again.
#   pack.ps1 install [<game folder>]      pack.ps1 uninstall [<game folder>]
# Run by Install.cmd and Uninstall.cmd beside the pack's README. What it does is in the README.
param([Parameter(Position = 0)][string]$Action = 'install', [Parameter(Position = 1)][string]$Game = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$latin = [Text.Encoding]::GetEncoding(28591)

function Fail([string]$message) { Write-Host "Stopped: $message" -ForegroundColor Red; exit 1 }
function Read-Lines([string]$path) {
    $text = $latin.GetString([IO.File]::ReadAllBytes($path))
    if (([regex]::Matches($text, "`n")).Count -ne ([regex]::Matches($text, "`r`n")).Count) { Fail "$path has mixed line endings; it is left alone." }
    $list = New-Object 'System.Collections.Generic.List[string]'
    $list.AddRange([string[]]($text -split "`r`n"))
    return ,$list
}
function Write-Lines([string]$path, $lines) { [IO.File]::WriteAllBytes($path, $latin.GetBytes([string]::Join("`r`n", [string[]]$lines))) }
function Sha([string]$path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() }
function Test-Game([string]$folder) {
    return $folder -and (Test-Path -LiteralPath (Join-Path $folder 'XEW\XComGame\Config\DefaultMaps.ini')) -and
        (Test-Path -LiteralPath (Join-Path $folder 'XEW\XComGame\CookedPCConsole'))
}
function Find-Games {
    $found = @()
    try {
        $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction Stop).SteamPath
        $libraries = @($steam)
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($m in [regex]::Matches((Get-Content -Raw -LiteralPath $vdf), '"path"\s+"([^"]+)"')) { $libraries += $m.Groups[1].Value.Replace('\\', '\') }
        }
        foreach ($library in $libraries) {
            $folder = Join-Path $library 'steamapps\common\XCom-Enemy-Unknown'
            if ((Test-Game $folder) -and ($found -notcontains $folder)) { $found += $folder }
        }
    } catch { }
    return $found
}
# Where a run of lines starts in a list, or -1.
function Find-Run($lines, [string[]]$run) {
    if ($run.Count -eq 0) { return -1 }
    for ($i = 0; $i -le $lines.Count - $run.Count; $i++) {
        $same = $true
        for ($k = 0; $k -lt $run.Count; $k++) { if ($lines[$i + $k] -cne $run[$k]) { $same = $false; break } }
        if ($same) { return $i }
    }
    return -1
}

if (-not (Test-Path -LiteralPath (Join-Path $root 'pack.json'))) { Fail "pack.json is not beside the scripts: unzip the whole pack first." }
$pack = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root 'pack.json') | ConvertFrom-Json
Write-Host "$($pack.name): $(@($pack.maps).Count) map(s), made with the XCOM Map Workshop $($pack.editorVersion)"

if (-not $Game) {
    $found = @(Find-Games)
    if ($found.Count) { Write-Host "Found: $($found -join '; ')" }
    $prompt = 'The game folder (the one with the XEW folder in it)'
    if ($found.Count) { $prompt += " [Enter for $($found[0])]" }
    $Game = (Read-Host $prompt).Trim().Trim('"')
    if (-not $Game -and $found.Count) { $Game = $found[0] }
}
if (-not (Test-Game $Game)) { Fail "'$Game' is not an XCOM game folder: it has no XEW\XComGame\Config\DefaultMaps.ini." }
$Game = (Resolve-Path -LiteralPath $Game).Path
if (Get-Process -Name XComEW -ErrorAction SilentlyContinue) { Fail 'XCOM is running. Close it and run this again.' }

$mapsPath = Join-Path $Game 'XEW\XComGame\Config\DefaultMaps.ini'
$lzPath = Join-Path $Game 'XEW\XComGame\Config\DefaultLZMutator.ini'
$cooked = Join-Path $Game 'XEW\XComGame\CookedPCConsole'
$stateFolder = Join-Path $Game 'XCOM Map Workshop\packs'
$statePath = Join-Path $stateFolder "$($pack.id).json"
$backup = Join-Path $stateFolder "$($pack.id)-before"

function Uninstall-Pack {
    if (-not (Test-Path -LiteralPath $statePath)) { return $false }
    $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
    $left = @()
    $maps = Read-Lines $mapsPath
    foreach ($block in @($state.added)) {
        $run = [string[]]@($block.lines)
        $at = Find-Run $maps $run
        if ($at -lt 0) { $left += "the records of $($block.variant) have changed: take them out by hand"; continue }
        $maps.RemoveRange($at, $run.Count)
    }
    foreach ($line in @($state.commented)) {
        $at = $maps.IndexOf(';' + $line)
        if ($at -lt 0) { $left += 'a record this pack commented out has changed since: check it by hand'; continue }
        $maps[$at] = $line
    }
    Write-Lines $mapsPath $maps
    if (@($state.zones).Count -and (Test-Path -LiteralPath $lzPath)) {
        $lz = Read-Lines $lzPath
        foreach ($block in @($state.zones)) {
            $run = [string[]]@($block.lines)
            $at = Find-Run $lz $run
            if ($at -lt 0) { $left += "the landing zones of $($block.variant) have changed: take them out by hand"; continue }
            $lz.RemoveRange($at, $run.Count)
        }
        Write-Lines $lzPath $lz
    }
    $gone = 0
    foreach ($file in @($state.files)) {
        $path = Join-Path $cooked $file.name
        if (-not (Test-Path -LiteralPath $path)) { continue }
        if ((Sha $path) -ne $file.sha256) { $left += "$($file.name) has changed since: it stays"; continue }
        Remove-Item -LiteralPath $path
        $gone++
    }
    Remove-Item -LiteralPath $statePath
    Write-Host "Taken out: the records of $(@($state.added).Count) map(s), $(@($state.commented).Count) record(s) of the game's own back in use, $gone file(s)."
    foreach ($note in $left) { Write-Host "  Left: $note" -ForegroundColor Yellow }
    $before = Join-Path $backup 'DefaultMaps.ini'
    if (Test-Path -LiteralPath $before) {
        if ((Sha $before) -eq (Sha $mapsPath)) {
            Write-Host 'DefaultMaps.ini is exactly as it was before the pack.'
            Remove-Item -LiteralPath $backup -Recurse
        } else {
            Write-Host "DefaultMaps.ini has other changes made since the pack was installed; they are kept. The file from before the pack is in $backup" -ForegroundColor Yellow
        }
    }
    return $true
}

if ($Action -eq 'uninstall') {
    if (-not (Uninstall-Pack)) { Write-Host "This pack is not installed in $Game (nothing to take out)." }
    exit 0
}
if ($Action -ne 'install') { Fail "Unknown action '$Action': install or uninstall." }

# ---- install
if (Test-Path -LiteralPath $statePath) {
    Write-Host 'This pack is installed already: taking the earlier install out first.'
    [void](Uninstall-Pack)
}
$source = Join-Path $root 'XEW\XComGame\CookedPCConsole'
$names = @($pack.files.PSObject.Properties | ForEach-Object { $_.Name })
foreach ($name in $names) {
    $from = Join-Path $source $name
    if (-not (Test-Path -LiteralPath $from)) { Fail "$name is missing from the pack: unzip the whole pack first." }
    if ((Sha $from) -ne $pack.files.$name) { Fail "$name in the pack is damaged (its checksum differs)." }
    $to = Join-Path $cooked $name
    if ((Test-Path -LiteralPath $to) -and (Sha $to) -ne $pack.files.$name) {
        Fail "The game already has another $name. Nothing was changed; take that file's owner out first."
    }
}
$maps = Read-Lines $mapsPath
$lz = $null
if (Test-Path -LiteralPath $lzPath) { $lz = Read-Lines $lzPath }
$hasLz = $null -ne $lz
$added = @(); $commented = @(); $zones = @(); $skipped = @(); $done = @()
foreach ($map in @($pack.maps)) {
    $base = [regex]::Escape($map.base)
    $live = '^\s*Maps=\(.*(?<![A-Za-z])Name="' + $base + '"'
    $any = '^\s*;*\s*Maps=\(.*(?<![A-Za-z])Name="' + $base + '"'
    $mine = '^\s*Maps=\(.*(?<![A-Za-z])Name="' + [regex]::Escape($map.variant) + '"'
    $last = -1; $has = $false
    for ($i = 0; $i -lt $maps.Count; $i++) {
        if ($maps[$i] -match $any) { $last = $i }
        if ($maps[$i] -match $mine) { $has = $true }
    }
    if ($has) { $skipped += "$($map.variant): the game already has a record of that name"; continue }
    if ($last -lt 0) { $skipped += "$($map.variant): this game has no record for its base map, $($map.base)"; continue }
    $records = [string[]]@($map.records)
    $maps.InsertRange($last + 1, $records)
    $added += @{ variant = $map.variant; lines = $records }
    # each map says whether it replaces its base map (a pack from before that says it once, for all)
    $way = $map.mode
    if (-not $way) { $way = $pack.mode }
    if ($way -eq 'replace') {
        for ($i = 0; $i -lt $maps.Count; $i++) {
            if ($maps[$i] -match $live) { $commented += $maps[$i]; $maps[$i] = ';' + $maps[$i] }
        }
    }
    if ($hasLz -and $map.landingZones) {
        $tag = 'MapName="' + $map.base + '"'; $own = 'MapName="' + $map.variant + '"'
        $at = -1; $there = $false
        for ($i = 0; $i -lt $lz.Count; $i++) {
            if ($lz[$i].Contains($own)) { $there = $true }
            if ($lz[$i].Contains($tag) -and -not $lz[$i].TrimStart().StartsWith(';')) { $at = $i }
        }
        if (-not $there -and ($at -ge 0 -or $map.ownZones)) {
            $lines = [string[]]@($map.landingZones)
            # the project's own zones on a map with none of its own go at the end
            if ($at -lt 0) { $at = $lz.Count - 1; while ($at -ge 0 -and $lz[$at] -eq '') { $at-- } }
            $lz.InsertRange($at + 1, $lines)
            $zones += @{ variant = $map.variant; lines = $lines }
        }
    }
    $done += $map
}
if (-not $done.Count) {
    foreach ($note in $skipped) { Write-Host "  Left out: $note" -ForegroundColor Yellow }
    Fail 'None of the pack''s maps can go into this game. Nothing was changed.'
}
# the files as they are now, then the changes
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -LiteralPath $mapsPath -Destination (Join-Path $backup 'DefaultMaps.ini') -Force
if ($hasLz) { Copy-Item -LiteralPath $lzPath -Destination (Join-Path $backup 'DefaultLZMutator.ini') -Force }
$copied = @()
$wanted = @($done | ForEach-Object { @($_.files) })
foreach ($name in $names) {
    if ($wanted -notcontains $name) { continue }
    $to = Join-Path $cooked $name
    if (Test-Path -LiteralPath $to) { continue }        # there already, the same file: it is not this pack's to delete
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $to
    $copied += @{ name = $name; sha256 = $pack.files.$name }
}
$state = @{ pack = $pack.id; name = $pack.name; mode = $pack.mode; installedAt = (Get-Date).ToString('s'); added = $added;
            commented = $commented; zones = $zones; files = $copied }
New-Item -ItemType Directory -Force -Path $stateFolder | Out-Null
ConvertTo-Json $state -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $statePath
Write-Lines $mapsPath $maps
if ($zones.Count) { Write-Lines $lzPath $lz }

Write-Host "Installed $($done.Count) map(s) in $Game." -ForegroundColor Green
foreach ($map in $done) {
    $how = 'beside it in the rotation'
    if ($map.mode -eq 'replace' -or (-not $map.mode -and $pack.mode -eq 'replace')) { $how = 'in its place' }
    Write-Host "  $($map.variant): $($map.name), a variant of $($map.base), $how"
}
if ($commented.Count) { Write-Host "$($commented.Count) record(s) of the game's own were commented out for the maps that replace theirs." }
foreach ($note in $skipped) { Write-Host "  Left out: $note" -ForegroundColor Yellow }
Write-Host "DefaultMaps.ini as it was is kept in $backup"
Write-Host 'Start a new mission to see them: a tactical save from before does not use the new maps. Uninstall.cmd takes them out again.'
exit 0
'''.replace('\n', '\r\n')
