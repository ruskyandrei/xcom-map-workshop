// Steam launch-option wrapper for XCOM: Enemy Unknown / Enemy Within (AppID 200510).
//
// Steam > XCOM: Enemy Unknown > Properties > General > Launch options:
//     "<lab>\bin\XComLabWrapper.exe" %command% -nostartupmovies
//
// The live LWR install and the lab copy sit side by side in steamapps\common; tools\lab\switch_install.ps1
// renames whichever is wanted to XCom-Enemy-Unknown, so Steam always runs the folder it knows.
//
// Normal (LWR) folder: runs Steam's command unchanged and waits for it.
// Lab copy (its root holds XComLab-copy.txt): adds -nohomedir, so settings, saves and logs stay inside the copy
// instead of Documents\My Games (a line "nohomedir=false" in the marker turns this off). The argument is passed
// down the EU stub -> launcher -> XComEW.exe chain. With a line "launch=direct" in the marker the wrapper skips
// the stub and the launcher and starts XEW\Binaries\Win32\XComEW.exe -FROMLAUNCHER itself: no launcher click, and
// no -LANGUAGE=INT, which the developer console reportedly needs.
// (With the launcher replaced by the stand-in, XComLauncherSkip.cs, there is no click either way; the stand-in adds
// -FROMLAUNCHER itself.)
// A line "args=..." in the marker adds those arguments for the lab copy, for example "args=-forcelogflush", which
// makes the game write its log line by line, so a hang or a crash keeps it (7 November 2026).
// XComEW.exe quits about a second after startup (exit code 1, nothing logged) while any steam_appid* file sits
// next to it, even steam_appid.txt.off (3 November 2026), so the wrapper warns about one.
// Every run is logged to logs\wrapper.log beside the exe's folder (<lab>\logs\wrapper.log for <lab>\bin\XComLabWrapper.exe).
// Set XCOMLAB_WRAPPER_DRYRUN=1 to log without starting anything.
//
// Build: csc /target:winexe /platform:x86 /out:<lab>\bin\XComLabWrapper.exe tools\lab\XComLabWrapper.cs
using System;
using System.Diagnostics;
using System.IO;

internal static class XComLabWrapper
{
    const string Marker = "XComLab-copy.txt";
    static readonly string LogFile = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\logs\wrapper.log"));

    static void Log(string message)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(LogFile));
            File.AppendAllText(LogFile, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message + Environment.NewLine);
        }
        catch { }
    }

    // Splits a raw Windows command line into its first token (unquoted) and the untouched remainder.
    static void SplitFirst(string commandLine, out string first, out string rest)
    {
        string s = commandLine.TrimStart();
        int end;
        if (s.StartsWith("\""))
        {
            end = s.IndexOf('"', 1);
            if (end < 0) end = s.Length;
            first = s.Substring(1, end - 1);
            end = Math.Min(end + 1, s.Length);
        }
        else
        {
            end = s.IndexOf(' ');
            if (end < 0) end = s.Length;
            first = s.Substring(0, end);
        }
        rest = s.Substring(end).TrimStart();
    }

    // The install root holding the marker, searching upwards from the launched exe; null for the live install.
    static string FindLabRoot(string exe)
    {
        try
        {
            for (string dir = Path.GetDirectoryName(Path.GetFullPath(exe)); dir != null; dir = Path.GetDirectoryName(dir))
            {
                if (File.Exists(Path.Combine(dir, Marker))) return dir;
                if (Path.GetFileName(dir).Equals("common", StringComparison.OrdinalIgnoreCase)) break;
            }
        }
        catch { }
        return null;
    }

    static int Main()
    {
        bool dryRun = Environment.GetEnvironmentVariable("XCOMLAB_WRAPPER_DRYRUN") == "1";
        string self, original, exe, arguments;
        SplitFirst(Environment.CommandLine, out self, out original);
        SplitFirst(original, out exe, out arguments);
        Log("start: steam command = " + original + (dryRun ? "   (dry run)" : ""));

        string labRoot = FindLabRoot(exe);
        string marker = "";
        try { if (labRoot != null) marker = File.ReadAllText(Path.Combine(labRoot, Marker)); } catch { }
        bool noHomeDir = marker.IndexOf("nohomedir=false", StringComparison.OrdinalIgnoreCase) < 0;
        string workingDir = Environment.CurrentDirectory;
        if (labRoot != null && !noHomeDir)
        {
            Log("  lab copy active (" + Path.Combine(labRoot, Marker) + "), marker says nohomedir=false: command unchanged");
        }
        else if (labRoot != null)
        {
            Log("  lab copy active (" + Path.Combine(labRoot, Marker) + "): adding -nohomedir");
            if (arguments.IndexOf("-nohomedir", StringComparison.OrdinalIgnoreCase) < 0) arguments = (arguments + " -nohomedir").Trim();
        }
        else
        {
            Log("  live install: command unchanged");
        }
        if (labRoot != null)
        {
            foreach (string line in marker.Split('\n'))
            {
                string t = line.Trim();
                if (!t.StartsWith("args=", StringComparison.OrdinalIgnoreCase)) continue;
                string extra = t.Substring(5).Trim();
                if (extra.Length == 0 || arguments.IndexOf(extra, StringComparison.OrdinalIgnoreCase) >= 0) continue;
                arguments = (arguments + " " + extra).Trim();
                Log("  marker adds: " + extra);
            }
        }
        string ewExe = labRoot == null ? null : Path.Combine(labRoot, @"XEW\Binaries\Win32\XComEW.exe");
        if (ewExe != null && marker.IndexOf("launch=direct", StringComparison.OrdinalIgnoreCase) >= 0 && File.Exists(ewExe)
            && Path.GetFileName(exe).Equals("XComGame.exe", StringComparison.OrdinalIgnoreCase))
        {
            exe = ewExe;
            workingDir = Path.GetDirectoryName(ewExe);
            arguments = ("-FROMLAUNCHER " + arguments).Trim();
            Log("  marker says launch=direct: starting XComEW.exe without the launcher");
        }
        try
        {
            string ewBin = Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(Path.GetFullPath(exe)))), @"XEW\Binaries\Win32");
            foreach (string stray in Directory.GetFiles(ewBin, "steam_appid*"))
                Log("  WARNING: " + stray + " exists: XComEW.exe quits at startup until it is removed");
        }
        catch { }

        Log("  run: \"" + exe + "\" " + arguments + "   (cwd " + workingDir + ")");
        if (dryRun) return 0;
        try
        {
            var info = new ProcessStartInfo(exe, arguments) { UseShellExecute = false, WorkingDirectory = workingDir };
            using (Process child = Process.Start(info))
            {
                child.WaitForExit();
                Log("  exit code " + child.ExitCode);
                return child.ExitCode;
            }
        }
        catch (Exception e)
        {
            Log("  failed: " + e.Message);
            return 1;
        }
    }
}
