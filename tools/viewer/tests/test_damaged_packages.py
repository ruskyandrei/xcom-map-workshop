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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import library  # noqa: E402
import manager  # noqa: E402
from package import FormatError, Package  # noqa: E402
import pictures  # noqa: E402
import scene_metadata  # noqa: E402
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


if __name__ == '__main__':
    unittest.main()
