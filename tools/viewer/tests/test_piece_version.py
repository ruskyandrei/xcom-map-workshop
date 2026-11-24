"""The library's piece version (library.PIECE_VERSION) against what a piece's export holds. Since 24 November 2026 the
library keeps its pieces by that version, not by the exporter's (library.piece_folder), so an exporter change to what
a piece carries has to raise it, or the editor goes on serving pieces exported the old way.

A few of URB_Bar's pieces (scenery, a backdrop building, a destructible, a fracturing piece, a door, a car, a physics
body) are exported into a scratch cache, and each one's fingerprint (its record but for where it is kept, its meshes'
bytes and its textures' pixels) is held against piece_fingerprints.json beside this: one that differs while the
version is the same fails, saying what to do. The fingerprints are of one copy of the map (its digest is in the file):
another copy skips. It reads the configured install (tools/viewer/settings.py) and skips without it.

  python -B tools/viewer/tests/test_piece_version.py --write     write the fingerprints again (after raising the version)
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lab'))
import library
import labpaths

RECORD = Path(__file__).with_name('piece_fingerprints.json')
BAR, NO_BAR = labpaths.install_map('URB_Bar')
SAMPLES = ('XComLevelActor_25',             # a sign: scenery, with its textures
           'StaticMeshActor_0',             # a backdrop building
           'XComDestructibleActor_340',     # an arcade machine
           'XComFracLevelActor_5',          # a fracturing column
           'XComInteractiveLevelActor_6',   # a door: its leaf and frame
           'XComDestructibleActor_63',      # a car: its body, glass and parts
           'KAsset_0')                      # a physics body: a skeletal mesh
# a record's fields that say where it is kept and by which versions, not what it holds
WHERE = ('base', 'version', 'exporterVersion')


def fingerprint(record, folder):
    """16 hex digits of what a piece's export holds: its record but for WHERE, its meshes' files and its textures'
    pixels (not their PNG bytes, which another image library could compress otherwise)."""
    from PIL import Image
    h = hashlib.sha256(json.dumps({k: v for k, v in record.items() if k not in WHERE}, sort_keys=True).encode())
    for mesh in sorted(record['meshes'].values(), key=lambda m: m['url']):
        h.update((folder / mesh['url']).read_bytes())
    for texture in sorted(record['textures'].values(), key=lambda t: t['url']):
        with Image.open(folder / texture['url']) as image:
            h.update(f'{image.mode} {image.size}'.encode())
            h.update(image.tobytes())
    return h.hexdigest()[:16]


def fingerprints():
    """{actor: fingerprint} of SAMPLES, exported now into a scratch cache, and the map's digest (16 hex digits)."""
    game = BAR.parents[3]
    with tempfile.TemporaryDirectory(prefix='piece-version-') as cache:
        shared, out = {}, {}
        for actor in SAMPLES:
            record = library.piece(cache, game, dict(package='URB_Bar', level='base', actor=actor), shared)
            folder = library.pieces_root(cache) / record['base'].removeprefix('/cache-library/')
            out[actor] = fingerprint(record, folder)
    return out, library.digest_of(BAR)[:16]


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class PieceVersionTests(unittest.TestCase):
    def test_a_piece_exported_otherwise_raises_the_piece_version(self):
        recorded = json.loads(RECORD.read_text(encoding='utf-8'))
        digest = library.digest_of(BAR)[:16]
        if digest not in recorded['maps']:
            self.skipTest(f'the fingerprints are of another copy of URB_Bar ({", ".join(recorded["maps"])}), not {digest}')
        write = f'write them again: python -B tools/viewer/tests/{Path(__file__).name} --write'
        self.assertEqual(recorded['pieceVersion'], library.PIECE_VERSION,
                         f'library.PIECE_VERSION was raised to {library.PIECE_VERSION} and the fingerprints are of '
                         f'{recorded["pieceVersion"]}: {write}')
        now, _ = fingerprints()
        changed = sorted(a for a in SAMPLES if now.get(a) != recorded['maps'][digest].get(a))
        self.assertFalse(changed, f'what a library piece holds changed ({", ".join(changed)} of URB_Bar) and '
                                  f'library.PIECE_VERSION is still {library.PIECE_VERSION}: the editor would go on serving '
                                  f'pieces exported before the change. Raise library.PIECE_VERSION (with a line on what '
                                  f'changed), then {write}')


def write():
    if not (BAR and BAR.exists()):
        raise SystemExit(NO_BAR)
    now, digest = fingerprints()
    old = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.is_file() else {}
    maps = old.get('maps', {}) if old.get('pieceVersion') == library.PIECE_VERSION else {}
    maps[digest] = now
    RECORD.write_text(json.dumps(dict(pieceVersion=library.PIECE_VERSION, maps=maps), indent=1) + '\n',
                      encoding='utf-8', newline='\n')
    print(f'{RECORD.name}: piece version {library.PIECE_VERSION}, URB_Bar {digest}: {len(now)} pieces')


if __name__ == '__main__':
    if sys.argv[1:] == ['--write']:
        write()
    else:
        unittest.main()
