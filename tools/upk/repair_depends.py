"""Give an uncompressed package a complete depends map, for tools that read it (the XCOM Uncooker).

  python -I tools/upk/repair_depends.py <package.upk> [more.upk ...]

Edits the given files in place, so use it only on copies, never on game files. Tools that append exports to
a package (as LWR's patched Engine/XComGame/XComStrategyGame show) leave the depends map one entry per original
export, ending where the first export's data starts. The game ignores the map in cooked packages; the Uncooker
reads ExportCount entries and overflows on the export data that follows.

The repair copies the existing entries to the end of the file, adds an empty entry (count 0) for each missing
export and points the summary's DependsOffset there. Nothing else moves, so export offsets and bulk-data
offsets stay valid. Already-complete maps are left alone.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkinfo


def depends_offset_field(data):
    """Byte position of the DependsOffset field in the package summary."""
    pos = 12                                    # tag, file/licensee version, header size
    length = struct.unpack_from('<i', data, pos)[0]
    pos += 4 + (length if length >= 0 else -2 * length)   # folder name
    pos += 4 + 6 * 4                            # package flags; name, export, import counts and offsets
    return pos


def repair(path):
    data = bytearray(path.read_bytes())
    h = upkinfo.summary(bytes(data[:1 << 16]))
    if h['chunks']:
        return 'compressed: skipped'
    field = depends_offset_field(data)
    if struct.unpack_from('<I', data, field)[0] != h['dependsoff']:
        return 'DependsOffset field not where expected: not changed'
    start = h['dependsoff']
    limit = h['headersize'] if start < h['headersize'] else len(data)
    off, entries = start, 0
    while entries < h['expcount'] and off + 4 <= limit:
        count = struct.unpack_from('<i', data, off)[0]
        if count < 0 or off + 4 + 4 * count > limit:
            break
        off += 4 + 4 * count
        entries += 1
    missing = h['expcount'] - entries
    if missing == 0:
        return 'depends map complete: not changed'
    new_map = bytes(data[start:off]) + b'\0\0\0\0' * missing
    new_start = len(data)
    data += new_map
    struct.pack_into('<I', data, field, new_start)
    path.write_bytes(bytes(data))
    return 'added %d empty entries; depends map moved from %d to %d (%d bytes)' % (missing, start, new_start, len(new_map))


def main():
    for name in sys.argv[1:]:
        print('%s: %s' % (name, repair(Path(name))))


if __name__ == '__main__':
    main()
