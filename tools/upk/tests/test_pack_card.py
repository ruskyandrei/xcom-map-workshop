"""The map pack card writer and reader (pack_card.py): ini lines parsed, cards written and read back, the engine's
name split, a fixed card's bytes, and, when an LWR install is configured, every map and landing line of that install
through a card and back. With the LWR team's reference writer at hand (a private copy, absent from the repository) a
card of ours is read by its reader and one of its cards by ours."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import pack_card  # noqa: E402
from pack_card import CardError, card, from_lines, map_line, parse_record, read, split_name, zone_line  # noqa: E402

MARKET = ('Maps=( MapFamily="EXP_Market", Name="EXP_Market", DisplayName="EXP_Market (Example Night Market) |0", '
          'MissionType=eMission_Abduction, bInRotation=True, TimeOfDay=eMissionTime_Night, ShipType=eShip_None, '
          'eRegion=eMissionRegion_None, CouncilType=eFCMType_None, NewMap=True, InitialChance=20, InitialGain=1.04, '
          'DynamicAliens[0]=eChar_None, DynamicAliens[1]=eChar_None, StreamingMaps[0]=( MapName="CIN_DropshipIntros", '
          'Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ), StreamingMaps[5]=( MapName="patch_hide", '
          'Loc=( X=-0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) )')
FARM = ('Maps=(MapFamily="CSmallScout_Farm_2001",Name="EXP_Farm",DisplayName="EXP_Farm (Crashed Small Scout - A Farm) |6",'
        'MissionType=eMission_Crash,bInRotation=false,TimeOfDay=eMissionTime_Day,ShipType=eShip_UFOSmallScout,'
        'ERegion=eMissionRegion_None,DynamicAliens[1]=eChar_Sectoid,StreamingMaps[1]=(MapName="patch_EXP_Farm"))')
ZONE = 'LZArray=(MapName="EXP_Market",ESpawnLoc=ESL_Normal,StartLoc=(X=719,Y=-1681,Z=64),StartDir=ELZD_North)'
ZONE_FULL = ('LZArray=(MapName="EXP_Farm",MissionType=eMission_Crash,CouncilType=eFCMType_None,ESpawnLoc=ESL_Alt,'
             'StartLoc=(X=-1536,Y=960.5,Z=64),StartDir=ELZD_East,AltSpawnLoc=(X=1,Y=2,Z=3),AltSpawnDir=ELZD_West)')
PICTURE = 'Pictures=(Map="EXP_Farm", Picture="UILibrary_MapImages.CAbductor_Cliffside")'


class Lines(unittest.TestCase):
    def test_a_map_line_is_parsed(self):
        record = parse_record(MARKET)
        self.assertEqual(record.kind, 'Maps')
        self.assertEqual(record.fields['DisplayName'], 'EXP_Market (Example Night Market) |0')
        self.assertEqual(record.fields['DynamicAliens'], {0: 'eChar_None', 1: 'eChar_None'})
        self.assertEqual(sorted(record.fields['StreamingMaps']), [0, 5])
        self.assertEqual(record.fields['StreamingMaps'][5]['MapName'], 'patch_hide')

    def test_keys_are_read_without_regard_to_capitals(self):
        record = parse_record(FARM)
        self.assertEqual(record.fields['eRegion'], 'eMissionRegion_None')
        self.assertNotIn('ERegion', record.fields)
        self.assertEqual(parse_record('+lzarray=(mapname="A",startloc=(x=1,y=2,z=3),startdir=ELZD_North)').fields,
                         {'MapName': 'A', 'StartLoc': {'X': '1', 'Y': '2', 'Z': '3'}, 'StartDir': 'ELZD_North'})

    def test_other_lines_are_no_records(self):
        for text in ('', '; Maps=( Name="X" )', '[XComGame.XComMapManager]', 'MapsVersion=3', b';Maps=(Name="X")'):
            self.assertIsNone(parse_record(text), text)

    def test_a_broken_record_is_refused(self):
        for text in ('Maps=( Name="X', 'Maps=( Name= )', 'Maps=( Name="X", ', 'Maps=( ="X" )'):
            with self.subTest(text), self.assertRaises(CardError): parse_record(text)

    def test_a_map_line_has_every_field(self):
        line = map_line(parse_record(FARM).fields)
        self.assertEqual(line['ShipType'], 4)
        self.assertIs(line['bInRotation'], False)
        self.assertIs(line['NewMap'], True)
        self.assertEqual((line['InitialChance'], round(line['InitialGain'], 4)), (20.0, 1.04))
        self.assertEqual((line['TimeOfDay'], line['CouncilType']), ('eMissionTime_Day', 'eFCMType_None'))
        self.assertEqual(line['DynamicAliens'], ['eChar_None', 'eChar_Sectoid'])
        # slot 1 used, slot 0 not: an empty element holds slot 0's place
        self.assertEqual([s['MapName'] for s in line['StreamingMaps']], ['', 'patch_EXP_Farm'])
        self.assertEqual(map_line(line), line)

    def test_a_gap_in_the_streamed_maps_is_filled(self):
        streams = map_line(parse_record(MARKET).fields)['StreamingMaps']
        self.assertEqual([s['MapName'] for s in streams], ['CIN_DropshipIntros', '', '', '', '', 'patch_hide'])
        self.assertEqual(streams[2], dict(MapName='', Loc=(0.0, 0.0, 0.0), Rot=(0, 0, 0)))

    def test_ship_types(self):
        self.assertEqual([pack_card.ship_number(v) for v in ('eShip_None', 'eship_ufoethereal', '12', 7)], [0, 9, 12, 7])
        with self.assertRaises(CardError): pack_card.ship_number('eShip_Nothing')

    def test_a_value_a_card_cant_hold_is_refused(self):
        """Review finding 44: each is a CardError (a ValueError, which the pack export reports for its project), not an
        error of another kind, a huge card or a line read a character at a time."""
        for text in ('Maps=( Name="X", InitialChance=abc )', 'Maps=( Name="X", InitialGain=1e300 )',
                     'Maps=( Name="X", ShipType=99999999999 )',
                     'Maps=( Name="X", StreamingMaps[0]=( MapName="A", Rot=( Pitch=inf ) ) )',
                     'Maps=( Name="X", StreamingMaps[100000]=( MapName="A" ) )', 'Maps=( Name="X", StreamingMaps="XY" )',
                     'Maps=( Name="X", StreamingMaps=( MapName="A" ) )', 'Maps=( Name="X", DynamicAliens[2]=eChar_Sectoid )',
                     'LZArray=( MapName="X", StartLoc=( X=nope ) )'):
            with self.subTest(text), self.assertRaises(CardError): from_lines('P', [text])
        # the highest slot taken, and one alien with no slot is slot 0, as the ini reads it
        line = map_line(parse_record(f'Maps=( Name="X", StreamingMaps[{pack_card.MAX_STREAM_SLOT}]=( MapName="A" ) )').fields)
        self.assertEqual(len(line['StreamingMaps']), pack_card.MAX_STREAM_SLOT + 1)
        self.assertEqual(map_line(parse_record('Maps=( Name="X", DynamicAliens=eChar_Sectoid )').fields)['DynamicAliens'],
                         ['eChar_Sectoid', 'eChar_None'])

    def test_a_zone_line_has_every_field(self):
        self.assertEqual(zone_line(parse_record(ZONE).fields),
                         dict(MapName='EXP_Market', MissionType='eMission_None', CouncilType='eFCMType_None',
                              StartLoc=(719.0, -1681.0, 64.0), StartDir='ELZD_North', ESpawnLoc='ESL_Normal',
                              AltSpawnLoc=(0.0, 0.0, 0.0), AltSpawnDir='None'))

    def test_an_unknown_key_is_named(self):
        data, warnings = from_lines('P', ['Maps=( Name="X", Colour=Red )'])
        self.assertEqual(warnings, ['Maps line X: a card has no field Colour'])
        self.assertEqual(read(data)['Maps'][0]['Name'], 'X')


class Names(unittest.TestCase):
    def test_the_engines_split(self):
        self.assertEqual(split_name('CSmallScout_Farm_2001'), ('CSmallScout_Farm', 2002))
        self.assertEqual(split_name('Thing_0'), ('Thing', 1))
        for whole in ('Thing_01', 'Thing', 'Thing_', 'eMission_Abduction', 'Thing_12345678901', '_5'):
            self.assertEqual(split_name(whole), (whole, 0), whole)

    def test_a_numbered_family_is_stored_split(self):
        data = card('P', [parse_record(FARM).fields])
        self.assertIn(b'CSmallScout_Farm\0', data)
        self.assertNotIn(b'CSmallScout_Farm_2001', data)
        self.assertEqual(read(data)['Maps'][0]['MapFamily'], 'CSmallScout_Farm_2001')


class Cards(unittest.TestCase):
    def test_round_trip(self):
        lines = [MARKET, '; a comment', ZONE, FARM, PICTURE, ZONE_FULL]
        data, warnings = from_lines('Example Pack v3', lines)
        self.assertEqual(warnings, [])
        held = read(data)
        self.assertEqual((held['PackName'], held['Format'], held['version'], held['licensee']), ('Example Pack v3', 1, 845, 0))
        self.assertEqual(held['Maps'], [map_line(parse_record(MARKET).fields), map_line(parse_record(FARM).fields)])
        self.assertEqual(held['Pictures'], [dict(Map='EXP_Farm', Picture='UILibrary_MapImages.CAbductor_Cliffside')])
        self.assertEqual(held['LZArray'], [zone_line(parse_record(ZONE).fields), zone_line(parse_record(ZONE_FULL).fields)])
        self.assertEqual(held['LZArray'][1]['StartLoc'], (-1536.0, 960.5, 64.0))

    def test_the_same_lines_give_the_same_bytes(self):
        self.assertEqual(from_lines('P', [MARKET, ZONE])[0], from_lines('P', [MARKET, ZONE])[0])
        self.assertNotEqual(from_lines('P', [MARKET, ZONE])[0], from_lines('Q', [MARKET, ZONE])[0])

    def test_an_empty_card(self):
        data = card('Nothing v1')
        self.assertEqual(read(data), dict(PackName='Nothing v1', Format=1, version=845, licensee=0, Maps=[], Pictures=[], LZArray=[]))

    def test_the_package_layout(self):
        data = card('P', [parse_record(MARKET).fields])
        tag, version, licensee, header = struct.unpack_from('<IHHi', data, 0)
        self.assertEqual((tag, version, licensee), (0x9E2A83C1, 845, 0))
        at = 12 + 4 + 5                                         # the folder name "None"
        flags, names, name_at, exports, export_at, imports, import_at, depends_at = struct.unpack_from('<Iiiiiiii', data, at)
        self.assertEqual((flags, exports, imports), (1, 1, 2))
        self.assertEqual(depends_at + 4, header)
        guid = data[at + 32 + 16:at + 32 + 32]
        self.assertNotEqual(guid, bytes(16))
        # the first seven names, as the game's own script packages order them
        r = pack_card._Reader(data)
        r.at = name_at
        first = []
        for _ in range(7):
            first.append(r.string()); r.unpack('<Q')
        self.assertEqual(tuple(first), pack_card.FIRST_NAMES)
        # the export: class the second import, no outer, flags, its data right after the header
        cls, _, outer = struct.unpack_from('<iii', data, export_at)
        object_flags, size, offset = struct.unpack_from('<Qii', data, export_at + 24)
        self.assertEqual((cls, outer, object_flags, offset, offset + size), (-2, 0, 0x000F000400000000, header, len(data)))
        self.assertEqual(struct.unpack_from('<i', data, offset)[0], 0)

    def test_a_fixed_card_byte_for_byte(self):
        data = card('Fixed v1', [parse_record(FARM).fields], [parse_record(PICTURE).fields], [parse_record(ZONE).fields])
        self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), FIXED)

    def test_text_outside_ascii(self):
        held = read(card('Café Łódź v1'))
        self.assertEqual(held['PackName'], 'Café Łódź v1')

    def test_what_is_not_a_card_is_refused(self):
        good = card('P', [parse_record(MARKET).fields])
        for data, why in ((b'', 'empty'), (b'\0' * 200, 'no tag'), (good[:-9], 'cut short'), (good[:200], 'a header only')):
            with self.subTest(why), self.assertRaises(CardError): read(data)

    def test_card_file_names(self):
        self.assertEqual(pack_card.file_name(42), 'LWRMapPack_0042.upk')
        self.assertEqual([pack_card.number_of(n) for n in ('LWRMapPack_0042.upk', 'lwrmappack_9999.UPK', 'LWRMapPack_42.upk', 'X.upk')],
                         [42, 9999, None, None])
        with self.assertRaises(CardError): pack_card.file_name(10000)

    def test_enum_warnings(self):
        held = read(from_lines('P', [MARKET, FARM, ZONE_FULL])[0])
        enums = dict(EMissionType=['eMission_None', 'eMission_Abduction'], ECharacter=['eChar_None'])
        self.assertEqual(pack_card.enum_warnings(held, enums),
                         ['EXP_Farm (Crashed Small Scout - A Farm) |6: the game has no EMissionType eMission_Crash',
                          'EXP_Farm (Crashed Small Scout - A Farm) |6: the game has no ECharacter eChar_Sectoid',
                          'landing zone of EXP_Farm: the game has no EMissionType eMission_Crash'])


FIXED = (3044, 'fdef5386903a3a37d579da448f83d4236d5476904aee0e05484abc19eb0f9f61')


def install_config():
    try:
        from settings import game_install, game_kind, load_settings
        game, _ = game_install(load_settings())
    except (OSError, ValueError, ImportError):
        return None
    if game is None or game_kind(game) != 'lwr': return None
    folder = Path(game) / 'XEW' / 'XComGame' / 'Config'
    return folder if (folder / 'DefaultMaps.ini').is_file() else None


CONFIG = install_config()


@unittest.skipUnless(CONFIG, 'no LWR install configured')
class Install(unittest.TestCase):
    def _records(self, name, kind):
        path = CONFIG / name
        if not path.is_file(): self.skipTest(f'the install has no {name}')
        records = [parse_record(line) for line in path.read_bytes().decode('latin-1').splitlines()]
        return [r.fields for r in records if r is not None and r.kind == kind]

    def test_every_map_line_through_a_card(self):
        fields = self._records('DefaultMaps.ini', 'Maps')
        self.assertGreater(len(fields), 100)
        for f in fields: self.assertEqual([k for k in f if k not in pack_card.KEYS['Maps']], [], f.get('Name'))
        held = read(card('Install', fields))
        self.assertEqual(held['Maps'], [map_line(f) for f in fields])
        # the ini's own values, not defaults standing in for them: names, display names and streams as the file has them
        self.assertEqual([m['DisplayName'] for m in held['Maps']], [f['DisplayName'] for f in fields])
        for m, f in zip(held['Maps'], fields):
            streams = f.get('StreamingMaps') or {}
            self.assertEqual({i: s['MapName'] for i, s in enumerate(m['StreamingMaps']) if s['MapName']},
                             {i: s['MapName'] for i, s in streams.items() if s.get('MapName')}, f['Name'])

    def test_every_landing_line_through_a_card(self):
        fields = self._records('DefaultLZMutator.ini', 'LZArray')
        self.assertGreater(len(fields), 100)
        held = read(card('Install', zones=fields))
        self.assertEqual(held['LZArray'], [zone_line(f) for f in fields])

    def test_the_installs_enum_values_are_the_scripts(self):
        import script_enums
        package = CONFIG.parent / 'CookedPCConsole' / 'XComGame.upk'
        enums = {name: record['entries'] for name, record in script_enums.read(package).items() if name}
        held = dict(Maps=self._records('DefaultMaps.ini', 'Maps'), LZArray=self._records('DefaultLZMutator.ini', 'LZArray'))
        self.assertEqual(pack_card.enum_warnings(held, enums), [])


REFERENCE = HERE.parents[2] / 'private' / 'research' / 'lwr-make_card-reference-2026-11-18.py'


@unittest.skipUnless(REFERENCE.is_file(), 'no private copy of the reference writer: %s is not in this checkout (a '
                                          'worktree has no private/)' % REFERENCE.relative_to(HERE.parents[2]).as_posix())
class Reference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('lwr_make_card', REFERENCE)
        cls.ref = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.ref)

    def test_its_card_read_by_ours(self):
        made = self.ref.card_from_ini(self.ref.EXAMPLE_BLOCK, 'Example Pack 1.0')
        held = read(self.ref.Card().build(made))
        ours = read(from_lines('Example Pack 1.0', self.ref.EXAMPLE_BLOCK.splitlines())[0])
        self.assertEqual(held, ours)
        self.assertEqual(len(held['Maps']), 2)
        self.assertEqual(len(held['LZArray']), 5)

    def test_our_card_read_by_its_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'LWRMapPack_0001.upk'
            path.write_bytes(from_lines('Example Pack 1.0', self.ref.EXAMPLE_BLOCK.splitlines() + [FARM])[0])
            out = io.StringIO()
            with contextlib.redirect_stdout(out): self.ref.read_card(str(path))
        text = out.getvalue()
        self.assertIn('properties end OK', text)
        self.assertNotIn('MISMATCH', text)
        self.assertIn("DisplayName = 'EXP_Market (Example Pack Night Market) |0'", text)
        self.assertIn('ShipType = 4', text)

    def test_the_same_tags_for_the_same_line(self):
        # a line with every field given and no gap: the two writers' property bytes differ only in the name table's
        # order, so the objects are the same size
        line = ('Maps=( MapFamily="A", Name="A", DisplayName="A (B) |0", MissionType=eMission_Abduction, bInRotation=True, '
                'TimeOfDay=eMissionTime_Night, ShipType=eShip_None, eRegion=eMissionRegion_None, CouncilType=eFCMType_None, '
                'NewMap=True, InitialChance=20, InitialGain=1.04, DynamicAliens[0]=eChar_None, DynamicAliens[1]=eChar_None, '
                'StreamingMaps[0]=( MapName="CIN_DropshipIntros", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) )')
        theirs = self.ref.Card().build(self.ref.card_from_ini(line, 'P'))
        ours = from_lines('P', [line])[0]

        def size(data):
            at = 12 + 4 + 5 + 4 + 8 + 4
            return struct.unpack_from('<i', data, struct.unpack_from('<i', data, at)[0] + 32)[0]
        # ours also writes the empty Pictures and LZArray arrays (a tag of 24 bytes and a count of 4, each)
        self.assertEqual(size(ours), size(theirs) + 2 * 28)


if __name__ == '__main__':
    unittest.main()
