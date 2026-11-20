"""Objects of one cooked map brought into another, renumbered (private/plans/done/cross-map-assets-implementation-plan.md,
3.3 and X3).

A cooked map holds its art as forced exports, and an object's bytes are the same in every map that holds it apart
from the numbers that are the package's own: name-table indices, object indices, and the absolute offsets of bulk
data that lies in the export. So an object another map has can be had here by copying its export with those numbers
rewritten, and everything it refers to that this map lacks with it.

  donor = Donor(<donor map.upk>, schema)        a package behind three methods: data, entry, fields
  remap(donor, index, name_of, object_of, place)    one export's bytes in another package's numbering
  closure(donor, roots, dest)                   what a set of the donor's actors needs: brought, reused, cut
  bring(g, dest, donor, roots)                  the closure appended to the map being grown; returns the report
  stage_edit(map, out, edit, cooked)            a native edit's foreign copies staged: the staged map, the edit
                                                rewritten for native_copy.py, and transplant.json

`roots` are actors of the donor's level. Each comes in as a **staged actor**: the actor and everything under it, and
the baked textures they read, as new exports under this map's level with names of their own, not in the Level's actor
list (the state a deleted piece is in). The assets they reference come in under their own packages, with their own
names, entries and net indices, unless this map has them already. A reference to another object of the donor's level
is cut (set to none) and listed. Nothing is placed: tools/bake/native_copy.py clones a staged actor as it clones one of
the map's own.

The fields of an export are found by its property types (tools/upk/typed_props.py, from the game's script packages)
and, for the classes that keep numbers in native data, by their layouts (tools/upk/native_fields.py). An export with
an array the schema can't type, or native data with no layout, is refused: nothing is guessed.

A native edit (the editor's native-edit.json: {copies: [...]}) names a foreign copy by `donor` ({package, [sha256]})
beside its `actor`, the actor's name in the donor's level. stage_edit stages each distinct (donor, actor) once and
gives the edit back with those copies' `actor` the staged actor's name and `staged: true`, which native_copy.py takes
as it takes any copy.

  python -B tools/bake/transplant.py <map.upk> <out dir> --edit native-edit.json [--cooked <CookedPCConsole>]
  python -B tools/bake/transplant.py <map.upk> <out dir> --stage DONOR ACTOR [--stage DONOR ACTOR ...]

Both write <out>/staged/<map>.upk and <out>/transplant.json; --edit also <out>/native-edit.staged.json. The donors
are looked for in --cooked, by default the folder the map is in.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import native_fields  # noqa: E402
import package_grow  # noqa: E402
import schema as schema_module  # noqa: E402
import typed_props  # noqa: E402
from package import Package, link_caches  # noqa: E402

WORLD = 'TheWorld'
LEVEL = 'TheWorld.PersistentLevel'
NAME, OBJECT, BULK = 'name', 'object', 'bulk'
# a level's baked textures lie at the package's top, not under the level; a staged actor's come with it
BAKED_TEXTURES = ('LightMapTexture2D', 'ShadowMapTexture2D')
# arrays the script packages don't type, in objects that are never brought (an editor-only actor's list)
UNTYPED_OK = ('DependentOn',)
# A piece placed by a prefab has its archetype inside the Prefab asset, beside the archetypes of everything else the
# prefab places (a building's props, its floor and building volumes with their brushes). The Prefab comes as a
# shell: itself and the archetypes the pieces brought use, its lists' other entries set to none. The game makes
# nothing from a Prefab at run time (the editor does, when a prefab is placed).
SHELLS = ('Prefab',)


class Refused(ValueError):
    """An object can't be brought: it has a field this module can't find."""


class Donor:
    """A cooked package as a source of objects. The three methods the transplant needs (data, entry, fields) are what
    another kind of donor (objects made here, plan 3.5) would give."""

    def __init__(self, path, schema):
        self.path = Path(path)
        self.p = p = Package(path)
        self.schema = schema
        self.entries, at = [], p.header['expoff']
        for _ in p.exports:
            e, size = package_grow.Entry.read(p.data, at)
            self.entries.append(e)
            at += size
        self._fields, self._top, self._subtree = {}, {}, {}
        self.assets = {}
        for i in range(1, len(p.exports) + 1):
            if self.is_asset(i):
                self.assets.setdefault((p.cls(i), p.paths[i - 1]), i)
        self.level = p.by_name.get(LEVEL)

    # -- the three methods ---------------------------------------------------------------------------------------
    def data(self, index):
        e = self.p.exports[index - 1]
        return self.p.data[e['off']:e['off'] + e['size']]

    def entry(self, index):
        return self.entries[index - 1]

    def fields(self, index):
        """(fields [(offset, kind)], net index offset) of export `index`: every name, object reference and bulk
        record of its data. Refused when one can't be found."""
        if index not in self._fields:
            p = self.p
            try:
                f = typed_props.fields(p, index, self.schema)
                bad = [u for u in f.untyped if u[0].rsplit('.', 1)[-1] not in UNTYPED_OK]
                if bad:
                    raise Refused('%s (%s): the array %s has no element type in the script packages'
                                  % (p.name(index), p.cls(index), bad[0][0]))
                native = native_fields.fields(p, index, f.end)
            except (typed_props.WalkError, native_fields.NativeError) as error:
                raise Refused(str(error)) from None
            self._fields[index] = (f.fields + native, f.net_index)
        return self._fields[index]

    # -- what the closure asks ------------------------------------------------------------------------------------
    def top(self, index):
        if index not in self._top:
            i = index
            while self.p.exports[i - 1]['outer'] > 0:
                i = self.p.exports[i - 1]['outer']
            self._top[index] = i
        return self._top[index]

    def is_asset(self, index):
        """Under (or itself) a top-level package that is not the level's: the game's art, as against the map's own
        objects."""
        t = self.top(index)
        return self.p.cls(t) == 'Package' and self.p.exports[t - 1]['name'] != WORLD

    def key(self, index):
        return self.p.cls(index), self.p.paths[index - 1]

    def subtree(self, index):
        out = [index]
        for c in self.p.children.get(index, []):
            out += self.subtree(c)
        return out

    def references(self, index):
        """The objects export `index` refers to: its class, super, outer and archetype, then each reference of its
        data (0 left out)."""
        e = self.p.exports[index - 1]
        refs = [e['cls'], e['sup'], e['outer'], e['arch']]
        data = self.data(index)
        refs += [struct.unpack_from('<i', data, at)[0] for at, kind in self.fields(index)[0] if kind == OBJECT]
        return [r for r in refs if r]


def remap(donor, index, name_of, object_of, place, net_index=None):
    """The data of the donor's export `index` in another package's numbering: `name_of(text)` the name-table index
    there, `object_of(reference)` the object index there, `place` the absolute offset the data will lie at.
    `net_index` replaces its net index when given. Returns a bytearray."""
    data = bytearray(donor.data(index))
    names = donor.p.names
    found, net_at = donor.fields(index)
    for at, kind in found:
        if kind == NAME:
            struct.pack_into('<i', data, at, name_of(names[struct.unpack_from('<i', data, at)[0]]))
        elif kind == OBJECT:
            value = struct.unpack_from('<i', data, at)[0]
            if value:
                struct.pack_into('<i', data, at, object_of(value))
        elif kind == BULK and not struct.unpack_from('<i', data, at)[0] & native_fields.STORED_ELSEWHERE:
            struct.pack_into('<i', data, at + 12, place + at + 16)
    if net_index is not None:
        struct.pack_into('<i', data, net_at, net_index)
    return data


class Destination:
    """The map being grown: `g` (package_grow.Grower over it) and what it holds already."""

    def __init__(self, path, g=None):
        self.path = Path(path)
        self.g = g or package_grow.Grower(str(path))
        self.p = p = Package(path)
        self.assets = {}
        for i, e in enumerate(p.exports, 1):
            top = i
            while p.exports[top - 1]['outer'] > 0:
                top = p.exports[top - 1]['outer']
            if p.cls(top) == 'Package' and p.exports[top - 1]['name'] != WORLD:
                self.assets.setdefault((p.cls(i), p.paths[i - 1]), i)
        self.level = p.by_name.get(LEVEL)
        if self.level is None:
            raise ValueError('%s has no persistent level' % self.path.name)
        self._imports = {}

    def import_of(self, donor, ref, object_of):
        """The import of this map for the donor's import `ref` (negative): found by class, name and outer, else
        added, its outer first."""
        # kept by the donor's file, or by the donor itself (held, so alive): never by id(), which a later donor takes
        # once an earlier one is freed, and would then be given that map's imports for its own (F-121)
        path = getattr(donor, 'path', None)
        known = self._imports.setdefault(str(Path(path).resolve()).casefold() if path else donor, {})
        if ref not in known:
            i = donor.p.imports[-ref - 1]
            outer = object_of(i['outer']) if i['outer'] else 0
            known[ref] = self.g.add_import(i['cpkg'], i['cls'], outer, i['name'])
        return known[ref]


class Plan:
    """What closure() found: `bring` (the donor's exports to copy, in its table's order), `staged` (those of them that
    are the level's: the actors, what lies under them, their baked textures), `reuse` {donor export: this map's},
    `cut` [(donor export, the level object it refers to)], `sizes` [(donor export, its size, this map's size)] for
    reused objects of another size, `shelled` [(a Prefab brought as a shell, what its lists named that is not
    brought)]."""

    def __init__(self):
        self.bring, self.staged, self.reuse, self.cut, self.sizes, self.shelled = [], set(), {}, [], [], []


def closure(donor, roots, dest, shared=None, shells=True):
    """`shared`: baked textures of the donor an earlier bring staged here already ({donor export: this map's}).
    `shells` off follows a Prefab's lists as any object's (SHELLS): what the library asks to learn whether a piece
    could come with its whole Prefab."""
    p = donor.p
    shared = shared or {}
    plan = Plan()
    own = set()
    for root in roots:
        if p.exports[root - 1]['outer'] != donor.level:
            raise ValueError('%s is not an actor of the donor\'s level' % p.name(root))
        own.update(donor.subtree(root))
    taken, cut, queue, shelled = set(), set(), [], []

    def want(ref, by):
        if ref <= 0 or ref in taken or ref in plan.reuse:
            return
        if ref in shared:
            plan.reuse[ref] = shared[ref]
            return
        if donor.is_asset(ref):
            here = dest.assets.get(donor.key(ref))
            if here is not None:
                plan.reuse[ref] = here
                theirs, mine = p.exports[ref - 1]['size'], dest.g.entries[here - 1].size
                if theirs != mine:
                    plan.sizes.append((ref, theirs, mine))
                return
        elif ref in own or (p.cls(ref) in BAKED_TEXTURES and p.exports[ref - 1]['outer'] == 0):
            plan.staged.add(ref)
        else:
            if (by, ref) not in cut:
                cut.add((by, ref))
                plan.cut.append((by, ref))
            return
        taken.add(ref)
        queue.append(ref)

    for root in roots:
        want(root, 0)
    while queue:
        index = queue.pop()
        e = p.exports[index - 1]
        shell = shells and p.cls(index) in SHELLS and donor.is_asset(index)
        its_own = (e['cls'], e['sup'], e['outer'], e['arch'])
        for ref in donor.references(index):
            if ref == donor.level and ref == e['outer']:
                continue                # a staged actor's outer: this map's level
            if shell and ref > 0 and ref not in its_own:
                shelled.append((index, ref))    # what a Prefab's lists name: not followed
                continue
            while ref < 0:              # an import can lie under an export: the maps hold XComGame as a package
                ref = p.imports[-ref - 1]['outer']
            want(ref, index)
    plan.bring = sorted(taken)
    plan.shelled = [(by, ref) for by, ref in dict.fromkeys(shelled) if ref not in taken and ref not in plan.reuse]
    return plan


def van_volumes(p, members):
    """The building and floor volumes of the van whose parts `members` (export indices of the package `p`'s level)
    are: [building, floor volume, ...] of the level's XComBuildingVolume more than half of whose residents they are
    (native_copy.van_buildings' rule, which finds the staged building again by it), or []."""
    level = p.by_name.get(LEVEL)
    members = set(members)
    for i in p.children.get(level, []) if level else []:
        if p.cls(i) != 'XComBuildingVolume':
            continue
        residents, volumes = set(), []
        for floor in p.structs(p.own(i, 'Floors')):
            cached = floor.get(('m_aCachedActors', 0), {}).get('value')
            residents |= {e[('ResidentActor', 0)]['value'] for e in p.structs(cached)} if cached else set()
            listed = floor.get(('FloorVolumes', 0), {}).get('value')
            volumes += [v for v in (p.refs(listed) if listed else []) if v > 0]
        if residents and len(residents & members) * 2 > len(residents):
            return [i] + volumes
    return []


def bring(g, dest, donor, roots, shared=None):
    """The donor's actors `roots` (export indices) staged in the map `g` grows (`dest`, a Destination over the same
    map), with what they need. Roots brought together keep their references to each other; a reference to an actor
    brought by another call is cut. `shared` ({}) carries the donor's baked textures from one call to the next, so
    pieces brought one by one share them as they do at home. Returns dict(staged {donor actor path: staged actor path}, mapping {donor export: new
    export}, brought, reused, cut, sizes, bytes, newNames, addedImports)."""
    p = donor.p
    plan = closure(donor, roots, dest, shared)
    names_before, imports_before, start = len(g.names), len(g.imports), g.next_offset()
    new = {d: len(g.entries) + 1 + k for k, d in enumerate(plan.bring)}
    cut = {ref for _, ref in plan.cut} | {ref for _, ref in plan.shelled}

    def object_of(ref):
        if ref < 0:
            return dest.import_of(donor, ref, object_of)
        if ref in new:
            return new[ref]
        if ref in plan.reuse:
            return plan.reuse[ref]
        if ref in cut:
            return 0
        raise ValueError('%s is neither brought, reused nor cut' % p.name(ref))

    for d in plan.bring:
        e = p.exports[d - 1]
        staged = d in plan.staged
        net = None
        if staged:
            _, net_at = donor.fields(d)
            if struct.unpack_from('<i', donor.data(d), net_at)[0] > 0:
                net = g.net_objects
                g.net_objects += 1
        data = remap(donor, d, g.name, object_of, g.next_offset(), net)
        entry = package_grow.Entry(donor.entry(d).data)
        outer = dest.level if staged and e['outer'] == donor.level else object_of(e['outer']) if e['outer'] else 0
        name_index = g.name(p.names[entry.name_index])
        number = entry.name_number
        if staged and outer in (0, dest.level):
            number = g.unused_number(name_index)
        for at, value in ((0, object_of(e['cls']) if e['cls'] else 0), (4, object_of(e['sup']) if e['sup'] else 0),
                          (8, outer), (12, name_index), (16, number),
                          (20, object_of(e['arch']) if e['arch'] else 0)):
            entry.put('<i', at, value)
        if g.adopt_export(entry.data, bytes(data)) != new[d]:
            raise ValueError('the brought exports did not get the planned indices')
    limit = len(g.entries)
    for d in plan.bring:
        e = g.entries[new[d] - 1]
        for at in (0, 4, 8, 20):
            if not -len(g.imports) <= e.get('<i', at) <= limit:
                raise ValueError('%s: an entry reference outside the package' % p.name(d))

    def path(index):
        e = g.entries[index - 1]
        own = g.name_of(e.name_index, e.name_number)
        return (path(e.outer) + '.' if e.outer > 0 else '') + own

    for d in plan.bring:
        if d not in plan.staged:
            dest.assets.setdefault(donor.key(d), new[d])    # a later bring finds them here
        elif shared is not None and p.cls(d) in BAKED_TEXTURES and p.exports[d - 1]['outer'] == 0:
            shared[d] = new[d]
    return dict(
        staged={p.name(root): path(new[root]) for root in roots},
        mapping=new,
        brought=[dict(cls=p.cls(d), object=p.name(d), export=new[d], staged=d in plan.staged,
                      bytes=p.exports[d - 1]['size']) for d in plan.bring],
        reused=len(plan.reuse),
        cut=[dict(by=p.name(by) if by else None, object=p.name(ref), cls=p.cls(ref)) for by, ref in plan.cut],
        shelled=sorted({p.name(by) for by, _ in plan.shelled}),
        sizes=[dict(object=p.name(ref), cls=p.cls(ref), donor=a, here=b) for ref, a, b in plan.sizes],
        bytes=g.next_offset() - start,
        newNames=g.names[names_before:], addedImports=len(g.imports) - imports_before)


# -- a native edit's foreign copies ------------------------------------------------------------------------------------
class DonorError(ValueError):
    """A donor map is missing, or is not the file the edit was made against. `code` is no-donor or donor-changed."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def donor_file(cooked, package):
    """The donor map `package` (a name, any case) in the folder `cooked`."""
    wanted = package.lower() + '.upk'
    for path in Path(cooked).iterdir():
        if path.name.lower() == wanted:
            return path
    raise DonorError('no-donor', 'the map %s, which a piece comes from, is not in %s' % (package, cooked))


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


# the native edit's lanes of effects, sounds and lens flares (the effects and sounds plan, Part D): a copy there names
# its source actor by `source`, and one from another map carries its `donor` (stage FX4; flares since FX6b)
LANES = ('effects', 'sounds', 'flares')


def stage_edit(map_path, out, edit, cooked=None, schema=None):
    """The foreign copies of the native edit `edit` ({copies: [...]}, or the list itself) staged in a copy of the map.
    Returns (map to give native_copy.py, the edit for it, report). With no foreign copy nothing is written: the map
    and the edit come back as they are, the report with no donors. Otherwise <out>/staged/<map>.upk is written (it
    reads the game's texture caches through package.link_caches), and the report is also <out>/transplant.json:
    dict(map, staged, donors [dict(map, file, sha256, pieces, effects (the lanes' actors, lens flares among them),
    flares (how many of those are lens flares), staged {actor: staged actor}, objectsBrought,
    objectsReused, cut, sizes, bytes, brought)], foreignPieces, writer). The effects, sounds and flares lanes' copies with a
    donor (LANES) are staged as pieces are, each actor alone and once however many copies name it, and come back
    naming the staged actor as their `source`."""
    map_path, out = Path(map_path), Path(out)
    cooked = Path(cooked) if cooked else map_path.parent
    copies = edit['copies'] if isinstance(edit, dict) else edit
    lights = (edit.get('lights') or {}) if isinstance(edit, dict) else {}
    lanes = {k: edit[k] for k in LANES if isinstance(edit.get(k), dict)} if isinstance(edit, dict) else {}
    foreign_area = {}
    for op in lights.get('area') or []:
        if donor := op.get('donor'):
            foreign_area.setdefault(donor['package'].lower(), []).append(op)
    wanted, effects_wanted = {}, {}
    for c in copies:
        if c.get('donor'):
            wanted.setdefault(c['donor']['package'].lower(), []).append(c)
    flare_sources = set()       # (donor, actor) of the flares lane's copies, for the report's count
    for lane, ops in lanes.items():
        for c in ops.get('copies') or []:
            if c.get('donor'):
                effects_wanted.setdefault(c['donor']['package'].lower(), []).append(c)
                if lane == 'flares':
                    flare_sources.add((c['donor']['package'].lower(), c['source']))
    report = dict(map=str(map_path), staged=None, donors=[], foreignPieces=0)
    if foreign_area.keys() - wanted.keys():
        raise DonorError('no-donor', 'a generated area light has no piece from its donor in the edit')
    if not wanted and not effects_wanted:
        return map_path, edit, report
    if schema is None:
        schema = schema_module.Schema(schema_module.build(cooked))
    dest = Destination(map_path)
    names, area_names = {}, {}
    for key in sorted(set(wanted) | set(effects_wanted)):
        group, effect_group = wanted.get(key, []), effects_wanted.get(key, [])
        path = donor_file(cooked, (group or effect_group)[0]['donor']['package'])
        digest = sha256(path)
        for c in group + effect_group:
            if c['donor'].get('sha256') and c['donor']['sha256'].lower() != digest:
                raise DonorError('donor-changed', 'the map %s is not the file the piece %s was taken from'
                                 % (path.name, c.get('actor') or c['source']))
        donor = Donor(path, schema)
        actors = list(dict.fromkeys(c['actor'] for c in group))
        effect_actors = [a for a in dict.fromkeys(c['source'] for c in effect_group) if a not in actors]
        for actor in actors + effect_actors:
            if donor.p.by_name.get(LEVEL + '.' + actor) is None:
                raise DonorError('donor-changed', '%s has no actor %s' % (path.name, actor))
        # the parts of one assembly (a car's body, glass and parts: copies with one `assembly`) are brought together,
        # so they keep their references to each other; any other piece is brought alone, and what it names of its
        # home map's other pieces is cut, whether or not the project brings those too
        lead = {a: a for a in actors}

        def find(a):
            while lead[a] != a:
                a = lead[a]
            return a
        by_assembly, vans = {}, set()
        for c in group:
            if c.get('assembly'):
                by_assembly.setdefault(c['assembly'], []).append(c['actor'])
                if c.get('family') == 'van':
                    vans.add(c['assembly'])
        for members in by_assembly.values():
            for m in members[1:]:
                lead[find(m)] = find(members[0])
        sets = {}
        for a in actors:
            sets.setdefault(find(a), []).append(a)
        staged, shared = {}, {}
        row = dict(map=path.stem, file=str(path), sha256=digest, pieces=len(actors), effects=len(effect_actors),
                   flares=sum(1 for a in effect_actors if (key, a) in flare_sources), staged=staged, objectsBrought=0, objectsReused=0, cut=[], sizes=[], bytes=0, brought=[], newNames=0,
                   addedImports=0, shelled=[])

        def stage_roots(roots, remap):
            r = bring(dest.g, dest, donor, roots, remap)
            row['objectsBrought'] += len(r['brought'])
            row['objectsReused'] += r['reused']
            row['bytes'] += r['bytes']
            row['newNames'] += len(r['newNames'])
            row['addedImports'] += r['addedImports']
            for k in ('cut', 'sizes', 'brought', 'shelled'):
                row[k] += r[k]
            return {name.rsplit('.', 1)[-1]: staged_name.rsplit('.', 1)[-1]
                    for name, staged_name in r['staged'].items()}
        # a van takes its own building along: the building volume and its floor volumes, with their brushes, staged
        # with its parts (native_copy.py clones them with the van and finds them by the parts they list)
        with_van = {find(by_assembly[a][0]) for a in vans}
        row['volumes'] = []
        for lead_actor, members in sets.items():
            roots = [donor.p.by_name[LEVEL + '.' + a] for a in members]
            if lead_actor in with_van:
                volumes = van_volumes(donor.p, roots)
                if not volumes:
                    raise DonorError('donor-changed', '%s: the van %s has no building of its own in %s'
                                     % (path.name, members[0], path.stem))
                row['volumes'] += [donor.p.name(v).rsplit('.', 1)[-1] for v in volumes]
                roots += volumes
            placed = stage_roots(roots, shared)
            staged.update({a: placed[a] for a in members})
        # an effect or a sound (the lanes' copies): its actor alone, as a piece is; what it names of its home map's
        # other actors is cut (the library offers none that rides on another), its system or waves reused where this
        # map has them by path already (transplant's rule for any asset; `sizes` lists those of another size)
        for a in effect_actors:
            staged.update(stage_roots([donor.p.by_name[LEVEL + '.' + a]], shared))
        if key in foreign_area:
            world = [i for i in dest.p.children[dest.level] if dest.p.cls(i) == 'WorldInfo']
            if len(world) != 1:
                raise DonorError('area-light-owner', f'{map_path.name} must have one WorldInfo for imported area lights')
            roots, remap = {}, dict(shared)
            for op in foreign_area[key]:
                light = donor.p.by_name.get(LEVEL + '.' + op['light'])
                owner = donor.p.own(light, 'Owner', 0) if light and donor.p.cls(light) == 'GeneratedMeshAreaLight' else 0
                if op['op'] != 'copy' or op['donor'].get('sha256') != digest or not owner or donor.p.cls(owner) != 'WorldInfo':
                    raise DonorError('donor-changed', f'{path.name}: area light {op["light"]} or its WorldInfo has changed')
                roots[op['light']] = light
                remap[owner] = world[0]
            area_names[key] = row['stagedAreas'] = stage_roots(list(roots.values()), remap)
        names[key] = staged
        report['donors'].append(row)
        report['foreignPieces'] += len(actors) + len(effect_actors)
    target = out / 'staged' / map_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    report['writer'] = dest.g.write(str(target))
    link_caches(target.parent, map_path.parent)
    report['staged'] = str(target)

    def rewritten(c):
        if not c.get('donor'):
            return c
        return dict(c, actor=names[c['donor']['package'].lower()][c['actor']], staged=True,
                    donor=dict(c['donor'], actor=c['actor']))
    new_copies = [rewritten(c) for c in copies]
    new_edit = dict(edit, copies=new_copies) if isinstance(edit, dict) else new_copies

    def lane_copy(c):
        if not c.get('donor'):
            return c
        return dict(c, source=names[c['donor']['package'].lower()][c['source']], staged=True,
                    donor=dict(c['donor'], actor=c['source']))
    for k, ops in lanes.items():
        if ops.get('copies'):
            new_edit[k] = dict(ops, copies=[lane_copy(c) for c in ops['copies']])
    if area_names:
        area = [dict(op, light=area_names[op['donor']['package'].lower()][op['light']]) if op.get('donor') else op
                for op in lights['area']]
        new_edit['lights'] = dict(lights, area=area, stagedAreas=sorted(n for rows in area_names.values() for n in rows.values()))
    (out / 'transplant.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    return target, new_edit, report


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('map', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('--edit', type=Path, help='a native edit (native-edit.json) whose foreign copies to stage')
    a.add_argument('--stage', action='append', nargs=2, default=[], metavar=('DONOR', 'ACTOR'),
                   help='an actor of a donor map\'s level to stage, by the map\'s and the actor\'s names')
    a.add_argument('--cooked', type=Path, help='where the donor maps are (default: the folder of the map)')
    args = a.parse_args()
    if bool(args.edit) == bool(args.stage):
        a.error('give --edit or --stage')
    edit = json.loads(args.edit.read_text(encoding='utf-8')) if args.edit else \
        [dict(actor=actor, donor=dict(package=donor)) for donor, actor in args.stage]
    try:
        staged, new_edit, report = stage_edit(args.map, args.out, edit, args.cooked)
    except (DonorError, Refused) as error:
        sys.exit(str(error))
    if args.edit:
        (args.out / 'native-edit.staged.json').write_text(json.dumps(new_edit, indent=1) + '\n', encoding='utf-8',
                                                          newline='\n')
    for d in report['donors']:
        print('%s: %d pieces and %d effects, sounds or flares staged (%s), %d objects brought (%d bytes), %d reused, %d '
              'references cut' % (d['map'], d['pieces'], d.get('effects', 0),
                                  ', '.join('%s -> %s' % kv for kv in d['staged'].items()), d['objectsBrought'],
                                  d['bytes'], d['objectsReused'], len(d['cut'])))
    print('map: %s' % staged)


if __name__ == '__main__':
    main()
