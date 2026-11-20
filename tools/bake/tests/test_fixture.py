"""Lighting field locator and fixture builder (baker design, stage 1)."""
import io
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

from PIL import Image
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lighting_fixture as fx  # noqa: E402
import lightmap_fields  # noqa: E402
from lighting_fixture import block_range, compressed_bulk, paint_dxt1, solid_block  # noqa: E402
import lighting_records as lighting  # noqa: E402
from texture import dds_header, decompress_payload  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
EAST_FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'
WEST_FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_91.StaticMeshComponent_6'


def decode(raw, w, h):
    return np.asarray(Image.open(io.BytesIO(dds_header(w, h, 'DXT1', len(raw)) + raw)).convert('RGB'))


class Blocks(unittest.TestCase):
    def test_solid_block_decodes_to_its_colour(self):
        for rgb, want in [((1, 0, 0), (255, 0, 0)), ((0, 1, 0), (0, 255, 0)), ((1, 1, 1), (255, 255, 255))]:
            img = decode(solid_block(rgb), 4, 4)
            self.assertTrue((img == want).all(), rgb)

    def test_solid_block_refuses_out_of_range(self):
        with self.assertRaises(ValueError):
            solid_block((1.5, 0, 0))

    def test_block_range_keeps_whole_blocks_inside(self):
        self.assertEqual(block_range(0.0, 0.25, 64), (0, 4))
        self.assertEqual(block_range(0.01, 0.25, 64), (1, 4))   # 0.64..16.64 texels
        self.assertEqual(block_range(0.5, 0.01, 64), (8, 8))    # under a block: none
        self.assertEqual(block_range(0.9, 0.5, 64), (15, 16))   # clipped at the edge

    def test_paint_changes_only_blocks_inside(self):
        rng = random.Random(3)
        w = h = 32
        raw = bytes(rng.randrange(256) for _ in range(8 * 8 * 8))
        new, n = paint_dxt1(raw, w, h, (0.25, 0.5), (0.5, 0.25), solid_block((0, 0, 1)))
        self.assertEqual(n, 4 * 2)
        a, b = decode(raw, w, h), decode(new, w, h)
        changed = (a != b).any(2)
        self.assertFalse(changed[:, :8].any() or changed[:, 24:].any() or changed[:16].any() or changed[24:].any())
        self.assertTrue((b[16:24, 8:24] == (0, 0, 255)).all())

    def test_bands_split_the_block_columns(self):
        w = h = 64
        raw = bytes(8 * 16 * 16)
        colours = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
        new, n = paint_dxt1(raw, w, h, (0.0, 0.0), (1.0, 0.5), [solid_block(c) for c in colours])
        self.assertEqual(n, 16 * 8)
        img = decode(new, w, h)
        for k, want in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]):
            self.assertTrue((img[:32, 16 * k:16 * (k + 1)] == want).all(), k)
        self.assertTrue((img[32:] == 0).all())

    def test_bands_on_a_mip_too_small_for_all(self):
        raw = bytes(8)
        new, n = paint_dxt1(raw, 4, 4, (0.0, 0.0), (1.0, 1.0), [solid_block((1, 0, 0)), solid_block((0, 1, 0))])
        self.assertEqual(n, 1)

    def test_cache_names_plain_and_numbered(self):
        """Output names plan 4: the Build's <Map>_Lighting is its own name (number 0); a name ending _<n>, as the
        Build's Lighting_<n> until 16 November 2026, is <Name> numbered n + 1 and wins over a plain reading."""
        for cache, fname in [('URB_BarFix_Lighting', ('URB_BarFix_Lighting', 0)), ('Map2ndTry_2_Lighting', ('Map2ndTry_2_Lighting', 0)),
                             ('Lighting_7000', ('Lighting', 7001)), ('Lighting_0', ('Lighting', 1)),
                             ('Lighting_07', ('Lighting_07', 0)),          # a leading zero: the engine keeps it whole
                             ('Lighting_2147483646', ('Lighting', 2147483647)), ('Lighting', ('Lighting', 0))]:
            with self.subTest(cache):
                self.assertEqual(fx.cache_fname(cache), fname)
                self.assertEqual(fx.cache_table_name(cache), fname[0])
        for bad in ('Lighting_2147483647', 'Bad-name', '1x', '', 'A' * 64, None):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    fx.cache_fname(bad)

    def test_compressed_bulk_round_trip(self):
        raw = bytes(random.Random(5).randrange(256) for _ in range(300_001))
        payload = compressed_bulk(raw, 131072)
        self.assertEqual(decompress_payload(payload, 16), raw)
        self.assertEqual(fx.bulk_block_size(payload), 131072)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class RealMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)

    def test_component_offsets_hold_their_values(self):
        f = lightmap_fields.component_fields(self.p, self.p.by_name[EAST_FLOOR])
        lm = f['lods'][0]['lightmap']
        for s in lm['slots']:
            self.assertEqual(struct.unpack_from('<i', self.p.data, s['textureOffset'])[0], s['index'])
            self.assertEqual(list(struct.unpack_from('<3f', self.p.data, s['scaleOffset'])), s['scale'])
        self.assertEqual(list(struct.unpack_from('<2f', self.p.data, lm['coordinateBiasOffset'])),
                         lm['coordinateBias'])

    def test_texture_offsets_hold_their_values(self):
        t = lightmap_fields.texture_fields(self.p, self.p.by_name['NormalizedAverageColor0_5'])
        self.assertEqual(self.p.names[struct.unpack_from('<i', self.p.data, t['cacheNameOffset'])[0]], 'Lighting')
        for m in t['mips']:
            self.assertEqual(struct.unpack_from('<4i', self.p.data, m['metaOffset']),
                             (m['flags'], m['count'], m['bytes'], m['offset']))
        self.assertEqual(sum(not m['inline'] for m in t['mips']), 4)

    def test_cache_name_must_be_new_and_known(self):
        with self.assertRaises(ValueError):
            fx.parse_cache_name(self.p, 'NotInTheNameTable_3')
        with self.assertRaises(ValueError):
            fx.parse_cache_name(self.p, 'Lighting')
        self.assertEqual(fx.parse_cache_name(self.p, 'Lighting_7000'), (self.p.names.index('Lighting'), 7001))
        # a plain name needs its text in the table, which only a growing write can add
        with self.assertRaisesRegex(ValueError, 'growing write adds it first'):
            fx.parse_cache_name(self.p, 'URB_BarNamed_Lighting')

    def test_a_named_cache_is_added_by_a_growing_write_and_written_as_a_plain_name(self):
        """Output names plan 4 and 5: the map grown with the cache's name alone in its table (the Build's named copy),
        read by a fresh reader; a redirect then writes that name, number 0, into the texture, and its mips go to
        <name>.tfc. Nothing else of the map changes: its logical bytes differ from the grown map's only at the
        texture's cache name and mip records."""
        import package_grow
        name = 'URB_BarNamed_Lighting'
        with tempfile.TemporaryDirectory() as d:
            grown = Path(d) / 'named' / 'URB_Bar.upk'
            grown.parent.mkdir()
            g = package_grow.Grower(str(BAR))
            g.name(name)
            g.write(str(grown))
            lighting.link_caches(grown.parent, BAR.parent)
            src = lighting.Package(grown)
            self.assertEqual(src.names[-1], name)
            self.assertEqual(fx.parse_cache_name(src, name), (len(src.names) - 1, 0))
            manifest = fx.run(grown, Path(d) / 'out', 'URB_BarNamed', [dict(op='redirect', texture='NormalizedAverageColor0_5')], cache=name)
            self.assertEqual(manifest['cache'], name)
            self.assertTrue((Path(d) / 'out' / f'{name}.tfc').is_file())
            q = lighting.Package(Path(d) / 'out' / 'URB_BarNamed.upk')
            self.assertEqual(q.effective(q.by_name['NormalizedAverageColor0_5'], 'TextureFileCacheName'), name)
            self.assertEqual(q.effective(q.by_name['DirectionalMaxComponent0_5'], 'TextureFileCacheName'), 'Lighting')
            t = lightmap_fields.texture_fields(q, q.by_name['NormalizedAverageColor0_5'])
            self.assertEqual(struct.unpack_from('<ii', q.data, t['cacheNameOffset']), (len(src.names) - 1, 0))
            # every byte as the grown map has it but the edits, and every edit a cache name or a mip record (from the
            # first chunk: the image's first bytes are the summary's, whose chunk table follows the re-encoded blocks)
            self.assertEqual(len(q.data), len(src.data))
            lo = src.header['chunks'][0][0]
            edited = np.zeros(len(src.data), bool)
            for e in manifest['edits']:
                self.assertRegex(e['what'], r'^(cache name of |mip \d+x\d+ of )')
                edited[e['offset']:e['offset'] + len(bytes.fromhex(e['new']))] = True
            diff = lo + np.nonzero(np.frombuffer(bytes(src.data), np.uint8)[lo:] != np.frombuffer(bytes(q.data), np.uint8)[lo:])[0]
            self.assertTrue(len(diff) and edited[diff].all())

    def test_paint_and_scale_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = fx.run(BAR, d, 'URB_BarTest', [
                dict(op='paint', component=EAST_FLOOR, slot=0, rgb=[1, 0, 0]),
                dict(op='scale', component=WEST_FLOOR, slot=1, factor=[4, 4, 4])], cache='Lighting_7000')
            q = lighting.Package(Path(d) / 'URB_BarTest.upk')
            west_old = lightmap_fields.component_fields(self.p, self.p.by_name[WEST_FLOOR])['lods'][0]['lightmap']
            west_new = lightmap_fields.component_fields(q, q.by_name[WEST_FLOOR])['lods'][0]['lightmap']
            self.assertEqual([round(v, 4) for v in west_new['slots'][1]['scale']],
                             [round(v * 4, 4) for v in west_old['slots'][1]['scale']])
            self.assertEqual(west_new['slots'][0], west_old['slots'][0])
            east = lightmap_fields.component_fields(q, q.by_name[EAST_FLOOR])
            self.assertEqual(east, lightmap_fields.component_fields(self.p, self.p.by_name[EAST_FLOOR]))
            t = lightmap_fields.texture_fields(q, q.by_name['NormalizedAverageColor0_5'])
            self.assertEqual(t['cache'], 'Lighting_7000')
            top = t['mips'][0]
            with open(Path(d) / 'Lighting_7000.tfc', 'rb') as f:
                f.seek(top['offset'])
                raw = decompress_payload(f.read(top['bytes']), top['flags'])
            img = decode(raw, 1024, 1024)
            lm = east['lods'][0]['lightmap']
            x0, x1 = block_range(lm['coordinateBias'][0], lm['coordinateScale'][0], 1024)
            y0, y1 = block_range(lm['coordinateBias'][1], lm['coordinateScale'][1], 1024)
            self.assertTrue((img[y0 * 4:y1 * 4, x0 * 4:x1 * 4] == (255, 0, 0)).all())
            # The other textures still read from the shared cache.
            self.assertEqual(q.effective(q.by_name['DirectionalMaxComponent0_5'], 'TextureFileCacheName'), 'Lighting')
            self.assertEqual(len(manifest['outputs']), 2)

    def test_bands_and_setscale_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fx.run(BAR, d, 'URB_BarTest', [
                dict(op='paint', component=EAST_FLOOR, slot=0, rgb=[1, 1, 1]),
                dict(op='paint', component=EAST_FLOOR, slot=1, rgb=[[1, 1, 1], [0.5, 0.5, 0.5], [0, 0, 0]]),
                dict(op='setscale', component=EAST_FLOOR, slot=1, value=[1, 1, 1])], cache='Lighting_7001')
            q = lighting.Package(Path(d) / 'URB_BarTest.upk')
            lm = lightmap_fields.component_fields(q, q.by_name[EAST_FLOOR])['lods'][0]['lightmap']
            self.assertEqual(lm['slots'][1]['scale'], [1.0, 1.0, 1.0])
            for name in ('NormalizedAverageColor0_5', 'DirectionalMaxComponent0_5'):
                self.assertEqual(q.effective(q.by_name[name], 'TextureFileCacheName'), 'Lighting_7001')
            t = lightmap_fields.texture_fields(q, q.by_name['DirectionalMaxComponent0_5'])
            top = t['mips'][0]
            with open(Path(d) / 'Lighting_7001.tfc', 'rb') as f:
                f.seek(top['offset'])
                img = decode(decompress_payload(f.read(top['bytes']), top['flags']), 1024, 1024)
            x0, x1 = block_range(lm['coordinateBias'][0], lm['coordinateScale'][0], 1024)
            y0, _ = block_range(lm['coordinateBias'][1], lm['coordinateScale'][1], 1024)
            row = img[y0 * 4 + 2]
            third = (x1 - x0) // 3
            self.assertEqual(tuple(row[x0 * 4 + 2]), (255, 255, 255))
            self.assertEqual(tuple(row[(x0 + third) * 4 + 6]), tuple(decode(solid_block((.5, .5, .5)), 4, 4)[0, 0]))
            self.assertEqual(tuple(row[x1 * 4 - 3]), (0, 0, 0))

    def test_image_writes_texels_and_rebuilds_mips(self):
        f = lightmap_fields.component_fields(self.p, self.p.by_name[EAST_FLOOR])['lods'][0]['lightmap']
        x0, y0, x1, y1 = fx.rect_bounds(f, 1024, 1024)
        h, w = y1 - y0, x1 - x0
        yy, xx = np.mgrid[0:h, 0:w]
        texels = np.stack([xx / w, yy / h, np.full((h, w), 0.5)], -1)
        mask = np.ones((h, w), bool)
        mask[:10, :10] = False                       # these keep the original texels
        with tempfile.TemporaryDirectory() as d:
            npz = Path(d) / 'img.npz'
            np.savez(npz, t=texels, t_mask=mask)
            manifest = fx.run(BAR, Path(d) / 'out', 'URB_BarTest', [
                dict(op='image', component=EAST_FLOOR, slot=1, npz=str(npz), key='t')], cache='Lighting_7002')
            q = lighting.Package(Path(d) / 'out' / 'URB_BarTest.upk')
            t = lightmap_fields.texture_fields(q, q.by_name['DirectionalMaxComponent0_5'])
            old = lightmap_fields.texture_fields(self.p, self.p.by_name['DirectionalMaxComponent0_5'])

            def mip(fields, k, tfc):
                m = fields['mips'][k]
                if m['inline']:
                    raw = (q if fields is t else self.p).data[m['payloadOffset']:m['payloadOffset'] + m['bytes']]
                else:
                    with open(tfc, 'rb') as fh:
                        fh.seek(m['offset'])
                        raw = decompress_payload(fh.read(m['bytes']), m['flags'])
                return decode(bytes(raw), m['width'], m['height']) / 255.0

            new_top = mip(t, 0, Path(d) / 'out' / 'Lighting_7002.tfc')
            old_top = mip(old, 0, BAR.parent / 'Lighting.tfc')
            region = new_top[y0:y1, x0:x1]
            err = np.abs(region[mask] - texels[mask])
            self.assertLess(err.mean(), 0.01)
            self.assertLess(err.max(), 0.06)
            self.assertLess(np.abs(region[:10, :10] - old_top[y0:y0 + 10, x0:x0 + 10]).max(), 0.1)
            outside = np.ones((1024, 1024), bool)
            outside[y0:y1, x0:x1] = False
            self.assertLess(np.abs(new_top - old_top)[outside].max(), 0.07)
            # far from the rectangle nothing changes
            self.assertTrue((new_top[:, :x0 - 8] == old_top[:, :x0 - 8]).all())
            # mip 1 and the inline 64 x 64 mip follow the gradient; mips under 16 texels wide stay as they were
            m1 = mip(t, 1, Path(d) / 'out' / 'Lighting_7002.tfc')
            cy, cx = (y0 + y1) // 4, (x0 + x1) // 4
            self.assertAlmostEqual(m1[cy, cx, 0], ((cx * 2 + 1) - x0) / w, delta=0.06)
            m64 = mip(t, 4, None)
            self.assertAlmostEqual(m64[(y0 + y1) // 32, (x0 + x1) // 32, 1], 0.5, delta=0.08)
            for k in range(7, len(t['mips'])):
                self.assertTrue((mip(t, k, None) == mip(old, k, None)).all(), k)
            entry = [e for e in manifest['edits'] if 'maxChangeOutsideRect' in e][0]
            self.assertLess(entry['maxChangeOutsideRect'], 0.07)

    def test_image_writes_a_lightmap_kept_inside_the_package_in_place(self):
        # a small lightmap (16 x 16, every mip inline and uncompressed) that one component owns
        comp, name = 'TheWorld.PersistentLevel.StaticMeshActor_105.StaticMeshComponent_97', 'DirectionalMaxComponent1_65'
        f = lightmap_fields.component_fields(self.p, self.p.by_name[comp])['lods'][0]['lightmap']
        old = lightmap_fields.texture_fields(self.p, self.p.by_name[name])
        self.assertFalse(any(m['flags'] & 1 for m in old['mips']))
        x0, y0, x1, y1 = fx.rect_bounds(f, 16, 16)
        texels = np.full((y1 - y0, x1 - x0, 3), (0.8, 0.2, 0.4))
        with tempfile.TemporaryDirectory() as d:
            npz = Path(d) / 'img.npz'
            np.savez(npz, t=texels, t_mask=np.ones(texels.shape[:2], bool))
            manifest = fx.run(BAR, Path(d) / 'out', 'URB_BarTest', [
                dict(op='image', component=comp, slot=1, npz=str(npz), key='t')], cache='Lighting_7003')
            # nothing to redirect: no variant cache, and the texture keeps its size and its cache name
            self.assertIsNone(manifest['cache'])
            self.assertEqual(len(manifest['outputs']), 1)
            q = lighting.Package(Path(d) / 'out' / 'URB_BarTest.upk')
            t = lightmap_fields.texture_fields(q, q.by_name[name])
            self.assertEqual(t['cache'], old['cache'])
            self.assertEqual([e['size'] for e in q.exports], [e['size'] for e in self.p.exports])

            def mip(pkg, fields, k):
                m = fields['mips'][k]
                return decode(bytes(pkg.data[m['payloadOffset']:m['payloadOffset'] + m['bytes']]), m['width'],
                              m['height']) / 255.0

            # the top mip and the 8 x 8 and 4 x 4 mips below it take the new light
            for k, (cy, cx) in [(0, (8, 8)), (1, (4, 4)), (2, (2, 2))]:
                self.assertLess(np.abs(mip(q, t, k)[cy, cx] - (0.8, 0.2, 0.4)).max(), 0.06, k)
                self.assertGreater(np.abs(mip(q, t, k) - mip(self.p, old, k)).max(), 0.1, k)


# URB_StreetOverpass as shipped: one of its shadow-map textures saves no cache name (every mip inside the map)
OVERPASS, NO_OVERPASS = labpaths.test_file('XCOM_OVERPASS_UPK', labpaths.lwr_cooked('URB_StreetOverpass.upk'),
                                           'URB_StreetOverpass.upk')
NO_CACHE_TEXTURE = 'ShadowMapTexture2D_173'      # 1024 x 1024 G8, NeverStream; XComDestructibleActor_18's shadow


@unittest.skipUnless(OVERPASS and OVERPASS.exists(), NO_OVERPASS)
class TextureWithoutCacheName(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(OVERPASS)

    def test_fields_read_with_no_cache(self):
        t = lightmap_fields.texture_fields(self.p, self.p.by_name[NO_CACHE_TEXTURE])
        self.assertIsNone(t['cache'])
        self.assertIsNone(t['cacheNameOffset'])
        self.assertEqual((t['mips'][0]['width'], t['mips'][0]['height']), (1024, 1024))
        self.assertTrue(all(m['inline'] for m in t['mips'] if m['bytes']))

    def test_gray_writes_it_in_place(self):
        index = self.p.by_name[NO_CACHE_TEXTURE]
        old = lightmap_fields.texture_fields(self.p, index)
        f = fx.Fixture(OVERPASS, 'Lighting_7003')
        f.gray(index, 0, 0, np.full((64, 64), 0.5), np.ones((64, 64), bool))
        self.assertIn(index, f.in_package)
        self.assertFalse(f.redirected)
        with tempfile.TemporaryDirectory() as d:
            manifest = f.finish(Path(d), 'URB_StreetOverpassTest')
            self.assertIsNone(manifest['cache'])
            q = lighting.Package(Path(d) / 'URB_StreetOverpassTest.upk')
            t = lightmap_fields.texture_fields(q, index)
            self.assertIsNone(t['cache'])
            m = t['mips'][0]
            top = np.frombuffer(bytes(q.data[m['payloadOffset']:m['payloadOffset'] + m['bytes']]), np.uint8)
            top = top.reshape(1024, 1024)
            self.assertTrue((top[:64, :64] == 128).all())
            o = old['mips'][0]
            before = np.frombuffer(bytes(self.p.data[o['payloadOffset']:o['payloadOffset'] + o['bytes']]), np.uint8)
            self.assertTrue((top[64:] == before.reshape(1024, 1024)[64:]).all())


if __name__ == '__main__':
    unittest.main()
