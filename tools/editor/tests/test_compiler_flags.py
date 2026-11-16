"""The compiler and pieces' flags (piece flags plan, P4): a flags-only override is written where the piece stands, a
moved or added copy carries its flags to the Build's writer, and what can't be built is warned of or noted."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
from compiler import compile_project  # noqa: E402
import ladders  # noqa: E402
import piece_flags  # noqa: E402
from test_compiler import PL, add, assembly_scene, document, noted, part, refused, scene, target, warned  # noqa: E402


def flagged(s, collides=True, body=True, **own):
    """`s` with every base piece's flags as its class has them (export 27's pieceFlags), and `own` ({short name:
    {property: value}}) set on those pieces by the actor itself."""
    for o in s['objects']:
        family = piece_flags.family_of(o['actorClass'])
        if family is None or o['layer'] != 'base':
            continue
        mine = own.get(compiler.short(o['actor']), {})
        values = dict(piece_flags.CLASS_DEFAULTS[o['actorClass']], **mine)
        raw = {k: [values[k], 'actor' if k in mine else 'class'] for k in piece_flags.FAMILY_PROPS[family] if k in values}
        o['pieceFlags'] = dict(family=family, raw=raw, roles=piece_flags.states(o['actorClass'], {k: v[0] for k, v in raw.items()}),
                               collides=collides, bodySetup=body)
    return s


def flags_of(spec):
    return next((o['pieces'] for o in spec['objects'] if o.get('type') == 'pieceFlags'), [])


def compiled(overrides=(), added=(), s=None, **changes):
    spec, report = compile_project(document(overrides, added, schemaVersion=2, **changes), s or flagged(scene()))
    assert report['ok'], refused(report)
    return spec, report


class FlagsInPlaceTests(unittest.TestCase):
    def test_flags_alone_are_written_where_the_piece_stands(self):
        spec, report = compiled([dict(target=target('XComLevelActor_1'), flags=dict(walking=False, mouse=False))])
        self.assertEqual([o['type'] for o in spec['objects']], ['pieceFlags'])
        (entry,) = flags_of(spec)
        self.assertEqual(entry, dict(name='XComLevelActor_1', target=PL + 'XComLevelActor_1',
                                     flags=dict(walking=False, mouse=False), box=[-48.0, 48.0, -48.0, 48.0, 0.0, 100.0],
                                     tiles=True, actorClass='XComLevelActor'))
        (entity,) = report['entities']
        self.assertEqual((entity['kind'], entity['after']['walking'], entity['after']['mouse'], entity['after']['cover']),
                         ('flags', 'off', 'off', 'on'))
        self.assertEqual(entity['writes'], [['bAlwaysConsiderForCover', False], ['bIgnoreFor3DCursorCollision', True]])
        counts = report['counts']
        self.assertEqual((counts['moved'], counts['deleted'], counts['added']), (0, 0, 0))
        self.assertEqual((counts['flags']['inPlace'], counts['flags']['onCopies'], counts['flags']['applied'],
                          counts['flags']['roles']['walking'], counts['flags']['roles']['cover']), (1, 0, 1, 1, 0))
        # made in the map by the Build's writer: nothing for a patch
        patch, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(patch['objects'], [])
        self.assertEqual(native['pieceFlags'], [entry])
        self.assertEqual((native['copies'], native['hides']), ([], []))

    def test_the_mouse_alone_changes_no_tile(self):
        spec, _ = compiled([dict(target=target('XComLevelActor_1'), flags=dict(mouse=False))])
        self.assertFalse(flags_of(spec)[0]['tiles'])

    def test_flags_with_the_pieces_own_pose_are_in_place_too(self):
        # a pose that rounds to the export's (an override kept after a move back) moves nothing
        spec, report = compiled([dict(target=target('XComLevelActor_2'), location=[96, 0, 0], rotation=[0, 0.3, 0],
                                      flags=dict(cover=False))])
        self.assertEqual([o['type'] for o in spec['objects']], ['pieceFlags'])
        self.assertEqual(report['counts']['moved'], 0)

    def test_records_in_any_order_compile_the_same(self):
        a = dict(target=target('XComLevelActor_2'), flags=dict(sight=False))
        b = dict(target=target('XComLevelActor_1'), flags=dict(walking=False))
        one, _ = compiled([a, b])
        two, _ = compiled([b, a])
        self.assertEqual(one, two)
        self.assertEqual([e['name'] for e in flags_of(one)], ['XComLevelActor_1', 'XComLevelActor_2'])

    def test_a_deleted_piece_has_its_flags_noted_not_built(self):
        spec, report = compiled([dict(target=target('XComLevelActor_1'), deleted=True, flags=dict(walking=False))])
        self.assertEqual([o['type'] for o in spec['objects']], ['hide'])
        self.assertEqual(noted(report, 'flags'), ['flags-deleted'])

    def test_malformed_flags_leave_the_record_out(self):
        for flags in ({}, dict(walking='no'), dict(walking=0), dict(ethereal=True), [], None):
            spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), flags=flags)], schemaVersion=2),
                                           flagged(scene()))
            self.assertEqual([d['code'] for d in refused(report)], ['malformed'], flags)
            self.assertEqual(flags_of(spec or dict(objects=[])), [])

    def test_a_role_the_class_lacks_is_noted_and_the_rest_built(self):
        s = flagged(assembly_scene())
        spec, report = compiled([dict(target=target('XComLadder_20'), flags=dict(cover=False, mouse=False))], s=s)
        self.assertEqual(noted(report, 'flags'), ['flags-unsupported'])
        self.assertEqual(flags_of(spec)[0]['flags'], dict(mouse=False))
        # all of it unsupported: nothing built for the piece
        spec, report = compiled([dict(target=target('StaticMeshActor_3'), flags=dict(walking=False))])
        self.assertEqual((flags_of(spec), noted(report, 'flags')), ([], ['flags-unsupported']))
        self.assertEqual(report['counts']['flags']['leftOut'], 1)

    def test_a_gated_props_ambiguous_request_is_warned_of_and_not_built(self):
        s = flagged(scene(), XComDestructibleActor_4=dict(bIgnoreForPathing=True, bIgnoreForCover=True))
        spec, report = compiled([dict(target=target('XComDestructibleActor_4'), flags=dict(cover=True))], s=s)
        self.assertEqual((flags_of(spec), warned(report, 'flags')), ([], ['flags-conflict']))
        # with walking given too, it is built, sight written to stay as it was (a companion)
        spec, report = compiled([dict(target=target('XComDestructibleActor_4'), flags=dict(cover=True, walking=True))], s=s)
        self.assertEqual(flags_of(spec)[0]['flags'], dict(cover=True, walking=True))
        self.assertEqual(report['entities'][0]['companions'], ['sight'])
        self.assertEqual(report['counts']['flags']['companions'], 1)

    def test_an_export_without_flags_builds_the_piece_without_them(self):
        spec, report = compiled([dict(target=target('XComLevelActor_1'), flags=dict(walking=False))], s=scene())
        self.assertEqual((flags_of(spec), warned(report, 'flags')), ([], ['flags-unavailable']))
        self.assertIn('export 27', report['warnings'][0]['message'])
        # moved, it is still moved, without them
        spec, report = compiled([dict(target=target('XComLevelActor_1'), location=[10, 20, 30], rotation=[0, 0, 0],
                                      flags=dict(walking=False))], s=scene())
        self.assertEqual([o['type'] for o in spec['objects']], ['copy', 'hide'])
        self.assertNotIn('flags', spec['objects'][0])

    def test_a_door_a_wall_and_a_piece_that_collides_with_nothing_are_warned_of_or_noted(self):
        s = flagged(scene())
        s['meshes']['wall'] = dict(bounds=[0, 0, 100, 200, 8, 100, 200])
        s['objects'].append(part('XComLevelActor_40', at=(0, 400, 0), mesh='wall'))
        s = flagged(s)
        _, report = compiled([dict(target=target('XComInteractiveLevelActor_8'), flags=dict(walking=False)),
                              dict(target=target('XComLevelActor_40'), flags=dict(sight=False)),
                              dict(target=target('XComFracLevelActor_11'), flags=dict(cover=False))], s=s)
        self.assertEqual(warned(report, 'flags'), ['flags-door'])
        self.assertEqual(noted(report, 'flags'), ['flags-wall', 'flags-wall'])
        _, report = compiled([dict(target=target('XComLevelActor_1'), flags=dict(walking=False))],
                             s=flagged(scene(), collides=False))
        self.assertEqual(noted(report, 'flags'), ['flags-no-collision'])
        _, report = compiled([dict(target=target('XComLevelActor_1'), flags=dict(walking=False))],
                             s=flagged(scene(), body=False))
        self.assertEqual(noted(report, 'flags'), ['flags-limited'])


class FlagsOnCopiesTests(unittest.TestCase):
    def test_a_moved_piece_carries_its_flags_to_its_copy(self):
        spec, report = compiled([dict(target=target('XComLevelActor_1'), location=[10, 20, 30], rotation=[0, 0, 0],
                                      flags=dict(floor=False))])
        copy_op, hide = spec['objects']
        self.assertEqual((copy_op['type'], copy_op['flags'], hide['type']), ('copy', [dict(floor=False)], 'hide'))
        self.assertEqual(report['counts']['flags']['onCopies'], 1)
        patch, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(native['copies'][0]['flags'], dict(floor=False))
        self.assertNotIn('pieceFlags', native)

    def test_added_copies_carry_theirs_and_the_others_none(self):
        plain = add('XComLevelActor_1', 1, (0, 400, 0))
        marked = dict(add('XComLevelActor_2', 2, (0, 600, 0)), flags=dict(cover=False, sight=False))
        spec, _ = compiled([], [plain, marked])
        (copy_op,) = spec['objects']
        self.assertEqual(copy_op['flags'], [None, dict(cover=False, sight=False)])
        _, native = compiler.native_split(spec)
        self.assertEqual([c.get('flags') for c in native['copies']], [None, dict(cover=False, sight=False)])
        # none with flags: no list
        spec, _ = compiled([], [plain])
        self.assertNotIn('flags', spec['objects'][0])

    def test_a_copy_of_a_class_the_patch_could_copy_is_made_in_the_map_when_it_has_flags(self):
        spec = dict(name='x', map=dict(name='URB_Bar'), objects=[dict(
            type='copy', **{'from': ['Thing_1', 'Thing_2']}, poses=[dict(location=[0, 0, 0], rotation=[0, 0, 0])] * 2,
            labels=['a', 'b'], boxes=[[0] * 6] * 2, classes=['SomeActor', 'SomeActor'], flags=[None, dict(mouse=False)],
            location=[0, 0, 0])])
        patch, native = compiler.native_split(spec)
        self.assertEqual([c['label'] for c in native['copies']], ['b'])
        (rest,) = patch['objects']
        self.assertEqual((rest['from'], rest['flags']), (['Thing_1'], [None]))

    def test_flags_on_a_cover_block_or_a_light_are_refused(self):
        cover = {'id': '00000000-0000-4000-8000-000000000009', 'actor': PL + 'CoverBlock_copy9',
                 'template': dict(kind='cover', version=2), 'cover': dict(type='high', size=[96, 96], heights=[-12, 96]),
                 'location': [0, 0, 0], 'rotation': [0, 0, 0], 'flags': dict(walking=False)}
        _, report = compile_project(document([], [cover], schemaVersion=2), flagged(scene()))
        self.assertIn('malformed', [d['code'] for d in refused(report)])


class FlagsAndFloorTests(unittest.TestCase):
    def test_a_piece_made_no_floor_takes_its_saved_floor_and_says_so(self):
        s = flagged(scene())
        s['tactical'] = dict(floorTiles=[dict(tile=[28, 19, 0], actor=PL + 'XComLevelActor_1'),
                                         dict(tile=[29, 19, 0], actor=PL + 'XComLevelActor_1'),
                                         dict(tile=[30, 19, 0], actor=PL + 'XComLevelActor_2')])
        spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), flags=dict(floor=False))],
                                                schemaVersion=2), s)
        self.assertEqual(warned(report, 'flags'), ['flags-floor'])
        self.assertEqual(next(w for w in report['warnings'] if w['code'] == 'flags-floor')['tiles'], 2)
        c = compiler.Compiler(document([dict(target=target('XComLevelActor_1'), flags=dict(floor=False))], schemaVersion=2), s)
        c.run()
        self.assertEqual(c.floor_now(), {(30, 19, 0)})
        self.assertEqual(c.floor_kept_off(), {PL + 'XComLevelActor_1'})

    def test_a_flat_piece_made_floor_counts_as_floor_and_an_added_one_made_no_floor_doesnt(self):
        s = flagged(scene(), XComLevelActor_1=dict(bPathColliding=False))
        s['meshes']['plate'] = dict(bounds=[0, 0, 4, 48, 48, 4, 70])
        s['objects'].append(part('XComLevelActor_41', at=(96, 96, 0), mesh='plate'))
        s['meshes']['m'] = dict(bounds=[0, 0, 4, 48, 48, 4, 70])         # every piece a flat plate
        s = flagged(s, XComLevelActor_1=dict(bPathColliding=False))
        c = compiler.Compiler(document([dict(target=target('XComLevelActor_1'), flags=dict(floor=True))],
                                       [dict(add('XComLevelActor_2', 1, (0, 960, 0)), flags=dict(floor=False)),
                                        add('XComLevelActor_2', 2, (0, 1152, 0))], schemaVersion=2), s)
        c.run()
        new, _ = c.added_floors()
        self.assertEqual(sorted(set(new.values())), ['XComLevelActor_1', 'XComLevelActor_2_copy2'])

    def test_the_maps_ladders_near_a_tile_change_are_rebuilt_top_first(self):
        s = assembly_scene()
        s['objects'].append(part('XComLevelActor_42', at=(432, 1200, 16)))      # beside XComLadder_20's foot
        s = flagged(s)
        spec, _ = compiled([dict(target=target('XComLevelActor_42'), flags=dict(walking=False))], s=s)
        (obj,) = [o for o in spec['objects'] if o.get('type') == 'pieceFlags']
        (ladder,) = obj['ladders']
        self.assertEqual(ladder['actor'], 'XComLadder_20')
        _, native = compiler.native_split(spec)
        self.assertEqual(native['pieceFlagLadders'], [ladder])
        # the mouse alone changes no tile, and a piece far off reaches no ladder
        for rec in (dict(target=target('XComLevelActor_42'), flags=dict(mouse=False)),
                    dict(target=target('XComLevelActor_1'), flags=dict(walking=False))):
            spec, _ = compiled([rec], s=s)
            self.assertNotIn('ladders', next(o for o in spec['objects'] if o.get('type') == 'pieceFlags'))

    def test_a_maps_ladder_whose_end_loses_its_floor_is_warned_of(self):
        s = flagged(assembly_scene())
        ladder = next(o for o in s['objects'] if o['actor'] == PL + 'XComLadder_20')
        e = ladders.ends(ladder['location'], ladder['rotation'], ladders.extent_z(dict(meshes=s['meshes']), ladder),
                         compiler.tile_corner(s['tileGrid']), ladders.floor_tiles(s))
        self.assertTrue(e['climbs'])
        for f in s['tactical']['floorTiles']:
            if f['tile'] == list(e['footTile']):
                f['actor'] = PL + 'XComLevelActor_34'
        _, report = compiled([dict(target=target('XComLevelActor_34'), flags=dict(floor=False))], s=s)
        self.assertEqual(warned(report, 'flags-floor'), ['flags-floor', 'flags-floor'])
        self.assertTrue(any('XComLadder_20' in w['message'] for w in report['warnings'] if w['code'] == 'flags-floor'))


if __name__ == '__main__':
    unittest.main()
