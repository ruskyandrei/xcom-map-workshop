"""Shadows for the relight: how much of each light a texel sees through the map's static geometry (baker design,
section 4.7), traced with Embree (`pip install embreex`).

Shadow casters are the mesh components Lightmass lit, as the bake itself records them: static and fractured mesh
components whose LOD 0 carries a lightmap or shadow maps, unless they turn shadows off (`CastShadow` or
`bCastStaticShadow` false; debris components default to off, as `XComDebrisStaticMeshComponent` does in EW's
XComGame.upk) or are hidden in game. Their meshes are read from the map and moved to world space as
`lightmap_texels.py` does for receivers; materials are treated as opaque.

A light's visibility from a texel is the fraction of shadow rays that reach it. Point and spot lights are spheres of
their Lightmass source radius (each ray aims at a point on the sphere's disk as seen from the texel); a directional
light is a cone of its source angle. Samples are stratified on the disk and turned by a random angle per texel, so
the penumbra comes out as fine noise, not bands.
"""
import math
from pathlib import Path
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_lighting as lighting  # noqa: E402
import lightmap_texels  # noqa: E402

MESH_COMPONENTS = {'StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComDebrisStaticMeshComponent'}
CAST_SHADOW_DEFAULT = {'XComDebrisStaticMeshComponent': False}   # EW's XComGame.upk class default; others True
# Ray starts from UDK's BaseLightmass.ini [DevOptions.StaticLightingSceneConstants]: off the surface by
# VisibilityNormalOffsetDistance (3) times the map's StaticLightingLevelScale (WorldInfo LightmassSettings; 0.5 in
# URB_Bar, so 1.5 units), then VisibilityRayOffsetDistance (0.1, scaled the same) along the ray. On the bar's
# pool-table floor this reproduces the original bake's rugs: those 1.33-1.35 units high leave the floor under them
# lit, those 1.85 and 2.8 units high leave it black. (Half a texel's half-diagonal, 1.46 units there, would fit too.)
NORMAL_OFFSET = 3.0
RAY_OFFSET = 0.1
FAR = 1.0e5          # how far a directional light's rays go


def is_caster(p, component):
    """Whether Lightmass would have used this component as a shadow caster (see the module notes)."""
    cls = p.cls(component)
    if cls not in MESH_COMPONENTS or not p.name(component).startswith('TheWorld.PersistentLevel.'):
        return False
    cast = p.effective(component, 'CastShadow')
    if cast is None:
        cast = CAST_SHADOW_DEFAULT.get(cls, True)
    if not cast or p.effective(component, 'bCastStaticShadow') is False:
        return False
    owner = p.exports[component - 1]['outer']
    hidden = p.effective(component, 'HiddenGame') or (owner > 0 and p.effective(owner, 'bHidden'))
    if hidden and not p.effective(component, 'bCastHiddenShadow'):
        return False
    if p.effective(component, 'StaticMesh', 0) <= 0:
        return False
    try:
        lods = lighting.component_record(p, component)['lods']
    except Exception:
        return False
    return bool(lods) and (lods[0]['lightmap']['type'] != 0 or bool(lods[0].get('shadowMaps')))


def caster_triangles(p, components=None, materials=False, pose=None):
    """World-space triangles (n, 3, 3) float32 of the casters and the component of each triangle; with `materials`,
    also each triangle's material export index. With `pose` (location, rotation), the components' actor stands there
    instead: a copy of it (lightmap_texels.world_matrix)."""
    if components is None:
        components = [i for i in range(1, len(p.exports) + 1) if is_caster(p, i)]
    cache = {}
    tris, owners, mats = [], [], []
    for ci in components:
        mi = p.effective(ci, 'StaticMesh', 0)
        if mi not in cache:
            cache[mi] = lightmap_texels.component_mesh(p, ci)
        m = cache[mi]
        m3 = lightmap_texels.world_matrix(p, ci, *(pose or (None, None)))
        world = m['positions'][m['triangles']] @ m3[:3, :3].T + m3[:3, 3]
        # UE3 winds front faces so that cross(v1 - v0, v2 - v0) points into the surface (75,789 of 75,793 triangles
        # of the bar's first 200 casters disagree with their vertex normals); Embree's geometric normal is that
        # cross product. Reverse the winding so it points out, unless a mirrored transform has already reversed it.
        if np.linalg.det(m3[:3, :3]) > 0:
            world = world[:, ::-1]
        tris.append(world.astype(np.float32))
        owners.append(np.full(len(world), ci, np.int32))
        if materials:
            mats.append(lightmap_texels.triangle_materials(p, ci, m))
    if not tris:
        empty = (np.zeros((0, 3, 3), np.float32), np.zeros(0, np.int32))
        return empty + ((np.zeros(0, np.int64),) if materials else ())
    out = (np.concatenate(tris), np.concatenate(owners))
    return out + ((np.concatenate(mats),) if materials else ())


class Occluder:
    """Embree scene of triangles; answers whether segments are blocked."""

    def __init__(self, triangles):
        from embreex import rtcore_scene
        from embreex.mesh_construction import TriangleMesh
        self.scene = rtcore_scene.EmbreeScene()
        self.count = len(triangles)
        if self.count:
            TriangleMesh(self.scene, np.ascontiguousarray(triangles, np.float32))

    def blocked(self, origins, targets, chunk=4_000_000):
        """True where the segment origin -> target hits a triangle (the target end shortened by a hair)."""
        origins = np.asarray(origins, np.float64)
        d = np.asarray(targets, np.float64) - origins
        length = np.linalg.norm(d, axis=1)
        out = np.zeros(len(origins), bool)
        if not self.count:
            return out
        ok = length > 1e-6
        dirs = np.zeros_like(d)
        dirs[ok] = d[ok] / length[ok, None]
        for k in range(0, len(origins), chunk):
            s = slice(k, k + chunk)
            res = self.scene.run(origins[s].astype(np.float32), dirs[s].astype(np.float32),
                                 dists=(length[s] * (1 - 1e-4)).astype(np.float32), query='OCCLUDED')
            out[s] = (np.asarray(res) != -1) & ok[s]
        return out


def disk_samples(count):
    """`count` stratified points in the unit disk (concentric rings), as (count, 2)."""
    n = max(1, int(round(math.sqrt(count))))
    pts = []
    for i in range(n):
        for j in range(n):
            r = math.sqrt((i + 0.5) / n)
            a = 2 * math.pi * (j + 0.5 * (i % 2)) / n
            pts.append((r * math.cos(a), r * math.sin(a)))
    return np.array(pts[:count] if len(pts) >= count else pts)


def point_turns(world, seed=0):
    """A pseudo-random angle (0-2 pi) per point, from a hash of its position (to 1/64 unit) and `seed`: the same
    point always gets the same angle, whatever else is in the batch, so a relight before and after an edit samples
    identically wherever the edit does not reach."""
    q = np.round(np.asarray(world, float).reshape(-1, 3) * 64).astype(np.int64).astype(np.uint64)
    with np.errstate(over='ignore'):
        h = (q[:, 0] * np.uint64(0x9E3779B97F4A7C15)) ^ (q[:, 1] * np.uint64(0xC2B2AE3D27D4EB4F)) \
            ^ (q[:, 2] * np.uint64(0x165667B19E3779F9)) ^ (np.uint64(seed & 0xFFFFFFFF) * np.uint64(0x27D4EB2F165667C5))
        h ^= h >> np.uint64(29)
        h *= np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(32)
    return (h >> np.uint64(40)).astype(np.float64) / float(1 << 24) * 2 * math.pi


def light_seed(light):
    """A seed that names a light (its kind, place or direction), so its shadow samples do not depend on which other
    lights are in the list."""
    key = (light['kind'], tuple(np.round(light.get('location', light.get('toLight', (0, 0, 0))), 3)),
           light.get('component', ''))
    return zlib.crc32(repr(key).encode())


def light_visibility(occluder, light, world, normals, samples=16, seed=0, level_scale=1.0):
    """Fraction (n,) of `light` each texel sees. `light` is a codec light dict (lightmap_encode.py); `level_scale` is
    the map's StaticLightingLevelScale, which scales the ray start offsets. Each texel's sample pattern is turned by
    `point_turns(world, seed)`."""
    n = len(world)
    if n == 0:
        return np.zeros(0)
    origin = np.asarray(world, float) + NORMAL_OFFSET * level_scale * np.asarray(normals, float)
    disk = disk_samples(samples)
    k = len(disk)
    turn = point_turns(world, seed)
    if light['kind'] == 'directional':
        axis = np.broadcast_to(np.asarray(light['toLight'], float), (n, 3))
        radius = np.full(n, math.tan(math.radians(light.get('lightSourceAngle', 3.0))) * FAR)
        centre = origin + axis * FAR
    else:
        centre = np.broadcast_to(np.asarray(light['location'], float), (n, 3))
        axis = centre - origin
        axis = axis / np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-9)
        radius = np.full(n, float(light.get('lightSourceRadius', 100.0)))
    # an orthonormal pair across the axis
    helper = np.where(np.abs(axis[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(axis, u)
    c, s = np.cos(turn)[:, None], np.sin(turn)[:, None]
    u, v = c * u + s * v, -s * u + c * v
    seen = np.zeros(n)
    sphere = light['kind'] != 'directional'
    for dx, dy in disk:
        # point and spot lights: the point on the sphere's near half above this disk point (Lightmass samples the
        # light's surface; for a lamp in a shade the near side faces the opening); directional: the cone's disk
        lift = -math.sqrt(max(0.0, 1 - dx * dx - dy * dy)) if sphere else 0.0
        target = centre + radius[:, None] * (dx * u + dy * v + lift * axis)
        d = target - origin
        start = origin + RAY_OFFSET * level_scale * d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        seen += ~occluder.blocked(start, target)
    return seen / k
