"""Spot and point lights built from a recipe, for maps with no light of the kind to copy (editor lights plan, 4.9
and 9.6; point lights: prefab plan 5.5, stage L1.1, so that a prefab's lights need no map).

A placed spot light in a cooked map is two exports and no more (its sprite and cone helpers are cooked away), as read
from URB_Bar's 62 spot lights and checked against URB_PoliceStation's, TempleShip's and CLrgScout_ForestTrench's
(research/spot-light-recipe.md):
- the SpotLight actor, under the persistent level: class Engine.SpotLight, no archetype of its own (the class default
  object stands in), its state frame and net index, then its tagged properties (LightComponent, Location, Rotation,
  bDirtyComponents, Tag); no Components array (the component is found through LightComponent);
- its SpotLightComponent, under the actor: class Engine.SpotLightComponent, archetype
  Engine.Default__SpotLight.SpotLightComponent0, an empty template owner class and its net index, then its tagged
  properties (cones, radius, falloff, the cached world matrix, Lightmass settings, the two GUIDs, brightness, colour,
  on/off and the built flag) and nothing after them.

add_spot builds both from a versioned recipe (RECIPES) and the destination package alone: the Engine imports it needs
are found by their names or added (package_grow.Grower.add_import), the exports are made with no template
(Grower.new_export), names come from the destination's name table (added when missing), and every object reference
is the destination's own. A placed point light is the same two exports with PointLight's classes and no cones
(POINT_RECIPES, add_point: read from 397 placed point lights of five maps). No other map, no UDK and no file beyond the destination is read. A recipe is construction
rules, symbolic references and explicit values, not bytes copied from a game package. A version, once validated, is
frozen (recipe_digest, pinned by the tests): a change is a new version, and a build uses the version its project
records. The caller adds the actor to the Level's actor list.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
import props as legacy_props  # noqa: E402

LEVEL = 'TheWorld.PersistentLevel'
# the light values of the plan's section 9.1, in the package's own terms
LIGHT_KEYS = ('color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled')
GUID_KEYS = ('LightGuid', 'LightmapGuid')
FLOAT_MAX = 3.4e38

# Version 1, validated on 9 November 2026 against every placed SpotLight of URB_Bar (62), URB_PoliceStation (31),
# TempleShip (54) and CLrgScout_ForestTrench (20): the same export flags, archetypes, preambles, property kinds and
# order, Lightmass settings, and no native tail (tests/test_light_factory.py, RecipeMatchesPlacedSpots).
# - imports: [path, class package, class]; an import's outer is its path up to the last dot (top level without one).
# - exports: their class and archetype name an import path; `name` is the export's name (its number an unused one).
# - properties: [name, kind, value], in the order the cooked components save them (the most derived class's first);
#   a value '$key' is filled in by add_spot (the light values, pose, GUIDs, component index, cached matrix). Kinds:
#   object, float, bool, name, and the structs Vector, Rotator, Matrix, Guid, Color; 'struct <Name>' is a struct of
#   tagged properties.
# - inherited: what this recipe never saves, left to the engine's archetype as every surveyed placed spot leaves it
#   (static, lightmapped, shadow casting, the static lighting channels).
RECIPES = {
    1: {
        'kind': 'spot',
        # the starting values (plan 3.3): white, brightness 1, radius 1,024, falloff 2, cones 0 and 44 degrees, on
        'light': {'color': [255, 255, 255], 'brightness': 1.0, 'radius': 1024.0, 'falloffExponent': 2.0,
                  'innerConeAngle': 0.0, 'outerConeAngle': 44.0, 'enabled': True},
        'rotation': [-16384, 0, 0],             # pointing down, the SpotLight class default
        'alpha': 255,                           # LightColor's fourth byte, as the bar's spots save it
        'imports': [
            ['Engine', 'Core', 'Package'],
            ['Engine.SpotLight', 'Core', 'Class'],
            ['Engine.SpotLightComponent', 'Core', 'Class'],
            ['Engine.Default__SpotLight', 'Engine', 'SpotLight'],
            ['Engine.Default__SpotLight.SpotLightComponent0', 'Engine', 'SpotLightComponent'],
        ],
        'actor': {
            'class': 'Engine.SpotLight', 'name': 'SpotLight', 'archetype': None,
            'flags': 0x0207000100000000,        # RF_HasStack, the three load flags, RF_Transactional
            # the state frame: node and state node the actor's class, then these, then the net index
            'preamble': {'kind': 'stateFrame', 'probeMask': 0xFFFFFFFF, 'latentAction': 0, 'stateStack': 0,
                         'codeOffset': -1},
            'properties': [
                ['LightComponent', 'object', '$component'],
                ['Location', 'Vector', '$location'],
                ['Rotation', 'Rotator', '$rotation'],
                ['bDirtyComponents', 'bool', False],
                ['Tag', 'name', 'SpotLight'],
            ],
        },
        'component': {
            'class': 'Engine.SpotLightComponent', 'name': 'SpotLightComponent',
            'archetype': 'Engine.Default__SpotLight.SpotLightComponent0',
            'flags': 0x0007000100000000,        # the three load flags, RF_Transactional
            # an empty template owner class (an instance, not a template), then the net index
            'preamble': {'kind': 'component', 'templateOwnerClass': 0},
            'properties': [
                ['InnerConeAngle', 'float', '$innerConeAngle'],
                ['OuterConeAngle', 'float', '$outerConeAngle'],
                ['Radius', 'float', '$radius'],
                ['FalloffExponent', 'float', '$falloffExponent'],
                ['CachedParentToWorld', 'Matrix', '$parentToWorld'],
                ['LightmassSettings', 'struct LightmassPointLightSettings', [['LightSourceRadius', 'float', 32.0]]],
                ['LightGuid', 'Guid', '$LightGuid'],
                ['LightmapGuid', 'Guid', '$LightmapGuid'],
                ['Brightness', 'float', '$brightness'],
                ['LightColor', 'Color', '$color'],
                ['bEnabled', 'bool', '$enabled'],
                ['bHasLightEverBeenBuiltIntoLightMap', 'bool', True],
            ],
            'inherited': ['CastShadows', 'CastStaticShadows', 'CastDynamicShadows', 'bCastCompositeShadow',
                          'bForceDynamicLight', 'UseDirectLightMap', 'LightingChannels', 'LightAffectsClassification',
                          'Function', 'ShadowRadiusMultiplier', 'LightShaftConeAngle'],
        },
    },
}


# A point light. Version 1, validated on 12 November 2026 against every placed PointLight of URB_Bar (54),
# URB_PoliceStation (67), TempleShip (87) and CLrgScout_ForestTrench (172): the spot's export flags, preambles and
# property kinds and order, with PointLight's classes and archetype and no cone angles
# (tests/test_light_factory.py, RecipeMatchesPlacedPoints). A point light has no direction: the actor saves no
# Rotation (as 357 of the 380 don't), and its cached matrix is its location's alone.
POINT_RECIPES = {
    1: {
        'kind': 'point',
        # the starting values: white, brightness 1, radius 1,024, falloff 2, on (the engine's own for a point light)
        'light': {'color': [255, 255, 255], 'brightness': 1.0, 'radius': 1024.0, 'falloffExponent': 2.0, 'enabled': True},
        'rotation': [0, 0, 0],
        'alpha': 255,
        'imports': [
            ['Engine', 'Core', 'Package'],
            ['Engine.PointLight', 'Core', 'Class'],
            ['Engine.PointLightComponent', 'Core', 'Class'],
            ['Engine.Default__PointLight', 'Engine', 'PointLight'],
            ['Engine.Default__PointLight.PointLightComponent0', 'Engine', 'PointLightComponent'],
        ],
        'actor': {
            'class': 'Engine.PointLight', 'name': 'PointLight', 'archetype': None,
            'flags': 0x0207000100000000,
            'preamble': {'kind': 'stateFrame', 'probeMask': 0xFFFFFFFF, 'latentAction': 0, 'stateStack': 0,
                         'codeOffset': -1},
            'properties': [
                ['LightComponent', 'object', '$component'],
                ['Location', 'Vector', '$location'],
                ['bDirtyComponents', 'bool', False],
                ['Tag', 'name', 'PointLight'],
            ],
        },
        'component': {
            'class': 'Engine.PointLightComponent', 'name': 'PointLightComponent',
            'archetype': 'Engine.Default__PointLight.PointLightComponent0',
            'flags': 0x0007000100000000,
            'preamble': {'kind': 'component', 'templateOwnerClass': 0},
            'properties': [
                ['Radius', 'float', '$radius'],
                ['FalloffExponent', 'float', '$falloffExponent'],
                ['CachedParentToWorld', 'Matrix', '$parentToWorld'],
                ['LightmassSettings', 'struct LightmassPointLightSettings', [['LightSourceRadius', 'float', 32.0]]],
                ['LightGuid', 'Guid', '$LightGuid'],
                ['LightmapGuid', 'Guid', '$LightmapGuid'],
                ['Brightness', 'float', '$brightness'],
                ['LightColor', 'Color', '$color'],
                ['bEnabled', 'bool', '$enabled'],
                ['bHasLightEverBeenBuiltIntoLightMap', 'bool', True],
            ],
            'inherited': ['CastShadows', 'CastStaticShadows', 'CastDynamicShadows', 'bCastCompositeShadow',
                          'bForceDynamicLight', 'UseDirectLightMap', 'LightingChannels', 'LightAffectsClassification',
                          'Function', 'ShadowRadiusMultiplier'],
        },
    },
}
# every kind's recipes, by version
KINDS = {'spot': RECIPES, 'point': POINT_RECIPES}


def recipe(version, kind='spot'):
    """The recipe of that kind and version, or ValueError for one this factory doesn't know."""
    known = KINDS.get(kind)
    if known is None:
        raise ValueError(f'no recipe makes a {kind!r} light (this factory makes {sorted(KINDS)})')
    if isinstance(version, bool) or not isinstance(version, int) or version not in known:
        raise ValueError(f'unknown {kind} light recipe version {version!r} (this factory knows {sorted(known)})')
    return known[version]


def recipe_digest(version, kind='spot'):
    """SHA-256 of a recipe's canonical JSON: what a build records, and what the tests pin to keep a version frozen."""
    text = json.dumps(recipe(version, kind), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def _table_sin(angle):
    """UE3's sine of a rotator angle, from its table of 16,384 single floats (the angle's low 16 bits over 4)."""
    return _f32(math.sin(((int(angle) >> 2) & 16383) * math.tau / 16384))


def cached_parent_to_world(location, rotation):
    """The 64 bytes of a light component's CachedParentToWorld for an actor at `location` (x, y, z) with `rotation`
    (pitch, yaw, roll, rotator units) and no scale: UE3's rotation-translation matrix (rows: the X, Y and Z axes and
    the origin), built with the engine's sine table. Each row is stored W first, then X, Y, Z (the Plane struct's own
    member W, then its Vector's), as every placed light's matrix in the surveyed maps is."""
    sp, sy, sr = (_table_sin(a) for a in rotation)
    cp, cy, cr = (_table_sin(a + 16384) for a in rotation)
    rows = [[cp * cy, cp * sy, sp, 0.0],
            [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp, 0.0],
            [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp, 0.0],
            [location[0], location[1], location[2], 1.0]]
    return b''.join(struct.pack('<4f', r[3], r[0], r[1], r[2]) for r in rows)


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or abs(value) > FLOAT_MAX:
        raise ValueError(f'{what} must be a finite number, not {value!r}')
    return float(value)


def _light_values(rec, light):
    """The complete light values (9.1; a point light's have no cones): the recipe's when `light` is None, else
    `light`, checked."""
    if light is None:
        light = rec['light']
    keys = [k for k in LIGHT_KEYS if k in rec['light']]
    if not isinstance(light, dict):
        raise ValueError(f'light must be a dict of {", ".join(keys)}')
    missing = [k for k in keys if k not in light]
    unknown = sorted(set(light) - set(keys))
    if missing or unknown:
        raise ValueError(f'light values incomplete or unknown: missing {missing}, unknown {unknown}')
    color = light['color']
    if not isinstance(color, (list, tuple)) or len(color) != 3 or any(
            isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255 for c in color):
        raise ValueError(f'color must be three whole numbers 0 to 255, not {color!r}')
    out = dict(color=list(color))
    for key in keys[1:-1]:
        out[key] = _number(light[key], key)
    for key in ('brightness', 'radius', 'falloffExponent'):
        if out[key] < 0:
            raise ValueError(f'{key} must not be negative, not {out[key]!r}')
    if not isinstance(light['enabled'], bool):
        raise ValueError(f'enabled must be true or false, not {light["enabled"]!r}')
    out['enabled'] = light['enabled']
    return out


def _pose(location, rotation):
    if not isinstance(location, (list, tuple)) or len(location) != 3:
        raise ValueError(f'location must be [x, y, z], not {location!r}')
    location = [_number(v, 'location') for v in location]
    if not isinstance(rotation, (list, tuple)) or len(rotation) != 3:
        raise ValueError(f'rotation must be [pitch, yaw, roll], not {rotation!r}')
    rot = []
    for v in rotation:
        v = _number(v, 'rotation')
        if v != int(v) or not -2 ** 31 <= v < 2 ** 31:
            raise ValueError(f'rotation must be whole rotator units, not {rotation!r}')
        rot.append(int(v))
    return location, rot


def _guid_values(guids):
    if not isinstance(guids, dict) or sorted(guids) != sorted(GUID_KEYS):
        raise ValueError(f'guids must be a dict of {" and ".join(GUID_KEYS)}')
    out = {}
    for key in GUID_KEYS:
        value = guids[key]
        if not isinstance(value, (bytes, bytearray)) or len(value) != 16 or not any(value):
            raise ValueError(f'{key} must be 16 bytes, not all zero')
        out[key] = bytes(value)
    if out['LightGuid'] == out['LightmapGuid']:
        raise ValueError('LightGuid and LightmapGuid must differ')
    return out


def _class_name(g, ref):
    if ref < 0:
        raw = struct.unpack('<iiiiiii', g.imports[-ref - 1])
        return g.name_of(raw[5], raw[6])
    if ref > 0:
        e = g.entries[ref - 1]
        return g.name_of(e.name_index, e.name_number)
    return 'Class'


def _walk(names, b, at, end):
    """(name, kind, struct name, value offset, size) of each tagged property from `at`."""
    def fname(o):
        i, n = struct.unpack_from('<ii', b, o)
        if not 0 <= i < len(names) or n < 0:
            raise ValueError(f'bad name at {o}')
        return names[i] + (f'_{n - 1}' if n else '')
    while at + 8 <= end:
        name = fname(at)
        if name == 'None':
            return
        kind = fname(at + 8)
        size = struct.unpack_from('<i', b, at + 16)[0]
        at += 24
        sub = None
        if kind == 'BoolProperty':
            size = 1
        elif kind in ('StructProperty', 'ByteProperty'):
            sub = fname(at)
            at += 8
        yield name, kind, sub, at, size
        at += size
    raise ValueError('no closing None')


def used_guids(g, p):
    """The 16-byte LightGuid and LightmapGuid of every light component in the source `p` and of every light
    component export `g` has added since (clones and recipe lights alike)."""
    used = set()
    for i in range(1, len(p.exports) + 1):
        if p.cls(i).endswith('LightComponent'):
            for key in GUID_KEYS:
                value = p.own(i, key)
                if isinstance(value, (bytes, bytearray)):
                    used.add(bytes(value))
    for i in range(len(p.exports) + 1, len(g.entries) + 1):
        e = g.entries[i - 1]
        if not _class_name(g, e.cls).endswith('LightComponent'):
            continue
        data = g.export_data(i)
        start = legacy_props.props_start(data, dict(off=0, size=len(data), flags=e.get('<Q', 24)), g.names)
        for name, kind, sub, at, size in _walk(g.names, data, start, len(data)):
            if name in GUID_KEYS and sub == 'Guid' and size == 16:
                used.add(bytes(data[at:at + 16]))
    return used


def _imports(g, rec):
    """The recipe's imports in the destination: {path: index}, and the indices made. An import is found by its class,
    name and outer, else added; the outer of each is the destination's own index of its parent path."""
    found, made = {}, []
    for path, class_package, class_name in rec['imports']:
        parent, _, name = path.rpartition('.')
        outer = found[parent] if parent else 0
        index = g.find_import(class_name, name, outer)
        if index is None:
            if not parent and any(e.outer == 0 and g.name_of(e.name_index, e.name_number) == name
                                  for e in g.entries):
                raise ValueError(f'the map holds {name} as an export, which the {rec["kind"]} recipe does not support')
            index = g.add_import(class_package, class_name, outer, name)
            made.append(index)
        found[path] = index
    return found, made


def _property(g, name, kind, value):
    def tag(property_type, size, struct_name=None):
        out = struct.pack('<iiiiii', g.name(name), 0, g.name(property_type), 0, size, 0)
        return out + (struct.pack('<ii', g.name(struct_name), 0) if struct_name else b'')
    if kind == 'object':
        return tag('ObjectProperty', 4) + struct.pack('<i', value)
    if kind == 'float':
        return tag('FloatProperty', 4) + struct.pack('<f', value)
    if kind == 'bool':
        return tag('BoolProperty', 0) + bytes([1 if value else 0])
    if kind == 'name':
        return tag('NameProperty', 8) + struct.pack('<ii', g.name(value), 0)
    if kind == 'Vector':
        return tag('StructProperty', 12, 'Vector') + struct.pack('<3f', *value)
    if kind == 'Rotator':
        return tag('StructProperty', 12, 'Rotator') + struct.pack('<3i', *value)
    if kind in ('Matrix', 'Guid'):
        size = 64 if kind == 'Matrix' else 16
        if len(value) != size:
            raise ValueError(f'{name} needs {size} bytes')
        return tag('StructProperty', size, kind) + bytes(value)
    if kind == 'Color':
        r, gr, b, a = value
        return tag('StructProperty', 4, 'Color') + bytes([b, gr, r, a])
    if kind.startswith('struct '):
        inner = _properties(g, value, {})
        return tag('StructProperty', len(inner), kind.split(' ', 1)[1]) + inner
    raise ValueError(f'unknown property kind {kind!r}')


def _properties(g, specs, values):
    """Tagged properties from `specs` ([name, kind, value]) with the destination's names, closed by None."""
    out = bytearray()
    for name, kind, value in specs:
        if isinstance(value, str) and value.startswith('$'):
            value = values[value[1:]]
        out += _property(g, name, kind, value)
    return bytes(out + struct.pack('<ii', g.name('None'), 0))


def _preamble(spec, cls, net):
    pre = spec['preamble']
    if pre['kind'] == 'stateFrame':
        return struct.pack('<iiIHiii', cls, cls, pre['probeMask'], pre['latentAction'], pre['stateStack'],
                           pre['codeOffset'], net)
    if pre['kind'] == 'component':
        return struct.pack('<ii', pre['templateOwnerClass'], net)
    raise ValueError(f'unknown preamble {pre["kind"]!r}')


def add_spot(g, p, location, rotation, light, guids, version=1):
    """A new SpotLight actor and its SpotLightComponent in the persistent level of the growing package `g`
    (package_grow.Grower) over its read-only source `p` (audit_lighting.Package), made by recipe `version` with no
    local light as a template: at `location` (x, y, z) and `rotation` (pitch, yaw, roll, whole rotator units; None
    for the recipe's, pointing down), with `light` (the seven values of plan 9.1, complete; None for the recipe's
    starting values) and `guids` (dict(LightGuid=16 bytes, LightmapGuid=16 bytes), used by no light of the map).
    Everything is checked before `g` changes; an unknown version raises ValueError. The caller adds the actor to the
    Level's actor list. Returns dict(actor, component: the new export indices, imports: the import indices it reused
    or made, in the recipe's order (Engine, the actor's class, the component's class, the class default object, the
    component archetype), created: those it made)."""
    return _add(recipe(version), g, p, location, rotation, light, guids)


def add_point(g, p, location, light, guids, version=1):
    """A new PointLight actor and its PointLightComponent, as add_spot makes a spot light: at `location`, with
    `light` (colour, brightness, radius, falloff exponent and enabled, complete; None for the recipe's starting
    values) and `guids`. A point light has no direction, so there is no rotation. Returns what add_spot does."""
    rec = recipe(version, 'point')
    return _add(rec, g, p, location, rec['rotation'], light, guids)


def _add(rec, g, p, location, rotation, light, guids):
    light = _light_values(rec, light)
    location, rotation = _pose(location, rec['rotation'] if rotation is None else rotation)
    guids = _guid_values(guids)
    level = p.by_name.get(LEVEL)
    if level is None or p.cls(level) != 'Level' or level > len(g.entries):
        raise ValueError(f'{p.path.name} has no {LEVEL} to add a light to')
    used = used_guids(g, p)
    clash = [key for key in GUID_KEYS if guids[key] in used]
    if clash:
        raise ValueError(f'{" and ".join(clash)} already belong to a light of the map')

    found, made = _imports(g, rec)
    actor = len(g.entries) + 1
    component = actor + 1
    values = dict(light, color=light['color'] + [rec['alpha']], location=location, rotation=rotation,
                  component=component, parentToWorld=cached_parent_to_world(location, rotation), **guids)
    for spec, index, outer in ((rec['actor'], actor, level), (rec['component'], component, actor)):
        cls = found[spec['class']]
        data = _preamble(spec, cls, g.next_net_index(outer)) + _properties(g, spec['properties'], values)
        archetype = found[spec['archetype']] if spec['archetype'] else 0
        if g.new_export(cls, outer, spec['name'], data, archetype=archetype, flags=spec['flags']) != index:
            raise RuntimeError('the light exports did not get the planned indices')
    return dict(actor=actor, component=component, imports=[found[path] for path, _, _ in rec['imports']],
                created=made)
