"""Pieces the Build makes from numbers, drawn in the editor as the Build makes them (custom geometry plan, section 0).

A fracturing wall made from numbers (an added copy's `generated` of kind 'fracWall': tools/bake/frac_wall.py) is
drawn from its own mesh, not its template's: GET /generated/fracwall.glb?wall=<its numbers as JSON> answers the
mesh tools/bake/frac_wall.py builds from them, as the export's mesh files are (mesh.write_glb), its six sections in
slot order (each side's face by storey, the trims, the inside faces), which the page binds to its template's
materials. A slot the wall has no triangles in (openings over a whole storey's face) is drawn as one triangle of no
area inside the wall, so every slot keeps its place in that order. The geometry is the numbers' and the recipe's
alone, so no map is read. Meshes are kept by their numbers while the server runs (the last CACHE_SIZE).

A floor or roof slab made from numbers (kind 'fracSlab': tools/bake/frac_slab.py, custom geometry plan M5) is drawn
the same way: GET /generated/fracslab.glb?slab=<its numbers as JSON>, its two sections (the top with the edges, the
underside) in slot order. A ground shape (kind 'ground': tools/bake/ground.py, M6): GET /generated/ground.glb?ground=
<numbers>, its one section.

A piece whose look is named by its donor (custom geometry plan, M4: `look: {mesh, measure}`, a ground look's also its
material; tools/bake/looks.py) is drawn in the recipe the catalogue holds for it, with as many sections as its donor
has (the recipe's `sections`); a donor look no catalogue holds can't be drawn here (the Build measures it).

A wall of any length and storeys and a slab of any size (custom geometry editing plan, B4, D-3) are drawn as the Build
makes them: cut into pieces the game is known to take (tools/bake/made_split.py: walls at most 16 tiles long and
their look's storeys tall, joined end to end and stacked; slabs at most 16 by 16 tiles), each built on its own and
put at its place, joined into one mesh with the same sections.

A made wall, floor or roof built broken (B5: its blasts, made_blasts) is drawn with the fragments its blasts knock out
left out: ?blasts=<its blasts as JSON> beside its numbers."""
from collections import OrderedDict
import json
import math
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
# (after the viewer's own modules, so no module of the Build's can stand in for one of them)
if str(HERE.parent / 'bake') not in sys.path:
    sys.path.append(str(HERE.parent / 'bake'))
import frac_slab  # noqa: E402
import frac_wall  # noqa: E402
import ground as ground_shapes  # noqa: E402
import looks  # noqa: E402
import made_blasts  # noqa: E402
import made_split  # noqa: E402
from mesh import write_glb  # noqa: E402

CACHE_SIZE = 32
PIECES_KEPT = 96      # the made pieces kept (Meshes.piece)
# the longest wall drawn (its tile edges' distance), the widest slab and the most storeys: the compiler's bounds
# (MADE_MAX_TILES, MADE_MAX_STOREYS); the Build cuts them into pieces the game takes (made_split)
MAX_TILES = 128
MAX_LENGTH = MAX_TILES * 96.0
MAX_STOREYS = made_split.MAX_STOREYS
MAX_OPENINGS = 64
MIN_LENGTH = 24 + 2 * frac_wall.RECIPE['endInset']
SLOTS = 6
SLAB_SLOTS = 2
GROUND_SLOTS = 1
MAX_HOLES = 256


class GeneratedError(ValueError):
    pass


def donor_look(kind, look):
    """A look named by its donor, checked and in one spelling ({mesh, measure}, a ground look's also its material);
    GeneratedError when malformed."""
    try:
        looks.check_look(kind, look)
    except looks.LookError as error:
        raise GeneratedError(str(error))
    return {k: look[k] for k in ('mesh', 'material', 'measure') if k in look}


def with_recipe(kind, numbers):
    """The numbers with their donor look's recipe put in (looks.resolve, from the catalogues), and how many sections
    the piece has: (numbers, sections or None for a look id's). GeneratedError for a donor look no catalogue holds."""
    look = numbers.get('look')
    if not isinstance(look, dict):
        return numbers, None
    try:
        resolved = looks.resolve(kind, look)
    except looks.LookError as error:
        raise GeneratedError('%s (the Build measures it from its donor)' % error)
    return dict(numbers, look=resolved), int(resolved['recipe'].get('sections') or 0) or None


def free_text(text):
    """Whether a request's numbers (JSON `text`) are in the free form (the custom geometry improvements plan, section
    10.2: `free: 1`); False for anything else, which the older parsers then say what is wrong with."""
    try:
        numbers = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(numbers, dict) and numbers.get('free') == 1


def free_numbers(kind, text):
    """A free-form piece's numbers (`kind` 'wall', 'slab' or 'ground') from the request's JSON, their donor look in
    one spelling, checked by the generator's own check of the free form (check_free), in one spelling for the cache's
    key: the numbers as the page sends them (made_free.js freeNumbers). GeneratedError when malformed."""
    numbers = json.loads(text)
    if isinstance(numbers.get('look'), dict):
        numbers = dict(numbers, look=donor_look(kind, numbers['look']))
    elif 'look' in numbers and numbers['look'] == {'wall': frac_wall.DEFAULT_LOOK, 'slab': frac_slab.DEFAULT_LOOK,
                                                   'ground': ground_shapes.DEFAULT_LOOK}[kind]:
        numbers = {k: v for k, v in numbers.items() if k != 'look'}
    if kind == 'wall':
        ends = numbers.get('ends')
        if ends is not None and (not isinstance(ends, list) or len(ends) != 2):
            raise GeneratedError("a wall's ends are two")
    generator = {'wall': frac_wall, 'slab': frac_slab, 'ground': ground_shapes}[kind]
    if not hasattr(generator, 'check_free'):
        raise GeneratedError('this editor makes no free-form %s yet' % kind)
    try:
        built = with_recipe(kind, numbers)[0]
        # (a wall or slab is checked piece by piece, as the Build cuts it: one piece is at most the splitter's chunk)
        if kind == 'wall':
            pieces = [n for _, _, n in made_split.wall_pieces(built, wall_look_storeys, wall_heights)]
        elif kind == 'slab':
            if not made_split.slab_left(built):
                raise ValueError("the slab's holes leave none of it")
            pieces = [n for _, _, n in made_split.slab_pieces(built)]
        else:
            pieces = [built]
        for piece in pieces:
            generator.check_free(piece)
    except (ValueError, TypeError, KeyError) as error:
        raise GeneratedError(str(error))
    return numbers


def wall_numbers(text):
    """The wall's numbers from the request's JSON, checked, in one spelling (the cache's key): dict(x0, x1, openings,
    seed), storeys when given (1 to MAX_STOREYS; a look id's 2, the default, is left out) and ends when one is joined
    (two free ends are left out). GeneratedError when malformed."""
    try:
        wall = json.loads(text)
    except (TypeError, ValueError):
        raise GeneratedError('the wall is not JSON')
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)  # noqa: E731
    if not isinstance(wall, dict) or not num(wall.get('x0')) or not num(wall.get('x1')):
        raise GeneratedError('a wall needs its ends, x0 and x1')
    x0, x1 = float(wall['x0']), float(wall['x1'])
    if not MIN_LENGTH <= x1 - x0 <= MAX_LENGTH:
        raise GeneratedError('a wall drawn here is %d to %d long' % (MIN_LENGTH, MAX_LENGTH))
    seed = wall.get('seed', 1)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise GeneratedError('a wall\'s seed is a whole number')
    openings = wall.get('openings') or []
    if not isinstance(openings, list) or len(openings) > MAX_OPENINGS:
        raise GeneratedError('a wall has up to %d openings' % MAX_OPENINGS)
    out = []
    for o in openings:
        if not (isinstance(o, dict) and all(num(o.get(k)) for k in ('x0', 'x1', 'z0', 'z1'))
                and x0 <= o['x0'] < o['x1'] <= x1 and o['z0'] < o['z1']):
            raise GeneratedError('an opening outside its wall or of no size')
        out.append({k: float(o[k]) for k in ('x0', 'x1', 'z0', 'z1')})
    storeys = wall.get('storeys')
    if storeys is not None and (not isinstance(storeys, int) or isinstance(storeys, bool)
                                or not 1 <= storeys <= MAX_STOREYS):
        raise GeneratedError('a wall has 1 to %d storeys' % MAX_STOREYS)
    # its end styles where it is joined to another made wall (custom geometry plan, M3 item 2): two free ends left out
    ends = wall.get('ends', ['free', 'free'])
    if not isinstance(ends, list) or len(ends) != 2 or any(e not in frac_wall.END_INSETS for e in ends):
        raise GeneratedError("a wall's ends are each %s" % ', '.join(frac_wall.END_INSETS))
    # its look (M4 item 1): the default left out; or named by its donor (M4)
    look = wall.get('look', frac_wall.DEFAULT_LOOK)
    if isinstance(look, dict):
        look = donor_look('wall', look)
    elif look not in frac_wall.LOOKS:
        raise GeneratedError('a wall\'s look is one of %s, or its donor {mesh, measure}' % ', '.join(frac_wall.LOOKS))
    if storeys == 2 and not isinstance(look, dict):
        storeys = None
    return dict(x0=x0, x1=x1, openings=out, seed=seed, **({'storeys': storeys} if storeys is not None else {}),
                **({'ends': list(ends)} if ends != ['free', 'free'] else {}),
                **({'look': look} if look != frac_wall.DEFAULT_LOOK else {}))


def slab_numbers(text):
    """A slab's numbers from the JSON `text`, checked (whole tiles, 1 to MAX_TILES each way, and each piece the Build
    cuts it into by frac_slab.check: holes of whole tiles inside it; at most MAX_HOLES holes), in the form frac_slab.build
    takes: x0, x1, y0, y1, holes, seed, and its look when it is not the first."""
    try:
        slab = json.loads(text)
    except (TypeError, ValueError):
        raise GeneratedError('a slab is its numbers as JSON')
    if not isinstance(slab, dict):
        raise GeneratedError('a slab is its numbers as JSON')
    holes = slab.get('holes') or []
    if not isinstance(holes, list) or len(holes) > MAX_HOLES:
        raise GeneratedError('a slab has at most %d holes' % MAX_HOLES)
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not all(number(slab.get(k)) for k in ('x0', 'x1', 'y0', 'y1')) or \
            not all(isinstance(h, dict) and all(number(h.get(k)) for k in ('x0', 'x1', 'y0', 'y1')) for h in holes):
        raise GeneratedError("a slab's footprint and holes are numbers")
    out = dict(x0=float(slab['x0']), x1=float(slab['x1']), y0=float(slab['y0']), y1=float(slab['y1']),
               holes=[{k: float(h[k]) for k in ('x0', 'x1', 'y0', 'y1')} for h in holes], seed=slab.get('seed', 1))
    look = slab.get('look', frac_slab.DEFAULT_LOOK)
    if isinstance(look, dict):
        out['look'] = donor_look('slab', look)
    elif look != frac_slab.DEFAULT_LOOK:
        out['look'] = look
    if not all(1 <= round((out[b] - out[a]) / 96.0) <= MAX_TILES for a, b in (('x0', 'x1'), ('y0', 'y1'))):
        raise GeneratedError('a slab drawn here is 1 to %d tiles each way' % MAX_TILES)
    try:
        # a slab cut into pieces drops the pieces its holes cover whole, so the whole slab is asked first: one its
        # holes leave none of is said, not drawn as nothing (the compiler leaves it out with the same words)
        if not made_split.slab_left(out):
            raise ValueError("the slab's holes leave none of it")
        for _, _, piece in made_split.slab_pieces(with_recipe('slab', out)[0]):
            frac_slab.check(piece)
    except ValueError as error:
        raise GeneratedError(str(error))
    return out


def joined(parts):
    """viewer_mesh's meshes [(mesh, (dx, dy, dz): its place in game axes)] as one mesh, each slot's triangles in one
    section, in slot order."""
    if len(parts) == 1 and not any(parts[0][1]):
        return parts[0][0]
    out = dict(positions=[], normals=[], tangents=[], uvs=[[], []], colors=[], indices=[], sections=[])
    by_slot = {}
    for mesh, (dx, dy, dz) in parts:
        base = len(out['positions']) // 3
        p = mesh['positions']
        for i in range(0, len(p), 3):
            out['positions'].extend((p[i] + dx, p[i + 1] + dz, p[i + 2] + dy))     # (the page's axes: x z y)
        for key in ('normals', 'tangents', 'colors'):
            out[key].extend(mesh[key])
        for channel in range(2):
            out['uvs'][channel].extend(mesh['uvs'][channel])
        for s in mesh['sections']:
            by_slot.setdefault(s['slot'], []).extend(v + base for v in mesh['indices'][s['first']:s['first'] + s['count']])
    for slot in sorted(by_slot):
        out['sections'].append(dict(slot=slot, first=len(out['indices']), count=len(by_slot[slot])))
        out['indices'].extend(by_slot[slot])
    return out


def blasts_of(text):
    """A piece's blasts from the JSON `text` ('' for none), checked (made_blasts.check)."""
    if not text:
        return []
    try:
        return made_blasts.check(json.loads(text))
    except (TypeError, ValueError) as error:
        raise GeneratedError('its blasts: %s' % error)


def wall_look_storeys(numbers):
    """(its look's own storeys, whether a wall one storey tall can be made in it) of a wall whose look is resolved."""
    own = frac_wall.storeys_of(frac_wall.look_of(numbers))
    return max(own), max(own) > 1 and 1 in own


def wall_heights(numbers):
    """A wall's bottom and top in its frame, its look resolved (frac_wall.shaped)."""
    R = frac_wall.shaped(numbers)
    return float(R['bottom']), float(R['top'])


def ground_numbers(text):
    """A ground shape's numbers from the JSON `text`, checked (ground.check), in one spelling: shape, x0, x1, y0, y1,
    height (a block's, ramp's or rock's), seed (a rock's), and its look when it is not the first."""
    try:
        g = json.loads(text)
    except (TypeError, ValueError):
        raise GeneratedError('a ground shape is its numbers as JSON')
    if not isinstance(g, dict):
        raise GeneratedError('a ground shape is its numbers as JSON')
    if isinstance(g.get('look'), dict):
        g = dict(g, look=donor_look('ground', g['look']))
    try:
        ground_shapes.check(with_recipe('ground', g)[0])
    except (ValueError, TypeError) as error:
        raise GeneratedError(str(error))
    out = dict(shape=g['shape'], **{k: float(g[k]) for k in ('x0', 'x1', 'y0', 'y1')})
    if g['shape'] != 'patch':
        out['height'] = float(g['height'])
    if g['shape'] == 'rock':
        out['seed'] = int(g['seed'])
        if g.get('points') is not None:
            out['points'] = [[float(v) for v in p] for p in g['points']]
    if g.get('look', ground_shapes.DEFAULT_LOOK) != ground_shapes.DEFAULT_LOOK:
        out['look'] = g['look']
    return out


def viewer_mesh(built, gone=()):
    """frac_wall.build's mesh in the form mesh.write_glb writes (mesh.read_mesh's: the page's axes, x z y), every slot
    with triangles: an empty one gets a triangle of no area at the middle of the wall's box (inside it). `gone`: the
    fragments left out (made_blasts.hidden)."""
    lod = built['mesh']['lods'][0]
    if gone:
        indices, sections = [], []
        for slot, kept in made_blasts.kept_indices(lod, gone):
            sections.append(dict(slot=slot, first=len(indices), count=len(kept)))
            indices.extend(kept)
    else:
        indices = list(lod['indices'][1])
        sections = [dict(slot=s['slot'], first=s['first'], count=3 * s['triangles']) for s in lod['sections']]
    out = dict(positions=[], normals=[], tangents=[], uvs=[[], []], colors=[], indices=indices, sections=sections)
    empty = [s for s in out['sections'] if not s['count']]
    for (x, y, z), (tangent, normal, uvs), colour in zip(lod['positions'], lod['vertices'], lod['colours']):
        t = [(v - 127.5) / 127.5 for v in tangent]
        n = [(v - 127.5) / 127.5 for v in normal]
        out['positions'].extend((x, z, y))
        out['normals'].extend((n[0], n[2], n[1]))
        out['tangents'].extend((t[0], t[2], t[1], -n[3]))
        for channel in range(2):
            out['uvs'][channel].extend(uvs[channel])
        b, g, r, a = colour
        out['colors'].extend((r / 255, g / 255, b / 255, a / 255))
    if empty:
        n = len(out['positions']) // 3
        middle = [(lo + hi) / 2 for lo, hi in zip(*(map(min, zip(*lod['positions'])), map(max, zip(*lod['positions']))))]
        out['positions'].extend((middle[0], middle[2], middle[1]))
        out['normals'].extend((0.0, 1.0, 0.0))
        out['tangents'].extend((1.0, 0.0, 0.0, 1.0))
        for channel in range(2):
            out['uvs'][channel].extend((0.0, 0.0))
        out['colors'].extend((1.0, 1.0, 1.0, 1.0))
        # the sections stay in slot order, each empty one a triangle at the new vertex, after the real ones
        for s in empty:
            s['first'] = len(out['indices'])
            s['count'] = 3
            out['indices'].extend((n, n, n))
        out['sections'].sort(key=lambda s: s['slot'])
    return out


class _Bytes:
    """What mesh.write_glb writes to, kept in memory."""
    data = b''

    def write_bytes(self, data):
        self.data = data


class Meshes:
    """The made walls' and slabs' mesh files, by their numbers."""

    def __init__(self, size=CACHE_SIZE):
        self.size = size
        self.kept = OrderedDict()
        self.piece_kept = OrderedDict()     # (maker, a piece's numbers) -> its build (piece)
        self.lock = threading.Lock()

    def piece(self, build, numbers):
        """build(numbers), kept (PIECES_KEPT): a long or tall made wall is cut into pieces, and the page asks for the
        whole wall at each step of a handle's drag; a gap moved changes only the pieces it is in, so the rest are not
        made again (the user, 19 November 2026: gap edits on a wall of 29 tiles and six storeys were slow)."""
        key = (build.__module__, build.__name__, json.dumps(numbers, sort_keys=True))
        with self.lock:
            if key in self.piece_kept:
                self.piece_kept.move_to_end(key)
                return self.piece_kept[key]
        built = build(numbers)
        with self.lock:
            self.piece_kept[key] = built
            while len(self.piece_kept) > PIECES_KEPT:
                self.piece_kept.popitem(last=False)
        return built

    def pieces(self, build, cut, blasts=(), slab=False):
        """A build of each piece the Build cuts a piece into (`cut`: [(dx, dy, dz, numbers)]), as one mesh; with the
        fragments `blasts` knock out (each piece's in its frame) left out."""
        def made():
            out = []
            for dx, dy, dz, numbers in cut:
                built = self.piece(build, numbers)
                span = [(0.0, numbers['x1'] - numbers['x0'])] + ([(0.0, numbers['y1'] - numbers['y0'])] if slab else [None])
                mine = made_blasts.for_piece(blasts, (dx, dy, dz), span) if blasts else []
                out.append((built, (dx, dy, dz), made_blasts.hidden(built, mine)))
            return out
        return made

    def fracwall(self, text, blasts=''):
        """The GLB of the wall whose numbers are the JSON `text`, broken by `blasts` (JSON, '' for none)."""
        wall = free_numbers('wall', text) if free_text(text) else wall_numbers(text)
        blasts = blasts_of(blasts)
        key = json.dumps(wall, sort_keys=True) + ('|' + json.dumps(blasts) if blasts else '')
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('wall', wall)
        try:
            cut = made_split.wall_pieces(built, wall_look_storeys, wall_heights, ends=True)
        except ValueError as error:
            raise GeneratedError('the wall could not be made: %s' % error)
        # (a piece of a cut wall is in its own frame, from 0: put at its start in the wall's)
        cut = [(0.0, 0.0, 0.0, built)] if len(cut) == 1 else [(built['x0'] + dx, 0.0, dz, n) for dx, dz, n in cut]
        return self.made(key, self.pieces(frac_wall.build, cut, blasts), sections or SLOTS, 'wall')

    def fracslab(self, text, blasts=''):
        """The GLB of the slab whose numbers are the JSON `text`, broken by `blasts` (JSON, '' for none)."""
        slab = free_numbers('slab', text) if free_text(text) else slab_numbers(text)
        blasts = blasts_of(blasts)
        key = 'slab:' + json.dumps(slab, sort_keys=True) + ('|' + json.dumps(blasts) if blasts else '')
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('slab', slab)
        cut = made_split.slab_pieces(built)
        cut = ([(0.0, 0.0, 0.0, built)] if len(cut) == 1
               else [(built['x0'] + dx, built['y0'] + dy, 0.0, n) for dx, dy, n in cut])
        return self.made(key, self.pieces(frac_slab.build, cut, blasts, slab=True), sections or SLAB_SLOTS, 'slab')

    def ground(self, text):
        """The GLB of the ground shape whose numbers are the JSON `text`."""
        shape = free_numbers('ground', text) if free_text(text) else ground_numbers(text)
        key = 'ground:' + json.dumps(shape, sort_keys=True)
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('ground', shape)
        return self.made(key, lambda: [(ground_shapes.build(built), (0.0, 0.0, 0.0), [])], sections or GROUND_SLOTS,
                         'ground shape')

    def ground_corners(self, text):
        """A rock's points and corners (ground.rock_corners) for the editor's blue dots: {points: [[x, y, z]],
        corners: [index]}."""
        shape = free_numbers('ground', text) if free_text(text) else ground_numbers(text)
        try:
            points, corners = ground_shapes.rock_corners(with_recipe('ground', shape)[0])
        except ValueError as error:
            raise GeneratedError(str(error))
        return dict(points=[[round(v, 4) for v in p] for p in points], corners=corners)

    def made(self, key, build, slots, what):
        try:
            built = build()
        except GeneratedError:
            raise
        except Exception as error:      # (a recipe the generator can't make: said, not a dropped answer)
            raise GeneratedError('the %s could not be made: %s' % (what, error))
        mesh = joined([(viewer_mesh(b, gone), at) for b, at, gone in built])
        if len(mesh['sections']) != slots:
            # the page binds the parts to the materials in slot order
            raise GeneratedError('the %s has %d slots, not %d' % (what, len(mesh['sections']), slots))
        sink = _Bytes()
        write_glb(mesh, sink)
        with self.lock:
            self.kept[key] = sink.data
            while len(self.kept) > self.size:
                self.kept.popitem(last=False)
        return sink.data
