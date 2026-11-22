"""Per-texel geometry of a map component's lightmap: world position and tangent frame at every texel centre of its
atlas rectangle (baker design, section 4.7).

The component's static mesh is read in game space (Z up). Its lightmap UVs (the mesh's LightMapCoordinateIndex
channel) map into the atlas through the lightmap record's coordinate scale and bias; each triangle is rasterised there
and the texels whose centres fall inside it take the interpolated position, normal, tangent and binormal sign, moved
to world space by the actor's and the component's transforms (as the viewer's exporter builds them). The frame is
made orthonormal per texel: binormal = (normal x tangent) * sign, the UE3 convention EXP-18 confirmed on UDK's
template floor (tangent +X, sign -1, binormal -Y).
"""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'viewer'))
from export_math import multiply, transform  # noqa: E402
from mesh import read_mesh  # noqa: E402


def world_matrix(p, component, location=None, rotation=None):
    """4 x 4 game-space local-to-world matrix of a component (actor transform times component transform). With
    `location` and `rotation`, its actor stands there instead (a copy at a new pose keeps the actor's scale and the
    component's own transform, as XComMapEdCopier's copies do)."""
    actor = p.exports[component - 1]['outer']
    for flag in ('AbsoluteTranslation', 'AbsoluteRotation', 'AbsoluteScale'):
        if p.effective(component, flag, False):
            raise ValueError(f'unsupported {flag} on {p.name(component)}')
    scale = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    cscale = [v * p.effective(component, 'Scale', 1) for v in p.effective(component, 'Scale3D', [1, 1, 1])]
    am = transform(p.effective(actor, 'Location', [0, 0, 0]) if location is None else location,
                   p.effective(actor, 'Rotation', [0, 0, 0]) if rotation is None else rotation, scale)
    cm = transform(p.effective(component, 'Translation', [0, 0, 0]), p.effective(component, 'Rotation', [0, 0, 0]),
                   cscale)
    return np.array(multiply(am, cm), float)


def component_mesh(p, component):
    """Game-space vertex arrays of the component's static mesh: positions, normals, tangents, binormal signs,
    lightmap UVs, triangle indices. `uv` is None for a mesh without the UV channel its LightMapCoordinateIndex names
    (CLrgScout_Stonewall's CemeteryFoliage.Meshes.VineTop_2: one channel, index 1, lit per vertex): it still casts
    shadows and has a box, and only `rasterise` refuses it."""
    mi = p.effective(component, 'StaticMesh', 0)
    if mi <= 0:
        raise ValueError(f'{p.name(component)} has no static mesh in this package')
    m = read_mesh(p, mi)
    channel = p.effective(mi, 'LightMapCoordinateIndex', 0)
    swap = [0, 2, 1]        # read_mesh gives glTF order (x, z, y); game space is (x, y, z)
    pos = np.array(m['positions'], float).reshape(-1, 3)[:, swap]
    nrm = np.array(m['normals'], float).reshape(-1, 3)[:, swap]
    tan4 = np.array(m['tangents'], float).reshape(-1, 4)
    tan = tan4[:, swap]
    sign = np.where(-tan4[:, 3] < 0, -1.0, 1.0)     # read_mesh stores -TangentZ.W as the glTF tangent w
    uv = np.array(m['uvs'][channel], float).reshape(-1, 2) if 0 <= channel < len(m['uvs']) else None
    tris = np.array(m['indices'], np.int64).reshape(-1, 3)
    return dict(mesh=p.name(mi), channel=channel, positions=pos, normals=nrm, tangents=tan, signs=sign, uv=uv,
                triangles=tris, sections=m['sections'])


def triangle_materials(p, component, mesh):
    """Material export index of each triangle: the component's override for the section's slot, else the mesh's."""
    overrides = p.refs(p.effective(component, 'Materials')) if p.effective(component, 'Materials') else []
    out = np.zeros(len(mesh['triangles']), np.int64)
    for s in mesh['sections']:
        slot = s['slot']
        mat = overrides[slot] if 0 <= slot < len(overrides) and overrides[slot] > 0 else s['material']
        out[s['first'] // 3:(s['first'] + s['count']) // 3] = mat
    return out


def rect_bounds(lightmap, width, height):
    """The texel bounds (x0, y0, x1, y1), half-open, of a lightmap record's rectangle in a width x height atlas."""
    (sx, sy), (bx, by) = lightmap['coordinateScale'], lightmap['coordinateBias']
    return (int(np.floor(bx * width + 1e-6)), int(np.floor(by * height + 1e-6)),
            int(np.ceil((bx + sx) * width - 1e-6)), int(np.ceil((by + sy) * height - 1e-6)))


def moved_rect(source, source_size, record, size):
    """Whether the lightmap or shadow-map record `record` over a texture of `size` (width, height) reads the texels
    `source` reads over one of `source_size`, moved by whole texels: a copy's own texture of the box of its source's
    (lightmap_textures.moved_record), or a whole clone (moved by none). The rectangle the same size in texels, its
    corner a whole number of texels away. (Records hold 32-bit floats and the sizes are powers of two: these sums are
    exact.)"""
    for k in (0, 1):
        if source['coordinateScale'][k] * source_size[k] != record['coordinateScale'][k] * size[k]:
            return False
        moved = source['coordinateBias'][k] * source_size[k] - record['coordinateBias'][k] * size[k]
        if moved != int(moved):
            return False
    return True


def rasterise(mesh, matrix, lightmap, size):
    """Texels of the atlas (size = [width, height]) whose centres lie on the mesh, inside the component's rectangle.

    Returns dict(px, py (atlas texel coordinates), world (n, 3), frames (n, 3, 3) rows tangent/binormal/normal,
    triangle (n,) the mesh triangle each texel lies on, rect (x0, y0, x1, y1) the rectangle's texel bounds,
    half-open)."""
    if mesh['uv'] is None:
        raise ValueError(f'{mesh["mesh"]} has no UV channel {mesh["channel"]}')
    width, height = size
    (sx, sy), (bx, by) = lightmap['coordinateScale'], lightmap['coordinateBias']
    x0, y0, x1, y1 = rect_bounds(lightmap, width, height)
    # texel centres sit at integer coordinates in this space
    px_uv = np.stack([(bx + sx * mesh['uv'][:, 0]) * width - 0.5, (by + sy * mesh['uv'][:, 1]) * height - 0.5], 1)
    owner = np.full((y1 - y0, x1 - x0), -1, np.int64)
    bary = np.zeros((y1 - y0, x1 - x0, 3))
    for t, (a, b, c) in enumerate(mesh['triangles']):
        pa, pb, pc = px_uv[a], px_uv[b], px_uv[c]
        lo = np.maximum(np.floor(np.minimum(np.minimum(pa, pb), pc)), [x0, y0]).astype(int)
        hi = np.minimum(np.ceil(np.maximum(np.maximum(pa, pb), pc)), [x1 - 1, y1 - 1]).astype(int)
        if (hi < lo).any():
            continue
        gx, gy = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
        det = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
        if abs(det) < 1e-12:
            continue
        wa = ((pb[1] - pc[1]) * (gx - pc[0]) + (pc[0] - pb[0]) * (gy - pc[1])) / det
        wb = ((pc[1] - pa[1]) * (gx - pc[0]) + (pa[0] - pc[0]) * (gy - pc[1])) / det
        wc = 1 - wa - wb
        inside = (wa >= -1e-6) & (wb >= -1e-6) & (wc >= -1e-6)
        if not inside.any():
            continue
        iy, ix = gy[inside] - y0, gx[inside] - x0
        owner[iy, ix] = t
        bary[iy, ix] = np.stack([wa[inside], wb[inside], wc[inside]], 1)
    iy, ix = np.nonzero(owner >= 0)
    tri = mesh['triangles'][owner[iy, ix]]
    w = bary[iy, ix]

    def interp(attr):
        return np.einsum('nk,nkd->nd', w, attr[tri])

    m3 = matrix[:3, :3]
    normal_m = np.linalg.inv(m3).T
    handed = np.sign(np.linalg.det(m3))
    world = interp(mesh['positions']) @ m3.T + matrix[:3, 3]
    n = interp(mesh['normals']) @ normal_m.T
    t = interp(mesh['tangents']) @ m3.T
    sign = mesh['signs'][tri[:, 0]] * handed
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    t -= (t * n).sum(1, keepdims=True) * n
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    b = np.cross(n, t) * sign[:, None]
    return dict(px=ix + x0, py=iy + y0, world=world, frames=np.stack([t, b, n], 1), triangle=owner[iy, ix],
                rect=(x0, y0, x1, y1))


def dilate(values, mask, passes=4):
    """Spread values (h, w, c) from masked texels into unmasked neighbours, `passes` texels deep (each new texel is
    the mean of its masked 8-neighbours). Returns (values, grown mask)."""
    values = values.copy()
    mask = mask.copy()
    h, w = mask.shape
    for _ in range(passes):
        acc = np.zeros_like(values)
        cnt = np.zeros((h, w))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                src = np.zeros((h, w), bool)
                sv = np.zeros_like(values)
                ys, yd = slice(max(0, dy), h + min(0, dy)), slice(max(0, -dy), h + min(0, -dy))
                xs, xd = slice(max(0, dx), w + min(0, dx)), slice(max(0, -dx), w + min(0, -dx))
                src[yd, xd] = mask[ys, xs]
                sv[yd, xd] = values[ys, xs]
                acc += sv * src[..., None]
                cnt += src
        grow = ~mask & (cnt > 0)
        if not grow.any():
            break
        values[grow] = acc[grow] / cnt[grow][:, None]
        mask = mask | grow
    return values, mask
