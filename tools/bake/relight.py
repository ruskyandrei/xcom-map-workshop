"""Relight map components from the map's own static lights with EW's lightmap codec (baker design, section 4.7).

For each component: the lights its lightmap was baked from (the lightmap record's light GUIDs, matched to the map's
light components), the world position and tangent frame of every texel (`lightmap_texels.py`), the light of each by
the codec fitted to UDK Lightmass (`lightmap_encode.py`, EXP-18), then both textures written into the component's
atlas rectangle and its directional slot scale set (`lightmap_writer.py` image and setscale).

By default the light is shadowed by the map's static geometry (`shadows.py`, Embree), the emissive surfaces' generated
area lights are added (Lightmass bakes emissive surfaces without listing them among a lightmap's lights), and one
bounce is gathered (`bounce.py`, with each surface's albedo from `albedo.py` and the WorldInfo's environment colour),
as URB_Bar's Lightmass settings ask (NumIndirectLightingBounces 1). Not modelled: ambient occlusion (tested on the
bar's floor, it made the match worse), masked materials' holes (they shadow as solid), more bounces.

  python -B tools/bake/relight.py <map.upk> <out dir> <variant> --cache Lighting_7004 --component PATH [...]
      [--component-list FILE] [--direct-only] [--no-emissive] [--samples 64] [--bounce-rays 64] [--stride 2]
      [--checker SIZE] [--source-radius R] [--remove-caster ACTOR ...] [--remove-caster-list FILE]
      [--remove-light LIGHT ...]
      [--edit-spec SPEC] [--native-copy COPY=SOURCE ...] [--foreign-copy COPY=STAGED ...] [--fresh-copy COPY ...]
      [--light-edits FILE] [--receivers-near R] [--no-quick]
      [--jobs N] [--band-texels N] [--floor F] [--piece-cache DIR --base SHA]

An edit is relit as a change on the original bake (see `apply_change`). `--edit-spec` takes the edit from an editor
patch spec (`tools/editor/compiler.py`): the pieces its exact hider hides are removed casters, and its copies are
added casters at their poses. A moved piece is both. The copies themselves are lit live in the game, and their light
environments cast no shadow (`bCastShadows` false, from XComDestructibleActor), so their shadows on the map's baked
receivers come only from here.

`--native-copy COPY=SOURCE` names an actor of the map that is a copy of SOURCE made as a new actor (native_copy.py
`--bake`, which runs this): the scene before the edit leaves it out, so the receivers around it take its shadows.
Its own lightmap and its shadow maps hold the source's bake (cloned textures), and go from our light on the source
where it stands, from the lights the source's lightmap lists, to our light on the copy where it stands, from the
lights the copy's lightmap lists (`relight_component` with `source`). A texel buried at either place keeps the
source's bake.

`--moved-in-place ACTOR=X,Y,Z,PITCH,YAW,ROLL` names an actor of the map moved where it is (native_spawns.py: a
landing's grounded Skyranger carried by its zone, F-98), standing at its new pose in the map, with its old pose. The
scene before the edit leaves it out where it stands and has a posed copy of it at the old pose; the scene after is the
map as it is. The receivers around both places are relit as for a moved piece. Its own lightmap and shadow maps keep
their bake.

`--foreign-copy COPY=STAGED` names an actor that is a copy of STAGED, a piece of another map staged in this one
(transplant.py; no level lists STAGED, and both scenes leave it out). The copy has no bake of this map to build on:
its lightmap is our light on it where it stands, from the lights its lightmap lists (native_copy.py gave it this map's),
with the area lights and the bounce; the texels our light doesn't reach are black. Its shadow maps of the map's
dominant light are their whole field, from the scene after the edit.

`--fresh-copy COPY` names a new actor of this map lit from nothing as a foreign copy is, with no staged piece: a copy
whose mesh the Build made (a generated fracturing wall, frac_walls.py), whose cloned lightmap holds its donor's bake
on another shape. The scene before the edit leaves it out; the scene after has it as it stands.

`--light-edits FILE` takes the light edits native_copy.py made in this map (lights deleted, changed, added, generated
area lights moved, copied or deleted; private/plans/done/editor-lights-plan.md, 4.4), as native_lights.relight_edits writes
them: each edited light's codec light before and after, and the GUIDs the build added to receivers' lightmap lists.
The scene before the edit has the original lights (a changed one as it was, no added one); the scene after has the
changed ones as they are now, the added ones and not the deleted ones (`resolve_light_states`). A receiver's direct
lights come from its lightmap list through each state's lights: before, its list as the original bake had it
(without the GUIDs the build added: a newly listed light invents no contribution to the original bake), a native
copy's from its source's; after, its list as it is now. The area lights of each state are its emissive stand-ins, and
its lights its bounce sources. `--remove-light` is one more such edit, a light taken away.

`--receivers-near R` relights, besides any components named, every texture-lightmapped component of the persistent
level whose world box comes within R units of what the edit changes: each removed caster where it stood, each copy at
its pose, and each edited light's radius before and after. Components the edit turns out not to reach keep their bake.
An edit that changes no texel (a disabled or zero-brightness light added, a light that reaches no receiver) succeeds:
the edited map is the variant as it is, its original lighting kept, with no texture cache (`lightingUnchanged` in the
records, their cache null). A receiver that fails to relight (rather than being left by rule: `Excluded`) makes such
an edit fail.

In an edit, a quick reach test (`edit_reaches`) first leaves out the components the edit can't change: those more than
REACH_NEAR (384) units from what it changes, where its bounce can't show, that no light reaching them shines through it
onto them and that are more than REACH_NEAR from every edited light's radius, before and after. They keep their bake, listed in the record's `unreached`; `--no-quick`
relights them all. `--jobs N` relights components in N worker processes (each builds the scenes once).

Since the faster-bake plan (private/plans/done/faster-bake-plan.md), an edit's relight goes further than the quick
test for each piece:
- in a piece in reach, only the texels the edit can change are relit (`texel_reach`: the same rule for each texel;
  not with `--no-quick`); the others keep the original bake exactly;
- a piece whose largest change is under `--floor` (0.043) keeps its bake;
- where the relit light still fits under the piece's original slot scale, the scale stays and only the changed texels
  are written (the writer leaves every other 4-texel block's bytes alone), and the ring of padding around the
  rectangle follows its border (`lightmap_writer.image`).
The pieces go to the workers largest first, and a piece of more than twice `--band-texels` texels is relit in bands,
each a job, put together afterwards (`prepare_component`, `compute_component`, `assemble_component`): one large floor
no longer holds a worker while the others stand idle. The dominant light's shadow maps are traced by the workers too.
A worker that dies stops the relight with a message instead of being waited for.
`--piece-cache DIR --base SHA` keeps each relit piece in DIR, and takes from there the pieces whose lights and reaching
edits are as they were when it was kept (`PieceCache`): a rebuild after a small change relights only what the change
reaches. The record's `timing` says where the time went (tools/bake/profile_build.py prints it).

In an edit, the dominant light's shadow maps are relit too (`shadowmaps.py`; `--no-shadow-maps` leaves them): every
component with one whose box the edit's shadow can reach (the quick test with the dominant light) is traced before
and after the edit, and where its view of the light changes, the map's own distance field takes our field's change.
They are listed in the record's `shadowMaps` (written) and `shadowMapsUnchanged`.

`--component-list` reads more component paths, one per line (# starts a comment). A component that cannot be
relit (no texture lightmap, a lightmap outside Lighting.tfc, StaticLightingHiddenByDefault) is skipped and listed in
the record's `skipped`; it keeps its bake. Small lightmaps kept whole inside the map package are written there in
place (`lightmap_writer.py`).

Texels inside geometry (`bounce.buried_texels`: a floor under a wall's foot, fracture pieces' interior faces) are
left out when the scene shadows: the dilation spreads their unburied neighbours' values into those at the edges, and
the rest keep the original bake. They show only once something breaks. In an edit that removes casters, a texel counts
as buried only if it is buried both before and after: the floor under a removed piece that stood solid on it is
relit. Its light before comes out near zero by itself (shadow rays and gather rays from inside the piece hit its back
faces), as in the original bake, which is black there; a texel only near the buried threshold keeps its own light.
`--checker SIZE` keeps the original bake in alternate cubes SIZE units wide (both re-encoded under one slot scale),
so that in the game any mismatch between the two bakes shows as a checkerboard on floors and walls alike.

Writes <out>/<variant>.upk and the variant texture cache <out>/<cache>.tfc (as lightmap_writer.py does: --cache is a
name the map's table holds, as the Build's <Map>_Lighting once a growing write has added it, or <Name>_<n> with <Name>
in it, as Lighting_7004), <out>/<variant>.relight.npz
(the texel images), <out>/<variant>.relight.json (lights, scales, coverage, comparison with the original bake) and
<out>/<variant>-<actor>.png previews: original and relit, as the light a flat surface would get (colour times the sum
of the three directional values), on one scale.
"""
import argparse
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import struct
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lighting_records as lighting  # noqa: E402
import lightmap_writer  # noqa: E402
import lightmap_encode as codec  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_texels  # noqa: E402
from lightmap_textures import top_mip_rect  # noqa: E402
import props as legacy_props  # noqa: E402
import bounce  # noqa: E402
import shadows  # noqa: E402
from lights import light_record  # noqa: E402

KINDS = {'PointLightComponent': 'point', 'SpotLightComponent': 'spot', 'DirectionalLightComponent': 'directional'}


def guid_hex(value):
    return value.hex() if isinstance(value, (bytes, bytearray)) else str(value)


def lightmass_settings(p, component):
    """The light component's explicit LightmassSettings members (a tagged struct), as {name: value}."""
    raw = p.effective(component, 'LightmassSettings')
    out = {}
    if not isinstance(raw, (bytes, bytearray)):
        return out
    for name, kind, _, _, at, size in legacy_props.tags(raw, 0, len(raw), p.names):
        value = raw[at:at + size]
        if kind == 'BoolProperty':
            out[name] = bool(value[0])
        elif kind == 'FloatProperty':
            out[name] = struct.unpack('<f', value)[0]
        elif kind == 'IntProperty':
            out[name] = struct.unpack('<i', value)[0]
        else:
            out[name] = value.hex()
    return out


def component_lights(p, guids):
    """Codec light dicts for the map's light components whose LightmapGuid or LightGuid is in `guids`."""
    return map_lights(p, guids=guids)


# Lights Lightmass bakes: placed static lights and the area lights it generated for emissive surfaces (role names as
# tools/viewer/lights.py gives them). Toggleable, dominant and forced-dynamic lights stay live.
BAKED_ROLES = ('static', 'area')


def map_lights(p, guids=None, roles=BAKED_ROLES):
    """Codec light dicts for the map's light components: those whose LightmapGuid or LightGuid is in `guids` when
    given, else every light whose role is in `roles` (every light at all when `roles` is None). Each carries `guids`,
    its LightmapGuid and LightGuid (hex): a lightmap may list either, and both name the one light."""
    want = set(guids) if guids is not None else None
    found = []
    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if cls not in KINDS or not p.name(i).startswith('TheWorld.PersistentLevel.'):
            continue
        hexes = [guid_hex(p.effective(i, k)) for k in ('LightmapGuid', 'LightGuid')
                 if isinstance(p.effective(i, k), (bytes, bytearray))]
        ids = set(hexes)
        if want is not None and not ids & want:
            continue
        actor = p.exports[i - 1]['outer']
        rec = light_record(p, actor)
        if rec is None or rec['component'] != p.name(i):
            if want is None:
                continue
            raise ValueError(f'{p.name(i)}: its actor does not name it as the light component')
        role = rec['role']
        if role == 'static' and p.effective(i, 'bForceDynamicLight'):
            role = 'movable'
        if want is None and roles is not None and role not in roles:
            continue
        settings = lightmass_settings(p, i)
        light = dict(kind=KINDS[cls], actor=rec['actor'], component=rec['component'], brightness=rec['brightness'],
                     color=rec['color'], enabled=rec['enabled'], role=role,
                     guid=sorted(ids & want)[0] if want is not None else min(ids, default=None), guids=hexes)
        if light['kind'] == 'directional':
            light['toLight'] = [-v for v in rec['direction']]
            light['lightSourceAngle'] = settings.get('LightSourceAngle', codec.UDK_DIRECTIONAL_SOURCE_ANGLE)
        else:
            light.update(location=rec['location'], radius=rec['radius'], falloffExponent=rec['falloffExponent'],
                         lightSourceRadius=settings.get('LightSourceRadius', codec.UDK_POINT_SOURCE_RADIUS))
            if light['kind'] == 'spot':
                light.update(direction=rec['direction'], innerConeAngle=rec['innerConeAngle'],
                             outerConeAngle=rec['outerConeAngle'])
        found.append(light)
    return found


class Excluded(ValueError):
    """A component the relight leaves with its bake by rule (no LOD-0 texture lightmap, StaticLightingHiddenByDefault,
    every texel inside geometry): a valid exclusion, unlike a failure to read, bake or write it."""


def emits(light):
    """Whether a codec light puts any light down: on, and brighter than 0."""
    return bool(light.get('enabled', True)) and float(light.get('brightness', 1.0)) > 0


def light_box(light):
    """A codec light's radius around its place [x0, x1, y0, y1, z0, z1]; everything for a directional light."""
    if 'location' not in light:
        return [-INF, INF, -INF, INF, -INF, INF]
    return [v for c in light['location'] for v in (c - light['radius'], c + light['radius'])]


def short_name(path):
    parts = path.split('.')
    return parts[2] if len(parts) > 2 else path


def resolve_light_states(p, doc=None, remove_lights=()):
    """The lights before and after an edit (editor lights plan, 4.4), from the map `p` (the grown map, whose changed
    and added lights hold their new values) and the light edits native_copy.py wrote (`doc`, its --light-edits file:
    each edit's codec light before and after, None before for an addition and None after for a deletion, and the GUIDs
    the build added to each receiver's lightmap lists). The lights no edit names are read from the map, and are the
    same in both states; an edited light's dicts come from `doc` alone, never from the map. Each `remove_lights` name
    (an actor or component: --remove-light) is one more edit, taking an enabled baked light away. Returns dict(before,
    after: every light of each state, edits, registered: {component path: [guid hex]})."""
    staged = set((doc or {}).get('stagedAreas') or [])
    every = [light for light in map_lights(p, roles=None) if light['component'] not in staged]
    names = {l['component'] for l in every}
    edits = [dict(e) for e in (doc or {}).get('edits', [])]
    edited = set()
    for e in edits:
        if e['component'] in edited:
            raise ValueError(f'two light edits name {e["component"]}')
        edited.add(e['component'])
    lost = sorted(e['component'] for e in edits if e['component'] not in names)
    if lost:
        raise ValueError(f'the light edits name lights the map lacks: {lost}')
    for n in remove_lights:
        found = [l for l in every if l['enabled'] and l['role'] in BAKED_ROLES and names_match(l['component'], [n])]
        if not found:
            raise ValueError(f'no baked light named {[n]}')
        for l in found:
            if l['component'] in edited:
                raise ValueError(f'{n} is both removed and edited')
            edited.add(l['component'])
            edits.append(dict(op='remove', name=short_name(l['actor']), label=n, kind=l['kind'], role=l['role'],
                              component=l['component'], actor=l['actor'], before=l, after=None))
    base = [l for l in every if l['component'] not in edited]
    return dict(before=base + [e['before'] for e in edits if e.get('before')],
                after=base + [e['after'] for e in edits if e.get('after')], edits=edits,
                registered={k: list(v) for k, v in ((doc or {}).get('registered') or {}).items()})


def world_lightmass_settings(p):
    """The WorldInfo's explicit LightmassSettings members (StaticLightingLevelScale, EnvironmentColor, ...)."""
    wi = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'WorldInfo']
    return lightmass_settings(p, wi[0]) if wi else {}


INF = float('inf')


def box_of(triangles):
    """The world box [x0, x1, y0, y1, z0, z1] of an (n, 3, 3) triangle array."""
    pts = np.asarray(triangles, np.float64).reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return [float(v) for pair in zip(lo, hi) for v in pair]


def boxes_meet(a, b, grow=0.0):
    return all(a[2 * k] - grow <= b[2 * k + 1] and b[2 * k] - grow <= a[2 * k + 1] for k in range(3))


def component_box(p, i, meshes=None):
    """A mesh component's world box: its mesh's vertices through its world matrix (`meshes` caches the vertices)."""
    meshes = {} if meshes is None else meshes
    mi = p.effective(i, 'StaticMesh', 0)
    if mi not in meshes:
        meshes[mi] = lightmap_texels.component_mesh(p, i)['positions']
    m3 = lightmap_texels.world_matrix(p, i)
    return box_of(meshes[mi] @ m3[:3, :3].T + m3[:3, 3])


def receivers_near(p, boxes, radius):
    """The persistent level's mesh components with a LOD-0 texture lightmap whose world box comes within `radius` of
    any of `boxes`, in export order: the receivers an edit can reach. Their world boxes are their meshes' vertices
    through their world matrices."""
    found, meshes = [], {}
    for i in range(1, len(p.exports) + 1):
        if not p.cls(i).endswith('StaticMeshComponent') or not p.name(i).startswith('TheWorld.PersistentLevel.'):
            continue
        if p.effective(i, 'StaticMesh', 0) <= 0:
            continue            # no mesh in the package: no surface to relight (T-28)
        try:
            f = lightmap_fields.component_fields(p, i)
        except Exception:       # a component whose fields don't parse can't be relit either
            continue
        if not f['lods'] or f['lods'][0]['lightmap']['type'] != 2:
            continue
        if any(boxes_meet(component_box(p, i, meshes), b, radius) for b in boxes):
            found.append(p.name(i))
    return found


# The quick reach test (edit_reaches). Within REACH_NEAR of what an edit changes, its bounce can show (EXP-17 run 10:
# beyond 384 units no texel changed by more than 0.043, against a lit floor's 6 to 7); beyond, only a shadow the edit
# casts or lifts, or a light it removes, changes a receiver.
REACH_NEAR = 384.0
GRID = np.stack(np.meshgrid(*[np.linspace(0, 1, 5)] * 3, indexing='ij'), -1).reshape(-1, 3)


def grid_points(box):
    lo, hi = np.array(box[0::2]), np.array(box[1::2])
    return lo + GRID * (hi - lo)


def segments_meet_box(origins, ends, box):
    """Whether any segment origins[k] -> ends[k] passes through the box (slab test)."""
    return bool(np.any(segments_cross_box(origins, ends, box)))


def segments_cross_box(origins, ends, box):
    """Which segments origins[k] -> ends[k] pass through the box (slab test)."""
    lo, hi = np.array(box[0::2]), np.array(box[1::2])
    d = ends - origins
    with np.errstate(divide='ignore', invalid='ignore'):
        t0, t1 = (lo - origins) / d, (hi - origins) / d
    near, far = np.minimum(t0, t1), np.maximum(t0, t1)
    # a segment parallel to a slab is inside it for every t or for none
    flat = d == 0
    inside = (origins >= lo) & (origins <= hi)
    near = np.where(flat, np.where(inside, -np.inf, np.inf), near)
    far = np.where(flat, np.where(inside, np.inf, -np.inf), far)
    tmin, tmax = near.max(axis=1), far.min(axis=1)
    return (tmin <= tmax) & (tmax >= 0) & (tmin <= 1)


def light_reaches(light, box):
    """Whether the light can reach the box: a directional light always, a point or spot light within its radius."""
    if 'location' not in light:
        return True
    c = np.clip(light['location'], box[0::2], box[1::2])
    return float(np.linalg.norm(np.asarray(light['location']) - c)) <= light['radius']


def light_source_radius(light):
    """A point or spot light's source radius: its own, 0 included, else UDK's default (review finding 44: a deliberate
    0 read as the default)."""
    r = light.get('lightSourceRadius')
    return float(codec.UDK_POINT_SOURCE_RADIUS if r is None else r)


def light_source_angle(light):
    """A directional light's source angle (degrees): its own, 0 included (the dominant light's hard shadow), else
    UDK's default."""
    a = light.get('lightSourceAngle')
    return float(codec.UDK_DIRECTIONAL_SOURCE_ANGLE if a is None else a)


def shadow_meets(light, edit, box):
    """Whether the light, shining through the edit box, can land on the box: some segment from a point of the box to
    the light crosses the edit box, or some ray from the light through a point of the edit box goes on into the box.
    The edit box grows with the light's source size, for the penumbra."""
    far = 1e6
    if 'location' in light:
        L = np.asarray(light['location'], np.float64)
        grow = 8 + light_source_radius(light)
    else:
        to = np.asarray(light['toLight'], np.float64)
        to = to / np.linalg.norm(to)
        gap = max([max(box[2 * k] - edit[2 * k + 1], edit[2 * k] - box[2 * k + 1], 0) for k in range(3)])
        grow = 8 + gap * np.tan(np.radians(light_source_angle(light)))
    e = [v + (grow if k % 2 else -grow) for k, v in enumerate(edit)]
    pb, pe = grid_points(box), grid_points(e)
    if 'location' in light:
        if segments_meet_box(pb, np.broadcast_to(L, pb.shape), e):
            return True
        return segments_meet_box(pe, pe + (pe - L) * far / np.maximum(np.linalg.norm(pe - L, axis=1, keepdims=True), 1e-6), box)
    if segments_meet_box(pb, pb + to * far, e):
        return True
    return segments_meet_box(pe, pe - to * far, box)


def edit_reaches(box, edit_boxes, lights, removed_lights=(), near=REACH_NEAR, edited=()):
    """Whether an edit can change the light of a receiver with this world box (a quick test before relighting it; it
    errs towards yes): the receiver lies within `near` of what the edit changes in the geometry (`edit_boxes`: its
    bounce), a light the edit removes reached it, or a light that reaches it shines through an edit box onto it (a
    shadow cast or lifted, however long). `edited` are the codec lights of every light edit, before and after (a
    changed light's both, an added light's after, a deleted light's before): a receiver within `near` of the radius
    of any of them that emits is reached (its direct light inside the radius, its bounce near it), so a rotated,
    narrowed, dimmed or switched-off light revisits the receivers it lit as well as reaching new ones."""
    if any(boxes_meet(box, b, near) for b in edit_boxes):
        return True
    if any(light_reaches(l, box) for l in removed_lights):
        return True
    if any(emits(l) and boxes_meet(box, light_box(l), near) for l in edited):
        return True
    return any(shadow_meets(l, e, box) for l in lights if light_reaches(l, box) for e in edit_boxes)


def names_match(path, names):
    """Whether an export path (TheWorld.PersistentLevel.Actor.Component) is one of `names`: a full path or an actor."""
    parts = path.split('.')
    actor = parts[2] if len(parts) > 3 else None
    return any(n == path or n == actor for n in names)


class Scene:
    """What every component of one map shares: shadow casters (an Embree scene), their albedo, the baked lights, the
    emissive surfaces' generated area lights, and the WorldInfo's Lightmass settings.

    Triangles whose material lets light through (translucent glass, decals) cast no shadow and reflect nothing.

    An edit leaves out casters (`remove_casters`) and lights (`remove_lights`), each named by its actor (as
    `XComLevelActor_123`) or its component path, and adds copies of casters at new poses (`add_casters`: dicts of
    `source`, an actor name, and its copy's `location` and `rotation`, as the editor's compiler writes them). A copy
    casts shadows and reflects light as its source does; its triangles' owners are negative (-1 for the first).

    `lights`, when given, are the lights of this state (resolve_light_states: an edit's before or after state), in
    place of the map's own: its registry, through which a lightmap's GUIDs resolve (`listed`), and its baked lights,
    area lights and bounce sources. `registered` ({component path: [guid hex]}, the before state's) are the GUIDs a
    build added to receivers' lightmap lists, which the state before the edit leaves out (`original_guids`). `note`
    adds to the edit's record. `ignore_casters` (actor names) are not of the map at all (pieces of other maps as
    transplant.py staged them, which no level lists): no state has them, and they are no part of the edit."""

    def __init__(self, p, samples=64, bounce_rays=64, stride=2, emissive=True, source_radius=None, remove_casters=(),
                 remove_lights=(), add_casters=(), source_estimate='mean', source_per_disc=40, source_bounces=1,
                 source_box=None, lights=None, registered=None, note=None, ignore_casters=()):
        import albedo as albedo_module
        self.samples, self.bounce_rays, self.stride, self.emissive = samples, bounce_rays, stride, emissive
        self.source_radius, self._source = source_radius, None
        self.source_estimate, self.source_per_disc = source_estimate, source_per_disc
        self.source_bounces, self.source_box = source_bounces, source_box
        adds = [dict(source=a['source'], location=[float(v) for v in a['location']],
                     rotation=[int(v) for v in a['rotation']]) for a in add_casters]
        self.edit = dict(removeCasters=sorted(remove_casters), removeLights=sorted(remove_lights),
                         addCasters=sorted(adds, key=json.dumps))
        self.edit.update(note or {})
        self._removed_lights = set(remove_lights)
        settings = world_lightmass_settings(p)
        self.level_scale = float(settings.get('StaticLightingLevelScale', 1.0))
        colour = settings.get('EnvironmentColor', dict(R=0, G=0, B=0))
        if isinstance(colour, str):          # an unparsed struct: four colour bytes B, G, R, A
            raw = bytes.fromhex(colour)
            colour = dict(B=raw[0], G=raw[1], R=raw[2])
        intensity = float(settings.get('EnvironmentIntensity', 1.0))
        self.environment = bounce.environment_radiance([colour['R'], colour['G'], colour['B']], intensity)
        if int(settings.get('NumIndirectLightingBounces', 3)) < 1:
            self.bounce_rays = 0
        tris, owners, mats = shadows.caster_triangles(p, materials=True)
        if ignore_casters:
            staged = [o for o in np.unique(owners) if names_match(p.name(int(o)), ignore_casters)]
            ours = ~np.isin(owners, staged)
            tris, owners, mats = tris[ours], owners[ours], mats[ours]
        casters = np.unique(owners)
        actors = {p.name(i) for i in range(1, len(p.exports) + 1)}
        removed = [o for o in casters if names_match(p.name(int(o)), remove_casters)]
        # a piece of the map that casts no shadow (CastShadow off, as some of URB_PoliceStation's are) removes nothing;
        # a name the map doesn't have is a mistake
        missing = [n for n in remove_casters if not any(names_match(p.name(int(o)), [n]) for o in removed)
                   and n not in actors and 'TheWorld.PersistentLevel.' + n not in actors]
        if missing:
            raise ValueError(f'no actor or component named {missing}')
        keep = ~np.isin(owners, removed)
        # where the edit changes the geometry: each removed caster where it stood, each copy at its pose
        self.edit_boxes = [box_of(tris[owners == o]) for o in removed]
        # what each edit box is, for the kept pieces of the last build (PieceCache): its triangles where they stand
        self.edit_keys = [hashlib.sha1(np.ascontiguousarray(tris[owners == o]).tobytes()).hexdigest() for o in removed]
        tris, owners, mats = [tris[keep]], [owners[keep]], [mats[keep]]
        self.copies = []
        for k, add in enumerate(self.edit['addCasters']):
            if 'TheWorld.PersistentLevel.' + add['source'] not in actors:
                raise ValueError(f'no actor named {add["source"]} to copy')
            # the source's casters as the map has them (a moved piece is also removed at its old place); a copy of a
            # piece that casts no shadow adds nothing
            comps = [int(o) for o in casters if names_match(p.name(int(o)), [add['source']])]
            n = 0
            if comps:
                t, _, m = shadows.caster_triangles(p, comps, materials=True, pose=(add['location'], add['rotation']))
                tris.append(t), owners.append(np.full(len(t), -(k + 1), np.int32)), mats.append(m)
                n = int(len(t))
                self.edit_boxes.append(box_of(t))
                self.edit_keys.append(hashlib.sha1(np.ascontiguousarray(t).tobytes()).hexdigest())
            self.copies.append(dict(add, triangles=n))
        tris, owners, mats = np.concatenate(tris), np.concatenate(owners), np.concatenate(mats)
        alb = albedo_module.Albedo(p)
        unique = np.unique(mats)
        passes = [m for m in unique if alb.transmits(int(m))]
        solid = ~np.isin(mats, passes)
        self.triangles, self.owners, self.materials = tris[solid], owners[solid], mats[solid]
        table = np.array([alb(int(m)) for m in unique])
        self.albedo_per_triangle = table[np.searchsorted(unique, self.materials)]
        self.occluder = shadows.Occluder(self.triangles)
        # this state's lights: every light of the map (a lightmap's GUIDs resolve through them), and the baked ones
        self.registry = list(lights) if lights is not None else map_lights(p, roles=None)
        self.registered = {k: set(v) for k, v in (registered or {}).items()}
        every = [l for l in self.registry if l['enabled'] and l['role'] in BAKED_ROLES]
        missing = [n for n in remove_lights if not any(names_match(l['component'], [n]) for l in every)]
        if missing:
            raise ValueError(f'no baked light named {missing}')
        self.lights = [l for l in every if self.keeps(l)]
        # a removed light changes what it reached: its radius around it (a directional light reaches everything);
        # kept apart from the geometry's edit boxes, which shadows are traced through
        self.light_boxes = [light_box(l) for l in every if not self.keeps(l)]
        self.area_lights = [l for l in self.lights if l['role'] == 'area']
        self.settings = settings
        # albedoSources over sorted keys: a set's order changes with each process's string hashing, and a piece's
        # report (kept in the piece cache's .npz) is written in its keys' order
        notes = list(alb.notes.values())
        self.counts = dict(casters=len(set(self.owners.tolist())), triangles=int(len(self.triangles)),
                           transmittingTriangles=int((~solid).sum()), materials=int(len(unique)),
                           albedoSources={k: notes.count(k) for k in sorted(set(notes))},
                           bakedLights=len(self.lights), areaLights=len(self.area_lights))

    def keeps(self, light):
        """Whether the edit keeps this light."""
        return not names_match(light['component'], self._removed_lights)

    def listed(self, guids):
        """The lights of this state whose LightmapGuid or LightGuid is in `guids` (a lightmap's list), once each, in
        the registry's order: both GUIDs name one light."""
        want = set(guids)
        return [l for l in self.registry if want & set(l.get('guids') or [l.get('guid')])]

    def original_guids(self, path, guids):
        """A receiver's lightmap list as the original bake had it: `guids` without those a build added to the
        component `path` (`registered`), so a newly listed light invents no contribution to the original bake."""
        added = self.registered.get(path, ())
        return [g for g in guids if g not in added]

    @property
    def source(self):
        """The bounce sources' smoothed direct light (bounce.SourceIrradiance), built on first use; None when the
        scene gathers from each hit's own direct light."""
        if self.source_radius and self._source is None:
            self._source = bounce.SourceIrradiance(self.occluder, self.triangles, self.lights, self.source_radius,
                                                   seed=11, per_disc=self.source_per_disc,
                                                   estimate=self.source_estimate, bounces=self.source_bounces,
                                                   albedo=self.albedo_per_triangle, environment=self.environment,
                                                   box=self.source_box)
        return self._source

    def describe(self):
        return dict(shadows=True, shadowSamples=self.samples, emissive=self.emissive, bounce=self.bounce_rays > 0,
                    bounceRays=self.bounce_rays, gatherStride=self.stride, sourceRadius=self.source_radius,
                    **({} if not self.source_radius else dict(sourceEstimate=self.source_estimate,
                                                              sourcePerDisc=self.source_per_disc,
                                                              sourceBounces=self.source_bounces)),
                    levelScale=self.level_scale,
                    environment=[float(v) for v in self.environment], worldLightmassSettings={
                        k: v for k, v in self.settings.items() if not isinstance(v, bytes)}, **self.counts)


def flat_light(nac, dmc, scale):
    """What a flat surface would get from stored texels: colour times the summed directional values (EXP-17)."""
    colour, directional = codec.decode(nac, dmc, scale)
    return colour * directional.sum(-1, keepdims=True)


def direct_coefficients(scene, lights, geo, idx=None):
    """Our direct light at the texels `idx` of `geo` (all of them by default): (n, 3 basis, 3 colour). Without a
    Scene, the listed `lights` unshadowed; with one, those the scene keeps, shadowed, with its area lights."""
    world, frames = geo['world'], geo['frames']
    if idx is not None:
        world, frames = world[idx], frames[idx]
    if scene is None:
        return codec.coefficients(lights, world, frames)
    direct_lights = [l for l in lights if scene.keeps(l)] + (scene.area_lights if scene.emissive else [])
    if len(world):
        # only the lights whose radius meets the texels: every piece is handed the map's every area light, and one
        # out of reach adds nothing (faster-bake plan, 3.3)
        box = [float(v) for pair in zip(world.min(0), world.max(0)) for v in pair]
        direct_lights = [l for l in direct_lights if light_reaches(l, box)]
    return codec.coefficients(direct_lights, world, frames, visibility=lambda light, lit: shadows.light_visibility(
        scene.occluder, light, world[lit], frames[lit, 2], samples=scene.samples, seed=shadows.light_seed(light),
        level_scale=scene.level_scale))


def gathers(scene):
    return scene is not None and scene.bounce_rays > 0


GATHER_CHUNK = 8192     # gather points worked out at a time: half a million rays, whatever the piece's size


def gather_coefficients(scene, geo, gidx):
    """The bounce gathered at the texels `gidx` of `geo` (indices): (n, 3, 3). In chunks, which bounds the memory a
    piece needs; a point's rays depend on its position alone, so the chunks give what one call gives."""
    world, frames = geo['world'], geo['frames']
    if not len(gidx):
        return np.zeros((0, 3, 3))
    return np.concatenate([
        bounce.gather(scene.occluder, scene.triangles, scene.albedo_per_triangle, scene.lights,
                      world[part], frames[part], rays=scene.bounce_rays, seed=7,
                      environment=scene.environment, source=scene.source)
        for part in (gidx[k:k + GATHER_CHUNK] for k in range(0, len(gidx), GATHER_CHUNK))])


def texel_size(geo):
    """The median world step between neighbouring texels of `geo` (1 for a single texel)."""
    world = geo['world']
    steps = np.linalg.norm(np.diff(world[np.lexsort((geo['px'], geo['py']))], axis=0), axis=1)
    return float(np.median(steps)) if len(steps) else 1.0      # one texel: no spacing, nothing to blur across


def smooth_indirect(scene, geo, gidx, gathered, idx=None):
    """The gathered bounce spread to the texels `idx` of `geo` (all by default): (n, 3, 3), and the filter's width."""
    world, frames = geo['world'], geo['frames']
    sigma = scene.stride * texel_size(geo)
    tw, tn = (world, frames[:, 2]) if idx is None else (world[idx], frames[idx, 2])
    if not len(tw):
        return np.zeros((0, 3, 3)), sigma
    return bounce.smooth(world[gidx], frames[gidx, 2], gathered, tw, tn, sigma=sigma), sigma


def model_coefficients(scene, lights, geo):
    """Our light at the texels of `geo`: (n, 3 basis, 3 colour) coefficients and gather statistics. Without a Scene,
    the listed `lights` unshadowed; with one, those the scene keeps, shadowed, with its area lights and bounce."""
    coef = direct_coefficients(scene, lights, geo)
    if not gathers(scene):
        return coef, {}
    gidx = np.nonzero(bounce.gather_points(geo['px'], geo['py'], scene.stride))[0]
    indirect, sigma = smooth_indirect(scene, geo, gidx, gather_coefficients(scene, geo, gidx))
    return coef + indirect, gather_stats(scene, gidx, sigma, indirect, coef + indirect)


def gather_stats(scene, gidx, sigma, indirect, coef):
    return dict(gatherPoints=int(len(gidx)), raysPerPoint=scene.bounce_rays, filterSigma=sigma,
                indirectShare=float(codec.encode(indirect)['dmcLinear'].sum() /
                                    max(codec.encode(coef)['dmcLinear'].sum(), 1e-12)))


# A piece with more texels to relight than this is relit in bands of about this many, each a job of its own, and
# put together afterwards (faster-bake plan, 3.4): one large floor otherwise holds a worker for a minute while the
# others stand idle, and its gather takes arrays of millions of rays.
BAND_TEXELS = 20000
# The quick reach test for each texel may make this many segment tests for a piece; beyond it every texel counts as
# in reach (a cleared map's thousand edit boxes reach everything anyway).
REACH_BUDGET = 2.0e8
# A piece whose largest change is under this keeps its bake (faster-bake plan, 5.1): EXP-17 runs 10 and 11 found
# changes of this size beyond the edit's reach (0.043 and 0.045 against a lit floor's 6 to 7), which the quick test
# has always left alone.
CHANGE_FLOOR = 0.043
# The original slot scale stays while the relit light goes no more than this over it (the excess is clipped: 1%
# of light at the brightest texel is under half a step of what the texture stores; a texel at the scale that gains
# a millionth must not send the whole rectangle to be stored again).
SCALE_FITS = 1.01


def axis_gap(world, box):
    """Each point's largest distance to the box along one axis (0 inside it): boxes_meet's measure, for points."""
    lo, hi = np.asarray(box[0::2], float), np.asarray(box[1::2], float)
    return np.maximum(np.maximum(lo - world, world - hi), 0.0).max(1)


def texel_reach(world, box, edit_boxes, lights, edited=(), near=REACH_NEAR, budget=REACH_BUDGET):
    """Which of a piece's texels (`world`, with the piece's world box) an edit can change: edit_reaches' rule for
    each texel instead of the piece's box (faster-bake plan, 3.5). A texel is in reach when it lies within `near` of
    an edit box or of an emitting edited light's radius, or when a line from it to a light that reaches it passes
    through an edit box grown for the light's size. It errs towards yes, and says yes for every texel where the
    shadow test would cost more than `budget` segment tests."""
    n = len(world)
    reach = np.zeros(n, bool)
    for e in edit_boxes:
        if boxes_meet(box, e, near):
            reach |= axis_gap(world, e) <= near
    for l in edited:
        if emits(l) and boxes_meet(box, light_box(l), near):
            reach |= axis_gap(world, light_box(l)) <= near
    if reach.all():
        return reach
    lit = [l for l in lights if light_reaches(l, box)]
    pairs = [(l, e) for e in edit_boxes if shadows_meet(lit, e, box) for l in lit if shadow_meets(l, e, box)]
    if len(pairs) * n > budget:
        return np.ones(n, bool)
    for l, e in pairs:
        rest = np.nonzero(~reach)[0]
        if not len(rest):
            break
        w = world[rest]
        if 'location' in l:
            L = np.asarray(l['location'], np.float64)
            inside = np.linalg.norm(w - L, axis=1) <= l['radius']
            grow = 8 + light_source_radius(l)
            rest, w = rest[inside], w[inside]
            ends = np.broadcast_to(L, w.shape)
        else:
            to = np.asarray(l['toLight'], np.float64)
            to = to / np.linalg.norm(to)
            gap = max([max(box[2 * k] - e[2 * k + 1], e[2 * k] - box[2 * k + 1], 0) for k in range(3)])
            grow = 8 + gap * np.tan(np.radians(light_source_angle(l)))
            ends = w + to * 1e6
        if not len(rest):
            continue
        g = [v + (grow if k % 2 else -grow) for k, v in enumerate(e)]
        reach[rest[segments_cross_box(w, ends, g)]] = True
    return reach


def prepare_component(p, path, scene=None, checker=None, after=None, source=None, fresh=False, reach=None):
    """Everything of one component's relight short of the light itself (see relight_component): its fields, the lights
    of each state, its texels (the buried ones left out) and which of them are to be relit. `reach` (dict(edit_boxes,
    edited), an edit's) leaves out the texels the edit can't change, for a piece of the map relit as a change: they
    keep the original bake exactly. Returns the work dict that compute_component and assemble_component take."""
    ci = p.by_name.get(path)
    if ci is None:
        raise ValueError(f'no export {path}')
    if (source is not None or fresh) and after is None:
        raise ValueError('a copy is relit in the scene after the edit: it needs one')
    if p.own(ci, 'StaticLightingHiddenByDefault', False):
        # URB_Bar's one such component, a corner column inside the wall pieces that shows once they break, was
        # baked lit as if they were not there; our shadows make it black, so it keeps its bake
        raise Excluded(f'{path} is StaticLightingHiddenByDefault')
    rec = lighting.component_record(p, ci)
    lm = rec['lods'][0]['lightmap'] if rec['lods'] else None
    if not lm or lm['type'] != 2:
        raise Excluded(f'{path} has no LOD-0 texture lightmap')
    fields = lightmap_fields.component_fields(p, ci)['lods'][0]['lightmap']
    nac_tex, dmc_tex = (fields['slots'][k]['index'] for k in (0, 1))
    tex = lightmap_fields.texture_fields(p, dmc_tex)
    size = [tex['mips'][0]['width'], tex['mips'][0]['height']]
    # the lights its lightmap lists, through each state's registry: after the edit, its list as it is now; before,
    # its list as the original bake had it (without the GUIDs a build added), with the lights as they were
    if scene is None:
        lights = component_lights(p, lm['lightGuids'])
        before_lights = lights
    else:
        lights = (after or scene).listed(lm['lightGuids'])
        before_lights = scene.listed(scene.original_guids(path, lm['lightGuids']))
    unmatched = len(set(lm['lightGuids']) - {g for l in lights for g in (l.get('guids') or [l['guid']])})
    active = [l for l in lights if l['enabled']]
    active_before = [l for l in before_lights if l['enabled']]
    mesh = lightmap_texels.component_mesh(p, ci)
    matrix = lightmap_texels.world_matrix(p, ci)
    geo = lightmap_texels.rasterise(mesh, matrix, fields, size)
    if not len(geo['world']):
        # (whatever the scene: without one, nothing below would catch it, review finding 44)
        raise Excluded(f'{path} covers no texel of its lightmap')
    geo_b = geo
    if source is not None:
        si = p.by_name.get(source)
        if si is None:
            raise ValueError(f'no export {source}')
        src_fields = lightmap_fields.component_fields(p, si)['lods'][0]['lightmap']
        if p.effective(si, 'StaticMesh', 0) != p.effective(ci, 'StaticMesh', 0) or any(
                src_fields[k] != fields[k] for k in ('coordinateScale', 'coordinateBias')):
            raise ValueError(f'{path} is not laid out as its source {source}')
        geo_b = lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, si), src_fields, size)
        if not (np.array_equal(geo_b['px'], geo['px']) and np.array_equal(geo_b['py'], geo['py'])):
            raise ValueError(f'{path}: its texels are not its source\'s')
        src_guids = lighting.component_record(p, si)['lods'][0]['lightmap']['lightGuids']
        # the source where it stands, with the lights its lightmap listed in the original bake, as they were
        active_before = [l for l in scene.listed(scene.original_guids(source, src_guids)) if l['enabled']] \
            if scene is not None else [l for l in component_lights(p, src_guids) if l['enabled']]
    buried, opened = 0, None
    if fresh:
        # a texel buried where the copy stands is left out, and takes its neighbours' light by the dilation
        inside = bounce.buried_texels(after.occluder, geo['world'], geo['frames'], after.level_scale)
        buried = int(inside.sum())
        if inside.all():
            raise Excluded(f'all {buried} texels of {path} lie inside geometry')
        geo = dict(geo, **{k: geo[k][~inside] for k in ('px', 'py', 'world', 'frames', 'triangle')})
        geo_b = geo
    elif scene is not None and source is not None:
        # a texel buried where either stands keeps the source's bake (its neighbours' change spreads into it)
        inside = (bounce.buried_texels(scene.occluder, geo_b['world'], geo_b['frames'], scene.level_scale) |
                  bounce.buried_texels(after.occluder, geo['world'], geo['frames'], after.level_scale))
        buried = int(inside.sum())
        if inside.all():
            raise Excluded(f'all {buried} texels of {path} lie inside geometry')
        keys = ('px', 'py', 'world', 'frames', 'triangle')
        geo = dict(geo, **{k: geo[k][~inside] for k in keys})
        geo_b = dict(geo_b, **{k: geo_b[k][~inside] for k in keys})
    elif scene is not None:
        # texels inside geometry are left out: the unburied texels' values spread into those at their edges, and the
        # rest keep the original bake (they show only once something breaks)
        inside = bounce.buried_texels(scene.occluder, geo['world'], geo['frames'], scene.level_scale)
        if after is not None and (after.edit['removeCasters'] or after.edit['addCasters']):
            # a texel inside a removed piece (the floor under a crate standing on it) is open after the edit; one
            # inside an added copy is relit too, and comes out dark (its rays hit the copy's back faces)
            inside_after = bounce.buried_texels(after.occluder, geo['world'], geo['frames'], after.level_scale)
            opened = inside & ~inside_after
            inside &= inside_after
        buried = int(inside.sum())
        if inside.all():
            raise Excluded(f'all {buried} texels of {path} lie inside geometry')
        opened = opened[~inside] if opened is not None else None
        geo = dict(geo, **{k: geo[k][~inside] for k in ('px', 'py', 'world', 'frames', 'triangle')})
        geo_b = geo
    mode = 'fresh' if fresh else 'delta' if after is not None else 'absolute'
    if mode == 'delta' and checker:
        raise ValueError('an edit is relit as a change; the checker compares absolute relights')
    main = after if fresh else scene            # the scene the first (or only) light is worked out in
    n = len(geo['world'])
    tidx = np.arange(n)
    gidx = np.nonzero(bounce.gather_points(geo['px'], geo['py'], main.stride))[0] if gathers(main) else np.zeros(0, int)
    if reach is not None and mode == 'delta' and source is None and scene is not None and n:
        # only the texels the edit can change, and the gather points the smoothing of those reads
        world = geo['world']
        can = texel_reach(world, box_of(world), reach['edit_boxes'], scene.lights, reach.get('edited') or ())
        if not can.all():
            tidx = np.nonzero(can)[0]
            if len(gidx) and len(tidx):
                from scipy.spatial import cKDTree
                margin = 3.0 * main.stride * texel_size(geo)
                d, _ = cKDTree(world[tidx]).query(world[gidx], k=1, distance_upper_bound=margin)
                gidx = gidx[np.isfinite(d)]
            elif not len(tidx):
                gidx = gidx[:0]
    return dict(path=path, source=source, fresh=bool(fresh), mode=mode, checker=checker, ci=ci, lm=lm, fields=fields,
                textures=(nac_tex, dmc_tex), size=size, lights=lights, unmatched=unmatched, active=active,
                active_before=active_before, mesh=dict(mesh=mesh['mesh'], channel=mesh['channel']), geo=geo,
                geo_b=geo_b, buried=buried, opened=opened, tidx=tidx, gidx=gidx, whole=len(tidx) == n)


def band_of(work, band=None):
    """(texel indices, gather indices) of band (k, count) of the work: the k-th share of each; all without a band."""
    if band is None:
        return work['tidx'], work['gidx']
    k, count = band
    return np.array_split(work['tidx'], count)[k], np.array_split(work['gidx'], count)[k]


def compute_component(work, scene=None, after=None, band=None):
    """Our light for one prepared component, or for one band of it: the texels' direct light and the gather points'
    bounce, in each scene its mode needs. Every value depends on its own texel alone (a texel's rays turn by its
    position), so the bands of a piece give together what the piece gives whole."""
    tidx, gidx = band_of(work, band)
    out = {}
    if not len(work['tidx']):
        return out          # no texel of it is in the edit's reach: nothing to work out
    if work['mode'] == 'fresh':
        states = [('first', after, work['active'], work['geo'])]
    else:
        states = [('first', scene, work['active_before'], work['geo_b'])]
        if work['mode'] == 'delta':
            states.append(('after', after, work['active'], work['geo']))
    for key, sc, lights, geo in states:
        out[key + '_direct'] = direct_coefficients(sc, lights, geo, tidx)
        if gathers(sc):
            out[key + '_gathered'] = gather_coefficients(sc, geo, gidx)
    return out


def join_parts(parts):
    """The bands' results (compute_component's, in band order) as one."""
    return {k: np.concatenate([part[k] for part in parts]) for k in parts[0]}


def reaching_boxes(box, edit_boxes, lights, near=REACH_NEAR, first=False):
    """Which edit boxes (indices) can change a receiver with this world box by themselves: edit_reaches' rule for the
    geometry, one edit box at a time. `first`: stop at the first found (whether any does)."""
    found, lit = [], None
    for k, e in enumerate(edit_boxes):
        if boxes_meet(box, e, near):
            found.append(k)
        else:
            if lit is None:
                lit = [l for l in lights if light_reaches(l, box)]
            if shadows_meet(lit, e, box):
                found.append(k)
        if first and found:
            break
    return found


def shadows_meet(lights, edit, box):
    """Whether any of `lights` (each reaching the box), shining through the edit box, can land on the box: shadow_meets
    for each, with the point and spot lights of one source size tested together."""
    far = 1e6
    groups = {}
    for l in lights:
        if 'location' not in l:
            if shadow_meets(l, edit, box):
                return True
            continue
        groups.setdefault(8 + light_source_radius(l), []).append(l)
    pb = grid_points(box)
    for grow, some in groups.items():
        e = [v + (grow if k % 2 else -grow) for k, v in enumerate(edit)]
        L = np.asarray([l['location'] for l in some], np.float64)            # (m, 3)
        if segments_cross_box(np.tile(pb, (len(L), 1)), np.repeat(L, len(pb), 0), e).any():
            return True
        pe = grid_points(e)
        o = np.tile(pe, (len(L), 1))
        d = o - np.repeat(L, len(pe), 0)
        ends = o + d * far / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
        if segments_cross_box(o, ends, box).any():
            return True
    return False


def assemble_component(p, work, parts, scene=None, after=None, exact=False):
    """The texture images and the report of one component from its prepared work and its light (compute_component's
    result, the bands joined). See relight_component."""
    path, source, fresh, mode, checker = (work[k] for k in ('path', 'source', 'fresh', 'mode', 'checker'))
    fields, geo, geo_b, tidx, gidx = (work[k] for k in ('fields', 'geo', 'geo_b', 'tidx', 'gidx'))
    nac_tex, dmc_tex = work['textures']
    lm, lights, active, active_before = (work[k] for k in ('lm', 'lights', 'active', 'active_before'))
    main = after if fresh else scene
    whole = work['whole']
    if not len(tidx):
        # no texel of it is in the edit's reach (texel_reach): it keeps its bake
        return dict(unchanged=True, report=dict(
            component=path, copyOf=source, fresh=False, mesh=work['mesh']['mesh'], rect=list(geo['rect']),
            atlas=work['size'], texels=dict(covered=int(len(geo['world'])), buried=work['buried'], inReach=0),
            delta=dict(maxFlatChange=0.0, texelsChanged=0, edit=after.edit)))

    def total(key, sc, g):
        """A state's light at the texels relit: its direct light and its smoothed bounce."""
        coef = parts[key + '_direct']
        if not gathers(sc):
            return coef, {}
        indirect, sigma = smooth_indirect(sc, g, gidx, parts[key + '_gathered'], None if whole else tidx)
        coef = coef + indirect
        return coef, gather_stats(sc, gidx, sigma, indirect, coef)

    coef, stats = total('first', main, geo if fresh else geo_b)
    world = geo['world']
    x0, y0, x1, y1 = geo['rect']
    h, w = y1 - y0, x1 - x0
    iy, ix = geo['py'] - y0, geo['px'] - x0
    covered = np.zeros((h, w), bool)
    covered[iy, ix] = True
    orig_nac = top_mip_rect(p, nac_tex, x0, y0, x1, y1)
    orig_dmc = top_mip_rect(p, dmc_tex, x0, y0, x1, y1)
    orig_scale = fields['slots'][1]['scale']
    delta = None
    only_changed = False
    ours = np.ones(len(world), bool)
    if fresh:
        # nothing of the textures' own is kept: black where our light doesn't reach
        black = np.zeros_like(orig_dmc)
        images, scale, rest, ours = absolute_images(coef, geo, covered, black, black, [1.0, 1.0, 1.0], None, ours)
        flat = codec.encode(coef)['dmcLinear'].sum(1)
        delta = dict(maxFlatChange=float(flat.max(initial=0.0)), texelsChanged=int(len(world)))
    elif mode == 'delta':
        # the original bake plus what the edit changes in our model: unchanged light stays EW's exactly
        coef_after, _ = total('after', after, geo)
        colour, directional = codec.decode(orig_nac, orig_dmc, orig_scale)           # (h, w, 3) each
        original = directional[..., :, None] * colour[..., None, :]                   # (h, w, 3 basis, 3 colour)
        change = coef_after - coef
        safe = np.where(coef > 1e-9, coef, 1.0)
        ratio = np.clip(coef_after / safe, 0.0, 1.0)
        # the change and the ratio spread from our texels to their neighbours (chart gutters, buried edges), which
        # keep their own original light; texels beyond keep the original as it is. The texels the edit can't reach
        # are not worked out: no change, the ratio 1
        spread_in = np.zeros((h, w, 27))
        if not whole:
            spread_in[iy, ix, 9:18] = 1.0
        spread_in[iy[tidx], ix[tidx]] = np.concatenate([change.reshape(-1, 9), ratio.reshape(-1, 9),
                                                        coef.reshape(-1, 9)], 1)
        spread, grown = lightmap_texels.dilate(spread_in, covered)
        ch, ra, bf = (spread[..., k * 9:(k + 1) * 9].reshape(h, w, 3, 3) for k in range(3))
        relit = original.copy()
        relit[grown] = apply_change(original[grown], bf[grown], ch[grown], ra[grown])
        rest = ~grown
        out = codec.encode(relit.reshape(-1, 3, 3))
        scale = out['dmcScale']
        images = {'nac': out['nac'].reshape(h, w, 3), 'dmc': out['dmc'].reshape(h, w, 3)}
        images['nac_mask'] = images['dmc_mask'] = np.ones((h, w), bool)
        fits = np.asarray(orig_scale, float)
        if exact and (fits > 0).all() and (out['dmcLinear'].max(0, initial=0.0) <= fits * SCALE_FITS).all():
            # the light still fits under the original slot scale: it stays, so the texels the edit leaves alone keep
            # their stored values, and only the texels it changes are written (faster-bake plan, 5.2)
            scale = [float(v) for v in fits]
            images['dmc'] = (np.clip(out['dmcLinear'] / fits, 0, 1) ** (1 / codec.GAMMA)).reshape(h, w, 3)
            touched = np.zeros((h, w), bool)
            touched[grown] = (relit[grown] != original[grown]).any((1, 2))
            images['nac_mask'] = images['dmc_mask'] = touched
            only_changed = True
        flat_change = (codec.encode(np.abs(change))['dmcLinear']).sum(1)
        flat_original = (directional.sum(-1) * colour.max(-1))[iy, ix][tidx]
        delta = dict(maxFlatChange=float(flat_change.max(initial=0.0)),
                     texelsChanged=int(((flat_change > 0.01) & (flat_change > 0.02 * flat_original)).sum()))
    else:
        images, scale, rest, ours = absolute_images(coef, geo, covered, orig_nac, orig_dmc, orig_scale, checker, ours)
    out = dict(dmcScale=scale)
    # comparison with the original bake on the covered texels that carry our light
    before = flat_light(orig_nac, orig_dmc, orig_scale)
    relit_flat = flat_light(np.where(images['nac_mask'][..., None], images['nac'], orig_nac) if only_changed
                            else images['nac'],
                            np.where(images['dmc_mask'][..., None], images['dmc'], orig_dmc) if only_changed
                            else images['dmc'], out['dmcScale'])
    b, a = before[iy, ix][ours].sum(1), relit_flat[iy, ix][ours].sum(1)
    opened = work['opened']
    report = dict(component=path, copyOf=source, fresh=bool(fresh), mesh=work['mesh']['mesh'],
                  lightmapChannel=work['mesh']['channel'],
                  rect=[x0, y0, x1, y1], atlas=work['size'],
                  texels=dict(rect=h * w, covered=int(covered.sum()), buried=work['buried'],
                              opened=0 if opened is None else int(opened.sum()),
                              keptOriginal=int(rest.sum()), ours=int(ours.sum()),
                              **({} if whole else {'inReach': int(len(tidx))})),
                  checker=checker,
                  lights=dict(guids=len(lm['lightGuids']), matched=len(lights), unmatched=work['unmatched'],
                              disabled=len(lights) - len(active),
                              kinds={k: sum(l['kind'] == k for l in active) for k in ('point', 'spot', 'directional')},
                              sourceRadii=sorted({l.get('lightSourceRadius') for l in active if 'location' in l}),
                              **({} if source is None else dict(
                                  source=len(active_before),
                                  added=sorted({l['component'] for l in active} -
                                               {l['component'] for l in active_before})))),
                  scales=dict(original=orig_scale, relit=out['dmcScale']),
                  flatLight=flat_light_stats(b, a),
                  model=scene.describe() if scene is not None else dict(shadows=False, emissive=False, bounce=False),
                  delta=None if delta is None else dict(delta, edit=after.edit),
                  bounce=stats,
                  lightList=[{k: v for k, v in l.items() if k not in ('guid', 'guids')} for l in active])
    return dict(report=report, images=images, before=before, after=relit_flat, covered=covered, scale=out['dmcScale'],
                fields=fields, onlyChanged=only_changed)


def relight_component(p, path, scene=None, checker=None, after=None, source=None, fresh=False, reach=None,
                      exact=False):
    """Relight one component. Without a Scene: direct light only, unshadowed (EXP-17 run 5). With one: shadows,
    emissive surfaces' area lights, and one bounce when the scene gathers. With `after` (the same map's Scene with an
    edit: casters or lights left out), the texels get the original bake plus our light after the edit minus before.

    A native copy (native_copy.py) gives `source`, the path of the component it copies. Its cloned textures hold the
    source's bake, so before is our light on the source where it stands, from the lights its lightmap lists, and
    after is our light on the copy where it stands, from the lights the copy's lightmap lists (the source's, and any
    that reach only the copy's place). The two share the mesh and the lightmap's layout, so each texel is the same
    point of the piece at the two poses.

    `fresh`: a copy of a piece of another map (--foreign-copy). Its textures hold that map's bake, which says nothing
    of this one: its texels are our light in the scene after the edit, from the lights its lightmap lists, and the
    texels of its rectangle that our light and its dilation don't reach are black.

    `reach` (dict(edit_boxes, edited)): in an edit, only the texels the edit can change are relit (texel_reach).
    `exact`: in an edit, the original slot scale stays where the light fits under it, and only the changed texels
    are written (the result's `onlyChanged`, with the images' masks).

    The work is in three steps, so that a large piece can be relit in bands by several workers: prepare_component,
    compute_component (once, or once for each band) and assemble_component."""
    work = prepare_component(p, path, scene, checker=checker, after=after, source=source, fresh=fresh, reach=reach)
    return assemble_component(p, work, compute_component(work, scene, after), scene, after, exact=exact)


def flat_light_stats(b, a):
    """Original (b) against relit (a) flat light on our texels. A small or dark component can leave too few texels
    for a statistic: that one is None (not NaN, which isn't JSON)."""
    lit = b > 0.05
    fine = len(b) > 1 and np.std(b) > 0 and np.std(a) > 0
    return dict(originalMedian=float(np.median(b)) if len(b) else None,
                relitMedian=float(np.median(a)) if len(a) else None,
                correlation=float(np.corrcoef(b, a)[0, 1]) if fine else None,
                within10pct=float(np.mean(np.abs(np.log2(np.maximum(a[lit], 1e-3) / np.maximum(b[lit], 1e-3)))
                                          < 0.15)) if lit.any() else None)


def apply_change(original, before, change, ratio):
    """The original bake's coefficients after an edit that changes our model's light by `change` (`ratio` = after /
    before, clipped to 0-1). Light added adds. Light taken away goes by two routes, weighted by how much of the
    original our model accounts for (before / original):
    - scaled, original x after / before, where our model accounts for most of it: this keeps the original's own
      texture (and its compression error) in proportion when most of the light goes;
    - subtracted, where our model accounts for little: there the ratio is noise, and the change is only what our model
      knows. The subtraction never goes below the scaled value (where our model puts more of a light than Lightmass
      did, it would go below zero)."""
    scaled = original * ratio
    subtracted = np.maximum(original + change, scaled)
    weight = np.clip(before / np.where(original > 1e-9, original, 1e-9), 0.0, 1.0)
    return np.where(change < 0, weight * scaled + (1 - weight) * subtracted, original + change)


def absolute_images(coef, geo, covered, orig_nac, orig_dmc, orig_scale, checker, ours):
    """Texture images for an absolute relight: our light on our texels (alternate cubes keep the original with
    `checker`, marked in `ours`), dilated into neighbours; texels beyond keep the original. Returns (images, slot
    scale, mask of the texels kept original)."""
    h, w = covered.shape
    x0, y0 = geo['rect'][:2]
    iy, ix = geo['py'] - y0, geo['px'] - x0
    world = geo['world']
    out = codec.encode(coef)
    nac_s, lin = out['nac'], out['dmcLinear']
    orig_lin = orig_dmc ** codec.GAMMA * np.asarray(orig_scale)                  # (h, w, 3), the whole rectangle
    if checker:
        # alternate cubes of `checker` world units keep the original bake, re-encoded under one scale for both (a
        # chessboard on floors, as cubes cut walls and furniture too)
        ours = (np.floor(world[:, 0] / checker) + np.floor(world[:, 1] / checker)
                + np.floor(world[:, 2] / checker)) % 2 == 0
        lin = np.where(ours[:, None], lin, orig_lin[iy, ix])
        nac_s = np.where(ours[:, None], nac_s, orig_nac[iy, ix])
    # texels of the rectangle that our light and its dilation do not reach (buried deep, or unused) keep the original
    # bake, re-encoded under the component's new slot scale like the rest
    rest = ~lightmap_texels.dilate(np.zeros((h, w, 1)), covered)[1]
    scale = np.maximum(lin.max(0, initial=0.0), orig_lin[rest].max(0, initial=0.0))
    scale = [float(v) for v in np.where(scale > 0, scale, 1.0)]                  # an unlit channel, as codec.encode
    dmc_s = np.clip(lin / np.asarray(scale), 0, 1) ** (1 / codec.GAMMA)
    images = {}
    for key, values, original in (('nac', nac_s, orig_nac),
                                  ('dmc', dmc_s, np.clip(orig_lin / np.asarray(scale), 0, 1) ** (1 / codec.GAMMA))):
        img = np.zeros((h, w, 3))
        img[iy, ix] = values
        img, mask = lightmap_texels.dilate(img, covered)
        img[rest] = original[rest]
        images[key], images[key + '_mask'] = img, np.ones_like(mask)
    return images, scale, rest, ours


def preview(before, after, covered, path):
    """Original | relit, one scale (the original's 99th percentile), gamma 2.2."""
    top = np.percentile(before[covered].max(1), 99) or 1.0
    tiles = [np.clip(img / top, 0, 1) ** (1 / 2.2) for img in (before, after)]
    gap = np.ones((before.shape[0], 8, 3))
    Image.fromarray((np.concatenate([tiles[0], gap, tiles[1]], 1) * 255).astype(np.uint8)).save(path)


def shadow_map_jobs(p, after, args, meshes, edit_boxes, copies=None, fresh=()):
    """The dominant light's shadow maps to trace after the edit (shadowmaps.py): one job for each component with
    one that the edit's shadow can reach. A native copy's component (a key of `copies`, path -> its source's path) is
    relit from its source's place to its own; a component of `fresh` (a copy of a piece of another map) gets its
    whole field. Each job is dict(path, ci, sm, light, source, fresh), or dict(path, sm, skipped) for one left by
    rule. They are worked out by shadow_map_job (in the workers, with the pieces: a cleared map has hundreds, and
    they took most of its build when they ran one after another) and put together by shadow_map_results."""
    import shadowmaps
    copies = copies or {}
    lights = shadowmaps.dominant_lights(p)
    jobs = []
    for path, ci, sm, light in shadowmaps.dominant_receivers(p, {g: l for g, l in lights.items() if l['enabled']}):
        if names_match(path, after.edit['removeCasters']):
            continue            # the edit hides it
        source = None
        if path in copies:
            si = p.by_name[copies[path]]
            same = [x for x in shadowmaps.shadow_maps(p, si) if x['guid'] == sm['guid']]
            if not same:
                jobs.append(dict(path=path, sm=sm, skipped='its source has no shadow map of this light'))
                continue
            source = (si, same[0])
        quick = dict(kind='directional', toLight=light['toLight'], lightSourceAngle=0.0)
        if path not in fresh and source is None and not args.no_quick and not any(
                shadow_meets(quick, e, component_box(p, ci, meshes)) for e in edit_boxes):
            continue
        jobs.append(dict(path=path, ci=ci, sm=sm, light=light, source=source, fresh=path in fresh))
    return jobs


def shadow_map_job(p, scene, after, job, tops):
    """One shadow map after the edit: shadowmaps' result (None when the edit changes nothing in it). `tops` keeps
    the decoded textures (many components share one atlas)."""
    import shadowmaps
    if job['fresh']:
        return shadowmaps.fresh_shadow_map(p, job['ci'], job['sm'], job['light'], after.occluder, after.level_scale,
                                           tops=tops)
    return shadowmaps.relight_shadow_map(p, job['ci'], job['sm'], job['light'], scene.occluder, after.occluder,
                                         scene.level_scale, tops=tops, source=job['source'])


def shadow_map_results(p, jobs, results, args, arrays, ops, npz):
    """The shadow maps' jobs put together in their order: `results` {job index: (result, error text)}. Adds `gray`
    ops (and their arrays) and returns (reports, the reached shadow maps left unchanged)."""
    reports, unchanged = [], []
    for index, job in enumerate(jobs):
        path, sm = job['path'], job['sm']
        if 'skipped' in job:
            reports.append(dict(component=path, shadowMap=sm['path'], skipped=job['skipped']))
            continue
        got, error = results[index]
        if error:
            reports.append(dict(component=path, shadowMap=sm['path'], skipped=error, failed=True))
            print(f'shadow map of {path} skipped: {error}')
            continue
        if got is None:
            unchanged.append(sm['path'])
            continue
        k = len(reports)
        arrays[f's{k}'], arrays[f's{k}_mask'] = got['values'], got['mask']
        ops.append(dict(op='gray', texture=p.name(got['texture']), x0=got['x0'], y0=got['y0'], npz=str(npz),
                        key=f's{k}'))
        reports.append(got['report'])
        tile = np.concatenate([got['original'], np.full((got['original'].shape[0], 4), 0.5), got['values']], 1)
        Image.fromarray((tile * 255).astype(np.uint8)).resize((tile.shape[1] * 2, tile.shape[0] * 2),
                                                             Image.NEAREST).save(
            args.out / f'{args.variant}-{path.split(".")[-2]}-shadow.png')
        r = got['report']
        print(f"shadow map of {path.split('.')[-2]} ({r['texture']}): {r['texelsWritten']} texels "
              f"({r['darker']} darker, {r['lighter']} lighter)")
    return reports, unchanged


def edit_from_spec(spec):
    """The casters an editor patch spec (tools/editor/compiler.py output) removes and adds: the exact hider's targets,
    and each copy's source at its pose. Anything else in the spec (a box hider, other objects) is refused, since its
    light is not modelled."""
    remove, add = [], []
    for obj in spec.get('objects', []):
        kind = obj.get('type')
        if kind == 'hide' and obj.get('exact'):
            remove += list(obj['alsoHide'])
        elif kind == 'copy' and obj.get('poses') is not None:
            if len(obj['from']) != len(obj['poses']):
                raise ValueError('a copy object with different numbers of sources and poses')
            add += [dict(source=s, location=q['location'], rotation=q['rotation'])
                    for s, q in zip(obj['from'], obj['poses'])]
        else:
            raise ValueError(f'the relight models exact hides and posed copies only, not a {kind} object')
    return sorted(set(remove)), add


# Worker processes (--jobs): each opens the map and builds the scenes once, then does the jobs it is given: a whole
# piece, one band of a large piece, or the putting together of a large piece's bands.
_WORKER = {}
MAX_BANDS = 16


def _worker_start(src, scene_args, before_args, after_args, checker, options=None):
    p = lighting.Package(Path(src))
    scene = Scene(p, **scene_args, **before_args) if scene_args is not None else None
    after = Scene(p, **scene_args, **after_args) if after_args is not None else None
    _worker_set(p, scene, after, checker, options)


def _worker_set(p, scene, after, checker, options=None):
    """What a worker works with (the main process itself with one job at a time). `options`: texelReach (the edit's
    reach test for each texel), edited (the edited lights' codec lights, before and after), exact (the scale kept
    and only changed texels written)."""
    options = options or {}
    reach = None
    if options.get('texelReach') and after is not None and scene is not None:
        reach = dict(edit_boxes=after.edit_boxes + scene.edit_boxes, edited=options.get('edited') or [])
    _WORKER.clear()
    _WORKER.update(p=p, scene=scene, after=after, checker=checker, reach=reach, exact=bool(options.get('exact')),
                   work=None)


def peak_memory_mb():
    """This process's peak memory in megabytes (0 where it can't be read)."""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
                        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return round(counters.PeakWorkingSetSize / 2 ** 20)
            return 0
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    except Exception:
        return 0


def total_memory_mb():
    """The computer's memory in megabytes (0 where it can't be read)."""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class Status(ctypes.Structure):
                _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong) for name in (
                        'ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile', 'ullTotalVirtual',
                        'ullAvailVirtual', 'ullAvailExtendedVirtual')]
            status = Status()
            status.dwLength = ctypes.sizeof(Status)
            if ctypes.WinDLL('kernel32').GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / 2 ** 20)
            return 0
        return round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2 ** 20)
    except Exception:
        return 0


def _prepared(path, source, fresh):
    """The piece's prepared work, kept while this worker does its bands one after another."""
    w = _WORKER
    if not w['work'] or w['work'][0] != (path, source, fresh):
        w['work'] = ((path, source, fresh), prepare_component(w['p'], path, w['scene'], checker=w['checker'],
                                                               after=w['after'], source=source, fresh=fresh,
                                                               reach=w['reach']))
    return w['work'][1]


def _worker_job(job):
    """One job: ('whole', path, source, fresh), ('band', path, source, fresh, k, count), ('assemble', path,
    source, fresh, parts), or ('shadow', ('shadow', index), None, False, a shadow_map_jobs job). Returns dict(kind,
    path, result or part, error, failed: whether the error is a failure rather than a valid exclusion, seconds,
    peakMemory)."""
    kind, path, source, fresh = job[:4]
    w = _WORKER
    out = dict(kind=kind, path=path, error=None, failed=False)
    started = time.perf_counter()
    try:
        if kind == 'whole':
            extra = {}
            if fresh:
                extra['fresh'] = True
            if w['reach'] is not None:
                extra['reach'] = w['reach']
            if w['exact']:
                extra['exact'] = True
            out['result'] = relight_component(w['p'], path, w['scene'], checker=w['checker'], after=w['after'],
                                              source=source, **extra)
        elif kind == 'shadow':
            out['result'] = shadow_map_job(w['p'], w['scene'], w['after'], job[4], w.setdefault('tops', {}))
        elif kind == 'band':
            out['band'] = job[4]
            out['part'] = compute_component(_prepared(path, source, fresh), w['scene'], w['after'], band=job[4:6])
        else:
            out['result'] = assemble_component(w['p'], _prepared(path, source, fresh), join_parts(job[4]),
                                               w['scene'], w['after'], exact=w['exact'])
            w['work'] = None
    except Exception as error:
        out.update(error=f'{type(error).__name__}: {error}', failed=not isinstance(error, Excluded))
    out.update(seconds=time.perf_counter() - started, peakMemory=peak_memory_mb())
    return out


def piece_jobs(pieces, jobs, band_texels=BAND_TEXELS):
    """The jobs for `pieces` ((path, source, fresh, rectangle texels)), largest first: a piece of more than twice
    `band_texels` (with more than one worker) as bands, each a job; the others whole."""
    out = []
    for path, source, fresh, area in pieces:
        count = min(MAX_BANDS, -(-area // band_texels)) if jobs > 1 and band_texels and area > 2 * band_texels else 1
        if count == 1:
            out.append((area, ('whole', path, source, fresh)))
        else:
            out += [(area / count, ('band', path, source, fresh, k, count)) for k in range(count)]
    return [job for _, job in sorted(out, key=lambda x: -x[0])]


def plan_jobs(pieces, shadow_queue, allowed, band_texels=BAND_TEXELS):
    """(the queue, the worker count): the shadow-map jobs, then the pieces' jobs as `allowed` workers cut them (a large
    piece in bands when more than one is allowed), and no more workers than the queue has jobs. (Counting the workers
    by the pieces first gave one large floor one worker and no bands: review finding 41.)"""
    queue = list(shadow_queue) + piece_jobs(pieces, allowed, band_texels)
    return queue, max(1, min(allowed, len(queue)))


def run_jobs(queue, jobs, start_args, on_piece):
    """Do the jobs (piece_jobs') with `jobs` workers, or here with one. `on_piece(path, result, error, failed,
    seconds, peak memory)` is called as each piece is finished, in whatever order they finish. A piece's bands are put
    together by one more job, taken before the pieces still waiting. A worker that dies (out of memory, a crash in a
    native library) stops the relight with the pieces it left unfinished named, instead of being waited for for
    ever. Returns the peak memory of the worker that used most (megabytes)."""
    import collections
    pending = collections.deque(queue)
    spent, parts, failed_pieces, peak = collections.defaultdict(float), {}, set(), 0

    def take(job, out):
        nonlocal peak
        path = job[1]
        spent[path] += out['seconds']
        peak = max(peak, out['peakMemory'])
        if path in failed_pieces:
            return
        if out['error']:
            failed_pieces.add(path) if job[0] == 'band' else None
            parts.pop(path, None)
            on_piece(path, None, out['error'], out['failed'], spent[path], out['peakMemory'])
        elif job[0] == 'band':
            got = parts.setdefault(path, {})
            got[job[4]] = out['part']
            if len(got) == job[5]:
                pending.appendleft(('assemble', path, job[2], job[3], [got[k] for k in range(job[5])]))
                del parts[path]
        else:
            on_piece(path, out['result'], None, False, spent[path], out['peakMemory'])

    if jobs <= 1:
        while pending:
            job = pending.popleft()
            take(job, _worker_job(job))
        return peak
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
    from concurrent.futures.process import BrokenProcessPool
    running = {}
    with ProcessPoolExecutor(jobs, mp_context=multiprocessing.get_context('spawn'), initializer=_worker_start,
                             initargs=start_args) as pool:
        try:
            while pending or running:
                while pending and len(running) < jobs:
                    job = pending.popleft()
                    running[pool.submit(_worker_job, job)] = job
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in done:
                    out = future.result()       # (a dead worker raises here, its job still among the running)
                    take(running.pop(future), out)
        except BrokenProcessPool:
            left = sorted({job[1] for job in list(running.values()) + list(pending) if isinstance(job[1], str)})
            sys.exit(f'a relight worker stopped (out of memory, or a crash): {len(left)} pieces were not finished'
                     + (', among them ' + ', '.join(short_name(x) for x in left[:8]) if left else '')
                     + '. Building again with fewer workers (--jobs) needs less memory.')
    return peak


# the code a kept piece's images depend on (under tools/): the relight and its models, the decode of the original
# bake, the readers of the map, its meshes and its materials (review finding 42); the release's version goes into the
# key too, for whatever this list leaves out
TOOL_FILES = ('bake/relight.py', 'bake/bounce.py', 'bake/shadows.py', 'bake/lightmap_encode.py',
              'bake/lightmap_texels.py', 'bake/albedo.py', 'bake/lightmap_textures.py', 'bake/lightmap_fields.py',
              'bake/dxt1.py', 'upk/lighting_records.py', 'upk/native_fields.py', 'upk/props.py', 'upk/decomp.py',
              'upk/lzo1x.py', 'upk/upkinfo.py', 'upk/package_edit.py', 'viewer/mesh.py', 'viewer/export_math.py',
              'viewer/export.py', 'viewer/lights.py', 'viewer/texture.py', 'viewer/package.py')
CACHE_BOXES = 64        # with more edit boxes than this, pieces are not kept: each box is tested against each piece


class PieceCache:
    """The pieces of a project's last baked build, kept for its next one (faster-bake plan, 3.7): a piece of the map
    relit as a change depends on the base map, the baker's code and settings, the lights its lightmap lists in each
    state, and the edits that reach it (edit_reaches, for each edit box and each edited light by itself). With all
    of those as they were, its images are taken from here instead of being worked out. Copies and pieces of other
    maps are always relit. After a build the folder holds that build's pieces and no others."""

    def __init__(self, folder, base, settings):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        from version import VERSION
        tools = hashlib.sha256()
        for name in TOOL_FILES:
            tools.update((ROOT / name).read_bytes())
        self.base = json.dumps([base, tools.hexdigest(), VERSION, settings], sort_keys=True)
        self.used = set()

    def key(self, path, fields, before_lights, after_lights, edits):
        def strip(lights):
            return [{k: v for k, v in l.items() if k not in ('guid', 'guids')} for l in lights]
        text = json.dumps([self.base, path, fields['coordinateScale'], fields['coordinateBias'],
                           strip(before_lights), strip(after_lights), edits], sort_keys=True, default=str)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:40]

    def load(self, key):
        """The kept result of the piece (relight_component's, or dict(unchanged=True, report)), or None."""
        file = self.folder / f'{key}.npz'
        try:
            with np.load(file, allow_pickle=False) as data:
                report = json.loads(str(data['report']))
                self.used.add(file.name)
                if 'nac' not in data.files:
                    return dict(unchanged=True, report=report)
                return dict(report=report, scale=[float(v) for v in data['scale']],
                            onlyChanged=bool(data['onlyChanged']),
                            images={k: data[k] for k in ('nac', 'dmc', 'nac_mask', 'dmc_mask')},
                            before=data['before'].astype(np.float64), after=data['after'].astype(np.float64),
                            covered=data['covered'])
        except Exception:       # none kept, or one that can't be read: the piece is relit
            return None

    def save(self, key, r, unchanged):
        file = self.folder / f'{key}.npz'
        temp = self.folder / f'{key}.{os.getpid()}.tmp.npz'
        try:
            arrays = dict(report=np.array(json.dumps(r['report'])))
            if not unchanged:
                arrays.update(scale=np.array(r['scale'], float), onlyChanged=np.array(bool(r.get('onlyChanged'))),
                              before=r['before'].astype(np.float32), after=r['after'].astype(np.float32),
                              covered=r['covered'], **r['images'])
            np.savez_compressed(temp, **arrays)
            os.replace(temp, file)
            self.used.add(file.name)
        except OSError:
            pass

    def prune(self):
        """Leave only what this build used or kept."""
        for file in self.folder.glob('*.npz'):
            if file.name not in self.used:
                try:
                    file.unlink()
                except OSError:
                    pass


def copy_components(p, natives):
    """The mesh components of native copies (`natives`: (copy actor, source actor) names, as XComLevelActor_469):
    {copy component path: the source's component of the same name}."""
    out = {}
    for copy, source in natives:
        ai = p.by_name.get('TheWorld.PersistentLevel.' + copy)
        si = p.by_name.get('TheWorld.PersistentLevel.' + source)
        if ai is None or si is None:
            raise ValueError(f'no actor {copy if ai is None else source}')
        for ci in p.children.get(ai, []):
            if p.cls(ci).endswith('StaticMeshComponent'):
                twin = p.name(si) + '.' + p.name(ci).split('.')[-1]
                if twin not in p.by_name:
                    raise ValueError(f'{p.name(ci)} has no component {twin} to copy')
                out[p.name(ci)] = twin
    return out


def fresh_components(p, foreign):
    """The static mesh components of the copies of pieces of other maps (`foreign`: (copy actor, staged actor)
    names): their paths."""
    out = []
    for copy, staged in foreign:
        ai = p.by_name.get('TheWorld.PersistentLevel.' + copy)
        if ai is None or 'TheWorld.PersistentLevel.' + staged not in p.by_name:
            raise ValueError(f'no actor {copy if ai is None else staged}')
        out += [p.name(ci) for ci in p.children.get(ai, []) if p.cls(ci).endswith('StaticMeshComponent')]
    return out


WORKER_MEMORY_MB = 1024     # what a worker is allowed for when the workers are counted (default_jobs)


def default_jobs():
    """Half the logical cores, at most 16, and no more than the computer's memory has room for: WORKER_MEMORY_MB
    each, with a quarter of the memory left for everything else."""
    jobs = max(1, min(16, (os.cpu_count() or 2) // 2))
    memory = total_memory_mb()
    if memory:
        jobs = max(1, min(jobs, int(memory * 0.75 // WORKER_MEMORY_MB)))
    return jobs


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('variant')
    a.add_argument('--cache', required=True,
                   help='variant texture cache name: one the map\'s name table holds (the Build\'s <Map>_Lighting, '
                        'added by a growing write first), or <Name>_<n> with <Name> in it')
    a.add_argument('--component', action='append', default=[])
    a.add_argument('--component-list', type=Path, help='file of component paths, one per line')
    a.add_argument('--direct-only', action='store_true', help='no shadows, emissive or bounce (EXP-17 run 5)')
    a.add_argument('--no-emissive', action='store_true', help='leave out the generated area lights')
    a.add_argument('--samples', type=int, default=64, help='shadow rays per texel and light')
    a.add_argument('--bounce-rays', type=int, default=64, help='gather rays per gather point (0: no bounce)')
    a.add_argument('--stride', type=int, default=2, help='gather at every stride-th texel in each atlas direction')
    a.add_argument('--source-radius', type=float,
                   help="smooth the bounce sources' direct light over discs this many units wide (0: each hit's own)")
    a.add_argument('--checker', type=float, help='keep the original bake in alternate squares this many units wide')
    a.add_argument('--remove-caster', action='append', default=[],
                   help='edit: this actor or component casts no shadow and reflects nothing (delta mode)')
    a.add_argument('--remove-caster-list', type=Path, metavar='FILE',
                   help='edit: a file of removed casters, one actor or component a line, as --remove-caster each '
                        '(a cleared map removes about a thousand, more than a command line holds)')
    a.add_argument('--remove-light', action='append', default=[],
                   help='edit: this light actor or component is off (delta mode)')
    a.add_argument('--edit-spec', type=Path,
                   help="edit: an editor patch spec (compiler.py): its hidden pieces are removed casters, its copies "
                        "added ones (delta mode)")
    a.add_argument('--native-copy', action='append', default=[], metavar='COPY=SOURCE',
                   help='edit: the actor COPY is a copy of SOURCE that the edit adds as a new actor of the map '
                        '(native_copy.py): the scene before leaves it out, and its own lightmap and shadow maps are '
                        "relit from SOURCE's place to its own (delta mode)")
    a.add_argument('--moved-in-place', action='append', default=[], metavar='ACTOR=X,Y,Z,PITCH,YAW,ROLL',
                   help='edit: the actor ACTOR stands at its new pose in the map, moved there from this old pose '
                        '(native_spawns.py, F-98): the scene before has it at the old pose; it keeps its own bake '
                        '(delta mode)')
    a.add_argument('--foreign-copy', action='append', default=[], metavar='COPY=STAGED',
                   help='edit: the actor COPY is a copy of STAGED, a piece of another map staged in this one '
                        '(transplant.py): both scenes leave STAGED out, and COPY is lit from nothing')
    a.add_argument('--fresh-copy', action='append', default=[], metavar='COPY',
                   help='edit: the actor COPY is a new actor of this map lit from nothing, as a foreign copy is, '
                        'with no staged piece (a generated wall, frac_walls.py): the scene before leaves it out')
    a.add_argument('--light-edits', type=Path, metavar='FILE',
                   help='edit: the light edits native_copy.py made in this map, with their lights before and after '
                        'and the GUIDs it added to receivers\' lightmaps (native_lights.relight_edits; delta mode)')
    a.add_argument('--receivers-near', type=float, metavar='R',
                   help='edit: also relight every texture-lightmapped component within R units of what the edit '
                        "changes (removed casters where they stood, copies at their poses, removed lights' reach)")
    a.add_argument('--no-shadow-maps', action='store_true',
                   help="edit: leave the dominant light's shadow maps as they are")
    a.add_argument('--no-quick', action='store_true',
                   help='edit: relight every component asked for, without the quick reach test first')
    a.add_argument('--jobs', type=int, default=default_jobs(),
                   help='worker processes, each relighting components in turn (default %(default)s: half the cores, '
                        'at most 16, and no more than the memory has room for)')
    a.add_argument('--band-texels', type=int, default=BAND_TEXELS,
                   help='a piece with more than twice this many texels is relit in bands of about this many, each a '
                        'job (default %(default)s; 0: every piece whole)')
    a.add_argument('--floor', type=float, default=CHANGE_FLOOR,
                   help='edit: a piece whose largest change is under this keeps its bake (default %(default)s)')
    a.add_argument('--piece-cache', type=Path, metavar='DIR',
                   help="edit: keep each piece's result in DIR and take from there the pieces whose lights and "
                        'reaching edits are as they were in the last build (needs --base)')
    a.add_argument('--base', metavar='SHA',
                   help="with --piece-cache: what names the map before the edit (the base map's SHA-256)")
    args = a.parse_args()
    add_casters, natives, foreign, moved, ignore, components = edit_arguments(a, args)
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    timings = {}
    p = lighting.Package(args.src)
    scene_args, states, before_args, scene, after, after_args = edit_scenes(a, args, p, add_casters, natives, foreign,
                                                                            moved, ignore)
    edit_boxes, edited, light_boxes, copies, fresh = edit_receivers(a, args, p, scene, after, states, natives,
                                                                    foreign, ignore, components)
    arrays, ops, reports, skipped, unchanged, unreached = {}, [], [], [], [], []
    npz = args.out / f'{args.variant}.relight.npz'
    timings['scenes'] = round(time.perf_counter() - started, 1)
    todo, meshes, areas, reaching, quick, keep_pieces = select_components(
        args, p, scene, after, components, copies, fresh, moved, edit_boxes, edited, skipped, unreached)
    timings['reach'] = round(time.perf_counter() - started - timings['scenes'], 1)
    # what an edit's relight does beyond the quick test for each piece (faster-bake plan, 3.5, 5.1, 5.2): the reach
    # test for each texel, the floor under a change, the scale kept
    finer = quick
    options = dict(texelReach=finer, exact=after is not None, edited=edited)
    floor = args.floor if after is not None else 0.0
    kept, keys, results, seconds = kept_pieces(args, p, scene, after, scene_args, floor, finer, options, todo, reaching,
                                               keep_pieces)
    taken, work, shadow_queue, shadow_seconds, jobs, peak_memory, shadow_reports, shadow_unchanged = run_pieces(
        args, p, scene, after, scene_args, before_args, after_args, options, floor, todo, copies, fresh, areas,
        edit_boxes, meshes, kept, keys, results, seconds, arrays, ops, reports, skipped, unchanged, npz, timings)
    write_record(args, p, states, after, edit_boxes, light_boxes, natives, foreign, components, arrays, ops, reports,
                 skipped, unchanged, unreached, npz, timings, started, floor, finer, seconds, peak_memory, taken, work,
                 shadow_queue, shadow_seconds, shadow_reports, shadow_unchanged, jobs, meshes)


def edit_arguments(a, args):
    """The edit the command line gives (the parser `a`, its `args`): (casters the edit spec adds, native copies
    [(copy, source)], foreign copies [(copy, staged)], pieces moved in place, the staged pieces no scene has, the
    components asked for). `args.remove_caster` takes the listed and the spec's removed casters. A malformed
    argument is the parser's error."""
    if args.remove_caster_list:
        listed = [l.strip() for l in args.remove_caster_list.read_text(encoding='utf-8').splitlines() if l.strip()]
        args.remove_caster = sorted(set(args.remove_caster) | set(listed))
    add_casters = []
    if args.edit_spec:
        spec_remove, add_casters = edit_from_spec(json.loads(args.edit_spec.read_text(encoding='utf-8')))
        args.remove_caster = sorted(set(args.remove_caster) | set(spec_remove))
    natives = []
    for item in args.native_copy:
        copy, _, source = item.partition('=')
        if not copy or not source:
            a.error(f'--native-copy takes COPY=SOURCE, not {item}')
        natives.append((copy, source))
    foreign = []
    for item in args.foreign_copy:
        copy, _, staged = item.partition('=')
        if not copy or not staged:
            a.error(f'--foreign-copy takes COPY=STAGED, not {item}')
        foreign.append((copy, staged))
    moved = []
    for item in args.moved_in_place:
        actor, _, pose = item.partition('=')
        values = pose.split(',')
        if not actor or len(values) != 6:
            a.error(f'--moved-in-place takes ACTOR=X,Y,Z,PITCH,YAW,ROLL, not {item}')
        moved.append(dict(source=actor, location=[float(v) for v in values[:3]],
                          rotation=[int(round(float(v))) for v in values[3:]]))
    # the staged pieces are in the package and in no level: no scene has them
    ignore = sorted({s for _, s in foreign})
    if args.out.resolve() == args.src.resolve().parent:
        a.error('write the variant outside the source map\'s folder')
    components = list(args.component)
    if args.component_list:
        components += [line.split('#')[0].strip() for line in args.component_list.read_text(encoding='utf-8').splitlines()
                       if line.split('#')[0].strip()]
    if (not components and args.receivers_near is None and not natives and not foreign and not moved
            and not args.fresh_copy):
        a.error('give --component, --component-list, --receivers-near, --native-copy, --foreign-copy, --fresh-copy '
                'or --moved-in-place')
    return add_casters, natives, foreign, moved, ignore, components


def edit_scenes(a, args, p, add_casters, natives, foreign, moved, ignore):
    """The scenes before and after the edit (Scene), with what each was made from: (scene_args, the light states,
    before_args, the scene before, the scene after or None, after_args)."""
    scene_args = None if args.direct_only else dict(samples=args.samples, bounce_rays=args.bounce_rays,
                                                    stride=args.stride, emissive=not args.no_emissive,
                                                    source_radius=args.source_radius)
    # the lights before and after the edit, resolved once here and handed to every worker as they are: the light
    # edits native_copy.py made, and the lights --remove-light takes away
    states = None
    if args.light_edits or args.remove_light:
        doc = json.loads(args.light_edits.read_text(encoding='utf-8')) if args.light_edits else None
        states = resolve_light_states(p, doc, args.remove_light)
        print('light edits:', json.dumps([(e['op'], e['name']) for e in states['edits']]))
    # the scene before the edit has no native copies: they are new actors of this map
    before_args = (dict(remove_casters=[c for c, _ in natives + foreign] + list(args.fresh_copy))
                   if natives or foreign or args.fresh_copy else {})
    # an actor moved in place stands at its new pose in the map: the scene before has it at its old one instead
    if moved:
        before_args['remove_casters'] = before_args.get('remove_casters', []) + [m['source'] for m in moved]
        before_args.update(add_casters=moved, note=dict(movedInPlace=[m['source'] for m in moved]))
    if ignore:
        before_args.update(ignore_casters=ignore)
    if states:
        before_args.update(lights=states['before'], registered=states['registered'])
    scene = None if scene_args is None else Scene(p, **scene_args, **before_args)
    if scene is not None:
        print('scene:', json.dumps(scene.counts), 'level scale', scene.level_scale, 'environment',
              np.round(scene.environment, 4).tolist())
    after, after_args = None, None
    if args.remove_caster or states or add_casters or natives or foreign or moved or args.fresh_copy:
        if scene is None:
            a.error('an edit needs the shadowed model (no --direct-only)')
        after_args = dict(remove_casters=args.remove_caster, add_casters=add_casters, ignore_casters=ignore)
        if states:
            after_args.update(lights=states['after'], note=dict(
                removeLights=sorted(args.remove_light),
                lightEdits=sorted(f"{e['op']} {e['name']}" for e in states['edits'])))
        if moved:       # (the record says what moved in place, with its old pose)
            after_args['note'] = dict(after_args.get('note') or {}, movedInPlace=[
                dict(actor=m['source'], oldLocation=m['location'], oldRotation=m['rotation']) for m in moved])
        after = Scene(p, **scene_args, **after_args)
        print('edit:', json.dumps(after.edit), 'casters', after.counts['casters'], 'of', scene.counts['casters'],
              'lights', len(after.lights), 'of', len(scene.lights),
              'copies', [(c['source'], c['triangles']) for c in after.copies])
    return scene_args, states, before_args, scene, after, after_args


def edit_receivers(a, args, p, scene, after, states, natives, foreign, ignore, components):
    """Where the edit reaches, and the components it adds to `components` (in place): (the edit's boxes, the edited
    lights before and after, their boxes, the native copies' components {copy: source}, the components lit from
    nothing)."""
    # where the edit changes the geometry: its removed casters and posed copies, and the native copies where they
    # stand; apart from them, the radius of every edited light before and after (plan 4.4)
    edit_boxes = (after.edit_boxes + scene.edit_boxes) if after is not None else []
    edited = [l for e in (states['edits'] if states else []) for l in (e.get('before'), e.get('after')) if l]
    light_boxes = [light_box(l) for l in edited if emits(l)]
    copies = copy_components(p, natives)
    if natives:
        print('native copies:', json.dumps(copies))
    fresh = fresh_components(p, foreign)
    if foreign:
        print('copies of pieces of other maps:', json.dumps(fresh))
    # new actors of this map lit from nothing (generated walls): their mesh components, no staged piece to leave out
    for copy in args.fresh_copy:
        ai = p.by_name.get('TheWorld.PersistentLevel.' + copy)
        if ai is None:
            a.error(f'--fresh-copy: no actor {copy}')
        fresh += [p.name(ci) for ci in p.children.get(ai, []) if p.cls(ci).endswith('StaticMeshComponent')]
    if args.fresh_copy:
        print('copies lit from nothing:', json.dumps(args.fresh_copy))
    if args.receivers_near is not None:
        if after is None:
            a.error('--receivers-near needs an edit')
        near = [c for c in receivers_near(p, edit_boxes + light_boxes, args.receivers_near)
                if not names_match(c, ignore)]
        components += [c for c in near if c not in components]
        print(f'receivers within {args.receivers_near:g} of the edit: {len(near)}')
    components += [c for c in copies if c not in components]
    components += [c for c in fresh if c not in components]
    return edit_boxes, edited, light_boxes, copies, fresh


def select_components(args, p, scene, after, components, copies, fresh, moved, edit_boxes, edited, skipped, unreached):
    """The components that go to the relight: those the fixture can write and, in an edit, that the quick test says
    it reaches. Returns (todo [(n, path)], the meshes read, each piece's texel area, the edits reaching each piece
    when pieces are kept, whether the quick test ran, whether pieces are kept); `skipped` and `unreached` take the
    rest."""
    probe = lightmap_writer.Fixture(args.src, args.cache)
    # what goes to the relight: components the fixture can write and, in an edit, that the quick test says it reaches
    todo, meshes, areas, reaching = [], {}, {}, {}
    quick = after is not None and not args.no_quick
    # the pieces of the last build are kept only where each edit box can be tested by itself
    keep_pieces = bool(quick and args.piece_cache and args.base and not args.checker
                       and len(edit_boxes) <= CACHE_BOXES)
    if quick and args.piece_cache and not keep_pieces:
        print('pieces are not kept for the next build: ' + ('no --base' if not args.base else
                                                            f'{len(edit_boxes)} edit boxes'))
    edit_keys = (getattr(after, 'edit_keys', []) + getattr(scene, 'edit_keys', [])) if after is not None else []
    for n, path in enumerate(components):
        if names_match(path, args.remove_caster):
            skipped.append(dict(component=path, reason='the edit removes it'))
            continue
        if names_match(path, [m['source'] for m in moved]):
            skipped.append(dict(component=path, reason='moved in place: it keeps its bake'))
            continue
        try:
            for slot in (0, 1):     # the fixture can write only textures it can move to the variant cache
                texture = probe.redirect(probe.component(path)['slots'][slot]['index'])
            top = texture['fields']['mips'][0]
            x0, y0, x1, y1 = lightmap_texels.rect_bounds(probe.component(path), top['width'], top['height'])
            areas[path] = (x1 - x0) * (y1 - y0)
        except Exception as error:
            # a texture outside Lighting.tfc, or no texture lightmap, is left by rule; a read failure is a failure
            failed = isinstance(error, lighting.FormatError) or not isinstance(error, ValueError)
            skipped.append(dict(component=path, reason=f'{type(error).__name__}: {error}',
                                **({'failed': True} if failed else {})))
            print(f'skipped {path}: {type(error).__name__}: {error}')
            continue
        if path not in copies and path not in fresh and quick:
            box = component_box(p, p.by_name[path], meshes)
            if keep_pieces and len(edit_keys) == len(edit_boxes):
                # which edits reach it, each by itself: they are what its kept result depends on
                hit = reaching_boxes(box, edit_boxes, scene.lights)
                lit = [l for l in edited if emits(l) and boxes_meet(box, light_box(l), REACH_NEAR)]
                reached = bool(hit or lit)
                reaching[path] = [sorted([edit_keys[k], k < len(after.edit_boxes)] for k in hit),
                                  [{k: v for k, v in l.items() if k not in ('guid', 'guids')} for l in lit]]
            else:
                reached = (any(emits(l) and boxes_meet(box, light_box(l), REACH_NEAR) for l in edited)
                           or bool(reaching_boxes(box, edit_boxes, scene.lights, first=True)))
            if not reached:
                unreached.append(path)      # the quick test: the edit's light can't reach it; it keeps its bake
                continue
        todo.append((n, path))
    if after is not None and not args.no_quick:
        print(f'the quick reach test keeps {len(todo)} of {len(todo) + len(unreached)} components')
    return todo, meshes, areas, reaching, quick, keep_pieces


def kept_pieces(args, p, scene, after, scene_args, floor, finer, options, todo, reaching, keep_pieces):
    """The pieces of the last build kept for this one (PieceCache): (the cache or None, each piece's key, the results
    taken from it, an empty table of seconds per piece)."""
    kept = None
    keys, results, seconds = {}, {}, {}
    if keep_pieces:
        kept = PieceCache(args.piece_cache, args.base, dict(
            scene=scene_args, floor=floor, finer=finer, exact=options['exact'], radius=args.receivers_near))
        for n, path in todo:
            if path in reaching:
                ci = p.by_name[path]
                guids = lighting.component_record(p, ci)['lods'][0]['lightmap']['lightGuids']
                keys[path] = kept.key(path, lightmap_fields.component_fields(p, ci)['lods'][0]['lightmap'],
                                      scene.listed(scene.original_guids(path, guids)), after.listed(guids),
                                      reaching[path])
                got = kept.load(keys[path])
                if got is not None:
                    # the record says what this build's edit is, not the one the piece was kept from
                    if got['report'].get('delta'):
                        got['report']['delta']['edit'] = after.edit
                    got['report']['model'] = scene.describe()
                    results[path] = (got, None, False)
        print(f'pieces kept from the last build: {len(results)} of {len(todo)}')
    return kept, keys, results, seconds


def run_pieces(args, p, scene, after, scene_args, before_args, after_args, options, floor, todo, copies, fresh, areas,
               edit_boxes, meshes, kept, keys, results, seconds, arrays, ops, reports, skipped, unchanged, npz, timings):
    """The relight's run: the pieces not kept, and the dominant light's shadow maps, on the workers; each result put
    into `arrays` and `ops` in the map's order, its report into `reports`, or the piece into `skipped` or
    `unchanged`. Returns (the pieces kept, the work done, the shadow-map jobs queued, their seconds, the workers,
    their peak memory, the shadow maps' reports and those unchanged)."""
    taken = set(results)
    work = [(path, copies.get(path), path in fresh, areas.get(path, 0)) for _, path in todo if path not in taken]
    # the dominant light's shadow maps go to the workers with the pieces, ahead of them
    # (a light-only edit moves no shadow caster: only the geometry's edit boxes, and native copies, reach them)
    shadow_jobs, shadow_results = [], {}
    if after is not None and not args.no_shadow_maps:
        shadow_jobs = shadow_map_jobs(p, after, args, meshes, edit_boxes, copies, set(fresh))
    shadow_queue = [('shadow', ('shadow', k), None, False, job) for k, job in enumerate(shadow_jobs)
                    if 'skipped' not in job]
    queue, jobs = plan_jobs(work, shadow_queue, args.jobs, args.band_texels)
    # one `progress:` line per component, for the editor's build window (tools/viewer/builds.py reads them), as each
    # is finished
    print(f'progress: relighting pieces {len(taken)}/{len(todo)}')

    def on_piece(path, r, error, failed, spent, memory):
        if isinstance(path, tuple):         # a shadow map
            shadow_results[path[1]] = (r, error)
            shadow_seconds.append(spent)
            return
        results[path] = (r, error, failed)
        seconds[path] = round(spent, 2)
        if r is not None and r.get('unchanged'):
            if kept is not None and path in keys:
                kept.save(keys[path], r, True)
        elif r is not None:
            # the previews are written as the pieces come in; the rest is put in the map's order below
            preview(r['before'], r['after'], r['covered'], args.out / f"{args.variant}-{path.split('.')[-2]}.png")
            if kept is not None and path in keys:
                kept.save(keys[path], r, is_unchanged(r))
            for key in ('before', 'after', 'covered'):
                r.pop(key, None)
        print(f'progress: relighting pieces {len(results)}/{len(todo)}')

    def is_unchanged(r):
        """Whether the edit leaves the piece as it was: no texel changed, or none by as much as the floor."""
        d = r['report'].get('delta')
        if after is None or not d:
            return False
        if not d['texelsChanged']:
            return True
        # (a copy, or a piece of another map, is written whatever the size of its change)
        return not (r['report'].get('copyOf') or r['report'].get('fresh')) and d['maxFlatChange'] < floor

    shadow_seconds = []
    pieces_started = time.perf_counter()
    if jobs <= 1:
        _worker_set(p, scene, after, args.checker, options)
    peak_memory = run_jobs(queue, jobs, (str(args.src), scene_args, before_args, after_args, args.checker, options),
                           on_piece)
    for path in taken:      # a kept piece's preview
        r = results[path][0]
        if not r.get('unchanged'):
            preview(r['before'], r['after'], r['covered'], args.out / f"{args.variant}-{path.split('.')[-2]}.png")
    timings['pieces'] = round(time.perf_counter() - pieces_started, 1)
    for n, path in todo:
        r, error, failed = results[path]
        if error:
            skipped.append(dict(component=path, reason=error, **({'failed': True} if failed else {})))
            print(f'skipped {path}: {error}')
            continue
        if r.get('unchanged') or is_unchanged(r):
            unchanged.append(path)          # the edit does not reach it: it keeps its bake, untouched
            continue
        for key, value in r['images'].items():
            arrays[f'c{n}_{key}'] = value
        only = {'onlyChanged': True} if r.get('onlyChanged') else {}
        if after is not None:
            only['ring'] = True     # the padding around the rectangle follows its border (lightmap_writer.image)
        ops += [dict(op='image', component=path, slot=0, npz=str(npz), key=f'c{n}_nac', **only),
                dict(op='image', component=path, slot=1, npz=str(npz), key=f'c{n}_dmc', **only),
                dict(op='setscale', component=path, slot=1, value=r['scale'])]
        actor = path.split('.')[-2]
        reports.append(r['report'])
        rep = r['report']
        flat = {key: 'n/a' if value is None else f'{value:.3f}' for key, value in rep['flatLight'].items()}
        print(f"{actor}: {rep['texels']['covered']} texels, {rep['lights']['matched']}/{rep['lights']['guids']} lights "
              f"({rep['lights']['kinds']}), scale {np.round(rep['scales']['original'], 3).tolist()} -> "
              f"{np.round(rep['scales']['relit'], 3).tolist()}, flat light median "
              f"{flat['originalMedian']} -> {flat['relitMedian']}, "
              f"correlation {flat['correlation']}, within 10% {flat['within10pct']}"
              + (f", edit changes {rep['delta']['texelsChanged']} texels (max {rep['delta']['maxFlatChange']:.3f})"
                 if rep['delta'] else ''))
    if kept is not None:
        kept.prune()
    shadow_reports, shadow_unchanged = [], []
    shadows_started = time.perf_counter()
    if after is not None and not args.no_shadow_maps:
        print('progress: shadow maps')
        shadow_reports, shadow_unchanged = shadow_map_results(p, shadow_jobs, shadow_results, args, arrays, ops, npz)
    timings['shadowMaps'] = round(time.perf_counter() - shadows_started, 1)
    return taken, work, shadow_queue, shadow_seconds, jobs, peak_memory, shadow_reports, shadow_unchanged


def write_record(args, p, states, after, edit_boxes, light_boxes, natives, foreign, components, arrays, ops, reports,
                 skipped, unchanged, unreached, npz, timings, started, floor, finer, seconds, peak_memory, taken, work,
                 shadow_queue, shadow_seconds, shadow_reports, shadow_unchanged, jobs, meshes):
    """The lighting written (lightmap_writer.run, or the map as it is when nothing changed) and the record:
    <out>/<variant>.relight.json, and the summary printed."""
    writing_started = time.perf_counter()
    failures = [s for s in skipped + shadow_reports if s.get('failed')]
    if not ops:
        # an edit that changes no texel (a disabled or zero-brightness light added, a light reaching no receiver) is
        # a valid result: the edited map with its original lighting and no texture cache (plan 4.4). An absolute
        # relight that relit nothing, or an edit whose receivers failed to relight, is not
        if after is None:
            sys.exit('nothing to write: no component was relit or changed')
        if failures:
            sys.exit(f'nothing written, and {len(failures)} receivers failed to relight: '
                     + '; '.join(f"{s['component']}: {s.get('reason') or s.get('skipped')}" for s in failures[:5]))
        print('progress: writing the map (lighting unchanged)')
        manifest = unchanged_fixture(args.src, args.out, args.variant)
    else:
        print('progress: writing the lighting')
        np.savez_compressed(npz, **arrays)
        manifest = lightmap_writer.run(args.src, args.out, args.variant, ops, args.cache)
    tool = dict(path='tools/bake/relight.py', sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    timings['writing'] = round(time.perf_counter() - writing_started, 1)
    timings['total'] = round(time.perf_counter() - started, 1)
    import decomp
    # where the time went (faster-bake plan, 6.2; tools/bake/profile_build.py prints it)
    timing = dict(seconds=timings, pieceSecondsSummed=round(sum(seconds.values()), 1), pieceSeconds=seconds,
                  peakWorkerMemoryMB=peak_memory, piecesKept=len(taken), piecesRelit=len(work),
                  shadowMapsTraced=len(shadow_queue), shadowMapSecondsSummed=round(sum(shadow_seconds), 1),
                  packagesDecoded=dict(decomp.STATS, seconds=round(decomp.STATS['seconds'], 2)))
    (args.out / f'{args.variant}.relight.json').write_text(
        json.dumps(dict(source=str(args.src), variant=args.variant, components=reports, skipped=skipped,
                        unchanged=unchanged, unreached=unreached, jobs=jobs, lightingUnchanged=not ops,
                        timing=timing, floor=floor, texelReach=finer,
                        otherPiecesChanged=manifest.get('otherPiecesChanged'),
                        failed=len(failures), cache=manifest['cache'],
                        edit=after.edit if after is not None else None,
                        copies=after.copies if after is not None else None,
                        editSpec=str(args.edit_spec) if args.edit_spec else None,
                        editBoxes=edit_boxes if after is not None else None,
                        lightBoxes=light_boxes if after is not None else None,
                        lightEdits=light_edit_report(p, states, reports, meshes) if states else None,
                        nativeCopies=[dict(copy=c, source=s) for c, s in natives],
                        foreignCopies=[dict(copy=c, staged=s) for c, s in foreign],
                        receiversNear=args.receivers_near, componentsAsked=len(components),
                        shadowMaps=shadow_reports, shadowMapsUnchanged=shadow_unchanged,
                        fixture=manifest['outputs'], tool=tool), indent=1) + '\n', encoding='utf-8', newline='\n')
    if after is not None and not args.no_shadow_maps:
        print(f'{len(shadow_reports)} shadow maps relit, {len(shadow_unchanged)} reached but unchanged')
    print(f'{len(reports)} components relit, {len(skipped)} skipped' +
          (f', {len(unchanged) + len(unreached)} not reached by the edit ({len(unreached)} by the quick test)'
           if after is not None else '') + ('; lighting unchanged' if not ops else ''))
    for e in manifest['edits']:
        print('-', e['what'], e.get('maxChangeOutsideRect', ''))
    other = manifest.get('otherPiecesChanged') or {}
    if other.get('texels'):
        # a warning, not a refusal: the writes reached into the lightmaps of pieces they were not for
        print(f"warning: writing the lighting changed {other['texels']} texels (by up to {other['largest']}) in the "
              f"lightmaps of {len(other['pieces'])} pieces that were not relit: {', '.join(other['pieces'][:6])}")


def unchanged_fixture(src, out, variant):
    """An edit that changes no lighting (plan 4.4): the edited map copied to <out>/<variant>.upk as it is, reading the
    original's lightmaps, and its fixture manifest as lightmap_writer.py writes one, with no texture cache (cache
    null), no edits and `lightingUnchanged`."""
    import shutil
    out = Path(out)
    dst = out / f'{variant}.upk'
    shutil.copyfile(src, dst)
    manifest = dict(source=str(Path(src).resolve()), sourceSha256=lighting.digest(src), variant=variant, cache=None,
                    outputs={str(dst): lighting.digest(dst)}, writer=None, edits=[], lightingUnchanged=True,
                    tool=dict(path='tools/bake/relight.py', sha256=lighting.digest(__file__)))
    (out / f'{variant}.fixture.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    return manifest


def light_edit_report(p, states, reports, meshes):
    """The record's `lightEdits` (plan 4.4): each light edit, its lights before and after, the receivers relit within
    REACH_NEAR of its radius (before or after), and the largest change among them."""
    boxes = {r['component']: component_box(p, p.by_name[r['component']], meshes) for r in reports}
    out = []
    for e in states['edits']:
        lights = [l for l in (e.get('before'), e.get('after')) if l and emits(l)]
        hit = [r for r in reports if any(boxes_meet(boxes[r['component']], light_box(l), REACH_NEAR) for l in lights)]
        out.append(dict(op=e['op'], name=e['name'], label=e.get('label'), component=e['component'],
                        before=e.get('before'), after=e.get('after'), receivers=[r['component'] for r in hit],
                        largestChange=max((r['delta']['maxFlatChange'] for r in hit if r.get('delta')), default=0.0)))
    return out


if __name__ == '__main__':
    main()
