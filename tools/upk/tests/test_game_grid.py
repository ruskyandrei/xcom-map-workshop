"""Every map the editor lists has the game's own tile grid (scene_metadata.game_grid; private/plans/done/game-grid-plan.md,
section 7): its world data saves one, its counts are the tile data's, the game's corner is a unit under the level
volume's, and the map's saved floors sit at the tile centres counted from it.

It reads the configured install's maps list (tools/viewer/settings.py; XCOM_GAME names another game folder, as for a
plain Enemy Within install) and skips without it. It takes two minutes, most of them opening the maps, so it runs only
when every suite runs (python tools/run_tests.py, as the release checks do) or with --install, which set
XCOM_INSTALL_TESTS."""
import math
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import scene_metadata  # noqa: E402
from package import Package  # noqa: E402


def game_folder():
    if os.environ.get('XCOM_GAME'):
        return Path(os.environ['XCOM_GAME'])
    import settings
    try:
        game, _ = settings.game_install(settings.load_settings())
    except (OSError, ValueError):
        return None
    return game


GAME = game_folder()
NO_GAME = 'the game install is not configured: set XCOM_GAME, or the settings (python tools/viewer/viewer.py settings)'


def listed_maps(game):
    import library
    return [(name, path) for name, _, path in library.donors(game)]


@unittest.skipUnless(os.environ.get('XCOM_INSTALL_TESTS'), 'the checks over every map run with every suite, or with '
                     'python tools/run_tests.py upk --install')
@unittest.skipUnless(GAME and GAME.exists(), NO_GAME)
class EveryListedMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grids = {}
        for name, path in listed_maps(GAME):
            p = Package(Path(path))
            grid = scene_metadata.game_grid(p)
            if grid is not None:
                cls.grids[name] = (p, grid)

    def test_the_install_has_maps_with_tile_data(self):
        self.assertGreater(len(self.grids), 50)

    def test_every_map_saves_its_grid_and_its_counts_are_the_tile_datas(self):
        bad = {name: (grid['source'], grid['notes']) for name, (_, grid) in self.grids.items()
               if grid['source'] != 'world-data' or any('counts' in n or 'corner' in n for n in grid['notes'])}
        self.assertEqual(bad, {})

    def test_the_games_corner_is_a_unit_under_the_level_volumes(self):
        off = {name: (grid['origin'], grid['tiles']) for name, (_, grid) in self.grids.items()
               if any(abs(grid['origin'][k] - grid['tiles'][k] - 1) > scene_metadata.BOX_NOTE for k in range(3))}
        self.assertEqual(off, {})

    def test_the_saved_floors_sit_at_the_tile_centres_from_the_games_corner(self):
        # across and along exactly; up, each floor in its level, from 2 units under the level's bottom (a floor a unit
        # or two under it counts in it) to its top: a grid counted down from the top of a tall map's box fails this
        bad = {}
        for name, (p, grid) in self.grids.items():
            container = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer')
            t, size = grid['tiles'], grid['size']
            for f in scene_metadata.saved_floor_tiles(p, container, grid['dimensions']):
                (x, y, z), (tx, ty, tz) = f['location'], f['tile']
                up = z - (t[2] + size[2] * tz)
                if (abs(x - (t[0] + size[0] * tx + size[0] / 2)) > 0.01 or abs(y - (t[1] + size[1] * ty + size[1] / 2)) > 0.01
                        or not -2.0 <= up <= size[2] or not math.isfinite(up)):
                    bad.setdefault(name, []).append((f['tile'], [round(v, 3) for v in f['location']]))
        self.assertEqual({k: (len(v), v[:3]) for k, v in bad.items()}, {})


if __name__ == '__main__':
    unittest.main()
