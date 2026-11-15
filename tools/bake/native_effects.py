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

Later the editor shows and edits effects as records of their own (moved, placed, deleted in the view). A carried
effect stays the piece's until the project gives it a record: the compiler leaves those out of `carriedEffects`.
"""
import struct

import native_copy

PL = 'TheWorld.PersistentLevel.'


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
