"""Textures written as the game stores them (texture.py, game-likeness plan A-S3b): a block-compressed texture as a
DDS file with every live mip, other formats and asked-for pictures as PNG, a broken chain of mips cut where it
breaks, and the server's PNG of a DDS file for a GPU without the block formats."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import texture  # noqa: E402
from package import Reader  # noqa: E402

from PIL import Image  # noqa: E402


def level(fmt, w, h, fill):
    return bytes([fill]) * texture.block_bytes(fmt, w, h)


class FakePackage:
    """What export_texture reads of a texture: its native record (inline mips) and its properties."""

    def __init__(self, fmt, sizes, srgb=True, skip=()):
        self.fmt, self.srgb = fmt, srgb
        raw = struct.pack('<4i', 0, 0, 0, 0)                     # source art: empty
        raw += struct.pack('<i', len(sizes))
        for k, (w, h) in enumerate(sizes):
            if fmt in texture.BLOCK_FORMATS:
                data = level(fmt, w, h, k + 1)
            else:
                data = bytes([40, 80, 120, 255]) * (w * h) if fmt == 'PF_A8R8G8B8' else bytes([90]) * (w * h)
            flags = 33 if k in skip else 0                        # an unused mip: dropped at cook, not inline
            raw += struct.pack('<4i', flags, len(data), len(data), 0) + (b'' if flags & 1 else data)
            raw += struct.pack('<2i', w, h)
        raw += bytes(16)                                          # the cache's ID
        self.raw = raw
        self.path = Path('.')

    def native(self, index):
        return Reader(self.raw)

    def effective(self, index, key, default=None):
        return {'Format': self.fmt, 'SRGB': self.srgb, 'TextureFileCacheName': 'None',
                'CompressionSettings': 'TC_Default'}.get(key, default)

    def name(self, index):
        return 'Made.Up.Texture'


def chain(w, h):
    out = []
    while True:
        out.append((w, h))
        if (w, h) == (1, 1):
            return out
        w, h = max(1, w // 2), max(1, h // 2)


class Dds(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix='texture-dds-'))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_dxt1_2048_has_12_levels_and_the_right_length(self):
        info = texture.export_texture(FakePackage('PF_DXT1', chain(2048, 2048)), 1, self.folder / 't.png', 'auto')
        self.assertEqual((info['container'], info['levels'], info['output']), ('dds', 12, 't.dds'))
        data = (self.folder / 't.dds').read_bytes()
        expected = sum(texture.block_bytes('PF_DXT1', w, h) for w, h in chain(2048, 2048))
        self.assertEqual(len(data), 128 + expected)
        flags, height, width, size, _, mips = struct.unpack_from('<6I', data, 8)
        self.assertEqual((height, width, size, mips), (2048, 2048, 512 * 512 * 8, 12))
        self.assertTrue(flags & 0x20000)
        self.assertEqual(data[128], 1)                            # the top level first, as stored
        self.assertEqual(data[128 + 512 * 512 * 8], 2)
        with Image.open(self.folder / 't.dds') as image:
            self.assertEqual(image.size, (2048, 2048))

    def test_non_square_dxt5_and_bc5(self):
        info = texture.export_texture(FakePackage('PF_DXT5', chain(256, 64)), 1, self.folder / 'a.png', 'auto')
        self.assertEqual(info['levels'], 9)
        info = texture.export_texture(FakePackage('PF_BC5', chain(64, 64), srgb=False), 1, self.folder / 'b.png', 'auto')
        self.assertEqual((info['container'], info['levels'], info['srgb']), ('dds', 7, False))

    def test_a_broken_chain_is_cut_where_it_breaks(self):
        sizes = [(512, 512), (256, 256), (64, 64), (32, 32)]       # the 128 level is missing
        info = texture.export_texture(FakePackage('PF_DXT1', sizes), 1, self.folder / 'c.png', 'auto')
        self.assertEqual(info['levels'], 2)
        info = texture.export_texture(FakePackage('PF_DXT1', chain(128, 128), skip={0}), 1, self.folder / 'd.png', 'auto')
        self.assertEqual((info['width'], info['levels']), (64, 7))   # an unused top mip is left out

    def test_other_formats_and_pictures_stay_png(self):
        info = texture.export_texture(FakePackage('PF_A8R8G8B8', [(8, 8)]), 1, self.folder / 'e.png', 'auto')
        self.assertEqual((info.get('container'), info['output']), (None, 'e.png'))
        info = texture.export_texture(FakePackage('PF_DXT1', chain(16, 16)), 1, self.folder / 'f.png', 'png')
        self.assertEqual((info.get('container'), info['output']), (None, 'f.png'))
        with Image.open(self.folder / 'f.png') as image:
            self.assertEqual(image.format, 'PNG')

    def test_the_servers_png_of_a_dds(self):
        texture.export_texture(FakePackage('PF_DXT5', chain(32, 32)), 1, self.folder / 'g.png', 'auto')
        import io
        with Image.open(io.BytesIO(texture.dds_png(self.folder / 'g.dds'))) as image:
            self.assertEqual((image.format, image.size, image.mode), ('PNG', (32, 32), 'RGBA'))


if __name__ == '__main__':
    unittest.main()
