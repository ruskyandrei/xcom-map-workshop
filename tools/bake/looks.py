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
page its list of a kind's looks: the entries with only the numbers the page draws by.

  python -B tools/bake/looks.py build [walls] [slabs] [ground]
"""
import argparse
import copy
import importlib
import json
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
    """The kind's measurer module (wall_measure, slab_measure, ground_measure)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    return importlib.import_module(KINDS[kind][1])


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
    (PAGE_RECIPE)."""
    data, _ = catalogue(kind, folder)
    out = []
    for e in data.get('looks', ()):
        row = {k: v for k, v in e.items() if k != 'recipe'}
        row['recipe'] = {k: e['recipe'][k] for k in PAGE_RECIPE[kind] if k in e.get('recipe', {})}
        out.append(row)
    return {'kind': kind, 'measure': data.get('measure'), 'looks': out}


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
