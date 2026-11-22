"""A map's background sound: the sound bed its script starts when the level loads (export 39; findings register F-159).

88 of the install's 97 base maps start exactly one sound from a SeqEvent_LevelLoaded, through a SeqAct_PlaySound with
no target, so it plays for the player rather than at a place, and nothing stops it: Bar's wind and traffic, a forest's
birds, a night's crickets. 26 different cues over the install, each in one of the game's sound packages that the maps
hold as forced exports (SoundAmbience-NorthAmerica.ForestAmbienceCue and the like).

background_sound(p): dict(event, op, cue, volume, fadeIn) of the map `p` (the viewer's Package), the first such sound,
or None. `op` is the SeqAct_PlaySound's path, which the Build edits (tools/bake/native_sounds.py background);
`volume` and `fadeIn` its VolumeMultiplier and FadeInTime where it saves them.

catalogue(): the game's sound beds the editor offers, read from background_sounds.json beside this module (each the
cue's path, the base map whose package holds it, its label, how many base maps play it, and the waves it plays), with
words(cue) for a cue's label and waves(p, cue) for the waves a cue plays in a package.

wave_source(cue, index): what the server's /background-sound.ogg reads a bed's wave by (the Map settings window's play
button): the map that plays it in the game install, an export-like record of the one wave for audio.WaveCache, and
the wave's id.
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


def waves(p, cue):
    """The paths of the SoundNodeWaves the cue `cue` (an export index of `p`) plays: from its FirstNode through each
    node's ChildNodes (a looping node, a mixer), in the order met, each once."""
    out, seen = [], set()
    todo = [p.properties(cue)[0].get(('FirstNode', 0), {}).get('value')]
    while todo:
        i = todo.pop(0)
        if not isinstance(i, int) or i <= 0 or i in seen:
            continue
        seen.add(i)
        if p.cls(i) == 'SoundNodeWave':
            out.append(p.name(i))
            continue
        item = p.properties(i)[0].get(('ChildNodes', 0))
        if item and item['kind'] == 'ArrayProperty':
            todo += list(p.refs(item['value']))
    return out


def wave_source(cue, index):
    """(the install's file of the map that plays the bed `cue`, a record of its `index`-th wave as an export's
    soundWaves give one (what audio.WaveCache.get reads), the wave's id '<map>|<wave path>'). KeyError for a cue the
    catalogue doesn't list or a wave it doesn't have; projects.ProjectError 409 with no game install, 404 when the
    install lacks the map."""
    from projects import ProjectError
    from settings import game_cooked, load_settings, resolve_game
    row = next((r for r in catalogue() if r['cue'] == cue), None)
    if row is None or not 0 <= index < len(row['waves']):
        raise KeyError(cue)
    settings = load_settings()
    game = resolve_game(settings['game'])[0] if settings.get('game') else None
    if game is None:
        raise ProjectError(409, 'The game install is not set or not found: choose it in the editor.')
    wanted = row['map'].lower() + '.upk'
    cooked = Path(game_cooked(game))
    path = next((f for f in cooked.iterdir() if f.name.lower() == wanted), None) if cooked.is_dir() else None
    if path is None:
        raise ProjectError(404, 'The map %s, which plays the sound %s, is not in the game install.' % (row['map'], row['label']))
    wave_id = '%s|%s' % (row['map'], row['waves'][index])
    scene = dict(name=row['map'], source=dict(file=str(path), sha256=None), streams=[],
                 soundWaves={wave_id: dict(playable=True)})
    return path, scene, wave_id


def words(cue):
    """A cue's label: the catalogue's, else its name without its package and a trailing "Cue"."""
    for row in catalogue():
        if row['cue'] == cue:
            return row['label']
    return re.sub(r'_?Cue$', '', str(cue).rsplit('.', 1)[-1]) or str(cue)
