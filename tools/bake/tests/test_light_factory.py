"""Spot lights built from a recipe with no local light to copy (light_factory.py; editor lights plan 4.9, 9.6).

The recipe checks run anywhere. The map-backed checks read the configured LWR install (tools/viewer/settings.py) and
skip without it: URB_TruckStop_EWI (the acceptance map, no spot light), URB_TruckStop_Stream (no light at all, and no
light import or name), and the maps the recipe was validated against (URB_Bar, URB_PoliceStation, TempleShip,
CLrgScout_ForestTrench)."""
import ast
import hashlib
import json
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
import light_factory  # noqa: E402
import native_copy  # noqa: E402
import lighting_records as lighting  # noqa: E402
import lights  # noqa: E402
import package as viewer_package  # noqa: E402
import package_grow  # noqa: E402
import props as legacy_props  # noqa: E402

sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402

TRUCKSTOP, NO_TRUCKSTOP = labpaths.test_file('XCOM_TRUCKSTOP_UPK', labpaths.lwr_cooked('URB_TruckStop_EWI.upk'),
                                             'URB_TruckStop_EWI.upk')
STREAM, NO_STREAM = labpaths.test_file('XCOM_TRUCKSTOP_STREAM_UPK', labpaths.lwr_cooked('URB_TruckStop_Stream.upk'),
                                       'URB_TruckStop_Stream.upk')
VALIDATED = {name: labpaths.test_file(env, labpaths.lwr_cooked(name + '.upk'), name + '.upk')
             for name, env in (('URB_Bar', 'XCOM_BAR_UPK'), ('URB_PoliceStation', 'XCOM_POLICE_UPK'),
                               ('TempleShip', 'XCOM_TEMPLE_UPK'), ('CLrgScout_ForestTrench', 'XCOM_FORESTTRENCH_UPK'))}
LEVEL = light_factory.LEVEL
# recipe version 1 as validated; a change to it is a new version (plan 4.9)
DIGEST_1 = '9d83db90d19665ddfd55861b5030b78c705f5725c850bbf95197cb0f5e3157d5'
LIGHT = dict(color=[255, 196, 140], brightness=2.5, radius=900.0, falloffExponent=3.0, innerConeAngle=10.0,
             outerConeAngle=40.0, enabled=True)
# the point recipe's version 1 as validated (12 November 2026)
POINT_DIGEST_1 = '93b91258675f5ef1a77633c66a149b340fb4331679c8beddf9b4112bca8204cf'
POINT_LIGHT = dict(color=[255, 196, 140], brightness=2.5, radius=640.0, falloffExponent=3.0, enabled=True)


def guids(seed):
    """As plan 9.5 derives them from a guidSeed."""
    return {k: hashlib.sha256(f'{seed}|{k}'.encode()).digest()[:16] for k in light_factory.GUID_KEYS}


def refuse_templates(g):
    """`g` with add_export (which copies a local template's entry) made to fail: the factory must not use it."""
    def no_template(*args, **kwargs):
        raise AssertionError('add_export copies a local template; the factory must not use it')
    g.add_export = no_template
    return g


def recipe_names(rec):
    """Every name the recipe can add to a package."""
    names = {'None', 'ObjectProperty', 'FloatProperty', 'BoolProperty', 'NameProperty', 'StructProperty', 'Vector',
             'Rotator', 'Matrix', 'Guid', 'Color'}
    for path, package, cls in rec['imports']:
        names |= {path.rsplit('.', 1)[-1], package, cls}

    def props(specs):
        for name, kind, value in specs:
            names.add(name)
            if kind.startswith('struct '):
                names.add(kind.split(' ', 1)[1])
                props(value)
            elif kind == 'name':
                names.add(value)
    for part in ('actor', 'component'):
        names.add(rec[part]['name'])
        props(rec[part]['properties'])
    return names


def preamble(q, index):
    e = q.exports[index - 1]
    start = legacy_props.props_start(q.data, e, q.names)
    return q.data[e['off']:start]


def net_index(q, index):
    e = q.exports[index - 1]
    start = legacy_props.props_start(q.data, e, q.names)
    return struct.unpack_from('<i', q.data, start - 4)[0] if start - 4 >= e['off'] else None


def top_package(q, ref):
    while True:
        outer = q.imports[-ref - 1]['outer'] if ref < 0 else q.exports[ref - 1]['outer']
        if outer == 0:
            return q.name(ref)
        ref = outer


def level_actors(q):
    level = q.by_name[LEVEL]
    r = q.native(level)
    owner, count = r.unpack('ii')
    return owner, list(r.unpack(f'{count}i'))


class RecipeTests(unittest.TestCase):
    """The recipe and the checks made before a package changes; no map needed."""

    def test_versions(self):
        self.assertEqual(sorted(light_factory.RECIPES), [1])
        self.assertIs(light_factory.recipe(1), light_factory.RECIPES[1])
        for bad in (0, 2, True, '1', 1.0, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                light_factory.recipe(bad)
            # refused before the package is touched (no package is given)
            with self.assertRaises(ValueError, msg=repr(bad)):
                light_factory.add_spot(None, None, [0, 0, 0], None, None, guids('x'), version=bad)

    def test_version_1_is_frozen(self):
        self.assertEqual(light_factory.recipe_digest(1), DIGEST_1,
                         'recipe version 1 changed: make the change a new version instead')

    def test_default_values_are_the_plans(self):
        rec = light_factory.RECIPES[1]
        # plan 3.3: white, brightness 1, radius 1,024, falloff 2, inner 0, outer 44 degrees, on, pointing down
        self.assertEqual(rec['light'], dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0,
                                            innerConeAngle=0.0, outerConeAngle=44.0, enabled=True))
        self.assertEqual(rec['rotation'], [-16384, 0, 0])
        self.assertEqual(sorted(rec['light']), sorted(light_factory.LIGHT_KEYS))
        # the export's own spot defaults (lights.py), so the editor shows what the factory makes
        spot = {**lights.LIGHT_DEFAULTS, **lights.COMPONENT_DEFAULTS['SpotLightComponent']}
        self.assertEqual([spot['Radius'], spot['FalloffExponent'], spot['InnerConeAngle'], spot['OuterConeAngle'],
                          spot['Brightness'], spot['bEnabled']],
                         [rec['light'][k] for k in ('radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle',
                                                    'brightness', 'enabled')])
        self.assertEqual(rec['rotation'], lights.ACTOR_ROTATION['SpotLight'])

    def test_every_editable_value_is_saved_and_the_static_settings_are_left_to_the_archetype(self):
        rec = light_factory.RECIPES[1]
        component = rec['component']
        saved = [name for name, _, _ in component['properties']]
        placeholders = {value[1:] for _, _, value in component['properties'] + rec['actor']['properties']
                        if isinstance(value, str) and value.startswith('$')}
        self.assertTrue(set(light_factory.LIGHT_KEYS) <= placeholders)
        self.assertFalse(set(component['inherited']) & set(saved))
        # the frozen static, shadow, channel and Lightmass settings
        fixed = {name: value for name, _, value in component['properties'] if not str(value).startswith('$')}
        self.assertEqual(fixed, {'LightmassSettings': [['LightSourceRadius', 'float', 32.0]],
                                 'bHasLightEverBeenBuiltIntoLightMap': True})
        self.assertEqual([p[0] for p in rec['actor']['properties']],
                         ['LightComponent', 'Location', 'Rotation', 'bDirtyComponents', 'Tag'])
        self.assertNotIn('Components', [p[0] for p in rec['actor']['properties']])

    def test_the_recipe_is_rules_and_names_not_package_bytes(self):
        # plain JSON (no bytes), no path of a computer, and the module imports nothing beyond the standard library
        # and the bundled property reader, so a release builds the light from the recipe and the destination alone
        text = json.dumps(light_factory.RECIPES)
        self.assertNotRegex(text, r'[A-Za-z]:\\|/|\.upk|\.tfc|UDK')
        tree = ast.parse((HERE.parent / 'light_factory.py').read_text(encoding='utf-8'))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imported, {'hashlib', 'json', 'math', 'pathlib', 'struct', 'sys', 'props'})

    def test_values_are_checked_before_the_package_changes(self):
        good = dict(LIGHT)
        cases = [dict(good, color=[256, 0, 0]), dict(good, color=[1, 2]), dict(good, color=[True, 0, 0]),
                 dict(good, radius=-1.0), dict(good, brightness=float('nan')), dict(good, enabled=1),
                 dict(good, outerConeAngle='44'), {k: v for k, v in good.items() if k != 'radius'},
                 dict(good, falloff=2.0), [1, 2, 3]]
        for light in cases:
            with self.assertRaises(ValueError, msg=repr(light)):
                light_factory.add_spot(None, None, [0, 0, 0], None, light, guids('x'))
        for location, rotation in (([0, 0], None), ([0, 0, float('inf')], None), ([0, 0, 0], [0.5, 0, 0]),
                                   ([0, 0, 0], [0, 0]), ([0, 0, 0], [2 ** 31, 0, 0])):
            with self.assertRaises(ValueError, msg=repr((location, rotation))):
                light_factory.add_spot(None, None, location, rotation, None, guids('x'))
        same = guids('x')
        for bad in (dict(same, LightGuid=bytes(16)), dict(same, LightGuid=b'short'),
                    dict(same, LightmapGuid=same['LightGuid']), {'LightGuid': same['LightGuid']},
                    dict(same, Other=bytes(16))):
            with self.assertRaises(ValueError, msg=repr(bad)):
                light_factory.add_spot(None, None, [0, 0, 0], None, None, bad)

    def test_cached_parent_to_world(self):
        # rows X, Y, Z axes and the origin, each stored W first
        m = struct.unpack('<16f', light_factory.cached_parent_to_world([10.0, -20.0, 30.0], [0, 0, 0]))
        self.assertEqual(m, (0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 10, -20, 30))
        # pointing down: the X axis is -Z
        m = struct.unpack('<16f', light_factory.cached_parent_to_world([0, 0, 0], [-16384, 0, 0]))
        self.assertAlmostEqual(m[3], -1.0, places=6)
        self.assertAlmostEqual(abs(m[1]) + abs(m[2]), 0.0, places=6)
        # a yaw of a quarter turn: X along +Y
        m = struct.unpack('<16f', light_factory.cached_parent_to_world([0, 0, 0], [0, 16384, 0]))
        self.assertAlmostEqual(m[2], 1.0, places=6)


@unittest.skipUnless(STREAM and STREAM.exists(), NO_STREAM)
class NoLightAtAll(unittest.TestCase):
    """A map with no light export, no light import and none of the light names (Truck Stop's stream level): the
    factory makes everything but the Engine package's import."""

    def test_construction_with_no_local_light(self):
        p = lighting.Package(STREAM)
        classes = {p.cls(i) for i in range(1, len(p.exports) + 1)}
        self.assertFalse({c for c in classes if 'Light' in c and 'Environment' not in c})
        self.assertFalse([i for i in p.imports if 'Light' in i['name'] and 'Environment' not in i['name']])
        self.assertNotIn('SpotLightComponent', p.names)
        g = refuse_templates(package_grow.Grower(str(STREAM)))
        engine = g.find_import('Package', 'Engine', 0)
        info = light_factory.add_spot(g, p, [64.0, -32.0, 200.0], [-16384, 0, 0], None, guids('stream'))
        self.assertEqual(info['imports'][0], engine)
        self.assertEqual(info['created'], info['imports'][1:])
        self.assertEqual(info['created'], [-(len(p.imports) + k) for k in range(1, 5)])
        native_copy.add_to_level(g, p, [info['actor']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / STREAM.name
            report = g.write(str(out))
            self.assertTrue(set(report['newNames']) <= recipe_names(light_factory.RECIPES[1]), report['newNames'])
            q = lighting.Package(out)
            chain = {q.name(i): (q.imports[-i - 1]['cpkg'], q.imports[-i - 1]['cls'])
                     for i in info['imports']}
            self.assertEqual(chain, {'Engine': ('Core', 'Package'), 'Engine.SpotLight': ('Core', 'Class'),
                                     'Engine.SpotLightComponent': ('Core', 'Class'),
                                     'Engine.Default__SpotLight': ('Engine', 'SpotLight'),
                                     'Engine.Default__SpotLight.SpotLightComponent0': ('Engine', 'SpotLightComponent')})
            record = lights.light_record(q, info['actor'])
            self.assertEqual((record['kind'], record['role'], record['location'], record['radius'],
                              record['outerConeAngle']), ('spot', 'static', [64.0, -32.0, 200.0], 1024.0, 44.0))
            self.assertEqual(level_actors(q)[1][-1], info['actor'])


@unittest.skipUnless(TRUCKSTOP and TRUCKSTOP.exists(), NO_TRUCKSTOP)
class TruckStop(unittest.TestCase):
    """The acceptance map (plan 4.9, EXP-26 run 6): no spot light, generated area lights using SpotLightComponent
    under their own archetype, and point lights."""
    LOCATION = [-1210.0, 230.0, 413.0]
    ROTATION = [-12000, 4000, 0]

    @classmethod
    def build(cls, out):
        p = lighting.Package(TRUCKSTOP)
        g = refuse_templates(package_grow.Grower(str(TRUCKSTOP)))
        info = light_factory.add_spot(g, p, cls.LOCATION, cls.ROTATION, LIGHT, guids('project|SpotLight_copy1'))
        native_copy.add_to_level(g, p, [info['actor']])
        return info, g.write(str(out))

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = lighting.Package(TRUCKSTOP)
        cls.out = Path(cls.tmp.name) / 'a' / TRUCKSTOP.name
        cls.out.parent.mkdir()
        cls.info, cls.report = cls.build(cls.out)
        cls.q = lighting.Package(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_map_has_no_spot_light_to_copy(self):
        p = self.p
        classes = [p.cls(i) for i in range(1, len(p.exports) + 1)]
        self.assertNotIn('SpotLight', classes)
        self.assertIn('GeneratedMeshAreaLight', classes)
        names = {p.name(-(k + 1)) for k in range(len(p.imports))}
        self.assertIn('Engine.SpotLightComponent', names)
        self.assertIn('Engine.Default__GeneratedMeshAreaLight.SpotLightComponent0', names)
        self.assertFalse({'Engine.SpotLight', 'Engine.Default__SpotLight'} & names)

    def test_imports_reused_and_made(self):
        p, q, info = self.p, self.q, self.info
        engine, actor_class, component_class, default, archetype = info['imports']
        # reused: the Engine package and the component class the area lights use; made: the rest, after the old
        self.assertEqual((q.name(engine), q.name(component_class)), ('Engine', 'Engine.SpotLightComponent'))
        self.assertGreaterEqual(engine, -len(p.imports))
        self.assertGreaterEqual(component_class, -len(p.imports))
        self.assertEqual(info['created'], [actor_class, default, archetype])
        self.assertEqual(info['created'], [-(len(p.imports) + k) for k in (1, 2, 3)])
        self.assertEqual(self.report['addedImports'], 3)
        self.assertEqual(q.imports[:len(p.imports)], p.imports)
        self.assertEqual(q.name(archetype), 'Engine.Default__SpotLight.SpotLightComponent0')
        self.assertEqual(q.imports[-archetype - 1]['outer'], default)
        self.assertEqual(q.imports[-default - 1]['outer'], engine)
        self.assertEqual(q.imports[-actor_class - 1]['outer'], engine)

    def test_the_exports_read_back(self):
        q, info = self.q, self.info
        rec = light_factory.RECIPES[1]
        actor, component = info['actor'], info['component']
        self.assertEqual((actor, component), (len(self.p.exports) + 1, len(self.p.exports) + 2))
        self.assertEqual((q.cls(actor), q.cls(component)), ('SpotLight', 'SpotLightComponent'))
        self.assertEqual(q.name(actor), LEVEL + '.SpotLight_0')
        self.assertEqual(q.exports[actor - 1]['outer'], q.by_name[LEVEL])
        self.assertEqual(q.exports[component - 1]['outer'], actor)
        self.assertEqual(q.own(actor, 'LightComponent'), component)
        self.assertEqual(q.children[actor], [component])
        self.assertEqual((q.exports[actor - 1]['flags'], q.exports[component - 1]['flags']),
                         (rec['actor']['flags'], rec['component']['flags']))
        self.assertEqual(q.exports[actor - 1]['arch'], 0)
        self.assertEqual(q.exports[component - 1]['arch'], info['imports'][4])
        # the actor's state frame names its class; the component is an instance (no template owner class)
        node, state, mask, latent, stack, code, net = struct.unpack('<iiIHiii', preamble(q, actor))
        self.assertEqual((node, state, mask, latent, stack, code), (info['imports'][1],) * 2 + (0xFFFFFFFF, 0, 0, -1))
        owner_class, component_net = struct.unpack('<ii', preamble(q, component))
        self.assertEqual(owner_class, 0)
        # fresh net indices: the map's next two, shared with no other export of the map's own net space (forced-export
        # packages count their own, T-15)
        count = self.p.header['gens'][0][2]
        self.assertEqual((net, component_net), (count, count + 1))
        self.assertEqual(self.report['netObjects'], count + 2)
        entries = package_grow.Grower(str(self.out)).entries

        def own_space(i):
            while i > 0:
                if entries[i - 1].get('<I', 40) & package_grow.FORCED_EXPORT:
                    return False
                i = entries[i - 1].outer
            return True
        others = [net_index(q, i) for i in range(1, len(self.p.exports) + 1)
                  if own_space(i) and q.cls(i) not in viewer_package.LEADING_SHADOW_MAP]
        self.assertTrue(others)
        self.assertFalse({net, component_net} & set(others))
        # tagged properties only, in the recipe's order, nothing after them
        for index, part in ((actor, 'actor'), (component, 'component')):
            values, end = q.properties(index)
            self.assertEqual([k[0] for k in values], [p[0] for p in rec[part]['properties']])
            self.assertEqual(end, q.exports[index - 1]['off'] + q.exports[index - 1]['size'])

    def test_values_and_guids_read_back(self):
        q, info = self.q, self.info
        record = lights.light_record(q, info['actor'])
        self.assertEqual((record['kind'], record['role'], record['actorClass'], record['componentClass']),
                         ('spot', 'static', 'SpotLight', 'SpotLightComponent'))
        self.assertEqual((record['location'], record['rotation']), (self.LOCATION, self.ROTATION))
        self.assertEqual([round(c * 255) for c in record['color']], LIGHT['color'])
        for key in ('brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled'):
            self.assertEqual(record[key], LIGHT[key], key)
        self.assertEqual(q.own(info['component'], 'LightColor')[3], 1.0)
        want = guids('project|SpotLight_copy1')
        for key in light_factory.GUID_KEYS:
            self.assertEqual(q.own(info['component'], key), want[key])
        self.assertEqual(q.own(info['component'], 'CachedParentToWorld'),
                         light_factory.cached_parent_to_world(self.LOCATION, self.ROTATION))
        self.assertEqual(lighting.explicit_properties(q, info['component'], ['LightmassSettings']),
                         {'LightmassSettings': {'LightSourceRadius': 32.0}})
        self.assertTrue(q.own(info['component'], 'bHasLightEverBeenBuiltIntoLightMap'))
        # unique among every light of the map
        seen = []
        for i in range(1, len(q.exports) + 1):
            if q.cls(i).endswith('LightComponent'):
                seen += [q.own(i, k) for k in light_factory.GUID_KEYS]
        for key in light_factory.GUID_KEYS:
            self.assertEqual(seen.count(want[key]), 1)
        # the relight's reader takes it as a placed static spot light
        import relight
        found = [x for x in relight.map_lights(q) if x['actor'] == q.name(info['actor'])]
        self.assertEqual([(x['kind'], x['role'], x['lightSourceRadius']) for x in found], [('spot', 'static', 32.0)])

    def test_the_level_slot_and_no_donor_reference(self):
        q, info = self.q, self.info
        level = q.by_name[LEVEL]
        owner, actors = level_actors(q)
        self.assertEqual((owner, actors[-1], actors.count(info['actor'])), (level, info['actor'], 1))
        walker = native_copy.Walker(q)
        refs = []
        for index in (info['actor'], info['component']):
            e = q.exports[index - 1]
            refs += [e['cls'], e['outer'], e['arch']]
            start = legacy_props.props_start(q.data, e, q.names) - e['off']
            data = q.data[e['off']:e['off'] + e['size']]
            refs += [struct.unpack_from('<i', data, at)[0] for _, at in walker.refs(data, start, e['size'])]
        refs += list(struct.unpack_from('<ii', preamble(q, info['actor'])))
        for ref in (r for r in refs if r):
            q.name(ref)     # within the package's tables
            self.assertIn(top_package(q, ref), ('Engine', 'TheWorld'), q.name(ref))
        self.assertTrue(set(self.report['newNames']) <= recipe_names(light_factory.RECIPES[1]))
        self.assertEqual(self.report['newNames'], ['SpotLight', 'Default__SpotLight', 'InnerConeAngle'])

    def test_a_second_build_gives_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / TRUCKSTOP.name
            info, report = self.build(out)
            self.assertEqual(info, self.info)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),
                             hashlib.sha256(self.out.read_bytes()).hexdigest())

    def test_more_spots_reuse_the_imports_and_refuse_used_guids(self):
        p = self.p
        g = refuse_templates(package_grow.Grower(str(TRUCKSTOP)))
        first = light_factory.add_spot(g, p, self.LOCATION, None, None, guids('one'))
        entries = len(g.entries)
        # the same GUIDs again (from the grown exports), or an area light's: refused, the package unchanged
        area = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'GeneratedMeshAreaLight')
        area_guid = p.own(p.own(area, 'LightComponent'), 'LightmapGuid')
        for bad in (guids('one'), dict(guids('two'), LightGuid=area_guid)):
            with self.assertRaises(ValueError):
                light_factory.add_spot(g, p, self.LOCATION, None, None, bad)
        self.assertEqual(len(g.entries), entries)
        second = light_factory.add_spot(g, p, [0.0, 0.0, 300.0], None, None, guids('two'))
        self.assertEqual((second['imports'], second['created']), (first['imports'], []))
        self.assertEqual(second['actor'], first['component'] + 1)
        names = [g.name_of(g.entries[i - 1].name_index, g.entries[i - 1].name_number)
                 for i in (first['actor'], second['actor'])]
        self.assertEqual(names, ['SpotLight_0', 'SpotLight_1'])


class RecipeMatchesPlacedSpots(unittest.TestCase):
    """The recipe against every placed SpotLight of the maps it was validated on (each skips when not installed):
    export flags, archetypes, preambles, property kinds and order, Lightmass settings, no native tail, and the
    cached matrix rule."""

    def check_map(self, path):
        p = lighting.Package(path)
        rec = light_factory.RECIPES[1]
        kinds = {'object': ('ObjectProperty', None), 'float': ('FloatProperty', None), 'bool': ('BoolProperty', None),
                 'name': ('NameProperty', None)}

        def expected(part):
            out = {}
            for name, kind, _ in rec[part]['properties']:
                if kind in kinds:
                    out[name] = kinds[kind]
                else:
                    out[name] = ('StructProperty', kind.split(' ', 1)[-1])
            return out
        actor_props, component_props = expected('actor'), expected('component')
        # what placed spots may save that the recipe leaves out: editor layers and scale, a shadow falloff
        extra_actor, extra_component = {'Layer', 'DrawScale3D'}, {'ShadowFalloffExponent'}
        spots = [i for i in range(1, len(p.exports) + 1)
                 if p.cls(i) == 'SpotLight' and p.name(i).startswith(LEVEL + '.')]
        self.assertTrue(spots)
        for actor in spots:
            component = p.own(actor, 'LightComponent')
            a, c = p.exports[actor - 1], p.exports[component - 1]
            self.assertEqual(p.children[actor], [component])
            self.assertEqual((a['flags'], a['arch'], a['sup']), (rec['actor']['flags'], 0, 0))
            self.assertEqual((c['flags'], c['outer'], p.name(c['arch'])),
                             (rec['component']['flags'], actor, rec['component']['archetype']))
            self.assertEqual(p.name(a['cls']), rec['actor']['class'])
            self.assertEqual(p.name(c['cls']), rec['component']['class'])
            node, state, mask, _, stack, code, net = struct.unpack('<iiIHiii', preamble(p, actor))
            frame = rec['actor']['preamble']
            self.assertEqual((node, state, mask, stack, code), (a['cls'], a['cls'], frame['probeMask'],
                                                                frame['stateStack'], frame['codeOffset']))
            owner_class, _ = struct.unpack('<ii', preamble(p, component))
            self.assertEqual(owner_class, rec['component']['preamble']['templateOwnerClass'])
            for index, want, extra in ((actor, actor_props, extra_actor), (component, component_props,
                                                                           extra_component)):
                values, end = p.properties(index)
                self.assertEqual(end, p.exports[index - 1]['off'] + p.exports[index - 1]['size'])
                shared = [k[0] for k in values if k[0] in want]
                self.assertEqual(shared, [k for k in want if k in shared], p.name(index))
                for (name, slot), v in values.items():
                    self.assertEqual(slot, 0)
                    if name in want:
                        self.assertEqual((v['kind'], v['subtype']), want[name], name)
                    else:
                        self.assertIn(name, extra, p.name(index))
            self.assertEqual(lighting.explicit_properties(p, component, ['LightmassSettings']),
                             {'LightmassSettings': {'LightSourceRadius': 32.0}})
            self.assertTrue(p.own(component, 'bHasLightEverBeenBuiltIntoLightMap'))
            for key in rec['component']['inherited']:
                self.assertIsNone(p.own(component, key), key)
            if p.own(actor, 'DrawScale3D') is None:
                stored = struct.unpack('<16f', p.own(component, 'CachedParentToWorld'))
                made = struct.unpack('<16f', light_factory.cached_parent_to_world(
                    p.effective(actor, 'Location', [0, 0, 0]), p.effective(actor, 'Rotation', rec['rotation'])))
                self.assertLess(max(abs(x - y) for x, y in zip(stored, made)), 1e-5, p.name(actor))
        return len(spots)

    def test_validated_maps(self):
        counts = {}
        for name, (path, why) in VALIDATED.items():
            with self.subTest(name):
                if not (path and path.exists()):
                    self.skipTest(why)
                counts[name] = self.check_map(path)
        expect = {'URB_Bar': 62, 'URB_PoliceStation': 31, 'TempleShip': 54, 'CLrgScout_ForestTrench': 20}
        self.assertEqual(counts, {k: v for k, v in expect.items() if k in counts})


class PointRecipeTests(unittest.TestCase):
    """The point light's recipe (prefab plan 5.5, stage L1.1) and its checks; no map needed."""

    def test_versions_and_the_frozen_recipe(self):
        self.assertEqual(sorted(light_factory.POINT_RECIPES), [1])
        self.assertIs(light_factory.recipe(1, 'point'), light_factory.POINT_RECIPES[1])
        self.assertEqual(light_factory.recipe_digest(1, 'point'), POINT_DIGEST_1,
                         'the point recipe version 1 changed: make the change a new version instead')
        # the spot's is untouched by the point's coming
        self.assertEqual(light_factory.recipe_digest(1), DIGEST_1)
        for bad in (0, 2, True, '1', None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                light_factory.add_point(None, None, [0, 0, 0], None, guids('x'), version=bad)
        with self.assertRaises(ValueError):
            light_factory.recipe(1, 'sky')

    def test_it_is_the_spot_without_cones_or_a_direction(self):
        point, spot = light_factory.POINT_RECIPES[1], light_factory.RECIPES[1]
        self.assertEqual(point['light'], {k: v for k, v in spot['light'].items() if 'Cone' not in k})
        self.assertEqual(point['rotation'], [0, 0, 0])
        names = lambda rec, part: [n for n, _, _ in rec[part]['properties']]
        self.assertEqual(names(point, 'actor'), [n for n in names(spot, 'actor') if n != 'Rotation'])
        self.assertEqual(names(point, 'component'), [n for n in names(spot, 'component') if 'Cone' not in n])
        for part in ('actor', 'component'):
            self.assertEqual((point[part]['flags'], point[part]['preamble']), (spot[part]['flags'], spot[part]['preamble']))
        self.assertEqual([i[0].replace('Point', 'Spot') for i in point['imports']], [i[0] for i in spot['imports']])
        # the export's own point defaults (lights.py), so the editor shows what the factory makes
        own = {**lights.LIGHT_DEFAULTS, **lights.COMPONENT_DEFAULTS['PointLightComponent']}
        self.assertEqual([own['Radius'], own['FalloffExponent'], own['Brightness'], own['bEnabled']],
                         [point['light'][k] for k in ('radius', 'falloffExponent', 'brightness', 'enabled')])

    def test_values_are_checked_before_the_package_changes(self):
        good = dict(POINT_LIGHT)
        for bad in (dict(good, innerConeAngle=10.0), dict(good, outerConeAngle=40.0), {k: v for k, v in good.items() if k != 'radius'},
                    dict(good, radius=-1.0), dict(good, color=[255, 255, 256]), dict(good, enabled=1), dict(LIGHT)):
            with self.assertRaises(ValueError, msg=repr(bad)):
                light_factory.add_point(None, None, [0, 0, 0], bad, guids('x'))


@unittest.skipUnless(STREAM and STREAM.exists(), NO_STREAM)
class PointWithNoLightAtAll(unittest.TestCase):
    """A point light made in a map with no light of any kind (Truck Stop's stream level), written and read back."""

    def test_construction_and_readback(self):
        p = lighting.Package(STREAM)
        self.assertNotIn('PointLightComponent', p.names)
        g = refuse_templates(package_grow.Grower(str(STREAM)))
        engine = g.find_import('Package', 'Engine', 0)
        info = light_factory.add_point(g, p, [64.0, -32.0, 200.0], POINT_LIGHT, guids('stream-point'))
        self.assertEqual(info['imports'][0], engine)
        self.assertEqual(info['created'], info['imports'][1:])
        # a spot light beside it: its own classes, the Engine import shared
        spot = light_factory.add_spot(g, p, [0.0, 0.0, 300.0], None, None, guids('stream-spot'))
        self.assertEqual(spot['imports'][0], engine)
        self.assertFalse(set(spot['created']) & set(info['created']))
        native_copy.add_to_level(g, p, [info['actor'], spot['actor']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / STREAM.name
            report = g.write(str(out))
            self.assertTrue(set(report['newNames']) <= recipe_names(light_factory.POINT_RECIPES[1]) | recipe_names(light_factory.RECIPES[1]),
                            report['newNames'])
            q = lighting.Package(out)
            chain = {q.name(i): (q.imports[-i - 1]['cpkg'], q.imports[-i - 1]['cls']) for i in info['imports']}
            self.assertEqual(chain, {'Engine': ('Core', 'Package'), 'Engine.PointLight': ('Core', 'Class'),
                                     'Engine.PointLightComponent': ('Core', 'Class'),
                                     'Engine.Default__PointLight': ('Engine', 'PointLight'),
                                     'Engine.Default__PointLight.PointLightComponent0': ('Engine', 'PointLightComponent')})
            actor, component = info['actor'], info['component']
            self.assertEqual((q.cls(actor), q.cls(component), q.children[actor]), ('PointLight', 'PointLightComponent', [component]))
            self.assertEqual(q.name(actor), LEVEL + '.PointLight_0')
            a, c = q.exports[actor - 1], q.exports[component - 1]
            rec = light_factory.POINT_RECIPES[1]
            self.assertEqual((a['flags'], a['arch'], c['flags'], q.name(c['arch'])),
                             (rec['actor']['flags'], 0, rec['component']['flags'], rec['component']['archetype']))
            for index, part in ((actor, 'actor'), (component, 'component')):
                values, end = q.properties(index)
                self.assertEqual(end, q.exports[index - 1]['off'] + q.exports[index - 1]['size'])
                self.assertEqual([k[0] for k in values], [n for n, _, _ in rec[part]['properties']])
            self.assertIsNone(q.own(actor, 'Rotation'))
            self.assertEqual(q.own(actor, 'LightComponent'), component)
            record = lights.light_record(q, actor)
            self.assertEqual((record['kind'], record['role'], record['location'], record['radius'], record['falloffExponent'],
                              record['brightness'], record['enabled']),
                             ('point', 'static', [64.0, -32.0, 200.0], 640.0, 3.0, 2.5, True))
            self.assertEqual([round(v * 255) for v in record['color'][:3]], POINT_LIGHT['color'])
            self.assertEqual(q.own(component, 'CachedParentToWorld'), light_factory.cached_parent_to_world([64.0, -32.0, 200.0], [0, 0, 0]))
            self.assertEqual({q.own(component, k) for k in light_factory.GUID_KEYS}, set(guids('stream-point').values()))
            self.assertEqual(level_actors(q)[1][-2:], [actor, spot['actor']])
            self.assertGreater(net_index(q, actor), 0)
            self.assertNotEqual(net_index(q, actor), net_index(q, component))
        # a second point light with the first's GUIDs is refused before anything is added
        before = len(g.entries)
        with self.assertRaises(ValueError):
            light_factory.add_point(g, p, [0.0, 0.0, 0.0], None, guids('stream-point'))
        self.assertEqual(len(g.entries), before)


class RecipeMatchesPlacedPoints(unittest.TestCase):
    """The point recipe against every placed PointLight of the maps the spot's was validated on (each skips when
    not installed): export flags, archetypes, preambles, property kinds and order, Lightmass settings, no native
    tail, and the cached matrix rule. A few placed point lights are not lightmapped ones (Temple Ship's 18 that save
    their lighting channels, and its four switched off): they share everything but the built flag."""

    def check_map(self, path):
        p = lighting.Package(path)
        rec = light_factory.POINT_RECIPES[1]
        kinds = {'object': ('ObjectProperty', None), 'float': ('FloatProperty', None), 'bool': ('BoolProperty', None),
                 'name': ('NameProperty', None)}
        expected = lambda part: {name: kinds.get(kind, ('StructProperty', kind.split(' ', 1)[-1]))
                                 for name, kind, _ in rec[part]['properties']}
        actor_props, component_props = expected('actor'), expected('component')
        # what placed points may save that the recipe leaves out: a turn, editor layers and scale; the settings of a
        # light that is not lightmapped
        extra_actor = {'Rotation', 'Layer', 'DrawScale3D', 'DrawScale'}
        extra_component = {'ShadowFalloffExponent', 'LightingChannels', 'LightAffectsClassification'}
        points = [i for i in range(1, len(p.exports) + 1)
                  if p.cls(i) == 'PointLight' and p.name(i).startswith(LEVEL + '.')]
        self.assertTrue(points)
        plain = 0
        for actor in points:
            component = p.own(actor, 'LightComponent')
            a, c = p.exports[actor - 1], p.exports[component - 1]
            self.assertEqual(p.children[actor], [component])
            self.assertEqual((a['flags'], a['arch'], a['sup']), (rec['actor']['flags'], 0, 0))
            self.assertEqual((c['flags'], c['outer'], p.name(c['arch'])),
                             (rec['component']['flags'], actor, rec['component']['archetype']))
            self.assertEqual(p.name(a['cls']), rec['actor']['class'])
            self.assertEqual(p.name(c['cls']), rec['component']['class'])
            node, state, mask, _, stack, code, net = struct.unpack('<iiIHiii', preamble(p, actor))
            frame = rec['actor']['preamble']
            self.assertEqual((node, state, mask, stack, code), (a['cls'], a['cls'], frame['probeMask'],
                                                                frame['stateStack'], frame['codeOffset']))
            owner_class, _ = struct.unpack('<ii', preamble(p, component))
            self.assertEqual(owner_class, rec['component']['preamble']['templateOwnerClass'])
            for index, want, extra in ((actor, actor_props, extra_actor), (component, component_props, extra_component)):
                values, end = p.properties(index)
                self.assertEqual(end, p.exports[index - 1]['off'] + p.exports[index - 1]['size'])
                shared = [k[0] for k in values if k[0] in want]
                self.assertEqual(shared, [k for k in want if k in shared], p.name(index))
                for (name, slot), v in values.items():
                    self.assertEqual(slot, 0)
                    if name in want:
                        self.assertEqual((v['kind'], v['subtype']), want[name], name)
                    else:
                        self.assertIn(name, extra, p.name(index))
            self.assertEqual(lighting.explicit_properties(p, component, ['LightmassSettings']),
                             {'LightmassSettings': {'LightSourceRadius': 32.0}})
            lightmapped = p.own(component, 'LightingChannels') is None and p.own(component, 'bEnabled') is None
            self.assertEqual(bool(p.own(component, 'bHasLightEverBeenBuiltIntoLightMap')), lightmapped, p.name(actor))
            if lightmapped:
                plain += 1
                for key in rec['component']['inherited']:
                    self.assertIsNone(p.own(component, key), key)
            if p.own(actor, 'DrawScale3D') is None and p.own(actor, 'DrawScale') is None:
                stored = struct.unpack('<16f', p.own(component, 'CachedParentToWorld'))
                made = struct.unpack('<16f', light_factory.cached_parent_to_world(
                    p.effective(actor, 'Location', [0, 0, 0]), p.effective(actor, 'Rotation', rec['rotation'])))
                self.assertLess(max(abs(x - y) for x, y in zip(stored, made)), 1e-5, p.name(actor))
        return len(points), plain

    def test_validated_maps(self):
        counts = {}
        for name, (path, why) in VALIDATED.items():
            with self.subTest(name):
                if not (path and path.exists()):
                    self.skipTest(why)
                counts[name] = self.check_map(path)
        expect = {'URB_Bar': (54, 54), 'URB_PoliceStation': (67, 67), 'TempleShip': (87, 65), 'CLrgScout_ForestTrench': (172, 172)}
        self.assertEqual(counts, {k: v for k, v in expect.items() if k in counts})


class ReleaseInclusion(unittest.TestCase):
    def test_the_release_takes_the_factory_once_the_writer_imports_it(self):
        sys.path.insert(0, str(TOOLS / 'release'))
        import make_release
        names = {p.relative_to(make_release.TOOLS).as_posix() for p in make_release.modules()}
        users = [p for p in names if p.endswith('.py') and 'light_factory' in (make_release.TOOLS / p).read_text(
            encoding='utf-8') and p != 'bake/light_factory.py']
        if not users:
            self.skipTest('no module the release takes imports light_factory yet (the writer, native_lights.py)')
        self.assertIn('bake/light_factory.py', names)


if __name__ == '__main__':
    unittest.main()
