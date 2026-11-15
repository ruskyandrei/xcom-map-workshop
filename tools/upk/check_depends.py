"""Find packages whose depends map a reader would choke on (the XCOM Uncooker's SerializeDependsMap overflow).

  python -I tools/upk/check_depends.py <CookedPCConsole folder>

Reads only the package summary of every *.upk the Uncooker would load (it skips patch_*, shader caches and
GlobalPersistentCookerData). For uncompressed packages it also walks the depends map: one int32 count plus that
many int32s per export, which must stay inside the header. Compressed packages are only listed, because their
tables sit inside LZO chunks.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkinfo


def uncooker_skips(name):
    return name.startswith('patch_') or 'ShaderCache' in name or 'GlobalPersistentCookerData' in name


def main():
    root = Path(sys.argv[1])
    compressed = uncompressed = 0
    problems = []
    for path in sorted(root.rglob('*.upk')):
        if uncooker_skips(path.name):
            continue
        with path.open('rb') as file:
            head = file.read(1 << 20)
        try:
            h = upkinfo.summary(head)
        except Exception as ex:
            problems.append((path.name, 'unreadable summary: %s' % ex))
            continue
        if h['tag'] != hex(0x9E2A83C1):
            problems.append((path.name, 'bad tag %s (fully LZO-wrapped package?)' % h['tag']))
            continue
        if h['chunks']:
            compressed += 1
            continue
        uncompressed += 1
        size = path.stat().st_size
        data = head if h['headersize'] <= len(head) else path.read_bytes()
        off, end = h['dependsoff'], h['headersize']
        if off >= end:   # map moved past the header by repair_depends.py
            end = size
            data = path.read_bytes()
        issue = None
        if not (0 < off <= end <= size):
            issue = 'depends offset %d outside header (header size %d, file %d)' % (off, end, size)
        else:
            for n in range(h['expcount']):
                if off + 4 > end:
                    issue = 'depends map runs past the header at export %d of %d' % (n + 1, h['expcount'])
                    break
                count = struct.unpack_from('<i', data, off)[0]
                if count < 0 or off + 4 + 4 * count > end:
                    issue = 'export %d of %d: depends count %d at offset %d' % (n + 1, h['expcount'], count, off)
                    break
                off += 4 + 4 * count
        problems.append((path.name, issue or 'uncompressed, depends map OK (%d exports, flags %s)' % (h['expcount'], h['flags'])))
    print('compressed packages: %d, uncompressed: %d' % (compressed, uncompressed))
    for name, issue in problems:
        print('  %-40s %s' % (name, issue))


if __name__ == '__main__':
    main()
