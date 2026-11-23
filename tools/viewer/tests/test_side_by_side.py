"""side_by_side.py: a game started beside another copy's (T-52). The memory change is tried on a 32-bit program of
Windows' own (its header's first bytes, written back as they were), never on the game."""
import ctypes
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import side_by_side  # noqa: E402

WOW64_CMD = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'SysWOW64' / 'cmd.exe'
NATIVE_CMD = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'cmd.exe'


class Environment(unittest.TestCase):
    def test_the_games_variables_replace_theirs_in_any_case(self):
        env = side_by_side.environment({'PATH': 'p', 'STEAMAPPID': '1', '__compat_layer': 'X', 'steamgameid': '2'})
        self.assertEqual(env, {'PATH': 'p', 'SteamAppId': '200510', 'SteamGameId': '200510',
                               '__COMPAT_LAYER': 'HIGHDPIAWARE'})

    def test_the_block_is_sorted_in_any_case_and_ends_with_two_nuls(self):
        self.assertEqual(side_by_side.environment_block({'b': '2', 'A': '1', 'SteamAppId': '3'}),
                         'A=1\0b=2\0SteamAppId=3\0\0')

    def test_the_change_is_the_labs(self):
        # the same call, bytes and replacement as tools/lab/XComSideBySide.cs
        text = (Path(__file__).resolve().parents[2] / 'lab' / 'XComSideBySide.cs').read_text(encoding='utf-8')
        self.assertIn('CallRva = 0x%X;' % side_by_side.CALL_RVA, text)
        self.assertIn('{ %s }' % ', '.join('0x%02X' % b for b in side_by_side.EXPECTED), text)
        self.assertIn('{ %s }' % ', '.join('0x%02X' % b for b in side_by_side.PATCH), text)


@unittest.skipUnless(sys.platform == 'win32' and WOW64_CMD.is_file(), 'needs Windows with its 32-bit programs')
class Start(unittest.TestCase):
    def test_a_32_bit_process_is_changed_where_its_exe_lies_and_ended_unrun(self):
        # the image's first bytes are its header's "MZ": found at the base read from the process's 32-bit PEB
        pid = side_by_side.start(WOW64_CMD, ['/c', 'exit'], rva=0, expected=b'MZ', replacement=b'MZ', resume=False)
        self.assertGreater(pid, 0)

    def test_bytes_that_differ_leave_the_process_ended_unchanged(self):
        with self.assertRaises(side_by_side.SideBySideError) as error:
            side_by_side.start(WOW64_CMD, [], rva=0, expected=b'XY', replacement=b'MZ', resume=False)
        self.assertIn('differs', str(error.exception))
        self.assertIn('4d 5a', str(error.exception))

    @unittest.skipUnless(ctypes.sizeof(ctypes.c_void_p) == 8, 'a 64-bit Python sees System32 as it is')
    def test_a_64_bit_program_is_refused(self):
        with self.assertRaises(side_by_side.SideBySideError) as error:
            side_by_side.start(NATIVE_CMD, [], rva=0, expected=b'MZ', replacement=b'MZ', resume=False)
        self.assertIn('not a 32-bit process', str(error.exception))

    def test_a_missing_exe_says_so(self):
        with self.assertRaises(side_by_side.SideBySideError) as error:
            side_by_side.start(WOW64_CMD.with_name('no-such-program.exe'), [], resume=False)
        self.assertIn("can't be started", str(error.exception))


if __name__ == '__main__':
    unittest.main()
