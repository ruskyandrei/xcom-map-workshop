"""A copy's lighting textures sized to what it reads (lightmap_textures.py: crop_box, moved_record, sized, cropped and
blank textures) and a map's lightmaps weighed (lighting_size.py): smaller built maps plan, stages S0 and S1, F-151."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lightmap_textures as lt  # noqa: E402
import lighting_records as lighting  # noqa: E402
import lighting_size  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_writer  # noqa: E402
import package_grow  # noqa: E402
import dxt1  # noqa: E402
from lightmap_texels import moved_rect, rect_bounds  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
# non-square atlases (1,024 by 256, 512 by 256, 64 by 32...): the tutorial's map
INTRO, NO_INTRO = labpaths.install_map('Act1_IntroLevel')


def records(p):
    """Every texture lightmap record (each LOD) and every ShadowMap2D of the map: [(texture, scale, bias, size)]."""
    out = []
    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if cls in lightmap_fields.COMPONENT_CLASSES:
            try:
                lods = lightmap_fields.component_fields(p, i)['lods']
            except Exception:
                continue
            for lod in lods:
                lm = lod['lightmap']
                if lm['type'] == 2 and lm['slots'][0]['index'] > 0:
                    t = lm['slots'][0]['index']
                    out.append((t, lm['coordinateScale'], lm['coordinateBias'],
                                (int(p.own(t, 'SizeX')), int(p.own(t, 'SizeY')))))
        elif cls == 'ShadowMap2D' and p.own(i, 'Texture', 0) > 0 and p.own(i, 'CoordinateScale'):
            t = p.own(i, 'Texture')
            out.append((t, struct.unpack('<2f', p.own(i, 'CoordinateScale')),
                        struct.unpack('<2f', p.own(i, 'CoordinateBias')), (int(p.own(t, 'SizeX')), int(p.own(t, 'SizeY')))))
    return out


class Rules(unittest.TestCase):
    """The mip chains, the box and the record arithmetic, without the game."""

    def test_mip_chains_are_the_games(self):
        # (read off the game's own: URB_TruckStop_EWI's 32 by 4 lightmap, TempleShip's 4 by 4, an 8 by 8 shadow map)
        self.assertEqual([m[:2] for m in lt.mip_sizes('PF_DXT1', 32, 4)],
                         [(32, 4), (16, 4), (8, 4), (4, 4), (4, 4), (4, 4)])
        self.assertEqual([m[:2] for m in lt.mip_sizes('PF_DXT1', 4, 4)], [(4, 4)] * 3)
        self.assertEqual([m[:2] for m in lt.mip_sizes('PF_DXT1', 64, 16)],
                         [(64, 16), (32, 8), (16, 4), (8, 4), (4, 4), (4, 4), (4, 4)])
        self.assertEqual([m[:2] for m in lt.mip_sizes('PF_G8', 8, 8)], [(8, 8), (4, 4), (2, 2), (1, 1)])
        self.assertEqual(len(lt.mip_sizes('PF_G8', 1024, 1024)), 11)
        self.assertEqual(lt.mip_bytes('PF_DXT1', 4, 4), 8)
        self.assertEqual(lt.mip_bytes('PF_DXT1', 8, 4), 16)
        self.assertEqual(lt.mip_bytes('PF_G8', 2, 2), 4)

    def test_the_box_holds_the_rectangles_and_their_ring_on_whole_blocks(self):
        # a 10 by 6 rectangle at (101, 203): with its ring 100..112 x 202..210, its start down to a block, 16 by 8
        self.assertEqual(lt.crop_box([(101, 203, 111, 209)], 1024, 1024, 'PF_DXT1'), (100, 200, 16, 16))
        # (the ring starts at 202, the block at 200: 200..210 is 10 high, 16 rounded up)
        # a G8 box starts anywhere; at least 8 a side
        self.assertEqual(lt.crop_box([(101, 203, 103, 205)], 1024, 1024, 'PF_G8'), (100, 202, 8, 8))
        # two rectangles: one box over both
        self.assertEqual(lt.crop_box([(9, 9, 15, 15), (40, 9, 47, 15)], 1024, 1024, 'PF_DXT1'), (8, 8, 64, 8))
        # at the far edge the box moves back inside
        self.assertEqual(lt.crop_box([(1019, 0, 1024, 3)], 1024, 1024, 'PF_DXT1'), (1016, 0, 8, 4))
        self.assertEqual(lt.crop_box([(500, 0, 1000, 3)], 1024, 1024, 'PF_DXT1'), (496, 0, 512, 4))
        self.assertEqual(lt.crop_box([(600, 0, 1000, 3)], 1024, 1024, 'PF_DXT1'), (512, 0, 512, 4))
        # the whole texture, nothing, or sides that are no powers of two: cloned as it is
        self.assertIsNone(lt.crop_box([(0, 0, 1000, 1000)], 1024, 1024, 'PF_DXT1'))
        self.assertIsNone(lt.crop_box([], 1024, 1024, 'PF_DXT1'))
        self.assertIsNone(lt.crop_box([(0, 0, 4, 4)], 1000, 1024, 'PF_DXT1'))
        # a record of no width (a coordinate scale of 0) still takes a texel
        self.assertEqual(lt.crop_box([(40, 40, 40, 40)], 1024, 1024, 'PF_DXT1'), (36, 36, 8, 8))

    def test_a_moved_record_reads_the_same_texels_exactly(self):
        rng = np.random.default_rng(5)
        for _ in range(2000):
            W, H = int(2 ** rng.integers(4, 11)), int(2 ** rng.integers(4, 11))
            sx, sy = rng.integers(1, W // 2) / W * rng.uniform(0.9, 1.0), rng.integers(1, H // 2) / H * rng.uniform(0.9, 1.0)
            bx, by = rng.uniform(0, 1 - sx), rng.uniform(0, 1 - sy)
            scale, bias = np.float32([sx, sy]).tolist(), np.float32([bx, by]).tolist()
            rect = rect_bounds(dict(coordinateScale=scale, coordinateBias=bias), W, H)
            box = lt.crop_box([rect], W, H, 'PF_DXT1')
            if box is None:
                continue
            s2, b2 = lt.moved_record(scale, bias, (W, H), box)
            moved = rect_bounds(dict(coordinateScale=s2, coordinateBias=b2), box[2], box[3])
            self.assertEqual(moved, (rect[0] - box[0], rect[1] - box[1], rect[2] - box[0], rect[3] - box[1]))
            self.assertTrue(moved_rect(dict(coordinateScale=scale, coordinateBias=bias), (W, H),
                                       dict(coordinateScale=s2, coordinateBias=b2), box[2:]))
            # (the values packed as the record holds them, 32-bit floats, read back the same)
            self.assertEqual(list(struct.unpack('<4f', struct.pack('<4f', *s2, *b2))), [*s2, *b2])

    def test_another_layout_is_not_a_moved_one(self):
        a = dict(coordinateScale=(0.25, 0.25), coordinateBias=(0.5, 0.5))
        self.assertTrue(moved_rect(a, (64, 64), dict(coordinateScale=(1.0, 1.0), coordinateBias=(0.0, 0.0)), (16, 16)))
        self.assertFalse(moved_rect(a, (64, 64), dict(coordinateScale=(0.5, 1.0), coordinateBias=(0.0, 0.0)), (16, 16)))
        self.assertFalse(moved_rect(a, (64, 64), dict(coordinateScale=(1.0, 1.0), coordinateBias=(0.03, 0.0)), (16, 16)))

    def test_lower_mips_are_box_averages_of_the_top(self):
        g8 = np.arange(64, dtype=np.uint8).reshape(8, 8) * 3
        mips = lt.made_mips('PF_G8', g8.tobytes(), 8, 8)
        self.assertEqual([len(m) for m in mips], [64, 16, 4, 1])
        self.assertEqual(mips[3], bytes([int(np.round(g8.mean()))]))
        np.testing.assert_array_equal(np.frombuffer(mips[1], np.uint8).reshape(4, 4),
                                      np.round(g8.reshape(4, 2, 4, 2).mean((1, 3))).astype(np.uint8))
        # (a lightmap's light is smooth: a gradient)
        yy, xx = np.mgrid[0:8, 0:16]
        rgb = ((xx + 2 * yy) / 29)[..., None] * np.array([1.0, 0.8, 0.5])     # (along one colour, as DXT1 holds a block)
        top = dxt1.encode_blocks(dxt1.image_blocks(rgb).reshape(-1, 16, 3))
        mips = lt.made_mips('PF_DXT1', top, 16, 8)
        self.assertEqual(mips[0], top)
        self.assertEqual([len(m) for m in mips], [lt.mip_bytes('PF_DXT1', *s[:2]) for s in lt.mip_sizes('PF_DXT1', 16, 8)])
        # each the top mip's decoded texels averaged and encoded again, as the writer rebuilds a mip; a mip stored
        # larger than it is (4 by 2 in a 4 by 4 block, 2 by 1, 1 by 1) repeats its texels
        decoded = dxt1.decode_image(top, 16, 8)
        for k, (sw, sh, w, h) in enumerate(lt.mip_sizes('PF_DXT1', 16, 8)[1:], 1):
            small = decoded.reshape(h, 8 // h, w, 16 // w, 3).mean((1, 3))
            small = np.repeat(np.repeat(small, sh // h, 0), sw // w, 1)
            self.assertEqual(mips[k], dxt1.encode_blocks(dxt1.image_blocks(small).reshape(-1, 16, 3)), k)
        self.assertLess(float(np.abs(dxt1.decode_image(mips[1], 8, 4) - decoded.reshape(4, 2, 8, 2, 3).mean((1, 3))).max()),
                        0.1)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class OnTheBar(unittest.TestCase):
    """Textures of a chosen size made in a grown URB_Bar, read back."""

    @classmethod
    def setUpClass(cls):
        cls.p = p = lighting.Package(BAR)
        cls.dir = tempfile.TemporaryDirectory()
        cls.recs = records(p)
        # a lamp post's lightmap and its moon shadow map, cropped; a blank one of each class
        comp = p.own(p.by_name['TheWorld.PersistentLevel.XComLevelActor_37'], 'StaticMeshComponent')
        cls.lm = lightmap_fields.component_fields(p, comp)['lods'][0]['lightmap']
        cls.comp = p.name(comp)
        cls.lm_tex = cls.lm['slots'][1]['index']
        W, H = int(p.own(cls.lm_tex, 'SizeX')), int(p.own(cls.lm_tex, 'SizeY'))
        cls.lm_rect = rect_bounds(cls.lm, W, H)
        cls.lm_box = lt.crop_box([cls.lm_rect], W, H, 'PF_DXT1')
        sm = next(i for i in p.children.get(comp, []) if p.cls(i) == 'ShadowMap2D')
        cls.sm_tex = p.own(sm, 'Texture')
        rec = dict(coordinateScale=struct.unpack('<2f', p.own(sm, 'CoordinateScale')),
                   coordinateBias=struct.unpack('<2f', p.own(sm, 'CoordinateBias')))
        cls.sm_rect = rect_bounds(rec, int(p.own(cls.sm_tex, 'SizeX')), int(p.own(cls.sm_tex, 'SizeY')))
        cls.sm_box = lt.crop_box([cls.sm_rect], int(p.own(cls.sm_tex, 'SizeX')), int(p.own(cls.sm_tex, 'SizeY')), 'PF_G8')
        g = package_grow.Grower(str(BAR))
        cls.made = dict(lm=lt.cropped_texture(g, p, cls.lm_tex, cls.lm_box),
                        sm=lt.cropped_texture(g, p, cls.sm_tex, cls.sm_box),
                        blank_lm=lt.blank_texture(g, p, cls.lm_tex, 32, 8),
                        blank_sm=lt.blank_texture(g, p, cls.sm_tex, 16, 64))
        cls.out = Path(cls.dir.name) / 'URB_Bar.upk'
        g.write(str(cls.out))
        lighting.link_caches(cls.dir.name, BAR.parent)
        cls.q = lighting.Package(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_every_record_of_the_bar_moves_into_its_box_exactly(self):
        moved = 0
        for t, scale, bias, size in self.recs:
            rect = rect_bounds(dict(coordinateScale=scale, coordinateBias=bias), *size)
            box = lt.crop_box([rect], *size, self.p.effective(t, 'Format'))
            if box is None:
                continue
            s2, b2 = lt.moved_record(scale, bias, size, box)
            self.assertEqual(rect_bounds(dict(coordinateScale=s2, coordinateBias=b2), *box[2:]),
                             (rect[0] - box[0], rect[1] - box[1], rect[2] - box[0], rect[3] - box[1]))
            moved += 1
        self.assertGreater(moved, 500)

    def test_the_textures_read_back_as_the_games_small_ones(self):
        q = self.q
        for key, (w, h) in dict(lm=self.lm_box[2:], sm=self.sm_box[2:], blank_lm=(32, 8), blank_sm=(16, 64)).items():
            k = self.made[key]
            t = lightmap_fields.texture_fields(q, k)          # (the audit reader's checks too)
            fmt = t['format']
            self.assertEqual([(m['width'], m['height']) for m in t['mips']], [s[:2] for s in lt.mip_sizes(fmt, w, h)])
            self.assertTrue(all(m['inline'] and not m['flags'] and m['bytes'] == m['count'] for m in t['mips']))
            self.assertIsNone(t['cache'])
            self.assertEqual((q.effective(k, 'SizeX'), q.effective(k, 'SizeY')), (w, h))
            self.assertEqual(q.effective(k, 'MipTailBaseIdx'), len(t['mips']) - 1)
            self.assertIs(q.effective(k, 'NeverStream'), True)
            self.assertIsNone(q.own(k, 'FirstResourceMemMip'))
            self.assertEqual(q.cls(k), self.p.cls(self.lm_tex if 'lm' in key else self.sm_tex))
            self.assertNotEqual(q.name(k), q.name(self.lm_tex if 'lm' in key else self.sm_tex))
            if 'sm' in key:
                self.assertEqual(q.own(k, 'ShadowmapFlags'), self.p.own(self.sm_tex, 'ShadowmapFlags'))
            lighting.texture_record(q, k)

    def test_a_cropped_texture_holds_the_sources_texels_over_its_box(self):
        x0, y0, w, h = self.lm_box
        np.testing.assert_array_equal(lt.top_mip_rgb(self.q, self.made['lm']),
                                      lt.top_mip_rect(self.p, self.lm_tex, x0, y0, x0 + w, y0 + h))
        raw, W, H = lt.top_mip_bytes(self.p, self.sm_tex)
        x0, y0, w, h = self.sm_box
        got, _, _ = lt.top_mip_bytes(self.q, self.made['sm'])
        self.assertEqual(got, np.frombuffer(raw, np.uint8).reshape(H, W)[y0:y0 + h, x0:x0 + w].tobytes())
        self.assertEqual(lt.top_mip_bytes(self.q, self.made['blank_sm'])[0], bytes(16 * 64))
        self.assertFalse(lt.top_mip_rgb(self.q, self.made['blank_lm']).any())

    def test_the_writer_edits_a_sized_texture_where_it_lies(self):
        """The relight's writer edits a sized texture in place: it never enters the build's cache, and no cache is
        written for it."""
        fx = lightmap_writer.Fixture(self.out, 'Lighting_7004')
        k = self.made['blank_sm']
        self.assertIs(fx.redirect(k), fx.in_package[k])
        values, mask = np.full((4, 3), 0.5), np.ones((4, 3), bool)
        fx.gray(k, 2, 6, values, mask)
        with tempfile.TemporaryDirectory() as d:
            m = fx.finish(d, 'URB_BarSized')
            self.assertIsNone(m['cache'])
            self.assertEqual(sorted(x.name for x in Path(d).iterdir()), ['URB_BarSized.fixture.json', 'URB_BarSized.upk'])
            q = lighting.Package(Path(d) / 'URB_BarSized.upk')
            top = np.frombuffer(lt.top_mip_bytes(q, k)[0], np.uint8).reshape(64, 16)
            self.assertEqual(int(top[6:10, 2:5].min()), 128)
            self.assertEqual(int(top.sum()), 128 * 12)
            self.assertIsNone(lightmap_fields.texture_fields(q, k)['cache'])

    def test_the_size_of_the_bar(self):
        got = lighting_size.survey(BAR)
        s = got['summary']
        self.assertEqual(s['textures'], sum(self.p.cls(k) in lightmap_fields.TEXTURE_CLASSES
                                            for k in range(1, len(self.p.exports) + 1)))
        self.assertEqual(s['unread'], 0)
        quick = lighting_size.inside(BAR)
        self.assertEqual((quick['bytes'], quick['textures'], quick['whole']), (s['inside'], s['insideTextures'], s['whole']))
        self.assertIn('lightmaps inside the map', lighting_size.describe(s))
        grown = lighting_size.inside(self.out)
        self.assertEqual(grown['textures'], quick['textures'] + 4)
        # a map alone in its folder, no texture cache beside it (a package's folder): the count reads the map alone
        import shutil
        with tempfile.TemporaryDirectory() as d:
            alone = Path(d) / 'URB_Bar.upk'
            shutil.copyfile(self.out, alone)
            self.assertEqual(lighting_size.inside(alone), grown)
            self.assertEqual(lighting_size.survey(alone)['summary']['inside'], grown['bytes'])


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class OddSizes(unittest.TestCase):
    """Every rectangle of a map with non-square atlases moves into its box exactly."""

    def test_every_record_moves_exactly(self):
        p = lighting.Package(INTRO)
        sizes, moved = set(), 0
        for t, scale, bias, size in records(p):
            sizes.add(size)
            rect = rect_bounds(dict(coordinateScale=scale, coordinateBias=bias), *size)
            box = lt.crop_box([rect], *size, p.effective(t, 'Format'))
            if box is None:
                continue
            s2, b2 = lt.moved_record(scale, bias, size, box)
            self.assertEqual(rect_bounds(dict(coordinateScale=s2, coordinateBias=b2), *box[2:]),
                             (rect[0] - box[0], rect[1] - box[1], rect[2] - box[0], rect[3] - box[1]))
            moved += 1
        self.assertTrue(any(w != h for w, h in sizes))
        self.assertGreater(moved, 100)


if __name__ == '__main__':
    unittest.main()
