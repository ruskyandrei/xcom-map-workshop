### The level's actor list, a volume's corners, a material's textures and a mesh's bounds are read inside their export

Four readers of an export's native data read the package's bytes with `struct.unpack_from`, bounded only by the end of
the file, so a damaged count or a short export was read on into the next export's bytes. They now read through the
package's bounded reader (`Package.native`, which refuses a read past the export's end with a `FormatError`):

- [scene_metadata.py](../../tools/viewer/scene_metadata.py)' `level_list` (the persistent level's actor list) and
  `plain_box` (a floor volume's brush corners; a vertex count is checked as a count);
- [export.py](../../tools/viewer/export.py)' `compiled_textures` (a cooked material's texture list; it kept its final
  check, which already kept it from answering with another export's references);
- [library.py](../../tools/viewer/library.py)' `describe` (a mesh's bounds, which give a piece's size and box).

Each keeps its answer when its export can't be read (the actor list's `None`, the volume's `None`, the material's
`[]`; a piece is refused as before by the scan's catch, a `FormatError` being a `ValueError`).

Checked: new tests in [test_damaged_packages.py](../../tools/viewer/tests/test_damaged_packages.py) on made-up packages
([upk_fixtures.py](../../tools/upk/tests/upk_fixtures.py) takes the names a body's properties use): an actor list whose
count runs past the level, a mesh with four of its seven bound numbers. Both failed before (the list read two more
actors from the next export; the bounds took three numbers from it). The exports of URB_Bar, URB_PoliceStation and
TempleShip from the LWR install are byte for byte the same as before the change (1,891 files), in the same time
(68.0 s before, 69.6 s after, noisy); a library scan of the three maps gives the same 746 entries. The viewer tests of
the exporter, the library, the effects and the spawn records pass.
