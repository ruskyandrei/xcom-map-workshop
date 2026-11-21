"""Piece flags' policy (tools/viewer/piece_flags.py): each class's roles from its settings, the write planner with a
prop's pathing gate and its companion writes, normalizing a request, and the parity cases the page's twin
(web/piece_flags.js, piece_flags_test.mjs) is held to.

  python -B tools/viewer/tests/test_piece_flags.py --write-cases    write piece_flag_cases.json again
"""
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


def made_cases():
    """Pieces made from numbers on donors of each class (piece_flags.made): [cls, record, kind, [class, record]]."""
    rng = random.Random(19112026)
    out = []
    for cls in CLASSES:
        family = pf.family_of(cls)
        props = pf.FAMILY_PROPS.get(family, ())
        for _ in range(3):
            raw = {k: [rng.choice((True, False)), rng.choice(('actor', 'archetype', 'class', 'assumed'))] for k in props}
            record = dict(family=family, raw=raw, roles={}, collides=rng.choice((True, False)), bodySetup=rng.choice((True, False, None)))
            for kind in ('fracWall', 'fracSlab', 'ground'):
                out.append([cls, record, kind, list(pf.made(cls, record, kind))])
    return out


def make_cases():
    """Deterministic cases: each class's defaults and a handful of mixed settings (a few unknown), every request,
    grouped by settings: [cls, raw, assumed, collides, facts, roles, [[request, plan, normalized or None]]]; and the
    made pieces' (made_cases)."""
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
            facts = dict(collides=rng.choice((True, True, False)), bodySetup=rng.choice((True, False, None)), assumed=assumed,
                         low=rng.choice((False, False, True, None)))
            plans = []
            for request in REQUESTS:
                p = pf.plan(cls, raw, request, assumed)
                plain = all(isinstance(v, bool) for v in request.values()) and all(k in pf.ROLES for k in request)
                plans.append([request, [code(p['before']), code(p['after']), [list(w) for w in p['writes']],
                                        p['companions'], p['effects'], sorted(p['unsupported']), sorted(p['conflicts']),
                                        sorted(p['unmet']), p['tiles']],
                              pf.normalize(cls, raw, request, assumed, facts['collides']) if plain else None])
            groups.append([cls, raw, assumed, facts['collides'], facts, pf.roles(cls, raw, facts), plans])
    return dict(contract=pf.contract(), groups=groups, made=made_cases())


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
        # a low piece's walking (EXP-62's hedge), only while walking is on and the piece collides
        r = pf.roles('XComDestructibleActor', default_raw('XComDestructibleActor'), dict(collides=True, low=True))
        self.assertEqual(r['walking']['limits'], ['low'])
        self.assertEqual(r['cover']['limits'], ['height-test'])
        r = pf.roles('XComDestructibleActor', dict(default_raw('XComDestructibleActor'), bAlwaysConsiderForCover=False),
                     dict(collides=True, low=True))
        self.assertNotIn('limits', r['walking'])
        r = pf.roles('XComDestructibleActor', default_raw('XComDestructibleActor'), dict(collides=False, low=True))
        self.assertEqual(r['walking']['limits'], ['no-collision'])


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


def cooked():
    """The configured install's CookedPCConsole, or the folder XCOM_COOKED names; None without either."""
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    import labpaths
    try:
        return labpaths.lwr_cooked()
    except (OSError, ValueError):
        return None


COOKED = cooked()
BAR = COOKED / 'URB_Bar.upk' if COOKED else None


@unittest.skipUnless(BAR and BAR.is_file(), 'URB_Bar.upk not found at %s' % BAR if BAR else
                     'the game install is not configured (python tools/viewer/viewer.py settings, or XCOM_COOKED)')
class Install(unittest.TestCase):
    """Read from the configured install: the class defaults in its script packages are CLASS_DEFAULTS, and URB_Bar's
    TVs are set as the survey found them (research/native/piece-flags.md, section 5)."""

    def test_script_packages_hold_the_table(self):
        packages = pf.ScriptDefaults.of(COOKED)
        self.assertIsNotNone(packages)
        for cls, table in pf.CLASS_DEFAULTS.items():
            package = 'Engine' if cls in ('StaticMeshActor', 'KAsset') else 'XComGame'
            chain = pf._script_chain(packages, '%s.Default__%s' % (package, cls))
            self.assertTrue(chain, cls)
            got = {}
            for sp, si in chain:
                for prop in table:
                    if prop not in got:
                        found, value = pf._own(sp, si, prop)
                        if found:
                            got[prop] = value
            self.assertEqual({k: got.get(k, False) for k in table}, table, cls)

    def test_the_bars_tvs(self):
        from package import Package
        p = Package(BAR)
        found = {}
        for i, path in enumerate(p.paths, 1):
            if not (path.startswith('TheWorld.PersistentLevel.') and path.count('.') == 2):
                continue
            meshes = [p.name(p.effective(c, 'StaticMesh', 0)).split('.')[-1] for c in p.children.get(i, [])
                      if p.cls(c) == 'StaticMeshComponent' and (p.effective(c, 'StaticMesh', 0) or 0) > 0]
            if meshes and meshes[0] in ('TV_BarRow', 'StoreTV_B_Off', 'StoreTV_B'):
                r = pf.resolve(p, i)
                s = pf.states(r['cls'], r['raw'])
                found.setdefault(meshes[0], set()).add((s['walking'], s['cover'], s['sight'], s['mouse']))
        self.assertEqual(found, {'TV_BarRow': {('off', 'off', 'off', 'off')}, 'StoreTV_B_Off': {('off', 'off', 'on', 'on')},
                                 'StoreTV_B': {('on', 'off', 'on', 'on')}})


    def test_the_export_carries_them(self):
        import tempfile
        from package import Package
        from export import Exporter, EXPORT_VERSION
        self.assertGreaterEqual(EXPORT_VERSION, 27)
        p = Package(BAR)
        with tempfile.TemporaryDirectory() as folder:
            e = Exporter(p, Path(folder))
            volume = next(i for i, path in enumerate(p.paths, 1) if p.cls(i) == 'XComLevelVolume')
            self.assertIsNone(e.piece_flags(volume))
            props = [i for i, path in enumerate(p.paths, 1) if path.startswith('TheWorld.PersistentLevel.XComDestructibleActor_')
                     and path.count('.') == 2]
            record = e.piece_flags(props[0])
            self.assertEqual(record['family'], 'prop')
            self.assertEqual(set(record['raw']), set(pf.FAMILY_PROPS['prop']))
            self.assertTrue(all(source in ('actor', 'archetype', 'class', 'assumed') for _, source in record['raw'].values()))
            self.assertEqual(set(record['roles']), set(pf.ROLES))
            mesh = next(i for i, _ in enumerate(p.paths, 1) if p.cls(i) == 'StaticMesh')
            self.assertEqual(set(e.mesh_collision(mesh)), {'bodySetup', 'simpleLine', 'simpleBox'})
            # a piece of another map's (the library's export: an added piece, a made wall's or ground's donor) carries
            # them too; a streamed or inherited package's doesn't (19 November 2026: the library's had none)
            self.assertEqual(Exporter(p, Path(folder), namespace='lib-URB_Bar').piece_flags(props[0]), record)
            for namespace in ('stream-URB_Bar', 'inherited-URB_Bar'):
                self.assertIsNone(Exporter(p, Path(folder), namespace=namespace).piece_flags(props[0]), namespace)

    def test_the_export_says_which_pieces_the_game_keeps_whole(self):
        # (export 36, F-139) the bar's roof and upper floor keep their fragments (bPreventChunkRemoval); its corner
        # column does not
        import tempfile
        from package import Package
        from export import Exporter, EXPORT_VERSION
        self.assertGreaterEqual(EXPORT_VERSION, 36)
        p = Package(BAR)
        with tempfile.TemporaryDirectory() as folder:
            e = Exporter(p, Path(folder))
            for name, keeps in (('XComFracLevelActor_3', True), ('XComFracLevelActor_7', True), ('XComFracLevelActor_5', None)):
                actor = p.by_name['TheWorld.PersistentLevel.' + name]
                record = e.component(actor, p.own(actor, 'FracturedStaticMeshComponent'))
                self.assertEqual(record.get('keepsPieces'), keeps, name)


class MadePieces(unittest.TestCase):
    """A wall, floor or ground made from numbers: its flags planned on what the Build makes of its donor (the user,
    19 November 2026: the flags were greyed on made pieces)."""

    def record(self, cls, **own):
        family = pf.family_of(cls)
        raw = {k: [own.get(k, pf.CLASS_DEFAULTS[cls].get(k, False)), 'actor' if k in own else 'class'] for k in pf.FAMILY_PROPS[family]}
        return dict(family=family, raw=raw, roles={}, collides=False, bodySetup=False)

    def test_a_ground_shape_on_a_static_mesh_actor_is_a_level_piece_that_collides(self):
        cls, record = pf.made('StaticMeshActor', self.record('StaticMeshActor', bPathColliding=True, bCanStepUpOn=False), 'ground')
        self.assertEqual((cls, record['family'], record['collides'], record['bodySetup']), ('XComLevelActor', 'level', True, True))
        # its own bPathColliding kept; bCanStepUpOn saved off is written on; the rest are the level piece's defaults
        self.assertEqual(record['raw']['bPathColliding'], [True, 'actor'])
        _, unsaved = pf.made('StaticMeshActor', self.record('StaticMeshActor', bPathColliding=False), 'ground')
        self.assertEqual((unsaved['raw']['bPathColliding'], unsaved['raw']['bCanStepUpOn']), ([False, 'actor'], [True, 'table']))
        _, plain = pf.made('StaticMeshActor', self.record('StaticMeshActor'), 'ground')
        self.assertEqual(plain['raw']['bPathColliding'], [True, 'table'])      # (a static mesh actor's default is off)
        self.assertEqual(record['raw']['bCanStepUpOn'], [True, 'build'])
        self.assertEqual(record['raw']['bAlwaysConsiderForCover'], [True, 'table'])
        self.assertEqual(record['raw']['bIgnoreForCover'], [False, 'table'])
        self.assertEqual(record['roles'], dict(walking='on', cover='on', sight='on', floor='on', mouse='on'))
        p = pf.plan(cls, pf.raw_of(record)[0], dict(walking=False, cover=False))
        self.assertEqual((p['unsupported'], p['writes']), ({}, [('bAlwaysConsiderForCover', False), ('bIgnoreForCover', True)]))

    def test_a_ground_shape_on_a_level_piece_has_the_builds_writes(self):
        cls, record = pf.made('XComLevelActor', self.record('XComLevelActor', bPathColliding=False, bIgnoreForCover=True,
                                                            bIsValidDestination=False, bAlwaysConsiderForCover=False), 'ground')
        self.assertEqual(cls, 'XComLevelActor')
        self.assertEqual({k: record['raw'][k] for k in ('bPathColliding', 'bIgnoreForCover', 'bIsValidDestination', 'bAlwaysConsiderForCover')},
                         dict(bPathColliding=[True, 'build'], bIgnoreForCover=[False, 'build'], bIsValidDestination=[True, 'build'],
                              bAlwaysConsiderForCover=[False, 'actor']))
        # a value from the class, not saved by the donor, is not written by the Build (written only where saved)
        _, record = pf.made('XComOpacityFadeLevelActor', self.record('XComOpacityFadeLevelActor'), 'ground')
        self.assertEqual(record['raw']['bPathColliding'], [True, 'class'])

    def test_a_wall_or_floor_keeps_its_donors_settings_with_collision_of_its_own(self):
        donor = self.record('XComFracLevelActor', bCanStepUpOn=True)
        for kind in ('fracWall', 'fracSlab'):
            cls, record = pf.made('XComFracLevelActor', donor, kind)
            self.assertEqual((cls, record['raw'], record['collides'], record['bodySetup']), ('XComFracLevelActor', donor['raw'], False, True))

    def test_the_rule_is_the_builds(self):
        sys.path.insert(0, str(HERE.parents[1] / 'bake'))
        import frac_walls
        import native_copy
        self.assertEqual(pf.MADE_GROUND['retyped'], frac_walls.RETYPED)
        self.assertEqual(pf.MADE_GROUND['always'], {native_copy.GROUND_ON[1]: dict(value=True, classes=list(native_copy.SCENERY_CLASSES))})
        saved = {k: v == b'\x01' for k, v in native_copy.GROUND_SAVED}
        self.assertEqual(pf.MADE_GROUND['saved'], {k: v for k, v in saved.items() if k in pf.PROPS})

    def test_the_contract_carries_it(self):
        c = pf.contract()
        self.assertEqual((c['madeGround'], c['classDefaults']), (pf.MADE_GROUND, pf.CLASS_DEFAULTS))


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
