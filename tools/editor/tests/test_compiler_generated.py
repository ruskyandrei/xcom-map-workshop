"""The compiler and fracturing walls made from numbers (custom geometry plan, section 0): an added copy of a
fracturing piece carries its `generated` request to the Build's writer (tools/bake/frac_walls.py), stands in the
made wall's box, and a malformed request, or one on any other piece, leaves the record out. What its openings do in
the game that may surprise is warned of (M1 item 4): a doorway with no door, one no tile's walking line passes
through, a window walked through, giving no cover, or not seen through."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
from compiler import compile_project  # noqa: E402
from test_compiler import add, codes, document, noted, refused, scene, warned  # noqa: E402

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

    def test_a_made_walls_height_is_free(self):
        # 14.5 over the template's floor (16 tiles from it): off its storeys, which a made wall keeps to no more (its columns are its
        # own); off its tiles still warns
        _, report = compiled([made(WALL, at=(0, 636, 14.5))])
        self.assertNotIn('off-grid', warned(report))
        _, report = compiled([made(WALL, at=(10, 636, 14.5))])
        self.assertIn('off-grid', warned(report))

    def test_none_without_a_request(self):
        spec, _ = compiled([add('XComFracLevelActor_11', 1, (0, 600, 0))])
        self.assertNotIn('generated', spec['objects'][0])

    def test_a_malformed_request_leaves_the_record_out(self):
        bad = [dict(kind='wall', version=1), dict(RELIT, version=2), 'fracWall',
               dict(WALL, wall=dict(x0=0, x1=12)), dict(WALL, wall=dict(x0=0, x1=39)),
               dict(WALL, wall=dict(x0=0, x1=96, openings=[dict(x0=80, x1=120, z0=0, z1=10)])),
               dict(WALL, wall=dict(x0=0, x1=96, seed='one')),
               dict(WALL, wall=dict(x0=0, x1=96, storeys=3)), dict(WALL, wall=dict(x0=0, x1=96, storeys=True)),
               dict(WALL, wall=dict(x0=0, x1=float('nan')))]
        for g in bad:
            spec, report = compiled([made(g)])
            self.assertIn('malformed', codes(report), g)
            self.assertFalse([o for o in (spec or {}).get('objects', []) if o['type'] == 'copy'], g)

    def test_a_one_storey_wall_is_a_wall(self):
        # (M2) storeys 1 or 2 (left out, 2) go to the Build as they are
        for storeys in (1, 2):
            g = dict(WALL, wall=dict(WALL['wall'], storeys=storeys))
            spec, report = compiled([made(g, at=(0, 636, 14.5))])
            self.assertNotIn('malformed', codes(report))
            (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
            self.assertEqual(op['generated'][0]['wall']['storeys'], storeys)

    def test_a_made_wall_breaks_with_its_groups_props(self):
        # (M3 item 4) a group that breaks together with a made wall and one prop: the wall gets the group's number
        # (wallGroups: its columns list the prop), the prop its breakGroup, and both are made in the map
        PL = 'TheWorld.PersistentLevel.'
        group = dict(id='g', breakTogether=True, members=[{'added': PL + 'XComFracLevelActor_11_copy1'},
                                                          {'added': PL + 'XComDestructibleActor_4_copy2'}])
        doc = document((), [made(WALL, at=(0, 636, 14.5)), add('XComDestructibleActor_4', 2, (144, 660, 14.5))],
                       schemaVersion=2, groups=[group])
        spec, report = compiler.compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('group-unbreakable', noted(report))
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        by = dict(zip(op['labels'], zip(op['wallGroups'], op['breakGroups'])))
        self.assertEqual(by, {'XComFracLevelActor_11_copy1': (1, 0), 'XComDestructibleActor_4_copy2': (0, 1)})
        self.assertEqual(report['groups'][0]['walls'], ['XComFracLevelActor_11_copy1'])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(sorted((c['label'], c.get('wallGroup', 0), c.get('breakGroup', 0)) for c in native['copies']),
                         [('XComDestructibleActor_4_copy2', 0, 1), ('XComFracLevelActor_11_copy1', 1, 0)])
        # a made wall with scenery only breaks with nothing
        lone = dict(group, members=[group['members'][0], {'added': PL + 'XComLevelActor_1_copy2'}])
        spec, report = compiler.compile_project(document((), [made(WALL, at=(0, 636, 14.5)), add('XComLevelActor_1', 2, (0, 900, 0))],
                                                         schemaVersion=2, groups=[lone]), scene())
        self.assertIn('group-unbreakable', noted(report))
        self.assertNotIn('wallGroups', [o for o in spec['objects'] if o['type'] == 'copy'][0])

    def test_only_a_fracturing_piece_is_made_from_numbers(self):
        spec, report = compiled([dict(add('XComLevelActor_1', 1, (0, 600, 0)), generated=WALL)])
        self.assertIn('malformed', codes(report))
        self.assertIn('only a fracturing piece', ' '.join(d['message'] for d in refused(report)))


def wall(*openings, x1=384.0):
    return dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=x1, openings=list(openings), seed=2))


DOORWAY = dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)
WINDOW = dict(x0=192.0, x1=288.0, z0=72.0, z1=168.0)


class OpeningTests(unittest.TestCase):
    def warned(self, generated, *more):
        _, report = compiled([made(generated)] + list(more))
        self.assertTrue(report['ok'], refused(report))
        return sorted(w['code'] for w in report['warnings'] if w['code'].startswith('wall-'))

    def test_what_the_game_does_at_an_opening(self):
        w = wall()['wall']
        self.assertEqual(compiler.opening_play(w, DOORWAY), dict(tiles=1, walk=True, climb=False, sight=True, cover='none'))
        self.assertEqual(compiler.opening_play(w, WINDOW), dict(tiles=1, walk=False, climb=True, sight=True, cover='low'))
        self.assertEqual(compiler.opening_play(w, dict(WINDOW, z0=112.0, z1=200.0)),
                         dict(tiles=1, walk=False, climb=False, sight=False, cover='high'))
        self.assertEqual(compiler.opening_play(w, dict(DOORWAY, x0=56.0, x1=136.0))['tiles'], 0)

    def test_the_page_knows_the_same_sweeps(self):
        import re
        text = (HERE.parents[1] / 'viewer' / 'web' / 'walls.js').read_text(encoding='utf-8')
        m = re.search(r'export const SWEEP = \{ cover: \[(\d+), (\d+)\], high: \[(\d+), (\d+)\], walk: (\d+), '
                      r'sight: (\d+), half: ([\d.]+) \}', text)
        s = compiler.WALL_SWEEPS
        self.assertEqual([float(v) for v in m.groups()], [*s['cover'], *s['high'], s['walk'], s['sight'], s['half']])

    def test_a_doorway_with_no_door_and_a_window_as_the_games(self):
        self.assertEqual(self.warned(wall(DOORWAY, WINDOW)), ['wall-doorway-no-door'])

    def test_a_door_in_the_doorway_takes_the_warning_away(self):
        # the scene's door (a 96 wide, 100 tall leaf about its pivot) copied into the doorway: the wall stands at y 600
        door = add('XComInteractiveLevelActor_8', 2, (144, 600, 0))
        self.assertEqual(self.warned(wall(DOORWAY), door), [])

    def test_openings_that_change_play(self):
        self.assertEqual(self.warned(wall(dict(DOORWAY, x0=56.0, x1=136.0))), ['wall-opening-between-tiles'])
        self.assertEqual(self.warned(wall(dict(DOORWAY, z1=40.0))), ['wall-doorway-low'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=40.0))), ['wall-window-walked'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=48.0, z1=60.5))), ['wall-window-blind'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=112.0, z1=200.0))), ['wall-window-blind'])


if __name__ == '__main__':
    unittest.main()
