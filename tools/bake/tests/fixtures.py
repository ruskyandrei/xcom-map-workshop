"""Records and helpers the bake tests share (review finding 58): kept here, not in a test module, so a suite that
needs one (the viewer's manager, play and output-name tests) imports no other suite's tests. What a helper needs of
tools/bake it imports when it runs, so a suite that only reads a record loads none of it."""
import contextlib
from pathlib import Path
import traceback

HERE = Path(__file__).resolve().parent
RECORDS = HERE.parents[1] / 'patch' / 'tests' / 'defaultmaps-records.txt'


def record(name):
    """The game's DefaultMaps.ini record of the map `name` (bar, templeship...), from
    tools/patch/tests/defaultmaps-records.txt."""
    for line in RECORDS.read_bytes().split(b'\n'):
        if line.startswith(name.encode() + b'\t'):
            return line.split(b'\t', 1)[1]
    raise KeyError(name)


class SharedBuild:
    """One package made from several tests' edits, each test reading back its own part: a class's tests share a build
    where their edits touch different actors and none changes what another reads back (the bake suite's time, made
    shorter by building once what the tests built one by one).

    `edits` is {name: edit}, the name saying what the edit does. `make(folder, edits)` makes the package of those edits
    in `folder` (a new folder) and returns what the tests read; `view(name, edit, made)` gives one test its part of it.
    When the shared make fails, each edit is made alone to find those that fail: each of those fails its own test, and
    the others are made together again, so one edit's failure is never read as its neighbours'."""

    def __init__(self, folder, edits, make, view=lambda name, edit, made: made):
        self.edits, self.view, self.errors, self.made = dict(edits), view, {}, None
        folder = Path(folder)
        try:
            self.made = make(folder / 'shared', self.edits)
            return
        except Exception:       # noqa: BLE001 (whatever it is, it is found edit by edit below)
            together = traceback.format_exc()
        for k, (name, edit) in enumerate(self.edits.items()):
            try:
                make(folder / ('alone-%d' % k), {name: edit})
            except Exception:   # noqa: BLE001
                self.errors[name] = 'made alone, it fails:\n' + traceback.format_exc()
        rest = {name: edit for name, edit in self.edits.items() if name not in self.errors}
        if rest:
            try:
                self.made = make(folder / 'rest', rest)
            except Exception:   # noqa: BLE001
                for name in rest:
                    self.errors[name] = 'made alone it builds, beside the others it fails:\n' + together

    @contextlib.contextmanager
    def part(self, test, name):
        """`test`'s part of the build, for its edit `name`, in a subtest named for the edit, so that every failure in
        it names the edit it checks. `test` fails at once when that edit did not apply."""
        if name not in self.edits:
            raise KeyError('no edit %r in the shared build' % name)
        if name in self.errors:
            test.fail('the edit %r did not apply in the shared build; %s' % (name, self.errors[name]))
        with test.subTest(edit=name):
            yield self.view(name, self.edits[name], self.made)


def native_build(src, variant):
    """SharedBuild's make for native_copy.build: the map `src` with the edits' build arguments (each edit a dict of
    native_copy.build's list arguments: copies, hides, assemblies...) joined in the edits' order, written as
    <folder>/<variant>.upk with its manifest beside it. It returns (the manifest, the written map read again). Two
    edits naming one actor, hidden piece or assembly interact: refused (ValueError), as they need builds of their
    own."""
    def make(folder, edits):
        import lighting_records
        import native_copy
        joined, owner = {}, {}
        for name, edit in edits.items():
            for key, values in edit.items():
                if not isinstance(values, list):
                    raise TypeError('edit %r: %s is not a list of records; only lists are joined' % (name, key))
                joined.setdefault(key, []).extend(values)
            named = ([('copy of', c['actor']) for c in edit.get('copies', [])]
                     + [('assembly', c['assembly']) for c in edit.get('copies', []) if c.get('assembly')]
                     + [('assembly', a['id']) for a in edit.get('assemblies', [])]
                     + [('hidden', h['name']) for h in edit.get('hides', [])])
            for key in set(named):
                if owner.setdefault(key, name) != name:
                    raise ValueError('the edits %r and %r both name the %s %s: they need builds of their own'
                                     % (owner[key], name, key[0], key[1]))
        manifest = native_copy.build(src, folder, variant, **joined)
        return manifest, lighting_records.Package(Path(folder) / ('%s.upk' % variant))
    return make


class NativePart:
    """One edit's part of a shared native_copy build (SharedBuild's view, with native_build's make): `edit`, `q` (the
    written map), `manifest` (the whole build's) and `nc`, the manifest's nativeCopies records that name the edit:
    its copies' sections in the build's order, its hidden pieces, assemblies, ladders, vans and building-floor
    listings, and the columns records of the fracturing pieces whose columns list its copies (a piece listing none of
    them is not in it). A columns record counts the piece's whole, so the edits a build shares are chosen so that no
    piece's columns are changed by two of them. The build's other records belong to no one edit and are not in it."""

    def __init__(self, name, edit, made):
        self.name, self.edit = name, edit
        self.manifest, self.q = made
        nc = self.manifest['nativeCopies']
        actors = {c['actor'] for c in edit.get('copies', [])}
        hidden = {h['name'] for h in edit.get('hides', [])}
        ids = ({c['assembly'] for c in edit.get('copies', []) if c.get('assembly')}
               | {a['id'] for a in edit.get('assemblies', [])})
        self.nc = dict(copies=[s for s in nc['copies'] if s['actor'] in actors],
                       hidden=[h for h in nc['hidden'] if h['name'] in hidden],
                       assemblies=[a for a in nc['assemblies'] if a['id'] in ids],
                       ladders=[x for x in nc['ladders'] if x['actor'] in actors],
                       vans=[v for v in nc['vans'] if v['assembly'] in ids],
                       floorCaches=[f for f in nc['floorCaches'] if f['copy'] in actors],
                       columns={piece: change for piece, change in nc['columns'].items()
                                if any(a['copy'] in actors for a in change['added'])})
