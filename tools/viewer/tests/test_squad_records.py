"""The test squad as the game takes it (squadrecords.py), on a scratch install (squad_fixture.py): the default squad
against the text plays wrote before the setup panel, each kind of unit's record, LWR's charges kept in perk entries,
the base stats, the counts of each array, what the panel offers, and the errors, warnings and notes a squad gets."""
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import gamedata  # noqa: E402
import squad_fixture  # noqa: E402
import squadrecords as sr  # noqa: E402
import squads  # noqa: E402

OLD_TEXT = (HERE / 'squad_default_lwr.txt').read_text(encoding='ascii').strip()


class Base(unittest.TestCase):
    kind = 'lwr'

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.game = squad_fixture.make_game(Path(self.folder.name) / 'Game', kind=self.kind)
        patch = squad_fixture.enums()
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)
        self.cat = gamedata.load(self.game)
        self.templates = sr.templates(self.cat)

    def squad(self, *units):
        doc = sr.default_document()
        if units: doc = dict(doc, units=[dict(u, id=u.get('id', f'u{i}')) for i, u in enumerate(units, 1)])
        return squads.check_document(doc)

    def unit(self, kind='soldier', **fields):
        return dict(self.templates[kind], **fields)

    def one(self, unit):
        r = sr.resolve(self.squad(unit), self.cat)
        return r, r.units[0]


class Default(Base):
    def test_the_default_is_the_old_six_with_their_class_records(self):
        r = sr.resolve(sr.default_document(), self.cat)
        self.assertTrue(r.playable, (r.errors, [(u.errors, u.warnings) for u in r.units]))
        # byte for byte the text plays wrote before the panel, but for each soldier's class record (the class's
        # number: LWR's class rules and the game's class label read it)
        self.assertEqual(re.sub(r',kClass=\(eType=\d\)', '', r.text), OLD_TEXT)
        self.assertEqual(re.findall(r'kClass=\(eType=(\d)\)', r.text), ['4', '3', '2', '1', '3', '4'])
        self.assertEqual([u.warnings + u.notes for u in r.units], [[]] * 6)
        self.assertEqual(r.units[2].summary, 'Heavy · Carapace Armor · Light Machine Gun · Rocket Launcher · HE Grenade')

    def test_the_default_document_is_a_valid_squad(self):
        self.assertEqual(squads.check_document(sr.default_document())['name'], 'Test squad')


class Kinds(Base):
    def test_a_shiv(self):
        r, u = self.one(self.unit('shiv', first='Iron'))
        text = sr.unit_text(u.record)
        self.assertTrue(text.startswith('(kChar=(strName="Iron",iType=3,kInventory=(iArmor=113,iPistol=0,'
                                        'arrLargeItems[0]=109,iNumLargeItems=1),'), text)
        self.assertIn('aAbilities[0]=8,aProperties[0]=4,aProperties[3]=1,aProperties[5]=1,aStats[0]=12,aStats[1]=55,', text)
        self.assertIn('aTraversals[1]=1,aTraversals[2]=1,aTraversals[3]=1,aTraversals[5]=1,aTraversals[7]=1,aTraversals[9]=1,'
                      'eClass=eSC_None', text)
        self.assertNotIn('kSoldier', text)
        self.assertTrue(text.endswith(',iUnitLoadoutID=-1)'))
        self.assertEqual(u.warnings, [])

    def test_a_mec_with_its_modules_in_order(self):
        r, u = self.one(self.unit('mec', first='Big', last='Mec'))
        text = sr.unit_text(u.record)
        self.assertIn('iType=2,kInventory=(iArmor=193,iPistol=0,arrLargeItems[0]=28,arrLargeItems[1]=22,arrLargeItems[2]=23,'
                      'iNumLargeItems=3)', text)
        self.assertIn('eClass=eSC_Mec', text)
        self.assertIn('kClass=(eType=6)', text)
        self.assertNotIn('arrCustomItems', text)               # the psi amp is a soldier's
        self.assertEqual(u.errors + u.warnings, [])

    def test_a_flyer_with_four_items_and_the_charges_lwr_reads_from_perks(self):
        r, u = self.one(self.unit(armour='eItem_ArmorArchangel', items=['eItem_BattleScanner', 'eItem_FragGrenade',
                                                                       'eItem_SmokeGrenade', 'eItem_BattleScanner']))
        text = sr.unit_text(u.record)
        self.assertIn('iArmor=63,', text)
        self.assertIn('arrSmallItems[0]=97,arrSmallItems[1]=81,arrSmallItems[2]=82,arrSmallItems[3]=97,iNumSmallItems=4,'
                      'arrCustomItems[0]=37,iNumCustomItems=1', text)
        # two scanners: two charges (aUpgrades[8] >> 1); a smoke grenade: one (aUpgrades[44] >> 1)
        self.assertIn('aUpgrades[8]=4,aUpgrades[44]=2,aAbilities[0]=7', text)
        self.assertEqual(len(u.warnings), 1)
        self.assertIn('3 small slots', u.warnings[0])

    def test_a_chosen_perk_and_a_charge_share_its_entry(self):
        perks = sr.default_document()['units'][0]
        r, u = self.one(self.unit(perks=['ePerk_SquadSight'], items=['eItem_SmokeGrenade']))
        self.assertIn('aUpgrades[3]=1,aUpgrades[44]=2,', sr.unit_text(u.record))
        self.assertEqual(perks['perks'], [])

    def test_base_stats_set_by_hand_replace_the_installs(self):
        r, u = self.one(self.unit(stats={'hp': 20, 'aim': 0, 'sight': 30}))
        text = sr.unit_text(u.record)
        self.assertIn('aStats[0]=20,aStats[3]=14,aStats[7]=30,aStats[10]=30,', text)
        self.assertNotIn('aStats[1]=', text)                   # aim 0: nothing written, as the record's own default

    def test_repeated_abilities_are_counted_as_the_game_does(self):
        core = self.game / 'XEW' / 'XComGame' / 'Config' / 'DefaultGameCore.ini'
        core.write_text(core.read_text(encoding='cp1252').replace('ABILITIES[0]=eAbility_TakeCover, ABILITIES[1]=0',
                                                                    'ABILITIES[0]=eAbility_TakeCover, ABILITIES[1]=eAbility_TakeCover'),
                        encoding='cp1252', newline='')
        self.cat = gamedata.load(self.game)
        r, u = self.one(self.unit())
        self.assertIn('aAbilities[0]=6,aAbilities[27]=2,', sr.unit_text(u.record))

    def test_eight_units_fit_in_one_command(self):
        units = [self.unit(id=f'u{i}', first='Unit', last=str(i), items=['eItem_FragGrenade'] * 8, perks=['ePerk_SquadSight'])
                 for i in range(8)]
        r = sr.resolve(self.squad(*units), self.cat)
        self.assertTrue(r.playable, r.errors)
        self.assertLess(len(r.text), sr.MAX_LINE)
        self.assertEqual(r.text.count('(kChar=('), 8)
        self.assertEqual(r.text.count('('), r.text.count(')'))
        self.assertIn('arrSmallItems[7]=81,iNumSmallItems=8', r.text)
        self.assertTrue(any('one tile behind' in n for n in r.notes))
        with mock.patch.object(sr, 'MAX_LINE', 1000):
            self.assertFalse(sr.resolve(self.squad(*units), self.cat).playable)


class Problems(Base):
    def test_errors_stop_a_play(self):
        cases = [
            (self.unit(armour='eItem_PlasmaLightRifle_Muton'), 'not an armour'),
            (self.unit(armour='eItem_SHIVDeck_I'), 'the body comes from it'),
            (self.unit('shiv', armour='eItem_ArmorKevlar'), 'the body comes from it'),
            (self.unit(armour='eItem_Gone'), 'not on this install'),
            (self.unit(armour=None), 'Choose its armour'),
            (self.unit(first='O"Brien'), 'letters, digits, spaces'),
            (self.unit(look=None), 'Choose a look'),
            (self.unit('mec', weapons=['eItem_MecKineticArm']), 'needs its gun first'),
            (self.unit('shiv', weapons=[]), 'needs a gun'),
            (self.unit(**{'class': 'eSC_Psi'}), 'not one the editor writes'),
            (self.unit(**{'class': 'eSC_Psi_12'}), 'names more than one'),
        ]
        for unit, words in cases:
            with self.subTest(words):
                r, u = self.one(unit)
                self.assertFalse(r.playable)
                self.assertIsNone(r.text)
                self.assertTrue(any(words in e for e in u.errors), u.errors)

    def test_names_the_game_takes(self):
        for good in ('Tom', "D'Arcy", 'Anne-Marie', 'J. 2', ''):
            self.assertEqual(sr.game_name(good), good)
        for bad in ('a"b', 'a\\b', 'a,b', 'a(b', 'a)b', 'a=b', 'a|b', 'new\nline', 'Jörg', 'tab\there'):
            with self.subTest(bad), self.assertRaises(ValueError): sr.game_name(bad)

    def test_warnings_say_what_the_game_does(self):
        cases = [
            (self.unit('shiv', weapons=['eItem_ShivMinigun', 'eItem_ShivMinigun']), 'only its first gun'),
            (self.unit('shiv', items=['eItem_FragGrenade']), 'carries no items'),
            (self.unit(weapons=['eItem_AssaultRifle', 'eItem_RocketLauncher', 'eItem_Shotgun']), 'first two large items'),
            (self.unit('mec', items=['eItem_FragGrenade']), 'gives a MEC no HE Grenade'),
            (self.unit(weapons=['eItem_Chaingun']), 'not a soldier\'s weapon'),
            (self.unit(sidearm='eItem_AssaultRifle'), 'not a pistol'),
            (self.unit(items=['eItem_FragGrenade'] * 9), 'backpack'),
            (self.unit(perks=['ePerk_Poisoned']), 'not one of the usual perks'),
        ]
        for unit, words in cases:
            with self.subTest(words):
                r, u = self.one(unit)
                self.assertTrue(r.playable, u.errors)
                self.assertTrue(any(words in w for w in u.warnings), u.warnings)
        # a heavy's machine gun in the pistol's place is the game's own way
        r, u = self.one(self.unit(**{'class': 'eSC_HeavyWeapons'}, sidearm='eItem_LMG', weapons=['eItem_RocketLauncher']))
        self.assertEqual(u.warnings, [])

    def test_two_shivs_under_lwr(self):
        r = sr.resolve(self.squad(self.unit('shiv'), self.unit('shiv')), self.cat)
        self.assertTrue(any('one SHIV act each turn' in w for w in r.warnings))

    def test_unresolved_choices_are_left_out_with_a_note_and_kept_in_the_squad(self):
        doc = self.squad(self.unit(items=['eItem_FragGrenade', 'eItem_Gone'], perks=['ePerk_Gone'], sidearm='eItem_Gone2',
                                   country='eCountry_Atlantis'))
        r = sr.resolve(doc, self.cat)
        u = r.units[0]
        self.assertTrue(r.playable)
        self.assertEqual(len(u.notes), 4, u.notes)
        self.assertIn('arrSmallItems[0]=81,iNumSmallItems=1', r.text)
        self.assertIn('iPistol=0', r.text)
        self.assertEqual(doc['units'][0]['items'], ['eItem_FragGrenade', 'eItem_Gone'])     # the document keeps them

    def test_no_install(self):
        r = sr.resolve(self.squad(), None)
        self.assertFalse(r.playable)
        self.assertTrue(r.errors)


class Offered(Base):
    def test_lists_by_role_and_cost(self):
        c = sr.choices(self.cat)
        self.assertEqual(c['slots']['shiv']['armour'], ['eItem_SHIVDeck_III', 'eItem_SHIVDeck_I'])
        self.assertIn('eItem_MecKineticArm', c['slots']['mec']['weapons'])
        self.assertNotIn('eItem_Chaingun', c['slots']['soldier']['weapons'])
        self.assertNotIn('eItem_PlasmaLightRifle_Muton', c['slots']['soldier']['weapons'])     # no cost row: an alien's
        self.assertIn('eItem_PlasmaLightRifle_Muton', c['slotsAll']['soldier']['weapons'])     # Show every item
        self.assertNotIn('eItem_Grapple', c['slots']['soldier']['items'])
        self.assertEqual(c['slots']['soldier']['sidearm'], ['eItem_Pistol'])
        self.assertEqual(c['base']['shiv'], dict(hp=12, aim=55, defence=0, mobility=14, will=0, sight=27))
        self.assertEqual([k['available'] for k in c['kinds']], [True, True, True])
        self.assertEqual([x['id'] for x in c['classes']], list(sr.SOLDIER_CLASSES))
        self.assertEqual([x['label'] for x in c['countries']], ['Belgium', 'Canada', 'India', 'Italy', 'Mexico', 'United States'])
        perks = {p['id']: p for p in c['perks']}
        self.assertTrue(perks['ePerk_SquadSight']['normal'])
        self.assertFalse(perks['ePerk_Poisoned']['normal'])
        self.assertEqual(c['templates']['mec']['weapons'], ['eItem_Chaingun', 'eItem_MecKineticArm', 'eItem_MecFlameThrower'])


class PlainEw(Base):
    kind = 'ew'

    def test_soldiers_only_and_six_at_most(self):
        c = sr.choices(self.cat)
        self.assertEqual([k['available'] for k in c['kinds']], [True, False, False])
        r = sr.resolve(sr.default_document(), self.cat)
        self.assertTrue(r.playable, (r.errors, [u.errors for u in r.units]))
        r, u = self.one(self.unit('shiv'))
        self.assertTrue(any('writes no SHIV' in e for e in u.errors))
        seven = [self.unit(id=f'u{i}') for i in range(7)]
        r = sr.resolve(self.squad(*seven), self.cat)
        self.assertTrue(any('at most 6' in e for e in r.errors))
        r, u = self.one(self.unit(armour='eItem_END_WEAPONS'))           # an armour LWR made: no body on plain EW
        self.assertTrue(any('no body' in e for e in u.errors))


if __name__ == '__main__':
    unittest.main()
