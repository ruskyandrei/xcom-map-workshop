"""The catalogue the test squad is set up from (gamedata.py): the config and localisation readers on their own, and a
catalogue of a scratch game folder (squad_fixture.py), its fingerprint following every file it reads."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import gamedata  # noqa: E402
import squad_fixture  # noqa: E402


class Ini(unittest.TestCase):
    def test_operators_and_repeated_sections(self):
        text = ('[A.B]\nKey=1\nKey=2\n; Key=commented\n[Other]\nKey=9\n[a.b]\n+Key=2\n+Key=3\n.Key=3\n-Key=1\n'
                'Single=x\nSingle=y\n')
        entries = gamedata.ini_entries(text)
        self.assertEqual(gamedata.ini_values(entries, 'A.B', 'key'), ['2', '3', '3'])
        self.assertEqual(gamedata.ini_value(entries, 'a.B', 'Single'), 'y')
        self.assertEqual(gamedata.ini_values(gamedata.ini_entries('[S]\nK=1\n!K=\nK=2\n'), 'S', 'K'), ['2'])

    def test_structs(self):
        row = gamedata.parse_struct('( strName="a, (b)", iType=eChar_Soldier, ABILITIES[0]=eAbility_X, ABILITIES[3]=7, '
                                    'kInventory=( iArmor=eItem_NONE, arrLargeItems[1]=4 ), Esc="say \\"hi\\"" )  ;Tac, (Vest)')
        self.assertEqual(row['strName'], 'a, (b)')
        self.assertEqual(row['iType'], 'eChar_Soldier')
        self.assertEqual(row['ABILITIES'], {0: 'eAbility_X', 3: '7'})
        self.assertEqual(row['kInventory'], {'iArmor': 'eItem_NONE', 'arrLargeItems': {1: '4'}})
        self.assertEqual(row['Esc'], 'say "hi"')
        self.assertEqual(gamedata.array(row, 'ABILITIES', 5), ['eAbility_X', '0', '0', '7', '0'])
        for bad in ('iType=1', '( iType=1', '( =1 )', '( a b )'):
            with self.subTest(bad), self.assertRaises(ValueError): gamedata.parse_struct(bad)


class Localisation(unittest.TestCase):
    def test_encodings_keys_and_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            game = Path(root)
            for lang, encoding, line in (('INT', 'utf-16', 'm_aItemNames[eItem_A]="Alpha"\nm_aItemNames[5]="Five"'),
                                         ('FRA', 'utf-8-sig', 'm_aItemNames[eItem_A]="Alpha FR"')):
                folder = game / 'XEW' / 'XComGame' / 'Localization' / lang
                folder.mkdir(parents=True)
                (folder / f'XComGame.{lang.lower()}').write_text(f'[XLocalizedData]\n{line}\n', encoding=encoding)
            enum = gamedata.Enum(dict(path='E', entries=['eItem_None', 'eItem_A', 'eItem_B', 'eItem_C', 'eItem_D', 'eItem_E'], ambiguous=[]))
            fra = gamedata.Localisation(game, 'FRA')
            self.assertEqual(fra.label('XComGame', 'XLocalizedData', 'm_aItemNames', enum, 1), 'Alpha FR')
            self.assertEqual(fra.label('XComGame', 'XLocalizedData', 'm_aItemNames', enum, 5), 'Five')    # INT, by number
            self.assertIsNone(fra.label('XComGame', 'XLocalizedData', 'm_aItemNames', enum, 2))
            self.assertEqual(len(fra.paths), 2)


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.game = squad_fixture.make_game(Path(self.folder.name) / 'Game')
        self.patch = squad_fixture.enums()
        self.patch.__enter__()

    def tearDown(self):
        self.patch.__exit__(None, None, None)
        self.folder.cleanup()

    def test_rows_labels_and_flags(self):
        cat = gamedata.load(self.game)
        self.assertEqual((cat.family, cat.language), ('lwr', 'INT'))
        self.assertEqual(sorted(cat.characters), ['eChar_Soldier', 'eChar_Tank'])
        self.assertEqual(cat.item_label(57), 'Tactical Vest')                    # a repurposed slot, labelled by number
        self.assertEqual(cat.armours[57]['iHPBonus'], '3')
        self.assertEqual(cat.flags(cat.weapons[86], 'Properties', 'EWeaponProperty', 6)[0], 'eWP_AnyClass')   # any case
        self.assertEqual(cat.flags(cat.characters['eChar_Soldier'], 'ABILITIES', 'EAbility', 8), ['eAbility_TakeCover'])
        self.assertIn(57, cat.costed)
        self.assertNotIn(120, cat.costed)
        self.assertEqual(cat.label('country', 15), 'Canada')                     # UTF-16 strategy file
        self.assertEqual(cat.label('class', 6), 'MEC Trooper')
        self.assertEqual(cat.label('perk', 5), 'Sprinter')                       # a bonus title when no passive one
        self.assertEqual(cat.ranks()[1], (1, 'Rank 1'))
        self.assertEqual(cat.diagnostics, [])

    def test_a_later_row_replaces_an_earlier_one(self):
        core = self.game / 'XEW' / 'XComGame' / 'Config' / 'DefaultGameCore.ini'
        core.write_text(core.read_text(encoding='cp1252') + squad_fixture.armour('eItem_ArmorKevlar', 99, 0, 1, 2) + '\r\n',
                        encoding='cp1252', newline='')
        cat = gamedata.load(self.game)
        self.assertEqual(cat.armours[59]['iHPBonus'], '99')
        self.assertTrue(any('two rows' in d for d in cat.diagnostics))

    def test_fingerprint_follows_config_and_localisation(self):
        first = gamedata.load(self.game).fingerprint
        self.assertEqual(gamedata.load(self.game).fingerprint, first)
        core = self.game / 'XEW' / 'XComGame' / 'Config' / 'DefaultGameCore.ini'
        core.write_text(core.read_text(encoding='cp1252').replace('HP=6,', 'HP=7,'), encoding='cp1252', newline='')
        second = gamedata.load(self.game).fingerprint
        self.assertNotEqual(second, first)
        loc = self.game / 'XEW' / 'XComGame' / 'Localization' / 'INT' / 'XComGame.int'
        loc.write_text(loc.read_text(encoding='cp1252').replace('"Pistol"', '"Sidearm"'), encoding='cp1252')
        self.assertNotEqual(gamedata.load(self.game).fingerprint, second)

    def test_a_newer_generated_config_is_named(self):
        generated = self.game / 'XEW' / 'XComGame' / 'Config' / 'XComGameCore.ini'
        generated.write_text(squad_fixture.core_ini().replace('HP=6,', 'HP=9,'), encoding='cp1252', newline='')
        later = time.time() + 60
        os.utime(generated, (later, later))
        self.assertTrue(any('XComGameCore.ini' in d for d in gamedata.load(self.game).diagnostics))

    def test_missing_inputs(self):
        (self.game / 'XEW' / 'XComGame' / 'Config' / 'DefaultGameCore.ini').unlink()
        with self.assertRaises(gamedata.GameDataError): gamedata.load(self.game)
        with self.assertRaises(gamedata.GameDataError): gamedata.load(Path(self.folder.name) / 'Nowhere')


if __name__ == '__main__':
    unittest.main()
