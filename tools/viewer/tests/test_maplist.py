from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maplist

# Records as LWR's DefaultMaps.ini writes them (cut short): a map with several records in different groups, a council
# variant, a commented-out record, the strategy map, a DLC record named after its package, and two maps that would
# share a label.
INI = '''[XComGame.XComMapManager]
Maps=( MapFamily="URB_StreetHurricane",  Name="URB_StreetHurricane",  DisplayName="URB_StreetHurricane (Beta/Functionality Complete  Street that dun soaked) |4", MissionType=eMission_Abduction, CouncilType=eFCMType_None, NewMap=True)
Maps=( MapFamily="URB_Bar",  Name="URB_Bar",  DisplayName="URB_Bar (Beta/Functionality Complete Urban Bar) |0", MissionType=eMission_Abduction, CouncilType=eFCMType_None)
Maps=( MapFamily="URB_Bar",  Name="URB_Bar_Terror",  DisplayName="URB_Bar_Terror (Terror) |0", MissionType=eMission_TerrorSite, CouncilType=eFCMType_None)
Maps=( MapFamily="URB_StreetHurricane",  Name="URB_StreetHurricane",  DisplayName="URB_StreetHurricane_Bomb (Mission Variant Bomb Defusal Street Hurricane)", MissionType=eMission_Special, CouncilType=eFCMType_Bomb)
Maps=( MapFamily="URB_StreetHurricane",  Name="URB_StreetHurricane",  DisplayName="URB_StreetHurricane (Capture and Hold) |4", MissionType=eMission_CaptureAndHold, CouncilType=eFCMType_None)
;Maps=( MapFamily="URB_StreetHurricane",  Name="URB_StreetHurricane",  DisplayName="URB_StreetHurricane_CovertOpsExtraction (Test Map)", MissionType=eMission_CovertOpsExtraction)
Maps=( MapFamily="templeship",  Name="TempleShip",  DisplayName="TempleShip  (Art Complete Temple Ship)", MissionType=eMission_Final, CouncilType=eFCMType_None)
Maps=( MapFamily="Command1",  Name="Command1",  DisplayName="Command1 (Command Center)", MissionType=eMission_Strategy, CouncilType=eFCMType_None)
Maps=( MapFamily="DLC1_1_LowFriends",  Name="DLC1_1_LowFriends",  DisplayName="DLC1_1_LowFriends", MissionType=eMission_Special, CouncilType=eFCMType_None)
Maps=( MapFamily="CBattleship",  Name="CBattleship_01",  DisplayName="CBattleship_01 (Crashed BattleShip)", MissionType=eMission_Crash, CouncilType=eFCMType_None)
Maps=( MapFamily="CBattleship",  Name="CBattleship_02",  DisplayName="CBattleship_02 (Crashed BattleShip)", MissionType=eMission_LandedUFO, CouncilType=eFCMType_None)
Maps=( MapFamily="Odd",  Name="Odd_NoNotes",  DisplayName="Odd_NoNotes", MissionType=eMission_ExaltRaid, CouncilType=eFCMType_None)
;Maps=( MapFamily="Act1_IntroLevel",  Name="Act1_IntroLevel",  DisplayName="Helo Crash (Abduction) |4", MissionType=eMission_Abduction, CouncilType=eFCMType_None, StreamingMaps[0]=( MapName="CIN_DropshipIntros" ) )
;Maps=( MapFamily="Act1_IntroLevel",  Name="Act1_IntroLevel",  DisplayName="IntroLevel Tutorial 1 (Basic Training)", MissionType=eMission_Special, CouncilType=eFCMType_None, StreamingMaps[1]=( MapName="Act1_IntroLevel_Script" ) )
;Maps=( MapFamily="URB_Museum",  Name="URB_Museum",  DisplayName="URB_Museum (Beta/Functionality Complete Urban Museum) |0", MissionType=eMission_Abduction, CouncilType=eFCMType_None)
'''


class MapListTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.game = Path(temp.name) / 'game'
        config = self.game / 'XEW' / 'XComGame' / 'Config'
        config.mkdir(parents=True)
        (config / 'DefaultMaps.ini').write_text(INI, encoding='latin-1', newline='\n')
        for folder, name in (('XEW', 'URB_Bar'), ('XEW', 'URB_StreetHurricane'), ('', 'URB_Bar')):
            cooked = self.game / folder / 'XComGame' / 'CookedPCConsole'
            cooked.mkdir(parents=True, exist_ok=True)
            (cooked / f'{name}.upk').write_bytes(folder.encode())
        (self.game / 'XComGame' / 'CookedPCConsole' / 'TempleShip.upk').write_bytes(b'base')
        self.maps = maplist.lwr_maps(self.game)

    def test_each_map_once_with_its_missions_and_groups(self):
        self.assertNotIn('Command1', self.maps)
        street = self.maps['URB_StreetHurricane']
        self.assertEqual([m['type'] for m in street['missions']], ['Abduction', 'Special', 'CaptureAndHold'])
        self.assertEqual([m['label'] for m in street['missions']], ['Abduction', 'Council bomb', 'Data recovery'])
        self.assertEqual(street['groups'], ['abduction', 'council', 'exalt'])
        self.assertEqual(self.maps['URB_Bar_Terror']['groups'], ['terror'])
        self.assertEqual(self.maps['TempleShip']['groups'], ['story'])
        self.assertEqual(self.maps['DLC1_1_LowFriends']['groups'], ['story'])
        self.assertEqual(self.maps['CBattleship_02']['groups'], ['ufo'])
        self.assertEqual(self.maps['Odd_NoNotes']['groups'], ['exalt'])

    def test_labels(self):
        labels = {name: entry['label'] for name, entry in self.maps.items()}
        self.assertEqual(labels['URB_Bar'], 'Urban Bar')                        # development notes dropped
        self.assertEqual(labels['TempleShip'], 'Temple Ship')
        self.assertEqual(labels['URB_StreetHurricane'], 'Street Hurricane')     # LABELS
        self.assertEqual(labels['DLC1_1_LowFriends'], 'Low Friends (Slingshot 1)')
        self.assertEqual(labels['URB_Bar_Terror'], 'URB Bar Terror')            # "Terror" only names the mission
        self.assertEqual(labels['Odd_NoNotes'], 'Odd NoNotes')
        self.assertEqual((labels['CBattleship_01'], labels['CBattleship_02']),
                         ('Crashed BattleShip (01)', 'Crashed BattleShip (02)'))

    def test_packages_prefer_the_ew_folder(self):
        self.assertEqual(self.maps['URB_Bar']['package'].read_bytes(), b'XEW')
        self.assertEqual(self.maps['TempleShip']['package'].read_bytes(), b'base')
        self.assertIsNone(self.maps['CBattleship_01']['package'])

    def test_the_intro_map_is_listed_from_its_commented_out_abduction_record(self):
        intro = self.maps['Act1_IntroLevel']
        self.assertEqual(intro['label'], 'Basic Training (tutorial map)')
        self.assertEqual(intro['groups'], ['abduction'])
        # the tutorial's record (Basic Training, streaming the tutorial's script) is not taken
        self.assertEqual([(m['type'], m['display']) for m in intro['missions']], [('Abduction', 'Helo Crash (Abduction) |4')])
        # other maps whose records are all commented out stay out (Long War's EU maps)
        self.assertNotIn('URB_Museum', self.maps)

    def test_records_keep_each_line_as_written_and_a_live_record_wins(self):
        records = maplist.records(INI)
        self.assertEqual(sum('Act1_IntroLevel' in r for r in records), 1)
        intro, = [r for r in records if 'Act1_IntroLevel' in r]
        self.assertTrue(intro.startswith('Maps=( MapFamily="Act1_IntroLevel"'))
        # a record as the file writes it, its trailing blank kept
        self.assertEqual(maplist.records(' ;; Maps=( Name="Act1_IntroLevel", MissionType=eMission_Abduction ) \n'),
                         ['Maps=( Name="Act1_IntroLevel", MissionType=eMission_Abduction ) '])
        self.assertEqual(len(records), len(maplist.live_records(INI)) + 1)
        # where the install has a live record for the map (plain EW may), the commented-out ones are not taken
        live = INI + 'Maps=( MapFamily="Act1_IntroLevel",  Name="Act1_IntroLevel",  DisplayName="IntroLevel", MissionType=eMission_Special)\n'
        self.assertEqual([maplist.field(r, 'DisplayName') for r in maplist.records(live) if 'Act1_IntroLevel' in r], ['IntroLevel'])

    def test_distinct_keeps_a_label_that_names_its_tail(self):
        maps = {'URB_Boulevard': dict(name='URB_Boulevard', label='Urban Boulevard'),
                'URB_Boulevard_Euro': dict(name='URB_Boulevard_Euro', label='Urban Boulevard')}
        maplist.distinct(maps)
        self.assertEqual([e['label'] for e in maps.values()], ['Urban Boulevard', 'Urban Boulevard (Euro)'])


if __name__ == '__main__':
    unittest.main()
