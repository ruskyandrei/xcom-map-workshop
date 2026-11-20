"""The prefab library on disk (private/plans/done/prefab-library-plan.md, 5.6 and stage P1).

A prefab is one JSON file in the prefabs folder (the `prefabs` setting; by default a `prefabs` folder beside the
projects), named after the prefab and kept as projects are (projects.py): atomic saves, a revision check, the
revision before in `.workshop\\<id>\\prefab.prev.json`. Beside it there the page keeps the prefab's picture
(`picture.png`). A deleted prefab is moved to `.workshop\\deleted\\`, not erased.

The file holds references, places and numbers only, never game data, so it can be passed on. A file from elsewhere
is not trusted: `validate` checks the whole document (schema and version, every key known, counts capped, every name
matched against a pattern, every number finite and in range) before it is stored, and the page shows names as text
only. Every later editor reads schema 1 (plan D11).

    { "schema": "xcom-map-workshop/prefab", "schemaVersion": 1, "id", "name", "revision", "created", "savedAt",
      "floor": { "tiles": [8, 6] },
      "pieces": [ a project's added records in prefab space: { actor, from, components, location, rotation, prefab,
                  partner, tinted?, recipe? } | { actor, template: {kind: "cover", version}, cover, location,
                  rotation } | { actor, template: {kind: "spot" | "point", version}, light, location, rotation }
                  | { actor, kind: "effect" | "sound", from, location, rotation, effect? | sound? } (schema 3: a copy
                  of a map's effect or ambient sound, with the values a project's record has)
                  | { actor, kind: "flare", from, location, rotation } (schema 3 too, since stage FX6b: a copy of a
                  map's lens flare; it has no values) ],
      "groups": [ { id, breakTogether?, members: [ {added} | {group} | {building} ] } ],
      "buildings": [ { id, name, kind, floors: [ { boxes: [[x0, y0, z0, x1, y1, z1]] } ] } ],
      "donors": [ { package, sha256? } ], "mission": null }

Prefab space is the tile grid: the origin is a tile corner at ground level, x and y across, z up, game units.
"""
import math
import os
import re
import threading
import time
import uuid

from projects import ID, SHA256, ProjectError, ProjectStore, file_stem

SCHEMA = 'xcom-map-workshop/prefab'
# 2: a copied piece's flags (`flags`; piece flags plan). 3: effects and sounds (pieces with a `kind`; the effects and
# sounds plan, stage FX6a; a lens flare is one more `kind` since stage FX6b, with no values object: an editor of
# before FX6b says it doesn't know the kind). 1 and 2 are read too
SCHEMA_VERSION = 3
READ_VERSIONS = (1, 2, 3)
EFFECT_KINDS = ('effect', 'sound', 'flare')
EFFECT_VALUE_KEYS = {'effect': ('scale', 'startsOn', 'parameters', 'follow'),
                     'sound': ('radiusMin', 'radiusMax', 'volume', 'pitch', 'startsOn')}
MAX_PARAMETERS = 64
FLAG_ROLES = ('walking', 'cover', 'sight', 'floor', 'mouse')
TOP_KEYS = {'schema', 'schemaVersion', 'id', 'name', 'revision', 'created', 'savedAt', 'floor', 'pieces', 'groups',
            'buildings', 'donors', 'mission'}
MAX_PIECES, MAX_GROUPS, MAX_BUILDINGS, MAX_DONORS, MAX_COMPONENTS, MAX_BOXES, MAX_FLOORS = 5000, 2000, 200, 200, 64, 64, 10
# A field this editor doesn't know (a newer editor's) is kept when its value is small: a number, true or false, null,
# a string of up to UNKNOWN_TEXT characters, or a list of up to UNKNOWN_LIST such values; at most UNKNOWN_FIELDS of
# them in one record. Anything larger or nested is refused: the file is not trusted.
UNKNOWN_TEXT, UNKNOWN_LIST, UNKNOWN_FIELDS = 200, 16, 8
MAX_TILES = 512
MAX_PICTURE = 1 << 20
# What library.piece asks of a map's and an actor's name, and what the exporter gives components and link tags.
PACKAGE = re.compile(r'[A-Za-z_][A-Za-z0-9_-]{0,79}')
ACTOR = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,119}(\.[A-Za-z_][A-Za-z0-9_]{0,119}){0,3}')
COMPONENT = re.compile(r'[A-Za-z_][A-Za-z0-9_.]{0,199}')
TAG = re.compile(r'[A-Za-z0-9_.:|-]{1,200}')
KEY = re.compile(r'[A-Za-z0-9_-]{1,64}')
WORD = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}')
PNG = b'\x89PNG\r\n\x1a\n'
LIGHT_KEYS = ('color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled')
LIGHT_KINDS = ('spot', 'point')
BUILDING_KINDS = ('building', 'ufo')


def bad(message):
    return ProjectError(422, 'This prefab file can\'t be used: ' + message)


def number(value, limit, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
        raise bad(f'{what} is not a number in range.')
    return value


def whole(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise bad(f'{what} is not a whole number from {low} to {high}.')
    return value


def triple(value, limit, what):
    if not isinstance(value, list) or len(value) != 3: raise bad(f'{what} is not three numbers.')
    for v in value: number(v, limit, what)


def named(value, pattern, what):
    if not isinstance(value, str) or not pattern.fullmatch(value): raise bad(f'{what} is not a name this editor takes.')
    return value


def small(value, inner=False):
    """Whether an unknown field's value may be carried (UNKNOWN_TEXT, UNKNOWN_LIST)."""
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, str):
        return len(value) <= UNKNOWN_TEXT
    return not inner and isinstance(value, list) and len(value) <= UNKNOWN_LIST and all(small(v, True) for v in value)


_SEEN = threading.local()      # validate(): the unknown fields met on the way, by name


def carried(value, known, what):
    """The fields of record `value` this editor doesn't know: noted when they are small enough to carry, refused
    otherwise."""
    unknown = sorted(str(k) for k in set(value) - set(known))
    large = [k for k in unknown if not isinstance(k, str) or not WORD.fullmatch(k) or not small(value[k])]
    if large or len(unknown) > UNKNOWN_FIELDS:
        raise bad(f'{what} has {", ".join(map(repr, (large or unknown)[:4]))}, which this editor doesn\'t know and '
                  'can\'t carry (a newer editor\'s field is kept only when its value is small).')
    if unknown and getattr(_SEEN, 'fields', None) is not None:
        _SEEN.fields.update(unknown)


def record(value, required, optional, what, strict=False):
    """`strict`: a record whose fields the compiler takes exactly (a template, a light's or a cover's values, a
    source, a recipe): an unknown field there is refused, small or not."""
    if not isinstance(value, dict): raise bad(f'{what} is not a record.')
    missing = [k for k in required if k not in value]
    if missing: raise bad(f'{what} lacks {", ".join(missing)}.')
    unknown = sorted(map(str, set(value) - set(required) - set(optional)))
    if strict and unknown: raise bad(f'{what} has {", ".join(map(repr, unknown[:4]))}, which this editor doesn\'t know.')
    carried(value, (*required, *optional), what)
    return value


def listed(value, most, what, least=0):
    if not isinstance(value, list) or not least <= len(value) <= most:
        raise bad(f'{what} is not a list of {least} to {most}.')
    return value


def check_schema(document, writing=False):
    """A prefab of a schema this editor reads; `writing` (a save): of the schema it writes (projects.check_schema)."""
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise ProjectError(422, 'This is not an XCOM Map Workshop prefab.')
    version = document.get('schemaVersion')
    if writing and version in READ_VERSIONS and version != SCHEMA_VERSION:
        raise ProjectError(409, f'This page is older than the editor\'s server: it saves prefab schema {version}, the '
                                f'server writes schema {SCHEMA_VERSION}. Reload the page and save again.',
                           schemaVersion=version, stale=True)
    if version not in READ_VERSIONS:
        raise ProjectError(409, f'This prefab was saved with prefab schema {version!r}; this editor reads schema '
                                f'{", ".join(map(str, READ_VERSIONS))}. A newer editor is needed to open it.',
                           schemaVersion=version)


def check_values(values, kind, what):
    """An effect's or a sound's values, as a project's record carries them (compiler.effect_values judges them
    against the effect they are set on; here only their shape)."""
    record(values, (), EFFECT_VALUE_KEYS[kind], what, True)
    if not isinstance(values.get('startsOn', True), bool): raise bad(f'{what}: startsOn is not true or false.')
    if values.get('follow', 'auto') not in ('none', 'auto'): raise bad(f'{what}: follow is not none or auto.')
    if 'scale' in values and number(values['scale'], 1e4, f'{what}\'s size') <= 0: raise bad(f'{what}\'s size is not over 0.')
    for key in ('radiusMin', 'radiusMax'):
        if key in values and number(values[key], 1e7, f'{what}\'s {key}') < 0: raise bad(f'{what}\'s {key} is negative.')
    for key in ('volume', 'pitch'):
        if key not in values: continue
        if not isinstance(values[key], list) or len(values[key]) != 2: raise bad(f'{what}\'s {key} is not two numbers.')
        for v in values[key]: number(v, 1e4, f'{what}\'s {key}')
    for k, p in enumerate(listed(values.get('parameters', []), MAX_PARAMETERS, f'{what}\'s parameters')):
        p = record(p, ('name', 'value'), ('type',), f'{what}\'s parameter {k + 1}', True)
        named(p['name'], COMPONENT, f'{what}\'s parameter name')
        if 'type' in p: named(p['type'], WORD, f'{what}\'s parameter type')
        value = p['value']
        if isinstance(value, list):
            if len(value) not in (3, 4): raise bad(f'{what}\'s parameter {p["name"]} is not a number, three or four.')
            for v in value: number(v, 1e9, f'{what}\'s parameter {p["name"]}')
        else:
            number(value, 1e9, f'{what}\'s parameter {p["name"]}')


def check_piece(piece, what):
    if not isinstance(piece, dict): raise bad(f'{what} is not a record.')
    if 'kind' in piece and 'template' not in piece:
        # an effect, an ambient sound or a lens flare: a copy of a map's own, with its values at most (a flare has none)
        kind = piece['kind']
        if kind not in EFFECT_KINDS:
            raise bad(f'{what} is of a kind this editor doesn\'t know ({str(kind)[:40]}).')
        record(piece, ('actor', 'kind', 'from', 'location', 'rotation'), (kind,) if kind in EFFECT_VALUE_KEYS else (), what, True)
        source = record(piece['from'], ('package', 'level', 'actor'), (), f'{what}\'s source', True)
        named(source['package'], PACKAGE, f'{what}\'s map')
        if source['level'] != 'base': raise bad(f'{what} is not of a map\'s own level.')
        named(source['actor'], ACTOR, f'{what}\'s source actor')
        if kind in piece: check_values(piece[kind], kind, f'{what}\'s values')
    elif 'template' in piece:
        template = record(piece['template'], ('kind', 'version'), (), f'{what}\'s template', True)
        kind = named(template['kind'], WORD, f'{what}\'s template kind')
        whole(template['version'], 1, 1000, f'{what}\'s template version')
        if kind == 'cover':
            record(piece, ('actor', 'template', 'cover', 'location', 'rotation'), (), what)
            # whole tiles (older), or units as the handles size it (compiler.cover_shape: a floor has no heights)
            if isinstance(piece['cover'], dict) and 'size' in piece['cover']:
                cover = record(piece['cover'], ('type', 'size'), ('heights',), f'{what}\'s cover', True)
                for key in ('size', 'heights'):
                    if key not in cover: continue
                    if not isinstance(cover[key], list) or len(cover[key]) != 2: raise bad(f'{what}\'s cover {key} is not two numbers.')
                    for v in cover[key]: number(v, 1e5, f'{what}\'s cover {key}')
            else:
                cover = record(piece['cover'], ('width', 'length', 'type', 'height'), (), f'{what}\'s cover', True)
                for key in ('width', 'length', 'height'): whole(cover[key], 1, 64, f'{what}\'s {key}')
            named(cover['type'], WORD, f'{what}\'s cover type')
        elif kind in LIGHT_KINDS:
            record(piece, ('actor', 'template', 'light', 'location', 'rotation'), (), what)
            # (a point light has no cones)
            keys = LIGHT_KEYS if kind == 'spot' else tuple(k for k in LIGHT_KEYS if not k.endswith('ConeAngle'))
            light = record(piece['light'], keys, (), f'{what}\'s light', True)
            colour = light['color']
            if not isinstance(colour, list) or len(colour) != 3: raise bad(f'{what}\'s colour is not three numbers.')
            for c in colour: whole(c, 0, 255, f'{what}\'s colour')
            for key in keys[1:-1]:
                if number(light[key], 1e6, f'{what}\'s {key}') < 0: raise bad(f'{what}\'s {key} is negative.')
            if not isinstance(light['enabled'], bool): raise bad(f'{what}\'s enabled is not true or false.')
        else:
            raise bad(f'{what} is made from a recipe this editor doesn\'t know ({kind}).')
    else:
        record(piece, ('actor', 'from', 'components', 'location', 'rotation'), ('prefab', 'partner', 'tinted', 'recipe', 'flags'), what)
        source = record(piece['from'], ('package', 'level', 'actor'), (), f'{what}\'s source', True)
        named(source['package'], PACKAGE, f'{what}\'s map')
        if source['level'] != 'base': raise bad(f'{what} is not a piece of a map\'s own level.')
        named(source['actor'], ACTOR, f'{what}\'s source actor')
        components = listed(piece['components'], MAX_COMPONENTS, f'{what}\'s components', 1)
        for c in components: named(c, COMPONENT, f'{what}\'s component')
        if len(set(components)) != len(components): raise bad(f'{what} names a component twice.')
        if piece.get('prefab') is not None: named(piece['prefab'], TAG, f'{what}\'s link')
        if piece.get('partner') is not None: named(piece['partner'], ACTOR, f'{what}\'s partner')
        if not isinstance(piece.get('tinted', False), bool): raise bad(f'{what}\'s tinted is not true or false.')
        if 'flags' in piece:
            # its flags (piece flags plan): known roles, each strictly true or false, never empty
            flags = piece['flags']
            if not isinstance(flags, dict) or not flags or any(k not in FLAG_ROLES for k in flags) \
                    or any(not isinstance(v, bool) for v in flags.values()):
                raise bad(f'{what}\'s flags are not walking, cover, sight, floor and mouse, each true or false.')
        if 'recipe' in piece:
            recipe = record(piece['recipe'], ('key', 'name'), ('member',), f'{what}\'s recipe', True)
            named(recipe['key'], KEY, f'{what}\'s recipe key')
            if 'member' in recipe: named(recipe['member'], KEY, f'{what}\'s member recipe key')
            if not isinstance(recipe['name'], str) or len(recipe['name']) > 200: raise bad(f'{what}\'s recipe name is too long.')
    named(piece['actor'], ACTOR, f'{what}\'s name')
    triple(piece['location'], 1e6, f'{what}\'s location')
    triple(piece['rotation'], 2 ** 31, f'{what}\'s rotation')


def recover_sources(document, index, read):
    """Propose exact recipe replacements while preserving the prefab's actor identities and edits."""
    # (an effect or a sound has no recipe to match by: it stays as saved)
    pieces = [p for p in document['pieces'] if p.get('from') and 'kind' not in p]
    donors = {d['package'].casefold(): d for d in document.get('donors', [])}
    entries = {e['key']: e for e in (index or {}).get('entries', []) if e['placeable']}
    records, healthy, changes, reasons = {}, set(), {}, {}

    def actor_path(name):
        return name if '.' in name else 'TheWorld.PersistentLevel.' + name

    def source_record(source):
        key = source['package'].casefold(), actor_path(source['actor'])
        if key not in records:
            try:
                records[key] = read(dict(source, actor=key[1].rsplit('.', 1)[-1]))
            except (ProjectError, OSError, ValueError, KeyError):
                records[key] = None
        return records[key]

    def components(record, actor):
        return sorted(o['component'] for o in record['objects'] if o['actor'] == actor)

    def shape(actor, parts):
        family = lambda path: re.sub(r'_\d+$', '', path.rsplit('.', 1)[-1])
        return family(actor), sorted(map(family, parts))

    groups = {}
    for p in pieces:
        source, name = p['from'], p['actor']
        package = source['package'].casefold()
        record = source_record(source)
        recipe = p.get('recipe')
        expected = donors.get(package, {}).get('sha256')
        current = (record.get('recipes') or {}).get(actor_path(source['actor']), {}) if record else {}
        if (record and (expected is None or expected == record['source']['sha256']) and
                (not recipe or record.get('key') == recipe['key']) and
                (not recipe or not recipe.get('member') or current.get('member') == recipe['member']) and
                components(record, actor_path(source['actor'])) == sorted(p['components'])):
            healthy.add(name)
        if not recipe:
            if name not in healthy:
                reasons[name] = 'No recipe was saved for this piece.'
            continue
        link = p.get('prefab') or min(name, p.get('partner') or name)
        groups.setdefault((package, recipe['key'], link), []).append(p)

    proposals = []
    for (package, key, _), group in groups.items():
        if all(p['actor'] in healthy for p in group):
            continue
        sources = [p['from'] for p in group]
        entry = entries.get(key)
        if entry:
            sources.append(entry['source'])
        for source in sources:
            record = source_record(source)
            if not record or record.get('key') != key:
                continue
            recipes = record.get('recipes') or {}
            if len(recipes) != len(group):
                continue  # recover a complete assembly together
            plan = {}
            for p in group:
                same_package = record['source']['package'].casefold() == package
                original = actor_path(p['from']['actor'])
                matches = [a for a, recipe in recipes.items()
                           if (not p['recipe'].get('member') or recipe.get('member') == p['recipe']['member'])
                           and shape(original, p['components']) == shape(a, components(record, a))]
                if same_package and original in matches:
                    matches = [original]
                if len(matches) != 1:
                    break
                actor = matches[0]
                plan[p['actor']] = (dict(p, **{'from': dict(package=record['source']['package'], level='base', actor=actor)},
                                          components=components(record, actor), recipe=recipes[actor]), record['source']['sha256'])
            if len(plan) == len(group) and len({p['from']['actor'] for p, _ in plan.values()}) == len(group):
                proposals.append(plan)
                break
        else:
            for p in group:
                if p['actor'] not in healthy:
                    reasons[p['actor']] = ('No unambiguous recipe match in the catalogue.' if index else
                                           'Scan the All maps catalogue to look for this recipe.')

    # A saved donor hash covers every reference to that package. Refresh it only if none of its old references remain.
    while proposals:
        proposed = {name: update for plan in proposals for name, update in plan.items()}
        kept = {p['from']['package'].casefold() for p in document['pieces'] if p.get('from') and p['actor'] not in proposed}
        blocked = {key for p, digest in proposed.values() if (key := p['from']['package'].casefold()) in kept
                   and donors.get(key, {}).get('sha256') not in (None, digest)}
        if not blocked:
            changes = proposed
            break
        for plan in proposals[:]:
            if any(p['from']['package'].casefold() in blocked for p, _ in plan.values()):
                for name in plan:
                    if name not in healthy:
                        reasons[name] = 'Other pieces still refer to an older version of this donor.'
                proposals.remove(plan)

    recovered = []
    for p in document['pieces']:
        if p['actor'] in changes:
            p, digest = changes[p['actor']]
            package = p['from']['package']
            donors[package.casefold()] = dict(package=package, sha256=digest)
        recovered.append(p)
    used = {p['from']['package'].casefold() for p in recovered if p.get('from')}
    return dict(document=dict(document, pieces=recovered, donors=[donors[k] for k in sorted(used & donors.keys())]),
                repaired=sorted(changes), unresolved=[dict(actor=a, reason=reasons[a]) for a in sorted(reasons)])


def validate(document, prefab_id):
    """Everything the server can check of a prefab without the game's maps: the whole document. Gives the names of
    the fields it carries without knowing them (a newer editor's; `carried`), sorted."""
    _SEEN.fields = set()
    try:
        _validate(document, prefab_id)
        return sorted(_SEEN.fields)
    finally:
        _SEEN.fields = None


def _validate(document, prefab_id):
    check_schema(document)
    carried(document, TOP_KEYS, 'it')
    if document.get('id') != prefab_id: raise ProjectError(422, 'The document belongs to another prefab.')
    name = document.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ProjectError(422, 'A prefab needs a name of 1 to 120 characters.')
    if any(ord(c) < 32 for c in name): raise bad('its name has control characters.')
    for key in ('created', 'savedAt'):
        if document.get(key) is not None and (not isinstance(document[key], str) or len(document[key]) > 40):
            raise bad(f'its {key} is not a time.')
    if document.get('revision') is not None: whole(document['revision'], 0, 10 ** 9, 'its revision')
    floor = record(document.get('floor'), ('tiles',), (), 'its floor')
    tiles = listed(floor['tiles'], 2, 'its floor\'s tiles', 2)
    for v in tiles: whole(v, 1, MAX_TILES, 'its floor\'s size')
    if document.get('mission') is not None: raise bad('it carries a mission, which this editor doesn\'t read yet.')

    actors = set()
    for k, piece in enumerate(listed(document.get('pieces'), MAX_PIECES, 'its pieces')):
        check_piece(piece, f'piece {k + 1}')
        if piece['actor'] in actors: raise bad(f'two pieces are called {piece["actor"]}.')
        actors.add(piece['actor'])
    for piece in document['pieces']:
        if 'kind' not in piece and piece.get('partner') is not None and piece['partner'] not in actors:
            raise bad(f'{piece["actor"]} names a partner that is not in the prefab.')

    buildings = set()
    for k, building in enumerate(listed(document.get('buildings', []), MAX_BUILDINGS, 'its buildings')):
        what = f'building {k + 1}'
        record(building, ('id', 'floors'), ('name', 'kind'), what)
        named(building['id'], KEY, f'{what}\'s id')
        if building['id'] in buildings: raise bad('two buildings have one id.')
        buildings.add(building['id'])
        label = building.get('name', '')
        if not isinstance(label, str) or len(label) > 120 or any(ord(c) < 32 for c in label): raise bad(f'{what}\'s name is not a name.')
        if building.get('kind', 'building') not in BUILDING_KINDS: raise bad(f'{what} is of a kind this editor doesn\'t know.')
        for floor in listed(building['floors'], MAX_FLOORS, f'{what}\'s floors', 1):
            record(floor, ('boxes',), (), f'{what}\'s floor')
            for box in listed(floor['boxes'], MAX_BOXES, f'{what}\'s boxes', 1):
                if not isinstance(box, list) or len(box) != 6: raise bad(f'{what} has a box that is not six numbers.')
                for v in box: number(v, 1e6, f'{what}\'s box')
                if any(box[i + 3] - box[i] < 1 for i in range(3)): raise bad(f'{what} has a box with no size.')

    ids = set()
    groups = listed(document.get('groups', []), MAX_GROUPS, 'its groups')
    for k, group in enumerate(groups):
        record(group, ('id', 'members'), ('breakTogether', 'locked'), f'group {k + 1}')
        named(group['id'], KEY, f'group {k + 1}\'s id')
        if group['id'] in ids: raise bad('two groups have one id.')
        ids.add(group['id'])
        for flag in ('breakTogether', 'locked'):
            if not isinstance(group.get(flag, False), bool): raise bad(f'group {k + 1}\'s {flag} is not true or false.')
    held = set()
    for k, group in enumerate(groups):
        what = f'group {k + 1}'
        for member in listed(group['members'], MAX_PIECES, f'{what}\'s members', 2):
            if not isinstance(member, dict) or len(member) != 1 or next(iter(member)) not in ('added', 'group', 'building'):
                raise bad(f'{what} has a member that is not a piece, a group or a building of the prefab.')
            kind, value = next(iter(member.items()))
            known = dict(added=actors, group=ids, building=buildings)[kind]
            if not isinstance(value, str) or value not in known or (kind == 'group' and value == group['id']):
                raise bad(f'{what} names a member the prefab doesn\'t have.')
            if (kind, value) in held: raise bad(f'{what} holds a member another group holds.')
            held.add((kind, value))
    # no group inside itself, however far down
    parent = {m['group']: g['id'] for g in groups for m in g['members'] if 'group' in m}
    for start in parent:
        seen, at = set(), start
        while at in parent:
            if at in seen: raise bad('its groups hold each other in a loop.')
            seen.add(at); at = parent[at]

    packages = set()
    for k, donor in enumerate(listed(document.get('donors', []), MAX_DONORS, 'its maps')):
        record(donor, ('package',), ('sha256',), f'map {k + 1}')
        named(donor['package'], PACKAGE, f'map {k + 1}\'s name')
        if 'sha256' in donor and not (isinstance(donor['sha256'], str) and SHA256.fullmatch(donor['sha256'])):
            raise bad(f'map {k + 1}\'s hash is not a SHA-256.')
        if donor['package'].lower() in packages: raise bad('a map is listed twice.')
        packages.add(donor['package'].lower())


class PrefabStore(ProjectStore):
    schema, noun, prev = SCHEMA, 'prefab', 'prefab.prev.json'

    def save_recovery(self, prefab_id, state):
        """Working coordinates, not a normalized library save; larger work can be recovered for repair. A page
        session's own draft (`owner`), kept as projects keep theirs (ProjectStore.save_recovery): one based on an older
        revision than the saved one is kept too, and answered as stale."""
        record(state, ('baseRevision', 'document', 'envelope', 'nextSerial'), ('owner',), 'recovery', True)
        whole(state['baseRevision'], 0, 10 ** 9, 'recovery revision')
        whole(state['nextSerial'], 0, 10 ** 9, 'recovery serial')
        document = state['document']
        if not isinstance(document, dict): raise bad('recovery has no document.')
        validate(dict(document, floor=dict(tiles=[1, 1])), prefab_id)
        envelope = state['envelope']
        if envelope is not None:
            listed(envelope, 6, 'recovery envelope', 6)
            for value in envelope: number(value, 1e6, 'recovery envelope')
            if any(envelope[k] > envelope[k + 3] for k in range(3)): raise bad('recovery envelope is reversed.')
        return super().save_recovery(prefab_id, state)

    def check(self, document):
        check_schema(document)

    def readable(self, document):
        return True

    def validate(self, document, prefab_id):
        """A save's check: the whole document, of the schema this editor writes."""
        check_schema(document, writing=True)
        validate(document, prefab_id)

    def load(self, prefab_id):
        """The prefab, checked whole: a file put in the folder by hand is trusted no more than an imported one."""
        document = super().load(prefab_id)
        validate(document, prefab_id)
        return document

    def summary(self, path, document):
        pieces = [p for p in document.get('pieces') if isinstance(p, dict)] if isinstance(document.get('pieces'), list) else []
        lights = sum(1 for p in pieces if isinstance(p.get('template'), dict) and p['template'].get('kind') in LIGHT_KINDS)
        floor = document.get('floor') if isinstance(document.get('floor'), dict) else {}
        effects, sounds, flares = (sum(1 for p in pieces if 'template' not in p and p.get('kind') == kind)
                                   for kind in EFFECT_KINDS)
        summary = dict(id=document['id'], name=document.get('name'), file=path.name, revision=document.get('revision'),
                    savedAt=document.get('savedAt'), pieces=len(pieces) - lights - effects - sounds - flares, lights=lights,
                    effects=effects, sounds=sounds, flares=flares,
                    buildings=len(document['buildings']) if isinstance(document.get('buildings'), list) else 0,
                    tiles=floor.get('tiles'),
                    maps=sorted({str(d.get('package')) for d in (document.get('donors') if isinstance(document.get('donors'), list) else [])
                                 if isinstance(d, dict)}),
                    picture=self.picture_path(document['id']).is_file())
        try:
            unknown = validate(document, document['id'])
            if unknown: summary['unknownFields'] = unknown
            from prefab_bounds import measure
            size = measure(document)
            if size['warnings']: summary['largeSize'] = size['warnings']
            if size['tall']: summary['tall'] = True
        except ProjectError:
            pass  # Loading reports malformed manually dropped files in full.
        return summary

    # ------------------------------------------------------------------ the picture the page draws of a prefab
    def picture_path(self, prefab_id):
        return self.state(prefab_id) / 'picture.png'

    def save_picture(self, prefab_id, data):
        if not data.startswith(PNG) or len(data) > MAX_PICTURE: raise ProjectError(422, 'A prefab\'s picture is a PNG of up to 1 MB.')
        with self.lock:
            if self._find(prefab_id) is None: raise ProjectError(404, 'No such prefab.')
            path = self._state_folder(prefab_id) / 'picture.png'
            temp = path.with_name(path.name + '.tmp')
            temp.write_bytes(data)
            os.replace(temp, path)
        return dict(ok=True)

    # ------------------------------------------------------------------ deleting, and files from elsewhere
    def delete(self, prefab_id):
        """The prefab's file moved to .workshop\\deleted\\ (kept, not erased); its picture and previous revision go."""
        with self.lock:
            path = self._find(prefab_id)
            if path is None: raise ProjectError(404, 'No such prefab.')
            kept = self.root / '.workshop' / 'deleted'
            self._state_folder(prefab_id)       # makes .workshop, hidden
            kept.mkdir(parents=True, exist_ok=True)
            target = kept / f'{path.stem} {time.strftime("%Y-%m-%d %H%M%S")}{path.suffix}'
            for n in range(2, 100):
                if not target.exists(): break
                target = kept / f'{path.stem} {time.strftime("%Y-%m-%d %H%M%S")} ({n}){path.suffix}'
            os.replace(path, target)
            state = self.state(prefab_id)
            for draft, _ in self._drafts(prefab_id): draft.unlink(missing_ok=True)
            for name in ('picture.png', self.prev): (state / name).unlink(missing_ok=True)
            try: state.rmdir()
            except OSError: pass
            self.paths.pop(prefab_id, None)
            return dict(ok=True, kept=str(target))

    def import_file(self, document, clash=None, expected=None):
        """A prefab file from elsewhere, checked whole and stored. One whose id the library has already is refused
        (409, with `clash`: the one here) unless `clash` says what to do: 'replace' saves it over that one as its
        next revision, 'copy' stores it as a new prefab with an id of its own. A replace names the revision it
        replaces (`expected`, the one the user was shown: review finding 4); one saved since is refused as a clash
        again, with its revision now."""
        if clash == 'replace' and (not isinstance(expected, int) or isinstance(expected, bool) or expected < 0):
            raise ProjectError(400, 'Say which revision of the prefab the file replaces (expectedRevision).')
        if not isinstance(document, dict): raise ProjectError(422, 'This is not an XCOM Map Workshop prefab.')
        check_schema(document)
        prefab_id = document.get('id')
        if not isinstance(prefab_id, str) or not ID.fullmatch(prefab_id): raise bad('it has no valid id.')
        validate(document, prefab_id)
        # (an older schema's file is a newer one's too: stored as the schema this editor writes)
        document = {k: v for k, v in document.items() if k not in ('revision', 'savedAt')}
        document['schemaVersion'] = SCHEMA_VERSION
        with self.lock:
            path = self._find(prefab_id)
            here = self._read(path) if path else None
            here_clash = dict(id=prefab_id, name=here.get('name'), revision=here.get('revision'), savedAt=here.get('savedAt')) \
                if isinstance(here, dict) else None
            if here is None:
                return dict(self.save(prefab_id, document, 0), id=prefab_id, name=document['name'])
            if clash == 'replace':
                if here.get('revision', 0) != expected:
                    raise ProjectError(409, f'The library\'s “{here.get("name")}” was saved again since (revision '
                                            f'{here.get("revision")}).', clash=here_clash, changed=True)
                document['created'] = here.get('created') or document.get('created')
                return dict(self.save(prefab_id, document, expected), id=prefab_id, name=document['name'], replaced=True)
            if clash == 'copy':
                new_id = str(uuid.uuid4())
                names = {str(p.get('name')).lower() for p in self.list()}
                name = base = (document['name'][:110] + ' (imported)')
                for n in range(2, 1000):
                    if name.lower() not in names: break
                    name = f'{base} {n}'
                document = dict(document, id=new_id, name=name)
                document.pop('created', None)
                return dict(self.save(new_id, document, 0), id=new_id, name=name, copied=True)
            raise ProjectError(409, f'The library already has this prefab, as “{here.get("name")}” (revision {here.get("revision")}).',
                               clash=here_clash)


__all__ = ['SCHEMA', 'SCHEMA_VERSION', 'PrefabStore', 'validate', 'file_stem']
