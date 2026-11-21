// Starts XCOM: Enemy Within (XComEW.exe) so that it runs beside another running copy of the game.
//
// Why it is needed (21 November 2026, findings register T-52): the game allows one instance per Windows session by
// itself; Steam is not what stops the second one. WinMain (0xBF0911 at the exe's preferred base 0x400000) calls a
// function (0xEEF7E0) that makes the named mutex "UnrealEngine3_8" and returns 0 when the mutex already exists;
// WinMain then returns 1 at once: exit code 1 after about 0.1 s and no Launch.log. A hidden desktop does not help,
// since named objects are per session, not per desktop.
//
// What this does: starts XComEW.exe suspended, replaces that one call in the new process's memory with
// "mov eax, 1" (as if it were the first instance), and resumes it. No file is changed. The game started this way
// never makes the mutex, so it starts whether or not another copy runs, and a copy started normally afterwards
// still sees itself as the first. The bytes are checked first; an exe that differs is started unchanged, with a
// message.
//
// It also sets SteamAppId and SteamGameId to 200510, which a game started outside Steam needs (F-84), and
// __COMPAT_LAYER=HIGHDPIAWARE, without which Windows scales a copy started from a folder that has no compatibility
// setting of its own and the game saves the wrong size (T-48), and starts the game in its own XEW\Binaries\Win32
// folder.
//
// Usage:
//   XComSideBySide.exe --exe <path to XComEW.exe> -- <game arguments>
//   XComSideBySide.exe --common <steamapps\common> --copy <name> -- <game arguments>
//       picks the folder XCom-Enemy-Unknown* under <common> whose XComLab-copy.txt has the line "copy=<name>",
//       so the folder may be renamed (tools\lab\switch_install.ps1 does that).
// Every run is logged to ..\logs\side-by-side.log beside this exe's folder.
//
// Build (32-bit, as the game is: the PEB is read as a 32-bit one):
//     csc /target:winexe /platform:x86 /out:<lab>\bin\XComSideBySide.exe tools\lab\XComSideBySide.cs
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;

internal static class XComSideBySide
{
    const string AppId = "200510";
    const uint CallRva = 0x7F0911;                                   // 0xBF0911 - 0x400000
    static readonly byte[] Expected = { 0xE8, 0xCA, 0xEE, 0x2F, 0x00 };   // call 0xEEF7E0
    static readonly byte[] Patch = { 0xB8, 0x01, 0x00, 0x00, 0x00 };      // mov eax, 1

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO
    {
        public int cb; public string lpReserved, lpDesktop, lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public int dwProcessId, dwThreadId; }
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_BASIC_INFORMATION { public IntPtr ExitStatus, PebBaseAddress, AffinityMask, BasePriority, UniqueProcessId, InheritedFrom; }

    [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool CreateProcessW(string app, System.Text.StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit, uint flags, IntPtr env, string cwd, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("ntdll")]
    static extern int NtQueryInformationProcess(IntPtr process, int cls, ref PROCESS_BASIC_INFORMATION info, int size, out int ret);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, int size, out int read);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool WriteProcessMemory(IntPtr process, IntPtr address, byte[] buffer, int size, out int written);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool VirtualProtectEx(IntPtr process, IntPtr address, IntPtr size, uint protect, out uint old);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool FlushInstructionCache(IntPtr process, IntPtr address, IntPtr size);
    [DllImport("kernel32", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32")]
    static extern bool CloseHandle(IntPtr handle);
    [DllImport("user32", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr owner, string text, string caption, uint type);

    static readonly string LogFile = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\logs\side-by-side.log"));

    static void Log(string message)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(LogFile));
            File.AppendAllText(LogFile, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message + Environment.NewLine);
        }
        catch { }
    }

    static int Fail(string message)
    {
        Log("  failed: " + message);
        MessageBoxW(IntPtr.Zero, message, "XCOM side by side", 0x10);
        return 2;
    }

    // The game folder under <common> whose marker names the copy; null when there is none.
    static string FindCopy(string common, string copy)
    {
        foreach (string dir in Directory.GetDirectories(common, "XCom-Enemy-Unknown*"))
        {
            string marker = Path.Combine(dir, "XComLab-copy.txt");
            if (!File.Exists(marker)) continue;
            foreach (string line in File.ReadAllLines(marker))
                if (line.Trim().Equals("copy=" + copy, StringComparison.OrdinalIgnoreCase)) return dir;
        }
        return null;
    }

    static int Main(string[] args)
    {
        Log("start: " + Environment.CommandLine);
        string exe = null, common = null, copy = null;
        for (int i = 0; i < args.Length && args[i] != "--"; i++)
        {
            if (args[i] == "--exe" && i + 1 < args.Length) exe = args[++i];
            else if (args[i] == "--common" && i + 1 < args.Length) common = args[++i];
            else if (args[i] == "--copy" && i + 1 < args.Length) copy = args[++i];
            else return Fail("Unknown argument: " + args[i]);
        }
        // The game's arguments are taken as typed, after the first " -- ".
        string raw = Environment.CommandLine;
        int split = raw.IndexOf(" -- ", StringComparison.Ordinal);
        string gameArgs = split < 0 ? "" : raw.Substring(split + 4).Trim();

        if (exe == null)
        {
            if (common == null || copy == null) return Fail("Give --exe <XComEW.exe>, or --common <steamapps\\common> and --copy <name>.");
            if (!Directory.Exists(common)) return Fail("Folder not found: " + common);
            string root = FindCopy(common, copy);
            if (root == null) return Fail("No XCom-Enemy-Unknown* folder under " + common + " has an XComLab-copy.txt with the line copy=" + copy + ".");
            exe = Path.Combine(root, @"XEW\Binaries\Win32\XComEW.exe");
        }
        exe = Path.GetFullPath(exe);
        if (!File.Exists(exe)) return Fail("Not found: " + exe);
        string bin = Path.GetDirectoryName(exe);
        foreach (string stray in Directory.GetFiles(bin, "steam_appid*"))
            Log("  WARNING: " + stray + " exists: XComEW.exe quits at startup until it is removed");

        Environment.SetEnvironmentVariable("SteamAppId", AppId);
        Environment.SetEnvironmentVariable("SteamGameId", AppId);
        Environment.SetEnvironmentVariable("__COMPAT_LAYER", "HIGHDPIAWARE");

        var si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
        PROCESS_INFORMATION pi;
        var cmd = new System.Text.StringBuilder("\"" + exe + "\" " + gameArgs);
        Log("  run: " + cmd + "   (cwd " + bin + ")");
        if (!CreateProcessW(exe, cmd, IntPtr.Zero, IntPtr.Zero, false, 0x4 /* CREATE_SUSPENDED */, IntPtr.Zero, bin, ref si, out pi))
            return Fail("Could not start " + exe + ": " + new Win32Exception(Marshal.GetLastWin32Error()).Message);
        try
        {
            string note = PatchInstanceCheck(pi.hProcess);
            Log("  pid " + pi.dwProcessId + ": " + note);
            if (ResumeThread(pi.hThread) == 0xFFFFFFFF)
            {
                TerminateProcess(pi.hProcess, 1);
                return Fail("Could not resume the game: " + new Win32Exception(Marshal.GetLastWin32Error()).Message);
            }
            if (!note.StartsWith("patched"))
                MessageBoxW(IntPtr.Zero, "The game was started without the side-by-side change (" + note + "). It will quit at once if another copy of XCOM is running.", "XCOM side by side", 0x30);
            return 0;
        }
        finally
        {
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
        }
    }

    // Replaces the call that makes the one-instance mutex. Returns "patched ..." or the reason it was left alone.
    static string PatchInstanceCheck(IntPtr process)
    {
        var info = new PROCESS_BASIC_INFORMATION();
        int ret, n;
        int status = NtQueryInformationProcess(process, 0, ref info, Marshal.SizeOf(typeof(PROCESS_BASIC_INFORMATION)), out ret);
        if (status != 0 || info.PebBaseAddress == IntPtr.Zero) return "could not find the process's PEB (status 0x" + status.ToString("X8") + ")";
        byte[] word = new byte[4];
        if (!ReadProcessMemory(process, new IntPtr(info.PebBaseAddress.ToInt64() + 8), word, 4, out n) || n != 4)
            return "could not read the image base: " + new Win32Exception(Marshal.GetLastWin32Error()).Message;
        uint imageBase = BitConverter.ToUInt32(word, 0);
        IntPtr address = new IntPtr(unchecked((int)(imageBase + CallRva)));
        byte[] now = new byte[Expected.Length];
        if (!ReadProcessMemory(process, address, now, now.Length, out n) || n != now.Length)
            return "could not read the code at 0x" + (imageBase + CallRva).ToString("X8") + ": " + new Win32Exception(Marshal.GetLastWin32Error()).Message;
        for (int i = 0; i < now.Length; i++)
            if (now[i] != Expected[i]) return "the exe differs from the one this tool knows (bytes " + BitConverter.ToString(now) + " at base+0x" + CallRva.ToString("X") + ")";
        uint old, ignored;
        if (!VirtualProtectEx(process, address, new IntPtr(Patch.Length), 0x40 /* PAGE_EXECUTE_READWRITE */, out old))
            return "could not unprotect the code: " + new Win32Exception(Marshal.GetLastWin32Error()).Message;
        bool wrote = WriteProcessMemory(process, address, Patch, Patch.Length, out n) && n == Patch.Length;
        int error = Marshal.GetLastWin32Error();
        VirtualProtectEx(process, address, new IntPtr(Patch.Length), old, out ignored);
        FlushInstructionCache(process, address, new IntPtr(Patch.Length));
        if (!wrote) return "could not write the change: " + new Win32Exception(error).Message;
        return "patched the one-instance check at 0x" + (imageBase + CallRva).ToString("X8") + " (image base 0x" + imageBase.ToString("X8") + ")";
    }
}
