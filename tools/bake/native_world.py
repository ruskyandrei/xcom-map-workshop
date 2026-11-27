"""The map's atmosphere written into the variant map (game-likeness plan, stage C5): the native edit's `atmosphere` lane,
{"fog": {member: value}, "postProcess": {member: value}}, the members a project changes of its WorldInfo's height fog
(`XComHeightFog`, an XComHeightFogParameters) and its post-process settings (`DefaultPostProcessSettings`, a
PostProcessSettings).

A map saves only the members of a struct that differ from its class's defaults (CSmallScout_DirtRoad's fog saves four:
no density, no height), so each struct is made again from the members the map saves, those the project changes put
over them (in place where the map saves the member, added before the struct's closing None where not), and the rest
left to the defaults as before. A post-process member goes with its override flag set, as the game's editor saves a
member it changed (`bOverride_Scene_Colorize` with `Scene_Colorize`: the class's default flag is off).

A value is the export's form (tools/viewer/atmosphere.py `plain`): a number, a bool, a colour as four numbers from 0 to
1 (a `Color` is saved a byte a channel, B G R A; a `LinearColor` as four floats), a `Vector` as three numbers, an enum
member's name. The members' kinds are the script packages' declarations, kept in tools/viewer/atmosphere_defaults.json
(`kinds`, made with its defaults and held to the install by its test).

  apply(g, p, lane, kinds=None) -> record | None   the lane made in the grower `g` of the map `p`
  read_back(q, record, lane)                       the written map read again: each member as the lane says
"""
import math
import struct

import native_lights
import props as legacy_props

STRUCTS = {'fog': ('XComHeightFog', 'XComHeightFogParameters'),
           'postProcess': ('DefaultPostProcessSettings', 'PostProcessSettings')}
# what is no value a project gives (the LUT blender's state, objects, the materials' array)
NOT_WRITTEN = {'ColorGradingLUT', 'ColorGrading_LookupTable', 'DOF_BokehTexture', 'DisabledMaterialEffects'}


class AtmosphereError(ValueError):
    """A lane the writer can't make: a member the struct lacks or a value of another kind."""


def member_kinds():
    """{'fog' | 'postProcess': {member: (property kind, struct name or None)}}: atmosphere_defaults.json's."""
    import atmosphere
    return {key: {name: tuple(kind) for name, kind in members.items()}
            for key, members in atmosphere.load_defaults()['kinds'].items()}


def value_bytes(g, name, kind, sub, value):
    """(kind, struct or enum name, value bytes) of a member's value in the export's form."""
    def number(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise AtmosphereError('%s needs a number, not %r' % (name, v))
        return float(v)

    def numbers(n):
        if not isinstance(value, (list, tuple)) or len(value) < n:
            raise AtmosphereError('%s needs %d numbers, not %r' % (name, n, value))
        return [number(v) for v in value[:n]]
    if kind == 'BoolProperty':
        if not isinstance(value, bool):
            raise AtmosphereError('%s needs true or false, not %r' % (name, value))
        return kind, None, bytes([1 if value else 0])
    if kind == 'FloatProperty':
        return kind, None, struct.pack('<f', number(value))
    if kind == 'ByteProperty' and isinstance(value, str):
        return kind, sub or _enum_of(name), struct.pack('<ii', g.name(value), 0)
    if kind == 'StructProperty' and sub == 'Color':
        r, gr, b, a = (max(0, min(255, int(round(v * 255)))) for v in numbers(4))
        return kind, 'Color', bytes([b, gr, r, a])
    if kind == 'StructProperty' and sub == 'LinearColor':
        return kind, 'LinearColor', struct.pack('<4f', *numbers(4))
    if kind == 'StructProperty' and sub == 'Vector':
        return kind, 'Vector', struct.pack('<3f', *numbers(3))
    raise AtmosphereError('%s is a %s%s, which a project does not set' % (name, kind, ' ' + sub if sub else ''))


def _enum_of(name):
    # the schema marks a byte property with an enum but does not name it: the one enum member of these structs
    if name == 'DOF_FocusType':
        return 'EFocusType'
    raise AtmosphereError('%s is a byte property of an enum the writer does not know' % name)


def _struct_value(walker, data, start, prop):
    """(value offset, size, struct name) of the struct property `prop` in an export's data, or None."""
    gen = walker.walk(bytes(data), start, len(data))
    try:
        while True:
            name, kind, sub, at, size = next(gen)
            if name == f'{prop}[0]':
                if kind != 'StructProperty':
                    raise AtmosphereError('the WorldInfo saves %s as a %s' % (prop, kind))
                return at, size, sub
    except StopIteration:
        return None


def world_info(p):
    """The persistent level's WorldInfo export index (an XComWorldInfo in XCOM's maps), as atmosphere.read finds it."""
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) in ('WorldInfo', 'XComWorldInfo') and p.name(i).startswith('TheWorld.PersistentLevel.'):
            return i
    raise AtmosphereError('the map has no WorldInfo')


def apply(g, p, lane, kinds=None):
    """The lane made in `g`, the grower of the map `p` (lighting_records.Package): each struct of the WorldInfo made
    again with the lane's members over the members the map saves. Returns the record: dict(worldInfo, fog?,
    postProcess?), each a dict(written: [members, flags included], added: [those the map did not save]); None for no
    lane. Raises AtmosphereError (nothing changed) on a member the struct lacks or a value of another kind."""
    if not lane or not any(lane.get(k) for k in STRUCTS):
        return None
    import atmosphere
    import native_copy
    walker = native_copy.Walker(p, g)
    wi = world_info(p)
    e = p.exports[wi - 1]
    data = bytearray(g.export_data(wi))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    record = dict(worldInfo=p.name(wi))
    every = kinds or member_kinds()
    for key, (prop, struct_name) in STRUCTS.items():
        changes = lane.get(key) or {}
        if not changes:
            continue
        kinds = every[key]
        found = _struct_value(walker, data, start, prop)
        if found and found[2] != struct_name:
            raise AtmosphereError('the WorldInfo saves %s as a %s, not a %s' % (prop, found[2], struct_name))
        inner = bytearray(data[found[0]:found[0] + found[1]]) if found else bytearray(struct.pack('<ii', g.name('None'), 0))
        written, added = [], []
        wanted = []
        for name, value in sorted(changes.items()):
            if name not in kinds or name in NOT_WRITTEN:
                raise AtmosphereError('%s has no member %s a project sets' % (struct_name, name))
            wanted.append((name, value))
            flag = atmosphere.override_flag(name, kinds) if key == 'postProcess' else None
            if flag and flag not in changes:
                wanted.append((flag, True))
        for name, value in wanted:
            kind, sub, raw = value_bytes(g, name, *kinds[name], value)
            inner = native_lights.put(walker, g, inner, 0, name, kind, sub, raw, added, written)
        data = native_lights.set_property(walker, g, data, start, prop, 'StructProperty', struct_name, bytes(inner))
        record[key] = dict(written=written, added=added)
    g.relocate(wi, bytes(data))
    return record


def read_back(q, record, lane):
    """The written map `q` (package.Package) read again: each of the lane's members as the lane says (a colour to its
    byte, a float to its four bytes). Raises AtmosphereError where it isn't so."""
    if not record:
        return
    import atmosphere
    wi = q.by_name.get(record['worldInfo']) or world_info(q)
    for key, (prop, _) in STRUCTS.items():
        if key not in record:
            continue
        raw = q.own(wi, prop)
        saved = atmosphere.members(q, raw) if raw else {}
        for name, value in (lane.get(key) or {}).items():
            got = saved.get(name)
            if isinstance(value, bool) or isinstance(value, str):
                same = got == value
            elif isinstance(value, (int, float)):
                same = isinstance(got, (int, float)) and abs(got - value) <= 1e-4 * max(1.0, abs(value))
            else:
                same = isinstance(got, list) and all(abs(a - b) <= 0.5 / 255 + 1e-6 for a, b in zip(got, value))
            if not same:
                raise AtmosphereError('%s.%s reads back %r, not %r' % (prop, name, got, value))
