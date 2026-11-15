"""Editor projects on disk (first-editor plan, section 3; contracts in research/editor-contracts.md).

One file per project in the projects folder, named after the project, so a project is shared by sending that file:

    Bar remix.json                       the saved document (any name ending .json is read; the id inside is what counts)
    .workshop\\<id>\\project.prev.json     the revision before it, kept by every save
    .workshop\\<id>\\recovery.json         unsaved state the browser autosaves; removed by the next save

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

SCHEMA = 'xcom-map-workshop/project'
SCHEMA_VERSION = 1
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


def check_schema(document):
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        raise ProjectError(422, 'This is not an XCOM Map Workshop project.')
    version = document.get('schemaVersion')
    if version != SCHEMA_VERSION:
        raise ProjectError(409, f'This project was saved with project schema {version}; this editor reads schema '
                                f'{SCHEMA_VERSION} only. Open it with the editor version that saved it.', schemaVersion=version)


def validate(document, project_id):
    """The checks the server can make without the map: shape, identity and binding. The browser checks the edits
    against the map when it opens them."""
    check_schema(document)
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
        check_schema(document)

    def validate(self, document, project_id):
        validate(document, project_id)

    def summary(self, path, document):
        source = document.get('source') or {}
        return dict(id=document['id'], name=document.get('name'), map=source.get('map'), file=path.name,
                    revision=document.get('revision'), savedAt=document.get('savedAt'),
                    recovery=(self.state(document['id']) / 'recovery.json').is_file())

    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.paths = {}             # project id -> its file, as last found; checked before each use

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

    def _migrate(self):
        """Moves each project folder of the old layout (<id>\\project.json) to a file named after the project, its
        previous revision and recovery to .workshop\\<id>\\. The folder goes once empty; anything else in it stays."""
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
                if (folder / kept).is_file():
                    state = state or self._state_folder(project_id)
                    os.replace(folder / kept, state / kept)
            os.replace(old, self._target(project_id, name, None))
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
            revision = document.get('revision')
            rank = (revision if isinstance(revision, int) else 0, str(document.get('savedAt') or ''),
                    file_stem(document.get('name')) == path.stem)
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

    def load(self, project_id):
        path = self._find(project_id)
        document = self._read(path) if path else None
        if document is None: raise ProjectError(404, f'No such {self.noun}.')
        self.check(document)
        return document

    def save(self, project_id, document, expected):
        """Write the next revision if `expected` is the current one (0 for a new project); returns it."""
        self.check_id(project_id)
        self.validate(document, project_id)
        if not isinstance(expected, int) or expected < 0: raise ProjectError(400, 'expectedRevision must be a whole number.')
        with self.lock:
            current_path = self._find(project_id)
            current = self._read(current_path) if current_path else None
            revision = current.get('revision', 0) if isinstance(current, dict) else 0
            if current is not None: self.check(current)
            if expected != revision:
                raise ProjectError(409, f'This {self.noun} was saved elsewhere since (revision {revision}).', revision=revision)
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
            (self.state(project_id) / 'recovery.json').unlink(missing_ok=True)
            self.paths[project_id] = target
            return dict(revision=document['revision'], savedAt=document['savedAt'], created=document['created'],
                        file=target.name)

    def recovery(self, project_id):
        return self._read(self.state(project_id) / 'recovery.json')

    def save_recovery(self, project_id, state):
        if not isinstance(state, dict): raise ProjectError(422, 'Recovery state must be an object.')
        with self.lock:
            if self._find(project_id) is None: raise ProjectError(404, f'No such {self.noun}.')
            self._write(self._state_folder(project_id) / 'recovery.json', dict(state, savedAt=now()))

    def drop_recovery(self, project_id):
        with self.lock: (self.state(project_id) / 'recovery.json').unlink(missing_ok=True)
