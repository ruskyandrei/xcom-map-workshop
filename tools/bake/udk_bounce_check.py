"""Compare our direct and bounce light with a UDK Lightmass calibration bake, texel by texel (EXP-18, bounce).

The scene is rebuilt from the calibration manifest (`udk_calib_scene.py`'s scene.json): UDK's template floor
(`MapTemplates.SM_Template_Map_Floor`) at each receiver's transform, every triangle with DefaultMaterial's albedo
(the sRGB-decoded mean of `EngineMaterials.DefaultDiffuse`, as `albedo.py` computes albedo), and the manifest's
directional, point and spot lights. For each receiver's top-face texels (`udk_calib_read.py --texels`) it computes
our shadowed direct light (`shadows.py`, `lightmap_encode.py`) and our bounce (`bounce.py`), and reports UDK's
light, ours, and how UDK's light beyond our direct compares with our bounce, in bands of distance from the nearest
other receiver (for a floor beside a wall: distance from the wall).

  python -B tools/bake/udk_bounce_check.py <lab>\\bake-calib\\calib8\\scene.json <lab>\\bake-calib\\calib8\\texels.npz
      [--rays 256] [--stride 3] [--spot-cone-scale 2] [--environment 64,69,97] [--udk <udk>] [--out result.json]

--udk defaults to the udk setting (tools/viewer/settings.py).

`--environment` gives the base map's EnvironmentColor (`udk_calib_base.py --environment`): our bounce then includes
the rays that leave the scene, as the relight's does.

Values are the summed linear directional values (the largest colour channel of each, over the three channels).
UDK's calibration base map keeps UDK's default number of bounces, so far from the lit surfaces its light can exceed
our one bounce by its later bounces.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import albedo  # noqa: E402
import audit_lighting as lighting  # noqa: E402
import bounce  # noqa: E402
import lightmap_encode as codec  # noqa: E402
import shadows  # noqa: E402
from mesh import read_mesh  # noqa: E402

BANDS = [(0, 100), (100, 400), (400, 800), (800, 1300)]


def template_floor(udk):
    p = lighting.Package(udk / 'Engine' / 'Content' / 'MapTemplates.upk')
    mi = next(i for i in range(1, len(p.exports) + 1) if p.name(i).endswith('SM_Template_Map_Floor'))
    m = read_mesh(p, mi)
    pos = np.array(m['positions'], float).reshape(-1, 3)[:, [0, 2, 1]]      # glTF order to game space
    return pos, np.array(m['indices'], np.int64).reshape(-1, 3)


def default_albedo(udk):
    p = lighting.Package(udk / 'Engine' / 'Content' / 'EngineMaterials.upk')
    tex = next(i for i in range(1, len(p.exports) + 1) if p.name(i).split('.')[-1] == 'DefaultDiffuse')
    return albedo.texture_mean(p, tex)


def scene_triangles(manifest, pos, tri):
    """World triangles of every receiver (wound so Embree's normal points out, as shadows.py does) and the index of
    the receiver each belongs to."""
    out, owner = [], []
    for k, r in enumerate(manifest['receivers']):
        axes = np.array(r['axes'])                                       # rows: the actor's X, Y, Z in world
        t = ((pos * r['scale']) @ axes + np.array(r['location'], float))[tri]
        out.append(t[:, ::-1] if np.linalg.det(axes) > 0 else t)
        owner.append(np.full(len(t), k))
    return np.concatenate(out).astype(np.float32), np.concatenate(owner)


def manifest_lights(manifest):
    """Codec light dicts for the manifest's lights (colours from bytes to 0-1)."""
    def colour(l):
        return [c / 255 for c in l.get('color', [255, 255, 255])]
    lights = [dict(kind='directional', toLight=l['toLight'], brightness=float(l.get('brightness', 1.0)),
                   color=colour(l), lightSourceAngle=codec.UDK_DIRECTIONAL_SOURCE_ANGLE)
              for l in manifest.get('lights') or []]
    for l in manifest.get('pointLights') or []:
        lights.append(dict(kind='point', location=l['location'], radius=float(l.get('radius', 1024.0)),
                           falloffExponent=float(l.get('falloffExponent', 2.0)), brightness=float(l.get('brightness', 1.0)),
                           color=colour(l), lightSourceRadius=float(l.get('lightSourceRadius', codec.UDK_POINT_SOURCE_RADIUS))))
    for l in manifest.get('spotLights') or []:
        lights.append(dict(kind='spot', location=l['location'], direction=l['direction'],
                           radius=float(l.get('radius', 1024.0)), falloffExponent=float(l.get('falloffExponent', 2.0)),
                           innerConeAngle=float(l.get('innerConeAngle', 0.0)), outerConeAngle=float(l.get('outerConeAngle', 44.0)),
                           brightness=float(l.get('brightness', 1.0)), color=colour(l),
                           lightSourceRadius=float(l.get('lightSourceRadius', codec.UDK_POINT_SOURCE_RADIUS))))
    return lights


def check(manifest, texels, udk=None, rays=256, stride=3, spot_cone_scale=None, seed=3, environment=(0.0, 0.0, 0.0),
          source_radius=None):
    if udk is None:
        sys.path.insert(0, str(ROOT / 'lab'))
        import labpaths
        udk = labpaths.udk()
    udk = Path(udk)
    pos, tri = template_floor(udk)
    alb = default_albedo(udk)
    tris, owner = scene_triangles(manifest, pos, tri)
    occ = shadows.Occluder(tris)
    albedo_per_triangle = np.tile(alb, (len(tris), 1))
    lights = manifest_lights(manifest)
    saved = bounce.SPOT_INDIRECT_CONE_SCALE
    if spot_cone_scale is not None:
        bounce.SPOT_INDIRECT_CONE_SCALE = spot_cone_scale
    try:
        out = dict(albedo=[float(v) for v in alb], spotIndirectConeScale=bounce.SPOT_INDIRECT_CONE_SCALE, rays=rays,
                   environment=[float(v) for v in environment], sourceRadius=source_radius, receivers={})
        source = None
        if source_radius:
            source = bounce.SourceIrradiance(occ, tris, lights, source_radius, seed=seed + 100)
        centres = tris.mean(1)
        for k, r in enumerate(manifest['receivers']):
            name = r['name']
            if name + '/world' not in texels:
                continue
            w, frame = texels[name + '/world'], texels[name + '/frame']
            udk_lin = (texels[name + '/dmc'] ** codec.GAMMA * texels[name + '/scales'][1]).sum(1)
            pick = (texels[name + '/px'] % stride == 0) & (texels[name + '/py'] % stride == 0)
            pts = w[pick] + 0.01 * frame[2]
            frames = np.broadcast_to(frame, (pick.sum(), 3, 3))
            direct = np.zeros((len(pts), 3, 3))
            for j, light in enumerate(lights):
                c = codec.light_contribution(light, pts, frames)
                lit = c.sum((1, 2)) > 0
                if lit.any():
                    c[lit] *= shadows.light_visibility(occ, light, pts[lit], frames[lit, 2], samples=64,
                                                       seed=seed + j)[:, None, None]
                direct += c
            ind = bounce.gather(occ, tris, albedo_per_triangle, lights, pts, frames, rays=rays, seed=seed,
                                environment=environment, source=source)
            d, b, u = (codec.encode(direct)['dmcLinear'].sum(1), codec.encode(ind)['dmcLinear'].sum(1), udk_lin[pick])
            from scipy.spatial import cKDTree
            others = cKDTree(centres[owner != k]).query(pts)[0] if (owner != k).any() else np.full(len(pts), np.inf)
            bands = []
            for lo, hi in BANDS:
                sel = (others >= lo) & (others < hi)
                if sel.sum() < 10:
                    continue
                bm = float(b[sel].mean())
                ratio = (u[sel].mean() - d[sel].mean()) / bm if bm > 0.02 * max(float(u[sel].mean()), 1e-6) else None
                bands.append(dict(distance=[lo, hi], texels=int(sel.sum()), udk=float(u[sel].mean()),
                                  direct=float(d[sel].mean()), bounce=bm,
                                  udkBeyondDirectOverBounce=None if ratio is None else float(ratio)))
            out['receivers'][name] = dict(texels=int(pick.sum()), udk=float(u.mean()), direct=float(d.mean()),
                                          bounce=float(b.mean()), bands=bands)
        return out
    finally:
        bounce.SPOT_INDIRECT_CONE_SCALE = saved


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('scene')
    a.add_argument('texels')
    a.add_argument('--rays', type=int, default=256)
    a.add_argument('--stride', type=int, default=3)
    a.add_argument('--spot-cone-scale', type=float)
    a.add_argument('--environment', default='0,0,0',
                   help="the base map's EnvironmentColor R,G,B (0-255): rays that leave the scene bring it back")
    a.add_argument('--environment-intensity', type=float, default=1.0)
    a.add_argument('--source-radius', type=float,
                   help="smooth the bounce sources' direct light over discs this wide (bounce.SourceIrradiance)")
    a.add_argument('--udk', help='UDK 2011-09 (default: the udk setting)')
    a.add_argument('--out')
    args = a.parse_args()
    manifest = json.loads(Path(args.scene).read_text())
    env = bounce.environment_radiance([int(v) for v in args.environment.split(',')], args.environment_intensity)
    result = check(manifest, np.load(args.texels), args.udk, args.rays, args.stride, args.spot_cone_scale,
                   environment=env, source_radius=args.source_radius)
    print(f"albedo {np.round(result['albedo'], 4).tolist()}, spot cone scale for bounce {result['spotIndirectConeScale']}")
    for name, r in result['receivers'].items():
        print(f"{name}: UDK {r['udk']:.4f}, ours direct {r['direct']:.4f} + bounce {r['bounce']:.4f}")
        for band in r['bands']:
            ratio = band['udkBeyondDirectOverBounce']
            print(f"   {band['distance'][0]:4d}-{band['distance'][1]:4d} from the nearest other receiver: UDK {band['udk']:.4f}, "
                  f"direct {band['direct']:.4f}, bounce {band['bounce']:.4f}, (UDK - direct) / bounce "
                  f"{'-' if ratio is None else f'{ratio:.2f}'}")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + '\n', newline='\n')


if __name__ == '__main__':
    main()
