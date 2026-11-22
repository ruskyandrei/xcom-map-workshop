"""Ambient sounds moved, turned, copied and deleted in the same map (the effects and sounds plan, Part D, stage FX3):
the native edit's `sounds` lane, made as native_effects.apply makes the effects' (a move in place, a delete off the
level's list, a copy cloned with what the actor owns). A simple sound (AmbientSoundSimple, its toggleable kind) owns
its AudioComponent, its SoundCue and its one SoundNodeAmbient, so its copy has a cue and a node of its own that point
at each other and at the wave, which stays shared; an AmbientSound plays a cue of the game's, shared by its copies.
A sound is in no floor's list (plan 2.4). A clear takes the map's own ambient sounds out (native_copy.CLEAR_OUT, since
18 November 2026), but those the project moves or copies itself and, in a clear that keeps the scenery outside the
play area, those standing outside it (KEEP_OUTSIDE).

The map's background sound (the native edit's `backgroundSound`: the sound the map's script starts when the level
loads, for the player; tools/viewer/background_sound.py) is written here too: its SeqAct_PlaySound given another cue (one
the map holds, or one tools/bake/transplant.py has brought from another map), no cue (it then plays nothing), or
another volume (background)."""
import struct

import native_effects

CLASSES = native_effects.SOUND_CLASSES


def apply(g, p, ops):
    """native_effects.apply for the `sounds` lane: (clones, gone, record)."""
    return native_effects.apply(g, p, ops, CLASSES, 'an ambient sound')


def verify(q, record):
    """The lane read back (native_effects.verify)."""
    native_effects.verify(q, record)


def background(g, p, lane):
    """The native edit's `backgroundSound` ({op, cue (a cue's path in the map, or None for no sound), volume?}) made in
    `g`, the grower of the map `p` (the staged map, when the cue was brought from another one): the SeqAct_PlaySound
    `op` given the cue (its PlaySound) and the volume (its VolumeMultiplier). Returns the record: dict(op, cue,
    export (the cue's, or 0), volume?)."""
    if not lane:
        return None
    import native_copy
    import native_lights
    import props as legacy_props
    op = p.by_name.get(lane['op'])
    if op is None or p.cls(op) != 'SeqAct_PlaySound':
        raise ValueError('the map has no sound action %s (its background sound)' % lane['op'])
    cue = 0
    if lane.get('cue') is not None:
        cue = p.by_name.get(lane['cue'])
        if cue is None or p.cls(cue) != 'SoundCue':
            raise ValueError('the map holds no sound cue %s (its background sound): bring it from its map first' % lane['cue'])
    walker = native_copy.Walker(p, g)
    e = p.exports[op - 1]
    data = bytearray(g.export_data(op))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_lights.set_property(walker, g, data, start, 'PlaySound', 'ObjectProperty', None, struct.pack('<i', cue))
    if lane.get('volume') is not None:
        data = native_lights.set_property(walker, g, data, start, 'VolumeMultiplier', 'FloatProperty', None,
                                          struct.pack('<f', float(lane['volume'])))
    g.relocate(op, bytes(data))
    return dict(op=lane['op'], cue=lane.get('cue'), export=cue, **({'volume': lane['volume']} if lane.get('volume') is not None else {}))


def verify_background(q, record):
    """The background sound read back from the written map `q` (package.Package): its action's cue and volume as the
    record says. Raises ValueError where it isn't so."""
    if not record:
        return
    op = q.by_name[record['op']]
    cue = q.own(op, 'PlaySound', 0) or 0
    if (q.name(cue) if cue else None) != record['cue']:
        raise ValueError('the background sound reads back %s, not %s' % (q.name(cue) if cue else None, record['cue']))
    if 'volume' in record and abs(float(q.own(op, 'VolumeMultiplier', 1.0)) - float(record['volume'])) > 1e-4:
        raise ValueError('the background sound\'s volume reads back %s, not %s' % (q.own(op, 'VolumeMultiplier'), record['volume']))
