"""The compiler and made pieces in the free form (the custom geometry improvements plan, stage 2, its section 10.2): a
free-form request is checked (made_edits.free_valid) and goes on to the Build as the Build's free version of its kind,
its numbers as they are, less `plain`, which is warned of as the older plain versions are; a free-form piece stands in
its own numbers' box; malformed numbers leave the record out."""
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


if __name__ == '__main__':
    unittest.main()
