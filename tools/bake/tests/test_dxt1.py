"""The numpy DXT1 encoder and decoder, checked against PIL's DDS decoder; `lightmap_textures` reads a lightmap's top
mip with this decoder."""
import io
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import dxt1  # noqa: E402
from texture import dds_header  # noqa: E402


def pil_decode(raw, width, height):
    image = Image.open(io.BytesIO(dds_header(width, height, 'DXT1', len(raw)) + raw)).convert('RGB')
    return np.asarray(image, dtype=np.float64) / 255.0


class Dxt1(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        # smooth gradients plus noise, like a lightmap, and a few hard edges
        y, x = np.mgrid[0:64, 0:64] / 63.0
        self.image = np.clip(np.stack([x, y, 0.5 * (x + y)], -1) + rng.normal(0, 0.02, (64, 64, 3)), 0, 1)
        self.image[20:28, 30:50] = [0.9, 0.2, 0.1]

    def test_decoder_matches_pil(self):
        raw = dxt1.encode_blocks(dxt1.image_blocks(self.image).reshape(-1, 16, 3))
        ours = dxt1.decode_image(raw, 64, 64)
        # PIL rounds the two interpolated palette entries to 8 bits
        self.assertLessEqual(np.abs(ours - pil_decode(raw, 64, 64)).max(), 1 / 255 + 1e-9)

    def test_encoding_error_is_small(self):
        raw = dxt1.encode_blocks(dxt1.image_blocks(self.image).reshape(-1, 16, 3))
        err = np.abs(dxt1.decode_image(raw, 64, 64) - self.image)
        self.assertLess(np.sqrt((err ** 2).mean()), 0.02)
        self.assertLess(err.max(), 0.15)

    def test_solid_blocks_are_exact_and_four_colour_mode_is_kept(self):
        blocks = np.repeat(np.array([[[0, 0, 0]], [[1, 1, 1]], [[1, 0, 0]], [[16 / 31, 32 / 63, 8 / 31]]], float),
                           16, axis=1)
        raw = dxt1.encode_blocks(blocks)
        self.assertTrue(np.abs(dxt1.decode_blocks(raw) - blocks).max() < 2e-3)   # RGB565 expansion
        words = np.frombuffer(raw, '<u4').reshape(-1, 2)
        self.assertTrue(((words[:, 0] & 0xFFFF) >= (words[:, 0] >> 16)).all())
        # a two-colour block keeps both colours and never decodes to black
        two = np.array([[0.8, 0.6, 0.4]] * 8 + [[0.2, 0.3, 0.4]] * 8)[None]
        out = dxt1.decode_blocks(dxt1.encode_blocks(two))
        self.assertLess(np.abs(out - two).max(), 0.02)

    def test_the_lightmap_reader_decodes_with_this_decoder(self):
        """lightmap_textures reads a lightmap's top mip with this decoder, whole or a rectangle of it (PIL's rounds a
        palette's in-between colours down to whole 255ths, a third or two of one away)."""
        from unittest import mock
        import lightmap_textures
        raw = dxt1.encode_blocks(dxt1.image_blocks(self.image).reshape(-1, 16, 3))
        with mock.patch.object(lightmap_textures, 'top_mip_raw', return_value=(raw, 64, 64)):
            whole = lightmap_textures.top_mip_rgb(None, 1)
            self.assertTrue((whole == dxt1.decode_image(raw, 64, 64)).all())
            for x0, y0, x1, y1 in ((0, 0, 64, 64), (5, 3, 23, 41), (8, 8, 12, 12), (61, 0, 64, 2)):
                with self.subTest(rect=(x0, y0, x1, y1)):
                    self.assertTrue((lightmap_textures.top_mip_rect(None, 1, x0, y0, x1, y1)
                                     == whole[y0:y1, x0:x1]).all())

    def test_blocks_image_round_trip(self):
        b = dxt1.image_blocks(self.image)
        self.assertEqual(b.shape, (16, 16, 16, 3))
        self.assertTrue((dxt1.blocks_image(b) == self.image).all())


if __name__ == '__main__':
    unittest.main()
