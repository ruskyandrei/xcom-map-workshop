"""EXP-27's project: floor pieces placed as the editor's Level snap places them (research/experiments/EXP-27-floor-pieces.md).

URB_Bar's sidewalk strip XComLevelActor_21 (SidewalkStrB8x4, unturned, on the south street, in no building floor) is
copied twice onto the open asphalt on the map's east side, whole tiles from where it stands (29 tiles east):
- at ground level, (1055, -1248, 0): the height it has in the map, as Level snap gives it on the road (its saved floor
  16 units over its pivot, so its surface at 16 like the map's sidewalks);
- at floor 2's height, (1055, -768, 192): as Level snap gives it with floor 2 chosen in the Floor picker. The nearest
  building with a floor 2 there is the bar's (XComBuildingVolume_0), whose floor 2 walks at 210 (its saved floor tiles
  near its volume's bottom), so the copy's pivot goes up 3 whole levels, to 192, and its surface to 208. No floor
  stands there in the map: the question of F-47 (a copied floor got no floor tiles) for a copy made in the map.

The heights are worked out here with the rules of tools/viewer/web/floors.js (ownedFloors, storeyHeight, levelHeight).

  python -B tools/editor/examples/exp27_projects.py [--cache <viewer cache>]
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
import settings  # noqa: E402
from projects import ProjectStore  # noqa: E402
from settings import load_settings  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
ID = '27a0a0b1-2727-4d0a-8e27-3c4d5e6f7a27'
MAP = 'URB_Bar'
SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
SOURCE = 'XComLevelActor_21'
GROUND, RAISED = (1055, -1248), (1055, -768)
STOREY = 64


def median(values):
    s = sorted(values)
    return s[len(s) // 2]


def owned_floor(scene, actor):
    """floors.js ownedFloors for one actor: the median height of its saved floor tiles on their most common level."""
    tiles = [t for t in scene['tactical']['floorTiles'] if t.get('actor') == actor]
    levels = {}
    for t in tiles:
        levels[t['tile'][2]] = levels.get(t['tile'][2], 0) + 1
    level = sorted(levels.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return median([t['location'][2] for t in tiles if t['tile'][2] == level])


def storey_height(scene, floor):
    """floors.js storeyHeight: the saved floor tiles inside a building floor's volumes near its bottom, their median."""
    boxes, bottom = floor['boxes'], floor['bottom']
    near = [t['location'][2] for t in scene['tactical']['floorTiles']
            if bottom - 8 <= t['location'][2] < bottom + STOREY
            and any(v['min'][0] <= t['location'][0] <= v['max'][0] and v['min'][1] <= t['location'][1] <= v['max'][1]
                    and v['min'][2] - 8 <= t['location'][2] <= v['max'][2] for v in boxes)]
    return median(near) if near else bottom


def level_height(pivot_z, support, z):
    """floors.js levelHeight: the piece's own pivot height, moved by whole levels to the level of floor z."""
    return pivot_z + round((z - pivot_z - support) / STOREY) * STOREY


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=SHA, exporterVersion=17)))
    found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + SOURCE]
    assert len(found) == 1, SOURCE
    src = found[0]
    support = owned_floor(scene, PL + SOURCE) - src['location'][2]
    bar = next(b for b in scene['buildings'] if b['name'].endswith('.XComBuildingVolume_0'))
    floor2 = storey_height(scene, bar['floors'][1])
    for x, y in (GROUND, RAISED):
        steps = ((x - src['location'][0]) / compiler.TILE, (y - src['location'][1]) / compiler.TILE)
        assert all(abs(v - round(v)) < 1e-6 for v in steps), steps
    heights = (level_height(src['location'][2], support, src['location'][2] + support),
               level_height(src['location'][2], support, floor2))
    # the source stands at z 0.000015, and a copy keeps that offset, as the editor's levelHeight does
    assert abs(heights[0]) < 0.01 and abs(heights[1] - 192) < 0.01, (heights, support, floor2)
    target = dict(package=MAP, level='base', actor=PL + SOURCE)
    added = [dict(id='27a0a0b1-2727-4a27-9c27-0d1e2f3a4%03d' % (k + 1), actor=PL + '%s_copy%d' % (SOURCE, k + 1),
                  **{'from': target}, components=[src['component']], location=[x, y, z], rotation=list(src['rotation']))
             for k, ((x, y), z) in enumerate(zip((GROUND, RAISED), heights))]
    # As the editor names a project's output (web/project.js outputNames): 30 characters at most for the patch (T-09).
    stem = MAP[:12]
    ship = '%s_%s_%s' % (stem, 'Exp27Floors'[:compiler.NAME_LIMIT - len('patch_') - len(stem) - 6], ID[:4])
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name='EXP-27 floor pieces at their levels',
               mode='edit', source=dict(map=MAP, package=MAP + '.upk', sha256=SHA, exporterVersion=17),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()), overrides=[], added=added,
               nextSerial=len(added), view=dict(camera=[1800, 2600, 400], target=[1400, 0, 1000]))
    spec, report = compiler.compile_project(doc, scene)
    if not report['ok']:
        raise SystemExit('the project does not compile: %s' % report['errors'])
    store = ProjectStore(load_settings()['projects'])
    try:
        current = store.load(ID)
        if current.get('created'):
            doc['created'] = current['created']
        expected = current['revision']
    except Exception:
        expected = 0
    saved = store.save(ID, doc, expected)
    print('saved %s (%s) revision %d in %s as %s: %d added; support %g, floor 2 of the bar at %g; %d warnings'
          % (doc['name'], ID, saved['revision'], store.path(ID), ship, report['counts']['added'], support, floor2,
             len(report['warnings'])))
    for w in report['warnings']:
        print('  warning:', w.get('code'), w.get('message'))
    for x in added:
        print('  %s at %s %s' % (x['actor'].split('.')[-1], x['location'], x['rotation']))


if __name__ == '__main__':
    main()
