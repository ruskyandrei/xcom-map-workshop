"""The editor's compiler for static pieces (first-editor plan, slice E3), and the preview of what it compiles."""
import copy
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
from compiler import compile_project, game_round, native_split, short, stream_only, world_box  # noqa: E402
from export_math import multiply, transform, view_matrix  # noqa: E402
from resolver import bounds, resolve_scene  # noqa: E402
from editor_fixtures import (DONOR_SHA, PL, SHA, MissionScenes, add, assembly_scene, codes, document,  # noqa: E402
                             left_out, noted, part, refused, scene, target, warned)

import settings  # noqa: E402
CACHE = Path(os.environ.get('XCOM_VIEWER_CACHE') or settings.configured('cache') or 'no-cache-configured')


def library_scanned():
    """Whether the configured cache holds a library index this version reads (an older one waits for its rescan)."""
    try:
        index = json.loads((CACHE / 'library' / 'index.json').read_text(encoding='utf-8'))
        import library
        return index.get('version') == library.INDEX_VERSION
    except (OSError, ValueError):
        return False
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
# the classes of the static pieces and props the Bar's parity test edits (the first editor's milestone M1)
STATIC_CLASSES = ('XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComCollectible')


def pinned_bar(test, version):
    """The viewer cache's export of the Bar these tests were written on (BAR_SHA), or the test skipped when the cache
    has none: no cache, no URB_Bar, or another install's Bar (review finding 58)."""
    try:
        return compiler.find_export(CACHE, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=version)))[1]
    except compiler.ExportMissing:
        test.skipTest('no export of the URB_Bar these tests pin (SHA-256 %s...) in the viewer cache' % BAR_SHA[:16])


def copies_of(names, serial, move):
    """Added copies of the scene's pieces `names`, each moved by `move` (a function of a source part to a pose)."""
    src = {o['actor']: o for o in assembly_scene()['objects'] if o['layer'] == 'base'}
    out = []
    for k, n in enumerate(names):
        loc, rot = move(src[PL + n])
        out.append(dict(add(n, serial + k, loc, rot)))
    return out


def grid_moved(turns, tiles, storeys=0):
    """A move of a part by `turns` quarter turns about Bar's grid corner (-2784, -1920) and `tiles` (dx, dy) tiles."""
    def move(o):
        ox, oy = -2783.9998, -1920.0
        x, y = compiler.turned((o['location'][0] - ox, o['location'][1] - oy), turns)
        return ([round(x + ox + 96 * tiles[0], 4), round(y + oy + 96 * tiles[1], 4), o['location'][2] + 64 * storeys],
                [o['rotation'][0], o['rotation'][1] + 16384 * turns, o['rotation'][2]])
    return move


def built(report):
    return report['counts']['moved'] + report['counts']['deleted'] + report['counts']['added']


class CompilerTests(MissionScenes, unittest.TestCase):
    def test_a_change_on_a_diagonal_cover_tile_gets_a_note_and_one_beside_it_does_not(self):
        # the map's diagonal cover tiles (export 38, tactical.diagonalCover): a change standing on one (the deleted
        # piece's box, a quarter tile round it) has the Build work the tile out whole (F-155); a tile two away is
        # only written for what the change alters, and not named
        s = scene()
        s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
        corner = s['tileGrid']['origin']
        under = [int((0 - corner[0]) // 96), int((0 - corner[1]) // 96), 0]      # XComLevelActor_1 stands at (0, 0, 0)
        s['tactical'] = dict(floorTiles=[], diagonalCover=[
            dict(tile=under, floor=0.0, location=None, directions=[dict(name='N', toward=[-1, 1], low=False)]),
            dict(tile=[under[0] + 3, under[1], 0], floor=0.0, location=None, directions=[])])
        _, report = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)]), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'diagonal-cover-rewritten'), [])        # a note, not a warning
        note, = [n for n in report['notes'] if n['code'] == 'diagonal-cover-rewritten']
        self.assertEqual(note['tiles'], [under])
        self.assertIn('keeps its diagonal cover while its slanted wall stands', note['message'])
        # a change elsewhere: no note
        _, report = compile_project(document([dict(target=target('XComFracLevelActor_11'), deleted=True)]), s)
        self.assertEqual([n for n in report['notes'] if n['code'] == 'diagonal-cover-rewritten'], [])

    def test_the_projects_diagonal_cover_goes_to_the_build(self):
        # schema 7 (KB-20: diagonal cover placed by hand): a mark's place is a tile's middle, counted from the game's
        # tile corner; a mark's `from` takes the map's own mark there away, and `removed` names the map's marks taken
        # away; marks on one tile join their corners; a mark that can't be read is left out; a mark on a tile with no
        # floor warns; a removed place the map gives no diagonal cover is a note
        from compiler_tables import tile_corner
        s = scene()
        s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
        c = tile_corner(s['tileGrid'])

        def at(t):
            return [c[0] + 96 * (t[0] + 0.5), c[1] + 96 * (t[1] + 0.5), c[2] + 64 * (t[2] + 0.5)]
        own = [[10, 10, 0], [12, 10, 0], [14, 10, 0]]
        s['tactical'] = dict(floorTiles=[dict(tile=t, location=at(t), normal=[0, 0, 1], actor=None)
                                         for t in own + [[12, 11, 0], [20, 20, 0]]],
                             diagonalCover=[dict(tile=t, floor=0.0, location=None, directions=[]) for t in own])
        doc = document([])
        doc['diagonalCover'] = dict(
            marks=[dict(at=at([20, 20, 0]), toward=[[1, 1]]), dict(at=at([20, 20, 0]), toward=[[-1, -1], [1, 1]]),
                   {'at': at([12, 11, 0]), 'toward': [[1, -1]], 'from': at([12, 10, 0])},
                   dict(at=at([14, 10, 0]), toward=[[1, -1]]), dict(at=at([30, 30, 0]), toward=[[1, 1]]),
                   dict(at=[1, 2], toward=[[1, 1]]), dict(at=at([5, 5, 0]), toward=[[2, 0]])],
            removed=[at([10, 10, 0]), at([40, 30, 0])])
        spec, report = compile_project(doc, s)
        self.assertTrue(report['ok'], refused(report))
        lane = spec['diagonalCover']
        self.assertEqual([(m['at'], m['toward']) for m in lane['marks']],
                         [(at([12, 11, 0]), [[1, -1]]), (at([14, 10, 0]), [[1, -1]]),
                          (at([20, 20, 0]), [[-1, -1], [1, 1]]), (at([30, 30, 0]), [[1, 1]])])
        self.assertEqual(lane['removed'], [at([10, 10, 0]), at([12, 10, 0])])
        self.assertEqual(sorted(e['record'] for e in report['leftOut'] if e['code'] == 'diagonal-mark'),
                         ['diagonalCover.marks[5]', 'diagonalCover.marks[6]'])
        no_floor, = [w for w in report['warnings'] if w['code'] == 'diagonal-mark-no-floor']
        self.assertEqual(no_floor['tiles'], [[30, 30, 0]])
        self.assertEqual(noted(report, 'diagonal-removed-unmarked'), ['diagonal-removed-unmarked'])
        # a mark on a tile a streamed level reworks at the battle's start gives no cover in the game (KB-22, export 41):
        # warned, one warning a level; a cleared map streams no patch level (KB-23), so its patch's areas warn of nothing
        s['missions'] = [dict(label='Abduction', streams=['patch_bar']), dict(label='Data recovery', streams=['patch_bar', 'URB_Bar_CNH'])]
        s['streams'] = {'patch_bar': dict(kind='lwr', rebuildSpheres=[dict(actor='V_0', centre=at([20, 20, 0]), radius=150)]),
                        'URB_Bar_CNH': dict(kind='mission', rebuildSpheres=[dict(actor='V_1', centre=at([14, 10, 0]), radius=10)])}
        spec, report = compile_project(doc, s)
        reworked = [w for w in report['warnings'] if w['code'] == 'diagonal-mark-reworked']
        self.assertEqual([(w['stream'], w['tiles']) for w in reworked], [('URB_Bar_CNH', [[14, 10, 0]]), ('patch_bar', [[20, 20, 0]])])
        self.assertIn("Long War's patch_bar reworks at every battle's start (tile (20, 20, 0))", reworked[1]['message'])
        self.assertIn('URB_Bar_CNH (streamed by Data recovery)', reworked[0]['message'])
        self.assertEqual(len(spec['diagonalCover']['marks']), 4)       # (warned, never left out)
        spec, report = compile_project(dict(doc, cleared=True), s)
        self.assertEqual([w['stream'] for w in report['warnings'] if w['code'] == 'diagonal-mark-reworked'], ['URB_Bar_CNH'])
        # a mission object's volume (a bomb's) goes where the project moves it, as the Build moves it in the stream's
        # copy, and with its delete; a record the project drops streams nothing; an added bomb streams its donor's
        volume = PL + 'XComRebuildWorldDataVolume_1'
        s['streams']['URB_Bar_CNH'].update(rebuildSpheres=[dict(actor=volume, centre=at([14, 10, 0]), radius=10)], missionObjects=[
            dict(actor=volume, actorClass='XComRebuildWorldDataVolume', kind='rebuild', location=at([14, 10, 0]), rotation=[0, 0, 0],
                 group='bomb', role='rebuild', referencedBy=[])])
        reworked = lambda r: sorted((w['stream'], w['tiles']) for w in r['warnings'] if w['code'] == 'diagonal-mark-reworked')  # noqa: E731
        stream_target = dict(package='URB_Bar_CNH', level='stream', actor=volume)
        moved = dict(doc, overrides=[dict(target=stream_target, location=at([30, 30, 0]), rotation=[0, 0, 0])])
        _, report = compile_project(moved, s)
        self.assertEqual(reworked(report), [('URB_Bar_CNH', [[30, 30, 0]]), ('patch_bar', [[20, 20, 0]])])
        self.assertIn('bomb mutator places the bomb', next(w['message'] for w in report['warnings'] if w.get('stream') == 'URB_Bar_CNH'))
        _, report = compile_project(dict(doc, overrides=[dict(target=stream_target, deleted=True)]), s)
        self.assertEqual(reworked(report), [('patch_bar', [[20, 20, 0]])])
        s['donors'] = {'Special/Bomb': dict(stream='URB_Slaughterhouse_Stream', missionObjects=[],
                                            rebuildSpheres=[dict(actor=PL + 'XComRebuildWorldDataVolume_9', centre=at([12, 11, 0]), radius=10)])}
        _, report = compile_project(dict(doc, missions=[dict(record=0), dict(kind='Special/Bomb')]), s)
        self.assertEqual(reworked(report), [('URB_Slaughterhouse_Stream', [[12, 11, 0]]), ('patch_bar', [[20, 20, 0]])])
        self.assertIn('URB_Slaughterhouse_Stream (streamed by Council bomb (added))', next(w['message'] for w in report['warnings']
                                                                        if w.get('stream') == 'URB_Slaughterhouse_Stream'))
        s.pop('streams'); s.pop('missions'); s.pop('donors')
        self.assertEqual(report['diagonalCover'], dict(marks=4, removed=2))
        # the Build takes it as the native edit's lane
        self.assertEqual(native_split(spec)[1]['diagonalCover'], lane)
        # none: no lane
        spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)]), s)
        self.assertNotIn('diagonalCover', spec)
        self.assertNotIn('diagonalCover', report)
        # a mark gone with its deleted piece (the page's carried record) takes the map's mark away; a project of schema 7
        # says the page carries the marks (pageCarries: the Build carries none of its own), with marks or none
        doc = document([dict(target=target('XComLevelActor_1'), deleted=True)], schemaVersion=7)
        doc['diagonalCover'] = dict(marks=[{'at': at([14, 10, 0]), 'toward': [[1, 1]], 'from': at([14, 10, 0]),
                                            'by': 'TheWorld.PersistentLevel.XComLevelActor_1', 'gone': True}])
        spec, _ = compile_project(doc, s)
        self.assertEqual(spec['diagonalCover'], dict(marks=[], removed=[at([14, 10, 0])], pageCarries=True))
        doc = document([dict(target=target('XComLevelActor_1'), deleted=True)], schemaVersion=7)
        spec, _ = compile_project(doc, s)
        self.assertEqual(spec['diagonalCover'], dict(pageCarries=True))
        # half cover: a mark's `low` corners go to the lane (joined on one tile as its corners are); a low corner the
        # mark doesn't have, or one that isn't a corner, leaves the mark out
        doc = document([dict(target=target('XComLevelActor_1'), deleted=True)])
        doc['diagonalCover'] = dict(marks=[dict(at=at([20, 20, 0]), toward=[[1, 1]], low=[[1, 1]]),
                                           dict(at=at([20, 20, 0]), toward=[[-1, -1]]),
                                           dict(at=at([21, 20, 0]), toward=[[1, 1]], low=[]),
                                           dict(at=at([22, 20, 0]), toward=[[1, 1]], low=[[-1, -1]]),
                                           dict(at=at([23, 20, 0]), toward=[[1, 1]], low='all')])
        spec, report = compile_project(doc, s)
        self.assertEqual(spec['diagonalCover']['marks'], [dict(at=at([20, 20, 0]), toward=[[-1, -1], [1, 1]], low=[[1, 1]]),
                                                          dict(at=at([21, 20, 0]), toward=[[1, 1]])])
        self.assertEqual(sorted(e['record'] for e in report['leftOut'] if e['code'] == 'diagonal-mark'),
                         ['diagonalCover.marks[3]', 'diagonalCover.marks[4]'])

    def test_a_map_the_game_knows_by_name_gets_a_note(self):
        # mission types plan, Part B: Zhang and the mission's script are tied to Low Friends' name
        s = dict(scene(), name='DLC1_1_LowFriends')
        doc = document([dict(target=target('XComLevelActor_1', package='DLC1_1_LowFriends'), deleted=True)],
                       source=dict(map='DLC1_1_LowFriends', package='DLC1_1_LowFriends.upk', sha256=SHA, exporterVersion=12))
        _, report = compile_project(doc, s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(noted(report, 'named-map'), ['named-map'])
        self.assertIn('Zhang', next(n['message'] for n in report['notes'] if n['code'] == 'named-map'))
        self.assertEqual(warned(report, 'named-map'), [])
        _, report = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)]), scene())
        self.assertEqual(noted(report, 'named-map'), [])

    def test_a_missions_objects_move_in_their_stream(self):
        # mission types plan, Part E: a stream target is moved in the stream's copy (streamMoves), its group checked as
        # one, its floor checked where it stands now
        s, at = self.mission_scene()
        stream = lambda actor: dict(package='URB_Bar_CNH', level='stream', actor=PL + actor)  # noqa: E731
        volume = s['streams']['URB_Bar_CNH']['missionObjects'][4]
        s['streams']['URB_Bar_CNH']['missionObjects'].append(dict(volume, actor=PL + 'XComCapturePointActor_0', actorClass='XComCapturePointActor',
                                                                  kind='capturePoint', role='actor', box=None))
        there = at(12, 10)
        moves = [dict(target=stream('XComSpawnPoint_1'), location=at(21, 20), rotation=[0, 16384, 0]),
                 dict(target=stream('XComCapturePointVolume_0'), location=[there[0], there[1], 0.0], rotation=[0, 0, 0])]
        spec, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)] + moves), s)
        self.assertTrue(report['ok'], refused(report))
        _, native = native_split(stream_only(spec))
        got = native['streamMoves']['URB_Bar_CNH']
        self.assertEqual([m['actor'] for m in got], ['XComCapturePointVolume_0', 'XComSpawnPoint_1'])
        self.assertEqual(got[1]['location'], at(21, 20))
        self.assertEqual(got[1]['rotation'], [0, 16384, 0])
        self.assertEqual(got[1]['old']['location'], at(20, 20))
        # the capture point's actor stayed behind: its group was not moved as one
        self.assertEqual(warned(report, 'mission-group-split'), ['mission-group-split'])
        moves.append(dict(target=stream('XComCapturePointActor_0'), location=[there[0], there[1], 0.0], rotation=[0, 0, 0]))
        spec, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)] + moves), s)
        self.assertEqual(warned(report, 'mission-group-split'), [])
        # moved over no floor: the floor where it stands now is checked
        s['tactical']['floorTiles'] = [f for f in s['tactical']['floorTiles'] if f['tile'][:2] != [21, 20]]
        _, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)] + moves), s)
        self.assertIn('XComSpawnPoint_1', ' '.join(w['message'] for w in report['warnings'] if w['code'] == 'mission-object'))
        # not a mission object, not a mission stream, malformed: errors; a delete: taken out of the copy, warned
        for bad, code in ((dict(target=stream('XComLevelActor_9'), location=at(1, 1), rotation=[0, 0, 0]), 'stream-actor'),
                          (dict(target=dict(stream('XComSpawnPoint_1'), package='patch_bar'), location=at(1, 1), rotation=[0, 0, 0]), 'stream'),
                          (dict(target=stream('XComSpawnPoint_1'), location=at(1, 1), rotation=[0, 0.5, 0]), 'malformed')):
            _, report = compile_project(document([bad]), s)
            self.assertEqual(codes(report), [code], bad)
        spec, report = compile_project(document([dict(target=stream('XComRadarArrayActor_0'), deleted=True)]), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission-object-deleted'), ['mission-object-deleted'])
        self.assertEqual(native_split(stream_only(spec))[1]['streamHides'], {'URB_Bar_CNH': ['XComRadarArrayActor_0']})

    def test_the_bombs_helper_point_moves_with_the_bomb(self):
        # export 33 (spawns plan SP3, F-124): the PointInSpace beside the bomb is in its group; a move that leaves it
        # behind splits the group, one that takes it along is accepted whole
        s, at = self.mission_scene()
        b = at(15, 15, 0.0)
        obj = lambda actor, cls, kind, role, where: dict(actor=PL + actor, actorClass=cls, kind=kind, location=where, rotation=[0, 0, 0],  # noqa: E731
                                                         archetype=None, tag=None, unitType=None, box=None, referencedBy=[],
                                                         group='bomb', role=role)
        s['missions'][1] = dict(type='Special', label='Council bomb', group='council', display='', streams=['URB_Bar_CNH'])
        s['streams']['URB_Bar_CNH']['missionObjects'] += [
            obj('XComLevelActor_50', 'XComLevelActor', 'bomb', 'bomb', b),
            obj('XComInteractiveLevelActor_50', 'XComInteractiveLevelActor', 'use', 'button', b),
            obj('PointInSpace_0', 'PointInSpace', 'part', 'point', [b[0] + 2.5, b[1], b[2] + 204.5])]
        stream = lambda actor: dict(package='URB_Bar_CNH', level='stream', actor=PL + actor)  # noqa: E731
        shift = lambda where: [where[0] + 288, where[1], where[2]]  # noqa: E731
        moves = [dict(target=stream('XComLevelActor_50'), location=shift(b), rotation=[0, 0, 0]),
                 dict(target=stream('XComInteractiveLevelActor_50'), location=shift(b), rotation=[0, 0, 0])]
        _, report = compile_project(document(moves), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission-group-split'), ['mission-group-split'])
        moves.append(dict(target=stream('PointInSpace_0'), location=shift([b[0] + 2.5, b[1], b[2] + 204.5]), rotation=[0, 0, 0]))
        spec, report = compile_project(document(moves), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission-group-split'), [])
        got = native_split(stream_only(spec))[1]['streamMoves']['URB_Bar_CNH']
        self.assertIn('PointInSpace_0', [m['actor'] for m in got])

    def donor_scene(self):
        """mission_scene with the bomb donor's objects (export 33's `donors`): the bomb at Slaughterhouse's place, off
        this map's grid, and a power node over a floor tile of the map."""
        s, at = self.mission_scene()
        node = at(5, 5)
        obj = lambda actor, cls, kind, role, group, where: dict(actor=PL + actor, actorClass=cls, kind=kind, location=where,  # noqa: E731
                                                                rotation=[0, 0, 0], archetype=None, tag=None, unitType=None, box=None,
                                                                referencedBy=[], group=group, role=role)
        s['donors'] = {'Special/Bomb': dict(stream='URB_Slaughterhouse_Stream', package='URB_Slaughterhouse_Stream.upk', missionObjects=[
            obj('XComLevelActor_11', 'XComLevelActor', 'bomb', 'bomb', 'bomb', [-90000.0, 1872.0, 68.0]),
            obj('PointInSpace_0', 'PointInSpace', 'part', 'point', 'bomb', [-89997.5, 1872.0, 272.5]),
            obj('XComLevelActor_6', 'XComLevelActor', 'powerNode', 'node', 'node:XComLevelActor_6', node)])}
        return s, at

    def test_an_added_bombs_objects_are_moved_in_the_donor_stream_and_checked(self):
        # spawns plan SP4: the added bomb's objects come from Slaughterhouse's stream (scene.donors); a move of them
        # needs the kind in the project's missions; left at the donor's own place they are warned of where that place
        # is off this map's grid, over no floor or inside a piece
        s, at = self.donor_scene()
        donor = lambda actor: dict(package='URB_Slaughterhouse_Stream', level='stream', actor=PL + actor)  # noqa: E731
        bomb_mission = [dict(record=0), dict(kind='Special/Bomb')]
        _, report = compile_project(document(missions=bomb_mission), s)
        self.assertTrue(report['ok'], refused(report))
        placed = [w for w in report['warnings'] if w['code'] == 'mission-donor-place']
        self.assertEqual([w['actor'].rsplit('.', 1)[-1] for w in placed], ['XComLevelActor_11'])
        self.assertIn('off the map\'s grid', placed[0]['message'])
        self.assertEqual((placed[0]['mission'], placed[0]['missionKind'], placed[0]['stream']),
                         ('Council bomb (added)', 'Special/Bomb', 'URB_Slaughterhouse_Stream'))
        # the bomb moved onto the map with its helper: accepted, in the stream's moves, no warning of its place
        there = at(12, 12, 0.0)
        moves = [dict(target=donor('XComLevelActor_11'), location=there, rotation=[0, 0, 0]),
                 dict(target=donor('PointInSpace_0'), location=[there[0] + 2.5, there[1], 204.5], rotation=[0, 0, 0])]
        spec, report = compile_project(document(moves, missions=bomb_mission), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission-donor-place'), [])
        self.assertEqual(warned(report, 'mission-group-split'), [])
        got = native_split(stream_only(spec))[1]['streamMoves']['URB_Slaughterhouse_Stream']
        self.assertEqual(sorted(m['actor'] for m in got), ['PointInSpace_0', 'XComLevelActor_11'])
        # a node's floor taken by the edit: the node's place is checked on this map too (a warning)
        s['tactical']['floorTiles'] = [f for f in s['tactical']['floorTiles'] if f['tile'][:2] != [5, 5]]
        _, report = compile_project(document(moves, missions=bomb_mission), s)
        self.assertIn('over no floor', ' '.join(w['message'] for w in report['warnings'] if w['code'] == 'mission-donor-place'))
        # the donor's objects moved by a project that adds no bomb: an error that says so
        _, report = compile_project(document(moves), s)
        self.assertEqual(sorted(set(codes(report))), ['stream-donor'])

    def test_the_drop_in_rule_is_checked_passed_on_and_says_what_it_covers(self):
        # spawns plan SP8: spawnRules {"dropIns": "placed"} or nothing; it is work of its own, goes to the Build's
        # native edit and the report, and a note counts the scripted actions it covers (export 33's uses) over the map
        # and the kept missions' streams; anything else is refused
        s, at = self.spawn_scene()
        use = lambda by: dict(how='direct', by=by, byClass='SeqAct_SpawnAlien')  # noqa: E731
        s['spawns'].append(dict(actor=PL + 'XComSpawnPoint_Alien_3', actorClass='XComSpawnPoint_Alien', kind='dropIn',
                                location=at(5, 5), rotation=[0, 0, 0], values={},
                                uses=[use('Main_Sequence.SeqAct_SpawnAlien_1'),
                                      dict(how='indirect', by='Main_Sequence.SeqAct_AccessObjectList_0',
                                           then=['Main_Sequence.SeqAct_SpawnAlien_2', 'Main_Sequence.SeqAct_SpawnAlien_1'])]))
        s['streams']['URB_Bar_CNH']['missionObjects'][2]['uses'] = [use('Stream_Sequence.SeqAct_SpawnAlien_0')]
        spec, report = compile_project(document(spawnRules=dict(dropIns='placed')), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['spawnRules'], dict(dropIns='placed'))
        self.assertEqual(native_split(spec)[1]['spawnRules'], dict(dropIns='placed'))
        note = next(n for n in report['notes'] if n['code'] == 'dropins-placed')
        self.assertEqual((note['actions'], note['missions']), (3, ['Abduction', 'Data recovery']))
        self.assertIn('3 scripted actions in URB_Bar_CNH, the map', note['message'])
        self.assertIn('URB_Bar_BarRemix_5005', note['message'])
        # one mission kept: its stream alone is counted with the map
        _, report = compile_project(document(spawnRules=dict(dropIns='placed'), missions=[dict(record=0)]), s)
        note = next(n for n in report['notes'] if n['code'] == 'dropins-placed')
        self.assertEqual((note['actions'], note['missions']), (2, ['Abduction']))
        # not a rule this editor knows: left out (refused until review finding 39), the drop-ins as the install has them
        for bad in (dict(dropIns='install'), dict(dropIns='placed', waves='placed'), 'placed', []):
            spec, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)], spawnRules=bad), s)
            self.assertEqual(codes(report), ['spawn-rules'], bad)
            self.assertTrue(report['ok'], bad)
            self.assertEqual((report['spawnRules'], native_split(spec)[1].get('spawnRules')), (None, None))
        # none: no note, nothing passed on
        spec, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)]), s)
        self.assertEqual((noted(report, 'dropins'), report['spawnRules'], native_split(spec)[1].get('spawnRules')), ([], None, None))

    def test_what_long_war_rebalance_is_told_of_the_map(self):
        # schema 6's lwrMapInfo (Map settings' Long War Rebalance section; LWR 3.00.00 beta 17's map info): the
        # compiler's reading of it goes to the Build in the report, and the spec is the same without it
        s = scene()
        plain, _ = compile_project(document(), s)
        for info, want in ((dict(alienDensity='Moderate'), dict(alienDensity='Moderate')),
                           (dict(holdTheLine='No', alienDensity='Swarming'), dict(alienDensity='Swarming', holdTheLine='No')),
                           (dict(holdTheLine='Yes'), dict(holdTheLine='Yes'))):
            spec, report = compile_project(document(lwrMapInfo=info), s)
            self.assertTrue(report['ok'], refused(report))
            self.assertEqual(report['lwrMapInfo'], want)
            self.assertEqual(list(report['lwrMapInfo']), [k for k in ('alienDensity', 'holdTheLine') if k in want])
            self.assertEqual(spec, plain)
            self.assertEqual([n['code'] for n in report['notes'] if n['code'].startswith('lwr')], ['lwr-map-info-set'])
        note = next(n for n in report['notes'] if n['code'] == 'lwr-map-info-set')
        self.assertIn('Long War Rebalance 3.00.00 beta 17', note['message'])
        # none, null or empty: nothing told, no note
        for doc in (document(), document(lwrMapInfo=None), document(lwrMapInfo={})):
            _, report = compile_project(doc, s)
            self.assertEqual((report['lwrMapInfo'], noted(report, 'lwr')), (None, []))
        # a key or a value this editor doesn't know: left out whole, and the rest of the project builds
        for bad in (dict(alienDensity='Huge'), dict(alienDensity='moderate'), dict(holdTheLine=False),
                    dict(alienDensity='Light', weather='Rain'), 'Moderate', ['Moderate']):
            _, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)], lwrMapInfo=bad), s)
            self.assertEqual(codes(report), ['lwr-map-info'], bad)
            self.assertTrue(report['ok'], bad)
            self.assertIsNone(report['lwrMapInfo'])

    def test_a_map_long_war_excludes_says_its_variant_is_not(self):
        # spawns plan SP8: the install's ExcludeMaps names the base map (the Chryssalid Hive's case): with no rule, a note
        # that the variant, under its own name, gets the drop-in mutator
        s, _ = self.spawn_scene()
        game = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, game, True)
        cfg = game / 'XEW/XComGame/Config'
        cfg.mkdir(parents=True)
        (cfg / 'DefaultMutatorLoader.ini').write_bytes(b'[XComMutator.XComMutatorLoader]\r\narrTacticalMutators="XComLZMutator.XComSpawnAlienMutator"\r\n')
        (cfg / 'DefaultRandomSpawns.ini').write_bytes(b'[XComLZMutator.XComSpawnAlienMutator]\r\nExcludeMaps = "URB_Bar"\r\n')
        library = compiler.Library(str(game), str(game))
        edit = [dict(target=target('XComLevelActor_2'), deleted=True)]
        _, report = compile_project(document(edit), s, (), library)
        self.assertEqual(noted(report, 'dropins'), ['dropins-base-excluded'])
        _, report = compile_project(document(edit, spawnRules=dict(dropIns='placed')), s, (), library)
        self.assertEqual(noted(report, 'dropins'), ['dropins-placed'])
        (cfg / 'DefaultRandomSpawns.ini').write_bytes(b'[XComLZMutator.XComSpawnAlienMutator]\r\nExcludeMaps = "EWI_ChryssalidHive"\r\n')
        _, report = compile_project(document(edit), s, (), library)
        self.assertEqual(noted(report, 'dropins'), [])

    def test_base_spawn_points_moved_and_given_values_where_the_spawn_family_builds(self):
        # spawns plan SP6: a base pod, Meld point or drop-in point moves, turns and takes the values of its kind, in
        # place (the native `spawns` lane, with no patch); off while the spawn family doesn't build
        s, at = self.spawn_scene()
        s['spawns'][0]['links'] = [dict(property='PathNode', actor=PL + 'XComAlienPathNode_4')]
        s['spawns'].append(dict(actor=PL + 'XComSpawnPoint_Alien_3', actorClass='XComSpawnPoint_Alien', kind='dropIn',
                                location=at(5, 5), rotation=[0, 0, 0], values={}))
        s['spawns'].append(dict(actor=PL + 'XComSpawnPoint_18', actorClass='XComSpawnPoint', kind='soldier',
                                location=at(6, 6), rotation=[0, 0, 0], values={}))
        pod = s['spawns'][0]
        edits = [dict(target=target('XComAlienPod_0'), location=[pod['location'][0] + 96, *pod['location'][1:]], rotation=[0, 16384, 0]),
                 dict(target=target('XComAlienPod_1'), spawn=dict(commander=True)),
                 dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(difficulty='Hard', destroyedOnTurn=6, spawnGroup=0)),
                 dict(target=target('XComSpawnPoint_Alien_3'), location=at(7, 5), rotation=[0, -16384, 0])]
        # (the family builds since EXP-72 runs 6 to 8; its gate still refuses where it is off)
        with mock.patch.dict(compiler.FAMILIES['spawn'], builds=False):
            _, report = compile_project(document(edits), s)
        self.assertEqual(sorted(set(codes(report))), ['family'])
        self.assertEqual(len(codes(report)), 4)
        spec, report = compile_project(document(edits), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['counts']['spawns'], dict(moved=2, valued=2, added=0, deleted=0))
        patch, native = native_split(spec)
        self.assertFalse(any(o.get('type') == 'spawns' for o in patch['objects']))
        lane = native['spawns']
        self.assertEqual([m['name'] for m in lane['moves']], ['XComAlienPod_0', 'XComSpawnPoint_Alien_3'])
        self.assertEqual(lane['moves'][0]['rotation'], [0, 16384, 0])
        self.assertEqual(lane['moves'][0]['before']['location'], pod['location'])
        # a value the map already has builds nothing (the Meld point's spawn group)
        self.assertEqual([(v['name'], v['spawn']) for v in lane['values']],
                         [('XComAlienPod_1', dict(commander=True)), ('XComMeldContainerSpawnPoint_1', dict(destroyedOnTurn=6, difficulty='Hard'))])
        self.assertEqual((lane['copies'], lane['deletes']), ([], []))
        # the pod's link to its path node stays where the map has it: a note says so
        self.assertIn('its PathNode XComAlienPathNode_4', next(n for n in report['notes'] if n['code'] == 'spawn-links')['message'])
        # refused: another kind's value, a value out of range, a kind the editor shows only, an actor the level
        # doesn't list, one whose values weren't read
        s['spawns'][2]['listed'] = False
        s['spawns'][3]['unread'] = 'bad bytes'
        for rec, code in [(dict(target=target('XComAlienPod_1'), spawn=dict(difficulty='Hard')), 'spawn-values'),
                          (dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(destroyedOnTurn=100)), 'spawn-values'),
                          (dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(difficulty='Medium')), 'spawn-values'),
                          (dict(target=target('XComAlienPod_0'), spawn=dict(use=1)), 'spawn-values'),
                          (dict(target=target('XComSpawnPoint_18'), location=at(9, 9), rotation=[0, 0, 0]), 'spawn-view-only'),
                          (dict(target=target('XComAlienPod_2'), spawn=dict(commander=True)), 'spawn-unlisted'),
                          (dict(target=target('XComMeldContainerSpawnPoint_0'), spawn=dict(spawnGroup=1)), 'spawn-unread')]:
            _, report = compile_project(document([rec]), s, enable=['spawn'])
            self.assertEqual(codes(report), [code], rec)
        # a value of no kind is noted and carried; a spawn point as the map has it builds nothing
        _, report = compile_project(document([dict(target=target('XComAlienPod_0'), spawn=dict(colour='red'))]), s, enable=['spawn'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(noted(report, 'un'), ['unchanged', 'unknown-field'])
        self.assertEqual(report['counts']['spawns'], dict(moved=0, valued=0, added=0, deleted=0))

    def test_base_spawn_points_copied_and_deleted(self):
        # spawns plan SP7: a pod or Meld point copied from a plain template of the map (a pod's copy takes the next pod
        # index no pod of the map or its streams has and no pod event names), a point deleted only when nothing names it
        s, at = self.spawn_scene()
        s['spawns'][1]['uses'] = [dict(how='event', by='Main_Sequence.SeqEvent_OnRevealPod_0', podId=7, staticOnly=False)]
        s['spawns'][1]['values']['commander'] = {'value': True, 'from': 'saved'}
        s['spawns'].append(dict(actor=PL + 'XComSpawnPoint_Alien_3', actorClass='XComSpawnPoint_Alien', kind='dropIn',
                                location=at(5, 5), rotation=[0, 0, 0], values={},
                                uses=[dict(how='direct', by='Main_Sequence.SeqAct_SpawnAlien_1', byClass='SeqAct_SpawnAlien')]))
        s['streams']['URB_Bar_CNH']['missionObjects'].append(dict(actor=PL + 'XComAlienPod_9', actorClass='XComAlienPod', kind='pod',
                                                                  location=at(1, 1), values={'podIndex': {'value': 9, 'from': 'saved'}}))
        copy = lambda n, src, kind, where, **extra: dict(id='c%d' % n, kind=kind, actor=PL + '%s_copy%d' % (src, n),  # noqa: E731
                                                         **{'from': target(src)}, location=where, rotation=[0, 0, 0], **extra)
        added = [copy(1, 'XComAlienPod_0', 'pod', at(12, 12, 17.0)), copy(2, 'XComAlienPod_2', 'pod', at(31, 31, 17.0), spawn=dict(use=False)),
                 copy(3, 'XComMeldContainerSpawnPoint_1', 'meld', at(26, 6, 17.0), spawn=dict(difficulty='Hard', spawnGroup=0))]
        gone = [dict(target=target('XComAlienPod_2'), deleted=True), dict(target=target('XComAlienPod_1'), deleted=True),
                dict(target=target('XComSpawnPoint_Alien_3'), deleted=True)]
        with mock.patch.dict(compiler.FAMILIES['spawn'], builds=False):
            _, report = compile_project(document(gone, added=added), s)
        self.assertEqual(sorted(set(codes(report))), ['family'])
        spec, report = compile_project(document(gone, added=added), s)
        self.assertTrue(report['ok'], refused(report))
        lane = native_split(spec)[1]['spawns']
        # above the stream's pod 9 (the map's are 0 to 2, an event names 7): 10 and 11, in the document's order
        self.assertEqual([(c['name'], c['source'], c.get('podIndex'), c.get('spawn')) for c in lane['copies']],
                         [('XComAlienPod_0_copy1', 'XComAlienPod_0', 10, None), ('XComAlienPod_2_copy2', 'XComAlienPod_2', 11, dict(use=False)),
                          ('XComMeldContainerSpawnPoint_1_copy3', 'XComMeldContainerSpawnPoint_1', None, dict(difficulty='Hard'))])
        # the delete of the pod nothing names is built; the pod an event names and the drop-in the Kismet uses stay
        self.assertEqual([d['name'] for d in lane['deletes']], ['XComAlienPod_2'])
        named = sorted(w['actor'] for w in report['warnings'] if w['code'] == 'spawn-delete-named')
        self.assertEqual(named, [PL + 'XComAlienPod_1', PL + 'XComSpawnPoint_Alien_3'])
        msg = next(w['message'] for w in report['warnings'] if w['actor'] == PL + 'XComAlienPod_1')
        self.assertIn('SeqEvent_OnRevealPod_0 (a pod event for its index)', msg)
        self.assertEqual(report['counts']['spawns'], dict(moved=0, valued=0, added=3, deleted=1))
        # SP5's count: two pods copied onto floor make up for the one deleted (no pod place lost)
        self.assertEqual(warned(report, 'spawn-pod'), [])
        # refused: a template that isn't plain, one of another kind, a drop-in copied, a template the export lacks
        for rec, code in [(copy(4, 'XComAlienPod_1', 'pod', at(12, 12, 17.0)), 'spawn-copy-template'),
                          (copy(5, 'XComAlienPod_0', 'meld', at(12, 12, 17.0)), 'malformed'),
                          (copy(6, 'XComMeldContainerSpawnPoint_0', 'meld', at(12, 12, 17.0), spawn=dict(commander=True)), 'spawn-values'),
                          (copy(7, 'XComAlienPod_77', 'pod', at(12, 12, 17.0)), 'missing'),
                          (dict(copy(8, 'XComAlienPod_0', 'pod', at(12, 12, 17.0)), id=''), 'malformed')]:
            _, report = compile_project(document(added=[rec]), s, enable=['spawn'])
            self.assertEqual(codes(report), [code], rec)
        # a drop-in point is no kind a project copies: its record goes to the effects' copier, which refuses it
        _, report = compile_project(document(added=[copy(9, 'XComSpawnPoint_Alien_3', 'dropIn', at(12, 12, 17.0))]), s, enable=['spawn'])
        self.assertEqual(codes(report), ['malformed'])
        # a pod deleted where the export could not read its uses stays too
        s['spawns'][0]['unread'] = 'bad bytes'
        _, report = compile_project(document([dict(target=target('XComAlienPod_0'), deleted=True)]), s, enable=['spawn'])
        self.assertEqual(warned(report, 'spawn-delete'), ['spawn-delete-named'])
        # on a cleared map it stays the same, said in a note (the clear cuts the map's script off from its triggers)
        _, report = compile_project(document([dict(target=target('XComAlienPod_0'), deleted=True)], cleared=True), s, enable=['spawn'])
        self.assertEqual((warned(report, 'spawn-delete'), noted(report, 'spawn-delete')), ([], ['spawn-delete-named']))
        # (the Triggers part's: with the lights alone cleared, still a warning)
        _, report = compile_project(document([dict(target=target('XComAlienPod_0'), deleted=True)], cleared={'lights': {}}), s, enable=['spawn'])
        self.assertEqual(warned(report, 'spawn-delete'), ['spawn-delete-named'])

    def test_no_spawn_volumes_are_sized_given_values_copied_made_and_deleted(self):
        # a no-spawn volume (export 34: its aliens and civilians switches) moves and is sized by its box, in place; a
        # copy of one, or a new one made from one of the map's plain volumes (no `from`), is placed by its box alone;
        # it is deleted as a point is; a pose, an empty box or a box on a point is refused
        s, at = self.spawn_scene()
        s['spawns'].append(dict(actor=PL + 'XComNoSpawnVolume_0', actorClass='XComNoSpawnVolume', kind='noSpawn',
                                location=[-384.0, -480.0, 96.0], rotation=[0, 0, 0], listed=True,
                                box=dict(min=[-864.0, -576.0, 0.0], max=[-384.0, -384.0, 256.0]),
                                values={'aliens': {'value': True, 'from': 'class'}, 'civilians': {'value': True, 'from': 'class'}}))
        s['spawns'].append(dict(actor=PL + 'XComNoSpawnVolume_2', actorClass='XComNoSpawnVolume', kind='noSpawn',
                                location=[0.0, 0.0, 96.0], rotation=[0, 0, 0], listed=True,
                                box=dict(min=[0.0, 0.0, 0.0], max=[192.0, 192.0, 256.0]), values={}))
        box = [-864.0, -576.0, 0.0, -192.0, -384.0, 320.0]
        edits = [dict(target=target('XComNoSpawnVolume_0'), box=box, spawn=dict(civilians=False, aliens=True)),
                 dict(target=target('XComNoSpawnVolume_2'), deleted=True)]
        added = [dict(id='v1', kind='noSpawn', actor=PL + 'XComNoSpawnVolume_0_copy1', **{'from': target('XComNoSpawnVolume_0')},
                      box=[96.0, 96.0, 0.0, 288.0, 288.0, 256.0]),
                 dict(id='v2', kind='noSpawn', actor=PL + 'XComNoSpawnVolume_copy2', box=[384.0, 384.0, 0.0, 672.0, 672.0, 256.0],
                      spawn=dict(aliens=False))]
        with mock.patch.dict(compiler.FAMILIES['spawn'], builds=False):
            _, report = compile_project(document(edits, added=added), s)
        self.assertEqual(sorted(set(codes(report))), ['family'])
        spec, report = compile_project(document(edits, added=added), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['counts']['spawns'], dict(moved=1, valued=1, added=2, deleted=1))
        lane = native_split(spec)[1]['spawns']
        self.assertEqual([(m['name'], m['box'], m['before']['box']) for m in lane['moves']],
                         [('XComNoSpawnVolume_0', box, [-864.0, -576.0, 0.0, -384.0, -384.0, 256.0])])
        self.assertNotIn('location', lane['moves'][0])
        # (aliens: true is the map's own value already)
        self.assertEqual([(v['name'], v['spawn']) for v in lane['values']], [('XComNoSpawnVolume_0', dict(civilians=False))])
        self.assertEqual([(c['name'], c['source'], c['box'], c.get('spawn')) for c in lane['copies']],
                         [('XComNoSpawnVolume_0_copy1', 'XComNoSpawnVolume_0', [96.0, 96.0, 0.0, 288.0, 288.0, 256.0], None),
                          ('XComNoSpawnVolume_copy2', None, [384.0, 384.0, 0.0, 672.0, 672.0, 256.0], dict(aliens=False))])
        self.assertEqual([d['name'] for d in lane['deletes']], ['XComNoSpawnVolume_2'])
        # a volume never counts as a pod place
        self.assertEqual(warned(report, 'spawn-pod'), [])
        # refused: a pose on a volume, a box on a pod, an empty box, a value of no volume, a copy with a pose, a copy of
        # a pod that says it is a volume
        for rec, code in [(dict(target=target('XComNoSpawnVolume_0'), location=[0, 0, 0], rotation=[0, 0, 0]), 'malformed'),
                          (dict(target=target('XComAlienPod_0'), box=box), 'malformed'),
                          (dict(target=target('XComNoSpawnVolume_0'), box=[0, 0, 0, 0, 96, 64]), 'malformed'),
                          (dict(target=target('XComNoSpawnVolume_0'), spawn=dict(use=True)), 'spawn-values'),
                          (dict(target=target('XComNoSpawnVolume_0'), spawn=dict(aliens='yes')), 'spawn-values')]:
            _, report = compile_project(document([rec]), s, enable=['spawn'])
            self.assertEqual(codes(report), [code], rec)
        for rec, code in [(dict(added[1], location=[0, 0, 0], rotation=[0, 0, 0]), 'malformed'),
                          (dict(added[0], **{'from': target('XComAlienPod_0')}), 'malformed'),
                          (dict(added[1], box=[0, 0, 0, 96, 96]), 'malformed')]:
            _, report = compile_project(document(added=[rec]), s, enable=['spawn'])
            self.assertEqual(codes(report), [code], rec)

    def test_pod_places_and_meld_groups_are_counted_against_the_edit(self):
        # spawns plan SP5: a pod or Meld point's place is usable in the grid, over floor that stays or is added, and in
        # no solid piece of the project; fewer pod places, or a Meld group without its hard points or any point, is
        # a warning that names the first point lost; points a resized grid leaves outside, a note
        s, at = self.spawn_scene()
        spawn_codes = lambda report: warned(report, 'spawn-') + noted(report, 'spawn-')  # noqa: E731
        _, report = compile_project(document(), s)
        self.assertEqual(spawn_codes(report), [])
        # XComLevelActor_1's floor tile goes, with the first pod's place and the hard point's
        gone = [dict(target=target('XComLevelActor_1'), deleted=True)]
        _, report = compile_project(document(gone), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spawn_codes(report), ['spawn-meld-group', 'spawn-pod-places'])
        pods = next(w for w in report['warnings'] if w['code'] == 'spawn-pod-places')
        self.assertEqual((pods['before'], pods['now'], pods['actor']), (3, 2, PL + 'XComAlienPod_0'))
        self.assertEqual(pods['mission'], 'Every mission of the variant')
        self.assertTrue(pods['message'].startswith('Every mission of the variant: 2 of the map'), pods['message'])
        meld = next(w for w in report['warnings'] if w['code'] == 'spawn-meld-group')
        self.assertIn('hard points', meld['message'])
        self.assertEqual(meld['actor'], PL + 'XComMeldContainerSpawnPoint_0')
        # one mission kept: the warnings name it
        _, report = compile_project(document(gone, missions=[dict(record=1)]), s)
        self.assertEqual({w['mission'] for w in report['warnings'] if w['code'].startswith('spawn-')}, {'Data recovery'})
        # a piece of the project over the second pod: its place is lost too
        _, report = compile_project(document(added=[add('XComLevelActor_2', 0, at(15, 15, 0.0))]), s)
        pods = next(w for w in report['warnings'] if w['code'] == 'spawn-pod-places')
        self.assertEqual((pods['before'], pods['now'], pods['actor']), (3, 2, PL + 'XComAlienPod_1'))
        # every floor tile the deleted piece's (a cleared map's): no pod place left, the Meld group has no point
        s2, _ = self.spawn_scene()
        for f in s2['tactical']['floorTiles']:
            f['actor'] = PL + 'XComLevelActor_1'
        _, report = compile_project(document(gone), s2)
        pods = next(w for w in report['warnings'] if w['code'] == 'spawn-pod-places')
        self.assertEqual((pods['before'], pods['now']), (3, 0))
        self.assertIn('none of its 2 usable points', next(w['message'] for w in report['warnings'] if w['code'] == 'spawn-meld-group'))
        # a cleared map's grid shrunk past the third pod and the easy point: they are outside (a note) and the pod's
        # place is lost
        _, report = compile_project(document(cleared=True, stage={'grid': [20, 20]}), s)
        self.assertTrue(report['ok'], refused(report))
        out = next(n for n in report['notes'] if n['code'] == 'spawn-outside')
        self.assertTrue(out['message'].startswith('1 pod and 1 Meld point of the map stand outside'), out['message'])
        self.assertEqual(out['count'], 2)
        pods = next(w for w in report['warnings'] if w['code'] == 'spawn-pod-places')
        self.assertEqual((pods['before'], pods['now'], pods['actor']), (3, 2, PL + 'XComAlienPod_2'))
        # the Meld group keeps its hard point: no Meld warning
        self.assertEqual(warned(report, 'spawn-meld'), [])

    def test_a_missions_objects_warn_when_the_edit_takes_their_floor_or_covers_them(self):
        # mission types plan, C3: warnings only, each naming its mission; the drop-in only a note
        s, at = self.mission_scene()
        vip = at(20, 20)
        doc = document([dict(target=target('XComLevelActor_1'), deleted=True)],
                       added=[add('XComLevelActor_2', 0, [vip[0], vip[1], 0])])
        _, report = compile_project(doc, s)
        self.assertTrue(report['ok'], refused(report))
        mine = [w for w in report['warnings'] if w['code'].startswith('mission-')]
        self.assertEqual(sorted((w['code'], w['actor'].rsplit('.', 1)[-1]) for w in mine),
                         [('mission-capture', 'XComCapturePointVolume_0'), ('mission-object', 'XComSpawnPoint_0'),
                          ('mission-object', 'XComSpawnPoint_1')])
        self.assertTrue(all((w['mission'], w['missionIndex'], w['stream']) == ('Data recovery', 1, 'URB_Bar_CNH') for w in mine))
        self.assertIn('the covert operative\'s point (XComSpawnPoint_0) has no floor under it now', next(w['message'] for w in mine if w['actor'].endswith('_0') and w['code'] == 'mission-object'))
        self.assertIn('is inside XComLevelActor_2_copy0', next(w['message'] for w in mine if w['actor'].endswith('_1')))
        self.assertEqual(noted(report, 'mission-'), ['mission-spawns'])
        # a variant that keeps only the abduction: nothing to say of the data recovery's objects
        _, report = compile_project(dict(doc, missions=[dict(record=0)]), s)
        self.assertEqual(warned(report, 'mission-') + noted(report, 'mission-'), [])
        # an edit that leaves their floor alone: no warning
        _, report = compile_project(document([dict(target=target('XComLevelActor_2'), deleted=True)]), s)
        self.assertEqual(warned(report, 'mission-'), [])

    def test_the_projects_missions_list_is_checked(self):
        # mission types plan, D1: an entry the Build can't write is left out, and a list that keeps none is as no list:
        # every record (an error until review finding 39); a UFO mission wants a UFO building
        s, _ = self.mission_scene()
        base = [dict(target=target('XComLevelActor_2'), deleted=True)]
        for bad in ([], 'all', [dict(record=2)], [dict(kind='Crash')], [dict(kind='TerrorSite', ship='eShip_UFOSmallScout')]):
            _, report = compile_project(document(base, missions=bad), s)
            self.assertEqual(codes(report), ['missions'], bad)
            self.assertTrue(report['ok'], bad)
            self.assertIsNone(report['missions'], bad)
            self.assertEqual(noted(report, 'missions-all'), ['missions-all'], bad)
        _, report = compile_project(document(base, missions=[dict(record=2), dict(record=0)]), s)
        self.assertEqual(([d['record'] for d in report['leftOut']], report['missions']), (['missions[0]'], [dict(record=0)]))
        _, report = compile_project(document(base, missions=[dict(record=1), dict(kind='Crash', ship='eShip_UFOSmallScout'),
                                                             dict(kind='Special/Bomb')]), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission-ufo'), ['mission-ufo'])
        self.assertEqual(noted(report, 'mission-bomb'), ['mission-bomb'])
        s['buildings'] = s['buildings'] + [dict(id='9', name=PL + 'XComBuildingVolume_9', actor='XComBuildingVolume_9', isUfo=True, floors=[])]
        _, report = compile_project(document(base, missions=[dict(kind='LandedUFO', ship='eShip_UFOAbductor')]), s)
        self.assertEqual(warned(report, 'mission-ufo'), [])

    def test_a_move_is_a_copy_then_an_exact_hide(self):
        spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), location=[10, 20, 30],
                                                      rotation=[0, 16384.4, 0])]), scene())
        self.assertTrue(report['ok'], refused(report))
        copy_op, hide = spec['objects']
        self.assertEqual(copy_op['type'], 'copy')
        self.assertEqual(copy_op['from'], ['XComLevelActor_1'])
        self.assertEqual(copy_op['poses'], [dict(location=[10, 20, 30], rotation=[0, 16384, 0])])
        self.assertEqual(copy_op['labels'], ['move:XComLevelActor_1'])
        self.assertEqual(hide, dict(type='hide', exact=True, location=hide['location'], alsoHide=['XComLevelActor_1'],
                                    labels=['move:XComLevelActor_1'], boxes=hide['boxes']))
        self.assertEqual(hide['boxes'], [[-48.0, 48.0, -48.0, 48.0, 0.0, 100.0]])    # where it stood
        self.assertAlmostEqual(report['entities'][0]['rotationRounding'], 0.4)
        self.assertEqual(spec['map'], dict(name='URB_Bar', origin=[-2784, -1920], shipAs='URB_Bar_BarRemix_5005',
                                           displayName='URB_Bar_BarRemix_5005 (Bar remix) |0', streamSlot='free'))
        self.assertEqual(spec['base'], '')

    def test_a_deleted_piece_is_hidden_exactly_and_its_neighbours_stay(self):
        spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)]), scene())
        self.assertEqual([o['type'] for o in spec['objects']], ['hide'])
        out = resolve_scene(scene(), spec)
        hidden = sorted((o['layer'], o['actor']) for o in out['objects'] if o.get('hiddenBy') is not None)
        # The inherited level's actor of the same short name stays (short names are not identity).
        self.assertEqual(hidden, [('base', PL + 'XComLevelActor_1')])
        self.assertEqual(out['preview']['notes'], [])

    def test_stream_only_ships_no_map(self):
        spec, _ = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)]), scene())
        plain = compiler.stream_only(spec)
        self.assertEqual(plain['map'], dict(name='URB_Bar', origin=[-2784, -1920], seedExternally=True))
        self.assertTrue(plain['editor']['streamOnly'])
        self.assertEqual(plain['objects'], spec['objects'])
        self.assertEqual(plain['name'], spec['name'])
        self.assertIn('shipAs', spec['map'])          # the compiled spec itself is left as it was

    def test_the_build_copies_plain_and_destructible_pieces_natively_with_their_groups(self):
        group = dict(id='g', breakTogether=True, members=[{'added': PL + 'XComDestructibleActor_4_copy3'},
                                                          {'added': PL + 'XComDestructibleActor_4_copy4'}])
        doc = document([dict(target=target('XComDestructibleActor_4'), location=[48, -96, 0], rotation=[0, 8192, 0]),
                        dict(target=target('XComLevelActor_2'), deleted=True)],
                       [add('XComLevelActor_1', 1, (0, 400, 0), (0, 0, 16384)), add('XComCollectible_10', 2, (0, 600, 0)),
                        add('XComDestructibleActor_4', 3, (0, -500, 0)), add('XComDestructibleActor_4', 4, (0, -700, 0))],
                       groups=[group])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        whole = spec['objects'][0]
        self.assertEqual(whole['classes'], ['XComDestructibleActor', 'XComCollectible', 'XComDestructibleActor',
                                            'XComDestructibleActor', 'XComLevelActor'])
        before = json.dumps(spec)
        patch, native = compiler.native_split(compiler.stream_only(spec))
        natives, originals = native['copies'], native['breakOriginals']
        self.assertEqual(json.dumps(spec), before)     # the compiled spec is left as it was
        # the moved destructible, the group's two copies (linked in the map) and the added level piece are made in the
        # map, at their poses
        self.assertEqual([(n['label'], n.get('breakGroup')) for n in natives],
                         [('move:XComDestructibleActor_4', None), ('XComCollectible_10_copy2', None),
                          ('XComDestructibleActor_4_copy3', 1), ('XComDestructibleActor_4_copy4', 1),
                          ('XComLevelActor_1_copy1', None)])
        self.assertEqual(natives[0], dict(actor='XComDestructibleActor_4', location=[48, -96, 0], rotation=[0, 8192, 0],
                                          label='move:XComDestructibleActor_4', box=whole['boxes'][0]))
        self.assertEqual(natives[4]['rotation'], [0, 0, 16384])
        self.assertEqual(originals, [])
        # the collectible's copy is a collectible (loot), and the hides are made in the map too: no patch
        self.assertEqual(patch['objects'], [])
        self.assertTrue(patch['map']['seedExternally'])
        hide = spec['objects'][1]
        self.assertEqual([(h['name'], h['label']) for h in native['hides']],
                         [('XComDestructibleActor_4', 'move:XComDestructibleActor_4'),
                          ('XComLevelActor_2', 'delete:XComLevelActor_2')])
        self.assertEqual([h['box'] for h in native['hides']], hide['boxes'])
        self.assertEqual(len(hide['boxes'][1]), 6)
        # copies alone
        spec, _ = compile_project(document([], [add('XComLevelActor_1', 1, (0, 400, 0))]), scene())
        patch, native = compiler.native_split(spec)
        self.assertEqual((patch['objects'], [n['label'] for n in native['copies']], native['hides']),
                         ([], ['XComLevelActor_1_copy1'], []))

    def test_groups_go_native_with_their_pieces_left_in_place_and_others_stay_the_copiers(self):
        copies = [add('XComDestructibleActor_4', 1, (0, -500, 0)), add('XComCollectible_10', 2, (0, -500, 64)),
                  add('XComDestructibleActor_4', 3, (0, -700, 0)), add('XComDestructibleActor_4', 4, (0, -900, 0))]
        groups = [dict(id='a', breakTogether=True, members=[{'added': PL + 'XComDestructibleActor_4_copy1'},
                                                            {'added': PL + 'XComCollectible_10_copy2'}]),
                  dict(id='b', breakTogether=True, members=[{'added': PL + 'XComDestructibleActor_4_copy3'},
                                                            target('XComCollectible_10')]),
                  dict(id='c', breakTogether=True, members=[{'added': PL + 'XComDestructibleActor_4_copy4'},
                                                            target('XComDestructibleActor_4')])]
        spec, report = compile_project(document([], copies, groups=groups), scene())
        self.assertTrue(report['ok'], refused(report))
        patch, native = compiler.native_split(spec)
        # every group goes native (a collectible's copy is a collectible), with the map's own pieces left in place
        self.assertEqual(patch['objects'], [])
        self.assertEqual([(n['label'], n['breakGroup']) for n in native['copies']],
                         [('XComCollectible_10_copy2', 1), ('XComDestructibleActor_4_copy1', 1),
                          ('XComDestructibleActor_4_copy3', 2), ('XComDestructibleActor_4_copy4', 3)])
        self.assertEqual(native['breakOriginals'],
                         [dict(name='XComCollectible_10', group=2), dict(name='XComDestructibleActor_4', group=3)])
        # a copy of a class the Build can't make in the map (none in M1 yet) keeps its whole group on the copier
        doc_spec = json.loads(json.dumps(spec))
        doc_spec['objects'][0]['classes'][1] = 'XComInteractiveLevelActor'
        patch, native = compiler.native_split(doc_spec)
        copy_op, = patch['objects']
        self.assertEqual((copy_op['labels'], copy_op['breakGroups']),
                         (['XComCollectible_10_copy2', 'XComDestructibleActor_4_copy1'], [1, 1]))
        self.assertNotIn('breakOriginals', copy_op)
        self.assertEqual([n['label'] for n in native['copies']],
                         ['XComDestructibleActor_4_copy3', 'XComDestructibleActor_4_copy4'])

    def test_one_source_copied_several_times_and_moved_hides_once(self):
        doc = document([dict(target=target('XComLevelActor_2'), location=[96, 0, 64], rotation=[0, 0, 0])],
                       [add('XComLevelActor_2', 2, (0, 300, 0)), add('XComLevelActor_2', 1, (0, 200, 0))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        copy_op, hide = spec['objects']
        self.assertEqual(copy_op['from'], ['XComLevelActor_2'] * 3)
        # The move first, then the added pieces by output name.
        self.assertEqual(copy_op['labels'], ['move:XComLevelActor_2', 'XComLevelActor_2_copy1', 'XComLevelActor_2_copy2'])
        self.assertEqual(hide['alsoHide'], ['XComLevelActor_2'])

    def test_a_deleted_template_is_still_copied_before_it_is_hidden(self):
        spec, _ = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True)],
                                           [add('XComLevelActor_1', 1, (0, 400, 0))]), scene())
        self.assertEqual([o['type'] for o in spec['objects']], ['copy', 'hide'])

    def test_destructible_props_build_like_static_pieces(self):
        doc = document([dict(target=target('XComDestructibleActor_4'), location=[48, -96, 0], rotation=[0, 8192, 0])],
                       [add('XComDestructibleActor_4', 1, (0, -500, 0), (0, 0, 16384))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        copy_op, hide = spec['objects']
        self.assertEqual(copy_op['from'], ['XComDestructibleActor_4'] * 2)
        self.assertEqual(copy_op['labels'], ['move:XComDestructibleActor_4', 'XComDestructibleActor_4_copy1'])
        self.assertEqual(hide['alsoHide'], ['XComDestructibleActor_4'])
        self.assertEqual({e['actorClass'] for e in report['entities']}, {'XComDestructibleActor'})
        spec, report = compile_project(document([dict(target=target('XComDestructibleActor_4'), deleted=True)]), scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['objects'][0]['alsoHide'], ['XComDestructibleActor_4'])

    def test_groups_that_break_together_number_their_copies_and_the_originals_left_in_place(self):
        copies = [add('XComDestructibleActor_4', 1, (0, -500, 0)), add('XComDestructibleActor_4', 2, (0, -500, 64)),
                  add('XComLevelActor_1', 3, (0, 400, 0)), add('XComDestructibleActor_4', 4, (0, -700, 0))]
        groups = [dict(id='b', locked=True, breakTogether=True,
                       members=[{'added': PL + 'XComDestructibleActor_4_copy1'}, {'added': PL + 'XComDestructibleActor_4_copy2'},
                                {'added': PL + 'XComLevelActor_1_copy3'}]),
                  dict(id='a', locked=False, breakTogether=True,
                       members=[target('XComCollectible_10'), {'added': PL + 'XComDestructibleActor_4_copy4'}]),
                  dict(id='c', locked=True, breakTogether=False, members=[target('XComLevelActor_1'), target('XComLevelActor_2')])]
        spec, report = compile_project(document([], copies, groups=groups), scene())
        self.assertTrue(report['ok'], refused(report))
        copy_op = spec['objects'][0]
        self.assertEqual(copy_op['labels'], ['XComDestructibleActor_4_copy1', 'XComDestructibleActor_4_copy2',
                                             'XComDestructibleActor_4_copy4', 'XComLevelActor_1_copy3'])
        # Numbered in the order of the groups' ids: a is 1, b is 2; c doesn't break together.
        self.assertEqual(copy_op['breakGroups'], [2, 2, 1, 0])
        self.assertEqual(copy_op['breakOriginals'], [dict(name='XComCollectible_10', group=1)])
        self.assertEqual(list(copy_op)[-1], 'extra')
        self.assertEqual([(g['id'], g['number'], g['copies'], g['originals'], g['notBreakable']) for g in report['groups']],
                         [('a', 1, ['XComDestructibleActor_4_copy4'], ['XComCollectible_10'], []),
                          ('b', 2, ['XComDestructibleActor_4_copy1', 'XComDestructibleActor_4_copy2'], [], ['XComLevelActor_1_copy3']),
                          ('c', 0, [], [], [])])
        self.assertEqual([w['code'] for w in report['notes']], ['group-unbreakable'])

    def test_groups_that_dont_break_together_leave_the_spec_as_it_was(self):
        copies = [add('XComDestructibleActor_4', 1, (0, -500, 0)), add('XComDestructibleActor_4', 2, (0, -500, 64))]
        plain, _ = compile_project(document([], copies), scene())
        group = dict(id='g', locked=True, members=[{'added': PL + 'XComDestructibleActor_4_copy1'}, {'added': PL + 'XComDestructibleActor_4_copy2'}])
        grouped, report = compile_project(document([], copies, groups=[group]), scene())
        self.assertEqual(json.dumps(plain), json.dumps(grouped))
        self.assertEqual(report['groups'][0]['breakTogether'], False)

    def test_a_moved_member_links_through_its_copy_and_a_deleted_one_drops_out(self):
        moved = dict(target=target('XComDestructibleActor_4'), location=[48, -96, 0], rotation=[0, 8192, 0])
        copies = [add('XComDestructibleActor_4', 1, (0, -500, 0))]
        group = dict(id='g', breakTogether=True, members=[target('XComDestructibleActor_4'), {'added': PL + 'XComDestructibleActor_4_copy1'}])
        spec, report = compile_project(document([moved], copies, groups=[group]), scene())
        self.assertEqual(spec['objects'][0]['labels'], ['move:XComDestructibleActor_4', 'XComDestructibleActor_4_copy1'])
        self.assertEqual(spec['objects'][0]['breakGroups'], [1, 1])
        self.assertNotIn('breakOriginals', spec['objects'][0])
        deleted = dict(target=target('XComDestructibleActor_4'), deleted=True)
        spec, report = compile_project(document([deleted], copies, groups=[group]), scene())
        self.assertNotIn('breakGroups', spec['objects'][0])
        self.assertEqual([w['code'] for w in report['notes']], ['group-unbreakable'])

    def test_a_group_of_originals_left_in_place_is_not_linked_yet(self):
        group = dict(id='g', breakTogether=True, members=[target('XComDestructibleActor_4'), target('XComCollectible_10')])
        spec, report = compile_project(document(groups=[group]), scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['objects'], [])
        self.assertEqual([w['code'] for w in report['warnings']], ['group-not-linked'])

    def test_malformed_groups_are_left_out(self):
        # (refused until review finding 39: a group is left out, and the rest builds)
        one = {'added': PL + 'XComDestructibleActor_4_copy1'}
        for bad in (dict(id='g', members=[one]), dict(id='g', members=[one, one]), dict(members=[one, target('XComLevelActor_1')]),
                    dict(id='g', members=[one, dict(actor='x')]), dict(id='g', breakTogether='yes', members=[one, target('XComLevelActor_1')]), 'g'):
            spec, report = compile_project(document([], [add('XComDestructibleActor_4', 1, (0, -500, 0))], groups=[bad]), scene())
            self.assertTrue(report['ok'], bad)
            self.assertEqual(codes(report), ['malformed'], bad)
            self.assertEqual([d['record'] for d in report['leftOut']], ['groups[0]'])
            self.assertEqual(spec['objects'][0]['labels'], ['XComDestructibleActor_4_copy1'])
            self.assertNotIn('breakGroups', spec['objects'][0])
        spec, report = compile_project(document(groups='g'), scene())
        self.assertEqual(codes(report), ['malformed'])
        self.assertTrue(report['ok'])

    def test_collectibles_build_like_destructible_props_and_warn_about_loot(self):
        doc = document([dict(target=target('XComCollectible_10'), location=[96, -600, 0], rotation=[0, 0, 0])],
                       [add('XComCollectible_10', 1, (0, -800, 0))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        copy_op, hide = spec['objects']
        self.assertEqual(copy_op['from'], ['XComCollectible_10'] * 2)
        self.assertEqual(hide['alsoHide'], ['XComCollectible_10'])
        self.assertEqual({e['actorClass'] for e in report['entities']}, {'XComCollectible'})
        # Each edit of a collectible says what happens to its loot.
        self.assertEqual([(w['code'], w.get('entity') or w.get('target')) for w in report['notes']],
                         [('collectible', PL + 'XComCollectible_10'), ('collectible', PL + 'XComCollectible_10_copy1')])
        self.assertIn('moved, it still counts once', report['notes'][0]['message'])
        self.assertIn('the copy counts as mission loot too', report['notes'][1]['message'])
        spec, report = compile_project(document([dict(target=target('XComCollectible_10'), deleted=True)]), scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['objects'][0]['alsoHide'], ['XComCollectible_10'])
        self.assertEqual([w['code'] for w in report['notes']], ['collectible'])
        self.assertIn('deleted, it no longer counts', report['notes'][0]['message'])
        # Other destructible props give no such warning.
        _, report = compile_project(document([dict(target=target('XComDestructibleActor_4'), deleted=True)]), scene())
        self.assertEqual(report['warnings'], [])

    def test_a_car_body_edited_without_its_glass_splits_the_car(self):
        # Moving, deleting or copying a destructible that names a partner (a car) builds with its glass, as one assembly
        # (cars build since EXP-24); alone, it splits the car.
        for overrides, added in [([dict(target=target('XComDestructibleActor_6'), location=[0, -200, 0], rotation=[0, 0, 0])], []),
                                 ([dict(target=target('XComDestructibleActor_6'), deleted=True)], []),
                                 ([], [dict(add('XComDestructibleActor_6', 1, (0, 0, 0)))])]:
            with self.subTest(overrides=overrides, added=bool(added)):
                spec, report = compile_project(document(overrides, added), scene())
                # (a refusal until 14 November 2026: a warning, and the part is edited as a piece of its own)
                self.assertEqual((left_out(report), built(report), warned(report, 'assembly-')), ([], 1, ['assembly-split']))
                self.assertEqual(report['warnings'][0]['family'], 'car')
                self.assertIn('XComFracLevelActor_7', report['warnings'][0]['message'])
                copy = next((o for o in spec['objects'] if o['type'] == 'copy'), None)
                if copy:
                    self.assertEqual((copy['untried'], 'assemblies' in copy), ([True], False))
                continue
                self.assertEqual(refused(report)[0]['family'], 'car')
                self.assertIn('XComFracLevelActor_7', refused(report)[0]['message'])

    def test_other_milestones_levels_and_offsets_are_refused(self):
        cases = [
            ([dict(target=target('XComLevelActor_1', 'inherited', 'patch_bar'), deleted=True)], [], 'level'),
            ([dict(target=target('XComLevelActor_9'), deleted=True)], [], 'missing'),
            ([], [dict(add('XComLevelActor_1', 1, (0, 0, 0)), components=['other'])], 'template-changed'),
            ([dict(target=target('XComLevelActor_1'), location=[0, 0, float('nan')], rotation=[0, 0, 0])], [], 'malformed'),
            ([dict(target=target('XComLevelActor_1'))], [], 'malformed'),
        ]
        for overrides, added, code in cases:
            with self.subTest(code=code):
                spec, report = compile_project(document(overrides, added), scene())
                self.assertEqual((left_out(report), built(report)), ([code], 0))
                self.assertEqual(report['leftOut'][0]['record'], 'overrides[0]' if overrides else 'added[0]')

    def test_what_our_own_gates_held_back_is_warned_of_and_built(self):
        # the user, 14 November 2026: warn and build, don't leave out. A tinted copy is built untinted, a copy that
        # names a partner alone, a class the Build has not made before as any copy, without a warning saying so (16
        # November 2026); the last two are marked untried, so the Build can leave them out if it can't make them
        # (build.py drop_untried)
        s = scene()
        s['objects'].append(part('SkeletalMeshActor_30', cls='SkeletalMeshActor', at=(0, -1500, 0)))
        doc = document([dict(target=target('SkeletalMeshActor_30'), location=[96, -1500, 0], rotation=[0, 0, 0])],
                       [dict(add('XComLevelActor_1', 1, (0, 300, 0)), tinted=True),
                        dict(add('XComLevelActor_1', 2, (0, 600, 0)), partner=PL + 'X_copy9'),
                        add('SkeletalMeshActor_30', 3, (0, 900, 0))])
        spec, report = compile_project(doc, s)
        self.assertEqual((left_out(report), built(report)), ([], 4))
        self.assertEqual(noted(report, 'tint-') + warned(report, 'partner-') + warned(report, 'class-'),
                         ['tint-dropped', 'partner-dropped'])
        self.assertNotIn('untried', ' '.join(w['message'] for w in report['warnings']))
        copy = next(o for o in spec['objects'] if o['type'] == 'copy')
        self.assertEqual(dict(zip(copy['labels'], copy['untried'])),
                         {'move:SkeletalMeshActor_30': True, 'XComLevelActor_1_copy1': False, 'XComLevelActor_1_copy2': True,
                          'SkeletalMeshActor_30_copy3': True})
        # every one is made in the map: nothing is left for the patch's copier
        patch_spec, native = compiler.native_split(spec)
        self.assertEqual(([o for o in patch_spec['objects'] if o['type'] == 'copy'], len(native['copies'])), ([], 4))
        self.assertEqual(sorted(c['label'] for c in native['copies'] if c.get('untried')),
                         ['SkeletalMeshActor_30_copy3', 'XComLevelActor_1_copy2', 'move:SkeletalMeshActor_30'])
        # a volume is no piece: the level volume draws some of a map's meshes and holds its tile data. A move or a
        # copy of one is left out, never built untried
        s['objects'].append(part('XComLevelVolume_0', cls='XComLevelVolume', at=(0, -2000, 0)))
        doc = document([dict(target=target('XComLevelVolume_0'), location=[96, -2000, 0], rotation=[0, 0, 0])],
                       [add('XComLevelVolume_0', 1, (0, 300, 0))])
        self.assertEqual((left_out(compile_project(doc, s)[1]), built(compile_project(doc, s)[1])), (['not-a-piece'] * 2, 0))

    def test_a_piece_left_out_does_not_stop_the_others(self):
        # plan "sturdier prefabs", R4: one piece that can't be built is left out and named; the rest builds
        doc = document([dict(target=target('XComLevelActor_9'), deleted=True), dict(target=target('XComLevelActor_1'), deleted=True)],
                       [dict(add('XComLevelActor_1', 1, (0, 0, 0)), components=['other']), add('XComLevelActor_2', 2, (0, 400, 0))])
        spec, report = compile_project(doc, scene())
        self.assertEqual(sorted(left_out(report)), ['missing', 'template-changed'])
        self.assertEqual([e['record'] for e in report['leftOut']], ['added[0]', 'overrides[0]'])
        self.assertEqual((report['counts']['deleted'], report['counts']['added']), (1, 1))
        self.assertEqual([o['type'] for o in spec['objects']], ['copy', 'hide'])

    def test_a_copy_keeps_its_components_offset(self):
        # plan R2: a component turned or shifted apart from its actor is cloned with it by the Build, so the copy
        # builds; its box is the offset component's (XComLevelActor_5's sits 16 units over its actor)
        flat = next(o for o in scene()['objects'] if o['actor'] == PL + 'XComLevelActor_5')
        doc = document([dict(target=target('XComLevelActor_5'), location=[0, 0, 0], rotation=[0, 0, 0])],
                       [add('XComLevelActor_5', 1, (960, 0, 64))])
        spec, report = compile_project(doc, scene())
        self.assertEqual((left_out(report), built(report)), ([], 2))
        plain = compiler.world_box(dict(flat, componentTransform=None), scene()['meshes'], [960, 0, 64], [0, 0, 0])
        copy = next(e for e in report['entities'] if e['kind'] == 'add')
        self.assertEqual(copy['newBox'], [round(v + (16 if k >= 4 else 0), 3) for k, v in enumerate(plain)])
        # a class the patch's copier would make can't take one (none builds today; the refusal stays for them)
        with mock.patch.object(compiler, 'NATIVE_CLASSES', ()):
            _, report = compile_project(doc, scene())
            self.assertEqual(left_out(report), ['component-offset'] * 2)

    def test_a_refusal_names_the_milestone(self):
        with mock.patch.dict(compiler.FAMILIES['frameless-door'], builds=False):
            _, report = compile_project(document([dict(target=target('XComInteractiveLevelActor_8'), deleted=True)]), scene())
        self.assertEqual(refused(report)[0]['milestone'], 2)
        self.assertIn('M2', refused(report)[0]['message'])
        # a car's glass is part of the car, which builds (since EXP-24): deleted alone it splits the car, which is
        # warned of and done (a refusal until 14 November 2026)
        _, report = compile_project(document([dict(target=target('XComFracLevelActor_7'), deleted=True)]), scene())
        self.assertEqual((warned(report, 'assembly-'), report['counts']['deleted']), (['assembly-split'], 1))
        # a fracturing piece of its own and a physics prop build (since 9 November); with a family off again, its
        # refusal names its milestone as before
        for name, cls, family in (('XComFracLevelActor_11', 'XComFracLevelActor', 'fracturing'), ('KAsset_12', 'KAsset', 'physics')):
            s = scene()
            s['objects'].append(part('KAsset_12', cls='KAsset', at=(0, -1200, 0)))
            at = next(o for o in s['objects'] if o['actor'] == PL + name)['location']
            doc = document([dict(target=target(name), location=[at[0] + 96, at[1], at[2]], rotation=[0, 0, 0])])
            # a delete of a family that isn't built is taken (Clear map plan, section 6), with no warning saying it
            # is untried (16 November 2026)
            with mock.patch.dict(compiler.FAMILIES[family], builds=False):
                spec, report = compile_project(document([dict(target=target(name), deleted=True)]), s)
                self.assertTrue(report['ok'], refused(report))
                self.assertEqual(warned(report, 'delete-'), [])
                self.assertEqual(spec['objects'][0]['alsoHide'], [name])
            with mock.patch.dict(compiler.FAMILIES[family], builds=False):
                spec, report = compile_project(doc, s)
                self.assertEqual(left_out(report), ['milestone'])
                self.assertEqual((refused(report)[0]['code'], refused(report)[0]['milestone'], refused(report)[0]['family']),
                                 ('milestone', 3, family))
                self.assertIn('%s, which builds from milestone M3' % cls, refused(report)[0]['message'])
                # --family builds it all the same (an experiment's build)
                spec, report = compile_project(doc, s, enable=[family])
                self.assertTrue(report['ok'], refused(report))
            spec, report = compile_project(doc, s)
            self.assertTrue(report['ok'], refused(report))
            self.assertEqual([o['alsoHide'] for o in spec['objects'] if o['type'] == 'hide'], [[name]])

    def test_a_fracturing_piece_builds_on_the_grid_and_a_physics_prop_anywhere(self):
        s = scene()
        s['objects'].append(part('KAsset_12', cls='KAsset', at=(0, -1200, 0)))
        wall = next(o for o in s['objects'] if o['id'] == 'XComFracLevelActor_11')
        # a wall moved two tiles and a storey and turned a quarter turn about a tile corner, and a copy of it
        loc, rot = grid_moved(1, (2, 0), 1)(wall)
        copy_loc, copy_rot = grid_moved(0, (0, -3))(wall)
        doc = document([dict(target=target('XComFracLevelActor_11'), location=loc, rotation=rot),
                        dict(target=target('KAsset_12'), location=[13.5, -1177.25, 3], rotation=[100, 5000, -20])],
                       [add('XComFracLevelActor_11', 1, copy_loc, copy_rot), add('KAsset_12', 2, (40.5, -1000, 0), (0, 77, 0))])
        spec, report = compile_project(doc, s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['warnings'], [])
        self.assertEqual(report['counts']['moved'], 2)
        self.assertEqual(report['counts']['added'], 2)
        # all four are made in the map itself, as single pieces (no assembly): the patch gets nothing
        patch, native = compiler.native_split(spec)
        self.assertEqual(patch['objects'], [])
        self.assertEqual(sorted((c['actor'], 'assembly' in c) for c in native['copies']),
                         [('KAsset_12', False), ('KAsset_12', False), ('XComFracLevelActor_11', False),
                          ('XComFracLevelActor_11', False)])
        self.assertEqual(sorted(h['name'] for h in native['hides']), ['KAsset_12', 'XComFracLevelActor_11'])
        # off the grid a fracturing piece builds too (since 10 November), with an off-grid warning naming what it misses
        # and the nearest pose on the grid; moved and added alike
        for bad_loc, bad_rot, why in (([wall['location'][0] + 40, wall['location'][1], 0], wall['rotation'], 'whole tiles'),
                                      (wall['location'], [0, 2000, 0], 'quarter turns'),
                                      ([wall['location'][0], wall['location'][1], 20], wall['rotation'], 'whole storeys'),
                                      (wall['location'], [300, 0, 0], 'pitch or roll')):
            for doc in (document([dict(target=target('XComFracLevelActor_11'), location=bad_loc, rotation=bad_rot)]),
                        document([], [add('XComFracLevelActor_11', 1, bad_loc, bad_rot)])):
                with self.subTest(why=why, added=bool(doc['added'])):
                    spec, report = compile_project(doc, s)
                    self.assertTrue(report['ok'], refused(report))
                    self.assertEqual([w['code'] for w in report['warnings']], ['off-grid'])
                    warning = report['warnings'][0]
                    self.assertEqual(warning['family'], 'fracturing')
                    self.assertIn(why, warning['message'])
                    _, native = compiler.native_split(spec)
                    self.assertEqual([(c['actor'], c['location']) for c in native['copies']],
                                     [('XComFracLevelActor_11', [float(v) for v in bad_loc])])
                    near = warning['nearest']
                    _, again = compile_project(document([dict(target=target('XComFracLevelActor_11'), location=near['location'],
                                                              rotation=near['rotation'])]), s)
                    self.assertTrue(again['ok'], again['errors'])
        # a door's frame without its leaf stays a destructible prop of its own, at any pose
        a = assembly_scene()
        _, report = compile_project(document([dict(target=target('XComDestructibleActor_22'), location=[500.5, 150, 16],
                                                   rotation=[0, 17000, 0])]), a)
        self.assertTrue(report['ok'], refused(report))

    def test_schema_source_and_output_are_checked(self):
        for doc, code in [(document(schemaVersion=10), 'schema'),
                          (document(source=dict(map='URB_Bar', sha256='b' * 64)), 'source-mismatch'),
                          (document(output=dict(shipAs='URB_Bar', patch='patch_x')), 'output'),
                          (document(output=dict(shipAs='Bad name', patch='patch_x')), 'output'),
                          (document(output=dict(shipAs='URB_Bar_X', patch='patch_urb_bar_exp11staticplacement')), 'output')]:
            with self.subTest(code=code):
                spec, report = compile_project(doc, scene())
                self.assertIsNone(spec)
                self.assertEqual(codes(report)[:1], [code])

    def test_output_names_of_any_valid_length_build_and_three_must_differ(self):
        """Output names plan 3.3: a new project's map name keeps to 24 (the Save dialog's allocation), but the compiler
        takes what UDK can save, so a project of before with a name of 25 to 30 characters still builds; one letter is
        a name; the map, its patch and the base map differ pairwise (the patch named as the base map too); a device
        name is refused."""
        for out in (dict(shipAs='A', patch='patch_a'), dict(shipAs='B' * 30, patch='patch_b'),
                    dict(shipAs='URB_Bar_Commercial_Fix_ab12', patch='patch_urb_bar_commercial_fix_')):
            with self.subTest(out=out):
                spec, report = compile_project(document(output=out), scene())
                self.assertTrue(report['ok'], refused(report))
                self.assertEqual(spec['map']['shipAs'], out['shipAs'])
        for out in (dict(shipAs='C' * 31, patch='patch_c'), dict(shipAs='Fine', patch='URB_BAR'),
                    dict(shipAs='Fine', patch='fine'), dict(shipAs='Con', patch='patch_con'), dict(shipAs='Fine', patch='LPT1')):
            with self.subTest(out=out):
                spec, report = compile_project(document(output=out), scene())
                self.assertIsNone(spec)
                self.assertEqual(codes(report)[:1], ['output'])

    def test_no_edits_is_a_variant_with_no_objects(self):
        spec, report = compile_project(document(name='Quote "and" pipe | é'), scene())
        self.assertTrue(report['ok'])
        self.assertEqual(spec['objects'], [])
        self.assertEqual(spec['map']['displayName'], 'URB_Bar_BarRemix_5005 (Quote and pipe) |0')

    def test_the_same_project_compiles_the_same_whatever_the_record_order(self):
        overrides = [dict(target=target('XComLevelActor_1'), deleted=True),
                     dict(target=target('XComLevelActor_2'), location=[100, 0, 0], rotation=[0, 1000, 0])]
        added = [add('XComLevelActor_1', k, (k * 10, 0, 0)) for k in range(1, 6)]
        first = json.dumps(compile_project(document(overrides, added), scene())[0])
        rnd = random.Random(4)
        for _ in range(5):
            o, a = overrides[:], added[:]
            rnd.shuffle(o); rnd.shuffle(a)
            self.assertEqual(json.dumps(compile_project(document(o, a), scene())[0]), first)

    def test_rotators_round_half_away_from_zero_and_keep_whole_turns(self):
        self.assertEqual([game_round(v) for v in (0.5, -0.5, 1.4999, -1.5, 70000)], [1, -1, 1, -2, 70000])
        spec, _ = compile_project(document([], [add('XComLevelActor_1', 1, (0, 0, 0), (-0.5, 70000, 32767.5))]), scene())
        self.assertEqual(spec['objects'][0]['poses'][0]['rotation'], [-1, 70000, 32768])

    def test_unchanged_poses_and_building_floors_are_reported(self):
        # StaticMeshActor_3 is in floor 0's cutaway; raised out of the floor's volume, its copy has no cutaway
        s = scene()
        s['buildings'] = [dict(name=PL + 'XComBuildingVolume_7', floors=[
            dict(index=0, boxes=[dict(min=[-60, 40, 0], max=[60, 160, 110])], members=[])])]
        spec, report = compile_project(document([dict(target=target('XComLevelActor_1'), location=[0, 0, 0], rotation=[0, 0, 0]),
                                                 dict(target=target('StaticMeshActor_3'), location=[0, 96, 640], rotation=[0, 0, 0])]), s)
        self.assertTrue(report['ok'])
        self.assertEqual(sorted(w['code'] for w in report['notes']), ['building-floor', 'unchanged'])
        self.assertEqual(spec['objects'][0]['from'], ['StaticMeshActor_3'])

    def test_a_piece_the_maps_kismet_names_is_moved_with_a_warning(self):
        # export 15's referencedBy (Bar's Kismet hides its grounded Skyranger at the landing); a warning since the
        # map buildings plan's E2b: the Build moves or deletes it as any other, its script acting on the original
        s = scene()
        for o in s['objects']:
            if o['actor'] == PL + 'XComLevelActor_2':
                o['referencedBy'] = ['SeqAct_ToggleHidden_1 Target']
        moved, deleted = (dict(target=target('XComLevelActor_2'), location=[96, 96, 0], rotation=[0, 0, 0]),
                          dict(target=target('XComLevelActor_2'), deleted=True))
        for rec in (moved, deleted):
            spec, report = compile_project(document([rec]), s)
            self.assertIsNotNone(spec)
            _, native = compiler.native_split(compiler.stream_only(spec))
            self.assertEqual([h['name'] for h in native['hides']], ['XComLevelActor_2'])
        # moved: a warning, the script misses the copy at its new place
        _, report = compile_project(document([moved]), s)
        self.assertEqual((codes(report), warned(report, 'mission')), ([], ['mission-linked']))
        self.assertIn('XComLevelActor_2 is moved', report['warnings'][0]['message'])
        self.assertIn('SeqAct_ToggleHidden_1 Target', report['warnings'][0]['message'])
        # deleted: the Build takes it out of the script (the spec's kismetCuts), a note; a copy of it too
        spec, report = compile_project(document([deleted]), s)
        self.assertEqual((warned(report, 'mission'), noted(report, 'mission')), ([], ['mission-linked']))
        self.assertEqual(native_split(spec)[1]['kismetCuts'], ['XComLevelActor_2'])
        spec, report = compile_project(document([deleted], [add('XComLevelActor_2', 1, (96, 192, 0))]), s)
        self.assertEqual((warned(report, 'mission'), noted(report, 'mission')), ([], ['mission-linked']))
        self.assertIn('takes it out of the map\'s Kismet', next(n for n in report['notes'] if n['code'] == 'mission-linked')['message'])
        # moved: no cut (the hidden original keeps its references)
        spec, _ = compile_project(document([moved]), s)
        self.assertNotIn('kismetCuts', native_split(spec)[1])
        # deleted, and the script waits on it (an event's originator): a warning on a map as it is, a note on a cleared one
        for o in s['objects']:
            if o['actor'] == PL + 'XComLevelActor_2':
                o['referencedBy'] = ['SeqAct_ToggleHidden_1 Target', 'SeqEvent_Destroyed_0 Originator']
        _, report = compile_project(document([deleted]), s)
        self.assertEqual(warned(report, 'mission'), ['mission-linked'])
        self.assertIn('waits on it (SeqEvent_Destroyed_0 Originator)', report['warnings'][0]['message'])
        _, report = compile_project(document([deleted], cleared=True), s)
        self.assertEqual((warned(report, 'mission'), noted(report, 'mission')), ([], ['mission-linked']))
        # that note follows the Triggers part (its script cut off from them): with the pieces alone cleared, a warning
        _, report = compile_project(document([deleted], cleared={'pieces': {}}), s)
        self.assertEqual(warned(report, 'mission'), ['mission-linked'])
        _, report = compile_project(document([deleted], cleared={'triggers': {}}), s)
        self.assertEqual((warned(report, 'mission'), noted(report, 'mission')), ([], ['mission-linked']))
        # copied alone (the original stays): nothing
        spec, report = compile_project(document([], [add('XComLevelActor_2', 1, (96, 192, 0))]), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(warned(report, 'mission') + noted(report, 'mission'), [])

    def test_landing_zone_pieces_are_moved_with_a_warning(self):
        # F-45: LWR's landing-zone mutator spawns the landing from the map's own pieces of the landing prefabs, told by
        # archetype (the grounded Skyranger, the soldier-spawn markers)
        s = scene()
        for o in s['objects']:
            if o['actor'] == PL + 'XComLevelActor_2':
                o['archetype'] = 'VEH_Lv1Skyranger_MOD.Prefabs.ARC_Skyranger_Grounded'
            if o['actor'] == PL + 'XComLevelActor_1' and o['layer'] == 'base':
                o['archetype'] = 'dgn_dropshipsoldierspawn.Archetypes.ARC_DropZone'
        self.assertEqual(compiler.landing_actors(s), [PL + 'XComLevelActor_1', PL + 'XComLevelActor_2'])
        for name in ('XComLevelActor_1', 'XComLevelActor_2'):
            for rec in (dict(target=target(name), location=[96, 960, 0], rotation=[0, 0, 0]),
                        dict(target=target(name), deleted=True)):
                spec, report = compile_project(document([rec]), s)
                self.assertIsNotNone(spec)
                self.assertEqual((codes(report), warned(report, 'landing')), ([], ['landing-zone']))
                self.assertIn('F-45', [w for w in report['warnings'] if w['code'] == 'landing-zone'][0]['message'])
        spec, report = compile_project(document([], [add('XComLevelActor_2', 1, (96, 192, 0))]), s)
        self.assertTrue(report['ok'], refused(report))
        # other archetypes of the same packages' names elsewhere in a path don't count
        self.assertFalse(compiler.is_landing(dict(archetype='Props.VEH_Lv1Skyranger_MOD.Prefabs.Thing')))

    def test_with_floor_boxes_the_floor_note_says_where_a_copy_stands(self):
        # export 15: a floor's volume boxes. StaticMeshActor_3 (in floor 0's cutaway) moved within the floor: no
        # note; moved out of every floor: its copy has no cutaway. XComLevelActor_1 (in none) copied into the floor
        s = scene()
        s['exporterVersion'] = 18
        s['buildings'] = [dict(name=PL + 'XComBuildingVolume_7', floors=[
            dict(index=0, boxes=[dict(min=[-200, 0, 0], max=[200, 400, 200])], members=[])])]
        inside = dict(target=target('StaticMeshActor_3'), location=[96, 192, 0], rotation=[0, 0, 0])
        outside = dict(target=target('StaticMeshActor_3'), location=[960, 960, 0], rotation=[0, 0, 0])
        self.assertEqual(compile_project(document([inside]), s)[1]['notes'], [])
        warned = compile_project(document([outside]), s)[1]['notes']
        self.assertEqual([w['code'] for w in warned], ['building-floor'])
        self.assertIn('stands in no building floor', warned[0]['message'])
        warned = compile_project(document([], [add('XComLevelActor_1', 1, (0, 192, 0))]), s)[1]['warnings']
        self.assertIn("floor 1 of XComBuildingVolume_7 but won't hide", warned[0]['message'])
        # listed though it stands in no floor volume (a ladder on an outer wall), moved and still outside them: the
        # copy keeps its original's listing, so no note
        s['buildings'][0]['floors'][0]['boxes'] = [dict(min=[-200, 200, 0], max=[200, 400, 200])]
        beside = dict(target=target('StaticMeshActor_3'), location=[96, 96, 0], rotation=[0, 0, 0])
        self.assertEqual(compile_project(document([beside]), s)[1]['warnings'], [])

    def test_unknown_fields_are_reported_not_silently_dropped(self):
        _, report = compile_project(document([dict(target=target('XComLevelActor_1'), deleted=True, scale=[2, 2, 2])]), scene())
        self.assertEqual([w['code'] for w in report['notes']], ['unknown-field'])

    def test_boxes_follow_the_full_rotation(self):
        meshes = scene()['meshes']
        obj = part('XComLevelActor_1')
        b = world_box(obj, meshes, [0, 0, 0], [0, 8192, 0])            # yaw 45 degrees
        self.assertAlmostEqual(b[1], 48 * math.sqrt(2), 4)
        self.assertAlmostEqual(b[4], 0, 4); self.assertAlmostEqual(b[5], 100, 4)
        b = world_box(obj, meshes, [0, 0, 0], [16384, 0, 0])           # pitch 90 (nose up): its top points to -x
        self.assertAlmostEqual(b[0], -100, 4); self.assertAlmostEqual(b[1], 0, 4)
        self.assertAlmostEqual(b[4], -48, 4); self.assertAlmostEqual(b[5], 48, 4)
        b = world_box(obj, meshes, [0, 0, 0], [0, 0, 16384])           # roll 90: along y
        self.assertAlmostEqual(b[3] - b[2], 100, 4)
        spec, _ = compile_project(document([], [add('XComLevelActor_1', 1, (10, 0, 0), (0, 8192, 0))]), scene())
        self.assertAlmostEqual(spec['objects'][0]['boxes'][0][1], 10 + 48 * math.sqrt(2), 2)


CAR = ['XComDestructibleActor_24', 'XComFracLevelActor_25', 'XComDestructibleActor_26']
VAN = ['XComDestructibleActor_30', 'XComFracLevelActor_31', 'XComLevelActor_32', 'XComLevelActor_33']
DOOR = ['XComInteractiveLevelActor_21', 'XComDestructibleActor_22']


class StageTests(unittest.TestCase):
    """A project's larger tile grid (Compiler.stage; prefab plan 5.11)."""
    def run_stage(self, stage, dims=(52, 39, 12), name='CB2_MP_Blank'):
        s = scene()
        s['name'] = name
        s['tileGrid'].update(dimensions=list(dims), size=[96, 96, 64])
        doc = document(stage=stage)
        doc['source'] = dict(doc['source'], map=name, package=name + '.upk')
        return compiler.compile_project(doc, s)

    def test_a_map_of_the_games_grows_too(self):
        _, report = self.run_stage({'grid': [61, 39]}, name='URB_Bar')
        self.assertTrue(report['ok'], refused(report))
        self.assertIn('stage-grown-map', noted(report))
        _, report = self.run_stage({'grid': [20, 39]}, name='URB_Bar')
        self.assertEqual(codes(report), ['stage-grid'])
        # (left out since review finding 39: the map keeps its size and the rest builds)
        self.assertEqual((report['ok'], report['stageGrid'], [d['record'] for d in report['leftOut']]), (True, None, ['stage']))
        # higher as it is (the user, 13 November 2026): taken, the note saying where the cursor's new floors come from
        _, report = self.run_stage({'grid': [52, 39, 16]}, name='URB_Bar')
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['stageGrid'], [52, 39, 16])
        message, = [d['message'] for d in report['notes'] if d['code'] == 'stage-grown-map']
        self.assertIn('new levels by storeys', message)
        self.assertNotIn('played', message)
        self.assertNotIn('ground', message)
        _, report = self.run_stage({'grid': [52, 39, 11]}, name='URB_Bar')
        self.assertEqual(codes(report), ['stage-grid'])

    def test_a_larger_grid_is_taken_and_reported(self):
        spec, report = self.run_stage({'grid': [61, 39]})
        self.assertTrue(report['ok'])
        self.assertEqual(report['stageGrid'], [61, 39, 12])

    def test_a_grid_drawn_ground_is_taken(self):
        _, report = self.run_stage({'grid': [52, 39], 'lines': True})
        self.assertTrue(report['ok'])

    def test_a_hidden_ground_is_taken(self):
        _, report = self.run_stage({'grid': [52, 39], 'hideGround': True})
        self.assertTrue(report['ok'])
        _, report = self.run_stage({'grid': [52, 39], 'hideGround': 'yes'})
        self.assertIn('stage-shape', [e['code'] for e in refused(report)])

    def test_levels_up_to_the_tallest_maps(self):
        """A third number, the levels (prefab plan 5.6b): from the map's own up to 30 (18 until 14 November 2026),
        upward from its bottom; over 18, the tallest of the game's own maps, with no warning (16 November 2026)."""
        _, report = self.run_stage({'grid': [52, 39, 18]})
        self.assertTrue(report['ok'])
        self.assertEqual(report['stageGrid'], [52, 39, 18])
        self.assertNotIn('stage-levels-tall', warned(report))
        _, report = self.run_stage({'grid': [52, 39, 12]})
        self.assertIsNone(report['stageGrid'])
        for levels in (19, 30):
            _, report = self.run_stage({'grid': [52, 39, levels]})
            self.assertEqual((report['ok'], report['stageGrid']), (True, [52, 39, levels]))
            self.assertEqual(warned(report, 'stage-'), [])
        for levels in (11, 31):
            _, report = self.run_stage({'grid': [52, 39, levels]})
            self.assertEqual(codes(report), ['stage-grid'], levels)
        self.assertEqual(compiler.STAGE_LEVELS_MAX, 30)

    def test_a_taller_grid_gets_a_cursor_storey_for_each_192(self):
        s = scene()
        s.update(name='CB2_MP_Blank', exporterVersion=20, cursorVolumes=[])
        s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
        for stage, storeys in ((None, 4), ({'grid': [52, 39, 18]}, 6), ({'grid': [52, 39, 14]}, 5), ({'grid': [52, 39, 30]}, 10)):
            c = compiler.Compiler(document(**({'stage': stage} if stage else {})), s)
            c.map = 'CB2_MP_Blank'
            c.stage()
            got = c.cursor_storeys()
            self.assertEqual(len(got), storeys, stage)
            # (the last storey reaches the grid's top, or a whole storey when the top is nearer: shell.py's rule)
            bottom = s['tileGrid']['origin'][2]
            self.assertEqual(got[-1][1][5], max(bottom + 64 * (stage['grid'][2] if stage else 12), bottom + 192 * storeys))

    def test_a_map_grown_as_it_is_keeps_its_cursor_volumes_and_gets_storeys_above(self):
        """A map with its own cursor volumes grown as it is (shell.py grow_cursors): a volume reaching the old far
        side stretched to the new one, one short of it kept, and storeys over the whole grid from the top of its own
        (the user, 13 November 2026: the levels too)."""
        s = scene()
        s.update(exporterVersion=22)
        s['tileGrid'].update(origin=[0.0, 0.0, 0.0], dimensions=[52, 39, 12], size=[96, 96, 64])
        s['cursorVolumes'] = [dict(name='whole', floor=1, stair=False, box=dict(min=[-10, -10, 0], max=[52 * 96 + 5, 39 * 96, 192])),
                              dict(name='house', floor=2, stair=False, box=dict(min=[100, 100, 192], max=[900, 39 * 96 - 0.5, 400])),
                              dict(name='step', floor=4, stair=True, box=dict(min=[0, 0, 0], max=[52 * 96, 39 * 96, 900]))]
        c = compiler.Compiler(document(stage={'grid': [60, 45, 18]}), s)
        c.map = 'URB_Bar'
        c.stage()
        got = c.cursor_storeys()
        self.assertEqual(got[0], (1, [-10, -10, 0, 60 * 96, 45 * 96, 192]))
        self.assertEqual(got[1], (2, [100, 100, 192, 900, 45 * 96, 400]))       # reaches Y's side only
        # from the plain volumes' top (400) to 1152: 752 units, four storeys, floors after the plain ones' highest
        self.assertEqual([(f, b[2], b[5]) for f, b in got[2:]], [(3, 400, 592), (4, 592, 784), (5, 784, 976), (6, 976, 1152)])
        self.assertTrue(all(b[:2] == [0.0, 0.0] and b[3:5] == [60 * 96, 45 * 96] for _, b in got[2:]))
        # the map's own size: its own, as they are
        c = compiler.Compiler(document(), s)
        c.map = 'URB_Bar'
        c.stage()
        self.assertEqual([f for f, _ in c.cursor_storeys()], [1, 2])

    def test_the_maps_own_size_is_no_resize(self):
        _, report = self.run_stage({'grid': [52, 39]})
        self.assertTrue(report['ok'])
        self.assertIsNone(report['stageGrid'])
        _, report = compiler.compile_project(document(), scene())
        self.assertIsNone(report['stageGrid'])

    def test_a_smaller_grid_is_refused(self):
        _, report = self.run_stage({'grid': [61, 30]})
        self.assertEqual(codes(report), ['stage-grid'])

    def test_a_grid_past_the_limit_is_refused_and_a_large_one_taken(self):
        """Up to 256 tiles a side (the user, 16 November 2026; 128 before), with no warning."""
        self.assertEqual(compiler.STAGE_GRID_MAX, 256)
        _, report = self.run_stage({'grid': [257, 39]})
        self.assertEqual(codes(report), ['stage-grid'])
        for grid in ([100, 39], [200, 39], [256, 256]):
            _, report = self.run_stage({'grid': grid})
            self.assertTrue(report['ok'], (grid, refused(report)))
            self.assertEqual(warned(report, 'stage-'), [])

    def test_a_map_past_the_limit_at_its_own_size_still_grows(self):
        """A map past the limit at its own size keeps its own as its limit on that axis, and the other axes keep 256
        tiles and 30 levels (stage_max; T-41: the Map grid snapped back on TempleShip, 45 by 203 by 15, while the
        limit was 128). A stand-in map 45 by 300 by 15 keeps the case now that TempleShip is under the limit."""
        self.assertEqual(compiler.stage_max([45, 300, 15]), [256, 300, 30])
        self.assertEqual(compiler.stage_max([45, 203, 15]), [256, 256, 30])
        self.assertEqual(compiler.stage_max([52, 39, 12]), [256, 256, 30])
        past = dict(dims=(45, 300, 15), name='TempleShip')
        for grid, want in (([46, 300], [46, 300, 15]), ([256, 300], [256, 300, 15]), ([45, 300, 16], [45, 300, 16]),
                           ([45, 300, 30], [45, 300, 30])):
            _, report = self.run_stage({'grid': grid}, **past)
            self.assertTrue(report['ok'], (grid, refused(report)))
            self.assertEqual(report['stageGrid'], want)
        for grid in ([257, 300], [45, 301], [45, 300, 31], [45, 256]):
            _, report = self.run_stage({'grid': grid}, **past)
            self.assertEqual(codes(report), ['stage-grid'], grid)
        # TempleShip itself grows deeper now, to 256
        temple = dict(dims=(45, 203, 15), name='TempleShip')
        for grid, want in (([45, 256], [45, 256, 15]), ([128, 230, 20], [128, 230, 20])):
            _, report = self.run_stage({'grid': grid}, **temple)
            self.assertTrue(report['ok'], (grid, refused(report)))
            self.assertEqual(report['stageGrid'], want)
        _, report = self.run_stage({'grid': [45, 257]}, **temple)
        self.assertEqual(codes(report), ['stage-grid'])
        # cleared: smaller on any axis, and never past its own 203 deep
        c = compiler.Compiler(document(cleared=True, stage={'grid': [40, 150, 8]}), dict(scene(), name='TempleShip'))
        c.scene['tileGrid'] = dict(c.scene['tileGrid'], dimensions=[45, 203, 15], size=[96, 96, 64])
        c.map = 'TempleShip'
        c.cleared_mark(); c.stage()
        self.assertEqual((c.mission_edits.stage_grid, [e['code'] for e in c.errors]), ([40, 150, 8], []))

    def test_a_malformed_stage_is_refused(self):
        for stage in ({'grid': [61]}, {'grid': [61.5, 39]}, {'grid': [61, 39], 'ground': 'yes'}, [61, 39], {'grid': [True, 39]},
                      {'grid': [61, 39, 18, 1]}, {'grid': [61, 39, 17.5]}, {'grid': [61, 39], 'lines': 'yes'}):
            _, report = self.run_stage(stage)
            self.assertEqual(codes(report), ['stage-shape'], stage)

    def test_a_map_without_a_grid_is_refused(self):
        s = scene()
        s['name'] = 'CB2_MP_Blank'
        s['tileGrid'].pop('dimensions', None)
        doc = document(stage={'grid': [61, 39]})
        doc['source'] = dict(doc['source'], map='CB2_MP_Blank')
        _, report = compiler.compile_project(doc, s)
        self.assertEqual(codes(report), ['stage-grid'])


FRAME = 'DGN_DropShipSoldierSpawn.Prefabs.SoldierSpawns_DrpshipVol.SoldierSpawns_DrpshipVol_12Arc0'
SKYRANGER = 'VEH_Lv1Skyranger_MOD.Prefabs.PRE_SkyrangerGrounded.PRE_SkyrangerGrounded_4Arc0'


def clear_scene():
    """Bar's grid (52 by 39 by 12) with floor on every ground tile, the landing's frame where Bar has it (its first
    line's place), its Skyranger, a few pieces, and the floor of the ground carried by XComLevelActor_9."""
    s = scene()
    s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
    s['objects'] += [part('XComLevelActor_60', at=(720, -1680, 0), archetype=FRAME),
                     part('XComLevelActor_61', at=(561, -2970, 0), archetype=SKYRANGER),
                     part('XComMergedLevelActor_62', cls='XComMergedLevelActor', at=(0, 600, 0),
                          componentTransform=transform([0, 0, 16], [0, 0, 0], [1, 1, 1]))]
    s['tactical'] = dict(floorTiles=[dict(tile=[x, y, 0], actor=PL + 'XComLevelActor_9') for x in range(52) for y in range(39)])
    s['objects'].append(part('XComLevelActor_9', at=(0, 0, 0)))
    return s


def everything(s):
    """The delete records of a clear: every base piece but the landing's."""
    return [dict(target=target(o['actor'].split('.')[-1]), deleted=True) for o in s['objects']
            if o['layer'] == 'base' and not compiler.is_landing(o)]


ZONE = dict(id='z1', location=[719, -1681, 64], direction='north', kind='normal')


# what `cleared: true` (schema 1 to 8) is read as: every part the Build clears, none keeping the outside
EVERY_PART = {'pieces': {}, 'lights': {}, 'effects': {}, 'triggers': {}}


class ClearTests(unittest.TestCase):
    """A cleared map, its size and its landing zones (private/plans/done/clear-map-plan.md, sections 4 and 6)."""

    def test_a_cleared_bar_compiles_with_no_error(self):
        s = clear_scene()
        spec, report = compile_project(document(everything(s), cleared=True), s)
        self.assertTrue(report['ok'], refused(report))
        # `cleared: true` (schema 1 to 8) is every part
        self.assertEqual(report['cleared'], EVERY_PART)
        # a merged actor (no family that builds) and a piece with a component offset are deleted all the same
        self.assertEqual(warned(report, 'delete-'), [])
        hides = next(o for o in spec['objects'] if o['type'] == 'hide')['alsoHide']
        self.assertIn('XComMergedLevelActor_62', hides)
        self.assertIn('XComLevelActor_5', hides)
        self.assertEqual(spec['cleared'], dict(grid=[52, 39, 12], parts=EVERY_PART))
        patch, native = compiler.native_split(spec)
        self.assertEqual(native['cleared'], dict(grid=[52, 39, 12], parts=EVERY_PART))
        self.assertNotIn('cleared', patch)
        # with the floor gone, the map's own landing stands on nothing: warned, never refused
        self.assertIn('landing-floor', warned(report))

    def test_a_cleared_maps_records_stream_none_of_its_patch_levels(self):
        # KB-23: Long War's patch levels go whole (pieces, lights, rebuild volumes, load scripts), so the Build makes
        # no copy of one, even for a ladder's helper; a mission's stream is left as it is
        s = clear_scene()
        helper = part('XComLadder_11', cls='XComLadder', at=(436, 1276, 14), mesh='ladder', layer='stream',
                      package='patch_bar', hidden=True)
        s['streams'] = {'patch_bar': dict(kind='lwr', objects=[helper], lights=[]),
                        'URB_Bar_CNH': dict(kind='mission', objects=[], lights=[], missionObjects=[])}
        spec, report = compile_project(document(everything(s), cleared=True), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertTrue(spec['dropPatches'])
        self.assertNotIn('patch_bar', spec.get('streamHides') or {})
        patch, native = compiler.native_split(spec)
        self.assertTrue(native['dropPatches'])
        self.assertNotIn('dropPatches', patch)
        # a map that isn't cleared streams them as before
        spec, _ = compile_project(document(everything(s)), s)
        self.assertNotIn('dropPatches', spec)

    def test_a_clear_that_keeps_the_scenery_outside_gives_the_build_the_play_area(self):
        s = clear_scene()
        o = s['tileGrid']['origin']
        # a level volume two tiles wider than the grid to the west and one longer to the north (viewer basis)
        s['playableBounds'] = b = dict(min=[o[0] - 192, 0, o[1]], max=[o[0] + 52 * 96, 768, o[1] + 40 * 96])
        # the play area: the level volume and the grid together, across (a larger grid reaches further)
        for grid, far in ((None, b['max'][0]), ([60, 45], s['tileGrid']['origin'][0] + 60 * 96)):
            doc = document(everything(s), cleared=True, clearKeepsOutside=True, **({'stage': {'grid': grid}} if grid else {}))
            spec, report = compile_project(doc, s)
            self.assertTrue(report['ok'], refused(report))
            # (schema 1 to 8: every part keeps the outside)
            self.assertEqual(report['cleared'], {k: dict(keepOutside=True) for k in EVERY_PART})
            box = spec['cleared']['parts']['pieces']['keepOutside']
            self.assertEqual([round(v) for v in box[:2]], [round(min(b['min'][0], s['tileGrid']['origin'][0])),
                                                           round(min(b['min'][2], s['tileGrid']['origin'][1]))])
            self.assertEqual(round(box[2]), round(max(b['max'][0], far)))
            self.assertEqual(compiler.native_split(spec)[1]['cleared']['parts'], {k: dict(keepOutside=box) for k in EVERY_PART})
        # a part each way (schema 9): only the one that keeps it gets the box
        spec, report = compile_project(document(everything(s), cleared={'pieces': {'keepOutside': True}, 'lights': {}}), s)
        self.assertEqual(report['cleared'], {'pieces': dict(keepOutside=True), 'lights': {}})
        self.assertEqual(sorted(spec['cleared']['parts']), ['lights', 'pieces'])
        self.assertEqual((sorted(spec['cleared']['parts']['pieces']), spec['cleared']['parts']['lights']), (['keepOutside'], {}))
        # without it, or without the clear, no box; a value not true or false is refused
        spec, _ = compile_project(document(everything(s), cleared=True, clearKeepsOutside=False), s)
        self.assertFalse(any(spec['cleared']['parts'].values()))
        spec, report = compile_project(document(clearKeepsOutside=True), s)
        self.assertIsNone(report['cleared'])
        _, report = compile_project(document(cleared=True, clearKeepsOutside='yes'), s)
        self.assertEqual(codes(report), ['cleared-shape'])

    def test_a_clear_takes_the_maps_triggers_unless_it_keeps_them(self):
        # F-159: the Build's clear_level takes the map's trigger volumes and sight points out, unless `clearKeepsTriggers`
        s = clear_scene()
        spec, report = compile_project(document(everything(s), cleared=True), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertIn('triggers', compiler.native_split(spec)[1]['cleared']['parts'])
        # (schema 1 to 8) `clearKeepsTriggers`: every part but the triggers
        spec, report = compile_project(document(everything(s), cleared=True, clearKeepsTriggers=True), s)
        self.assertEqual(sorted(compiler.native_split(spec)[1]['cleared']['parts']), ['effects', 'lights', 'pieces'])
        self.assertNotIn('triggers', report['cleared'])
        # without the clear it says nothing; a value not true or false is left out
        _, report = compile_project(document(clearKeepsTriggers=True), s)
        self.assertIsNone(report['cleared'])
        _, report = compile_project(document(cleared=True, clearKeepsTriggers='yes'), s)
        self.assertEqual(codes(report), ['cleared-shape'])

    def test_one_part_alone_leaves_the_rest_of_the_map_as_it_is(self):
        # the clear-by-parts plan, section 2: a part without the pieces neither lets the grid shrink nor drops Long
        # War's patch levels; it goes to the Build alone
        s = clear_scene()
        s['streams'] = {'patch_bar': dict(kind='lwr', objects=[], lights=[])}
        for part in ('lights', 'effects', 'triggers'):
            spec, report = compile_project(document(cleared={part: {}}), s)
            self.assertTrue(report['ok'], refused(report))
            self.assertEqual((report['cleared'], spec['cleared']['parts']), ({part: {}}, {part: {}}), part)
            self.assertNotIn('dropPatches', spec)
            _, report = compile_project(document(cleared={part: {}}, stage={'grid': [40, 30]}), s)
            self.assertEqual(codes(report), ['stage-grid'], part)
        # the pieces alone: the grid may shrink, the patch levels dropped
        spec, report = compile_project(document(everything(s), cleared={'pieces': {}}, stage={'grid': [40, 30]}), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual((spec['cleared'], spec.get('dropPatches')), (dict(grid=[40, 30, 12], parts={'pieces': {}}), True))
        # nothing cleared: no mark
        spec, report = compile_project(document(cleared={}), s)
        self.assertEqual((report['cleared'], spec.get('cleared')), (None, None))

    def test_a_part_it_cannot_read_is_left_out_and_the_rest_cleared(self):
        s = clear_scene()
        for bad in ({'roofs': {}}, {'lights': True}, {'lights': {'keepOutside': 'yes'}}, {'lights': {'keep': True}}):
            spec, report = compile_project(document(cleared=dict(bad, triggers={})), s)
            self.assertEqual(codes(report), ['cleared-shape'], bad)
            self.assertEqual(report['cleared'], {'triggers': {}}, bad)
            self.assertEqual(spec['cleared']['parts'], {'triggers': {}}, bad)

    def test_a_map_as_it_is_only_grows(self):
        s = clear_scene()
        # smaller, or fewer levels, until it is cleared: refused
        for grid in ([40, 30, 8], [52, 39, 8]):
            _, report = compile_project(document(stage={'grid': grid}), s)
            self.assertEqual(codes(report), ['stage-grid'], grid)
        # larger (the user, 13 November 2026): taken, with a note on what the Build does with the new area
        spec, report = compile_project(document(stage={'grid': [60, 45]}), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['stageGrid'], [60, 45, 12])
        self.assertIn('stage-grown-map', noted(report))
        _, report = compile_project(document(cleared='yes'), s)
        self.assertEqual(codes(report), ['cleared-shape'])
        self.assertEqual((report['ok'], report['cleared']), (True, None))       # left out: not cleared (finding 39)

    def test_a_cleared_maps_grid_may_be_smaller_or_larger(self):
        s = clear_scene()
        for grid, want in (([40, 30, 8], [40, 30, 8]), ([60, 45], [60, 45, 12]), ([52, 39, 1], [52, 39, 1])):
            spec, report = compile_project(document(everything(s), cleared=True, stage={'grid': grid}), s)
            self.assertTrue(report['ok'], (grid, refused(report)))
            self.assertEqual(report['stageGrid'], want)
            self.assertEqual(spec['cleared'], dict(grid=want, parts=EVERY_PART))
        for grid in ([0, 30], [52, 257], [52, 39, 31], [52, 39, 0]):
            _, report = compile_project(document(cleared=True, stage={'grid': grid}), s)
            self.assertEqual(codes(report), ['stage-grid'], grid)
        _, report = compile_project(document(cleared=True, stage={'grid': [52, 39], 'ground': False}), s)
        self.assertIn('stage-ground', noted(report))

    def test_pieces_outside_a_smaller_grid_are_warned_of(self):
        s = clear_scene()
        far = add('XComLevelActor_2', 1, (2000, 0, 0))
        _, report = compile_project(document(everything(s), [far], cleared=True, stage={'grid': [20, 39]}), s)
        self.assertTrue(report['ok'], refused(report))
        w = next(d for d in report['warnings'] if d['code'] == 'stage-outside')
        self.assertEqual(w['names'], ['XComLevelActor_2_copy1'])
        # and the map's landing, outside a grid 20 tiles across (its frame stands 36 tiles in)
        self.assertIn('landing-outside', warned(report))
        # a piece sunk into the ground still reaches the grid (its box 0 to 100 high, here -60 to 40), one wholly under
        # it does not; a light outside is no problem (the user, 14 November 2026: warnings for what can cause one)
        sunk, under = add('XComLevelActor_2', 2, (0, 0, -60)), add('XComLevelActor_2', 3, (0, 96, -200))
        _, report = compile_project(document(everything(s), [sunk, under], cleared=True, stage={'grid': [40, 39]}), s)
        self.assertEqual(next(d for d in report['warnings'] if d['code'] == 'stage-outside')['names'], ['XComLevelActor_2_copy3'])

    def test_the_maps_low_scenery_in_a_grown_area_is_floor_for_a_zone(self):
        # Bar grown as it is from 52 to 62 tiles along X: a flat level actor of the map past its far X side (x 2208)
        # is made walkable by the Build (F-100), so a zone on it has floor; without it, or deleted, it has none
        s = clear_scene()
        s['meshes']['flat'] = dict(bounds=[0, 0, 0, 480, 480, 0, 700])
        plane = part('XComLevelActor_70', at=(2700, -1200, 0), mesh='flat')
        zone = dict(ZONE, location=[2700, -1200, 64])
        grown = dict(stage={'grid': [62, 39]}, landingZones=[zone])
        _, report = compile_project(document(**grown), dict(s, objects=s['objects'] + [plane]))
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('landing-floor', warned(report))
        _, report = compile_project(document(**grown), s)
        self.assertIn('landing-floor', warned(report))
        _, report = compile_project(document([dict(target=target('XComLevelActor_70'), deleted=True)], **grown),
                                    dict(s, objects=s['objects'] + [plane]))
        self.assertIn('landing-floor', warned(report))

    def test_a_small_grid_leaves_no_room_for_lwrs_pods(self):
        s = clear_scene()
        _, report = compile_project(document(cleared=True, stage={'grid': [52, 39]}), s)
        self.assertNotIn('stage-small', warned(report))
        zone = dict(ZONE, location=[-2784 + 18 * 96, -1920 + 12 * 96, 64])
        _, report = compile_project(document(cleared=True, stage={'grid': [36, 36]}, landingZones=[zone]), s)
        self.assertIn('stage-small', warned(report))

    def test_an_area_light_whose_glowing_piece_is_not_settled_goes_with_a_clear(self):
        s = clear_scene()
        s['objects'][0]['areaLights'] = ['light:9']
        s['lights'] = [dict(id='light:9', actor=PL + 'GeneratedMeshAreaLight_9', role='area', layer='base',
                            sourcePackage='URB_Bar', actorClass='GeneratedMeshAreaLight', location=[0, 0, 50],
                            rotation=[0, 0, 0], radius=100, emitterAttachment=dict(status='ambiguous', candidates=[]))]
        doc = document([dict(target=target('XComLevelActor_1'), deleted=True)])
        _, report = compile_project(doc, s)
        self.assertIn('area-light-unresolved', noted(report))
        _, report = compile_project(dict(doc, cleared=True), s)
        self.assertNotIn('area-light-unresolved', noted(report))

    def test_landing_zones_checked_and_carried(self):
        s = clear_scene()
        spec, report = compile_project(document(landingZones=[ZONE]), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['ownLandings'], 1)
        self.assertEqual(warned(report, 'landing'), [])
        self.assertEqual(spec['landingZones'], dict(zones=[ZONE], own=[0], ownLandings=1))
        _, native = compiler.native_split(spec)
        self.assertEqual(native['landingZones']['zones'], [ZONE])
        # a second zone plays under LWR only; one kept for a mission is LWR's alone; one with no line plays nowhere
        second = dict(ZONE, id='z2', location=[1103, 1583, 64], direction='south')
        mission = dict(ZONE, id='z0', missionType='eMission_Abduction')
        unused = dict(second, id='z3', lwr=False)
        spec, report = compile_project(document(landingZones=[mission, ZONE, second, unused]), s)
        self.assertEqual(spec['landingZones']['own'], [1])
        lwr_only = next(d for d in report['warnings'] if d['code'] == 'landing-lwr-only')
        self.assertEqual(lwr_only['zones'], [1, 3])
        self.assertEqual(next(d for d in report['warnings'] if d['code'] == 'landing-unused')['zones'], [4])
        # marked Plain EW (the panel's tick): the marked zone is the map's own landing, wherever it stands in the list
        marked = dict(second, ew=True)
        spec, report = compile_project(document(landingZones=[ZONE, marked]), s)
        self.assertEqual(spec['landingZones']['own'], [1])
        self.assertEqual(spec['landingZones']['zones'][1]['ew'], True)
        self.assertEqual(next(d for d in report['warnings'] if d['code'] == 'landing-lwr-only')['zones'], [1])
        # more marked than the map has landings: the extra are LWR's, warned of; none marked of a marked list: fewer
        spec, report = compile_project(document(landingZones=[dict(ZONE, ew=True), marked]), s)
        self.assertEqual(spec['landingZones']['own'], [0])
        self.assertEqual(next(d for d in report['warnings'] if d['code'] == 'landing-ew-extra')['zones'], [2])
        self.assertNotIn('landing-ew-fewer', warned(report))
        # a map with three landings of its own and one zone marked: plain EW also lands at the other two where they are
        s3 = clear_scene()
        s3['objects'] += [part('XComLevelActor_70', at=(-1200, 600, 0), archetype=FRAME),
                          part('XComLevelActor_71', at=(1200, 600, 0), archetype=FRAME)]
        _, report = compile_project(document(landingZones=[ZONE, marked]), s3)
        self.assertEqual(report['ownLandings'], 3)
        self.assertEqual(next(d for d in report['warnings'] if d['code'] == 'landing-ew-fewer')['missing'], 2)
        _, report = compile_project(document(landingZones=[dict(ZONE, ew=1)]), s)
        self.assertIn('landing-shape', codes(report))
        # none
        _, report = compile_project(document(landingZones=[]), s)
        self.assertEqual(warned(report, 'landing'), ['landing-none'])
        # malformed (review finding 39): the zone is left out and the rest are the variant's; a list that is no list,
        # or whose zones are all left out, is as none (the base map's lines copied), never a refusal
        for zones, kept in (('none', None), ([dict(ZONE, direction='up')], None), ([ZONE, ZONE], [ZONE]),
                            ([dict(ZONE, direction='up'), second], [second])):
            spec, report = compile_project(document(landingZones=zones), s)
            self.assertTrue(report['ok'], refused(report))
            self.assertIn('landing-shape', [d['code'] for d in report['leftOut']])
            self.assertEqual((spec.get('landingZones') or {}).get('zones'), kept)

    def test_a_zone_over_no_floor_or_under_a_piece(self):
        s = clear_scene()
        # the ground's floor is gone with its piece
        doc = document([dict(target=target('XComLevelActor_9'), deleted=True)], landingZones=[ZONE])
        _, report = compile_project(doc, s)
        w = next(d for d in report['warnings'] if d['code'] == 'landing-floor')
        self.assertEqual(w['points'], [1, 2, 3, 4, 5, 6])
        # a tall piece put on soldier point 4 (Bar's first line: 719, -1681 + 288)
        crate = add('XComLevelActor_2', 1, (719, -1393, 0))
        _, report = compile_project(document(added=[crate], landingZones=[ZONE]), s)
        self.assertIn('landing-blocked', warned(report))
        self.assertIn('XComLevelActor_2_copy1', next(d for d in report['warnings'] if d['code'] == 'landing-blocked')['message'])


class FakeLibrary:
    """The library as the compiler asks it: pieces of URB_PoliceStation, by actor."""

    def __init__(self, fail=None, **entry):
        self.fail, self.entry, self.asked = fail, entry, []

    def record(self, wanted, sky=False):
        self.asked.append(wanted)
        if self.fail:
            raise compiler.LibraryError(self.fail, 'the library says %s' % self.fail)
        name = short(wanted['actor'])
        cls = self.entry.get('actorClass', 'XComLevelActor')
        whole = self.entry.get('whole')     # an assembly: {family, parts: {actor: class}}, its first part the pivot
        parts = whole['parts'] if whole else {name: cls}
        objs = [part(n, cls=c, at=(5000, 5000, 0), package='URB_PoliceStation', mesh='lamp') for n, c in parts.items()]
        record = dict(version=4, key='k', grid=self.entry.get('grid'),
                      source=dict(package='URB_PoliceStation', level='base', actor=name, sha256=DONOR_SHA),
                      objects=objs, meshes={'lamp': dict(bounds=[0, 0, 100, 10, 10, 100, 101])})
        entry = dict(key='k', actorClass=cls, placeable=True, reason=None)
        if whole:
            members = [PL + n for n in parts]
            record['assembly'] = dict(family=whole['family'], members=sorted(members), pivot=members[0], leaves=[])
            entry.update(family=whole['family'], assembly=dict(family=whole['family'], members=len(members)))
        return record, dict(entry, **{k: v for k, v in self.entry.items() if k != 'whole'})


def map_building_scene():
    """A scene of export 21 with three buildings of the map: a shed of two floors (one box each), a van's own building
    and one the Kismet names (its floor volume)."""
    s = scene()
    s['exporterVersion'] = 21
    s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
    box = lambda *v: dict(min=list(v[:3]), max=list(v[3:]))
    floor = lambda volumes, boxes: dict(volumes=[PL + v for v in volumes], plain=[True] * len(volumes), boxes=boxes, members=[])
    s['buildings'] = [
        dict(id='11', name=PL + 'XComBuildingVolume_2', actor='XComBuildingVolume_2', level='PersistentLevel', isUfo=False,
             referencedBy=[], van=False, floors=[floor(['XComFloorVolume_3'], [box(0, 0, 16, 384, 384, 208)]),
                                                 floor(['XComFloorVolume_4'], [box(0, 0, 208, 384, 384, 400)])]),
        dict(id='12', name=PL + 'XComBuildingVolume_1', actor='XComBuildingVolume_1', level='PersistentLevel', isUfo=False,
             referencedBy=[], van=True, floors=[floor(['XComFloorVolume_5'], [box(1000, 0, 16, 1200, 96, 200)])]),
        dict(id='13', name=PL + 'XComBuildingVolume_6', actor='XComBuildingVolume_6', level='PersistentLevel', isUfo=True,
             referencedBy=['SeqAct_Toggle_0 Target'], van=False,
             floors=[floor(['XComFloorVolume_7'], [box(-960, 0, 16, -576, 384, 208)])])]
    return s


class MapBuildingTests(unittest.TestCase):
    """The map's own buildings changed or deleted (Compiler.buildings; map buildings plan, sections 2 and 3)."""
    SHED = 'map:PersistentLevel.XComBuildingVolume_2'

    def shed(self, *floors, **more):
        """A record for the shed: floors as [(volume or None, box)]."""
        floors = floors or ([('XComFloorVolume_3', [0, 0, 16, 384, 384, 208])], [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])
        return dict(dict(id=self.SHED, name='XComBuildingVolume_2', kind='building',
                         replaces=target('XComBuildingVolume_2'),
                         floors=[dict(boxes=[list(b) for _, b in f], volumes=[v for v, _ in f]) for f in floors]), **more)

    def compiled(self, buildings, scene=None, **doc):
        spec, report = compile_project(document(buildings=buildings, **doc), scene or map_building_scene())
        edits = compiler.native_split(spec)[1].get('buildingEdits', []) if spec else None
        return spec, report, edits

    def test_unchanged_builds_nothing(self):
        spec, report, edits = self.compiled([self.shed()])
        self.assertEqual((codes(report), report['warnings'], edits), ([], [], []))
        # within 0.01 of the export's box is the same; the name alone is no edit for the Build
        spec, report, edits = self.compiled([self.shed([('XComFloorVolume_3', [0, 0, 16.004, 384, 384, 208])],
                                                  [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])], name='Shed')])
        self.assertEqual((codes(report), edits), ([], []))

    def test_a_box_stretched(self):
        spec, report, edits = self.compiled([self.shed([('XComFloorVolume_3', [0, 0, 16, 480, 384, 208])],
                                                  [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])])
        self.assertEqual((codes(report), report['warnings']), ([], []))
        self.assertEqual(len(edits), 1)
        e = edits[0]
        self.assertEqual((e['actor'], e['deleted'], e['moved'], e['kind']), ('XComBuildingVolume_2', False, False, 'building'))
        self.assertEqual(e['floors'][0], dict(boxes=[[0.0, 0.0, 16.0, 480.0, 384.0, 208.0]], volumes=['XComFloorVolume_3']))
        self.assertEqual(e['old'][1], [dict(volume='XComFloorVolume_4', box=[0, 0, 208, 384, 384, 400])])
        self.assertEqual(report['mapBuildings'], [dict(id=self.SHED, actor='XComBuildingVolume_2', floors=2, moved=False)])

    def test_a_floor_added_on_top_and_below(self):
        ground, roof = ('XComFloorVolume_3', [0, 0, 16, 384, 384, 208]), ('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])
        _, report, edits = self.compiled([self.shed([ground], [roof], [(None, [0, 0, 400, 384, 384, 592])])])
        self.assertEqual((codes(report), len(edits[0]['floors']), edits[0]['floors'][2]['volumes']), ([], 3, [None]))
        below = [(None, [0, 0, -176, 384, 384, 16])]
        _, report, edits = self.compiled([self.shed(below, [ground], [roof])])
        self.assertEqual([f['volumes'] for f in edits[0]['floors']], [[None], ['XComFloorVolume_3'], ['XComFloorVolume_4']])

    def test_moved_whole(self):
        shift = lambda b, dx, dy=0: [b[0] + dx, b[1] + dy, b[2], b[3] + dx, b[4] + dy, b[5]]
        _, report, edits = self.compiled([self.shed([('XComFloorVolume_3', shift([0, 0, 16, 384, 384, 208], 192, 96))],
                                               [('XComFloorVolume_4', shift([0, 0, 208, 384, 384, 400], 192, 96))])])
        self.assertTrue(edits[0]['moved'])
        # a quarter turn about the shed's middle is a move too; one floor moved is not
        self.assertTrue(compiler.moved_whole([[dict(volume='a', box=[0, 0, 0, 384, 192, 100])]],
                                             [dict(boxes=[[96, -96, 0, 288, 288, 100]], volumes=['a'])]))
        _, report, edits = self.compiled([self.shed([('XComFloorVolume_3', shift([0, 0, 16, 384, 384, 208], 192))],
                                               [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])])
        self.assertFalse(edits[0]['moved'])

    def test_a_piece_moved_with_its_building_stands_in_it(self):
        # the floor a moved piece's copy stands in is looked up in the buildings as the project has them; the cursor
        # says nothing of a box at its volume's own height (moved sideways), only of one raised or lowered
        s = map_building_scene()
        for o in s['objects']:
            if o['actor'] == PL + 'XComLevelActor_2':
                o['floors'] = [dict(building='11', floor=0, cutdownFloor=0)]
        ox, oy, oz = s['tileGrid']['origin'][:3]
        s['cursorVolumes'] = [dict(name='c%d' % n, floor=n + 1, stair=False, box=dict(min=[ox, oy, oz + z0], max=[ox + 5000, oy + 4000, oz + z1]))
                              for n, (z0, z1) in enumerate(((0, 300), (300, 600)))]
        piece = [dict(target=target('XComLevelActor_2'), location=[96, 960, 0], rotation=[0, 0, 0])]
        north = lambda b: [b[0], b[1] + 960, b[2], b[3], b[4] + 960, b[5]]
        shed = self.shed([('XComFloorVolume_3', north([0, 0, 16, 384, 384, 208]))], [('XComFloorVolume_4', north([0, 0, 208, 384, 384, 400]))])
        _, report, edits = self.compiled([shed], s, overrides=piece)
        self.assertEqual((codes(report), report['warnings']), ([], []))
        self.assertTrue(edits[0]['moved'])
        # the piece moved without its building: its copy stands in no floor
        _, report, _ = self.compiled([], s, overrides=piece)
        self.assertEqual(noted(report), ['building-floor'])
        # the building moved without the piece: nothing to say (the piece stays, listed by the rule at its place)
        _, report, _ = self.compiled([shed], s)
        self.assertEqual(report['warnings'], [])
        # a floor raised away from the cursor's floors is warned of
        raised = self.shed([('XComFloorVolume_3', north([0, 0, 16, 384, 384, 240]))], [('XComFloorVolume_4', north([0, 0, 240, 384, 384, 400]))])
        _, report, _ = self.compiled([raised], s)
        self.assertEqual(warned(report), ['building-cursor'])

    def test_deleted(self):
        spec, report, edits = self.compiled([dict(id=self.SHED, replaces=target('XComBuildingVolume_2'), deleted=True)])
        self.assertEqual((codes(report), report['warnings']), ([], []))
        self.assertEqual([(e['actor'], e['deleted']) for e in edits], [('XComBuildingVolume_2', True)])
        self.assertEqual(report['mapBuildings'], [dict(id=self.SHED, actor='XComBuildingVolume_2', deleted=True)])

    def test_the_package_is_the_map_whatever_its_case(self):
        # the page writes the export's name, which can differ in case from the map record's (CsmallScout_Farm)
        gone = dict(id=self.SHED, replaces=target('XComBuildingVolume_2', package='urb_bar'), deleted=True)
        spec, report, edits = self.compiled([gone])
        self.assertEqual((codes(report), report['warnings']), ([], []))
        self.assertEqual([(e['actor'], e['deleted']) for e in edits], [('XComBuildingVolume_2', True)])

    def test_one_the_kismet_names_is_warned_of(self):
        rec = dict(id='map:PersistentLevel.XComBuildingVolume_6', replaces=target('XComBuildingVolume_6'), deleted=True)
        _, report, edits = self.compiled([rec])
        self.assertEqual((codes(report), warned(report)), ([], ['mission-linked']))
        self.assertEqual(len(edits), 1)
        moved = dict(id=rec['id'], name='Pod', kind='ufo', replaces=rec['replaces'],
                     floors=[dict(boxes=[[-960, 96, 16, -576, 480, 208]], volumes=['XComFloorVolume_7'])])
        _, report, edits = self.compiled([moved])
        self.assertEqual((warned(report), edits[0]['kind'], edits[0]['moved']), (['mission-linked'], 'ufo', True))

    def test_an_overlap_with_a_changed_box_is_warned_of(self):
        # the shed's ground floor stretched into the Kismet building: one warning; their own boxes, as exported, none
        _, report, edits = self.compiled([self.shed([('XComFloorVolume_3', [-700, 0, 16, 384, 384, 208])],
                                               [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])])
        self.assertEqual((codes(report), warned(report)), ([], ['building-overlap']))
        self.assertIn("map's own building XComBuildingVolume_6", report['warnings'][0]['message'])
        # and stretched up into its own roof floor
        _, report, _ = self.compiled([self.shed([('XComFloorVolume_3', [0, 0, 16, 384, 384, 300])],
                                           [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])])
        self.assertEqual(warned(report), ['building-overlap'])
        self.assertIn('the same building', report['warnings'][0]['message'])

    def test_records_the_compiler_cannot_use_are_passed_over(self):
        van = dict(id='map:PersistentLevel.XComBuildingVolume_1', replaces=target('XComBuildingVolume_1'), deleted=True)
        nobody = dict(id='map:PersistentLevel.XComBuildingVolume_99', replaces=target('XComBuildingVolume_99'), deleted=True)
        twice = dict(self.shed(), id='other')
        for recs in ([van], [nobody], [self.shed(), twice]):
            spec, report, edits = self.compiled(recs)
            self.assertEqual((codes(report), warned(report), edits), ([], ['building-replaces'], []), recs)
        # an older export has no actors to match
        old = map_building_scene()
        old['exporterVersion'] = 20
        _, report, edits = self.compiled([dict(self.shed(), floors=[dict(boxes=[[0, 0, 16, 480, 384, 208]], volumes=['XComFloorVolume_3'])])], old)
        self.assertEqual((warned(report), edits), (['building-replaces'], []))
        self.assertIn('export 21', report['warnings'][0]['message'])
        # a volume that is not the building's, or named twice, gets a new box's
        _, report, edits = self.compiled([self.shed([('XComFloorVolume_7', [0, 0, 16, 384, 384, 208])],
                                               [('XComFloorVolume_4', [0, 0, 208, 384, 384, 400])])])
        self.assertEqual((warned(report), edits[0]['floors'][0]['volumes']), (['building-replaces'], [None]))

    def test_the_shape_is_checked(self):
        for bad in (dict(self.shed(), floors=[dict(boxes=[[0, 0, 16, 384, 384, 208]])]),
                    dict(self.shed(), floors=[dict(boxes=[[0, 0, 16, 384, 384, 208]], volumes=[])]),
                    dict(id=self.SHED, replaces=target('XComBuildingVolume_2'), deleted=True, floors=[]),
                    dict(id=self.SHED, deleted=True),
                    dict(self.shed(), replaces=dict(package='URB_Bar', actor=PL + 'XComBuildingVolume_2')),
                    dict(id='b', name='Hut', floors=[dict(boxes=[[0, 0, 0, 96, 96, 96]], volumes=[None])])):
            _, report, _ = self.compiled([bad])
            self.assertEqual(codes(report), ['building-shape'], bad)
            self.assertTrue(report['ok'], bad)          # left out, the rest built (review finding 39)
        # one bad record among good ones: only it is left out
        _, report, _ = self.compiled([dict(id='b', name='Hut', floors=[dict(boxes=[[0, 0, 0, 96, 96, 96]], volumes=[None])]),
                                      self.shed()])
        self.assertEqual(([d['record'] for d in report['leftOut']], report['ok']), (['buildings[0]'], True))

    def test_a_group_may_hold_a_map_building_with_no_record(self):
        g = dict(id='g', locked=True, breakTogether=False, members=[target('XComLevelActor_1'), dict(building=self.SHED)])
        _, report, _ = self.compiled([], groups=[g])
        self.assertEqual((codes(report), warned(report, 'group')), ([], []))
        # a van's building, or a deleted one, is no member
        gone = dict(id=self.SHED, replaces=target('XComBuildingVolume_2'), deleted=True)
        _, report, _ = self.compiled([gone], groups=[g])
        self.assertEqual(warned(report, 'group'), ['group-member'])
        van = dict(g, members=[target('XComLevelActor_1'), dict(building='map:PersistentLevel.XComBuildingVolume_1')])
        _, report, _ = self.compiled([], groups=[van])
        self.assertEqual(warned(report, 'group'), ['group-member'])


class BuildingTests(unittest.TestCase):
    """A project's buildings made from nothing (Compiler.buildings; prefab plan 5.1)."""
    GROUND, ABOVE = [0, 0, 0, 576, 576, 176], [0, 0, 176, 576, 576, 384]

    def hut(self, *floors, **more):
        return dict(id='b1', name='Hut', kind='building',
                    floors=[dict(boxes=[list(x) for x in boxes]) for boxes in (floors or ([self.GROUND], [self.ABOVE]))],
                    **more)

    def run_buildings(self, buildings, enable=('building',), own=()):
        s = scene()
        s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
        if own:
            s['exporterVersion'] = max(s.get('exporterVersion') or 0, 15)
            s['buildings'] = list(own)
        return compiler.compile_project(document(buildings=buildings), s, enable)

    def test_groups_nest_and_break_by_their_own_pieces(self):
        g = lambda gid, *members, **more: dict(dict(id=gid, locked=True, breakTogether=False, members=list(members)), **more)
        piece = lambda n: target('XComLevelActor_%d' % n)
        run = lambda *groups: compile_project(document(groups=list(groups)), scene())[1]
        inner, other = g('a', piece(1), piece(2)), g('b', piece(3), piece(4))
        report = run(inner, other, g('c', dict(group='a'), dict(group='b')))
        self.assertEqual(codes(report), [])
        self.assertEqual([e['id'] for e in report['groups']], ['a', 'b', 'c'])
        # a group of one group and one piece; a group that breaks together skips the group inside it
        self.assertEqual(codes(run(inner, g('c', dict(group='a'), piece(3), breakTogether=True))), [])
        # named groups must be the project's, in one group at most, and in no loop: else a note (refused until review
        # finding 39; nothing of nesting reaches the game, so the groups build as they are)
        nested = lambda report: (codes(report), [n['code'] for n in report['notes'] if n['code'] == 'group-nesting'])  # noqa: E731
        self.assertEqual(nested(run(inner, g('c', dict(group='zz'), piece(3)))), ([], ['group-nesting']))
        self.assertEqual(nested(run(g('a', dict(group='a'), piece(1)))), ([], ['group-nesting']))
        self.assertEqual(nested(run(inner, g('c', dict(group='a'), piece(3)), g('d', dict(group='a'), piece(4)))), ([], ['group-nesting']))
        self.assertEqual(nested(run(g('a', dict(group='b'), piece(1)), g('b', dict(group='a'), piece(2)))), ([], ['group-nesting']))

    def test_a_group_holds_lights_and_buildings_which_only_move_with_it(self):
        g = lambda gid, *members, **more: dict(dict(id=gid, locked=True, breakTogether=False, members=list(members)), **more)
        piece = lambda n: target('XComLevelActor_%d' % n)

        def run(*groups, **doc):
            s = light_scene()
            s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
            _, report = compiler.compile_project(document(groups=list(groups), **doc), s, ('building', 'light'))
            return codes(report), [w['code'] for w in report['warnings'] + report['notes'] if w['code'].startswith('group')]
        hut = self.hut()
        # a piece, a light of the map, a light the project adds and a building of the project: one group
        add = light_add('SpotLight_41', 3, (300, 0, 300))
        mixed = g('a', piece(1), target('PointLight_40'), dict(added=add['actor']), dict(building='b1'))
        self.assertEqual(run(mixed, added=[add], buildings=[hut]), ([], []))
        # a group placed from a prefab carries the prefab's mark, which the Build passes over
        self.assertEqual(run(dict(mixed, prefab=dict(id='p1', name='Hut', revision=2)), added=[add], buildings=[hut]), ([], []))
        # breaking together passes over them without a word: only its pieces are counted (here one, so nothing links)
        errors, warnings = run(dict(mixed, breakTogether=True), added=[add], buildings=[hut])
        self.assertEqual((errors, sorted(set(warnings))), ([], ['group-unbreakable']))
        # a building that is not the project's is said and ignored
        self.assertEqual(run(g('a', piece(1), dict(building='zz')), buildings=[hut]), ([], ['group-member']))
        self.assertEqual(compiler.member_key(dict(building='b1')), 'building|b1')
        self.assertIsNone(compiler.member_key(dict(building=3)))

    def test_a_floor_that_misses_the_cursors_floors_is_warned_of(self):
        def run(cursor, *floors, version=20):
            s = scene()
            s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
            s['exporterVersion'] = version
            s['cursorVolumes'] = cursor
            _, report = compiler.compile_project(document(buildings=[self.hut(*floors)]), s, ('building',))
            self.assertEqual(codes(report), [])
            return [w for w in report['warnings'] if w['code'] == 'building-cursor']
        ox, oy, oz = scene()['tileGrid']['origin'][:3]
        bar = [dict(name='c%d' % n, floor=n + 1, stair=False, box=dict(min=[ox, oy, oz + z0], max=[ox + 5000, oy + 4000, oz + z1]))
               for n, (z0, z1) in enumerate(((0, 210), (210, 402), (402, 594)))]
        at = lambda z0, z1: [[ox, oy, oz + z0, ox + 576, oy + 576, oz + z1]]
        # the hut's floors start at 0 and 176: within reach of the bar's cursor floors at 0 and 210? 176 is 34 away
        warned = run(bar, at(0, 176), at(176, 384))
        self.assertEqual([w['floor'] for w in warned], [1])
        self.assertIn('210', warned[0]['message'])
        self.assertEqual(run(bar, at(0, 200), at(200, 392)), [])
        # a map with no cursor volumes gets even storeys of 192 from the Build
        self.assertEqual(run([], at(0, 184), at(184, 376)), [])
        self.assertEqual([w['floor'] for w in run([], at(0, 256), at(256, 512))], [1])
        # a stair volume is no storey, and an older export says nothing
        stair = [dict(bar[0]), dict(bar[1], stair=True)]
        self.assertEqual(run(stair, at(0, 100), at(100, 300))[0]['starts'], [round(oz, 2)])
        self.assertEqual(run(bar, at(0, 100), at(100, 300), version=19), [])

    def test_a_building_whose_floors_are_the_cursors(self):
        """The building cursor floors plan: with `cursorFloors` a building's floor boxes are the cursor's floors over it
        (made_cursors, FloorEdits.cursor_areas): it isn't held to the map's (building-cursor), the tick goes to the
        native edit and the report, a note says where its floors start, and a floor out of order and a stair volume
        under it are warned of."""
        ox, oy, oz = scene()['tileGrid']['origin'][:3]
        bar = [dict(name='c%d' % n, floor=n + 1, stair=False, box=dict(min=[ox, oy, oz + z0], max=[ox + 5000, oy + 4000, oz + z1]))
               for n, (z0, z1) in enumerate(((0, 210), (210, 402), (402, 594)))]
        at = lambda z0, z1: [[ox, oy, oz + z0, ox + 576, oy + 576, oz + z1]]  # noqa: E731

        def sc(cursor=bar):
            s = scene()
            s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
            s['exporterVersion'] = 20
            s['cursorVolumes'] = cursor
            return s

        def run(*buildings, cursor=bar):
            return compiler.compile_project(document(buildings=list(buildings)), sc(cursor), ('building',))
        hut = self.hut(at(0, 176), at(176, 384), cursorFloors=True)
        spec, report = run(hut)
        self.assertEqual(codes(report), [])
        self.assertEqual(warned(report, 'building-cursor'), [])         # (without the tick floor 1 would be: 176 is 34 off 210)
        self.assertEqual(report['buildings'], [dict(id='b1', name='Hut', kind='building', floors=2, cursorFloors=True)])
        self.assertTrue(native_split(spec)[1]['buildings'][0]['cursorFloors'])
        notes = [n for n in report['notes'] if n['code'] == 'building-cursor-floors']
        self.assertEqual(len(notes), 1)
        self.assertIn('1 from %g, 2 from %g' % (oz, oz + 176), notes[0]['message'])
        # the cursor's floors: over the hut its own, each 2 under its box; off it the bar's
        c = compiler.Compiler(document(buildings=[hut]), sc())
        c.map = 'URB_Bar'
        c.stage()
        got = c.cursor_storeys()
        self.assertEqual(sorted((b[2], b[5], f) for f, b in got if b[0] <= ox + 100 <= b[3] and b[1] <= oy + 100 <= b[4]),
                         [(oz - 2, oz + 174, 1), (oz + 174, oz + 384, 2)])
        self.assertEqual(sorted((b[2], f) for f, b in got if b[0] <= ox + 1000 <= b[3] and b[1] <= oy + 100 <= b[4]),
                         [(oz, 1), (oz + 210, 2), (oz + 402, 3)])
        # without the tick: as before, held to the map's
        spec, report = run(self.hut(at(0, 176), at(176, 384)))
        self.assertEqual(warned(report, 'building-cursor'), ['building-cursor'])
        self.assertNotIn('cursorFloors', native_split(spec)[1]['buildings'][0])
        # a floor starting under the one before it
        _, report = run(self.hut(at(100, 300), at(50, 250), at(300, 500), cursorFloors=True))
        self.assertEqual([w['floors'] for w in report['warnings'] if w['code'] == 'building-cursor-order'], [[2]])
        # a stair volume of the map under it stays
        stair = bar + [dict(name='st', floor=2, stair=True, box=dict(min=[ox + 100, oy + 100, oz], max=[ox + 200, oy + 200, oz + 220]))]
        _, report = run(hut, cursor=stair)
        self.assertEqual(warned(report, 'building-cursor'), ['building-cursor-volume'])
        # ... but not on a cleared map, whose own cursor volumes go
        _, report = compiler.compile_project(document(buildings=[hut], cleared=True), sc(stair), ('building',))
        self.assertEqual(warned(report, 'building-cursor'), [])
        # the tick is a boolean: anything else leaves the record out
        _, report = run(dict(hut, cursorFloors='yes'))
        self.assertEqual(left_out(report), ['building-shape'])
        # the map's own buildings bring none
        doc = document(buildings=[dict(hut, replaces=dict(package='URB_Bar', level='base', actor='XComBuildingVolume_0'),
                                       floors=[dict(f, volumes=[None]) for f in hut['floors']])])
        self.assertEqual(compiler.Compiler(doc, sc()).floor_edits.cursor_areas(), [])

    def test_a_building_goes_to_the_native_edit(self):
        spec, report = self.run_buildings([self.hut()])
        self.assertEqual(codes(report), [])
        self.assertEqual(report['buildings'], [dict(id='b1', name='Hut', kind='building', floors=2)])
        patch, native = compiler.native_split(spec)
        self.assertEqual(patch['objects'], [])
        self.assertEqual(native['buildings'], [dict(id='b1', name='Hut', kind='building',
                                                    floors=[dict(boxes=[[float(v) for v in self.GROUND]]),
                                                            dict(boxes=[[float(v) for v in self.ABOVE]])])])

    def test_the_family_builds_since_exp_44(self):
        self.assertTrue(compiler.FAMILIES['building']['builds'])
        _, report = self.run_buildings([self.hut()], enable=())
        self.assertEqual(codes(report), [])

    def test_switched_off_again_it_is_refused(self):
        was = compiler.FAMILIES['building']
        self.addCleanup(compiler.FAMILIES.__setitem__, 'building', was)
        compiler.FAMILIES['building'] = dict(was, builds=False)
        spec, report = self.run_buildings([self.hut()], enable=())
        self.assertIsNone(spec)
        self.assertEqual(codes(report), ['family'])
        self.assertEqual(refused(report)[0]['family'], 'building')

    def test_no_buildings_is_no_edit(self):
        _, report = self.run_buildings([], enable=())
        self.assertEqual(codes(report), [])

    def test_the_shape_is_checked(self):
        for bad in ([dict(self.hut(), kind='shed')], [dict(self.hut(), floors=[])], [self.hut([])],
                    [self.hut([[0, 0, 0, 96, 96, 0]])], [self.hut([[0, 0, 0, 96]])], [self.hut(), self.hut()],
                    [dict(self.hut(), id='')], 'hut', [self.hut([[0, 0, 0, 96, 96, 'high']])]):
            _, report = self.run_buildings(bad)
            self.assertEqual(codes(report), ['building-shape'], bad)

    def test_a_box_outside_the_grid_is_warned_of(self):
        # a warning since the map buildings plan (the user: warn, don't block)
        for floor in ([[-2880 - 96, 0, 0, -2784, 96, 176]], [[0, 0, 0, 96, 96, 12 * 64 + 64]]):
            spec, report = self.run_buildings([self.hut(floor)])
            self.assertEqual((codes(report), noted(report, 'building-o')), ([], ['building-outside']))
            self.assertIsNotNone(spec)

    def test_floors_that_overlap_are_warned_of(self):
        spec, report = self.run_buildings([self.hut([self.GROUND], [[0, 0, 100, 576, 576, 384]])])
        self.assertEqual((codes(report), warned(report, 'building-o')), ([], ['building-overlap']))
        self.assertEqual(len(compiler.native_split(spec)[1]['buildings']), 1)
        # two boxes of one floor say nothing; two buildings do, once for the pair
        _, report = self.run_buildings([self.hut([self.GROUND, [96, 96, 0, 672, 672, 176]])])
        self.assertEqual(warned(report, 'building-o'), [])
        _, report = self.run_buildings([self.hut(), dict(self.hut([[480, 480, 0, 960, 960, 176]]), id='b2', name='Shed')])
        self.assertEqual((codes(report), warned(report, 'building-o')), ([], ['building-overlap']))
        # side by side, sharing a face
        _, report = self.run_buildings([self.hut(), dict(self.hut([[576, 0, 0, 960, 576, 176]]), id='b2')])
        self.assertEqual(warned(report, 'building-o'), [])

    def test_copied_overlapping_floors_keep_authored_roof_assignment(self):
        s = scene()
        s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
        s['buildings'] = [dict(id='7', name=PL + 'XComBuildingVolume_1', floors=[
            dict(boxes=[dict(min=[0, 0, 0], max=[384, 576, 320])]),
            dict(boxes=[dict(min=[0, 0, 192], max=[384, 576, 576])]),
        ])]
        s['objects'][0]['floors'] = [dict(building='7', floor=1, cutdownFloor=0)]
        roof = add('XComLevelActor_1', 1, (1344, 0, 0), (0, 16384, 0))
        building = self.hut([[768, 0, 0, 1344, 384, 320]], [[768, 0, 192, 1344, 384, 576]])
        spec, report = compile_project(document(added=[roof], buildings=[building]), s)
        self.assertTrue(report['ok'], refused(report))
        _, native = compiler.native_split(spec)
        carry = native['buildings'][0]['carry'][short(roof['actor'])]
        self.assertEqual((carry['saved'], carry['floor_map']), ([[1, 0]], [0, 1]))
        self.assertEqual(carry['floors'], [[[768, 0, 0, 1344, 384, 320]], [[768, 0, 192, 1344, 384, 576]]])
        self.assertNotIn('building-overlap', warned(report))
        # Edited boxes (the Small Landed UFO prefab's: 36 lower, the roof floor taller) still come from the source
        # building: the roof keeps the map's listing where the rule agrees (buildings.members), the floors their overlap.
        edited = self.hut([[768, 0, -36, 1344, 384, 284]], [[768, 0, 156, 1344, 384, 612]])
        spec, report = compile_project(document(added=[roof], buildings=[edited]), s)
        _, native = compiler.native_split(spec)
        self.assertEqual(native['buildings'][0]['carry'][short(roof['actor'])]['saved'], [[1, 0]])
        self.assertNotIn('building-overlap', warned(report))
        # A building the source's floors don't meet falls back to the rule and the ordinary overlap validation.
        away = self.hut([[1920, 0, 0, 2496, 384, 320]], [[1920, 0, 192, 2496, 384, 576]])
        spec, report = compile_project(document(added=[roof], buildings=[away]), s)
        _, native = compiler.native_split(spec)
        self.assertNotIn('carry', native['buildings'][0])
        self.assertIn('building-overlap', warned(report))

    def test_source_floor_match_cases(self):
        """The twin of web/floors.js sourceFloorMatch: the same cases (tools/viewer/tests/source_floor_match_test.mjs)."""
        for c in json.loads((Path(__file__).parent / 'source_floor_match_cases.json').read_text(encoding='utf-8')):
            got = compiler.source_floor_match(c['buildings'], [dict(boxes=f) for f in c['floors']], c['before'],
                                              c['location'], c['rotation'])
            self.assertEqual(got and dict(building=got['building']['id'], floorMap=got['floor_map']), c['expect'], c['name'])

    def test_the_maps_own_floors_are_warned_of(self):
        own = [dict(name=PL + 'XComBuildingVolume_0',
                    floors=[dict(index=0, boxes=[dict(min=[384, 384, 0], max=[960, 960, 176])])])]
        _, report = self.run_buildings([self.hut()], own=own)
        self.assertEqual((codes(report), warned(report, 'building-o')), ([], ['building-overlap']))
        self.assertIn("map's own building XComBuildingVolume_0", report['warnings'][0]['message'])
        _, report = self.run_buildings([self.hut([[-960, 0, 0, -480, 576, 176]])], own=own)
        self.assertEqual(warned(report, 'building-o'), [])


def foreign(name, serial, at, rot=(0, 0, 0), package='urb_policestation'):
    return dict(add(name, serial, at, rot), **{'from': target(name, package=package)})


class ForeignTests(unittest.TestCase):
    def test_generated_area_lights_follow_each_foreign_copy_from_the_donor_pose(self):
        owner = PL + 'XComLevelActor_15'
        light = dict(actor=PL + 'GeneratedMeshAreaLight_1', actorClass='GeneratedMeshAreaLight',
                     location=[5010, 5020, 30], rotation=[-100, 0, 0], radius=256)
        library = FakeLibrary(grid=[-1000, -1000, 64])
        record, entry = library.record(target(short(owner), package='URB_PoliceStation'))
        attached = record['areaLights'] = {owner: dict(lights=[light], unresolved=[])}
        library = mock.Mock()
        library.record.return_value = record, entry
        s = scene()
        s['tileGrid'] = dict(origin=[-2784, -1920, 0], dimensions=[52, 39, 12], size=[96, 96, 64])
        doc = document(added=[foreign(short(owner), 1, (96, 400, 0), (0, 16384, 0)),
                              foreign(short(owner), 2, (96, 600, 0))])
        spec, report = compile_project(doc, s, library=library)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['counts']['lights']['area'], 2)
        _, native = compiler.native_split(spec)
        first, second = native['lights']['area']
        self.assertEqual((first['location'], first['rotation']), ([76, 410, 30], [-100, 16384, 0]))
        self.assertEqual((second['location'], second['rotation']), ([106, 620, 30], [-100, 0, 0]))
        self.assertEqual(first['donor'], dict(package='URB_PoliceStation', sha256=DONOR_SHA))
        self.assertNotEqual(first['guidSeed'], second['guidSeed'])
        attached[owner]['unresolved'] = [light['actor']]
        spec, report = compile_project(doc, s, library=library)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(report['counts']['lights']['area'], 2)
        self.assertEqual([w['code'] for w in report['notes']].count('foreign-area-light-unresolved'), 2)

    def test_a_piece_of_another_map_is_a_copy_made_in_the_map_with_its_donor(self):
        doc = document(added=[foreign('XComLevelActor_15', 1, (96, 400, 0), (0, 16384, 0)),
                              foreign('XComLevelActor_15', 2, (96, 600, 0)), add('XComLevelActor_1', 3, (0, 400, 0))])
        library = FakeLibrary()
        spec, report = compile_project(doc, scene(), library=library)
        self.assertTrue(report['ok'], refused(report))
        donor = dict(package='URB_PoliceStation', sha256=DONOR_SHA)
        copy = spec['objects'][0]
        self.assertEqual(copy['from'], ['XComLevelActor_15', 'XComLevelActor_15', 'XComLevelActor_1'])
        self.assertEqual(copy['donors'], [donor, donor, None])
        # the box is the donor's mesh at the new pose, not the base map's
        self.assertEqual(copy['boxes'][1], [86, 106, 590, 610, 0, 200])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual([(c['actor'], c['label'], c.get('donor')) for c in native['copies']],
                         [('XComLevelActor_15', 'XComLevelActor_15_copy1', donor),
                          ('XComLevelActor_15', 'XComLevelActor_15_copy2', donor),
                          ('XComLevelActor_1', 'XComLevelActor_1_copy3', None)])
        self.assertEqual(native['copies'][0]['rotation'], [0, 16384, 0])
        self.assertEqual(report['donors'], [dict(donor, pieces=['XComLevelActor_15'])])
        # one warning for them all: the light is the donor map's
        self.assertEqual([w['code'] for w in report['notes']].count('foreign-quick-light'), 1)
        # a project without such a piece has no donors and no such field in its spec
        spec, report = compile_project(document(added=[add('XComLevelActor_1', 3, (0, 400, 0))]), scene(), library=library)
        self.assertEqual((report['donors'], 'donors' in spec['objects'][0]), ([], False))

    def test_what_the_library_cant_give_is_an_error_with_its_code(self):
        doc = document(added=[foreign('XComLevelActor_15', 1, (96, 400, 0))])
        spec, report = compile_project(doc, scene())
        self.assertEqual(left_out(report), ['no-library'])
        for code in ('no-library', 'donor-missing', 'donor-changed', 'not-placeable'):
            spec, report = compile_project(doc, scene(), library=FakeLibrary(fail=code))
            self.assertEqual((left_out(report), built(report)), ([code], 0))
            self.assertEqual(refused(report)[0]['entity'], PL + 'XComLevelActor_15_copy1')
        spec, report = compile_project(doc, scene(), library=FakeLibrary(placeable=False, reason='it is hidden in its map'))
        self.assertEqual(codes(report), ['not-placeable'])
        self.assertIn('it is hidden in its map', refused(report)[0]['message'])

    def test_only_the_families_switched_on_come_from_other_maps(self):
        import compiler
        before = compiler.FOREIGN_FAMILIES
        self.addCleanup(setattr, compiler, 'FOREIGN_FAMILIES', before)
        self.assertIn('destructible', before)       # since EXP-39; the gate itself is checked with it off
        compiler.FOREIGN_FAMILIES = ('scenery',)
        doc = document(added=[foreign('XComDestructibleActor_9', 1, (96, 400, 0))])
        library = FakeLibrary(actorClass='XComDestructibleActor')
        spec, report = compile_project(doc, scene(), library=library)
        # (a refusal until 14 November 2026: built and marked untried for the Build's fallback; warned of until 16
        # November 2026, when no warning says a piece is untried)
        self.assertEqual((codes(report), warned(report, 'foreign-')), ([], []))
        self.assertEqual(spec['objects'][0]['untried'], [True])
        self.assertTrue(compiler.native_split(spec)[1]['copies'][0]['untried'])
        spec, report = compile_project(doc, scene(), library=library, foreign=['destructible'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['objects'][0]['donors'], [dict(package='URB_PoliceStation', sha256=DONOR_SHA)])
        # the index holds such a piece back by its family alone (`blocked`): this build's gate decides, not the index
        def untried(library, **options):
            spec, report = compile_project(doc, scene(), library=library, **options)
            marked = [bool(o.get('untried') and o['untried'][0]) for o in spec['objects'] if o['type'] == 'copy']
            return codes(report), warned(report, 'foreign-'), marked
        gated = FakeLibrary(actorClass='XComDestructibleActor', placeable=False, blocked='family', reason='a later step')
        self.assertEqual(untried(gated), ([], [], [True]))
        self.assertEqual(untried(gated, foreign=['destructible']), ([], [], [False]))
        # one the library holds back for being linked or hidden is built too (14 November 2026), warned of for what
        # shows in the game; one that needs something that can't be brought is left out, as before
        for blocked, words in (('assembly', 'linked to other pieces'), ('hidden', 'hidden in its own map')):
            held = FakeLibrary(actorClass='XComDestructibleActor', placeable=False, blocked=blocked, reason='linked')
            self.assertEqual(untried(held, foreign=['destructible']), ([], ['foreign-held'], [True]), blocked)
            report = compile_project(doc, scene(), library=held, foreign=['destructible'])[1]
            self.assertIn(words, report['warnings'][-1]['message'])
        closure = FakeLibrary(actorClass='XComDestructibleActor', placeable=False, blocked='closure', reason='it needs x')
        self.assertEqual(untried(closure, foreign=['destructible'])[:2], (['not-placeable'], []))
        # a class with no family of its own is brought untried as well
        self.assertEqual(untried(FakeLibrary(actorClass='SomethingElse')), ([], [], [True]))

    def test_a_piece_that_keeps_the_grid_stands_on_this_maps_as_on_its_own(self):
        # a fracturing piece of a map whose grid corner is 48 off the bar's in x and a storey and a half down: where
        # it stands at home (5000, 5000, 0) reads on the bar's grid as moved by the corners' difference
        s = scene()
        s['tileGrid'] = dict(origin=[-2784.0, -1920.0, 0.0], dimensions=[52, 39, 12], size=[96, 96, 64])
        library = FakeLibrary(actorClass='XComFracLevelActor', grid=[-1776.0, -2496.0, -96.0])
        home = [5000 - 2784 + 1776, 5000 - 1920 + 2496, 96]

        def at(dx, dy, dz):
            doc = document(added=[foreign('XComFracLevelActor_9', 1, (home[0] + dx, home[1] + dy, home[2] + dz))])
            return compile_project(doc, s, library=library, foreign=['fracturing'])[1]
        report = at(-96 * 30, -96 * 20, -64)
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('off-grid', [w['code'] for w in report['warnings']])
        self.assertIn('off-grid', [w['code'] for w in at(-96 * 30 + 48, 0, 0)['warnings']])       # half a tile off
        # a home map without a grid can't place such a piece; scenery doesn't ask
        report = compile_project(document(added=[foreign('XComFracLevelActor_9', 1, home)]), s,
                                 library=FakeLibrary(actorClass='XComFracLevelActor'), foreign=['fracturing'])[1]
        self.assertEqual(codes(report), ['pose'])

    CAR = dict(family='car', parts={'XComDestructibleActor_9': 'XComDestructibleActor',
                                    'XComFracLevelActor_3': 'XComFracLevelActor'})
    GRID = [-2783.9998 - 96 * 40, -1920.0 - 96 * 40, 0.0]      # the home map's grid corner: forty tiles off the bar's

    def car(self, serial, at, names=('XComDestructibleActor_9', 'XComFracLevelActor_3')):
        return [foreign(n, serial + k, at) for k, n in enumerate(names)]

    def test_an_assembly_of_another_map_comes_whole(self):
        s = scene()
        s['tileGrid'] = dict(origin=[-2783.9998, -1920.0, 0.0], dimensions=[52, 39, 12], size=[96, 96, 64])
        library = FakeLibrary(whole=self.CAR, grid=self.GRID, placeable=False, blocked='family', reason='later')
        before = compiler.FOREIGN_ASSEMBLIES
        self.addCleanup(setattr, compiler, 'FOREIGN_ASSEMBLIES', before)
        self.assertIn('car', before)                 # since EXP-40; the gate itself is checked with it off
        compiler.FOREIGN_ASSEMBLIES = ()
        home = (5000 + 96 * 40, 5000 + 96 * 40, 0)             # where it stands at home, on the bar's grid
        at = (home[0] - 96 * 60, home[1] - 96 * 50, 0)
        doc = document(added=self.car(1, at))
        # held back until its game check, as the index says: built, with no warning saying so
        _r = compile_project(doc, s, library=library)[1]
        self.assertEqual((codes(_r), warned(_r, 'foreign-')), ([], []))
        spec, report = compile_project(doc, s, library=library, foreign=['car'])
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('off-grid', [w['code'] for w in report['warnings']])
        _, native = compiler.native_split(compiler.stream_only(spec))
        copies = native['copies']
        self.assertEqual(sorted(c['actor'] for c in copies), ['XComDestructibleActor_9', 'XComFracLevelActor_3'])
        # one copy of the car: its parts share the assembly, and each names the map it comes from
        self.assertEqual({c['assembly'] for c in copies}, {'add:XComDestructibleActor_9_copy1'})
        self.assertEqual({c['family'] for c in copies}, {'car'})
        self.assertTrue(all(c['donor'] == dict(package='URB_PoliceStation', sha256=DONOR_SHA) for c in copies))
        (move,) = native['assemblies']
        self.assertEqual((move['family'], move['turns'], len(move['members'])), ('car', 0, 2))
        # the body without its glass is no car
        _, report = compile_project(document(added=self.car(1, at)[:1]), s, library=library, foreign=['car'])
        self.assertEqual((codes(report), warned(report, 'assembly-')), ([], ['assembly-split']))     # (warned of and built since 14 November 2026)
        # two cars from one original are two assemblies
        spec, report = compile_project(document(added=self.car(1, at) + self.car(3, (at[0] + 96 * 4, at[1], 0))), s,
                                       library=library, foreign=['car'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(len(compiler.native_split(compiler.stream_only(spec))[1]['assemblies']), 2)
        # a van is an assembly with a gate of its own (its building comes with it: the transplanter's part)
        van = FakeLibrary(whole=dict(self.CAR, family='van'), grid=self.GRID)
        _r = compile_project(doc, s, library=van)[1]
        self.assertEqual((codes(_r), warned(_r, 'foreign-')), ([], []))
        self.assertIn('van', before)                 # since EXP-42
        spec, report = compile_project(doc, s, library=van, foreign=['van'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual({c['family'] for c in compiler.native_split(compiler.stream_only(spec))[1]['copies']}, {'van'})

    def test_a_ladder_of_another_map_is_checked_against_this_maps_floors(self):
        s = assembly_scene()
        library = FakeLibrary(actorClass='XComLadder', grid=list(s['tileGrid']['origin'][:3]))
        doc = document(added=[foreign('XComLadder_9', 1, (5000, 5000, 0))])
        before = compiler.FOREIGN_FAMILIES
        self.addCleanup(setattr, compiler, 'FOREIGN_FAMILIES', before)
        self.assertIn('ladder', before)              # since EXP-40 run 2; the gate itself is checked with it off
        compiler.FOREIGN_FAMILIES = ('scenery',)
        _r = compile_project(doc, s, library=library)[1]
        self.assertEqual((codes(_r), warned(_r, 'foreign-')), ([], []))
        # where it stands at home there is no floor here: the climb is warned of as a copy of the bar's own would be
        report = compile_project(doc, s, library=library, foreign=['ladder'])[1]
        self.assertEqual((codes(report), [w['code'] for w in report['warnings'] if w['code'] == 'ladder-climb']), ([], ['ladder-climb']))

    def test_an_entry_held_for_a_game_check_builds_only_in_that_checks_build(self):
        # (nothing is held today: the entry here is as the library would mark one)
        doc = document(added=[foreign('XComDestructibleActor_9', 1, (96, 400, 0))])
        held = FakeLibrary(actorClass='XComDestructibleActor', placeable=False, blocked='check', held=['prefab'],
                           reason='Pieces brought this way wait for their game test.')
        _, report = compile_project(doc, scene(), library=held)
        _r = report
        self.assertEqual((codes(_r), warned(_r, 'foreign-')), ([], []))
        self.assertTrue(compile_project(doc, scene(), library=held, foreign=['check'])[1]['ok'])
        # the check's gate lifts nothing else
        hidden = FakeLibrary(actorClass='XComDestructibleActor', placeable=False, blocked='hidden', reason='hidden')
        _r = compile_project(doc, scene(), library=hidden, foreign=['check'])[1]
        self.assertEqual((codes(_r), warned(_r, 'foreign-')), ([], ['foreign-held']))

    def test_other_maps_are_templates_only(self):
        # an override of another map's piece, or a piece of another map's stream, is refused as before
        doc = document([dict(target=target('XComLevelActor_15', package='URB_PoliceStation'), deleted=True)])
        library = FakeLibrary()
        spec, report = compile_project(doc, scene(), library=library)
        self.assertEqual((codes(report), library.asked), (['level'], []))
        doc = document(added=[dict(foreign('XComLevelActor_15', 1, (96, 400, 0)),
                                   **{'from': target('XComLevelActor_15', level='stream', package='URB_PoliceStation')})])
        spec, report = compile_project(doc, scene(), library=library)
        self.assertEqual((codes(report), library.asked), (['level'], []))

    @unittest.skipUnless(library_scanned() and settings.configured('game'),
                         'needs the game install and its library scanned into the cache (by this version of the index)')
    def test_the_installs_library_gives_a_piece_and_says_what_it_lacks(self):
        game = settings.resolve_game(settings.configured('game'))[0]
        library = compiler.Library(CACHE, game)
        record, entry = library.record(target('XComLevelActor_15', package='URB_PoliceStation'))
        self.assertEqual((record['source']['package'], entry['placeable'], entry['actorClass']),
                         ('URB_PoliceStation', True, 'XComLevelActor'))
        self.assertTrue(all(o['mesh'] in record['meshes'] for o in record['objects']))
        for name, package, code in (('XComLevelActor_999999', 'URB_PoliceStation', 'donor-changed'),
                                    ('XComLevelActor_15', 'URB_NoSuchMap', 'donor-missing')):
            with self.assertRaises(compiler.LibraryError) as raised:
                library.record(target(name, package=package))
            self.assertEqual(raised.exception.code, code)

    def test_the_library_of_a_cache_without_a_scan_says_so(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(compiler.LibraryError) as raised:
                compiler.Library(tmp, tmp).record(target('XComLevelActor_15', package='URB_PoliceStation'))
        self.assertEqual(raised.exception.code, 'no-library')


def moved(names, move):
    src = {o['actor']: o for o in assembly_scene()['objects'] if o['layer'] == 'base'}
    out = []
    for n in names:
        loc, rot = move(src[PL + n])
        out.append(dict(target=target(n), location=loc, rotation=rot))
    return out


LADDER = lambda: next(o for o in assembly_scene()['objects'] if o['actor'] == PL + 'XComLadder_20')


class FamilyTests(unittest.TestCase):
    """Families, assemblies and the pose rule (private/plans/done/cars-doors-ladders-plan.md, sections 3.2 to 3.4)."""

    def test_the_families_table(self):
        self.assertEqual(sorted(f for f, v in compiler.FAMILIES.items() if v['builds']),
                         ['building', 'car', 'collectible', 'destructible', 'door', 'effect', 'effect-values', 'flare', 'fracturing',
                          'frameless-door', 'ladder', 'light', 'physics', 'scenery', 'sound', 'sound-values', 'spawn', 'van'])
        # every class with a family builds (fracturing pieces and physics props since 9 November), in the map itself
        # or as part of an assembly
        self.assertTrue(all(compiler.FAMILIES[f]['builds'] for f in compiler.CLASS_FAMILY.values()))
        self.assertEqual(set(compiler.CLASS_FAMILY) - set(compiler.NATIVE_CLASSES), {'XComLadder', 'XComInteractiveLevelActor'})
        self.assertTrue(all(compiler.FAMILIES[f]['grid'] for f in compiler.ASSEMBLY_FAMILIES))
        # a fracturing piece keeps the grid move (its columns are saved one to a tile); a physics prop takes any pose
        self.assertEqual((compiler.FAMILIES['fracturing']['grid'], compiler.FAMILIES['physics']['grid']), (True, False))
        with self.assertRaises(ValueError):
            compile_project(document(), scene(), enable=['boats'])

    def test_assemblies_of_a_small_scene(self):
        found = compiler.assemblies(assembly_scene(), 'URB_Bar')
        got = {}
        for a in found.values():
            got[short(a['pivot'])] = (a['family'], [short(m) for m in a['members']])
        self.assertEqual(got, {
            'XComLadder_20': ('ladder', ['XComLadder_20']),
            'XComInteractiveLevelActor_21': ('door', sorted(DOOR)),
            'XComInteractiveLevelActor_23': ('frameless-door', ['XComInteractiveLevelActor_23']),
            'XComInteractiveLevelActor_8': ('frameless-door', ['XComInteractiveLevelActor_8']),
            'XComDestructibleActor_24': ('car', sorted(CAR)),
            'XComDestructibleActor_30': ('van', sorted(VAN)),
            'XComDestructibleActor_6': ('car', ['XComDestructibleActor_6', 'XComFracLevelActor_7']),
        })
        # a plain piece of a building, the skid mark under the van and the inherited level's pieces are in none
        for name in ('XComLevelActor_1', 'XComLevelActor_34', 'XComFracLevelActor_11'):
            self.assertNotIn(PL + name, found)

    def test_a_vans_own_building(self):
        # export 21's `van`: the building most of whose listed pieces are one van's goes with the van; a building
        # whose pieces are no van's is the map's
        self.assertEqual(compiler.van_buildings(assembly_scene(), 'URB_Bar'), {'1'})

    def test_a_part_the_glass_names_at_the_bodys_place_joins_the_car(self):
        # export 16's breaks: Police Station's standalone light bars stand 2 units from their sedan's body, in no
        # prefab, and only the glass's columns name them; a piece the glass names elsewhere (a fence, a neighbouring
        # wreck) stays out, and so does a piece at the body's place that the glass doesn't name
        s = assembly_scene()
        s['objects'] += [
            part('XComDestructibleActor_27', cls='XComDestructibleActor', at=(-1242.36, -482.16, 0), rot=(0, -728, 0)),
            part('XComDestructibleActor_28', cls='XComDestructibleActor', at=(-1140, -482, 0)),
            part('XComDestructibleActor_29', cls='XComDestructibleActor', at=(-1240.36, -480.16, 0)),
        ]
        glass = [o for o in s['objects'] if o['actor'] == PL + 'XComFracLevelActor_25'][0]
        glass['breaks'] = [PL + 'XComDestructibleActor_24', PL + 'XComDestructibleActor_26', PL + 'XComDestructibleActor_27',
                           PL + 'XComDestructibleActor_28']
        found = compiler.assemblies(s, 'URB_Bar')
        self.assertEqual([short(m) for m in found[PL + 'XComDestructibleActor_24']['members']],
                         sorted(CAR + ['XComDestructibleActor_27']))
        for name in ('XComDestructibleActor_28', 'XComDestructibleActor_29'):
            self.assertNotIn(PL + name, found)

    def test_the_bars_assemblies(self):
        # the inventory (plan section 2): 13 cars and 4 vans, 7 framed doors, 2 ladders
        base = pinned_bar(self, 14)
        found = {id(a): a for a in compiler.assemblies(base, 'URB_Bar').values()}.values()
        count = {}
        for a in found:
            count[a['family']] = count.get(a['family'], 0) + 1
        self.assertEqual(count, {'car': 13, 'van': 4, 'door': 7, 'ladder': 2})
        police = [a for a in found if a['pivot'] == PL + 'XComDestructibleActor_64'][0]
        self.assertEqual([short(m) for m in police['members']],
                         ['XComDestructibleActor_143', 'XComDestructibleActor_64', 'XComFracLevelActor_45'])
        door = [a for a in found if a['pivot'] == PL + 'XComInteractiveLevelActor_26'][0]
        self.assertEqual([short(m) for m in door['members']], ['XComDestructibleActor_502', 'XComInteractiveLevelActor_26'])

    def test_the_pose_rule_cases(self):
        # the same cases the editor's recipe snap is checked against
        cases = json.loads((HERE / 'pose_rule_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreater(len(cases), 8)
        for c in cases:
            with self.subTest(case=c['case']):
                s, p = c['source'], c['pose']
                m = compiler.grid_move(s['location'], s['rotation'], p['location'], p['rotation'], c['origin'])
                self.assertEqual((m['valid'], m['why'], m['turns']), (c['valid'], c['why'], c['turns']))
                for a, b in zip(m['translation'], c['translation']):
                    self.assertAlmostEqual(a, b, delta=1e-3)
                loc, rot = compiler.nearest_grid_pose(s['location'], s['rotation'], p['location'], p['rotation'], c['origin'])
                self.assertEqual(rot, c['nearest']['rotation'])
                for a, b in zip(loc, c['nearest']['location']):
                    self.assertAlmostEqual(a, b, delta=1e-3)
                # the nearest pose builds, and a valid pose is its own nearest
                self.assertTrue(compiler.grid_move(s['location'], s['rotation'], loc, rot, c['origin'])['valid'])
                if c['valid']:
                    for a, b in zip(loc, p['location']):
                        self.assertAlmostEqual(a, b, delta=0.5)

    def test_refused_families_give_one_error_per_assembly(self):
        rest = (moved(CAR, grid_moved(0, (2, 0))) + moved(VAN, grid_moved(0, (0, 3)))
                + [dict(target=target(n), deleted=True) for n in DOOR]
                + [dict(target=target('XComLadder_20'), deleted=True)])
        frameless = [dict(target=target('XComInteractiveLevelActor_23'), deleted=True)]
        with mock.patch.dict(compiler.FAMILIES['frameless-door'], builds=False):
            spec, report = compile_project(document(rest + frameless), assembly_scene())
        self.assertEqual(left_out(report), ['milestone'])
        # With its recipe disabled, the frameless door is the one refused.
        self.assertEqual(sorted((e['code'], e['family'], e['milestone']) for e in refused(report)),
                         [('milestone', 'frameless-door', 2)])
        self.assertIn('XComInteractiveLevelActor_23', refused(report)[0]['message'])
        self.assertIn('door without a frame', refused(report)[0]['message'])
        spec, report = compile_project(document(rest + frameless), assembly_scene())
        self.assertTrue(report['ok'], refused(report))
        copy = next(o for o in spec['objects'] if o['type'] == 'copy')
        self.assertEqual([f for n, f in zip(copy['from'], copy['families']) if n in VAN], ['van'] * len(VAN))

    def test_a_doors_frame_alone_is_a_destructible_prop(self):
        # an open doorway: the frame alone moves anywhere, as any destructible prop
        spec, report = compile_project(document([dict(target=target('XComDestructibleActor_22'), location=[500, 150, 16],
                                                      rotation=[0, 1000, 0])]), assembly_scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('assemblies', spec['objects'][0])
        self.assertNotIn('family', report['entities'][0])

    def test_an_enabled_family_builds_its_assembly_with_one_grid_move(self):
        doc = document(moved(CAR, grid_moved(1, (2, 0))))
        spec, report = compile_project(doc, assembly_scene(), enable=['car'])
        self.assertTrue(report['ok'], refused(report))
        whole = spec['objects'][0]
        self.assertEqual(whole['labels'], ['move:' + n for n in sorted(CAR)])
        self.assertEqual(whole['assemblies'], ['move:XComDestructibleActor_24'] * 3)
        self.assertEqual(whole['families'], ['car'] * 3)
        (m,) = whole['assemblyMoves']
        self.assertEqual((m['id'], m['family'], m['turns'], m['members']),
                         ('move:XComDestructibleActor_24', 'car', 1, ['move:' + n for n in sorted(CAR)]))
        self.assertEqual(report['assemblies'], whole['assemblyMoves'])
        self.assertIn('car', report['families'])
        self.assertEqual(sorted(h for h in spec['objects'][1]['alsoHide']), sorted(CAR))
        patch, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(patch['objects'], [])
        self.assertEqual([(n['label'], n['family'], n['assembly']) for n in native['copies']],
                         [('move:' + n, 'car', 'move:XComDestructibleActor_24') for n in sorted(CAR)])
        self.assertEqual(native['assemblies'], whole['assemblyMoves'])
        # the move takes the original's parts to the copies: R(x) + translation
        src = {o['actor']: o for o in assembly_scene()['objects']}
        for n in native['copies']:
            s = src[PL + n['actor']]['location']
            x, y = compiler.turned(s, m['turns'])
            self.assertAlmostEqual(x + m['translation'][0], n['location'][0], delta=1e-3)
            self.assertAlmostEqual(y + m['translation'][1], n['location'][1], delta=1e-3)

    def test_whole_assemblies_are_deleted_and_copied(self):
        doc = document([dict(target=target(n), deleted=True) for n in CAR],
                       copies_of(CAR, 1, grid_moved(0, (0, 3))) + copies_of(CAR, 4, grid_moved(2, (5, 5)))
                       + copies_of(['XComLadder_20'], 7, grid_moved(1, (40, -5))) + copies_of(DOOR, 8, grid_moved(0, (0, 0), 1)))
        spec, report = compile_project(doc, assembly_scene(), enable=['car', 'ladder', 'door'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual([m['id'] for m in report['assemblies']],
                         ['add:XComDestructibleActor_24_copy1', 'add:XComDestructibleActor_24_copy4',
                          'add:XComInteractiveLevelActor_21_copy8', 'add:XComLadder_20_copy7'])
        self.assertEqual([(m['family'], m['turns']) for m in report['assemblies']], [('car', 0), ('car', 2), ('door', 0), ('ladder', 1)])
        deletes = [e for e in report['entities'] if e['kind'] == 'delete']
        self.assertEqual({e['assembly'] for e in deletes}, {'delete:XComDestructibleActor_24'})
        self.assertEqual(sorted(spec['objects'][1]['labels']), sorted('delete:' + n for n in CAR))
        # the deleted car's parts are still the copies' templates, read before they are hidden
        self.assertEqual(len(spec['objects'][0]['labels']), 3 + 3 + 1 + 2)

    def test_a_map_whose_package_and_records_differ_in_case(self):
        # CsmallScout_Farm.upk, Name="CSmallScout_Farm": the project names the record's, the export the package's
        s = assembly_scene()
        s['name'] = 'URB_bar'
        for o in s['objects']:
            if o['sourcePackage'] == 'URB_Bar':
                o['sourcePackage'] = 'URB_bar'
        moved = [dict(target=dict(target('XComLadder_20'), package='URB_bar'),
                      **dict(zip(('location', 'rotation'), grid_moved(0, (0, -3))(LADDER()))))]
        spec, report = compile_project(document(moved), s, enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['map']['name'], 'URB_Bar')
        self.assertEqual([e['family'] for e in report['entities']], ['ladder'])
        s['name'] = 'URB_Other'
        self.assertEqual(codes(compile_project(document(moved), s, enable=['ladder'])[1]), ['source-mismatch'])

    def test_a_ladder_climbs_only_between_floors(self):
        # Bar's XComLadder_4 (here 20): foot (33, 33, 0), top (33, 32, 7) with roof below it (plan 2.1)
        spec, report = compile_project(document([dict(target=target('XComLadder_20'), **dict(zip(('location', 'rotation'),
                                       grid_moved(0, (0, -3))(LADDER()))))]), assembly_scene(), enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        copy = spec['objects'][0]
        self.assertEqual(copy['ladders'], [dict(foot=[33, 30, 0], top=[33, 29, 6])])
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(native['copies'][0]['ladder'], dict(foot=[33, 30, 0], top=[33, 29, 6]))
        # a copy turned to face +X past x tile 40, where the roofs end: its top has no floor
        far = copies_of(['XComLadder_20'], 1, grid_moved(1, (76, -5)))
        # warned of, and built as a piece with no climb of its own (warn, don't block)
        spec, report = compile_project(document(added=far), assembly_scene(), enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        [warning] = [w for w in report['warnings'] if w['code'] == 'ladder-climb']
        self.assertIn('top tile', warning['message'])
        self.assertEqual(warning['ends']['top'][2], 7)
        self.assertFalse(any(c for o in spec['objects'] for c in (o.get('ladders') or [])))

    def test_a_ladder_does_not_climb_to_the_floor_of_a_piece_the_project_deletes(self):
        # a deleted or moved piece takes its floor with it (floor_now), as the compiler's other floor checks count it,
        # whether or not a piece's flags take a floor away too (selection.js ladderNow is the twin)
        s = assembly_scene()
        for f in s['tactical']['floorTiles']:
            if f['tile'][2] == 6:
                f['actor'] = PL + 'XComLevelActor_34'       # the roofs' floor is this piece's
        moved = dict(target=target('XComLadder_20'), **dict(zip(('location', 'rotation'), grid_moved(0, (0, -3))(LADDER()))))
        climbs = lambda spec: [c for o in spec['objects'] for c in (o.get('ladders') or [])]  # noqa: E731
        spec, report = compile_project(document([moved]), s, enable=['ladder'])
        self.assertEqual(climbs(spec), [dict(foot=[33, 30, 0], top=[33, 29, 6])])
        for gone in (dict(deleted=True), dict(location=[-1900, -1240, 640], rotation=[0, 0, 0])):
            with self.subTest(gone):
                spec, report = compile_project(document([moved, dict(target=target('XComLevelActor_34'), **gone)]), s,
                                               enable=['ladder'])
                self.assertTrue(report['ok'], refused(report))
                [warning] = [w for w in report['warnings'] if w['code'] == 'ladder-climb']
                self.assertIn('top tile', warning['message'])
                self.assertEqual(climbs(spec), [])

    def test_a_ladders_ends_count_from_the_corner_the_game_counts_its_tiles_from(self):
        # export 26's tileGrid.tiles (its world data's WorldBounds); an older export's: a unit under the origin
        self.assertEqual(compiler.tile_corner(dict(origin=[0, 10, 20])), [-1, 9, 19])
        self.assertEqual(compiler.tile_corner(dict(origin=[0, 10, 20], tiles=[-1.5, 9, 19])), [-1.5, 9, 19])
        self.assertIsNone(compiler.tile_corner({}))
        # the same ends from the export's own corner as from the older rule (Bar's XComLadder_4 here 20)
        moved = [dict(target=target('XComLadder_20'), **dict(zip(('location', 'rotation'), grid_moved(0, (0, -3))(LADDER()))))]
        scene = assembly_scene()
        o = scene['tileGrid']['origin']
        scene['tileGrid']['tiles'] = [o[0] - 1, o[1] - 1, o[2] - 1]
        spec, report = compile_project(document(moved), scene, enable=['ladder'])
        self.assertEqual(spec['objects'][0]['ladders'], [dict(foot=[33, 30, 0], top=[33, 29, 6])])

        # counted from a corner a whole tile further west, every end is a tile further east
        def ends(report, spec):
            warned = [w['ends'] for w in report['warnings'] if w['code'] == 'ladder-climb']
            return warned[0] if warned else spec['objects'][0]['ladders'][0]
        scene['tileGrid']['tiles'] = [o[0] - 1 - 96, o[1] - 1, o[2] - 1]
        spec, report = compile_project(document(moved), scene, enable=['ladder'])
        self.assertEqual(ends(report, spec)['foot'], [34, 30, 0])

    def test_a_ladder_counts_the_floor_a_flat_piece_of_the_project_adds(self):
        # the copy past the roofs' end (the test above): its top tile has no floor in the map
        far = copies_of(['XComLadder_20'], 1, grid_moved(1, (76, -5)))
        _, report = compile_project(document(added=far), assembly_scene(), enable=['ladder'])
        tx, ty, tz = next(w for w in report['warnings'] if w['code'] == 'ladder-climb')['ends']['top']
        s = assembly_scene()
        ox, oy, oz = s['tileGrid']['origin'][:3]
        s['meshes']['slab'] = dict(name='Kit.Meshes.Slab', bounds=[0, 0, -4, 96, 96, 4, 136])
        home = (ox + 96 * 3, oy + 96 * 3, oz + 64 * tz + 4)
        s['objects'].append(part('XComLevelActor_30', cls='XComLevelActor', at=home, mesh='slab'))
        at = [ox + 96 * (tx + 0.5) + 48, oy + 96 * (ty + 0.5) + 48, home[2]]     # two by two tiles, the top tile among them
        slab = add('XComLevelActor_30', 5, at, (0, 0, 0))
        spec, report = compile_project(document(added=far + [slab]), s, enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertIn('ladder-new-floor', [w['code'] for w in report['warnings']])
        self.assertEqual(next(c for o in spec['objects'] for c in (o.get('ladders') or []) if c)['top'], [tx, ty, tz])
        # the slab listed before the ladder, or after it: the climb is checked once every copy is known
        spec, report = compile_project(document(added=[slab] + far), s, enable=['ladder'])
        self.assertEqual(next(c for o in spec['objects'] for c in (o.get('ladders') or []) if c)['top'], [tx, ty, tz])
        # the same slab with another hanging 96 over it: no standing room, so no floor, and the ladder is warned of
        low = add('XComLevelActor_30', 6, [at[0], at[1], at[2] + 128], (0, 0, 0))
        spec, report = compile_project(document(added=far + [slab, low]), s, enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertLessEqual({'ladder-climb', 'floor-headroom'}, {w['code'] for w in report['warnings']})

    def test_a_moved_ladder_counts_the_floors_the_project_adds_and_its_grown_levels(self):
        # the map's own ladder moved (an override, read before the added pieces) to where its top has no floor
        far = copies_of(['XComLadder_20'], 1, grid_moved(1, (76, -5)))[0]
        moved = dict(target=target('XComLadder_20'), location=far['location'], rotation=far['rotation'])
        s = assembly_scene()
        _, report = compile_project(document([moved]), s, enable=['ladder'])
        tx, ty, tz = next(w for w in report['warnings'] if w['code'] == 'ladder-climb')['ends']['top']
        ox, oy, oz = s['tileGrid']['origin'][:3]
        s['meshes']['slab'] = dict(name='Kit.Meshes.Slab', bounds=[0, 0, -4, 96, 96, 4, 136])
        home = (ox + 96 * 3, oy + 96 * 3, oz + 64 * tz + 4)
        s['objects'].append(part('XComLevelActor_30', cls='XComLevelActor', at=home, mesh='slab'))
        at = [ox + 96 * (tx + 0.5) + 48, oy + 96 * (ty + 0.5) + 48, home[2]]
        spec, report = compile_project(document([moved], added=[add('XComLevelActor_30', 5, at, (0, 0, 0))]), s, enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('ladder-climb', [w['code'] for w in report['warnings']])
        self.assertEqual(next(c for o in spec['objects'] for c in (o.get('ladders') or []) if c)['top'], [tx, ty, tz])
        # an invisible floor (a cover block made to carry floor) under the top counts as the slab does
        plate = dict(id='0c0ffee0-0000-4000-8000-000000000001', actor=PL + 'Cover_1', template=dict(kind='cover', version=1),
                     cover=dict(width=2, length=2, type='floor', height=1),
                     location=[ox + 96 * tx, oy + 96 * ty, oz + 64 * tz], rotation=[0, 0, 0])
        spec, report = compile_project(document([moved], added=[plate]), s, enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertNotIn('ladder-climb', [w['code'] for w in report['warnings']])
        # a level the grid grew by is a level a flat piece gives floor on
        nx, ny, nz = s['tileGrid']['dimensions']
        c = compiler.Compiler(document(stage=dict(grid=[nx, ny, nz + 4])), s)
        if c is not None:
            c.mission_edits.stage_grid = [nx, ny, nz + 4]
            c.copies.append(dict(box=[ox, ox + 96, oy, oy + 96, oz + 64 * nz - 6, oz + 64 * nz + 2], label='high'))
            self.assertEqual(list(c.added_floors()[0]), [(0, 0, nz)])
            c.mission_edits.stage_grid = None
            self.assertEqual(c.added_floors()[0], {})

    def test_a_flat_piece_larger_than_the_map_gives_floor_only_over_the_grid(self):
        # a prefab's sea plane, 200 tiles square round the map (a reported project had twenty, and their tiles outside
        # the grid took its compile minutes): floor on the grid's tiles alone, a grown grid's new ones among them
        s = assembly_scene()
        ox, oy, oz = s['tileGrid']['origin'][:3]
        nx, ny, nz = s['tileGrid']['dimensions']
        c = compiler.Compiler(document(), s)
        sea = dict(box=[ox - 96 * 100, ox + 96 * 100, oy - 96 * 100, oy + 96 * 100, oz - 2, oz + 2], label='sea')
        c.copies.append(sea)
        floor, blocked = c.added_floors()
        self.assertEqual(set(floor), {(x, y, 0) for x in range(nx) for y in range(ny)})
        self.assertEqual(blocked, {})
        # a plate hanging a storey over one tile takes its standing room (and is floor on its own level); a sea wholly
        # past the grid gives nothing, until the grid grows over it
        c.copies.append(dict(box=[ox + 96 * 2, ox + 96 * 3, oy + 96 * 4, oy + 96 * 5, oz + 64, oz + 80], label='low'))
        c.copies.append(dict(box=[ox + 96 * nx + 96, ox + 96 * nx + 9600, oy, oy + 96 * ny, oz - 2, oz + 2], label='past'))
        floor, blocked = c.added_floors()
        self.assertEqual(blocked, {(2, 4, 0): ('sea', 'low')})
        self.assertEqual({t for t, label in floor.items() if label == 'sea'},
                         {(x, y, 0) for x in range(nx) for y in range(ny)} - {(2, 4, 0)})
        self.assertEqual({t: label for t, label in floor.items() if label != 'sea'}, {(2, 4, 1): 'low'})
        c.mission_edits.stage_grid = [nx + 3, ny + 2, nz]
        floor, _ = c.added_floors()
        self.assertEqual(len([t for t in floor if t[2] == 0]), (nx + 3) * (ny + 2) - 1)
        self.assertEqual({t for t, label in floor.items() if label == 'past'}, {(x, y, 0) for x in (nx + 1, nx + 2) for y in range(ny)})

    def test_a_moved_or_deleted_ladder_takes_its_patch_helper_with_it(self):
        def with_helper(at):
            s = assembly_scene()
            helper = part('XComLadder_11', cls='XComLadder', at=at, rot=(0, -16384, 0), mesh='ladder', layer='stream',
                          package='patch_bar', hidden=True)
            s['streams'] = {'patch_bar': dict(kind='lwr', objects=[helper])}
            return s
        moved = [dict(target=target('XComLadder_20'), **dict(zip(('location', 'rotation'),
                      grid_moved(0, (0, -3))(LADDER()))))]
        # Bar's XComLadder_15 stands 20 units from its ladder, with the same ends: an exact helper
        spec, report = compile_project(document(moved), with_helper((436, 1276, 14)), enable=['ladder'])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['streamHides'], {'patch_bar': ['XComLadder_11']})
        patch, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(native['streamHides'], {'patch_bar': ['XComLadder_11']})
        self.assertNotIn('streamHides', patch)
        self.assertEqual([e['helpers'] for e in report['entities'] if e['kind'] == 'move'], [['patch_bar.XComLadder_11']])
        self.assertEqual(report['warnings'], [])
        # one standing 40 units off, with other ends, is a near helper: hidden too, with a warning
        spec, report = compile_project(document([dict(target=target('XComLadder_20'), deleted=True)]),
                                       with_helper((432, 1336, 16)), enable=['ladder'])
        self.assertEqual(spec['streamHides'], {'patch_bar': ['XComLadder_11']})
        self.assertEqual([w['code'] for w in report['warnings']], ['ladder-helper'])
        # none within half a tile: nothing to hide
        spec, report = compile_project(document([dict(target=target('XComLadder_20'), deleted=True)]),
                                       with_helper((432, 1396, 16)), enable=['ladder'])
        self.assertNotIn('streamHides', spec)

    def test_assemblies_edited_in_part_are_refused(self):
        on = ['car', 'door', 'ladder']
        cases = [
            ('the body alone moved', moved(CAR[:1], grid_moved(0, (1, 0))), [], 'assembly-split'),
            ('the parts moved apart', moved(CAR[:2], grid_moved(0, (1, 0))) + moved(CAR[2:], grid_moved(0, (2, 0))), [], 'assembly-split'),
            ('part deleted, part moved', [dict(target=target(CAR[0]), deleted=True)] + moved(CAR[1:], grid_moved(0, (1, 0))), [], 'assembly-split'),
            ('the leaf moved without its frame', moved(DOOR[:1], grid_moved(0, (1, 0))), [], 'assembly-split'),
            ('a copy without its glass', [], copies_of([CAR[0], CAR[2]], 1, grid_moved(0, (0, 3))), 'assembly-split'),
            ('two copies of the light bar at one place', [],
             copies_of(CAR, 1, grid_moved(0, (0, 3))) + copies_of(CAR[2:], 4, grid_moved(0, (0, 3))), 'malformed'),
        ]
        for name, overrides, added, code in cases:
            with self.subTest(case=name):
                spec, report = compile_project(document(overrides, added), assembly_scene(), enable=on)
                if code == 'assembly-split':
                    # (a refusal until 14 November 2026: each part is edited on its own, marked untried)
                    self.assertEqual((left_out(report), warned(report, 'assembly-')), ([], ['assembly-split']))
                    self.assertEqual(built(report), len(overrides) + len(added))
                    self.assertFalse(report['assemblies'])
                    copy = next((o for o in spec['objects'] if o['type'] == 'copy'), None)
                    self.assertTrue(copy is None or all(copy['untried']))
                    continue
                self.assertEqual(left_out(report), [code], refused(report))

    def test_assemblies_off_the_grid_build_with_a_warning(self):
        # Since 10 November 2026 a pose off the grid builds: the assembly's pieces are made where they stand, its move
        # says grid false, and an off-grid warning names what the pose misses and the nearest pose on the grid.
        on = ['car', 'door', 'ladder']

        def off_grid(o):
            # the whole car turned a quarter about its body's pivot, which stands off the tile corners
            px, py = -1240.36, -482.16
            x, y = compiler.turned((o['location'][0] - px, o['location'][1] - py), 1)
            return [round(x + px, 4), round(y + py, 4), o['location'][2]], [0, o['rotation'][1] + 16384, 0]
        half_tile = lambda o: ([o['location'][0] + 48, o['location'][1], 0], o['rotation'])  # noqa: E731
        cases = [
            ('the car turned about its own pivot', moved(CAR, off_grid), [], 'car', 'whole tiles'),
            ('the car moved half a tile', moved(CAR, half_tile), [], 'car', 'whole tiles'),
            ('a copy of the car half a tile over', [], copies_of(CAR, 1, half_tile), 'car', 'whole tiles'),
            ('the door turned 30 degrees', moved(DOOR, lambda o: (o['location'], [0, o['rotation'][1] + 5461, 0])), [],
             'door', 'quarter turns'),
        ]
        for name, overrides, added, family, why in cases:
            with self.subTest(case=name):
                spec, report = compile_project(document(overrides, added), assembly_scene(), enable=on)
                self.assertTrue(report['ok'], refused(report))
                self.assertEqual([w['code'] for w in report['warnings'] if w['code'] == 'off-grid'], ['off-grid'])
                warning = next(w for w in report['warnings'] if w['code'] == 'off-grid')
                self.assertEqual(warning['family'], family)
                self.assertIn(why, warning['message'])
                self.assertEqual(sorted(warning['nearest']), ['location', 'rotation'])
                self.assertEqual([m['grid'] for m in report['assemblies']], [False])
                _, native = compiler.native_split(spec)
                self.assertEqual([m.get('grid') for m in native['assemblies']], [False])
                self.assertEqual(len({c['assembly'] for c in native['copies']}), 1)

    def test_unchanged_assemblies_are_reported(self):
        src = {o['actor']: o for o in assembly_scene()['objects']}
        doc = document([dict(target=target(n), location=src[PL + n]['location'], rotation=src[PL + n]['rotation']) for n in CAR])
        spec, report = compile_project(doc, assembly_scene(), enable=['car'])
        self.assertTrue(report['ok'])
        self.assertEqual(spec['objects'], [])
        self.assertEqual([w['code'] for w in report['notes']], ['unchanged'])


class PreviewParityTests(unittest.TestCase):
    """A compiled spec, previewed by the viewer's resolver, shows the project as the viewer draws it (plan section 6,
    item 8): each copy where its pose puts it, within the rotator rounding, and exactly the targets hidden."""

    def check(self, base, doc):
        spec, report = compile_project(doc, base)
        self.assertTrue(report['ok'], refused(report))
        out = resolve_scene(base, spec)
        self.assertEqual(out['preview']['notes'], [])
        copies = {o['provenance']['label']: o for o in out['objects'] if o.get('provenance', {}).get('type') == 'copy'}
        src = {(o['layer'], o['actor']): o for o in base['objects']}
        want = {}
        for rec in doc['overrides']:
            if not rec.get('deleted'):
                want['move:' + rec['target']['actor'].split('.')[-1]] = (rec, src[('base', rec['target']['actor'])])
        for rec in doc['added']:
            want[rec['actor'].split('.')[-1]] = (rec, src[('base', rec['from']['actor'])])
        self.assertEqual(sorted(copies), sorted(want))
        for label, (rec, s) in want.items():
            # The viewer's own matrix for the pose: actorMatrix(pose) x actorMatrix(source pose)^-1 x source matrix,
            # which with no component offset is the pose's transform.
            drawn = view_matrix(multiply(transform(rec['location'], rec['rotation'], s['scale']), s['componentTransform']))
            got = copies[label]['matrix']
            # Each rotator component is rounded by at most half a unit: the axes differ by under 1.5 units' turn.
            worst = max(abs(a - b) for a, b in zip(got[:12], drawn[:12]))
            self.assertLess(worst, 1.5 * math.tau / 65536, label)
            self.assertLess(max(abs(a - b) for a, b in zip(got[12:15], drawn[12:15])), 1e-3, label)
            # The compiler's seed box is the resolver's bounds of the copy.
            lo, hi = bounds(copies[label], base['meshes'])
            box = spec['objects'][0]['boxes'][spec['objects'][0]['labels'].index(label)]
            for k, (a, b) in enumerate([(box[0], lo[0]), (box[1], hi[0]), (box[2], lo[1]), (box[3], hi[1]), (box[4], lo[2]), (box[5], hi[2])]):
                self.assertAlmostEqual(a, b, delta=0.01, msg='%s box %d' % (label, k))
        hidden = sorted(o['actor'] for o in out['objects'] if o.get('hiddenBy') is not None)
        targets = sorted(r['target']['actor'] for r in doc['overrides'])
        self.assertEqual(hidden, targets)

    def test_small_scene(self):
        doc = document([dict(target=target('XComLevelActor_1'), location=[10.5, 20, 30], rotation=[2730.667, 16384.4, -5461.333]),
                        dict(target=target('XComLevelActor_2'), deleted=True),
                        dict(target=target('XComDestructibleActor_4'), location=[0, -48, 0], rotation=[0, -8192, 2730.667])],
                       [add('XComLevelActor_2', 1, (0, 300, 0), (8192, 0, 16384)), add('StaticMeshActor_3', 2, (5, 5, 5), (0, 4096.5, 0)),
                        add('XComDestructibleActor_4', 3, (40, -600, 0), (0, 12000, 0))])
        self.check(scene(), doc)

    def test_the_bars_static_pieces(self):
        base = pinned_bar(self, 12)
        rnd = random.Random(11)
        # pieces of cars, vans, doors and ladders build with their assemblies, not one by one
        joined = compiler.assemblies(base, 'URB_Bar')
        # glowing pieces take their generated lights along (LightTests check those): the parity here is the pieces'
        glowing = {l['emitterAttachment']['owner']['target']['actor'] for l in base['lights']
                   if (l.get('emitterAttachment') or {}).get('status') == 'verified'}
        self.assertGreater(len(glowing), 20)
        pieces = sorted({o['actor'] for o in base['objects'] if o['actorClass'] in STATIC_CLASSES and o['layer'] == 'base'
                         and not o.get('partner') and o['actor'] not in joined and o['actor'] not in glowing})
        self.assertGreater(len(pieces), 750)
        # Destructible props are among them (M1 since EXP-13; cars', vans' and doors' are left out above).
        self.assertGreater(sum(o['actorClass'] == 'XComDestructibleActor' for o in base['objects'] if o['actor'] in pieces), 320)
        chosen = rnd.sample(pieces, 60)
        overrides, added = [], []
        by_actor = {o['actor']: o for o in base['objects']}
        for k, a in enumerate(chosen[:40]):
            s = by_actor[a]
            if k % 4 == 0:
                overrides.append(dict(target=dict(package='URB_Bar', level='base', actor=a), deleted=True))
            else:
                overrides.append(dict(target=dict(package='URB_Bar', level='base', actor=a),
                                      location=[round(s['location'][j] + rnd.uniform(-200, 200), 4) for j in range(3)],
                                      rotation=[round(rnd.uniform(-32768, 32768), 3) for _ in range(3)]))
        for k, a in enumerate(chosen[40:]):
            added.append({'id': '00000000-0000-4000-8000-%012d' % k, 'actor': a + '_copy%d' % (k + 1),
                          'from': dict(package='URB_Bar', level='base', actor=a), 'components': [by_actor[a]['component']],
                          'location': [round(rnd.uniform(-2000, 2000), 4), round(rnd.uniform(-1800, 1800), 4), round(rnd.uniform(0, 400), 4)],
                          'rotation': [round(rnd.uniform(-65536, 65536), 3) for _ in range(3)]})
        doc = document(overrides, added, source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12))
        self.check(base, doc)


# ---------------------------------------------------------------- lights (private/plans/done/editor-lights-plan.md, L6)
def light(name, kind='point', at=(0, 0, 200), role='static', layer='base', package='URB_Bar', **extra):
    rec = dict(id='light:' + name, actor=PL + name, component=PL + name + ('.SpotLightComponent_0' if kind == 'spot'
                                                                          else '.PointLightComponent_0'),
               actorClass={'point': 'PointLight', 'spot': 'SpotLight', 'directional': 'DominantDirectionalLight'}[kind]
               if role != 'area' else 'GeneratedMeshAreaLight',
               sourcePackage=package, layer=layer, kind=kind, role=role, location=list(at),
               rotation=[-16384, 0, 0] if kind == 'spot' else [0, 0, 0], direction=[0, 0, -1],
               color=[1.0, 0.8, 0.6], brightness=1.5, enabled=True, castShadows=True,
               lightmapGuid='%032x' % (abs(hash(name)) % 16 ** 32), lightGuid='%032x' % (abs(hash(name + 'x')) % 16 ** 32),
               bakedInto=['XComLevelActor_1'], shadowMapped=[], channels=False, saved=['LightColor'], referencedBy=[])
    if kind in ('point', 'spot'):
        rec.update(radius=512.0, falloffExponent=2.0)
    if kind == 'spot':
        rec.update(innerConeAngle=10.0, outerConeAngle=40.0)
    rec.update(extra)
    return rec


def attachment(owner, status='verified', candidates=()):
    return dict(status=status, reason='', owner=dict(target=target(owner), component=PL + owner + '.StaticMeshComponent_0',
                                                    objectId=owner) if owner else None,
                candidates=[dict(objectId=c) for c in candidates], ownerMatrix=None, local=None, matcher=1)


def light_scene():
    s = scene()
    s['lights'] = [
        light('PointLight_40'),
        light('SpotLight_41', kind='spot', at=(96, 0, 300), outerConeAngle=580.0),
        light('GeneratedMeshAreaLight_42', kind='spot', role='area', at=(96, 0, 60), radius=300.0, bakedInto=[],
              channels=True, emitterAttachment=attachment('XComLevelActor_2')),
        light('GeneratedMeshAreaLight_43', kind='spot', role='area', at=(0, -40, 60), radius=300.0, bakedInto=[],
              channels=True, emitterAttachment=attachment(None, 'ambiguous', ['XComLevelActor_1', 'XComDestructibleActor_4'])),
        light('SpotLightToggleable_44', kind='spot', role='toggleable',
              referencedBy=['XComDestructibleActor_14 ToggleLight (XComDestructibleActor_Action_ToggleLight_0)']),
        light('PointLight_45', channels=True),
        light('DominantDirectionalLight_46', kind='directional', role='dominant'),
        light('PointLight_47', layer='stream', package='patch_bar'),
        light('PointLight_48', referencedBy=['SeqAct_Toggle_0 Target']),
        light('PointLight_49', bakedInto=[]),
        {k: v for k, v in light('PointLight_50').items() if k not in ('lightmapGuid', 'bakedInto')},
    ]
    for o in s['objects']:
        o['areaLights'] = {'XComLevelActor_2': ['light:GeneratedMeshAreaLight_42'],
                           'XComLevelActor_1': ['light:GeneratedMeshAreaLight_43'],
                           'XComDestructibleActor_4': ['light:GeneratedMeshAreaLight_43']}.get(o['id'], []) \
            if o['layer'] == 'base' else []
    return s


def light_add(name, serial, at, rot=(0, 0, 0), **extra):
    rec = {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + '%s_copy%d' % (name, serial), 'from': target(name),
           'components': [PL + name + ('.SpotLightComponent_0' if 'Spot' in name else '.PointLightComponent_0')],
           'location': list(at), 'rotation': list(rot)}
    rec.update(extra)
    return rec


def recipe_spot(serial, at, **light_values):
    values = dict(compiler.LIGHT_RECIPES['spot'][1], **light_values)
    return {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + 'SpotLight_copy%d' % serial,
            'template': dict(kind='spot', version=1), 'location': list(at), 'rotation': [-16384, 0, 0], 'light': values}


def lights_of(spec):
    return next((o for o in spec['objects'] if o['type'] == 'lights'), None)


class LightTests(unittest.TestCase):
    def compile(self, overrides=(), added=(), enable=('light',), scene_=None, **doc):
        return compile_project(document(overrides, added, **doc), scene_ or light_scene(), enable)

    def test_light_edits_build_and_the_family_off_refuses_them_with_its_note(self):
        # on for every project since 9 November (the user's word after EXP-26 run 1)
        spec, report = self.compile([dict(target=target('PointLight_40'), deleted=True)], enable=())
        self.assertEqual(codes(report), [])
        self.assertIn('light', report['families'])
        self.assertEqual([d['name'] for d in lights_of(spec)['deletes']], ['PointLight_40'])
        self.assertIsNone(compiler.FAMILIES['light']['milestone'])
        # switched off, the refusal comes back with the page's note
        with mock.patch.dict(compiler.FAMILIES['light'], builds=False):
            _, report = self.compile([dict(target=target('PointLight_40'), deleted=True)], enable=())
            self.assertEqual(codes(report), ['family'])
            self.assertIn(compiler.FAMILIES['light']['note'], refused(report)[0]['message'])
            self.assertEqual(refused(report)[0]['family'], 'light')
            self.assertNotIn('light', report['families'])

    def test_a_deleted_moved_changed_and_copied_light(self):
        spec, report = self.compile(
            [dict(target=target('PointLight_40'), deleted=True),
             dict(target=target('SpotLight_41'), location=[200, 0, 300], light=dict(color=[255, 196, 140], brightness=2.5))],
            [light_add('SpotLight_41', 3, (500, 500, 300), (-16384, 0, 0), light=dict(radius=900))])
        self.assertTrue(report['ok'], refused(report))
        lights = lights_of(spec)
        self.assertEqual([d['name'] for d in lights['deletes']], ['PointLight_40'])
        self.assertEqual(lights['deletes'][0]['reach'], [-512.0, 512.0, -512.0, 512.0, -312.0, 712.0])
        change = lights['changes'][0]
        self.assertEqual(change['set'], dict(color=[255, 196, 140], brightness=2.5))
        # the stored 580-degree cone is kept raw: a move and a recolour don't touch it
        self.assertEqual(change['light']['outerConeAngle'], 580.0)
        self.assertEqual(change['before']['outerConeAngle'], 580.0)
        self.assertEqual(change['before']['color'], [255, 204, 153])
        self.assertEqual(change['location'], [200, 0, 300])
        self.assertEqual(change['reach']['after'][0], 200 - 512)
        add_ = lights['adds'][0]
        self.assertEqual((add_['from'], add_['name'], add_['light']['radius'], add_['light']['outerConeAngle']),
                         ('SpotLight_41', 'SpotLight_41_copy3', 900, 580.0))
        self.assertEqual(add_['guidSeed'], '5005037f-f7ac-4287-97f6-d1cab95360f9|SpotLight_41_copy3')
        self.assertEqual(report['counts']['lights'], dict(deleted=1, added=1, changed=1, area=0))
        # the Build's writer makes them: native_split moves the object to the native edit
        patch, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual(patch['objects'], [])
        self.assertEqual(native['lights']['changes'][0]['name'], 'SpotLight_41')
        self.assertNotIn('lights', compiler.native_split(compiler.stream_only(
            self.compile([dict(target=target('StaticMeshActor_3'), deleted=True)])[0]))[1])

    def test_a_recipe_spot_and_its_refusals(self):
        spec, report = self.compile([], [recipe_spot(4, (10, 20, 300), color=[10, 20, 30])])
        self.assertTrue(report['ok'], refused(report))
        add_ = lights_of(spec)['adds'][0]
        self.assertEqual((add_['template'], add_['name'], add_['light']['color'], add_['rotation']),
                         (dict(kind='spot', version=1), 'SpotLight_copy4', [10, 20, 30], [-16384, 0, 0]))
        self.assertNotIn('from', add_)
        bad = {'an unknown version': dict(recipe_spot(5, (0, 0, 0)), template=dict(kind='spot', version=9)),
               'both forms': dict(recipe_spot(5, (0, 0, 0)), **{'from': target('SpotLight_41')}),
               'an incomplete light': dict(recipe_spot(5, (0, 0, 0)), light=dict(brightness=1.0))}
        for case, rec in bad.items():
            with self.subTest(case=case):
                self.assertEqual(len(left_out(self.compile([], [rec])[1])), 1)

    def test_a_recipe_point_has_no_cones_or_direction(self):
        # prefab plan 5.5: a prefab's point lights are recipe lights, so they need no map
        values = dict(compiler.LIGHT_RECIPES['point'][1], radius=640.0)
        point = lambda **more: dict({'id': '00000000-0000-4000-8000-000000000006', 'actor': PL + 'PointLight_copy6',
                                     'template': dict(kind='point', version=1), 'location': [10, 20, 300], 'rotation': [0, 0, 0],
                                     'light': dict(values)}, **more)
        self.assertEqual(sorted(values), ['brightness', 'color', 'enabled', 'falloffExponent', 'radius'])
        spec, report = self.compile([], [point()])
        self.assertTrue(report['ok'], refused(report))
        add_ = lights_of(spec)['adds'][0]
        self.assertEqual((add_['template'], add_['name'], add_['kind'], add_['light'], add_['rotation']),
                         (dict(kind='point', version=1), 'PointLight_copy6', 'point', values, [0, 0, 0]))
        bad = {'cones': point(light=dict(values, innerConeAngle=0.0, outerConeAngle=44.0)),
               'an incomplete light': point(light=dict(radius=640.0)),
               'an unknown version': point(template=dict(kind='point', version=2))}
        for case, rec in bad.items():
            with self.subTest(case=case):
                self.assertEqual(len(left_out(self.compile([], [rec])[1])), 1)

    def test_view_only_lights_are_refused_with_their_reason(self):
        for name, why in [('GeneratedMeshAreaLight_42', 'glowing surface'), ('SpotLightToggleable_44', 'lit live'),
                          ('PointLight_45', 'lighting channels'), ('DominantDirectionalLight_46', 'sun, moon or sky'),
                          ('PointLight_48', 'Kismet'), ('PointLight_49', 'no lightmap'),
                          ('PointLight_50', 'light data')]:
            with self.subTest(light=name):
                _, report = self.compile([dict(target=target(name), location=[1, 2, 3])])
                self.assertEqual(codes(report), ['light-view-only'])
                self.assertIn(why, refused(report)[0]['message'])
        _, report = self.compile([dict(target=target('PointLight_47', 'stream', 'patch_bar'), deleted=True)])
        self.assertEqual(codes(report), ['level'])
        _, report = self.compile([], [light_add('PointLight_45', 1, (0, 0, 0))])
        self.assertEqual(codes(report), ['light-view-only'])

    def test_submitted_values_are_checked_but_inherited_ones_kept(self):
        cases = {'colour above 255': ('SpotLight_41', dict(color=[256, 0, 0])),
                 'colour as floats': ('SpotLight_41', dict(color=[1.0, 0.5, 0.5])),
                 'not finite': ('PointLight_40', dict(brightness=float('nan'))),
                 'a cone on a point light': ('PointLight_40', dict(outerConeAngle=30)),
                 'enabled not a bool': ('SpotLight_41', dict(enabled=1)),
                 'an unknown value': ('SpotLight_41', dict(castShadows=False))}
        for case, (name, values) in cases.items():
            with self.subTest(case=case):
                _, report = self.compile([dict(target=target(name), light=values)])
                self.assertEqual(len(left_out(report)), 1)
        # a number outside its range is built at the nearest value in range, with a warning (plan R3)
        clamped = {'brightness above 100': ('SpotLight_41', dict(brightness=101), dict(brightness=100.0)),
                   'radius below 1': ('PointLight_40', dict(radius=0.5), dict(radius=1.0)),
                   'falloff below 0.1': ('PointLight_40', dict(falloffExponent=0.0), dict(falloffExponent=0.1)),
                   'inner wider than outer': ('SpotLight_41', dict(innerConeAngle=60, outerConeAngle=30),
                                              dict(innerConeAngle=30, outerConeAngle=30)),
                   'outer above 89.99': ('SpotLight_41', dict(outerConeAngle=100), dict(outerConeAngle=89.99))}
        for case, (name, values, built_as) in clamped.items():
            with self.subTest(case=case):
                spec, report = self.compile([dict(target=target(name), light=values)])
                self.assertEqual((left_out(report), noted(report, 'light-')), ([], ['light-clamped']))
                after = lights_of(spec)['changes'][0]['light']
                self.assertEqual({k: after[k] for k in built_as}, built_as)
                self.assertIn(name, report['notes'][0]['message'])
        # editing the inner cone of the stored-580 spot: valid (inner 30 is no wider than the stored outer)
        spec, report = self.compile([dict(target=target('SpotLight_41'), light=dict(innerConeAngle=30))])
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(lights_of(spec)['changes'][0]['light']['outerConeAngle'], 580.0)
        # a malformed inherited value is refused, not carried
        s = light_scene()
        s['lights'][0]['brightness'] = float('inf')
        self.assertEqual(codes(self.compile([dict(target=target('PointLight_40'), location=[5, 0, 200])], scene_=s)[1]),
                         ['light-value'])

    def test_redundant_light_overrides_build_nothing(self):
        spec, report = self.compile([dict(target=target('SpotLight_41'), location=[96, 0, 300],
                                          light=dict(brightness=1.5, color=[255, 204, 153]))])
        self.assertTrue(report['ok'])
        self.assertEqual([w['code'] for w in report['notes']], ['unchanged'])
        self.assertIsNone(lights_of(spec))
        # a disabled light is a real edit
        spec, _ = self.compile([dict(target=target('PointLight_40'), light=dict(enabled=False))])
        self.assertEqual(lights_of(spec)['changes'][0]['set'], dict(enabled=False))

    def test_edits_need_an_export_with_the_light_data(self):
        edit = [dict(target=target('XComLevelActor_1'), deleted=True)]
        for case, change in [('version 17', dict(exporterVersion=17)), ('no metadata', dict(lightMetadata=None)),
                             ('no matcher', dict(lightMetadata=dict(version=1, areaMatcher=None)))]:
            with self.subTest(case=case):
                s = light_scene()
                s.update(change)
                _, report = self.compile(edit, scene_=s)
                self.assertEqual(codes(report), ['export-version'])
                self.assertIn('re-export', refused(report)[0]['message'])
                self.assertIsNone(compiler.light_metadata_problem(light_scene()))
        # a project with nothing in it compiles on an old export (and builds nothing)
        s = light_scene()
        s['exporterVersion'] = 17
        self.assertTrue(self.compile(scene_=s)[1]['ok'])

    def test_a_glowing_piece_takes_its_area_lights_along(self):
        spec, report = self.compile([dict(target=target('XComLevelActor_2'), location=[96, 96, 0], rotation=[0, 16384, 0])],
                                    [add('XComLevelActor_2', 7, (500, 0, 0))])
        self.assertTrue(report['ok'], refused(report))
        area = lights_of(spec)['area']
        self.assertEqual([(a['op'], a['name']) for a in area],
                         [('copy', 'GeneratedMeshAreaLight_42_XComLevelActor_2_copy7'), ('move', 'GeneratedMeshAreaLight_42')])
        copy_, move = area
        # the move turns the light a quarter about the piece's place: (96, 0) -> (96, 96), its yaw +16384
        self.assertEqual(move['location'], [96.0, 96.0, 60.0])
        self.assertEqual(move['rotation'], [-16384, 16384, 0])
        self.assertEqual(copy_['location'], [500.0, 0.0, 60.0])
        self.assertEqual(copy_['guidSeed'], '5005037f-f7ac-4287-97f6-d1cab95360f9|GeneratedMeshAreaLight_42|XComLevelActor_2_copy7')
        self.assertEqual(report['counts']['lights']['area'], 2)
        # deleted, its light goes; with the family off, the piece's edit is refused (the light isn't left behind)
        spec, _ = self.compile([dict(target=target('XComLevelActor_2'), deleted=True)], enable=())
        self.assertEqual([a['op'] for a in lights_of(spec)['area']], ['delete'])
        with mock.patch.dict(compiler.FAMILIES['light'], builds=False):
            _, report = self.compile([dict(target=target('XComLevelActor_2'), deleted=True)], enable=())
            # (a warning: the piece is deleted, the light stays)
            self.assertEqual((left_out(report), noted(report, 'family')), ([], ['family']))
            self.assertIn('GeneratedMeshAreaLight_42', report['notes'][0]['message'])

    def test_an_unsettled_glow_needs_resolving_before_its_piece_moves(self):
        edit = [dict(target=target('XComLevelActor_1'), location=[0, 0, 64])]
        spec, report = self.compile(edit)
        # (a warning since plan R4: the piece moves, the light stays where the map has it)
        self.assertEqual((left_out(report), noted(report, 'area-')), ([], ['area-light-unresolved']))
        self.assertIsNone(lights_of(spec))
        # kept fixed: the piece moves alone
        keep = [dict(target=target('GeneratedMeshAreaLight_43'), owner=None)]
        spec, report = self.compile(edit, areaLightBindings=keep)
        self.assertTrue(report['ok'], refused(report))
        self.assertIsNone(lights_of(spec))
        # assigned to the piece: it follows
        bind = [dict(target=target('GeneratedMeshAreaLight_43'),
                     owner=dict(target=target('XComLevelActor_1'), component=PL + 'XComLevelActor_1.StaticMeshComponent_0'))]
        spec, report = self.compile(edit, areaLightBindings=bind)
        self.assertEqual([(a['op'], a['location']) for a in lights_of(spec)['area']], [('move', [0.0, -40.0, 124.0])])
        # bad bindings: not an area light, an owner the export lacks, twice
        for case, records in [('not an area light', [dict(keep[0], target=target('PointLight_40'))]),
                              ('a missing owner', [dict(bind[0], owner=dict(target=target('Nope_1'), component='x'))]),
                              ('twice', keep + keep)]:
            with self.subTest(case=case):
                self.assertIn('area-binding', codes(self.compile(edit, areaLightBindings=records)[1]))

    def test_light_specs_are_deterministic(self):
        overrides = [dict(target=target('PointLight_40'), deleted=True),
                     dict(target=target('SpotLight_41'), light=dict(brightness=3))]
        added = [light_add('SpotLight_41', 3, (500, 500, 300)), recipe_spot(4, (1, 2, 3)), add('XComLevelActor_2', 5, (0, 400, 0))]
        first = json.dumps(self.compile(overrides, added)[0])
        rnd = random.Random(6)
        for _ in range(5):
            o, a = overrides[:], added[:]
            rnd.shuffle(o); rnd.shuffle(a)
            self.assertEqual(json.dumps(self.compile(o, a)[0]), first)

    def test_rotators_come_back_from_their_matrices(self):
        rnd = random.Random(3)
        for _ in range(200):
            rot = [rnd.randrange(-16000, 16000), rnd.randrange(-32768, 32768), rnd.randrange(-32768, 32768)]
            back = compiler.rotator_of(transform([0, 0, 0], rot, [1, 1, 1]))
            a, b = transform([0, 0, 0], rot, [1, 1, 1]), transform([0, 0, 0], back, [1, 1, 1])
            self.assertTrue(all(abs(a[i][j] - b[i][j]) < 2e-4 for i in range(3) for j in range(3)), (rot, back))

    def test_find_export_takes_a_new_enough_generation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            def make(name, version, sha=BAR_SHA, text=None):
                folder = Path(root) / 'URB_Bar' / name
                folder.mkdir(parents=True)
                (folder / 'scene.json').write_text(text if text is not None else json.dumps(dict(
                    schemaVersion=1, name='URB_Bar', scope='map', exporterVersion=version, source=dict(sha256=sha))),
                    encoding='utf-8')
            doc = dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=17))
            make(BAR_SHA[:16] + '-v17-map', 17)
            with self.assertRaisesRegex(compiler.ExportMissing, 'version 18 or newer'):
                compiler.find_export(root, doc)
            make(BAR_SHA[:16] + '-v18-map', 18)
            make('b' * 16 + '-v19-map', 19, 'b' * 64)       # another package's newer export never stands in
            scene_path, data = compiler.find_export(root, doc)
            self.assertEqual((scene_path.parent.name, data['exporterVersion']), (BAR_SHA[:16] + '-v18-map', 18))
            self.assertEqual(compiler.find_export(root, doc, minimum=17)[1]['exporterVersion'], 17)
            # a later export at the same version is published beside it with a suffix (export.py): the newest is taken
            make(BAR_SHA[:16] + '-v18-map-x1y2z3', 18)
            os.utime(Path(root) / 'URB_Bar' / (BAR_SHA[:16] + '-v18-map') / 'scene.json', (1_000_000, 1_000_000))
            self.assertEqual(compiler.find_export(root, doc)[0].parent.name, BAR_SHA[:16] + '-v18-map-x1y2z3')
            # a newer candidate that can't be used is passed over for the next (review finding 17): truncated, of
            # another schema, of another package under this one's name, or of another version than its name says
            make(BAR_SHA[:16] + '-v20-map', 20, text='{"schemaVersion": 1, "name": "URB_B')
            make(BAR_SHA[:16] + '-v21-map', 21, text=json.dumps(dict(schemaVersion=2, name='URB_Bar', scope='map',
                                                                     exporterVersion=21, source=dict(sha256=BAR_SHA))))
            make(BAR_SHA[:16] + '-v22-map', 22, sha=BAR_SHA[:16] + 'f' * 48)
            make(BAR_SHA[:16] + '-v23-map', 22)
            self.assertEqual(compiler.find_export(root, doc)[0].parent.name, BAR_SHA[:16] + '-v18-map-x1y2z3')


def cover(serial, at, width=1, length=1, kind='high', rot=(0, 0, 0), height=1, **extra):
    """An added cover block (compiler.COVER_RECIPES), its corner at `at`: `kind` its type, `height` in tiles."""
    rec = {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + 'CoverBlock_copy%d' % serial,
           'template': dict(kind='cover', version=1), 'cover': dict(width=width, length=length, type=kind, height=height),
           'location': list(at), 'rotation': list(rot)}
    rec.update(extra)
    return rec


class CoverTests(unittest.TestCase):
    def test_cover_blocks_go_to_the_writer_with_their_box(self):
        doc = document(added=[cover(1, (-1824, -960, 0)), cover(2, (-1536, -960, 0), 2, 1, 'low', (0, 16384, 0))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        blocks = [o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks']
        high, low = blocks
        self.assertEqual((high['name'], high['kind'], high['size'], high['heights']),
                         ('CoverBlock_copy1', 'high', [96.0, 96.0], [-12.0, 96.0]))
        self.assertEqual(high['box'], [-1824.0, -1728.0, -960.0, -864.0, -12.0, 96.0])
        self.assertEqual((low['kind'], low['size'], low['heights'], low['rotation']),
                         ('low', [192.0, 96.0], [-12.0, 84.0], [0, 16384, 0]))
        # turned a quarter: its 2 tiles along X lie along Y, back from its corner along X
        self.assertEqual(low['box'], [-1632.0, -1536.0, -960.0, -768.0, -12.0, 84.0])
        self.assertEqual(report['counts']['added'], 2)
        self.assertEqual({e['entity'] for e in report['entities'] if e['kind'] == 'add'},
                         {PL + 'CoverBlock_copy1', PL + 'CoverBlock_copy2'})
        _, native = compiler.native_split(compiler.stream_only(spec))
        self.assertEqual([c['name'] for c in native['covers']], ['CoverBlock_copy1', 'CoverBlock_copy2'])
        self.assertEqual(native['copies'], [])
        self.assertFalse(_['objects'])          # nothing left for a patch

    def test_a_block_two_tiles_tall_and_an_invisible_floor(self):
        doc = document(added=[cover(1, (0, 0, 0), 1, 2, 'high', height=2), cover(2, (96, 0, 64), 3, 2, 'floor')])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        tall, floor = [o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks']
        self.assertEqual((tall['kind'], tall['size'], tall['heights']), ('high', [96.0, 192.0], [-12.0, 192.0]))
        self.assertEqual(tall['box'], [0.0, 96.0, 0.0, 192.0, -12.0, 192.0])
        self.assertEqual((floor['kind'], floor['size'], floor['heights']), ('floor', [288.0, 192.0], [-2.0, 0.0]))
        self.assertEqual(floor['box'], [96.0, 384.0, 0.0, 192.0, 62.0, 64.0])      # its top at its location
        self.assertEqual([e['cover'] for e in report['entities'] if e['kind'] == 'add'],
                         [dict(width=1, length=2, type='high', height=2), dict(width=3, length=2, type='floor', height=1)])

    def test_a_first_record_reads_as_one_tile_tall(self):
        old = dict(cover(1, (0, 0, 0)), cover=dict(width=2, length=1, height='low'))
        spec, report = compile_project(document(added=[old]), scene())
        self.assertTrue(report['ok'], refused(report))
        [block] = [o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks']
        self.assertEqual((block['kind'], block['heights']), ('low', [-12.0, 84.0]))
        self.assertEqual([e['cover'] for e in report['entities'] if e['kind'] == 'add'],
                         [dict(width=2, length=1, type='low', height=1)])

    def test_malformed_cover_blocks_are_refused(self):
        bad = {
            'an unknown version': cover(1, (0, 0, 0), template=dict(kind='cover', version=9)),
            'too wide': cover(1, (0, 0, 0), width=17),
            'no tiles': cover(1, (0, 0, 0), length=0),
            'a fractional size': cover(1, (0, 0, 0), width=1.5),
            'an unknown type': cover(1, (0, 0, 0), kind='medium'),
            'too tall': cover(1, (0, 0, 0), height=9),
            'no height': cover(1, (0, 0, 0), height=0),
            'a tall floor': cover(1, (0, 0, 0), kind='floor', height=2),
            'a missing value': dict(cover(1, (0, 0, 0)), cover=dict(width=1, length=1, type='high')),
            'an old record with a number': dict(cover(1, (0, 0, 0)), cover=dict(width=1, length=1, height=2)),
            'a copy as well': dict(cover(1, (0, 0, 0)), **{'from': target('XComLevelActor_1')}),
            'cover values on a copy': dict(add('XComLevelActor_1', 1, (0, 0, 0)), cover=dict(width=1, length=1, type='low', height=1)),
        }
        for why, rec in bad.items():
            with self.subTest(why):
                spec, report = compile_project(document(added=[rec]), scene())
                self.assertEqual((len(left_out(report)), built(report)), (1, 0))
                self.assertTrue(set(codes(report)) <= {'malformed', 'cover-recipe'}, codes(report))

    def test_a_cover_block_in_a_group_that_breaks_together_breaks_with_its_one_prop(self):
        doc = document(added=[cover(1, (0, 0, 0)), add('XComDestructibleActor_4', 2, (96, 96, 0)), cover(3, (192, 0, 0))],
                       groups=[dict(id='g1', locked=True, breakTogether=True,
                                    members=[dict(added=PL + 'CoverBlock_copy1'),
                                             dict(added=PL + 'XComDestructibleActor_4_copy2')])])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual([w['code'] for w in report['warnings']], [])
        [g] = report['groups']
        self.assertEqual((g['number'], g['copies'], g['blocks'], g['notBreakable']),
                         (1, ['XComDestructibleActor_4_copy2'], ['CoverBlock_copy1'], []))
        native = compiler.native_split(spec)[1]
        # the block of the group carries its number; the one outside any group is as it was
        self.assertEqual([(c['name'], c.get('breakGroup')) for c in native['covers']],
                         [('CoverBlock_copy1', 1), ('CoverBlock_copy3', None)])
        self.assertEqual([c['breakGroup'] for c in native['copies']], [1])
        self.assertEqual({e['entity']: e['actorClass'] for e in report['entities'] if e.get('cover')},
                         {PL + 'CoverBlock_copy1': 'XComDestructibleActor', PL + 'CoverBlock_copy3': 'XComLevelActor'})

    def test_a_cover_block_breaks_with_a_map_prop_left_in_place(self):
        # no copy in the project: the map's piece reaches the Build in an object of its own
        doc = document(added=[cover(1, (0, 0, 0))],
                       groups=[dict(id='g1', locked=True, breakTogether=True,
                                    members=[dict(added=PL + 'CoverBlock_copy1'), target('XComDestructibleActor_4')])])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual([w['code'] for w in report['warnings']], [])
        self.assertEqual([o['type'] for o in spec['objects']], ['breakOriginals', 'covers'])
        patch, native = compiler.native_split(spec)
        self.assertEqual(patch['objects'], [])
        self.assertEqual(native['breakOriginals'], [dict(name='XComDestructibleActor_4', group=1)])
        self.assertEqual([c['breakGroup'] for c in native['covers']], [1])
        self.assertEqual(native['copies'], [])

    def test_a_cover_block_with_no_prop_or_an_invisible_floor_stays(self):
        doc = document(added=[cover(1, (0, 0, 0)), cover(2, (96, 0, 0)), add('XComLevelActor_1', 3, (0, 400, 0))],
                       groups=[dict(id='g1', locked=True, breakTogether=True,
                                    members=[dict(added=PL + 'CoverBlock_copy1'), dict(added=PL + 'CoverBlock_copy2'),
                                             dict(added=PL + 'XComLevelActor_1_copy3')])])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual({w['code'] for w in report['notes']}, {'group-unbreakable'})
        self.assertEqual(report['groups'][0]['number'], 0)
        self.assertTrue(all('breakGroup' not in c for c in compiler.native_split(spec)[1]['covers']))
        doc = document(added=[cover(1, (0, 0, 64), kind='floor'), add('XComDestructibleActor_4', 2, (96, 96, 0)),
                              add('XComDestructibleActor_4', 3, (96, 192, 0))],
                       groups=[dict(id='g1', locked=True, breakTogether=True,
                                    members=[dict(added=PL + 'CoverBlock_copy1'),
                                             dict(added=PL + 'XComDestructibleActor_4_copy2'),
                                             dict(added=PL + 'XComDestructibleActor_4_copy3')])])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        [g] = report['groups']
        self.assertEqual((g['number'], g['blocks'], g['notBreakable']), (1, [], ['CoverBlock_copy1']))
        self.assertTrue(all('breakGroup' not in c for c in compiler.native_split(spec)[1]['covers']))

    def test_the_page_gets_the_recipe(self):
        import families
        t = families.table()['coverRecipes']
        self.assertEqual((t['versions'], t['latest'], t['maxTiles'], t['maxHeight'], t['heightStep'], t['flat']),
                         ([1, 2], 2, 16, 8, 96.0, ['floor']))
        self.assertEqual(t['heights'], {'high': [-12.0, 96.0], 'low': [-12.0, 84.0], 'floor': [-2.0, 0.0],
                                        'block': [-12.0, 96.0]})
        self.assertEqual(t['types'], {'1': ['floor', 'high', 'low'], '2': ['block', 'floor', 'high', 'low']})

    def test_a_blocker_is_version_2s_and_goes_to_the_writer_with_its_version(self):
        """A blocker (Discord feedback S6) is the high block's box with no cover: version 2 makes it, version 1 doesn't.
        Each block reaches the Build with the version it was saved with."""
        doc = document(added=[cover(1, (0, 0, 0)), cover(2, (96, 0, 0), kind='block', height=2,
                                                          template=dict(kind='cover', version=2))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        high, block = [o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks']
        self.assertEqual((high['kind'], high['version']), ('high', 1))
        self.assertEqual((block['kind'], block['version'], block['heights']), ('block', 2, [-12.0, 192.0]))
        self.assertEqual([c['version'] for c in compiler.native_split(spec)[1]['covers']], [1, 2])
        spec, report = compile_project(document(added=[cover(1, (0, 0, 0), kind='block')]), scene())
        self.assertEqual((len(left_out(report)), built(report)), (1, 0))
        self.assertEqual(codes(report), ['malformed'])

    def test_a_record_in_units_is_the_same_block_as_one_in_tiles(self):
        """The editor's handles save sizes in units (cover-block-handles-plan.md): a whole-tile size in units gives the
        block its whole-tile record gives."""
        tiles = document(added=[cover(1, (0, 0, 0), 2, 1, 'high', height=2), cover(2, (192, 0, 64), 3, 2, 'floor')])
        units = document(added=[dict(cover(1, (0, 0, 0)), cover=dict(type='high', size=[192, 96], heights=[-12, 192])),
                                dict(cover(2, (192, 0, 64)), cover=dict(type='floor', size=[288, 192]))])
        blocks = []
        for doc in (tiles, units):
            spec, report = compile_project(doc, scene())
            self.assertTrue(report['ok'], refused(report))
            self.assertEqual(report['warnings'], [])
            blocks.append([o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks'])
        self.assertEqual(blocks[0], blocks[1])

    def test_blocks_smaller_than_a_tile_and_what_the_game_makes_of_them(self):
        """Half a tile, a thin wall along a tile edge, a block too thin for the game, one too short to give cover, one
        floating over where the game looks for cover and a thin plate under it: all built, the last four warned of
        (the plate is four tiles across, so the game counts it: it isn't thin, but it is short). A blocker that short
        is not warned of: it gives no cover anyway."""
        doc = document(added=[
            dict(cover(1, (24, 24, 0)), cover=dict(type='high', size=[48, 48], heights=[-12, 96])),
            dict(cover(2, (92, 0, 0)), cover=dict(type='high', size=[8, 96], heights=[-12, 96])),
            dict(cover(3, (192, 0, 0)), cover=dict(type='low', size=[2, 96], heights=[-12, 84])),
            dict(cover(4, (288, 0, 0)), cover=dict(type='high', size=[96, 96], heights=[-12, 40])),
            dict(cover(5, (384, 0, 0), template=dict(kind='cover', version=2)),
                 cover=dict(type='block', size=[96, 96], heights=[10, 40])),
            dict(cover(6, (480, 0, 0)), cover=dict(type='high', size=[96, 96], heights=[60, 160])),
            dict(cover(7, (576, 0, 0)), cover=dict(type='high', size=[384, 96], heights=[-12, -10]))])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        half, wall, thin, short_, blocker, high_up, plate = [o for o in spec['objects'] if o['type'] == 'covers'][0]['blocks']
        self.assertEqual((half['size'], half['heights'], half['box']), ([48.0, 48.0], [-12.0, 96.0], [24.0, 72.0, 24.0, 72.0, -12.0, 96.0]))
        self.assertEqual(wall['box'], [92.0, 100.0, 0.0, 96.0, -12.0, 96.0])
        self.assertEqual((blocker['heights'], blocker['box'][4:]), ([10.0, 40.0], [10.0, 40.0]))     # floating off the floor
        self.assertEqual(sorted((w['code'], w['message'].split(' ')[0]) for w in report['warnings']),
                         [('cover-short', 'CoverBlock_copy4'), ('cover-short', 'CoverBlock_copy6'),
                          ('cover-short', 'CoverBlock_copy7'), ('cover-thin', 'CoverBlock_copy3')])

    def test_malformed_records_in_units_are_refused(self):
        bad = {
            'one number across': dict(type='high', size=[96], heights=[-12, 96]),
            'nothing across': dict(type='high', size=[0, 96], heights=[-12, 96]),
            'too wide': dict(type='high', size=[1537, 96], heights=[-12, 96]),
            'upside down': dict(type='high', size=[96, 96], heights=[96, -12]),
            'too tall': dict(type='high', size=[96, 96], heights=[-12, 800]),
            'no heights': dict(type='high', size=[96, 96]),
            'a floor with heights': dict(type='floor', size=[96, 96], heights=[-2, 0]),
            'a size as text': dict(type='high', size=['96', 96], heights=[-12, 96]),
            'tiles and units both': dict(type='high', size=[96, 96], heights=[-12, 96], width=1),
        }
        for why, c in bad.items():
            with self.subTest(why):
                spec, report = compile_project(document(added=[dict(cover(1, (0, 0, 0)), cover=c)]), scene())
                self.assertEqual((len(left_out(report)), built(report)), (1, 0))
                self.assertEqual(codes(report), ['malformed'])

    def test_a_blocker_breaks_with_its_group(self):
        doc = document(added=[cover(1, (0, 0, 0), kind='block', template=dict(kind='cover', version=2)),
                              add('XComDestructibleActor_4', 2, (96, 96, 0))],
                       groups=[dict(id='g1', locked=True, breakTogether=True,
                                    members=[dict(added=PL + 'CoverBlock_copy1'),
                                             dict(added=PL + 'XComDestructibleActor_4_copy2')])])
        spec, report = compile_project(doc, scene())
        self.assertTrue(report['ok'], refused(report))
        [g] = report['groups']
        self.assertEqual((g['number'], g['blocks']), (1, ['CoverBlock_copy1']))
        self.assertEqual([(c['kind'], c['breakGroup']) for c in compiler.native_split(spec)[1]['covers']], [('block', 1)])



class CarriedEffects(unittest.TestCase):
    """Export 23's effects: the pairs a piece carries go to the native edit as `carriedEffects` (native_effects.py)."""
    def test_the_pairs_reach_the_native_edit(self):
        s = scene()
        s['effects'] = [dict(actor='TheWorld.PersistentLevel.Emitter_4', carriedBy='TheWorld.PersistentLevel.XComLevelActor_116'),
                        dict(actor='TheWorld.PersistentLevel.Emitter_9', carriedBy=None)]
        spec, report = compiler.compile_project(document(), s)
        self.assertTrue(report['ok'], refused(report))
        self.assertEqual(spec['carriedEffects'], {'XComLevelActor_116': ['Emitter_4']})
        _, native = compiler.native_split(spec)
        self.assertEqual(native['carriedEffects'], {'XComLevelActor_116': ['Emitter_4']})
        s['effects'] = []
        spec, _ = compiler.compile_project(document(), s)
        self.assertNotIn('carriedEffects', spec)

if __name__ == '__main__':
    unittest.main()
