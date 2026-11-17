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
sounds too. A carried effect stays the piece's until the project gives it a record: the compiler leaves those out of
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
"""
import struct

import native_copy

PL = 'TheWorld.PersistentLevel.'
EFFECT_CLASSES = ('Emitter',)
SOUND_CLASSES = ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundMovable')
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
    walker = native_copy.Walker(p)
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


def pose_of(p, i):
    return ([float(v) for v in p.own(i, 'Location', [0.0, 0.0, 0.0])],
            [int(v) for v in p.own(i, 'Rotation', [0, 0, 0])])


def apply(g, p, ops, classes=EFFECT_CLASSES, what='an effect'):
    """A lane of the native edit (the compiler's `effects` or `sounds`: {moves: [{name, location, rotation}],
    deletes: [{name}], copies: [{id, name, source, location, rotation}]}) made in `g`, the grower of package `p`.
    Returns (the clones to add to the level's list, the actors to take out of it, the record: [dict(actor, how:
    moved | deleted | copied, export, cls, location?, rotation?, before?, id?, source?, mapping?)])."""
    if not ops or not any(ops.get(k) for k in ('moves', 'deletes', 'copies')):
        return [], set(), []
    walker = native_copy.Walker(p)
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
        record.append(dict(actor=c['name'], id=c.get('id'), source=c['source'], how='copied', export=made['actor'],
                           cls=p.cls(i), location=loc, rotation=rot, mapping=made['mapping'],
                           **({'donor': c['donor']} if c.get('donor') else {})))
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
    walker = buildings.grown_walker(p, g)
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
            template = buildings.building_template(p, native_copy.Walker(p))
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
