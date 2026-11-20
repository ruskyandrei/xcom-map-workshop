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
# shapes, blasts, made floors' cursors and cuts)
from compiler_tables import (FRAC_SLAB_LOOKS, GROUND_LOOKS, HEADROOM, MADE_KINDS, TILE, donor_shape, keyable,
                             made_wall_along, short, tidy, union, wall_heights, world_box)
from export_math import transform
import looks
import ground as ground_shapes
import made_blasts
import made_cursors
import made_split

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
GENERATED_VERSIONS = {'fracWall': (1, 2, 3, 4), 'fracSlab': (1, 2, 3), 'ground': (1, 2, 3, 4), 'relit': (1,)}
DONOR_LOOK_SINCE = {'fracWall': 3, 'fracSlab': 2, 'ground': 2}
# a made piece with no look chosen (custom geometry editing plan, B2, 19 November 2026): drawn plain in the editor, its
# numbers its kind's default look's as version 1 has them; the Build makes it in that look (D-1) and warns made-no-look,
# and the copy goes on as version 1
PLAIN_VERSION = {'fracWall': 4, 'fracSlab': 3, 'ground': 3}
# a rock whose corners were moved in the editor (look picker and rock points plan, R1): its numbers carry `points`, and
# its request is this version whatever its look (a look id, one named by its donor, or none: plain), so an editor from
# before refuses it rather than make the seed's rock; it goes on to the Build as the version its look gives
POINTS_VERSION = {'ground': 4}


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
    import frac_wall
    own = frac_wall.storeys_of(frac_wall.look_of(dict(wall, look=resolved)))
    return max(own), max(own) > 1 and 1 in own


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


def opening_play(wall, o):
    """What the game does at an opening of a made wall (walls.js openingPlay is the twin): dict(tiles (how many tiles'
    centre lines pass through it), walk, climb (units vault through it: low cover under it, which the game's tile
    rebuild gives its ClimbOver, F-126), sight, cover: 'none', 'low', 'high' or 'whole' (the wall's own cover at those
    tiles))."""
    length = float(wall['x1']) - float(wall['x0'])
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
        found = wall_joins([dict(key=copy['label'], location=copy['location'], rotation=copy['rotation'],
                                 wall=copy['generated']['wall']) for copy, _ in self.walls])
        for copy, where in self.walls:
            ends = found[copy['label']]['ends']
            if ends == ['free', 'free']:
                continue
            gen = copy['generated']
            copy['generated'] = dict(gen, version=max(2, gen.get('version', 1)), wall=dict(gen['wall'], ends=list(ends)))
            _, _, inset, half = wall_heights(gen['wall'])
            insets = {'free': inset, 'line': 0.0, 'through': -half}
            along = made_wall_along(gen['wall'], insets[ends[0]], insets[ends[1]])
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
        for copy, where in self.wholes:
            wall = copy['generated']['wall']
            name = copy['label']
            for o in wall.get('openings') or []:
                play = opening_play(wall, o)
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
