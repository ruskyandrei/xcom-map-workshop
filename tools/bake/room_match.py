"""How closely our light model matches a map's own bake across many components: the yardstick of baker step L5.

An edit is relit as a change on the original bake, so small edits look right even where the model is off. A remix
that changes most of a room needs the model itself to match (EXP-17 run 7: 25% of the bar room's lit texels within
10%). This relights the components named, absolutely and without writing anything, and compares our light with the
original's at every texel the relight would write (not buried in geometry), as the light a flat surface would get
(colour times the summed directional values):

- the share of lit texels (original above 0.05) within 10% (|log2 ratio| < 0.15) and the median |log2 ratio|;
- the same by facing (floors, walls, ceilings and undersides) and by the original's brightness;
- the checkerboard test of run 7: texels grouped by component, facing and 192-unit cube, each group's median light
  against the original's; the share of texels in groups within 10% and within 40% is what a whole-room checkerboard
  in the game would show;
- per component, ranked by how much of the room's error it carries;
- with `--parts`, our light split into its sources (the component's lights direct, the emissive surfaces' area
  lights, bounce of the map's lights, the environment's rays), each source's share by facing.

  python -B tools/bake/room_match.py <map.upk> --component-list FILE [--component PATH ...] [--samples 64]
      [--bounce-rays 64] [--stride 2] [--no-emissive] [--parts] [--jobs N] [--out report.json] [--previews DIR]

Prints a summary; `--out` writes the full report (numbers only, no texel data). `--previews` writes an image per
component (original | ours | where they differ) into a folder of the caller's choosing, outside the repo: they are
decoded from the game's lightmaps.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relight  # noqa: E402  (puts tools/upk and tools/viewer on the path)
from relight import bounce, codec, lighting, lightmap_fields, lightmap_texels, shadows, top_mip_rgb  # noqa: E402

LIT = 0.05                      # original flat light below this is too dark to judge a ratio by (EXP-17 run 6)
WITHIN = 0.15                   # |log2 ratio| under this: within about 10%
LOOSE = math.log2(1.4)          # within 40%
CUBE = 192.0                    # two tiles, the checkerboard of EXP-17 runs 6 and 7
BANDS = [(0.01, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.5), (0.5, None)]
PARTS = ('direct', 'emissive', 'bounce', 'environment')


def facing(nz):
    return np.where(nz > 0.7, 'floor', np.where(nz < -0.7, 'ceiling', 'wall'))


def part_coefficients(scene, active, geo, parts=False):
    """Our light at the texels of `geo` as relight.model_coefficients gives it; with `parts`, a dict of each source's
    coefficients (they sum to the total) instead."""
    if not parts:
        return {'total': relight.model_coefficients(scene, active, geo)[0]}
    world, frames = geo['world'], geo['frames']

    def direct(lights):
        return codec.coefficients(lights, world, frames, visibility=lambda light, lit: shadows.light_visibility(
            scene.occluder, light, world[lit], frames[lit, 2], samples=scene.samples, seed=shadows.light_seed(light),
            level_scale=scene.level_scale))
    out = {'direct': direct([l for l in active if scene.keeps(l)]),
           'emissive': direct(scene.area_lights) if scene.emissive else np.zeros((len(world), 3, 3))}
    zero = np.zeros((len(world), 3, 3))
    out['bounce'], out['environment'] = zero, zero
    if scene.bounce_rays > 0:
        pick = bounce.gather_points(geo['px'], geo['py'], scene.stride)
        steps = np.linalg.norm(np.diff(world[np.lexsort((geo['px'], geo['py']))], axis=0), axis=1)
        texel = float(np.median(steps)) if len(steps) else 1.0
        sources = [('bounce', scene.lights, (0.0, 0.0, 0.0))]
        if parts == 'by-material':
            # the bounce as usual, and each material's share of it (the material of the surface the light bounced
            # off), so that its albedo can be fitted
            names, index = np.unique(scene.materials, return_inverse=True)
            g, split = bounce.gather(scene.occluder, scene.triangles, scene.albedo_per_triangle, scene.lights,
                                     world[pick], frames[pick], rays=scene.bounce_rays, seed=7,
                                     source=scene.source, groups=(index, len(names)))
            out['bounce'] = bounce.smooth(world[pick], frames[pick, 2], g, world, frames[:, 2],
                                          sigma=scene.stride * texel)
            out['split'] = bounce.smooth(world[pick], frames[pick, 2], split, world, frames[:, 2],
                                         sigma=scene.stride * texel).astype(np.float32)
            out['splitNames'] = names
            sources = []
        if parts == 'by-kind':
            # bounce split by the kind of light it starts from: placed point and spot lights, the emissive stand-ins
            sources = [(f'bounce_{k}', [l for l in scene.lights if kind_of(l) == k], (0.0, 0.0, 0.0))
                       for k in BOUNCE_KINDS]
        for key, lights, env in sources + [('environment', [], scene.environment)]:
            g = bounce.gather(scene.occluder, scene.triangles, scene.albedo_per_triangle, lights, world[pick],
                              frames[pick], rays=scene.bounce_rays, seed=7, environment=env,
                              source=scene.source if key == 'bounce' else None)
            out[key] = bounce.smooth(world[pick], frames[pick, 2], g, world, frames[:, 2],
                                     sigma=scene.stride * texel)
        if parts == 'by-kind':
            out['bounce'] = sum(out[f'bounce_{k}'] for k in BOUNCE_KINDS)
    return out


BOUNCE_KINDS = ('point', 'spot', 'area', 'directional')


def kind_of(light):
    return 'area' if light['role'] == 'area' else light['kind']


def measure(p, path, scene, parts=False):
    """One component's texels: the original's flat light, ours (and each source's with `parts`), world positions and
    normals' z. Raises ValueError for a component the relight would skip."""
    ci = p.by_name.get(path)
    if ci is None:
        raise ValueError(f'no export {path}')
    if p.own(ci, 'StaticLightingHiddenByDefault', False):
        raise ValueError(f'{path} is StaticLightingHiddenByDefault')
    rec = lighting.component_record(p, ci)
    lm = rec['lods'][0]['lightmap'] if rec['lods'] else None
    if not lm or lm['type'] != 2:
        raise ValueError(f'{path} has no LOD-0 texture lightmap')
    fields = lightmap_fields.component_fields(p, ci)['lods'][0]['lightmap']
    nac_tex, dmc_tex = (fields['slots'][k]['index'] for k in (0, 1))
    tex = lightmap_fields.texture_fields(p, dmc_tex)
    size = [tex['mips'][0]['width'], tex['mips'][0]['height']]
    active = [l for l in relight.component_lights(p, lm['lightGuids']) if l['enabled']]
    mesh = lightmap_texels.component_mesh(p, ci)
    geo = lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, ci), fields, size)
    inside = bounce.buried_texels(scene.occluder, geo['world'], geo['frames'], scene.level_scale)
    if inside.all():
        raise ValueError(f'all texels of {path} lie inside geometry')
    geo = dict(geo, **{k: geo[k][~inside] for k in ('px', 'py', 'world', 'frames', 'triangle')})
    x0, y0 = geo['rect'][:2]
    iy, ix = geo['py'] - y0, geo['px'] - x0
    orig = relight.flat_light(top_mip_rgb(p, nac_tex), top_mip_rgb(p, dmc_tex), fields['slots'][1]['scale'])
    coefs = part_coefficients(scene, active, geo, parts)
    split, split_names = coefs.pop('split', None), coefs.pop('splitNames', None)
    flat = {k: v.sum((1, 2)) for k, v in coefs.items()}
    if parts:
        flat['total'] = sum(flat[k] for k in PARTS)
    out = dict(component=path, mesh=mesh['mesh'], b=orig[y0:, x0:][iy, ix].sum(1), a=flat['total'],
               parts={k: v for k, v in flat.items() if k != 'total'}, world=geo['world'], nz=geo['frames'][:, 2, 2],
               buried=int(inside.sum()), ix=ix, iy=iy, shape=(geo['rect'][3] - y0, geo['rect'][2] - x0))
    if split is not None:
        out.update(split=split, splitNames=[p.name(int(m)) if m > 0 else str(int(m)) for m in split_names])
    return out


def preview(result, path):
    """original | ours | where they differ (blue: ours darker, red: ours brighter, white: within 10%; black: unlit),
    each texel of the component's rectangle, the light on one scale (the original's 99th percentile), gamma 2.2."""
    from PIL import Image
    h, w = result['shape']
    b, a = result['b'], result['a']
    top = np.percentile(b, 99) if len(b) else 1.0
    top = top if top > 0 else 1.0
    tiles = []
    for values in (b, a):
        img = np.zeros((h, w))
        img[result['iy'], result['ix']] = np.clip(values / top, 0, 1) ** (1 / 2.2)
        tiles.append(np.repeat(img[..., None], 3, -1))
    e = np.clip(log_ratio(a, b), -2, 2) / 2                         # -1 (ours a quarter) .. 1 (ours four times)
    near = np.abs(log_ratio(a, b)) < WITHIN
    colour = np.stack([1 - np.maximum(-e, 0), 1 - np.abs(e), 1 - np.maximum(e, 0)], -1)
    colour[near] = 1.0
    colour[b <= LIT] = 0.0
    diff = np.zeros((h, w, 3))
    diff[result['iy'], result['ix']] = colour
    gap = np.ones((h, 4, 3))
    out = np.concatenate([tiles[0], gap, tiles[1], gap, diff], 1)
    if result['parts']:
        # a second row: each source of ours (direct, emissive, bounce, environment) on the same scale
        row = []
        for k in PARTS:
            img = np.zeros((h, w))
            img[result['iy'], result['ix']] = np.clip(result['parts'][k] / top, 0, 1) ** (1 / 2.2)
            row += [np.repeat(img[..., None], 3, -1), gap]
        row = np.concatenate(row[:-1], 1)
        width = max(row.shape[1], out.shape[1])
        pad = lambda m: np.concatenate([m, np.ones((h, width - m.shape[1], 3))], 1)
        out = np.concatenate([pad(out), np.ones((4, width, 3)), pad(row)], 0)
    h = out.shape[0]
    scale = max(1, int(256 // max(h, 1)))
    Image.fromarray((out * 255).astype(np.uint8)).resize((out.shape[1] * scale, h * scale), Image.NEAREST).save(path)


_WORKER = {}


def components_box(p, paths, margin):
    """The world box around the components named (those that exist), grown by `margin`."""
    boxes, meshes = [], {}
    for path in paths:
        i = p.by_name.get(path)
        if i is not None:
            try:
                boxes.append(relight.component_box(p, i, meshes))
            except Exception:
                pass
    b = np.array(boxes)
    return [float(b[:, 0].min() - margin), float(b[:, 1].max() + margin), float(b[:, 2].min() - margin),
            float(b[:, 3].max() + margin), float(b[:, 4].min() - margin), float(b[:, 5].max() + margin)]


def _start(src, scene_args, parts, paths=(), source_margin=None):
    p = lighting.Package(Path(src))
    if source_margin is not None and scene_args.get('source_radius'):
        scene_args = dict(scene_args, source_box=components_box(p, paths, source_margin))
    _WORKER.update(p=p, scene=relight.Scene(p, **scene_args), parts=parts)


def _measure(path):
    try:
        return path, measure(_WORKER['p'], path, _WORKER['scene'], _WORKER['parts']), None
    except ValueError as error:
        return path, None, str(error)


def log_ratio(a, b):
    return np.log2(np.maximum(a, 1e-3) / np.maximum(b, 1e-3))


def summary(b, a):
    lit = b > LIT
    if not lit.any():
        return dict(texels=int(len(b)), lit=0)
    e = np.abs(log_ratio(a[lit], b[lit]))
    return dict(texels=int(len(b)), lit=int(lit.sum()), within10=float(np.mean(e < WITHIN)),
                within40=float(np.mean(e < LOOSE)), medianAbsLog2=float(np.median(e)),
                medianRatio=float(np.median(a[lit] / np.maximum(b[lit], 1e-9))),
                originalMedian=float(np.median(b[lit])), oursMedian=float(np.median(a[lit])))


def report(results, parts=False):
    b = np.concatenate([r['b'] for r in results])
    a = np.concatenate([r['a'] for r in results])
    face = np.concatenate([facing(r['nz']) for r in results])
    world = np.concatenate([r['world'] for r in results])
    comp = np.concatenate([np.full(len(r['b']), k) for k, r in enumerate(results)])
    out = dict(all=summary(b, a), byFacing={f: summary(b[face == f], a[face == f]) for f in ('floor', 'wall', 'ceiling')})
    bands = []
    for lo, hi in BANDS:
        m = (b >= lo) & (b < hi if hi else True)
        bands.append(dict(band=[lo, hi], share=float(m.mean()),
                          medianRatio=float(np.median(a[m] / b[m])) if m.any() else None))
    out['byBrightness'] = bands
    # the checkerboard: groups of (component, facing, cube), lit texels only
    lit = b > LIT
    if not lit.any():
        out.update(checker=dict(cube=CUBE, groups=0), components=[])
        return out
    cube =np.floor(world / CUBE).astype(np.int64)
    keys = np.stack([comp, np.searchsorted(['ceiling', 'floor', 'wall'], face), cube[:, 0], cube[:, 1], cube[:, 2]], 1)[lit]
    _, group, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    group = group.ravel()
    order = np.argsort(group, kind='stable')
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    bl, al = b[lit][order], a[lit][order]
    ratios = np.array([np.median(al[s:s + c]) / max(np.median(bl[s:s + c]), 1e-9) for s, c in zip(starts, counts)])
    err = np.abs(np.log2(np.maximum(ratios, 1e-3)))
    out['checker'] = dict(cube=CUBE, groups=int(len(counts)),
                          texelsWithin10=float(counts[err < WITHIN].sum() / counts.sum()),
                          texelsWithin40=float(counts[err < LOOSE].sum() / counts.sum()),
                          medianGroupRatio=float(np.exp2(np.median(np.log2(np.maximum(ratios, 1e-3))))))
    per = []
    total_err = 0.0
    for k, r in enumerate(results):
        s = summary(r['b'], r['a'])
        m = r['b'] > LIT
        load = float(np.abs(log_ratio(r['a'][m], r['b'][m])).sum()) if m.any() else 0.0
        total_err += load
        per.append(dict(component=r['component'].split('.', 2)[-1], mesh=r['mesh'].split('.')[-1], buried=r['buried'],
                        errorLoad=load, **s))
    for row in per:
        row['errorShare'] = row.pop('errorLoad') / max(total_err, 1e-9)
    out['components'] = sorted(per, key=lambda r: -r['errorShare'])
    if parts:
        shares = {}
        for f in ('floor', 'wall', 'ceiling'):
            m = (face == f) & lit
            ours = a[m].sum()
            shares[f] = {k: float(np.concatenate([r['parts'][k] for r in results])[m].sum() / max(ours, 1e-9))
                         for k in PARTS}
            shares[f]['originalOverOurs'] = float(b[m].sum() / max(ours, 1e-9))
        out['partShares'] = shares
    return out


def print_summary(rep):
    def line(name, s):
        if not s.get('lit'):
            return f'  {name:10} no lit texels'
        return (f'  {name:10} {s["lit"]:8} lit texels  within 10% {s["within10"]:6.1%}  within 40% {s["within40"]:6.1%}'
                f'  median |log2| {s["medianAbsLog2"]:.2f}  ours/original {s["medianRatio"]:.2f}')
    print(line('all', rep['all']))
    for f, s in rep['byFacing'].items():
        print(line(f, s))
    c = rep['checker']
    if not c['groups']:
        return
    print(f'  checker   {c["groups"]} groups of {c["cube"]:.0f}: texels in groups within 10% {c["texelsWithin10"]:.1%}, '
          f'within 40% {c["texelsWithin40"]:.1%}, median group ratio {c["medianGroupRatio"]:.2f}')
    print('  by brightness:', ', '.join(f'{lo}-{hi or "up"}: {bd["share"]:.0%} at {bd["medianRatio"] or 0:.2f}'
                                         for bd in rep['byBrightness'] for lo, hi in [bd['band']]))
    if 'partShares' in rep:
        for f, s in rep['partShares'].items():
            print(f'  {f:10} ' + '  '.join(f'{k} {v:.0%}' for k, v in s.items() if k != 'originalOverOurs')
                  + f'  original/ours {s["originalOverOurs"]:.2f}')
    print('  worst components:')
    for r in rep['components'][:12]:
        print(f'    {r["errorShare"]:5.1%}  {r["component"]:60} within 10% {r.get("within10", 0):5.1%}'
              f'  ours/original {r.get("medianRatio", 0):.2f}')


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('--component', action='append', default=[])
    a.add_argument('--component-list', type=Path)
    a.add_argument('--samples', type=int, default=64)
    a.add_argument('--bounce-rays', type=int, default=64)
    a.add_argument('--stride', type=int, default=2)
    a.add_argument('--source-radius', type=float,
                   help='bounce sources lit as a photon map sees them, over discs this wide (bounce.SourceIrradiance)')
    a.add_argument('--source-estimate', choices=('mean', 'density'), default='mean')
    a.add_argument('--source-per-disc', type=int, default=40)
    a.add_argument('--source-bounces', type=int, default=1,
                   help='with --source-radius: bounces the sources carry (2: the final gather gives two bounces)')
    a.add_argument('--source-margin', type=float, default=1024.0,
                   help='with --source-radius: sample the surface within this far of the components measured')
    a.add_argument('--no-emissive', action='store_true')
    a.add_argument('--parts', action='store_true', help='split our light into its sources')
    a.add_argument('--bounce-by-kind', action='store_true',
                   help='with --parts, also split the bounce by the kind of light it starts from (point, spot, '
                        'the emissive stand-ins, directional); one gather per kind')
    a.add_argument('--bounce-by-material', action='store_true',
                   help='with --parts and --texels, also save each material\'s share of the bounce (the surface it '
                        'bounced off), for fitting albedos')
    a.add_argument('--jobs', type=int, default=relight.default_jobs())
    a.add_argument('--out', type=Path)
    a.add_argument('--previews', type=Path, metavar='DIR',
                   help='write <component>.png per component: original | ours | where they differ')
    a.add_argument('--texels', type=Path, metavar='NPZ',
                   help='save every texel (original, ours, our sources, normal z, position, component) for fitting')
    args = a.parse_args()
    paths = list(args.component)
    if args.component_list:
        for line in args.component_list.read_text().splitlines():
            line = line.split('#')[0].strip()
            if line:
                paths.append(line)
    if not paths:
        a.error('name components with --component or --component-list')
    scene_args = dict(samples=args.samples, bounce_rays=args.bounce_rays, stride=args.stride,
                      emissive=not args.no_emissive, source_radius=args.source_radius,
                      source_estimate=args.source_estimate, source_per_disc=args.source_per_disc,
                      source_bounces=args.source_bounces)
    started = time.monotonic()
    results, skipped = [], {}
    parts = (('by-kind' if args.bounce_by_kind else 'by-material' if args.bounce_by_material else True)
             if args.parts else False)
    with ProcessPoolExecutor(args.jobs, initializer=_start,
                             initargs=(str(args.src), scene_args, parts, paths, args.source_margin)) as pool:
        for k, (path, result, error) in enumerate(pool.map(_measure, paths), 1):
            if error:
                skipped[path] = error
            else:
                results.append(result)
                if args.previews:
                    args.previews.mkdir(parents=True, exist_ok=True)
                    preview(result, args.previews / (path.split('.', 2)[-1].replace('.', '-') + '.png'))
            print(f'progress: components {k}/{len(paths)}', flush=True)
    if not results:
        sys.exit('nothing measured: ' + json.dumps(skipped))
    rep = report(results, args.parts)
    rep = dict(source=str(args.src), measured=len(results), skipped=skipped, model=scene_args,
               seconds=round(time.monotonic() - started), **rep)
    print_summary(rep)
    if args.texels:
        args.texels.parent.mkdir(parents=True, exist_ok=True)
        cat = lambda key: np.concatenate([r[key] for r in results])
        np.savez_compressed(args.texels, b=cat('b'), a=cat('a'), nz=cat('nz'), world=cat('world'),
                            component=np.concatenate([np.full(len(r['b']), k) for k, r in enumerate(results)]),
                            names=np.array([r['component'] for r in results]),
                            **({f'part_{k}': np.concatenate([r['parts'][k] for r in results])
                                for k in results[0]['parts']} if args.parts else {}),
                            **({} if 'split' not in results[0] else dict(
                                split=np.concatenate([r['split'] for r in results]),
                                split_names=np.array(results[0]['splitNames']))))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rep, indent=1) + '\n', newline='\n')
        print('report', args.out)


if __name__ == '__main__':
    main()
