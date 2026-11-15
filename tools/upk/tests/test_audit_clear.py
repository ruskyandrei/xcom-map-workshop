"""The clear survey's pure parts (audit_clear.py): LWR's lines read and placed, an own landing matched to a line, the
class sorting for a clear, the native's group order."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_clear as clear  # noqa: E402

BAR_LINE = 'LZArray=(MapName="URB_Bar",ESpawnLoc=ESL_Normal,StartLoc=(X=719,Y=-1681,Z=64),StartDir=ELZD_North)'
# URB_Bar's own landing as its package has it (PrefabInstance_19's actors)
BAR_LANDING = dict(frame=[720.0, -1680.0, 0.0], evac=[719.6, -1727.6, 94.9], playerStart=[728.6, -1491.1, 80.0],
                   point=[480.0, -1248.0, 0.0],
                   spawns=[[912.0, -1296.0, 48.0], [720.0, -1200.0, 48.0], [912.0, -1488.0, 48.0],
                           [720.0, -1392.0, 48.0], [528.0, -1296.0, 48.0], [528.0, -1488.0, 48.0]])


class Lines(unittest.TestCase):
    def test_a_line_is_read(self):
        line = clear.parse_lz_line(BAR_LINE + '\r\n')
        self.assertEqual(line['map'], 'URB_Bar')
        self.assertEqual(line['kind'], 'ESL_Normal')
        self.assertEqual(line['start'], [719.0, -1681.0, 64.0])
        self.assertEqual(line['direction'], 'ELZD_North')
        self.assertIsNone(line['missionType'])
        self.assertEqual(line['other'], {})

    def test_a_mission_and_unknown_fields_are_kept(self):
        line = clear.parse_lz_line('  LZArray=(MapName="X",MissionType=eMission_TerrorSite,ESpawnLoc=ESL_Inside,'
                                   'StartLoc=(X=-1.5,Y=2,Z=3),StartDir=ELZD_West,Foo=Bar)')
        self.assertEqual(line['missionType'], 'eMission_TerrorSite')
        self.assertEqual(line['start'], [-1.5, 2.0, 3.0])
        self.assertEqual(line['other'], {'Foo': 'Bar'})

    def test_comments_and_other_lines_are_not_lines(self):
        self.assertIsNone(clear.parse_lz_line(';' + BAR_LINE))
        self.assertIsNone(clear.parse_lz_line('[XComLZMutator.XComLZMutator]'))
        self.assertIsNone(clear.parse_lz_line(''))


class Places(unittest.TestCase):
    def test_north_puts_the_offsets_as_they_are(self):
        p = clear.zone_places([0.0, 0.0, 64.0], 'ELZD_North')
        self.assertEqual(p['frame'], [0.0, 0.0, 0.0])
        self.assertEqual(p['evac'], [0.0, -47.0, 96.0])
        self.assertEqual(p['spawns'][0], [192.0, 384.0, 48.0])

    def test_east_turns_a_quarter_from_x_to_y(self):
        p = clear.zone_places([0.0, 0.0, 64.0], 'ELZD_East')
        for got, want in zip(p['spawns'][1], [-480.0, 0.0, 48.0]):
            self.assertAlmostEqual(got, want, places=6)

    def test_inside_puts_the_points_288_back(self):
        p = clear.zone_places([0.0, 0.0, 64.0], 'ELZD_North', 'ESL_Inside')
        self.assertEqual(p['spawns'][1], [0.0, 192.0, 48.0])
        self.assertEqual(p['frame'], [0.0, 0.0, 0.0])


class Matching(unittest.TestCase):
    def test_bars_first_line_is_its_own_landing_within_two_units(self):
        line = clear.parse_lz_line(BAR_LINE)
        dev = clear.line_deviation(BAR_LANDING, line)
        self.assertLess(dev['spawns'], 2.0)
        self.assertLess(dev['frame'], 2.0)
        self.assertEqual(clear.match_level(dev), 'exact')

    def test_the_points_match_in_any_order(self):
        shuffled = dict(BAR_LANDING, spawns=list(reversed(BAR_LANDING['spawns'])))
        self.assertLess(clear.line_deviation(shuffled, clear.parse_lz_line(BAR_LINE))['spawns'], 2.0)

    def test_the_best_line_is_chosen_by_the_points(self):
        far = clear.parse_lz_line(BAR_LINE.replace('X=719', 'X=-1297'))
        near = clear.parse_lz_line(BAR_LINE.replace('X=719', 'X=815'))      # a tile off
        k, dev, level = clear.best_line(BAR_LANDING, [far, near])
        self.assertEqual(k, 1)
        self.assertEqual(level, 'tile')
        self.assertEqual(clear.best_line(BAR_LANDING, []), (None, None, 'none'))

    def test_levels(self):
        self.assertEqual(clear.match_level({'spawns': 3.0, 'frame': 30.0}), 'spawns')
        self.assertEqual(clear.match_level({'spawns': 40.0}), 'near')
        self.assertEqual(clear.match_level({'spawns': 500.0}), 'none')
        self.assertEqual(clear.match_level({'spawns': None}), 'none')

    def test_set_deviation_counts_both_ways(self):
        self.assertIsNone(clear.set_deviation([], [[0, 0, 0]]))
        # every predicted place is near an actual one, but an actual one is far from any predicted
        self.assertEqual(clear.set_deviation([[0, 0, 0]], [[0, 0, 0], [10, 0, 0]]), 10.0)


class Sorting(unittest.TestCase):
    def test_classes_go_to_their_groups(self):
        L = clear.LEVEL
        actors = [(L + 'XComFloorVolume_1', 'XComFloorVolume'), (L + 'Emitter_3', 'Emitter'),
                  (L + 'Emitter_78', 'Emitter'), (L + 'XComBuildingVolume_6', 'XComBuildingVolume'),
                  (L + 'SkyLight_0', 'SkyLight'), (L + 'PointLight_2', 'PointLight'),
                  (L + 'PointLight_9', 'PointLight'), (L + 'XComLevelActor_4', 'XComLevelActor'),
                  (L + 'XComFracLevelActor_1002', 'XComFracLevelActor'), (L + 'Main_Sequence.SeqAct_Delay_0', 'SeqAct_Delay'),
                  (L + 'XComLevelVolume_4_StaticMesh', 'StaticMesh'), (L + 'XComOddThing_0', 'XComOddThing')]
        got = clear.sort_classes(actors, records=[L + 'XComLevelActor_4', L + 'PointLight_2'],
                                 landing=[L + 'Emitter_78', L + 'XComBuildingVolume_6'])
        self.assertEqual(got['out'], {'Emitter': 1, 'PointLight': 1, 'XComFloorVolume': 1})
        self.assertEqual(got['landing'], {'Emitter': 1, 'XComBuildingVolume': 1})
        self.assertEqual(got['records'], {'PointLight': 1, 'XComLevelActor': 1})
        self.assertEqual(got['stays'], {'SkyLight': 1})
        self.assertEqual(got['unexported'], {'XComFracLevelActor': 1})
        self.assertEqual(got['kismet'], {'SeqAct_Delay': 1})
        self.assertEqual(got['other'], {'StaticMesh': 1})
        self.assertEqual(got['neither'], {'XComOddThing': 1})

    def test_the_lists_do_not_overlap(self):
        self.assertFalse(set(clear.CLEAR_OUT) & set(clear.CLEAR_STAYS))
        self.assertFalse(set(clear.PIECE_CLASSES) & (set(clear.CLEAR_OUT) | set(clear.CLEAR_STAYS)))


class Small(unittest.TestCase):
    def test_group_order_is_by_text(self):
        self.assertEqual(clear.sorted_group_keys(['Group2', 'Group10', 'Group0', 'Group2']), ['Group0', 'Group10', 'Group2'])
        self.assertEqual(clear.sorted_group_keys(['XComSpawnPoint', 'Group1']), ['Group1', 'XComSpawnPoint'])

    def test_levels_under_the_ground(self):
        self.assertEqual(clear.ground_levels(0.0, -128.0), 2.0)
        self.assertEqual(clear.ground_levels(0.0, 0.0), 0.0)

    def test_newest_export(self):
        with tempfile.TemporaryDirectory() as t:
            for name in ('a-v9-map', 'a-v20-map-x1', 'a-v20-map', 'a-v3-map'):
                (Path(t) / name).mkdir()
                (Path(t) / name / 'scene.json').write_text('{}', encoding='utf-8')
            self.assertEqual(clear.newest_export(t).parent.name, 'a-v20-map')
            self.assertIsNone(clear.newest_export(Path(t) / 'a-v3-map'))


if __name__ == '__main__':
    unittest.main()
