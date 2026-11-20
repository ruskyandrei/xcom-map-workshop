"""EXP-51's project: a cleared URB_Bar (Clear map plan, step C9, run 1).

- Every piece of Bar deleted as the editor's Clear map deletes them, the ground too, `cleared` set, at Bar's own size.
- Two landing zones, as clear_bar_project.py's ZONES: Bar's own landing moved four tiles east and turned to face west
  (the zone a plain install plays too), and one added on the car park facing north (Long War only).
- A field of floor round each zone: copies, each in its original's place, of Bar's own floor pieces that carry a
  floor tile within two tiles of the zone's frame, evac box or soldier tiles. Bar's ground is laid in slabs of about
  ten by ten tiles, so each field is a few slabs.
- One building made from nothing beside the added zone: URB_ResearchOutpost's shed, as EXP-44 brought it onto the
  blank map (its walls, roof, doors and four props, and its two floors as a building of the project), on the first
  place of the field that keeps a tile clear of the zone.

Usage: exp51_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened once in the editor at export 22, and the library scanned (viewer.py library scan). Without --full the
lighting is not baked. --store saves the project in the editor's own project store instead (its next revision) and
builds it into the editor's builds folder, so that the editor's Play in game and Land here find it as the project's
last build. A plan of what was laid (plan.json) goes beside it in <out>."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor' / 'examples'), str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import clear_bar_project as clear  # noqa: E402
import compiler  # noqa: E402
import library  # noqa: E402
import settings as settings_module  # noqa: E402
import spawns  # noqa: E402

PROJECT_ID = '00000000-0000-4000-8000-000000000e51'
TILE, LEVEL = 96.0, 64.0
MARGIN = 2 * TILE
HOME = 'URB_ResearchOutpost'
# the shed of EXP-44: its pieces on its home map, and its two floor volumes there ([x0, y0, z0, x1, y1, z1])
SHED = ['XComDecoFracLevelActor_100', 'XComDecoFracLevelActor_101', 'XComDecoFracLevelActor_98',
        'XComDecoFracLevelActor_99', 'XComFracLevelActor_55', 'XComDestructibleActor_159', 'XComInteractiveLevelActor_17',
        'XComDestructibleActor_162', 'XComDestructibleActor_93', 'XComDestructibleActor_421', 'XComDestructibleActor_157']
SHED_FLOORS = [[-192.0, -1536.0, 0.0, 384.0, -960.0, 176.0], [-192.0, -1536.0, 176.0, 384.0, -960.0, 384.0]]


def zone_box(zone):
    """[x0, y0, x1, y1] round everything the zone puts down: the frame, the evac box, the soldier tiles."""
    at = spawns.place(zone)
    xs = [at['frame'][0][0]] + [loc[0] for loc, _ in at['soldiers']]
    ys = [at['frame'][0][1]] + [loc[1] for loc, _ in at['soldiers']]
    e = spawns.evac_box(zone)
    return [min(xs + [e[0]]), min(ys + [e[1]]), max(xs + [e[3]]), max(ys + [e[4]])]


def grow(box, by):
    return [box[0] - by, box[1] - by, box[2] + by, box[3] + by]


def inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def floor_field(scene, zones):
    """Bar's floor pieces with a ground-level floor tile near a zone: {actor: [its tiles' (x, y)]}."""
    near = [grow(zone_box(z), MARGIN) for z in zones]
    grounds = [spawns.ground(z) for z in zones]
    tiles = {}
    for f in scene['tactical']['floorTiles']:
        tiles.setdefault(f['actor'], []).append(f['location'])
    chosen = {}
    for actor, locations in tiles.items():
        if any(inside(b, x, y) and abs(z - g) <= LEVEL / 2 for b, g in zip(near, grounds) for x, y, z in locations):
            chosen[actor] = [(x, y) for x, y, z in locations if any(abs(z - g) <= LEVEL / 2 for g in grounds)]
    return chosen


def copies(scene, actors, serial):
    """Copies in place of the map's own pieces `actors`, as the page saves a copy (one record per actor)."""
    parts = {}
    for o in scene['objects']:
        if o['layer'] == 'base' and o['actor'] in actors:
            parts.setdefault(o['actor'], []).append(o)
    out = []
    for name in sorted(parts):
        serial += 1
        p = parts[name]
        out.append({'id': '00000000-0000-4000-8000-%012d' % (510000 + serial), 'actor': '%s_copy%d' % (name, serial),
                    'from': dict(package=p[0]['sourcePackage'], level='base', actor=name),
                    'components': sorted(o['component'] for o in p),
                    'location': list(p[0]['location']), 'rotation': list(p[0]['rotation'])})
    return out, serial


def shed_place(scene, zone, zones, field_tiles):
    """Where the shed's ground floor box goes on this map: the field's place nearest `zone` whose 6 x 6 tiles are all
    laid floor, off the grid's outer row, and a tile clear of what every zone puts down."""
    origin, (nx, ny, _) = scene['tileGrid']['origin'], scene['tileGrid']['dimensions']
    laid = {(round((x - origin[0] - TILE / 2) / TILE), round((y - origin[1] - TILE / 2) / TILE)) for x, y in field_tiles}
    keeps = [grow(zone_box(z), TILE) for z in zones]
    w = round((SHED_FLOORS[0][3] - SHED_FLOORS[0][0]) / TILE)
    h = round((SHED_FLOORS[0][4] - SHED_FLOORS[0][1]) / TILE)
    zx, zy = zone['location'][:2]
    best = None
    for (i, j) in sorted(laid):
        x0, y0 = origin[0] + i * TILE, origin[1] + j * TILE
        box = [x0, y0, x0 + w * TILE, y0 + h * TILE]
        if i < 1 or j < 1 or i + w > nx - 1 or j + h > ny - 1:
            continue
        if not all((i + a, j + b) in laid for a in range(w) for b in range(h)):
            continue
        if any(not (box[2] < k[0] or box[0] > k[2] or box[3] < k[1] or box[1] > k[3]) for k in keeps):
            continue
        d = ((box[0] + box[2]) / 2 - zx) ** 2 + ((box[1] + box[3]) / 2 - zy) ** 2
        if best is None or d < best[0]:
            best = (d, box)
    assert best, 'no place on the field for the shed'
    return best[1]


def main(argv):
    out = Path(argv[0])
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    cache = s['cache']
    sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', clear.MAP + '.upk').read_bytes()).hexdigest()
    _, scene = compiler.find_export(cache, dict(source=dict(map=clear.MAP, sha256=sha, exporterVersion=22)))
    assert scene['exporterVersion'] >= 22, 'open Bar in the editor first (export 22)'
    zones = [dict(z) for z in clear.ZONES]
    field = floor_field(scene, zones)
    added, serial = copies(scene, set(field), 0)
    field_tiles = [t for ts in field.values() for t in ts]
    # the shed beside the added zone (the second), moved by whole tiles from its home map's place
    box = shed_place(scene, zones[1], zones, field_tiles)
    records = [library.piece(cache, game, dict(package=HOME, level='base', actor=a)) for a in SHED]
    grid = records[0]['grid']
    rebase = [scene['tileGrid']['origin'][k] - grid[k] for k in range(3)]
    want = [box[0], box[1], scene['tileGrid']['origin'][2]]
    step = (TILE, TILE, LEVEL)
    move = [rebase[k] + round((want[k] - (SHED_FLOORS[0][k] + rebase[k])) / step[k]) * step[k] for k in range(3)]
    seen = set()
    for record in records:
        actors = {}
        for o in record['objects']:
            actors.setdefault(o['actor'], []).append(o)
        for name, parts in sorted(actors.items()):
            if name in seen:
                continue
            seen.add(name)
            serial += 1
            added.append({'id': '00000000-0000-4000-8000-%012d' % (510000 + serial), 'actor': '%s_copy%d' % (name, serial),
                          'from': dict(package=HOME, level='base', actor=name),
                          'components': sorted(o['component'] for o in parts),
                          'location': [round(parts[0]['location'][k] + move[k], 4) for k in range(3)],
                          'rotation': list(parts[0]['rotation'])})
    floors = [[round(v + move[k % 3], 4) for k, v in enumerate(b)] for b in SHED_FLOORS]
    buildings = [dict(id='00000000-0000-4000-8000-0000000b0051', name='Shed', kind='building',
                      floors=[dict(boxes=[b]) for b in floors])]
    doc = clear.document(sha, scene, None, zones, added)
    doc.update(id=PROJECT_ID, name='EXP-51 cleared Bar', savedAt='2026-11-13T00:00:00Z', buildings=buildings,
               output=dict(shipAs='URB_Bar_X51', patch='patch_urb_bar_x51'), nextSerial=serial + 1,
               # the viewer's basis (x, up, y): south of the landing, looking north over both zones
               view=dict(camera=[0, 2200, -4200], target=[0, 0, -1300]))
    plan = dict(zones=[dict(id=z['id'], box=zone_box(z), ground=spawns.ground(z),
                            soldiers=[loc for loc, _ in spawns.place(z)['soldiers']]) for z in zones],
                field=sorted(a.rsplit('.', 1)[-1] for a in field), fieldTiles=len(field_tiles),
                shed=dict(box=box, floors=floors, pieces=len(seen)))
    print(json.dumps(plan, indent=1))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'plan.json').write_text(json.dumps(plan, indent=1), encoding='utf-8', newline='\n')
    builds = out / 'builds'
    if '--store' in argv:
        import projects
        store = projects.ProjectStore(s['projects'])
        try:
            revision = store.load(doc['id']).get('revision', 0)
        except projects.ProjectError:
            revision = 0
        saved = store.save(doc['id'], {k: v for k, v in doc.items() if k not in ('revision', 'savedAt')}, revision)
        project, builds = store.path(doc['id']), Path(s['output'])
        doc = store.load(doc['id'])
        print('saved in the editor\'s store as revision %d: %s' % (saved['revision'], project.name))
    else:
        project = out / 'project.json'
        compiler.write_json(project, doc)
    spec, report = compiler.compile_project(doc, scene, library=compiler.Library(cache, game))
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('warnings', json.dumps(sorted({w['code'] for w in report['warnings']})))
    for w in report['warnings']:
        if w['code'].startswith(('landing', 'stage', 'floor')):
            print('  ', w['code'], w['message'][:300])
    if not report['ok'] or '--compile' in argv:
        return 0 if report['ok'] else 1
    try:
        m = build.Build(build.BuildInputs(project, cache, builds, game, s['udk'], quick='--full' not in argv)).run()
    except build.BuildError as error:
        print('build failed:', error)
        return 1
    print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'buildings', 'seconds')}))
    print('package', builds / m['variant'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
