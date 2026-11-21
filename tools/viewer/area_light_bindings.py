"""Generated area lights and the glowing pieces that emitted them (editor lights plan 4.8 and 9.7).

When a map was baked, Lightmass made a `GeneratedMeshAreaLight` for each patch of glowing surface. Its `Owner` is the
WorldInfo, so the map does not say which piece emitted it. This module finds the piece from the map itself, so that
the page, the compiler and the writer all use the same association. Calibrated on URB_Bar and TempleShip
(research/area-light-matching.md); [bytes] marks what was read from the packages there.

What a generated light is:

- **Where it stands** [bytes]: at the centre of its emitting patch, moved out along the patch's average outward
  normal by Lightmass's `MeshAreaLightGeneratedDynamicLightSurfaceOffset` (30 units in UDK's BaseLightmass.ini) times
  the level's `StaticLightingLevelScale` (the WorldInfo's LightmassSettings: 0.5 on the bar, so 15 units; 1 on
  Temple, so 30), pointing along that normal: a 90-degree spot. So the patch's centre, the light's **foot**, is the
  light moved back along its direction by that offset. On a flat patch the foot lies on the surface; on a curved or
  boxed one (the claw machine) it can lie inside, up to 12 units from the surface. Normal agreement is evidence, not
  a rule: the bar's arcade machine has 20 lights pointing up from just above its base, whose faces there point down.
- **What emits one** [bytes]: only mesh components whose LightmassSettings set `bUseEmissiveForStaticLighting`. The
  light's `FalloffExponent` is the component's `EmissiveLightFalloffExponent` (default 2), and its `Radius` the
  component's `EmissiveLightExplicitInfluenceRadius` when that is set (otherwise Lightmass computes a radius from the
  brightness). These are delta-serialised structs: each member is the component's own, else its archetype's
  (`component_settings`; the bar's flood lights set only `EmissiveBoost` and inherit the flag from
  `FloodLight.Archetypes.FloodLightA`). Lightmass makes area lights mesh by mesh, so one light has one emitter.
- Material evidence (the export's profiles: an emissive parameter or texture, `EmsValue` and `EmsColor` parameters,
  emissive words in names) is recorded but covers only part of the materials; its absence proves nothing.

The match, for each base-level area light (`associate`):

1. Candidates: base-level static mesh components with a surface within `gather` of the light's foot, from their
   world-space triangles (the export's mesh key, read from the package, placed by the actor transform times the
   component transform as `export.py` and `compiler.world_box` place them). A KD-tree over the triangles keeps Temple
   Ship's 1,190 lights to seconds.
2. Measured per candidate: `distance` (light to the nearest point of its surface), `footDistance` (foot to the
   nearest point), `normalDot` (the best agreement of the light's direction with a triangle's mean vertex normal,
   the normals Lightmass averages, among its triangles near the foot), the emissive evidence and a `score` for
   ranking and display.
3. A candidate is **supported** when its component sets the emissive flag, its falloff matches the light's, its
   explicit radius matches (or it has none) and its surface comes within `footMax` of the foot.
4. `verified` when the supported candidates within `margin` of the closest belong to one actor (the closest
   component is the owner); `ambiguous` when they belong to several actors (pieces that move independently);
   `unmatched` when none is supported (the reason says what was missing); `unsupported` for a light outside the base
   level, or an owner whose transform can't carry a light. Every case lists its candidates.

Matrices are game-space 4 x 4 lists of rows, column-vector convention, as export_math builds them:
`world = M . [local, 1]`; columns 0 to 2 are the frame's X, Y and Z axes (scaled), column 3 its origin. An owner's
matrix is the actor transform times the component transform. A rotator is `[pitch, yaw, roll]` in UE3 units (65,536
per turn), its rotation matrix `export_math.transform([0, 0, 0], rotator, [1, 1, 1])`. A light's `local` pose is its
location in the owner's frame (the full inverse, so a scaled owner carries it to the scaled place) and its rotation
relative to the owner's rotation (the matrix's polar part: its scale and shear removed; a mirrored owner's frame
flips its Z axis to stay a rotation). `light_pose(local, owner_matrix)` is the inverse, so for an owner moved by a
rigid transform, `lightAfter = ownerAfter . inverse(ownerBefore) . lightBefore`.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import time

import numpy as np

from export_math import forward, multiply, transform
from mesh import read_mesh
from package import FormatError, Reader

MATCHER_VERSION = 1

# The rules' constants, in multiples of the level's surface offset (SURFACE_OFFSET x StaticLightingLevelScale), and
# why (research/area-light-matching.md has the measurements):
SURFACE_OFFSET = 30.0     # UDK BaseLightmass.ini [DevOptions.MeshAreaLights] MeshAreaLightGeneratedDynamicLightSurfaceOffset
FOOT_MAX = 1.5            # a supported emitter's surface within this of the foot: the true owners' furthest is 0.8 on
                          #   the bar (a claw machine's patch centred inside its box), 0.26 on Temple
GATHER = 3.0              # candidates listed: any surface within this of the foot
MARGIN = 0.5              # a second supported actor within this of the closest makes the match ambiguous; no two
                          #   emitters with matching settings came within 2.6 offsets of one foot (Temple's power cores)
NEAR_FOOT = 0.5           # normalDot looks at the triangles within this beyond a candidate's closest approach
MAX_CANDIDATES = 8        # candidates listed per light (all supported competitors are always listed)
SMALL_TRIANGLE = 1.0      # triangles up to this circumradius go in the KD-tree; larger ones are tested by sphere
WEIGHTS = dict(lightmass=0.25, falloff=0.1, radius=0.1, material=0.05, proximity=0.35, facing=0.15)
DEFAULT_FALLOFF = 2.0     # FLightmassPrimitiveSettings.EmissiveLightFalloffExponent's default
EMISSIVE_WORDS = ('EMS', 'EMISSIVE', 'GLOW', 'NEON')


def thresholds(scale):
    """The rules' thresholds for a level scale, in units, with the multiples and weights they come from."""
    offset = SURFACE_OFFSET * scale
    return dict(levelScale=scale, surfaceOffset=offset, footMax=FOOT_MAX * offset, gather=GATHER * offset,
                margin=MARGIN * offset, nearFoot=NEAR_FOOT * offset, maxCandidates=MAX_CANDIDATES,
                multiples=dict(footMax=FOOT_MAX, gather=GATHER, margin=MARGIN, nearFoot=NEAR_FOOT),
                weights=dict(WEIGHTS))


# ---- poses ----------------------------------------------------------------------------------------------------

def rotation_matrix(rotator):
    """The 3 x 3 rotation of a rotator (floats allowed), columns its X, Y and Z axes."""
    return np.array(transform([0, 0, 0], rotator, [1, 1, 1]), float)[:3, :3]


def rotator_of(r):
    """A rotation matrix's rotator, floats in UE3 units: FMatrix::Rotator (pitch and yaw from the X axis, roll from
    the Z and Y axes against the pitch-and-yaw frame's Y axis). Pointing straight up or down, the yaw is the one
    that leaves no roll."""
    x, y, z = r[:, 0], r[:, 1], r[:, 2]
    flat = math.hypot(x[0], x[1])
    pitch = math.atan2(x[2], flat)
    yaw = math.atan2(x[1], x[0]) if flat > 1e-9 else math.atan2(-y[0], y[1])
    unit = 32768 / math.pi
    side = rotation_matrix([pitch * unit, yaw * unit, 0])[:, 1]
    roll = math.atan2(float(z @ side), float(y @ side))
    return [pitch * unit, yaw * unit, roll * unit]


def whole(rotator):
    """A rotator in whole units, each in -32768..32767."""
    return [(int(round(v)) + 32768) % 65536 - 32768 for v in rotator]


def frame_rotation(linear):
    """The rotation of a 3 x 3 linear part: its polar factor (scale and shear removed); a mirrored frame's Z axis
    is flipped so it stays a rotation (the same flip before and after a rigid move, so lights follow)."""
    u, _, vt = np.linalg.svd(np.asarray(linear, float))
    r = u @ vt
    if np.linalg.det(r) < 0:
        r = r @ np.diag([1.0, 1.0, -1.0])
    return r


def owner_matrix(obj):
    """An export object's component world matrix (rows, game space): actor transform times component transform."""
    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return multiply(transform(obj['location'], obj['rotation'], obj.get('scale') or [1, 1, 1]),
                    obj.get('componentTransform') or identity)


def local_pose(location, rotation, owner):
    """A light's pose in an owner's frame (module notes): {location, rotation}, floats."""
    m = np.asarray(owner, float)
    where = np.linalg.solve(m[:3, :3], np.asarray(location, float) - m[:3, 3])
    turn = frame_rotation(m[:3, :3]).T @ rotation_matrix(rotation)
    return dict(location=[round(float(v), 6) for v in where], rotation=[round(v, 6) for v in rotator_of(turn)])


def light_pose(local, owner_matrix):
    """A generated light's world (location, rotation) under an owner component placed by `owner_matrix` (rows,
    game space): the inverse of how `local` was taken (module notes). The rotation is a whole-unit rotator."""
    m = np.asarray(owner_matrix, float)
    where = m[:3, :3] @ np.asarray(local['location'], float) + m[:3, 3]
    turn = frame_rotation(m[:3, :3]) @ rotation_matrix(local['rotation'])
    return [round(float(v), 6) for v in where], whole(rotator_of(turn))


# ---- the package's evidence -----------------------------------------------------------------------------------

def component_settings(p, component):
    """A component's effective LightmassSettings members: each its own, else its archetype's (delta-serialised
    structs, module notes). {} when none says anything."""
    out, seen = {}, set()
    while component > 0 and component not in seen:
        seen.add(component)
        raw = p.own(component, 'LightmassSettings')
        if isinstance(raw, (bytes, bytearray)):
            for (name, _), item in p.tagged(Reader(raw)).items():
                out.setdefault(name, item['value'])
        component = p.exports[component - 1]['arch']
    return out


def level_scale(p):
    """The persistent level's StaticLightingLevelScale (its WorldInfo's LightmassSettings), 1 when unset."""
    for index, path in enumerate(p.paths, 1):
        if path.startswith('TheWorld.PersistentLevel.') and path.count('.') == 2 and p.cls(index) == 'WorldInfo':
            raw = p.own(index, 'LightmassSettings')
            if isinstance(raw, (bytes, bytearray)):
                item = p.tagged(Reader(raw)).get(('StaticLightingLevelScale', 0))
                if item and item['value'] > 0: return float(item['value'])
            return 1.0
    return 1.0


def material_evidence(record):
    """Why an export material record looks emissive, or None: an emissive parameter or texture in its profile, a
    positive EmsValue/Emissive/Glow scalar, an EmsColor/Emissive/Glow vector with colour, an Ems/Emissive/Glow
    texture parameter, an unlit constant colour, or an emissive word in its name. Partial: None proves nothing."""
    if not record: return None
    render = record.get('render') or {}
    if render.get('emissiveParameter') or record.get('emissive'):
        return f"emissive parameter {render.get('emissiveParameter') or 'texture'}"
    def emissive_name(name):
        words = name.upper().replace('-', '_').replace(' ', '_').split('_')
        return any(w.startswith(EMISSIVE_WORDS) for w in words)
    for name, value in sorted((record.get('scalars') or {}).items()):
        if emissive_name(name) and isinstance(value, (int, float)) and value > 0: return f'{name} {value:g}'
    for name, value in sorted((record.get('vectors') or {}).items()):
        if emissive_name(name) and isinstance(value, list) and any(v > 0 for v in value[:3]): return name
    for name in sorted(record.get('textureParameters') or {}):
        if emissive_name(name): return f'texture parameter {name}'
    if render.get('family') == 'constant' and render.get('unlit'): return 'unlit constant colour'
    for name in [record.get('name') or ''] + list(record.get('parents') or []):
        if emissive_name(name.rsplit('.', 1)[-1]): return f'name {name}'
    return None


class PackageSource:
    """What the matcher reads from the viewer Package: the level scale, a component's LightmassSettings, and an
    export object's mesh as game-space triangles."""

    def __init__(self, p):
        self.p = p
        self.level_scale = level_scale(p)
        self._meshes = {}

    def settings(self, obj):
        index = self.p.by_name.get(obj['component'], 0)
        return component_settings(self.p, index) if index > 0 else {}

    def mesh(self, obj, record):
        """dict(positions (n, 3) game space, local to the component; triangles (m, 3); sections (m,) the index of
        the drawn section each triangle is in, as obj['materials'] lists them), with the fragment mask applied as
        the export applies it."""
        key = obj['mesh']
        if key not in self._meshes:
            head = key.split('-', 1)[0]
            if not head.isdigit(): raise ValueError(f'mesh {key} is not a base-level mesh of this package')
            index = int(head)
            if index > len(self.p.exports) or self.p.name(index) != record.get('name'):
                raise ValueError(f'mesh {key} is not {record.get("name")} in this package')
            if self.p.cls(index) not in ('StaticMesh', 'FracturedStaticMesh'):
                raise ValueError(f'{record.get("name")} is not a static mesh')
            m = read_mesh(self.p, index)
            positions = np.array(m['positions'], float).reshape(-1, 3)[:, [0, 2, 1]]   # glTF order to game space
            normals = np.array(m['normals'], float).reshape(-1, 3)[:, [0, 2, 1]]
            mask = record.get('fragmentMask')
            triangles, sections = [], []
            for s in m['sections']:
                if mask is not None:
                    if len(s['fragments']) != len(mask): raise ValueError('fragment ranges disagree with the mask')
                    ids = [i for on, (first, count) in zip(mask, s['fragments']) if on
                           for i in m['indices'][first:first + count * 3]]
                else:
                    ids = m['indices'][s['first']:s['first'] + s['count']]
                if not ids: continue
                triangles.append(np.array(ids, np.int64).reshape(-1, 3))
                sections.append(np.full(len(ids) // 3, len(sections), np.int64))
            if not triangles: raise ValueError(f'{record.get("name")} draws no triangles')
            self._meshes[key] = dict(positions=positions, normals=normals, triangles=np.concatenate(triangles),
                                     sections=np.concatenate(sections))
        return self._meshes[key]


# ---- geometry --------------------------------------------------------------------------------------------------

def closest_points(p, a, b, c):
    """The closest points to points p on triangles (a, b, c), all (n, 3): Ericson's Real-Time Collision Detection
    5.1.5, vectorised."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.einsum('ij,ij->i', ab, ap), np.einsum('ij,ij->i', ac, ap)
    bp = p - b
    d3, d4 = np.einsum('ij,ij->i', ab, bp), np.einsum('ij,ij->i', ac, bp)
    cp = p - c
    d5, d6 = np.einsum('ij,ij->i', ab, cp), np.einsum('ij,ij->i', ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    out = np.empty_like(p)
    done = np.zeros(len(p), bool)

    def put(mask, value):
        pick = mask & ~done
        out[pick] = value[pick]
        done[pick] = True
    with np.errstate(divide='ignore', invalid='ignore'):
        put((d1 <= 0) & (d2 <= 0), a)
        put((d3 >= 0) & (d4 <= d3), b)
        put((d6 >= 0) & (d5 <= d6), c)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + (d1 / (d1 - d3))[:, None] * ab)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + (d2 / (d2 - d6))[:, None] * ac)
        put((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), b + ((d4 - d3) / ((d4 - d3) + (d5 - d6)))[:, None] * (c - b))
        total = va + vb + vc
        inside = a + (vb / total)[:, None] * ab + (vc / total)[:, None] * ac
        # degenerate triangles (no area) that slipped through: their first corner
        put(np.isfinite(inside).all(1), inside)
        put(np.ones(len(p), bool), a)
    return out


class Triangles:
    """World-space triangles of the candidate components, with outward normals (`normals` from the winding;
    `shading`, the mean of each triangle's vertex normals where the source gives them, else the same), a KD-tree over
    the small ones' centroids and bounding spheres for the large ones."""

    def __init__(self, tris, owners, sections, small, shading=None):
        from scipy.spatial import cKDTree
        self.tris, self.owners, self.sections = tris, owners, sections
        # UE3 winds front faces so that cross(v1 - v0, v2 - v0) points into the surface (bake/shadows.py
        # caster_triangles); the caller has already reversed mirrored components' triangles
        normals = np.cross(tris[:, 2] - tris[:, 0], tris[:, 1] - tris[:, 0])
        length = np.linalg.norm(normals, axis=1)
        self.normals = np.divide(normals, length[:, None], out=np.zeros_like(normals), where=length[:, None] > 0)
        self.shading = self.normals if shading is None else shading
        self.centres = tris.mean(1)
        self.radii = np.linalg.norm(tris - self.centres[:, None], axis=2).max(1)
        self.small = np.nonzero(self.radii <= small)[0]
        self.large = np.nonzero(self.radii > small)[0]
        self.reach = small
        self.tree = cKDTree(self.centres[self.small]) if len(self.small) else None

    def near(self, point, distance):
        """Indices of the triangles that may come within `distance` of `point`."""
        found = []
        if self.tree is not None:
            found.append(self.small[np.asarray(self.tree.query_ball_point(point, distance + self.reach), np.int64)])
        if len(self.large):
            gap = np.linalg.norm(self.centres[self.large] - point, axis=1) - self.radii[self.large]
            found.append(self.large[gap <= distance])
        return np.sort(np.concatenate(found)) if found else np.zeros(0, np.int64)


# ---- the match -------------------------------------------------------------------------------------------------

def associate(p, objects, lights, meshes, materials, warn=None):
    """The matcher's result for a map, from the viewer Package and the export's own records (module notes; plan 9.7):
    dict(version, thresholds, attachments: {area light id: attachment}, owners: {object id: [area light ids]})."""
    return associate_with(PackageSource(p), objects, lights, meshes, materials, warn)


def associate_with(source, objects, lights, meshes, materials, warn=None):
    """associate() over a source of evidence: `source.level_scale`, `source.settings(obj)` (the component's
    LightmassSettings members) and `source.mesh(obj, mesh_record)` (PackageSource.mesh's shape). The tests give
    synthetic ones."""
    say = warn or (lambda source_, message: None)
    t = thresholds(source.level_scale)
    offset, gather = t['surfaceOffset'], t['gather']
    area = sorted((l for l in lights if l.get('role') == 'area'), key=lambda l: l['id'])
    attachments = {}
    base = []
    for light in area:
        if light.get('layer', 'base') != 'base':
            attachments[light['id']] = attachment('unsupported', f"the light is in the {light.get('layer')} layer: only "
                                                  f"base-level lights follow pieces", None, [], None, None)
        else:
            base.append(light)
    location = np.array([l['location'] for l in base], float).reshape(-1, 3)
    direction = np.array([forward(l['rotation']) if l.get('rotation') is not None else l['direction'] for l in base],
                         float).reshape(-1, 3)
    direction /= np.maximum(np.linalg.norm(direction, axis=1), 1e-12)[:, None]
    feet = location - offset * direction

    # candidate components: base-level static meshes whose bounding sphere comes within reach of a foot
    from scipy.spatial import cKDTree
    foot_tree = cKDTree(feet) if len(feet) else None
    chosen, tris, owners, sections, shading = [], [], [], [], []
    for obj in objects:
        if foot_tree is None: break
        record = meshes.get(obj.get('mesh'))
        if obj.get('layer') != 'base' or not record or record.get('kind') == 'skeletal': continue
        m = np.array(owner_matrix(obj), float)
        b = record.get('bounds') or [0, 0, 0, 0, 0, 0, 0]
        centre = m[:3, :3] @ np.asarray(b[:3], float) + m[:3, 3]
        stretch = float(np.linalg.norm(m[:3, :3], 2))
        radius = max(float(b[6]) if len(b) > 6 else 0.0, float(np.linalg.norm(b[3:6]))) * stretch
        if not foot_tree.query_ball_point(centre, radius + gather): continue
        try:
            mesh = source.mesh(obj, record)
        except (ValueError, FormatError, struct.error, IndexError) as error:
            say(obj.get('component'), f'area-light matching skips it: {error}')
            continue
        world = (mesh['positions'] @ m[:3, :3].T + m[:3, 3])[mesh['triangles']]
        if np.linalg.det(m[:3, :3]) < 0: world = world[:, ::-1]      # a mirror reverses the winding back
        if mesh.get('normals') is not None:
            # the vertex normals Lightmass averages, by the inverse transpose, each triangle's mean
            vertex = mesh['normals'] @ np.linalg.inv(m[:3, :3])
            mean = vertex[mesh['triangles']].sum(1)
            length = np.linalg.norm(mean, axis=1)
            shading.append(np.divide(mean, length[:, None], out=np.zeros_like(mean), where=length[:, None] > 1e-9))
        else:
            shading.append(None)
        chosen.append(obj)
        tris.append(world)
        owners.append(np.full(len(world), len(chosen) - 1, np.int64))
        sections.append(mesh['sections'])
    if tris:
        triangles = Triangles(np.concatenate(tris), np.concatenate(owners), np.concatenate(sections),
                              SMALL_TRIANGLE * gather)
        if any(s is not None for s in shading):
            triangles.shading = np.concatenate([g if s is None else s for s, g in zip(shading, np.split(
                triangles.normals, np.cumsum([len(w) for w in tris])[:-1]))])
    settings, evidence = {}, {}

    def lightmass(k):
        if k not in settings:
            try: settings[k] = source.settings(chosen[k])
            except (ValueError, FormatError, struct.error) as error:
                say(chosen[k].get('component'), f'LightmassSettings unreadable: {error}')
                settings[k] = {}
        return settings[k]

    def materials_of(k):
        if k not in evidence:
            evidence[k] = [why for why in (material_evidence(materials.get(key)) for key in chosen[k].get('materials') or [])
                           if why]
        return evidence[k]

    for i, light in enumerate(base):
        found = []
        if tris:
            near = triangles.near(feet[i], gather)
            if len(near):
                foot_points = closest_points(np.repeat(feet[i][None], len(near), 0), *(triangles.tris[near, j] for j in range(3)))
                foot_gap = np.linalg.norm(foot_points - feet[i], axis=1)
                keep = foot_gap <= gather
                near, foot_gap = near[keep], foot_gap[keep]
            if len(near):
                light_points = closest_points(np.repeat(location[i][None], len(near), 0),
                                              *(triangles.tris[near, j] for j in range(3)))
                light_gap = np.linalg.norm(light_points - location[i], axis=1)
                facing = triangles.shading[near] @ direction[i]
                who = triangles.owners[near]
                for k in np.unique(who):
                    mine = who == k
                    closest = float(foot_gap[mine].min())
                    window = mine & (foot_gap <= closest + t['nearFoot'])
                    nearest = np.flatnonzero(mine)[np.argmin(foot_gap[mine])]
                    found.append(candidate(chosen[k], light, foot_distance=closest, distance=float(light_gap[mine].min()),
                                           normal_dot=float(facing[window].max()), settings=lightmass(k),
                                           material_reasons=materials_of(k),
                                           material=section_material(chosen[k], triangles.sections[near[nearest]], materials),
                                           t=t))
        attachments[light['id']] = decide(light, found, t)
    owners_out = {}
    for light_id, entry in attachments.items():
        for c in entry['candidates']:
            owners_out.setdefault(c['objectId'], []).append(light_id)
    return dict(version=MATCHER_VERSION, thresholds=t, attachments=dict(sorted(attachments.items())),
                owners={k: sorted(v) for k, v in sorted(owners_out.items())})


def section_material(obj, section, materials):
    keys = obj.get('materials') or []
    key = keys[section] if 0 <= section < len(keys) else None
    return (materials.get(key) or {}).get('name') if key is not None else None


def candidate(obj, light, *, foot_distance, distance, normal_dot, settings, material_reasons, material, t):
    """One candidate's measurements, evidence, support and score."""
    flag = bool(settings.get('bUseEmissiveForStaticLighting'))
    falloff = float(settings.get('EmissiveLightFalloffExponent', DEFAULT_FALLOFF))
    explicit = float(settings.get('EmissiveLightExplicitInfluenceRadius', 0.0) or 0.0)
    falloff_ok = abs(falloff - float(light.get('falloffExponent', DEFAULT_FALLOFF))) <= 1e-3
    radius_ok = explicit <= 0 or abs(explicit - float(light.get('radius', 0.0))) <= 1e-2 * max(1.0, explicit)
    emissive = (['lightmass'] if flag else []) + (['falloff'] if flag and falloff_ok else []) + (
        ([] if not flag else ['radius-computed'] if explicit <= 0 else ['radius'] if radius_ok else [])) + (
        ['material'] if material_reasons else [])
    w = t['weights']
    score = (w['lightmass'] * flag + w['falloff'] * (flag and falloff_ok) + w['radius'] * (flag and radius_ok)
             + w['material'] * bool(material_reasons)
             + w['proximity'] * max(0.0, 1 - foot_distance / t['gather']) + w['facing'] * max(0.0, normal_dot))
    supported = flag and falloff_ok and radius_ok and foot_distance <= t['footMax']
    return dict(objectId=obj['id'], actor=obj['actor'], component=obj['component'], distance=round(distance, 2),
                footDistance=round(foot_distance, 2), normalDot=round(normal_dot, 3), emissive=emissive,
                score=round(score, 4), supported=bool(supported), material=material,
                emitter=dict(falloff=falloff, radius=explicit) if flag else None,
                materialEvidence=material_reasons[:3], _obj=obj)


def short(path):
    return str(path).rsplit('.', 1)[-1]


def matches(c):
    """Whether a candidate's emitter settings fit the light (the flag, the falloff and the radius)."""
    return 'falloff' in c['emissive'] and ('radius' in c['emissive'] or 'radius-computed' in c['emissive'])


def attachment(status, reason, owner, candidates, matrix, local):
    return dict(status=status, reason=reason, owner=owner, candidates=candidates, ownerMatrix=matrix, local=local,
                matcher=MATCHER_VERSION)


def decide(light, found, t):
    """The attachment for one base-level light from its candidates (module notes, step 4)."""
    rank = sorted(found, key=lambda c: (-c['score'], c['footDistance'], c['objectId']))
    supported = sorted((c for c in found if c['supported']), key=lambda c: (c['footDistance'], -c['score'], c['objectId']))
    competitors = [c for c in supported if c['footDistance'] <= supported[0]['footDistance'] + t['margin']] if supported else []
    listed = competitors + [c for c in rank if c not in competitors]
    listed = listed[:max(t['maxCandidates'], len(competitors))]
    objs = {c['objectId']: c.pop('_obj') for c in found}
    if not supported:
        return attachment('unmatched', unmatched_reason(light, rank, t), None, listed, None, None)
    actors = sorted({c['actor'] for c in competitors})
    if len(actors) > 1:
        names = ', '.join(f"{short(c['actor'])} ({c['footDistance']:.1f})" for c in competitors)
        return attachment('ambiguous', f"{len(actors)} pieces' emitters fit within {t['margin']:.1f} units of the "
                          f"closest (foot distances): {names}", None, listed, None, None)
    best = competitors[0]
    obj = objs[best['objectId']]
    matrix = owner_matrix(obj)
    if abs(np.linalg.det(np.asarray(matrix, float)[:3, :3])) < 1e-9:
        return attachment('unsupported', f"{short(best['actor'])}'s transform is singular: it can't carry a light",
                          None, listed, None, None)
    others = sorted((c for c in found if c['actor'] != best['actor'] and matches(c)), key=lambda c: c['footDistance'])
    reason = (f"one emitter fits: {short(best['actor'])} (its surface {best['footDistance']:.1f} units from the "
              f"light's foot, normal agreement {best['normalDot']:.2f})")
    if len(competitors) > 1:
        reason += f"; {len(competitors) - 1} other component(s) of the same actor also fit"
    reason += (f"; the next emitter with matching settings, {short(others[0]['actor'])}, is "
               f"{others[0]['footDistance']:.1f} units from the foot" if others else
               f"; no other emitter with matching settings within {t['gather']:.0f} units")
    owner = dict(target=dict(package=obj.get('sourcePackage'), level='base', actor=obj['actor']),
                 component=obj['component'], objectId=obj['id'])
    return attachment('verified', reason, owner, listed, matrix,
                      local_pose(light['location'], light['rotation'], matrix))


def unmatched_reason(light, rank, t):
    if not rank:
        return f"no base-level surface within {t['gather']:.0f} units of the light's foot"
    flagged = [c for c in rank if 'lightmass' in c['emissive']]
    if not flagged:
        return (f"no nearby component sets bUseEmissiveForStaticLighting; nearest surface: "
                f"{short(min(rank, key=lambda c: c['footDistance'])['actor'])}")
    fitting = [c for c in flagged if matches(c)]
    if not fitting:
        c = min(flagged, key=lambda c: c['footDistance'])
        return (f"nearby emitters' settings differ from the light's (falloff {light.get('falloffExponent'):g}, radius "
                f"{light.get('radius'):g}): {short(c['actor'])} has falloff {c['emitter']['falloff']:g}, explicit radius "
                f"{c['emitter']['radius']:g}")
    c = min(fitting, key=lambda c: c['footDistance'])
    return (f"the nearest emitter with matching settings, {short(c['actor'])}, is {c['footDistance']:.1f} units from "
            f"the light's foot (limit {t['footMax']:.1f})")


# ---- calibration and inspection from the command line ----------------------------------------------------------

def export_records(package_path, folder):
    """The export's records of a map (objects, lights, meshes, materials, diagnostics) as `viewer.py export` makes
    them, its meshes written to `folder` and its textures skipped (the matcher reads none)."""
    from export import Exporter
    from package import Package

    class RecordsOnly(Exporter):
        def texture(self, index): return None
    p = Package(package_path)
    result = RecordsOnly(p, Path(folder)).run('map')
    return p, result


def summary(result):
    counts = {}
    for entry in result['attachments'].values():
        counts[entry['status']] = counts.get(entry['status'], 0) + 1
    return counts


def main(argv=None):
    import tempfile
    import settings as viewer_settings
    from package import Package
    ap = argparse.ArgumentParser(description='Match a map\'s generated area lights to their glowing pieces and report.')
    ap.add_argument('map', help='a map name in the game install (the game setting), or a .upk path')
    ap.add_argument('--scene', help="an export's scene.json to take the records from (else the map is exported to a "
                                    'temporary folder first)')
    ap.add_argument('--json', help='write the matcher result here')
    ap.add_argument('--show', type=int, default=3, help='examples per status to print')
    args = ap.parse_args(argv)
    path = Path(args.map)
    if path.suffix.lower() != '.upk':
        cooked = viewer_settings.lwr_cooked()
        if cooked is None: raise SystemExit('The game install is not set: python tools/viewer/viewer.py settings')
        path = cooked / f'{args.map}.upk'
    diagnostics = []
    started = time.perf_counter()
    if args.scene:
        p = Package(path)
        scene = json.loads(Path(args.scene).read_text(encoding='utf-8'))
        records, exported = scene, 0.0
    else:
        with tempfile.TemporaryDirectory(prefix='area-lights-') as folder:
            p, records = export_records(path, folder)
        exported = time.perf_counter() - started
    started = time.perf_counter()
    result = associate(p, records['objects'], records['lights'], records['meshes'], records['materials'],
                       lambda source, message: diagnostics.append(f'{source}: {message}'))
    took = time.perf_counter() - started
    print(f"{p.path.stem}: {len(result['attachments'])} area lights, {summary(result)}; matched in {took:.1f} s"
          + (f' (export {exported:.1f} s)' if exported else '') + f"; level scale {result['thresholds']['levelScale']:g}")
    for line in diagnostics[:10]: print('  warning:', line)
    names = {l['id']: short(l['actor']) for l in records['lights']}
    for status in ('verified', 'ambiguous', 'unmatched', 'unsupported'):
        shown = [(k, v) for k, v in result['attachments'].items() if v['status'] == status][:args.show]
        for light_id, entry in shown:
            print(f'  {status} {names.get(light_id, light_id)}: {entry["reason"]}')
    if args.json:
        Path(args.json).write_text(json.dumps(dict(result, map=p.path.stem, seconds=round(took, 2)), indent=1),
                                   encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
