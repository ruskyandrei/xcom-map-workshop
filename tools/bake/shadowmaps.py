"""Dominant-light shadow maps (baker plan step L3, gate C4).

A map's dominant light (the bar's moon, `DominantDirectionalLight`) is drawn live, not baked into the lightmaps. What
shadows it on static surfaces is a per-component shadow map: a `ShadowMap2D` object on the component's LOD record
(texture, coordinate scale and bias into the texture's atlas, the light's `LightGuid`), whose texture is an 8-bit
(G8) signed distance field: 1 well inside the light, 0 well inside the shadow, 0.5 on the shadow's edge, linear in
between over the light's transition distance.

This module rebuilds such a field from our own scene: the component's texels in the shadow map's rectangle (the
lightmap UV channel, at `UPSAMPLE` x `UPSAMPLE` sub-samples per texel), one ray each toward the light, then each
sub-sample's distance (world units) to the nearest sub-sample on the other side of the shadow's edge, signed and
scaled into the field, averaged per texel.

  python -B tools/bake/shadowmaps.py gate <map.upk> <component> [<component> ...] [--out DIR]

compares the field rebuilt for unedited components with the map's own (the gate: is the model and encoding right?).
"""
import argparse
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relight  # noqa: E402  (sets up the tool paths)
import audit_lighting as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_texels  # noqa: E402
import shadows  # noqa: E402
from export_math import forward  # noqa: E402
from texture import decompress_payload  # noqa: E402

UPSAMPLE = 4             # sub-samples per texel side
TRANSITION = 25.0        # world units from the edge to a field value of 0 or 1 (the gate: the bar's asphalt)
DOMINANT = ('DominantDirectionalLightComponent',)
MAX_REACH = 48           # the widest search window, in sub-samples each way


def guid_hex(raw):
    return raw.hex() if isinstance(raw, (bytes, bytearray)) else None


def dominant_lights(p):
    """{LightGuid hex: light} for the map's dominant directional lights: component, actor and `toLight` (unit vector
    toward the light)."""
    out = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in DOMINANT or not p.name(i).startswith('TheWorld.PersistentLevel.'):
            continue
        actor = p.exports[i - 1]['outer']
        rotation = p.effective(actor, 'Rotation', [-16384, 0, 0])
        to_light = [-v for v in forward(rotation)]
        out[guid_hex(p.own(i, 'LightGuid'))] = dict(component=p.name(i), actor=p.name(actor), toLight=to_light,
                                                    enabled=bool(p.effective(i, 'bEnabled', True)))
    return out


def shadow_maps(p, ci):
    """The component's LOD-0 shadow maps: dicts of export, texture (export index), scale, bias, guid, factor (True
    for a plain shadow-factor texture, False for a distance field)."""
    f = lightmap_fields.component_fields(p, ci)
    out = []
    for ref in (f['lods'][0]['shadowMaps'] if f['lods'] else []):
        if ref <= 0:
            continue
        out.append(dict(export=ref, path=p.name(ref), texture=p.own(ref, 'Texture'),
                        scale=list(struct.unpack('<2f', p.own(ref, 'CoordinateScale'))),
                        bias=list(struct.unpack('<2f', p.own(ref, 'CoordinateBias'))),
                        guid=guid_hex(p.own(ref, 'LightGuid')), factor=bool(p.own(ref, 'bIsShadowFactorTexture', False))))
    return out


def texture_top(p, index):
    """The shadow map texture's top mip as a uint8 (h, w) array, and its fields."""
    t = lightmap_fields.texture_fields(p, index)
    m = t['mips'][0]
    if m['inline']:
        raw = bytes(p.data[m['payloadOffset']:m['payloadOffset'] + m['bytes']])
    else:
        with lighting.cache_file(p.path.parent, t['cache']).open('rb') as fh:
            fh.seek(m['offset'])
            raw = decompress_payload(fh.read(m['bytes']), m['flags'])
    if len(raw) != m['width'] * m['height']:
        raise ValueError(f'{t["path"]} is not one byte per texel')
    return np.frombuffer(raw, np.uint8).reshape(m['height'], m['width']), t


def sub_samples(p, ci, sm, size, upsample=UPSAMPLE, mesh=None):
    """The component's surface at `upsample` x `upsample` points per shadow-map texel: lightmap_texels.rasterise on
    the atlas at that many times its size."""
    mesh = mesh or lightmap_texels.component_mesh(p, ci)
    record = dict(coordinateScale=sm['scale'], coordinateBias=sm['bias'])
    geo = lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, ci), record,
                                    [size[0] * upsample, size[1] * upsample])
    return geo


def lit(occluder, to_light, geo, level_scale=1.0):
    """True where a sub-sample sees the light: one ray from just off the surface toward it."""
    world, normals = geo['world'], geo['frames'][:, 2]
    origin = world + shadows.NORMAL_OFFSET * level_scale * normals
    to = np.asarray(to_light, float)
    start = origin + shadows.RAY_OFFSET * level_scale * to
    return ~occluder.blocked(start, origin + to * shadows.FAR)


def grid(geo):
    """The sub-samples of `geo` laid out on their grid: covered (H, W) bool, world (H, W, 3) (NaN where uncovered),
    the grid indices of geo's points, and the world spacing along each grid axis (texels can be stretched: a road
    marking's are long)."""
    x0, y0, x1, y1 = geo['rect']
    H, W = y1 - y0, x1 - x0
    covered = np.zeros((H, W), bool)
    iy, ix = geo['py'] - y0, geo['px'] - x0
    covered[iy, ix] = True
    world = np.full((H, W, 3), np.nan)
    world[iy, ix] = geo['world']
    spacing = []
    for axis in (0, 1):
        steps = np.linalg.norm(np.diff(world, axis=axis), axis=2).ravel()
        steps = steps[np.isfinite(steps) & (steps > 1e-6)]
        spacing.append(float(np.median(steps)) if len(steps) else 1.0)
    return dict(shape=(H, W), covered=covered, world=world, iy=iy, ix=ix, spacing=spacing)


def reach_of(g, transition=TRANSITION):
    """The search window's half width in grid cells: it reaches `transition` along the finer axis."""
    return min(int(math.ceil(transition / max(min(g['spacing']), 1e-3))) + 1, MAX_REACH)


def signed_distance(g, light, transition=TRANSITION, only=None):
    """(H, W) signed world distance from each covered sub-sample to the shadow's edge, positive in the light, at most
    2 x `transition` either way: the nearest covered sub-sample on the other side, searched within a window of the
    grid reaching `transition` (by world distance, so that UV islands packed side by side, as a road marking's dashes
    are, don't see each other), less the half step before it (the edge lies halfway between the last sub-sample on
    one side and the first on the other). With `only` (H, W bool), sub-samples outside it are left at the ends."""
    from scipy import ndimage
    covered, world = g['covered'], g['world']
    H, W = g['shape']
    reach = reach_of(g, transition)
    shadowed, lit_ = covered & ~light, covered & light
    box = np.ones((2 * reach + 1, 2 * reach + 1), bool)
    near_shadow = ndimage.binary_dilation(shadowed, box) if shadowed.any() else np.zeros_like(covered)
    near_light = ndimage.binary_dilation(lit_, box) if lit_.any() else np.zeros_like(covered)
    todo = (lit_ & near_shadow) | (shadowed & near_light)
    if only is not None:
        todo &= only
    ty, tx = np.nonzero(todo)
    best = np.full(len(ty), np.inf)
    best_steps = np.ones(len(ty))
    if len(ty):
        tw = world[ty, tx]
        mine = light[ty, tx]
        pad = reach
        cov_p = np.pad(covered, pad)
        light_p = np.pad(light, pad)
        world_p = np.pad(world, ((pad, pad), (pad, pad), (0, 0)), constant_values=np.nan)
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                if not dy and not dx:
                    continue
                oy, ox = ty + dy + pad, tx + dx + pad
                other = cov_p[oy, ox] & (light_p[oy, ox] != mine)
                if not other.any():
                    continue
                dist = np.where(other, np.linalg.norm(world_p[oy, ox] - tw, axis=1), np.inf)
                closer = dist < best
                best[closer] = dist[closer]
                best_steps[closer] = max(abs(dy), abs(dx))
    d = np.full((H, W), 2 * transition)
    d[ty, tx] = np.minimum(best * (1 - 1 / (2 * best_steps)), 2 * transition)
    return np.where(light, d, -d)


def encode(d, transition=TRANSITION):
    """Field values in [0, 1] from signed distances: 0.5 on the edge, 1 at `transition` into the light."""
    return np.clip(0.5 + d / (2 * transition), 0, 1)


def texel_means(values, covered, upsample=UPSAMPLE):
    """Per texel: the mean of `values` over its covered sub-samples; and which texels have any."""
    H, W = values.shape
    h, w = -(-H // upsample), -(-W // upsample)
    v = np.zeros((h * upsample, w * upsample))
    c = np.zeros((h * upsample, w * upsample))
    v[:H, :W] = np.where(covered, values, 0)
    c[:H, :W] = covered
    count = c.reshape(h, upsample, w, upsample).sum((1, 3))
    total = v.reshape(h, upsample, w, upsample).sum((1, 3))
    return total / np.maximum(count, 1), count > 0


def light_grid(g, seen):
    light = np.zeros(g['shape'], bool)
    light[g['iy'], g['ix']] = seen
    return light


def field(geo, seen, size, upsample=UPSAMPLE, transition=TRANSITION):
    """The whole distance field per texel of the shadow map's rectangle: (values (h, w) in [0, 1], covered (h, w),
    the sub-sample spacing). A texel's value is the mean of its covered sub-samples' encoded distances."""
    g = grid(geo)
    values, covered = texel_means(encode(signed_distance(g, light_grid(g, seen), transition), transition),
                                  g['covered'], upsample)
    return values, covered, g['spacing']


def change(geo, seen_before, seen_after, upsample=UPSAMPLE, transition=TRANSITION):
    """What an edit changes in the field, per texel: None when no sub-sample's view of the light changes, else
    (delta (h, w): after minus before, covered (h, w), sub-samples changed). Only the sub-samples within the search
    window of a changed one can differ, so only those are measured."""
    from scipy import ndimage
    if np.array_equal(seen_before, seen_after):
        return None
    g = grid(geo)
    before, after = light_grid(g, seen_before), light_grid(g, seen_after)
    flipped = g['covered'] & (before != after)
    reach = reach_of(g, transition)
    region = ndimage.binary_dilation(flipped, np.ones((2 * reach + 1, 2 * reach + 1), bool))
    vb = encode(signed_distance(g, before, transition, region), transition)
    va = encode(signed_distance(g, after, transition, region), transition)
    diff = np.where(region & g['covered'], va - vb, 0.0)
    delta, covered = texel_means(diff, g['covered'], upsample)
    return delta, covered, int(flipped.sum())


def dominant_receivers(p, lights):
    """Every persistent-level mesh component with a shadow map of one of the dominant `lights`: (path, export,
    shadow map, light). A component with no static mesh in the package is left out: it draws no surface to relight
    (DLC1_1_LowFriends' XComLevelActor_16.StaticMeshComponent_166 names no mesh and keeps a shadow map, T-28)."""
    out = []
    for i in range(1, len(p.exports) + 1):
        if not p.cls(i).endswith('StaticMeshComponent') or not p.name(i).startswith('TheWorld.PersistentLevel.'):
            continue
        if p.effective(i, 'StaticMesh', 0) <= 0:
            continue
        try:
            maps = shadow_maps(p, i)
        except Exception:       # a component whose fields don't parse carries no shadow map we can write
            continue
        for sm in maps:
            if sm['guid'] in lights and not sm['factor']:
                out.append((p.name(i), i, sm, lights[sm['guid']]))
    return out


def relight_shadow_map(p, ci, sm, light, before, after, level_scale=1.0, transition=TRANSITION, tops=None,
                       source=None):
    """One shadow map after an edit: the original field plus what the edit changes in ours (so that where it changes
    nothing, the map's own field stays exactly). `before` and `after` are the scenes' occluders. Returns None when the
    edit changes no sub-sample's view of the light, else dict(texture (export), x0, y0, values (h, w) in [0, 1],
    mask (h, w): the texels to write, original (h, w), report). `tops` caches decoded textures by export (many
    components share one atlas).

    A native copy (native_copy.py) gives `source`, (component export, shadow map) of the piece it copies: its cloned
    texture holds the source's field, so before is the source where it stands, and after is the copy where it stands.
    The two share the mesh and the shadow map's layout, so each sub-sample is the same point of the piece."""
    from scipy import ndimage
    tops = {} if tops is None else tops
    if sm['texture'] not in tops:
        tops[sm['texture']] = texture_top(p, sm['texture'])
    top, t = tops[sm['texture']]
    size = [t['mips'][0]['width'], t['mips'][0]['height']]
    geo = sub_samples(p, ci, sm, size)
    geo_b = geo
    if source is not None:
        si, ssm = source
        if (ssm['scale'], ssm['bias']) != (sm['scale'], sm['bias']):
            raise ValueError(f'{p.name(ci)}: its shadow map is not laid out as its source\'s')
        geo_b = sub_samples(p, si, ssm, size)
        if not (np.array_equal(geo_b['px'], geo['px']) and np.array_equal(geo_b['py'], geo['py'])):
            raise ValueError(f'{p.name(ci)}: its sub-samples are not its source\'s')
    seen_b = lit(before, light['toLight'], geo_b, level_scale)
    seen_a = lit(after, light['toLight'], geo, level_scale)
    got = change(geo, seen_b, seen_a, transition=transition)
    if got is None:
        return None
    delta, covered, flipped = got
    x0, y0 = geo['rect'][0] // UPSAMPLE, geo['rect'][1] // UPSAMPLE
    h, w = delta.shape
    h, w = min(h, size[1] - y0), min(w, size[0] - x0)
    delta, covered = delta[:h, :w], covered[:h, :w]
    # the uncovered texels around the component's islands carry its field too (the bake pads them, and the game's
    # filtering reads them at the islands' edges): those within 2 texels take their nearest covered texel's change
    if (~covered).any() and covered.any():
        dist, idx = ndimage.distance_transform_edt(~covered, return_indices=True)
        pad = (~covered) & (dist <= 2)
        delta = np.where(pad, delta[idx[0], idx[1]], delta)
        covered = covered | pad
    original = top[y0:y0 + h, x0:x0 + w] / 255.0
    values = np.clip(original + delta, 0, 1)
    mask = covered & (np.abs(np.round(values * 255) - top[y0:y0 + h, x0:x0 + w]) >= 1)
    if not mask.any():
        return None
    report = dict(component=p.name(ci), shadowMap=sm['path'], texture=t['path'], light=light['component'],
                  rect=[x0, y0, x0 + w, y0 + h], atlas=size, subSamplesChanged=flipped,
                  texelsWritten=int(mask.sum()), darker=int((mask & (delta < 0)).sum()),
                  lighter=int((mask & (delta > 0)).sum()), transition=transition,
                  copyOf=p.name(source[0]) if source is not None else None)
    return dict(texture=sm['texture'], x0=x0, y0=y0, values=values, mask=mask, original=original, report=report)


def fresh_shadow_map(p, ci, sm, light, after, level_scale=1.0, transition=TRANSITION, tops=None):
    """The whole field of one shadow map, from nothing: for a piece brought from another map, whose texture holds
    its home map's field (relight.py --foreign-copy). `after` is the occluder of the scene after the edit. Returns
    relight_shadow_map's dict; every covered texel is written, and the uncovered ones within 2 texels take their
    nearest covered texel's value."""
    from scipy import ndimage
    tops = {} if tops is None else tops
    if sm['texture'] not in tops:
        tops[sm['texture']] = texture_top(p, sm['texture'])
    top, t = tops[sm['texture']]
    size = [t['mips'][0]['width'], t['mips'][0]['height']]
    geo = sub_samples(p, ci, sm, size)
    seen = lit(after, light['toLight'], geo, level_scale)
    values, covered, _ = field(geo, seen, size, transition=transition)
    x0, y0 = geo['rect'][0] // UPSAMPLE, geo['rect'][1] // UPSAMPLE
    h, w = values.shape
    h, w = min(h, size[1] - y0), min(w, size[0] - x0)
    values, covered = values[:h, :w], covered[:h, :w]
    if not covered.any():
        return None
    if (~covered).any():
        dist, idx = ndimage.distance_transform_edt(~covered, return_indices=True)
        pad = (~covered) & (dist <= 2)
        values = np.where(pad, values[idx[0], idx[1]], values)
        covered = covered | pad
    original = top[y0:y0 + h, x0:x0 + w] / 255.0
    values = np.clip(values, 0, 1)
    report = dict(component=p.name(ci), shadowMap=sm['path'], texture=t['path'], light=light['component'],
                  rect=[x0, y0, x0 + w, y0 + h], atlas=size, subSamplesChanged=int(len(seen)),
                  texelsWritten=int(covered.sum()), darker=int((covered & (values < 0.5)).sum()),
                  lighter=int((covered & (values >= 0.5)).sum()), litShare=round(float(seen.mean()), 3),
                  transition=transition, copyOf=None, fresh=True)
    return dict(texture=sm['texture'], x0=x0, y0=y0, values=values, mask=covered, original=original, report=report)


def gate(src, components, out=None, transitions=(25.0, 50.0, 75.0, 100.0)):
    p = lighting.Package(src)
    scene = relight.Scene(p, samples=1, bounce_rays=0, emissive=False)
    lights = dominant_lights(p)
    results = []
    for path in components:
        ci = p.by_name[path]
        for sm in shadow_maps(p, ci):
            light = lights.get(sm['guid'])
            if light is None:
                results.append(dict(component=path, shadowMap=sm['path'], note='not a dominant light\'s'))
                continue
            top, t = texture_top(p, sm['texture'])
            size = [t['mips'][0]['width'], t['mips'][0]['height']]
            geo = sub_samples(p, ci, sm, size)
            seen = lit(scene.occluder, light['toLight'], geo, scene.level_scale)
            x0, y0 = int(math.floor(sm['bias'][0] * size[0] + 1e-6)), int(math.floor(sm['bias'][1] * size[1] + 1e-6))
            row = dict(component=path, shadowMap=sm['path'], texture=t['path'], rect=geo['rect'],
                       litShare=round(float(seen.mean()), 3), byTransition={})
            for tr in transitions:
                values, covered, spacing = field(geo, seen, size, transition=tr)
                gx0, gy0 = geo['rect'][0] // UPSAMPLE, geo['rect'][1] // UPSAMPLE
                orig = top[gy0:gy0 + values.shape[0], gx0:gx0 + values.shape[1]] / 255.0
                ok = covered[:orig.shape[0], :orig.shape[1]]
                diff = np.abs(values[:orig.shape[0], :orig.shape[1]] - orig)[ok]
                ramp = ok & (orig > 0.02) & (orig < 0.98)
                rdiff = np.abs(values[:orig.shape[0], :orig.shape[1]] - orig)[ramp]
                side = (values[:orig.shape[0], :orig.shape[1]] > 0.5) == (orig > 0.5)
                row['byTransition'][tr] = dict(sameSide=round(float(side[ok].mean()), 4),
                                               meanAbs=round(float(diff.mean()), 4),
                                               within01=round(float((diff < 0.1).mean()), 4),
                                               rampTexels=int(ramp.sum()),
                                               rampMeanAbs=round(float(rdiff.mean()), 4) if len(rdiff) else None)
                row['subSampleSpacing'] = [round(v, 3) for v in spacing]
                if out and tr == transitions[0]:
                    from PIL import Image
                    out.mkdir(parents=True, exist_ok=True)
                    a = (np.nan_to_num(values[:orig.shape[0], :orig.shape[1]]) * 255).astype(np.uint8)
                    b = (orig * 255).astype(np.uint8)
                    pic = np.concatenate([b, np.full((b.shape[0], 2), 128, np.uint8), a], 1)
                    Image.fromarray(pic).resize((pic.shape[1] * 3, pic.shape[0] * 3), Image.NEAREST).save(
                        out / f'{path.split(".")[-2]}-{sm["path"].split(".")[-1]}.png')
            results.append(row)
            print(json.dumps(row))
    return results


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = a.add_subparsers(dest='action', required=True)
    g = sub.add_parser('gate')
    g.add_argument('src', type=Path)
    g.add_argument('components', nargs='+')
    g.add_argument('--out', type=Path)
    args = a.parse_args()
    if args.action == 'gate':
        gate(args.src, args.components, args.out)


if __name__ == '__main__':
    main()
