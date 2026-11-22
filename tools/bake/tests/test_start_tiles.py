"""The tiles near a Build's changes written as the battle's rebuild will leave them (start_tiles.py, F-157), on the bar:
the game places the terror civilians on the stored cover points before that rebuild runs."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import native_copy  # noqa: E402
import lighting_records as lighting  # noqa: E402
import start_tiles  # noqa: E402
import world_grid  # noqa: E402
import world_links  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
import fixtures  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
STRIP = 'XComFracLevelActor_17'     # the upstairs floor strip: ten floor tiles on level 3, each with a cover point
DUMPSTER = 'XComDestructibleActor_61'
OPEN = (32, 4, 0)                   # a tile of open street: floor, no cover, nothing blocking two tiles round it
FLOOR = 0x2000


def stores(p):
    return world_grid.decode(world_grid.container_of(p)[1])['stores']


def value(store, t, fmt='<I'):
    v = store.get(t)
    return struct.unpack_from(fmt, v[0], 0) if v and v[1] else None


class Around(unittest.TestCase):
    def test_a_tile_round_a_change_reaches_one_each_way_a_level_under_and_two_over(self):
        out = start_tiles.around({(5, 5, 3)}, (10, 10, 12))
        self.assertEqual(len(out), 3 * 3 * 4)
        self.assertEqual({t[2] for t in out}, {2, 3, 4, 5})

    def test_the_grids_edges_clip_it(self):
        self.assertEqual(start_tiles.around({(0, 0, 0)}, (10, 10, 12)), {(x, y, z) for x in (0, 1) for y in (0, 1)
                                                                        for z in (0, 1, 2)})


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class StartTiles(unittest.TestCase):
    """One build of the bar: the upstairs floor strip deleted, the dumpster copied onto open street."""

    @classmethod
    def setUpClass(cls):
        cls.p = p = lighting.Package(BAR)
        grid = native_copy.level_grid(p)
        cls.at = [grid['ox'] + 96.0 * (OPEN[0] + 0.5), grid['oy'] + 96.0 * (OPEN[1] + 0.5), 0.0]
        folder = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        edit = dict(hides=[dict(name=STRIP)], copies=[dict(actor=DUMPSTER, location=cls.at, rotation=[0, 0, 0])])
        cls.manifest, cls.q = fixtures.native_build(BAR, 'URB_BarStart')(folder, {'strip and dumpster': edit})
        cls.before, cls.after = stores(p), stores(cls.q)
        strip = p.by_name[native_copy.PL + STRIP]
        cls.strip_tiles = sorted(t for t, (raw, present) in cls.before[2].items()
                                 if present and world_links.parse_element('floor', raw, 0)[0]['actor'] == strip)

    def test_a_deleted_upstairs_floor_leaves_no_floor_or_cover_point_to_start_on(self):
        # (F-157) before: the strip's tiles kept their floors and cover points in the built map until the battle's
        # rebuild, and the game had placed the terror civilians on those by then
        self.assertEqual(len(self.strip_tiles), 10)
        self.assertTrue(all(value(self.before[1], t) for t in self.strip_tiles))
        queued = native_copy.rebuild_order(self.q)
        for t in self.strip_tiles:
            with self.subTest(tile=t):
                static = value(self.after[0], t)[0]
                self.assertFalse(static & FLOOR)
                self.assertIsNone(value(self.after[2], t, '<3f'))     # no floor element
                self.assertIsNone(value(self.after[1], t))            # no cover point
                self.assertIsNone(value(self.after[3], t, '<3f'))
                self.assertTrue(static & start_tiles.SEED)            # and the battle's rebuild still works it out
                self.assertIn(t, queued)

    def test_a_copy_gives_the_tiles_beside_it_their_cover_points_from_the_start(self):
        beside = [(OPEN[0] + dx, OPEN[1] + dy, 0) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
        self.assertFalse(any(value(self.before[1], t) for t in beside))
        made = [t for t in beside if value(self.after[1], t)]
        self.assertTrue(made, 'no tile beside the copy has a cover point')
        for t in made:
            self.assertIsNotNone(value(self.after[3], t, '<3f'), t)
            self.assertTrue(value(self.after[0], t)[0] & FLOOR, t)

    def test_tiles_far_from_the_changes_keep_their_bytes(self):
        changed = set(self.strip_tiles) | {OPEN}
        far = [t for t in self.before[0] if min(max(abs(t[0] - c[0]), abs(t[1] - c[1])) for c in changed) > 4]
        self.assertGreater(len(far), 10000)
        for k in range(4):
            differ = [t for t in far if self.before[k].get(t) != self.after[k].get(t)]
            self.assertEqual(differ, [], 'store %d' % k)

    def test_the_record_says_what_was_written(self):
        rec = self.manifest['nativeCopies']['startTiles']
        self.assertGreater(rec['written'], 0)
        self.assertGreaterEqual(rec['floorsTaken'], 10)
        self.assertGreaterEqual(rec['coverTaken'], 10)
        self.assertGreaterEqual(rec['coverMade'], 1)
        self.assertGreater(rec['considered'], rec['written'])


if __name__ == '__main__':
    unittest.main()
