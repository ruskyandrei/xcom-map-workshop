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
            (play.parent / 'xmwh1.txt').write_bytes(b'shot')
            self.assertEqual(sorted(prepared.restore()), ['XComContent.ini', 'XComEngine.ini', 'XComNew.ini'])
            self.assertEqual((config / 'XComContent.ini').read_bytes(), b'[content]\r\n')
            self.assertEqual((config / 'XComEngine.ini').read_bytes(), b'[engine]\r\n')
            self.assertFalse((config / 'XComNew.ini').exists())
            self.assertFalse(target.exists())
            self.assertEqual(list(play.parent.glob('*.txt')), [])

    def test_saving_starts_by_the_key_and_puts_saves_back(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            saves = game / 'XEW' / 'XComGame' / 'SaveData'
            saves.mkdir()
            (saves / 'profile.bin').write_bytes(b'profile')
            (saves / 'save8').write_bytes(b'the user\'s quicksave')
            prepared = Prepared(game, dll, 'open URB_Bar\n', saving=True)
            self.assertEqual(prepared.exec_file, hidden_game.START_FILE)
            start = game / 'XEW' / 'Binaries' / hidden_game.START_FILE
            self.assertEqual(start.read_bytes(), b'setbind F5 exec ' + hidden_game.PLAY_FILE.encode() + b'\r\n')
            # the logged-in game writes its profile, a quicksave takes the user's slot, another save is new
            (saves / 'profile.bin').write_bytes(b'the run\'s profile')
            (saves / 'save8').write_bytes(b'the run\'s quicksave')
            (saves / 'save9').write_bytes(b'new')
            self.assertEqual(sorted(prepared.restore()), ['profile.bin', 'save8', 'save9'])
            self.assertEqual((saves / 'profile.bin').read_bytes(), b'profile')
            self.assertEqual((saves / 'save8').read_bytes(), b'the user\'s quicksave')
            self.assertFalse((saves / 'save9').exists())
            self.assertFalse(start.exists())

    def test_without_saving_the_saves_are_not_touched(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            saves = game / 'XEW' / 'XComGame' / 'SaveData'
            saves.mkdir()
            prepared = Prepared(game, dll, 'open URB_Bar\n')
            self.assertEqual(prepared.exec_file, hidden_game.PLAY_FILE)
            (saves / 'save9').write_bytes(b'someone else\'s')
            self.assertEqual(prepared.restore(), [])
            self.assertTrue((saves / 'save9').exists())

    def test_saving_needs_a_battle(self):
        with tempfile.TemporaryDirectory() as root:
            game, dll = make_game(root), hidden_game.dxvk_dll(make_dxvk(root, 'dxvk-3.1.1'))
            with self.assertRaisesRegex(RunError, 'needs a battle'): Prepared(game, dll, None, saving=True)

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


class Pointing(unittest.TestCase):
    """The camera that puts the picture's corner over a tile, against what the game answered (17 November 2026, a
    soldier at 1583,911, field of view 20: yaw 0 gave the tile 96,288 from him, yaw 90 the tile -288,96)."""

    def corner(self, fov, yaw):
        import math
        reach = hidden_game.AIM_REACH * math.tan(math.radians(fov / 2))
        angle = math.radians(yaw + hidden_game.AIM_ANGLE)
        return reach * math.cos(angle), reach * math.sin(angle)

    def test_measured_yaws_fall_on_their_tiles(self):
        for yaw, tile in ((0, (96, 288)), (90, (-288, 96)), (180, (-96, -288)), (270, (288, -96))):
            x, y = self.corner(20, yaw)
            self.assertTrue(hidden_game.on_tile((x, y), tile), (yaw, x, y))

    def test_camera_for_a_target_points_back_at_it(self):
        unit = (1583.0, 911.0)
        for target in ((1391.0, 1103.0), (1583.0, 719.0), (2543.0, 911.0), (1487.0, 911.0)):
            fov, yaw = hidden_game.aim_camera(unit, target)
            x, y = self.corner(fov, yaw)
            self.assertAlmostEqual(unit[0] + x, target[0], places=3)
            self.assertAlmostEqual(unit[1] + y, target[1], places=3)

    def test_own_tile_refused(self):
        with self.assertRaisesRegex(RunError, 'stands on'): hidden_game.aim_camera((0, 0), (10, 10))


class Answers(unittest.TestCase):
    LOG = ("[0134.67] Log: 2) XGUnit URB_Bar.TheWorld:PersistentLevel.XGUnit_2.Location = (X=1582.961426,Y=911.033325,Z=67.178223)\n"
           "[0134.67] ScriptWarning: Accessed None 'm_kInventory'\n"
           "\tFunction LWRebalance.LWRGfx_UnitFlag:SetOWDamage:00E2\n"
           "[0134.68] Log: Execing ..\\..\\Binaries\\xmwh3.txt\n"
           "[0134.68] ExecWarning: Unrecognized property m_iMovesLeft\n")

    def test_log_gain_keeps_answers_only(self):
        lines = hidden_game.log_gain(self.LOG)
        self.assertEqual(len(lines), 2)
        self.assertIn('XGUnit_2.Location', lines[0])
        self.assertIn('Unrecognized property', lines[1])

    def test_vectors_by_object(self):
        self.assertEqual(hidden_game.vectors(hidden_game.log_gain(self.LOG)), {'XGUnit_2': (1582.961426, 911.033325, 67.178223)})


class Sounds(unittest.TestCase):
    def test_waves_of_the_games_list(self):
        lines = ['[0178.75] Log:    0.    Yes 178.75   0.18  SoundAmbience-NorthAmerica.FlyingPaperLoop   XComTacticalSoundManager_0',
                 '[0178.75] Log:    2.    Yes 178.75   0.60  SoundBarMuzak.BarMuzakStereo   AmbientSoundSimple_2',
                 '[0178.75] Log: Total: 4']
        self.assertEqual(hidden_game.waves(lines), [(0.18, 'SoundAmbience-NorthAmerica.FlyingPaperLoop', 'XComTacticalSoundManager_0'),
                                                    (0.6, 'SoundBarMuzak.BarMuzakStereo', 'AmbientSoundSimple_2')])


class Input(unittest.TestCase):
    """T-45: with no mouse in Windows the game crashes as it starts (DirectInput's system mouse), so no run starts."""

    def test_no_mouse_stops_the_run(self):
        with self.assertRaisesRegex(RunError, 'no mouse'): hidden_game.check_input((0, 1))

    def test_no_keyboard_is_a_note(self):
        self.assertIsNone(hidden_game.check_input((1, 1)))
        self.assertIn('no keyboard', hidden_game.check_input((2, 0)))
        self.assertIsNone(hidden_game.check_input(None))

    def test_the_devices_are_counted(self):
        devices = hidden_game.input_devices()
        if devices is not None: self.assertTrue(all(isinstance(n, int) and n >= 0 for n in devices))


class Arguments(unittest.TestCase):
    def test_exec_only_with_a_commands_file(self):
        self.assertEqual(hidden_game.game_arguments((1280, 720)),
                         ['-FROMLAUNCHER', '-nostartupmovies', '-nohomedir', '-forcelogflush', '-windowed', '-ResX=1280', '-ResY=720'])
        self.assertIn('-EXEC=' + hidden_game.PLAY_FILE, hidden_game.game_arguments((800, 600), hidden_game.PLAY_FILE))


if __name__ == '__main__':
    unittest.main()
