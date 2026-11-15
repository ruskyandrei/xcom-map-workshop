<#
Saves the map open in a running authoring-UDK editor under a given file name, without real keyboard or mouse input.

MAP SAVE / OBJ SAVEPACKAGE from the command box fail, but File > Save As works: this sends that menu command, fills the standard
Save As dialog through window messages, presses Save and answers Yes if Windows asks to replace the file.

  pwsh -File tools\lab\udk_editor_saveas.ps1 -File <udk>\UDKGame\Content\Maps\patches\patch_exp04.udk
#>
param([Parameter(Mandatory)][string]$File, [int]$Timeout = 60)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class UdkSaveAs {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
  static string Cls(IntPtr h) { var s = new StringBuilder(64); GetClassName(h, s, 64); return s.ToString(); }
  public static string Text(IntPtr h) { var s = new StringBuilder(256); GetWindowText(h, s, 256); return s.ToString(); }
  // Visible standard dialogs (#32770) owned by the process, except the editor's own hidden-in-plain-sight "WPFFrame".
  public static List<IntPtr> Dialogs(uint pid) {
    var o = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h) && Cls(h) == "#32770" && Text(h) != "WPFFrame") o.Add(h); return true; }, IntPtr.Zero);
    return o;
  }
  static IntPtr Child(IntPtr dlg, Func<IntPtr, bool> ok) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(dlg, (h, l) => { if (ok(h)) { found = h; return false; } return true; }, IntPtr.Zero);
    return found;
  }
  // The file-name box: in the Explorer-style dialog the Edit in a ComboBox under a FloatNotifySink (the address bar's
  // Edit sits under a ComboBoxEx32 instead); in the old-style dialog the Edit in the ComboBox with id 1148 (cmb13).
  public static bool SetFileName(IntPtr dlg, string path) {
    IntPtr e = Child(dlg, h => Cls(h) == "Edit" && Cls(GetParent(h)) == "ComboBox" && Cls(GetParent(GetParent(h))) == "FloatNotifySink");
    if (e == IntPtr.Zero) e = Child(dlg, h => Cls(h) == "Edit" && GetDlgCtrlID(GetParent(h)) == 1148);
    if (e == IntPtr.Zero) return false;
    SendMessage(e, 0x000C, IntPtr.Zero, path);                                     // WM_SETTEXT
    return true;
  }
  // Presses the button with the given control id (1 = Save), or with the given text ("&Yes" in Confirm Save As,
  // whose buttons all have id 0).
  public static bool Press(IntPtr dlg, int id) {
    IntPtr b = Child(dlg, h => Cls(h) == "Button" && GetDlgCtrlID(h) == id);
    if (b == IntPtr.Zero) return false;
    PostMessage(b, 0x00F5, IntPtr.Zero, IntPtr.Zero);                              // BM_CLICK
    return true;
  }
  public static bool Press(IntPtr dlg, string text) {
    IntPtr b = Child(dlg, h => Cls(h) == "Button" && Text(h) == text);
    if (b == IntPtr.Zero) return false;
    PostMessage(b, 0x00F5, IntPtr.Zero, IntPtr.Zero);                              // BM_CLICK
    return true;
  }
  public static string Describe(IntPtr dlg) {
    var o = new StringBuilder();
    EnumChildWindows(dlg, (h, l) => { var t = Text(h); if (t.Length > 0) o.Append("[" + Cls(h) + " " + GetDlgCtrlID(h) + " " + t + "] "); return true; }, IntPtr.Zero);
    return o.ToString();
  }
}
'@
$p = Get-Process UDK -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Unreal Development Kit*' } | Select-Object -First 1
if (-not $p) { throw 'No UDK editor window is open.' }
$before = if (Test-Path $File) { (Get-Item $File).LastWriteTime } else { [datetime]::MinValue }
$pid0 = [uint32]$p.Id
# A Save dialog can take many seconds to appear (Save Current Level opens one too for a map not yet saved in this
# session), so an already open one is used rather than opening a second.
if ([UdkSaveAs]::Dialogs($pid0).Count) { Write-Host 'using the dialog already open' }
else { [UdkSaveAs]::PostMessage($p.MainWindowHandle, 0x0111, [IntPtr]6384, [IntPtr]::Zero) | Out-Null }   # File > Save As

$t0 = Get-Date; $named = $false; $answered = @{}
while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
    Start-Sleep -Milliseconds 500
    foreach ($d in [UdkSaveAs]::Dialogs($pid0)) {
        $title = [UdkSaveAs]::Text($d)
        if (-not $named -and [UdkSaveAs]::SetFileName($d, $File)) {
            Start-Sleep -Milliseconds 300; [UdkSaveAs]::Press($d, 1) | Out-Null; $named = $true
            Write-Host "filled '$title' and pressed Save"
        } elseif ($named -and $title -ne 'Save As' -and -not $answered[$d]) {
            Write-Host "dialog '$title': $([UdkSaveAs]::Describe($d))"
            if ([UdkSaveAs]::Press($d, '&Yes')) { Write-Host 'pressed Yes'; $answered[$d] = $true }
        }
    }
    if ($named -and (Test-Path $File) -and (Get-Item $File).LastWriteTime -gt $before -and -not [UdkSaveAs]::Dialogs($pid0).Count) {
        Start-Sleep -Seconds 2
        $i = Get-Item $File; Write-Host "saved $File ($($i.Length) bytes, $($i.LastWriteTime))"; exit 0
    }
}
Write-Host "timed out; open dialogs: $(([UdkSaveAs]::Dialogs($pid0) | ForEach-Object { [UdkSaveAs]::Text($_) }) -join ', ')"
exit 1
