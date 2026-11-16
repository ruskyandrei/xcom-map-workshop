"""The editor's Build (tools/editor/build.py): a saved project to a variant package, with the tools it runs stubbed."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402
import compiler  # noqa: E402

RECORDS = HERE.parents[1] / 'patch' / 'tests' / 'defaultmaps-records.txt'
BASE = b'pristine bar'
VARIANT, PATCH = 'URB_Bar_Test_1234', 'patch_urb_bar_test_1234'
INTRO = 'CIN_DropshipIntros_%s' % VARIANT      # the variant's own landing intro (intro_copy.py, F-45)
# a compiled spec's objects (test_compiler covers the compiler): a copy the Build makes in the map, and a hide
COPY = dict(type='copy', location=[1, 2, 0], poses=[dict(location=[1, 2, 0], rotation=[0, 16384, 0])],
            labels=['XComLevelActor_1_copy1'], boxes=[[0, 1, 0, 1, 0, 1]], classes=['XComLevelActor'],
            extra=['bLogTiles=False'], **{'from': ['XComLevelActor_1']})
HIDE = dict(type='hide', exact=True, location=[0, 0, 0], alsoHide=['XComLevelActor_2'], labels=['delete:XComLevelActor_2'],
            boxes=[[90, 100, -5, 5, 0, 50]])
# a copy of a class the Build can't make in the map (a door; none in M1 yet): it stays the patch's
DOOR = dict(COPY, labels=['XComInteractiveLevelActor_3_copy2'], classes=['XComInteractiveLevelActor'],
            **{'from': ['XComInteractiveLevelActor_3']})
NATIVE_HIDE = dict(name='XComLevelActor_2', label='delete:XComLevelActor_2', box=[90, 100, -5, 5, 0, 50])
# the compiler's lights object (editor lights plan, 4.2 and 9.5): a moved spot, a recoloured point light, an added
# disabled copy, a recipe spot, a deletion, and a glowing piece's generated light following it
SPOT_BEFORE = dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, innerConeAngle=0.0,
                   outerConeAngle=44.0, enabled=True, location=[0.0, 0.0, 300.0], rotation=[-16384, 0, 0])
LIGHTS = dict(type='lights',
              deletes=[dict(name='SpotLight_3', label='delete:SpotLight_3', kind='spot', role='static', reach=[0] * 6)],
              changes=[dict(name='SpotLight_53', label='SpotLight_53', kind='spot', role='static',
                            location=[96.0, 0.0, 300.0], rotation=[-16384, 0, 0], set={},
                            light=dict(SPOT_BEFORE, location=[96.0, 0.0, 300.0]), before=SPOT_BEFORE),
                       dict(name='PointLight_0', label='PointLight_0', kind='point', role='static',
                            location=[1.0, 2.0, 3.0], rotation=[0, 0, 0], set=dict(color=[255, 0, 0]),
                            before=dict(color=[255, 255, 255], location=[1.0, 2.0, 3.0], rotation=[0, 0, 0]))],
              adds=[dict(name='SpotLight_53_copy7', label='SpotLight_53_copy7', kind='spot', role='static',
                         location=[0, 0, 0], rotation=[0, 0, 0], light=dict(enabled=False), guidSeed='p|x',
                         **{'from': 'SpotLight_53'}),
                    dict(name='SpotLight_copy8', label='SpotLight_copy8', kind='spot', role='static',
                         template=dict(kind='spot', version=1), location=[0, 0, 0], rotation=[0, 0, 0],
                         light=SPOT_BEFORE, guidSeed='p|y')],
              area=[dict(op='move', name='GeneratedMeshAreaLight_370', light='GeneratedMeshAreaLight_370',
                         owner='XComLevelActor_9', ownerEntity='XComLevelActor_9', location=[0, 0, 0],
                         rotation=[0, 0, 0])])


def record(name):
    for line in RECORDS.read_bytes().split(b'\n'):
        if line.startswith(name.encode() + b'\t'):
            return line.split(b'\t', 1)[1].decode('latin-1')
    raise KeyError(name)


class ConfigLines(unittest.TestCase):
    def test_the_base_record_renamed_out_of_rotation_with_the_patch_in_a_free_slot(self):
        bar = record('bar')
        c = build.config_lines(['[XComGame.XComMapManager]', bar, record('templeship')],
                               ['LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))', ';LZArray=(MapName="URB_Bar")',
                                'LZArray=(MapName="Other",StartLoc=(X=0,Y=0,Z=0))'],
                               ['AbductionMapRules=(iMaxDifficulty=eMissionDiff_Moderate, Map="URB_Bar")'],
                               'URB_Bar', VARIANT, PATCH, '%s (Test) |0' % VARIANT)
        line, = c['maps']
        self.assertEqual(c['missions'], ['Abduction'])
        self.assertIn('Name="%s"' % VARIANT, line)
        self.assertIn('DisplayName="%s (Test) |0"' % VARIANT, line)
        self.assertIn('MapFamily="URB_Bar"', line)
        self.assertRegex(line, r'bInRotation=False')
        # Bar's record streams slots 0, 1 and 5 already: the patch goes in 2
        self.assertEqual(c['streamSlots'], [2])
        self.assertIn('StreamingMaps[2]=( MapName="%s"' % PATCH, line)
        self.assertEqual(line.count('StreamingMaps['), bar.count('StreamingMaps[') + 1)
        self.assertEqual(c['landingZones'], ['LZArray=(MapName="%s",StartLoc=(X=1,Y=2,Z=3))' % VARIANT])
        self.assertEqual(c['miniMods'], ['AbductionMapRules=(iMaxDifficulty=eMissionDiff_Moderate, Map="%s")' % VARIANT])

    def test_the_variant_streams_its_own_intro_copy_in_place_of_the_original(self):
        bar = record('bar')
        self.assertEqual(build.intro_stream(bar), 'CIN_DropshipIntros')
        self.assertIsNone(build.intro_stream(record('templeship')))      # Temple's arrival names no map
        # the alien bases' entrance picks its scene by map name too (F-76)
        self.assertEqual(build.intro_stream(record('alienbase01')), 'CIN_TP05A_EnteringAlienBase')
        c = build.config_lines([bar], [], [], 'URB_Bar', VARIANT, None, 'x', intros={'CIN_DropshipIntros': INTRO})
        line, = c['maps']
        self.assertIn('StreamingMaps[0]=( MapName="%s"' % INTRO, line)
        self.assertNotIn('MapName="CIN_DropshipIntros"', line)
        self.assertEqual(line.count('StreamingMaps['), bar.count('StreamingMaps['))

    def test_a_map_with_several_records_gets_one_for_each_mission(self):
        bar = record('bar')
        terror = build.set_field(bar.replace('CIN_DropshipIntros', 'CIN_FastropeIntros'), 'MissionType',
                                 'eMission_TerrorSite', quoted=False)
        bomb = build.set_field(build.set_field(bar, 'MissionType', 'eMission_Special', quoted=False), 'CouncilType',
                               'eFCMType_Bomb', quoted=False)
        self.assertEqual(build.intro_streams([bar, terror, bomb, record('templeship')]),
                         ['CIN_DropshipIntros', 'CIN_FastropeIntros'])
        copies = {'CIN_DropshipIntros': INTRO, 'CIN_FastropeIntros': 'CIN_FastropeIntros_%s' % VARIANT}
        c = build.config_lines(['[XComGame.XComMapManager]', bar, record('bar_terror'), terror, bomb, bomb], [], [],
                               'URB_Bar', VARIANT, PATCH, lambda mission: '%s (Test, %s) |0' % (VARIANT, mission),
                               intros=copies)
        # Bar_Terror is another map; the second bomb record, the same once renamed, is written once
        self.assertEqual(c['missions'], ['Abduction', 'Terror', 'Council bomb'])
        self.assertEqual(len(c['maps']), 3)
        self.assertIn('DisplayName="%s (Test, Terror) |0"' % VARIANT, c['maps'][1])
        self.assertIn('MapName="CIN_FastropeIntros_%s"' % VARIANT, c['maps'][1])
        self.assertIn('MapName="%s"' % INTRO, c['maps'][2])
        self.assertTrue(all('MapName="%s"' % PATCH in line and 'Name="%s"' % VARIANT in line for line in c['maps']))
        self.assertEqual(c['streamSlots'], [2, 2, 2])
        # which of the base map's records each stands for (Play in game picks a mission by them): both bombs are one
        self.assertEqual(c['recordMissions'], [[0], [1], [2, 3]])
        self.assertEqual(c['matchedNames'], [])     # these bombs' display names are Bar's own: no _Bomb in them

    def test_the_projects_missions_alone_and_the_kinds_it_adds(self):
        # mission types plan, D4: records for the listed missions only; an added kind made from the base map's abduction
        bar = record('bar')
        terror = build.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False)
        bomb = build.set_field(build.set_field(bar, 'MissionType', 'eMission_Special', quoted=False), 'CouncilType', 'eFCMType_Bomb', quoted=False)
        maps = ['[XComGame.XComMapManager]', bomb, bar, terror]
        named = lambda mission: '%s (Test, %s) |0' % (VARIANT, mission)  # noqa: E731
        c = build.config_lines(maps, [], [], 'URB_Bar', VARIANT, PATCH, named,
                               missions_list=[dict(kind='Special/Bomb'), dict(record=2), dict(kind='Crash', ship='eShip_UFOSmallScout'),
                                              dict(record=1), dict(kind='Nonsense')])
        self.assertEqual(c['missions'], ['Abduction', 'Terror', 'Council bomb', 'Crashed UFO'])     # added kinds in missions.ADDED_KINDS' order
        self.assertEqual(c['recordMissions'], [[1], [2], ['Special/Bomb'], ['Crash']])
        self.assertTrue(c['missionsFromProject'])
        added_bomb, crash = c['maps'][2], c['maps'][3]
        self.assertIn('MissionType=eMission_Crash', crash)
        self.assertIn('ShipType=eShip_UFOSmallScout', crash)
        self.assertIn('DisplayName="%s (Test, Crashed UFO) |0"' % VARIANT, crash)
        # the bomb: Slaughterhouse's stream (LWR's mutator places its bomb), Long War's _Bomb in the display name
        self.assertIn('CouncilType=eFCMType_Bomb', added_bomb)
        self.assertIn('MapName="URB_Slaughterhouse_Stream"', added_bomb)
        self.assertIn('DisplayName="%s_Bomb (Test, Council bomb) |0"' % VARIANT, added_bomb)
        self.assertTrue(all('bInRotation=False' in l and 'MapName="%s"' % PATCH in l for l in c['maps']))
        # no list: every record of the base map, as before; the template is the abduction, not the first record
        self.assertEqual(build.config_lines(maps, [], [], 'URB_Bar', VARIANT, PATCH, named)['missions'], ['Council bomb', 'Abduction', 'Terror'])
        self.assertEqual(build.template_record([bomb, terror, bar]), bar)
        # two records of one mission that differ: display names of their own
        other = build.set_field(bar, 'TimeOfDay', 'eMissionTime_Day', quoted=False)
        c = build.config_lines([bar, other], [], [], 'URB_Bar', VARIANT, None, named)
        self.assertEqual(c['missions'], ['Abduction', 'Abduction 2'])
        self.assertIn('DisplayName="%s (Test, Abduction 2) |0"' % VARIANT, c['maps'][1])

    def test_a_bomb_records_display_name_keeps_what_long_war_matches(self):
        # Long War throttles a bomb mission's reinforcements by "_Bomb" in the record's display name (plan 2.5)
        bar = record('bar')
        bomb = build.set_field(build.set_field(build.set_field(bar, 'MissionType', 'eMission_Special', quoted=False),
                                               'CouncilType', 'eFCMType_Bomb', quoted=False),
                               'DisplayName', 'URB_Bar_Bomb (Mission Variant Bomb Defusal Bar) |0')
        c = build.config_lines(['[XComGame.XComMapManager]', bar, bomb], [], [], 'URB_Bar', VARIANT, PATCH,
                               lambda mission: '%s (Test, %s) |0' % (VARIANT, mission))
        self.assertIn('DisplayName="%s (Test, Abduction) |0"' % VARIANT, c['maps'][0])
        self.assertIn('DisplayName="%s_Bomb (Test, Council bomb) |0"' % VARIANT, c['maps'][1])
        self.assertEqual([(m['record'], m['marker']) for m in c['matchedNames']], [(1, '_Bomb')])
        # one record: the project's name alone, the marker kept all the same; a variant named with it gets no second
        c = build.config_lines([bomb], [], [], 'URB_Bar', VARIANT, None, '%s (Test) |0' % VARIANT)
        self.assertIn('DisplayName="%s_Bomb (Test) |0"' % VARIANT, c['maps'][0])
        c = build.config_lines([bomb], [], [], 'URB_Bar', 'URB_Bar_Bomb_x', None, 'URB_Bar_Bomb_x (Test) |0')
        self.assertIn('DisplayName="URB_Bar_Bomb_x (Test) |0"', c['maps'][0])

    def test_the_projects_landing_zones_are_the_variants_lines(self):
        """Clear map plan, step C7: zones without lwr: false, in order, in place of the base map's lines."""
        zones = [dict(id='a', location=[719, -1681, 64], direction='north', kind='normal'),
                 dict(id='b', location=[1, 2, 64], direction='east', kind='inside', lwr=False),
                 dict(id='c', location=[5, 6.5, 80], direction='west', kind='normal', missionType='eMission_Abduction')]
        lz = ['LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))']
        c = build.config_lines([record('bar')], lz, [], 'URB_Bar', VARIANT, PATCH, 'x', zones=zones)
        self.assertEqual(c['landingZones'], [
            'LZArray=(MapName="%s",ESpawnLoc=ESL_Normal,StartLoc=(X=719,Y=-1681,Z=64),StartDir=ELZD_North)' % VARIANT,
            'LZArray=(MapName="%s",MissionType=eMission_Abduction,ESpawnLoc=ESL_Normal,StartLoc=(X=5,Y=6.5,Z=80),'
            'StartDir=ELZD_West)' % VARIANT])
        self.assertTrue(c['landingZonesFromProject'])
        self.assertEqual(c['landingZoneIds'], ['a', 'c'])       # Land here finds a zone's line by them
        self.assertEqual(build.config_lines([record('bar')], lz, [], 'URB_Bar', VARIANT, PATCH, 'x', zones=[])['landingZones'], [])
        # without zones, as before: a copy of the base map's, and no mark
        c = build.config_lines([record('bar')], lz, [], 'URB_Bar', VARIANT, PATCH, 'x')
        self.assertNotIn('landingZonesFromProject', c)
        # a plain install has no landing-zone file: none, whatever the project says
        c = build.config_lines([record('bar')], None, None, 'URB_Bar', VARIANT, PATCH, 'x', zones=zones)
        self.assertEqual((c['landingZones'], c.get('landingZonesFromProject')), (None, None))

    def test_a_map_without_a_record_is_refused_and_one_without_landing_zones_gets_none(self):
        with self.assertRaises(build.BuildError):
            build.config_lines([], ['LZArray=(MapName="URB_Bar")'], [], 'URB_Bar', VARIANT, PATCH, 'x')
        # TempleShip, the final mission, lands no Skyranger and has no landing zones
        c = build.config_lines([record('bar')], ['LZArray=(MapName="Other")'], [], 'URB_Bar', VARIANT, PATCH, 'x')
        self.assertEqual((c['landingZones'], c['miniMods']), ([], []))
        m = dict(variant=VARIANT, patch=PATCH, cache='Lighting_1', files={'CookedPCConsole/a.upk': 'x'}, builtAt='now',
                 project=dict(id='p', name='n', revision=1), source=dict(map='URB_Bar', sha256='s'), config=c)
        self.assertIn('nothing to add; URB_Bar has no landing zones there', build.readme(m))

    def test_the_intro_map_builds_from_its_commented_out_abduction_record(self):
        # LWR comments out both of Act1_IntroLevel's records; a variant takes the abduction's (maplist.SWITCHED_OFF)
        abduction, tutorial = record('intro_abduction'), record('intro_tutorial')
        c = build.config_lines(['[XComGame.XComMapManager]', abduction, tutorial, record('bar')], [],
                               ['AbductionMapRules=(iMaxDifficulty=eMissionDiff_VeryHard, Map="Act1_IntroLevel")'],
                               'Act1_IntroLevel', 'Act1_IntroLevel_Test_1', PATCH, 'Act1_IntroLevel_Test_1 (Test) |0')
        line, = c['maps']
        self.assertEqual(c['missions'], ['Abduction'])
        self.assertTrue(line.startswith('Maps=( MapFamily="Act1_IntroLevel"'))     # live, without the ';'
        self.assertIn('Name="Act1_IntroLevel_Test_1"', line)
        self.assertRegex(line, r'bInRotation=False')
        self.assertNotIn('Act1_IntroLevel_Script', line)
        self.assertIn('StreamingMaps[1]=( MapName="%s"' % PATCH, line)
        self.assertEqual(c['miniMods'], ['AbductionMapRules=(iMaxDifficulty=eMissionDiff_VeryHard, Map="Act1_IntroLevel_Test_1")'])
        # a commented-out record of another map is no record of it
        with self.assertRaises(build.BuildError):
            build.config_lines([';' + record('bar')], [], [], 'URB_Bar', VARIANT, PATCH, 'x')

    def test_cache_names_are_the_variants_own(self):
        # output names plan 4: <Variant>_Lighting, a plain name (lighting_fixture.cache_fname gives number 0)
        self.assertEqual(build.cache_name(VARIANT), VARIANT + '_Lighting')
        self.assertEqual(build.cache_name('BarFix_2'), 'BarFix_2_Lighting')
        sys.path.insert(0, str(HERE.parents[1] / 'bake'))
        import lighting_fixture
        self.assertEqual(lighting_fixture.cache_fname(build.cache_name(VARIANT)), (VARIANT + '_Lighting', 0))


class LightCounts(unittest.TestCase):
    def test_light_edits_are_counted_by_kind(self):
        native = dict(lights={k: v for k, v in LIGHTS.items() if k != 'type'})
        self.assertTrue(build.has_light_edits(native))
        self.assertEqual(build.light_counts(native), dict(
            moved=1, changed=1, added=2, recipeSpots=1, deleted=1,
            area=dict(moved=1, copied=0, deleted=0, pieces=['XComLevelActor_9'])))
        self.assertEqual(build.light_summary(build.light_counts(native)),
                         'lights 1 moved, 1 changed, 2 added, 1 deleted; glow lights following their pieces 1 moved '
                         '(XComLevelActor_9)')
        for empty in (dict(), dict(lights=None), dict(lights=dict(deletes=[], changes=[], adds=[], area=[]))):
            self.assertFalse(build.has_light_edits(empty))
            self.assertIsNone(build.light_counts(empty))
            self.assertEqual(build.light_summary(None), '')
        # a change that moves nothing and sets nothing counts as neither
        still = dict(lights=dict(changes=[dict(name='X', location=[1, 2, 3], rotation=[0, 0, 0], set={},
                                               before=dict(location=[1.0, 2.0, 3.0], rotation=[0, 0, 0]))]))
        self.assertEqual((build.light_counts(still)['moved'], build.light_counts(still)['changed']), (0, 0))

    def test_the_quick_build_light_text_stays_conditional_until_the_game_test(self):
        # plan 4.3: until EXP-26 run 2 is played, the unbaked behaviour is stated as to be confirmed
        self.assertIn('still to be confirmed (EXP-26 run 2)', build.QUICK_LIGHTS)
        for limitation in ('a deleted light\'s pool stays on the baked surfaces', 'an added light has no baked light',
                           'the old glow stays baked where it was'):
            self.assertIn(limitation, build.QUICK_LIGHTS)


class Builds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.lwr, self.udk, self.work, self.output = root / 'lwr', root / 'udk', root / 'patchtool', root / 'builds'
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        cooked.mkdir(parents=True)
        (cooked / 'URB_Bar.upk').write_bytes(BASE)
        (cooked / 'CIN_DropshipIntros.upk').write_bytes(b'the landing intros')
        cfg = self.lwr / 'XEW/XComGame/Config'
        cfg.mkdir(parents=True)
        (cfg / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n%s\r\n' % record('bar')).encode('latin-1'))
        (cfg / 'DefaultLZMutator.ini').write_bytes(b'LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))\r\n')
        (cfg / 'DefaultMiniMods.ini').write_bytes(b'AbductionMapRules=(iMaxDifficulty=eMissionDiff_Moderate, Map="URB_Bar")\r\n')
        self.doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='0000-test', name='Test "build" | one',
                        revision=3, savedAt='2026-11-07T11:00:00Z',
                        source=dict(map='URB_Bar', sha256=hashlib.sha256(BASE).hexdigest(), exporterVersion=12),
                        output=dict(shipAs=VARIANT, patch=PATCH))
        self.project = root / 'project.json'
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        self.ran = []
        self.relit = 1
        self.failing = None
        self.unchanged_lighting = False
        self.landing = True         # the intro has a landing of its own for URB_Bar
        self.no_staged_report = False
        # the compiler's own work is tested in test_compiler; here it gives a fixed spec
        saved = compiler.find_export, compiler.compile_project
        self.addCleanup(setattr, compiler, 'find_export', saved[0])
        self.addCleanup(setattr, compiler, 'compile_project', saved[1])
        compiler.find_export = lambda cache, doc: (root / 'scene.json', dict(name='URB_Bar'))
        self.spec = dict(name=PATCH, map=dict(name='URB_Bar', origin=[0, 0, 0], shipAs=VARIANT), editor={},
                         objects=[COPY, DOOR, HIDE])
        self.report = dict(errors=[], warnings=[], counts=dict(moved=0, deleted=0, added=1, errors=0, warnings=0))
        compiler.compile_project = lambda doc, scene, enable=(), library=None, foreign=(): (self.spec, dict(self.report))

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, args, log):
        args = [str(a) for a in args]
        self.ran.append(args)
        Path(log).write_text('ran\n')
        if self.failing and any(self.failing in a for a in args):
            raise build.BuildError('%s failed' % self.failing)
        if args[0] == 'pwsh':
            step = args[4]
            if step == 'build':
                (self.work / PATCH).mkdir(parents=True, exist_ok=True)
                (self.work / PATCH / 'seed-plan-built.tsv').write_text('box\t1\n')
            else:
                out = self.udk / 'UDKGame/CookedPC/Maps/patches'
                out.mkdir(parents=True, exist_ok=True)
                (out / ('%s.udk' % PATCH)).write_bytes(b'cooked patch')
        elif any(a.endswith('stream_copy.py') for a in args):
            k = next(i for i, a in enumerate(args) if a.endswith('stream_copy.py'))
            Path(args[k + 2]).write_bytes(b'stream copy of ' + Path(args[k + 1]).read_bytes())
        elif any(a.endswith('shell.py') for a in args):
            # the equipped map (tools/bake/shell.py): a grown grid, with the pieces kept off named
            k = next(i for i, a in enumerate(args) if a.endswith('shell.py'))
            out = Path(args[k + 2])
            out.mkdir(parents=True, exist_ok=True)
            (out / 'URB_Bar.upk').write_bytes(b'grown ' + Path(args[k + 1]).read_bytes())
            kept = [args[i + 1] for i, a in enumerate(args) if a == '--floor-off']
            (out / 'shell.json').write_text(json.dumps(dict(shelled=str(out / 'URB_Bar.upk'), brought={}, resized=dict(
                before=[52, 39, 12], grid=[60, 40, 12], ground='laid', planesLaid=2,
                **({'floorKeptOff': kept} if kept else {})))), encoding='utf-8')
        elif any(a.endswith('intro_copy.py') for a in args):
            k = next(i for i, a in enumerate(args) if a.endswith('intro_copy.py'))
            if self.landing:
                Path(args[k + 2]).write_bytes(b'intro copy of ' + Path(args[k + 1]).read_bytes())
        elif any(a.endswith('transplant.py') for a in args):
            # the edit's pieces of other maps staged in a copy of the map (tools/bake/transplant.py)
            k = next(i for i, a in enumerate(args) if a.endswith('transplant.py'))
            out, edit = Path(args[k + 2]), json.loads(Path(args[args.index('--edit') + 1]).read_text(encoding='utf-8'))
            (out / 'staged').mkdir(parents=True)
            staged = out / 'staged' / Path(args[k + 1]).name
            staged.write_bytes(b'staged ' + Path(args[k + 1]).read_bytes())
            edit['copies'] = [dict(c, actor=c['actor'] + '_900', staged=True) if c.get('donor') else c
                              for c in edit['copies']]
            (out / 'native-edit.staged.json').write_text(json.dumps(edit), encoding='utf-8')
            if not self.no_staged_report:
                (out / 'transplant.json').write_text(json.dumps(dict(
                    map=args[k + 1], staged=str(staged), foreignPieces=1, writer={},
                    donors=[dict(map='URB_PoliceStation', file='x', sha256='d' * 64, pieces=1, staged={}, objectsBrought=7,
                                 objectsReused=3, cut=[], sizes={}, bytes=1234, brought=[], newNames=2,
                                 addedImports=1)])), encoding='utf-8')
        elif '--bake' not in args and any(a.endswith('native_copy.py') for a in args):
            # a quick build's: the edit made in the map, nothing relit, no texture cache
            k = next(i for i, a in enumerate(args) if a.endswith('native_copy.py'))
            lit, variant = Path(args[k + 2]), args[k + 3]
            lit.mkdir(parents=True, exist_ok=True)
            (lit / ('%s.upk' % variant)).write_bytes(b'unbaked map of ' + Path(args[k + 1]).read_bytes())
            self.flag_fixture(args, lit, variant)
        elif self.unchanged_lighting:
            # a completed calculation that wrote no texel (relight.py's zero-write success): the edited map, no cache
            k = next(i for i, a in enumerate(args) if a.endswith('.py'))
            lit, variant = Path(args[k + 2]), args[k + 3]
            lit.mkdir(parents=True, exist_ok=True)
            (lit / ('%s.upk' % variant)).write_bytes(b'edited map, lighting unchanged')
            (lit / ('%s.relight.json' % variant)).write_text(json.dumps(dict(
                components=[], unchanged=[], skipped=[], lightingUnchanged=True, cache=None, nativeCopies=[])))
            (lit / ('%s.fixture.json' % variant)).write_text(json.dumps(dict(cache=None, lightingUnchanged=True, lights=dict(
                policy='baked', registered={}, unregistered=[], edits=[dict(op='add', created=[-301, -302])]))))
        else:
            k = next(i for i, a in enumerate(args) if a.endswith('.py'))
            lit, variant, cache = Path(args[k + 2]), args[k + 3], args[args.index('--cache') + 1]
            lit.mkdir(parents=True, exist_ok=True)
            (lit / ('%s.upk' % variant)).write_bytes(b'relit map %d' % self.relit)
            (lit / ('%s.tfc' % cache)).write_bytes(b'lightmaps')
            native = args[k].endswith('native_copy.py')
            if native:
                self.flag_fixture(args, lit, variant)
            (lit / ('%s.relight.json' % variant)).write_text(json.dumps(dict(
                components=[1, 2], unchanged=[3], skipped=[], copies=[] if native else [dict(source='X_1', triangles=5)],
                nativeCopies=[dict(copy='XComLevelActor_99', source='XComLevelActor_1')] if native else [])))

    def tool(self, name):
        return [r for r in self.ran if r[0] != 'pwsh' and any(a.endswith(name) for a in r)]

    @staticmethod
    def flag_fixture(args, lit, variant):
        """The writer's record of the native edit's flags (native_copy.py's pieceFlags section), as it writes it."""
        edit = json.loads(Path(args[args.index('--copies') + 1]).read_text(encoding='utf-8'))
        pieces, copies = edit.get('pieceFlags') or [], [c for c in edit.get('copies') or [] if c.get('flags')]
        if not (pieces or copies):
            return
        rec = lambda name, flags: dict(actor=name, applied=flags, written=[['bIgnoreFor3DCursorCollision', True, 'added']])  # noqa: E731
        (lit / ('%s.fixture.json' % variant)).write_text(json.dumps(dict(nativeCopies=dict(ladders=[], pieceFlags=dict(
            inPlace=[rec(e['name'], e['flags']) for e in pieces], onCopies=[rec(c['actor'], c['flags']) for c in copies],
            tiles=dict(regions=[dict(tiles=[1, 2, 1, 2, 1, 2], volume=900)], seeded=4) if pieces else None,
            written=len(pieces) + len(copies), refused=[])))), encoding='utf-8')

    @staticmethod
    def seed(src, dst, plan):
        dst.write_bytes(Path(src).read_bytes() + b' seeded')
        dst.with_name(dst.name + '.seeded.txt').write_text("the seeder's note")     # as seed_map.apply writes
        return 'seeded 3 tiles'

    def make(self, stamp='110000', udk=True, quick=False):
        import datetime
        now = datetime.datetime(2026, 11, 7, int(stamp[:2]), int(stamp[2:4]), int(stamp[4:]))
        return build.Build(self.project, self.tmp.name, self.output, self.lwr, self.udk if udk else None,
                           patch_work=self.work, now=now, run=self.run_tool, seed=self.seed, echo=lambda *_: None,
                           quick=quick, named=self.name_copy)

    def name_copy(self, src, dst, text):
        """The named copy's growing write (Build.named_base), as a stand-in: the map's bytes and the name added."""
        self.named = getattr(self, 'named', []) + [(str(src), str(dst), text)]
        Path(dst).write_bytes(Path(src).read_bytes() + b' +' + text.encode())

    def test_a_moved_landing_alone_is_relit(self):
        """A project whose one change moves the map's own landing: its grounded Skyranger casts a shadow, so a full
        build bakes (native_copy.py with --bake, which hands the relight the move: F-98) instead of keeping the map's
        lighting."""
        self.spec['objects'] = []
        self.spec['landingZones'] = dict(zones=[dict(id='z1', location=[1103, -1681, 64], direction='north', kind='normal',
                                                     ew=True)], own=[0], ownLandings=1)
        b = self.make()
        b._landing_moves = []       # (the intro copy's frames, read from the base map: this one is a stand-in)
        m = b.run()
        light, = self.tool('native_copy.py')
        for flag in ('--bake', '--cache', '--receivers-near'):
            self.assertIn(flag, light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(edit['landingZones']['own'], [0])
        self.assertFalse(m['lightingUnchanged'])

    def test_cover_blocks_alone_are_made_in_the_map_with_the_lighting_unchanged(self):
        """A project with nothing but cover blocks: hidden pieces change no baked light, so a full build makes the map
        as a quick build does (native_copy.py without --bake, no relight) and keeps the map's lighting; with another
        edit the blocks go to the baking writer with it."""
        block = dict(name='CoverBlock_copy1', label='CoverBlock_copy1', kind='high', location=[0, 0, 0], rotation=[0, 0, 0],
                     size=[96.0, 96.0], heights=[-12.0, 96.0], box=[0, 96, 0, 96, -12, 96])
        self.spec['objects'] = [dict(type='covers', blocks=[block])]
        m = self.make().run()
        light, = self.tool('native_copy.py')
        for flag in ('--bake', '--cache', '--receivers-near'):
            self.assertNotIn(flag, light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual((edit['copies'], edit['covers']), ([], [block]))
        self.assertEqual(self.tool('relight.py'), [])
        stage = next(s for s in m['stages'] if s['stage'] == 'light')
        self.assertEqual((stage['baked'], stage['cache'], stage['lightingUnchanged'], stage['coverBlocks']), (True, None, True, 1))
        self.assertEqual((m['cache'], m['lightingUnchanged'], m['coverBlocks'], m['quick']), (None, True, 1, False))
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('its cover blocks and invisible floors made as hidden pieces', readme)
        self.assertIn('lighting unchanged', readme)
        # with a copy as well: one baking writer for both
        self.ran.clear()
        self.spec['objects'] = [COPY, dict(type='covers', blocks=[block])]
        m = self.make(stamp='110100').run()
        light, = self.tool('native_copy.py')
        self.assertIn('--bake', light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(([c['actor'] for c in edit['copies']], edit['covers']), (['XComLevelActor_1'], [block]))

    def test_flags_alone_are_written_in_the_map_with_the_lighting_unchanged(self):
        """A project whose only change is pieces' flags (piece flags plan, 6.3): flags are settings the game reads, not
        light, so a full build makes the map as a quick build does (native_copy.py without --bake) and keeps its
        lighting; the writer's record of them is in the light stage and the manifest. The mouse alone is an edit too."""
        mouse = dict(name='XComLevelActor_9', target='TheWorld.PersistentLevel.XComLevelActor_9', flags=dict(mouse=False),
                     box=[0, 96, 0, 96, 0, 64], tiles=False, actorClass='XComLevelActor')
        self.spec['objects'] = [dict(type='pieceFlags', pieces=[mouse])]
        m = self.make().run()
        light, = self.tool('native_copy.py')
        for flag in ('--bake', '--cache', '--receivers-near'):
            self.assertNotIn(flag, light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual((edit['copies'], edit['hides'], edit['pieceFlags']), ([], [], [mouse]))
        self.assertEqual(self.tool('relight.py'), [])
        compiled = next(s for s in m['stages'] if s['stage'] == 'compile')
        self.assertEqual(compiled['pieceFlags'], 1)
        stage = next(s for s in m['stages'] if s['stage'] == 'light')
        self.assertEqual((stage['baked'], stage['cache'], stage['lightingUnchanged']), (True, None, True))
        self.assertEqual(stage['pieceFlags'], dict(inPlace=1, onCopies=0, written=1, refused=[], regions=1, seeded=4, ladders=0))
        self.assertEqual((m['cache'], m['lightingUnchanged'], m['pieceFlags']), (None, True, 1))
        # a quick build makes them the same way
        self.ran.clear()
        m = self.make(stamp='110100', quick=True).run()
        light, = self.tool('native_copy.py')
        self.assertNotIn('--bake', light)
        self.assertEqual(next(s for s in m['stages'] if s['stage'] == 'light')['pieceFlags']['inPlace'], 1)
        # with a copy: the baking writer makes both, and the copy carries its own flags
        self.ran.clear()
        self.spec['objects'] = [dict(COPY, flags=[dict(cover=False)]), dict(type='pieceFlags', pieces=[mouse])]
        m = self.make(stamp='110200').run()
        light, = self.tool('native_copy.py')
        self.assertIn('--bake', light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(([c.get('flags') for c in edit['copies']], edit['pieceFlags']), ([dict(cover=False)], [mouse]))
        compiled = next(s for s in m['stages'] if s['stage'] == 'compile')
        self.assertEqual((compiled['pieceFlags'], compiled['flagCopies']), (1, 1))
        stage = next(s for s in m['stages'] if s['stage'] == 'light')
        self.assertEqual((stage['pieceFlags']['inPlace'], stage['pieceFlags']['onCopies']), (1, 1))
        # with a grid grown: the lighting unchanged too, as cover blocks on a grown grid have it
        self.ran.clear()
        self.spec['objects'] = [dict(type='pieceFlags', pieces=[mouse])]
        self.report['stageGrid'] = [60, 40, 12]
        m = self.make(stamp='110300').run()
        light, = self.tool('native_copy.py')
        self.assertNotIn('--bake', light)
        self.assertEqual(self.tool('relight.py'), [])
        self.assertTrue(m['lightingUnchanged'])

    def test_a_grown_grid_leaves_a_piece_whose_floor_is_turned_off_as_it_is(self):
        """F-100's scenery floor on a grown grid gives way to the user's Floor off (piece flags plan, 6.2): shell.py is
        told which pieces to leave."""
        sys.path.insert(0, str(Path(build.__file__).resolve().parents[1] / 'bake'))
        import package
        import shell
        off = dict(name='XComLevelActor_13', target='TheWorld.PersistentLevel.XComLevelActor_13', flags=dict(floor=False),
                   box=[0, 96, 0, 96, 0, 4], tiles=True, actorClass='XComLevelActor')
        on = dict(off, name='XComLevelActor_14', target='TheWorld.PersistentLevel.XComLevelActor_14', flags=dict(floor=True))
        self.spec['objects'] = [dict(type='pieceFlags', pieces=[off, on])]
        self.report['stageGrid'] = [60, 40, 12]
        self.doc['stage'] = dict(grid=[60, 40])
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        with mock.patch.object(package, 'Package', lambda path: None), \
                mock.patch.object(shell, 'needs', lambda p, building=False: []):
            m = self.make().run()
        run, = self.tool('shell.py')
        self.assertEqual([run[i + 1] for i, a in enumerate(run) if a == '--floor-off'], ['XComLevelActor_13'])
        shelled = next(s for s in m['stages'] if s['stage'] == 'shell')
        self.assertEqual(shelled['grid']['floorKeptOff'], ['XComLevelActor_13'])

    def test_a_quick_build_makes_the_edit_in_the_map_without_baking_its_lighting(self):
        self.spec['objects'] = [COPY, HIDE]
        m = self.make(quick=True).run()
        light, = self.tool('native_copy.py')
        k = light.index(str(build.NATIVE_COPY))
        self.assertEqual(light[k + 1:k + 4], [str(self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk'),
                                              str(self.output / '.work' / ('%s-20261107-110000' % VARIANT) / 'lit'), VARIANT])
        for flag in ('--bake', '--cache', '--receivers-near', '--edit-spec'):
            self.assertNotIn(flag, light)
        # the same edit a full build makes (the copies and the hides), with nothing relit
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(([c['actor'] for c in edit['copies']], edit['hides']), (['XComLevelActor_1'], [NATIVE_HIDE]))
        self.assertEqual(self.tool('relight.py'), [])
        light_stage = dict(m['stages'][3])
        self.assertGreaterEqual(light_stage.pop('seconds'), 0)       # every stage says how long it took
        self.assertEqual(light_stage, dict(stage='light', cache=None, baked=False, nativeCopies=1, hidden=1))
        # no texture cache; the map as native_copy.py made it (no seed plan without a patch)
        self.assertEqual(sorted(m['files']), sorted('CookedPCConsole/%s.upk' % n for n in (VARIANT, INTRO)))
        pkg = self.output / VARIANT
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'unbaked map of ' + BASE)
        self.assertEqual((m['quick'], m['cache'], m['times']), (True, None, {'quick': m['seconds']}))
        readme = (pkg / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('%s: Test "build" | one, a variant of URB_Bar (QUICK BUILD: its lighting is not baked)' % VARIANT, readme)
        self.assertIn('its lighting NOT baked. This is a quick build', readme)
        self.assertIn('the pieces it deletes or moves taken out', readme)
        self.assertNotIn('.tfc', readme)
        # a full build's manifest says it isn't quick
        self.assertFalse(self.make('111500').run()['quick'])

    def test_pieces_of_other_maps_are_staged_in_the_map_before_the_copies_are_made(self):
        lamp = dict(COPY, labels=['XComLevelActor_15_copy1'], donors=[dict(package='URB_PoliceStation', sha256='d' * 64)],
                    **{'from': ['XComLevelActor_15']})
        self.spec['objects'] = [COPY, lamp]
        m = self.make(quick=True).run()
        work = self.output / '.work' / ('%s-20261107-110000' % VARIANT)
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        staging, = self.tool('transplant.py')
        k = staging.index(str(build.TRANSPLANT))
        self.assertEqual(staging[k + 1:], [str(cooked / 'URB_Bar.upk'), str(work / 'transplant'), '--edit',
                                           str(work / 'native-edit.json'), '--cooked', str(cooked)])
        # the copier reads the staged map and the edit that names the staged actors
        light, = self.tool('native_copy.py')
        k = light.index(str(build.NATIVE_COPY))
        self.assertEqual(light[k + 1], str(work / 'transplant' / 'staged' / 'URB_Bar.upk'))
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual([(c['actor'], c.get('staged')) for c in edit['copies']],
                         [('XComLevelActor_1', None), ('XComLevelActor_15_900', True)])
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'unbaked map of staged ' + BASE)
        self.assertEqual([s['stage'] for s in m['stages']], ['snapshot', 'compile', 'patch', 'transplant', 'light', 'seeds'])
        self.assertEqual(m['stages'][1]['foreignCopies'], 1)       # the page shows the stage's step from the compile on
        self.assertEqual((m['foreignPieces'], m['donors']),
                         (1, [dict(map='URB_PoliceStation', sha256='d' * 64, file='x', pieces=1, objectsBrought=7,
                                   objectsReused=3, cut=[], bytes=1234)]))
        # a full build: the same staging, and the baking copier reads the staged map (it lights them from nothing)
        self.ran.clear()
        m = self.make('110500').run()
        work = self.output / '.work' / ('%s-20261107-110500' % VARIANT)
        self.assertEqual(len(self.tool('transplant.py')), 1)
        light, = self.tool('native_copy.py')
        k = light.index(str(build.NATIVE_COPY))
        self.assertEqual(light[k + 1], str(work / 'transplant' / 'staged' / 'URB_Bar.upk'))
        self.assertIn('--bake', light)
        self.assertEqual(light[light.index('--copies') + 1], str(work / 'transplant' / 'native-edit.staged.json'))
        self.assertEqual((m['quick'], m['foreignPieces']), (False, 1))
        # a transplanter that staged nothing fails the build
        self.no_staged_report = True
        with self.assertRaises(build.BuildError) as raised:
            self.make('111000', quick=True).run()
        self.assertIn('staged no map', str(raised.exception))

    def test_a_build_without_pieces_of_other_maps_stages_nothing(self):
        self.spec['objects'] = [COPY, HIDE]
        m = self.make(quick=True).run()
        self.assertEqual(self.tool('transplant.py'), [])
        self.assertEqual((m['foreignPieces'], m['donors']), (0, []))
        self.assertNotIn('transplant', [s['stage'] for s in m['stages']])
        self.assertNotIn('foreignCopies', m['stages'][1])

    def test_a_quick_build_of_an_edit_only_a_patch_makes_ships_the_base_map_renamed(self):
        self.spec['objects'] = [DOOR]
        m = self.make(quick=True).run()
        self.assertEqual([r[4] for r in self.ran if r[0] == 'pwsh'], ['build', 'cook'])
        self.assertEqual((self.tool('native_copy.py'), self.tool('relight.py')), ([], []))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), BASE + b' seeded')
        self.assertEqual(m['streams'], [PATCH])

    def test_each_kind_of_build_keeps_the_other_kinds_last_time(self):
        full = self.make('110000').run()
        self.assertEqual(full['times'], {'full': full['seconds']})
        quick = self.make('111000', quick=True).run()
        self.assertEqual(quick['times'], {'full': full['seconds'], 'quick': quick['seconds']})
        manifest = self.output / VARIANT / 'manifest.json'
        m = json.loads(manifest.read_text(encoding='utf-8'))
        m['times'] = {'full': 600, 'quick': 7}
        manifest.write_text(json.dumps(m), encoding='utf-8')
        again = self.make('112000').run()
        self.assertEqual(again['times'], {'full': again['seconds'], 'quick': 7})
        # a package from before quick builds was a full one; another project's says nothing
        self.assertEqual(build.last_times(manifest, '0000-test'), {'full': again['seconds'], 'quick': 7})
        manifest.write_text(json.dumps(dict(project=dict(id='0000-test'), seconds=268)), encoding='utf-8')
        self.assertEqual(build.last_times(manifest, '0000-test'), {'full': 268})
        self.assertEqual(build.last_times(manifest, 'another'), {})
        self.assertEqual(build.last_times(manifest.with_name('none.json'), '0000-test'), {})

    def test_a_moved_ladders_helper_leaves_the_variants_copy_of_its_patch(self):
        # the compiler's streamHides (a ladder's hidden helper in patch_bar): the Build ships patch_bar_<variant>
        # without it, streamed in patch_bar's place, and passes --family through to the compiler
        (self.lwr / 'XEW/XComGame/CookedPCConsole/patch_bar.upk').write_bytes(b'the bar patch')
        self.spec = dict(self.spec, objects=[COPY], streamHides={'patch_bar': ['XComLadder_11']})
        seen = []
        compiler.compile_project = lambda doc, scene, enable=(), library=None, foreign=(): (seen.append(enable), (self.spec, dict(self.report)))[1]
        b = self.make()
        b.enable = ('frameless-door',)
        m = b.run()
        copy = 'patch_bar_%s' % VARIANT
        self.assertEqual(seen, [('frameless-door',)])
        self.assertEqual(m['families'], ['frameless-door'])
        self.assertEqual(m['streamCopies'], [dict(stream='patch_bar', copy=copy, hidden=['XComLadder_11'])])
        self.assertEqual(m['replaceStreams'], {'CIN_DropshipIntros': INTRO, 'patch_bar': copy})
        self.assertIn('CookedPCConsole/%s.upk' % copy, m['files'])
        run, = self.tool('stream_copy.py')
        self.assertEqual(run[run.index('--hide') + 1], 'XComLadder_11')
        line, = m['config']['maps']
        self.assertIn('MapName="%s"' % copy, line)
        self.assertNotIn('MapName="patch_bar"', line)
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % copy)).read_bytes(), b'stream copy of the bar patch')

    def test_a_missions_moved_objects_ship_in_a_copy_of_its_stream_for_that_mission_only(self):
        # mission types plan, Part E: the compiler's streamMoves; the Build copies the stream with the moves (and the map
        # switches naming the variant), ships it, streams it in the data recovery's record alone, and hands the base
        # map's tiles under the moved solid piece to native_copy.py (streamTiles)
        bar = record('bar')
        cnh = build.set_field(build.add_stream(bar, 'URB_Bar_CNH')[0], 'MissionType', 'eMission_CaptureAndHold', quoted=False)
        cfg = self.lwr / 'XEW/XComGame/Config'
        (cfg / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n%s\r\n%s\r\n' % (bar, cnh)).encode('latin-1'))
        (self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar_CNH.upk').write_bytes(b'the data recovery stream')
        move = dict(actor='XComCapturePointVolume_0', location=[96.0, 0.0, 0.0], rotation=[0, 0, 0],
                    old=dict(location=[0.0, 0.0, 0.0], rotation=[0, 0, 0]), kind='capturePoint', group='capture:XComCapturePointVolume_0')
        self.spec = dict(self.spec, objects=[COPY], streamMoves={'URB_Bar_CNH': [move]})
        compiler.compile_project = lambda doc, scene, enable=(), library=None, foreign=(): (self.spec, dict(self.report))
        tiles = [dict(actor='XComLevelActor_6', old=[0, 10, 0, 10, 0, 10], new=[96, 106, 0, 10, 0, 10])]
        with mock.patch.object(build.Build, 'stream_tile_boxes', lambda b: [dict(stream='URB_Bar_CNH', **t) for t in tiles]):
            m = self.make().run()
        copy = 'URB_Bar_CNH_%s' % VARIANT
        self.assertEqual(m['streamCopies'], [dict(stream='URB_Bar_CNH', copy=copy, hidden=[], moved=['XComCapturePointVolume_0'])])
        self.assertIn('CookedPCConsole/%s.upk' % copy, m['files'])
        run, = self.tool('stream_copy.py')
        self.assertNotIn('--hide', run)
        self.assertEqual(run[run.index('--base') + 1:run.index('--base') + 4], ['URB_Bar', '--variant', VARIANT])
        listed = json.loads(Path(run[run.index('--moves') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(listed, [dict(actor='XComCapturePointVolume_0', location=[96.0, 0.0, 0.0], rotation=[0, 0, 0])])
        abduction, recovery = m['config']['maps']
        self.assertIn('MapName="%s"' % copy, recovery)
        self.assertNotIn('MapName="URB_Bar_CNH"', recovery)
        self.assertNotIn(copy, abduction)
        native = json.loads(next((self.output / '.work').glob('%s-*/native-edit.json' % VARIANT)).read_text(encoding='utf-8'))
        self.assertEqual(native['streamTiles'], [dict(stream='URB_Bar_CNH', **tiles[0])])
        self.assertEqual(native['streamMoves'], {'URB_Bar_CNH': [move]})

    def test_a_build_makes_the_variant_package(self):
        m = self.make().run()
        pkg = self.output / VARIANT
        cache = build.cache_name(VARIANT)
        self.assertEqual(sorted(m['files']), sorted('CookedPCConsole/%s' % n for n in
                                                    ('%s.upk' % VARIANT, '%s.upk' % PATCH, '%s.tfc' % cache,
                                                     '%s.upk' % INTRO)))
        # the variant's own landing intro, streamed in place of CIN_DropshipIntros
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % INTRO)).read_bytes(), b'intro copy of the landing intros')
        self.assertEqual((m['intros'], m['replaceStreams']), ([dict(stream='CIN_DropshipIntros', copy=INTRO)],
                                                              {'CIN_DropshipIntros': INTRO}))
        self.assertIn('StreamingMaps[0]=( MapName="%s"' % INTRO, m['config']['maps'][0])
        intro, = self.tool('intro_copy.py')
        k = intro.index(str(build.INTRO_COPY))
        self.assertEqual(intro[k + 1:k + 5], [str(self.lwr / 'XEW/XComGame/CookedPCConsole/CIN_DropshipIntros.upk'),
                                               str(pkg.parent / '.work' / ('%s-20261107-110000' % VARIANT) / 'package' /
                                                   'CookedPCConsole' / ('%s.upk' % INTRO)), 'URB_Bar', VARIANT])
        self.assertIn('tools/bake/intro_copy.py', m['tools'])
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'relit map 1 seeded')
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % PATCH)).read_bytes(), b'cooked patch')
        for rel, digest in m['files'].items():
            self.assertEqual(build.sha256(pkg / rel), digest)
        on_disk = json.loads((pkg / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(on_disk, json.loads(json.dumps(m)))
        self.assertEqual(m['schema'], build.SCHEMA)
        self.assertEqual(m['buildId'], '%s-20261107-110000' % VARIANT)
        self.assertEqual(m['streams'], [PATCH])
        self.assertEqual((m['project']['id'], m['project']['revision']), ('0000-test', 3))
        self.assertEqual(m['source']['sha256'], hashlib.sha256(BASE).hexdigest())
        self.assertEqual([s['stage'] for s in m['stages']], ['snapshot', 'compile', 'patch', 'light', 'seeds'])
        self.assertIn('DisplayName="%s (Test build  one) |0"' % VARIANT, m['config']['maps'][0])
        readme = (pkg / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn(m['config']['maps'][0], readme)
        self.assertIn('LZArray=(MapName="%s"' % VARIANT, readme)
        self.assertIn('its copies made as pieces of the map', readme)
        self.assertIn('the pieces it deletes or moves taken out', readme)
        self.assertIn('%s.upk is the rest of the edit' % PATCH, readme)
        self.assertIn('%s.upk is the landing intro (CIN_DropshipIntros) with URB_Bar\'s landing' % INTRO, readme)
        self.assertIn('streams %s in place of CIN_DropshipIntros' % INTRO, readme)
        self.assertNotIn('\n', readme.replace('\r\n', ''))
        self.assertEqual(sorted(str(p.relative_to(pkg).as_posix()) for p in pkg.rglob('*') if p.is_file()),
                         sorted(['manifest.json', 'README.txt'] + list(m['files'])))
        self.assertFalse((self.output / ('%s.zip' % VARIANT)).exists())      # no zip beside it
        # the stream-only spec without the copy went to patchtool and relight, patchtool with -Force and its work
        # folder; the copy is made in the map
        spec = json.loads(Path(m['stages'][1]['spec']).read_text(encoding='utf-8'))
        self.assertTrue(spec['map']['seedExternally'])
        self.assertNotIn('shipAs', spec['map'])
        self.assertEqual(spec['objects'], [DOOR])
        self.assertEqual((m['stages'][1]['nativeCopies'], m['stages'][1]['copierCopies'], m['stages'][1]['hides'],
                          m['stages'][1]['patchHides']), (1, 1, 1, 0))
        self.assertEqual((m['nativeCopies'], m['nativeHides']), (1, 1))
        self.assertIn('tools/bake/native_copy.py', m['tools'])
        self.assertEqual(on_disk['stages'][3]['nativeCopies'], [['XComLevelActor_99', 'XComLevelActor_1']])
        pw = [r for r in self.ran if r[0] == 'pwsh']
        self.assertEqual([r[4] for r in pw], ['build', 'cook'])
        self.assertIn('-Force', pw[0])
        self.assertEqual(pw[0][pw[0].index('-Work') + 1], str(self.work))
        self.assertEqual(pw[0][pw[0].index('-Lwr') + 1], str(self.lwr))
        self.assertEqual(self.tool('relight.py'), [])
        light, = self.tool('native_copy.py')
        k = next(i for i, a in enumerate(light) if a.endswith('native_copy.py'))
        self.assertEqual(light[k + 1], str(self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk'))
        self.assertIn('-u', light[:k])         # its output streams, for the editor's build progress
        self.assertIn('--bake', light)
        self.assertEqual(light[light.index('--receivers-near') + 1], '1024')
        self.assertEqual(light[light.index('--edit-spec') + 1], m['stages'][1]['spec'])
        copies = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual(copies, dict(copies=[dict(actor='XComLevelActor_1', location=[1, 2, 0], rotation=[0, 16384, 0],
                                                   label='XComLevelActor_1_copy1', box=[0, 1, 0, 1, 0, 1])],
                                      breakOriginals=[], hides=[NATIVE_HIDE]))

    def test_an_intro_without_a_landing_for_the_map_is_streamed_as_it_is(self):
        self.landing = False
        m = self.make().run()
        self.assertEqual((m['intros'], m['replaceStreams']), ([], {}))
        self.assertNotIn('CookedPCConsole/%s.upk' % INTRO, m['files'])
        self.assertIn('StreamingMaps[0]=( MapName="CIN_DropshipIntros"', m['config']['maps'][0])

    def test_a_map_with_missions_that_land_differently_gets_an_intro_copy_for_each(self):
        bar = record('bar')
        terror = build.set_field(bar.replace('CIN_DropshipIntros', 'CIN_FastropeIntros'), 'MissionType',
                                 'eMission_TerrorSite', quoted=False)
        cfg = self.lwr / 'XEW/XComGame/Config'
        (cfg / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n%s\r\n%s\r\n' % (bar, terror)).encode('latin-1'))
        (self.lwr / 'XEW/XComGame/CookedPCConsole/CIN_FastropeIntros.upk').write_bytes(b'the fast-rope intros')
        m = self.make().run()
        fastrope = 'CIN_FastropeIntros_%s' % VARIANT
        self.assertEqual(m['replaceStreams'], {'CIN_DropshipIntros': INTRO, 'CIN_FastropeIntros': fastrope})
        self.assertEqual(len(self.tool('intro_copy.py')), 2)
        self.assertIn('CookedPCConsole/%s.upk' % fastrope, m['files'])
        self.assertEqual(m['config']['missions'], ['Abduction', 'Terror'])
        self.assertIn('DisplayName="%s (Test build  one, Terror) |0"' % VARIANT, m['config']['maps'][1])
        self.assertIn('MapName="%s"' % fastrope, m['config']['maps'][1])
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('one record for each mission URB_Bar serves (Abduction, Terror)', readme)
        self.assertTrue(all(line in readme for line in m['config']['maps']))

    def test_an_alien_base_gets_its_own_entrance_intro(self):
        # F-76: CIN_TP05A_EnteringAlienBase switches on the map's name, as the landings do; a variant streams its copy
        base = record('alienbase01')
        cfg = self.lwr / 'XEW/XComGame/Config'
        (cfg / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n%s\r\n' % base.replace(
            'Name="AlienBase01"', 'Name="URB_Bar"')).encode('latin-1'))
        (self.lwr / 'XEW/XComGame/CookedPCConsole/CIN_TP05A_EnteringAlienBase.upk').write_bytes(b'the entrance')
        m = self.make().run()
        entrance = 'CIN_TP05A_EnteringAlienBase_%s' % VARIANT
        self.assertEqual(m['replaceStreams'], {'CIN_TP05A_EnteringAlienBase': entrance})
        self.assertEqual(m['intros'], [dict(stream='CIN_TP05A_EnteringAlienBase', copy=entrance)])
        intro, = self.tool('intro_copy.py')
        k = intro.index(str(build.INTRO_COPY))
        self.assertEqual((intro[k + 1], intro[k + 3:k + 5]),
                         (str(self.lwr / 'XEW/XComGame/CookedPCConsole/CIN_TP05A_EnteringAlienBase.upk'), ['URB_Bar', VARIANT]))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % entrance)).read_bytes(),
                         b'intro copy of the entrance')
        line, = m['config']['maps']
        self.assertIn('StreamingMaps[0]=( MapName="%s"' % entrance, line)
        self.assertNotIn('MapName="CIN_TP05A_EnteringAlienBase"', line)
        self.assertIn('MissionType=eMission_AlienBase', line)
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('%s.upk is the intro (CIN_TP05A_EnteringAlienBase) with URB_Bar\'s scene' % entrance, readme)
        self.assertNotIn('Skyranger', readme)

    def test_copies_alone_build_no_patch_and_stream_none(self):
        self.spec['objects'] = [COPY]
        m = self.make().run()
        self.assertEqual([r for r in self.ran if r[0] == 'pwsh'], [])
        self.assertEqual(m['stages'][2]['stage'], 'patch')
        self.assertIn('skipped', m['stages'][2])
        cache = build.cache_name(VARIANT)
        self.assertEqual(sorted(m['files']), sorted('CookedPCConsole/%s' % n for n in ('%s.upk' % VARIANT, '%s.tfc' % cache,
                                                                                    '%s.upk' % INTRO)))
        self.assertEqual((m['patch'], m['streams'], m['config']['streamSlots']), (None, [], [None]))
        self.assertEqual(m['config']['maps'][0].count('StreamingMaps['), record('bar').count('StreamingMaps['))
        light, = self.tool('native_copy.py')
        self.assertNotIn('--edit-spec', light)
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('(out of rotation; streams %s in place of CIN_DropshipIntros):' % INTRO, readme)
        self.assertNotIn(PATCH, readme)
        # no seed plan without a patch: native_copy.py seeds the copies' tiles itself
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'relit map 1')

    def test_hides_alone_are_made_in_the_map_with_no_patch(self):
        self.spec['objects'] = [HIDE]
        m = self.make().run()
        self.assertEqual([r for r in self.ran if r[0] == 'pwsh'], [])
        light, = self.tool('native_copy.py')
        self.assertNotIn('--edit-spec', light)
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual((edit['copies'], edit['hides']), ([], [NATIVE_HIDE]))
        self.assertEqual((m['nativeCopies'], m['nativeHides'], m['streams']), (0, 1, []))
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertNotIn('its copies made as pieces of the map', readme)
        self.assertIn('the pieces it deletes or moves taken out', readme)

    def test_groups_that_break_together_go_native_with_their_pieces_left_in_place(self):
        grouped = dict(COPY, breakGroups=[1], breakOriginals=[dict(name='XComDestructibleActor_61', group=1)],
                       classes=['XComDestructibleActor'])
        self.spec['objects'] = [grouped, HIDE]
        m = self.make().run()
        light, = self.tool('native_copy.py')
        copies = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual([c.get('breakGroup') for c in copies['copies']], [1])
        self.assertEqual(copies['breakOriginals'], [dict(name='XComDestructibleActor_61', group=1)])
        self.assertEqual(m['stages'][1]['nativeBreakGroups'], 1)
        spec = json.loads(Path(m['stages'][1]['spec']).read_text(encoding='utf-8'))
        self.assertEqual(spec['objects'], [])
        self.assertEqual(m['streams'], [])

    def test_a_plain_ew_install_builds_without_long_wars_files(self):
        # plain Enemy Within: no DefaultLZMutator.ini or DefaultMiniMods.ini, display names without LWR's " |0"
        cfg = self.lwr / 'XEW/XComGame/Config'
        (cfg / 'DefaultLZMutator.ini').unlink()
        (cfg / 'DefaultMiniMods.ini').unlink()
        plain = record('bar').replace(' |0"', '"')
        self.assertNotEqual(plain, record('bar'))
        (cfg / 'DefaultMaps.ini').write_bytes(('[XComGame.XComMapManager]\r\n%s\r\n' % plain).encode('latin-1'))
        self.spec['objects'] = [COPY]
        m = self.make(udk=False).run()
        self.assertEqual((m['config']['landingZones'], m['config']['miniMods']), (None, None))
        line, = m['config']['maps']
        self.assertRegex(line, r'DisplayName="%s \([^"|]*\)"' % VARIANT)
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertNotIn('DefaultLZMutator', readme)
        self.assertNotIn('DefaultMiniMods', readme)
        self.assertIn(line, readme)
        # the editor's version, and how to play it by hand: rotation on, the original's off
        self.assertEqual(m['editorVersion'], build.VERSION)
        self.assertIn('Built by the XCOM Map Workshop %s from project' % build.VERSION, readme)
        self.assertIn('set bInRotation=True on the records', readme)
        self.assertIn('the lines with Name="URB_Bar" in DefaultMaps.ini', readme)

    def test_without_udk_an_edit_made_in_the_map_builds(self):
        self.spec['objects'] = [COPY]
        m = self.make(udk=False).run()
        self.assertIn('skipped', m['stages'][2])
        self.assertEqual([r for r in self.ran if r[0] == 'pwsh'], [])

    def test_without_udk_an_edit_that_needs_a_patch_is_refused_saying_so(self):
        self.spec['objects'] = [DOOR]
        with self.assertRaisesRegex(build.BuildError, 'needs a patch cooked in UDK, and the udk setting is not set'):
            self.make(udk=False).run()
        self.assertEqual([r for r in self.ran if r[0] == 'pwsh'], [])

    def test_the_copiers_copies_stay_in_the_patch(self):
        self.spec['objects'] = [DOOR]
        m = self.make().run()
        spec = json.loads(Path(m['stages'][1]['spec']).read_text(encoding='utf-8'))
        self.assertEqual(spec['objects'], [DOOR])
        self.assertEqual([r[4] for r in self.ran if r[0] == 'pwsh'], ['build', 'cook'])
        self.assertEqual(len(self.tool('relight.py')), 1)
        self.assertEqual(m['streams'], [PATCH])
        # output names plan 4: the relight alone reads a named copy of the map in the work folder (the cache's name
        # added to its table by a growing write), never the install's file, and the copy reads the install's caches
        light, = self.tool('relight.py')
        work = Path(m['work'])
        k = next(i for i, a in enumerate(light) if a.endswith('relight.py'))
        self.assertEqual(Path(light[k + 1]), work / 'named' / 'URB_Bar.upk')
        self.assertEqual(light[light.index('--cache') + 1], VARIANT + '_Lighting')
        self.assertEqual(self.named, [(str(self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk'),
                                       str(work / 'named' / 'URB_Bar.upk'), VARIANT + '_Lighting')])
        self.assertEqual((work / 'named' / 'tfc-folder.txt').read_text(encoding='utf-8').strip(),
                         str((self.lwr / 'XEW/XComGame/CookedPCConsole').resolve()))
        self.assertEqual((self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk').read_bytes(), BASE)
        self.assertEqual(m['cache'], VARIANT + '_Lighting')
        self.assertIn('CookedPCConsole/%s_Lighting.tfc' % VARIANT, m['files'])

    def test_a_collectibles_copy_is_made_in_the_map(self):
        collectible = dict(COPY, labels=['XComCollectible_10_copy2'], classes=['XComCollectible'],
                           **{'from': ['XComCollectible_10']})
        self.spec['objects'] = [collectible]
        m = self.make().run()
        self.assertEqual((m['nativeCopies'], m['streams']), (1, []))

    def test_a_project_that_changes_nothing_is_refused(self):
        self.spec['objects'] = []
        with self.assertRaisesRegex(build.BuildError, 'changes nothing'):
            self.make().run()
        self.assertEqual(self.ran, [])

    def test_patchtool_works_in_the_builds_folder_by_default(self):
        import datetime
        b = build.Build(self.project, self.tmp.name, self.output, self.lwr, self.udk, now=datetime.datetime(2026, 11, 7),
                        run=self.run_tool, seed=self.seed, echo=lambda *_: None)
        self.assertEqual(b.patch_work, self.output / '.work' / 'patchtool')

    def test_a_rebuild_replaces_the_package(self):
        self.make('110000').run()
        (self.output / ('%s.zip' % VARIANT)).write_bytes(b'an earlier version\'s zip of the folder')
        self.relit = 2
        m = self.make('111500').run()
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'relit map 2 seeded')
        self.assertEqual(json.loads((self.output / VARIANT / 'manifest.json').read_text())['buildId'], m['buildId'])
        self.assertEqual([p.name for p in self.output.iterdir() if not p.name.startswith('.')], [VARIANT])

    def foreign_build(self, name=VARIANT, project='1111-other', files=()):
        """A folder in the builds folder: another project's build (its manifest names `project`), or with project
        None a folder with no manifest."""
        folder = self.output / name
        (folder / 'CookedPCConsole').mkdir(parents=True)
        (folder / 'CookedPCConsole' / 'kept.upk').write_bytes(b'theirs')
        if project:
            (folder / 'manifest.json').write_text(json.dumps(dict(
                schema=build.SCHEMA, schemaVersion=1, variant=name, project=dict(id=project, name='Someone else'),
                files={'CookedPCConsole/%s' % f: 'x' for f in files})), encoding='utf-8')
        return folder

    def test_a_build_never_replaces_a_folder_that_is_not_its_projects(self):
        """Output names plan 3.4: the builds folder's package of the variant's name is replaced only when its manifest
        names this project; a folder with no manifest, a malformed one, another project's or one named in another
        case is refused before anything is built, and stays as it was."""
        for name, project in ((VARIANT, None), (VARIANT, '1111-other'), (VARIANT.lower(), '1111-other'), (VARIANT, '')):
            with self.subTest(name=name, project=project):
                folder = self.foreign_build(name, project)
                if project == '':
                    (folder / 'manifest.json').write_text('{not json', encoding='utf-8')
                before = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
                self.ran = []
                with self.assertRaisesRegex(build.BuildError, 'is (the build of another project|no build of this project)'):
                    self.make().run()
                self.assertEqual(self.ran, [])      # refused before any tool ran
                self.assertEqual({p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}, before)
                import shutil
                shutil.rmtree(folder)
        # the command line refuses the same
        self.foreign_build(VARIANT, '1111-other')
        with mock.patch.object(build.settings_module, 'load_settings', return_value=dict(
                game=self.lwr, udk=None, cache=self.tmp.name, output=self.output, projects=self.project.parent, install=None)), \
                mock.patch.object(build.settings_module, 'resolve_game', return_value=(self.lwr, None)), \
                mock.patch('builtins.print') as said:
            self.assertEqual(build.main([str(self.project)]), 1)
        self.assertIn('the build of another project', said.call_args_list[-1].args[0])

    def test_the_names_a_build_writes_must_be_free_for_its_project(self):
        """Output names plan 3.4: every name the build may write (the map, its patch, its texture cache, its intro and
        stream copies) is checked against other projects, other builds and the game install before the costly
        stages, and again as the package goes in."""
        self.spec['objects'] = [COPY, HIDE]
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        cases = [
            ('another build lists the intro copy', lambda: self.foreign_build('Other_Variant', files=['%s.upk' % INTRO])),
            ('the install has the intro copy', lambda: (cooked / ('%s.upk' % INTRO)).write_bytes(b'by hand')),
            ('the install has the cache in another case', lambda: (cooked / ('%s_lighting.tfc' % VARIANT.lower())).write_bytes(b'x')),
            ('another project has the same names', lambda: (self.project.parent / 'copy.json').write_text(
                json.dumps(dict(self.doc, id='2222-copy', name='A copy')), encoding='utf-8')),
        ]
        for what, make in cases:
            with self.subTest(what):
                make()
                self.ran = []
                with self.assertRaisesRegex(build.BuildError, 'the build would write names that are taken'):
                    self.make().run()
                self.assertFalse(self.tool('native_copy.py'))
                self.assertFalse((self.output / VARIANT).exists())
                import shutil
                for p in [self.output / 'Other_Variant', cooked / ('%s.upk' % INTRO), cooked / ('%s_lighting.tfc' % VARIANT.lower()),
                          self.project.parent / 'copy.json']:
                    shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
        # a quick build writes no cache: a file of the cache's name doesn't stop it
        (cooked / ('%s_Lighting.tfc' % VARIANT)).write_bytes(b'x')
        self.make(quick=True).run()
        self.assertTrue((self.output / VARIANT / 'manifest.json').is_file())
        # what the editor installed for this project (its ledger says whose) is its own
        (cooked / ('%s_Lighting.tfc' % VARIANT)).unlink()
        import installs
        (cooked / ('%s.upk' % VARIANT)).write_bytes(b'installed earlier')
        installs.write_ledger(self.lwr, dict(playFiles={'%s.upk' % VARIANT: 'h'}, owners={'%s.upk' % VARIANT: self.doc['id']}))
        self.make('111500').run()
        installs.write_ledger(self.lwr, dict(playFiles={'%s.upk' % VARIANT: 'h'}, owners={'%s.upk' % VARIANT: 'someone'}))
        with self.assertRaisesRegex(build.BuildError, 'installed by the editor'):
            self.make('112000').run()
        # a ledger from before owners were noted: left to the install step
        installs.write_ledger(self.lwr, dict(playFiles={'%s.upk' % VARIANT: 'h'}))
        self.make('112500').run()

    def test_a_package_of_before_rebuilds_with_the_named_cache_and_quick_builds_have_none(self):
        """Output names plan 4: a project's package built with Lighting_<n> (before 16 November 2026) is replaced by
        one with <Variant>_Lighting.tfc; a quick build in between has no cache; the next full build has it again."""
        self.spec['objects'] = [COPY, HIDE]
        old = self.foreign_build(VARIANT, self.doc['id'], files=['%s.upk' % VARIANT, 'Lighting_4242.tfc'])
        m = json.loads((old / 'manifest.json').read_text(encoding='utf-8'))
        (old / 'manifest.json').write_text(json.dumps(dict(m, cache='Lighting_4242')), encoding='utf-8')
        caches = []
        for stamp, quick in (('110000', False), ('111000', True), ('112000', False)):
            m = self.make(stamp, quick=quick).run()
            caches.append((m['cache'], sorted(Path(f).name for f in m['files'] if f.endswith('.tfc'))))
        named = VARIANT + '_Lighting'
        self.assertEqual(caches, [(named, [named + '.tfc']), (None, []), (named, [named + '.tfc'])])
        self.assertFalse((self.output / VARIANT / 'CookedPCConsole' / 'Lighting_4242.tfc').exists())
        self.assertIn('lightmaps are in %s.tfc' % named, (self.output / VARIANT / 'README.txt').read_text(encoding='latin-1'))

    def test_a_package_that_cannot_be_put_in_place_leaves_the_last_one(self):
        """Output names plan 3.4: the swap is undone when the new folder can't take the old one's place."""
        first = self.make('110000').run()
        real = Path.rename

        def rename(path, target):
            if Path(path).name == 'package':
                raise OSError('held open')
            return real(path, target)
        with mock.patch.object(Path, 'rename', rename):
            with self.assertRaisesRegex(build.BuildError, 'could not be put in place'):
                self.make('111500').run()
        self.assertEqual(json.loads((self.output / VARIANT / 'manifest.json').read_text())['buildId'], first['buildId'])
        self.assertFalse((self.output / '.work' / 'locks' / ('%s.lock' % VARIANT.lower())).exists())

    def test_a_baked_build_keeps_its_pieces_for_the_next_and_names_the_base_map(self):
        """Faster-bake plan, 3.7: the relight is told where this variant's relit pieces are kept, and what map they
        were made on."""
        self.spec['objects'] = [COPY, HIDE]
        self.make().run()
        light, = self.tool('native_copy.py')
        self.assertEqual(light[light.index('--piece-cache') + 1], str(self.output / '.work' / 'pieces' / VARIANT))
        self.assertEqual(light[light.index('--base') + 1], hashlib.sha256(BASE).hexdigest())
        self.make('111500', quick=True).run()
        self.assertNotIn('--piece-cache', self.tool('native_copy.py')[1])

    def test_old_work_folders_keep_only_their_logs_and_small_records(self):
        """Faster-bake plan, 6.1: a variant's three newest work folders stay whole; older ones lose their heavy
        files. Another variant's count apart, and folders that are no build's are left."""
        work = self.output / '.work'
        for stamp in ('20261101-100000', '20261102-100000', '20261103-100000'):
            old = work / ('%s-%s' % (VARIANT, stamp))
            (old / 'lit' / 'grown').mkdir(parents=True)
            (old / 'lit' / 'grown' / 'URB_Bar.upk').write_bytes(b'x' * 10)
            (old / 'logs').mkdir()
            (old / 'logs' / 'native-copy.log').write_text('log')
            (old / 'compile-report.json').write_text('{}')
            (old / 'big.bin').write_bytes(bytes(2 << 20))
        other = work / 'Other_Variant_1-20261101-100000' / 'lit'
        other.mkdir(parents=True)
        (work / 'pieces' / VARIANT).mkdir(parents=True)
        (work / 'pieces' / VARIANT / 'kept.npz').write_bytes(b'kept')
        self.make('110000').run()       # the fourth: the oldest is pruned
        oldest = work / ('%s-20261101-100000' % VARIANT)
        self.assertEqual(sorted(f.name for f in oldest.iterdir()), ['compile-report.json', 'logs'])
        self.assertTrue((oldest / 'logs' / 'native-copy.log').is_file())
        self.assertTrue((work / ('%s-20261102-100000' % VARIANT) / 'lit' / 'grown' / 'URB_Bar.upk').is_file())
        self.assertTrue(other.is_dir())
        self.assertTrue((work / 'pieces' / VARIANT / 'kept.npz').is_file())

    def test_a_failed_build_leaves_the_last_good_package(self):
        first = self.make('110000').run()
        self.failing = 'native_copy'
        with self.assertRaises(build.BuildError):
            self.make('112000').run()
        self.assertEqual(json.loads((self.output / VARIANT / 'manifest.json').read_text())['buildId'], first['buildId'])

    def failing_once(self, tool):
        """The first run of `tool` fails; later ones go through."""
        runs, plain = [], Builds.run_tool.__get__(self)

        def run(args, log):
            mine = any(tool in str(a) for a in args)
            self.failing = tool if mine and not runs else None
            if mine:
                runs.append(1)
            return plain(args, log)
        self.run_tool = run

    def test_untried_pieces_the_build_cannot_make_are_left_out_and_the_rest_is_built(self):
        # (the user, 14 November 2026: warn and build what our own gates held back. The compiler marks such a copy
        # untried; when the copy stage fails with one in the edit, the Build takes them out and builds the rest)
        tried = dict(COPY, untried=[False])
        untried = dict(COPY, labels=['move:SkeletalMeshActor_30'], classes=['SkeletalMeshActor'], untried=[True],
                       **{'from': ['SkeletalMeshActor_30']})
        moved = dict(HIDE, alsoHide=['SkeletalMeshActor_30'], labels=['move:SkeletalMeshActor_30'])
        self.spec['objects'] = [tried, untried, moved]
        self.failing_once('native_copy')
        m = self.make().run()
        first, second = self.tool('native_copy.py')
        edit = json.loads(Path(second[second.index('--copies') + 1]).read_text(encoding='utf-8'))
        # the tried copy is still made; the untried move is gone with its hide, so the piece stays where the map has it
        self.assertEqual(([c['label'] for c in edit['copies']], edit['hides']), (['XComLevelActor_1_copy1'], []))
        stage = next(s for s in m['stages'] if s['stage'] == 'leftout')
        self.assertEqual((stage['count'], [p['code'] for p in stage['pieces']], stage['pieces'][0]['actor']),
                         (1, ['untried-failed'], 'SkeletalMeshActor_30'))
        self.assertIn('stays where the map has it', stage['pieces'][0]['message'])
        self.assertEqual([row['code'] for row in m['leftOut']], ['untried-failed'])
        self.assertTrue((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).exists())

    def test_a_failure_with_no_untried_piece_is_the_builds_and_one_with_nothing_else_says_so(self):
        self.spec['objects'] = [dict(COPY, untried=[False])]
        self.failing_once('native_copy')
        with self.assertRaises(build.BuildError):
            self.make('110000').run()
        self.assertEqual(len(self.tool('native_copy.py')), 1)
        # an edit of untried pieces alone: nothing is left to build
        self.ran.clear()
        self.spec['objects'] = [dict(COPY, untried=[True])]
        self.failing_once('native_copy')
        with self.assertRaises(build.BuildError) as caught:
            self.make('112000').run()
        self.assertIn('nothing of the project can be built', str(caught.exception))

    def test_a_project_that_does_not_compile_builds_nothing(self):
        self.spec = None
        self.report['errors'] = [dict(message='a piece is gone')]
        with self.assertRaisesRegex(build.BuildError, 'a piece is gone'):
            self.make().run()
        self.assertEqual(self.ran, [])
        self.assertFalse((self.output / VARIANT).exists())

    def test_another_base_map_is_refused(self):
        (self.lwr / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk').write_bytes(b'another bar')
        with self.assertRaisesRegex(build.BuildError, 'not the map the project was made on'):
            self.make().run()

    def test_an_edit_without_seeds_ships_the_relit_map_as_is(self):
        b = self.make()

        def no_plan(args, log):
            self.run_tool(args, log)
            if args[0] == 'pwsh' and str(args[4]) == 'build':
                (self.work / PATCH / 'seed-plan-built.tsv').unlink()
        b.run_tool = no_plan
        m = b.run()
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'relit map 1')
        self.assertIsNone(m['stages'][2]['seedPlan'])

    def lights_split(self):
        """The compiler's own native_split (plan 4.2, 9.5): the spec's lights object goes to the native edit's
        `lights`, never to the patch. Its report counts the lights too (`counts.lights`), which the Build's own counts
        replace in the compile stage."""
        patch, native = compiler.native_split(dict(objects=[LIGHTS]))
        self.assertEqual((patch['objects'], native['lights']), ([], {k: v for k, v in LIGHTS.items() if k != 'type'}))
        self.report['counts']['lights'] = dict(deleted=1, added=2, changed=2, area=1)

    def test_a_lights_only_edit_is_made_by_native_copy_in_both_kinds_of_build(self):
        self.lights_split()
        self.spec['objects'] = [LIGHTS]
        counts = dict(moved=1, changed=1, added=2, recipeSpots=1, deleted=1,
                      area=dict(moved=1, copied=0, deleted=0, pieces=['XComLevelActor_9']))
        m = self.make().run()
        light, = self.tool('native_copy.py')
        self.assertIn('--bake', light)
        self.assertEqual(self.tool('relight.py'), [])
        self.assertEqual([r for r in self.ran if r[0] == 'pwsh'], [])
        edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
        self.assertEqual((edit['copies'], edit['hides'], edit['lights']['adds']), ([], [], LIGHTS['adds']))
        self.assertEqual(m['stages'][1]['lights'], counts)
        self.assertEqual(m['stages'][3]['lights']['moved'], 1)
        self.assertEqual((m['lights'], m['lightingUnchanged'], m['nativeCopies'], m['nativeHides']), (counts, False, 0, 0))
        self.assertIn('tools/bake/native_lights.py', m['tools'])
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('its light edits made in the map (lights 1 moved, 1 changed, 2 added, 1 deleted; glow lights '
                      'following their pieces 1 moved (XComLevelActor_9))', readme)
        self.assertIn('Each added, moved or changed light is baked into the lightmaps', readme)
        self.assertNotIn(build.QUICK_LIGHTS, readme)
        # a quick build: the same edit, no --bake, and the unbaked-light limitations in its README
        self.ran = []
        q = self.make('111500', quick=True).run()
        light, = self.tool('native_copy.py')
        self.assertNotIn('--bake', light)
        self.assertEqual(q['stages'][3]['lights']['added'], 2)
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn(build.QUICK_LIGHTS, readme)
        self.assertIn('EXP-26 run 2', readme)
        self.assertNotIn('Each added, moved or changed light is baked', readme)

    def test_a_full_build_that_changes_no_lighting_ships_the_edited_map_without_a_cache(self):
        # plan 4.4 and 4.5: an added disabled light; the relight completes and writes no texel
        self.lights_split()
        self.spec['objects'] = [dict(LIGHTS, deletes=[], changes=[], adds=LIGHTS['adds'][:1], area=[])]
        self.unchanged_lighting = True
        m = self.make().run()
        cache = build.cache_name(VARIANT)
        self.assertIsNone(m['cache'])
        self.assertTrue(m['lightingUnchanged'])
        self.assertEqual(sorted(m['files']), sorted('CookedPCConsole/%s.upk' % n for n in (VARIANT, INTRO)))
        self.assertNotIn('CookedPCConsole/%s.tfc' % cache, m['files'])
        stage = m['stages'][3]
        self.assertEqual((stage['cache'], stage['baked'], stage['lightingUnchanged'], stage['written']),
                         (None, True, True, 0))
        self.assertEqual(stage['lights']['createdImports'], ['-301', '-302'])
        pkg = self.output / VARIANT
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'edited map, lighting unchanged')
        readme = (pkg / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('the edit changes no baked light (lighting unchanged)', readme)
        self.assertNotIn('.tfc', readme)
        on_disk = json.loads((pkg / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual((on_disk['cache'], on_disk['lightingUnchanged']), (None, True))

    def test_empty_light_lists_still_change_nothing(self):
        self.lights_split()
        self.spec['objects'] = [dict(type='lights', deletes=[], changes=[], adds=[], area=[])]
        with self.assertRaisesRegex(build.BuildError, 'changes nothing'):
            self.make().run()

    def test_the_export_asked_for_is_one_with_light_metadata_where_the_compiler_takes_a_minimum(self):
        seen = []
        root = Path(self.tmp.name)
        compiler.find_export = lambda cache, doc, minimum=None: (seen.append(minimum),
                                                                 (root / 'scene.json', dict(name='URB_Bar')))[1]
        self.make().run()
        self.assertEqual(seen, [build.EXPORT_MINIMUM])

    def test_a_project_is_found_by_file_id_or_name(self):
        folder = Path(self.tmp.name) / 'projects'
        folder.mkdir()
        doc = json.loads(self.project.read_text(encoding='utf-8'))
        pid = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc'
        (folder / 'shared.json').write_text(json.dumps(dict(doc, id=pid, name='Bar remix')), encoding='utf-8')
        self.assertEqual(build.find_project(pid, folder), folder / 'shared.json')
        self.assertEqual(build.find_project('bar REMIX', folder), folder / 'shared.json')
        self.assertEqual(build.find_project(str(self.project), folder), self.project)
        for missing in ('nope', '1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d'):
            with self.assertRaises(build.BuildError):
                build.find_project(missing, folder)
        (folder / 'other.json').write_text(json.dumps(dict(doc, id='1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d', name='Bar Remix')), encoding='utf-8')
        with self.assertRaises(build.BuildError) as error:
            build.find_project('Bar remix', folder)
        self.assertIn('2 projects are called', str(error.exception))


if __name__ == '__main__':
    unittest.main()
