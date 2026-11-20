"""What the long-running server keeps of the packages it opens (review finding 19): a package is freed once nothing
holds it (no cache on its methods), and the collision cache keeps a bounded number, by the package's SHA-256, with its
answers the same after one is let go."""
import gc
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import weakref

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import pack_card  # noqa: E402
import collision  # noqa: E402
from package import Package  # noqa: E402


class Lifetime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def package_file(self, name):
        path = self.root / f'{name}.upk'
        path.write_bytes(pack_card.card(name))
        return path

    def test_a_package_is_freed_once_let_go(self):
        p = Package(self.package_file('Freed'))
        values, _ = p.properties(1)
        self.assertIs(p.properties(1)[0], values)           # read once, kept on the package itself
        ref = weakref.ref(p)
        del p, values
        gc.collect()
        self.assertIsNone(ref())

    def test_the_collision_cache_keeps_a_bounded_number_by_package(self):
        paths = [self.package_file(name) for name in ('One', 'Two')]
        scenes = [dict(source=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest()), meshes={'1': {}}) for p in paths]
        cache = collision.CollisionCache(limit=1)
        opened = []
        real = collision.Package
        def counting(path):
            opened.append(Path(path).name)
            return real(path)
        with mock.patch.object(collision, 'Package', counting):
            first = cache.get(self.root / 'one-v1', scenes[0], lambda: paths[0], ['1'])
            held = weakref.ref(cache.packages[scenes[0]['source']['sha256']])
            # a re-export of the same file (another generation folder) opens nothing again
            self.assertEqual(cache.get(self.root / 'one-v2', scenes[0], lambda: paths[0], ['1']), first)
            self.assertEqual(opened, ['One.upk'])
            cache.get(self.root / 'two-v1', scenes[1], lambda: paths[1], ['1'])
            gc.collect()
            self.assertIsNone(held())                        # the first let go: the limit is one
            self.assertEqual(len(cache.packages), 1)
            self.assertEqual(cache.get(self.root / 'one-v1', scenes[0], lambda: paths[0], ['1']), first)

    def test_the_collision_route_reads_a_scene_once(self):
        root = self.root / 'gen'
        root.mkdir()
        (root / 'scene.json').write_text(json.dumps(dict(meshes={'3': {}, '1': {}}, source=dict(file='x', sha256='a' * 64))),
                                         encoding='utf-8')
        cache = collision.CollisionCache()
        reads = []
        real = Path.read_text
        with mock.patch.object(Path, 'read_text', lambda self, *a, **k: reads.append(self) or real(self, *a, **k)):
            first = cache.scene(root)
            self.assertEqual(cache.scene(root), first)
        self.assertEqual(len(reads), 1)
        self.assertEqual(first, dict(meshes=['1', '3'], source=dict(file='x', sha256='a' * 64)))


if __name__ == '__main__':
    unittest.main()
