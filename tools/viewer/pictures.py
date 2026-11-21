"""A project's map picture: the 512 x 256 picture the Build writes into the map as its `MapPicture` (LWR map packs
plan, 4.2 and 4.3; tools/bake/map_frame.py writes it).

Kept on this computer with the project's other state, by project id:

    <projects>\\.workshop\\<id>\\picture.png         the picture, a clean opaque 512 x 256 PNG
    <projects>\\.workshop\\<id>\\picture.prev.png    the one before it (or the one removed), kept by every change

The project's document names its picture by the file's SHA-256 (`picture: {sha256}`), written by an ordinary save:
the picture is part of the project's revision. A change of the picture that is never saved leaves the saved revision
its own picture, in `picture.prev.png`: `picture_file` gives whichever of the two the document names.

A project file sent to someone else has its picture beside it as `<project file's name without .json>.picture.png`
(`beside`). Reading never changes a file (review finding 45): `picture_file` finds the picture there while it lies
beside the project's file, and the project's next save takes it in (`adopt_beside`: kept here byte for byte, the file
beside it deleted), so a rename keeps it.

Save as copies the picture the document names to the new project inside the save itself (`copy_picture`, review
finding 8), byte for byte, so the new document never names a picture its project doesn't keep.

Only the cropped picture is kept: the browser crops and scales (web/map_picture.js), the server takes nothing but an
opaque 512 x 256 PNG of up to 1 MB and writes it again from its pixels.
"""
import hashlib
import io
import os
from pathlib import Path
import sys

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402
from projects import ID, SHA256, STATE, ProjectError, hide

HERE = Path(__file__).resolve().parent
NAME, PREVIOUS = 'picture.png', 'picture.prev.png'
BESIDE = '.picture.png'
WIDTH, HEIGHT = 512, 256
MAX_BYTES = 1 << 20
PNG = b'\x89PNG\r\n\x1a\n'


def _root(projects):
    """The projects folder: a path, or a ProjectStore."""
    return Path(projects) if isinstance(projects, (str, os.PathLike)) else Path(projects.root)


def _folder(projects, project_id):
    if not isinstance(project_id, str) or not ID.fullmatch(project_id):
        raise ProjectError(404, 'No such project.')
    return _root(projects) / STATE / project_id


def sha256(data):
    return hashlib.sha256(data).hexdigest()


_HASHES = {}        # file -> (size, modified time, SHA-256): a kept picture hashed once while unchanged (review finding 50)


def file_sha256(path):
    """The SHA-256 of the file at `path`, from _HASHES while its size and modified time are the same."""
    path = Path(path)
    stat = path.stat()
    known = _HASHES.get(str(path))
    if known and known[:2] == (stat.st_size, stat.st_mtime_ns):
        return known[2]
    digest = sha256(path.read_bytes())
    _HASHES[str(path)] = (stat.st_size, stat.st_mtime_ns, digest)
    return digest


def named(document):
    """The SHA-256 of the picture a project's document names, or None (none, or a malformed record)."""
    picture = document.get('picture') if isinstance(document, dict) else None
    value = picture.get('sha256') if isinstance(picture, dict) else None
    return value if isinstance(value, str) and SHA256.fullmatch(value) else None


def _opened(data):
    """The picture `data` is, as a Pillow RGB image: an opaque 512 x 256 PNG of up to MAX_BYTES, else a ProjectError."""
    from PIL import Image
    if len(data) > MAX_BYTES:
        raise ProjectError(413, 'A map picture is a PNG of up to 1 MB.')
    if not data.startswith(PNG):
        raise ProjectError(422, 'A map picture is a PNG.')
    try:
        with Image.open(io.BytesIO(data), formats=['PNG']) as image:
            if image.size != (WIDTH, HEIGHT):
                raise ProjectError(422, 'A map picture is %d x %d; this one is %d x %d.' % ((WIDTH, HEIGHT) + image.size))
            image.load()
            rgba = image.convert('RGBA')
    except ProjectError:
        raise
    except Exception as error:      # Pillow raises many kinds for a file it can't read
        raise ProjectError(422, 'The picture could not be read: %s' % error)
    if rgba.getchannel('A').getextrema()[0] < 255:
        raise ProjectError(422, 'A map picture has no transparent parts.')
    return rgba.convert('RGB')


def clean(data):
    """`data` (an opaque 512 x 256 PNG) written again from its pixels alone: no text, no colour profile, no times."""
    image = _opened(data)
    out = io.BytesIO()
    image.save(out, 'PNG', optimize=False, compress_level=6)
    return out.getvalue()


def _replace(path, data):
    temp = path.with_name(path.name + '.tmp')
    with open(temp, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _state_folder(projects, project_id):
    folder = _folder(projects, project_id)
    if not folder.parent.is_dir():
        folder.parent.mkdir(parents=True, exist_ok=True)
        hide(folder.parent)
    folder.mkdir(exist_ok=True)
    return folder


def _keep_previous(folder, saved=None):
    """The current picture becomes the one before it, unless that would lose the picture the saved revision names
    (`saved`, its SHA-256): a current picture that was never saved is dropped instead."""
    current, previous = folder / NAME, folder / PREVIOUS
    if not current.is_file():
        return
    if saved and file_sha256(current) != saved and previous.is_file() and file_sha256(previous) == saved:
        current.unlink()
    else:
        os.replace(current, previous)


def save_picture(projects, project_id, data, saved=None):
    """Keeps `data` (a PNG the page sent) as the project's picture, written again clean: dict(sha256), the kept
    file's. The picture before it stays as picture.prev.png; `saved` is the SHA-256 the project's saved revision
    names, whose file is never the one lost."""
    data = clean(data)
    digest = sha256(data)
    folder = _state_folder(projects, project_id)
    current = folder / NAME
    if current.is_file() and file_sha256(current) == digest:
        return dict(sha256=digest)
    _keep_previous(folder, saved)
    _replace(current, data)
    return dict(sha256=digest)


def copy_picture(projects, from_id, to_id, sha256_, saved=None):
    """The kept picture of project `from_id` with that SHA-256 (`picture_file`: its current one, the one before, or one
    lying beside its file) kept as project `to_id`'s current picture as well, byte for byte, so its SHA-256 stays the
    one the document names (Save as: review finding 8). The one `to_id` had is kept for its saved revision (`saved`,
    the SHA-256 that names), as save_picture keeps it. True, or False when `from_id` keeps no picture with that
    SHA-256; an error copying (OSError) is the caller's."""
    source = picture_file(projects, from_id, sha256_)
    if source is None:
        return False
    data = source.read_bytes()
    if sha256(data) != sha256_:
        return False
    folder = _state_folder(projects, to_id)
    current = folder / NAME
    if current.is_file() and file_sha256(current) == sha256_:
        return True
    _keep_previous(folder, saved)
    _replace(current, data)
    return True


def remove_picture(projects, project_id, saved=None):
    """Takes the project's picture away (kept as picture.prev.png, for the saved revision that still names it):
    dict(removed)."""
    folder = _folder(projects, project_id)
    had = (folder / NAME).is_file()
    if had:
        _keep_previous(folder, saved)
    return dict(removed=had)


def picture_file(projects, project_id, sha256_=None):
    """The project's kept picture file, or None. `projects` is the projects folder (or a ProjectStore). With
    `sha256_` (the one the project's document names: `named(document)`), the kept file with that SHA-256, the
    current one or the one before it, else the file lying beside the project's file when it is that picture (one sent
    with the project, until its next save takes it in), or None; without, the current one. Nothing is written."""
    try:
        folder = _folder(projects, project_id)
    except ProjectError:
        return None
    for name in (NAME, PREVIOUS) if sha256_ else (NAME,):
        path = folder / name
        try:
            if path.is_file() and (not sha256_ or file_sha256(path) == sha256_):
                return path
        except OSError:
            continue
    if sha256_:
        path = _beside_file(projects, project_id)
        try:
            if path is not None and path.is_file() and path.stat().st_size <= MAX_BYTES and file_sha256(path) == sha256_:
                return path
        except OSError:
            pass
    return None


def _beside_file(projects, project_id):
    """Where a picture sent with the project's file lies (`beside`), or None when the project's file isn't found."""
    from projects import ProjectStore
    store = projects if isinstance(projects, ProjectStore) else ProjectStore(_root(projects))
    try:
        path = store._find(project_id)
    except ProjectError:
        return None
    return beside(path) if path is not None else None


def project_picture(projects, document):
    """The picture file a project's document names (`picture_file` with its id and SHA-256), or None: no picture, or
    its file is not on this computer."""
    digest = named(document)
    return picture_file(projects, document.get('id'), digest) if digest else None


def beside(project_path):
    """Where a project file's picture lies when the two are sent together: `Bar remix.json` has
    `Bar remix.picture.png`."""
    project_path = Path(project_path)
    return project_path.with_name(project_path.stem + BESIDE)


def adopt_picture(projects, project_id, source_path, sha256_=None, remove=True):
    """Takes the picture file `source_path` (one lying beside a project file put into the projects folder) in as the
    project's kept picture, when it is a map picture and, with `sha256_` (the one the project names), its SHA-256 is
    that one. The file is kept byte for byte, so its SHA-256 stays the project's; `remove` then deletes the source.
    Returns True when the project's picture is now that file, False when the file was left alone."""
    source_path = Path(source_path)
    try:
        if not source_path.is_file() or source_path.stat().st_size > MAX_BYTES:
            return False
        data = source_path.read_bytes()
    except OSError:
        return False
    digest = sha256(data)
    if sha256_ and digest != sha256_:
        return False
    try:
        _opened(data)
    except ProjectError:
        return False
    try:
        folder = _state_folder(projects, project_id)
        current = folder / NAME
        if not (current.is_file() and file_sha256(current) == digest):
            _keep_previous(folder)
            _replace(current, data)
        if remove:
            source_path.unlink(missing_ok=True)
    except (OSError, ProjectError):
        return False
    return True


def adopt_beside(projects, project_path, document):
    """`adopt_picture` for a project as it is saved (ProjectStore.save; never as it is read: review finding 45): when
    its document names a picture this computer does not keep and the file `beside(project_path)` is it, that file is
    taken in. Returns True when it was."""
    digest = named(document)
    if not digest:
        return False
    found = picture_file(projects, document.get('id'), digest)
    if found is not None and found.parent == _folder(projects, document.get('id')):
        return False
    return adopt_picture(projects, document.get('id'), beside(project_path), digest)


def game_png(path):
    """The picture file as the game will show it: through DXT1 and back, a PNG's bytes (the dialog's preview)."""
    from PIL import Image
    map_frame = _map_frame()
    with Image.open(path) as image:
        shown = map_frame.decode(map_frame.encode(image))
    out = io.BytesIO()
    shown.save(out, 'PNG')
    return out.getvalue()


def shown_png(data):
    """A cropped picture the page sent (an opaque 512 x 256 PNG) as the game will show it, a PNG's bytes; nothing is
    kept."""
    map_frame = _map_frame()
    shown = map_frame.decode(map_frame.encode(_opened(data)))
    out = io.BytesIO()
    shown.save(out, 'PNG')
    return out.getvalue()


def _map_frame():
    paths.use('bake')
    import map_frame
    return map_frame


# ---------------------------------------------------------------- the base map's picture, from the game
_BASE = {}      # cooked folder -> ({map name, lower case: (package file, export index, library)}, the files' times)


def _base_index(cooked):
    """Every picture of the game's map-image packages in `cooked` (the install's CookedPCConsole), by the map name it
    is called after, read once and again when a package file changes. A package that can't be read or is damaged is
    skipped: the readers refuse it with an OSError or a ValueError (KB-9), and the other packages' pictures are
    listed."""
    from package import Package
    map_frame = _map_frame()
    cooked = Path(cooked)
    files = [(library, cooked / (library + '_SF.upk')) for library in map_frame.LIBRARIES]
    stamp = tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for _, f in files if f.is_file())
    cached = _BASE.get(str(cooked))
    if cached and cached[1] == stamp:
        return cached[0]
    index = {}
    for library, path in files:
        if not path.is_file():
            continue
        try:
            p = Package(path)
            for k in range(1, len(p.exports) + 1):
                if p.cls(k) == 'Texture2D':
                    index.setdefault(p.name(k).rsplit('.', 1)[-1].lower(), (path, k, library))
        except (OSError, ValueError):
            continue
    _BASE[str(cooked)] = (index, stamp)
    return index


def base_library(cooked, map_name):
    """The game's map-image package that has a picture called after the map (`UILibrary_MapImages`, or `_DLC1`,
    `_DLC2`, `_HQAssault`), or None: the game shows no picture for the map."""
    if not cooked or not map_name:
        return None
    try:
        found = _base_index(cooked).get(str(map_name).lower())
    except OSError:
        return None
    return found[2] if found else None


def base_png(cooked, map_name):
    """The game's own picture of the map, a PNG's bytes, or None when the game has none."""
    import tempfile
    from package import FormatError, Package
    import texture
    if not cooked or not map_name:
        return None
    found = _base_index(cooked).get(str(map_name).lower())
    if not found:
        return None
    path, index, _ = found
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / 'picture.png'
        try:
            texture.export_texture(Package(path), index, out)
        except (OSError, ValueError, FormatError):
            return None
        return out.read_bytes()


def status(projects, document, cooked=None):
    """Whose picture a project's map shows: 'own' (the project's, kept here), 'base' (the base map's, which the game
    has) or 'none'."""
    if project_picture(projects, document) is not None:
        return 'own'
    source = document.get('source') if isinstance(document, dict) else None
    return 'base' if base_library(cooked, (source or {}).get('map')) else 'none'
