"""A damaged package in the install is refused, not read on (KB-9): a damaged or cut-short map-picture package
(<cooked>/<library>_SF.upk) is skipped, so the other packages' pictures are still listed and the Project manager
still lists its projects; before, the package reader's struct.error or IndexError went through the picture code's
catch and the listing failed."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import manager  # noqa: E402
import pictures  # noqa: E402
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


if __name__ == '__main__':
    unittest.main()
