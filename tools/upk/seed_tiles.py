"""
Seeds tiles in a map's baked world data so the game's runtime tile rebuild re-checks them (EXP-07, F-29).

The rebuild (XComWorldData.RebuildTileDataExtents) queues a tile only if its baked static flags have a bit in 0xFFF
(research/native-code-notes.md). Tiles that were empty when the map was built never are, so geometry added at run time
doesn't block above the ground there. This sets SEED on the chosen tiles whose low 12 bits are 0; the rebuild then
recomputes their flags from the geometry, as it does for every other tile. Seeded tiles must lie inside a region the
patch rebuilds at load.

Writes a new package; never touches the input. The XComWorldDataContainer must be one compressed chunk of its own
(true for URB_Bar). Only the changed 128 KB blocks are re-encoded (as literal LZO1X runs), so every uncompressed
offset in the package stays the same. The result is decoded again and compared with the intended bytes.

  python seed_tiles.py <map.upk> <out.upk> <x0> <x1> <y0> <y1> <z0> <z1> [more boxes ...] [--seed 0x1]
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo, decomp, lzo1x

SEED_DEFAULT = 0x1


def chunk_table_offset(b):
    """Byte offset of the summary's compressed-chunk table (count, then 16-byte entries)."""
    r = upkinfo.R(b)
    r.u32(); r.u16(); r.u16(); r.u32(); r.fstr(); r.u32()
    for _ in range(11): r.u32()   # name, export, import counts/offsets; depends, guids, thumbnails
    r.o += 16
    gc = r.u32(); r.o += 12 * gc
    r.u32(); r.u32(); r.u32()
    return r.o


def parse_static_store(blob):
    o = 12
    nchunks, n = struct.unpack_from('<II', blob, o); o += 8 + 4 * n
    NX, NY, NZ = struct.unpack_from('<3i', blob, o); o += 12
    tiles = {}
    for k in range(nchunks):
        seq, cnt, x, y, z, m = struct.unpack_from('<IIiiiI', blob, o)
        if seq != k or m != 18:
            raise ValueError('unexpected chunk record %d at %d' % (k, o))
        p = o + 24
        for i in range(18):
            tx, ty, tz = x + i % 3, y + (i // 3) % 3, z + i // 9
            tiles[(tx, ty, tz)] = p + 5 * i
        o = p + 90
    return (NX, NY, NZ), tiles, o


def lzo_literals(data):
    """A valid LZO1X stream holding data as one literal run, then the end marker."""
    n = len(data)
    if n < 19:
        raise ValueError('block too small for this encoder')
    rest = n - 3 - 15
    k = (rest - 1) // 255
    r = rest - 255 * k
    return bytes([0]) + bytes(k) + bytes([r]) + data + b'\x11\x00\x00'


def seed_package(src, dst, tiles, seed=SEED_DEFAULT):
    """Writes dst: src with seed set on each of tiles ((x, y, z) tile indices) whose low 12 bits are 0.

    Tiles outside the world are skipped. Returns (seeded, already, dims): the (x, y, z, old, new, old present) rows of
    the tiles changed, the number left alone because they already had low bits, and (NX, NY, NZ). With nothing to
    seed, dst is a plain copy of src. Writes dst + '.seeded.txt' listing the changed tiles."""
    if not (seed & 0xFFF) or seed & ~0xFFF:
        raise ValueError('the seed must be bits within 0xFFF')
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError('refusing to overwrite the input')

    raw = open(src, 'rb').read()
    h = upkinfo.summary(raw)
    full, _ = decomp.decompress_pkg(src)
    names, imps, exps = upkinfo.tables(full, h)
    conts = [e for e in exps if upkinfo.clsname(e['cls'], imps, exps) == 'XComWorldDataContainer']
    if len(conts) != 1:
        raise ValueError('expected one XComWorldDataContainer, found %d' % len(conts))
    ce = conts[0]
    ci = [i for i, (uo, us, co, cs) in enumerate(h['chunks']) if uo == ce['off'] and us == ce['size']]
    if not ci:
        raise ValueError('the container is not a compressed chunk of its own; this tool cannot handle that')
    ci = ci[0]
    uo, us, co, cs = h['chunks'][ci]

    # The chunk's blocks.
    r = upkinfo.R(raw, co)
    tag, bsz, csum, usum = r.u32(), r.u32(), r.u32(), r.u32()
    nb = (usum + bsz - 1) // bsz
    blocks = [(r.u32(), r.u32()) for _ in range(nb)]
    p = r.o
    datas = []
    for c, u in blocks:
        datas.append(bytearray(lzo1x.decompress(raw[p:p + c], u))); p += c
    blob = bytearray(b''.join(datas))
    if bytes(blob) != full[uo:uo + us]:
        raise ValueError('chunk decode mismatch')

    (NX, NY, NZ), where, store_end = parse_static_store(blob)
    changed, already = [], 0
    for x, y, z in sorted(set(tiles)):
        if not (0 <= x < NX and 0 <= y < NY and 0 <= z < NZ):
            continue
        off = where[(x, y, z)]
        f, pres = struct.unpack_from('<IB', blob, off)
        if f & 0xFFF:
            already += 1
            continue
        struct.pack_into('<IB', blob, off, f | seed, 1)
        changed.append((x, y, z, f, f | seed, pres))

    with open(dst + '.seeded.txt', 'w') as m:
        m.write('x\ty\tz\told_flags\tnew_flags\told_present\n')
        for x, y, z, f, g, pres in changed:
            m.write('%d\t%d\t%d\t0x%08X\t0x%08X\t%d\n' % (x, y, z, f, g, pres))
    if not changed:
        open(dst, 'wb').write(raw)
        return changed, already, (NX, NY, NZ)

    # Re-encode only the changed blocks.
    newblocks, payload = [], b''
    p = co + 16 + 8 * nb
    for k, (c, u) in enumerate(blocks):
        old = raw[p:p + c]; p += c
        part = bytes(blob[k * bsz:k * bsz + u])
        if part == bytes(datas[k]):
            enc = old
        else:
            enc = lzo_literals(part)
            if lzo1x.decompress(enc, u) != part:
                raise ValueError('literal LZO round trip failed on block %d' % k)
        newblocks.append((len(enc), u)); payload += enc
    newchunk = struct.pack('<IIII', tag, bsz, sum(c for c, u in newblocks), usum)
    newchunk += b''.join(struct.pack('<II', c, u) for c, u in newblocks) + payload

    if co + cs != len(raw) and ci != len(h['chunks']) - 1:
        raise ValueError('the container chunk is not last in the file; offsets would shift')
    out = bytearray(raw[:co] + newchunk + raw[co + cs:])
    t = chunk_table_offset(raw)
    n = struct.unpack_from('<I', raw, t)[0]
    if n != len(h['chunks']):
        raise ValueError('chunk table not where expected')
    ent = t + 4 + 16 * ci
    if struct.unpack_from('<IIII', raw, ent) != (uo, us, co, cs):
        raise ValueError('chunk table entry mismatch')
    struct.pack_into('<IIII', out, ent, uo, us, co, len(newchunk))
    open(dst, 'wb').write(out)

    # Check: decode the written package and compare.
    # Everything must match the original except the one chunk-table entry (its compressed size) and the container's
    # bytes, which must be the seeded ones.
    full2, h2 = decomp.decompress_pkg(dst)
    expect = bytearray(full)
    struct.pack_into('<IIII', expect, ent, uo, us, co, len(newchunk))
    expect[uo:uo + us] = blob
    if bytes(full2) != bytes(expect):
        raise ValueError('verification failed: the written package does not decode to the intended bytes')
    if [c for i, c in enumerate(h2['chunks']) if i != ci] != [c for i, c in enumerate(h['chunks']) if i != ci]:
        raise ValueError('verification failed: other chunk table entries changed')
    return changed, already, (NX, NY, NZ)


def main():
    args = sys.argv[1:]
    seed = SEED_DEFAULT
    if '--seed' in args:
        i = args.index('--seed'); seed = int(args[i + 1], 0); del args[i:i + 2]
    src, dst = args[0], args[1]
    nums = [int(v) for v in args[2:]]
    if not nums or len(nums) % 6:
        raise SystemExit('give boxes as x0 x1 y0 y1 z0 z1')
    tiles = []
    for i in range(0, len(nums), 6):
        x0, x1, y0, y1, z0, z1 = nums[i:i + 6]
        tiles += [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    changed, already, dims = seed_package(src, dst, tiles, seed)
    if not changed:
        raise SystemExit('nothing to seed: every chosen tile already has low bits (%s is a plain copy)' % dst)
    print('seeded %d tiles with 0x%X in %s (%d already had low bits); wrote %s, verified' % (
        len(changed), seed, os.path.basename(src), already, dst))


if __name__ == '__main__':
    main()
