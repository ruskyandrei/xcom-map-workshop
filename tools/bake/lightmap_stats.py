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
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
import audit_lighting as lighting  # noqa: E402
from texture import decompress_payload, dds_header  # noqa: E402

INSET = 2
DARK = 0.02
PERCENTILES = [1, 10, 50, 90, 99]


def top_mip_rgb(p, index):
    """The largest live mip of a DXT1 texture as float RGB in [0, 1]."""
    raw, w, h = top_mip_raw(p, index)
    image = Image.open(io.BytesIO(dds_header(w, h, 'DXT1', len(raw)) + raw)).convert('RGB')
    return np.asarray(image, dtype=np.float64) / 255.0


def top_mip_rect(p, index, x0, y0, x1, y1):
    """top_mip_rgb(p, index)[y0:y1, x0:x1], decoding only the 4-texel blocks the rectangle touches: a piece's
    rectangle is a small part of its atlas, and a relight reads two for every piece."""
    raw, w, h = top_mip_raw(p, index)
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bx0, by0, bx1, by1 = max(0, x0 // 4), max(0, y0 // 4), min(bw, -(-x1 // 4)), min(bh, -(-y1 // 4))
    if bx1 <= bx0 or by1 <= by0:
        return np.zeros((0, 0, 3))
    part = np.frombuffer(raw, np.uint8).reshape(bh, bw, 8)[by0:by1, bx0:bx1].tobytes()
    rw, rh = (bx1 - bx0) * 4, (by1 - by0) * 4
    image = Image.open(io.BytesIO(dds_header(rw, rh, 'DXT1', len(part)) + part)).convert('RGB')
    image = np.asarray(image, dtype=np.float64) / 255.0
    return image[y0 - by0 * 4:y1 - by0 * 4, x0 - bx0 * 4:x1 - bx0 * 4]


RAW_KEPT = 64       # top mips kept for each package (half a megabyte each at 1,024 texels)


def top_mip_raw(p, index):
    """(DXT1 bytes, width, height) of a texture's largest live mip, kept for the package (many pieces share an
    atlas, and reading one from the texture cache decodes its LZO in Python)."""
    kept = p.__dict__.setdefault('_top_mip_raw', {})
    if index in kept:
        return kept[index]
    if p.effective(index, 'Format') != 'PF_DXT1':
        raise ValueError(f'{p.name(index)} is not DXT1')
    r = p.native(index)
    lighting.bulk_meta(r)
    best = None
    for _ in range(r.count()):
        start = r.pos
        m = lighting.bulk_meta(r)
        m['width'], m['height'] = r.unpack('2i')
        if m['bytes'] and not m['flags'] & 32 and (best is None or m['width'] > best[0]['width']):
            best = (m, start)
    if best is None:
        raise ValueError(f'{p.name(index)} has no live mip')
    m, start = best
    if m['inline']:
        payload = p.data[start + 16:start + 16 + m['bytes']]
    else:
        cache = p.effective(index, 'TextureFileCacheName')
        with lighting.cache_file(p.path.parent, cache).open('rb') as f:
            f.seek(m['offset'])
            payload = f.read(m['bytes'])
    raw = decompress_payload(payload, m['flags'])
    w, h = m['width'], m['height']
    if len(raw) != max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8:
        raise ValueError('DXT1 mip size mismatch')
    if len(kept) >= RAW_KEPT:
        kept.pop(next(iter(kept)))
    kept[index] = (raw, w, h)
    return kept[index]


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
                    'tools/upk/audit_lighting.py': lighting.digest(lighting.__file__)},
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
