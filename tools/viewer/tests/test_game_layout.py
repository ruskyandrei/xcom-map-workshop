"""The game folder's layout in one place (settings.py: ew_folder, game_cooked, game_config, cooked_folders, and COOKED,
the name of the game's packages folder, which a Build's package and a map pack hold too): the helpers find a map in the
install's EW packages, then in the base game's, and no module the release ships spells CookedPCConsole in its code
but settings.py.

A spelling in code is a string with no blank in it (a path, a pattern, a folder name; an f-string's constant parts
counted one by one); words meant for the user (a message, a docstring, the readme lines a pack carries) hold blanks
and may name the folder, as the PowerShell a map pack carries (pack_scripts.py) does, which is text of another
language."""
import ast
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
VIEWER = HERE.parent
TOOLS = VIEWER.parent
sys.path.insert(0, str(VIEWER))
import export  # noqa: E402
import maplist  # noqa: E402
import settings  # noqa: E402

# Left in the Build's own files, counted so that none is added: the base map's and the streams' paths (game_files'
# lwr_file with the folder's name), the package's folder and the names its manifest lists, the prefab test's check of
# them. Each goes onto settings with the Build's next change; its count here then falls.
LEFT = {'build.py': 8, 'prefab_stage.py': 1, 'prefab_tests.py': 2}


def shipped():
    """The modules the release ships, as tools/release/make_release.py finds them."""
    sys.path.insert(0, str(TOOLS / 'release'))
    try:
        import make_release
    finally:
        sys.path.remove(str(TOOLS / 'release'))
    return make_release.modules()


def spellings(path):
    """[line] of each string in `path`'s code that names CookedPCConsole with no blank in it."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    return [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and settings.COOKED in node.value and not any(c.isspace() for c in node.value)]


class Helpers(unittest.TestCase):
    def test_the_layout_of_an_install(self):
        game = Path('G')
        self.assertEqual(settings.game_cooked(game), game / 'XEW' / 'XComGame' / 'CookedPCConsole')
        self.assertEqual(settings.game_config(game), game / 'XEW' / 'XComGame' / 'Config')
        self.assertEqual(settings.cooked_folders('G'), (game / 'XEW' / 'XComGame' / 'CookedPCConsole',
                                                        game / 'XComGame' / 'CookedPCConsole'))

    def test_a_map_is_found_in_the_ew_packages_then_the_base_games(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            ew, base = settings.cooked_folders(game)
            for folder, name in ((ew, 'Both'), (base, 'Both'), (ew, 'EwOnly'), (base, 'BaseOnly')):
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'{name}.upk').write_bytes(b'')
            self.assertEqual(maplist.package_of(game, 'Both'), ew / 'Both.upk')
            self.assertEqual(maplist.package_of(str(game), 'BaseOnly'), base / 'BaseOnly.upk')
            self.assertIsNone(maplist.package_of(game, 'Nowhere'))
            self.assertTrue(settings.is_game(game))
            # a stream beside the map's package, else in the base game's packages
            self.assertEqual(export.stream_package(ew / 'EwOnly.upk', 'Both'), (ew / 'Both.upk').resolve())
            self.assertEqual(export.stream_package(ew / 'EwOnly.upk', 'BaseOnly'), (base / 'BaseOnly.upk').resolve())
            self.assertIsNone(export.stream_package(ew / 'EwOnly.upk', 'Nowhere'))


class OneSpelling(unittest.TestCase):
    def test_only_settings_spells_the_packages_folder_in_code(self):
        found = {path.name: lines for path in shipped() if (lines := spellings(path))}
        self.assertIn('settings.py', found, 'the scan no longer sees the one spelling')
        left = {name: lines for name, lines in found.items() if name != 'settings.py' and name not in LEFT}
        self.assertEqual(left, {}, 'CookedPCConsole spelled in code outside settings.py: use its helpers or COOKED')
        self.assertEqual({name: len(found.get(name, ())) for name in LEFT}, LEFT,
                         'a count of the spellings left in the Build\'s files changed: lower LEFT, or use settings')


if __name__ == '__main__':
    unittest.main()
