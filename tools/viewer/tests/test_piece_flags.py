"""Piece flags' policy (tools/viewer/piece_flags.py): each class's roles from its settings, the write planner with a
prop's pathing gate and its companion writes, normalizing a request, and the parity cases the page's twin
(web/piece_flags.js, piece_flags_test.mjs) is held to.

  python -B tools/viewer/tests/test_piece_flags.py --write-cases    write piece_flag_cases.json again
"""
import itertools
import json
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import piece_flags as pf  # noqa: E402

CASES = HERE / 'piece_flag_cases.json'
CLASSES = ('XComLevelActor', 'XComDestructibleActor', 'XComCollectible', 'XComInteractiveLevelActor',
           'XComFracLevelActor', 'XComLadder', 'StaticMeshActor', 'KAsset', 'XComLevelVolume')
REQUESTS = ([{r: v} for r in pf.ROLES for v in (True, False)]
            + [dict(walking=False, cover=False, sight=False, floor=False), dict(walking=True, cover=True, sight=True),
               dict(cover=True, mouse=False), dict(walking=True, sight=False), dict(floor=True, walking=False),
               dict(cover=False, sight=True), {'ethereal': True}, dict(walking=1)])


def default_raw(cls):
    family = pf.family_of(cls)
    return {k: pf.CLASS_DEFAULTS.get(cls, {}).get(k, False) for k in pf.FAMILY_PROPS.get(family, ())}


CODES = {'on': 'o', 'off': 'x', 'partial': 'p', 'unknown': 'u', 'n/a': '-'}


def code(states):
    """Five states as five letters (o on, x off, p partial, u unknown, - n/a), in ROLES order."""
    return ''.join(CODES[states[r]] for r in pf.ROLES)


def make_cases():
    """Deterministic cases: each class's defaults and a handful of mixed settings (a few unknown), every request,
    grouped by settings: [cls, raw, assumed, collides, facts, roles, [[request, plan, normalized or None]]]."""
    rng = random.Random(16112026)
    groups = []
    for cls in CLASSES:
        family = pf.family_of(cls)
        props = pf.FAMILY_PROPS.get(family, ())
        raws = [default_raw(cls)]
        if family in pf.GATED:
            raws.append(dict(default_raw(cls), bIgnoreForPathing=True))
            raws.append(dict(default_raw(cls), bIgnoreForPathing=True, bPathColliding=True))
            raws.append(dict(default_raw(cls), bIgnoreForPathing=True, bAlwaysConsiderForCover=False, bIgnoreForCover=True))
        for _ in range(3 if props else 1):
            raws.append({k: rng.choice((True, False, True, False, None) if rng.random() < 0.2 else (True, False)) for k in props})
        for raw in raws:
            assumed = [k for k in props if rng.random() < 0.08]
            facts = dict(collides=rng.choice((True, True, False)), bodySetup=rng.choice((True, False, None)), assumed=assumed)
            plans = []
            for request in REQUESTS:
                p = pf.plan(cls, raw, request, assumed)
                plain = all(isinstance(v, bool) for v in request.values()) and all(k in pf.ROLES for k in request)
                plans.append([request, [code(p['before']), code(p['after']), [list(w) for w in p['writes']],
                                        p['companions'], p['effects'], sorted(p['unsupported']), sorted(p['conflicts']),
                                        sorted(p['unmet']), p['tiles']],
                              pf.normalize(cls, raw, request, assumed, facts['collides']) if plain else None])
            groups.append([cls, raw, assumed, facts['collides'], facts, pf.roles(cls, raw, facts), plans])
    return dict(contract=pf.contract(), groups=groups)


class Roles(unittest.TestCase):
    def test_class_defaults(self):
        on = dict(walking='on', cover='on', sight='on', floor='on', mouse='on')
        self.assertEqual(pf.states('XComLevelActor', default_raw('XComLevelActor')), on)
        self.assertEqual(pf.states('XComDestructibleActor', default_raw('XComDestructibleActor')), dict(on, floor='off'))
        self.assertEqual(pf.states('XComFracLevelActor', default_raw('XComFracLevelActor')), dict(on, floor='off'))
        ladder = pf.states('XComLadder', default_raw('XComLadder'))
        self.assertEqual((ladder['cover'], ladder['floor'], ladder['walking']), ('n/a', 'off', 'on'))
        door = pf.states('XComInteractiveLevelActor', default_raw('XComInteractiveLevelActor'))
        self.assertEqual(door['mouse'], 'n/a')
        plain = pf.states('StaticMeshActor', default_raw('StaticMeshActor'))
        self.assertEqual(plain, dict(walking='n/a', cover='n/a', sight='n/a', floor='off', mouse='n/a'))
        self.assertEqual(set(pf.states('XComLevelVolume', {}).values()), {'n/a'})

    def test_gate_makes_walking_partial_and_sight_follow_the_floor(self):
        raw = dict(default_raw('XComDestructibleActor'), bIgnoreForPathing=True)
        s = pf.states('XComDestructibleActor', raw)
        self.assertEqual((s['walking'], s['cover'], s['sight']), ('partial', 'off', 'off'))
        s = pf.states('XComDestructibleActor', dict(raw, bPathColliding=True))
        self.assertEqual((s['sight'], s['floor']), ('partial', 'on'))

    def test_floor_needs_step_up(self):
        raw = dict(default_raw('XComLevelActor'), bCanStepUpOn=False)
        r = pf.roles('XComLevelActor', raw)
        self.assertEqual(r['floor']['state'], 'off')
        self.assertIn('stops-floor', r['floor']['limits'])

    def test_interactive_prop_never_gives_cover(self):
        r = pf.roles('XComDestructibleActor', dict(default_raw('XComDestructibleActor'), bInteractive=True))
        self.assertEqual(r['cover']['state'], 'n/a')

    def test_unknown_input(self):
        raw = dict(default_raw('XComLevelActor'), bIgnoreForCover=None)
        self.assertEqual(pf.states('XComLevelActor', raw)['cover'], 'unknown')

    def test_limits(self):
        r = pf.roles('XComLevelActor', default_raw('XComLevelActor'), dict(collides=False, assumed=['bIgnoreForCover']))
        self.assertEqual(r['mouse']['limits'], ['no-collision'])
        self.assertEqual(r['cover']['limits'], ['no-collision', 'assumed'])
        r = pf.roles('XComLevelActor', default_raw('XComLevelActor'), dict(collides=True, bodySetup=False))
        self.assertEqual(r['walking']['limits'], ['no-body-setup'])
        self.assertNotIn('limits', r['floor'])
        self.assertNotIn('limits', r['mouse'])


class Plan(unittest.TestCase):
    def test_each_role_alone(self):
        raw = default_raw('XComLevelActor')
        for role, prop, value in (('walking', 'bAlwaysConsiderForCover', False), ('cover', 'bIgnoreForCover', True),
                                  ('sight', 'bBlockUnitVisibility', False), ('floor', 'bPathColliding', False),
                                  ('mouse', 'bIgnoreFor3DCursorCollision', True)):
            p = pf.plan('XComLevelActor', raw, {role: False})
            self.assertEqual(p['writes'], [(prop, value)], role)
            self.assertEqual([r for r in pf.ROLES if p['after'][r] != p['before'][r]], [role])
            self.assertEqual(p['tiles'], role != 'mouse')

    def test_no_op_writes_nothing(self):
        p = pf.plan('XComLevelActor', default_raw('XComLevelActor'), dict(walking=True, mouse=True))
        self.assertEqual((p['writes'], p['tiles']), ([], False))

    def test_assumed_value_is_written(self):
        p = pf.plan('XComLevelActor', default_raw('XComLevelActor'), dict(cover=True), assumed=['bIgnoreForCover'])
        self.assertEqual(p['writes'], [('bIgnoreForCover', False)])
        self.assertFalse(p['tiles'])

    def test_floor_on_sets_step_up(self):
        raw = dict(default_raw('XComFracLevelActor'))
        p = pf.plan('XComFracLevelActor', raw, dict(floor=True))
        self.assertEqual(p['writes'], [('bPathColliding', True), ('bCanStepUpOn', True)])
        p = pf.plan('XComFracLevelActor', dict(raw, bPathColliding=True, bCanStepUpOn=True), dict(floor=False))
        self.assertEqual(p['writes'], [('bPathColliding', False)])

    def test_opening_the_gate_keeps_cover_and_sight_off(self):
        # walking off, cover and sight off only because of the gate: asking walking on opens it, and cover and sight
        # are written off so they stay as they were
        raw = dict(default_raw('XComDestructibleActor'), bIgnoreForPathing=True, bAlwaysConsiderForCover=False)
        p = pf.plan('XComDestructibleActor', raw, dict(walking=True))
        self.assertEqual(p['conflicts'], {})
        self.assertEqual(dict(p['writes']), dict(bAlwaysConsiderForCover=True, bIgnoreForCover=True,
                                                 bBlockUnitVisibility=False, bIgnoreForPathing=False))
        self.assertEqual(sorted(p['companions']), ['cover', 'sight'])
        self.assertEqual(p['after'], dict(p['before'], walking='on'))

    def test_inherited_gate_is_cleared_too(self):
        raw = dict(default_raw('XComDestructibleActor'), bIgnoreForPathing=True, bAlwaysConsiderForCover=False)
        p = pf.plan('XComDestructibleActor', raw, dict(cover=True))
        self.assertIn(('bIgnoreForPathing', False), p['writes'])
        self.assertEqual(p['after']['cover'], 'on')
        self.assertEqual(p['after']['sight'], 'off')

    def test_half_on_walking_needs_an_answer(self):
        raw = dict(default_raw('XComDestructibleActor'), bIgnoreForPathing=True)
        p = pf.plan('XComDestructibleActor', raw, dict(cover=True))
        self.assertEqual(sorted(p['conflicts']), ['walking'])
        self.assertEqual(p['writes'], [])
        p = pf.plan('XComDestructibleActor', raw, dict(cover=True, walking=True))
        self.assertEqual(p['conflicts'], {})
        self.assertEqual((p['after']['walking'], p['after']['cover'], p['after']['sight']), ('on', 'on', 'off'))
        # walking off alone needs no gate
        p = pf.plan('XComDestructibleActor', raw, dict(walking=False))
        self.assertEqual(p['writes'], [('bAlwaysConsiderForCover', False)])

    def test_gated_floor_sight_follows(self):
        raw = dict(default_raw('XComDestructibleActor'), bIgnoreForPathing=True, bPathColliding=True)
        p = pf.plan('XComDestructibleActor', raw, dict(floor=False))
        self.assertEqual((p['after']['sight'], p['effects'], p['conflicts']), ('off', ['sight'], {}))

    def test_unsupported(self):
        p = pf.plan('StaticMeshActor', default_raw('StaticMeshActor'), dict(cover=False, floor=True))
        self.assertEqual(sorted(p['unsupported']), ['cover'])
        self.assertEqual(p['writes'], [('bPathColliding', True)])
        p = pf.plan('XComInteractiveLevelActor', default_raw('XComInteractiveLevelActor'), dict(mouse=False))
        self.assertEqual(sorted(p['unsupported']), ['mouse'])
        self.assertEqual(sorted(pf.plan('XComLevelActor', {}, {'walking': 1})['unsupported']), ['walking'])

    def test_normalize(self):
        raw = default_raw('XComLevelActor')
        self.assertEqual(pf.normalize('XComLevelActor', raw, dict(walking=True, cover=False)), dict(cover=False))
        self.assertEqual(pf.normalize('XComLevelActor', raw, dict(walking=True), ['bAlwaysConsiderForCover']),
                         dict(walking=True))
        off = dict(raw, bPathColliding=False)
        self.assertEqual(pf.normalize('XComLevelActor', off, dict(floor=False), collides=False), dict(floor=False))
        self.assertEqual(pf.normalize('XComLevelActor', off, dict(floor=False), collides=True), {})


class Parity(unittest.TestCase):
    def test_cases_are_current(self):
        """piece_flag_cases.json is what this module gives now (write it again with --write-cases)."""
        self.assertEqual(json.loads(CASES.read_text(encoding='utf-8')), json.loads(json.dumps(make_cases())))

    def test_contract_classes_cover_compiler_classes(self):
        sys.path.insert(0, str(HERE.parents[1] / 'editor'))
        import compiler
        for cls in compiler.CLASS_FAMILY:
            self.assertIn(cls, pf.CLASSES, cls)


if __name__ == '__main__':
    if '--write-cases' in sys.argv:
        CASES.write_text(json.dumps(make_cases(), indent=None, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
        print('wrote', CASES)
    else:
        unittest.main()
