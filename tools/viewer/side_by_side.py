"""Starting XComEW.exe so that it runs beside another copy's running game (Play in game; findings register T-52).

The game allows one instance per Windows session by itself: WinMain (0xBF0911 at the exe's preferred base 0x400000)
calls a function (0xEEF7E0) that makes the named mutex UnrealEngine3_8 and returns 0 when it exists already, and WinMain
then returns 1 at once. Steam, for its part, starts none of XCOM's while a game of any copy runs ("game is already
running"). So a play beside another copy's game starts the install's XComEW.exe itself, as the lab's
XComSideBySide.exe does (tools/lab/XComSideBySide.cs): suspended, that one call replaced in the new process's memory
with `mov eax, 1` (as if it were the first instance), then resumed. No file is changed. The bytes are checked first:
an exe that differs is ended before it runs, and the play says why.

The game gets SteamAppId and SteamGameId, which a game started outside Steam needs (F-84), and
__COMPAT_LAYER=HIGHDPIAWARE, without which Windows scales a copy started from a folder with no compatibility setting
of its own and the game saves the wrong size (T-48). It starts in its own XEW\\Binaries\\Win32, out of the server's
job where Windows allows that, so it outlives the server as a game Steam starts does.

The exe is 32-bit; the server's Python may be either. Windows only (start raises elsewhere).
"""
import ctypes
import os
import subprocess
import sys

CALL_RVA = 0x7F0911                                    # 0xBF0911 - 0x400000
EXPECTED = bytes((0xE8, 0xCA, 0xEE, 0x2F, 0x00))       # call 0xEEF7E0
PATCH = bytes((0xB8, 0x01, 0x00, 0x00, 0x00))          # mov eax, 1
APP_ID = '200510'
ENVIRONMENT = {'SteamAppId': APP_ID, 'SteamGameId': APP_ID, '__COMPAT_LAYER': 'HIGHDPIAWARE'}

CREATE_SUSPENDED, DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP = 0x4, 0x8, 0x200
CREATE_UNICODE_ENVIRONMENT, CREATE_BREAKAWAY_FROM_JOB = 0x400, 0x01000000
ERROR_ACCESS_DENIED = 5
PAGE_EXECUTE_READWRITE = 0x40


class SideBySideError(Exception):
    pass


def environment(base=None):
    """The game's environment: `base` (the server's own when None) with ENVIRONMENT's variables in place of any of
    theirs, whatever their case (Windows reads names in any case)."""
    names = {k.upper() for k in ENVIRONMENT}
    out = {k: v for k, v in (os.environ if base is None else base).items() if k.upper() not in names}
    out.update(ENVIRONMENT)
    return out


def environment_block(env):
    """A CreateProcessW environment block: NAME=value strings, each ended by a NUL, sorted by name in any case, and a
    NUL after the last."""
    return ''.join(f'{k}={v}\0' for k, v in sorted(env.items(), key=lambda kv: kv[0].upper())) + '\0'


def _api():
    """kernel32's and ntdll's functions, typed (a library object of this module's own, so no other module's types
    change)."""
    from ctypes import wintypes as w
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    n = ctypes.WinDLL('ntdll')

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR), ('lpTitle', w.LPWSTR),
                    ('dwX', w.DWORD), ('dwY', w.DWORD), ('dwXSize', w.DWORD), ('dwYSize', w.DWORD),
                    ('dwXCountChars', w.DWORD), ('dwYCountChars', w.DWORD), ('dwFillAttribute', w.DWORD),
                    ('dwFlags', w.DWORD), ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
                    ('lpReserved2', ctypes.c_void_p), ('hStdInput', w.HANDLE), ('hStdOutput', w.HANDLE),
                    ('hStdError', w.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE), ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]

    class PROCESS_BASIC_INFORMATION(ctypes.Structure):     # (each field pointer-sized as laid out)
        _fields_ = [('ExitStatus', ctypes.c_void_p), ('PebBaseAddress', ctypes.c_void_p),
                    ('AffinityMask', ctypes.c_void_p), ('BasePriority', ctypes.c_void_p),
                    ('UniqueProcessId', ctypes.c_void_p), ('InheritedFromUniqueProcessId', ctypes.c_void_p)]

    def typed(f, res, *args):
        f.restype, f.argtypes = res, args
        return f
    api = dict(
        STARTUPINFOW=STARTUPINFOW, PROCESS_INFORMATION=PROCESS_INFORMATION,
        PROCESS_BASIC_INFORMATION=PROCESS_BASIC_INFORMATION,
        CreateProcessW=typed(k.CreateProcessW, w.BOOL, w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
                             w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(STARTUPINFOW),
                             ctypes.POINTER(PROCESS_INFORMATION)),
        ReadProcessMemory=typed(k.ReadProcessMemory, w.BOOL, w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)),
        WriteProcessMemory=typed(k.WriteProcessMemory, w.BOOL, w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)),
        VirtualProtectEx=typed(k.VirtualProtectEx, w.BOOL, w.HANDLE, ctypes.c_void_p, ctypes.c_size_t, w.DWORD,
                               ctypes.POINTER(w.DWORD)),
        FlushInstructionCache=typed(k.FlushInstructionCache, w.BOOL, w.HANDLE, ctypes.c_void_p, ctypes.c_size_t),
        ResumeThread=typed(k.ResumeThread, w.DWORD, w.HANDLE),
        TerminateProcess=typed(k.TerminateProcess, w.BOOL, w.HANDLE, w.UINT),
        CloseHandle=typed(k.CloseHandle, w.BOOL, w.HANDLE),
        NtQueryInformationProcess=typed(n.NtQueryInformationProcess, ctypes.c_long, w.HANDLE, ctypes.c_int,
                                        ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)))
    return api


def _why(api_error=None):
    return ctypes.FormatError(api_error if api_error is not None else ctypes.get_last_error()).strip()


def read(api, process, address, size):
    """`size` bytes of the process's memory at `address`."""
    buffer, done = ctypes.create_string_buffer(size), ctypes.c_size_t()
    if not api['ReadProcessMemory'](process, address, buffer, size, ctypes.byref(done)) or done.value != size:
        raise SideBySideError(f'its memory at 0x{address:08X} can\'t be read ({_why()})')
    return buffer.raw


def image_base(api, process):
    """Where the exe lies in a 32-bit process just made, suspended: its 32-bit PEB's ImageBaseAddress (+8). The PEB is
    ProcessBasicInformation's to a 32-bit Python, ProcessWow64Information's to a 64-bit one."""
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        peb = ctypes.c_void_p()
        status = api['NtQueryInformationProcess'](process, 26, ctypes.byref(peb), ctypes.sizeof(peb), None)
        peb = peb.value
    else:
        info = api['PROCESS_BASIC_INFORMATION']()
        status = api['NtQueryInformationProcess'](process, 0, ctypes.byref(info), ctypes.sizeof(info), None)
        peb = info.PebBaseAddress
    if status != 0 or not peb:
        raise SideBySideError(f'it is not a 32-bit process, or its PEB can\'t be found (status 0x{status & 0xFFFFFFFF:08X})')
    return int.from_bytes(read(api, process, peb + 8, 4), 'little')


def patch(api, process, rva, expected, replacement):
    """Replaces the bytes `expected` at the exe's base + `rva` with `replacement` in the process; the address. Raises
    SideBySideError, the process unchanged, when the bytes there differ."""
    address = image_base(api, process) + rva
    now = read(api, process, address, len(expected))
    if now != expected:
        raise SideBySideError(f'this XComEW.exe differs from the one the editor knows how to start beside another '
                              f'game (bytes {now.hex(" ")} at its base + 0x{rva:X})')
    from ctypes import wintypes
    old, done = wintypes.DWORD(), ctypes.c_size_t()
    if not api['VirtualProtectEx'](process, address, len(replacement), PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        raise SideBySideError(f'its code can\'t be changed ({_why()})')
    try:
        buffer = ctypes.create_string_buffer(replacement, len(replacement))
        wrote = api['WriteProcessMemory'](process, address, buffer, len(replacement), ctypes.byref(done))
        error = ctypes.get_last_error()
    finally:
        api['VirtualProtectEx'](process, address, len(replacement), old.value, ctypes.byref(wintypes.DWORD()))
        api['FlushInstructionCache'](process, address, len(replacement))
    if not wrote or done.value != len(replacement):
        raise SideBySideError(f'its code can\'t be changed ({_why(error)})')
    return address


def create_suspended(api, exe, args, cwd, env):
    """A PROCESS_INFORMATION of `exe` started suspended with `args`, in `cwd`, with the environment `env`, detached
    and out of the server's job (or in it, where the job keeps its processes)."""
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(exe)] + [str(a) for a in args]))
    block = ctypes.create_unicode_buffer(environment_block(env))
    flags = CREATE_SUSPENDED | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_UNICODE_ENVIRONMENT
    for extra in (CREATE_BREAKAWAY_FROM_JOB, 0):
        si, pi = api['STARTUPINFOW'](), api['PROCESS_INFORMATION']()
        si.cb = ctypes.sizeof(si)
        if api['CreateProcessW'](str(exe), command, None, None, False, flags | extra, block, str(cwd),
                                 ctypes.byref(si), ctypes.byref(pi)):
            return pi
        error = ctypes.get_last_error()
        if not (extra and error == ERROR_ACCESS_DENIED): break
    raise SideBySideError(f'{exe} can\'t be started ({_why(error)})')


def start(exe, args, cwd=None, env=None, rva=CALL_RVA, expected=EXPECTED, replacement=PATCH, resume=True):
    """Starts `exe` (a 32-bit XComEW.exe) with `args` so that it runs beside another game: its process id. In `cwd`
    (the exe's folder when None), with `environment(env)`. Raises SideBySideError, with nothing left running, when it
    can't. rva, expected, replacement and resume are for tests (resume=False ends the process once changed)."""
    if sys.platform != 'win32': raise SideBySideError('a game is started beside another only on Windows')
    api = _api()
    pi = create_suspended(api, exe, args, cwd or os.path.dirname(os.path.abspath(exe)), environment(env))
    try:
        try:
            patch(api, pi.hProcess, rva, expected, replacement)
            if not resume:
                api['TerminateProcess'](pi.hProcess, 0)
            elif api['ResumeThread'](pi.hThread) == 0xFFFFFFFF:
                raise SideBySideError(f'the game can\'t be resumed ({_why()})')
        except BaseException:
            api['TerminateProcess'](pi.hProcess, 1)
            raise
        return pi.dwProcessId
    finally:
        api['CloseHandle'](pi.hThread)
        api['CloseHandle'](pi.hProcess)
