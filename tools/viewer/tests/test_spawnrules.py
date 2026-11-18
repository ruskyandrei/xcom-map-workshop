"""What an install does with spawn points (spawnrules.py; editor spawns implementation plan, SP2 and SP8): the loader's
spawn mutators, the RandomSpawns numbers and ExcludeMaps lines, the rules of a plain and a Long War install, and the
planning of a variant's ExcludeMaps line. Fixtures, and the configured install's files where present."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import spawnrules  # noqa: E402
from settings import lwr_cooked  # noqa: E402

LOADER = '''[XComMutator.XComMutatorLoader]
arrTacticalMutators="XComLZMutator.XComLZMutator"
arrTacticalMutators="XComLZMutator.XComBombMutator"
;arrTacticalMutators="XComLZMutator.XComMeldSpawnMutator"
arrTacticalMutators="XComLZMutator.XComPodSpawnMutator"
arrTacticalMutators = "XComLZMutator.XComSpawnAlienMutator"
arrStrategicMutators="XComLZMutator.XComFCMutator"
arrTacticalMutators="LWRebalance.RebalanceMutator"
'''
SPAWNS = '''[XComLZMutator.XComSpawnAlienMutator]\r
USE_OVERWATCH = true\r
MIN_DROP_DIST = 7\r
MAX_DROP_DIST = 32\r
ExcludeMaps = "EWI_ChryssalidHive"\r
;ExcludeMaps = "DLC2_2_Deluge"\r
ExcludeMaps=URB_Plain\r
\r
[XComLZMutator.XComSpawnMutator]\r
PLAYER_PROXIMITY = 29\r
ExcludeMaps = "NotThisSection"\r
\r
[XComLZMutator.XComMeldSpawnMutator]\r
NumContainers = 3\r
EqSlope = 1.55\r
'''


def lines(text):
    return text.encode('latin-1').split(b'\r\n')


class Loader(unittest.TestCase):
    def test_the_spawn_mutators_in_order_a_commented_one_absent(self):
        found = spawnrules.loader(LOADER)
        self.assertTrue(found['found'])
        self.assertEqual(found['families'], dict(landing='active', bomb='active', meld='absent', pods='active', dropIns='active'))
        self.assertEqual(found['tactical'][-1], 'LWRebalance.RebalanceMutator')
        self.assertEqual(found['commented'], ['XComLZMutator.XComMeldSpawnMutator'])
        self.assertNotIn('XComLZMutator.XComFCMutator', found['tactical'])      # a strategic one

    def test_a_file_without_the_section_is_unknown(self):
        found = spawnrules.loader('[Something.Else]\narrTacticalMutators="XComLZMutator.XComLZMutator"\n')
        self.assertFalse(found['found'])
        self.assertEqual(set(found['families'].values()), {'unknown'})


class RandomSpawns(unittest.TestCase):
    def test_numbers_and_exclusions_by_section(self):
        found = spawnrules.random_spawns(SPAWNS)
        self.assertTrue(found['found'])
        self.assertEqual(found['config'], dict(useOverwatch=True, dropMin=7, dropMax=32, playerProximity=29,
                                               meldContainers=3, meldSlope=1.55))
        self.assertEqual([(e['name'], e['live'], e['quoted']) for e in found['excludeMaps']],
                         [('EWI_ChryssalidHive', True, True), ('DLC2_2_Deluge', False, True), ('URB_Plain', True, False)])
        self.assertTrue(spawnrules.excluded(found, 'ewi_chryssalidhive'))
        self.assertFalse(spawnrules.excluded(found, 'DLC2_2_Deluge'))           # commented out
        self.assertFalse(spawnrules.excluded(found, 'NotThisSection'))          # another section's line


class Rules(unittest.TestCase):
    def make(self, files):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        game = Path(d.name)
        (game / 'Binaries' / 'Win32').mkdir(parents=True)
        (game / 'Binaries' / 'Win32' / 'XComGame.exe').write_bytes(b'')
        config = game / 'XEW' / 'XComGame' / 'Config'
        config.mkdir(parents=True)
        (game / 'XEW' / 'Binaries' / 'Win32').mkdir(parents=True)
        (game / 'XEW' / 'Binaries' / 'Win32' / 'XComEW.exe').write_bytes(b'')
        for name, text in files.items():
            (config / name).write_text(text, encoding='latin-1', newline='')
        return game

    def test_plain_enemy_within_has_every_family_absent(self):
        found = spawnrules.rules(self.make({}))
        self.assertEqual({found[f] for f in spawnrules.FAMILIES}, {'absent'})
        self.assertEqual(found['excludeMaps'], [])

    def test_a_long_war_install(self):
        found = spawnrules.rules(self.make({spawnrules.LOADER: LOADER, spawnrules.RANDOM_SPAWNS: SPAWNS,
                                            'DefaultLZMutator.ini': ''}))
        self.assertEqual((found['meld'], found['dropIns']), ('absent', 'active'))
        self.assertEqual(found['config']['dropMax'], 32)
        self.assertTrue(found['dropInSection'])
        self.assertEqual(found['detected'], 'install')

    def test_no_game_is_unknown(self):
        found = spawnrules.rules(None)
        self.assertEqual({found[f] for f in spawnrules.FAMILIES}, {'unknown'})

    def test_the_configured_install(self):
        cooked = lwr_cooked()
        game = Path(cooked).parents[2] if cooked else None
        if not game or not (game / 'XEW' / 'XComGame' / 'Config' / spawnrules.LOADER).is_file():
            self.skipTest('no Long War install configured')
        found = spawnrules.rules(game)
        self.assertEqual({found[f] for f in spawnrules.FAMILIES}, {'active'})
        self.assertTrue(spawnrules.excluded(found, 'EWI_ChryssalidHive'))
        self.assertEqual(found['config']['meldContainers'], 3)
        self.assertEqual(found['config']['playerProximity'], 29)


class PlanExclusion(unittest.TestCase):
    def test_after_the_last_exclude_line_live_or_commented(self):
        text = lines(SPAWNS)
        at, new, why = spawnrules.plan_exclusion(text, 'URB_Bar_MyBar', 'XCOM Map Workshop: My bar')
        self.assertIsNone(why)
        self.assertEqual(text[at - 1], b'ExcludeMaps=URB_Plain')
        self.assertEqual(new, [b';URB_Bar_MyBar: scripted drop-ins land where placed (XCOM Map Workshop: My bar)',
                               b'ExcludeMaps = "URB_Bar_MyBar"'])
        after = text[:at] + new + text[at:]
        self.assertTrue(spawnrules.excluded(spawnrules.random_spawns(b'\r\n'.join(after)), 'URB_Bar_MyBar'))
        self.assertEqual(spawnrules.exclusion_lines(after, 'URB_Bar_MyBar'), [at + 1])

    def test_nothing_when_the_variant_is_listed_already(self):
        text = lines(SPAWNS)
        self.assertEqual(spawnrules.plan_exclusion(text, 'urb_plain', 'x'), (None, [], None))

    def test_a_commented_entry_for_the_variant_is_no_entry(self):
        text = lines(SPAWNS)
        at, new, why = spawnrules.plan_exclusion(text, 'DLC2_2_Deluge', 'x')
        self.assertEqual(new[-1], b'ExcludeMaps = "DLC2_2_Deluge"')

    def test_a_section_with_no_exclusions_gets_the_line_at_its_end(self):
        text = lines('[XComLZMutator.XComSpawnAlienMutator]\r\nMAX_DROP_DIST = 32\r\n\r\n[Other]\r\nA=1')
        at, new, why = spawnrules.plan_exclusion(text, 'V', 'n')
        self.assertEqual(at, 2)
        text = lines('[XComLZMutator.XComSpawnAlienMutator]\r\nMAX_DROP_DIST = 32')
        self.assertEqual(spawnrules.plan_exclusion(text, 'V', 'n')[0], 2)

    def test_another_sections_line_and_the_plus_form(self):
        # a line naming the variant in another section is not its entry; the drop-in section's +ExcludeMaps= is
        text = lines(SPAWNS.replace('"NotThisSection"', '"V"'))
        at, new, why = spawnrules.plan_exclusion(text, 'V', 'n')
        self.assertEqual((at, why), (7, None))
        plus = lines(SPAWNS.replace('ExcludeMaps=URB_Plain', '+ExcludeMaps="V"'))
        self.assertEqual(spawnrules.plan_exclusion(plus, 'V', 'n'), (None, [], None))

    def test_the_block_is_a_note_and_the_entry(self):
        self.assertEqual(spawnrules.exclusion_block('V', 'XCOM Map Workshop, project P'),
                         [b';V: scripted drop-ins land where placed (XCOM Map Workshop, project P)', b'ExcludeMaps = "V"'])

    def test_a_file_with_no_drop_in_section_says_why(self):
        at, new, why = spawnrules.plan_exclusion(lines('[Other]\r\nA=1'), 'V', 'n')
        self.assertEqual((at, new), (None, []))
        self.assertIn('another version', why)


if __name__ == '__main__':
    unittest.main()
