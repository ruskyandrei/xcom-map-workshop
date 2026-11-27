"""A turned sun's shadows made again for the whole map (sun_bake.py, run by relight.py --sun-turned; the game-likeness
plan's T-S4): the light's frame and box, its map of the level traced and written, the lighting samples' marks, the
whole map's shadow-map jobs, on made-up geometry and records, on the install's URB_Bar as it is, and on a scratch copy
of URB_Bar with its moon turned, relit and read back."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import relight  # noqa: E402  (sets up the tool paths)
import lighting_records as lighting  # noqa: E402
import shadowmaps  # noqa: E402
import shadows  # noqa: E402
import sun_bake  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
PL = 'TheWorld.PersistentLevel.'
MOON = PL + 'DominantDirectionalLight_1.DominantDirectionalLightComponent_0'
TURNED = [-2912, 16384, 0]      # the moon turned to a low sun from the west (16 degrees up)


def quads(*rects):
    """Triangles of horizontal rectangles (x0, x1, y0, y1, z), two each, for an occluder."""
    tris = []
    for x0, x1, y0, y1, z in rects:
        a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
        tris += [(a, b, c), (a, c, d)]
    return np.array(tris, np.float32)


class Frame(unittest.TestCase):
    def test_a_light_from_above_takes_the_worlds_x(self):
        w2l, l2w = sun_bake.light_frame([0.0, 0.0, -1.0])
        np.testing.assert_allclose(l2w, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]], atol=1e-12)
        np.testing.assert_allclose(w2l, l2w.T)

    def test_the_axes_are_square_and_the_matrices_inverses(self):
        for d in ([-0.11, 0.12, -0.99], [0.3, -0.9, -0.3], [0.96, 0.0, -0.27], [0.0, -0.96, -0.28]):
            w2l, l2w = sun_bake.light_frame(d)
            np.testing.assert_allclose(l2w[:3, :3] @ l2w[:3, :3].T, np.eye(3), atol=1e-12)
            np.testing.assert_allclose(w2l @ l2w, np.eye(4), atol=1e-12)
            np.testing.assert_allclose(l2w[2, :3], np.asarray(d) / np.linalg.norm(d))
            # y is x cross z, as UE3 takes it: a left-handed basis
            self.assertAlmostEqual(np.linalg.det(l2w[:3, :3]), -1.0, places=9)

    def test_a_low_light_takes_the_worlds_z(self):
        # nearer the level than the vertical: x is the world's z made square to the light
        w2l, l2w = sun_bake.light_frame([0.0, -0.96, -0.28])
        z = np.array([0.0, 0.0, 1.0])
        d = np.array([0.0, -0.96, -0.28]) / np.linalg.norm([0.0, -0.96, -0.28])
        x = z - d * z.dot(d)
        np.testing.assert_allclose(l2w[0, :3], x / np.linalg.norm(x))

    def test_the_box_is_the_world_boxs_corners_in_light_space(self):
        w2l, _ = sun_bake.light_frame([0.0, 0.0, -1.0])
        self.assertEqual(sun_bake.light_box([-10, -20, -5], [30, 40, 50], w2l), [-10, -20, -50, 30, 40, 5])
        # a quarter turn about z (light x the world's y, light y the world's -x): the world's x and y trade places
        turn = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float)
        self.assertEqual(sun_bake.light_box([0, 0, 0], [10, 20, 30], turn), [0, -10, 0, 20, 0, 30])

    def test_the_wanted_size_is_a_texel_of_a_hundred_units_times_the_scale(self):
        self.assertEqual(sun_bake.wanted_size([-3647.4, -2350.6, 0, 2959.2, 2536.5, 1], 0.5), [132, 97])
        self.assertEqual(sun_bake.wanted_size([0, 0, 0, 100, 900, 1], 1.0), [4, 9])


class LevelDepths(unittest.TestCase):
    """level_depths on made-up geometry: a ground at z 0 that ends at y 440, a roof at z 100 over x -40 to 240, the
    light straight down over a box of 11 x 11 texels of 100 units (rays at x and y -500 + 25 k)."""

    def setUp(self):
        self.occluder = shadows.Occluder(quads((-1000, 1000, -1000, 440, 0.0), (-40, 240, -1000, 1000, 100.0)))
        w2l, self.l2w = sun_bake.light_frame([0.0, 0.0, -1.0])
        self.bounds = sun_bake.light_box([-500, -500, -50], [500, 500, 300], w2l)     # z from -300 to 50: 350 deep

    def test_each_texel_takes_its_deepest_ray(self):
        depths, missed = sun_bake.level_depths(self.occluder, self.l2w, self.bounds, [11, 11])
        grid = depths.reshape(11, 11)
        ground, roof = round(300 / 350 * 65535), round(200 / 350 * 65535)
        # texels 5 and 6 (x 0 to 100, 100 to 200, both ends) lie wholly under the roof; texel 4 (-100 to 0) and 7
        # (200 to 300) reach past it, and take the ground
        self.assertEqual(list(grid[0]), [ground] * 5 + [roof] * 2 + [ground] * 4)
        self.assertEqual(list(grid[8]), list(grid[0]))
        # rows 9 (y 400 to 500) and 10 (500 to 600) have rays past the ground's end: the far face, but under the roof,
        # where every ray hits the roof
        self.assertEqual(list(grid[10]), [65535] * 5 + [roof] * 2 + [65535] * 4)
        self.assertEqual(list(grid[9]), list(grid[10]))
        # the rays that met nothing: 3 rows of rays of row 9 and 5 of row 10, each with 41 of its 55 out of the roof
        self.assertEqual(missed, (3 + 5) * 41)

    def test_a_box_with_no_depth_is_refused(self):
        with self.assertRaises(ValueError):
            sun_bake.level_depths(self.occluder, self.l2w, [-1, -1, 5, 1, 1, 5], [4, 4])


class Marks(unittest.TestCase):
    def test_a_point_under_a_roof_is_out_of_the_light(self):
        occluder = shadows.Occluder(quads((0, 100, 0, 100, 200.0)))
        points = np.array([[50.0, 50.0, 0.0], [250.0, 50.0, 0.0], [50.0, 50.0, 250.0], [-50.0, 50.0, 0.0]])
        np.testing.assert_array_equal(sun_bake.shadowed_points(occluder, points, [[0.0, 0.0, 1.0]]),
                                      [True, False, False, False])
        # a light 45 degrees up in the west (-x): the roof's shadow falls 200 units east of it, on the second point;
        # with both lights, a point out of either is marked
        low = [-1.0, 0.0, 1.0]
        np.testing.assert_array_equal(sun_bake.shadowed_points(occluder, points, [low]), [False, True, False, False])
        np.testing.assert_array_equal(sun_bake.shadowed_points(occluder, points, [[0.0, 0.0, 1.0], low]),
                                      [True, True, False, False])


class MapEdits(unittest.TestCase):
    """map_edits' bytes, on the readers' records as a made-up map would give them: the depths over the counted array,
    each matrix row saved W first, the box's six floats; the IsValid byte and the sizes left alone."""

    def test_the_edits_write_what_the_readers_read_back(self):
        old = dict(offset=1000, sizeX=3, sizeY=2, depths=(1, 2, 3, 4, 5, 6), bounds=[0.0] * 6)
        places = dict(WorldToLight=2000, LightToWorld=2100, LightSpaceImportanceBounds=2200, ShadowMapSizeX=2300,
                      ShadowMapSizeY=2310)
        w2l, l2w = sun_bake.light_frame([0.3, -0.9, -0.3])
        made = dict(sizeX=3, sizeY=2, depths=np.array([10, 20, 30, 40, 50, 65535], np.uint16), worldToLight=w2l,
                    lightToWorld=l2w, bounds=[-1.5, -2.5, -3.5, 4.5, 5.5, 6.5])
        p = mock.Mock()
        p.name.return_value = MOON
        with mock.patch.object(sun_bake.lighting, 'dominant_shadow_map', return_value=old), \
                mock.patch.object(sun_bake.lighting, 'shadow_info_places', return_value=places):
            edits = sun_bake.map_edits(p, 7, made)
            data = bytearray(3000)
            for at, value, _ in edits:
                data[at:at + len(value)] = value
            self.assertEqual(sorted(at for at, _, _ in edits), [1000, 2000, 2100, 2200])
            self.assertEqual(struct.unpack_from('<6H', data, 1000), (10, 20, 30, 40, 50, 65535))
            np.testing.assert_allclose(lighting.matrix_rows(data[2000:2064]), w2l, atol=1e-7)
            np.testing.assert_allclose(lighting.matrix_rows(data[2100:2164]), l2w, atol=1e-7)
            self.assertEqual(struct.unpack_from('<6f', data, 2200), (-1.5, -2.5, -3.5, 4.5, 5.5, 6.5))
            self.assertEqual(data[2224], 0)         # the box's IsValid byte is not written
            with self.assertRaises(ValueError):
                sun_bake.map_edits(p, 7, dict(made, depths=made['depths'][:4]))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarAsItIs(unittest.TestCase):
    """URB_Bar's moon as the map has it: sun_bake's rules give what Lightmass stored (F-195)."""

    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        cls.ci = cls.p.by_name[MOON]
        cls.stored = lighting.dominant_shadow_map(cls.p, cls.ci)
        cls.world = relight.Scene(cls.p, samples=1, bounce_rays=0, emissive=False)

    def test_the_frame_and_the_box_are_the_maps(self):
        w2l, l2w = sun_bake.light_frame(np.asarray(self.stored['lightToWorld'])[2, :3])
        np.testing.assert_allclose(l2w, self.stored['lightToWorld'], atol=1e-6)
        np.testing.assert_allclose(w2l, self.stored['worldToLight'], atol=1e-6)
        lo, hi = sun_bake.importance_box(self.p)
        np.testing.assert_allclose(sun_bake.light_box(lo, hi, np.asarray(self.stored['worldToLight'])),
                                   self.stored['bounds'], atol=0.01)
        self.assertEqual(sun_bake.wanted_size(self.stored['bounds'], self.world.level_scale), [132, 97])
        # the moon's direction is its actor's Rotation (to a fiftieth of a degree)
        made = sun_bake.level_map(self.p, self.ci, self.world.occluder, self.world.level_scale)
        np.testing.assert_allclose(made['lightToWorld'], self.stored['lightToWorld'], atol=5e-4)

    def test_the_depths_are_the_maps(self):
        s = self.stored
        depths, missed = sun_bake.level_depths(self.world.occluder, np.asarray(s['lightToWorld']), s['bounds'],
                                               [s['sizeX'], s['sizeY']])
        d = (np.asarray(s['depths'], float) - depths) / 65535 * (s['bounds'][5] - s['bounds'][2])
        self.assertEqual(missed, 0)
        self.assertGreater(np.mean(np.abs(d) < 25), 0.98)       # 98.7%
        self.assertGreater(np.mean(np.abs(d) < 1), 0.92)        # 94.0%

    def test_the_marks_are_the_maps(self):
        volume, marks = sun_bake.sample_marks(self.p, self.world.occluder, self.world.level_scale)
        stored = [s[-1] for s in volume['samples']]
        self.assertEqual(len(marks), 1743)
        self.assertGreater(np.mean(np.array(marks) == np.array(stored)), 0.995)     # 6 of 1,743 differ

    def test_the_whole_maps_jobs_take_every_shadow_map_of_the_moon_and_the_debris(self):
        jobs = sun_bake.whole_map_jobs(self.p)
        moon = self.p.own(self.ci, 'LightGuid').hex()
        self.assertEqual(len(jobs), 708)
        self.assertEqual({j['sm']['guid'] for j in jobs}, {moon})
        self.assertTrue(all(j['fresh'] and j['source'] is None for j in jobs))
        self.assertEqual(sum(1 for j in jobs if self.p.cls(j['ci']) == shadowmaps.DEBRIS), 81)
        # an edit's relight leaves the debris pieces as it did
        self.assertEqual(len(shadowmaps.dominant_receivers(self.p, sun_bake.enabled_lights(self.p))), 627)
        self.assertEqual(sun_bake.direction_key(self.p), [[moon, [0.109838, -0.117762, 0.986949]]])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class TurnedBar(unittest.TestCase):
    """A scratch copy of URB_Bar with its moon turned to a low sun (native_copy.set_pose on its actor), relit with
    --sun-turned alone and read back."""

    @classmethod
    def setUpClass(cls):
        import native_copy
        import package_grow
        cls.folder = tempfile.TemporaryDirectory()
        root = Path(cls.folder.name)
        (root / 'turned').mkdir()
        src = Path(BAR)
        p = lighting.Package(src)
        g = package_grow.Grower(str(src))
        native_copy.set_pose(native_copy.Walker(p, g), g, p, p.exports[p.by_name[MOON] - 1]['outer'], None, TURNED)
        turned = root / 'turned' / 'URB_Bar.upk'
        g.write(str(turned))
        lighting.link_caches(turned.parent, src.parent)
        cls.out = root / 'lit'
        run = subprocess.run([sys.executable, '-B', str(HERE.parent / 'relight.py'), str(turned), str(cls.out), 'URB_Bar_Sun',
                              '--cache', 'Lighting_7004', '--sun-turned', '--receivers-near', '600'],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
        if run.returncode:
            raise AssertionError(f'relight --sun-turned failed: {run.stdout[-2000:]} {run.stderr[-2000:]}')
        lighting.link_caches(cls.out, src.parent)
        cls.record = json.loads((cls.out / 'URB_Bar_Sun.relight.json').read_text(encoding='utf-8'))
        cls.q = lighting.Package(cls.out / 'URB_Bar_Sun.upk')
        cls.old = lighting.Package(src)
        cls.world = relight.Scene(cls.q, samples=1, bounce_rays=0, emissive=False)
        cls.light = sun_bake.enabled_lights(cls.q)[cls.q.own(cls.q.by_name[MOON], 'LightGuid').hex()]

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_the_record_says_what_was_made(self):
        r = self.record
        self.assertFalse(r['lightingUnchanged'])
        self.assertEqual((len(r['components']), r['failed']), (0, 0))
        self.assertEqual(len([s for s in r['shadowMaps'] if 'skipped' not in s]), 708)
        (m,) = r['sun']['maps']
        self.assertEqual(m['size'], [132, 97])
        self.assertEqual(m['depthsChanged'], 12804)
        self.assertGreater(r['sun']['samples']['changed'], 100)
        self.assertEqual(r['sun']['notes'], [])

    def test_the_shadow_maps_are_the_new_suns(self):
        agree = far_agree = n = n_far = changed = 0
        tops = {}
        for job in sun_bake.whole_map_jobs(self.q)[::5]:
            ci, sm = job['ci'], job['sm']
            if sm['texture'] not in tops:
                tops[sm['texture']] = shadowmaps.texture_top(self.q, sm['texture'])
            top, t = tops[sm['texture']]
            geo = shadowmaps.sub_samples(self.q, ci, sm, [t['mips'][0]['width'], t['mips'][0]['height']], upsample=1)
            if not len(geo['world']):
                continue
            seen = shadowmaps.lit(self.world.occluder, self.light['toLight'], geo, self.world.level_scale)
            value = top[geo['py'], geo['px']] / 255.0
            far = (value < 0.25) | (value > 0.75)
            agree += np.sum((value > 0.5) == seen)
            far_agree += np.sum(((value > 0.5) == seen)[far])
            n, n_far = n + len(seen), n_far + far.sum()
            before = shadowmaps.texture_top(self.old, self.old.own(self.old.by_name[sm['path']], 'Texture'))[0]
            changed += int(np.sum(np.abs(before[geo['py'], geo['px']].astype(int) - top[geo['py'], geo['px']]) > 2))
        self.assertGreater(agree / n, 0.99)             # 99.6% on every piece
        self.assertGreater(far_agree / n_far, 0.999)    # away from the shadows' edges
        self.assertGreater(changed / n, 0.3)            # the old moon's shadows are gone (45%)

    def test_the_map_of_the_level_is_the_new_suns(self):
        ci = self.q.by_name[MOON]
        got = lighting.dominant_shadow_map(self.q, ci)
        w2l, l2w = sun_bake.light_frame(-np.asarray(self.light['toLight']))
        np.testing.assert_allclose(got['lightToWorld'], l2w, atol=1e-6)
        lo, hi = sun_bake.importance_box(self.q)
        np.testing.assert_allclose(got['bounds'], sun_bake.light_box(lo, hi, w2l), atol=0.01)
        self.assertEqual((got['sizeX'], got['sizeY']), (132, 97))
        # it puts the lighting samples in the sun's shadow where rays do about as often as the game's own maps of
        # 16-degree suns do theirs (74 to 92%, F-196)
        volume, marks = sun_bake.sample_marks(self.q, self.world.occluder, self.world.level_scale)
        points = np.array([s[:3] for s in volume['samples']], float)
        self.assertGreater(np.mean(sun_bake.shadowed_by_map(self.q, ci, points) == np.array(marks, bool)), 0.85)

    def test_the_samples_marks_are_the_new_suns(self):
        volume, marks = sun_bake.sample_marks(self.q, self.world.occluder, self.world.level_scale)
        self.assertEqual([s[-1] for s in volume['samples']], marks)
        old = lighting.light_volume(self.old, self.old.by_name[PL[:-1]])
        self.assertEqual([s[:-1] for s in volume['samples']], [s[:-1] for s in old['samples']])
        self.assertNotEqual(marks, [s[-1] for s in old['samples']])


if __name__ == '__main__':
    unittest.main()
