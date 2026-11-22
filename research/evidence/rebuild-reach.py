"""Read-only: how far the battle's tile rebuild reaches for a rebuild volume the Build clones from each map's
template (findings register F-150).

The game rebuilds, for each XComRebuildWorldDataVolume, the tiles of the cube its bounds' centre ± its bounds' sphere
radius (XGBattle.DoWorldDataRebuild), and that sphere is the brush's own times the volume's largest scale on any
axis (native_copy.volume_sphere), not the diagonal of the scaled box. Over every base map the install lists
(tools/viewer/library.py donors), or the maps named, this reads the volume the Build clones (native_copy.
rebuild_template), its brush's box and sphere, and gives for a sample box (3 by 3 tiles, four levels up from the
grid's bottom: 304 by 304 by 272) the radius by the box's diagonal and the radius the game reads.

  python -B research/evidence/rebuild-reach.py [<map.upk> ...] [--json <out>]
"""
import argparse
import json
import math
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
for d in ('upk', 'viewer', 'bake'):
    sys.path.insert(0, str(TOOLS / d))
import native_copy  # noqa: E402
import lighting_records as lighting  # noqa: E402

SAMPLE = (152.0, 152.0, 136.0)      # half the sample box


def report(path):
    p = lighting.Package(Path(path))
    try:
        template = native_copy.rebuild_template(p)
    except (ValueError, KeyError) as e:
        return dict(map=Path(path).stem, template=None, why=str(e))
    ti = p.by_name[native_copy.PL + template]
    _, extent = native_copy.brush_bounds(p, ti)
    sphere = native_copy.brush_sphere(p, ti)
    game = sphere * max(SAMPLE[k] / extent[k] for k in range(3))
    return dict(map=Path(path).stem, template=template, templateClass=p.cls(ti), brushExtent=[round(v, 2) for v in extent],
                brushSphere=round(sphere, 2), sampleByDiagonal=round(math.sqrt(sum(v * v for v in SAMPLE)), 1),
                sampleInGame=round(game, 1), tilesInGame=round(game / 96.0, 1))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('maps', nargs='*', type=Path)
    a.add_argument('--json', type=Path)
    args = a.parse_args(argv)
    maps = args.maps
    if not maps:
        import library
        import settings
        game, _ = settings.game_install(settings.load_settings())
        maps = [Path(path) for _, role, path in library.donors(game) if role == 'base']
    out = []
    for path in maps:
        try:
            r = report(path)
        except Exception as e:      # a map this reader can't open is named, not fatal
            r = dict(map=Path(path).stem, template=None, why='%s: %s' % (type(e).__name__, e))
        out.append(r)
        if r.get('template'):
            print('%-30s %-28s brush %-28s sphere %7.1f: the sample box reaches %7.1f (%5.1f tiles), by its diagonal %5.1f'
                  % (r['map'], r['template'], r['brushExtent'], r['brushSphere'], r['sampleInGame'], r['tilesInGame'],
                     r['sampleByDiagonal']))
        else:
            print('%-30s no template: %s' % (r['map'], r['why']))
    got = [r['tilesInGame'] for r in out if r.get('template')]
    if got:
        got.sort()
        print('%d maps: the sample box reaches %.1f to %.1f tiles from its centre, median %.1f; by its diagonal %.1f'
              % (len(got), got[0], got[-1], got[len(got) // 2], math.sqrt(sum(v * v for v in SAMPLE)) / 96.0))
    if args.json:
        args.json.write_text(json.dumps(dict(sampleHalf=SAMPLE, maps=out), indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
