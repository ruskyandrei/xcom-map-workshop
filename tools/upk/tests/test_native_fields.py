"""The names, references and bulk records of native data (native_fields.py), against the readers each layout was
taken from, on three maps of the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED names).
Without the install those tests skip. The one reader of a mesh component's LOD records (native_fields.mesh_lods), and
the three readers that take from it, are also tested on a made-up component that needs no install."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'bake'))
sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402
import lighting_records  # noqa: E402
import lightmap_fields  # noqa: E402
import native_fields  # noqa: E402
import schema  # noqa: E402
import typed_props  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
MAPS = ('URB_Bar', 'TempleShip', 'URB_PoliceStation')
# the maps the skeletal mesh's and the decal component's layouts were found on
SKELETAL_MAPS = ('URB_Bar', 'URB_PoliceStation', 'CSmallScout_DirtRoad', 'URB_TruckStop_EWI', 'TempleShip', 'AlienBase01')
# the maps the fracturing classes are walked over, and those of them that hold such pieces (the alien maps have none)
FRACTURING_MAPS = ('URB_Bar', 'URB_PoliceStation', 'CSmallScout_DirtRoad', 'URB_TruckStop_EWI', 'TempleShip',
                   'AlienBase01')
WITH_FRACTURING = ('URB_Bar', 'URB_PoliceStation', 'CSmallScout_DirtRoad', 'URB_TruckStop_EWI')
# with native data, no layout and not plain: refused until their milestones (plan X9; brushes later still)
UNMAPPED = {'XComDebrisStaticMeshComponent', 'PrefabInstance', 'XComFracDecoComponent',
            'XComFracDebrisComponent', 'InstancedStaticMeshComponent', 'XComWorldData', 'Level', 'World',
            'XComVisGroupData', 'SeqAct_Interp', 'XComDestructionInstData', 'XComWorldDataContainer', 'ModelComponent',
            'ShadowMap1D', 'TextureMovie'}


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class NativeFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from package import Package
        cls.schema = schema.Schema(schema.build(BAR.parent))
        cls.p = Package(BAR)
        cls.ends = {}

    def native(self, index, p=None):
        p = p or self.p
        return native_fields.fields(p, index, typed_props.fields(p, index, self.schema).end)

    def values(self, index, kind):
        e = self.p.exports[index - 1]
        return [(at, struct.unpack_from('<i', self.p.data, e['off'] + at)[0])
                for at, k in self.native(index) if k == kind]

    def of(self, cls, limit=40):
        return [i for i in range(1, len(self.p.exports) + 1) if self.p.cls(i) == cls][:limit]

    def test_every_export_of_three_maps_is_mapped_plain_or_refused_by_name(self):
        from package import Package
        for name in MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            p = self.p if name == 'URB_Bar' else Package(path)
            mapped = set()
            for i in range(1, len(p.exports) + 1):
                try:
                    if self.native(i, p):
                        mapped.add(p.cls(i))
                except native_fields.Unmapped:
                    self.assertIn(p.cls(i), UNMAPPED, p.name(i))
            self.assertLessEqual({'Texture2D', 'StaticMesh', 'Material', 'MaterialInstanceConstant',
                                  'StaticMeshComponent', 'LightMapTexture2D'}, mapped, name)

    def test_a_lightmap_textures_bulk_records_are_the_fixture_writers(self):
        import lightmap_fields
        for i in self.of('LightMapTexture2D', 12) + self.of('ShadowMapTexture2D', 6):
            e = self.p.exports[i - 1]
            t = lightmap_fields.texture_fields(self.p, i)
            bulks = [e['off'] + at for at, k in self.native(i) if k == 'bulk']
            self.assertEqual(bulks[1:1 + len(t['mips'])], [m['metaOffset'] for m in t['mips']])
            cook = [e['off'] + at for at, k in self.native(i) if k == 'cook16']
            self.assertEqual(cook, [t['cacheGuidOffset']])

    def test_a_static_meshs_references_are_its_body_setup_and_section_materials(self):
        import mesh
        seen = 0
        for i in self.of('StaticMesh', 400):
            m = mesh.read_mesh(self.p, i)
            refs = [v for _, v in self.values(i, 'object')]
            if m['lods'] == 1:
                self.assertEqual(refs[1:], [s['material'] for s in m['sections']], self.p.name(i))
                seen += 1
            self.assertIn(self.p.cls(refs[0]) if refs[0] > 0 else None, ('RB_BodySetup', None))
            self.assertEqual(len(self.values(i, 'bulk')), m['lods'])
        self.assertGreater(seen, 300)

    def test_a_materials_references_are_the_textures_its_shaders_sample(self):
        import export
        for cls in ('Material', 'DecalMaterial'):
            for i in self.of(cls):
                refs = [v for _, v in self.values(i, 'object')]
                self.assertEqual([r for r in refs if r and 'Texture' in self.p.cls(r)],
                                 export.compiled_textures(self.p, i), self.p.name(i))
                e = self.p.exports[i - 1]
                self.assertEqual([at for at, k in self.native(i) if k == 'cook4'], [e['size'] - 4])

    def test_a_material_instances_names_are_its_static_parameters(self):
        import materials
        seen = 0
        for i in self.of('MaterialInstanceConstant', 200):
            e = self.p.exports[i - 1]
            names = [self.p.names[v] for _, v in self.values(i, 'name')]
            switches = materials.static_switches(self.p, i)
            self.assertLessEqual(set(switches), set(names), self.p.name(i))
            seen += bool(names)
            if not self.p.own(i, 'bHasStaticPermutationResource', False):
                self.assertEqual(self.native(i), [])
        self.assertGreater(seen, 20)

    def test_a_mesh_components_references_are_its_shadow_maps_and_lightmap_textures(self):
        import lightmap_fields
        textured = 0
        for i in self.of('StaticMeshComponent', 300):
            e = self.p.exports[i - 1]
            f = lightmap_fields.component_fields(self.p, i)
            mine = {e['off'] + at for at, _ in self.values(i, 'object')}
            for lod in f['lods']:
                for k in range(len(lod['shadowMaps'])):
                    self.assertIn(lod['shadowMapsOffset'] + 4 + 4 * k, mine)
                if lod['lightmap']['type'] == 2:
                    textured += 1
                    for s in lod['lightmap']['slots']:
                        self.assertIn(s['textureOffset'], mine)
        self.assertGreater(textured, 100)

    def test_a_skeletal_meshs_fields_are_its_materials_bone_names_and_one_bulk_record_a_lod(self):
        """Doors, physics props and skeletal actors (plan X9): every skeletal mesh of six maps reads to its end."""
        from package import FormatError, Package
        import skeletal
        seen = drawn = 0
        for name in SKELETAL_MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            p = self.p if name == 'URB_Bar' else Package(path)
            for i in range(1, len(p.exports) + 1):
                if p.cls(i) != 'SkeletalMesh':
                    continue
                e = p.exports[i - 1]
                found = self.native(i, p)                           # raises unless the walk ends at the export's end
                at = {kind: [a for a, k in found if k == kind] for kind in ('name', 'object', 'bulk')}
                self.assertEqual(len(found), sum(len(v) for v in at.values()), p.name(i))
                names = [p.names[struct.unpack_from('<i', p.data, e['off'] + a)[0]] for a in at['name']]
                refs = [struct.unpack_from('<i', p.data, e['off'] + a)[0] for a in at['object']]
                # each bone is named twice: in the reference skeleton, and in the map of names to bone numbers
                half = len(names) // 2
                self.assertEqual(len(names), 2 * half, p.name(i))
                self.assertEqual(sorted(names[:half]), sorted(names[half:]), p.name(i))
                # the materials, then a clothing asset (none in the game) for each
                self.assertEqual(len(refs) % 2, 0, p.name(i))
                materials = refs[:len(refs) // 2]
                self.assertEqual(refs[len(refs) // 2:], [0] * len(materials), p.name(i))
                for m in materials:
                    self.assertIn(p.cls(m) if m > 0 else None,
                                  ('Material', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying', None))
                # the raw point indices of each LOD: an empty record in cooked data, pointing past itself
                self.assertGreaterEqual(len(at['bulk']), 1)
                for a in at['bulk']:
                    flags, _, size, offset = struct.unpack_from('<4i', p.data, e['off'] + a)
                    self.assertEqual((size, offset), (0, e['off'] + a + 16), p.name(i))
                seen += 1
                try:
                    m = skeletal.read_skeletal(p, i)                # the viewer's reader, where it reads the mesh
                except FormatError:
                    continue
                drawn += 1
                self.assertEqual([n.lower() for n in names[:half]],
                                 [b['name'].lower() for b in m['bones']], p.name(i))
                self.assertLessEqual({s['material'] for s in m['sections']}, set(materials), p.name(i))
                self.assertEqual(len(at['bulk']), m['lods'])
                self.assertLess(at['bulk'][0], m['lod0End'] - e['off'])     # LOD 0's record is in LOD 0
        self.assertGreaterEqual(seen, 25)
        self.assertGreaterEqual(drawn, 20)

    def test_a_decal_components_references_are_the_components_it_lies_on(self):
        from package import Package
        placed = templates = 0
        for name in SKELETAL_MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            p = self.p if name == 'URB_Bar' else Package(path)
            for i in range(1, len(p.exports) + 1):
                if p.cls(i) != 'DecalComponent':
                    continue
                e = p.exports[i - 1]
                start = typed_props.fields(p, i, self.schema).end
                found = native_fields.fields(p, i, start)
                receivers = struct.unpack_from('<i', p.data, e['off'] + start)[0]
                self.assertEqual([k for _, k in found], ['object'] * receivers, p.name(i))
                for at, _ in found:
                    ref = struct.unpack_from('<i', p.data, e['off'] + at)[0]
                    self.assertTrue(p.cls(ref).endswith('Component'), (p.name(i), p.cls(ref)))
                    self.assertTrue(p.name(ref).startswith('TheWorld.PersistentLevel.'), p.name(ref))
                placed += bool(receivers)
                templates += not receivers
        self.assertGreater(placed, 150)
        self.assertGreater(templates, 10)                           # an archetype's, as a physics prop's closure holds

    def test_a_volumes_brush_reads_to_its_end(self):
        # a volume's geometry (a van's building and floor volumes go with it into another map): every brush
        # component, model and polygon list of three maps reads to its last byte
        from package import Package
        counts = {}
        for name in MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            p = self.p if name == 'URB_Bar' else Package(path)
            for i in range(1, len(p.exports) + 1):
                cls = p.cls(i)
                if cls not in ('Model', 'Polys', 'BrushComponent'):
                    continue
                found = self.native(i, p)
                counts[cls] = counts.get(cls, 0) + 1
                e = p.exports[i - 1]
                refs = [struct.unpack_from('<i', p.data, e['off'] + at)[0] for at, kind in found if kind == 'object']
                if cls == 'BrushComponent':
                    self.assertEqual(found, [])
                elif cls == 'Model':
                    # its Polys is among what it names (a level's own model has none)
                    polys = [r for r in refs if r > 0 and p.cls(r) == 'Polys']
                    self.assertLessEqual(len(polys), 1, p.name(i))
                    if p.cls(e['outer']) in ('XComBuildingVolume', 'XComFloorVolume'):
                        self.assertEqual(len(polys), 1, p.name(i))
                        self.assertEqual(p.exports[polys[0] - 1]['outer'], i)
                else:
                    self.assertEqual(sum(1 for _, kind in found if kind == 'name') % 2, 0)
        self.assertGreater(counts['Model'], 40)
        self.assertGreater(counts['Polys'], 40)
        self.assertGreater(counts['BrushComponent'], 40)

    def test_a_class_with_native_data_and_no_layout_is_refused(self):
        i = self.of('PrefabInstance', 1)[0]
        with self.assertRaises(native_fields.Unmapped):
            self.native(i)
        self.assertEqual(self.native(self.of('RB_BodySetup', 1)[0]), [])

    def test_a_bulk_record_in_the_export_points_at_its_own_payload(self):
        for i in self.of('Texture2D', 30) + self.of('SoundNodeWave', 10):
            e = self.p.exports[i - 1]
            inline = 0
            for at, _ in self.values(i, 'bulk'):
                flags, _, size, offset = struct.unpack_from('<4i', self.p.data, e['off'] + at)
                if not flags & native_fields.STORED_ELSEWHERE:
                    self.assertEqual(offset, e['off'] + at + 16)
                    inline += 1
            self.assertGreater(inline, 0, self.p.name(i))

    def test_a_fractured_mesh_and_its_component_read_to_their_ends_on_six_maps(self):
        """fields() reads each to the last byte of its export or raises. A fractured mesh is a static mesh and one
        reference more, the mesh it was sliced from (none in cooked data); a fractured mesh component's fields are
        those of a static mesh component, checked against the lighting reader."""
        import lightmap_fields
        import mesh
        from package import Package
        for name in FRACTURING_MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            p = self.p if name == 'URB_Bar' else Package(path)
            meshes = components = 0
            for i in range(1, len(p.exports) + 1):
                cls, e = p.cls(i), p.exports[i - 1]
                if cls == 'FracturedStaticMesh':
                    found = self.native(i, p)
                    refs = [(at, struct.unpack_from('<i', p.data, e['off'] + at)[0]) for at, k in found if k == 'object']
                    m = mesh.read_mesh(p, i)
                    self.assertEqual(len([k for _, k in found if k == 'bulk']), m['lods'], p.name(i))
                    self.assertEqual({k for _, k in found}, {'object', 'bulk'})
                    self.assertEqual(refs[-1][1], 0, p.name(i))                 # the source mesh: cooked out
                    self.assertGreater(refs[-1][0], m['lod0End'] - e['off'])
                    if m['lods'] == 1:
                        self.assertEqual([v for _, v in refs[1:-1]], [s['material'] for s in m['sections']], p.name(i))
                    self.assertIn(p.cls(refs[0][1]) if refs[0][1] > 0 else None, ('RB_BodySetup', None))
                    meshes += 1
                elif cls == 'FracturedStaticMeshComponent':
                    found = self.native(i, p)
                    if p.properties(i)[1] == e['off'] + e['size']:
                        self.assertEqual(found, [])                             # a template with no native data
                        continue
                    mine = {e['off'] + at for at, k in found if k == 'object'}
                    for lod in lightmap_fields.component_fields(p, i)['lods']:
                        for k in range(len(lod['shadowMaps'])):
                            self.assertIn(lod['shadowMapsOffset'] + 4 + 4 * k, mine)
                        if lod['lightmap']['type'] == 2:
                            for s in lod['lightmap']['slots']:
                                self.assertIn(s['textureOffset'], mine)
                        elif lod['lightmap']['type'] == 1:
                            self.assertIn(lod['lightmap']['ownerOffset'], mine)
                            for at in lod['lightmap']['bulkOffsets']:
                                self.assertIn((at - e['off'], 'bulk'), found)
                    components += 1
            if name in WITH_FRACTURING:
                self.assertGreater(meshes, 0, name)
                self.assertGreater(components, meshes, name)
            else:
                self.assertEqual((meshes, components), (0, 0), name)


# -- a made-up mesh component: the one reader of its LOD records, in both licensee branches ------------------------
OFF = 100               # where the component's data lies in the made-up package
OBJECTS = {0: 'None', 1: 'Owner', 2: 'Lightmap_0', 3: 'Lightmap_1', 4: 'Lightmap_2', 5: 'ShadowMap', 6: 'SwapMesh'}


class MadeUp:
    """What the readers read of a viewer Package: one mesh component (export 1), its data all native, the objects of
    OBJECTS to point at."""

    def __init__(self, licensee, native, cls='StaticMeshComponent'):
        from package import FormatError
        self.FormatError = FormatError
        self.header = dict(ver=845, lic=licensee)
        self.data = bytes(OFF) + native
        self.exports = [dict(off=OFF, size=len(native), outer=0)]
        self.klass = cls

    def native(self, index):
        from package import Reader
        return Reader(self.data, OFF, len(self.data))

    def name(self, ref):
        if ref not in OBJECTS:
            raise self.FormatError('Invalid object reference %d' % ref)
        return OBJECTS[ref]

    def cls(self, index):
        return self.klass


class Bytes:
    """A component's native data, written in order, each part's place in the package noted."""

    def __init__(self):
        self.b, self.at = b'', {}

    def put(self, raw, name=None):
        if name:
            self.at[name] = OFF + len(self.b)
        self.b += raw
        return self

    def texture_lod(self, key):
        """A LOD with a shadow map, no shadow vertex buffers, a texture lightmap of two lights, no colours."""
        self.put(struct.pack('<2i', 1, 5), key + 'shadows').put(struct.pack('<i', 0))
        self.put(struct.pack('<i', 2), key + 'lightmap').put(struct.pack('<i', 2))
        self.put(bytes(range(16)) + bytes(range(16, 32)))
        for k, (ref, scale) in enumerate(((2, 1.0), (3, 2.0), (4, 3.0))):
            self.put(struct.pack('<i', ref), '%sslot%d' % (key, k)).put(struct.pack('<3f', scale, scale, scale))
        self.put(struct.pack('<2f', 0.25, 0.5), key + 'scale').put(struct.pack('<2f', 0.125, 0.75), key + 'bias')
        return self.put(b'\0' + struct.pack('<i', 0))

    def vertex_lod(self, key):
        """A LOD lit per vertex: its owner, two bulk records with their payloads inline, three scale vectors; painted
        colours (stride 4, two of them) and one position."""
        self.put(struct.pack('<2i', 0, 0)).put(struct.pack('<i', 1), key + 'lightmap').put(struct.pack('<i', 0))
        self.put(struct.pack('<i', 1), key + 'owner')
        self.bulk(key + 'directional', bytes(range(1, 9)))
        self.put(struct.pack('<9f', *range(9)))
        self.bulk(key + 'simple', bytes(range(9, 13)))
        self.put(b'\1' + struct.pack('<2I', 4, 2) + struct.pack('<2i', 4, 2) + bytes(8))
        return self.put(struct.pack('<i', 1) + bytes(12))

    def bulk(self, name, payload):
        at = OFF + len(self.b)
        return self.put(struct.pack('<4i', 0, len(payload), len(payload), at + 16) + payload, name)


def made(licensee, lods=1):
    """(the native data, the places of its parts): `lods` texture LODs, and EW's swaps (a vertex-lit LOD and an unlit
    one, then two meshes) for licensee 64."""
    b = Bytes().put(struct.pack('<i', lods))
    for k in range(lods):
        b.texture_lod('lod%d.' % k)
    if licensee:
        b.vertex_lod('swap0.')
        b.put(struct.pack('<2i', 0, 0)).put(struct.pack('<i', 0), 'swap1.lightmap').put(b'\0' + struct.pack('<i', 0))
        b.put(struct.pack('<i', 6), 'mesh0').put(struct.pack('<i', 0), 'mesh1')
    return b.b, b.at


class MeshLods(unittest.TestCase):
    def test_one_reader_gives_each_value_with_its_place_in_both_branches(self):
        for licensee in (64, 0):
            native, at = made(licensee)
            p = MadeUp(licensee, native)
            with self.subTest(licensee=licensee):
                r = p.native(1)
                lods = native_fields.mesh_lods(r, p)
                self.assertEqual(r.pos, r.end)
                lod = lods['lods'][0]
                self.assertEqual(lod['shadowMaps'], dict(at=at['lod0.shadows'], refs=[5]))
                lm = lod['lightmap']
                self.assertEqual((lm['offset'], lm['type'], len(lm['lightGuids'])), (at['lod0.lightmap'], 2, 2))
                self.assertEqual([(s['textureOffset'], s['index'], s['scale'][0]) for s in lm['slots']],
                                 [(at['lod0.slot%d' % k], 2 + k, 1.0 + k) for k in range(3)])
                self.assertEqual((lm['coordinateScaleOffset'], lm['coordinateBias']), (at['lod0.scale'], [0.125, 0.75]))
                if not licensee:
                    self.assertEqual((lods['swaps'], lods['swapMeshes']), ([], []))
                    continue
                vertex = lods['swaps'][0]['lightmap']
                self.assertEqual((vertex['type'], vertex['ownerOffset'], vertex['owner']), (1, at['swap0.owner'], 1))
                self.assertEqual([(b['at'], b['bytes'], b['inline']) for b in (vertex['directionalSamples'],
                                                                              vertex['simpleSamples'])],
                                 [(at['swap0.directional'], 8, True), (at['swap0.simple'], 4, True)])
                self.assertTrue(lods['swaps'][0]['overrideVertexColors'])
                self.assertEqual(lods['swaps'][1]['lightmap'], dict(offset=at['swap1.lightmap'], type=0))
                self.assertEqual(lods['swapMeshes'], [dict(at=at['mesh0'], ref=6), dict(at=at['mesh1'], ref=0)])

    def test_the_three_readers_that_take_from_it(self):
        for licensee in (64, 0):
            native, at = made(licensee, lods=2)
            p = MadeUp(licensee, native)
            with self.subTest(licensee=licensee):
                # the bakers' values (lighting_records)
                record = lighting_records.component_record(p, 1)
                self.assertEqual([lod['shadowMaps'] for lod in record['lods']], [[5], [5]])
                self.assertEqual([s['texture'] for s in record['lods'][1]['lightmap']['slots']],
                                 ['Lightmap_0', 'Lightmap_1', 'Lightmap_2'])
                self.assertEqual((len(record['swaps']), record['swapMeshes']),
                                 (2, ['SwapMesh', 'None']) if licensee else (0, []))
                if licensee:
                    self.assertEqual(record['swaps'][0]['lightmap']['owner'], 'Owner')
                    self.assertEqual(record['swaps'][0]['lightmap']['simpleSamples'],
                                     dict(flags=0, count=4, bytes=4, offset=at['swap0.simple'] + 16, inline=True))
                # the relight's places (lightmap_fields): the LOD array alone
                fields = lightmap_fields.component_fields(p, 1)
                lm = fields['lods'][1]['lightmap']
                self.assertEqual((fields['lods'][1]['shadowMapsOffset'], lm['lightGuidCount'], lm['coordinateBiasOffset']),
                                 (at['lod1.shadows'], 2, at['lod1.bias']))
                self.assertEqual([s['scaleOffset'] for s in lm['slots']], [at['lod1.slot%d' % k] + 4 for k in range(3)])
                # the transplant's fields (native_fields), from the export's start
                rel = {k: v - OFF for k, v in at.items()}
                got = native_fields.fields(p, 1, 0)
                objects = [a for a, kind in got if kind == 'object']
                self.assertEqual(objects[:8], [x for n in range(2) for x in [rel['lod%d.shadows' % n] + 4]
                                               + [rel['lod%d.slot%d' % (n, k)] for k in range(3)]])
                if licensee:
                    self.assertEqual(objects[-3:], [rel['swap0.owner'], rel['mesh0'], rel['mesh1']])
                    self.assertEqual([a for a, kind in got if kind == 'bulk'],
                                     [rel['swap0.directional'], rel['swap0.simple']])
                else:
                    self.assertEqual(len(objects), 8)
                    self.assertNotIn('bulk', {kind for _, kind in got})

    def test_what_does_not_read_as_the_layout_is_refused(self):
        native, at = made(64)
        from package import FormatError
        # read in the other branch, EW's swaps are bytes left over: refused by a static mesh component's readers
        with self.assertRaises(FormatError):
            lighting_records.component_record(MadeUp(0, native), 1)
        with self.assertRaises(native_fields.NativeError):
            native_fields.fields(MadeUp(0, native), 1, 0)
        broken = {'a lightmap type of 3': (at['lod0.lightmap'], struct.pack('<i', 3)),
                  'a shadow map that is no object': (at['lod0.shadows'] + 4, struct.pack('<i', 99)),
                  'a negative vertex sample size': (at['swap0.simple'] + 8, struct.pack('<i', -4)),
                  'a vertex-colour flag of 2': (at['swap1.lightmap'] + 4, b'\2')}
        for why, (where, raw) in broken.items():
            data = bytearray(native)
            data[where - OFF:where - OFF + len(raw)] = raw
            p = MadeUp(64, bytes(data))
            with self.subTest(why):
                with self.assertRaises(FormatError):
                    lighting_records.component_record(p, 1)
                with self.assertRaises(FormatError):
                    lightmap_fields.component_fields(p, 1)
                with self.assertRaises(native_fields.NativeError):
                    native_fields.fields(p, 1, 0)
        # a vertex lightmap's inline payload must lie right after its record, where a copy moves it with the export
        data = bytearray(native)
        struct.pack_into('<i', data, at['swap0.directional'] - OFF + 12, 0)
        with self.assertRaises(native_fields.NativeError):
            native_fields.fields(MadeUp(64, bytes(data)), 1, 0)


if __name__ == '__main__':
    unittest.main()
