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
older revision is refused as a conflict instead of overwriting work saved from another tab. A document of a schema
version the editor reads (READ_VERSIONS) opens, and a save writes the current one (SCHEMA_VERSION); any other version
is refused with a clear message.
"""
from datetime import datetime, timezone
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import threading

import atomic_files

SCHEMA = 'xcom-map-workshop/project'
# 2: pieces' flags (overrides[].flags, added[].flags; piece flags plan); 3: effects and sounds (records of their own:
# the effects and sounds plan, Part C); 4: the spawns plan's records (`spawnRules`, SP8; the base map's spawn points'
# overrides and added records, SP6 and SP7); 5: the map's background sound (`backgroundSound`) and a clear that keeps
# the map's triggers (`clearKeepsTriggers`); 6: what Long War Rebalance is told of the map (`lwrMapInfo`); 7: the
# diagonal cover the project marks (`diagonalCover`); 8: a building's floors as the cursor's (`buildings[].cursorFloors`).
# 1 to 7 are read too, and saved as 8.
SCHEMA_VERSION = 8
READ_VERSIONS = (1, 2, 3, 4, 5, 6, 7, 8)
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


def os_reason(error):
    """Why a file operation failed, in words the page shows (review finding 46)."""
    import errno
    if error.errno == errno.ENOSPC or getattr(error, 'winerror', None) in (39, 112): return 'the disk is full'
    if isinstance(error, PermissionError) or getattr(error, 'winerror', None) in (5, 32, 33):
        return ('access was refused: the file is open in another program, or the file or its folder is read-only'
                f' ({error.strerror or error})')
    return str(error.strerror or error)


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
    if not isinstance(document.get('clearKeepsTriggers', False), bool):
        raise ProjectError(422, '"clearKeepsTriggers" must be true or false.')
    # The map's background sound (schema 5): optional, {cue, volume?}; the compiler checks the cue and the volume.
    sound = document.get('backgroundSound')
    if sound is not None and not (isinstance(sound, dict) and 'cue' in sound and set(sound) <= {'cue', 'volume'}):
        raise ProjectError(422, '"backgroundSound" must be {cue, volume}: a sound\'s path or null, and a volume.')
    # What Long War Rebalance is told of the map (schema 6): optional, a record of texts; the compiler checks the keys
    # and their values.
    info = document.get('lwrMapInfo')
    if info is not None and not (isinstance(info, dict) and all(isinstance(v, str) for v in info.values())):
        raise ProjectError(422, '"lwrMapInfo" must be a record of texts.')
    # The diagonal cover the project marks (schema 7): optional, {marks: [records], removed: [places]}; the compiler
    # checks each mark and place.
    diagonal = document.get('diagonalCover')
    if diagonal is not None and not (isinstance(diagonal, dict) and set(diagonal) <= {'marks', 'removed'}
                                     and isinstance(diagonal.get('marks', []), list)
                                     and all(isinstance(m, dict) for m in diagonal.get('marks', []))
                                     and isinstance(diagonal.get('removed', []), list)):
        raise ProjectError(422, '"diagonalCover" must be {marks, removed}: a list of marks and a list of places.')
    zones =document.get('landingZones', [])
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

    def live(self, summary):
        """A cached summary with what other files say brought up to date: whether drafts are kept."""
        return dict(summary, recovery=bool(self._drafts(summary['id'])))

    def __init__(self, root, names=None):
        """names: what checks a new project's output names as it saves (outputnames.Service; the server's), or None
        (a store a tool opens checks their form alone)."""
        self.root = Path(root)
        self.lock = threading.RLock()
        self.paths = {}             # project id -> its file, as last found; checked before each use
        self.names = names
        # What each file in the folder said the last time it was read (review finding 20): file -> {stamp (modified
        # time, size, file id), entry (dict(id, rank, readable, named, problem, summary, name, revision, output) or a
        # ProjectError), claim ((output, owner, name) of a document of this schema, or None)}. A file is read again
        # only when its stamp changed; `reads` counts the reads.
        self.cache, self.reads = {}, 0

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

    def _read(self, path):
        self.reads += 1         # (every JSON file the store reads, drafts too: review finding 20's count)
        try: return json.loads(path.read_text(encoding='utf8'))
        except FileNotFoundError: return None
        except (OSError, ValueError) as error: raise ProjectError(500, f'{path.name} could not be read: {error}')

    @staticmethod
    def _write(path, value):
        """`value` written to `path` through a temporary file and flushed to the disk (atomic_files, which tries a
        replace that another program's hold refuses again); a failure (a full disk, a file held too long, a read-only
        folder) is a ProjectError that says why, the temporary file gone (review finding 46)."""
        try:
            atomic_files.write_text(path, json.dumps(value, indent=1, ensure_ascii=False) + '\n', sync=True)
        except OSError as error:
            raise ProjectError(500, f'{path.name} could not be written: {os_reason(error)}.') from None

    def _state_folder(self, project_id):
        state = self.state(project_id)
        if not state.parent.is_dir():
            state.parent.mkdir(parents=True, exist_ok=True)
            hide(state.parent)
        state.mkdir(exist_ok=True)
        return state

    def _id_of(self, path):
        record = self._look(path)
        return record['id'] if record else None

    def _look(self, path):
        """What the file says (self.cache's record), read again only when it changed; None when it is gone."""
        try: stat = path.stat()
        except OSError: return None
        stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        with self.lock:
            record = self.cache.get(str(path))
            if record and record['stamp'] == stamp: return record
            try: document = self._read(path)
            except ProjectError as error: document = error
            record = dict(stamp=stamp, id=document.get('id') if isinstance(document, dict) else None, claim=None,
                          entry=self._entry(path, document))
            if isinstance(document, dict) and document.get('schema') == self.schema and isinstance(document.get('output'), dict):
                record['claim'] = (document['output'], document.get('id') if isinstance(document.get('id'), str) and document.get('id') else None,
                                   document.get('name') or path.stem)
            self.cache[str(path)] = record
            return record

    def _entry(self, path, document):
        """What the listing and the lookups need of a file's document: dict(id, rank, readable, named, problem,
        summary, name, revision, output), or the ProjectError that makes it no document of this store's."""
        if isinstance(document, ProjectError): return document
        if not isinstance(document, dict) or document.get('schema') != self.schema:
            return ProjectError(422, f'This is not an XCOM Map Workshop {self.noun}.')
        if not ID.fullmatch(str(document.get('id'))): return ProjectError(422, f'The {self.noun} has no valid id.')
        try: self.check(document); problem = None
        except ProjectError as error: problem = error
        return dict(id=document['id'], rank=self._rank(document), readable=self.readable(document),
                    named=file_stem(str(document.get('name'))) == path.stem, problem=problem,
                    summary=None if problem else self.summary(path, document), name=document.get('name'),
                    revision=document.get('revision'), output=document.get('output'))

    def cached(self, project_id):
        """What the store knows of the project from its last read of the project's file (review finding 20): its
        `name`, `revision`, `output` (and the listing's summary), read again only when the file changed. For the polled
        routes (the build status, the queue view). A ProjectError when there is no such project or it can't be read."""
        with self.lock:
            path = self._find(project_id)
            record = self._look(path) if path is not None else None
        entry = record['entry'] if record else ProjectError(404, f'No such {self.noun}.')
        if isinstance(entry, ProjectError): raise entry
        if entry['problem']: raise entry['problem']
        return entry

    def claimed(self):
        """[(output, owner id or None, name)] of every file of this schema in the folder that has output names
        (outputnames.Claims), from what the files said when last read. An OSError when the folder can't be read."""
        with self.lock:
            self._scan(strict=True)
            return [r['claim'] for r in self.cache.values() if r['claim']]

    # ------------------------------------------------------------------ finding the files

    @staticmethod
    def _rank(document):
        """Which of two documents of one project is the project: the higher revision, then the later save."""
        if not isinstance(document, dict): return (-1, '')
        revision = document.get('revision')
        return (revision if isinstance(revision, int) and not isinstance(revision, bool) else 0, str(document.get('savedAt') or ''))

    def _scan(self, strict=False):
        """Every project file: [(path, entry or ProjectError)] (`_entry`), with self.paths refreshed. A project of
        another schema version is found by its id (opening it says which version) but listed with its error. Two files
        with one project id (a copy made beside it): the newest revision is the project, the other is listed as a
        copy. A file unchanged since it was last read is not read again (review finding 20). `strict`: a folder that
        can't be read is an OSError, not an empty listing."""
        found = []
        if self.root.is_dir():
            try: paths = sorted(self.root.iterdir())
            except OSError:
                if strict: raise
                paths = []
            for path in paths:
                if path.suffix.lower() != SUFFIX or not path.is_file(): continue
                record = self._look(path)
                if record is not None: found.append((path, record['entry']))
        seen = {str(path) for path, _ in found}
        for key in [k for k in self.cache if k not in seen]: del self.cache[key]       # (files gone since)
        best = {}
        for path, entry in found:
            if isinstance(entry, ProjectError): continue
            # (a copy that can be read is the project before one that can't: review finding 9)
            rank = (entry['readable'], *entry['rank'], entry['named'])
            if entry['id'] not in best or rank > best[entry['id']][0]: best[entry['id']] = (rank, path)
        self.paths = {project_id: path for project_id, (_, path) in best.items()}
        rows = []
        for path, entry in found:
            if not isinstance(entry, ProjectError):
                if not same_path(self.paths[entry['id']], path):
                    entry = ProjectError(409, f'A copy of the {self.noun} in “{self.paths[entry["id"]].name}” (the '
                                              f'same {self.noun} id). Open that one; delete or move this copy.')
                elif entry['problem']:
                    entry = entry['problem']
            rows.append((path, entry))
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
        """Every project's summary, newest save first; unreadable ones (and copies) are listed with their error. A file
        unchanged since the last listing is not read again."""
        with self.lock: rows = self._scan()
        found = []
        for path, entry in rows:
            if isinstance(entry, ProjectError):
                found.append(dict(id=path.name, name=path.name, file=path.name, error=entry.message))
                continue
            found.append(self.live(entry['summary']))
        return sorted(found, key=lambda p: str(p.get('savedAt') or ''), reverse=True)

    def listing(self):
        """Every project as the project manager lists it (review finding 20): [(summary, document or None)], newest
        save first, each project's file read once, its summary made from the very document given (None, and the
        summary's `error`, when it can't be read)."""
        with self.lock: rows = self._scan()
        found = []
        for path, entry in rows:
            if isinstance(entry, ProjectError):
                found.append((dict(id=path.name, name=path.name, file=path.name, error=entry.message), None))
                continue
            try:
                document = self._read(path)
                if document is None: raise ProjectError(404, f'No such {self.noun}.')
                self.check(document)
                if document.get('id') != entry['id']: raise ProjectError(409, f'{path.name} now holds another {self.noun}.')
            except ProjectError as error:
                found.append((dict(entry['summary'], error=error.message), None))
                continue
            found.append((self.live(self.summary(path, document)), document))
        return sorted(found, key=lambda p: str(p[0].get('savedAt') or ''), reverse=True)

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

    def save(self, project_id, document, expected, owner=None, picture_from=None):
        """Write the next revision if `expected` is the current one (0 for a new project); returns it. `owner`: the
        page session saving, whose draft for recovery the save holds now and so removes (other sessions' stay).
        `picture_from`: Save as from that project, whose kept map picture the document names: copied to this one
        before the document is written (review finding 8; `pictureMissing` in the answer when that project keeps no
        such picture, and the document is saved naming it all the same)."""
        self.check_id(project_id)
        self.validate(document, project_id)
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise ProjectError(400, 'expectedRevision must be a whole number.')
        if owner is not None: self._draft_path(project_id, owner)      # (checked before anything is written)
        if picture_from is not None: self.check_id(picture_from)
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
            # (a full disk, a locked file or a read-only folder: said, not a dropped connection, review finding 46)
            try:
                self.root.mkdir(parents=True, exist_ok=True)
                pictured = self._pictures(project_id, document, current, current_path, picture_from)
                target = self._target(project_id, document['name'], current_path)
                if current is not None:
                    # Keep the previous revision, itself written atomically, before replacing the project.
                    state = self._state_folder(project_id)
                    shutil.copyfile(current_path, state / (self.prev + '.tmp'))
                    atomic_files.replace(state / (self.prev + '.tmp'), state / self.prev)
                    # Only the case of the name changed: rename the file first, so it shows the new case.
                    if same_path(target, current_path) and target.name != current_path.name:
                        atomic_files.replace(current_path, target)
            except OSError as error:
                raise ProjectError(500, f'Nothing was written in {self.root}: {os_reason(error)}.') from None
            self._write(target, document)
            if current_path is not None and not same_path(current_path, target):
                try: current_path.unlink(missing_ok=True)
                except OSError as error:        # (saved: said beside the answer)
                    pictured = dict(pictured, note=f'{current_path.name}, the {self.noun}\'s file before it was renamed, '
                                                   f'could not be removed ({os_reason(error)}): it is listed as a copy '
                                                   f'until it is deleted.')
            if owner is not None:
                try: self._draft_path(project_id, owner).unlink(missing_ok=True)
                except OSError: pass        # (saved all the same: the draft is offered once more, then discarded)
            self.paths[project_id] = target
            return dict(revision=document['revision'], savedAt=document['savedAt'], created=document['created'],
                        file=target.name, **pictured)

    def _pictures(self, project_id, document, current, current_path, picture_from):
        """The map picture the document names, kept with the project before the document is written (pictures.py):
        copied from `picture_from` (Save as), or taken in from beside the project's file (one sent with it), which a
        rename would leave behind. {} or {pictureMissing: True}."""
        import pictures
        digest = pictures.named(document)
        if not digest: return {}
        if picture_from is not None and picture_from != project_id:
            try:
                copied = pictures.copy_picture(self, picture_from, project_id, digest, saved=pictures.named(current))
            except OSError as error:
                raise ProjectError(500, f'The map picture could not be copied to the project ({error}); nothing was saved.')
            return {} if copied else dict(pictureMissing=True)
        if current_path is not None: pictures.adopt_beside(self, current_path, document)
        return {}

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
            try: self._state_folder(project_id)
            except OSError as error: raise ProjectError(500, f'The folder for kept changes could not be made: {os_reason(error)}.') from None
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
