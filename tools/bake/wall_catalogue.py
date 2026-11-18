"""The walls' catalogue (custom geometry plan, stage M4 item 3): every wall-shaped fracturing mesh of the install, as a
look the editor offers, written to tools/bake/looks/walls.json (checked in; the page reads it for the picker, the Build
reads a look's recipe from it when it holds that mesh at that measurer's version, else measures the donor itself).

The walls are the 344 of the wall-look audit (research/evidence/wall-look-audit-2026-11-18.json: each mesh, the maps it
is placed in and how often, its setting, and the placing it was measured on). For each, the placing to copy is that
placing when it stands at scale 1 (its actor's DrawScale and DrawScale3D and its component's Scale and Scale3D all
1), else the first placing at scale 1 in its maps (by name), else that placing as it is (its facts then say its
`scale`; the recipe is in the mesh's own units, and the Build stands the made copy at scale 1). It is measured there by
tools/bake/wall_measure.py (`measure`: its recipe, warnings and facts) and given the twin check (`twin`: the wall made
at its donor's length and measured again; 'ok', or the keys that differ in words). A wall the generator can't make
faithfully stays in, with its warning (warn, don't block).

An entry: {mesh, map, actor, maps {map: placings}, name (words from the mesh's name), setting (the audit's), lwrOnly,
facts, warnings, twin, recipe}. lwrOnly is true when the donor's map is not one Firaxis cooked (its package's
licensee is not 64: Long War Rebalance's own packages are licensee 0); the rule is written in the file's `about`.
The file is LF, the looks sorted by mesh, one look a line, the same bytes from the same install (a test checks it).

  python -B tools/bake/wall_catalogue.py build [--out <file>] [--only <mesh> ...] [--audit <file>]
  python -B tools/bake/wall_catalogue.py check       (a fresh build gives the checked-in file's bytes)

Nothing is written into the game's folders.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(REPO / 'tools' / folder))
sys.path.insert(0, str(HERE))
import wall_measure  # noqa: E402

AUDIT = REPO / 'research' / 'evidence' / 'wall-look-audit-2026-11-18.json'
OUT = HERE / 'looks' / 'walls.json'
FIRAXIS = 64            # the licensee Firaxis cooked the base game's packages with
ABOUT = ("The walls' catalogue (custom geometry plan, M4): every wall-shaped fracturing mesh of the install (the 344 of "
         "research/evidence/wall-look-audit-2026-11-18.json) as a look, measured by tools/bake/wall_measure.py at the "
         "placing to copy (map, actor: at scale 1 where the mesh has one) and given its twin check (the wall made at its "
         "donor's length and measured again: 'ok', or what differs). Written by python -B tools/bake/wall_catalogue.py "
         "build. lwrOnly: true when the donor's map is not one Firaxis cooked (its package's licensee is not 64; Long War "
         "Rebalance's own packages are licensee 0, and none of them holds a fracturing piece); every donor map of this "
         "install is Firaxis's, so no look needs Long War Rebalance.")
SUFFIX = re.compile(r'_(FRACTURED|FRAC|FRC)$', re.I)


def readable(mesh):
    """Words for a look from its mesh's name: URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED -> 'Bar Int Wall B'."""
    short = SUFFIX.sub('', mesh.split('.')[-1])
    short = re.sub(r'^(URB|BLDG|URb)_', '', short)
    words = re.sub(r'(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Z][a-z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', short.replace('_', ' '))
    return ' '.join(words.split())


def scale_of(p, actor):
    """The scale a placed piece stands at: its actor's DrawScale and DrawScale3D and its component's Scale and
    Scale3D, as (x, y, z)."""
    comp = p.own(actor, 'FracturedStaticMeshComponent')
    s = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    if comp:
        s = [a * b * p.effective(comp, 'Scale', 1) for a, b in zip(s, p.effective(comp, 'Scale3D', [1, 1, 1]))]
    return tuple(float(v) for v in s)


def unscaled(p, actor):
    return all(abs(v - 1.0) < 1e-6 for v in scale_of(p, actor))


class Maps:
    """The install's map packages, opened once each (the few most recently used kept open)."""

    def __init__(self, keep=4):
        self.open, self.keep = {}, keep

    def get(self, name):
        import labpaths
        from package import Package
        if name in self.open:
            self.open[name] = self.open.pop(name)
            return self.open[name]
        path = labpaths.lwr_cooked(name + '.upk')
        if path is None or not Path(path).exists():
            raise FileNotFoundError('%s.upk is not in the configured install (python tools/viewer/viewer.py settings)' % name)
        p = Package(path)
        self.open[name] = p
        while len(self.open) > self.keep:
            self.open.pop(next(iter(self.open)))
        return p


def placing(maps, mesh, wall):
    """(map, actor name) of the placing to copy for the audit's `wall` (the module's docstring)."""
    first = (wall['measuredOn'], wall['actor'])
    p = maps.get(first[0])
    actor = p.by_name.get('TheWorld.PersistentLevel.' + first[1])
    if actor and unscaled(p, actor):
        return first
    for name in sorted(wall['placed']):
        q = maps.get(name)
        index = q.by_name.get(mesh)
        if not index:
            continue
        for a, _, _ in wall_measure.placed(q, index):
            if unscaled(q, a):
                return name, q.name(a).split('.')[-1]
    return first


def twin_words(result):
    """'ok', or what the twin check found different, in words."""
    if result['ok']:
        return 'ok'
    return '; '.join('%s: %s' % (r['key'], r['note']) for r in result['rows'] if not r['ok'])


def look_of(maps, mesh, wall):
    """The catalogue's entry of the audit's wall `wall` (its mesh `mesh`)."""
    map_name, actor = placing(maps, mesh, wall)
    p = maps.get(map_name)
    entry = wall_measure.measure(p, actor)
    scale = scale_of(p, p.by_name['TheWorld.PersistentLevel.' + actor])
    if any(abs(v - 1.0) > 1e-6 for v in scale):
        # (no placing of it at scale 1: the made copy stands at 1, its recipe in the mesh's own units)
        entry['facts']['scale'] = [round(v, 4) for v in scale]
    try:
        twin = twin_words(wall_measure.twin(entry['recipe']))
    except Exception as err:        # noqa: BLE001 (the generator failing on a donor is the twin's finding, not fatal)
        twin = 'the generator failed: %s: %s' % (type(err).__name__, err)
    return dict(mesh=mesh, map=map_name, actor=actor, maps=dict(sorted(wall['placed'].items())), name=readable(mesh),
                setting=wall['setting'], lwrOnly=p.header['lic'] != FIRAXIS, facts=entry['facts'],
                warnings=entry['warnings'], twin=twin, recipe=entry['recipe'])


def build(audit=AUDIT, only=None, progress=None):
    """The catalogue (a dict) of the audit's walls (`only`: those meshes)."""
    walls = json.loads(Path(audit).read_text(encoding='utf-8'))['walls']
    names = sorted(m for m in walls if not only or m in only)
    maps = Maps()
    looks = []
    # by the map each was measured on, so each map is opened once
    for k, mesh in enumerate(sorted(names, key=lambda m: (walls[m]['measuredOn'], m))):
        t0 = time.time()
        looks.append(look_of(maps, mesh, walls[mesh]))
        if progress:
            progress('%3d/%d %-70s %-5s %.1fs' % (k + 1, len(names), mesh, 'ok' if looks[-1]['twin'] == 'ok' else 'DIFF',
                                                 time.time() - t0))
    looks.sort(key=lambda e: e['mesh'])
    return dict(about=ABOUT, measure=wall_measure.VERSION, built='<game>', looks=looks)


def text(catalogue):
    """The catalogue's file: LF, its keys in order, one look a line."""
    head = ',\n'.join(' %s: %s' % (json.dumps(k), json.dumps(catalogue[k], ensure_ascii=False))
                      for k in ('about', 'measure', 'built'))
    rows = ',\n'.join('  ' + json.dumps(e, ensure_ascii=False, separators=(',', ':')) for e in catalogue['looks'])
    return '{\n%s,\n "looks": [\n%s\n ]\n}\n' % (head, rows)


def write(catalogue, path=OUT):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(catalogue), encoding='utf-8', newline='\n')
    return path


def summary(catalogue):
    """Counts: the looks, those whose twin is 'ok', by verdict."""
    from collections import Counter
    looks = catalogue['looks']
    by = Counter((e['facts']['verdict'], e['twin'] == 'ok') for e in looks)
    verdicts = sorted({v for v, _ in by})
    return dict(looks=len(looks), twinOk=sum(e['twin'] == 'ok' for e in looks),
                byVerdict={v: dict(looks=by[v, True] + by[v, False], twinOk=by[v, True]) for v in verdicts},
                warned=sum(bool(e['warnings']) for e in looks), lwrOnly=sum(e['lwrOnly'] for e in looks))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('action', choices=('build', 'check'))
    a.add_argument('--out', type=Path, default=OUT)
    a.add_argument('--audit', type=Path, default=AUDIT)
    a.add_argument('--only', nargs='*', help='only these meshes (a partial catalogue: not for checking in)')
    a.add_argument('--quiet', action='store_true')
    args = a.parse_args()
    progress = None if args.quiet else (lambda line: print(line, flush=True))
    catalogue = build(args.audit, set(args.only) if args.only else None, progress)
    if args.action == 'check':
        same = OUT.exists() and OUT.read_text(encoding='utf-8') == text(catalogue)
        print('the same bytes as %s' % OUT.name if same else '%s differs from a fresh build' % OUT.name)
        raise SystemExit(0 if same else 1)
    path = write(catalogue, args.out)
    print(json.dumps(summary(catalogue), indent=1))
    print('wrote %s' % path)


if __name__ == '__main__':
    main()
