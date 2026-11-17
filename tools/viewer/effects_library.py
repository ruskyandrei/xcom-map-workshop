"""Effects and sounds in the library (private/plans/todo/effects-and-sounds-plan.md, Part E, stage FX4): each donor
map's effects (Emitter actors) and ambient sounds as recipes the Add panel can place in another map, the kinds the
panel sorts them into, and what keeps one from being placed.

A **recipe** is what makes two placed actors the same thing to place: an effect's class, particle system, saved
instance parameters, scale, component offset and starting state; a sound's class, cue (its path when the cue is an
asset others play; its node classes and waves when it is the sound's own), node values and starting state. `key` is
its hash, so an effect placed the same way in two maps is one entry. Two recipes of one system are two entries (a
steam turned up is not the steam as it is), and two cues that reach one wave are two sounds.

What is not offered, and why (an entry's `reason`): an actor its level doesn't list, one that rides on another (it
moves with that actor), an effect that plays no particle system, and the landing's actors (Long War's landing
mutator takes out every actor made like the landing's when a battle loads: F-120). The streams' effects are a
mission's own and are not scanned: the donors are the base maps.

Kinds come from the system's or the wave's name (KINDS): for the panel's filter only, never to hide an entry (an
effect matching no rule is Other).
"""
import hashlib
import json
import re

RECIPE_VERSION = 1
# an effect's kind, from its system's package and name: the first rule that matches wins
EFFECT_KINDS = (
    ('Nature', r'firefl|moth|(?<![a-z])rats?(?![a-z])|bird|pigeon|crow|sparrow|seagull|owl(?![a-z])|squirrel|'
               r'(?<![a-z])fl(y|ies)(?![a-z])|leaf|leaves|petal|flower|snow|cloud|(?<![a-z])fish'),
    ('Fire', r'fire|flame|ember|burn|spark|torch|candle|plasma'),
    ('Light beams and glows', r'light|beam|glow|blink|lamp|cone|flash|searchlight|projector|police|traffic|alarm'),
    ('Smoke and steam', r'smoke|steam|vapou?r|fog|mist|incense|exhaust|dust'),
    ('Water', r'water|drip|rain|splash|foam|puddle|fountain|stream|fluid|goop|(?<![a-z])dam(?![a-z])|spray|spout'),
    ('Alien', r'alien|holo|nanobot|psi|stasis|power_core|chryssalid|battleship|ufo|ethereal|globe'),
    ('Wreckage and trash', r'trash|paper|debris|destruct|wreck|rope|cloth|tarp|rock'),
)
# a sound's kind, from its wave's package and name
SOUND_KINDS = (
    ('Music and voices', r'muzak|music|radio|store|shop|pizza|fastfood|coffee|bank|liquor|voice|crowd'),
    ('Engines', r'engine|idle|chopper|carsteam|flyby'),
    ('Alien', r'alien|ufo|stasis|psi|plasma|gollop|hyperwave|exalt|powersource|navmodule|examtable|cover'),
    ('Nature and weather', r'stream|fountain|hydrant|geyser|wind|tarp|rain|water|bird|cricket|forest|cemetery'),
    ('Machines', r'hum|machine|air|condition|fluorescent|dryer|wash|freezer|lab|generator|tv|static|tone|spark|'
                 r'laundromat|fog'),
)
OTHER = 'Other'


def kind_of(kind, path):
    """The panel's kind of an effect (its system's path) or a sound (its first wave's path, or its cue's)."""
    text = (path or '').casefold().replace('.', '_')
    for label, pattern in EFFECT_KINDS if kind == 'effect' else SOUND_KINDS:
        if re.search(pattern, text):
            return label
    return OTHER


def short(path):
    return str(path or '').rsplit('.', 1)[-1]


def recipe(record):
    """The recipe of one export 28 record (effects_metadata.describe's): the fields that make two placed actors the
    same thing to place, as a dict that sorts and hashes the same every time."""
    if record['kind'] == 'effect':
        return dict(v=RECIPE_VERSION, kind='effect', actorClass=record['actorClass'], system=record.get('template'),
                    parameters=record.get('parameters') or [], scale=[round(float(v), 4) for v in record['scale']],
                    componentPose=record.get('componentPose'), startsOn=record.get('startsOn'))
    cue = record.get('cue') or {}
    return dict(v=RECIPE_VERSION, kind='sound', actorClass=record['actorClass'],
                cue=None if cue.get('private') else cue.get('path'), nodes=record.get('nodes'),
                waves=[w.split('|', 1)[1] for w in record.get('waves') or []],
                values={k: (round(v, 4) if isinstance(v, float) else v) for k, v in (record.get('values') or {}).items()},
                startsOn=record.get('startsOn'))


def recipe_key(record):
    """The recipe's hash: 16 hex digits, as the library's mesh recipes."""
    return hashlib.sha256(json.dumps(recipe(record), sort_keys=True, default=str).encode()).hexdigest()[:16]


def blocked(record):
    """Why a record can't be placed in another map, or None (the module notes)."""
    if record.get('stream'):
        return 'it is a mission stream\'s own'
    if record.get('landingActor') or record.get('landingRole'):
        return ('it is one of the landing\'s actors, which Long War\'s landing mutator takes out when a battle loads, '
                'copies and all')
    if not record.get('can', {}).get('copy'):
        return (record.get('why') or {}).get('copy') or 'the map\'s data says it can\'t be copied'
    return None


def name_of(record, systems=None):
    """What the panel calls it: the system's short name (Steam_Small), the first wave's (CarPickupIdle), else the
    cue's or the actor's."""
    if record['kind'] == 'effect':
        return short(record.get('template')) or short(record['actor'])
    waves = record.get('waves') or []
    if waves:
        return short(waves[0].split('|', 1)[1])
    return short((record.get('cue') or {}).get('path')) or short(record['actor'])


def kind_path(record):
    """The path a record's kind is read from."""
    if record['kind'] == 'effect':
        return record.get('template')
    waves = record.get('waves') or []
    return waves[0].split('|', 1)[1] if waves else (record.get('cue') or {}).get('path')
