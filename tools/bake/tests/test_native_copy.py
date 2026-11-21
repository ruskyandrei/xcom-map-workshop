"""A copy of a placed piece as new exports of the map (native_copy.py, baker step L4), on the bar."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import native_copy  # noqa: E402
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import package_grow  # noqa: E402
import relight  # noqa: E402
import seed_map  # noqa: E402
import shadowmaps  # noqa: E402
import world_links  # noqa: E402
import decomp  # noqa: E402   (on the path native_copy gives)

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
import fixtures  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
# a map with no trigger volume at all (F-59), from the LWR install
POLICE, NO_POLICE = labpaths.test_file('XCOM_POLICE_UPK', labpaths.lwr_cooked('URB_PoliceStation.upk'),
                                       'URB_PoliceStation.upk')
# a map whose first fallback volumes (camera blocking volumes) have no brush (F-67), from the LWR install
DEMOLITION, NO_DEMOLITION = labpaths.test_file('XCOM_DEMOLITION_UPK', labpaths.lwr_cooked('URB_Demolition_EWI.upk'),
                                               'URB_Demolition_EWI.upk')
# a map whose only plain volume with a brush of the fallback classes is its lightmass importance volume (F-77)
INTRO, NO_INTRO = labpaths.install_map('Act1_IntroLevel')
# the blank map, lit by one baked (not dominant) directional light (EXP-79 run D)
BLANK, NO_BLANK = labpaths.test_file('XCOM_BLANK_UPK', labpaths.lwr_cooked('CB2_MP_Blank.upk'), 'CB2_MP_Blank.upk')
PL = native_copy.PL


class FloorMembershipCases(unittest.TestCase):
    """A copy's building-floor listings: floor_at and copy_floors pass the cases the editor's view (floors.js
    floorAt and copyFloors) passes too (private/plans/done/floor-brush-plan.md, 3.8)."""
    cases = __import__('json').loads((HERE / 'floor_membership_cases.json').read_text(encoding='utf-8'))

    def test_floor_at(self):
        for c in self.cases['floorAt']:
            buildings = {i: (None, None, [dict(volumes=f) for f in floors]) for i, floors in enumerate(c['buildings'])}
            at = native_copy.floor_at(buildings, c['box'])
            self.assertEqual(list(at) if at else None, c['at'], c['case'])

    def test_copy_floors(self):
        for c in self.cases['copyFloors']:
            got = native_copy.copy_floors([tuple(x) for x in c['listings']], tuple(c['here']) if c['here'] else None,
                                          tuple(c['there']) if c['there'] else None, lambda b: c['floors'][b])
            self.assertEqual([[b, f, cut] for _, b, f, cut in got], c['expect'], c['case'])
            self.assertEqual([n for n, *_ in got], list(range(len(got))), c['case'])


class CommandLine(unittest.TestCase):
    """The Build runs native_copy.py with a --copies file (tools/editor/build.py): main makes the Build's state from it
    through edit_state, and each copy, the native edit's and the command line's, through copy_record, whole, a made
    wall's wallGroup included (review finding 36), and the file's other sections as they are."""
    # a copy record with every field compiler.native_split writes, and a staged one as transplant.py rewrites it
    WALL = dict(actor='XComFracLevelActor_11', location=[0, 636, 14.5], rotation=[0, 16384, 0], box=[[0, 0, 0], [1, 1, 1]],
                label='XComFracLevelActor_11_copy1', wallGroup=1, untried=True, flags={'mouse': False},
                generated={'kind': 'wall', 'version': 3}, blasts=[{'at': [1, 2, 3], 'radius': 100}], breaksFurther=True)
    PROP = dict(actor='XComDestructibleActor_4', location=[144, 660, 14.5], rotation=[0, 0, 0], label='prop', breakGroup=1,
                family='door', assembly='a1', ladder={'foot': [1, 2, 3], 'top': [1, 2, 9]}, futureField='kept')
    STAGED = dict(actor='StaticMeshActor_9', location=[1, 2, 3], yaw=8192, staged=True,
                  donor={'package': 'URB_PoliceStation', 'actor': 'StaticMeshActor_3'})
    # one copy carrying every optional field there is (compiler.native_split's, transplant.py's staged ones, the
    # command line's yaw) and one no reader knows yet, its pose and group as text and floats
    EVERY = dict(actor='XComFracLevelActor_11', location=['0', 636, 14.5], rotation=[0.0, '16384', 0], yaw=8192,
                 label='wall', box=[[0, 0, 0], [1, 1, 1]], breakGroup='3', wallGroup=2, untried=True,
                 donor={'package': 'URB_PoliceStation', 'actor': 'StaticMeshActor_3'}, staged=True,
                 flags={'mouse': False, 'floor': True}, generated={'kind': 'fracWall', 'version': 3},
                 blasts=[{'at': [1, 2, 3], 'radius': 100}], breaksFurther=True, family='door', assembly='a1',
                 ladder={'foot': [1, 2, 3], 'top': [1, 2, 9]}, futureField={'kept': [1]})
    # each lane of the native edit (but copies) and the state's field it goes to
    LANES = dict(breakOriginals='break_originals', hides='hides', assemblies='assemblies', lights='lights',
                 covers='covers', buildings='buildings', buildingEdits='building_edits', cleared='cleared',
                 landingZones='landing_zones', carriedEffects='carried_effects', effects='effects', sounds='sounds',
                 flares='flares', spawns='spawns', streamTiles='stream_tiles', pieceFlags='piece_flags',
                 pieceFlagLadders='flag_ladders', pieceBlasts='piece_blasts')

    def run_main(self, doc, *more):
        got = {}

        class Stop(Exception):
            pass

        def build(st):
            got['state'] = st
            raise Stop
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'native-edit.json'
            path.write_text(__import__('json').dumps(doc), encoding='utf-8', newline='\n')
            argv, real = sys.argv, native_copy.build
            sys.argv = ['native_copy.py', 'src.upk', d, 'Variant'] + (['--copies', str(path)] if doc is not None else []) \
                + list(more)
            native_copy.build = build
            try:
                with self.assertRaises(Stop):
                    native_copy.main()
            finally:
                sys.argv, native_copy.build = argv, real
        return got['state']

    def test_copy_records_reach_build_whole(self):
        st = self.run_main(dict(copies=[self.WALL, self.PROP, self.STAGED],
                                breakOriginals=[{'name': 'XComLevelActor_2', 'group': 1}]))
        copies = st.copies
        self.assertEqual(len(copies), 3)
        for sent, received in zip((self.WALL, self.PROP, self.STAGED), copies):
            for key, value in sent.items():
                self.assertEqual(received.get(key), value, key)
        self.assertEqual(copies[0]['wallGroup'], 1)
        self.assertEqual(st.break_originals, [{'name': 'XComLevelActor_2', 'group': 1}])

    def test_the_pose_is_read_as_numbers(self):
        st = self.run_main([dict(actor='XComLevelActor_1', location=['1', 2, 3.5], rotation=['0', 16384.0, 0],
                                 breakGroup='2')])
        (c,) = st.copies
        self.assertEqual((c['location'], c['rotation'], c['breakGroup']), ([1.0, 2.0, 3.5], [0, 16384, 0], 2))
        self.assertEqual([type(v) for v in c['location'] + c['rotation']], [float] * 3 + [int] * 3)

    def test_a_copy_carrying_every_field_comes_through_whole(self):
        # finding 36's kind of loss: a field of a copy dropped between the native edit and build, by any of the ways
        # in (the record alone, the native edit as a dict or as a list of copies, main from the --copies file)
        want = dict(self.EVERY, location=[0.0, 636.0, 14.5], rotation=[0, 16384, 0], breakGroup=3)
        got = native_copy.copy_record(self.EVERY)
        self.assertEqual(got, want)
        self.assertEqual([type(v) for v in got['location'] + got['rotation'] + [got['breakGroup']]],
                         [float] * 3 + [int] * 4)
        for doc in ([self.EVERY], dict(copies=[self.EVERY])):
            with self.subTest(doc=type(doc).__name__):
                self.assertEqual(native_copy.edit_state('src.upk', 'out', 'Variant', doc).copies, [want])
                self.assertEqual(self.run_main(doc).copies, [want])
        self.assertEqual(self.EVERY['location'], ['0', 636, 14.5])     # the record given is left as it was

    def test_every_lane_reaches_its_field(self):
        # every lane the copy tool reads from the native edit is in LANES, and each reaches its field as it is
        import inspect
        import re
        read = set(re.findall(r"doc\.get\('(\w+)'\)", inspect.getsource(native_copy.edit_state))) - {'copies'}
        self.assertEqual(read, set(self.LANES))
        doc = dict(copies=[], **{lane: [{'lane': lane}] for lane in self.LANES})
        for st in (native_copy.edit_state('src.upk', 'out', 'Variant', doc), self.run_main(doc)):
            for lane, name in self.LANES.items():
                self.assertEqual(getattr(st, name), [{'lane': lane}], lane)
        st = native_copy.edit_state('src.upk', 'out', 'Variant', dict(copies=[]), bake=True, cache='Variant_Lighting',
                                    tiles=False, jobs=3)
        self.assertEqual((st.bake, st.cache, st.tiles, st.jobs, st.lights, st.hides), (True, 'Variant_Lighting', False,
                                                                                      3, None, []))

    def test_the_command_lines_copies_come_through_copy_record(self):
        st = self.run_main(None, '--copy', 'XComLevelActor_1', '1', '2', '3.5', '8192', '--actor', 'XComLevelActor_2',
                           '--at', '4', '5', '6')
        self.assertEqual(st.copies, [
            dict(actor='XComLevelActor_1', location=[1.0, 2.0, 3.5], yaw=8192, rotation=None, breakGroup=0),
            dict(actor='XComLevelActor_2', location=[4.0, 5.0, 6.0], yaw=None, rotation=None, breakGroup=0)])
        # after the native edit's copies, in the order given
        st = self.run_main([dict(actor='XComLevelActor_3', location=[0, 0, 0])], '--copy', 'XComLevelActor_1', '1', '2', '3')
        self.assertEqual([c['actor'] for c in st.copies], ['XComLevelActor_3', 'XComLevelActor_1'])


@unittest.skipUnless(DEMOLITION and DEMOLITION.exists(), NO_DEMOLITION)
class RebuildTemplateBrush(unittest.TestCase):
    def test_a_volume_with_no_brush_is_passed_over(self):
        # URB_Demolition_EWI's GameCameraBlockingVolume_0 and _1 are plain volumes with no brush model: the template is
        # its first cursor volume, and a rebuild volume cloned from it has the box asked for
        p = lighting.Package(DEMOLITION)
        self.assertEqual(p.own(p.by_name[PL + 'GameCameraBlockingVolume_0'], 'Brush', 0), 0)
        template = native_copy.rebuild_template(p)
        self.assertEqual(template, 'XComCursorVolume_0')
        g = package_grow.Grower(str(DEMOLITION))
        box = [0.0, 192.0, 0.0, 96.0, -200.0, 64.0]
        vol = native_copy.add_rebuild_volume(g, p, box)
        native_copy.add_to_level(g, p, [vol['export']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Demolition_EWI.upk'
            g.write(str(out))
            q = lighting.Package(out)
            self.assertEqual(q.cls(vol['export']), 'XComRebuildWorldDataVolume')
            lo, hi = native_copy.brush_box(q, vol['export'])
            self.assertTrue(np.allclose([c for pair in zip(lo, hi) for c in pair], box, atol=0.01))


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class RebuildTemplateIntro(unittest.TestCase):
    def test_the_intro_map_clones_its_lightmass_importance_volume(self):
        # Act1_IntroLevel has no trigger, no-spawn or cursor volume, and its camera blocking volumes have no brush
        p = lighting.Package(INTRO)
        self.assertEqual(native_copy.rebuild_template(p), 'LightmassImportanceVolume_1')
        g = package_grow.Grower(str(INTRO))
        box = [-800.0, -608.0, 600.0, 696.0, -8.0, 256.0]
        vol = native_copy.add_rebuild_volume(g, p, box)
        native_copy.add_to_level(g, p, [vol['export']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'Act1_IntroLevel.upk'
            g.write(str(out))
            q = lighting.Package(out)
            self.assertEqual(q.cls(vol['export']), 'XComRebuildWorldDataVolume')
            lo, hi = native_copy.brush_box(q, vol['export'])
            self.assertTrue(np.allclose([c for pair in zip(lo, hi) for c in pair], box, atol=0.01))


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class WalkableScenery(unittest.TestCase):
    def test_a_copy_of_a_backdrop_ground_plane_in_the_grid_is_floor(self):
        # Act1_IntroLevel's XComLevelActor_13, a ground plane of its backdrop past the play area, saves its collision
        # off (F-100). Its copy in the play area, a storey up, gets it on, and tiles (a copy at the ground seeds none:
        # the ground level is re-checked by the map's own rebuild volumes, or the grown grid's); a copy outside the
        # grid keeps it off
        name = 'XComLevelActor_13'
        copies = [dict(actor=name, location=[-2000.0, -500.0, 192.0], rotation=[0, 0, 0], label='in'),
                  dict(actor=name, location=[9000.0, -500.0, 0.0], rotation=[0, 0, 0], label='out')]
        p = lighting.Package(INTRO)
        self.assertIs(p.effective(p.by_name[PL + name], 'bCollideActors'), False)
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(INTRO, d, 'IntroScenery', copies))
            inside, outside = m['nativeCopies']['copies']
            q = lighting.Package(Path(d) / 'IntroScenery.upk')
            self.assertIn('walkable', inside)
            self.assertIsNotNone(inside['tiles'])
            self.assertNotIn('walkable', outside)
            self.assertIsNone(outside['tiles'])
            for section, on in ((inside, True), (outside, False)):
                actor = section['export']
                self.assertEqual(q.effective(actor, 'bCollideActors', True), on)
                self.assertEqual(q.effective(actor, 'bPathColliding', True), on)
                self.assertEqual(native_copy.collides(q, actor), on)
            # the original stays as the map has it
            self.assertIs(q.effective(q.by_name[PL + name], 'bCollideActors'), False)


@unittest.skipUnless(POLICE and POLICE.exists(), NO_POLICE)
class RebuildTemplate(unittest.TestCase):
    """The police station: rebuild volumes on a map without a trigger volume, and two copies made in one build the
    class shares (fixtures.SharedBuild), each test reading its own part (part): a door copied onto the station's
    outer wall and the car copied a few tiles on, which touch different pieces and lists."""
    DOOR = 'door 0 and its frame (XComDestructibleActor_42) copied into door 95\'s doorway on the back wall'
    CAR = 'car 1071 and its glass (XComFracLevelActor_198) copied three tiles on'

    @classmethod
    def setUpClass(cls):
        p = lighting.Package(POLICE)
        folder = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        cls.shared = fixtures.SharedBuild(folder / 'build', {cls.DOOR: cls.door_copied(p), cls.CAR: cls.car_copied(p)},
                                          fixtures.native_build(POLICE, 'URB_PoliceShared'), fixtures.NativePart)
        cls.addClassCleanup(delattr, cls, 'shared')     # the map read back goes with its folder, not held to the end

    def part(self, name):
        """This test's part of the shared build that carries the edit `name` (fixtures.SharedBuild.part)."""
        return self.shared.part(self, name)

    @staticmethod
    def door_copied(p):
        # Police Station's floor volumes end on the back wall's line (x -384), so a door there has its centre on their
        # face: door 0 copied into door 95's doorway joins floor 0 of the station (the volumes it overlaps most)
        copies = []
        for n in ('XComDestructibleActor_42', 'XComInteractiveLevelActor_0'):
            i = p.by_name[PL + n]
            loc = list(p.own(i, 'Location'))
            copies.append(dict(actor=n, location=[loc[0] - 1056, loc[1] + 2400, loc[2]], rotation=[0, 16384, 0],
                               assembly='add:XComInteractiveLevelActor_0_copy2', family='door'))
        return dict(copies=copies)

    @staticmethod
    def car_copied(p):
        # Police Station's car 1071: its glass's columns also name XComDestructibleActor_1070, outside the car
        copies = []
        for n in ('XComDestructibleActor_1071', 'XComFracLevelActor_198'):
            i = p.by_name[PL + n]
            loc = list(p.own(i, 'Location'))
            copies.append(dict(actor=n, location=[loc[0], loc[1] + 288, loc[2]], rotation=list(p.own(i, 'Rotation', [0, 0, 0])),
                               assembly='add:XComDestructibleActor_1071_copy1', family='car'))
        return dict(copies=copies)

    def test_priority_tile_volumes_precede_existing_rebuilds(self):
        with tempfile.TemporaryDirectory() as d:
            first, second = Path(d) / 'first.upk', Path(d) / 'second.upk'
            p = lighting.Package(POLICE)
            g = package_grow.Grower(str(POLICE))
            existing = native_copy.tile_volume(g, p, [1, 1, 0])['export']
            native_copy.add_to_level(g, p, [existing])
            g.write(str(first))
            p = lighting.Package(first)
            g = package_grow.Grower(str(first))
            priority = native_copy.tile_volume(g, p, [2, 2, 1])['export']
            native_copy.add_to_level(g, p, [], before_rebuild=[priority])
            g.write(str(second))
            q = lighting.Package(second)
            order = native_copy.level_actors(q)
            volumes = [i for i in order if i > 0 and q.cls(i) == 'XComRebuildWorldDataVolume']
            self.assertEqual(volumes[0], priority)
            self.assertIn(existing, volumes[1:])
            self.assertEqual([i for i in order if i != priority], native_copy.level_actors(p))

    def test_a_map_without_a_trigger_volume_clones_another_plain_volume(self):
        p = lighting.Package(POLICE)
        self.assertNotIn(PL + native_copy.REBUILD_TEMPLATE, p.by_name)
        template = native_copy.rebuild_template(p)
        self.assertEqual(template, 'XComNoSpawnVolume_11')
        g = package_grow.Grower(str(POLICE))
        box = [0.0, 192.0, 0.0, 96.0, -8.0, 256.0]
        vol = native_copy.add_rebuild_volume(g, p, box)
        self.assertEqual(vol['template'], template)
        native_copy.add_to_level(g, p, [vol['export']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_PoliceStation.upk'
            g.write(str(out))
            q = lighting.Package(out)
            v = vol['export']
            self.assertEqual(q.cls(v), 'XComRebuildWorldDataVolume')
            lo, hi = native_copy.brush_box(q, v)
            self.assertTrue(np.allclose([c for pair in zip(lo, hi) for c in pair], box, atol=0.01))


    def test_a_door_copy_on_its_buildings_outer_wall_joins_that_floor(self):
        with self.part(self.DOOR) as part:
            self.assertEqual(part.nc['floorCaches'],
                             [dict(copy=c['actor'], building='XComBuildingVolume_2', floor=0) for c in part.edit['copies']])

    def test_a_car_copys_glass_drops_column_entries_of_other_pieces(self):
        # the copy's columns keep the body's entry (pointing at the body's copy) and drop that one (plan 7.2)
        with self.part(self.CAR) as part:
            sec = {c['actor']: c for c in part.nc['copies']}
            self.assertGreater(sec['XComFracLevelActor_198']['columns']['dropped'], 0)
            q = part.q
            glass = sec['XComFracLevelActor_198']['export']
            named = {e[('DestructibleActor', 0)]['value'] for c in q.structs(q.own(glass, 'FragmentColumns'))
                     for e in q.structs(c.get(('DestructibleCache', 0), {}).get('value'))}
            self.assertEqual(named, {sec['XComDestructibleActor_1071']['export']})


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class NativeCopy(unittest.TestCase):
    """Copies, moves and deletes on the bar. Most tests' edits are made in three builds the class shares
    (fixtures.SharedBuild), each test reading back its own part (part): two native_copy builds, and one Grower for the
    tests of the copy's own steps. A test shares a build when its edit touches actors no other edit of that build
    touches and changes nothing another reads back (a moved piece's tiles, a deleted piece's links, a piece's
    columns): each shared edit's records are the ones it gets built alone. A test keeps a build of its own when it
    reads a count of the whole map, when its edit meets another test's, or when its build is the one that makes its
    kind of edit alone (a copy, a move, a delete), so that a fault that shows only when an edit is alone is still
    caught."""
    # the shared builds' edits, by the names failures show
    LADDER_PLAIN = 'XComLadder_3 moved two tiles along its wall, with no climb record'
    CAR_TURNED = 'the police car (body 64, light bar 143, glass 45) copied a quarter turn round'
    DOOR_MOVED = 'door 6 and its frame moved a tile along the inner wall, door 7 and its frame deleted'
    CORPSE = 'KAsset_0 copied to a pose off the grid, KAsset_1 deleted'
    VAN_COPIED = 'the delivery van (cab 527 and its six parts) copied a quarter turn round'
    STRIP_UP = 'the upstairs floor strip (XComFracLevelActor_17) copied 2 tiles north and 3 levels up'
    # the shared Grower's
    PROP_TURNED = 'XComDestructibleActor_100 cloned where it stands at a full rotation'
    MESHLESS_TURNED = 'XComLevelActor_5 cloned at a full rotation'
    CAR_ABOUT_CORNER = 'the police car cloned a quarter turn about a tile corner and moved 30 tiles'

    @classmethod
    def setUpClass(cls):
        cls.p = p = lighting.Package(BAR)
        folder = Path(cls.enterClassContext(tempfile.TemporaryDirectory()))
        # two native_copy builds, not one: the van's copy seeds tiles the car's seeds too, and so do the ladder's and
        # the strip's, and the second to seed them would find them seeded (its tiles record's counts not its own)
        builds = [fixtures.SharedBuild(folder / 'build', {
            # first: its copy's rebuild volume is then the first of the level's list, as when it is built alone
            cls.LADDER_PLAIN: dict(copies=[cls.LADDER], hides=[dict(name='XComLadder_3')]),
            cls.CAR_TURNED: cls.car_turned(),
            cls.DOOR_MOVED: cls.door_moved(p),
            cls.CORPSE: cls.corpse(p)}, fixtures.native_build(BAR, 'URB_BarShared'), fixtures.NativePart),
            fixtures.SharedBuild(folder / 'build2', {
                cls.VAN_COPIED: cls.van_copied(),
                cls.STRIP_UP: cls.strip(p, 192.0)}, fixtures.native_build(BAR, 'URB_BarShared2'), fixtures.NativePart),
            fixtures.SharedBuild(folder / 'grown', dict(
                {edit: cls.full_rotation(name, where, rotation) for edit, name, where, rotation, _ in cls.FULL_ROTATIONS},
                **{cls.CAR_ABOUT_CORNER: cls.car_about_corner}), cls.grow, lambda name, edit, made: (made[0][name], made[1]))]
        cls.shared = {name: build for build in builds for name in build.edits}
        cls.addClassCleanup(delattr, cls, 'shared')     # the maps read back go with their folder, not held to the end

    def part(self, name):
        """This test's part of the shared build that carries the edit `name` (fixtures.SharedBuild.part)."""
        return self.shared[name].part(self, name)

    @staticmethod
    def grow(folder, edits):
        """The shared Grower's make (fixtures.SharedBuild): each edit, a function of the Grower and the source map
        returning what its test reads and the actors it adds, made in one Grower of the bar; their actors added to
        the level together; the map written and read again. Returns ({name: what its test reads}, the written map)."""
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        got, actors = {}, []
        for name, edit in edits.items():
            got[name], added = edit(g, p)
            actors += added
        native_copy.add_to_level(g, p, actors)
        folder.mkdir(parents=True)
        out = folder / 'URB_BarNative.upk'
        g.write(str(out))
        return got, lighting.Package(out)

    def test_the_shared_builds_maps_read_back_as_a_whole_decode_reads_them(self):
        # the growing writer's check (follow-ups item 1.1) decodes only the blocks a write made and takes the rest
        # from the source's image: on the three maps the class wrote, that is the image a whole decode gives
        import package_edit
        import upkinfo
        raw = package_edit.package_bytes(str(BAR))
        src_h = upkinfo.summary(raw)
        full, _ = decomp.decompress_pkg(str(BAR))
        builds = {id(b): b for b in self.shared.values()}.values()
        written = [b.made[1].path for b in builds if b.made is not None]
        self.assertEqual(len(written), 3)
        for path in written:
            with self.subTest(map=path.name):
                b = path.read_bytes()
                h = upkinfo.summary(b)
                image, taken, decoded = decomp.decode_written(b, h, raw, src_h, full)
                self.assertEqual(image, decomp._decode(b, h))
                self.assertLess(decoded, taken // 5)

    def test_a_build_decodes_its_map_once(self):
        # the map a build writes is read back from the source's decoded blocks and kept (follow-ups item 1.1): a
        # build decodes the bar once, and neither the writer's check nor the readers after it decode the written map
        # whole (before, the check did: two decodes)
        copy = dict(actor='XComLevelActor_37', location=[-1155.0, -1874.4, 0.0], rotation=[0, 0, 0])
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ):
            for name in (decomp.WORK_ENV, decomp.KEEP_ENV):
                os.environ.pop(name, None)
            decomp._MEMO.clear()
            before = dict(decomp.STATS)
            native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarOneCopy', [copy]))
            self.assertEqual({k: decomp.STATS[k] - before[k] for k in ('decoded', 'written')},
                             dict(decoded=1, written=1))

    def test_a_sky_dome_collides_with_nothing_so_its_copy_seeds_no_tiles(self):
        # F-93: the Bar's two sky domes save no collision; its pieces collide
        p = self.p
        for name, expected in (('XComLevelActor_257', False), ('XComLevelActor_63', False),
                               ('XComLevelActor_10', True), ('XComDestructibleActor_10', True)):
            self.assertIs(native_copy.collides(p, p.by_name[PL + name]), expected, name)

    def test_the_walker_finds_a_destructibles_references(self):
        p = self.p
        ai = p.by_name[PL + 'XComDestructibleActor_294']
        e = p.exports[ai - 1]
        start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
        data = p.data[e['off']:e['off'] + e['size']]
        refs = {prop: struct.unpack_from('<i', data, at)[0] for prop, at in native_copy.Walker(p).refs(data, start, e['size'])}
        self.assertEqual(refs['StaticMeshComponent[0]'], p.by_name[PL + 'XComDestructibleActor_294.StaticMeshComponent_68'])
        self.assertEqual(refs['LightEnvironment[0]'],
                         p.by_name[PL + 'XComDestructibleActor_294.DynamicLightEnvironmentComponent_2248'])
        # the damage actions inside the DestroyedEvents structs are found too
        actions = [v for k, v in refs.items() if k.startswith('DestroyedEvents')]
        self.assertTrue(actions and all(p.exports[v - 1]['outer'] == ai for v in actions if v > 0))

    def test_arrays_that_hold_no_references_are_not_taken_for_them(self):
        # a van's floor volume's brush hull and its building's visibility group numbers (the inventory read them as
        # references to unrelated actors; a clone would have rewritten any that equalled a cloned index)
        p = self.p
        w = native_copy.Walker(p)
        for name in ('XComFloorVolume_0.BrushComponent_5', 'XComBuildingVolume_1'):
            i = p.by_name[PL + name]
            e = p.exports[i - 1]
            start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
            paths = [prop for prop, _ in w.refs(p.data[e['off']:e['off'] + e['size']], start, e['size'])]
            self.assertFalse([x for x in paths if any(n in x for n in native_copy.NOT_REFERENCES)], name)
        # the building's own references are still found
        i = p.by_name[PL + 'XComBuildingVolume_1']
        e = p.exports[i - 1]
        start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
        paths = [prop for prop, _ in w.refs(p.data[e['off']:e['off'] + e['size']], start, e['size'])]
        self.assertTrue(any('FloorVolumes' in x for x in paths) and any('ResidentActor' in x for x in paths))

    @staticmethod
    def car_about_corner(g, p):
        """The shared Grower's edit of the test below: the police car cloned as one assembly, a quarter turn about a
        tile corner and a move, as the compiler's grid move would make, and a rebuild volume over it."""
        names = ['XComDestructibleActor_64', 'XComFracLevelActor_45', 'XComDestructibleActor_143']
        old = {n: p.by_name[PL + n] for n in names}
        corner = (-2784.0, -1920.0)
        members = []
        for n in names:
            loc = list(p.own(old[n], 'Location'))
            rot = [int(v) for v in p.own(old[n], 'Rotation', [0, 0, 0])]
            x, y = loc[0] - corner[0], loc[1] - corner[1]
            members.append((old[n], [-y + corner[0] + 30 * 96, x + corner[1], loc[2]], [rot[0], rot[1] + 16384, rot[2]]))
        infos = native_copy.clone_assembly(g, p, members)
        tile = native_copy.add_tiles_box(g, p, native_copy.assembly_box(p, members))
        return (dict(names=names, old=old, members=members, infos=infos, tile=tile),
                [info['actor'] for info in infos] + [tile['volume']['export']])

    def test_an_assemblys_parts_are_cloned_together_and_point_at_each_others_copies(self):
        # the police car: its body names its glass as HidingPartner, the glass's fragment columns name the body and
        # the light bar; a quarter turn about a tile corner and a move, as the compiler's grid move would make (in the
        # shared Grower: car_about_corner)
        p = self.p
        with self.part(self.CAR_ABOUT_CORNER) as (made, q):
            names, old, members, infos, tile = (made[k] for k in ('names', 'old', 'members', 'infos', 'tile'))
            new = {n: info['actor'] for n, info in zip(names, infos)}
            originals = set()
            for n in names:
                originals |= set(native_copy.subtree(p, old[n]))
            qw = native_copy.Walker(q)

            def refs(i):
                e = q.exports[i - 1]
                start = native_copy.legacy_props.props_start(q.data, e, q.names) - e['off']
                data = q.data[e['off']:e['off'] + e['size']]
                return [(prop, struct.unpack_from('<i', data, at)[0]) for prop, at in qw.refs(data, start, e['size'])]
            body = dict(refs(new['XComDestructibleActor_64']))
            self.assertEqual(body['HidingPartner[0]'], new['XComFracLevelActor_45'])
            columns = [v for prop, v in refs(new['XComFracLevelActor_45']) if 'DestructibleActor' in prop]
            self.assertTrue(columns)
            self.assertEqual(set(columns), {new['XComDestructibleActor_64'], new['XComDestructibleActor_143']})
            # no clone of any member points at an original member's export; the originals keep their own links
            for info in infos:
                for clone in info['mapping'].values():
                    self.assertFalse({v for _, v in refs(clone)} & originals, q.name(clone))
            self.assertEqual(dict(refs(old['XComDestructibleActor_64']))['HidingPartner[0]'], old['XComFracLevelActor_45'])
            # each clone stands at its pose; one rebuild volume covers the whole car
            for (_, loc, rot), n in zip(members, names):
                self.assertEqual([round(v, 3) for v in q.own(new[n], 'Location')], [round(v, 3) for v in loc])
                self.assertEqual(list(q.own(new[n], 'Rotation')), rot)
            box = native_copy.assembly_box(p, members)
            lo, hi = native_copy.brush_box(q, tile['volume']['export'])
            self.assertTrue(lo[0] <= box[0] and hi[0] >= box[1] and lo[1] <= box[2] and hi[1] >= box[3])

    def test_build_makes_an_assembly_in_one_piece(self):
        # the Build's copies file: the car's three copies share an assembly; the manifest keeps the move
        p = self.p
        names = ['XComDestructibleActor_64', 'XComFracLevelActor_45', 'XComDestructibleActor_143']
        copies = []
        for n in names:
            i = p.by_name[PL + n]
            loc = list(p.own(i, 'Location'))
            copies.append(dict(actor=n, location=[loc[0], loc[1] + 288, loc[2]],
                               rotation=[int(v) for v in p.own(i, 'Rotation', [0, 0, 0])],
                               assembly='add:XComDestructibleActor_64_copy1', family='car'))
        move = dict(id='add:XComDestructibleActor_64_copy1', family='car', members=names, turns=0, translation=[0, 288, 0])
        copies.append(dict(actor='XComLevelActor_37', location=[-1155.0, -1874.4, 0.0], rotation=[0, 0, 0]))
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarCars', copies, assemblies=[move]))
            sec = m['nativeCopies']['copies']
            self.assertEqual([c.get('assembly') for c in sec], [move['id']] * 3 + [None])
            self.assertEqual([c['tiles'] is not None for c in sec], [True, False, False, True])
            self.assertEqual(m['nativeCopies']['assemblies'], [move])
            self.assertEqual(m['nativeCopies']['level']['actorsAfter'] - m['nativeCopies']['level']['actorsBefore'], 3 + 1 + 1 + 1)

    # the ladder's copy of the test below
    LADDER = dict(actor='XComLadder_3', location=[-1680.0, 528.0, 16.0], rotation=[0, 0, 0],
                  assembly='move:XComLadder_3', family='ladder')

    def test_a_ladder_copy_rebuilds_its_top_tile_first(self):
        # EXP-22 run 1's hazard case: XComLadder_3 (facing +X, no saved Rotation) moved two tiles along its wall. Its
        # copy's own volume adds the foot (11, 25, 0) before the top (12, 25, 6), X running outer and Z inner; the
        # small volume over the top tile, first in the level's list, puts the top first. The move without its climb
        # is in a shared build; with it, a build of its own (the move alone, and it counts the volumes)
        hide = [dict(name='XComLadder_3')]
        copy = self.LADDER
        with self.part(self.LADDER_PLAIN) as plain:
            order = native_copy.rebuild_order(plain.q)
            self.assertLess(order[(11, 25, 0)], order[(12, 25, 6)])
            self.assertEqual(plain.nc['ladders'], [])
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(
                BAR, d, 'URB_BarLadder', [dict(copy, ladder=dict(foot=[11, 25, 0], top=[12, 25, 6]))], hides=hide))
            [ladder] = m['nativeCopies']['ladders']
            self.assertLess(ladder['topPlace'], ladder['footPlace'])
            q = lighting.Package(Path(d) / 'URB_BarLadder.upk')
            volumes = [a for a in native_copy.level_actors(q) if a > 0 and q.cls(a) == 'XComRebuildWorldDataVolume']
            self.assertEqual(volumes[0], ladder['topVolume']['export'])
            self.assertEqual(len(volumes), 3)    # the top tile's, the copy's, the hidden original's
            self.assertEqual(q.own(ladder['export'], 'Rotation'), [0, 0, 0])
            self.assertEqual(q.own(ladder['export'], 'Location'), [-1680.0, 528.0, 16.0])
            # the top tile's volume reaches that tile alone
            c, r = native_copy.volume_sphere(q, volumes[0])
            self.assertAlmostEqual(r, 24.0, places=3)
            # a copy whose foot no volume reaches makes no climb: refused
            with self.assertRaises(ValueError):
                native_copy.ladder_order(q, [dict(copy='X', foot=[0, 0, 11], top=[12, 25, 6])])

    def test_a_ladder_copy_on_a_grown_map_rebuilds_its_top_tile_first(self):
        # a grown map has shell.py's whole-grid ground volume ahead in the level's list: it would queue the foot
        # (11, 25, 0) before the top (12, 25, 6), so the top tile's volume goes before it, as on the blank map
        import shell
        grid = native_copy.level_grid(self.p)
        copy = dict(actor='XComLadder_3', location=[-1680.0, 528.0, 16.0], rotation=[0, 0, 0],
                    assembly='move:XComLadder_3', family='ladder', ladder=dict(foot=[11, 25, 0], top=[12, 25, 6]))
        with tempfile.TemporaryDirectory() as d:
            grown = shell.equip(BAR, Path(d) / 'shell', grid=(grid['nx'] + 4, grid['ny']), ground=True)['shelled']
            m = native_copy.build(native_copy.BuildState(grown, Path(d) / 'out', 'URB_BarLadderGrown', [copy],
                                                         hides=[dict(name='XComLadder_3')]))
            [ladder] = m['nativeCopies']['ladders']
            self.assertLess(ladder['topPlace'], ladder['footPlace'])
            q = lighting.Package(Path(d) / 'out' / 'URB_BarLadderGrown.upk')
            volumes = [a for a in native_copy.level_actors(q) if a > 0 and q.cls(a) == 'XComRebuildWorldDataVolume']
            self.assertEqual(volumes[0], ladder['topVolume']['export'])

    def test_a_cloned_lamp_post_is_a_new_actor_of_the_level(self):
        p = self.p
        old = p.by_name[PL + 'XComLevelActor_37']
        g = package_grow.Grower(str(BAR))
        info = native_copy.clone_actor(g, p, old, (-1155.0, -1874.4, 0.0), (0, 16384, 0))
        native_copy.add_to_level(g, p, [info['actor']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_BarNative.upk'
            g.write(str(out))
            q = lighting.Package(out)
            new = info['actor']
            self.assertEqual(q.cls(new), 'XComLevelActor')
            self.assertTrue(q.name(new).startswith(PL + 'XComLevelActor_'))
            self.assertNotEqual(q.name(new), p.name(old))
            self.assertEqual(q.own(new, 'Location'), [-1155.0, -1874.4000244140625, 0.0])
            self.assertEqual(q.own(new, 'Rotation'), [0, 16384, 0])
            comp = q.own(new, 'StaticMeshComponent')
            self.assertEqual(comp, q.own(new, 'CollisionComponent'))
            self.assertEqual(q.exports[comp - 1]['outer'], new)
            self.assertEqual(q.own(comp, 'VisibilityId'), -1)
            self.assertEqual(q.exports[comp - 1]['arch'], p.exports[p.own(old, 'StaticMeshComponent') - 1]['arch'])
            sm = lightmap_fields.component_fields(q, comp)['lods'][0]['shadowMaps']
            self.assertEqual([q.exports[s - 1]['outer'] for s in sm], [comp])
            level = q.by_name['TheWorld.PersistentLevel']
            _, end = q.properties(level)
            owner, count = struct.unpack_from('<ii', q.data, end)
            self.assertEqual(struct.unpack_from('<i', q.data, end + 8 + 4 * (count - 1))[0], new)
            # the original stays as it was
            self.assertEqual(q.own(old, 'Location'), p.own(old, 'Location'))
            # every clone with a net index has a fresh one, from the package's count up (a clone keeping its
            # original's is a duplicate the game logs at every load)
            def net(pkg, i):
                e = pkg.exports[i - 1]
                return struct.unpack_from('<i', pkg.data, e['off'] + native_copy.net_index_offset(pkg, i))[0]
            count = p.header['gens'][0][2]
            fresh = sorted(net(q, n) for o, n in info['mapping'].items() if net(p, o) > 0)
            self.assertEqual(fresh, list(range(count, count + len(fresh))))
            self.assertEqual(q.header['gens'][0][2], count + len(fresh))

    # the pieces of the test below, each cloned in the shared Grower (full_rotation): its edit's name, the piece, its
    # place (None: where it stands), its rotation, and whether its mesh is this map's
    FULL_ROTATIONS = ((PROP_TURNED, 'XComDestructibleActor_100', None, (1024, 8192, -2048), True),
                      (MESHLESS_TURNED, 'XComLevelActor_5', (64.0, -32.0, 8.0), (0, -16384, 0), False))

    @staticmethod
    def full_rotation(name, where, rotation):
        """A shared Grower's edit of the test below: the piece `name` cloned at `where` (None: where it stands) and
        `rotation`."""
        def edit(g, p):
            old = p.by_name[PL + name]
            info = native_copy.clone_actor(g, p, old, where or p.own(old, 'Location'), rotation)
            return info, [info['actor']]
        return edit

    def test_a_piece_at_the_default_pose_takes_a_full_rotation(self):
        # a piece standing at rotation 0 saves no Rotation (XComLevelActor_5 no Location either): the copy's are added
        p = self.p
        for edit, name, where, rotation, has_mesh in self.FULL_ROTATIONS:
            old = p.by_name[PL + name]
            self.assertIsNone(p.own(old, 'Rotation', None))
            where = where or p.own(old, 'Location')
            with self.part(edit) as (info, q):
                new = info['actor']
                self.assertEqual(q.own(new, 'Rotation'), list(rotation))
                self.assertEqual(q.own(new, 'Location'), [float(np.float32(v)) for v in where])
                self.assertEqual(q.own(new, 'StaticMeshComponent'), info['mapping'][p.own(old, 'StaticMeshComponent')])
                self.assertIsNone(q.own(old, 'Rotation', None))
                if not has_mesh:
                    continue        # its mesh is another package's
                # the copy's box follows the full rotation
                box = native_copy.piece_box(q, new, where, rotation)
                self.assertEqual(box, native_copy.piece_box(p, old, where, rotation))
                self.assertNotEqual(box, native_copy.piece_box(p, old, where, (0, 0, 0)))

    def test_copies_link_the_parts_copied_with_them_and_their_break_groups(self):
        p = self.p
        w = native_copy.Walker(p)
        g = package_grow.Grower(str(BAR))

        def own(name):
            i = p.by_name[PL + name]
            return i, list(p.own(i, 'Location')), [int(v) for v in p.own(i, 'Rotation', [0, 0, 0])]
        table, table_at, table_rot = own('XComDestructibleActor_491')     # a pool table: it lists its top as a child
        top, top_at, top_rot = own('XComDestructibleActor_45')
        e = p.exports[table - 1]
        start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
        self.assertEqual(native_copy.object_array(w, p.data[e['off']:e['off'] + e['size']], start, 'AffectedChildren'),
                         [top])
        shift = [400.0, 0.0, 0.0]
        jobs = [('XComDestructibleActor_491', [a + b for a, b in zip(table_at, shift)], table_rot, 0),
                ('XComDestructibleActor_45', [a + b for a, b in zip(top_at, shift)], top_rot, 0),
                ('XComDestructibleActor_491', [a + b for a, b in zip(table_at, (0.0, 900.0, 0.0))], table_rot, 0),
                ('XComDestructibleActor_29', [-1200.0, -1008.0, 0.0], [0, 0, 0], 1),
                ('XComDestructibleActor_13', [-1872.0, -1008.0, 0.0], [0, 0, 0], 1)]
        made = []
        for name, where, rot, group in jobs:
            info = native_copy.clone_actor(g, p, p.by_name[PL + name], where, rot)
            made.append(dict(actor=name, location=where, rotation=rot, info=info, breakGroup=group))
        dumpster = p.by_name[PL + 'XComDestructibleActor_61']
        groups, notes = native_copy.link_children(g, p, made, [dict(name='XComDestructibleActor_61', group=1)])
        native_copy.add_to_level(g, p, [m['info']['actor'] for m in made])
        new = [m['info']['actor'] for m in made]
        self.assertEqual(groups, {1: [new[3], new[4], dumpster]})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_BarNative.upk'
            g.write(str(out))
            q = lighting.Package(out)
            qw = native_copy.Walker(q)

            def children(i):
                e = q.exports[i - 1]
                start = native_copy.legacy_props.props_start(q.data, e, q.names) - e['off']
                return native_copy.object_array(qw, q.data[e['off']:e['off'] + e['size']], start, 'AffectedChildren')
            # the table moved with its top lists the top's copy; the table copied alone lists nothing of the original's
            self.assertEqual(children(new[0]), [new[1]])
            self.assertEqual(children(new[2]), [])
            self.assertEqual(notes[new[2]], [dict(child='XComDestructibleActor_45', copy=None)])
            self.assertEqual(children(table), [top])                 # the original keeps its own
            # the group: each member lists the others (the keg keeps its original's empty slots)
            self.assertEqual(children(new[3]), [new[4], dumpster])
            self.assertEqual([c for c in children(new[4]) if c], [new[3], dumpster])
            self.assertEqual(children(dumpster)[-2:], [new[3], new[4]])

    def test_a_door_leafs_box_comes_from_its_skeletal_mesh(self):
        # G4: the leaf draws a skeletal mesh and saves an unused StaticMeshComponent (no mesh): its box is the skeletal
        # mesh's in its reference pose, closed in its doorway; it has no lighting textures
        p = self.p
        leaf = p.by_name[PL + 'XComInteractiveLevelActor_6']
        box = native_copy.piece_box(p, leaf, p.own(leaf, 'Location'), p.own(leaf, 'Rotation', [0, 0, 0]))
        self.assertEqual([round(v) for v in box], [-858, -774, 662, 682, 18, 171])
        self.assertTrue(native_copy.has_mesh(p, leaf))
        self.assertEqual(native_copy.lighting_textures(p, native_copy.subtree(p, leaf)), [])

    @staticmethod
    def door_moved(p):
        """The shared build's edit of the test below."""
        names = ['XComDestructibleActor_60', 'XComInteractiveLevelActor_6']
        copies = []
        for n in names:
            i = p.by_name[PL + n]
            loc = list(p.own(i, 'Location'))
            copies.append(dict(actor=n, location=[loc[0] + 96, loc[1], loc[2]], rotation=[0, 0, 0],
                               assembly='move:XComInteractiveLevelActor_6', family='door'))
        return dict(copies=copies,
                    hides=[dict(name=n) for n in names + ['XComDestructibleActor_65', 'XComInteractiveLevelActor_7']])

    def test_a_door_copy_joins_its_walls_columns_and_its_floors_cutaway(self):
        # G8 and G7, on the bar's inner wall (XComDecoFracLevelActor_16): door 6 moved one tile along it, door 7
        # deleted. The copies are listed in the wall's columns as the original was, a tile along (the frame's MinZ
        # kept), and in floor 0's cutaway of the bar; the hidden doors leave every column (in a shared build: no other
        # edit of that build is listed in, or lists, the inner wall's columns)
        p = self.p
        with self.part(self.DOOR_MOVED) as part:
            names, hides = [c['actor'] for c in part.edit['copies']], part.edit['hides']
            nc = part.nc
            new = {c['actor']: c['export'] for c in nc['copies']}
            self.assertEqual(nc['columns']['XComDecoFracLevelActor_16']['dropped'], 36)
            self.assertEqual(len(nc['columns']['XComDecoFracLevelActor_16']['added']), 16)
            self.assertEqual(nc['floorCaches'], [dict(copy=n, building='XComBuildingVolume_0', floor=0) for n in names])
            q = part.q
            level = q.by_name['TheWorld.PersistentLevel']
            listed = {}
            for i in range(1, len(q.exports) + 1):
                if q.cls(i) in native_copy.FRACTURING and q.exports[i - 1]['outer'] == level:
                    for c in q.structs(q.own(i, 'FragmentColumns')):
                        for e in q.structs(c.get(('DestructibleCache', 0), {}).get('value')):
                            listed.setdefault(e[('DestructibleActor', 0)]['value'], []).append(
                                (q.name(i).split('.')[-1], e.get(('MinZ', 0), {}).get('value')))
            for h in hides:
                self.assertNotIn(p.by_name[PL + h['name']], listed)
            self.assertEqual(set(listed[new['XComDestructibleActor_60']]), {('XComDecoFracLevelActor_16', 15.0)})
            self.assertEqual(len(listed[new['XComInteractiveLevelActor_6']]), 8)
            cached = {}
            for i, name in enumerate(q.paths, 1):
                if q.cls(i) == 'XComBuildingVolume' and q.exports[i - 1]['outer'] == level:
                    for k, row in enumerate(q.structs(q.own(i, 'Floors'))):
                        for e in q.structs(row.get(('m_aCachedActors', 0), {}).get('value')):
                            cached.setdefault(e[('ResidentActor', 0)]['value'], []).append((name.split('.')[-1], k))
            for n in names:
                self.assertEqual(cached[new[n]], [('XComBuildingVolume_0', 0)])

    @staticmethod
    def van_copied():
        """The shared build's edit of the test below: the compiler's poses."""
        poses = {'XComDestructibleActor_104': ([-1247.21, -957.18, 0.0], [0, 49152, 0]),
                 'XComDestructibleActor_524': ([-1247.21, -957.18, 0.0], [0, 16384, 0]),
                 'XComDestructibleActor_525': ([-1247.21, -955.18, 0.0], [0, 16384, 0]),
                 'XComDestructibleActor_527': ([-1247.21, -957.18, 0.0], [0, 16384, 0]),
                 'XComFracLevelActor_16': ([-1247.21, -955.18, 0.0], [0, 16384, 0]),
                 'XComLevelActor_217': ([-1247.21, -955.18, 0.0], [0, 16384, 0]),
                 'XComLevelActor_226': ([-1247.21, -957.18, 0.0], [0, 16384, 0])}
        return dict(copies=[dict(actor=n, location=at, rotation=rot, assembly='add:XComDestructibleActor_527_copy4',
                                 family='van') for n, (at, rot) in poses.items()])

    def test_a_van_copy_takes_its_building_and_floor_volumes_along(self):
        # plan section 7.6, EXP-24 run 3's delivery van (cab 527) copied a quarter turn round (the compiler's poses):
        # its building and two floor volumes are cloned and turned with it; the copied building lists the parts'
        # copies (the cab with its CutdownFloor) and drops the three pieces under the original van; its floor volumes
        # and roof group point at the clones; its visibility groups are emptied (in a shared build: no other edit of
        # that build stands in the van's building)
        p = self.p
        with self.part(self.VAN_COPIED) as part:
            (van,) = part.nc['vans']
            self.assertEqual(van['building']['original'], 'XComBuildingVolume_3')
            self.assertEqual(sorted(van['dropped']), ['XComLevelActor_151', 'XComLevelActor_205', 'XComLevelActor_274'])
            self.assertEqual(van['outside'], [])
            self.assertEqual(sorted(f['original'] for f in van['floorVolumes']), ['XComFloorVolume_2', 'XComFloorVolume_3'])
            self.assertEqual(part.nc['floorCaches'], [])
            q = part.q
            sec = {c['actor']: c['export'] for c in part.nc['copies']}
            b = van['building']['export']
            # the building turned about the cab as the van turns: (-619, -481) is 50 east of the cab's (-669, -481)
            self.assertEqual(q.own(b, 'Rotation'), [0, 16384, 0])
            for x, y in zip(q.own(b, 'Location'), [-1247.21, -907.18, 364.0]):
                self.assertAlmostEqual(x, y, delta=0.5)
            floors = q.structs(q.own(b, 'Floors'))
            listed = [[(e[('ResidentActor', 0)]['value'], e.get(('CutdownFloor', 0), {}).get('value')) for e in
                       q.structs(f[('m_aCachedActors', 0)]['value'])] for f in floors]
            self.assertEqual(sorted(listed[0]), sorted([(sec['XComDestructibleActor_527'], 1)] + [
                (sec[n], None) for n in ('XComDestructibleActor_524', 'XComDestructibleActor_104',
                                         'XComDestructibleActor_525', 'XComLevelActor_217')]))
            self.assertEqual(listed[1], [(sec['XComLevelActor_226'], None)])
            volumes = {f['original']: f['export'] for f in van['floorVolumes']}
            self.assertEqual([q.refs(f[('FloorVolumes', 0)]['value']) for f in floors],
                             [[volumes['XComFloorVolume_3']], [volumes['XComFloorVolume_2']]])
            for v in volumes.values():
                self.assertEqual(q.own(v, 'Rotation'), [0, 16384, 0])
            groups = q.structs(q.own(b, 'ExternalMeshGroups'))
            self.assertEqual(q.refs(groups[0][('m_aActors', 0)]['value']), [sec['XComLevelActor_226']])
            self.assertEqual(struct.unpack_from('<i', q.own(b, 'VisGroupIdxToHideWhenOccluding'))[0], 0)
            # the clones are in the level's actor list; the original's building keeps its lists
            level = q.by_name['TheWorld.PersistentLevel']
            e = q.exports[level - 1]
            _, end = q.properties(level)
            count = struct.unpack_from('<i', q.data, end + 4)[0]
            actors = set(struct.unpack_from(f'<{count}i', q.data, end + 8))
            self.assertTrue({b, *volumes.values()} <= actors)
            self.assertEqual(q.own(q.by_name[PL + 'XComBuildingVolume_3'], 'Floors'),
                             p.own(p.by_name[PL + 'XComBuildingVolume_3'], 'Floors'))

    def test_a_deleted_vans_building_leaves_the_level_with_it(self):
        # the moving van (cab 101, 14 parts) deleted: its building and floor volumes leave the level's actor list too
        names = ['XComDestructibleActor_101', 'XComDestructibleActor_165', 'XComDestructibleActor_17',
                 'XComDestructibleActor_180', 'XComDestructibleActor_188', 'XComDestructibleActor_190',
                 'XComDestructibleActor_194', 'XComDestructibleActor_195', 'XComDestructibleActor_28',
                 'XComDestructibleActor_47', 'XComDestructibleActor_59', 'XComFracLevelActor_15', 'XComLevelActor_1',
                 'XComLevelActor_7']
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarNoVan', [],
                                                         hides=[dict(name=n) for n in names]))
            self.assertEqual(m['nativeCopies']['hiddenBuildings'],
                             [dict(building='XComBuildingVolume_1', volumes=['XComFloorVolume_0', 'XComFloorVolume_1'])])
            q = lighting.Package(Path(d) / 'URB_BarNoVan.upk')
            level = q.by_name['TheWorld.PersistentLevel']
            _, end = q.properties(level)
            count = struct.unpack_from('<i', q.data, end + 4)[0]
            actors = set(struct.unpack_from(f'<{count}i', q.data, end + 8))
            for n in ('XComBuildingVolume_1', 'XComFloorVolume_0', 'XComFloorVolume_1', 'XComBuildingVolume_3'):
                self.assertEqual(q.by_name[PL + n] in actors, n == 'XComBuildingVolume_3', n)

    # the police car's copy of the test below: the compiler's poses
    CAR_POSES = {'XComDestructibleActor_64': [-1341.8371, -856.3627, 0.0],
                 'XComDestructibleActor_143': [-1341.9375, -857.7891, 0.0],
                 'XComFracLevelActor_45': [-1341.7027, -854.3664, 0.0]}

    @classmethod
    def car_turned(cls):
        """The shared build's edit of the test below."""
        return dict(copies=[dict(actor=n, location=at, rotation=[0, 15656, 0],
                                 assembly='add:XComDestructibleActor_64_copy1', family='car')
                            for n, at in cls.CAR_POSES.items()])

    def test_a_car_copys_glass_columns_turn_and_move_with_it(self):
        # G8's glass half, EXP-24 run 1's police car: body 64, light bar 143 and glass 45 copied a quarter turn round
        # (the compiler's poses). Each of the copy's columns is the original's box carried by the move, and names the
        # body's and the light bar's copies with the original's MinZ (in a shared build)
        p = self.p
        poses = self.CAR_POSES
        with self.part(self.CAR_TURNED) as part:
            sec = {c['actor']: c for c in part.nc['copies']}
            self.assertEqual(sec['XComFracLevelActor_45']['columns'], dict(columns=6, dropped=0))
            q = part.q
            old = p.by_name[PL + 'XComFracLevelActor_45']
            before = (p.own(old, 'Location'), p.own(old, 'Rotation'))
            after = (poses['XComFracLevelActor_45'], [0, 15656, 0])
            originals = p.structs(p.own(old, 'FragmentColumns'))
            moved = q.structs(q.own(sec['XComFracLevelActor_45']['export'], 'FragmentColumns'))
            self.assertEqual(len(moved), len(originals))
            for a, b in zip(originals, moved):
                va, vb = (struct.unpack('<6f', c[('Bounds', 0)]['value'][:24]) for c in (a, b))
                want = native_copy.moved_box([va[0], va[3], va[1], va[4], va[2], va[5]], before, after)
                for x, y in zip(want, [vb[0], vb[3], vb[1], vb[4], vb[2], vb[5]]):
                    self.assertAlmostEqual(x, y, delta=0.01)
                got = [(e[('DestructibleActor', 0)]['value'], e[('MinZ', 0)]['value'])
                       for e in q.structs(b[('DestructibleCache', 0)]['value'])]
                self.assertEqual([v for v, _ in got], [sec['XComDestructibleActor_64']['export'],
                                                       sec['XComDestructibleActor_143']['export']])

    # ---- fracturing pieces of their own (walls, storey floors) and physics props, built since 9 November 2026
    @staticmethod
    def wall_columns(pkg, index):
        """A fracturing piece's columns in a written package: [(box [x0, x1, y0, y1, z0, z1], the actors its
        DestructibleCache names, the (actor, column) pairs its FracActorCache names)]."""
        out = []
        for c in pkg.structs(pkg.own(index, 'FragmentColumns')):
            v = struct.unpack('<6f', c[('Bounds', 0)]['value'][:24])
            out.append(([v[0], v[3], v[1], v[4], v[2], v[5]],
                        [e[('DestructibleActor', 0)]['value'] for e in pkg.structs(c.get(('DestructibleCache', 0), {}).get('value'))],
                        [(e[('FracActor', 0)]['value'], e.get(('ColumnIndex', 0), {}).get('value', 0))
                         for e in pkg.structs(c.get(('FracActorCache', 0), {}).get('value'))]))
        return out

    @staticmethod
    def level_actors(pkg):
        _, end = pkg.properties(pkg.by_name['TheWorld.PersistentLevel'])
        return set(struct.unpack_from(f"<{struct.unpack_from('<i', pkg.data, end + 4)[0]}i", pkg.data, end + 8))

    def moved_south(self, names, tiles=9, **extra):
        p = self.p
        out = []
        for n in names:
            i = p.by_name[PL + n]
            loc = list(p.own(i, 'Location'))
            out.append(dict(actor=n, location=[loc[0], loc[1] - 96.0 * tiles, loc[2]],
                            rotation=list(p.own(i, 'Rotation', [0, 0, 0])), **extra))
        return out

    def test_a_wall_copy_takes_its_columns_and_the_doors_copied_with_it(self):
        # The bar's inner wall (XComDecoFracLevelActor_16, 33 columns) copied 9 tiles south with door 6 and its frame,
        # by one move: each column's box is carried, the copy lists the door's copies where the wall listed the door,
        # every other piece the wall listed (door 7, the pictures, the shelves) and every neighbouring wall's column
        # is dropped, and the door's copies are listed once (the columns' own listing, not again by edit_columns)
        p = self.p
        wall, door = 'XComDecoFracLevelActor_16', ['XComDestructibleActor_60', 'XComInteractiveLevelActor_6']
        copies = self.moved_south([wall]) + self.moved_south(door, assembly='add:XComInteractiveLevelActor_6_copy2',
                                                              family='door')
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarWall', copies))
            nc = m['nativeCopies']
            sec = {c['actor']: c for c in nc['copies']}
            old = p.by_name[PL + wall]
            originals = self.wall_columns(p, old)
            listed = sum(a in [p.by_name[PL + n] for n in door] for _, names, _ in originals for a in names)
            everything = sum(len(names) for _, names, _ in originals)
            beside = sum(len(near) for *_, near in originals)
            self.assertGreater(listed, 0)
            self.assertGreater(beside, 0)
            self.assertEqual(sec[wall]['columns'], dict(columns=33, dropped=everything - listed, carried=listed,
                                                        neighbours=dict(kept=0, dropped=beside)))
            self.assertNotIn('assembly', sec[wall])
            q = lighting.Package(Path(d) / 'URB_BarWall.upk')
            new = sec[wall]['export']
            self.assertEqual(q.cls(new), 'XComDecoFracLevelActor')
            self.assertIn(new, self.level_actors(q))
            before = (p.own(old, 'Location'), p.own(old, 'Rotation'))
            after = (sec[wall]['location'], sec[wall]['rotation'])
            moved = self.wall_columns(q, new)
            self.assertEqual(len(moved), 33)
            copy_of = {p.by_name[PL + n]: sec[n]['export'] for n in door}
            for (box, names, _), (new_box, new_names, near) in zip(originals, moved):
                for x, y in zip(native_copy.moved_box(box, before, after), new_box):
                    self.assertAlmostEqual(x, y, delta=0.01)
                self.assertEqual(new_names, [copy_of[a] for a in names if a in copy_of])
                self.assertEqual(near, [])
            # the original wall is as it was, and no column of the map names the copies but the wall copy's
            self.assertEqual(self.wall_columns(q, old), originals)
            self.assertEqual(nc['columns'], {})
            # the wall's copy has its own component (and no lighting textures of its own in an unbaked build)
            comp = q.own(new, 'FracturedStaticMeshComponent', 0)
            self.assertEqual(q.exports[comp - 1]['outer'], new)
            self.assertEqual(q.own(comp, 'VisibilityId', 0), -1)
            self.assertEqual(q.own(comp, 'EditorPaintedVisibleFragments'), p.own(p.own(old, 'FracturedStaticMeshComponent', 0),
                                                                                  'EditorPaintedVisibleFragments'))

    def test_a_hidden_wall_leaves_its_neighbours_columns_and_a_door_copy_joins_a_walls_copy(self):
        # The inner cross wall (XComDecoFracLevelActor_17) deleted: the walls and the roof slab beside it stop listing
        # its columns. The inner wall copied 9 tiles south on its own, and door 7 (with its frame) copied into that
        # copy's other doorway, 7 tiles east and 9 south (another move than the wall's): the door's copies join the
        # wall copy's columns there (edit_columns), as a door moved along a wall of the map joins that wall's
        p = self.p
        wall, gone, door = 'XComDecoFracLevelActor_16', 'XComDecoFracLevelActor_17', ['XComDestructibleActor_65', 'XComInteractiveLevelActor_7']
        copies = self.moved_south([wall])
        for c in self.moved_south(door, assembly='add:XComInteractiveLevelActor_7_copy2', family='door'):
            copies.append(dict(c, location=[c['location'][0] + 96.0 * 7, c['location'][1], c['location'][2]]))
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarWalls', copies, hides=[dict(name=gone)]))
            nc = m['nativeCopies']
            sec = {c['actor']: c for c in nc['copies']}
            q = lighting.Package(Path(d) / 'URB_BarWalls.upk')
            actors = self.level_actors(q)
            hidden = p.by_name[PL + gone]
            self.assertNotIn(hidden, actors)
            level = q.by_name['TheWorld.PersistentLevel']
            listing = 0
            for i in range(1, len(p.exports) + 1):
                if p.cls(i) in native_copy.FRACTURING and p.exports[i - 1]['outer'] == p.by_name['TheWorld.PersistentLevel']:
                    listing += sum(a == hidden for *_, near in self.wall_columns(p, i) for a, _ in near)
            self.assertGreater(listing, 0)
            dropped = 0
            for i in actors:
                if i > 0 and q.cls(i) in native_copy.FRACTURING and q.exports[i - 1]['outer'] == level:
                    for _, names, near in self.wall_columns(q, i):
                        # nothing in the level lists a piece out of it
                        self.assertTrue(all(a in actors for a in names), q.name(i))
                        self.assertTrue(all(a in actors for a, _ in near), q.name(i))
            for name, change in nc['columns'].items():
                dropped += change.get('neighboursDropped', 0)
            # the wall's own copy dropped its listing of the hidden wall's columns with the rest (move_columns)
            copy_listing = sum(a == hidden for *_, near in self.wall_columns(p, p.by_name[PL + wall]) for a, _ in near)
            self.assertEqual(dropped, listing)
            self.assertGreater(copy_listing, 0)
            self.assertEqual(sec[wall]['columns']['neighbours']['kept'], 0)
            # the door's copies in the wall copy's columns, and in no column of the map's own walls
            key = '%s copy %d' % (wall, sec[wall]['export'])
            self.assertEqual(sorted({a['copy'] for a in nc['columns'][key]['added']}), sorted(door))
            new = self.wall_columns(q, sec[wall]['export'])
            for n in door:
                self.assertGreaterEqual(sum(sec[n]['export'] in names for _, names, _ in new), 5, n)
                self.assertTrue(all(names.count(sec[n]['export']) <= 1 for _, names, _ in new))
            self.assertEqual(sum(sec[n]['export'] in names for n in door
                                 for _, names, _ in self.wall_columns(q, q.by_name[PL + wall])), 0)

    @staticmethod
    def strip(p, dz):
        """The edit of the test below: the upstairs floor strip copied 2 tiles north and `dz` up, turned round."""
        loc = list(p.own(p.by_name[PL + 'XComFracLevelActor_17'], 'Location'))
        return dict(copies=[dict(actor='XComFracLevelActor_17', rotation=[0, 32768, 0],
                                 location=[loc[0], loc[1] + 192.0, loc[2] + dz])])

    def test_a_storey_floor_copy_moved_up_takes_its_fragment_heights_along(self):
        # The upstairs floor strip (XComFracLevelActor_17: fragments saved at world z 208..210) copied 2 tiles north
        # and 3 levels up: its component's FragmentBoundsMinZ and MaxZ, its columns' boxes and its fragments' MinZ all
        # rise by 192. Copied at its own height (EXP-28 run 1), they stay as they are. Moved up, it is in the class's
        # shared build; at its own height, a build of its own (a copy alone)
        p = self.p
        old = p.by_name[PL + 'XComFracLevelActor_17']
        comp = p.own(old, 'FracturedStaticMeshComponent', 0)
        self.assertEqual((p.own(comp, 'FragmentBoundsMinZ'), p.own(comp, 'FragmentBoundsMaxZ')), (208.0, 210.0))

        def check(sec, q, dz):
            new = q.own(sec['export'], 'FracturedStaticMeshComponent', 0)
            self.assertEqual((q.own(new, 'FragmentBoundsMinZ'), q.own(new, 'FragmentBoundsMaxZ')), (208.0 + dz, 210.0 + dz))
            # the original's are untouched
            self.assertEqual((q.own(comp, 'FragmentBoundsMinZ'), q.own(comp, 'FragmentBoundsMaxZ')), (208.0, 210.0))
            for (box, *_), (moved, *_) in zip(self.wall_columns(p, old), self.wall_columns(q, sec['export'])):
                self.assertAlmostEqual(moved[4], box[4] + dz, delta=0.01)
                self.assertAlmostEqual(moved[5], box[5] + dz, delta=0.01)
                self.assertAlmostEqual(moved[2], box[2] + 192.0, delta=0.01)
        with self.part(self.STRIP_UP) as part:
            (sec,) = part.nc['copies']
            check(sec, part.q, 192.0)
        with self.subTest(dz=0.0), tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(BAR, d, 'URB_BarStrip', **self.strip(p, 0.0)))
            check(m['nativeCopies']['copies'][0], lighting.Package(Path(d) / 'URB_BarStrip.upk'), 0.0)

    @staticmethod
    def corpse(p):
        """The shared build's edit of the test below."""
        loc = list(p.own(p.by_name[PL + 'KAsset_0'], 'Location'))
        return dict(copies=[dict(actor='KAsset_0', location=[loc[0] + 187.5, loc[1] + 20.0, loc[2]], rotation=[0, 5000, 0])],
                    hides=[dict(name='KAsset_1')])

    def test_a_physics_prop_is_cloned_with_its_skeletal_mesh(self):
        # A corpse (KAsset_0: a skeletal mesh with a physics asset, lit live) copied to a pose off the grid, and
        # KAsset_1 deleted: the copy is a KAsset of the level with its own components, and no lighting textures (in a
        # shared build)
        p = self.p
        old = p.by_name[PL + 'KAsset_0']
        with self.part(self.CORPSE) as part:
            copies = part.edit['copies']
            (sec,) = part.nc['copies']
            self.assertEqual((len(sec['exports']), sec['textures']), (3, {}))
            self.assertIsNotNone(sec['tiles'])
            q = part.q
            new = sec['export']
            actors = self.level_actors(q)
            self.assertEqual(q.cls(new), 'KAsset')
            self.assertIn(new, actors)
            self.assertNotIn(p.by_name[PL + 'KAsset_1'], actors)
            self.assertTrue(np.allclose(q.own(new, 'Location'), copies[0]['location'], atol=1e-3))
            self.assertEqual(list(q.own(new, 'Rotation')), [0, 5000, 0])
            mesh = q.own(new, 'SkeletalMeshComponent', 0)
            self.assertEqual((q.cls(mesh), q.exports[mesh - 1]['outer']), ('SkeletalMeshComponent', new))
            self.assertEqual(q.own(new, 'CollisionComponent', 0), mesh)
            old_mesh = p.own(old, 'SkeletalMeshComponent', 0)
            # the same skeletal mesh and physics asset, and a light environment of its own
            for name in ('SkeletalMesh', 'PhysicsAsset'):
                self.assertEqual(q.name(q.own(mesh, name, 0)), p.name(p.own(old_mesh, name, 0)))
            env = q.own(mesh, 'LightEnvironment', 0)
            self.assertEqual(q.exports[env - 1]['outer'], new)
            self.assertNotEqual(env, p.own(old_mesh, 'LightEnvironment', 0))
            self.assertEqual(q.own(new, 'Tag'), p.own(old, 'Tag'))

    def test_hidden_pieces_leave_the_levels_list_and_their_parents_and_get_a_rebuild(self):
        p = self.p
        g = package_grow.Grower(str(BAR))
        top, table = p.by_name[PL + 'XComDestructibleActor_45'], p.by_name[PL + 'XComDestructibleActor_491']
        dumpster = p.by_name[PL + 'XComDestructibleActor_61']
        hidden, volumes = native_copy.hide_pieces(g, p, [dict(name='XComDestructibleActor_45'),
                                                         dict(name='XComDestructibleActor_61',
                                                              box=[-2740, -2640, -1390, -1290, 0, 120])])
        level = native_copy.add_to_level(g, p, volumes)
        self.assertEqual([h['name'] for h in hidden], ['XComDestructibleActor_45', 'XComDestructibleActor_61'])
        self.assertEqual(hidden[0]['unlinkedFrom'], ['XComDestructibleActor_491'])    # the table listed its top
        self.assertEqual(hidden[1]['box'], [-2740.0, -2640.0, -1390.0, -1290.0, 0.0, 120.0])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_BarHidden.upk'
            g.write(str(out))
            q = lighting.Package(out)
            lv = q.by_name['TheWorld.PersistentLevel']
            _, end = q.properties(lv)
            owner, count = struct.unpack_from('<ii', q.data, end)
            actors = list(struct.unpack_from(f'<{count}i', q.data, end + 8))
            self.assertEqual(count, level['actorsAfter'])
            self.assertNotIn(top, actors)
            self.assertNotIn(dumpster, actors)
            self.assertIn(table, actors)
            self.assertEqual(actors[-2:], volumes)
            self.assertEqual(actors.count(0) - 2, [*struct.unpack_from(f'<{level["actorsBefore"]}i', p.data,
                                                                         p.properties(lv)[1] + 8)].count(0))
            # the exports stay (building caches list the table's top), dormant
            self.assertEqual(q.cls(top), 'XComDestructibleActor')
            e = q.exports[table - 1]
            start = native_copy.legacy_props.props_start(q.data, e, q.names) - e['off']
            self.assertEqual(native_copy.object_array(native_copy.Walker(q), q.data[e['off']:e['off'] + e['size']],
                                                      start, 'AffectedChildren'), [])
            for v in volumes:
                self.assertEqual(q.cls(v), 'XComRebuildWorldDataVolume')

    def test_a_flat_piece_at_the_grids_bottom_gets_a_rebuild(self):
        # (EXP-78) a ground plane at the grid's bottom reaches no level from 1 up: it still gets a rebuild volume over
        # its tiles and the ring round them, reaching down to the grid's bottom
        p = self.p
        g = package_grow.Grower(str(BAR))
        grid = native_copy.level_grid(p)
        flat = [-1536.0, -1152.0, -960.0, -672.0, grid['oz'], grid['oz']]
        hidden, volumes = native_copy.hide_pieces(g, p, [dict(name='XComDestructibleActor_61', box=flat)])
        self.assertEqual(hidden[0]['tiles'][4:], [1, 1])
        self.assertEqual(volumes, [hidden[0]['volume']['export']])

    def test_pieces_outside_the_maps_tiles_are_hidden_and_copied_without_a_rebuild(self):
        # the tutorial map's backdrop pieces stand two tiles past its level volume: a delete of one stopped the build
        p = self.p
        g = package_grow.Grower(str(BAR))
        outside = [-1200.0, -1100.0, -2400.0, -2300.0, 0.0, 120.0]        # the grid starts at y -1920
        dumpster = p.by_name[PL + 'XComDestructibleActor_61']
        hidden, volumes = native_copy.hide_pieces(g, p, [dict(name='XComDestructibleActor_61', box=outside),
                                                         dict(name='XComDestructibleActor_45')])
        self.assertEqual((hidden[0]['tiles'], hidden[0]['volume']), (None, None))
        self.assertEqual(volumes, [hidden[1]['volume']['export']])
        edits = len(g.edits)
        self.assertIsNone(native_copy.add_tiles_box(g, p, outside))
        self.assertEqual(len(g.edits), edits)                              # no seeds
        native_copy.add_to_level(g, p, volumes)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_BarOutside.upk'
            g.write(str(out))
            q = lighting.Package(out)
            _, end = q.properties(q.by_name['TheWorld.PersistentLevel'])
            count = struct.unpack_from('<i', q.data, end + 4)[0]
            actors = list(struct.unpack_from(f'<{count}i', q.data, end + 8))
            self.assertNotIn(dumpster, actors)                             # hidden all the same
            self.assertEqual(actors[-1:], volumes)

    def test_a_copys_tiles_are_seeded_and_a_rebuild_volume_covers_them(self):
        p = self.p
        old = p.by_name[PL + 'XComLevelActor_37']
        where, rotation = (-1155.0, -1874.4, 0.0), p.own(old, 'Rotation', [0, 0, 0])
        grid = native_copy.level_grid(p)
        self.assertEqual((round(grid['ox']), grid['oy'], grid['oz'], grid['nx'], grid['ny'], grid['nz']),
                         (-2784, -1920.0, 0.0, 52, 39, 12))
        g = package_grow.Grower(str(BAR))
        info = native_copy.clone_actor(g, p, old, where, rotation)
        tiles = native_copy.add_tiles_box(g, p, native_copy.piece_box(p, old, where, rotation))
        # the post crosses tiles 16-17 x 0-1 up to level 6; with a ring around and a level above, nothing was marked
        self.assertEqual(tiles['tiles'], [15, 18, 0, 2, 1, 7])
        self.assertEqual((tiles['seeded'], tiles['alreadyMarked']), (84, 0))
        vol = tiles['volume']
        native_copy.add_to_level(g, p, [info['actor'], vol['export']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            g.write(str(out))
            q = lighting.Package(out)
            v = vol['export']
            # no archetype, as the game's own rebuild volumes (the class default object stands in)
            self.assertEqual((q.cls(v), q.exports[v - 1]['arch']), ('XComRebuildWorldDataVolume', 0))
            self.assertEqual(q.own(v, 'Tag'), 'XComRebuildWorldDataVolume')
            comp = q.own(v, 'BrushComponent')
            self.assertEqual(q.own(v, 'CollisionComponent'), comp)
            self.assertEqual((q.exports[comp - 1]['outer'], q.name(q.exports[comp - 1]['arch'])),
                             (v, 'XComGame.Default__XComRebuildWorldDataVolume.BrushComponent0'))
            self.assertEqual(q.own(v, 'Brush'), p.own(p.by_name[PL + native_copy.REBUILD_TEMPLATE], 'Brush'))
            # its box is the seeded tiles' (plus the plan's few units), so the rebuild reaches every seeded tile
            lo, hi = native_copy.brush_box(q, v)
            box = [c for pair in zip(lo, hi) for c in pair]
            self.assertTrue(np.allclose(box, vol['bounds'], atol=0.01))
            self.assertTrue(np.allclose(box, seed_map.world_of(tiles['tiles'], grid)[:4] + (-8.0, box[5]),
                                        atol=0.01))
            # the seeds read back; the template is untouched
            e = [i for i in range(1, len(q.exports) + 1) if q.cls(i) == 'XComWorldDataContainer'][0]
            blob = q.data[q.exports[e - 1]['off']:q.exports[e - 1]['off'] + q.exports[e - 1]['size']]
            _, at, _ = world_links.static_tiles(blob)
            self.assertTrue(all(struct.unpack_from('<I', blob, at[tuple(t)])[0] & 0xFFF == native_copy.SEED
                                for t in tiles['seededTiles']))
            template = q.by_name[PL + native_copy.REBUILD_TEMPLATE]
            self.assertEqual((q.cls(template), q.own(template, 'Location')),
                             ('TriggerVolume', p.own(template, 'Location')))
            level = q.by_name['TheWorld.PersistentLevel']
            _, end = q.properties(level)
            count = struct.unpack_from('<i', q.data, end + 4)[0]
            self.assertEqual(struct.unpack_from('<2i', q.data, end + 8 + 4 * (count - 2)), (info['actor'], v))

    def test_a_copys_extra_lights_come_from_the_lights_after_the_edit(self):
        # editor lights plan 4.3, step 3: with light edits, a copy's lightmap may list only lights that exist after
        # the edit, as they are after it: a deleted light drops out, a light moved to the copy's place joins
        import native_lights
        p = self.p
        old = p.by_name[PL + 'XComLevelActor_37']
        comp = p.own(old, 'StaticMeshComponent')
        where, rotation = (-1155.0, -1874.4, 0.0), p.own(old, 'Rotation', [0, 0, 0])
        reg = native_lights.source_registry(p)
        base = native_copy.extra_lights(p, comp, where, rotation, lights=list(reg.values()))
        self.assertEqual(base, native_copy.extra_lights(p, comp, where, rotation))       # the default: the source's
        p0 = reg['PointLight_0']
        state = native_lights.prepare(p, dict(
            deletes=[dict(name='SpotLight_17')],
            changes=[dict(name='PointLight_0', location=[where[0] + 50, where[1], 200.0], rotation=[0, 0, 0], set={},
                          before=dict(p0['raw']))]))
        after = native_copy.extra_lights(p, comp, where, rotation, lights=list(state['after'].values()))
        names = {x['light'].split('.')[-2]: x for x in after}
        self.assertNotIn('SpotLight_17', names)
        self.assertTrue(names['PointLight_0']['kept'])
        self.assertEqual(names['PointLight_0']['guid'], p0['guids']['LightmapGuid'])
        self.assertNotIn('PointLight_0', {x['light'].split('.')[-2] for x in base})

    def test_a_copy_with_its_own_lighting_reads_cloned_textures_and_lists_the_lights_of_its_place(self):
        p = self.p
        old = p.by_name[PL + 'XComLevelActor_37']
        comp = p.own(old, 'StaticMeshComponent')
        where, rotation = (-1155.0, -1874.4, 0.0), p.own(old, 'Rotation', [0, 0, 0])
        # midway to the next lamp post, its spotlight reaches the copy; the original's lightmap lists only its own
        extra = native_copy.extra_lights(p, comp, where, rotation)
        kept = [x['light'].split('.')[-2] for x in extra if x['kept']]
        self.assertIn('SpotLight_17', kept)
        self.assertNotIn('SpotLight_53', [x['light'].split('.')[-2] for x in extra])
        g = package_grow.Grower(str(BAR))
        info = native_copy.clone_actor(g, p, old, where, rotation, own_lighting=True,
                                       extra_guids={comp: [x['guid'] for x in extra if x['kept']]})
        native_copy.add_to_level(g, p, [info['actor']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            g.write(str(out))
            # the grown map reads the original's texture caches where they are, through tfc-folder.txt
            lighting.link_caches(d, BAR.parent)
            self.assertEqual(lighting.cache_file(d, 'Lighting'), BAR.parent.resolve() / 'Lighting.tfc')
            q = lighting.Package(out)
            new_comp = info['mapping'][comp]
            a = lightmap_fields.component_fields(p, comp)['lods'][0]
            b = lightmap_fields.component_fields(q, new_comp)['lods'][0]
            # the lightmap: cloned textures, the same layout, the original's lights and then the added ones
            for sa, sb in zip(a['lightmap']['slots'][:2], b['lightmap']['slots'][:2]):
                self.assertEqual(sb['index'], info['textures'][sa['index']])
                self.assertEqual(q.cls(sb['index']), p.cls(sa['index']))
                ta, tb = (lightmap_fields.texture_fields(x, s['index']) for x, s in ((p, sa), (q, sb)))
                self.assertEqual([(m['width'], m['height'], m['bytes']) for m in ta['mips']],
                                 [(m['width'], m['height'], m['bytes']) for m in tb['mips']])
                self.assertEqual(sb['scale'], sa['scale'])
            for k in ('coordinateScale', 'coordinateBias'):
                self.assertEqual(b['lightmap'][k], a['lightmap'][k])
            ga = lighting.component_record(p, comp)['lods'][0]['lightmap']['lightGuids']
            gb = lighting.component_record(q, new_comp)['lods'][0]['lightmap']['lightGuids']
            self.assertEqual(gb[:len(ga)], ga)
            self.assertEqual(len(gb), len(ga) + len(kept))
            added = {l['component'].split('.')[-2] for l in relight.component_lights(q, gb)}
            self.assertEqual(added, {'SpotLight_53', *kept})
            # the moon's shadow map: the copy's own ShadowMap2D reading a cloned texture
            sm_a, sm_b = shadowmaps.shadow_maps(p, comp), shadowmaps.shadow_maps(q, new_comp)
            self.assertEqual([s['texture'] for s in sm_b], [info['textures'][s['texture']] for s in sm_a])
            self.assertEqual([s['guid'] for s in sm_b], [s['guid'] for s in sm_a])
            # the original still reads the original textures
            self.assertEqual(lightmap_fields.component_fields(q, comp)['lods'][0]['lightmap']['slots'][0]['index'],
                             a['lightmap']['slots'][0]['index'])

            # the relight: the scene before the edit leaves the copy out; the copy goes from the source's light where
            # it stands (its own spotlight) to its own where it stands (both spotlights, each 620 units away)
            copy = q.name(info['actor']).split('.')[-1]
            before = relight.Scene(q, samples=8, bounce_rays=0, emissive=False, remove_casters=[copy])
            after = relight.Scene(q, samples=8, bounce_rays=0, emissive=False)
            self.assertEqual(after.counts['casters'], before.counts['casters'] + 1)
            copies = relight.copy_components(q, [(copy, 'XComLevelActor_37')])
            self.assertEqual(copies, {q.name(new_comp): p.name(comp)})
            r = relight.relight_component(q, q.name(new_comp), before, after=after, source=p.name(comp))
            rep = r['report']
            self.assertEqual(rep['copyOf'], p.name(comp))
            self.assertEqual((rep['lights']['source'], rep['lights']['added']),
                             (1, ['TheWorld.PersistentLevel.SpotLight_17.SpotLightComponent_90']))
            self.assertGreater(rep['delta']['texelsChanged'], rep['texels']['covered'] // 3)
            # the lamp head's underside, beside its own light where the source stands, is far darker at the copy
            b, a2 = r['before'].sum(2), r['after'].sum(2)
            top = r['covered'] & (b >= np.percentile(b[r['covered']], 99))
            self.assertLess(float(np.median(a2[top] / b[top])), 0.7)
            # its moon shadow map from the source's place to its own
            sm = shadowmaps.shadow_maps(q, new_comp)[0]
            moon = shadowmaps.dominant_lights(q)[sm['guid']]
            got = shadowmaps.relight_shadow_map(q, new_comp, sm, moon, before.occluder, after.occluder,
                                                before.level_scale, source=(comp, shadowmaps.shadow_maps(q, comp)[0]))
            self.assertIsNotNone(got)
            self.assertEqual(got['report']['copyOf'], p.name(comp))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class MadeShadowMaps(unittest.TestCase):
    """(follow-up 2.2) The donor's shadow maps a copy made from numbers does not clone: the moon's on the component that
    gets the made mesh, for a donor outdoors; none for an inside wall, which lists the moon irrelevant; none where the
    map names no dominant light."""

    def test_the_moons_map_of_the_component_that_gets_the_made_mesh(self):
        import frac_walls
        p = lighting.Package(BAR)
        moon = native_copy.dominant_guid(p)
        asphalt = p.by_name[PL + 'XComLevelActor_131']
        comp = frac_walls.made_component(p, asphalt, dict(kind='ground'))
        self.assertEqual(comp, p.own(asphalt, 'StaticMeshComponent'))
        (sm,) = shadowmaps.shadow_maps(p, comp)
        self.assertEqual(native_copy.made_shadow_maps(p, [comp], guid=moon), {sm['export']})
        self.assertEqual(native_copy.made_shadow_maps(p, [comp]), set())
        inside = p.by_name[PL + 'XComDecoFracLevelActor_17']
        wall = frac_walls.made_component(p, inside, dict(kind='fracWall'))
        self.assertEqual(wall, p.own(inside, 'FracturedStaticMeshComponent'))
        self.assertEqual(native_copy.made_shadow_maps(p, [wall], guid=moon), set())
        # a copy that keeps its donor's mesh, or no request, has no made component
        self.assertIsNone(frac_walls.made_component(p, asphalt, dict(kind='relit')))
        self.assertIsNone(frac_walls.made_component(p, asphalt, None))


class BulkOffsets(unittest.TestCase):
    """An inline bulk record's payload offset follows its export to a new place (no game data)."""
    OFF = 1000          # where the export lies in the source

    def export(self, payload=b'\x07' * 8, at=20, flags=0, offset=None):
        """An export's bytes with one bulk record at `at`: flags, element count, bytes, offset in file, payload."""
        meta = self.OFF + at
        record = struct.pack('<4i', flags, len(payload), len(payload), meta + 16 if offset is None else offset)
        return bytearray(bytes(at) + record + (b'' if flags & 1 else payload) + bytes(12)), meta

    def test_the_offset_moves_with_the_export(self):
        data, meta = self.export()
        native_copy.move_bulk_offsets(None, data, [meta], self.OFF, 5000)
        self.assertEqual(struct.unpack_from('<4i', data, 20), (0, 8, 8, 5000 + 20 + 16))

    def test_bytes_put_in_before_a_record_move_it_and_those_after_it_dont(self):
        data, meta = self.export()
        data[4:4] = bytes(16)
        data[len(data) - 4:len(data) - 4] = bytes(16)
        native_copy.move_bulk_offsets(None, data, [meta], self.OFF, 5000, [(4, 16), (48, 16)])
        self.assertEqual(struct.unpack_from('<4i', data, 36), (0, 8, 8, 5000 + 36 + 16))

    def test_an_empty_record_moves_too_and_one_stored_elsewhere_stays(self):
        data, meta = self.export(payload=b'')
        native_copy.move_bulk_offsets(None, data, [meta], self.OFF, 5000)
        self.assertEqual(struct.unpack_from('<4i', data, 20), (0, 0, 0, 5000 + 36))
        data, meta = self.export(flags=1, offset=123456)
        native_copy.move_bulk_offsets(None, data, [meta], self.OFF, 5000)
        self.assertEqual(struct.unpack_from('<4i', data, 20)[3], 123456)

    def test_a_record_that_points_elsewhere_is_refused(self):
        data, meta = self.export(offset=77)
        with self.assertRaisesRegex(ValueError, 'points to 77'):
            native_copy.move_bulk_offsets(None, data, [meta], self.OFF, 5000)


# a map with a piece lit per vertex (T-26): CLrgScout_Stonewall's vine, from the LWR install
STONEWALL, NO_STONEWALL = labpaths.test_file('XCOM_STONEWALL_UPK', labpaths.lwr_cooked('CLrgScout_Stonewall.upk'),
                                             'CLrgScout_Stonewall.upk')


@unittest.skipUnless(STONEWALL and STONEWALL.exists(), NO_STONEWALL)
class VertexLit(unittest.TestCase):
    VINE = 'XComDestructibleActor_124'

    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(STONEWALL)

    def vertex_lightmap(self, pkg, comp):
        """(owner, [(flags, count, bytes, offset - record's own place, payload)]) of the component's vertex lightmap."""
        found = native_copy.vertex_lightmaps(pkg, comp)
        self.assertEqual(len(found), 1)
        records = []
        for meta in found[0]['bulkOffsets']:
            flags, count, nbytes, offset = struct.unpack_from('<4i', pkg.data, meta)
            records.append((flags, count, nbytes, offset - meta, bytes(pkg.data[meta + 16:meta + 16 + nbytes])))
        return found[0]['owner'], records

    def test_the_vine_is_lit_per_vertex_and_has_no_lighting_textures(self):
        p = self.p
        actor = p.by_name[PL + self.VINE]
        comp = p.own(actor, 'StaticMeshComponent')
        owner, records = self.vertex_lightmap(p, comp)
        self.assertEqual(owner, comp)
        self.assertEqual([r[3] for r in records], [16, 16])
        self.assertGreater(records[0][2], 0)
        self.assertEqual(native_copy.lighting_textures(p, native_copy.subtree(p, actor)), [])

    def test_a_copy_of_the_vine_owns_its_vertex_lightmap_where_it_lies(self):
        # the build's copy (unbaked, as a quick build makes it): a new actor of the level whose mesh component owns
        # its lightmap, the samples the original's, their bulk records pointing at the copy's own bytes
        p = self.p
        actor = p.by_name[PL + self.VINE]
        comp = p.own(actor, 'StaticMeshComponent')
        loc = list(p.own(actor, 'Location'))
        copies = [dict(actor=self.VINE, location=[loc[0], loc[1] - 192.0, loc[2]])]
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(STONEWALL, d, 'StonewallVine', copies))
            sec = m['nativeCopies']['copies'][0]
            self.assertEqual(sec['textures'], {})
            self.assertIn([p.name(comp), 'LightMap.Owner'], [list(x) for x in sec['remapped']])
            q = lighting.Package(Path(d) / 'StonewallVine.upk')
            new = sec['export']
            new_comp = q.own(new, 'StaticMeshComponent')
            self.assertEqual(q.exports[new_comp - 1]['outer'], new)
            self.assertIn(new, NativeCopy.level_actors(q))
            owner, records = self.vertex_lightmap(q, new_comp)
            self.assertEqual(owner, new_comp)
            self.assertEqual(records, self.vertex_lightmap(p, comp)[1])
            # the copy's data lies after the original package, and its records point there
            self.assertGreater(q.exports[new_comp - 1]['off'], len(p.data))
            # the original keeps its own
            self.assertEqual(self.vertex_lightmap(q, comp), self.vertex_lightmap(p, comp))
            # it casts its shadow from its new place: the original's triangles, two tiles along
            import shadows
            self.assertTrue(shadows.is_caster(q, new_comp))
            tris = shadows.caster_triangles(q, [new_comp])[0]
            self.assertTrue(np.allclose(tris, shadows.caster_triangles(p, [comp])[0] + [0.0, -192.0, 0.0], atol=0.01))

    def test_a_clone_given_new_data_afterwards_is_caught(self):
        # the check after the write: a clone relocated after it was made leaves its bulk offsets behind
        p = self.p
        actor = p.by_name[PL + self.VINE]
        g = package_grow.Grower(str(STONEWALL))
        info = native_copy.clone_actor(g, p, actor, (0.0, 0.0, 0.0), (0, 0, 0))
        new_comp = info['mapping'][p.own(actor, 'StaticMeshComponent')]
        g.relocate(new_comp, g.export_data(new_comp))
        native_copy.add_to_level(g, p, [info['actor']])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'Stonewall.upk'
            g.write(str(out))
            with self.assertRaisesRegex(ValueError, 'bulk record'):
                native_copy.check_vertex_lightmaps(lighting.Package(out), info['mapping'])


@unittest.skipUnless(BLANK and BLANK.exists(), NO_BLANK)
class BakedDirectionalLight(unittest.TestCase):
    """(EXP-79 run D) The blank map's only light is a baked DirectionalLight, which its own pieces' lightmaps list. A
    piece of another map, or a ground shape made from one, brought onto it is given that light, as the point and spot
    lights of a game map are: without it the relight gave it bounce light alone and it was drawn black."""

    def test_a_piece_of_another_map_is_given_the_maps_directional_light(self):
        import native_lights
        p = lighting.Package(BLANK)
        light = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'DirectionalLightComponent'
                 and p.name(i).startswith(PL)]
        self.assertEqual(len(light), 1)
        # a ground plane of the map's own, treated as a piece of another map (its list taken as none of this map's)
        plane = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'StaticMeshComponent'
                     and p.name(i).startswith(PL + 'XComLevelActor_')
                     and lighting.component_record(p, i)['lods'][0]['lightmap'].get('type') == 2)
        extra = native_copy.extra_lights(p, plane, [0.0, 0.0, 4.0], [0, 0, 0], fresh=True,
                                         lights=list(native_lights.source_registry(p).values()))
        (found,) = [x for x in extra if x['light'] == p.name(light[0])]
        self.assertTrue(found['kept'])
        field = native_copy.guid_field(p, list(native_lights.source_registry(p).values()))
        self.assertEqual(found['guid'], bytes(p.effective(light[0], field)))
        # its own list holds the light already: nothing is added
        self.assertEqual([x for x in native_copy.extra_lights(p, plane, [0.0, 0.0, 4.0], [0, 0, 0])
                          if x['light'] == p.name(light[0])], [])

    @unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
    def test_a_dominant_light_is_not_listed(self):
        # URB_Bar's moon is a dominant light: it lights by shadow maps, never a lightmap's list
        p = lighting.Package(BAR)
        old = p.by_name[PL + 'XComLevelActor_37']
        comp = p.own(old, 'StaticMeshComponent')
        extra = native_copy.extra_lights(p, comp, (-1155.0, -1874.4, 0.0), p.own(old, 'Rotation', [0, 0, 0]), fresh=True)
        self.assertFalse([x for x in extra if 'Directional' in x['light']])


if __name__ == '__main__':
    unittest.main()
