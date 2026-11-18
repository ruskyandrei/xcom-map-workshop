"""Read-only: the sizes of the game's windows, for the wall tool's Window preset (custom geometry plan, stage M1).

A window in the game's walls is a hole in a fracturing wall with a glass piece standing in it. Over the maps named (by
default every URB map the install lists), each placed piece whose mesh's name holds "glass" or "window" (not a
vehicle's) is paired with the wall (a placed piece whose mesh's name
holds "wall", static or fracturing, at least 150 tall) whose plane it stands in: the glass's box lies inside the wall's along the wall and up, and across the
wall its middle is within 16 of the wall's. For each pair it reports the glass's width along the wall, and its
bottom and top over the wall's lowest point (the wall's bottom: the Bar's inside walls stand 16 into their floor).

Prints the counts by size and writes the rows with --output. No game file is written.

  python -B research/evidence/wall-openings.py [--maps URB_Bar ...] [--output <file.json>]
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import gen_mesh  # noqa: E402
import lightmap_texels  # noqa: E402
from package import Package  # noqa: E402

FRACTURING = ('XComDecoFracLevelActor', 'XComFracLevelActor')
MESH_COMPONENTS = ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'FracturedSkinnedMeshComponent')


def world_box(p, comp, mesh):
    m = gen_mesh.read(p, mesh)
    c, h = m['bounds'][0:3], m['bounds'][3:6]
    corners = np.array([[c[0] + sx * h[0], c[1] + sy * h[1], c[2] + sz * h[2], 1.0]
                        for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    w = corners @ lightmap_texels.world_matrix(p, comp).T
    return [float(v) for k in range(3) for v in (w[:, k].min(), w[:, k].max())]


def pieces(p):
    """[(actor, mesh name, world box, fracturing wall?)] of the map's placed mesh pieces."""
    out = []
    level = set(p.level_actors()) if hasattr(p, 'level_actors') else None
    for i, e in enumerate(p.exports, 1):
        cls = p.cls(i)
        if cls not in MESH_COMPONENTS:
            continue
        mesh = p.own(i, 'StaticMesh') or p.own(i, 'SkeletalMesh')
        if not mesh or mesh < 0:
            continue
        name = p.name(mesh)
        actor = e.get('outer')
        try:
            box = world_box(p, i, mesh)
        except Exception:
            continue
        actor_cls = p.cls(actor) if actor and actor > 0 else ''
        out.append((p.name(actor) if actor and actor > 0 else '', name, box,
                    'wall' in name.lower().split('.')[-1] and box[5] - box[4] >= 150))
    return out


def pairs(rows):
    walls = [r for r in rows if r[3]]
    out = []
    for actor, name, box, is_wall in rows:
        short = name.split('.')[-1].lower()
        if is_wall or not ('glass' in short or 'window' in short) or name.lower().startswith('veh_'):
            continue
        for wa, wname, wb, _ in walls:
            along = 0 if wb[1] - wb[0] >= wb[3] - wb[2] else 1
            across = 1 - along
            mid = (box[2 * across] + box[2 * across + 1]) / 2
            wmid = (wb[2 * across] + wb[2 * across + 1]) / 2
            inside = (box[2 * along] >= wb[2 * along] - 1 and box[2 * along + 1] <= wb[2 * along + 1] + 1
                      and box[4] >= wb[4] - 1 and box[5] <= wb[5] + 1)
            if inside and abs(mid - wmid) <= 16:
                out.append(dict(glass=name, actor=actor, wall=wname, width=round(box[2 * along + 1] - box[2 * along], 1),
                                bottom=round(box[4] - wb[4], 1), top=round(box[5] - wb[4], 1),
                                wallHeight=round(wb[5] - wb[4], 1)))
                break
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--maps', nargs='*')
    a.add_argument('--output', type=Path)
    args = a.parse_args()
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    maps = [(n, Path(path)) for n, _, path in library.donors(game)]
    want = {m.casefold() for m in args.maps} if args.maps else None
    maps = [(n, path) for n, path in maps if (n.casefold() in want if want else n.upper().startswith('URB_'))]
    found = []
    for n, path in maps:
        try:
            p = Package(path)
            rows = pairs(pieces(p))
        except Exception as error:      # a map the reader can't take is reported, not fatal
            print('%s: %s' % (n, error))
            continue
        for r in rows:
            r['map'] = n
        found += rows
        print('%s: %d windows' % (n, len(rows)))
    sizes = Counter((r['width'], r['bottom'], r['top']) for r in found)
    print('width, bottom, top over the wall\'s bottom: count')
    for (w, b, t), c in sizes.most_common(25):
        print('  %6.1f %6.1f %6.1f: %d' % (w, b, t, c))
    if args.output:
        args.output.write_text(json.dumps(dict(scope='Read-only: placed glass pieces in fracturing walls', windows=found),
                                          indent=1) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
