"""mapsini.py, the one reader and writer of a DefaultMaps.ini record's fields: a record read as the game reads it
(spaces allowed around '=', as a record written by hand may have them: KB-11), on a line of bytes or of text, and
written back in the kind it was given."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import mapsini  # noqa: E402
from viewer_fixtures import record  # noqa: E402


class Fields(unittest.TestCase):
    def test_a_field_written_by_hand_with_spaces_around_its_equals_sign_is_read_and_set(self):
        line = (b'Maps=( MapFamily="URB_Bar",  Name = "URB_Bar",  DisplayName= "URB_Bar (Bar) |0", '
                b'MissionType =eMission_TerrorSite, bInRotation =  True, ShipType = 10, CouncilType=eFCMType_None )')
        self.assertEqual((mapsini.field(line, 'Name'), mapsini.field(line, 'DisplayName'), mapsini.field(line, 'MapFamily')),
                         ('URB_Bar', 'URB_Bar (Bar) |0', 'URB_Bar'))
        self.assertEqual((mapsini.unquoted(line, 'MissionType'), mapsini.unquoted(line, 'bInRotation'),
                          mapsini.unquoted(line, 'CouncilType')), ('eMission_TerrorSite', 'True', 'eFCMType_None'))
        # an unquoted value of digits (the installs' landed and crashed UFOs' ShipType=10)
        self.assertEqual(mapsini.unquoted(line, 'ShipType'), '10')
        new = mapsini.set_field(mapsini.set_field(line, 'Name', 'URB_Bar_Remix'), 'bInRotation', 'False', quoted=False)
        self.assertEqual((mapsini.field(new, 'Name'), mapsini.unquoted(new, 'bInRotation')), ('URB_Bar_Remix', 'False'))
        self.assertIn(b'Name="URB_Bar_Remix",', new)
        self.assertIn(b'bInRotation=False,', new)
        self.assertEqual(mapsini.set_field(line, 'ShipType', 'eShip_UFOSupply', quoted=False).count(b'ShipType=eShip_UFOSupply,'), 1)
        # a name that ends another field's is not the field (MapName, DisplayName)
        self.assertIsNone(mapsini.field(b'Maps=( DisplayName = "x", StreamingMaps[0]=( MapName = "y" ) )', 'Name'))
        with self.assertRaises(ValueError):
            mapsini.set_field(line, 'TimeOfDay', 'eMissionTime_Day', quoted=False)

    def test_a_line_of_text_is_read_and_written_as_its_bytes_are(self):
        line = record('bar')
        text = line.decode('latin-1') + ' \xa0'         # a Latin-1 no-break space: a letter of no field
        for name in ('MapFamily', 'Name', 'DisplayName'):
            self.assertEqual(mapsini.field(text, name), mapsini.field(line, name))
        for name in ('MissionType', 'bInRotation', 'CouncilType'):
            self.assertEqual(mapsini.unquoted(text, name), mapsini.unquoted(line, name))
        self.assertEqual(mapsini.slot_streams(text), mapsini.slot_streams(line))
        self.assertEqual(mapsini.stream_slots(text), mapsini.stream_slots(line))
        new, slot = mapsini.add_stream(line, 'patch_urb_bar_remix')
        self.assertIsInstance(new, bytes)
        self.assertEqual(mapsini.add_stream(line.decode('latin-1'), 'patch_urb_bar_remix'), (new.decode('latin-1'), slot))
        written = mapsini.set_field(line, 'DisplayName', 'URB_Bar_Remix (Caf\xe9) |0')
        self.assertIsInstance(written, bytes)
        self.assertIn(b'DisplayName="URB_Bar_Remix (Caf\xe9) |0"', written)
        self.assertEqual(mapsini.set_field(line.decode('latin-1'), 'DisplayName', 'URB_Bar_Remix (Caf\xe9) |0'),
                         written.decode('latin-1'))


class PatchLevels(unittest.TestCase):
    """drop_patches: a cleared map's record streams none of Long War's patch levels (KNOWN-BUGS.md KB-23)."""

    def test_the_bars_patches_go_and_its_intro_stays_in_its_slot(self):
        line = record('bar')
        self.assertEqual(mapsini.slot_streams(line), ['CIN_DropshipIntros', 'patch_bar', 'patch_hide_randomized_objects'])
        new, dropped = mapsini.drop_patches(line)
        self.assertIsInstance(new, bytes)
        self.assertEqual(dropped, ['patch_bar', 'patch_hide_randomized_objects'])
        self.assertEqual((mapsini.slot_streams(new), mapsini.stream_slots(new)), (['CIN_DropshipIntros'], [0]))
        # nothing else of the record changes, and it still reads (the closing parenthesis kept)
        self.assertEqual(new.split(b'StreamingMaps')[0], line.split(b'StreamingMaps')[0])
        self.assertTrue(new.rstrip().endswith(b')'))
        self.assertEqual(new.count(b'('), new.count(b')'))
        self.assertEqual(mapsini.field(new, 'Name'), 'URB_Bar')
        # the edit patch then goes in the slot patch_bar had
        self.assertEqual(mapsini.add_stream(new, 'patch_urb_bar_remix')[1], 1)
        # a line of text likewise
        self.assertEqual(mapsini.drop_patches(line.decode('latin-1')), (new.decode('latin-1'), dropped))

    def test_a_stream_behind_a_taken_slot_moves_up_and_a_record_without_patches_is_left(self):
        entry = lambda k, name: f'StreamingMaps[{k}]=( MapName="{name}", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) )'  # noqa: E731
        line = ('Maps=( Name="Map", DisplayName="Map |0", ' + ', '.join(
            [entry(0, 'Patch_Map'), entry(1, 'URB_Map_CNH'), entry(2, 'CIN_Intro'), entry(5, 'patch_hide_randomized_objects')]) + ' )')
        new, dropped = mapsini.drop_patches(line)
        self.assertEqual(dropped, ['Patch_Map', 'patch_hide_randomized_objects'])       # (any case)
        # no gap is left before a stream: a travel loads only the slots before the first one (T-08)
        self.assertEqual(list(zip(mapsini.stream_slots(new), mapsini.slot_streams(new))), [(0, 'URB_Map_CNH'), (1, 'CIN_Intro')])
        self.assertTrue(new.startswith('Maps=( Name="Map", DisplayName="Map |0", StreamingMaps[0]=( MapName="URB_Map_CNH"'))
        plain = 'Maps=( Name="Map", ' + entry(0, 'CIN_Intro') + ' )'
        self.assertEqual(mapsini.drop_patches(plain), (plain, []))
        self.assertEqual(mapsini.drop_patches('Maps=( Name="Map" )'), ('Maps=( Name="Map" )', []))


if __name__ == '__main__':
    unittest.main()
