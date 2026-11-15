// A stand-in for XCOM's launcher (XEW\Binaries\Win32\XCOMLauncher.exe) that asks nothing: it starts the XComEW.exe
// beside it with -FROMLAUNCHER and the arguments it was given, as the real launcher does after "Enemy Within" is
// clicked, and ends. Steam, launch options and the editor's Play in game work as before, without the click, and the
// game still runs as XComEW.exe.
//
// Why not a copy of XComEW.exe under the launcher's name (the usual advice): started by the game's Steam stub
// (Binaries\Win32\XComGame.exe) the copy quit within 200 ms, exit code 1 and nothing logged, every time
// (11 November 2026, findings register F-84), though the same file started by hand ran, and so does XComEW.exe
// started by this program. The real launcher also adds -LANGUAGE=<the one picked>; this one adds none, and the game
// takes its own setting.
//
// The arguments go on without the quotes they came in, as the real launcher hands them on: Steam's stub quotes each
// one ("-EXEC=file.txt"), and the game reads a quoted -EXEC with the closing quote as part of the file's name
// ("Can't find file '..\..\Binaries\file.txt"'"), so the commands of the editor's Play in game never ran and the
// game stopped at the main menu (11 November 2026). An argument with a space in it keeps its quotes.
//
// A start that ends within three seconds with an error is tried again, up to three times (not needed so far).
//
// Put in place (the game closed):
//     rename <game>\XEW\Binaries\Win32\XCOMLauncher.exe to XCOMLauncher_backup.exe
//     csc /target:winexe /out:<game>\XEW\Binaries\Win32\XCOMLauncher.exe tools\lab\XComLauncherSkip.cs
// Undo: delete it and rename the backup back (Steam's "Verify integrity of game files" also restores the launcher).
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

internal static class XComLauncherSkip
{
    static int Main(string[] args)
    {
        var parts = new System.Collections.Generic.List<string>();
        foreach (string arg in args)
        {
            if (arg.Length == 0) continue;
            parts.Add(arg.IndexOfAny(new[] { ' ', '\t' }) >= 0 ? "\"" + arg + "\"" : arg);
        }
        string rest = string.Join(" ", parts);
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        string game = Path.Combine(folder, "XComEW.exe");
        string arguments = rest.IndexOf("-FROMLAUNCHER", StringComparison.OrdinalIgnoreCase) >= 0 ? rest : ("-FROMLAUNCHER " + rest).Trim();
        var info = new ProcessStartInfo(game, arguments) { UseShellExecute = false, WorkingDirectory = folder };
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                using (Process child = Process.Start(info))
                {
                    if (!child.WaitForExit(3000) || child.ExitCode == 0 || attempt == 3) return 0;
                }
            }
            catch (Exception) { return 1; }
            Thread.Sleep(1000);
        }
    }
}
