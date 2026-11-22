"""A map's baked tile data written anew for a grid of another size (world_grid.py; prefab plan 5.11, clear-map plan 7.5).

The checks of the game's maps read the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED
names) and skip without it."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
import world_grid  # noqa: E402
import world_links  # noqa: E402
from package import Package  # noqa: E402

BLANK, NO_BLANK = labpaths.install_map('CB2_MP_Blank')
BAR, NO_BAR = labpaths.install_map('URB_Bar')
CORNER = [-2113, -1345, -1]     # the game's corner of the blank map's grid (WorldBounds'), a unit under its level volume's


class FlatFloor(unittest.TestCase):
    def links(self, raw):
        v, _ = world_links.parse_element('floor', raw + b'\0', 0)
        return v

    def test_an_inner_tile_links_to_the_eight_around_it_in_the_bakes_order(self):
        v = self.links(world_grid.flat_floor(10, 10, (36, 36, 12), CORNER, 1152))
        self.assertEqual([l['to'] for l in v['links']],
                         [(9, 10, 0), (11, 10, 0), (10, 9, 0), (10, 11, 0), (9, 11, 0), (11, 11, 0), (11, 9, 0), (9, 9, 0)])
        self.assertEqual([round(l['cost'], 3) for l in v['links']], [1.0] * 4 + [1.414] * 4)
        self.assertEqual((v['loc'], v['ramp'], v['actor'], v['volume']), ((-1105.0, -337.0, 0.0), 0, 1152, 0))

    def test_a_corner_tile_links_only_into_the_grid(self):
        v = self.links(world_grid.flat_floor(0, 0, (36, 36, 12), CORNER, 7))
        self.assertEqual([l['to'] for l in v['links']], [(1, 0, 0), (0, 1, 0), (1, 1, 0)])

    def test_an_absent_tiles_element_is_as_long_as_an_empty_floor(self):
        self.assertEqual(len(world_grid.flat_floor(0, 0, (1, 1, 2), CORNER, 0)), world_grid.SIZES['floor'])


class Place(unittest.TestCase):
    def test_the_five_places_across_a_grid(self):
        self.assertEqual([world_grid.place(v, 36) for v in (0, 1, 2, 17, 33, 34, 35)], [0, 1, 2, 2, 2, 3, 4])


class CutLinks(unittest.TestCase):
    def test_a_flat_floor_cut_to_a_smaller_grid_is_that_grids_flat_floor(self):
        for x, y in ((29, 10), (10, 29), (29, 29), (28, 3), (28, 28)):
            raw = world_grid.flat_floor(x, y, (54, 54, 12), CORNER, 1152)
            self.assertEqual(world_grid.cut_links(raw, (30, 30, 12)), world_grid.flat_floor(x, y, (30, 30, 12), CORNER, 1152))
        raw = world_grid.flat_floor(29, 29, (54, 54, 12), CORNER, 7)
        cut = world_grid.cut_links(raw, (30, 30, 12))
        self.assertEqual(len(world_links.parse_element('floor', cut, 0)[0]['links']), 3)
        self.assertEqual(len(raw) - len(cut), 5 * 28)        # a plain link is 28 bytes
        self.assertEqual(world_grid.floor_actor(cut), 7)

    def test_a_link_up_or_to_another_level_is_cut_by_the_grids_height(self):
        link = lambda to: struct.pack('<iiifi', *to, 1.0, 0) + bytes(8)      # noqa: E731
        raw = bytes(24) + struct.pack('<I', 2) + link((1, 0, 0)) + link((0, 0, 6)) + b'\0' + struct.pack('<ii', 3, 0)
        cut = world_grid.cut_links(raw, (2, 2, 6))
        self.assertEqual([l['to'] for l in world_links.parse_element('floor', cut, 0)[0]['links']], [(1, 0, 0)])
        self.assertIs(world_grid.cut_links(raw, (2, 2, 7)), raw)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class RoundTrip(unittest.TestCase):
    def test_a_map_with_an_uneven_grid_and_out_of_turn_chunk_lists_is_written_back_the_same(self):
        _, blob = world_grid.container_of(Package(BAR))      # 52 by 39: a part chunk on its x edge
        self.assertEqual(world_grid.encode(world_grid.decode(blob)), blob)

    def test_cut_by_a_few_tiles_and_two_levels(self):
        """URB_Bar (52 by 39 by 12) made 48 by 35 by 10 (clear-map plan, section 7 step 5): every store parses with its
        counts, every link it keeps is the map's and points inside, and it is written back the same."""
        _, blob = world_grid.container_of(Package(BAR))
        model = world_grid.decode(blob)
        small = world_grid.encode(world_grid.resize(model, 48, 35, None, None, 10))
        wd = world_links.parse_container(small)
        world_links.self_check(small, wd)
        self.assertEqual(tuple(wd['dims']), (48, 35, 10))
        self.assertEqual(world_grid.encode(world_grid.decode(small)), small)
        inside = lambda t: all(0 <= t[k] < (48, 35, 10)[k] for k in range(3))      # noqa: E731
        key = lambda l: (l['from'], l['to'], l['cost'], l['obj'], tuple(l['types']), tuple(l['pos']))      # noqa: E731
        kept = sorted(key(l) for l in world_links.all_links(world_links.parse_container(blob))
                      if inside(l['from']) and inside(l['to']))
        self.assertEqual(sorted(key(l) for l in world_links.all_links(wd)), kept)
        # every kept tile of every store is the map's, but the flags of the new far edges; a part chunk's tiles past
        # the grid are absent and zero, as the game writes them (URB_Bar's at x 52 and 53)
        again = world_grid.decode(small)
        for k, store in enumerate(again['stores']):
            past = {t: v for t, v in store.items() if not inside(t)}
            self.assertTrue(all(v == (bytes(len(v[0])), 0) for v in past.values()), k)
            store = {t: v for t, v in store.items() if inside(t)}
            self.assertEqual(set(store), {t for t in model['stores'][k] if inside(t)}, k)
            if k == 0:
                self.assertTrue(all(t[0] >= 46 or t[1] >= 33 for t, v in store.items() if v != model['stores'][0][t]))
            elif k != world_grid.FLOOR_STORE:
                self.assertTrue(all(v == model['stores'][k][t] for t, v in store.items()), k)


@unittest.skipUnless(BLANK and BLANK.exists(), NO_BLANK)
class BlankMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.blob = world_grid.container_of(Package(BLANK))
        cls.model = world_grid.decode(cls.blob)

    def test_written_back_the_same(self):
        self.assertEqual(world_grid.encode(self.model), self.blob)

    def test_the_bare_ground_rules_give_its_own_tiles_back_but_about_its_pieces(self):
        r = world_grid.check_bare(self.model, CORNER)
        self.assertEqual(r['flags'][0], 36 * 36 * 12)
        self.assertEqual(r['floor'][0], 36 * 36)
        # the wall, the van, the pickup and two edge tiles: 121 columns of tiles in all
        self.assertLess(len({(x, y) for x, y, z in r['odd']}), 130)
        self.assertGreater(r['flags'][1] / r['flags'][0], 0.97)

    def test_grown_to_the_same_size_nothing_changes(self):
        same = world_grid.grow(self.model, 36, 36, CORNER, lambda x, y: 0)
        self.assertEqual(same['stores'], self.model['stores'])

    def test_a_smaller_grid_is_refused(self):
        with self.assertRaises(ValueError):
            world_grid.grow(self.model, 30, 36, CORNER, lambda x, y: 0)
        with self.assertRaises(ValueError):
            world_grid.grow(self.model, 36, 36, CORNER, lambda x, y: 0, 11)

    def test_grown_taller(self):
        """18 levels (prefab plan 5.6b): upward only, so every tile of every store keeps its index and its data, and
        the new levels are open air as the map's top level is."""
        grown = world_grid.decode(world_grid.encode(world_grid.grow(self.model, 36, 36, CORNER, None, 18)))
        self.assertEqual(grown['dims'], (36, 36, 18))
        for k, store in enumerate(self.model['stores']):
            self.assertTrue(all(grown['stores'][k].get(t) == v for t, v in store.items()), k)
        top = {(x, y): raw for (x, y, z), (raw, present) in self.model['stores'][0].items() if z == 11 and present}
        new = [(t, v) for t, v in grown['stores'][0].items() if t[2] >= 12]
        self.assertEqual(len(new), 36 * 36 * 6)
        self.assertTrue(all(present for _, (raw, present) in new))
        # the new levels take the top level's commonest flags for each place across the grid
        self.assertEqual(grown['stores'][0][(18, 18, 17)][0], top[(18, 18)])
        self.assertTrue(all(len(grown['stores'][k]) == len(s) for k, s in enumerate(self.model['stores']) if k))

    def test_grown(self):
        grown = world_grid.grow(self.model, 54, 45, CORNER, lambda x, y: 900 + x // 9)
        blob = world_grid.encode(grown)
        wd = world_links.parse_container(blob)      # every store's lists, headers and counts are checked there
        self.assertEqual(tuple(wd['dims']), (54, 45, 12))
        self.assertEqual(len(wd['floor']), 54 * 45)
        self.assertEqual(wd['floor'][(53, 44, 0)]['value']['actor'], 905)
        # a tile of the map's own keeps its floor piece, and one of its old far edge now links past it
        old = world_links.parse_container(self.blob)['floor']
        self.assertEqual(wd['floor'][(10, 10, 0)]['value']['actor'], old[(10, 10, 0)]['value']['actor'])
        self.assertEqual(len(wd['floor'][(35, 10, 0)]['value']['links']), 8)
        self.assertEqual(len(old[(35, 10, 0)]['value']['links']), 5)
        # every tile is present in the flag store, and the new ground reads as bare ground by the same rules
        again = world_grid.decode(blob)
        self.assertTrue(all(present for _, present in again['stores'][0].values()))
        r = world_grid.check_bare(again, CORNER)
        before = world_grid.check_bare(self.model, CORNER)
        self.assertEqual({(x, y) for x, y, z in r['odd']}, {(x, y) for x, y, z in before['odd']})
        # the cover stores are the map's own
        self.assertEqual(sum(p for _, p in again['stores'][1].values()), sum(p for _, p in self.model['stores'][1].values()))

    def test_resized_larger_on_every_axis_is_grown(self):
        floor = lambda x, y: 900 + x // 9      # noqa: E731
        self.assertEqual(world_grid.encode(world_grid.resize(self.model, 54, 45, CORNER, floor, 18)),
                         world_grid.encode(world_grid.grow(self.model, 54, 45, CORNER, floor, 18)))
        same = world_grid.resize(self.model, 36, 36, CORNER, None)
        self.assertEqual(world_grid.encode(same), self.blob)

    def grown_and_back(self, floor, nz):
        grown = world_grid.decode(world_grid.encode(world_grid.grow(self.model, 54, 54, CORNER, floor, nz)))
        return world_grid.encode(world_grid.resize(grown, 36, 36, CORNER, None, 12))

    def test_grown_with_ground_and_resized_back_is_its_own_container(self):
        """54 by 54 (and 18 levels) and back: byte for byte the map's container as encode() writes it with its chunk
        lists in turn. The map's own lists of the two cover stores have two entries out of turn, which grow() cannot
        keep (it numbers the chunks anew); that order is the only difference from the map's bytes."""
        mine = world_grid.encode(dict(self.model, orders=None))
        self.assertNotEqual(mine, self.blob)
        for nz in (None, 18):
            back = self.grown_and_back(lambda x, y: 900 + x // 9, nz)
            self.assertEqual(back, mine, nz)
            again = world_grid.decode(back)
            self.assertEqual(again['stores'], self.model['stores'])
            self.assertEqual([sorted(o) for o in again['orders']], [sorted(o) for o in self.model['orders']])

    def test_grown_without_ground_and_resized_back_loses_only_the_far_edges_ground_flags(self):
        """With no ground laid the new ground is open air with the seed bit, the commonest ground of the grown grid,
        and the edge ground's flags are nowhere in it: the ground tiles of the two far edges (and the two next to
        the far y edge at x 0 and 1, whose near-edge rule changes too) come back other than the map's. Everything
        else is the map's."""
        for nz in (None, 18):
            again = world_grid.decode(self.grown_and_back(None, nz))
            for k, store in enumerate(again['stores']):
                odd = {t for t, v in store.items() if v != self.model['stores'][k].get(t)}
                self.assertEqual(set(store), set(self.model['stores'][k]), k)
                if k:
                    self.assertEqual(odd, set(), k)
                else:
                    self.assertTrue(odd and all(z == 0 and (x >= 34 or y >= 34) for x, y, z in odd), sorted(odd)[:5])
                    self.assertLess(len(odd), 80)

    def test_resized_smaller(self):
        """30 by 28 by 9: every link inside, a ground floor by rule on the new edges is the flat floor of the new grid,
        the new far edges take the edge's flags, and the cover stores lose the tiles past the edges only."""
        small = world_grid.resize(self.model, 30, 28, CORNER, None, 9)
        blob = world_grid.encode(small)
        wd = world_links.parse_container(blob)
        self.assertEqual(tuple(wd['dims']), (30, 28, 9))
        self.assertEqual(sum(p for _, p in world_grid.decode(blob)['stores'][0].values()), 30 * 28 * 9)
        self.assertTrue(all(all(0 <= l['to'][k] < (30, 28, 9)[k] for k in range(3)) for l in world_links.all_links(wd)))
        rule = world_grid.bare_flags(self.model)
        flags = small['stores'][0]
        self.assertEqual(flags[(29, 10, 0)][0], rule[(4, 2, 0)])
        self.assertEqual(flags[(10, 27, 0)][0], rule[(2, 4, 0)])
        self.assertEqual(flags[(29, 27, 5)][0], rule[(4, 4, 5)])
        self.assertEqual(flags[(10, 10, 8)], self.model['stores'][0][(10, 10, 8)])
        before = world_links.parse_container(self.blob)['floor']
        flat = 0
        for (x, y, z), t in wd['floor'].items():
            old = self.model['stores'][world_grid.FLOOR_STORE][(x, y, z)][0]
            if z == 0 and old == world_grid.flat_floor(x, y, (36, 36, 12), CORNER, world_grid.floor_actor(old)):
                flat += 1
                self.assertEqual(small['stores'][world_grid.FLOOR_STORE][(x, y, z)][0],
                                 world_grid.flat_floor(x, y, (30, 28, 9), CORNER, world_grid.floor_actor(old)))
            self.assertEqual(t['value']['actor'], before[(x, y, z)]['value']['actor'])
        self.assertGreater(flat, 700)
        self.assertEqual(len(wd['floor'][(29, 10, 0)]['value']['links']), 5)

    def test_larger_on_one_axis_smaller_on_another(self):
        mixed = world_grid.encode(world_grid.resize(self.model, 45, 30, CORNER, None, 10))
        wd = world_links.parse_container(mixed)
        self.assertEqual(tuple(wd['dims']), (45, 30, 10))
        self.assertTrue(all(all(0 <= l['to'][k] < (45, 30, 10)[k] for k in range(3)) for l in world_links.all_links(wd)))
        # the cut is made first, then the grid grown: grow() of the cut model
        cut = world_grid.shrink(self.model, 36, 30, 10)
        self.assertEqual(mixed, world_grid.encode(world_grid.grow(cut, 45, 30, CORNER, None, 10)))
        self.assertEqual(world_grid.decode(mixed)['stores'][0][(44, 29, 0)][0][:4],
                         (struct.unpack('<I', world_grid.bare_flags(cut)[(4, 4, 1)])[0] | world_grid.SEED).to_bytes(4, 'little'))

    def test_shrink_refuses_a_larger_grid(self):
        with self.assertRaises(ValueError):
            world_grid.shrink(self.model, 37, 36)
        with self.assertRaises(ValueError):
            world_grid.resize(self.model, 0, 36, CORNER, None)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Forget(unittest.TestCase):
    """(F-156) No tile names an actor a Build took out of the level: a floor piece or floor volume becomes none, a
    link through a path object or an interact point of an actor is dropped; nothing else changes."""

    @classmethod
    def setUpClass(cls):
        _, cls.blob = world_grid.container_of(Package(BAR))

    def model(self):
        return world_grid.decode(self.blob)

    def floors(self, model):
        return {t: world_links.parse_element('floor', raw, 0)[0]
                for t, (raw, present) in model['stores'][world_grid.FLOOR_STORE].items() if present}

    def test_the_elements_encode_back_to_their_bytes(self):
        model = self.model()
        for t, (raw, present) in model['stores'][world_grid.FLOOR_STORE].items():
            if present:
                self.assertEqual(world_links.encode_floor(world_links.parse_element('floor', raw, 0)[0]), raw, t)
        for t, (raw, present) in model['stores'][world_grid.INTERACT_STORE].items():
            if present:
                self.assertEqual(world_links.encode_interact(world_links.parse_element('interact', raw, 0)[0]), raw, t)

    def test_nothing_gone_changes_nothing(self):
        model = self.model()
        self.assertEqual(world_grid.forget(model, set()), dict(floorActor=0, floorVolume=0, links=0, interactPoints=0))
        self.assertEqual(world_grid.encode(model), self.blob)

    def test_a_floor_piece_and_a_floor_volume_become_none(self):
        before = self.floors(self.model())
        actor = max({r['actor'] for r in before.values()} - {0},
                    key=lambda a: sum(r['actor'] == a for r in before.values()))
        volume = next(r['volume'] for r in before.values() if r['volume'])
        model = self.model()
        got = world_grid.forget(model, {actor, volume})
        after = self.floors(model)
        self.assertEqual(got['floorActor'], sum(r['actor'] == actor for r in before.values()))
        self.assertEqual(got['floorVolume'], sum(r['volume'] == volume for r in before.values()))
        self.assertGreater(got['floorActor'], 0)
        for t, r in before.items():
            want = dict(r, actor=0 if r['actor'] == actor else r['actor'], volume=0 if r['volume'] == volume else r['volume'])
            self.assertEqual({k: after[t][k] for k in ('actor', 'volume', 'loc', 'ramp')},
                             {k: want[k] for k in ('actor', 'volume', 'loc', 'ramp')})
            self.assertEqual(len(after[t]['links']), len(r['links']))
        world_links.parse_container(world_grid.encode(model))         # every store still parses

    def test_a_link_through_a_path_object_and_its_actors_interact_points_are_dropped(self):
        before = self.floors(self.model())
        obj = next(l['obj'] for r in before.values() for l in r['links'] if l['obj'])
        points = {t: world_links.parse_element('interact', raw, 0)[0]
                  for t, (raw, present) in self.model()['stores'][world_grid.INTERACT_STORE].items() if present}
        actor = next(pt['actor'] for pts in points.values() for pt in pts)
        model = self.model()
        got = world_grid.forget(model, {obj, actor})
        # (a door's interact points' actor is the path object of the links through it too)
        self.assertEqual(got['links'], sum(l['obj'] in (obj, actor) for r in before.values() for l in r['links']))
        self.assertEqual(got['interactPoints'], sum(pt['actor'] == actor for pts in points.values() for pt in pts))
        wd = world_links.parse_container(world_grid.encode(model))
        self.assertFalse([l for t in wd['floor'].values() for l in t['value']['links'] if l['obj'] in (obj, actor)])
        for c in wd['stores'][world_grid.INTERACT_STORE]['chunks']:
            for t in c['tiles']:
                self.assertFalse([pt for pt in t['value'] if pt['actor'] == actor])
                if t['tile'] in points:
                    # a tile left with no point saves none, as the bake's do
                    left = [pt for pt in points[t['tile']] if pt['actor'] != actor]
                    self.assertEqual((t['present'], len(t['value'])), (1 if left else 0, len(left)))


if __name__ == '__main__':
    unittest.main()
