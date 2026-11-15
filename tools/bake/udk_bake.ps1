<#
Bakes a T3D scene with UDK 2011-09's Lightmass and saves it as a .udk map (baker design, section 4.7: the UDK
encoder reference). A developer calibration tool only: no released bake step runs UDK.

  pwsh -File tools\bake\udk_bake.ps1 -T3d <lab>\bake-calib\calib1\scene.t3d -Map CalibBase -Out BakeCalib2

Opens the editor on -Map (a map in UDK's content folders; without it, UDK's template map, whose WorldInfo adds a
sky-blue Lightmass environment light: make a base map with udk_calib_base.py), deletes its actors, MAP IMPORTADDs
the T3D, runs the lines of -Commands if given (the editor refuses SET), runs BUILDLIGHTING from the command box and
confirms its Lighting Build Options dialog, waits until Lightmass has run and the log has gone quiet (or a lighting-complete
line appears), then saves through File > Save As (tools\lab\udk_editor_saveas.ps1) as
UDKGame\Content\Maps\calib\<Out>.udk and ends the editor.

-Quality Preview|Medium|High|Production sets the Lighting Build Options dialog's quality for this bake (QualityLevel
0-3 in UDKGame\Config\UDKEditorUserSettings.ini, put back byte for byte afterwards); without it the dialog keeps
what the file says. Preview emits few photons, too few for bounce light in a small scene.

Runs on the private desktop XComLab-UDK (tools\lab\HiddenRun.cs), like patchtool's build step, unless -Visible:
there the editor needs DirectX 11. Everything the editor starts (Swarm Agent, UnrealLightmass) belongs to HiddenRun's
job and ends with it. The editor's Launch.log is kept as <work>\launch-<time>.log beside the T3D.
-Udk defaults to the udk setting; HiddenRun.exe is compiled to <lab>\bin (tools\lab\LabSettings.ps1).
Exit code 0 on success, 1 on failure, 124 if the hidden run timed out.
#>
param(
    [Parameter(Mandatory)][string]$T3d,
    [Parameter(Mandatory)][string]$Out,
    [string]$Map = '',
    [string]$Commands = '',
    [switch]$Visible, [switch]$Force,
    [int]$OpenTimeout = 90, [int]$BuildTimeout = 1800, [int]$SaveTimeout = 180, [int]$Quiet = 20,
    [ValidateSet('', 'Preview', 'Medium', 'High', 'Production')][string]$Quality = '',
    [string]$Udk = ''
)
$ErrorActionPreference = 'Stop'
$lab = (Resolve-Path (Join-Path $PSScriptRoot '..\lab')).Path
. (Join-Path $lab 'LabSettings.ps1')
if (-not $Udk) { $Udk = Get-LabUdk }
$launchLog = Join-Path $Udk 'UDKGame\Logs\Launch.log'
$settingsIni = Join-Path $Udk 'UDKGame\Config\UDKEditorUserSettings.ini'
$calibDir = Join-Path $Udk 'UDKGame\Content\Maps\calib'
$udkFile = Join-Path $calibDir "$Out.udk"
$T3d = (Resolve-Path -LiteralPath $T3d).Path
$work = Split-Path -Parent $T3d
$extra = if ($Commands) { @(Get-Content -LiteralPath $Commands | Where-Object { $_.Trim() }) } else { @() }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if ($Out -notmatch '^[A-Za-z][A-Za-z0-9_]{1,29}$') { throw "-Out '$Out' must be a package name of at most 30 characters" }

Add-Type -Name ThreadDesktop -Namespace UdkBake -MemberDefinition @'
[DllImport("user32.dll")] static extern IntPtr GetThreadDesktop(uint thread);
[DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
[DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern bool GetUserObjectInformation(IntPtr h, int index, System.Text.StringBuilder info, int length, out int needed);
public static string Name() { var b = new System.Text.StringBuilder(256); int n; GetUserObjectInformation(GetThreadDesktop(GetCurrentThreadId()), 2, b, 512, out n); return b.ToString(); }
'@
$desktop = [UdkBake.ThreadDesktop]::Name()

if ($desktop -eq 'Default') {
    if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { Write-Host 'FAIL: a UDK process is running; close it first'; exit 1 }
    if ((Test-Path -LiteralPath $udkFile) -and -not $Force) { Write-Host "FAIL: $udkFile exists; pass -Force to replace it"; exit 1 }
    $same = @(Get-ChildItem -LiteralPath (Join-Path $Udk 'UDKGame\Content') -Recurse -File | Where-Object { $_.BaseName -ieq $Out -and $_.FullName -ne $udkFile })
    if ($same) { Write-Host "FAIL: another package is already called $Out`: $($same[0].FullName)"; exit 1 }
}
if (-not $Visible -and $desktop -eq 'Default') {
    $hiddenRun = Join-Path (Get-LabRoot) 'bin\HiddenRun.exe'
    $hiddenSrc = Join-Path $lab 'HiddenRun.cs'
    if (-not (Test-Path -LiteralPath $hiddenRun) -or (Get-Item -LiteralPath $hiddenRun).LastWriteTime -lt (Get-Item -LiteralPath $hiddenSrc).LastWriteTime) {
        New-Item -ItemType Directory -Force -Path (Split-Path $hiddenRun) | Out-Null
        & (Get-Csc) /nologo /target:exe /platform:anycpu "/out:$hiddenRun" $hiddenSrc
        if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: could not compile $hiddenSrc"; exit 1 }
    }
    $forward = foreach ($k in $PSBoundParameters.Keys) {
        $v = $PSBoundParameters[$k]
        if ($v -is [switch]) { if ($v) { "-$k" } } else { "-$k"; "$v" }
    }
    $limit = 3 * ($OpenTimeout + 10) + $BuildTimeout + $SaveTimeout + 120
    Write-Host "[$(Get-Date -Format HH:mm:ss)] baking on the hidden desktop XComLab-UDK (-Visible shows the editor instead)"
    & $hiddenRun --desktop XComLab-UDK --timeout $limit -- (Get-Process -Id $PID).Path -NoProfile -File $PSCommandPath @forward
    $code = $LASTEXITCODE
    if ($code -eq 124) { Write-Host "FAIL: the hidden bake did not finish in $limit s and was ended" }
    exit $code
}

function Say([string]$Text) { Write-Host "[$(Get-Date -Format HH:mm:ss)] $Text" }
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Threading;
public static class UdkBakeCommandBox {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect r);
  struct Rect { public int L, T, R, B; }
  static string Cls(IntPtr h) { var s = new StringBuilder(64); GetClassName(h, s, 64); return s.ToString(); }
  // The command box is the lowest wide Edit inside a ComboBox of the main window (as in patchtool).
  public static IntPtr Find(IntPtr main) {
    IntPtr best = IntPtr.Zero; int bestTop = int.MinValue;
    EnumChildWindows(main, (h, l) => { Rect r; GetWindowRect(h, out r);
      if (Cls(h) == "Edit" && Cls(GetParent(h)) == "ComboBox" && r.R - r.L > 200 && r.T > bestTop) { best = h; bestTop = r.T; } return true; }, IntPtr.Zero);
    return best;
  }
  // Enter as WM_KEYDOWN/WM_KEYUP only: an extra WM_CHAR re-runs slow commands (patchtool finding).
  public static void Run(IntPtr edit, string cmd) {
    SendMessage(edit, 0x000C, IntPtr.Zero, cmd);
    Thread.Sleep(100);
    PostMessage(edit, 0x0100, (IntPtr)0x0D, (IntPtr)0x001C0001);
    PostMessage(edit, 0x0101, (IntPtr)0x0D, unchecked((IntPtr)(int)0xC01C0001));
  }
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  static string Txt(IntPtr h) { var s = new StringBuilder(256); GetWindowText(h, s, 256); return s.ToString(); }
  // A visible dialog (#32770) of the process with this title, or zero.
  public static IntPtr Dialog(uint pid, string title) {
    IntPtr f = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h) && Cls(h) == "#32770" && Txt(h) == title) { f = h; return false; } return true; }, IntPtr.Zero);
    return f;
  }
  static IntPtr Button(IntPtr dlg, string text) {
    IntPtr f = IntPtr.Zero;
    EnumChildWindows(dlg, (h, l) => { if (Cls(h) == "Button" && Txt(h) == text) { f = h; return false; } return true; }, IntPtr.Zero);
    return f;
  }
  public static bool Checked(IntPtr dlg, string text) { return SendMessage(Button(dlg, text), 0x00F0, IntPtr.Zero, IntPtr.Zero) == (IntPtr)1; }
  // BM_CLICK, posted so a modal dialog's own loop handles it. False when there is no such button.
  public static bool Click(IntPtr dlg, string text) {
    IntPtr b = Button(dlg, text);
    if (b == IntPtr.Zero) return false;
    PostMessage(b, 0x00F5, IntPtr.Zero, IntPtr.Zero);
    return true;
  }
}
'@
# BUILDLIGHTING opens the modal "Lighting Build Options" dialog; Use Lightmass must stay ticked and the stats window
# off. After the build the editor leaves "Map Check" and "Lighting Results" open, which the Save As helper would take
# for its dialog, so they are closed first (first calibration bake, 6 November).
function Confirm-BuildOptions([uint32]$EditorPid) {
    $d = [UdkBakeCommandBox]::Dialog($EditorPid, 'Lighting Build Options')
    if ($d -eq [IntPtr]::Zero) { return $false }
    if (-not [UdkBakeCommandBox]::Checked($d, 'Use Lightmass')) { $null = [UdkBakeCommandBox]::Click($d, 'Use Lightmass'); Say 'ticked Use Lightmass' }
    if ([UdkBakeCommandBox]::Checked($d, 'Show lighting stats after build completes')) { $null = [UdkBakeCommandBox]::Click($d, 'Show lighting stats after build completes') }
    Start-Sleep -Milliseconds 300
    $null = [UdkBakeCommandBox]::Click($d, '&OK')
    Say 'pressed OK in Lighting Build Options'
    return $true
}
function Close-ResultWindows([uint32]$EditorPid) {
    foreach ($t in 'Map Check', 'Lighting Results') {
        $d = [UdkBakeCommandBox]::Dialog($EditorPid, $t)
        if ($d -ne [IntPtr]::Zero -and [UdkBakeCommandBox]::Click($d, 'Close')) { Say "closed $t"; Start-Sleep -Milliseconds 500 }
    }
}
$editorPids = @()
function Send-Commands([string[]]$Commands, [int]$Wait = 2) {
    $edit = [IntPtr]::Zero
    for ($try = 1; $edit -eq [IntPtr]::Zero; $try++) {
        $p = Get-Process -Id $script:editorPids -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' } | Select-Object -First 1
        if ($p) { $edit = [UdkBakeCommandBox]::Find($p.MainWindowHandle) }
        if ($edit -eq [IntPtr]::Zero) { if ($try -ge 15) { throw 'the editor command box was not found in 30 s' }; Start-Sleep -Seconds 2 }
    }
    $n0 = @(Get-Content -LiteralPath $launchLog).Count
    foreach ($c in $Commands) { [UdkBakeCommandBox]::Run($edit, $c); Start-Sleep -Seconds $Wait }
    @(Get-Content -LiteralPath $launchLog | Select-Object -Skip $n0)
}
function Keep-Log { if (Test-Path -LiteralPath $launchLog) { Copy-Item -LiteralPath $launchLog (Join-Path $work "launch-$stamp.log") -Force } }

$ok = $false
$iniBytes = $null
try {
    if (Get-Process -Name UDK -ErrorAction SilentlyContinue) { throw 'a UDK process is already running' }
    if ($Quality) {
        $level = @{ Preview = 0; Medium = 1; High = 2; Production = 3 }[$Quality]
        $iniBytes = [IO.File]::ReadAllBytes($settingsIni)
        $latin1 = [Text.Encoding]::GetEncoding(28591)
        $text = $latin1.GetString($iniBytes)
        $at = $text.IndexOf('[LightingBuildOptions]')
        $m = if ($at -ge 0) { [regex]::new('QualityLevel=\d+').Match($text, $at) } else { $null }
        if (-not $m -or -not $m.Success) { $iniBytes = $null; throw "no QualityLevel under [LightingBuildOptions] in $settingsIni" }
        $text = $text.Substring(0, $m.Index) + "QualityLevel=$level" + $text.Substring($m.Index + $m.Length)
        [IO.File]::WriteAllBytes($settingsIni, $latin1.GetBytes($text))
        Say "Lightmass quality $Quality (QualityLevel=$level in UDKEditorUserSettings.ini for this bake)"
    }
    $dx11 = $desktop -ne 'Default'
    Say "opening the editor on desktop $desktop$(if ($dx11) { ' (DirectX 11)' })"
    $global:LASTEXITCODE = 0
    & (Join-Path $lab 'udk_editor_try.ps1') -Map $Map -Tries 3 -Timeout $OpenTimeout -Udk $Udk -Dx11:$dx11 *>&1 | ForEach-Object { Say "  editor: $_" }
    $editorPids = @(Get-Process -Name UDK -ErrorAction SilentlyContinue | ForEach-Object Id)
    if ($LASTEXITCODE -ne 0 -or -not $editorPids) { throw 'the editor did not open' }
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Get-Process -Id $editorPids -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' })) {
        if ((Get-Date) -gt $deadline) { throw 'the editor window did not appear' }
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 3
    $del = Send-Commands @('ACTOR SELECT ALL', 'DELETE') 2
    Say "cleared the $(if ($Map) { "base map $Map" } else { 'template map' }) ($(@($del | Where-Object { $_ -match 'Cmd: DELETE' }).Count) DELETE run; $(@($del | Where-Object { $_ -match 'Deleted \d+ Actors' }) -join ' '))"
    $imp = Send-Commands @("MAP IMPORTADD FILE=`"$T3d`"") 4
    $imp | Where-Object { $_ -match 'error|warning|fail|unresolved|can''t|cannot' } | ForEach-Object { Say "  import: $_" }
    $runs = @($imp | Where-Object { $_ -match 'Cmd: MAP IMPORTADD' }).Count
    if ($runs -ne 1) { throw "the import ran $runs times" }
    foreach ($c in $extra) {
        $out = Send-Commands @($c) 2
        $out | ForEach-Object { Say "  command: $_" }
        if (-not ($out | Where-Object { $_ -match ('Cmd: ' + [regex]::Escape($c.Trim())) })) { throw "the editor did not log the command: $c" }
    }

    $n0 = @(Get-Content -LiteralPath $launchLog).Count
    $t0 = Get-Date
    $null = Send-Commands @('BUILDLIGHTING') 2
    Say 'BUILDLIGHTING sent; waiting for Lightmass'
    $editorPid = [uint32]$editorPids[0]
    $confirmed = $false
    $sawLightmass = $false; $lastLen = -1; $lastChange = Get-Date; $done = $null
    while (((Get-Date) - $t0).TotalSeconds -lt $BuildTimeout) {
        Start-Sleep -Seconds 2
        if (-not (Get-Process -Id $editorPids -ErrorAction SilentlyContinue)) { throw 'the editor exited during the build' }
        if (-not $confirmed) { $confirmed = Confirm-BuildOptions $editorPid }
        if (Get-Process -Name UnrealLightmass -ErrorAction SilentlyContinue) { $sawLightmass = $true }
        $lines = @(Get-Content -LiteralPath $launchLog | Select-Object -Skip $n0)
        if ($lines.Count -ne $lastLen) { $lastLen = $lines.Count; $lastChange = Get-Date }
        $hit = $lines | Where-Object { $_ -match 'Lighting build took|Illumination: |Lighting complete|Static lighting build|LightingBuild.*(complete|finished)' } | Select-Object -Last 1
        if ($hit) { $done = "log: $hit"; break }
        if ($sawLightmass -and -not (Get-Process -Name UnrealLightmass -ErrorAction SilentlyContinue) -and ((Get-Date) - $lastChange).TotalSeconds -ge $Quiet) {
            $done = "Lightmass ran and exited; log quiet for $Quiet s"; break
        }
    }
    $secs = [int]((Get-Date) - $t0).TotalSeconds
    Get-Content -LiteralPath $launchLog | Select-Object -Skip $n0 | Where-Object { $_ -match 'Lightmass|Lighting|Swarm|light|error|warning' } |
        Select-Object -Last 40 | ForEach-Object { Say "  build: $_" }
    if (-not $done) { throw "the lighting build did not finish in $BuildTimeout s (Lightmass seen: $sawLightmass)" }
    Say "build finished after $secs s ($done)"
    Start-Sleep -Seconds 5
    Close-ResultWindows $editorPid
    if (Get-Content -LiteralPath $launchLog | Select-Object -Skip $n0 | Where-Object { $_ -match '^\[[\d.]+\] Critical:' }) { throw 'the editor logged a critical error during the build' }

    New-Item -ItemType Directory -Force -Path $calibDir | Out-Null
    $before = Get-Date
    $global:LASTEXITCODE = 0
    & (Join-Path $lab 'udk_editor_saveas.ps1') -File $udkFile -Timeout $SaveTimeout *>&1 | ForEach-Object { Say "  save: $_" }
    if ($LASTEXITCODE -ne 0) { throw 'Save As failed or timed out' }
    $i = Get-Item -LiteralPath $udkFile
    if ($i.LastWriteTime -lt $before) { throw "$udkFile was not rewritten" }
    Say "saved $udkFile ($($i.Length) bytes)"
    $ok = $true
} catch {
    Say "FAIL: $($_.Exception.Message)"
} finally {
    foreach ($id in $editorPids) {
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p -and -not $p.HasExited) { $p.Kill(); $null = $p.WaitForExit(15000); Say "closed the editor (pid $id)" }
    }
    if ($iniBytes) { [IO.File]::WriteAllBytes($settingsIni, $iniBytes); Say 'put UDKEditorUserSettings.ini back' }
    Keep-Log
}
if (-not $ok) { exit 1 }
