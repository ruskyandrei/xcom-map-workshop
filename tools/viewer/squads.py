"""The test squad: the one squad every Play in game lands with, its file, and the page's routes
(private/plans/todo/test-squad-plan.md, sections 4 and 5.1).

The squad is kept in test-squad.json beside the editor's settings (settings.settings_path(): normally
Documents\\XCOM Map Workshop), so a redirected Documents folder or the settings override (tests) moves it too. Its
document:

    {"schema": "xcom-map-workshop/test-squad", "version": 1, "name": "Test squad",
     "source": {"family": "lwr", "fingerprint": "..."},           the install it was last saved against
     "units": [{"id": "unit-1", "kind": "soldier" | "mec" | "shiv", "first": ..., "last": ..., "class": "eSC_Assault",
                "rank": 1, "look": "man-a", "country": "eCountry_Canada", "armour": "eItem_ArmorKevlar",
                "sidearm": "eItem_Pistol", "weapons": [...], "items": [...], "perks": [...], "stats": {"hp": 8}}, ...]}

Items, classes, perks and countries are the game's enum names (a slot of its tables: gamedata.py); looks are the keys
of squadrecords.LOOKS. `stats` holds only the base stats set by hand (hp, aim, defence, mobility, will, sight); one
not there is the install's base. A selection the install the squad plays in doesn't have stays in the file, shown as
unresolved, and comes back when the squad is played on an install that has it.

The file is saved whole: a temporary file, then a replace, the file before it kept as test-squad.prev.json. Each
read gives the file's revision (a hash of its bytes; 'none' when there is no file, which means the default squad),
and a save names the revision it was based on: another is refused (409), so a save from another tab or an edit of
the file meanwhile is never overwritten unseen. A file that can't be read is reported, never replaced by the default
behind the user's back; a save over it keeps its bytes aside first (test-squad.bad-<time>.json).

A shared squad is the same document without `source`, as <name>.xcomsquad.json (`export_document`); `import_document`
checks one (its schema, version, size and fields) and gives the draft to look at and save. A newer version is refused.

  GET /squad.json      the saved squad (or the default), its revision, the install it plays in, the choices that
                       install offers, and the warnings and errors of the squad there (squadrecords.resolve)
  PUT /squad.json      {"expectedRevision", "document"}: save it
  POST /squad/check    {"document"}: the same answer for a draft, nothing saved
  POST /squad/import   {"text"}: a shared squad's text checked and given back as a draft
  POST /squad/export   {"document"}: the shared file's name and text
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading

import version
from projects import ProjectError

SCHEMA = 'xcom-map-workshop/test-squad'
SCHEMA_VERSION = 1
FILE, PREVIOUS = 'test-squad.json', 'test-squad.prev.json'
SHARED_SUFFIX = '.xcomsquad.json'
MAX_BYTES = 256 << 10
MAX_UNITS = 8           # the most the panel keeps; the install's own limit is squadrecords' (Adapter.max_units)
KINDS = ('soldier', 'mec', 'shiv')
STATS = ('hp', 'aim', 'defence', 'mobility', 'will', 'sight')
STAT_RANGE = (0, 999)
NAME_MAX = 24           # a unit's first or last name, or a SHIV's name
SQUAD_NAME_MAX = 40
LIST_MAX = dict(weapons=16, items=16, perks=64)
SYMBOL = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,80}')
UNIT_ID = re.compile(r'[A-Za-z0-9_-]{1,40}')
LOOK = re.compile(r'[a-z0-9-]{1,24}')
CONTROL = re.compile(r'[\x00-\x1f\x7f-\x9f]')
UNIT_KEYS = ('id', 'kind', 'first', 'last', 'class', 'rank', 'look', 'country', 'armour', 'sidearm', 'weapons', 'items',
             'perks', 'stats')


class SquadError(ProjectError):
    pass


def store_path(settings_file=None):
    """test-squad.json beside the settings file (settings.settings_path() when not given)."""
    if settings_file is None:
        from settings import settings_path
        settings_file = settings_path()
    return Path(settings_file).parent / FILE


def _text(value, field, limit, empty=True):
    if not isinstance(value, str): raise SquadError(422, f'{field} is not text.')
    if CONTROL.search(value): raise SquadError(422, f'{field} holds a control character.')
    if len(value) > limit: raise SquadError(422, f'{field} is longer than {limit} characters.')
    if not empty and not value.strip(): raise SquadError(422, f'{field} is empty.')
    return value


def _symbol(value, field, optional=True):
    if value is None and optional: return None
    if not isinstance(value, str) or not SYMBOL.fullmatch(value): raise SquadError(422, f'{field} is not a game name.')
    return value


def check_unit(unit, where):
    if not isinstance(unit, dict): raise SquadError(422, f'{where} is not a unit.')
    extra = sorted(set(unit) - set(UNIT_KEYS))
    if extra: raise SquadError(422, f'{where} has fields this editor does not know: {", ".join(extra)}.')
    out = {}
    if not isinstance(unit.get('id'), str) or not UNIT_ID.fullmatch(unit['id']): raise SquadError(422, f'{where} has no id.')
    out['id'] = unit['id']
    if unit.get('kind') not in KINDS: raise SquadError(422, f'{where}: kind is soldier, mec or shiv.')
    out['kind'] = unit['kind']
    out['first'] = _text(unit.get('first', ''), f'{where} first name', NAME_MAX)
    out['last'] = _text(unit.get('last', ''), f'{where} last name', NAME_MAX)
    for key in ('class', 'country', 'armour', 'sidearm'): out[key] = _symbol(unit.get(key), f'{where} {key}')
    look = unit.get('look')
    if look is not None and not (isinstance(look, str) and LOOK.fullmatch(look)): raise SquadError(422, f'{where}: look is not one of the looks.')
    out['look'] = look
    rank = unit.get('rank', 0)
    if not isinstance(rank, int) or isinstance(rank, bool) or not 0 <= rank <= 31: raise SquadError(422, f'{where}: rank is a whole number from 0 to 31.')
    out['rank'] = rank
    for key, limit in LIST_MAX.items():
        values = unit.get(key, [])
        if not isinstance(values, list) or len(values) > limit: raise SquadError(422, f'{where}: {key} is a list of at most {limit}.')
        out[key] = [_symbol(v, f'{where} {key}', optional=False) for v in values]
    stats = unit.get('stats', {})
    if not isinstance(stats, dict): raise SquadError(422, f'{where}: stats is an object.')
    out['stats'] = {}
    for key, value in stats.items():
        if key not in STATS: raise SquadError(422, f'{where}: {key} is not a base stat ({", ".join(STATS)}).')
        if not isinstance(value, int) or isinstance(value, bool) or not STAT_RANGE[0] <= value <= STAT_RANGE[1]:
            raise SquadError(422, f'{where}: {key} is a whole number from {STAT_RANGE[0]} to {STAT_RANGE[1]}.')
        out['stats'][key] = value
    return {key: out[key] for key in UNIT_KEYS}


def check_document(document, shared=False):
    """The document with its fields checked and in their order (a SquadError, 422, says what is wrong). shared: a
    file to import, whose `source` is dropped."""
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise SquadError(422, 'This is not an XCOM Map Workshop test squad.')
    v = document.get('version')
    if not isinstance(v, int) or isinstance(v, bool) or v < 1: raise SquadError(422, 'The squad has no version.')
    if v > SCHEMA_VERSION:
        raise SquadError(422, f'This squad was made by a newer XCOM Map Workshop (squad version {v}; this one reads '
                              f'{SCHEMA_VERSION}). Update the editor to use it.', newer=True)
    name = _text(document.get('name', ''), 'The squad\'s name', SQUAD_NAME_MAX, empty=False).strip()
    units = document.get('units')
    if not isinstance(units, list) or not 1 <= len(units) <= MAX_UNITS:
        raise SquadError(422, f'A squad has 1 to {MAX_UNITS} units.')
    checked = [check_unit(unit, f'Unit {i + 1}') for i, unit in enumerate(units)]
    ids = [u['id'] for u in checked]
    if len(set(ids)) != len(ids): raise SquadError(422, 'Two units have the same id.')
    out = dict(schema=SCHEMA, version=SCHEMA_VERSION, name=name)
    source = document.get('source')
    if not shared and isinstance(source, dict):
        out['source'] = {k: source[k] for k in ('family', 'fingerprint') if isinstance(source.get(k), str) and len(source[k]) <= 80}
    out['units'] = checked
    return out


def revision_of(data):
    return 'none' if data is None else hashlib.sha256(data).hexdigest()[:16]


class SquadStore:
    """test-squad.json at `path`: read() gives (document or None, revision, error or None); save() writes."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _bytes(self):
        try: return self.path.read_bytes()
        except FileNotFoundError: return None

    def read(self):
        """(the checked document or None when there is no file, the revision, why the file can't be used or None)."""
        with self.lock:
            return self._read()

    def _read(self):
        try: data = self._bytes()
        except OSError as error: return None, 'unreadable', f'{self.path} could not be read ({error.strerror or error})'
        if data is None: return None, 'none', None
        revision = revision_of(data)
        if len(data) > MAX_BYTES: return None, revision, f'{self.path} is larger than a squad can be'
        try: document = check_document(json.loads(data.decode('utf-8')))
        except (UnicodeDecodeError, ValueError) as error: return None, revision, f'{self.path} is not a squad file ({error})'
        except SquadError as error: return None, revision, f'{self.path}: {error.message}'
        return document, revision, None

    def save(self, document, expected):
        """Write the (checked) document if the file is still at revision `expected`; the new revision."""
        document = check_document(document)
        with self.lock:
            _, current, problem = self._read()
            if expected != current:
                raise SquadError(409, 'The squad was saved elsewhere meanwhile (another tab, or its file was changed). '
                                      'Your changes are still here: reopen the panel to see the saved squad.',
                                 code='squad-changed', revision=current)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            old = self._bytes()
            if old is not None:
                # a file that could not be read keeps its bytes under a name of its own; a good one becomes the backup
                aside = (self.path.with_name(f'test-squad.bad-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json')
                         if problem else self.path.with_name(PREVIOUS))
                temp = aside.with_name(aside.name + '.tmp')
                temp.write_bytes(old)
                os.replace(temp, aside)
            data = (json.dumps(document, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
            temp = self.path.with_name(self.path.name + f'.{os.getpid()}.tmp')
            temp.write_bytes(data)
            os.replace(temp, self.path)
            return revision_of(data)


SHARED_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def export_document(document):
    """(file name, text) of a squad to share: the document without its install's details."""
    document = check_document(document, shared=True)
    shared = dict(document, editor=version.VERSION)
    name = SHARED_NAME.sub('_', document['name']).strip(' .') or 'Test squad'
    return name + SHARED_SUFFIX, json.dumps(shared, indent=2, ensure_ascii=False) + '\n'


def import_document(text):
    """A shared squad's text checked: the document, without `source` (it is the install of whoever shared it)."""
    if not isinstance(text, str): raise SquadError(400, 'Send the file\'s text.')
    if len(text.encode('utf-8')) > MAX_BYTES: raise SquadError(413, 'The file is larger than a squad can be.')
    try: document = json.loads(text)
    except ValueError as error: raise SquadError(422, f'The file is not a squad (not JSON: {error}).')
    if isinstance(document, dict): document = {k: v for k, v in document.items() if k != 'editor'}
    return check_document(document, shared=True)


# ---- the service the page's routes use ----

class SquadService:
    """The saved squad against the install Play in game uses. target(): (game folder or None, what was found, where
    the choice came from), the player's; cache: a folder for the install's enums (gamedata.load)."""

    def __init__(self, store, target, cache=None):
        self.store, self.target, self.cache = store, target, cache
        self._memo = {}
        self._memo_lock = threading.Lock()

    def catalogue(self, game):
        """(the install's catalogue, None) or (None, why it can't be read), kept while its files are unchanged."""
        import gamedata
        key = str(game)
        signature = gamedata.signature(game)
        with self._memo_lock:
            held = self._memo.get(key)
            if held and held[0] == signature: return held[1], held[2]
        try: result = gamedata.load(game, self.cache), None
        except (OSError, gamedata.GameDataError) as error: result = None, str(error)
        with self._memo_lock: self._memo[key] = (signature, *result)
        return result

    def _install(self):
        game, note, source = self.target()
        if game is None: return None, None, dict(folder=None, note=note, source=source)
        catalogue, why = self.catalogue(game)
        info = dict(folder=str(game), note=note, source=source, error=why)
        if catalogue is not None:
            info.update(family=catalogue.family, fingerprint=catalogue.fingerprint, language=catalogue.language)
        return game, catalogue, info

    def status(self, draft=None, choices=True):
        """The squad (the draft, else the saved one, else the default), its revision and file problem, the install,
        what it offers (choices) and the squad checked against it."""
        import squadrecords
        saved, revision, problem = self.store.read()
        _, catalogue, install = self._install()
        default = squadrecords.default_document(catalogue)
        document = draft if draft is not None else saved if saved is not None else (None if problem else default)
        out = dict(revision=revision, problem=problem, saved=saved is not None, install=install, default=default,
                   document=document, limits=dict(units=MAX_UNITS, name=NAME_MAX, squadName=SQUAD_NAME_MAX,
                                                  stats=list(STAT_RANGE)))
        if catalogue is not None and choices: out['choices'] = squadrecords.choices(catalogue)
        out['check'] = squadrecords.resolve(document, catalogue).public() if document is not None else None
        return out

    def get(self): return self.status()

    def save(self, request):
        if not isinstance(request, dict) or 'document' not in request: raise SquadError(400, 'Send {expectedRevision, document}.')
        document = check_document(request['document'])
        _, catalogue, _ = self._install()
        if catalogue is not None:
            document['source'] = dict(family=catalogue.family, fingerprint=catalogue.fingerprint)
            document = {k: document[k] for k in ('schema', 'version', 'name', 'source', 'units')}
        self.store.save(document, request.get('expectedRevision'))
        return self.status(choices=False)

    def check(self, request):
        if not isinstance(request, dict) or 'document' not in request: raise SquadError(400, 'Send {document}.')
        document = check_document(request['document'])
        _, catalogue, install = self._install()
        import squadrecords
        return dict(install=install, check=squadrecords.resolve(document, catalogue).public())

    def import_text(self, request):
        if not isinstance(request, dict): raise SquadError(400, 'Send {text}.')
        document = import_document(request.get('text'))
        return dict(self.check(dict(document=document)), document=document)

    def export(self, request):
        if not isinstance(request, dict) or 'document' not in request: raise SquadError(400, 'Send {document}.')
        name, text = export_document(request['document'])
        return dict(name=name, text=text)

    def summary(self):
        """The squad in a few words for the play dialog: {name, units, playable, errors, warnings} or {problem}."""
        import squadrecords
        saved, _, problem = self.store.read()
        _, catalogue, _ = self._install()
        if problem: return dict(problem=problem, playable=False)
        document = saved or squadrecords.default_document(catalogue)
        if document is None: return None
        check = squadrecords.resolve(document, catalogue)
        return dict(name=document['name'], units=len(document['units']), saved=saved is not None,
                    playable=check.playable, errors=check.all_errors()[:3],
                    warnings=len(check.warnings) + sum(len(u.warnings) for u in check.units))

    def snapshot(self, game):
        """The squad a play lands with, resolved once against the install it plays in: (document, Resolved). A
        SquadError says why there is none to play (the file can't be read, or the squad has errors there)."""
        import squadrecords
        saved, _, problem = self.store.read()
        if problem:
            raise SquadError(409, f'The test squad\'s file can\'t be used ({problem}). Open Settings, Test squad setup, '
                                  'to see it, and save a squad there.')
        catalogue, why = self.catalogue(game)
        if catalogue is None: raise SquadError(409, f'The install\'s soldier data could not be read: {why}.')
        document = saved or squadrecords.default_document(catalogue)
        resolved = squadrecords.resolve(document, catalogue)
        if not resolved.playable:
            errors = resolved.all_errors()
            raise SquadError(409, 'The test squad can\'t be played on this install: ' + '; '.join(errors[:4])
                             + ('' if len(errors) <= 4 else f' (and {len(errors) - 4} more)')
                             + '. Settings, Test squad setup, shows it.')
        return document, resolved
