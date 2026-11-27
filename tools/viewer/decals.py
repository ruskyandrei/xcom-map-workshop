"""The map's placed decals in the export (the game-likeness plan, stage D1; export 47; F-210, F-211): each decal's
actor, place, frame, size and material, and one mesh of the triangles the game stored for it on the surfaces it lies
on, its parts grouped by the piece each lies on.

The triangles are the game's own (decal_records.receivers: clipped to the decal's box when it was placed, kept in each
receiving component's space), put in the world where the map has that piece (the export's own record of it: its
actor's and component's transforms). A receiver that is no piece of the export (one that could not be read) leaves its
part out, with a diagnostic. The mesh's vertices carry what the game's decal vertex shader makes of them
(decal_records.coordinates, surface_frame): its texture coordinates in the first UV channel, its blend by the surface's
angle and its depth along the decal's normal in the second, the decal's own tangent frame on the surface as the mesh's
tangents, the surface's normal as its normals.

  records(exporter, objects) -> [dict]     the package's placed decals, their meshes written in the export's folder
"""
from pathlib import Path
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402
paths.use('upk')
import numpy as np  # noqa: E402
import decal_records  # noqa: E402
from export_math import multiply, transform  # noqa: E402
from mesh import write_glb  # noqa: E402
from package import FormatError  # noqa: E402
from scene_metadata import level_list  # noqa: E402

OWNERS = decal_records.OWNERS


def _round(values, places=4):
    return [round(float(v), places) for v in values]


def world_matrix(obj):
    """A piece's local-to-world transform (4 x 4 rows, game axes) from its export record: its actor's transform (its
    location, rotation and scale) times its component's, as Exporter.component made its `matrix`."""
    return multiply(transform(obj['location'], obj['rotation'], obj['scale']), obj['componentTransform'])


def decal_mesh(f, parts):
    """The decal's mesh as write_glb takes it, from its parts [(receiver, local-to-world matrix)], and each part's
    index range and area: (mesh, [(first, count, area)])."""
    positions, normals, tangents, uv0, uv1, indices, ranges = [], [], [], [], [], [], []
    base = 0
    for rec, matrix in parts:
        local, _, packed = decal_records.vertices(rec)
        points, surface = decal_records.in_world(matrix, local, packed)
        u, v, blend, depth = decal_records.coordinates(f, points, surface)
        tangent, binormal = decal_records.surface_frame(f, surface)
        # the binormal's side of the tangent and normal (UE3's binormal = cross(normal, tangent) * w)
        w = np.where(np.einsum('ij,ij->i', np.cross(surface, tangent), binormal) < 0, -1.0, 1.0)
        tri = np.asarray(rec['indices'], dtype=np.int64).reshape(-1, 3)
        a, b, c = points[tri[:, 0]], points[tri[:, 1]], points[tri[:, 2]]
        area = float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2) if len(tri) else 0.0
        ranges.append((len(indices), len(rec['indices']), area))
        indices.extend(int(i) + base for i in rec['indices'])
        base += len(points)
        # the mesh's axes are the game's x, z, y (as mesh.read_mesh writes a piece's), its tangent's w flipped there
        positions.append(points[:, [0, 2, 1]])
        normals.append(surface[:, [0, 2, 1]])
        tangents.append(np.column_stack([tangent[:, [0, 2, 1]], -w]))
        uv0.append(np.column_stack([u, v]))
        uv1.append(np.column_stack([blend, depth]))
    flat = lambda rows, k: [float(x) for x in np.concatenate(rows).reshape(-1)] if rows else []  # noqa: E731
    mesh = dict(positions=flat(positions, 3), normals=flat(normals, 3), tangents=flat(tangents, 4),
                uvs=[flat(uv0, 2), flat(uv1, 2)], colors=[], indices=indices,
                sections=[dict(first=0, count=len(indices), slot=0)])
    return mesh, ranges


def records(exporter, objects):
    """The placed decals of the exporter's package (each DecalComponent of a DecalActor or DecalActorMovable of its
    level that has receivers), as export 47's `decals` (research/editor-contracts.md section 13), each mesh written as
    decal-<id>.glb in the export's folder. `objects` are the package's pieces as the export made them."""
    p = exporter.p
    pieces = {o['id']: o for o in objects}
    listed = level_list(p)          # (None: not read, every actor taken as listed)
    out = []
    for actor, name in enumerate(p.paths, 1):
        if not name.startswith('TheWorld.PersistentLevel.') or name.count('.') != 2 or p.cls(actor) not in OWNERS:
            continue
        for component in p.children.get(actor, []):
            if p.cls(component) != 'DecalComponent':
                continue
            try:
                record = one(exporter, actor, component, pieces, listed is None or actor in listed)
            except (FormatError, ValueError, IndexError, KeyError, np.linalg.LinAlgError) as error:
                exporter.warn(p.name(component), f'Decal not read: {error}')
                continue
            if record:
                out.append(record)
    return out


def one(exporter, actor, component, pieces, listed):
    """One decal's record (records' form), or None for a component with no receivers. `listed`: whether its actor is
    in the level's actor list (the Build's clear takes only what is)."""
    p, prefix = exporter.p, exporter.prefix
    found = decal_records.receivers(p.native(component), p)
    if not found:
        return None
    f = decal_records.frame(p, component)
    if any(f[k] is None for k in ('location', 'tangent', 'binormal', 'normal')):
        raise FormatError('its frame is not saved')
    parts, receivers = [], []
    for rec in found:
        owner = p.exports[rec['component'] - 1]['outer']
        piece = f"{prefix}{owner}:{rec['component']}"
        if piece not in pieces:
            exporter.warn(p.name(component), f"its part on {p.name(rec['component'])} is left out: that piece is not "
                                             'in the export')
            continue
        parts.append((rec, world_matrix(pieces[piece])))
        receivers.append(dict(piece=piece, actor=p.name(owner), component=p.name(rec['component']),
                              triangles=rec['triangles']))
    key = f'{prefix}{actor}'
    mesh_record = None
    lies_on = None
    if parts:
        mesh, ranges = decal_mesh(f, parts)
        url = f'decal-{key}.glb'
        write_glb(mesh, exporter.folder / url)
        for entry, (first, count, area) in zip(receivers, ranges):
            entry.update(first=first, count=count, area=round(area, 1))
        lies_on = max(receivers, key=lambda r: r['area'])['piece']
        xyz = np.asarray(mesh['positions']).reshape(-1, 3)[:, [0, 2, 1]]
        mesh_record = dict(url=url, vertices=len(xyz), triangles=len(mesh['indices']) // 3,
                           box=dict(min=_round(xyz.min(axis=0), 2), max=_round(xyz.max(axis=0), 2)))
    material = decal_records.member(p, component, 'DecalMaterial') or 0
    return dict(id=f'{key}:{component}', actor=p.name(actor), component=p.name(component), actorClass=p.cls(actor),
                sourcePackage=p.path.stem, layer='inherited' if prefix else 'base',
                location=_round(p.effective(actor, 'Location', [0, 0, 0])),
                rotation=[int(v) for v in p.effective(actor, 'Rotation', [0, 0, 0])],
                hidden=bool(p.effective(actor, 'bHidden', False) or p.effective(component, 'HiddenGame', False)),
                listed=listed,
                prefab=exporter.prefabs.get(actor), liesOn=lies_on,
                material=exporter.section_material(material, 0) if material else None,
                size=dict(width=round(f['width'], 4), height=round(f['height'], 4), nearPlane=round(f['nearPlane'], 4),
                          farPlane=round(f['farPlane'], 4), tile=_round(f['tile']), offset=_round(f['offset']),
                          decalRotation=round(f['decalRotation'], 4), blendRange=_round(f['blendRange']),
                          depthBias=f['depthBias']),
                frame=dict(location=_round(f['location']), tangent=_round(f['tangent'], 6),
                           binormal=_round(f['binormal'], 6), normal=_round(f['normal'], 6)),
                mesh=mesh_record, receivers=receivers)
