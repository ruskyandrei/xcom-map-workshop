"""The sun's baked shadows made again for the whole map when its direction changed (the sun plan's section 5; stage
T-S4 of the game-likeness plan). A Build with baking runs it inside the relight (relight.py --sun-turned) when its
native edit says the sun's direction changed (`sun.directionChanged`, tools/editor/build.py). By then the light's new
Rotation is in the map (the Build's native step writes it), and every part below reads the direction from there.

- Every distance-field shadow map of the map's dominant light, on every piece the level lists (the copies, the pieces
  of other maps and the made pieces the edit added, and the debris volume's pieces), traced from nothing in the scene
  after the edit (shadowmaps.fresh_shadow_map) and written as it is, not as a change on the old field, which holds
  the old sun's shadows. `whole_map_jobs` hands them to the relight's workers as its own shadow-map jobs.
- The light's own shadow map of the level for moving things (`DominantLightShadowMap` on its component, F-176), made
  as Lightmass makes one (F-195). Its light-space frame comes from the light's direction (`light_frame`: UE3's
  FindBestAxisVectors). Its box is the map's Lightmass importance volume in that frame (`light_box`). Each texel's
  depth is the deepest of 5 x 5 rays from the box's near face along the light, across the texel from its corner to
  the next texel's (`level_depths`). The map keeps its size, since a write in place cannot change the count of its
  depths, so its texels stretch to the new box.
- Each lighting sample's mark for "the sun does not reach here" (`bShadowedFromDominantLights`, F-175), set again by
  one ray from the sample toward the light (`sample_marks`).

`level_edits` gives the last two as fixed-size edits of the map, which the relight's writer makes in its one write
(lightmap_writer.run's `edits`, through package_edit.write_edited); `verify` reads them back from the written map.
Pieces with no shadow map of the light (on its IrrelevantLights: wholly in the old sun's shadow, F-184) have no texture
to take a new field, and stay unlit by it.
"""
import math
from pathlib import Path
import struct
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import lighting_records as lighting  # noqa: E402
import shadowmaps  # noqa: E402
import shadows  # noqa: E402
from export_math import forward, transform  # noqa: E402
from scene_metadata import level_list  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
SUPER_SAMPLE = 4        # steps across a texel of the light's map of the level, 5 rays a side with both ends (F-195)
DEPTH_STEPS = 65535     # a stored depth: 0 at the box's near face, this at its far face
TEXEL_UNITS = 100.0     # Lightmass's world units a texel of the map of the level, times the level's lighting scale


def enabled_lights(p):
    """{LightGuid hex: light} of the map's enabled dominant directional lights (shadowmaps.dominant_lights)."""
    return {g: l for g, l in shadowmaps.dominant_lights(p).items() if l['enabled']}


def direction_key(p):
    """The sun's direction as the piece cache's key holds it (relight.PieceCache): each enabled dominant light's GUID
    and the direction toward it, rounded."""
    return sorted([g, [round(float(v), 6) for v in l['toLight']]] for g, l in enabled_lights(p).items())


# ------------------------------------------------------------------------------------------------ the shadow maps

def whole_map_jobs(p):
    """Every distance-field shadow map of the map's enabled dominant lights on a piece the level lists (debris
    pieces included), each a job of the relight's shadow maps lit from nothing: dict(path, ci, sm, light, source
    None, fresh True), in the map's order. A piece the edit took out of the level (a hidden one), or one staged from
    another map that no level lists, is left: the game never draws it."""
    listed = level_list(p)
    jobs = []
    for path, ci, sm, light in shadowmaps.dominant_receivers(p, enabled_lights(p), debris=True):
        if listed is not None and p.exports[ci - 1]['outer'] not in listed:
            continue
        jobs.append(dict(path=path, ci=ci, sm=sm, light=light, source=None, fresh=True))
    return jobs


# --------------------------------------------------------------------------------- the light's map of the level

def light_frame(direction):
    """(worldToLight, lightToWorld), 4 x 4 arrays with rows as lighting_records.matrix_rows gives them, for a
    dominant light shining along `direction`: UE3's basis, the light space's z the direction, its x the world's x
    (for a light nearer the vertical than either level axis) or the world's z, made square to the direction, and its
    y x cross z. lightToWorld's rows are the axes and worldToLight is its transpose (F-195: as all 93 maps of the
    install with a map of the level store them)."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    ax, ay, az = np.abs(d)
    x = np.array([1.0, 0.0, 0.0]) if az > ax and az > ay else np.array([0.0, 0.0, 1.0])
    x = x - d * x.dot(d)
    x /= np.linalg.norm(x)
    l2w = np.eye(4)
    l2w[0, :3], l2w[1, :3], l2w[2, :3] = x, np.cross(x, d), d
    return l2w.T.copy(), l2w


def importance_box(p):
    """The world box (lo, hi) of the map's Lightmass importance volumes together: each one's brush bounds through its
    actor's pose and scale, the eight corners boxed. None when the map has none (every map of the install with a
    map of the level has one, F-195)."""
    import native_copy
    boxes = []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'LightmassImportanceVolume' or p.exports[i - 1]['outer'] != p.by_name.get(PL[:-1]):
            continue
        origin, extent = native_copy.brush_bounds(p, i)
        scale = [v * p.effective(i, 'DrawScale', 1.0) for v in p.effective(i, 'DrawScale3D', [1.0, 1.0, 1.0])]
        m = np.array(transform(p.effective(i, 'Location', [0.0, 0.0, 0.0]), p.effective(i, 'Rotation', [0, 0, 0]),
                               scale), float)
        corners = np.array([[origin[0] + a * extent[0], origin[1] + b * extent[1], origin[2] + c * extent[2], 1.0]
                            for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])
        world = (corners @ m.T)[:, :3]
        boxes.append((world.min(0), world.max(0)))
    if not boxes:
        return None
    return np.min([b[0] for b in boxes], 0), np.max([b[1] for b in boxes], 0)


def light_box(lo, hi, world_to_light):
    """The world box (lo, hi) in light space: its eight corners through `world_to_light`, boxed, as [min x, y, z,
    max x, y, z] (LightSpaceImportanceBounds)."""
    corners = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    ls = (corners @ world_to_light)[:, :3]
    return [float(v) for v in ls.min(0)] + [float(v) for v in ls.max(0)]


def wanted_size(bounds, level_scale):
    """The map's size Lightmass would give this box (F-195): a texel TEXEL_UNITS times the level's lighting scale
    wide, at least 4 texels a side."""
    unit = TEXEL_UNITS * level_scale
    return [max(int((bounds[3] - bounds[0]) / unit), 4), max(int((bounds[4] - bounds[1]) / unit), 4)]


def level_depths(occluder, light_to_world, bounds, size, super_sample=SUPER_SAMPLE):
    """The depths of a map of the level (sizeX x sizeY, rows of X, Y down the rows) as Lightmass traces them (F-195):
    for texel (X, Y), (s + 1) x (s + 1) rays along the light from the box's near face (s `super_sample`), at the
    fractions (X + a / s) / (sizeX - 1) and (Y + b / s) / (sizeY - 1) of the box's width and height for a and b from
    0 to s, the texel's corner to the next one's; the texel's depth is the deepest hit, a ray that meets nothing
    counting as the far face. Returns (depths: uint16 array, 0 at the near face and DEPTH_STEPS at the far, rays that
    met nothing)."""
    sx, sy = size
    lo, hi = np.asarray(bounds[:3], float), np.asarray(bounds[3:], float)
    depth = hi[2] - lo[2]
    if depth <= 0:
        raise ValueError(f'a map of the level with a box {depth} units deep')
    ix, iy = np.arange(sx, dtype=float), np.arange(sy, dtype=float)
    a = np.arange(super_sample + 1, dtype=float) / super_sample
    k = len(a)
    fx = (ix[:, None] + a[None, :]).ravel() / max(sx - 1, 1)        # (sx * k,): X fastest within its texel
    fy = (iy[:, None] + a[None, :]).ravel() / max(sy - 1, 1)
    X, Y = np.meshgrid(lo[0] + fx * (hi[0] - lo[0]), lo[1] + fy * (hi[1] - lo[1]))
    near = np.stack([X.ravel(), Y.ravel(), np.full(X.size, lo[2]), np.ones(X.size)], 1) @ np.asarray(light_to_world)
    along = np.asarray(light_to_world)[2, :3]
    along = along / np.linalg.norm(along)
    dist = distances(occluder, near[:, :3], along, depth)
    missed = ~np.isfinite(dist)
    dist[missed] = depth
    deepest = dist.reshape(sy, k, sx, k).max((1, 3))
    stored = np.round(np.clip(deepest / depth, 0.0, 1.0) * DEPTH_STEPS).astype(np.uint16)
    return stored.ravel(), int(missed.sum())


def distances(occluder, origins, direction, far):
    """Each ray's distance from `origins` along `direction` to the first triangle of `occluder` (shadows.Occluder),
    inf where none lies within `far`."""
    if not occluder.count:
        return np.full(len(origins), np.inf)
    dirs = np.broadcast_to(np.asarray(direction, np.float32), (len(origins), 3))
    got = np.asarray(occluder.scene.run(np.ascontiguousarray(origins, np.float32), np.ascontiguousarray(dirs),
                                        query='DISTANCE'), float)
    got[~np.isfinite(got) | (got > far)] = np.inf
    return got


def level_map(p, ci, occluder, level_scale):
    """The light `ci`'s map of the level made again for its direction as the map now has it (its actor's
    Rotation): dict(component, sizeX, sizeY (kept), size Lightmass would give the new box, depths, worldToLight,
    lightToWorld, bounds, missed, old (what the map stored: depths, bounds)), or dict(component, skipped: why) for a
    light with no map of the level, or a map with no importance volume to box it."""
    old = lighting.dominant_shadow_map(p, ci)
    out = dict(component=p.name(ci))
    if not old['depths']:
        return dict(out, skipped='the light has no map of the level')
    box = importance_box(p)
    if box is None:
        return dict(out, skipped='the map has no Lightmass importance volume to bound its map of the level')
    actor = p.exports[ci - 1]['outer']
    w2l, l2w = light_frame(forward(p.effective(actor, 'Rotation', [-16384, 0, 0])))
    bounds = light_box(box[0], box[1], w2l)
    size = [old['sizeX'], old['sizeY']]
    depths, missed = level_depths(occluder, l2w, bounds, size)
    return dict(out, sizeX=size[0], sizeY=size[1], wantedSize=wanted_size(bounds, level_scale), depths=depths,
                worldToLight=w2l, lightToWorld=l2w, bounds=bounds, missed=missed,
                old=dict(depths=np.asarray(old['depths'], np.uint16), bounds=old['bounds']))


def matrix_bytes(rows):
    """A Matrix struct's 64 bytes from four (X, Y, Z, W) rows, each saved W first (lighting_records.matrix_rows)."""
    return b''.join(struct.pack('<4f', float(r[3]), float(r[0]), float(r[1]), float(r[2])) for r in rows)


def map_edits(p, ci, made):
    """The fixed-size edits ((logical offset, bytes, what)) that give the light `ci` the map of the level `made`
    (level_map's): its depths over the counted array, its two matrices and the box's six floats (its IsValid byte and
    the sizes kept). ValueError for a count that is not the map's."""
    old = lighting.dominant_shadow_map(p, ci)
    if len(made['depths']) != len(old['depths']) or [made['sizeX'], made['sizeY']] != [old['sizeX'], old['sizeY']]:
        raise ValueError(f"{p.name(ci)}: {len(made['depths'])} depths for its {old['sizeX']} x {old['sizeY']} map")
    places = lighting.shadow_info_places(p, ci)
    short = p.name(ci)[len(PL):]
    return [(old['offset'], np.asarray(made['depths'], '<u2').tobytes(), f'map of the level of {short}: depths'),
            (places['WorldToLight'], matrix_bytes(made['worldToLight']), f'map of the level of {short}: WorldToLight'),
            (places['LightToWorld'], matrix_bytes(made['lightToWorld']), f'map of the level of {short}: LightToWorld'),
            (places['LightSpaceImportanceBounds'], struct.pack('<6f', *made['bounds']),
             f'map of the level of {short}: LightSpaceImportanceBounds')]


# ------------------------------------------------------------------------------------------- the lighting samples

def persistent_level(p):
    return p.by_name.get(PL[:-1])


def sample_marks(p, occluder, level_scale, lights=None):
    """Each lighting sample's mark made again (bShadowedFromDominantLights): 1 where a ray from the sample toward
    any enabled dominant light (`lights`, enabled_lights' by default) meets a triangle of `occluder`, else 0 (on
    URB_Bar's own moon 99.7% of the map's marks, F-195). Returns (the volume as lighting_records.light_volume reads it,
    the marks in its samples' order)."""
    volume = lighting.light_volume(p, persistent_level(p))
    lights = enabled_lights(p) if lights is None else lights
    where = np.array([s[:3] for s in volume['samples']], float).reshape(-1, 3)
    shadowed = shadowed_points(occluder, where, [l['toLight'] for l in lights.values()], level_scale)
    return volume, [int(v) for v in shadowed]


def shadowed_points(occluder, points, to_lights, level_scale=1.0):
    """Which `points` (n, 3) a ray toward any of the directions `to_lights` (each toward a light) leaves blocked by a
    triangle of `occluder`: one ray each, started a hair along it (shadows.RAY_OFFSET times the level's lighting
    scale)."""
    shadowed = np.zeros(len(points), bool)
    for to in to_lights:
        to = np.asarray(to, float)
        to = to / np.linalg.norm(to)
        start = points + shadows.RAY_OFFSET * level_scale * to
        shadowed |= occluder.blocked(start, points + to * shadows.FAR)
    return shadowed


# --------------------------------------------------------------------------------------------- the edits, read back

def level_edits(p, world):
    """The light's map of the level and the lighting samples' marks made again in the scene `world` (relight.Scene:
    the map after the edit), as fixed-size edits for the relight's writer: (edits [(offset, bytes, what)], record).
    The record says what was made (its `maps`, for verify, hold the values written) and what was left, and why."""
    lights = enabled_lights(p)
    record = dict(lights=[dict(component=l['component'], toLight=[round(float(v), 6) for v in l['toLight']])
                          for l in lights.values()], maps=[], samples=None, notes=[])
    edits = []
    by_component = {p.by_name[l['component']]: l for l in lights.values()}
    for ci in sorted(by_component):
        made = level_map(p, ci, world.occluder, world.level_scale)
        if 'skipped' in made:
            record['notes'].append(f"{made['component'][len(PL):]}: {made['skipped']}")
            continue
        edits += map_edits(p, ci, made)
        record['maps'].append(made)
    if lights:
        try:
            volume, marks = sample_marks(p, world.occluder, world.level_scale, lights)
        except lighting.FormatError as error:
            record['notes'].append(f'the lighting samples were not read ({error}): their marks are the old sun\'s')
        else:
            before = [s[-1] for s in volume['samples']]
            edits += [(at, value, 'lighting sample mark') for at, value in lighting.mark_edits(volume, marks)]
            record['samples'] = dict(count=len(marks), markedBefore=sum(before), markedAfter=sum(marks),
                                     changed=sum(a != b for a, b in zip(before, marks)), marks=marks)
    return edits, record


def summary(record):
    """The record without its arrays, for the relight's JSON record: each map's size, box, the depths changed and
    the rays that met nothing; the samples' counts."""
    maps = []
    for m in record['maps']:
        b = m['bounds']
        maps.append(dict(component=m['component'][len(PL):], size=[m['sizeX'], m['sizeY']], wantedSize=m['wantedSize'],
                         bounds=[round(v, 2) for v in b], oldBounds=[round(v, 2) for v in m['old']['bounds']],
                         unitsPerTexel=[round((b[3] - b[0]) / m['sizeX'], 2), round((b[4] - b[1]) / m['sizeY'], 2)],
                         depthsChanged=int((m['depths'] != m['old']['depths']).sum()), missed=m['missed']))
    samples = None if record['samples'] is None else {k: v for k, v in record['samples'].items() if k != 'marks'}
    return dict(lights=record['lights'], maps=maps, samples=samples, notes=record['notes'])


def verify(path, record):
    """The written map at `path` read back: each light's map of the level holds the depths, matrices (as float32) and
    box the record made, its size kept, and the lighting samples hold the marks made, every other field as before.
    ValueError on any difference."""
    q = lighting.Package(path)
    for m in record['maps']:
        ci = q.by_name[m['component']]
        got = lighting.dominant_shadow_map(q, ci)
        if [got['sizeX'], got['sizeY']] != [m['sizeX'], m['sizeY']] or not np.array_equal(
                np.asarray(got['depths'], np.uint16), np.asarray(m['depths'], np.uint16)):
            raise ValueError(f"{m['component']}: its map of the level does not read back as written")
        for key in ('worldToLight', 'lightToWorld'):
            if not np.array_equal(np.asarray(got[key], np.float32), np.asarray(m[key], np.float32)):
                raise ValueError(f"{m['component']}: its {key} does not read back as written")
        if not np.array_equal(np.asarray(got['bounds'], np.float32), np.asarray(m['bounds'], np.float32)):
            raise ValueError(f"{m['component']}: its box does not read back as written")
    if record['samples'] is not None:
        volume = lighting.light_volume(q, persistent_level(q))
        if [s[-1] for s in volume['samples']] != record['samples']['marks']:
            raise ValueError('the lighting samples\' marks do not read back as written')


def shadowed_by_map(p, ci, points, bias=0.0):
    """Which world `points` (n, 3) the light `ci`'s map of the level, as the map holds it, puts in shadow: deeper
    along the light than the depth of the texel that holds them (its corner layout, as level_depths traces it) by more
    than `bias` units. A point outside the box's width and height takes the nearest texel."""
    m = lighting.dominant_shadow_map(p, ci)
    sx, sy, b = m['sizeX'], m['sizeY'], m['bounds']
    ls = np.c_[np.asarray(points, float), np.ones(len(points))] @ np.asarray(m['worldToLight'], float)
    x = np.clip(np.floor((ls[:, 0] - b[0]) / (b[3] - b[0]) * (sx - 1)), 0, sx - 1).astype(int)
    y = np.clip(np.floor((ls[:, 1] - b[1]) / (b[4] - b[1]) * (sy - 1)), 0, sy - 1).astype(int)
    stored = b[2] + np.asarray(m['depths'], float)[y * sx + x] / DEPTH_STEPS * (b[5] - b[2])
    return ls[:, 2] > stored + bias


def fit(p, ci, occluder):
    """How the light `ci`'s map of the level, as the map holds it, fits rays traced along the light through
    `occluder` from each texel's centre (audit_suns.py level-map's yardstick, F-176): dict(texels, hits, within25,
    within100, median: stored less traced, in world units)."""
    m = lighting.dominant_shadow_map(p, ci)
    sx, sy, b = m['sizeX'], m['sizeY'], m['bounds']
    l2w = np.asarray(m['lightToWorld'], float)
    xs = b[0] + (np.arange(sx) + 0.5) * (b[3] - b[0]) / sx
    ys = b[1] + (np.arange(sy) + 0.5) * (b[4] - b[1]) / sy
    X, Y = np.meshgrid(xs, ys)
    near = np.stack([X.ravel(), Y.ravel(), np.full(X.size, b[2]), np.ones(X.size)], 1) @ l2w
    along = l2w[2, :3] / np.linalg.norm(l2w[2, :3])
    dist = distances(occluder, near[:, :3], along, math.inf)
    hit = np.isfinite(dist)
    stored = np.asarray(m['depths'], float) / DEPTH_STEPS * (b[5] - b[2])
    d = stored[hit] - dist[hit]
    return dict(texels=int(len(hit)), hits=int(hit.sum()), within25=round(float(np.mean(np.abs(d) < 25)), 4),
                within100=round(float(np.mean(np.abs(d) < 100)), 4), median=round(float(np.median(d)), 2))
