"""The Level's lighting samples for moving things (lighting_records.probe_volume): its precomputed light volume read
from the end of the Level's native data, on made-up bytes and on the install's URB_Bar."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import paths  # noqa: E402
paths.use('upk', 'viewer', 'lab')
import lighting_records  # noqa: E402
from package import Reader  # noqa: E402
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
SUFFIX = bytes(73)          # an empty visibility handler and an empty volume distance field


def sample(position, radius=96.0, shadowed=0, indirect=(10, 20, 30, 255)):
    """One 33-byte FVolumeLightingSample: position and radius, four direction bytes, three colours, the mark."""
    return (struct.pack('<4f', *position, radius) + bytes([1, 2, 3, 4]) + bytes(indirect) + bytes(4)
            + bytes([5, 6, 7, 8]) + bytes([shadowed]))


def volume(samples, box=(-100.0, -100.0, -50.0, 100.0, 100.0, 50.0), spacing=64.0):
    """A light volume: initialized, its box (valid), its spacing, its counted samples."""
    return (struct.pack('<i6fB', 1, *box, 1) + struct.pack('<f', spacing) + struct.pack('<i', len(samples))
            + b''.join(samples))


class StubLevel:
    """A package whose one export (1, a Level) has the native data `data`: bytes standing in for the Level's physics
    caches, then the volume and the suffix."""

    def __init__(self, data):
        self.data = data

    def native(self, index):
        return Reader(self.data)

    def name(self, index):
        return 'TheWorld.PersistentLevel'


class ProbeVolume(unittest.TestCase):
    def test_reads_the_samples_and_counts_the_shadowed(self):
        samples = [sample((0.0, 0.0, 0.0)), sample((50.0, 0.0, 0.0), shadowed=1),
                   sample((0.0, 50.0, 10.0), shadowed=1, indirect=(0, 0, 0, 255))]
        prefix = b'\x07' * 41
        got = lighting_records.probe_volume(StubLevel(prefix + volume(samples) + SUFFIX), 1, [])
        self.assertEqual(got['offset'], len(prefix))
        self.assertEqual(got['count'], 3)
        self.assertEqual(got['shadowedFromDominant'], 2)
        self.assertEqual(got['nonzeroIndirectRGB'], 2)
        self.assertEqual(got['bounds'], [-100.0, -100.0, -50.0, 100.0, 100.0, 50.0])
        self.assertEqual(got['sampleSpacing'], 64.0)
        self.assertEqual(got['centersOutsideStoredBounds'], 0)

    def test_a_query_point_finds_its_nearest_samples(self):
        samples = [sample((0.0, 0.0, 0.0)), sample((50.0, 0.0, 0.0)), sample((300.0, 0.0, 0.0))]
        got = lighting_records.probe_volume(StubLevel(bytes(8) + volume(samples) + SUFFIX), 1,
                                            [dict(label='a', location=[45.0, 0.0, 0.0])])
        point, = got['points']
        self.assertEqual([c['sampleIndex'] for c in point['closest']], [1, 0, 2])
        self.assertEqual(point['sphereCoverageCount'], 2)

    def test_a_level_ending_otherwise_is_refused(self):
        data = bytes(8) + volume([sample((0.0, 0.0, 0.0))]) + b'\x01' + bytes(72)
        with self.assertRaises(lighting_records.FormatError):
            lighting_records.probe_volume(StubLevel(data), 1, [])

    def test_no_volume_is_refused(self):
        with self.assertRaises(lighting_records.FormatError):
            lighting_records.probe_volume(StubLevel(bytes(200) + SUFFIX), 1, [])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class InstallBar(unittest.TestCase):
    def test_the_bars_samples(self):
        p = lighting_records.Package(BAR)
        level = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'Level')
        got = lighting_records.probe_volume(p, level, [])
        # research/evidence/lighting-audit-2026-11-06.json
        self.assertEqual((got['count'], got['shadowedFromDominant']), (1743, 222))


if __name__ == '__main__':
    unittest.main()
