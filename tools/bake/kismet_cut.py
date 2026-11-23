"""The map's Kismet let go of the pieces an edit deletes (the user, 23 November 2026, of a cleared map's warnings: "I
don't care about these scripts doing anything, why can't we just delete them too?").

A deleted piece is taken out of the level's actor list (native_copy.hide_pieces), but the map's Kismet still holds it:
a variable's object, an event's Originator, an object list. Its script then acts on a piece that is no longer in the
map (F-63). Here every reference of the persistent level's sequence objects to such a piece is emptied:

- an object property holding it (SeqVar_Object's ObjValue, an event's Originator, an op's own reference) is set to
  None: the actions that read the variable act on nothing;
- a plain reference array listing it (SeqVar_ObjectList's ObjList) loses the entry;
- an event whose Originator was emptied is switched off (bEnabled false), as native_copy.switch_off_events does for a
  trigger the clear takes out: with no originator it can no longer fire by any road.

A reference in a static array's other slots (`Key[1]` and on) is left, and said (kept). What reads the references is
scene_metadata.kismet_walk, the export's reader of the same references (referencedBy).

  cut(g, p, gone)      the map `p` (grown as `g`): its Kismet's references to `gone` (export indices) emptied; the record
  verify(q, record)    the written map `q` read back: no listed reference left, each event listed switched off"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE.parent / 'upk'))
import props as legacy_props  # noqa: E402

LEVEL = 'TheWorld.PersistentLevel.'


def cut(g, p, gone):
    """The map's Kismet's references to `gone` (export indices of placed actors the edit takes out) emptied in `g`.
    Returns dict(cut: [dict(object (its path under the level), property, actor)], off: [the events switched off],
    kept: [dict(object, property, actor)] (a static array's other slots)), each sorted, or None when the Kismet names
    none of them."""
    import native_copy
    import native_lights
    import scene_metadata
    gone = set(gone)
    if not gone:
        return None
    named, _, _, _ = scene_metadata.kismet_walk(p)
    hits = {i: [(a, prop) for a, prop in refs if a in gone] for i, refs in named.items()}
    hits = {i: refs for i, refs in hits.items() if refs}
    if not hits:
        return None
    walker = native_copy.Walker(p, g)
    short = lambda i: p.name(i).rsplit('.', 1)[-1]  # noqa: E731
    path = lambda i: p.name(i).replace(LEVEL, '', 1)  # noqa: E731  (a sequence object's path under the level)
    out = dict(cut=[], off=[], kept=[])
    for i, refs in sorted(hits.items()):
        e = p.exports[i - 1]
        data = bytearray(g.export_data(i))
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        props = p.properties(i)[0]
        emptied_originator = False
        for prop in sorted({prop for _, prop in refs}):
            actors = sorted(short(a) for a, pr in refs if pr == prop)
            if '[' in prop:
                out['kept'] += [dict(object=path(i), property=prop, actor=a) for a in actors]
                continue
            item = props.get((prop, 0))
            if item['kind'] == 'ObjectProperty':
                data = native_lights.set_property(walker, g, data, start, prop, 'ObjectProperty', None, struct.pack('<i', 0))
                emptied_originator = emptied_originator or prop == 'Originator'
            else:
                values = list(struct.unpack_from('<%di' % struct.unpack_from('<i', item['value'])[0], item['value'], 4))
                data = native_copy.set_object_array(walker, g, data, start, prop, [v for v in values if v not in gone])
            out['cut'] += [dict(object=path(i), property=prop, actor=a) for a in actors]
        if emptied_originator and p.cls(i).startswith(('SeqEvent', 'XComSeqEvent')):
            data = native_lights.set_property(walker, g, data, start, 'bEnabled', 'BoolProperty', None, b'\x00')
            out['off'].append(path(i))
        g.relocate(i, bytes(data))
    for k in ('cut', 'kept'):
        out[k].sort(key=lambda r: (r['object'], r['property'], r['actor']))
    out['off'].sort()
    return out


def verify(q, record):
    """The written map `q` read back: none of the record's cut references left, each event it switched off saved off.
    Raises ValueError on a difference."""
    import scene_metadata
    named, _, _, _ = scene_metadata.kismet_walk(q)
    held = {(q.name(i).replace(LEVEL, '', 1), prop, q.name(a).rsplit('.', 1)[-1]) for i, refs in named.items() for a, prop in refs}
    for r in record.get('cut') or []:
        if (r['object'], r['property'], r['actor']) in held:
            raise ValueError("the map's Kismet still holds %s in %s %s" % (r['actor'], r['object'], r['property']))
    by_name = {q.name(i).replace(LEVEL, '', 1): i for i in range(1, len(q.exports) + 1)
               if q.name(i).startswith(LEVEL) and 'Seq' in q.cls(i)}
    for name in record.get('off') or []:
        i = by_name.get(name)
        if i is None or q.effective(i, 'bEnabled', True):
            raise ValueError('the event %s is not switched off' % name)
