"""Read-only statistics of EW directional lightmap pairs, to rank codec hypotheses (EXP-16 run 2).

For every LOD-0 2D lightmap record it summarises the three slot scales. For the busiest atlas pairs it decodes the
top mip of both textures and samples every receiver rectangle in them (inset from its edge, near-black directional
texels skipped), then reports distributions: the largest channel of NormalizedAverageColor, the channels of
DirectionalMaxComponent and how they correlate.

Writes bounded metadata JSON only; no image or texture data is exported. Does not decode the shader, so the numbers
support or weaken a reading of the format; they do not establish the decoder.

  python -B tools/bake/lightmap_stats.py <map.upk> [...] --out research/evidence/<name>.json [--pairs 3]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lighting_records as lighting  # noqa: E402
from lightmap_textures import top_mip_rgb  # noqa: E402,F401 (the readers the relight uses; udk_calib_read imports them here)

INSET = 2
DARK = 0.02
PERCENTILES = [1, 10, 50, 90, 99]


def rounded(values, digits=4):
    return [round(float(v), digits) for v in values]


def lod0_records(p):
    out = []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in ('StaticMeshComponent', 'FracturedStaticMeshComponent'):
            continue
        if not p.name(i).startswith('TheWorld.'):
            continue
        component = lighting.component_record(p, i)
        if component['lods'] and component['lods'][0]['lightmap']['type'] == 2:
            out.append((p.name(i), component['lods'][0]['lightmap']))
    return out


def scale_summary(records, slot):
    s = np.array([lm['slots'][slot]['scale'] for _, lm in records])
    return dict(distinct=len({tuple(row) for row in s.tolist()}), min=rounded(s.min(0)), max=rounded(s.max(0)),
                unequalChannels=int((np.ptp(s, axis=1) > 1e-6).sum()))


def pair_samples(p, members, a, b):
    A, B = top_mip_rgb(p, a), top_mip_rgb(p, b)
    if A.shape != B.shape:
        raise ValueError('Pair textures differ in size')
    h, w, _ = A.shape
    colour, directional, used = [], [], 0
    for _, lm in members:
        sx, sy = lm['coordinateScale']
        bx, by = lm['coordinateBias']
        x0, y0 = int(round(bx * w)), int(round(by * h))
        x1, y1 = int(round((bx + sx) * w)), int(round((by + sy) * h))
        if x1 - x0 <= 2 * INSET + 1 or y1 - y0 <= 2 * INSET + 1:
            continue
        a_ = A[y0 + INSET:y1 - INSET, x0 + INSET:x1 - INSET].reshape(-1, 3)
        b_ = B[y0 + INSET:y1 - INSET, x0 + INSET:x1 - INSET].reshape(-1, 3)
        keep = b_.max(1) > DARK
        colour.append(a_[keep])
        directional.append(b_[keep])
        used += 1
    return np.concatenate(colour), np.concatenate(directional), used, [w, h]


def audit(path, pair_count):
    p = lighting.Package(path)
    if p.header['lic'] != 64:
        raise ValueError('This tool reads EW licensee-64 component records')
    records = lod0_records(p)
    pairs = collections.defaultdict(list)
    for name, lm in records:
        pairs[(lm['slots'][0]['index'], lm['slots'][1]['index'])].append((name, lm))
    busiest = sorted(pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:pair_count]
    colour, directional, chosen = [], [], []
    for (a, b), members in busiest:
        c, d, used, size = pair_samples(p, members, a, b)
        colour.append(c)
        directional.append(d)
        chosen.append(dict(textures=[p.name(a), p.name(b)], size=size, receivers=len(members),
                           receiversSampled=used, texels=len(c)))
    colour, directional = np.concatenate(colour), np.concatenate(directional)
    peak = colour.max(1)
    return dict(
        path=str(p.path), sha256=lighting.digest(p.path), lod0Records2d=len(records),
        slotScales={'slot0': scale_summary(records, 0), 'slot1': scale_summary(records, 1),
                    'slot2': scale_summary(records, 2)},
        slotTexturePatterns=dict(collections.Counter(
            ','.join(s['texture'].rsplit('_', 1)[0] if s['index'] else 'None' for s in lm['slots'])
            for _, lm in records)),
        pairs=chosen, texels=len(colour),
        normalizedAverageColor=dict(
            maxChannelPercentiles=dict(zip(map(str, PERCENTILES), rounded(np.percentile(peak, PERCENTILES), 3))),
            fractionMaxChannelAtLeast094=round(float((peak >= 0.94).mean()), 4),
            channelMeans=rounded(colour.mean(0), 3)),
        directionalMaxComponent=dict(
            channelMeans=rounded(directional.mean(0), 3),
            maxChannelPercentiles=dict(zip(map(str, PERCENTILES),
                                           rounded(np.percentile(directional.max(1), PERCENTILES), 3))),
            medianRelativeSpread=round(float(np.median(
                (directional.max(1) - directional.min(1)) / directional.max(1))), 3),
            channelCorrelation=[rounded(row, 3) for row in np.corrcoef(directional.T)]))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('packages', nargs='+', type=Path)
    a.add_argument('--out', required=True, type=Path)
    a.add_argument('--pairs', type=int, default=3, help='Busiest atlas pairs to sample per map')
    args = a.parse_args()
    if args.out.suffix != '.json':
        a.error('Output must be metadata JSON')
    for src in args.packages:
        if args.out.resolve().is_relative_to(src.resolve().parent):
            a.error('Output must be outside the input content directory')
    before = {str(p.resolve()): lighting.digest(p) for p in args.packages}
    result = dict(
        date='2026-11-06',
        scope='Read-only statistics of lightmap scales and texel values; not a decoder or runtime test',
        method=dict(insetTexels=INSET, skipDirectionalMaxBelow=DARK, mip='largest live mip, decoded DXT1 RGB / 255'),
        toolHashes={'tools/bake/lightmap_stats.py': lighting.digest(__file__),
                    'tools/upk/lighting_records.py': lighting.digest(lighting.__file__)},
        packages=[audit(p, args.pairs) for p in args.packages])
    assert before == {str(p.resolve()): lighting.digest(p) for p in args.packages}, 'Input changed during audit'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    for p in result['packages']:
        print(Path(p['path']).stem, 'texels', p['texels'], json.dumps(p['slotScales']))
        print('  colour max-channel', json.dumps(p['normalizedAverageColor']))
        print('  directional', json.dumps(p['directionalMaxComponent']))


if __name__ == '__main__':
    main()
