<#
Presses "Enemy Within" in the XCOM launcher window (XCOMLauncher.exe) with a real mouse click.
Not needed, and finds no window, in an install whose launcher is the stand-in (XComLauncherSkip.cs), as both
of this project's are since 11 November 2026.

The launcher's two buttons are unlabelled image panes (Enemy Within on top, Enemy Unknown below) that ignore
posted window messages, so the cursor is moved there, clicked and put back. Waits up to -TimeoutSeconds for the
launcher window to appear.

Windows often refuses SetForegroundWindow from a background script, so the launcher is made topmost for the
click, and nothing is clicked unless the launcher is the window under the cursor (3 November 2026: two clicks
landed on Discord sitting over the launcher).
#>
param([int]$TimeoutSeconds = 60)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class LauncherMouse {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint f);
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
"@
$null = [LauncherMouse]::SetProcessDPIAware()

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    $p = Get-Process -Name XCOMLauncher -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    if (-not $p) { Start-Sleep -Milliseconds 500 }
} until ($p -or (Get-Date) -gt $deadline)
if (-not $p) { throw "No XCOM launcher window within $TimeoutSeconds s" }
Start-Sleep -Seconds 1

$root = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$panes = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition) |
    Where-Object { $_.Current.BoundingRectangle.Width -gt 200 -and $_.Current.BoundingRectangle.Height -gt 100 } |
    Sort-Object { $_.Current.BoundingRectangle.Y }
if ($panes.Count -lt 2) { throw "Expected two button panes in the launcher, found $($panes.Count)" }
$r = $panes[0].Current.BoundingRectangle
$x = [int]($r.X + $r.Width / 2); $y = [int]($r.Y + $r.Height / 2)

$hwnd = $p.MainWindowHandle; $launcherPath = $p.Path
$noMoveSize = 0x0001 -bor 0x0002 -bor 0x0010   # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
$null = [LauncherMouse]::SetWindowPos($hwnd, [IntPtr](-1), 0, 0, 0, 0, $noMoveSize)   # HWND_TOPMOST
$null = [LauncherMouse]::SetForegroundWindow($hwnd); Start-Sleep -Milliseconds 300
try {
    $pt = New-Object LauncherMouse+POINT; $pt.X = $x; $pt.Y = $y
    $under = [LauncherMouse]::GetAncestor([LauncherMouse]::WindowFromPoint($pt), 2)   # GA_ROOT
    if ($under -ne $hwnd) { throw "Not clicking: another window covers the Enemy Within button at ($x, $y)" }
    $old = New-Object LauncherMouse+POINT; $null = [LauncherMouse]::GetCursorPos([ref]$old)
    $null = [LauncherMouse]::SetCursorPos($x, $y); Start-Sleep -Milliseconds 150
    [LauncherMouse]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 80
    [LauncherMouse]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 200
    $null = [LauncherMouse]::SetCursorPos($old.X, $old.Y)
    Write-Host "Clicked Enemy Within at ($x, $y) in $launcherPath"
} finally {
    if (-not $p.HasExited) { $null = [LauncherMouse]::SetWindowPos($hwnd, [IntPtr](-2), 0, 0, 0, 0, $noMoveSize) }   # HWND_NOTOPMOST
}
