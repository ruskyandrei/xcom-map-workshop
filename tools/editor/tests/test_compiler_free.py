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
from editor_fixtures import codes, compiled, made, refused, warned  # noqa: E402

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

    def test_a_free_ramp_s_slope_is_its_rise_over_its_run(self):
        ramp = dict(shape='ramp', free=1, x0=0.0, x1=96.0, y0=0.0, y1=96.0, z0=0.0, z1=192.0)
        self.assertAlmostEqual(compiler.ground_slope(ramp), 63.43, places=2)
        self.assertEqual(compiler.ground_box(ramp), (0.0, 96.0, 0.0, 96.0, 0.0, 192.0))


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
