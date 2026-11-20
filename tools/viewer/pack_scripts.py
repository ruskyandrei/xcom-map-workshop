"""The scripts a map pack's zip carries (manager.pack), so that whoever gets the pack installs it with a double-click
and takes it out again the same way, without the editor: Install.cmd and Uninstall.cmd, which run pack-tools\\pack.ps1
with Windows' own PowerShell (5.1 or later).

Install asks for the game folder (or takes it as its argument; it offers the Steam installs it finds) and refuses
while XCOM runs. Then one of two ways (a third argument, cards or classic, forces one):

- The game's script reads map pack cards (its XComMutator.u holds the name LWRMapPackCard: Long War Rebalance 3.00.00
  beta 15 or later): the pack's folder is copied into CookedPCConsole (any lighting cache a map could not take in
  beside the folder: the game finds a .tfc only there, F-140), and the
  drop-in exclusion lines added where a map asks for them (a card can't carry them). No other file of the game is
  touched. It names another pack's card of the same number and a file of the same name elsewhere under
  CookedPCConsole. Uninstall deletes the files it copied (the folder too, once empty) and those lines.
- Any other install, the classic way: it keeps copies of DefaultMaps.ini and DefaultLZMutator.ini as they are, copies the pack's files, adds each
map's records after its base map's (and, for a map made to replace its original, comments out the base map's own
records it has records for, by their DisplayName in pack.json's switch, leaving the others in use (F-118): each map
says which way in pack.json, so one pack can hold both kinds), adds its landing zones where the install has Long War's file,
adds its drop-in exclusion lines (a project that leaves scripted drop-ins where placed) where the install has Long War's
DefaultRandomSpawns.ini and its drop-in section, and writes down what it did in
<game>\\XCOM Map Workshop\\packs\\<pack id>.json (the pack id is the pack's folder name, the same at every version,
so a newer version installed over an older one takes the older out first, whichever way that one went in). Uninstall
undoes exactly that: the lines it added go, the lines it
commented out come back, the files it copied are deleted if unchanged; it says whether DefaultMaps.ini is then byte
for byte as it was before the pack (it is, unless something else changed the file meanwhile, whose changes stay).
What it can't take out (lines changed since, a file changed since) stays noted in the state file for the next
Uninstall, and a map whose records stay in the game keeps its files, as a card changed since keeps the pack's maps
(review finding 26): a record naming a map that is not there could be drawn by the game. An install over an earlier
one with such leftovers stops until they are put right.

The lines come from pack.json, worked out from the install the pack was made from (installs.rotation_plan): a map whose
base map has no record in the target install is left out, and so is one that already has a record of its name there.
The files are read and written as bytes (Latin-1, CRLF), as the editor's own install step does.
"""

CMD = r'''@echo off
rem {what} this map pack. Double-click it, or give the game folder: {name}.cmd "D:\Steam\steamapps\common\XCom-Enemy-Unknown"
rem Windows PowerShell builds its own module path: one inherited from PowerShell 7 hides its Get-FileHash.
setlocal
set "PSModulePath="
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack-tools\pack.ps1" {action} %*
set code=%errorlevel%
if "%~1"=="" pause
exit /b %code%
'''

INSTALL_CMD = CMD.format(what='Installs', name='Install', action='install').replace('\n', '\r\n')
UNINSTALL_CMD = CMD.format(what='Takes out', name='Uninstall', action='uninstall').replace('\n', '\r\n')

PS1 = r'''# Installs a map pack made with the XCOM Map Workshop into a game folder, or takes it out again.
#   pack.ps1 install [<game folder> [cards|classic]]      pack.ps1 uninstall [<game folder>]
# Run by Install.cmd and Uninstall.cmd beside the pack's README. What it does is in the README.
# An install whose script reads map pack cards (Long War Rebalance 3.00.00 beta 15 or later) gets the pack's folder
# copied into CookedPCConsole and its lighting caches beside it; any other gets the maps' files and their lines in
# DefaultMaps.ini. The third argument forces one way.
param([Parameter(Position = 0)][string]$Action = 'install', [Parameter(Position = 1)][string]$Game = '',
      [Parameter(Position = 2)][string]$Route = '')
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
# A config is written whole beside itself, read back, then put in its place (File.Replace keeps its attributes), so a
# write cut short (a full disk, the machine turned off) leaves the file as it was, never half of the new one; a file
# something holds open is tried again a few times.
function Write-Lines([string]$path, $lines) {
    $bytes = $latin.GetBytes([string]::Join("`r`n", [string[]]$lines))
    $temp = "$path.pack-new"
    try {
        [IO.File]::WriteAllBytes($temp, $bytes)
        if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($temp)) -ne [Convert]::ToBase64String($bytes)) { throw 'it did not read back as written' }
    } catch {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
        Fail "$path could not be written ($_); it is left as it was."
    }
    for ($try = 1; ; $try++) {
        try {
            if (Test-Path -LiteralPath $path) { [IO.File]::Replace($temp, $path, [NullString]::Value) } else { [IO.File]::Move($temp, $path) }
            return
        } catch {
            if ($try -ge 5) {
                Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
                $why = if ($_.Exception.InnerException) { $_.Exception.InnerException.Message } else { $_.Exception.Message }
                Fail "$path could not be replaced ($why); it is left as it was."
            }
            Start-Sleep -Milliseconds 400
        }
    }
}
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
$rsPath = Join-Path $Game 'XEW\XComGame\Config\DefaultRandomSpawns.ini'
$dropInSection = '[XComLZMutator.XComSpawnAlienMutator]'
$cooked = Join-Path $Game 'XEW\XComGame\CookedPCConsole'
$stateFolder = Join-Path $Game 'XCOM Map Workshop\packs'
$statePath = Join-Path $stateFolder "$($pack.id).json"
$backup = Join-Path $stateFolder "$($pack.id)-before"
$packFolder = $pack.folder
$sourceRoot = Join-Path $root 'CookedPCConsole'
$sourceFolder = Join-Path $sourceRoot $packFolder
$caches = [string[]]@($pack.cacheFiles)

# Where a file of the pack lies in the unzipped pack: in the pack's folder, or (a lighting cache) beside it.
function Source-Of([string]$name) {
    $inFolder = Join-Path $sourceFolder $name
    if (Test-Path -LiteralPath $inFolder) { return $inFolder }
    return Join-Path $sourceRoot $name
}
# Whether the game's script reads map pack cards: its XComMutator.u has the card's class.
function Test-Cards {
    $script = Join-Path $cooked 'XComMutator.u'
    if (-not (Test-Path -LiteralPath $script)) { return $false }
    return $latin.GetString([IO.File]::ReadAllBytes($script)).Contains('LWRMapPackCard')
}
# A map's drop-in exclusion lines put into the lines of DefaultRandomSpawns.ini: after the last ExcludeMaps line of
# the drop-in section (live or commented), else at the section's end. Returns the lines added, or $null where a live
# line for the map is there already or the file has no such section.
function Add-Exclusion($rs, $map) {
    $start = -1; $end = $rs.Count; $last = -1; $there = $false
    for ($i = 0; $i -lt $rs.Count; $i++) {
        $t = $rs[$i].Trim()
        if ($t.StartsWith('[')) { if ($start -ge 0 -and $end -eq $rs.Count -and $i -gt $start) { $end = $i }; if ($t -eq $dropInSection -and $start -lt 0) { $start = $i }; continue }
        if ($start -lt 0 -or $i -ge $end) { continue }
        if ($t -match '^;*\s*[+.!]?ExcludeMaps\s*=') { $last = $i }
        if ($t -match ('^[+.!]?ExcludeMaps\s*=\s*"?' + [regex]::Escape($map.variant) + '"?\s*$')) { $there = $true }
    }
    if ($start -lt 0 -or $there) { return $null }
    $at = $last + 1
    if ($last -lt 0) { $at = $end; while ($at - 1 -gt $start -and $rs[$at - 1].Trim() -eq '') { $at-- } }
    $lines = [string[]]@($map.dropInExclusion)
    $rs.InsertRange($at, $lines)
    return ,$lines
}
function Remove-Exclusions($state, [ref]$left, [ref]$kept) {
    if (-not (@($state.exclusions).Count -and (Test-Path -LiteralPath $rsPath))) { return }
    $rs = Read-Lines $rsPath
    foreach ($block in @($state.exclusions)) {
        $run = [string[]]@($block.lines)
        $at = Find-Run $rs $run
        if ($at -lt 0) { $left.Value += "the drop-in exclusion of $($block.variant) has changed: take it out by hand"; $kept.Value += $block; continue }
        $rs.RemoveRange($at, $run.Count)
    }
    Write-Lines $rsPath $rs
}
# What could not be taken out stays noted in the pack's state file, for Uninstall.cmd to take out once it is put right.
function Save-Left($state, $keep) {
    foreach ($key in @($keep.Keys)) { $state | Add-Member -NotePropertyName $key -NotePropertyValue @($keep[$key]) -Force }
    ConvertTo-Json $state -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $statePath
    Write-Host "What is left stays noted in $statePath`: run Uninstall.cmd again once it is put right." -ForegroundColor Yellow
}

function Uninstall-Pack {
    if (-not (Test-Path -LiteralPath $statePath)) { return $false }
    $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
    $left = @()
    if ($state.route -eq 'cards') {
        # the folder's files and the caches beside it, each deleted if unchanged; the folder goes once empty. While the
        # card stays (changed since), it names the maps, and they stay too.
        $keep = @{ files = @(); exclusions = @() }
        $cardStays = $false
        foreach ($file in @($state.files | Where-Object { $_.name -match 'LWRMapPack_\d{4}\.upk$' })) {
            $path = Join-Path $cooked $file.name
            if ((Test-Path -LiteralPath $path) -and (Sha $path) -ne $file.sha256) { $cardStays = $true }
        }
        $gone = 0
        foreach ($file in @($state.files)) {
            $path = Join-Path $cooked $file.name
            if (-not (Test-Path -LiteralPath $path)) { continue }
            if ((Sha $path) -ne $file.sha256) { $left += "$($file.name) has changed since: it stays"; $keep.files += $file; continue }
            if ($cardStays) { $left += "$($file.name) stays: the pack's card, changed since, still names it"; $keep.files += $file; continue }
            Remove-Item -LiteralPath $path
            $gone++
        }
        $there = Join-Path $cooked $state.folder
        if ((Test-Path -LiteralPath $there) -and -not @(Get-ChildItem -LiteralPath $there -Force).Count) { Remove-Item -LiteralPath $there }
        $kept = @()
        Remove-Exclusions $state ([ref]$left) ([ref]$kept)
        $keep.exclusions = $kept
        Write-Host "Taken out: the pack's folder $($state.folder), $gone file(s)."
        foreach ($note in $left) { Write-Host "  Left: $note" -ForegroundColor Yellow }
        if (@($keep.files).Count -or @($keep.exclusions).Count) { Save-Left $state $keep; return $true }
        Remove-Item -LiteralPath $statePath
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse }
        return $true
    }
    $maps = Read-Lines $mapsPath
    $keep = @{ added = @(); commented = @(); zones = @(); exclusions = @(); files = @() }
    $taken = 0; $back = 0; $held = @()
    foreach ($block in @($state.added)) {
        $run = [string[]]@($block.lines)
        $at = Find-Run $maps $run
        if ($at -ge 0) { $maps.RemoveRange($at, $run.Count); $taken++; continue }
        # not there as written: still in the game while a record of its name is, and then its files stay too (a record
        # naming a map that is not there could be drawn); with none, taken out by hand already
        $named = '^\s*Maps=\(.*(?<![A-Za-z])Name="' + [regex]::Escape($block.variant) + '"'
        if (-not @($maps | Where-Object { $_ -match $named }).Count) { continue }
        $left += "the records of $($block.variant) have changed: take them out by hand"
        $keep.added += $block
        if ($block.PSObject.Properties.Name -contains 'files') { $held += @($block.files) }
        else { $held += @($state.files | ForEach-Object { $_.name }) }    # a state from before: which are its, nothing says
    }
    foreach ($line in @($state.commented)) {
        $at = $maps.IndexOf(';' + $line)
        if ($at -lt 0) { $left += 'a record this pack commented out has changed since: check it by hand'; $keep.commented += $line; continue }
        $maps[$at] = $line
        $back++
    }
    Write-Lines $mapsPath $maps
    if (@($state.zones).Count -and (Test-Path -LiteralPath $lzPath)) {
        $lz = Read-Lines $lzPath
        foreach ($block in @($state.zones)) {
            $run = [string[]]@($block.lines)
            $at = Find-Run $lz $run
            if ($at -lt 0) { $left += "the landing zones of $($block.variant) have changed: take them out by hand"; $keep.zones += $block; continue }
            $lz.RemoveRange($at, $run.Count)
        }
        Write-Lines $lzPath $lz
    }
    $kept = @()
    Remove-Exclusions $state ([ref]$left) ([ref]$kept)
    $keep.exclusions = $kept
    $gone = 0
    foreach ($file in @($state.files)) {
        $path = Join-Path $cooked $file.name
        if (-not (Test-Path -LiteralPath $path)) { continue }
        if ($held -contains $file.name) { $left += "$($file.name) stays: records that play it are still in DefaultMaps.ini"; $keep.files += $file; continue }
        if ((Sha $path) -ne $file.sha256) { $left += "$($file.name) has changed since: it stays"; $keep.files += $file; continue }
        Remove-Item -LiteralPath $path
        $gone++
    }
    Write-Host "Taken out: the records of $taken map(s), $back record(s) of the game's own back in use, $gone file(s)."
    foreach ($note in $left) { Write-Host "  Left: $note" -ForegroundColor Yellow }
    if (@($keep.Values | ForEach-Object { @($_) }).Count) { Save-Left $state $keep }
    else { Remove-Item -LiteralPath $statePath }
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
    if (Test-Path -LiteralPath $statePath) { Fail 'Part of the earlier install could not be taken out (above), and it stays noted: put it right and run Install.cmd again.' }
}
$useCards = Test-Cards
if ($Route -eq 'classic') { $useCards = $false } elseif ($Route -eq 'cards') { $useCards = $true } elseif ($Route) { Fail "Unknown way '$Route': cards or classic." }
$names = @($pack.files.PSObject.Properties | ForEach-Object { $_.Name })
foreach ($name in $names) {
    $from = Source-Of $name
    if (-not (Test-Path -LiteralPath $from)) { Fail "$name is missing from the pack: unzip the whole pack first." }
    if ((Sha $from) -ne $pack.files.$name) { Fail "$name in the pack is damaged (its checksum differs)." }
    # in CookedPCConsole itself go every file the classic way, and the lighting caches either way
    if ($useCards -and $caches -notcontains $name) { continue }
    $to = Join-Path $cooked $name
    if ((Test-Path -LiteralPath $to) -and (Sha $to) -ne $pack.files.$name) {
        Fail "The game already has another $name. Nothing was changed; take that file's owner out first."
    }
}
if ($useCards) {
    # ---- an install that reads map pack cards: the folder copied, the caches beside it, nothing else
    $cardPath = Join-Path $sourceFolder $pack.card.file
    if (-not (Test-Path -LiteralPath $cardPath)) { Fail "$($pack.card.file) is missing from the pack: unzip the whole pack first." }
    $target = Join-Path $cooked $packFolder
    $notes = @()
    # another pack's card of the same number, or a file of the same name elsewhere: the game finds one of the two
    $mine = @(Get-ChildItem -LiteralPath $sourceFolder -File | ForEach-Object { $_.Name })
    $lower = @($mine | ForEach-Object { $_.ToLower() })
    foreach ($other in @(Get-ChildItem -LiteralPath $cooked -Recurse -File | Where-Object { $_.Extension -eq '.upk' -and $lower -contains $_.Name.ToLower() -and $_.DirectoryName -ne $target })) {
        $where = $other.DirectoryName.Substring($cooked.Length).TrimStart('\')
        if (-not $where) { $where = 'CookedPCConsole itself' }
        if ($other.Name -ieq $pack.card.file) { $notes += "another pack's card has the same number ($($other.Name), in $where): rename one of the two, keeping LWRMapPack_ and four digits, or one pack is not read" }
        else { $notes += "$($other.Name) is also in $where`: the game uses only one of the two files" }
    }
    $rs = $null
    if (Test-Path -LiteralPath $rsPath) { $rs = Read-Lines $rsPath }
    $exclusions = @()
    if ($null -ne $rs) {
        foreach ($map in @($pack.maps)) {
            if (-not $map.dropInExclusion) { continue }
            $lines = Add-Exclusion $rs $map
            if ($null -ne $lines) { $exclusions += @{ variant = $map.variant; lines = $lines } }
        }
    }
    New-Item -ItemType Directory -Force -Path $stateFolder | Out-Null
    if ($exclusions.Count) {
        New-Item -ItemType Directory -Force -Path $backup | Out-Null
        Copy-Item -LiteralPath $rsPath -Destination (Join-Path $backup 'DefaultRandomSpawns.ini') -Force
    }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $copied = @()
    foreach ($name in $mine) {
        $to = Join-Path $target $name
        Copy-Item -LiteralPath (Join-Path $sourceFolder $name) -Destination $to -Force
        $copied += @{ name = "$packFolder\$name"; sha256 = (Sha $to) }
    }
    foreach ($name in $caches) {
        $to = Join-Path $cooked $name
        if (Test-Path -LiteralPath $to) { continue }        # there already, the same file: it is not this pack's to delete
        Copy-Item -LiteralPath (Source-Of $name) -Destination $to
        $copied += @{ name = $name; sha256 = $pack.files.$name }
    }
    $state = @{ pack = $pack.id; name = $pack.name; mode = $pack.mode; route = 'cards'; folder = $packFolder;
                installedAt = (Get-Date).ToString('s'); exclusions = $exclusions; files = $copied }
    ConvertTo-Json $state -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $statePath
    if ($exclusions.Count) { Write-Lines $rsPath $rs }
    Write-Host "Installed $(@($pack.maps).Count) map(s) in $Game as the map pack folder $packFolder (card $($pack.card.file))." -ForegroundColor Green
    foreach ($map in @($pack.maps)) {
        $how = 'beside it in the rotation'
        if ($map.mode -eq 'replace' -or (-not $map.mode -and $pack.mode -eq 'replace')) { $how = 'in its place' }
        Write-Host "  $($map.variant): $($map.name), a variant of $($map.base), $how"
    }
    if ($caches.Count) { Write-Host "$($caches.Count) lighting cache file(s) lie beside the folder, in CookedPCConsole itself." }
    if ($exclusions.Count) { Write-Host "$($exclusions.Count) drop-in exclusion(s) were added to DefaultRandomSpawns.ini (a card can't carry them)." }
    foreach ($note in $notes) { Write-Host "  Note: $note" -ForegroundColor Yellow }
    $changed = 'No file of the game was changed.'
    if ($exclusions.Count) { $changed = 'No other file of the game was changed.' }
    Write-Host "$changed In the game's console, Mutate LWRMapTest Packs lists the pack. Uninstall.cmd takes it out again."
    exit 0
}
$maps = Read-Lines $mapsPath
$lz = $null
if (Test-Path -LiteralPath $lzPath) { $lz = Read-Lines $lzPath }
$hasLz = $null -ne $lz
$rs = $null
if (Test-Path -LiteralPath $rsPath) { $rs = Read-Lines $rsPath }
$hasRs = $null -ne $rs
$added = @(); $commented = @(); $zones = @(); $exclusions = @(); $skipped = @(); $done = @()
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
    # with its files, which stay while its records do (Uninstall-Pack)
    $added += @{ variant = $map.variant; lines = $records; files = [string[]]@($map.files) }
    # each map says whether it replaces its base map (a pack from before that says it once, for all)
    $way = $map.mode
    if (-not $way) { $way = $pack.mode }
    if ($way -eq 'replace') {
        # the base map's records the map has records for, by their DisplayName (switch); the others stay in use. A
        # pack from before switch comments out every one.
        $only = $null
        if ($map.PSObject.Properties.Name -contains 'switch') { $only = [string[]]@($map.switch) }
        for ($i = 0; $i -lt $maps.Count; $i++) {
            if ($maps[$i] -notmatch $live) { continue }
            if ($null -ne $only) {
                $display = ''
                if ($maps[$i] -match 'DisplayName="([^"]*)"') { $display = $Matches[1] }
                if ($only -cnotcontains $display) { continue }
            }
            $commented += $maps[$i]; $maps[$i] = ';' + $maps[$i]
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
    if ($hasRs -and $map.dropInExclusion) {
        $lines = Add-Exclusion $rs $map
        if ($null -ne $lines) { $exclusions += @{ variant = $map.variant; lines = $lines } }
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
if ($hasRs) { Copy-Item -LiteralPath $rsPath -Destination (Join-Path $backup 'DefaultRandomSpawns.ini') -Force }
$copied = @()
$wanted = @($done | ForEach-Object { @($_.files) })
foreach ($name in $names) {
    if ($wanted -notcontains $name) { continue }
    $to = Join-Path $cooked $name
    if (Test-Path -LiteralPath $to) { continue }        # there already, the same file: it is not this pack's to delete
    Copy-Item -LiteralPath (Source-Of $name) -Destination $to
    $copied += @{ name = $name; sha256 = $pack.files.$name }
}
$state = @{ pack = $pack.id; name = $pack.name; mode = $pack.mode; route = 'classic'; installedAt = (Get-Date).ToString('s'); added = $added;
            commented = $commented; zones = $zones; exclusions = $exclusions; files = $copied }
New-Item -ItemType Directory -Force -Path $stateFolder | Out-Null
ConvertTo-Json $state -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $statePath
Write-Lines $mapsPath $maps
if ($zones.Count) { Write-Lines $lzPath $lz }
if ($exclusions.Count) { Write-Lines $rsPath $rs }

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
