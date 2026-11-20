"""
Seeds tiles in a map's baked world data so the game's runtime tile rebuild re-checks them (EXP-07, F-29).

The rebuild (XComWorldData.RebuildTileDataExtents) queues a tile only if its baked static flags have a bit in 0xFFF
(research/native-code-notes.md). Tiles that were empty when the map was built never are, so geometry added at run time
doesn't block above the ground there. This sets SEED on the chosen tiles whose low 12 bits are 0; the rebuild then
recomputes their flags from the geometry, as it does for every other tile. Seeded tiles must lie inside a region the
patch rebuilds at load.

Writes a new package; never touches the input. The changed tiles are an edit list for package_edit.write_edited: only
the changed 128 KB blocks are re-encoded (as literal LZO1X runs), later chunks move along, every uncompressed offset
stays the same, and the result is decoded again and compared with the intended bytes. The patch path seeds the tiles
of a patch's copies with it (seed_map.apply); the Build's own copies seed theirs in the growing write
(tools/bake/native_copy.py seed_tiles_under).

  python seed_tiles.py <map.upk> <out.upk> <x0> <x1> <y0> <y1> <z0> <z1> [more boxes ...] [--seed 0x1]
"""
import os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo, decomp, package_edit, world_links

SEED_DEFAULT = 0x1


def seed_package(src, dst, tiles, seed=SEED_DEFAULT):
    """Writes dst: src with seed set on each of tiles ((x, y, z) tile indices) whose low 12 bits are 0.

    Tiles outside the world are skipped. Returns (seeded, already, dims): the (x, y, z, old, new, old present) rows of
    the tiles changed, the number left alone because they already had low bits, and (NX, NY, NZ). With nothing to
    seed, dst is a plain copy of src. Writes dst + '.seeded.txt' listing the changed tiles. The static flags are read
    by world_links.static_tiles and the changed tiles written by package_edit.write_edited (review finding 52)."""
    if not (seed & 0xFFF) or seed & ~0xFFF:
        raise ValueError('the seed must be bits within 0xFFF')
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError('refusing to overwrite the input')

    full, h = decomp.decompress_pkg(src)
    names, imps, exps = upkinfo.tables(full, h)
    conts = [e for e in exps if upkinfo.clsname(e['cls'], imps, exps) == 'XComWorldDataContainer']
    if len(conts) != 1:
        raise ValueError('expected one XComWorldDataContainer, found %d' % len(conts))
    ce = conts[0]
    blob = full[ce['off']:ce['off'] + ce['size']]

    (NX, NY, NZ), where, _ = world_links.static_tiles(blob)
    changed, already, edits = [], 0, []
    for x, y, z in sorted(set(tiles)):
        if not (0 <= x < NX and 0 <= y < NY and 0 <= z < NZ):
            continue
        off = where[(x, y, z)]
        f, pres = struct.unpack_from('<IB', blob, off)
        if f & 0xFFF:
            already += 1
            continue
        edits.append((ce['off'] + off, struct.pack('<IB', f | seed, 1)))
        changed.append((x, y, z, f, f | seed, pres))

    with open(dst + '.seeded.txt', 'w') as m:
        m.write('x\ty\tz\told_flags\tnew_flags\told_present\n')
        for x, y, z, f, g, pres in changed:
            m.write('%d\t%d\t%d\t0x%08X\t0x%08X\t%d\n' % (x, y, z, f, g, pres))
    if not changed:
        shutil.copyfile(src, dst)
        return changed, already, (NX, NY, NZ)
    package_edit.write_edited(src, dst, edits)
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
