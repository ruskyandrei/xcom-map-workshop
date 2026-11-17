"""Lens flares moved, turned, copied and deleted in the same map (the effects and sounds plan, Part D, stage FX6b):
the native edit's `flares` lane, made as native_effects.apply makes the effects' (a move in place, a delete off the
level's list, a copy cloned with what the actor owns). A LensFlareSource owns one thing, its LensFlareComponent (the
actor's LensFlareComp), which names the flare's template (a LensFlare asset: on the component itself, or on the
archetype the actor was made from) and saves its colour; nothing else of the map names either. So a copy is the actor
and a component of its own, and the template, the archetype and the materials stay shared. A flare has no values the
editor sets (its template and colour stay as the map has them), is in no floor's list, and goes when a map is cleared
unless the project moves it itself (native_copy.CLEAR_OUT, as an effect)."""
import native_effects

CLASSES = native_effects.FLARE_CLASSES


def apply(g, p, ops):
    """native_effects.apply for the `flares` lane: (clones, gone, record)."""
    for c in (ops or {}).get('copies') or []:
        if c.get('values'):
            raise ValueError('%s: a lens flare has no values to set' % c.get('name'))
    if (ops or {}).get('values'):
        raise ValueError('a lens flare has no values to set')
    return native_effects.apply(g, p, ops, CLASSES, 'a lens flare')


def verify(q, record):
    """The lane read back (native_effects.verify), and each copy's component its own with a template to show."""
    native_effects.verify(q, record)
    for r in record:
        if r['how'] != 'copied':
            continue
        component = q.effective(r['export'], 'LensFlareComp', 0) or 0
        if component <= 0 or q.exports[component - 1]['outer'] != r['export']:
            raise ValueError('copy %s has no lens flare component of its own' % r['actor'])
        if not q.effective(component, 'Template', 0):
            raise ValueError('copy %s names no flare template' % r['actor'])
