"""Read-only parser for the static tile store at the start of an XComWorldDataContainer's native data.
Layout (EXP-07, from URB_Bar): 12 bytes of property header; u32 chunk count; TArray<int> chunk order; i32 NumX, NumY,
NumZ; then per chunk: u32 seq, u32 tiles, i32 X, Y, Z (tile origin), u32 n (18), n x (u32 flags, u8 present)."""
import struct
def parse(blob, start=12):
    o = start
    nchunks, n = struct.unpack_from('<II', blob, o); o += 8
    order = struct.unpack_from('<%dI' % n, blob, o); o += 4 * n
    NX, NY, NZ = struct.unpack_from('<3i', blob, o); o += 12
    chunks = []
    for k in range(nchunks):
        seq, cnt, x, y, z, m = struct.unpack_from('<IIiiiI', blob, o)
        if seq != k or m != 18:
            raise ValueError('chunk %d at %d: seq %d m %d' % (k, o, seq, m))
        p = o + 24
        tiles = [struct.unpack_from('<IB', blob, p + 5 * i) for i in range(m)]
        chunks.append(dict(seq=seq, cnt=cnt, x=x, y=y, z=z, tiles=tiles, off=o, data=p))
        o = p + 5 * m
    return dict(nchunks=nchunks, order=order, NX=NX, NY=NY, NZ=NZ, chunks=chunks, end=o)

def tile_index(x, y, z):
    """Index of a tile inside its chunk, as the game's code computes it."""
    return (x % 3) + 3 * ((y % 3) + 3 * (z % 2))

def tile(wd, x, y, z):
    for c in wd['chunks']:
        if c['x'] == x - x % 3 and c['y'] == y - y % 3 and c['z'] == z - z % 2:
            return c['tiles'][tile_index(x, y, z)], c
    return None, None
