"""Read-only evidence for the smaller built maps plan (F-151, stage S0): the lightmaps and shadow maps of every package
of the install, as the game's own bake made them.

For each LightMapTexture2D and ShadowMapTexture2D: its format and size, whether every live mip is inside the package
(inline), its saved properties, and its mip chain. The counts say what a texture the size of a piece is to the game:
small lightmaps of their own (down to 4 by 4) are common, the small ones are held wholly inside the map, and a few
are NeverStream with no cache name, the form inline_lighting.py writes. One example of each size and class is kept
with its properties and mips, the layout lightmap_textures.sized_texture follows.

Uses the configured install's CookedPCConsole (XCOM_COOKED names another). Prints a summary; --output saves the JSON.

  python -B research/evidence/lighting-texture-survey.py [--maps URB_Bar ...] [--output <out.json>]
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for folder in ('upk', 'viewer', 'bake', 'lab'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import labpaths  # noqa: E402
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402


def survey(paths):
    dims, inline_dims, props, chains = Counter(), Counter(), Counter(), Counter()
    examples, failed, maps = {}, [], 0
    for path in paths:
        try:
            p = lighting.Package(path)
        except Exception as error:      # noqa: BLE001  (a package the reader can't open: counted, not fatal)
            failed.append([path.name, str(error)[:80]])
            continue
        found = False
        for k in range(1, len(p.exports) + 1):
            cls = p.cls(k)
            if cls not in lightmap_fields.TEXTURE_CLASSES:
                continue
            found = True
            try:
                t = lightmap_fields.texture_fields(p, k)
                saved = {name: p.own(k, name) for name, _ in lightmap_fields.property_offsets(p, k)}
            except Exception as error:  # noqa: BLE001
                failed.append([f'{path.name}:{p.name(k)}', str(error)[:80]])
                continue
            kind = 'lightmap' if cls == 'LightMapTexture2D' else 'shadow map'
            top = t['mips'][0]
            key = (kind, t['format'], top['width'], top['height'])
            live = [m for m in t['mips'] if m['bytes'] and not m['flags'] & 32]
            inside = all(m['inline'] for m in live)
            dims[key] += 1
            inline_dims[key] += inside
            props[(kind, inside, tuple(sorted(saved)))] += 1
            chains[(kind, top['width'], top['height'], tuple((m['width'], m['height']) for m in t['mips']))] += 1
            if str(key) not in examples and inside:
                examples[str(key)] = dict(texture=f'{path.name}:{p.name(k)}',
                                          properties={n: v for n, v in saved.items() if not isinstance(v, (bytes, bytearray))},
                                          mips=[[m['width'], m['height'], m['bytes'], m['flags']] for m in t['mips']])
        maps += found
    rows = lambda counter: [[list(k), v] for k, v in sorted(counter.items(), key=lambda kv: -kv[1])]  # noqa: E731
    return dict(packages=len(paths), packagesWithLighting=maps, failed=failed[:40],
                textures=sum(dims.values()), sizes=rows(dims), wholeInside=rows(inline_dims),
                properties=[[list(k[:2]) + [list(k[2])], v] for k, v in sorted(props.items(), key=lambda kv: -kv[1])],
                mipChains=[[[k[0], k[1], k[2]], [list(m) for m in k[3]], v]
                           for k, v in sorted(chains.items(), key=lambda kv: -kv[1])][:60],
                examples=examples)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--maps', nargs='*', help='package names (default: every .upk of the cooked folder)')
    a.add_argument('--output', type=Path)
    args = a.parse_args()
    cooked = labpaths.lwr_cooked()
    if cooked is None:
        raise SystemExit('no CookedPCConsole: set XCOM_COOKED or the settings (python tools/viewer/viewer.py settings)')
    paths = [cooked / f'{m}.upk' for m in args.maps] if args.maps else sorted(cooked.glob('*.upk'))
    got = survey(paths)
    print('%d packages, %d with lighting textures, %d textures' % (got['packages'], got['packagesWithLighting'],
                                                                   got['textures']))
    for (kind, fmt, w, h), n in got['sizes'][:20]:
        inside = dict((tuple(k), v) for k, v in got['wholeInside']).get((kind, fmt, w, h), 0)
        print('  %-10s %s %4d x %-4d %6d  (%d wholly inside)' % (kind, fmt, w, h, n, inside))
    if args.output:
        args.output.write_text(json.dumps(got, indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
