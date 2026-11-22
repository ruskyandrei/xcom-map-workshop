"""A map's background sound: the sound bed its script starts when the level loads (export 39; findings register F-159).

88 of the install's 97 base maps start exactly one sound from a SeqEvent_LevelLoaded, through a SeqAct_PlaySound with
no target, so it plays for the player rather than at a place, and nothing stops it: Bar's wind and traffic, a forest's
birds, a night's crickets. 26 different cues over the install, each in one of the game's sound packages that the maps
hold as forced exports (SoundAmbience-NorthAmerica.ForestAmbienceCue and the like).

background_sound(p): dict(event, op, cue, volume, fadeIn) of the map `p` (the viewer's Package), the first such sound,
or None. `op` is the SeqAct_PlaySound's path, which the Build edits (tools/bake/native_sounds.py background);
`volume` and `fadeIn` its VolumeMultiplier and FadeInTime where it saves them.

catalogue(): the game's sound beds the editor offers, read from background_sounds.json beside this module (each the
cue's path, the base map whose package holds it, and its label), with words(cue) for a cue's label.
"""
import json
import re
from pathlib import Path

from package import FormatError

LEVEL = 'TheWorld.PersistentLevel'
CATALOGUE = Path(__file__).with_name('background_sounds.json')
DEPTH = 6       # how many links from the level-loaded event a background sound may stand (one or two on every map)


def _sequence(p, i):
    c = p.cls(i)
    return c.startswith('Seq') or c in ('Sequence', 'PrefabSequence')


def _in_level(p, i, level):
    o = p.exports[i - 1]['outer']
    while o > 0:
        if o == level:
            return True
        o = p.exports[o - 1]['outer']
    return False


def _links(p, i):
    """The ops export `i`'s output links lead to, with the input each enters."""
    item = p.properties(i)[0].get(('OutputLinks', 0))
    if not item or item['kind'] != 'ArrayProperty':
        return []
    out = []
    for row in p.structs(item['value']):
        for link in p.structs(row.get(('Links', 0), {}).get('value')):
            op = link.get(('LinkedOp', 0), {}).get('value')
            if isinstance(op, int) and op > 0:
                out.append((op, int(link.get(('InputLinkIdx', 0), {}).get('value') or 0)))
    return out


def _targeted(p, i):
    """Whether a SeqAct_PlaySound has a variable linked to it (a target: it plays at that place)."""
    item = p.properties(i)[0].get(('VariableLinks', 0))
    if not item or item['kind'] != 'ArrayProperty':
        return False
    return any(p.refs(row.get(('LinkedVariables', 0), {}).get('value')) for row in p.structs(item['value']))


def background_sound(p):
    level = p.by_name.get(LEVEL)
    if level is None:
        return None
    events = [i for i in range(1, len(p.exports) + 1)
              if p.cls(i) == 'SeqEvent_LevelLoaded' and _in_level(p, i, level)]
    for event in events:
        seen, todo = {event}, [(event, 0)]
        while todo:
            i, depth = todo.pop(0)
            try:
                links = _links(p, i)
            except (FormatError, ValueError):
                continue
            for op, idx in links:
                if op in seen or not _sequence(p, op):
                    continue
                seen.add(op)
                if p.cls(op) == 'SeqAct_PlaySound' and idx == 0 and not _targeted(p, op):
                    props = p.properties(op)[0]
                    cue = props.get(('PlaySound', 0), {}).get('value')
                    if not isinstance(cue, int) or cue == 0:
                        continue
                    found = dict(event=p.name(event), op=p.name(op), cue=p.name(cue))
                    for key, name in (('VolumeMultiplier', 'volume'), ('FadeInTime', 'fadeIn')):
                        item = props.get((key, 0))
                        found[name] = round(float(item['value']), 4) if item else None
                    return found
                if depth + 1 < DEPTH:
                    todo.append((op, depth + 1))
    return None


def catalogue():
    """[dict(cue, map, label, maps)] of background_sounds.json, in its order (the commonest first)."""
    return json.loads(CATALOGUE.read_text(encoding='utf-8'))['sounds']


def words(cue):
    """A cue's label: the catalogue's, else its name without its package and a trailing "Cue"."""
    for row in catalogue():
        if row['cue'] == cue:
            return row['label']
    return re.sub(r'_?Cue$', '', str(cue).rsplit('.', 1)[-1]) or str(cue)
