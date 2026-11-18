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
has (the recipe's `sections`); a donor look no catalogue holds can't be drawn here (the Build measures it)."""
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
from mesh import write_glb  # noqa: E402

CACHE_SIZE = 32
# the longest wall drawn (its tile edges' distance): 32 tiles; the Build makes any length
MAX_LENGTH = 3072.0
MAX_OPENINGS = 16
MIN_LENGTH = 24 + 2 * frac_wall.RECIPE['endInset']
SLOTS = 6
SLAB_SLOTS = 2
GROUND_SLOTS = 1
MAX_HOLES = 32


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


def wall_numbers(text):
    """The wall's numbers from the request's JSON, checked, in one spelling (the cache's key): dict(x0, x1, openings,
    seed), storeys when it is 1 (frac_wall.shaped: 2, the donor's, is left out) and ends when one is joined (two free
    ends are left out). GeneratedError when malformed."""
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
    storeys = wall.get('storeys', 2)
    if storeys not in frac_wall.STOREYS or isinstance(storeys, bool):
        raise GeneratedError('a wall has 1 or 2 storeys')
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
    return dict(x0=x0, x1=x1, openings=out, seed=seed, **({'storeys': 1} if storeys == 1 else {}),
                **({'ends': list(ends)} if ends != ['free', 'free'] else {}),
                **({'look': look} if look != frac_wall.DEFAULT_LOOK else {}))


def slab_numbers(text):
    """A slab's numbers from the JSON `text`, checked (frac_slab.check: whole tiles, 1 to 16 each way, holes of whole
    tiles inside it; at most MAX_HOLES holes), in the form frac_slab.build takes: x0, x1, y0, y1, holes, seed, and its
    look when it is not the first."""
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
    try:
        frac_slab.check(with_recipe('slab', out)[0])
    except ValueError as error:
        raise GeneratedError(str(error))
    return out


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
    if g.get('look', ground_shapes.DEFAULT_LOOK) != ground_shapes.DEFAULT_LOOK:
        out['look'] = g['look']
    return out


def viewer_mesh(built):
    """frac_wall.build's mesh in the form mesh.write_glb writes (mesh.read_mesh's: the page's axes, x z y), every slot
    with triangles: an empty one gets a triangle of no area at the middle of the wall's box (inside it)."""
    lod = built['mesh']['lods'][0]
    out = dict(positions=[], normals=[], tangents=[], uvs=[[], []], colors=[], indices=list(lod['indices'][1]),
               sections=[dict(slot=s['slot'], first=s['first'], count=3 * s['triangles']) for s in lod['sections']])
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
        self.lock = threading.Lock()

    def fracwall(self, text):
        """The GLB of the wall whose numbers are the JSON `text`."""
        wall = wall_numbers(text)
        key = json.dumps(wall, sort_keys=True)
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('wall', wall)
        return self.made(key, lambda: frac_wall.build(built), sections or SLOTS, 'wall')

    def fracslab(self, text):
        """The GLB of the slab whose numbers are the JSON `text`."""
        slab = slab_numbers(text)
        key = 'slab:' + json.dumps(slab, sort_keys=True)
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('slab', slab)
        return self.made(key, lambda: frac_slab.build(built), sections or SLAB_SLOTS, 'slab')

    def ground(self, text):
        """The GLB of the ground shape whose numbers are the JSON `text`."""
        shape = ground_numbers(text)
        key = 'ground:' + json.dumps(shape, sort_keys=True)
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
        built, sections = with_recipe('ground', shape)
        return self.made(key, lambda: ground_shapes.build(built), sections or GROUND_SLOTS, 'ground shape')

    def made(self, key, build, slots, what):
        try:
            built = build()
        except GeneratedError:
            raise
        except Exception as error:      # (a recipe the generator can't make: said, not a dropped answer)
            raise GeneratedError('the %s could not be made: %s' % (what, error))
        mesh = viewer_mesh(built)
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
