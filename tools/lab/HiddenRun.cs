// Runs a command on a private Windows desktop that is never switched onto the user's displays, so the windows it
// opens (the UDK editor, its Save dialogs) can't take the user's foreground or keyboard focus.
//
//   HiddenRun.exe [--desktop <name>] [--timeout <seconds>] -- <exe> [args...]
//
// - Everything the command starts inherits the desktop. Window lookups and window messages only work within one
//   desktop, so the tools that drive the editor must run inside the same HiddenRun command as the editor itself.
// - The command and its children share a job that is killed when the command exits or times out, or when HiddenRun
//   is stopped. Standard input is an already-closed pipe; standard output and error are passed through.
// - Not every program runs there: UDK.com (the cooker) exits at once with code 3 and no output, with or without a
//   console of its own, so patchtool cooks on the user's desktop.
// - The clipboard belongs to the window station, which is shared with the user's desktop.
// - Exit code: the command's, or 124 on timeout.
//
// Build: csc /nologo /target:exe /platform:anycpu /out:<lab>\bin\HiddenRun.exe tools\lab\HiddenRun.cs
// (patchtool.ps1 and udk_bake.ps1 compile it themselves when it is missing or older than this source.)
using System;
using System.ComponentModel;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class HiddenRun
{
    static int Main(string[] args)
    {
        string desktop = "XComLab-UDK";
        int timeout = 0, i = 0;
        for (; i < args.Length && args[i] != "--"; i++)
        {
            if (args[i] == "--desktop") desktop = args[++i];
            else if (args[i] == "--timeout") timeout = int.Parse(args[++i]);
            else { Console.Error.WriteLine("usage: HiddenRun [--desktop name] [--timeout s] -- exe [args...]"); return 2; }
        }
        if (i + 1 >= args.Length) { Console.Error.WriteLine("usage: HiddenRun [--desktop name] [--timeout s] -- exe [args...]"); return 2; }
        string exe = args[i + 1];
        var rest = new string[args.Length - i - 2];
        Array.Copy(args, i + 2, rest, 0, rest.Length);
        try { return Run(desktop, exe, rest, timeout); }
        catch (Exception e) { Console.Error.WriteLine("HiddenRun: " + e.Message); return 1; }
    }

    static int Run(string name, string exe, string[] arguments, int timeoutSeconds)
    {
        IntPtr desk = CreateDesktop(name, IntPtr.Zero, IntPtr.Zero, 0, 0x000F01FF, IntPtr.Zero);   // opens it if it exists
        if (desk == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot create desktop " + name);
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot create a job");
        try
        {
            var limits = new ExtendedLimits();
            limits.basic.flags = KillOnJobClose;
            if (!SetInformationJobObject(job, ExtendedLimitInformation, ref limits, Marshal.SizeOf(typeof(ExtendedLimits))))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot configure the job");
            using (var pipe = new AnonymousPipeServerStream(PipeDirection.In, HandleInheritability.Inheritable))
            {
                var input = new AnonymousPipeServerStream(PipeDirection.Out, HandleInheritability.Inheritable);
                IntPtr client = pipe.ClientSafePipeHandle.DangerousGetHandle();
                var startup = new StartupInfo { cb = Marshal.SizeOf(typeof(StartupInfo)), desktop = name, dwFlags = UseShowWindow | UseStdHandles, wShowWindow = 1,
                    input = input.ClientSafePipeHandle.DangerousGetHandle(), output = client, error = client };
                ProcessInfo info;
                if (!CreateProcess(Path.IsPathRooted(exe) ? exe : null, CommandLine(exe, arguments), IntPtr.Zero, IntPtr.Zero, true,
                                   CreateNoWindow | CreateSuspended, IntPtr.Zero, Environment.CurrentDirectory, ref startup, out info))
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot start " + exe);
                pipe.DisposeLocalCopyOfClientHandle(); input.Dispose();
                try
                {
                    if (!AssignProcessToJobObject(job, info.process)) throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot put the command in its job");
                    ResumeThread(info.thread);
                    var reader = new Thread(() =>
                    {
                        using (var lines = new StreamReader(pipe, Encoding.UTF8))
                            for (string line; (line = lines.ReadLine()) != null;) Console.WriteLine(line);
                    });
                    reader.IsBackground = true; reader.Start();
                    uint wait = WaitForSingleObject(info.process, timeoutSeconds > 0 ? (uint)timeoutSeconds * 1000 : uint.MaxValue);
                    if (wait != 0) { Console.Error.WriteLine("HiddenRun: timed out after " + timeoutSeconds + " s; ending the command"); CloseHandle(job); job = IntPtr.Zero; reader.Join(3000); return 124; }
                    uint code;
                    if (!GetExitCodeProcess(info.process, out code)) throw new Win32Exception(Marshal.GetLastWin32Error(), "cannot read the exit code");
                    if (!reader.Join(3000)) { CloseHandle(job); job = IntPtr.Zero; reader.Join(3000); }
                    return unchecked((int)code);
                }
                finally { CloseHandle(info.thread); CloseHandle(info.process); }
            }
        }
        finally { if (job != IntPtr.Zero) CloseHandle(job); CloseDesktop(desk); }
    }

    static StringBuilder CommandLine(string exe, string[] arguments)
    {
        var sb = new StringBuilder(Quote(exe));
        foreach (string a in arguments) sb.Append(' ').Append(Quote(a));
        return sb;
    }

    static string Quote(string value)
    {
        if (value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) return value;
        var result = new StringBuilder("\""); int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { result.Append('\\', slashes * 2 + 1); result.Append(c); }
            else { result.Append('\\', slashes); result.Append(c); }
            slashes = 0;
        }
        result.Append('\\', slashes * 2); return result.Append('"').ToString();
    }

    const uint CreateNoWindow = 0x08000000, CreateSuspended = 0x4, KillOnJobClose = 0x2000;
    const int UseShowWindow = 0x1, UseStdHandles = 0x100, ExtendedLimitInformation = 9;
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] struct StartupInfo
    {
        public int cb; public string reserved, desktop, title; public int x, y, width, height, xChars, yChars, fill, dwFlags;
        public short wShowWindow, reservedSize; public IntPtr reservedBytes, input, output, error;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process, thread; public uint processId, threadId; }
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits { public long perProcessTime, perJobTime; public uint flags; public UIntPtr minimumWorkingSet, maximumWorkingSet; public uint activeProcesses; public UIntPtr affinity; public uint priority, schedulingClass; }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong reads, writes, others, readBytes, writeBytes, otherBytes; }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits { public BasicLimits basic; public IoCounters io; public UIntPtr processMemory, jobMemory, peakProcessMemory, peakJobMemory; }
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr CreateDesktop(string name, IntPtr device, IntPtr mode, uint flags, uint access, IntPtr security);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("kernel32.dll", EntryPoint = "CreateProcessW", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CreateProcess(string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, bool inherit, uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInfo info);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetInformationJobObject(IntPtr job, int kind, ref ExtendedLimits info, int length);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetExitCodeProcess(IntPtr process, out uint code);
}
