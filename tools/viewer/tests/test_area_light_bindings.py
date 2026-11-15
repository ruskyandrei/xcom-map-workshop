"""The area-light matcher (area_light_bindings.py): which glowing piece emitted each generated area light, and the
light's pose relative to it (editor lights plan 4.8, 9.7; research/area-light-matching.md)."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import area_light_bindings as alb  # noqa: E402
from export_math import forward, multiply, transform  # noqa: E402
import settings  # noqa: E402

COOKED = settings.lwr_cooked()
BAR = COOKED / 'URB_Bar.upk' if COOKED else None
EMITTER = dict(bUseEmissiveForStaticLighting=True, EmissiveLightFalloffExponent=3.0,
               EmissiveLightExplicitInfluenceRadius=256.0)


def box(half):
    """A box mesh centred on its origin: positions (8, 3), triangles (12, 3) wound as UE3 winds them (numeric
    cross(v1 - v0, v2 - v0) pointing into the box), one section."""
    hx, hy, hz = half
    corners = np.array([[sx * hx, sy * hy, sz * hz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float)
    triangles = []
    for axis in range(3):
        for sign in (-1, 1):
            face = [i for i, c in enumerate(corners) if c[axis] * sign > 0]
            a, b, c, d = sorted(face, key=lambda i: math.atan2(*np.delete(corners[i], axis)))
            for tri in ((a, b, c), (a, c, d)):
                v = corners[list(tri)]
                if np.cross(v[1] - v[0], v[2] - v[0])[axis] * sign > 0: tri = (tri[0], tri[2], tri[1])
                triangles.append(tri)
    return dict(positions=corners, triangles=np.array(triangles, np.int64), sections=np.zeros(12, np.int64))


class Source:
    """A synthetic evidence source (associate_with): component settings and box meshes by key."""

    def __init__(self, scale=1.0, settings_by_component=None, meshes=None):
        self.level_scale = scale
        self._settings = settings_by_component or {}
        self._meshes = meshes or {}

    def settings(self, obj):
        return self._settings.get(obj['component'], {})

    def mesh(self, obj, record):
        return self._meshes[obj['mesh']]


class Scene:
    """Objects, mesh records, lights and a Source for a synthetic map (game units, level scale 1: offset 30)."""

    def __init__(self, scale=1.0):
        self.objects, self.meshes, self.lights, self.materials = [], {}, [], {}
        self.source = Source(scale)
        self.offset = alb.SURFACE_OFFSET * scale

    def piece(self, actor, half, location=(0, 0, 0), rotation=(0, 0, 0), settings_=None, component='Mesh',
              translation=(0, 0, 0), turn=(0, 0, 0), scale=(1, 1, 1)):
        key = f'mesh-{len(self.meshes)}'
        self.meshes[key] = dict(name=f'Synthetic.Meshes.{key}', bounds=[0, 0, 0, *half, float(np.linalg.norm(half))],
                                kind='static', fragmentMask=None)
        self.source._meshes[key] = box(half)
        path = f'TheWorld.PersistentLevel.{actor}.{component}'
        obj = dict(id=f'{len(self.objects) + 1}:{len(self.objects) + 100}', actor=f'TheWorld.PersistentLevel.{actor}',
                   component=path, layer='base', sourcePackage='Synthetic', mesh=key, materials=[],
                   location=list(location), rotation=list(rotation), scale=list(scale),
                   componentTransform=transform(list(translation), list(turn), [1, 1, 1]))
        self.objects.append(obj)
        if settings_: self.source._settings[path] = dict(settings_)
        return obj

    def light(self, name, surface_point, normal, radius=256.0, falloff=3.0, layer='base'):
        """A generated light Lightmass would make for a patch centred at surface_point facing along normal."""
        n = np.asarray(normal, float) / np.linalg.norm(normal)
        rotation = alb.whole([math.atan2(n[2], math.hypot(n[0], n[1])) * 32768 / math.pi,
                              math.atan2(n[1], n[0]) * 32768 / math.pi, 0])
        location = (np.asarray(surface_point, float) + self.offset * np.asarray(forward(rotation))).tolist()
        record = dict(id=f'light:{name}', actor=f'TheWorld.PersistentLevel.{name}', layer=layer, role='area',
                      kind='spot', location=location, rotation=rotation, direction=forward(rotation), radius=radius,
                      falloffExponent=falloff)
        self.lights.append(record)
        return record

    def run(self):
        return alb.associate_with(self.source, self.objects, self.lights, self.meshes, self.materials)


def world(obj, local_point):
    m = np.array(alb.owner_matrix(obj), float)
    return (m[:3, :3] @ np.asarray(local_point, float) + m[:3, 3]).tolist()


def same_turn(test, a, b, places=4):
    """Two rotators give the same rotation."""
    test.assertTrue(np.allclose(alb.rotation_matrix(a), alb.rotation_matrix(b), atol=10 ** -places), (a, b))


class MatchTests(unittest.TestCase):
    def test_a_unique_emitter_is_verified_and_the_wall_behind_it_is_not(self):
        s = Scene()
        sign = s.piece('Sign_1', (5, 40, 20), location=(0, 0, 100), settings_=EMITTER)
        wall = s.piece('Wall_1', (5, 200, 200), location=(-10, 0, 100))
        light = s.light('GeneratedMeshAreaLight_1', (5, 10, 105), (1, 0, 0))
        result = s.run()
        a = result['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        self.assertEqual(a['owner'], dict(target=dict(package='Synthetic', level='base', actor=sign['actor']),
                                          component=sign['component'], objectId=sign['id']))
        self.assertEqual(a['matcher'], alb.MATCHER_VERSION)
        first, *rest = a['candidates']
        self.assertEqual((first['actor'], first['supported'], first['emissive']),
                         (sign['actor'], True, ['lightmass', 'falloff', 'radius']))
        self.assertAlmostEqual(first['footDistance'], 0.0, places=1)
        self.assertGreater(first['normalDot'], 0.99)
        self.assertIn(wall['actor'], [c['actor'] for c in rest])
        self.assertFalse(next(c for c in rest if c['actor'] == wall['actor'])['supported'])
        self.assertEqual(result['owners'][sign['id']], [light['id']])
        self.assertEqual(result['owners'][wall['id']], [light['id']])   # a candidate, though not the owner
        self.assertEqual(a['ownerMatrix'], alb.owner_matrix(sign))
        for got, want in zip(a['local']['location'], [5 + s.offset, 10, 5]):
            self.assertAlmostEqual(got, want, places=3)
        self.assertEqual(result['version'], alb.MATCHER_VERSION)
        self.assertEqual(result['thresholds']['surfaceOffset'], 30.0)

    def test_one_owner_with_several_proxies(self):
        s = Scene()
        lamp = s.piece('Lamp_1', (20, 20, 20), settings_=EMITTER)
        ids = [s.light(f'GeneratedMeshAreaLight_{i}', point, normal)['id'] for i, (point, normal) in enumerate(
            [((20, 0, 0), (1, 0, 0)), ((0, 20, 5), (0, 1, 0)), ((0, 0, 20), (0, 0, 1))])]
        result = s.run()
        for i in ids:
            self.assertEqual(result['attachments'][i]['status'], 'verified')
            self.assertEqual(result['attachments'][i]['owner']['objectId'], lamp['id'])
        self.assertEqual(result['owners'][lamp['id']], sorted(ids))

    def test_adjacent_competing_owners_are_ambiguous(self):
        s = Scene()
        left = s.piece('Sign_1', (20, 20, 5), location=(-21, 0, 0), settings_=EMITTER)
        right = s.piece('Sign_2', (20, 20, 5), location=(21, 0, 0), settings_=EMITTER)
        light = s.light('GeneratedMeshAreaLight_1', (0, 0, 5), (0, 0, 1))   # over the seam between them
        result = s.run()
        a = result['attachments'][light['id']]
        self.assertEqual(a['status'], 'ambiguous', a['reason'])
        self.assertIsNone(a['owner'])
        self.assertIsNone(a['ownerMatrix'])
        self.assertIsNone(a['local'])
        self.assertEqual({c['actor'] for c in a['candidates'] if c['supported']}, {left['actor'], right['actor']})
        self.assertIn('Sign_1', a['reason'])
        self.assertIn('Sign_2', a['reason'])
        self.assertEqual(result['owners'][left['id']], [light['id']])
        self.assertEqual(result['owners'][right['id']], [light['id']])

    def test_a_repeated_emitter_further_off_does_not_make_it_ambiguous(self):
        s = Scene()
        near = s.piece('Core_1', (20, 20, 5), settings_=EMITTER)
        s.piece('Core_2', (20, 20, 5), location=(60, 0, 0), settings_=EMITTER)   # 20 units of gap: 2/3 offset
        light = s.light('GeneratedMeshAreaLight_1', (-10, 0, 5), (0, 0, 1))
        a = s.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        self.assertEqual(a['owner']['objectId'], near['id'])
        self.assertIn('the next emitter with matching settings, Core_2', a['reason'])

    def test_a_closer_emitter_with_other_settings_is_not_the_owner(self):
        s = Scene()
        true = s.piece('Neon_1', (5, 40, 20), settings_=EMITTER)
        s.piece('Flood_1', (5, 40, 20), location=(0, 0, 41), settings_=dict(EMITTER, EmissiveLightFalloffExponent=6.0))
        light = s.light('GeneratedMeshAreaLight_1', (5, 0, 19), (1, 0, 0))
        a = s.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        self.assertEqual(a['owner']['objectId'], true['id'])
        alone = Scene()
        alone.piece('Flood_1', (5, 40, 20), settings_=dict(EMITTER, EmissiveLightFalloffExponent=6.0))
        light = alone.light('GeneratedMeshAreaLight_1', (5, 0, 0), (1, 0, 0))
        a = alone.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'unmatched')
        self.assertIn("settings differ from the light's", a['reason'])
        self.assertEqual(a['candidates'][0]['emissive'], ['lightmass', 'radius'])

    def test_a_computed_radius_matches_any_light_radius(self):
        s = Scene()
        s.piece('Panel_1', (5, 40, 20), settings_=dict(bUseEmissiveForStaticLighting=True))
        light = s.light('GeneratedMeshAreaLight_1', (5, 0, 0), (1, 0, 0), radius=173.54, falloff=2.0)
        a = s.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        self.assertEqual(a['candidates'][0]['emissive'], ['lightmass', 'falloff', 'radius-computed'])

    def test_unmatched_lights_say_why(self):
        s = Scene()
        wall = s.piece('Wall_1', (5, 200, 200))
        beside = s.light('GeneratedMeshAreaLight_1', (5, 0, 0), (1, 0, 0))
        nowhere = s.light('GeneratedMeshAreaLight_2', (5000, 0, 0), (0, 0, 1))
        far = s.piece('Sign_1', (5, 40, 20), location=(0, 1000, 0), settings_=EMITTER)
        off = s.light('GeneratedMeshAreaLight_3', (5 + 50, 1000, 0), (1, 0, 0))   # 50 units out: past footMax 45
        result = s.run()
        a = result['attachments'][beside['id']]
        self.assertEqual((a['status'], a['owner'], a['local']), ('unmatched', None, None))
        self.assertIn('bUseEmissiveForStaticLighting', a['reason'])
        self.assertEqual([c['actor'] for c in a['candidates']], [wall['actor']])
        a = result['attachments'][nowhere['id']]
        self.assertEqual((a['status'], a['candidates']), ('unmatched', []))
        self.assertIn('no base-level surface', a['reason'])
        a = result['attachments'][off['id']]
        self.assertEqual(a['status'], 'unmatched')
        self.assertIn('Sign_1, is 50.0 units', a['reason'])
        self.assertEqual(result['owners'][far['id']], [off['id']])

    def test_lights_outside_the_base_level_are_unsupported(self):
        s = Scene()
        s.piece('Sign_1', (5, 40, 20), settings_=EMITTER)
        light = s.light('GeneratedMeshAreaLight_1', (5, 0, 0), (1, 0, 0), layer='stream')
        a = s.run()['attachments'][light['id']]
        self.assertEqual((a['status'], a['candidates'], a['owner']), ('unsupported', [], None))
        self.assertIn('stream layer', a['reason'])

    def test_streamed_pieces_are_never_candidates(self):
        s = Scene()
        sign = s.piece('Sign_1', (5, 40, 20), settings_=EMITTER)
        sign['layer'] = 'stream'
        light = s.light('GeneratedMeshAreaLight_1', (5, 0, 0), (1, 0, 0))
        a = s.run()['attachments'][light['id']]
        self.assertEqual((a['status'], a['candidates']), ('unmatched', []))

    def test_two_components_of_one_actor_verify_to_the_closer(self):
        s = Scene()
        bulb = s.piece('Lamp_1', (5, 5, 5), settings_=EMITTER, component='Bulb')
        s.piece('Lamp_1', (5, 5, 5), settings_=EMITTER, component='Housing', translation=(0, 12, 0))
        light = s.light('GeneratedMeshAreaLight_1', (0, 0, 5), (0, 0, 1))
        a = s.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        self.assertEqual(a['owner']['component'], bulb['component'])
        self.assertIn('other component(s) of the same actor', a['reason'])

    def test_a_component_offset_from_its_actor_pivot(self):
        s = Scene()
        obj = s.piece('Flood_1', (10, 30, 15), location=(100, 50, 0), rotation=(0, 5461, 0), settings_=EMITTER,
                      translation=(40, 0, 25), turn=(2000, 3000, 0))
        surface = world(obj, (10, 5, 3))
        normal = np.array(alb.owner_matrix(obj), float)[:3, 0]   # the box's +X face
        light = s.light('GeneratedMeshAreaLight_1', surface, normal)
        a = s.run()['attachments'][light['id']]
        self.assertEqual(a['status'], 'verified', a['reason'])
        before = np.array(alb.multiply(transform([100, 50, 0], [0, 5461, 0], [1, 1, 1]),
                                       transform([40, 0, 25], [2000, 3000, 0], [1, 1, 1])))
        self.assertTrue(np.allclose(a['ownerMatrix'], before))
        # the local pose is in the component's frame, not the actor's: the +X face, 30 units out
        for got, want in zip(a['local']['location'], [10 + s.offset, 5, 3]):
            self.assertAlmostEqual(got, want, delta=0.05)
        self.assertLess(abs(a['local']['rotation'][0]) + abs(a['local']['rotation'][1]), 20)
        # the actor moved and turned: the light follows the component (lightAfter = ownerAfter . ownerBefore^-1 . light)
        after = np.array(multiply(transform([-300, 420, 64], [0, -12000, 0], [1, 1, 1]),
                                  transform([40, 0, 25], [2000, 3000, 0], [1, 1, 1])))
        location, rotation = alb.light_pose(a['local'], after.tolist())
        delta = after @ np.linalg.inv(before)
        want = delta[:3, :3] @ np.array(light['location']) + delta[:3, 3]
        self.assertTrue(np.allclose(location, want, atol=1e-4))
        self.assertTrue(np.allclose(forward(rotation), delta[:3, :3] @ np.array(forward(light['rotation'])), atol=2e-4))
        # turning about the actor's origin alone, without its rotation's effect on the offset, would miss it
        naive = np.array(light['location']) + np.array([-400, 370, 64])
        self.assertGreater(np.linalg.norm(naive - want), 10)

    def test_results_are_deterministic(self):
        def build():
            s = Scene(scale=0.5)
            s.piece('Sign_1', (5, 40, 20), settings_=EMITTER)
            s.piece('Sign_2', (5, 40, 20), location=(0, 81, 0), settings_=EMITTER)
            s.light('GeneratedMeshAreaLight_2', (5, 0, 0), (1, 0, 0))
            s.light('GeneratedMeshAreaLight_1', (5, 40.5, 0), (1, 0, 0))
            return json.dumps(s.run(), sort_keys=True)
        self.assertEqual(build(), build())
        result = json.loads(build())
        self.assertEqual(list(result['attachments']), sorted(result['attachments']))
        self.assertEqual(result['thresholds']['surfaceOffset'], 15.0)


class PoseTests(unittest.TestCase):
    ROTATORS = [[0, 0, 0], [0, 16384, 0], [-16384, 0, 0], [2970, -19483, 0], [-3000, 12345, 777], [12000, -30000, -8000],
                [16000, 1234, 4321], [-16300, 30000, 20000], [5, 32767, -32768], [9999, -1, 1]]

    def test_rotators_and_matrices_round_trip(self):
        for r in self.ROTATORS:
            self.assertEqual(alb.whole(alb.rotator_of(alb.rotation_matrix(r))), alb.whole(r), r)
        for r in ([16384, 0, 0], [16384, 5000, 0], [-16384, 12000, 3000]):   # straight up or down
            same_turn(self, alb.whole(alb.rotator_of(alb.rotation_matrix(r))), r)

    def owners(self):
        yield transform([0, 0, 0], [0, 0, 0], [1, 1, 1])
        yield transform([1000, -2000, 300], [0, 8192, 0], [1, 1, 1])
        yield multiply(transform([-50, 70, 12.5], [1234, -5678, 910], [1, 1, 1]),
                       transform([40, -12, 25], [-3000, 7000, 500], [1, 1, 1]))
        yield multiply(transform([10, 20, 30], [0, 3000, 0], [2, 2, 2]), transform([5, 0, 0], [0, 0, 0], [1, 1, 1]))
        yield transform([0, 0, 0], [500, 21000, -9000], [1.5, 0.75, 2])                 # non-uniform scale
        yield transform([300, 0, 0], [0, 10000, 0], [-1, 1, 1])                          # mirrored

    def test_light_pose_inverts_local_pose(self):
        for owner in self.owners():
            for r in self.ROTATORS:
                where = [123.4, -567.8, 91.2]
                local = alb.local_pose(where, r, owner)
                location, rotation = alb.light_pose(local, owner)
                self.assertTrue(np.allclose(location, where, atol=1e-4), (owner, r))
                same_turn(self, rotation, r, places=3)
                self.assertEqual(rotation, alb.whole(r), (owner, r))

    def test_a_pose_copied_to_a_second_placement(self):
        component = transform([40, -12, 25], [-3000, 7000, 500], [1, 1, 1])
        first = multiply(transform([-50, 70, 12.5], [1234, -5678, 910], [1, 1, 1]), component)
        local = alb.local_pose([0, 15, 80], [-4000, 20000, 0], first)
        for pose in (([900, 900, 0], [0, 23456, 0]), ([-1, -2, 300], [700, -16000, 1500]), ([0, 0, 0], [0, 0, 0])):
            second = multiply(transform(*pose, [1, 1, 1]), component)
            location, rotation = alb.light_pose(local, second)
            delta = np.array(second) @ np.linalg.inv(np.array(first))
            self.assertTrue(np.allclose(location, delta[:3, :3] @ [0, 15, 80] + delta[:3, 3], atol=1e-4))
            same_turn(self, rotation, alb.rotator_of(delta[:3, :3] @ alb.rotation_matrix([-4000, 20000, 0])), places=3)
            # copying the copy: the same local pose, so the same set of lights per placement
            again = alb.local_pose(location, rotation, second)
            self.assertTrue(np.allclose(again['location'], local['location'], atol=1e-3))

    def test_mirrored_and_scaled_owners_carry_their_lights_rigidly(self):
        for owner in list(self.owners())[3:]:
            local = alb.local_pose([10, 20, 30], [1000, 2000, 3000], owner)
            move = transform([77, -88, 99], [3000, -7000, 1200], [1, 1, 1])
            location, rotation = alb.light_pose(local, multiply(move, owner))
            m = np.array(move)
            self.assertTrue(np.allclose(location, m[:3, :3] @ [10, 20, 30] + m[:3, 3], atol=1e-4))
            same_turn(self, rotation, alb.rotator_of(m[:3, :3] @ alb.rotation_matrix([1000, 2000, 3000])), places=3)


class EvidenceTests(unittest.TestCase):
    def test_material_evidence(self):
        self.assertIn('EmsValue', alb.material_evidence(dict(name='ClawMachine.Materials.ClawMachine',
                                                             scalars=dict(EmsValue=2.0, RefValue=0.3))))
        self.assertIsNone(alb.material_evidence(dict(name='BarDeco.Materials.Pennants', scalars=dict(EmsValue=0))))
        self.assertIn('Spc_Ems_Ref_Opc', alb.material_evidence(dict(render=dict(emissiveParameter='Spc_Ems_Ref_Opc'))))
        self.assertEqual(alb.material_evidence(dict(vectors={'EmsColor_EmsValue': [1, 0.3, 0.2, 3]})), 'EmsColor_EmsValue')
        self.assertIsNone(alb.material_evidence(dict(name='TexLibrary.Materials.Brick', scalars=dict(TileXY=1.0),
                                                     textureParameters={'Diffuse': 'x'})))
        self.assertIsNone(alb.material_evidence(None))


@unittest.skipUnless(BAR and BAR.exists(), 'URB_Bar.upk of the game install (the game setting) not found')
class OnTheBar(unittest.TestCase):
    """URB_Bar's 137 area lights, from records the export makes (its textures skipped), read from the install."""

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory(prefix='area-lights-') as folder:
            cls.p, cls.records = alb.export_records(BAR, folder)
        cls.result = cls.match(cls.records)
        cls.lights = {alb.short(l['actor']): l for l in cls.records['lights']}

    @classmethod
    def match(cls, records):
        return alb.associate(cls.p, records['objects'], records['lights'], records['meshes'], records['materials'])

    def attachment(self, name, result=None):
        return (result or self.result)['attachments'][self.lights[name]['id']]

    def test_every_area_light_is_verified_and_stable(self):
        self.assertEqual(alb.summary(self.result), {'verified': 137})
        self.assertEqual(self.result['thresholds']['levelScale'], 0.5)
        self.assertEqual(json.dumps(self.match(self.records), sort_keys=True), json.dumps(self.result, sort_keys=True))

    def test_hand_checked_owners(self):
        owners = {'GeneratedMeshAreaLight_370': 'XComDestructibleActor_316',   # the claw machine's front
                  'GeneratedMeshAreaLight_401': 'XComDestructibleActor_316',   # its slanted top, normal against
                  'GeneratedMeshAreaLight_403': 'XComDestructibleActor_340',   # the arcade machine's screen
                  'GeneratedMeshAreaLight_413': 'XComDestructibleActor_340',   # an arcade light pointing up by its base
                  'GeneratedMeshAreaLight_433': 'XComDestructibleActor_425',   # a ceiling lamp
                  'GeneratedMeshAreaLight_442': 'XComDestructibleActor_448',   # a flood light (settings inherited)
                  'GeneratedMeshAreaLight_447': 'XComDestructibleActor_267',   # a neon sign, not the wall behind it
                  'GeneratedMeshAreaLight_457': 'XComDestructibleActor_319',   # neon sign C, not B 56 units off
                  'GeneratedMeshAreaLight_483': 'XComLevelActor_259',          # a street light's lamp
                  'GeneratedMeshAreaLight_495': 'XComLevelActor_250'}
        for light, actor in owners.items():
            a = self.attachment(light)
            self.assertEqual((a['status'], alb.short(a['owner']['target']['actor'])), ('verified', actor), light)
            self.assertEqual(a['owner']['target']['package'], 'URB_Bar')
        counts = {}
        for a in self.result['attachments'].values():
            counts[alb.short(a['owner']['target']['actor'])] = counts.get(alb.short(a['owner']['target']['actor']), 0) + 1
        self.assertEqual({k: counts[k] for k in ('XComDestructibleActor_316', 'XComDestructibleActor_340',
                                                 'XComLevelActor_250', 'XComLevelActor_259')},
                         {'XComDestructibleActor_316': 33, 'XComDestructibleActor_340': 30,
                          'XComLevelActor_250': 12, 'XComLevelActor_259': 12})

    def test_repeated_flood_lights_carry_the_same_local_pose(self):
        poses = [a['local'] for a in self.result['attachments'].values()
                 if alb.short(a['owner']['target']['actor']) in ('XComDestructibleActor_443', 'XComDestructibleActor_445',
                                                                 'XComDestructibleActor_446', 'XComDestructibleActor_447',
                                                                 'XComDestructibleActor_448')]
        self.assertEqual(len(poses), 5)
        # within a fifth of a unit and a tenth of a degree: XComDestructibleActor_447, turned another way from the
        # other four, was baked 0.17 units and 11 rotator units off theirs
        for pose in poses[1:]:
            self.assertTrue(np.allclose(pose['location'], poses[0]['location'], atol=0.2))
            same_turn(self, pose['rotation'], poses[0]['rotation'], places=2)

    def test_light_pose_reproduces_every_light(self):
        for light_id, a in self.result['attachments'].items():
            light = next(l for l in self.records['lights'] if l['id'] == light_id)
            location, rotation = alb.light_pose(a['local'], a['ownerMatrix'])
            self.assertTrue(np.allclose(location, light['location'], atol=1e-3), light['actor'])
            same_turn(self, rotation, light['rotation'], places=3)

    def test_a_missing_owner_leaves_its_lights_unmatched_not_given_to_a_neighbour(self):
        records = copy.copy(self.records)
        records['objects'] = [o for o in self.records['objects'] if alb.short(o['actor']) != 'XComDestructibleActor_316']
        result = self.match(records)
        claw = [light_id for light_id, a in self.result['attachments'].items()
                if alb.short(a['owner']['target']['actor']) == 'XComDestructibleActor_316']
        self.assertEqual(len(claw), 33)
        self.assertEqual({result['attachments'][i]['status'] for i in claw}, {'unmatched'})
        self.assertEqual(alb.summary(result), {'verified': 104, 'unmatched': 33})
        # the arcade machine beside it glows too, but with falloff 5, not the claw machine's 10
        self.assertTrue(any("settings differ" in result['attachments'][i]['reason'] for i in claw))

    def test_a_copy_standing_in_the_original_makes_it_ambiguous(self):
        records = copy.copy(self.records)
        flood = next(o for o in self.records['objects'] if alb.short(o['actor']) == 'XComDestructibleActor_448'
                     and o['mesh'] and not o.get('hidden'))
        twin = dict(flood, id='twin', actor='TheWorld.PersistentLevel.XComDestructibleActor_9999',
                    location=[v + d for v, d in zip(flood['location'], (3, 0, 0))])
        records['objects'] = self.records['objects'] + [twin]
        a = self.attachment('GeneratedMeshAreaLight_442', self.match(records))
        self.assertEqual(a['status'], 'ambiguous', a['reason'])
        self.assertEqual({alb.short(c['actor']) for c in a['candidates'] if c['supported']},
                         {'XComDestructibleActor_448', 'XComDestructibleActor_9999'})


if __name__ == '__main__':
    unittest.main()
