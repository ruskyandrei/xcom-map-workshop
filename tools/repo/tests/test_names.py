"""The tools reach each other by putting folders on sys.path (tools/paths.py), so which file a name finds must not
depend on the order the folders went on: no two tracked Python files share a name, and none takes the name of a
standard-library module or of a package the editor installs (review finding 54)."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import paths  # noqa: E402

# the import names of tools/viewer/requirements.txt's and tools/requirements-dev.txt's packages
INSTALLED = {'numpy', 'scipy', 'PIL', 'embreex', 'playwright'}


def tracked_modules():
    """The tracked Python files' paths, repo-relative with forward slashes."""
    out = subprocess.run(['git', '-C', str(REPO), 'ls-files', '*.py'], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


class Names(unittest.TestCase):
    def test_no_two_tracked_python_files_share_a_name(self):
        seen = {}
        for path in tracked_modules():
            seen.setdefault(path.rsplit('/', 1)[-1], []).append(path)
        self.assertEqual({name: where for name, where in seen.items() if len(where) > 1}, {})

    def test_no_tracked_module_takes_a_standard_or_installed_name(self):
        taken = sys.stdlib_module_names | INSTALLED
        clash = sorted(p for p in tracked_modules() if p.rsplit('/', 1)[-1][:-3] in taken)
        self.assertEqual(clash, [])


class Use(unittest.TestCase):
    def setUp(self):
        self.saved = list(sys.path)

    def tearDown(self):
        sys.path[:] = self.saved

    def test_a_folder_goes_on_once_however_it_was_spelled(self):
        bake = str(paths.TOOLS / 'bake')
        sys.path[:] = [p for p in sys.path if paths.same(p) != paths.same(bake)]
        paths.use('bake')
        self.assertEqual(sys.path[0], bake)
        before = list(sys.path)
        paths.use('bake', 'bake')
        self.assertEqual(sys.path, before)
        # an earlier insert of the same folder spelled another way (a `..` step, the other slash) counts as there
        sys.path[:] = [p for p in sys.path if paths.same(p) != paths.same(bake)]
        sys.path.insert(0, os.path.join(str(paths.TOOLS), 'viewer', '..', 'bake').replace('\\', '/'))
        before = list(sys.path)
        paths.use('bake')
        self.assertEqual(sys.path, before)

    def test_an_unknown_folder_is_refused(self):
        with self.assertRaises(ValueError):
            paths.use('no-such-folder')


if __name__ == '__main__':
    unittest.main()
