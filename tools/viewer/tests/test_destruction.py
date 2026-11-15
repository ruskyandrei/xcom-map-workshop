"""What the game's damage does to a piece (export 17, scene_metadata.destruction): its toughness and health."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene_metadata import DEFAULT_TOUGHNESS_HEALTH, destruction
import settings

# URB_Bar from the game install (the game setting); without it the package test skips
COOKED = settings.lwr_cooked()
BAR = COOKED / 'URB_Bar.upk' if COOKED else None


class ToughnessPackage:
    """Exports by index: (path, class, own properties, archetype index). Negative indices are imports, by name."""
    def __init__(self, exports, imports=()):
        self.exports, self.imports = exports, list(imports)
    def cls(self, index): return self.exports[index - 1][1]
    def name(self, index): return self.exports[index - 1][0] if index > 0 else self.imports[-index - 1]
    def effective(self, index, key, default=None):
        while index > 0:
            path, cls, props, arch = self.exports[index - 1]
            if key in props: return props[key]
            index = arch
        return default


PL = 'TheWorld.PersistentLevel.'
PACKAGE = ToughnessPackage([
    ('GameData_Toughness.Toughness_METAL', 'XComDestructibleActor_Toughness', {'Health': 90}, -1),
    ('GameData_Toughness.Toughness_GLASS', 'XComDestructibleActor_Toughness', {'Health': 10, 'bFragile': True}, -1),
    ('GameData_Toughness.Toughness_INVINCIBLE', 'XComDestructibleActor_Toughness', {'Health': 90, 'bInvincible': True}, -1),
    ('Kit.Archetypes.ARC_Dumpster', 'XComDestructibleActor', {'Toughness': 1}, 0),
    (PL + 'XComDestructibleActor_1', 'XComDestructibleActor', {}, 4),                 # 5: through its archetype
    (PL + 'XComDestructibleActor_2', 'XComDestructibleActor', {}, 0),                 # 6: names none
    (PL + 'XComFracLevelActor_1', 'XComFracLevelActor', {'Toughness': 2}, 0),         # 7: glass
    (PL + 'XComFracLevelActor_2', 'XComFracLevelActor', {}, 0),                       # 8: names none
    (PL + 'XComLevelActor_1', 'XComLevelActor', {}, 0),                               # 9: scenery
    (PL + 'XComInteractiveLevelActor_1', 'XComInteractiveLevelActor', {'Toughness': 3}, 0),  # 10: an invincible door
    (PL + 'XComDestructibleActor_3', 'XComDestructibleActor', {'Toughness': -2}, 0),  # 11: an imported toughness
    ('GameData_Toughness.Toughness_HALF', 'XComDestructibleActor_Toughness', {}, 1),  # 12: Health from its archetype
    (PL + 'XComCollectible_1', 'XComCollectible', {'Toughness': 12}, 0),              # 13
], imports=['XComGame.Default__XComDestructibleActor_Toughness', 'Other.Toughness_RUBBER'])


class DestructionTests(unittest.TestCase):
    def test_a_prop_takes_its_toughness_through_its_archetype(self):
        self.assertEqual(destruction(PACKAGE, 5), dict(kind='prop', toughness='Toughness_METAL', health=90,
                                                       defaulted=False, flags=[]))

    def test_a_prop_naming_no_toughness_has_the_class_default(self):
        self.assertEqual(destruction(PACKAGE, 6), dict(kind='prop', toughness=None, health=DEFAULT_TOUGHNESS_HEALTH,
                                                       defaulted=True, flags=[]))
        self.assertEqual(DEFAULT_TOUGHNESS_HEALTH, 3)

    def test_fracturing_pieces(self):
        self.assertEqual(destruction(PACKAGE, 7), dict(kind='fracture', toughness='Toughness_GLASS', health=10,
                                                       defaulted=False, flags=['bFragile']))
        # with no toughness its health is unknown: the game's native code decides
        self.assertEqual(destruction(PACKAGE, 8), dict(kind='fracture', toughness=None, health=None, defaulted=False,
                                                       flags=[]))

    def test_scenery_has_no_health(self):
        self.assertIsNone(destruction(PACKAGE, 9))

    def test_flags_imports_and_toughness_archetypes(self):
        self.assertEqual(destruction(PACKAGE, 10)['flags'], ['bInvincible'])
        self.assertEqual(destruction(PACKAGE, 10)['kind'], 'prop')
        self.assertEqual(destruction(PACKAGE, 11), dict(kind='prop', toughness='Toughness_RUBBER', health=None,
                                                        defaulted=False, flags=[]))
        # a toughness whose own Health is unset takes its archetype's (Toughness_METAL's)
        self.assertEqual(destruction(PACKAGE, 13)['health'], 90)

    @unittest.skipUnless(BAR and BAR.exists(), 'URB_Bar.upk of the game install (the game setting) not found')
    def test_the_bars_pieces(self):
        from package import Package
        p = Package(BAR)
        of = lambda name: destruction(p, p.by_name[PL + name])  # noqa: E731
        car = of('XComDestructibleActor_20')
        self.assertEqual((car['kind'], car['toughness'], car['health'], car['flags']), ('prop', 'Toughness_SMALLCAR', 500, []))
        self.assertIsNone(of('XComLevelActor_242'))
        deco = of('XComDecoFracLevelActor_9')
        self.assertEqual((deco['kind'], deco['toughness'], deco['health']), ('fracture', 'Toughness_MASONRY', 80))
        glass = of(p.name(p.own(p.by_name[PL + 'XComDestructibleActor_20'], 'HidingPartner')).rsplit('.', 1)[-1])
        self.assertEqual((glass['kind'], glass['toughness'], glass['health'], glass['flags']),
                         ('fracture', 'Toughness_GLASS', 10, ['bFragile']))


if __name__ == '__main__': unittest.main()
