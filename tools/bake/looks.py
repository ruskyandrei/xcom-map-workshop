"""The looks a made wall, slab or ground shape can take: any of the game's own pieces of that kind, named by their
donor (custom geometry plan, stage M4; private/plans/done/custom-geometry-m4-workorders.md holds the contract).

A made piece is a copy of its donor actor, so the copy's own source (its map and actor) is the placing the Build
clones. Its request names the look as `look: {mesh, measure}` (a ground shape's also `material`): the donor's mesh
path and the version of the measurer that read it. The recipe the generator builds from comes from the checked-in
catalogue when it holds that mesh (and material) at that measurer version, else from measuring the donor with the
measurer of that version (`resolve` with the package the donor is in and its actor's name). Each measurer is
deterministic, so a catalogued look and a measured one give the same piece. Requests with a look id ('bar-inside',
'floor', 'asphalt') are older and read from wall_looks.json, slab_looks.json and ground_looks.json as before; this
module only resolves the looks named by their donor.

The catalogues are tools/bake/looks/walls.json, slabs.json and ground.json, each {about, measure, built, looks: [entry]},
an entry {mesh, map, actor, maps, name, setting, lwrOnly, facts, warnings, twin, recipe} (ground's with its material),
written by wall_catalogue.py, slab_catalogue.py and ground_catalogue.py; `build` runs them. `listing` gives the
page its list of a kind's looks: the entries with only the numbers the page draws by, and each entry's `surfaces`.

`surfaces` (the custom geometry improvements plan, 5.2) says, for each surface a texture mapping takes (uv_mapping.py:
a wall's faces, side by side; a slab's top and underside; a ground shape's top and sides), how its look draws it on
its donor, worked out from the recipe's planar maps over the donor face's extent (no map is read again): the slots it
draws in, its repeat along u and v, the repeats the donor's face spans along each (`share`) and whether the texture
tiles along each (`tiles`). Some looks draw a window of a larger texture (an atlas: the subway car roof's top is the
top half of its texture, its underside the bottom half); a texture mapping repeats the whole texture, which on such a
surface shows its other parts (the page says so: made_mapping.js textureNotes). The rule, along each axis: the texture
tiles where the face's coordinates run over a whole repeat or across a repeat's edge (a whole number); where they stay
inside one repeat, it tiles when the surface's two repeats are square (within SQUARE: a texture laid by the world, on a
face narrower than its repeat, as the construction kit's 88-wide core floors on a 192 tile), and is a window when they
are not (an unwrap fitted to a part of a texture: the subway roof's 302 by 584, the UFO walls' 288 by 916) or when the
coordinate doesn't change at all (a strip of a trim texture). On the checked-in catalogues (21 November 2026) it finds
22 wall faces (a side each) of 17 looks, 8 slab surfaces of 6 looks and the tops of 32 of the 193 ground looks windows
(test_looks.py names some of each, and tiling ones the span alone would have taken); and 71 wall faces of 50 looks are
no face at all (their outline there is trims, which a mapping doesn't take: `faces` side None; 21 looks on both sides).
A ground look's top has no measured place (its box's middle isn't recorded), so only its span is read there; its sides
take its top's repeats (ground.py), and its fact.

  python -B tools/bake/looks.py build [walls] [slabs] [ground]
"""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import threading

HERE = Path(__file__).resolve().parent
FOLDER = HERE / 'looks'
# each kind: its catalogue file, its measurer module, the script that writes the catalogue
KINDS = {
    'wall': ('walls.json', 'wall_measure', 'wall_catalogue.py'),
    'slab': ('slabs.json', 'slab_measure', 'slab_catalogue.py'),
    'ground': ('ground.json', 'ground_measure', 'ground_catalogue.py'),
}
# the generated request kinds and the key their numbers are under, by look kind
REQUESTS = {'fracWall': ('wall', 'wall'), 'fracSlab': ('slab', 'slab'), 'ground': ('ground', 'ground')}
# the recipe's numbers the page draws by, each kind's (heights, thickness, slots); the rest stays with the Build
PAGE_RECIPE = {
    'wall': ('bottom', 'top', 'storey', 'face', 'half', 'endInset', 'sections'),
    'slab': ('bottom', 'top', 'sections', 'tile'),
    'ground': ('thickness', 'repeat', 'sections'),
}
_lock = threading.Lock()
_catalogues = {}
_measured = {}


class LookError(ValueError):
    pass


def check_look(kind, look):
    """A donor look's numbers, checked: {mesh: a mesh path, measure: a whole number of 1 or more} (ground's also
    material: a material path). LookError when malformed."""
    if kind not in KINDS:
        raise LookError('a look of an unknown kind: %r' % (kind,))
    if not isinstance(look, dict) or not isinstance(look.get('mesh'), str) or '.' not in look['mesh']:
        raise LookError("a look names its donor's mesh (package.group.name): %r" % (look,))
    measure = look.get('measure')
    if not isinstance(measure, int) or isinstance(measure, bool) or measure < 1:
        raise LookError("a look names the measurer's version that read it (1 or more): %r" % (look,))
    if kind == 'ground' and (not isinstance(look.get('material'), str) or '.' not in look['material']):
        raise LookError("a ground look names its material (package.group.name): %r" % (look,))
    return look


def catalogue(kind, folder=None):
    """The kind's catalogue ({about, measure, looks}; no looks when the file isn't there), read once."""
    if kind not in KINDS:
        raise LookError('a look of an unknown kind: %r' % (kind,))
    path = Path(folder or FOLDER) / KINDS[kind][0]
    key = str(path)
    with _lock:
        if key not in _catalogues:
            data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'looks': []}
            index = {}
            for e in data.get('looks', ()):
                index[(e['mesh'], e.get('material') if kind == 'ground' else None)] = e
            _catalogues[key] = (data, index)
        return _catalogues[key]


def entry(kind, mesh, material=None, folder=None):
    """The catalogue's entry for that donor mesh (and a ground look's material), or None."""
    return catalogue(kind, folder)[1].get((mesh, material if kind == 'ground' else None))


def measurer(kind):
    """The kind's measurer module (KINDS: wall_measure, slab_measure, ground_measure). Each is imported by its name
    here, not through importlib, so that the release's list of modules (make_release.modules, which reads the
    imports) ships all three."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    if kind == 'wall':
        import wall_measure as module
    elif kind == 'slab':
        import slab_measure as module
    elif kind == 'ground':
        import ground_measure as module
    else:
        raise KeyError(kind)
    assert module.__name__ == KINDS[kind][1]
    return module


def resolve(kind, look, package=None, actor=None, folder=None):
    """The look with its recipe: dict(look, recipe, warnings). From the catalogue when it holds the donor at the
    look's measurer version; else measured on the donor (`package`, a Package the donor is placed in, and `actor`,
    its actor's name), kept while this process runs. LookError when neither can give it."""
    check_look(kind, look)
    material = look.get('material') if kind == 'ground' else None
    data, _ = catalogue(kind, folder)
    e = entry(kind, look['mesh'], material, folder)
    base = {k: look[k] for k in ('mesh', 'measure', 'material') if k in look}
    if e is not None and data.get('measure') == look['measure']:
        return dict(base, recipe=copy.deepcopy(e['recipe']), warnings=list(e.get('warnings', ())))
    key = (kind, look['mesh'], material, look['measure'], getattr(package, 'path', None), actor)
    with _lock:
        if key in _measured:
            return copy.deepcopy(_measured[key])
    if package is None or actor is None:
        raise LookError('the look of %s is in no catalogue at measurer version %d, and no donor was given to measure'
                        % (look['mesh'], look['measure']))
    module = measurer(kind)
    if getattr(module, 'VERSION', None) != look['measure']:
        raise LookError('the look of %s was read by measurer version %d; this Build has version %s'
                        % (look['mesh'], look['measure'], getattr(module, 'VERSION', None)))
    # (a ground look is its material on the donor: the measurer reads that one, not the donor's top)
    measured = module.measure(package, actor, material=material) if kind == 'ground' else module.measure(package, actor)
    out = dict(base, recipe=measured['recipe'], warnings=list(measured.get('warnings', ())))
    with _lock:
        _measured[key] = copy.deepcopy(out)
    return out


def resolved(generated, package=None, actor=None, folder=None):
    """A copy's `generated` request with its look's recipe put in (resolve) when its look names a donor; as it is
    otherwise (a look id, no look, or a look already resolved)."""
    if not isinstance(generated, dict) or generated.get('kind') not in REQUESTS:
        return generated
    kind, key = REQUESTS[generated['kind']]
    numbers = generated.get(key)
    look = numbers.get('look') if isinstance(numbers, dict) else None
    if not isinstance(look, dict) or 'recipe' in look:
        return generated
    return dict(generated, **{key: dict(numbers, look=resolve(kind, look, package, actor, folder))})


def listing(kind, folder=None):
    """The page's list of the kind's looks: each entry with only the recipe's numbers the page draws by
    (PAGE_RECIPE), and its surfaces (`surfaces`)."""
    data, _ = catalogue(kind, folder)
    out = []
    for e in data.get('looks', ()):
        row = {k: v for k, v in e.items() if k != 'recipe'}
        row['recipe'] = {k: e['recipe'][k] for k in PAGE_RECIPE[kind] if k in e.get('recipe', {})}
        row['surfaces'] = surfaces(kind, e)
        out.append(row)
    return {'kind': kind, 'measure': data.get('measure'), 'looks': out}


# ---- whether a look's surfaces tile (the module's words)
SQUARE = 1.1        # a surface whose two repeats are within a tenth of each other is square
SLACK = 1e-3        # of a repeat: coordinates this near a whole repeat or a whole number reach it
CONSTANT = 1e6      # game units: a coordinate whose repeat is longer doesn't change (measure_common.CONSTANT)


def _repeat(g):
    """Game units a repeat of a planar map's coordinate (u = a x + b y + c: 1 / |(a, b)|), None where it doesn't
    change."""
    length = math.hypot(g[0], g[1])
    return round(1.0 / length, 1) if length * CONSTANT > 1.0 else None


def tiling(fit, xs, ys, placed=True):
    """How a planar map `fit` ([[a, b, c], [d, e, f]]: u = a x + b y + c, v = d x + e y + f) draws its texture over a
    face spanning xs (x0, x1) and ys (y0, y1): dict(repeat [u, v], share [u, v], tiles [u, v]) (the module's rule).
    `placed` False: the face's place isn't known, only its size (xs and ys from 0), so whether it crosses a repeat's edge
    isn't read."""
    repeat = [_repeat(g) for g in fit]
    square = None not in repeat and max(repeat) <= SQUARE * min(repeat)
    share, tiles = [], []
    for g in fit:
        values = [g[0] * x + g[1] * y + g[2] for x in xs for y in ys]
        lo, hi = min(values), max(values)
        crosses = placed and math.floor(lo + SLACK) != math.floor(hi - SLACK)
        share.append(round(hi - lo, 3) + 0.0)
        tiles.append(bool(hi - lo >= 1.0 - SLACK or crosses or square))
    return dict(repeat=repeat, share=share, tiles=tiles)


def _wall_side(R, X):
    """A wall look's side X ('A', facing +y; 'B'): dict(slots, repeat, share, tiles) of its face (each face slot over
    its band of the face, between the side's storey splits: tiling along an axis where every slot tiles), or None for a
    side with no face (its outline there all trims)."""
    prof, strips = R['profile'][X], R['strips'][X]
    runs = [(prof[k][1], prof[k + 1][1]) for k, s in enumerate(strips) if s.get('face')]
    slots = list(R['slots'].get('side' + X) or [])
    if not runs or not slots:
        return None
    z0, z1 = min(a for a, _ in runs), max(b for _, b in runs)
    cuts = [z0] + [z for z in sorted(R['splits'].get(X) or []) if z0 < z < z1] + [z1]
    xs = tuple(R['frame']['x'])
    parts = []
    for k, (lo, hi) in enumerate(zip(cuts, cuts[1:])):
        slot = slots[min(k, len(slots) - 1)]
        fit = R['faceUV'].get('%d%s' % (slot, X)) or next(iter(R['faceUV'].values()), None)
        if fit:
            parts.append(tiling(fit, xs, (lo, hi)))
    if not parts:
        return None
    return dict(slots=slots, repeat=parts[0]['repeat'], share=[max(p['share'][k] for p in parts) for k in (0, 1)],
                tiles=[all(p['tiles'][k] for p in parts) for k in (0, 1)])


def surfaces(kind, entry):
    """Each surface of a look that a texture mapping takes, as its look draws it on its donor (the module's words): a
    wall's {faces: {A: side, B: side}} (_wall_side: None for a side with no face), a slab's {top, underside} and a
    ground look's {top, sides}, each dict(slots, repeat, share, tiles) (tiling). {} for an entry whose recipe doesn't
    hold its maps (an older catalogue's, a test's)."""
    R = entry.get('recipe') or {}
    try:
        if kind == 'wall':
            return {'faces': {X: _wall_side(R, X) for X in 'AB'}}
        if kind == 'slab':
            (cx, cy), (sx, sy) = R['measured']['centre'], R['measured']['size'][:2]
            xs, ys = (cx - sx / 2, cx + sx / 2), (cy - sy / 2, cy + sy / 2)
            return {role: dict(slots=[R['slots'][role]], **tiling(R['uv'][role], xs, ys)) for role in ('top', 'underside')}
        if kind == 'ground':
            sx, sy = entry['facts']['size'][:2]
            top = dict(slots=[R['slot']], **tiling(R['uv']['top'], (0.0, sx), (0.0, sy), placed=False))
            return {'top': top, 'sides': top}
    except (KeyError, IndexError, TypeError, ValueError):
        return {}
    return {}


def mapped_windows(kind, numbers, folder=None):
    """The surfaces of a made piece's numbers (a wall's, slab's or ground shape's) that its texture mapping lists and
    its catalogued look draws as a part of a larger texture (surfaces: a texture that doesn't tile along an axis; a
    wall's faces when either side's does), in uv_mapping.ROLES' order: the whole texture repeats on them. [] for a look
    no catalogue holds."""
    look = numbers.get('look') if isinstance(numbers, dict) else None
    listed = ((numbers.get('mapping') or {}).get('surfaces') or {}) if isinstance(numbers, dict) else {}
    if not isinstance(look, dict) or not listed or kind not in KINDS:
        return []
    e = entry(kind, look.get('mesh'), look.get('material'), folder)
    found = surfaces(kind, e) if e else {}
    out = []
    for role in ('faces', 'top', 'underside', 'sides'):
        f = found.get(role) if role in listed else None
        sides = list(f.values()) if role == 'faces' and f else [f]
        if any(s and False in s['tiles'] for s in sides):
            out.append(role)
    return out


def forget():
    """Drop what was read and measured (the tests, and a server whose catalogues were rebuilt)."""
    with _lock:
        _catalogues.clear()
        _measured.clear()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build', help='write the catalogues (all three when none is named)')
    b.add_argument('kinds', nargs='*', choices=('walls', 'slabs', 'ground'))
    args = parser.parse_args(argv)
    names = {'walls': 'wall', 'slabs': 'slab', 'ground': 'ground'}
    for name in args.kinds or ('walls', 'slabs', 'ground'):
        script = HERE / KINDS[names[name]][2]
        print('== %s (%s)' % (name, script.name), flush=True)
        done = subprocess.run([sys.executable, '-B', str(script), 'build'])
        if done.returncode:
            return done.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
