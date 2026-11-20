"""A named Windows mutex the editor's server holds while it runs (review finding 60).

Setup names it (installer.iss, AppMutex), so an upgrade or an uninstall started while the editor runs asks for the
editor to be closed first, instead of replacing the python and tools folders a running editor holds open. The
mutex is made in the session's namespace and in Global\\ (another session's Setup sees that one), and lives as long
as the server's process: Windows closes it when the process ends, however it ends.
"""
import ctypes
import sys

NAME = 'XCOMMapWorkshopEditor'
SYNCHRONIZE = 0x00100000
_held = []


def _kernel32():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateMutexW.restype = ctypes.c_void_p
    k.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    k.OpenMutexW.restype = ctypes.c_void_p
    k.OpenMutexW.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p)
    k.CloseHandle.argtypes = (ctypes.c_void_p,)
    return k


def hold(name=NAME):
    """Make (or open) the mutex in both namespaces and keep the handles for the process's life. Returns how many were
    made: 0 off Windows or when Windows refuses (the editor runs all the same; Setup then can't tell it runs)."""
    if sys.platform != 'win32':
        return 0
    try:
        k = _kernel32()
    except (OSError, AttributeError):
        return 0
    for full in (name, 'Global\\' + name):
        handle = k.CreateMutexW(None, False, full)
        if handle:
            _held.append(handle)
    return len(_held)


def exists(name=NAME):
    """Whether a mutex of that name is held by some process now (as Setup asks it)."""
    if sys.platform != 'win32':
        return False
    k = _kernel32()
    handle = k.OpenMutexW(SYNCHRONIZE, False, name)
    if not handle:
        return False
    k.CloseHandle(handle)
    return True


def release():
    """Close the handles this process holds (for tests; the server keeps them until it ends)."""
    if sys.platform != 'win32':
        return
    k = _kernel32()
    while _held:
        k.CloseHandle(_held.pop())
