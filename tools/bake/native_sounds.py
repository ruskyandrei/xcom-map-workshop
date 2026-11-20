"""Ambient sounds moved, turned, copied and deleted in the same map (the effects and sounds plan, Part D, stage FX3):
the native edit's `sounds` lane, made as native_effects.apply makes the effects' (a move in place, a delete off the
level's list, a copy cloned with what the actor owns). A simple sound (AmbientSoundSimple, its toggleable kind) owns
its AudioComponent, its SoundCue and its one SoundNodeAmbient, so its copy has a cue and a node of its own that point
at each other and at the wave, which stays shared; an AmbientSound plays a cue of the game's, shared by its copies.
A sound is in no floor's list (plan 2.4). A clear takes the map's own ambient sounds out (native_copy.CLEAR_OUT, since
18 November 2026), but those the project moves or copies itself and, in a clear that keeps the scenery outside the
play area, those standing outside it (KEEP_OUTSIDE)."""
import native_effects

CLASSES = native_effects.SOUND_CLASSES


def apply(g, p, ops):
    """native_effects.apply for the `sounds` lane: (clones, gone, record)."""
    return native_effects.apply(g, p, ops, CLASSES, 'an ambient sound')


def verify(q, record):
    """The lane read back (native_effects.verify)."""
    native_effects.verify(q, record)
