"""A map's own picture (map_frame.py): a top-level Texture2D named MapPicture, made as the game's map pictures are.

The recipe checks run anywhere. The map-backed checks read the configured install (tools/viewer/settings.py) and skip
without it: the game's own map-image packages, which the recipe was read from, and URB_TruckStop_Stream, a small map
with no texture of its own, where pictures are written."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
import map_frame  # noqa: E402
import package as viewer_package  # noqa: E402
import native_fields  # noqa: E402
import package_grow  # noqa: E402
import texture as viewer_texture  # noqa: E402

sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402

IMAGES, NO_IMAGES = labpaths.test_file('XCOM_MAP_IMAGES_UPK', labpaths.lwr_cooked('UILibrary_MapImages_SF.upk'),
                                       'UILibrary_MapImages_SF.upk')
STREAM, NO_STREAM = labpaths.test_file('XCOM_TRUCKSTOP_STREAM_UPK', labpaths.lwr_cooked('URB_TruckStop_Stream.upk'),
                                       'URB_TruckStop_Stream.upk')
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
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


def picture(seed=0):
    """A known picture: smooth gradients with a few flat bars, which DXT1 keeps closely."""
    x = np.linspace(0.0, 1.0, map_frame.WIDTH)[None, :]
    y = np.linspace(0.0, 1.0, map_frame.HEIGHT)[:, None]
    rgb = np.stack([x + 0 * y, y + 0 * x, (1 - x) * (1 - y) if not seed else x * y], -1)
    rgb[96:160, 64 + 32 * seed:192 + 32 * seed] = [0.9, 0.2, 0.1]
    return Image.fromarray(np.rint(rgb * 255).astype(np.uint8), 'RGB')


def difference(a, b):
    """(mean, largest) difference of two pictures' channels, of 255."""
    d = np.abs(np.asarray(a.convert('RGB'), np.int32) - np.asarray(b.convert('RGB'), np.int32))
    return float(d.mean()), int(d.max())


class Pixels(unittest.TestCase):
    def test_a_picture_survives_dxt1_within_its_error(self):
        image = picture()
        pixels = map_frame.encode(image)
        self.assertEqual(len(pixels), 65536)
        mean, worst = difference(map_frame.decode(pixels), image)
        self.assertLess(mean, 2.0)
        self.assertLess(worst, 24)
        self.assertEqual(map_frame.encode(image), pixels)
        self.assertEqual(len(map_frame.cache_guid(pixels)), 16)
        self.assertNotEqual(map_frame.cache_guid(pixels), map_frame.cache_guid(map_frame.encode(picture(1))))

    def test_only_a_picture_of_the_size_is_taken(self):
        with self.assertRaises(ValueError):
            map_frame.encode(Image.new('RGB', (256, 256)))
        with self.assertRaises(ValueError):
            map_frame.decode(bytes(100))
        # alpha is dropped, not blended
        rgba = picture().convert('RGBA')
        rgba.putalpha(7)
        self.assertEqual(map_frame.encode(rgba), map_frame.encode(picture()))


def read_back(path):
    """(package, the picture's export index, its description) of a written map; the native data must read whole as a
    2D texture (native_fields raises when bytes are left over)."""
    p = viewer_package.Package(path)
    found = map_frame.locate(p)
    index = found['export']
    e = p.exports[index - 1]
    fields = native_fields.fields(p, index, p.properties(index)[1] - e['off'])
    return p, index, map_frame.describe(p, index), fields, found


@unittest.skipUnless(STREAM and STREAM.exists(), NO_STREAM)
class WrittenPicture(unittest.TestCase):
    """A picture written into URB_TruckStop_Stream, which has no texture and no Texture2D import."""
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.out = Path(cls.dir.name) / 'one' / 'URB_TruckStop_Stream.upk'
        cls.out.parent.mkdir()
        cls.image = picture()
        cls.pixels = map_frame.encode(cls.image)
        cls.report = map_frame.write_picture(STREAM, cls.out, cls.pixels)
        cls.before = viewer_package.Package(STREAM)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_the_map_had_none_and_gets_one_export(self):
        self.assertIsNone(map_frame.read_picture(STREAM))
        self.assertIsNone(map_frame.locate(self.before))
        self.assertFalse(any(i['name'] == 'Texture2D' for i in self.before.imports))
        p, index, d, fields, found = read_back(self.out)
        self.assertEqual(self.report, dict(export=index, how='added'))
        self.assertEqual(len(p.exports), len(self.before.exports) + 1)
        self.assertEqual(index, len(p.exports))
        self.assertEqual(p.name(index), 'MapPicture')
        self.assertEqual(p.cls(index), 'Texture2D')
        e = p.exports[index - 1]
        self.assertEqual((e['outer'], e['arch'], e['sup']), (0, 0, 0))
        cls = p.imports[-e['cls'] - 1]
        self.assertEqual((cls['cpkg'], cls['cls'], cls['name']), ('Core', 'Class', 'Texture2D'))
        engine = p.imports[-cls['outer'] - 1]
        self.assertEqual((engine['cls'], engine['name'], engine['outer']), ('Package', 'Engine', 0))
        # every export the map had is where it was, byte for byte
        for old, new in zip(self.before.exports, p.exports):
            self.assertEqual((old['off'], old['size']), (new['off'], new['size']))
            self.assertEqual(self.before.data[old['off']:old['off'] + old['size']], p.data[new['off']:new['off'] + new['size']])

    def test_it_reads_back_as_the_recipe_with_nothing_left_over(self):
        p, index, d, fields, found = read_back(self.out)
        self.assertEqual(d['flags'], map_frame.RECIPE['flags'])
        self.assertEqual(d['properties'], TAGS)
        self.assertEqual(d['bytes'], map_frame.EXPORT_BYTES)
        self.assertEqual(d['propertyBytes'], 278)
        self.assertEqual([kind for _, kind in fields], ['bulk', 'bulk', 'cook16'])
        source, (mip,) = d['sourceArt'], d['mips']
        self.assertEqual((source['flags'], source['count'], source['size'], source['offset']), (0, 0, 0, source['after']))
        self.assertEqual((mip['flags'], mip['count'], mip['size'], mip['offset']), (0, 65536, 65536, mip['after']))
        self.assertEqual((mip['width'], mip['height']), (512, 256))
        self.assertEqual(d['pixels'], self.pixels)
        self.assertEqual(d['guid'], map_frame.cache_guid(self.pixels))
        self.assertEqual(d['tail'], [0, 1, 0])
        self.assertEqual(map_frame.read_picture(self.out), self.pixels)
        # a net index of its own: the map's next, and the map counts one more
        self.assertEqual(d['netIndex'], self.before.header['gens'][0][2])
        self.assertEqual(p.header['gens'][0][2], d['netIndex'] + 1)
        self.assertEqual(p.header['gens'][0][0], len(p.exports))
        # no export flags: read from the entry itself
        entry = package_grow.Grower(str(self.out)).entries[index - 1]
        self.assertEqual((entry.get('<I', 40), entry.get('<I', 44)), (0, 0))

    def test_the_editor_s_texture_reader_shows_the_picture(self):
        p, index, d, fields, found = read_back(self.out)
        png = Path(self.dir.name) / 'back.png'
        info = viewer_texture.export_texture(p, index, png)
        self.assertEqual((info['format'], info['width'], info['height'], info['mipCount']), ('PF_DXT1', 512, 256, 1))
        self.assertFalse(info['srgb'])
        self.assertIsNone(info['cache'])
        with Image.open(png) as shown:
            mean, worst = difference(shown, self.image)
            same = difference(shown, map_frame.decode(self.pixels))
        self.assertLess(mean, 2.0)
        self.assertLess(worst, 24)
        self.assertLessEqual(same[1], 1)        # Pillow's DXT1 decoder and ours round a third apart at most

    def test_a_second_picture_is_swapped_in_place(self):
        other = map_frame.encode(picture(1))
        out = Path(self.dir.name) / 'two' / self.out.name
        out.parent.mkdir()
        report = map_frame.write_picture(self.out, out, other)
        first, index, _, _, _ = read_back(self.out)
        p, index2, d, fields, found = read_back(out)
        self.assertEqual(report, dict(export=index, how='swapped'))
        self.assertEqual(index2, index)
        self.assertEqual(len(p.data), len(first.data))
        self.assertEqual([(e['off'], e['size']) for e in p.exports], [(e['off'], e['size']) for e in first.exports])
        self.assertEqual(p.header['gens'], first.header['gens'])
        self.assertEqual(d['pixels'], other)
        self.assertEqual(d['guid'], map_frame.cache_guid(other))
        # nothing else of the package changed
        lo = p.exports[index - 1]['off']
        changed = [k for k in range(first.header['chunks'][0][0], len(p.data)) if p.data[k] != first.data[k]]
        self.assertTrue(changed)
        self.assertTrue(all(lo <= k < lo + map_frame.EXPORT_BYTES for k in changed))
        # and the first again gives the first file's picture back
        back = Path(self.dir.name) / 'three' / self.out.name
        back.parent.mkdir()
        map_frame.write_picture(out, back, self.pixels)
        self.assertEqual(viewer_package.Package(back).data, first.data)

    def test_a_package_grown_twice_keeps_one_picture(self):
        other = map_frame.encode(picture(1))
        g = package_grow.Grower(str(self.out))
        index, how = map_frame.add_picture(g, other)
        out = Path(self.dir.name) / 'grown' / self.out.name
        out.parent.mkdir()
        g.write(str(out))
        p, index2, d, fields, found = read_back(out)
        first = viewer_package.Package(self.out)
        self.assertEqual((how, index, index2), ('replaced', len(first.exports), len(first.exports)))
        self.assertEqual(len(p.exports), len(first.exports))
        self.assertEqual(len(p.imports), len(first.imports))
        self.assertEqual(p.names, first.names)
        self.assertEqual(sum(1 for i in range(1, len(p.exports) + 1) if p.name(i) == 'MapPicture'), 1)
        self.assertEqual(d['pixels'], other)
        self.assertEqual(d['properties'], TAGS)
        self.assertEqual(d['netIndex'], map_frame.describe(first, index)['netIndex'])
        self.assertEqual(p.header['gens'][0][2], first.header['gens'][0][2])
        self.assertEqual(d['mips'][0]['offset'], d['mips'][0]['after'])
        self.assertGreater(p.exports[index - 1]['off'], first.exports[index - 1]['off'])
        # and a picture after another growing write of the package (the Build's edits come first)
        moved = Path(self.dir.name) / 'moved' / self.out.name
        moved.parent.mkdir()
        package_grow.Grower(str(STREAM)).write(str(moved))
        after = Path(self.dir.name) / 'after' / self.out.name
        after.parent.mkdir()
        self.assertEqual(map_frame.write_picture(moved, after, self.pixels)['how'], 'added')
        self.assertEqual(read_back(after)[2]['pixels'], self.pixels)

    @unittest.skipUnless(IMAGES and IMAGES.exists(), NO_IMAGES)
    def test_its_flags_and_property_tags_are_a_game_picture_s(self):
        game = viewer_package.Package(IMAGES)
        theirs = map_frame.describe(game, next(i for i in range(1, len(game.exports) + 1) if game.cls(i) == 'Texture2D'))
        p, index, ours, _, _ = read_back(self.out)
        self.assertEqual(ours['flags'], theirs['flags'])
        self.assertEqual(ours['properties'], theirs['properties'])
        self.assertEqual(ours['bytes'], theirs['bytes'])
        self.assertEqual(ours['tail'], theirs['tail'])
        for key in ('flags', 'count', 'size'):
            self.assertEqual(ours['sourceArt'][key], theirs['sourceArt'][key])
            self.assertEqual(ours['mips'][0][key], theirs['mips'][0][key])
        # the data byte for byte, but for what is each picture's own: net index, names' indices, offsets, pixels, GUID
        ours_class, theirs_class = p.imports[-p.exports[index - 1]['cls'] - 1], game.imports[2]
        self.assertEqual((ours_class['cpkg'], ours_class['cls'], ours_class['name']),
                         (theirs_class['cpkg'], theirs_class['cls'], theirs_class['name']))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class PictureInAMap(unittest.TestCase):
    def test_a_whole_map_takes_a_picture_and_keeps_its_texture_class(self):
        before = viewer_package.Package(BAR)
        had = [k for k, i in enumerate(before.imports) if i['name'] == 'Texture2D' and i['cls'] == 'Class']
        self.assertEqual(len(had), 1)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            pixels = map_frame.encode(picture())
            report = map_frame.write_picture(BAR, out, pixels)
            p, index, described, fields, found = read_back(out)
            self.assertEqual(report, dict(export=len(before.exports) + 1, how='added'))
            self.assertEqual(len(p.imports), len(before.imports))
            self.assertEqual(p.exports[index - 1]['cls'], -(had[0] + 1))
            self.assertEqual(described['pixels'], pixels)
            self.assertEqual(described['properties'], TAGS)
            self.assertEqual(described['netIndex'], before.header['gens'][0][2])


if __name__ == '__main__':
    unittest.main()
