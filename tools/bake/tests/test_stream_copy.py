"""A streamed patch copied for a variant without some of its actors (tools/bake/stream_copy.py, step G6), on the LWR
install's patch_bar."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import stream_copy  # noqa: E402
from stream_copy import lighting, native_copy, PL  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# XCOM_PATCH_BAR_UPK, else the LWR install's (tools/viewer/settings.py)
PATCH, NO_PATCH = labpaths.test_file('XCOM_PATCH_BAR_UPK', labpaths.lwr_cooked('patch_bar.upk'), 'patch_bar.upk')


@unittest.skipUnless(PATCH and PATCH.exists(), NO_PATCH)
class StreamCopy(unittest.TestCase):
    def test_the_bars_ladder_helpers_leave_the_copys_level_and_nothing_else_changes(self):
        p = lighting.Package(PATCH)
        before = native_copy.level_actors(p)
        helpers = [p.by_name[PL + n] for n in ('XComLadder_11', 'XComLadder_15')]
        self.assertTrue(all(h in before for h in helpers))
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'patch_bar_URB_Bar_Test_1234.upk'
            report = stream_copy.make(PATCH, dst, ['XComLadder_11', 'XComLadder_15'])
            q = lighting.Package(dst)
            after = native_copy.level_actors(q)
            self.assertEqual(len(q.exports), len(p.exports))
            self.assertEqual(len(after), len(before))
            # the helpers' slots are empty, every other slot as it was; the helpers are still exports, never spawned
            self.assertEqual(after, [0 if a in helpers else a for a in before])
            self.assertEqual([q.cls(h) for h in helpers], ['XComLadder', 'XComLadder'])
            self.assertEqual([h['name'] for h in report['hidden']], ['XComLadder_11', 'XComLadder_15'])

    def test_an_actor_the_patch_lacks_is_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            stream_copy.make(PATCH, Path(d) / 'x.upk', ['XComLadder_999'])


# the bomb stream LWR gives Slaughterhouse, Boulevard, Fast Food and Street Hurricane (mission types plan, Part E)
BOMB, NO_BOMB = labpaths.test_file('XCOM_BOMB_STREAM_UPK', labpaths.lwr_cooked('URB_Slaughterhouse_Stream.upk'),
                                   'URB_Slaughterhouse_Stream.upk')
# a power node's group as export 24 has it (scene_metadata.mission_objects: node:XComLevelActor_6)
NODE = ['XComLevelActor_6', 'XComInteractiveLevelActor_6', 'Emitter_0', 'Emitter_1', 'XComRebuildWorldDataVolume_7']


@unittest.skipUnless(BOMB and BOMB.exists(), NO_BOMB)
class MissionStreamMoves(unittest.TestCase):
    def test_a_power_nodes_group_moves_in_place_and_keeps_every_reference(self):
        p = lighting.Package(BOMB)
        at = {n: p.own(p.by_name[PL + n], 'Location', [0.0, 0.0, 0.0]) for n in NODE}
        turn = {n: p.own(p.by_name[PL + n], 'Rotation') or [0, 0, 0] for n in NODE}
        moves = [dict(actor=n, location=[at[n][0] + 192, at[n][1] - 96, at[n][2] + 64], rotation=list(turn[n])) for n in NODE]
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'URB_Slaughterhouse_Stream_URB_Test_1234.upk'
            report = stream_copy.make(BOMB, dst, [], moves, 'URB_StreetHurricane', 'URB_Test_1234')
            q = lighting.Package(dst)
            # the same exports under the same names; the level lists the same actors; only the group's places change
            self.assertEqual([q.name(i) for i in range(1, len(q.exports) + 1)], [p.name(i) for i in range(1, len(p.exports) + 1)])
            self.assertEqual(native_copy.level_actors(q), native_copy.level_actors(p))
            for n in NODE:
                i = q.by_name[PL + n]
                self.assertEqual([round(v, 3) for v in q.own(i, 'Location')], [round(at[n][0] + 192, 3), round(at[n][1] - 96, 3), round(at[n][2] + 64, 3)], n)
                self.assertEqual(q.own(i, 'Rotation') or [0, 0, 0], list(turn[n]), n)
            # an actor of another group stays where it was
            other = p.by_name[PL + 'XComLevelActor_8']
            self.assertEqual(q.own(other, 'Location'), p.own(other, 'Location'))
            # what points at the group's actors still does: every object property of every export reads the same
            for i in range(1, len(p.exports) + 1):
                if p.cls(i).startswith('SeqVar_Object'):
                    self.assertEqual(q.own(i, 'ObjValue'), p.own(i, 'ObjValue'))
            self.assertEqual([m['actor'] for m in report['moved']], NODE)
            self.assertEqual(report['renamed'], [])         # this stream has no switch on the map's name
        # the node's mesh touches the game's tiles: its box before and after, 192 across, 96 back and 64 up
        boxes = stream_copy.tile_boxes(BOMB, moves)
        self.assertEqual([b['actor'] for b in boxes], ['XComLevelActor_6'])
        b = boxes[0]
        self.assertEqual([round(b['new'][k] - b['old'][k], 2) for k in range(6)], [192, 192, -96, -96, 64, 64])

    def test_an_actor_moved_and_taken_out_is_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            stream_copy.make(BOMB, Path(d) / 'x.upk', ['Emitter_0'], [dict(actor='Emitter_0', location=[0, 0, 0], rotation=[0, 0, 0])])


# Police Station's data recovery stream (EXP-55): the captured encoder saves no Rotation of its own, its archetype
# (ARC_Encoder_CapturePoint) turns it a quarter, as export 24 reads it
CAPTURE, NO_CAPTURE = labpaths.test_file('XCOM_CAPTURE_STREAM_UPK', labpaths.lwr_cooked('URB_PoliceStation_CNH.upk'),
                                         'URB_PoliceStation_CNH.upk')
ENCODER = 'XComCapturePointActor_0'


@unittest.skipUnless(CAPTURE and CAPTURE.exists(), NO_CAPTURE)
class TurnedByItsArchetype(unittest.TestCase):
    def test_an_actor_turned_by_its_archetype_keeps_its_turn_and_its_old_box(self):
        p = lighting.Package(CAPTURE)
        i = p.by_name[PL + ENCODER]
        self.assertIsNone(p.own(i, 'Rotation'))
        turn = [int(v) for v in p.effective(i, 'Rotation')]
        self.assertEqual(turn, [0, -16384, 0])
        at = [float(v) for v in p.effective(i, 'Location')]
        moves = [dict(actor=ENCODER, location=[at[0] + 96, at[1] + 864, at[2]], rotation=turn)]
        with tempfile.TemporaryDirectory() as d:
            report = stream_copy.make(CAPTURE, Path(d) / 'x.upk', [], moves)
            q = lighting.Package(Path(d) / 'x.upk')
            j = q.by_name[PL + ENCODER]
            # the turn it has is its archetype's: the report says so, and the copy leaves it to the archetype
            self.assertEqual(report['moved'][0]['old'], dict(location=at, rotation=turn))
            self.assertIsNone(q.own(j, 'Rotation'))
            self.assertEqual([int(v) for v in q.effective(j, 'Rotation')], turn)
            self.assertEqual([round(v, 3) for v in q.own(j, 'Location')], [round(at[0] + 96, 3), round(at[1] + 864, 3), round(at[2], 3)])
            # a real turn is written
            report = stream_copy.make(CAPTURE, Path(d) / 'y.upk', [], [dict(moves[0], rotation=[0, 0, 0])])
            self.assertEqual(lighting.Package(Path(d) / 'y.upk').own(j, 'Rotation'), [0, 0, 0])
        # the box it leaves is the one it stands in, turned: the move shifts it and nothing else
        b = stream_copy.tile_boxes(CAPTURE, moves)
        self.assertEqual([x['actor'] for x in b], [ENCODER])
        self.assertEqual([round(b[0]['new'][k] - b[0]['old'][k], 2) for k in range(6)], [96, 96, 864, 864, 0, 0])


if __name__ == '__main__':
    unittest.main()
