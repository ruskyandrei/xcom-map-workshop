"""Light edits made in the map (editor lights plan, private/plans/done/editor-lights-plan.md, 4.3 and 4.8; the native edit's
`lights`, plan 9.5), used by native_copy.build().

The pristine source is read once (`prepare`): every point and spot light of the persistent level becomes a registry
entry with its stored raw values (plan 9.1: colour bytes, brightness, radius, falloff, cone angles as stored, on/off,
place and rotation), its two GUIDs and its scale. The edit is resolved against those entries into explicit before and
after registries, keyed by the light's short name: deletes are absent from after, additions from before, a changed
light is a new entry in after with the same GUIDs. New lights get deterministic GUIDs from their `guidSeed`
(`light_guids`). Normalized codec lights (lightmap_encode's dicts, as relight.map_lights gives them) are derived from
the raw values when needed (`codec_light`), never written back over them.

`apply` makes the actor and component changes in the growing package `g` (package_grow.Grower), reading the source `p`
only for offsets and templates:
- a delete takes the actor out of the Level's actor list (the caller empties its slot); its GUIDs stay in the
  lightmaps that list them, which is harmless (plan 2.6);
- a change writes only the properties its `set` names (`set_property`: a value the component doesn't save gains its
  tag before the closing None), the actor's Location and Rotation when they changed, and CachedParentToWorld for the
  new pose (`parent_to_world`); the GUIDs are kept;
- an add copies a light of the map (`native_copy.clone_assembly`: a light actor's subtree is the actor and its one
  component) with fresh GUIDs, its values and its pose, or constructs a spot by the built-in recipe
  (light_factory.add_spot, plan 9.6); a light gets no tiles;
- generated area lights (GeneratedMeshAreaLight) are moved, copied or deleted with their glowing piece's derived pose,
  keeping their class, flags, archetype and WorldInfo owner, and never join a receiver's lightmap list.

`Registrar` and `register` are for baked builds only: each added or changed placed light that emits is listed in the
texture lightmaps of the receivers its radius sphere meets at their final poses (conservative membership, not the
brightness cutoff of native_copy.EXTRA_LIGHT_MIN), so the game doesn't light it live on top of the bake (plan 2.6).
Splices are merged per component and made on the writer's current bytes. Unbaked builds leave every receiver list as
it is and add no GUID to any. `relight_edits` gives the relight (relight.py --light-edits) the resolved before and
after codec lights, and `record` the fixture manifest's `lights` section.
"""
import hashlib
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import props as legacy_props  # noqa: E402
from export_math import forward, transform  # noqa: E402
from lights import light_record  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
GUID_KEYS = ('LightGuid', 'LightmapGuid')
# plan 9.1: the editable values, by the component property each is stored in
PROPERTIES = dict(color=('LightColor', 'StructProperty', 'Color'), brightness=('Brightness', 'FloatProperty', None),
                  radius=('Radius', 'FloatProperty', None), falloffExponent=('FalloffExponent', 'FloatProperty', None),
                  innerConeAngle=('InnerConeAngle', 'FloatProperty', None),
                  outerConeAngle=('OuterConeAngle', 'FloatProperty', None), enabled=('bEnabled', 'BoolProperty', None))
VALUE_KEYS = tuple(PROPERTIES)
CONE_KEYS = ('innerConeAngle', 'outerConeAngle')
LIGHT_COMPONENTS = {'PointLightComponent': 'point', 'SpotLightComponent': 'spot'}
UDK_POINT_SOURCE_RADIUS = 100.0       # lightmap_encode's: LightmassPointLightSettings default in UDK's Engine.u
# how far a place may move before it counts as moved (the editor's JSON against the package's float32 values)
PLACE_TOLERANCE = 1e-3


def keys_for(kind):
    return VALUE_KEYS if kind == 'spot' else tuple(k for k in VALUE_KEYS if k not in CONE_KEYS)


# ---------------------------------------------------------------- the property writer

def set_property(walker, g, data, start, name, kind, struct_name, raw):
    """`data` (an export's bytes, tagged properties from `start`; a bytearray is changed in place) with the property
    `name` (array index 0) set to the value bytes `raw`: in place when the export saves it (its tag's size follows the
    value's own size), else added before the closing None (the export then grows; nothing in an export's data points
    past its properties). `kind` is the property type (FloatProperty, StructProperty, BoolProperty...), `struct_name`
    a struct's name (Vector, Rotator, Color, Matrix, Guid) or a byte property's enum, else None. A BoolProperty's tag
    saves size 0 and its value as one byte, as the Walker and the package reader read it. Returns the bytes."""
    if not isinstance(data, bytearray):
        data = bytearray(data)
    raw = bytes(raw)
    if kind == 'BoolProperty' and len(raw) != 1:
        raise ValueError(f'{name}: a bool property holds one byte, not {len(raw)}')
    named = kind in ('StructProperty', 'ByteProperty')
    if named and not struct_name:
        raise ValueError(f'{name}: a {kind} needs its struct or enum name')
    gen = walker.walk(bytes(data), start, len(data))
    try:
        while True:
            prop, found, sub, at, size = next(gen)
            if prop != f'{name}[0]':
                continue
            if found != kind or (named and sub != struct_name):
                raise ValueError(f'{name} is saved as a {found}{" " + sub if sub else ""}, not a {kind}'
                                 f'{" " + struct_name if named else ""}')
            if size != len(raw):        # a bool's tag says 0 and its value is one byte: never here
                struct.pack_into('<i', data, at - 8 - (8 if named else 0), len(raw))
            data[at:at + size] = raw
            return data
    except StopIteration as done:
        end = done.value
    tag = struct.pack('<iiiiii', g.name(name), 0, g.name(kind), 0, 0 if kind == 'BoolProperty' else len(raw), 0)
    if named:
        tag += struct.pack('<ii', g.name(struct_name), 0)
    data[end - 8:end - 8] = tag + raw
    return data


def saves(walker, data, start, name):
    """Whether the export bytes save the property `name` (index 0)."""
    return walker.value(bytes(data), start, len(data), f'{name}[0]') is not None


def put(walker, g, data, start, name, kind, struct_name, raw, added, written):
    """set_property, noting the property in `written` and, when its tag is new, in `added`."""
    if not saves(walker, data, start, name):
        added.append(name)
    written.append(name)
    return set_property(walker, g, data, start, name, kind, struct_name, raw)


def value_bytes(key, value, alpha=255):
    """(property, kind, struct name, value bytes) of a plan 9.1 value: LightColor as B G R A (the alpha the
    component's own), floats as 4 bytes, bEnabled as one byte."""
    prop, kind, sub = PROPERTIES[key]
    if key == 'color':
        r, g, b = (int(v) for v in value)
        return prop, kind, sub, bytes([b, g, r, int(alpha)])
    if key == 'enabled':
        return prop, kind, sub, bytes([1 if value else 0])
    return prop, kind, sub, struct.pack('<f', float(value))


def parent_to_world(location, rotation, scale=(1.0, 1.0, 1.0)):
    """A light component's CachedParentToWorld for its actor at `location`, `rotation` and `scale`: the actor's
    local-to-world matrix, 64 bytes. Read on Bar, Police Station and Temple (all 1,683 point, spot and generated
    lights): rows are the X, Y and Z axes (scaled by the actor's DrawScale3D) and the origin, each saved W first
    (0 for an axis, 1 for the origin), then X, Y, Z."""
    m = transform(location, rotation, scale)
    rows = []
    for j in range(3):
        rows += [0.0, m[0][j], m[1][j], m[2][j]]
    rows += [1.0] + [float(v) for v in location]
    return struct.pack('<16f', *rows)


def light_guids(seed):
    """A new light's {LightGuid, LightmapGuid} from its guidSeed (plan 9.5): the first 16 bytes of
    sha256(guidSeed + '|LightGuid') and of sha256(guidSeed + '|LightmapGuid')."""
    if not isinstance(seed, str) or not seed:
        raise ValueError('a new light needs its guidSeed')
    return {k: hashlib.sha256((seed + '|' + k).encode()).digest()[:16] for k in GUID_KEYS}


def props_start(p, index):
    """Where an export's tagged properties start in its data (as the source has it)."""
    e = p.exports[index - 1]
    return legacy_props.props_start(p.data, e, p.names) - e['off']


# ---------------------------------------------------------------- the registries

def short(path):
    return path[len(PL):] if path and path.startswith(PL) else path


def lightmass_source_radius(p, component):
    """The light component's LightmassSettings LightSourceRadius, or UDK's default (relight.lightmass_settings)."""
    import relight
    return float(relight.lightmass_settings(p, component).get('LightSourceRadius', UDK_POINT_SOURCE_RADIUS))


def raw_values(p, actor):
    """(light_record, the raw values plan 9.1 names plus location and rotation) of a light actor of the source: what
    the package stores, with the UDK class defaults (lights.py) for what it doesn't."""
    rec = light_record(p, actor)
    raw = dict(color=[int(round(v * 255)) for v in rec['color']], brightness=float(rec['brightness']),
               radius=float(rec['radius']), falloffExponent=float(rec['falloffExponent']), enabled=bool(rec['enabled']))
    if rec['kind'] == 'spot':
        raw.update(innerConeAngle=float(rec['innerConeAngle']), outerConeAngle=float(rec['outerConeAngle']))
    raw.update(location=[float(v) for v in rec['location']], rotation=[int(v) for v in rec['rotation']])
    return rec, raw


def source_entry(p, actor):
    """A light of the source as a registry entry: id (its short name), actor and component paths and export indices,
    kind, role, actor class, guids ({LightGuid, LightmapGuid}: 16 bytes each), raw values, the alpha byte of its
    LightColor, its actor's scale and its Lightmass source radius."""
    rec, raw = raw_values(p, actor)
    ci = p.by_name[rec['component']]
    guids = {}
    for k in GUID_KEYS:
        v = p.effective(ci, k)
        if isinstance(v, (bytes, bytearray)) and len(v) == 16:
            guids[k] = bytes(v)
    own = p.own(ci, 'LightColor')
    s = p.own(actor, 'DrawScale', 1.0)
    return dict(id=short(rec['actor']), actor=rec['actor'], component=rec['component'], actorIndex=actor,
                componentIndex=ci, kind=rec['kind'], role=rec['role'], actorClass=rec['actorClass'], guids=guids,
                raw=raw, alpha=int(round(own[3] * 255)) if own else 255,
                scale=[v * s for v in p.own(actor, 'DrawScale3D', [1.0, 1.0, 1.0])],
                lightSourceRadius=lightmass_source_radius(p, ci))


def source_registry(p):
    """Every point and spot light of the persistent level (placed, generated area and toggleable alike) as a registry
    entry, by its short name, in export order."""
    out = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in LIGHT_COMPONENTS or not p.name(i).startswith(PL):
            continue
        actor = p.exports[i - 1]['outer']
        try:
            rec = light_record(p, actor)
        except ValueError:
            continue
        if rec is None or rec['component'] != p.name(i):
            continue
        entry = source_entry(p, actor)
        out[entry['id']] = entry
    return out


def codec_light(entry, raw=None):
    """The codec light (lightmap_encode's dict, the shape relight.map_lights gives) of a registry entry: colour as
    0-1 values, the spot's direction from its rotation, cone angles as stored (the codec takes the effective cone,
    lights.effective_cone), and `guids` (its LightmapGuid and LightGuid, hex) for the relight's registries."""
    raw = entry['raw'] if raw is None else raw
    hexes = [entry['guids'][k].hex() for k in ('LightmapGuid', 'LightGuid') if k in entry['guids']]
    d = dict(kind=entry['kind'], actor=entry.get('actor'), component=entry.get('component'),
             brightness=float(raw['brightness']), color=[c / 255 for c in raw['color']], enabled=bool(raw['enabled']),
             role=entry['role'], guid=sorted(hexes)[0] if hexes else None, guids=hexes,
             location=[float(v) for v in raw['location']], radius=float(raw['radius']),
             falloffExponent=float(raw['falloffExponent']), lightSourceRadius=float(entry['lightSourceRadius']))
    if entry['kind'] == 'spot':
        d.update(direction=forward(raw['rotation']), innerConeAngle=float(raw['innerConeAngle']),
                 outerConeAngle=float(raw['outerConeAngle']))
    return d


def emits(raw):
    """Whether light with these raw values puts any light down: on, and brighter than 0."""
    return bool(raw['enabled']) and float(raw['brightness']) > 0


def reach_box(raw):
    """The light's radius around its place, [x0, x1, y0, y1, z0, z1]."""
    r = float(raw['radius'])
    return [v for c in raw['location'] for v in (float(c) - r, float(c) + r)]


def checked_values(given, kind, what, complete=False):
    """Plan 9.1 values from the edit, checked: known keys, no cone on a point light, colour three integer bytes,
    `enabled` a bool, the rest finite numbers. (The compiler checks ranges of authored values; inherited stored
    values, such as a 580-degree cone, are kept as they are.)"""
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise ValueError(f'{what}: light values must be an object')
    out = {}
    for k, v in given.items():
        if k not in VALUE_KEYS:
            raise ValueError(f'{what}: unknown light value {k}')
        if k in CONE_KEYS and kind != 'spot':
            raise ValueError(f'{what}: a {kind} light has no {k}')
        if k == 'color':
            if (not isinstance(v, (list, tuple)) or len(v) != 3
                    or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in v)):
                raise ValueError(f'{what}: color must be three integer bytes 0-255, not {v!r}')
            out[k] = [int(c) for c in v]
        elif k == 'enabled':
            if not isinstance(v, bool):
                raise ValueError(f'{what}: enabled must be true or false, not {v!r}')
            out[k] = v
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f'{what}: {k} must be a finite number, not {v!r}')
            out[k] = float(v)
    if complete:
        missing = [k for k in keys_for(kind) if k not in out]
        if missing:
            raise ValueError(f'{what}: the light lacks {", ".join(missing)}')
    return out


def checked_pose(value, what, rotator=False):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)):
        raise ValueError(f'{what} must be three finite numbers, not {value!r}')
    return [int(round(v)) for v in value] if rotator else [float(v) for v in value]


def same_value(a, b, key):
    if key == 'color':
        return [int(v) for v in a] == [int(v) for v in b]
    if key == 'enabled':
        return bool(a) == bool(b)
    if key == 'rotation':
        return [int(v) for v in a] == [int(v) for v in b]
    if key == 'location':
        return all(abs(float(x) - float(y)) <= 0.01 + 1e-6 * abs(float(y)) for x, y in zip(a, b))
    return abs(float(a) - float(b)) <= 1e-4 * max(1.0, abs(float(b)))


def check_matches(what, given, raw, keys=None):
    """`given` (values the edit says a light has) against `raw` (what the writer resolved): ValueError on a
    difference beyond float32 rounding."""
    if given is None:
        return
    for k, v in given.items():
        if keys is not None and k not in keys:
            continue
        if k not in raw:
            raise ValueError(f'{what}: {k} is not a value of this light')
        if not same_value(v, raw[k], k):
            raise ValueError(f'{what}: {k} is {raw[k]!r} in the map, the edit says {v!r}')


def moved(before, after):
    """(location changed, rotation changed) between two raw value sets."""
    loc = any(abs(float(a) - float(b)) > PLACE_TOLERANCE for a, b in zip(before['location'], after['location']))
    return loc, [int(v) for v in before['rotation']] != [int(v) for v in after['rotation']]


def prepare(p, edit):
    """The native edit's `lights` (plan 9.5) resolved against the pristine source `p`: dict(before, after: {id:
    entry}, ops: [resolved op], guids: {new light id: {LightGuid, LightmapGuid}}). Each op is dict(op: delete,
    change, add, area-move, area-copy or area-delete; name, label, kind, role; before and after: registry entries or
    None; set (a change's values to write), template (a copy's source entry), recipe (a recipe spot's version),
    owner, ownerEntity (area)). Raises ValueError on a light the map lacks, an op on a light of the wrong role, a
    change whose `before` or `light` disagrees with the map, a second op on one light, or colliding GUIDs."""
    edit = edit or {}
    registry = source_registry(p)
    staged = set(edit.get('stagedAreas') or [])
    if staged:
        from native_copy import level_actors
        listed = set(level_actors(p))
        if any(n not in registry or registry[n]['role'] != 'area' or registry[n]['actorIndex'] in listed for n in staged):
            raise ValueError('staged area templates must be generated area lights outside the level actor list')
    before = {name: entry for name, entry in registry.items() if name not in staged}
    after = dict(before)
    used = {g for e in registry.values() for g in e['guids'].values()}
    ops, touched, names = [], set(), set()

    def light(name, role, what):
        e = before.get(name)
        if e is None:
            raise ValueError(f'{what}: no light {name} in the map\'s persistent level')
        if (e['role'] == 'area') != (role == 'area'):
            raise ValueError(f'{what}: {name} is a {e["role"]} light, not a{"n area" if role == "area" else " placed"} '
                             'light')
        if role != 'area' and e['role'] != 'static':
            raise ValueError(f'{what}: {name} is a {e["role"]} light, which light edits leave as it is')
        return e

    def once(name, what):
        if name in touched:
            raise ValueError(f'{what}: {name} has more than one edit')
        touched.add(name)

    def fresh(seed, name, what):
        guids = light_guids(seed)
        if set(guids.values()) & used:
            raise ValueError(f'{what}: the GUIDs of {name} collide with another light\'s')
        used.update(guids.values())
        return guids

    def new_name(name, what):
        if not isinstance(name, str) or not name:
            raise ValueError(f'{what}: a new light needs its output name')
        if name in after or name in names or name in before:
            raise ValueError(f'{what}: the output name {name} is taken')
        names.add(name)

    for d in edit.get('deletes') or []:
        what = f"delete {d.get('name')}"
        e = light(d.get('name'), 'static', what)
        if d.get('kind') and d['kind'] != e['kind']:
            raise ValueError(f'{what}: it is a {e["kind"]} light, not a {d["kind"]} light')
        once(e['id'], what)
        after.pop(e['id'])
        ops.append(dict(op='delete', name=e['id'], label=d.get('label'), kind=e['kind'], role=e['role'], before=e,
                        after=None))
    for c in edit.get('changes') or []:
        what = f"change {c.get('name')}"
        e = light(c.get('name'), 'static', what)
        if c.get('kind') and c['kind'] != e['kind']:
            raise ValueError(f'{what}: it is a {e["kind"]} light, not a {c["kind"]} light')
        once(e['id'], what)
        check_matches(what + ' (before)', c.get('before'), e['raw'])
        values = checked_values(c.get('set'), e['kind'], what)
        raw = dict(e['raw'], **values)
        raw['location'] = checked_pose(c['location'], what + ' location') if c.get('location') is not None \
            else list(e['raw']['location'])
        raw['rotation'] = checked_pose(c['rotation'], what + ' rotation', True) if c.get('rotation') is not None \
            else list(e['raw']['rotation'])
        check_matches(what + ' (light)', c.get('light'), raw, keys_for(e['kind']))
        a = dict(e, raw=raw)
        after[e['id']] = a
        ops.append(dict(op='change', name=e['id'], label=c.get('label'), kind=e['kind'], role=e['role'], before=e,
                        after=a, set=values))
    for d in edit.get('adds') or []:
        what = f"add {d.get('name')}"
        if ('from' in d) == ('template' in d):
            raise ValueError(f'{what}: an added light names either a template light (from) or a recipe (template)')
        new_name(d.get('name'), what)
        location = checked_pose(d.get('location'), what + ' location')
        rotation = checked_pose(d.get('rotation'), what + ' rotation', True)
        guids = fresh(d.get('guidSeed'), d['name'], what)
        if d.get('role', 'static') != 'static':
            raise ValueError(f'{what}: an added light is a placed (static) light')
        if 'from' in d:
            t = light(d['from'], 'static', what)
            if d.get('kind') and d['kind'] != t['kind']:
                raise ValueError(f'{what}: its template {t["id"]} is a {t["kind"]} light, not a {d["kind"]} light')
            raw = dict(t['raw'], **checked_values(d.get('light'), t['kind'], what), location=location,
                       rotation=rotation)
            a = dict(t, id=d['name'], actor=None, component=None, actorIndex=None, componentIndex=None, guids=guids,
                     raw=raw)
            ops.append(dict(op='add', name=d['name'], label=d.get('label') or d['name'], kind=t['kind'],
                            role='static', before=None, after=a, template=t))
        else:
            recipe = d['template']
            made = recipe.get('kind') if isinstance(recipe, dict) else None
            if made not in RECIPE_CLASSES:
                raise ValueError(f'{what}: the built-in recipes make spot and point lights only, not {recipe!r}')
            version = recipe.get('version')
            if isinstance(version, bool) or not isinstance(version, int):
                raise ValueError(f'{what}: the recipe needs a whole version number')
            if d.get('kind') not in (None, made):
                raise ValueError(f'{what}: the recipe makes a {made} light, not a {d["kind"]} light')
            raw = dict(checked_values(d.get('light'), made, what, complete=True), location=location,
                       rotation=rotation)
            a = dict(id=d['name'], actor=None, component=None, actorIndex=None, componentIndex=None, kind=made,
                     role='static', actorClass=RECIPE_CLASSES[made], guids=guids, raw=raw, alpha=255, scale=[1.0, 1.0, 1.0],
                     lightSourceRadius=recipe_source_radius(version, made))
            ops.append(dict(op='add', name=d['name'], label=d.get('label') or d['name'], kind=made, role='static',
                            before=None, after=a, recipe=version))
        after[d['name']] = a
    for d in edit.get('area') or []:
        op = d.get('op')
        what = f"area {op} {d.get('light')}"
        if op not in ('move', 'copy', 'delete'):
            raise ValueError(f'{what}: an area light is moved, copied or deleted, not {op!r}')
        name = d.get('light')
        if name in staged:
            if op != 'copy':
                raise ValueError(f'{what}: a staged area light is a template for copying')
            e = registry[name]
        else:
            e = light(name, 'area', what)
        common = dict(kind=e['kind'], role='area', owner=d.get('owner'), ownerEntity=d.get('ownerEntity'))
        if op == 'delete':
            once(e['id'], what)
            after.pop(e['id'])
            ops.append(dict(common, op='area-delete', name=e['id'], label=d.get('label'), before=e, after=None))
            continue
        location = checked_pose(d.get('location'), what + ' location')
        rotation = checked_pose(d.get('rotation'), what + ' rotation', True)
        raw = dict(e['raw'], location=location, rotation=rotation)
        if op == 'move':
            once(e['id'], what)
            a = dict(e, raw=raw)
            after[e['id']] = a
            ops.append(dict(common, op='area-move', name=e['id'], label=d.get('label'), before=e, after=a))
        else:
            new_name(d.get('name'), what)
            a = dict(e, id=d['name'], actor=None, component=None, actorIndex=None, componentIndex=None,
                     guids=fresh(d.get('guidSeed'), d['name'], what), raw=raw)
            after[d['name']] = a
            ops.append(dict(common, op='area-copy', name=d['name'], label=d.get('label') or d['name'], before=None,
                            after=a, template=e))
    return dict(before=before, after=after, ops=ops, stagedAreas=sorted(registry[n]['component'] for n in staged))


# the lights the built-in recipes make (light_factory.py), by kind: the actor's class
RECIPE_CLASSES = {'spot': 'SpotLight', 'point': 'PointLight'}


def recipe_source_radius(version, kind='spot'):
    """The Lightmass source radius a recipe light is made with, which the relight must bake it with: the one its
    recipe's component saves (LightmassSettings' LightSourceRadius; F-91), else UDK's default."""
    try:
        import light_factory
    except ImportError:
        return UDK_POINT_SOURCE_RADIUS
    recipe = getattr(light_factory, 'RECIPES' if kind == 'spot' else 'POINT_RECIPES', {}).get(version) or {}
    for key in ('lightSourceRadius', 'LightSourceRadius'):
        if isinstance(recipe.get(key), (int, float)):
            return float(recipe[key])
    lightmass = recipe.get('lightmass') or recipe.get('LightmassSettings') or {}
    value = lightmass.get('LightSourceRadius') if isinstance(lightmass, dict) else None
    if not isinstance(value, (int, float)):
        # the factory's recipes: the component's properties, [name, kind, value], the struct's own a list of such
        for name, _, saved in (recipe.get('component') or {}).get('properties') or []:
            if name == 'LightmassSettings' and isinstance(saved, list):
                value = next((v for n, _, v in saved if n == 'LightSourceRadius'), None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return UDK_POINT_SOURCE_RADIUS
    return float(value)


def is_empty(edit):
    return not edit or not any(edit.get(k) for k in ('deletes', 'changes', 'adds', 'area'))


# ---------------------------------------------------------------- the writer

def component_flags(q, ci):
    """A light component's own saved bool and byte (enum) properties in the written map `q`, {name: value}, and the
    names of everything it saves: the precomputed-lighting flags an unbaked build carries (bHasLightEverBeenBuilt-
    IntoLightMap and the rest, plan 4.3) are among them."""
    props = q.properties(ci)[0]
    flags = {name: item['value'] for (name, slot), item in props.items()
             if slot == 0 and item['kind'] in ('BoolProperty', 'ByteProperty')}
    return flags, sorted({name for name, _ in props})


def write_pose(walker, g, p, actor, start, raw, loc, rot, added, written):
    data = bytearray(g.export_data(actor))
    if loc:
        data = put(walker, g, data, start, 'Location', 'StructProperty', 'Vector',
                   struct.pack('<3f', *[float(v) for v in raw['location']]), added, written)
    if rot:
        data = put(walker, g, data, start, 'Rotation', 'StructProperty', 'Rotator',
                   struct.pack('<3i', *[int(v) for v in raw['rotation']]), added, written)
    g.relocate(actor, bytes(data))


def apply(g, p, state):
    """The light edits of `state` (prepare's) made in the growing package `g` over the source `p`. Returns
    dict(actors: the new light actors, for the Level's list; gone: the actors whose Level slots empty; records: one
    per op, in order, dict(op, name, exports {actor, component}, tagsAdded, written, actorTagsAdded, actorWritten,
    guids, flags, saved, imports, created)). New entries get their export indices."""
    import native_copy
    walker = native_copy.Walker(p, g)
    actors, gone, records = [], set(), []
    for op in state['ops']:
        kind, b, a = op['op'], op['before'], op['after']
        rec = dict(op=kind, name=op['name'], tagsAdded=[], written=[], actorTagsAdded=[], actorWritten=[])
        if kind in ('delete', 'area-delete'):
            gone.add(b['actorIndex'])
            rec['exports'] = dict(actor=b['actorIndex'], component=b['componentIndex'])
        elif kind in ('change', 'area-move'):
            ai, ci = b['actorIndex'], b['componentIndex']
            loc, rot = moved(b['raw'], a['raw'])
            if loc or rot:
                write_pose(walker, g, p, ai, props_start(p, ai), a['raw'], loc, rot, rec['actorTagsAdded'],
                           rec['actorWritten'])
            start = props_start(p, ci)
            data = bytearray(g.export_data(ci))
            for key in op.get('set') or {}:
                data = put(walker, g, data, start, *value_bytes(key, a['raw'][key], b['alpha']), rec['tagsAdded'],
                           rec['written'])
            if loc or rot:
                data = put(walker, g, data, start, 'CachedParentToWorld', 'StructProperty', 'Matrix',
                           parent_to_world(a['raw']['location'], a['raw']['rotation'], b['scale']), rec['tagsAdded'],
                           rec['written'])
            if rec['written']:
                g.relocate(ci, bytes(data))
            rec['exports'] = dict(actor=ai, component=ci)
        elif op.get('template') is not None:
            t = op['template']
            info = native_copy.clone_assembly(g, p, [(t['actorIndex'], a['raw']['location'], a['raw']['rotation'])])[0]
            ai, ci = info['actor'], info['mapping'][t['componentIndex']]
            start = props_start(p, t['componentIndex'])
            data = bytearray(g.export_data(ci))
            for k in GUID_KEYS:
                data = put(walker, g, data, start, k, 'StructProperty', 'Guid', a['guids'][k], rec['tagsAdded'],
                           rec['written'])
            for key in keys_for(a['kind']):
                if not same_value(a['raw'][key], t['raw'][key], key):
                    data = put(walker, g, data, start, *value_bytes(key, a['raw'][key], t['alpha']),
                               rec['tagsAdded'], rec['written'])
            data = put(walker, g, data, start, 'CachedParentToWorld', 'StructProperty', 'Matrix',
                       parent_to_world(a['raw']['location'], a['raw']['rotation'], t['scale']), rec['tagsAdded'],
                       rec['written'])
            g.relocate(ci, bytes(data))
            a.update(actorIndex=ai, componentIndex=ci)
            actors.append(ai)
            rec['exports'] = dict(actor=ai, component=ci)
            rec['actorWritten'] = ['Location', 'Rotation']
        else:
            made = add_recipe(g, p, a, op['recipe'])
            a.update(actorIndex=made['actor'], componentIndex=made['component'])
            actors.append(made['actor'])
            rec.update(exports=dict(actor=made['actor'], component=made['component']),
                       imports=list(made.get('imports') or []), created=list(made.get('created') or []))
        rec['guids'] = {k: v.hex() for k, v in (a or b)['guids'].items()}
        records.append(rec)
    return dict(actors=actors, gone=gone, records=records)


def add_recipe(g, p, entry, version):
    """A spot or point light made by the built-in recipe (plan 4.9 and 9.6; prefab plan 5.5), from
    tools/bake/light_factory.py."""
    try:
        import light_factory
    except ImportError as error:
        raise ValueError('this copy of the tools has no light_factory.py, which makes recipe lights') from error
    raw, kind = entry['raw'], entry['kind']
    light = {k: (list(raw[k]) if k == 'color' else raw[k]) for k in keys_for(kind)}
    if kind == 'point':
        made = light_factory.add_point(g, p, list(raw['location']), light, dict(entry['guids']), version)
    else:
        made = light_factory.add_spot(g, p, list(raw['location']), list(raw['rotation']), light, dict(entry['guids']),
                                      version)
    if not isinstance(made, dict) or 'actor' not in made or 'component' not in made:
        raise ValueError('light_factory returned no actor and component for the recipe light')
    return made


# ---------------------------------------------------------------- receiver membership (baked builds only)

class Registrar:
    """Light GUIDs to add to receivers' texture lightmap lists (every LOD with one), merged per component, spliced into
    the writer's current bytes: a list grows by its count and 16-byte GUIDs (the record holds no offsets into the
    export), the export relocated. Splices made by an earlier `apply` of this registrar are accounted for, so several
    light edits compose; any other change to the component's bytes before its lists is refused."""

    def __init__(self, p):
        self.p = p
        self.pending = {}       # component export -> [16-byte guids]
        self.applied = {}       # component export -> {lod: [guids inserted]}

    def add(self, ci, guid):
        guids = self.pending.setdefault(ci, [])
        if guid not in guids:
            guids.append(guid)

    def apply(self, g):
        """Splice what is pending. Returns {component export: [guid hex added]} (a GUID a list already holds is not
        added again)."""
        p, out = self.p, {}
        for ci in sorted(self.pending):
            guids = self.pending[ci]
            e = p.exports[ci - 1]
            fields = lightmap_fields.component_fields(p, ci)
            listed = [lod['lightmap'].get('lightGuids', []) for lod in lighting.component_record(p, ci)['lods']]
            done = self.applied.setdefault(ci, {})
            data = bytearray(g.export_data(ci))
            shift, added = 0, []
            for k, lod in enumerate(fields['lods']):
                lm = lod['lightmap']
                if lm['type'] != 2:
                    continue
                have = listed[k] + [x.hex() for x in done.get(k, [])]
                at = lm['lightGuidsOffset'] - e['off'] + shift
                count = struct.unpack_from('<i', data, at - 4)[0]
                if count != len(have) or bytes(data[at:at + 16 * count]) != b''.join(bytes.fromhex(x) for x in have):
                    raise ValueError(f'{p.name(ci)}: its lightmap list changed before this splice')
                new = [x for x in guids if x.hex() not in have]
                if new:
                    struct.pack_into('<i', data, at - 4, count + len(new))
                    data[at + 16 * count:at + 16 * count] = b''.join(new)
                    done.setdefault(k, []).extend(new)
                    added += [x.hex() for x in new if x.hex() not in added]
                shift += 16 * len(done.get(k, []))
            if added:
                g.relocate(ci, bytes(data))
                out[ci] = added
        self.pending = {}
        return out


def lightmap_kind(p, ci):
    """A mesh component's LOD-0 lightmap: 'texture', 'vertex' or 'none' (no lightmap, or no LOD data); None when its
    native data can't be read."""
    try:
        f = lightmap_fields.component_fields(p, ci)
    except Exception:
        return None
    if not f['lods']:
        return 'none'
    return {2: 'texture', 1: 'vertex'}.get(f['lods'][0]['lightmap']['type'], 'none')


def mesh_box(p, ci, meshes, location=None, rotation=None):
    """A mesh component's world box from its mesh's vertices, its actor at `location`, `rotation` when given."""
    import lightmap_texels
    mi = p.effective(ci, 'StaticMesh', 0)
    if mi not in meshes:
        meshes[mi] = lightmap_texels.component_mesh(p, ci)['positions']
    m = lightmap_texels.world_matrix(p, ci, location, rotation)
    pts = meshes[mi] @ m[:3, :3].T + m[:3, 3]
    return [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]


def sphere_meets(raw, box):
    """Whether a light's radius sphere meets a world box: the conservative membership test."""
    d2 = 0.0
    for k, c in enumerate(raw['location']):
        lo, hi = box[2 * k], box[2 * k + 1]
        d = lo - float(c) if float(c) < lo else float(c) - hi if float(c) > hi else 0.0
        d2 += d * d
    return d2 <= float(raw['radius']) ** 2


def registering(state):
    """The lights a baked build lists in receivers' lightmaps: each added and each changed placed light that emits
    (a disabled or zero-brightness one needs no membership until it puts light down). Generated area lights never."""
    if not state:
        return []
    return [op['after'] for op in state['ops']
            if op['op'] in ('add', 'change') and op['after']['role'] == 'static' and emits(op['after']['raw'])]


def copy_registrations(p, state, ci, location, rotation, meshes=None):
    """The registering lights whose radius sphere meets the copied mesh component `ci` (of the source) at its copy's
    pose: [(16-byte LightmapGuid, light id)]. Empty for a component without a LOD-0 texture lightmap."""
    lights = registering(state)
    if not lights or lightmap_kind(p, ci) != 'texture':
        return []
    box = mesh_box(p, ci, {} if meshes is None else meshes, location, rotation)
    return [(e['guids']['LightmapGuid'], e['id']) for e in lights if 'LightmapGuid' in e['guids']
            and sphere_meets(e['raw'], box)]


def register(g, p, state, registrar, exclude=()):
    """The registering lights listed in the texture lightmaps of the map's own receivers their radius sphere meets
    (receivers of the actors `exclude`, hidden pieces, left out). Mesh components in reach without a texture lightmap
    (vertex lit, no lightmap or LOD data) are reported: they take the light live [inferred, plan 4.3]. Returns
    dict(registered: {component export: [(guid hex, light id)]}, unregistered: [dict(component, reason, lights)])."""
    lights = registering(state)
    out = dict(registered={}, unregistered=[])
    if not lights:
        return out
    meshes, wanted = {}, {}
    for ci in range(1, len(p.exports) + 1):
        if p.cls(ci) not in lightmap_fields.COMPONENT_CLASSES or not p.name(ci).startswith(PL):
            continue
        actor = p.exports[ci - 1]['outer']
        if actor in exclude or p.effective(ci, 'StaticMesh', 0) <= 0:
            continue
        try:
            box = mesh_box(p, ci, meshes)
        except Exception:
            continue
        reach = [e for e in lights if 'LightmapGuid' in e['guids'] and sphere_meets(e['raw'], box)]
        if not reach:
            continue
        kind = lightmap_kind(p, ci)
        if kind != 'texture':
            out['unregistered'].append(dict(component=p.name(ci), reason=f'{kind or "unreadable"} lightmap',
                                            lights=[e['id'] for e in reach]))
            continue
        for e in reach:
            registrar.add(ci, e['guids']['LightmapGuid'])
            wanted.setdefault(ci, {})[e['guids']['LightmapGuid'].hex()] = e['id']
    for ci, added in registrar.apply(g).items():
        out['registered'][ci] = [(h, wanted.get(ci, {}).get(h)) for h in added]
    return out


# ---------------------------------------------------------------- after writing

def verify(q, state, result=None):
    """The grown map `q` read back: every light the edit leaves has the after values, GUIDs and pose, deleted ones
    are out of the Level's actor list and new ones in it. Fills the after entries' actor and component paths, and
    each of `result`'s records (apply's) with its component's saved flags as written. Raises ValueError on a
    difference."""
    import native_copy
    listed = set(native_copy.level_actors(q))
    records = result['records'] if result else [{} for _ in state['ops']]
    for op, rec in zip(state['ops'], records):
        b, a = op['before'], op['after']
        if a is None:
            if b['actorIndex'] in listed:
                raise ValueError(f'{op["name"]} is still in the Level\'s actor list')
            continue
        rec['flags'], rec['saved'] = component_flags(q, a['componentIndex'])
        ai, ci = a['actorIndex'], a['componentIndex']
        if ai not in listed:
            raise ValueError(f'{op["name"]} is not in the Level\'s actor list')
        rec = light_record(q, ai)
        if rec is None or q.by_name.get(rec['component']) != ci:
            raise ValueError(f'{op["name"]}: its actor does not name its light component')
        a['actor'], a['component'] = rec['actor'], rec['component']
        if op['op'] in ('add', 'area-copy') and q.cls(ai) != (a['actorClass'] if op.get('template') is None
                                                                else q.cls(op['template']['actorIndex'])):
            raise ValueError(f'{op["name"]}: a {q.cls(ai)}, not its template\'s class')
        _, raw = raw_values(q, ai)
        check_matches(f'{op["name"]} as written', {k: v for k, v in a['raw'].items()}, raw)
        for k, v in a['guids'].items():
            if bytes(q.effective(ci, k) or b'') != v:
                raise ValueError(f'{op["name"]}: its {k} reads back as another')


def relight_edits(state, registered, policy='baked'):
    """The relight's --light-edits document (plan 4.4): each edit's normalized codec light before and after (None
    before for an addition, None after for a deletion), its component and GUIDs (both resolve to one light), and the
    GUIDs this build added to each receiver's lists ({component path: [hex]}), which the relight's before state leaves
    out (original membership)."""
    edits = []
    for op in state['ops']:
        b, a = op['before'], op['after']
        edits.append(dict(op=op['op'], name=op['name'], label=op.get('label'), kind=op['kind'], role=op['role'],
                          component=(a or b)['component'], actor=(a or b)['actor'],
                          guids={k: v.hex() for k, v in (a or b)['guids'].items()},
                          before=codec_light(b) if b else None, after=codec_light(a) if a else None,
                          reach=dict(before=reach_box(b['raw']) if b else None, after=reach_box(a['raw']) if a else None)))
    return dict(version=1, policy=policy, edits=edits, registered={k: list(v) for k, v in sorted(registered.items())},
                **({'stagedAreas': state['stagedAreas']} if state.get('stagedAreas') else {}))


def jsonable(raw):
    return None if raw is None else {k: (list(v) if isinstance(v, (list, tuple)) else v) for k, v in raw.items()}


def record(state, result, policy, registration=None, copies=None, names=None):
    """The fixture manifest's `lights` section (plan 4.3, "The record"): the registration policy; each edit with its
    exports, the tags it added and the properties it wrote, its GUIDs, its raw values before and after (what the delta
    is between), the component's saved flags, and for a recipe spot the imports it used or made; the receivers each
    light was listed in (`registered`, the map's own and the piece copies'), and the receivers in reach without a
    texture lightmap (`unregistered`). `names` turns export indices into paths."""
    name = names or (lambda i: i)
    edits = []
    for op, rec in zip(state['ops'], result['records']):
        b, a = op['before'], op['after']
        item = dict(op=op['op'], name=op['name'], label=op.get('label'), kind=op['kind'], role=op['role'],
                    actor=name(rec['exports']['actor']), component=name(rec['exports']['component']),
                    exports=rec['exports'], guids=rec['guids'], tagsAdded=rec['tagsAdded'], written=rec['written'],
                    actorTagsAdded=rec['actorTagsAdded'], actorWritten=rec['actorWritten'],
                    before=jsonable(b['raw']) if b else None, after=jsonable(a['raw']) if a else None)
        if op.get('set') is not None:
            item['set'] = jsonable(op['set'])
        if op.get('template') is not None:
            item['from'] = op['template']['id']
        if op.get('recipe') is not None:
            item.update(recipe=dict(kind=op['kind'], version=op['recipe']), imports=rec.get('imports', []),
                        created=rec.get('created', []))
        if op['role'] == 'area':
            item.update(owner=op.get('owner'), ownerEntity=op.get('ownerEntity'), lightmapRegistration=False)
        if 'flags' in rec:
            item.update(flags=rec['flags'], saved=rec['saved'])
        edits.append(item)
    reg = registration or dict(registered={}, unregistered=[])
    registered = {name(ci): [dict(guid=h, light=l) for h, l in v] for ci, v in sorted(reg['registered'].items())}
    for path, v in sorted((copies or {}).items()):
        registered[path] = [dict(guid=h, light=l) for h, l in v]
    counts = dict(deleted=sum(o['op'] == 'delete' for o in state['ops']),
                  changed=sum(o['op'] == 'change' and bool(o.get('set')) for o in state['ops']),
                  moved=sum(o['op'] == 'change' and any(moved(o['before']['raw'], o['after']['raw']))
                            for o in state['ops']),
                  added=sum(o['op'] == 'add' for o in state['ops']),
                  area=dict(moved=sum(o['op'] == 'area-move' for o in state['ops']),
                            copied=sum(o['op'] == 'area-copy' for o in state['ops']),
                            deleted=sum(o['op'] == 'area-delete' for o in state['ops'])))
    return dict(policy=policy, counts=counts, edits=edits, registered=registered,
                unregistered=reg['unregistered'],
                note=('baked: each added or changed placed light that emits is listed in the texture lightmaps its '
                      'radius reaches; generated area lights never are' if policy == 'baked' else
                      'unbaked: receivers\' lightmap lists are left as they are and no new light GUID is added to '
                      'any, so no lightmap holds an edited or added light\'s light'))
