<#
Checks patchtool's record for a map shipped under its own name (map.shipAs, map.streamSlot) without the game, UDK or
the lab:
  1. Get-StreamSlotSpec, Get-StreamSlots and Get-ShipRecord on real record lines (defaultmaps-records.txt, copied
     byte for byte from LWR's DefaultMaps.ini and from the lab's EXP-08 record);
  2. with -Config (a folder holding DefaultMaps.ini and DefaultLZMutator.ini, only read), Set-ShipConfig itself on
     copies of both files in a temporary folder: only the planned lines change, CRLF and the rest stay byte for byte,
     a second run changes nothing, and a new slot updates the record in place.
The functions are taken from this checkout's patchtool.ps1 (from its syntax tree; its main code does not run).

  pwsh -NoProfile -File tools\patch\tests\test_ship_record.ps1
  pwsh -NoProfile -File tools\patch\tests\test_ship_record.ps1 -Config "<LWR install>\XEW\XComGame\Config"

Exit code 0 when every check passes, 1 otherwise.
#>
param([string]$Config = '')
$ErrorActionPreference = 'Stop'
$latin1 = [Text.Encoding]::Latin1

# ---------------------------------------------------------------- the functions under test, from patchtool.ps1
$tool = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\patchtool.ps1')).Path
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($tool, [ref]$null, [ref]$parseErrors)
if ($parseErrors) { Write-Host "FAIL: patchtool.ps1 does not parse: $($parseErrors[0])"; exit 1 }
$want = 'Opt', 'Backup', 'Get-StreamSlotSpec', 'Get-StreamSlots', 'Get-ShipRecord', 'Edit-LabIni', 'Set-ShipConfig'
$defs = @($ast.FindAll({ param($a) $a -is [Management.Automation.Language.FunctionDefinitionAst] }, $false) | Where-Object Name -in $want)
$lost = @($want | Where-Object { $_ -notin $defs.Name })
if ($lost) { Write-Host "FAIL: patchtool.ps1 has no $($lost -join ', ')"; exit 1 }
foreach ($d in $defs) { . ([scriptblock]::Create($d.Extent.Text)) }
$said = [Collections.Generic.List[string]]::new()
function Say([string]$Text) { $said.Add($Text) }
function Done([string]$Text) { $said.Add($Text) }

$script:fails = 0; $script:count = 0
function Check([string]$What, [bool]$Ok, [string]$Detail = '') {
    $script:count++
    if ($Ok) { Write-Host "ok   $What" } else { $script:fails++; Write-Host "FAIL $What$(if ($Detail) { "`n     $Detail" })" }
}
function Throws([string]$What, [scriptblock]$Do, [string]$Like) {
    $msg = $null
    try { $null = & $Do } catch { $msg = $_.Exception.Message }
    Check $What ($null -ne $msg -and $msg -like $Like) $(if ($null -eq $msg) { 'no error' } else { $msg })
}
function SlotList([string]$Record) { (@(Get-StreamSlots $Record) | ForEach-Object { "$($_.Slot)=$($_.MapName)" }) -join ' ' }

$rows = @{}
foreach ($l in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'defaultmaps-records.txt'), $latin1)) {
    if (-not $l -or $l.StartsWith('#')) { continue }
    $t = $l.IndexOf("`t"); $rows[$l.Substring(0, $t)] = $l.Substring($t + 1)
}
Check 'the fixture has its 10 record lines' ($rows.Count -eq 10) "$($rows.Count): $($rows.Keys -join ', ')"

# ---------------------------------------------------------------- 1. the stream slot a spec gives
Write-Host '-- map.streamSlot values'
Check 'slot 1' ((Get-StreamSlotSpec 1) -eq 1)
Check 'slot 0 and 100 are allowed' ((Get-StreamSlotSpec 0) -eq 0 -and (Get-StreamSlotSpec 100) -eq 100)
Check 'a JSON number (Int64) gives an int' ((Get-StreamSlotSpec ('{"s": 2}' | ConvertFrom-Json).s) -is [int])
Check '2.0 is slot 2' ((Get-StreamSlotSpec 2.0) -eq 2)
Check '"free" and "FREE" give free' ((Get-StreamSlotSpec 'free') -ceq 'free' -and (Get-StreamSlotSpec 'FREE') -ceq 'free')
Throws 'the text "2" is refused' { Get-StreamSlotSpec '2' 'map.streamSlot' } 'map.streamSlot must be a slot number from 0 to 100, or "free", not the text*'
Throws '-1 is refused' { Get-StreamSlotSpec (-1) } '*not -1'
Throws 'a JSON -1 is refused' { Get-StreamSlotSpec ('{"s": -1}' | ConvertFrom-Json).s } '*not -1'
Throws '101 is refused' { Get-StreamSlotSpec 101 } '*not 101'
Throws '1.5 is refused' { Get-StreamSlotSpec 1.5 } '*not 1.5'
Throws 'a JSON 2.5 is refused' { Get-StreamSlotSpec ('{"s": 2.5}' | ConvertFrom-Json).s } '*not 2.5'
Throws 'true is refused' { Get-StreamSlotSpec $true } '*not ''True'' (Boolean)'
Throws 'a list is refused' { Get-StreamSlotSpec @(1, 2) } '*(Object`[`])'

# ---------------------------------------------------------------- 1. reading the slots of LWR's records
Write-Host '-- StreamingMaps entries of real records'
$slotsWant = [ordered]@{
    bar                 = '0=CIN_DropshipIntros 1=patch_bar 5=patch_hide_randomized_objects'
    bar_terror          = '0=CIN_DropshipIntros 1=patch_bar'
    liquorstore         = '0=CIN_DropshipIntros 5=patch_hide_randomized_objects 2=patch_liquorestore'
    gangplank           = '0=CIN_DropshipIntros 5=patch_hide_randomized_objects 2=patch_battleship_roof'
    templeship          = '0=TempleShip_Stream 1=CIN_TP12A_ArriveTempleShip 5=patch_hide_randomized_objects'
    researchoutpost_ewi = '0=CIN_FastropeIntros 1=URB_ResearchOutpost_CovExt 2=patch_researchoutpost'
}
foreach ($k in $slotsWant.Keys) { $got = SlotList $rows[$k]; Check "$k streams $($slotsWant[$k])" ($got -ceq $slotsWant[$k]) "got $got" }
$ro = @(Get-StreamSlots $rows.researchoutpost_ewi)
Check 'researchoutpost_ewi: bare names are read as bare, the quoted one as quoted' (-not $ro[0].Quoted -and -not $ro[1].Quoted -and $ro[2].Quoted)

# ---------------------------------------------------------------- 1. the shipped record
Write-Host '-- Get-ShipRecord'
$bar = $rows.bar
# Slot 1 as before E0: the same line patchtool wrote for EXP-08 on 4 November 2026.
$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarBlank' 'URB_BarBlank (EXP-08 blank map) |0' 'patch_exp08blank' 1 $false 'Day'
Check 'slot 1 gives the EXP-08 record byte for byte' ($r.Record -ceq $rows.exp08_barblank) "got  $($r.Record)`n     want $($rows.exp08_barblank)"
Check 'slot 1 replaced patch_bar' ($r.Slot -eq 1 -and $r.Old -ceq 'patch_bar' -and -not $r.Added)

# "free" on URB_Bar: slot 2 added at the end, everything else as the base record. Written out by hand from the line.
$tail = 'Roll=0 ) ) ) '
$free = $bar.Replace('Name="URB_Bar",', 'Name="URB_BarSlot",').Replace('DisplayName="URB_Bar (Beta/Functionality Complete Urban Bar) |0"', 'DisplayName="URB_BarSlot (EXP-10 stream slot) |0"').Replace('bInRotation=True', 'bInRotation=False')
Check 'the bar line ends as expected' ($free.EndsWith($tail))
$free = $free.Substring(0, $free.Length - $tail.Length) + 'Roll=0 ) ), StreamingMaps[2]=( MapName="patch_exp10slot", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) ) '
$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarSlot' 'URB_BarSlot (EXP-10 stream slot) |0' 'patch_exp10slot' 'free'
Check '"free" on URB_Bar adds StreamingMaps[2]' ($r.Slot -eq 2 -and $r.Added -and $r.Old -ceq '')
Check '"free" on URB_Bar gives the expected line' ($r.Record -ceq $free) "got  $($r.Record)`n     want $free"
Check '"free" keeps all three of URB_Bar''s streams' ((SlotList $r.Record) -ceq '0=CIN_DropshipIntros 1=patch_bar 5=patch_hide_randomized_objects 2=patch_exp10slot') (SlotList $r.Record)
Check 'no TimeOfDay given: the record keeps Night' ($r.Record.Contains('TimeOfDay=eMissionTime_Night,'))
Check 'the variant is out of rotation' ($r.Record.Contains('bInRotation=False,') -and -not $r.Record.Contains('bInRotation=True'))
$r2 = Get-ShipRecord $bar 'URB_Bar' 'URB_BarSlot' 'URB_BarSlot (EXP-10 stream slot) |0' 'patch_exp10slot' 'FREE'
Check 'the same base record gives the same line again' ($r2.Record -ceq $r.Record)

$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarX' 'X |0' 'patch_x' 7
Check 'slot 7 is added after slot 5' ($r.Added -and (SlotList $r.Record) -ceq '0=CIN_DropshipIntros 1=patch_bar 5=patch_hide_randomized_objects 7=patch_x')
$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarX' 'X |0' 'patch_x' 5
Check 'slot 5 replaces patch_hide_randomized_objects' (-not $r.Added -and $r.Old -ceq 'patch_hide_randomized_objects' -and (SlotList $r.Record) -ceq '0=CIN_DropshipIntros 1=patch_bar 5=patch_x')
$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarX' 'X |0' 'patch_x' 0
Check 'slot 0 replaces the dropship intro (Set-ShipConfig warns)' (-not $r.Added -and $r.Old -ceq 'CIN_DropshipIntros')
$r = Get-ShipRecord $rows.bar_terror 'URB_Bar_Terror' 'URB_Bar_TerrorX' 'X |0' 'patch_x' 'free'
Check '"free" on URB_Bar_Terror (0, 1) adds slot 2' ($r.Slot -eq 2 -and (SlotList $r.Record) -ceq '0=CIN_DropshipIntros 1=patch_bar 2=patch_x')

$r = Get-ShipRecord $rows.templeship 'TempleShip' 'TempleShipX' 'TempleShipX |0' 'patch_x' 'free'
Check '"free" on TempleShip adds slot 2 and keeps its arrival cinematic (T-08)' ($r.Slot -eq 2 -and (SlotList $r.Record) -ceq '0=TempleShip_Stream 1=CIN_TP12A_ArriveTempleShip 5=patch_hide_randomized_objects 2=patch_x') (SlotList $r.Record)
Check 'TempleShip keeps TimeOfDay None' ($r.Record.Contains('TimeOfDay=eMissionTime_None,'))
$r = Get-ShipRecord $rows.templeship 'TempleShip' 'TempleShipX' 'TempleShipX |0' 'patch_x' 1
Check 'slot 1 on TempleShip would replace CIN_TP12A_ArriveTempleShip' ($r.Old -ceq 'CIN_TP12A_ArriveTempleShip')

$r = Get-ShipRecord $rows.liquorstore 'URB_LiquorStore' 'URB_LiquorStoreX' 'X |0' 'patch_x' 'free'
Check '"free" on URB_LiquorStore (0, 5, 2) adds slot 1' ($r.Slot -eq 1 -and (SlotList $r.Record) -ceq '0=CIN_DropshipIntros 5=patch_hide_randomized_objects 2=patch_liquorestore 1=patch_x')
$r = Get-ShipRecord $rows.gangplank 'DLC1_3_Gangplank' 'GangplankX' 'X |0' 'patch_x' 'free'
$gTail = "Roll=0 ) ), StreamingMaps[1]=( MapName=`"patch_x`", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) )`t`t`t`t`t`t"
Check 'gangplank (last entry ends with a comma): one comma, the tabs after the record kept' ($r.Slot -eq 1 -and $r.Record.EndsWith($gTail) -and $r.Record -notmatch ',\s*,') ($r.Record.Substring($r.Record.Length - 120))
$r = Get-ShipRecord $rows.researchoutpost_ewi 'URB_ResearchOutpost_EWI' 'X_EWI' 'X |0' 'patch_x' 1
Check 'a bare MapName is replaced bare' ($r.Old -ceq 'URB_ResearchOutpost_CovExt' -and $r.Record.Contains('StreamingMaps[1]=(MapName=patch_x, '))
$r = Get-ShipRecord $rows.researchoutpost_ewi 'URB_ResearchOutpost_EWI' 'X_EWI' 'X |0' 'patch_x' 'free'
Check '"free" on researchoutpost_ewi (0, 1, 2) adds slot 3' ($r.Slot -eq 3 -and $r.Record.EndsWith('Roll=0 ) ), StreamingMaps[3]=( MapName="patch_x", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) )'))

$r = Get-ShipRecord $bar 'URB_Bar' 'URB_BarX' 'Bar $1 $$ |0' 'patch_x' 1
Check 'a $ in the display name is written as it is' ($r.Record.Contains('DisplayName="Bar $1 $$ |0"'))
Check 'the old [regex]::Replace(..., 1) call replaced every match (1 is RegexOptions.IgnoreCase)' ([regex]::Replace('aXA', 'a', 'b', 1) -ceq 'bXb')

Throws 'a record without the base map''s Name is refused' { Get-ShipRecord $bar 'URB_Pub' 'X' 'X |0' 'patch_x' 1 } 'the record has no Name="URB_Pub"'
Throws 'a record whose brackets don''t close is refused' { Get-ShipRecord $bar.Substring(0, $bar.LastIndexOf(')')) 'URB_Bar' 'X' 'X |0' 'patch_x' 'free' } '*can''t find the end of URB_Bar''s record*'
Throws 'text after the record is refused' { Get-ShipRecord ($bar + '; note') 'URB_Bar' 'X' 'X |0' 'patch_x' 'free' } '*can''t find the end of URB_Bar''s record*'
Throws 'a slot written twice is refused' { Get-ShipRecord $bar.Replace('StreamingMaps[5]=', 'StreamingMaps[1]=') 'URB_Bar' 'X' 'X |0' 'patch_x' 'free' } '*StreamingMaps`[1`] more than once'
Throws 'an entry without a MapName is refused' { Get-ShipRecord $bar.Replace('StreamingMaps[5]=( MapName=', 'StreamingMaps[5]=( Name=') 'URB_Bar' 'X' 'X |0' 'patch_x' 'free' } '*3 StreamingMaps entries but only 2*'
Throws 'a bad slot is refused' { Get-ShipRecord $bar 'URB_Bar' 'X' 'X |0' 'patch_x' 'next' } 'the stream slot must be*'

# ---------------------------------------------------------------- 2. Set-ShipConfig on copies of real INI files
if ($Config) {
    Write-Host "-- Set-ShipConfig on copies of $Config (only read)"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) "patchtool-ship-test-$PID"
    try {
        $Game = Join-Path $tmp 'game'
        $cfg = Join-Path $Game 'XEW\XComGame\Config'
        New-Item -ItemType Directory -Force $cfg | Out-Null
        $given = @(foreach ($f in 'DefaultMaps.ini', 'DefaultLZMutator.ini') { (Get-FileHash -LiteralPath (Join-Path $Config $f)).Hash; Copy-Item -LiteralPath (Join-Path $Config $f) (Join-Path $cfg $f) })
        $gameIni = Join-Path $cfg 'DefaultMaps.ini'; $lzIni = Join-Path $cfg 'DefaultLZMutator.ini'
        $backups = Join-Path $tmp 'backups'; $stamp = 'test'
        function Lines([string]$Path) { , ($latin1.GetString([IO.File]::ReadAllBytes($Path)) -split "`r`n") }
        function Crlf([string]$Path) { $t = $latin1.GetString([IO.File]::ReadAllBytes($Path)); ($t.Split("`n").Count - 1) -eq ([regex]::Matches($t, "`r`n").Count) }
        $o = Lines $gameIni; $oLz = Lines $lzIni
        $b = @(for ($i = 0; $i -lt $o.Count; $i++) { if ($o[$i] -match '^\s*Maps=\(' -and $o[$i] -match '(?<![A-Za-z])Name="URB_Bar"\s*,') { $i } })[0]
        $zones = @($oLz | Where-Object { $_ -notmatch '^\s*;' -and $_.Contains('MapName="URB_Bar",') })

        $ship = [pscustomobject]@{ map = 'URB_Bar'; shipAs = 'URB_BarSlot'; displayName = 'URB_BarSlot (EXP-10 stream slot) |0'; inRotation = $false; timeOfDay = ''; patch = 'patch_exp10slot'; streamSlot = 'free' }
        $said.Clear(); Set-ShipConfig $ship
        $n = Lines $gameIni
        Check 'free: two lines added to DefaultMaps.ini' ($n.Count -eq $o.Count + 2) "$($o.Count) -> $($n.Count)"
        Check 'free: every other line kept byte for byte' ((($n[0..$b] + $n[($b + 3)..($n.Count - 1)]) -join "`n") -ceq ($o -join "`n"))
        Check 'free: the comment names the slot' ($n[$b + 1].StartsWith("; URB_BarSlot: URB_Bar's record under its own name, streaming patch_exp10slot in StreamingMaps[2] (patchtool, ")) $n[$b + 1]
        Check 'free: the record is the expected line' ($n[$b + 2] -ceq $free)
        Check 'free: DefaultMaps.ini keeps CRLF, no BOM' ((Crlf $gameIni) -and [IO.File]::ReadAllBytes($gameIni)[0] -ne 0xEF)
        Check 'free: the summary says StreamingMaps[2] added' (@($said | Where-Object { $_ -like '*a record for URB_BarSlot*StreamingMaps`[2`] added for patch_exp10slot*' }).Count -eq 1) ($said -join ' / ')
        $nLz = Lines $lzIni
        $copied = @($nLz | Where-Object { $_ -notmatch '^\s*;' -and $_.Contains('MapName="URB_BarSlot",') })
        Check "free: URB_Bar's $($zones.Count) landing zones copied" ($zones.Count -gt 0 -and $copied.Count -eq $zones.Count -and $nLz.Count -eq $oLz.Count + $zones.Count + 1)
        Check 'free: DefaultLZMutator.ini keeps CRLF' (Crlf $lzIni)
        Check 'free: both INIs backed up' (@(Get-ChildItem -LiteralPath $backups).Count -eq 2)

        $h1 = (Get-FileHash -LiteralPath $gameIni).Hash; $h2 = (Get-FileHash -LiteralPath $lzIni).Hash
        $said.Clear(); Set-ShipConfig $ship
        Check 'again: neither file changes' ((Get-FileHash -LiteralPath $gameIni).Hash -eq $h1 -and (Get-FileHash -LiteralPath $lzIni).Hash -eq $h2)
        Check 'again: it says both are there already' (@($said | Where-Object { $_ -like '*already has*' }).Count -eq 2) ($said -join ' / ')

        $ship.streamSlot = [long]1
        $said.Clear(); Set-ShipConfig $ship
        $n2 = Lines $gameIni
        $want1 = (Get-ShipRecord $o[$b] 'URB_Bar' 'URB_BarSlot' 'URB_BarSlot (EXP-10 stream slot) |0' 'patch_exp10slot' 1).Record
        Check 'slot 1 next: the record is updated in place' ($n2.Count -eq $n.Count -and $n2[$b + 2] -ceq $want1 -and (SlotList $n2[$b + 2]) -ceq '0=CIN_DropshipIntros 1=patch_exp10slot 5=patch_hide_randomized_objects')
        Check 'slot 1 next: the summary says patch_bar -> patch_exp10slot' (@($said | Where-Object { $_ -like '*record updated (StreamingMaps`[1`] patch_bar -> patch_exp10slot)*' }).Count -eq 1) ($said -join ' / ')

        # A ship file from before map.streamSlot (EXP-08's) has no streamSlot: slot 1, the same record as on 4 November.
        $old = [pscustomobject]@{ map = 'URB_Bar'; shipAs = 'URB_BarBlank'; displayName = 'URB_BarBlank (EXP-08 blank map) |0'; inRotation = $false; timeOfDay = 'Day'; patch = 'patch_exp08blank' }
        $said.Clear(); Set-ShipConfig $old
        $n3 = Lines $gameIni
        Check 'an EXP-08 ship file still gives the EXP-08 record' ($n3[$b + 2] -ceq $rows.exp08_barblank -and $n3.Count -eq $n2.Count + 2)

        $temple = [pscustomobject]@{ map = 'TempleShip'; shipAs = 'TempleShipX'; displayName = 'TempleShipX (test) |0'; inRotation = $false; timeOfDay = ''; patch = 'patch_x'; streamSlot = 1 }
        $said.Clear(); Set-ShipConfig $temple
        Check 'TempleShip slot 1: a warning that it replaces the cinematic (T-08)' (@($said | Where-Object { $_ -like "WARNING: StreamingMaps``[1``] of TempleShip's record streams 'CIN_TP12A_ArriveTempleShip', not a patch*" }).Count -eq 1) ($said -join ' / ')
        $temple.displayName = 'TempleShipY (test) |0'; $temple.shipAs = 'TempleShipY'; $temple.streamSlot = 'free'
        $said.Clear(); Set-ShipConfig $temple
        Check 'TempleShip free: no warning, slot 2 added' (@($said | Where-Object { $_ -like 'WARNING: StreamingMaps*' }).Count -eq 0 -and @($said | Where-Object { $_ -like '*StreamingMaps`[2`] added for patch_x*' }).Count -eq 1) ($said -join ' / ')

        # A test slot pointed at the base map has the base map's Name too (EXP-14 run 1b). With -Stream naming that
        # slot, the record is still made from the base map's own record, not from the test slot.
        $slotName = 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0'
        $m = Lines $gameIni
        $ti = @(for ($i = 0; $i -lt $m.Count; $i++) { if ($m[$i] -match '^\s*Maps=\(' -and $m[$i].Contains("DisplayName=`"$slotName`"")) { $i } })
        Check 'the test slot line is in DefaultMaps.ini' ($ti.Count -eq 1) "$($ti.Count) lines"
        if ($ti.Count -eq 1) {
            $m[$ti[0]] = [regex]::new('(?<![A-Za-z])Name="[^"]*"').Replace($m[$ti[0]], 'Name="TempleShip"', 1)
            [IO.File]::WriteAllBytes($gameIni, $latin1.GetBytes($m -join "`r`n"))
            $tz = [pscustomobject]@{ map = 'TempleShip'; shipAs = 'TempleShipZ'; displayName = 'TempleShipZ (test) |0'; inRotation = $false; timeOfDay = ''; patch = 'patch_z'; streamSlot = 'free' }
            $Stream = $slotName
            $said.Clear(); Set-ShipConfig $tz
            $Stream = ''
            $all = Lines $gameIni
            $z = @($all | Where-Object { $_.Contains('DisplayName="TempleShipZ (test) |0"') })
            Check 'a test slot named TempleShip: the record is made from Temple''s own, not the slot' ($z.Count -eq 1 -and $z[0].Contains('MapFamily="templeship"') -and $z[0].Contains('MissionType=eMission_Final')) ($z -join ' / ')
            $said.Clear(); Set-ShipConfig ([pscustomobject]@{ map = 'TempleShip'; shipAs = 'TempleShipW'; displayName = 'TempleShipW (test) |0'; inRotation = $false; timeOfDay = ''; patch = 'patch_w'; streamSlot = 'free' })
            $all = Lines $gameIni
            $w = @($all | Where-Object { $_.Contains('DisplayName="TempleShipW (test) |0"') })
            Check 'without -Stream, the first line named TempleShip is taken, as before (the test slot here)' ($w.Count -eq 1 -and -not $w[0].Contains('MapFamily="templeship"') -and -not $w[0].Contains('MissionType=eMission_Final')) ($w -join ' / ')
        }
        $after = @(foreach ($f in 'DefaultMaps.ini', 'DefaultLZMutator.ini') { (Get-FileHash -LiteralPath (Join-Path $Config $f)).Hash })
        Check 'the files given with -Config are untouched' (($after -join ' ') -eq ($given -join ' '))
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
} else { Write-Host '-- Set-ShipConfig on real INI files: skipped (give -Config <folder with DefaultMaps.ini and DefaultLZMutator.ini>)' }

Write-Host "$($script:count - $script:fails) of $($script:count) checks passed"
exit $(if ($script:fails) { 1 } else { 0 })
