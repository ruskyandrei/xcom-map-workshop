<#
Sends commands to the command box of a running authoring-UDK editor and prints the log lines they produce.

The editor ignores -EXEC= on its command line, but its command box (bottom left of the main window) takes the same
commands as the console. This finds that box through UI Automation and types into it with window messages, so it
works without moving the mouse or focusing the editor.

  pwsh -File tools\lab\udk_editor_cmd.ps1 'ACTOR SELECT ALL' 'EDIT COPY'
  pwsh -File tools\lab\udk_editor_cmd.ps1 -Wait 6 'OBJ SAVEPACKAGE PACKAGE="patch_exp04" FILE="..\..\UDKGame\Content\Maps\patches\patch_exp04.udk" SILENT=TRUE'

Useful commands: MAP IMPORTADD FILE="<t3d>", ACTOR SELECT ALL, EDIT COPY (selected actors as T3D to the clipboard),
OBJ SAVEPACKAGE PACKAGE="<name>" FILE="<path>" SILENT=TRUE, QUIT_EDITOR. MAP SAVE FILE= does nothing in this build.
-Udk defaults to the udk setting (tools\lab\LabSettings.ps1).
#>
param([Parameter(Mandatory, ValueFromRemainingArguments)][string[]]$Commands, [int]$Wait = 2,
      [string]$Udk = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LabSettings.ps1')
if (-not $Udk) { $Udk = Get-LabUdk }
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Threading;
public static class UdkCommandBox {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect r);
  struct Rect { public int L, T, R, B; }
  static string Cls(IntPtr h) { var s = new StringBuilder(64); GetClassName(h, s, 64); return s.ToString(); }
  public static IntPtr Find(IntPtr main) {
    IntPtr best = IntPtr.Zero; int bestTop = int.MinValue;
    EnumChildWindows(main, (h, l) => {
      Rect r; GetWindowRect(h, out r);
      if (Cls(h) == "Edit" && Cls(GetParent(h)) == "ComboBox" && r.R - r.L > 200 && r.T > bestTop) { best = h; bestTop = r.T; }
      return true;
    }, IntPtr.Zero);
    return best;
  }
  public static void Run(IntPtr edit, string cmd) {
    SendMessage(edit, 0x000C, IntPtr.Zero, cmd);                                   // WM_SETTEXT
    Thread.Sleep(100);
    // Key-down only: the editor's message loop makes the character itself, so also posting WM_CHAR ran slow
    // commands such as MAP IMPORTADD twice.
    PostMessage(edit, 0x0100, (IntPtr)0x0D, (IntPtr)0x001C0001);                   // WM_KEYDOWN Enter
    PostMessage(edit, 0x0101, (IntPtr)0x0D, unchecked((IntPtr)(int)0xC01C0001));   // WM_KEYUP
  }
}
'@
$p = Get-Process UDK -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' } | Select-Object -First 1
if (-not $p) { throw 'No UDK editor window is open.' }
# The command box is the ComboBox lowest in the main window; its text field is the Edit inside it. (UI Automation
# often sees none of the editor's controls, so this walks the native windows instead.)
$edit = [UdkCommandBox]::Find($p.MainWindowHandle)
if ($edit -eq [IntPtr]::Zero) { throw 'Command box not found.' }
$log = Join-Path $Udk 'UDKGame\Logs\Launch.log'
$n0 = (Get-Content $log).Count
foreach ($c in $Commands) { [UdkCommandBox]::Run($edit, $c); Start-Sleep -Seconds $Wait }
Get-Content $log | Select-Object -Skip $n0 | Where-Object { $_ -notmatch '^\[[\d.]+\] Cmd: $' }
