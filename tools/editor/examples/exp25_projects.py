"""EXP-25's projects: checklist item 1's maps, every kind of edit (private/plans/done/preview-release.md, item 1; the cars,
doors and ladders plan, step 7; research/experiments/EXP-25-preview-maps.md).

Each run is one project on one map, played through a whole mission: a moved, a deleted and a copied piece, a
collectible copied where the map has one, and a copy of each assembly family the map has that builds (ladders,
framed doors, cars, vans). Doors without a frame (UFO, alien and barn doors) are still refused, so the UFO maps copy
none.

- police (run 1, URB_PoliceStation; no collectible, no ladder):
  - in the lobby (floor 2, z 80), the wooden bench XComDestructibleActor_55 moves 2 tiles south, from (-96, 820) to
    (-96, 628), and the bench XComDestructibleActor_57 beside it, at (79, 820), is deleted;
  - the utility box XComDestructibleActor_278 (from (912, 1740)) is copied into the car park west of the station, at
    (-1104, -756), and the dumpster XComDestructibleActor_169 (from the fenced corner at (-1664, -2384)) into the
    street east of it, at (1408, -464);
  - the west facade's double door (leaves XComInteractiveLevelActor_17 and _18, frames _15 and _35) is copied a
    quarter turn round into the inner wall WallD's east doorway (x 288 to 480, y -672), which has no door (EXP-23
    run 2 put the same copy in its west one);
  - the compact car XComDestructibleActor_1077 (glass XComFracLevelActor_201, at (962, -2496)) is copied a quarter
    turn round, east of it along the south street;
  - the delivery van at (-1058, -1356) (cab XComDestructibleActor_1088, 7 parts, its own building) is copied a
    quarter turn round into the street south of the station.
- forest (run 2, CLrgScout_ForestTrench; its doors are the UFO's, without frames):
  - in the clearing north of the UFO, the tree XComDestructibleActor_242 moves 2 tiles east, from (-192, 1824) to
    (0, 1824); the big rock XComDestructibleActor_19 at (-960, 2304) is deleted; the rock XComDestructibleActor_476
    (from (1536, 2208)) is copied to (-768, 1824);
  - the power core XComCollectible_10 (the UFO's north power room, (-816, 1200)) is copied out into the clearing, at
    (-432, 1872): a copy is a collectible too, counted as loot at the end.
- farm (run 3, CSmallScout_Farm, whose package is CsmallScout_Farm; its doors, the barn's and the UFO's, have no
  frames):
  - the tractor XComDestructibleActor_153 moves 2 tiles north, from (-1, -1) to (-1, 191), and is copied beside it,
    to (-481, 191); the generator XComDestructibleActor_4 at (95, 1104) is deleted;
  - the UFO's navigation part XComCollectible_12 (from (1872, -1904)) is copied inside the UFO, to (1872, -1232);
  - the ladder XComLadder_4 is copied 3 tiles along the big barn's lean-to, to (-1392, -1392), where EXP-22 run 2
    moved it (its patch_farm helper stays with the original);
  - the flatbed truck XComDestructibleActor_91 (5 parts) is copied 14 tiles east and 10 north, unturned.
- demolition (run 4, URB_Demolition_EWI; its doors have no frames):
  - the bulldozer XComDestructibleActor_100 moves 2 tiles east, to (864, 384); the portable toilet
    XComDestructibleActor_156 in the pit is deleted; the crate stack XComDestructibleActor_363 is copied to
    (-1580, 233);
  - the drain pipe XComLadder_4 (at (1200, -1488), up a site office) is copied 2 tiles north along the office (2
    west would have stood clear of it, though the compiler's end check passes there);
  - the SUV XComDestructibleActor_83 (at (1632, -844)) is copied 7 tiles north, unturned.
- truckstop (run 5, URB_TruckStop_EWI; Fastrope intro only; its one empty doorway is a garage opening, so no door):
  - the dumpster XComDestructibleActor_32 moves 2 tiles east, to (-1920, 1048); the forklift
    XComDestructibleActor_415 is deleted; the tall crate stack XComDestructibleActor_216 is copied to (1879, -433);
  - the tall drain pipe XComLadder_7 (at (-2832, -1680)) is copied 2 tiles east along its wall (2 north of
    XComLadder_3 would have stood inside the store's jutting wall, though the compiler's end check passes there);
  - the semi truck cab XComDestructibleActor_197 (at (2112, 384)) is copied 3 tiles east, unturned.
- hurricane (run 6, URB_StreetHurricane_Terror): the moving vans' ladders climb through patch_streethurricane's
  helpers only (the compiler refuses a copy: no floor at its top in the map), so the vans stay as they are:
  - the cover chunk XComDestructibleActor_50 moves 2 tiles east, to (-768, 96); the park bench
    XComDestructibleActor_14 is deleted; the cover chunk XComDestructibleActor_52 is copied 2 tiles north, to
    (-535, 625);
  - the sedan XComDestructibleActor_98 (at (1444, 384)) is copied a quarter turn round, east of it.

Writes the run's project into the projects folder (the editor settings) and prints its id. Run again, it saves the
same edit as the next revision.

  python tools/editor/examples/exp25_projects.py <run> [--cache <viewer cache>]
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
# Each run: plain pieces moved by (dx, dy), deleted, and copied to (x, y) keeping the original's height and turn;
# assemblies copied, by a piece of each: (piece, quarter turns about the grid's corner, tiles, storeys), as the
# recipe snap poses them. `view`: the viewer's camera and target in its basis (x, up, y). `map` is the records'
# name (the map browser's id), `package` the package's where its case differs (the farm's; T-17).
RUNS = {
    'police': dict(
        id='25a0a0b1-2525-4d0a-8e25-3c4d5e6f7a25', name='EXP-25 the police station, every kind',
        map='URB_PoliceStation', sha='86785ed731811d0b337e8ab2bb9aa0215678d88b48de0beadea9bf7193f0fa29',
        moved=(('XComDestructibleActor_55', (0, -192)),),
        deleted=('XComDestructibleActor_57',),
        copied=(('XComDestructibleActor_278', (-1104, -756)), ('XComDestructibleActor_169', (1408, -464))),
        assemblies=(('XComInteractiveLevelActor_17', 1, (39, 6), 0),   # the double door's halves, into WallD's
                    ('XComInteractiveLevelActor_18', 1, (39, 6), 0),   # east doorway
                    ('XComDestructibleActor_1077', 1, (33, -26), 0),   # the compact car
                    ('XComDestructibleActor_1088', 1, (31, -3), 0)),   # the delivery van
        view=dict(camera=[0, 3200, -2600], target=[0, 0, -300])),
    'forest': dict(
        id='25b0a0b1-2525-4d0a-8e25-3c4d5e6f7b25', name='EXP-25 the forest trench, every kind',
        map='CLrgScout_ForestTrench', sha='de5d2e0e0589468699903f77b4253753aea42c7d1df74784550abf8591db2a58',
        moved=(('XComDestructibleActor_242', (192, 0)),),
        deleted=('XComDestructibleActor_19',),
        copied=(('XComDestructibleActor_476', (-768, 1824)), ('XComCollectible_10', (-432, 1872))),
        assemblies=(),
        view=dict(camera=[-400, 2600, -800], target=[-500, 0, 1800])),
    'farm': dict(
        id='25c0a0b1-2525-4d0a-8e25-3c4d5e6f7c25', name='EXP-25 the farm, every kind',
        map='CSmallScout_Farm', package='CsmallScout_Farm',
        sha='ae812dfb72da490956f8e29e822a36be6420f414cb4e8c1ede6c7cc2e9bf9163',
        moved=(('XComDestructibleActor_153', (0, 192)),),
        deleted=('XComDestructibleActor_4',),
        copied=(('XComDestructibleActor_153', (-481, 191)), ('XComCollectible_12', (1872, -1232))),
        assemblies=(('XComLadder_4', 0, (0, 3), 0),                  # along the lean-to, where EXP-22 moved it
                    ('XComDestructibleActor_91', 0, (14, 10), 0)),   # the flatbed truck
        view=dict(camera=[100, 3200, -2400], target=[100, 0, 0])),
    'demolition': dict(
        id='25d0a0b1-2525-4d0a-8e25-3c4d5e6f7d25', name='EXP-25 the demolition site, every kind',
        map='URB_Demolition_EWI', sha='18fbffb08a0b1870576fe2d7f24b937ec3400e17b7307d1d2da67541068f25fc',
        moved=(('XComDestructibleActor_100', (192, 0)),),
        deleted=('XComDestructibleActor_156',),
        copied=(('XComDestructibleActor_363', (-1580, 233)),),
        assemblies=(('XComLadder_4', 0, (0, 2), 0),                  # a drain pipe, along its site office
                    ('XComDestructibleActor_83', 0, (0, 7), 0)),     # the SUV
        view=dict(camera=[200, 3200, -2900], target=[200, 0, -500])),
    'truckstop': dict(
        id='25e0a0b1-2525-4d0a-8e25-3c4d5e6f7e25', name='EXP-25 the truck stop, every kind',
        map='URB_TruckStop_EWI', sha='7037aaff0e564fa6608d7f89b093936e4f2c10e4f5a3c863e2495701848dc61a',
        moved=(('XComDestructibleActor_32', (192, 0)),),
        deleted=('XComDestructibleActor_415',),
        copied=(('XComDestructibleActor_216', (1879, -433)),),
        assemblies=(('XComLadder_7', 0, (2, 0), 0),                  # a tall drain pipe, along its wall
                    ('XComDestructibleActor_197', 0, (3, 0), 0)),    # the semi truck cab
        view=dict(camera=[0, 4200, -3200], target=[0, 0, 100])),
    'hurricane': dict(
        id='25f0a0b1-2525-4d0a-8e25-3c4d5e6f7f25', name='EXP-25 the hurricane street, every kind',
        map='URB_StreetHurricane_Terror', sha='eca55ecc31d617ec54344aac7aa66ddc1a83e322d0bc9b7cefc059f0d78db295',
        moved=(('XComDestructibleActor_50', (192, 0)),),
        deleted=('XComDestructibleActor_14',),
        copied=(('XComDestructibleActor_52', (-535, 625)),),
        assemblies=(('XComDestructibleActor_98', 1, (71, -36), 0),),  # the sedan
        view=dict(camera=[400, 3200, -2400], target=[400, 0, 200])),
}


def main():
    a = argparse.ArgumentParser()
    a.add_argument('run', choices=sorted(RUNS))
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    run = RUNS[args.run]
    ID, MAP = run['id'], run['map']
    PACKAGE = run.get('package', MAP)
    copy_id = ID[:8] + '-2525-4a25-9c25-0d1e2f3a4' + ID[2] + '%02d'
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=run['sha'], exporterVersion=16)))
    origin = scene['tileGrid']['origin'][:2]
    assemblies = compiler.assemblies(scene, PACKAGE)
    pieces = lambda piece: [m.split('.')[-1] for m in assemblies[PL + piece]['members']]  # noqa: E731

    def parts(name):
        found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + name]
        assert found, name
        return found

    def grid_pose(src, turns, tiles, storeys):
        # the pose the recipe snap gives: quarter turns about the grid's corner, whole tiles and storeys, exactly
        x, y = compiler.turned((src['location'][0] - origin[0], src['location'][1] - origin[1]), turns)
        at = [origin[0] + x + compiler.TILE * tiles[0], origin[1] + y + compiler.TILE * tiles[1],
              src['location'][2] + compiler.STOREY * storeys]
        rot = [src['rotation'][0], src['rotation'][1] + turns * compiler.QUARTER, src['rotation'][2]]
        return compiler.nearest_grid_pose(src['location'], src['rotation'], at, rot, origin)

    target = lambda name: dict(package=PACKAGE, level='base', actor=PL + name)  # noqa: E731
    overrides = []
    for name, (dx, dy) in run['moved']:
        src = parts(name)[0]
        overrides.append(dict(target=target(name), location=[src['location'][0] + dx, src['location'][1] + dy,
                                                             src['location'][2]], rotation=list(src['rotation'])))
    overrides += [dict(target=target(name), deleted=True) for name in run['deleted']]
    added = []

    def add(name, loc, rot):
        found = parts(name)
        k = len(added) + 1
        added.append(dict(id=copy_id % k, actor=PL + '%s_copy%d' % (name, k), **{'from': target(name)},
                          components=sorted(o['component'] for o in found), location=loc, rotation=rot))

    for name, (x, y) in run['copied']:
        src = parts(name)[0]
        add(name, [x, y, src['location'][2]], list(src['rotation']))
    for piece, turns, tiles, storeys in run['assemblies']:
        for name in pieces(piece):
            add(name, *grid_pose(parts(name)[0], turns, tiles, storeys))
    # As the editor names a project's output (web/project.js outputNames): 30 characters at most for the patch (T-09).
    stem = MAP[:12]
    ship = '%s_%s_%s' % (stem, 'Exp25'[:compiler.NAME_LIMIT - len('patch_') - len(stem) - 6], ID[:4])
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=run['name'], mode='edit',
               source=dict(map=MAP, package=PACKAGE + '.upk', sha256=run['sha'], exporterVersion=16),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added), view=run['view'])
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
    print('saved %s (%s) revision %d in %s as %s: %d moved, %d deleted, %d added; assemblies %s; %d warnings'
          % (run['name'], ID, saved['revision'], store.path(ID), ship, report['counts']['moved'],
             report['counts']['deleted'], report['counts']['added'],
             [(m['id'], m['turns'], m['translation']) for m in report['assemblies']], len(report['warnings'])))
    for w in report['warnings']:
        print('  warning:', w.get('code'), w.get('message'))
    for x in added:
        print('  %s at %s %s' % (x['actor'].split('.')[-1], [round(v, 2) for v in x['location']], x['rotation']))


if __name__ == '__main__':
    main()
