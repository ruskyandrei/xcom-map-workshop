"""tools/patch/tests/test_ship_record.ps1 run from the editor suite (review finding 58: it was run by nothing, while
patchtool.ps1 is still what the Build runs for a patch). The script checks patchtool's record for a map shipped under
its own name on real record lines, and with -Config Set-ShipConfig on copies of an install's two config files (the
install's own are only read). It needs PowerShell 7 ([Text.Encoding]::Latin1)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'patch' / 'tests' / 'test_ship_record.ps1'
PWSH = shutil.which('pwsh')


def install_config():
    """(the configured LWR install's Config folder or None, why the second part skips without it)."""
    if os.environ.get('XCOM_GAME'):
        folder = Path(os.environ['XCOM_GAME']) / 'XEW' / 'XComGame' / 'Config'
    else:
        try:
            sys.path.insert(0, str(HERE.parents[1] / 'lab'))
            import labpaths
            folder = labpaths.lwr_game() / 'XEW' / 'XComGame' / 'Config'
        except Exception as error:      # noqa: BLE001  (no settings, no install: the part skips)
            return None, 'no install configured (%s)' % error
    if all((folder / f).is_file() for f in ('DefaultMaps.ini', 'DefaultLZMutator.ini')):
        return folder, ''
    return None, 'the install has no DefaultMaps.ini and DefaultLZMutator.ini in %s' % folder


@unittest.skipUnless(PWSH, 'test_ship_record.ps1 runs with PowerShell 7 (pwsh)')
class ShipRecord(unittest.TestCase):
    def run_script(self, *more):
        done = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File', str(SCRIPT), *more], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout[-4000:] + done.stderr[-2000:])
        self.assertNotIn('FAIL', done.stdout)
        return done.stdout

    def test_the_records_on_real_lines(self):
        self.assertIn('skipped', self.run_script())

    def test_set_ship_config_on_copies_of_the_installs_files(self):
        folder, why = install_config()
        if folder is None:
            self.skipTest(why)
        out = self.run_script('-Config', str(folder))
        self.assertIn('the files given with -Config are untouched', out)


if __name__ == '__main__':
    unittest.main()
