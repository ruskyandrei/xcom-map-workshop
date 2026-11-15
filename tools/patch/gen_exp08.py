"""Writes the EXP-08 spec (tools/patch/examples/exp08blank.json) and, for run 2, its plan for tools/upk/map_picture.py
(tools/upk/plans/urb_bar-blank.json): URB_Bar's play area wiped, ground included, then our own ground and layout from
URB_Bar's own pieces (research/experiments/EXP-08-blank-map.md).

Run 1, the blank grid:
- One copy object per ground plane: URB_Bar's flat asphalt plane (grassPlanes.AsphaltPlaneFlat, 960 x 960, 10 x 10
  tiles, pivot at its centre, z 0) laid on the tile grid. A copier copies each source once, so a fill needs one
  object per plane; the editor's Build will write specs this way too.
- The planes cover every original asphalt plane that reaches into the play area: 6 x 5 of them, x -2784..2976,
  y -2496..2304. The play area (52 x 39 tiles from (-2784, -1920)) needs 6 x 4, but the original row north of it and
  column east of it reach 384 and 192 units in, so they are hidden and covered too.
- One hide box over the play area (z -64..832, the level volume's 0..768 with margin), with the ground
  (KeepGroundHeight -1), lights, volumes and fragments. Actors whose centre is outside it but whose box reaches more
  than EDGE units into it are hidden by name (alsoHide): the edge asphalt, the sidewalk ring, the bushes, a street
  sign. The landing prefabs' pieces are kept, wherever they stand (F-45): the grounded Skyranger, the dropship's
  soldier-spawn volume, its drop-zone marker, spawn points and effects. LWR copies them to the landing zone. The
  intro itself needs the map name too; patchtool's XComMapEdIntro sees to that (map.shipAs).
- A sun object: the map's only light once the hider has taken URB_Bar's out (the moon and the sky light included).

Run 2, a small layout on that ground (all of it from URB_Bar's own pieces):
- The step 3b block (the bar's west block, 12 x 12 tiles, turned 90 degrees, as the L layout's wing) in the middle,
  tiles x 20..31, y 13..24, with its closing end wall (from EXP-07 step 3b) and a door in it, its building volume, the
  wing's wood floor and furniture, and a visible ladder on its north wall.
- A sidewalk ring 4 tiles wide round it (tiles x 16..35, y 9..28): URB_Bar's corner, 8- and 2-tile sidewalk pieces
  turned so that their curbs face out.
- A 4 x 4 hole in the ground (tiles x 3..6, y 27..30): the asphalt plane there is left out and four scaled copies
  fill the rest of its square.
- Three clusters of cover (a dumpster, a box stack, trash or a fence) west, east and south of the ring, and three
  spawned cars on the tile grid, all clear of the seven landing zones and their spawn points (F-06).

Run 3, run 2's layout without the hole (the ground under it is whole again; F-46 is set aside), and the block with two
storeys. Its walls stand 400 high round one tall storey, and its building already has two floors below the roof
(floor volumes z 16..208 and 208..400), so a second floor fits inside the shell:
- The ceiling's I-beams (XComLevelActor_4) are left out: their collision is one solid box under the whole roof
  (z 362..397), which leaves a second floor 151 units of headroom, and the game gave it no floor tiles (run 3a).
  ComKit's storeys have about 190 (a floor at 208..210, the next at 398..402).
- A wood floor at z 210 over the whole block but one corner tile, the ladder well (tile x 20, y 24, the south-west
  room's south-west corner): two copies of the wing's wood floor, each scaled close to its own size so that the
  planks keep their look, overlapping everywhere but the well (11 x 12 and 12 x 11 tiles). They join the building's
  second floor in its floor caches (copier BuildingFloor), so the cutaway hides them with that floor.
- A ladder in the well, against the floor's edge: URB_Bar's metal ladder squashed to 0.42 of its height (200 units),
  so that its top point lands on the new floor's tiles (research/native/ladder-links.md), with no climb loops.
- Two box stacks upstairs for cover.

  python tools/patch/gen_exp08.py [--run 1|2|3] [--photo] [--inventory <tsv>] [--out <json>] [--plan <json>]

--photo adds the overview view (patchtool's photo object, without a light of its own) for an overview shot.
"""
import argparse, csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ap = argparse.ArgumentParser()
ap.add_argument('--run', type=int, choices=(1, 2, 3), default=3)
ap.add_argument('--inventory', help=r"URB_Bar's inventory (default: patchtool's, <lab>\patchtool\maps\URB_Bar-inventory.tsv)")
ap.add_argument('--out', default=os.path.join(HERE, 'examples', 'exp08blank.json'))
ap.add_argument('--plan', default=os.path.join(ROOT, 'tools', 'upk', 'plans', 'urb_bar-blank.json'))
ap.add_argument('--photo', action='store_true', help='add the overview view, for an overview shot')
a = ap.parse_args()
if not a.inventory:
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'lab'))
    import labpaths
    a.inventory = str(labpaths.lab_root() / 'patchtool' / 'maps' / 'URB_Bar-inventory.tsv')

OX, OY, T = -2784, -1920, 96                 # URB_Bar's grid: 52 x 39 x 12 tiles
NX, NY = 52, 39
X0, X1, Y0, Y1 = OX, OX + NX * T, OY, OY + NY * T
EDGE = 8                                     # how far an outside actor must reach in to be hidden by name
GROUND = 'XComLevelActor_242'                # a plain asphalt plane, (-382, -1056, 0)
# The landing prefabs are gameplay, not scenery: LWR's landing-zone mutator spawns copies of their pieces at the
# chosen landing zone with the map's own pieces as templates, so a piece the hider has switched off gives a switched-off
# copy. Run 1 hid the dropship's soldier-spawn volume and drop-zone marker, and the landing cutscene didn't play (F-45).
LANDING = ('DGN_DropShipSoldierSpawn.', 'VEH_Lv1Skyranger_MOD.Prefabs.')
LZ = [[719, -1681], [-1297, -1681], [1103, 1583], [-2065, 1583], [-2641, 143], [1967, 911], [1967, -1489]]


def rng(s):
    lo, hi = s.split('..')
    return float(lo), float(hi)


def by_name(n):
    return (n.rsplit('_', 1)[0], int(n.rsplit('_', 1)[1]))


def wx(tx):
    return OX + T * tx


def wy(ty):
    return OY + T * ty


rows = list(csv.DictReader(open(a.inventory, encoding='utf-8'), delimiter='\t'))
inv = {r['name']: r for r in rows}
KEEP = sorted((r['name'] for r in rows if r['archetype'].startswith(LANDING)), key=by_name)
src = inv[GROUND]
assert src['mesh'] == 'grassPlanes.AsphaltPlaneFlat', src['mesh']
pivot = [float(src['x']), float(src['y']), float(src['z'])]


def loc(name):
    r = inv[name]
    return [float(r['x']), float(r['y']), float(r['z'])]


also, planes = [], []
for r in rows:
    if not r['box x']:
        continue
    bx, by = rng(r['box x']), rng(r['box y'])
    # The hider tests the centre of an actor's bounds, not its pivot (a fence's pivot is at one end).
    x, y = (bx[0] + bx[1]) / 2, (by[0] + by[1]) / 2
    inside = X0 <= x <= X1 and Y0 <= y <= Y1
    # The overlap with the play area along each axis; along an axis where the centre is outside, it is how far the
    # actor reaches in across that edge, and it must be more than EDGE.
    over = min(bx[1], X1) - max(bx[0], X0), min(by[1], Y1) - max(by[0], Y0)
    out = not X0 <= x <= X1, not Y0 <= y <= Y1
    if over[0] <= 0 or over[1] <= 0 or any(o and v <= EDGE for o, v in zip(out, over)):
        continue
    if r['mesh'] == 'grassPlanes.AsphaltPlaneFlat':
        planes.append((bx, by))
    if not inside and r['name'] not in KEEP:
        also.append(r['name'])

# The ground grid: 10-tile planes on tile corners, covering every original plane that reaches into the play area.
gx0 = min(b[0][0] for b in planes); gx1 = max(b[0][1] for b in planes)
step = 10 * T
# x: the originals stand on the 10-tile grid from the origin, about 2 units off; the copies stand on it exactly.
xs = [OX + step * i + step / 2 for i in range(int(round((gx0 - OX) / step)), int(round((gx1 - OX) / step)))]
# y: the originals' rows start 6 tiles off that grid (-2496 = OY - 576), so the copies take the originals' rows,
# snapped to tile corners.
ys = [round((y - OY) / T) * T + OY for y in sorted({(b[1][0] + b[1][1]) / 2 for b in planes})]

# Run 2's hole: tiles x 3..6, y 27..30, inside the plane centred at (-2304, 864) (tiles x 0..9, y 24..33).
HOLE_CELL = (-2304.0, 864)
HOLE = (3, 27, 6, 30)

objects, plan_props, plan_cars = [], [], []


def ground(x, y, scale=None, note=None):
    o = {'type': 'copy', 'from': [GROUND], 'pivot': pivot, 'location': [x, y, pivot[2]], 'extra': ['bLogTiles=False']}
    if scale:
        o['extra'].append('CopyScale=(X=%g,Y=%g,Z=1.0)' % scale)
    if note:
        o['note'] = note
    objects.append(o)
    return o


for y in ys:
    for x in xs:
        if a.run == 2 and (x, y) == HOLE_CELL:
            continue
        ground(x, y)
if a.run == 2:
    # The hole's square, without the hole: two 3 x 10 strips and two 4 x 3 pieces (the plane's pivot is its centre).
    hx0, hy0, hx1, hy1 = HOLE
    cx0, cy0 = 0, 24                           # the square's first tile
    ground(wx(cx0 + 1.5), wy(cy0 + 5), (0.3, 1.0), 'Around the hole: tiles x 0..2, y 24..33.')
    ground(wx(cx0 + 8.5), wy(cy0 + 5), (0.3, 1.0), 'Around the hole: tiles x 7..9, y 24..33.')
    ground(wx(cx0 + 5), wy(cy0 + 1.5), (0.4, 0.3), 'Around the hole: tiles x 3..6, y 24..26.')
    ground(wx(cx0 + 5), wy(cy0 + 8.5), (0.4, 0.3), 'Around the hole: tiles x 3..6, y 31..33.')
n_ground = len(objects)

# One copier logs the 3D cursor's tile (point and F9), and A* paths and floor tiles where the layout needs checking.
if a.run == 1:
    objects[0]['extra'] += [
        'bLogCursor=True',
        'PathProbes(0)=(X=-2400,Y=0,Z=16)', 'PathProbes(1)=(X=1800,Y=1200,Z=16)',      # across the bar's footprint
        'PathProbes(2)=(X=-1500,Y=-1700,Z=16)', 'PathProbes(3)=(X=-1500,Y=1700,Z=16)',  # north to south, west of it
        'PathProbes(4)=(X=960,Y=-400,Z=16)', 'PathProbes(5)=(X=1008,Y=-160,Z=16)',      # by PathBlockingVolume_0 (39, 17)
        'FloorProbes(0)=(X=-480,Y=672,Z=24)', 'FloorProbes(1)=(X=-1056,Y=672,Z=24)',    # where the bar stood
        'FloorProbes(2)=(X=2160,Y=0,Z=24)', 'FloorProbes(3)=(X=0,Y=1776,Z=24)',        # the edges
        'FloorProbes(4)=(X=-2736,Y=-1872,Z=24)', 'FloorProbes(5)=(X=-480,Y=672,Z=88)']  # a corner; a level up
elif a.run == 3:
    objects[0]['extra'] += [
        'bLogCursor=True',
        'PathProbes(0)=(X=-624,Y=240,Z=16)', 'PathProbes(1)=(X=-624,Y=240,Z=216)',     # up the inside ladder
        'PathProbes(2)=(X=-432,Y=-864,Z=16)', 'PathProbes(3)=(X=-288,Y=-96,Z=16)',     # the north sidewalk into the block
        'PathProbes(4)=(X=-240,Y=-816,Z=16)', 'PathProbes(5)=(X=-240,Y=-600,Z=410)',   # up the outside ladder to the roof
        'PathProbes(6)=(X=-288,Y=-96,Z=216)', 'PathProbes(7)=(X=-240,Y=-600,Z=410)',   # second floor to the roof
        'FloorProbes(0)=(X=-624,Y=240,Z=216)', 'FloorProbes(1)=(X=-816,Y=432,Z=216)',  # second floor; the well
        'FloorProbes(2)=(X=-720,Y=432,Z=216)', 'FloorProbes(3)=(X=-288,Y=-96,Z=24)',   # the ladder's top tile; inside
        'FloorProbes(4)=(X=-288,Y=-96,Z=216)', 'FloorProbes(5)=(X=-288,Y=-96,Z=410)',  # second floor; roof
        'FloorProbes(6)=(X=240,Y=-624,Z=216)', 'FloorProbes(7)=(X=-2304,Y=864,Z=24)']  # over the porch; the old hole
else:
    objects[0]['extra'] += [
        'bLogCursor=True',
        'PathProbes(0)=(X=-2640,Y=864,Z=16)', 'PathProbes(1)=(X=-1968,Y=864,Z=16)',    # across the hole, west to east
        'PathProbes(2)=(X=-2304,Y=528,Z=16)', 'PathProbes(3)=(X=-2304,Y=1200,Z=16)',   # across it, north to south
        'PathProbes(4)=(X=-432,Y=-864,Z=16)', 'PathProbes(5)=(X=-288,Y=-96,Z=16)',     # the north sidewalk into the block
        'PathProbes(6)=(X=-240,Y=-816,Z=16)', 'PathProbes(7)=(X=-240,Y=-600,Z=410)',   # up the ladder to the roof
        'FloorProbes(0)=(X=-2304,Y=864,Z=24)', 'FloorProbes(1)=(X=-2448,Y=720,Z=24)',  # the hole: middle, corner tile
        'FloorProbes(2)=(X=-2640,Y=864,Z=24)', 'FloorProbes(3)=(X=-1056,Y=-96,Z=24)',  # beside it; the west sidewalk
        'FloorProbes(4)=(X=-288,Y=-96,Z=24)', 'FloorProbes(5)=(X=-288,Y=-96,Z=410)']   # inside the block; its roof

if a.run >= 2:
    wing = json.load(open(os.path.join(HERE, 'examples', 'exp07wing.json')))['objects']
    block = json.load(open(os.path.join(HERE, 'examples', 'exp07block.json')))['objects']
    assert wing[0]['from'][0] == 'XComDecoFracLevelActor_7' and wing[0]['pivot'] == [-1056, 672, 16]
    WING_C = wing[0]['location']               # (192, -576, 16)
    C = [-288, -96, 16]                        # the block's centre here: tiles x 20..31, y 13..24
    d = [C[0] - WING_C[0], C[1] - WING_C[1]]

    def shifted(o):
        return [o['location'][0] + d[0], o['location'][1] + d[1], o['location'][2]]

    bi = len(objects)
    # Run 3 leaves the ceiling's I-beams out: their collision is one box under the whole roof, too low over a second floor.
    block_from = [n for n in wing[0]['from'] if not (a.run >= 3 and n == 'XComLevelActor_4')]
    objects.append({'type': 'copy', 'from': block_from, 'pivot': wing[0]['pivot'], 'location': C, 'yaw': 90,
                    'building': wing[0]['building'],
                    'extra': ['bLogTiles=False', 'bProbeIndoor=True', 'bCopyDoors=True', 'LateRebuild=4.0', 'LadderFootRebuild=6.0'],
                    'note': 'The step 3b block (the bar\'s west block), turned 90 degrees as the L layout\'s wing, its doors copied (bCopyDoors).'})
    assert block[1]['yaw'] == 270 and block[1]['pivot'] == [-1056, 672, 16]
    objects.append({'type': 'copy', 'from': block[1]['from'] + ['XComInteractiveLevelActor_4'], 'pivot': block[1]['pivot'],
                    'location': C, 'yaw': 270, 'inBuilding': bi, 'extra': ['bLogTiles=False', 'bCopyDoors=True'],
                    'note': 'The closing copy of EXP-07 step 3b (end wall, its parapet, back return and door frame on the side the block is open), and the door for that frame (XComInteractiveLevelActor_4 goes with XComDestructibleActor_31).'})
    for k in (2, 3, 4, 5, 6, 7, 8, 20):         # the wing's furniture and its wood floor, moved with the block
        o = dict(wing[k]); o['location'] = shifted(wing[k]); o['inBuilding'] = bi
        objects.append(o)
    wl = wing[24]
    assert wl['type'] == 'ladder'
    objects.append({'type': 'ladder', 'location': shifted(wl), 'yaw': wl['yaw'], 'hidden': False,
                    'note': 'The ladder on the block\'s north wall, outside, on the north sidewalk: as in the L layout\'s wing (F-39).'})

    if a.run >= 3:
        # The second floor: the wing's wood floor (URB_Bar_384CFloor, 13 x 13 tiles at scale 1; at its yaw of -90 the
        # copy's CopyScale X runs along world y) a storey up, twice, each piece over a rectangle of whole tiles.
        fl = wing[20]
        assert fl['from'] == ['XComLevelActor_302'] and fl['yaw'] == 0
        r = inv['XComLevelActor_302']
        (fx0, fx1), (fy0, fy1) = rng(r['box x']), rng(r['box y'])
        fw, fh = fx1 - fx0, fy1 - fy0                 # 1248 x 1248
        piv = fl['pivot']
        STOREY = 192
        # The pieces' tops (the mesh is z -2..2 about its pivot) at 209.5 and 210.5, ComKit's second-floor height (its
        # Core_384FloorB is at 208..210), so that the storey keeps ComKit's headroom under the roof slab (398).
        SLAB_Z = 207.5
        WELL = (20, 24)                               # the ladder well, the south-west room's south-west corner
        plan_props.append({'min': list(WELL), 'max': list(WELL)})
        slabs = [((21, 13), (31, 24), 0, 'east of the well: tiles x 21..31, y 13..24'),
                 ((20, 13), (31, 23), 1, 'north of the well: tiles x 20..31, y 13..23')]
        for (tx0, ty0), (tx1, ty1), up, where in slabs:
            x0, x1, y0, y1 = wx(tx0), wx(tx1 + 1), wy(ty0), wy(ty1 + 1)
            sx, sy = (x1 - x0) / fw, (y1 - y0) / fh
            objects.append({'type': 'copy', 'from': fl['from'], 'pivot': piv,
                            'location': [round(x0 + (piv[0] - fx0) * sx, 3), round(y0 + (piv[1] - fy0) * sy, 3),
                                         SLAB_Z + up],
                            'yaw': 0, 'inBuilding': bi,
                            'extra': ['bLogTiles=False', 'CopyScale=(X=%g,Y=%g,Z=1.0)' % (round(sy, 6), round(sx, 6)), 'BuildingFloor=1'],
                            'note': 'The second floor, %s, on the building\'s second floor in its floor caches (BuildingFloor 1).' % where})
        # The ladder in the well: its foot tile the well, its top point 76 units on, past the floor's edge, on the
        # floor's tile (21, 24), at z 16 + 0.42 * 477 + 8 = 224 (level 3; the floor's top is at 211).
        objects.append({'type': 'ladder', 'location': [wx(WELL[0] + 0.5), wy(WELL[1] + 0.5), 16], 'yaw': 0, 'hidden': False,
                        'loops': 0, 'extra': ['DrawScale3D=(X=1.0,Y=1.0,Z=0.42)'],
                        'note': 'The inside ladder, in the well (tile x 20, y 24) against the second floor\'s edge: URB_Bar\'s ladder squashed to 200 units.'})
        # Cover upstairs: a box stack in the east room and one in the north-west room, a storey up.
        BOXES = 'XComDestructibleActor_12'
        r = inv[BOXES]
        (px0, px1), (py0, py1) = rng(r['box x']), rng(r['box y'])
        p = loc(BOXES)
        for tx, ty in ((28, 17), (23, 16)):
            cx, cy = wx(tx + 0.5), wy(ty + 0.5)
            objects.append({'type': 'copy', 'from': [BOXES], 'pivot': p,
                            'location': [round(p[0] + cx - (px0 + px1) / 2, 1), round(p[1] + cy - (py0 + py1) / 2, 1), p[2] + SLAB_Z + 3],
                            'inBuilding': bi, 'extra': ['bLogTiles=False', 'BuildingFloor=1'],
                            'note': 'Cover upstairs: a box stack on tile x %d, y %d of the second floor.' % (tx, ty)})

    # The sidewalk ring. At yaw 0 a piece runs +x from its pivot and 4 tiles -y, curb on its +y edge; a corner piece
    # has curbs on its -x and +y edges. The copier's yaw is the wanted yaw less the source's.
    SIDE8, SIDE2, CORNER = 'XComLevelActor_47', 'XComLevelActor_111', 'XComLevelActor_116'   # StrA8x4, StrA2x4, CrnA4x4
    bx0, by0, bx1, by1 = C[0] - 576, C[1] - 576, C[0] + 576, C[1] + 576    # the block: x -864..288, y -672..480
    W = 4 * T
    ring = [  # (source, wanted yaw, pivot x, y)
        (SIDE8, 0, bx0, by1 + W), (SIDE2, 0, bx0 + 8 * T, by1 + W), (SIDE2, 0, bx0 + 10 * T, by1 + W),          # south
        (SIDE8, 180, bx1, by0 - W), (SIDE2, 180, bx1 - 8 * T, by0 - W), (SIDE2, 180, bx1 - 10 * T, by0 - W),    # north
        (SIDE8, 270, bx1 + W, by1), (SIDE2, 270, bx1 + W, by1 - 8 * T), (SIDE2, 270, bx1 + W, by1 - 10 * T),    # east
        (SIDE8, 90, bx0 - W, by0), (SIDE2, 90, bx0 - W, by0 + 8 * T), (SIDE2, 90, bx0 - W, by0 + 10 * T),       # west
        (CORNER, 0, bx0 - W, by1 + W), (CORNER, 90, bx0 - W, by0 - W), (CORNER, 180, bx1 + W, by0 - W), (CORNER, 270, bx1 + W, by1 + W)]
    for s, yaw, x, y in ring:
        r = inv[s]
        objects.append({'type': 'copy', 'from': [s], 'pivot': loc(s), 'location': [x, y, float(r['z'])],
                        'yaw': (yaw - int(float(r['yaw']))) % 360, 'extra': ['bLogTiles=False']})

    # Cover, each prop centred on a footprint of whole tiles: (source, footprint tile min, footprint size).
    DUMP, BOXES, CAN, BAG, FENCE = 'XComDestructibleActor_2', 'XComDestructibleActor_12', 'XComDestructibleActor_29', 'XComDestructibleActor_297', 'XComDestructibleActor_18'
    cover = [(DUMP, (9, 13), (2, 1)), (BOXES, (11, 15), (1, 1)), (CAN, (8, 15), (1, 1)),          # west of the ring
             (DUMP, (41, 15), (2, 1)), (FENCE, (40, 17), (1, 1)), (BOXES, (43, 16), (1, 1)),      # east
             (DUMP, (24, 32), (2, 1)), (BOXES, (27, 33), (1, 1)), (BAG, (22, 31), (1, 1))]        # south
    for s, (tx, ty), (w, h) in cover:
        r = inv[s]
        (px0, px1), (py0, py1) = rng(r['box x']), rng(r['box y'])
        p = loc(s)
        cx, cy = wx(tx + w / 2), wy(ty + h / 2)
        objects.append({'type': 'copy', 'from': [s], 'pivot': p,
                        'location': [round(p[0] + cx - (px0 + px1) / 2, 1), round(p[1] + cy - (py0 + py1) / 2, 1), p[2]],
                        'extra': ['bLogTiles=False'],
                        'note': 'Cover: %s on tiles x %d..%d, y %d..%d.' % (r['mesh'].split('.')[-1], tx, tx + w - 1, ty, ty + h - 1)})
        plan_props.append({'min': [tx, ty], 'max': [tx + w - 1, ty + h - 1]})

    # Three cars, snapped to the tile grid by the spawner (F-41), as the L layout's.
    compact = {k: wing[23][k] for k in ('archetype', 'partner', 'partnerOffset')}
    suv = {k: wing[22][k] for k in ('archetype', 'partner', 'partnerOffset')}
    cars = [(suv, 90, (wx(40), wy(23)), [0.02, 0.25, 0.08], [256, 192, 160], ([38, 22], [4, 2]), 'An SUV east of the ring, along x.'),
            (compact, -90, (wx(12.5), wy(25)), [0.85, 0.55, 0.02], [256, 192, 160], ([11, 24], [3, 2]), 'A compact between the hole and the ring, along x.'),
            (compact, 0, (wx(22.5), wy(5.5)), [0.9, 0.9, 0.9], [192, 256, 160], ([22, 4], [2, 3]), 'A compact north of the ring, along y, between the north landing zones\' spawn points.')]
    for kind, yaw, (x, y), tint, ext, rect, note in cars:
        o = {'type': 'spawn', 'location': [x, y, 0], 'yaw': yaw, 'tint': tint, 'rebuildExtent': ext, 'extra': ['bSnapToTiles=True'], 'note': note}
        o.update(kind)
        objects.append(o)
        plan_cars.append({'tile': rect[0], 'size': rect[1]})

objects.append({'type': 'sun', 'sun': 1.2, 'sky': 0.5, 'yaw': 138, 'pitch': 50,
                'note': 'The photo object\'s light (EXP-07 run 35), on its own: the map\'s only light.'})
cz, hz = (-64 + 832) / 2, (832 + 64) / 2
objects.append({'type': 'hide', 'location': [(X0 + X1) / 2, (Y0 + Y1) / 2, cz], 'half': [(X1 - X0) / 2, (Y1 - Y0) / 2, hz],
                'keep': KEEP, 'alsoHide': sorted(also, key=by_name),
                'extra': ['KeepGroundHeight=-1', 'bHideLights=True', 'bHideVolumes=True', 'bHideFragments=True',
                          'ProbeStart=(X=-1056,Y=-120,Z=64)', 'ProbeEnd=(X=-1056,Y=400,Z=64)']})
if a.photo:
    objects.append({'type': 'photo', 'sun': 0, 'sky': 0, 'note': 'The overview view for a shot; the sun object lights the map.'})

what = ('run 1, the blank grid' if a.run == 1 else
        'run 2, a small layout: the step 3b block with a sidewalk ring, a 4 x 4 hole in the ground (tiles x 3..6, y 27..30), '
        'three clusters of cover and three cars' if a.run == 2 else
        'run 3, run 2\'s layout without the hole, the block with two storeys: a wood second floor at z 210 (no ceiling beams) with a ladder '
        'well in the south-west corner, a short ladder up, two box stacks upstairs')
spec = {
    'note': ('EXP-08 %s (research/experiments/EXP-08-blank-map.md), written by tools/patch/gen_exp08.py: everything URB_Bar '
             'places in its play area is hidden, ground and lights included, and copies of its asphalt plane %s lay new '
             'ground on the tile grid, x %g..%g, y %g..%g. A sun object is the only light. The patch starts from an empty '
             'map (base ""), not patch_bar, whose cover fixes belong to the old layout, and the map ships as URB_BarBlank '
             '(map.shipAs), beside the untouched URB_Bar (F-42). %d actors outside the play area that reach into it are '
             'hidden by name; the pieces of the landing prefabs stay (F-45). Lit by the sun, the map is a day map '
             '(map.timeOfDay).' % (what, GROUND, xs[0] - step / 2, xs[-1] + step / 2, ys[0] - step / 2, ys[-1] + step / 2, len(also))),
    'name': 'patch_exp08blank',
    'base': '',
    'map': {'name': 'URB_Bar', 'origin': [OX, OY], 'tileSize': T, 'shipAs': 'URB_BarBlank',
            'displayName': 'URB_BarBlank (EXP-08 blank map) |0',
            # Lit by the sun object, so a day map (URB_Bar's record says night; LWR counts night missions).
            'timeOfDay': 'Day'},
    'objects': objects,
}
with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(spec, f, indent=2)
    f.write('\n')
print('wrote %s: %s; %d objects (%d ground)%s' % (a.out, what, len(objects), n_ground, ', the photo view' if a.photo else ''))

if a.run >= 2:
    t = lambda v, o: int(round((v - o) / T))
    plan = {
        'name': 'blank map, run %d layout' % a.run,
        'origin': [OX, OY], 'tiles': [NX, NY], 'landingZones': LZ, 'blank': True,
        'ground': [{'min': [0, 0], 'max': [NX - 1, NY - 1]}],
        'holes': [{'min': [HOLE[0], HOLE[1]], 'max': [HOLE[2], HOLE[3]]}] if a.run == 2 else [],
        'sidewalks': [{'min': [t(bx0 - W, OX), t(by0 - W, OY)], 'max': [t(bx1 + W, OX) - 1, t(by0, OY) - 1]},
                      {'min': [t(bx0 - W, OX), t(by1, OY)], 'max': [t(bx1 + W, OX) - 1, t(by1 + W, OY) - 1]},
                      {'min': [t(bx0 - W, OX), t(by0, OY)], 'max': [t(bx0, OX) - 1, t(by1, OY) - 1]},
                      {'min': [t(bx1, OX), t(by0, OY)], 'max': [t(bx1 + W, OX) - 1, t(by1, OY) - 1]}],
        'building': [{'min': [t(bx0, OX), t(by0, OY)], 'max': [t(bx1, OX) - 1, t(by1, OY) - 1]}],
        'props': plan_props, 'cars': plan_cars,
        'labels': [{'tile': [22, 18], 'text': 'step 3b block' if a.run == 2 else 'block, 2 storeys'}]
                  + ([{'tile': [1, 34], 'text': 'hole 4x4'}] if a.run == 2 else [{'tile': [15, 26.6], 'text': 'ladder (20,24)'}])
                  + [{'tile': [5, 11], 'text': 'cover'}, {'tile': [41, 12], 'text': 'cover'}, {'tile': [22, 35], 'text': 'cover'}],
    }
    with open(a.plan, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(plan, f, indent=1)
        f.write('\n')
    print('wrote the plan %s' % a.plan)
