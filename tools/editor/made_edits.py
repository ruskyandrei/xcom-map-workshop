"""Walls, floors, roofs and ground shapes made from numbers (the custom geometry plan and its editing plan), and the
blasts that break a fracturing piece, for the compiler.

A record's `generated` is checked here (generated_valid, with ground_valid and slab_valid): a fracturing wall, a floor
or roof slab or a ground shape made from numbers on a copy of its template, or the template's own mesh relit as a made
wall is; so are an override's or a copy's `blasts` (blasts_valid). The compiler's add makes each copy: a made wall or
floor past the sizes the game is known to take is cut into pieces (made_pieces), each added as a copy of its own
(split_made). add records the made copies here: `walls`, each made wall's copy and where (its template's parts in
`parts`), `slabs`, each made floor's or roof's, and `wholes`, each made wall as drawn; `broken_wholes` says how many
blasts a cut piece's whole was given. Once every copy is made, the compiler's run asks for the checks: made walls that
meet (join_made_walls, wall_joins), that stand on another (made_walls_stacked) and their gaps (made_wall_openings,
opening_play); made floors and roofs in a building but in none of its floors (made_slabs_in_floors), and over the
map's cursor volumes or too near its floor (made_slab_cursors). The cursor's floors over the made slabs are the
floor family's (floor_edits.py: with_made_slabs reads `slabs`).

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A MadeEdits works for one
Compiler: it reads the scene, the meshes, the copies and hides made so far, the buildings and the floor tiles from it,
asks it for a piece's boxes (boxes) and to add each piece of a cut wall or floor (add), and says what it finds
through its error, warn and note, so the report and the pieces left out are the compiler's as before.

Its own tables and helpers (GENERATED_VERSIONS, FRAC_WALL_LOOKS, WALL_SWEEPS, wall_joins, opening_play and the others)
are here, and the compiler names again those that others read through it (compiler.FRAC_WALL_MIN_LENGTH,
compiler.wall_joins, ...). What the family shares with the compiler (TILE, HEADROOM, MADE_KINDS, donor_shape,
wall_heights, made_wall_along, short, tidy and the others it imports) it takes from compiler_tables, so it never
imports the compiler.
"""
import json
import math
from itertools import product
from pathlib import Path

# (compiler_tables puts tools/viewer on the path, for export_math, and tools/bake, for the Build's looks, ground
# shapes, blasts, made floors' cursors and cuts, and a made wall's storeys)
from compiler_tables import (FRAC_SLAB_LOOKS, GROUND_LOOKS, HEADROOM, MADE_KINDS, TILE, donor_shape, keyable,
                             made_wall_along, short, tidy, union, wall_heights, world_box)
from export_math import transform
import looks
import ground as ground_shapes
import made_blasts
import made_cursors
import made_split
import frac_wall     # (loaded already: ground's import loads it)

# A fracturing wall made from numbers (custom geometry plan, section 0): its numbers are its tile edges, it is at
# least this long (tools/bake/frac_walls.py MIN_LENGTH; test_frac_walls checks they agree), and its solid stops
# FRAC_WALL_END_INSET (compiler_tables) short of each end
FRAC_WALL_MIN_LENGTH = 40.0
# the looks a made wall can be in (custom geometry plan, M4 item 1: tools/bake/wall_looks.json, frac_wall.LOOKS); the
# first is the one a wall naming none is in
FRAC_WALL_LOOKS = [look['id'] for look in json.loads(
    (Path(__file__).resolve().parents[1] / 'bake' / 'wall_looks.json').read_text(encoding='utf-8'))['looks']]
# a floor or roof slab made from numbers (custom geometry plan, M5: tools/bake/frac_slab.py, slab_looks.json): a slab
# is whole tiles, 1 to FRAC_SLAB_MAX_TILES each way, its holes whole tiles inside it; its looks are FRAC_SLAB_LOOKS
# (compiler_tables), and the look of one that names none is the compiler's FRAC_SLAB_DEFAULT_LOOK
FRAC_SLAB_MAX_TILES = 16
# a made wall or floor of any size (custom geometry editing plan, B4, D-3, 19 November 2026): the Build cuts it into
# pieces of at most FRAC_SLAB_MAX_TILES tiles and its look's storeys (made_split); these bound the numbers only
MADE_MAX_TILES = 128
MADE_MAX_STOREYS = made_split.MAX_STOREYS
# ground shapes made from numbers (M6: tools/bake/ground.py): a patch, block or ramp of whole tiles (1 to 16 each way), a
# block's or ramp's height 1 to 384 (the plain pieces one copies, GROUND_CLASSES, and its slopes are the compiler's)
GROUND_SHAPES = ('patch', 'block', 'ramp', 'rock')
GROUND_ROCK_SEEDS = 2 ** 31     # a rock's seed is 0 to this less one (ground.py ROCK_SEEDS)
GROUND_MAX_HEIGHT = 384.0
GROUND_MAX_TILES = 64       # (one plain piece, not cut: B4; ground.MAX_TILES)


# the generated request versions each kind takes (tools/bake/frac_walls.py VERSIONS, OTHER_VERSIONS); a look named by
# its donor (custom geometry plan, M4: {mesh, measure}, looks.py) comes with a wall's version 3 and a slab's or ground
# shape's version 2, which always name one
GENERATED_VERSIONS = {'fracWall': (1, 2, 3, 4, 5), 'fracSlab': (1, 2, 3, 4), 'ground': (1, 2, 3, 4, 5), 'relit': (1,)}
DONOR_LOOK_SINCE = {'fracWall': 3, 'fracSlab': 2, 'ground': 2}
# a made piece with no look chosen (custom geometry editing plan, B2, 19 November 2026): drawn plain in the editor, its
# numbers its kind's default look's as version 1 has them; the Build makes it in that look (D-1) and warns made-no-look,
# and the copy goes on as version 1
PLAIN_VERSION = {'fracWall': 4, 'fracSlab': 3, 'ground': 3}
# a rock whose corners were moved in the editor (look picker and rock points plan, R1): its numbers carry `points`, and
# its request is this version whatever its look (a look id, one named by its donor, or none: plain), so an editor from
# before refuses it rather than make the seed's rock; it goes on to the Build as the version its look gives
POINTS_VERSION = {'ground': 4}
# the free form (custom geometry improvements plan, stage 2, its section 10.2): one request version of each kind whose
# numbers carry `free: 1` and say everything in fields: the look (absent the kind's default, a look id, or one named by
# its donor; `plain` beside it when none was chosen), the extents in the piece's own frame at any size (a wall's x0..x1,
# its faces y0..y1, its bottom and top z0..z1 and `tall`; a slab's footprint and plate; a ground shape's footprint and
# z0..z1), openings and holes anywhere inside, a rock's moved points, and the texture mapping (stage 4). It goes on to
# the Build as the Build's free version of its kind (tools/bake/frac_walls.py), its numbers as they are, less `plain`.
FREE_VERSION = {'fracWall': 5, 'fracSlab': 4, 'ground': 5}
BUILD_FREE_VERSION = {'fracWall': 4, 'fracSlab': 3, 'ground': 3}
WALL_TALL = ('repeat', 'stretch')
# a texture mapping's surfaces and modes (the plan's section 5; built in its stage 4)
MAPPING_ROLES = ('faces', 'top', 'underside', 'sides')
MAPPING_MODES = ('size', 'fit', 'count')


def wall_look_storeys(wall):
    """(its look's own storeys, whether a wall one storey tall can be made in it) of a made wall (frac_wall.storeys_of):
    the Bar's inside wall's, (2, yes), for a look id; for a donor look no catalogue holds, its storeys as asked, uncut
    (the Build measures it)."""
    look = wall.get('look')
    if not isinstance(look, dict):
        return 2, True
    try:
        resolved = looks.resolve('wall', look)
    except looks.LookError:
        return int(wall.get('storeys') or 2), False
    own = frac_wall.storeys_of(frac_wall.look_of(dict(wall, look=resolved)))
    return max(own), max(own) > 1 and 1 in own


def mapping_valid(mapping, num):
    """Whether a free-form piece's texture mapping is well formed: {surfaces: {role: {mode, u, v, turn, flipU, flipV,
    offsetU, offsetV, world}}}, each surface's fields optional but its mode, u and v (positive) and turn, offsets
    finite."""
    if not isinstance(mapping, dict) or set(mapping) - {'surfaces'} or not isinstance(mapping.get('surfaces'), dict):
        return False
    for role, s in mapping['surfaces'].items():
        if role not in MAPPING_ROLES or not isinstance(s, dict) or s.get('mode') not in MAPPING_MODES:
            return False
        if set(s) - {'mode', 'modeV', 'u', 'v', 'turn', 'flipU', 'flipV', 'offsetU', 'offsetV', 'world'} or s.get('modeV', s['mode']) not in MAPPING_MODES:
            return False
        if not (num(s.get('u')) and num(s.get('v')) and s['u'] > 0 and s['v'] > 0):
            return False
        if not all(num(s.get(k, 0)) for k in ('turn', 'offsetU', 'offsetV')):
            return False
        if not all(isinstance(s.get(k, False), bool) for k in ('flipU', 'flipV', 'world')):
            return False
    return True


def free_valid(kind, n, num):
    """Whether a free-form piece's numbers (FREE_VERSION) are well formed: `free` 1, finite extents with some size each
    way, openings or holes inside, a whole seed, a look that is absent, a look id of its kind or one named by its donor,
    `plain` a boolean, a mapping of mapping_valid's. The generators check what the geometry can hold (the Build's
    check)."""
    if not isinstance(n, dict) or n.get('free') != 1 or 'whole' in n or 'ends' in n or 'storeys' in n or 'height' in n:
        return False
    keys = ('x0', 'x1', 'y0', 'y1', 'z0', 'z1')
    if not all(num(n.get(k)) for k in keys) or not (n['x0'] < n['x1'] and n['y0'] < n['y1'] and n['z0'] < n['z1']):
        return False
    if not isinstance(n.get('plain', False), bool) or ('mapping' in n and not mapping_valid(n['mapping'], num)):
        return False
    seed = n.get('seed', 1)
    if not isinstance(seed, int) or isinstance(seed, bool):
        return False
    ids = {'fracWall': FRAC_WALL_LOOKS, 'fracSlab': FRAC_SLAB_LOOKS, 'ground': GROUND_LOOKS}[kind]
    look = n.get('look')
    if look is not None and not (isinstance(look, str) and look in ids):
        try:
            looks.check_look(looks.REQUESTS[kind][0], look)
        except looks.LookError:
            return False
    if kind == 'fracWall':
        return n.get('tall', 'repeat') in WALL_TALL and isinstance(n.get('openings') or [], list) and all(
            isinstance(o, dict) and all(num(o.get(k)) for k in ('x0', 'x1', 'z0', 'z1'))
            and n['x0'] <= o['x0'] < o['x1'] <= n['x1'] and o['z0'] < o['z1'] for o in n.get('openings') or [])
    if kind == 'fracSlab':
        return isinstance(n.get('holes') or [], list) and all(
            isinstance(h, dict) and all(num(h.get(k)) for k in ('x0', 'x1', 'y0', 'y1'))
            and n['x0'] <= h['x0'] < h['x1'] <= n['x1'] and n['y0'] <= h['y0'] < h['y1'] <= n['y1'] for h in n.get('holes') or [])
    if n.get('shape') not in GROUND_SHAPES or ('points' in n and n['shape'] != 'rock'):
        return False
    if n['shape'] == 'rock' and not (isinstance(n.get('seed'), int) and not isinstance(n.get('seed'), bool)
                                     and 0 <= n['seed'] < GROUND_ROCK_SEEDS):
        return False
    points = n.get('points')
    return points is None or (isinstance(points, list) and all(
        isinstance(p, list) and len(p) == 3 and all(num(v) for v in p)
        and n['x0'] - 1e-6 <= p[0] <= n['x1'] + 1e-6 and n['y0'] - 1e-6 <= p[1] <= n['y1'] + 1e-6 for p in points))


def look_valid(kind, look, version, since, ids):
    """Whether a made piece's look fits its request version: named by its donor from version `since` on (always), a
    look id of `ids` (or none) before it."""
    if version >= since:
        try:
            looks.check_look(looks.REQUESTS[kind][0], look)
            return True
        except looks.LookError:
            return False
    return look is None or (isinstance(look, str) and look in ids)


# What the game does at a made wall's opening (custom geometry plan, M1 item 4; tools/viewer/web/walls.js is the twin):
# its sweeps over a tile's floor along the line between two tiles' centres (research/native/cover-build.md,
# line-of-sight.md): cover 44 to 60, high or low 88 to 104, walking 64 (half a unit thick), sight from the eye tile 96
# over the floor's level. An opening counts at a tile only where it holds the tile's centre along the wall. Heights
# are over the floor the wall stands on (its numbers' z 0); a doorway reaches the wall's bottom, -16.
WALL_SWEEPS = dict(cover=(44.0, 60.0), high=(88.0, 104.0), walk=64.0, sight=96.0, half=0.5)


def grid_crossings(location, rotation, wall, origin):
    """Where the game's lines between tiles' centres cross a made wall (the improvements plan, 4.6; walls.js
    gridCrossings is the twin): the places along it, in its frame, where it crosses a line x = origin x + 96 (i + 0.5)
    or y = origin y + 96 (j + 0.5) of the map's tile grid (its corner `origin`), between its ends, sorted. The rounded
    rotator's yaw, as the package holds it."""
    yaw = round(rotation[1]) * 2 * math.pi / 65536
    d = (math.cos(yaw), math.sin(yaw))
    x0, x1 = float(wall['x0']), float(wall['x1'])
    out = []
    for k in (0, 1):
        if abs(d[k]) < 1e-9:
            continue
        a, b = sorted((location[k] + d[k] * x0, location[k] + d[k] * x1))
        first = math.ceil((a - origin[k]) / 96.0 - 0.5 - 1e-9)
        last = math.floor((b - origin[k]) / 96.0 - 0.5 + 1e-9)
        for i in range(first, last + 1):
            c = origin[k] + 96.0 * (i + 0.5)
            out.append(round((c - location[k]) / d[k], 6))
    return sorted(x for x in out if x0 - 1e-6 <= x <= x1 + 1e-6)


def opening_play(wall, o, centres=None):
    """What the game does at an opening of a made wall (walls.js openingPlay is the twin): dict(tiles (how many tiles'
    centre lines pass through it), walk, climb (units vault through it: low cover under it, which the game's tile
    rebuild gives its ClimbOver, F-126), sight, cover: 'none', 'low', 'high' or 'whole' (the wall's own cover at those
    tiles)). `centres`: where those lines cross the wall in its frame (grid_crossings: a free-form wall's, on the map's
    grid); left out, a tile's middle every 96 from its start, as an older wall stands on the tile lines."""
    length = float(wall['x1']) - float(wall['x0'])
    if centres is None:
        centres = [float(wall['x0']) + 96.0 * (k + 0.5) for k in range(int(round(length / 96.0)))]
    tiles = sum(1 for c in centres if o['x0'] + 1 < c < o['x1'] - 1)
    if not tiles:
        return dict(tiles=0, walk=False, climb=False, sight=False, cover='whole')
    s = WALL_SWEEPS

    def spans(a, b):
        return o['z0'] < a and o['z1'] > b
    cover_hit, high_hit = not spans(*s['cover']), not spans(*s['high'])
    walk = spans(s['walk'] - s['half'], s['walk'] + s['half'])
    cover = 'none' if not cover_hit else 'high' if high_hit else 'low'
    return dict(tiles=tiles, walk=walk, climb=not walk and cover == 'low',
                sight=spans(s['sight'] - s['half'], s['sight'] + s['half']), cover=cover)


# How made walls meet (custom geometry plan, M3 item 2; walls.js wallJoins is the twin): an end's style for its solid
# (tools/bake/frac_wall.py END_INSETS) and how it meets. The game's walls (research/evidence/wall-joints.py): an
# inside wall's end on another wall's line stops square 8 short of it (a T's stem: 'free', as a free end); at an L one
# runs through to the other's far face ('through') and the other butts on its face ('free'); end to end both reach the
# line ('line').
WALL_JOIN_REACH = 1.0           # an end within this of a point or a line meets it
WALL_JOIN_FLOOR = 32.0          # walls meet when their heights overlap by more than this (a storey apart they don't)


def wall_joins(walls):
    """Where made walls meet: `walls` [dict(key, location, rotation, wall)] (their poses and numbers) gives {key:
    dict(ends: [the x0 end's style, the x1 end's] ('free', 'through' or 'line'), joins: [dict(end (0 or 1), how
    ('corner' (runs through), 'butt', 'line', 'stem'), other (the other wall's key))])}. An end meets the walls whose
    ends lie within WALL_JOIN_REACH of it, or whose centre line passes through it between their ends, on the same floor
    (heights overlapping by more than WALL_JOIN_FLOOR). At a point: two ends leaving it in opposite directions are end
    to end ('line'; with a second such pair across them, that pair butts); a wall passing through makes every end there
    a stem; two ends at right angles make an L, where the taller wall runs through, then the longer, then the one along
    game x, and the other butts. Anything else (walls overlapping) stays free. Only level walls turned by yaw meet."""
    tau = 2 * math.pi
    info = []
    for w in walls:
        loc, rot, wall = w['location'], w['rotation'], w['wall']
        if round(rot[0]) % 65536 or round(rot[2]) % 65536:
            continue
        yaw = rot[1] * tau / 65536
        d = (math.cos(yaw), math.sin(yaw))
        x0, x1 = float(wall['x0']), float(wall['x1'])
        bottom, top, _, _ = wall_heights(wall)
        info.append(dict(key=w['key'], d=d, x0=x0, x1=x1,
                         p=[(loc[0] + d[0] * x, loc[1] + d[1] * x) for x in (x0, x1)],
                         z=(loc[2] + bottom, loc[2] + top), height=top, length=x1 - x0,
                         loc=(loc[0], loc[1])))
    out = {w['key']: dict(ends=['free', 'free'], joins=[]) for w in walls}

    def floor(a, b):
        return min(a['z'][1], b['z'][1]) - max(a['z'][0], b['z'][0]) > WALL_JOIN_FLOOR

    def through(pt, b):
        vx, vy = pt[0] - b['loc'][0], pt[1] - b['loc'][1]
        t = vx * b['d'][0] + vy * b['d'][1]
        return abs(b['d'][0] * vy - b['d'][1] * vx) <= WALL_JOIN_REACH and b['x0'] + WALL_JOIN_REACH < t < b['x1'] - WALL_JOIN_REACH

    def leaving(w, m):
        # the way the wall leaves the point at its end m, as a quarter: 0 +x, 1 +y, 2 -x, 3 -y
        dx, dy = w['d'] if m == 0 else (-w['d'][0], -w['d'][1])
        return (0 if dx > 0.5 else 2) if abs(dx) > abs(dy) else (1 if dy > 0.5 else 3)

    done = set()
    for i, a in enumerate(info):
        for k in (0, 1):
            if (i, k) in done:
                continue
            pt = a['p'][k]
            ends = [(j, m) for j, b in enumerate(info) for m in (0, 1)
                    if (j == i or floor(a, b)) and math.dist(b['p'][m], pt) <= WALL_JOIN_REACH]
            done.update(ends)
            passes = [j for j, b in enumerate(info) if j != i and floor(a, b) and through(pt, b)]
            if len(ends) < 2 and not passes:
                continue
            style = {}
            if passes:
                for j, m in ends:
                    style[j, m] = ('free', 'stem', info[passes[0]]['key'])
            else:
                by = {}
                for j, m in ends:
                    by.setdefault(leaving(info[j], m), []).append((j, m))
                if any(len(v) > 1 for v in by.values()):
                    continue                    # walls overlapping: left free
                pairs = [q for q in (0, 1) if q in by and q + 2 in by]
                if pairs:
                    line = pairs[0]             # (two pairs: the one along x is end to end, the other butts on it)
                    (ja, ma), (jb, mb) = by[line][0], by[line + 2][0]
                    style[ja, ma] = ('line', 'line', info[jb]['key'])
                    style[jb, mb] = ('line', 'line', info[ja]['key'])
                    for q in ((1, 3) if line == 0 else (0, 2)):
                        if q in by:
                            j, m = by[q][0]
                            style[j, m] = ('free', 'stem', info[ja]['key'])
                elif len(ends) == 2:
                    (ja, ma), (jb, mb) = ends
                    A, B = info[ja], info[jb]
                    rank = lambda w: (w['height'], w['length'], abs(w['d'][0]) > abs(w['d'][1]))  # noqa: E731
                    if rank(A) < rank(B):
                        (ja, ma), (jb, mb), A, B = (jb, mb), (ja, ma), B, A
                    style[ja, ma] = ('through', 'corner', B['key'])
                    style[jb, mb] = ('free', 'butt', A['key'])
            for (j, m), (shape, how, other) in style.items():
                rec = out[info[j]['key']]
                rec['ends'][m] = shape
                rec['joins'].append(dict(end=m, how=how, other=other))
    return out


# Free-form walls meeting at any angle (the custom geometry improvements plan, 4.7, decisions D7 and D10; walls.js
# freeWallJoins is the twin, and free_join_cases.json the cases both pass): two ends within WALL_JOIN_REACH of each
# other are each cut on the one upright plane through the corner, the line from where their inner faces cross to where
# their outer faces cross, right angles too; two ends in line meet end to end ('line'); an end on another wall's line
# between its ends stops against that wall's near face, leaning along it (a stem), as ends do against a pair in line.
# Under MITRE_LEAST degrees between the walls, or three or more ends at a point with no two in line, ends meet square
# (left free). An end is a style ('free', 'line') or {inset (how far in from the wall's own end its solid stops along
# its line), lean (how far its plane leans along the wall for each unit across it)}, the frac_wall free form's. The
# angle is the rounded rotator's, as the package holds it, on both sides.
MITRE_LEAST = 30.0
WALL_IN_LINE = math.cos(math.radians(179.0))     # two ends leaving a point this nearly opposite are in line


def _free_frame(w):
    """A free-form wall's frame in plan: (its origin, its direction, its normal), the yaw a whole rotator."""
    yaw = round(w['rotation'][1]) * 2 * math.pi / 65536
    d = (math.cos(yaw), math.sin(yaw))
    return (float(w['location'][0]), float(w['location'][1])), d, (-d[1], d[0])


def _meet(p, u, q, v):
    """Where the lines p + s u and q + t v cross (None when they run alongside)."""
    det = u[0] * -v[1] - u[1] * -v[0]
    if abs(det) < 1e-9:
        return None
    rx, ry = q[0] - p[0], q[1] - p[1]
    s = (rx * -v[1] - ry * -v[0]) / det
    return (p[0] + s * u[0], p[1] + s * u[1])


def _end_on(a, k, point_line, least=MITRE_LEAST):
    """Wall a's end k ({inset, lean}) on the plane through the line `point_line` ((point, direction) in plan); 'free'
    where the plane meets the wall at under `least` degrees (a stem's least is the walls' own, a mitre's half the
    corner's)."""
    (o, d, n), (q, v) = a['frame'], point_line
    cx = _meet(o, d, q, v)
    if cx is None:
        return 'free'
    across = v[0] * n[0] + v[1] * n[1]
    if abs(across) < math.sin(math.radians(least)) - 1e-9:
        return 'free'
    x_c = (cx[0] - o[0]) * d[0] + (cx[1] - o[1]) * d[1]
    lean = (v[0] * d[0] + v[1] * d[1]) / across
    inset = a['x1'] - x_c if k == 1 else x_c - a['x0']
    return dict(inset=tidy(inset, 6), lean=tidy(lean, 6))


def _face(w, y):
    """A wall's face at y across, as a line in plan: (a point on it, its direction)."""
    o, d, n = w['frame']
    return (o[0] + y * n[0], o[1] + y * n[1]), d


def _away(w, k):
    """The way wall w runs from its end k, into the wall."""
    d = w['frame'][1]
    return d if k == 0 else (-d[0], -d[1])


def free_wall_joins(walls):
    """Where free-form made walls meet: `walls` [dict(key, location, rotation, wall)] gives {key: dict(ends: [the x0
    end, the x1 end] ('free', 'line' or {inset, lean}), joins: [dict(end, how ('mitre', 'line', 'stem'), other)])}.
    Only level walls turned by yaw meet (as wall_joins)."""
    info = []
    for w in walls:
        rot, n = w['rotation'], w['wall']
        if round(rot[0]) % 65536 or round(rot[2]) % 65536:
            continue
        frame = _free_frame(w)
        o, d, _ = frame
        x0, x1 = float(n['x0']), float(n['x1'])
        info.append(dict(key=w['key'], frame=frame, x0=x0, x1=x1, y0=float(n['y0']), y1=float(n['y1']),
                         p=[(o[0] + d[0] * x, o[1] + d[1] * x) for x in (x0, x1)],
                         z=(float(w['location'][2]) + float(n['z0']), float(w['location'][2]) + float(n['z1']))))
    out = {w['key']: dict(ends=['free', 'free'], joins=[]) for w in walls}

    def floor(a, b):
        return min(a['z'][1], b['z'][1]) - max(a['z'][0], b['z'][0]) > WALL_JOIN_FLOOR

    def passes(pt, b):
        o, d, _ = b['frame']
        vx, vy = pt[0] - o[0], pt[1] - o[1]
        t = vx * d[0] + vy * d[1]
        return abs(d[0] * vy - d[1] * vx) <= WALL_JOIN_REACH and b['x0'] + WALL_JOIN_REACH < t < b['x1'] - WALL_JOIN_REACH

    def near_face(c, a, k):
        """Wall c's face on the side wall a's end k runs into: as a line."""
        v, n = _away(a, k), c['frame'][2]
        return _face(c, c['y1'] if v[0] * n[0] + v[1] * n[1] > 0 else c['y0'])

    def put(j, m, end, how, other):
        rec = out[info[j]['key']]
        rec['ends'][m] = end
        rec['joins'].append(dict(end=m, how=how, other=info[other]['key']))

    done = set()
    for i, a in enumerate(info):
        for k in (0, 1):
            if (i, k) in done:
                continue
            pt = a['p'][k]
            ends = [(j, m) for j, b in enumerate(info) for m in (0, 1)
                    if (j == i or floor(a, b)) and math.dist(b['p'][m], pt) <= WALL_JOIN_REACH]
            done.update(ends)
            through = [j for j, b in enumerate(info) if j != i and floor(a, b) and passes(pt, b)]
            if through:
                for j, m in ends:
                    end = _end_on(info[j], m, near_face(info[through[0]], info[j], m))
                    if end != 'free':
                        put(j, m, end, 'stem', through[0])
                continue
            if len(ends) < 2:
                continue
            pairs = [(e, f) for x, e in enumerate(ends) for f in ends[x + 1:]
                     if sum(p * q for p, q in zip(_away(info[e[0]], e[1]), _away(info[f[0]], f[1]))) <= WALL_IN_LINE]
            if pairs:
                (ja, ma), (jb, mb) = pairs[0]
                put(ja, ma, 'line', 'line', jb)
                put(jb, mb, 'line', 'line', ja)
                for j, m in ends:
                    if (j, m) in pairs[0]:
                        continue
                    end = _end_on(info[j], m, near_face(info[ja], info[j], m))
                    if end != 'free':
                        put(j, m, end, 'stem', ja)
                continue
            if len(ends) != 2:
                continue                        # three or more ends, none in line: square, for now
            (ja, ma), (jb, mb) = ends
            A, B = info[ja], info[jb]
            u, v = _away(A, ma), _away(B, mb)
            angle = math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))))
            if angle < MITRE_LEAST or ja == jb:
                continue
            # the inner faces (each wall's face toward the other) cross at one point, the outer at another: the plane
            nA, nB = A['frame'][2], B['frame'][2]
            inA, outA = (A['y1'], A['y0']) if v[0] * nA[0] + v[1] * nA[1] > 0 else (A['y0'], A['y1'])
            inB, outB = (B['y1'], B['y0']) if u[0] * nB[0] + u[1] * nB[1] > 0 else (B['y0'], B['y1'])
            inner = _meet(*_face(A, inA), *_face(B, inB))
            outer = _meet(*_face(A, outA), *_face(B, outB))
            if inner is None or outer is None:
                continue
            plane = (inner, (outer[0] - inner[0], outer[1] - inner[1]))
            length = math.hypot(*plane[1])
            if length < 1e-9:
                continue
            plane = (inner, (plane[1][0] / length, plane[1][1] / length))
            put(ja, ma, _end_on(A, ma, plane, MITRE_LEAST / 2), 'mitre', jb)
            put(jb, mb, _end_on(B, mb, plane, MITRE_LEAST / 2), 'mitre', ja)
    return out


def made_wall_joins(walls):
    """Where made walls meet, old and free-form alike: the free-form walls' ends among themselves by free_wall_joins;
    every other end by wall_joins, today's rule (a corner with a wall of an older version keeps it)."""
    old = wall_joins(walls)
    free = free_wall_joins([w for w in walls if w['wall'].get('free') == 1])
    out = {}
    for w in walls:
        o = old[w['key']]
        f = free.get(w['key'])
        if not f:
            out[w['key']] = o
            continue
        ends, joins = list(f['ends']), list(f['joins'])
        for j in o['joins']:
            if any(x['end'] == j['end'] for x in f['joins']):
                continue
            # (an end the free rule left: joined to an older wall by today's rule, or nothing)
            other = next((x for x in walls if x['key'] == j['other']), None)
            if other is not None and other['wall'].get('free') != 1:
                ends[j['end']] = o['ends'][j['end']]
                joins.append(j)
        out[w['key']] = dict(ends=ends, joins=joins)
    return out


def opening_box(location, rotation, o, half=12.0):
    """The world box [x0, x1, y0, y1, z0, z1] of a made wall's opening, the wall standing at `location` turned by
    `rotation` (its numbers in its own frame: x along it, z over its floor)."""
    m = transform(location, rotation, [1, 1, 1])
    pts = [[sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)]
           for v in product((o['x0'], o['x1']), (-half, half), (o['z0'], o['z1']))]
    return [min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts),
            min(p[2] for p in pts), max(p[2] for p in pts)]


WALL_STACK_GAP = 24.0      # a made wall's bottom this near another's top stands on it (made_walls_stacked)


def overlaps_by(a, b, least):
    """Whether boxes a and b ([x0, x1, y0, y1, z0, z1]) overlap at all across and by more than `least` along x or y
    (whichever is longer in a) and up."""
    along = 0 if a[1] - a[0] >= a[3] - a[2] else 1
    over = [min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) for k in range(3)]
    return over[along] > least and over[2] > least and over[1 - along] > 0


class MadeEdits:
    def __init__(self, compiler):
        self.c = compiler
        # the made pieces' copies the compiler's add makes (custom geometry plan), with where, for the checks run asks
        # for once every copy is made; and the blasts of each cut piece's whole
        self.walls = []        # (copy, where) of each fracturing wall made from numbers (made_wall_openings)
        self.parts = {}        # a made wall's label: its template's parts (join_made_walls makes its box again)
        self.slabs = []        # (copy, where) of each floor or roof made from numbers (made_slabs_in_floors)
        self.wholes = []       # (copy, where) of each made wall as drawn: its copy, or its pieces' whole (split_made)
        self.broken_wholes = {}     # a cut piece's member key: how many blasts it was given (split_made)

    def generated_valid(self, rec, where):
        """Whether a record's `generated` (if any) is well formed (custom geometry plan, section 0): {kind 'fracWall',
        version 1, wall {x0, x1, openings [{x0, x1, z0, z1}], seed, storeys (1 or 2; left out, 2)}}, a fracturing wall made from numbers in its
        template's frame (tools/bake/frac_wall.py; x0 and x1 its tile edges, FRAC_WALL_MIN_LENGTH apart or more), or {kind 'relit', version 1}, the template's own mesh lit as a made
        wall is. A malformed one leaves the record out, as any malformed field does."""
        if 'generated' not in rec:
            return True
        g = rec['generated']
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)  # noqa: E731
        # (version 2 names a look; a wall's end styles are the Build's, worked out from where the walls meet; a wall's
        # version 3 and a slab's or ground shape's version 2 name the look by its donor)
        ok = isinstance(g, dict) and keyable(g.get('kind')) and g.get('kind') in GENERATED_VERSIONS \
            and g.get('version') in GENERATED_VERSIONS[g['kind']]
        if ok and g['version'] == FREE_VERSION.get(g['kind']):
            return self.free_generated(rec, g, num, where)
        # (a plain piece's numbers are checked as version 1's; a rock's with points as its look's version)
        points = ok and g['version'] == POINTS_VERSION.get(g['kind'])
        look = (g.get('ground') or {}).get('look') if points and isinstance(g.get('ground'), dict) else None
        plain = ok and (g['version'] == PLAIN_VERSION.get(g['kind']) or (points and look is None))
        version = 1 if plain else (2 if isinstance(look, dict) else 1) if points else g['version'] if ok else None
        if ok and g['kind'] == 'fracSlab':
            ok = self.slab_valid(g.get('slab'), num, version)
            if ok and not made_split.slab_left(g['slab']):
                # (nothing of it to build: the Build's check refuses it, review finding 32)
                self.c.error('slab-all-holes', '%s: its holes leave none of it, so it is left out of the build'
                           % (rec.get('label') or short(rec.get('from', {}).get('actor', '?'))), **where)
                return False
        elif ok and g['kind'] == 'ground':
            ok = self.ground_valid(g.get('ground'), num, version, points)
        elif ok and g['kind'] == 'fracWall':
            w = g.get('wall')
            ok = (isinstance(w, dict) and num(w.get('x0')) and num(w.get('x1')) and w['x1'] - w['x0'] >= FRAC_WALL_MIN_LENGTH
                  and w['x1'] - w['x0'] <= MADE_MAX_TILES * TILE + 1e-6 and 'ends' not in w and 'whole' not in w
                  and (('look' not in w and version < 3) or (version >= 2 and look_valid(
                      'fracWall', w.get('look'), version, DONOR_LOOK_SINCE['fracWall'], FRAC_WALL_LOOKS)))
                  and isinstance(w.get('seed', 1), int) and isinstance(w.get('storeys', 2), int)
                  and 1 <= w.get('storeys', 2) <= MADE_MAX_STOREYS and not isinstance(w.get('storeys'), bool)
                  and all(isinstance(o, dict) and all(num(o.get(k)) for k in ('x0', 'x1', 'z0', 'z1'))
                          and w['x0'] <= o['x0'] < o['x1'] <= w['x1'] and o['z0'] < o['z1']
                          for o in w.get('openings') or []))
        if ok and 'blasts' in g:
            # (a made wall, floor or roof built broken: custom geometry editing plan, B5)
            try:
                if g['kind'] not in MADE_KINDS:
                    raise ValueError('only a made wall, floor or roof breaks')
                made_blasts.check(g['blasts'])
                if g.get('breaksFurther', True) is not True:
                    raise ValueError('breaksFurther is true or left out')
            except ValueError as error:
                self.c.error('malformed', '%s: its blasts are not ones the Build makes: %s'
                           % (rec.get('label') or short(rec.get('from', {}).get('actor', '?')), error), **where)
                return False
        if ok and 'breaksFurther' in g and 'blasts' not in g:
            self.c.note('unknown-field', '%s: breaksFurther goes with blasts; with none it is ignored'
                      % (rec.get('label') or short(rec.get('from', {}).get('actor', '?'))), **where)
            g = rec['generated'] = {k: v for k, v in g.items() if k != 'breaksFurther'}
        if ok and plain:
            name = rec.get('label') or short(rec.get('from', {}).get('actor', '?'))
            default = ("the Bar's inside wall" if g['kind'] == 'fracWall' else 'asphalt' if g['kind'] == 'ground'
                       else "the Bar's upper floor" if g['slab'].get('look') == 'floor' else "the Bar's roof")
            self.c.warn('made-no-look', "%s has no look chosen (drawn plain in the editor): the Build makes it in %s, its "
                      "kind's default look; choose its look in its piece panel" % (name, default), **where)
            g = rec['generated'] = dict(g, version=1)
        elif ok and points:
            g = rec['generated'] = dict(g, version=version)
        if ok:
            kind = {'fracWall': 'wall', 'fracSlab': 'slab', 'ground': 'ground'}.get(g['kind'])
            numbers = g.get(kind) if kind else None
            if kind and donor_shape(kind, numbers) is False:
                self.c.note('look-measured', "%s's look, %s, is in none of this editor's catalogues: the Build measures it "
                          'from its donor' % (rec.get('label') or short(rec.get('from', {}).get('actor', '?')),
                                              numbers['look']['mesh']), **where)
            return True
        self.c.error('malformed', "generated must be a fracturing wall's numbers ({kind: fracWall, version: 1, wall: "
                   '{x0, x1, openings, seed, storeys}}: up to %d tiles long and %d storeys, version 2 with its look: '
                   'one of %s, or version 3 with its look named by its donor: {mesh, measure}), a slab\'s ({kind: '
                   'fracSlab, version: 1, slab: {x0, x1, y0, y1, holes, seed, look}}: whole tiles, 1 to %d each way, '
                   'its holes whole tiles inside it, its look one of %s), a ground shape\'s ({kind: ground, version: 1, '
                   'ground: {shape (patch, block or ramp), x0, x1, y0, y1, height, look}}: whole tiles, 1 to %d each '
                   'way, a height of 1 to %g, its look one of %s; version 2 for a slab or ground shape names its look '
                   'by its donor: {mesh, measure}, a ground look\'s also its material) or {kind: relit, version: 1} '
                   '(it has %r)'
                   % (MADE_MAX_TILES, MADE_MAX_STOREYS, ', '.join(FRAC_WALL_LOOKS), MADE_MAX_TILES,
                      ', '.join(FRAC_SLAB_LOOKS), GROUND_MAX_TILES, GROUND_MAX_HEIGHT, ', '.join(GROUND_LOOKS), g),
                   **where)
        return False

    def free_generated(self, rec, g, num, where):
        """A free-form request (FREE_VERSION) checked and put into the Build's free version (BUILD_FREE_VERSION): its
        numbers as they are, less `plain` (warned of: the Build makes the kind's default look), its blasts checked as
        any made piece's."""
        kind = {'fracWall': 'wall', 'fracSlab': 'slab', 'ground': 'ground'}[g['kind']]
        name = rec.get('label') or short(rec.get('from', {}).get('actor', '?'))
        n = g.get(kind)
        if not free_valid(g['kind'], n, num):
            self.c.error('malformed', '%s: its numbers are not a %s of the free form (custom geometry improvements plan, '
                         'section 10.2: free 1, x0 < x1, y0 < y1, z0 < z1, openings or holes inside, a whole seed, a look '
                         'of its kind; it has %r)' % (name, kind, n), **where)
            return False
        if g['kind'] == 'fracSlab' and not made_split.slab_left(n):
            self.c.error('slab-all-holes', '%s: its holes leave none of it, so it is left out of the build' % name, **where)
            return False
        if 'blasts' in g:
            try:
                if g['kind'] not in MADE_KINDS:
                    raise ValueError('only a made wall, floor or roof breaks')
                made_blasts.check(g['blasts'])
                if g.get('breaksFurther', True) is not True:
                    raise ValueError('breaksFurther is true or left out')
            except ValueError as error:
                self.c.error('malformed', '%s: its blasts are not ones the Build makes: %s' % (name, error), **where)
                return False
        elif 'breaksFurther' in g:
            self.c.note('unknown-field', '%s: breaksFurther goes with blasts; with none it is ignored' % name, **where)
            g = {k: v for k, v in g.items() if k != 'breaksFurther'}
        numbers = {k: v for k, v in n.items() if k != 'plain'}
        if n.get('plain'):
            default = ("the Bar's inside wall" if g['kind'] == 'fracWall' else 'asphalt' if g['kind'] == 'ground'
                       else "the Bar's upper floor" if n.get('look') == 'floor' else "the Bar's roof")
            self.c.warn('made-no-look', "%s has no look chosen (drawn plain in the editor): the Build makes it in %s, its "
                        "kind's default look; choose its look in its piece panel" % (name, default), **where)
            numbers.pop('look', None)
        rec['generated'] = dict(g, version=BUILD_FREE_VERSION[g['kind']], **{kind: numbers})
        if donor_shape(kind, numbers) is False:
            self.c.note('look-measured', "%s's look, %s, is in none of this editor's catalogues: the Build measures it "
                        'from its donor' % (name, numbers['look']['mesh']), **where)
        return True

    @staticmethod
    def ground_valid(s, num, version=1, points=False):
        """Whether a ground shape's numbers are well formed (tools/bake/ground.py check is the Build's); `points`: a
        rock's request of POINTS_VERSION, which carries its moved points (and no other request does)."""
        if not (isinstance(s, dict) and s.get('shape') in GROUND_SHAPES and all(num(s.get(k)) for k in ('x0', 'x1', 'y0', 'y1'))):
            return False
        if ('points' in s) != bool(points) or (points and s['shape'] != 'rock'):
            return False
        if points:
            try:
                if not num(s.get('height')):
                    return False
                ground_shapes.check_points(s)
            except (ValueError, TypeError, KeyError):
                return False
        whole = all(abs((s[b] - s[a]) / 96.0 - round((s[b] - s[a]) / 96.0)) < 1e-4
                    and 1 <= round((s[b] - s[a]) / 96.0) <= GROUND_MAX_TILES for a, b in (('x0', 'x1'), ('y0', 'y1')))
        height = s['shape'] == 'patch' or (num(s.get('height')) and 1 <= s['height'] <= GROUND_MAX_HEIGHT)
        seed = s['shape'] != 'rock' or (isinstance(s.get('seed'), int) and not isinstance(s.get('seed'), bool)
                                        and 0 <= s['seed'] < GROUND_ROCK_SEEDS)
        return whole and height and seed and look_valid('ground', s.get('look'), version, DONOR_LOOK_SINCE['ground'],
                                                        GROUND_LOOKS)

    @staticmethod
    def slab_valid(s, num, version=1):
        """Whether a slab's numbers are well formed (tools/bake/frac_slab.py check is the Build's; one its holes leave
        none of is well formed, and left out by generated_valid)."""
        def whole(v, base):
            return abs((v - base) / 96.0 - round((v - base) / 96.0)) < 1e-4
        if not (isinstance(s, dict) and all(num(s.get(k)) for k in ('x0', 'x1', 'y0', 'y1'))):
            return False
        if not all(whole(s[b], s[a]) and 1 <= round((s[b] - s[a]) / 96.0) <= MADE_MAX_TILES
                   for a, b in (('x0', 'x1'), ('y0', 'y1'))) or 'whole' in s:
            return False
        if not look_valid('fracSlab', s.get('look'), version, DONOR_LOOK_SINCE['fracSlab'], FRAC_SLAB_LOOKS) \
                or not isinstance(s.get('seed', 1), int) \
                or isinstance(s.get('seed'), bool) or not isinstance(s.get('holes') or [], list):
            return False
        return all(isinstance(h, dict) and all(num(h.get(k)) for k in ('x0', 'x1', 'y0', 'y1'))
                   and s['x0'] <= h['x0'] < h['x1'] <= s['x1'] and s['y0'] <= h['y0'] < h['y1'] <= s['y1']
                   and all(whole(h[k], s[k[0] + '0']) for k in ('x0', 'x1', 'y0', 'y1'))
                   for h in s.get('holes') or [])

    def join_made_walls(self):
        """Made walls that meet (custom geometry plan, M3 item 2): each copy's request gains its end styles
        (wall_joins; version 2, `ends`) when an end is joined, and its box follows its solid."""
        if len(self.walls) < 2:
            return
        found = made_wall_joins([dict(key=copy['label'], location=copy['location'], rotation=copy['rotation'],
                                      wall=copy['generated']['wall']) for copy, _ in self.walls])
        for copy, where in self.walls:
            ends = found[copy['label']]['ends']
            if ends == ['free', 'free']:
                continue
            gen = copy['generated']
            copy['generated'] = dict(gen, version=max(2, gen.get('version', 1)), wall=dict(gen['wall'], ends=list(ends)))
            _, _, inset, half = wall_heights(gen['wall'])
            insets = {'free': inset, 'line': 0.0, 'through': -half}
            # (a mitred or leaning end: its solid reaches its plane's furthest point along the wall)
            reach = lambda e: insets[e] if isinstance(e, str) else e['inset'] - abs(e['lean']) * half  # noqa: E731
            along = made_wall_along(gen['wall'], reach(ends[0]), reach(ends[1]))
            copy['box'] = self.c.boxes(self.parts[copy['label']], copy['location'], copy['rotation'], along)

    def made_walls_stacked(self):
        """A note for each made wall standing on another (custom geometry plan, M2 item 6; F-127): its bottom within
        WALL_STACK_GAP of the other's top, the two overlapping across and by more than a tile's quarter along. When
        the one under it breaks, it stays standing: the game passes a break from one fracturing piece to another only
        up to the height the blast reached (research/native/frac-neighbours.md), and the game's own walls keep their
        upper part over a hole broken under it (EXP-75 run C)."""
        for upper, where in self.walls:
            a = upper.get('box')
            if not a:
                continue
            for lower, _ in self.walls:
                b = lower.get('box')
                if lower is upper or not b or abs(a[4] - b[5]) > WALL_STACK_GAP or lower['member'] == upper['member']:
                    continue
                along = 0 if a[1] - a[0] >= a[3] - a[2] else 1
                over = [min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) for k in range(2)]
                if over[along] > TILE / 4 and over[1 - along] > 0:
                    self.c.note('wall-on-wall', "%s stands on %s: when %s breaks under it, it stays standing, as the "
                              "game's walls keep their upper part over a hole broken under it (a break passes from one "
                              'piece to another only as high as the blast reached)'
                              % (upper.get('whole') or upper['label'], lower.get('whole') or lower['label'],
                                 lower.get('whole') or lower['label']), **where)
                    break

    def made_slab_wholes(self):
        """The made floors and roofs as they were drawn, for the checks: [(copy, where)], a slab the Build cuts into
        pieces (made_split) one entry, its label the whole's and its box the pieces' together."""
        out, at = [], {}
        for c, where in self.slabs:
            if not c.get('box'):
                continue
            name = c.get('whole')
            if not name:
                out.append((c, where))
            elif name in at:
                at[name]['box'] = union([at[name]['box'], c['box']])
            else:
                at[name] = dict(label=name, box=list(c['box']))
                out.append((at[name], where))
        return out

    def made_slab_boxes(self):
        """The made floors and roofs as made_cursors takes them: [dict(box [x0, y0, z0, x1, y1, z1], label)]."""
        return [dict(box=[b[0], b[2], b[4], b[1], b[3], b[5]], label=c['label'])
                for c, _ in self.slabs for b in [c.get('box')] if b]

    def made_slab_cursors(self):
        """The made floors' and roofs' own cursor floors (custom geometry plan, M5b; F-128): the Build gives each its
        floors over its footprint (tools/bake/made_cursors.py), and cursor_storeys has them. Warned of:
        - slab-cursor-volume: a footprint over a stair or turned cursor volume of the map's, which stays as it is
          over the made floors;
        - slab-headroom: a made slab less than HEADROOM over the map's own floor tiles under it (F-71: the game gives
          no floor to a tile a soldier can't stand on). A made slab over another flat piece the project adds is
          floor_headroom's."""
        if not self.slabs:
            return
        slabs = self.made_slab_boxes()
        if (self.c.scene.get('exporterVersion') or 0) >= 20:
            volumes = [dict(key=v.get('name') or str(k), floor=v.get('floor'), box=list(v['box']['min']) + list(v['box']['max']),
                            stair=bool(v.get('stair')))
                       for k, v in enumerate(self.c.scene.get('cursorVolumes') or []) if v.get('box')]
            crossed = {}
            whole = {c['label']: c.get('whole') or c['label'] for c, _ in self.slabs}
            for c in made_cursors.split(volumes, slabs)['crossed']:
                crossed.setdefault(whole.get(c['slab'], c['slab']), set()).add('%s (%s)' % (short(str(c['volume'])), "a stair's" if c['why'] == 'stair' else 'turned'))
            for label, names in sorted(crossed.items()):
                where = next((w for c, w in self.slabs if (c.get('whole') or c['label']) == label), {})
                self.c.warn('slab-cursor-volume', "%s is over the map's cursor %s %s, which the Build leaves as %s over it: "
                          "the cursor may keep to %s floor there rather than the made floor's" % (
                              label, 'volume' if len(names) == 1 else 'volumes', ', '.join(sorted(names)),
                              'it is' if len(names) == 1 else 'they are', 'its' if len(names) == 1 else 'their'), **where)
        # (the floor tiles' saved places: a tile's floor is where the map's own piece has it)
        floors = [f for f in self.c.floor_edits.floor_records_now() if len(f.get('location') or ()) == 3]
        for c, where in self.made_slab_wholes():
            b, under = [c['box'][k] for k in (0, 2, 4, 1, 3, 5)], c['box'][4]
            tiles = sorted(list(f['tile']) for f in floors
                           if b[0] < f['location'][0] < b[3] and b[1] < f['location'][1] < b[4]
                           and 8.0 < under - f['location'][2] < HEADROOM)
            if tiles:
                self.c.warn('slab-headroom', "%s is less than %d units over the map's floor under it at %d %s: the game gives no "
                          "floor to a tile a soldier can't stand on, so %s won't be walked on" % (
                              c['label'], HEADROOM, len(tiles), 'tile' if len(tiles) == 1 else 'tiles',
                              'it' if len(tiles) == 1 else 'they'), tiles=tiles[:12], **where)

    def made_slabs_in_floors(self):
        """A warning for each floor or roof made from numbers that stands in a building but counts for none of its
        floors by the game editor's rule (tools/bake/buildings.py, F-87): a piece is listed in a floor only when it
        touches one of the floor's boxes (within 2) with its bottom more than 20 under that box's top. Such a slab is
        never cut away with its building, and the cursor lands on it (EXP-76 run E). The game's buildings have a floor
        start at each slab: URB_Bar's upstairs floor is the bottom of its floor 1, its roof of its floor 2.
        And slab-outdoors for one in no building with the map's floor at least HEADROOM under it: there the mouse
        takes its top on every storey (F-135)."""
        slabs = self.made_slab_wholes()
        if not slabs:
            return
        houses = [(b['name'] or 'a new building', [[x for x in f['boxes']] for f in b['floors']]) for b in self.c.building_edits.new_buildings]
        houses += [(e['name'], [[x for x in f['boxes']] for f in e['floors']]) for e in self.c.building_edits.edits
                   if not e.get('deleted') and e.get('floors')]
        edited = {e['actor'] for e in self.c.building_edits.edits}
        for b in self.c.scene.get('buildings') or []:
            if b.get('actor') in edited:
                continue
            floors = [[[*v['min'], *v['max']] for v in f.get('boxes') or [] if isinstance(v, dict)] for f in b.get('floors') or []]
            if any(floors):
                houses.append((b.get('actor') or 'a building of the map\'s', floors))
        ground = [f for f in self.c.floor_edits.floor_records_now() if len(f.get('location') or ()) == 3]
        for c, where in slabs:
            box = c['box']
            for name, floors in houses:
                vols = [v for f in floors for v in f if len(v) == 6]
                inside = any(min(box[1], v[3]) - max(box[0], v[0]) > TILE / 2 and min(box[3], v[4]) - max(box[2], v[1]) > TILE / 2
                             and v[2] - 64 <= box[4] <= v[5] + 64 for v in vols)
                if not inside:
                    continue
                counts = any(box[4] < v[5] - 20 and all(box[2 * j] <= v[j + 3] + 2 and box[2 * j + 1] >= v[j] - 2 for j in range(3))
                             for f in floors for v in f if len(v) == 6)
                if not counts:
                    self.c.warn('slab-in-no-floor', "%s stands in %s but in none of its floors: the game won't cut it away "
                              'when the cursor is inside, and the cursor lands on it. Start a floor at its height (the '
                              "game lists a piece in a floor only when its bottom is more than 20 under the floor's top), "
                              'as the Room with a roof tool and the game\'s buildings do' % (c['label'], name),
                              **where)
                break
            # (EXP-80 run H) out of every building the mouse takes the first walkable hit at once, whatever the storey
            # (XComTacticalHUD.GetMousePickActor), as on the game's overpasses and canopies: the tiles with the map's
            # floor standing room under the slab where its top is in no building's floor box
            boxes = [v for _, floors in houses for f in floors for v in f if len(v) == 6]
            under = sorted(list(f['tile']) for f in ground
                           if box[0] < f['location'][0] < box[1] and box[2] < f['location'][1] < box[3]
                           and box[4] - f['location'][2] >= HEADROOM
                           and not any(v[0] <= f['location'][0] <= v[3] and v[1] <= f['location'][1] <= v[4]
                                       and v[2] - 1 <= box[5] <= v[5] + 16 for v in boxes))
            if under:
                self.c.warn('slab-outdoors', "%s is in no building over %d %s of the map's floor under it: where soldiers "
                          "can stand on its top, the mouse picks it there on every storey, as it does the game's overpasses "
                          'and canopies, and the floor under it only from beside it. In a building (the Room with a roof '
                          'tool, or a building drawn round it) the storeys are picked one at a time and cut away' % (
                              c['label'], len(under), 'tile' if len(under) == 1 else 'tiles'), tiles=under[:12], **where)

    def made_wall_openings(self):
        """Warnings for what a made wall's gaps do in the game that may surprise (custom geometry plan, M1 item 4),
        by opening_play (one kind of gap since 19 November 2026, its play read from its shape): a gap units walk
        through with no wall under it to give cover and no door in it (a unit in it has cover toward its sides, as the
        game gives a tile between two pieces of wall; the game's doorways hold doors); one they walk through over a
        wall that gives cover; one starting under the cover line too low to walk through; one starting over it that
        doesn't reach across the sight line. A door stands in a gap when a door's box (a copy's, or one of the map's
        own the project leaves where it is) overlaps the gap's box by more than 8 along the wall and up."""
        if not self.wholes:
            return
        hidden = {short(h['name']) for h in self.c.hides}
        doors = [c['box'] for c in self.c.copies if c.get('actorClass') == 'XComInteractiveLevelActor' and c.get('box')]
        for obj in self.c.scene.get('objects') or []:
            if (obj.get('layer') == 'base' and obj.get('actorClass') == 'XComInteractiveLevelActor'
                    and short(obj['actor']) not in hidden and obj.get('mesh') in self.c.meshes):
                doors.append(world_box(obj, self.c.meshes, obj['location'], obj['rotation']))
        origin = self.c.grid_origin or self.c.origin
        for copy, where in self.wholes:
            wall = copy['generated']['wall']
            name = copy['label']
            # (a free-form wall's gaps are read on the map's grid, where the game's lines cross it)
            centres = grid_crossings(copy['location'], copy['rotation'], wall, origin) if wall.get('free') == 1 else None
            for o in wall.get('openings') or []:
                play = opening_play(wall, o, centres)
                low = o['z0'] < WALL_SWEEPS['cover'][0]
                what = "%s's gap at %g to %g along it" % (name, o['x0'], o['x1'])
                if not play['tiles']:
                    self.c.warn('wall-opening-between-tiles', "%s: units can't walk or see through it, and the wall gives "
                              "cover there as if whole: no tile's centre line passes through it (the game walks, sees "
                              "and takes cover along the lines between tiles' centres)" % what, **where)
                    continue
                if play['walk'] and play['cover'] != 'none':
                    self.c.warn('wall-window-walked', "%s: its bottom, %g over the floor, is under the game's walking "
                              'line, %g: units walk through it, over the wall under it, which gives %s cover there' % (
                                  what, o['z0'], WALL_SWEEPS['walk'], play['cover']), **where)
                elif play['walk']:
                    box = opening_box(copy['location'], copy['rotation'], o)
                    if not any(overlaps_by(box, d, 8.0) for d in doors):
                        self.c.warn('wall-doorway-no-door', '%s: a unit in this gap has cover toward its sides: put a '
                                  "door in it, as the game's doorways have" % what, **where)
                elif low:
                    self.c.warn('wall-doorway-low', "%s: units can't walk through it: its top is under the game's "
                              'walking line, %g over the floor' % (what, WALL_SWEEPS['walk']), **where)
                if not low and not play['walk'] and not play['sight']:
                    self.c.warn('wall-window-blind', "%s: units can't see through it: it doesn't reach across the "
                              "game's sight line, %g over the floor" % (what, WALL_SWEEPS['sight']), **where)

    def blasts_valid(self, rec, parts, where, name=None):
        """Whether an override's or added copy's `blasts` are well formed (made_blasts.check) and on a fracturing
        piece; else an error and the record (an override) or its blasts (a copy) left out."""
        try:
            if parts[0]['actorClass'] not in ('XComFracLevelActor', 'XComDecoFracLevelActor'):
                raise ValueError('it is a %s: only a fracturing piece breaks' % parts[0]['actorClass'])
            made_blasts.check(rec['blasts'])
            if rec.get('breaksFurther', True) is not True:
                raise ValueError('breaksFurther is true or left out')
        except ValueError as error:
            self.c.error('malformed', '%s: its blasts are not ones the Build makes: %s' % (
                name or short(rec['target']['actor']), error), **where)
            return False
        return True

    def made_pieces(self, made):
        """[(its place in the whole's frame (x, y, z), its numbers)] of a made wall or slab (made_split): one, the
        numbers as they are, when no cut is needed."""
        if made['kind'] == 'fracWall':
            w = made['wall']
            return [((float(w['x0']) + dx, 0.0, dz), n) for dx, dz, n in made_split.wall_pieces(
                w, wall_look_storeys, lambda n: wall_heights(n)[:2])]
        s = made['slab']
        return [((float(s['x0']) + dx, float(s['y0']) + dy, 0.0), n) for dx, dy, n in made_split.slab_pieces(s)]

    def split_made(self, rec, where, parts, pose, extra, pieces):
        """A made wall or floor cut into pieces the game is known to take (custom geometry editing plan, B4, D-3;
        made_split): each a copy of its own (`<actor>_part<k>`) at its place in the whole's frame, all of them one
        member of the project's groups (the whole's); the notes and checks name the whole."""
        out, made = rec['actor'], rec['generated']
        loc, rot, rounding = pose
        key = 'wall' if made['kind'] == 'fracWall' else 'slab'
        m = transform(loc, rot, [1, 1, 1])
        first = len(self.c.copies)
        if made.get('blasts'):
            self.broken_wholes['added|' + out] = len(made['blasts'])
        for k, (at, numbers) in enumerate(pieces, 1):
            place = [m[i][0] * at[0] + m[i][1] * at[1] + m[i][2] * at[2] + m[i][3] for i in range(3)]
            gen = dict(made, **{key: numbers})
            if made.get('blasts'):
                # (each piece the blasts that reach it, in its frame)
                span = [(0.0, float(numbers['x1']))] + ([(0.0, float(numbers['y1']))] if key == 'slab' else [None])
                gen['blasts'] = made_blasts.for_piece(made['blasts'], at, span)
                if not gen['blasts']:
                    del gen['blasts']
                    gen.pop('breaksFurther', None)
            self.c.add(dict(rec, actor='%s_part%d' % (out, k), generated=gen), where, parts,
                     (place, rot, rounding), extra=dict(extra, piece=k, member='added|' + out, whole=short(out)))
        made_copies = self.c.copies[first:]
        if not made_copies:
            return
        numbers = made[key]
        if key == 'wall':
            self.wholes.append((dict(label=short(out), location=loc, rotation=rot, generated=made), dict(where)))
            tiles = round((float(numbers['x1']) - float(numbers['x0'])) / TILE)
            joined = len({round(at[0], 3) for at, _ in pieces}) > 1
            stacked = len({round(at[2], 3) for at, _ in pieces}) > 1
            self.c.note('made-split', '%s, %d tiles long and %d storeys, is made as %d walls %s (each at most %d tiles long '
                      "and its look's storeys tall, as the game's walls are): a break passes between them as between "
                      "the game's joined walls" % (
                          short(out), tiles, numbers.get('storeys') or wall_look_storeys(numbers)[0], len(made_copies),
                          ' and '.join(w for w, on in (('joined end to end', joined), ('stacked', stacked)) if on),
                          FRAC_SLAB_MAX_TILES), **where)
        else:
            nx, ny = (round((float(numbers[b]) - float(numbers[a])) / TILE) for a, b in (('x0', 'x1'), ('y0', 'y1')))
            self.c.note('made-split', '%s, %d by %d tiles, is made as %d slabs side by side (each at most %d by %d '
                      'tiles): they list each other\'s fragments where they meet, as the game\'s touching pieces do, '
                      'so a break passes between them' % (short(out), nx, ny, len(made_copies), FRAC_SLAB_MAX_TILES,
                                                         FRAC_SLAB_MAX_TILES), **where)
        self.c.entities.append(dict(kind='add', entity=out, id=rec.get('id'), template=rec['from']['actor'],
                                  actorClass=parts[0]['actorClass'], location=loc, rotation=rot,
                                  rotationRounding=tidy(rounding, 6), pieces=len(made_copies),
                                  newBox=[tidy(v, 3) for v in union([c['box'] for c in made_copies])], **extra))
