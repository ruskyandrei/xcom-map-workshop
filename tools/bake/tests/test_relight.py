"""Per-texel geometry and the relight of a real map component (the bar's pool-table floor), when the map is here."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lightmap_texels  # noqa: E402
import native_lights  # noqa: E402
import relight  # noqa: E402
import lighting_records as lighting  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'


class Dilate(unittest.TestCase):
    def test_values_spread_into_unmasked_neighbours(self):
        values = np.zeros((5, 5, 1))
        mask = np.zeros((5, 5), bool)
        values[2, 2] = 1.0
        mask[2, 2] = True
        out, grown = lightmap_texels.dilate(values, mask, passes=1)
        self.assertTrue(grown[1:4, 1:4].all() and not grown[0].any())
        self.assertTrue((out[1:4, 1:4] == 1.0).all())
        out, grown = lightmap_texels.dilate(values, mask, passes=2)
        self.assertTrue(grown.all())


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ApplyChange(unittest.TestCase):
    def rule(self, original, before, after):
        o, b, a = (np.array([float(v)]) for v in (original, before, after))
        return float(relight.apply_change(o, b, a - b, np.clip(a / b, 0, 1))[0])

    def test_light_added_adds(self):
        self.assertAlmostEqual(self.rule(0.5, 0.2, 1.2), 1.5)

    def test_light_removed_where_our_model_accounts_for_it_scales(self):
        # our model has 4 of the original's 4; taking 3 away leaves a quarter of the original
        self.assertAlmostEqual(self.rule(4.0, 4.0, 1.0), 1.0)
        # it has 3.6 of 4 and takes 3 away: mostly scaled (0.67), a little subtracted (1.0)
        self.assertAlmostEqual(self.rule(4.0, 3.6, 0.6), 0.9 * 4 * 0.6 / 3.6 + 0.1 * 1.0, places=6)

    def test_light_removed_where_our_model_accounts_for_little_subtracts(self):
        # our model has 0.1 of the original's 2 and takes it all away: 1.9 is left, not 0
        self.assertAlmostEqual(self.rule(2.0, 0.1, 0.0), 0.05 * 0 + 0.95 * 1.9, places=6)

    def test_never_below_zero(self):
        # our model puts more of the light here than Lightmass did
        self.assertGreaterEqual(self.rule(1.0, 3.0, 0.0), 0.0)
        self.assertAlmostEqual(self.rule(1.0, 3.0, 1.5), 0.5)


class EditFromSpec(unittest.TestCase):
    def test_hides_are_removed_and_copies_added_at_their_poses(self):
        spec = dict(objects=[
            dict(type='copy', location=[0, 0, 0], **{'from': ['A_1', 'B_2']},
                 poses=[dict(location=[1, 2, 3], rotation=[0, 16384, 0]), dict(location=[4, 5, 6], rotation=[0, 0, 0])]),
            dict(type='hide', exact=True, location=[0, 0, 0], alsoHide=['B_2', 'A_1'])])
        remove, add = relight.edit_from_spec(spec)
        self.assertEqual(remove, ['A_1', 'B_2'])
        self.assertEqual(add, [dict(source='A_1', location=[1, 2, 3], rotation=[0, 16384, 0]),
                               dict(source='B_2', location=[4, 5, 6], rotation=[0, 0, 0])])

    def test_what_the_relight_does_not_model_is_refused(self):
        for obj in (dict(type='hide', location=[0, 0, 0]), dict(type='sun'), dict(type='copy', **{'from': ['A']})):
            with self.assertRaises(ValueError):
                relight.edit_from_spec(dict(objects=[obj]))


class EditReaches(unittest.TestCase):
    """The quick reach test, on boxes [x0, x1, y0, y1, z0, z1] and lights as relight's map_lights gives them."""
    CRATE = [0, 50, 0, 50, 0, 100]                          # an edit: a crate standing on the floor at the origin
    LAMP = dict(kind='point', location=[25, 25, 300], radius=2000, lightSourceRadius=10)

    def test_near_the_edit_its_bounce_counts(self):
        self.assertTrue(relight.edit_reaches([400, 420, 0, 50, 0, 10], [self.CRATE], []))
        self.assertFalse(relight.edit_reaches([500, 520, 0, 50, 0, 10], [self.CRATE], []))

    def test_a_shadow_reaches_as_far_as_it_falls(self):
        low = dict(self.LAMP, location=[-400, 25, 120])     # a low lamp throws the crate's shadow far along x
        floor_far = [900, 960, 0, 50, -2, 0]
        self.assertTrue(relight.edit_reaches(floor_far, [self.CRATE], [low]))
        # off to the side of the shadow, or with the lamp on the far side, it doesn't
        self.assertFalse(relight.edit_reaches([900, 960, 600, 650, -2, 0], [self.CRATE], [low]))
        self.assertFalse(relight.edit_reaches(floor_far, [self.CRATE], [dict(low, location=[2000, 25, 120])]))
        # a lamp out of range reaches nothing
        self.assertFalse(relight.edit_reaches(floor_far, [self.CRATE], [dict(low, radius=100)]))

    def test_a_directional_light_shadows_without_a_range(self):
        # a low sun (3 degrees up) throws the 100-tall crate's shadow about 1900 units along x, its penumbra further
        sun = dict(kind='directional', toLight=[-1, 0, 0.05], lightSourceAngle=1.0)
        self.assertTrue(relight.edit_reaches([1500, 1550, 0, 50, -2, 0], [self.CRATE], [sun]))
        self.assertFalse(relight.edit_reaches([4500, 4550, 0, 50, -2, 0], [self.CRATE], [sun]))
        self.assertFalse(relight.edit_reaches([-1550, -1500, 0, 50, -2, 0], [self.CRATE], [sun]))

    def test_a_removed_light_reaches_what_it_lit(self):
        self.assertTrue(relight.edit_reaches([3000, 3050, 0, 50, 0, 10], [], [], removed_lights=[dict(self.LAMP, location=[3000, 0, 300])]))
        self.assertFalse(relight.edit_reaches([3000, 3050, 0, 50, 0, 10], [], [], removed_lights=[self.LAMP]))

    def test_segments_meet_box(self):
        box = [0, 10, 0, 10, 0, 10]
        o = np.array([[-5.0, 5, 5], [-5, 20, 5], [5, 5, 5]])
        e = np.array([[15.0, 5, 5], [15, 20, 5], [6, 6, 6]])
        self.assertTrue(relight.segments_meet_box(o[:1], e[:1], box))
        self.assertFalse(relight.segments_meet_box(o[1:2], e[1:2], box))
        self.assertTrue(relight.segments_meet_box(o[2:], e[2:], box))        # inside it
        self.assertFalse(relight.segments_meet_box(np.array([[-5.0, 5, 5]]), np.array([[-1.0, 5, 5]]), box))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class PoolTableFloor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        cls.r = relight.relight_component(cls.p, FLOOR)

    def test_texels_lie_on_the_floor_with_unit_frames(self):
        ci = self.p.by_name[FLOOR]
        fields = self.r['fields']
        geo = lightmap_texels.rasterise(lightmap_texels.component_mesh(self.p, ci),
                                        lightmap_texels.world_matrix(self.p, ci), fields, [1024, 1024])
        self.assertEqual(geo['rect'], (369, 1, 671, 303))
        self.assertEqual(len(geo['px']), 73495)
        frames = geo['frames']
        self.assertLess(np.abs(np.einsum('nij,nkj->nik', frames, frames) - np.eye(3)).max(), 1e-9)
        top = frames[:, 2, 2] > 0.99
        self.assertGreater(top.mean(), 0.95)
        # the top face: actor turned -90 degrees in yaw, so tangent (local +X) is world -Y and binormal world +X
        # packed byte normals and tangents carry +-0.004 of noise
        self.assertTrue(np.allclose(np.median(frames[top, 0], 0), [0, -1, 0], atol=0.01))
        self.assertTrue(np.allclose(np.median(frames[top, 1], 0), [1, 0, 0], atol=0.01))
        world = geo['world'][top]
        self.assertTrue(np.allclose(world[:, 2], 16, atol=2.5))
        self.assertTrue(world[:, 0].min() >= -480.5 and world[:, 0].max() <= 768.5)

    def test_all_lights_matched_and_lit_areas_match_the_original_bake(self):
        rep = self.r['report']
        self.assertEqual((rep['lights']['guids'], rep['lights']['matched']), (52, 52))
        self.assertEqual(rep['lights']['sourceRadii'], [32.0])
        self.assertGreater(rep['flatLight']['correlation'], 0.85)
        # where the original is brightest (light pools, no shadow) the relit floor is within 5% of it
        b, a, cov = self.r['before'].sum(2), self.r['after'].sum(2), self.r['covered']
        top = cov & (b >= np.percentile(b[cov], 97))
        self.assertAlmostEqual(float(np.median(a[top] / b[top])), 1.0, delta=0.05)

    def test_images_cover_the_rectangle_and_stay_in_range(self):
        imgs = self.r['images']
        for key in ('nac', 'dmc'):
            self.assertEqual(imgs[key].shape, (302, 302, 3))
            self.assertTrue(imgs[key + '_mask'][self.r['covered']].all())
            self.assertTrue((imgs[key] >= 0).all() and (imgs[key] <= 1 + 1e-9).all())
        self.assertAlmostEqual(float(imgs['nac'][self.r['covered']].max()), 1.0, places=6)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class NoTexel(unittest.TestCase):
    def test_a_piece_that_covers_no_texel_is_left_out_whatever_the_scene(self):
        # (review finding 44) a direct-only relight (no scene) of a piece whose charts cover no texel of its lightmap
        # (the floor here, its rasterising emptied) is an exclusion, not an AttributeError
        empty = dict(px=np.zeros(0, int), py=np.zeros(0, int), world=np.zeros((0, 3)), frames=np.zeros((0, 3, 3)),
                     triangle=np.zeros(0, int), rect=(0, 0, 0, 0))
        p = lighting.Package(BAR)
        with mock.patch.object(relight.lightmap_texels, 'rasterise', lambda *a, **k: empty):
            with self.assertRaisesRegex(relight.Excluded, 'covers no texel'):
                relight.relight_component(p, FLOOR, None)


@unittest.skipUnless(BAR and BAR.exists() and (BAR.parent / 'Lighting.tfc').exists(), NO_BAR + ' (with Lighting.tfc)')
class ComponentList(unittest.TestCase):
    def test_list_relights_what_it_can_and_records_the_rest(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            listing = tmp / 'components.txt'
            listing.write_text(f'# the floor, then a name the map does not have\n{FLOOR}  # pool-table floor\n'
                               'TheWorld.PersistentLevel.NoSuchActor.StaticMeshComponent_0\n', encoding='utf-8')
            argv = sys.argv
            sys.argv = ['relight.py', str(BAR), str(tmp / 'out'), 'URB_BarListTest', '--cache', 'Lighting_7099',
                        '--component-list', str(listing), '--direct-only']
            try:
                relight.main()
            finally:
                sys.argv = argv
            record = json.loads((tmp / 'out' / 'URB_BarListTest.relight.json').read_text(encoding='utf-8'))
            self.assertEqual([c['component'] for c in record['components']], [FLOOR])
            self.assertEqual([s['component'] for s in record['skipped']],
                             ['TheWorld.PersistentLevel.NoSuchActor.StaticMeshComponent_0'])
            self.assertTrue((tmp / 'out' / 'URB_BarListTest.upk').exists())


PL = 'TheWorld.PersistentLevel.'


# ---------------------------------------------------------------- synthetic: the relight's light states

def codec(name, guid, brightness=1.0, enabled=True, role='static', location=(0.0, 0.0, 100.0), radius=500.0):
    return dict(kind='point', actor=PL + name, component=PL + name + '.C', brightness=brightness, color=[1, 1, 1],
                enabled=enabled, role=role, guid=guid, guids=[guid, guid.upper()], location=list(location),
                radius=radius, falloffExponent=2.0, lightSourceRadius=32.0)


class LightStates(unittest.TestCase):
    def setUp(self):
        self.map = [codec('A', 'aa'), codec('B', 'bb'), codec('New', 'nn', brightness=3.0)]
        patch = mock.patch.object(relight, 'map_lights', lambda p, guids=None, roles=None: list(self.map))
        patch.start()
        self.addCleanup(patch.stop)

    def test_before_and_after_come_from_the_edits_and_the_rest_from_the_map(self):
        changed = codec('A', 'aa', brightness=2.0)
        doc = dict(edits=[dict(op='change', name='A', component=PL + 'A.C', before=codec('A', 'aa'), after=changed),
                          dict(op='add', name='New', component=PL + 'New.C', before=None, after=codec('New', 'nn', 3.0))],
                   registered={PL + 'R.C': ['nn']})
        s = relight.resolve_light_states(None, doc)
        before = {l['component']: l for l in s['before']}
        after = {l['component']: l for l in s['after']}
        self.assertEqual(before[PL + 'A.C']['brightness'], 1.0)
        self.assertEqual(after[PL + 'A.C']['brightness'], 2.0)
        self.assertNotIn(PL + 'New.C', before)
        self.assertIn(PL + 'New.C', after)
        self.assertEqual(s['registered'], {PL + 'R.C': ['nn']})
        # --remove-light is one more edit
        s = relight.resolve_light_states(None, doc, ['B'])
        self.assertNotIn(PL + 'B.C', {l['component'] for l in s['after']})
        self.assertIn(PL + 'B.C', {l['component'] for l in s['before']})
        self.assertEqual(s['edits'][-1]['op'], 'remove')
        with self.assertRaisesRegex(ValueError, 'no baked light'):
            relight.resolve_light_states(None, doc, ['Nothing_1'])
        with self.assertRaisesRegex(ValueError, 'lacks'):
            relight.resolve_light_states(None, dict(edits=[dict(op='delete', name='Gone', component=PL + 'Gone.C',
                                                                before=codec('Gone', 'gg'), after=None)]))

    def test_a_receivers_lights_resolve_through_its_states_registry(self):
        before = [codec('A', 'aa'), codec('B', 'bb')]
        after = [codec('A', 'aa', brightness=2.0), codec('New', 'nn')]
        sb = type('S', (), {})()
        sb.registry, sb.registered = before, {PL + 'R.C': {'nn'}}
        sa = type('S', (), {})()
        sa.registry, sa.registered = after, {}
        listed = ['aa', 'BB', 'nn']                 # a lightmap may list either GUID of a light
        self.assertEqual([l['brightness'] for l in relight.Scene.listed(sa, listed)], [2.0, 1.0])
        self.assertEqual([l['component'] for l in relight.Scene.listed(sb, listed)], [PL + 'A.C', PL + 'B.C'])
        # the GUID the build added to R is not in its original list: the new light invents nothing before
        self.assertEqual(relight.Scene.original_guids(sb, PL + 'R.C', listed), ['aa', 'BB'])
        self.assertEqual(relight.Scene.original_guids(sb, PL + 'Other.C', listed), listed)


class ChangedReach(unittest.TestCase):
    """edit_reaches with the lights of an edit before and after (plan 4.4, regression case 4)."""
    SPOT = dict(kind='spot', location=[0.0, 0.0, 300.0], radius=600.0, brightness=1.0, enabled=True,
                direction=[0, 0, -1], innerConeAngle=0, outerConeAngle=30, lightSourceRadius=32)
    OLD = [100, 150, 0, 50, 0, 10]          # a receiver the spot lit
    FAR = [2000, 2050, 0, 50, 0, 10]

    def reaches(self, box, *lights):
        return relight.edit_reaches(box, [], [], edited=[l for l in lights if l])

    def test_rotating_narrowing_dimming_or_switching_off_revisits_the_old_receivers(self):
        for after in (dict(self.SPOT, direction=[1, 0, 0]), dict(self.SPOT, outerConeAngle=10),
                      dict(self.SPOT, enabled=False), dict(self.SPOT, radius=50.0), dict(self.SPOT, brightness=0.0),
                      dict(self.SPOT, falloffExponent=8), None):
            self.assertTrue(self.reaches(self.OLD, self.SPOT, after), after)
        self.assertFalse(self.reaches(self.FAR, self.SPOT, dict(self.SPOT, brightness=3)))

    def test_moving_or_widening_reaches_the_new_receivers(self):
        self.assertTrue(self.reaches(self.FAR, self.SPOT, dict(self.SPOT, location=[2000.0, 0.0, 300.0])))
        self.assertTrue(self.reaches(self.FAR, self.SPOT, dict(self.SPOT, radius=2100.0)))
        # within REACH_NEAR of the radius: its bounce can show there; beyond it, nothing
        self.assertTrue(self.reaches([900, 950, 0, 50, 0, 10], self.SPOT))
        self.assertFalse(self.reaches([1000, 1050, 0, 50, 0, 10], self.SPOT))

    def test_a_light_that_emits_nothing_reaches_nothing(self):
        off = dict(self.SPOT, enabled=False)
        self.assertFalse(self.reaches(self.OLD, None, off))
        self.assertFalse(self.reaches(self.OLD, dict(self.SPOT, brightness=0.0)))
        self.assertEqual([relight.light_box(l) for l in (self.SPOT,)], [[-600, 600, -600, 600, -300, 900]])


class Unchanged(unittest.TestCase):
    def test_an_unchanged_relight_ships_the_edited_map_with_no_cache(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'grown' / 'URB_Bar.upk'
            src.parent.mkdir()
            src.write_bytes(b'the edited map')
            m = relight.unchanged_fixture(src, d, 'URB_BarX')
            dst = Path(d) / 'URB_BarX.upk'
            self.assertEqual(dst.read_bytes(), b'the edited map')
            self.assertEqual((m['cache'], m['edits'], m['lightingUnchanged']), (None, [], True))
            self.assertEqual(m['outputs'], {str(dst): hashlib.sha256(b'the edited map').hexdigest()})
            self.assertEqual(json.loads((Path(d) / 'URB_BarX.fixture.json').read_text(encoding='utf-8')), m)
            self.assertEqual(list(Path(d).glob('*.tfc')), [])


def stub_scene(calls):
    """relight.Scene stood in for (no casters, no Embree): it records what each state was built from."""
    class Stub:
        def __init__(self, p, lights=None, registered=None, note=None, remove_casters=(), add_casters=(),
                     remove_lights=(), **kw):
            calls.append(dict(lights=lights, registered=registered, note=note))
            self.registry = list(lights) if lights is not None else []
            self.registered = {k: set(v) for k, v in (registered or {}).items()}
            self.lights = [l for l in self.registry if l['enabled'] and l['role'] in relight.BAKED_ROLES]
            self.area_lights, self.copies, self.edit_boxes, self.light_boxes = [], [], [], []
            self.counts, self.level_scale, self.environment = {'casters': 0}, 1.0, np.zeros(3)
            self.edit = dict(removeCasters=sorted(remove_casters), removeLights=sorted(remove_lights), addCasters=[])
            self.edit.update(note or {})

        def keeps(self, light):
            return True
    return Stub


@unittest.skipUnless(BAR and BAR.exists() and (BAR.parent / 'Lighting.tfc').exists(), NO_BAR + ' (with Lighting.tfc)')
class RelightLightEdits(unittest.TestCase):
    """relight.py --light-edits on the bar itself standing in for a grown map (a change of a light the map has),
    with the scenes stubbed: the edit's reach, a failure that stays a failure, an exclusion that doesn't, and the
    states each worker gets."""

    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        reg = native_lights.source_registry(cls.p)
        e = reg['SpotLight_53']
        state = dict(ops=[dict(op='change', name=e['id'], label=e['id'], kind='spot', role='static', before=e,
                               after=dict(e, raw=dict(e['raw'], brightness=3.0)))])
        cls.doc = native_lights.relight_edits(state, {})

    def run_main(self, d, extra=(), raise_as=None):
        edits = Path(d) / 'edits.json'
        edits.write_text(json.dumps(self.doc), encoding='utf-8')
        calls = []

        def broken(p, path, scene=None, checker=None, after=None, source=None, **kw):
            raise raise_as(f'{path}: injected')
        argv = ['relight.py', str(BAR), str(Path(d) / 'out'), 'URB_BarRL', '--cache', 'Lighting_7124',
                '--light-edits', str(edits), '--receivers-near', '0', '--no-shadow-maps', '--jobs', '1', *extra]
        with mock.patch.object(relight, 'Scene', stub_scene(calls)), \
                mock.patch.object(relight, 'relight_component', broken), mock.patch.object(sys, 'argv', argv):
            relight.main()
        return calls

    def test_a_receiver_that_fails_to_relight_fails_the_edit_and_an_exclusion_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as stop:
                self.run_main(d, raise_as=RuntimeError)
            self.assertIn('failed to relight', str(stop.exception.code))
            self.assertFalse((Path(d) / 'out' / 'URB_BarRL.upk').exists())
        with tempfile.TemporaryDirectory() as d:
            calls = self.run_main(d, raise_as=relight.Excluded)
            rec = json.loads((Path(d) / 'out' / 'URB_BarRL.relight.json').read_text(encoding='utf-8'))
            self.assertTrue(rec['lightingUnchanged'])
            self.assertEqual((rec['components'], rec['cache'], rec['failed']), ([], None, 0))
            self.assertTrue(rec['skipped'] and not any(s.get('failed') for s in rec['skipped']))
            (edit,) = rec['lightEdits']
            self.assertEqual((edit['op'], edit['before']['brightness'], edit['after']['brightness']),
                             ('change', 1.5, 3.0))
            # the spot's radius before and after, apart from the geometry's (none here)
            self.assertEqual(rec['editBoxes'], [])
            self.assertEqual(len(rec['lightBoxes']), 2)
            # both states built from the document: the changed light with its values, the rest from the map
            before, after = calls
            b = {l['component']: l for l in before['lights']}
            a = {l['component']: l for l in after['lights']}
            c = self.doc['edits'][0]['component']
            self.assertEqual((b[c]['brightness'], a[c]['brightness']), (1.5, 3.0))
            self.assertEqual(set(b), set(a))
            self.assertEqual(after['note']['lightEdits'], ['change SpotLight_53'])
            self.assertEqual(json.loads((Path(d) / 'out' / 'URB_BarRL.fixture.json').read_text(
                encoding='utf-8'))['cache'], None)
            self.assertEqual(list((Path(d) / 'out').glob('*.tfc')), [])

    def test_remove_light_is_one_case_of_the_edit_list(self):
        with tempfile.TemporaryDirectory() as d:
            edits = Path(d) / 'none.json'
            calls = []
            argv = ['relight.py', str(BAR), str(Path(d) / 'out'), 'URB_BarRM', '--cache', 'Lighting_7126',
                    '--remove-light', 'SpotLight_3', '--receivers-near', '0', '--no-shadow-maps', '--jobs', '1']

            def excluded(p, path, scene=None, checker=None, after=None, source=None, **kw):
                raise relight.Excluded('kept')
            with mock.patch.object(relight, 'Scene', stub_scene(calls)), \
                    mock.patch.object(relight, 'relight_component', excluded), mock.patch.object(sys, 'argv', argv):
                relight.main()
            del edits
            rec = json.loads((Path(d) / 'out' / 'URB_BarRM.relight.json').read_text(encoding='utf-8'))
            (edit,) = rec['lightEdits']
            self.assertEqual((edit['op'], edit['after']), ('remove', None))
            self.assertEqual(rec['edit']['removeLights'], ['SpotLight_3'])
            before, after = calls
            spot = 'TheWorld.PersistentLevel.SpotLight_3.SpotLightComponent_90'
            self.assertIn(spot, {l['component'] for l in before['lights']})
            self.assertNotIn(spot, {l['component'] for l in after['lights']})

    def test_workers_get_the_resolved_states_as_they_are(self):
        # a worker builds its scenes from the arguments the main process passes, never from the grown map's lights
        states = relight.resolve_light_states(self.p, self.doc)
        calls = []
        with mock.patch.object(relight, 'Scene', stub_scene(calls)), \
                mock.patch.object(relight.lighting, 'Package', lambda path: 'the map'):
            relight._worker_start(str(BAR), dict(samples=4), dict(lights=states['before'], registered={'x': ['y']}),
                                  dict(lights=states['after']), None)
        self.assertEqual([c['lights'] for c in calls], [states['before'], states['after']])
        self.assertEqual(calls[0]['registered'], {'x': ['y']})

if __name__ == '__main__':
    unittest.main()
