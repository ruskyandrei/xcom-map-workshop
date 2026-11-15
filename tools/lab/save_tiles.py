"""What the game made of a map's tiles, read out of a tactical save: its static tile flags beside the map's baked ones.

A tactical save holds the battle's static tile store (the flags the bake wrote and the game's tile rebuild rewrote:
research/native-code-notes.md, "World data tile storage"), in the layout the map's XComWorldDataContainer saves it
in. So after a run of an edited map, a save made during it shows, without the game, whether the rebuild gave a copy's
tiles a floor (bit 0x2000), marked them occupied (0x8000), or cleared a hidden piece's (EXP-28 run 1).

  python -B tools/lab/save_tiles.py <save> <map.upk> --tiles X0 X1 Y0 Y1 Z [--tiles ...]
  python -B tools/lab/save_tiles.py <save> <map.upk> --box X0 X1 Y0 Y1 Z0 Z1 [--box ...]

<save> is a save file of the game (in the lab copy: <lab copy>/XEW/XComGame/SaveData/save<n>), <map.upk> the map the
mission plays (the variant, or its base map: the tile grid is the same), read for the grid and the baked flags.
--tiles takes tile numbers, --box a world box (x, y, z up), printed a level at a time. Each tile reads
`baked -> saved`, six hex digits each, then F for a floor and O for occupied; a tile whose flags changed is starred.

The save is the game's own compression (a 1,024-byte header, then chunks of LZO1X blocks, as a cooked package's);
nothing is written anywhere.
"""
import argparse
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'upk'))
import lzo1x  # noqa: E402
import wdparse  # noqa: E402

HEADER = 1024
TAG = 0x9E2A83C1
FLOOR, OCCUPIED = 0x2000, 0x8000
TILE, LEVEL = 96.0, 64.0


def decompress(data):
    """The save's data after its header: its compressed chunks (tag, block size, compressed and uncompressed size,
    the blocks' sizes, the blocks), decompressed and joined."""
    o, out = HEADER, bytearray()
    while o + 16 <= len(data) and struct.unpack_from('<I', data, o)[0] == TAG:
        _, _, _, usize = struct.unpack_from('<4I', data, o)
        o += 16
        blocks, got = [], 0
        while got < usize:
            c, u = struct.unpack_from('<2I', data, o)
            o += 8
            blocks.append((c, u))
            got += u
        for c, u in blocks:
            out += lzo1x.decompress(data[o:o + c], u)
            o += c
    if not out:
        raise ValueError('no compressed chunk after the header: not a save of the game')
    return bytes(out)


def static_store(blob, dims, chunks):
    """The static tile store of a grid of `dims` (NumX, NumY, NumZ) tiles in `chunks` chunks, found in decompressed
    save data `blob` by its header (the chunk count twice, the chunk order, the dims): wdparse.parse's dict."""
    sig, at = struct.pack('<3i', *dims), -1
    while True:
        at = blob.find(sig, at + 1)
        if at < 0:
            raise ValueError('no tile store of %s tiles in the save: is it a save of this map?' % (dims,))
        start = at - 4 * chunks - 8
        if start >= 0 and struct.unpack_from('<II', blob, start) == (chunks, chunks):
            return wdparse.parse(blob, start)


def baked_store(package):
    """(the map's baked static tile store, its package) from a map package."""
    sys.path.insert(0, str(TOOLS / 'bake'))
    import audit_lighting as lighting
    p = lighting.Package(Path(package))
    found = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer']
    if len(found) != 1:
        raise ValueError('expected one XComWorldDataContainer in %s, found %d' % (package, len(found)))
    e = p.exports[found[0] - 1]
    return wdparse.parse(p.data[e['off']:e['off'] + e['size']]), p


def flags(store, x, y, z):
    """A tile's flag word in a store, or None outside it."""
    found, _ = wdparse.tile(store, x, y, z)
    return found[0] if found else None


def mark(f):
    return '      --' if f is None else '%06x%s%s' % (f, 'F' if f & FLOOR else '.', 'O' if f & OCCUPIED else '.')


def rows(baked, saved, x0, x1, y0, y1, z):
    """The lines for one level of a tile range, the highest Y first, and (floors baked, floors saved, tiles changed)."""
    lines, counts = [], [0, 0, 0]
    for y in range(y1, y0 - 1, -1):
        cells = []
        for x in range(x0, x1 + 1):
            a, b = flags(baked, x, y, z), flags(saved, x, y, z)
            counts[0] += bool(a and a & FLOOR)
            counts[1] += bool(b and b & FLOOR)
            counts[2] += a != b
            cells.append('%s->%s%s' % (mark(a), mark(b), '*' if a != b else ' '))
        lines.append('  y %3d: %s' % (y, ' '.join(cells)))
    return lines, tuple(counts)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('save', type=Path)
    a.add_argument('map', type=Path)
    a.add_argument('--tiles', action='append', nargs=5, type=int, default=[], metavar=('X0', 'X1', 'Y0', 'Y1', 'Z'))
    a.add_argument('--box', action='append', nargs=6, type=float, default=[], metavar=('X0', 'X1', 'Y0', 'Y1', 'Z0', 'Z1'))
    args = a.parse_args(argv)
    if not args.tiles and not args.box:
        a.error('give --tiles or --box')
    baked, p = baked_store(args.map)
    dims = (baked['NX'], baked['NY'], baked['NZ'])
    saved = static_store(decompress(args.save.read_bytes()), dims, baked['nchunks'])
    ranges = [tuple(t) for t in args.tiles]
    if args.box:
        sys.path.insert(0, str(TOOLS / 'bake'))
        import native_copy
        grid = native_copy.level_grid(p)
        for x0, x1, y0, y1, z0, z1 in args.box:
            tx = [int((v - grid['ox']) // TILE) for v in (x0, x1 - 1e-3)]
            ty = [int((v - grid['oy']) // TILE) for v in (y0, y1 - 1e-3)]
            for z in range(int((z0 - grid['oz']) // LEVEL), int((z1 - 1e-3 - grid['oz']) // LEVEL) + 1):
                ranges.append((tx[0], tx[1], ty[0], ty[1], z))
    print('%s: %d x %d x %d tiles; baked -> saved, F floor, O occupied, * changed' % ((args.map.stem,) + dims))
    for x0, x1, y0, y1, z in ranges:
        lines, (before, after, changed) = rows(baked, saved, x0, x1, y0, y1, z)
        print('tiles x %d..%d, y %d..%d, level %d: floors %d -> %d, %d tile(s) changed' % (x0, x1, y0, y1, z, before, after, changed))
        print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
