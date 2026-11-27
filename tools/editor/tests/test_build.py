"""The editor's Build (tools/editor/build.py): a saved project to a variant package, with the tools it runs stubbed."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402
import compiler  # noqa: E402
import editor_fixtures  # noqa: E402
import mapsini  # noqa: E402  (the one writer of a DefaultMaps.ini record, on the path through build)

BASE = b'pristine bar'
VARIANT, PATCH = 'URB_Bar_Test_1234', 'patch_urb_bar_test_1234'
PICTURE_PROJECT = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc'       # a project with a map picture has a real id (pictures.py)
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
    """The game's DefaultMaps.ini record of the map `name` (editor_fixtures.record), as text."""
    return editor_fixtures.record(name).decode('latin-1')


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

    def test_a_cleared_maps_records_stream_none_of_its_patch_levels(self):
        # KB-23: patch_bar and patch_hide_randomized_objects out, before the intro copy and the patch go in
        bar = record('bar')
        c = build.config_lines(['[XComGame.XComMapManager]', bar], None, None, 'URB_Bar', VARIANT, PATCH,
                               '%s (Test) |0' % VARIANT, intros={'CIN_DropshipIntros': INTRO}, drop_patches=True)
        line, = c['maps']
        self.assertEqual(c['droppedStreams'], ['patch_bar', 'patch_hide_randomized_objects'])
        self.assertEqual(mapsini.slot_streams(line), [INTRO, PATCH])
        self.assertEqual((mapsini.stream_slots(line), c['streamSlots']), ([0, 1], [1]))
        # without it, as before, and the result has no droppedStreams
        c = build.config_lines(['[XComGame.XComMapManager]', bar], None, None, 'URB_Bar', VARIANT, PATCH, '%s (Test) |0' % VARIANT)
        self.assertNotIn('droppedStreams', c)
        self.assertIn('MapName="patch_bar"', c['maps'][0])

    def test_the_projects_time_of_day_is_each_records_time_of_day(self):
        # the time of day (game-likeness plan, T-S2): every record the variant gets, an added kind's too, says the time
        # the project sets, written by mapsini's one writer; nothing else of the record changes
        bar = record('bar')
        self.assertEqual(mapsini.unquoted(bar, 'TimeOfDay'), 'eMissionTime_Night')
        terror = mapsini.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False)
        c = build.config_lines([bar, terror], None, None, 'URB_Bar', VARIANT, PATCH, None,
                               missions_list=[dict(record=0), dict(record=1), dict(kind='Special/Bomb')],
                               time_of_day='eMissionTime_Day')
        self.assertEqual(len(c['maps']), 3)
        self.assertEqual([mapsini.unquoted(line, 'TimeOfDay') for line in c['maps']], ['eMissionTime_Day'] * 3)
        self.assertEqual(c['timeOfDay'], 'eMissionTime_Day')
        plain = build.config_lines([bar, terror], None, None, 'URB_Bar', VARIANT, PATCH, None,
                                   missions_list=[dict(record=0), dict(record=1), dict(kind='Special/Bomb')])
        self.assertNotIn('timeOfDay', plain)
        self.assertEqual([line.replace('eMissionTime_Day', 'eMissionTime_Night') for line in c['maps']], plain['maps'])

    def test_the_base_map_is_found_whatever_the_case_of_its_name(self):
        # the farm's file is CsmallScout_Farm.upk and its records, landing zones and rules name CSmallScout_Farm: the
        # game matches names whatever their case, and so does the Build
        bar = record('bar')
        c = build.config_lines(['[XComGame.XComMapManager]', bar],
                               ['LZArray=(MapName="urb_bar",StartLoc=(X=1,Y=2,Z=3))'],
                               ['AbductionMapRules=(iMaxDifficulty=eMissionDiff_Moderate, Map="URB_BAR")'],
                               'Urb_Bar', VARIANT, PATCH, '%s (Test) |0' % VARIANT)
        line, = c['maps']
        self.assertIn('Name="%s"' % VARIANT, line)
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
        terror = mapsini.set_field(bar.replace('CIN_DropshipIntros', 'CIN_FastropeIntros'), 'MissionType',
                                   'eMission_TerrorSite', quoted=False)
        bomb = mapsini.set_field(mapsini.set_field(bar, 'MissionType', 'eMission_Special', quoted=False), 'CouncilType',
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
        terror = mapsini.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False)
        bomb = mapsini.set_field(mapsini.set_field(bar, 'MissionType', 'eMission_Special', quoted=False), 'CouncilType', 'eFCMType_Bomb', quoted=False)
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
        other = mapsini.set_field(bar, 'TimeOfDay', 'eMissionTime_Day', quoted=False)
        c = build.config_lines([bar, other], [], [], 'URB_Bar', VARIANT, None, named)
        self.assertEqual(c['missions'], ['Abduction', 'Abduction 2'])
        self.assertIn('DisplayName="%s (Test, Abduction 2) |0"' % VARIANT, c['maps'][1])

    def test_an_added_bomb_streams_the_variants_copy_of_its_donor(self):
        # spawns plan SP4: the added bomb's objects moved make a copy of Slaughterhouse's stream; the added record
        # streams that copy (a copy replaces its source in every record that streams it), a control record of another
        # kind streams neither
        bar = record('bar')
        copy = 'URB_Slaughterhouse_Stream_%s' % VARIANT
        c = build.config_lines(['[XComGame.XComMapManager]', bar], [], [], 'URB_Bar', VARIANT, PATCH,
                               lambda mission: '%s (Test, %s) |0' % (VARIANT, mission),
                               intros={'URB_Slaughterhouse_Stream': copy},
                               missions_list=[dict(record=0), dict(kind='Special/Bomb')])
        abduction, bomb = c['maps']
        self.assertIn('MapName="%s"' % copy, bomb)
        self.assertNotIn('MapName="URB_Slaughterhouse_Stream"', bomb)
        self.assertNotIn('URB_Slaughterhouse_Stream', abduction)

    def test_a_bomb_records_display_name_keeps_what_long_war_matches(self):
        # Long War throttles a bomb mission's reinforcements by "_Bomb" in the record's display name (plan 2.5)
        bar = record('bar')
        bomb = mapsini.set_field(mapsini.set_field(mapsini.set_field(bar, 'MissionType', 'eMission_Special', quoted=False),
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

    def test_a_record_keeps_its_base_records_own_words(self):
        # LWR map packs plan, section 3: LWR reads a UFO's size from words in the display name, and missions on the
        # globe find a map by it, so it holds the base record's words and nothing of the project's name
        farm = mapsini.set_field(mapsini.set_field(record('bar'), 'Name', 'CSmallScout_Farm'), 'DisplayName',
                                 'CSmallScout_Farm (Crashed Small Scout - Franklin\'s Fancy Farm) |6')
        c = build.config_lines([farm], [], [], 'CSmallScout_Farm', VARIANT, PATCH, None)
        self.assertIn('DisplayName="%s (Crashed Small Scout - Franklin\'s Fancy Farm) |6"' % VARIANT, c['maps'][0])
        # a record without an ending takes the install's; a bomb's keeps what Long War matches
        plain = mapsini.set_field(record('bar'), 'DisplayName', 'URB_Bar (Urban Bar)')
        c = build.config_lines([plain], [], [], 'URB_Bar', VARIANT, PATCH, dict(tail=' |0'))
        self.assertIn('DisplayName="%s (Urban Bar) |0"' % VARIANT, c['maps'][0])
        bomb = mapsini.set_field(record('bar'), 'DisplayName', 'URB_Bar_Bomb (Bomb Defusal Bar) |0')
        c = build.config_lines([bomb], [], [], 'URB_Bar', VARIANT, PATCH, None)
        self.assertIn('DisplayName="%s_Bomb (Bomb Defusal Bar) |0"' % VARIANT, c['maps'][0])

    def test_two_records_with_the_same_words_say_their_missions(self):
        bar = record('bar')
        terror = mapsini.set_field(mapsini.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False),
                                   'DisplayName', 'URB_Bar_T (Beta/Functionality Complete Urban Bar) |0')
        c = build.config_lines([bar, terror], [], [], 'URB_Bar', VARIANT, PATCH, None)
        names = ['DisplayName="%s"' % mapsini.field(line, 'DisplayName') for line in c['maps']]
        self.assertEqual(names, ['DisplayName="%s (Beta/Functionality Complete Urban Bar) |0"' % VARIANT,
                                 'DisplayName="%s (Beta/Functionality Complete Urban Bar, Terror) |0"' % VARIANT])

    def test_an_added_ufo_missions_name_says_its_ship_as_lwr_reads_it(self):
        bar = record('bar')
        listed = [dict(record=0), dict(kind='Crash', ship='eShip_UFOAbductor'), dict(kind='LandedUFO', ship='eShip_UFOSupply')]
        c = build.config_lines([bar], [], [], 'URB_Bar', VARIANT, PATCH, None, missions_list=listed)
        names = [mapsini.field(line, 'DisplayName') for line in c['maps']]
        self.assertEqual(names[0], '%s (Beta/Functionality Complete Urban Bar) |0' % VARIANT)
        self.assertIn(' Abductor ', names[1])
        self.assertTrue(names[1].endswith('Urban Bar, Crashed Abductor UFO) |0'), names[1])
        self.assertIn(' Supply Ship ', names[2])
        self.assertEqual(len(set(names)), 3)
        import missions
        self.assertIn(' Crashed Overseer ', ', ' + missions.added_words(dict(kind='Crash', ship='eShip_UFOEthereal')))
        self.assertIn(' Crashed Destroyer ', ', ' + missions.added_words(dict(kind='Crash', ship='eShip_UFOLargeScout')))
        self.assertEqual(missions.added_words(dict(kind='TerrorSite')), 'Terror')

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
        m = dict(variant=VARIANT, patch=PATCH, cache=None, files={'CookedPCConsole/a.upk': 'x'}, builtAt='now',
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

    def test_a_record_written_by_hand_with_spaces_around_its_equals_signs_is_one_of_the_maps(self):
        # KB-11: the game reads a record written Name = "URB_Bar", and so do the map list and the install
        # (installs.base_records): the Build finds the same records in the same order, so its records stand for the
        # install's (config.recordMissions), and writes its own copy of that one
        bar = record('bar')
        terror = mapsini.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False)
        spaced = re.sub(r'(?<![A-Za-z])Name="URB_Bar"', 'Name = "URB_Bar"', terror, count=1)
        spaced = spaced.replace('DisplayName="', 'DisplayName  =  "').replace('bInRotation=True', 'bInRotation= True')
        maps = ['[XComGame.XComMapManager]', bar, record('templeship'), spaced]
        self.assertEqual(build.base_records(maps, 'URB_Bar'), [bar, spaced])
        self.assertEqual([l.decode('latin-1') for _, l in build.installs.base_records([m.encode('latin-1') for m in maps], 'URB_Bar')],
                         [bar, spaced])
        c = build.config_lines(maps, [], [], 'URB_Bar', VARIANT, PATCH, None)
        self.assertEqual((c['missions'], c['recordMissions']), (['Abduction', 'Terror'], [[0], [1]]))
        mine = c['maps'][1]
        self.assertEqual((mapsini.field(mine, 'Name'), mapsini.unquoted(mine, 'bInRotation'), mapsini.unquoted(mine, 'MissionType')),
                         (VARIANT, 'False', 'eMission_TerrorSite'))
        self.assertEqual(mapsini.field(mine, 'DisplayName'), '%s (Beta/Functionality Complete Urban Bar, Terror) |0' % VARIANT)
        self.assertIn('StreamingMaps[2]=( MapName="%s"' % PATCH, mine)

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

    def test_the_quick_build_light_text_says_what_is_not_baked(self):
        # plan 4.3, said plainly (review finding 44: the editor never says a thing waits for a game test)
        for limitation in ('a deleted light\'s pool stays on the baked surfaces', 'an added light has no baked light',
                           'the old glow stays baked where it was'):
            self.assertIn(limitation, build.QUICK_LIGHTS)
        for doubt in ('to be confirmed', 'not yet known', 'EXP-26'):
            self.assertNotIn(doubt, build.QUICK_LIGHTS)


class ToolRunner(unittest.TestCase):
    def test_a_tool_in_a_folder_the_code_page_lacks_runs_and_is_logged(self):
        """Build._run starts each tool with UTF-8 for its output (procs.utf8_env): a builds folder under a Cyrillic user
        name is printed, where a tool writing in the system's code page stopped at its first path. The test's own
        environment is stripped of the variables first (the test runner sets one)."""
        import os
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'Иван' / 'builds'
            folder.mkdir(parents=True)
            tool = folder / 'tool.py'
            tool.write_text('import sys\nprint("work folder: " + sys.argv[1])\n', encoding='utf-8')
            said = []
            b = build.Build(build.BuildInputs(folder / 'project.json', temp, folder, temp, None, echo=said.append))
            bare = {k: v for k, v in os.environ.items() if k not in ('PYTHONUTF8', 'PYTHONIOENCODING')}
            with mock.patch.dict(os.environ, bare, clear=True):
                b._run([sys.executable, '-B', tool, folder / '.work'], folder / 'tool.log')
            self.assertIn('    work folder: %s' % (folder / '.work'), said)
            self.assertIn('work folder: %s' % (folder / '.work'), (folder / 'tool.log').read_text(encoding='utf-8'))


class Generators(unittest.TestCase):
    def test_the_exp26_generator_compiles_as_it_was_made_and_saves_at_the_stores_schema(self):
        """tools/editor/examples/exp26_projects.py (build_outputs.py's bar-pieces input takes its compile) made its
        document at project schema 1, which the store refuses to write: it compiles it so and saves it at the
        store's schema (follow-ups 3.6). The map's export is a stand-in here."""
        import runpy
        import projects
        script = HERE.parent / 'examples' / 'exp26_projects.py'
        pl = 'TheWorld.PersistentLevel.'
        lights = [dict(actor=pl + n, layer='base', location=[0.0, 0.0, 300.0], rotation=[-16384, 0, 0],
                       component=pl + n + '.SpotLightComponent_0')
                  for n in ('SpotLight_3', 'PointLight_4', 'SpotLight_53', 'SpotLight_32', 'PointLight_15')]
        objects = [dict(actor=pl + n, layer='base', location=[96.0, 0.0, 0.0], rotation=[0, 0, 0],
                        component=pl + n + '.StaticMeshComponent_0')
                   for n in ('XComLevelActor_37', 'XComDestructibleActor_2')]
        compiled = []
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(compiler, 'find_export', return_value=('scene.json', dict(lights=lights, objects=objects))), \
                mock.patch.object(compiler, 'light_rule', return_value=None), \
                mock.patch.object(compiler, 'compile_project', side_effect=lambda doc, scene, enable=(): (
                    compiled.append(dict(doc)), ({}, dict(ok=True, counts={}, warnings=[])))[1]), \
                mock.patch('sys.argv', [str(script), '--cache', temp]), \
                mock.patch('settings.load_settings', return_value=dict(projects=Path(temp) / 'projects', cache=Path(temp))):
            runpy.run_path(str(script), run_name='__main__')
            saved = projects.ProjectStore(Path(temp) / 'projects').load('26a0a0b1-2626-4d0a-8e26-3c4d5e6f7a26')
        self.assertEqual([d['schemaVersion'] for d in compiled], [1])
        self.assertEqual((saved['schemaVersion'], saved['revision'], saved['name']),
                         (projects.SCHEMA_VERSION, 1, 'EXP-26 lights'))


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
        self.said = []
        self.relit = 1
        self.failing = None
        self.unchanged_lighting = False
        self.landing = True         # the intro has a landing of its own for URB_Bar
        self.no_staged_report = False
        # a baked Build's records of what it made and relit: the writer's copies (none), the relight's reports of the
        # lightmaps (two) and the sun shadow maps (none) it wrote
        self.copies_made, self.relit_reports, self.shadow_reports = None, [1, 2], []
        # the compiler's own work is tested in test_compiler; here it gives a fixed spec
        saved = compiler.find_export, compiler.compile_project
        self.addCleanup(setattr, compiler, 'find_export', saved[0])
        self.addCleanup(setattr, compiler, 'compile_project', saved[1])
        compiler.find_export = lambda cache, doc, minimum=None: (root / 'scene.json', dict(name='URB_Bar'))
        self.spec = dict(name=PATCH, map=dict(name='URB_Bar', origin=[0, 0, 0], shipAs=VARIANT), editor={},
                         objects=[COPY, DOOR, HIDE])
        self.report = dict(errors=[], warnings=[], counts=dict(moved=0, deleted=0, added=1, errors=0, warnings=0))
        compiler.compile_project = lambda doc, scene, enable=(), library=None, foreign=(): (self.spec, dict(self.report))
        # the lightmaps put inside the map (inline_lighting.py, tested on real maps in the bake suite): here the made-up
        # map is marked, and inside_fails makes it fail as a map that can't take them would
        self.inside_fails = None
        self.addCleanup(setattr, build, 'inline_map', build.inline_map)
        build.inline_map = self.inline_map
        # what the built map holds of lightmaps (lighting_size.py, tested on real maps in the bake suite): made up
        self.held = dict(textures=3, bytes=1000, cached=0, whole=0)
        self.no_cache = False       # the relight writes no cache: every texture it wrote is inside the map already
        self.addCleanup(setattr, build, 'lightmaps_held', build.lightmaps_held)
        build.lightmaps_held = lambda path: dict(self.held)

    def inline_map(self, src, dst, cache, tfc):
        if self.inside_fails: raise ValueError(self.inside_fails)
        data = b'inside ' + Path(src).read_bytes() + b' with ' + Path(tfc).read_bytes()
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_bytes(data)
        return dict(cache=cache, textures=2, mips=8, bytes=len(Path(tfc).read_bytes()), sha256=hashlib.sha256(data).hexdigest())

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
            for lane in ('effects', 'sounds', 'flares'):
                if edit.get(lane):
                    edit[lane]['copies'] = [dict(c, source=c['source'] + '_900', staged=True) if c.get('donor') else c
                                            for c in edit[lane]['copies']]
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
            if not self.no_cache:
                (lit / ('%s.tfc' % cache)).write_bytes(b'lightmaps')
            native = args[k].endswith('native_copy.py')
            if native:
                self.flag_fixture(args, lit, variant)
                if self.copies_made:
                    # the writer's record of its copies (native_copy.py's nativeCopies `copies`: each copy's label
                    # and the actor it made)
                    path = lit / ('%s.fixture.json' % variant)
                    fixture = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else dict(nativeCopies={})
                    fixture['nativeCopies']['copies'] = self.copies_made
                    path.write_text(json.dumps(fixture), encoding='utf-8')
            (lit / ('%s.relight.json' % variant)).write_text(json.dumps(dict(
                components=self.relit_reports, shadowMaps=self.shadow_reports, unchanged=[3], skipped=[],
                copies=[] if native else [dict(source='X_1', triangles=5)],
                nativeCopies=[dict(copy='XComLevelActor_99', source='XComLevelActor_1')] if native else [],
                # the relight's record of texels its writes changed in pieces it didn't relight (lighting_fixture)
                otherPiecesChanged=getattr(self, 'other_changed', dict(textures=0, pieces=[], texels=0, largest=0.0)))))

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
        return build.Build(build.BuildInputs(
            self.project, self.tmp.name, self.output, self.lwr, self.udk if udk else None, patch_work=self.work,
            now=now, run=self.run_tool, seed=self.seed, echo=self.said.append, quick=quick, named=self.name_copy,
            picture=self.picture_copy))

    def picture_copy(self, src, dst, png):
        """The map picture's writer (Build._picture), as a stand-in: the map's bytes and the picture file's hash."""
        self.pictured = getattr(self, 'pictured', []) + [(str(src), str(dst), str(png))]
        Path(dst).write_bytes(Path(src).read_bytes() + b' +picture ' + hashlib.sha256(Path(png).read_bytes()).hexdigest().encode())
        return dict(export=7, how='added')

    def with_picture(self, colour=(30, 60, 90), keep=True):
        """The project given a map picture (pictures.py keeps the file beside it, by the project's id); returns its
        SHA-256. `keep` False: the project names it and the file is not there."""
        import io
        from PIL import Image
        import pictures
        out = io.BytesIO()
        Image.new('RGB', (512, 256), colour).save(out, 'PNG')
        self.doc['id'] = PICTURE_PROJECT
        digest = pictures.save_picture(self.project.parent, PICTURE_PROJECT, out.getvalue())['sha256']
        if not keep:
            pictures.remove_picture(self.project.parent, PICTURE_PROJECT)
            (self.project.parent / '.workshop' / PICTURE_PROJECT / 'picture.prev.png').unlink()
        self.doc['picture'] = dict(sha256=digest)
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        return digest

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

    def test_a_spawn_rule_alone_builds_with_its_exclusion_line(self):
        """Editor spawns plan, SP8: a project whose one change is its spawn rule (scripted drop-ins where placed) is
        work: it builds the map with the lighting unchanged, and the manifest and README carry the variant's ExcludeMaps
        line for DefaultRandomSpawns.ini. On an install without that file (plain EW) the line is said with why it has no
        place there."""
        self.spec['objects'] = []
        self.spec['spawnRules'] = dict(dropIns='placed')
        m = self.make().run()
        ex = m['config']['dropInExclusion']
        self.assertEqual((ex['file'], ex['section'], ex['line']),
                         ('DefaultRandomSpawns.ini', 'XComLZMutator.XComSpawnAlienMutator', 'ExcludeMaps = "%s"' % VARIANT))
        self.assertIn('plain Enemy Within', ex['why'])
        self.assertIn('plain Enemy Within lands scripted drop-ins where placed already', (self.output / VARIANT / 'README.txt').read_text('latin-1'))
        cfg = self.lwr / 'XEW/XComGame/Config'
        (cfg / 'DefaultMutatorLoader.ini').write_bytes(b'[XComMutator.XComMutatorLoader]\r\narrTacticalMutators="XComLZMutator.XComSpawnAlienMutator"\r\n')
        (cfg / 'DefaultRandomSpawns.ini').write_bytes(b'[XComLZMutator.XComSpawnAlienMutator]\r\nExcludeMaps = "EWI_ChryssalidHive"\r\n')
        m = self.make('111500').run()
        self.assertNotIn('why', m['config']['dropInExclusion'])
        readme = (self.output / VARIANT / 'README.txt').read_text('latin-1')
        self.assertIn('DefaultRandomSpawns.ini, in its [XComLZMutator.XComSpawnAlienMutator] section', readme)
        self.assertIn('\nExcludeMaps = "%s"\n' % VARIANT, readme)
        self.assertTrue(m['lightingUnchanged'])
        self.assertIn('reads URB_Bar\'s own lightmaps', readme)
        # without the rule the same project changes nothing
        del self.spec['spawnRules']
        with self.assertRaisesRegex(build.BuildError, 'no spawn rule is set'):
            self.make('112000').run()

    def test_what_long_war_rebalance_is_told_of_the_map_builds_as_its_lines(self):
        """Schema 6's lwrMapInfo (LWR 3.00.00 beta 17's map info): the compiler's reading of it (the report's) becomes
        the variant's MapInfo lines in the manifest's config and the README, in LWR's own spelling; a project whose
        one change it is builds the map with the lighting unchanged. Without it the manifest has no such lines."""
        m = self.make().run()
        self.assertNotIn('mapInfo', m['config'])
        self.assertNotIn('MapInfo=', (self.output / VARIANT / 'README.txt').read_text('latin-1'))
        self.spec['objects'] = []
        self.report['lwrMapInfo'] = dict(alienDensity='Moderate', holdTheLine='No')
        m = self.make('111500').run()
        lines = ['MapInfo=(Map="%s", Key="AlienDensity", Value="Moderate")' % VARIANT,
                 'MapInfo=(Map="%s", Key="HoldTheLine", Value="No")' % VARIANT]
        self.assertEqual(m['config']['mapInfo'], lines)
        self.assertTrue(m['lightingUnchanged'])
        readme = (self.output / VARIANT / 'README.txt').read_text('latin-1')
        self.assertIn('Long War Rebalance 3.00.00 beta 17 or later, what it is told of the map', readme)
        for line in lines: self.assertIn('\n%s\n' % line, readme)
        # the lines are ones a card holds
        sys.path.insert(0, str(Path(build.__file__).resolve().parents[1] / 'upk'))
        import pack_card
        self.assertEqual([pack_card.parse_record(l).kind for l in lines], ['MapInfo', 'MapInfo'])
        self.assertEqual(pack_card.info_warnings(dict(MapInfo=[pack_card.parse_record(l).fields for l in lines])), [])

    def test_a_baked_build_that_changes_nothing_in_the_map_records_its_lighting_unchanged(self):
        """A baked Build of landing-zone lines alone, or of a spawn rule alone, relights nothing and keeps the map's
        own lightmaps: its light stage says so as a baked Build of cover blocks alone does (baked, lighting unchanged,
        no cache), not as a quick Build's (baked false), so the Build window says lighting unchanged, not lighting not
        baked. A quick Build of the same is a quick Build's."""
        self.spec['objects'] = []
        zones = dict(zones=[dict(id='z1', location=[719, -1681, 64], direction='north', kind='normal')], own=[], ownLandings=0)
        for stamp, key, value in (('110000', 'landingZones', zones), ('110100', 'spawnRules', dict(dropIns='placed'))):
            with self.subTest(key):
                self.spec.pop('landingZones', None)
                self.spec.pop('spawnRules', None)
                self.spec[key] = value
                self.ran.clear()
                m = self.make(stamp).run()
                self.assertEqual((self.tool('relight.py'), [r for r in self.tool('native_copy.py') if '--bake' in r]), ([], []))
                stage = next(s for s in m['stages'] if s['stage'] == 'light')
                self.assertEqual((stage['baked'], stage['cache'], stage.get('lightingUnchanged'), stage['nativeCopies'], stage['hidden']),
                                 (True, None, True, 0, 0))
                self.assertEqual((m['quick'], m['cache'], m['lightingUnchanged']), (False, None, True))
                # (nothing relit: the map's own lightmaps are the Build's, and it names no light of its own)
                self.assertFalse({'builtActors', 'relitComponents', 'asBuilt'} & set(m))
                q = self.make('11%s30' % stamp[2:4], quick=True).run()
                stage = next(s for s in q['stages'] if s['stage'] == 'light')
                self.assertEqual((stage['baked'], stage['cache'], 'lightingUnchanged' in stage), (False, None, False))
                self.assertEqual((q['quick'], q['lightingUnchanged']), (True, False))

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

    def test_each_tool_the_build_starts_is_named_first(self):
        """build.py says what runs before each tool it starts, in a `running: <label>` line (Build.tool), which the
        server shows on the build's step (tools/viewer/builds.py reads that line, not the tool's command line): each
        tool of a patched baked build, a quick build and a relight alone comes just after its line, labelled; and
        build.py starts a tool nowhere but in Build.tool, so the Build's other tools (the shell, the transplant, the
        stream copies) say theirs too."""
        events = []

        class Said(list):
            def append(self, line):
                super().append(line)
                events.append(line)
        self.said = Said()
        record = self.run_tool

        def run(args, log):
            events.append(('ran', next(Path(str(a)).name for a in args if str(a).endswith(('.py', '.ps1')))))
            record(args, log)
        self.run_tool = run

        def started():
            pairs = [(events[i - 1], e[1]) if i and isinstance(events[i - 1], str) and events[i - 1].startswith('running:')
                     else ('(no running line)', e[1]) for i, e in enumerate(events) if isinstance(e, tuple)]
            events.clear()
            return pairs
        self.make().run()
        self.assertEqual(started(), [('running: patch and cook', 'patchtool.ps1'), ('running: patch and cook', 'patchtool.ps1'),
                                     ('running: copying and relighting', 'native_copy.py'), ('running:', 'intro_copy.py')])
        self.make('110100', quick=True).run()
        self.assertEqual(started(), [('running: patch and cook', 'patchtool.ps1'), ('running: patch and cook', 'patchtool.ps1'),
                                     ('running: making the edit in the map', 'native_copy.py'), ('running:', 'intro_copy.py')])
        self.spec['objects'] = [DOOR]
        self.make('110200').run()
        self.assertEqual(started(), [('running: patch and cook', 'patchtool.ps1'), ('running: patch and cook', 'patchtool.ps1'),
                                     ('running: relighting', 'relight.py'), ('running:', 'intro_copy.py')])
        import ast
        tree = ast.parse(Path(build.__file__).read_text(encoding='utf-8'))
        starts = [(f.name, n.lineno) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) for n in ast.walk(f)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('run_tool', '_run')]
        self.assertEqual([name for name, _ in starts], ['tool'], 'a tool started outside Build.tool: %s' % starts)

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
                         (1, [dict(map='URB_PoliceStation', sha256='d' * 64, file='x', pieces=1, effects=0, flares=0, objectsBrought=7,
                                   objectsReused=3, cut=[], sizes={}, bytes=1234)]))
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

    def test_effects_of_other_maps_alone_are_staged_and_keep_the_lighting(self):
        """An effect of another map (the effects and sounds plan, stage FX4), the project's only change: staged in the
        map first, then made by native_copy.py from the staged map in both kinds of build, with the lighting kept."""
        foam = dict(id='a', name='Emitter_10_copy1', source='Emitter_10', actorClass='Emitter', location=[0.0, 0.0, 0.0],
                    rotation=[0, 0, 0], donor=dict(package='URB_PierA', sha256='d' * 64))
        self.spec['objects'] = [dict(type='effects', moves=[], deletes=[], copies=[foam])]
        work = self.output / '.work' / ('%s-20261107-110000' % VARIANT)
        for quick in (False, True):
            self.ran.clear()
            m = self.make(stamp='110000' if not quick else '110100', quick=quick).run()
            work = self.output / '.work' / ('%s-%s' % (VARIANT, m['buildId'].split('-', 1)[1]))
            self.assertEqual(len(self.tool('transplant.py')), 1)
            light, = self.tool('native_copy.py')
            k = light.index(str(build.NATIVE_COPY))
            self.assertEqual(light[k + 1], str(work / 'transplant' / 'staged' / 'URB_Bar.upk'))
            self.assertNotIn('--bake', light)
            edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
            self.assertEqual([(c['source'], c['staged']) for c in edit['effects']['copies']], [('Emitter_10_900', True)])
            self.assertEqual(self.tool('relight.py'), [])
            self.assertEqual((m['quick'], m['cache']), (quick, None))
        # a copy of the map's own effect stages nothing
        self.ran.clear()
        self.spec['objects'] = [dict(type='effects', moves=[], deletes=[], copies=[{k: v for k, v in foam.items() if k != 'donor'}])]
        self.make(stamp='110200', quick=True).run()
        self.assertEqual(self.tool('transplant.py'), [])

    def test_lens_flares_alone_build_as_effects_do(self):
        """The flares' lane (stage FX6b), the project's only change: made by native_copy.py in both kinds of build with
        the lighting kept; one of another map is staged first, one of the map's own stages nothing."""
        glare = dict(id='a', name='LensFlareSource_0_copy1', source='LensFlareSource_0', actorClass='LensFlareSource',
                     location=[0.0, 640.0, 200.0], rotation=[0, 0, 0], donor=dict(package='AlienBase01', sha256='d' * 64))
        move = dict(name='LensFlareSource_7', actorClass='LensFlareSource', location=[900.0, -220.0, 300.0], rotation=[0, 0, 0])
        self.spec['objects'] = [dict(type='flares', moves=[move], deletes=[], copies=[glare], values=[])]
        for quick in (False, True):
            self.ran.clear()
            m = self.make(stamp='110000' if not quick else '110100', quick=quick).run()
            self.assertEqual(len(self.tool('transplant.py')), 1)
            light, = self.tool('native_copy.py')
            self.assertNotIn('--bake', light)
            edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
            self.assertEqual([(c['source'], c['staged']) for c in edit['flares']['copies']], [('LensFlareSource_0_900', True)])
            self.assertEqual([x['name'] for x in edit['flares']['moves']], ['LensFlareSource_7'])
            self.assertNotIn('effects', edit)
            self.assertEqual(self.tool('relight.py'), [])
            self.assertEqual((m['quick'], m['cache']), (quick, None))
        # the map's own flare moved, the project's only change: built, nothing staged
        self.ran.clear()
        self.spec['objects'] = [dict(type='flares', moves=[move], deletes=[], copies=[], values=[])]
        self.make(stamp='110200', quick=True).run()
        self.assertEqual(self.tool('transplant.py'), [])
        self.assertEqual(len(self.tool('native_copy.py')), 1)

    def test_base_spawn_points_alone_build_in_the_map_with_the_lighting_kept(self):
        """The spawns lane (the editor spawns plan, SP6 and SP7), the project's only change: a pod moved, a Meld point
        given values, a pod copied and one deleted are made by native_copy.py in both kinds of build, with nothing staged,
        no relight and the lighting kept; the manifest counts them."""
        move = dict(name='XComAlienPod_Abduction_0', actorClass='XComAlienPod_Abduction', kind='pod',
                    location=[1694.8, 1642.2, 1.5], rotation=[0, 0, 0], before=dict(location=[1598.8, 1642.2, 1.5], rotation=[0, -16384, 0]))
        value = dict(name='XComMeldContainerSpawnPoint_2', actorClass='XComMeldContainerSpawnPoint', kind='meld',
                     spawn=dict(difficulty='Hard', destroyedOnTurn=6))
        copy = dict(id='a', name='XComAlienPod_Abduction_2_copy1', source='XComAlienPod_Abduction_2', kind='pod', podIndex=5,
                    actorClass='XComAlienPod_Abduction', location=[-1145.6, 251.2, 17.0], rotation=[0, -16384, 0])
        gone = dict(name='XComAlienPod_Abduction_4', actorClass='XComAlienPod_Abduction', kind='pod')
        self.spec['objects'] = [dict(type='spawns', moves=[move], values=[value], deletes=[gone], copies=[copy])]
        for quick in (False, True):
            self.ran.clear()
            m = self.make(stamp='110000' if not quick else '110100', quick=quick).run()
            self.assertEqual(self.tool('transplant.py'), [])
            light, = self.tool('native_copy.py')
            self.assertNotIn('--bake', light)
            edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
            self.assertEqual((edit['spawns']['moves'], edit['spawns']['values'], edit['spawns']['copies'], edit['spawns']['deletes']),
                             ([move], [value], [copy], [gone]))
            self.assertEqual(self.tool('relight.py'), [])
            self.assertEqual((m['quick'], m['cache']), (quick, None))
            self.assertEqual(m['spawnEdits'], dict(moved=1, valued=1, added=1, deleted=1))

    def test_the_time_of_day_alone_builds_with_the_lighting_kept_and_its_records_time(self):
        """The sun lane (game-likeness plan, T-S2), the project's only change: written into native-edit.json and made by
        native_copy.py in both kinds of build with the lighting kept; every record says the report's time of day; a
        quick Build that turns the sun says its shadows stay the old ones (sun-shadows-stale), a full one does not."""
        sun = dict(actor='DominantDirectionalLight_1', component='DominantDirectionalLight_1.DominantDirectionalLightComponent_0',
                   rotation=[-10194, 24213, -27675], color=[255, 245, 215], brightness=1.1, directionChanged=True,
                   sky=dict(actor='SkyLight_0', component='SkyLight_0.SkyLightComponent_263', color=[150, 150, 170],
                            brightness=0.6, lowerColor=[255, 224, 173], lowerBrightness=0.01))
        self.spec = dict(self.spec, objects=[], sun=sun)
        self.report['sun'] = dict(time='13:00', timeOfDay='eMissionTime_Day', directionChanged=True, sky=True)
        for quick in (False, True):
            self.ran.clear()
            m = self.make(stamp='110000' if not quick else '110100', quick=quick).run()
            light, = self.tool('native_copy.py')
            self.assertNotIn('--bake', light)
            edit = json.loads(Path(light[light.index('--copies') + 1]).read_text(encoding='utf-8'))
            self.assertEqual(edit['sun'], sun)
            self.assertEqual(self.tool('relight.py'), [])
            self.assertEqual((m['quick'], m['cache']), (quick, None))
            line, = m['config']['maps']
            self.assertEqual(mapsini.unquoted(line, 'TimeOfDay'), 'eMissionTime_Day')
            self.assertEqual(m['config']['timeOfDay'], 'eMissionTime_Day')
            report = json.loads((Path(m['work']) / 'compile-report.json').read_text(encoding='utf-8'))
            self.assertEqual([w['code'] for w in report['warnings']], ['sun-shadows-stale'] if quick else [])
        # the direction kept: no warning on a quick Build either (the stand-in compile's report afresh: the quick Build
        # added its warning to the list it shares)
        self.report = dict(self.report, warnings=[], counts=dict(self.report['counts'], warnings=0),
                           sun=dict(self.report['sun'], directionChanged=False))
        self.spec['sun'] = dict(sun, directionChanged=False)
        m = self.make(stamp='110200', quick=True).run()
        self.assertEqual(json.loads((Path(m['work']) / 'compile-report.json').read_text(encoding='utf-8'))['warnings'], [])

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

    def test_a_cleared_maps_build_streams_none_of_its_patch_levels(self):
        # KB-23: the compiler's dropPatches; the records leave patch_bar and patch_hide_randomized_objects out, the
        # manifest says so for the installs (installs.plan_record), and the readme names them
        self.spec = dict(self.spec, objects=[COPY], dropPatches=True)
        m = self.make().run()
        self.assertTrue(m['dropPatches'])
        self.assertEqual(m['config']['droppedStreams'], ['patch_bar', 'patch_hide_randomized_objects'])
        line, = m['config']['maps']
        self.assertEqual([s for s in mapsini.slot_streams(line) if s.lower().startswith('patch_bar')], [])
        self.assertNotIn('patch_hide_randomized_objects', line)
        self.assertIn('MapName="%s"' % INTRO, line)
        self.assertEqual(m['streamCopies'], [])
        text = (self.output / VARIANT / 'README.txt').read_text(encoding='utf-8')
        self.assertIn('streams none of patch_bar, patch_hide_randomized_objects', text)

    def test_a_missions_moved_objects_ship_in_a_copy_of_its_stream_for_that_mission_only(self):
        # mission types plan, Part E: the compiler's streamMoves; the Build copies the stream with the moves (and the map
        # switches naming the variant), ships it, streams it in the data recovery's record alone, and hands the base
        # map's tiles under the moved solid piece to native_copy.py (streamTiles)
        bar = record('bar')
        cnh = mapsini.set_field(mapsini.add_stream(bar, 'URB_Bar_CNH')[0], 'MissionType', 'eMission_CaptureAndHold', quoted=False)
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
                                                    ('%s.upk' % VARIANT, '%s.upk' % PATCH, '%s.upk' % INTRO)))
        # its lightmaps inside the map (inline_lighting.py): no texture cache goes with it
        self.assertEqual((m['cache'], m['lightingInside']), (None, dict(cache=cache, textures=2, mips=8, bytes=9,
                                                                        held=dict(textures=3, bytes=1000, whole=0))))
        self.assertIn('lightmaps inside the map: 0.0 MB in 3 textures', self.said)
        self.assertFalse(any(line.startswith('warning: ') for line in self.said))
        self.assertIn('tools/bake/inline_lighting.py', m['tools'])
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
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'inside relit map 1 seeded with lightmaps')
        self.assertEqual((pkg / 'CookedPCConsole' / ('%s.upk' % PATCH)).read_bytes(), b'cooked patch')
        for rel, digest in m['files'].items():
            self.assertEqual(build.sha256(pkg / rel), digest)
        # the package's manifest names no folder of this computer (smaller built maps plan, P2): the record with its
        # folders, which the build returns, is the work folder's build-log.json
        on_disk = json.loads((pkg / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((Path(m['work']) / 'build-log.json').read_text(encoding='utf-8')), json.loads(json.dumps(m)))
        text = json.dumps(on_disk).replace('\\\\', '\\').lower()
        for folder in (self.tmp.name, str(Path.home())):
            self.assertNotIn(folder.lower(), text)
        self.assertEqual(on_disk['work'], str(Path('<builds>') / '.work' / m['buildId']))
        self.assertEqual(on_disk['project']['file'], str(Path('<projects>') / self.project.name))
        for key in ('files', 'config', 'buildId', 'variant', 'lightingInside', 'tools'):
            self.assertEqual(on_disk[key], json.loads(json.dumps(m[key])), key)
        self.assertEqual(m['schema'], build.SCHEMA)
        self.assertEqual(m['buildId'], '%s-20261107-110000' % VARIANT)
        self.assertEqual(m['streams'], [PATCH])
        self.assertEqual((m['project']['id'], m['project']['revision']), ('0000-test', 3))
        self.assertEqual(m['source']['sha256'], hashlib.sha256(BASE).hexdigest())
        self.assertEqual([s['stage'] for s in m['stages']], ['snapshot', 'compile', 'patch', 'light', 'seeds', 'inside'])
        self.assertIn('DisplayName="%s (Beta/Functionality Complete Urban Bar) |0"' % VARIANT, m['config']['maps'][0])
        readme = (pkg / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('its lightmaps inside the map (no texture cache goes with it)', readme)
        self.assertNotIn('.tfc', readme)
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

    def test_a_baked_build_names_the_actor_each_piece_became_and_keeps_the_project_as_built(self):
        """A baked Build's manifest (the game-likeness plan's B4): which built actor each project piece became, from the
        writer's record of its copies (a moved original by its copy's label, an added piece by its output name, a made
        piece cut into parts by its parts in order; a copy the project names nothing for left out), the components the
        relight wrote a lightmap or a sun shadow map for (a skipped one not), and the project as built. A quick Build's
        has none of them, nor a baked one whose lighting is unchanged (test_a_baked_build_that_changes_nothing...)."""
        pl = 'TheWorld.PersistentLevel.'
        self.doc['added'] = [dict(id='a', actor=pl + 'XComLevelActor_1_copy1', components=[], location=[1, 2, 0], rotation=[0, 0, 0],
                                  **{'from': dict(package='URB_Bar', level='base', actor=pl + 'XComLevelActor_1')}),
                             dict(id='b', actor=pl + 'XComFracLevelActor_5_copy2', components=[], location=[0, 0, 0], rotation=[0, 0, 0],
                                  **{'from': dict(package='URB_Bar', level='base', actor=pl + 'XComFracLevelActor_5')})]
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        self.copies_made = [dict(label='XComLevelActor_1_copy1', copy=pl + 'XComLevelActor_99'),
                            dict(label='move:XComLevelActor_7', copy=pl + 'XComLevelActor_100'),
                            dict(label='XComFracLevelActor_5_copy2_part2', copy=pl + 'XComFracLevelActor_31'),
                            dict(label='XComFracLevelActor_5_copy2_part1', copy=pl + 'XComFracLevelActor_30'),
                            dict(label='XComLevelActor_3_copy9', copy=pl + 'XComLevelActor_101')]
        lit = lambda actor, component: dict(component='%s%s.%s' % (pl, actor, component), texels=4)  # noqa: E731
        self.relit_reports = [lit('XComLevelActor_8', 'StaticMeshComponent_2'), lit('XComLevelActor_99', 'StaticMeshComponent_0')]
        self.shadow_reports = [lit('XComLevelActor_8', 'StaticMeshComponent_2'), lit('XComLevelActor_9', 'StaticMeshComponent_4'),
                               dict(lit('XComLevelActor_10', 'StaticMeshComponent_1'), skipped='no shadow map of the sun')]
        m = self.make().run()
        self.assertEqual(m['builtActors'], {pl + 'XComFracLevelActor_5_copy2': [pl + 'XComFracLevelActor_30', pl + 'XComFracLevelActor_31'],
                                            pl + 'XComLevelActor_1_copy1': pl + 'XComLevelActor_99',
                                            pl + 'XComLevelActor_7': pl + 'XComLevelActor_100'})
        self.assertEqual(m['relitComponents'], [pl + 'XComLevelActor_8.StaticMeshComponent_2', pl + 'XComLevelActor_9.StaticMeshComponent_4',
                                                pl + 'XComLevelActor_99.StaticMeshComponent_0'])
        self.assertEqual(m['asBuilt'], self.doc)
        on_disk = json.loads((self.output / VARIANT / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual((on_disk['builtActors'], on_disk['relitComponents'], on_disk['asBuilt']['added']),
                         (m['builtActors'], m['relitComponents'], self.doc['added']))
        q = self.make('120000', quick=True).run()
        self.assertFalse({'builtActors', 'relitComponents', 'asBuilt'} & set(q))

    def test_the_manifest_names_every_module_of_the_compile(self):
        """The manifest's tools record names build.py first, then every module of tools/editor it imports, found from
        their imports: the compiler and the modules split off it (its tables, the edit families, the native edit, the
        piece lookup) and game_files, each with its SHA-256; not the prefab test's stage, which no Build imports."""
        m = self.make().run()
        editor = Path(build.__file__).resolve().parent
        named = [k for k in m['tools'] if k.startswith('tools/editor/')]
        self.assertEqual(named[0], 'tools/editor/build.py')
        wanted = {'tools/editor/%s' % n for n in ('compiler.py', 'compiler_tables.py', 'native_edit.py', 'piece_lookup.py',
                                                 'game_files.py')}
        wanted |= {'tools/editor/%s' % p.name for p in editor.glob('*_edits.py')}
        self.assertLessEqual(wanted, set(named))
        self.assertNotIn('tools/editor/prefab_stage.py', named)
        for k in named:
            self.assertEqual(m['tools'][k], build.sha256(editor.parents[1] / k))

    def test_the_manifest_names_the_modules_of_the_tools_the_build_runs(self):
        """The manifest's tools record names the modules of tools/bake and tools/upk found from the imports of the
        tools the Build runs and of build.py itself (follow-ups 3.5: a hand list left out the shell, the copy tool's
        makers and the relight's own modules), each with its SHA-256; not a module none of them imports (the lab's
        deploy fixture)."""
        m = self.make().run()
        root = Path(build.__file__).resolve().parents[2]
        named = set(m['tools'])
        for module in ('shell', 'cover_blocks', 'buildings', 'native_spawns', 'frac_walls', 'shadowmaps', 'shadows',
                       'bounce', 'lightmap_encode', 'relight', 'native_copy', 'native_lights', 'light_factory',
                       'native_effects', 'native_sounds', 'native_flares', 'lightmap_writer', 'intro_copy',
                       'stream_copy', 'transplant', 'map_frame', 'inline_lighting'):
            self.assertIn('tools/bake/%s.py' % module, named)
        for module in ('decomp', 'upkinfo', 'package_grow', 'seed_map', 'seed_tiles'):
            self.assertIn('tools/upk/%s.py' % module, named)
        self.assertNotIn('tools/bake/deploy_fixture.py', named)
        for k in named:
            self.assertEqual(m['tools'][k], build.sha256(root / k))

    def test_an_intro_without_a_landing_for_the_map_is_streamed_as_it_is(self):
        self.landing = False
        m = self.make().run()
        self.assertEqual((m['intros'], m['replaceStreams']), ([], {}))
        self.assertNotIn('CookedPCConsole/%s.upk' % INTRO, m['files'])
        self.assertIn('StreamingMaps[0]=( MapName="CIN_DropshipIntros"', m['config']['maps'][0])

    def test_a_map_with_missions_that_land_differently_gets_an_intro_copy_for_each(self):
        bar = record('bar')
        terror = mapsini.set_field(bar.replace('CIN_DropshipIntros', 'CIN_FastropeIntros'), 'MissionType',
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
        self.assertIn('DisplayName="%s (Beta/Functionality Complete Urban Bar, Terror) |0"' % VARIANT, m['config']['maps'][1])
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
        self.assertEqual(sorted(m['files']), sorted('CookedPCConsole/%s' % n for n in ('%s.upk' % VARIANT, '%s.upk' % INTRO)))
        self.assertEqual(m['lightingInside']['cache'], cache)
        self.assertEqual((m['patch'], m['streams'], m['config']['streamSlots']), (None, [], [None]))
        self.assertEqual(m['config']['maps'][0].count('StreamingMaps['), record('bar').count('StreamingMaps['))
        light, = self.tool('native_copy.py')
        self.assertNotIn('--edit-spec', light)
        readme = (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('(out of rotation; streams %s in place of CIN_DropshipIntros):' % INTRO, readme)
        self.assertNotIn(PATCH, readme)
        # no seed plan without a patch: native_copy.py seeds the copies' tiles itself
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'inside relit map 1 with lightmaps')

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

    def test_texels_changed_in_pieces_not_relit_reach_the_light_stage(self):
        """(review finding 15) The relight's record of texels its writes changed in the lightmaps of pieces it was not
        relighting reaches the light stage as a record of its own (count, largest change, the first pieces), by both
        command lines (native_copy.py --bake, and relight.py alone); a clean record adds nothing."""
        pieces = ['TheWorld.PersistentLevel.XComLevelActor_%d.StaticMeshComponent_0' % k for k in range(25)]
        self.other_changed = dict(textures=2, pieces=pieces, texels=37, largest=0.21)
        for stamp, objects, tool in (('110000', [COPY, DOOR, HIDE], 'native_copy.py'), ('111500', [DOOR], 'relight.py')):
            with self.subTest(tool=tool):
                self.ran.clear()
                self.spec['objects'] = objects
                m = self.make(stamp).run()
                self.assertTrue(any('--cache' in r for r in self.tool(tool)))
                other = next(s for s in m['stages'] if s['stage'] == 'light')['otherPiecesChanged']
                self.assertEqual({k: other[k] for k in ('texels', 'largest', 'count', 'textures')},
                                 dict(texels=37, largest=0.21, count=25, textures=2))
                self.assertEqual(other['pieces'], pieces[:build.OTHER_SHOWN])
        self.other_changed = dict(textures=0, pieces=[], texels=0, largest=0.0)
        m = self.make('112000').run()
        self.assertNotIn('otherPiecesChanged', next(s for s in m['stages'] if s['stage'] == 'light'))

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
        self.assertEqual((m['cache'], m['lightingInside']['cache']), (None, VARIANT + '_Lighting'))
        self.assertNotIn('CookedPCConsole/%s_Lighting.tfc' % VARIANT, m['files'])

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

    def test_a_project_whose_only_change_is_its_missions_builds(self):
        """(review finding 39) The missions list and the map picture are changes like any other: a project that only
        narrows its missions, or only gives its map a picture (the LWR 3 map packs' use), builds the map unchanged
        with them, its lighting kept."""
        self.spec['objects'] = []
        self.doc['missions'] = [dict(record=0)]
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        m = self.make().run()
        self.assertTrue(m['lightingUnchanged'])
        self.assertEqual((m['config']['missionsFromProject'], m['config']['missions']), (True, ['Abduction']))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), BASE)

    def test_a_project_whose_only_change_is_its_picture_builds(self):
        self.spec['objects'] = []
        digest = self.with_picture()
        m = self.make('111500').run()
        self.assertEqual((m['lightingUnchanged'], m['picture']['sha256']), (True, digest))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         BASE + b' +picture ' + digest.encode())

    def test_the_missions_the_compiler_keeps_are_the_records_written(self):
        """(review finding 39) An entry of the missions list the compiler leaves out is not written either: the
        records are the report's `missions` (None: every record of the base map)."""
        self.doc['missions'] = [dict(record=5), dict(record=0)]
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        self.report['missions'] = [dict(record=0)]
        self.assertEqual(self.make().run()['config']['missions'], ['Abduction'])
        self.report['missions'] = None          # none of its entries could be written: every record
        m = self.make('111500').run()
        self.assertNotIn('missionsFromProject', m['config'])

    def test_a_map_size_the_compiler_left_out_is_not_read(self):
        """(review finding 39) The compiler leaves out a size it can't build (record `stage`) and the rest builds: the
        shell stage then reads nothing of `stage`, and the map keeps its own size."""
        sys.path.insert(0, str(Path(build.__file__).resolve().parents[1] / 'bake'))
        import package
        import shell
        self.doc['stage'] = dict(grid=[20, 10], lines=True)
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        with mock.patch.object(package, 'Package', lambda path: None), \
                mock.patch.object(shell, 'needs', lambda p, building=False: []):
            # the same size, kept: the shell stage runs on it
            self.make().run()
            self.assertEqual(len(self.tool('shell.py')), 1)
            self.ran.clear()
            self.report['leftOut'] = [dict(code='stage-grid', message='the size is left out', record='stage')]
            m = self.make('111500').run()
        self.assertEqual(self.tool('shell.py'), [])
        self.assertNotIn('shell', m)
        self.assertEqual(m['leftOut'], [dict(actor='', code='stage-grid', message='the size is left out')])

    def test_a_picture_that_cannot_be_written_is_a_note_and_the_bake_is_kept(self):
        """(review finding 39) A picture the writer fails on no longer fails the build after its whole bake: it is a
        note, and the map is built without a picture of its own."""
        self.with_picture()

        def broken(src, dst, png):
            raise ValueError('not a picture the writer can read')
        b = self.make()
        b.picture_tool = broken
        m = b.run()
        self.assertNotIn('picture', m)
        self.assertIn('could not be written', m['pictureNote'])
        self.assertIn('not a picture the writer can read', m['pictureNote'])
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'inside relit map 1 seeded with lightmaps')

    def test_patchtool_works_in_the_builds_folder_by_default(self):
        import datetime
        b = build.Build(build.BuildInputs(self.project, self.tmp.name, self.output, self.lwr, self.udk,
                                          now=datetime.datetime(2026, 11, 7), run=self.run_tool, seed=self.seed,
                                          echo=lambda *_: None))
        self.assertEqual(b.patch_work, self.output / '.work' / 'patchtool')

    def test_a_project_with_a_map_picture_builds_it_into_the_map(self):
        digest = self.with_picture()
        m = self.make().run()
        pkg = self.output / VARIANT
        self.assertEqual(m['picture'], dict(sha256=digest, format='DXT1'))
        self.assertNotIn('pictureNote', m)
        # written after the seeds, into the package's map, from the project's kept file; the lightmaps go in last
        self.assertEqual([s['stage'] for s in m['stages']], ['snapshot', 'compile', 'patch', 'light', 'seeds', 'picture', 'inside'])
        self.assertEqual(m['stages'][-2], dict(m['stages'][-2], written=True, export=7, how='added', sha256=digest, format='DXT1'))
        built = pkg / 'CookedPCConsole' / ('%s.upk' % VARIANT)
        self.assertEqual(built.read_bytes(), b'inside relit map 1 seeded +picture ' + digest.encode() + b' with lightmaps')
        (src, dst, png), = self.pictured
        self.assertEqual(Path(png), self.project.parent / '.workshop' / PICTURE_PROJECT / 'picture.png')
        self.assertTrue(src.endswith('%s.upk' % VARIANT) and 'package' in src and 'pictured' in dst)
        self.assertFalse(Path(dst).exists())            # moved into the package
        # the manifest's hash is the map's with its picture, and the tool is named
        self.assertEqual(m['files']['CookedPCConsole/%s.upk' % VARIANT], build.sha256(built))
        self.assertIn('tools/bake/map_frame.py', m['tools'])
        readme = (pkg / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn('%s.upk holds the project\'s map picture (MapPicture, 512 x 256, DXT1)' % VARIANT, readme)
        self.assertEqual(json.loads((pkg / 'manifest.json').read_text(encoding='utf-8'))['picture'], m['picture'])
        # a quick build has it too
        q = self.make('111000', quick=True).run()
        self.assertEqual((q['picture'], q['stages'][-1]['stage']), (dict(sha256=digest, format='DXT1'), 'picture'))
        self.assertTrue(built.read_bytes().endswith(b' +picture ' + digest.encode()))

    def test_a_map_held_a_moment_by_another_program_is_still_put_in_place(self):
        # the map with its picture and the map with its lightmaps inside are put in place through atomic_files.replace,
        # which tries again while Windows refuses (a virus scanner or an indexer holding the map a moment, KB-10)
        digest = self.with_picture()
        real, refused = os.replace, collections.Counter()

        def replace(src, dst, *args, **kwargs):
            stage = Path(src).parent.name
            if stage in ('pictured', 'inside') and refused[stage] < 2:
                refused[stage] += 1
                raise PermissionError(13, 'The process cannot access the file because it is being used by another process', str(dst))
            return real(src, dst, *args, **kwargs)
        with mock.patch('os.replace', replace):
            m = self.make().run()
        self.assertEqual(dict(refused), dict(pictured=2, inside=2))
        built = self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)
        self.assertEqual(built.read_bytes(), b'inside relit map 1 seeded +picture ' + digest.encode() + b' with lightmaps')
        self.assertEqual((m['picture'], m['lightingInside']['cache']), (dict(sha256=digest, format='DXT1'), VARIANT + '_Lighting'))
        self.assertEqual(m['files']['CookedPCConsole/%s.upk' % VARIANT], build.sha256(built))

    def test_a_snapshots_build_takes_the_picture_captured_beside_it(self):
        """(review finding 12) A build of the server's snapshot (--saved-file) takes the picture captured beside it
        (project.picture.png) and nothing else: a picture chosen since, kept with the project, is not this build's. The
        manifest names the bytes it read."""
        import pictures
        digest = self.with_picture()
        attempt = Path(self.tmp.name) / 'attempt'
        attempt.mkdir()
        snapshot = attempt / 'project.json'
        snapshot.write_bytes(self.project.read_bytes())
        kept = self.project.parent / '.workshop' / PICTURE_PROJECT / 'picture.png'
        pictures.beside(snapshot).write_bytes(kept.read_bytes())
        self.with_picture(colour=(200, 10, 10))         # chosen since: the store's now, not the snapshot's

        def make(stamp):
            import datetime
            return build.Build(build.BuildInputs(
                snapshot, self.tmp.name, self.output, self.lwr, self.udk, patch_work=self.work,
                now=datetime.datetime(2026, 11, 7, 11, int(stamp), 0), run=self.run_tool, seed=self.seed,
                echo=self.said.append, named=self.name_copy, picture=self.picture_copy,
                projects=self.project.parent, saved_file=self.project))
        m = make('0').run()
        (_, _, png), = self.pictured
        self.assertEqual(Path(png), pictures.beside(snapshot))
        self.assertEqual(m['picture']['sha256'], digest)
        self.assertEqual((m['project']['sha256'], m['project']['file']),
                         (hashlib.sha256(snapshot.read_bytes()).hexdigest(), str(self.project)))
        # with no copy beside it, the build says the picture is missing (the store's is another)
        pictures.beside(snapshot).unlink()
        m = make('5').run()
        self.assertNotIn('picture', m)
        self.assertIn('not on this computer', m['pictureNote'])

    def test_a_project_without_a_map_picture_builds_none(self):
        m = self.make().run()
        self.assertNotIn('picture', m)
        self.assertNotIn('pictureNote', m)
        self.assertNotIn('picture', [s['stage'] for s in m['stages']])
        self.assertFalse(getattr(self, 'pictured', None))
        self.assertNotIn('map picture', (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1'))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'inside relit map 1 seeded with lightmaps')

    def test_a_picture_whose_file_is_missing_is_a_note_and_the_map_builds_without_it(self):
        digest = self.with_picture(keep=False)
        m = self.make().run()
        self.assertNotIn('picture', m)
        self.assertIn('not on this computer', m['pictureNote'])
        self.assertIn(digest[:12], m['pictureNote'])
        picture, = [s for s in m['stages'] if s['stage'] == 'picture']
        self.assertFalse(picture['written'])
        self.assertFalse(getattr(self, 'pictured', None))
        self.assertTrue(any(line.startswith('note: ') and 'map picture' in line for line in self.said))
        self.assertFalse(any(line.startswith('warning: ') for line in self.said))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'inside relit map 1 seeded with lightmaps')
        self.assertIn('No map picture: the project names a map picture whose file is not on this computer',
                      (self.output / VARIANT / 'README.txt').read_bytes().decode('latin-1'))
        # a malformed record is the same: a note, never a refusal
        self.doc['picture'] = dict(sha256='nope')
        self.project.write_text(json.dumps(self.doc), encoding='utf-8')
        m = self.make('111000').run()
        self.assertIn('malformed', m['pictureNote'])

    def test_a_changed_picture_is_an_ordinary_rebuild(self):
        first = self.with_picture()
        self.make().run()
        second = self.with_picture(colour=(200, 10, 10))
        self.assertNotEqual(first, second)
        m = self.make('111500').run()
        self.assertEqual(m['picture']['sha256'], second)
        self.assertEqual(len(self.tool('native_copy.py')), 2)       # the edit made and lit again, no shortcut
        self.assertIn(b'+picture ' + second.encode(), (self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes())

    def test_the_picture_s_own_writer_adds_the_texture_to_a_real_map(self):
        sys.path.insert(0, str(HERE.parents[1] / 'lab'))
        sys.path.insert(0, str(HERE.parents[1] / 'bake'))
        import labpaths
        import map_frame
        stream, why = labpaths.test_file('XCOM_TRUCKSTOP_STREAM_UPK', labpaths.lwr_cooked('URB_TruckStop_Stream.upk'),
                                         'URB_TruckStop_Stream.upk')
        if not (stream and stream.exists()):
            self.skipTest(why)
        self.with_picture()
        png = self.project.parent / '.workshop' / PICTURE_PROJECT / 'picture.png'
        out = Path(self.tmp.name) / 'pictured.upk'
        report = build.Build._picture(stream, out, png)
        self.assertEqual(report['how'], 'added')

        def read_picture(path):     # the map package's own picture's DXT1 pixels, or None
            found = map_frame.locate(Package(path))
            return found['pixels'] if found else None
        from package import Package
        self.assertEqual(read_picture(out), map_frame.encode_file(png))
        self.assertIsNone(read_picture(stream))

    def test_a_rebuild_replaces_the_package(self):
        self.make('110000').run()
        (self.output / ('%s.zip' % VARIANT)).write_bytes(b'an earlier version\'s zip of the folder')
        self.relit = 2
        m = self.make('111500').run()
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'inside relit map 2 seeded with lightmaps')
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
        """Output names plan 3.4: every name the build may write (the map, its patch, its intro and stream copies) is
        checked against other projects, other builds and the game install before the costly stages, and again as the
        package goes in."""
        self.spec['objects'] = [COPY, HIDE]
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        cases = [
            ('another build lists the intro copy', lambda: self.foreign_build('Other_Variant', files=['%s.upk' % INTRO])),
            ('the install has the intro copy', lambda: (cooked / ('%s.upk' % INTRO)).write_bytes(b'by hand')),
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
                for p in [self.output / 'Other_Variant', cooked / ('%s.upk' % INTRO), self.project.parent / 'copy.json']:
                    shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
        # a build's texture cache never leaves its work folder (its lightmaps go inside the map): a file of the cache's
        # name doesn't stop it
        (cooked / ('%s_Lighting.tfc' % VARIANT)).write_bytes(b'x')
        self.make().run()
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

    def test_the_patch_name_counts_only_when_the_build_makes_a_patch(self):
        """A file of the patch's name in the install (an earlier test's, put there by the lab's patchtool) stops a
        build whose edit needs a patch, and not one made in the map alone, which never writes it."""
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        (cooked / ('%s.upk' % PATCH)).write_bytes(b'an earlier patchtool test of the project')
        self.spec['objects'] = [DOOR]
        with self.assertRaisesRegex(build.BuildError, 'the build would write names that are taken: %s ' % PATCH):
            self.make().run()
        self.spec['objects'] = [COPY]
        m = self.make('111500').run()
        self.assertIsNone(m['patch'])
        self.assertNotIn('CookedPCConsole/%s.upk' % PATCH, m['files'])

    def test_a_snapshot_build_checks_names_against_the_projects_folder_and_names_its_attempt(self):
        """Build queue plan, 9.1 and 9.2: a build of a private snapshot (the queue's) is told the projects folder, so
        other projects' names still stop it; its attempt goes into its id, its work folder and its manifest, with the
        project's own file."""
        self.spec['objects'] = [COPY, HIDE]
        private = Path(self.tmp.name) / 'queue-attempts' / 'a1' / 'project.json'
        private.parent.mkdir(parents=True)
        private.write_text(json.dumps(self.doc), encoding='utf-8')
        (self.project.parent / 'copy.json').write_text(json.dumps(dict(self.doc, id='2222-copy', name='A copy')), encoding='utf-8')
        attempt = '0f8b1234-1d2a-4b6c-8e9f-123456789abc'
        import datetime

        def snapshot_build(projects):
            return build.Build(build.BuildInputs(
                private, self.tmp.name, self.output, self.lwr, self.udk, patch_work=self.work,
                now=datetime.datetime(2026, 11, 7, 11, 0, 0), run=self.run_tool, seed=self.seed,
                echo=lambda *_: None, named=self.name_copy, projects=projects, attempt=attempt,
                saved_file=self.project))
        # without the projects folder the snapshot's own folder is all it sees: the other project's names go unseen
        with self.assertRaisesRegex(build.BuildError, 'the build would write names that are taken'):
            snapshot_build(self.project.parent).run()
        (self.project.parent / 'copy.json').unlink()
        m = snapshot_build(self.project.parent).run()
        self.assertEqual((m['attempt'], m['buildId']), (attempt, '%s-20261107-110000-0f8b1234' % VARIANT))
        self.assertEqual(m['project']['file'], str(self.project))
        self.assertTrue((self.output / '.work' / m['buildId'] / 'logs').is_dir())
        self.assertEqual(json.loads((self.output / VARIANT / 'manifest.json').read_text())['attempt'], attempt)

    TEST_ID, TEST_NAME = '01234567-89ab-4cde-8f01-23456789abcd', '0123456789ab'   # a prefab test's id, its folder's name

    def prefab_test(self, depth, quick=True):
        """A prefab test's Build as prefab_tests.py starts it: the test's project in its own folder
        (<builds>/.prefab-tests/<name>/project.json, carrying prefabTest), the package into its artifacts folder; the
        builds folder padded to `depth` characters. (builds, the test's folder, the Build)."""
        import datetime
        root = Path(self.tmp.name)
        builds = Path(str(root / 'b') + 'x' * (depth - len(str(root / 'b'))))
        folder = builds / '.prefab-tests' / self.TEST_NAME
        (folder / 'artifacts').mkdir(parents=True)
        doc = dict(self.doc, id=self.TEST_ID, prefabTest=dict(id=self.TEST_ID, snapshotHash='0' * 64),
                   output=dict(shipAs='pt_' + self.TEST_NAME, patch='pp_' + self.TEST_NAME))
        (folder / 'project.json').write_text(json.dumps(doc), encoding='utf-8')
        self.spec['objects'] = [COPY, HIDE]       # (a test makes no patch)
        return builds, folder, build.Build(build.BuildInputs(
            folder / 'project.json', self.tmp.name, folder / 'artifacts', self.lwr, self.udk, patch_work=self.work,
            now=datetime.datetime(2026, 11, 7, 11, 0, 0), run=self.run_tool, seed=self.seed, echo=self.said.append,
            quick=quick, named=self.name_copy, picture=self.picture_copy))

    def test_a_prefab_tests_build_works_in_the_tests_folder_and_fits_a_deep_builds_folder(self):
        """KB-12: a prefab test's Build worked in <artifacts>/.work/<Variant>-<stamp> under the test's folder, which
        with a long builds folder passed Windows' 260 characters (the package's intro copy in the work folder, here
        140 characters past the builds folder). It works in the test's own folder, `w`: the deepest file it writes
        is 108 characters past the builds folder (the package's intro copy in place), and the Build passes under a
        builds folder of 140 characters, where the old layout's deepest would be 280."""
        builds, folder, b = self.prefab_test(140)
        variant = 'pt_' + self.TEST_NAME
        old = (folder / 'artifacts' / '.work' / ('%s-20261107-110000' % variant) / 'package' / 'CookedPCConsole'
               / ('CIN_DropshipIntros_%s.upk' % variant))
        self.assertGreater(len(str(old)), 259)
        m = b.run()
        self.assertEqual(m['work'], str(folder / 'w'))
        self.assertTrue((folder / 'w' / 'logs').is_dir())
        self.assertEqual([p.name for p in (folder / 'artifacts' / '.work').glob('%s-*' % variant)], [])
        deepest = max(len(str(p)) - len(str(builds)) for p in builds.rglob('*'))
        self.assertEqual(deepest, 108)
        self.assertLessEqual(len(str(builds)) + deepest, 259)
        self.assertEqual(sorted(m['files']), ['CookedPCConsole/CIN_DropshipIntros_%s.upk' % variant,
                                              'CookedPCConsole/%s.upk' % variant])

    def test_a_build_whose_files_would_pass_windows_path_limit_stops_before_its_first_stage(self):
        """KB-12, decision D4: where long paths are off, a build whose deepest file would pass Windows' 259
        characters stops before the snapshot stage with the code path-too-long, saying by how many characters and that
        the builds folder should be on a shorter path; nothing is run or made. Here a prefab test under a builds folder
        of 160 characters (its package's intro copy would be 268). One of 145 builds, its decoded maps not kept (a
        note: decoding them again is slower and stops nothing). With long paths on there is no limit to keep to."""
        with mock.patch.object(build, 'long_paths', return_value=False):
            _, folder, b = self.prefab_test(145)
            m = b.run()
            self.assertIn('CookedPCConsole/CIN_DropshipIntros_pt_%s.upk' % self.TEST_NAME, m['files'])
            self.assertTrue(any(s.startswith('note: the decoded maps can\'t be kept in the work folder') for s in self.said))
            self.ran.clear()
            builds, folder, b = self.prefab_test(160)
            with self.assertRaises(build.BuildError) as refused:
                b.run()
        self.assertEqual(refused.exception.code, 'path-too-long')
        words = str(refused.exception)
        self.assertIn('too long for this build by 9 characters', words)
        self.assertIn('the package\'s CIN_DropshipIntros_pt_%s.upk would be written at %s (268 characters)'
                      % (self.TEST_NAME, folder / 'artifacts' / ('pt_' + self.TEST_NAME) / 'CookedPCConsole'
                         / ('CIN_DropshipIntros_pt_%s.upk' % self.TEST_NAME)), words)
        self.assertIn('Put the builds folder on a path at least 9 characters shorter', words)
        self.assertEqual((b.stages, self.ran), ([], []))
        self.assertFalse((folder / 'w').exists())
        with mock.patch.object(build, 'long_paths', return_value=True):
            b.check_paths([b.variant] + b.intro_names())       # (the same build: nothing to keep to)

    def test_a_projects_build_whose_stream_copy_would_pass_the_limit_stops_after_its_compile(self):
        """The names the compile adds (a copy of a stream the edit changes) are checked in preflight, before the costly
        stages: a project's Build (not a test's) whose stream copy would pass the limit stops there, path-too-long."""
        import datetime
        stream = 'URB_Bar_a_long_mission_stream_name'
        (self.lwr / 'XEW/XComGame/CookedPCConsole' / ('%s.upk' % stream)).write_bytes(b'a stream')
        self.spec = dict(self.spec, objects=[COPY], streamHides={stream: ['XComLadder_11']})
        root = Path(self.tmp.name)
        output = Path(str(root / 'o') + 'x' * (145 - len(str(root / 'o'))))
        b = build.Build(build.BuildInputs(
            self.project, self.tmp.name, output, self.lwr, self.udk, patch_work=self.work,
            now=datetime.datetime(2026, 11, 7, 11, 0, 0), run=self.run_tool, seed=self.seed, echo=self.said.append,
            named=self.name_copy, picture=self.picture_copy))
        with mock.patch.object(build, 'long_paths', return_value=False), self.assertRaises(build.BuildError) as refused:
            b.run()
        self.assertEqual(refused.exception.code, 'path-too-long')
        self.assertIn('too long for this build by 7 characters: the package\'s %s_%s.upk' % (stream, VARIANT),
                      str(refused.exception))
        self.assertEqual([s['stage'] for s in b.stages], ['snapshot', 'compile'])
        self.assertEqual(self.ran, [])

    def test_a_given_work_folder_is_the_builds(self):
        """BuildInputs.work (--work): the build works there, whatever the project."""
        import datetime
        self.spec['objects'] = [COPY, HIDE]
        work = Path(self.tmp.name) / 'elsewhere'
        m = build.Build(build.BuildInputs(
            self.project, self.tmp.name, self.output, self.lwr, self.udk, patch_work=self.work,
            now=datetime.datetime(2026, 11, 7, 11, 0, 0), run=self.run_tool, seed=self.seed, echo=self.said.append,
            quick=True, named=self.name_copy, picture=self.picture_copy, work=work)).run()
        self.assertEqual(m['work'], str(work))
        self.assertTrue((work / 'logs' / 'native-copy.log').is_file())
        self.assertFalse((self.output / '.work' / m['buildId']).exists())

    def test_a_pinned_command_line_reads_nothing_from_the_settings(self):
        """Build queue plan, 9.1: the server's queue passes every folder, and the installs the names are checked
        against, so a setting saved after the capture changes nothing of the build."""
        seen = {}

        class Recorder:
            def __init__(self, inputs):
                seen.update(inputs=inputs)

            def run(self):
                return {}
        attempt = '0f8b1234-1d2a-4b6c-8e9f-123456789abc'
        with mock.patch.object(build.settings_module, 'load_settings', side_effect=AssertionError('settings read')), \
                mock.patch.object(build, 'Build', Recorder):
            code = build.main([str(self.project), '--pinned', '--game', str(self.lwr), '--cache', 'C', '--output', 'O',
                               '--projects', 'P', '--check-game', 'I', '--attempt', attempt, '--saved-file', 'S',
                               '--work', 'W'])
        self.assertEqual(code, 0)
        i = seen['inputs']
        self.assertEqual((i.project, i.cache, i.output, i.lwr, i.udk),
                         (self.project, Path('C'), Path('O'), self.lwr, None))      # no --udk: no UDK
        self.assertEqual((i.games, i.projects, i.attempt, i.saved_file, i.work),
                         ([Path('I')], Path('P'), attempt, Path('S'), Path('W')))
        with self.assertRaises(SystemExit):
            build.main([str(self.project), '--pinned', '--game', str(self.lwr)])         # a folder missing
        with self.assertRaises(SystemExit):
            build.main([str(self.project), '--attempt', 'not-a-uuid'])

    def test_a_package_of_before_rebuilds_with_its_lightmaps_inside_and_quick_builds_have_none(self):
        """Output names plan 4: a project's package built with Lighting_<n> (before 16 November 2026) is replaced by
        one whose relight writes <Variant>_Lighting, whose lightmaps then go inside the map (19 November 2026): no
        .tfc in the package; a quick build in between has none to put in; the next full build has them inside again."""
        self.spec['objects'] = [COPY, HIDE]
        old = self.foreign_build(VARIANT, self.doc['id'], files=['%s.upk' % VARIANT, 'Lighting_4242.tfc'])
        m = json.loads((old / 'manifest.json').read_text(encoding='utf-8'))
        (old / 'manifest.json').write_text(json.dumps(dict(m, cache='Lighting_4242')), encoding='utf-8')
        caches = []
        for stamp, quick in (('110000', False), ('111000', True), ('112000', False)):
            m = self.make(stamp, quick=quick).run()
            caches.append((m['cache'], sorted(Path(f).name for f in m['files'] if f.endswith('.tfc')),
                           (m.get('lightingInside') or {}).get('cache')))
        named = VARIANT + '_Lighting'
        self.assertEqual(caches, [(None, [], named), (None, [], None), (None, [], named)])
        self.assertFalse((self.output / VARIANT / 'CookedPCConsole' / 'Lighting_4242.tfc').exists())
        self.assertFalse(list((self.output / VARIANT).rglob('*.tfc')))
        self.assertIn('its lightmaps inside the map', (self.output / VARIANT / 'README.txt').read_text(encoding='latin-1'))

    def test_a_build_whose_lightmaps_are_all_in_the_map_already_moves_none(self):
        """(smaller built maps plan, S3) A relight that writes only textures held inside the map (the copies' own,
        sized to what they read) writes no cache, or a cache no texture names: the lightmaps are inside all the same,
        none moved, no .tfc in the package, and the README says so."""
        self.no_cache = True
        m = self.make('110000').run()
        named = VARIANT + '_Lighting'
        self.assertEqual((m['cache'], m['lightingInside']),
                         (None, dict(cache=named, textures=0, mips=0, bytes=0, held=dict(textures=3, bytes=1000, whole=0))))
        self.assertFalse(list((self.output / VARIANT).rglob('*.tfc')))
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(), b'relit map 1 seeded')
        self.assertIn('its lightmaps inside the map', (self.output / VARIANT / 'README.txt').read_text(encoding='latin-1'))
        # a cache that no texture of the map names: the same
        self.no_cache = False
        saved = build.inline_map
        build.inline_map = lambda src, dst, cache, tfc: (_ for _ in ()).throw(build.NotNamed('no texture names it'))
        try:
            m = self.make('111000').run()
        finally:
            build.inline_map = saved
        self.assertEqual((m['cache'], m['lightingInside']['textures']), (None, 0))
        self.assertFalse(list((self.output / VARIANT).rglob('*.tfc')))

    def test_a_map_holding_many_lightmaps_says_so(self):
        """(decision D4) More than 100 MB of lightmaps inside the map: a warning that says what it costs in the game;
        a map the count can't read builds all the same, with a note."""
        self.held = dict(textures=600, bytes=150 * 1000 * 1000, cached=0, whole=290)
        m = self.make('110000').run()
        warning, = [line for line in self.said if line.startswith('warning: ')]
        self.assertIn('150 MB of lightmaps (290 whole 1,024-texel atlases)', warning)
        self.assertIn('keeps them in memory for the whole battle', warning)
        self.assertEqual(m['lightingInside']['held']['bytes'], 150 * 1000 * 1000)
        self.said.clear()
        saved = build.lightmaps_held
        build.lightmaps_held = lambda path: (_ for _ in ()).throw(ValueError('not a package'))
        try:
            m = self.make('111000').run()
        finally:
            build.lightmaps_held = saved
        self.assertIsNone(m['lightingInside']['held'])
        self.assertIn('note: the lightmaps inside the map could not be counted (not a package)', self.said)

    def test_a_map_that_cannot_take_its_lightmaps_in_fails_the_build(self):
        """No build ships a texture cache: a map whose lightmaps can't be put inside it fails the build, saying why,
        and leaves the last good package as it was."""
        first = self.make('110000').run()
        self.inside_fails = 'not a package'
        with self.assertRaisesRegex(build.BuildError, r'the baked lightmaps could not be put inside the map \(not a package\)'):
            self.make('111000').run()
        m = json.loads((self.output / VARIANT / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(m['buildId'], first['buildId'])
        self.assertFalse(list((self.output / VARIANT).rglob('*.tfc')))

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
        # no journal is left, and the variant's guard is free again (the lock file stays: the OS holds the lock)
        import publication
        self.assertEqual(publication.pending(self.output), [])
        lock = publication.FileLock(publication.lock_path(self.output, VARIANT))
        self.assertTrue(lock.acquire())
        lock.release()

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

    def test_a_failed_build_prunes_old_work_too(self):
        """(review findings 49 and 62) The prune runs after a failed build as after a built one: its own work folder
        and kept pieces stay as they are, however old, and kept pieces no build has used for PIECE_DAYS go. A
        variant no project ships as is left whole: the build knows one projects folder (the server prunes those)."""
        import os
        import time
        import builds as build_runs
        work = self.output / '.work'
        for stamp in ('20261101-100000', '20261102-100000', '20261103-100000'):
            old = work / ('%s-%s' % (VARIANT, stamp))
            (old / 'lit').mkdir(parents=True)
            (old / 'lit' / 'URB_Bar.upk').write_bytes(b'x' * 10)
            (old / 'logs').mkdir()
        unowned = work / 'Nobodys_Variant-20261001-100000' / 'lit'
        unowned.mkdir(parents=True)
        long_ago = time.time() - (build_runs.PIECE_DAYS + 1) * 86400
        stale, own = work / 'pieces' / 'Other_Variant', work / 'pieces' / VARIANT
        for kept in (stale, own):
            kept.mkdir(parents=True)
            (kept / 'piece.npz').write_bytes(b'kept')
            os.utime(kept / 'piece.npz', (long_ago, long_ago))
            os.utime(kept, (long_ago, long_ago))
        self.failing = 'native_copy'
        with self.assertRaises(build.BuildError):
            self.make('110000').run()
        self.assertEqual([f.name for f in (work / ('%s-20261101-100000' % VARIANT)).iterdir()], ['logs'])
        self.assertTrue((work / ('%s-20261102-100000' % VARIANT) / 'lit' / 'URB_Bar.upk').is_file())
        failed, = (f for f in work.glob('%s-20261107-110000*' % VARIANT))
        self.assertTrue((failed / 'logs').is_dir())
        self.assertFalse(stale.exists())
        self.assertTrue((own / 'piece.npz').is_file())
        self.assertTrue(unowned.is_dir())
        self.assertTrue(any('old build work pruned' in line for line in self.said))

    def test_a_failed_build_leaves_the_last_good_package(self):
        first = self.make('110000').run()
        self.failing = 'native_copy'
        with self.assertRaises(build.BuildError):
            self.make('112000').run()
        self.assertEqual(json.loads((self.output / VARIANT / 'manifest.json').read_text())['buildId'], first['buildId'])

    def failing_once(self, tool, says='', times=1):
        """The first `times` runs of `tool` fail as Build._run says a failure ("<tool> failed (exit 1); see <log>"),
        their log ending with `says` (a str, or one per failure); later ones go through."""
        runs, plain = [], Builds.run_tool.__get__(self)

        def run(args, log):
            mine = any(tool in str(a) for a in args)
            if mine and '--copies' in [str(a) for a in args]:     # the edit as this run was given it
                self.edits_seen = getattr(self, 'edits_seen', []) + [
                    json.loads(Path(args[[str(a) for a in args].index('--copies') + 1]).read_text(encoding='utf-8'))]
            if mine and len(runs) < times:
                runs.append(1)
                self.ran.append([str(a) for a in args])
                text = says if isinstance(says, str) else says[len(runs) - 1]
                Path(log).write_text('ran\nTraceback (most recent call last):\nValueError: %s\n' % text, encoding='utf-8')
                raise build.BuildError('%s failed (exit 1); see %s' % (tool, log))
            if mine:
                runs.append(1)
            return plain(args, log)
        self.run_tool = run

    def test_untried_pieces_the_build_cannot_make_are_left_out_and_the_rest_is_built(self):
        # (14 November 2026: warn and build what our own gates held back. The compiler marks such a copy
        # untried; when the copy stage fails with one in the edit, the Build takes them out and builds the rest)
        tried = dict(COPY, untried=[False])
        untried = dict(COPY, labels=['move:SkeletalMeshActor_30'], classes=['SkeletalMeshActor'], untried=[True],
                       **{'from': ['SkeletalMeshActor_30']})
        moved = dict(HIDE, alsoHide=['SkeletalMeshActor_30'], labels=['move:SkeletalMeshActor_30'])
        self.spec['objects'] = [tried, untried, moved]
        self.failing_once('native_copy', 'bad property name in TheWorld.PersistentLevel.SkeletalMeshActor_30')
        b = self.make()
        m = b.run()
        first, second = self.tool('native_copy.py')
        edit = json.loads(Path(second[second.index('--copies') + 1]).read_text(encoding='utf-8'))
        # the tried copy is still made; the untried move is gone with its hide, so the piece stays where the map has it
        self.assertEqual(([c['label'] for c in edit['copies']], edit['hides']), (['XComLevelActor_1_copy1'], []))
        stage = next(s for s in m['stages'] if s['stage'] == 'leftout')
        self.assertEqual((stage['count'], [p['code'] for p in stage['pieces']], stage['pieces'][0]['actor']),
                         (1, ['untried-failed'], 'SkeletalMeshActor_30'))
        self.assertIn('stays where the map has it', stage['pieces'][0]['message'])
        self.assertEqual([row['code'] for row in m['leftOut']], ['untried-failed'])
        # compile-report.json, which the build window says has them all, has the Build's own too, marked by its stage
        report = json.loads((b.work / 'compile-report.json').read_text(encoding='utf-8'))
        self.assertEqual([(e['entity'], e['code'], e['stage']) for e in report['leftOut']],
                         [('SkeletalMeshActor_30', 'untried-failed', 'leftout')])
        self.assertEqual(report['counts']['leftOut'], 1)
        self.assertNotIn('leftOut', self.report['counts'])
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
        self.failing_once('native_copy', 'making XComLevelActor_1_copy1 failed')
        with self.assertRaises(build.BuildError) as caught:
            self.make('112000').run()
        self.assertIn('nothing of the project can be built', str(caught.exception))

    def test_a_failure_that_names_no_untried_piece_is_not_run_again(self):
        """(review finding 40) Untried copies are dropped and the stages run again only when the failing tool names
        one of them (its message or its log's last lines); else the failure is the build's own, said at once."""
        self.spec['objects'] = [dict(COPY, untried=[True])]
        self.failing_once('native_copy', 'the disk is full')
        with self.assertRaisesRegex(build.BuildError, 'native_copy failed'):
            self.make().run()
        self.assertEqual(len(self.tool('native_copy.py')), 1)

    def test_only_the_untried_pieces_a_failure_names_are_dropped_with_what_depends_on_them(self):
        """(review finding 40) Of two untried copies, the one the failure names is dropped, with its glow light and
        its group (left with one piece, which no longer breaks with anything); a second failure that names the other
        drops it too, and the stage lists both. The 'nothing left' test is the compile step's (has_work): a mission
        object's move left keeps the build going."""
        first = dict(COPY, labels=['SkeletalMeshActor_30_copy1'], classes=['SkeletalMeshActor'], untried=[True],
                     breakGroups=[1], **{'from': ['SkeletalMeshActor_30']})
        second = dict(COPY, labels=['SkeletalMeshActor_31_copy2'], classes=['SkeletalMeshActor'], untried=[True],
                      **{'from': ['SkeletalMeshActor_31']})
        prop = dict(COPY, labels=['XComDestructibleActor_4_copy3'], classes=['XComDestructibleActor'], breakGroups=[1],
                    untried=[False], **{'from': ['XComDestructibleActor_4']})
        glow = dict(LIGHTS, deletes=[], changes=[], adds=[], area=[
            dict(op='copy', name='GeneratedMeshAreaLight_1_SkeletalMeshActor_30_copy1', light='GeneratedMeshAreaLight_1',
                 owner='SkeletalMeshActor_30', ownerEntity='SkeletalMeshActor_30_copy1', location=[0, 0, 0], rotation=[0, 0, 0])])
        self.spec['objects'] = [first, second, prop, glow]
        self.failing_once('native_copy', ['bad property in SkeletalMeshActor_30_copy1', 'SkeletalMeshActor_31 has no mesh'], times=2)
        m = self.make().run()
        self.assertEqual(len(self.tool('native_copy.py')), 3)
        before, edit, last = self.edits_seen
        self.assertEqual(before['copies'][2]['breakGroup'], 1)
        # after the first: the named copy gone, its glow light with it, and its group (now one prop) unlinked
        self.assertEqual([c['label'] for c in edit['copies']], ['SkeletalMeshActor_31_copy2', 'XComDestructibleActor_4_copy3'])
        self.assertNotIn('breakGroup', edit['copies'][1])
        self.assertEqual(edit['lights']['area'], [])
        self.assertEqual([c['label'] for c in last['copies']], ['XComDestructibleActor_4_copy3'])
        stage = [s for s in m['stages'] if s['stage'] == 'leftout'][-1]
        self.assertEqual(([p['actor'] for p in stage['pieces']], stage['count']),
                         (['SkeletalMeshActor_30_copy1', 'SkeletalMeshActor_31_copy2'], 2))
        self.assertEqual([s.get('groupsUnlinked') for s in m['stages'] if s['stage'] == 'leftout'], [[1], None])
        self.assertIsNone(m['lights'])
        # the compile step's own test: untried copies alone beside a mission object's move still leave work
        self.ran.clear()
        self.spec['objects'] = [dict(second, breakGroups=[0])]
        self.spec['streamMoves'] = {'URB_Bar_CNH': [dict(actor='XComSpawnPoint_1', location=[0, 0, 0], rotation=[0, 0, 0])]}
        self.failing_once('native_copy', 'SkeletalMeshActor_31 has no mesh')
        b = self.make('113000')
        b.stream_tile_boxes = lambda: []
        b.stream_copies = lambda cooked: {}
        self.assertIn('leftout', [s['stage'] for s in b.run()['stages']])

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
        self.assertEqual((self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT)).read_bytes(),
                         b'inside relit map 1 with lightmaps')
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
        self.assertNotIn('EXP-26', readme)
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

    def test_the_export_asked_for_is_one_with_light_metadata(self):
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
