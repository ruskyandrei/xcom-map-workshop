"""hidden_game.py's own parts, without the game: the steps check, the DXVK pick, and what a run puts in the lab copy
and takes out again (on a made-up game folder)."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hidden_game  # noqa: E402
from hidden_game import Prepared, RunError  # noqa: E402


def make_game(root, marker=True):
    game = Path(root) / 'game'
    hidden_game.win32(game).mkdir(parents=True)
    (hidden_game.win32(game) / 'XComEW.exe').write_bytes(b'exe')
    hidden_game.config_folder(game).mkdir(parents=True)
    (hidden_game.config_folder(game) / 'XComContent.ini').write_bytes(b'[content]\r\n')
    (hidden_game.config_folder(game) / 'XComEngine.ini').write_bytes(b'[engine]\r\n')
    if marker: (game / hidden_game.settings.LAB_MARKER).write_text('lab', newline='\n')
    return game


def make_dxvk(root, *versions):
    for version in versions:
        folder = Path(root) / 'lab' / 'dxvk' / version / 'x32'
        folder.mkdir(parents=True)
        (folder / 'd3d9.dll').write_bytes(version.encode())
    return Path(root) / 'lab'


class Steps(unittest.TestCase):
    def test_comments_and_blank_lines_dropped(self):
        self.assertEqual(hidden_game.check_steps(['# first', '', '  wait 5 ', 'SHOT start']), ['wait 5', 'SHOT start'])

    def test_none_and_unknown_refused(self):
        with self.assertRaises(RunError): hidden_game.check_steps(['# nothing'])
        with self.assertRaisesRegex(RunError, 'press'): hidden_game.check_steps(['wait 1', 'press A'])


class Dxvk(unittest.TestCase):
    def test_newest_by_number(self):
        with tempfile.TemporaryDirectory() as root:
            lab = make_dxvk(root, 'dxvk-2.9', 'dxvk-3.1.1', 'dxvk-3.0')
            self.assertEqual(hidden_game.dxvk_dll(lab).parents[1].name, 'dxvk-3.1.1')

    def test_missing_says_where(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RunError, 'x32'): hidden_game.dxvk_dll(Path(root) / 'lab')


class PreparedCopy(unittest.TestCase):
    def test_everything_put_back(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            prepared = Prepared(game, dll, 'set A b C\nopen URB_Bar\n')
            target = hidden_game.win32(game) / 'd3d9.dll'
            play = game / 'XEW' / 'Binaries' / hidden_game.PLAY_FILE
            self.assertEqual(target.read_bytes(), dll.read_bytes())
            self.assertEqual(play.read_bytes(), b'set A b C\r\nopen URB_Bar\r\n')
            # what a run does: a config rewritten, one made, one deleted, a console step's file left behind
            config = hidden_game.config_folder(game)
            (config / 'XComContent.ini').write_bytes(b'[content]\r\nbAllowJITLoad=True\r\n')
            (config / 'XComNew.ini').write_bytes(b'new')
            (config / 'XComEngine.ini').unlink()
            (play.parent / 'XComMapWorkshop-hidden-1.txt').write_bytes(b'shot')
            self.assertEqual(sorted(prepared.restore()), ['XComContent.ini', 'XComEngine.ini', 'XComNew.ini'])
            self.assertEqual((config / 'XComContent.ini').read_bytes(), b'[content]\r\n')
            self.assertEqual((config / 'XComEngine.ini').read_bytes(), b'[engine]\r\n')
            self.assertFalse((config / 'XComNew.ini').exists())
            self.assertFalse(target.exists())
            self.assertEqual(list(play.parent.glob('*.txt')), [])

    def test_same_dll_already_there_is_left(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            target = hidden_game.win32(game) / 'd3d9.dll'
            target.write_bytes(dll.read_bytes())
            prepared = Prepared(game, dll)
            self.assertEqual(prepared.restore(), [])
            self.assertTrue(target.exists())

    def test_another_dll_stops_the_run(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            (hidden_game.win32(game) / 'd3d9.dll').write_bytes(b'someone else\'s')
            with self.assertRaisesRegex(RunError, 'another d3d9.dll'): Prepared(game, dll)

    def test_only_the_lab_copy(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root, marker=False), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            with self.assertRaisesRegex(RunError, 'not the lab copy'): Prepared(game, dll)
            self.assertFalse((hidden_game.win32(game) / 'd3d9.dll').exists())


class Arguments(unittest.TestCase):
    def test_exec_only_with_a_commands_file(self):
        self.assertEqual(hidden_game.game_arguments((1280, 720)),
                         ['-FROMLAUNCHER', '-nostartupmovies', '-nohomedir', '-forcelogflush', '-windowed', '-ResX=1280', '-ResY=720'])
        self.assertIn('-EXEC=' + hidden_game.PLAY_FILE, hidden_game.game_arguments((800, 600), hidden_game.PLAY_FILE))


if __name__ == '__main__':
    unittest.main()
