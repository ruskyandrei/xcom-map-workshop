"""A map's own picture (map_frame.py): a top-level Texture2D named MapPicture, made as the game's map pictures are.

The recipe checks run anywhere. The map-backed checks read the configured install (tools/viewer/settings.py) and skip
without it: the game's own map-image packages, which the recipe was read from, and URB_TruckStop_Stream, a small map
with no texture of its own, where pictures are written."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
import map_frame  # noqa: E402
import package as viewer_package  # noqa: E402

sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402

IMAGES, NO_IMAGES = labpaths.test_file('XCOM_MAP_IMAGES_UPK', labpaths.lwr_cooked('UILibrary_MapImages_SF.upk'),
                                       'UILibrary_MapImages_SF.upk')
# the recipe's tags as the game saves them: [name, property type, enum, size, value]
TAGS = [
    ['SizeX', 'IntProperty', None, 4, 512],
    ['SizeY', 'IntProperty', None, 4, 256],
    ['OriginalSizeX', 'IntProperty', None, 4, 512],
    ['OriginalSizeY', 'IntProperty', None, 4, 256],
    ['Format', 'ByteProperty', 'EPixelFormat', 8, 'PF_DXT1'],
    ['MipTailBaseIdx', 'IntProperty', None, 4, 9],
    ['SRGB', 'BoolProperty', None, 0, False],
    ['NeverStream', 'BoolProperty', None, 0, True],
    ['LODGroup', 'ByteProperty', 'TextureGroup', 8, 'TEXTUREGROUP_UI'],
]
EXTRA = ['CompressionNoAlpha', 'BoolProperty', None, 0, True]
KINDS = {'int': 'IntProperty', 'bool': 'BoolProperty', 'enum': 'ByteProperty'}


def recipe_tags():
    """The recipe's properties as `describe` gives a saved picture's."""
    out = []
    for name, kind, value in map_frame.RECIPE['properties']:
        enum, value = (value[0], value[1]) if kind == 'enum' else (None, value)
        out.append([name, KINDS[kind], enum, {'int': 4, 'bool': 0, 'enum': 8}[kind], value])
    return out


class Recipe(unittest.TestCase):
    def test_the_recipe_is_the_picture_the_game_saves(self):
        self.assertEqual(recipe_tags(), TAGS)
        self.assertEqual(map_frame.RECIPE['flags'], 0x000F000400000000)
        self.assertEqual(map_frame.RECIPE['tail'], [0, 1, 0])
        self.assertEqual((map_frame.WIDTH, map_frame.HEIGHT, map_frame.PIXEL_BYTES), (512, 256, 65536))


@unittest.skipUnless(IMAGES and IMAGES.exists(), NO_IMAGES)
class GamePictures(unittest.TestCase):
    """The game's own map pictures, every one of the install's four packages: what the recipe was read from."""
    def test_every_picture_of_the_game_is_made_as_the_recipe_says(self):
        seen = 0
        for library in map_frame.LIBRARIES:
            path = IMAGES.with_name(library + '_SF.upk')
            if not path.exists():
                continue
            p = viewer_package.Package(path)
            for index in range(1, len(p.exports) + 1):
                if p.cls(index) != 'Texture2D':
                    continue
                d = map_frame.describe(p, index)
                with self.subTest(picture=p.name(index)):
                    self.assertEqual(d['flags'], map_frame.RECIPE['flags'])
                    # the six DLC pictures save one property more, which the recipe leaves out as the other 99 do
                    extra = [t for t in d['properties'] if t[0] == 'CompressionNoAlpha']
                    self.assertEqual(extra, [EXTRA] if 'DLC' in library else [])
                    self.assertEqual([t for t in d['properties'] if t not in extra], TAGS)
                    self.assertEqual(d['bytes'], map_frame.EXPORT_BYTES + 25 * len(extra))
                    self.assertEqual(d['propertyBytes'], 278 + 25 * len(extra))
                    source, (mip,) = d['sourceArt'], d['mips']
                    self.assertEqual((source['flags'], source['count'], source['size']), (0, 0, 0))
                    self.assertEqual(source['offset'], source['after'])
                    self.assertEqual((mip['flags'], mip['count'], mip['size']), (0, 65536, 65536))
                    self.assertEqual(mip['offset'], mip['after'])
                    self.assertEqual((mip['width'], mip['height']), (512, 256))
                    self.assertEqual(len(d['pixels']), map_frame.PIXEL_BYTES)
                    self.assertEqual(d['tail'], map_frame.RECIPE['tail'])
                seen += 1
        self.assertGreaterEqual(seen, 98)       # the base game's package alone has 98


if __name__ == '__main__':
    unittest.main()
