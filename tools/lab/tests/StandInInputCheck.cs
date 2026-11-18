// A 32-bit check of the stand-in dinput8.dll outside the game (test_stand_in_input.py compiles and runs it):
//   StandInInputCheck.exe <dinput8.dll>
// It makes DirectInput through the DLL, asks for the system mouse and keyboard, and plays the calls the game makes
// on a device (SetDataFormat, SetCooperativeLevel, Acquire, GetDeviceState, GetDeviceData, GetCapabilities,
// GetDeviceInfo, Release). One line a result; exit code 0 when every call answered as a stand-in should, 1 if not.
// With XCOM_STAND_IN_INPUT=always the devices are the stand-ins; without it, Windows' own where Windows has them
// (then only CreateDevice is checked).
using System;
using System.Runtime.InteropServices;

static class StandInInputCheck
{
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32", CharSet = CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32")] static extern IntPtr GetModuleHandleW(IntPtr name);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int Create8(IntPtr instance, uint version, ref Guid iid, out IntPtr result, IntPtr outer);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int CreateDevice(IntPtr self, ref Guid guid, out IntPtr device, IntPtr outer);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Call0(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Call1(IntPtr self, IntPtr a);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Call2(IntPtr self, IntPtr a, IntPtr b);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Call4(IntPtr self, IntPtr a, IntPtr b, IntPtr c, IntPtr d);

    static readonly Guid IID_IDirectInput8W = new Guid("BF798031-483A-4DA2-AA99-5D64ED369700");
    static readonly Guid SysMouse = new Guid("6F1D2B60-D5A0-11CF-BFC7-444553540000");
    static readonly Guid SysKeyboard = new Guid("6F1D2B61-D5A0-11CF-BFC7-444553540000");
    static int failures;

    static T Method<T>(IntPtr obj, int index) where T : class
    {
        IntPtr table = Marshal.ReadIntPtr(obj);
        return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(table, index * IntPtr.Size), typeof(T)) as T;
    }

    static void Expect(string what, bool ok, string detail)
    {
        Console.WriteLine((ok ? "ok   " : "FAIL ") + what + (detail.Length > 0 ? ": " + detail : ""));
        if (!ok) failures++;
    }

    static void Device(IntPtr input, Guid guid, string name, bool standIn)
    {
        IntPtr device;
        int hr = Method<CreateDevice>(input, 3)(input, ref guid, out device, IntPtr.Zero);
        Expect(name + " CreateDevice", hr == 0 && device != IntPtr.Zero, string.Format("0x{0:x8}", hr));
        if (device == IntPtr.Zero || !standIn) return;
        IntPtr buffer = Marshal.AllocHGlobal(1200);
        try
        {
            Expect(name + " SetDataFormat", Method<Call1>(device, 11)(device, buffer) == 0, "");
            Expect(name + " SetCooperativeLevel", Method<Call2>(device, 13)(device, IntPtr.Zero, new IntPtr(6)) == 0, "");
            Expect(name + " Acquire", Method<Call0>(device, 7)(device) == 0, "");
            for (int i = 0; i < 256; i++) Marshal.WriteByte(buffer, i, 0xFF);
            int state = Method<Call2>(device, 9)(device, new IntPtr(256), buffer);
            bool zero = true;
            for (int i = 0; i < 256; i++) if (Marshal.ReadByte(buffer, i) != 0) zero = false;
            Expect(name + " GetDeviceState", state == 0 && zero, zero ? "all zero" : "not zero");
            IntPtr count = Marshal.AllocHGlobal(4);
            Marshal.WriteInt32(count, 32);
            int data = Method<Call4>(device, 10)(device, new IntPtr(16), buffer, count, IntPtr.Zero);
            Expect(name + " GetDeviceData", data == 0 && Marshal.ReadInt32(count) == 0, "events " + Marshal.ReadInt32(count));
            Marshal.FreeHGlobal(count);
            Marshal.WriteInt32(buffer, 44);                       // DIDEVCAPS
            int caps = Method<Call1>(device, 3)(device, buffer);
            Expect(name + " GetCapabilities", caps == 0 && (Marshal.ReadInt32(buffer, 4) & 1) == 1,
                   string.Format("type 0x{0:x}", Marshal.ReadInt32(buffer, 8)));
            Marshal.WriteInt32(buffer, 1100);                     // DIDEVICEINSTANCEW
            int info = Method<Call1>(device, 15)(device, buffer);
            byte[] product = new byte[16];
            Marshal.Copy(new IntPtr(buffer.ToInt64() + 20), product, 0, 16);
            Expect(name + " GetDeviceInfo", info == 0 && new Guid(product) == guid, new Guid(product).ToString());
            Expect(name + " Unacquire", Method<Call0>(device, 8)(device) == 0, "");
            Method<Call0>(device, 2)(device);
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    static int Main(string[] args)
    {
        if (args.Length != 1) { Console.WriteLine("usage: StandInInputCheck <dinput8.dll>"); return 2; }
        IntPtr dll = LoadLibraryW(args[0]);
        if (dll == IntPtr.Zero) { Console.WriteLine("FAIL load " + args[0] + ": " + Marshal.GetLastWin32Error()); return 1; }
        IntPtr proc = GetProcAddress(dll, "DirectInput8Create");
        if (proc == IntPtr.Zero) { Console.WriteLine("FAIL no DirectInput8Create"); return 1; }
        Create8 create = (Create8)Marshal.GetDelegateForFunctionPointer(proc, typeof(Create8));
        Guid iid = IID_IDirectInput8W;
        IntPtr input;
        int hr = create(GetModuleHandleW(IntPtr.Zero), 0x0800, ref iid, out input, IntPtr.Zero);
        Expect("DirectInput8Create", hr == 0 && input != IntPtr.Zero, string.Format("0x{0:x8}", hr));
        if (input == IntPtr.Zero) return 1;
        bool standIn = Environment.GetEnvironmentVariable("XCOM_STAND_IN_INPUT") == "always";
        Device(input, SysMouse, "mouse", standIn);
        Device(input, SysKeyboard, "keyboard", standIn);
        return failures == 0 ? 0 : 1;
    }
}
