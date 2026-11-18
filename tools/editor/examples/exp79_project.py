"""EXP-79's projects: run D of the custom geometry plan (stage M4, looks from any piece), two showrooms on the blank
map (CB2_MP_Blank, its size set by the project), each look made from numbers beside a copy of its donor in the same
light.

- `walls`: the twelve walls shortlisted on 18 November (research/evidence/wall-look-audit-2026-11-18.json, its
  recommended ones that are no alternate), a row each, running east: a copy of the donor as it stands in its map
  (a quarter turn and whole tiles and storeys from its place there, so its length runs east and its bottom is at the
  floor), then two tiles on a made wall of the donor's length at its donor's height (its twin), then three tiles on
  a longer made wall, four tiles more, with a doorway in its middle tile. Rows are four tiles apart, so one grenade
  between two rows reaches both longer walls.
- `floors`: six floors and roofs (a flat floor, a flat roof, a pitched roof and a thick roof made flat, and two
  layouts other than the Bar's: a three-slot floor and a one-slot roof), each a copy of its donor with a made slab of
  the donor's footprint beside it at the same height; and eight ground looks (one from a donor placed at 0.6), each
  a copy of its donor plane with a made block (three tiles square, 64 high) and a made patch (three tiles square) on
  it, or beside a donor that is no plane.
- `eyedropper`: on URB_Bar, a plain copy of another map's floor (URB_TruckStop's floor deck) on the parking lot. The
  editor's eyedropper then takes the look of the bar's own facade wall and of that floor, and a wall and a slab are
  drawn in them and saved there (the browser check, EXP-79): once the project is in the store, the script leaves it
  as it is and only compiles and builds it.

Each made piece names its look by its donor (`look: {mesh, measure}`, a ground look's also `material`): walls request
version 3, slabs and ground version 2. The recipes come from the checked-in catalogues (tools/bake/looks/). Donors from
other maps come through the library (it must have been scanned). The blank map's own pieces (two cars and their glass,
a floor-corner wall) are deleted.

Usage: exp79_project.py walls|floors|eyedropper --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'."""
import argparse
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import build  # noqa: E402
import compiler  # noqa: E402
import library  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, PL = 'CB2_MP_Blank', 'TheWorld.PersistentLevel.'
TILE, LEVEL, Q = 96.0, 64.0, 16384
LOOKS = ROOT / 'tools' / 'bake' / 'looks'
AUDIT = ROOT / 'research' / 'evidence' / 'wall-look-audit-2026-11-18.json'
# the blank map's own pieces, deleted: two cars, their glass, a floor-corner wall
DELETED = ('XComDestructibleActor_0', 'XComDestructibleActor_1', 'XComFracLevelActor_0', 'XComFracLevelActor_1',
           'XComDecoFracLevelActor_0')
PROJECTS = {
    'walls': ('00000000-0000-4000-8000-0000000e7900', 'EXP-79 walls', '0000000e79'),
    'floors': ('00000000-0000-4000-8000-0000000e7a00', 'EXP-79 floors and ground', '0000000e7a'),
    'eyedropper': ('00000000-0000-4000-8000-0000000e7b00', 'EXP-79 eyedropper', '0000000e7b'),
}
# the eyedropper project's map, and the other map's floor copied onto its parking lot: (map, actor, at)
EYE_MAP = 'URB_Bar'
EYE_FLOOR = ('URB_TruckStop', 'XComFracLevelActor_0', (-1728.0, -1440.0))
# the six floors and roofs (slabs.json meshes): (label, mesh)
SLABS = (
    ('FlatFloor', 'ComKit_Meshes.Cores.Core_384CFloorB_FRACTURED'),
    ('FlatRoof', 'URB_MilitaryAmmo_FRAC.Meshes.URBMilAmmoSubRoof_FRACTURED'),
    ('Pitched', 'URB_ResearchOutpost_FRAC.Meshes.ROShedRoof_FRACTURED'),
    ('Thick', 'SubwayTrain.Meshes.SubwayCarRoof_FRACTURED'),
    ('ThreeSlot', 'URB_TruckStop_FRAC.Meshes.TS_FloorDeck_FRACTURED'),
    ('OneSlot', 'URB_SmallCemetery_FRAC.Meshes.URBSmCemShedRoof_FRACTURED'),
)
# the eight ground looks (ground.json, by map and actor): (label, map, actor)
GROUNDS = (
    ('Asphalt', 'URB_CommercialAlley', 'StaticMeshActor_50'),
    ('DirtBlend', 'URB_GasStation_EWI', 'XComLevelActor_10'),
    ('Grass', 'URB_Demolition_EWI', 'XComLevelActor_13'),
    ('Snow', 'EWI_ChryssalidHive', 'XComLevelActor_1206'),
    ('ConcreteScaled', 'URB_StreetOverpass_EWI', 'XComLevelActor_264'),
    ('Sidewalk', 'URB_Boulevard', 'StaticMeshActor_18'),
    ('StoneRed', 'DLC1_1_LowFriends', 'XComLevelActor_161'),
    ('Sandstone', 'URB_SmallCemetery', 'XComLevelActor_678'),
)
GAP_TWIN, GAP_LONG, ROW = 2, 3, 4      # tiles: donor to twin, twin to the longer wall, row to row
PLANE_TOP = 4.0     # a ground donor plane's top: over the stage's ground planes (their tops at 2)


def catalogue(name):
    return json.loads((LOOKS / (name + '.json')).read_text(encoding='utf-8'))


def short(actor):
    return actor.split('.')[-1]


class Donors:
    """Donor placings read through the library: each one's record (library.piece) and its pose on this map."""

    def __init__(self, cache, game, grid):
        self.cache, self.game, self.grid, self.shared = cache, game, grid, {}

    def record(self, package, actor):
        return library.piece(self.cache, self.game, dict(package=package, level='base', actor=short(actor)), self.shared)

    def placing(self, package, actor):
        """(the record, its object for the actor, its location said on this map's grid)."""
        r = self.record(package, actor)
        objs = [o for o in r['objects'] if short(o['actor']) == short(actor)]
        if not objs:
            raise SystemExit('%s has no %s in the library' % (package, actor))
        o = objs[0]
        shift = [a - b for a, b in zip(self.grid, r['grid'])] if r.get('grid') else [0.0, 0.0, 0.0]
        return r, o, [v + d for v, d in zip(o['location'], shift)]


def local_box(record, o):
    """The donor mesh's box in its actor's frame, scaled: (min [x, y, z], max [x, y, z])."""
    b = record['meshes'][o['mesh']]['bounds']
    s = o.get('scale') or [1, 1, 1]
    lo = [(b[k] - b[k + 3]) * s[k] for k in range(3)]
    hi = [(b[k] + b[k + 3]) * s[k] for k in range(3)]
    return [min(a, c) for a, c in zip(lo, hi)], [max(a, c) for a, c in zip(lo, hi)]


def world_box(lo, hi, yaw, at):
    """The box of a local box turned by `yaw` (whole quarter turns) about the actor and put at `at`."""
    turns = round(yaw / Q) % 4
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][turns]
    xs, ys = [], []
    for x in (lo[0], hi[0]):
        for y in (lo[1], hi[1]):
            xs.append(at[0] + x * c - y * s)
            ys.append(at[1] + x * s + y * c)
    return [min(xs), min(ys), at[2] + lo[2]], [max(xs), max(ys), at[2] + hi[2]]


def donor_copy(donors, package, actor, x0, y_mid, bottom_at, long_axis_east=True, step=LEVEL):
    """A copy of a donor placing: turned whole quarter turns so its length runs east (when asked), moved whole tiles so
    its box starts at x0 and is centred on y_mid, and whole storeys so its box's bottom is at `bottom_at` (exactly
    with `step` None: a piece off the tile grid, scenery).
    Returns (added fields, the box)."""
    r, o, at = donors.placing(package, actor)
    if o['rotation'][0] or o['rotation'][2] or o['rotation'][1] % Q:
        raise SystemExit('%s.%s is not square to the world (rotation %r)' % (package, actor, o['rotation']))
    lo, hi = local_box(r, o)
    yaw = o['rotation'][1]
    if long_axis_east:
        for k in range(4):
            wlo, whi = world_box(lo, hi, yaw + k * Q, at)
            if whi[0] - wlo[0] >= whi[1] - wlo[1]:
                yaw += k * Q
                break
    wlo, whi = world_box(lo, hi, yaw, at)
    dx = round((x0 - wlo[0]) / TILE) * TILE
    dy = round((y_mid - (wlo[1] + whi[1]) / 2) / TILE) * TILE
    dz = (bottom_at - wlo[2]) if step is None else round((bottom_at - wlo[2]) / step) * step
    location = [at[0] + dx, at[1] + dy, at[2] + dz]
    box = world_box(lo, hi, yaw, location)
    fields = dict(components=[o['component']], location=location, rotation=[0, yaw, 0],
                  **{'from': dict(package=r['source']['package'], level='base', actor=PL + short(actor))})
    return fields, box, (r, o)


def made_copy(donors, package, actor, location, yaw, generated):
    r, o, _ = donors.placing(package, actor)
    return dict(components=[o['component']], location=location, rotation=[0, yaw, 0], generated=generated,
                **{'from': dict(package=r['source']['package'], level='base', actor=PL + short(actor))})


def walls(donors, origin):
    """The walls showroom's pieces: [(label, added fields)] and the extent [x max, y max]."""
    cat = catalogue('walls')
    by = {e['mesh']: e for e in cat['looks']}
    chosen = [r['mesh'] for r in json.loads(AUDIT.read_text(encoding='utf-8'))['recommended'] if not r['alternate']]
    out, xmax = [], origin[0]
    x0, y0 = origin[0] + 4 * TILE, origin[1] + 4 * TILE
    for row, mesh in enumerate(chosen):
        e = by.get(mesh)
        if e is None:
            raise SystemExit('the walls catalogue has no %s' % mesh)
        rec = e['recipe']
        y = y0 + row * ROW * TILE
        # the donor's bottom at the recipe's bottom over the floor (z 0): the made wall stands where its donor does
        fields, box, _ = donor_copy(donors, e['map'], e['actor'], x0, y, rec['bottom'])
        out.append(('W%02d_donor' % row, fields))
        length = float(e['facts']['size']['length'])
        look = dict(mesh=mesh, measure=cat['measure'])
        tx = math.ceil((box[1][0] + GAP_TWIN * TILE) / TILE) * TILE
        twin = dict(kind='fracWall', version=3, wall=dict(x0=0.0, x1=length, openings=[], seed=7900 + row, look=look))
        # (a made wall's height is free: it stands level with its donor's copy, its bottom where the donor's is)
        z = box[0][2] - rec['bottom']
        out.append(('W%02d_twin' % row, made_copy(donors, e['map'], e['actor'], [tx, y, z], 0, twin)))
        lx = math.ceil((tx + length + GAP_LONG * TILE) / TILE) * TILE
        tiles = math.ceil(length / TILE) + 4
        door = tiles // 2
        longer = dict(kind='fracWall', version=3, wall=dict(
            x0=0.0, x1=tiles * TILE, seed=7950 + row, look=look,
            openings=[dict(x0=door * TILE, x1=door * TILE + TILE, z0=rec['bottom'], z1=rec['bottom'] + 176.0)]))
        out.append(('W%02d_long' % row, made_copy(donors, e['map'], e['actor'], [lx, y, z], 0, longer)))
        xmax = max(xmax, lx + tiles * TILE)
    return out, [xmax, y0 + (len(chosen) - 1) * ROW * TILE + 2 * TILE]


def floors(donors, origin):
    """The floors showroom's pieces: [(label, added fields)] and the extent [x max, y max]."""
    out, xmax, ymax = [], origin[0], origin[1]
    slabs = catalogue('slabs')
    by = {e['mesh']: e for e in slabs['looks']}
    x, y, depth = origin[0] + 4 * TILE, origin[1] + 4 * TILE, 0.0
    for k, (label, mesh) in enumerate(SLABS):
        e = by[mesh]
        rec = e['recipe']
        # the donor's top at the recipe's top over z 0, so the made slab's plate and the donor's are level
        fields, box, (r, o) = donor_copy(donors, e['map'], e['actor'], x, 0.0, 0.0, long_axis_east=False)
        lo, hi = local_box(r, o)
        # moved so its box's south edge is at y, its top at the recipe's top
        dy = round((y - box[0][1]) / TILE) * TILE
        dz = round((rec['top'] - box[1][2]) / LEVEL) * LEVEL
        fields['location'] = [fields['location'][0], fields['location'][1] + dy, fields['location'][2] + dz]
        box = world_box(lo, hi, fields['rotation'][1], fields['location'])
        out.append(('%s_donor' % label, fields))
        w = min(compiler.FRAC_SLAB_MAX_TILES * TILE, max(TILE, round((box[1][0] - box[0][0]) / TILE) * TILE))
        d = min(compiler.FRAC_SLAB_MAX_TILES * TILE, max(TILE, round((box[1][1] - box[0][1]) / TILE) * TILE))
        sx = math.ceil((box[1][0] + 2 * TILE) / TILE) * TILE
        sy = math.floor(box[0][1] / TILE) * TILE
        slab = dict(kind='fracSlab', version=2, slab=dict(x0=0.0, x1=w, y0=0.0, y1=d, seed=7900 + k, holes=[],
                                                          look=dict(mesh=mesh, measure=slabs['measure'])))
        # (its plate's top level with the donor's)
        out.append(('%s_made' % label, made_copy(donors, e['map'], e['actor'], [sx, sy, box[1][2] - rec['top']], 0, slab)))
        right = sx + w
        xmax, depth = max(xmax, right), max(depth, max(box[1][1], sy + d) - y)
        x = math.ceil((right + 3 * TILE) / TILE) * TILE
        if k % 3 == 2:      # three a row
            x, y, depth = origin[0] + 4 * TILE, math.ceil((y + depth + 3 * TILE) / TILE) * TILE, 0.0
    ground = catalogue('ground')
    gby = {(e['map'], short(e['actor'])): e for e in ground['looks']}
    x, depth = origin[0] + 4 * TILE, 0.0
    for k, (label, package, actor) in enumerate(GROUNDS):
        e = gby[(package, actor)]
        look = dict(mesh=e['mesh'], material=e['material'], measure=ground['measure'])
        fields, box, _ = donor_copy(donors, package, actor, x, 0.0, 0.0, long_axis_east=False, step=None)
        r, o, _ = donors.placing(package, actor)
        lo, hi = local_box(r, o)
        dy = round((y - box[0][1]) / TILE) * TILE
        flat = e['facts'].get('shape') == 'flat' and hi[2] - lo[2] < 8
        # a plane's top just over the stage's ground (z 0, its planes' tops at 2); another donor's bottom on it (scenery
        # takes any height)
        dz = (PLANE_TOP - box[1][2]) if flat else (0.0 - box[0][2])
        fields['location'] = [fields['location'][0], fields['location'][1] + dy, fields['location'][2] + dz]
        box = world_box(lo, hi, fields['rotation'][1], fields['location'])
        out.append(('%s_donor' % label, fields))
        top = box[1][2] if flat else 0.0
        # on the plane (its middle) or beside the donor
        if flat and box[1][0] - box[0][0] >= 7 * TILE and box[1][1] - box[0][1] >= 3 * TILE:
            bx = math.ceil(box[0][0] / TILE) * TILE
            by_ = math.ceil(box[0][1] / TILE) * TILE
        else:
            bx, by_ = math.ceil((box[1][0] + 2 * TILE) / TILE) * TILE, math.floor(box[0][1] / TILE) * TILE
        block = dict(kind='ground', version=2, ground=dict(shape='block', x0=0.0, x1=3 * TILE, y0=0.0, y1=3 * TILE,
                                                           height=64.0, look=look))
        patch = dict(kind='ground', version=2, ground=dict(shape='patch', x0=0.0, x1=3 * TILE, y0=0.0, y1=3 * TILE,
                                                           look=look))
        out.append(('%s_block' % label, made_copy(donors, package, actor, [bx, by_, top], 0, block)))
        out.append(('%s_patch' % label, made_copy(donors, package, actor, [bx + 4 * TILE, by_, top], 0, patch)))
        right = max(box[1][0], bx + 7 * TILE)
        xmax, depth = max(xmax, right), max(depth, max(box[1][1], by_ + 3 * TILE) - y)
        x = math.ceil((right + 3 * TILE) / TILE) * TILE
        if k % 4 == 3:      # four a row
            x, y, depth = origin[0] + 4 * TILE, math.ceil((y + depth + 3 * TILE) / TILE) * TILE, 0.0
        ymax = max(ymax, y + depth)
    return out, [xmax, max(ymax, y)]


def eyedropper(donors, origin):
    """The eyedropper project's first piece: a plain copy of another map's floor on URB_Bar's lot, its box's south-west
    corner near `EYE_FLOOR`'s point and its top at its own storey there (the editor draws the made pieces)."""
    package, actor, (x, y) = EYE_FLOOR
    fields, box, _ = donor_copy(donors, package, actor, x, 0.0, 0.0, long_axis_east=False)
    r, o, _ = donors.placing(package, actor)
    lo, hi = local_box(r, o)
    dy = round((y - box[0][1]) / TILE) * TILE
    dz = round((194.0 - box[1][2]) / LEVEL) * LEVEL      # (a floor over the lot, near the bar's upstairs floor)
    fields['location'] = [fields['location'][0], fields['location'][1] + dy, fields['location'][2] + dz]
    box = world_box(lo, hi, fields['rotation'][1], fields['location'])
    return [('Deck', fields)], [box[1][0], box[1][1]]


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('which', choices=sorted(PROJECTS))
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--build', action='store_true')
    a.add_argument('--quick', action='store_true', help='with --build: without baking')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    the_map = EYE_MAP if args.which == 'eyedropper' else MAP
    base = build.lwr_file(game, 'CookedPCConsole', the_map + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=the_map, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    grid = scene['tileGrid']
    origin = [float(v) for v in grid['origin'][:3]]
    print('base map %s (SHA-256 %s), export %s, grid %s from %s' % (base.name, sha[:12], export.parent.name,
                                                                    grid['dimensions'], origin))
    donors = Donors(s['cache'], game, origin)
    pieces, extent = dict(walls=walls, floors=floors, eyedropper=eyedropper)[args.which](donors, origin)
    size = [int(math.ceil((extent[k] - origin[k]) / TILE)) + 4 for k in range(2)]
    size = [max(int(grid['dimensions'][k]), v) for k, v in enumerate(size)]
    if args.which != 'eyedropper':
        print('the stage: %d by %d tiles' % tuple(size))
    project_id, name, prefix = PROJECTS[args.which]
    store = projects.ProjectStore(args.store)
    try:
        current = store.load(project_id)
    except projects.ProjectError:
        current = None
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']
    else:
        claims = outputnames.Claims(store.root, str(args.builds), [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, the_map))
        output.pop('reason', None)
    added = [dict(id='00000000-0000-4000-8000-%s%02d' % (prefix, k + 1), prefab=None, partner=None,
                  actor=PL + '%s_copy%d' % (short(f['from']['actor']), k + 1), **f)
             for k, (_, f) in enumerate(pieces)]
    overrides = [] if args.which == 'eyedropper' else \
        [dict(target=dict(package=MAP, level='base', actor=PL + n), deleted=True) for n in DELETED]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=the_map, package=the_map + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=overrides, added=added, groups=[], buildings=[],
               nextSerial=len(added) + 1, view=dict(camera=[origin[0] - 600, 1500, origin[1] - 600],
                                                     target=[origin[0] + 1200, 0, origin[1] + 1200]))
    if args.which != 'eyedropper':
        doc['stage'] = dict(grid=size)
    else:
        doc['view'] = dict(camera=[-1200, 900, -2000], target=[-1500, 100, -1300])
    if current and current.get('created'):
        doc['created'] = current['created']
    if args.which == 'eyedropper' and current:
        # (drawn in the editor since: kept as it is)
        doc = current['doc'] if 'doc' in current else current
        added = doc['added']
        pieces = [(short(a['actor']), a) for a in added]
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:300]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    _, native = compiler.native_split(compiler.stream_only(spec))
    names = {short(p['actor']): label for p, (label, _) in zip(added, pieces)}
    print('boxes', json.dumps([(names.get(short(c['label']), c['label']), [round(v) for v in c['box']])
                               for c in native['copies'] if c.get('box')]))
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    if not (args.which == 'eyedropper' and current):
        saved = store.save(project_id, doc, current['revision'] if current else 0)
        print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    if not args.build:
        return
    try:
        m = build.Build(store.path(project_id), s['cache'], args.builds, game, s['udk'], quick=args.quick).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
