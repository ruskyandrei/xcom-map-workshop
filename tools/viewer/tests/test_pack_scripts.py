"""A map pack's Install.cmd and Uninstall.cmd (pack_scripts.py) on the temporary game installs of test_play.py:
- review finding 26: Uninstall keeps a map whose records were edited since in the game, with its files, and keeps
  noting what it left; a card changed since keeps the pack's maps; the cards install no longer says no file was
  changed after adding drop-in lines;
- review finding 25: the scripts run the same from a shell that set PowerShell 7's module path;
- a config is written beside itself and put in its place, or left as it was."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'bake' / 'tests'))
import installs  # noqa: E402,F401  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import manager  # noqa: E402
import test_manager  # noqa: E402  (its Manager is used by name, so that its tests don't run here again)
from test_manager import OTHER, OTHER_ID, pack_env, powershell_report  # noqa: E402
import test_play  # noqa: E402
from viewer_fixtures import ID  # noqa: E402

VARIANT = test_play.VARIANT
WINDOWS_POWERSHELL = sys.platform == 'win32' and shutil.which('powershell')


def xcom_running():
    import procs
    return procs.running('XComEW.exe')


@unittest.skipUnless(WINDOWS_POWERSHELL, 'the pack\'s scripts run with Windows PowerShell')
class PackScripts(unittest.TestCase):
    setUp = test_play.Play.setUp
    M = test_manager.Manager
    player, package, files, records, more_missions, second, card_game = (
        M.player, M.package, M.files, M.records, M.more_missions, M.second, M.card_game)
    run_script, run_script_with = M.run_script, M.run_script_with
    del M

    def setup_pack(self, name, **request):
        """Two projects on Bar built and packed (the request's mode, additional by default), unzipped: its folder."""
        if xcom_running(): self.skipTest('XCOM is running: the scripts refuse, as they should')
        self.package()
        self.second()
        r = manager.pack(self.store, self.builds, self.player(), dict(dict(projects=[ID, OTHER_ID], mode='additional'),
                                                                       name=name, **request))
        folder = Path(self.temp.name) / f'unzipped {name}'
        with zipfile.ZipFile(r['zip']) as z: z.extractall(folder)
        return folder, r

    def edit_record(self, game, variant):
        path = game / 'XEW/XComGame/Config/DefaultMaps.ini'
        lines = dep.lines_of(path.read_bytes())
        at = next(i for i, l in enumerate(lines) if dep.is_record(l) and dep.field(l, 'Name') == variant)
        lines[at] = dep.set_field(lines[at], 'DisplayName', 'Edited by hand')
        path.write_bytes(dep.EOL.join(lines))

    def drop_records(self, game, variant):
        path = game / 'XEW/XComGame/Config/DefaultMaps.ini'
        path.write_bytes(dep.EOL.join(l for l in dep.lines_of(path.read_bytes())
                                      if not (dep.is_record(l) and dep.field(l, 'Name') == variant)))

    def test_uninstall_keeps_a_map_whose_records_were_edited_and_notes_what_it_left(self):
        self.more_missions(self.copy)
        folder, r = self.setup_pack('Edited')
        cooked = self.copy / 'XEW/XComGame/CookedPCConsole'
        state = self.copy / 'XCOM Map Workshop/packs' / f'{r["folder"]}.json'
        own = sorted(p.name for p in cooked.iterdir())
        self.run_script(folder, 'Install.cmd', self.copy)
        self.edit_record(self.copy, VARIANT)
        out = self.run_script(folder, 'Uninstall.cmd', self.copy)
        self.assertIn(f'the records of {VARIANT} have changed', out)
        self.assertIn(f'{VARIANT}.upk stays', out)
        self.assertTrue((cooked / f'{VARIANT}.upk').is_file())               # the edited map's files stay
        self.assertFalse((cooked / f'{OTHER}.upk').exists())                 # the other map's go
        self.assertEqual(self.records(self.copy, OTHER), [])
        left = json.loads(state.read_text(encoding='utf-8-sig'))             # still noted, with only what is left
        self.assertEqual([b['variant'] for b in left['added']], [VARIANT])
        self.assertIn(f'{VARIANT}.upk', [f['name'] for f in left['files']])
        self.assertNotIn(f'{OTHER}.upk', [f['name'] for f in left['files']])
        # an install over it stops until it is put right
        out = self.run_script_with(folder, 'Install.cmd', self.copy, code=1)
        self.assertIn('could not be taken out', out)
        # the records taken out by hand: the next Uninstall takes the files and forgets the pack
        self.drop_records(self.copy, VARIANT)
        self.run_script(folder, 'Uninstall.cmd', self.copy)
        self.assertEqual(sorted(p.name for p in cooked.iterdir()), own)
        self.assertFalse(state.exists())

    def test_a_card_changed_since_keeps_the_packs_maps(self):
        """The cards way: the card names the folder's maps, so while it stays (changed since) they stay too. And the
        install says what it changed: with a drop-in line added, not that no file was changed."""
        for game in (self.copy,):
            self.card_game(game)
            (game / 'XEW/XComGame/Config/DefaultMutatorLoader.ini').write_bytes(test_play.MUTATOR_LOADER)
            (game / 'XEW/XComGame/Config/DefaultRandomSpawns.ini').write_bytes(test_play.RANDOM_SPAWNS)
        if xcom_running(): self.skipTest('XCOM is running: the scripts refuse, as they should')
        self.package(exclusion=True)
        self.second()
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID, OTHER_ID], mode='additional', name='Card kept'))
        folder = Path(self.temp.name) / 'unzipped card kept'
        with zipfile.ZipFile(r['zip']) as z: z.extractall(folder)
        out = self.run_script(folder, 'Install.cmd', self.copy)
        self.assertIn('drop-in exclusion(s) were added', out)
        self.assertIn('No other file of the game was changed', out)
        self.assertNotIn('No file of the game was changed', out)
        there = self.copy / 'XEW/XComGame/CookedPCConsole' / r['folder']
        card = there / ('LWRMapPack_%04d.upk' % r['card'])
        card.write_bytes(card.read_bytes() + b'edited')
        out = self.run_script(folder, 'Uninstall.cmd', self.copy)
        self.assertIn('changed since: it stays', out)
        self.assertTrue((there / f'{VARIANT}.upk').is_file() and (there / f'{OTHER}.upk').is_file())
        state = self.copy / 'XCOM Map Workshop/packs' / f'{r["folder"]}.json'
        self.assertTrue(state.is_file())
        card.unlink()
        self.run_script(folder, 'Uninstall.cmd', self.copy)
        self.assertFalse(there.exists() or state.exists())

    def test_a_config_is_replaced_whole_or_left_as_it_was(self):
        """(review finding 26's leftover) The scripts write a config beside itself and put it in its place: none of
        their temporary files is left, and a config that can't be replaced (here read-only) stays byte for byte."""
        import os
        import stat
        self.more_missions(self.copy)
        folder, r = self.setup_pack('Whole')
        config = self.copy / 'XEW/XComGame/Config'
        maps = config / 'DefaultMaps.ini'
        before = maps.read_bytes()
        self.assertIn('Installed 2 map(s)', self.run_script(folder, 'Install.cmd', self.copy))
        self.assertNotEqual(maps.read_bytes(), before)
        self.assertEqual(list(config.glob('*.pack-new')), [])
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual((maps.read_bytes(), list(config.glob('*.pack-new'))), (before, []))
        os.chmod(maps, stat.S_IREAD)
        try:
            out = self.run_script_with(folder, 'Install.cmd', self.copy, code=1)
        finally:
            os.chmod(maps, stat.S_IREAD | stat.S_IWRITE)
        self.assertIn('could not be replaced', out)
        self.assertIn('it is left as it was', out)
        self.assertEqual(maps.read_bytes(), before)
        self.assertEqual(list(config.glob('*.pack-new')), [])

    def test_the_scripts_run_from_powershell_7(self):
        """Review finding 25: a suite (or a user) in PowerShell 7 hands Windows PowerShell 7's module path, where it does
        not find Get-FileHash. Install.cmd clears it, so the scripts work the same."""
        pwsh = shutil.which('pwsh')
        if not pwsh: self.skipTest('PowerShell 7 is not installed')
        home = subprocess.run([pwsh, '-NoProfile', '-Command', '$PSHOME'], capture_output=True, text=True, timeout=60).stdout.strip()
        if not home or not (Path(home) / 'Modules').is_dir(): self.skipTest('PowerShell 7 has no Modules folder')
        env = pack_env([Path(home) / 'Modules'])
        self.assertIn('Get-FileHash: False', powershell_report(env))       # the trap, as a PowerShell 7 shell sets it
        self.more_missions(self.copy)
        folder, r = self.setup_pack('From seven')
        out = self.run_script_with(folder, 'Install.cmd', self.copy, env=env)
        self.assertIn('Installed 2 map(s)', out)
        self.assertIn('exactly as it was before the pack', self.run_script_with(folder, 'Uninstall.cmd', self.copy, env=env))


if __name__ == '__main__':
    unittest.main()
