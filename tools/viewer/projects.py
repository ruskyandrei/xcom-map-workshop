"""Editor projects on disk (first-editor plan, section 3; contracts in research/editor-contracts.md).

One file per project in the projects folder, named after the project, so a project is shared by sending that file:

    Bar remix.json                       the saved document (any name ending .json is read; the id inside is what counts)
    .workshop\\<id>\\project.prev.json     the revision before it, kept by every save
    .workshop\\<id>\\recovery-<owner>.json unsaved state a page autosaves, one file per page session (`owner`, the id
                                         the page made when it loaded); removed when that session saves or discards,
                                         or when the user restores or discards it from another page
    .workshop\\<id>\\recovery.json         the same, kept before drafts had owners (an older editor's)

`.workshop` (hidden on Windows) keeps what stays on this computer, by project id, so renaming or moving a project's file
keeps its backup and recovery. A save writes the file the project's name gives (`<name>.json`, characters Windows
forbids replaced by `_`, ` (2)` added when another project has that name), and renames the file when the name changes.

Saves are atomic (a temporary file, then a replace) and carry the revision they were based on: a save based on an
older revision is refused as a conflict instead of overwriting work saved from another tab. A document with another
schema version is refused with a clear message; there is no migration before the tool is public.

Projects saved before 8 November 2026 had a folder each, named by id (`<id>\\project.json`, `project.prev.json`,
`recovery.json`). The store moves such folders to the layout above the first time it reads the projects folder.
"""
from datetime import datetime, timezone
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import threading
import uuid

SCHEMA = 'xcom-map-workshop/project'
# 2: pieces' flags (overrides[].flags, added[].flags; piece flags plan); 3: effects and sounds (records of their own:
# the effects and sounds plan, Part C); 4: the spawns plan's records (`spawnRules`, SP8; the base map's spawn points'
# overrides and added records, SP6 and SP7). 1 to 3 are read too, and saved as 4.
SCHEMA_VERSION = 4
READ_VERSIONS = (1, 2, 3, 4)
MAX_BYTES = 32 << 20
ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
SHA256 = re.compile(r'[0-9a-f]{64}')
STATE = '.workshop'
SUFFIX = '.json'
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


class ProjectError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def draft_query(query):
    """A DELETE of a draft's address query (parse_qs with blank values kept): (owner, savedAt). `owner` must be said
    (blank: the draft kept before drafts had owners), so no page deletes drafts it can't name."""
    if 'owner' not in query: raise ProjectError(400, 'Say whose kept changes to discard (?owner=).')
    owner = query['owner'][0] or None
    return owner, (query.get('savedAt') or [None])[0]


def check_schema(document, writing=False):
    """A project of a schema this editor reads (READ_VERSIONS); `writing` (a save): of the schema it writes, so a page
    older than the server (it would drop the newer fields it doesn't know) can't save over a newer document."""
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise ProjectError(422, 'This is not an XCOM Map Workshop project.')
    version = document.get('schemaVersion')
    if writing and version in READ_VERSIONS and version != SCHEMA_VERSION:
        raise ProjectError(409, f'This page is older than the editor\'s server: it saves project schema {version}, the '
                                f'server writes schema {SCHEMA_VERSION}. Reload the page and save again (the unsaved '
                                f'changes are offered back when the project opens).', schemaVersion=version, stale=True)
    if version not in READ_VERSIONS:
        raise ProjectError(409, f'This project was saved with project schema {version}; this editor reads schema '
                                f'{", ".join(map(str, READ_VERSIONS))}. Open it with the editor version that saved it.',
                           schemaVersion=version)


def shape_problem(document):
    """What keeps a project of a schema this editor reads from being listed, opened or built (review finding 9), in
    words, or None: the least the listing, the page and the Build read, the same for schema 1 to 4. Its name is text;
    it names its base map and that map's SHA-256; its edits, when it has them, are lists of records; its revision is a
    whole number. Edits that name pieces a map lacks are the page's to judge, and carried."""
    if not isinstance(document.get('name', ''), str): return 'its name is not text'
    source = document.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('map'), str) or not isinstance(source.get('sha256'), str):
        return 'it does not name its base map and that map\'s SHA-256 (source.map and source.sha256)'
    for key in ('overrides', 'added', 'groups', 'areaLightBindings', 'buildings'):
        if key in document and not (isinstance(document[key], list) and all(isinstance(r, dict) for r in document[key])):
            return f'its "{key}" is not a list of records'
    revision = document.get('revision', 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0: return 'its revision is not a whole number'
    return None


def validate(document, project_id):
    """The checks the server can make without the map: shape, identity and binding. The browser checks the edits
    against the map when it opens them."""
    check_schema(document, writing=True)
    if document.get('id') != project_id: raise ProjectError(422, 'The document belongs to another project.')
    name = document.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 120: raise ProjectError(422, 'A project needs a name of 1 to 120 characters.')
    if document.get('mode') != 'edit': raise ProjectError(422, 'Only "edit" projects are supported.')
    source = document.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('map'), str) or not SHA256.fullmatch(str(source.get('sha256'))):
        raise ProjectError(422, 'The project must name its base map and that map\'s SHA-256.')
    for key in ('overrides', 'added'):
        if not isinstance(document.get(key), list) or not all(isinstance(item, dict) for item in document[key]):
            raise ProjectError(422, f'"{key}" must be a list of records.')
    # The user's groups are optional (projects saved before them have none).
    groups = document.get('groups', [])
    if not isinstance(groups, list) or not all(isinstance(item, dict) for item in groups):
        raise ProjectError(422, '"groups" must be a list of records.')
    # Area lights bound to their glowing pieces are optional too (editor lights plan 3.5): the frame and type only; the
    # compiler checks them against the map.
    bindings = document.get('areaLightBindings', [])
    if not isinstance(bindings, list) or not all(isinstance(item, dict) for item in bindings):
        raise ProjectError(422, '"areaLightBindings" must be a list of records.')
    # A cleared map and its landing zones (Clear map plan, section 6): optional; the compiler checks the zones.
    if document.get('cleared', False) not in (True, False):
        raise ProjectError(422, '"cleared" must be true or false.')
    if not isinstance(document.get('clearKeepsOutside', False), bool):
        raise ProjectError(422, '"clearKeepsOutside" must be true or false.')
    zones = document.get('landingZones', [])
    if not isinstance(zones, list) or not all(isinstance(item, dict) for item in zones):
        raise ProjectError(422, '"landingZones" must be a list of records.')
    # The missions the variant serves (mission types plan, D1): optional; the compiler checks the entries.
    listed = document.get('missions', [])
    if not isinstance(listed, list) or not all(isinstance(item, dict) for item in listed):
        raise ProjectError(422, '"missions" must be a list of records.')
    # Its map picture (LWR map packs plan, 4.3; pictures.py keeps the file): optional, named by the file's SHA-256.
    picture = document.get('picture')
    if picture is not None and not (isinstance(picture, dict) and set(picture) == {'sha256'}
                                    and SHA256.fullmatch(str(picture['sha256']))):
        raise ProjectError(422, '"picture" must be {sha256}: the SHA-256 of its map picture.')
    # Its output names (output names plan): package names, when it has them; who holds them is checked as it saves
    # (ProjectStore.check_output)
    if 'output' in document and not valid_output(document['output']):
        raise ProjectError(422, '"output" must be the map\'s and its patch\'s package names (letters, digits and _, '
                                'starting with a letter).')


# (a name UDK can't save, over 30 characters, still saves: an old project keeps its names, and the compiler says to
# use Save as before it builds)
OUTPUT_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,62}')


def valid_output(output):
    """Output names as a project saves them: {shipAs, patch}, package names (outputnames.py says which are free and
    gives a new project's, at most 24 characters)."""
    return (isinstance(output, dict) and set(output) == {'shipAs', 'patch'}
            and all(isinstance(output[k], str) and OUTPUT_NAME.fullmatch(output[k]) for k in output))


def file_stem(name):
    """The file name a project's name gives, without the suffix: what Windows forbids replaced by `_`, no leading or
    trailing dots or spaces, and never a device name (CON, NUL, COM1...)."""
    stem = FORBIDDEN.sub('_', str(name)).strip(' .')
    if not stem: stem = 'project'
    if stem.split('.')[0].strip().upper() in RESERVED: stem = '_' + stem
    return stem


def same_path(a, b):
    """The same path, as the file system compares them (regardless of case on Windows)."""
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def hide(path):
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)  # FILE_ATTRIBUTE_HIDDEN
        except (AttributeError, OSError):
            pass


class ProjectStore:
    # What a store of another kind of document changes (prefabs.py): its schema, what it is called in messages, and
    # the name its previous revision is kept under.
    schema, noun, prev = SCHEMA, 'project', 'project.prev.json'

    def check(self, document):
        """A document the listing, the page and the Build can read: of a schema this editor reads, and of the least
        shape they read (shape_problem); else a ProjectError that says why."""
        check_schema(document)
        problem = shape_problem(document)
        if problem: raise ProjectError(422, f'This {self.noun} can\'t be read: {problem}.')

    def readable(self, document):
        """Whether the listing prefers this document over a copy that can't be read (prefabs: always)."""
        return shape_problem(document) is None

    def validate(self, document, project_id):
        validate(document, project_id)

    def summary(self, path, document):
        source = document.get('source') or {}
        return dict(id=document['id'], name=document.get('name'), map=source.get('map'), file=path.name,
                    revision=document.get('revision'), savedAt=document.get('savedAt'),
                    recovery=bool(self._drafts(document['id'])))

    def __init__(self, root, names=None):
        """names: what checks a new project's output names as it saves (outputnames.Service; the server's), or None
        (a store a tool opens checks their form alone)."""
        self.root = Path(root)
        self.lock = threading.RLock()
        self.paths = {}             # project id -> its file, as last found; checked before each use
        self.names = names

    def check_output(self, document, current):
        """A project's output names as it saves, in the store's lock (output names plan 3.3): fixed once saved, so a
        saved project's next revision must carry them exactly (a case-only change of its name keeps them as they
        are); a new project's (or one saved without any) are checked by `names` when the store has it."""
        before = current.get('output') if isinstance(current, dict) else None
        if valid_output(before):
            if document.get('output') != before:
                raise ProjectError(409, f'This project builds as {before["shipAs"]}: its map name is fixed when it is '
                                        f'first saved. Use Save as with a new name to save it as a new project that '
                                        f'builds under a name of its own.', output=before)
            return
        if self.names is not None:
            self.names.check_new(document)

    def check_id(self, project_id):
        if not isinstance(project_id, str) or not ID.fullmatch(project_id): raise ProjectError(404, f'No such {self.noun}.')
        return project_id

    def state(self, project_id):
        """The folder of what stays on this computer for a project: its previous revision and recovery."""
        return self.root / STATE / self.check_id(project_id)

    @staticmethod
    def _read(path):
        try: return json.loads(path.read_text(encoding='utf8'))
        except FileNotFoundError: return None
        except (OSError, ValueError) as error: raise ProjectError(500, f'{path.name} could not be read: {error}')

    @staticmethod
    def _write(path, value):
        temp = path.with_name(path.name + '.tmp')
        with open(temp, 'w', encoding='utf8', newline='\n') as stream:
            json.dump(value, stream, indent=1, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)

    def _state_folder(self, project_id):
        state = self.state(project_id)
        if not state.parent.is_dir():
            state.parent.mkdir(parents=True, exist_ok=True)
            hide(state.parent)
        state.mkdir(exist_ok=True)
        return state

    def _id_of(self, path):
        try:
            document = json.loads(path.read_text(encoding='utf8'))
            return document.get('id') if isinstance(document, dict) else None
        except (OSError, ValueError):
            return None

    # ------------------------------------------------------------------ finding the files

    @staticmethod
    def _rank(document):
        """Which of two documents of one project is the project: the higher revision, then the later save."""
        if not isinstance(document, dict): return (-1, '')
        revision = document.get('revision')
        return (revision if isinstance(revision, int) and not isinstance(revision, bool) else 0, str(document.get('savedAt') or ''))

    @staticmethod
    def _free(path):
        """`path`, or the first `<stem> (2)`, `(3)`... beside it that is free: nothing is written over."""
        if not path.exists(): return path
        for n in itertools.count(2):
            other = path.with_name(f'{path.stem} ({n}){path.suffix}')
            if not other.exists(): return other

    def _migrate(self):
        """Moves each project folder of the old layout (<id>\\project.json) to a file named after the project, its
        previous revision and recovery to .workshop\\<id>\\. The folder goes once empty; anything else in it stays.

        Nothing is written over (review finding 5). When a file of this layout holds the project already (a backup
        restored beside a current library), the two are ranked as the listing ranks copies (revision, then the later
        save; the file here wins a tie) and the other is kept beside it as `<name> (kept copy).json`, which the
        listing shows as a copy of the project; the same bytes twice keep one. A previous revision or a draft whose
        name is taken is kept under a name of its own (a draft as another page's). Each step is one rename, so a
        stop halfway leaves the folder to finish at the next listing."""
        if not self.root.is_dir(): return
        for folder in sorted(self.root.iterdir()):
            old = folder / 'project.json'
            if not folder.is_dir() or not ID.fullmatch(folder.name) or not old.is_file(): continue
            try: document = json.loads(old.read_text(encoding='utf8'))
            except (OSError, ValueError): document = None
            project_id = document.get('id') if isinstance(document, dict) and ID.fullmatch(str(document.get('id'))) else folder.name
            name = document.get('name') if isinstance(document, dict) and isinstance(document.get('name'), str) and document['name'].strip() else folder.name
            state = None
            for kept in ('project.prev.json', 'recovery.json'):
                source = folder / kept
                if not source.is_file(): continue
                state = state or self._state_folder(project_id)
                target = state / kept
                if target.exists():
                    if target.read_bytes() == source.read_bytes():
                        source.unlink(); continue
                    target = state / f'recovery-{uuid.uuid4()}.json' if kept == 'recovery.json' else self._free(target)
                os.replace(source, target)
            target = self._target(project_id, name, None)
            if not target.exists():
                os.replace(old, target)
            elif target.read_bytes() == old.read_bytes():
                old.unlink()
            else:
                copy = self._free(target.with_name(f'{target.stem} (kept copy){SUFFIX}'))
                try: here = json.loads(target.read_text(encoding='utf8'))
                except (OSError, ValueError): here = None
                if self._rank(document) > self._rank(here):
                    os.replace(target, copy)        # the file here is the older: kept beside, then the folder's moves in
                    os.replace(old, target)
                else:
                    os.replace(old, copy)
            for temp in folder.glob('*.tmp'): temp.unlink(missing_ok=True)
            try: folder.rmdir()
            except OSError: pass

    def _scan(self):
        """Every project file: [(path, document or ProjectError)], with self.paths refreshed. A project of another
        schema version is found by its id (opening it says which version) but listed with its error. Two files with
        one project id (a copy made beside it): the newest revision is the project, the other is listed as a copy."""
        self._migrate()
        found = []
        if self.root.is_dir():
            for path in sorted(self.root.iterdir()):
                if not path.is_file() or path.suffix.lower() != SUFFIX: continue
                try:
                    document = self._read(path)
                    if not isinstance(document, dict) or document.get('schema') != self.schema:
                        raise ProjectError(422, f'This is not an XCOM Map Workshop {self.noun}.')
                    if not ID.fullmatch(str(document.get('id'))): raise ProjectError(422, f'The {self.noun} has no valid id.')
                    found.append((path, document))
                except ProjectError as error:
                    found.append((path, error))
        best = {}
        for path, document in found:
            if isinstance(document, ProjectError): continue
            # (a copy that can be read is the project before one that can't: review finding 9)
            rank = (self.readable(document), *self._rank(document), file_stem(str(document.get('name'))) == path.stem)
            if document['id'] not in best or rank > best[document['id']][0]: best[document['id']] = (rank, path)
        self.paths = {project_id: path for project_id, (_, path) in best.items()}
        rows = []
        for path, document in found:
            if not isinstance(document, ProjectError):
                if not same_path(self.paths[document['id']], path):
                    document = ProjectError(409, f'A copy of the {self.noun} in “{self.paths[document["id"]].name}” (the '
                                                 f'same {self.noun} id). Open that one; delete or move this copy.')
                else:
                    try: self.check(document)
                    except ProjectError as error: document = error
            rows.append((path, document))
        return rows

    def _find(self, project_id):
        """The project's file, or None."""
        self.check_id(project_id)
        with self.lock:
            path = self.paths.get(project_id)
            if path is not None and path.is_file() and self._id_of(path) == project_id: return path
            self._scan()
            return self.paths.get(project_id)

    def _target(self, project_id, name, current):
        """The file a save of the project under this name writes: <name>.json, or <name> (2).json and so on when
        another project holds that name."""
        stem = file_stem(name)
        for n in itertools.count(1):
            path = self.root / f'{stem}{f" ({n})" if n > 1 else ""}{SUFFIX}'
            if current is not None and same_path(path, current): return path
            if not path.exists() or self._id_of(path) == project_id: return path

    def path(self, project_id):
        """The project's file (the build reads it)."""
        path = self._find(project_id)
        if path is None: raise ProjectError(404, f'No such {self.noun}.')
        return path

    # ------------------------------------------------------------------ the routes' operations

    def list(self):
        """Every project's summary, newest save first; unreadable ones (and copies) are listed with their error."""
        with self.lock: rows = self._scan()
        found = []
        for path, document in rows:
            if isinstance(document, ProjectError):
                found.append(dict(id=path.name, name=path.name, file=path.name, error=document.message))
                continue
            found.append(self.summary(path, document))
        return sorted(found, key=lambda p: str(p.get('savedAt') or ''), reverse=True)

    def capture(self, project_id):
        """The saved project exactly as a build of it is to read it (build queue plan, 9.1): (document, the file's bytes,
        their SHA-256, the file), read whole under the store's lock, so a save or a rename can't replace it mid-read.
        The caller writes those bytes to a snapshot of its own before it builds; a later save changes nothing of it."""
        import hashlib
        with self.lock:
            path = self._find(project_id)
            if path is None: raise ProjectError(404, f'No such {self.noun}.')
            try: data = path.read_bytes()
            except OSError as error: raise ProjectError(500, f'{path.name} could not be read: {error}')
        try: document = json.loads(data.decode('utf8'))
        except (UnicodeDecodeError, ValueError) as error: raise ProjectError(422, f'{path.name} could not be read: {error}')
        self.check(document)
        if document.get('id') != project_id: raise ProjectError(409, f'{path.name} now holds another {self.noun}.')
        return document, data, hashlib.sha256(data).hexdigest(), path

    def load(self, project_id):
        path = self._find(project_id)
        document = self._read(path) if path else None
        if document is None: raise ProjectError(404, f'No such {self.noun}.')
        self.check(document)
        return document

    def save(self, project_id, document, expected, owner=None):
        """Write the next revision if `expected` is the current one (0 for a new project); returns it. `owner`: the
        page session saving, whose draft for recovery the save holds now and so removes (other sessions' stay)."""
        self.check_id(project_id)
        self.validate(document, project_id)
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise ProjectError(400, 'expectedRevision must be a whole number.')
        if owner is not None: self._draft_path(project_id, owner)      # (checked before anything is written)
        with self.lock:
            current_path = self._find(project_id)
            current = self._read(current_path) if current_path else None
            revision = current.get('revision', 0) if isinstance(current, dict) else 0
            if current is not None: self.check(current)
            if expected != revision:
                raise ProjectError(409, f'This {self.noun} was saved elsewhere since (revision {revision}).', revision=revision)
            # its output names, in the lock: two first saves can't both take one name
            self.check_output(document, current)
            document = dict(document, revision=revision + 1, savedAt=now())
            document.setdefault('created', document['savedAt'])
            self.root.mkdir(parents=True, exist_ok=True)
            target = self._target(project_id, document['name'], current_path)
            if current is not None:
                # Keep the previous revision, itself written atomically, before replacing the project.
                state = self._state_folder(project_id)
                shutil.copyfile(current_path, state / (self.prev + '.tmp'))
                os.replace(state / (self.prev + '.tmp'), state / self.prev)
                # Only the case of the name changed: rename the file first, so it shows the new case.
                if same_path(target, current_path) and target.name != current_path.name: os.replace(current_path, target)
            self._write(target, document)
            if current_path is not None and not same_path(current_path, target): current_path.unlink(missing_ok=True)
            if owner is not None:
                try: self._draft_path(project_id, owner).unlink(missing_ok=True)
                except OSError: pass        # (saved all the same: the draft is offered once more, then discarded)
            self.paths[project_id] = target
            return dict(revision=document['revision'], savedAt=document['savedAt'], created=document['created'],
                        file=target.name)

    # ------------------------------------------------------------------ drafts kept for recovery (review finding 3)
    # Each page session keeps its own draft (`owner`: the id the page made when it loaded), so two pages editing one
    # project never write over or delete each other's. A page deletes only its own draft (on saving, discarding or
    # leaving), or the one it showed the user and the user restored or discarded (by its owner and time). A draft
    # based on an older revision than the saved one (another page saved meanwhile) is kept too, and said to be stale.

    def _draft_path(self, project_id, owner):
        """The file of `owner`'s draft (None: the one kept before drafts had owners)."""
        state = self.state(project_id)
        if owner is None: return state / 'recovery.json'
        if not isinstance(owner, str) or not ID.fullmatch(owner):
            raise ProjectError(400, 'A draft\'s owner is the id of the page session that keeps it.')
        return state / f'recovery-{owner}.json'

    def _drafts(self, project_id):
        """[(file, owner or None)]: the drafts kept for the project."""
        state = self.state(project_id)
        try: names = os.listdir(state)
        except OSError: return []
        found = []
        for name in sorted(names):
            if name == 'recovery.json': found.append((state / name, None))
            elif name.startswith('recovery-') and name.endswith('.json') and ID.fullmatch(name[9:-5]):
                found.append((state / name, name[9:-5]))
        return found

    def recovery(self, project_id):
        """The newest draft kept for the project, with its `owner` (null: kept before drafts had owners) and `others`
        (how many more are kept), or None. A draft that can't be read is passed over."""
        drafts = []
        for path, owner in self._drafts(project_id):
            try: state = self._read(path)
            except ProjectError: continue
            if isinstance(state, dict): drafts.append(dict(state, owner=owner))
        if not drafts: return None
        drafts.sort(key=lambda d: str(d.get('savedAt') or ''), reverse=True)
        return dict(drafts[0], others=len(drafts) - 1)

    def _stale(self, project_id, state):
        """{revision, stale}: the saved revision and whether the draft is based on an older one (refused when it is
        based on a newer one, which no page has)."""
        current = self.load(project_id).get('revision', 0)
        base = state.get('baseRevision')
        if base is None: return dict(revision=current, stale=False)
        if not isinstance(base, int) or isinstance(base, bool) or base < 0:
            raise ProjectError(422, 'A draft\'s baseRevision is a whole number.')
        if base > current:
            raise ProjectError(409, f'This draft is based on revision {base}; the {self.noun} is at revision {current}.',
                               revision=current)
        return dict(revision=current, stale=base < current)

    def save_recovery(self, project_id, state):
        """Keeps a page session's draft (`state.owner`: the session; none: the owner-less file). Answers {ok,
        revision, stale}."""
        if not isinstance(state, dict): raise ProjectError(422, 'Recovery state must be an object.')
        path = self._draft_path(project_id, state.get('owner'))
        with self.lock:
            if self._find(project_id) is None: raise ProjectError(404, f'No such {self.noun}.')
            answer = self._stale(project_id, state)
            self._state_folder(project_id)
            self._write(path, dict(state, savedAt=now()))
            return dict(answer, ok=True)

    def drop_recovery(self, project_id, owner=None, saved_at=None):
        """Deletes `owner`'s draft (None: the owner-less one), and only while it is still the one kept at `saved_at`
        when that is given (a draft the user was shown, and that its page may have kept again since). Answers
        {dropped}."""
        path = self._draft_path(project_id, owner)
        with self.lock:
            if saved_at is not None:
                try: kept = self._read(path)
                except ProjectError: kept = None
                if not isinstance(kept, dict) or kept.get('savedAt') != saved_at: return dict(dropped=False)
            try:
                if not path.is_file(): return dict(dropped=False)
                path.unlink()
            except OSError as error:
                raise ProjectError(500, f'The kept changes could not be discarded: {error}')
            return dict(dropped=True)
