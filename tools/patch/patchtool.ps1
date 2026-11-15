<#
Builds a streaming patch map for XCOM: EW (LWR) from a small JSON spec of objects, unattended, and deploys it into
the lab copy. Steps:

  t3d     Write the T3D for the spec's objects (no editor). Each object i gets names with the suffix nameBase + i
          (XComLevelActor_900, StaticMeshComponent_900, ..., Model_900); the suffix is raised in steps of 100 until
          no name clashes with any object name in the base patch package.
  build   t3d, compile the scripts (UDK.com make) if any .uc source is newer than its package, then copy the base
          patch .udk to <name>.udk, open it in the authoring editor, MAP IMPORTADD the T3D
          through the command box (exactly once; see Send-EditorCommands), check with ACTOR SELECT ALL + EDIT COPY
          that every new actor is there under its own name, mesh and location (and nothing else new), save with
          File > Save As, check the saved package, close the editor.
  cook    PC cook of <name> (UDK.com CookPackages). Passes when the cooked file is fresh and the only cook error is
          the known HQSound_MCMusic one; puts CookedPC\HQSound_MCMusic_SF.upk back if the cook deleted it.
  deploy  Copy the cooked map into the lab copy as XEW\XComGame\CookedPCConsole\<name>.upk. With -Stream
          <DisplayName>, also point StreamingMaps[-Slot] of that DefaultMaps.ini map line at <name>.
  stream  Only the DefaultMaps.ini edit (-Map names the patch when no spec is given).
  all     t3d, build, cook, deploy.
  unseed  Put the original base map back in the lab copy, if it is seeded for this patch (-Map or spec).

Tile seeds (EXP-07, findings register F-29): when the spec names its base map (map.name, e.g. URB_Bar), t3d plans
the tiles the patch's copies, spawns and actors cross above the ground (tools\upk\seed_map.py) and adds an
XComMapEdTileSeeds actor, last, that rebuilds them at load. deploy then puts a copy of the original map with those
tiles seeded into the lab (the game's rebuild ignores tiles the map's baked data left empty). The original comes from
the LWR install (read only) and is kept in <Work>\maps; the lab's map is replaced only when it is the original or the
copy this tool last seeded (ledger <Work>\seeded.txt). One patch's seeds per map at a time.

  pwsh -File tools\patch\patchtool.ps1 t3d tools\patch\examples\exp04.json
  pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp04b.json
  pwsh -File tools\patch\patchtool.ps1 deploy -Map patch_exp04b -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0'
  pwsh -File tools\patch\patchtool.ps1 stream -Map patch_exp04 -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0'

Safety: refuses to start when a UDK process is already running, and only kills the editor it started. Refuses to
overwrite an existing <name>.udk (build) or a game .upk this tool did not deploy (deploy) unless -Force; either way
the old file is backed up first. Touches the game folder only when switch_install.ps1 says active=lab and XCOM is
not running. DefaultMaps.ini is backed up before every edit and rewritten byte for byte except the one entry.
The user's clipboard (text, image or file list) is saved before EDIT COPY and put back afterwards.

The build step (also within all) runs on a private desktop that is never shown (tools\lab\HiddenRun.cs), so the
editor and its Save As dialogs never take the user's focus; the editor runs with DirectX 11 there. -Visible keeps
them on the user's desktop instead (DirectX 9, as before). The cook can't run there and stays on the user's desktop,
where it opens no window: it shares the console of whatever runs patchtool.

Work files, backups and logs: <Work>\<name>\ (and \backups); -Work defaults to <lab>\patchtool, and the editor's Build
passes its own (<builds>\.work\patchtool). -Lwr names the LWR install the original maps are read from (read only);
without it, switch_install.ps1 says where it is. -Udk defaults to the udk setting, <lab> is the lab setting, and -Game
(the lab copy, for deploy, stream and unseed) defaults to XCom-Enemy-Unknown, the folder Steam runs, in the Steam
library the lwr setting names (tools\lab\LabSettings.ps1). Exit code 0 on success, 1 on failure.
Spec format: tools\patch\README.md.
#>
param(
    [Parameter(Mandatory, Position = 0)][ValidateSet('t3d', 'build', 'cook', 'deploy', 'stream', 'all', 'unseed')][string]$Step,
    [Parameter(Position = 1)][string]$Spec = '',
    [string]$Map = '',
    [string]$Stream = '',
    [int]$Slot = 1,
    [switch]$Force,
    [switch]$Visible,
    [int]$OpenTimeout = 90, [int]$SaveTimeout = 180, [int]$CookTimeout = 900, [int]$CopyTimeout = 60,
    [string]$Udk = '',
    [string]$Game = '',
    [string]$Work = '',
    [string]$Lwr = ''
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
$latin1 = [Text.Encoding]::Latin1
$lab = (Resolve-Path (Join-Path $PSScriptRoot '..\lab')).Path
# Folders not given come from the settings. The game folder is only needed by the steps that touch the lab copy
# (Assert-LabGame), so a build or cook runs without it.
. (Join-Path $lab 'LabSettings.ps1')
$labRoot = Get-LabSetting 'lab'
if (-not $Udk) { $Udk = Get-LabUdk }
if (-not $Work) { $Work = Join-Path (Get-LabRoot) 'patchtool' }
if (-not $Game) { $Game = try { Get-ActiveGame } catch { '' } }
$patchDir = Join-Path $Udk 'UDKGame\Content\Maps\patches'
$cookedDir = Join-Path $Udk 'UDKGame\CookedPC\Maps\patches'
$launchLog = Join-Path $Udk 'UDKGame\Logs\Launch.log'
$hqSound = Join-Path $Udk 'UDKGame\CookedPC\HQSound_MCMusic_SF.upk'
# The cook deletes HQSound_MCMusic_SF.upk now and then; patchtool keeps a copy of it to put back (the upstream UDK's
# copy in <lab>\upstream is the fallback, on the lab machine).
$hqSoundKept = Join-Path $Work 'keep\HQSound_MCMusic_SF.upk'
$hqSoundSource = if ($labRoot) { Join-Path $labRoot 'upstream\iiiLiQuiDiii-UDK\UDK-2011-09\UDKGame\CookedPC\HQSound_MCMusic_SF.upk' } else { '' }
$gameCooked = if ($Game) { Join-Path $Game 'XEW\XComGame\CookedPCConsole' } else { '' }
$gameIni = if ($Game) { Join-Path $Game 'XEW\XComGame\Config\DefaultMaps.ini' } else { '' }
$backups = Join-Path $Work 'backups'
$ledger = Join-Path $Work 'deployed.txt'
$seedLedger = Join-Path $Work 'seeded.txt'      # time, map, patch, planned tiles, SHA-256 of the lab's map after
$mapsDir = Join-Path $Work 'maps'               # originals of seeded base maps, and their inventories
$seedTool = (Resolve-Path (Join-Path $PSScriptRoot '..\upk\seed_map.py')).Path
$linksTool = (Resolve-Path (Join-Path $PSScriptRoot '..\upk\world_links.py')).Path
$bakeTool = (Resolve-Path (Join-Path $PSScriptRoot '..\upk\bake_actor.py')).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$collisionTypes = @('COLLIDE_BlockAllButWeapons', 'COLLIDE_BlockAll')   # the ones whose component flags are known
$script:runLog = $null
$script:editorPids = @()
$script:clip = $null
$script:summary = [Collections.Generic.List[string]]::new()

# Window lookups and window messages only reach windows on the caller's own desktop, so the build step moves onto the
# private desktop as a whole (HiddenRun starts this script again there, as the build step with the same parameters)
# rather than just the editor. The cooker exits at once there (exit 3, no log), so all goes on with the cook and the
# deploy here, where they open no window either. HiddenRun.exe is compiled from tools\lab\HiddenRun.cs when it is
# missing or older than its source.
Add-Type -Name ThreadDesktop -Namespace PatchTool -MemberDefinition @'
[DllImport("user32.dll")] static extern IntPtr GetThreadDesktop(uint thread);
[DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
[DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool GetUserObjectInformation(IntPtr h, int index, System.Text.StringBuilder info, int length, out int needed);
public static string Name() { var b = new System.Text.StringBuilder(256); int n; GetUserObjectInformation(GetThreadDesktop(GetCurrentThreadId()), 2, b, 512, out n); return b.ToString(); }
'@
$desktop = [PatchTool.ThreadDesktop]::Name()
$builtHidden = $false

# The editor stops at a "scripts are out of date" prompt when a .uc file is newer than its compiled package, or when
# the package is missing (a failed make deletes the packages it was rebuilding); on the hidden desktop nobody sees it,
# and the build fails as "the editor did not open". So the build first compiles the scripts (UDK.com make) when any
# package the editor compiles (EditPackages in UDKEngine.ini, those with sources) is missing or older than one of its
# sources. Like the cook, make runs here, on the user's desktop, without a window.
if ($Step -in 'build', 'all' -and $desktop -eq 'Default') {
    $packages = Select-String -LiteralPath (Join-Path $Udk 'UDKGame\Config\UDKEngine.ini') -Pattern '^EditPackages=(\w+)\s*$' |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -Unique
    $stale = @($packages | Where-Object {
        $classes = Join-Path $Udk "Development\Src\$_\Classes"
        if (-not (Test-Path -LiteralPath $classes)) { return $false }
        $u = Get-Item -LiteralPath (Join-Path $Udk "UDKGame\Script\$_.u") -ErrorAction SilentlyContinue
        $newest = Get-ChildItem -LiteralPath $classes -Filter *.uc | Sort-Object LastWriteTime | Select-Object -Last 1
        -not $u -or ($newest -and $newest.LastWriteTime -gt $u.LastWriteTime)
    })
    if ($stale) {
        if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { Write-Host 'FAIL: a UDK process is running; close it before building'; exit 1 }
        $makeLog = Join-Path $Work "make-$(Get-Date -Format yyyyMMdd-HHmmss).log"
        New-Item -ItemType Directory -Force -Path $Work | Out-Null
        Write-Host "[$(Get-Date -Format HH:mm:ss)] compiling the scripts ($($stale -join ', ') missing or older than their sources)"
        $p = Start-Process -FilePath (Join-Path $Udk 'Binaries\Win32\UDK.com') -WorkingDirectory (Join-Path $Udk 'Binaries\Win32') `
            -ArgumentList @('make', '-unattended', '-nopause') -RedirectStandardOutput $makeLog -RedirectStandardError "$makeLog.err" -NoNewWindow -PassThru
        if (-not $p.WaitForExit(600000)) { Stop-Process -Id $p.Id -Force; Write-Host "FAIL: make did not finish in 600 s (log $makeLog)"; exit 1 }
        $lines = @(Get-Content -LiteralPath $makeLog)
        $result = $lines | Where-Object { $_ -match '^(Success|Failure) - ' } | Select-Object -Last 1
        if ($result -notmatch '^Success - 0 error') {
            $lines | Where-Object { $_ -match ': Error,|^Error' } | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
            Write-Host "FAIL: the scripts did not compile: $(if ($result) { $result } else { "no result, exit $($p.ExitCode)" }) (log $makeLog)"
            exit 1
        }
        Write-Host "[$(Get-Date -Format HH:mm:ss)]   make: $result"
    }
}
if ($Step -in 'build', 'all' -and -not $Visible -and $desktop -eq 'Default') {
    # compiled beside the work folder: <lab>\bin for the lab's own, <builds>\.work\bin for the editor's builds
    $hiddenRun = Join-Path (Split-Path $Work) 'bin\HiddenRun.exe'
    $hiddenSrc = Join-Path $lab 'HiddenRun.cs'
    New-Item -ItemType Directory -Force -Path (Split-Path $hiddenRun) | Out-Null
    if (-not (Test-Path -LiteralPath $hiddenRun) -or (Get-Item -LiteralPath $hiddenRun).LastWriteTime -lt (Get-Item -LiteralPath $hiddenSrc).LastWriteTime) {
        & (Get-Csc) /nologo /target:exe /platform:anycpu "/out:$hiddenRun" $hiddenSrc
        if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: could not compile $hiddenSrc"; exit 1 }
    }
    $forward = foreach ($k in $PSBoundParameters.Keys) {
        if ($k -in 'Step', 'Stream', 'Slot') { continue }
        $v = $PSBoundParameters[$k]
        if ($v -is [switch]) { if ($v) { "-$k" } } else { "-$k"; "$v" }
    }
    $limit = 3 * ($OpenTimeout + 10) + $SaveTimeout + $CopyTimeout + 600
    Write-Host "[$(Get-Date -Format HH:mm:ss)] building on the hidden desktop XComLab-UDK (-Visible shows the editor instead)"
    & $hiddenRun --desktop XComLab-UDK --timeout $limit -- (Get-Process -Id $PID).Path -NoProfile -File $PSCommandPath -Step build @forward
    $code = $LASTEXITCODE
    if ($code -eq 124) { Write-Host "FAIL: the hidden build did not finish in $limit s and was ended" }
    if ($code -ne 0 -or $Step -eq 'build') { exit $code }
    $builtHidden = $true
}

function Say([string]$Text) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Text
    Write-Host $line
    if ($script:runLog) { Add-Content -LiteralPath $script:runLog -Value $line }
}
function Done([string]$Text) { $script:summary.Add($Text); Say $Text }
function Opt($o, [string]$n, $d) { if ($null -ne $o -and $o.PSObject.Properties[$n] -and $null -ne $o.$n) { $o.$n } else { $d } }
function F6([double]$v) { if ($v -eq 0) { $v = 0.0 }; $v.ToString('0.000000', $inv) }
function Backup([string]$Path, [string]$Dir) {
    New-Item -ItemType Directory -Force $Dir | Out-Null
    $to = Join-Path $Dir ('{0}.{1}' -f (Split-Path $Path -Leaf), $stamp)
    for ($k = 2; Test-Path -LiteralPath $to; $k++) { $to = Join-Path $Dir ('{0}.{1}-{2}' -f (Split-Path $Path -Leaf), $stamp, $k) }
    Copy-Item -LiteralPath $Path $to
    $to
}

# ---------------------------------------------------------------- spec
function Get-Vec($v, [int]$n, [string]$what) {
    $a = @($v | ForEach-Object { [double]$_ })
    if ($a.Count -eq 1 -and $n -eq 3) { $a = @($a[0], $a[0], $a[0]) }
    if ($a.Count -ne $n) { throw "$what needs $n numbers" }
    , $a
}
function Get-Position($o, $s, [string]$what) {
    $z = Opt $o 'z' $null
    if ($o.PSObject.Properties['location']) {
        $l = @($o.location | ForEach-Object { [double]$_ })
        if ($l.Count -lt 2 -or $l.Count -gt 3) { throw "${what}: location needs [x, y] or [x, y, z]" }
        $x = $l[0]; $y = $l[1]; if ($l.Count -eq 3) { $z = $l[2] }
    } elseif ($o.PSObject.Properties['tile']) {
        $t = Get-Vec $o.tile 2 "${what}: tile"
        $off = switch ([string](Opt $o 'anchor' 'corner')) {
            'corner' { 0 } 'center' { $s.TileSize / 2 } default { throw "${what}: anchor must be corner or center" } }
        $x = $s.OriginX + $s.TileSize * $t[0] + $off
        $y = $s.OriginY + $s.TileSize * $t[1] + $off
    } else { throw "${what}: give location [x, y, z] or tile [tx, ty]" }
    if ($null -eq $z) { $z = $s.GroundZ }
    , @([double]$x, [double]$y, [double]$z)
}
# A stream slot as given: a whole number from 0 to 100 (StreamingMaps[100] is the highest index reported to work, in
# research/evidence/forum-and-wiki-notes-2026-11-03.md), or "free". Returns the number, or 'free'.
function Get-StreamSlotSpec($v, [string]$what = 'the stream slot') {
    $want = "$what must be a slot number from 0 to 100, or `"free`""
    if ($v -is [string]) {
        if ($v -ieq 'free') { return 'free' }
        throw "$want, not the text '$v'"
    }
    if (-not ($v -is [int] -or $v -is [long] -or $v -is [double] -or $v -is [decimal])) { throw "$want, not $(if ($null -eq $v) { 'nothing' } else { "'$v' ($($v.GetType().Name))" })" }
    $d = [double]$v
    if ($d -ne [math]::Floor($d) -or $d -lt 0 -or $d -gt 100) { throw "$want, not $v" }
    [int]$d
}
function Read-Spec([string]$Path) {
    $j = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $name = [string](Opt $j 'name' '')
    if ($name -notmatch '^[A-Za-z][A-Za-z0-9_]{2,62}$') { throw "spec name '$name' must be letters, digits and _ (e.g. patch_mything)" }
    # UDK's Save As stops at a warning dialog for package names over 30 characters ("Unreal filenames should be no
    # longer than 30 characters"), which the hidden build can only wait out (findings register T-09).
    if ($name.Length -gt 30) { throw "spec name '$name' is $($name.Length) characters; UDK can't save a package name over 30" }
    $base = [string](Opt $j 'base' 'patch_bar')
    $basePath = ''
    if ($base) {
        $basePath = if ($base -match '[\\/]') { $base } else { Join-Path $patchDir "$base.udk" }
        if (-not (Test-Path -LiteralPath $basePath)) { throw "base patch not found: $basePath" }
        if ((Split-Path $basePath -LeafBase) -ieq $name) { throw 'the patch name must differ from its base' }
    }
    $m = Opt $j 'map' $null
    $origin = Get-Vec (Opt $m 'origin' @(0, 0)) 2 'map.origin'
    $mapName = [string](Opt $m 'name' '')
    if ($mapName -and $mapName -notmatch '^[A-Za-z][A-Za-z0-9_]{1,62}$') { throw "map.name '$mapName' must be a map package name such as URB_Bar" }
    # map.shipAs: deploy puts the base map (seeded or not) into the lab under this name, with its own map record and
    # the base map's landing-zone lines, and leaves the base map's own file alone (F-42).
    $shipAs = [string](Opt $m 'shipAs' '')
    if ($shipAs) {
        if (-not $mapName) { throw 'map.shipAs needs map.name, the base map to ship a copy of' }
        if ($shipAs -notmatch '^[A-Za-z][A-Za-z0-9_]{1,62}$') { throw "map.shipAs '$shipAs' must be a map package name such as URB_BarBlank" }
        if ($shipAs -ieq $mapName) { throw 'map.shipAs must differ from map.name' }
        if ($shipAs.Length -gt 30) { throw "map.shipAs '$shipAs' is $($shipAs.Length) characters; keep map package names to 30, as UDK does (T-09)" }
    }
    # map.timeOfDay (Day, Night or None): the TimeOfDay of the shipped map's record, for a map whose lighting differs
    # from the base map's (EXP-08: URB_Bar is a night map, the blank map is lit as day), and of the -Stream slot. None
    # is Temple Ship's (EXP-14: the test slot plays a Temple variant as its own record has it).
    $tod = [string](Opt $m 'timeOfDay' '')
    if ($tod) {
        if (-not $shipAs) { throw 'map.timeOfDay needs map.shipAs: it sets the shipped map record' }
        $tod = @('Day', 'Night', 'None') | Where-Object { $_ -ieq $tod }
        if (-not $tod) { throw 'map.timeOfDay must be Day, Night or None' }
    }
    # map.streamSlot: the StreamingMaps slot of the shipped map's record that streams the patch. A number (default 1:
    # patch_bar's slot in URB_Bar's record, which the patch then replaces, as before), or "free": the lowest slot the
    # base map's record does not use, added, so that every stream of the base record stays (E0, EXP-10).
    $slotSpec = Opt $m 'streamSlot' $null
    if ($null -ne $slotSpec -and -not $shipAs) { throw 'map.streamSlot needs map.shipAs: it sets the shipped map record' }
    $streamSlot = Get-StreamSlotSpec $(if ($null -eq $slotSpec) { 1 } else { $slotSpec }) 'map.streamSlot'
    # map.seedExternally: the seeds are planned and rebuilt at load as usual, but deploy seeds no map in the lab: the
    # map is shipped by another tool, which applies the plan (the relit variant, tools/bake/deploy_fixture.py
    # --seed-plan, EXP-17). The editor's compiler writes it with --stream-only.
    $seedExt = [bool](Opt $m 'seedExternally' $false)
    if ($seedExt -and $shipAs) { throw 'map.seedExternally and map.shipAs exclude each other: a shipped map is seeded by deploy' }
    $s = [pscustomobject]@{
        Name = $name; Base = $base; BasePath = $basePath; Path = (Resolve-Path -LiteralPath $Path).Path
        MapName = $mapName; Seed = ((Opt $j 'seed' $true) -ne $false); SeedExternally = $seedExt
        ShipAs = $shipAs; ShipDisplay = [string](Opt $m 'displayName' "$shipAs (patchtool $name) |0"); InRotation = [bool](Opt $m 'inRotation' $false); TimeOfDay = [string]$tod
        StreamSlot = $streamSlot
        # The dropship intro picks its landing by the exact map name (F-45); with shipAs, an XComMapEdIntro gives the
        # shipped map its base map's landing. map.intro false leaves it out.
        Intro = ($shipAs -and (Opt $m 'intro' $true) -ne $false)
        OriginX = $origin[0]; OriginY = $origin[1]; TileSize = [double](Opt $m 'tileSize' 96)
        GroundZ = [double](Opt $m 'groundZ' 3.999993)      # what the editor wrote for the shipped floor-standing patches
        NameBase = [int](Opt $j 'nameBase' 900); Objects = @()
    }
    $objs = @(Opt $j 'objects' @())
    # A variant with no edits (the editor's no-op build): with map.shipAs, the intro is the patch's one actor.
    if (-not $objs.Count -and -not $s.Intro) { throw 'the spec has no objects (only a spec with map.shipAs and its intro may have none)' }
    $i = 0
    foreach ($o in $objs) {
        $what = "objects[$i]"
        $type = [string](Opt $o 'type' 'actor')
        if ($type -notin 'actor', 'volume', 'borrow', 'spawn', 'hide', 'copy', 'bake', 'ladder', 'photo', 'sun') { throw "${what}: type must be actor, volume, borrow, spawn, hide, copy, bake, ladder, photo or sun" }
        # A photo or sun object needs no place: its light shines over the whole map.
        $pos = if ($type -in 'photo', 'sun' -and -not ($o.PSObject.Properties['location'] -or $o.PSObject.Properties['tile'])) { [double[]]@(0, 0, 1000) } else { Get-Position $o $s $what }
        $obj = [ordered]@{ Index = $i; Type = $type; Pos = $pos; Volume = $null }
        if ($type -eq 'sun') {
            # XComMapEdSun (script package XComMapEd): a dynamic directional light from yaw, pitch degrees down, and a
            # sky light, over the whole map (EXP-08: the blank map's only light). The defaults are the photo object's.
            $obj.Sun = [double](Opt $o 'sun' 1.2); $obj.Sky = [double](Opt $o 'sky' 0.5)
            $obj.YawDeg = [double](Opt $o 'yaw' 138); $obj.PitchDeg = [double](Opt $o 'pitch' 50)
            if ($obj.Sun -lt 0 -or $obj.Sky -lt 0) { throw "${what}: sun and sky are brightnesses, 0 or more" }
            $obj.Mesh = $null
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a sun object takes no volume" }
        } elseif ($type -eq 'photo') {
            # XComMapEdPhoto (script package XComMapEd): the overview view for screenshots. Its class defaults are the
            # settings of EXP-07 run 35's overview shot; each field given here overrides one.
            $obj.Photo = [ordered]@{}
            foreach ($f in @(@('fov', 'FOV'), @('distance', 'Distance'), @('pitch', 'Pitch'), @('sun', 'Sun'), @('sky', 'Sky'), @('sunYaw', 'SunYaw'),
                             @('sunPitch', 'SunPitch'), @('highlights', 'Highlights'), @('midTones', 'MidTones'))) {
                $v = Opt $o $f[0] $null
                if ($null -ne $v) { $obj.Photo[$f[1]] = [double]$v }
            }
            $h = Opt $o 'hideUI' $null
            if ($null -ne $h) { $obj.Photo['bHideUI'] = [bool]$h }
            $obj.Mesh = $null
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a photo object takes no volume" }
        } elseif ($type -eq 'ladder') {
            # An XComLadder placed in the patch itself, as the shipped patch_bar places its hidden ladders: the tile
            # rebuild makes climb links for the patch's ladders (EXP-07 run 17, F-30).
            $mesh = [string](Opt $o 'mesh' 'LadderMetal.Meshes.LadderMetalA_448')
            if ($mesh -notmatch '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$') { throw "${what}: mesh must be Package.Name" }
            $obj.Mesh = $mesh; $obj.YawDeg = [double](Opt $o 'yaw' 0)
            $obj.Yaw = [int][math]::Round($obj.YawDeg * 65536 / 360)
            $obj.Hidden = [bool](Opt $o 'hidden' $true)
            # loops: XComLadder.LoopAnimations, the climb's half loops between getting on and off (4 for the 477-unit
            # LadderMetalA_448; the climb snaps to the top at the end, so a wrong count only looks off).
            $obj.Loops = [int](Opt $o 'loops' 4)
            if ($obj.Loops -lt 0) { throw "${what}: loops must be 0 or more" }
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a ladder takes no volume; its tiles are seeded and rebuilt" }
        } elseif ($type -eq 'bake') {
            # A base-map actor put somewhere else in the lab's copy of the map itself, so it stands there from load
            # (bake_actor.py): ladders, whose climb links the game re-makes from where they stood at load (F-30).
            $obj.Actor = [string](Opt $o 'actor' '')
            if ($obj.Actor -notmatch '^[A-Za-z_]\w*$') { throw "${what}: a bake needs actor, the base map's actor name (e.g. XComLadder_4)" }
            $y = Opt $o 'yaw' $null
            $obj.YawDeg = if ($null -ne $y) { [double]$y } else { $null }
            $obj.Links = [bool](Opt $o 'links' $true)
            $obj.Join = [int](Opt $o 'join' -1)
            $obj.Mesh = $null
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a bake places no actor of its own" }
        } elseif ($type -eq 'spawn') {
            # XComMapEdSpawner (script package XComMapEd): spawns the game's own actor from an archetype in memory.
            $gamePath = '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+){1,4}$'
            $obj.Archetype = [string](Opt $o 'archetype' '')
            if ($obj.Archetype -notmatch $gamePath) { throw "${what}: archetype must be a game path, e.g. VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1" }
            $obj.Partner = [string](Opt $o 'partner' '')
            if ($obj.Partner -and $obj.Partner -notmatch $gamePath) { throw "${what}: partner must be a game path" }
            $obj.PartnerOffset = Get-Vec (Opt $o 'partnerOffset' @(0, 0, 0)) 3 "${what}: partnerOffset"
            $tint = Opt $o 'tint' $null
            $obj.Tint = if ($null -ne $tint) { Get-Vec $tint 3 "${what}: tint" } else { $null }
            $obj.RebuildExtent = Get-Vec (Opt $o 'rebuildExtent' @(192, 256, 160)) 3 "${what}: rebuildExtent"
            $obj.YawDeg = [double](Opt $o 'yaw' 0); $obj.Yaw = [int][math]::Round($obj.YawDeg * 65536 / 360)
            $obj.Mesh = $null
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a spawn rebuilds its own tile data (rebuildExtent); add a separate volume object if you want one" }
        } elseif ($type -eq 'copy') {
            # XComMapEdCopier (script package XComMapEd): copies pieces the base map placed, moved and turned as one group.
            $obj.From = @(Opt $o 'from' @() | ForEach-Object { [string]$_ })
            if (-not $obj.From.Count) { throw "${what}: a copy needs from, the names of the base map's pieces (e.g. XComDecoFracLevelActor_10)" }
            foreach ($k in $obj.From) { if ($k -notmatch '^[A-Za-z_]\w*$') { throw "${what}: '$k' must be an actor name such as XComDecoFracLevelActor_10" } }
            # poses (the editor's compiler, E3): one absolute pose per name in from, a location and a full rotator in
            # whole rotation units (65536 a turn), instead of moving the group from pivot by yaw. A name may then
            # appear more than once (two copies of one piece). labels name each copy in the log; boxes (the copies'
            # world boxes, [x0, x1, y0, y1, z0, z1]) are what seed_map.py plans their tiles from.
            $obj.Poses = $null; $obj.Labels = @()
            $poses = Opt $o 'poses' $null
            if ($null -ne $poses) {
                $poses = @($poses)
                if ($poses.Count -ne $obj.From.Count) { throw "${what}: poses needs one pose per name in from ($($obj.From.Count)), not $($poses.Count)" }
                foreach ($f in 'pivot', 'yaw', 'building', 'inBuilding') { if ($o.PSObject.Properties[$f]) { throw "${what}: a copy with poses places each piece itself; it takes no $f" } }
                $obj.Poses = @(for ($k = 0; $k -lt $poses.Count; $k++) {
                    $pl = Get-Vec (Opt $poses[$k] 'location' $null) 3 "${what}: poses[$k].location"
                    $pr = @(Opt $poses[$k] 'rotation' @() | ForEach-Object { [double]$_ })
                    if ($pr.Count -ne 3) { throw "${what}: poses[$k].rotation needs [pitch, yaw, roll]" }
                    foreach ($v in $pr) { if ($v -ne [math]::Truncate($v) -or [math]::Abs($v) -gt 2147483647) { throw "${what}: poses[$k].rotation must be whole rotation units (65536 a turn)" } }
                    [pscustomobject]@{ Location = $pl; Rotation = [int[]]@($pr | ForEach-Object { [int]$_ }) }
                })
                $obj.Labels = @(Opt $o 'labels' @() | ForEach-Object { [string]$_ })
                if ($obj.Labels.Count -and $obj.Labels.Count -ne $obj.From.Count) { throw "${what}: labels needs one label per name in from" }
                foreach ($k in $obj.Labels) { if ($k -notmatch '^[\x20-\x7E]*$' -or $k -match '"') { throw "${what}: label '$k' must be plain ASCII without quotes" } }
                # read the property itself: a function's return (Opt) would unroll a single box into its six numbers
                $bx = $null; if ($o.PSObject.Properties['boxes']) { $bx = $o.boxes }
                if ($null -ne $bx -and @($bx).Count -ne $obj.From.Count) { throw "${what}: boxes needs one box per name in from" }
                $obj.Pivot = [double[]]@(0, 0, 0); $obj.YawDeg = 0; $obj.Yaw = 0
            } else {
                if (@($obj.From | Select-Object -Unique).Count -ne $obj.From.Count) { throw "${what}: a name may appear twice in from only with poses" }
                $obj.Pivot = Get-Vec (Opt $o 'pivot' $null) 3 "${what}: pivot"
                $obj.YawDeg = [double](Opt $o 'yaw' 0)
                if ($obj.YawDeg % 90 -ne 0) { throw "${what}: yaw must be a multiple of 90 so the copies stay on the tile grid" }
                $obj.Yaw = [int][math]::Round($obj.YawDeg * 65536 / 360)
            }
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            # Break groups (the editor's groups that break together): breakGroups gives a group number per name in from
            # (0 for none); breakOriginals names the base map's own pieces, left in place, that break with a group.
            # The copier links each group's pieces at load: damage to one takes the others with it.
            $obj.BreakGroups = [int[]]@(Opt $o 'breakGroups' @() | ForEach-Object {
                if ("$_" -notmatch '^\d+$') { throw "${what}: breakGroups must be whole numbers, 0 for none" }; [int]$_ })
            if ($obj.BreakGroups.Count -and $obj.BreakGroups.Count -ne $obj.From.Count) { throw "${what}: breakGroups needs one number per name in from" }
            $obj.BreakOriginals = @(Opt $o 'breakOriginals' @() | ForEach-Object {
                $bn = [string](Opt $_ 'name' ''); $bg = "$(Opt $_ 'group' '')"
                if ($bn -notmatch '^[A-Za-z_]\w*$' -or $bg -notmatch '^[1-9]\d*$') { throw "${what}: each breakOriginals entry needs a name (an actor name such as XComDestructibleActor_60) and a group (1 or more)" }
                [pscustomobject]@{ Name = $bn; Group = [int]$bg } })
            $obj.Mesh = $null
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a copy rebuilds the tile data over its own pieces" }
            # A building volume for the copies, with floor volumes moved and turned like them from the base map's (by name).
            # inBuilding: the index of an earlier copy object whose building these copies join.
            $obj.InBuilding = [int](Opt $o 'inBuilding' -1)
            $obj.Building = $null
            $bld = Opt $o 'building' $null
            if ($null -ne $bld) {
                $floors = [Collections.Generic.List[string[]]]::new()
                foreach ($f in @(Opt $bld 'floors' @())) {
                    $names = [string[]]@($f | ForEach-Object { [string]$_ })
                    foreach ($k in $names) { if ($k -notmatch '^[A-Za-z_]\w*$') { throw "${what}: building floor volume '$k' must be an actor name such as XComFloorVolume_15" } }
                    if (-not $names.Count) { throw "${what}: each building floor needs at least one floor volume" }
                    $floors.Add($names)
                }
                if (-not $floors.Count) { throw "${what}: building.floors lists the base map's floor volumes per floor, e.g. " + '[["XComFloorVolume_15"], ["XComFloorVolume_16"]]' }
                if (@($floors | ForEach-Object { $_ }).Count -gt 9) { throw "${what}: at most 9 floor volumes per building" }
                $obj.Building = [pscustomobject]@{ Floors = $floors; Margin = [double](Opt $bld 'margin' 96); Below = [double](Opt $bld 'below' 144); Above = [double](Opt $bld 'above' 48) }
            }
        } elseif ($type -eq 'hide') {
            # XComMapEdHider (script package XComMapEd): takes the base map's actors in a box out of play at load.
            $obj.Half = Get-Vec (Opt $o 'half' 512) 3 "${what}: half"
            foreach ($h in $obj.Half) { if ($h -le 0) { throw "${what}: half-sizes must be > 0" } }
            $obj.Keep = @(Opt $o 'keep' @() | ForEach-Object { [string]$_ })
            $obj.HideInPlace = @()   # filled by t3d: the patch's own ladders
            $obj.AlsoHide = @(Opt $o 'alsoHide' @() | ForEach-Object { [string]$_ })
            foreach ($k in $obj.Keep + $obj.AlsoHide) { if ($k -notmatch '^[A-Za-z_]\w*$') { throw "${what}: '$k' must be an actor name such as XComLevelActor_91" } }
            # exact (the editor's compiler, E3): hide only the base map's actors named in alsoHide, wherever they stand,
            # with no box; labels name each target in the log.
            $obj.Exact = [bool](Opt $o 'exact' $false); $obj.Labels = @()
            if ($obj.Exact) {
                if (-not $obj.AlsoHide.Count) { throw "${what}: an exact hide needs alsoHide, the base map's actors to hide" }
                if (@($obj.AlsoHide | Select-Object -Unique).Count -ne $obj.AlsoHide.Count) { throw "${what}: an actor is named twice in alsoHide" }
                foreach ($f in 'half', 'keep') { if ($o.PSObject.Properties[$f]) { throw "${what}: an exact hide hides only alsoHide; it takes no $f" } }
                $obj.Labels = @(Opt $o 'labels' @() | ForEach-Object { [string]$_ })
                if ($obj.Labels.Count -and $obj.Labels.Count -ne $obj.AlsoHide.Count) { throw "${what}: labels needs one label per name in alsoHide" }
                foreach ($k in $obj.Labels) { if ($k -notmatch '^[\x20-\x7E]*$' -or $k -match '"') { throw "${what}: label '$k' must be plain ASCII without quotes" } }
            }
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $obj.Extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            $obj.Mesh = $null; $obj.YawDeg = 0
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a hide rebuilds the tile data over its own box" }
        } elseif ($type -eq 'borrow') {
            # XComMapEdBorrowedMesh (script package XComMapEd): shows a mesh the base map already has in memory.
            $gamePath = '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+){1,4}$'
            $path = [string](Opt $o 'meshPath' '')
            $from = [string](Opt $o 'copyFrom' '')
            if (-not $path -and -not $from) { throw "${what}: a borrow needs copyFrom (an actor or archetype, e.g. VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1) or meshPath" }
            foreach ($p in @($path, $from) | Where-Object { $_ }) { if ($p -notmatch $gamePath) { throw "${what}: '$p' must be a game path, Package.Group.Name" } }
            $mats = @(Opt $o 'materials' @() | ForEach-Object { [string]$_ })
            foreach ($p in $mats | Where-Object { $_ }) { if ($p -notmatch $gamePath) { throw "${what}: material '$p' must be a game path" } }
            $obj.CopyFrom = $from; $obj.Materials = $mats
            $mesh = [string](Opt $o 'mesh' 'CoverPatch.High2x2')
            if ($mesh -notmatch '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$') { throw "${what}: mesh (the placeholder) must be Package.Name" }
            $scale = Opt $o 'scale' $null
            if ($null -ne $scale) { $scale = @($scale | ForEach-Object { [double]$_ }); if ($scale.Count -notin 1, 3) { throw "${what}: scale is a number or [x, y, z]" } }
            $obj.MeshPath = $path; $obj.Mesh = $mesh; $obj.YawDeg = [double](Opt $o 'yaw' 0); $obj.Scale = $scale
            $obj.Yaw = [int][math]::Round($obj.YawDeg * 65536 / 360)
            $obj.Extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            if ((Opt $o 'volume' $false) -ne $false) { throw "${what}: a borrow has no collision, so it takes no rebuild volume; add a hidden cover actor for gameplay" }
        } elseif ($type -eq 'actor') {
            $mesh = [string](Opt $o 'mesh' '')
            if ($mesh -notmatch '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$') { throw "${what}: mesh must be Package.Name, e.g. CoverPatch.High2x2" }
            $cover = ([string](Opt $o 'cover' 'Default')) -replace '^CoverForce_', ''
            $cover = @('Default', 'High', 'Low') | Where-Object { $_ -ieq $cover }
            if (-not $cover) { throw "${what}: cover must be Default, High or Low" }
            $coll = [string](Opt $o 'collision' 'BlockAllButWeapons')
            if ($coll -notmatch '^COLLIDE_') { $coll = "COLLIDE_$coll" }
            $coll = $collisionTypes | Where-Object { $_ -ieq $coll }
            if (-not $coll) { throw "${what}: collision must be one of $($collisionTypes -join ', ')" }
            $scale = Opt $o 'scale' $null
            if ($null -ne $scale) { $scale = @($scale | ForEach-Object { [double]$_ }); if ($scale.Count -notin 1, 3) { throw "${what}: scale is a number or [x, y, z]" } }
            $extra = @(Opt $o 'extra' @() | ForEach-Object { [string]$_ })
            foreach ($e in $extra) { if ($e -notmatch '^[A-Za-z_]\w*(\(\d+\))?=[^\r\n]*$') { throw "${what}: extra line '$e' must be Property=Value" } }
            $obj.Mesh = $mesh; $obj.YawDeg = [double](Opt $o 'yaw' 0); $obj.Cover = $cover; $obj.Collision = $coll
            $obj.Hidden = [bool](Opt $o 'hidden' $false); $obj.Scale = $scale; $obj.Extra = $extra
            $obj.Yaw = [int][math]::Round($obj.YawDeg * 65536 / 360)   # degrees -> Unreal rotation units
            $v = Opt $o 'volume' $true
            if ($v -is [bool]) { if ($v) { $v = [pscustomobject]@{} } else { $v = $null } }
            if ($null -ne $v) {
                $half = Get-Vec (Opt $v 'half' 128) 3 "${what}: volume.half"
                $c = if ($v.PSObject.Properties['location']) { Get-Vec $v.location 3 "${what}: volume.location" }
                     else { $off = Get-Vec (Opt $v 'offset' @(0, 0, 12)) 3 "${what}: volume.offset"; @(($pos[0] + $off[0]), ($pos[1] + $off[1]), ($pos[2] + $off[2])) }
                $obj.Volume = @{ Half = $half; Center = @($c | ForEach-Object { [math]::Round($_) }) }
            }
        } else {
            $obj.Volume = @{ Half = (Get-Vec (Opt $o 'half' 128) 3 "${what}: half"); Center = @($pos | ForEach-Object { [math]::Round($_) }) }
        }
        if ($obj.Volume) { foreach ($h in $obj.Volume.Half) { if ($h -le 0) { throw "${what}: volume half-sizes must be > 0" } } }
        $s.Objects += [pscustomobject]$obj
        $i++
    }
    $s
}

# ---------------------------------------------------------------- package names (uncompressed UE3 package)
function Get-PackageObjectNames([string]$Path) {
    $set = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $r = [IO.BinaryReader]::new([IO.File]::OpenRead($Path))
    try {
        function FStr { $n = $r.ReadInt32()
            if ($n -gt 0) { $latin1.GetString($r.ReadBytes($n), 0, $n - 1) }
            elseif ($n -lt 0) { [Text.Encoding]::Unicode.GetString($r.ReadBytes(-2 * $n), 0, -2 * $n - 2) } else { '' } }
        if ($r.ReadUInt32() -ne 2653586369) { throw "$Path is not an Unreal package" }   # tag 0x9E2A83C1
        $null = $r.ReadUInt16(), $r.ReadUInt16(), $r.ReadUInt32(); $null = FStr; $null = $r.ReadUInt32()
        $nameCount = $r.ReadInt32(); $nameOff = $r.ReadInt32(); $expCount = $r.ReadInt32(); $expOff = $r.ReadInt32()
        $null = $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32()
        $null = $r.ReadBytes(16); $gens = $r.ReadInt32(); $null = $r.ReadBytes(12 * $gens)
        $null = $r.ReadUInt32(), $r.ReadUInt32(), $r.ReadUInt32()
        if ($r.ReadInt32() -ne 0) { throw "$Path is compressed; cannot list its names" }
        $r.BaseStream.Position = $nameOff
        $names = for ($k = 0; $k -lt $nameCount; $k++) { FStr; $null = $r.ReadUInt64() }
        $r.BaseStream.Position = $expOff
        for ($k = 0; $k -lt $expCount; $k++) {
            $null = $r.ReadInt32(), $r.ReadInt32(), $r.ReadInt32()
            $ni = $r.ReadInt32(); $nn = $r.ReadInt32()
            $null = $r.ReadInt32(), $r.ReadUInt64(), $r.ReadUInt32(), $r.ReadUInt32(), $r.ReadUInt32()
            $nc = $r.ReadInt32(); $null = $r.ReadBytes(4 * $nc + 16 + 4)
            $null = $set.Add($(if ($nn) { '{0}_{1}' -f $names[$ni], ($nn - 1) } else { $names[$ni] }))
        }
    } finally { $r.Dispose() }
    , $set
}

# ---------------------------------------------------------------- T3D
function Get-Names($o, [int]$base) {
    $n = $base + $o.Index
    @{ Actor = "XComLevelActor_$n"; Mesh = "StaticMeshComponent_$n"; Floor = "XComFloorComponent_$n"; Ladder = "XComLadder_$n"
       Volume = "XComRebuildWorldDataVolume_$n"; Brush = "BrushComponent_$n"; Model = "Model_$n"
       Borrow = "XComMapEdBorrowedMesh_$n"; Light = "DynamicLightEnvironmentComponent_$n"; Spawner = "XComMapEdSpawner_$n"
       Hider = "XComMapEdHider_$n"; Copier = "XComMapEdCopier_$n"; Seeds = "XComMapEdTileSeeds_$n"; Photo = "XComMapEdPhoto_$n"; Sun = "XComMapEdSun_$n"; Intro = "XComMapEdIntro_$n"
       Building = "XComBuildingVolume_${n}0"; BBrush = "BrushComponent_${n}0"; BModel = "Model_${n}0"
       FVol1 = "XComFloorVolume_${n}1"; FVol2 = "XComFloorVolume_${n}2"; FVol3 = "XComFloorVolume_${n}3"; FVol4 = "XComFloorVolume_${n}4"
       FVol5 = "XComFloorVolume_${n}5"; FVol6 = "XComFloorVolume_${n}6"; FVol7 = "XComFloorVolume_${n}7"; FVol8 = "XComFloorVolume_${n}8"
       FVol9 = "XComFloorVolume_${n}9" }
}
# The base map's inventory (tools\upk\map_inventory.py), by actor name; made in <Work>\maps when missing.
function Get-InventoryRows([string]$MapName, $s) {
    $tsv = Join-Path $mapsDir "$MapName-inventory.tsv"
    if (-not (Test-Path -LiteralPath $tsv)) {
        $orig = Get-OriginalMap $MapName
        $global:LASTEXITCODE = 0
        $out = @(& (Get-Python) (Join-Path $PSScriptRoot '..\upk\map_inventory.py') $orig ($tsv -replace '\.tsv$', '') --origin "$($s.OriginX)" "$($s.OriginY)" 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -ne 0) { throw "the map inventory failed: $($out -join ' / ')" }
    }
    $rows = @{}
    Import-Csv -LiteralPath $tsv -Delimiter "`t" | ForEach-Object { $rows[$_.name] = $_ }
    $rows
}
function Get-InventoryBox($row, [string]$what) {
    if (-not $row -or -not $row.'box x') { throw "$what has no box in the map inventory" }
    [double[]]@(($row.'box x', $row.'box y', $row.'box z') | ForEach-Object { $_ -split '\.\.' } | ForEach-Object { [double]::Parse($_, $inv) })
}
# A box (x0, x1, y0, y1, z0, z1) moved from pivot to loc and turned by yaw degrees (a multiple of 90), as copies are.
function Move-Box([double[]]$b, [double[]]$pivot, [double[]]$loc, [double]$yaw) {
    $k = (([int][math]::Round($yaw / 90)) % 4 + 4) % 4
    $xs = [Collections.Generic.List[double]]::new(); $ys = [Collections.Generic.List[double]]::new()
    foreach ($x in $b[0], $b[1]) {
        foreach ($y in $b[2], $b[3]) {
            $dx = $x - $pivot[0]; $dy = $y - $pivot[1]
            switch ($k) { 0 { $rx = $dx; $ry = $dy } 1 { $rx = -$dy; $ry = $dx } 2 { $rx = -$dx; $ry = -$dy } 3 { $rx = $dy; $ry = -$dx } }
            $xs.Add($loc[0] + $rx); $ys.Add($loc[1] + $ry)
        }
    }
    $dz = $loc[2] - $pivot[2]
    [double[]]@(($xs | Measure-Object -Minimum).Minimum, ($xs | Measure-Object -Maximum).Maximum, ($ys | Measure-Object -Minimum).Minimum,
                ($ys | Measure-Object -Maximum).Maximum, ($b[4] + $dz), ($b[5] + $dz))
}
# The copy's building: floor volumes from the base map's, moved and turned like the copies, and a building volume
# around them that lists them floor by floor. Returns the T3D lines and the actors to expect.
function Get-BuildingT3d($o, $n, $s) {
    $rows = Get-InventoryRows $s.MapName $s
    $L = [Collections.Generic.List[string]]::new(); $exp = @(); $refs = @(); $all = @()
    $k = 0
    for ($f = 0; $f -lt $o.Building.Floors.Count; $f++) {
        $fr = @()
        foreach ($src in $o.Building.Floors[$f]) {
            $k++
            $b = Move-Box (Get-InventoryBox $rows[$src] "floor volume $src") $o.Pivot $o.Pos $o.YawDeg
            $all += , $b
            $c = [double[]]@((($b[0] + $b[1]) / 2), (($b[2] + $b[3]) / 2), (($b[4] + $b[5]) / 2))
            $h = [double[]]@((($b[1] - $b[0]) / 2), (($b[3] - $b[2]) / 2), (($b[5] - $b[4]) / 2))
            $vn = $n."FVol$k"
            $L.AddRange([string[]](Get-BoxVolumeT3d 'XComFloorVolume' $h $c $vn ($vn -replace '^XComFloorVolume_', 'BrushComponent_') ($vn -replace '^XComFloorVolume_', 'Model_') @("FloorNumber=$($f + 1)")))
            $exp += [pscustomobject]@{ Class = 'XComFloorVolume'; Name = $vn; Mesh = $null; Pos = $c }
            $fr += "XComFloorVolume'$vn'"
            Say ('  object {0}: {1} (floor {2}) from {3}: x {4}..{5} y {6}..{7} z {8}..{9}' -f $o.Index, $vn, ($f + 1), $src, $b[0], $b[1], $b[2], $b[3], $b[4], $b[5])
        }
        $refs += "Floors($f)=(FloorVolumes=($($fr -join ',')))"
    }
    $m = $o.Building.Margin
    $x0 = ($all | ForEach-Object { $_[0] } | Measure-Object -Minimum).Minimum - $m; $x1 = ($all | ForEach-Object { $_[1] } | Measure-Object -Maximum).Maximum + $m
    $y0 = ($all | ForEach-Object { $_[2] } | Measure-Object -Minimum).Minimum - $m; $y1 = ($all | ForEach-Object { $_[3] } | Measure-Object -Maximum).Maximum + $m
    $z0 = ($all | ForEach-Object { $_[4] } | Measure-Object -Minimum).Minimum - $o.Building.Below; $z1 = ($all | ForEach-Object { $_[5] } | Measure-Object -Maximum).Maximum + $o.Building.Above
    $c = [double[]]@((($x0 + $x1) / 2), (($y0 + $y1) / 2), (($z0 + $z1) / 2)); $h = [double[]]@((($x1 - $x0) / 2), (($y1 - $y0) / 2), (($z1 - $z0) / 2))
    $L.AddRange([string[]](Get-BoxVolumeT3d 'XComBuildingVolume' $h $c $n.Building $n.BBrush $n.BModel $refs))
    $exp += [pscustomobject]@{ Class = 'XComBuildingVolume'; Name = $n.Building; Mesh = $null; Pos = $c; Refs = @(1..$k | ForEach-Object { $n."FVol$_" }) }
    Say ('  object {0}: {1} around them: x {2}..{3} y {4}..{5} z {6}..{7}, {8} floor(s)' -f $o.Index, $n.Building, $x0, $x1, $y0, $y1, $z0, $z1, $o.Building.Floors.Count)
    [pscustomobject]@{ Lines = $L; Expect = $exp }
}
# The seeds actor: rebuilds every planned seed box at load (tools\upk\seed_map.py plan, columns wx0..wz1).
function Get-SeedsT3d($rows, [int]$tiles, [double[]]$pos, $n) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdTileSeeds'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdTileSeeds Name=$($n.Seeds) Archetype=XComMapEdTileSeeds'$arch'")
    $k = 0
    foreach ($r in $rows) {
        $w = 'wx0', 'wy0', 'wz0', 'wx1', 'wy1', 'wz1' | ForEach-Object { F6 ([double]::Parse($r.$_, $inv)) }
        $L.Add(("${b}SeedBoxes($k)=(Min=(X={0},Y={1},Z={2}),Max=(X={3},Y={4},Z={5}),IsValid=1)" -f $w))
        $k++
    }
    $L.Add("${b}PlannedTiles=$tiles")
    $L.Add("${b}$(Loc $pos)")
    $L.Add("${b}Name=`"$($n.Seeds)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdTileSeeds'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-SpawnT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdSpawner'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdSpawner Name=$($n.Spawner) Archetype=XComMapEdSpawner'$arch'")
    $L.Add("${b}ArchetypePath=`"$($o.Archetype)`"")
    if ($o.Partner) {
        $L.Add("${b}PartnerPath=`"$($o.Partner)`"")
        $p = $o.PartnerOffset
        if ($p[0] -or $p[1] -or $p[2]) { $L.Add(("${b}PartnerOffset=(X={0},Y={1},Z={2})" -f (F6 $p[0]), (F6 $p[1]), (F6 $p[2]))) }
    }
    if ($o.Tint) { $L.Add("${b}bTint=True"); $L.Add(("${b}Tint=(R={0},G={1},B={2},A=1.000000)" -f (F6 $o.Tint[0]), (F6 $o.Tint[1]), (F6 $o.Tint[2]))) }
    $e = $o.RebuildExtent
    $L.Add(("${b}RebuildExtent=(X={0},Y={1},Z={2})" -f (F6 $e[0]), (F6 $e[1]), (F6 $e[2])))
    foreach ($x in $o.Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $o.Pos)")
    if ($o.Yaw) { $L.Add("${b}Rotation=(Pitch=0,Yaw=$($o.Yaw),Roll=0)") }
    $L.Add("${b}Name=`"$($n.Spawner)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdSpawner'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-CopyT3d($o, $n, [string]$Building = '', [string[]]$PrePlaced = @()) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdCopier'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdCopier Name=$($n.Copier) Archetype=XComMapEdCopier'$arch'")
    for ($k = 0; $k -lt $o.From.Count; $k++) { $L.Add("${b}SourceNames($k)=`"$($o.From[$k])`"") }
    for ($k = 0; $k -lt $PrePlaced.Count; $k++) {
        $L.Add("${b}SourceNames($($o.From.Count + $k))=`"$($PrePlaced[$k])`"")
        $L.Add("${b}PrePlaced($k)=`"$($PrePlaced[$k])`"")
    }
    if ($Building) { $L.Add("${b}BuildingName=`"$Building`"") }
    if ($o.Poses) {
        $L.Add("${b}bAbsolutePoses=True")
        for ($k = 0; $k -lt $o.Poses.Count; $k++) {
            $q = $o.Poses[$k]
            $L.Add(("${b}PoseLocations($k)=(X={0},Y={1},Z={2})" -f (F6 $q.Location[0]), (F6 $q.Location[1]), (F6 $q.Location[2])))
            $L.Add("${b}PoseRotations($k)=(Pitch=$($q.Rotation[0]),Yaw=$($q.Rotation[1]),Roll=$($q.Rotation[2]))")
        }
        for ($k = 0; $k -lt $o.Labels.Count; $k++) { $L.Add("${b}CopyLabels($k)=`"$($o.Labels[$k])`"") }
    }
    for ($k = 0; $k -lt $o.BreakGroups.Count; $k++) { $L.Add("${b}BreakGroups($k)=$($o.BreakGroups[$k])") }
    for ($k = 0; $k -lt $o.BreakOriginals.Count; $k++) {
        $L.Add("${b}BreakOriginals($k)=`"$($o.BreakOriginals[$k].Name)`"")
        $L.Add("${b}BreakOriginalGroups($k)=$($o.BreakOriginals[$k].Group)")
    }
    $p = $o.Pivot
    $L.Add(("${b}Pivot=(X={0},Y={1},Z={2})" -f (F6 $p[0]), (F6 $p[1]), (F6 $p[2])))
    foreach ($x in $o.Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $o.Pos)")
    if ($o.Yaw) { $L.Add("${b}Rotation=(Pitch=0,Yaw=$($o.Yaw),Roll=0)") }
    $L.Add("${b}Name=`"$($n.Copier)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdCopier'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-HideT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdHider'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdHider Name=$($n.Hider) Archetype=XComMapEdHider'$arch'")
    if ($o.Exact) {
        $L.Add("${b}bExactTargets=True")
        for ($k = 0; $k -lt $o.Labels.Count; $k++) { $L.Add("${b}TargetLabels($k)=`"$($o.Labels[$k])`"") }
    } else {
        $h = $o.Half
        $L.Add(("${b}HideExtent=(X={0},Y={1},Z={2})" -f (F6 $h[0]), (F6 $h[1]), (F6 $h[2])))
    }
    for ($k = 0; $k -lt $o.Keep.Count; $k++) { $L.Add("${b}KeepNames($k)=`"$($o.Keep[$k])`"") }
    for ($k = 0; $k -lt $o.AlsoHide.Count; $k++) { $L.Add("${b}AlsoHide($k)=`"$($o.AlsoHide[$k])`"") }
    for ($k = 0; $k -lt @($o.HideInPlace).Count; $k++) { $L.Add("${b}HideInPlace($k)=`"$(@($o.HideInPlace)[$k])`"") }
    foreach ($x in $o.Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $o.Pos)")
    $L.Add("${b}Name=`"$($n.Hider)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdHider'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-PhotoT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdPhoto'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdPhoto Name=$($n.Photo) Archetype=XComMapEdPhoto'$arch'")
    foreach ($k in $o.Photo.Keys) {
        $v = $o.Photo[$k]
        $L.Add("${b}$k=$(if ($v -is [bool]) { if ($v) { 'True' } else { 'False' } } else { F6 $v })")
    }
    foreach ($x in $o.Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $o.Pos)")
    $L.Add("${b}Name=`"$($n.Photo)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdPhoto'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-SunT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9
    $arch = 'XComMapEd.Default__XComMapEdSun'
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdSun Name=$($n.Sun) Archetype=XComMapEdSun'$arch'")
    $L.Add("${b}SunBrightness=$(F6 $o.Sun)")
    $L.Add("${b}SkyBrightness=$(F6 $o.Sky)")
    foreach ($x in $o.Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $o.Pos)")
    $L.Add(("${b}Rotation=(Pitch={0},Yaw={1},Roll=0)" -f (-[int][math]::Round($o.PitchDeg * 65536 / 360)), ([int][math]::Round($o.YawDeg * 65536 / 360))))
    $L.Add("${b}Name=`"$($n.Sun)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdSun'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Get-BorrowT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9; $c = ' ' * 12
    $arch = "XComMapEd.Default__XComMapEdBorrowedMesh"
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComMapEdBorrowedMesh Name=$($n.Borrow) Archetype=XComMapEdBorrowedMesh'$arch'")
    $L.Add("${b}Begin Object Class=DynamicLightEnvironmentComponent Name=MyLightEnvironment ObjName=$($n.Light) Archetype=DynamicLightEnvironmentComponent'${arch}:MyLightEnvironment'")
    $L.Add("${c}Name=`"$($n.Light)`"")
    $L.Add("${c}ObjectArchetype=DynamicLightEnvironmentComponent'${arch}:MyLightEnvironment'")
    $L.Add("${b}End Object")
    $L.Add("${b}Begin Object Class=StaticMeshComponent Name=StaticMeshComponent0 ObjName=$($n.Mesh) Archetype=StaticMeshComponent'${arch}:StaticMeshComponent0'")
    $L.Add("${c}StaticMesh=StaticMesh'$($o.Mesh)'")
    $L.Add("${c}LightEnvironment=DynamicLightEnvironmentComponent'$($n.Light)'")
    $L.Add("${c}Name=`"$($n.Mesh)`"")
    $L.Add("${c}ObjectArchetype=StaticMeshComponent'${arch}:StaticMeshComponent0'")
    $L.Add("${b}End Object")
    if ($o.CopyFrom) { $L.Add("${b}CopyFromPath=`"$($o.CopyFrom)`"") }
    if ($o.MeshPath) { $L.Add("${b}MeshPath=`"$($o.MeshPath)`"") }
    for ($k = 0; $k -lt $o.Materials.Count; $k++) { if ($o.Materials[$k]) { $L.Add("${b}MaterialPaths($k)=`"$($o.Materials[$k])`"") } }
    $L.Add("${b}StaticMeshComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}LightEnvironment=DynamicLightEnvironmentComponent'$($n.Light)'")
    $L.Add("${b}Components(0)=DynamicLightEnvironmentComponent'$($n.Light)'")
    $L.Add("${b}Components(1)=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}$(Loc $o.Pos)")
    if ($o.Yaw) { $L.Add("${b}Rotation=(Pitch=0,Yaw=$($o.Yaw),Roll=0)") }
    if ($o.Scale) {
        if ($o.Scale.Count -eq 1) { if ($o.Scale[0] -ne 1) { $L.Add("${b}DrawScale=$(F6 $o.Scale[0])") } }
        else { $L.Add(("${b}DrawScale3D=(X={0},Y={1},Z={2})" -f (F6 $o.Scale[0]), (F6 $o.Scale[1]), (F6 $o.Scale[2]))) }
    }
    foreach ($e in $o.Extra) { $L.Add("${b}$e") }
    $L.Add("${b}CollisionComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Name=`"$($n.Borrow)`"")
    $L.Add("${b}ObjectArchetype=XComMapEdBorrowedMesh'$arch'")
    $L.Add("${a}End Actor")
    $L
}
function Loc([double[]]$p) { 'Location=(X={0},Y={1},Z={2})' -f (F6 $p[0]), (F6 $p[1]), (F6 $p[2]) }
# A ladder, written as the shipped patch_bar's XComLadder_15 is (hidden there; the base map draws the visible one).
function Get-LadderT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9; $c = ' ' * 12
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComLadder Name=$($n.Ladder) Archetype=XComLadder'XComGame.Default__XComLadder'")
    $L.Add("${b}Begin Object Class=StaticMeshComponent Name=StaticMeshComponent0 ObjName=$($n.Mesh) Archetype=StaticMeshComponent'XComGame.Default__XComLadder:StaticMeshComponent0'")
    $L.Add("${c}StaticMesh=StaticMesh'$($o.Mesh)'")
    $L.Add("${c}WireframeColor=(B=6,G=255,R=193,A=255)")
    $L.Add("${c}ReplacementPrimitive=None")
    $L.Add("${c}bAllowApproximateOcclusion=True")
    $L.Add("${c}bUsePrecomputedShadows=True")
    $L.Add("${c}LightingChannels=(bInitialized=True,Static=True)")
    $L.Add("${c}Name=`"$($n.Mesh)`"")
    $L.Add("${c}ObjectArchetype=StaticMeshComponent'XComGame.Default__XComLadder:StaticMeshComponent0'")
    $L.Add("${b}End Object")
    $L.Add("${b}LoopAnimations=$($o.Loops)")
    $L.Add("${b}StaticMesh=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}VisibilityBlockingData=(bBlockUnitVisibility=False)")
    $L.Add("${b}bCanClimbOver=True")
    $L.Add("${b}bIgnoreForCover=True")
    $L.Add("${b}StaticMeshComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Components(0)=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}$(Loc $o.Pos)")
    if ($o.Yaw) { $L.Add("${b}Rotation=(Pitch=0,Yaw=$($o.Yaw),Roll=0)") }
    if ($o.Hidden) { $L.Add("${b}bHidden=True") }
    foreach ($e in $o.Extra) { $L.Add("${b}$e") }
    $L.Add("${b}Tag=`"XComLadder`"")
    $L.Add("${b}CollisionComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Name=`"$($n.Ladder)`"")
    $L.Add("${b}ObjectArchetype=XComLadder'XComGame.Default__XComLadder'")
    $L.Add("${a}End Actor")
    $L
}
function Get-ActorT3d($o, $n) {
    $a = ' ' * 6; $b = ' ' * 9; $c = ' ' * 12
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=XComLevelActor Name=$($n.Actor) Archetype=XComLevelActor'XComGame.Default__XComLevelActor'")
    $L.Add("${b}Begin Object Class=StaticMeshComponent Name=StaticMeshComponent0 ObjName=$($n.Mesh) Archetype=StaticMeshComponent'XComGame.Default__XComLevelActor:StaticMeshComponent0'")
    $L.Add("${c}StaticMesh=StaticMesh'$($o.Mesh)'")
    $L.Add("${c}WireframeColor=(B=6,G=255,R=193,A=255)")
    $L.Add("${c}ReplacementPrimitive=None")
    $L.Add("${c}bAllowApproximateOcclusion=True")
    $L.Add("${c}bUsePrecomputedShadows=True")
    if ($o.Collision -eq 'COLLIDE_BlockAllButWeapons') { $L.Add("${c}BlockZeroExtent=False") }   # weapons pass; pawns are blocked
    $L.Add("${c}LightingChannels=(bInitialized=True,Static=True)")
    $L.Add("${c}Name=`"$($n.Mesh)`"")
    $L.Add("${c}ObjectArchetype=StaticMeshComponent'XComGame.Default__XComLevelActor:StaticMeshComponent0'")
    $L.Add("${b}End Object")
    $L.Add("${b}Begin Object Class=XComFloorComponent Name=FloorComponent0 ObjName=$($n.Floor) Archetype=XComFloorComponent'XComGame.Default__XComLevelActor:FloorComponent0'")
    $L.Add("${c}OwnerMeshComponents(0)=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${c}Name=`"$($n.Floor)`"")
    $L.Add("${c}ObjectArchetype=XComFloorComponent'XComGame.Default__XComLevelActor:FloorComponent0'")
    $L.Add("${b}End Object")
    $L.Add("${b}FloorComponent=XComFloorComponent'$($n.Floor)'")
    if ($o.Cover -ne 'Default') { $L.Add("${b}CoverForceFlag=CoverForce_$($o.Cover)") }
    $L.Add("${b}StaticMeshComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Components(0)=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Components(1)=XComFloorComponent'$($n.Floor)'")
    $L.Add("${b}$(Loc $o.Pos)")
    if ($o.Yaw) { $L.Add("${b}Rotation=(Pitch=0,Yaw=$($o.Yaw),Roll=0)") }
    if ($o.Scale) {
        if ($o.Scale.Count -eq 1) { if ($o.Scale[0] -ne 1) { $L.Add("${b}DrawScale=$(F6 $o.Scale[0])") } }
        else { $L.Add(("${b}DrawScale3D=(X={0},Y={1},Z={2})" -f (F6 $o.Scale[0]), (F6 $o.Scale[1]), (F6 $o.Scale[2]))) }
    }
    $L.Add("${b}CollisionType=$($o.Collision)")
    if ($o.Hidden) { $L.Add("${b}bHidden=True") }
    foreach ($e in $o.Extra) { $L.Add("${b}$e") }
    $L.Add("${b}Tag=`"XComLevelActor`"")
    $L.Add("${b}CollisionComponent=StaticMeshComponent'$($n.Mesh)'")
    $L.Add("${b}Name=`"$($n.Actor)`"")
    $L.Add("${b}ObjectArchetype=XComLevelActor'XComGame.Default__XComLevelActor'")
    $L.Add("${a}End Actor")
    $L
}
# A box brush with half-sizes $h, laid out exactly like the editor's own cube brush (as in patch_bar's volumes).
function Get-VolumeT3d($o, $n) {
    Get-BoxVolumeT3d 'XComRebuildWorldDataVolume' $o.Volume.Half $o.Volume.Center $n.Volume $n.Brush $n.Model @()
}
function Get-BoxVolumeT3d([string]$Class, [double[]]$h, [double[]]$Center, [string]$VolName, [string]$BrushName, [string]$ModelName, [string[]]$Extra) {
    $a = ' ' * 6; $b = ' ' * 9; $c = ' ' * 12; $p = ' ' * 15; $q = ' ' * 18
    function V([string]$pat) { , @(0..2 | ForEach-Object { $(if ($pat[$_] -eq '-') { -1 } else { 1 }) * $h[$_] }) }
    function BN([double]$v) { $(if ($v -lt 0) { '-' } else { '+' }) + [math]::Abs($v).ToString('00000.000000', $inv) }
    function BV([string]$pat) { $v = V $pat; ($v | ForEach-Object { BN $_ }) -join ',' }
    $verts = @('++-', '+--', '---', '+++', '--+', '-+-', '+-+', '-++') | ForEach-Object { , (V $_) }
    $vd = ($verts | ForEach-Object { '(X={0},Y={1},Z={2})' -f (F6 $_[0]), (F6 $_[1]), (F6 $_[2]) }) -join ','
    $pv = (0, 4 | ForEach-Object { $g = $_; 0..2 | ForEach-Object {
        '(W={0},X={1},Y={2},Z={3})' -f (F6 $verts[$g + 3][$_]), (F6 $verts[$g][$_]), (F6 $verts[$g + 1][$_]), (F6 $verts[$g + 2][$_]) } }) -join ','
    # Plane distances as float32(h * 0.99999994), the editor's float rounding of the cube's normals.
    $W = { param($x) F6 ([double][float]($x * 0.99999994)) }
    $fp = (@(@('X=0.000000,Y=-0.000000,Z=-1.000000', 2), @('X=1.000000,Y=0.000000,Z=0.000000', 0), @('X=0.000000,Y=-1.000000,Z=0.000000', 1),
             @('X=-1.000000,Y=0.000000,Z=0.000000', 0), @('X=-0.000000,Y=1.000000,Z=0.000000', 1), @('X=0.000000,Y=-0.000000,Z=1.000000', 2)) |
           ForEach-Object { '(W={0},{1})' -f (& $W $h[$_[1]]), $_[0] }) -join ','
    $box = '(Min=(X={0},Y={1},Z={2}),Max=(X={3},Y={4},Z={5}),IsValid=1)' -f (F6 (-$h[0])), (F6 (-$h[1])), (F6 (-$h[2])), (F6 $h[0]), (F6 $h[1]), (F6 $h[2])
    $agg = "BrushAggGeom=(ConvexElems=((VertexData=($vd),PermutedVertexData=($pv),FaceTriData=(0,2,1,0,5,2,1,3,0,1,6,3,4,1,2,4,6,1,5,4,2,5,7,4,7,0,3,7,5,0,6,7,3,6,4,7)," +
        'EdgeDirections=((X=-1.000000,Y=0.000000,Z=0.000000),(X=0.000000,Y=-1.000000,Z=0.000000),(X=0.000000,Y=0.000000,Z=1.000000)),' +
        'FaceNormalDirections=((X=0.000000,Y=-0.000000,Z=-1.000000),(X=1.000000,Y=0.000000,Z=0.000000),(X=0.000000,Y=-1.000000,Z=0.000000)),' +
        "FacePlaneData=($fp),ElemBox=$box)))"
    $faces = @(
        @('---', '-00001.000000,+00000.000000,+00000.000000', '+00000.000000,+00001.000000,+00000.000000', '+00000.000000,+00000.000000,-00001.000000', '---', '--+', '-++', '-+-'),
        @('-+-', '+00000.000000,+00001.000000,+00000.000000', '+00001.000000,-00000.000000,+00000.000000', '+00000.000000,+00000.000000,-00001.000000', '-+-', '-++', '+++', '++-'),
        @('++-', '+00001.000000,+00000.000000,+00000.000000', '+00000.000000,-00001.000000,+00000.000000', '+00000.000000,+00000.000000,-00001.000000', '++-', '+++', '+-+', '+--'),
        @('+--', '+00000.000000,-00001.000000,+00000.000000', '-00001.000000,-00000.000000,-00000.000000', '+00000.000000,+00000.000000,-00001.000000', '+--', '+-+', '--+', '---'),
        @('-++', '+00000.000000,+00000.000000,+00001.000000', '+00001.000000,+00000.000000,+00000.000000', '+00000.000000,+00001.000000,+00000.000000', '-++', '--+', '+-+', '+++'),
        @('---', '+00000.000000,+00000.000000,-00001.000000', '+00001.000000,+00000.000000,+00000.000000', '+00000.000000,-00001.000000,+00000.000000', '---', '-+-', '++-', '+--'))
    $L = [Collections.Generic.List[string]]::new()
    $L.Add("${a}Begin Actor Class=$Class Name=$VolName Archetype=$Class'XComGame.Default__${Class}'")
    $L.Add("${b}Begin Object Class=BrushComponent Name=BrushComponent0 ObjName=$BrushName Archetype=BrushComponent'XComGame.Default__${Class}:BrushComponent0'")
    $L.Add("${c}Brush=Model'$ModelName'")
    $L.Add("${c}$agg")
    foreach ($t in 'ReplacementPrimitive=None', 'bAcceptsLights=True', 'CollideActors=True', 'BlockNonZeroExtent=True', 'bDisableAllRigidBody=True',
                   'AlwaysLoadOnClient=True', 'AlwaysLoadOnServer=True', 'LightingChannels=(bInitialized=True,Dynamic=True)') { $L.Add("${c}$t") }
    $L.Add("${c}Name=`"$BrushName`"")
    $L.Add("${c}ObjectArchetype=BrushComponent'XComGame.Default__${Class}:BrushComponent0'")
    $L.Add("${b}End Object")
    $L.Add("${b}Begin Brush Name=$ModelName")
    $L.Add("${c}Begin PolyList")
    for ($k = 0; $k -lt 6; $k++) {
        $f = $faces[$k]
        $L.Add("${p}Begin Polygon Flags=3584 Link=$k")
        $L.Add("${q}Origin   $(BV $f[0])")
        $L.Add("${q}Normal   $($f[1])")
        $L.Add("${q}TextureU $($f[2])")
        $L.Add("${q}TextureV $($f[3])")
        foreach ($vp in $f[4..7]) { $L.Add("${q}Vertex   $(BV $vp)") }
        $L.Add("${p}End Polygon")
    }
    $L.Add("${c}End PolyList")
    $L.Add("${b}End Brush")
    $L.Add("${b}Brush=Model'$ModelName'")
    $L.Add("${b}BrushComponent=BrushComponent'$BrushName'")
    $L.Add("${b}Components(0)=BrushComponent'$BrushName'")
    foreach ($x in $Extra) { $L.Add("${b}$x") }
    $L.Add("${b}$(Loc $Center)")
    $L.Add("${b}Tag=`"$Class`"")
    $L.Add("${b}CollisionComponent=BrushComponent'$BrushName'")
    $L.Add("${b}Name=`"$VolName`"")
    $L.Add("${b}ObjectArchetype=$Class'XComGame.Default__${Class}'")
    $L.Add("${a}End Actor")
    $L
}
function Step-T3d($s) {
    $wd = Join-Path $Work $s.Name
    $taken = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    if ($s.BasePath) { $taken = Get-PackageObjectNames $s.BasePath }
    $base = $s.NameBase
    for ($tries = 0; ; $tries++) {
        $clash = @(@($s.Objects) + @([pscustomobject]@{ Index = $s.Objects.Count }, [pscustomobject]@{ Index = $s.Objects.Count + 1 }) | ForEach-Object { (Get-Names $_ $base).Values } | Where-Object { $taken.Contains($_) })
        if (-not $clash) { break }
        if ($tries -ge 100) { throw "no free name suffix found from $($s.NameBase)" }
        Say "names with suffix $base clash with the base patch ($($clash[0]), ...); trying $($base + 100)"
        $base += 100
    }
    $L = [Collections.Generic.List[string]]::new()
    $L.Add('Begin Map'); $L.Add('   Begin Level')
    # MAP IMPORTADD silently drops the file's first actor when that actor is non-static (our borrow actor, an
    # InterpActor); a Note or XComLevelActor first is kept (EXP-05, 3 November 2026). So lead with a Note then.
    $lead = ''
    $first = if ($s.Objects.Count) { $s.Objects[0].Type } elseif ($s.Intro) { 'intro' } else { '' }
    if ($first -in 'borrow', 'spawn', 'hide', 'copy', 'photo', 'sun', 'intro') {
        $lead = "Note_$base"
        $p0 = if ($s.Objects.Count) { $s.Objects[0].Pos } else { [double[]]@($s.OriginX, $s.OriginY, 1000) }
        foreach ($t in "      Begin Actor Class=Note Name=Note_$base Archetype=Note'Engine.Default__Note'",
                       "         Text=`"patchtool $($s.Name): the import drops a leading non-static actor`"",
                       "         $(Loc @($p0[0], $p0[1], ($p0[2] + 200)))", "      End Actor") { $L.Add($t) }
    }
    $expect = @()
    foreach ($o in $s.Objects) {
        $n = Get-Names $o $base
        if ($o.Type -eq 'actor') {
            $L.AddRange([string[]](Get-ActorT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComLevelActor'; Name = $n.Actor; Mesh = $o.Mesh; Pos = $o.Pos }
            $desc = '{0} {1} at ({2}) yaw {3} cover {4} {5}{6}' -f $n.Actor, $o.Mesh, (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), $o.YawDeg, $o.Cover, $o.Collision, $(if ($o.Hidden) { ' hidden' } else { '' })
            Say "  object $($o.Index): $desc"
        } elseif ($o.Type -eq 'spawn') {
            $L.AddRange([string[]](Get-SpawnT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdSpawner'; Name = $n.Spawner; Mesh = $null; Pos = $o.Pos }
            Say ('  object {0}: {1} spawns {2}{3} at ({4}) yaw {5}{6}' -f $o.Index, $n.Spawner, $o.Archetype, $(if ($o.Partner) { " + $($o.Partner)" } else { '' }),
                (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), $o.YawDeg, $(if ($o.Tint) { " tint ($($o.Tint -join ', '))" } else { '' }))
        } elseif ($o.Type -eq 'copy') {
            $bt = $null
            if ($o.Building) {
                if (-not $s.MapName) { throw "objects[$($o.Index)]: a copy's building needs map.name, to read the base map's floor volumes" }
                $bt = Get-BuildingT3d $o $n $s
            }
            $bName = ''
            if ($bt) { $bName = $n.Building }
            elseif ($o.InBuilding -ge 0) {
                $owner = if ($o.InBuilding -lt $o.Index) { $s.Objects[$o.InBuilding] } else { $null }
                if (-not $owner -or $owner.Type -ne 'copy' -or -not $owner.Building) { throw "objects[$($o.Index)]: inBuilding $($o.InBuilding) must be an earlier copy object with a building" }
                $bName = (Get-Names $owner $base).Building
            }
            $pre = [string[]]@($s.Objects | Where-Object { $_.Type -eq 'bake' -and $_.Join -eq $o.Index } | ForEach-Object { $_.Actor })
            $L.AddRange([string[]](Get-CopyT3d $o $n $bName $pre))
            $expect += [pscustomobject]@{ Class = 'XComMapEdCopier'; Name = $n.Copier; Mesh = $null; Pos = $o.Pos }
            if ($bt) { $L.AddRange([string[]]$bt.Lines); $expect += $bt.Expect }
            if ($o.Poses) {
                Say ('  object {0}: {1} copies {2} piece(s), each to its own pose' -f $o.Index, $n.Copier, $o.From.Count)
                for ($k = 0; $k -lt $o.From.Count; $k++) {
                    $q = $o.Poses[$k]
                    Say ('    {0} to ({1}) rotation ({2}){3}' -f $o.From[$k], (($q.Location | ForEach-Object { F6 $_ }) -join ', '), ($q.Rotation -join ', '),
                        $(if ($k -lt $o.Labels.Count) { " as $($o.Labels[$k])" } else { '' }))
                }
            } else {
                Say ('  object {0}: {1} copies {2} piece(s) ({3}) from pivot ({4}) to ({5}) yaw {6}' -f $o.Index, $n.Copier, $o.From.Count, ($o.From -join ' '),
                    ($o.Pivot -join ', '), (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), $o.YawDeg)
            }
        } elseif ($o.Type -eq 'sun') {
            $L.AddRange([string[]](Get-SunT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdSun'; Name = $n.Sun; Mesh = $null; Pos = $o.Pos }
            Say ('  object {0}: {1} lights the map: sun {2} from yaw {3}, {4} degrees down; sky {5}' -f $o.Index, $n.Sun, $o.Sun, $o.YawDeg, $o.PitchDeg, $o.Sky)
        } elseif ($o.Type -eq 'photo') {
            $L.AddRange([string[]](Get-PhotoT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdPhoto'; Name = $n.Photo; Mesh = $null; Pos = $o.Pos }
            Say ('  object {0}: {1} sets up the overview view{2}' -f $o.Index, $n.Photo,
                $(if ($o.Photo.Count) { ' (' + (($o.Photo.Keys | ForEach-Object { "$_ $($o.Photo[$_])" }) -join ', ') + ')' } else { ' (the class defaults)' }))
        } elseif ($o.Type -eq 'ladder') {
            $L.AddRange([string[]](Get-LadderT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComLadder'; Name = $n.Ladder; Mesh = $o.Mesh; Pos = $o.Pos }
            Say ('  object {0}: {1} {2} at ({3}) yaw {4}{5}' -f $o.Index, $n.Ladder, $o.Mesh, (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), $o.YawDeg, $(if ($o.Hidden) { ' hidden' } else { '' }))
        } elseif ($o.Type -eq 'bake') {
            if (-not $s.MapName) { throw "objects[$($o.Index)]: a bake needs map.name, the base map to bake into" }
            if ($o.Join -ge 0 -and ($o.Join -ge $s.Objects.Count -or $s.Objects[$o.Join].Type -ne 'copy')) { throw "objects[$($o.Index)]: join $($o.Join) must be a copy object" }
            Say ('  object {0}: bakes {1} to ({2}){3} in {4} at deploy{5}{6}' -f $o.Index, $o.Actor, ($o.Pos -join ', '), $(if ($null -ne $o.YawDeg) { " yaw $($o.YawDeg)" } else { '' }),
                $s.MapName, $(if ($o.Links) { ', with its pathing links' } else { '' }), $(if ($o.Join -ge 0) { ", joining object $($o.Join)'s copies" } else { '' }))
        } elseif ($o.Type -eq 'hide') {
            # The patch's own hidden ladders inside the box are hidden (no collision) but stay where they are; its visible
            # ones are kept (EXP-07 run 30); other hidden doors and ladders go under the map (EXP-07 run 21).
            $o.HideInPlace = @($s.Objects | Where-Object { $_.Type -eq 'ladder' -and $_.Hidden } | ForEach-Object { (Get-Names $_ $base).Ladder })
            $o.Keep = @($o.Keep) + @($s.Objects | Where-Object { $_.Type -eq 'ladder' -and -not $_.Hidden } | ForEach-Object { (Get-Names $_ $base).Ladder })
            $L.AddRange([string[]](Get-HideT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdHider'; Name = $n.Hider; Mesh = $null; Pos = $o.Pos }
            if ($o.Exact) {
                Say ('  object {0}: {1} hides exactly {2} base-map actor(s): {3}' -f $o.Index, $n.Hider, $o.AlsoHide.Count, ($o.AlsoHide -join ' '))
            } else {
                Say ('  object {0}: {1} hides the base map in ({2}) half ({3}){4}{5}' -f $o.Index, $n.Hider, (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), ($o.Half -join ', '),
                    $(if ($o.Keep.Count) { ", keeps $($o.Keep -join ' ')" } else { '' }), $(if ($o.AlsoHide.Count) { ", also hides $($o.AlsoHide -join ' ')" } else { '' }))
            }
        } elseif ($o.Type -eq 'borrow') {
            $L.AddRange([string[]](Get-BorrowT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdBorrowedMesh'; Name = $n.Borrow; Mesh = $o.Mesh; Pos = $o.Pos }
            $src = @($(if ($o.CopyFrom) { "copy of $($o.CopyFrom)" }), $(if ($o.MeshPath) { "mesh $($o.MeshPath)" }), $(if ($o.Materials.Count) { "$($o.Materials.Count) material(s)" })) | Where-Object { $_ }
            Say ('  object {0}: {1} borrows {2} (placeholder {3}) at ({4}) yaw {5}' -f $o.Index, $n.Borrow, ($src -join ', '), $o.Mesh, (($o.Pos | ForEach-Object { F6 $_ }) -join ', '), $o.YawDeg)
        }
        if ($o.Volume) {
            $L.AddRange([string[]](Get-VolumeT3d $o $n))
            $expect += [pscustomobject]@{ Class = 'XComRebuildWorldDataVolume'; Name = $n.Volume; Mesh = $null; Pos = [double[]]$o.Volume.Center }
            Say ('  object {0}: {1} half ({2}) at ({3})' -f $o.Index, $n.Volume, ($o.Volume.Half -join ', '), ($o.Volume.Center -join ', '))
        }
    }
    # A map shipped under a new name gets its base map's dropship intro (F-45): XComMapEdIntro renames the base map's
    # case in the intro's map-name switches at load. Its suffix is the one after the seeds actor's.
    if ($s.Intro) {
        $n = Get-Names ([pscustomobject]@{ Index = $s.Objects.Count + 1 }) $base
        $ip = [double[]]@($s.OriginX, $s.OriginY, 1000)
        foreach ($t in "      Begin Actor Class=XComMapEdIntro Name=$($n.Intro) Archetype=XComMapEdIntro'XComMapEd.Default__XComMapEdIntro'",
                       "         IntroMapName=`"$($s.MapName)`"", "         $(Loc $ip)", "         Name=`"$($n.Intro)`"",
                       "         ObjectArchetype=XComMapEdIntro'XComMapEd.Default__XComMapEdIntro'", "      End Actor") { $L.Add($t) }
        $expect += [pscustomobject]@{ Class = 'XComMapEdIntro'; Name = $n.Intro; Mesh = $null; Pos = $ip }
        Say "  intro: $($n.Intro) gives $($s.ShipAs) $($s.MapName)'s dropship intro (renames its case in CIN_DropshipIntros' map switches at load)"
    }
    # Tile seeds (F-29): plan them from the original base map, and add the actor that rebuilds them at load, last.
    $seedPlan = Join-Path $wd 'seed-plan.tsv'; $seedMap = Join-Path $wd 'seed-plan.map'; $seedLinks = Join-Path $wd 'seed-links.tsv'
    $seedBakes = Join-Path $wd 'seed-bakes.tsv'; $seedExtFile = Join-Path $wd 'seed-external.txt'
    Remove-Item -LiteralPath $seedPlan, $seedMap, $seedLinks, $seedBakes, $seedExtFile -ErrorAction SilentlyContinue
    $bakes = @($s.Objects | Where-Object { $_.Type -eq 'bake' })
    if ($bakes.Count) {
        $rowsInv = Get-InventoryRows $s.MapName $s
        $lines = foreach ($bk in $bakes) {
            $r = $rowsInv[$bk.Actor]
            if (-not $r) { throw "objects[$($bk.Index)]: no $($bk.Actor) in the base map's inventory" }
            # actor, new x y z, new yaw (or -), links 0/1, old x y z, old yaw
            ($bk.Actor, ($bk.Pos -join ' '), $(if ($null -ne $bk.YawDeg) { $bk.YawDeg } else { '-' }), [int]$bk.Links, "$($r.x) $($r.y) $($r.z)", $r.yaw) -join "`t"
        }
        [IO.File]::WriteAllLines($seedBakes, [string[]]@($lines))
        [IO.File]::WriteAllText($seedMap, $s.MapName)
    }
    $placing = @($s.Objects | Where-Object { $_.Type -in 'copy', 'spawn', 'actor' }).Count
    if ($s.MapName -and $s.Seed -and $placing) {
        $orig = Get-OriginalMap $s.MapName
        $global:LASTEXITCODE = 0
        $out = @(& (Get-Python) $seedTool plan $s.Path $orig $seedPlan --inventory (Join-Path $mapsDir "$($s.MapName)-inventory.tsv") 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -ne 0) { throw "the seed plan failed: $($out -join ' / ')" }
        $out | ForEach-Object { Say "  seeds: $_" }
        $rows = @(Import-Csv -LiteralPath $seedPlan -Delimiter "`t")
        if ($rows.Count) {
            $tiles = if (($out -join "`n") -match 'planned \d+ box\(es\), (\d+) tiles') { [int]$Matches[1] } else { 0 }
            $wx = $rows | ForEach-Object { [double]::Parse($_.wx0, $inv); [double]::Parse($_.wx1, $inv) } | Measure-Object -Minimum -Maximum
            $wy = $rows | ForEach-Object { [double]::Parse($_.wy0, $inv); [double]::Parse($_.wy1, $inv) } | Measure-Object -Minimum -Maximum
            $wz = $rows | ForEach-Object { [double]::Parse($_.wz0, $inv) } | Measure-Object -Minimum
            $pos = [double[]]@([math]::Round(($wx.Minimum + $wx.Maximum) / 2), [math]::Round(($wy.Minimum + $wy.Maximum) / 2), [math]::Round($wz.Minimum))
            $n = Get-Names ([pscustomobject]@{ Index = $s.Objects.Count }) $base
            $L.AddRange([string[]](Get-SeedsT3d $rows $tiles $pos $n))
            $expect += [pscustomobject]@{ Class = 'XComMapEdTileSeeds'; Name = $n.Seeds; Mesh = $null; Pos = $pos }
            [IO.File]::WriteAllText($seedMap, $s.MapName)
            # Ladders are moved as themselves; their baked pathing links (F-30) go with them at deploy. Doors' don't:
            # the rebuild makes a moved door's kick links from its new interaction points, and moved baked links on
            # top made a soldier kick twice (EXP-07 run 18). A copier with bCopyLadders copies its ladders instead,
            # and the base map's ladder keeps its links where it stands.
            $rowsInv = Get-InventoryRows $s.MapName $s
            $moves = foreach ($c in @($s.Objects | Where-Object { $_.Type -eq 'copy' -and -not $_.Poses -and -not (@($_.Extra) -contains 'bCopyLadders=True') })) {
                foreach ($f in $c.From) {
                    $r = $rowsInv[$f]
                    if ($r -and $r.class -eq 'XComLadder') {
                        ($f, ($c.Pivot -join ' '), ($c.Pos -join ' '), $c.YawDeg) -join "`t"
                    }
                }
            }
            if ($moves) {
                [IO.File]::WriteAllLines($seedLinks, [string[]]@($moves))
                Say "  links: deploy moves the baked pathing links of $(@($moves).Count) moved piece(s) with them: $((@($moves) | ForEach-Object { ($_ -split "`t")[0] }) -join ' ')"
            }
            if ($s.SeedExternally) {
                if ($moves -or $bakes.Count) { throw 'map.seedExternally: moved ladders and baked actors change the map itself; ship it with map.shipAs instead' }
                [IO.File]::WriteAllText($seedExtFile, "The map that streams $($s.Name) is shipped by another tool, which applies seed-plan-built.tsv ($tiles tiles).")
                Say "  seeds: $($n.Seeds) rebuilds the $($rows.Count) planned box(es) at load; deploy leaves their $tiles tiles to the tool that ships $($s.MapName)'s variant (map.seedExternally)"
            } else {
                Say "  seeds: $($n.Seeds) rebuilds the $($rows.Count) planned box(es) at load; deploy seeds their $tiles tiles in $($s.MapName)$(if ($s.ShipAs) { " (shipped as $($s.ShipAs))" })"
            }
        } else { Remove-Item -LiteralPath $seedPlan }
    } elseif ($s.Seed -and $placing -and -not $s.MapName) {
        Say 'WARNING: the spec has no map.name, so nothing is seeded: what it places will not block above the ground on tiles the map left empty (F-29)'
    }
    # The map to ship under its own name (map.shipAs), for deploy; build marks it as built, like the seed plan.
    $shipFile = Join-Path $wd 'ship.json'
    if ($s.ShipAs) {
        if ($s.ShipDisplay -notmatch '^[^"\r\n]+$') { throw 'map.displayName must be one line without quotes' }
        [IO.File]::WriteAllText($shipFile, ([ordered]@{ map = $s.MapName; shipAs = $s.ShipAs; displayName = $s.ShipDisplay; inRotation = $s.InRotation; timeOfDay = $s.TimeOfDay; patch = $s.Name; streamSlot = $s.StreamSlot } | ConvertTo-Json))
        $slotText = if ($s.StreamSlot -is [string]) { "a StreamingMaps slot of its own (the lowest one $($s.MapName)'s record does not use)" } else { "StreamingMaps[$($s.StreamSlot)]" }
        Say "  ship: deploy puts $($s.MapName) into the lab as $($s.ShipAs).upk$(if (Test-Path -LiteralPath $seedPlan) { ' (seeded)' } else { ' (nothing to seed)' }), with the record '$($s.ShipDisplay)' streaming $($s.Name) in $slotText and $($s.MapName)'s landing zones; $($s.MapName).upk stays as it is"
    } else { Remove-Item -LiteralPath $shipFile -ErrorAction SilentlyContinue }
    $L.Add('   End Level'); $L.Add('Begin Surface'); $L.Add('End Surface'); $L.Add('End Map')
    $text = ($L -join "`r`n") + "`r`n"
    if ($text -match '[^\x00-\x7F]') { throw 'the T3D would not be plain ASCII' }
    $t3d = Join-Path $wd "$($s.Name)-add.t3d"
    [IO.File]::WriteAllText($t3d, $text, [Text.Encoding]::ASCII)
    Done "t3d: $t3d ($($expect.Count) actors, suffix $base, $($text.Length) bytes)"
    [pscustomobject]@{ T3d = $t3d; Expect = $expect; Taken = $taken; Lead = $lead }
}

# ---------------------------------------------------------------- editor
function Get-ClipboardText { [Windows.Forms.Clipboard]::GetText() }
function Save-Clipboard {
    Add-Type -AssemblyName System.Windows.Forms
    if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') { throw 'clipboard use needs an STA thread (run with pwsh, not pwsh -MTA)' }
    $c = [Windows.Forms.Clipboard]
    $script:clip = if ($c::ContainsText()) { @{ Kind = 'text'; Data = $c::GetText() } }
                   elseif ($c::ContainsImage()) { @{ Kind = 'image'; Data = $c::GetImage() } }
                   elseif ($c::ContainsFileDropList()) { @{ Kind = 'files'; Data = $c::GetFileDropList() } }
                   else { @{ Kind = 'empty' } }
    Say "saved the clipboard ($($script:clip.Kind))"
}
function Restore-Clipboard {
    if (-not $script:clip) { return }
    $c = [Windows.Forms.Clipboard]
    switch ($script:clip.Kind) {
        'text' { $c::SetText($script:clip.Data) }
        'image' { $c::SetImage($script:clip.Data) }
        'files' { $c::SetFileDropList($script:clip.Data) }
        default { $c::Clear() }
    }
    $ok = ($script:clip.Kind -ne 'text') -or ($c::GetText() -ceq $script:clip.Data)
    Say "put the clipboard back ($($script:clip.Kind)$(if (-not $ok) { ', TEXT DIFFERS' }))"
    $script:clip = $null
}
function Stop-MyEditor {
    foreach ($id in $script:editorPids) {
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p -and -not $p.HasExited) { $p.Kill(); $null = $p.WaitForExit(15000); Say "closed the editor (pid $id)" }
    }
    $script:editorPids = @()
}
# Types commands into the editor's command box by window messages, like tools\lab\udk_editor_cmd.ps1, but presses
# Enter with WM_KEYDOWN/WM_KEYUP only. udk_editor_cmd.ps1 also posts a WM_CHAR, and the editor's own message loop
# makes another one from the key-down; a slow command such as MAP IMPORTADD pumps messages while it runs, so the
# second Enter re-runs it (tested: two imports with both, one with either alone).
function Send-EditorCommands([string[]]$Commands, [int]$Wait = 2) {
    if (-not ('PatchToolCommandBox' -as [type])) {
        Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Threading;
public static class PatchToolCommandBox {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect r);
  struct Rect { public int L, T, R, B; }
  static string Cls(IntPtr h) { var s = new StringBuilder(64); GetClassName(h, s, 64); return s.ToString(); }
  // The command box is the lowest wide Edit inside a ComboBox of the main window.
  public static IntPtr Find(IntPtr main) {
    IntPtr best = IntPtr.Zero; int bestTop = int.MinValue;
    EnumChildWindows(main, (h, l) => { Rect r; GetWindowRect(h, out r);
      if (Cls(h) == "Edit" && Cls(GetParent(h)) == "ComboBox" && r.R - r.L > 200 && r.T > bestTop) { best = h; bestTop = r.T; } return true; }, IntPtr.Zero);
    return best;
  }
  public static void Run(IntPtr edit, string cmd) {
    SendMessage(edit, 0x000C, IntPtr.Zero, cmd);                                   // WM_SETTEXT
    Thread.Sleep(100);
    PostMessage(edit, 0x0100, (IntPtr)0x0D, (IntPtr)0x001C0001);                   // WM_KEYDOWN Enter
    PostMessage(edit, 0x0101, (IntPtr)0x0D, unchecked((IntPtr)(int)0xC01C0001));   // WM_KEYUP
  }
}
'@
    }
    $edit = [IntPtr]::Zero
    for ($try = 1; $edit -eq [IntPtr]::Zero; $try++) {
        $p = Get-Process -Id $script:editorPids -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' } | Select-Object -First 1
        if ($p) { $edit = [PatchToolCommandBox]::Find($p.MainWindowHandle) }
        if ($edit -eq [IntPtr]::Zero) { if ($try -ge 15) { throw 'the editor command box was not found in 30 s' }; Start-Sleep -Seconds 2 }
    }
    $n0 = @(Get-Content -LiteralPath $launchLog).Count
    foreach ($c in $Commands) { [PatchToolCommandBox]::Run($edit, $c); Start-Sleep -Seconds $Wait }
    @(Get-Content -LiteralPath $launchLog | Select-Object -Skip $n0)
}
function Step-Build($s, $plan) {
    $wd = Join-Path $Work $s.Name
    $udkFile = Join-Path $patchDir "$($s.Name).udk"
    if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { throw 'a UDK process is already running (not started by this tool); close it first' }
    $same = @(Get-ChildItem -LiteralPath (Join-Path $Udk 'UDKGame\Content') -Recurse -File | Where-Object { $_.BaseName -ieq $s.Name -and $_.FullName -ne $udkFile })
    if ($same) { throw "another package already has the name $($s.Name): $($same[0].FullName)" }
    if (Test-Path -LiteralPath $udkFile) {
        if (-not $Force) { throw "$udkFile already exists; pass -Force to rebuild it (it is backed up first)" }
        Say "backed up the old $($s.Name).udk to $(Backup $udkFile (Join-Path $wd 'backups'))"
        Remove-Item -LiteralPath $udkFile
    }
    $baseLen = 0
    if ($s.BasePath) { Copy-Item -LiteralPath $s.BasePath $udkFile; $baseLen = (Get-Item $udkFile).Length; Say "copied base $($s.BasePath) ($baseLen bytes) to $udkFile" }

    $global:LASTEXITCODE = 0
    $mapArg = if ($s.BasePath) { $s.Name } else { '' }
    # Off the user's desktop DirectX 9 finds no hardware, so the editor runs with DirectX 11 there.
    $dx11 = $desktop -ne 'Default'
    Say "opening the editor on desktop $desktop$(if ($dx11) { ' (DirectX 11)' })"
    & (Join-Path $lab 'udk_editor_try.ps1') -Map $mapArg -Tries 3 -Timeout $OpenTimeout -Udk $Udk -Dx11:$dx11 *>&1 | ForEach-Object { Say "  editor: $_" }
    $script:editorPids = @(Get-Process -Name UDK -ErrorAction SilentlyContinue | ForEach-Object Id)
    if ($LASTEXITCODE -ne 0 -or -not $script:editorPids) { throw 'the editor did not open' }
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Get-Process -Id $script:editorPids -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' })) {
        if ((Get-Date) -gt $deadline) { throw 'the editor window did not appear' }
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 3
    Say "editor open (pid $($script:editorPids -join ', '))"

    $sentinel = "patchtool-$stamp"
    Save-Clipboard
    try {
        [Windows.Forms.Clipboard]::SetText($sentinel)
        if (-not $s.BasePath) {
            # With no map the editor opens Template_MidDay (floor, sky sphere, light, fog, PlayerStart, cube): clear it.
            $del = Send-EditorCommands @('ACTOR SELECT ALL', 'DELETE') 2
            Say "cleared the editor's template map ($(@($del | Where-Object { $_ -match 'Cmd: DELETE' }).Count) DELETE run)"
        }
        $out = Send-EditorCommands @("MAP IMPORTADD FILE=`"$($plan.T3d)`"") 3
        $out | ForEach-Object { Say "  log: $_" }
        $runs = @($out | Where-Object { $_ -match 'Cmd: MAP IMPORTADD' }).Count
        if ($runs -ne 1) { throw "the import ran $runs times (log lines above)" }
        # Normal for T3D brushes: the component names the Model before the Brush block defines it.
        $issues = @($out | Where-Object { $_ -match 'error|warning|fail|unresolved|can''t|cannot' -and
            $_ -notmatch "Model'Model_\d+'" -and $_ -notmatch 'BuildSimpleBrushCollision: BrushComponent with no Owner' })
        if ($issues) { Say "WARNING: the import logged $($issues.Count) unexpected line(s), see above" }
        $null = Send-EditorCommands @('ACTOR SELECT ALL', 'EDIT COPY') 1
        $deadline = (Get-Date).AddSeconds(60)
        do {
            Start-Sleep -Milliseconds 500
            $txt = Get-ClipboardText
            if ((Get-Date) -gt $deadline) { throw 'EDIT COPY put nothing on the clipboard within 60 s' }
        } until ($txt -and $txt -ne $sentinel -and $txt -match '^\s*Begin Map')
    } finally { Restore-Clipboard }
    $copyFile = Join-Path $wd "editcopy-$stamp.t3d"
    [IO.File]::WriteAllText($copyFile, $txt, [Text.Encoding]::ASCII)

    # Every expected actor under its own name, class, mesh and location; no other new XCOM actor (a second import).
    $blocks = @{}
    foreach ($m in [regex]::Matches($txt, '(?ms)^\s*Begin Actor Class=(\S+) Name=(\S+) .*?^\s*End Actor')) { $blocks[$m.Groups[2].Value] = @($m.Groups[1].Value, $m.Value) }
    foreach ($e in $plan.Expect) {
        $blk = $blocks[$e.Name]
        if (-not $blk) { throw "EDIT COPY does not list $($e.Name) (copy saved to $copyFile)" }
        if ($blk[0] -ne $e.Class) { throw "$($e.Name) is a $($blk[0]), expected $($e.Class)" }
        if ($e.Mesh -and $blk[1] -notmatch [regex]::Escape("StaticMesh=StaticMesh'$($e.Mesh)'")) { throw "$($e.Name) does not have mesh $($e.Mesh)" }
        $lm = [regex]::Match($blk[1], '(?m)^ {9}Location=\(X=([-\d.]+),Y=([-\d.]+),Z=([-\d.]+)\)')
        if (-not $lm.Success) { throw "$($e.Name) has no Location in EDIT COPY" }
        $got = 1..3 | ForEach-Object { [double]::Parse($lm.Groups[$_].Value, $inv) }
        for ($k = 0; $k -lt 3; $k++) { if ([math]::Abs($got[$k] - $e.Pos[$k]) -gt 0.01) { throw "$($e.Name) is at ($($got -join ', ')), expected ($($e.Pos -join ', '))" } }
        if ($e.PSObject.Properties['Refs']) {
            foreach ($r in $e.Refs) { if ($blk[1] -notmatch "XComFloorVolume'([^']*\.)?$r'") { throw "$($e.Name) does not list its floor volume $r in EDIT COPY (copy saved to $copyFile)" } }
        }
    }
    $expNames = @($plan.Expect | ForEach-Object Name)
    $extra = @($blocks.Keys | Where-Object { $blocks[$_][0] -in 'XComLevelActor', 'XComLadder', 'XComRebuildWorldDataVolume', 'XComMapEdBorrowedMesh', 'XComMapEdSpawner', 'XComMapEdHider', 'XComMapEdCopier', 'XComMapEdTileSeeds', 'XComMapEdSun', 'XComMapEdPhoto', 'XComMapEdIntro', 'XComBuildingVolume', 'XComFloorVolume' -and $_ -notin $expNames -and -not $plan.Taken.Contains($_) })
    if ($extra) { throw "EDIT COPY lists XCOM actors that are neither in the base nor in the spec: $($extra -join ', ')" }
    # On an empty map only the spec's actors may be left, and the leading Note the T3D puts first.
    $left = @($blocks.Keys | Where-Object { -not $s.BasePath -and $_ -notin $expNames -and $_ -ne $plan.Lead })
    if ($left) { throw "the empty map still holds actors besides the spec's: $($left -join ', ')" }
    Done "import: EDIT COPY lists all $($expNames.Count) new actors ($($expNames -join ', ')) with the right class, mesh and location; $($blocks.Count) actors in all; copy kept as $copyFile"

    $before = Get-Date
    $global:LASTEXITCODE = 0
    & (Join-Path $lab 'udk_editor_saveas.ps1') -File $udkFile -Timeout $SaveTimeout *>&1 | ForEach-Object { Say "  save: $_" }
    if ($LASTEXITCODE -ne 0) { throw 'Save As failed or timed out' }
    $i = Get-Item -LiteralPath $udkFile
    if ($i.LastWriteTime -lt $before) { throw "$udkFile was not rewritten" }
    if ($i.Length -le $baseLen) { throw "$udkFile did not grow ($($i.Length) bytes, base $baseLen)" }
    $saved = Get-PackageObjectNames $udkFile
    $miss = @($expNames | Where-Object { -not $saved.Contains($_) })
    if ($miss) { throw "the saved package lacks $($miss -join ', ')" }
    Done "save: $udkFile $($i.Length) bytes (base $baseLen, +$($i.Length - $baseLen)); its export table has all new actors"
    # The seed plan that went into this build is the one deploy seeds the base map with.
    foreach ($f in 'seed-plan.tsv', 'seed-plan.map', 'seed-links.tsv', 'seed-bakes.tsv', 'seed-external.txt') {
        $from = Join-Path $wd $f; $to = Join-Path $wd ($f -replace '^seed-(plan|links|bakes|external)', 'seed-$1-built')
        if (Test-Path -LiteralPath $from) { Copy-Item -LiteralPath $from $to -Force } else { Remove-Item -LiteralPath $to -ErrorAction SilentlyContinue }
    }
    $from = Join-Path $wd 'ship.json'; $to = Join-Path $wd 'ship-built.json'
    if (Test-Path -LiteralPath $from) { Copy-Item -LiteralPath $from $to -Force } else { Remove-Item -LiteralPath $to -ErrorAction SilentlyContinue }
    Stop-MyEditor
    Copy-Item -LiteralPath $launchLog (Join-Path $wd "logs\editor-$stamp.log")
}

# ---------------------------------------------------------------- cook
function Stop-Tree([int]$Id) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$Id" | ForEach-Object { Stop-Tree $_.ProcessId }
    Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue
}
function Step-Cook([string]$name) {
    $wd = Join-Path $Work $name
    $src = Join-Path $patchDir "$name.udk"
    if (-not (Test-Path -LiteralPath $src)) { throw "no source map $src; run build first" }
    if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { throw 'a UDK process is running; close it before cooking' }
    $cooked = Join-Path $cookedDir "$name.udk"
    $out = Join-Path $wd "logs\cook-$stamp.log"
    $t0 = Get-Date
    if ((Test-Path -LiteralPath $hqSound) -and -not (Test-Path -LiteralPath $hqSoundKept)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $hqSoundKept) | Out-Null
        Copy-Item -LiteralPath $hqSound $hqSoundKept
    }
    Say "cooking $name (timeout $CookTimeout s)"
    $p = Start-Process -FilePath (Join-Path $Udk 'Binaries\Win32\UDK.com') -WorkingDirectory (Join-Path $Udk 'Binaries\Win32') `
        -ArgumentList @('CookPackages', '-platform=PC', $name, '-unattended', '-nopause', '-LanguageForCooking=INT') `
        -RedirectStandardOutput $out -RedirectStandardError "$out.err" -NoNewWindow -PassThru
    if (-not $p.WaitForExit($CookTimeout * 1000)) { Stop-Tree $p.Id; throw "the cook did not finish in $CookTimeout s (log $out)" }
    $lines = @(Get-Content -LiteralPath $out)
    if (-not (Test-Path -LiteralPath $hqSound)) {
        $from = if (Test-Path -LiteralPath $hqSoundKept) { $hqSoundKept } else { $hqSoundSource }
        if (-not $from -or -not (Test-Path -LiteralPath $from)) { throw "the cook deleted $hqSound and there is no copy to put back ($hqSoundKept)" }
        Copy-Item -LiteralPath $from $hqSound
        Say "the cook deleted CookedPC\HQSound_MCMusic_SF.upk; restored it from $from"
    }
    $at = [Array]::FindLastIndex([string[]]$lines, [Predicate[string]] { param($l) $l -match '^Warning/Error Summary' })
    $result = $lines | Where-Object { $_ -match '^(Success|Failure) - ' } | Select-Object -Last 1
    if ($at -lt 0 -or -not $result) { throw "the cook log has no summary (exit $($p.ExitCode)); see $out" }
    $tail = $lines[$at..($lines.Count - 1)]
    $errs = @($tail | Where-Object { $_ -match '^\s*Error' -and $_ -notmatch 'HQSound_MCMusic' })
    $known = @($tail | Where-Object { $_ -match '^\s*Error' -and $_ -match 'HQSound_MCMusic' }).Count
    $errs | ForEach-Object { Say "  cook error: $_" }
    if ($errs) { throw "the cook reported $($errs.Count) error(s) besides the known HQSound_MCMusic one; see $out" }
    $count = if ($result -match '(\d+) error') { [int]$Matches[1] } else { 0 }
    if ($count -gt $known) { throw "the cook counts $count errors but only $known are the known HQSound_MCMusic one; see $out" }
    # A single-threaded cook logs "Cooking [Seekfree] <name>", a multithreaded one "Job[n] <name> done in ...".
    $rxName = [regex]::Escape($name)
    $cookedIt = [bool]($lines | Where-Object { $_ -match "^Cooking \[Seekfree\] $rxName\s*$" -or $_ -match "^Job\[\d+\] $rxName done" })
    if (-not (Test-Path -LiteralPath $cooked)) { throw "no cooked file $cooked after the cook; see $out" }
    $ci = Get-Item -LiteralPath $cooked
    if ($cookedIt) {
        if ($ci.LastWriteTime -lt $t0.AddSeconds(-2)) { throw "the cook says it cooked $name but $cooked is older than the cook" }
        $how = 'cooked'
    } else {
        # The cooker skips a map whose cooked file is newer than its source (incremental cook).
        if ($ci.LastWriteTime -lt (Get-Item -LiteralPath $src).LastWriteTime) { throw "the cook skipped $name and $cooked is older than its source; see $out" }
        $how = 'already up to date (the cooker skipped it; the cooked file is newer than the source)'
    }
    Done "cook: $cooked $($ci.Length) bytes, $how, $([int]((Get-Date) - $t0).TotalSeconds) s; '$result' (only the known HQSound_MCMusic error); log $out"
}

# ---------------------------------------------------------------- deploy
function Assert-LabGame {
    if (-not $Game) { throw 'no game folder: pass -Game, or set the lwr setting (python tools/viewer/viewer.py settings --lwr <folder>)' }
    $st = (& (Join-Path $lab 'switch_install.ps1') status *>&1 | Out-String).Trim()
    if ($st -notmatch '(^|\s)active=lab(\s|$)') { throw "switch_install status says '$st', not active=lab; not touching the game folder" }
    if (-not (Test-Path -LiteralPath (Join-Path $Game 'XComLab-copy.txt'))) { throw "$Game has no XComLab-copy.txt marker" }
    if (Get-Process | Where-Object { $_.Path -and ($_.Path -like "$Game\*" -or $_.Path -like '*XComLabWrapper*') }) { throw 'XCOM is running; quit it first' }
}
function Step-Deploy([string]$name) {
    $wd = Join-Path $Work $name
    Assert-LabGame
    $src = Join-Path $cookedDir "$name.udk"
    if (-not (Test-Path -LiteralPath $src)) { throw "no cooked map $src; run cook first" }
    $srcUdk = Join-Path $patchDir "$name.udk"
    if ((Test-Path -LiteralPath $srcUdk) -and (Get-Item -LiteralPath $srcUdk).LastWriteTime -gt (Get-Item -LiteralPath $src).LastWriteTime) { Say "WARNING: $srcUdk is newer than its cook" }
    $dst = Join-Path $gameCooked "$name.upk"
    $mine = (Test-Path -LiteralPath $ledger) -and (@(Get-Content -LiteralPath $ledger) -contains $name)
    if (Test-Path -LiteralPath $dst) {
        if (-not $mine -and -not $Force) { throw "$dst exists and was not deployed by this tool; pass -Force to replace it (it is backed up first)" }
        Say "backed up the old $name.upk to $(Backup $dst (Join-Path $wd 'backups'))"
    }
    Copy-Item -LiteralPath $src $dst -Force
    if ((Get-FileHash -LiteralPath $src).Hash -ne (Get-FileHash -LiteralPath $dst).Hash) { throw "the copy at $dst differs from $src" }
    if (-not $mine) { Add-Content -LiteralPath $ledger -Value $name }
    Done "deploy: $dst $((Get-Item -LiteralPath $dst).Length) bytes (same SHA-256 as the cook)"
    Step-Seed $name
}

# ---------------------------------------------------------------- tile seeds (F-29)
function Get-Python {
    $p = Get-Command python -ErrorAction SilentlyContinue
    if (-not $p) { throw 'no python on PATH (needed for tools\upk\seed_map.py)' }
    $p.Source
}
# The base map as shipped, kept in <Work>\maps. Taken once from the LWR install, read only.
function Get-OriginalMap([string]$MapName) {
    $orig = Join-Path $mapsDir "$MapName.upk"
    if (Test-Path -LiteralPath $orig) { return $orig }
    # -Lwr names the install (the editor's settings); otherwise switch_install says where it is in the lab
    $lwr = if ($Lwr) { $Lwr } else {
        if (-not $Game) { throw 'no LWR install: pass -Lwr, or set the lwr setting (python tools/viewer/viewer.py settings --lwr <folder>)' }
        $st = (& (Join-Path $lab 'switch_install.ps1') status *>&1 | Out-String).Trim()
        if ($st -match '(^|\s)active=lwr(\s|$)') { $Game }
        elseif ($st -match '(^|\s)parked\.LWR=lwr(\s|$)') { Join-Path (Split-Path $Game) 'XCom-Enemy-Unknown.LWR' }
        else { throw "can't find the LWR install from switch_install status '$st'" }
    }
    $src = Join-Path $lwr "XEW\XComGame\CookedPCConsole\$MapName.upk"
    if (-not (Test-Path -LiteralPath $src)) { throw "the LWR install has no $src" }
    New-Item -ItemType Directory -Force -Path $mapsDir | Out-Null
    Copy-Item -LiteralPath $src "$orig.part"
    if ((Get-FileHash -LiteralPath $src).Hash -ne (Get-FileHash -LiteralPath "$orig.part").Hash) { throw "the copy of $src differs from it" }
    Move-Item -LiteralPath "$orig.part" $orig
    Say "kept the original $MapName.upk from the LWR install (read only) as $orig"
    $orig
}
function Get-SeedEntries([string]$MapName) {
    if (-not (Test-Path -LiteralPath $seedLedger)) { return @() }
    @(Get-Content -LiteralPath $seedLedger | Where-Object { $_ } | ForEach-Object {
        $f = $_ -split "`t"
        [pscustomobject]@{ Time = $f[0]; Map = $f[1]; Patch = $f[2]; Tiles = $f[3]; Hash = $f[4] } } |
        Where-Object { -not $MapName -or $_.Map -ieq $MapName })
}
# Puts $file into the lab as <Target>.upk. For the base map itself (Target = MapName), only if the lab's file is the
# original or the copy this tool last wrote. For a map shipped under its own name (map.shipAs), only if the lab has
# no such file yet or has the copy this tool last wrote. -Force replaces any other file, after a backup.
function Set-LabMap([string]$MapName, [string]$file, [string]$patch, [string]$tiles, [string]$Target = '') {
    if (-not $Target) { $Target = $MapName }
    $labMap = Join-Path $gameCooked "$Target.upk"
    $last = @(Get-SeedEntries $Target) | Select-Object -Last 1
    if ($Target -ieq $MapName) {
        if (-not (Test-Path -LiteralPath $labMap)) { throw "the lab copy has no $labMap" }
        $cur = (Get-FileHash -LiteralPath $labMap).Hash
        $orig = (Get-FileHash -LiteralPath (Get-OriginalMap $MapName)).Hash
        if ($cur -ne $orig -and -not ($last -and $cur -eq $last.Hash)) {
            if (-not $Force) { throw "$labMap is neither the original nor the copy patchtool last seeded; pass -Force to replace it (it is backed up first)" }
            Say "backed up the lab's $Target.upk to $(Backup $labMap $backups)"
        }
    } elseif (Test-Path -LiteralPath $labMap) {
        $cur = (Get-FileHash -LiteralPath $labMap).Hash
        if (-not ($last -and $cur -eq $last.Hash)) {
            if (-not $Force) { throw "$labMap is not the copy patchtool last shipped there; pass -Force to replace it (it is backed up first)" }
            Say "backed up the lab's $Target.upk to $(Backup $labMap $backups)"
        }
    }
    Copy-Item -LiteralPath $file $labMap -Force
    $new = (Get-FileHash -LiteralPath $labMap).Hash
    if ($new -ne (Get-FileHash -LiteralPath $file).Hash) { throw "the copy at $labMap differs from $file" }
    Add-Content -LiteralPath $seedLedger -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Target, $patch, $tiles, $new -join "`t")
    $labMap
}
function Get-ShipInfo([string]$name) {
    $f = Join-Path (Join-Path $Work $name) 'ship-built.json'
    if (Test-Path -LiteralPath $f) { Get-Content -LiteralPath $f -Raw | ConvertFrom-Json } else { $null }
}
# Edits a lab config file through $Edit (a script block from the file's lines to its new lines), only by inserting or
# replacing whole lines; backs it up first and checks the result. Returns a summary, or '' when nothing changed.
function Edit-LabIni([string]$Path, [scriptblock]$Edit) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { throw "$Path starts with a UTF-8 BOM; not editing it" }
    $text = $latin1.GetString($bytes)
    $nl = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $orig = [string[]]($text -split [regex]::Escape($nl))
    $res = & $Edit ([Collections.Generic.List[string]]::new($orig))
    if (-not $res -or -not $res.Changed) { return '' }
    $lines = [string[]]$res.Lines
    $bak = Backup $Path $backups
    # Build the whole text first, then write it in one go (an INI opened for writing early came out empty in EXP-07).
    $out = $latin1.GetBytes($lines -join $nl)
    [IO.File]::WriteAllBytes($Path, $out)
    $check = $latin1.GetString([IO.File]::ReadAllBytes($Path)) -split [regex]::Escape($nl)
    $kept = @($orig | Where-Object { $_ -notin $res.Removed })
    $left = @($check | Where-Object { $_ -notin $res.Added })
    if ($check.Count -ne $lines.Count -or ($kept -join "`n") -cne ($left -join "`n")) { throw "$Path did not come out as planned; restore it from $bak" }
    "$($res.Summary) (backup $bak)"
}
# The StreamingMaps entries of a DefaultMaps.ini record line, in the order written: Slot, MapName, and where the name
# stands in the line (Index, Length, Quoted). LWR's records write MapName quoted or bare, with or without spaces, with
# sparse slots (URB_Bar: 0, 1, 5) and out of order (lines 13 and 124: 0, 5, 2).
function Get-StreamSlots([string]$Record) {
    $all = [regex]::Matches($Record, 'StreamingMaps\[\s*(\d+)\s*\]\s*=')
    $named = [regex]::Matches($Record, 'StreamingMaps\[\s*(\d+)\s*\]\s*=\s*\(\s*MapName\s*=\s*(?:"([^"]*)"|([^\s",()]*))')
    if ($named.Count -ne $all.Count) { throw "the record has $($all.Count) StreamingMaps entries but only $($named.Count) start with a MapName" }
    foreach ($e in $named) {
        $g = if ($e.Groups[2].Success) { $e.Groups[2] } else { $e.Groups[3] }
        [pscustomobject]@{ Slot = [int]$e.Groups[1].Value; MapName = $g.Value; Index = $g.Index; Length = $g.Length; Quoted = $e.Groups[2].Success }
    }
}
# The record of a map shipped under its own name (map.shipAs), made from the base map's record line: Name and
# DisplayName, bInRotation, TimeOfDay (when given), and the patch in StreamingMaps[Slot]. Slot is a number or 'free':
# the lowest slot the base record does not use (an entry with an empty MapName counts as used, so 'free' never
# replaces anything). A slot the record has gets the patch as its MapName (slot 1 replaces patch_bar in URB_Bar's
# record, as before E0); a slot it lacks is added at the end of the record, written as the stream step writes it.
# Pure: reads and writes no file. Returns Record (the new line), Slot, Old (the MapName replaced) and Added.
function Get-ShipRecord([string]$Record, [string]$Map, [string]$To, [string]$DisplayName, [string]$Patch, $Slot, [bool]$InRotation = $false, [string]$TimeOfDay = '') {
    # The first match only, ignoring case as the record lookup does. (Before E0 this passed 1 to [regex]::Replace,
    # where it means RegexOptions.IgnoreCase, not a count; a record has each of these once, so the result is the same.)
    function Sub1([string]$Text, [string]$Pattern, [string]$By) { [regex]::new($Pattern, 'IgnoreCase').Replace($Text, $By.Replace('$', '$$'), 1) }
    $Slot = Get-StreamSlotSpec $Slot
    $rx = '(?<![A-Za-z])Name="' + [regex]::Escape($Map) + '"\s*,'
    if ($Record -notmatch $rx) { throw "the record has no Name=`"$Map`"" }
    $rec = Sub1 $Record $rx "Name=`"$To`","
    $rec = Sub1 $rec 'DisplayName="[^"]*"' "DisplayName=`"$DisplayName`""
    $slots = @(Get-StreamSlots $rec)
    $twice = @($slots | Group-Object Slot | Where-Object Count -gt 1 | ForEach-Object Name)
    if ($twice) { throw "$Map's record has StreamingMaps[$($twice -join '], [')] more than once" }
    $used = @($slots | ForEach-Object Slot)
    $k = $Slot
    if ($Slot -is [string]) { $k = 0; while ($used -contains $k) { $k++ } }
    $hit = @($slots | Where-Object Slot -eq $k)
    if ($hit) {
        $old = $hit[0].MapName; $added = $false
        $rec = $rec.Substring(0, $hit[0].Index) + $Patch + $rec.Substring($hit[0].Index + $hit[0].Length)
    } else {
        # The bracket that closes Maps=( (quoted text skipped); only blanks may follow it.
        $depth = 0; $close = -1; $quoted = $false
        for ($i = $rec.IndexOf('('); $i -ge 0 -and $i -lt $rec.Length; $i++) {
            $c = $rec[$i]
            if ($c -eq '"') { $quoted = -not $quoted }
            elseif (-not $quoted -and $c -eq '(') { $depth++ }
            elseif (-not $quoted -and $c -eq ')') { $depth--; if ($depth -eq 0) { $close = $i; break } }
        }
        if ($close -lt 0 -or $rec.Substring($close + 1).Trim()) { throw "can't find the end of $Map's record (its brackets don't balance, or text follows them)" }
        $head = $rec.Substring(0, $close).TrimEnd()
        $sep = if ($head.EndsWith(',')) { ' ' } else { ', ' }    # line 124 ends its last entry with a comma
        $rec = $head + $sep + "StreamingMaps[$k]=( MapName=`"$Patch`", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) " + $rec.Substring($close)
        $old = ''; $added = $true
    }
    $rec = Sub1 $rec 'bInRotation=\w+' "bInRotation=$(if ($InRotation) { 'True' } else { 'False' })"
    if ($TimeOfDay) {
        if ($rec -notmatch 'TimeOfDay=eMissionTime_\w+') { throw "$Map's record has no TimeOfDay to set" }
        $rec = Sub1 $rec 'TimeOfDay=eMissionTime_\w+' "TimeOfDay=eMissionTime_$TimeOfDay"
    }
    [pscustomobject]@{ Record = $rec; Slot = $k; Old = $old; Added = $added }
}
# map.shipAs: the base map's landing zones (LWR, DefaultLZMutator.ini) and a map record of its own (DefaultMaps.ini)
# under the new name. Both are keyed by map name (F-42).
function Set-ShipConfig($ship) {
    $map = [string]$ship.map; $to = [string]$ship.shipAs
    $slot = Opt $ship 'streamSlot' 1     # ship files written before map.streamSlot streamed the patch in slot 1
    $lzIni = Join-Path $Game 'XEW\XComGame\Config\DefaultLZMutator.ini'
    $r = Edit-LabIni $lzIni {
        param($L)
        $src = @(for ($k = 0; $k -lt $L.Count; $k++) { if ($L[$k] -notmatch '^\s*;' -and $L[$k].Contains("MapName=`"$map`",")) { $k } })
        if (-not $src) { Say "WARNING: DefaultLZMutator.ini has no landing zones for $map; none written for $to"; return }
        $want = @($src | ForEach-Object { $L[$_].Replace("MapName=`"$map`",", "MapName=`"$to`",") })
        $have = @($L | Where-Object { $_ -notmatch '^\s*;' -and $_.Contains("MapName=`"$to`",") })
        if ($have.Count) {
            if (($have -join "`n") -cne ($want -join "`n")) { Say "WARNING: DefaultLZMutator.ini already has $($have.Count) landing zone(s) for $to that differ from $map's; left as they are" }
            return
        }
        $add = @(";$to locations = copy of $map (patchtool $($ship.patch), $(Get-Date -Format 'd MMM yyyy'))") + $want
        $L.InsertRange($src[-1] + 1, [string[]]$add)
        [pscustomobject]@{ Changed = $true; Lines = $L; Added = $add; Removed = @(); Summary = "DefaultLZMutator.ini: $($want.Count) landing zone(s) of $map copied for $to" }
    }
    if ($r) { Done "ship: $r" } else { Say "  ship: DefaultLZMutator.ini already has $to's landing zones" }
    $r = Edit-LabIni $gameIni {
        param($L)
        $rx = '(?<![A-Za-z])Name="' + [regex]::Escape($map) + '"\s*,'
        $src = @(for ($k = 0; $k -lt $L.Count; $k++) { if ($L[$k] -match '^\s*Maps=\(' -and $L[$k] -match $rx) { $k } })
        # A test slot pointed at the base map itself has the base map's Name too (EXP-14 run 1b); the line -Stream
        # points is never the base map's own record. (On 6 November the Temple variant's record was made from the
        # test slot this way: map family URB_Bar, an abduction.)
        if ($Stream) { $src = @($src | Where-Object { -not $L[$_].Contains("DisplayName=`"$Stream`"") }) }
        if ($src.Count -lt 1) { throw "DefaultMaps.ini has no record with Name=`"$map`"$(if ($Stream) { " besides the one -Stream points" })" }
        $new = Get-ShipRecord $L[$src[0]] $map $to ([string]$ship.displayName) ([string]$ship.patch) $slot ([bool]$ship.inRotation) ([string]$ship.timeOfDay)
        $rec = $new.Record
        $how = if ($new.Added) { "StreamingMaps[$($new.Slot)] added for $($ship.patch)" } else { "StreamingMaps[$($new.Slot)] $($new.Old) -> $($ship.patch)" }
        # T-08: Temple Ship's slot 1 is its arrival cinematic, not a patch.
        if (-not $new.Added -and $new.Old -notmatch '^patch_') { Say "WARNING: StreamingMaps[$($new.Slot)] of $map's record streams '$($new.Old)', not a patch; $to's record streams $($ship.patch) there instead (map.streamSlot `"free`" would keep it)" }
        $key = "DisplayName=`"$($ship.displayName)`""
        $own = @(for ($k = 0; $k -lt $L.Count; $k++) { if ($L[$k] -notmatch '^\s*;' -and $L[$k].Contains($key)) { $k } })
        if ($own.Count -gt 1) { throw "DefaultMaps.ini has $($own.Count) records named '$($ship.displayName)'" }
        if ($own.Count -eq 1) {
            if ($L[$own[0]] -ceq $rec) { return }
            $old = $L[$own[0]]; $L[$own[0]] = $rec
            return [pscustomobject]@{ Changed = $true; Lines = $L; Added = @($rec); Removed = @($old); Summary = "DefaultMaps.ini line $($own[0] + 1): $to's record updated ($how)" }
        }
        $add = @("; $to`: $map's record under its own name, streaming $($ship.patch) in StreamingMaps[$($new.Slot)] (patchtool, $(Get-Date -Format 'd MMM yyyy'))", $rec)
        $L.InsertRange($src[0] + 1, [string[]]$add)
        [pscustomobject]@{ Changed = $true; Lines = $L; Added = $add; Removed = @(); Summary = "DefaultMaps.ini line $($src[0] + 3): a record for $to ('$($ship.displayName)', bInRotation $([bool]$ship.inRotation), $how)" }
    }
    if ($r) { Done "ship: $r" } else { Say "  ship: DefaultMaps.ini already has $to's record" }
}
function Step-Seed([string]$name) {
    $wd = Join-Path $Work $name
    $plan = Join-Path $wd 'seed-plan-built.tsv'; $mapFile = Join-Path $wd 'seed-plan-built.map'
    $bakesFile = Join-Path $wd 'seed-bakes-built.tsv'
    $ship = Get-ShipInfo $name
    if (Test-Path -LiteralPath (Join-Path $wd 'seed-external-built.txt')) {
        # map.seedExternally: another tool ships the map and applies the plan. A lab map seeded for this patch before
        # goes back to the original.
        foreach ($m in @(Get-SeedEntries '' | Group-Object Map | ForEach-Object { $_.Group[-1] } | Where-Object { $_.Patch -eq $name })) {
            $null = Set-LabMap $m.Map (Get-OriginalMap $m.Map) '(original)' 0
            Done "seed: $name is seeded by the tool that ships its map now; put the original $($m.Map).upk back"
        }
        Done "seed: no lab map seeded; the map's shipper applies $plan (map.seedExternally)"
        return
    }
    $seeding = (Test-Path -LiteralPath $plan) -or (Test-Path -LiteralPath $bakesFile)
    if (-not $seeding -and -not $ship) {
        # Nothing to seed. A map still seeded for this patch goes back to the original.
        foreach ($m in @(Get-SeedEntries '' | Group-Object Map | ForEach-Object { $_.Group[-1] } | Where-Object { $_.Patch -eq $name })) {
            $null = Set-LabMap $m.Map (Get-OriginalMap $m.Map) '(original)' 0
            Done "seed: $name seeds nothing now; put the original $($m.Map).upk back"
        }
        return
    }
    $mapName = if ($seeding) { [IO.File]::ReadAllText($mapFile).Trim() } else { [string]$ship.map }
    if ($ship -and $ship.map -ine $mapName) { throw "the seed plan is for $mapName but the patch ships a copy of $($ship.map)" }
    $target = if ($ship) { [string]$ship.shipAs } else { $mapName }
    $last = @(Get-SeedEntries $target) | Select-Object -Last 1
    if ($last -and $last.Patch -notin $name, '(original)') { Say "WARNING: $target.upk was seeded for $($last.Patch); $name's seeds replace them" }
    if ($ship) {
        # A patch that ships its map under a new name no longer seeds the base map's own file: put it back.
        $old = @(Get-SeedEntries $mapName) | Select-Object -Last 1
        if ($old -and $old.Patch -eq $name) {
            $null = Set-LabMap $mapName (Get-OriginalMap $mapName) '(original)' 0
            Done "seed: $name now ships as $target; put the original $mapName.upk back"
        }
    }
    $orig = Get-OriginalMap $mapName
    $tmp = Join-Path $wd "$mapName-seeded.upk"
    $global:LASTEXITCODE = 0
    $tiles = '0'
    if (Test-Path -LiteralPath $plan) {
        $out = @(& (Get-Python) $seedTool apply $orig $tmp $plan 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -ne 0) { throw "seeding failed: $($out -join ' / ')" }
        $out | ForEach-Object { Say "  seeds: $_" }
        $tiles = if (($out -join "`n") -match 'seeded (\d+) of') { $Matches[1] } else { '?' }
    } else { Copy-Item -LiteralPath $orig $tmp -Force }
    $links = Join-Path $wd 'seed-links-built.tsv'
    $nMoved = 0
    if (Test-Path -LiteralPath $links) {
        foreach ($line in [IO.File]::ReadAllLines($links)) {
            if (-not $line) { continue }
            $f = $line -split "`t"
            $next = "$tmp.links.upk"
            $global:LASTEXITCODE = 0
            $out = @(& (Get-Python) $linksTool move $tmp $next --object $f[0] --pivot ($f[1] -split ' ') --location ($f[2] -split ' ') --yaw $f[3] 2>&1 | ForEach-Object { "$_" })
            if ($LASTEXITCODE -ne 0) { throw "moving the links of $($f[0]) failed: $($out -join ' / ')" }
            $out | Where-Object { $_ -match '^moved ' } | ForEach-Object { Say "  links: $_" }
            Move-Item -LiteralPath $next $tmp -Force
            $nMoved++
        }
    }
    $nBaked = 0
    if (Test-Path -LiteralPath $bakesFile) {
        $rows = @([IO.File]::ReadAllLines($bakesFile) | Where-Object { $_ } | ForEach-Object { , ($_ -split "`t") })
        $bakeArgs = foreach ($f in $rows) { $f[0]; $f[1] -split ' '; if ($f[2] -ne '-') { $f[2] } }
        $next = "$tmp.bake.upk"
        $global:LASTEXITCODE = 0
        $out = @(& (Get-Python) $bakeTool $tmp $next @bakeArgs 2>&1 | ForEach-Object { "$_" })
        if ($LASTEXITCODE -ne 0) { throw "baking failed: $($out -join ' / ')" }
        $out | ForEach-Object { Say "  bake: $_" }
        Move-Item -LiteralPath $next $tmp -Force
        foreach ($f in $rows) {
            $nBaked++
            if ($f[3] -ne '1') { continue }
            $oldYaw = [double]::Parse($f[5], $inv)
            $turn = if ($f[2] -ne '-') { [double]::Parse($f[2], $inv) - $oldYaw } else { 0 }
            $next = "$tmp.links.upk"
            $global:LASTEXITCODE = 0
            $out = @(& (Get-Python) $linksTool move $tmp $next --object $f[0] --pivot ($f[4] -split ' ') --location ($f[1] -split ' ') --yaw $turn 2>&1 | ForEach-Object { "$_" })
            if ($LASTEXITCODE -ne 0) { throw "moving the links of $($f[0]) failed: $($out -join ' / ')" }
            $out | Where-Object { $_ -match '^moved ' } | ForEach-Object { Say "  links: $_" }
            Move-Item -LiteralPath $next $tmp -Force
        }
    }
    $labMap = Set-LabMap $mapName $tmp $name $tiles $target
    Done "seed: $labMap is the original $mapName with $tiles tiles seeded$(if ($nMoved) { ", the links of $nMoved moved piece(s) moved" })$(if ($nBaked) { ", $nBaked actor(s) baked in place" }) for $name$(if ($seeding) { " (manifest $tmp.seeded.txt)" }); ledger $seedLedger"
    if ($ship) { Set-ShipConfig $ship }
}
function Step-Unseed([string]$name) {
    Assert-LabGame
    $hits = @(Get-SeedEntries '' | Group-Object Map | ForEach-Object { $_.Group[-1] } | Where-Object { $_.Patch -eq $name })
    if (-not $hits) { Done "unseed: no map is seeded for $name"; return }
    $ship = Get-ShipInfo $name
    foreach ($m in $hits) {
        if ($ship -and $m.Map -ieq $ship.shipAs) {
            # A shipped copy has no original of its own: it becomes an unseeded copy of the base map.
            $null = Set-LabMap $ship.map (Get-OriginalMap $ship.map) '(original)' 0 $m.Map
            Done "unseed: $($m.Map).upk in the lab is now an unseeded copy of the original $($ship.map) (it was seeded for $name)"
            continue
        }
        $null = Set-LabMap $m.Map (Get-OriginalMap $m.Map) '(original)' 0
        Done "unseed: put the original $($m.Map).upk back in the lab (it was seeded for $name)"
    }
}
function Set-StreamEntry([string]$name, [string]$DisplayName, [int]$Slot) {
    Assert-LabGame
    $bytes = [IO.File]::ReadAllBytes($gameIni)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { throw "$gameIni starts with a UTF-8 BOM; not editing it" }
    $orig = $latin1.GetString($bytes) -split "`r`n"
    $lines = [string[]]$orig.Clone()
    $key = "DisplayName=`"$DisplayName`""
    $hits = @(for ($k = 0; $k -lt $lines.Count; $k++) { if ($lines[$k] -notmatch '^\s*;' -and $lines[$k].Contains($key)) { $k } })
    if ($hits.Count -ne 1) { throw "DefaultMaps.ini has $($hits.Count) uncommented lines with $key; need exactly one" }
    $n = $hits[0]; $line = $lines[$n]
    # A patch that ships its map under a new name (map.shipAs): the line loads that map too.
    $ship = Get-ShipInfo $name
    $mapNote = ''
    if ($ship) {
        $nm = [regex]::Match($line, '(?<![A-Za-z])Name="([^"]*)"')
        if (-not $nm.Success) { throw "DefaultMaps.ini line $($n + 1) has no Name=" }
        if ($nm.Groups[1].Value -cne $ship.shipAs) {
            $mapNote = ", Name $($nm.Groups[1].Value) -> $($ship.shipAs)"
            $line = $line.Substring(0, $nm.Groups[1].Index) + $ship.shipAs + $line.Substring($nm.Groups[1].Index + $nm.Groups[1].Length)
        }
        # The slot plays the map as its own record would: the same time of day.
        $tm = [regex]::Match($line, 'TimeOfDay=eMissionTime_(\w+)')
        if ($ship.timeOfDay -and $tm.Success -and $tm.Groups[1].Value -cne $ship.timeOfDay) {
            $mapNote += ", TimeOfDay $($tm.Groups[1].Value) -> $($ship.timeOfDay)"
            $line = $line.Substring(0, $tm.Groups[1].Index) + $ship.timeOfDay + $line.Substring($tm.Groups[1].Index + $tm.Groups[1].Length)
        }
    }
    $m = [regex]::Match($line, 'StreamingMaps\[' + $Slot + '\]=\(\s*MapName="([^"]*)"')
    if ($m.Success) {
        $old = $m.Groups[1].Value
        if ($old -ceq $name -and -not $mapNote) { Done "stream: DefaultMaps.ini line $($n + 1) already streams $name in StreamingMaps[$Slot]; not changed"; return }
        $new = $line.Substring(0, $m.Groups[1].Index) + $name + $line.Substring($m.Groups[1].Index + $m.Groups[1].Length)
    } else {
        $old = '(none)'
        $close = $line.LastIndexOf(')')
        $new = $line.Substring(0, $close).TrimEnd() + ", StreamingMaps[$Slot]=( MapName=`"$name`", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) " + $line.Substring($close)
    }
    $bak = Backup $gameIni $backups
    $lines[$n] = $new
    [IO.File]::WriteAllBytes($gameIni, $latin1.GetBytes($lines -join "`r`n"))
    $check = $latin1.GetString([IO.File]::ReadAllBytes($gameIni)) -split "`r`n"
    $diff = @(for ($k = 0; $k -lt [math]::Max($check.Count, $orig.Count); $k++) { if ($check[$k] -cne $orig[$k]) { $k } })
    if ($check.Count -ne $orig.Count -or $diff.Count -ne 1 -or $diff[0] -ne $n -or $check[$n] -cne $new) { throw "DefaultMaps.ini did not change in exactly line $($n + 1); restore it from $bak" }
    Done "stream: DefaultMaps.ini line $($n + 1) StreamingMaps[$Slot] $old -> $name$mapNote (backup $bak)"
}

# ---------------------------------------------------------------- main
$t0 = Get-Date
$code = 0
try {
    $s = $null
    if ($Spec) { $s = Read-Spec $Spec }
    elseif ($Step -in 't3d', 'build', 'all') { throw "the $Step step needs a spec file" }
    $name = if ($s) { $s.Name } else { $Map }
    if (-not $name) { throw 'give a spec file or -Map <patch name>' }
    if ($s -and $Map -and $Map -ne $s.Name) { throw "-Map $Map differs from the spec name $($s.Name)" }
    if ($name -notmatch '^[A-Za-z][A-Za-z0-9_]{2,62}$') { throw "bad patch name '$name'" }
    if ($Step -eq 'stream' -and -not $Stream) { throw 'the stream step needs -Stream <DisplayName>' }
    New-Item -ItemType Directory -Force (Join-Path $Work "$name\logs") | Out-Null
    $script:runLog = Join-Path $Work "$name\logs\patchtool-$Step-$stamp.log"
    Say "patchtool $Step $name$(if ($s) { " (spec $($s.Path), base $(if ($s.Base) { $s.Base } else { 'empty map' }), $($s.Objects.Count) objects)" })"
    if ($builtHidden) { Done "build: done on the hidden desktop (its log is above and in $(Join-Path $Work "$name\logs"))" }
    elseif ($Step -in 't3d', 'build', 'all') { $plan = Step-T3d $s }
    if ($Step -in 'build', 'all' -and -not $builtHidden) { Step-Build $s $plan }
    if ($Step -in 'cook', 'all') { Step-Cook $name }
    if ($Step -in 'deploy', 'all') { Step-Deploy $name }
    if ($Step -eq 'unseed') { Step-Unseed $name }
    if ($Stream -and $Step -in 'deploy', 'all', 'stream') { Set-StreamEntry $name $Stream $Slot }
    elseif ($Stream) { Say "WARNING: -Stream is ignored by the $Step step" }
    Say "OK: $Step $name in $([int]((Get-Date) - $t0).TotalSeconds) s"
    $script:summary | ForEach-Object { Say "  $_" }
} catch {
    Say "FAIL: $($_.Exception.Message)"
    Say "  at $(($_.ScriptStackTrace -split "`n")[0])"
    $code = 1
} finally {
    Restore-Clipboard
    Stop-MyEditor
}
exit $code
