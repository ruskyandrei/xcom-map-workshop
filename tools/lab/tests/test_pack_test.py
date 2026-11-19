"""pack_test.py without the game: a pack put into a made-up lab copy and taken out again, the first mission card, and
a made-up Launch.log read (its lines written as beta 15's script writes them)."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pack_test  # noqa: E402
import pack_card  # noqa: E402
from pack_test import TestError  # noqa: E402

INTRO = ('Maps=( MapFamily="URB_CommercialAlley", Name="URB_CommercialAlley_EWI", DisplayName="URB_CommercialAlley_EWI '
         '(Commercial Alley Redux) |0", MissionType=eMission_Abduction, bInRotation=False, TimeOfDay=eMissionTime_Night, '
         'ShipType=eShip_None, eRegion=eMissionRegion_None, StreamingMaps[0]=( MapName="CIN_DropshipIntros" ) )')
BAR = ('Maps=( MapFamily="URB_Bar", Name="Pinkbar", DisplayName="Pinkbar (Night Bar) |0", MissionType=eMission_Abduction, '
       'bInRotation=True, TimeOfDay=eMissionTime_Night, StreamingMaps[0]=( MapName="CIN_DropshipIntros_Pinkbar" ), '
       'StreamingMaps[1]=( MapName="patch_bar" ) )')
FARM = ('Maps=( MapFamily="CSmallScout_Farm", Name="FarmTwo", DisplayName="CSmallScout_Farm (Crashed Small Scout - Farm) |6", '
        'MissionType=eMission_Crash, ShipType=eShip_UFOSmallScout, StreamingMaps[0]=( MapName="CIN_DropshipIntros_FarmTwo" ) )')


def make_game(root, marker=True):
    game = Path(root) / 'game'
    pack_test.cooked(game).mkdir(parents=True)
    pack_test.config(game).mkdir(parents=True)
    (pack_test.cooked(game) / 'URB_Bar.upk').write_bytes(b'bar')
    (pack_test.cooked(game) / 'Voice').mkdir()
    (pack_test.cooked(game) / 'Voice' / 'Voice1.upk').write_bytes(b'voice')
    (pack_test.config(game) / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n' + INTRO + '\r\n').encode())
    if marker: (game / pack_test.MARKER).write_text('copy=test\n', newline='\n')
    return game


def make_pack(root, name='TestPack', number=42, lines=(BAR, FARM), version=1):
    folder = Path(root) / 'packs' / f'v{version}' / name
    folder.mkdir(parents=True)
    (folder / pack_card.file_name(number)).write_bytes(pack_card.from_lines(f'Test Pack v{version}', lines)[0])
    (folder / 'Pinkbar.upk').write_bytes(b'map %d' % version)
    (folder / 'README.txt').write_text('a pack\n', newline='\n')
    return folder


def quiet(*_): pass


class PutAndTake(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = make_game(self.temp.name)

    def test_put_then_take_leaves_the_copy_as_it_was(self):
        before = pack_test.survey(self.game, hashed=True)
        target = pack_test.put(make_pack(self.temp.name), self.game, echo=quiet)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ['LWRMapPack_0042.upk', 'Pinkbar.upk', 'README.txt'])
        self.assertEqual(target.parent, pack_test.cooked(self.game))
        self.assertTrue(pack_test.take(self.game, echo=quiet))
        self.assertEqual(pack_test.survey(self.game, hashed=True), before)
        self.assertFalse((self.game / pack_test.NOTE).exists())

    def test_the_pack_is_found_in_a_folder_above_it_and_in_a_zip(self):
        folder = make_pack(self.temp.name)
        pack_test.put(folder.parent, self.game, echo=quiet)
        self.assertTrue((pack_test.cooked(self.game) / 'TestPack' / 'Pinkbar.upk').is_file())
        pack_test.take(self.game, echo=quiet)
        archive = Path(self.temp.name) / 'pack.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('README.txt', 'x')
            for path in folder.iterdir(): z.write(path, f'TestPack/{path.name}')
        pack_test.put(archive, self.game, echo=quiet)
        self.assertTrue((pack_test.cooked(self.game) / 'TestPack' / 'LWRMapPack_0042.upk').is_file())

    def test_an_exported_packs_caches_go_beside_the_folder(self):
        folder = make_pack(self.temp.name)
        unzipped = Path(self.temp.name) / 'unzipped' / 'CookedPCConsole'
        unzipped.mkdir(parents=True)
        folder.rename(unzipped / 'TestPack')
        (unzipped / 'Pinkbar_Lighting.tfc').write_bytes(b'cache')
        before = pack_test.survey(self.game, hashed=True)
        pack_test.put(unzipped.parent, self.game, echo=quiet)
        self.assertEqual((pack_test.cooked(self.game) / 'Pinkbar_Lighting.tfc').read_bytes(), b'cache')
        self.assertFalse((pack_test.cooked(self.game) / 'TestPack' / 'Pinkbar_Lighting.tfc').exists())
        self.assertTrue(pack_test.take(self.game, echo=quiet))
        self.assertEqual(pack_test.survey(self.game, hashed=True), before)

    def test_a_newer_version_replaces_or_goes_over(self):
        pack_test.put(make_pack(self.temp.name), self.game, echo=quiet)
        (pack_test.cooked(self.game) / 'TestPack' / 'Old.upk').write_bytes(b'old')
        newer = make_pack(self.temp.name, version=2)
        pack_test.put(newer, self.game, over=True, echo=quiet)
        there = pack_test.cooked(self.game) / 'TestPack'
        self.assertEqual((there / 'Pinkbar.upk').read_bytes(), b'map 2')
        self.assertTrue((there / 'Old.upk').is_file())
        pack_test.put(newer, self.game, echo=quiet)
        self.assertFalse((there / 'Old.upk').exists())

    def test_take_names_what_else_changed(self):
        pack_test.put(make_pack(self.temp.name), self.game, echo=quiet)
        (pack_test.config(self.game) / 'DefaultMaps.ini').write_bytes(b'changed')
        (pack_test.cooked(self.game) / 'Stray.upk').write_bytes(b'stray')
        said = []
        self.assertFalse(pack_test.take(self.game, echo=said.append))
        self.assertIn('  config: DefaultMaps.ini changed', said)
        self.assertIn('  cooked: Stray.upk is new', said)
        self.assertTrue((self.game / pack_test.NOTE).is_file())

    def test_only_a_lab_copy_is_written_to(self):
        other = make_game(Path(self.temp.name) / 'other', marker=False)
        with self.assertRaisesRegex(TestError, 'not a lab copy'): pack_test.put(make_pack(self.temp.name), other, echo=quiet)
        with self.assertRaisesRegex(TestError, 'not a lab copy'): pack_test.first_mission(other, 'Pinkbar', echo=quiet)

    def test_a_folder_already_there_is_not_touched(self):
        (pack_test.cooked(self.game) / 'TestPack').mkdir()
        with self.assertRaisesRegex(TestError, 'there already'): pack_test.put(make_pack(self.temp.name), self.game, echo=quiet)

    def test_a_source_without_a_card_is_refused(self):
        empty = Path(self.temp.name) / 'empty'
        empty.mkdir()
        with self.assertRaisesRegex(TestError, '0 folders with a card'): pack_test.put(empty, self.game, echo=quiet)


class FirstMission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = make_game(self.temp.name)
        pack_test.put(make_pack(self.temp.name), self.game, echo=quiet)

    def test_the_card_gives_the_first_missions_name_to_a_pack_map(self):
        target = pack_test.first_mission(self.game, 'pinkbar', echo=quiet)
        self.assertEqual(target, pack_test.cooked(self.game) / pack_test.FIRST_FOLDER / 'LWRMapPack_9999.upk')
        held = pack_card.read(target.read_bytes())
        self.assertEqual(held['PackName'], 'First mission test')
        self.assertEqual(len(held['Maps']), 1)
        line = held['Maps'][0]
        self.assertEqual((line['DisplayName'], line['Name'], line['MapFamily']),
                         ('URB_CommercialAlley_EWI (Commercial Alley Redux) |0', 'Pinkbar', 'URB_Bar'))
        self.assertEqual((line['MissionType'], line['bInRotation'], line['TimeOfDay']),
                         ('eMission_Abduction', False, 'eMissionTime_Night'))
        self.assertEqual([s['MapName'] for s in line['StreamingMaps']], ['CIN_DropshipIntros_Pinkbar', 'patch_bar'])

    def test_off_and_take_remove_it(self):
        pack_test.first_mission(self.game, 'Pinkbar', echo=quiet)
        pack_test.first_mission(self.game, off=True, echo=quiet)
        self.assertFalse((pack_test.cooked(self.game) / pack_test.FIRST_FOLDER).exists())
        pack_test.first_mission(self.game, 'Pinkbar', echo=quiet)
        self.assertTrue(pack_test.take(self.game, echo=quiet))
        self.assertFalse((pack_test.cooked(self.game) / pack_test.FIRST_FOLDER).exists())

    def test_a_map_no_card_names_is_refused(self):
        with self.assertRaisesRegex(TestError, 'no card'): pack_test.first_mission(self.game, 'Nowhere', echo=quiet)


W = 'MutatorLoader XComGame.XComShell'
LOG = f'''[0003.10] Log: something else
[0005.12] ScriptLog: LWRMAPPACK: {W}: card 0042 'Test Pack v1' (format 1): 2 map line(s), 1 picture line(s), 7 LZ line(s)
[0005.12] ScriptLog: LWRMAPPACK: {W}: card 0077 'From The Future': SKIPPED, card format 2 is for a newer LWR (this one reads format 1)
[0005.13] ScriptLog: LWRMAPPACK: {W}: looked for map pack cards LWRMapPack_0000 to 9999 in 612 ms: 2 found; DefaultLWRMapPacks.ini has 0 map line(s)
[0005.14] ScriptLog: LWRMAPPACK: {W}: skipped 'Gone (A Map) |0' (card 0042 'Test Pack v1'): map file 'Gone' is not installed
[0005.14] ScriptLog: LWRMAPPACK: {W}: 'Twice (A Map) |0' is in several packs: card 0050 'Other v1' (file 'TwiceB') is used, over card 0042 'Test Pack v1' (file 'TwiceA')
[0005.14] ScriptLog: LWRMAPPACK: {W}: looked for 3 map file(s), 1 missing, 0 merged before
[0005.15] ScriptLog: LWRMAPPACK: {W}: merged - 1 added, 1 replaced
[0005.15] ScriptLog: LWRMAPPACK:   'Pinkbar (Night Bar) |0': the game finds it (file 'Pinkbar', type 2, in rotation True)
[0060.00] ScriptLog: LWRMAPPACK: Packs: 2 card(s)
[0060.00] ScriptLog: LWRMAPPACK:   card 0042 'Test Pack v1' (format 1): 2 map line(s), 1 picture line(s), 7 LZ line(s)
[0060.01] ScriptLog: LWRMAPPACK:   'Pinkbar (Night Bar) |0', file 'Pinkbar', from card 0042 'Test Pack v1': used
[0060.01] ScriptLog: LWRMAPPACK:   'Gone (A Map) |0', file 'Gone', from card 0042 'Test Pack v1': NOT used: map file missing
[0060.02] ScriptLog: LWRMAPPACK: Peek Pinkbar, step 2 (texture MapPicture): 3 ms, found (Texture2D), map NOT loaded
[0090.00] ScriptLog: XComLZMutator: 7 LZ line(s) from map packs added
[0090.10] ScriptLog: LWRMAPPACK: mission start (from a save False): map file 'Pinkbar'; the game's map line 'Pinkbar (Night Bar) |0' (file 'Pinkbar', type 2); streamed levels: CIN_DropshipIntros_Pinkbar, patch_bar
[0095.00] ScriptLog: LWRMAPPACK: no picture for pack map FarmTwo (no FarmTwo_Picture.upk, no MapPicture inside the map)
[0096.00] ScriptLog: MAPFRAME Pinkbar (Night Bar) |0 -> Pinkbar image 512x256 on True
'''


class Log(unittest.TestCase):
    def setUp(self):
        self.log = pack_test.read_log(LOG)

    def test_the_scan_and_the_cards(self):
        self.assertEqual(self.log['scans'], [dict(when=W, last=9999, ms=612, found=2, ini=0)])
        self.assertEqual(self.log['cards'], [dict(number=42, name='Test Pack v1', format=1, maps=2, pictures=1, zones=7)])
        self.assertEqual(self.log['cardsSkipped'], [dict(number=77, name='From The Future', format=2)])
        self.assertEqual(self.log['looked'], [dict(looked=3, missing=1)])

    def test_skipped_and_shared_lines(self):
        self.assertEqual(self.log['skipped'], [dict(display='Gone (A Map) |0', source="card 0042 'Test Pack v1'", file='Gone')])
        self.assertEqual(self.log['several'][0]['file'], 'TwiceB')
        self.assertIn("card 0042 'Test Pack v1' (file 'TwiceA')", self.log['several'][0]['lost'])

    def test_what_the_game_finds_and_lists(self):
        self.assertEqual(self.log['finds'], [dict(display='Pinkbar (Night Bar) |0', file='Pinkbar', type=2, rotation='True')])
        self.assertEqual([(l['file'], l['state']) for l in self.log['listed']],
                         [('Pinkbar', 'used'), ('Gone', 'NOT used: map file missing')])

    def test_a_mission_start(self):
        self.assertEqual(self.log['starts'], [dict(save=False, mapFile='Pinkbar', display='Pinkbar (Night Bar) |0',
                                                   file='Pinkbar', type=2, levels=['CIN_DropshipIntros_Pinkbar', 'patch_bar'])])

    def test_pictures_and_landings(self):
        self.assertEqual(self.log['noPicture'], ['FarmTwo'])
        self.assertEqual(self.log['frames'], ['MAPFRAME Pinkbar (Night Bar) |0 -> Pinkbar image 512x256 on True'])
        self.assertEqual(self.log['zonesAdded'], [7])
        self.assertEqual(len(self.log['peeks']), 1)

    def test_verdicts(self):
        lines = [('Pinkbar (Night Bar) |0', 'Pinkbar'), ('Gone (A Map) |0', 'Gone'), ('Twice (A Map) |0', 'TwiceA'),
                 ('Quiet (A Map) |0', 'Quiet')]
        found = pack_test.verdicts(self.log, lines)
        self.assertEqual([(name, ok) for _, name, ok, _ in found],
                         [('Pinkbar', True), ('Gone', False), ('TwiceA', False), ('Quiet', True)])
        self.assertIn('a mission started on it under this line', found[0][3])
        self.assertIn('not installed', found[1][3])
        self.assertIn("card 0050 'Other v1'", found[2][3])

    def test_a_log_without_a_scan_passes_nothing(self):
        found = pack_test.verdicts(pack_test.read_log('[0001.00] Log: nothing\n'), [('A (B) |0', 'A')])
        self.assertEqual([ok for _, _, ok, _ in found], [False])

    def test_the_report_and_its_exit(self):
        out = io.StringIO()
        good = pack_test.report(self.log, [('Pinkbar (Night Bar) |0', 'Pinkbar')], echo=lambda s: out.write(s + '\n'))
        self.assertTrue(good)
        self.assertIn('scan (MutatorLoader XComGame.XComShell): 2 card(s) in 612 ms', out.getvalue())
        self.assertFalse(pack_test.report(self.log, [('Gone (A Map) |0', 'Gone')], echo=quiet))

    def test_pack_lines_from_a_card_and_a_pack_json(self):
        with tempfile.TemporaryDirectory() as temp:
            card = Path(temp) / 'LWRMapPack_0042.upk'
            card.write_bytes(pack_card.from_lines('P', [BAR, FARM])[0])
            described = Path(temp) / 'pack.json'
            described.write_text(json.dumps(dict(card=dict(lines=[BAR, FARM]))), encoding='utf-8')
            want = [('Pinkbar (Night Bar) |0', 'Pinkbar'), ('CSmallScout_Farm (Crashed Small Scout - Farm) |6', 'FarmTwo')]
            self.assertEqual(pack_test.pack_lines(card), want)
            self.assertEqual(pack_test.pack_lines(described), want)


if __name__ == '__main__':
    unittest.main()
