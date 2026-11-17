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
                     '{"x0": 0, "x1": NaN}'):
            with self.assertRaises(generated.GeneratedError, msg=text):
                generated.Meshes().fracwall(text)

    def test_the_numbers_are_kept_in_one_spelling(self):
        self.assertEqual(generated.wall_numbers(json.dumps(dict(x1=96, x0=0))),
                         dict(x0=0.0, x1=96.0, openings=[], seed=1))


if __name__ == '__main__':
    unittest.main()
