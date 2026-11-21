"""A damaged package in the install is refused, not read on (KB-9): a damaged or cut-short map-picture package
(<cooked>/<library>_SF.upk) is skipped, so the other packages' pictures are still listed and the Project manager
still lists its projects; before, the package reader's struct.error or IndexError went through the picture code's
catch and the listing failed. The readers of an export's native data read inside that export, never on into the next
one's bytes (the level's actor list, a mesh's bounds)."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import library  # noqa: E402
import manager  # noqa: E402
from package import FormatError, Package  # noqa: E402
import packs  # noqa: E402
import pictures  # noqa: E402
import scene_metadata  # noqa: E402
import texture  # noqa: E402
from viewer_fixtures import ID, ManagerInstalls  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / 'upk' / 'tests'))
from upk_fixtures import made_up_package  # noqa: E402

# the good package: the DLC's map pictures, two of them; the damaged one is the base game's, read first
GOOD = made_up_package((('Texture2D', 'URB_Bar', 0, b''), ('Texture2D', 'DLC1_1_LowFriends', 0, b'')))[0]
WHOLE, AT = made_up_package((('Package', 'Maps', 0, b''), ('Texture2D', 'URB_Mall', 1, b''),
                             ('Texture2D', 'URB_Cafe', 1, b'')))


def patched(at, fmt, *values):
    out = bytearray(WHOLE)
    struct.pack_into(fmt, out, at, *values)
    return bytes(out)


# each way a map-picture package can be damaged: what the reader met before (in brackets), all a ValueError now
DAMAGED = {
    'a file of five bytes (struct.error)': WHOLE[:5],
    'cut short in the summary (struct.error)': WHOLE[:AT['gens'] - 3],
    'cut short in the name table (struct.error)': WHOLE[:AT['name_at'][8] + 12],
    'cut short in the export table (struct.error)': WHOLE[:AT['depends'] - 1],
    'an export whose class is past the imports (IndexError)': patched(AT['export_at'][1], '<i', -40),
    'an export whose outer is past the exports (IndexError)': patched(AT['export_at'][2] + 8, '<i', 40),
}


def write_pictures(cooked, damaged):
    cooked.mkdir(parents=True, exist_ok=True)
    (cooked / 'UILibrary_MapImages_SF.upk').write_bytes(damaged)
    (cooked / 'UILibrary_MapImages_DLC1_SF.upk').write_bytes(GOOD)


class MapPictures(unittest.TestCase):
    def test_a_damaged_map_picture_package_is_skipped_and_the_others_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n, (what, damaged) in enumerate(DAMAGED.items()):
                cooked = Path(tmp) / str(n)
                write_pictures(cooked, damaged)
                index = pictures._base_index(cooked)
                self.assertEqual({k: v[2] for k, v in index.items()},
                                 {'urb_bar': 'UILibrary_MapImages_DLC1', 'dlc1_1_lowfriends': 'UILibrary_MapImages_DLC1'},
                                 what)
                self.assertEqual(pictures.base_library(cooked, 'URB_Bar'), 'UILibrary_MapImages_DLC1', what)
                self.assertIsNone(pictures.base_library(cooked, 'URB_Mall'), what)
                self.assertEqual(pictures.status(None, dict(source=dict(map='URB_Mall')), cooked), 'none', what)
            # the same package whole lists its pictures
            cooked = Path(tmp) / 'whole'
            write_pictures(cooked, WHOLE)
            self.assertEqual(pictures.base_library(cooked, 'URB_Mall'), 'UILibrary_MapImages')
            self.assertEqual(pictures.base_library(cooked, 'urb_cafe'), 'UILibrary_MapImages')


class Listing(ManagerInstalls, unittest.TestCase):
    def test_the_project_manager_lists_its_projects_beside_a_damaged_map_picture_package(self):
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        for what, damaged in DAMAGED.items():
            write_pictures(cooked, damaged)
            listed = manager.listing(self.store, self.builds, self.player())
            row = next(p for p in listed['projects'] if p['id'] == ID)
            # the project's map, Bar, has its picture in the good package
            self.assertEqual((row['map'], row['picture']), ('URB_Bar', 'base'), what)


NET_NONE = struct.pack('<i', 0) + struct.pack('<ii', 0, 0)     # a net index and the closing None: no properties
NEXT = ('Package', 'Next', 0, NET_NONE + struct.pack('<3f', 7.0, 8.0, 9.0))     # the export whose bytes follow


class Bounded(unittest.TestCase):
    """A count or a struct that runs past its export's end is refused, not read on into the next export's bytes."""

    def package(self, objects, extra_names=()):
        data, at = made_up_package(objects, extra_names=extra_names)
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'Map.upk'
        path.write_bytes(data)
        return Package(path), at['index']

    def test_the_level_s_actor_list_is_read_inside_the_level(self):
        def level(count, actors):
            body = NET_NONE + struct.pack('<ii', 2, count) + struct.pack('<%di' % len(actors), *actors)
            return self.package((('World', 'TheWorld', 0, NET_NONE), ('Level', 'PersistentLevel', 1, body),
                                 ('StaticMeshActor', 'Rock', 2, NET_NONE), NEXT))[0]
        self.assertEqual(scene_metadata.level_list(level(1, [3])), {3})
        # a count of three with one actor listed: before, the next exports' bytes were read as two more actors
        self.assertIsNone(scene_metadata.level_list(level(3, [3])))

    def test_a_mesh_s_bounds_are_read_inside_the_mesh(self):
        def with_component(bounds):
            def objects(component):
                return (('StaticMeshActor', 'Rock', 0, NET_NONE), ('StaticMeshComponent', 'Part', 1, component),
                        ('StaticMesh', 'RockMesh', 0, NET_NONE + struct.pack('<%df' % len(bounds), *bounds)), NEXT)
            # the component's one property, StaticMesh = export 3, by the name table's places (bodies don't move them)
            index = made_up_package(objects(b''), extra_names=('ObjectProperty',))[1]['index']
            component = (struct.pack('<i', 0) + struct.pack('<6i', index['StaticMesh'], 0, index['ObjectProperty'], 0, 4, 0)
                         + struct.pack('<i', 3) + struct.pack('<ii', 0, 0))
            return self.package(objects(component), extra_names=('ObjectProperty',))[0]
        whole = library.describe(with_component((0.0, 0.0, 0.0, 10.0, 20.0, 30.0, 40.0)), 1)
        self.assertEqual((whole['name'], whole['size']), ('RockMesh', [20.0, 40.0, 60.0]))
        # four of the seven numbers: before, the other three came from the next export's bytes
        with self.assertRaises(FormatError):
            library.describe(with_component((0.0, 0.0, 0.0, 10.0)), 1)


class PackageGuid(unittest.TestCase):
    """packs.package_guid reads the GUID through upkinfo.summary (item 6.7): a summary that does not read is None."""

    def guid(self, data):
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'Map.upk'
        path.write_bytes(data)
        return packs.package_guid(path)

    def test_a_good_package_gives_its_guid_and_an_all_zero_one_is_seen(self):
        self.assertEqual(self.guid(WHOLE), bytes(range(16)))
        zeroed = bytearray(WHOLE)
        zeroed[AT['gens'] - 16:AT['gens']] = bytes(16)
        self.assertEqual(self.guid(bytes(zeroed)), bytes(16))       # the pack export's warning

    def test_a_summary_cut_short_and_a_file_that_is_no_package_give_none(self):
        # cut after the GUID, in the chunk table: before, the GUID was taken from a summary that does not read
        self.assertIsNone(self.guid(WHOLE[:AT['chunks'] + 2]))
        self.assertIsNone(self.guid(WHOLE[:AT['gens'] - 3]))        # cut inside the GUID
        self.assertIsNone(self.guid(b'bar'))
        self.assertIsNone(self.guid(b'not a package at all, but long enough to hold a summary\r\n' * 8))
        self.assertIsNone(packs.package_guid(Path(self.enterContext(tempfile.TemporaryDirectory())) / 'missing.upk'))


def bulk(blocks, flags=16, block=8, tag=0x9E2A83C1, total=None, packed=None, table=None):
    """A compressed bulk payload of `blocks` (each block's bytes), LZO (16, literal runs) or zlib (2)."""
    import package_edit
    encoded = [package_edit.lzo_literals(b) if flags & 16 else zlib.compress(b) for b in blocks]
    table = table if table is not None else [(len(e), len(b)) for e, b in zip(encoded, blocks)]
    head = struct.pack('<4I', tag, block, sum(len(e) for e in encoded) if packed is None else packed,
                       sum(len(b) for b in blocks) if total is None else total)
    return head + b''.join(struct.pack('<2I', *t) for t in table) + b''.join(encoded)


class BulkPayload(unittest.TestCase):
    """texture.decompress_payload reads its header and block table through decomp.read_chunk (item 6.6) and keeps its
    own checks: LZX refused, the 512 MB limit, the payload ending where its blocks end. Each refusal a FormatError."""
    BLOCKS = [b'abcdefgh', b'ijklmnop', b'qrs']

    def test_lzo_and_zlib_payloads_decode_and_an_uncompressed_one_is_as_it_is(self):
        self.assertEqual(texture.decompress_payload(bulk(self.BLOCKS), 16), b''.join(self.BLOCKS))
        self.assertEqual(texture.decompress_payload(bulk(self.BLOCKS, flags=2), 2), b''.join(self.BLOCKS))
        self.assertEqual(texture.decompress_payload(b'plain bytes', 0), b'plain bytes')

    def test_a_damaged_payload_is_a_format_error(self):
        good = bulk(self.BLOCKS)
        damaged = {
            'packed sizes that do not add up': bulk(self.BLOCKS, packed=len(good) - 30),
            'unpacked sizes that do not add up': bulk(self.BLOCKS, total=18),
            'another tag': bulk(self.BLOCKS, tag=0x12345678),
            'a block size of 0': bulk(self.BLOCKS, block=0),
            'a header cut short': good[:12],
            'a block table cut short': good[:24],
            'blocks cut short': good[:-1],
            'bytes after its blocks': good + b'\0',
            'a total past the limit': bulk([b'x'], block=1 << 30, total=texture.BULK_LIMIT + 1,
                                           table=[(len(bulk([b'x'])) - 24, texture.BULK_LIMIT + 1)]),
        }
        for what, data in damaged.items():
            with self.assertRaises(FormatError, msg=what):
                texture.decompress_payload(data, 16)
        with self.assertRaisesRegex(FormatError, 'LZX'):
            texture.decompress_payload(good, 128)
        # sums that add up, but a block that decodes to another size than its entry: lzo1x's ValueError, as before
        sizes = [(c, u) for c, u in struct.iter_unpack('<2I', good[16:40])]
        shifted = bulk(self.BLOCKS, table=[(sizes[0][0], 7), (sizes[1][0], 9), sizes[2]])
        with self.assertRaisesRegex(ValueError, 'not 7'):
            texture.decompress_payload(shifted, 16)


if __name__ == '__main__':
    unittest.main()
