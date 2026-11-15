"""The faster-bake plan's parts (private/plans/done/faster-bake-plan.md): packages decoded once, the writer's
changed blocks, the reach test for each texel, pieces relit in bands, the worker pool, the pieces kept for the next
build. The tests on the bar itself run when the map is here."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lighting_fixture  # noqa: E402
import relight  # noqa: E402
import audit_lighting as lighting  # noqa: E402
import decomp  # noqa: E402
import lzo1x  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
HAS_BAR = bool(BAR and BAR.exists() and (BAR.parent / 'Lighting.tfc').exists())
PL = 'TheWorld.PersistentLevel.'
FLOOR = PL + 'XComLevelActor_302.StaticMeshComponent_7'
SMALL = PL + 'XComLevelActor_95.StaticMeshComponent_156'        # 5,740 texels, beside the pool table
TABLE = 'XComDestructibleActor_491'      # the pool table


class Lzo(unittest.TestCase):
    def test_matches_copy_as_a_byte_at_a_time_would_overlapping_or_not(self):
        end = b'\x11\x00\x00'
        # four literals, then a match of four bytes at distance 1, 2 and 4
        for token, distance, expect in ((96, 1, b'dddd'), (100, 2, b'cdcd'), (108, 4, b'abcd')):
            self.assertEqual(lzo1x.decompress(bytes([21]) + b'abcd' + bytes([token, 0]) + end, 8), b'abcd' + expect,
                             distance)


@unittest.skipUnless(HAS_BAR, NO_BAR)
class DecodedOnce(unittest.TestCase):
    def setUp(self):
        decomp._MEMO.clear()
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        for name in (decomp.WORK_ENV, decomp.KEEP_ENV):
            os.environ.pop(name, None)

    def tearDown(self):
        self.env.stop()
        decomp._MEMO.clear()

    def test_a_package_is_decoded_once_in_a_process_and_kept_for_the_next(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ[decomp.WORK_ENV] = d
            before = dict(decomp.STATS)
            first, _ = decomp.decompress_pkg(str(BAR))
            again, _ = decomp.decompress_pkg(str(BAR))
            self.assertIs(first, again)
            self.assertEqual((decomp.STATS['decoded'] - before['decoded'], decomp.STATS['memo'] - before['memo']), (1, 1))
            kept, = Path(d).glob('*.unpacked')
            self.assertEqual(kept.read_bytes(), first)
            # another process (this one with its memory emptied) reads the kept image
            decomp._MEMO.clear()
            third, _ = decomp.decompress_pkg(str(BAR))
            self.assertEqual(third, first)
            self.assertEqual(decomp.STATS['disk'] - before['disk'], 1)
            # an image of the wrong length is not believed
            decomp._MEMO.clear()
            kept.write_bytes(first[:-1])
            self.assertEqual(decomp.decompress_pkg(str(BAR))[0], first)
            self.assertEqual(decomp.STATS['decoded'] - before['decoded'], 2)

    def test_the_kept_folder_holds_the_newest_images_only(self):
        with tempfile.TemporaryDirectory() as d:
            for k in range(5):
                (Path(d) / f'{k:064d}.unpacked').write_bytes(b'x')
                os.utime(Path(d) / f'{k:064d}.unpacked', (1000 + k, 1000 + k))
            decomp.prune_kept(d, keep_files=2)
            self.assertEqual(sorted(p.name[-10:-9] for p in Path(d).iterdir()), ['3', '4'])
            decomp.keep(str(BAR), d)
            self.assertEqual(len(list(Path(d).glob('*.unpacked'))), 3)


class Reach(unittest.TestCase):
    CRATE = [0, 50, 0, 50, 0, 40]
    LAMP = dict(kind='point', location=[25, 25, 300], radius=2000, enabled=True, brightness=1.0)

    def test_a_texel_near_the_edit_is_in_reach_and_one_far_away_is_not(self):
        world = np.array([[60.0, 25, 0], [430, 25, 0], [440, 25, 0], [3000, 25, 0]])
        box = relight.box_of(world)
        self.assertEqual(relight.texel_reach(world, box, [self.CRATE], []).tolist(), [True, True, False, False])

    def test_a_texel_in_the_shadow_the_edit_casts_or_lifts_is_in_reach_however_far(self):
        low = dict(self.LAMP, location=[-400, 25, 60], lightSourceRadius=10)
        # along the line from the lamp through the crate; off that line; beyond the lamp's radius
        world = np.array([[1500.0, 25, 0], [1500, 900, 0], [2500, 25, 0]])
        got = relight.texel_reach(world, relight.box_of(world), [self.CRATE], [low])
        self.assertEqual(got.tolist(), [True, False, False])
        # where the test would cost too much, every texel counts as in reach
        self.assertTrue(relight.texel_reach(world, relight.box_of(world), [self.CRATE], [low], budget=1).all())

    def test_a_texel_near_an_edited_lights_radius_is_in_reach(self):
        lamp = dict(self.LAMP, location=[0, 0, 100], radius=200)
        world = np.array([[100.0, 0, 0], [500, 0, 0], [700, 0, 0]])
        got = relight.texel_reach(world, relight.box_of(world), [], [], edited=[lamp])
        self.assertEqual(got.tolist(), [True, True, False])
        self.assertFalse(relight.texel_reach(world, relight.box_of(world), [], [], edited=[dict(lamp, enabled=False)]).any())

    def test_the_edit_boxes_that_reach_a_piece_are_those_edit_reaches_finds_one_at_a_time(self):
        low = dict(self.LAMP, location=[-400, 25, 60], lightSourceRadius=10)
        sun = dict(kind='directional', toLight=[-0.6, 0.0, 0.8], enabled=True, brightness=1.0)
        far_crate = [5000, 5050, 0, 50, 0, 40]
        for box in ([400, 420, 0, 50, 0, 10], [500, 520, 0, 50, 0, 10], [1400, 1600, 0, 50, -2, 0],
                    [900, 960, 600, 650, -2, 0], [5300, 5350, 0, 50, -2, 0]):
            for lights in ([], [low], [sun], [low, sun]):
                edits = [self.CRATE, far_crate]
                expect = [k for k, e in enumerate(edits) if relight.edit_reaches(box, [e], lights)]
                self.assertEqual(relight.reaching_boxes(box, edits, lights), expect, (box, lights))
                self.assertEqual(bool(relight.reaching_boxes(box, edits, lights, first=True)), bool(expect))


class Jobs(unittest.TestCase):
    def test_large_pieces_go_as_bands_and_the_largest_job_first(self):
        pieces = [('small', None, False, 500), ('large', None, False, 90000), ('middle', 'source', False, 30000)]
        jobs = relight.piece_jobs(pieces, 4, band_texels=20000)
        self.assertEqual(jobs[0], ('middle', 'source', False)[:0] + ('whole', 'middle', 'source', False))
        self.assertEqual(jobs[1:6], [('band', 'large', None, False, k, 5) for k in range(5)])
        self.assertEqual(jobs[6], ('whole', 'small', None, False))
        # one worker, or no band size: every piece whole
        self.assertEqual({j[0] for j in relight.piece_jobs(pieces, 1, band_texels=20000)}, {'whole'})
        self.assertEqual({j[0] for j in relight.piece_jobs(pieces, 4, band_texels=0)}, {'whole'})

    def test_bands_are_put_together_and_a_failed_band_fails_its_piece_once(self):
        done = []

        def job(j):
            out = dict(kind=j[0], path=j[1], error=None, failed=False, seconds=1.0, peakMemory=7)
            if j[0] == 'band':
                if j[1] == 'bad' and j[4] == 1:
                    return dict(out, error='RuntimeError: no', failed=True)
                return dict(out, band=j[4], part=dict(v=np.array([j[4]])))
            if j[0] == 'assemble':
                return dict(out, result=dict(joined=relight.join_parts(j[4])['v'].tolist()))
            return dict(out, result=dict(whole=True))
        queue = [('band', 'big', None, False, k, 3) for k in range(3)] + [('whole', 'one', None, False)] + \
                [('band', 'bad', None, False, k, 2) for k in range(2)]
        with mock.patch.object(relight, '_worker_job', job):
            peak = relight.run_jobs(queue, 1, (), lambda *a: done.append(a))
        self.assertEqual(peak, 7)
        got = {a[0]: a for a in done}
        self.assertEqual(sorted(got), ['bad', 'big', 'one'])
        self.assertEqual(got['big'][1], dict(joined=[0, 1, 2]))
        self.assertEqual(got['big'][4], 4.0)                 # its three bands and their putting together
        self.assertEqual((got['bad'][1], got['bad'][2], got['bad'][3]), (None, 'RuntimeError: no', True))
        self.assertEqual(len(done), 3)

    def test_a_pool_whose_workers_die_stops_the_relight_instead_of_waiting_for_ever(self):
        # workers that can't start (no such map) break the pool, as one that dies at work does
        with self.assertRaises(SystemExit) as stop:
            relight.run_jobs([('whole', PL + 'A.B', None, False), ('whole', PL + 'C.D', None, False)], 2,
                             (str(HERE / 'no-such-map.upk'), None, {}, None, None, {}), lambda *a: None)
        self.assertIn('a relight worker stopped', str(stop.exception.code))
        self.assertIn('2 pieces were not finished', str(stop.exception.code))

    def test_shadow_maps_traced_by_the_workers_are_put_together_in_their_order(self):
        jobs = [dict(path=PL + 'A.C', sm=dict(path='S0'), skipped='its source has no shadow map of this light'),
                dict(path=PL + 'B.C', sm=dict(path='S1')), dict(path=PL + 'D.C', sm=dict(path='S2')),
                dict(path=PL + 'E.C', sm=dict(path='S3'))]
        got = dict(texture=5, x0=3, y0=4, values=np.full((2, 2), 0.25), mask=np.ones((2, 2), bool),
                   original=np.zeros((2, 2)), report=dict(component=PL + 'E.C', texture='T', texelsWritten=4,
                                                          darker=0, lighter=4))
        results = {3: (got, None), 1: (None, None), 2: (None, 'RuntimeError: no')}
        arrays, ops = {}, []
        with tempfile.TemporaryDirectory() as d:
            args = mock.Mock(out=Path(d), variant='V')
            p = mock.Mock()
            p.name = lambda index: 'TheWorld.Texture_%d' % index
            reports, unchanged = relight.shadow_map_results(p, jobs, results, args, arrays, ops, 'the.npz')
            self.assertTrue((Path(d) / 'V-E-shadow.png').is_file())
        self.assertEqual(unchanged, ['S1'])
        self.assertEqual([(r.get('skipped'), r.get('failed')) for r in reports],
                         [('its source has no shadow map of this light', None), ('RuntimeError: no', True), (None, None)])
        self.assertEqual(ops, [dict(op='gray', texture='TheWorld.Texture_5', x0=3, y0=4, npz='the.npz', key='s2')])
        self.assertEqual(sorted(arrays), ['s2', 's2_mask'])

    def test_the_workers_are_counted_by_cores_and_memory(self):
        self.assertGreaterEqual(relight.default_jobs(), 1)
        with mock.patch.object(relight, 'total_memory_mb', lambda: 4096), mock.patch.object(os, 'cpu_count', lambda: 32):
            self.assertEqual(relight.default_jobs(), 3)
        with mock.patch.object(relight, 'total_memory_mb', lambda: 0), mock.patch.object(os, 'cpu_count', lambda: 32):
            self.assertEqual(relight.default_jobs(), 16)
        self.assertGreater(relight.peak_memory_mb(), 0)


class KeptPieces(unittest.TestCase):
    FIELDS = dict(coordinateScale=[0.1, 0.1], coordinateBias=[0.2, 0.3])
    LAMP = dict(kind='point', component='L.C', location=[0, 0, 0], radius=10, guid='aa', guids=['aa', 'bb'])

    def result(self):
        h, w = 3, 4
        return dict(report=dict(component='P', delta=dict(texelsChanged=5, maxFlatChange=0.5, edit=dict(a=1))),
                    scale=[1.0, 2.0, 3.0], onlyChanged=True,
                    images=dict(nac=np.random.rand(h, w, 3), dmc=np.random.rand(h, w, 3),
                                nac_mask=np.ones((h, w), bool), dmc_mask=np.zeros((h, w), bool)),
                    before=np.random.rand(h, w, 3), after=np.random.rand(h, w, 3), covered=np.ones((h, w), bool))

    def test_a_piece_comes_back_as_it_was_kept_and_what_a_build_did_not_use_goes(self):
        with tempfile.TemporaryDirectory() as d:
            cache = relight.PieceCache(Path(d) / 'pieces', 'base', dict(samples=64))
            key = cache.key('P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True]], []])
            self.assertIsNone(cache.load(key))
            r = self.result()
            cache.save(key, r, False)
            cache.save('unchanged', dict(report=dict(component='Q')), True)
            again = relight.PieceCache(Path(d) / 'pieces', 'base', dict(samples=64))
            got = again.load(key)
            self.assertEqual((got['report'], got['scale'], got['onlyChanged']), (r['report'], r['scale'], True))
            for k in ('nac', 'dmc', 'nac_mask', 'dmc_mask'):
                self.assertTrue(np.array_equal(got['images'][k], r['images'][k]), k)
            again.prune()       # the unchanged piece was not asked for in this build
            self.assertEqual([p.name for p in (Path(d) / 'pieces').iterdir()], [key + '.npz'])
            self.assertEqual(relight.PieceCache(Path(d) / 'pieces', 'base', {}).load('unchanged'), None)

    def test_the_key_follows_what_the_piece_depends_on_and_not_a_lights_guids(self):
        with tempfile.TemporaryDirectory() as d:
            cache = relight.PieceCache(d, 'base', dict(samples=64))
            key = cache.key('P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True]], []])
            same = cache.key('P', self.FIELDS, [dict(self.LAMP, guid='zz', guids=['zz'])], [self.LAMP], [[['box', True]], []])
            self.assertEqual(key, same)
            others = [cache.key('Q', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True]], []]),
                      cache.key('P', self.FIELDS, [self.LAMP], [dict(self.LAMP, radius=11)], [[['box', True]], []]),
                      cache.key('P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', False]], []]),
                      cache.key('P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True], ['box2', True]], []]),
                      relight.PieceCache(d, 'another base', dict(samples=64)).key(
                          'P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True]], []]),
                      relight.PieceCache(d, 'base', dict(samples=16)).key(
                          'P', self.FIELDS, [self.LAMP], [self.LAMP], [[['box', True]], []])]
            self.assertEqual(len({key, *others}), 7)


@unittest.skipUnless(HAS_BAR, NO_BAR)
class OnTheBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = lighting.Package(BAR)
        settings = dict(samples=4, bounce_rays=16, stride=2)
        cls.scene = relight.Scene(cls.p, **settings)
        # the pool table casts no shadow and one ceiling spot over the open floor is off
        cls.after = relight.Scene(cls.p, remove_casters=[TABLE], remove_lights=['SpotLight_3'], **settings)
        spot = [l for l in cls.scene.lights if relight.names_match(l['component'], ['SpotLight_3'])]
        cls.reach = dict(edit_boxes=cls.after.edit_boxes, edited=spot)

    def test_the_bands_of_a_piece_give_what_the_piece_gives_whole(self):
        work = relight.prepare_component(self.p, SMALL, self.scene, after=self.after)
        whole = relight.compute_component(work, self.scene, self.after)
        parts = relight.join_parts([relight.compute_component(work, self.scene, self.after, band=(k, 3))
                                    for k in range(3)])
        self.assertEqual(sorted(parts), sorted(whole))
        for key in whole:
            self.assertTrue(np.array_equal(parts[key], whole[key]), key)
        a = relight.assemble_component(self.p, work, whole, self.scene, self.after)
        b = relight.relight_component(self.p, SMALL, self.scene, after=self.after)
        for key in ('nac', 'dmc'):
            self.assertTrue(np.array_equal(a['images'][key], b['images'][key]), key)
        self.assertEqual(a['report'], b['report'])

    def test_unchanged_texels_keep_the_bake_exactly_and_changed_ones_get_what_the_whole_relight_gives(self):
        whole = relight.relight_component(self.p, FLOOR, self.scene, after=self.after)
        fine = relight.relight_component(self.p, FLOOR, self.scene, after=self.after, reach=self.reach, exact=True)
        self.assertTrue(fine['onlyChanged'])
        # the slot scale stays, and only changed texels are written
        self.assertEqual(fine['report']['scales']['relit'], fine['report']['scales']['original'])
        mask = fine['images']['dmc_mask']
        self.assertTrue(0 < mask.sum() < mask.size)
        # the table's shadow is lifted in both: the same texels change, by the same light (the whole relight
        # stores under another scale, so the two are compared as light)
        scale_a, scale_b = whole['report']['scales']['relit'], fine['report']['scales']['relit']
        light_a = whole['images']['dmc'][mask] ** 2.2 * np.asarray(scale_a)
        light_b = fine['images']['dmc'][mask] ** 2.2 * np.asarray(scale_b)
        self.assertLess(float(np.abs(light_a - light_b).max()), 0.02 * float(light_a.max()))
        self.assertGreater(fine['report']['delta']['maxFlatChange'], relight.CHANGE_FLOOR)

    def test_only_the_texels_in_reach_are_worked_out(self):
        near = dict(edit_boxes=self.after.edit_boxes, edited=[])        # the table alone, without the spot's radius
        work = relight.prepare_component(self.p, FLOOR, self.scene, after=self.after, reach=near)
        whole = relight.prepare_component(self.p, FLOOR, self.scene, after=self.after)
        self.assertTrue(whole['whole'] and not work['whole'])
        self.assertLess(len(work['tidx']), len(whole['tidx']))
        self.assertLess(len(work['gidx']), len(whole['gidx']))
        parts = relight.compute_component(work, self.scene, self.after)
        self.assertEqual(len(parts['first_direct']), len(work['tidx']))
        r = relight.assemble_component(self.p, work, parts, self.scene, self.after, exact=True)
        self.assertEqual(r['report']['texels']['inReach'], len(work['tidx']))

    def test_a_piece_with_no_texel_in_reach_is_not_worked_out(self):
        far = dict(edit_boxes=[[90000, 90010, 0, 10, 0, 10]], edited=[])
        r = relight.relight_component(self.p, SMALL, self.scene, after=self.after, reach=far)
        self.assertTrue(r['unchanged'])
        self.assertEqual((r['report']['texels']['inReach'], r['report']['delta']['texelsChanged']), (0, 0))

    def test_only_the_blocks_with_a_changed_texel_are_written_and_no_other_piece_is_touched(self):
        fx = lighting_fixture.Fixture(BAR, 'Lighting_7190')
        lm = fx.component(FLOOR)
        t = fx.redirect(lm['slots'][1]['index'])
        top = t['fields']['mips'][0]
        x0, y0, x1, y1 = lighting_fixture.rect_bounds(lm, top['width'], top['height'])
        before = bytes(t['mips'][0]['raw'])
        texels = np.full((y1 - y0, x1 - x0, 3), 0.5)
        mask = np.zeros((y1 - y0, x1 - x0), bool)
        mask[40:44, 40:44] = True
        fx.image(FLOOR, 1, texels, mask, only_changed=True)
        entry = fx.log[-1]
        self.assertLessEqual(entry['blocksPerMip'][0]['blocks'], 4)
        after = bytes(t['mips'][0]['raw'])
        changed = np.frombuffer(before, np.uint8).reshape(-1, 8) != np.frombuffer(after, np.uint8).reshape(-1, 8)
        self.assertTrue(0 < changed.any(1).sum() <= 4)
        other = fx.others_changed()
        self.assertEqual((other['texels'], other['pieces']), (0, []))
        # with the ring, the padding just outside the rectangle takes its border's new value
        import dxt1
        ringed = lighting_fixture.Fixture(BAR, 'Lighting_7190')
        t2 = ringed.redirect(lm['slots'][1]['index'])
        ringed.image(FLOOR, 1, np.full((y1 - y0, x1 - x0, 3), 0.75), np.ones((y1 - y0, x1 - x0), bool), ring=True)
        got = dxt1.decode_image(t2['mips'][0]['raw'], top['width'], top['height'])
        was = dxt1.decode_image(before, top['width'], top['height'])
        for column in (x0 - 1, x1):
            self.assertLess(float(np.abs(got[y0:y1, column] - 0.75).max()), 0.02)
        self.assertGreater(float(np.abs(was[y0:y1, x0 - 1] - 0.75).mean()), 0.1)       # (it was something else)
        self.assertEqual(ringed.others_changed()['texels'], 0)
        # without only_changed, every block the rectangle touches is encoded again
        whole = lighting_fixture.Fixture(BAR, 'Lighting_7190')
        whole.image(FLOOR, 1, texels, mask)
        self.assertGreater(whole.log[-1]['blocksPerMip'][0]['blocks'], 1000)


if __name__ == '__main__':
    unittest.main()
