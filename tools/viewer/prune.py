"""Old exports out of the viewer cache (the user, 13 November 2026: "automatically delete them when a new one is
available").

A map's export is a generation folder, <first 16 hex digits of the package's SHA-256>-v<exporter version>-<scope>,
with -<suffix> for a later export of the same version published beside one a running server may be serving
(export.py). Each new exporter version re-exports the maps as they open, and the older generations stayed: about
150 MB a map a version, 14 GB in all on 13 November 2026. Nothing needs them:
- the server picks each map's newest generation when it starts (catalogue.load_catalogue);
- the Build takes the export the project names, else the newest of its package (compiler.find_export), and a save
  binds a project to the export it was edited on;
- an older exporter's export can be made again from Git.
What does need care is a running server: it serves the generation it picked, and an open page reads meshes and
textures from it. So only the main server prunes (port 8768, AGENTS.md; a test server never), and only when nothing of
its own is in use: when it starts, before it picks its exports, and after an export it made itself, once it has
switched the map to the new generation.

The rule, for each map folder: of its generations of one package (the same SHA-256 prefix) and scope, the newest
readable one (exporter version, then the scene's time) stays and the older ones go. Readable is what the map list and
the Build take (catalogue.generation: the scene reads whole, of schema 1, of that package, version and scope), so the
generation they serve is never the one deleted: a newer one whose scene.json is truncated or foreign is passed over and
left as it is, never taken as the newest (review finding 17). Another package's (another install's copy of the map)
stays as its own. In-progress folders (.export-*) and anything that is not a generation are left. The library's
piece folders (library/pieces/<map>/<digest>-v<version>) go by the same rule, by their folders' time.

  python -B tools/viewer/prune.py [<cache>] [--dry-run]     what goes (and with --dry-run, nothing is deleted)
"""
import argparse
from pathlib import Path
import re
import shutil
import sys

GENERATION = re.compile(r'^(?P<digest>[0-9a-f]{16})-v(?P<version>\d+)-(?P<scope>map|sample)(?:-[A-Za-z0-9_]+)?$')
PIECES = re.compile(r'^(?P<digest>[0-9a-f]{16})-v(?P<version>\d+)$')


def _newest_first(folders, pattern, stamp):
    """{(digest, scope): [folders, newest first]} of the folders matching `pattern`."""
    groups = {}
    for folder in folders:
        m = pattern.match(folder.name)
        if not m:
            continue
        key = (m.group('digest'), m.groupdict().get('scope'))
        groups.setdefault(key, []).append((int(m.group('version')), stamp(folder), folder.name, folder))
    return {k: [f for *_, f in sorted(v, reverse=True)] for k, v in groups.items()}


def _scene_time(folder):
    try:
        return (folder / 'scene.json').stat().st_mtime_ns
    except OSError:
        return -1


def _folder_time(folder):
    try:
        return folder.stat().st_mtime_ns
    except OSError:
        return -1


def stale(cache, only=None, keep=()):
    """The generation folders that go: [Path], for every map folder of the cache root, or the map folder `only`. A
    generation with no scene.json is never the newest (an export that did not finish publishing) and is left; one whose
    scene.json can't be used (catalogue.generation) is never the newest either, and goes only when a readable one of
    its package is newer. `keep`: folders never to delete (the ones a server serves)."""
    from catalogue import usable
    cache = Path(cache)
    keep = {Path(k).resolve() for k in keep}
    out = []
    maps = [Path(only)] if only else [c for c in cache.iterdir() if c.is_dir() and not c.name.startswith('.')
                                     and c.name not in ('library', 'checks')]
    for folder in maps:
        try:
            children = [c for c in folder.iterdir() if c.is_dir() and not c.name.startswith('.')]
        except OSError:
            continue
        complete = [c for c in children if (c / 'scene.json').is_file()]
        for group in _newest_first(complete, GENERATION, _scene_time).values():
            newest = next((k for k, f in enumerate(group) if usable(f)), None)
            if newest is not None:
                out += group[newest + 1:]
    pieces = cache / 'library' / 'pieces'
    if not only and pieces.is_dir():
        for folder in pieces.iterdir():
            if folder.is_dir():
                for group in _newest_first([c for c in folder.iterdir() if c.is_dir()], PIECES, _folder_time).values():
                    out += group[1:]
    return [f for f in out if f.resolve() not in keep]


def size_of(folder):
    total = 0
    for p in Path(folder).rglob('*'):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def prune(cache, only=None, keep=(), dry_run=False, log=None):
    """Deletes stale() and returns dict(removed: [folder names relative to the cache], bytes, failed: [(name, error)]).
    A folder that can't be deleted whole (a file held open) is reported and left for the next time."""
    cache = Path(cache)
    removed, failed, total = [], [], 0
    for folder in stale(cache, only, keep):
        name = str(folder.relative_to(cache)) if folder.is_relative_to(cache) else str(folder)
        size = size_of(folder)
        if not dry_run:
            try:
                shutil.rmtree(folder)
            except OSError as error:
                failed.append((name, str(error)))
                continue
        removed.append(name)
        total += size
        if log:
            log('%s %s (%.0f MB)' % ('would remove' if dry_run else 'removed', name, size / 1e6))
    return dict(removed=removed, bytes=total, failed=failed)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('cache', type=Path, nargs='?', help='the viewer cache (default: the cache setting)')
    ap.add_argument('--dry-run', action='store_true', help='list what would go, delete nothing')
    a = ap.parse_args(argv)
    if a.cache is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from settings import load_settings
        a.cache = load_settings()['cache']
    r = prune(a.cache, dry_run=a.dry_run, log=print)
    print('%s %d folders, %.1f GB%s' % ('would remove' if a.dry_run else 'removed', len(r['removed']), r['bytes'] / 1e9,
                                       ', %d could not be removed' % len(r['failed']) if r['failed'] else ''))
    for name, error in r['failed']:
        print('  not removed: %s: %s' % (name, error))
    return 0


if __name__ == '__main__':
    sys.exit(main())
