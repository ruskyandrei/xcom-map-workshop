"""Effects carried by the piece they stand on (the user, 13 November 2026: "make the skyranger lights move with it").

An effect is an Emitter actor: a placed particle system (fires, rain run-off, a Skyranger's idle lights, a claw
machine's lights). The editor neither shows nor edits them yet, and a project's moved, copied or deleted piece is a
copy and a hide (native_copy.build), so an effect standing on a piece stayed where the piece was. On the tutorial's
Act1_IntroLevel the Skyranger is a loose piece (XComLevelActor_116) with its lights beside it (Emitter_4,
FX_VH_Skyranger.P_Skyranger_Idle); on the battle maps the Skyranger is a prefab whose emitter native_spawns moves with
its landing, but a piece moved by hand left its lights too.

Which piece carries which effect is the export's (export 23's `effects`, scene_metadata.effect_metadata: an effect
in the persistent level whose Location is within 2 units, on every axis, of exactly one mesh piece's own Location);
the compiler passes the pairs on as the native edit's `carriedEffects` ({piece: [effect]}, short names). Here:
- the piece moved (its copy labelled `move:`, the original hidden): the effect moved in place by the same move
  (native_copy.moved_pose), keeping its name;
- the piece copied: the effect cloned at the copy's pose (native_copy.clone_actor) and listed in the level;
- the piece deleted (hidden with no move): the effect taken out of the level's list (native_copy.empty_slots).
An effect at the place of two pieces or more is no piece's (TempleShip's vortex stands at the world's origin with
38 pieces; the tutorial's police lights on a car body and its glass). Across nine maps checked on 13 November the
rule picks every Skyranger's idle lights, URB_Bar's claw machine lights and DEMO_SonOfFacemelt's four water valves.

Since the effects and sounds plan's stage FX3 the editor edits effects as records of their own (the Effects view):
the native edit's `effects` lane ({moves, deletes, copies}: apply), which native_sounds.py runs for the ambient
sounds too and native_flares.py for the lens flares (stage FX6b). A carried effect stays the piece's until the project gives it a record: the compiler leaves those out of
`carriedEffects`. Then:
- a move: the actor posed in place (its Location and Rotation set), keeping its export and everything that names it;
- a delete: the actor's slot in the level's list emptied (native_copy.empty_slots), its export left as it is, so what
  the mission's script names of it still resolves;
- a copy: the actor and everything under it cloned (native_copy.clone_actor: its component, light environment and,
  for a simple sound, its own cue and node), every reference inside the clone pointing at the clone's own, the
  particle system or wave shared; listed in the level.
floor_lists then writes the building floors' m_aCachedEmitters (the effects that hide when the camera cuts a floor
away: plan 2.4) once, against the final effects and floors: an effect the project doesn't touch keeps its listings,
a moved one leaves every list and is listed as a new one is, by each upper floor (index 1 up) one of whose boxes
holds its place within SLACK, and a deleted one leaves them all. Only Emitters are listed. verify reads it all back.

Since stage FX5 a lane also sets values (set_values): an original's in place (the lane's `values`: [{name, effect
or sound}]) and a copy's on its clone (the copy's `values`), never on the source, an archetype or a shared cue:
- an effect's `scale` multiplies the actor's DrawScale as the map has it (its DrawScale3D, an uneven scale, kept);
  `startsOn` is its ParticleSystemComponent's bAutoActivate; `parameters` ([{name, type, value}]) patch its
  InstanceParameters: the first entry of that name has its value field set (Scalar, Vector or Color, by its saved
  type), a name it doesn't save is added at the end as a new entry of `type`, and every other entry, its order and
  its fields stay byte for byte;
- a sound's `radiusMin`, `radiusMax`, `volume` ([VolumeMin, VolumeMax]) and `pitch` ([PitchMin, PitchMax]) are set
  on its own node (SoundNodeInstance: a simple sound's private SoundNodeAmbient), a value its node inherits from an
  archetype written on the node itself; `startsOn` is the actor's bAutoPlay.
Each is written even where it equals the value it overrides, so the edit reads back as made.
"""
import re
import struct

import native_copy

PL = 'TheWorld.PersistentLevel.'
EFFECT_CLASSES = ('Emitter',)
SOUND_CLASSES = ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundMovable')
FLARE_CLASSES = ('LensFlareSource',)
SLACK = 2.0         # buildings.SLACK: how far outside a floor's box a new effect may stand and be listed by it


def template(p, emitter):
    """The particle system an Emitter draws (its path), or None."""
    pc = p.own(emitter, 'ParticleSystemComponent', 0)
    t = p.effective(pc, 'Template', 0) if pc and pc > 0 else 0
    return p.name(t) if t else None


def carried(p, pairs):
    """{piece export: [emitter exports]} from the native edit's `carriedEffects` ({piece: [effect]}, short names);
    names the map lacks, or that are not an Emitter, are left out."""
    out = {}
    for piece, effects in (pairs or {}).items():
        i = p.by_name.get(PL + piece)
        if i is None:
            continue
        found = [p.by_name[PL + e] for e in effects if PL + e in p.by_name and p.cls(p.by_name[PL + e]) == 'Emitter']
        if found:
            out[i] = found
    return out


def _set_pose(walker, g, p, index, location, rotation):
    import native_lights
    e = p.exports[index - 1]
    data = bytearray(g.export_data(index))
    start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_lights.set_property(walker, g, data, start, 'Location', 'StructProperty', 'Vector',
                                      struct.pack('<3f', *location))
    data = native_lights.set_property(walker, g, data, start, 'Rotation', 'StructProperty', 'Rotator',
                                      struct.pack('<3i', *rotation))
    g.relocate(index, bytes(data))


def carry(g, p, copies, hidden, pairs):
    """The effects the moved, copied and deleted pieces carry, made to follow them in `g` (the grower of package `p`).
    `copies`: [(original export, label, before (location, rotation), after (location, rotation))], one for each copy
    native_copy.build made (a label starting `move:` is a move); `hidden`: the exports the edit takes out; `pairs`:
    the native edit's `carriedEffects`. Returns (the
    clones to add to the level's list, the emitters to take out of it, the report: [dict(effect, template, piece,
    how: moved | copied | deleted, location?, rotation?, copy?)])."""
    by_piece = carried(p, pairs)
    if not by_piece:
        return [], set(), []
    walker = native_copy.Walker(p, g)
    hidden = set(hidden)
    clones, gone, report = [], set(), []
    moved = set()
    for original, label, before, after in copies:
        effects = by_piece.get(original)
        if not effects:
            continue
        is_move = original in hidden and str(label or '').startswith('move:') and original not in moved
        if is_move:
            moved.add(original)
        for e in effects:
            loc0 = p.own(e, 'Location', [0.0, 0.0, 0.0])
            rot0 = [int(v) for v in p.own(e, 'Rotation', [0, 0, 0])]
            loc, rot = native_copy.moved_pose(loc0, rot0, before, after)
            rec = dict(effect=p.name(e).rsplit('.', 1)[-1], template=template(p, e),
                       piece=p.name(original).rsplit('.', 1)[-1], location=[round(v, 3) for v in loc], rotation=rot)
            if is_move:
                _set_pose(walker, g, p, e, loc, rot)
                report.append(dict(rec, how='moved'))
            else:
                made = native_copy.clone_actor(g, p, e, loc, rot)
                clones.append(made['actor'])
                report.append(dict(rec, how='copied', copy=made['actor']))
    for original in hidden - moved:
        for e in by_piece.get(original) or []:
            gone.add(e)
            report.append(dict(effect=p.name(e).rsplit('.', 1)[-1], template=template(p, e),
                               piece=p.name(original).rsplit('.', 1)[-1], how='deleted'))
    return clones, gone, report


# ---------------------------------------------------------------- the effects and sounds lanes (plan Part D)
def lane_actor(p, name, classes, listed, what, staged=False):
    """The export of `name` (a short name) in the level: one of `classes`, in the level's actor list, or for
    `staged` (a copy's source another map's actor brought in by transplant.stage_edit: stage FX4) one outside it.
    Raises ValueError for anything else (the compiler checks the same against the export)."""
    i = p.by_name.get(PL + str(name))
    if i is None:
        raise ValueError('the map has no actor %s (%s)' % (name, what))
    if p.cls(i) not in classes:
        raise ValueError('%s is %s, not %s' % (name, p.cls(i), what))
    if staged:
        if i in listed:
            raise ValueError('%s, staged from another map, is in the level\'s actor list' % name)
    elif i not in listed:
        raise ValueError('%s is not in the level\'s actor list' % name)
    return i


# ---------------------------------------------------------------- values (the effects and sounds plan, stage FX5)
# a particle parameter's value field by its saved type: the three kinds the editor writes (plan Part C)
PARAMETER_FIELDS = {'PSPT_Scalar': ('Scalar', 'FloatProperty', None), 'PSPT_Vector': ('Vector', 'StructProperty', 'Vector'),
                    'PSPT_Color': ('Color', 'StructProperty', 'Color')}
SOUND_FIELDS = (('radiusMin', ('RadiusMin',)), ('radiusMax', ('RadiusMax',)), ('volume', ('VolumeMin', 'VolumeMax')),
                ('pitch', ('PitchMin', 'PitchMax')))


def fname(g, text):
    """(name index, number) of `text` as the game keeps a name: a trailing _<digits> is its number (Emitter_46 is
    Emitter, 47), as the package's own names are read back."""
    m = re.fullmatch(r'(.+)_(0|[1-9][0-9]*)', text)
    if m:
        return g.name(m.group(1)), int(m.group(2)) + 1
    return g.name(text), 0


def parameter_raw(type_, value):
    """A parameter value's bytes: a scalar's float, a vector's three floats, a colour's (R, G, B, A, each 0 to 1) as
    the game's Color struct keeps it (B, G, R, A bytes)."""
    if type_ == 'PSPT_Scalar':
        return struct.pack('<f', float(value))
    if type_ == 'PSPT_Vector':
        return struct.pack('<3f', *[float(v) for v in value])
    if type_ == 'PSPT_Color':
        r, g_, b, a = [max(0, min(255, int(round(float(v) * 255)))) for v in value]
        return bytes((b, g_, r, a))
    raise ValueError('a parameter of type %s is not written' % type_)


def _fields(walker, b):
    """{property: (kind, value offset, size)} of a struct element's tags (b holds the element alone)."""
    out = {}
    for prop, kind, sub, at, size in walker.walk(bytes(b), 0, len(b)):
        out[prop] = (kind, at, size)
    return out


def _element_key(walker, b):
    """(name, type) of a ParticleSysParam element (bytes of its tags): its Name (None when it saves none) and its
    ParamType (PSPT_None when it saves none)."""
    f = _fields(walker, b)
    name = walker.name_at(b, f['Name[0]'][1]) if 'Name[0]' in f else None
    kind = walker.name_at(b, f['ParamType[0]'][1]) if 'ParamType[0]' in f else 'PSPT_None'
    return name, kind


def new_parameter(g, name, type_, raw):
    """A new ParticleSysParam element's tags, in the order the game's maps save them: Name, ParamType, the value."""
    field, kind, sub = PARAMETER_FIELDS[type_]

    def tag(n, k, size, extra=b''):
        return struct.pack('<iiiiii', g.name(n), 0, g.name(k), 0, size, 0) + extra
    return (tag('Name', 'NameProperty', 8) + struct.pack('<ii', *fname(g, name))
            + tag('ParamType', 'ByteProperty', 8, struct.pack('<ii', g.name('EParticleSysParamType'), 0))
            + struct.pack('<ii', g.name(type_), 0)
            + tag(field, kind, len(raw), struct.pack('<ii', g.name(sub), 0) if sub else b'') + raw
            + struct.pack('<ii', g.name('None'), 0))


def set_parameters(walker, g, data, start, params):
    """`data` (a ParticleSystemComponent's bytes, tagged properties from `start`) with its InstanceParameters patched
    by `params` ([dict(name, type, value)]): the first entry of a name has its value field set in place (its saved
    type must be `type`), a name it doesn't save is added at the end. Entries not named stay byte for byte, and an
    unchanged value leaves the bytes as they were. Returns the bytes."""
    import native_lights
    data = bytes(data)
    found = native_copy.find_prop(walker, data, start, len(data), 'InstanceParameters[0]')
    pieces = [data[a:b] for a, b in native_copy.struct_elements(walker, data, found[2], found[3])] if found else []
    keys = [_element_key(walker, piece) for piece in pieces]
    for prm in params:
        type_, raw = prm['type'], parameter_raw(prm['type'], prm['value'])
        field, kind, sub = PARAMETER_FIELDS[type_]
        k = next((j for j, (n, _) in enumerate(keys) if n == prm['name']), None)
        if k is None:
            pieces.append(new_parameter(g, prm['name'], type_, raw))
            keys.append((prm['name'], type_))
            continue
        if keys[k][1] != type_:
            raise ValueError('parameter %s is saved as %s, not %s' % (prm['name'], keys[k][1], type_))
        pieces[k] = bytes(native_lights.set_property(walker, g, pieces[k], 0, field, kind, sub, raw))
    if found:
        return native_copy.rebuilt(data, found, pieces)
    if not pieces:
        return data
    gen = walker.walk(data, start, len(data))
    try:
        while True:
            next(gen)
    except StopIteration as done:
        end = done.value
    payload = struct.pack('<i', len(pieces)) + b''.join(pieces)
    tag = struct.pack('<iiiiii', g.name('InstanceParameters'), 0, g.name('ArrayProperty'), 0, len(payload), 0)
    return data[:end - 8] + tag + payload + data[end - 8:]


def _set(walker, g, p, target, source, sets):
    """Tagged properties `sets` ([(name, kind, struct, raw)]) written on export `target` of `g`, whose bytes are laid
    out as export `source` of `p` (an original: itself; a clone: its source)."""
    import native_lights
    e = p.exports[source - 1]
    start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
    data = bytearray(g.export_data(target))
    for name, kind, sub, raw in sets:
        data = native_lights.set_property(walker, g, data, start, name, kind, sub, raw)
    g.relocate(target, bytes(data))


def set_values(g, p, source, kind, values, mapping=None):
    """An effect's or sound's `values` (kind 'effect' or 'sound') written in `g`, the grower of `p`: on the actor
    `source` itself (an original's edit, in place), or with `mapping` ({source export: clone export},
    native_copy.clone_actor's) on its clone. What it writes to is the actor's own (its component, its node): never
    the source of a clone, an archetype or a cue asset. Returns what was written (dict: drawScale, startsOn,
    parameters, radiusMin, radiusMax, volume, pitch), as check_values reads it back."""
    walker = native_copy.Walker(p, g)
    mapping = mapping or {}

    def own(i):
        return mapping.get(i) if mapping else i
    actor = own(source)
    written = {}
    under = set(native_copy.subtree(p, source))

    def owned(index, what):
        if not index or index <= 0 or index not in under or own(index) is None:
            raise ValueError('%s has no %s of its own to write its values on' % (p.name(source), what))
        return own(index)
    if kind == 'effect':
        if values.get('scale') is not None:
            draw = float(p.effective(source, 'DrawScale', 1.0) or 1.0) * float(values['scale'])
            _set(walker, g, p, actor, source, [('DrawScale', 'FloatProperty', None, struct.pack('<f', draw))])
            written['drawScale'] = struct.unpack('<f', struct.pack('<f', draw))[0]
        if values.get('startsOn') is not None or values.get('parameters'):
            comp = p.effective(source, 'ParticleSystemComponent', 0)
            target = owned(comp, 'particle component')
            if values.get('startsOn') is not None:
                _set(walker, g, p, target, comp,
                     [('bAutoActivate', 'BoolProperty', None, bytes((int(bool(values['startsOn'])),)))])
                written['startsOn'] = bool(values['startsOn'])
            if values.get('parameters'):
                e = p.exports[comp - 1]
                start = native_copy.legacy_props.props_start(p.data, e, p.names) - e['off']
                g.relocate(target, set_parameters(walker, g, g.export_data(target), start, values['parameters']))
                written['parameters'] = [dict(name=x['name'], type=x['type'], value=x['value'])
                                         for x in values['parameters']]
        return written
    if kind != 'sound':
        raise ValueError("values are an effect's or a sound's: a lens flare has none to set" if kind == 'flare'
                         else "values are an effect's or a sound's, not a %s's" % kind)
    if values.get('startsOn') is not None:
        _set(walker, g, p, actor, source,
             [('bAutoPlay', 'BoolProperty', None, bytes((int(bool(values['startsOn'])),)))])
        written['startsOn'] = bool(values['startsOn'])
    sets = []
    for key, props in SOUND_FIELDS:
        v = values.get(key)
        if v is None:
            continue
        v = [v] if len(props) == 1 else list(v)
        sets += [(prop, 'FloatProperty', None, struct.pack('<f', float(x))) for prop, x in zip(props, v)]
        written[key] = v[0] if len(props) == 1 else v
    if sets:
        node = p.effective(source, 'SoundNodeInstance', 0)
        _set(walker, g, p, owned(node, 'sound node'), node, sets)
    return written


def read_values(q, actor, kind):
    """What set_values writes, as the written map `q` (package.Package) reads it back: drawScale, startsOn,
    parameters ({name: dict(type, scalar, vector, colour)}, the first entry of each name), radiusMin, radiusMax,
    volume, pitch."""
    out = {}
    if kind == 'effect':
        out['drawScale'] = q.own(actor, 'DrawScale', 1.0)
        comp = q.own(actor, 'ParticleSystemComponent', 0)
        if comp and comp > 0:
            out['startsOn'] = q.own(comp, 'bAutoActivate')
            out['parameters'] = {}
            raw = q.own(comp, 'InstanceParameters')
            for row in q.structs(raw) if raw else []:
                f = {k[0]: v['value'] for k, v in row.items() if k[1] == 0}
                name = f.get('Name')
                if name is not None and str(name) not in out['parameters']:
                    out['parameters'][str(name)] = dict(type=str(f.get('ParamType', 'PSPT_None')), scalar=f.get('Scalar'),
                                                        vector=f.get('Vector'), colour=f.get('Color'))
        return out
    out['startsOn'] = q.own(actor, 'bAutoPlay')
    node = q.own(actor, 'SoundNodeInstance', 0)
    if node and node > 0:
        for key, props in SOUND_FIELDS:
            v = [q.own(node, prop) for prop in props]
            out[key] = v[0] if len(props) == 1 else v
    return out


def check_values(q, actor, kind, written, what):
    """Raise ValueError unless the written map `q` reads back on `actor` what set_values wrote (`written`)."""
    got = read_values(q, actor, kind)

    def close(a, b):
        return a is not None and abs(float(a) - float(b)) <= 1e-4 * max(1.0, abs(float(b)))
    for key, want in written.items():
        if key == 'parameters':
            for prm in want:
                have = got.get('parameters', {}).get(prm['name'])
                if not have or have['type'] != prm['type']:
                    raise ValueError('%s: parameter %s reads back as %s' % (what, prm['name'], have))
                if prm['type'] == 'PSPT_Color':
                    value = have['colour']
                    ok = value is not None and all(abs(float(a) - round(float(b) * 255) / 255) < 1e-3
                                                   for a, b in zip(value, prm['value']))
                elif prm['type'] == 'PSPT_Vector':
                    value = have['vector']
                    ok = value is not None and all(close(a, b) for a, b in zip(value, prm['value']))
                else:
                    value = have['scalar']
                    ok = close(value, prm['value'])
                if not ok:
                    raise ValueError('%s: parameter %s reads back %s, not %s' % (what, prm['name'], value, prm['value']))
        elif key == 'startsOn':
            if bool(got.get(key)) != want:
                raise ValueError('%s: %s reads back %s, not %s' % (what, key, got.get(key), want))
        elif isinstance(want, list):
            if not got.get(key) or not all(close(a, b) for a, b in zip(got[key], want)):
                raise ValueError('%s: %s reads back %s, not %s' % (what, key, got.get(key), want))
        elif not close(got.get(key), want):
            raise ValueError('%s: %s reads back %s, not %s' % (what, key, got.get(key), want))


def pose_of(p, i):
    return ([float(v) for v in p.own(i, 'Location', [0.0, 0.0, 0.0])],
            [int(v) for v in p.own(i, 'Rotation', [0, 0, 0])])


def apply(g, p, ops, classes=EFFECT_CLASSES, what='an effect'):
    """A lane of the native edit (the compiler's `effects`, `sounds` or `flares`: {moves: [{name, location, rotation}],
    deletes: [{name}], copies: [{id, name, source, location, rotation, values?}], values: [{name, effect | sound}]})
    made in `g`, the grower of package `p`. Returns (the clones to add to the level's list, the actors to take out of
    it, the record: [dict(actor, how: moved | deleted | copied | valued, export, cls, location?, rotation?, before?,
    id?, source?, mapping?, values?)]): `values` what set_values wrote."""
    if not ops or not any(ops.get(k) for k in ('moves', 'deletes', 'copies', 'values')):
        return [], set(), []
    kind = ('effect' if tuple(classes) == EFFECT_CLASSES else 'flare' if tuple(classes) == FLARE_CLASSES else 'sound')
    walker = native_copy.Walker(p, g)
    listed = set(native_copy.level_actors(p))
    edited, clones, gone, record = set(), [], set(), []
    for m in ops.get('moves') or []:
        i = lane_actor(p, m['name'], classes, listed, what)
        if i in edited:
            raise ValueError('%s is moved or deleted twice' % m['name'])
        edited.add(i)
        loc, rot = [float(v) for v in m['location']], [int(v) for v in m['rotation']]
        before = pose_of(p, i)
        _set_pose(walker, g, p, i, loc, rot)
        record.append(dict(actor=m['name'], how='moved', export=i, cls=p.cls(i), location=loc, rotation=rot,
                           before=dict(location=before[0], rotation=before[1])))
    for d in ops.get('deletes') or []:
        i = lane_actor(p, d['name'], classes, listed, what)
        if i in edited:
            raise ValueError('%s is moved or deleted twice' % d['name'])
        edited.add(i)
        gone.add(i)
        record.append(dict(actor=d['name'], how='deleted', export=i, cls=p.cls(i)))
    for c in ops.get('copies') or []:
        i = lane_actor(p, c['source'], classes, listed, what, staged=bool(c.get('staged')))
        loc, rot = [float(v) for v in c['location']], [int(v) for v in c['rotation']]
        made = native_copy.clone_actor(g, p, i, loc, rot)
        clones.append(made['actor'])
        # its values on the clone's own exports (the source and what it shares untouched)
        written = set_values(g, p, i, kind, c['values'], made['mapping']) if c.get('values') else None
        record.append(dict(actor=c['name'], id=c.get('id'), source=c['source'], how='copied', export=made['actor'],
                           cls=p.cls(i), location=loc, rotation=rot, mapping=made['mapping'],
                           **({'donor': c['donor']} if c.get('donor') else {}),
                           **({'values': written} if written else {})))
    for v in ops.get('values') or []:
        i = lane_actor(p, v['name'], classes, listed, what)
        if i in gone:
            raise ValueError('%s is deleted and given values' % v['name'])
        written = set_values(g, p, i, kind, v.get(kind) or {})
        record.append(dict(actor=v['name'], how='valued', export=i, cls=p.cls(i), values=written))
    return clones, gone, record


def _box(b):
    """A floor box as dict(min, max), from one or from [x0, y0, z0, x1, y1, z1]."""
    if isinstance(b, dict):
        return dict(min=[float(v) for v in b['min']], max=[float(v) for v in b['max']])
    return dict(min=[float(v) for v in b[:3]], max=[float(v) for v in b[3:]])


def holds(boxes, at, slack=SLACK):
    return any(all(b['min'][a] - slack <= at[a] <= b['max'][a] + slack for a in range(3)) for b in boxes)


def floor_lists(g, p, moved, new, deleted, edits=(), made=()):
    """The building floors' m_aCachedEmitters written once, against the final effects and floors (plan Part D):
    `moved` and `new` ({emitter export: its location now}) leave every list and are listed by each upper floor
    (index 1 up) one of whose boxes holds them within SLACK; `deleted` (emitter exports) leave every list; any other
    effect keeps its listings. A floor's boxes are the project's for a building it edits in place (`edits`, the
    compiler's buildingEdits; a deleted one is left alone) or makes from nothing (`made`, buildings.make's records),
    else its floor volumes' as the map has them. Run after every other writer of the floors. Returns [dict(effect
    (export), building (export), floor, how: joined | left)]."""
    import buildings
    import scene_metadata
    leaving = set(moved) | set(deleted)
    joining = dict(moved)
    joining.update(new)
    if not leaving and not joining:
        return []
    walker = native_copy.Walker(p, g)
    level = p.by_name['TheWorld.PersistentLevel']
    edited = {}
    for e in edits or ():
        i = p.by_name.get(PL + e['actor'])
        if i is not None:
            edited[i] = None if e.get('deleted') else [[_box(x) for x in f['boxes']] for f in e['floors']]
    targets = []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'XComBuildingVolume' or p.exports[i - 1]['outer'] != level:
            continue
        if i in edited and edited[i] is None:
            continue
        targets.append((i, buildings.start_of(p, i), edited.get(i)))
    template = None
    for r in made or ():
        if template is None:
            template = buildings.building_template(p, native_copy.Walker(p, g))
        targets.append((r['building'], buildings.start_of(p, template['actor']),
                        [[_box(x) for x in f['boxes']] for f in r['floors']]))
    report = []
    for i, start, boxes in targets:
        b = g.export_data(i)
        found = native_copy.find_prop(walker, b, start, len(b), 'Floors[0]')
        if found is None:
            continue
        parts, changed = [], False
        for k, (s0, e0) in enumerate(native_copy.struct_elements(walker, b, found[2], found[3])):
            element = bytes(b[s0:e0])
            have = native_copy.object_array(walker, element, 0, 'm_aCachedEmitters')
            if boxes is None:
                vols = native_copy.find_prop(walker, element, 0, len(element), 'FloorVolumes[0]')
                refs = struct.unpack_from('<%di' % struct.unpack_from('<i', element, vols[2])[0], element,
                                          vols[2] + 4) if vols else ()
                floor = [x for x in (scene_metadata.volume_bounds(p, r) for r in refs if 0 < r <= len(p.exports)) if x]
            else:
                floor = boxes[k] if k < len(boxes) else []
            keep = [v for v in have if v not in leaving]
            keep += [v for v, at in sorted(joining.items()) if k >= 1 and v not in keep and holds(floor, at)]
            if keep == have:
                parts.append(element)
                continue
            report += [dict(effect=v, building=i, floor=k, how='left') for v in have if v not in keep]
            report += [dict(effect=v, building=i, floor=k, how='joined') for v in keep if v not in have]
            field = native_copy.find_prop(walker, element, 0, len(element), 'm_aCachedEmitters[0]')
            parts.append(native_copy.with_array(g, element, (0, len(element)), field, 'm_aCachedEmitters',
                                                [struct.pack('<i', v) for v in keep]))
            changed = True
        if changed:
            g.relocate(i, native_copy.rebuilt(b, found, parts))
    return report


def verify(q, record, floors=()):
    """The lanes read back from the written map `q` (package.Package): a moved actor at its pose and still listed, a
    deleted one off the level's list, a copy listed, of its source's class, everything under it the clone's own and
    nothing in it pointing into its source's subtree; each floor change in its floor's m_aCachedEmitters. Raises
    ValueError at the first thing that isn't so."""
    import props as legacy_props
    listed = set(native_copy.level_actors(q))
    walker = native_copy.Walker(q)
    for r in record:
        i = r['export']
        if r['how'] == 'moved':
            loc, rot = pose_of(q, i)
            if any(abs(a - b) > 1e-3 for a, b in zip(loc, r['location'])) or rot != list(r['rotation']):
                raise ValueError('%s reads back at %s %s, not %s %s' % (r['actor'], loc, rot, r['location'], r['rotation']))
            if i not in listed:
                raise ValueError('%s moved but is off the level\'s list' % r['actor'])
        elif r['how'] == 'deleted':
            if i in listed:
                raise ValueError('%s deleted but still in the level\'s list' % r['actor'])
        elif r['how'] == 'valued':
            if i not in listed:
                raise ValueError('%s given values but is off the level\'s list' % r['actor'])
        else:
            if i not in listed or q.cls(i) != r['cls']:
                raise ValueError('copy %s is not a listed %s' % (r['actor'], r['cls']))
            loc, rot = pose_of(q, i)
            if any(abs(a - b) > 1e-3 for a, b in zip(loc, r['location'])) or rot != list(r['rotation']):
                raise ValueError('copy %s reads back at %s %s, not %s %s' % (r['actor'], loc, rot, r['location'], r['rotation']))
            source = {int(k) for k in r['mapping']}
            mine = {int(v) for v in r['mapping'].values()}
            for n in mine:
                e = q.exports[n - 1]
                if n != i and e['outer'] not in mine:
                    raise ValueError('%s of copy %s is not under the copy' % (q.name(n), r['actor']))
                data = bytes(q.data[e['off']:e['off'] + e['size']])
                start = legacy_props.props_start(q.data, e, q.names) - e['off']
                for prop, ref in walker.refs(data, start, len(data)):
                    if struct.unpack_from('<i', data, ref)[0] in source:
                        raise ValueError('%s of copy %s points into its source (%s)' % (q.name(n), r['actor'], prop))
        if r.get('values'):
            check_values(q, i, 'effect' if r['cls'] in EFFECT_CLASSES else 'sound', r['values'], r['actor'])
    lists = {}
    for f in floors or ():
        if f['building'] not in lists:
            rows = q.structs(q.own(f['building'], 'Floors'))
            lists[f['building']] = [set(q.refs(row[('m_aCachedEmitters', 0)]['value']))
                                    if ('m_aCachedEmitters', 0) in row else set() for row in rows]
        there = f['effect'] in lists[f['building']][f['floor']]
        if there != (f['how'] == 'joined'):
            raise ValueError('%s %s floor %d of %s, but reads back %s' % (
                q.name(f['effect']), f['how'], f['floor'], q.name(f['building']), 'listed' if there else 'unlisted'))
