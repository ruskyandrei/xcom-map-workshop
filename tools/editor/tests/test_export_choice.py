"""The Build's choice of export (compiler.find_export, review findings 17 and 44): a project with no usable export of
its map fails the build with its own "build failed:" reason (a BuildError, never SystemExit from library code)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402
import compiler  # noqa: E402

SHA = 'a3ae5a73457c3c3f' + '0' * 48


class NoExport(unittest.TestCase):
    def test_a_missing_or_unusable_export_is_a_build_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / 'projects' / 'project.json'
            project.parent.mkdir()
            project.write_text(json.dumps(dict(id='0f8b1234-1d2a-4b6c-8e9f-123456789abc', name='Bar', revision=1,
                                               output=dict(shipAs='URB_Bar_Test', patch='patch_URB_Bar_Test'),
                                               source=dict(map='URB_Bar', sha256=SHA, exporterVersion=36))),
                               encoding='utf-8')
            cache = root / 'cache'
            broken = cache / 'URB_Bar' / ('%s-v36-map' % SHA[:16])
            broken.mkdir(parents=True)
            (broken / 'scene.json').write_text('{"schemaVersion": 1, "na', encoding='utf-8')      # truncated
            (root / 'output').mkdir()
            b = build.Build(project, cache, root / 'output', root / 'game', None, echo=lambda *a: None)
            with self.assertRaises(build.BuildError) as failed:
                b.snapshot()
            self.assertIn('no export of URB_Bar', str(failed.exception))
            self.assertIn('prepare the map', str(failed.exception))
            with self.assertRaises(compiler.ExportMissing):
                compiler.find_export(cache, json.loads(project.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
