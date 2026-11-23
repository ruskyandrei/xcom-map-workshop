"""A copy of a placed piece as a real piece of the map (baker plan step L4): new exports, by the growing writer.

The editor's copies are spawned at load by the patch and lit live, so they never look quite like the baked pieces
around them (F-52, F-56). This makes the copy in the map itself, as the level designer's copy would be:
- the piece's actor and every export under it (components, shadow maps, a destructible's damage actions and cues)
  are cloned as new exports (package_grow.py appends them), the children under the new actor;
- references among them are remapped to the clones: tagged object and component properties (also inside structs
  and arrays), and the mesh component's LOD records (shadow maps, lightmap textures);
- a piece lit per vertex (CLrgScout_Stonewall's vine, Temple Ship's door volumes) keeps its lightmap in the mesh
  component's own data: the clone owns its copy, with the samples' absolute offsets moved to where the clone lies
  (vertex_lightmaps, move_bulk_offsets). The relight writes textures only, so such a copy keeps its original's light;
- the new actor gets an unused name number and the copy's Location and Rotation (added to its properties when the
  original, at the default pose, saves none), and every clone that has a net
  index gets a fresh one (the package's net object count grows; a clone keeping its original's is a duplicate the game
  logs at every load, EXP-20 run 4b); its mesh components get VisibilityId -1, so the map's precomputed visibility, made
  for the original's place, doesn't cull them;
- the Level's actor list (its first native field: owner, count, actors) gets the new actor, the Level's export
  relocated to the end with the longer list (it holds no absolute offsets);
- the archetypes stay shared: they are exports of the map (outside the level), as the originals use them.

The copy also gets its tiles (cover, movement and line of sight), unless `--no-tiles`:
- the tiles it crosses above the ground get the seed bit 0x1 where the map's baked world data has nothing
  (`seed_tiles_under`, as tools/upk/seed_map.py plans a copy's tiles), so the game's tile rebuild re-checks them;
- an XComRebuildWorldDataVolume over them (`add_rebuild_volume`): the battle rebuilds the tiles inside every such
  volume once the level has loaded, and again after a saved game loads (XGBattle.DoWorldDataRebuild). It is a clone of
  one of the map's trigger volumes (its actor and brush component; the brush model stays shared), retyped, scaled
  and placed over the copy; the class, its default object and its brush component template become new imports.

With `--bake` the copy gets lighting of its own (`own_lighting`):
- its lightmap textures and its shadow maps' textures are cloned as new exports too (the cloned textures start as
  the original's bake), and the copy points at them;
- its lightmap lists any baked light that reaches only its new place (`extra_lights`), so that light is baked in;
- then relight.py runs on the grown map with `--native-copy`: the copy's own lightmap and shadow maps go from the
  original's light where it stands to the copy's where it stands, and the receivers around it (`--receivers-near`)
  get the copy's shadows. That writes the variant and its fixture manifest, which deploy_fixture.py deploys.
  `--edit-spec` adds an editor patch spec's hides (and posed copies) to that relight: the editor's Build makes its
  copies here and leaves its hidden pieces to the patch (tools/editor/build.py).
  The grown map, in <out dir>/grown, reads the original's texture caches through tfc-folder.txt beside it, and its
  name table holds the variant cache's name (--cache: the Build's <Map>_Lighting), which the relight writes into the
  textures it moves to that cache.
Without it, the copy reads the original's lightmap and shadow maps (EXP-20 run 2).

  python -B tools/bake/native_copy.py <map.upk> <out dir> <variant> --copy ACTOR X Y Z [YAW] [--copy ...]
      [--copies copies.json] [--no-tiles] [--bake --cache URB_BarFix_Lighting [--receivers-near 600] [--jobs N]
      [--edit-spec spec.json]]
  (or one copy as --actor NAME --at X Y Z [--yaw YAW]). copies.json is a list of {"actor", "location": [x, y, z],
  "rotation": [pitch, yaw, roll]}, as the editor's Build writes it. Copies with the same "assembly" (the compiler's: a
  car's parts, a door's leaf and frame) are one copy of it, cloned together so that they reference each other's
  clones, with one rebuild volume (clone_assembly, assembly_box). A ladder's copy carries its "ladder" ends ({foot,
  top} tiles, the compiler's): a small rebuild volume over its top tile goes first in the level's list, so the climb
  keeps both its links, and the built map's rebuild order is checked (ladder_order).
Hidden pieces leave every wall's fragment columns, and a door's copy joins the destination wall's (frac_columns.py's
edit_columns), a wall's copy among them; a fracturing piece's copy (a car's glass, a wall, a storey floor) takes its
own columns along, still listing the pieces copied with it by the same move (move_columns); a physics prop (KAsset) is
cloned as any piece is, its skeletal mesh lit live; a van takes its building and floor volumes along
(van_buildings, edit_van_building), and a moved or deleted van's go with it (hide_van_buildings);
every copy whose original is in a building floor's cutaway joins the floor it stands in (edit_floor_caches).

The editor's light edits ("lights" in copies.json: lights deleted, changed, added from a template light or the
built-in spot recipe, generated area lights following their pieces; private/plans/done/editor-lights-plan.md, 4.3 and 9.5) are
made by native_lights.py, in both modes. With --bake the added and changed placed lights join the lightmaps of the
receivers they reach (the copies' too), and the relight gets their before and after states (--light-edits).
"""
import argparse
import dataclasses
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import weakref

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_textures  # noqa: E402
import lightmap_writer  # noqa: E402
import package_grow  # noqa: E402
import piece_flags  # noqa: E402
import props as legacy_props  # noqa: E402
import scene_metadata  # noqa: E402
import seed_map  # noqa: E402
import world_links  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
REF_KINDS = ('ObjectProperty', 'ComponentProperty', 'ClassProperty', 'InterfaceProperty')
# structs serialized as raw bytes, not tagged properties (UE3 immutable/native structs)
RAW_STRUCTS = {'Vector', 'Vector2D', 'Vector4', 'Rotator', 'Guid', 'Color', 'LinearColor', 'Plane', 'Quat', 'Box',
               'Matrix', 'IntPoint', 'TwoVectors', 'Sphere', 'BoxSphereBounds', 'InterpCurvePointFloat'}
MESH_COMPONENTS = ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComMapEdMeshComponent')
# arrays of 4-byte values that hold no object references, though the Walker can't tell them from object arrays: a
# brush's convex hull data, a building's visibility group numbers, a deco component's per-instance bits (the cars,
# doors and ladders inventory found each read as references, private/plans/done/cars-doors-ladders-plan.md, step G2)
NOT_REFERENCES = ('FaceTriData', 'VisGroupIdxToHideWhenOccluding', 'PerInstanceBitfield',
                  # a fractured mesh component's painted fragments: bytes of 0 and 1, four to a value
                  'EditorPaintedVisibleFragments')
# a baked light that reaches a copy's new place joins its lightmap when its unshadowed light there peaks above this
# (flat light, the units of the lightmaps' decoded values; a lit texel is about 0.1 to 1)
EXTRA_LIGHT_MIN = 0.005
# the map's volume whose actor and brush component the rebuild volume is cloned from (a small box brush, no rotation)
REBUILD_TEMPLATE = 'TriggerVolume_0'
# where a map has no TriggerVolume_0 (URB_PoliceStation has no trigger volume at all; F-59), a plain volume of these
# classes in its persistent level, in this order: a rebuild volume of its own first (no retyping), then the classes
# with the fewest properties of their own. It must have a brush model to scale (URB_Demolition_EWI's camera blocking
# volumes have none; F-67). Act1_IntroLevel, the tutorial's map, has none of the first five with a brush: its
# lightmass importance volume, with no properties of its own, is the last resort (F-77)
REBUILD_FALLBACKS = ('XComRebuildWorldDataVolume', 'TriggerVolume', 'XComNoSpawnVolume', 'GameCameraBlockingVolume',
                     'XComCursorVolume', 'LightmassImportanceVolume')
SEED = 0x1


class Walker:
    """Tagged properties of an export's data: where each value lies, and which values are object references.

    With `g`, the growing package (package_grow.Grower) being written over the map `p`, names are read from the
    grower's table: the map's, then the ones added. A property whose name is new to the map is added there with an
    index past the end of the map's own table, so a walker of grown bytes needs it (review finding 37)."""

    def __init__(self, p, g=None):
        self.p = p
        self.names = p.names if g is None else g.names

    def name_at(self, b, at):
        i, n = struct.unpack_from('<ii', b, at)
        if not 0 <= i < len(self.names) or n < 0:
            return None
        return self.names[i] + (f'_{n - 1}' if n else '')

    def looks_tagged(self, b, at, end):
        if at + 8 > end:
            return False
        name = self.name_at(b, at)
        if name is None:
            return False
        if name == 'None':
            return True
        if at + 24 > end:
            return False
        kind = self.name_at(b, at + 8)
        return kind in legacy_props.PROP_TYPES

    def walk(self, b, at, end, path=''):
        """Yields (path, kind, subtype, value offset, size) for each tagged property from `at`; returns the offset
        after the closing None. The walk is props.tags' (bounded by `end`, with this walker's names; review finding
        52)."""
        it = legacy_props.tags(b, at, end, self.names)
        while True:
            try:
                name, kind, sub, index, v, size = next(it)
            except StopIteration as stop:
                return stop.value
            yield (f'{path}{name}[{index}]', kind, sub, v, size)

    def refs(self, b, at, end, path=''):
        """(path, offset) of every object reference in the tagged properties from `at`, nested structs and arrays
        included."""
        out = []
        for prop, kind, sub, v, size in list(self.walk(b, at, end, path)):
            if kind in REF_KINDS:
                out.append((prop, v))
            elif kind == 'DelegateProperty':
                out.append((prop, v))
            elif kind == 'StructProperty' and sub not in RAW_STRUCTS and self.looks_tagged(b, v, v + size):
                out += self.refs(b, v, v + size, prop + '.')
            elif kind == 'ArrayProperty' and size >= 4:
                count = struct.unpack_from('<i', b, v)[0]
                body, stop = v + 4, v + size
                if count and self.looks_tagged(b, body, stop):
                    pos = body
                    for k in range(count):
                        elem = []
                        gen = self.walk(b, pos, stop, f'{prop}({k}).')
                        try:
                            while True:
                                elem.append(next(gen))
                        except StopIteration as done:
                            after = done.value
                        out += self.refs(b, pos, after, f'{prop}({k}).')
                        pos = after
                elif count and size - 4 == 4 * count and prop.rsplit('.', 1)[-1].split('[')[0] not in NOT_REFERENCES:
                    for k in range(count):
                        out.append((f'{prop}({k})', body + 4 * k))
        return out

    def value(self, b, at, end, wanted):
        """Offset of the tagged property `wanted` (name[index]) value, or None."""
        for prop, kind, sub, v, size in self.walk(b, at, end):
            if prop == wanted:
                return v
        return None


def subtree(p, index):
    out = [index]
    for c in p.children.get(index, []):
        out += subtree(p, c)
    return out


def net_index_offset(p, index):
    """Where an export's NetIndex lies in its data: the 4 bytes before its tagged properties (after the state frame of
    an object that has one, and after a component's template owner class)."""
    e = p.exports[index - 1]
    return legacy_props.props_start(p.data, e, p.names) - e['off'] - 4


def lighting_textures(p, tree):
    """The textures the lighting of the exports in `tree` reads, once each in order: the mesh components' texture
    lightmaps (every LOD) and the shadow maps' textures. A skeletal mesh (a door leaf) is lit live: it has neither.
    A piece lit per vertex has no lightmap texture: its samples lie in the component's own data and go with the
    component's clone (clone_assembly, vertex_lightmaps)."""
    out = []
    for i in tree:
        cls = p.cls(i)
        if static_mesh(p, i) > 0:
            for lod in lightmap_fields.component_fields(p, i)['lods']:
                lm = lod['lightmap']
                if lm['type'] == 2:
                    out += [s['index'] for s in lm['slots'] if s['index'] > 0]
        elif cls == 'ShadowMap2D':
            t = p.own(i, 'Texture', 0)
            if t > 0:
                out.append(t)
    return list(dict.fromkeys(out))


def lighting_boxes(p, tree, made=()):
    """The texture of its own a copy gets for each lighting texture the exports of `tree` read (lighting_textures):
    the box of the texture its records read (lightmap_textures.crop_box over their rectangles), so the copy carries
    the part of an atlas it uses and not the whole sheet (smaller built maps plan, F-151). A lightmap record's slots
    share one coordinate scale and bias, so the textures one record reads take one box, over every record that reads
    any of them; where they differ in size, or a shadow map saves no coordinates, they are cloned whole (box None).

    The LOD 0 lightmaps of `made` (mesh components that get a mesh made from numbers, frac_walls.made_component)
    don't count: frac_walls.add_walls gives each textures of its own. A texture only they read is not cloned at all.

    Returns (boxes {texture: (x0, y0, w, h) or None}, sizes {texture: (width, height)}, skip {texture})."""
    from lightmap_texels import rect_bounds
    sizes, fmts, rects, groups, whole, others, seen = {}, {}, {}, {}, set(), set(), set()
    records = {}        # texture -> [(coordinate scale, bias)] of the records that read it

    def size(t):
        if t not in sizes:
            top = lightmap_fields.texture_fields(p, t)['mips'][0]
            sizes[t], fmts[t] = (top['width'], top['height']), p.effective(t, 'Format')
        return sizes[t]

    def find(t):
        while groups.get(t, t) != t:
            t = groups[t]
        return t

    for i in tree:
        if static_mesh(p, i) > 0:
            for lod_index, lod in enumerate(lightmap_fields.component_fields(p, i)['lods']):
                lm = lod['lightmap']
                ts = [s['index'] for s in lm.get('slots', []) if s['index'] > 0] if lm['type'] == 2 else []
                seen.update(ts)
                if not ts or (i in made and lod_index == 0):
                    continue
                others.update(ts)
                for t in ts:
                    rects.setdefault(t, []).append(rect_bounds(lm, *size(t)))
                    records.setdefault(t, []).append((lm['coordinateScale'], lm['coordinateBias']))
                    groups[find(t)] = find(ts[0])
        elif p.cls(i) == 'ShadowMap2D':
            t = p.own(i, 'Texture', 0)
            if t <= 0:
                continue
            seen.add(t)
            others.add(t)
            scale, bias = p.own(i, 'CoordinateScale'), p.own(i, 'CoordinateBias')
            if not isinstance(scale, (bytes, bytearray)) or not isinstance(bias, (bytes, bytearray)):
                whole.add(t)
                continue
            rec = dict(coordinateScale=struct.unpack('<2f', scale), coordinateBias=struct.unpack('<2f', bias))
            rects.setdefault(t, []).append(rect_bounds(rec, *size(t)))
            records.setdefault(t, []).append((rec['coordinateScale'], rec['coordinateBias']))
    members = {}
    for t in others:
        members.setdefault(find(t), []).append(t)
    boxes = {}
    for ts in members.values():
        box = None
        if len({(sizes.get(t), fmts.get(t)) for t in ts}) == 1 and not whole & set(ts) and ts[0] in sizes:
            box = lightmap_textures.crop_box([r for t in ts for r in rects.get(t, [])], *sizes[ts[0]], fmts[ts[0]])
        try:        # every record that reads them must move into the box exactly, or they are cloned whole
            for t in ts if box else ():
                for scale, bias in records.get(t, []):
                    lightmap_textures.moved_record(scale, bias, sizes[t], box)
        except ValueError:
            box = None
        boxes.update({t: box for t in ts})
    return boxes, sizes, seen - others


def vertex_lightmaps(p, index):
    """The vertex lightmaps (lightmap type 1) of mesh component `index`, one per LOD that has one, as
    lightmap_fields locates them: `ownerOffset` and `owner` (the component itself in the cooked maps), and
    `bulkOffsets`, its two bulk records (directional and simple samples). Each inline record holds the absolute
    offset of its payload, so a clone's must be moved to where the clone lies (move_bulk_offsets), as a cloned
    texture's are (lightmap_textures.clone_texture). CLrgScout_Stonewall's vine and Temple Ship's four door volumes are
    lit this way. One in a mesh-swap record is refused: none of the maps has one, and its fields aren't located."""
    if any(lod['lightmap']['type'] == 1 for lod in lighting.component_record(p, index)['swaps']):
        raise ValueError(f'{p.name(index)} has a vertex lightmap in a mesh-swap record, which the copy can\'t move')
    return [lod['lightmap'] for lod in lightmap_fields.component_fields(p, index)['lods']
            if lod['lightmap']['type'] == 1]


def move_bulk_offsets(p, data, metas, off, place, inserts=()):
    """`data` (a bytearray: an export's bytes, copied from logical offset `off`) with its inline bulk records' payload
    offsets moved to where the export will lie, logical offset `place` (package_grow's next_offset). `metas` are the
    records' absolute offsets in the source; `inserts` ((offset in the source's data, bytes added)) are what was
    put into `data` since, each moving the records after it."""
    for meta in metas:
        rel = meta - off + sum(n for at, n in inserts if at <= meta - off)
        flags, count, nbytes, offset = struct.unpack_from('<4i', data, rel)
        if flags & 1:
            continue                    # stored outside the package: nothing of the export's own to point at
        if offset != meta + 16:
            raise ValueError(f'an inline bulk record at {meta} points to {offset}, not past itself')
        struct.pack_into('<i', data, rel + 12, place + rel + 16)
    return data


def check_vertex_lightmaps(q, clones):
    """The written map `q`: every cloned mesh component (`clones`, {original export: clone}) owns its vertex
    lightmaps, and their inline bulk records point at their own payloads. A clone given new data after it was made
    (relocated, as a fracturing piece's is) would have left them behind."""
    for old, new in clones.items():
        if q.cls(new) not in MESH_COMPONENTS:
            continue
        for lm in vertex_lightmaps(q, new):
            if lm['owner'] != new and lm['owner'] in clones:
                raise ValueError(f'{q.name(new)}: its vertex lightmap still belongs to {q.name(lm["owner"])}')
            for meta in lm['bulkOffsets']:
                flags, count, nbytes, offset = struct.unpack_from('<4i', q.data, meta)
                if not flags & 1 and offset != meta + 16:
                    raise ValueError(f'{q.name(new)}: a vertex lightmap\'s bulk record at {meta} points to {offset}')


def guid_field(p, lights):
    """Which of a light's GUIDs this map's texture lightmaps list, LightmapGuid or LightGuid: the one more of the
    level's lightmap lists name (LightmapGuid where neither is named). A piece brought from another map lists none of
    this map's lights, so the map's own pieces say."""
    if getattr(p, '_guid_field', None) is None:
        by = {}
        for e in lights:
            for k, v in e['guids'].items():
                by.setdefault(bytes(v).hex(), set()).add(k)
        votes = dict(LightmapGuid=0, LightGuid=0)
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) not in MESH_COMPONENTS or not p.name(i).startswith(PL):
                continue
            try:
                lods = lighting.component_record(p, i)['lods']
            except Exception:
                continue
            if not lods or lods[0]['lightmap'].get('type') != 2:
                continue
            for g in lods[0]['lightmap']['lightGuids']:
                for k in by.get(g, ()):
                    if k in votes:
                        votes[k] += 1
        p._guid_field = 'LightGuid' if votes['LightGuid'] > votes['LightmapGuid'] else 'LightmapGuid'
    return p._guid_field


def extra_lights(p, ci, location, rotation, threshold=EXTRA_LIGHT_MIN, lights=None, fresh=False):
    """The baked point, spot and directional lights that component `ci`'s lightmap doesn't list but that light it at
    a new pose: each light within reach of the component there, with its unshadowed light on the component's texels. `lights` are
    the lights after the edit (native_lights registry entries: an edit's changed lights with their new values and
    places, its added lights, not its deleted ones); by default the source's own (native_lights.source_registry).
    Returns dicts of light (component path, or a new light's output name), guid (the 16 bytes its lightmap would
    list), peak (flat light), kept (peak > threshold), sorted by peak.

    `fresh`: the component is a piece of another map (transplant.py): the lights its lightmap lists are that map's,
    none of this one's, so every light of this map that lights it is found, by the GUID this map's lightmaps list
    (guid_field)."""
    import numpy as np
    import lightmap_encode as codec
    import lightmap_texels
    import native_lights
    import relight
    lods = lightmap_fields.component_fields(p, ci)['lods']
    if not lods:
        return []
    lm = lods[0]['lightmap']
    if lm['type'] != 2:
        return []
    if lights is None:
        lights = list(native_lights.source_registry(p).values())
    listed = set() if fresh else set(lighting.component_record(p, ci)['lods'][0]['lightmap']['lightGuids'])
    t = lightmap_fields.texture_fields(p, lm['slots'][1]['index'])
    size = [t['mips'][0]['width'], t['mips'][0]['height']]
    mesh = lightmap_texels.component_mesh(p, ci)
    geo = lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, ci, location, rotation), lm, size)
    world = geo['world']
    box = [v for k in range(3) for v in (float(world[:, k].min()), float(world[:, k].max()))]
    # which of a light's guids its lightmaps list: the field the component's listed lights match on
    field = guid_field(p, lights) if fresh else 'LightmapGuid'
    for e in lights:
        ids = {v.hex() for v in e['guids'].values()}
        if ids & listed and e['guids'].get('LightmapGuid', b'').hex() not in listed:
            field = 'LightGuid'
    out = []
    for e in lights:
        if e['role'] != 'static' or field not in e['guids']:
            continue
        light = native_lights.codec_light(e)
        if not light['enabled']:
            continue
        ids = {v.hex() for v in e['guids'].values()}
        if ids & listed or not relight.light_reaches(light, box):
            continue
        coef = codec.coefficients([light], world, geo['frames'])
        peak = float(codec.encode(coef)['dmcLinear'].sum(1).max(initial=0.0))
        out.append(dict(light=e.get('component') or e['id'], guid=bytes(e['guids'][field]), peak=peak,
                        kept=peak > threshold))
    # the map's baked directional lights (a DirectionalLight, not the dominant one: the blank map's only light, whose
    # light its own pieces' lightmaps hold), which reach everywhere; the registry holds point and spot lights only
    # (EXP-79 run D: a piece of another map, or a ground shape made from one, on the blank map had no light listed
    # and came out black)
    for light in relight.map_lights(p, roles=('static',)):
        if light['kind'] != 'directional' or not light['enabled'] or set(light['guids']) & listed:
            continue
        guid = p.effective(p.by_name[light['component']], field)
        if not isinstance(guid, (bytes, bytearray)) or len(guid) != 16:
            continue
        coef = codec.coefficients([light], world, geo['frames'])
        peak = float(codec.encode(coef)['dmcLinear'].sum(1).max(initial=0.0))
        out.append(dict(light=light['component'], guid=bytes(guid), peak=peak, kept=peak > threshold))
    return sorted(out, key=lambda x: -x['peak'])


def dominant_guid(p):
    """The 16 bytes of the LightGuid of the map's dominant directional light (the first enabled one), or None: what a
    shadow map of this map names."""
    import shadowmaps
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) in shadowmaps.DOMINANT and p.name(i).startswith(PL) and p.effective(i, 'bEnabled', True):
            value = p.own(i, 'LightGuid')
            if isinstance(value, (bytes, bytearray)) and len(value) == 16:
                return bytes(value)
    return None


def clone_actor(g, p, actor, location, rotation, own_lighting=False, extra_guids=None):
    """The piece `actor` (export index) cloned under the same level, at `location` (x, y, z) and `rotation` (pitch,
    yaw, roll, rotator units). With `own_lighting`, its lighting textures are cloned too and the copy reads the clones;
    `extra_guids` ({mesh component export: [16-byte light guids]}) adds lights to that component's texture lightmaps.
    Returns dict(actor: new index, mapping {old: new}, textures {old: new}, remapped [(export, path)])."""
    return clone_assembly(g, p, [(actor, location, rotation)], own_lighting, extra_guids)[0]


def made_shadow_maps(p, components, fresh=(), guid=None):
    """The shadow maps a copy made from numbers does not take from its donor (follow-ups item 2.2): of each mesh
    component of `components` (the ones that get a mesh made from numbers, frac_walls.made_component), its LOD 0
    distance-field shadow maps of the map's dominant light (`guid`, dominant_guid's 16 bytes; every distance field of a
    component of `fresh`, which the copy points at that light): exports of the component, listed by no other LOD. They
    are laid out for the donor's mesh: frac_walls.add_walls gives the made piece one of its own, or lists the light
    irrelevant, in their place. A set of export indices."""
    import shadowmaps
    if guid is None:
        return set()
    out = set()
    for ci in components:
        lods = lightmap_fields.component_fields(p, ci)['lods']
        if not lods:
            continue
        others = {ref for lod in lods[1:] for ref in lod['shadowMaps']}
        for sm in shadowmaps.shadow_maps(p, ci):
            if (not sm['factor'] and (ci in fresh or sm['guid'] == guid.hex()) and sm['export'] not in others
                    and p.exports[sm['export'] - 1]['outer'] == ci):
                out.add(sm['export'])
    return out


def clone_assembly(g, p, members, own_lighting=False, extra_guids=None, fresh=(), shadow_guid=None, made=()):
    """The pieces `members` ([(actor export index, location, rotation)]) cloned together under the level, as one copy
    of an assembly (a car's parts, a door's leaf and frame; private/plans/done/cars-doors-ladders-plan.md, step G2). Each clone
    is clone_actor's, and a reference from any member's exports to any member's (an actor or anything under it) points
    at that member's clone: a car body's HidingPartner at the glass's copy, the glass's fragment columns at the body's
    and the light bar's copies. References to anything else stay as they are. Lighting textures are each member's own
    clones, as clone_actor's are. Returns clone_actor's dict for each member, in order.

    `fresh` are mesh components (export indices) of pieces brought from another map: a clone's texture lightmaps list
    `extra_guids` alone (the lights they listed are the other map's), and its distance-field shadow maps name
    `shadow_guid`, this map's dominant light (left as they are where the map has none).

    `made` are the mesh components that get a mesh made from numbers (frac_walls.made_component): their shadow maps
    of the dominant light (made_shadow_maps) are not cloned, nor their textures. The component's clone still names the
    donor's own map there until frac_walls.add_walls writes its list; each member's dict gives them as `uncloned`.
    Their LOD 0 lightmap's textures are not cloned either where nothing else reads them (lighting_boxes): add_walls
    gives the made piece textures of its own (it must, or the relight would write into the donor's).

    A lighting texture is cloned as a texture the size of what the copy reads of it (lighting_boxes,
    lightmap_textures.cropped_texture, holding the source's bake there), and the copy's lightmap records and shadow
    maps get the coordinate scale and bias that point into it (lightmap_textures.moved_record): the same texels, so
    the relight reads and writes what it did in a clone of the whole atlas. Each member's dict gives the boxes as
    `boxes` ({original texture: (x0, y0, w, h)}, the ones cut)."""
    walker = Walker(p, g)
    fresh = set(fresh)
    made = set(made)
    extra_guids = extra_guids or {}
    uncloned = made_shadow_maps(p, made, fresh, dominant_guid(p)) if made else set()
    at = len(g.entries) + 1
    plans, everyone = [], {}
    for actor, location, rotation in members:
        tree = [i for i in subtree(p, actor) if i not in uncloned]
        mapping = {old: at + k for k, old in enumerate(tree)}
        at += len(tree)
        boxes, sizes, skip = lighting_boxes(p, tree, made) if own_lighting else ({}, {}, set())
        textures = [t for t in lighting_textures(p, tree) if t not in skip] if own_lighting else []
        tex_map = {t: at + j for j, t in enumerate(textures)}
        at += len(textures)
        if set(mapping) & set(everyone):
            raise ValueError(f'{p.name(actor)} is cloned twice in one assembly')
        everyone.update(mapping)
        plans.append((actor, location, rotation, tree, mapping, textures, tex_map, boxes, sizes))
    infos = []
    for actor, location, rotation, tree, mapping, textures, tex_map, boxes, sizes in plans:
        remap = {**everyone, **tex_map}
        remapped = []
        for old in tree:
            e = p.exports[old - 1]
            off, size = e['off'], e['size']
            data = bytearray(p.data[off:off + size])
            start = legacy_props.props_start(p.data, e, p.names) - off
            for prop, ref in walker.refs(bytes(data), start, size):
                value = struct.unpack_from('<i', data, ref)[0]
                if value in remap:
                    struct.pack_into('<i', data, ref, remap[value])
                    remapped.append((p.name(old), prop))
            cls = p.cls(old)
            inserts, bulks = [], []
            if cls in MESH_COMPONENTS:
                # a vertex lightmap goes with the clone: the clone owns it, and its samples lie where the clone does
                for lm in vertex_lightmaps(p, old):
                    if lm['owner'] in everyone:
                        struct.pack_into('<i', data, lm['ownerOffset'] - off, everyone[lm['owner']])
                        remapped.append((p.name(old), 'LightMap.Owner'))
                    bulks += lm['bulkOffsets']
                f = lightmap_fields.component_fields(p, old)
                guids = [lod['lightmap'].get('lightGuids', []) for lod in lighting.component_record(p, old)['lods']]
                for lod_index, lod in enumerate(f['lods']):
                    sm = lod['shadowMapsOffset'] - off
                    n = struct.unpack_from('<i', data, sm)[0]
                    for j in range(n):
                        value = struct.unpack_from('<i', data, sm + 4 + 4 * j)[0]
                        if value in mapping:
                            struct.pack_into('<i', data, sm + 4 + 4 * j, mapping[value])
                            remapped.append((p.name(old), f'LOD{lod_index}.ShadowMaps({j})'))
                    lm = lod['lightmap']
                    if lm['type'] == 2:
                        for j, s in enumerate(lm['slots']):
                            if s['index'] in tex_map:
                                struct.pack_into('<i', data, s['textureOffset'] - off, tex_map[s['index']])
                                remapped.append((p.name(old), f'LOD{lod_index}.LightMap.Textures({j})'))
                        cut = [s['index'] for s in lm['slots'] if boxes.get(s['index']) and s['index'] in tex_map]
                        if cut and not (old in made and lod_index == 0):
                            # the record points into the copy's own texture of the box (lighting_boxes: one box for
                            # all the textures of a record)
                            scale, bias = lightmap_textures.moved_record(lm['coordinateScale'], lm['coordinateBias'],
                                                                         sizes[cut[0]], boxes[cut[0]])
                            struct.pack_into('<2f', data, lm['coordinateScaleOffset'] - off, *scale)
                            struct.pack_into('<2f', data, lm['coordinateBiasOffset'] - off, *bias)
                            remapped.append((p.name(old), f'LOD{lod_index}.LightMap.Coordinates: its own texture'))
                        if old in fresh:
                            # a piece of another map: its list is this map's lights alone
                            if bulks:
                                raise ValueError(f'{p.name(old)}: a piece of another map with a vertex lightmap '
                                                 'beside a texture lightmap can\'t take this map\'s lights')
                            inserts.append((lm['lightGuidsOffset'] - off, lm['lightGuidCount'],
                                            list(extra_guids.get(old, [])), True))
                            continue
                        new = [x for x in extra_guids.get(old, []) if x.hex() not in guids[lod_index]]
                        if new:
                            inserts.append((lm['lightGuidsOffset'] - off, lm['lightGuidCount'], new, False))
                vis = walker.value(bytes(data), start, size, 'VisibilityId[0]')
                if vis is not None:
                    struct.pack_into('<i', data, vis, -1)
            if (cls == 'ShadowMap2D' and shadow_guid and p.exports[old - 1]['outer'] in fresh
                    and not p.own(old, 'bIsShadowFactorTexture', False)):
                data = set_struct(walker, g, data, start, 'LightGuid', 'Guid', '<16s', [shadow_guid])
                remapped.append((p.name(old), 'LightGuid: this map\'s dominant light'))
            texture = p.own(old, 'Texture', 0) if cls == 'ShadowMap2D' else 0
            if texture in tex_map and boxes.get(texture):
                scale, bias = lightmap_textures.moved_record(struct.unpack('<2f', p.own(old, 'CoordinateScale')),
                                                             struct.unpack('<2f', p.own(old, 'CoordinateBias')),
                                                             sizes[texture], boxes[texture])
                data = set_struct(walker, g, data, start, 'CoordinateScale', 'Vector2D', '<2f', scale)
                data = set_struct(walker, g, data, start, 'CoordinateBias', 'Vector2D', '<2f', bias)
                remapped.append((p.name(old), 'Coordinates: its own texture'))
            g.fresh_net_index(old, data, at=start - 4)
            if old == actor:
                # set in place, or added before the closing None when the original stands at the default (0)
                data = set_struct(walker, g, data, start, 'Location', 'Vector', '<3f', [float(v) for v in location])
                data = set_struct(walker, g, data, start, 'Rotation', 'Rotator', '<3i', [int(v) for v in rotation])
            # added lights last, later records first: an insertion moves what follows it (a texture lightmap's record
            # holds no offsets into the export; a vertex lightmap's bulk records are moved below)
            for where, n, new, replace in sorted(inserts, key=lambda x: -x[0]):
                if replace:
                    struct.pack_into('<i', data, where - 4, len(new))
                    data[where:where + 16 * n] = b''.join(new)
                    remapped.append((p.name(old), f'LightMap.LightGuids: {n} of its home map out, {len(new)} of this map in'))
                    continue
                struct.pack_into('<i', data, where - 4, n + len(new))
                data[where + 16 * n:where + 16 * n] = b''.join(new)
                remapped.append((p.name(old), f'LightMap.LightGuids +{len(new)}'))
            place = g.next_offset()
            if bulks:
                move_bulk_offsets(p, data, bulks, off, place, [(w + 16 * n, 16 * len(x)) for w, n, x, _ in inserts])
                remapped.append((p.name(old), f'LightMap bulk offsets x{len(bulks)}'))
            number = g.unused_number(g.entries[old - 1].name_index) if old == actor else None
            new = g.add_export(old, bytes(data), number=number if number is not None else g.entries[old - 1].name_number)
            if new != mapping[old]:
                raise ValueError('the clones did not get the planned indices')
            if g.entries[new - 1].offset != place:
                raise ValueError('a clone did not land where its bulk offsets say')
            outer = p.exports[old - 1]['outer']
            if outer in mapping:
                g.entries[new - 1].put('<i', 8, mapping[outer])
        for t in textures:
            new = (lightmap_textures.cropped_texture(g, p, t, boxes[t]) if boxes.get(t)
                   else lightmap_textures.clone_texture(g, p, t))
            if new != tex_map[t]:
                raise ValueError('the texture clones did not get the planned indices')
        info = dict(actor=mapping[actor], mapping=mapping, textures=tex_map, remapped=remapped,
                    boxes={t: boxes[t] for t in textures if boxes.get(t)})
        left = sorted(i for i in subtree(p, actor) if i in uncloned)
        if left:
            info['uncloned'] = left
        infos.append(info)
    return infos


def set_struct(walker, g, data, start, name, struct_name, fmt, value):
    """`data` (an export's bytes, tagged properties from `start`) with the struct property `name` (a Vector, '<3f',
    or a Rotator, '<3i', or any raw struct packed by `fmt`) set to `value`: in place when the export saves it, else
    added before the closing None (the export then grows; nothing in an actor's data points past its properties). The
    tag's size is the value's own (native_lights.set_property)."""
    import native_lights
    return native_lights.set_property(walker, g, data, start, name, 'StructProperty', struct_name,
                                      struct.pack(fmt, *value))


POSE = ('Location', 'Rotation', 'RelativeLocation')


def set_pose(walker, g, p, index, location=None, rotation=None, relative=None, names=POSE, noted=None):
    """Export `index` with its place set where it stands in the map `g` grows: each of `location` (a Vector),
    `rotation` (a Rotator) and `relative` (a component's or a based actor's RelativeLocation) that is given, written in
    place or added before the closing None where the export saves none (native_lights.set_property). `names` are the
    three properties' names (a Kismet Set Location action saves LocationValue and RotationValue); `noted`, a pair of
    lists (added, written), records the properties written and those added (native_lights.put). The one way the Build
    sets a pose in place (review finding 55)."""
    import native_lights
    e = p.exports[index - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    for name, (struct_name, fmt, kind), value in zip(names, (('Vector', '<3f', float), ('Rotator', '<3i', int),
                                                             ('Vector', '<3f', float)), (location, rotation, relative)):
        if value is None:
            continue
        raw = struct.pack(fmt, *[kind(v) for v in value])
        if noted is not None:
            data = native_lights.put(walker, g, data, start, name, 'StructProperty', struct_name, raw, *noted)
        else:
            data = native_lights.set_property(walker, g, data, start, name, 'StructProperty', struct_name, raw)
    g.relocate(index, bytes(data))


def set_object_array(walker, g, data, start, name, values):
    """`data` (an export's bytes, tagged properties from `start`) with the object array property `name` set to
    `values` (export indices): in place when the export saves it, else added before the closing None (nothing is
    added for an empty list)."""
    payload = struct.pack('<i', len(values)) + b''.join(struct.pack('<i', v) for v in values)
    gen = walker.walk(bytes(data), start, len(data))
    try:
        while True:
            prop, kind, _, at, size = next(gen)
            if prop == f'{name}[0]':
                if kind != 'ArrayProperty':
                    raise ValueError(f'{name} is a {kind}, not an array')
                struct.pack_into('<i', data, at - 8, len(payload))
                data[at:at + size] = payload
                return data
    except StopIteration as done:
        end = done.value
    if values:
        tag = struct.pack('<iiiiii', g.name(name), 0, g.name('ArrayProperty'), 0, len(payload), 0)
        data[end - 8:end - 8] = tag + payload
    return data


def object_array(walker, data, start, name):
    """The export indices in the object array property `name`, or [] when the export saves none."""
    for prop, kind, _, at, size in walker.walk(bytes(data), start, len(data)):
        if prop == f'{name}[0]' and kind == 'ArrayProperty':
            return list(struct.unpack_from(f'<{struct.unpack_from("<i", data, at)[0]}i', data, at + 4))
    return []


BREAKABLE = ('XComDestructibleActor', 'XComCollectible')
PART_MATCH = 32.0        # how far a part's copy may be from where its parent's copy puts it (units)


def copy_children(p, made, m, level):
    """The AffectedChildren a copy keeps from its original: a part of the same assembly (a pool table's top, a van's
    door) points at that part's copy made in this build, the one standing as far from this copy as the originals stand
    apart (within PART_MATCH; a rigid move keeps distances), and is dropped when the part wasn't copied with it: the
    original's parts are the original's. References to anything but the level's actors (a few name archetypes) stay
    as they are. Returns (children, notes)."""
    import numpy as np
    walker = Walker(p)
    old = p.by_name[PL + m['actor']]
    e = p.exports[old - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    here = np.array(p.own(old, 'Location', [0.0, 0.0, 0.0]), float)
    out, notes = [], []
    for child in object_array(walker, p.data[e['off']:e['off'] + e['size']], start, 'AffectedChildren'):
        if child == 0 and m.get('staged'):
            continue        # a piece of another map: what it listed of its home map's pieces was cut (transplant.py)
        if child <= 0 or p.exports[child - 1]['outer'] != level:
            out.append(child)
            continue
        apart = float(np.linalg.norm(np.array(p.own(child, 'Location', [0.0, 0.0, 0.0]), float) - here))
        best = None
        for other in made:
            if other is not m and p.by_name[PL + other['actor']] == child:
                off = abs(float(np.linalg.norm(np.array(other['location']) - np.array(m['location']))) - apart)
                if off <= PART_MATCH and (best is None or off < best[0]):
                    best = (off, other['info']['actor'])
        if best:
            out.append(best[1])
        notes.append(dict(child=p.name(child).split('.')[-1], copy=best[1] if best else None))
    return out, notes


def assembly_children(p, m, mapping, level):
    """The AffectedChildren a copy of an assembly's member keeps: a child that is a member points at that member's
    copy in this copy of the assembly (`mapping`: every member's original exports -> clones), a child that is another
    piece of the level is dropped (the original's parts are the original's), anything else stays. Returns (children,
    notes), as copy_children."""
    walker = Walker(p)
    old = p.by_name[PL + m['actor']]
    e = p.exports[old - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    out, notes = [], []
    for child in object_array(walker, p.data[e['off']:e['off'] + e['size']], start, 'AffectedChildren'):
        if child in mapping:
            out.append(mapping[child])
            notes.append(dict(child=p.name(child).split('.')[-1], copy=mapping[child]))
        elif child == 0 and m.get('staged'):
            continue        # cut with its home map's other pieces
        elif child <= 0 or p.exports[child - 1]['outer'] != level:
            out.append(child)
        else:
            notes.append(dict(child=p.name(child).split('.')[-1], copy=None))
    return out, notes


def link_children(g, p, made, originals, blocks=(), walled=()):
    """Every copy's AffectedChildren, the game's link between pieces that break together: the state one enters
    (damaged, destroyed) is passed on to the pieces it lists (XComDestructibleActor.SyncChildStates, which skips a
    child already in that state, so links may go both ways). A copy keeps its assembly's links to the parts copied
    with it (copy_children; for a copy of one of the compiler's assemblies, its own members' copies exactly:
    assembly_children). The editor's groups that break together (compiler.py's break groups) link each member to
    every other: `made` are the copies (dicts with `info`, `breakGroup` and, for an assembly's, `assembly`), `originals`
    the map's own pieces left in place ({name, group}), which keep their own children too. `blocks` are the cover
    blocks that break with a group ((group, actor export): cover_blocks.py's hidden props): each member of the group
    lists them too, and a block lists nothing, so it follows its group and nothing follows it; with a block, one
    member is enough for a group, and so it is in a group with a made wall (`walled`: those groups' numbers), whose
    columns list its pieces (frac_walls.group_columns). Returns ({group: [members, then blocks]}, {copy: notes})."""
    walker = Walker(p, g)
    level = p.by_name['TheWorld.PersistentLevel']
    groups, kept, notes = {}, {}, {}
    together = {}       # an assembly's copy: every original export of its members -> its clone
    for m in made:
        if m.get('assembly'):
            together.setdefault(m['assembly'], {}).update(m['info']['mapping'])
    for m in made:
        new = m['info']['actor']
        if m.get('assembly'):
            kept[new], notes[new] = assembly_children(p, m, together[m['assembly']], level)
        else:
            kept[new], notes[new] = copy_children(p, made, m, level)
        if m.get('breakGroup'):
            groups.setdefault(int(m['breakGroup']), []).append(new)
    for o in originals:
        i = p.by_name.get(PL + o['name'])
        if i is None or p.cls(i) not in BREAKABLE or p.exports[i - 1]['outer'] != level:
            raise ValueError(f"break group {o['group']}: no destructible piece {o['name']} in the map's level")
        if i in groups.get(int(o['group']), []):
            raise ValueError(f"break group {o['group']} lists {o['name']} twice")
        groups.setdefault(int(o['group']), []).append(i)
    followers = {}
    for number, actor in blocks:
        if int(number) not in groups and int(number) not in walled:
            raise ValueError(f'break group {number} has a cover block and no breakable piece')
        followers.setdefault(int(number), []).append(actor)
    partners = {}
    for number, members in groups.items():
        if len(members) + len(followers.get(number, [])) < (1 if number in walled else 2):
            raise ValueError(f'break group {number} has {len(members)} piece(s)')
        for a in members:
            partners[a] = [b for b in members if b != a] + followers.get(number, [])
    for m in made:
        new = m['info']['actor']
        old = p.by_name[PL + m['actor']]
        e = p.exports[old - 1]
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        data = bytearray(g.export_data(new))
        want = kept[new] + [b for b in partners.get(new, []) if b not in kept[new]]
        if object_array(walker, data, start, 'AffectedChildren') != want:
            g.relocate(new, bytes(set_object_array(walker, g, data, start, 'AffectedChildren', want)))
    for i in sorted({i for members in groups.values() for i in members} - set(kept)):
        e = p.exports[i - 1]
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        data = bytearray(g.export_data(i))
        own = object_array(walker, data, start, 'AffectedChildren')
        g.relocate(i, bytes(set_object_array(walker, g, data, start, 'AffectedChildren',
                                             own + [b for b in partners[i] if b not in own])))
    return {number: members + followers.get(number, []) for number, members in sorted(groups.items())}, notes


def set_vector(walker, g, data, start, name, value):
    return set_struct(walker, g, data, start, name, 'Vector', '<3f', [float(v) for v in value])


def level_grid(p):
    """The map's tile grid, from its one XComLevelVolume: dict(ox, oy, oz, nx, ny, nz, tx, ty, tz) as seed_map.py
    has it (scene_metadata.game_grid; private/plans/done/game-grid-plan.md):
    - ox, oy, oz: the level volume's box's low corner, where the maps' own pieces stand on whole tiles, which the Build
      places, seeds and sizes by (seed_map's tile rules, the rebuild volumes, a grown grid's corner);
    - tx, ty, tz: the corner the game counts its tiles from (its world data's WorldBounds, a unit under ox, oy, oz),
      for what the game itself works out from it (rebuild_order);
    - nx, ny, nz: the tile counts of the map's tile data (a box can miss them: CBattleship_01's is half a level over
      its 15 levels). A package with no tile data takes the box's, rounded."""
    level = p.by_name['TheWorld.PersistentLevel']
    vols = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComLevelVolume'
            and p.exports[i - 1]['outer'] == level and p.own(i, 'Brush', 0) > 0]
    if len(vols) != 1:
        raise ValueError(f'expected one XComLevelVolume with a brush, found {len(vols)}')
    lo, hi = brush_box(p, vols[0])
    grid = scene_metadata.game_grid(p, dict(min=lo, max=hi))
    if grid is None:
        n = [round((hi[0] - lo[0]) / seed_map.TILE), round((hi[1] - lo[1]) / seed_map.TILE),
             round((hi[2] - lo[2]) / seed_map.FLOOR)]
        tiles = [v - 1 for v in lo]
    else:
        n, tiles = grid['dimensions'], grid['tiles']
    return dict(ox=lo[0], oy=lo[1], oz=lo[2], nx=n[0], ny=n[1], nz=n[2], tx=tiles[0], ty=tiles[1], tz=tiles[2])


def brush_bounds(p, volume):
    """A volume's brush model's local bounds: (origin, extent)."""
    model = p.own(volume, 'Brush', 0)
    if model <= 0:
        raise ValueError(f'{p.name(volume)} has no brush')
    _, end = p.properties(model)
    v = struct.unpack_from('<6f', p.data, end)
    return list(v[:3]), list(v[3:])


def brush_sphere(p, volume):
    """A volume's brush model's local bounds' sphere radius (the float after its box's origin and extent)."""
    model = p.own(volume, 'Brush', 0)
    if model <= 0:
        raise ValueError(f'{p.name(volume)} has no brush')
    _, end = p.properties(model)
    return struct.unpack_from('<7f', p.data, end)[6]


def brush_box(p, volume, location=None, scale=None):
    """A volume's world box (lo, hi): its brush's bounds moved by its Location and scaled by its DrawScale3D (an
    unturned volume only)."""
    if any(p.own(volume, 'Rotation', [0, 0, 0])):
        raise ValueError(f'{p.name(volume)} is turned')
    origin, extent = brush_bounds(p, volume)
    loc = location if location is not None else p.own(volume, 'Location', [0, 0, 0])
    if scale is None:
        scale = [v * p.own(volume, 'DrawScale', 1.0) for v in p.own(volume, 'DrawScale3D', [1.0, 1.0, 1.0])]
    lo = [loc[k] + scale[k] * (origin[k] - extent[k]) for k in range(3)]
    hi = [loc[k] + scale[k] * (origin[k] + extent[k]) for k in range(3)]
    return lo, hi


def static_mesh(p, ci):
    """The static mesh a mesh component draws, or 0: a door leaf saves an unused StaticMeshComponent beside the
    skeletal one it draws with (private/plans/done/cars-doors-ladders-plan.md, 2.2 and step G4)."""
    return p.effective(ci, 'StaticMesh', 0) if p.cls(ci) in MESH_COMPONENTS else 0


def skeletal_mesh(p, ci):
    """The skeletal mesh a SkeletalMeshComponent draws (a door leaf's), or 0."""
    return p.effective(ci, 'SkeletalMesh', 0) if p.cls(ci) == 'SkeletalMeshComponent' else 0


def skeletal_points(p, ci, location, rotation):
    """World positions of a skeletal component's mesh in its reference pose (a door leaf, closed), with the actor at
    `location` and `rotation`: the pose the export draws and the compiler's box (skeletal.read_skeletal)."""
    import numpy as np
    import lightmap_texels
    from skeletal import read_skeletal
    pos = np.array(read_skeletal(p, skeletal_mesh(p, ci))['positions'], float).reshape(-1, 3)[:, [0, 2, 1]]
    m = lightmap_texels.world_matrix(p, ci, location, rotation)
    return pos @ m[:3, :3].T + m[:3, 3]


def piece_box(p, actor, location, rotation):
    """The world box [x0, x1, y0, y1, z0, z1] of a piece's meshes with the actor at `location` and `rotation`: its
    static meshes, and a door leaf's skeletal mesh in its reference pose."""
    import numpy as np
    import lightmap_texels
    pts = []
    for ci in subtree(p, actor):
        if static_mesh(p, ci) > 0:
            mesh = lightmap_texels.component_mesh(p, ci)
            m = lightmap_texels.world_matrix(p, ci, location, rotation)
            pts.append(mesh['positions'] @ m[:3, :3].T + m[:3, 3])
        elif skeletal_mesh(p, ci) > 0:
            pts.append(skeletal_points(p, ci, location, rotation))
    if not pts:
        raise ValueError(f'{p.name(actor)} has no mesh')
    pts = np.concatenate(pts)
    return [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]


_STATIC = weakref.WeakKeyDictionary()     # package -> its static flags (static_flags)


def static_flags(p):
    """(the map's one XComWorldDataContainer's export entry, its bytes, (NX, NY, NZ), {tile: the offset of its static
    flags in those bytes}), read once for each open package with world_links.static_tiles' checks (review finding
    52). They are the map's own bytes: a Build's seeds go into its grower's edits, never into the package."""
    found = _STATIC.get(p)
    if found is None:
        conts = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer']
        if len(conts) != 1:
            raise ValueError(f'expected one XComWorldDataContainer, found {len(conts)}')
        e = p.exports[conts[0] - 1]
        blob = p.data[e['off']:e['off'] + e['size']]
        found = _STATIC[p] = (e, blob) + world_links.static_tiles(blob)[:2]
    return found


def seed_tiles_under(g, p, box, grid, seed=SEED, ring=1, above=1):
    """Seed bit `seed` on the tiles a piece's world `box` crosses, from level 1 up (seed_map.py's copy plan: the
    box plus a quarter tile in x and y), and on `ring` tiles around them and `above` levels over them, where the
    baked static flags have none of the low 12 bits: in-place edits of the map's XComWorldDataContainer. The ring and
    the level above are there because the bake marks them too: a lamp post's neighbours carry direction bits toward
    it at every level, and the tile over its top a bit of its own (EXP-20 run 4). Returns dict(tiles: the tile
    ranges, seeded: [(x, y, z, old, new)], already)."""
    t = seed_map.tiles_touched(box, grid, seed_map.MARGIN)
    t = seed_map.clamp((t[0] - ring, t[1] + ring, t[2] - ring, t[3] + ring, t[4], t[5] + above), grid)
    if t is None:
        return dict(tiles=None, seeded=[], already=0)
    e, blob, dims, where = static_flags(p)
    if tuple(dims) != (grid['nx'], grid['ny'], grid['nz']):
        raise ValueError(f'the world data is {dims} tiles, the level volume {grid}')
    seeded, already = [], 0
    for tile in seed_map.tile_set([('', '', '') + tuple(t)]):
        at = where[tile]
        flags, present = struct.unpack_from('<IB', blob, at)
        if flags & 0xFFF or e['off'] + at in g.edits:      # marked in the map, or seeded for another copy
            already += 1
            continue
        g.edit(e['off'] + at, struct.pack('<IB', flags | seed, 1))
        seeded.append(tile + (flags, flags | seed))
    return dict(tiles=list(t), seeded=seeded, already=already)


def plain_volume(p, index):
    """Whether an export is a plain volume: an actor whose only children are its brush component and model, and
    the component has none."""
    tc = p.own(index, 'BrushComponent', 0)
    kids = p.children.get(index, [])
    return tc > 0 and not ({p.cls(k) for k in kids} - {'BrushComponent', 'Model'}) and not p.children.get(tc)


def rebuild_template(p):
    """The volume add_rebuild_volume clones, by its name in the persistent level: REBUILD_TEMPLATE where the map has
    it, else the first plain volume with a brush model of the persistent level by REBUILD_FALLBACKS (F-59, F-67). A
    turned one would do as well: add_volume saves the clone unturned, its brush's own box stretched over the tiles."""
    if PL + REBUILD_TEMPLATE in p.by_name:
        return REBUILD_TEMPLATE
    found = {}
    for path, index in p.by_name.items():
        cls = p.cls(index)
        if cls not in REBUILD_FALLBACKS or not path.startswith(PL) or '.' in path[len(PL):] or cls in found:
            continue
        if not plain_volume(p, index) or p.own(index, 'Brush', 0) <= 0:
            continue
        found[cls] = path[len(PL):]
    for cls in REBUILD_FALLBACKS:
        if cls in found:
            return found[cls]
    raise ValueError('the map has no plain volume with a brush to clone a rebuild volume from')


def volume_pose(p, volume, box):
    """(location, scale): the Location and DrawScale3D that stretch volume `volume`'s brush over `box` (world [x0, x1,
    y0, y1, z0, z1]), unturned, its own DrawScale kept."""
    origin, extent = brush_bounds(p, volume)
    uniform = float(p.own(volume, 'DrawScale', 1.0) or 1.0)
    centre = [(box[2 * k] + box[2 * k + 1]) / 2 for k in range(3)]
    half = [(box[2 * k + 1] - box[2 * k]) / 2 for k in range(3)]
    scale = [half[k] / (extent[k] * uniform) for k in range(3)]
    location = [centre[k] - scale[k] * uniform * origin[k] for k in range(3)]
    return location, scale


def add_volume(g, p, box, cls_name, template, tag=None):
    """A volume of class `cls_name` (an XComGame class) whose bounds are `box` (world [x0, x1, y0, y1, z0, z1]): the
    map's plain volume `template` (its name in the persistent level; its actor and brush component, the brush model
    staying shared) cloned, placed and scaled, and retyped where it is of another class. Its Tag is `tag` (the class's
    name by default: the template's own tag would match what scripts look for by it). Returns dict(export, mapping
    (template export -> clone), template (its export), location, scale)."""
    walker = Walker(p, g)
    ti = p.by_name[PL + template]
    tc = p.own(ti, 'BrushComponent', 0)
    if not plain_volume(p, ti):
        raise ValueError(f'{template} is not a plain volume (an actor, a brush component and a model)')
    location, scale = volume_pose(p, ti, box)
    retype = p.cls(ti) != cls_name
    if retype:
        # the cooked maps hold XComGame as a package export (their XComGame class imports hang under it)
        package = g.find_import('Package', 'XComGame', 0)
        if package is None:
            found = [i for i in range(1, len(p.exports) + 1)
                     if p.cls(i) == 'Package' and p.name(i) == 'XComGame' and p.exports[i - 1]['outer'] == 0]
            if len(found) != 1:
                raise ValueError('the map has no XComGame package to import the volume class from')
            package = found[0]
        cls = g.add_import('Core', 'Class', package, cls_name)
        default = g.add_import('XComGame', cls_name, package, f'Default__{cls_name}')
        comp_arch = g.add_import('Engine', 'BrushComponent', default, 'BrushComponent0')
    first = len(g.entries) + 1
    mapping = {ti: first, tc: first + 1}
    name_index = g.name(cls_name) if retype else g.entries[ti - 1].name_index
    tag_index = g.name(tag or cls_name)
    for old in (ti, tc):
        e = p.exports[old - 1]
        off, size = e['off'], e['size']
        data = bytearray(p.data[off:off + size])
        start = legacy_props.props_start(p.data, e, p.names) - off
        for prop, at in walker.refs(bytes(data), start, size):
            value = struct.unpack_from('<i', data, at)[0]
            if value in mapping:
                struct.pack_into('<i', data, at, mapping[value])
        g.fresh_net_index(old, data, at=start - 4)
        if old == ti:
            at = walker.value(bytes(data), start, size, 'Tag[0]')
            if at is not None:
                struct.pack_into('<ii', data, at, tag_index, 0)
            data = set_vector(walker, g, data, start, 'Location', location)
            data = set_vector(walker, g, data, start, 'DrawScale3D', scale)
            if any(p.own(ti, 'Rotation', [0, 0, 0])):       # (the box is unturned)
                data = set_struct(walker, g, data, start, 'Rotation', 'Rotator', '<3i', [0, 0, 0])
            new = g.add_export(old, bytes(data), number=g.unused_number(name_index), name_index=name_index)
            if retype:
                g.entries[new - 1].put('<i', 0, cls)
            # its archetype stays the template's, none: the game's own placed volumes have none either (their class
            # default object stands in); the default object is imported for its brush component template
        else:
            new = g.add_export(old, bytes(data), number=g.entries[old - 1].name_number)
            g.entries[new - 1].put('<i', 8, mapping[ti])
            if retype:
                g.entries[new - 1].put('<i', 20, comp_arch)
        if new != mapping[old]:
            raise ValueError('the volume clones did not get the planned indices')
    return dict(export=mapping[ti], mapping=mapping, template=ti, location=location, scale=scale)


def box_reach(p, template, box):
    """The sphere radius the game gives a clone of the volume `template` (its name in the persistent level) placed
    over `box` (add_volume): the template's brush's sphere times the largest of the scales that stretch its brush
    over the box (volume_sphere's rule)."""
    ti = p.by_name[PL + template]
    _, extent = brush_bounds(p, ti)
    return brush_sphere(p, ti) * max((box[2 * k + 1] - box[2 * k]) / 2 / extent[k] for k in range(3))


def reach_box(p, template, centre, radius):
    """The box [x0, x1, y0, y1, z0, z1] to place a clone of `template` over so that the game's sphere for it has
    `radius` about `centre`: the template's brush scaled alike on every axis."""
    ti = p.by_name[PL + template]
    _, extent = brush_bounds(p, ti)
    scale = radius / brush_sphere(p, ti)
    return [centre[k // 2] + (scale if k % 2 else -scale) * extent[k // 2] for k in range(6)]


_DIAGONAL = weakref.WeakKeyDictionary()     # package -> its baked diagonal cover tiles (diagonal_tiles)
COVER_DIAGONAL = 0x10000
COVER_STORE = 1         # the container's second store: the cover flags (world_links.NAMES)
# the tiles over a floor tile that carry its standing-room mark (0x80000, research/native/cover-build.md, section 2):
# kept with a diagonal tile the rebuild leaves alone, since only the floor tile's own rebuild writes them
STANDING_ROOM = 2


def diagonal_tiles(p):
    """The tiles of the map's bake whose cover flags carry COVER_Diagonal (frozenset of (x, y, z)): where a unit in
    the corner of a slanted wall gets cover along the diagonals. The map's full build wrote the flag, from its cover
    seeds; a tile the battle rebuilds loses it for good (F-149). Empty for a package with no tile data."""
    found = _DIAGONAL.get(p)
    if found is None:
        try:
            blob = static_flags(p)[1]
        except ValueError:
            found = frozenset()
        else:
            store = world_links.parse_container(blob)['stores'][COVER_STORE]
            found = frozenset(t['tile'] for c in store['chunks'] for t in c['tiles']
                              if t['present'] and struct.unpack_from('<I', blob, t['off'])[0] & COVER_DIAGONAL)
        _DIAGONAL[p] = found
    return found


# a marked corner's cover bit: the diagonal facing (sx, sy) in game axes (research/native/cover-build.md, section 4's
# diagonal table; scene_metadata.DIAGONAL_DIRECTIONS)
DIAGONAL_BITS = {(-1, 1): 0x1, (1, -1): 0x2, (-1, -1): 0x4, (1, 1): 0x8}


def diagonal_edit(p, lane):
    """The project's diagonal cover (the native edit's `diagonalCover`: `marks` [{at, toward, low?}], `removed` [at],
    each `at` a world place in a tile, its middle; `low` the corners of `toward` that are half cover) as tiles of the
    map's grid (level_grid): dict(marks {tile: the cover bits of its corners (0x1 to 0x8), with the low bit (0x10 to
    0x80) of each half one}, removed (the map's marked tiles that lose their diagonal cover; a tile the project marks
    again is a mark), outside (the places off the grid or with no corner, left out)), or None for none. Diagonal
    cover by hand: private/plans/todo/diagonal-cover-by-hand-and-views-plan.md, section 3.3."""
    if not lane or not (lane.get('marks') or lane.get('removed')):
        return None
    grid = level_grid(p)
    corner, dims = (grid['tx'], grid['ty'], grid['tz']), (grid['nx'], grid['ny'], grid['nz'])
    size = (seed_map.TILE, seed_map.TILE, seed_map.FLOOR)

    def tile(at):
        return tuple(int(math.floor((float(at[k]) - corner[k]) / size[k])) for k in range(3))
    marks, outside = {}, []
    for m in lane.get('marks') or []:
        t = tile(m['at'])
        bits = 0
        for d in m.get('toward') or []:
            bits |= DIAGONAL_BITS.get((int(d[0]), int(d[1])), 0)
        for d in m.get('low') or []:
            bits |= (DIAGONAL_BITS.get((int(d[0]), int(d[1])), 0) & bits) << 4       # (half: the corner's low bit)
        if not bits or not all(0 <= t[k] < dims[k] for k in range(3)):
            outside.append([float(v) for v in m['at']])
            continue
        marks[t] = marks.get(t, 0) | bits
    bake = diagonal_tiles(p)
    removed = {t for t in (tile(a) for a in lane.get('removed') or []) if t in bake and t not in marks}
    return dict(marks=marks, removed=removed, outside=outside)


def diagonal_marked(g, p):
    """The map's marked tiles (its bake's diagonal cover, diagonal_tiles) that the project leaves marked: less those
    its `removed` names (the grower's diagonal_edit, diagonal_edit's record). A frozenset."""
    edit = getattr(g, 'diagonal_edit', None)
    bake = diagonal_tiles(p)
    return frozenset(bake - edit['removed']) if edit else bake


def changed_tiles(boxes, grid):
    """The tiles world boxes stand on (scene_metadata.changed_tiles, the rule's one home: the compiler and the page
    count them so too), on the grid level_grid gives."""
    return scene_metadata.changed_tiles(boxes, (grid['ox'], grid['oy'], grid['oz']), (grid['nx'], grid['ny'], grid['nz']),
                                        (seed_map.TILE, seed_map.TILE, seed_map.FLOOR), seed_map.MARGIN)


def rebuild_spares(p, box, radius, spare=False, changed=None, edit=None):
    """What a rebuild volume over `box` (its bounds' sphere `radius`) must leave alone, or None when it reaches
    nothing of the kind: dict(corner: the game's tile corner, need: the tile box it is put there for (the tiles whose
    centres the box holds), forbidden: the tiles its volumes must not take, spared: the diagonal tiles among them the
    one volume would have reached, rebuilt: the diagonal tiles inside the box, which the rebuild takes, written: those
    inside it next to a change, which the Build writes itself, whole: those a change stands on, which the Build writes
    whole, on: the tiles the changes stand on).

    A diagonal tile outside the box is left alone, with the two tiles over it. Without `changed` one inside the box is
    rebuilt and loses its diagonal cover. With `changed` (the world boxes of what changed there: a copy, a hidden or
    moved piece, a piece whose flags change) every diagonal tile inside is left out of the rebuild too, with the two
    tiles over it but those a change stands on: a tile the changes do not stand on (changed_tiles) is next to them
    only, `written` (diagonal_keep.py works out what the change alters of it), and one they stand on is written
    `whole` (diagonal_keep works the tile out as the game's build would, its links included, F-154). With `spare` (a
    volume that is there for no change of the map's pieces: a grown grid's) the ones inside are left alone as they
    are. `edit` (diagonal_edit's record): the project's diagonal cover, its marks among the diagonal tiles and its
    removed ones out of them."""
    import rebuild_fit
    diagonal = diagonal_tiles(p)
    if edit:
        diagonal = (diagonal - edit['removed']) | frozenset(edit['marks'])
    if not diagonal:
        return None
    grid = level_grid(p)
    corner = (grid['tx'], grid['ty'], grid['tz'])
    need = rebuild_fit.centred(box, corner)
    if need is None:
        return None
    inside = lambda t: all(need[2 * k] <= t[k] <= need[2 * k + 1] for k in range(3))  # noqa: E731
    on = changed_tiles(changed, grid) if changed else None
    written = sorted(t for t in diagonal if not spare and inside(t) and on is not None and t not in on)
    whole = sorted(t for t in diagonal if not spare and inside(t) and on is not None and t in on)
    kept = {t for t in diagonal if spare or not inside(t)} | set(written) | set(whole)
    forbidden = set(kept)
    for x, y, z in kept:
        forbidden |= {(x, y, z + n) for n in range(1, STANDING_ROOM + 1)
                      if spare or not inside((x, y, z + n)) or on is not None and (x, y, z + n) not in on}
    reach = rebuild_fit.span([(box[2 * k] + box[2 * k + 1]) / 2 for k in range(3)], radius, corner)
    reached = lambda t: all(reach[k][0] <= t[k] <= reach[k][1] for k in range(3))  # noqa: E731
    rebuilt = sorted(t for t in diagonal if t not in kept)
    on_set = sorted(on) if on else []
    if not any(reached(t) for t in forbidden):
        return dict(corner=corner, need=need, forbidden=set(), spared=[], rebuilt=rebuilt, written=[], whole=[],
                    on=on_set) if rebuilt or on_set else None
    return dict(corner=corner, need=need, forbidden=forbidden, spared=sorted(t for t in kept if reached(t)),
                rebuilt=rebuilt, written=[t for t in written if reached(t)], whole=[t for t in whole if reached(t)],
                on=on_set)


def add_rebuild_volume(g, p, box, template=None, spare=False, changed=None):
    """An XComRebuildWorldDataVolume whose bounds are `box` (world [x0, x1, y0, y1, z0, z1]): the map's volume
    `template` (its actor and brush component) cloned, retyped, placed and scaled (add_volume). The battle rebuilds the
    tiles within the bounds' sphere radius of their centre, in x and y and in z (XGBattle.DoWorldDataRebuild), and
    that sphere is the template's brush's times the largest scale (volume_sphere), often far past the box. Returns
    dict(export, location, scale, bounds, rebuildExtent: that radius).

    Where that reach would take a tile with diagonal cover that the box is not there for (rebuild_spares; F-149), the
    box's tiles get several smaller volumes instead that reach none of them (rebuild_fit.fit). `export` is then the
    first, and add_to_level lists the others after it wherever it is listed; the record gains `fitted`
    (dict(volumes: the exports, spared: the diagonal tiles left alone)) and its location, scale and rebuildExtent are
    the first volume's. A record of a box that holds diagonal tiles names them in `diagonalRebuilt`: the rebuild takes
    their diagonal cover; with `changed` (rebuild_spares) they are left out instead, the ones next to the change named
    in `diagonalWritten` and the ones it stands on in `diagonalWhole`, and the grower gathers them (`diagonal_writes`,
    `diagonal_whole`) for the Build to write after (diagonal_keep.write). The grower gathers the `changed` boxes too
    (`change_boxes`), whose tiles the Build writes as the battle's rebuild will leave them (start_tiles.write)."""
    import rebuild_fit
    if changed:
        g.__dict__.setdefault('change_boxes', []).extend([float(v) for v in b] for b in changed)
    template = template or rebuild_template(p)
    radius = box_reach(p, template, box)
    spares = rebuild_spares(p, box, radius, spare, changed, getattr(g, 'diagonal_edit', None))
    cubes = rebuild_fit.fit(spares['need'], spares['forbidden']) if spares and spares['forbidden'] else []
    note = {'diagonalRebuilt': [list(t) for t in spares['rebuilt']]} if spares and spares['rebuilt'] else {}
    if spares and spares['written']:
        note['diagonalWritten'] = [list(t) for t in spares['written']]
        if not hasattr(g, 'diagonal_writes'):
            g.diagonal_writes = set()
        g.diagonal_writes.update(spares['written'])
    if spares and spares['whole']:
        note['diagonalWhole'] = [list(t) for t in spares['whole']]
        if not hasattr(g, 'diagonal_whole'):
            g.diagonal_whole = set()
        g.diagonal_whole.update(spares['whole'])
    if not cubes:
        made = add_volume(g, p, box, 'XComRebuildWorldDataVolume', template)
        return dict(export=made['mapping'][made['template']], template=template, location=made['location'],
                    scale=made['scale'], bounds=box, rebuildExtent=radius, **note)
    made, first = [], None
    for cube in cubes:
        centre, reach = rebuild_fit.pose(cube, spares['corner'])
        one = add_volume(g, p, reach_box(p, template, centre, reach), 'XComRebuildWorldDataVolume', template)
        made.append(one['mapping'][one['template']])
        first = first or dict(one, reach=reach)
    if not hasattr(g, 'rebuild_more'):
        g.rebuild_more = {}
    g.rebuild_more[made[0]] = made[1:]
    return dict(export=made[0], template=template, location=first['location'], scale=first['scale'], bounds=box,
                rebuildExtent=first['reach'], fitted=dict(volumes=made, spared=[list(t) for t in spares['spared']]),
                **note)


def diagonal_words(volume):
    """What a rebuild volume's record says of the map's diagonal cover, for the Build's log: '' for most."""
    fitted, lost = volume.get('fitted'), volume.get('diagonalRebuilt')
    kept = (volume.get('diagonalWritten') or []) + (volume.get('diagonalWhole') or [])
    words = ''
    if fitted:
        more = len(fitted['volumes']) - 1
        words = ((f" and {more} more" if more else '') + f" (fitted to its tiles: one volume over them would have "
                 f"reached {len(fitted['spared'])} tiles with diagonal cover, which the rebuild takes away)")
    if lost:
        words += f"; tiles {', '.join(str(tuple(t)) for t in lost)} are rebuilt and lose their diagonal cover"
    if kept:
        words += f"; tiles {', '.join(str(tuple(t)) for t in kept)} with diagonal cover written by the Build"
    return words


def diagonal_candidates(g, p, box, grid, carry):
    """The tiles a copy of one of the map's own pieces stands on (its world `box`; changed_tiles) where the Build may
    write a corner with diagonal cover the copy carries (diagonal_keep.write's `candidates`, F-155), gathered in the
    grower's `diagonal_candidates` {tile: 'carried'}. The copy (`carry`: (actor, location, rotation), the original and
    the copy's pose) carries the map's marks (diagonal cover plan, 5.4): a tile is 'carried' where its centre, taken
    back through the copy's move, falls on a tile of the original's with diagonal cover in the bake that the project
    leaves marked (diagonal_marked), and nothing elsewhere; a carried tile gets diagonal cover where a diagonal still
    gives some there, as a seeded tile would. A piece with no place of its own in the map (made from numbers, a cover
    block, a piece brought from another map) carries nothing: its diagonal cover is what the project marks (KB-20)."""
    import numpy as np
    from export_math import transform
    tiles = changed_tiles([box], grid)
    found = g.__dict__.setdefault('diagonal_candidates', {})
    marked = diagonal_marked(g, p)
    if not marked:
        return
    actor, location, rotation = carry
    src = np.array(transform(p.own(actor, 'Location', [0.0, 0.0, 0.0]), p.own(actor, 'Rotation', [0, 0, 0]),
                             [1.0, 1.0, 1.0]), float)
    dst = np.array(transform(location, rotation, [1.0, 1.0, 1.0]), float)
    back = src @ np.linalg.inv(dst)
    corner = (grid['tx'], grid['ty'], grid['tz'])
    size = (seed_map.TILE, seed_map.TILE, seed_map.FLOOR)
    for t in tiles:
        centre = [corner[k] + size[k] * (t[k] + 0.5) for k in range(3)] + [1.0]
        home = back @ np.array(centre)
        if tuple(int(np.floor((home[k] - corner[k]) / size[k])) for k in range(3)) in marked:
            found[t] = 'carried'


def tile_volume(g, p, tile, grid=None):
    """A small rebuild volume over one tile (x, y, z): its bounds' sphere (radius 24) stays inside the tile, so the
    battle's rebuild of it queues that tile alone. A ladder copy's linked top tile gets one, first among the
    volumes the Build adds (research/native/ladder-links.md, "The rebuild's work set"). The volume is the template's
    brush scaled alike on every axis to that sphere (reach_box): a box of 32 by 32 by 16 gave a sphere of 24 only
    where the template's brush is a cube (F-150)."""
    import rebuild_fit
    grid = grid or level_grid(p)
    c = [grid['ox'] + (tile[0] + 0.5) * seed_map.TILE, grid['oy'] + (tile[1] + 0.5) * seed_map.TILE,
         grid['oz'] + (tile[2] + 0.5) * seed_map.FLOOR]
    return add_rebuild_volume(g, p, reach_box(p, rebuild_template(p), c, rebuild_fit.SINGLE))


def actor_list(p, data=None):
    """The persistent Level's actor list, where it lies: (the Level's export index, the list's offset in `data`, the
    actors: export indices, 0 for an empty slot, in order). `data` is the Level's export bytes as an edit has left them
    (a Grower's export_data), else the map's own (the offset then in p.data). The list is the first thing of the
    Level's native data, owned by the Level; anything else is refused. The one reader of it (review finding 55)."""
    level = p.by_name['TheWorld.PersistentLevel']
    end = p.properties(level)[1]
    at = end if data is None else end - p.exports[level - 1]['off']
    data = p.data if data is None else data
    owner, count = struct.unpack_from('<ii', data, at)
    if owner != level:
        raise ValueError('the Level does not start its native data with its actor list')
    return level, at, list(struct.unpack_from('<%di' % count, data, at + 8))


def level_actors(p):
    """The persistent Level's actor list (export indices, 0 for an empty slot), in order."""
    return actor_list(p)[2]


def volume_sphere(p, volume):
    """(origin, radius) of a volume's bounds as the game reads them: its brush's bounds moved and scaled with the
    actor, the sphere's radius the brush's own times the actor's largest scale on any axis (UE3's
    FBoxSphereBounds::TransformBy; findings register F-150: read off a battle's save to the tile). It is not the
    scaled box's diagonal: a flat brush stretched upward gets a sphere many times its box."""
    origin, extent = brush_bounds(p, volume)
    scale = [v * p.own(volume, 'DrawScale', 1.0) for v in p.own(volume, 'DrawScale3D', [1.0, 1.0, 1.0])]
    loc = p.own(volume, 'Location', [0.0, 0.0, 0.0])
    radius = brush_sphere(p, volume) * max(abs(v) for v in scale)
    if any(p.own(volume, 'Rotation', [0, 0, 0])):
        if any(abs(v) > 1e-3 for v in origin):
            raise ValueError(f'{p.name(volume)} is turned about an off-centre brush')
        return list(loc), radius
    return [loc[k] + scale[k] * origin[k] for k in range(3)], radius


def rebuild_order(p, queued=True):
    """The battle's rebuild work set at level start, in order, as {tile: place}: XGBattle.DoWorldDataRebuild calls
    RebuildTileData(Origin, SphereRadius, SphereRadius) for every XComRebuildWorldDataVolume (AllActors: the
    persistent level's actor list first, the streamed levels' after), and each call adds the tiles of the box Origin ±
    SphereRadius, X outer, Y middle, Z inner, whose static flags have a bit in 0xFFF; a tile keeps the place it was
    first added at (research/native/ladder-links.md, G5). The streamed levels' volumes and LWR's mutator (which
    queues its own first) are not read here. With `queued` False, every tile of the boxes whatever its flags: the
    tiles a seed bit would put in the work set (start_tiles.py)."""
    import math
    grid = level_grid(p)
    _, blob, dims, where = static_flags(p)
    size = (seed_map.TILE, seed_map.TILE, seed_map.FLOOR)
    # the game works the boxes' tiles out from its own corner (WorldBounds'), a unit under the level volume's
    lo_of = (grid['tx'], grid['ty'], grid['tz'])

    def flags(tile):
        at = where.get(tile)
        if at is None:
            return 0
        value, present = struct.unpack_from('<IB', blob, at)
        return value if present else 0

    order = {}
    for a in level_actors(p):
        if a <= 0 or p.cls(a) != 'XComRebuildWorldDataVolume':
            continue
        c, r = volume_sphere(p, a)
        span = [(max(0, math.floor((c[k] - r - lo_of[k]) / size[k])), min(dims[k] - 1, math.floor((c[k] + r - lo_of[k]) / size[k])))
                for k in range(3)]
        for x in range(span[0][0], span[0][1] + 1):
            for y in range(span[1][0], span[1][1] + 1):
                for z in range(span[2][0], span[2][1] + 1):
                    if (x, y, z) not in order and (not queued or flags((x, y, z)) & 0xFFF):
                        order[(x, y, z)] = len(order)
    return order


def ladder_order(p, ladders):
    """Each ladder copy's climb against the built map's rebuild order (rebuild_order): `ladders` [{copy, foot, top}]
    (tiles). The rebuild makes a ladder's links from its foot tile, which must be queued; the down link survives when
    the top tile comes first, or is never queued. Returns the records with each tile's place; raises ValueError when
    a climb would lose a link."""
    order = rebuild_order(p)
    out = []
    for l in ladders:
        foot, top = order.get(tuple(l['foot'])), order.get(tuple(l['top']))
        rec = dict(l, footPlace=foot, topPlace=top)
        out.append(rec)
        if foot is None:
            raise ValueError(f"{l['copy']}'s foot tile {l['foot']} is in no rebuild volume: the game makes no climb")
        if top is not None and top > foot:
            raise ValueError(f"{l['copy']}'s top tile {l['top']} is rebuilt after its foot {l['foot']} (places {top} and "
                             f"{foot}): the top's rebuild would take the climb's down link away")
    return out


def has_mesh(p, actor):
    return any(static_mesh(p, ci) > 0 or skeletal_mesh(p, ci) > 0 for ci in subtree(p, actor))


# Whether the actor can touch the game's tiles: it collides (bCollideActors) and one of its mesh components does
# (CollideActors). A piece that can't (a sky dome) changes no tile, so its copy seeds none. The export's rule too.
collides = piece_flags.collides


# Scenery the map shows but the game ignores (F-100): the ground planes and pavements a map is seen against beyond
# its play area save their collision off (bCollideActors and bPathColliding on the actor, CollideActors and
# BlockRigidBody on its mesh), so the tile rebuild finds no floor on them. A piece no taller than this is low enough
# to be ground, a pavement or a stain.
SCENERY_LOW = 32.0
SCENERY_CLASSES = ('XComLevelActor',)


def walkable_scenery(p, actor, box):
    """Whether a piece is low scenery whose collision the map turned off (F-100): a level actor of a static mesh
    that saves bCollideActors false, its world `box` ([x0, x1, y0, y1, z0, z1]) at most SCENERY_LOW high."""
    return (p.cls(actor) in SCENERY_CLASSES and p.effective(actor, 'bCollideActors', True) is False
            and any(static_mesh(p, ci) > 0 for ci in subtree(p, actor)) and box[5] - box[4] <= SCENERY_LOW)


def make_walkable(g, p, actor, mapping=None):
    """The piece `actor` (or its clone, by clone_actor's `mapping` {original export: clone}) with its collision on,
    as the game's floor pieces have it: bCollideActors and bPathColliding on the actor, CollideActors and
    BlockRigidBody on each of its mesh components (F-100). Same-size writes where the export saves them false;
    added where it saves none."""
    import native_lights
    mapping = mapping or {}
    walker = Walker(p, g)
    parts = [(actor, ('bCollideActors', 'bPathColliding'))]
    parts += [(ci, ('CollideActors', 'BlockRigidBody')) for ci in subtree(p, actor) if static_mesh(p, ci) > 0]
    for source, names in parts:
        index = mapping.get(source, source)
        data = bytearray(g.export_data(index))
        start = native_lights.props_start(p, source)
        for name in names:
            data = native_lights.set_property(walker, g, data, start, name, 'BoolProperty', None, b'\x01')
        g.relocate(index, bytes(data))


# what ground_collision writes on a ground shape's clone: always (on a donor of SCENERY_CLASSES the second too), and
# where the donor saves them (piece_flags.MADE_GROUND says the flags' part of it to the page and the compiler)
GROUND_ON = ('bCollideActors', 'bPathColliding')
GROUND_SAVED = (('bIgnoreForCover', b'\x00'), ('bCanClimbOnto', b'\x01'), ('bIsValidDestination', b'\x01'),
                ('bWorldGeometry', b'\x01'), ('bCanStepUpOn', b'\x01'))


def ground_collision(g, p, actor, mapping):
    """A ground shape's copy (custom geometry plan, M6) collides, whatever its donor saves: many of the game's ground
    planes are backdrop saved with their collision off and some ignore cover (research/evidence/ground-audit.py). The
    clone (clone_actor's `mapping`) gets bCollideActors on the actor (bPathColliding too on an XComLevelActor, as
    make_walkable gives) and CollideActors and BlockRigidBody on its mesh components; bIgnoreForCover off and
    bCanClimbOnto, bIsValidDestination, bWorldGeometry and bCanStepUpOn on where the donor saves them otherwise
    (written only where saved: a class without them must not get them; EXP-79 run D: URB_Demolition_EWI's grass plane
    saves bWorldGeometry off, and a block made from it was walked into, its top never the cursor's; the asphalt
    StaticMeshActor of URB_CommercialAlley saves bCanStepUpOn off, and no soldier climbed onto a block made from it).
    Returns the names changed."""
    import native_lights
    walker = Walker(p, g)
    changed = []
    on = GROUND_ON if p.cls(actor) in SCENERY_CLASSES else GROUND_ON[:1]
    parts = [(actor, on, GROUND_SAVED)]
    parts += [(ci, ('CollideActors', 'BlockRigidBody'), ()) for ci in subtree(p, actor) if static_mesh(p, ci) > 0]
    for source, names, saved_only in parts:
        index = mapping.get(source, source)
        data = bytearray(g.export_data(index))
        start = native_lights.props_start(p, source)
        for name in names:
            if p.effective(source, name, True) is False:
                changed.append(name)
            data = native_lights.set_property(walker, g, data, start, name, 'BoolProperty', None, b'\x01')
        for name, raw in saved_only:
            at = walker.value(bytes(data), start, len(data), name + '[0]')
            if at is not None and data[at:at + 1] != raw:
                data[at:at + 1] = raw
                changed.append(name)
        g.relocate(index, bytes(data))
    return changed


def in_grid(box, grid):
    """Whether a world box crosses the tile grid's footprint (level_grid's)."""
    return (box[1] > grid['ox'] and box[0] < grid['ox'] + 96.0 * grid['nx']
            and box[3] > grid['oy'] and box[2] < grid['oy'] + 96.0 * grid['ny'])


def assembly_box(p, members):
    """The world box of an assembly's copy: the union of its members' piece_box ([(actor, location, rotation)]), of
    those with a static mesh (a door's skeletal leaf is boxed by its frame until step G4)."""
    boxes = [piece_box(p, actor, location, rotation) for actor, location, rotation in members if has_mesh(p, actor)]
    if not boxes:
        raise ValueError(f'no member of {[p.name(a) for a, _, _ in members]} has a mesh')
    return [f(b[k] for b in boxes) for k in range(6) for f in [(min, max)[k % 2]]]


def add_tiles_box(g, p, box):
    """A copy's tiles, for its world box [x0, x1, y0, y1, z0, z1] (a piece's piece_box, an assembly's assembly_box):
    seeds above the ground and a rebuild volume over every tile it crosses (level 0 has floor flags everywhere, so the
    rebuild always re-checks it). Returns the manifest's `tiles` section; its `volume` is the new actor to add to the
    level. None for a box that crosses no tile of the map (a piece outside the level volume, as the maps' own backdrop
    pieces are): it has no tiles to seed or rebuild."""
    grid = level_grid(p)
    seeds = seed_tiles_under(g, p, box, grid)
    t = seeds['tiles']
    if t is None:
        return None
    x0, x1, y0, y1, _, z1 = seed_map.world_of(t, grid)
    volume = add_rebuild_volume(g, p, [x0, x1, y0, y1, grid['oz'] - seed_map.REBUILD_PAD, z1], changed=[box])
    return dict(grid=grid, box=box, tiles=t, seeded=len(seeds['seeded']), alreadyMarked=seeds['already'],
                seededTiles=[list(x[:3]) for x in seeds['seeded']], volume=volume)


def hide_tiles(g, p, box, grid=None):
    """A rebuild volume over the tiles a hidden piece's world `box` crosses, plus a ring of one tile, so the game's
    rebuild at load re-checks them without it (they carry the bake's marks already: no seeds are needed). Returns the
    volume section, or None for a box that crosses no tile of the map (a piece outside the level volume): there is
    nothing to re-check."""
    grid = grid or level_grid(p)
    t = seed_map.tiles_touched(box, grid, seed_map.MARGIN)
    # (a piece in the ground level alone, a flat ground plane among them, reaches no level from 1 up, which seeds
    # count from: its tiles still need re-checking, and the volume reaches down to the grid's bottom anyway. EXP-78:
    # the farm's deleted ground plane at -128 kept its floors, "outside the map's tiles")
    t = t[:5] + (max(t[5], t[4] - 1),) if t else None
    t = seed_map.clamp((t[0] - 1, t[1] + 1, t[2] - 1, t[3] + 1, t[4], t[5] + 1), grid) if t else None
    if t is None:
        return None
    x0, x1, y0, y1, _, z1 = seed_map.world_of(t, grid)
    return dict(tiles=list(t), volume=add_rebuild_volume(g, p, [x0, x1, y0, y1, grid['oz'] - seed_map.REBUILD_PAD, z1],
                                                         changed=[box]))


def hide_pieces(g, p, hides, volumes=True):
    """The pieces `hides` ({name, box}: actors of the map's level, as an editor delete or move hides them) taken out
    of the map as the level designer's delete takes them: each one's slot in the Level's actor list becomes None, so
    the game never spawns it into the world (no mesh, collision, cover or line of sight; the loot count,
    XComCollectible.CollectCollectibles, walks the same list, so a hidden collectible isn't loot). Every other piece's
    AffectedChildren drops it, so breaking one doesn't put it through its states. Building floor caches and visibility
    groups that list it keep a dormant object. A rebuild volume over each re-checks its tiles at load (hide_tiles); a
    piece outside the map's tiles has none (its section's `tiles` and `volume` are None). Without `volumes` (a cleared
    map, whose one volume covers the whole grid: clear_level) none has a volume of its own.
    Returns (the manifest's sections, the volumes to add to the level)."""
    walker = Walker(p, g)
    level = p.by_name['TheWorld.PersistentLevel']
    grid = level_grid(p)
    rebuild = volumes       # (the list below takes the name)
    gone, out, volumes = set(), [], []
    for h in hides:
        i = p.by_name.get(PL + h['name'])
        if i is None or p.exports[i - 1]['outer'] != level:
            raise ValueError(f"no piece {h['name']} in the map's level to hide")
        gone.add(i)
        box = [float(v) for v in h['box']] if h.get('box') else piece_box(p, i, p.own(i, 'Location', [0.0, 0.0, 0.0]),
                                                                          p.own(i, 'Rotation', [0, 0, 0]))
        tiles = hide_tiles(g, p, box, grid) if rebuild else None
        if tiles:
            volumes.append(tiles['volume']['export'])
        out.append(dict(name=h['name'], export=i, box=box, tiles=tiles['tiles'] if tiles else None,
                        volume=tiles['volume'] if tiles else None, unlinkedFrom=[]))
    empty_slots(g, p, gone)
    # the pieces that list a hidden one as a child
    by_export = {s['export']: s for s in out}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in BREAKABLE or p.exports[i - 1]['outer'] != level or i in gone:
            continue
        ei = p.exports[i - 1]
        start = legacy_props.props_start(p.data, ei, p.names) - ei['off']
        kids = object_array(walker, p.data[ei['off']:ei['off'] + ei['size']], start, 'AffectedChildren')
        if not set(kids) & gone:
            continue
        cur = bytearray(g.export_data(i))
        now = object_array(walker, cur, start, 'AffectedChildren')
        g.relocate(i, bytes(set_object_array(walker, g, cur, start, 'AffectedChildren', [k for k in now if k not in gone])))
        for k in set(kids) & gone:
            by_export[k]['unlinkedFrom'].append(p.name(i).split('.')[-1])
    return out, volumes


def empty_slots(g, p, gone):
    """The persistent Level's actor list with the actors `gone` (export indices) in it as empty slots (None), as the
    level designer's delete leaves them: the game never spawns them. The Level export is relocated."""
    data = bytearray(g.export_data(p.by_name['TheWorld.PersistentLevel']))
    level, at, listed = actor_list(p, data)
    found = set()
    for k, actor in enumerate(listed):
        if actor in gone:
            found.add(actor)
            struct.pack_into('<i', data, at + 8 + 4 * k, 0)
    if found != set(gone):
        raise ValueError(f'not in the Level\'s actor list: {sorted(p.name(i) for i in set(gone) - found)}')
    g.relocate(level, bytes(data))


# ---------------------------------------------------------------- a cleared map (private/plans/done/clear-map-plan.md)
# What clear_level takes out of a cleared map's actor list (section 7, step 1): what belonged to the pieces that are
# gone and the editor never showed. Classes are matched exactly.
CLEAR_OUT = (
    # building and floor volumes (without pieces they would still cut away and hide at their old places; the map's
    # cursor volumes are the shell stage's, which takes them out and brings even storeys over the grid: shell.py --clear)
    'XComBuildingVolume', 'XComFloorVolume',
    # smoke, steam, stains and glints of what is gone (F-50)
    'Emitter', 'DecalActor', 'DecalActorMovable', 'LensFlareSource',
    # the map's ambient sounds: the jukebox, the hum of what is gone (the user, 18 November 2026: Clear left them in
    # the play area); the landing's go with its Skyranger, kept as the landing's
    'AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop', 'AmbientSoundMovable',
    # path-blocking, camera-blocking and damage volumes (EXP-08 switched Bar's off for the same reason)
    'PathBlockingVolume', 'GameCameraBlockingVolume', 'BlockingVolume', 'XComDamageVolume', 'DynamicBlockingVolume',
    'XComCameraVolume', 'XComHideVolume',
    # cover seeds: the cover the old geometry gave (the C0 survey's proposal; their native side is not read)
    'XComCoverSeed',
    # the lights the editor cannot edit or that belonged to the pieces (the directional lights and the sky light stay)
    'PointLight', 'PointLightMovable', 'PointLightToggleable', 'SpotLight', 'SpotLightMovable', 'SpotLightToggleable',
    'GeneratedMeshAreaLight', 'XComPointLight', 'XComSpotLight',
)
# What of CLEAR_OUT a clear that keeps the scenery outside the play area leaves when it stands outside (the compiler's
# `keepOutside` box): the lights, smoke, stains and glints of the pieces it kept
KEEP_OUTSIDE = ('Emitter', 'DecalActor', 'DecalActorMovable', 'LensFlareSource', 'PointLight', 'PointLightMovable',
                'AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop', 'AmbientSoundMovable',
                'PointLightToggleable', 'SpotLight', 'SpotLightMovable', 'SpotLightToggleable', 'GeneratedMeshAreaLight',
                'XComPointLight', 'XComSpotLight')
# What a clear takes out unless the project keeps them (`keepTriggers`, the Clear map window's "Keep the map's triggers
# and scripts"; findings register F-159): the map's trigger volumes (touch triggers, water volumes units wade in, the
# empty ones) and sight points. Left, a cleared map's water still makes units wade where the stream was, a crashed
# UFO's entry narration plays on the empty field and a console's narration when its place is seen. A trigger volume
# taken out has its events switched off too (switch_off_events). A mission stream's are the mission's, and stay.
CLEAR_TRIGGERS = ('TriggerVolume', 'XComSquadVisiblePoint')
KEEP_OUTSIDE = KEEP_OUTSIDE + CLEAR_TRIGGERS
# What a clear leaves (section 2's "Stay" rows), so an actor of a class on neither list is named in the report
CLEAR_KEEP = (
    'DominantDirectionalLight', 'DirectionalLight', 'DirectionalLightToggleable', 'SkyLight', 'SkyLightToggleable',
    'XComLevelVolume', 'XComCursorVolume', 'LightmassImportanceVolume', 'PostProcessVolume', 'WorldInfo', 'PlayerStart', 'PointInSpace',
    'XComSpawnPoint', 'XComSpawnPoint_Alien', 'XComAlienPod', 'XComAlienPod_Abduction', 'XComAlienPathNode',
    'XComMeldContainerSpawnPoint', 'XComNoSpawnVolume', 'XComRebuildWorldDataVolume',
    'XComAlienPod_Terror', 'XComAlienPod_Hunter', 'XComAlienSpawnVolume', 'XComWaveSystem', 'XComRainVolume',
    'XComWeatherControl',
    # a prefab's instance stays: the native picks the squad's spawn group from the points prefabs hold (F-96)
    'PrefabInstance', 'VisGroupActor', 'Note', 'KActor', 'CameraActor', 'XComCapturePointVolume',
    'XComDropshipAudioActor', 'XComTacticalSoundManager', 'XComInteractPoint', 'XComExtractionVolume',
    # the pieces: the editor's delete records take each one out, and the page shows them
    'XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComCollectible', 'XComFracLevelActor',
    'XComDecoFracLevelActor', 'KAsset', 'XComInteractiveLevelActor', 'XComLadder', 'XComMergedLevelActor',
    'XComOpacityFadeLevelActor', 'SkeletalMeshActor', 'SkeletalMeshActorMAT',
)


def archetype_path(p, i):
    """The archetype an actor was placed from (an import or an export's path), or ''."""
    a = p.exports[i - 1]['arch']
    return p.name(a) if a else ''


def landing_actor(p, i):
    """Whether a level actor is one of the landing's prefabs' (by its archetype; section 4): never taken out (LWR spawns
    the landing from them, a plain install plays them), the evac volume among them, which is a building volume, and
    the grounded Skyranger's dust, an emitter placed beside its prefab (the C0 survey: 17 landing actors on Bar)."""
    return scene_metadata.landing_archetype(archetype_path(p, i))


def clear_level(g, p, gone=(), keep=(), outside=None, keep_triggers=False):
    """A cleared map (Clear map plan, section 7): every actor of CLEAR_OUT's classes in the persistent level's actor
    list taken out (empty_slots, as a delete is made), and those of CLEAR_TRIGGERS unless `keep_triggers` (their touch
    events switched off: switch_off_events), but for the landing's prefabs' actors and those already gone
    (`gone`: export indices the edit takes out itself) and those the edit keeps on purpose (`keep`: the volumes of the
    map's buildings it edits in place) and, with `outside` ([x0, y0, x1, y1]: the play area of a clear that keeps
    the scenery outside it), the actors of KEEP_OUTSIDE's classes whose Location is outside that box; and one
    rebuild volume over the whole tile grid, all its
    levels, in place of one for each delete: the tiles the old pieces stood on carry the bake's marks, so the battle
    works them out again. Returns (the report: {out: {class: count}, kept: {class: count}, odd: {class: [names]},
    landing: [names], outside: {class: count}, eventsOff: [names], rebuildVolume}, the volume's export to add to the
    level)."""
    gone = set(gone)
    out, kept, odd, landing, take, beyond = {}, {}, {}, [], set(), {}
    # the actor list as the edit has left it so far (a van's or an emptied building's volumes may be out already)
    level, _, listed = actor_list(p, g.export_data(p.by_name['TheWorld.PersistentLevel']))
    for i in listed:
        if i <= 0 or i in gone or p.exports[i - 1]['outer'] != level:
            continue
        cls = p.cls(i)
        if i in keep:
            kept[cls] = kept.get(cls, 0) + 1
            continue
        if landing_actor(p, i):
            landing.append(p.name(i).split('.')[-1])
            continue
        if cls in CLEAR_TRIGGERS and keep_triggers:
            kept[cls] = kept.get(cls, 0) + 1
            continue
        if outside and cls in KEEP_OUTSIDE:
            x, y = p.own(i, 'Location', [0.0, 0.0, 0.0])[:2]
            if x < outside[0] or x > outside[2] or y < outside[1] or y > outside[3]:
                beyond[cls] = beyond.get(cls, 0) + 1
                continue
        if cls in CLEAR_OUT or cls in CLEAR_TRIGGERS:
            take.add(i)
            out[cls] = out.get(cls, 0) + 1
        elif cls in CLEAR_KEEP:
            kept[cls] = kept.get(cls, 0) + 1
        else:
            odd.setdefault(cls, []).append(p.name(i).split('.')[-1])
    if take:
        empty_slots(g, p, take)
    events_off = switch_off_events(g, p, [i for i in take if p.cls(i) == 'TriggerVolume'])
    grid = level_grid(p)
    box = [grid['ox'], grid['ox'] + seed_map.TILE * grid['nx'], grid['oy'], grid['oy'] + seed_map.TILE * grid['ny'],
           grid['oz'] - seed_map.REBUILD_PAD, grid['oz'] + seed_map.FLOOR * grid['nz']]
    volume = add_rebuild_volume(g, p, box)
    report = dict(out=dict(sorted(out.items())), kept=dict(sorted(kept.items())),
                  odd={k: sorted(v) for k, v in sorted(odd.items())}, landing=sorted(landing),
                  **({'outside': dict(sorted(beyond.items()))} if outside else {}),
                  taken=sorted(p.name(i).split('.')[-1] for i in take), eventsOff=events_off,
                  rebuildVolume=dict(bounds=volume['bounds'], extent=volume['rebuildExtent']))
    return report, volume['export']


def switch_off_events(g, p, volumes):
    """The sequence events whose Originator is one of `volumes` (export indices of the map `p`, grown by `g`) switched
    off (bEnabled false, written in place or added): a trigger volume out of the level's list can no longer be touched,
    and its events then cannot fire by any other road either. Returns their short names, sorted."""
    import native_lights
    volumes = set(volumes)
    if not volumes:
        return []
    walker = Walker(p, g)
    off = []
    for i in range(1, len(p.exports) + 1):
        if not p.cls(i).startswith('SeqEvent') or p.own(i, 'Originator') not in volumes:
            continue
        e = p.exports[i - 1]
        data = bytearray(g.export_data(i))
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        data = native_lights.set_property(walker, g, data, start, 'bEnabled', 'BoolProperty', None, b'\x00')
        g.relocate(i, bytes(data))
        off.append(p.name(i).split('.')[-1])
    return sorted(off)


FRACTURING = ('XComDecoFracLevelActor', 'XComFracLevelActor')
# more removed casters than this go to the relight in a file (--remove-caster-list)
CASTER_ARGS = 100


def find_prop(walker, b, at, end, wanted):
    """(kind, tag offset, value offset, size) of the tagged property `wanted` (name[index]) in b[at:end], or None."""
    for prop, kind, sub, v, size in walker.walk(bytes(b), at, end):
        if prop == wanted:
            return kind, v - 24 - (8 if kind in ('StructProperty', 'ByteProperty') else 0), v, size
    return None


def struct_elements(walker, b, at, size):
    """(start, end) of each struct in the array value b[at:at + size] (its count first)."""
    count = struct.unpack_from('<i', b, at)[0]
    pos, stop, out = at + 4, at + size, []
    for _ in range(count):
        gen = walker.walk(bytes(b), pos, stop)
        try:
            while True:
                next(gen)
        except StopIteration as done:
            out.append((pos, done.value))
            pos = done.value
    if pos != stop:
        raise ValueError('a struct array whose elements do not fill it')
    return out


def struct_entries(walker, b, field, ref):
    """The structs of an array property found as `field` (find_prop's) of export bytes `b`, each dict(raw: its bytes,
    actor: its object property `ref`, and where in raw that reference, MinZ and CutdownFloor lie, or None)."""
    if field is None:
        return []
    out = []
    for s, e in struct_elements(walker, b, field[2], field[3]):
        raw = bytes(b[s:e])
        at = {name: find_prop(walker, raw, 0, len(raw), name + '[0]') for name in (ref, 'MinZ', 'CutdownFloor')}
        out.append(dict(raw=raw, actor=struct.unpack_from('<i', raw, at[ref][2])[0] if at[ref] else 0,
                        actorAt=at[ref][2] if at[ref] else None, minZAt=at['MinZ'][2] if at['MinZ'] else None,
                        cutdownAt=at['CutdownFloor'][2] if at['CutdownFloor'] else None))
    return out


def entry_for(entry, actor, dz=0.0, floors=0):
    """A copy of a struct entry (struct_entries') naming `actor`, its MinZ raised by `dz` and its CutdownFloor by
    `floors`, where it saves them. CutdownFloor names a floor of the building (walls of floor 0 that rise through
    floor 1 name 2, those of floor 2 name 3) and 0 names none (a door's, on any floor): only one it names moves."""
    raw = bytearray(entry['raw'])
    struct.pack_into('<i', raw, entry['actorAt'], actor)
    if entry['minZAt'] is not None:
        struct.pack_into('<f', raw, entry['minZAt'], struct.unpack_from('<f', raw, entry['minZAt'])[0] + dz)
    if entry['cutdownAt'] is not None and raw[entry['cutdownAt']]:
        raw[entry['cutdownAt']] = max(1, min(255, raw[entry['cutdownAt']] + floors))
    return bytes(raw)


def with_array(g, b, element, field, name, entries):
    """The struct element b[s:e] (`element`) with its array property `name` (found as `field`, or None when it saves
    none) holding the struct bytes `entries`: set in place, or added before the element's closing None."""
    s, e = element
    payload = struct.pack('<i', len(entries)) + b''.join(entries)
    if field is not None:
        _, tag, at, size = field
        piece = bytearray(b[s:at]) + payload + bytes(b[at + size:e])
        struct.pack_into('<i', piece, tag - s + 16, len(payload))
        return bytes(piece)
    if not entries:
        return bytes(b[s:e])
    tag = struct.pack('<iiiiii', g.name(name), 0, g.name('ArrayProperty'), 0, len(payload), 0)
    return bytes(b[s:e - 8]) + tag + payload + bytes(b[e - 8:e])


def rebuilt(b, field, pieces):
    """Export bytes `b` with the array property found as `field` holding the struct bytes `pieces`."""
    _, tag, at, size = field
    body = struct.pack('<i', len(pieces)) + b''.join(pieces)
    out = bytearray(b[:at]) + body + bytes(b[at + size:])
    struct.pack_into('<i', out, tag + 16, len(body))
    return bytes(out)


def moved_box(box, before, after):
    """The world box `box` [x0, x1, y0, y1, z0, z1] carried as a piece is carried from the pose `before` to `after`
    ((location, rotation) each): the box of its turned corners."""
    import numpy as np
    from export_math import transform
    m = np.array(transform(after[0], after[1], [1, 1, 1]), float) @ np.linalg.inv(
        np.array(transform(before[0], before[1], [1, 1, 1]), float))
    corners = np.array([[x, y, z, 1.0] for x in box[0:2] for y in box[2:4] for z in box[4:6]]) @ m.T
    return [float(v) for k in range(3) for v in (corners[:, k].min(), corners[:, k].max())]


def building_floors(walker, g, p):
    """The level's building volumes' floors: {building export: (its bytes, the Floors property, [dict(element,
    volumes: world boxes of its floor volumes, field: its m_aCachedActors property or None, entries)])}."""
    import scene_metadata
    level = p.by_name['TheWorld.PersistentLevel']
    out = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'XComBuildingVolume' or p.exports[i - 1]['outer'] != level:
            continue
        b = g.export_data(i)
        e = p.exports[i - 1]
        found = find_prop(walker, b, legacy_props.props_start(p.data, e, p.names) - e['off'], len(b), 'Floors[0]')
        if found is None:
            continue
        floors = []
        for s, end in struct_elements(walker, b, found[2], found[3]):
            vols = find_prop(walker, b, s, end, 'FloorVolumes[0]')
            refs = list(struct.unpack_from(f'<{struct.unpack_from("<i", b, vols[2])[0]}i', b, vols[2] + 4)) if vols else []
            boxes = [scene_metadata.volume_bounds(p, r) for r in refs if r > 0]
            field = find_prop(walker, b, s, end, 'm_aCachedActors[0]')
            floors.append(dict(element=(s, end), volumes=[x for x in boxes if x], field=field,
                               entries=struct_entries(walker, b, field, 'ResidentActor')))
        out[i] = (b, found, floors)
    return out


def floor_at(buildings, box):
    """(building, floor index) whose floor volumes overlap the world box `box` [x0, x1, y0, y1, z0, z1] most, or None
    when none does. A door stands in its building's outer wall, where a floor volume often ends: URB_PoliceStation's
    end on the back wall's line, so a door's centre lies on their face."""
    best, most = None, 0.0
    for i, (_, _, floors) in buildings.items():
        for k, floor in enumerate(floors):
            got = 0.0
            for v in floor['volumes']:
                inter = 1.0
                for j in range(3):
                    inter *= max(0.0, min(box[2 * j + 1], v['max'][j]) - max(box[2 * j], v['min'][j]))
                got += inter
            if got > most:
                best, most = (i, k), got
    return best


def moved_cutdown(cut, floors):
    """A CutdownFloor moved by `floors` floors, as entry_for moves it: 0 names none and stays."""
    return max(1, min(255, cut + floors)) if cut else 0


def copy_floors(listings, here, there, floor_count):
    """A copy's building-floor listings (edit_floor_caches' rule; the editor's view has its twin, floors.js
    copyFloors, and both pass the cases in tests/floor_membership_cases.json). listings: the original's [(building,
    floor, cutdown)]; here and there: the (building, floor) the original and the copy stand in (floor_at), or None;
    floor_count(building): its floors. A piece listed nowhere stays so; one listed though it stands in no floor volume
    (a ladder on a building's outer wall), copied to none either, keeps its listings as they are; any other copy standing
    in no floor gets none; else each listing moves to the floor the copy stands in, as far above it as the original's
    listing is above the floor the original stands in (clamped to the building's floors), its CutdownFloor moved by as
    many floors. Returns [(n, building, floor, cutdown)], n the index of the listing each comes from; [] for none."""
    if not listings:
        return []
    if there is None and here is None:
        return [(n, b, k, cut) for n, (b, k, cut) in enumerate(listings)]
    if there is None:
        return []
    out = []
    for n, (b, k, cut) in enumerate(listings):
        rise = k - here[1] if here and here[0] == b else 0
        floor = max(0, min(floor_count(there[0]) - 1, there[1] + rise))
        out.append((n, there[0], floor, moved_cutdown(cut, floor - k)))
    return out


def edit_floor_caches(g, p, copies, replaced=None):
    """Copies join the cutaway of the building floor they stand in (private/plans/done/cars-doors-ladders-plan.md, 6.4 and step
    G7). A piece listed in a building floor's m_aCachedActors hides with that floor and cuts down with it; a copy is in
    no list, so it would stay drawn (F-31). Each copy in `copies` ([(original, copy) export indices, (location,
    rotation) of the original, of the copy]) whose original is listed gets its original's entry in the building floor
    the copy stands in, as far above it as the original's listing is above the floor the original stands in
    (CutdownFloor moved by as many floors); a copy of a piece listed though it stands in no floor volume (a ladder on
    a building's outer wall), standing in none either, keeps its original's listing; any other copy standing in no
    building floor
    gets none. (The floor is the one whose floor volumes overlap the copy's box most: floor_at.) The copy keeps its original's floor component and cutout flag (cloned with it). Hidden originals stay
    listed (dormant, F-58). `replaced`: the map's buildings the Build edits in place ({building export: its new floors'
    boxes [[x0, y0, z0, x1, y1, z1]] per floor, or None for a deleted one}; buildings.edit): a copy standing in one is
    left to that edit, which lists it by the carried rule, and the copy's floor is found with their new boxes.
    Returns the manifest's section: [{copy, building, floor} or {copy, outside: true} or {copy, building, edited:
    true}]."""
    walker = Walker(p, g)
    buildings = building_floors(walker, g, p)
    replaced = replaced or {}
    after_floors = {i: (b, field, floors) for i, (b, field, floors) in buildings.items() if i not in replaced}
    for i, new in replaced.items():
        if new is not None and i in buildings:
            after_floors[i] = (None, None, [dict(volumes=[dict(min=x[:3], max=x[3:]) for x in boxes]) for boxes in new])
    lists = {i: [[x['raw'] for x in floor['entries']] for floor in floors] for i, (_, _, floors) in buildings.items()}
    out, changed = [], set()
    for original, copy, before, after in copies:
        listings = [(i, k, x) for i, (_, _, floors) in buildings.items() for k, floor in enumerate(floors)
                    for x in floor['entries'] if x['actor'] == original]
        if not listings:
            continue
        box = piece_box(p, original, before[0], before[1])
        there = floor_at(after_floors, moved_box(box, before, after))
        name = p.name(original).split('.')[-1]
        if there is not None and there[0] in replaced:
            out.append(dict(copy=name, building=p.name(there[0]).split('.')[-1], edited=True))
            continue
        here = floor_at(buildings, box)
        # listed though it stands in no floor volume (a ladder on a shed's outer wall, CSmallScout_Farm), and the copy
        # outside them too: it keeps its original's listing
        kept = there is None and here is None
        placed = copy_floors([(i, k, 0) for i, k, _ in listings], here, there, lambda b: len(after_floors[b][2]))
        if not placed:
            out.append(dict(copy=name, outside=True))
            continue
        for n, b, floor, _ in placed:
            _, k, entry = listings[n]
            lists[b][floor].append(entry_for(entry, copy, floors=floor - k))
            changed.add(b)
            out.append(dict(copy=name, building=p.name(b).split('.')[-1], floor=floor, **({'kept': True} if kept else {})))
    for i in changed:
        b, field, floors = buildings[i]
        parts = [with_array(g, b, f['element'], f['field'], 'm_aCachedActors', new) for f, new in zip(floors, lists[i])]
        g.relocate(i, rebuilt(b, field, parts))
    return out


def list_made_walls(g, p, walls, replaced=None):
    """Walls made from numbers (frac_walls.add_walls' records) in the cutaway of the map's own buildings they stand in
    (custom geometry plan, M3 item 7): each is listed in every floor the game editor's rule gives for its own box
    (buildings.rule: the floors whose volumes it touches, with their CutdownFloor), as a piece placed there in the
    game's editor would be; a two-storey wall lands in both floors' lists. A copy's original's listing (edit_floor_caches)
    is no guide here: the donor is another shape, often of another map. Buildings the Build edits in place (`replaced`)
    and buildings made from nothing list them by the same rule themselves. Returns the manifest's section: [dict(wall,
    building, floors: [[floor, CutdownFloor]])]."""
    import buildings as building_tools
    # (ground shapes too, M6: their donor is a ground plane, in no building)
    walls = [w for w in walls if w.get('kind') in ('fracWall', 'fracSlab', 'ground')]
    if not walls:
        return []
    walker = Walker(p, g)
    found = building_floors(walker, g, p)
    replaced = replaced or {}
    shape = building_tools.building_template(p, walker)
    out, changed = [], {}
    for i, (b, field, floors) in found.items():
        if i in replaced:
            continue
        boxes = [[list(x['min']) + list(x['max']) for x in f['volumes']] for f in floors]
        lists = None
        for w in walls:
            listed = building_tools.rule(p, w['original'], w['box'], boxes)
            if not listed:
                continue
            if lists is None:
                lists = [[x['raw'] for x in f['entries']] for f in floors]
            for k, cut in listed:
                lists[k].append(building_tools.rule_entry(shape, floors, w['copy'], cut))
            out.append(dict(wall=w['copy'], building=i, floors=[[k, cut] for k, cut in listed]))
        if lists is not None:
            changed[i] = lists
    for i, lists in changed.items():
        b, field, floors = found[i]
        parts = [with_array(g, b, f['element'], f['field'], 'm_aCachedActors', new) for f, new in zip(floors, lists)]
        g.relocate(i, rebuilt(b, field, parts))
    return out


def building_lists(p, i):
    """A building volume's (export index) residents (every Floors(k).m_aCachedActors(j).ResidentActor) and floor
    volumes (Floors(k).FloorVolumes), as (set, list) of export indices."""
    residents, volumes = set(), []
    for floor in p.structs(p.own(i, 'Floors')):
        cached = floor.get(('m_aCachedActors', 0), {}).get('value')
        residents |= {e[('ResidentActor', 0)]['value'] for e in p.structs(cached)} if cached else set()
        listed = floor.get(('FloorVolumes', 0), {}).get('value')
        volumes += [v for v in (p.refs(listed) if listed else []) if v > 0]
    return residents, volumes


def van_buildings(p, pieces):
    """The vans' own buildings among `pieces` (export indices; private/plans/done/cars-doors-ladders-plan.md, 2.3 and 7.6): each
    of the level's XComBuildingVolumes more than half of whose listed residents are among them, as the compiler tells a
    van from a car: [dict(building, volumes: its floor volumes, residents)]. A van's building lists its parts on floor 0
    (its cargo floor) and its roof on floor 1, and whatever else stands in its floor volumes (on Bar, a skid mark and
    litter under the delivery van)."""
    level = p.by_name['TheWorld.PersistentLevel']
    pieces, out = set(pieces), []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'XComBuildingVolume' or p.exports[i - 1]['outer'] != level:
            continue
        residents, volumes = building_lists(p, i)
        if piece_flags.van_building(residents, pieces):
            out.append(dict(building=i, volumes=volumes, residents=sorted(residents)))
    return out


def moved_pose(location, rotation, before, after):
    """The pose (location, rotation) of a piece at `location`, `rotation` carried as another is carried from the pose
    `before` to `after` ((location, rotation) each): a van's volumes go with its parts, a quarter turn turning them."""
    import numpy as np
    from export_math import transform
    m = np.array(transform(after[0], after[1], [1, 1, 1]), float) @ np.linalg.inv(
        np.array(transform(before[0], before[1], [1, 1, 1]), float))
    at = m @ np.array([*location, 1.0])
    return [float(v) for v in at[:3]], [int(r) + int(a) - int(b) for r, a, b in zip(rotation, after[1], before[1])]


def edit_van_building(g, p, original, copy, own):
    """A van's copied building (`copy`, the clone of `original`, export indices; private/plans/done/cars-doors-ladders-plan.md,
    7.6): each floor's m_aCachedActors keeps the residents among `own` (the assembly's clones, which clone_assembly
    points it at) and drops the rest (pieces under the original van, which stay where they stand), and
    VisGroupIdxToHideWhenOccluding is emptied (visibility groups of the original's place). Its floor volumes and
    ExternalMeshGroups already point at the clones. Returns dict(dropped: the residents dropped, outside: actors of its
    ExternalMeshGroups outside the assembly, kept as they are)."""
    walker = Walker(p, g)
    e = p.exports[original - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    b = g.export_data(copy)
    dropped = []
    found = find_prop(walker, b, start, len(b), 'Floors[0]')
    if found is not None:
        pieces = []
        for element in struct_elements(walker, b, found[2], found[3]):
            field = find_prop(walker, b, element[0], element[1], 'm_aCachedActors[0]')
            entries = struct_entries(walker, b, field, 'ResidentActor')
            dropped += [p.name(x['actor']).split('.')[-1] for x in entries if x['actor'] not in own]
            pieces.append(with_array(g, b, element, field, 'm_aCachedActors',
                                     [x['raw'] for x in entries if x['actor'] in own]))
        b = rebuilt(b, found, pieces)
    vis = find_prop(walker, b, start, len(b), 'VisGroupIdxToHideWhenOccluding[0]')
    if vis is not None:
        _, tag, at, size = vis
        out = bytearray(b[:at]) + struct.pack('<i', 0) + bytes(b[at + size:])
        struct.pack_into('<i', out, tag + 16, 4)
        b = bytes(out)
    outside = []
    groups = find_prop(walker, b, start, len(b), 'ExternalMeshGroups[0]')
    for s_, e_ in struct_elements(walker, b, groups[2], groups[3]) if groups else []:
        listed = find_prop(walker, b, s_, e_, 'm_aActors[0]')
        if listed:
            n = struct.unpack_from('<i', b, listed[2])[0]
            outside += [p.name(v).split('.')[-1] for v in struct.unpack_from(f'<{n}i', b, listed[2] + 4) if v not in own]
    g.relocate(copy, bytes(b))
    return dict(dropped=dropped, outside=outside)


def hide_van_buildings(g, p, gone, edited=()):
    """The buildings of vans moved or deleted (`gone`: the hidden pieces, export indices) taken out of the map with their
    floor volumes, as hide_pieces takes pieces out (empty slots in the Level's actor list): van_buildings' rule. The
    parts' hides rebuild the tiles. `edited`: the map's buildings the Build edits in place (buildings.edit), never a
    van's though all their pieces moved. Returns [{building, volumes}] (names)."""
    out, slots = [], set()
    for van in van_buildings(p, gone):
        if van['building'] in edited:
            continue
        slots |= {van['building'], *van['volumes']}
        out.append(dict(building=p.name(van['building']).split('.')[-1],
                        volumes=[p.name(v).split('.')[-1] for v in van['volumes']]))
    if slots:
        empty_slots(g, p, slots)
    return out


def add_to_level(g, p, actors, *, before_rebuild=()):
    """Append actors and place any priority volumes before the first existing rebuild volume. A rebuild volume made
    as several (add_rebuild_volume's `fitted`) is listed with the others right after it."""
    more = getattr(g, 'rebuild_more', {})
    actors = [b for a in actors for b in [a] + more.get(a, [])]
    before_rebuild = [b for a in before_rebuild for b in [a] + more.get(a, [])]
    data = bytearray(g.export_data(p.by_name['TheWorld.PersistentLevel']))
    level, at, listed = actor_list(p, data)
    count = len(listed)
    tail = at + 8 + 4 * count
    original = tuple(listed)
    where = next((k for k, a in enumerate(original) if a > 0 and p.cls(a) == 'XComRebuildWorldDataVolume'),
                 count) if before_rebuild else count
    after = original[:where] + tuple(before_rebuild) + original[where:] + tuple(actors)
    struct.pack_into('<i', data, at + 4, len(after))
    data[at + 8:tail] = struct.pack(f'<{len(after)}i', *after)
    g.relocate(level, bytes(data))
    return dict(level=level, actorsBefore=count, actorsAfter=len(after))


# ---------------------------------------------------------------- pieces' flags (piece flags plan, P5)
# More separate tile regions than this for the map's own pieces whose flags change, and one rebuild volume covers
# them all (their seeds stay each piece's own)
FLAG_REGIONS = 48


def props_end(walker, data, start):
    """Where an export's tagged properties end (after their closing None)."""
    gen = walker.walk(bytes(data), start, len(data))
    try:
        while True:
            next(gen)
    except StopIteration as done:
        return done.value


def set_struct_bool(walker, g, data, start, outer, struct_name, field, value):
    """(data, how) with the bool `field` of the struct property `outer` (of struct `struct_name`, saved as tagged
    fields) set to `value`, its other fields left as they are: the field changed in place ('changed'), added to the
    struct the export saves ('field added': the struct's tag grows by it), or, where the export saves no such struct,
    a struct of that one field added ('struct added'): the game loads a struct field by field over the actor's
    archetype, so the fields it doesn't save keep what the archetype or the class gives them (as cover_blocks' low
    cover saves VisibilityBlockingData)."""
    import native_lights
    raw = b'\x01' if value else b'\x00'
    for prop, kind, sub, at, size in walker.walk(bytes(data), start, len(data)):
        if prop != f'{outer}[0]':
            continue
        if kind != 'StructProperty' or sub != struct_name:
            raise ValueError(f'{outer} is saved as a {kind} {sub}, not a StructProperty {struct_name}')
        if not walker.looks_tagged(bytes(data), at, at + size):
            raise ValueError(f'{outer} is not saved as tagged fields')
        had = native_lights.saves(walker, data[:at + size], at, field)
        before = len(data)
        data = native_lights.set_property(walker, g, data, at, field, 'BoolProperty', None, raw)
        grown = len(data) - before
        if grown:
            struct.pack_into('<i', data, at - 16, size + grown)
        return data, 'changed' if had else 'field added'
    body = (struct.pack('<iiiiii', g.name(field), 0, g.name('BoolProperty'), 0, 0, 0) + raw
            + struct.pack('<ii', g.name('None'), 0))
    data = native_lights.set_property(walker, g, data, start, outer, 'StructProperty', struct_name, body)
    return data, 'struct added'


def set_roles(g, p, source, index, request, known=None, label=None, made=None):
    """A piece's flags (piece flags plan, 3.2) written on the export `index` of the map being built: the source actor
    `source` (the same export for a piece of the map left where it stands, the original for a copy) has its settings
    resolved from the package (piece_flags.resolve: the actor, its archetypes in the map, the class default), with
    `known` ({property: value}) the writes this build has made on it already (make_walkable's bPathColliding), and
    the request {role: bool} planned against them (piece_flags.plan). Each planned write goes on the actor itself:
    a bool in place or added, VisibilityBlockingData's field patched in its struct (set_struct_bool); nothing on an
    archetype or a component, and the bytes after the properties (the actor's native tail) stay as they were. A
    request that a prop's gate makes ambiguous here is refused (nothing written). made: the generated kind of a piece
    made from numbers, planned on what the Build makes of its donor (piece_flags.made_settings: a ground shape's
    class, retyped later by frac_walls, and ground_collision's writes). Returns the manifest's record."""
    import native_lights
    import piece_flags
    r = piece_flags.resolve(p, source)
    cls, raw, sources = piece_flags.made_settings(r['cls'], r['raw'], r['source'], made) if made else \
        (r['cls'], dict(r['raw']), dict(r['source']))
    for k, v in (known or {}).items():
        if k in raw:
            raw[k], sources[k] = v, 'build'
    assumed = sorted(k for k, v in sources.items() if v == 'assumed')
    plan = piece_flags.plan(cls, raw, request, assumed)
    rec = dict(actor=p.name(source).split('.')[-1], label=label, export=index, actorClass=cls, requested=dict(request),
               applied={k: v for k, v in request.items() if k not in plan['unsupported']},
               before=plan['before'], after=plan['after'], companions=list(plan['companions']),
               settings={k: [raw[k], sources[k]] for k in raw}, assumed=assumed, written=[], tiles=False)
    if plan['unsupported']:
        rec['unsupported'] = dict(plan['unsupported'])
    if plan['unmet']:
        rec['unmet'] = dict(plan['unmet'])
    if plan['conflicts']:
        rec.update(refused=dict(plan['conflicts']), applied={}, after=plan['before'])
        return rec
    if not plan['writes']:
        return rec
    walker = Walker(p, g)
    data = bytearray(g.export_data(index))
    start = native_lights.props_start(p, source)
    tail = bytes(data[props_end(walker, data, start):])
    for prop, value in plan['writes']:
        if prop in piece_flags.STRUCT_FIELDS:
            outer, struct_name = piece_flags.STRUCT_FIELDS[prop]
            data, how = set_struct_bool(walker, g, data, start, outer, struct_name, prop, value)
        else:
            how = 'changed' if native_lights.saves(walker, data, start, prop) else 'added'
            data = native_lights.set_property(walker, g, data, start, prop, 'BoolProperty', None,
                                              b'\x01' if value else b'\x00')
        rec['written'].append([prop, bool(value), how])
    if bytes(data[props_end(walker, data, start):]) != tail:
        raise ValueError(f"{rec['actor']}'s flags: writing them changed the actor's native data")
    g.relocate(index, bytes(data))
    rec['tiles'] = bool(plan['tiles'])
    return rec


def verify_roles(q, rec):
    """A flags record (set_roles) read back from the written map `q` with a fresh reader: every property written is
    saved by the actor with its value, and each role asked for and each companion is in the state planned. Raises
    ValueError where not: the edit is not in the map, and the build must not say it is."""
    import piece_flags
    if not rec['written']:
        return
    r = piece_flags.resolve(q, rec['export'])
    for prop, value, _ in rec['written']:
        if r['source'].get(prop) != 'actor' or r['raw'].get(prop) is not value:
            raise ValueError(f"{rec['actor']}'s flags: {prop} reads back as {r['raw'].get(prop)!r} "
                             f"({r['source'].get(prop)}), not {value!r} on the actor")
    now = piece_flags.states(rec['actorClass'], r['raw'])
    for role in list(rec['applied']) + rec['companions']:
        if now[role] != rec['after'][role]:
            raise ValueError(f"{rec['actor']}'s flags: {role} reads back {now[role]}, not {rec['after'][role]}")
    rec['readBack'] = True


def merge_ranges(ranges):
    """Tile ranges (x0, x1, y0, y1, z0, z1) merged where they overlap or touch in x and y (each region's volume
    reaches down to the ground, so the levels just join)."""
    out = [list(t) for t in ranges]
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                if a[0] <= b[1] + 1 and b[0] <= a[1] + 1 and a[2] <= b[3] + 1 and b[2] <= a[3] + 1:
                    out[i] = [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]),
                              min(a[4], b[4]), max(a[5], b[5])]
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return [tuple(t) for t in sorted(out)]


def flag_tiles(g, p, boxes, volumes=True, max_regions=FLAG_REGIONS):
    """The tiles of the map's own pieces whose flags change where they stand (`boxes`: [(name, world box)]): each
    piece's tiles seeded as a copy's are (seed_tiles_under: its box, the ring round it and the level over it, where
    the bake left no mark), and a rebuild volume over each region those tiles make (merge_ranges), from the ground up,
    or one over them all past `max_regions`; none with `volumes` False (a cleared map's own volume covers the grid).
    Returns (the manifest's record, the volumes' exports)."""
    grid = level_grid(p)
    ranges, seeded, already, outside = [], 0, 0, []
    changed = []
    for name, box in boxes:
        s = seed_tiles_under(g, p, box, grid)
        if s['tiles'] is None:
            outside.append(name)
            continue
        changed.append(box)
        ranges.append(tuple(s['tiles']))
        seeded += len(s['seeded'])
        already += s['already']
    regions = merge_ranges(ranges)
    joined = len(regions) > max_regions
    if joined:
        regions = [tuple(f(t[k] for t in regions) for k in range(6) for f in [(min, max)[k % 2]])]
    made, listed = [], []
    for t in regions:
        v = None
        if volumes:
            x0, x1, y0, y1, _, z1 = seed_map.world_of(t, grid)
            v = add_rebuild_volume(g, p, [x0, x1, y0, y1, grid['oz'] - seed_map.REBUILD_PAD, z1], changed=changed)
            made.append(v['export'])
        listed.append(dict(tiles=list(t), **({'volume': v['export']} if v else {})))
    record = dict(regions=listed, seeded=seeded, alreadyMarked=already, outside=outside, joined=joined,
                  volumes='own' if volumes else "the cleared map's", bounds='drawn')
    return record, made


def break_component(g, p, actor, mapping, blasts, label=None, breaks_further=False):
    """The fracturing piece `actor` of the map (its component cloned as `mapping` says, or itself) broken by `blasts`
    (custom geometry editing plan, E6; made_blasts): the fragments they reach saved painted out on its component with
    those its map paints out. A piece whose component keeps its fragments (bPreventChunkRemoval: most roofs and
    floors) draws them all whatever is painted out (F-138): it stays whole in battle, as the game keeps it, its
    component drawing a copy of its mesh with every fragment out cut away (frac_walls.cut_copy, F-139); with
    `breaks_further` the setting is turned off instead and it breaks further, as a wall does. Returns its record:
    label, fragments, knocked (those newly out), hidden (all out), chunksLet or keptWhole (the cut mesh's name)."""
    import frac_walls
    import gen_mesh
    import made_blasts
    comp = p.own(actor, 'FracturedStaticMeshComponent')
    if not comp:
        raise ValueError('%s is no fracturing piece: only one breaks' % (label or p.name(actor)))
    mesh = gen_mesh.read(p, p.effective(comp, 'StaticMesh'))
    frags = mesh['fractured']['fragments']
    shown = made_blasts.shown_of(p.effective(comp, 'EditorPaintedVisibleFragments'), len(frags))
    hit = made_blasts.hidden_at(made_blasts.fragment_centres(mesh['lods'][0], len(frags)), blasts)
    before = {i for i, s in enumerate(shown) if not s}
    out = sorted(before | set(hit))
    e = p.exports[comp - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    target = mapping.get(comp, comp) if mapping else comp
    walker = Walker(p, g)
    data = frac_walls.painted_arrays(g, walker, g.export_data(target), start, made_blasts.visible_value(len(frags), out),
                                     made_blasts.chunks_of_bounds(frags, out))
    # a piece that keeps its fragments: kept whole, its hole cut into its own mesh (F-139), or, asked to break further,
    # let go of them (F-138)
    keeps = frac_walls.keeps_chunks(p, comp) and bool(out)
    whole = None
    if keeps and not breaks_further:
        whole = frac_walls.cut_copy(g, p, p.effective(comp, 'StaticMesh'), out)
        data = frac_walls.use_mesh(g, walker, data, start, whole['export'], whole['mesh'])
    elif keeps:
        data = frac_walls.allow_chunk_removal(g, walker, data, start)
    g.relocate(target, data)
    return dict(label=label or p.name(actor).split('.')[-1], fragments=len(frags), knocked=len(set(hit) - before),
                hidden=len(out), **({'keptWhole': whole['name']} if whole else {'chunksLet': True} if keeps else {}))


def blasts_in_place(g, p, pieces, gone=(), tiles=True, volumes=True):
    """The map's own fracturing pieces broken where they stand (the compiler's `pieceBlasts`: name, blasts; E6): each
    one's component written by break_component, and its tiles worked out again as a flag change's are (flag_tiles). A
    piece the edit takes out of the level, or that the map hasn't, is an error. Returns (record, the volumes made)."""
    level = p.by_name['TheWorld.PersistentLevel']
    gone = set(gone)
    records, boxes = [], []
    for e in pieces:
        index = p.by_name.get(PL + e['name'])
        if index is None or p.exports[index - 1]['outer'] != level:
            raise ValueError(f"{e['name']}'s blasts: the map has no such actor in its persistent level")
        if index in gone:
            raise ValueError(f"{e['name']}'s blasts: the edit takes the piece out of the level")
        records.append(break_component(g, p, index, None, e['blasts'], label=e['name'],
                                       breaks_further=bool(e.get('breaksFurther'))))
        if tiles and has_mesh(p, index):
            boxes.append((e['name'], piece_box(p, index, p.own(index, 'Location', [0.0, 0.0, 0.0]),
                                               p.own(index, 'Rotation', [0, 0, 0]))))
    tile_record, made = flag_tiles(g, p, boxes, volumes) if boxes else (None, [])
    return dict(pieces=records, tiles=tile_record), made


def flags_in_place(g, p, pieces, ladders=(), gone=(), tiles=True, volumes=True):
    """The map's own pieces whose flags change where they stand (the compiler's `pieceFlags`: name, flags): each
    written on the actor (set_roles), after the copies are made from the map's pieces, so a copy never takes a flag
    meant for its original. A piece whose tile flags change gets its tiles worked out again (flag_tiles); the mouse
    alone, or a request that writes nothing, needs no tile work. A map ladder whose foot or top tile such a change
    reaches (the compiler's `ladders`: actor, foot, top) gets its top tile rebuilt first and its foot after, as a
    moved ladder's are. A piece the edit takes out of the level, or that the map hasn't, is an error. Returns (record,
    the volumes to add after the copies', the volumes to rebuild first, the ladders for ladder_order)."""
    level = p.by_name['TheWorld.PersistentLevel']
    gone = set(gone)
    records, boxes = [], []
    for e in pieces:
        index = p.by_name.get(PL + e['name'])
        if index is None or p.exports[index - 1]['outer'] != level:
            raise ValueError(f"{e['name']}'s flags: the map has no such actor in its persistent level")
        if index in gone:
            raise ValueError(f"{e['name']}'s flags: the edit takes the piece out of the level")
        rec = set_roles(g, p, index, index, e['flags'], label=e['name'])
        records.append(rec)
        if not (rec['tiles'] and tiles):
            continue
        if not has_mesh(p, index):
            rec['tileWork'] = 'none: the piece has no mesh to box'
            continue
        boxes.append((e['name'], piece_box(p, index, p.own(index, 'Location', [0.0, 0.0, 0.0]),
                                           p.own(index, 'Rotation', [0, 0, 0]))))
    tile_record, volumes_made = flag_tiles(g, p, boxes, volumes) if boxes else (None, [])
    firsts, after, ladder_records = [], [], []
    for l in ladders if boxes else ():
        index = p.by_name.get(PL + l['actor'])
        if index is None or index in gone:
            continue
        top, foot = tile_volume(g, p, l['top']), tile_volume(g, p, l['foot'])
        firsts.append(top['export'])
        after.append(foot['export'])
        ladder_records.append(dict(actor=l['actor'], export=index, foot=list(l['foot']), top=list(l['top']),
                                   topVolume=top, footVolume=foot['export'], inPlace=True))
    return dict(pieces=records, tiles=tile_record), volumes_made + after, firsts, ladder_records


def flags_summary(rec):
    """One line of a flags record (set_roles) for the log."""
    words = ', '.join(f"{k} {'on' if v else 'off'}" for k, v in rec['applied'].items()) or 'nothing'
    if rec.get('refused'):
        return f"{rec['actor']}: flags refused ({'; '.join(rec['refused'].values())})"
    wrote = ', '.join(f"{p}={'true' if v else 'false'} ({how})" for p, v, how in rec['written']) or 'no write needed'
    return (f"{rec['actor']}: {words}: {wrote}" + (f"; companions {', '.join(rec['companions'])}" if rec['companions'] else '')
            + (f"; not a setting of it: {', '.join(rec['unsupported'])}" if rec.get('unsupported') else ''))


def by_assembly(copies):
    """The copies in their order, as [(assembly id or None, [copies])]: the copies of one assembly together, at the
    place of its first; every other copy alone."""
    out, where = [], {}
    for c in copies:
        a = c.get('assembly')
        if not a:
            out.append((None, [c]))
        elif a in where:
            out[where[a]][1].append(c)
        else:
            where[a] = len(out)
            out.append((a, [c]))
    return out


def filled(factory=None):
    """A field of BuildState that build fills, not an input: None, or empty (`factory`), until its step."""
    return dataclasses.field(init=False, **({'default_factory': factory} if factory else {'default': None}))


@dataclasses.dataclass(eq=False)
class BuildState:
    """A Build of the copy tool: what it is given, and what it has done so far that its later steps and its record
    read (review finding 51). Its caller makes it with the inputs (main from the command line and the native edit, a
    test with its own); build() takes it and fills the rest. build's docstring says what each input does.

    gone() is the one answer to what the edit has taken out: the pieces hidden, the slots the building edits emptied,
    the lights the light edits deleted, the effects, sounds, flares and spawn points the lanes took out (and the
    carried effects of deleted pieces), and what the clear took. The manifest (manifest_parts) and the relight
    command (relight_command) are made from its fields once build has filled them."""
    src: object                     # the pristine map (its path)
    out: object                     # the folder the variant map and its fixture manifest go to
    variant: str                    # the variant's name
    copies: list                    # the copies: the native edit's `copies`
    bake: bool = False              # the copies lit of their own and the relight run (--bake)
    cache: object = None            # with bake: the variant texture cache's name (--cache)
    receivers_near: float = 600.0   # with bake: the relight's receivers within this many units of a copy
    jobs: object = None             # with bake: the relight's worker processes
    tiles: bool = True              # the copies seeded in the tiles, under rebuild volumes (not --no-tiles)
    edit_spec: object = None        # with bake: an editor patch spec whose hides the relight models too
    # the native edit's other lanes (compiler.native_split's keys, in the names build takes them by)
    break_originals: tuple = ()     # breakOriginals
    hides: tuple = ()               # hides
    assemblies: tuple = ()          # assemblies
    lights: object = None           # lights
    covers: tuple = ()              # covers
    buildings: tuple = ()           # buildings
    building_edits: tuple = ()      # buildingEdits
    cleared: object = None          # cleared
    landing_zones: object = None    # landingZones
    carried_effects: object = None  # carriedEffects
    piece_cache: object = None      # with bake: the folder of the project's last baked pieces (--piece-cache)
    base: object = None             # with piece_cache: the SHA-256 of the map before any of the edit (--base)
    stream_tiles: tuple = ()        # streamTiles (the Build's, from streamMoves)
    piece_flags: tuple = ()         # pieceFlags
    flag_ladders: tuple = ()        # pieceFlagLadders
    effects: object = None          # effects
    sounds: object = None           # sounds
    flares: object = None           # flares
    spawns: object = None           # spawns
    background_sound: object = None     # backgroundSound
    piece_blasts: tuple = ()        # pieceBlasts
    diagonal_cover: object = None   # diagonalCover (the project's diagonal cover marks, diagonal_edit)
    # what build fills, as it goes
    p: object = filled()                # the pristine map read (build, first)
    g: object = filled()                # the variant map's growing writer (build, first)
    light_state: object = filled()      # the light edits resolved against the pristine map, or None (build)
    hidden: list = filled(list)         # hide_pieces' records
    edit_slots: set = filled(set)       # the building edits' emptied slots
    lights_gone: set = filled(set)      # the light edits' deletes
    effects_gone: set = filled(set)     # the lanes' deletes (effects, sounds, flares, spawns), the carried effects'
    cleared_record: object = filled()   # clear_level's record
    # the copies made (clone_copies)
    made: list = filled(list)           # each copy's record: its original, clone, pose, extra lights and tiles
    actors: list = filled(list)         # what the level's list gets: the clones, their volumes (and the cover blocks)
    firsts: list = filled(list)         # the ladders' top tile volumes, first in the level's list
    ladders: list = filled(list)        # each ladder's copy: its ends and top tile volume
    vans: list = filled(list)           # each van's building and floor volumes, carried with it
    flag_copies: list = filled(list)    # the copies' flags written on their clones (set_roles)
    blast_copies: list = filled(list)   # the copies broken by their blasts (break_component)
    # the fracturing copies and the walls made from numbers (fracturing_copies)
    poses: list = filled(list)          # each copy's (original, clone, its pose before, after, family)
    fracturing: list = filled(list)     # the fracturing copies, as (original, clone), their columns moved with them
    generated_records: list = filled(list)  # the pieces made from numbers (frac_walls.add_walls' records)
    # the walls' columns (wall_columns), and what it reads that build made
    walled: set = filled(set)           # the break groups that hold a wall made from numbers
    cover_records: list = filled(list)  # the cover blocks made (cover_blocks.add_blocks' records)
    columns: dict = filled(dict)        # each wall's columns changed by the hides and the door copies (edit_columns)
    door_listings: list = filled(list)  # doors in a made wall's opening, listed in its columns
    group_listings: list = filled(list)     # a made wall's break group's pieces, listed in its columns
    neighbour_listings: list = filled(list)     # made walls and the fracturing pieces they meet, listing each other
    # the building floors (edit_buildings)
    floor_caches: list = filled(list)   # each copy in its building floor's cutaway (edit_floor_caches)
    made_floors: list = filled(list)    # the made walls in the map's buildings' cutaways (list_made_walls)
    building_actors: list = filled(list)    # the buildings' new volumes, for the level's list
    building_records: list = filled(list)   # the buildings made from nothing (buildings.make)
    edit_records: list = filled(list)   # the map's own buildings edited (buildings.edit)
    # the map's own actors edited in place (edits_in_place), and what it reads that build made
    light_result: object = filled()     # what the light edits made in the map (native_lights.apply), or None (build)
    hide_volumes: list = filled(list)   # the rebuild volumes of the pieces taken out, the clear's and the tiles' edits
    effect_moved: set = filled(set)     # the effects moved (carried or by a lane), which a clear keeps
    registration: object = filled()     # the light edits listed in the receivers' lightmaps (baked), or None
    landing_record: object = filled()   # the map's landings moved (native_spawns.apply), or None
    sound_record: object = filled()     # the map's background sound written (native_sounds.background), or None
    flag_record: object = filled()      # the map's own pieces' flags written (flags_in_place), or None
    blast_record: object = filled()     # the map's own pieces broken where they stand (blasts_in_place), or None
    stream_record: list = filled(list)  # a mission's pieces' tiles moved in their stream
    priority: tuple = filled(tuple)     # the ladders' top tile volumes the rebuild queues first, on a resized map
    # the floors' effect lists and the cursor floors (floors_and_cursors), and what it reads that build made
    effect_record: list = filled(list)  # the effects carried with the moved, copied and deleted pieces
    lane_effects: list = filled(list)   # the effects lane's records (native_effects.apply)
    floor_emitters: list = filled(list)     # the effects listed in, or taken out of, the building floors' lists
    cursor_record: object = filled()    # the made slabs' cursor floors (made_cursors.apply), or None
    cursor_clones: list = filled(list)  # the cursor volumes made, for the level's list
    # the map written and read back (write_and_verify), and what it reads that build made
    effect_clones: list = filled(list)  # the effects, sounds, flares and spawn points copied, for the level's list
    lane_sounds: list = filled(list)    # the sounds lane's records (native_sounds.apply)
    lane_flares: list = filled(list)    # the flares lane's records (native_flares.apply)
    lane_spawns: list = filled(list)    # the spawns lane's records (native_spawns.apply_lane)
    level: object = filled()            # the level's actor list written (add_to_level)
    dst: object = filled()              # the map written: <out>/<variant>.upk, or the grown map in <out>/grown
    report: object = filled()           # the growing writer's report of the write
    q: object = filled()                # the written map, read again
    diagonal: object = filled()         # the diagonal cover tiles next to a change, written (diagonal_keep.write)
    start_tiles: object = filled()      # the tiles near the changes written as the rebuild leaves them (start_tiles)
    forgot: object = filled()           # the tiles' references to actors taken out of the level, cleared (F-156)
    # what build makes between its steps
    groups: dict = filled(dict)         # the break groups linked (link_children): each group's clones
    children: dict = filled(dict)       # each clone's parts linked to it (link_children)
    hidden_buildings: list = filled(list)   # the moved or deleted vans' buildings taken out (hide_van_buildings)
    # the record (manifest_parts)
    sections: list = filled(list)       # the manifest's section of each copy
    copy_members: dict = filled(dict)   # the lights listed in the copies' lightmaps by membership

    def gone(self):
        """Every actor (export index) the edit has taken out so far."""
        out = {h['export'] for h in self.hidden} | self.edit_slots | self.lights_gone | set(self.effects_gone)
        if self.cleared_record:
            out |= {self.p.by_name[PL + n] for n in self.cleared_record['taken'] if PL + n in self.p.by_name}
        return out


def manifest_parts(st, q, bake):
    """The manifest's nativeCopies section of the Build `st` (BuildState, its results kept) whose map was written and
    read again as `q`: (the copies' sections, the rest of it, the lights section or None). Kept on `st` too, for the
    relight command: the sections and the lights listed in the copies by membership."""
    import native_lights
    p, made, hidden, cleared_record = st.p, st.made, st.hidden, st.cleared_record
    src, level, report, children, groups = st.src, st.level, st.report, st.children, st.groups
    assemblies, ladders, columns, effect_record = st.assemblies, st.ladders, st.columns, st.effect_record
    lane_effects, lane_sounds = st.lane_effects, st.lane_sounds
    lane_flares, lane_spawns = st.lane_flares, st.lane_spawns
    floor_emitters, floor_caches, hidden_buildings = st.floor_emitters, st.floor_caches, st.hidden_buildings
    building_records, edit_records, cover_records = st.building_records, st.edit_records, st.cover_records
    generated_records, door_listings, group_listings = st.generated_records, st.door_listings, st.group_listings
    made_floors, neighbour_listings, landing_record = st.made_floors, st.neighbour_listings, st.landing_record
    cursor_record, stream_record = st.cursor_record, st.stream_record
    flag_copies, flag_record = st.flag_copies, st.flag_record
    blast_copies, blast_record, vans = st.blast_copies, st.blast_record, st.vans
    state, light_result, registration = st.light_state, st.light_result, st.registration
    # the copies' components and the lights listed in them by membership
    copy_members = {q.name(m['info']['mapping'][ci]): [(x['guid'].hex(), x['light']) for x in found
                                                        if x.get('membership')]
                    for m in made for ci, found in m['extra'].items()}
    copy_members = {k: v for k, v in copy_members.items() if v}
    sections = []
    for m in made:
        info, new = m['info'], m['info']['actor']
        sections.append(dict(actor=m['actor'], label=m.get('label'), copy=q.name(new), export=new, location=m['location'],
                             rotation=m['rotation'], exports={p.name(o): n for o, n in info['mapping'].items()},
                             textures={p.name(o): q.name(n) for o, n in info['textures'].items()},
                             extraLights={p.name(ci): [dict(light=x['light'], peak=x['peak'], kept=x['kept'],
                                                            **({'membership': True} if x.get('membership') else {}))
                                                       for x in found] for ci, found in m['extra'].items()},
                             remapped=info['remapped'], tiles=m['tiles'], breakGroup=m['breakGroup'],
                             **({'walkable': 'collision turned on: low scenery of the map (F-100)'} if m['walkable'] else {}),
                             **({'staged': True, 'donor': m['donor'], 'lighting': 'fresh' if bake else 'its home map\'s'}
                                if m['staged'] else {}),
                             **({'columns': info['columns']} if info.get('columns') else {}),
                             **({'generated': m['generated']['kind']} if m.get('generated') else {}),
                             parts=children[new],
                             **({'assembly': m['assembly'], 'family': m['family']} if m.get('assembly') else {})))
    tool = dict(path='tools/bake/native_copy.py', sha256=lighting.digest(__file__))
    lights_record = None
    if state:
        lights_record = native_lights.record(state, light_result, 'baked' if bake else 'unbaked', registration,
                                             copy_members, names=q.name)
        lights_record['tool'] = dict(path='tools/bake/native_lights.py', sha256=lighting.digest(native_lights.__file__))
    common = dict(level=level, writer=report, source=str(src), sourceSha256=lighting.digest(src), tool=tool,
                  breakGroups={str(k): [q.name(i).split('.')[-1] for i in v] for k, v in groups.items()},
                  hidden=hidden, assemblies=list(assemblies), ladders=ladders, columns=columns,
                  carriedEffects=[dict(r, copy=q.name(r['copy']).split('.')[-1]) if 'copy' in r else r
                                  for r in effect_record],
                  **{key: [dict({k: v for k, v in r.items() if k not in ('export', 'mapping', 'template')},
                                **({'copy': q.name(r['export']).split('.')[-1],
                                    'exports': {p.name(o): q.name(n) for o, n in r['mapping'].items()}}
                                   if r['how'] == 'copied' else {}))
                           for r in lane]
                     for key, lane in (('effects', lane_effects), ('sounds', lane_sounds), ('flares', lane_flares),
                                       ('spawns', lane_spawns))
                     if lane},
                  **({'floorEmitters': [dict(effect=q.name(f['effect']).split('.')[-1],
                                             building=q.name(f['building']).split('.')[-1], floor=f['floor'],
                                             how=f['how']) for f in floor_emitters]} if floor_emitters else {}),
                  **({'backgroundSound': st.sound_record} if st.sound_record else {}),
                  floorCaches=floor_caches, hiddenBuildings=hidden_buildings,
                  buildings=[dict(b, copy=q.name(b['building']).split('.')[-1],
                                  floors=[dict(f, volumes=[q.name(v).split('.')[-1] for v in f['volumes']],
                                               members=[dict(m, actor=q.name(m['actor']).split('.')[-1])
                                                        for m in f['members']]) for f in b['floors']])
                             for b in building_records],
                  buildingEdits=[dict(r, **({'volumes': dict(r['volumes'], made=[q.name(v).split('.')[-1] for v in r['volumes']['made']])}
                                            if not r['deleted'] else {}),
                                      **({'floors': [dict(f, volumes=[q.name(v).split('.')[-1] for v in f['volumes']])
                                                     for f in r['floors']]} if not r['deleted'] else {}))
                                 for r in edit_records],
                  coverBlocks=[dict(c, copy=q.name(c['actor'])) for c in cover_records],
                  **({'diagonalCover': st.diagonal} if st.diagonal else {}),
                  **({'startTiles': st.start_tiles} if st.start_tiles else {}),
                  **({'tilesForgot': st.forgot} if st.forgot else {}),
                  **({'generatedWalls': [dict(r, copy=q.name(r['copy']).split('.')[-1],
                                              **({'mesh': q.name(r['mesh'])} if r.get('mesh') else {}))
                                         for r in generated_records]} if generated_records else {}),
                  **({'doorListings': [dict(door=p.name(d['original']).split('.')[-1], copy=q.name(d['door']).split('.')[-1],
                                            wall=q.name(d['wall']).split('.')[-1], columns=d['columns'])
                                       for d in door_listings]} if door_listings else {}),
                  **({'groupListings': [dict(piece=q.name(d['piece']).split('.')[-1], wall=q.name(d['wall']).split('.')[-1],
                                             columns=d['columns']) for d in group_listings]} if group_listings else {}),
                  **({'madeWallFloors': [dict(wall=q.name(d['wall']).split('.')[-1], building=p.name(d['building']).split('.')[-1],
                                              floors=d['floors']) for d in made_floors]} if made_floors else {}),
                  **({'neighbourListings': [dict(wall=q.name(d['wall']).split('.')[-1], other=q.name(d['other']).split('.')[-1],
                                                 lists=d['lists'], listed=d['listed']) for d in neighbour_listings]}
                     if neighbour_listings else {}),
                  **({'cleared': cleared_record} if cleared_record else {}),
                  **({'landings': landing_record} if landing_record else {}),
                  **({'madeCursors': dict(cursor_record, added=[dict({k: v for k, v in a.items() if k != 'export'},
                                                                     copy=q.name(a['export']).split('.')[-1])
                                                                for a in cursor_record['added']])}
                     if cursor_record else {}),
                  **({'streamTiles': stream_record} if stream_record else {}),
                  **({'pieceFlags': dict(
                      onCopies=[dict(r, copy=q.name(r['export']).split('.')[-1]) for r in flag_copies],
                      inPlace=(flag_record or {}).get('pieces') or [], tiles=(flag_record or {}).get('tiles'),
                      written=sum(len(r['written']) for r in flag_copies + ((flag_record or {}).get('pieces') or [])),
                      refused=[r['actor'] for r in flag_copies + ((flag_record or {}).get('pieces') or []) if r.get('refused')])}
                     if flag_copies or flag_record else {}),
                  **({'pieceBlasts': dict(onCopies=blast_copies, inPlace=(blast_record or {}).get('pieces') or [],
                                          tiles=(blast_record or {}).get('tiles'))}
                     if blast_copies or blast_record else {}),
                  vans=[dict(v, building=dict(v['building'], copy=q.name(v['building']['export'])),
                             floorVolumes=[dict(f, copy=q.name(f['export'])) for f in v['floorVolumes']]) for v in vans])
    st.sections, st.copy_members = sections, copy_members
    return sections, common, lights_record


def relight_command(st, dst, out, variant, cache, receivers_near, edit_spec, jobs, piece_cache, base):
    """The relight's command line for the Build `st` (BuildState, its manifest made: manifest_parts) whose grown map is
    `dst`, and the files it names that a command line can't hold: <out>/<variant>.removed-casters.txt and
    <out>/<variant>.light-edits.json."""
    import native_lights
    p, sections, hidden, landing_record = st.p, st.sections, st.hidden, st.landing_record
    state, registration, copy_members = st.light_state, st.registration, st.copy_members
    cmd = [sys.executable, '-B', '-u', str(HERE / 'relight.py'), str(dst), str(out), variant, '--cache', cache,
           '--receivers-near', str(receivers_near)]
    for sec in sections:
        if sec.get('generated'):
            # a generated wall (or its reference beside it): its cloned lightmap holds its donor's bake on another
            # shape, so it is lit from nothing
            cmd += ['--fresh-copy', sec['copy'].split('.')[-1]]
            continue
        cmd += ['--foreign-copy' if sec.get('staged') else '--native-copy',
                f"{sec['copy'].split('.')[-1]}={sec['actor']}"]
    if len(hidden) > CASTER_ARGS:
        # more than a command line holds (a cleared map hides about a thousand): one file
        listing = out / f'{variant}.removed-casters.txt'
        listing.write_text(''.join(h['name'] + '\n' for h in hidden), encoding='utf-8', newline='\n')
        cmd += ['--remove-caster-list', str(listing)]
    else:
        for h in hidden:
            cmd += ['--remove-caster', h['name']]
    if edit_spec:
        cmd += ['--edit-spec', str(edit_spec)]
    # the map's own landings moved in place (native_spawns.py): each piece with a mesh (the grounded Skyranger)
    # goes to the relight with its old pose, so its shadow leaves the old place and falls at the new one (F-98)
    for move in landing_record or []:
        for a in move['actors']:
            if a.get('skipped') or a['path'] not in p.by_name or not has_mesh(p, p.by_name[a['path']]):
                continue
            (loc0, rot0), _ = a['old'], a['new']
            cmd += ['--moved-in-place', '%s=%s' % (a['path'].split('.')[-1],
                                                   ','.join('%r' % float(v) for v in list(loc0) + list(rot0)))]
    if state:
        # the resolved light states and the memberships this build added (plan 4.4): the relight never rebuilds
        # them from the grown map
        registered = {p.name(ci): [h for h, _ in v] for ci, v in registration['registered'].items()}
        for path, v in copy_members.items():
            registered.setdefault(path, []).extend(h for h, _ in v)
        edits_file = out / f'{variant}.light-edits.json'
        edits_file.write_text(json.dumps(native_lights.relight_edits(state, registered), indent=1) + '\n',
                              encoding='utf-8', newline='\n')
        cmd += ['--light-edits', str(edits_file)]
    if jobs:
        cmd += ['--jobs', str(jobs)]
    if piece_cache and base:
        # the pieces of this project's last baked build, for those the new edit leaves as they were
        cmd += ['--piece-cache', str(piece_cache), '--base', base]
    return cmd


def clone_copies(st):
    """The Build `st`'s copies (BuildState) made as new actors, an assembly's together (clone_assembly), each with
    the lights its lightmap may list, its tiles and rebuild volume, a van's building, a ladder's top tile, its flags
    and its blasts: build's first step after the light edits. Fills the state's made, actors, firsts, ladders, vans,
    flag_copies and blast_copies."""
    import frac_walls
    import native_lights
    p, g, copies, bake, tiles, state = st.p, st.g, st.copies, st.bake, st.tiles, st.light_state
    # the lights a copy's lightmap may list: the after registry (plan 4.3, step 3)
    after_lights = None
    if bake and copies:
        after_lights = list(state['after'].values()) if state else list(native_lights.source_registry(p).values())
    meshes = {}
    made, actors, firsts, ladders, vans = [], [], [], [], []
    flag_copies, blast_copies = [], []
    scenery_grid = None     # the tile grid, read when a copy of low scenery needs it (F-100)
    for assembly, group in by_assembly(copies):
        members = []
        for c in group:
            ai = p.by_name[PL + c['actor']]
            rot = [int(v) for v in p.own(ai, 'Rotation', [0, 0, 0])]
            if c.get('rotation') is not None:
                rotation = [int(v) for v in c['rotation']]
            else:
                rotation = [rot[0], int(c['yaw']) if c.get('yaw') is not None else rot[1], rot[2]]
            location = [float(v) for v in c['location']]
            extra = {}
            if bake:
                for ci in subtree(p, ai):
                    if static_mesh(p, ci) > 0:
                        extra[ci] = extra_lights(p, ci, location, rotation, lights=after_lights,
                                                 fresh=bool(c.get('staged')))
                        # an added or changed light reaching the copy's place is listed by membership, whatever
                        # its brightness there (plan 4.3)
                        for guid, light in native_lights.copy_registrations(p, state, ci, location, rotation, meshes):
                            same = [x for x in extra[ci] if x['guid'] == guid]
                            for x in same:
                                x.update(kept=True, membership=True)
                            if not same:
                                extra[ci].append(dict(light=light, guid=guid, peak=None, kept=True, membership=True))
            members.append((c, ai, location, rotation, extra))
        guids = {ci: list(dict.fromkeys(x['guid'] for x in found if x['kept']))
                 for *_, extra in members for ci, found in extra.items()}
        # a van's building and floor volumes go with its parts, carried by the same move (plan section 7.6)
        found = (van_buildings(p, [ai for _, ai, *_ in members])
                 if any(c.get('family') == 'van' for c, *_ in members) else [])
        van = found[0] if found else None
        volumes = []
        if van:
            _, a0, loc0, rot0, _ = members[0]
            before = (p.own(a0, 'Location', [0.0, 0.0, 0.0]), p.own(a0, 'Rotation', [0, 0, 0]))
            for v in [van['building']] + van['volumes']:
                volumes.append((v, *moved_pose(p.own(v, 'Location', [0.0, 0.0, 0.0]), p.own(v, 'Rotation', [0, 0, 0]),
                                               before, (loc0, rot0))))
        # the mesh components of pieces brought from another map: lit from nothing in a baked build
        fresh = {ci for c, ai, *_ in members if c.get('staged') and bake
                 for ci in subtree(p, ai) if p.cls(ci) in MESH_COMPONENTS}
        # the components that get a mesh made from numbers: the donor's shadow map of the dominant light, laid out for
        # the donor's mesh, is not cloned (frac_walls.add_walls gives each its own)
        made_components = {ci for c, ai, *_ in members if c.get('generated')
                           for ci in [frac_walls.made_component(p, ai, c['generated'])] if ci}
        infos = clone_assembly(g, p, [(ai, location, rotation) for _, ai, location, rotation, _ in members] + volumes,
                               own_lighting=bake, extra_guids=guids, fresh=fresh,
                               shadow_guid=dominant_guid(p) if fresh else None, made=made_components)
        infos, volume_infos = infos[:len(members)], infos[len(members):]
        own = {info['actor'] for info in infos}
        for info in infos:
            info['own'] = own
        if van:
            change = edit_van_building(g, p, van['building'], volume_infos[0]['actor'], own)
            vans.append(dict(assembly=assembly, **change, building=dict(original=p.name(van['building']).split('.')[-1],
                             export=volume_infos[0]['actor'], location=volumes[0][1], rotation=volumes[0][2]),
                             floorVolumes=[dict(original=p.name(v).split('.')[-1], export=info['actor'], location=loc,
                                                rotation=rot) for (v, loc, rot), info in zip(volumes[1:], volume_infos[1:])]))
        # low scenery the map turned the collision off on (a ground plane or pavement of its backdrop), copied into
        # the play area, gets its collision on: it is floor there, as the map's own floor pieces are (F-100)
        walked = set()
        for c, ai, location, rotation, _ in members:
            if p.cls(ai) not in SCENERY_CLASSES or p.effective(ai, 'bCollideActors', True) is not False or not has_mesh(p, ai):
                continue
            # (the user's Floor off gives way to nothing: such a copy keeps its collision off, piece flags plan 6.2)
            if (c.get('flags') or {}).get('floor') is False:
                continue
            box = piece_box(p, ai, location, rotation)
            scenery_grid = scenery_grid or level_grid(p)
            if walkable_scenery(p, ai, box) and in_grid(box, scenery_grid):
                make_walkable(g, p, ai, infos[[m[1] for m in members].index(ai)]['mapping'])
                walked.add(ai)
        # ground shapes made from numbers collide and take cover, whatever their donor (a backdrop plane) saves
        for c, ai, location, rotation, _ in members:
            if (c.get('generated') or {}).get('kind') == 'ground':
                changed = ground_collision(g, p, ai, infos[[m[1] for m in members].index(ai)]['mapping'])
                walked.add(ai)
                if changed:
                    print('    %s: a ground shape on %s, which saves its collision or cover off: on for the shape (%s)'
                          % (c.get('label') or c['actor'], p.name(ai).split('.')[-1], ', '.join(changed)))
        # the copies' flags, on their clones (the bPathColliding make_walkable wrote counts as theirs; a ground
        # shape's writes are made_settings')
        for (c, ai, *_), info in zip(members, infos):
            if c.get('flags'):
                kind = (c.get('generated') or {}).get('kind')
                flag_copies.append(set_roles(g, p, ai, info['actor'], c['flags'],
                                             known={'bPathColliding': True} if ai in walked and kind != 'ground' else None,
                                             label=c.get('label') or c['actor'], made=kind))
        # a moved piece of the map's broken by blasts: on its clone (E6)
        for (c, ai, *_), info in zip(members, infos):
            if c.get('blasts') and not c.get('generated'):
                blast_copies.append(break_component(g, p, ai, info['mapping'], c['blasts'], label=c.get('label') or c['actor'],
                                                    breaks_further=bool(c.get('breaksFurther'))))
        # (a piece that collides with nothing, a sky dome 127,000 units across, changes no tile: seeding the whole
        # grid under it only made the game re-check every tile, F-93)
        box = None
        if tiles and any(collides(p, ai) or ai in walked for _, ai, _, _, _ in members):
            box = assembly_box(p, [(ai, loc, rot) for _, ai, loc, rot, _ in members])
            # a generated wall (frac_walls.py) stands in its own box, not its donor's
            gen = [(c, ai, loc, rot) for c, ai, loc, rot, _ in members if c.get('generated')]
            if gen:
                box = frac_walls.wall_box(p, gen[0][1], gen[0][2], gen[0][3], gen[0][0]['generated']) or box
        tile_info = add_tiles_box(g, p, box) if box is not None else None
        if tile_info:
            # where a copy of the map's own piece carries a slanted corner with diagonal cover (diagonal_keep.write)
            for c, ai, location, rotation, _ in members:
                if has_mesh(p, ai) and (collides(p, ai) or ai in walked) and not (c.get('generated') or c.get('staged')) \
                        and getattr(g, 'diagonal_carries', True):
                    diagonal_candidates(g, p, piece_box(p, ai, location, rotation), tile_info['grid'], (ai, location, rotation))
        actors += ([info['actor'] for info in infos] + [info['actor'] for info in volume_infos]
                   + ([tile_info['volume']['export']] if tile_info else []))
        # a ladder's linked top tile rebuilt before anything reaches its foot (plan section 5.2, recipe 1)
        for (c, *_), info in zip(members, infos):
            if c.get('ladder') and tiles:
                top = tile_volume(g, p, c['ladder']['top'])
                firsts.append(top['export'])
                ladders.append(dict(actor=c['actor'], export=info['actor'], foot=list(c['ladder']['foot']),
                                    top=list(c['ladder']['top']), topVolume=top))
        for k, ((c, ai, location, rotation, extra), info) in enumerate(zip(members, infos)):
            made.append(dict(actor=c['actor'], label=c.get('label'), location=location, rotation=rotation, info=info, extra=extra,
                             staged=bool(c.get('staged')), donor=c.get('donor'), generated=c.get('generated'),
                             breakGroup=c.get('breakGroup') or 0, wallGroup=c.get('wallGroup') or 0,
                             tiles=tile_info if k == 0 else None,
                             walkable=ai in walked,
                             **({'assembly': assembly, 'family': c.get('family')} if assembly else {})))
    st.made, st.actors, st.firsts, st.ladders, st.vans = made, actors, firsts, ladders, vans
    st.flag_copies, st.blast_copies = flag_copies, blast_copies


def fracturing_copies(st):
    """The Build `st`'s fracturing copies (BuildState: a car's glass, a wall, a storey floor) with their columns,
    and the walls, slabs and ground shapes made from numbers (frac_walls.py), after the copies are made
    (clone_copies) and the cover blocks. Fills the state's poses (each copy's original, clone, the original's pose
    and its own, and its family), fracturing (the fracturing copies, as (original, clone)) and generated_records."""
    import frac_columns
    p, g, bake, made = st.p, st.g, st.bake, st.made
    # each copy: its original, its clone, the original's pose and its own
    poses = []
    for m in made:
        original = p.by_name[PL + m['actor']]
        poses.append((original, m['info']['actor'], (p.own(original, 'Location', [0.0, 0.0, 0.0]),
                      p.own(original, 'Rotation', [0, 0, 0])), (m['location'], m['rotation']), m.get('family')))
    # a fracturing copy (a car's glass, a wall, a storey floor): its columns go with it, still listing the pieces
    # copied with it, its assembly's and those carried by the same move (move_columns)
    fracturing = []
    for m, (original, copy, before, after, _) in zip(made, poses):
        own = m['info'].pop('own')
        if p.cls(original) not in FRACTURING:
            continue
        partners = {}
        for o, c, b0, a0, _ in poses:
            if c not in own and o not in partners and frac_columns.same_move((before, after), (b0, a0)):
                partners[o] = c
        m['info']['columns'] = frac_columns.move_columns(g, p, original, copy, before, after, own, partners)
        # the fragments' saved world heights go up or down with a storey move
        frac_columns.shift_fragment_heights(g, p, m['info']['mapping'], after[0][2] - before[0][2])
        fracturing.append((original, copy))
    # generated walls (frac_walls.py, plan section 0): a fracturing copy's mesh and columns made from numbers
    generated = [dict(original=original, info=m['info'], generated=m['generated'], location=after[0], rotation=after[1],
                      label=m.get('label') or m['actor'], wallGroup=m.get('wallGroup') or 0)
                 for m, (original, copy, before, after, _) in zip(made, poses) if m.get('generated')]
    generated_records = []
    if generated:
        import frac_walls
        generated_records = frac_walls.add_walls(g, p, generated, level_grid(p), bake=bake)
        for r in generated_records:
            light = r.get('light') or {}
            lit = ('%d x %d texels of its own' % tuple(light['rect']) if light.get('kind') == 'rect'
                   else 'one even light, from %s' % light['piece'].split('.')[-2] if light.get('kind') == 'even'
                   else 'as its donor\'s')
            if r['kind'] in frac_walls.MADE:
                print('    %s: made from numbers as %s, %d fragments%s, %d triangles, %d collision boxes; its columns '
                      'are its own (%d); its lightmap %s' % (
                          r['label'], r['meshName'], r['fragments'],
                          (' (%d knocked out by its blasts%s)' % (r['broken'], '; bPreventChunkRemoval turned off'
                                                                  if r.get('chunksLet') else '; kept whole in battle, the '
                                                                  'hole cut into its mesh' if r.get('keptWhole') else ''))
                          if r.get('broken') else '',
                          r['triangles'], r['solids'], r['columns'], lit))
            elif r['kind'] == 'ground':
                print('    %s: a ground shape made from numbers as %s, %d triangles, one collision element; its lightmap %s'
                      % (r['label'], r['meshName'], r['triangles'], lit))
    st.poses, st.fracturing, st.generated_records = poses, fracturing, generated_records


def wall_columns(st):
    """The walls' fragment columns after the hides and the lanes (BuildState `st`): the hidden pieces left out and
    the door copies added (frac_columns.edit_columns), and the walls made from numbers listing a door in their
    opening, a group that breaks with them and the fracturing pieces they meet (frac_walls.py). Fills the state's
    columns, door_listings, group_listings and neighbour_listings."""
    import frac_columns
    p, g, made, poses, fracturing = st.p, st.g, st.made, st.poses, st.fracturing
    generated_records, hidden, walled = st.generated_records, st.hidden, st.walled
    break_originals, cover_records = st.break_originals, st.cover_records
    # the walls' columns without the hidden pieces and with the door copies (G8); every copy in the cutaway of its
    # building floor (G7)
    columns = frac_columns.edit_columns(g, p, {h['export'] for h in hidden}, [x[:4] for x in poses if x[4] == 'door'],
                                        fracturing)
    # a door in a made wall's opening that nothing lists yet (a door of another map): in the wall's columns by it
    door_listings = []
    if any(r['kind'] == 'fracWall' for r in generated_records):
        import frac_walls
        door_listings = frac_walls.door_columns(
            g, p, generated_records, [(copy, piece_box(p, original, *after), original)
                                      for original, copy, before, after, family in poses if family == 'door'])
        for d in door_listings:
            print("    %s's copy: in a made wall's doorway, listed in %d of its columns"
                  % (p.name(d['original']).split('.')[-1], len(d['columns'])))
    # a group that breaks together with a made wall: its props and cover blocks in the wall's columns by them
    group_listings = []
    if walled:
        members, labels = {}, {}
        for m, (original, copy, before, after, _) in zip(made, poses):
            if m.get('breakGroup') in walled:
                members.setdefault(m['breakGroup'], []).append((copy, piece_box(p, original, *after), original))
                labels[copy] = m.get('label') or m['actor']
        for o in break_originals:
            if int(o['group']) in walled:
                i = p.by_name[PL + o['name']]
                members.setdefault(int(o['group']), []).append(
                    (i, piece_box(p, i, p.own(i, 'Location', [0.0, 0.0, 0.0]), p.own(i, 'Rotation', [0, 0, 0])), i))
                labels[i] = o['name']
        # (a cover block that breaks is a hidden prop: its entry copies a prop's)
        prop_class = next((i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComDestructibleActor'), None)
        for c in cover_records:
            if c.get('breakGroup') in walled and prop_class:
                members.setdefault(c['breakGroup'], []).append((c['actor'], c['box'], prop_class))
                labels[c['actor']] = c['name']
        import frac_walls
        group_listings = frac_walls.group_columns(g, p, generated_records, members)
        for d in group_listings:
            print("    %s: breaks with its group's made wall, listed in %d of its columns"
                  % (labels.get(d['piece'], d['piece']), len(d['columns'])))
    # made walls and slabs and the fracturing pieces they touch list each other's columns, by the game's rule (M3 item 3)
    neighbour_listings = []
    if any(r['kind'] in ('fracWall', 'fracSlab') for r in generated_records):
        import frac_walls
        gone = {h['export'] for h in hidden}
        level_index = p.by_name['TheWorld.PersistentLevel']

        def heights(i, dz=0.0):
            comp = p.own(i, 'FracturedStaticMeshComponent')
            lo, hi = (p.own(comp, 'FragmentBoundsMinZ'), p.own(comp, 'FragmentBoundsMaxZ')) if comp else (None, None)
            return [None, None, None, None, None if lo is None else lo + dz, None if hi is None else hi + dz]
        others = [dict(export=i, original=i, bounds=heights(i)) for i in range(1, len(p.exports) + 1)
                  if p.cls(i) in FRACTURING and p.exports[i - 1]['outer'] == level_index and i not in gone
                  and not p.effective(i, 'bHidden', False)]
        made_copies = {r['copy'] for r in generated_records}
        others += [dict(export=copy, original=original, bounds=heights(original, after[0][2] - before[0][2]))
                   for original, copy, before, after, family in poses
                   if p.cls(original) in FRACTURING and copy not in made_copies]
        neighbour_listings = frac_walls.neighbour_columns(g, p, generated_records, others)
        named = {x['export']: p.name(x['original']).split('.')[-1] + ('' if x['export'] == x['original'] else "'s copy")
                 for x in others}
        named.update({r['copy']: r['label'] for r in generated_records if r['kind'] in ('fracWall', 'fracSlab')})
        for d in neighbour_listings:
            print('    %s and %s list each other\'s columns where they meet (%d and %d listings)'
                  % (named[d['wall']], named.get(d['other'], d['other']), d['lists'], d['listed']))
    st.columns, st.door_listings = columns, door_listings
    st.group_listings, st.neighbour_listings = group_listings, neighbour_listings


def edit_buildings(st):
    """The building floors after the copies, the hides and the walls' columns (BuildState `st`): each copy in the
    cutaway of the map's building floor it stands in (edit_floor_caches), the walls made from numbers in the map's
    buildings they stand in (list_made_walls), the buildings made from nothing (buildings.make) and the map's own
    edited in place (buildings.edit), with the slots they empty. Fills the state's floor_caches, made_floors,
    building_actors, building_records, edit_records and edit_slots."""
    p, g, made, poses, generated_records, hidden = st.p, st.g, st.made, st.poses, st.generated_records, st.hidden
    buildings, building_edits = st.buildings, st.building_edits
    # the map's own buildings edited in place (their new boxes), for the copies' floors
    replaced = {}
    for e in building_edits:
        bi = p.by_name.get(PL + e['actor'])
        if bi is not None:
            replaced[bi] = None if e.get('deleted') else [x for f in e['floors'] for x in [f['boxes']]]
    # a van's parts are in its own building's cutaway, which comes with them
    made_walls = {r['copy'] for r in generated_records if r['kind'] in ('fracWall', 'fracSlab', 'ground')}
    floor_caches = edit_floor_caches(g, p, [x[:4] for x in poses if x[4] != 'van' and x[1] not in made_walls], replaced)
    # walls made from numbers in the map's own buildings they stand in, by their own boxes (M3 item 7)
    made_floors = list_made_walls(g, p, generated_records, replaced) if made_walls else []
    for d in made_floors:
        print('    %s: in %s\'s cutaway, %s' % (
            next(r['label'] for r in generated_records if r.get('copy') == d['wall']), p.name(d['building']).split('.')[-1],
            ', '.join('floor %d%s' % (k, ', CutdownFloor %d' % cut if cut else '') for k, cut in d['floors'])))
    # the buildings made from nothing: their volumes, and in each floor the pieces that stand in it after the edit
    building_actors, building_records, edit_records, edit_slots = [], [], [], set()
    if buildings or building_edits:
        import buildings as new_buildings
        gone = {h['export'] for h in hidden}
        level_index = p.by_name['TheWorld.PersistentLevel']
        candidates = [dict(actor=i, source=i, name=p.name(i).split('.')[-1]) for i in level_actors(p)
                      if i > 0 and i not in gone and p.exports[i - 1]['outer'] == level_index
                      and not p.effective(i, 'bHidden', False)]
        made_boxes = {r['copy']: r['box'] for r in generated_records if r['kind'] in ('fracWall', 'fracSlab', 'ground')}
        candidates += [dict(actor=copy, source=original, location=after[0], rotation=after[1], label=m['label'],
                            name='copy of ' + p.name(original).split('.')[-1],
                            **({'box': made_boxes[copy]} if copy in made_boxes else {}))
                       for m, (original, copy, _, after, _) in zip(made, poses)]
        if buildings:
            building_actors, building_records = new_buildings.make(g, p, buildings, candidates)
        if building_edits:
            # a moved piece's copy stands in for it in the building's external mesh groups
            moved_copies = {original: copy for original, copy, *_ in poses if original in gone}
            edit_actors, edit_slots, edit_records = new_buildings.edit(g, p, building_edits, candidates, gone,
                                                                       moved_copies)
            building_actors += edit_actors
            if edit_slots:
                empty_slots(g, p, edit_slots)
    st.edit_slots = set(edit_slots)
    st.floor_caches, st.made_floors = floor_caches, made_floors
    st.building_actors, st.building_records, st.edit_records = building_actors, building_records, edit_records


def edits_in_place(st):
    """The map's own actors edited in place once every copy is made from them (BuildState `st`): the added and
    changed lights listed in the receivers they reach (native_lights.register), the clear (clear_level), the map's
    landings moved (native_spawns.apply), pieces' flags (flags_in_place) and blasts (blasts_in_place) where they
    stand, a mission's pieces' tiles moved in their stream, and the ladders' top tiles first in the rebuild order.
    Fills the state's registration, cleared_record, landing_record, flag_record, blast_record, stream_record and
    priority, and adds to its hide_volumes, firsts and ladders."""
    import native_lights
    p, g, bake, tiles, state, light_result = st.p, st.g, st.bake, st.tiles, st.light_state, st.light_result
    cleared, building_edits, landing_zones, stream_tiles = (st.cleared, st.building_edits, st.landing_zones,
                                                            st.stream_tiles)
    piece_flags, flag_ladders, piece_blasts = st.piece_flags, st.flag_ladders, st.piece_blasts
    hidden, hide_volumes, effect_moved = st.hidden, st.hide_volumes, st.effect_moved
    firsts, ladders = st.firsts, st.ladders
    flag_record = blast_record = None
    # the added and changed placed lights in the lightmaps of the map's own receivers they reach (baked builds only;
    # plan 4.3, step 4); the copies' are in their clones already
    registration = None
    if state and bake:
        registration = native_lights.register(g, p, state, native_lights.Registrar(p),
                                              exclude={h['export'] for h in hidden})
    if light_result and light_result['gone']:
        empty_slots(g, p, light_result['gone'])
    cleared_record = None
    if cleared:
        taken = st.gone()
        # the map's buildings the edit changes in place keep their volumes
        keep = {p.by_name[PL + n] for e in building_edits if not e.get('deleted')
                for n in [e['actor']] + [v for f in e.get('floors') or [] for v in f.get('volumes') or [] if v]
                if PL + n in p.by_name} | effect_moved      # a moved piece's effects stay with it
        cleared_record, clear_volume = clear_level(g, p, taken, keep, cleared.get('keepOutside'),
                                                   cleared.get('keepTriggers') is True)
        st.cleared_record = cleared_record
        hide_volumes = hide_volumes + [clear_volume]
    # the map's background sound: its level-loaded sound given another cue, none, or another volume
    import native_sounds
    st.sound_record = native_sounds.background(g, p, st.background_sound)
    landing_record = None
    if landing_zones:
        import native_spawns
        landing_record, landing_volumes = native_spawns.apply(g, p, landing_zones, st.gone())
        hide_volumes = hide_volumes + landing_volumes
    # the map's own pieces whose flags change where they stand: after every copy is made from them and the clear
    # has run, so neither a copy nor a piece the clear takes out gets them
    if piece_flags:
        gone_now = st.gone()
        flag_record, flag_volumes, flag_firsts, flag_ladder_records = flags_in_place(
            g, p, piece_flags, flag_ladders, gone_now, tiles=tiles, volumes=not cleared)
        hide_volumes = hide_volumes + flag_volumes
        firsts += flag_firsts
        ladders += flag_ladder_records
    # the map's own fracturing pieces broken where they stand (E6): after every copy is made from them
    if piece_blasts:
        gone_now = st.gone()
        blast_record, blast_volumes = blasts_in_place(g, p, piece_blasts, gone_now, tiles=tiles, volumes=not cleared)
        hide_volumes = hide_volumes + blast_volumes
    # a mission's solid pieces moved in their stream (mission types plan, Part E; stream_copy.tile_boxes): the map's
    # baked tiles rebuilt where each stood, and seeded and rebuilt where it stands now, as a moved landing's are
    stream_record = []
    for t in stream_tiles or ():
        old, new = hide_tiles(g, p, t['old']), add_tiles_box(g, p, t['new'])
        hide_volumes = hide_volumes + [v['volume']['export'] for v in (old, new) if v]
        stream_record.append(dict(stream=t['stream'], actor=t['actor'], old=old['tiles'] if old else None,
                                  new=new['tiles'] if new else None, seeded=new['seeded'] if new else 0))
    priority = ()
    if ladders and any(a > 0 and p.cls(a) == 'XComRebuildWorldDataVolume' for a in level_actors(p)):
        # A resized map (the blank map, a grown or cleared one: shell.py's ground volume) already has a rebuild
        # volume. It would queue the ladders' newly seeded tiles before their top volumes. Queue the top tiles
        # first, highest first when two climbs share a tile. A map of the game's as it is has none.
        priority = [l['topVolume']['export'] for l in sorted(ladders, key=lambda l: -l['top'][2])]
        firsts = []
    st.registration, st.landing_record, st.stream_record = registration, landing_record, stream_record
    st.flag_record, st.blast_record, st.priority = flag_record, blast_record, priority
    st.hide_volumes, st.firsts, st.ladders = hide_volumes, firsts, ladders


def floors_and_cursors(st):
    """The building floors' effect lists against the final effects and floors (native_effects.floor_lists), and the
    made floors' and roofs' own cursor floors (made_cursors.py), after the copies, the buildings, the clear and the
    landings (BuildState `st`). Fills the state's floor_emitters, cursor_record and cursor_clones."""
    import native_effects
    p, g, building_edits, building_records = st.p, st.g, st.building_edits, st.building_records
    effect_record, lane_effects, generated_records = st.effect_record, st.lane_effects, st.generated_records
    # the building floors' effect lists, once, against the final effects and floors (plan Part D): after the copies'
    # cutaways, the buildings made and edited, the clear and the landings
    moved_now = {r['export']: r['location'] for r in lane_effects if r['how'] == 'moved'}
    moved_now.update({p.by_name[PL + r['effect']]: r['location'] for r in effect_record if r['how'] == 'moved'})
    new_now = {r['export']: r['location'] for r in lane_effects if r['how'] == 'copied'}
    new_now.update({r['copy']: r['location'] for r in effect_record if r['how'] == 'copied'})
    gone_effects = ({r['export'] for r in lane_effects if r['how'] == 'deleted'}
                    | {p.by_name[PL + r['effect']] for r in effect_record if r['how'] == 'deleted'})
    floor_emitters = native_effects.floor_lists(g, p, moved_now, new_now, gone_effects, building_edits,
                                                building_records)
    # the made floors' and roofs' own cursor floors over their footprints (made_cursors.py; custom geometry plan M5b,
    # F-128): the map's cursor volumes they cross taken out and stood again round them, and floors breaking at
    # their tops over them (a slab turned off the quarter turns: in steps, made_cursors.build_slabs)
    cursor_record, cursor_clones = None, []
    if any(r['kind'] == 'fracSlab' for r in generated_records):
        import made_cursors
        made_slabs = made_cursors.build_slabs(p, generated_records, st.copies)
        cursor_record, cursor_clones = made_cursors.apply(g, p, made_slabs)
        if cursor_record:
            print("    the made floors' and roofs' cursor floors: %d of the map's cursor volumes taken out (%s), %d made "
                  '(%d over the made slabs)' % (len(cursor_record['hidden']), ', '.join(cursor_record['hidden']) or 'none',
                                               len(cursor_record['added']), sum(a['over'] for a in cursor_record['added'])))
            for c in cursor_record['crossed']:
                print("    %s is over the map's %s cursor volume %s, left as it is" % (
                    c['slab'], 'stair' if c['why'] == 'stair' else 'turned', c['volume']))
    st.floor_emitters, st.cursor_record, st.cursor_clones = floor_emitters, cursor_record, cursor_clones


def taken_out(p):
    """The exports directly under the persistent level that are not in its actor list: the actors the Build took out
    of the level (a deleted piece, building, floor volume, light or effect), and the few objects the game's maps
    keep there that are no actors (its Kismet's main sequence)."""
    level = p.by_name['TheWorld.PersistentLevel']
    listed = set(level_actors(p))
    return {i for i in range(1, len(p.exports) + 1) if p.exports[i - 1]['outer'] == level and i not in listed}


def rewrite_tiles(path, boxes):
    """The written map at `path` with its tile data rewritten once (written in place when anything changed):
    - the tiles near its changes (`boxes`: the grower's change_boxes) and round the floors of the pieces taken out of
      the level as the battle's rebuild will leave them (start_tiles.apply): the game places the terror civilians and
      the pods' other aliens from the stored tiles before that rebuild runs (F-157);
    - then no tile naming an actor the Build took out of the level (world_grid.forget): the game frees such an actor
      once the map has loaded, and a tile that still named it made saving the battle crash (F-156: a deleted
      building's floor volumes, deleted floor pieces, outside every rebuild volume).
    Returns (start_tiles.apply's record, world_grid.forget's counts), each {} when it changed nothing."""
    import os
    import package_grow
    import start_tiles
    import world_grid
    p = lighting.Package(Path(path))
    if not any(p.cls(i) == 'XComWorldDataContainer' for i in range(1, len(p.exports) + 1)):
        return {}, {}
    index, blob = world_grid.container_of(p)
    model, start = start_tiles.apply(p, boxes)
    if model is None:
        model = world_grid.decode(blob)
    counts = world_grid.forget(model, taken_out(p))
    counts = {k: v for k, v in counts.items() if v}
    if not start and not counts:
        return {}, {}
    encoded = world_grid.encode(model)
    if encoded[:world_links.HEADER] != blob[:world_links.HEADER]:
        raise ValueError('the tile data was not written back with its header')
    g = package_grow.Grower(str(path))
    g.relocate(index, encoded)
    tmp = Path(str(path) + '.tiles')
    g.write(str(tmp))
    del g, p
    os.replace(tmp, path)
    return start, counts


def write_and_verify(st):
    """The variant map written and read back (BuildState `st`): every new actor in the level's list (add_to_level),
    the map written by the growing writer (<out>/<variant>.upk, or with bake the grown map in <out>/grown, its name
    table holding the variant cache's name), then what was written checked from a fresh read: the copies' vertex
    lightmaps, the light edits, the lanes and the floors' effect lists, the made cursors, the flags; the ladders'
    rebuild order read from it. Fills the state's level, dst, report and q, and the ladders' records read back."""
    import native_effects
    import native_flares
    import native_lights
    import native_sounds
    import native_spawns
    p, g, src, out, variant, bake, cache = st.p, st.g, st.src, st.out, st.variant, st.bake, st.cache
    firsts, actors, hide_volumes, priority, made = st.firsts, st.actors, st.hide_volumes, st.priority, st.made
    building_actors, effect_clones, cursor_clones = st.building_actors, st.effect_clones, st.cursor_clones
    state, light_result, cursor_record = st.light_state, st.light_result, st.cursor_record
    floor_emitters, lane_effects, lane_sounds = st.floor_emitters, st.lane_effects, st.lane_sounds
    lane_flares, lane_spawns = st.lane_flares, st.lane_spawns
    flag_copies, flag_record, ladders = st.flag_copies, st.flag_record, st.ladders
    level = add_to_level(g, p, firsts + actors + hide_volumes + building_actors + effect_clones + cursor_clones
                         + (light_result['actors'] if light_result else []), before_rebuild=priority)
    dst = out / ('grown' if bake else '') / (src.name if bake else f'{variant}.upk')
    dst.parent.mkdir(parents=True, exist_ok=True)
    if bake:
        # the variant texture cache's name in the table (the Build's <Map>_Lighting), so the relight's fixture,
        # reading the grown map afresh, can write it into the textures it redirects (lightmap_writer.cache_fname)
        g.name(lightmap_writer.cache_table_name(cache))
    report = g.write(str(dst))
    # the diagonal cover tiles next to a change, left out of the rebuild: written now, against the built map
    # (diagonal_keep.py; findings register F-149)
    if getattr(g, 'diagonal_writes', None) or getattr(g, 'diagonal_whole', None) or \
            getattr(g, 'diagonal_candidates', None) or g.diagonal_edit:
        import diagonal_keep
        st.diagonal = diagonal_keep.write(dst, getattr(g, 'diagonal_writes', set()), getattr(g, 'diagonal_whole', set()),
                                          getattr(g, 'diagonal_candidates', set()), g.diagonal_edit)
    # the tile data rewritten once: the tiles near the changes as the battle's rebuild will leave them (the game
    # places the terror civilians and the pods' other aliens from the stored tiles before it runs that rebuild,
    # F-157), and no tile naming an actor taken out of the level (the game frees those, and saving crashed, F-156)
    st.start_tiles, st.forgot = rewrite_tiles(dst, getattr(g, 'change_boxes', []))
    if st.start_tiles:
        print('tiles: %s near the changes written as the battle\'s rebuild will leave them (%s)'
              % (st.start_tiles['written'], ', '.join('%s %s' % (k, v) for k, v in st.start_tiles.items()
                                                      if k not in ('written',))))
    if st.forgot:
        print('tiles: %s' % ', '.join('%s %d' % (k, v) for k, v in st.forgot.items()) + ' named actors taken out of '
              'the level: cleared (a link or interact point dropped)')
    q = lighting.Package(dst)
    for m in made:
        check_vertex_lightmaps(q, m['info']['mapping'])
    if state:
        native_lights.verify(q, state, light_result)
    # the effects' and sounds' lanes and the floors' effect lists read back
    if lane_effects or lane_sounds or lane_flares or floor_emitters or lane_spawns:
        from package import Package as Reader
        r = Reader(dst)
        native_effects.verify(r, lane_effects, floor_emitters)
        native_sounds.verify(r, lane_sounds)
        native_flares.verify(r, lane_flares)
        native_spawns.verify(r, lane_spawns, p)
    if st.sound_record:
        from package import Package as Reader
        native_sounds.verify_background(Reader(dst), st.sound_record)
    # the made floors' cursor volumes read back
    if cursor_record and cursor_record['added']:
        import made_cursors
        from package import Package as Reader
        made_cursors.verify(Reader(dst), cursor_record)
    # the flags read back with a fresh reader: an edit not in the map is an error, never a success
    for rec in flag_copies + (flag_record['pieces'] if flag_record else []):
        verify_roles(q, rec)
    ladders = ladder_order(q, [dict(l, copy=q.name(l['export']).split('.')[-1]) for l in ladders]) if ladders else []
    st.level, st.dst, st.report, st.q, st.ladders = level, dst, report, q, ladders


def build(st):
    """The Build `st` (BuildState), made by its caller with its inputs: the fields named here (src, out, variant,
    copies, bake...), which build reads once, and the state build fills as it goes.

    The map `src` with `copies` made as new actors: <out>/<variant>.upk, or with `bake` the grown map in
    <out>/grown and the relit variant (relight.py), and the fixture manifest <out>/<variant>.fixture.json, with a
    `nativeCopies` section. A copy is a dict of actor (as XComLevelActor_37), location, and rotation [pitch, yaw, roll]
    or yaw alone (the original's pitch and roll); with neither, the original's rotation. `edit_spec`, with `bake`: an
    editor patch spec whose exact hides (and posed copies) relight models too (relight.py --edit-spec), for an edit
    whose hidden pieces stay in a patch. A copy's `breakGroup` (a number) and `break_originals` ({name, group}: the
    map's own pieces left in place) link the editor's groups that break together (link_children). `hides` ({name,
    box}) are taken out of the map (hide_pieces), after the copies are made (a moved piece is the source of its copy)
    and before the relight, which leaves them out of the scene after the edit (--remove-caster).

    Copies with the same `assembly` (the compiler's assemblies: a car's parts, a door's leaf and frame) are one copy of
    it: cloned together, so their references to each other point at each other's clones (clone_assembly), with one
    rebuild volume over them all (assembly_box), its tiles recorded on the first. `assemblies` (the compiler's moves:
    id, family, members, turns, translation) go into the manifest.

    `lights` is the native edit's light edits (editor lights plan, 9.5; native_lights.py): resolved against the
    pristine map once, made in the map before the copies (a light gets no tiles), and recorded in the manifest's
    `lights` section. With `bake`, the copies' extra lights come from the lights after the edit, each added or changed
    placed light that emits is listed in the texture lightmaps of the receivers it reaches at their final poses (the
    copies' too), and the relight gets the resolved before and after lights (relight.py --light-edits,
    <out>/<variant>.light-edits.json). Without, every receiver's lightmap list stays as it is.

    `covers` are the editor's cover blocks (the compiler's: name, kind, location, rotation, size, heights, box):
    invisible pieces that give cover, a hidden level actor and a box mesh made from a recipe (cover_blocks.py), each
    in its tiles as a copy is. The manifest's `coverBlocks` lists them.

    `buildings` are buildings made from nothing (buildings.py: id, name, kind, floors of boxes): a building volume
    and floor volumes cloned from the map's, each floor listing the pieces that stand in it after the edit (the map's
    own that are not hidden, and the copies), by the game editor's own rule. The manifest's `buildings` lists them.
    `building_edits` are the map's own buildings changed or deleted (the compiler's buildingEdits; buildings.edit),
    edited in place after the copies and hides: the manifest's `buildingEdits` lists what each kept, moved, made and
    took out.

    A copy with `staged` is a piece of another map, staged in `src` by transplant.py (its `actor` the staged actor,
    which no level lists). Without `bake` it keeps its home map's lighting. With `bake` it is lit from nothing: its
    lightmaps list this map's lights alone, its shadow maps name this map's dominant light, and the relight gives
    it the light of where it stands (relight.py --foreign-copy), with the staged actor left out of both scenes.

    `cleared` (the compiler's: {grid, keepOutside?, keepTriggers?}) says the map was cleared (Clear map plan, section 7): the hides get no rebuild
    volume of their own, and clear_level takes out what the editor never showed and puts one volume over the grid,
    after the hides and the building edits. The manifest's `cleared` section counts what it took by class.

    `carried_effects` (the compiler's `carriedEffects`, {piece: [effect]}: export 23's carriedBy) are the effects
    that follow their piece's move, copy or delete (native_effects.py).

    `effects` and `sounds` (the compiler's lanes: {moves, deletes, copies}; the effects and sounds plan, stage FX3) are
    the effects and ambient sounds the project moves in place, takes out of the level's list or copies
    (native_effects.apply, native_sounds.apply); after every other writer, native_effects.floor_lists lists the moved
    and new effects (the lanes' and the carried ones) in the building floors whose boxes hold them and takes the moved
    and deleted ones out of the lists that named them. A directly moved effect stays on a cleared map. The manifest's
    `effects`, `sounds` and `floorEmitters` sections say what was done, read back (native_effects.verify).

    `flares` is the same lane for the lens flares (LensFlareSource actors; stage FX6b, native_flares.apply): a move in
    place, a delete off the level's list, a copy cloned with its LensFlareComponent, the flare template shared. A
    flare is in no floor's list; a clear takes the map's flares out (CLEAR_OUT) but for one the project moves itself,
    and a copy is made after the clear. The manifest's `flares` section says what was done, read back.

    `spawns` (the compiler's lane: {moves, values}; the editor spawns plan, SP6) moves the base map's pods, Meld points
    and drop-in points in place and sets their values (native_spawns.apply_lane); the manifest's `spawns` section
    says what was done, read back (native_spawns.verify).

    `background_sound` (the compiler's `backgroundSound`: {op, cue, volume?}) gives the map's level-loaded sound another
    cue, none or another volume (native_sounds.background), read back (native_sounds.verify_background); the manifest's
    `backgroundSound` says what was written.

    `landing_zones` (the compiler's: {zones, own, ownLandings}) moves the map's own landings to the zones that are also
    theirs (native_spawns.py), in place; the manifest's `landings` section lists what moved.

    Pieces' flags (piece flags plan): a copy's `flags` ({role: bool}) are written on its clone once it is made
    (set_roles; a copy of low scenery whose Floor is off is not made walkable), and `piece_flags` (the compiler's
    `pieceFlags`: the map's own pieces whose flags change where they stand) on the map's actors after every copy is
    made and the clear has run (flags_in_place), their tiles worked out again, with `flag_ladders`' top tiles first.
    Each is read back from the written map. The manifest's `pieceFlags` section lists what was asked, written and
    read back.

    Broken pieces (custom geometry editing plan, E6): a copy's `blasts` (a moved piece of the map's) are written on its
    clone, and `piece_blasts` (the compiler's `pieceBlasts`: the map's own fracturing pieces broken where they stand) on
    the map's components after every copy is made (blasts_in_place), their tiles worked out again: the fragments each
    blast reaches saved painted out with those the map paints out. A piece the game keeps whole (most roofs and floors)
    draws a copy of its mesh with those fragments cut away and stays whole in battle, unless its `breaksFurther` asks
    it to break further (break_component). The manifest's `pieceBlasts` section lists them."""
    import cover_blocks
    import native_lights
    st.src, st.out = Path(st.src), Path(st.out)
    st.out.mkdir(parents=True, exist_ok=True)
    if st.bake and not st.cache:
        raise ValueError('a baked copy needs a variant texture cache name (--cache)')
    if st.bake:
        lightmap_writer.cache_fname(st.cache)     # a cache name that can be a file and an FName, before any work
    p = lighting.Package(st.src)
    g = package_grow.Grower(str(st.src))
    # the project's diagonal cover marks, as tiles: every rebuild volume keeps off its marks, and the writer writes them
    # and the tiles it takes diagonal cover from (diagonal_keep.write)
    g.diagonal_edit = diagonal_edit(p, st.diagonal_cover)
    # (a project whose page worked out the marks its pieces carry, pageCarries: the Build carries none of its own)
    g.diagonal_carries = not (st.diagonal_cover or {}).get('pageCarries')
    # the light edits: resolved against the pristine map, then made in the map (plan 4.3, steps 1 and 2)
    st.light_state = None if native_lights.is_empty(st.lights) else native_lights.prepare(p, st.lights)
    st.light_result = native_lights.apply(g, p, st.light_state) if st.light_state else None
    # what the edit takes out, added to as each step takes something (BuildState.gone)
    st.p = p
    st.lights_gone = set((st.light_result or {}).get('gone') or ())
    # the copies (clone_copies)
    st.g = g
    clone_copies(st)
    # the cover blocks: hidden level actors on box meshes, made from a recipe (cover_blocks.py), each in its tiles
    cover_actors, st.cover_records = cover_blocks.add_blocks(g, p, st.covers) if st.covers else ([], [])
    st.actors += cover_actors
    # the fracturing copies and the walls made from numbers (fracturing_copies)
    fracturing_copies(st)
    st.walled = {m['wallGroup'] for m in st.made if m.get('wallGroup')}
    st.groups, st.children = link_children(
        g, p, st.made, st.break_originals,
        [(c['breakGroup'], c['actor']) for c in st.cover_records if c.get('breakGroup')], walled=st.walled)
    st.hidden, st.hide_volumes = hide_pieces(g, p, st.hides, volumes=not st.cleared) if st.hides else ([], [])
    # the effects the moved, copied and deleted pieces carry (native_effects.py: a Skyranger's lights go with it)
    import native_effects
    st.effect_clones, effect_gone, st.effect_record = native_effects.carry(
        g, p, [(original, m.get('label'), before, after)
               for m, (original, _, before, after, _) in zip(st.made, st.poses) if m.get('staged') is not True],
        {h['export'] for h in st.hidden}, st.carried_effects)
    # the effects and sounds the project edits itself (the effects and sounds plan, Part D): moved in place, deleted
    # from the level's list, copied with what they own
    import native_sounds
    lane_clones, lane_gone, st.lane_effects = native_effects.apply(g, p, st.effects)
    sound_clones, sound_gone, st.lane_sounds = native_sounds.apply(g, p, st.sounds)
    import native_flares
    flare_clones, flare_gone, st.lane_flares = native_flares.apply(g, p, st.flares)
    # the base map's spawn points the project moves or gives values (the editor spawns plan, SP6)
    import native_spawns
    spawn_clones, spawn_gone, st.lane_spawns = native_spawns.apply_lane(g, p, st.spawns)
    effect_gone = set(effect_gone) | lane_gone | sound_gone | flare_gone | spawn_gone
    st.effect_clones = list(st.effect_clones) + lane_clones + sound_clones + flare_clones + spawn_clones
    st.effects_gone = effect_gone
    if effect_gone:
        empty_slots(g, p, effect_gone)
    st.effect_moved = ({p.by_name[PL + r['effect']] for r in st.effect_record if r['how'] == 'moved'}
                       | {r['export'] for r in st.lane_effects + st.lane_flares + st.lane_sounds
                          if r['how'] == 'moved'})
    # a moved or deleted van's building and floor volumes go with it
    edited = {p.by_name[PL + e['actor']] for e in st.building_edits if PL + e['actor'] in p.by_name}
    st.hidden_buildings = hide_van_buildings(g, p, {h['export'] for h in st.hidden}, edited) if st.hidden else []
    # the walls' columns (wall_columns)
    wall_columns(st)
    # the building floors: the copies', the made walls', the buildings made and edited (edit_buildings)
    edit_buildings(st)
    # the map's own actors edited in place: lights registered, the clear, landings, flags, blasts (edits_in_place)
    edits_in_place(st)
    # the building floors' effect lists and the made slabs' cursor floors (floors_and_cursors)
    floors_and_cursors(st)
    # the map written and read back (write_and_verify)
    write_and_verify(st)
    # what the record is made from (manifest_parts, relight_command)
    sections, common, lights_record = manifest_parts(st, st.q, st.bake)
    tool = common['tool']
    if not st.bake:
        files = {str(st.dst): lightmap_writer.sha256(st.dst.read_bytes())}
        manifest = dict(source=str(st.src), sourceSha256=lighting.digest(st.src), variant=st.variant, cache=None,
                        outputs=files, nativeCopies=dict(common, copies=sections), tool=tool)
    else:
        # the readers find the original's texture caches through tfc-folder.txt beside the grown map (nothing copied)
        lighting.link_caches(st.dst.parent, st.src.parent)
        cmd = relight_command(st, st.dst, st.out, st.variant, st.cache, st.receivers_near, st.edit_spec, st.jobs,
                              st.piece_cache, st.base)
        print(' '.join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        manifest = json.loads((st.out / f'{st.variant}.fixture.json').read_text(encoding='utf-8'))
        manifest['nativeCopies'] = dict(common, copies=sections, grown=str(st.dst),
                                        editSpec=str(st.edit_spec) if st.edit_spec else None)
    if lights_record:
        manifest['lights'] = lights_record
    (st.out / f'{st.variant}.fixture.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8',
                                                       newline='\n')
    return manifest


def copy_record(c):
    """A copy as build reads it, from a copy of the native edit (or one main makes from the command line): the record
    whole, as the compiler (and transplant.py) wrote it, since build reads its fields (a made wall's wallGroup among
    them: review finding 36, a copy's field dropped on the way); only the pose and the group are read as numbers."""
    return dict(c, location=[float(v) for v in c['location']],
                rotation=[int(v) for v in c['rotation']] if c.get('rotation') is not None else None,
                breakGroup=int(c.get('breakGroup') or 0))


def edit_state(src, out, variant, doc, **options):
    """The Build (BuildState) of the native edit `doc` on the map `src`, into `out` as `variant`: `doc` as the Build
    writes it (native-edit.json: compiler.native_split's dict of lanes), or a list of copies alone; `options` are the
    state's other inputs (bake, cache, receivers_near, jobs, tiles, edit_spec, piece_cache, base). Each lane goes to
    its field as it is, and each copy through copy_record."""
    copies, break_originals, hides, assemblies, lights, covers, buildings, edits = [], [], [], [], None, [], [], []
    cleared = landing_zones = carried_effects = effects = sounds = flares = spawns = background_sound = None
    diagonal_cover = None
    stream_tiles, piece_flags, flag_ladders, piece_blasts = [], [], [], []
    if isinstance(doc, dict):
        assemblies = doc.get('assemblies') or []
        lights = doc.get('lights')
        covers = doc.get('covers') or []
        buildings = doc.get('buildings') or []
        edits = doc.get('buildingEdits') or []
        cleared = doc.get('cleared')
        landing_zones = doc.get('landingZones')
        carried_effects = doc.get('carriedEffects')
        effects, sounds, flares = doc.get('effects'), doc.get('sounds'), doc.get('flares')
        spawns = doc.get('spawns')
        background_sound = doc.get('backgroundSound')
        stream_tiles = doc.get('streamTiles') or []
        piece_flags = doc.get('pieceFlags') or []
        flag_ladders = doc.get('pieceFlagLadders') or []
        piece_blasts = doc.get('pieceBlasts') or []
        diagonal_cover = doc.get('diagonalCover')
        doc, break_originals, hides = doc.get('copies') or [], doc.get('breakOriginals') or [], doc.get('hides') or []
    for c in doc:
        copies.append(copy_record(c))
    return BuildState(src, out, variant, copies, break_originals=break_originals, hides=hides, assemblies=assemblies,
                      lights=lights, covers=covers, buildings=buildings, building_edits=edits, cleared=cleared,
                      landing_zones=landing_zones, carried_effects=carried_effects, stream_tiles=stream_tiles,
                      piece_flags=piece_flags, flag_ladders=flag_ladders, effects=effects, sounds=sounds, flares=flares,
                      spawns=spawns, background_sound=background_sound, piece_blasts=piece_blasts,
                      diagonal_cover=diagonal_cover, **options)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('variant')
    a.add_argument('--copy', action='append', nargs='+', default=[], metavar='ACTOR X Y Z [YAW]',
                   help='a piece to copy and where (yaw in rotator units, 65536 a turn; default the original\'s); '
                        'repeat for more copies')
    a.add_argument('--actor', help='one piece to copy, as XComLevelActor_37 (with --at and --yaw)')
    a.add_argument('--at', nargs=3, type=float, metavar=('X', 'Y', 'Z'))
    a.add_argument('--yaw', type=int, help='rotator units (65536 a turn); default: the original\'s')
    a.add_argument('--copies', type=Path, metavar='FILE',
                   help='a JSON list of copies, each {"actor", "location": [x, y, z], "rotation": [pitch, yaw, roll], '
                        '"breakGroup": n}, or {"copies": [...], "breakOriginals": [{"name", "group"}], "hides": '
                        '[{"name", "box"}], "lights": {"deletes", "changes", "adds", "area"}, "covers": [{"name", '
                        '"kind", "location", "rotation", "size", "heights", "box"}], "buildings": [{"id", "name", "kind", "floors": '
                        '[{"boxes"}]}], "pieceFlags": [{"name", "flags"}], "pieceFlagLadders": [{"actor", "foot", '
                        '"top"}]} with a copy\'s "flags" {role: bool} (the editor\'s Build writes it; lights: editor '
                        'lights plan 9.5; covers: cover_blocks.py; flags: piece flags plan)')
    a.add_argument('--no-tiles', action='store_true', help='leave the copies out of the tiles (no seeds or rebuild)')
    a.add_argument('--bake', action='store_true', help='give the copies their own lighting (relight.py --native-copy)')
    a.add_argument('--cache', help='with --bake: the variant texture cache\'s name (the Build\'s <Map>_Lighting; added to '
                                   'the grown map\'s name table), or <Name>_<n> with <Name> in the map\'s')
    a.add_argument('--receivers-near', type=float, default=600.0,
                   help='with --bake: relight the receivers within this many units of a copy (default %(default)s)')
    a.add_argument('--jobs', type=int, help='with --bake: relight worker processes')
    a.add_argument('--edit-spec', type=Path,
                   help='with --bake: an editor patch spec whose hides the relight models too (relight.py --edit-spec)')
    a.add_argument('--piece-cache', type=Path, metavar='DIR',
                   help="with --bake: keep the relit pieces in DIR for the project's next build (relight.py "
                        '--piece-cache; needs --base)')
    a.add_argument('--base', metavar='SHA', help='with --piece-cache: the SHA-256 of the map before any of the edit')
    args = a.parse_args()
    doc = json.loads(args.copies.read_text(encoding='utf-8')) if args.copies else []
    st = edit_state(args.src, args.out, args.variant, doc, bake=args.bake, cache=args.cache,
                    receivers_near=args.receivers_near, jobs=args.jobs, tiles=not args.no_tiles,
                    edit_spec=args.edit_spec, piece_cache=args.piece_cache, base=args.base)
    for item in args.copy:
        if len(item) not in (4, 5):
            a.error(f'--copy takes ACTOR X Y Z [YAW], not {item}')
        st.copies.append(copy_record(dict(actor=item[0], location=item[1:4],
                                          yaw=int(item[4]) if len(item) == 5 else None)))
    if args.actor:
        if not args.at:
            a.error('--actor needs --at')
        st.copies.append(copy_record(dict(actor=args.actor, location=args.at, yaw=args.yaw)))
    import native_lights
    if not st.copies and not st.hides and not st.covers and not st.buildings and not st.building_edits \
            and not st.cleared and not st.landing_zones and not st.stream_tiles and not st.piece_flags \
            and native_lights.is_empty(st.lights) and not st.effects and not st.sounds and not st.flares \
            and not st.spawns and not st.background_sound and not st.piece_blasts \
            and not ((st.diagonal_cover or {}).get('marks') or (st.diagonal_cover or {}).get('removed')):
        a.error('give --copy, --copies (or --actor with --at)')
    if args.edit_spec and not args.bake:
        a.error('--edit-spec needs --bake')
    m = build(st)
    # one line per copy; the whole record is the manifest's nativeCopies section
    for c in m['nativeCopies']['copies']:
        t = c['tiles']
        print(f"{c['actor']} -> {c['copy'].split('.')[-1]} at {[round(v, 1) for v in c['location']]} {c['rotation']}: "
              f"{len(c['exports'])} exports, {len(c['textures'])} lighting textures"
              + (f", tiles {t['tiles']} ({t['seeded']} seeded, {t['alreadyMarked']} already marked), rebuild volume "
                 f"{t['volume']['export']}{diagonal_words(t['volume'])}" if t
                 else ', tiles with its assembly' if c.get('assembly') else ', no tiles')
              + (f" (a {c['family']}, {c['assembly']})" if c.get('assembly') else '')
              + (f"; its {c['columns']['columns']} columns moved with it, {c['columns']['dropped']} entries of other "
                 f"pieces dropped" + (f", {c['columns']['carried']} now naming the copies made with it"
                                      if c['columns'].get('carried') else '')
                 + (f", {c['columns']['neighbours']['dropped']} neighbouring columns dropped"
                    + (f" and {c['columns']['neighbours']['kept']} kept" if c['columns']['neighbours']['kept'] else '')
                    if c['columns'].get('neighbours') else '') if c.get('columns') else ''))
    for c in m['nativeCopies']['coverBlocks']:
        t = c['tiles']
        print(f"{'invisible floor' if c['kind'] == 'floor' else 'cover block'} {c['name']} ({c['kind']}) -> "
              f"{c['copy'].split('.')[-1]}" + (f" and {len(c['cells']) - 1} more" if len(c.get('cells', [])) > 1 else '')
              + " at "
              f"{[round(v, 1) for v in c['location']]} {c['rotation']}: "
              + (f"tiles {t['tiles']} ({t['seeded']} seeded, {t['alreadyMarked']} already marked), rebuild volume "
                 f"{t['volume']['export']}{diagonal_words(t['volume'])}" if t
                 else 'outside the map\'s tiles, no rebuild volume'))
    for h in m['nativeCopies']['hidden']:
        print(f"hidden {h['name']}: out of the Level's list, "
              + (f"tiles {h['tiles']} rebuilt by volume {h['volume']['export']}{diagonal_words(h['volume'])}" if h['volume']
                 else 'outside the map\'s tiles, no rebuild volume')
              + (f", unlinked from {', '.join(h['unlinkedFrom'])}" if h['unlinkedFrom'] else ''))
    whole = (m['nativeCopies'].get('diagonalCover') or {}).get('whole', [])
    corners = [r['tile'] for r in whole if r.get('newCorner')]
    marks = [r for r in whole if r.get('mark')]
    removed = [r['tile'] for r in whole if r.get('removed')]
    refitted = (m['nativeCopies'].get('diagonalCover') or {}).get('refitted') or []
    if corners:
        print(f"diagonal cover carried to new slanted corners: tiles {', '.join(str(tuple(t)) for t in corners)}")
    if marks:
        print("diagonal cover marked by the project: " + '; '.join(
            f"tile {tuple(r['tile'])} toward {', '.join(str(tuple(c)) for c in r['mark'])}"
            + (f" (no wall toward {', '.join(str(tuple(c)) for c in r['noWall'])})" if r.get('noWall') else '')
            + (' (no floor of its own)' if r.get('noFloor') else '') for r in marks))
    if removed:
        print(f"diagonal cover taken away by the project: tiles {', '.join(str(tuple(t)) for t in removed)}")
    if refitted:
        print(f"rebuild volumes refitted round them: {', '.join(r['volume'] + ' into ' + str(r['into']) for r in refitted)}")
    for key in ('effects', 'sounds', 'flares', 'spawns'):
        for r in m['nativeCopies'].get(key) or []:
            print(f"{key[:-1]} {r['actor']} {r['how']}" + (f" from {r['source']} -> {r['copy']}" if r['how'] == 'copied' else '')
                  + (f" at {[round(v, 1) for v in r['location']]} {r['rotation']}" if 'location' in r else '')
                  + (f" values {r['values']}" if r.get('values') else ''))
    for f in m['nativeCopies'].get('floorEmitters') or []:
        print(f"effect {f['effect']} {f['how']} floor {f['floor']} of {f['building']}")
    for r in m['nativeCopies'].get('carriedEffects') or []:
        print(f"effect {r['effect']} ({r['template']}) {r['how']} with {r['piece']}"
              + (f" -> {r['copy']}" if r.get('copy') else '')
              + (f" at {[round(v, 1) for v in r['location']]} {r['rotation']}" if r['how'] != 'deleted' else ''))
    flagged = m['nativeCopies'].get('pieceFlags')
    for rec in (flagged or {}).get('onCopies') or []:
        print(f"flags of copy {rec['copy']} ({rec['label']}): {flags_summary(rec)}")
    for rec in (flagged or {}).get('inPlace') or []:
        print(f"flags in place: {flags_summary(rec)}" + (f" ({rec['tileWork']})" if rec.get('tileWork') else ''))
    if flagged and flagged.get('tiles'):
        t = flagged['tiles']
        print(f"flags' tiles: {len(t['regions'])} region{'s' if len(t['regions']) != 1 else ''}"
              + (' (joined)' if t['joined'] else '') + f", {t['seeded']} seeded, {t['alreadyMarked']} already marked"
              + (f", outside the map's tiles: {', '.join(t['outside'])}" if t['outside'] else '')
              + f"; rebuild volumes: {t['volumes']}")
    broken = m['nativeCopies'].get('pieceBlasts')
    for how, rec in [('copy', r) for r in (broken or {}).get('onCopies') or []] + [
            ('in place', r) for r in (broken or {}).get('inPlace') or []]:
        print(f"broken ({how}) {rec['label']}: {rec['knocked']} of its {rec['fragments']} fragments knocked out by its blasts, "
              f"{rec['hidden']} painted out in all" + ('; bPreventChunkRemoval turned off' if rec.get('chunksLet') else
                                                       f"; kept whole in battle, drawing {rec['keptWhole']} (the hole cut "
                                                       f"into a copy of its mesh)" if rec.get('keptWhole') else ''))
    if broken and broken.get('tiles'):
        t = broken['tiles']
        print(f"broken pieces' tiles: {len(t['regions'])} region{'s' if len(t['regions']) != 1 else ''}"
              + (' (joined)' if t['joined'] else '') + f", {t['seeded']} seeded, {t['alreadyMarked']} already marked"
              + (f", outside the map's tiles: {', '.join(t['outside'])}" if t['outside'] else '')
              + f"; rebuild volumes: {t['volumes']}")
    for l in m['nativeCopies']['ladders']:
        print(f"ladder {l['copy']}: foot {l['foot']} rebuilt at place {l['footPlace']}, top {l['top']} at "
              f"{l['topPlace']} (volume {l['topVolume']['export']} first)")
    for piece, change in m['nativeCopies']['columns'].items():
        print(f"{piece}'s columns: {change['dropped']} entries of hidden pieces dropped"
              + (f", {change['neighboursDropped']} of hidden pieces' columns beside them"
                 if change.get('neighboursDropped') else '')
              + (f", {len(change['added'])} added for {', '.join(sorted({a['copy'] for a in change['added']}))}'s copies"
                 if change['added'] else ''))
    for f in m['nativeCopies']['floorCaches']:
        print(f"{f['copy']}'s copy: " + ('in no building floor' if f.get('outside') else
                                         f"in {f['building']}, edited in place (its lists carried)" if f.get('edited') else
                                         f"in {f['building']}'s floor {f['floor']} cutaway"))
    for v in m['nativeCopies']['vans']:
        b = v['building']
        print(f"{v['assembly']}: building {b['original']} -> {b['copy'].split('.')[-1]} at "
              f"{[round(x, 1) for x in b['location']]} {b['rotation']}, floor volumes "
              + ', '.join(f"{f['original']} -> {f['copy'].split('.')[-1]}" for f in v['floorVolumes'])
              + (f"; residents not of the van dropped: {', '.join(v['dropped'])}" if v['dropped'] else '')
              + (f"; its external mesh groups list {', '.join(v['outside'])} outside it" if v['outside'] else ''))
    for h in m['nativeCopies']['hiddenBuildings']:
        print(f"hidden building {h['building']} with floor volumes {', '.join(h['volumes'])}")
    for b in m['nativeCopies']['buildings']:
        print(f"building {b['name'] or b['id']} ({b['kind']}) -> {b['copy']}: " + '; '.join(
            f"floor {k}: {', '.join(f['volumes'])}, {len(f['members'])} pieces"
            + (f" ({sum(1 for x in f['members'] if x['cutdown'])} cut down)" if any(x['cutdown'] for x in f['members']) else '')
            for k, f in enumerate(b['floors']))
              + (f"; no box read for {', '.join(b['unread'])}" if b['unread'] else ''))
    for e in m['nativeCopies']['buildingEdits']:
        if e['deleted']:
            print(f"building {e['actor']} deleted: it and its floor volumes {', '.join(e['volumes'])} out of the level")
            continue
        v = e['volumes']
        print(f"building {e['actor']} edited in place{' (moved whole)' if e['moved'] else ''}: volumes "
              + ', '.join(f"{len(v[k])} {k}" for k in ('kept', 'moved', 'stretched', 'replaced', 'made', 'removed') if v[k])
              + f"; pieces: {e['pieces']['kept']} keep the map's listing, {e['pieces']['rule']} listed by the rule"
              + (f", {e['pieces']['unread']} with no box kept as saved" if e['pieces']['unread'] else '')
              + (f"; emitters dropped: {', '.join(e['emittersDropped'])}" if e['emittersDropped'] else '')
              + ('; visibility groups emptied' if e['visGroupsEmptied'] else '')
              + (f"; mesh groups point at the copies of {', '.join(e['meshGroupsRepointed'])}" if e['meshGroupsRepointed'] else ''))
    for number, names in m['nativeCopies']['breakGroups'].items():
        print(f'break group {number}: {", ".join(names)} (each lists the others in AffectedChildren; a cover block '
              'is listed and lists none)')
    lit = m.get('lights')
    for e in (lit or {}).get('edits', []):
        print(f"light {e['op']} {e['name']}" + (f" -> {e['actor'].split('.')[-1]}" if e['op'] in ('add', 'area-copy')
                                                else '')
              + (f": wrote {', '.join(e['written'])}" if e['written'] else '')
              + (f"; tags added {', '.join(e['tagsAdded'])}" if e['tagsAdded'] else ''))
    if lit:
        print(f"lights ({lit['policy']}): listed in {len(lit['registered'])} receivers' lightmaps"
              + (f", {len(lit['unregistered'])} in reach without a texture lightmap" if lit['unregistered'] else ''))
    print(f"manifest: {Path(args.out) / (args.variant + '.fixture.json')}")


if __name__ == '__main__':
    main()
