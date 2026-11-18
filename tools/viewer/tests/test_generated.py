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
                     json.dumps(dict(x0=0, x1=96, openings=[dict(x0=0, x1=10, z0=0, z1=10)] * 17)),
                     json.dumps(dict(x0=0, x1=96, storeys=3)), json.dumps(dict(x0=0, x1=96, storeys=True)),
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
                     json.dumps(dict(self.SLAB, holes=[dict(x0=0, x1=96, y0=0, y1=96)] * 33)),
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

    def test_the_numbers_are_kept_in_one_spelling_and_bad_ones_refused(self):
        self.assertEqual(generated.ground_numbers(json.dumps(dict(shape='patch', x0=0, x1=96, y0=0, y1=96, height=5))),
                         dict(shape='patch', x0=0.0, x1=96.0, y0=0.0, y1=96.0))
        for text in ('', '[]', json.dumps(dict(shape='dome', x0=0, x1=96, y0=0, y1=96)),
                     json.dumps(dict(shape='block', x0=0, x1=96, y0=0, y1=96)),
                     json.dumps(dict(shape='block', x0=0, x1=90, y0=0, y1=96, height=10))):
            with self.assertRaises(generated.GeneratedError, msg=text):
                generated.Meshes().ground(text)


if __name__ == '__main__':
    unittest.main()
