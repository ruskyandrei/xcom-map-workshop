"""Installing the editor's variant packages in the lab's test slot (tools/lab/lab_install.py), on a temporary copy of
the lab's layout."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import deploy_fixture as dep  # noqa: E402
import lab_install  # noqa: E402
from fixtures import record  # noqa: E402


class LabInstall(unittest.TestCase):
    def setUp(self):
        running = dep.game_running
        self.addCleanup(setattr, dep, 'game_running', running)
        dep.game_running = lambda: False
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.game, self.work, self.builds = root / 'game', root / 'work', root / 'builds'
        self.cfg = self.game / 'XEW/XComGame/Config'
        self.cfg.mkdir(parents=True)
        (self.game / 'XEW/XComGame/CookedPCConsole').mkdir(parents=True)
        (self.game / 'XComLab-copy.txt').write_text('lab')
        slot = dep.set_field(record('templeship'), 'DisplayName', dep.TEST_SLOT)
        (self.cfg / 'DefaultMaps.ini').write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', record('bar'), slot, b'']))
        (self.cfg / 'DefaultLZMutator.ini').write_bytes(dep.EOL.join([b'LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))', b'']))

    def tearDown(self):
        self.tmp.cleanup()

    def package(self, variant='URB_Bar_Add_1', patch='patch_urb_bar_add_1', built='2026-11-07T11:00:00', tag=b''):
        folder = self.builds / variant
        cooked = folder / 'CookedPCConsole'
        cooked.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, data in [(f'{variant}.upk', b'relit seeded map' + tag), ('Lighting_4242.tfc', b'lightmaps' + tag),
                           (f'{patch}.upk', b'patch' + tag)]:
            (cooked / name).write_bytes(data)
            files[f'CookedPCConsole/{name}'] = hashlib.sha256(data).hexdigest()
        m = dict(schema=lab_install.SCHEMA, schemaVersion=1, buildId=f'{variant}-{built}', builtAt=built,
                 project=dict(id='p1', name='Test', revision=1), source=dict(map='URB_Bar', sha256='s' * 64),
                 variant=variant, patch=patch, files=files, streams=[patch])
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        return folder, m

    def slot(self):
        lines = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)
        return lines[2]

    def test_install_puts_the_package_in_the_test_slot(self):
        folder, m = self.package()
        _, plan = lab_install.install(folder, game=self.game, work=self.work)
        slot = self.slot()
        self.assertEqual(dep.field(slot, 'Name'), 'URB_Bar_Add_1')
        self.assertEqual(dep.field(slot, 'DisplayName'), dep.TEST_SLOT)
        self.assertIn(b'StreamingMaps[2]=( MapName="patch_urb_bar_add_1"', slot)
        cooked = self.game / 'XEW/XComGame/CookedPCConsole'
        self.assertEqual((cooked / 'patch_urb_bar_add_1.upk').read_bytes(), b'patch')
        self.assertEqual((cooked / 'URB_Bar_Add_1.upk').read_bytes(), b'relit seeded map')
        self.assertEqual(plan['seedPlans'], [])
        lz = (self.cfg / 'DefaultLZMutator.ini').read_bytes()
        self.assertIn(b'LZArray=(MapName="URB_Bar_Add_1",StartLoc=(X=1,Y=2,Z=3))', lz)
        ledger = lab_install.read_ledger(self.work)
        self.assertEqual(ledger[m['buildId']]['record'], plan['record'])
        self.assertEqual(lab_install.new_packages(self.builds, self.work), [])
        dep.restore(plan['record'], self.game)
        self.assertEqual(dep.field(self.slot(), 'Name'), dep.field(record('templeship'), 'Name'))

    def test_a_package_changed_since_its_build_is_refused(self):
        folder, _ = self.package()
        (folder / 'CookedPCConsole' / 'URB_Bar_Add_1.upk').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'differs from its manifest'):
            lab_install.install(folder, game=self.game, work=self.work)
        self.assertEqual(dep.field(self.slot(), 'DisplayName'), dep.TEST_SLOT)
        self.assertNotEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_Add_1')

    def test_watch_installs_the_newest_new_package_and_passes_over_older_ones(self):
        self.package('URB_Bar_A_1', 'patch_urb_bar_a_1', '2026-11-07T11:00:00')
        _, newest = self.package('URB_Bar_B_2', 'patch_urb_bar_b_2', '2026-11-07T11:05:00')
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True)
        self.assertEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_B_2')
        ledger = lab_install.read_ledger(self.work)
        self.assertIn('installedAt', ledger[newest['buildId']])
        self.assertEqual(ledger['URB_Bar_A_1-2026-11-07T11:00:00']['superseded'], newest['buildId'])
        # a rebuild of the same project is a new package, installed over the last
        self.package('URB_Bar_B_2', 'patch_urb_bar_b_2', '2026-11-07T11:20:00', tag=b' v2')
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True)
        cooked = self.game / 'XEW/XComGame/CookedPCConsole'
        self.assertEqual((cooked / 'URB_Bar_B_2.upk').read_bytes(), b'relit seeded map v2')
        self.assertEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_B_2')
        # both installs may fall in one second: each keeps its own record, and the latest undoes both
        ledger = lab_install.read_ledger(self.work)
        first, second = ledger[newest['buildId']]['record'], ledger['URB_Bar_B_2-2026-11-07T11:20:00']['record']
        self.assertNotEqual(first, second)
        self.assertEqual(json.loads(Path(second).read_text())['previous'], first)
        dep.restore(second, self.game)
        self.assertEqual(dep.field(self.slot(), 'Name'), dep.field(record('templeship'), 'Name'))

    def test_watch_can_leave_the_packages_already_there(self):
        self.package('URB_Bar_Old_1', 'patch_urb_bar_old_1', '2026-11-07T10:00:00')
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True, pending=False)
        self.assertNotEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_Old_1')
        self.assertEqual(lab_install.read_ledger(self.work), {})
        # with pending, it takes the package that was there
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True, pending=True)
        self.assertEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_Old_1')

    def test_watch_waits_while_the_game_runs(self):
        self.package()
        dep.game_running = lambda: True
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True)
        self.assertNotEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_Add_1')
        self.assertEqual(lab_install.read_ledger(self.work), {})
        dep.game_running = lambda: False
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True)
        self.assertEqual(dep.field(self.slot(), 'Name'), 'URB_Bar_Add_1')

    def test_a_failed_install_is_recorded_and_not_tried_again(self):
        folder, m = self.package()
        (self.game / 'XEW/XComGame/CookedPCConsole/patch_urb_bar_add_1.upk').write_bytes(b'someone else\'s')
        lab_install.watch(self.builds, 0, game=self.game, work=self.work, once=True)
        ledger = lab_install.read_ledger(self.work)
        self.assertIn('was not put there by this tool', ledger[m['buildId']]['failed'])
        self.assertEqual(lab_install.new_packages(self.builds, self.work), [])

    def test_the_work_folder_and_other_folders_are_not_packages(self):
        self.package()
        (self.builds / '.work' / 'x').mkdir(parents=True)
        (self.builds / '.work' / 'x' / 'manifest.json').write_text('{}')
        (self.builds / 'notes').mkdir()
        self.assertEqual([m['variant'] for m, _ in lab_install.packages(self.builds)], ['URB_Bar_Add_1'])


if __name__ == '__main__':
    unittest.main()
