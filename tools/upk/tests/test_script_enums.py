"""The enum reader (script_enums.py) on synthetic enum exports, and, when the configured install is LWR, on its
XComGame.upk (the entries the test squad names: test-squad plan, section 2). The live checks skip without that
install; LWR's numbers are no claim about another install."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import script_enums  # noqa: E402
from script_enums import Enum, EnumError, entries  # noqa: E402

NAMES = ['None', 'eThing_A', 'eThing_B', 'eThing_MAX', 'IntProperty', 'Foo', 'StructProperty', 'Vector', 'BoolProperty']


def fname(index, number=0): return struct.pack('<iI', index, number)


def export(values, props=b'', count=None):
    """An enum export: net index, properties then None, Next, the names."""
    body = struct.pack('<i', 7) + props + fname(0) + struct.pack('<i', 0)
    body += struct.pack('<i', len(values) if count is None else count)
    return body + b''.join(fname(*v) for v in values)


class Entries(unittest.TestCase):
    def test_names_and_numbers(self):
        raw = export([(1,), (2,), (2, 1), (2, 2), (3,)])
        self.assertEqual(entries(raw, NAMES), ['eThing_A', 'eThing_B', 'eThing_B_0', 'eThing_B_1', 'eThing_MAX'])

    def test_huge_numbers_are_unsigned(self):
        # LWR's padded ECharacter: numbers in steps of 2^24, up to 0x80000000 and beyond
        raw = export([(3, 0x01000000), (3, 0x80000000)])
        self.assertEqual(entries(raw, NAMES), ['eThing_MAX_16777215', 'eThing_MAX_2147483647'])

    def test_properties_before_the_names_are_skipped(self):
        props = fname(5) + fname(4) + struct.pack('<ii', 4, 0) + struct.pack('<i', 9)
        props += fname(5) + fname(6) + struct.pack('<ii', 12, 0) + fname(7) + b'\0' * 12
        props += fname(5) + fname(8) + struct.pack('<ii', 0, 0) + b'\1'
        self.assertEqual(entries(export([(1,), (2,)], props), NAMES), ['eThing_A', 'eThing_B'])

    def test_bad_exports_are_refused(self):
        good = export([(1,), (2,)])
        for raw, why in ((good[:-3], 'truncated'), (export([(1,)], count=5), 'count past the end'),
                         (export([(1,)], count=-1), 'negative count'), (good + b'\0' * 8, 'bytes after the names'),
                         (export([(99,)]), 'name index outside the table'), (b'\0' * 10, 'too short')):
            with self.subTest(why), self.assertRaises(EnumError): entries(raw, NAMES)


class Lookups(unittest.TestCase):
    def setUp(self):
        self.enum = Enum(dict(path='X.ESoldierClass', entries=['eSC_None', 'eSC_Psi_12', 'eSC_Psi_12', 'eSC_MAX'],
                              ambiguous=['eSC_Psi_12']))

    def test_a_shared_name_names_no_entry(self):
        self.assertEqual(self.enum.index('eSC_None'), 0)
        with self.assertRaises(EnumError): self.enum.index('eSC_Psi_12')
        with self.assertRaises(EnumError): self.enum.index('eSC_Nothing')
        self.assertNotIn('eSC_Psi_12', self.enum)
        self.assertEqual(self.enum.name(2), 'eSC_Psi_12')
        self.assertIsNone(self.enum.unique(2))
        self.assertIsNone(self.enum.name(4))
        self.assertIsNone(self.enum.name(-1))


def lwr_package():
    try:
        from settings import game_install, game_kind, load_settings
        game, _ = game_install(load_settings())
    except (OSError, ValueError, ImportError):
        return None
    if game is None or game_kind(game) != 'lwr': return None
    path = Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole' / 'XComGame.upk'
    return path if path.is_file() else None


PACKAGE = lwr_package()


@unittest.skipUnless(PACKAGE, 'no LWR install configured')
class LiveLwr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enums = script_enums.read(PACKAGE)

    def test_reference_entries(self):
        item = Enum(self.enums['EItemType'])
        for name, index in dict(eItem_SHIVDeck_I=113, eItem_SHIVDeck_III=115, eItem_ShivMinigun=109,
                                eItem_ArmorSkeleton=61, eItem_ArmorArchangel=63, eItem_BattleScanner=97,
                                eItem_FragGrenade=81, eItem_SmokeGrenade=82, eItem_GasGrenade=86, eItem_MecArmor1=193,
                                eItem_Chaingun=28, eItem_MecKineticArm=22, eItem_MecFlameThrower=23,
                                eItem_SniperRifle=6).items():
            self.assertEqual(item.index(name), index, name)
        self.assertEqual(Enum(self.enums['ECharacter']).index('eChar_Tank'), 3)
        self.assertEqual(Enum(self.enums['ESoldierClass']).index('eSC_Mec'), 6)
        self.assertEqual(Enum(self.enums['EPerkType']).index('ePerk_SquadSight'), 3)

    def test_lwr_padding_is_kept_by_position(self):
        classes = Enum(self.enums['ESoldierClass'])
        self.assertEqual((classes.name(19), classes.name(20)), ('eSC_Psi_12', 'eSC_Psi_12'))
        self.assertIn('eSC_Psi_12', classes.ambiguous)
        self.assertEqual(len(Enum(self.enums['ECharacter'])), 227)

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            first = script_enums.cached(PACKAGE, folder)
            kept = list(Path(folder).glob('enums-*.json'))
            self.assertEqual(len(kept), 1)
            self.assertIn(f'-r{script_enums.READER_VERSION}', kept[0].name)
            self.assertEqual(script_enums.cached(PACKAGE, folder)['EItemType'], first['EItemType'])


if __name__ == '__main__':
    unittest.main()
