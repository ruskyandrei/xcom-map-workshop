"""Records and helpers the bake tests share (review finding 58): kept here, not in a test module, so that no test
imports another. The records more than one suite shares come from their one home, tools/tests/shared_fixtures.py.
What a helper needs of tools/bake it imports when it runs."""
import contextlib
from pathlib import Path
import struct
import sys
import tempfile
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tests'))
from shared_fixtures import minimal_mesh, record  # noqa: E402,F401  (the records every suite shares)
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import props as legacy_props  # noqa: E402

# a package's tagged properties and a mesh's convex hull, read back (test_cover_blocks' and test_frac_walls')
RAW = {'Vector': '3f', 'Plane': '4f', 'Box': '6fB'}


def tagged(p, b, at=0):
    """[(name, kind, value)] of tagged properties in b from `at` up to None: a struct of plain fields as a list, of
    tagged fields as tagged(); an array as (count, raw elements)."""
    out = []
    while True:
        name = p.names[struct.unpack_from('<i', b, at)[0]]
        if name == 'None':
            return out
        kind = p.names[struct.unpack_from('<i', b, at + 8)[0]]
        size = struct.unpack_from('<i', b, at + 16)[0]
        at += 24
        if kind == 'StructProperty':
            sname = p.names[struct.unpack_from('<i', b, at)[0]]
            at += 8
            body = b[at:at + size]
            out.append((name, sname, list(struct.unpack('<' + RAW[sname], body)) if sname in RAW else tagged(p, body)))
        elif kind == 'ArrayProperty':
            out.append((name, kind, (struct.unpack_from('<i', b, at)[0], b[at + 4:at + size])))
        elif kind == 'BoolProperty':
            out.append((name, kind, b[at]))
            at += 1
            continue
        else:
            out.append((name, kind, b[at:at + size]))
        at += size


def hull(p, body_setup):
    """An RB_BodySetup's (version, [its tagged property names], its one convex element's fields as convex_hull gives
    them)."""
    props = tagged(p, export_bytes(p, body_setup), legacy_props.props_start(p.data, p.exports[body_setup - 1], p.names)
                   - p.exports[body_setup - 1]['off'])
    named = {n: v for n, _, v in props}
    version = struct.unpack('<i', named['PreCachedPhysDataVersion'])[0]
    [(top, _, (count, elems))] = named['AggGeom']
    assert top == 'ConvexElems' and count == 1
    fmts = dict(VertexData='3f', PermutedVertexData='4f', FaceTriData='i', EdgeDirections='3f',
                FaceNormalDirections='3f', FacePlaneData='4f')
    out = {}
    for name, kind, value in tagged(p, elems):
        if name == 'ElemBox':
            out[name] = [value[:3], value[3:6], value[6]]
        else:
            n, raw = value
            size = struct.calcsize('<' + fmts[name])
            rows = [list(struct.unpack_from('<' + fmts[name], raw, size * k)) for k in range(n)]
            out[name] = [r[0] for r in rows] if fmts[name] == 'i' else rows
    return version, [n for n, _, _ in props], out


def export_bytes(p, i):
    e = p.exports[i - 1]
    return bytes(p.data[e['off']:e['off'] + e['size']])


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
    native_copy.BuildState's list inputs: copies, hides, assemblies...) joined in the edits' order, written as
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
        manifest = native_copy.build(native_copy.BuildState(src, folder, variant, **joined))
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


class ModuleBuilds:
    """The shared builds (SharedBuild) that several classes of one test module read: `specs` is {build: a function
    returning its (edits, make, view)}. Each is made the first time a class asks for it (get), so that a class run
    alone makes only the build it reads, and kept until the module's tests end (close, from the module's
    tearDownModule)."""

    def __init__(self, **specs):
        self.specs, self.made, self.tmp = specs, {}, None

    def get(self, name):
        if name not in self.made:
            if self.tmp is None:
                self.tmp = tempfile.TemporaryDirectory()
            edits, make, view = self.specs[name]()
            self.made[name] = SharedBuild(Path(self.tmp.name) / name, edits, make, view)
        return self.made[name]

    def close(self):
        self.made.clear()
        if self.tmp is not None:
            self.tmp.cleanup()
            self.tmp = None


class SharedPart:
    """A test class (before unittest.TestCase in its bases) whose tests read the edit EDIT of the shared build BUILD of
    BUILDS (the module's ModuleBuilds), each test in part()."""
    BUILDS = BUILD = EDIT = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.build = cls.BUILDS.get(cls.BUILD)

    def part(self, edit=None):
        """This test's part of the shared build, for the class's edit or `edit`, in a subtest named for it
        (SharedBuild.part)."""
        return self.build.part(self, edit or self.EDIT)


def copies_build(src, variant, stage=None, **options):
    """SharedBuild's make for native_copy.build when each edit is a list of copies (made walls, slabs and ground, the
    doors standing in them), so that two edits may copy one piece: the edits' copies joined in the edits' order and
    built without baking, with `options` (native_copy.BuildState's other inputs), as <folder>/<variant>.upk. `stage`,
    for pieces of another map, is transplant.stage_edit's call (src, folder, edit) -> (the staged map, the staged
    edit, its report), made on the joined copies first; the build is then made from the staged map in <folder>/build.
    The edits are told apart by where their copies stand in the build's sections (native_copy keeps the copies'
    order, an assembly's together), so two edits naming one assembly are refused (ValueError). Returns a dict:
    manifest, q (the written map read again), copies (those built: the staged ones where staged), report (the
    staging's, or None) and spans ({edit: (its first copy, its count)})."""
    def make(folder, edits):
        import lighting_records
        import native_copy
        joined, spans, owner = [], {}, {}
        for name, copies in edits.items():
            if not isinstance(copies, list):
                raise TypeError('edit %r is not a list of copies' % name)
            for a in {c['assembly'] for c in copies if c.get('assembly')}:
                if owner.setdefault(a, name) != name:
                    raise ValueError('the edits %r and %r both name the assembly %s: they need builds of their own'
                                     % (owner[a], name, a))
            spans[name] = (len(joined), len(copies))
            joined += [dict(c) for c in copies]
        folder, out, report = Path(folder), Path(folder), None
        if stage:
            folder.mkdir(parents=True)
            src_map, edit, report = stage(src, folder, dict(copies=joined))
            joined, out = edit['copies'], folder / 'build'
        else:
            src_map = src
        manifest = native_copy.build(native_copy.BuildState(src_map, out, variant, joined, **options))
        return dict(manifest=manifest, q=lighting_records.Package(out / ('%s.upk' % variant)), copies=joined,
                    report=report, spans=spans)
    return make


class CopiesPart:
    """One edit's part of a shared copies_build (SharedBuild's view): `edit` (its copies as asked), `copies` (as
    built: the staged ones where staged), `q` (the written map), `manifest` (the whole build's), `report` (the
    staging's, whole) and `m`, the manifest with its nativeCopies cut to the records that name the edit's copies:
    their sections, made pieces' records (generatedWalls), door listings, made walls' building floors, neighbour
    listings with either side its own, and flags on its copies (pieceFlags' onCopies). The build's records of the
    whole map (the made cursors, the hidden pieces, the columns...) belong to no one edit and are not in `m`: a test
    that reads one reads `manifest`, in a build where no other edit makes one."""
    LISTS = (('generatedWalls', ('copy',)), ('doorListings', ('copy',)), ('madeWallFloors', ('wall',)),
             ('neighbourListings', ('wall', 'other')))

    def __init__(self, name, edit, made):
        first, count = made['spans'][name]
        self.name, self.edit = name, edit
        self.manifest, self.q, self.report = made['manifest'], made['q'], made['report']
        self.copies = made['copies'][first:first + count]
        nc = self.manifest['nativeCopies']
        sections = nc['copies'][first:first + count]
        if [s['actor'] for s in sections] != [c['actor'] for c in self.copies]:
            raise AssertionError('the build\'s sections from %d are %s, not the edit %r\'s copies %s'
                                 % (first, [s['actor'] for s in sections], name, [c['actor'] for c in self.copies]))
        mine = {s['copy'].split('.')[-1] for s in sections}
        part = dict(copies=sections)
        for key, fields in self.LISTS:
            if key in nc:
                part[key] = [r for r in nc[key] if any(r[f] in mine for f in fields)]
        if 'pieceFlags' in nc:
            part['pieceFlags'] = dict(onCopies=[r for r in nc['pieceFlags']['onCopies'] if r['copy'] in mine])
        self.m = dict(self.manifest, nativeCopies=part)


LANES = ('effects', 'sounds', 'flares')


def lanes_build(src, variant, stage=None):
    """SharedBuild's make for native_copy.build's lanes (effects, sounds, flares: each a dict of moves, deletes, copies
    and values): each edit a dict of lanes, and no two edits edit one lane, so that a lane's records are one edit's
    (ValueError). The edits' lanes are built together, with no copies of pieces, as <folder>/<variant>.upk. `stage`,
    for lanes copying another map's actors, is transplant.stage_edit (src, folder, edit) -> (the staged map, the staged
    edit, its report), made on the joined edit first; the build is then made from the staged map in <folder>/build.
    Returns a dict: manifest, q (the written map read again), edit (the lanes as built: the staged edit where staged)
    and report (the staging's, or None)."""
    def make(folder, edits):
        import lighting_records
        import native_copy
        joined, owner = {}, {}
        for name, lanes in edits.items():
            for lane, value in lanes.items():
                if lane not in LANES:
                    raise ValueError('edit %r: %s is not a lane (%s)' % (name, lane, ', '.join(LANES)))
                if owner.setdefault(lane, name) != name:
                    raise ValueError('the edits %r and %r both edit the %s lane: a shared build takes one edit a lane'
                                     % (owner[lane], name, lane))
                joined[lane] = value
        folder, out, report, src_map = Path(folder), Path(folder), None, src
        edit = dict(copies=[], **joined)
        if stage:
            folder.mkdir(parents=True)
            src_map, edit, report = stage(src, folder, edit)
            out = folder / 'build'
        manifest = native_copy.build(native_copy.BuildState(src_map, out, variant, edit['copies'],
                                                            **{lane: edit[lane] for lane in joined}))
        return dict(manifest=manifest, q=lighting_records.Package(out / ('%s.upk' % variant)), edit=edit, report=report)
    return make


class LanesPart:
    """One edit's part of a shared lanes_build (SharedBuild's view): `edit` (its lanes as given), `staged` (its lanes
    as built: the staged edit's where staged), `q` (the written map), `manifest` (the whole build's), `section` (the
    manifest's records of its lanes, and of the floors' emitter lists with the effects lane), `report` (the staging's,
    whole) and `donors`, the report's rows of the maps its lanes' copies come from."""

    def __init__(self, name, edit, made):
        self.name, self.edit = name, edit
        self.manifest, self.q, self.report = made['manifest'], made['q'], made['report']
        nc = self.manifest['nativeCopies']
        keys = list(edit) + (['floorEmitters'] if 'effects' in edit else [])
        self.section = {k: nc[k] for k in keys if k in nc}
        self.staged = {lane: made['edit'][lane] for lane in edit}
        maps = {c['donor']['package'] for lane in edit.values() for c in lane.get('copies', []) if c.get('donor')}
        self.donors = [r for r in (self.report or {}).get('donors', []) if r['map'] in maps]
