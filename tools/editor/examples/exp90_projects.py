"""EXP-90's project: made pieces in the free form (the custom geometry improvements plan, its section 7's game runs),
on URB_Bar's car park.

The car park's cars and vans are deleted (each assembly whole) so the pieces have room, as in EXP-81 and EXP-84. Walls
are copies of URB_Bar's inside wall (XComDecoFracLevelActor_17, the default look), floors of its upstairs floor
(XComFracLevelActor_17, look 'floor', plate 192 to 194 over the piece's origin). Every piece is a free-form request
(fracWall 5, fracSlab 4; numbers with `free: 1`), on the lot (floor 0):
- A: a wall along x, its start 30.25 off a tile line and its line 40.5 off one ((-1889.75, -1111.5)), 287.5 long, two
  storeys (bottom -16, top 384), a window from 64 to 136 along it (72 to 168 up) and a doorway from 156 to 268 (from
  the floor to 160) that spans the game tile column x -1729 to -1633;
- B: an upper floor 230.5 by 170.25 against A's north face ((-1840.25, -1103.5)), a hole from 40.25 to 80.25 along x
  and 118.5 to 158.5 along y, across the game tiles' edge at y -961;
- C: two one-storey walls at a free angle meeting end to end: C1 from (-1250.5, -1440.25), 384 long, yaw 5461 (30
  degrees); C2 from C1's far end (worked out from the rounded yaw), 288 long, yaw 21845 (120 degrees): a right-angled
  corner the compiler mitres;
- D: walls along x at y -576: D1 from x -1920, 260 tall (bottom -16, top 244), D2 from -1536, 600 tall with tall
  'repeat', D3 from -1152, 600 tall with tall 'stretch' (each two tiles long), D4 from -768, 48 thick (faces at -24
  and 24), two storeys, a doorway in its middle tile;
- E: an upper floor 288 by 192 turned 20 degrees about the vertical (yaw 3641) from (-400.5, -1440.25);
- F: two two-storey walls along x at y -864, F1 from x -480 with its faces mapped (size 64 by 64, turned 30 degrees),
  F2 from x 0 unmapped, both 288 long in the same look.
The car park's wheel stops (ParkingBlock) are deleted too: they stood under C and E. The squad lands east of all of it
(the map's landing: soldiers at x 528 to 912, y -1488 to -1200).
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp90_projects.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; URB_Bar must have been
opened in the editor."""
import argparse
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import build  # noqa: E402
import compiler  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, PL = 'URB_Bar', 'TheWorld.PersistentLevel.'
WALL_DONOR, FLOOR_DONOR = 'XComDecoFracLevelActor_17', 'XComFracLevelActor_17'
PROJECT = ('00000000-0000-4000-8000-0000000e9000', 'EXP-90 free form pieces')
LOT = 0.0
LOT_BOX = (-2112.0, 1440.0, -1536.0, -288.0)        # the car park (x0, x1, y0, y1): its cars and vans go
STOPS = 'ParkingBlock.Meshes.ParkingBlock'          # and its wheel stops
BAR_WALL = dict(y0=-8.0, y1=8.0, z0=-16.0)          # the inside wall's faces and bottom (walls.js BAR_SPEC)
TWO, ONE = 384.0, 192.0                             # its tops at two storeys and one
DOORWAY = dict(z0=-16.0, z1=160.0)
MAPPING = dict(surfaces=dict(faces=dict(mode='size', u=64.0, v=64.0, turn=30.0)))
C1_AT, C1_YAW, C1_LONG = (-1250.5, -1440.25), 5461, 384.0
C2_YAW, C2_LONG = 21845, 288.0


def wall(x1, z1, seed, openings=(), **more):
    """A free-form inside wall from x 0 to x1, its top z1; `more` overrides its faces (y0, y1), sets `tall` or adds a
    mapping."""
    numbers = dict(free=1, x0=0.0, x1=x1, z1=z1, tall='repeat', openings=list(openings), seed=seed)
    numbers.update(BAR_WALL)
    numbers.update(more)
    return dict(kind='fracWall', version=5, wall=numbers)


def slab(x1, y1, seed, holes=()):
    return dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0.0, x1=x1, y0=0.0, y1=y1, z0=192.0, z1=194.0,
                                                      holes=list(holes), seed=seed, look='floor'))


def c1_end():
    """C1's far end, from its yaw as the package holds it (a whole rotator), to the ten-thousandth a project keeps."""
    yaw = C1_YAW * 2 * math.pi / 65536
    return [round(C1_AT[0] + C1_LONG * math.cos(yaw), 4), round(C1_AT[1] + C1_LONG * math.sin(yaw), 4)]


PIECES = (
    # (label, donor, location, yaw, generated)
    ('A', WALL_DONOR, [-1889.75, -1111.5, LOT], 0,
     wall(287.5, TWO, 901, [dict(x0=64.0, x1=136.0, z0=72.0, z1=168.0), dict(x0=156.0, x1=268.0, **DOORWAY)])),
    ('B', FLOOR_DONOR, [-1840.25, -1103.5, LOT], 0, slab(230.5, 170.25, 902, [dict(x0=40.25, x1=80.25, y0=118.5, y1=158.5)])),
    ('C1', WALL_DONOR, [C1_AT[0], C1_AT[1], LOT], C1_YAW, wall(C1_LONG, ONE, 903)),
    ('C2', WALL_DONOR, c1_end() + [LOT], C2_YAW, wall(C2_LONG, ONE, 904)),
    ('D1', WALL_DONOR, [-1920.0, -576.0, LOT], 0, wall(192.0, 244.0, 905)),
    ('D2', WALL_DONOR, [-1536.0, -576.0, LOT], 0, wall(192.0, 584.0, 906, tall='repeat')),
    ('D3', WALL_DONOR, [-1152.0, -576.0, LOT], 0, wall(192.0, 584.0, 907, tall='stretch')),
    ('D4', WALL_DONOR, [-768.0, -576.0, LOT], 0, wall(288.0, TWO, 908, [dict(x0=96.0, x1=192.0, **DOORWAY)], y0=-24.0, y1=24.0)),
    ('E', FLOOR_DONOR, [-400.5, -1440.25, LOT], 3641, slab(288.0, 192.0, 909)),
    ('F1', WALL_DONOR, [-480.0, -960.0, LOT], 0, wall(288.0, TWO, 910, mapping=MAPPING)),
    ('F2', WALL_DONOR, [0.0, -960.0, LOT], 0, wall(288.0, TWO, 910)),
)


def added(scene):
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    return [dict(id='00000000-0000-4000-8000-0000000e90%02d' % (k + 1), actor=PL + '%s_copy%d' % (donor, k + 1),
                 **{'from': dict(package=MAP, level='base', actor=PL + donor)}, components=[by_actor[PL + donor]['component']],
                 location=location, rotation=[0, yaw, 0], prefab=None, partner=None, generated=generated)
            for k, (label, donor, location, yaw, generated) in enumerate(PIECES)]


def lot_deletes(scene):
    """Delete records for the car park's cars and vans, each assembly whole, and its wheel stops."""
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    out = []
    for o in by_actor.values():
        x, y = (o.get('location') or [None, None])[:2]
        if (scene['meshes'].get(str(o.get('mesh')), {}).get('name') == STOPS and x is not None
                and LOT_BOX[0] <= x <= LOT_BOX[1] and LOT_BOX[2] <= y <= LOT_BOX[3]):
            out.append(dict(target=dict(package=MAP, level='base', actor=o['actor']), deleted=True))
    for pivot, a in sorted(compiler.assemblies(scene, MAP).items()):
        if a.get('family') not in ('car', 'van') or pivot not in by_actor:
            continue
        x, y = by_actor[pivot]['location'][:2]
        if LOT_BOX[0] <= x <= LOT_BOX[1] and LOT_BOX[2] <= y <= LOT_BOX[3]:
            out += [dict(target=dict(package=MAP, level='base', actor=m), deleted=True) for m in a['members']]
    return sorted(out, key=lambda r: r['target']['actor'])


def in_the_way(scene, deletes):
    """The map's own pieces left standing within a tile of a group's ground (the ground must be clear): (label, actor)."""
    gone = {d['target']['actor'] for d in deletes}
    groups = dict(AB=(-1985.0, -1505.0, -1210.0, -835.0), C=(-1350.0, -800.0, -1540.0, -900.0),
                  D=(-2016.0, -384.0, -672.0, -480.0), E=(-560.0, 0.0, -1536.0, -1100.0), F=(-576.0, 384.0, -1056.0, -864.0))
    out = []
    for o in scene['objects']:
        if o.get('layer') != 'base' or o['actor'] in gone or not o.get('mesh') or o.get('location') is None:
            continue
        x, y, z = o['location']
        for label, (x0, x1, y0, y1) in groups.items():
            if x0 <= x <= x1 and y0 <= y <= y1 and -40 < z < 600:
                mesh = scene['meshes'].get(str(o['mesh']), {}).get('name', '')
                out.append((label, o['actor'].split('.')[-1], mesh, [round(v) for v in o['location']]))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--build', action='store_true')
    a.add_argument('--quick', action='store_true', help='with --build: without baking')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    base = build.lwr_file(game, 'CookedPCConsole', MAP + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=MAP, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    print('base map %s (SHA-256 %s), export %s' % (base.name, sha[:12], export.parent.name))
    store = projects.ProjectStore(args.store)
    project_id, name = PROJECT
    try:
        current = store.load(project_id)
    except projects.ProjectError:
        current = None
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']
    else:
        claims = outputnames.Claims(store.root, str(args.builds), [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, MAP))
        output.pop('reason', None)
    pieces = added(scene)
    deletes = lot_deletes(scene)
    print('deleted from the car park: %d pieces of its cars and vans' % len(deletes))
    print('map pieces standing on the groups\' ground:', json.dumps(in_the_way(scene, deletes)))
    print('C1 ends at %s: C2 starts there' % c1_end())
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=deletes, added=pieces, groups=[], buildings=[],
               nextSerial=len(pieces) + 1, view=dict(camera=[-900, 1400, -2600], target=[-900, 0, -900]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:300]) for w in report['warnings']], indent=1))
    print('notes', json.dumps([(w['code'], w['message'][:300]) for w in report['notes']
                               if w['code'].startswith(('made', 'slab', 'wall', 'floor'))], indent=1))
    labels = {p['actor']: label for p, (label, *_) in zip(pieces, PIECES)}
    _, native = compiler.native_split(compiler.stream_only(spec))
    for c in native['copies']:
        g = c.get('generated') or {}
        if g.get('kind') in ('fracWall', 'fracSlab'):
            n = g.get('wall') or g.get('slab')
            print('  %-4s %-40s at %-30s yaw %-6d v%d x %g..%g y %g..%g z %g..%g%s%s%s' % (
                labels.get(PL + c['label'].split('.')[-1], ''), c['label'], [round(v, 4) for v in c['location']],
                round(c['rotation'][1]), g['version'], n['x0'], n['x1'], n['y0'], n['y1'], n['z0'], n['z1'],
                ', ends %s' % json.dumps(n['ends']) if n.get('ends') else '', ', whole %s' % n['whole'] if n.get('whole') else '',
                ', mapping' if n.get('mapping') else ''))
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    if not args.build:
        return
    try:
        m = build.Build(build.BuildInputs(store.path(project_id), s['cache'], args.builds, game, s['udk'],
                                          quick=args.quick)).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
