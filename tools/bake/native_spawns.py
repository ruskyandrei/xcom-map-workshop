"""The map's own landings moved in place (private/plans/done/clear-map-plan.md, section 4; findings register F-96 to
F-98): what a plain Enemy Within install plays, and what LWR's landing-zone mutator spawns its landing from.

A project's landing zones (the compiler's `landingZones`: {zones, own, ownLandings}) name, by `own`, the zones that are
also the map's own landings: the first own slot is the map's first landing (its group by the game's order, export 22),
the second the second. Each such zone that puts the landing somewhere else than the map has it moves the landing's
prefab's actors in place, by the offsets of LWR's mutator (XComLZMutator.CalcLocations; tools/viewer/spawns.py), so
that both installs land the squad at the same place:
- the drop zone's frame to the zone's place, turned by the zone's direction;
- the evac volume, the player start and the PointInSpace to their offsets, each turned as the mutator turns them
  (AdjRotation: the zone's turn plus its own yaw less the frame's). The evac volume saves Rotation (0, 0, 0), its turn
  being baked into its brush (F-98), so it is written the zone's turn less the frame's;
- the six soldier points to their offsets, facing a quarter turn on (FaceRot);
- the grounded Skyranger next to the landing (its prefab's mesh, emitter, sound and PointInSpace) by the same rigid
  move as the frame: from the frame's old place and turn to its new ones.
A landing with no frame (the tutorial's, TempleShip's, the alien bases') is the zone spawns.fit_zone fits to its soldier
points; while the zone stays there nothing moves, and moved, its actors go to the zone's offsets as any landing's do
(its own layout is not kept), the Skyranger from where the fitted zone's frame would stand.
Every actor keeps its name and archetype (LWR finds its templates by archetype; the mission script's show-or-hide
switch names the Skyranger and the frame). A player start based on another actor gets its RelativeLocation anew.
The Skyranger is in the baked tile data: a rebuild volume goes over its old place and its new one, which is seeded as
a copy's is.

A full Build's relight sees the move (F-98): native_copy.py hands each moved piece with a mesh to relight.py as
moved in place (--moved-in-place, with its old pose), so its shadow leaves the old place and falls at the new one. Its
own lightmap and shadow maps keep their bake.

  python -B tools/bake/native_spawns.py <map.upk> <native-edit.json> <out.upk>   (a check: the moves on their own)
"""
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import props as legacy_props  # noqa: E402
import scene_metadata  # noqa: E402
import spawns  # noqa: E402

TURN = 65536
SAME = 4.0     # a zone whose frame and soldiers are this near the landing's own is the landing unmoved


def norm(yaw):
    """A yaw in (-32768, 32768]."""
    yaw = int(round(yaw)) % TURN
    return yaw - TURN if yaw > TURN // 2 else yaw


def unmoved(landing, zone, bottom=None):
    """Whether the zone puts the landing where the map has it: its frame and six soldier points within SAME units,
    the frame's turn the zone's."""
    by = {a['role']: a for a in landing['actors']}
    at = spawns.place(zone)
    frame = by.get('frame')
    if frame is None:
        fitted = spawns.fit_zone(landing['actors'], bottom)
        return fitted is not None and spawns.at_own_place(zone, dict(zone=fitted))
    if norm(frame['rotation'][1] - at['frame'][1]) != 0:
        return False
    pairs = [(frame['location'], at['frame'][0])] + [(by['soldier%d' % (k + 1)]['location'], at['soldiers'][k][0])
                                                     for k in range(6) if 'soldier%d' % (k + 1) in by]
    return all(all(abs(a[j] - b[j]) <= SAME for j in range(3)) for a, b in pairs)


def plan(landings, zones, bottom=None):
    """The moves for a project's zones ({zones, own}): [dict(landing (its prefab), group, zone (its id), actors:
    [dict(path, role, old: (location, rotation), new: (location, rotation), relative?)])], one for each own slot
    whose zone moves its landing. `landings` is scene_metadata.landing_metadata's list, in the game's order;
    `bottom` the tile grid's (a landing with no frame is fitted on it: spawns.fit_zone)."""
    out = []
    for k, slot in enumerate(zones.get('own') or []):
        if k >= len(landings):
            break
        landing, zone = landings[k], zones['zones'][slot]
        by = {a['role']: a for a in landing['actors']}
        here = spawns.frame_of(landing, bottom)
        if here is None or unmoved(landing, zone, bottom):
            continue
        at = spawns.place(zone)
        frame = by.get('frame')
        f_loc, f_yaw = here
        z_yaw = spawns.yaw_of(zone['direction'])
        actors = []

        def move(a, location, yaw):
            actors.append(dict(path=a['path'], role=a['role'], actorClass=a['actorClass'], savesRotation=a['savesRotation'],
                               old=(list(a['location']), list(a['rotation'])),
                               new=([round(v, 4) for v in location], [a['rotation'][0], norm(yaw), a['rotation'][2]])))
        if frame:
            move(frame, at['frame'][0], z_yaw)
        for role in ('volume', 'playerStart', 'point'):
            if role in by:
                a = by[role]
                move(a, at[role][0], z_yaw + a['rotation'][1] - f_yaw)
        for n in range(6):
            a = by.get('soldier%d' % (n + 1))
            if a:
                move(a, at['soldiers'][n][0], at['soldiers'][n][1])
        sky = landing.get('skyranger')
        if sky:
            turn = z_yaw - f_yaw
            for a in sky['actors']:
                d = spawns.turn([a['location'][j] - f_loc[j] for j in range(3)], turn)
                move(a, [at['frame'][0][j] + d[j] for j in range(3)], a['rotation'][1] + turn)
        out.append(dict(landing=landing['prefab'], group=landing.get('group'), index=k, zone=zone['id'], slot=slot,
                        frame=dict(old=[list(f_loc), f_yaw], new=[list(at['frame'][0]), z_yaw]),
                        skyranger=sky['prefab'] if sky else None, actors=actors))
    return out


def _set(walker, g, p, index, location=None, rotation=None, relative=None):
    import native_lights
    e = p.exports[index - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    if location is not None:
        data = native_lights.set_property(walker, g, data, start, 'Location', 'StructProperty', 'Vector',
                                          struct.pack('<3f', *location))
    if rotation is not None:
        data = native_lights.set_property(walker, g, data, start, 'Rotation', 'StructProperty', 'Rotator',
                                          struct.pack('<3i', *rotation))
    if relative is not None:
        data = native_lights.set_property(walker, g, data, start, 'RelativeLocation', 'StructProperty', 'Vector',
                                          struct.pack('<3f', *relative))
    g.relocate(index, bytes(data))


def apply(g, p, zones, gone=()):
    """The project's own landings moved in the map (`g` the grower of package `p`): returns (the report: the moves,
    each actor's old and new pose, and the tiles; the rebuild volumes to add to the level). `gone`: actors the edit
    takes out (never moved)."""
    import native_copy
    walker = native_copy.Walker(p)
    moves = plan(scene_metadata.landing_metadata(p), zones, native_copy.level_grid(p)['oz'])
    volumes, report = [], []
    for m in moves:
        tiles = []
        for a in m['actors']:
            i = p.by_name[a['path']]
            if i in gone:
                a['skipped'] = 'taken out by the edit'
                continue
            (loc0, rot0), (loc1, rot1) = a['old'], a['new']
            rotation = rot1 if (a['savesRotation'] or rot1 != rot0) else None
            relative = None
            if p.cls(i) == 'PlayerStart' and p.own(i, 'RelativeLocation') is not None:
                base = p.own(i, 'Base', 0)
                if base > 0:
                    b_loc, b_yaw = p.own(base, 'Location', [0.0, 0.0, 0.0]), (p.own(base, 'Rotation') or [0, 0, 0])[1]
                    relative = spawns.turn([loc1[j] - b_loc[j] for j in range(3)], -b_yaw)
                    a['relative'] = [round(v, 4) for v in relative]
            _set(walker, g, p, i, loc1, rotation, relative)
            # a piece in the baked tiles (the Skyranger): its old tiles rebuilt, its new ones seeded and rebuilt
            if native_copy.has_mesh(p, i) and native_copy.collides(p, i):
                old = native_copy.hide_tiles(g, p, native_copy.piece_box(p, i, loc0, rot0))
                new = native_copy.add_tiles_box(g, p, native_copy.piece_box(p, i, loc1, rot1))
                for t in (old, new):
                    if t:
                        volumes.append(t['volume']['export'])
                tiles.append(dict(actor=a['path'].split('.')[-1], old=old['tiles'] if old else None,
                                  new=new['tiles'] if new else None, seeded=new['seeded'] if new else 0))
        report.append(dict(m, tiles=tiles))
    return report, volumes


# ---------------------------------------------------------------- the base map's spawn points (editor spawns plan, SP6)
# The native edit's `spawns` lane: {moves: [{name, location, rotation}], values: [{name, spawn}], deletes, copies}
# (copies and deletes are stage SP7's). A point keeps its export, name, archetype and everything that names it: a move
# sets its Location (and its Rotation where it saves one or turns), a based point's RelativeLocation from its base's
# final place; a value sets one property on the actor itself, adding the tag where the actor saves none.
# A value's property, its type and, for a byte, its enum (Bar's hard Meld points save m_eDifficulty as an
# EMeldContainerDifficulty name; pods save none of their flags, which then take a bool tag as other writers' do)
SPAWN_VALUES = {
    'commander': ('bCommanderPod', 'BoolProperty', None),
    'secondary': ('bSecondaryPod', 'BoolProperty', None),
    'use': ('bUse', 'BoolProperty', None),
    'difficulty': ('m_eDifficulty', 'ByteProperty', 'EMeldContainerDifficulty'),
    'destroyedOnTurn': ('m_iDestroyedOnTurn', 'IntProperty', None),
    'spawnGroup': ('m_iSpawnGroup', 'IntProperty', None),
    # a pod's copy's own index (SP7), never a value a project sets
    'podIndex': ('PodIndex', 'IntProperty', None),
}
VALUE_KINDS = {'pod': ('commander', 'secondary', 'use'), 'meld': ('difficulty', 'destroyedOnTurn', 'spawnGroup'),
               'dropIn': ()}
DIFFICULTY_PREFIX = 'eMeldContainerDifficulty_'
PL = 'TheWorld.PersistentLevel.'


def spawn_kind(cls):
    """'pod', 'meld' or 'dropIn' for the classes the lane edits (scene_metadata.spawn_family's), else None."""
    if cls.startswith('XComAlienPod'): return 'pod'
    if cls == 'XComMeldContainerSpawnPoint': return 'meld'
    if cls == 'XComSpawnPoint_Alien': return 'dropIn'
    return None


def lane_actor(p, name, listed):
    """The export of spawn point `name` (a short name): a pod, Meld point or drop-in point in the level's actor list;
    ValueError for anything else (the compiler checks the same against the export)."""
    i = p.by_name.get(PL + str(name))
    if i is None:
        raise ValueError('the map has no actor %s (a spawn point)' % name)
    if spawn_kind(p.cls(i)) is None:
        raise ValueError('%s is %s, not a pod, Meld point or drop-in point' % (name, p.cls(i)))
    if i not in listed:
        raise ValueError('%s is not in the level\'s actor list' % name)
    return i


def value_bytes(g, key, value):
    """(property, type, enum, value bytes) of a spawn value: a bool as one byte, a whole number as 4, the Meld
    difficulty ('Easy' or 'Hard') as its enum value's name in `g`'s name table."""
    prop, kind, sub = SPAWN_VALUES[key]
    if kind == 'BoolProperty':
        return prop, kind, sub, bytes([1 if value else 0])
    if kind == 'IntProperty':
        return prop, kind, sub, struct.pack('<i', int(value))
    return prop, kind, sub, struct.pack('<ii', g.name(DIFFICULTY_PREFIX + str(value)), 0)


def set_values(g, p, index, values, walker, like=None, pod_index=None):
    """A spawn point's values ({commander, secondary, use} for a pod, {difficulty, destroyedOnTurn, spawnGroup} for a
    Meld point) written on actor `index` of `g`, the grower of `p`. A copy (SP7) is `index` in `g` laid out as its
    template `like` of `p`, and a pod's copy gets `pod_index` (its PodIndex). Returns what was written."""
    import native_lights
    like = like or index
    kind = spawn_kind(p.cls(like))
    wrong = sorted(set(values) - set(VALUE_KINDS.get(kind) or ()))
    if wrong:
        raise ValueError('%s (%s) has no value %s' % (p.name(like), p.cls(like), ', '.join(wrong)))
    values = dict(values)
    if pod_index is not None:
        if kind != 'pod':
            raise ValueError('%s (%s) is no pod, so it has no pod index' % (p.name(like), p.cls(like)))
        values['podIndex'] = int(pod_index)
    e = p.exports[like - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    written = {}
    for key in sorted(values):
        prop, ptype, sub, raw = value_bytes(g, key, values[key])
        data = native_lights.set_property(walker, g, data, start, prop, ptype, sub, raw)
        written[key] = values[key]
    g.relocate(index, bytes(data))
    return written


def apply_lane(g, p, ops):
    """The `spawns` lane made in `g`, the grower of `p`: returns (the clones to add to the level's list, the actors to
    take out of it, the record: [dict(actor, how: moved | valued | deleted | copied, export, cls, location?, rotation?,
    before?, relative?, values?, id?, source?, template?, podIndex?)]), as native_effects.apply returns its own. A copy
    (SP7) is its template cloned with its components (native_copy.clone_actor), placed, given its pod index (a pod's)
    and its values; a delete leaves its slot in the level's list empty (native_copy.empty_slots, by the caller)."""
    if not ops or not any(ops.get(k) for k in ('moves', 'values', 'deletes', 'copies')):
        return [], set(), []
    import buildings
    import native_copy
    walker = buildings.grown_walker(p, g)
    listed = set(native_copy.level_actors(p))
    record, moved, gone, clones = [], {}, set(), []
    for m in ops.get('moves') or []:
        i = lane_actor(p, m['name'], listed)
        if i in moved:
            raise ValueError('%s is moved twice' % m['name'])
        loc, rot = [float(v) for v in m['location']], [int(v) for v in m['rotation']]
        before = ([float(v) for v in p.own(i, 'Location', [0.0, 0.0, 0.0])], [int(v) for v in p.own(i, 'Rotation', [0, 0, 0])])
        moved[i] = (loc, rot)
        record.append(dict(actor=m['name'], how='moved', export=i, cls=p.cls(i), location=loc, rotation=rot,
                           before=dict(location=before[0], rotation=before[1])))
    for r in record:
        i, (loc, rot) = r['export'], moved[r['export']]
        rotation = rot if (p.own(i, 'Rotation') is not None or rot != r['before']['rotation']) else None
        relative = _relative(p, i, loc, moved)
        if relative is not None:
            r['relative'] = [round(v, 4) for v in relative]
        _set(walker, g, p, i, loc, rotation, relative)
    valued = set()
    for v in ops.get('values') or []:
        i = lane_actor(p, v['name'], listed)
        valued.add(i)
        written = set_values(g, p, i, v.get('spawn') or {}, walker)
        record.append(dict(actor=v['name'], how='valued', export=i, cls=p.cls(i), values=written))
    for d in ops.get('deletes') or []:
        i = lane_actor(p, d['name'], listed)
        if i in moved or i in valued or i in gone:
            raise ValueError('%s is deleted and also moved, given values or deleted again' % d['name'])
        gone.add(i)
        record.append(dict(actor=d['name'], how='deleted', export=i, cls=p.cls(i)))
    events = scene_metadata.pod_events(p) if any(c.get('podIndex') is not None for c in ops.get('copies') or []) else {}
    for c in ops.get('copies') or []:
        i = lane_actor(p, c['source'], listed)
        if i in gone:
            raise ValueError('%s copies %s, which the edit deletes' % (c['name'], c['source']))
        kind = spawn_kind(p.cls(i))
        if kind not in ('pod', 'meld') or (c.get('kind') and c['kind'] != kind):
            raise ValueError('%s copies %s (%s): only pods and Meld points are copied' % (c['name'], c['source'], p.cls(i)))
        index = c.get('podIndex')
        if kind == 'pod' and (not isinstance(index, int) or isinstance(index, bool)):
            raise ValueError('%s is a copy of a pod and has no pod index' % c['name'])
        if kind == 'pod' and index in events:
            raise ValueError('%s would take pod index %d, which a pod event of the map names' % (c['name'], index))
        loc, rot = [float(v) for v in c['location']], [int(v) for v in c['rotation']]
        made = native_copy.clone_actor(g, p, i, loc, rot)
        n = made['actor']
        relative = _relative(p, i, loc, moved)
        if relative is not None:
            _set_like(walker, g, p, n, i, relative)
        written = set_values(g, p, n, c.get('spawn') or {}, walker, like=i, pod_index=index if kind == 'pod' else None)
        clones.append(n)
        record.append(dict(actor=c['name'], id=c.get('id'), source=c['source'], how='copied', export=n, template=i,
                           mapping=made['mapping'],
                           cls=p.cls(i), location=loc, rotation=rot, values=written,
                           **({'podIndex': index} if kind == 'pod' else {}),
                           **({'relative': [round(v, 4) for v in relative]} if relative is not None else {})))
    return clones, gone, record


def _relative(p, i, loc, moved):
    """A based actor's relative place for world place `loc`, worked from where its base stands after the edit (a base
    this lane moves too: its new place); None for an actor that saves no base or relative place."""
    base = p.own(i, 'Base', 0)
    if not (isinstance(base, int) and base > 0 and p.own(i, 'RelativeLocation') is not None):
        return None
    b_loc, b_rot = moved.get(base) or (p.own(base, 'Location', [0.0, 0.0, 0.0]), p.own(base, 'Rotation') or [0, 0, 0])
    return spawns.turn([loc[j] - b_loc[j] for j in range(3)], -b_rot[1])


def _set_like(walker, g, p, index, like, relative):
    """A copy's relative place written on export `index` of `g`, laid out as its template `like` of `p`."""
    import native_lights
    e = p.exports[like - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_lights.set_property(walker, g, data, start, 'RelativeLocation', 'StructProperty', 'Vector',
                                      struct.pack('<3f', *relative))
    g.relocate(index, bytes(data))


def read_value(q, i, key):
    """A spawn value as the written map `q` (package.Package) has it on actor `i`, or None where it saves none."""
    prop = SPAWN_VALUES[key][0]
    value = q.own(i, prop)
    if key == 'difficulty' and value is not None:
        value = str(value)
        return value[len(DIFFICULTY_PREFIX):] if value.startswith(DIFFICULTY_PREFIX) else value
    if SPAWN_VALUES[key][1] == 'BoolProperty' and value is not None:
        return bool(value)
    return value


def verify(q, record, p=None):
    """The lane read back from the written map `q`: a moved point at its pose and still listed, a valued one with each
    value it was given, a deleted one off the level's list, a copy listed at its pose with its pod index and values
    and, given the map before the edit `p`, its template byte for byte as it was. Raises ValueError at the first thing
    that isn't so."""
    import native_copy
    listed = set(native_copy.level_actors(q))
    for r in record:
        i = r['export']
        if r['how'] == 'deleted':
            if i in listed:
                raise ValueError("%s is still on the level's list after its delete" % r['actor'])
            continue
        if i not in listed:
            raise ValueError("%s is off the level's list after the edit" % r['actor'])
        if r['how'] in ('moved', 'copied'):
            loc = [float(v) for v in q.own(i, 'Location', [0.0, 0.0, 0.0])]
            rot = [int(v) for v in q.own(i, 'Rotation', [0, 0, 0])]
            if any(abs(a - b) > 1e-3 for a, b in zip(loc, r['location'])) or rot != list(r['rotation']):
                raise ValueError('%s reads back at %s %s, not %s %s' % (r['actor'], loc, rot, r['location'], r['rotation']))
        if r['how'] in ('valued', 'copied'):
            for key, want in (r.get('values') or {}).items():
                got = read_value(q, i, key)
                if got != want:
                    raise ValueError('%s reads back %s = %r, not %r' % (r['actor'], key, got, want))
        if r['how'] == 'copied' and p is not None:
            t = r['template']
            a, b = p.exports[t - 1], q.exports[t - 1]
            if q.data[b['off']:b['off'] + b['size']] != p.data[a['off']:a['off'] + a['size']]:
                raise ValueError('%s, the template of %s, changed' % (r['source'], r['actor']))


def main(argv=None):
    import package_grow
    from package import Package
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, edit, out = argv
    zones = json.loads(Path(edit).read_text(encoding='utf-8')).get('landingZones')
    p = Package(src)
    g = package_grow.Grower(str(src))
    report, volumes = apply(g, p, zones or {})
    import native_copy
    if volumes:
        native_copy.add_to_level(g, p, volumes)
    g.write(str(out))
    for m in report:
        print('%s (%s) to zone %s: %d actors moved' % (m['landing'], m['group'], m['zone'], len(m['actors'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
