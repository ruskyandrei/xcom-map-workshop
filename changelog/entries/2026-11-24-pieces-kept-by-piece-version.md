### The library's pieces are kept by the piece version, not the exporter's

Every new exporter version had every piece of other maps read again (all 9,733, 7 to 11 minutes, about 6 GB
rewritten, with Cache everything or one by one as they were used), though of exports 27 to 42 only two changed what a
piece holds; the rest were about maps.

- A donor's pieces folder is named `<sha16>-p<PIECE_VERSION>` (`library.piece_folder`), no longer
  `<sha16>-v<EXPORT_VERSION>`: piece records, effect records, drawings and area lights all go there, each already
  versioned by its own file. ([library.py](../../tools/viewer/library.py))
- The folders the exporter named until now (`-v42`) hold piece version 12, so where a map's `-p12` folder is not
  there yet its `-v42` one is used as it is (`ADOPTED_EXPORT`), with no renaming that a page reading from it could
  trip on: nothing already cached is read again.
- Pruning, at the main server's start and after Cache everything, takes a `-p` folder as newer than any `-v` one of
  the same map file ([prune.py](../../tools/viewer/prune.py) `piece_order`).
- The rule: an exporter change to what a piece carries (its meshes, materials or textures as written, or a field of its
  record) raises `library.PIECE_VERSION`; [export.py](../../tools/viewer/export.py)'s version notes say so.
  [test_piece_version.py](../../tools/viewer/tests/test_piece_version.py) holds it: seven of URB_Bar's pieces
  (scenery, a backdrop, a destructible, a fracturing piece, a door, a car, a physics body) exported into a scratch
  cache and fingerprinted (record but for where it is kept, meshes' bytes, textures' pixels) against
  [piece_fingerprints.json](../../tools/viewer/tests/piece_fingerprints.json); a change with the version the same
  fails, saying to raise it and write them again (`--write`). Another copy of URB_Bar skips.

Checked: the viewer, editor and repo suites (the new test about 4 s; it fails as it should with one fingerprint
altered); [test_precache.py](../../tools/viewer/tests/test_precache.py) (the plan's folder names, a `-v42` folder
taken and read into, its older ones pruned, this version's own folder preferred once there) and
[test_prune.py](../../tools/viewer/tests/test_prune.py) (a `-p` folder newer than any `-v`). The seven sample pieces
as the cache already held them in `-v42` fingerprint the same as a fresh export, so taking those folders as they are
serves the same pieces.

Known gaps: maps are still prepared again with each exporter version (their meshes and textures could be kept);
someone changing what a piece carries still has to raise the version, the test catching it only for what the seven
samples hold.
