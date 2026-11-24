"""Pieces' flags written in the map by native_copy.py (piece flags plan, P5), on the bar: in place and on copies, read
back with a fresh reader; the struct field patched with its siblings kept; tiles worked out again only where a tile
flag changes, in merged regions."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_columns  # noqa: E402
import native_copy  # noqa: E402
import lighting_records as lighting  # noqa: E402
import package_grow  # noqa: E402
import piece_flags  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
# a map no object of which saves bIgnoreFor3DCursorCollision, the mouse flag's property (review finding 37)
FALLEN, NO_FALLEN = labpaths.test_file('XCOM_HIGHWAYFALLEN_UPK', labpaths.lwr_cooked('URB_HighwayFallen.upk'),
                                       'URB_HighwayFallen.upk')
PL = native_copy.PL


class Ranges(unittest.TestCase):
    def test_touching_regions_merge_and_apart_ones_dont(self):
        self.assertEqual(native_copy.merge_ranges([(0, 2, 0, 2, 1, 2), (3, 4, 1, 1, 1, 3), (9, 9, 9, 9, 1, 1)]),
                         [(0, 4, 0, 2, 1, 3), (9, 9, 9, 9, 1, 1)])
        # a chain joins through its middle
        self.assertEqual(native_copy.merge_ranges([(0, 0, 0, 0, 1, 1), (4, 4, 0, 0, 1, 1), (2, 2, 0, 0, 1, 1),
                                                   (1, 1, 0, 0, 1, 1), (3, 3, 0, 0, 1, 1)]), [(0, 4, 0, 0, 1, 1)])
        self.assertEqual(native_copy.merge_ranges([]), [])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class StructField(unittest.TestCase):
    def test_the_field_is_patched_and_its_siblings_and_the_tail_kept(self):
        g = package_grow.Grower(str(BAR))
        p = lighting.Package(BAR)
        walker = native_copy.Walker(p, g)
        n = lambda s: g.name(s)    # noqa: E731

        def boolean(name, value):
            return struct.pack('<iiiiii', n(name), 0, n('BoolProperty'), 0, 0, 0) + bytes([value])
        none = struct.pack('<ii', n('None'), 0)
        inner = boolean('bOtherField', 1) + none
        outer = struct.pack('<iiiiii', n('VisibilityBlockingData'), 0, n('StructProperty'), 0, len(inner), 0) \
            + struct.pack('<ii', n('VisibilityBlocking'), 0) + inner
        tail = b'\x07\x07\x07\x07'
        data = bytearray(boolean('bHidden', 1) + outer + none + tail)

        def fields(d):
            out = {}
            for prop, kind, sub, at, size in walker.walk(bytes(d), 0, len(d)):
                if prop == 'VisibilityBlockingData[0]':
                    out = {k: d[a] for k, _, _, a, _ in walker.walk(bytes(d), at, at + size)}
            return out
        d1, how = native_copy.set_struct_bool(walker, g, bytearray(data), 0, 'VisibilityBlockingData',
                                              'VisibilityBlocking', 'bBlockUnitVisibility', False)
        self.assertEqual(how, 'field added')
        self.assertEqual(fields(d1), {'bOtherField[0]': 1, 'bBlockUnitVisibility[0]': 0})
        self.assertTrue(bytes(d1).endswith(none + tail))
        d2, how = native_copy.set_struct_bool(walker, g, d1, 0, 'VisibilityBlockingData', 'VisibilityBlocking',
                                              'bBlockUnitVisibility', True)
        self.assertEqual((how, fields(d2)), ('changed', {'bOtherField[0]': 1, 'bBlockUnitVisibility[0]': 1}))
        self.assertEqual(len(d2), len(d1))      # a second write is the same size
        # no struct saved: one of the field alone is added
        bare = bytearray(boolean('bHidden', 1) + none + tail)
        d3, how = native_copy.set_struct_bool(walker, g, bare, 0, 'VisibilityBlockingData', 'VisibilityBlocking',
                                              'bBlockUnitVisibility', False)
        self.assertEqual((how, fields(d3)), ('struct added', {'bBlockUnitVisibility[0]': 0}))
        self.assertTrue(bytes(d3).endswith(none + tail))


@unittest.skipUnless(FALLEN and FALLEN.exists(), NO_FALLEN)
class NameNewToTheMap(unittest.TestCase):
    """(Review finding 37) A copy given "mouse off" on a map that has no bIgnoreFor3DCursorCollision in its name table:
    set_roles adds the name to the grower's table and the tag before the closing None, and the writers that walk the
    copy afterwards (link_children, move_columns) get past it. Nothing is written to disk."""
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(FALLEN)
        cls.level = cls.p.by_name['TheWorld.PersistentLevel']

    def copy(self, classes):
        p = self.p
        self.assertNotIn('bIgnoreFor3DCursorCollision', p.names)
        actor = next(i for i in native_copy.level_actors(p) if i > 0 and p.cls(i) in classes
                     and p.exports[i - 1]['outer'] == self.level and native_copy.has_mesh(p, i))
        before = ([float(v) for v in p.own(actor, 'Location', [0.0, 0.0, 0.0])],
                  [int(v) for v in p.own(actor, 'Rotation', [0, 0, 0])])
        after = ([v + 192.0 for v in before[0]], before[1])
        g = package_grow.Grower(str(FALLEN))
        info = native_copy.clone_assembly(g, p, [(actor, *after)])[0]
        return g, actor, info, before, after

    def mouse_off(self, g, actor, info):
        rec = native_copy.set_roles(g, self.p, actor, info['actor'], {'mouse': False}, label='copy')
        self.assertEqual(rec['written'], [['bIgnoreFor3DCursorCollision', True, 'added']])

    def test_link_children_walks_past_it(self):
        g, actor, info, _, after = self.copy(('XComLevelActor',))
        self.mouse_off(g, actor, info)
        made = [dict(actor=self.p.name(actor).split('.')[-1], info=info, location=after[0], rotation=after[1],
                     breakGroup=0)]
        native_copy.link_children(g, self.p, made, [])

    def test_move_columns_walks_past_it(self):
        # a fracturing copy that saves no FragmentColumns (cut out of the copy here): move_columns walks to the end
        g, actor, info, before, after = self.copy(native_copy.FRACTURING)
        e = self.p.exports[actor - 1]
        start = native_copy.legacy_props.props_start(self.p.data, e, self.p.names) - e['off']
        b = bytearray(g.export_data(info['actor']))
        _, tag, value, size = native_copy.find_prop(native_copy.Walker(self.p), b, start, len(b), 'FragmentColumns[0]')
        g.relocate(info['actor'], bytes(b[:tag] + b[value + size:]))
        self.mouse_off(g, actor, info)
        self.assertIsNone(frac_columns.move_columns(g, self.p, actor, info['actor'], before, after, {info['actor']}))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class FlagsBuilt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        loc = list(cls.p.own(cls.p.by_name[PL + 'XComLevelActor_103'], 'Location'))
        cls.copies = [dict(actor='XComLevelActor_103', location=[loc[0] + 192, loc[1], loc[2]], rotation=None,
                           label='XComLevelActor_103_copy1', flags=dict(floor=False)),
                      dict(actor='XComLevelActor_103', location=[loc[0] + 384, loc[1], loc[2]], rotation=None,
                           label='XComLevelActor_103_copy2')]
        cls.pieces = [dict(name='XComLevelActor_103', flags=dict(walking=False, sight=False, mouse=False)),
                      dict(name='XComDestructibleActor_111', flags=dict(walking=True, cover=True)),
                      dict(name='XComLevelActor_11', flags=dict(mouse=False))]
        cls.m = native_copy.build(native_copy.BuildState(BAR, out, 'Flags', cls.copies, piece_flags=cls.pieces))
        cls.q = lighting.Package(out / 'Flags.upk')
        cls.record = cls.m['nativeCopies']['pieceFlags']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def states(self, q, index):
        return piece_flags.states(q.cls(index), piece_flags.resolve(q, index)['raw'])

    def test_in_place_flags_are_on_the_actor_and_read_back(self):
        q = self.q
        by = {r['actor']: r for r in self.record['inPlace']}
        lvl = q.by_name[PL + 'XComLevelActor_103']
        self.assertEqual(self.states(q, lvl), dict(walking='off', cover='on', sight='off', floor='on', mouse='off'))
        r = piece_flags.resolve(q, lvl)
        for prop in ('bAlwaysConsiderForCover', 'bBlockUnitVisibility', 'bIgnoreFor3DCursorCollision'):
            self.assertEqual(r['source'][prop], 'actor', prop)
        self.assertTrue(all(rec.get('readBack') for rec in by.values() if rec['written']))
        self.assertEqual([w[0] for w in by['XComLevelActor_103']['written']],
                         ['bAlwaysConsiderForCover', 'bBlockUnitVisibility', 'bIgnoreFor3DCursorCollision'])

    def test_a_gated_prop_opens_its_gate_with_sight_left_as_it_was(self):
        q, p = self.q, self.p
        name = PL + 'XComDestructibleActor_111'
        before = self.states(p, p.by_name[name])
        self.assertEqual((before['walking'], before['cover'], before['sight']), ('partial', 'off', 'off'))
        after = self.states(q, q.by_name[name])
        self.assertEqual((after['walking'], after['cover'], after['sight']), ('on', 'on', 'off'))
        rec = next(r for r in self.record['inPlace'] if r['actor'] == 'XComDestructibleActor_111')
        self.assertEqual(rec['companions'], [])     # its sight is off already: the open gate leaves it off
        self.assertIn(['bIgnoreForPathing', False, 'added'], rec['written'])
        self.assertIs(piece_flags.resolve(q, q.by_name[name])['raw']['bIgnoreForPathing'], False)

    def test_the_mouse_alone_needs_no_tile_work_and_the_others_tiles_are_rebuilt(self):
        tiles = self.record['tiles']
        rec = next(r for r in self.record['inPlace'] if r['actor'] == 'XComLevelActor_11')
        self.assertFalse(rec['tiles'])
        self.assertEqual(len(tiles['regions']), len({tuple(t['tiles']) for t in tiles['regions']}))
        self.assertTrue(all('volume' in t for t in tiles['regions']))
        self.assertGreaterEqual(len(tiles['regions']), 1)
        self.assertLessEqual(len(tiles['regions']), 2)      # two pieces with tile changes

    def test_copies_take_their_own_flags_and_never_the_originals(self):
        q = self.q
        one, two = self.m['nativeCopies']['copies']
        self.assertEqual(self.states(q, one['export']), dict(walking='on', cover='on', sight='on', floor='off', mouse='on'))
        self.assertEqual(self.states(q, two['export']), dict(walking='on', cover='on', sight='on', floor='on', mouse='on'))
        (rec,) = self.record['onCopies']
        self.assertEqual((rec['copy'], rec['written'], rec.get('readBack')),
                         (q.name(one['export']).split('.')[-1], [['bPathColliding', False, 'added']], True))

    def test_the_rest_of_each_actor_is_as_it_was(self):
        # every property of the actors but those written is the same, and so is everything after their properties
        p, q = self.p, self.q
        for rec in self.record['inPlace']:
            i = p.by_name[PL + rec['actor']]
            mine, theirs = p.properties(i)[0], q.properties(q.by_name[PL + rec['actor']])[0]
            written = {w[0] for w in rec['written']} | {'VisibilityBlockingData'}
            self.assertEqual({k: v for k, v in mine.items() if k[0] not in written},
                             {k: v for k, v in theirs.items() if k[0] not in written}, rec['actor'])
            e, f = p.exports[i - 1], q.exports[q.by_name[PL + rec['actor']] - 1]
            self.assertEqual(p.data[p.properties(i)[1]:e['off'] + e['size']],
                             q.data[q.properties(q.by_name[PL + rec['actor']])[1]:f['off'] + f['size']], rec['actor'])

    def test_writing_again_on_the_built_map_writes_nothing(self):
        out = Path(self.tmp.name) / 'again'
        m = native_copy.build(native_copy.BuildState(Path(self.tmp.name) / 'Flags.upk', out, 'Again', [],
                                                     piece_flags=self.pieces))
        f = m['nativeCopies']['pieceFlags']
        self.assertEqual(f['written'], 0)
        self.assertIsNone(f['tiles'])

    def test_a_piece_the_map_hasnt_or_the_edit_takes_out_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                native_copy.build(native_copy.BuildState(
                    BAR, d, 'Missing', [], piece_flags=[dict(name='XComLevelActor_99999', flags=dict(mouse=False))]))
            box = native_copy.piece_box(self.p, self.p.by_name[PL + 'XComLevelActor_11'],
                                        self.p.own(self.p.by_name[PL + 'XComLevelActor_11'], 'Location'),
                                        self.p.own(self.p.by_name[PL + 'XComLevelActor_11'], 'Rotation', [0, 0, 0]))
            with self.assertRaises(ValueError):
                native_copy.build(native_copy.BuildState(
                    BAR, d, 'Gone', [], hides=[dict(name='XComLevelActor_11', box=box)],
                    piece_flags=[dict(name='XComLevelActor_11', flags=dict(mouse=False))]))

    def test_a_maps_ladder_near_a_change_rebuilds_its_top_tile_first(self):
        # XComLadder_3 where the map has it (foot (11, 23, 0), top (12, 23, 6): two tiles short of its moved copy in
        # test_native_copy), its own walking turned off: the region's volume would queue its foot first; the top tile's
        # own volume goes first in the level's list, and the foot's after
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(
                BAR, d, 'FlagLadder', [], piece_flags=[dict(name='XComLadder_3', flags=dict(walking=False))],
                flag_ladders=[dict(actor='XComLadder_3', foot=[11, 23, 0], top=[12, 23, 6])]))
            [ladder] = m['nativeCopies']['ladders']
            self.assertTrue(ladder['inPlace'])
            self.assertLess(ladder['topPlace'], ladder['footPlace'])
            q = lighting.Package(Path(d) / 'FlagLadder.upk')
            volumes = [a for a in native_copy.level_actors(q) if a > 0 and q.cls(a) == 'XComRebuildWorldDataVolume']
            self.assertEqual(volumes[0], ladder['topVolume']['export'])
            # a change that needs no tile work rebuilds no ladder
            m = native_copy.build(native_copy.BuildState(
                BAR, Path(d) / 'mouse', 'FlagMouse', [], piece_flags=[dict(name='XComLadder_3', flags=dict(mouse=False))],
                flag_ladders=[dict(actor='XComLadder_3', foot=[11, 23, 0], top=[12, 23, 6])]))
            self.assertEqual(m['nativeCopies']['ladders'], [])

    def test_on_a_cleared_map_the_clears_volume_covers_the_tiles_and_kept_pieces_take_flags(self):
        # the clear leaves the map's pieces (the delete records take them out) and puts one volume over the grid: the
        # flags' tiles are seeded, with no volume of their own
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(native_copy.BuildState(
                BAR, d, 'FlagCleared', [], cleared=dict(grid=[52, 39, 12], parts={k: {} for k in native_copy.CLEAR_PARTS}),
                piece_flags=[dict(name='XComLevelActor_103', flags=dict(walking=False))]))
            f = m['nativeCopies']['pieceFlags']
            self.assertEqual(f['tiles']['volumes'], "the cleared map's")
            self.assertTrue(all('volume' not in t for t in f['tiles']['regions']))
            q = lighting.Package(Path(d) / 'FlagCleared.upk')
            self.assertEqual(self.states(q, q.by_name[PL + 'XComLevelActor_103'])['walking'], 'off')

    def test_many_regions_are_joined_past_the_limit(self):
        g = package_grow.Grower(str(BAR))
        p = self.p
        boxes = []
        for name in ('XComLevelActor_103', 'XComLevelActor_11', 'XComDestructibleActor_111'):
            i = p.by_name[PL + name]
            boxes.append((name, native_copy.piece_box(p, i, p.own(i, 'Location'), p.own(i, 'Rotation', [0, 0, 0]))))
        rec, made = native_copy.flag_tiles(g, p, boxes, max_regions=1)
        self.assertEqual((len(rec['regions']), len(made), rec['joined']), (1, 1, True))
        rec, made = native_copy.flag_tiles(g, p, boxes, volumes=False)
        self.assertEqual(made, [])
        self.assertTrue(all('volume' not in t for t in rec['regions']))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class FlagsCommandLine(unittest.TestCase):
    def test_the_command_line_keeps_a_copys_flags_and_the_pieces_in_place(self):
        p = lighting.Package(BAR)
        loc = list(p.own(p.by_name[PL + 'XComLevelActor_103'], 'Location'))
        edit = dict(copies=[dict(actor='XComLevelActor_103', location=[loc[0] + 192, loc[1], loc[2]], rotation=[0, 0, 0],
                                 label='c', flags=dict(mouse=False))],
                    pieceFlags=[dict(name='XComLevelActor_11', flags=dict(walking=False))])
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'edit.json'
            f.write_text(json.dumps(edit), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(HERE.parent / 'native_copy.py'), str(BAR), d, 'Cli',
                                  '--copies', str(f)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            self.assertIn('flags of copy', run.stdout)
            self.assertIn('flags in place: XComLevelActor_11', run.stdout)
            m = json.loads((Path(d) / 'Cli.fixture.json').read_text(encoding='utf-8'))
            f = m['nativeCopies']['pieceFlags']
            self.assertEqual(([r['applied'] for r in f['onCopies']], [r['applied'] for r in f['inPlace']]),
                             ([dict(mouse=False)], [dict(walking=False)]))
            # flags alone are an edit
            only = Path(d) / 'only.json'
            only.write_text(json.dumps(dict(pieceFlags=[dict(name='XComLevelActor_11', flags=dict(mouse=False))])),
                            encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(HERE.parent / 'native_copy.py'), str(BAR),
                                  str(Path(d) / 'only'), 'Only', '--copies', str(only)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
