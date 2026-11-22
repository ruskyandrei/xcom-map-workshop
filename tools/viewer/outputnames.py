"""A project's output names (output names plan): what its map is called in the game, and who holds the names a build
writes. The server's Save dialog asks it for a new project's map name (POST /projects/output-names), the projects
store checks a new project's names with it as it saves (projects.py), and the Build (tools/editor/build.py) and the
installs (installs.py) check what they write against the same claims.

A new project builds as its project name made one word (convert), at most LIMIT characters, numbered when that is
taken (allocate). Its names are fixed at its first save: the map (output.shipAs), its edit patch (output.patch,
patch_<map in lower case>), its texture cache when a build bakes one (<map>_Lighting.tfc: cache_name) and the copies a
build makes of streamed packages (<stream>_<map>: the landing intros, and a stream whose pieces the project moves or
deletes). Projects saved before 16 November 2026 keep the names they have (the base map's, the project's and a piece
of its id).

Names are compared regardless of case, as Windows compares file names. A name is taken (Claims) when any of these
holds it:
- another project's output names, in the projects folder (an imported file too);
- a build in the builds folder: its folder and every name its manifest lists (files, patch, cache, the intro and
  stream copies), whichever project's it is; a folder there without a readable manifest is taken too;
- a package or other file of a game install (the one the editor reads and the one it plays in), and the names its
  DefaultMaps.ini records use (maps and the streams they load);
- a variant the editor installed there (its ledgers), and the files it copied in;
- in the lab copy, a file the lab's own deploy tools put there before the editor could install (installs.lab_deploys):
  soft, as a project's earlier test;
- a Windows device name (CON, NUL, COM1...), and the prefixes kept for other files (RESERVED_PREFIXES).
A project's own claims don't count against it, but only where something says they are its own: its id in a build's
manifest or in the install's ledger. A name taken locally may still be free or taken elsewhere: a pack shared with
someone else can meet a name on their install, which their install step then refuses.
"""
import json
import os
from pathlib import Path
import re
import unicodedata

from projects import RESERVED as DEVICES, SCHEMA as PROJECT_SCHEMA, ProjectError, valid_output  # noqa: F401

LIMIT = 24              # a newly allocated map name: its patch, patch_<name>, keeps to PACKAGE_LIMIT
PACKAGE_LIMIT = 30      # UDK's Save As refuses longer package names (findings register T-09)
CACHE_SUFFIX = '_Lighting'
# the streamed intros a build copies under the variant's name (tools/editor/build.py and tools/bake/intro_copy.py)
INTROS = ('CIN_DropshipIntros', 'CIN_FastropeIntros', 'CIN_TP05A_EnteringAlienBase')
# the beginnings kept for other files: edit patches, a prefab test's map and patch, and the intro copies
RESERVED_PREFIXES = ('patch_', 'pt_', 'pp_') + tuple(f'{i}_' for i in INTROS)
PACKAGE = re.compile(r'[A-Za-z][A-Za-z0-9_]*')
ATTEMPTS = 999          # numbers tried after the plain name (_2 ... _999) before giving up
BUILD_SCHEMA = 'xcom-map-workshop/variant-package'


class NamesError(Exception):
    """A source of claims that is set but can't be read, or no free name left."""


def cache_name(variant):
    """The texture cache a baked build of `variant` writes: <variant>_Lighting (a .tfc beside the map)."""
    return variant + CACHE_SUFFIX


def patch_name(variant):
    return 'patch_' + variant.lower()


def _word(name):
    """The name's ASCII letters, digits and underscores as typed, accents taken off first (so é is e, and an accent
    never splits a word), every other character a break that goes; each word's first letter a capital."""
    text = unicodedata.normalize('NFKD', str(name))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    out, start = [], True
    for c in text:
        if c.isascii() and (c.isalnum() or c == '_'):
            out.append(c.upper() if start and c.isalpha() else c)
            start = False
        else:
            start = True
    word = ''.join(out)
    if not word: return 'Map'
    return word if word[0].isalpha() else 'Map' + word


def kept_prefix(word):
    """The kept prefix `word` starts with (RESERVED_PREFIXES, regardless of case), or None."""
    return next((p for p in RESERVED_PREFIXES if word.lower().startswith(p.lower())), None)


def convert(name):
    """The project's name as one word for a package (_word), Map in front when it would start with no letter or with
    a kept prefix (once, before it is cut or numbered). Not cut to LIMIT: candidates does that."""
    word = _word(name)
    return 'Map' + word if kept_prefix(word) else word


def candidates(stem, limit=LIMIT):
    """The names tried for `stem` in order: the stem cut to `limit`, then _2, _3... each on the stem cut shorter so
    that the number fits."""
    yield stem[:limit]
    for n in range(2, ATTEMPTS + 1):
        tail = f'_{n}'
        yield stem[:limit - len(tail)] + tail


def is_device(name):
    return name.split('.')[0].upper() in DEVICES


def derived(variant, streams=()):
    """Every name a build of `variant` can write: the map, its patch, its texture cache and a copy of each stream in
    `streams` (the intros and the other streams of its base map's records)."""
    return [variant, patch_name(variant), cache_name(variant)] + [f'{s}_{variant}' for s in dict.fromkeys(streams)]


def allocate(name, taken, streams=()):
    """A new project's output names for the project name `name`: {shipAs, patch, reason}. `taken(names)` says why
    one of the names is taken (a phrase), or None. reason: why the map name is not the name as one word (a kept
    prefix, taken, a device name), or None. A NamesError when every number is taken."""
    stem, prefix = convert(name), kept_prefix(_word(name))
    first_why = None
    for n, candidate in enumerate(candidates(stem)):
        why = 'Windows keeps that name for a device' if is_device(candidate) else taken(derived(candidate, streams))
        if why is None:
            reasons = []
            if prefix: reasons.append(f'names that start {prefix} are kept for other files, so Map goes in front')
            if n: reasons.append(f'{stem[:LIMIT]} is taken ({first_why}), so the name is numbered')
            return dict(shipAs=candidate, patch=patch_name(candidate), reason='; '.join(reasons) or None)
        if n == 0: first_why = why
    raise NamesError(f'every name from {stem[:LIMIT]} to {candidate} is taken; choose another project name')


def accepts(name, output, taken, streams=()):
    """None when `output` is names `allocate` could give the project name `name` now (one of its numbered names, free),
    else why not (a phrase)."""
    if not valid_output(output): return 'they are not package names'
    variant = output['shipAs']
    if output['patch'] != patch_name(variant): return f'its patch must be {patch_name(variant)}'
    if variant not in candidates(convert(name)): return f'{variant} is not a name the project name gives'
    if is_device(variant): return 'a name Windows keeps for a device'
    return taken(derived(variant, streams))


def find_ci(folder, name):
    """The entry of `folder` called `name` regardless of case (Windows' way, on any file system), or None."""
    try:
        for entry in Path(folder).iterdir():
            if entry.name.lower() == name.lower(): return entry
    except (FileNotFoundError, NotADirectoryError):
        pass
    return None


def base_streams(game, base):
    """The streams the base map's records load in the install `game` (its intros and its other streams, in order),
    from its DefaultMaps.ini as the install has it (the editor's lines taken out). [] for a map with no record."""
    import installs
    import maplist
    import mapsini
    text = installs.maps_text(game)
    found = []
    for record in maplist.records(text):
        if (mapsini.field(record, 'Name') or '').lower() != base.lower(): continue
        found += mapsini.slot_streams(record)
    return list(dict.fromkeys(found))


class Claims:
    """Who holds which names (the module's list), read once: `taken(names)` and `conflicts(names)` say which of
    `names` are held by anything but the project `project_id` (with proof it is its own)."""

    def __init__(self, projects=None, builds=None, games=(), project_id=None):
        """projects: the projects folder, or the server's ProjectStore, whose files are read only when they changed
        since its last look (review finding 20)."""
        self.project_id = project_id
        self.held = {}      # lower-case name -> [(what holds it, owner project id or None, soft)]
        self.notes = []     # what could not be looked at, in words (an install that is not set)
        if hasattr(projects, 'claimed'): self._store(projects)
        elif projects is not None: self._projects(Path(projects))
        if builds is not None: self._builds(Path(builds))
        for game in games:
            if game is not None: self._game(Path(game))

    def add(self, name, what, owner=None, soft=False):
        """`soft`: held by something whose owner nothing says but that may be a project's own earlier work (a file
        the editor installed under a ledger from before owners were noted, a lab deploy's record of a variant or a
        file a lab deploy put in): it
        keeps a new project from taking the name, and is left to the install step (installs.preflight) when a
        project builds."""
        if isinstance(name, str) and name:
            self.held.setdefault(name.lower(), []).append((what, owner, soft))

    def _projects(self, root):
        if not root.exists(): return
        try: paths = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == '.json')
        except OSError as error: raise NamesError(f'the projects folder {root} can\'t be read ({error})')
        for path in paths:
            try: document = json.loads(path.read_text(encoding='utf8'))
            except (OSError, ValueError): continue      # not a project file: nothing it holds
            if not isinstance(document, dict) or document.get('schema') != PROJECT_SCHEMA: continue
            owner = document.get('id') if isinstance(document.get('id'), str) and document.get('id') else None
            out = document.get('output')
            if not isinstance(out, dict): continue
            label = f'the project “{document.get("name") or path.stem}”'
            for key in ('shipAs', 'patch'):
                self.add(out.get(key), label, owner)
            if isinstance(out.get('shipAs'), str):
                self.add(cache_name(out['shipAs']), label, owner)

    def _store(self, store):
        """As _projects, from the store's cache of what each project file said (ProjectStore.claimed)."""
        try: claims = store.claimed()
        except OSError as error: raise NamesError(f'the projects folder {store.root} can\'t be read ({error})')
        for out, owner, name in claims:
            label = f'the project “{name}”'
            for key in ('shipAs', 'patch'):
                self.add(out.get(key), label, owner)
            if isinstance(out.get('shipAs'), str):
                self.add(cache_name(out['shipAs']), label, owner)

    def _builds(self, root):
        if not root.exists(): return
        try: folders = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.'))
        except OSError as error: raise NamesError(f'the builds folder {root} can\'t be read ({error})')
        for folder in folders:
            m = read_manifest(folder)
            if m is None:
                self.add(folder.name, f'the folder {folder.name} in the builds folder (not a build)')
                continue
            owner = (m.get('project') or {}).get('id') or None
            label = f'the build {folder.name} of “{(m.get("project") or {}).get("name") or "a project"}”'
            for name in build_names(m, folder.name):
                self.add(name, label, owner)

    def _game(self, game):
        import installs
        cooked = installs.cooked(game)
        try:
            files = sorted(p.name for p in cooked.iterdir()) if cooked.is_dir() else []
            ledger = installs.read_ledger(game)
            text = installs.maps_text(game) if installs.config(game, 'DefaultMaps.ini').is_file() else ''
        except (OSError, ValueError, installs.InstallError) as error:
            raise NamesError(f'the game install {game} can\'t be read ({error})')
        owners = installs.file_owners(ledger)
        noted = installs.noted_files(ledger)
        lab = installs.lab_deploys(game)
        for name in files:
            if name.startswith('.'): continue
            stem = name.rsplit('.', 1)[0]
            if name.lower() in noted:
                owner = owners.get(name.lower())
                self.add(stem, f'{name}, installed by the editor in {game.name}', owner, soft=owner is None)
            elif name.lower() in lab:
                # an earlier test of a project, put there by the lab's deploy tools (by name here: the install step
                # checks its bytes before it replaces it)
                self.add(stem, f'{name}, put in {game.name} by the lab\'s deploy tools', soft=True)
            else:
                self.add(stem, f'{name} in {game.name}\'s CookedPCConsole')
        for variant, owner in installs.recorded_variants(ledger).items():
            self.add(variant, f'{variant}, installed by the editor in {game.name}', owner)
        import maplist
        import mapsini
        lines = text.splitlines()
        for k, line in enumerate(lines):
            # live records, and commented-out ones (they name a map too)
            off = maplist.COMMENTED.match(line)
            record = off.group(1) if off else line.strip() if line.lstrip().startswith('Maps=(') else None
            if record is None: continue
            name = mapsini.field(record, 'Name')
            # a record of the lab's patchtool deploy (installs.patchtool_record): an earlier test of a project
            lab = bool(name and not off) and installs.patchtool_record(
                [l.encode('latin-1', 'replace') for l in lines[max(0, k - 1):k + 1]], name) is not None
            self.add(name, f'a map record of {game.name}\'s DefaultMaps.ini', soft=lab)
            for stream in mapsini.slot_streams(record):
                self.add(stream, f'a stream in {game.name}\'s DefaultMaps.ini')

    def holders(self, name):
        """What holds `name` other than the project itself, in words."""
        return [what for what, owner, soft in self.held.get(name.lower(), [])
                if not (self.project_id and (owner == self.project_id or soft))]

    def conflicts(self, names):
        """[(name, what holds it)] for each of `names` held by something else."""
        return [(n, what) for n in dict.fromkeys(names) for what in self.holders(n)[:1]]

    def taken(self, names):
        """Why the first of `names` that something else holds is taken (a phrase), or None."""
        found = self.conflicts(names)
        return None if not found else (f'{found[0][1]} holds it' if found[0][0].lower() == names[0].lower()
                                       else f'{found[0][1]} holds {found[0][0]}')


def read_manifest(folder):
    """A build folder's manifest (a dict of the variant-package schema), or None."""
    try: m = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    return m if isinstance(m, dict) and m.get('schema') == BUILD_SCHEMA else None


def build_names(m, folder=None):
    """Every name a build holds: its folder, variant, patch, cache, files (without their extensions) and the copies it
    streams in place of others."""
    names = [folder, m.get('variant'), m.get('patch'), m.get('cache')]
    names += [Path(f).name.rsplit('.', 1)[0] for f in m.get('files') or {} if isinstance(f, str)]
    names += [c for c in (m.get('replaceStreams') or {}).values() if isinstance(c, str)]
    names += [s.get('copy') for s in m.get('streamCopies') or [] if isinstance(s, dict)]
    names += [s.get('copy') for s in m.get('intros') or [] if isinstance(s, dict)]
    return [n for n in dict.fromkeys(names) if isinstance(n, str) and n]


class Service:
    """The server's names: the Save dialog's preview (POST /projects/output-names) and the store's check of a new
    project's names as it saves (ProjectStore.check_output, inside the store's lock). One server process: two servers
    writing one projects folder are not kept apart here; the Build and the installs check again."""

    def __init__(self, store, builds, games):
        """store: the ProjectStore; builds: the builds folder; games(): [(game folder or None, what it is)], the install
        the editor reads and the one it plays in."""
        self.store, self.builds, self.games = store, Path(builds) if builds else None, games

    def _folders(self):
        found, notes = [], []
        for folder, what in self.games():
            if folder is None:
                notes.append(f'{what} is not set, so the names are not checked against it yet')
            elif all(not same(folder, f) for f in found):
                found.append(Path(folder))
        return found, notes

    def claims(self, project_id=None):
        games, notes = self._folders()
        try:
            claims = Claims(self.store, self.builds, games, project_id)
        except NamesError as error:
            raise ProjectError(503, f'The map name can\'t be worked out: {error}.')
        claims.notes = notes
        return claims, games

    def streams(self, games, base):
        for game in games:
            try: return base_streams(game, base)
            except (OSError, ValueError): continue
        return list(INTROS)     # no install to read: every intro a build could copy

    def preview(self, name, base, target=None):
        """What the Save dialog shows for saving under `name`: a new project's names (fresh), or those of the project
        `target` (the open project or the one replaced: fixed). {name, fresh, output, reason, limit, notes,
        conflicts}."""
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ProjectError(422, 'A project needs a name of 1 to 120 characters.')
        if not isinstance(base, str) or not PACKAGE.fullmatch(base):
            raise ProjectError(422, 'Say which map the project is of.')
        if target is not None:
            document = self.store.load(self.store.check_id(target))
            output = document.get('output')
            claims, games = self.claims(target)
            clash = claims.conflicts(derived(output['shipAs'], self.streams(games, base))) if valid_output(output) else []
            return dict(name=name, fresh=False, output=output if valid_output(output) else None, reason=None,
                        limit=LIMIT, notes=claims.notes,
                        conflicts=[f'{n}: {what}' for n, what in clash])
        claims, games = self.claims()
        try: output = allocate(name, claims.taken, self.streams(games, base))
        except NamesError as error: raise ProjectError(409, f'No map name is free: {error}.')
        reason = output.pop('reason')
        return dict(name=name, fresh=True, output=output, reason=reason, limit=LIMIT, notes=claims.notes, conflicts=[])

    def check_new(self, document):
        """A new project's names as it saves (the store's lock held): refused (409, with the names it would get now
        as `proposal`) unless they are names the project's name gives that are free."""
        output, name = document.get('output'), document.get('name')
        base = (document.get('source') or {}).get('map')
        if output is None:
            raise ProjectError(422, 'A new project needs its map name: reload the page and save again.')
        claims, games = self.claims()
        streams = self.streams(games, base) if isinstance(base, str) else list(INTROS)
        why = accepts(name, output, claims.taken, streams)
        if why is None: return
        try: proposal = allocate(name, claims.taken, streams)
        except NamesError as error: raise ProjectError(409, f'No map name is free: {error}.')
        reason = proposal.pop('reason')
        shown = output.get('shipAs') if isinstance(output, dict) else None
        raise ProjectError(409, f'The map name {shown} can\'t be used ({why}); it would build as {proposal["shipAs"]}. '
                                f'Save again to use that.', proposal=dict(output=proposal, reason=reason, limit=LIMIT))


def same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
