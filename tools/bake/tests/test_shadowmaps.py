"""Dominant-light shadow maps (shadowmaps.py) and their G8 writer (lighting_fixture.py gray)."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import shadowmaps as sm  # noqa: E402
import lighting_fixture as fx  # noqa: E402
import lightmap_fields  # noqa: E402
import audit_lighting as lighting  # noqa: E402
from texture import decompress_payload  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')


def flat_geo(w, h, spacing=1.0, islands=False):
    """A flat strip of sub-samples on a w x h grid, `spacing` apart; with `islands`, the lower half of the rows lies
    1000 units away in the world, as a second UV island packed beside the first."""
    py, px = np.mgrid[0:h, 0:w]
    world = np.stack([px * spacing, py * spacing, np.zeros_like(px, float)], -1).reshape(-1, 3).astype(float)
    if islands:
        world[(py >= h // 2).ravel(), 1] += 1000.0
    return dict(rect=(0, 0, w, h), px=px.ravel(), py=py.ravel(), world=world)


class Field(unittest.TestCase):
    def test_signed_distance_is_linear_across_a_straight_edge(self):
        geo = flat_geo(80, 8)
        g = sm.grid(geo)
        light = g['covered'] & (np.arange(80)[None, :] >= 40)
        d = sm.signed_distance(g, light, transition=10.0)
        # the edge lies between x 39 and 40: distances run x - 39.5 within the window, then stop at 2 x transition
        for x in (34, 38, 39, 40, 41, 45, 49):
            self.assertAlmostEqual(d[3, x], x - 39.5, places=6, msg=x)
        self.assertEqual(d[3, 0], -20.0)
        self.assertEqual(d[3, 79], 20.0)
        v = sm.encode(d, 10.0)
        self.assertAlmostEqual(v[3, 40], 0.525)
        self.assertEqual(v[3, 79], 1.0)

    def test_stretched_texels_measure_world_distance(self):
        g = sm.grid(flat_geo(40, 8, spacing=3.0))
        self.assertEqual(g['spacing'], [3.0, 3.0])
        light = g['covered'] & (np.arange(40)[None, :] >= 20)
        d = sm.signed_distance(g, light, transition=25.0)
        self.assertAlmostEqual(d[2, 22], 7.5, places=6)    # 2.5 sub-samples of 3 units from the edge

    def test_islands_side_by_side_in_the_grid_do_not_see_each_other(self):
        geo = flat_geo(40, 8, islands=True)
        g = sm.grid(geo)
        light = np.zeros((8, 40), bool)
        light[:4] = True            # the first island is lit, the second (beside it in the grid) in shadow
        d = sm.signed_distance(g, light, transition=10.0)
        self.assertTrue((d[:4] == 20.0).all() and (d[4:] == -20.0).all())

    def test_texel_means_average_the_covered_sub_samples(self):
        values = np.arange(16, dtype=float).reshape(4, 4)
        covered = np.ones((4, 4), bool)
        covered[0, 0] = False
        mean, any_ = sm.texel_means(values, covered, upsample=2)
        self.assertAlmostEqual(mean[0, 0], (1 + 4 + 5) / 3)
        self.assertTrue(any_.all())

    def test_change_is_none_without_a_flip_and_local_with_one(self):
        geo = flat_geo(160, 160)
        before = np.ones(len(geo['world']), bool)
        self.assertIsNone(sm.change(geo, before, before.copy(), upsample=4, transition=10.0))
        after = before.copy()
        block = (geo['px'] >= 60) & (geo['px'] < 80) & (geo['py'] >= 60) & (geo['py'] < 80)
        after[block] = False        # a new shadow, 20 x 20 sub-samples
        delta, covered, flipped = sm.change(geo, before, after, upsample=4, transition=10.0)
        self.assertEqual(flipped, 400)
        self.assertEqual(delta.shape, (40, 40))
        self.assertLess(delta[17, 17], -0.9)               # inside the new shadow: from 1 to about 0
        self.assertEqual(delta[0, 0], 0.0)                 # far from it: nothing
        self.assertTrue((delta <= 1e-12).all())            # a new shadow only darkens


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarShadowMaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)

    def test_the_moon_and_the_asphalts_shadow_map(self):
        lights = sm.dominant_lights(self.p)
        self.assertEqual([l['actor'] for l in lights.values()], ['TheWorld.PersistentLevel.DominantDirectionalLight_1'])
        ci = self.p.by_name['TheWorld.PersistentLevel.XComLevelActor_275.StaticMeshComponent_414']
        (m,) = sm.shadow_maps(self.p, ci)
        self.assertIn(m['guid'], lights)
        self.assertFalse(m['factor'])
        top, t = sm.texture_top(self.p, m['texture'])
        self.assertEqual(top.shape, (1024, 1024))
        self.assertEqual(t['format'], 'PF_G8')

    def test_gray_writes_the_top_mip_and_rebuilds_the_lower_ones(self):
        name = 'ShadowMapTexture2D_322'
        index = self.p.by_name[name]
        old_top, old = sm.texture_top(self.p, index)
        values = np.full((16, 16), 0.5)
        mask = np.ones((16, 16), bool)
        mask[:2] = False
        with tempfile.TemporaryDirectory() as d:
            npz = Path(d) / 'g.npz'
            np.savez(npz, g=values, g_mask=mask)
            manifest = fx.run(BAR, Path(d) / 'out', 'URB_BarGray', [
                dict(op='gray', texture=name, x0=200, y0=248, npz=str(npz), key='g')], cache='Lighting_7004')
            q = lighting.Package(Path(d) / 'out' / 'URB_BarGray.upk')
            t = lightmap_fields.texture_fields(q, q.by_name[name])
            self.assertEqual(t['cache'], 'Lighting_7004')

            def mip(k):
                m = t['mips'][k]
                with open(Path(d) / 'out' / 'Lighting_7004.tfc', 'rb') as fh:
                    fh.seek(m['offset'])
                    raw = decompress_payload(fh.read(m['bytes']), m['flags'])
                return np.frombuffer(raw, np.uint8).reshape(m['height'], m['width'])

            top = mip(0)
            self.assertTrue((top[250:264, 200:216] == 128).all())
            self.assertTrue((top[248:250, 200:216] == old_top[248:250, 200:216]).all())
            changed = top != old_top
            changed[250:264, 200:216] = False
            self.assertFalse(changed.any())
            # mip 1 is the box average of the edited top mip: inside the patch, the patch's value
            self.assertEqual(mip(1)[128, 104], 128)
            self.assertTrue(any('gray ShadowMapTexture2D_322' in e['what'] for e in manifest['edits']))


# DLC1_1_LowFriends as shipped: one of its components names no static mesh but keeps a dominant-light shadow map
LOW_FRIENDS, NO_LOW_FRIENDS = labpaths.test_file('XCOM_LOWFRIENDS_UPK', labpaths.lwr_cooked('DLC1_1_LowFriends.upk'),
                                                 'DLC1_1_LowFriends.upk')
MESHLESS = 'TheWorld.PersistentLevel.XComLevelActor_16.StaticMeshComponent_166'


@unittest.skipUnless(LOW_FRIENDS and LOW_FRIENDS.exists(), NO_LOW_FRIENDS)
class MeshlessReceiver(unittest.TestCase):
    def test_a_component_with_no_mesh_is_no_receiver(self):
        import relight
        p = lighting.Package(LOW_FRIENDS)
        i = p.by_name[MESHLESS]
        self.assertEqual(p.effective(i, 'StaticMesh', 0), 0)
        self.assertTrue(sm.shadow_maps(p, i))       # it keeps a shadow map of the dominant light
        lights = {g: l for g, l in sm.dominant_lights(p).items() if l['enabled']}
        receivers = sm.dominant_receivers(p, lights)
        self.assertTrue(receivers)
        self.assertNotIn(MESHLESS, [path for path, *_ in receivers])
        # every receiver left has a box, as the relight's quick reach test asks for
        meshes = {}
        for path, ci, *_ in receivers:
            relight.component_box(p, ci, meshes)


if __name__ == '__main__':
    unittest.main()
