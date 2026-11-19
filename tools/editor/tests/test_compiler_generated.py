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
from test_compiler import PL, add, codes, document, noted, refused, scene, target, warned  # noqa: E402

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
        # a made wall is noted (it breaks in parts, passing breaks on); the relit reference is the template's own
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

    def test_made_walls_that_meet_carry_their_end_styles(self):
        # (M3 item 2) an L: A along x from (0, 600) to (384, 600), B a quarter turn from A's far end; A (along x, as
        # long and tall) runs through, B butts. Their requests become version 2 with `ends`; A's box reaches 8 past
        # its tile edge
        plain = dict(WALL, wall=dict(WALL['wall'], openings=[]))
        spec, report = compiled([made(plain, serial=1, at=(0, 600, 0)),
                                 dict(made(plain, serial=2, at=(384, 600, 0)), rotation=[0, 16384, 0]),
                                 made(plain, serial=3, at=(0, 2400, 0))])
        self.assertTrue(report['ok'], refused(report))
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        a, b, c = op['generated']
        self.assertEqual((a['version'], a['wall']['ends']), (2, ['free', 'through']))
        self.assertEqual(b, plain)          # butting: a free end's shape, its request unchanged
        self.assertEqual(c, plain)          # alone
        _, native = compiler.native_split(spec)
        self.assertEqual(native['copies'][0]['box'][:2], [8.0, 392.0])

    def test_a_wall_names_its_look_and_leaves_its_ends_to_the_build(self):
        # (M4 item 1) version 2 names a look of wall_looks.json; a project's wall carries no end styles (the Build's)
        self.assertEqual(compiler.FRAC_WALL_LOOKS[0], 'bar-inside')
        named = dict(WALL, version=2, wall=dict(WALL['wall'], look='bar-inside'))
        spec, report = compiled([made(named)])
        self.assertTrue(report['ok'], refused(report))
        for bad in (dict(WALL, wall=dict(WALL['wall'], look='bar-inside')),          # a look needs version 2
                    dict(WALL, version=2, wall=dict(WALL['wall'], look='marble')),
                    dict(WALL, version=2, wall=dict(WALL['wall'], ends=['free', 'through']))):
            _, report = compiled([made(bad)])
            self.assertIn('malformed', codes(report), bad)

    def test_the_join_rule(self):
        def wall(key, at, yaw=0, length=384.0, storeys=2):
            return dict(key=key, location=list(at), rotation=[0, yaw, 0],
                        wall=dict(x0=0.0, x1=length, **({'storeys': 1} if storeys == 1 else {})))
        Q = 16384

        def ends(walls):
            return {k: v['ends'] for k, v in compiler.wall_joins(walls).items()}
        # an L: the longer runs through, whichever way round
        self.assertEqual(ends([wall('a', (0, 0, 0), length=480.0), wall('b', (480, 0, 0), Q)]),
                         {'a': ['free', 'through'], 'b': ['free', 'free']})
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (384, 0, 0), Q, length=480.0)]),
                         {'a': ['free', 'free'], 'b': ['through', 'free']})
        # the taller first: a one-storey wall butts on a two-storey one
        self.assertEqual(ends([wall('a', (0, 0, 0), length=480.0, storeys=1), wall('b', (480, 0, 0), Q)]),
                         {'a': ['free', 'free'], 'b': ['through', 'free']})
        # the same: the one along x; an L at its start (b turned back on itself)
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (0, 384, 0), -Q)]),
                         {'a': ['through', 'free'], 'b': ['free', 'free']})
        # a T: the stem's end on the other's line between its ends stays free
        found = compiler.wall_joins([wall('a', (0, 0, 0), length=768.0), wall('b', (384, 0, 0), Q)])
        self.assertEqual({k: v['ends'] for k, v in found.items()}, {'a': ['free', 'free'], 'b': ['free', 'free']})
        self.assertEqual(found['b']['joins'], [dict(end=0, how='stem', other='a')])
        # end to end
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (384, 0, 0))]),
                         {'a': ['free', 'line'], 'b': ['line', 'free']})
        # end to end with a stem between them: the pair along x reaches the line, the stem stays free
        found = compiler.wall_joins([wall('a', (0, 0, 0)), wall('b', (384, 0, 0)), wall('c', (384, 0, 0), Q)])
        self.assertEqual({k: v['ends'] for k, v in found.items()},
                         {'a': ['free', 'line'], 'b': ['line', 'free'], 'c': ['free', 'free']})
        self.assertEqual(found['c']['joins'], [dict(end=0, how='stem', other='b')])
        # a cross of four ends: the pair along x end to end, the pair along y butting
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (384, 0, 0)), wall('c', (384, 0, 0), Q),
                               wall('d', (384, -384, 0), Q)]),
                         {'a': ['free', 'line'], 'b': ['line', 'free'], 'c': ['free', 'free'], 'd': ['free', 'free']})
        # a storey apart, or overlapping, or off by more than a unit: nothing meets
        self.assertEqual(ends([wall('a', (0, 0, 0), storeys=1), wall('b', (384, 0, 192), Q)]),
                         {'a': ['free', 'free'], 'b': ['free', 'free']})
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (0, 0, 0))]),
                         {'a': ['free', 'free'], 'b': ['free', 'free']})
        self.assertEqual(ends([wall('a', (0, 0, 0)), wall('b', (386, 0, 0), Q)]),
                         {'a': ['free', 'free'], 'b': ['free', 'free']})

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
               dict(WALL, wall=dict(x0=0, x1=96, storeys=13)), dict(WALL, wall=dict(x0=0, x1=96, storeys=True)),
               dict(WALL, wall=dict(x0=0, x1=96 * 129)), dict(WALL, wall=dict(x0=0, x1=96, whole=[0, 192])),
               dict(WALL, wall=dict(x0=0, x1=float('nan')))]
        for g in bad:
            spec, report = compiled([made(g)])
            self.assertIn('malformed', codes(report), g)
            self.assertFalse([o for o in (spec or {}).get('objects', []) if o['type'] == 'copy'], g)

    def test_a_slab_stands_in_its_footprint_and_bad_slabs_are_left_out(self):
        # (M5) a roof slab of 4 by 3 tiles with a hole: it goes to the Build as it is, noted, in its own box (its
        # footprint, between its look's heights: the roof's -2 to 2, the floor's 192 to 194), its height free
        slab = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4,
                                                         holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)]))
        floor = dict(slab, slab=dict(slab['slab'], holes=[], look='floor'))
        spec, report = compiled([made(slab, at=(0, 636, 14.5)), made(floor, serial=2, at=(0, 1212, 0))])
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('off-grid', warned(report))
        self.assertEqual(noted(report, 'generated'), ['generated-slab', 'generated-slab'])
        _, native = compiler.native_split(spec)
        roof, up = (c['box'] for c in native['copies'])
        self.assertEqual(roof, [0.0, 384.0, 636.0, 924.0, 12.5, 16.5])
        self.assertEqual(up, [0.0, 384.0, 1212.0, 1500.0, 192.0, 194.0])
        for bad in (dict(slab, version=2), dict(slab, slab=dict(slab['slab'], x1=380.0)),
                    dict(slab, slab=dict(slab['slab'], x1=96.0 * 129)), dict(slab, slab=dict(slab['slab'], look='marble')),
                    dict(slab, slab=dict(slab['slab'], holes=[dict(x0=0.0, x1=50.0, y0=0.0, y1=96.0)])),
                    dict(slab, slab=dict(slab['slab'], holes=[dict(x0=0.0, x1=96.0, y0=0.0, y1=480.0)])),
                    dict(slab, slab=dict(slab['slab'], seed=True)), dict(slab, slab=None)):
            spec, report = compiled([made(bad)])
            self.assertIn('malformed', codes(report), bad)
            self.assertFalse([o for o in (spec or {}).get('objects', []) if o['type'] == 'copy'], bad)

    def test_a_slab_in_a_building_but_in_none_of_its_floors_is_warned(self):
        # (EXP-76 run E) a made floor (its box 192 to 194) in a building whose floors break at 208 and 400 counts for
        # none (its bottom within 20 of floor 0's top, under floor 1): the game never cuts it away. With floors that
        # break at its height, as the Room with a roof tool now makes them, it counts for floor 1
        floor = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[], look='floor'))

        def run(breaks):
            house = dict(id='00000000-0000-4000-8000-0000000000b1', name='Hut', kind='building',
                         floors=[dict(boxes=[[0.0, 1212.0, lo, 384.0, 1500.0, hi]]) for lo, hi in breaks])
            doc = document((), [made(floor, at=(0, 1212, 0))], schemaVersion=4, buildings=[house])
            s = scene()
            s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
            _, report = compile_project(doc, s)
            self.assertTrue(report['ok'], refused(report))
            return [w for w in report['warnings'] if w['code'] == 'slab-in-no-floor']

        (w,) = run([(-16.0, 208.0), (208.0, 400.0)])
        self.assertIn('Hut', w['message'])
        self.assertEqual(w.get('record'), 'added[0]')
        self.assertEqual(run([(-16.0, 192.0), (192.0, 384.0), (384.0, 576.0)]), [])

    def test_made_slabs_bring_cursor_floors_of_their_own(self):
        # (M5b, F-128) URB_Bar's cursor floors break at 210, 402 and 594. A made floor with its top at 300 takes the
        # break at 210 over its footprint (tools/bake/made_cursors.py): a building's floor starting at 300 there is
        # where the cursor's floor starts, and is not warned (building-cursor); slab-under-cursor-break is gone
        floor = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[], look='floor'))
        bands = [(0.0, 210.0), (210.0, 402.0), (402.0, 594.0), (594.0, 768.0)]

        def scene_with(volumes, tiles=()):
            s = scene()
            s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
            s['exporterVersion'] = max(20, s.get('exporterVersion') or 0)
            s['cursorVolumes'] = volumes
            s['tactical'] = dict(floorTiles=list(tiles))
            return s

        bar = [dict(name='TheWorld.PersistentLevel.XComCursorVolume_%d' % n, floor=n + 1,
                    box=dict(min=[-5000.0, -5000.0, lo], max=[5000.0, 5000.0, hi])) for n, (lo, hi) in enumerate(bands)]

        def run(z, building_bottom=None, volumes=bar, tiles=()):
            house = [dict(id='00000000-0000-4000-8000-0000000000b1', name='Room', kind='building',
                          floors=[dict(boxes=[[0.0, 1212.0, 0.0, 384.0, 1500.0, building_bottom]]),
                                  dict(boxes=[[0.0, 1212.0, building_bottom, 384.0, 1500.0, building_bottom + 192.0]])])] \
                if building_bottom is not None else []
            doc = document((), [made(floor, at=(0, 1212, z))], schemaVersion=4, buildings=house)
            _, report = compile_project(doc, scene_with(volumes, tiles))
            self.assertTrue(report['ok'], refused(report))
            return report

        report = run(106.0, building_bottom=300.0)
        self.assertNotIn('building-cursor', warned(report))
        self.assertNotIn('slab-under-cursor-break', warned(report))
        # the same building box over no made floor is away from the map's floors
        doc = document((), [], schemaVersion=4, buildings=[dict(id='00000000-0000-4000-8000-0000000000b1', name='Room', kind='building',
                                                                floors=[dict(boxes=[[0.0, 1212.0, 0.0, 384.0, 1500.0, 300.0]]),
                                                                        dict(boxes=[[0.0, 1212.0, 300.0, 384.0, 1500.0, 492.0]])])])
        _, report = compile_project(doc, scene_with(bar))
        self.assertIn('building-cursor', warned(report))
        # a stair's cursor volume under the floor stays as it is, and is warned of
        stair = dict(name='TheWorld.PersistentLevel.XComCursorVolume_9', floor=2, stair=True,
                     box=dict(min=[96.0, 1300.0, 0.0], max=[192.0, 1400.0, 220.0]))
        (w,) = [d for d in run(106.0, volumes=bar + [stair])['warnings'] if d['code'] == 'slab-cursor-volume']
        self.assertIn("XComCursorVolume_9 (a stair's)", w['message'])
        self.assertEqual(w.get('record'), 'added[0]')
        # a made floor less than standing room over the map's floor tiles under it: their floor goes (F-71)
        tiles = [dict(tile=[x, 13, 0], location=[48.0 + 96.0 * x, 1260.0, 16.0], actor='TheWorld.PersistentLevel.Ground')
                 for x in range(4)]
        (w,) = [d for d in run(-40.0, tiles=tiles)['warnings'] if d['code'] == 'slab-headroom']
        self.assertIn('at 4 tiles', w['message'])
        self.assertNotIn('slab-headroom', warned(run(106.0, tiles=tiles)))
        # (EXP-80 run H, F-135) in no building, with the map's floor under it, the mouse takes its top on every storey;
        # in a building, or too low to stand under, not warned
        (w,) = [d for d in run(106.0, tiles=tiles)['warnings'] if d['code'] == 'slab-outdoors']
        self.assertIn('over 4 tiles', w['message'])
        self.assertEqual(w.get('record'), 'added[0]')
        self.assertNotIn('slab-outdoors', warned(run(106.0, building_bottom=300.0, tiles=tiles)))
        self.assertNotIn('slab-outdoors', warned(run(-40.0, tiles=tiles)))
        self.assertNotIn('slab-outdoors', warned(run(106.0)))

    def test_a_made_piece_on_a_scaled_donor_stands_in_its_box_at_scale_1(self):
        # (M4b item 5) the Build makes a piece from numbers at scale 1 whatever its donor's (frac_walls.unscale): its box
        # is its own numbers', not scaled by the donor's 0.6 (EXP-79's concrete donor at 0.6 had a box 0.6 the size)
        block = dict(kind='ground', version=1, ground=dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0))
        s = scene()
        for o in s['objects']:
            if o['actor'].endswith('.XComLevelActor_1'):
                o['scale'] = [0.6, 0.6, 0.6]
        spec, report = compile_project(document((), [made(block, name='XComLevelActor_1', at=(0, 0, 0))], schemaVersion=2), s)
        self.assertTrue(report['ok'], refused(report))
        _, native = compiler.native_split(spec)
        (box,) = [c['box'] for c in native['copies']]
        self.assertEqual(box, [0.0, 192.0, 0.0, 96.0, 0.0, 64.0])

    def test_a_ground_shape_copies_a_plain_piece_in_its_own_box(self):
        # (M6) a block, a ramp and a patch on XComLevelActor_1's copies: their boxes their own (a patch under the ground
        # it lies on), their height free; noted; a ramp over 10 degrees noted sloped, one over 45 warned; on a fracturing
        # piece, or with bad numbers, left out
        block = dict(kind='ground', version=1, ground=dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0))
        ramp = dict(kind='ground', version=1, ground=dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=96.0, height=96.0))
        steep = dict(ramp, ground=dict(ramp['ground'], x1=96.0, height=192.0))
        patch = dict(kind='ground', version=1, ground=dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0))
        rock = dict(kind='ground', version=1, ground=dict(shape='rock', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=96.0, seed=3))
        spec, report = compiled([made(block, name='XComLevelActor_1', at=(0, 0, 14.5)),
                                 made(ramp, name='XComLevelActor_1', serial=2, at=(0, 192, 0)),
                                 made(steep, name='XComLevelActor_1', serial=3, at=(0, 384, 0)),
                                 made(patch, name='XComLevelActor_1', serial=4, at=(0, 576, 0)),
                                 made(rock, name='XComLevelActor_1', serial=5, at=(0, 768, 0))])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(noted(report, 'generated'), ['generated-ground'] * 5)
        # a rock stands in the way (units don't walk on it)
        (rock_note,) = [d['message'] for d in report['notes'] if d['code'] == 'generated-ground' and 'rock' in d['message']]
        self.assertIn('stands in the way', rock_note)
        self.assertEqual(noted(report, 'ground'), ['ground-sloped'])
        self.assertIn('ground-steep', warned(report))
        _, native = compiler.native_split(spec)
        boxes = [c['box'] for c in native['copies']]
        self.assertEqual(boxes[0], [0.0, 192.0, 0.0, 96.0, 14.5, 78.5])
        self.assertEqual(boxes[1], [0.0, 288.0, 192.0, 288.0, 0.0, 96.0])
        self.assertEqual(boxes[3][4:], [3.0 - compiler.GROUND_LOOKS[compiler.GROUND_DEFAULT_LOOK], 3.0])     # (F-137: 3 over the ground)
        self.assertEqual(boxes[4], [0.0, 96.0, 768.0, 864.0, 0.0, 96.0])
        for bad in (dict(block, ground=dict(block['ground'], shape='dome')), dict(block, ground=dict(block['ground'], height=0)),
                    dict(block, ground=dict(block['ground'], x1=100.0)), dict(block, ground=dict(block['ground'], look='marble')),
                    dict(block, version=2), dict(rock, ground=dict(rock['ground'], seed=None)),
                    dict(rock, ground=dict(rock['ground'], seed=-2)), dict(rock, ground=dict(rock['ground'], seed=2.5))):
            spec, report = compiled([made(bad, name='XComLevelActor_1')])
            self.assertIn('malformed', codes(report), bad)
        spec, report = compiled([made(block)])          # on a fracturing piece
        self.assertIn('malformed', codes(report))

    def test_a_wall_on_a_wall_is_noted(self):
        # (F-127) a made wall whose bottom is at another's top, over it, is noted: it stays when the one under it
        # breaks. The test template is 100 tall about its pivot; the third wall stands 100 over the second's top
        plain = dict(WALL, wall=dict(WALL['wall'], openings=[]))
        spec, report = compiled([made(plain, serial=1, at=(0, 600, 0)), made(plain, serial=2, at=(0, 600, 100)),
                                 made(plain, serial=3, at=(0, 600, 300)), made(plain, serial=4, at=(0, 1800, 100))])
        self.assertTrue(report['ok'], refused(report))
        notes = [d for d in report['notes'] if d['code'] == 'wall-on-wall']
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('stays standing', notes[0]['message'])

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


class SplitTests(unittest.TestCase):
    """A made wall or floor past the sizes the game is known to take (custom geometry editing plan, B4, D-3): the
    compiler cuts it into pieces (tools/bake/made_split.py), each a copy of its own at its place, joined end to end
    or stacked, one member of the project's groups; the notes and checks name the whole."""
    NAME = 'XComFracLevelActor_11_copy1'

    def copies(self, spec):
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        return op

    def test_a_long_wall_is_three_joined_walls_cut_outside_its_gap(self):
        # 40 tiles with a gap over tiles 15 and 16: cut at 15 (16 would fall in the gap) and 31
        gap = dict(x0=96.0 * 15, x1=96.0 * 17, z0=8.0, z1=160.0)
        g = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=96.0 * 40, openings=[gap], seed=5))
        spec, report = compiled([made(g, at=(0, 600, 0))])
        self.assertTrue(report['ok'], refused(report))
        op = self.copies(spec)
        self.assertEqual(op['labels'], [self.NAME + '_part%d' % k for k in (1, 2, 3)])
        walls = [r['wall'] for r in op['generated']]
        self.assertEqual([(w['x0'], w['x1']) for w in walls], [(0.0, 1440.0), (0.0, 1536.0), (0.0, 864.0)])
        self.assertEqual([w['whole'] for w in walls], [[0.0, 3840.0], [1440.0, 3840.0], [2976.0, 3840.0]])
        self.assertEqual([w['openings'] for w in walls], [[], [dict(x0=0.0, x1=192.0, z0=8.0, z1=160.0)], []])
        self.assertEqual(len({w['seed'] for w in walls}), 3)
        self.assertEqual([p['location'] for p in op['poses']], [[0.0, 600.0, 0.0], [1440.0, 600.0, 0.0], [2976.0, 600.0, 0.0]])
        # joined end to end: the joints' ends reach the line (version 2), the wall's own ends stay free
        self.assertEqual([r['version'] for r in op['generated']], [2, 2, 2])
        self.assertEqual([w['ends'] for w in walls], [['free', 'line'], ['line', 'line'], ['line', 'free']])
        self.assertEqual([b[:2] for b in op['boxes']], [[8.0, 1440.0], [1440.0, 2976.0], [2976.0, 3832.0]])
        # said once, for the whole; its gap is checked on the whole
        self.assertEqual(noted(report, 'generated'), ['generated-wall'])
        self.assertEqual(noted(report, 'made-split'), ['made-split'])
        split = next(d['message'] for d in report['notes'] if d['code'] == 'made-split')
        self.assertIn('%s, 40 tiles long and 2 storeys, is made as 3 walls joined end to end' % self.NAME, split)
        door = [d['message'] for d in report['warnings'] if d['code'] == 'wall-doorway-no-door']
        self.assertEqual(door, ["%s's gap at 1440 to 1632 along it: a unit in this gap has cover toward its sides: put a "
                                "door in it, as the game's doorways have" % self.NAME])
        self.assertNotIn('wall-on-wall', noted(report))

    def test_a_tall_wall_is_walls_of_its_looks_storeys_stacked(self):
        # the Bar's inside wall is two storeys, -16 to 384: four storeys are two of it, the upper on the lower's top
        # (400 up); three are two and one
        for storeys, pieces in ((4, [None, None]), (3, [None, 1])):
            g = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[], seed=5, storeys=storeys))
            spec, report = compiled([made(g, at=(0, 600, 14.5))])
            self.assertTrue(report['ok'], refused(report))
            op = self.copies(spec)
            self.assertEqual([r['wall'].get('storeys') for r in op['generated']], pieces)
            self.assertEqual([p['location'] for p in op['poses']], [[0.0, 600.0, 14.5], [0.0, 600.0, 414.5]])
            self.assertNotIn('whole', op['generated'][0]['wall'])
            self.assertNotIn('wall-on-wall', noted(report))
            self.assertIn('is made as 2 walls stacked (',
                          next(d['message'] for d in report['notes'] if d['code'] == 'made-split'))

    def test_a_large_floor_is_slabs_side_by_side(self):
        # 30 by 20 tiles with a hole across the first cut: four slabs, 16 and 14 by 16 and 4
        hole = dict(x0=96.0 * 15, x1=96.0 * 17, y0=0.0, y1=96.0)
        g = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=96.0 * 30, y0=0.0, y1=96.0 * 20, holes=[hole], seed=4))
        spec, report = compiled([made(g, at=(0, 636, 14.5))])
        self.assertTrue(report['ok'], refused(report))
        op = self.copies(spec)
        slabs = [r['slab'] for r in op['generated']]
        self.assertEqual([(s['x1'], s['y1']) for s in slabs], [(1440.0, 1536.0), (1440.0, 1536.0), (1440.0, 384.0),
                                                              (1440.0, 384.0)])
        self.assertEqual([s['whole'] for s in slabs], [[0.0, 0.0, 2880.0, 1920.0], [1440.0, 0.0, 2880.0, 1920.0],
                                                       [0.0, 1536.0, 2880.0, 1920.0], [1440.0, 1536.0, 2880.0, 1920.0]])
        self.assertEqual([s['holes'] for s in slabs], [[], [dict(x0=0.0, x1=192.0, y0=0.0, y1=96.0)], [], []])
        self.assertEqual([p['location'] for p in op['poses']], [[0.0, 636.0, 14.5], [1440.0, 636.0, 14.5],
                                                                [0.0, 2172.0, 14.5], [1440.0, 2172.0, 14.5]])
        self.assertEqual(noted(report, 'generated'), ['generated-slab'])
        self.assertIn('%s, 30 by 20 tiles, is made as 4 slabs side by side' % self.NAME,
                      next(d['message'] for d in report['notes'] if d['code'] == 'made-split'))

    def test_a_cut_walls_pieces_break_with_its_group(self):
        # a group that breaks together names the wall once: each piece lists the group's prop
        PL = 'TheWorld.PersistentLevel.'
        g = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=96.0 * 20, openings=[], seed=5))
        group = dict(id='g', breakTogether=True, members=[{'added': PL + self.NAME},
                                                          {'added': PL + 'XComDestructibleActor_4_copy2'}])
        doc = document((), [made(g, at=(0, 636, 14.5)), add('XComDestructibleActor_4', 2, (144, 660, 14.5))],
                       schemaVersion=2, groups=[group])
        spec, report = compiler.compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        op = self.copies(spec)
        by = dict(zip(op['labels'], op['wallGroups']))
        self.assertEqual(by, {self.NAME + '_part1': 1, self.NAME + '_part2': 1, 'XComDestructibleActor_4_copy2': 0})
        self.assertEqual(report['groups'][0]['walls'], [self.NAME])


class BlastTests(unittest.TestCase):
    """A made wall, floor or roof built broken (custom geometry editing plan, B5): its blasts go to the Build with its
    numbers, each piece of a cut one the blasts that reach it in its frame; a note says it is built broken; bad blasts,
    or blasts on ground, leave the record out."""
    NAME = 'XComFracLevelActor_11_copy1'

    def test_a_broken_wall_takes_its_blasts_to_the_build(self):
        blasts = [dict(at=[192.0, 12.0, 100.0], radius=96.0)]
        g = dict(WALL, blasts=blasts)
        spec, report = compiled([made(g)])
        self.assertTrue(report['ok'], refused(report))
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        self.assertEqual(op['generated'][0]['blasts'], blasts)
        self.assertEqual(noted(report, 'made-broken'), ['made-broken'])
        self.assertIn('%s is built broken: its blast (Break' % self.NAME,
                      next(d['message'] for d in report['notes'] if d['code'] == 'made-broken'))

    def test_a_cut_wall_gives_each_piece_the_blasts_that_reach_it(self):
        # 40 tiles cut at 16 and 32: a blast 100 along reaches the first piece only; one at 1700 the second, 164 in
        blasts = [dict(at=[100.0, 0.0, 50.0], radius=96.0), dict(at=[1700.0, 0.0, 50.0], radius=96.0)]
        g = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=96.0 * 40, openings=[], seed=5), blasts=blasts)
        spec, report = compiled([made(g)])
        self.assertTrue(report['ok'], refused(report))
        (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
        self.assertEqual([r.get('blasts') for r in op['generated']],
                         [[blasts[0]], [dict(at=[164.0, 0.0, 50.0], radius=96.0)], None])
        self.assertEqual(noted(report, 'made-broken'), ['made-broken'])

    def test_bad_blasts_leave_the_record_out(self):
        ground = dict(kind='ground', version=1, ground=dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0))
        for g in (dict(WALL, blasts='x'), dict(WALL, blasts=[dict(at=[0, 0], radius=96)]),
                  dict(WALL, blasts=[dict(at=[0, 0, 0], radius=1)]),
                  dict(ground, blasts=[dict(at=[0, 0, 0], radius=96)])):
            spec, report = compiled([made(g) if g['kind'] != 'ground' else dict(add('XComLevelActor_1', 1, (0, 600, 0)), generated=g)])
            self.assertIn('malformed', codes(report), g)


def wall(*openings, x1=384.0):
    return dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=x1, openings=list(openings), seed=2))


DOORWAY = dict(x0=96.0, x1=192.0, z0=8.0, z1=160.0)
WINDOW = dict(x0=192.0, x1=288.0, z0=72.0, z1=168.0)


class PlainTests(unittest.TestCase):
    """A made piece with no look chosen (custom geometry editing plan, B2): drawn plain in the editor at its kind's
    plain version, its numbers its default look's as version 1 has them; the Build makes it in that look, as version 1,
    and a warning names it (D-1)."""

    def test_a_plain_piece_is_built_in_its_kind_s_default_look_and_named(self):
        wall = dict(WALL, version=4)
        floor = dict(kind='fracSlab', version=3, slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[], look='floor'))
        block = dict(kind='ground', version=3, ground=dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0))
        spec, report = compiled([made(wall), made(floor, serial=2, at=(0, 1212, 0)),
                                 made(block, name='XComLevelActor_1', serial=3, at=(0, 2400, 0))])
        self.assertTrue(report['ok'], refused(report))
        got = [w for w in report['warnings'] if w['code'] == 'made-no-look']
        self.assertEqual(len(got), 3)
        self.assertIn("the Bar's inside wall", got[0]['message'])
        self.assertIn("the Bar's upper floor", got[1]['message'])
        self.assertIn('asphalt', got[2]['message'])
        _, native = compiler.native_split(spec)
        made_ones = [c['generated'] for c in native['copies'] if c.get('generated')]
        self.assertEqual([g['version'] for g in made_ones], [1, 1, 1])
        self.assertEqual(made_ones[1]['slab']['look'], 'floor')

    def test_a_plain_piece_names_no_donor_look(self):
        # (its numbers are version 1's: a donor look in them is malformed)
        wall = dict(WALL, version=4, wall=dict(WALL['wall'], look={'mesh': 'URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', 'measure': 1}))
        _, report = compiled([made(wall)])
        self.assertIn('malformed', codes(report))


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
        self.assertEqual(self.warned(wall(dict(DOORWAY, z0=-16.0, z1=40.0))), ['wall-doorway-low'])
        # (one kind of gap: a window's shape low enough to walk through with no cover is a doorway)
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=40.0))), ['wall-doorway-no-door'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=50.0))), ['wall-window-walked'])
        # cut to the wall's bottom, or through its top: as any doorway
        self.assertEqual(self.warned(wall(dict(DOORWAY, z0=-16.0, z1=384.0))), ['wall-doorway-no-door'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=48.0, z1=60.5))), ['wall-window-blind'])
        self.assertEqual(self.warned(wall(dict(WINDOW, z0=112.0, z1=200.0))), ['wall-window-blind'])


class DonorLookTests(unittest.TestCase):
    """Looks named by their donor (custom geometry plan, M4: {mesh, measure}, tools/bake/looks.py): a slab's version 2
    and a ground shape's stand in their look's heights from the catalogue; one no catalogue holds goes to the Build,
    noted (it measures the donor); a donor look with an older version, or an old look id with the newer, is left out."""

    def setUp(self):
        import json
        import tempfile
        from unittest import mock
        self.dir = tempfile.TemporaryDirectory()
        folder = Path(self.dir.name)
        slab = {'mesh': 'Pkg.Meshes.Floor_FRACTURED', 'map': 'MapA', 'actor': 'XComFracLevelActor_4', 'maps': {},
                'name': 'Floor', 'setting': '', 'lwrOnly': False, 'facts': {}, 'warnings': [], 'twin': 'ok',
                'recipe': {'bottom': 0.0, 'top': 6.0, 'sections': 2, 'tile': 96.0}}
        grass = {'mesh': 'Pkg.Meshes.Plane', 'material': 'Pkg.Materials.Grass', 'map': 'MapB', 'actor': 'XComLevelActor_2',
                 'maps': {}, 'name': 'Grass', 'setting': '', 'lwrOnly': False, 'facts': {}, 'warnings': [], 'twin': 'ok',
                 'recipe': {'thickness': 4.0, 'repeat': 256.0, 'sections': 1}}
        for name, e in (('slabs.json', slab), ('ground.json', grass)):
            (folder / name).write_text(json.dumps({'measure': 1, 'looks': [e]}), encoding='utf-8', newline='\n')
        compiler.looks.forget()
        self.patch = mock.patch.object(compiler.looks, 'FOLDER', folder)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        compiler.looks.forget()
        self.dir.cleanup()

    def test_a_donor_look_takes_its_heights_from_the_catalogue(self):
        look = {'mesh': 'Pkg.Meshes.Floor_FRACTURED', 'measure': 1}
        slab = dict(kind='fracSlab', version=2, slab=dict(x0=0.0, x1=192.0, y0=0.0, y1=96.0, seed=1, holes=[], look=look))
        patch = dict(kind='ground', version=2, ground=dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0,
                                                            look={'mesh': 'Pkg.Meshes.Plane', 'material': 'Pkg.Materials.Grass',
                                                                  'measure': 1}))
        spec, report = compiled([made(slab, at=(0, 636, 0)), made(patch, name='XComLevelActor_5', serial=2, at=(0, 1212, 0))])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(noted(report, 'look-measured'), [])
        _, native = compiler.native_split(spec)
        floor, ground = (c['box'] for c in native['copies'])
        self.assertEqual(floor[4:], [0.0, 6.0])
        self.assertEqual(ground[5] - ground[4], 4.0)        # (the catalogued grass's thickness, not asphalt's 8)

    def test_a_donor_look_no_catalogue_holds_goes_to_the_build_noted(self):
        look = {'mesh': 'Other.Meshes.Roof_FRACTURED', 'measure': 1}
        slab = dict(kind='fracSlab', version=2, slab=dict(x0=0.0, x1=192.0, y0=0.0, y1=96.0, seed=1, holes=[], look=look))
        spec, report = compiled([made(slab, at=(0, 636, 0))])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(len(noted(report, 'look-measured')), 1)
        _, native = compiler.native_split(spec)
        self.assertEqual(native['copies'][0]['generated'], slab)

    def test_a_look_must_fit_its_request_version(self):
        donor = {'mesh': 'Pkg.Meshes.Floor_FRACTURED', 'measure': 1}
        base = dict(x0=0.0, x1=192.0, y0=0.0, y1=96.0, seed=1, holes=[])
        for bad in (dict(kind='fracSlab', version=1, slab=dict(base, look=donor)),
                    dict(kind='fracSlab', version=2, slab=dict(base, look='floor')),
                    dict(kind='fracSlab', version=2, slab=dict(base, look={'mesh': 'NoDot', 'measure': 1})),
                    dict(kind='fracWall', version=3, wall=dict(x0=0.0, x1=192.0, openings=[], look='bar-inside')),
                    dict(kind='fracWall', version=3, wall=dict(x0=0.0, x1=192.0, openings=[])),
                    dict(kind='fracWall', version=2, wall=dict(x0=0.0, x1=192.0, openings=[], look=donor)),
                    dict(kind='ground', version=2, ground=dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0, look=donor))):
            spec, report = compiled([made(bad)])
            self.assertIn('malformed', codes(report), bad)


class MapBlastTests(unittest.TestCase):
    """(custom geometry editing plan, E6) The map's own fracturing pieces broken: where it stands, the override's blasts
    go to the Build's writer as the spec's pieceBlasts; a moved one's, or an added copy's, on its copy, made in the map;
    a note says it is built broken; blasts on a piece that doesn't break, or bad ones, are errors; a deleted piece's are
    not built."""
    NAME = 'XComFracLevelActor_11'
    BLASTS = [dict(at=[0.0, 0.0, 60.0], radius=96.0)]

    def compile(self, overrides=(), added=()):
        return compile_project(document(overrides, added, schemaVersion=2), scene())

    def test_a_piece_broken_where_it_stands(self):
        spec, report = self.compile([dict(target=target(self.NAME), blasts=self.BLASTS)])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual([o for o in spec['objects'] if o['type'] == 'pieceBlasts'],
                         [dict(type='pieceBlasts', pieces=[dict(name=self.NAME, target=PL + self.NAME, blasts=self.BLASTS)])])
        self.assertFalse([o for o in spec['objects'] if o['type'] == 'copy'])
        self.assertEqual(noted(report, 'map-broken'), ['map-broken'])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(native['pieceBlasts'], [dict(name=self.NAME, blasts=self.BLASTS)])

    def test_a_moved_piece_and_an_added_copy_carry_their_blasts(self):
        added = dict(add(self.NAME, 1, (0, 600, 0)), blasts=self.BLASTS)
        spec, report = self.compile([dict(target=target(self.NAME), location=[96.0, -900.0, 0.0], rotation=[0, 0, 0],
                                          blasts=self.BLASTS)], [added])
        self.assertTrue(report['ok'], refused(report))
        self.assertFalse([o for o in spec['objects'] if o['type'] == 'pieceBlasts'])
        self.assertEqual(noted(report, 'map-broken'), ['map-broken', 'map-broken'])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(sorted(c['label'] for c in native['copies'] if c.get('blasts') == self.BLASTS),
                         sorted(c['label'] for c in native['copies']))
        self.assertEqual(len(native['copies']), 2)
        self.assertNotIn('pieceBlasts', native)

    def test_blasts_on_a_piece_that_does_not_break_or_bad_ones_are_errors(self):
        for name, blasts in (('XComLevelActor_1', self.BLASTS), (self.NAME, [dict(at=[0, 0], radius=96)]),
                             (self.NAME, [dict(at=[0, 0, 0], radius=1000)])):
            spec, report = self.compile([dict(target=target(name), blasts=blasts)])
            self.assertIn('malformed', codes(report), (name, blasts))
            self.assertFalse([o for o in spec['objects'] if o['type'] == 'pieceBlasts'])
        _, report = self.compile((), [dict(add('XComLevelActor_1', 1, (0, 600, 0)), blasts=self.BLASTS)])
        self.assertIn('malformed', codes(report))

    def test_a_deleted_piece_s_blasts_are_not_built(self):
        spec, report = self.compile([dict(target=target(self.NAME), deleted=True, blasts=self.BLASTS)])
        self.assertTrue(report['ok'], refused(report))
        self.assertFalse([o for o in spec['objects'] if o['type'] == 'pieceBlasts'])
        self.assertEqual(noted(report, 'blasts-deleted'), ['blasts-deleted'])


if __name__ == '__main__':
    unittest.main()
