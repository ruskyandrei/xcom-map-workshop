"""The base map's spawn points and who uses them (export 33; private/plans/todo/editor-spawns-implementation-plan.md,
SP1), on the install's packages: URB_Bar's pods and Meld points, Police Station's and HQ assault's wave points, Pier
A's scripted drop-ins, Slaughterhouse's bomb group with its helper point. Skipped where the install isn't there."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export  # noqa: E402
import scene_metadata  # noqa: E402
from package import Package  # noqa: E402
from settings import lwr_cooked  # noqa: E402

COOKED = Path(lwr_cooked() or 'no-install-configured')


def package(name):
    path = COOKED / f'{name}.upk'
    if not path.exists():
        raise unittest.SkipTest(f'{name} not available')
    return Package(path)


def wave_uses(record):
    return [u for u in record['uses'] if u['how'] == 'wave']


class BarSpawns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = package('URB_Bar')
        cls.records = scene_metadata.spawn_metadata(cls.p, scene_metadata.landing_metadata(cls.p))

    def test_five_pods_and_four_meld_points_with_where_each_value_comes_from(self):
        pods = [r for r in self.records if r['kind'] == 'pod']
        meld = [r for r in self.records if r['kind'] == 'meld']
        self.assertEqual(sorted(r['values']['podIndex']['value'] for r in pods), [0, 1, 2, 3, 4])
        self.assertTrue(all(r['values']['podIndex']['from'] == 'saved' for r in pods))
        # the pods save no bUse: the class's default
        self.assertTrue(all(r['values']['use'] == {'value': True, 'from': 'class'} for r in pods))
        self.assertTrue(all(r['values']['commander'] == {'value': False, 'from': 'class'} for r in pods))
        self.assertEqual(len(meld), 4)
        turns = sorted((r['values']['difficulty']['value'], r['values']['difficulty']['from'],
                        r['values']['destroyedOnTurn']['value']) for r in meld)
        # the two easy points save no difficulty and turn 4; the two hard ones save Hard and turn 8
        self.assertEqual(turns, [('Easy', 'class', 4), ('Easy', 'class', 4), ('Hard', 'saved', 8), ('Hard', 'saved', 8)])
        self.assertTrue(all(r['values']['spawnGroup'] == {'value': 0, 'from': 'class'} for r in meld))
        self.assertTrue(all(r['listed'] for r in pods + meld))
        self.assertTrue(all('unread' not in r for r in self.records))

    def test_the_landings_actors_carry_their_landing(self):
        owned = [r for r in self.records if r['landing']]
        # the start and six soldier points of its one landing (its other twelve XComSpawnPoints are multiplayer points)
        self.assertEqual(Counter(r['kind'] for r in owned), Counter({'soldier': 6, 'start': 1}))
        self.assertEqual({r['landing'] for r in owned}, {'PrefabInstance_19'})
        points = [r for r in self.records if r['actorClass'] == 'XComSpawnPoint']
        self.assertEqual(len(points), 18)
        self.assertEqual(Counter(r['values']['unitType']['value'] for r in points if not r['landing']),
                         Counter({'UNIT_TYPE_MPTeamOne': 6, 'UNIT_TYPE_MPTeamTwo': 6}))

    def test_a_volume_has_its_box_and_a_point_its_pose(self):
        volume = next(r for r in self.records if r['kind'] == 'noSpawn')
        self.assertLess(volume['box']['min'][0], volume['box']['max'][0])
        # (export 34: its two switches, both on in the game's class default; the Bar's save neither)
        for r in self.records:
            if r['kind'] == 'noSpawn':
                self.assertEqual(r['values'], {'aliens': {'value': True, 'from': 'class'}, 'civilians': {'value': True, 'from': 'class'}})
                self.assertEqual(r['other'], [])
        pod = next(r for r in self.records if r['kind'] == 'pod')
        self.assertTrue(pod['savesRotation'])
        self.assertEqual(pod['rotation'], [0, -16384, 0])


class StreamSpawns(unittest.TestCase):
    def test_police_stations_wave_points(self):
        objects = scene_metadata.mission_objects(package('URB_PoliceStation_CNH'))
        drops = [o for o in objects if o['kind'] == 'dropIn']
        self.assertEqual(len(drops), 24)
        self.assertEqual(sum(len(wave_uses(o)) for o in drops), 36)
        self.assertTrue(all(wave_uses(o) for o in drops))
        # a point in two groups is reported twice, each with its set, wave, group and place in the list
        shared = [o for o in drops if len({(u['set'], u['wave'], u['group']) for u in wave_uses(o)}) > 1]
        self.assertTrue(shared)
        self.assertTrue(all(u['role'] == 'destination' and u['index'] >= 1 for o in drops for u in wave_uses(o)))
        self.assertTrue(all(o['listed'] for o in drops))

    def test_hq_assaults_origin_points(self):
        objects = scene_metadata.mission_objects(package('EWI_HQAssault_Stream'))
        origins = [u for o in objects for u in wave_uses(o) if u['role'] == 'origin']
        self.assertEqual(len(origins), 34)
        self.assertIn(dict(how='wave', by='XComWaveSystem_1', set=17, wave=1, group=1, index=1, role='origin'), origins)

    def test_pier_as_scripted_drop_ins(self):
        objects = scene_metadata.mission_objects(package('URB_PierA_Stream'))
        best = Counter()
        for o in objects:
            if o['kind'] != 'dropIn': continue
            hows = {u['how'] for u in o['uses']}
            best['direct' if 'direct' in hows else 'indirect' if 'indirect' in hows else 'none'] += 1
        self.assertEqual(best, Counter(direct=6, indirect=9, none=3))
        point = next(o for o in objects if o['actor'].endswith('.XComSpawnPoint_Alien_3'))
        self.assertIn(dict(by='SeqAct_SpawnAlien_4', byClass='SeqAct_SpawnAlien', how='direct', link='SpawnPoints'), point['uses'])
        listed = next(o for o in objects if o['actor'].endswith('.XComSpawnPoint_Alien_1'))
        use = next(u for u in listed['uses'] if u['how'] == 'indirect')
        self.assertEqual((use['by'], use['link']), ('SeqAct_AccessObjectList_2', 'Object List'))
        pod = next(o for o in objects if o['kind'] == 'pod')
        self.assertEqual(pod['values']['forceType'], {'value': True, 'from': 'saved'})

    def test_the_bomb_group_has_its_helper_point(self):
        objects = scene_metadata.mission_objects(package('URB_Slaughterhouse_Stream'))
        groups = {}
        for o in objects:
            if o['group']: groups.setdefault(o['group'], []).append(o)
        bomb = groups['bomb']
        self.assertEqual(len(bomb), 11)
        helper = next(o for o in bomb if o['role'] == 'point')
        self.assertEqual((helper['actor'], helper['actorClass'], helper['kind']),
                         ('TheWorld.PersistentLevel.PointInSpace_0', 'PointInSpace', 'part'))
        centre = next(o for o in bomb if o['role'] == 'bomb')['location']
        self.assertAlmostEqual(helper['location'][2] - centre[2], 204.5, delta=1)
        nodes = [g for g in groups if g.startswith('node:')]
        self.assertEqual(len(nodes), 8)
        self.assertTrue(all(sorted(o['role'] for o in groups[g]) == ['button', 'effect', 'effect', 'node', 'rebuild'] for g in nodes))

    def test_the_bomb_donor_entry(self):
        package('URB_Slaughterhouse_Stream')
        donors = scene_metadata.donor_objects(COOKED / 'URB_Slaughterhouse_Stream.upk')
        entry = donors['Special/Bomb']
        self.assertEqual((entry['stream'], entry['package']), ('URB_Slaughterhouse_Stream', 'URB_Slaughterhouse_Stream.upk'))
        self.assertEqual(sum(o['kind'] == 'powerNode' for o in entry['missionObjects']), 8)
        self.assertEqual(scene_metadata.donor_objects(None), {})
        self.assertEqual(scene_metadata.donor_objects(COOKED / 'nowhere.upk'), {})


class SameShortNames(unittest.TestCase):
    def test_two_packages_with_the_same_short_actor_name_keep_their_own_records(self):
        police = scene_metadata.mission_objects(package('URB_PoliceStation_CNH'))
        pier = scene_metadata.mission_objects(package('URB_PierA_Stream'))
        a = {o['actor']: o for o in police if o['kind'] == 'dropIn'}
        b = {o['actor']: o for o in pier if o['kind'] == 'dropIn'}
        same = set(a) & set(b)
        self.assertTrue(same, 'the two streams share a drop-in point\'s name')
        name = sorted(same)[0]
        self.assertNotEqual(a[name]['location'], b[name]['location'])


class ExportCarriesThem(unittest.TestCase):
    def test_a_lwr_patch_layer_has_its_spawns_and_a_mission_layer_its_objects(self):
        police = package('URB_PoliceStation')
        with tempfile.TemporaryDirectory() as d:
            result = dict(meshes={}, materials={}, textures={}, diagnostics=[])
            streams = export.stream_layers(police, result, Path(d), [dict(streams=['URB_PoliceStation_CNH', 'patch_policestation'])])
        self.assertIn('spawns', streams['patch_policestation'])
        self.assertNotIn('spawns', streams['URB_PoliceStation_CNH'])
        self.assertTrue(all('uses' in o and 'values' in o for o in streams['URB_PoliceStation_CNH']['missionObjects']))


if __name__ == '__main__':
    unittest.main()
