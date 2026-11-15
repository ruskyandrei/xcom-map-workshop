"""Where a build's time went (faster-bake plan, section 6.2): the stages' seconds from the package's manifest, and
the relight's own record of its phases, its slowest pieces, the pieces kept from the last build, its workers' peak
memory and the packages it decoded.

  python -B tools/bake/profile_build.py <package folder | manifest.json | work folder> [--pieces 10]

A package folder is <builds>/<Variant>; its manifest names the build's work folder, where the relight's record is
(<work>/lit/<Variant>.relight.json). A work folder alone gives the relight's part.
"""
import argparse
import json
from pathlib import Path


def load(path):
    path = Path(path)
    manifest = None
    if path.is_file():
        manifest = json.loads(path.read_text(encoding='utf-8'))
    elif (path / 'manifest.json').is_file():
        manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    work = Path(manifest['work']) if manifest else path
    records = sorted((work / 'lit').glob('*.relight.json')) if (work / 'lit').is_dir() else []
    relight = json.loads(records[0].read_text(encoding='utf-8')) if records else None
    return manifest, relight


def lines(manifest, relight, pieces=10):
    out = []
    if manifest:
        out.append('%s, %s build, %s s' % (manifest.get('buildId'), 'quick' if manifest.get('quick') else 'full',
                                           manifest.get('seconds')))
        out.append('stages:')
        for s in manifest.get('stages') or []:
            out.append('  %-12s %7s s' % (s['stage'], s.get('seconds', '?')))
    timing = (relight or {}).get('timing')
    if not timing:
        out.append('no relight record with timings (a quick build, or one made before they were recorded)')
        return out
    out.append('relight (%d workers):' % relight.get('jobs', 0))
    names = dict(scenes='opening the map, the scenes', reach='the receivers, the reach test',
                 pieces='the pieces and shadow maps', shadowMaps='shadow maps put together',
                 writing='writing the lighting', total='in all')
    for key, label in names.items():
        if key in timing['seconds']:
            out.append('  %-30s %7.1f s' % (label, timing['seconds'][key]))
    out.append('  pieces: %d relit (%.0f s summed over the workers), %d kept from the last build, %d written, '
               '%d unchanged, %d left by the quick test' % (
                   timing.get('piecesRelit', 0), timing.get('pieceSecondsSummed', 0), timing.get('piecesKept', 0),
                   len(relight.get('components') or []), len(relight.get('unchanged') or []),
                   len(relight.get('unreached') or [])))
    if timing.get('shadowMapsTraced'):
        out.append('  shadow maps: %d traced with the pieces (%.0f s summed over the workers)' % (
            timing['shadowMapsTraced'], timing.get('shadowMapSecondsSummed', 0)))
    out.append('  a worker\'s peak memory: %s MB' % timing.get('peakWorkerMemoryMB'))
    d = timing.get('packagesDecoded') or {}
    out.append('  packages: %s decoded (%.1f s), %s from this process, %s from the kept images' % (
        d.get('decoded'), d.get('seconds', 0), d.get('memo'), d.get('disk')))
    slow = sorted((timing.get('pieceSeconds') or {}).items(), key=lambda x: -x[1])[:pieces]
    if slow:
        out.append('  the slowest pieces (seconds summed over their bands):')
        reports = {r['component']: r for r in relight.get('components') or []}
        for path, seconds in slow:
            texels = (reports.get(path) or {}).get('texels') or {}
            out.append('    %7.1f  %s%s' % (seconds, path.split('.', 2)[-1], '  (%s texels, %s in reach)' % (
                texels.get('covered'), texels.get('inReach', 'all')) if texels else ''))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('build', type=Path)
    a.add_argument('--pieces', type=int, default=10, help='how many of the slowest pieces to list')
    args = a.parse_args()
    print('\n'.join(lines(*load(args.build), pieces=args.pieces)))


if __name__ == '__main__':
    main()
