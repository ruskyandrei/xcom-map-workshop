"""Reading a tactical save's static tile store (tools/lab/save_tiles.py), on a made-up save: a header, two compressed
chunks and a store of one chunk of tiles among other data."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import save_tiles  # noqa: E402
import package_edit  # noqa: E402


def store(flags, dims=(3, 3, 2)):
    """A static store of one chunk (3 x 3 x 2 tiles) with the 18 flag words `flags`, as the game saves it."""
    out = struct.pack('<II', 1, 1) + struct.pack('<I', 0) + struct.pack('<3i', *dims)
    out += struct.pack('<IIiiiI', 0, 18, 0, 0, 0, 18)
    return out + b''.join(struct.pack('<IB', f, 1) for f in flags)


def chunk(payload, block=40):
    """A compressed chunk of the game's: the payload in blocks of `block` bytes, each one LZO1X literal run."""
    parts = [payload[i:i + block] for i in range(0, len(payload), block)]
    packed = [package_edit.lzo_literals(part) for part in parts]
    head = struct.pack('<4I', save_tiles.TAG, block, sum(len(c) for c in packed), len(payload))
    return head + b''.join(struct.pack('<2I', len(c), len(part)) for c, part in zip(packed, parts)) + b''.join(packed)


class SaveTiles(unittest.TestCase):
    def test_the_store_is_found_in_a_decompressed_save_and_compared_with_the_baked_one(self):
        baked_flags = [0x020000] * 18
        saved_flags = list(baked_flags)
        saved_flags[0] = 0x622820       # tile (0, 0, 0): a floor after the rebuild
        saved_flags[4] = 0x0A8040       # tile (1, 1, 0): occupied
        # the dims alone, before the store, are not taken for it (a save names them elsewhere too)
        first = b'x' * 61 + struct.pack('<3i', 3, 3, 2) + b'y' * 30
        payload = first + store(saved_flags) + b'z' * 77
        data = bytes(save_tiles.HEADER) + chunk(payload[:100]) + chunk(payload[100:], block=64)
        blob = save_tiles.decompress(data)
        self.assertEqual(blob, payload)
        saved = save_tiles.static_store(blob, (3, 3, 2), 1)
        baked = save_tiles.wdparse.parse(store(baked_flags), 0)
        self.assertEqual(save_tiles.flags(saved, 0, 0, 0), 0x622820)
        self.assertEqual(save_tiles.flags(saved, 1, 1, 0), 0x0A8040)
        self.assertEqual(save_tiles.flags(saved, 2, 2, 1), 0x020000)
        self.assertIsNone(save_tiles.flags(saved, 3, 0, 0))
        lines, counts = save_tiles.rows(baked, saved, 0, 2, 0, 1, 0)
        self.assertEqual(counts, (0, 1, 2))
        self.assertEqual(lines[1], '  y   0: 020000..->622820F.* 020000..->020000..  020000..->020000.. ')
        self.assertIn('020000..->0a8040.O*', lines[0])
        with self.assertRaises(ValueError):
            save_tiles.static_store(blob, (52, 39, 12), 1404)
        with self.assertRaises(ValueError):
            save_tiles.decompress(bytes(save_tiles.HEADER) + b'not a save')


if __name__ == '__main__':
    unittest.main()
