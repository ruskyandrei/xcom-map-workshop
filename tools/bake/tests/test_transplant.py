"""Objects of one map brought into another (transplant.py; private/plans/done/cross-map-assets-implementation-plan.md, X3).

Every check reads the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED names) and skips
without it. The oracle runs over three pairs of maps; XCOM_TRANSPLANT_RING=1 runs it over every Firaxis-cooked base
map against the next (96 pairs on Long War Rebalance, about a minute on six cores).

The oracle: an asset two maps both hold, taken from the first and renumbered for the second, must be the second's
bytes. What may differ is listed here and nothing else may:
- one cook writes a few values differently from another (transplant.cook_noise);
- the same path can hold an object of another size, or one that refers to an object the other map lacks: the
  cooker kept different things (490 and 448 objects over the ring);
- the class defaults of the level volume and its world data carry a net index of the map (12 each);
- 32 more objects differ in content (29 meshes by one reference, a section's material that one cook kept and
  another didn't; three particle modules);
- Model and Polys keep numbers in native data; they had no layout until vans (11 November 2026) and were compared
  by their properties alone. A class still without a layout (a PrefabInstance) is refused when asked for.

Skeletal meshes have their layout (the X9 families of doors and physics props): SkeletalPieces brings a door and a
physics prop of two other maps into URB_Bar and reads them back. So have fracturing meshes: FracturingPiece."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402
import native_copy  # noqa: E402
import native_fields  # noqa: E402
import package_grow  # noqa: E402
import schema as schema_module  # noqa: E402
import transplant  # noqa: E402
import typed_props  # noqa: E402
from package import Package  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
POLICE, NO_POLICE = labpaths.install_map('URB_PoliceStation')
CLIFF, NO_CLIFF = labpaths.install_map('CAbductor_Cliffside')
PAIRS = (('URB_Bar', 'URB_PoliceStation'), ('CSmallScout_DirtRoad', 'URB_TruckStop_EWI'), ('TempleShip', 'AlienBase01'))
# with fields in native data and no layout (plan X9; brushes later): compared by their properties alone, they differ
NO_LAYOUT = set()        # Model and Polys have theirs since vans (11 November 2026)
# the class defaults whose net index is the map's
MAP_NET_INDEX = {'XComLevelVolume': 'XComGame.Default__XComLevelVolume',
                 'XComWorldData': 'XComGame.Default__XComLevelVolume.XComWorldData_0'}
# over the ring: the classes with objects of other content in two maps
OTHER_CONTENT = {'StaticMesh', 'XComDestructibleActor', 'ParticleLODLevel', 'ParticleModuleSizeByDistance'}
PL = transplant.LEVEL + '.'
# two plain props of the police station the bar lacks: a lamp post (mesh, body setup, material instance, three
# textures, their four packages) and a concrete pile (an archetype with its components besides)
LAMP, PILE = 'XComLevelActor_15', 'XComLevelActor_111'
LAMP_MESH = 'parkLampPost.Meshes.ParkLampPost_B'
# a fracturing piece of the police station whose fractured mesh the bar lacks, and that names no other piece
COLUMN, COLUMN_MESH = 'XComFracLevelActor_52', 'MuseumColumn.Meshes.MuseumColumn576_FRACTURED'

_SCHEMA = None


def game_schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = schema_module.Schema(schema_module.build(BAR.parent))
    return _SCHEMA


def _oracle(pair):
    a, b = (transplant.Donor(labpaths.install_map(name)[0], game_schema()) for name in pair)
    return pair, transplant.oracle(a, b)


def check_oracle(test, pair, result, ring=False):
    for cls, row in result['classes'].items():
        where = '%s in %s and %s' % (cls, *pair)
        counted = sum(row.get(k, 0) for k in ('equal', 'cookNoise', 'size', 'differs', 'plainEqual', 'plainDiffers',
                                              'refused'))
        test.assertEqual(counted, row['objects'], where)
        test.assertNotIn('refused', row, where)
        if row.get('plainDiffers'):
            test.assertIn(cls, NO_LAYOUT | {'XComWorldData'}, where)
        if row.get('plainEqual'):
            test.assertIn(cls, native_fields.PLAIN | {'DecalComponent', 'BrushComponent', 'XComWorldData'}, where)
        if row.get('differs'):
            test.assertIn(cls, (OTHER_CONTENT if ring else set()) | {'XComLevelVolume'}, where)
    for d in result['differences']:
        if d['cls'] in MAP_NET_INDEX and d['why'] != 'size':
            test.assertEqual((d['object'], d['at']), (MAP_NET_INDEX[d['cls']], 0), pair)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Oracle(unittest.TestCase):
    def test_an_asset_of_one_map_renumbered_is_the_other_maps_bytes(self):
        total = 0
        for pair in PAIRS:
            if not all(labpaths.install_map(n)[0].exists() for n in pair):
                self.skipTest('no %s or %s in the install' % pair)
            _, result = _oracle(pair)
            check_oracle(self, pair, result)
            rows = result['classes']
            total += sum(r['objects'] for r in rows.values())
            for cls in ('StaticMesh', 'Texture2D', 'StaticMeshComponent'):
                self.assertEqual(rows[cls]['objects'], rows[cls].get('equal', 0) + rows[cls].get('cookNoise', 0)
                                 + rows[cls].get('size', 0), (pair, cls))
            for cls in ('Material', 'MaterialInstanceConstant'):
                self.assertEqual(rows[cls]['objects'], rows[cls].get('cookNoise', 0) + rows[cls].get('equal', 0))
        self.assertGreater(total, 7000)

    @unittest.skipUnless(os.environ.get('XCOM_TRANSPLANT_RING'), 'set XCOM_TRANSPLANT_RING=1 for the ring of base maps')
    def test_the_ring_of_base_maps_differs_only_by_the_known_list(self):
        import collections
        import multiprocessing
        import re
        game = BAR.parents[3]
        names = set()
        maps = game / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini'
        for line in maps.read_bytes().decode('latin-1').splitlines():
            if not line.lstrip().startswith(';'):
                names.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
        files = {p.stem.lower(): p for p in BAR.parent.glob('*.upk')}
        ring = sorted((files[n.lower()].stem for n in names if n.lower() in files
                       and struct.unpack_from('<HH', files[n.lower()].read_bytes()[:8], 4)[1] == 64), key=str.lower)
        self.assertGreater(len(ring), 50)
        with multiprocessing.get_context('spawn').Pool(min(6, os.cpu_count() or 1)) as pool:
            results = pool.map(_oracle, list(zip(ring, ring[1:] + ring[:1])))
        total = collections.Counter()
        shapes = collections.defaultdict(list)
        for pair, result in results:
            check_oracle(self, pair, result, ring=True)
            for row in result['classes'].values():
                total.update(row)
            for d in result['differences']:
                shapes[(d['cls'], d['why'])].append((pair, d))
        self.assertGreater(total['objects'], 300000)
        self.assertEqual(total['objects'], sum(total[k] for k in ('equal', 'cookNoise', 'size', 'differs',
                                                                  'plainEqual', 'plainDiffers')))
        # the shapes: a mesh's one reference (a section's material) that one cook kept and another didn't, as
        # FX_Fire_B.Fire_Rubble_Mid's, and an archetype that refers to an object the other map lacks
        meshes = [d for _, d in shapes[('StaticMesh', 'differs')]]
        self.assertTrue(all('missing' in d or d['bytes'] <= 4 for d in meshes), meshes)
        self.assertIn('FX_Fire_B.Fire_Rubble_Mid', [d['object'] for d in meshes])
        self.assertTrue(any('missing' in d for _, d in shapes[('XComDestructibleActor', 'differs')]))
        print('\nring of %d: %s' % (len(ring), dict(total)))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class SelfTransplant(unittest.TestCase):
    def test_an_object_renumbered_into_its_own_package_is_its_own_bytes(self):
        donor = transplant.Donor(BAR, game_schema())
        p = donor.p
        names = {name: k for k, name in reversed(list(enumerate(p.names)))}
        done, refused = 0, set()
        for i, e in enumerate(p.exports, 1):
            try:
                mine = transplant.remap(donor, i, names.__getitem__, lambda ref: ref, e['off'])
            except transplant.Refused:
                refused.add(p.cls(i))
                continue
            # a name the table holds twice reads back as its first place: none of the bar's does
            self.assertEqual(bytes(mine), donor.data(i), p.name(i))
            done += 1
        self.assertGreater(done, 13000)
        self.assertFalse({'SkeletalMesh', 'DecalComponent', 'FracturedStaticMesh', 'FracturedStaticMeshComponent'}
                         & refused)


@unittest.skipUnless(BAR and BAR.exists() and POLICE and POLICE.exists(),
                     NO_BAR if not (BAR and BAR.exists()) else NO_POLICE)
class WrittenMap(unittest.TestCase):
    """URB_Bar grown with two props of URB_PoliceStation, staged."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.donor = transplant.Donor(POLICE, game_schema())
        cls.dest = transplant.Destination(BAR)
        cls.before = dict(names=list(cls.dest.g.names), imports=len(cls.dest.g.imports),
                          net=cls.dest.g.net_objects)
        cls.roots = [cls.donor.p.by_name[PL + LAMP], cls.donor.p.by_name[PL + PILE]]
        cls.report = transplant.bring(cls.dest.g, cls.dest, cls.donor, cls.roots)
        cls.out = Path(cls.tmp.name) / 'URB_Bar.upk'
        cls.writer = cls.dest.g.write(str(cls.out))
        cls.q = Package(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_what_was_brought(self):
        r, d = self.report, self.donor.p
        by_class = {}
        for row in r['brought']:
            by_class.setdefault(row['cls'], []).append(row)
        self.assertEqual(len(by_class['XComLevelActor']), 3)            # the two actors and the pile's archetype
        self.assertEqual(sum(1 for row in by_class['XComLevelActor'] if row['staged']), 2)
        self.assertIn(LAMP_MESH, [row['object'] for row in by_class['StaticMesh']])
        self.assertEqual(len(by_class['StaticMesh']), 2)
        self.assertEqual(len(by_class['LightMapTexture2D']), 4)         # each prop's colour and direction textures
        self.assertTrue(all(row['staged'] for row in by_class['LightMapTexture2D']))
        self.assertGreaterEqual(len(by_class['Texture2D']), 5)
        self.assertEqual(r['cut'], [])
        self.assertGreater(r['reused'], 5)                              # parent materials, shared textures, packages
        # a staged actor has a name of its own under the bar's level
        for root, name in zip(self.roots, (LAMP, PILE)):
            staged = r['staged'][PL + name]
            self.assertTrue(staged.startswith(PL + 'XComLevelActor_'))
            self.assertNotIn(staged, self.dest.p.by_name)
            self.assertEqual(self.q.by_name[staged], r['mapping'][root])
        self.assertEqual(self.writer['added'], len(r['brought']))
        self.assertEqual(r['bytes'], sum(row['bytes'] for row in r['brought']))

    def test_the_maps_own_exports_are_untouched(self):
        p, q = self.dest.p, self.q
        self.assertEqual(q.names[:len(p.names)], p.names)
        self.assertEqual(q.imports[:len(p.imports)], p.imports)
        self.assertEqual(q.exports[:len(p.exports)], p.exports)
        lo = p.header['chunks'][0][0]
        end = p.header['chunks'][-1][0] + p.header['chunks'][-1][1]
        self.assertEqual(q.data[lo:end], p.data[lo:end])
        # the staged actors are in no actor list
        self.assertEqual(native_copy.level_actors(q), native_copy.level_actors(p))

    def test_each_new_export_is_its_donors_in_the_grown_maps_numbering(self):
        """Read back from the file and renumbered again by names and paths, not by what bring() planned."""
        d, q, new = self.donor, self.q, self.report['mapping']
        names = {name: k for k, name in reversed(list(enumerate(q.names)))}
        exports, imports = {}, {}
        for i in range(1, len(q.exports) + 1):
            exports.setdefault((q.cls(i), q.paths[i - 1]), i)
        for k, row in enumerate(q.imports):
            imports.setdefault((row['cls'], q.name(-k - 1)), -k - 1)
        staged = {x for x, row in zip(sorted(new), self.report['brought']) if row['staged']}

        def object_of(ref):
            if ref < 0:
                return imports[(d.p.imports[-ref - 1]['cls'], d.p.name(ref))]
            if ref in staged:
                return new[ref]
            return exports[d.key(ref)]

        nets = []
        for old, index in sorted(new.items()):
            e = q.exports[index - 1]
            theirs = q.data[e['off']:e['off'] + e['size']]
            net = None
            if old in staged:
                net_at = d.fields(old)[1]
                net = struct.unpack_from('<i', theirs, net_at)[0]
                if struct.unpack_from('<i', d.data(old), net_at)[0] > 0:
                    nets.append(net)
                else:
                    net = None
            mine = transplant.remap(d, old, names.__getitem__, object_of, e['off'], net)
            self.assertEqual(bytes(mine), theirs, d.p.name(old))
            # and it reads as its class does: its properties to their closing None, its native data to its end,
            # each bulk record in it pointing at its own payload
            f = typed_props.fields(q, index, d.schema)
            native_fields.fields(q, index, f.end)
        # a staged object's net index is the map's next, one each; an asset keeps its own
        self.assertEqual(sorted(nets), list(range(self.before['net'], self.before['net'] + len(nets))))
        self.assertEqual(q.header['gens'][0][2], self.before['net'] + len(nets))
        self.assertEqual(q.header['gens'][0][0], len(q.exports))

    def test_each_new_entry_is_its_donors_but_for_the_renumbered_fields(self):
        d, q = self.donor, self.q
        at, entries = q.header['expoff'], []
        for _ in q.exports:
            e, size = package_grow.Entry.read(q.data, at)
            entries.append(e)
            at += size
        for old, index in self.report['mapping'].items():
            mine, theirs = bytes(entries[index - 1].data), bytes(d.entry(old).data)
            self.assertEqual(len(mine), len(theirs))
            self.assertEqual(mine[24:32] + mine[40:], theirs[24:32] + theirs[40:], d.p.name(old))   # flags; the rest
            self.assertEqual(q.cls(index), d.p.cls(old))
            a, b = q.exports[index - 1], d.p.exports[old - 1]
            self.assertEqual(a['size'], b['size'])
            if b['arch']:
                self.assertEqual(q.name(a['arch']).rsplit('.', 1)[-1], d.p.name(b['arch']).rsplit('.', 1)[-1])
            row = next(r for r in self.report['brought'] if r['export'] == index)
            if not row['staged']:
                self.assertEqual(q.paths[index - 1], d.p.paths[old - 1])            # an asset keeps its path
            elif b['outer'] not in (0, d.level):
                self.assertEqual(a['name'], b['name'])                              # a component keeps its name
                self.assertEqual(a['outer'], self.report['mapping'][b['outer']])

    def test_the_names_and_imports_added_are_the_ones_the_new_exports_use(self):
        d, q = self.donor, self.q
        added = q.names[len(self.before['names']):]
        self.assertEqual(added, self.report['newNames'])
        self.assertEqual(len(set(added)), len(added))
        self.assertFalse(set(added) & set(self.before['names']))
        self.assertTrue(set(added) <= set(d.p.names))
        self.assertIn('ParkLampPost_B', added)
        donors = {(row['cls'], d.p.name(-k - 1)) for k, row in enumerate(d.p.imports)}
        for k in range(self.before['imports'], len(q.imports)):
            self.assertIn((q.imports[k]['cls'], q.name(-k - 1)), donors)
        self.assertEqual(len(q.imports) - self.before['imports'], self.report['addedImports'])

    def test_a_second_bring_finds_the_assets_the_first_brought(self):
        dest = transplant.Destination(BAR)
        lamp = self.donor.p.by_name[PL + LAMP]
        first = transplant.bring(dest.g, dest, self.donor, [lamp])
        again = transplant.bring(dest.g, dest, self.donor, [lamp])
        self.assertTrue(any(not row['staged'] for row in first['brought']))
        self.assertTrue(all(row['staged'] for row in again['brought']))
        self.assertNotEqual(first['staged'], again['staged'])
        self.assertEqual(again['newNames'], [])

    def test_an_actor_whose_closure_has_no_layout_is_refused_whole(self):
        d = self.donor
        # a prefab's instance: its native data has no layout (a volume was refused until brush components had theirs)
        prefab = next(i for i in d.p.children[d.level] if d.p.cls(i) == 'PrefabInstance')
        with self.assertRaisesRegex(transplant.Refused, 'no layout here'):
            transplant.closure(d, [prefab], transplant.Destination(BAR))
        with self.assertRaises(ValueError):
            transplant.closure(d, [d.p.by_name[LAMP_MESH]], self.dest)      # not an actor of the level


@unittest.skipUnless(BAR and BAR.exists() and POLICE and POLICE.exists(),
                     NO_BAR if not (BAR and BAR.exists()) else NO_POLICE)
class FracturingPiece(unittest.TestCase):
    """URB_Bar grown with a fracturing piece of URB_PoliceStation, staged: a museum column, whose fractured mesh the
    bar lacks. Nothing is placed and its fragment columns are the police station's still: making them for this map's
    tiles is the copier's work (plan X9)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.donor = transplant.Donor(POLICE, game_schema())
        cls.dest = transplant.Destination(BAR)
        cls.root = cls.donor.p.by_name[PL + COLUMN]
        cls.report = transplant.bring(cls.dest.g, cls.dest, cls.donor, [cls.root])
        cls.out = Path(cls.tmp.name) / 'URB_Bar.upk'
        cls.dest.g.write(str(cls.out))
        cls.q = Package(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_actor_comes_with_its_component_and_its_fractured_mesh(self):
        r, q = self.report, self.q
        rows = {}
        for row in r['brought']:
            rows.setdefault(row['cls'], []).append(row)
        self.assertEqual([(row['object'], row['staged']) for row in rows['FracturedStaticMesh']],
                         [(COLUMN_MESH, False)])
        self.assertEqual([row['staged'] for row in rows['XComFracLevelActor']], [True])
        self.assertEqual([row['staged'] for row in rows['FracturedStaticMeshComponent']], [True])
        self.assertEqual(len(rows['RB_BodySetup']), 1)
        self.assertTrue(all(row['staged'] for row in rows['LightMapTexture2D'] + rows['ShadowMapTexture2D']))
        self.assertEqual(r['cut'], [])
        self.assertNotIn(('FracturedStaticMesh', COLUMN_MESH), transplant.Destination(BAR).assets)
        staged = q.by_name[r['staged'][PL + COLUMN]]
        self.assertEqual(q.cls(staged), 'XComFracLevelActor')
        self.assertNotIn(staged, native_copy.level_actors(q))
        component, = [i for i in q.children[staged] if q.cls(i) == 'FracturedStaticMeshComponent']
        self.assertEqual(q.own(staged, 'FracturedStaticMeshComponent'), component)
        mesh = q.own(component, 'StaticMesh')
        self.assertEqual((q.cls(mesh), q.name(mesh)), ('FracturedStaticMesh', COLUMN_MESH))

    def test_the_written_map_reads_as_the_donors_objects_do(self):
        """Each new export read back from the file: its properties and native data to its last byte, and the mesh
        and the component by the readers the viewer and the baker use, with what they read in the donor."""
        import lightmap_fields
        import mesh as mesh_reader
        d, q = self.donor, self.q
        for old, index in self.report['mapping'].items():
            f = typed_props.fields(q, index, d.schema)
            native = native_fields.fields(q, index, f.end)
            mine, _ = d.fields(old)
            self.assertEqual(f.fields + native, mine, d.p.name(old))
            self.assertEqual(q.exports[index - 1]['size'], d.p.exports[old - 1]['size'])
            if q.cls(index) == 'FracturedStaticMesh':
                a, b = mesh_reader.read_mesh(d.p, old), mesh_reader.read_mesh(q, index)
                self.assertEqual((a['positions'], a['indices']), (b['positions'], b['indices']))
                self.assertEqual([q.name(s['material']) for s in b['sections']],
                                 [d.p.name(s['material']) for s in a['sections']])
                self.assertEqual(len(a['sections']), 3)
            elif q.cls(index) == 'FracturedStaticMeshComponent':
                a, b = lightmap_fields.component_fields(d.p, old), lightmap_fields.component_fields(q, index)
                for x, y in zip(a['lods'], b['lods'], strict=True):
                    self.assertEqual(x['lightmap']['type'], 2)
                    self.assertEqual(len(x['shadowMaps']), len(y['shadowMaps']))
                    for s, t in zip(x['lightmap']['slots'], y['lightmap']['slots'], strict=True):
                        self.assertEqual(bool(s['index']), bool(t['index']))
                        if t['index']:
                            self.assertEqual(t['index'], self.report['mapping'][s['index']])
                            self.assertEqual(q.cls(t['index']), 'LightMapTexture2D')

    def test_each_new_export_is_its_donors_in_the_grown_maps_numbering(self):
        d, q, new = self.donor, self.q, self.report['mapping']
        names = {name: k for k, name in reversed(list(enumerate(q.names)))}
        exports, imports = {}, {}
        for i in range(1, len(q.exports) + 1):
            exports.setdefault((q.cls(i), q.paths[i - 1]), i)
        for k, row in enumerate(q.imports):
            imports.setdefault((row['cls'], q.name(-k - 1)), -k - 1)
        staged = {x for x, row in zip(sorted(new), self.report['brought']) if row['staged']}

        def object_of(ref):
            if ref < 0:
                return imports[(d.p.imports[-ref - 1]['cls'], d.p.name(ref))]
            return new[ref] if ref in staged else exports[d.key(ref)]

        for old, index in sorted(new.items()):
            e = q.exports[index - 1]
            theirs = q.data[e['off']:e['off'] + e['size']]
            net = struct.unpack_from('<i', theirs, d.fields(old)[1])[0] if old in staged else None
            mine = transplant.remap(d, old, names.__getitem__, object_of, e['off'], net)
            self.assertEqual(bytes(mine), theirs, d.p.name(old))


OUTPOST, NO_OUTPOST = labpaths.install_map('URB_ResearchOutpost_EWI')


@unittest.skipUnless(BAR and BAR.exists() and OUTPOST and OUTPOST.exists(), NO_BAR if not (BAR and BAR.exists()) else NO_OUTPOST)
class StagedVan(unittest.TestCase):
    """A van of another map (URB_ResearchOutpost_EWI's moving van) staged with the building it takes along, and
    copied as a van of the map's own is: its building volume and floor volumes, with their brushes, list the copy's
    parts."""
    BODY = 'XComDestructibleActor_238'

    @classmethod
    def setUpClass(cls):
        from package import Package
        import library
        cls.Package = Package
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        p = Package(OUTPOST)
        van = library.level_assemblies(p)[PL + cls.BODY]
        assert van['family'] == 'van', van
        cls.members = [m.rsplit('.', 1)[-1] for m in van['members']]
        cls.volumes = [p.name(v).rsplit('.', 1)[-1] for v in transplant.van_volumes(p, [p.by_name[m] for m in van['members']])]
        home = {m: (p.effective(p.by_name[PL + m], 'Location', [0, 0, 0]), p.effective(p.by_name[PL + m], 'Rotation', [0, 0, 0]))
                for m in cls.members}
        shift = [a - b for a, b in zip([1248.0, -768.0, 4.0], home[cls.BODY][0])]
        shift = [round(v / 96) * 96 for v in shift[:2]] + [0.0]
        donor = dict(package='URB_ResearchOutpost_EWI')
        cls.copies = [dict(actor=m, donor=donor, location=[v + d for v, d in zip(home[m][0], shift)],
                           rotation=list(home[m][1]), label=m + '_copy', assembly='add:van', family='van')
                      for m in cls.members]
        cls.staged, cls.edit, cls.report = transplant.stage_edit(BAR, cls.out, dict(copies=cls.copies), schema=game_schema())
        cls.manifest = native_copy.build(cls.staged, cls.out / 'build', 'URB_BarVan', cls.edit['copies'])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_building_is_staged_with_the_parts(self):
        (row,) = self.report['donors']
        self.assertEqual(len(self.volumes), 3)                                  # the building and its two floors
        self.assertEqual(row['volumes'], self.volumes)
        self.assertEqual(sorted(row['staged']), sorted(self.members))
        brought = [b['cls'] for b in row['brought'] if b['staged']]
        for cls, least in (('XComBuildingVolume', 1), ('XComFloorVolume', 2), ('Model', 3), ('Polys', 3), ('BrushComponent', 3)):
            self.assertGreaterEqual(brought.count(cls), least, cls)
        # as a car would, its parts brought without the gate's family have no building
        apart = [dict(c, family='car') for c in self.copies]
        _, _, report = transplant.stage_edit(BAR, self.out / 'car', dict(copies=apart), schema=game_schema())
        self.assertEqual(report['donors'][0]['volumes'], [])

    def test_the_copy_has_a_building_of_its_own(self):
        q = self.Package(self.out / 'build' / 'URB_BarVan.upk')
        (van,) = self.manifest['nativeCopies']['vans']
        made = {q.by_name[r['copy']] for r in self.manifest['nativeCopies']['copies']}
        self.assertEqual(len(made), len(self.members))
        building = van['building']['export']
        self.assertEqual(q.cls(building), 'XComBuildingVolume')
        floors = q.structs(q.own(building, 'Floors'))
        self.assertEqual(len(floors), 2)
        volumes = []
        for floor in floors:
            residents = [e[('ResidentActor', 0)]['value'] for e in q.structs(floor[('m_aCachedActors', 0)]['value'])]
            self.assertTrue(residents and set(residents) <= made, residents)    # the copy's parts, nothing else
            volumes += q.refs(floor[('FloorVolumes', 0)]['value'])
        self.assertEqual(sorted(volumes), sorted(f['export'] for f in van['floorVolumes']))
        listed = set(native_copy.level_actors(native_copy.lighting.Package(self.out / 'build' / 'URB_BarVan.upk')))
        for v in [building] + volumes:
            self.assertIn(v, listed)
            model = q.own(v, 'Brush', 0)
            # a brush of its own, under it, that reads back by its layout. Its polygon list is the staged
            # original's, as a copied van of the map's own keeps its original's (the copier clones the model and
            # leaves what its native data names; the game builds nothing from a Polys)
            self.assertEqual((q.cls(model), q.exports[model - 1]['outer']), ('Model', v))
            refs = [r for r in transplant.Donor(self.out / 'build' / 'URB_BarVan.upk', game_schema()).references(model) if r > 0]
            self.assertTrue(any(q.cls(r) == 'Polys' for r in refs))
        self.assertEqual(van['dropped'], [])


HIGHWAY, NO_HIGHWAY = labpaths.install_map('URB_Highway1')
AMMO, NO_AMMO = labpaths.install_map('URB_MilitaryAmmo')


@unittest.skipUnless(BAR and BAR.exists() and HIGHWAY and HIGHWAY.exists() and AMMO and AMMO.exists(),
                     NO_BAR if not (BAR and BAR.exists()) else NO_HIGHWAY or NO_AMMO)
class LooseEnds(unittest.TestCase):
    """Two kinds of piece that name more of their home map than can come (X9's last): a piece placed by a prefab,
    whose archetype is inside the Prefab beside a building's volumes and their brushes (URB_Highway1's semi-trailer
    door), and a prop that lists the pieces it takes down with it (URB_MilitaryAmmo's barrels on a pallet)."""
    DOOR, PALLET = 'XComDestructibleActor_39', 'XComDestructibleActor_275'
    PREFAB = 'VEH_SemiTrailer_A.Prefab.PRE_SemiTrailer_Car'

    @classmethod
    def setUpClass(cls):
        from package import Package
        cls.Package = Package
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.edit = dict(copies=[
            dict(actor=cls.DOOR, donor=dict(package='URB_Highway1'), location=[1104.0, -1008.0, 0.0], rotation=[0, 0, 0]),
            dict(actor=cls.PALLET, donor=dict(package='URB_MilitaryAmmo'), location=[1300.0, -640.0, 0.0],
                 rotation=[0, 0, 0])])
        cls.staged, cls.new_edit, cls.report = transplant.stage_edit(BAR, cls.out, cls.edit, schema=game_schema())
        cls.manifest = native_copy.build(cls.staged, cls.out / 'build', 'URB_BarLoose', cls.new_edit['copies'])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_prefab_comes_as_a_shell(self):
        donor = transplant.Donor(HIGHWAY, game_schema())
        p = donor.p
        door = p.by_name[PL + self.DOOR]

        class Nowhere:
            assets = {}
        # with its whole Prefab the door would bring the archetypes of the trailer's volumes and their brushes
        whole = transplant.closure(donor, [door], Nowhere, shells=False)
        self.assertTrue([i for i in whole.bring if p.cls(i) == 'BrushComponent'])
        plan = transplant.closure(donor, [door], Nowhere)
        self.assertLess(len(plan.bring), len(whole.bring))
        prefab = p.by_name[self.PREFAB]
        archetype = p.exports[door - 1]['arch']
        self.assertEqual(p.exports[archetype - 1]['outer'], prefab)
        self.assertIn(prefab, plan.bring)
        self.assertIn(archetype, plan.bring)
        left = {ref for by, ref in plan.shelled}
        self.assertTrue(left and all(by == prefab for by, _ in plan.shelled))
        self.assertFalse(left & set(plan.bring))
        self.assertFalse([i for i in plan.bring if p.cls(i) in ('BrushComponent', 'XComFloorVolume', 'XComBuildingVolume')])
        self.assertEqual([c for c in plan.cut if p.cls(c[1]) != 'Emitter'], [])       # nothing of the level is lost

    def test_the_staged_map_has_the_shell_and_the_pieces_archetype(self):
        row = next(d for d in self.report['donors'] if d['map'] == 'URB_Highway1')
        self.assertEqual(row['shelled'], [self.PREFAB])
        q = self.Package(self.staged)
        prefab = q.by_name[self.PREFAB]
        staged = q.by_name[PL + row['staged'][self.DOOR]]
        archetype = q.exports[staged - 1]['arch']
        self.assertEqual(q.exports[archetype - 1]['outer'], prefab)
        # the shell reads back, and what its lists still name is the archetype brought
        named = [r for r in transplant.Donor(self.staged, game_schema()).references(prefab) if r > 0]
        self.assertIn(archetype, named)
        self.assertTrue(all(q.exports[r - 1]['outer'] in (0, prefab) or r in (q.exports[prefab - 1]['outer'],) or
                            q.cls(r) != 'BrushComponent' for r in named))

    def test_a_prop_comes_without_the_list_of_what_it_takes_down(self):
        row = next(d for d in self.report['donors'] if d['map'] == 'URB_MilitaryAmmo')
        self.assertEqual([(c['by'], c['cls']) for c in row['cut']], [(PL + self.PALLET, 'XComDestructibleActor')])
        q = self.Package(self.out / 'build' / 'URB_BarLoose.upk')
        record = next(r for r in self.manifest['nativeCopies']['copies'] if r['actor'] == row['staged'][self.PALLET])
        copy = q.by_name[record['copy']]
        raw = q.own(copy, 'AffectedChildren')
        # the copy lists nothing: no entry left pointing at nothing
        self.assertTrue(raw is None or struct.unpack_from('<i', raw)[0] == 0, raw)
        self.assertIn(copy, set(native_copy.level_actors(q)))


@unittest.skipUnless(BAR and BAR.exists() and POLICE and POLICE.exists(),
                     NO_BAR if not (BAR and BAR.exists()) else NO_POLICE)
class StagedAssembly(unittest.TestCase):
    """An assembly of another map (a Police Station car: its body, glass and parts) staged and copied as one (X9):
    its parts keep their references to each other, which a part brought alone loses."""
    AT = [1250.0, -800.0, 0.0]

    @classmethod
    def setUpClass(cls):
        from package import Package
        import library
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        p = Package(POLICE)
        found = library.level_assemblies(p)
        car = min((a for a in found.values() if a['family'] == 'car' and len(a['members']) >= 3),
                  key=lambda a: a['pivot'])
        cls.members = [m.rsplit('.', 1)[-1] for m in car['members']]
        cls.body = car['pivot'].rsplit('.', 1)[-1]
        cls.glass = p.name(p.effective(p.by_name[car['pivot']], 'HidingPartner', 0)).rsplit('.', 1)[-1]
        home = {m: (p.effective(p.by_name[PL + m], 'Location', [0, 0, 0]), p.effective(p.by_name[PL + m], 'Rotation', [0, 0, 0]))
                for m in cls.members}
        shift = [a - b for a, b in zip(cls.AT, home[cls.body][0])]
        donor = dict(package='URB_PoliceStation')
        cls.copies = [dict(actor=m, donor=donor, location=[v + d for v, d in zip(home[m][0], shift)],
                           rotation=list(home[m][1]), label=m + '_copy', assembly='add:car', family='car')
                      for m in cls.members]
        cls.staged, cls.edit, cls.report = transplant.stage_edit(BAR, cls.out / 'whole', dict(copies=cls.copies),
                                                                 schema=game_schema())
        cls.manifest = native_copy.build(cls.staged, cls.out / 'build', 'URB_BarCar', cls.edit['copies'])
        cls.Package = Package

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_parts_staged_together_keep_their_links(self):
        (donor,) = self.report['donors']
        self.assertEqual((donor['pieces'], sorted(donor['staged'])), (len(self.members), sorted(self.members)))
        q = self.Package(self.staged)
        body, glass = (q.by_name[PL + donor['staged'][n]] for n in (self.body, self.glass))
        self.assertEqual(q.effective(body, 'HidingPartner', 0), glass)
        # nothing of the car itself is cut: only what its glass lists of the pieces beside it at home
        inside = {PL + m for m in self.members}
        self.assertFalse([c for c in donor['cut'] if c['object'] in inside], donor['cut'])

    def test_a_part_brought_alone_loses_them(self):
        alone = [dict(c, assembly=None, family=None) for c in self.copies]
        staged, _, report = transplant.stage_edit(BAR, self.out / 'apart', dict(copies=alone), schema=game_schema())
        (donor,) = report['donors']
        q = self.Package(staged)
        self.assertEqual(q.effective(q.by_name[PL + donor['staged'][self.body]], 'HidingPartner', 0), 0)
        self.assertIn(PL + self.glass, {c['object'] for c in donor['cut']})
        # the baked textures the parts share are brought once all the same
        textures = [b['object'] for b in donor['brought'] if b['cls'] in transplant.BAKED_TEXTURES]
        self.assertEqual(len(textures), len(set(textures)))

    def test_the_copy_is_a_car_of_its_own(self):
        from scene_metadata import fragment_breaks
        q = self.Package(self.out / 'build' / 'URB_BarCar.upk')
        records = {r['actor']: r for r in self.manifest['nativeCopies']['copies']}
        staged = self.report['donors'][0]['staged']
        made = {m: q.by_name[records[staged[m]]['copy']] for m in self.members}
        self.assertEqual({r.get('family') for r in records.values()}, {'car'})
        self.assertEqual(len({r['assembly'] for r in records.values()}), 1)
        # the body hides with the glass of this copy, and the glass's columns break this copy's parts
        self.assertEqual(q.effective(made[self.body], 'HidingPartner', 0), made[self.glass])
        breaks = set(fragment_breaks(q, [made[self.glass]]).get(made[self.glass], []))
        self.assertTrue(breaks and breaks <= set(made.values()), breaks)
        self.assertIn(made[self.body], breaks)
        listed = set(native_copy.level_actors(q))
        self.assertTrue(set(made.values()) <= listed)
        self.assertFalse({q.by_name[PL + staged[m]] for m in self.members} & listed)      # the staged car: unlisted


@unittest.skipUnless(BAR and BAR.exists() and POLICE and POLICE.exists(),
                     NO_BAR if not (BAR and BAR.exists()) else NO_POLICE)
class StagedCopy(unittest.TestCase):
    """A native edit with a foreign copy: staged by stage_edit, then made by native_copy.py as any copy is (X4)."""
    SPOT, OWN = [-1155.0, -1874.4, 0.0], [-900.0, -1874.4, 0.0]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.edit = dict(copies=[
            dict(actor=LAMP, donor=dict(package='urb_policestation', sha256=transplant.sha256(POLICE)),
                 location=cls.SPOT, rotation=[0, 16384, 0], label='lamp'),
            dict(actor=LAMP, donor=dict(package='URB_PoliceStation'), location=[-1155.0, -1500.0, 0.0],
                 rotation=[0, 0, 0], label='lamp again'),
            dict(actor='XComLevelActor_37', location=cls.OWN, rotation=[0, 0, 0], label='the bar\'s own')])
        cls.staged, cls.new_edit, cls.report = transplant.stage_edit(BAR, cls.out, cls.edit, schema=game_schema())
        cls.manifest = native_copy.build(cls.staged, cls.out / 'build', 'URB_BarStaged', cls.new_edit['copies'])
        cls.q = native_copy.lighting.Package(cls.out / 'build' / 'URB_BarStaged.upk')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_edit_comes_back_naming_the_staged_actor(self):
        lamp, again, own = self.new_edit['copies']
        donor = self.report['donors'][0]
        self.assertEqual((donor['map'], donor['pieces'], donor['cut']), ('URB_PoliceStation', 1, []))    # staged once
        self.assertEqual(self.report['foreignPieces'], 1)
        staged = donor['staged'][LAMP]
        self.assertEqual((lamp['actor'], again['actor']), (staged, staged))
        self.assertTrue(lamp['staged'] and again['staged'])
        self.assertEqual(lamp['donor']['actor'], LAMP)
        self.assertEqual((lamp['location'], lamp['rotation'], lamp['label']), (self.SPOT, [0, 16384, 0], 'lamp'))
        self.assertEqual(own, self.edit['copies'][2])
        self.assertEqual(self.edit['copies'][0]['actor'], LAMP)                # the edit given is not changed
        self.assertEqual(self.staged, self.out / 'staged' / 'URB_Bar.upk')
        self.assertTrue((self.out / 'transplant.json').is_file())
        self.assertTrue((self.out / 'staged' / 'tfc-folder.txt').is_file())    # it reads the game's texture caches
        self.assertEqual(donor['sha256'], transplant.sha256(POLICE))

    def test_the_copier_makes_a_staged_actors_copy_as_it_makes_one_of_the_maps_own(self):
        import lightmap_fields
        q = self.q
        staged = q.by_name[PL + self.new_edit['copies'][0]['actor']]
        listed = set(native_copy.level_actors(q))
        self.assertNotIn(staged, listed)                                        # staged: in no actor list
        records = self.manifest['nativeCopies']['copies']
        self.assertEqual(len(records), 3)
        for record, spot in zip(records, (self.SPOT, [-1155.0, -1500.0, 0.0], self.OWN)):
            copy = q.by_name[record['copy']]
            self.assertIn(copy, listed)
            self.assertEqual([round(v, 1) for v in q.own(copy, 'Location')], spot)
            # in the tiles (seeds, a rebuild volume) when it collides; the police station's lamp collides with nothing
            # (bCollideActors off), so its copies seed no tiles (native_copy.collides, F-93)
            if native_copy.collides(q, copy):
                self.assertGreater(record['tiles']['volume']['export'], 0)
            else:
                self.assertIsNone(record['tiles'])
        self.assertEqual([r['tiles'] is not None for r in records], [False, False, True])
        self.assertEqual(q.own(q.by_name[records[0]['copy']], 'Rotation'), [0, 16384, 0])
        # each lamp copy draws the police station's mesh and reads the staged actor's baked textures, which name the
        # shared cache (a quick build: the home map's light)
        def component(actor):
            return next(i for i in q.children[actor] if q.cls(i) == 'StaticMeshComponent')
        home = lightmap_fields.component_fields(q, component(staged))['lods'][0]['lightmap']
        self.assertEqual(home['type'], 2)
        for record in records[:2]:
            c = component(q.by_name[record['copy']])
            self.assertEqual(q.name(q.own(c, 'StaticMesh')), LAMP_MESH)
            mine = lightmap_fields.component_fields(q, c)['lods'][0]['lightmap']
            self.assertEqual([s['index'] for s in mine['slots']], [s['index'] for s in home['slots']])
        # read from the staged map, which finds the game's caches: the reader checks each mip lies inside the cache
        staged_map = native_copy.lighting.Package(self.staged)
        for slot in home['slots']:
            if slot['index'] > 0:
                self.assertEqual(q.cls(slot['index']), 'LightMapTexture2D')
                self.assertEqual(lightmap_fields.texture_fields(staged_map, slot['index'])['cache'], 'Lighting')

    def test_an_edit_with_no_foreign_copy_is_given_back_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            edit = dict(copies=[self.edit['copies'][2]])
            staged, new_edit, report = transplant.stage_edit(BAR, d, edit)
            self.assertEqual((staged, new_edit, report['donors']), (BAR, edit, []))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_a_missing_or_changed_donor_is_said(self):
        def stage(**donor):
            actor = donor.pop('actor', LAMP)
            with tempfile.TemporaryDirectory() as d:
                transplant.stage_edit(BAR, d, [dict(actor=actor, donor=donor, location=self.SPOT)],
                                      schema=game_schema())
        for code, donor in (('no-donor', dict(package='URB_NoSuchMap')),
                            ('donor-changed', dict(package='URB_PoliceStation', sha256='0' * 64)),
                            ('donor-changed', dict(package='URB_PoliceStation', actor='XComLevelActor_99999'))):
            with self.assertRaises(transplant.DonorError) as raised:
                stage(**donor)
            self.assertEqual(raised.exception.code, code)


ROAD, NO_ROAD = labpaths.install_map('CSmallScout_DirtRoad')
# pieces with a skeletal mesh the bar lacks: the small scout's door (an alien door: its mesh with sockets, physics
# asset, animation set and tree, sounds, materials that change over time) and a corpse of the police station (a
# physics prop: its archetype, mesh and material)
DOOR, DOOR_MESH = 'XComInteractiveLevelActor_0', 'AlienDoors.Meshes.AlienDoor_Scout_ANIM'
CORPSE, CORPSE_MESH = 'KAsset_23', 'CHH_GenericCorpse_MOD.Meshes.SM_GenericCorpse'


@unittest.skipUnless(all(m and m.exists() for m in (BAR, POLICE, ROAD)), NO_BAR or NO_POLICE or NO_ROAD
                     or 'a map of the install is missing')
class SkeletalPieces(unittest.TestCase):
    """URB_Bar grown with a door of CSmallScout_DirtRoad and a physics prop of URB_PoliceStation, staged (X9: the
    skeletal mesh's layout, native_fields.py)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dest = transplant.Destination(BAR)
        cls.net = cls.dest.g.net_objects
        cls.brought = []
        for path, actor in ((ROAD, DOOR), (POLICE, CORPSE)):
            donor = transplant.Donor(path, game_schema())
            root = donor.p.by_name[PL + actor]
            cls.brought.append((donor, root, transplant.bring(cls.dest.g, cls.dest, donor, [root])))
        cls.out = Path(cls.tmp.name) / 'URB_Bar.upk'
        cls.writer = cls.dest.g.write(str(cls.out))
        cls.q = Package(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def classes(self, report):
        by_class = {}
        for row in report['brought']:
            by_class.setdefault(row['cls'], []).append(row)
        return by_class

    def test_what_a_door_and_a_physics_prop_bring(self):
        (road, door, r), (police, corpse, k) = self.brought
        self.assertNotIn(('SkeletalMesh', DOOR_MESH), transplant.Destination(BAR).assets)
        self.assertNotIn(('SkeletalMesh', CORPSE_MESH), transplant.Destination(BAR).assets)
        got = self.classes(r)
        self.assertEqual([row['object'] for row in got['SkeletalMesh']], [DOOR_MESH])
        for cls, count in (('XComInteractiveLevelActor', 1), ('SkeletalMeshComponent', 1), ('PhysicsAsset', 1),
                           ('PhysicsAssetInstance', 1), ('RB_BodySetup', 1), ('AnimSet', 1), ('AnimTree', 1),
                           ('AnimSequence', 4), ('AnimNodeSequence', 4), ('SkeletalMeshSocket', 12),
                           ('MaterialInstanceTimeVarying', 2), ('SoundNodeWave', 2)):
            self.assertEqual(len(got[cls]), count, cls)
        self.assertTrue(got['XComInteractiveLevelActor'][0]['staged'] and got['SkeletalMeshComponent'][0]['staged'])
        self.assertFalse(any(row['staged'] for cls in ('SkeletalMesh', 'PhysicsAsset', 'AnimSet', 'AnimTree')
                             for row in got[cls]))
        self.assertEqual(r['cut'], [])
        got = self.classes(k)
        self.assertEqual([row['object'] for row in got['SkeletalMesh']], [CORPSE_MESH])
        self.assertEqual(sum(1 for row in got['KAsset'] if row['staged']), 1)       # and its archetypes
        self.assertGreaterEqual(len(got['KAsset']), 2)
        self.assertEqual(sum(1 for row in got['SkeletalMeshComponent'] if row['staged']), 1)
        self.assertEqual(k['cut'], [])
        for donor, root, report in self.brought:
            staged, = report['staged'].values()
            self.assertEqual(self.q.by_name[staged], report['mapping'][root])
            self.assertNotIn(staged, self.dest.p.by_name)
        self.assertEqual(self.writer['added'], len(r['brought']) + len(k['brought']))
        # the staged pieces are in no actor list, and the map's own exports are as they were
        self.assertEqual(native_copy.level_actors(self.q), native_copy.level_actors(self.dest.p))
        self.assertEqual(self.q.exports[:len(self.dest.p.exports)], self.dest.p.exports)

    def test_each_new_export_is_its_donors_in_the_grown_maps_numbering_and_reads_to_its_end(self):
        """Read back from the file and renumbered again by names and paths, not by what bring() planned."""
        q = self.q
        names = {name: k for k, name in reversed(list(enumerate(q.names)))}
        exports, imports = {}, {}
        for i in range(1, len(q.exports) + 1):
            exports.setdefault((q.cls(i), q.paths[i - 1]), i)
        for k, row in enumerate(q.imports):
            imports.setdefault((row['cls'], q.name(-k - 1)), -k - 1)
        nets, meshes = [], 0
        for d, root, report in self.brought:
            new = report['mapping']
            staged = {x for x, row in zip(sorted(new), report['brought']) if row['staged']}

            def object_of(ref):
                if ref < 0:
                    return imports[(d.p.imports[-ref - 1]['cls'], d.p.name(ref))]
                if ref in staged:
                    return new[ref]
                return exports[d.key(ref)]

            for old, index in sorted(new.items()):
                e = q.exports[index - 1]
                theirs = q.data[e['off']:e['off'] + e['size']]
                net = None
                if old in staged:
                    net_at = d.fields(old)[1]
                    if struct.unpack_from('<i', d.data(old), net_at)[0] > 0:
                        net = struct.unpack_from('<i', theirs, net_at)[0]
                        nets.append(net)
                mine = transplant.remap(d, old, names.__getitem__, object_of, e['off'], net)
                self.assertEqual(bytes(mine), theirs, d.p.name(old))
                # it reads as its class does: its properties to their closing None, its native data to its end
                f = typed_props.fields(q, index, d.schema)
                native = native_fields.fields(q, index, f.end)
                if q.cls(index) != 'SkeletalMesh':
                    continue
                meshes += 1
                # the mesh in the grown map: its bones and materials by name are the donor's, and its bulk record
                # points at its own place in this file
                theirs_native = d.fields(old)[0][len(f.fields):]
                self.assertEqual([k for _, k in native], [k for _, k in theirs_native])
                was = d.p.exports[old - 1]
                for (at, kind), (at_d, _) in zip(native, theirs_native):
                    self.assertEqual(at, at_d)
                    a, = struct.unpack_from('<i', q.data, e['off'] + at)
                    b, = struct.unpack_from('<i', d.p.data, was['off'] + at)
                    if kind == 'name':
                        self.assertEqual(q.names[a], d.p.names[b])
                    elif kind == 'object':
                        self.assertEqual(q.name(a) if a else None, d.p.name(b) if b else None)
                    elif kind == 'bulk':
                        self.assertEqual(struct.unpack_from('<i', q.data, e['off'] + at + 12)[0], e['off'] + at + 16)
                self.assertGreater(sum(1 for _, k in native if k == 'name'), 1)
                self.assertGreater(sum(1 for _, k in native if k == 'object'), 1)
        self.assertEqual(meshes, 2)
        self.assertEqual(sorted(nets), list(range(self.net, self.net + len(nets))))
        self.assertEqual(q.header['gens'][0][0], len(q.exports))

    def test_the_viewer_draws_the_brought_meshes_as_it_draws_the_donors(self):
        import skeletal
        for (d, root, report), mesh in zip(self.brought, (DOOR_MESH, CORPSE_MESH)):
            mine = skeletal.read_skeletal(self.q, self.q.by_name[mesh])
            theirs = skeletal.read_skeletal(d.p, d.p.by_name[mesh])
            for key in ('positions', 'indices', 'joints', 'weights', 'bounds'):
                self.assertEqual(mine[key], theirs[key], (mesh, key))
            self.assertEqual([b['name'] for b in mine['bones']], [b['name'] for b in theirs['bones']])
            self.assertEqual([self.q.name(s['material']) for s in mine['sections']],
                             [d.p.name(s['material']) for s in theirs['sections']])


@unittest.skipUnless(BAR and POLICE and CLIFF, NO_BAR or NO_POLICE or NO_CLIFF)
class FreshLight(unittest.TestCase):
    """A baked build with pieces of other maps (X8; EXP-37's two props where they were played): each is lit from
    nothing where it stands. One real bake, about a minute."""
    WALL = 'XComLevelActor_106'      # CAbductor_Cliffside's alien wall: it has a shadow map of its map's dominant light

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        edit = dict(copies=[
            dict(actor=LAMP, donor=dict(package='URB_PoliceStation'), location=[1300.0, -640.0, 0.0], rotation=[0, 0, 0]),
            dict(actor=cls.WALL, donor=dict(package='CAbductor_Cliffside'), location=[1150.0, -900.0, 0.0],
                 rotation=[0, 0, 0])])
        cls.staged, cls.edit, _ = transplant.stage_edit(BAR, cls.out, edit, schema=game_schema())
        cls.manifest = native_copy.build(cls.staged, cls.out / 'baked', 'URB_BarFresh', cls.edit['copies'], bake=True,
                                         cache='URB_BarFresh_Lighting', receivers_near=600.0)
        cls.q = native_copy.lighting.Package(cls.out / 'baked' / 'URB_BarFresh.upk')
        cls.relit = json.loads((cls.out / 'baked' / 'URB_BarFresh.relight.json').read_text(encoding='utf-8'))
        cls.records = cls.manifest['nativeCopies']['copies']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def component(self, actor):
        return next(i for i in self.q.children[actor] if self.q.cls(i) == 'StaticMeshComponent')

    def test_the_relit_textures_name_the_variants_own_cache(self):
        """Output names plan 4: the Build's cache name, <Map>_Lighting, added to the grown map's table, is what every
        texture the relight moved names (number 0), read back by a fresh reader; the textures it left keep theirs."""
        q, cache = self.q, 'URB_BarFresh_Lighting'
        self.assertEqual(self.manifest['cache'], cache)
        self.assertTrue((self.out / 'baked' / f'{cache}.tfc').is_file())
        moved = {e['what'].split(' of ', 1)[1].split(':')[0] for e in self.manifest['edits'] if e['what'].startswith('cache name of ')}
        self.assertTrue(moved)
        for path in moved:
            self.assertEqual(q.effective(q.by_name[path], 'TextureFileCacheName'), cache, path)
        others = [n for n in q.by_name if n.split('.')[-1].startswith('NormalizedAverageColor') and n not in moved]
        self.assertTrue(any(q.effective(q.by_name[n], 'TextureFileCacheName') == 'Lighting' for n in others))

    def test_a_copys_lightmap_lists_this_maps_lights_alone(self):
        import native_lights
        q = self.q
        mine = {bytes(v).hex() for e in native_lights.source_registry(q).values() for v in e['guids'].values()}
        for record, c in zip(self.records, self.edit['copies']):
            self.assertTrue(record['staged'])
            self.assertEqual(record['lighting'], 'fresh')
            copy = self.component(q.by_name[record['copy']])
            home = self.component(q.by_name[PL + c['actor']])
            listed = native_copy.lighting.component_record(q, copy)['lods'][0]['lightmap']['lightGuids']
            theirs = native_copy.lighting.component_record(q, home)['lods'][0]['lightmap']['lightGuids']
            self.assertTrue(listed)
            self.assertLessEqual(set(listed), mine)                 # every light it lists is a light of this map
            self.assertFalse(set(theirs) & mine)                    # the staged piece's are its home map's
            self.assertFalse(set(listed) & set(theirs))

    def test_a_copys_shadow_map_names_this_maps_dominant_light(self):
        import shadowmaps
        q = self.q
        dominant, = [g for g, l in shadowmaps.dominant_lights(q).items() if l['enabled']]
        lamp, wall = (self.component(q.by_name[r['copy']]) for r in self.records)
        self.assertEqual(shadowmaps.shadow_maps(q, lamp), [])       # the lamp post had none in its home map
        maps = shadowmaps.shadow_maps(q, wall)
        self.assertEqual([m['guid'] for m in maps], [dominant])
        home = shadowmaps.shadow_maps(q, self.component(q.by_name[PL + self.edit['copies'][1]['actor']]))
        self.assertNotEqual(home[0]['guid'], dominant)
        self.assertNotEqual(home[0]['texture'], maps[0]['texture'])     # its own texture, not the staged piece's
        # the whole field was written, lit and shadowed parts both
        report, = [s for s in self.relit['shadowMaps'] if s.get('fresh')]
        self.assertEqual(report['component'], q.name(wall))
        self.assertGreater(report['texelsWritten'], 500)
        self.assertTrue(report['darker'] and report['lighter'])

    def test_the_copies_are_lit_from_nothing_where_they_stand(self):
        q = self.q
        fresh = {r['component']: r for r in self.relit['components'] if r['fresh']}
        self.assertEqual(sorted(fresh), sorted(q.name(self.component(q.by_name[r['copy']])) for r in self.records))
        for r in fresh.values():
            self.assertIsNone(r['copyOf'])
            self.assertEqual(r['lights']['matched'], r['lights']['guids'])
            self.assertGreater(r['texels']['ours'], 100)
            # in a car park at night: some light, and nothing like the alien ship's
            self.assertTrue(0.02 < r['flatLight']['relitMedian'] < 1.0, r['flatLight'])
        self.assertEqual(self.relit['nativeCopies'], [])
        self.assertEqual(sorted(c['staged'] for c in self.relit['foreignCopies']),
                         sorted(c['actor'] for c in self.edit['copies']))

    def test_the_staged_pieces_are_in_no_scene(self):
        staged = [c['actor'] for c in self.edit['copies']]
        # the edit is the two copies where they stand: the staged pieces, far off where their home maps have them,
        # are no casters, no part of the edit and no receivers
        self.assertEqual(len(self.relit['editBoxes']), 2)
        for box in self.relit['editBoxes']:
            self.assertTrue(700 < box[0] < 1500 and -1100 < box[2] < -500, box)
        self.assertEqual(self.relit['edit']['removeCasters'], [])
        named = [r['component'] for r in self.relit['components']] + self.relit['unchanged'] + self.relit['unreached'] \
            + [s['component'] for s in self.relit['skipped']]
        self.assertFalse([n for n in named if n.split('.')[2] in staged])
        self.assertEqual(self.relit['failed'], 0)
        # the map's own pieces around them took their shadows
        self.assertGreater(len(self.relit['components']), 2)


if __name__ == '__main__':
    unittest.main()
