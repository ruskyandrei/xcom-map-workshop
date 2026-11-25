"""A bare map equipped for a battle and the Build (shell.py; private/plans/done/prefab-library-plan.md 5.10, EXP-43).

The checks of the game's blank map read the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED
names) and skip without it."""
from pathlib import Path
import struct
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
import scene_metadata  # noqa: E402
import shell  # noqa: E402
from package import Package  # noqa: E402

BLANK, NO_BLANK = labpaths.install_map('CB2_MP_Blank')
BAR, NO_BAR = labpaths.install_map('URB_Bar')
POLICE, NO_POLICE = labpaths.install_map('URB_PoliceStation')
INTRO, NO_INTRO = labpaths.install_map('Act1_IntroLevel')
FARM, NO_FARM = labpaths.install_map('CsmallScout_Farm')

_EQUIPPED = {}


def equipped(**options):
    """(the equip's report, the written map) of the blank map equipped with `options`, written once for every class
    of the module that only reads it (review finding 61: a whole-map write each)."""
    key = tuple(sorted(options.items()))
    if key not in _EQUIPPED:
        tmp = tempfile.TemporaryDirectory()
        report = shell.equip(BLANK, tmp.name, **options)
        _EQUIPPED[key] = (tmp, report, Package(Path(tmp.name) / Path(BLANK).name))
    return _EQUIPPED[key][1:]


def tearDownModule():
    for tmp, _, _ in _EQUIPPED.values():
        tmp.cleanup()
    _EQUIPPED.clear()


class Fit(unittest.TestCase):
    def test_a_long_enough_span_moves_the_least_and_keeps_its_length(self):
        self.assertEqual(shell.fit(-1920, 1824, -1344, 2112), (1.0, -1632.0))
        self.assertEqual(shell.fit(-2784, 2208, -2112, 1344), (1.0, -2784.0))

    def test_a_shorter_span_is_stretched_to_the_grid(self):
        scale, lo = shell.fit(-1920, 1824, -1344, 3840)
        self.assertAlmostEqual(scale, 5184 / 3744)
        self.assertEqual(lo, -1344)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class OrdinaryMap(unittest.TestCase):
    def test_a_map_of_the_game_lacks_nothing(self):
        self.assertEqual(shell.needs(Package(BAR)), [])
        self.assertEqual(len(shell.soldier_points(Package(BAR))), 6)


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class BlankMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BLANK, cls.tmp.name)
        cls.before = Package(BLANK)
        cls.p = Package(Path(cls.tmp.name) / Path(BLANK).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_blank_map_lacks_all_three(self):
        self.assertEqual(shell.needs(self.before), ['soldiers', 'cursor', 'template'])
        self.assertEqual(self.report['needs'], ['soldiers', 'cursor', 'template'])

    def test_equipped_it_lacks_nothing(self):
        self.assertEqual(shell.needs(self.p), [])
        native_copy.rebuild_template(self.p)

    def test_six_soldier_points_stand_on_the_team_one_points(self):
        points = shell.soldier_points(self.p)
        self.assertEqual(len(points), 6)
        self.assertEqual([list(self.p.own(i, 'Location')) for i in points], shell.squad_places(self.before))

    def test_the_cursor_volumes_cover_the_grid_a_storey_each(self):
        grid = shell.grid_box(self.p)
        live = shell.listed(self.p)
        volumes = [i for i in shell.actors(self.p, 'XComCursorVolume') if i in live]
        self.assertEqual(sorted(self.p.effective(i, 'm_iFloorNumber') for i in volumes), [1, 2, 3, 4])
        for i in volumes:
            b = scene_metadata.volume_bounds(self.p, i)
            for k in range(2):
                self.assertLessEqual(b['min'][k], grid[k] + 0.01)
                self.assertGreaterEqual(b['max'][k], grid[k + 3] - 0.01)
        bottoms = sorted(scene_metadata.volume_bounds(self.p, i)['min'][2] for i in volumes)
        self.assertAlmostEqual(bottoms[0], grid[2], places=2)
        # even storeys of 192 from the grid's bottom, floor by floor, the last one to the grid's top
        by_floor = sorted(volumes, key=lambda i: self.p.effective(i, 'm_iFloorNumber'))
        for n, i in enumerate(by_floor):
            b = scene_metadata.volume_bounds(self.p, i)
            self.assertAlmostEqual(b['min'][2], grid[2] + 192 * n, places=2)
            self.assertAlmostEqual(b['max'][2], grid[5] if n == 3 else grid[2] + 192 * (n + 1), places=2)

    def test_the_template_is_staged_not_placed(self):
        template = self.p.by_name[shell.LEVEL + '.' + native_copy.rebuild_template(self.p)]
        self.assertNotIn(template, shell.listed(self.p))

    def test_the_maps_own_actors_stay_listed(self):
        self.assertTrue(shell.listed(self.before) <= shell.listed(self.p))
        self.assertEqual(len(shell.listed(self.p)) - len(shell.listed(self.before)), 10)

    def test_an_equipped_map_is_left_alone(self):
        with tempfile.TemporaryDirectory() as again:
            report = shell.equip(Path(self.tmp.name) / Path(BLANK).name, again, cooked=Path(BLANK).parent)
            self.assertEqual(report['needs'], [])
            self.assertFalse((Path(again) / Path(BLANK).name).exists())


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class LargerGrid(unittest.TestCase):
    """The blank map equipped and made 54 by 45 tiles (prefab plan 5.11)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BLANK, cls.tmp.name, grid=(54, 45))
        cls.p = Package(Path(cls.tmp.name) / Path(BLANK).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_part_says_the_new_size(self):
        import struct
        import world_grid
        import world_links
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (54, 45, 12))
        self.assertAlmostEqual(grid['ox'], -2112, places=2)
        self.assertAlmostEqual(grid['oy'], -1344, places=2)
        volume = shell.actors(self.p, 'XComLevelVolume')[0]
        world = self.p.own(volume, 'WorldData')
        self.assertEqual([self.p.own(world, k) for k in ('NumX', 'NumY', 'NumZ', 'NumTiles')], [54, 45, 12, 54 * 45 * 12])
        self.assertEqual(struct.unpack('<6f', self.p.own(world, 'WorldBounds')[:24])[3:5], (3073.0, 2977.0))
        _, blob = world_grid.container_of(self.p)
        wd = world_links.parse_container(blob)
        self.assertEqual(tuple(wd['dims']), (54, 45, 12))
        # each ground tile names a ground plane in the level's list, 81 tiles to a plane
        live = shell.listed(self.p)
        planes = {}
        for t in wd['floor'].values():
            planes[t['value']['actor']] = planes.get(t['value']['actor'], 0) + 1
        self.assertEqual(len(planes), 30)
        self.assertTrue(all(a in live and self.p.cls(a) == 'XComLevelActor' and n == 81 for a, n in planes.items()))

    def test_the_cursor_volumes_are_fitted_to_it(self):
        live = shell.listed(self.p)
        for i in shell.actors(self.p, 'XComCursorVolume'):
            self.assertIn(i, live)
            b = scene_metadata.volume_bounds(self.p, i)
            self.assertLessEqual(b['min'][0], -2112 + 0.01)
            self.assertGreaterEqual(b['max'][0], 3072 - 0.01)
            self.assertAlmostEqual(b['min'][1], -1344, places=1)     # stretched in y: the bar's are 39 tiles deep
            self.assertAlmostEqual(b['max'][1], 2976, places=1)

    def test_a_rebuild_volume_covers_the_whole_grid(self):
        live = shell.listed(self.p)
        boxes = [scene_metadata.volume_bounds(self.p, i) for i in shell.actors(self.p, 'XComRebuildWorldDataVolume') if i in live]
        self.assertEqual(len(boxes), 1)
        self.assertEqual([round(v) for v in boxes[0]['min'][:2] + boxes[0]['max'][:2]], [-2112, -1344, 3072, 2976])

    def test_the_same_grid_again_changes_nothing(self):
        with tempfile.TemporaryDirectory() as again:
            report = shell.equip(Path(self.tmp.name) / Path(BLANK).name, again, cooked=Path(BLANK).parent, grid=(54, 45))
            self.assertIsNone(report['written'])


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class SmallerGrid(unittest.TestCase):
    """The blank map equipped and made 30 by 28 tiles and 9 levels (clear-map plan, section 7 step 5): from the same
    corner and bottom."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BLANK, cls.tmp.name, grid=(30, 28), levels=9)
        cls.p = Package(Path(cls.tmp.name) / Path(BLANK).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_part_says_the_new_size(self):
        import struct
        import world_grid
        import world_links
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (30, 28, 9))
        self.assertEqual([round(grid[k], 2) for k in ('ox', 'oy', 'oz')], [-2112, -1344, 0])
        volume = shell.actors(self.p, 'XComLevelVolume')[0]
        world = self.p.own(volume, 'WorldData')
        self.assertEqual([self.p.own(world, k) for k in ('NumX', 'NumY', 'NumZ', 'NumTiles')], [30, 28, 9, 30 * 28 * 9])
        bounds = struct.unpack('<6f', self.p.own(world, 'WorldBounds')[:24])
        self.assertEqual([round(v, 2) for v in bounds], [-2113.0, -1345.0, -1.0, 769.0, 1345.0, 577.0])
        self.assertEqual(self.report['resized']['before'], [36, 36, 12])
        self.assertEqual(self.report['resized']['grid'], [30, 28, 9])
        self.assertEqual(self.report['resized']['planesLaid'], 0)
        _, blob = world_grid.container_of(self.p)
        wd = world_links.parse_container(blob)
        self.assertEqual(tuple(wd['dims']), (30, 28, 9))
        self.assertEqual(len(wd['floor']), 30 * 28)
        self.assertTrue(all(all(0 <= l['to'][k] < (30, 28, 9)[k] for k in range(3)) for l in world_links.all_links(wd)))

    def test_the_level_volume_is_the_grid(self):
        volume = shell.actors(self.p, 'XComLevelVolume')[0]
        b = scene_metadata.volume_bounds(self.p, volume)
        self.assertEqual([round(v, 1) for v in b['min'] + b['max']], [-2112, -1344, 0, 768, 1344, 576])

    def test_a_rebuild_volume_covers_the_whole_grid(self):
        live = shell.listed(self.p)
        boxes = [scene_metadata.volume_bounds(self.p, i) for i in shell.actors(self.p, 'XComRebuildWorldDataVolume') if i in live]
        self.assertEqual(len(boxes), 1)
        self.assertEqual([round(v) for v in boxes[0]['min'][:2] + boxes[0]['max'][:2]], [-2112, -1344, 768, 1344])

    def test_the_cursor_storeys_start_at_the_bottom_and_cover_the_grid(self):
        live = shell.listed(self.p)
        floors = sorted((self.p.effective(i, 'm_iFloorNumber'), scene_metadata.volume_bounds(self.p, i))
                        for i in shell.actors(self.p, 'XComCursorVolume') if i in live)
        # three storeys of 192 make the grid's 576; the bar's volumes are longer than the grid in x and y and keep
        # their length (fit), as on the blank map's own size
        self.assertEqual([(round(b['min'][2]), round(b['max'][2])) for _, b in floors[:3]],
                         [(192 * n, 192 * (n + 1)) for n in range(3)])
        for _, b in floors:
            self.assertTrue(b['min'][0] <= -2112 + 0.01 and b['max'][0] >= 768 - 0.01)
            self.assertTrue(b['min'][1] <= -1344 + 0.01 and b['max'][1] >= 1344 - 0.01)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class SmallerRealMap(unittest.TestCase):
    """URB_Bar made 48 by 35 tiles and 10 levels (clear-map plan, section 7 step 5): a map that lacks nothing, with its
    own cursor volumes."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BAR, cls.tmp.name, grid=(48, 35), levels=10)
        cls.p = Package(Path(cls.tmp.name) / Path(BAR).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_part_says_the_new_size(self):
        import struct
        import world_grid
        import world_links
        before = native_copy.level_grid(Package(BAR))
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (48, 35, 10))
        self.assertEqual([round(grid[k]) for k in ('ox', 'oy', 'oz')], [round(before[k]) for k in ('ox', 'oy', 'oz')])
        volume = next(i for i in shell.actors(self.p, 'XComLevelVolume') if self.p.own(i, 'Brush', 0) > 0)
        world = self.p.own(volume, 'WorldData')
        self.assertEqual([self.p.own(world, k) for k in ('NumX', 'NumY', 'NumZ', 'NumTiles')], [48, 35, 10, 48 * 35 * 10])
        ox, oy, oz = (round(before[k]) for k in ('ox', 'oy', 'oz'))
        bounds = struct.unpack('<6f', self.p.own(world, 'WorldBounds')[:24])
        self.assertEqual([round(v, 2) for v in bounds[3:]], [ox + 96 * 48 + 1.0, oy + 96 * 35 + 1.0, oz + 64 * 10 + 1.0])
        self.assertEqual(self.report['resized']['planesLaid'], 0)       # no new area to lay ground over
        _, blob = world_grid.container_of(self.p)
        wd = world_links.parse_container(blob)
        self.assertEqual(tuple(wd['dims']), (48, 35, 10))
        self.assertTrue(all(all(0 <= l['to'][k] < (48, 35, 10)[k] for k in range(3)) for l in world_links.all_links(wd)))
        self.assertEqual(world_grid.encode(world_grid.decode(blob)), blob)
        b = scene_metadata.volume_bounds(self.p, volume)
        self.assertEqual([round(v, 1) for v in b['min'] + b['max']], [ox, oy, oz, ox + 96 * 48, oy + 96 * 35, oz + 640])


def cursor_boxes(p):
    """The listed cursor volumes of `p`: {name: (floor, [x0, y0, z0, x1, y1, z1])}."""
    live = shell.listed(p)
    out = {}
    for i in shell.actors(p, 'XComCursorVolume'):
        if i in live:
            b = scene_metadata.volume_bounds(p, i)
            out[p.name(i).rsplit('.', 1)[-1]] = (p.effective(i, 'm_iFloorNumber'), b['min'] + b['max'])
    return out


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class GrownRealMap(unittest.TestCase):
    """URB_Bar grown as it is to 60 by 45 tiles and 18 levels (grow_cursors; 13 November 2026): its four
    whole-map cursor volumes stretched to the new far sides at their own heights, and two even storeys over the
    whole grid from the top of its own (768) to the new top (1152), floors 5 and 6."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BAR, cls.tmp.name, grid=(60, 45), levels=18)
        cls.p = Package(Path(cls.tmp.name) / Path(BAR).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_own_volumes_stretched_and_two_storeys_over_the_new_levels(self):
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (60, 45, 18))
        x1, y1, top = grid['ox'] + 96 * 60, grid['oy'] + 96 * 45, grid['oz'] + 64 * 18
        before, after = cursor_boxes(Package(BAR)), cursor_boxes(self.p)
        for name, (floor, b) in before.items():
            f, a = after[name]
            self.assertEqual(f, floor)
            self.assertEqual([round(v, 1) for v in a[:3]] + [round(a[5], 1)], [round(v, 1) for v in b[:3]] + [round(b[5], 1)])
            self.assertEqual([round(a[3], 1), round(a[4], 1)], [round(x1, 1), round(y1, 1)])
        self.assertEqual(sorted(self.report['grownCursors']['stretched']), sorted(before))
        made = sorted(v for k, v in after.items() if k not in before)
        self.assertEqual([f for f, _ in made], [5, 6])
        self.assertEqual([(round(b[2]), round(b[5])) for _, b in made], [(768, 960), (960, round(top))])
        for _, b in made:
            self.assertEqual([round(v, 1) for v in (b[0], b[1], b[3], b[4])],
                             [round(grid['ox'], 1), round(grid['oy'], 1), round(x1, 1), round(y1, 1)])


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class GrownIntroScenery(unittest.TestCase):
    """Act1_IntroLevel grown as it is from 62 by 19 to 95 by 25 tiles, no ground laid (the user's intro+, F-100): the
    ground planes and pavements it is seen against past its far sides save their collision off, and they are made
    walkable; nothing else changes its collision."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(INTRO, cls.tmp.name, grid=(95, 25), levels=18, ground=False)
        cls.own = Package(INTRO)
        cls.p = Package(Path(cls.tmp.name) / Path(INTRO).name)
        cls.walked = cls.report['resized']['walkableScenery']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def actor(self, p, name):
        return p.by_name[shell.LEVEL + '.' + name]

    def test_the_ground_and_pavements_past_the_far_sides_are_walkable(self):
        # a ground plane and a pavement past the far X side, a pavement past the far Y side, and a street block
        # across the far X side
        for name in ('XComLevelActor_13', 'XComLevelActor_183', 'XComLevelActor_230', 'XComLevelActor_256',
                     'XComLevelActor_444'):
            self.assertIn(name, self.walked)
        for name in self.walked:
            i = self.actor(self.p, name)
            self.assertIs(self.p.effective(i, 'bCollideActors'), True, name)
            self.assertIs(self.p.effective(i, 'bPathColliding'), True, name)
            self.assertTrue(native_copy.collides(self.p, i), name)
            for ci in native_copy.subtree(self.p, i):
                if native_copy.static_mesh(self.p, ci) > 0:
                    self.assertIsNot(self.p.effective(ci, 'BlockRigidBody', True), False, name)

    def test_each_one_is_low_ground_level_scenery_reaching_the_new_area(self):
        g0 = native_copy.level_grid(self.own)
        x1, y1 = g0['ox'] + 96 * g0['nx'], g0['oy'] + 96 * g0['ny']
        grown = dict(g0, nx=95, ny=25)
        for name in self.walked:
            i = self.actor(self.own, name)
            box = native_copy.piece_box(self.own, i, self.own.own(i, 'Location', [0.0, 0.0, 0.0]),
                                        self.own.own(i, 'Rotation', [0, 0, 0]))
            self.assertTrue(native_copy.walkable_scenery(self.own, i, box), name)
            self.assertTrue(g0['oz'] - 16 <= box[4] and box[5] <= g0['oz'] + 64 * 18, name)
            self.assertTrue(native_copy.in_grid(box, grown) and (box[1] > x1 or box[3] > y1), name)

    def test_a_piece_whose_floor_the_project_turns_off_is_left_as_it_is(self):
        # piece flags plan, 6.2: the user's Floor off gives way to nothing, F-100's scenery floor included
        g0 = native_copy.level_grid(self.own)
        names = lambda found: {self.own.name(i).rsplit('.', 1)[-1] for i, _, _ in found}    # noqa: E731
        every = names(shell.scenery_to_walk(self.own, g0, 95, 25, 18))
        kept = names(shell.scenery_to_walk(self.own, g0, 95, 25, 18, floor_off=['XComLevelActor_13']))
        self.assertEqual(every - kept, {'XComLevelActor_13'})

    def test_nothing_else_changes_its_collision(self):
        # a street block south of the grid that crosses only the map's own area, the backdrop's buildings, and the
        # ground the map plays on keep theirs
        for name in ('XComLevelActor_110', 'StaticMeshActor_1', 'XComLevelActor_181'):
            self.assertNotIn(name, self.walked)
        live = shell.listed(self.own)
        for i in sorted(live):
            if i <= 0 or self.own.cls(i) not in ('XComLevelActor', 'StaticMeshActor'):
                continue
            name = self.own.name(i).rsplit('.', 1)[-1]
            if name in self.walked:
                continue
            j = self.actor(self.p, name)
            for flag in ('bCollideActors', 'bPathColliding'):
                self.assertEqual(self.p.effective(j, flag, True), self.own.effective(i, flag, True), name)
        print('\nAct1_IntroLevel grown: %d pieces of scenery made walkable' % len(self.walked))


@unittest.skipUnless(FARM and FARM.exists(), NO_FARM)
class GrownFarmPlateau(unittest.TestCase):
    """CsmallScout_Farm grown as it is from 70 to 91 tiles along Y, its ground laid (the user's farm++, F-100): its play
    area's ground is at -128, the grid's bottom, and the new strip takes in a raised backdrop whose ground planes, at
    0, are floor pieces already. Their tiles, two levels up, go in the rebuild's queue; no ground plane is laid under
    them; the sky's ground plane under the world is no part of it."""
    @classmethod
    def setUpClass(cls):
        import world_grid
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(FARM, cls.tmp.name, grid=(67, 91), levels=18)
        cls.own = Package(FARM)
        cls.p = Package(Path(cls.tmp.name) / Path(FARM).name)
        cls.r = cls.report['resized']
        cls.tiles = world_grid.decode(world_grid.container_of(cls.p)[1])['stores'][0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_plateaus_ground_is_floor_and_the_sky_plane_is_not(self):
        for name in ('XComLevelActor_106', 'XComLevelActor_363'):
            self.assertIn(name, self.r['sceneryFloors'])
        self.assertEqual(self.r['walkableScenery'], [])
        self.assertNotIn('XComLevelActor_600', self.r['sceneryFloors'])

    def test_its_tiles_are_queued_and_the_rebuild_reaches_them(self):
        import world_grid
        g0 = native_copy.level_grid(self.own)
        origin = [round(g0[k]) for k in ('ox', 'oy', 'oz')]
        i = self.own.by_name[shell.LEVEL + '.XComLevelActor_106']
        box = native_copy.piece_box(self.own, i, self.own.own(i, 'Location'), self.own.own(i, 'Rotation', [0, 0, 0]))
        tiles = shell.scenery_tiles(box, origin, 67, 91)
        self.assertTrue(tiles and all(z == 2 for _, _, z in tiles))      # 0 is two levels over -128
        for tile in tiles:
            raw, present = self.tiles[tile]
            self.assertTrue(present and struct.unpack('<I', raw)[0] & 0xFFF, tile)
        self.assertTrue(any(struct.unpack('<I', self.tiles[t][0])[0] & world_grid.SEED for t in tiles))
        self.assertGreaterEqual(self.r['rebuildVolume']['bounds'][5], 64.0)

    def test_the_rebuild_leaves_the_scouts_diagonal_cover_alone(self):
        # the scout's eight slanted corners carry diagonal cover, which a rebuilt tile loses for good (F-149): the
        # grown grid's rebuild is made of volumes that take none of them, nor the two tiles over each, and every
        # other tile the one volume was there for
        diagonal = native_copy.diagonal_tiles(self.own)
        self.assertEqual(len(diagonal), 8)
        self.assertEqual(native_copy.diagonal_tiles(self.p), diagonal)       # the grown grid keeps them
        fitted = self.r['rebuildVolume']['fitted']
        self.assertEqual(sorted(tuple(t) for t in fitted['spared']), sorted(diagonal))
        listed = [a for a in shell.listed(self.p) if self.p.cls(a) == 'XComRebuildWorldDataVolume']
        self.assertEqual(listed, fitted['volumes'])
        self.assertGreater(len(listed), 1)
        order = native_copy.rebuild_order(self.p)
        kept = {(x, y, z + n) for x, y, z in diagonal for n in range(3)}
        self.assertEqual(kept & set(order), set())
        top = int((self.r['rebuildVolume']['bounds'][5] - native_copy.level_grid(self.p)['tz']) // 64)
        missed = [t for t, (raw, present) in self.tiles.items()
                  if t[2] < top and present and struct.unpack('<I', raw)[0] & 0xFFF and t not in order and t not in kept]
        self.assertEqual(missed, [])

    def test_no_ground_plane_is_laid_under_it(self):
        g0 = native_copy.level_grid(self.own)
        mesh = self.own.effective(self.own.own(self.own.by_name[shell.LEVEL + '.' + self.r['groundPlane']],
                                               'StaticMeshComponent', 0), 'StaticMesh')
        live = shell.listed(self.p)
        laid = [j for j in live if j > len(self.own.exports) and self.p.cls(j) == 'XComLevelActor'
                and self.p.effective(self.p.own(j, 'StaticMeshComponent', 0), 'StaticMesh') == mesh]
        self.assertEqual(len(laid), self.r['planesLaid'])
        self.assertTrue(self.r['blocksUnderScenery'])
        i = self.own.by_name[shell.LEVEL + '.XComLevelActor_106']
        b = native_copy.piece_box(self.own, i, self.own.own(i, 'Location'), self.own.own(i, 'Rotation', [0, 0, 0]))
        for j in laid:
            x, y, _ = self.p.own(j, 'Location')
            self.assertFalse(b[0] < x < b[1] and b[2] < y < b[3], self.p.name(j))
        print('\nCsmallScout_Farm grown: %d floor pieces of scenery, %d tiles queued, %d blocks left to them, %d planes laid'
              % (len(self.r['sceneryFloors']), self.r['sceneryTilesSeeded'], len(self.r['blocksUnderScenery']),
                 self.r['planesLaid']))


@unittest.skipUnless(POLICE and POLICE.exists(), NO_POLICE)
class GrownPoliceStation(unittest.TestCase):
    """URB_PoliceStation grown as it is to 55 by 50 tiles and 18 levels: its 63 cursor volumes are fitted to its
    buildings; the ones short of the far sides keep their places, the rest reach the new sides, and storeys over the
    whole grid start at the top of its own."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(POLICE, cls.tmp.name, grid=(55, 50), levels=18)
        cls.p = Package(Path(cls.tmp.name) / Path(POLICE).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_fitted_volumes_stay_and_storeys_go_on_from_the_top(self):
        own = Package(POLICE)
        g0 = native_copy.level_grid(own)
        grid = native_copy.level_grid(self.p)
        old_x1, old_y1 = g0['ox'] + 96 * g0['nx'], g0['oy'] + 96 * g0['ny']
        x1, y1, top = grid['ox'] + 96 * 55, grid['oy'] + 96 * 50, grid['oz'] + 64 * 18
        before, after = cursor_boxes(own), cursor_boxes(self.p)
        grown = self.report['grownCursors']
        moved = 0
        for name, (floor, b) in before.items():
            f, a = after[name]
            self.assertEqual(f, floor)
            reach = [b[3] >= old_x1 - 1, b[4] >= old_y1 - 1]
            if name in grown['turned'] or not any(reach):
                self.assertEqual([round(v, 1) for v in a], [round(v, 1) for v in b], name)
                continue
            moved += 1
            self.assertIn(name, grown['stretched'])
            self.assertEqual([round(v, 1) for v in a[:3]] + [round(a[5], 1)], [round(v, 1) for v in b[:3]] + [round(b[5], 1)])
            self.assertEqual(round(a[3], 1), round(x1, 1) if reach[0] else round(b[3], 1))
            self.assertEqual(round(a[4], 1), round(y1, 1) if reach[1] else round(b[4], 1))
        self.assertEqual(moved, len(grown['stretched']))
        self.assertLess(moved, len(before))                  # most are fitted to a building
        own_top = max(b[5] for _, b in before.values())
        highest = max(f for f, _ in before.values())
        made = sorted(v for k, v in after.items() if k not in before)
        n = max(1, round((top - own_top) / 192))
        self.assertEqual([f for f, _ in made], list(range(highest + 1, highest + 1 + n)))
        self.assertAlmostEqual(made[0][1][2], own_top, places=1)
        self.assertAlmostEqual(made[-1][1][5], top, places=1)
        print('\nURB_PoliceStation grown:', {k: len(v) for k, v in grown.items()},
              [(f, round(b[2]), round(b[5])) for f, b in made])


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class TallerGrid(unittest.TestCase):
    """The blank map equipped and made 18 levels high, the tallest map's (prefab plan 5.6b): upward from its ground.
    Equipped with the runtime fill light too, which AmbientLight reads from the same map (equipped); it changes
    nothing here."""
    @classmethod
    def setUpClass(cls):
        cls.report, cls.p = equipped(levels=18, ambient=True)

    def test_every_part_says_the_new_height(self):
        import struct
        import world_grid
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (36, 36, 18))
        self.assertAlmostEqual(grid['oz'], 0, places=2)
        volume = shell.actors(self.p, 'XComLevelVolume')[0]
        world = self.p.own(volume, 'WorldData')
        self.assertEqual([self.p.own(world, k) for k in ('NumX', 'NumY', 'NumZ', 'NumTiles')], [36, 36, 18, 36 * 36 * 18])
        bounds = struct.unpack('<6f', self.p.own(world, 'WorldBounds')[:24])
        self.assertEqual([round(v, 2) for v in bounds], [-2113.0, -1345.0, -1.0, 1345.0, 2113.0, 1153.0])
        _, blob = world_grid.container_of(self.p)
        self.assertEqual(world_grid.decode(blob)['dims'], (36, 36, 18))
        self.assertEqual(self.report['resized']['grid'], [36, 36, 18])

    def test_six_cursor_storeys_reach_the_top(self):
        live = shell.listed(self.p)
        floors = sorted((self.p.effective(i, 'm_iFloorNumber'), scene_metadata.volume_bounds(self.p, i))
                        for i in shell.actors(self.p, 'XComCursorVolume') if i in live)
        self.assertEqual([f for f, _ in floors], [1, 2, 3, 4, 5, 6])
        self.assertEqual([(round(b['min'][2]), round(b['max'][2])) for _, b in floors],
                         [(192 * n, 192 * (n + 1)) for n in range(6)])
        self.assertTrue(all(b['min'][0] <= -2112 + 0.01 and b['max'][0] >= 1344 - 0.01 for _, b in floors))


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class TallestGrid(unittest.TestCase):
    """The blank map made 30 levels high, the editor's limit since 14 November 2026 (the game's own maps go to 18):
    every part says the height, and ten cursor storeys reach its top. Not played in the game."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BLANK, cls.tmp.name, levels=30)
        cls.p = Package(Path(cls.tmp.name) / Path(BLANK).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_part_says_the_new_height(self):
        import struct
        import world_grid
        grid = native_copy.level_grid(self.p)
        self.assertEqual((grid['nx'], grid['ny'], grid['nz']), (36, 36, 30))
        volume = shell.actors(self.p, 'XComLevelVolume')[0]
        world = self.p.own(volume, 'WorldData')
        self.assertEqual([self.p.own(world, k) for k in ('NumX', 'NumY', 'NumZ', 'NumTiles')], [36, 36, 30, 36 * 36 * 30])
        bounds = struct.unpack('<6f', self.p.own(world, 'WorldBounds')[:24])
        self.assertEqual([round(v, 2) for v in bounds], [-2113.0, -1345.0, -1.0, 1345.0, 2113.0, 1921.0])
        _, blob = world_grid.container_of(self.p)
        self.assertEqual(world_grid.decode(blob)['dims'], (36, 36, 30))
        self.assertEqual(self.report['resized']['grid'], [36, 36, 30])
        box = scene_metadata.volume_bounds(self.p, volume)
        self.assertGreaterEqual(box['max'][2], 1920 - 0.01)

    def test_ten_cursor_storeys_reach_the_top(self):
        live = shell.listed(self.p)
        floors = sorted((self.p.effective(i, 'm_iFloorNumber'), scene_metadata.volume_bounds(self.p, i))
                        for i in shell.actors(self.p, 'XComCursorVolume') if i in live)
        self.assertEqual([f for f, _ in floors], list(range(1, 11)))
        self.assertEqual([(round(b['min'][2]), round(b['max'][2])) for _, b in floors],
                         [(192 * n, 192 * (n + 1)) for n in range(10)])


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class GridLines(unittest.TestCase):
    """The blank map made 40 by 46 tiles and 18 levels, its ground drawn as a grid (--grid-lines; prefab plan 5.11): the
    ground planes hidden, collision kept, and a white line along every tile edge."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BLANK, cls.tmp.name, grid=(40, 46), levels=18, lines=True)
        cls.p = Package(Path(cls.tmp.name) / Path(BLANK).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def planes(self):
        return [i for i in shell.actors(self.p, 'XComLevelActor') if 'CFloor_864' in self.p.name(self.p.effective(self.p.own(i, 'StaticMeshComponent', 0), 'StaticMesh') or 0)]

    def test_every_ground_plane_is_hidden_and_keeps_its_collision(self):
        live = shell.listed(self.p)
        planes = [i for i in self.planes() if i in live]
        self.assertGreater(len(planes), 16)         # the map's own and the ones laid for the larger grid
        self.assertEqual(self.report['gridLines']['hiddenPlanes'], len(planes))
        for i in planes:
            self.assertIs(self.p.own(i, 'bHidden'), True, self.p.name(i))
            self.assertNotEqual(self.p.own(i, 'bCollideActors'), False)

    def test_a_line_along_every_tile_edge_ending_at_the_grid(self):
        live = shell.listed(self.p)
        line = shell.LEVEL + '.' + self.report['brought']['line'][0]
        mesh = self.p.effective(self.p.own(self.p.by_name[line], 'StaticMeshComponent', 0), 'StaticMesh')
        copies = [i for i in shell.actors(self.p, 'XComLevelActor') if i in live and self.p.name(i) != line
                  and self.p.effective(self.p.own(i, 'StaticMeshComponent', 0), 'StaticMesh') == mesh]
        # 47 rows along x of 3 copies (3,840: 1,536, 1,536, 768) and 41 along y of 3 (4,416: 1,536, 1,536, 1,344)
        self.assertEqual(len(copies), 47 * 3 + 41 * 3)
        self.assertEqual(self.report['gridLines']['lines'], len(copies))
        ends = {}
        for i in copies:
            loc, rot = self.p.own(i, 'Location'), self.p.own(i, 'Rotation', [0, 0, 0])
            scale = (self.p.own(i, 'DrawScale3D') or [1.0, 1.0, 1.0])[0]
            along = 1 if rot[1] else 0
            self.assertAlmostEqual(loc[2], 1.0, places=2)
            self.assertAlmostEqual((loc[1 - along] - (-2112, -1344)[1 - along]) % 96, 0, places=2)
            ends.setdefault((along, round(loc[1 - along])), []).append((loc[along] - 768 * scale, loc[along] + 768 * scale))
        for (along, _), spans in ends.items():
            spans.sort()
            self.assertAlmostEqual(spans[0][0], (-2112, -1344)[along], places=1)
            self.assertAlmostEqual(spans[-1][1], (-2112 + 96 * 40, -1344 + 96 * 46)[along], places=1)
            self.assertTrue(all(abs(a[1] - b[0]) < 0.1 for a, b in zip(spans, spans[1:])))


class HiddenGround(unittest.TestCase):
    """--hide-ground: the planes hidden as with --grid-lines, and no line brought or laid."""
    def test_planes_hidden_and_no_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = shell.equip(BLANK, tmp, grid=(40, 46), levels=18, hide=True)
            p = Package(Path(tmp) / Path(BLANK).name)
            live = shell.listed(p)
            planes = [i for i in shell.actors(p, 'XComLevelActor') if i in live and 'CFloor_864' in
                      p.name(p.effective(p.own(i, 'StaticMeshComponent', 0), 'StaticMesh') or 0)]
            self.assertEqual(report['hiddenGround']['planes'], len(planes))
            self.assertTrue(all(p.own(i, 'bHidden') is True for i in planes))
            self.assertNotIn('gridLines', report)
            self.assertNotIn('line', report['brought'])
            self.assertFalse(any('RoadPaint' in p.name(p.effective(p.own(i, 'StaticMeshComponent', 0), 'StaticMesh') or 0)
                                 for i in shell.actors(p, 'XComLevelActor')))


@unittest.skipUnless(BLANK and BLANK.exists() and BAR and BAR.exists(), NO_BLANK)
class AmbientLight(unittest.TestCase):
    """The runtime fill light (--ambient), read from TallerGrid's map, equipped with it (equipped)."""
    def test_runtime_fill_is_listed_and_reaches_static_and_dynamic_meshes(self):
        report, p = equipped(levels=18, ambient=True)
        actor = p.by_name[report['ambientLight']['actor']]
        self.assertIn(actor, shell.listed(p))
        self.assertEqual(p.cls(actor), 'SkyLight')
        component = p.own(actor, 'LightComponent')
        self.assertEqual(p.cls(component), 'SkyLightComponent')
        self.assertIs(p.own(component, 'UseDirectLightMap'), False)
        self.assertIs(p.own(component, 'CastShadows'), False)
        self.assertAlmostEqual(p.own(component, 'Brightness'), shell.AMBIENT_UPPER)
        self.assertAlmostEqual(p.own(component, 'LowerBrightness'), shell.AMBIENT_LOWER)
        self.assertEqual(p.own(component, 'LightAffectsClassification'), 'LAC_DYNAMIC_AND_STATIC_AFFECTING')
        raw = p.own(component, 'LightingChannels')
        channels = {name: raw[at] for name, kind, _, at, _ in native_copy.Walker(p).walk(raw, 0, len(raw))
                    if kind == 'BoolProperty'}
        self.assertEqual(channels, {f'{name}[0]': 1 for name in
                                   ('bInitialized', 'BSP', 'Static', 'Dynamic', 'CompositeDynamic')})
        sun = p.by_name[report['ambientLight']['directional']]
        self.assertIn(sun, shell.listed(p))
        self.assertIs(p.own(sun, 'bMovable'), True)
        self.assertIs(p.own(sun, 'bStatic'), False)
        component = p.own(sun, 'LightComponent')
        self.assertIs(p.own(component, 'bForceDynamicLight'), True)
        self.assertIs(p.own(component, 'UseDirectLightMap'), False)
        self.assertAlmostEqual(p.own(component, 'Brightness'), shell.STAGE_SUN_BRIGHTNESS)


if __name__ == '__main__':
    unittest.main()
