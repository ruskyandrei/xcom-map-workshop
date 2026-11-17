// Starts the game and works through a list of steps, sending it keys as window messages and collecting the game's
// own screenshots. Made to run on a private desktop (HiddenRun.cs), where nothing is on the user's screen and
// SendInput reaches nothing: window messages only reach windows of the caller's own desktop, so this starts the game
// itself and stays beside it. tools/lab/hidden_game.py prepares the install, runs this and tidies up after.
//
//   GameRemote.exe <XComEW.exe> <steps file> <out folder> <Launch.log> [game arguments...]
//
// Steps, one a line (# starts a comment), times in seconds:
//   wait <s>                    sleep
//   waitlog <s> <text>          wait until the game's log holds <text> (any case), at most <s>; the run fails if it doesn't
//   console <command>           run a console command: written to a file in XEW\Binaries and run by typing
//                               "exec <file>" in the game's one-line console (so any character can be in it)
//   type <command>              type the command itself in the console (letters, digits, space, '-' and '.' only)
//   shot <name>                 the game's own "shot"; the picture is saved as <out>\<name>.png
//   key <name> [count]          a key: A-Z, 0-9, F1-F12, RETURN, ESCAPE, SPACE, TAB, BACK, the arrows, HOME, END,
//                               PAGEUP, PAGEDOWN, BACKSLASH, TILDE, or 0x<hex>
//
// - No mouse: on a private desktop the game takes neither posted mouse messages (no hover, no click at its main menu)
//   nor a cursor position (SetCursorPos and GetCursorPos are refused there, error 5). Its menus go by the arrow keys
//   and Enter, and the console does the rest (findings register T-43).
// - Each line it prints starts with the seconds since the game was started.
// - Pictures: the game writes ScreenShotNNNNN.bmp to XComGame\Screenshots\PCConsole (beside the log's folder); each
//   is converted and the .bmp removed. A capture of the window from outside is black on a private desktop.
// - The game is ended (killed) after the last step, or when a step fails. Exit code: 0, 1 the game ended by itself or
//   had no window, 3 a waitlog or a shot ran out of time, 2 a bad steps file or bad arguments.
//
// Build: csc /nologo /target:exe /platform:anycpu /r:System.Drawing.dll /out:<lab>\bin\GameRemote.exe tools\lab\GameRemote.cs
// (hidden_game.py compiles it itself when it is missing or older than this source.)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class GameRemote
{
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    const uint WM_KEYDOWN = 0x100, WM_KEYUP = 0x101;
    const string WindowClass = "LaunchUnrealUWindowsClient";

    sealed class Fail : Exception { public readonly int Code; public Fail(int code, string message) : base(message) { Code = code; } }

    static readonly Stopwatch Clock = new Stopwatch();
    static Process game;
    static IntPtr window;
    static string logFile, shotFolder, binaries, outFolder;
    static DateTime started;
    static int execCount;
    static readonly List<string> execFiles = new List<string>();

    static void Say(string format, params object[] args)
    {
        Console.WriteLine("[{0,6:F1}] {1}", Clock.Elapsed.TotalSeconds, args.Length == 0 ? format : string.Format(format, args));
    }

    static void Alive() { if (game.HasExited) throw new Fail(1, "the game ended by itself, exit code " + game.ExitCode); }

    static void Sleep(double seconds)
    {
        DateTime until = DateTime.UtcNow.AddSeconds(seconds);
        while (DateTime.UtcNow < until) { Alive(); Thread.Sleep(Math.Min(200, Math.Max(1, (int)(until - DateTime.UtcNow).TotalMilliseconds))); }
    }

    static IntPtr FindWindow()
    {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, l) =>
        {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid != (uint)game.Id || !IsWindowVisible(h)) return true;
            var name = new StringBuilder(100); GetClassName(h, name, 100);
            if (name.ToString() != WindowClass) return true;
            found = h; return false;
        }, IntPtr.Zero);
        return found;
    }

    static void Key(uint vk)
    {
        uint scan = MapVirtualKey(vk, 0);
        PostMessage(window, WM_KEYDOWN, (IntPtr)vk, (IntPtr)(1 | (scan << 16)));
        Thread.Sleep(40);
        PostMessage(window, WM_KEYUP, (IntPtr)vk, (IntPtr)unchecked((int)(1 | (scan << 16) | 0xC0000000)));
        Thread.Sleep(40);
    }

    static uint TypedKey(char ch)
    {
        char c = char.ToUpperInvariant(ch);
        if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) return c;
        return c == ' ' ? 0x20u : c == '-' ? 0xBDu : c == '.' ? 0xBEu : 0u;
    }

    static void CheckTyped(string text, int line)
    {
        foreach (char ch in text)
            if (TypedKey(ch) == 0) throw new Fail(2, string.Format("line {0}: '{1}' can't be typed (letters, digits, space, '-' and '.' only); use console", line, ch));
    }

    // The one-line console: backslash opens it, Enter runs the line and closes it.
    static void TypeCommand(string text)
    {
        Alive();
        Key(0xDC); Thread.Sleep(400);
        foreach (char ch in text) Key(TypedKey(ch));
        Thread.Sleep(150);
        Key(0x0D);
    }

    static uint VkFromName(string name, int line)
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
            case "BACKSLASH": return 0xDC;
            case "TILDE": return 0xC0;
            case "LEFT": return 0x25; case "UP": return 0x26; case "RIGHT": return 0x27; case "DOWN": return 0x28;
            case "PAGEUP": return 0x21; case "PAGEDOWN": return 0x22;
            case "HOME": return 0x24; case "END": return 0x23;
        }
        int f;
        if (n.StartsWith("F") && n.Length <= 3 && int.TryParse(n.Substring(1), out f) && f >= 1 && f <= 12) return (uint)(0x6F + f);
        if (n.StartsWith("0X")) return Convert.ToUInt32(n.Substring(2), 16);
        throw new Fail(2, string.Format("line {0}: unknown key {1}", line, name));
    }

    static string ReadLog()
    {
        try
        {
            var info = new FileInfo(logFile);
            if (!info.Exists || info.LastWriteTime < started) return "";       // still the log of an earlier start
            using (var stream = new FileStream(logFile, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            using (var reader = new StreamReader(stream)) return reader.ReadToEnd();
        }
        catch (IOException) { return ""; }
    }

    static HashSet<string> Shots()
    {
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (Directory.Exists(shotFolder)) foreach (string f in Directory.GetFiles(shotFolder, "*.bmp")) names.Add(f);
        return names;
    }

    static void Shot(string name)
    {
        HashSet<string> before = Shots();
        TypeCommand("shot");
        DateTime until = DateTime.UtcNow.AddSeconds(20);
        while (DateTime.UtcNow < until)
        {
            Sleep(0.3);
            foreach (string file in Shots())
            {
                if (before.Contains(file)) continue;
                long size = new FileInfo(file).Length; Thread.Sleep(300);
                if (size == 0 || size != new FileInfo(file).Length) continue;      // still being written
                string target = Path.Combine(outFolder, name + ".png");
                using (Image image = Image.FromFile(file)) { image.Save(target, ImageFormat.Png); Say("shot {0}: {1}x{2} {3}", name, image.Width, image.Height, target); }
                File.Delete(file);
                return;
            }
        }
        throw new Fail(3, "shot " + name + ": the game wrote no picture in 20 s");
    }

    static double Number(string text, int line)
    {
        double value;
        if (!double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value) || value < 0) throw new Fail(2, string.Format("line {0}: {1} is not a number", line, text));
        return value;
    }

    sealed class Step { public int Line; public string Verb; public string[] Args; public string Rest; }

    static List<Step> ReadSteps(string file)
    {
        var steps = new List<Step>();
        string[] lines = File.ReadAllLines(file);
        for (int i = 0; i < lines.Length; i++)
        {
            string text = lines[i].Trim();
            if (text.Length == 0 || text[0] == '#') continue;
            int space = text.IndexOf(' ');
            var step = new Step { Line = i + 1, Verb = (space < 0 ? text : text.Substring(0, space)).ToLowerInvariant(), Rest = space < 0 ? "" : text.Substring(space + 1).Trim() };
            step.Args = step.Rest.Length == 0 ? new string[0] : step.Rest.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            int n = step.Args.Length;
            switch (step.Verb)
            {
                case "wait": if (n != 1) throw new Fail(2, "line " + step.Line + ": wait <seconds>"); Number(step.Args[0], step.Line); break;
                case "waitlog": if (n < 2) throw new Fail(2, "line " + step.Line + ": waitlog <seconds> <text>"); Number(step.Args[0], step.Line); break;
                case "console": if (n < 1) throw new Fail(2, "line " + step.Line + ": console <command>"); break;
                case "type": if (n < 1) throw new Fail(2, "line " + step.Line + ": type <command>"); CheckTyped(step.Rest, step.Line); break;
                case "shot":
                    if (n != 1 || step.Args[0].IndexOfAny(Path.GetInvalidFileNameChars()) >= 0) throw new Fail(2, "line " + step.Line + ": shot <name>");
                    break;
                case "key": if (n < 1 || n > 2) throw new Fail(2, "line " + step.Line + ": key <name> [count]"); VkFromName(step.Args[0], step.Line); if (n == 2) Number(step.Args[1], step.Line); break;
                default: throw new Fail(2, "line " + step.Line + ": unknown step " + step.Verb);
            }
            steps.Add(step);
        }
        return steps;
    }

    static string Quote(string value)
    {
        return value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '"' }) < 0 ? value : "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    static void Run(List<Step> steps)
    {
        foreach (Step step in steps)
        {
            Alive();
            switch (step.Verb)
            {
                case "wait": Sleep(Number(step.Args[0], step.Line)); break;
                case "waitlog":
                {
                    double limit = Number(step.Args[0], step.Line);
                    string text = step.Rest.Substring(step.Rest.IndexOf(' ') + 1).Trim();
                    DateTime until = DateTime.UtcNow.AddSeconds(limit);
                    while (ReadLog().IndexOf(text, StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        if (DateTime.UtcNow > until) throw new Fail(3, string.Format("waitlog: no \"{0}\" in the log after {1} s", text, limit));
                        Sleep(0.5);
                    }
                    Say("log has \"{0}\"", text);
                    break;
                }
                case "console":
                {
                    string name = string.Format("XComMapWorkshop-hidden-{0}.txt", ++execCount);
                    string file = Path.Combine(binaries, name);
                    File.WriteAllText(file, step.Rest + "\r\n", new UTF8Encoding(false));
                    execFiles.Add(file);
                    Say("console {0}", step.Rest);
                    TypeCommand("exec " + name);
                    Sleep(0.5);
                    break;
                }
                case "type": Say("type {0}", step.Rest); TypeCommand(step.Rest); Sleep(0.5); break;
                case "shot": Shot(step.Args[0]); break;
                case "key":
                {
                    uint vk = VkFromName(step.Args[0], step.Line);
                    int count = step.Args.Length > 1 ? (int)Number(step.Args[1], step.Line) : 1;
                    Say("key {0} x{1}", step.Args[0], count);
                    for (int i = 0; i < count; i++) { Key(vk); Thread.Sleep(60); }
                    break;
                }
            }
        }
    }

    static int Main(string[] args)
    {
        if (args.Length < 4) { Console.Error.WriteLine("usage: GameRemote <XComEW.exe> <steps file> <out folder> <Launch.log> [game arguments...]"); return 2; }
        string exe = Path.GetFullPath(args[0]);
        outFolder = Path.GetFullPath(args[2]);
        logFile = Path.GetFullPath(args[3]);
        binaries = Path.GetDirectoryName(Path.GetDirectoryName(exe));                                  // XEW\Binaries
        shotFolder = Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(logFile)), "Screenshots", "PCConsole");
        var gameArgs = new string[args.Length - 4];
        Array.Copy(args, 4, gameArgs, 0, gameArgs.Length);
        int code = 0;
        try
        {
            List<Step> steps = ReadSteps(args[1]);
            Directory.CreateDirectory(outFolder);
            var info = new ProcessStartInfo(exe, string.Join(" ", Array.ConvertAll(gameArgs, Quote))) { UseShellExecute = false, WorkingDirectory = Path.GetDirectoryName(exe) };
            started = DateTime.Now.AddSeconds(-1);
            Clock.Start();
            game = Process.Start(info);
            Say("started {0} {1}", Path.GetFileName(exe), info.Arguments);
            DateTime until = DateTime.UtcNow.AddSeconds(120);
            while ((window = FindWindow()) == IntPtr.Zero)
            {
                if (DateTime.UtcNow > until) throw new Fail(1, "the game opened no window in 120 s");
                Sleep(0.5);
            }
            RECT r; GetClientRect(window, out r);
            Say("window 0x{0:X}, client {1}x{2}", window.ToInt64(), r.R, r.B);
            Run(steps);
            Say("steps done");
        }
        catch (Fail fail) { Say("FAIL: " + fail.Message); code = fail.Code; }
        catch (Exception error) { Say("FAIL: " + error.Message); code = 1; }
        finally
        {
            try { if (game != null && !game.HasExited) { game.Kill(); game.WaitForExit(10000); } } catch (Exception) { }
            foreach (string file in execFiles) try { File.Delete(file); } catch (Exception) { }
        }
        return code;
    }
}
