"""The sun's records in lighting_records: the Level's lighting samples for moving things (its precomputed light volume
read from the end of the Level's native data, light_volume and probe_volume), the edits that set their marks
(mark_edits), and the dominant light's own shadow map of the level (dominant_shadow_map), on made-up bytes and on the
install's URB_Bar."""
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


class Marks(unittest.TestCase):
    def setUp(self):
        self.prefix = b'\x07' * 41
        samples = [sample((0.0, 0.0, 0.0)), sample((50.0, 0.0, 0.0), shadowed=1), sample((0.0, 50.0, 0.0))]
        self.data = self.prefix + volume(samples) + SUFFIX
        self.volume = lighting_records.light_volume(StubLevel(self.data), 1)

    def test_each_mark_is_its_samples_last_byte(self):
        places = lighting_records.mark_places(self.volume)
        self.assertEqual(places, [len(self.prefix) + 37 + 33 * k + 32 for k in range(3)])
        self.assertEqual([self.data[at] for at in places], [0, 1, 0])

    def test_the_edits_set_only_the_marks_that_change(self):
        edits = lighting_records.mark_edits(self.volume, [1, 1, 0])
        self.assertEqual(edits, [(len(self.prefix) + 37 + 32, b'\x01')])
        changed = bytearray(self.data)
        for at, value in edits:
            changed[at:at + len(value)] = value
        again = lighting_records.light_volume(StubLevel(bytes(changed)), 1)
        self.assertEqual([s[-1] for s in again['samples']], [1, 1, 0])
        self.assertEqual([s[:-1] for s in again['samples']], [s[:-1] for s in self.volume['samples']])
        self.assertEqual(lighting_records.mark_edits(self.volume, [0, 1, 0]), [])

    def test_a_wrong_count_or_value_is_refused(self):
        with self.assertRaises(ValueError):
            lighting_records.mark_edits(self.volume, [0, 1])
        with self.assertRaises(ValueError):
            lighting_records.mark_edits(self.volume, [0, 2, 0])


def matrix(rows):
    """A Matrix struct's 64 bytes from four (X, Y, Z, W) rows, each saved W first."""
    return b''.join(struct.pack('<4f', r[3], r[0], r[1], r[2]) for r in rows)


IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


class StubLight:
    """A package whose export 1 is a dominant light's component: `depths` saved ahead of its header, and its
    DominantLightShadowInfo's members (`info`) as the package's tagged reader gives them."""

    def __init__(self, depths, info, cls='DominantDirectionalLightComponent', count=None):
        body = struct.pack('<i', len(depths) if count is None else count) + struct.pack(f'<{len(depths)}H', *depths)
        self.data = b'\x09' * 5 + body + bytes(8) + b'(properties)'
        self.exports = [dict(off=5, size=len(self.data) - 5)]
        self.info, self.kind = info, cls

    def cls(self, index):
        return self.kind

    def name(self, index):
        return 'TheWorld.PersistentLevel.DominantDirectionalLight_1.DominantDirectionalLightComponent_0'

    def own(self, index, key):
        return b'(the struct)' if key == 'DominantLightShadowInfo' and self.info is not None else None

    def tagged(self, reader):
        return {(k, 0): dict(kind='', value=v) for k, v in self.info.items()}


def shadow_info(x, y, box=(-100.0, -50.0, -20.0, 100.0, 50.0, 30.0)):
    return dict(WorldToLight=matrix(IDENTITY), LightToWorld=matrix([[0.0, 1.0, 0.0, 0.0]] + IDENTITY[1:]),
                LightSpaceImportanceBounds=struct.pack('<6fB', *box, 1), ShadowMapSizeX=x, ShadowMapSizeY=y)


class DominantShadowMap(unittest.TestCase):
    def test_reads_the_depths_the_size_the_matrices_and_the_box(self):
        got = lighting_records.dominant_shadow_map(StubLight([1, 2, 3, 65535, 0, 7], shadow_info(3, 2)), 1)
        self.assertEqual((got['sizeX'], got['sizeY'], got['depths']), (3, 2, (1, 2, 3, 65535, 0, 7)))
        self.assertEqual(got['offset'], 5 + 4)
        self.assertEqual(got['worldToLight'], IDENTITY)
        self.assertEqual(got['lightToWorld'][0], [0.0, 1.0, 0.0, 0.0])
        self.assertEqual(got['bounds'], [-100.0, -50.0, -20.0, 100.0, 50.0, 30.0])

    def test_a_count_that_is_not_the_size_is_refused(self):
        with self.assertRaises(lighting_records.FormatError):
            lighting_records.dominant_shadow_map(StubLight([1, 2, 3, 4], shadow_info(3, 2)), 1)

    def test_an_array_running_past_the_export_is_refused(self):
        with self.assertRaises(lighting_records.FormatError):
            lighting_records.dominant_shadow_map(StubLight([1, 2], shadow_info(3, 2), count=100), 1)

    def test_another_class_is_refused(self):
        with self.assertRaises(lighting_records.FormatError):
            lighting_records.dominant_shadow_map(StubLight([], None, cls='DirectionalLightComponent'), 1)

    def test_a_light_with_no_map_of_the_level(self):
        got = lighting_records.dominant_shadow_map(StubLight([], None), 1)
        self.assertEqual((got['sizeX'], got['sizeY'], got['depths'], got['bounds']), (0, 0, (), None))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class InstallBar(unittest.TestCase):
    def test_the_bars_samples(self):
        p = lighting_records.Package(BAR)
        level = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'Level')
        got = lighting_records.probe_volume(p, level, [])
        # research/evidence/lighting-audit-2026-11-06.json
        self.assertEqual((got['count'], got['shadowedFromDominant']), (1743, 222))

    def test_the_moons_map_of_the_level(self):
        p = lighting_records.Package(BAR)
        ci = p.by_name['TheWorld.PersistentLevel.DominantDirectionalLight_1.DominantDirectionalLightComponent_0']
        got = lighting_records.dominant_shadow_map(p, ci)
        self.assertEqual((got['sizeX'], got['sizeY'], len(got['depths'])), (132, 97, 12804))
        self.assertEqual(got['offset'], p.exports[ci - 1]['off'] + 4)
        # the light space's z is the moon's direction (the actor's Rotation), and the two matrices are inverses
        to_light = [0.10984, -0.11776, 0.98695]
        self.assertTrue(all(abs(got['worldToLight'][k][2] + to_light[k]) < 1e-3 for k in range(3)))
        product = [[sum(got['worldToLight'][i][k] * got['lightToWorld'][k][j] for k in range(4)) for j in range(4)]
                   for i in range(4)]
        self.assertTrue(all(abs(product[i][j] - (i == j)) < 1e-4 for i in range(4) for j in range(4)))
        self.assertEqual([round(v) for v in got['bounds']], [-3647, -2351, -1994, 2959, 2536, 789])


if __name__ == '__main__':
    unittest.main()
