"""A built map's own lighting cache put inside the map (inline_lighting.py; LWR map packs, F-140)."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_lighting as lighting  # noqa: E402
import inline_lighting  # noqa: E402
import lighting_fixture as fx  # noqa: E402
import lightmap_fields  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
EAST_FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'
CACHE = 'Lighting_7004'


def quiet(*_):
    pass


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Inline(unittest.TestCase):
    """URB_Bar relit by the fixture writer into a cache of its own (two textures: one painted, one moved there as it
    was), then that cache put inside the map."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        d = Path(cls.dir.name)
        fx.run(BAR, d / 'built', 'URB_BarInline', [dict(op='redirect', texture='NormalizedAverageColor0_5'),
                                                   dict(op='paint', component=EAST_FLOOR, slot=1, rgb=[1, 0, 0])], cache=CACHE)
        cls.built = d / 'built' / 'URB_BarInline.upk'
        cls.tfc = d / 'built' / f'{CACHE}.tfc'
        cls.out = d / 'inline' / 'URB_BarInline.upk'
        cls.result = inline_lighting.inline(cls.built, cls.out, CACHE, echo=quiet)
        cls.src, cls.dst = lighting.Package(cls.built), lighting.Package(cls.out)
        cls.chosen = [cls.src.name(k) for k in range(1, len(cls.src.exports) + 1)
                      if cls.src.cls(k) in lightmap_fields.TEXTURE_CLASSES and cls.src.effective(k, 'TextureFileCacheName') == CACHE]

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_every_texture_of_the_cache_holds_its_mips_inside(self):
        self.assertGreaterEqual(len(self.chosen), 2)
        self.assertEqual(self.result['textures'], len(self.chosen))
        cache_bytes = self.tfc.read_bytes()
        moved = 0
        for name in self.chosen:
            with self.subTest(name):
                k, j = self.dst.by_name[name], self.src.by_name[name]
                self.assertIsNone(self.dst.effective(k, 'TextureFileCacheName'))
                self.assertIs(self.dst.effective(k, 'NeverStream'), True)
                t = lightmap_fields.texture_fields(self.dst, k)
                self.assertTrue(all(m['inline'] and not m['flags'] for m in t['mips']))
                self.assertEqual(inline_lighting.mips_of(self.dst, k), inline_lighting.mips_of(self.src, j, cache_bytes))
                moved += sum(m['flags'] & 1 for m in lightmap_fields.texture_fields(self.src, j)['mips'])
        self.assertEqual(self.result['mips'], moved)
        self.assertGreater(self.result['bytes'], 0)

    def test_nothing_else_of_the_map_changes(self):
        """The textures of the game's shared Lighting cache, and every other export, are as they were."""
        chosen = {self.src.by_name[n] for n in self.chosen}
        self.assertEqual(len(self.dst.exports), len(self.src.exports))
        shared = 0
        for k in range(1, len(self.src.exports) + 1):
            if k in chosen: continue
            a, b = self.src.exports[k - 1], self.dst.exports[k - 1]
            self.assertEqual(self.src.data[a['off']:a['off'] + a['size']], self.dst.data[b['off']:b['off'] + b['size']], self.src.name(k))
            if self.src.cls(k) in lightmap_fields.TEXTURE_CLASSES and self.src.effective(k, 'TextureFileCacheName') == 'Lighting':
                shared += 1
        self.assertGreater(shared, 0)

    def test_a_map_already_inside_has_nothing_to_move(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(inline_lighting.NotNamed):
                inline_lighting.inline(self.out, Path(d) / 'again.upk', CACHE, self.tfc, echo=quiet)
            self.assertFalse((Path(d) / 'again.upk').exists())

    def test_a_cache_too_short_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            short = Path(d) / f'{CACHE}.tfc'
            short.write_bytes(self.tfc.read_bytes()[:1000])
            with self.assertRaisesRegex(inline_lighting.InlineError, 'outside the cache'):
                inline_lighting.inline(self.built, Path(d) / 'out.upk', CACHE, short, echo=quiet)

    def test_command_line(self):
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with mock.patch.object(sys, 'argv', ['inline_lighting.py', str(self.built), str(Path(d) / 'a.upk'), '--cache', 'Nobody_1']), \
                    contextlib.redirect_stderr(err):
                self.assertEqual(inline_lighting.main(), 2)
            self.assertIn('names the cache Nobody_1', err.getvalue())
            out = io.StringIO()
            with mock.patch.object(sys, 'argv', ['inline_lighting.py', str(self.built), str(Path(d) / 'b.upk'), '--cache', CACHE]), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(inline_lighting.main(), 0)
            self.assertEqual((Path(d) / 'b.upk').read_bytes(), self.out.read_bytes())
            self.assertIn(f'moved inside from {CACHE}.tfc', out.getvalue())


if __name__ == '__main__':
    unittest.main()
