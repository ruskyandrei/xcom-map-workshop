"""The cursor's own floors over made floors and roofs (made_cursors.py; custom geometry plan M5b, F-128): the split
rule on plain numbers, and the page's twin (web/floors.js madeStoreys) on the same cases."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import made_cursors  # noqa: E402

# URB_Bar's four map-wide cursor floors (its export's cursorVolumes), breaking at 210, 402 and 594
BAR = [dict(key='C%d' % n, floor=n, box=[-2784.0, -1920.0, lo, 2208.0, 1824.0, hi])
       for n, (lo, hi) in enumerate([(0.0, 210.0), (210.0, 402.0), (402.0, 594.0), (594.0, 768.0)], 1)]
ROOM = [0.0, 0.0, 384.0, 288.0]     # a room's footprint, x0 y0 x1 y1


def slab(top, foot=ROOM, label='Slab', thick=2.0):
    """A made slab's box, 2 thick as the made floors are: its floor starts at made_cursors.UNDER under its underside,
    4 under its top."""
    return dict(box=[foot[0], foot[1], top - thick, foot[2], foot[3], top], label=label)


def area(b):
    return (b[3] - b[0]) * (b[4] - b[1])


class Split(unittest.TestCase):
    def test_a_room_on_the_bar_brings_floors_breaking_at_its_floor_and_roof(self):
        # (F-128, EXP-76 run E) a made floor (192 to 194) and a roof (382 to 386): over the room the floors break 2
        # under their undersides (EXP-80 run G: a floor's cursor looks down from its volume's top, and one starting on
        # a slab's top landed on it), the map's floor numbers kept; outside it each of the bar's floors stands again
        # round the room, the same heights
        s = made_cursors.split(BAR, [slab(194.0, label='Floor'), slab(386.0, label='Roof', thick=4.0)])
        self.assertEqual(s['hidden'], ['C1', 'C2', 'C3', 'C4'])
        over = sorted((v['box'][2], v['box'][5], v['floor']) for v in s['volumes'] if v['over'])
        self.assertEqual(over, [(0.0, 190.0, 1), (190.0, 380.0, 2), (380.0, 594.0, 3), (594.0, 768.0, 4)])
        for v in s['volumes']:
            if v['over']:
                self.assertEqual([v['box'][k] for k in (0, 1, 3, 4)], ROOM)
        for c in BAR:
            outside = [v for v in s['volumes'] if not v['over'] and v['source'] == c['key']]
            self.assertEqual(len(outside), 4)
            self.assertTrue(all(v['floor'] == c['floor'] and v['box'][2] == c['box'][2] and v['box'][5] == c['box'][5]
                                for v in outside))
            self.assertAlmostEqual(sum(area(v['box']) for v in outside), area(c['box']) - 384.0 * 288.0)
        self.assertEqual(s['crossed'], [])

    def test_nothing_overlaps_and_everything_is_covered(self):
        s = made_cursors.split(BAR, [slab(194.0), slab(386.0, foot=[192.0, 96.0, 768.0, 480.0])])
        boxes = [v['box'] for v in s['volumes']]
        for n, a in enumerate(boxes):
            for b in boxes[n + 1:]:
                self.assertFalse(all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > 1e-6 for k in range(3)), (a, b))
        whole = sum(area(c['box']) * (c['box'][5] - c['box'][2]) for c in BAR)
        self.assertAlmostEqual(sum(area(b) * (b[5] - b[2]) for b in boxes), whole, 1)

    def test_a_slab_on_a_break_or_near_the_bottom_changes_nothing(self):
        # (its floor's start, 4 under its top, on a break of the map's, or within half a storey of the bottom)
        for top in (214.0, 406.0, 16.0, 90.0):
            self.assertEqual(made_cursors.split(BAR, [slab(top)]), dict(hidden=[], volumes=[], crossed=[]), top)
        self.assertEqual(made_cursors.split(BAR, []), dict(hidden=[], volumes=[], crossed=[]))

    def test_a_top_with_no_break_near_adds_a_floor_and_the_floors_over_it_go_up(self):
        one = [dict(key='A', floor=1, box=[-1000.0, -1000.0, 0.0, 1000.0, 1000.0, 210.0]),
               dict(key='B', floor=2, box=[-1000.0, -1000.0, 210.0, 1000.0, 1000.0, 768.0])]
        s = made_cursors.split(one, [slab(504.0)])
        over = sorted((v['box'][2], v['box'][5], v['floor'], v['source']) for v in s['volumes'] if v['over'])
        self.assertEqual(over, [(0.0, 210.0, 1, 'A'), (210.0, 500.0, 2, 'B'), (500.0, 768.0, 3, 'B')])

    def test_a_footprint_across_two_local_volumes_is_cut_at_their_edge(self):
        # (the police station's cursor volumes are fitted to its parts) two volumes side by side breaking at
        # different heights: the room over both gets the floors of each on its own side; at 300 the west break (256)
        # is taken, the east one (192) is too far and a floor is added over it
        local = [dict(key='W1', floor=1, box=[-500.0, -500.0, 0.0, 192.0, 500.0, 256.0]),
                 dict(key='W2', floor=2, box=[-500.0, -500.0, 256.0, 192.0, 500.0, 512.0]),
                 dict(key='E1', floor=1, box=[192.0, -500.0, 0.0, 900.0, 500.0, 192.0]),
                 dict(key='E2', floor=2, box=[192.0, -500.0, 192.0, 900.0, 500.0, 512.0])]
        s = made_cursors.split(local, [slab(304.0)])
        west = sorted((v['box'][2], v['box'][5], v['floor']) for v in s['volumes'] if v['over'] and v['box'][3] <= 192.0)
        east = sorted((v['box'][2], v['box'][5], v['floor']) for v in s['volumes'] if v['over'] and v['box'][0] >= 192.0)
        self.assertEqual(west, [(0.0, 300.0, 1), (300.0, 512.0, 2)])
        self.assertEqual(east, [(0.0, 192.0, 1), (192.0, 300.0, 2), (300.0, 512.0, 3)])
        # the same floors on both sides make one volume each across the edge
        s = made_cursors.split(local, [slab(228.0)])
        self.assertEqual(sorted((v['box'][0], v['box'][3], v['box'][2], v['box'][5]) for v in s['volumes'] if v['over']),
                         [(0.0, 384.0, 0.0, 224.0), (0.0, 384.0, 224.0, 512.0)])

    def test_a_cell_with_no_volume_takes_the_grids_floors(self):
        s = made_cursors.split([], [slab(194.0)], grid=[-1000.0, -1000.0, 0.0, 1000.0, 1000.0, 768.0])
        self.assertEqual(sorted((v['box'][2], v['box'][5], v['floor'], v['source']) for v in s['volumes']),
                         [(0.0, 190.0, 1, None), (190.0, 768.0, 2, None)])
        self.assertEqual(made_cursors.split([], [slab(194.0)]), dict(hidden=[], volumes=[], crossed=[]))

    def test_a_stair_volume_under_a_footprint_is_reported_and_left(self):
        stair = dict(key='S', floor=2, box=[100.0, 100.0, 0.0, 200.0, 200.0, 220.0], stair=True)
        s = made_cursors.split(BAR + [stair], [slab(194.0, label='Floor')])
        self.assertEqual(s['crossed'], [dict(slab='Floor', volume='S', why='stair')])
        self.assertNotIn('S', s['hidden'])
        self.assertFalse(any(v['source'] == 'S' for v in s['volumes']))

    def test_storeys_are_the_volumes_kept_and_made(self):
        st = made_cursors.storeys(BAR, [slab(194.0)])
        self.assertEqual(len(st), 4 * 4 + 4)
        inside = sorted((b[2], f) for f, b in st if b[0] <= 192.0 <= b[3] and b[1] <= 144.0 <= b[4])
        self.assertEqual(inside, [(0.0, 1), (190.0, 2), (402.0, 3), (594.0, 4)])


class BuildingAreas(unittest.TestCase):
    """A building whose floors are the cursor's (the building cursor floors plan): its floor boxes make the cursor's
    floors over its footprint. The cases web/floors.js passes too (building_cursor_cases.json, shared_cases_test.mjs)."""

    @staticmethod
    def cases():
        return json.loads((HERE / 'building_cursor_cases.json').read_text(encoding='utf-8'))['cases']

    def test_the_cases(self):
        cases = self.cases()
        self.assertGreaterEqual(len(cases), 9)
        for c in cases:
            vols = [dict(v, key=k) for k, v in enumerate(c['volumes'])]
            got = sorted([f, [float(round(x, 3)) for x in b]] for f, b in made_cursors.storeys(vols, c['slabs'], c['grid'], c['areas']))
            self.assertEqual(got, c['storeys'], c['case'])
            s = made_cursors.split(vols, c['slabs'], c['grid'], c['areas'])
            self.assertEqual(sorted([v['building'], v['floor'], [float(round(x, 3)) for x in v['box']]]
                                    for v in s['volumes'] if 'building' in v), c['buildingVolumes'], c['case'])
            self.assertEqual(s['crossed'], c['crossed'], c['case'])
            self.assertEqual([made_cursors.unordered(a) for a in c['areas']], c['unordered'], c['case'])

    def test_the_boat_has_four_floors_each_starting_under_its_box(self):
        # the report of 23 November 2026: the hold (-106), the deck (278), the cabin (470) and its roof (598)
        boat = self.cases()[0]
        vols = [dict(v, key=k) for k, v in enumerate(boat['volumes'])]
        cabin = [(b[2], b[5], f) for f, b in made_cursors.storeys(vols, [], None, boat['areas'])
                 if b[0] <= -4100 <= b[3] and b[1] <= 2000 <= b[4]]
        self.assertEqual(sorted(cabin), [(-108.0, 276.0, 1), (276.0, 468.0, 2), (468.0, 596.0, 3), (596.0, 768.0, 4)])
        deck = sorted((b[2], b[5], f) for f, b in made_cursors.storeys(vols, [], None, boat['areas'])
                      if b[0] <= -2500 <= b[3] and b[1] <= 2000 <= b[4])
        self.assertEqual(deck, [(-108.0, 276.0, 1), (276.0, 470.0, 2)])
        # off the boat, the map's even storeys
        off = sorted((b[2], f) for f, b in made_cursors.storeys(vols, [], None, boat['areas']) if b[0] <= 0 <= b[3] and b[1] <= 0 <= b[4])
        self.assertEqual(off, [(-192.0, 1), (0.0, 2), (192.0, 3), (384.0, 4), (576.0, 5), (768.0, 6)])

    def test_nothing_overlaps_and_the_map_outside_is_as_it_was(self):
        for c in self.cases():
            vols = [dict(v, key=k) for k, v in enumerate(c['volumes'])]
            boxes = [b for _, b in made_cursors.storeys(vols, c['slabs'], c['grid'], c['areas'])]
            for n, a in enumerate(boxes):
                for b in boxes[n + 1:]:
                    self.assertFalse(all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > 1e-6 for k in range(3)), (c['case'], a, b))
        # a made slab half inside a building keeps its own break outside it: 2 under its underside, taking the bar's
        # break at 210 (within half a storey), as it would with no building
        c = next(c for c in self.cases() if 'half inside' in c['case'])
        vols = [dict(v, key=k) for k, v in enumerate(c['volumes'])]
        outside = sorted((b[2], f) for f, b in made_cursors.storeys(vols, c['slabs'], c['grid'], c['areas'])
                         if b[0] <= 480 <= b[3] and b[1] <= 144 <= b[4])
        self.assertEqual(outside, [(0.0, 1), (300.0, 2), (402.0, 3), (594.0, 4)])
        alone = sorted((b[2], f) for f, b in made_cursors.storeys(vols, c['slabs'], c['grid'])
                       if b[0] <= 480 <= b[3] and b[1] <= 144 <= b[4])
        self.assertEqual(outside, alone)

    def test_no_area_changes_nothing(self):
        self.assertEqual(made_cursors.split(BAR, [], areas=[]), dict(hidden=[], volumes=[], crossed=[]))
        self.assertEqual(made_cursors.split(BAR, [slab(194.0)], areas=None), made_cursors.split(BAR, [slab(194.0)]))


class SlabTiles(unittest.TestCase):
    """Which tiles a made slab is floor on, those it covers in part, and a turned one's steps (F-147, EXP-90 checks 2
    and 5): the cases web/floors.js passes too (slab_tiles_cases.json, shared_cases_test.mjs)."""

    @staticmethod
    def solids(case, holes=True):
        return [dict(outline=made_cursors.outline(s['location'], s['rotation'], s['slab']),
                     holes=[made_cursors.outline(s['location'], s['rotation'], h) for h in s['slab']['holes']] if holes else [])
                for s in case['solids']]

    def test_the_cases(self):
        cases = json.loads((HERE / 'slab_tiles_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(cases), 7)
        for c in cases:
            got = made_cursors.tiles(self.solids(c), c['corner'])
            self.assertEqual(got, dict(floor=c['floor'], part=c['part']), c['case'])
            self.assertEqual(made_cursors.steps(self.solids(c, holes=False), c['z'][0], c['z'][1], c['corner']), c['steps'],
                             c['case'])

    def test_exp90_s_readings(self):
        # B (check 2): floor where a soldier stood, (-1681, -1009), none on the 29% and 24% tiles the cursor read the
        # ground on; E (check 5): floor where the cursor read its top, none at the box's corners off it
        cases = json.loads((HERE / 'slab_tiles_cases.json').read_text(encoding='utf-8'))['cases']
        at = lambda t: [-2785.0 + 96 * t[0] + 48, -1921.0 + 96 * t[1] + 48]  # noqa: E731
        b = made_cursors.tiles(self.solids(next(c for c in cases if 'floor B' in c['case'])), [-2785.0, -1921.0])
        self.assertIn([-1681.0, -1009.0], [at(t) for t in b['floor']])
        self.assertEqual({tuple(at(t)): t[2] for t in b['part']}[(-1681.0, -913.0)], 0.289)
        self.assertEqual({tuple(at(t)): t[2] for t in b['part']}[(-1585.0, -1009.0)], 0.242)
        e = next(c for c in cases if 'floor E' in c['case'])
        t = made_cursors.tiles(self.solids(e), e['corner'])
        self.assertTrue({(-337.0, -1297.0), (-433.0, -1297.0)} <= {tuple(at(x)) for x in t['floor']})
        self.assertTrue({(-433.0, -1393.0), (-145.0, -1201.0), (-433.0, -1201.0)} <= {tuple(at(x)[:2]) for x in t['part']})

    def test_the_steps_stay_over_the_turned_slab(self):
        # E's twelve steps cover it all and only the parts of the tiles it reaches: 13,587 of the box round it beside
        # it against 38,507
        e = [c for c in json.loads((HERE / 'slab_tiles_cases.json').read_text(encoding='utf-8'))['cases'] if 'turned 20' in c['case']][0]
        boxes = made_cursors.steps(self.solids(e, holes=False), 192.0, 194.0, e['corner'])
        self.assertEqual(len(boxes), 12)
        self.assertLess(sum(area(b) for b in boxes) - 288 * 192, 14000)
        for b in boxes:
            for other in boxes:
                if b is not other:
                    self.assertFalse(min(b[3], other[3]) - max(b[0], other[0]) > 1e-6 and min(b[4], other[4]) - max(b[1], other[1]) > 1e-6)
        s = made_cursors.split(BAR, [dict(box=b, label='E') for b in boxes])
        self.assertTrue(all(v['box'][2] in (0.0, 190.0, 402.0, 594.0) for v in s['volumes'] if v['over']))

    def test_turned_is_yaw_alone(self):
        self.assertTrue(made_cursors.turned([0, 3641, 0]))
        self.assertFalse(made_cursors.turned([0, 16384, 0]))
        self.assertFalse(made_cursors.turned([0, -32768, 0]))
        self.assertFalse(made_cursors.turned([2048, 3000, 0]))       # (pitched: the compiler's made-tilted)


class BuildSlabs(unittest.TestCase):
    """The Build's made slabs for the cursor floors (build_slabs): an unturned slab's box as the Build made it, as
    before; a turned one's steps from its copy's pose and numbers, on the map's tile grid."""

    def test_unturned_box_and_turned_steps(self):
        from unittest import mock
        import native_copy
        records = [dict(kind='fracSlab', label='B', box=[-1840.25, -1609.75, -1103.5, -933.25, 192.0, 194.0]),
                   dict(kind='fracWall', label='A', box=[0, 1, 0, 1, 0, 1]),
                   dict(kind='fracSlab', label='E', box=[-466.17, -129.87, -1440.25, -1161.325, 192.0, 194.0])]
        copies = [dict(label='B', location=[-1840.25, -1103.5, 0.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracSlab', slab=dict(free=1, x0=0.0, x1=230.5, y0=0.0, y1=170.25))),
                  dict(label='E', location=[-400.5, -1440.25, 0.0], rotation=[0, 3641, 0],
                       generated=dict(kind='fracSlab', slab=dict(free=1, x0=0.0, x1=288.0, y0=0.0, y1=192.0)))]
        with mock.patch.object(native_copy, 'level_grid', return_value=dict(tx=-2785.0, ty=-1921.0)) as grid:
            got = made_cursors.build_slabs(object(), records, copies)
        grid.assert_called_once()
        self.assertEqual(got[0], dict(box=[-1840.25, -1103.5, 192.0, -1609.75, -933.25, 194.0], label='B'))
        e = [dict(outline=made_cursors.outline(copies[1]['location'], copies[1]['rotation'], copies[1]['generated']['slab']), holes=[])]
        self.assertEqual(got[1:], [dict(box=b, label='E') for b in made_cursors.steps(e, 192.0, 194.0, (-2785.0, -1921.0))])
        # no turned slab: the grid is never read
        with mock.patch.object(native_copy, 'level_grid') as grid:
            self.assertEqual(len(made_cursors.build_slabs(object(), records[:2], copies)), 1)
        grid.assert_not_called()


class Rectangles(unittest.TestCase):
    def test_a_ring_of_cells_is_four_rectangles(self):
        xs = ys = [0.0, 1.0, 2.0, 3.0]
        out = made_cursors.rectangles(xs, ys, lambda i, j: None if (i, j) == (1, 1) else 'v')
        self.assertEqual(len(out), 4)
        self.assertEqual(sum((r[2] - r[0]) * (r[3] - r[1]) for _, r in out), 8.0)


@unittest.skipUnless(shutil.which('node'), 'node is not on the PATH')
class Twin(unittest.TestCase):
    """web/floors.js madeStoreys gives the same floors as made_cursors.storeys on the same cases."""

    def test_the_page_splits_as_the_build_does(self):
        cases = [dict(volumes=BAR, slabs=[slab(194.0), slab(386.0)], grid=None),
                 dict(volumes=BAR, slabs=[slab(194.0), slab(386.0, foot=[192.0, 96.0, 768.0, 480.0])], grid=None),
                 dict(volumes=[], slabs=[slab(194.0)], grid=[-1000.0, -1000.0, 0.0, 1000.0, 1000.0, 768.0]),
                 dict(volumes=BAR, slabs=[slab(214.0), slab(60.0)], grid=None),
                 dict(volumes=BAR, slabs=[slab(210.0, thick=32.0)], grid=None),
                 # (a turned slab's steps, EXP-90's E: twelve boxes)
                 dict(volumes=BAR, slabs=[dict(box=b, label='E') for b in made_cursors.steps(
                     [dict(outline=made_cursors.outline([-400.5, -1440.25, 0.0], [0, 3641, 0],
                                                        dict(x0=0.0, x1=288.0, y0=0.0, y1=192.0)), holes=[])],
                     192.0, 194.0, (-2785.0, -1921.0))], grid=None)]
        script = ("import('%s').then(m => { const cases = JSON.parse(process.argv[1]);"
                  " console.log(JSON.stringify(cases.map(c => m.madeStoreys("
                  "c.volumes.map(v => ({ floor: v.floor, box: v.box, made: false })), c.slabs, c.grid)"
                  ".map(s => [s.floor, s.box])))); })") % (TOOLS / 'viewer' / 'web' / 'floors.js').as_uri()
        got = json.loads(subprocess.run(['node', '-e', script, json.dumps(cases)], capture_output=True, text=True,
                                        check=True).stdout)
        for case, page in zip(cases, got):
            want = [[f, [float(round(x, 3)) for x in b]] for f, b in
                    made_cursors.storeys([dict(v, key=k) for k, v in enumerate(case['volumes'])], case['slabs'], case['grid'])]
            self.assertEqual(sorted(json.dumps(x) for x in want),
                             sorted(json.dumps([f, [float(round(x, 3)) for x in b]]) for f, b in page))


if __name__ == '__main__':
    unittest.main()
