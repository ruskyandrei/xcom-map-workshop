/* A stand-in dinput8.dll for hidden game runs (findings register T-45).

   The game asks DirectInput for the system mouse as it starts and uses what it gets without a check, so with no
   mouse in Windows (the mouse and keyboard switched to another computer, asleep or unplugged) it crashes about 3
   seconds in. Put beside XComEW.exe for a run, this DLL is loaded instead of Windows' own (the game imports
   DirectInput8Create from DINPUT8.dll by name). It hands every call to Windows' dinput8.dll, and when the game asks
   for the system mouse or keyboard and Windows has none, it gives a stand-in device instead: attached, acquired at
   once, never moving and with no key down. On a hidden desktop the game takes no input from DirectInput anyway (its
   window is never in front); hidden_game.py drives it by window messages and console commands.

   Environment (hidden_game.py sets them):
     XCOM_STAND_IN_INPUT=always     stand-ins for the mouse and keyboard even where Windows has them (to test this)
     XCOM_STAND_IN_INPUT_LOG=<file> a line appended for each device the game asks for and what it got

   Built by tools/lab/build_stand_in_input.py with clang-cl and lld-link: 32-bit, no C runtime, no Windows SDK (the
   few kernel32 functions it needs are declared here and imported through a library made from a .def). */

#define WINAPI __stdcall
typedef unsigned int UINT;
typedef unsigned long DWORD;
typedef unsigned long ULONG;
typedef long HRESULT;
typedef int BOOL;
typedef void *HANDLE;
typedef void *HMODULE;
typedef __WCHAR_TYPE__ WCHAR;
typedef struct { DWORD a; unsigned short b, c; unsigned char d[8]; } GUID;

__declspec(dllimport) HMODULE WINAPI LoadLibraryW(const WCHAR *name);
__declspec(dllimport) void *WINAPI GetProcAddress(HMODULE module, const char *name);
__declspec(dllimport) UINT WINAPI GetSystemDirectoryW(WCHAR *buffer, UINT size);
__declspec(dllimport) BOOL WINAPI VirtualProtect(void *address, UINT size, DWORD protect, DWORD *old);
__declspec(dllimport) DWORD WINAPI GetEnvironmentVariableW(const WCHAR *name, WCHAR *buffer, DWORD size);
__declspec(dllimport) HANDLE WINAPI CreateFileW(const WCHAR *name, DWORD access, DWORD share, void *security,
                                                DWORD disposition, DWORD flags, HANDLE templ);
__declspec(dllimport) BOOL WINAPI WriteFile(HANDLE file, const void *data, DWORD size, DWORD *written, void *overlapped);
__declspec(dllimport) BOOL WINAPI CloseHandle(HANDLE file);

#pragma comment(linker, "/EXPORT:DirectInput8Create=_DirectInput8Create@20")
#pragma comment(linker, "/EXPORT:DllCanUnloadNow=_DllCanUnloadNow@0,PRIVATE")
#pragma comment(linker, "/EXPORT:DllGetClassObject=_DllGetClassObject@12,PRIVATE")
#pragma comment(linker, "/EXPORT:DllRegisterServer=_DllRegisterServer@0,PRIVATE")
#pragma comment(linker, "/EXPORT:DllUnregisterServer=_DllUnregisterServer@0,PRIVATE")

#define S_OK 0
#define S_FALSE 1
#define E_FAIL ((HRESULT)0x80004005L)
#define DIERR_UNSUPPORTED ((HRESULT)0x80004001L)
#define DIERR_OBJECTNOTFOUND ((HRESULT)0x80070002L)
#define DIDC_ATTACHED 0x1
#define MOUSE_TYPE (0x12 | (1 << 8))      /* DI8DEVTYPE_MOUSE, DI8DEVTYPEMOUSE_UNKNOWN */
#define KEYBOARD_TYPE (0x13 | (4 << 8))   /* DI8DEVTYPE_KEYBOARD, DI8DEVTYPEKEYBOARD_PCENH */

static const GUID SYS_MOUSE = {0x6F1D2B60, 0xD5A0, 0x11CF, {0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00}};
static const GUID SYS_KEYBOARD = {0x6F1D2B61, 0xD5A0, 0x11CF, {0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00}};

/* (no C runtime: the compiler may still call memset for a loop of its own) */
void *memset(void *to, int value, unsigned int size)
{
    unsigned char *p = (unsigned char *)to;
    while (size--) *p++ = (unsigned char)value;
    return to;
}

static int same_guid(const GUID *a, const GUID *b)
{
    const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
    int i;
    if (!a || !b) return 0;
    for (i = 0; i < 16; i++) if (x[i] != y[i]) return 0;
    return 1;
}

/* ------------------------------------------------------------------ the log and the environment */

static int env_is(const WCHAR *name, const WCHAR *value)
{
    WCHAR got[16];
    DWORD n = GetEnvironmentVariableW(name, got, 16), i;
    if (!n || n >= 16) return 0;
    for (i = 0; i <= n; i++) if (got[i] != value[i]) return 0;
    return 1;
}

static void log_line(const char *text)
{
    WCHAR path[520];
    DWORD n = GetEnvironmentVariableW(L"XCOM_STAND_IN_INPUT_LOG", path, 520), size = 0, written;
    HANDLE file;
    if (!n || n >= 520) return;
    file = CreateFileW(path, 0x4 /* FILE_APPEND_DATA */, 0x3, 0, 4 /* OPEN_ALWAYS */, 0x80, 0);
    if (file == (HANDLE)-1) return;
    while (text[size]) size++;
    WriteFile(file, text, size, &written, 0);
    WriteFile(file, "\r\n", 2, &written, 0);
    CloseHandle(file);
}

/* ------------------------------------------------------------------ the stand-in device */

typedef struct StandIn { void **vtbl; ULONG refs; DWORD type; const GUID *guid; } StandIn;

static HRESULT WINAPI query_interface(StandIn *self, const GUID *iid, void **out)
{
    (void)iid;
    if (!out) return E_FAIL;
    *out = self;
    self->refs++;
    return S_OK;
}
static ULONG WINAPI add_ref(StandIn *self) { return ++self->refs; }
static ULONG WINAPI release(StandIn *self) { return self->refs > 1 ? --self->refs : 1; }

static HRESULT WINAPI get_capabilities(StandIn *self, DWORD *caps)
{
    DWORD size, i;
    if (!caps) return E_FAIL;
    size = caps[0] / 4;
    for (i = 1; i < size; i++) caps[i] = 0;
    if (size > 1) caps[1] = DIDC_ATTACHED;
    if (size > 2) caps[2] = self->type;
    if (size > 3) caps[3] = self->type == MOUSE_TYPE ? 3 : 0;          /* axes */
    if (size > 4) caps[4] = self->type == MOUSE_TYPE ? 8 : 128;        /* buttons, keys */
    return S_OK;
}

static HRESULT WINAPI get_device_state(StandIn *self, DWORD size, void *data)
{
    (void)self;
    if (data) memset(data, 0, size);
    return S_OK;
}

static HRESULT WINAPI get_device_data(StandIn *self, DWORD object_size, void *data, DWORD *count, DWORD flags)
{
    (void)self; (void)object_size; (void)data; (void)flags;
    if (count) *count = 0;
    return S_OK;
}

static HRESULT WINAPI get_object_info(StandIn *self, void *info, DWORD object, DWORD how)
{
    (void)self; (void)info; (void)object; (void)how;
    return DIERR_OBJECTNOTFOUND;
}

static HRESULT WINAPI get_device_info(StandIn *self, unsigned char *info)
{
    DWORD size;
    if (!info) return E_FAIL;
    size = *(DWORD *)info;
    if (size < 40) return E_FAIL;
    memset(info + 4, 0, size - 4);
    *(GUID *)(info + 4) = *self->guid;      /* guidInstance */
    *(GUID *)(info + 20) = *self->guid;     /* guidProduct */
    *(DWORD *)(info + 36) = self->type;     /* dwDevType */
    return S_OK;
}

/* the rest, by how many arguments they take after the device (a __stdcall method pops its own) */
static HRESULT WINAPI ok0(StandIn *s) { (void)s; return S_OK; }
static HRESULT WINAPI ok1(StandIn *s, void *a) { (void)s; (void)a; return S_OK; }
static HRESULT WINAPI ok2(StandIn *s, void *a, void *b) { (void)s; (void)a; (void)b; return S_OK; }
static HRESULT WINAPI ok3(StandIn *s, void *a, void *b, void *c) { (void)s; (void)a; (void)b; (void)c; return S_OK; }
static HRESULT WINAPI no1(StandIn *s, void *a) { (void)s; (void)a; return DIERR_UNSUPPORTED; }
static HRESULT WINAPI no2(StandIn *s, void *a, void *b) { (void)s; (void)a; (void)b; return DIERR_UNSUPPORTED; }
static HRESULT WINAPI no3(StandIn *s, void *a, void *b, void *c) { (void)s; (void)a; (void)b; (void)c; return DIERR_UNSUPPORTED; }
static HRESULT WINAPI no4(StandIn *s, void *a, void *b, void *c, void *d)
{ (void)s; (void)a; (void)b; (void)c; (void)d; return DIERR_UNSUPPORTED; }

/* IDirectInputDevice8's methods in order (the A and W interfaces share the layout) */
static void *DEVICE_METHODS[32] = {
    (void *)query_interface,    /*  0 QueryInterface(iid, out) */
    (void *)add_ref,            /*  1 AddRef */
    (void *)release,            /*  2 Release */
    (void *)get_capabilities,   /*  3 GetCapabilities(caps) */
    (void *)ok3,                /*  4 EnumObjects(callback, ref, flags): none */
    (void *)no2,                /*  5 GetProperty(guid, header) */
    (void *)ok2,                /*  6 SetProperty(guid, header) */
    (void *)ok0,                /*  7 Acquire */
    (void *)ok0,                /*  8 Unacquire */
    (void *)get_device_state,   /*  9 GetDeviceState(size, data): all zero */
    (void *)get_device_data,    /* 10 GetDeviceData(size, data, count, flags): no events */
    (void *)ok1,                /* 11 SetDataFormat(format) */
    (void *)ok1,                /* 12 SetEventNotification(event) */
    (void *)ok2,                /* 13 SetCooperativeLevel(window, flags) */
    (void *)get_object_info,    /* 14 GetObjectInfo(info, object, how) */
    (void *)get_device_info,    /* 15 GetDeviceInfo(info) */
    (void *)no2,                /* 16 RunControlPanel(window, flags) */
    (void *)ok3,                /* 17 Initialize(instance, version, guid) */
    (void *)no4,                /* 18 CreateEffect(guid, effect, out, outer) */
    (void *)ok3,                /* 19 EnumEffects(callback, ref, type): none */
    (void *)no2,                /* 20 GetEffectInfo(info, guid) */
    (void *)no1,                /* 21 GetForceFeedbackState(out) */
    (void *)no1,                /* 22 SendForceFeedbackCommand(flags) */
    (void *)ok3,                /* 23 EnumCreatedEffectObjects(callback, ref, flags): none */
    (void *)no1,                /* 24 Escape(escape) */
    (void *)ok0,                /* 25 Poll */
    (void *)no4,                /* 26 SendDeviceData(size, data, count, flags) */
    (void *)no4,                /* 27 EnumEffectsInFile(file, callback, ref, flags) */
    (void *)no4,                /* 28 WriteEffectToFile(file, count, effects, flags) */
    (void *)no3,                /* 29 BuildActionMap(format, user, flags) */
    (void *)no3,                /* 30 SetActionMap(format, user, flags) */
    (void *)no1,                /* 31 GetImageInfo(header) */
};

static StandIn MOUSE = {DEVICE_METHODS, 1, MOUSE_TYPE, &SYS_MOUSE};
static StandIn KEYBOARD = {DEVICE_METHODS, 1, KEYBOARD_TYPE, &SYS_KEYBOARD};

/* ------------------------------------------------------------------ Windows' DirectInput, with CreateDevice watched */

typedef HRESULT(WINAPI *Create8)(HMODULE, DWORD, const GUID *, void **, void *);
typedef HRESULT(WINAPI *CreateDevice)(void *, const GUID *, void **, void *);
typedef HRESULT(WINAPI *Plain)(void);
typedef HRESULT(WINAPI *ClassObject)(const GUID *, const GUID *, void **);

static HMODULE windows_dll;
static CreateDevice windows_create_device;

static void *windows_proc(const char *name)
{
    if (!windows_dll) {
        WCHAR path[300];
        const WCHAR *file = L"\\dinput8.dll";
        UINT n = GetSystemDirectoryW(path, 280), i;
        if (!n || n >= 280) return 0;
        for (i = 0; file[i]; i++) path[n + i] = file[i];
        path[n + i] = 0;
        windows_dll = LoadLibraryW(path);
        if (!windows_dll) return 0;
    }
    return GetProcAddress(windows_dll, name);
}

static HRESULT WINAPI create_device(void *self, const GUID *guid, void **out, void *outer)
{
    StandIn *stand_in = same_guid(guid, &SYS_MOUSE) ? &MOUSE : same_guid(guid, &SYS_KEYBOARD) ? &KEYBOARD : 0;
    HRESULT result;
    if (stand_in && out && env_is(L"XCOM_STAND_IN_INPUT", L"always")) {
        *out = stand_in;
        log_line(stand_in == &MOUSE ? "system mouse: the stand-in (asked for)" : "system keyboard: the stand-in (asked for)");
        return S_OK;
    }
    result = windows_create_device(self, guid, out, outer);
    if (stand_in && out && (result < 0 || !*out)) {
        *out = stand_in;
        log_line(stand_in == &MOUSE ? "system mouse: the stand-in (Windows has none)" : "system keyboard: the stand-in (Windows has none)");
        return S_OK;
    }
    if (stand_in) log_line(stand_in == &MOUSE ? "system mouse: Windows' own" : "system keyboard: Windows' own");
    return result;
}

static void watch(void *direct_input)
{
    void **methods = *(void ***)direct_input;
    DWORD old;
    if (methods[3] == (void *)create_device) return;
    if (!VirtualProtect(&methods[3], sizeof(void *), 0x04 /* PAGE_READWRITE */, &old)) {
        log_line("could not watch DirectInput's CreateDevice");
        return;
    }
    windows_create_device = (CreateDevice)methods[3];
    methods[3] = (void *)create_device;
    VirtualProtect(&methods[3], sizeof(void *), old, &old);
}

HRESULT WINAPI DirectInput8Create(HMODULE instance, DWORD version, const GUID *iid, void **out, void *outer)
{
    Create8 create = (Create8)windows_proc("DirectInput8Create");
    HRESULT result;
    if (!create) {
        log_line("Windows' dinput8.dll not found");
        return E_FAIL;
    }
    result = create(instance, version, iid, out, outer);
    if (result >= 0 && out && *out) watch(*out);
    return result;
}

HRESULT WINAPI DllCanUnloadNow(void) { return S_FALSE; }

HRESULT WINAPI DllGetClassObject(const GUID *clsid, const GUID *iid, void **out)
{
    ClassObject f = (ClassObject)windows_proc("DllGetClassObject");
    return f ? f(clsid, iid, out) : E_FAIL;
}

HRESULT WINAPI DllRegisterServer(void)
{
    Plain f = (Plain)windows_proc("DllRegisterServer");
    return f ? f() : E_FAIL;
}

HRESULT WINAPI DllUnregisterServer(void)
{
    Plain f = (Plain)windows_proc("DllUnregisterServer");
    return f ? f() : E_FAIL;
}
