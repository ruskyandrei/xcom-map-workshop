"""Builds the stand-in dinput8.dll that hidden game runs put beside the game when Windows has no mouse or keyboard.

  python tools/lab/build_stand_in_input.py --llvm <LLVM bin folder> [--out <file>]

The game asks DirectInput for the system mouse as it starts and crashes without one (findings register T-45);
StandInInput.c passes everything to Windows' own dinput8.dll and gives a stand-in device where Windows has none.
hidden_game.py takes the DLL from <lab>\\bin\\dinput8.dll (the default --out), the way it takes DXVK from <lab>\\dxvk.

<LLVM bin folder> holds clang-cl.exe, lld-link.exe and llvm-dlltool.exe (LLVM 15 or later). No Windows SDK is needed:
the DLL uses no C runtime, and its few kernel32 functions are imported through a library made here from a .def.
"""
import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'viewer')]
import labpaths  # noqa: E402

SOURCE = HERE / 'StandInInput.c'
NAME = 'dinput8.dll'
KERNEL32 = ('LoadLibraryW@4', 'GetProcAddress@8', 'GetSystemDirectoryW@8', 'VirtualProtect@16',
            'GetEnvironmentVariableW@12', 'CreateFileW@28', 'WriteFile@20', 'CloseHandle@4',
            'AddVectoredExceptionHandler@8', 'GetModuleHandleExW@12', 'GetModuleFileNameA@12', 'GetCurrentThreadId@0')
EXPORTS = ('DirectInput8Create', 'DllCanUnloadNow', 'DllGetClassObject', 'DllRegisterServer', 'DllUnregisterServer')


class BuildError(Exception):
    pass


def exports(data):
    """(machine, the export names) of a PE file's bytes."""
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0': raise BuildError('not a PE file')
    machine, sections = struct.unpack_from('<HH', data, pe + 4)
    optional = pe + 24
    size = struct.unpack_from('<H', data, pe + 20)[0]
    table = optional + size

    def offset(rva):
        for i in range(sections):
            virtual_size, address, raw_size, raw = struct.unpack_from('<IIII', data, table + 40 * i + 8)
            if address <= rva < address + max(virtual_size, raw_size): return raw + rva - address
        raise BuildError(f'address 0x{rva:x} is in no section')
    directory = struct.unpack_from('<I', data, optional + 96)[0]       # PE32: the export directory's address
    if not directory: return machine, []
    d = offset(directory)
    count, names = struct.unpack_from('<I', data, d + 24)[0], struct.unpack_from('<I', data, d + 32)[0]
    out = []
    for i in range(count):
        at = offset(struct.unpack_from('<I', data, offset(names) + 4 * i)[0])
        out.append(data[at:data.index(b'\0', at)].decode('ascii'))
    return machine, out


def build(llvm, out):
    llvm = Path(llvm)
    tools = {name: llvm / name for name in ('clang-cl.exe', 'lld-link.exe', 'llvm-dlltool.exe')}
    for name, path in tools.items():
        if not path.is_file(): raise BuildError(f'No {name} in {llvm}')
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / 'kernel32.def').write_text('LIBRARY kernel32.dll\nEXPORTS\n' + '\n'.join(KERNEL32) + '\n', newline='\n')
        steps = [
            [tools['llvm-dlltool.exe'], '-m', 'i386', '-k', '-d', work / 'kernel32.def', '-l', work / 'kernel32.lib'],
            [tools['clang-cl.exe'], '--target=i686-pc-windows-msvc', '/c', '/O1', '/GS-', '/Zl', '/W3',
             '/clang:-ffreestanding', f'/Fo{work / "StandInInput.obj"}', SOURCE],
            [tools['lld-link.exe'], '/dll', '/noentry', '/nodefaultlib', '/machine:x86', f'/out:{work / NAME}',
             work / 'StandInInput.obj', work / 'kernel32.lib'],
        ]
        for step in steps:
            done = subprocess.run([str(s) for s in step], capture_output=True, text=True)
            if done.returncode: raise BuildError(f'{Path(step[0]).name} failed:\n{done.stdout}{done.stderr}')
        data = (work / NAME).read_bytes()
    machine, names = exports(data)
    if machine != 0x14c: raise BuildError(f'{NAME} is not 32-bit (machine 0x{machine:x})')
    if sorted(names) != sorted(EXPORTS): raise BuildError(f'{NAME} exports {names}, not {list(EXPORTS)}')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--llvm', type=Path, required=True, help='the folder with clang-cl.exe, lld-link.exe and llvm-dlltool.exe')
    ap.add_argument('--out', type=Path, help=f'where to write it (default <lab>\\bin\\{NAME}, where hidden_game.py looks)')
    args = ap.parse_args(argv)
    try:
        out = build(args.llvm, args.out or Path(labpaths.lab_root()) / 'bin' / NAME)
    except (BuildError, OSError) as error:
        print(f'FAIL: {error}')
        return 1
    print(f'built: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
