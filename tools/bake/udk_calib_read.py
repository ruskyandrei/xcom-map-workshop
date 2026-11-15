"""Reads what UDK Lightmass wrote for each receiver of a calibration scene (baker design, section 4.7).

For every receiver in <scene.json> (from `udk_calib_scene.py`), finds its component in the baked .udk, decodes the
top mip of its three lightmap textures (`NormalizedAverageColor`, `DirectionalMaxComponent`, `SimpleLightmap`) and
takes the median texel over the middle of the floor's top face. It pairs that with the light's direction in the
top face's tangent space (tangent +X, binormal -Y, normal +Z of the template floor, turned with the actor).

  python -B tools/bake/udk_calib_read.py <baked.udk> <scene.json> [--out result.json] [--texels texels.npz]

--texels also writes every texel of each receiver's top face (its world position, the face's tangent frame and the
decoded texels of the three textures, with the slot scales), for lights whose effect varies over the face (point and
spot lights). Read-only; the result holds numbers only.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(ROOT / 'bake'))
import audit_lighting as lighting  # noqa: E402
from lightmap_stats import top_mip_rgb  # noqa: E402

# The middle of the template floor's top face in its lightmap UVs (channel 1 spans u 0.003-0.813, v 0.187-0.997 on
# the top face), kept well away from its edges and from the sides' charts.
TOP_U = (0.15, 0.66)
TOP_V = (0.34, 0.85)
# The whole top face in the same UVs, and its lightmap UV as an affine map of local position (u = a + b x + c y), a
# least-squares fit over the face's 100 vertices in UDK's Engine/Content/MapTemplates.upk (residual 2e-4, the UVs'
# storage precision). The face lies at local z = 0.
TOP_FACE_U = (0.003, 0.813)
TOP_FACE_V = (0.1865, 0.9966)
TOP_UV_FROM_LOCAL = ((0.423528611, 1.97701762e-4, 0.0), (0.597998675, 0.0, -1.97745446e-4))


def tangent_frame(axes):
    """World tangent, binormal and normal of the template floor's top face for an actor with these axes."""
    x, y, z = (np.array(a, float) for a in axes)
    return x, -y, z


def receiver_component(p, rec):
    """The receiver's StaticMeshComponent: by the actor name the T3D gave it, else by the actor's Tag."""
    want = f"TheWorld.PersistentLevel.{rec['actor']}"
    comps = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'StaticMeshComponent'
             and p.name(i).startswith('TheWorld.PersistentLevel.')]
    for i in comps:
        if p.name(i).rsplit('.', 1)[0] == want:
            return i
    for i in comps:
        owner = p.exports[i - 1]['outer']
        if owner > 0 and p.effective(owner, 'Tag') == rec['name']:
            return i
    raise KeyError(f"no component for receiver {rec['name']} ({rec['actor']})")


def top_face_texels(lm, rec, size, margin=1.5):
    """Atlas pixels (x, y) whose centres lie on the receiver's top face at least `margin` texels inside it, with the
    centres' world positions. `size` is the atlas texture's [width, height]."""
    width, height = size
    sx, sy = lm['coordinateScale']; bx, by = lm['coordinateBias']
    (au, bu, cu), (av, bv, cv) = TOP_UV_FROM_LOCAL
    du, dv = margin / (sx * width), margin / (sy * height)
    x0, x1 = (bx + sx * u for u in (TOP_FACE_U[0] + du, TOP_FACE_U[1] - du))
    y0, y1 = (by + sy * v for v in (TOP_FACE_V[0] + dv, TOP_FACE_V[1] - dv))
    xs = np.arange(int(np.ceil(x0 * width - 0.5)), int(np.floor(x1 * width - 0.5)) + 1)
    ys = np.arange(int(np.ceil(y0 * height - 0.5)), int(np.floor(y1 * height - 0.5)) + 1)
    px, py = np.meshgrid(xs, ys)
    u = ((px + 0.5) / width - bx) / sx
    v = ((py + 0.5) / height - by) / sy
    # invert the affine map (the fit has no cross terms worth keeping: c_u and b_v are below 1e-11)
    lx = (u - au) / bu
    ly = (v - av) / cv
    axes = np.array(rec['axes'], float)
    world = np.array(rec['location'], float) + rec['scale'] * (lx[..., None] * axes[0] + ly[..., None] * axes[1])
    return px.ravel(), py.ravel(), world.reshape(-1, 3)


def lightmass_settings(p):
    """The saved WorldInfo's explicit LightmassSettings members (tagged struct: name, type, size, index, value)."""
    wi = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'WorldInfo']
    raw = p.own(wi[0], 'LightmassSettings') if wi else None
    out, pos = {}, 0
    while isinstance(raw, bytes) and pos + 24 <= len(raw):
        name = p.names[struct.unpack_from('<i', raw, pos)[0]]
        if name == 'None':
            break
        kind = p.names[struct.unpack_from('<i', raw, pos + 8)[0]]
        size = struct.unpack_from('<i', raw, pos + 16)[0]
        pos += 24
        if kind == 'StructProperty':
            pos += 8
        if kind == 'BoolProperty':
            out[name] = bool(raw[pos]); pos += 1
            continue
        value = raw[pos:pos + size]; pos += size
        if kind == 'FloatProperty':
            out[name] = struct.unpack('<f', value)[0]
        elif kind == 'IntProperty':
            out[name] = struct.unpack('<i', value)[0]
        elif name == 'EnvironmentColor' and size == 4:
            b, g, r, a = value
            out[name] = dict(R=r, G=g, B=b, A=a)
        else:
            out[name] = value.hex()
    return out


def read(udk, scene, texels=None):
    """(saved Lightmass settings, one row per receiver). With `texels` (a dict), also fills it with each receiver's
    top-face texels: '<name>/world', '/px', '/py', '/nac', '/dmc', '/simple' (decoded 0-1 values), '/scales' (the
    three slots' scales) and '/frame' (tangent, binormal, normal)."""
    p = lighting.Package(Path(udk))
    if p.header['lic'] != 0:
        raise ValueError('expected a UDK (licensee 0) package')
    cache = {}

    def tex(i):
        if i not in cache:
            cache[i] = top_mip_rgb(p, i)
        return cache[i]

    to_light = np.array(scene['light']['toLight'], float) if scene.get('light') else None
    all_lights = [np.array(lt['toLight'], float) for lt in scene.get('lights', [scene['light']] if scene.get('light')
                                                                      else [])]
    out = []
    for rec in scene['receivers']:
        ci = receiver_component(p, rec)
        lods = lighting.component_record(p, ci)['lods']
        lm = lods[0]['lightmap'] if lods else {'type': 0}
        row = dict(name=rec['name'], component=p.name(ci), lightmapType=lm['type'])
        t, b, n = tangent_frame(rec['axes'])
        if to_light is not None:
            row['toLightTangent'] = [round(float(to_light @ v), 6) for v in (t, b, n)]
        if len(all_lights) > 1:
            row['toLightTangents'] = [[round(float(lt @ v), 6) for v in (t, b, n)] for lt in all_lights]
        if lm['type'] != 2:
            out.append(row)
            continue
        size = None
        summary = []
        for slot in lm['slots']:
            if slot['index'] <= 0:
                summary.append(None)
                continue
            img = tex(slot['index'])
            height, width = img.shape[:2]   # UDK packs small lightmaps into non-square textures (128 x 64)
            size = [width, height]
            sx, sy = lm['coordinateScale']; bx, by = lm['coordinateBias']
            x0, x1 = (int(np.ceil((bx + sx * u) * width)) for u in TOP_U)
            y0, y1 = (int(np.ceil((by + sy * v) * height)) for v in TOP_V)
            block = img[y0:y1, x0:x1].reshape(-1, 3)
            summary.append(dict(median=np.median(block, 0).round(5).tolist(), min=block.min(0).round(5).tolist(),
                                max=block.max(0).round(5).tolist(), count=len(block)))
        row['slots'] = [dict(texture=s['texture'], scale=[round(v, 6) for v in s['scale']], texels=tx)
                        for s, tx in zip(lm['slots'], summary)]
        row['atlas'] = dict(size=size, coordinateScale=lm['coordinateScale'], coordinateBias=lm['coordinateBias'])
        row['lightGuids'] = lm['lightGuids']
        if texels is not None:
            px, py, world = top_face_texels(lm, rec, size)
            key = rec['name']
            texels[f'{key}/world'] = world
            texels[f'{key}/px'], texels[f'{key}/py'] = px, py
            for name, slot in zip(('nac', 'dmc', 'simple'), lm['slots']):
                texels[f'{key}/{name}'] = tex(slot['index'])[py, px] if slot['index'] > 0 else np.zeros((len(px), 3))
            texels[f'{key}/scales'] = np.array([s['scale'] for s in lm['slots']], float)
            texels[f'{key}/frame'] = np.array([t, b, n])
        out.append(row)
    return lightmass_settings(p), out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('udk', type=Path)
    a.add_argument('scene', type=Path)
    a.add_argument('--out', type=Path)
    a.add_argument('--texels', type=Path, help='write every top-face texel of each receiver to this .npz')
    args = a.parse_args()
    scene = json.loads(args.scene.read_text(encoding='utf-8'))
    texels = {} if args.texels else None
    settings, rows = read(args.udk, scene, texels)
    if args.texels:
        np.savez_compressed(args.texels, **texels)
    print('saved WorldInfo LightmassSettings (explicit members):', settings)
    for r in rows:
        line = f"{r['name']:10s} L_ts {r.get('toLightTangent')}"
        if 'slots' in r:
            nac, dmc, sim = (s['texels']['median'] if s['texels'] else None for s in r['slots'])
            line += f"  NAC {nac}  DMC {dmc} x {r['slots'][1]['scale']}  simple {sim} x {r['slots'][2]['scale'][0]}"
        else:
            line += f"  lightmap type {r['lightmapType']}"
        print(line)
    if args.out:
        args.out.write_text(json.dumps(dict(udk=str(args.udk), scene=str(args.scene), lightmassSettings=settings,
                                            receivers=rows), indent=1) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
