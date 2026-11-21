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

    def test_soldier_points_off_the_layout_are_kept_by_their_own_zone(self):
        # KB-13 (T-51): 89 of the install's 141 landings with a frame have soldier points off the mutator's layout for
        # it (the police station's on raised ground, 3 to 5 units across and 38 to 70 higher; many a third of a tile
        # off): the zone at the landing's own place moves nothing, a zone moved or of another kind moves them
        for off in ([3, -5, 38], [-4, 5, 70], [32, 0, 0], [0, -384, 16]):
            landing = landing_at(OWN)
            for a in landing['actors']:
                if a['role'] in ('soldier2', 'soldier4', 'soldier6'):
                    a['location'] = [a['location'][j] + off[j] for j in range(3)]
            self.assertEqual(native_spawns.plan([landing], dict(zones=[OWN], own=[0])), [], off)
            self.assertEqual(native_spawns.plan([landing], dict(zones=[dict(OWN, location=[720, -1680, 64])], own=[0])), [])
            inside, = native_spawns.plan([landing], dict(zones=[dict(OWN, kind='inside')], own=[0]))
            at = spawns.place(dict(OWN, kind='inside'))
            by = {a['role']: a for a in inside['actors']}
            self.assertEqual(by['soldier2']['new'][0], [round(v, 4) for v in at['soldiers'][1][0]])
            self.assertEqual(len(native_spawns.plan([landing], dict(zones=[MOVED], own=[0]))), 1)

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
        self.assertEqual(len(moved), 15)        # ten of the landing's, five of the Skyranger's (its dust: export 35)
        dust = next(a for a in moved if a['role'] == 'dust')
        self.assertEqual(dust['path'], 'TheWorld.PersistentLevel.Emitter_0')
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
                native_copy.build(native_copy.BuildState(
                    BAR, d, 'URB_BarLz', [], bake=True, cache='Lighting_7351',
                    landing_zones=dict(zones=[dict(MOVED, ew=True)], own=[0], ownLandings=1)))
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
        self.assertEqual(native_spawns.apply_lane(None, None, dict(moves=[], values=[], copies=[], deletes=[])), ([], set(), []))


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


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarSpawnCopies(unittest.TestCase):
    """URB_Bar's pods and Meld points copied and deleted (SP7): pod 2 copied with pod index 5, Meld point 2 copied and
    made hard, pod 4 deleted; written, read back, the templates as they were."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.ops = dict(copies=[dict(id='a', name='XComAlienPod_Abduction_2_copy1', source='XComAlienPod_Abduction_2', kind='pod',
                                    location=[-1145.6, 251.2, 17.0], rotation=[0, 0, 0], podIndex=5, spawn=dict(use=False)),
                               dict(id='b', name='XComMeldContainerSpawnPoint_2_copy2', source='XComMeldContainerSpawnPoint_2',
                                    kind='meld', location=[912.0, 720.0, 17.0], rotation=[0, 0, 0], spawn=dict(difficulty='Hard'))],
                       deletes=[dict(name='XComAlienPod_Abduction_4')])
        cls.clones, cls.gone, cls.record = native_spawns.apply_lane(g, cls.p, cls.ops)
        native_copy.add_to_level(g, cls.p, cls.clones)
        native_copy.empty_slots(g, cls.p, cls.gone)
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_copies_are_listed_with_their_index_and_values_and_the_delete_is_off_the_list(self):
        native_spawns.verify(self.q, self.record, self.p)
        by = {r['actor']: r for r in self.record}
        pod, meld = by['XComAlienPod_Abduction_2_copy1'], by['XComMeldContainerSpawnPoint_2_copy2']
        self.assertEqual(self.q.cls(pod['export']), 'XComAlienPod_Abduction')
        self.assertEqual(native_spawns.read_value(self.q, pod['export'], 'podIndex'), 5)
        self.assertEqual(native_spawns.read_value(self.q, pod['export'], 'use'), False)
        self.assertEqual(native_spawns.read_value(self.q, meld['export'], 'difficulty'), 'Hard')
        # the copy owns clones of its template's components, and shares its archetype
        t = self.p.by_name[native_spawns.PL + 'XComAlienPod_Abduction_2']
        self.assertEqual(len(self.q.children.get(pod['export'], [])), len(self.p.children.get(t, [])))
        self.assertEqual(self.q.exports[pod['export'] - 1]['arch'], self.p.exports[t - 1]['arch'])
        listed = native_copy.level_actors(self.q)
        self.assertNotIn(self.p.by_name[native_spawns.PL + 'XComAlienPod_Abduction_4'], listed)
        self.assertEqual(sum(1 for i in listed if i > 0), sum(1 for i in native_copy.level_actors(self.p) if i > 0) + 1)

    def test_refusals(self):
        g = package_grow.Grower(str(BAR))
        pod = dict(name='c', source='XComAlienPod_Abduction_2', kind='pod', location=[0, 0, 0], rotation=[0, 0, 0], podIndex=5)
        for ops in (dict(copies=[dict(pod, podIndex=None)]),                         # a pod's copy with no index
                    dict(copies=[dict(pod, source='XComSpawnPoint_18')]),           # no pod or Meld point
                    dict(copies=[dict(pod, kind='meld')]),                          # the kind is not the template's
                    dict(deletes=[dict(name='XComAlienPod_Abduction_4')] * 2)):
            with self.assertRaises(ValueError, msg=ops):
                native_spawns.apply_lane(g, self.p, ops)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarNoSpawnVolumes(unittest.TestCase):
    """URB_Bar's no-spawn volumes edited (the user, 18 November 2026: editable and added from the Add panel): volume 0
    stretched over a new box in place and let civilians in, a copy of it, a new one (made from the map's first volume),
    volume 2 deleted; and a pod copied from a pod the same edit deletes (a cleared map's new pod). Written, read back,
    each volume's brush over its box."""
    VOLUME0 = [-864.0, -576.0, 0.0, -192.0, -384.0, 320.0]
    COPY = [96.0, 96.0, 0.0, 288.0, 288.0, 256.0]
    NEW = [384.0, 384.0, 0.0, 672.0, 672.0, 256.0]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.ops = dict(moves=[dict(name='XComNoSpawnVolume_0', box=cls.VOLUME0)],
                       values=[dict(name='XComNoSpawnVolume_0', spawn=dict(civilians=False))],
                       copies=[dict(id='v', name='XComNoSpawnVolume_0_copy1', source='XComNoSpawnVolume_0', kind='noSpawn', box=cls.COPY),
                               dict(id='w', name='XComNoSpawnVolume_copy2', source=None, kind='noSpawn', box=cls.NEW, spawn=dict(aliens=False)),
                               dict(id='p', name='XComAlienPod_Abduction_2_copy3', source='XComAlienPod_Abduction_2', kind='pod',
                                    location=[-1145.6, 251.2, 17.0], rotation=[0, 0, 0], podIndex=5)],
                       deletes=[dict(name='XComNoSpawnVolume_2'), dict(name='XComAlienPod_Abduction_2')])
        cls.clones, cls.gone, cls.record = native_spawns.apply_lane(g, cls.p, cls.ops)
        native_copy.add_to_level(g, cls.p, cls.clones)
        native_copy.empty_slots(g, cls.p, cls.gone)
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def box_of(self, i):
        b = scene_metadata.volume_bounds(self.q, i)
        return [round(v, 2) for v in b['min'] + b['max']]

    def test_each_volume_reads_back_over_its_box_with_its_values(self):
        native_spawns.verify(self.q, self.record, self.p)
        by = {(r['actor'], r['how']): r for r in self.record}
        v0 = self.q.by_name[native_spawns.PL + 'XComNoSpawnVolume_0']
        self.assertEqual(self.box_of(v0), self.VOLUME0)
        self.assertEqual(native_spawns.read_value(self.q, v0, 'civilians'), False)
        copy, new = by[('XComNoSpawnVolume_0_copy1', 'copied')], by[('XComNoSpawnVolume_copy2', 'copied')]
        for r, box in ((copy, self.COPY), (new, self.NEW)):
            self.assertEqual(self.q.cls(r['export']), 'XComNoSpawnVolume')
            self.assertEqual(self.box_of(r['export']), box)
            self.assertEqual(str(self.q.own(r['export'], 'Tag')), 'XComNoSpawnVolume')
        self.assertEqual(native_spawns.read_value(self.q, new['export'], 'aliens'), False)
        self.assertIsNone(native_spawns.read_value(self.q, copy['export'], 'aliens'))
        # the volume edited in place keeps its name; the deleted volume and pod are off the list, the copies on it
        listed = set(native_copy.level_actors(self.q))
        self.assertIn(v0, listed)
        for name in ('XComNoSpawnVolume_2', 'XComAlienPod_Abduction_2'):
            self.assertNotIn(self.p.by_name[native_spawns.PL + name], listed)
        for r in (copy, new, by[('XComAlienPod_Abduction_2_copy3', 'copied')]):
            self.assertIn(r['export'], listed)
        # the pod copied from a deleted pod is a pod, with its index
        pod = by[('XComAlienPod_Abduction_2_copy3', 'copied')]
        self.assertEqual(self.q.cls(pod['export']), 'XComAlienPod_Abduction')
        self.assertEqual(native_spawns.read_value(self.q, pod['export'], 'podIndex'), 5)

    def test_a_map_with_no_volume_of_its_own_makes_one_from_another_volume(self):
        # (volume_template with no no-spawn volume listed: the rebuild volume's template, retyped)
        g = package_grow.Grower(str(BAR))
        listed = {i for i in native_copy.level_actors(self.p) if i > 0 and self.p.cls(i) != 'XComNoSpawnVolume'}
        template = native_spawns.volume_template(self.p, listed)
        self.assertNotEqual(self.p.cls(self.p.by_name[native_spawns.PL + template]), 'XComNoSpawnVolume')
        made = native_spawns.copy_volume(g, self.p, dict(name='n', source=None, box=self.NEW), listed)
        native_copy.add_to_level(g, self.p, [made['export']])
        out = Path(self.tmp.name) / 'retyped.upk'
        g.write(str(out))
        q = Package(out)
        self.assertEqual(q.cls(made['export']), 'XComNoSpawnVolume')
        self.assertEqual(q.cls(q.own(made['export'], 'BrushComponent')), 'BrushComponent')
        b = scene_metadata.volume_bounds(q, made['export'])
        self.assertEqual([round(v, 2) for v in b['min'] + b['max']], self.NEW)

    def test_refusals(self):
        g = package_grow.Grower(str(BAR))
        for ops in (dict(moves=[dict(name='XComAlienPod_Abduction_0', box=self.VOLUME0)]),     # a pod moved by a box
                    dict(copies=[dict(name='c', source='XComAlienPod_Abduction_0', kind='noSpawn', box=self.COPY)]),
                    dict(copies=[dict(name='c', source=None, kind='noSpawn', box=[0, 0, 0, 0, 96, 64])]),
                    dict(values=[dict(name='XComNoSpawnVolume_0', spawn=dict(use=True))])):
            with self.assertRaises(ValueError, msg=ops):
                native_spawns.apply_lane(g, self.p, ops)


class OwnZonesOfRealMaps(unittest.TestCase):
    """KB-13 (T-51): each landing with a frame of two maps whose soldier points stand off the mutator's layout (the
    police station's on raised ground, the Boulevard's a third of a tile off) is unmoved by the zone its frame gives."""
    def test_each_landing_is_unmoved_by_its_own_zone(self):
        for name in ('URB_PoliceStation', 'URB_Boulevard'):
            path, why = labpaths.install_map(name)
            if not (path and Path(path).exists()):
                self.skipTest(why)
            framed = 0
            for landing in scene_metadata.landing_metadata(Package(path)):
                frame = next((a for a in landing['actors'] if a['role'] == 'frame'), None)
                if frame:
                    framed += 1
                    zone = spawns.zone_of_frame(frame['location'], frame['rotation'][1])
                    self.assertTrue(native_spawns.unmoved(landing, zone), (name, landing['prefab']))
            self.assertGreater(framed, 0, name)


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
