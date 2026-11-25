"""T2's stage placement, snapshot checks and conversion through the ordinary compiler."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prefab_stage as stage
from prefabs import SCHEMA, SCHEMA_VERSION
from projects import ProjectError
from settings import load_settings, resolve_game

TEST = 'e9246ca2-8f17-47a6-8394-f0e6511b3ae8'
PREFAB = 'b82516ae-5d73-4d37-93b1-deafbf016c84'
GRID = dict(origin=[-2112, -1344, 0], size=[96, 96, 64], dimensions=[36, 36, 12])
SPAWNS = [[x, y, 64] for x in (-144, 48) for y in (336, 528, 720)]
PROJECT = dict(overrides=[], stage=dict(grid=[36, 36, 18]))


def snapshot(**changes):
    return dict(dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, id=PREFAB, name='Stage fixture',
                     floor=dict(tiles=[1, 1]), pieces=[], buildings=[], groups=[], donors=[]), **changes)


def floor(box):
    return dict(id='floor-1', name='Hall', kind='building', floors=[dict(boxes=[box])])


def light(kind='point'):
    values = dict(color=[255, 232, 180], brightness=2, radius=128, falloffExponent=2, enabled=True)
    if kind == 'spot':
        values.update(innerConeAngle=15, outerConeAngle=40)
    return dict(actor=kind + 'Light', location=[96, -48, 128], rotation=[-16384, 0, 0],
                template=dict(kind=kind, version=1), light=values)


def source(name, actor='XComDestructibleActor_1', package='Donor'):
    return dict(actor=name, location=[-144, 48, 64], rotation=[0, 16384, 0],
                components=[actor + '.StaticMeshComponent_0'],
                **{'from': dict(package=package, level='base', actor=stage.LEVEL + '.' + actor)})


class StageTests(unittest.TestCase):
    def test_shared_builder_translation_cases(self):
        path = stage.TOOLS / 'viewer' / 'tests' / 'prefab_translation_cases.json'
        for case in json.loads(path.read_text(encoding='utf8')):
            with self.subTest(case['name']):
                self.assertEqual(stage.translate(case['localPosition'], case['origin']), case['worldPosition'])
                self.assertEqual(stage.translate(case['localBox'], case['origin']), case['worldBox'])

    def test_placement_preserves_ground_height_and_stays_clear_of_spawn_tiles(self):
        bounds = [-192, -96, 0, 192, 96, 768]
        placement = stage.place(bounds, GRID, SPAWNS)
        self.assertEqual(placement, stage.place(bounds, GRID, SPAWNS))
        self.assertEqual(placement['grid'], [36, 36])
        self.assertEqual(placement['bounds'][2::3], [0, 768])
        self.assertTrue(all((placement['translation'][k] - GRID['origin'][k]) % 96 == 0 for k in range(2)))
        x, y = placement['tile']
        lo_x, lo_y, hi_x, hi_y = placement['reservedTiles']
        self.assertTrue(x + 4 <= lo_x or x >= hi_x or y + 2 <= lo_y or y >= hi_y)

    def test_the_reserved_tiles_take_a_seventh_and_eighth_unit_too(self):
        # a squad of seven or eight (the test squad, squadrecords.py): XGPlayer.LoadSquad puts units past the sixth one
        # tile behind a landing point, so every tile next to one must be kept clear of the prefab
        placement = stage.place([-192, -96, 0, 192, 96, 768], GRID, SPAWNS)
        lo_x, lo_y, hi_x, hi_y = placement['reservedTiles']
        for point in SPAWNS:
            tx, ty = [(point[k] - GRID['origin'][k]) // 96 for k in range(2)]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    self.assertTrue(lo_x <= tx + dx < hi_x and lo_y <= ty + dy < hi_y, (point, dx, dy))

    def test_exact_width_can_grow_the_stage_but_a_full_stage_has_no_squad_room(self):
        limit = stage.MAX_TILES * 96
        self.assertEqual(stage.MAX_TILES, 256)
        self.assertEqual(stage.place([0, 0, 0, limit, 96, 64], GRID, SPAWNS)['grid'], [stage.MAX_TILES, 36])
        with self.assertRaises(ProjectError) as failed:
            stage.place([0, 0, 0, limit, limit, 64], GRID, SPAWNS)
        self.assertEqual(failed.exception.extra['code'], 'squad-room')

    def test_only_complete_nonempty_snapshots_can_test(self):
        for doc, code in [(dict(id=PREFAB), 'snapshot-schema'), (snapshot(), 'snapshot-empty')]:
            with self.subTest(code=code), self.assertRaises(ProjectError) as failed:
                stage.validate_snapshot(doc)
            self.assertEqual(failed.exception.extra['code'], code)
        stage.validate_snapshot(snapshot(pieces=[light()]))
        stage.validate_snapshot(snapshot(buildings=[floor([0, 0, 0, 96, 96, 176])]))

    def test_source_failures_include_each_snapshot_actor(self):
        lost_map = source('LostMap', package='Missing')
        lost_actor = source('LostActor', actor='XComDestructibleActor_2')
        lost_component = source('LostComponent')
        changed = source('ChangedDonor', package='Other')
        unsupported = light()
        unsupported['template']['version'] = 999
        doc = snapshot(pieces=[lost_map, lost_actor, lost_component, changed, unsupported],
                       donors=[dict(package='Other', sha256='b' * 64)])
        record = dict(source=dict(package='Donor', sha256='a' * 64),
                      objects=[dict(actor=lost_component['from']['actor'], component='ComponentThatChanged')])
        answers = [
            (None, ProjectError(404, 'Missing map', code='donor-missing')),
            (None, ProjectError(404, 'Missing actor', code='piece-missing')),
            (record, None),
            (dict(record, source=dict(package='Other', sha256='a' * 64)), None),
        ]
        # each is left out and named; the test goes on with what is left (plan "sturdier prefabs", R4)
        kept = source('Kept', actor='XComDestructibleActor_3')
        doc['pieces'].append(kept)
        doc['groups'] = [dict(id='g', members=[dict(added='Kept'), dict(added='LostMap')]),
                         dict(id='h', members=[dict(added='LostActor'), dict(added='LostComponent'), dict(group='g')])]
        answers.append((dict(record, objects=[dict(actor=kept['from']['actor'], component=kept['components'][0])]), None))
        with patch.object(stage, 'read_pieces', return_value=iter(answers)):
            left, records, targets, donors, notes = stage.resolve_sources(doc, None, None)
        self.assertEqual({e['actor']: e['code'] for e in notes}, dict(
            LostMap='donor-missing', LostActor='piece-missing', LostComponent='template-changed',
            ChangedDonor='donor-changed', pointLight='recipe-unsupported'))
        self.assertTrue(all(e['leftOut'] and e['message'].startswith('Left out: ') for e in notes))
        self.assertEqual(([p['actor'] for p in left['pieces']], left['groups'], list(targets), donors),
                         (['Kept'], [], ['Kept'], {'Donor': 'a' * 64}))
        self.assertEqual(len(doc['pieces']), 6)     # (the snapshot given is not changed)

    def test_effects_and_sounds_are_read_from_their_maps_and_go_into_the_test(self):
        # effects and sounds plan, stage FX6a: a prefab's effect or sound is a project's copy of its original
        steam = dict(actor='Steam', kind='effect', location=[96, 0, 32], rotation=[0, 0, 0], effect=dict(scale=2.0, follow='none'),
                     **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.Emitter_3')})
        hum = dict(actor='Hum', kind='sound', location=[0, 96, 64], rotation=[0, 0, 0],
                   **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.AmbientSoundSimple_2')})
        lost = dict(steam, actor='Lost', **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.Emitter_9')})
        wrong = dict(hum, actor='Wrong', **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.Emitter_3')})
        moved = dict(steam, actor='Moved', **{'from': dict(package='Other', level='base', actor=stage.LEVEL + '.Emitter_1')})
        asked = []

        def effect(cache, game, source, shared=None):
            asked.append((source['package'], source['actor']))
            if source['actor'] == 'Emitter_9': raise ProjectError(404, 'Donor has no effect or ambient sound called Emitter_9.', code='effect-missing')
            return dict(kind='sound' if source['actor'].startswith('Ambient') else 'effect',
                        source=dict(package=source['package'], sha256='a' * 64, actor=source['actor']))
        doc = snapshot(pieces=[steam, hum, lost, wrong, moved], donors=[dict(package='Donor', sha256='a' * 64), dict(package='Other', sha256='b' * 64)],
                       groups=[dict(id='g', members=[dict(added='Steam'), dict(added='Hum'), dict(added='Lost')])])
        with patch.object(stage, 'read_pieces', return_value=iter(())), patch.object(stage.piece_library, 'effect', effect):
            left, records, targets, donors, notes = stage.resolve_sources(doc, None, None)
        self.assertEqual({e['actor']: e['code'] for e in notes}, dict(Lost='effect-missing', Wrong='piece-missing', Moved='donor-changed'))
        self.assertEqual(asked[0], ('Donor', 'Emitter_3'))      # (asked by its short name, as a project's copy is)
        self.assertEqual(([p['actor'] for p in left['pieces']], records, donors), (['Steam', 'Hum'], {}, {'Donor': 'a' * 64}))
        self.assertEqual(targets, dict(Steam=steam['from'], Hum=hum['from']))
        self.assertEqual(left['groups'], [dict(id='g', members=[dict(added='Steam'), dict(added='Hum')])])
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=29, tileGrid=GRID)
        for builds, values in ((False, dict(follow='none')), (True, steam['effect'])):
            gates = {k: dict(v, builds=builds) if k.endswith('-values') else v for k, v in stage.compiler.FAMILIES.items()}
            with patch.object(stage, 'stock_overrides', return_value=[]), patch.object(stage.compiler, 'FAMILIES', gates):
                project, ids = stage.make_project(left, scene, dict(grid=[36, 36], translation=[384, -192, 0]), targets, TEST)
            fx, snd = project['added']
            # its values go into the test where their family builds; what says how it follows always does
            self.assertEqual((fx['kind'], fx['from'], fx['location'], fx['effect']), ('effect', steam['from'], [480, -192, 32], values))
            self.assertEqual((snd['kind'], snd['from'], 'sound' in snd, 'components' in snd, 'partner' in snd), ('sound', hum['from'], False, False, False))
            self.assertEqual(project['groups'][0]['members'], [dict(added=fx['actor']), dict(added=snd['actor'])])

    def test_a_lens_flare_is_read_from_its_map_and_goes_into_the_test(self):
        # effects and sounds plan, stage FX6b: a prefab's lens flare is a project's copy of its original, without values
        glare = dict(actor='Glare', kind='flare', location=[96, 0, 300], rotation=[0, 8192, 0],
                     **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.LensFlareSource_7')})
        wrong = dict(glare, actor='Wrong', **{'from': dict(package='Donor', level='base', actor=stage.LEVEL + '.Emitter_3')})

        def effect(cache, game, source, shared=None):
            return dict(kind='flare' if source['actor'].startswith('LensFlare') else 'effect',
                        source=dict(package=source['package'], sha256='a' * 64, actor=source['actor']))
        doc = snapshot(pieces=[glare, wrong], donors=[dict(package='Donor', sha256='a' * 64)])
        with patch.object(stage, 'read_pieces', return_value=iter(())), patch.object(stage.piece_library, 'effect', effect):
            left, records, targets, donors, notes = stage.resolve_sources(doc, None, None)
        self.assertEqual([(e['actor'], e['code']) for e in notes], [('Wrong', 'piece-missing')])
        self.assertIn('is not a lens flare', notes[0]['message'])
        self.assertEqual(([p['actor'] for p in left['pieces']], targets), (['Glare'], dict(Glare=glare['from'])))
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=29, tileGrid=GRID)
        with patch.object(stage, 'stock_overrides', return_value=[]):
            project, ids = stage.make_project(left, scene, dict(grid=[36, 36], translation=[384, -192, 0]), targets, TEST)
        flare, = project['added']
        self.assertEqual((flare['kind'], flare['from'], flare['location'], flare['rotation']), ('flare', glare['from'], [480, -192, 300], [0, 8192, 0]))
        self.assertFalse({'flare', 'effect', 'sound', 'components', 'partner'} & set(flare))

    def test_a_piece_left_out_takes_its_place_in_groups_and_partners_with_it(self):
        body, glass = source('Body'), source('Glass', actor='XComFracLevelActor_1')
        body['partner'] = 'Glass'
        doc = snapshot(pieces=[body, glass, light()], donors=[dict(package='Donor'), dict(package='Other')],
                       groups=[dict(id='in', members=[dict(added='Glass'), dict(added='pointLight')]),
                               dict(id='out', breakTogether=True, members=[dict(group='in'), dict(added='Body')])])
        left = stage.without(doc, ['Glass'])
        self.assertEqual([(p['actor'], p.get('partner')) for p in left['pieces']], [('Body', None), ('pointLight', None)])
        self.assertEqual(left['groups'], [dict(id='out', breakTogether=True, members=[dict(added='pointLight'), dict(added='Body')])])
        self.assertEqual(left['donors'], [dict(package='Donor')])
        self.assertIs(stage.without(doc, []), doc)

    def test_the_stage_is_as_tall_as_the_prefab_needs(self):
        # 18 levels at least (the tallest map's, as every test before), 30 at most; the page's prefabStageLevels passes
        # the same cases (stage_levels_cases.json, shared_cases_test.mjs)
        cases = json.loads(Path(__file__).with_name('stage_levels_cases.json').read_text(encoding='utf-8'))['cases']
        for top, levels in cases:
            self.assertEqual(stage.stage_levels([0, 0, 0, 96, 96, top]), levels, top)

    def test_one_translation_preserves_the_pose_and_remaps_nested_references(self):
        body, glass, spot = source('Body'), source('Glass', actor='XComFracLevelActor_1'), light('spot')
        body.update(prefab='car-instance', partner='Glass')
        glass.update(prefab='car-instance')
        doc = snapshot(pieces=[body, glass, spot], buildings=[floor([-192, 0, 0, 0, 192, 176])],
                       groups=[dict(id='car', breakTogether=True, members=[dict(added='Body'), dict(added='Glass')]),
                               dict(id='outer', members=[dict(group='car'), dict(building='floor-1')])])
        before = deepcopy(doc)
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=20, tileGrid=GRID)
        targets = {p['actor']: p['from'] for p in (body, glass)}
        with patch.object(stage, 'stock_overrides', return_value=[]):
            project, ids = stage.make_project(doc, scene, dict(grid=[36, 36], translation=[384, -192, 0]), targets, TEST)
        self.assertEqual(doc, before)
        added = project['added']
        self.assertEqual(added[0]['location'], [240, -144, 64])
        self.assertEqual(added[0]['rotation'], body['rotation'])
        self.assertEqual(added[0]['components'], body['components'])
        self.assertEqual(added[0]['partner'], added[1]['actor'])
        self.assertEqual(added[0]['prefab'], added[1]['prefab'])
        self.assertEqual(added[2]['location'], [480, -240, 128])
        self.assertEqual(added[2]['light'], spot['light'])
        self.assertEqual(project['groups'][1]['members'], [
            dict(group=ids['group']['car']), dict(building=ids['building']['floor-1'])])
        self.assertTrue(project['groups'][0]['breakTogether'])
        self.assertEqual(project['buildings'][0]['floors'][0]['boxes'], [[192, -192, 0, 384, 0, 176]])
        self.assertEqual(project['stage'], dict(grid=[36, 36, 18], ground=True, hideGround=True))

    def test_made_pieces_and_a_broken_copy_reach_the_tests_project(self):
        # review finding 6: a prefab's made wall (its numbers, its own blasts) and a broken copy (its blasts, Breaks
        # further in battle) are built by Test in game as they are, not as their donors
        wall, broken = source('Wall', actor='XComDecoFracLevelActor_17'), source('Broken', actor='XComFracLevelActor_1')
        wall['generated'] = dict(kind='fracWall', version=4, wall=dict(x0=0, x1=288, openings=[dict(x0=96, x1=192, z0=0, z1=208)], seed=3),
                                 blasts=[dict(at=[48, 0, 96], radius=96)])
        broken.update(blasts=[dict(at=[10, 20, 30], radius=96)], breaksFurther=True, flags=dict(cover=False))
        doc = snapshot(pieces=[wall, broken])
        stage.validate_snapshot(doc)
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=20, tileGrid=GRID)
        with patch.object(stage, 'stock_overrides', return_value=[]):
            project, _ = stage.make_project(doc, scene, dict(grid=[36, 36], translation=[0, 0, 0]),
                                            {p['actor']: p['from'] for p in (wall, broken)}, TEST)
        made, copy = project['added']
        self.assertEqual(made['generated'], wall['generated'])
        self.assertEqual((copy['blasts'], copy['breaksFurther'], copy['flags']), (broken['blasts'], True, dict(cover=False)))
        self.assertNotIn('blasts', made)
        self.assertTrue({'generated', 'blasts', 'breaksFurther'} <= set(stage.PIECE_FIELDS))

    def test_a_map_lights_wide_stored_cone_becomes_the_cone_it_lights_as(self):
        # a prefab saved before the page capped them: the Small Landed UFO's blue spots hold the map's stored 100
        spot = light('spot')
        spot['light'].update(innerConeAngle=0, outerConeAngle=100)
        doc = snapshot(pieces=[spot, light('spot')])
        before = deepcopy(doc)
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=20, tileGrid=GRID)
        with patch.object(stage, 'stock_overrides', return_value=[]):
            project, _ = stage.make_project(doc, scene, dict(grid=[36, 36], translation=[0, 0, 0]), {}, TEST)
        self.assertEqual(doc, before)
        wide, plain = project['added']
        self.assertEqual((wide['light']['innerConeAngle'], wide['light']['outerConeAngle']), (0, 89.99))
        self.assertEqual(plain['light'], light('spot')['light'])
        for key in ('innerConeAngle', 'outerConeAngle'):
            self.assertIsNone(stage.compiler.light_value_problem(key, wide['light'][key]))

    def test_the_stage_gets_a_sky_dome_and_one_turned_over_under_it(self):
        doc = snapshot(pieces=[source('Body')])
        scene = dict(name=stage.MAP, source=dict(sha256='a' * 64), exporterVersion=20, tileGrid=GRID)
        with patch.object(stage, 'stock_overrides', return_value=[]):
            project, ids = stage.make_project(doc, scene, dict(grid=[40, 46], translation=[0, 0, 0]),
                                              {'Body': doc['pieces'][0]['from']}, TEST)
        sky = stage.SKY['actor']
        record = dict(source=dict(package='URB_TruckStop_EWI', sha256='b' * 64),
                      objects=[dict(actor=sky, component=sky + '.StaticMeshComponent_1120')])
        donors = {}
        with patch.object(stage, 'read_pieces', return_value=iter([(record, None)])):
            stage.add_sky(project, ids, dict(grid=[40, 46]), GRID, 'cache', 'game', donors)
        domes = project['added'][1:]
        self.assertEqual([d['rotation'] for d in domes], [[0, 0, 0], [0, 0, 32768]])
        self.assertEqual({tuple(d['location']) for d in domes}, {(-2112 + 40 * 48, -1344 + 46 * 48, 0)})
        self.assertEqual({d['from']['actor'] for d in domes}, {sky})
        self.assertEqual(ids['added']['(stage sky 2)'], domes[1]['actor'])
        self.assertEqual(donors, {'URB_TruckStop_EWI': 'b' * 64})
        self.assertEqual(project['nextSerial'], 4)
        with patch.object(stage, 'read_pieces', return_value=iter([(None, ProjectError(404, 'gone'))])), \
                self.assertRaises(ProjectError) as failed:
            stage.add_sky(project, ids, dict(grid=[40, 46]), GRID, 'cache', 'game', {})
        self.assertEqual(failed.exception.extra['issues'][0]['code'], 'stage-sky')

    def test_off_grid_poses_warn_as_the_build_does_and_notes_are_not_listed(self):
        # since plan "sturdier prefabs" (R1) the test follows the Build's rules: these build, and are listed; a rounded
        # rotation and the compiler's notes can cause no problem in the game, and are not (14 November 2026)
        entity = 'PrefabTest_copy1'
        ids = dict(added={'Wall': entity}, building={})
        report = dict(errors=[], leftOut=[], warnings=[dict(code='off-grid', message='The wall is off grid.', entity=entity)],
                      notes=[dict(code='collectible', message='loot', entity=entity)],
                      entities=[dict(entity=entity, kind='add', rotationRounding=0.2)], buildings=[], donors=[])
        with patch.object(stage.compiler, 'compile_project', return_value=({}, report)):
            _, errors, issues = stage.compile_stage(PROJECT, {}, None, ids, {})
        self.assertEqual(errors, [])
        self.assertEqual([(e['code'], e['actor']) for e in issues], [('off-grid', 'Wall')])
        self.assertEqual(issues[0]['message'], 'The wall is off grid.')

    def test_compile_says_an_off_grid_piece_once_with_its_name(self):
        entity = 'PrefabTest_copy1'
        ids = dict(added={'Door': entity}, building={})
        warning = dict(code='off-grid', message='The door is off grid.')
        report = dict(errors=[], leftOut=[], warnings=[warning, dict(warning, entity=entity)], entities=[], buildings=[], donors=[])
        with patch.object(stage.compiler, 'compile_project', return_value=(None, report)):
            _, errors, issues = stage.compile_stage(PROJECT, {}, None, ids, {})
        self.assertEqual((errors, [(e['code'], e['actor']) for e in issues]), ([], [('off-grid', 'Door')]))

    def test_pieces_the_compiler_left_out_are_named_and_counted_for(self):
        ids = dict(added={'Fence': 'F', 'Body': 'B', 'Glass': 'G', 'Crate': 'C'}, building={})
        gone = [dict(code='not-placeable', message='it is hidden in its map', entity='F', record='added[0]'),
                dict(code='assembly-split', message='the car copies as one', entity='B', record='added[1]')]
        report = dict(errors=[], leftOut=gone, warnings=[dict(code='collectible', message='loot', entity='C')],
                      entities=[dict(entity='C', kind='add')], buildings=[], donors=[])
        with patch.object(stage.compiler, 'compile_project', return_value=({}, report)):
            _, errors, issues = stage.compile_stage(PROJECT, {}, None, ids, {})
        self.assertEqual(errors, [])
        self.assertEqual([(e['code'], e['actor'], e.get('leftOut', False)) for e in issues],
                         [('not-placeable', 'Fence', True), ('assembly-split', 'Body', True), ('left-out', 'Glass', True),
                          ('collectible', 'Crate', False)])
        self.assertEqual(issues[0]['message'], 'Left out: Fence: it is hidden in its map')
        # a piece the compiler made that the test never asked for is still the test's error
        report['entities'].append(dict(entity='X', kind='add'))
        with patch.object(stage.compiler, 'compile_project', return_value=({}, report)):
            _, errors, _ = stage.compile_stage(PROJECT, {}, None, ids, {})
        self.assertEqual([e['code'] for e in errors], ['compile-count'])

    def test_grid_pieces_and_cover_blocks_keep_their_pivot_in_the_grid(self):
        ids = dict(added={'Door': 'D', 'Cover': 'C', 'Prop': 'P', 'High door': 'H'}, building={})
        entities = [
            dict(entity='D', kind='add', actorClass='XComInteractiveLevelActor', location=[0, 0, -64]),
            dict(entity='C', kind='add', actorClass='XComLevelActor', cover=dict(type='low'), location=[0, 0, 1152]),
            dict(entity='P', kind='add', actorClass='XComLevelActor', location=[0, 0, -150]),
            dict(entity='H', kind='add', actorClass='XComInteractiveLevelActor', location=[0, 0, 1088]),
        ]
        report = dict(errors=[], leftOut=[], warnings=[], entities=entities, buildings=[], donors=[])
        scene = dict(tileGrid=GRID)
        with patch.object(stage.compiler, 'compile_project', return_value=(None, report)):
            _, errors, issues = stage.compile_stage(PROJECT, scene, None, ids, {})
        # (warnings since R1: they are built, and give no cover there)
        self.assertEqual((errors, sorted((e['code'], e['actor']) for e in issues)),
                         ([], [('pivot-outside-grid', 'Cover'), ('pivot-outside-grid', 'Door')]))
        # on a taller stage the cover block at 1,152 is in the grid
        with patch.object(stage.compiler, 'compile_project', return_value=(None, report)):
            _, _, issues = stage.compile_stage(dict(PROJECT, stage=dict(grid=[36, 36, 19])), scene, None, ids, {})
        self.assertEqual([e['actor'] for e in issues], ['Door'])

    def test_real_blank_map_compiles_building_only_and_light_only_and_checks_actual_bounds(self):
        settings = load_settings()
        game, _ = resolve_game(settings.get('game'))
        if game is None or settings.get('cache') is None:
            self.skipTest('No local game and viewer cache configured')
        wide = dict(light('spot'), actor='wideSpotLight')     # a map light's stored 100, as the UFO prefab's
        wide['light'].update(innerConeAngle=0, outerConeAngle=100)
        cases = [
            (snapshot(buildings=[floor([0, 0, 0, 128 * 96, 96, 768])]), [128, 36], 1, 0),
            (snapshot(pieces=[light(), light('spot'), wide]), [36, 36], 0, 3),
        ]
        for doc, grid, buildings, lights in cases:
            with self.subTest(grid=grid):
                try:
                    result = stage.prepare(doc, TEST, settings['cache'], game)
                except ProjectError as error:
                    if error.extra['code'] in ('stage-unprepared', 'stage-missing'):
                        self.skipTest(error.message)
                    raise
                self.assertEqual(result['placement']['grid'], grid)
                self.assertEqual(len(result['report']['buildings']), buildings)
                self.assertEqual(result['report']['counts']['lights']['added'], lights)
                self.assertEqual(result['report']['counts']['deleted'], len(stage.STOCK_PROPS))
                self.assertEqual(sum('PrefabTest_sky' in a['actor'] for a in result['project']['added']), 2)
        # over 18 levels the stage grows with the prefab, to 30 at most (with no warning that it is untried, 16
        # November 2026); over the height allowance the size warns and the test builds all the same (plan "sturdier
        # prefabs", R7 and part H)
        for top, levels, codes in ((1345, 22, set()), (2113, 30, {'size-large'})):
            with self.subTest(top=top):
                try:
                    result = stage.prepare(snapshot(buildings=[floor([0, 0, 0, 96, 96, top])]), TEST, settings['cache'], game)
                except ProjectError as error:      # the blank map not prepared at this export number: as above
                    if error.extra['code'] in ('stage-unprepared', 'stage-missing'):
                        self.skipTest(error.message)
                    raise
                self.assertEqual(result['project']['stage']['grid'], [36, 36, levels])
                self.assertEqual(result['report']['stageGrid'], [36, 36, levels])
                self.assertTrue(codes <= {i['code'] for i in result['issues']}, result['issues'])
                self.assertNotIn('stage-levels-tall', {i['code'] for i in result['issues']})
                self.assertEqual(result['leftOut'], [])


if __name__ == '__main__':
    unittest.main()
