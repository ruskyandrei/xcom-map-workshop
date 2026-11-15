// Drives a running game window with simulated input and takes screenshots, for in-game checks without a person.
//
//   GameDriver.exe info                          window of XComEW.exe (or XCOMLauncher.exe): handle, rectangle, foreground
//   GameDriver.exe shot <out.png> [scale]        screenshot of the game window (scale 0.5 halves it); prints the size
//   GameDriver.exe focus                         brings the game window to the front (topmost trick plus a click)
//   GameDriver.exe move <x> <y>                  mouse to window-relative pixel x,y (full-resolution pixels)
//   GameDriver.exe click <x> <y> [right]         move there and click
//   GameDriver.exe key <name> [count]            press a key: a VK name such as RETURN, ESCAPE, OEM_5 (backslash), F1, A
//   GameDriver.exe type <text>                   types text as characters (for the console)
//   GameDriver.exe console <command>             opens the one-line console (backslash), types the command, presses Enter
//   GameDriver.exe hotkey <dir> [key]            stays running: each press of the global hotkey (default F9, which the
//                                                game leaves unbound) saves <dir>\look-<time>.png, appends
//                                                "<time> <file>" to <dir>\looks.txt and beeps; one instance at a time
//   GameDriver.exe waitlook <dir> [seen]         waits until looks.txt has more than <seen> lines (default: as many as
//                                                now), prints the new lines and exits
//
// Every input command first checks that the game window is in front and refuses otherwise, so it never types into
// another program. The process is DPI aware, so coordinates are physical pixels, as in the screenshots.
// "hotkey" sends no input; it only registers the key (the game then doesn't see it) and captures the screen.
//
// Build: csc /nologo /target:exe /platform:anycpu /r:System.Drawing.dll /out:<lab>\bin\GameDriver.exe tools\lab\GameDriver.cs
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Threading;

internal static class GameDriver
{
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Explicit)] struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public INPUTUNION u; }

    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUT[] inputs, int size);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint mapType);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
    [DllImport("user32.dll")] static extern int GetMessage(out MSG m, IntPtr h, uint min, uint max);
    [StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam, lParam; public uint time; public POINT pt; }
    const uint MOD_NOREPEAT = 0x4000, WM_HOTKEY = 0x0312;

    const uint INPUT_MOUSE = 0, INPUT_KEYBOARD = 1;
    const uint KEYEVENTF_KEYUP = 0x2, KEYEVENTF_UNICODE = 0x4, KEYEVENTF_SCANCODE = 0x8;
    const uint MOUSEEVENTF_MOVE = 0x1, MOUSEEVENTF_LEFTDOWN = 0x2, MOUSEEVENTF_LEFTUP = 0x4, MOUSEEVENTF_RIGHTDOWN = 0x8, MOUSEEVENTF_RIGHTUP = 0x10;

    static IntPtr FindGameWindow(out string processName)
    {
        foreach (string name in new[] { "XComEW", "XCOMLauncher" })
            foreach (Process p in Process.GetProcessesByName(name))
                if (p.MainWindowHandle != IntPtr.Zero && IsWindowVisible(p.MainWindowHandle)) { processName = name; return p.MainWindowHandle; }
        processName = null;
        return IntPtr.Zero;
    }

    static Rectangle ClientRectOnScreen(IntPtr h)
    {
        RECT r; GetClientRect(h, out r);
        var p = new POINT();
        ClientToScreen(h, ref p);
        return new Rectangle(p.X, p.Y, r.Right - r.Left, r.Bottom - r.Top);
    }

    static IntPtr RequireFront()
    {
        string name;
        IntPtr h = FindGameWindow(out name);
        if (h == IntPtr.Zero) throw new Exception("no XComEW or XCOMLauncher window");
        if (GetForegroundWindow() != h) throw new Exception(name + " is not the foreground window; run 'focus' first");
        return h;
    }

    static void Send(params INPUT[] inputs) { SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT))); }

    static INPUT Key(ushort vk, bool up)
    {
        var i = new INPUT { type = INPUT_KEYBOARD };
        i.u.ki.wVk = vk;
        i.u.ki.wScan = (ushort)MapVirtualKey(vk, 0);
        i.u.ki.dwFlags = up ? KEYEVENTF_KEYUP : 0;
        return i;
    }

    static INPUT Char(char c, bool up)
    {
        var i = new INPUT { type = INPUT_KEYBOARD };
        i.u.ki.wScan = c;
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | (up ? KEYEVENTF_KEYUP : 0);
        return i;
    }

    static INPUT Mouse(uint flags) { var i = new INPUT { type = INPUT_MOUSE }; i.u.mi.dwFlags = flags; return i; }

    static ushort VkFromName(string name)
    {
        string n = name.ToUpperInvariant();
        if (n.Length == 1 && ((n[0] >= 'A' && n[0] <= 'Z') || (n[0] >= '0' && n[0] <= '9'))) return n[0];
        switch (n)
        {
            case "RETURN": case "ENTER": return 0x0D;
            case "ESCAPE": case "ESC": return 0x1B;
            case "SPACE": return 0x20;
            case "TAB": return 0x09;
            case "BACK": return 0x08;
            case "OEM_5": case "BACKSLASH": return 0xDC;
            case "OEM_3": case "TILDE": return 0xC0;
            case "LEFT": return 0x25; case "UP": return 0x26; case "RIGHT": return 0x27; case "DOWN": return 0x28;
            case "PRIOR": case "PAGEUP": return 0x21; case "NEXT": case "PAGEDOWN": return 0x22;
            case "HOME": return 0x24; case "END": return 0x23;
        }
        if (n.StartsWith("F") && n.Length <= 3) { int f; if (int.TryParse(n.Substring(1), out f) && f >= 1 && f <= 12) return (ushort)(0x6F + f); }
        if (n.StartsWith("0X")) return Convert.ToUInt16(n.Substring(2), 16);
        throw new Exception("unknown key " + name);
    }

    static void PressKey(ushort vk) { Send(Key(vk, false)); Thread.Sleep(40); Send(Key(vk, true)); Thread.Sleep(60); }

    static void TypeText(string text)
    {
        // The game's console ignores Unicode (VK_PACKET) input, so letters, digits, space, '-' and '.' are sent as key
        // presses (lower case; console commands ignore case). Anything else falls back to a Unicode character.
        foreach (char ch in text)
        {
            char c = char.ToUpperInvariant(ch);
            ushort vk = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ? c : c == ' ' ? (ushort)0x20 : c == '-' ? (ushort)0xBD : c == '.' ? (ushort)0xBE : (ushort)0;
            if (vk != 0) { Send(Key(vk, false)); Thread.Sleep(15); Send(Key(vk, true)); }
            else Send(Char(ch, false), Char(ch, true));
            Thread.Sleep(20);
        }
    }

    static void MoveTo(IntPtr h, int x, int y)
    {
        Rectangle r = ClientRectOnScreen(h);
        SetCursorPos(r.X + x, r.Y + y);
        Thread.Sleep(30);
        // The game's menus react to mouse-move events, which SetCursorPos alone doesn't send: nudge the mouse.
        var nudge = Mouse(MOUSEEVENTF_MOVE); nudge.u.mi.dx = 1; Send(nudge); Thread.Sleep(30);
        nudge.u.mi.dx = -1; Send(nudge); Thread.Sleep(80);
    }

    // Saves the game window's client area; returns a one-line description.
    static string Capture(string path, double scale)
    {
        string name;
        IntPtr h = FindGameWindow(out name);
        if (h == IntPtr.Zero) throw new Exception("no game window");
        Rectangle r = ClientRectOnScreen(h);
        using (var full = new Bitmap(r.Width, r.Height, PixelFormat.Format24bppRgb))
        {
            using (Graphics g = Graphics.FromImage(full)) g.CopyFromScreen(r.X, r.Y, 0, 0, r.Size);
            int w = (int)(r.Width * scale), hh = (int)(r.Height * scale);
            using (var outBmp = new Bitmap(w, hh, PixelFormat.Format24bppRgb))
            {
                using (Graphics g = Graphics.FromImage(outBmp)) { g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.DrawImage(full, 0, 0, w, hh); }
                outBmp.Save(path, path.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase) ? ImageFormat.Jpeg : ImageFormat.Png);
            }
        }
        return string.Format("{0}: {1}x{2} window, saved at scale {3} to {4}", name, r.Width, r.Height, scale, path);
    }

    static int LineCount(string file) { return System.IO.File.Exists(file) ? System.IO.File.ReadAllLines(file).Length : 0; }

    static int Main(string[] args)
    {
        SetProcessDPIAware();
        try
        {
            if (args.Length == 0) { Console.Error.WriteLine("usage: GameDriver info|shot|focus|move|click|key|type|console ..."); return 2; }
            string name;
            IntPtr h;
            switch (args[0].ToLowerInvariant())
            {
                case "info":
                {
                    h = FindGameWindow(out name);
                    if (h == IntPtr.Zero) { Console.WriteLine("no game window"); return 1; }
                    Rectangle r = ClientRectOnScreen(h);
                    Console.WriteLine("{0} window 0x{1:X} client {2},{3} {4}x{5} foreground={6}", name, h.ToInt64(), r.X, r.Y, r.Width, r.Height, GetForegroundWindow() == h);
                    return 0;
                }
                case "shot":
                {
                    double scale = args.Length > 2 ? double.Parse(args[2], System.Globalization.CultureInfo.InvariantCulture) : 1.0;
                    Console.WriteLine(Capture(args[1], scale));
                    return 0;
                }
                case "hotkey":
                {
                    string dir = args[1];
                    System.IO.Directory.CreateDirectory(dir);
                    string list = System.IO.Path.Combine(dir, "looks.txt");
                    ushort vk = VkFromName(args.Length > 2 ? args[2] : "F9");
                    bool first;
                    using (var single = new Mutex(true, "XComLabGameDriverHotkey", out first))
                    {
                        if (!first) throw new Exception("a hotkey instance is already running");
                        if (!RegisterHotKey(IntPtr.Zero, 1, MOD_NOREPEAT, vk)) throw new Exception("could not register the hotkey (another program has it)");
                        Console.WriteLine("hotkey {0} ready; looks go to {1}", args.Length > 2 ? args[2] : "F9", list);
                        MSG m;
                        while (GetMessage(out m, IntPtr.Zero, 0, 0) > 0)
                        {
                            if (m.message != WM_HOTKEY) continue;
                            string stamp = DateTime.Now.ToString("HHmmss");
                            string file = System.IO.Path.Combine(dir, "look-" + stamp + ".png");
                            try
                            {
                                Thread.Sleep(150);
                                string what = Capture(file, 1.0);
                                System.IO.File.AppendAllText(list, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + file + Environment.NewLine);
                                Console.WriteLine(what);
                                Console.Beep(1400, 120);
                            }
                            catch (Exception e) { Console.Error.WriteLine("capture failed: " + e.Message); Console.Beep(400, 300); }
                        }
                    }
                    return 0;
                }
                case "waitlook":
                {
                    string list = System.IO.Path.Combine(args[1], "looks.txt");
                    int seen = args.Length > 2 ? int.Parse(args[2]) : LineCount(list);
                    while (LineCount(list) <= seen) Thread.Sleep(500);
                    Thread.Sleep(300);
                    string[] lines = System.IO.File.ReadAllLines(list);
                    for (int i = seen; i < lines.Length; i++) Console.WriteLine(lines[i]);
                    Console.WriteLine("seen={0}", lines.Length);
                    return 0;
                }
                case "focus":
                {
                    h = FindGameWindow(out name);
                    if (h == IntPtr.Zero) throw new Exception("no game window");
                    if (GetForegroundWindow() != h)
                    {
                        const uint flags = 0x0001 | 0x0002;   // SWP_NOSIZE | SWP_NOMOVE
                        SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, flags);   // HWND_TOPMOST
                        SetForegroundWindow(h);
                        Thread.Sleep(200);
                        if (GetForegroundWindow() != h)
                        {
                            // A click inside the window is what Windows accepts as the user's choice; click a corner of the client area.
                            Rectangle r = ClientRectOnScreen(h);
                            var corner = new POINT { X = r.X + 5, Y = r.Bottom - 5 };
                            if (GetAncestor(WindowFromPoint(corner), 2) != h) throw new Exception("another window covers the game window");
                            SetCursorPos(corner.X, corner.Y);
                            Send(Mouse(MOUSEEVENTF_LEFTDOWN)); Thread.Sleep(60); Send(Mouse(MOUSEEVENTF_LEFTUP));
                            Thread.Sleep(300);
                        }
                        SetWindowPos(h, new IntPtr(-2), 0, 0, 0, 0, flags);   // HWND_NOTOPMOST
                    }
                    Console.WriteLine("{0} foreground={1}", name, GetForegroundWindow() == h);
                    return GetForegroundWindow() == h ? 0 : 1;
                }
                case "move":
                    h = RequireFront(); MoveTo(h, int.Parse(args[1]), int.Parse(args[2])); return 0;
                case "click":
                {
                    h = RequireFront(); MoveTo(h, int.Parse(args[1]), int.Parse(args[2]));
                    bool right = args.Length > 3 && args[3] == "right";
                    Send(Mouse(right ? MOUSEEVENTF_RIGHTDOWN : MOUSEEVENTF_LEFTDOWN)); Thread.Sleep(60);
                    Send(Mouse(right ? MOUSEEVENTF_RIGHTUP : MOUSEEVENTF_LEFTUP)); Thread.Sleep(100);
                    return 0;
                }
                case "key":
                {
                    RequireFront();
                    ushort vk = VkFromName(args[1]);
                    int count = args.Length > 2 ? int.Parse(args[2]) : 1;
                    for (int i = 0; i < count; i++) PressKey(vk);
                    return 0;
                }
                case "type":
                    RequireFront(); TypeText(string.Join(" ", args, 1, args.Length - 1)); return 0;
                case "console":
                    RequireFront();
                    PressKey(0xDC); Thread.Sleep(300);
                    TypeText(string.Join(" ", args, 1, args.Length - 1)); Thread.Sleep(100);
                    PressKey(0x0D);
                    return 0;
            }
            Console.Error.WriteLine("unknown command " + args[0]);
            return 2;
        }
        catch (Exception e)
        {
            Console.Error.WriteLine("error: " + e.Message);
            return 1;
        }
    }
}
