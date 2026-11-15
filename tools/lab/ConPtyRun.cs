// Runs a console program inside a Windows pseudo console (ConPTY) and copies everything it prints to a log file.
//
// For tools that need a real console and crash when their output is redirected, such as XCOM-Uncooker.exe
// (it sets Console.CursorVisible). The log keeps the raw output, including terminal escape sequences.
//
//   ConPtyRun.exe [--size=<cols>x<rows>] <log file> <command line...>
//   ConPtyRun.exe --size=240x400 <lab>\logs\exp02-uncooker.vt "<lab>\tools\...\XCOM-Uncooker.exe" "<in>" "<out>"
//
// The pseudo console has no scrollback beyond its size (default 200x50); the Uncooker's progress windows need
// more rows than that.
//
// Exits with the program's exit code. Build:
//   csc /nologo /target:exe /platform:x64 /out:<lab>\bin\ConPtyRun.exe tools\lab\ConPtyRun.cs
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32.SafeHandles;

internal static class ConPtyRun
{
    [StructLayout(LayoutKind.Sequential)] struct COORD { public short X, Y; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO
    {
        public int cb; public string lpReserved, lpDesktop, lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }
    [StructLayout(LayoutKind.Sequential)] struct STARTUPINFOEX { public STARTUPINFO StartupInfo; public IntPtr lpAttributeList; }
    [StructLayout(LayoutKind.Sequential)] struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public int dwProcessId, dwThreadId; }

    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CreatePipe(out SafeFileHandle read, out SafeFileHandle write, IntPtr attrs, int size);
    [DllImport("kernel32.dll", SetLastError = true)] static extern int CreatePseudoConsole(COORD size, SafeFileHandle input, SafeFileHandle output, uint flags, out IntPtr pc);
    [DllImport("kernel32.dll", SetLastError = true)] static extern void ClosePseudoConsole(IntPtr pc);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool InitializeProcThreadAttributeList(IntPtr list, int count, int flags, ref IntPtr size);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool UpdateProcThreadAttribute(IntPtr list, uint flags, IntPtr attr, IntPtr value, IntPtr size, IntPtr prev, IntPtr retSize);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool CreateProcess(string app, string cmd, IntPtr pa, IntPtr ta, bool inherit, uint flags, IntPtr env, string dir, ref STARTUPINFOEX si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)] static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);

    const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
    static readonly IntPtr PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = (IntPtr)0x00020016;

    static int Main(string[] args)
    {
        short cols = 200, rows = 50;
        int first = 0;
        if (args.Length > 0 && args[0].StartsWith("--size="))
        {
            string[] wh = args[0].Substring(7).Split('x');
            cols = short.Parse(wh[0]); rows = short.Parse(wh[1]); first = 1;
        }
        if (args.Length < first + 2) { Console.Error.WriteLine("usage: ConPtyRun [--size=<cols>x<rows>] <log file> <command line...>"); return 2; }
        string log = args[first];
        // Rebuild the child's command line from the raw one, so its quoting is passed through untouched.
        string raw = Environment.CommandLine;
        int skip = 0;
        for (int t = 0; t < first + 2; t++)
        {
            while (skip < raw.Length && raw[skip] == ' ') skip++;
            bool quoted = skip < raw.Length && raw[skip] == '"';
            skip++;
            while (skip < raw.Length && (quoted ? raw[skip] != '"' : raw[skip] != ' ')) skip++;
            if (quoted) skip++;
        }
        string commandLine = raw.Substring(skip).Trim();

        SafeFileHandle inRead, inWrite, outRead, outWrite;
        CreatePipe(out inRead, out inWrite, IntPtr.Zero, 0);
        CreatePipe(out outRead, out outWrite, IntPtr.Zero, 0);
        IntPtr pc;
        int hr = CreatePseudoConsole(new COORD { X = cols, Y = rows }, inRead, outWrite, 0, out pc);
        if (hr != 0) { Console.Error.WriteLine("CreatePseudoConsole failed: 0x" + hr.ToString("X")); return 3; }
        inRead.Dispose(); outWrite.Dispose();

        IntPtr size = IntPtr.Zero;
        InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref size);
        var si = new STARTUPINFOEX();
        si.StartupInfo.cb = Marshal.SizeOf(typeof(STARTUPINFOEX));
        si.StartupInfo.dwFlags = 0x00000100;   // STARTF_USESTDHANDLES with null handles: otherwise a child of a redirected parent writes to the parent's pipes, not the pseudo console
        si.lpAttributeList = Marshal.AllocHGlobal(size);
        InitializeProcThreadAttributeList(si.lpAttributeList, 1, 0, ref size);
        UpdateProcThreadAttribute(si.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, pc, (IntPtr)IntPtr.Size, IntPtr.Zero, IntPtr.Zero);

        using (var logStream = new FileStream(log, FileMode.Create, FileAccess.Write, FileShare.Read))
        {
            var reader = new Thread(() =>
            {
                var buffer = new byte[65536];
                using (var pipe = new FileStream(outRead, FileAccess.Read))
                {
                    int n;
                    try { while ((n = pipe.Read(buffer, 0, buffer.Length)) > 0) { logStream.Write(buffer, 0, n); logStream.Flush(); } }
                    catch (IOException) { }
                }
            });
            reader.Start();

            PROCESS_INFORMATION pi;
            if (!CreateProcess(null, commandLine, IntPtr.Zero, IntPtr.Zero, false, EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, null, ref si, out pi))
            {
                Console.Error.WriteLine("CreateProcess failed: " + Marshal.GetLastWin32Error() + " for: " + commandLine);
                ClosePseudoConsole(pc); return 4;
            }
            WaitForSingleObject(pi.hProcess, 0xFFFFFFFF);
            uint code; GetExitCodeProcess(pi.hProcess, out code);
            CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
            ClosePseudoConsole(pc);
            inWrite.Dispose();
            reader.Join(10000);
            return (int)code;
        }
    }
}
