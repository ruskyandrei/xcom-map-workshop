"""The game's property types (schema.py) and the typed walk of tagged properties (typed_props.py).

The synthetic checks run anywhere. The others read the configured install (tools/viewer/settings.py, or the folder
XCOM_COOKED names) and skip without it."""
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
import schema  # noqa: E402
import typed_props  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
MAPS = ('URB_Bar', 'TempleShip', 'URB_PoliceStation')

# -- a package of four exports' worth of bytes, by hand ------------------------------------------------------------
NAMES = ['None', 'Things', 'ArrayProperty', 'Numbers', 'Spot', 'StructProperty', 'Vector', 'Parts', 'Part', 'Label',
         'NameProperty', 'Hello', 'Owner', 'ObjectProperty', 'Kind', 'ByteProperty', 'EKind', 'KIND_One', 'Mystery',
         'IntProperty', 'Count']
N = NAMES.index
DOC = dict(version=1, packages={}, raw=['Core.Object.Vector'], structs={
    'Core.Object.Vector': dict(kind='ScriptStruct', super=None, flags=0x30, order=['X', 'Y', 'Z'],
                               props={k: dict(kind='FloatProperty') for k in 'XYZ'}),
    'Game.Thing.Part': dict(kind='ScriptStruct', super=None, flags=0, order=['Label', 'Owner'],
                            props=dict(Label=dict(kind='NameProperty'), Owner=dict(kind='ObjectProperty'))),
    'Game.Base': dict(kind='Class', super=None, order=[], props=dict(
        Things=dict(kind='ArrayProperty', inner=dict(kind='ObjectProperty')))),
    'Game.Thing': dict(kind='Class', super='Game.Base', order=[], props=dict(
        Numbers=dict(kind='ArrayProperty', inner=dict(kind='IntProperty')),
        Spot=dict(kind='StructProperty', struct='Core.Object.Vector'),
        Parts=dict(kind='ArrayProperty', inner=dict(kind='StructProperty', struct='Game.Thing.Part')),
        Kind=dict(kind='ByteProperty', enum=True)))})


def tag(name, kind, value, extra=b''):
    return struct.pack('<6i', N(name), 0, N(kind), 0, len(value), 0) + extra + value


def fname(name):
    return struct.pack('<2i', N(name), 0)


class FakePackage:
    """What typed_props reads of a viewer Package: one export of class Game.Thing."""

    def __init__(self, blob):
        self.names = NAMES
        self.data = bytes(16) + blob
        self.exports = [dict(off=16, size=len(blob), flags=0, cls=-1, outer=0)]

    def name(self, index):
        return 'Game.Thing' if index == -1 else 'Thing_0'

    def cls(self, index):
        return 'Thing'


class TypedWalk(unittest.TestCase):
    SCHEMA = schema.Schema(DOC)

    def walk(self, properties):
        blob = struct.pack('<i', 7) + properties + fname('None')
        return typed_props.fields(FakePackage(blob), 1, self.SCHEMA), blob

    def kinds(self, f, blob, kind):
        return [struct.unpack_from('<i', blob, at)[0] for at, k in f.fields if k == kind and at >= f.start]

    def test_an_array_of_objects_is_references_and_an_array_of_numbers_is_not(self):
        things = tag('Things', 'ArrayProperty', struct.pack('<3i', 2, 41, -42))
        numbers = tag('Numbers', 'ArrayProperty', struct.pack('<3i', 2, 41, -42))
        f, blob = self.walk(things + numbers)
        self.assertEqual(self.kinds(f, blob, 'object'), [41, -42])
        self.assertEqual((f.start, f.end, f.net_index), (4, len(blob), 0))
        self.assertEqual(f.untyped, [])

    def test_a_plain_bytes_struct_is_read_by_its_members_and_a_tagged_one_by_its_tags(self):
        spot = tag('Spot', 'StructProperty', struct.pack('<3f', 1, 2, 3), fname('Vector'))
        part = tag('Label', 'NameProperty', fname('Hello')) + tag('Owner', 'ObjectProperty', struct.pack('<i', 9))
        parts = tag('Parts', 'ArrayProperty', struct.pack('<i', 2) + (part + fname('None')) * 2)
        f, blob = self.walk(spot + parts)
        self.assertEqual(self.kinds(f, blob, 'object'), [9, 9])
        names = [NAMES[v] for v in self.kinds(f, blob, 'name')]
        self.assertEqual(names, ['Spot', 'StructProperty', 'Vector', 'Parts', 'ArrayProperty']
                         + ['Label', 'NameProperty', 'Hello', 'Owner', 'ObjectProperty', 'None'] * 2 + ['None'])

    def test_an_enum_value_is_a_name(self):
        f, blob = self.walk(tag('Kind', 'ByteProperty', fname('KIND_One'), fname('EKind')))
        self.assertEqual([NAMES[v] for v in self.kinds(f, blob, 'name')],
                         ['Kind', 'ByteProperty', 'EKind', 'KIND_One', 'None'])

    def test_an_array_the_schema_lacks_is_reported_and_an_empty_one_is_not(self):
        f, _ = self.walk(tag('Mystery', 'ArrayProperty', struct.pack('<2i', 1, 5))
                         + tag('Count', 'ArrayProperty', struct.pack('<i', 0)))
        self.assertEqual([u[0] for u in f.untyped], ['Mystery'])

    def test_an_array_that_does_not_fill_its_size_fails(self):
        with self.assertRaises(typed_props.WalkError):
            self.walk(tag('Things', 'ArrayProperty', struct.pack('<4i', 2, 41, -42, 0)))

    def test_a_components_owner_class_and_template_name_are_fields(self):
        blob = struct.pack('<i', -1) + fname('Hello') + struct.pack('<i', 7) \
            + tag('Count', 'IntProperty', struct.pack('<i', 3)) + fname('None')
        f = typed_props.fields(FakePackage(blob), 1, self.SCHEMA)
        self.assertEqual(f.fields[:2], [(0, 'object'), (4, 'name')])
        self.assertEqual((f.net_index, f.start), (12, 16))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class GameSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = schema.Schema(schema.build(BAR.parent))

    def test_what_the_script_packages_say(self):
        s, c = self.schema, self.schema.counts()
        self.assertGreater(c['classes'], 2000)
        self.assertGreater(c['arrays'], 2000)
        self.assertEqual(s.prop('Engine.StaticMeshComponent', 'Materials'),
                         dict(kind='ArrayProperty', inner=dict(kind='ObjectProperty')))     # MeshComponent's
        self.assertEqual(s.prop('Engine.StaticMeshComponent', 'LightmassSettings')['struct'],
                         'Engine.EngineTypes.LightmassPrimitiveSettings')
        self.assertTrue(s.is_raw('Core.Object.Vector'))
        self.assertEqual([n for n, _ in s.members('Core.Object.Box')], ['Min', 'Max', 'IsValid'])
        self.assertFalse(s.is_raw('Core.Object.BoxSphereBounds'))
        self.assertIsNone(s.prop('Engine.StaticMeshComponent', 'NoSuchProperty'))

    def test_every_export_of_three_maps_walks_to_its_closing_none(self):
        from package import Package
        for name in MAPS:
            path, why = labpaths.install_map(name)
            if not path.exists():
                self.skipTest(why)
            s = typed_props.survey(Package(path), self.schema)
            self.assertEqual(s['failed'], [], name)
            # the one array no script package types: an editor-only actor's list
            self.assertLessEqual(set(s['untyped']), {'VisGroupActor.DependentOn'}, name)
            self.assertGreater(s['objects'], 20000)

    def test_its_references_are_the_copiers_walker_less_that_walkers_wrong_guesses(self):
        """native_copy.Walker takes every array of 4-byte values for references unless it is on a list; the typed
        walk lists a reference only where the property is one. On the bar the typed walk finds no reference the
        walker lacks, and what the walker has beyond it are arrays of numbers (curves' lookup tables above all)."""
        import native_copy
        from package import Package
        p = Package(BAR)
        walker = native_copy.Walker(p)
        both, extra = 0, {}
        for i, e in enumerate(p.exports, 1):
            f = typed_props.fields(p, i, self.schema)
            data = p.data[e['off']:e['off'] + e['size']]
            theirs = {at: prop for prop, at in walker.refs(data, f.start, len(data))}
            mine = {at for at, kind in f.fields if kind == 'object' and at >= f.start}
            self.assertLessEqual(mine, set(theirs), p.name(i))
            both += len(mine)
            for at in set(theirs) - mine:
                extra[theirs[at].rsplit('.', 1)[-1].split('[')[0].split('(')[0]] = p.cls(i)
        self.assertGreater(both, 30000)
        self.assertIn('LookupTable', extra)
        for prop, cls in extra.items():
            known = self.schema.prop(typed_props.class_path(p, next(
                i for i in range(1, len(p.exports) + 1) if p.cls(i) == cls)), prop)
            # where the schema knows the property by the class alone, it is not an array of references
            if known is not None and known['kind'] == 'ArrayProperty':
                self.assertNotIn(known['inner']['kind'], typed_props.REFERENCES, prop)


if __name__ == '__main__':
    unittest.main()
