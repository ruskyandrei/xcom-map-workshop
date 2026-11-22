"""The compiler and made pieces in the free form (the custom geometry improvements plan, stage 2, its section 10.2): a
free-form request is checked (made_edits.free_valid) and goes on to the Build as the Build's free version of its kind,
its numbers as they are, less `plain`, which is warned of as the older plain versions are; a free-form piece stands in
its own numbers' box; malformed numbers leave the record out."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
import made_edits  # noqa: E402
from editor_fixtures import codes, compiled, document, made, noted, refused, scene, warned  # noqa: E402

WALL = dict(kind='fracWall', version=5, wall=dict(free=1, x0=-20.5, x1=123.0, y0=-10.0, y1=10.0, z0=-16.0, z1=201.25,
                                                  tall='repeat', openings=[dict(x0=10.0, x1=60.5, z0=-16.0, z1=150.0)], seed=2))
SLAB = dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0.0, x1=150.5, y0=-10.0, y1=96.0, z0=-6.0, z1=2.0,
                                                  holes=[dict(x0=40.0, x1=70.0, y0=0.0, y1=30.0)], seed=4, look='floor'))
BLOCK = dict(kind='ground', version=5, ground=dict(free=1, shape='block', x0=0.0, x1=7000.0, y0=0.0, y1=96.0, z0=0.0, z1=500.0))


def native_made(spec):
    _, native = compiler.native_split(spec)
    return [c for c in native['copies'] if c.get('generated')]


class FreeFormTests(unittest.TestCase):
    def test_the_versions(self):
        self.assertEqual(made_edits.FREE_VERSION, {'fracWall': 5, 'fracSlab': 4, 'ground': 5})
        for kind, version in made_edits.FREE_VERSION.items():
            self.assertIn(version, made_edits.GENERATED_VERSIONS[kind])
        self.assertEqual(made_edits.BUILD_FREE_VERSION, {'fracWall': 4, 'fracSlab': 3, 'ground': 3})

    def test_a_free_form_piece_goes_to_the_build_as_its_free_version(self):
        spec, report = compiled([made(WALL), made(SLAB, serial=2, at=(0, 1212, 0)),
                                 made(BLOCK, name='XComLevelActor_1', serial=3, at=(0, 2400, 0))])
        self.assertTrue(report['ok'], refused(report))
        wall, slab, block = native_made(spec)
        self.assertEqual(wall['generated'], dict(WALL, version=4))
        self.assertEqual(slab['generated'], dict(SLAB, version=3))
        self.assertEqual(block['generated'], dict(BLOCK, version=3))
        # each stands in its own numbers: the wall's solid 8 in from its ends (its look's inset), its faces and heights
        # (made's place: 600 along y)
        self.assertEqual(wall['box'], [-12.5, 115.0, 590.0, 610.0, -16.0, 201.25])
        self.assertEqual(slab['box'], [0.0, 150.5, 1202.0, 1308.0, -6.0, 2.0])
        self.assertEqual(block['box'], [0.0, 7000.0, 2400.0, 2496.0, 0.0, 500.0])     # (no 64-tile, no 384 cap)

    def test_a_plain_free_form_piece_is_warned_and_built_in_its_default_look(self):
        wall = dict(WALL, wall=dict(WALL['wall'], plain=True))
        spec, report = compiled([made(wall)])
        self.assertTrue(report['ok'], refused(report))
        self.assertIn('made-no-look', warned(report))
        (copy,) = native_made(spec)
        self.assertNotIn('plain', copy['generated']['wall'])
        self.assertNotIn('look', copy['generated']['wall'])

    def test_malformed_free_numbers_leave_the_record_out(self):
        w = WALL['wall']
        for bad in (dict(w, free=0), dict(w, x1=w['x0']), dict(w, z0=300.0), dict(w, y1=float('nan')), dict(w, tall='tilt'),
                    dict(w, openings=[dict(x0=-50.0, x1=10.0, z0=0.0, z1=50.0)]), dict(w, storeys=2), dict(w, seed=1.5),
                    dict(w, look='marble'), dict(w, plain='yes'), dict(w, mapping=dict(surfaces=dict(faces=dict(mode='tile', u=1, v=1)))),
                    dict(w, mapping=dict(surfaces=dict(faces=dict(mode='size', u=0, v=64)))),
                    dict(w, mapping=dict(surfaces=dict(roof=dict(mode='size', u=64, v=64))))):
            _, report = compiled([made(dict(WALL, wall=bad))])
            self.assertIn('malformed', codes(report), bad)
        s = SLAB['slab']
        for bad in (dict(s, holes=[dict(x0=140.0, x1=160.0, y0=0.0, y1=10.0)]), dict(s, y0=96.0), dict(s, look=7)):
            _, report = compiled([made(dict(SLAB, slab=bad))])
            self.assertIn('malformed', codes(report), bad)
        _, report = compiled([made(dict(SLAB, slab=dict(s, holes=[dict(x0=0.0, x1=150.5, y0=-10.0, y1=96.0)])))])
        self.assertIn('slab-all-holes', codes(report))
        # (two holes leaving a strip 0.5 wide between them leave some of it; tile centres would say none)
        strip = dict(s, holes=[dict(x0=0.0, x1=75.0, y0=-10.0, y1=96.0), dict(x0=75.5, x1=150.5, y0=-10.0, y1=96.0)])
        self.assertTrue(made_edits.free_slab_left(strip))
        self.assertFalse(made_edits.free_slab_left(dict(strip, holes=strip['holes'] + [dict(x0=74.0, x1=76.0, y0=-10.0, y1=96.0)])))
        g = BLOCK['ground']
        for bad in (dict(g, shape='dome'), dict(g, height=64.0), dict(g, points=[[0, 0, 0]]),
                    dict(g, shape='rock', seed=-1)):
            _, report = compiled([made(dict(BLOCK, ground=bad), name='XComLevelActor_1')])
            self.assertIn('malformed', codes(report), bad)

    def test_a_mapping_of_the_stage_4_shape_is_carried(self):
        mapping = dict(surfaces=dict(faces=dict(mode='size', u=64.0, v=64.0, turn=30.0, flipU=True, offsetU=0.5, world=False)))
        wall = dict(WALL, wall=dict(WALL['wall'], mapping=mapping))
        spec, report = compiled([made(wall)])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(native_made(spec)[0]['generated']['wall']['mapping'], mapping)

    def test_a_world_aligned_surface_goes_with_its_origin(self):
        # (stage 4: the Build is told where the piece's frame stands on the surface's axes in the world, from the
        # record's pose; one the record carries is not taken, and a malformed one leaves the record out)
        mapping = dict(surfaces=dict(faces=dict(mode='size', u=64.0, v=64.0, world=True)))
        wall = dict(WALL, wall=dict(WALL['wall'], mapping=mapping, mappingOrigin=dict(faces=[1.0, 2.0])))
        spec, report = compiled([dict(made(wall, at=(300.0, 600.0, 16.0)), rotation=[0, 16384, 0])])
        self.assertTrue(report['ok'], refused(report))
        numbers = native_made(spec)[0]['generated']['wall']
        self.assertEqual(numbers['mappingOrigin'], dict(faces=[600.0, 16.0]))
        self.assertEqual(numbers['mapping'], mapping)
        # (three numbers are the Build's too, for any surface: a record carrying them is taken, and not used)
        three = dict(WALL, wall=dict(WALL['wall'], mapping=mapping, mappingOrigin=dict(faces=[1.0, 2.0, 3.0], sides=[0.0, 0.0, 0.0])))
        _, report = compiled([made(three)])
        self.assertTrue(report['ok'], refused(report))
        # a mapping in the piece's own frame: no origin
        local = dict(WALL, wall=dict(WALL['wall'], mapping=dict(surfaces=dict(faces=dict(mode='size', u=64.0, v=64.0)))))
        spec, report = compiled([made(local)])
        self.assertNotIn('mappingOrigin', native_made(spec)[0]['generated']['wall'])
        for bad in (dict(faces=[1.0]), dict(roof=[1.0, 2.0]), dict(faces=[1.0, float('inf')]), [1.0, 2.0], dict(sides=[1.0, 2.0])):
            _, report = compiled([made(dict(WALL, wall=dict(WALL['wall'], mappingOrigin=bad)))])
            self.assertIn('malformed', codes(report), bad)

    def test_the_texture_origins_the_page_works_out_too(self):
        # (mapping_origin_cases.json, shared_cases_test.mjs: made_mapping.js mappingOrigin is the twin)
        cases = json.loads(Path(__file__).with_name('mapping_origin_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(cases), 10)
        for c in cases:
            self.assertEqual(made_edits.mapping_origin(c['kind'], c.get('mapping'), c['location'], c['rotation']), c['origin'],
                             c['case'])

    def test_a_free_ramp_s_slope_is_its_rise_over_its_run(self):
        ramp = dict(shape='ramp', free=1, x0=0.0, x1=96.0, y0=0.0, y1=96.0, z0=0.0, z1=192.0)
        self.assertAlmostEqual(compiler.ground_slope(ramp), 63.43, places=2)
        self.assertEqual(compiler.ground_box(ramp), (0.0, 96.0, 0.0, 96.0, 0.0, 192.0))


class TiltedTests(unittest.TestCase):
    def test_a_tilted_floor_builds_with_a_warning_and_a_turned_one_with_a_note(self):
        # (decision D6) pitched: built as drawn, warned; turned about the vertical off the quarter turns: its cursor
        # floors in steps square to the world (EXP-90 check 5), a note; on a quarter turn: nothing said
        tilted = dict(made(SLAB), rotation=[2048, 0, 0])
        turned = dict(made(SLAB, serial=2, at=(0, 1800, 0)), rotation=[0, 3000, 0])
        square = dict(made(SLAB, serial=3, at=(0, 3000, 0)), rotation=[0, 16384, 0])
        ramp = dict(made(BLOCK, name='XComLevelActor_1', serial=4, at=(0, 4200, 0)), rotation=[0, 0, 12000])
        spec, report = compiled([tilted, turned, square, ramp])
        self.assertTrue(report['ok'], refused(report))
        got = [w['code'] for w in report['warnings'] if w['code'] in ('made-tilted', 'slab-turned')]
        self.assertEqual(sorted(got), ['made-tilted', 'made-tilted'])
        (note,) = [n['message'] for n in report['notes'] if n['code'] == 'slab-turned']
        self.assertIn('XComFracLevelActor_11_copy2', note)
        self.assertIn('boxes square to the world, one round its part of each tile it reaches', note)
        (ground_warning,) = [w['message'] for w in report['warnings'] if w['code'] == 'made-tilted' and 'cursor' not in w['message']]
        self.assertIn('no cover', ground_warning)
        self.assertEqual(len(native_made(spec)), 4)
        # (a free-form piece is drawn to stand anywhere: its template's pose rule is not warned of)
        self.assertNotIn('off-grid', warned(report))


# EXP-90's floors (tools/editor/examples/exp90_projects.py): B off the tile lines, E turned 20 degrees
FLOOR_B = dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0.0, x1=230.5, y0=0.0, y1=170.25, z0=192.0, z1=194.0,
                                                     holes=[dict(x0=40.25, x1=80.25, y0=118.5, y1=158.5)], seed=902, look='floor'))
FLOOR_E = dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0.0, x1=288.0, y0=0.0, y1=192.0, z0=192.0, z1=194.0,
                                                     holes=[], seed=909, look='floor'))


class SlabTilesTests(unittest.TestCase):
    """A made floor against the game's tiles (F-147; EXP-90 checks 2 and 5; made_cursors.tiles and steps): the tiles
    at its edge it covers in part short of their centres are no floor, a note; a turned floor's cursor floors stand in
    steps, as the Build's made_cursors.build_slabs makes them."""

    def test_a_floor_off_the_tile_lines_notes_the_tiles_it_covers_in_part(self):
        _, report = compiled([made(FLOOR_B, at=(-1840.25, -1103.5, 0.0))])
        self.assertTrue(report['ok'], refused(report))
        (n,) = [d for d in report['notes'] if d['code'] == 'slab-edge-tiles']
        self.assertIn('covers 10 tiles at its edge in part, short of their centre', n['message'])
        self.assertIn('so they are no floor at its height (it is floor on 2 tiles)', n['message'])
        self.assertIn([11, 10, 3], n['tiles'])      # (-1681, -913), 29% under it: a soldier sent there went down
        self.assertIn([12, 9, 3], n['tiles'])       # (-1585, -1009), 24%
        self.assertEqual(n.get('record'), 'added[0]')
        self.assertNotIn('slab-edge-tiles', warned(report))

    def test_a_floor_on_whole_tiles_notes_nothing(self):
        whole = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=192.0, y0=0.0, y1=192.0, seed=1, holes=[], look='floor'))
        _, report = compiled([made(whole, at=(-1824.0, -1440.0, 0.0))])
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('slab-edge-tiles', noted(report))

    def test_a_turned_floor_s_cursor_floors_stand_in_steps(self):
        import made_cursors
        doc = document((), [dict(made(FLOOR_E, at=(-400.5, -1440.25, 0.0)), rotation=[0, 3641, 0])], schemaVersion=2)
        c = compiler.Compiler(doc, scene())
        _, report = c.run()
        self.assertTrue(report['ok'], refused(report))
        boxes = c.made_edits.made_slab_boxes()
        self.assertEqual(len(boxes), 12)
        (n,) = [d['message'] for d in report['notes'] if d['code'] == 'slab-turned']
        self.assertIn('in 12 boxes square to the world', n)
        # the Build's: its record's box and its copy as the native edit has it, on the same grid
        (copy,) = [x for x in c.copies if x.get('generated')]
        b = copy['box']
        corner = compiler.tile_corner(scene()['tileGrid'])
        from unittest import mock
        import native_copy
        with mock.patch.object(native_copy, 'level_grid', return_value=dict(tx=corner[0], ty=corner[1])):
            built = made_cursors.build_slabs(None, [dict(kind='fracSlab', label=copy['label'], box=b)], [copy])
        self.assertEqual(built, boxes)
        # its tiles: floor on five, seven in part (the cursor's reading at (-433, -1393), 34% under it, among them)
        (n,) = [d for d in report['notes'] if d['code'] == 'slab-edge-tiles']
        self.assertIn('covers 7 tiles at its edge in part', n['message'])
        self.assertIn([24, 5, 3], n['tiles'])


# EXP-90's wall A (exp90_projects.py): along x, its line 6.5 off the game's tile row centre line (7.5 off the grid's
# origin's), a window 64 to 136 along it and a doorway 156 to 268
WALL_A = dict(kind='fracWall', version=5, wall=dict(free=1, x0=0.0, x1=287.5, y0=-8.0, y1=8.0, z0=-16.0, z1=384.0,
                                                    tall='repeat', seed=901, openings=[
                                                        dict(x0=64.0, x1=136.0, z0=72.0, z1=168.0),
                                                        dict(x0=156.0, x1=268.0, z0=-16.0, z1=160.0)]))


class InRowTests(unittest.TestCase):
    """A free-form wall standing over the tiles' middles takes those tiles (F-146, EXP-90 check 1; made_edits.row_tiles
    and opening_play): its window's tile is taken and nobody climbs through it, its doorway's is walked; a note says it
    takes the tiles. A wall on the tile edges reads as before."""

    def test_the_cases_the_page_passes_too(self):
        # (opening_play_cases.json, shared_cases_test.mjs: walls.js gridCrossings, rowTiles and openingPlay)
        cases = json.loads(Path(__file__).with_name('opening_play_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(cases), 9)
        for c in cases:
            w = c['wall']
            crossings = made_edits.grid_crossings(c['location'], c['rotation'], w, c['origin'])
            taken = made_edits.row_tiles(c['location'], c['rotation'], w, c['origin'])
            self.assertEqual([crossings, taken], [c['crossings'], c['taken']], c['case'])
            self.assertEqual([made_edits.opening_play(w, o, crossings, taken) for o in w['openings']], c['plays'], c['case'])

    def test_wall_a_as_exp90_played_it(self):
        w = WALL_A['wall']
        loc, rot, origin = [-1889.75, -1111.5, 0.0], [0, 0, 0], [-2784.0, -1920.0]
        crossings = made_edits.grid_crossings(loc, rot, w, origin)
        taken = made_edits.row_tiles(loc, rot, w, origin)
        self.assertEqual(taken, crossings)          # it stands over its row's three tiles
        window, door = (made_edits.opening_play(w, o, crossings, taken) for o in w['openings'])
        # the window's tile could not be stood on, nobody was seen to vault; low cover beside it (30); the doorway
        # walked through, no cover (0)
        self.assertEqual(window, dict(tiles=1, walk=False, climb=False, sight=True, cover='low', inside=True))
        self.assertEqual(door, dict(tiles=1, walk=True, climb=False, sight=True, cover='none', inside=True))
        # on the tile edge the same wall reads as an edge wall: its window climbed through
        edge = [loc[0], -1152.0, 0.0]
        self.assertEqual(made_edits.row_tiles(edge, rot, w, origin), [])
        self.assertTrue(made_edits.opening_play(w, w['openings'][0], made_edits.grid_crossings(edge, rot, w, origin), [])['climb'])

    def test_the_compiler_notes_the_tiles_it_takes(self):
        _, report = compiled([made(WALL_A, at=(-1889.75, -1111.5, 0.0))])
        self.assertTrue(report['ok'], refused(report))
        (n,) = [d for d in report['notes'] if d['code'] == 'wall-in-row']
        self.assertIn('stands over the middle of 3 tiles, not on the tile edges: it takes 2 of them (no one stands there, '
                      'its gaps that leave room to stand excepted), and gives cover to the tiles either side', n['message'])
        self.assertEqual(warned(report, 'wall-'), ['wall-doorway-no-door'])
        self.assertNotIn('wall-in-row', warned(report))
        # on the tile edge: no note
        _, report = compiled([made(WALL_A, at=(-1889.75, -1152.0, 0.0))])
        self.assertNotIn('wall-in-row', noted(report))
        self.assertEqual(warned(report, 'wall-'), ['wall-doorway-no-door'])

    def test_a_doorway_that_leaves_no_room_in_its_tile_is_warned_so(self):
        narrow = dict(WALL_A, wall=dict(WALL_A['wall'], openings=[dict(x0=99.0, x1=129.0, z0=-16.0, z1=160.0)]))
        _, report = compiled([made(narrow, at=(-1889.75, -1111.5, 0.0))])
        (w,) = [d['message'] for d in report['warnings'] if d['code'] == 'wall-doorway-low']
        self.assertIn("units can't stand in its tile or walk through it: the wall stands over the tile's middle", w)
        (n,) = [d['message'] for d in report['notes'] if d['code'] == 'wall-in-row']
        self.assertIn('it takes them (no one stands there)', n)


class FreeJoinTests(unittest.TestCase):
    def test_the_cases_the_page_passes_too(self):
        # (free_join_cases.json, shared_cases_test.mjs: walls.js freeWallJoins is the twin)
        cases = json.loads(Path(__file__).with_name('free_join_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(cases), 15)
        for c in cases:
            found = made_edits.free_wall_joins([
                dict(key=w['key'], location=w['at'], rotation=[0, w['yaw'], 0],
                     wall=dict(free=1, x0=w['x0'], x1=w['x1'], y0=w['y'][0], y1=w['y'][1], z0=w['z'][0], z1=w['z'][1]))
                for w in c['walls']])
            self.assertEqual({k: v['ends'] for k, v in found.items()}, c['ends'], c['case'])
            self.assertEqual({k: [j['how'] for j in v['joins']] for k, v in found.items()}, c['joins'], c['case'])

    def test_a_mitre_by_hand(self):
        # a right angle: each end's plane leans one unit along per unit across, through the corner; 60 degrees: cot 30
        free = lambda key, at, yaw: dict(key=key, location=at, rotation=[0, yaw, 0],  # noqa: E731
                                         wall=dict(free=1, x0=0.0, x1=384.0, y0=-8.0, y1=8.0, z0=-16.0, z1=384.0))
        found = made_edits.free_wall_joins([free('a', [0, 0, 0], 0), free('b', [384, 0, 0], 16384)])
        self.assertEqual(found['a']['ends'][1], dict(inset=0.0, lean=-1.0))
        found = made_edits.free_wall_joins([free('a', [0, 0, 0], 0), free('b', [384, 0, 0], round(65536 / 3))])
        self.assertAlmostEqual(abs(found['a']['ends'][1]['lean']), 3 ** 0.5, places=3)

    def test_a_free_wall_meeting_an_older_one_keeps_today_s_rule(self):
        old = dict(key='old', location=[0, 0, 0], rotation=[0, 0, 0], wall=dict(x0=0.0, x1=480.0, openings=[], seed=1))
        new = dict(key='new', location=[480, 0, 0], rotation=[0, 16384, 0],
                   wall=dict(free=1, x0=0.0, x1=384.0, y0=-8.0, y1=8.0, z0=-16.0, z1=384.0))
        found = made_edits.made_wall_joins([old, new])
        self.assertEqual(found['old']['ends'], ['free', 'through'])
        self.assertEqual(found['new']['ends'], ['free', 'free'])
        self.assertEqual([j['how'] for j in found['new']['joins']], ['butt'])

    def test_mitred_walls_go_to_the_build_with_their_ends(self):
        a = dict(WALL, wall=dict(WALL['wall'], x0=0.0, x1=384.0, openings=[]))
        b = dict(a)
        spec, report = compiled([made(a, at=(0, 600, 0)), dict(made(b, serial=2, at=(384, 600, 0)), rotation=[0, 16384, 0])])
        self.assertTrue(report['ok'], refused(report))
        walls = native_made(spec)
        self.assertEqual(walls[0]['generated']['wall']['ends'], ['free', dict(inset=0.0, lean=-1.0)])
        self.assertEqual(walls[1]['generated']['wall']['ends'], [dict(inset=0.0, lean=1.0), 'free'])
        self.assertEqual(walls[0]['generated']['version'], 4)


if __name__ == '__main__':
    unittest.main()
