"""The compiler and fracturing walls made from numbers (custom geometry plan, section 0): an added copy of a
fracturing piece carries its `generated` request to the Build's writer (tools/bake/frac_walls.py), stands in the
made wall's box, and a malformed request, or one on any other piece, leaves the record out."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
from compiler import compile_project  # noqa: E402
from test_compiler import add, codes, document, noted, refused, scene  # noqa: E402

WALL = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[dict(x0=96, x1=192, z0=0, z1=60)], seed=2))
RELIT = dict(kind='relit', version=1)


def made(generated, name='XComFracLevelActor_11', serial=1, at=(0, 600, 0)):
    return dict(add(name, serial, at), generated=generated)


def compiled(added):
    spec, report = compile_project(document((), added, schemaVersion=2), scene())
    return spec, report


class GeneratedTests(unittest.TestCase):
    def test_a_fracturing_copy_carries_its_wall_to_the_builds_writer(self):
        spec, report = compiled([made(WALL), made(RELIT, serial=2, at=(0, 1200, 0)),
                                 add('XComFracLevelActor_7', 3, (0, 1800, 0))])
        self.assertTrue(report['ok'], refused(report))
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        self.assertEqual(op['generated'], [WALL, RELIT, None])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual([c.get('generated') for c in native['copies']], [WALL, RELIT, None])
        self.assertNotIn('generated', [k for o in compiler.native_split(spec)[0]['objects'] for k in o])
        # a made wall is noted (a blast doesn't spread to or from it); the relit reference is the template's own
        self.assertEqual(noted(report, 'generated'), ['generated-wall'])

    def test_a_made_wall_stands_in_its_own_box(self):
        spec, report = compiled([made(WALL), made(RELIT, serial=2, at=(0, 1200, 0))])
        self.assertTrue(report['ok'], refused(report))
        _, native = compiler.native_split(spec)
        wall, relit = (c['box'] for c in native['copies'])
        # the template's mesh is 96 square and 100 tall about its pivot: the wall keeps its y and z, its x is its own
        # solid, 8 in from its tile edges at each end
        self.assertEqual(wall, [8.0, 376.0, 552.0, 648.0, 0.0, 100.0])
        self.assertEqual(relit, [-48.0, 48.0, 1152.0, 1248.0, 0.0, 100.0])

    def test_none_without_a_request(self):
        spec, _ = compiled([add('XComFracLevelActor_11', 1, (0, 600, 0))])
        self.assertNotIn('generated', spec['objects'][0])

    def test_a_malformed_request_leaves_the_record_out(self):
        bad = [dict(kind='wall', version=1), dict(RELIT, version=2), 'fracWall',
               dict(WALL, wall=dict(x0=0, x1=12)), dict(WALL, wall=dict(x0=0, x1=39)),
               dict(WALL, wall=dict(x0=0, x1=96, openings=[dict(x0=80, x1=120, z0=0, z1=10)])),
               dict(WALL, wall=dict(x0=0, x1=96, seed='one')),
               dict(WALL, wall=dict(x0=0, x1=float('nan')))]
        for g in bad:
            spec, report = compiled([made(g)])
            self.assertIn('malformed', codes(report), g)
            self.assertFalse([o for o in (spec or {}).get('objects', []) if o['type'] == 'copy'], g)

    def test_only_a_fracturing_piece_is_made_from_numbers(self):
        spec, report = compiled([dict(add('XComLevelActor_1', 1, (0, 600, 0)), generated=WALL)])
        self.assertIn('malformed', codes(report))
        self.assertIn('only a fracturing piece', ' '.join(d['message'] for d in refused(report)))


if __name__ == '__main__':
    unittest.main()
