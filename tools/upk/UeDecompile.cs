// Decompiles UnrealScript from a UE3 package with UE Explorer's own library (Eliot.UELib), without its GUI.
//
//   UeDecompile.exe <package> <Class>                 the whole class
//   UeDecompile.exe <package> <Class>.<Function>      one function (or state) of it
//   UeDecompile.exe <package> --find <text>           objects whose path contains <text>
//   UeDecompile.exe <package> --all <folder>          every class, one <Class>.uc file each
//
// Reads the package only. Point it at a copy of a game file, never at the LWR install.
//
// UE Explorer's folder (with Eliot.UELib.dll and its dependencies) is the UE_EXPLORER environment variable, else
// ..\tools\ue-explorer-1.6.2\ue-explorer from the exe's folder (<lab>\tools\... for <lab>\bin\UeDecompile.exe).
//
// Build (x86, because UE Explorer is):
//   csc /nologo /target:exe /platform:x86 /r:<lab>\tools\ue-explorer-1.6.2\ue-explorer\Eliot.UELib.dll
//       /out:<lab>\bin\UeDecompile.exe tools\upk\UeDecompile.cs
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using UELib;
using UELib.Core;

internal static class UeDecompile
{
    static readonly string LibDir = Environment.GetEnvironmentVariable("UE_EXPLORER") ??
        Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\tools\ue-explorer-1.6.2\ue-explorer"));

    static int Main(string[] args)
    {
        // UELib and its dependencies stay in the UE Explorer folder.
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string path = Path.Combine(LibDir, new AssemblyName(e.Name).Name + ".dll");
            return File.Exists(path) ? Assembly.LoadFrom(path) : null;
        };
        if (args.Length < 2) { Console.Error.WriteLine("usage: UeDecompile <package> <Class>[.<Function>] | --find <text>"); return 2; }
        return Run(args);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static int Run(string[] args)
    {
        UnrealPackage package = UnrealLoader.LoadFullPackage(args[0], FileAccess.Read);
        var objects = package.Objects.Where(o => o != null && o.ExportTable != null).ToList();
        if (args[1] == "--find")
        {
            foreach (UObject o in objects.Where(o => o.GetPath().IndexOf(args[2], StringComparison.OrdinalIgnoreCase) >= 0))
                Console.WriteLine(o.GetType().Name + "  " + o.GetPath());
            return 0;
        }
        if (args[1] == "--all")
        {
            Directory.CreateDirectory(args[2]);
            int failed = 0;
            foreach (UClass c in objects.OfType<UClass>())
            {
                string text;
                try { c.BeginDeserializing(); text = c.Decompile(); }
                catch (Exception e) { text = "// decompile failed: " + e.Message; failed++; }
                File.WriteAllText(Path.Combine(args[2], c.Name + ".uc"), text);
            }
            Console.WriteLine(objects.OfType<UClass>().Count() + " classes, " + failed + " failed");
            return 0;
        }
        string[] parts = args[1].Split('.');
        UObject target = parts.Length == 1
            ? objects.FirstOrDefault(o => o is UClass && o.Name.ToString().Equals(parts[0], StringComparison.OrdinalIgnoreCase))
            : objects.FirstOrDefault(o => o is UStruct && o.Name.ToString().Equals(parts[1], StringComparison.OrdinalIgnoreCase)
                                          && o.Outer != null && o.Outer.Name.ToString().Equals(parts[0], StringComparison.OrdinalIgnoreCase));
        if (target == null) { Console.Error.WriteLine("not found: " + args[1]); return 1; }
        target.BeginDeserializing();
        Console.WriteLine(target.Decompile());
        return 0;
    }
}
