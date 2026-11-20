"""The server's builds as contained process trees (build queue plan, 9.3).

A build is build.py and the tools it runs (patchtool, UDK, native_copy.py, relight.py and its workers). Each launch is
contained before any of its code runs, so stopping it stops every process of it and the server's death takes them
with it:

- Windows: the process is created suspended, put in a Job Object of its own that kills its processes when its last
  handle closes (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE), then resumed. Only the server holds that handle, so a server that
  dies, however it dies, closes it and the job's processes are killed. A process that can't be put in its job is
  killed before it runs: no build runs uncontained.
- Elsewhere (the tests' other platforms): a session of its own, killed by its process group.

`terminate` kills the whole tree and `drain` waits until none of its processes is left (the job's count of active
processes, or the process group). `identity(pid)` is a process's creation time, which with its id names it (an id
alone is reused), and `tree_alive(pid, created)` lists what is still running of a tree a server started before it
restarted: the process itself and every live descendant reached through live parents. A PID read from a file is
never killed: it is only asked about.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

WINDOWS = sys.platform == 'win32'
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class ContainError(OSError):
    pass


def utf8_env(env=None):
    """The environment for a child whose output is read through a pipe as UTF-8: `env` (default this process's) with
    PYTHONUTF8 and PYTHONIOENCODING set, which every Python process below it inherits. Without them a piped Python
    child writes in the system's ANSI code page, so a folder whose name that code page lacks (a Cyrillic or Chinese
    user name under Documents, on a Western system) stops it at its first print of a path."""
    return dict(os.environ if env is None else env, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')


if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    CREATE_SUSPENDED = 0x4
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x100000
    THREAD_SUSPEND_RESUME = 0x2
    TH32CS_SNAPPROCESS, TH32CS_SNAPTHREAD = 0x2, 0x4
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectBasicAccountingInformation, JobObjectBasicProcessIdList, JobObjectExtendedLimitInformation = 1, 3, 9
    MEMBERS = 4096
    WAIT_TIMEOUT = 0x102
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _BasicLimit(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _BasicLimit), ('IoInfo', _IoCounters),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    class _Accounting(ctypes.Structure):
        _fields_ = [('TotalUserTime', ctypes.c_int64), ('TotalKernelTime', ctypes.c_int64),
                    ('ThisPeriodTotalUserTime', ctypes.c_int64), ('ThisPeriodTotalKernelTime', ctypes.c_int64),
                    ('TotalPageFaultCount', wintypes.DWORD), ('TotalProcesses', wintypes.DWORD),
                    ('ActiveProcesses', wintypes.DWORD), ('TotalTerminatedProcesses', wintypes.DWORD)]

    class _IdList(ctypes.Structure):
        _fields_ = [('NumberOfAssignedProcesses', wintypes.DWORD), ('NumberOfProcessIdsInList', wintypes.DWORD),
                    ('ProcessIdList', ctypes.c_size_t * MEMBERS)]

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ThreadID', wintypes.DWORD),
                    ('th32OwnerProcessID', wintypes.DWORD), ('tpBasePri', ctypes.c_long), ('tpDeltaPri', ctypes.c_long),
                    ('dwFlags', wintypes.DWORD)]

    class _ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]

    def _fn(name, restype, *argtypes):
        f = getattr(_k32, name)
        f.restype, f.argtypes = restype, list(argtypes)
        return f

    _CreateJobObjectW = _fn('CreateJobObjectW', wintypes.HANDLE, ctypes.c_void_p, wintypes.LPCWSTR)
    _SetInformationJobObject = _fn('SetInformationJobObject', wintypes.BOOL, wintypes.HANDLE, ctypes.c_int,
                                   ctypes.c_void_p, wintypes.DWORD)
    _QueryInformationJobObject = _fn('QueryInformationJobObject', wintypes.BOOL, wintypes.HANDLE, ctypes.c_int,
                                     ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p)
    _AssignProcessToJobObject = _fn('AssignProcessToJobObject', wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE)
    _TerminateJobObject = _fn('TerminateJobObject', wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
    _TerminateProcess = _fn('TerminateProcess', wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
    _CloseHandle = _fn('CloseHandle', wintypes.BOOL, wintypes.HANDLE)
    _OpenProcess = _fn('OpenProcess', wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _OpenThread = _fn('OpenThread', wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _ResumeThread = _fn('ResumeThread', wintypes.DWORD, wintypes.HANDLE)
    _GetProcessTimes = _fn('GetProcessTimes', wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_void_p, ctypes.c_void_p)
    _WaitForSingleObject = _fn('WaitForSingleObject', wintypes.DWORD, wintypes.HANDLE, wintypes.DWORD)
    _CreateToolhelp32Snapshot = _fn('CreateToolhelp32Snapshot', wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
    _Thread32First = _fn('Thread32First', wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p)
    _Thread32Next = _fn('Thread32Next', wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p)
    _Process32FirstW = _fn('Process32FirstW', wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p)
    _Process32NextW = _fn('Process32NextW', wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p)

    def _error(what):
        return ContainError(ctypes.get_last_error(), f'{what} failed (Windows error {ctypes.get_last_error()})')

    def _new_job():
        job = _CreateJobObjectW(None, None)
        if not job:
            raise _error('CreateJobObject')
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            error = _error('SetInformationJobObject')
            _CloseHandle(job)
            raise error
        return job

    def _threads(pid):
        snap = _CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        if not snap or snap == INVALID_HANDLE:
            raise _error('CreateToolhelp32Snapshot')
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found, more = [], _Thread32First(snap, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == pid:
                    found.append(entry.th32ThreadID)
                more = _Thread32Next(snap, ctypes.byref(entry))
            return found
        finally:
            _CloseHandle(snap)

    def _resume(pid):
        threads = _threads(pid)
        if not threads:
            raise ContainError(0, f'process {pid} has no thread to resume')
        for tid in threads:
            handle = _OpenThread(THREAD_SUSPEND_RESUME, False, tid)
            if not handle:
                raise _error('OpenThread')
            try:
                if _ResumeThread(handle) == 0xFFFFFFFF:
                    raise _error('ResumeThread')
            finally:
                _CloseHandle(handle)

    def _processes():
        """{pid: (parent pid, exe name)} of every process now."""
        snap = _CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == INVALID_HANDLE:
            raise _error('CreateToolhelp32Snapshot')
        try:
            entry = _ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found, more = {}, _Process32FirstW(snap, ctypes.byref(entry))
            while more:
                found[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
                more = _Process32NextW(snap, ctypes.byref(entry))
            return found
        finally:
            _CloseHandle(snap)


def identity(pid):
    """A live process's creation time (an integer that, with the id, names it), or None when no process has this id."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if WINDOWS:
        handle = _OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if not handle:
            return None
        try:
            if _WaitForSingleObject(handle, 0) != WAIT_TIMEOUT:
                return None         # it has exited (its object kept by someone's handle)
            created, other = ctypes.c_uint64(), ctypes.c_uint64()
            if not _GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(other), ctypes.byref(other),
                                    ctypes.byref(other)):
                return None
            return created.value
        finally:
            _CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    try:
        return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return 0


def tree_alive(pid, created):
    """What still runs of the process tree started as (pid, created): [(pid, exe name)], the process itself first when
    it is alive. Descendants are found through live parents, each younger than its parent and older than whatever
    holds a parent's id now (so a reused id adopts no one). [] when the tree is gone. Unknown process state is
    reported as running ([(pid, '?')]): the caller keeps waiting rather than guessing."""
    if not isinstance(pid, int) or pid <= 0:
        return []
    if not WINDOWS:
        try:
            os.killpg(pid, 0)
            return [(pid, '?')]
        except ProcessLookupError:
            return []
        except PermissionError:
            return [(pid, '?')]
    try:
        table = _processes()
    except OSError:
        return [(pid, '?')]
    children = {}
    for child, (parent, name) in table.items():
        children.setdefault(parent, []).append(child)
    alive, seen = [], set()
    if created is not None and identity(pid) == created:
        alive.append((pid, table.get(pid, (0, '?'))[1]))
    frontier = [(pid, created or 0)]
    while frontier:
        parent, born = frontier.pop()
        holder = identity(parent)
        for child in children.get(parent, ()):
            if child in seen or child == parent:
                continue
            when = identity(child)
            if when is None or when < born or (holder is not None and holder != born and when >= holder):
                continue
            seen.add(child)
            alive.append((child, table[child][1]))
            frontier.append((child, when))
    return alive


def processes():
    """{pid: (parent pid, exe name)} of every process now, from one snapshot of the process table: no child process
    (Windows; an OSError elsewhere, or when the snapshot can't be taken)."""
    if not WINDOWS:
        raise OSError('the process table is read on Windows only')
    return _processes()


def running(image):
    """Whether a process whose exe is named `image` (any case) runs now: one snapshot of the process table, where
    asking tasklist started a process each time (review finding 50). Unknown process state is reported as running, as
    tree_alive does; elsewhere than Windows, False."""
    if not WINDOWS:
        return False
    try:
        table = _processes()
    except OSError:
        return True
    return any(name.lower() == image.lower() for _, name in table.values())


class Contained:
    """A launched process tree: `proc` (its subprocess.Popen), `pid`, `created` (identity)."""

    def __init__(self, proc, job=None):
        self.proc, self.job, self.pid = proc, job, proc.pid
        self.created = identity(proc.pid)
        # every process seen in the tree, by id: its creation time. The job's count drops as soon as a process is
        # told to end, a moment before it has; drain waits for each of these to be gone.
        self.seen = {self.pid: self.created} if self.created is not None else {}

    def members(self):
        """The tree's processes now, [(pid, created)], each also remembered in `seen`."""
        found = []
        if WINDOWS and self.job:
            ids = _IdList()
            if _QueryInformationJobObject(self.job, JobObjectBasicProcessIdList, ctypes.byref(ids), ctypes.sizeof(ids), None):
                for pid in ids.ProcessIdList[:ids.NumberOfProcessIdsInList]:
                    if pid not in self.seen and (when := identity(pid)) is not None:
                        self.seen[pid] = when
                    if pid in self.seen:
                        found.append((pid, self.seen[pid]))
        elif self.proc.poll() is None:
            found.append((self.pid, self.created))
        return found

    def lingering(self):
        """The processes seen in the tree that have not ended yet: [(pid, created)]."""
        return [(pid, when) for pid, when in self.seen.items() if when is not None and identity(pid) == when]

    def active(self):
        """How many of the tree's processes are alive (0 when it is gone)."""
        if WINDOWS:
            if not self.job:
                return 0 if self.proc.poll() is not None else 1
            info = _Accounting()
            if not _QueryInformationJobObject(self.job, JobObjectBasicAccountingInformation, ctypes.byref(info),
                                              ctypes.sizeof(info), None):
                return 1        # unknown: counted as running
            return info.ActiveProcesses
        if self.proc.poll() is None:
            return 1
        try:
            os.killpg(self.pid, 0)
            return 1
        except ProcessLookupError:
            return 0
        except PermissionError:
            return 1

    def terminate(self):
        """Kill every process of the tree (the job, or the process group)."""
        if WINDOWS:
            if self.job:
                self.members()
                _TerminateJobObject(self.job, 1)
            elif self.proc.poll() is None:
                self.proc.kill()
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.pid, sig)
            except ProcessLookupError:
                return
            if sig == signal.SIGTERM:
                end = time.monotonic() + 3
                while time.monotonic() < end and self.active():
                    time.sleep(0.05)
                if not self.active():
                    return

    def drain(self, timeout=60.0, kill_after=None):
        """Wait until none of the tree's processes is left; after `kill_after` seconds (if given) kill what is left.
        True when it is gone."""
        start = time.monotonic()
        killed = False
        while self.members() is not None and (self.active() or self.lingering()):
            waited = time.monotonic() - start
            if kill_after is not None and not killed and waited >= kill_after:
                self.terminate()
                killed = True
            if waited >= timeout:
                return False
            time.sleep(0.05)
        return True

    def close(self):
        """Let go of the job (its processes, if any were left, are killed: kill on close)."""
        if WINDOWS and self.job:
            _CloseHandle(self.job)
            self.job = None


def launch(argv, **popen):
    """Start argv as a contained tree (see the module notes): a Contained. Popen's own arguments pass through; its
    environment (`env`, default this process's) gets UTF-8 for Python's standard streams (utf8_env)."""
    popen['env'] = utf8_env(popen.get('env'))
    if not WINDOWS:
        proc = subprocess.Popen(argv, start_new_session=True, **popen)
        return Contained(proc)
    job = _new_job()
    flags = popen.pop('creationflags', 0) | CREATE_SUSPENDED
    try:
        proc = subprocess.Popen(argv, creationflags=flags, **popen)
    except BaseException:
        _CloseHandle(job)
        raise
    try:
        if not _AssignProcessToJobObject(job, int(proc._handle)):
            raise _error('AssignProcessToJobObject')
        _resume(proc.pid)
    except BaseException:
        # never left running uncontained: it has run none of its code yet
        _TerminateProcess(int(proc._handle), 1)
        proc.wait()
        for stream in (proc.stdout, proc.stderr, proc.stdin):
            if stream:
                stream.close()
        _CloseHandle(job)
        raise
    return Contained(proc, job)
