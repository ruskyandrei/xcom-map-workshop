"""A change of a game install's files stopped part-way (review finding 2): a play's install, a campaign install, a
play's clear-up and Remove from game, each stopped after any file copy, config replacement, ledger or journal write
(a crash or a forced stop: no clean-up runs), then the next operation on the install (Remove from game, or the next
look at it). The game's files must come back byte for byte, nothing of the change left behind, and a hand edit made
in between kept and reported. On the temporary game installs of test_play.py."""
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture  # noqa: E402
import mapsini as dep  # noqa: E402
import procs  # noqa: E402
import test_play  # noqa: E402  (its Play is used by name, so that its tests don't run here again)
import test_manager  # noqa: E402

VARIANT = test_play.VARIANT


class Killed(BaseException):
    """The process stopped here: not an error, so no roll-back runs on the way out (as with a crash)."""


class Stops:
    """Counts the change's writes (each package file copied in or taken out, each config file replaced, each ledger and
    journal write) and stops at one of them, just after it is done."""
    def __init__(self, at=None):
        self.at, self.count, self.kinds = at, 0, []

    def wrap(self, kind, real):
        def step(*args, **kwargs):
            out = real(*args, **kwargs)
            self.count += 1
            self.kinds.append(kind)
            if self.count == self.at: raise Killed(f'stopped after step {self.count} ({kind})')
            return out
        return step

    def __enter__(self):
        self.patches = [mock.patch.object(dep, 'write_checked', self.wrap('config', dep.write_checked)),
                        mock.patch.object(installs, 'write_ledger', self.wrap('ledger', installs.write_ledger)),
                        mock.patch.object(installs._Change, 'save', self.wrap('journal', installs._Change.save)),
                        mock.patch.object(installs._Change, 'copy_in', self.wrap('copy', installs._Change.copy_in)),
                        mock.patch.object(installs._Change, 'take_out', self.wrap('take out', installs._Change.take_out))]
        for p in self.patches: p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches): p.stop()
        return False


class Recovery(unittest.TestCase):
    setUp = test_play.Play.setUp
    package = test_play.Play.package

    def fresh(self, name):
        """A game install of its own, as test_play makes them, Bar given terror and council records."""
        game = Path(self.temp.name) / 'games' / name
        test_play.game_folder(game, self.default)
        test_manager.Manager.more_missions(self, game)
        return game

    def state(self, game):
        """Every file of the install but the editor's ledger folder, with its bytes."""
        return {str(p.relative_to(game)): p.read_bytes() for p in sorted(game.rglob('*'))
                if p.is_file() and installs.LEDGER_FOLDER not in p.relative_to(game).parts}

    def assert_settled(self, game, before):
        self.assertEqual(self.state(game), before)
        self.assertFalse(installs.change_path(game).exists())
        self.assertFalse((game / installs.LEDGER_FOLDER / 'change').exists())
        self.assertEqual([p.name for p in game.rglob('*.tmp')], [])
        self.assertFalse(installs._ACTIVE)

    def scenarios(self):
        """(name, what to do before, the change to stop, what undoes everything): a play's install, a campaign install
        in place of the map, a play's clear-up and Remove from game (both after a play's and a campaign install)."""
        folder = self.output / VARIANT
        play = lambda game: installs.install_package(game, folder)                       # noqa: E731
        campaign = lambda game: installs.install_rotation(game, folder, 'replace')      # noqa: E731
        both = lambda game: (campaign(game), play(game))                                # noqa: E731
        return [('play', lambda game: None, play, installs.reset),
                ('campaign', lambda game: None, campaign, installs.reset),
                ('clear-up', play, installs.clear_play, installs.reset),
                ('remove from game', both, installs.reset, installs.reset)]

    def test_a_change_stopped_after_any_write_is_undone_by_the_next_operation(self):
        self.package()
        for name, before_change, change, undo in self.scenarios():
            game = self.fresh(f'{name} counted')
            before_change(game)
            with Stops() as counted: change(game)
            kinds = counted.kinds
            self.assertIn('config', kinds)
            self.assertIn('ledger', kinds)
            if name in ('play', 'campaign'): self.assertIn('copy', kinds)
            if name in ('clear-up', 'remove from game'): self.assertIn('take out', kinds)
            for at, kind in enumerate(kinds, 1):
                with self.subTest(change=name, step=at, after=kind):
                    game = self.fresh(f'{name} {at}')
                    original = self.state(game)
                    before_change(game)
                    with self.assertRaises(Killed), Stops(at): change(game)
                    self.assertFalse(installs._ACTIVE)                  # the stopped server's change is over
                    undo(game)
                    self.assert_settled(game, original)

    def test_after_a_stop_the_variant_is_no_map_of_the_install_and_installs_again(self):
        """The first review's fixture stopped a campaign replacement at its final ledger write: the map rotation had
        changed and the ledger knew none of it. The next look at the install undoes it, so the variant is not listed
        as a game map and the next install of it is not refused."""
        self.package()
        game = self.fresh('final ledger write')
        original = self.state(game)
        with Stops() as counted: installs.install_rotation(game, self.output / VARIANT, 'replace')
        last = max(i for i, k in enumerate(counted.kinds, 1) if k == 'ledger')
        installs.reset(game)
        with self.assertRaises(Killed), Stops(last): installs.install_rotation(game, self.output / VARIANT, 'replace')
        self.assertTrue(installs.change_path(game).exists())
        self.assertIsNone(installs.ready(game))                             # the next look settles it
        self.assertEqual(self.state(game), original)
        self.assertFalse(any(dep.field(l, 'Name') == VARIANT for l in installs.pristine_lines(game)))
        history = installs.read_ledger(game)['history']
        self.assertTrue(history[-1]['rolledBack'])
        self.assertIn(VARIANT, history[-1]['interrupted'])
        installs.install_rotation(game, self.output / VARIANT, 'replace')
        self.assertTrue(any(dep.field(l, 'Name') == VARIANT for l in dep.lines_of(
            installs.config(game, 'DefaultMaps.ini').read_bytes())))
        installs.reset(game)
        self.assert_settled(game, original)

    def test_a_hand_edit_after_a_stop_is_kept_and_reported(self):
        self.package()
        game = self.fresh('hand edit')
        with Stops() as counted: installs.install_package(game, self.output / VARIANT)
        installs.reset(game)
        first_config = counted.kinds.index('config') + 1
        with self.assertRaises(Killed), Stops(first_config): installs.install_package(game, self.output / VARIANT)
        maps = installs.config(game, 'DefaultMaps.ini')
        before = maps.read_bytes()
        maps.write_bytes(before + b';my own line\r\n')
        done = installs.reset(game)
        self.assertIn(b';my own line', maps.read_bytes())                  # the edit is kept
        last = [h for h in installs.read_ledger(game)['history'] if h.get('interrupted')][-1]
        self.assertTrue(any('DefaultMaps.ini has changed' in note for note in last['left']))
        kept = sorted((game / installs.LEDGER_FOLDER / 'backups').glob('interrupted-*'))
        self.assertEqual(len(kept), 1)
        self.assertNotIn(VARIANT.encode(), (kept[0] / 'DefaultMaps.ini').read_bytes())     # the text from before
        self.assertIsInstance(done, dict)
        self.assertFalse(installs.change_path(game).exists())

    def test_a_change_that_fails_is_undone_at_once(self):
        """An error part-way (a file that can't be written) rolls the change back before the error is reported."""
        self.package()
        game = self.fresh('error')
        original = self.state(game)
        real = dep.write_checked
        calls = []

        def second_fails(path, lines):
            calls.append(path.name)
            if len(calls) == 2: raise OSError('the disk is full')
            return real(path, lines)
        with mock.patch.object(dep, 'write_checked', second_fails):
            with self.assertRaises(OSError): installs.install_package(game, self.output / VARIANT)
        self.assert_settled(game, original)
        self.assertTrue(installs.read_ledger(game)['history'][-1]['rolledBack'])

    def test_the_game_running_is_one_look_at_the_process_table(self):
        """Review finding 50: no tasklist is started to ask whether XCOM runs."""
        with mock.patch.object(procs, 'running', return_value=True) as running, mock.patch('subprocess.run') as run:
            self.assertTrue(REAL_GAME_RUNNING())
            self.assertTrue(REAL_DEP_GAME_RUNNING())
        self.assertEqual(running.call_args_list, [mock.call('XComEW.exe')] * 2)
        run.assert_not_called()
        self.assertFalse(procs.running('NoSuchProgram-XMW.exe'))


class Pruning(unittest.TestCase):
    """Review finding 49: the install's backups and the ledger's history keep the newest (installs.KEEP_BACKUPS,
    KEEP_HISTORY), never a folder something still needs, and none while a change waits."""
    setUp = test_play.Play.setUp

    def ledger_with(self, game, count):
        backups = game / installs.LEDGER_FOLDER / 'backups'
        names = [f'20261120-1000{k:02d}' for k in range(count - 1)] + ['interrupted-20261120-090000']
        names = [names[-1]] + names[:-1]                                    # the oldest: a roll-back's
        for name in names:
            (backups / name).mkdir(parents=True)
            (backups / name / 'DefaultMaps.ini').write_bytes(b'x')
        lab = backups / names[1] / 'CookedPCConsole' / 'URB_Lab.upk'       # an old one keeps a lab file to go back
        lab.parent.mkdir()
        lab.write_bytes(b'lab')
        return dict(backups=[str((backups / n).relative_to(game)) for n in names],
                    history=[dict(at=str(k)) for k in range(installs.KEEP_HISTORY + 50)],
                    labFiles={'URB_Lab.upk': str(lab.relative_to(game))}, files={'URB_Lab.upk': 'f' * 64}), names

    def test_the_newest_are_kept_and_what_is_needed(self):
        game = self.lwr
        ledger, names = self.ledger_with(game, installs.KEEP_BACKUPS + 10)
        installs.write_ledger(game, ledger)
        kept = installs.read_ledger(game)
        self.assertEqual(len(kept['history']), installs.KEEP_HISTORY)
        self.assertEqual(kept['history'][-1], dict(at=str(installs.KEEP_HISTORY + 49)))
        self.assertEqual([Path(b).name for b in kept['backups']], names[:2] + names[-installs.KEEP_BACKUPS:])
        there = sorted(p.name for p in (game / installs.LEDGER_FOLDER / 'backups').iterdir())
        self.assertEqual(there, sorted(names[:2] + names[-installs.KEEP_BACKUPS:]))
        self.assertEqual(ledger['backups'], kept['backups'])                # the caller's dict too

    def test_nothing_is_deleted_while_a_change_waits(self):
        game = self.lwr
        ledger, names = self.ledger_with(game, installs.KEEP_BACKUPS + 5)
        installs.change_path(game).write_text('{}', encoding='utf-8')
        installs.write_ledger(game, ledger)
        self.assertEqual(len(installs.read_ledger(game)['backups']), len(names))
        self.assertEqual(len(list((game / installs.LEDGER_FOLDER / 'backups').iterdir())), len(names))
        self.assertEqual(len(installs.read_ledger(game)['history']), installs.KEEP_HISTORY)


# the real checks, before the tests' set-up stands in for them
REAL_GAME_RUNNING, REAL_DEP_GAME_RUNNING = installs.game_running, deploy_fixture.game_running


class Removal(unittest.TestCase):
    """Review finding 26: a play's clear-up and Remove from game, with one record the editor added edited before (a
    mod manager, a hand edit). The record stays, and so do its variant's files and the ledger's note of what was left:
    a live record naming a package that is gone could be drawn by the game. Once the record is taken out by hand, the
    next removal takes the rest."""
    setUp = test_play.Play.setUp
    package = test_play.Play.package
    fresh = Recovery.fresh
    state = Recovery.state

    def edit_record(self, game, variant, k=0):
        """The k-th record of `variant` in DefaultMaps.ini given a display name of the user's own."""
        path = installs.config(game, 'DefaultMaps.ini')
        lines = dep.lines_of(path.read_bytes())
        at = [i for i, l in enumerate(lines) if dep.is_record(l) and dep.field(l, 'Name') == variant][k]
        lines[at] = dep.set_field(lines[at], 'DisplayName', 'Edited by hand')
        path.write_bytes(dep.EOL.join(lines))

    def drop_records(self, game, variant):
        """Every record of `variant` (and the editor's comment lines for it) taken out of DefaultMaps.ini by hand."""
        path = installs.config(game, 'DefaultMaps.ini')
        lines = [l for l in dep.lines_of(path.read_bytes())
                 if not (dep.is_record(l) and dep.field(l, 'Name') == variant) and not l.startswith(f'; {variant}:'.encode())]
        path.write_bytes(dep.EOL.join(lines))

    def cooked(self, game):
        return sorted(p.name for p in installs.cooked(game).iterdir())

    def test_a_plays_clear_up_keeps_the_files_of_a_record_edited_since(self):
        self.package()
        game = self.fresh('clear-up')
        own = self.cooked(game)
        installs.install_package(game, self.output / VARIANT)
        played = self.cooked(game)
        self.edit_record(game, VARIANT)
        done = installs.clear_play(game)
        self.assertEqual(done['records'], 0)
        self.assertEqual(self.cooked(game), played)                         # the variant's files stay
        self.assertTrue(any(f'record for {VARIANT}' in n for n in done['left']))
        self.assertTrue(any(n.startswith(f'{VARIANT}.upk stays') for n in done['left']))
        ledger = installs.read_ledger(game)
        self.assertEqual([b['variant'] for b in ledger['records']], [VARIANT])
        self.assertEqual(set(ledger['playFiles']), set(played) - set(own))   # still noted as the editor's
        self.assertIn(VARIANT, ledger['installed'])
        # the record taken out by hand: the next clear-up takes the files
        self.drop_records(game, VARIANT)
        done = installs.clear_play(game)
        self.assertEqual(self.cooked(game), own)
        self.assertEqual(done['left'], [])
        ledger = installs.read_ledger(game)
        self.assertFalse(ledger['records'] or ledger['playFiles'] or ledger.get('owners'))

    def test_remove_from_game_keeps_what_it_could_not_take_out(self):
        self.package()
        game = self.fresh('remove')
        original = self.state(game)
        own = self.cooked(game)
        installs.install_rotation(game, self.output / VARIANT, 'replace')
        installed = self.cooked(game)
        self.edit_record(game, VARIANT, 1)                                  # one of its campaign records
        done = installs.reset(game)
        self.assertEqual(done['rotation'], 0)
        self.assertEqual(self.cooked(game), installed)
        self.assertTrue(any(f'rotation records for {VARIANT}' in n for n in done['left']))
        ledger = installs.read_ledger(game)
        self.assertEqual([e['variant'] for e in ledger['rotation']], [VARIANT])
        self.assertEqual(set(ledger['files']), set(installed) - set(own))
        self.assertTrue(all(o for o in ledger['owners'].values()))
        # the variant is still the editor's, so it is no map of the install's own
        self.assertFalse(any(dep.field(l, 'Name') == VARIANT for l in installs.pristine_lines(game)
                             if dep.is_record(l) and dep.field(l, 'DisplayName') != 'Edited by hand'))
        status = installs.status(game)
        self.assertTrue(status['anything'])
        # taken out by hand, and the base map's records put back by hand: the next Remove takes the files
        self.drop_records(game, VARIANT)
        maps = installs.config(game, 'DefaultMaps.ini')
        maps.write_bytes(maps.read_bytes().replace(b'\r\n;Maps=(', b'\r\nMaps=('))
        done = installs.reset(game)
        self.assertEqual(self.cooked(game), own)
        ledger = installs.read_ledger(game)
        self.assertFalse(ledger['rotation'] or ledger['files'] or ledger.get('owners'))
        self.assertEqual(installs.config(game, 'DefaultMaps.ini').read_bytes(),
                         original[str(Path('XEW/XComGame/Config/DefaultMaps.ini'))])

    def test_landing_zones_left_stay_noted(self):
        self.package()
        game = self.fresh('zones')
        installs.install_package(game, self.output / VARIANT)
        lz = installs.config(game, installs.LZ)
        lz.write_bytes(lz.read_bytes().replace(f'MapName="{VARIANT}"'.encode(), f'MapName="{VARIANT}" '.encode()))
        done = installs.reset(game)
        self.assertTrue(any('landing-zone lines' in n for n in done['left']))
        self.assertEqual([b['variant'] for b in installs.read_ledger(game)['playZones']], [VARIANT])


if __name__ == '__main__':
    unittest.main()
