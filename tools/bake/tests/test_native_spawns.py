"""The map's own landings moved in place (native_spawns.py; private/plans/done/clear-map-plan.md, section 4). The
plan on small records, and URB_Bar's landing moved and turned on the configured install (skipped without it)."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402
import native_copy  # noqa: E402
import native_spawns  # noqa: E402
import package_grow  # noqa: E402
import scene_metadata  # noqa: E402
import spawns  # noqa: E402
from package import Package  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
OWN = dict(id='own', location=[719, -1681, 64], direction='north', kind='normal')
MOVED = dict(id='moved', location=[719 + 384, -1681, 64], direction='east', kind='normal')


def actor(role, location, yaw=0, cls='XComSpawnPoint', saves=False):
    return dict(role=role, path='TheWorld.PersistentLevel.%s_%s' % (cls, role), actorClass=cls, archetype=None,
                location=list(location), rotation=[0, yaw, 0], tag=None, savesRotation=saves)


def landing_at(zone):
    """A landing whose actors stand where the zone puts them (the frame unturned when the zone faces north)."""
    at = spawns.place(zone)
    actors = [actor('frame', at['frame'][0], at['frame'][1], 'XComLevelActor'),
              actor('volume', at['volume'][0], 0, 'XComBuildingVolume', True),
              actor('playerStart', at['playerStart'][0], 0, 'PlayerStart'), actor('point', at['point'][0], 0, 'PointInSpace')]
    actors += [actor('soldier%d' % (k + 1), at['soldiers'][k][0]) for k in range(6)]
    sky = dict(prefab='PrefabInstance_17', actors=[actor('mesh', [at['frame'][0][0] - 160, at['frame'][0][1] - 1290, 0], 192,
                                                         'XComLevelActor', True)])
    return dict(prefab='PrefabInstance_19', group='XComSpawnPoint', actors=actors, skyranger=sky)


class Plan(unittest.TestCase):
    def test_an_unmoved_zone_moves_nothing(self):
        landing = landing_at(OWN)
        self.assertEqual(native_spawns.plan([landing], dict(zones=[OWN], own=[0])), [])
        # within four units is the same place (Bar's first line is its own landing within two)
        near = dict(OWN, location=[720, -1680, 64])
        self.assertEqual(native_spawns.plan([landing], dict(zones=[near], own=[0])), [])
        # a zone that is not one of the map's own moves nothing
        self.assertEqual(native_spawns.plan([landing], dict(zones=[OWN, MOVED], own=[0])), [])

    def test_a_moved_and_turned_zone_moves_every_actor_by_the_mutators_rules(self):
        landing = landing_at(OWN)
        moves = native_spawns.plan([landing], dict(zones=[MOVED], own=[0]))
        self.assertEqual(len(moves), 1)
        by = {a['role']: a for a in moves[0]['actors']}
        at = spawns.place(MOVED)
        self.assertEqual(by['frame']['new'], ([1103, -1681, 0], [0, 16384, 0]))
        self.assertEqual(by['volume']['new'][0], [round(v, 4) for v in at['volume'][0]])
        # the evac volume saves no turn of its own: it takes the zone's less the frame's
        self.assertEqual(by['volume']['new'][1], [0, 16384, 0])
        for k in range(6):
            self.assertEqual(by['soldier%d' % (k + 1)]['new'][0], [round(v, 4) for v in at['soldiers'][k][0]])
            self.assertEqual(by['soldier%d' % (k + 1)]['new'][1][1], native_spawns.norm(at['soldiers'][k][1]))
        # the Skyranger by the frame's rigid move: 160 west and 1290 south of the frame, turned a quarter, is 1290 east
        # and 160 south of it, its yaw a quarter on
        mesh = by['mesh']['new']
        self.assertEqual([round(v) for v in mesh[0]], [1103 + 1290, -1681 - 160, 0])
        self.assertEqual(mesh[1], [0, 192 + 16384, 0])

    def test_landings_by_slot(self):
        first, second = landing_at(OWN), landing_at(dict(OWN, location=[0, 0, 64]))
        moves = native_spawns.plan([first, second], dict(zones=[dict(MOVED, missionType='eMission_Abduction'), OWN, MOVED],
                                                         own=[1, 2]))
        # the first own slot is zone 1 (unmoved for the first landing); the second, zone 2, moves the second landing
        self.assertEqual([(m['slot'], m['zone']) for m in moves], [(2, 'moved')])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarMoved(unittest.TestCase):
    """URB_Bar's landing moved four tiles east and turned east, written and read back."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.report, volumes = native_spawns.apply(g, cls.p, dict(zones=[MOVED, dict(OWN, id='other', location=[0, 0, 64])],
                                                                 own=[0]))
        native_copy.add_to_level(g, cls.p, volumes)
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)
        cls.volumes = volumes

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_landing_actor_is_at_its_new_place_under_its_own_name(self):
        self.assertEqual(len(self.report), 1)
        moved = self.report[0]['actors']
        self.assertEqual(len(moved), 14)        # ten of the landing's, four of the Skyranger's
        for a in moved:
            i = self.q.by_name[a['path']]       # the same name
            self.assertEqual(self.q.exports[i - 1]['arch'], self.p.exports[self.p.by_name[a['path']] - 1]['arch'])
            loc = self.q.own(i, 'Location')
            self.assertTrue(all(abs(loc[j] - a['new'][0][j]) < 0.01 for j in range(3)), a['path'])
            rot = self.q.own(i, 'Rotation') or [0, 0, 0]
            self.assertEqual([int(v) for v in rot], a['new'][1], a['path'])
        # read again from the written map, the landing is where the zone puts it
        landing = scene_metadata.landing_metadata(self.q)[0]
        self.assertTrue(native_spawns.unmoved(landing, MOVED))
        frame = next(a for a in landing['actors'] if a['role'] == 'frame')
        self.assertEqual(spawns.zone_of_frame(frame['location'], frame['rotation'][1])['direction'], 'east')

    def test_the_player_start_keeps_its_base_and_the_skyranger_its_tiles(self):
        start = next(a for a in self.report[0]['actors'] if a['role'] == 'playerStart')
        i = self.q.by_name[start['path']]
        base = self.q.own(i, 'Base')
        rel = self.q.own(i, 'RelativeLocation')
        b = self.q.own(base, 'Location')
        self.assertTrue(all(abs(b[j] + rel[j] - start['new'][0][j]) < 0.01 for j in range(3)))
        tiles = self.report[0]['tiles']
        self.assertEqual([t['actor'] for t in tiles], ['XComLevelActor_138'])
        self.assertTrue(tiles[0]['old'] and tiles[0]['new'])
        self.assertEqual(len(self.volumes), 2)
        live = set(native_copy.level_actors(self.q))
        self.assertTrue(all(v in live for v in self.volumes))



@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarMovedBaked(unittest.TestCase):
    def test_the_relight_gets_the_skyranger_moved_in_place_with_its_old_pose(self):
        # F-98: a baked build hands the relight each moved piece with a mesh (the grounded Skyranger,
        # XComLevelActor_138, and the drop zone's frame, which casts no shadow) as moved in place, with its old pose;
        # the relight itself is not run here
        import subprocess
        p = Package(BAR)
        calls = []

        def run(cmd, check=True):
            calls.append([str(c) for c in cmd])
            raise RuntimeError('captured')
        original, subprocess.run = subprocess.run, run
        try:
            with tempfile.TemporaryDirectory() as d, self.assertRaises(RuntimeError):
                native_copy.build(BAR, d, 'URB_BarLz', [], bake=True, cache='Lighting_7351',
                                  landing_zones=dict(zones=[dict(MOVED, ew=True)], own=[0], ownLandings=1))
        finally:
            subprocess.run = original
        cmd = calls[0]
        self.assertTrue(any(c.endswith('relight.py') for c in cmd[:4]))
        moved = dict(cmd[i + 1].split('=', 1) for i, c in enumerate(cmd) if c == '--moved-in-place')
        self.assertIn('XComLevelActor_138', moved)
        sky = p.by_name['TheWorld.PersistentLevel.XComLevelActor_138']
        old = [float(v) for v in moved['XComLevelActor_138'].split(',')]
        self.assertEqual([round(v, 2) for v in old[:3]], [round(v, 2) for v in p.own(sky, 'Location')])
        self.assertEqual([round(v) for v in old[3:]], list(p.own(sky, 'Rotation', [0, 0, 0])))
        # only pieces with a mesh: no spawn point, player start or volume
        for name in moved:
            self.assertTrue(native_copy.has_mesh(p, p.by_name['TheWorld.PersistentLevel.' + name]), name)


class SpawnValueBytes(unittest.TestCase):
    """The spawns lane's values as bytes (the editor spawns plan, SP6): a bool one byte, a whole number four, the Meld
    difficulty its enum value's name and number 0."""
    def test_bytes(self):
        class Names:
            def name(self, text):
                return {'eMeldContainerDifficulty_Hard': 7}[text]
        g = Names()
        self.assertEqual(native_spawns.value_bytes(g, 'commander', True), ('bCommanderPod', 'BoolProperty', None, b'\x01'))
        self.assertEqual(native_spawns.value_bytes(g, 'use', False)[3], b'\x00')
        self.assertEqual(native_spawns.value_bytes(g, 'destroyedOnTurn', -1), ('m_iDestroyedOnTurn', 'IntProperty', None, b'\xff' * 4))
        self.assertEqual(native_spawns.value_bytes(g, 'difficulty', 'Hard'),
                         ('m_eDifficulty', 'ByteProperty', 'EMeldContainerDifficulty', b'\x07\x00\x00\x00\x00\x00\x00\x00'))
        self.assertEqual(native_spawns.spawn_kind('XComAlienPod_Abduction'), 'pod')
        self.assertIsNone(native_spawns.spawn_kind('XComSpawnPoint'))
        self.assertEqual(native_spawns.apply_lane(None, None, dict(moves=[], values=[])), ([], set(), []))
        with self.assertRaises(ValueError):
            native_spawns.apply_lane(None, None, dict(deletes=[dict(name='XComAlienPod_0')]))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarSpawnEdits(unittest.TestCase):
    """URB_Bar's own spawn points edited in place (SP6): pod 0 moved a tile and turned a quarter, pod 1 the commander's,
    Meld point 2 hard and destroyed on turn 6, Meld point 3 in spawn group 1; written, read back, and the rest of the
    map as it was."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        pod = cls.p.by_name[native_spawns.PL + 'XComAlienPod_Abduction_0']
        cls.before = [float(v) for v in cls.p.own(pod, 'Location')], [int(v) for v in cls.p.own(pod, 'Rotation', [0, 0, 0])]
        cls.moved = ([cls.before[0][0] + 96] + cls.before[0][1:], [0, cls.before[1][1] + 16384, 0])
        g = package_grow.Grower(str(BAR))
        cls.ops = dict(moves=[dict(name='XComAlienPod_Abduction_0', location=cls.moved[0], rotation=cls.moved[1])],
                       values=[dict(name='XComAlienPod_Abduction_1', spawn=dict(commander=True)),
                               dict(name='XComMeldContainerSpawnPoint_2', spawn=dict(difficulty='Hard', destroyedOnTurn=6)),
                               dict(name='XComMeldContainerSpawnPoint_3', spawn=dict(spawnGroup=1))])
        clones, gone, cls.record = native_spawns.apply_lane(g, cls.p, cls.ops)
        assert (clones, gone) == ([], set())
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_point_reads_back_as_edited_under_its_own_name(self):
        native_spawns.verify(self.q, self.record)
        self.assertEqual([(r['actor'], r['how']) for r in self.record],
                         [('XComAlienPod_Abduction_0', 'moved'), ('XComAlienPod_Abduction_1', 'valued'),
                          ('XComMeldContainerSpawnPoint_2', 'valued'), ('XComMeldContainerSpawnPoint_3', 'valued')])
        at = lambda name: self.q.by_name[native_spawns.PL + name]  # noqa: E731
        self.assertEqual([round(v, 3) for v in self.q.own(at('XComAlienPod_Abduction_0'), 'Location')], [round(v, 3) for v in self.moved[0]])
        self.assertEqual(native_spawns.read_value(self.q, at('XComAlienPod_Abduction_1'), 'commander'), True)
        self.assertEqual(native_spawns.read_value(self.q, at('XComMeldContainerSpawnPoint_2'), 'difficulty'), 'Hard')
        self.assertEqual(native_spawns.read_value(self.q, at('XComMeldContainerSpawnPoint_2'), 'destroyedOnTurn'), 6)
        self.assertEqual(native_spawns.read_value(self.q, at('XComMeldContainerSpawnPoint_3'), 'spawnGroup'), 1)
        # (what the edit left alone: pod 1's own place, pod 0's values)
        self.assertEqual(self.q.own(at('XComAlienPod_Abduction_1'), 'Location'),
                         self.p.own(self.p.by_name[native_spawns.PL + 'XComAlienPod_Abduction_1'], 'Location'))
        self.assertIsNone(native_spawns.read_value(self.q, at('XComAlienPod_Abduction_0'), 'commander'))

    def test_the_rest_of_the_map_is_as_it_was(self):
        self.assertEqual(len(self.q.exports), len(self.p.exports))
        edited = {r['export'] for r in self.record}
        for i in range(1, len(self.p.exports) + 1):
            self.assertEqual(self.q.exports[i - 1]['name'], self.p.exports[i - 1]['name'])
            if i in edited or self.p.cls(i) in ('Level', 'Package'):
                continue
            a, b = self.p.exports[i - 1], self.q.exports[i - 1]
            if self.p.cls(i).startswith('XCom') and self.p.name(i).startswith(('XComAlienPod', 'XComMeld', 'XComSpawnPoint')):
                self.assertEqual(self.q.data[b['off']:b['off'] + b['size']], self.p.data[a['off']:a['off'] + a['size']], self.p.name(i))
        self.assertEqual(set(native_copy.level_actors(self.q)), set(native_copy.level_actors(self.p)))

    def test_refusals(self):
        g = package_grow.Grower(str(BAR))
        for ops in (dict(moves=[dict(name='XComSpawnPoint_18', location=[0, 0, 0], rotation=[0, 0, 0])]),
                    dict(moves=[dict(name='XComAlienPod_Abduction_99', location=[0, 0, 0], rotation=[0, 0, 0])]),
                    dict(values=[dict(name='XComAlienPod_Abduction_0', spawn=dict(difficulty='Hard'))]),
                    dict(moves=[dict(name='XComAlienPod_Abduction_0', location=[0, 0, 0], rotation=[0, 0, 0])] * 2)):
            with self.assertRaises(ValueError, msg=ops):
                native_spawns.apply_lane(g, self.p, ops)


class FramelessPlan(unittest.TestCase):
    """A landing with no frame (the tutorial's): nothing moves while its zone is the fitted one; moved, its actors go
    to the zone's offsets from the fitted frame, and no frame is written."""
    def test_unmoved_then_moved(self):
        landing = landing_at(OWN)
        landing['actors'] = [a for a in landing['actors'] if a['role'] != 'frame']
        fitted = spawns.fit_zone(landing['actors'])
        self.assertEqual(native_spawns.plan([landing], dict(zones=[dict(fitted, id='z')], own=[0])), [])
        moved = dict(fitted, id='z', location=[fitted['location'][0] + 480] + fitted['location'][1:], direction='east')
        m, = native_spawns.plan([landing], dict(zones=[moved], own=[0]))
        roles = {a['role']: a for a in m['actors']}
        self.assertNotIn('frame', roles)
        self.assertEqual(m['frame']['old'], [spawns.place(fitted)['frame'][0], 0])
        at = spawns.place(moved)
        for k in range(6):
            self.assertEqual(roles['soldier%d' % (k + 1)]['new'][0], [round(v, 4) for v in at['soldiers'][k][0]])

if __name__ == '__main__':
    unittest.main()
