"""Light edits made in the map (native_lights.py; editor lights plan 4.3 and 9.5), with the relight's light states
(relight.py --light-edits, plan 4.4). Synthetic cases need no map; the map-backed ones use URB_Bar as shipped and
skip without it."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import native_copy  # noqa: E402
import native_lights  # noqa: E402
import lighting_records as lighting  # noqa: E402
import package_grow  # noqa: E402
import relight  # noqa: E402
from lights import effective_cone_degrees, light_record  # noqa: E402
from package import Package, Reader  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
TEMPLE, NO_TEMPLE = labpaths.test_file('XCOM_TEMPLE_UPK', labpaths.lwr_cooked('TempleShip.upk'), 'TempleShip.upk')
# maps whose name tables lack a light value's property (review finding 37): no light of the farm saves
# FalloffExponent, none of the battleship's InnerConeAngle
FARM, NO_FARM = labpaths.test_file('XCOM_FARM_UPK', labpaths.lwr_cooked('CsmallScout_Farm.upk'), 'CsmallScout_Farm.upk')
BATTLESHIP, NO_BATTLESHIP = labpaths.test_file('XCOM_BATTLESHIP_UPK', labpaths.lwr_cooked('CBattleship_01.upk'),
                                               'CBattleship_01.upk')
PL = native_lights.PL


# ---------------------------------------------------------------- synthetic: the property writer

class FakeGrower:
    """The part of package_grow.Grower set_property uses: the name table."""
    def __init__(self, names):
        self.names = list(names)

    def name(self, text):
        if text not in self.names:
            self.names.append(text)
        return self.names.index(text)


class FakePackage:
    """The map as the reader read it: its own copy of the name table, which the grower's additions never reach (as
    lighting_records.Package's and package_grow.Grower's are two lists)."""
    def __init__(self, names):
        self.names = list(names)


def tag(names, name, kind, size, sub=None):
    out = struct.pack('<iiiiii', names.index(name), 0, names.index(kind), 0, size, 0)
    return out + (struct.pack('<ii', names.index(sub), 0) if sub else b'')


def read_tags(names, data, start):
    """The tagged properties as the package reader reads them."""
    pk = Package.__new__(Package)
    pk.names = names
    return pk.tagged(Reader(bytes(data), start))


class SetProperty(unittest.TestCase):
    NAMES = ['None', 'Radius', 'FloatProperty', 'LightColor', 'StructProperty', 'Color', 'Location', 'Vector']

    def export(self):
        n = self.NAMES
        props = (tag(n, 'Radius', 'FloatProperty', 4) + struct.pack('<f', 512.0)
                 + tag(n, 'LightColor', 'StructProperty', 4, 'Color') + bytes([10, 20, 30, 255])
                 + struct.pack('<ii', 0, 0))
        return bytearray(struct.pack('<i', 7) + props), 4       # a NetIndex, then the properties

    def setUp(self):
        self.g = FakeGrower(self.NAMES)
        self.w = native_copy.Walker(FakePackage(self.NAMES), self.g)

    def test_a_saved_value_is_set_in_place(self):
        data, start = self.export()
        size = len(data)
        out = native_lights.set_property(self.w, self.g, data, start, 'Radius', 'FloatProperty', None,
                                         struct.pack('<f', 900.0))
        self.assertIs(out, data)            # a bytearray is changed in place
        self.assertEqual(len(out), size)
        tags = read_tags(self.g.names, out, start)
        self.assertEqual(tags[('Radius', 0)]['value'], 900.0)
        self.assertEqual(tags[('LightColor', 0)]['value'], [30 / 255, 20 / 255, 10 / 255, 1.0])

    def test_an_unsaved_value_gains_its_tag_before_the_closing_none(self):
        data, start = self.export()
        out = native_lights.set_property(self.w, self.g, data, start, 'Brightness', 'FloatProperty', None,
                                         struct.pack('<f', 2.5))
        out = native_lights.set_property(self.w, self.g, out, start, 'bEnabled', 'BoolProperty', None, b'\x00')
        out = native_lights.set_property(self.w, self.g, out, start, 'CachedParentToWorld', 'StructProperty', 'Matrix',
                                         native_lights.parent_to_world([1, 2, 3], [0, 0, 0]))
        tags = read_tags(self.g.names, out, start)
        self.assertEqual(tags[('Brightness', 0)]['value'], 2.5)
        self.assertIs(tags[('bEnabled', 0)]['value'], False)
        self.assertEqual(len(tags[('CachedParentToWorld', 0)]['value']), 64)
        self.assertEqual(tags[('Radius', 0)]['value'], 512.0)       # what was there survives
        # a bool's tag saves size 0 and one value byte, as the Walker reads it
        found = {p: (k, size) for p, k, _, _, size in self.w.walk(bytes(out), start, len(out))}
        self.assertEqual(found['bEnabled[0]'], ('BoolProperty', 1))
        at = bytes(out).index(struct.pack('<ii', self.g.names.index('bEnabled'), 0))
        self.assertEqual(struct.unpack_from('<i', out, at + 16)[0], 0)
        self.assertEqual(out[-8:], struct.pack('<ii', 0, 0))        # still closed by None

    def test_set_struct_takes_the_values_own_size(self):
        data, start = self.export()
        out = native_copy.set_struct(self.w, self.g, data, start, 'Location', 'Vector', '<3f', [1.0, 2.0, 3.0])
        tags = read_tags(self.g.names, out, start)
        self.assertEqual(tags[('Location', 0)]['value'], [1.0, 2.0, 3.0])
        out = native_copy.set_struct(self.w, self.g, out, start, 'Location', 'Vector', '<3f', [4.0, 5.0, 6.0])
        self.assertEqual(read_tags(self.g.names, out, start)[('Location', 0)]['value'], [4.0, 5.0, 6.0])

    def test_a_property_saved_as_another_kind_is_refused(self):
        data, start = self.export()
        with self.assertRaisesRegex(ValueError, 'saved as a FloatProperty'):
            native_lights.set_property(self.w, self.g, data, start, 'Radius', 'StructProperty', 'Vector', bytes(12))
        with self.assertRaisesRegex(ValueError, 'one byte'):
            native_lights.set_property(self.w, self.g, data, start, 'bEnabled', 'BoolProperty', None, b'\x00\x00')

    def test_a_name_new_to_the_map_is_walked_with_the_growers_names(self):
        # (review finding 37) a tag whose name the map lacks gets an index past the map's own table; the walker of a
        # growing package reads names from the grower, so a second write (and any walk) gets past it
        data, start = self.export()
        out = native_lights.set_property(self.w, self.g, data, start, 'FalloffExponent', 'FloatProperty', None,
                                         struct.pack('<f', 3.0))
        out = native_lights.set_property(self.w, self.g, out, start, 'bEnabled', 'BoolProperty', None, b'\x00')
        self.assertNotIn('FalloffExponent', self.w.p.names)
        found = [prop for prop, *_ in self.w.walk(bytes(out), start, len(out))]
        self.assertEqual(found, ['Radius[0]', 'LightColor[0]', 'FalloffExponent[0]', 'bEnabled[0]'])
        # a walker that knows the map's own names alone stops at it
        with self.assertRaisesRegex(ValueError, 'bad property name'):
            list(native_copy.Walker(FakePackage(self.NAMES)).walk(bytes(out), start, len(out)))

    def test_value_bytes(self):
        self.assertEqual(native_lights.value_bytes('color', [255, 196, 140], 200),
                         ('LightColor', 'StructProperty', 'Color', bytes([140, 196, 255, 200])))
        self.assertEqual(native_lights.value_bytes('enabled', False)[3], b'\x00')
        self.assertEqual(native_lights.value_bytes('outerConeAngle', 580)[:3], ('OuterConeAngle', 'FloatProperty', None))


class Guids(unittest.TestCase):
    def test_new_guids_come_from_the_seed_as_the_interface_says(self):
        seed = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc|SpotLight_53_copy7'
        g = native_lights.light_guids(seed)
        self.assertEqual(g['LightGuid'], hashlib.sha256((seed + '|LightGuid').encode()).digest()[:16])
        self.assertEqual(g['LightmapGuid'], hashlib.sha256((seed + '|LightmapGuid').encode()).digest()[:16])
        self.assertEqual(g, native_lights.light_guids(seed))
        self.assertNotEqual(g, native_lights.light_guids(seed + 'x'))
        with self.assertRaises(ValueError):
            native_lights.light_guids('')

    def test_parent_to_world_saves_each_row_w_first(self):
        m = struct.unpack('<16f', native_lights.parent_to_world([10, 20, 30], [0, 16384, 0], [2, 2, 2]))
        # yaw a quarter turn: X axis along +Y, Y axis along -X, scaled by 2; the origin last, W first
        np.testing.assert_allclose(m, [0, 0, 2, 0, 0, -2, 0, 0, 0, 0, 0, 2, 1, 10, 20, 30], atol=1e-6)


# ---------------------------------------------------------------- synthetic: resolving the edit

def entry(name, kind='spot', role='static', guid=1, **raw):
    values = dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, enabled=True,
                  location=[0.0, 0.0, 100.0], rotation=[-16384, 0, 0])
    if kind == 'spot':
        values.update(innerConeAngle=0.0, outerConeAngle=44.0)
    values.update(raw)
    return dict(id=name, actor=PL + name, component=PL + name + '.C', actorIndex=guid, componentIndex=guid + 1000,
                kind=kind, role=role, actorClass='SpotLight', raw=values, alpha=255, scale=[1.0, 1.0, 1.0],
                lightSourceRadius=32.0, guids=dict(LightGuid=bytes([guid]) * 16, LightmapGuid=bytes([guid + 100]) * 16))


class Prepare(unittest.TestCase):
    def setUp(self):
        reg = {e['id']: e for e in (entry('SpotLight_1', guid=1), entry('PointLight_2', 'point', guid=2),
                                    entry('GeneratedMeshAreaLight_3', role='area', guid=3),
                                    entry('SpotLightToggleable_4', role='toggleable', guid=4),
                                    entry('SpotLight_5', guid=5, outerConeAngle=580.0))}
        patch = mock.patch.object(native_lights, 'source_registry', lambda p: reg)
        patch.start()
        self.addCleanup(patch.stop)
        self.reg = reg

    def prep(self, **edit):
        return native_lights.prepare(None, edit)

    def test_deletes_are_absent_after_and_additions_before(self):
        s = self.prep(deletes=[dict(name='SpotLight_1')],
                      adds=[dict(name='PointLight_2_copy3', **{'from': 'PointLight_2'}, location=[5, 6, 7],
                                 rotation=[0, 0, 0], light=dict(brightness=4.0), guidSeed='p|PointLight_2_copy3')])
        self.assertNotIn('SpotLight_1', s['after'])
        self.assertIn('SpotLight_1', s['before'])
        self.assertNotIn('PointLight_2_copy3', s['before'])
        add = s['after']['PointLight_2_copy3']
        self.assertEqual(add['raw']['brightness'], 4.0)
        self.assertEqual(add['raw']['location'], [5.0, 6.0, 7.0])
        self.assertEqual(add['guids'], native_lights.light_guids('p|PointLight_2_copy3'))
        self.assertEqual([o['op'] for o in s['ops']], ['delete', 'add'])
        # the unchanged lights are in both
        self.assertIs(s['after']['SpotLight_5'], s['before']['SpotLight_5'])

    def test_a_change_writes_its_set_keeps_its_guids_and_its_stored_cone(self):
        b = self.reg['SpotLight_5']['raw']
        s = self.prep(changes=[dict(name='SpotLight_5', location=[100, 0, 100], rotation=b['rotation'],
                                    set=dict(color=[255, 0, 0]), before=b,
                                    light=dict(b, color=[255, 0, 0], location=[100, 0, 100]))])
        a = s['after']['SpotLight_5']
        self.assertEqual(a['raw']['outerConeAngle'], 580.0)         # inherited, as stored
        self.assertEqual(a['guids'], self.reg['SpotLight_5']['guids'])
        self.assertEqual(s['ops'][0]['set'], dict(color=[255, 0, 0]))
        self.assertEqual(s['before']['SpotLight_5']['raw']['color'], [255, 255, 255])
        # the codec light uses the stored angles; the codec clamps them (lights.effective_cone)
        self.assertEqual(native_lights.codec_light(a)['outerConeAngle'], 580.0)

    def test_disagreeing_before_or_light_values_are_refused(self):
        b = self.reg['SpotLight_1']['raw']
        with self.assertRaisesRegex(ValueError, 'brightness is 1.0 in the map'):
            self.prep(changes=[dict(name='SpotLight_1', set={}, before=dict(b, brightness=3.0))])
        with self.assertRaisesRegex(ValueError, 'radius'):
            self.prep(changes=[dict(name='SpotLight_1', set=dict(radius=500.0), light=dict(b, radius=600.0))])

    def test_what_a_light_edit_may_not_touch_is_refused(self):
        cases = [
            dict(deletes=[dict(name='GeneratedMeshAreaLight_3')]),                   # an area light, directly
            dict(changes=[dict(name='SpotLightToggleable_4', set=dict(brightness=2.0))]),
            dict(deletes=[dict(name='NoSuchLight_9')]),
            dict(area=[dict(op='move', light='SpotLight_1', location=[0, 0, 0], rotation=[0, 0, 0])]),
            dict(changes=[dict(name='PointLight_2', set=dict(outerConeAngle=30.0))]),  # no cone on a point light
            dict(changes=[dict(name='SpotLight_1', set=dict(brightness=float('nan')))]),
            dict(changes=[dict(name='SpotLight_1', set=dict(enabled=1))]),
            dict(changes=[dict(name='SpotLight_1', set=dict(color=[256, 0, 0]))]),
            dict(deletes=[dict(name='SpotLight_1')], changes=[dict(name='SpotLight_1', set={})]),
            dict(adds=[dict(name='X', **{'from': 'SpotLight_1'}, template=dict(kind='spot', version=1),
                            location=[0, 0, 0], rotation=[0, 0, 0], guidSeed='p|X')]),
            dict(adds=[dict(name='X', template=dict(kind='spot', version=1), location=[0, 0, 0], rotation=[0, 0, 0],
                            light=dict(brightness=1.0), guidSeed='p|X')]),            # a recipe light is complete
            dict(adds=[dict(name='X', template=dict(kind='point', version=1), location=[0, 0, 0],
                            rotation=[0, 0, 0], light={}, guidSeed='p|X')]),
            dict(adds=[dict(name='X', **{'from': 'SpotLight_1'}, location=[0, 0, 0], rotation=[0, 0, 0])]),
            dict(adds=[dict(name='SpotLight_5', **{'from': 'SpotLight_1'}, location=[0, 0, 0], rotation=[0, 0, 0],
                            guidSeed='p|Y')]),
        ]
        for edit in cases:
            with self.assertRaises(ValueError, msg=json.dumps(edit, default=str)):
                self.prep(**edit)

    def test_colliding_guids_are_refused(self):
        add = dict(**{'from': 'SpotLight_1'}, location=[0, 0, 0], rotation=[0, 0, 0], guidSeed='p|same')
        with self.assertRaisesRegex(ValueError, 'collide'):
            self.prep(adds=[dict(add, name='A'), dict(add, name='B')])

    def test_a_recipe_spot_and_area_ops(self):
        light = dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, innerConeAngle=0.0,
                     outerConeAngle=44.0, enabled=True)
        area = self.reg['GeneratedMeshAreaLight_3']
        s = self.prep(adds=[dict(name='SpotLight_copy8', template=dict(kind='spot', version=1), location=[1, 2, 3],
                                 rotation=[-16384, 0, 0], light=light, guidSeed='p|SpotLight_copy8')],
                      area=[dict(op='move', name='GeneratedMeshAreaLight_3', light='GeneratedMeshAreaLight_3',
                                 location=[9, 9, 9], rotation=[0, 0, 0], owner='A', ownerEntity='A'),
                            dict(op='copy', name='GeneratedMeshAreaLight_3_c', light='GeneratedMeshAreaLight_3',
                                 location=[8, 8, 8], rotation=[0, 0, 0], owner='A', ownerEntity='A_copy2',
                                 guidSeed='p|GeneratedMeshAreaLight_3|A_copy2')])
        recipe, move, copy = s['ops']
        self.assertEqual((recipe['recipe'], recipe['after']['kind'], recipe['after']['role']), (1, 'spot', 'static'))
        self.assertEqual(move['after']['guids'], area['guids'])
        self.assertEqual(copy['after']['guids'], native_lights.light_guids('p|GeneratedMeshAreaLight_3|A_copy2'))
        self.assertEqual(copy['after']['role'], 'area')
        # placed lights that emit are listed in receivers' lightmaps; area lights never are
        self.assertEqual([e['id'] for e in native_lights.registering(s)], ['SpotLight_copy8'])
        off = self.prep(adds=[dict(name='Off', **{'from': 'SpotLight_1'}, location=[0, 0, 0], rotation=[0, 0, 0],
                                   light=dict(enabled=False), guidSeed='p|Off'),
                              dict(name='Dark', **{'from': 'SpotLight_1'}, location=[0, 0, 0], rotation=[0, 0, 0],
                                   light=dict(brightness=0.0), guidSeed='p|Dark')])
        self.assertEqual(native_lights.registering(off), [])

    def test_relight_edits_carry_both_states_and_the_memberships(self):
        b = self.reg['SpotLight_1']['raw']
        s = self.prep(deletes=[dict(name='PointLight_2')],
                      changes=[dict(name='SpotLight_1', set=dict(brightness=2.0), location=b['location'],
                                    rotation=b['rotation'])])
        doc = native_lights.relight_edits(s, {PL + 'X.C': ['ab' * 16]})
        delete, change = doc['edits']
        self.assertIsNone(delete['after'])
        self.assertEqual(delete['before']['component'], PL + 'PointLight_2.C')
        self.assertEqual((change['before']['brightness'], change['after']['brightness']), (1.0, 2.0))
        self.assertEqual(change['before']['guids'], change['after']['guids'])
        self.assertEqual(doc['registered'], {PL + 'X.C': ['ab' * 16]})
        self.assertEqual(change['reach']['after'], [-1024.0, 1024.0, -1024.0, 1024.0, -924.0, 1124.0])


# ---------------------------------------------------------------- map-backed: the writer on the bar

def change(e, **kw):
    """A change of a registry entry as the compiler's native edit has it (plan 9.5)."""
    raw = e['raw']
    out = dict(name=e['id'], label=e['id'], kind=e['kind'], role='static', location=raw['location'],
               rotation=raw['rotation'], set={}, before=dict(raw))
    out.update(kw)
    return out


def level_slots(q):
    return native_copy.level_actors(q)


def lists(p, components):
    return {c: lighting.component_record(p, c)['lods'][0]['lightmap'].get('lightGuids') for c in components}


def fake_relight(calls):
    """native_copy.build's relight run, stubbed: the command recorded and an unchanged fixture written."""
    def run(cmd, check=True):
        calls.append(cmd)
        k = next(i for i, a in enumerate(cmd) if str(a).endswith('relight.py'))
        src, out, variant = Path(cmd[k + 1]), Path(cmd[k + 2]), cmd[k + 3]
        relight.unchanged_fixture(src, out, variant)
    return run


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarLights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        cls.reg = native_lights.source_registry(cls.p)

    def test_the_registry_holds_every_light_and_its_codec_lights_are_relights(self):
        p, reg = self.p, self.reg
        self.assertEqual(sum(e['role'] == 'static' for e in reg.values()), 116)
        self.assertEqual(sum(e['role'] == 'area' for e in reg.values()), 137)
        self.assertEqual(reg['SpotLightToggleable_2']['role'], 'toggleable')
        ours = {e['component']: native_lights.codec_light(e) for e in reg.values()}
        theirs = {l['component']: l for l in relight.map_lights(p, roles=None) if l['kind'] != 'directional'}
        self.assertEqual(ours, theirs)
        e = reg['SpotLight_53']
        self.assertEqual(e['guids']['LightmapGuid'].hex(), '09e509d62f94f742af9327af010b4019')
        self.assertEqual(e['raw']['color'], [234, 201, 140])
        self.assertEqual((e['raw']['innerConeAngle'], e['raw']['outerConeAngle']), (10.0, 70.0))

    def test_the_cached_matrix_is_the_actors_pose(self):
        # every light of the bar: the writer's matrix against the stored one (SpotLight_36's DrawScale3D 0.648 too)
        p = self.p
        worst = 0.0
        for e in self.reg.values():
            stored = np.array(struct.unpack('<16f', p.own(e['componentIndex'], 'CachedParentToWorld')))
            mine = np.array(struct.unpack('<16f', native_lights.parent_to_world(e['raw']['location'],
                                                                                 e['raw']['rotation'], e['scale'])))
            worst = max(worst, float(np.abs(stored - mine)[:13].max()))
            np.testing.assert_allclose(stored[13:], mine[13:], atol=1e-3)
        self.assertLess(worst, 1e-3)

    def edit_and_write(self, edit, d, name='URB_BarLights'):
        p = self.p
        g = package_grow.Grower(str(BAR))
        state = native_lights.prepare(p, edit)
        result = native_lights.apply(g, p, state)
        if result['gone']:
            native_copy.empty_slots(g, p, result['gone'])
        native_copy.add_to_level(g, p, result['actors'])
        out = Path(d) / f'{name}.upk'
        g.write(str(out))
        q = lighting.Package(out)
        native_lights.verify(q, state, result)
        return state, result, q

    def test_delete_change_and_copy_in_the_map(self):
        p, reg = self.p, self.reg
        s53, p0, s3 = reg['SpotLight_53'], reg['PointLight_0'], reg['SpotLight_3']
        self.assertIsNone(p.own(p0['componentIndex'], 'Brightness'))          # left at the class default
        edit = dict(deletes=[dict(name='SpotLight_3', label='delete:SpotLight_3', kind='spot', role='static',
                                  reach=native_lights.reach_box(s3['raw']))],
                    changes=[change(p0, set=dict(brightness=3.0)),
                             change(s53, location=[s53['raw']['location'][0] + 300] + s53['raw']['location'][1:],
                                    set=dict(color=[255, 196, 140]))],
                    adds=[dict(name='SpotLight_53_copy7', label='SpotLight_53_copy7', kind='spot', role='static',
                               **{'from': 'SpotLight_53'}, location=[-1000.0, -1500.0, 400.0], rotation=[-16384, 0, 0],
                               light=dict(radius=900.0), guidSeed='proj|SpotLight_53_copy7')])
        with tempfile.TemporaryDirectory() as d:
            state, result, q = self.edit_and_write(edit, d)
            slots = level_slots(q)
            rec = {r['name']: r for r in result['records']}
            # delete: out of the Level's list, its component untouched, its GUIDs still in the lightmaps listing them
            self.assertNotIn(s3['actorIndex'], slots)
            ce = q.exports[s3['componentIndex'] - 1]
            pe = p.exports[s3['componentIndex'] - 1]
            self.assertEqual(q.data[ce['off']:ce['off'] + ce['size']], p.data[pe['off']:pe['off'] + pe['size']])
            # change: an unset Brightness gains a tag; untouched raw values survive; GUIDs kept
            self.assertEqual(rec['PointLight_0']['tagsAdded'], ['Brightness'])
            r0 = light_record(q, p0['actorIndex'])
            self.assertEqual(r0['brightness'], 3.0)
            for key in ('Radius', 'FalloffExponent', 'LightColor', 'LightGuid', 'LightmapGuid', 'CachedParentToWorld'):
                self.assertEqual(q.own(p0['componentIndex'], key), p.own(p0['componentIndex'], key), key)
            self.assertNotIn('Location', rec['PointLight_0']['actorWritten'])
            # the moved spot: Location written (its Rotation kept), its matrix at the new place, its cone kept
            self.assertEqual(rec['SpotLight_53']['actorWritten'], ['Location'])
            self.assertEqual(rec['SpotLight_53']['written'], ['LightColor', 'CachedParentToWorld'])
            r53 = light_record(q, s53['actorIndex'])
            self.assertAlmostEqual(r53['location'][0], s53['raw']['location'][0] + 300, places=3)
            self.assertEqual([round(c * 255) for c in r53['color']], [255, 196, 140])
            self.assertEqual((r53['innerConeAngle'], r53['outerConeAngle']), (10.0, 70.0))
            m = struct.unpack('<16f', q.own(s53['componentIndex'], 'CachedParentToWorld'))
            self.assertAlmostEqual(m[13], s53['raw']['location'][0] + 300, places=2)
            self.assertEqual(q.own(s53['componentIndex'], 'LightGuid'), p.own(s53['componentIndex'], 'LightGuid'))
            self.assertEqual(q.own(s53['componentIndex'], 'LightColor')[3], 1.0)       # its own alpha byte
            # copy: a new SpotLight_<n>, deterministic fresh GUIDs, a Level slot, its values and pose, no tiles
            add = state['after']['SpotLight_53_copy7']
            ai, ci = add['actorIndex'], add['componentIndex']
            self.assertEqual(q.cls(ai), 'SpotLight')
            self.assertTrue(q.name(ai).startswith(PL + 'SpotLight_') and q.name(ai) not in p.by_name)
            self.assertEqual(q.exports[ci - 1]['outer'], ai)
            self.assertIn(ai, slots)
            self.assertEqual(len(slots), len(level_slots(p)) + 1)       # the light alone: no rebuild volume
            guids = native_lights.light_guids('proj|SpotLight_53_copy7')
            self.assertEqual((q.own(ci, 'LightGuid'), q.own(ci, 'LightmapGuid')),
                             (guids['LightGuid'], guids['LightmapGuid']))
            rc = light_record(q, ai)
            self.assertEqual((rc['location'], rc['rotation'], rc['radius']), ([-1000.0, -1500.0, 400.0],
                                                                               [-16384, 0, 0], 900.0))
            self.assertEqual((rc['outerConeAngle'], rc['brightness']), (70.0, 1.5))
            self.assertEqual(q.exports[ci - 1]['arch'], p.exports[s53['componentIndex'] - 1]['arch'])
            # the re-read map's lights: the deleted one is gone from what the relight sees after (the Level's list)
            self.assertEqual(rec['SpotLight_53_copy7']['flags'], {'bHasLightEverBeenBuiltIntoLightMap': True})

    def test_a_recipe_spot_is_made_by_the_factory_and_joins_the_level(self):
        # plan 9.6: light_factory.add_spot(g, p, location, rotation, light, guids, version) -> dict(actor, component,
        # imports, created). Until the factory is on this branch, a stand-in builds the actor (here a clone of a spot
        # of the map, its values and GUIDs written as the recipe would) so the rest of the path runs for real
        p, reg = self.p, self.reg
        calls = []

        def add_spot(g, pkg, location, rotation, light, guids, version=1):
            calls.append(dict(location=location, rotation=rotation, light=light, guids=guids, version=version))
            t = reg['SpotLight_53']
            info = native_copy.clone_assembly(g, pkg, [(t['actorIndex'], location, rotation)])[0]
            ci = info['mapping'][t['componentIndex']]
            walker = native_copy.Walker(pkg, g)
            data = bytearray(g.export_data(ci))
            start = native_lights.props_start(pkg, t['componentIndex'])
            for key in native_lights.keys_for('spot'):
                data = native_lights.set_property(walker, g, data, start, *native_lights.value_bytes(key, light[key]))
            for k, v in guids.items():
                data = native_lights.set_property(walker, g, data, start, k, 'StructProperty', 'Guid', v)
            g.relocate(ci, bytes(data))
            return dict(actor=info['actor'], component=ci, imports=[-1], created=[])
        light = dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, innerConeAngle=0.0,
                     outerConeAngle=44.0, enabled=True)
        edit = dict(adds=[dict(name='SpotLight_copy8', label='SpotLight_copy8', kind='spot', role='static',
                               template=dict(kind='spot', version=1), location=[-900.0, -1500.0, 380.0],
                               rotation=[-16384, 0, 0], light=light, guidSeed='proj|SpotLight_copy8')])
        factory = type(sys)('light_factory')
        factory.add_spot, factory.RECIPES = add_spot, {1: dict(lightSourceRadius=32.0)}
        with mock.patch.dict(sys.modules, light_factory=factory), tempfile.TemporaryDirectory() as d:
            state, result, q = self.edit_and_write(edit, d)
            (call,) = calls
            self.assertEqual((call['location'], call['rotation'], call['light'], call['version']),
                             ([-900.0, -1500.0, 380.0], [-16384, 0, 0], light, 1))
            self.assertEqual(call['guids'], native_lights.light_guids('proj|SpotLight_copy8'))
            a = state['after']['SpotLight_copy8']
            self.assertEqual((a['lightSourceRadius'], result['records'][0]['imports']), (32.0, [-1]))
            self.assertIn(a['actorIndex'], level_slots(q))
            r = light_record(q, a['actorIndex'])
            self.assertEqual((r['outerConeAngle'], r['brightness'], r['location']), (44.0, 1.0, [-900.0, -1500.0, 380.0]))
            self.assertEqual(native_lights.registering(state), [a])
        # without the factory, a recipe spot is refused saying why
        with mock.patch.dict(sys.modules, light_factory=None), tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'no light_factory.py'):
                self.edit_and_write(edit, d)

    def test_a_recipe_point_is_made_by_the_factory_itself(self):
        # prefab plan 5.5 (stage L1.1): light_factory.add_point, the real one, with no light of the map as a template
        light = dict(color=[255, 180, 90], brightness=2.0, radius=640.0, falloffExponent=3.0, enabled=True)
        edit = dict(adds=[dict(name='PointLight_copy9', label='PointLight_copy9', kind='point', role='static',
                               template=dict(kind='point', version=1), location=[-900.0, -1500.0, 380.0],
                               rotation=[0, 0, 0], light=light, guidSeed='proj|PointLight_copy9')])
        with tempfile.TemporaryDirectory() as d:
            state, result, q = self.edit_and_write(edit, d)
            a = state['after']['PointLight_copy9']
            # the relight bakes it with the source radius the light saves (F-91: it was UDK's default, 100)
            self.assertEqual((a['kind'], a['actorClass'], a['lightSourceRadius']), ('point', 'PointLight', 32.0))
            self.assertEqual(lighting.explicit_properties(q, a['componentIndex'], ['LightmassSettings']),
                             {'LightmassSettings': {'LightSourceRadius': a['lightSourceRadius']}})
            # and so for a recipe spot, by the real factory's recipe; a recipe that says nothing takes UDK's default
            self.assertEqual(native_lights.recipe_source_radius(1, 'spot'), 32.0)
            self.assertEqual(native_lights.recipe_source_radius(99, 'spot'), native_lights.UDK_POINT_SOURCE_RADIUS)
            self.assertIn(a['actorIndex'], level_slots(q))
            self.assertEqual((q.cls(a['actorIndex']), q.cls(a['componentIndex'])), ('PointLight', 'PointLightComponent'))
            r = light_record(q, a['actorIndex'])
            self.assertEqual((r['kind'], r['role'], r['radius'], r['falloffExponent'], r['brightness'], r['location']),
                             ('point', 'static', 640.0, 3.0, 2.0, [-900.0, -1500.0, 380.0]))
            guids = native_lights.light_guids('proj|PointLight_copy9')
            self.assertEqual((q.own(a['componentIndex'], 'LightGuid'), q.own(a['componentIndex'], 'LightmapGuid')),
                             (guids['LightGuid'], guids['LightmapGuid']))
            # the map has point lights: their class and archetype imports are reused, none made
            self.assertEqual(result['records'][0]['created'], [])
            self.assertEqual(native_lights.registering(state), [a])
        # a point light has no cones, and a recipe of another kind is refused
        for bad, words in ((dict(edit['adds'][0], light=dict(light, outerConeAngle=40.0)), 'has no outerConeAngle'),
                           (dict(edit['adds'][0], template=dict(kind='sky', version=1)), 'spot and point lights only'),
                           (dict(edit['adds'][0], kind='spot'), 'makes a point light')):
            with self.assertRaisesRegex(ValueError, words):
                native_lights.prepare(self.p, dict(adds=[bad]))

    def test_the_same_edit_makes_the_same_map(self):
        edit = dict(adds=[dict(name='PointLight_0_copy1', **{'from': 'PointLight_0'}, location=[0.0, 0.0, 200.0],
                               rotation=[0, 0, 0], guidSeed='proj|PointLight_0_copy1')])
        with tempfile.TemporaryDirectory() as d:
            native_copy.build(BAR, Path(d) / 'a', 'URB_BarL', [], lights=edit)
            native_copy.build(BAR, Path(d) / 'b', 'URB_BarL', [], lights=edit)
            self.assertEqual((Path(d) / 'a' / 'URB_BarL.upk').read_bytes(), (Path(d) / 'b' / 'URB_BarL.upk').read_bytes())

    def test_area_lights_keep_their_class_flags_and_owner_and_join_no_lightmap(self):
        p, reg = self.p, self.reg
        area = reg['GeneratedMeshAreaLight_370']
        other = reg['GeneratedMeshAreaLight_371']
        raw = area['raw']
        edit = dict(area=[dict(op='move', name=area['id'], light=area['id'], owner='XComLevelActor_1',
                               ownerEntity='XComLevelActor_1', location=[raw['location'][0] + 96] + raw['location'][1:],
                               rotation=[raw['rotation'][0], raw['rotation'][1] + 16384, 0]),
                          dict(op='copy', name='GeneratedMeshAreaLight_370_c', light=area['id'],
                               owner='XComLevelActor_1', ownerEntity='XComLevelActor_1_copy2',
                               location=[0.0, 0.0, 100.0], rotation=[0, 0, 0],
                               guidSeed='proj|GeneratedMeshAreaLight_370|XComLevelActor_1_copy2'),
                          dict(op='delete', name=other['id'], light=other['id'], owner='XComLevelActor_2',
                               ownerEntity='XComLevelActor_2')])
        with tempfile.TemporaryDirectory() as d:
            state, result, q = self.edit_and_write(edit, d)
            copy = state['after']['GeneratedMeshAreaLight_370_c']
            for ai, ci, src in ((area['actorIndex'], area['componentIndex'], area),
                                (copy['actorIndex'], copy['componentIndex'], area)):
                self.assertEqual(q.cls(ai), 'GeneratedMeshAreaLight')
                self.assertEqual(q.own(ai, 'Owner'), p.own(src['actorIndex'], 'Owner'))
                self.assertEqual(q.name(q.own(ai, 'Owner')).split('.')[-1], 'WorldInfo_6')
                self.assertEqual(q.own(ci, 'LightAffectsClassification'), 'LAC_USER_SELECTED')
                self.assertEqual(q.exports[ai - 1]['flags'], p.exports[src['actorIndex'] - 1]['flags'])
                self.assertEqual(q.exports[ci - 1]['arch'], p.exports[src['componentIndex'] - 1]['arch'])
                self.assertEqual(light_record(q, ai)['role'], 'area')
            self.assertEqual(light_record(q, area['actorIndex'])['rotation'][1], raw['rotation'][1] + 16384)
            self.assertNotIn(other['actorIndex'], level_slots(q))
            self.assertIn(copy['actorIndex'], level_slots(q))
            # never registered, even in a baked build
            self.assertEqual(native_lights.registering(state), [])

    def build_baked(self, d, copies, lights, name='URB_BarLit'):
        calls = []
        with mock.patch.object(native_copy.subprocess, 'run', fake_relight(calls)):
            m = native_copy.build(BAR, d, name, copies, bake=True, cache=f'{name}_Lighting', lights=lights)
        (cmd,) = calls
        doc = json.loads(Path(cmd[cmd.index('--light-edits') + 1]).read_text(encoding='utf-8'))
        grown = lighting.Package(Path(d) / 'grown' / 'URB_Bar.upk')
        # the variant cache's name is in the grown map's table for the relight to write (output names plan 4)
        self.assertIn(f'{name}_Lighting', grown.names)
        self.assertEqual(cmd[cmd.index('--cache') + 1], f'{name}_Lighting')
        return m, doc, grown

    def test_memberships_in_a_baked_build_cover_new_lights_and_copies_and_accumulate(self):
        # regression case 2: two lights added in the open lot east of the bar, sharing receivers, and a lamp post
        # copied into their reach; the moved spot reaches receivers at its new place
        p, reg = self.p, self.reg
        s53 = reg['SpotLight_53']
        spot = [-1155.0, -1874.4, 0.0]
        adds = [dict(name=f'PointLight_0_copy{k}', **{'from': 'PointLight_0'},
                     location=[spot[0] + 40 * k, spot[1], 150.0], rotation=[0, 0, 0], light=dict(radius=300.0),
                     guidSeed=f'proj|PointLight_0_copy{k}') for k in (1, 2)]
        moved_to = [s53['raw']['location'][0] - 1500.0] + s53['raw']['location'][1:]
        lights = dict(adds=adds, changes=[change(s53, location=moved_to)])
        lamp = p.by_name[PL + 'XComLevelActor_37']
        copies = [dict(actor='XComLevelActor_37', location=spot, rotation=p.own(lamp, 'Rotation', [0, 0, 0]))]
        with tempfile.TemporaryDirectory() as d:
            m, doc, q = self.build_baked(d, copies, lights)
            new = {e['name']: bytes.fromhex(e['guids']['LightmapGuid']) for e in doc['edits'] if e['op'] == 'add'}
            self.assertEqual(set(new), {'PointLight_0_copy1', 'PointLight_0_copy2'})
            moved_guid = s53['guids']['LightmapGuid'].hex()
            # the copy's lightmap lists both new lights after its source's own list; its source's list is as it was
            sec = m['nativeCopies']['copies'][0]
            comp = p.own(lamp, 'StaticMeshComponent')
            copy_comp = sec['exports'][p.name(comp)]
            src_list = lighting.component_record(p, comp)['lods'][0]['lightmap']['lightGuids']
            got = lighting.component_record(q, copy_comp)['lods'][0]['lightmap']['lightGuids']
            self.assertEqual(got[:len(src_list)], src_list)
            self.assertTrue({g.hex() for g in new.values()} <= set(got))
            self.assertEqual(lighting.component_record(q, comp)['lods'][0]['lightmap']['lightGuids'], src_list)
            # receivers of the map's own: the new lights accumulate on the ones they share, original lists kept as
            # the head of each, and the moved spot listed where it now reaches
            reg_doc = doc['registered']
            shared = [c for c, v in reg_doc.items() if {g.hex() for g in new.values()} <= set(v)
                      and q.by_name[c] <= len(p.exports)]
            self.assertTrue(shared, 'no receiver of the map lists both new lights')
            for c, added in reg_doc.items():
                ci = q.by_name[c]
                if ci > len(p.exports):
                    continue
                before = lighting.component_record(p, ci)['lods'][0]['lightmap']['lightGuids']
                after = lighting.component_record(q, ci)['lods'][0]['lightmap']['lightGuids']
                self.assertEqual(after, before + [g for g in added if g not in before], c)
            self.assertTrue(any(moved_guid in v for c, v in reg_doc.items()))
            # each registered receiver is within the light's radius of it: conservative, sphere against box
            meshes = {}
            for c, added in reg_doc.items():
                ci = q.by_name[c]
                if ci > len(p.exports):
                    continue
                box = native_lights.mesh_box(p, ci, meshes)
                for g in added:
                    e = next(e for e in doc['edits'] if e['guids']['LightmapGuid'] == g)
                    self.assertTrue(native_lights.sphere_meets(dict(location=e['after']['location'],
                                                                    radius=e['after']['radius']), box))
            # the record: policy, the lights listed in the copy by membership, nothing listed for no light
            lit = m['lights']
            self.assertEqual(lit['policy'], 'baked')
            self.assertIn(q.name(copy_comp), lit['registered'])
            self.assertEqual(lit['counts'], dict(deleted=0, changed=0, moved=1, added=2,
                                                 area=dict(moved=0, copied=0, deleted=0)))
            # the relight's light states from the same document: the copy's source and every receiver's original
            # list leave the new lights out before; after, the receiver resolves them
            states = relight.resolve_light_states(q, doc)
            before = type('S', (), {})()
            before.registry, before.registered = states['before'], {k: set(v) for k, v in states['registered'].items()}
            after = type('S', (), {})()
            after.registry, after.registered = states['after'], {}
            c = shared[0]
            listed = lighting.component_record(q, q.by_name[c])['lods'][0]['lightmap']['lightGuids']
            names_before = {l['component'] for l in relight.Scene.listed(before, relight.Scene.original_guids(
                before, c, listed))}
            names_after = {l['component'] for l in relight.Scene.listed(after, listed)}
            new_components = {e['component'] for e in doc['edits'] if e['op'] == 'add'}
            self.assertFalse(names_before & new_components)
            self.assertEqual(names_after & new_components, new_components)

    def test_a_copy_lit_only_by_a_new_light_receives_its_bake_and_its_before_state_does_not(self):
        # regression case 2 through the relight's model: a lamp post copied into the far car park, a point light added
        # beside it; real scenes (few samples, no bounce) built from the light-edits document
        p = self.p
        lamp = p.by_name[PL + 'XComLevelActor_37']
        spot = [-2500.0, -1700.0, 0.0]
        add = dict(name='PointLight_0_copy1', **{'from': 'PointLight_0'}, location=[spot[0] + 60, spot[1], 120.0],
                   rotation=[0, 0, 0], light=dict(radius=400.0, brightness=4.0), guidSeed='proj|PointLight_0_copy1')
        copies = [dict(actor='XComLevelActor_37', location=spot, rotation=p.own(lamp, 'Rotation', [0, 0, 0]))]
        with tempfile.TemporaryDirectory() as d:
            m, doc, q = self.build_baked(d, copies, dict(adds=[add]))
            sec = m['nativeCopies']['copies'][0]
            comp = p.own(lamp, 'StaticMeshComponent')
            copy_comp = q.name(sec['exports'][p.name(comp)])
            new_component = doc['edits'][0]['component']
            self.assertIn(doc['edits'][0]['guids']['LightmapGuid'], doc['registered'][copy_comp])
            states = relight.resolve_light_states(q, doc)
            copy_actor = sec['copy'].split('.')[-1]
            fast = dict(samples=8, bounce_rays=0, emissive=False)
            before = relight.Scene(q, **fast, remove_casters=[copy_actor], lights=states['before'],
                                   registered=states['registered'])
            after = relight.Scene(q, **fast, lights=states['after'])
            self.assertEqual(len(after.lights), len(before.lights) + 1)
            r = relight.relight_component(q, copy_comp, before, after=after, source=p.name(comp))
            rep = r['report']
            self.assertIn(new_component, rep['lights']['added'])
            self.assertIn(new_component, {l['component'] for l in rep['lightList']})
            self.assertGreater(rep['delta']['texelsChanged'], 0)
            # brighter where the new light stands: the copy's side facing it gains light
            gain = r['after'].sum(2)[r['covered']] - r['before'].sum(2)[r['covered']]
            self.assertGreater(float(np.percentile(gain, 99)), 0.05)
            # a receiver of the map the new light was added to: its original bake knows nothing of it
            originals = [c for c in doc['registered'] if q.by_name[c] <= len(p.exports)]
            if originals:
                r2 = relight.relight_component(q, originals[0], before, after=after)
                self.assertIn(new_component, {l['component'] for l in r2['report']['lightList']})
                self.assertGreaterEqual(r2['report']['delta']['maxFlatChange'], 0.0)

    def test_an_unbaked_build_leaves_every_lightmap_list_as_it_is(self):
        # regression case 5: the same kind of project without baking: no GUID added anywhere, copies included
        p, reg = self.p, self.reg
        s53 = reg['SpotLight_53']
        lamp = p.by_name[PL + 'XComLevelActor_37']
        lights = dict(adds=[dict(name='PointLight_0_copy1', **{'from': 'PointLight_0'},
                                 location=[-1155.0, -1874.4, 150.0], rotation=[0, 0, 0], guidSeed='proj|PointLight_0_copy1')],
                      changes=[change(s53, set=dict(brightness=4.0))])
        copies = [dict(actor='XComLevelActor_37', location=[-1155.0, -1874.4, 0.0],
                       rotation=p.own(lamp, 'Rotation', [0, 0, 0]))]
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(BAR, d, 'URB_BarQuick', copies, lights=lights)
            q = lighting.Package(Path(d) / 'URB_BarQuick.upk')
            comps = [i for i in range(1, len(p.exports) + 1) if p.cls(i) in ('StaticMeshComponent',)
                     and p.name(i).startswith(PL) and native_lights.lightmap_kind(p, i) == 'texture']
            self.assertEqual(lists(q, comps), lists(p, comps))
            sec = m['nativeCopies']['copies'][0]
            comp = p.own(lamp, 'StaticMeshComponent')
            self.assertEqual(lists(q, [sec['exports'][p.name(comp)]])[sec['exports'][p.name(comp)]],
                             lists(p, [comp])[comp])
            self.assertEqual((m['lights']['policy'], m['lights']['registered']), ('unbaked', {}))
            self.assertEqual(light_record(q, s53['actorIndex'])['brightness'], 4.0)
            self.assertFalse((Path(d) / 'URB_BarQuick.light-edits.json').exists())

    def test_relight_states_and_registration_record_in_the_light_edits_file(self):
        # a deleted light: before has it, after has not, and no receiver list grows
        s3 = self.reg['SpotLight_3']
        with tempfile.TemporaryDirectory() as d:
            m, doc, q = self.build_baked(d, [], dict(deletes=[dict(name='SpotLight_3')]))
            (e,) = doc['edits']
            self.assertEqual((e['op'], e['after'], e['before']['component']), ('delete', None, s3['component']))
            self.assertEqual(doc['registered'], {})
            self.assertEqual(m['lights']['registered'], {})
            states = relight.resolve_light_states(q, doc)
            self.assertIn(s3['component'], {l['component'] for l in states['before']})
            self.assertNotIn(s3['component'], {l['component'] for l in states['after']})


@unittest.skipUnless(BAR and BAR.exists() and (BAR.parent / 'Lighting.tfc').exists(), NO_BAR + ' (with Lighting.tfc)')
class ZeroWrites(unittest.TestCase):
    def test_lights_that_change_no_texel_still_build_an_edited_map(self):
        # regression case 6, a full build: a disabled light, a zero-brightness one and one far below the map that
        # reaches no receiver; the relight runs for real, writes no texel, and the build succeeds without a cache
        adds = [dict(name='PointLight_0_copy1', **{'from': 'PointLight_0'}, location=[-1155.0, -1874.4, 150.0],
                     rotation=[0, 0, 0], light=dict(enabled=False), guidSeed='proj|PointLight_0_copy1'),
                dict(name='PointLight_0_copy2', **{'from': 'PointLight_0'}, location=[-1000.0, -1874.4, 150.0],
                     rotation=[0, 0, 0], light=dict(brightness=0.0), guidSeed='proj|PointLight_0_copy2'),
                dict(name='PointLight_0_copy3', **{'from': 'PointLight_0'}, location=[0.0, 0.0, -20000.0],
                     rotation=[0, 0, 0], light=dict(radius=64.0), guidSeed='proj|PointLight_0_copy3')]
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(BAR, d, 'URB_BarZero', [], bake=True, cache='URB_BarZero_Lighting', lights=dict(adds=adds))
            out = Path(d)
            self.assertTrue(m['lightingUnchanged'])
            self.assertIsNone(m['cache'])
            self.assertEqual(m['edits'], [])
            self.assertEqual(list(out.glob('*.tfc')), [])
            rec = json.loads((out / 'URB_BarZero.relight.json').read_text(encoding='utf-8'))
            self.assertEqual((rec['components'], rec['lightingUnchanged'], rec['cache']), ([], True, None))
            self.assertEqual([e['name'] for e in rec['lightEdits']], [a['name'] for a in adds])
            # the map, the fixture report and the relight report agree: the variant is the edited map, which re-reads
            # with the three lights (no receiver lists them: none emits where a receiver is)
            variant = out / 'URB_BarZero.upk'
            self.assertEqual(m['outputs'], {str(variant): lighting.digest(variant)})
            self.assertEqual(variant.read_bytes(), (out / 'grown' / 'URB_Bar.upk').read_bytes())
            q = lighting.Package(variant)
            made = {e['name']: e for e in m['lights']['edits']}
            self.assertFalse(light_record(q, q.by_name[made['PointLight_0_copy1']['actor']])['enabled'])
            self.assertEqual(light_record(q, q.by_name[made['PointLight_0_copy2']['actor']])['brightness'], 0.0)
            self.assertEqual(m['lights']['registered'], {})
            self.assertEqual(m['nativeCopies']['copies'], [])


class NameNewToTheMap(unittest.TestCase):
    """(Review finding 37) A light change setting two values its component does not save, the first a property no
    object of the map saves: apply adds its name to the grower's table and walks past it to write the second."""
    def changed(self, path, kind, values):
        p = lighting.Package(path)
        prop = native_lights.PROPERTIES[next(iter(values))][0]
        self.assertNotIn(prop, p.names)
        reg = native_lights.source_registry(p)
        e = next(e for e in reg.values() if e['role'] == 'static' and e['kind'] == kind)
        g = package_grow.Grower(str(path))
        state = native_lights.prepare(p, dict(changes=[change(e, set=dict(values))]))
        (rec,) = native_lights.apply(g, p, state)['records']
        names = [native_lights.PROPERTIES[k][0] for k in values]
        self.assertEqual((rec['tagsAdded'][:1], rec['written']), ([prop], names))
        ci = rec['exports']['component']
        data = g.export_data(ci)
        found = [prop for prop, *_ in native_copy.Walker(p, g).walk(data, native_lights.props_start(p, ci), len(data))]
        self.assertLessEqual({n + '[0]' for n in names}, set(found))

    @unittest.skipUnless(FARM and FARM.exists(), NO_FARM)
    def test_a_point_lights_falloff_exponent_on_the_farm(self):
        self.changed(FARM, 'point', dict(falloffExponent=3.0, enabled=False))

    @unittest.skipUnless(BATTLESHIP and BATTLESHIP.exists(), NO_BATTLESHIP)
    def test_a_spot_lights_inner_cone_on_the_battleship(self):
        self.changed(BATTLESHIP, 'spot', dict(innerConeAngle=10.0, enabled=False))


@unittest.skipUnless(TEMPLE and TEMPLE.exists(), NO_TEMPLE)
class StoredCone(unittest.TestCase):
    def test_a_stored_580_degree_cone_survives_a_move_and_a_copy(self):
        # Temple Ship's SpotLight_29 stores an outer cone of 580 degrees (plan 2.7): moved and recoloured, and copied,
        # the raw angle is kept; the codec draws it with the effective cone
        p = lighting.Package(TEMPLE)
        reg = native_lights.source_registry(p)
        e = reg['SpotLight_29']
        self.assertEqual(e['raw']['outerConeAngle'], 580.0)
        edit = dict(changes=[change(e, location=[e['raw']['location'][0] + 64] + e['raw']['location'][1:],
                                    set=dict(color=[200, 220, 255]))],
                    adds=[dict(name='SpotLight_29_copy1', **{'from': 'SpotLight_29'}, location=[0.0, 0.0, 0.0],
                               rotation=e['raw']['rotation'], guidSeed='proj|SpotLight_29_copy1')])
        g = package_grow.Grower(str(TEMPLE))
        state = native_lights.prepare(p, edit)
        result = native_lights.apply(g, p, state)
        native_copy.add_to_level(g, p, result['actors'])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'TempleShip.upk'
            g.write(str(out))
            q = lighting.Package(out)
            native_lights.verify(q, state, result)
            for ai in (e['actorIndex'], state['after']['SpotLight_29_copy1']['actorIndex']):
                self.assertEqual(light_record(q, ai)['outerConeAngle'], 580.0)
            self.assertNotIn('OuterConeAngle', result['records'][0]['written'] + result['records'][1]['written'])
            c = native_lights.codec_light(state['after']['SpotLight_29'])
            self.assertAlmostEqual(effective_cone_degrees(c['innerConeAngle'], c['outerConeAngle'])[1], 89.99, places=6)


if __name__ == '__main__':
    unittest.main()
