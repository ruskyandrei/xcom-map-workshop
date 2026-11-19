"""A fracturing wall's look measured from a donor, in the shape of tools/bake/frac_wall.py's RECIPE
(private/plans/done/custom-geometry-implementation-plan.md, stage M4 item 2: "measured, not typed").

The measuring is tools/bake/wall_measure.py's (moved there in M4, work order A; its docstring says how it measures):
this script is a wrapper of it with the same output. It reads one FracturedStaticMesh of a map of the install (by the
map and the mesh's name, or a placed actor's) and writes its entry (RECIPE's keys), its diagnostics (`measured`) and
what it cannot measure (`notMeasured`).

--check measures URB_Bar's donor (XComDecoFracLevelActor_17) and compares each key with RECIPE, within
wall_measure.CHECK_TOLERANCE (the cell as the grid it gives on the donor's solid: the recipe's cell and the measured one
both give its 6 x 5 fragments). No game file is written.

  python -B research/evidence/wall-look-measure.py --check
  python -B research/evidence/wall-look-measure.py --look URB_Bar:XComDecoFracLevelActor_17
  python -B research/evidence/wall-look-measure.py --look URB_PoliceStation:URB_PoliceStationBuilding.Meshes.PoliceStationWallD_FRACTURED
  python -B research/evidence/wall-look-measure.py --check --look <map>:<actor or mesh> ... --output <file.json>
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import gen_mesh  # noqa: E402
import wall_measure  # noqa: E402
# the names the wall-look audit (research/evidence/wall-look-audit.py) takes from here
from wall_measure import (BAR, CHECK_TOLERANCE, FRACTURING, check, compare, find, install_package,  # noqa: E402,F401
                          materials_of, placed)

measure = wall_measure.measure_raw


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--look', nargs='*', default=[], metavar='MAP:ACTOR_OR_MESH',
                   help='donors to measure: a map and a placed actor\'s or a fracturing mesh\'s name')
    a.add_argument('--check', action='store_true', help='measure URB_Bar\'s donor and compare it with frac_wall.RECIPE')
    a.add_argument('--cuts', action='store_true', help='keep each cut\'s place and deviation in the diagnostics')
    a.add_argument('--output', type=Path)
    args = a.parse_args()
    out = {}
    if args.check:
        import frac_wall
        r = measure(install_package(BAR[0]), BAR[1], args.cuts)
        rows = check(r, frac_wall.RECIPE)
        out['check'] = dict(donor='%s:%s' % BAR, rows=rows, passed=sum(x['ok'] for x in rows), of=len(rows),
                            notMeasured=r['notMeasured'])
        out.setdefault('looks', {})['%s:%s' % BAR] = r
        for x in rows:
            print('%-26s %-5s measured %s  recipe %s%s' % (x['key'], 'ok' if x['ok'] else 'DIFF', json.dumps(x['measured']),
                                                         json.dumps(x['recipe']), ('  (' + x['note'] + ')') if x['note'] else ''))
        print('%d of %d keys within tolerance' % (out['check']['passed'], out['check']['of']))
    packages = {}
    for spec in args.look:
        name, _, what = spec.partition(':')
        try:
            if name not in packages:
                packages[name] = install_package(name)
            r = measure(packages[name], what, args.cuts)
        except (SystemExit, ValueError, KeyError, gen_mesh.MeshError) as err:
            out.setdefault('errors', {})[spec] = str(err)
            print('%s: %s' % (spec, err))
            continue
        out.setdefault('looks', {})[spec] = r
        print(json.dumps(dict(look=spec, entry=r['entry'], sweep=r['measured']['sweep']), indent=1))
    if args.output:
        args.output.write_text(json.dumps(out, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
