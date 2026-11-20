"""Dominant-light shadow maps (shadowmaps.py) and their G8 writer (lightmap_writer.py gray)."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import shadowmaps as sm  # noqa: E402
import lightmap_writer as fx  # noqa: E402
import lightmap_fields  # noqa: E402
import lighting_records as lighting  # noqa: E402
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


def old_signed_distance(g, light, transition=sm.TRANSITION, only=None):
    """shadowmaps.signed_distance as it was before the editor refactor's stage B6: a search from every to-do
    sub-sample through every offset of the window, the window's masks grown by a dilation by the whole box. The
    reference its rewrite gives bit for bit."""
    from scipy import ndimage
    covered, world = g['covered'], g['world']
    H, W = g['shape']
    reach = sm.reach_of(g, transition)
    shadowed, lit_ = covered & ~light, covered & light
    box = np.ones((2 * reach + 1, 2 * reach + 1), bool)
    near_shadow = ndimage.binary_dilation(shadowed, box) if shadowed.any() else np.zeros_like(covered)
    near_light = ndimage.binary_dilation(lit_, box) if lit_.any() else np.zeros_like(covered)
    todo = (lit_ & near_shadow) | (shadowed & near_light)
    if only is not None:
        todo &= only
    ty, tx = np.nonzero(todo)
    best = np.full(len(ty), np.inf)
    best_steps = np.ones(len(ty))
    if len(ty):
        tw = world[ty, tx]
        mine = light[ty, tx]
        pad = reach
        cov_p = np.pad(covered, pad)
        light_p = np.pad(light, pad)
        world_p = np.pad(world, ((pad, pad), (pad, pad), (0, 0)), constant_values=np.nan)
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                if not dy and not dx:
                    continue
                oy, ox = ty + dy + pad, tx + dx + pad
                other = cov_p[oy, ox] & (light_p[oy, ox] != mine)
                if not other.any():
                    continue
                dist = np.where(other, np.linalg.norm(world_p[oy, ox] - tw, axis=1), np.inf)
                closer = dist < best
                best[closer] = dist[closer]
                best_steps[closer] = max(abs(dy), abs(dx))
    d = np.full((H, W), 2 * transition)
    d[ty, tx] = np.minimum(best * (1 - 1 / (2 * best_steps)), 2 * transition)
    return np.where(light, d, -d)


def made_up_grid(rng, case):
    """A made-up sub-sample grid, its light and an `only` mask (or None), for the search against the old one: whole
    units (many equal distances), stretched texels with a second island beside the first, a bent and noisy surface,
    or coarse steps in height; holes; light scattered, cut by a line or with one shadowed block; every seventh case
    keeps light on uncovered sub-samples too."""
    H, W = int(rng.integers(1, 33)), int(rng.integers(1, 33))
    py, px = np.mgrid[0:H, 0:W]
    kind = case % 4
    if kind == 0:
        world = np.stack([px * 1.0, py * 1.0, np.zeros((H, W))], -1)
    elif kind == 1:
        world = np.stack([px * 3.0, py * 0.5, np.zeros((H, W))], -1)
        world[H // 2:, :, 1] += 1000.0
    elif kind == 2:
        world = np.stack([px * 2.0, py * 2.0, np.sin(px / 3.0) * 4.0], -1) + rng.normal(0, 0.3, (H, W, 3))
    else:
        world = np.stack([px * 4.0, py * 4.0, rng.integers(0, 3, (H, W)) * 4.0], -1)
    covered = rng.random((H, W)) < rng.uniform(0.3, 1.0)
    world[~covered] = np.nan
    pattern = case % 3
    if pattern == 0:
        light = rng.random((H, W)) < rng.uniform(0.1, 0.9)
    elif pattern == 1:
        light = (px * rng.normal() + py * rng.normal()) > rng.normal() * W
    else:
        light = np.ones((H, W), bool)
        y0, x0 = int(rng.integers(0, H)), int(rng.integers(0, W))
        light[y0:y0 + int(rng.integers(1, 12)), x0:x0 + int(rng.integers(1, 12))] = False
    if case % 7:
        light &= covered
    only = None
    if case % 5 == 0:
        only = rng.random((H, W)) < 0.5
    elif case % 5 == 1:
        only = np.zeros((H, W), bool)
        only[:H // 2] = True
    g = dict(covered=covered, world=world, shape=(H, W),
             spacing=[float(rng.choice([1.0, 2.0, 3.0, 4.0])), float(rng.choice([1.0, 2.0, 4.0]))])
    return g, light, float(rng.choice([2.0, 5.0, 10.0])), only


class SearchAsBefore(unittest.TestCase):
    """The distance search (signed_distance and its nearest_across) gives the old search's answer bit for bit."""

    def assertSame(self, got, want, msg=None):
        self.assertEqual(got.dtype, want.dtype, msg)
        self.assertTrue(np.array_equal(got, want), '%s: differs at %s' % (msg, np.argwhere(got != want)[:4].tolist()))

    def test_made_up_grids_give_the_old_answer(self):
        rng = np.random.default_rng(20261120)
        for case in range(40):
            g, light, transition, only = made_up_grid(rng, case)
            self.assertSame(sm.signed_distance(g, light, transition, only),
                            old_signed_distance(g, light, transition, only), 'case %d' % case)

    def test_of_equal_distances_the_first_offset_in_raster_order_gives_the_steps(self):
        # a lit sub-sample with two shadowed ones 5 units away: at (+3, +4), 4 steps, and at (+5, 0), 5 steps; the
        # first in raster order (dy first) is (+3, +4), so the distance is 5 less half of a fourth: 4.375
        py, px = np.mgrid[0:24, 0:24]
        world = np.stack([px * 1.0, py * 1.0, np.zeros((24, 24))], -1)
        only = np.zeros((24, 24), bool)
        only[10, 10] = True
        # with six more lit ones beside the shadowed two, the lit side is the larger: the search starts from the
        # shadowed ones and finds the lit one, which meets its offsets in reverse order
        for more_lit in (False, True):
            covered = np.zeros((24, 24), bool)
            covered[10, 10] = covered[13, 14] = covered[15, 10] = True
            light = np.zeros((24, 24), bool)
            light[10, 10] = True
            if more_lit:
                covered[16, 9:12] = covered[16, 13:16] = light[16, 9:12] = light[16, 13:16] = True
            g = dict(covered=covered, world=world, shape=(24, 24), spacing=[1.0, 1.0])
            d = sm.signed_distance(g, light, 10.0, only)
            self.assertEqual(d[10, 10], 4.375, more_lit)
            self.assertSame(d, old_signed_distance(g, light, 10.0, only), more_lit)
            self.assertSame(sm.signed_distance(g, light, 10.0), old_signed_distance(g, light, 10.0), more_lit)

    def test_near_is_the_dilation_by_the_whole_box(self):
        from scipy import ndimage
        rng = np.random.default_rng(7)
        for case in range(12):
            m = rng.random((int(rng.integers(1, 70)), int(rng.integers(1, 70)))) < [0.002, 0.05, 0.5][case % 3]
            reach = int(rng.integers(1, sm.MAX_REACH + 1))
            want = ndimage.binary_dilation(m, np.ones((2 * reach + 1, 2 * reach + 1), bool))
            self.assertSame(sm.near(m, reach), want, 'case %d' % case)


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
