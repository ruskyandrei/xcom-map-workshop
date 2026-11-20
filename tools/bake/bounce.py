"""Bounce light for the relight: one bounce of indirect light by final gathering (baker design, section 4.7).

From each gather point, rays go out over the hemisphere in even solid-angle steps (stratified, turned at random per
point). Where a ray meets a shadow caster, that point's direct irradiance from every light (attenuation, cone,
cos(normal, light), one shadow ray to the light's near side) times the surface's albedo over pi is the radiance coming
back along the ray. Each ray is then a small directional light of intensity radiance x solid angle, and goes into the
codec like any other light (lightmap_encode.py), so bounce light lands in the three directional channels by the
direction it arrives from. Rays that leave the scene or meet a surface from behind bring nothing back.

Gathering is the slow part, so it runs on a subset of texels (every `stride`-th in each atlas direction) and the rest
take the nearest gather point's coefficients; bounce light changes slowly over a surface.
"""
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lightmap_encode as codec  # noqa: E402
import shadows  # noqa: E402
from lights import effective_cone  # noqa: E402  (lightmap_encode puts tools/viewer on the path)

GATHER_OFFSET = 1.5      # gather rays start this far off the surface
# Lightmass lights a spot light's bounce sources as if both its cone angles were twice as wide (UDK BakeCalib9:
# spots aimed at walls lit the walls as the direct model says, but bounced 3.5-6.5 times our light onto the floors;
# doubled cones bring that to 0.9-1.6, as for point lights, the excess far away being UDK's extra bounces; EXP-18).
# Its direct light keeps the real cone.
SPOT_INDIRECT_CONE_SCALE = 2.0
# Radiance of rays that leave the scene, per unit of the WorldInfo's EnvironmentColor (decoded with the power the
# lightmaps' values take, codec.GAMMA: 2.2, not the sRGB curve) times its EnvironmentIntensity. UDK BakeCalib12
# (EXP-18), the environment light alone at the bar's colour: UDK's light was 0.263-0.267 of ours at 1.0 on an open
# floor, on a floor beside a wall and on the wall, so the angular model holds and only the scale differs (near 1/pi =
# 0.318, but below it).
ENVIRONMENT_SCALE = 0.266
CULL_MIN = 2000          # direct_irradiance: fewer points than this are not worth a k-d tree


def environment_radiance(colour, intensity=1.0):
    """Linear radiance of rays that leave the scene, from EnvironmentColor bytes (R, G, B) and EnvironmentIntensity."""
    return (np.asarray(colour, float) / 255.0) ** codec.GAMMA * intensity * ENVIRONMENT_SCALE


def hemisphere_directions(count):
    """`count` stratified unit directions over the upper hemisphere (z up), each standing for the same solid angle."""
    n = max(1, int(round(math.sqrt(count))))
    out = []
    for i in range(n):
        for j in range(n):
            z = (i + 0.5) / n                 # uniform in z = uniform in solid angle
            a = 2 * math.pi * (j + 0.5 * (i % 2)) / n
            r = math.sqrt(max(0.0, 1 - z * z))
            out.append((r * math.cos(a), r * math.sin(a), z))
    return np.array(out)


def tangent_frames(normals):
    """(n, 3, 3) frames (rows tangent, binormal, normal) around unit normals."""
    normals = np.asarray(normals, float)
    helper = np.where(np.abs(normals[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    t = np.cross(helper, normals)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    return np.stack([t, np.cross(normals, t), normals], 1)


def buried_texels(occluder, world, frames, level_scale=1.0, rays=16, chunk=250_000):
    """True where a texel lies inside geometry: more than half the rays over its hemisphere, from where its shadow
    rays start (shadows.NORMAL_OFFSET x level_scale off the surface), meet surfaces from behind. Such texels (a floor
    under a wall's foot, fracture pieces' interior faces, wall pieces sunk into each other) cannot be seen until
    something breaks; tracing from them gives black, while Lightmass left them lit."""
    world = np.asarray(world, float)
    frames = np.asarray(frames, float)
    dirs_t = hemisphere_directions(rays)
    k = len(dirs_t)
    out = np.zeros(len(world), bool)
    if not occluder.count:
        return out
    for s in range(0, len(world), chunk):
        w, f = world[s:s + chunk], frames[s:s + chunk]
        d = np.einsum('kj,nji->nki', dirs_t, f).reshape(-1, 3).astype(np.float32)
        o = np.repeat(w + shadows.NORMAL_OFFSET * level_scale * f[:, 2], k, 0).astype(np.float32)
        res = occluder.scene.run(o, d, output=1)
        back = (np.asarray(res['primID']) >= 0) & ((np.asarray(res['Ng'], float) * d).sum(1) > 0)
        out[s:s + chunk] = back.reshape(len(w), k).mean(1) > 0.5
    return out


def direct_irradiance(occluder, lights, points, normals, seed=0, spot_cone_scale=None):
    """(n, 3) linear irradiance at points with normals: sum of brightness x linear colour x attenuation x
    max(0, n . l) x visibility (one shadow ray each). Spot cones are widened by `spot_cone_scale` (default
    SPOT_INDIRECT_CONE_SCALE, as Lightmass lights bounce sources; 1 gives the real cone)."""
    scale = SPOT_INDIRECT_CONE_SCALE if spot_cone_scale is None else spot_cone_scale
    all_points = np.asarray(points, float)
    all_normals = np.asarray(normals, float)
    out = np.zeros((len(all_points), 3))
    # a point or spot light is worked out only at the points inside its radius, found with a k-d tree: a map has
    # hundreds of lights and a gather millions of ray hits, most of them far from any one light (faster-bake plan,
    # 3.3). The points taken, their order and the arithmetic on them are as without the tree.
    tree = None
    if len(all_points) > CULL_MIN and any(light['kind'] != 'directional' for light in lights):
        from scipy.spatial import cKDTree
        tree = cKDTree(all_points)
    for light in lights:
        cand = None
        points, normals = all_points, all_normals
        if light['kind'] == 'directional':
            l = np.broadcast_to(np.asarray(light['toLight'], float), points.shape)
            att = np.ones(len(points))
            near = np.ones(len(points), bool)
        else:
            if tree is not None:
                cand = np.asarray(tree.query_ball_point(light['location'], float(light['radius']) * (1 + 1e-9)),
                                  np.int64)
                if not len(cand):
                    continue
                cand.sort()
                points, normals = all_points[cand], all_normals[cand]
            L = np.asarray(light['location'], float) - points
            d2 = (L * L).sum(1)
            near = d2 < float(light['radius']) ** 2
            if not near.any():
                continue
            d = np.sqrt(np.maximum(d2, 1e-12))
            l = L / d[:, None]
            base = np.maximum(0.0, 1 - d2 / float(light['radius']) ** 2)
            F = float(light['falloffExponent'])
            att = base ** F if F > 0 else near.astype(float)
            if light['kind'] == 'spot':
                # the effective cone (lights.effective_cone), widened
                inner, outer = (math.degrees(v) for v in effective_cone(light['innerConeAngle'], light['outerConeAngle']))
                cos_o = math.cos(math.radians(min(179.0, scale * outer)))
                cos_i = math.cos(math.radians(min(178.0, scale * inner)))
                s = (-l) @ np.asarray(light['direction'], float)
                att = att * np.clip((s - cos_o) / max(cos_i - cos_o, 1e-6), 0, 1) ** 2
        cosine = (normals * l).sum(1)
        w = float(light.get('brightness', 1.0)) * att * np.maximum(0.0, cosine)
        idx = np.nonzero(near & (w > 1e-5))[0]
        if not len(idx):
            continue
        vis = shadows.light_visibility(occluder, light, points[idx], normals[idx], samples=1,
                                       seed=shadows.light_seed(light) + seed, level_scale=0.0)
        at = idx if cand is None else cand[idx]
        out[at] += (w[idx] * vis)[:, None] * codec.linear_colour(light['color'])[None, :]
    return out


class SourceIrradiance:
    """Direct irradiance of bounce sources as Lightmass's photon map sees it: each final-gather hit takes the mean
    direct irradiance of the surface around it, over a disc of `radius` (its direct photon search distance), among
    surface samples facing within 60 degrees of the hit's normal (PhotonSearchAngleThreshold 0.5). So a lit floor's
    light reaches the shadowed floor just under a counter's overhang or a wall's foot, and the undersides above them
    get its bounce. Samples are spread over every triangle by area, about `per_disc` to a disc; a hit with no sample
    around it takes its own direct irradiance.

    `estimate` 'mean' averages the samples found (EXP-17 run 7's trial). 'density' is a photon map's own estimate:
    the light the samples carry (each stands for its share of surface) over the disc's whole area, pi r^2. Where the
    surface around a hit is smaller than the disc, as on a floor at a wall's foot or on a narrow ledge, the estimate
    falls with it.

    `bounces` above 1 adds light that has already bounced: each sample gathers `gather_rays` rays, a hit reflecting
    the light of the sample nearest it times its albedo (`albedo`, per triangle of the occluder) over pi, a ray that
    leaves the scene bringing `environment`; repeated once per extra bounce. A final gather from these sources then
    gives `bounces` bounces in all."""

    def __init__(self, occluder, triangles, lights, radius, per_disc=40, seed=0, spot_cone_scale=None,
                 max_samples=3_000_000, estimate='mean', bounces=1, albedo=None, environment=(0.0, 0.0, 0.0),
                 gather_rays=32, box=None):
        from scipy.spatial import cKDTree
        if estimate not in ('mean', 'density'):
            raise ValueError(f'unknown estimate {estimate!r}')
        tris = np.asarray(triangles, float)
        self.occluder, self.lights, self.radius, self.spot_cone_scale = occluder, lights, float(radius), spot_cone_scale
        self.estimate = estimate
        cross = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        area = 0.5 * np.linalg.norm(cross, axis=1)
        normals = cross / np.maximum(2 * area, 1e-12)[:, None]     # outward (shadows.caster_triangles' winding)
        if box is not None:
            # samples only where they are wanted (a map's far terrain can hold most of its surface): triangles
            # meeting the box (x0, x1, y0, y1, z0, z1); the samples outside it are dropped below
            lo, hi = tris.min(1), tris.max(1)
            b = np.asarray(box, float).reshape(3, 2)
            meets = ((hi >= b[:, 0]) & (lo <= b[:, 1])).all(1)
            area = np.where(meets, area, 0.0)
        spacing2 = math.pi * self.radius ** 2 / per_disc
        spacing2 = max(spacing2, area.sum() / max_samples)
        rng = np.random.default_rng(seed)
        expected = area / spacing2
        count = np.floor(expected).astype(np.int64) + (rng.random(len(tris)) < expected % 1)
        owner = np.repeat(np.arange(len(tris)), count)
        u, v = rng.random(len(owner)), rng.random(len(owner))
        flip = u + v > 1
        u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
        t = tris[owner]
        self.points = t[:, 0] + u[:, None] * (t[:, 1] - t[:, 0]) + v[:, None] * (t[:, 2] - t[:, 0])
        self.normals = normals[owner]
        if box is not None:
            keep = ((self.points >= b[:, 0]) & (self.points <= b[:, 1])).all(1)
            self.points, self.normals = self.points[keep], self.normals[keep]
        # photons land only where light can reach: samples inside geometry (floor under a wall or a crate, faces
        # sunk into others) would carry darkness into their open neighbours' estimate
        open_ = ~buried_texels(occluder, self.points, tangent_frames(self.normals), level_scale=1.0, rays=8)
        self.points, self.normals = self.points[open_], self.normals[open_]
        if not len(self.points):
            raise ValueError('no surface to sample')
        self.irradiance = direct_irradiance(occluder, lights, self.points + 0.5 * self.normals, self.normals,
                                            seed=seed + 1, spot_cone_scale=spot_cone_scale)
        self.tree = cKDTree(self.points)
        self.spacing2 = spacing2                 # surface area each sample stands for
        # the density estimate needs every sample in the disc (layered surfaces put more than per_disc there)
        self.neighbours = int(min(len(self.points), max(8, round(per_disc * (4 if estimate == 'density' else 1.5)))))
        self.direct = self.irradiance
        if bounces > 1:
            if albedo is None:
                raise ValueError('more than one bounce needs the triangles\' albedo')
            albedo = np.asarray(albedo, float)
            for _ in range(int(bounces) - 1):
                self.irradiance = self.direct + self._indirect(self.irradiance, albedo, environment, gather_rays)

    def _nearest(self, values, points, normals):
        """`values` of the sample nearest each point that faces its way (within 60 degrees), within four sample
        spacings; zero where there is none."""
        reach = 4 * math.sqrt(self.spacing2)
        dist, idx = self.tree.query(points, k=4, distance_upper_bound=reach, workers=-1)
        ok = np.isfinite(dist)
        safe = np.where(ok, idx, 0)
        ok &= np.einsum('nkd,nd->nk', self.normals[safe], normals) >= 0.5
        first = np.argmax(ok, axis=1)
        out = values[safe[np.arange(len(points)), first]]
        out[~ok.any(1)] = 0.0
        return out

    def _indirect(self, values, albedo, environment, rays, chunk=150_000):
        """Irradiance at every sample from one more bounce of `values` (see the class notes)."""
        dirs_t = hemisphere_directions(rays)
        k = len(dirs_t)
        solid = 2 * math.pi / k
        frames = tangent_frames(self.normals)
        env = np.asarray(environment, float)
        out = np.zeros_like(values)
        for s in range(0, len(self.points), chunk):
            n = min(chunk, len(self.points) - s)
            d = np.einsum('kj,nji->nki', dirs_t, frames[s:s + n]).reshape(-1, 3).astype(np.float32)
            o = np.repeat(self.points[s:s + n] + GATHER_OFFSET * self.normals[s:s + n], k, 0).astype(np.float32)
            res = self.occluder.scene.run(o, d, output=1)
            prim, tfar = np.asarray(res['primID']), np.asarray(res['tfar'])
            ng = np.asarray(res['Ng'], float)
            hit = prim >= 0
            radiance = np.zeros((len(d), 3))
            radiance[~hit] = env
            h = np.nonzero(hit)[0]
            if len(h):
                ngh = ng[h] / np.maximum(np.linalg.norm(ng[h], axis=1, keepdims=True), 1e-12)
                front = (ngh * d[h]).sum(1) < 0
                h, ngh = h[front], ngh[front]
                pts = o[h] + d[h] * tfar[h, None]
                radiance[h] = albedo[prim[h]] * self._nearest(values, pts, ngh) / math.pi
            weight = np.tile(dirs_t[:, 2] * solid, n)                 # cos(theta) x solid angle
            out[s:s + n] = (radiance * weight[:, None]).reshape(n, k, 3).sum(1)
        return out

    def __call__(self, points, normals, seed=0):
        points = np.asarray(points, float)
        normals = np.asarray(normals, float)
        out = np.zeros((len(points), 3))
        if not len(points):
            return out
        dist, idx = self.tree.query(points, k=self.neighbours, distance_upper_bound=self.radius, workers=-1)
        dist, idx = dist.reshape(len(points), -1), idx.reshape(len(points), -1)
        ok = np.isfinite(dist)
        safe = np.where(ok, idx, 0)
        ok &= np.einsum('nkd,nd->nk', self.normals[safe], normals) >= 0.5
        n = ok.sum(1)
        have = n > 0
        total = (self.irradiance[safe] * ok[..., None]).sum(1)[have]
        if self.estimate == 'density':
            out[have] = total * self.spacing2 / (math.pi * self.radius ** 2)
        else:
            out[have] = total / n[have, None]
        if (~have).any():
            out[~have] = direct_irradiance(self.occluder, self.lights, points[~have] + 0.5 * normals[~have],
                                           normals[~have], seed=seed, spot_cone_scale=self.spot_cone_scale)
        return out


def gather(occluder, triangles, albedo, lights, world, frames, rays=64, seed=0, environment=(0.0, 0.0, 0.0),
           occlusion_distance=None, source=None, groups=None):
    """(n, 3, 3) bounce coefficients at points with frames (rows tangent, binormal, normal). Rays that leave the
    scene bring back `environment` (linear radiance: the WorldInfo's Lightmass EnvironmentColor, decoded with codec.GAMMA,
    times its EnvironmentIntensity: environment_radiance). With `occlusion_distance`, also returns each point's occlusion: the fraction of its rays
    that meet a surface nearer than that (Lightmass's ambient occlusion). With `source` (a SourceIrradiance), hits take
    its smoothed direct irradiance instead of their own (and `lights` is not used).

    With `groups` (a group index per occluder triangle, as its material, and the group count: (index array, count)),
    returns instead (coef, split): `split` (n, count) is each group's share of the flat light (summed over the basis
    and colours) of what the rays bring back from surfaces, so a group's albedo scaled by s scales its column by s.
    Light from the environment is in no group."""
    world = np.asarray(world, float)
    frames = np.asarray(frames, float)
    n = len(world)
    dirs_t = hemisphere_directions(rays)
    k = len(dirs_t)
    solid = 2 * math.pi / k
    turn = shadows.point_turns(world, seed)          # the same rays from the same point, batch or not
    c, s = np.cos(turn), np.sin(turn)
    # per point and ray: direction in the tangent frame (turned about the normal), then in world space
    dx = c[:, None] * dirs_t[None, :, 0] - s[:, None] * dirs_t[None, :, 1]
    dy = s[:, None] * dirs_t[None, :, 0] + c[:, None] * dirs_t[None, :, 1]
    dz = np.broadcast_to(dirs_t[None, :, 2], (n, k))
    l_ts = np.stack([dx, dy, dz], -1)                                        # (n, k, 3)
    d_world = np.einsum('nkj,nji->nki', l_ts, frames)                        # sum_j l_ts[j] * frame row j
    origin = world + GATHER_OFFSET * frames[:, 2]
    o = np.repeat(origin, k, 0).astype(np.float32)
    dw = d_world.reshape(-1, 3).astype(np.float32)
    res = occluder.scene.run(o, dw, output=1)
    prim = np.asarray(res['primID'])
    tfar = np.asarray(res['tfar'])
    ng = np.asarray(res['Ng'], float)
    hit = prim >= 0
    radiance = np.zeros((n * k, 3))
    radiance[~hit] = np.asarray(environment, float)
    if hit.any():
        h = np.nonzero(hit)[0]
        ngh = ng[h] / np.maximum(np.linalg.norm(ng[h], axis=1, keepdims=True), 1e-12)
        front = (ngh * dw[h]).sum(1) < 0          # shadows.caster_triangles winds triangles so Ng points out
        h, ngh = h[front], ngh[front]
        pts = o[h] + dw[h] * tfar[h, None]
        if source is not None:
            e = source(pts, ngh, seed=seed + 1)
        else:
            e = direct_irradiance(occluder, lights, pts + 0.5 * ngh, ngh, seed=seed + 1)
        radiance[h] = albedo[prim[h]] * e / math.pi
    radiance = radiance.reshape(n, k, 3)
    lt = l_ts.reshape(n * k, 3)
    weight = solid * codec.elevation_term(lt[:, 2], np.zeros(len(lt)))
    lob = codec.lobes(lt, np.zeros(len(lt)))
    per_ray = (weight[:, None] * lob).reshape(n, k, 3)                        # (n, k, 3 basis)
    coef = np.einsum('nkb,nkc->nbc', per_ray, radiance)
    if groups is not None:
        index, count = groups
        flat = (per_ray.sum(-1) * radiance.sum(-1)).reshape(-1)                 # each ray's flat light
        split = np.zeros((n, count))
        if hit.any():
            np.add.at(split, (h // k, np.asarray(index)[prim[h]]), flat[h])
        return coef, split
    if occlusion_distance is None:
        return coef
    near = (hit & (tfar < occlusion_distance)).reshape(n, k)
    return coef, near.mean(1)


def gather_points(px, py, stride):
    """The texels that gather: every stride-th in each atlas direction (all of them if none qualify)."""
    pick = (px % stride == 0) & (py % stride == 0)
    return pick if pick.any() else np.ones(len(px), bool)


def smooth(gather_world, gather_normals, gather_values, world, normals, sigma, neighbours=16, min_cos=0.8):
    """Values at every texel: the Gaussian-weighted mean (world distance, width sigma) of up to `neighbours` nearby
    gather points whose normals agree (cos > min_cos); the nearest gather point where none do. This both fills the
    texels between gather points and evens out the gather's noise."""
    from scipy.spatial import cKDTree
    k = min(neighbours, len(gather_world))
    d, idx = cKDTree(gather_world).query(world, k=k)
    d, idx = d.reshape(len(world), k), idx.reshape(len(world), k)
    agree = np.einsum('nj,nkj->nk', normals, gather_normals[idx]) > min_cos
    w = np.exp(-0.5 * (d / sigma) ** 2) * agree
    total = w.sum(1)
    none = total <= 1e-12
    w[none, 0], total[none] = 1.0, 1.0
    flat = gather_values.reshape(len(gather_values), -1)
    out = np.einsum('nk,nkv->nv', w, flat[idx]) / total[:, None]
    return out.reshape((len(world),) + gather_values.shape[1:])
