"""Materials' programs on their export records (material_programs.py, export 43): the shader map matching rule, the
shader cache kept in the cache folder and read back the same, no cache meaning no programs; on the install, an
export of COverseer_TheBarrens whose RocksRiver_VertPaint draws Dirt, Grass and Leaves as the game mixes them
(F-167), every texture its program samples exported, and its painted pieces' colour files as long as their meshes."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import material_programs  # noqa: E402
import shader_cache  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BARRENS, NO_BARRENS = labpaths.test_file('XCOM_BARRENS_UPK', labpaths.lwr_cooked('COverseer_TheBarrens.upk'),
                                         'COverseer_TheBarrens.upk')
CACHE, NO_CACHE = labpaths.test_file('XCOM_SHADER_CACHE_UPK', labpaths.lwr_cooked(shader_cache.FILE_NAME),
                                     'the RefShaderCache')


class Map:
    def __init__(self, base, switches):
        self.base, self.switches = base, switches


class Matching(unittest.TestCase):
    def test_exact_then_by_values(self):
        exact = Map(b'a', [('Rock', False, True)])
        loose = Map(b'a', [('Rock', True, False)])
        cache = type('C', (), {'by_base': {b'a': [exact, loose]}})()
        self.assertEqual(material_programs.match(cache, b'a', [('Rock', False, True)]), ('exact', exact))
        self.assertEqual(material_programs.match(cache, b'a', [('Rock', True, True)]), ('values', loose))
        self.assertEqual(material_programs.match(cache, b'b', []), ('none', None))
        self.assertEqual(material_programs.match(cache, b'a', [('Moss', True, True)]), ('base', None))

    def test_no_cache_no_programs(self):
        programs = material_programs.Programs(None)
        folder = Path(tempfile.mkdtemp(prefix='no-cache-'))
        try:
            self.assertIsNone(programs.cache_for(folder / 'Map.upk'))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_unlit_colour_is_its_glow(self):
        self.assertTrue(material_programs.gives_colour({'outputs': {'diffuse': {}}, 'refused': {}}))
        self.assertTrue(material_programs.gives_colour({'outputs': {}, 'refused': {}, 'unlit': True}))
        self.assertFalse(material_programs.gives_colour({'outputs': {}, 'refused': {'glow': 'x'}, 'unlit': True}))
        self.assertFalse(material_programs.gives_colour({'outputs': {'normal': {}}, 'refused': {}}))


@unittest.skipUnless(CACHE and CACHE.exists(), NO_CACHE)
class Kept(unittest.TestCase):
    def test_kept_cache_reads_the_same(self):
        folder = Path(tempfile.mkdtemp(prefix='kept-cache-'))
        try:
            first = shader_cache._kept(CACHE, folder)
            kept = list(folder.glob('shader-cache-*.bin'))
            self.assertEqual(len(kept), 1)
            again = shader_cache._kept(CACHE, folder)
            self.assertIsNone(again.package)                  # read from the kept file, not the package
            self.assertEqual(len(again.shaders), len(first.shaders))
            m = again.find_maps('172d031942d928ea4848ee82989329c6')[0]
            self.assertEqual(again.name(m), 'ENV_ForestGround')
            sid = next(iter(again.shader_refs(m)['FLocalVertexFactory'].values()))
            self.assertEqual(again.shader_code(sid), first.shader_code(sid))
        finally:
            shutil.rmtree(folder, ignore_errors=True)


@unittest.skipUnless(BARRENS and BARRENS.exists() and CACHE and CACHE.exists(), NO_BARRENS)
class Barrens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import export
        cls.folder = Path(tempfile.mkdtemp(prefix='programs-export-'))
        export.export_map(BARRENS, cls.folder, 'map')
        cls.generation = next((cls.folder / BARRENS.stem).glob('*-v%d-map' % export.EXPORT_VERSION))
        cls.scene = json.loads((cls.generation / 'scene.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_rocks_river_draws_its_layers(self):
        record = next(m for m in self.scene['materials'].values()
                      if m['name'].endswith('RocksRiver_VertPaint'))
        program = record['program']
        named = {t['parameter']: t for t in program['textures'].values() if t.get('parameter')}
        self.assertTrue({'Dirt', 'Grass', 'Leaves'} <= set(named), sorted(named))
        self.assertNotIn('Rock', named)                        # never sampled by its shader
        for t in program['textures'].values():
            texture = self.scene['textures'][t['texture']]
            self.assertTrue((self.generation / texture['url']).is_file(), texture['url'])
        self.assertEqual(record['diffuse'] is not None, True)  # today's fields stay
        kinds = {s['kind'] for sources in program['inputs'].values() for s in sources if s}
        self.assertIn('color', kinds)

    def test_painted_pieces_have_their_colours(self):
        painted = [o for o in self.scene['objects'] if o.get('paint')]
        self.assertTrue(painted)
        for o in painted[:20]:
            vertices = self.scene['meshes'][o['mesh']]['vertices']
            self.assertEqual((self.generation / o['paint']).stat().st_size, 4 * vertices, o['id'])

    def test_atmosphere_is_on_the_scene(self):
        self.assertIn('fog', self.scene['atmosphere']['world'])


if __name__ == '__main__':
    unittest.main()
