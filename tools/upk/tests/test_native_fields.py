"""The names, references and bulk records of native data (native_fields.py), against the readers each layout was
taken from, on three maps of the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED names).
Without the install the tests skip."""
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


if __name__ == '__main__':
    unittest.main()
