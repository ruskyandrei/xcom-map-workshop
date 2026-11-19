"""Pieces the Build makes from numbers, drawn in the editor as the Build makes them (generated.py): a fracturing wall's
mesh file from its numbers, its sections in slot order, its box its solid's; malformed numbers refused; one file for
the same numbers however they are spelt."""
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import generated  # noqa: E402

DOOR = dict(x0=96, x1=192, z0=-16, z1=160)
CUSTOM = dict(x0=0, x1=384, openings=[DOOR], seed=2)


def gltf(payload):
    """The GLB's JSON document, its header checked."""
    magic, version, length = struct.unpack_from('<III', payload, 0)
    size, kind = struct.unpack_from('<I4s', payload, 12)
    assert (magic, version, length, kind) == (0x46546C67, 2, len(payload), b'JSON')
    return json.loads(payload[20:20 + size])


class FracWall(unittest.TestCase):
    def test_the_mesh_has_six_sections_in_slot_order_and_the_walls_solid_for_its_box(self):
        doc = gltf(generated.Meshes().fracwall(json.dumps(CUSTOM)))
        prims = doc['meshes'][0]['primitives']
        self.assertEqual([p['extras']['materialSlot'] for p in prims], list(range(generated.SLOTS)))
        pos = doc['accessors'][prims[0]['attributes']['POSITION']]
        # the page's axes (x, up, y): the solid 8 in from the tile edges, -16 to 384 up, 12 each side of the line
        self.assertEqual(pos['min'], [8.0, -16.0, -12.0])
        self.assertEqual(pos['max'], [376.0, 384.0, 12.0])
        self.assertIn('TEXCOORD_1', prims[0]['attributes'])
        self.assertIn('COLOR_0', prims[0]['attributes'])

    def test_a_slot_with_nothing_in_it_is_drawn_as_a_triangle_of_no_area(self):
        # a doorway over the whole lower storey of a one-tile wall: the lower storey's face slots hold no faces
        wall = dict(x0=0, x1=96, openings=[dict(x0=0, x1=96, z0=-16, z1=200)], seed=1)
        import frac_wall
        lod = frac_wall.build(wall)['mesh']['lods'][0]
        empty = [s['slot'] for s in lod['sections'] if not s['triangles']]
        self.assertTrue(empty)
        doc = gltf(generated.Meshes().fracwall(json.dumps(wall)))
        prims = doc['meshes'][0]['primitives']
        self.assertEqual([p['extras']['materialSlot'] for p in prims], list(range(generated.SLOTS)))
        for slot in empty:
            self.assertEqual(doc['accessors'][prims[slot]['indices']]['count'], 3)

    def test_the_same_numbers_are_one_file_however_they_are_spelt(self):
        meshes = generated.Meshes()
        a = meshes.fracwall(json.dumps(CUSTOM))
        b = meshes.fracwall(json.dumps(dict(seed=2, openings=[{k: float(v) for k, v in DOOR.items()}], x1=384.0, x0=0.0)))
        self.assertIs(a, b)
        self.assertNotEqual(a, meshes.fracwall(json.dumps(dict(CUSTOM, seed=3))))

    def test_the_cache_keeps_the_last_ones(self):
        meshes = generated.Meshes(size=2)
        for seed in (1, 2, 3):
            meshes.fracwall(json.dumps(dict(x0=0, x1=96, seed=seed)))
        self.assertEqual(len(meshes.kept), 2)

    def test_malformed_numbers_are_refused(self):
        for text in ('not json', '[]', json.dumps(dict(x0=0)), json.dumps(dict(x0=0, x1=39)),
                     json.dumps(dict(x0=0, x1=generated.MAX_LENGTH + 1)), json.dumps(dict(x0=0, x1=96, seed=1.5)),
                     json.dumps(dict(x0=0, x1=96, openings=[dict(x0=80, x1=120, z0=0, z1=10)])),
                     json.dumps(dict(x0=0, x1=96, openings=[dict(x0=0, x1=10, z0=0, z1=10)] * (generated.MAX_OPENINGS + 1))),
                     json.dumps(dict(x0=0, x1=96, storeys=13)), json.dumps(dict(x0=0, x1=96, storeys=True)),
                     json.dumps(dict(x0=0, x1=96, ends=['free'])), json.dumps(dict(x0=0, x1=96, ends=['free', 'mitre'])),
                     '{"x0": 0, "x1": NaN}'):
            with self.assertRaises(generated.GeneratedError, msg=text):
                generated.Meshes().fracwall(text)

    def test_the_numbers_are_kept_in_one_spelling(self):
        self.assertEqual(generated.wall_numbers(json.dumps(dict(x1=96, x0=0))),
                         dict(x0=0.0, x1=96.0, openings=[], seed=1))
        # (M2) a wall's storeys: 2 is the donor's and left out, 1 kept
        self.assertEqual(generated.wall_numbers(json.dumps(dict(x0=0, x1=96, storeys=2))),
                         dict(x0=0.0, x1=96.0, openings=[], seed=1))
        self.assertEqual(generated.wall_numbers(json.dumps(dict(x0=0, x1=96, storeys=1)))['storeys'], 1)
        # (M4) its look: the default left out, one not listed refused
        self.assertNotIn('look', generated.wall_numbers(json.dumps(dict(x0=0, x1=96, look='bar-inside'))))
        with self.assertRaises(generated.GeneratedError):
            generated.wall_numbers(json.dumps(dict(x0=0, x1=96, look='marble')))
        # (M3) its end styles: two free ends left out, a joined one kept
        self.assertNotIn('ends', generated.wall_numbers(json.dumps(dict(x0=0, x1=96, ends=['free', 'free']))))
        self.assertEqual(generated.wall_numbers(json.dumps(dict(x0=0, x1=96, ends=['through', 'free'])))['ends'],
                         ['through', 'free'])

    def test_a_one_storey_wall_is_drawn_a_storey_high(self):
        built = generated.frac_wall.build(generated.wall_numbers(json.dumps(dict(x0=0, x1=192, storeys=1))))
        self.assertEqual(max(p[2] for p in built['mesh']['lods'][0]['positions']), 192.0)
        mesh = generated.viewer_mesh(built)
        self.assertEqual(len(mesh['sections']), generated.SLOTS)


class Pieces(unittest.TestCase):
    """(custom geometry editing plan, B4) a wall longer or taller than the game's and a slab larger are drawn as the
    Build makes them, its pieces (made_split) joined into one mesh with the same sections."""

    def box(self, doc):
        prims = doc['meshes'][0]['primitives']
        pos = [doc['accessors'][p['attributes']['POSITION']] for p in prims]
        return [min(a['min'][k] for a in pos) for k in range(3)], [max(a['max'][k] for a in pos) for k in range(3)]

    def test_a_long_tall_wall_is_its_pieces_joined(self):
        import frac_wall
        wall = dict(x0=0, x1=96 * 40, openings=[], seed=2, storeys=4)
        doc = gltf(generated.Meshes().fracwall(json.dumps(wall)))
        prims = doc['meshes'][0]['primitives']
        self.assertEqual([p['extras']['materialSlot'] for p in prims], list(range(generated.SLOTS)))
        # (the page's axes: x, up, y) 8 in from its ends, -16 to the top of two two-storey pieces stacked (784)
        lo, hi = self.box(doc)
        self.assertEqual((lo[0], hi[0], lo[1], hi[1]), (8.0, 3832.0, -16.0, 784.0))
        # as many triangles as its six pieces have
        pieces = generated.made_split.wall_pieces(wall, generated.wall_look_storeys, generated.wall_heights, ends=True)
        self.assertEqual(len(pieces), 6)
        want = sum(s['triangles'] for _, _, n in pieces for s in frac_wall.build(n)['mesh']['lods'][0]['sections'])
        got = sum(doc['accessors'][p['indices']]['count'] for p in prims) // 3
        self.assertGreaterEqual(got, want)
        self.assertLessEqual(got, want + 6 * generated.SLOTS)    # (a slot empty in a piece is a triangle of no area)

    def test_a_large_slab_is_its_pieces_joined(self):
        doc = gltf(generated.Meshes().fracslab(json.dumps(dict(x0=0, x1=96 * 30, y0=0, y1=96 * 20, holes=[], seed=1))))
        lo, hi = self.box(doc)
        self.assertEqual((lo[0], hi[0], lo[2], hi[2]), (0.0, 2880.0, 0.0, 1920.0))


class Broken(unittest.TestCase):
    """(custom geometry editing plan, B5) a made wall or slab built broken is drawn without the fragments its blasts
    knock out (made_blasts); its blasts are part of its file's key; bad blasts are refused."""

    def triangles(self, payload):
        doc = gltf(payload)
        return sum(doc['accessors'][p['indices']]['count'] for p in doc['meshes'][0]['primitives']) // 3

    def test_a_broken_wall_and_slab_are_drawn_without_their_knocked_out_fragments(self):
        meshes = generated.Meshes()
        blasts = json.dumps([dict(at=[192, 12, 100], radius=96)])
        whole, broken = meshes.fracwall(json.dumps(CUSTOM)), meshes.fracwall(json.dumps(CUSTOM), blasts)
        self.assertLess(self.triangles(broken), self.triangles(whole))
        self.assertIs(meshes.fracwall(json.dumps(CUSTOM), blasts), broken)
        self.assertIs(meshes.fracwall(json.dumps(CUSTOM), ''), whole)
        slab = json.dumps(dict(x0=0, x1=384, y0=0, y1=288, holes=[], seed=4))
        self.assertLess(self.triangles(meshes.fracslab(slab, json.dumps([dict(at=[192, 144, 0], radius=96)]))),
                        self.triangles(meshes.fracslab(slab)))
        # a long wall's blast at its second piece breaks that piece, in its frame
        long = json.dumps(dict(x0=0, x1=96 * 40, openings=[], seed=2))
        self.assertLess(self.triangles(meshes.fracwall(long, json.dumps([dict(at=[1700, 0, 100], radius=96)]))),
                        self.triangles(meshes.fracwall(long)))
        for bad in ('x', json.dumps([dict(at=[0, 0], radius=96)]), json.dumps([dict(at=[0, 0, 0], radius=1)])):
            with self.assertRaises(generated.GeneratedError, msg=bad):
                meshes.fracwall(json.dumps(CUSTOM), bad)


class FracSlab(unittest.TestCase):
    """(M5) a floor or roof slab's mesh file from its numbers."""
    SLAB = dict(x0=0, x1=384, y0=0, y1=288, holes=[dict(x0=96, x1=192, y0=96, y1=192)], seed=4)

    def test_the_mesh_has_two_sections_in_slot_order_and_the_slabs_plate_for_its_box(self):
        doc = gltf(generated.Meshes().fracslab(json.dumps(self.SLAB)))
        prims = doc['meshes'][0]['primitives']
        self.assertEqual([p['extras']['materialSlot'] for p in prims], [0, 1])
        pos = doc['accessors'][prims[0]['attributes']['POSITION']]
        # the page's axes (x, up, y): the footprint, the roof's plate -2 to 2
        self.assertEqual(pos['min'], [0.0, -2.0, 0.0])
        self.assertEqual(pos['max'], [384.0, 2.0, 288.0])
        floor = gltf(generated.Meshes().fracslab(json.dumps(dict(self.SLAB, look='floor'))))
        pos = floor['accessors'][floor['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        self.assertEqual((pos['min'][1], pos['max'][1]), (192.0, 194.0))

    def test_the_numbers_are_kept_in_one_spelling_and_bad_ones_refused(self):
        self.assertEqual(generated.slab_numbers(json.dumps(dict(x0=0, x1=96, y0=0, y1=96, look='roof'))),
                         dict(x0=0.0, x1=96.0, y0=0.0, y1=96.0, holes=[], seed=1))
        meshes = generated.Meshes()
        self.assertIs(meshes.fracslab(json.dumps(self.SLAB)),
                      meshes.fracslab(json.dumps(dict(self.SLAB, x1=384.0, look='roof'))))
        for text in ('', '[]', json.dumps(dict(self.SLAB, x1=380)), json.dumps(dict(self.SLAB, look='marble')),
                     json.dumps(dict(self.SLAB, holes=[dict(x0=0, x1=96, y0=0, y1=480)])),
                     json.dumps(dict(self.SLAB, holes=[dict(x0=0, x1=96, y0=0, y1=96)] * (generated.MAX_HOLES + 1))),
                     json.dumps(dict(self.SLAB, x1=96 * 129)),
                     json.dumps(dict(self.SLAB, x0=True)), '{"x0": 0, "x1": NaN, "y0": 0, "y1": 96}'):
            with self.assertRaises(generated.GeneratedError, msg=text):
                generated.Meshes().fracslab(text)


class Ground(unittest.TestCase):
    """(M6) a ground shape's mesh file from its numbers: one section, its box the shape's."""
    def test_a_ramp_is_one_section_its_box_its_wedge(self):
        doc = gltf(generated.Meshes().ground(json.dumps(dict(shape='ramp', x0=0, x1=288, y0=0, y1=96, height=96))))
        prims = doc['meshes'][0]['primitives']
        self.assertEqual([p['extras']['materialSlot'] for p in prims], [0])
        pos = doc['accessors'][prims[0]['attributes']['POSITION']]
        self.assertEqual((pos['min'], pos['max']), ([0.0, 0.0, 0.0], [288.0, 96.0, 96.0]))

    def test_a_rock_keeps_its_seed_and_stands_in_its_footprint(self):
        numbers = dict(shape='rock', x0=0, x1=192, y0=0, y1=96, height=96, seed=5)
        self.assertEqual(generated.ground_numbers(json.dumps(numbers)),
                         dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=96.0, seed=5))
        doc = gltf(generated.Meshes().ground(json.dumps(numbers)))
        pos = doc['accessors'][doc['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        # (the file's axes are the page's: x, up, y)
        (x0, z0, y0), (x1, z1, y1) = pos['min'], pos['max']
        self.assertTrue(x0 >= 0 and y0 >= 0 and z0 == 0, pos['min'])
        self.assertTrue(x1 <= 192 and y1 <= 96 and abs(z1 - 96) < 1e-3, pos['max'])
        with self.assertRaises(generated.GeneratedError):
            generated.Meshes().ground(json.dumps(dict(numbers, seed='x')))

    def test_a_rocks_corners_are_its_meshs_each_with_its_points_index(self):
        # (look picker and rock points plan, R2) the points (the seed's, or moved ones), and which are hull corners: the
        # mesh's corners are those points; a rock with points is drawn from them
        numbers = dict(shape='rock', x0=0, x1=192, y0=0, y1=96, height=96, seed=5)
        answer = generated.Meshes().ground_corners(json.dumps(numbers))
        self.assertEqual(len(answer['points']), 24)
        self.assertTrue(set(answer['corners']) <= set(range(24)) and len(answer['corners']) >= 8, answer['corners'])
        doc = gltf(generated.Meshes().ground(json.dumps(numbers)))
        pos = doc['accessors'][doc['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        corner = lambda p: [p[0], p[2], p[1]]       # (the file's axes: x, up, y)
        tops = {tuple(round(v, 1) for v in answer['points'][i]) for i in answer['corners'] if answer['points'][i][2] > 0}
        self.assertIn(tuple(round(v, 1) for v in corner(pos['max']))[2], {t[2] for t in tops})
        moved = [list(p) for p in answer['points']]
        top = max(range(24), key=lambda i: moved[i][2])
        moved[top] = [20.0, 20.0, 90.0]
        given = dict(numbers, points=moved)
        self.assertEqual(generated.ground_numbers(json.dumps(given))['points'][top], [20.0, 20.0, 90.0])
        again = generated.Meshes().ground_corners(json.dumps(given))
        self.assertEqual(again['points'][top], [20.0, 20.0, 90.0])
        self.assertIn(top, again['corners'])
        doc = gltf(generated.Meshes().ground(json.dumps(given)))
        pos = doc['accessors'][doc['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        self.assertLess(pos['max'][1], 96 - 1)              # (its top now the highest other point, under 96)
        for bad in (dict(numbers, shape='block', height=64), dict(given, points=moved[:-1])):
            with self.assertRaises(generated.GeneratedError):
                generated.Meshes().ground_corners(json.dumps(bad))

    def test_the_numbers_are_kept_in_one_spelling_and_bad_ones_refused(self):
        self.assertEqual(generated.ground_numbers(json.dumps(dict(shape='patch', x0=0, x1=96, y0=0, y1=96, height=5))),
                         dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0))
        for text in ('', '[]', json.dumps(dict(shape='dome', x0=0, x1=96, y0=0, y1=96)),
                     json.dumps(dict(shape='block', x0=0, x1=96, y0=0, y1=96)),
                     json.dumps(dict(shape='block', x0=0, x1=90, y0=0, y1=96, height=10))):
            with self.assertRaises(generated.GeneratedError, msg=text):
                generated.Meshes().ground(text)


class DonorLooks(unittest.TestCase):
    """Looks named by their donor (custom geometry plan, M4): checked and kept in one spelling; one no catalogue holds
    can't be drawn here (the Build measures it)."""

    def test_a_donor_look_is_kept_in_one_spelling(self):
        look = {'mesh': 'Pkg.Meshes.WallB_FRACTURED', 'measure': 1, 'extra': 'dropped'}
        wall = generated.wall_numbers(json.dumps(dict(x0=0, x1=384, look=look)))
        self.assertEqual(wall['look'], {'mesh': 'Pkg.Meshes.WallB_FRACTURED', 'measure': 1})
        for bad in ({'mesh': 'NoDot', 'measure': 1}, {'mesh': 'Pkg.Meshes.WallB', 'measure': 0}, 'marble'):
            with self.assertRaises(generated.GeneratedError):
                generated.wall_numbers(json.dumps(dict(x0=0, x1=384, look=bad)))
        with self.assertRaises(generated.GeneratedError):        # a ground look names its material too
            generated.ground_numbers(json.dumps(dict(shape='patch', x0=0, x1=96, y0=0, y1=96,
                                                     look={'mesh': 'Pkg.Meshes.Plane', 'measure': 1})))

    def test_a_donor_look_no_catalogue_holds_is_not_drawn(self):
        look = {'mesh': 'Nowhere.Meshes.WallZ_FRACTURED', 'measure': 1}
        with self.assertRaises(generated.GeneratedError) as caught:
            generated.Meshes().fracwall(json.dumps(dict(x0=0, x1=384, look=look)))
        self.assertIn('measures it', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
