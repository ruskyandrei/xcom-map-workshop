"""Local original-map viewer. Run with --help for export and serve commands."""
import argparse
import errno
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import socket
import sys
import traceback
import webbrowser
from urllib.parse import parse_qs, unquote, urlsplit
from export import export_map, stream_package, EXPORT_VERSION
from catalogue import PackageDigests, load_catalogue, public_catalogue, with_install
from projects import ProjectError, ProjectStore, draft_query
from prefabs import MAX_PICTURE, PrefabStore
from prefab_tests import PrefabTests
from builds import BuildRunner
from buildqueue import BuildQueue
from exports import ExportRunner
from play import Player
from gamesetup import GameSetup
from families import FamilyCache
from collision import CollisionCache
from audio import OggError, WaveCache, byte_range
from generated import GeneratedError, Meshes as GeneratedMeshes
import looks as made_looks
from library import LibraryRunner, pieces_root
from precache import PrecacheRunner
import guide
import gamemaps
import manager
import pictures
from maplist import lwr_maps
from settings import KEYS, doctor, load_settings, resolve_game, save_settings, settings_path

WEB = Path(__file__).resolve().parent / "web"


class Live:
    """What the server serves that choosing another game install replaces (gamesetup.py): the map list with the
    install's maps, their exporter, and the player (Play in game: its settings)."""

    def __init__(self, catalogue, exports=None, player=None, library=None):
        self.catalogue, self.exports, self.player, self.library = catalogue, exports, player, library


MAIN_PORT = 8768     # the main viewer/editor server (AGENTS.md): the one that prunes old exports (prune.py)


def install_catalogue(catalogue, cache_root, settings, prune=False):
    """The exported maps' catalogue with every map the game install plays (export on first open), and the exporter
    for them: (catalogue, exports or None). `prune`: the exporter deletes a map's older generations once it has
    switched the map to a new one (the main server's)."""
    if settings['game'] is None: return catalogue, None
    game, note = resolve_game(settings['game'])
    if game is None:
        print(f"Only exported maps are listed: {note}", flush=True)
        return catalogue, None
    try:
        # each exported map serves its export of the install's own file of it (review finding 18)
        from maplist import package_of
        digests = PackageDigests(cache_root)
        def digest(name):
            path = package_of(game, name)
            try: return digests.digest(path) if path else None
            except OSError: return None
        catalogue = with_install(catalogue, lwr_maps(game), digest)
        digests.save()
        return catalogue, ExportRunner(catalogue, cache_root, settings['game'], prune=prune, digests=digests)
    except (OSError, ValueError) as error:
        print(f"Only exported maps are listed: {error}", flush=True)
        return catalogue, None


def install_busy(live, precache):
    """Another install is chosen only when nothing works on this one (review finding 48; the build queue has its own
    guard): a map export, a library scan or the cache job would go on into the old install's catalogue, beside a new
    runner that allows a second at once. ProjectError 409 saying what runs."""
    busy = []
    exporting = live.exports.running() if live.exports else None
    if exporting: busy.append(f'{exporting} is being prepared')
    if live.library and live.library.running(): busy.append('the library of pieces is being read')
    if precache and precache.running(): busy.append('Cache everything is running')
    if busy:
        said = '; '.join(busy)
        raise ProjectError(409, f'{said[:1].upper() + said[1:]}: wait for it, or cancel it, before choosing another game '
                                'install.', code='install-busy')


def landing_lines(map_id):
    """The game install's landing-zone lines for a map (DefaultLZMutator.ini; tools/viewer/spawns.py): dict(kind: the
    install's kind (settings.game_kind), file, lines: [zone without an id, in order]). A plain install, or none set,
    has no lines."""
    import spawns
    from settings import game_kind
    try:
        game, _ = resolve_game(load_settings()['game']) if load_settings().get('game') else (None, None)
    except (OSError, ValueError):
        game = None
    if game is None:
        return dict(kind=None, file=None, lines=[])
    ini = Path(game) / 'XEW' / 'XComGame' / 'Config' / 'DefaultLZMutator.ini'
    if not ini.is_file():
        return dict(kind=game_kind(game), file=None, lines=[])
    zones = spawns.map_lines(ini.read_text(encoding='latin-1'), map_id)
    return dict(kind=game_kind(game), file=str(ini), lines=[z for z in zones if not z.get('verbatim')])


def spawn_rules(map_id):
    """What the game install does with the map's spawn points (spawnrules.rules; editor spawns implementation plan,
    SP2): read each time, as landing_lines is, with `excluded` (whether the install's ExcludeMaps names the map)."""
    import spawnrules
    try:
        game, _ = resolve_game(load_settings()['game']) if load_settings().get('game') else (None, None)
    except (OSError, ValueError):
        game = None
    try:
        found = spawnrules.rules(game)
    except (OSError, ValueError) as error:
        found = dict(spawnrules.rules(None), error=str(error))
    return dict(found, map=map_id, excluded=spawnrules.excluded(found, map_id))


def contained(root, rel):
    """The path `rel` names under the folder `root` (absolute), or root/.denied, worked out from the text alone: a part
    that is absolute, names a drive or a network share, starts with a slash or backslash, or holds a colon or a NUL is
    refused before anything is joined, and the joined path is compared with the root without being resolved (resolving
    opens the path first: a network one would be reached; review finding 45)."""
    root = str(root)
    denied = os.path.join(root, '.denied')
    if rel and (rel[0] in '/\\' or ':' in rel or '\x00' in rel or PureWindowsPath(rel).drive
                or PureWindowsPath(rel).is_absolute() or PurePosixPath(rel).is_absolute()):
        return denied
    target = os.path.normpath(os.path.join(root, rel)) if rel else os.path.normpath(root)
    base = os.path.normcase(os.path.normpath(root))
    try:
        inside = os.path.commonpath([os.path.normcase(target), base]) == base
    except ValueError:
        inside = False
    return target if inside else denied


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Windows SO_REUSEADDR can let a second process bind the same port.
        # Fail clearly instead of serving requests from an obsolete generation.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(SimpleHTTPRequestHandler):
    # Reuse browser connections while loading hundreds of mesh/texture files.
    # HTTP/1.0 closed a socket per asset and could exhaust Windows buffers across reloads.
    protocol_version = 'HTTP/1.1'
    # Python's MIME guesses read the Windows registry, which can map .js to text/plain;
    # browsers refuse module scripts served that way. Fix the types the viewer serves.
    extensions_map = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                      ".json": "application/json", ".glb": "model/gltf-binary", ".png": "image/png"}
    # each map's families and assemblies (families.py), worked out once per server
    family_cache = FamilyCache()
    # each map's line-check collision by mesh (collision.py), its package read once per server
    collision_cache = CollisionCache()
    # each wave the Effects view previews (audio.py), read from its package once and kept within a bound
    wave_cache = WaveCache()
    # the meshes of pieces the Build makes from numbers (generated.py), kept by their numbers
    generated_meshes = GeneratedMeshes()

    def __init__(self, *args, catalogue=None, projects=None, builds=None, exports=None, player=None, live=None,
                 setup=None, library=None, prefabs=None, prefab_tests=None, precache=None, queue=None, **kwargs):
        # what a change of the game install replaces (gamesetup.py) is read from `live` on each request, since a
        # kept-alive connection outlives it
        self.live = live or Live(catalogue, exports, player, library)
        self.projects = projects
        self.prefabs = prefabs
        self.prefab_tests = prefab_tests
        self.precache = precache
        self.builds = builds
        self.queue = queue
        self.game_setup = setup
        super().__init__(*args, directory=str(WEB), **kwargs)

    catalogue = property(lambda self: self.live.catalogue)
    library = property(lambda self: self.live.library)
    exports = property(lambda self: self.live.exports)
    player = property(lambda self: self.live.player)
    squads = property(lambda self: getattr(self.live.player, 'squads', None))

    @property
    def scene_root(self):
        default = self.catalogue['maps'].get(self.catalogue['defaultMap']) if self.catalogue['defaultMap'] else None
        return default['root'] if default and default.get('root') else None

    def send_json(self, status, value, body=True, store=True):
        payload = json.dumps(value).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        if not store: self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if body: self.wfile.write(payload)

    # Projects (by id; projects.py finds each one's file): GET /projects.json lists them; /projects/<id>/project.json (GET, PUT {expectedRevision, document})
    # and /projects/<id>/recovery.json (GET: the kept state or null; PUT; DELETE). Changes are accepted only from the viewer's own page.
    # Builds (builds.py): POST /projects/<id>/build builds the saved project ({"quick": true}: without baking its
    # lighting); GET /projects/<id>/build.json follows it; POST /builds/reveal {path} shows a builds-folder path in
    # Explorer.
    def project_route(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if parts == ['projects.json']: return ('list', None)
        if parts == ['projects', 'output-names']: return ('names', None)
        if len(parts) == 3 and parts[0] == 'projects' and parts[2] in ('project.json', 'recovery.json', 'build.json'):
            return (parts[2].split('.')[0] + ('-status' if parts[2] == 'build.json' else ''), parts[1])
        if len(parts) == 3 and parts[0] == 'projects' and parts[2] in ('build', 'build-cancel', 'report'): return (parts[2], parts[1])
        if parts == ['builds', 'reveal']: return ('reveal', None)
        # the project's map picture (pictures.py), and the game's own picture of a map
        if len(parts) == 3 and parts[0] == 'projects' and parts[2] == 'picture.png': return ('picture', parts[1])
        if parts == ['projects', 'picture-preview']: return ('picture-preview', None)
        if len(parts) == 2 and parts[0] == 'map-pictures' and parts[1].endswith('.png'): return ('base-picture', unquote(parts[1][:-4]))
        return None

    def send_png(self, payload):
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def game_cooked(self):
        """The CookedPCConsole of the game install the editor reads, or None."""
        from settings import lwr_game
        try: game, _ = lwr_game(self.player.settings) if self.player is not None else (None, None)
        except (OSError, ValueError): game = None
        return None if game is None else game / 'XEW' / 'XComGame' / 'CookedPCConsole'

    def same_origin(self):
        # A page elsewhere (or a DNS-rebound name) must not reach these routes: the Host must be this server's
        # loopback address, and a browser's Origin, when sent, this server's own.
        host = self.headers.get('Host', '')
        port = self.server.server_port
        if host not in (f'127.0.0.1:{port}', f'localhost:{port}'): return False
        origin = self.headers.get('Origin')
        return origin is None or origin == f'http://{host}'

    def parse_request(self):
        """Every request's Host, and its Origin when sent, checked in one place before any route, reads too: a page
        elsewhere, or one that rebinds its name to 127.0.0.1, reads nothing (review finding 45)."""
        if not super().parse_request(): return False
        self.answered = False
        if self.same_origin(): return True
        self.body_read = False
        self.drain_body()
        self.send_json(403, dict(error=f'Only the editor\'s own page (http://127.0.0.1:{self.server.server_port}/) '
                                       'may use this server.'), body=self.command != 'HEAD')
        return False

    def send_response(self, *args, **kwargs):
        self.answered = True
        super().send_response(*args, **kwargs)

    def answer(self, method, route):
        """Run a request's route; any failure it doesn't answer itself is answered as a JSON 500 with its reason, never
        a dropped connection (review finding 46). The traceback goes to the server's window."""
        try:
            route()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True
        except Exception as error:      # noqa: BLE001 (whatever failed, the page is told why)
            traceback.print_exc()
            if getattr(self, 'answered', False):
                self.close_connection = True
                return
            try:
                self.send_json(500, dict(error=f'The editor\'s server could not do that: {error}' if str(error)
                                         else f'The editor\'s server could not do that ({type(error).__name__}).'),
                               body=method != 'HEAD')
            except OSError:
                self.close_connection = True

    def body_length(self, limit=32 << 20, too_large='Too large.'):
        """A request body's length from its Content-Length (none: 0): 400 when it is not a whole number of 0 or more,
        413 over `limit` (review finding 46: a bad value raised with no answer, a negative one held the thread)."""
        try: length = int(self.headers.get('Content-Length') or 0)
        except ValueError: raise ProjectError(400, 'Invalid Content-Length.')
        if length < 0: raise ProjectError(400, 'Invalid Content-Length.')
        if length > limit: raise ProjectError(413, too_large)
        return length

    def body_json(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ProjectError(415, 'Send JSON.')
        length = self.body_length()
        self.body_read = True
        try: return json.loads(self.rfile.read(length) or b'null')
        except ValueError: raise ProjectError(400, 'Malformed JSON.')

    def drain_body(self):
        """Read a body the route left unread (Build's POST, a refused change): on a kept-alive connection the next
        request would otherwise start with it ('{}GET ...', answered 501). One too large to read closes the
        connection instead."""
        if self.body_read: return
        try: length = int(self.headers.get('Content-Length') or 0)
        except ValueError: length = -1
        if length < 0 or length > 32 << 20: self.close_connection = True
        elif length: self.rfile.read(length)

    def handle_project(self, method):
        route = self.project_route()
        if route is None or self.projects is None: return False
        kind, project_id = route
        self.body_read = False
        try:
            if method != 'GET' and not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
            if kind == 'list' and method == 'GET':
                self.send_json(200, dict(folder=str(self.projects.root), projects=self.projects.list()))
            elif kind == 'names' and method == 'POST':
                # the Save dialog: the map name saving under {name} gives (a new project's, or the fixed one of the
                # project {target}, the open one or one replaced), for the map {map} (outputnames.Service.preview)
                request = self.body_json()
                if not isinstance(request, dict): raise ProjectError(400, 'Send {name, map, target}.')
                if self.projects.names is None: raise ProjectError(404, 'This server does not name projects.')
                self.send_json(200, self.projects.names.preview(request.get('name'), request.get('map'), request.get('target')))
            elif kind == 'project' and method == 'GET':
                # (a picture sent beside the project's file is found there, and taken in by its next save: a read
                # changes no file)
                self.send_json(200, self.projects.load(project_id))
            # The map picture (pictures.py): PUT /projects/<id>/picture.png keeps an opaque 512 x 256 PNG of up to
            # 1 MB, written again clean, and answers {sha256}; GET serves the kept one (?sha256=<hash>: the kept file
            # with that hash, the current one or the one before it; ?as=game: as the game shows it, after DXT1);
            # DELETE takes it away. GET /map-pictures/<map>.png is the game's own picture of a map (404: it has none).
            elif kind == 'picture' and method == 'PUT':
                length = self.body_length(pictures.MAX_BYTES, 'A map picture is a PNG of up to 1 MB.')
                if length <= 0: raise ProjectError(400, 'Send the picture.')
                saved = pictures.named(self.projects.load(project_id))
                self.body_read = True
                self.send_json(200, pictures.save_picture(self.projects, project_id, self.rfile.read(length), saved))
            elif kind == 'picture-preview' and method == 'POST':
                # a cropped picture as the game will show it (after DXT1), for the dialog; nothing is kept
                length = self.body_length(pictures.MAX_BYTES, 'A map picture is a PNG of up to 1 MB.')
                if length <= 0: raise ProjectError(400, 'Send the picture.')
                self.body_read = True
                self.send_png(pictures.shown_png(self.rfile.read(length)))
            elif kind == 'picture' and method == 'GET':
                query = parse_qs(urlsplit(self.path).query)
                wanted = (query.get('sha256') or [None])[0]
                path = pictures.picture_file(self.projects, self.projects.check_id(project_id), wanted)
                if path is None: raise ProjectError(404, 'No picture is kept for that project.')
                self.send_png(pictures.game_png(path) if query.get('as') == ['game'] else path.read_bytes())
            elif kind == 'picture' and method == 'DELETE':
                saved = pictures.named(self.projects.load(project_id))
                self.send_json(200, pictures.remove_picture(self.projects, project_id, saved))
            elif kind == 'base-picture' and method == 'GET':
                payload = pictures.base_png(self.game_cooked(), project_id)
                if payload is None: raise ProjectError(404, 'The game has no picture of that map.')
                self.send_png(payload)
            elif kind == 'project' and method == 'PUT':
                request = self.body_json()
                if not isinstance(request, dict): raise ProjectError(400, 'Send {expectedRevision, document}.')
                # owner: the page session saving (its draft for recovery goes); pictureFrom: Save as from that project,
                # whose map picture the document names (copied with the save)
                self.send_json(200, self.projects.save(project_id, request.get('document'), request.get('expectedRevision'),
                                                       owner=request.get('owner'), picture_from=request.get('pictureFrom')))
            elif kind == 'recovery' and method == 'GET':
                # null when nothing is kept: asking is routine, not an error.
                self.projects.load(project_id)
                self.send_json(200, self.projects.recovery(project_id))
            elif kind == 'recovery' and method == 'PUT':
                self.send_json(200, self.projects.save_recovery(project_id, self.body_json()))
            elif kind == 'recovery' and method == 'DELETE':
                # ?owner=<page session>[&savedAt=<the draft shown>]: that draft alone
                owner, saved_at = draft_query(parse_qs(urlsplit(self.path).query, keep_blank_values=True))
                self.send_json(200, self.projects.drop_recovery(project_id, owner, saved_at))
            elif kind in ('build', 'build-status', 'build-cancel', 'report', 'reveal') and self.builds is None:
                raise ProjectError(404, 'This server does not build.')
            elif kind == 'build' and method == 'POST':
                # {"quick": true}: a quick build (the edit without its lighting baked); no body or {}: a full one
                request = self.body_json() if self.body_length() else None
                self.send_json(202, self.builds.start(project_id, quick=isinstance(request, dict) and request.get('quick') is True))
            elif kind == 'build-status' and method == 'GET':
                self.send_json(200, self.builds.status(project_id))
            elif kind == 'build-cancel' and method == 'POST':
                # {"attempt": id}: only that launch (a stale page's cancel stops no newer build); none: the running one
                request = self.body_json() if self.body_length() else None
                attempt =request.get('attempt') if isinstance(request, dict) else None
                if attempt is not None and not (isinstance(attempt, str) and self.projects.check_id(attempt)):
                    raise ProjectError(400, 'Send {"attempt": the build\'s attempt id}.')
                self.send_json(200, self.builds.cancel(project_id, attempt))
            elif kind == 'report' and method == 'POST':
                self.send_json(200, self.builds.report(project_id))
            elif kind == 'reveal' and method == 'POST':
                request = self.body_json()
                self.send_json(200, self.builds.reveal(request.get('path') if isinstance(request, dict) else None))
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        finally:
            self.drain_body()
        return True

    # The prefab library (prefabs.py): GET /prefabs.json lists it; /prefabs/<id>/prefab.json (GET; PUT {expectedRevision,
    # document}; DELETE moves the file to a kept folder); /prefabs/<id>/picture.png (GET, PUT: the picture the page
    # draws); POST /prefabs/import {document, clash: null | "replace" | "copy"} takes a file from elsewhere.
    def handle_prefabs(self, method):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if parts[0] not in ('prefabs.json', 'prefabs'): return False
        self.body_read = False
        try:
            if self.prefabs is None: raise ProjectError(404, 'This server has no prefab library.')
            if method != 'GET' and not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
            if parts == ['prefabs.json'] and method == 'GET':
                self.send_json(200, dict(folder=str(self.prefabs.root), prefabs=self.prefabs.list()))
            elif parts == ['prefabs', 'import'] and method == 'POST':
                request = self.body_json()
                if not isinstance(request, dict): raise ProjectError(400, 'Send {document, clash}.')
                # (a replace names the revision it replaces: expectedRevision)
                self.send_json(200, self.prefabs.import_file(request.get('document'), request.get('clash'),
                                                             request.get('expectedRevision')))
            elif parts == ['prefabs', 'size'] and method == 'POST':
                from prefab_bounds import measure
                request = self.body_json()
                document = request.get('document') if isinstance(request, dict) else None
                self.prefabs.validate(document, document.get('id') if isinstance(document, dict) else None)
                self.send_json(200, measure(document, self.library))
            elif parts == ['prefabs', 'recover-sources'] and method == 'POST':
                request = self.body_json()
                document = request.get('document') if isinstance(request, dict) else None
                self.prefabs.validate(document, document.get('id') if isinstance(document, dict) else None)
                if self.library is None: raise ProjectError(409, 'The map catalogue is unavailable.')
                self.send_json(200, self.library.recover_prefab(document))
            elif len(parts) == 3 and parts[2] == 'recovery.json' and method == 'GET':
                self.send_json(200, self.prefabs.recovery(parts[1]))
            elif len(parts) == 3 and parts[2] == 'recovery.json' and method == 'PUT':
                self.send_json(200, self.prefabs.save_recovery(parts[1], self.body_json()))
            elif len(parts) == 3 and parts[2] == 'recovery.json' and method == 'DELETE':
                owner, saved_at = draft_query(parse_qs(urlsplit(self.path).query, keep_blank_values=True))
                self.send_json(200, self.prefabs.drop_recovery(parts[1], owner, saved_at))
            elif len(parts) == 3 and parts[2] == 'prefab.json' and method == 'GET':
                self.send_json(200, self.prefabs.load(parts[1]))
            elif len(parts) == 3 and parts[2] == 'prefab.json' and method == 'PUT':
                self.prefabs.check_id(parts[1])
                request = self.body_json()
                if not isinstance(request, dict): raise ProjectError(400, 'Send {expectedRevision, document}.')
                from prefab_bounds import require_supported
                document = request.get('document')
                self.prefabs.validate(document, parts[1])
                recipes = {}
                size = require_supported(document, self.library, recipes=recipes)
                for piece in document['pieces']:
                    if piece['actor'] in recipes:
                        piece['recipe'] = recipes[piece['actor']]
                if not document['pieces'] and not document.get('buildings'): raise ProjectError(422, 'A prefab is empty.')
                self.send_json(200, dict(self.prefabs.save(parts[1], document, request.get('expectedRevision'),
                                                           owner=request.get('owner')),
                                         size=size, recipes=recipes))
            elif len(parts) == 3 and parts[2] == 'prefab.json' and method == 'DELETE':
                self.send_json(200, self.prefabs.delete(parts[1]))
            elif len(parts) == 3 and parts[2] == 'picture.png' and method == 'PUT':
                length = self.body_length(MAX_PICTURE)
                self.body_read = True
                self.send_json(200, self.prefabs.save_picture(parts[1], self.rfile.read(length)))
            elif len(parts) == 3 and parts[2] == 'picture.png' and method == 'GET':
                path = self.prefabs.picture_path(parts[1])
                if not path.is_file(): raise ProjectError(404, 'No picture is kept for that prefab.')
                payload = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        except OSError as error:
            self.send_json(500, dict(error=f'The prefab library could not be read: {error}'))
        finally:
            self.drain_body()
        return True

    # Export on first open (exports.py): POST /maps/<id>/export exports a listed map not exported yet;
    # GET /maps/<id>/export.json follows it.
    def handle_prefab_tests(self, method):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if parts[0] != 'prefab-tests': return False
        self.body_read = False
        try:
            if self.prefab_tests is None:
                raise ProjectError(404, 'This server does not test prefabs.', code='test-unavailable')
            if method == 'POST' and not self.same_origin():
                raise ProjectError(403, 'Changes are only accepted from the viewer itself.', code='test-origin')
            if parts[1:] == ['check'] and method == 'POST':
                # what a test of this snapshot would say, nothing built (PrefabTests.check)
                request = self.body_json()
                snapshot = request.get('snapshot') if isinstance(request, dict) else None
                if not isinstance(snapshot, dict):
                    raise ProjectError(400, 'Send {snapshot}.', code='test-request')
                self.send_json(200, self.prefab_tests.check(snapshot))
            elif len(parts) == 1 and method == 'POST':
                self.send_json(202, self.prefab_tests.start(self.body_json()))
            elif len(parts) == 2 and parts[1].endswith('.json') and method == 'GET':
                self.send_json(200, self.prefab_tests.status(parts[1][:-5]))
            elif len(parts) == 3 and method == 'POST' and parts[2] in ('cancel', 'play'):
                request = self.body_json()
                if parts[2] == 'cancel' and request != {}:
                    raise ProjectError(400, 'Send an empty cancellation request.', code='test-request')
                action = self.prefab_tests.cancel(parts[1]) if parts[2] == 'cancel' else self.prefab_tests.play(parts[1], request)
                self.send_json(200, action)
            else:
                raise ProjectError(405, 'Not allowed.', code='test-route')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        except OSError as error:
            self.send_json(500, dict(error=str(error), code='test-storage'))
        finally:
            self.drain_body()
        return True

    def handle_map(self, method):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if len(parts) != 3 or parts[0] != 'maps' or parts[2] not in ('export', 'export.json'): return False
        self.body_read = False
        try:
            if self.exports is None: raise ProjectError(404, 'This server does not export maps.')
            if parts[2] == 'export' and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                request = self.body_json() if self.body_length() else None
                self.send_json(202, self.exports.start(parts[1], prepare=bool(isinstance(request, dict) and request.get('prepare'))))
            elif parts[2] == 'export.json' and method == 'GET':
                self.send_json(200, self.exports.status(parts[1]))
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        finally:
            self.drain_body()
        return True

    # The families of pieces and a map's assemblies (families.py): GET /maps/<id>/families.json, for an exported map.
    def handle_families(self, method):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if parts == ['families.json']:
            from families import table, light_table
            if method != 'GET': self.send_json(405, dict(error='Not allowed.'))
            else: self.send_json(200, dict(table(), **{**light_table({}), 'exportProblem': None}, map=None, assemblies=[], helpers={}, landing=[]))
            return True
        if len(parts) == 3 and parts[0] == 'maps' and parts[2] == 'landing-lines.json':
            # the game install's LZArray lines for the map (Clear map plan, section 4): read each time, never exported
            if method != 'GET': self.send_json(405, dict(error='Not allowed.'))
            else: self.send_json(200, landing_lines(parts[1]))
            return True
        if len(parts) == 3 and parts[0] == 'maps' and parts[2] == 'spawn-rules.json':
            # the install's spawn mutators and their config (spawns plan SP2): read each time, never exported
            if method != 'GET': self.send_json(405, dict(error='Not allowed.'))
            else: self.send_json(200, spawn_rules(parts[1]))
            return True
        if len(parts) != 3 or parts[0] != 'maps' or parts[2] != 'families.json': return False
        entry = self.catalogue['maps'].get(parts[1])
        if method != 'GET': self.send_json(405, dict(error='Not allowed.'))
        elif not entry or entry.get('root') is None: self.send_json(404, dict(error='That map is not exported.'))
        else:
            try: self.send_json(200, self.family_cache.get(entry['root']))
            except (OSError, ValueError) as error: self.send_json(500, dict(error=f'Could not read the map: {error}'))
        return True

    # The game's collision for line checks by mesh (collision.py): GET /maps/<id>/collision.json, every mesh of the
    # map's own package, or ?mesh=<id>&mesh=<id> those; for an exported map, from its package in the install.
    def handle_collision(self, method):
        split = urlsplit(self.path)
        parts = split.path.strip('/').split('/')
        if len(parts) != 3 or parts[0] != 'maps' or parts[2] != 'collision.json': return False
        entry = self.catalogue['maps'].get(parts[1])
        if method != 'GET': self.send_json(405, dict(error='Not allowed.'))
        elif not entry or entry.get('root') is None: self.send_json(404, dict(error='That map is not exported.'))
        else:
            try:
                root = Path(entry['root'])
                scene = self.collision_cache.scene(root)        # (read once per export, not on every request)
                ids = parse_qs(split.query).get('mesh') or scene['meshes']
                find = (lambda: self.exports.package(parts[1])) if self.exports else (lambda: scene['source']['file'])
                self.send_json(200, dict(meshes=self.collision_cache.get(root, scene, find, ids)))
            except ProjectError as error: self.send_json(error.status, dict(error=error.message, **error.extra))
            except (OSError, ValueError, KeyError) as error: self.send_json(500, dict(error=f'Could not read the map\'s collision: {error}'))
        return True

    # A sound's wave for the Effects view's Wave preview (audio.py): GET or HEAD /maps/<id>/wave.ogg?id=<wave id>, the
    # id a key of the export's soundWaves ('<package>|<path>'). The Ogg stream is read from the package in the install
    # (the map's own only while it is the file the map was exported from), checked, kept, and answered with its length,
    # an ETag (If-None-Match: 304) and one byte range at a time (206; 416 outside it). An id the export doesn't list is
    # 404, a wave it can't serve 422 with why: one bad wave never fails the map.
    # GET or HEAD /library/wave.ogg?package=<map>&id=<wave id> is a wave of an effect or sound of another map (the Add
    # panel's All maps; library.effect_records lists the donor's waves), read from that map in the install as it was
    # when its records were made.
    def handle_wave(self, method):
        split = urlsplit(self.path)
        parts = split.path.strip('/').split('/')
        if parts == ['library', 'wave.ogg']: return self.library_wave(method, split)
        if len(parts) != 3 or parts[0] != 'maps' or parts[2] != 'wave.ogg': return False
        entry = self.catalogue['maps'].get(parts[1])
        wave_id = (parse_qs(split.query).get('id') or [''])[0]
        if method not in ('GET', 'HEAD'): self.send_json(405, dict(error='Not allowed.'))
        elif not entry or entry.get('root') is None: self.send_json(404, dict(error='That map is not exported.'), body=method == 'GET')
        else:
            try:
                root = Path(entry['root'])
                scene = self.wave_cache.scene(root)       # (read once per version of the file, not per wave)
                find = (lambda: self.exports.package(parts[1])) if self.exports else (lambda: scene['source']['file'])
                cooked = lambda: Path(find())
                data, etag, record = self.wave_cache.get(
                    root, scene, wave_id, find, lambda name: stream_package(cooked(), name))
            except KeyError: self.send_json(404, dict(error='That wave is not one of this map\'s.'), body=method == 'GET')
            except OggError as error: self.send_json(422, dict(error=f'The wave can\'t be played: {error}'), body=method == 'GET')
            except ProjectError as error: self.send_json(error.status, dict(error=error.message, **error.extra), body=method == 'GET')
            except (OSError, ValueError) as error: self.send_json(500, dict(error=f'Could not read the wave: {error}'), body=method == 'GET')
            else: self.send_wave(data, f'"{etag}"', method == 'GET')
        return True

    def library_wave(self, method, split):
        query = parse_qs(split.query)
        package, wave_id = (query.get('package') or [''])[0], (query.get('id') or [''])[0]
        if method not in ('GET', 'HEAD'): self.send_json(405, dict(error='Not allowed.'))
        elif self.library is None: self.send_json(404, dict(error='This server has no library.'), body=method == 'GET')
        else:
            try:
                path, scene = self.library.wave_scene(package)
                data, etag, _ = self.wave_cache.get('library:' + scene['name'], scene, wave_id, lambda: path, lambda name: None)
            except KeyError: self.send_json(404, dict(error=f'That wave is not one of {package}\'s.'), body=method == 'GET')
            except OggError as error: self.send_json(422, dict(error=f'The wave can\'t be played: {error}'), body=method == 'GET')
            except ProjectError as error: self.send_json(error.status, dict(error=error.message, **error.extra), body=method == 'GET')
            except (OSError, ValueError) as error: self.send_json(500, dict(error=f'Could not read the wave: {error}'), body=method == 'GET')
            else: self.send_wave(data, f'"{etag}"', method == 'GET')
        return True

    def send_wave(self, data, etag, body):
        if etag in [t.strip() for t in self.headers.get('If-None-Match', '').split(',')]:
            self.send_response(304)
            self.send_header('ETag', etag)
            self.end_headers()
            return
        span = byte_range(self.headers.get('Range'), len(data))
        if span is False:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{len(data)}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        start, end = span or (0, len(data) - 1)
        self.send_response(206 if span else 200)
        self.send_header('Content-Type', 'audio/ogg')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('ETag', etag)
        if span: self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        if body: self.wfile.write(data[start:end + 1])

    # The looks a made wall, slab or ground shape can take (custom geometry plan, M4: tools/bake/looks.py): GET
    # /looks/walls.json, /looks/slabs.json and /looks/ground.json list each kind's, with the numbers the page draws by.
    def handle_looks(self, method):
        kinds = {'/looks/walls.json': 'wall', '/looks/slabs.json': 'slab', '/looks/ground.json': 'ground'}
        path = urlsplit(self.path).path
        if path not in kinds: return False
        if method != 'GET':
            self.send_json(405, dict(error='Not allowed.'))
            return True
        self.send_json(200, made_looks.listing(kinds[path]))
        return True

    # Pieces the Build makes from numbers, drawn as it makes them (generated.py): GET /generated/fracwall.glb?wall=<the
    # wall's numbers as JSON> is a fracturing wall's mesh (an added copy's `generated`, kind fracWall), in slot order;
    # GET /generated/fracslab.glb?slab=<numbers> a floor or roof slab's (kind fracSlab); /generated/ground.glb?ground=
    # <numbers> a ground shape's (kind ground); GET /generated/ground-corners.json?ground=<a rock's numbers> its points
    # and which are its corners ({points, corners}: the editor's blue dots, look picker and rock points plan R2).
    def handle_generated(self, method):
        split = urlsplit(self.path)
        if split.path == '/generated/ground-corners.json' and method == 'GET':
            try:
                self.send_json(200, self.generated_meshes.ground_corners((parse_qs(split.query).get('ground') or [''])[0]))
            except (GeneratedError, ValueError) as error:
                self.send_json(400, dict(error=f"The rock's corners can't be read: {error}"))
            return True
        kinds = {'/generated/fracwall.glb': ('wall', 'fracwall'), '/generated/fracslab.glb': ('slab', 'fracslab'),
                 '/generated/ground.glb': ('ground', 'ground')}
        if split.path not in kinds: return False
        if method != 'GET':
            self.send_json(405, dict(error='Not allowed.'))
            return True
        what, maker = kinds[split.path]
        query = parse_qs(split.query)
        try:
            # (a made wall, floor or roof built broken: its blasts beside its numbers, custom geometry editing plan B5)
            more = ((query.get('blasts') or [''])[0],) if what != 'ground' else ()
            payload = getattr(self.generated_meshes, maker)((query.get(what) or [''])[0], *more)
        except (GeneratedError, ValueError) as error:
            self.send_json(400, dict(error=f"The {what} can't be drawn: {error}"))
            return True
        self.send_response(200)
        self.send_header('Content-Type', 'model/gltf-binary')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return True

    # Play in game (play.py): GET /play.json says which installs the editor works with and what it has installed
    # there; POST /play/start ({project} or {map}) starts the game on a map and POST /play/remove takes the editor's
    # installs back out.
    def handle_play(self, method):
        path = urlsplit(self.path).path
        if path not in ('/play.json', '/play/start', '/play/remove'): return False
        self.body_read = False
        try:
            if self.player is None: raise ProjectError(404, 'This server starts no game.')
            if path == '/play.json' and method == 'GET': self.send_json(200, self.player.status())
            elif path != '/play.json' and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                self.send_json(200, self.player.play(self.body_json()) if path == '/play/start' else self.player.remove())
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        finally:
            self.drain_body()
        return True

    # The test squad (squads.py, squadrecords.py): GET /squad.json is the saved squad (or the default) with what the
    # install Play in game uses offers and the squad checked there; PUT /squad.json {expectedRevision, document} saves
    # it; POST /squad/check {document} checks a draft, /squad/import {text} reads a shared file as a draft and
    # /squad/export {document} gives a shared file's name and text.
    def handle_squad(self, method):
        path = urlsplit(self.path).path
        if path not in ('/squad.json', '/squad/check', '/squad/import', '/squad/export'): return False
        self.body_read = False
        try:
            if self.squads is None: raise ProjectError(404, 'This server has no test squad.')
            if path == '/squad.json' and method == 'GET': self.send_json(200, self.squads.get())
            elif (path == '/squad.json' and method == 'PUT') or (path != '/squad.json' and method == 'POST'):
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                act = {'/squad.json': self.squads.save, '/squad/check': self.squads.check,
                       '/squad/import': self.squads.import_text, '/squad/export': self.squads.export}[path]
                self.send_json(200, act(self.body_json()))
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        except OSError as error:
            self.send_json(500, dict(error=f'The squad could not be saved: {error.strerror or error}'))
        finally:
            self.drain_body()
        return True

    # The project manager (manager.py): GET /manager.json lists every project with its last build and what is in the
    # game of it; POST /manager/install and /manager/pack act on {"projects": [id...], "mode": ...}.
    # GET /manager/packs.json lists the saved map packs (packs.py) and DELETE /manager/packs/<folder> forgets one.
    # The Game maps window (gamemaps.py): GET /gamemaps.json lists the install's map records and what the editor
    # changed of them; POST /gamemaps/use {records, use} switches the install's own records on or off and
    # POST /gamemaps/undo {variants} takes builds out.
    def handle_manager(self, method):
        path = urlsplit(self.path).path
        saved_pack = path[len('/manager/packs/'):] if path.startswith('/manager/packs/') else None
        if saved_pack is None and path not in ('/manager.json', '/manager/install', '/manager/pack', '/manager/packs.json',
                                               '/gamemaps.json', '/gamemaps/use', '/gamemaps/undo'): return False
        self.body_read = False
        try:
            if self.projects is None or self.builds is None: raise ProjectError(404, 'This server does not build.')
            if path.startswith('/gamemaps'):
                if path == '/gamemaps.json' and method == 'GET': self.send_json(200, gamemaps.listing(self.player))
                elif path != '/gamemaps.json' and method == 'POST':
                    if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                    self.send_json(200, (gamemaps.use if path == '/gamemaps/use' else gamemaps.undo)(self.player, self.body_json()))
                else: raise ProjectError(405, 'Not allowed.')
            elif path == '/manager.json' and method == 'GET':
                self.send_json(200, manager.listing(self.projects, self.builds, self.player))
            elif path == '/manager/packs.json' and method == 'GET':
                self.send_json(200, manager.pack_list(self.projects, self.builds))
            elif saved_pack is not None and method == 'DELETE':
                # DELETE /manager/packs/<folder>: the saved pack forgotten (its zips stay)
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                self.send_json(200, manager.pack_forget(self.projects, self.builds, unquote(saved_pack)))
            elif saved_pack is not None or path == '/manager/packs.json': raise ProjectError(405, 'Not allowed.')
            elif path != '/manager.json' and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                act = dict(install=manager.install, pack=manager.pack)[path.rsplit('/', 1)[1]]
                self.send_json(200, act(self.projects, self.builds, self.player, self.body_json()))
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        finally:
            self.drain_body()
        return True

    # The build queue (buildqueue.py): GET /manager/queue.json is the queue; POST /manager/queue adds projects and
    # /manager/queue/stop, /resume, /remove, /clear and /reset act on it, each with {queueId, expectedRevision,
    # requestId}. A server without a queue (none was made) answers 404.
    QUEUE_ROUTES = {'/manager/queue': 'add', '/manager/queue/stop': 'stop', '/manager/queue/resume': 'resume',
                    '/manager/queue/remove': 'remove', '/manager/queue/clear': 'clear', '/manager/queue/reset': 'reset'}

    def handle_queue(self, method):
        path = urlsplit(self.path).path
        if path != '/manager/queue.json' and path not in self.QUEUE_ROUTES: return False
        self.body_read = False
        try:
            if self.queue is None: raise ProjectError(404, 'This server has no build queue.', code='queue-unsupported')
            if path == '/manager/queue.json' and method == 'GET':
                self.send_json(200, self.queue.view(), store=False)
            elif path in self.QUEUE_ROUTES and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                status, answer = getattr(self.queue, self.QUEUE_ROUTES[path])(self.body_json())
                self.send_json(status, answer, store=False)
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra), store=False)
        except OSError as error:
            self.send_json(500, dict(error=f'The build queue could not be read or saved: {error}', code='queue-storage'), store=False)
        finally:
            self.drain_body()
        return True

    # The library of pieces across the game's maps (library.py): GET /library.json is the scan's state and, with
    # ?index=1, the index and the keys of the thumbnails kept; POST /library/scan starts a scan and GET /library/scan.json follows it;
    # GET /library/piece.json?package=&actor= is one piece as a template, exported on first request (its files under
    # /cache-library/); POST /library/pieces {sources: [{package, level, actor}]} exports many at once, each map opened
    # once (a prefab's first use), and answers {errors: [null or why]}; POST /library/pieces.json {sources} (at most 200)
    # answers the records themselves, {pieces: [{record} or {error}]}; GET and PUT /library/thumbs/<key>.png keep the thumbnails the page draws,
    # and /library/pictures/<key>.png the look picker's larger pictures (GET /library/pictures.json: their keys); GET and PUT
    # /library/state.json ({expectedRevision, document}) are the user's favourites and recently used pieces.
    # GET /library/effect.json?package=&actor= is one effect or ambient sound of another map as a template (library.effect:
    # its export 28 record, its particle system or waves), POST /library/effects.json {sources} (at most 200) many,
    # {effects: [{record} or {error}]} (a project's opening).
    def handle_library(self, method):
        split = urlsplit(self.path)
        parts = split.path.strip('/').split('/')
        if parts[0] not in ('library.json', 'library'): return False
        self.body_read = False
        try:
            if self.library is None: raise ProjectError(404, 'This server has no library.')
            if method != 'GET' and not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
            if parts == ['library.json'] and method == 'GET':
                status = self.library.status()
                if 'index=1' in split.query and status['ready']:
                    # the index is some megabytes: its bytes as kept, not parsed and written again
                    payload = (b'{"status":' + json.dumps(status).encode() + b',"thumbs":' + json.dumps(self.library.thumbs()).encode()
                               + b',"index":' + self.library.index()[1] + b'}')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                else: self.send_json(200, dict(status=status, index=None))
            elif parts == ['library', 'scan'] and method == 'POST': self.send_json(202, self.library.start())
            elif parts == ['library', 'scan.json'] and method == 'GET': self.send_json(200, self.library.status()['scan'])
            elif parts == ['library', 'piece.json'] and method == 'GET':
                query = parse_qs(split.query)
                self.send_json(200, self.library.piece({k: (query.get(k) or [''])[0] for k in ('package', 'level', 'actor')}))
            elif parts == ['library', 'pieces'] and method == 'POST':
                request = self.body_json()
                sources = request.get('sources') if isinstance(request, dict) else None
                if not isinstance(sources, list) or len(sources) > 5000 or not all(isinstance(s, dict) for s in sources):
                    raise ProjectError(400, 'Send {sources: [{package, level, actor}]}.')
                self.send_json(200, dict(errors=self.library.pieces(sources)))
            elif parts == ['library', 'pieces.json'] and method == 'POST':
                # the records themselves, for a page that opens many pieces: asked for in chunks, so it can show a count
                request = self.body_json()
                sources = request.get('sources') if isinstance(request, dict) else None
                if not isinstance(sources, list) or len(sources) > 200 or not all(isinstance(s, dict) for s in sources):
                    raise ProjectError(400, 'Send {sources: [{package, level, actor}]}, at most 200.')
                self.send_json(200, dict(pieces=self.library.records(sources)))
            elif parts == ['library', 'effect.json'] and method == 'GET':
                query = parse_qs(split.query)
                self.send_json(200, self.library.effect({k: (query.get(k) or [''])[0] for k in ('package', 'level', 'actor')}))
            elif parts == ['library', 'effects.json'] and method == 'POST':
                request = self.body_json()
                sources = request.get('sources') if isinstance(request, dict) else None
                if not isinstance(sources, list) or len(sources) > 200 or not all(isinstance(s, dict) for s in sources):
                    raise ProjectError(400, 'Send {sources: [{package, level, actor}]}, at most 200.')
                self.send_json(200, dict(effects=self.library.effects(sources)))
            elif parts == ['library', 'state.json'] and method == 'GET': self.send_json(200, self.library.load_state())
            elif parts == ['library', 'state.json'] and method == 'PUT':
                request = self.body_json()
                if not isinstance(request, dict): raise ProjectError(400, 'Send {expectedRevision, document}.')
                self.send_json(200, self.library.save_state(request.get('document'), request.get('expectedRevision')))
            elif parts == ['library', 'pictures.json'] and method == 'GET':
                self.send_json(200, dict(pictures=self.library.thumbs('pictures')))
            elif len(parts) == 3 and parts[:2] in (['library', 'thumbs'], ['library', 'pictures']) and parts[2].endswith('.png') and method in ('GET', 'PUT'):
                folder = parts[1]
                path = self.library.thumb(parts[2][:-4], folder)
                if method == 'PUT':
                    length = self.body_length(4 << 20 if folder == 'pictures' else 1 << 20)
                    self.body_read = True
                    self.send_json(200, self.library.save_thumb(parts[2][:-4], self.rfile.read(length), folder))
                elif not path.is_file(): raise ProjectError(404, 'No picture is kept for that.')
                else:
                    payload = path.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        except (OSError, ValueError) as error:
            self.send_json(500, dict(error=f'The library could not be read: {error}'))
        finally:
            self.drain_body()
        return True

    # The cache filled ahead of use (precache.py): GET /precache.json (?plan=1 adds what there is to do),
    # POST /precache/start {pieces, maps} and POST /precache/cancel.
    def handle_precache(self, method):
        split = urlsplit(self.path)
        if split.path not in ('/precache.json', '/precache/start', '/precache/cancel'): return False
        self.body_read = False
        try:
            if self.precache is None: raise ProjectError(404, 'This server caches nothing ahead.')
            if split.path == '/precache.json' and method == 'GET':
                self.send_json(200, self.precache.status(plan='plan=1' in split.query))
            elif split.path != '/precache.json' and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                if split.path == '/precache/start': self.send_json(202, self.precache.start(self.body_json()))
                else: self.send_json(200, self.precache.cancel())
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        except (OSError, ValueError) as error:
            self.send_json(500, dict(error=f'The cache could not be read: {error}'))
        finally:
            self.drain_body()
        return True

    # The game install and the doctor's checks (gamesetup.py): GET /setup.json (?checks=0 leaves the checks out),
    # POST /setup/game {folder} and POST /setup/browse.
    def handle_setup(self, method):
        split = urlsplit(self.path)
        if split.path not in ('/setup.json', '/setup/game', '/setup/browse'): return False
        self.body_read = False
        try:
            if self.game_setup is None: raise ProjectError(404, 'This server sets nothing up.')
            if split.path == '/setup.json' and method == 'GET':
                self.send_json(200, self.game_setup.status(checks='checks=0' not in split.query))
            elif split.path != '/setup.json' and method == 'POST':
                if not self.same_origin(): raise ProjectError(403, 'Changes are only accepted from the viewer itself.')
                self.send_json(200, self.game_setup.choose(self.body_json()) if split.path == "/setup/game" else self.game_setup.browse())
            else: raise ProjectError(405, 'Not allowed.')
        except ProjectError as error:
            self.send_json(error.status, dict(error=error.message, **error.extra))
        finally:
            self.drain_body()
        return True

    def map_catalogue(self, body=True):
        # a server that exports maps marks the ones exported by an older exporter (the page exports them again), and
        # serves each map from its export of the install's file as the file is now
        if self.exports: self.exports.recheck()
        payload=json.dumps(public_catalogue(self.catalogue, EXPORT_VERSION if self.exports else None)).encode('utf8')
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        if body:self.wfile.write(payload)

    def user_guide(self, body=True):
        """GET /guide.html: the user guide as one page (guide.py), which the ? menu links to."""
        payload = guide.page()
        if payload is None:
            self.send_error(404, 'This editor has no user guide')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if body: self.wfile.write(payload)

    def do_GET(self): self.answer('GET', self.route_GET)

    def route_GET(self):
        if urlsplit(self.path).path == '/maps.json': self.map_catalogue()
        elif urlsplit(self.path).path == '/guide.html': self.user_guide()
        elif not any(handle('GET') for handle in (self.handle_map, self.handle_families, self.handle_collision, self.handle_wave, self.handle_generated, self.handle_looks, self.handle_play, self.handle_squad, self.handle_manager, self.handle_queue, self.handle_setup, self.handle_precache, self.handle_library, self.handle_prefabs, self.handle_prefab_tests, self.handle_project)):
            super().do_GET()

    def do_PUT(self): self.answer('PUT', self.route_PUT)

    def route_PUT(self):
        if not any(handle('PUT') for handle in (self.handle_squad, self.handle_library, self.handle_prefabs, self.handle_project)): self.send_error(405)

    def do_POST(self): self.answer('POST', self.route_POST)

    def route_POST(self):
        if not any(handle('POST') for handle in (self.handle_map, self.handle_play, self.handle_squad, self.handle_manager, self.handle_queue, self.handle_setup, self.handle_precache, self.handle_library, self.handle_prefabs, self.handle_prefab_tests, self.handle_project)): self.send_error(405)

    def do_DELETE(self): self.answer('DELETE', self.route_DELETE)

    def route_DELETE(self):
        if not any(handle('DELETE') for handle in (self.handle_squad, self.handle_prefabs, self.handle_manager, self.handle_project)): self.send_error(405)

    def do_HEAD(self): self.answer('HEAD', self.route_HEAD)

    def route_HEAD(self):
        if urlsplit(self.path).path == '/maps.json': self.map_catalogue(body=False)
        elif urlsplit(self.path).path == '/guide.html': self.user_guide(body=False)
        elif not self.handle_wave('HEAD'): super().do_HEAD()

    def translate_path(self, path):
        request = unquote(urlsplit(path).path)
        # (only the one slash the request path starts with is taken off: a second one would make it a network path)
        root,rel=WEB,request[1:] if request.startswith('/') else request
        if request.startswith('/cache-library/'):
            # a library piece's meshes and textures (library.py): <donor>/<generation>/<file>
            if self.library is None: return str(WEB / ".denied")
            root,rel=pieces_root(self.library.cache).resolve(),request[len('/cache-library/'):]
        elif request.startswith('/cache/'):
            rel=request[len('/cache/'):]
            map_id,_,asset=rel.partition('/')
            entry=self.catalogue['maps'].get(map_id)
            # a listed map not exported yet has no files to serve
            if entry and entry.get('root') is None: return str(WEB / ".denied")
            root=entry['root'] if entry else self.scene_root
            if root is None: return str(WEB / ".denied")
            if entry:rel=asset
        return contained(root, rel)

    def list_directory(self, path):
        self.send_error(403, "Directory listing is disabled")
        return None

    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def running_viewer(port):
    """Whether a viewer answers on this port (its map list)."""
    from urllib.request import urlopen
    try:
        with urlopen(f"http://127.0.0.1:{port}/maps.json", timeout=5) as response:
            return 'maps' in json.loads(response.read())
    except (OSError, ValueError):
        return False


def compiler_families():
    """The compiler's families (compiler.FAMILIES), for serve --family's choices."""
    import families
    return families.compiler.FAMILIES


def main():
    # a redirected output is in the system's code page: a folder name it lacks (a Cyrillic user name on a Western
    # system) is shown with a stand-in rather than stopping the server as it starts (review finding 35)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try: stream.reconfigure(errors='backslashreplace')
            except (OSError, ValueError): pass
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command",required=True)
    exp = sub.add_parser("export",help="Read an original EW package into an external cache")
    exp.add_argument("map",type=Path)
    exp.add_argument("--cache",type=Path,help="The viewer cache to export into (default: the cache setting)")
    exp.add_argument("--scope",choices=("map",),default="map",help="map, the whole map (the only scope)")
    exp.add_argument("--spec",type=Path,action="append",default=[],help="Include a patch spec as an experimental preview (repeatable)")
    serve = sub.add_parser("serve",help="Open an exported scene locally")
    serve.add_argument("scene",type=Path,nargs="?",help="Cache root with prepared maps, or one exact cache generation (default: the cache setting)")
    # 8768 is the main viewer/editor server (AGENTS.md); test servers use 8790-8799.
    serve.add_argument("--port",type=int,default=8768)
    serve.add_argument("--no-open",action="store_true")
    serve.add_argument("--reuse",action="store_true",help="If a viewer already serves the port, open the browser on it and stop (the release's launcher)")
    serve.add_argument("--projects",type=Path,help="Projects folder (default: the projects setting); tests use a scratch folder")
    serve.add_argument("--prefabs",type=Path,help="Prefab library folder (default: the prefabs setting; with --projects, a prefabs folder beside it)")
    serve.add_argument("--builds",type=Path,help="Builds folder (default: the output setting); tests use a scratch folder")
    serve.add_argument("--squad",type=Path,help="The test squad's file (default: test-squad.json beside the settings): a test server points it at a scratch file, never the user's")
    serve.add_argument("--dry-play",action="store_true",help="Play in game does everything but start the game: for tests, with --install <a scratch game folder>")
    serve.add_argument("--family",action="append",default=[],choices=sorted(f for f, v in compiler_families().items() if not v['builds']),help="A family the compiler doesn't build for every project that this server's page edits and its Build makes, for an experiment's runs (as build.py --family; the choices are the families still switched off: today 'other', the classes with no family of their own)")
    serve.add_argument("--try-mission-lines",action="store_true",help="Play in game puts in every mission command not yet known to work (missions.LINES: the open line's content options, the civilians' looks, the UFO and council types), for the game runs that try them (EXP-53)")
    serve.add_argument("--install",type=Path,help="The game folder Play in game installs into and starts (default: the install setting, else the game install); tests use a scratch copy")
    conf = sub.add_parser("settings",help="Show the editor settings, or set them (a folder path, or an empty string to clear)")
    for key in KEYS: conf.add_argument(f"--{key}")
    conf.add_argument("--lwr",dest="game",help=argparse.SUPPRESS)      # the game setting's name before plain EW
    lib = sub.add_parser("library",help="The library of pieces across the game's maps: scan the install, or export one piece")
    lib.add_argument("action",choices=("scan","piece","precache"))
    lib.add_argument("names",nargs="*",help="piece: the donor map and the actor")
    lib.add_argument("--cache",type=Path,help="The viewer cache (default: the cache setting)")
    lib.add_argument("--game",type=Path,help="The game install (default: the game setting)")
    lib.add_argument("--jobs",type=int,default=6)
    lib.add_argument("--only",nargs="+",help="scan: these maps only")
    lib.add_argument("--stop-file",type=Path,help="precache: stop after the pieces in hand once this file appears")
    doc = sub.add_parser("doctor",help="Check the editor's prerequisites")
    doc.add_argument("--cache",type=Path,help="Also check the game install's maps against this cache's exports")
    args = ap.parse_args()
    if args.command in ("export", "serve") and (args.cache if args.command == "export" else args.scene) is None:
        try: cache = load_settings()['cache']
        except (OSError, ValueError) as error: ap.error(f"Settings: {error}")
        if args.command == "export": args.cache = cache
        else: args.scene = cache
    if args.command == "library":
        import library
        try:
            settings = load_settings() if args.cache is None or args.game is None else {}
            cache = args.cache or settings['cache']
            game, note = resolve_game(args.game or settings['game']) if (args.game or settings.get('game')) else (None, 'the game install is not set')
        except (OSError, ValueError) as error: ap.error(f"Settings: {error}")
        if game is None: ap.error(note)
        if args.action == "scan":
            index = library.scan(game, cache, args.jobs, only=args.only,
                                 progress=lambda done, total, name: print(f"progress: scanning the maps {done}/{total}", flush=True))
            print(json.dumps(library.summary(index), indent=2))
        elif args.action == "precache":
            # every piece the library lists, written to the cache ahead of use (the page's Settings menu: precache.py);
            # the library is read first when it is not there or the install's maps changed since
            index = library.load_index(cache)
            if index is None or any(library.stale(index, game)):
                library.scan(game, cache, args.jobs,
                             progress=lambda done, total, name: print(f"progress: reading the game's maps {done}/{total}", flush=True))
            result = library.precache(game, cache, args.jobs, stop=args.stop_file,
                                      progress=lambda done, total: print(f"progress: caching the pieces {done}/{total}", flush=True))
            print("result: " + json.dumps(result), flush=True)
        else:
            if len(args.names) != 2: ap.error("library piece takes the donor map and the actor")
            try: record = library.piece(cache, game, dict(package=args.names[0], actor=args.names[1]))
            except ProjectError as error: ap.error(error.message)
            print(json.dumps(dict(base=record['base'], objects=len(record['objects']), meshes=len(record['meshes']),
                                  materials=len(record['materials']), textures=len(record['textures']),
                                  diagnostics=len(record['diagnostics'])), indent=2))
    elif args.command == "export":
        # progress lines for the server's export on first open (exports.py)
        report = lambda what, done, total: print(f"progress: {what} {done}/{total}", flush=True)  # noqa: E731
        folder, data = export_map(args.map,args.cache,args.scope,args.spec,progress=report)
        print(json.dumps({"folder":str(folder),"counts":data["counts"],"diagnostics":len(data["diagnostics"])},indent=2))
    elif args.command == "settings":
        updates = {key: (getattr(args, key) or None) for key in KEYS if getattr(args, key) is not None}
        try: settings = save_settings(updates) if updates else load_settings()
        except (OSError, ValueError) as error: ap.error(str(error))
        print(settings_path())
        for key in KEYS: print(f"  {key:9} {settings[key] if settings[key] is not None else '(not set)'}")
    elif args.command == "doctor":
        try: settings = load_settings()
        except (OSError, ValueError) as error: ap.error(str(error))
        sources = []
        if args.cache:
            for entry in load_catalogue(args.cache)['maps'].values():
                source = json.loads((entry['root'] / 'scene.json').read_text(encoding='utf8')).get('source', {})
                if source.get('sha256'): sources.append(dict(name=entry['name'], sha256=source['sha256']))
        checks = doctor(settings, sources)
        for check in checks:
            print(f"{check['status'].upper():8} {check['name']:15} {check['detail']}")
            if check['fix']: print(f"{'':24} -> {check['fix']}")
        raise SystemExit(0 if all(c['status'] in ('ok', 'warn') for c in checks) else 1)
    else:
        # A cache root may be empty (a first run): the page then asks for the game install and lists its maps.
        exact = (args.scene/"scene.json").is_file()
        if not exact:
            try: args.scene.mkdir(parents=True, exist_ok=True)
            except OSError as error: ap.error(f"Cache {args.scene}: {error}")
        # The port first (review finding 16): a second start while the editor runs (the release launcher's --reuse, a
        # double launch) finds it taken before it deletes or reads anything of the cache the running server serves.
        # The socket listens from here; requests wait for the routes, set once everything below is ready.
        try:
            server = LocalServer(("127.0.0.1", args.port), Handler)
        except OSError as error:
            if error.errno not in (errno.EADDRINUSE,) and getattr(error,"winerror",None) != 10048: raise
            if args.reuse and running_viewer(args.port):
                print(f"The editor is already running: http://127.0.0.1:{args.port}/", flush=True)
                if not args.no_open: webbrowser.open(f"http://127.0.0.1:{args.port}/")
                return
            ap.error(f"Port {args.port} is already in use, probably by a viewer that is already running (8768 is the "
                     "main one). Restart that one (Ctrl+C in its window) instead of starting a second; tests "
                     "use --port 8790-8799.")
        # while it runs, Setup sees the editor running and asks for it to be closed before an upgrade (finding 60)
        import appmutex
        appmutex.hold()
        try:
            serve_cache(args, ap, server, exact)
        finally:
            server.server_close()


def serve_cache(args, ap, server, exact):
    """The rest of `serve`, once `server` holds the port: the cache pruned and read, the routes set, and served."""
    # the main server deletes old exports before it picks its own (prune.py; a test server never does)
    main_server = args.port == MAIN_PORT and not exact
    if main_server:
        try:
            import prune
            pruned = prune.prune(args.scene)
            if pruned['removed'] or pruned['failed']:
                print(f"Old exports: {len(pruned['removed'])} removed ({pruned['bytes'] / 1e9:.1f} GB)"
                      + (f", {len(pruned['failed'])} could not be removed" if pruned['failed'] else ''), flush=True)
        except OSError as error:
            print(f"Old exports were not removed: {error}", flush=True)
    try: exported=load_catalogue(args.scene, allow_empty=not exact)
    except (OSError,ValueError) as error:ap.error(str(error))
    try:
        settings = load_settings()
        projects = ProjectStore(args.projects or settings['projects'])
        prefabs = PrefabStore(args.prefabs or (args.projects.parent / 'prefabs' if args.projects else settings['prefabs']))
    except (OSError,ValueError) as error:ap.error(f"Settings: {error}")
    # Build finds a project's export by its map and hash under the cache root (one exact generation's is two up).
    cache_root = args.scene.parent.parent if exact else args.scene
    if args.family:
        import families as family_table
        family_table.ENABLED.update(args.family)
    # a scratch projects folder beside the settings' builds folder (a test server given --projects alone) must not
    # make every real variant look abandoned to the prune at start: only each variant's newest are then kept whole
    builds = BuildRunner(projects, cache_root, args.builds or settings['output'], enable=args.family,
                         orphans=not (args.projects and not args.builds))
    if not (WEB/"vendor/three/three.module.js").is_file():
        ap.error("Run python tools/viewer/setup_vendor.py once to install the pinned browser library")
    # Serving a cache root lists every map the game install plays; those not exported yet export on first open.
    catalogue, exports = (exported, None) if exact else install_catalogue(exported, cache_root, settings, main_server)
    # Play in game (play.py): in the install setting's game, else the game install.
    dry = dict(start=lambda argv, cwd=None: None, command=lambda game, name, steam: ([], None, 'dry'), appear=0, cleanup=False) if args.dry_play else {}
    live = Live(catalogue, exports, Player(settings, builds, catalogue, projects, install=args.install, try_lines=args.try_mission_lines, **dry),
                None if exact else LibraryRunner(cache_root, settings['game']))
    # the test squad (squads.py): its file beside the settings, checked against the install Play in game uses
    from squads import SquadService, SquadStore, store_path
    live.player.squads = SquadService(SquadStore(args.squad or store_path()), lambda: live.player.target(),
                                      cache=Path(cache_root) / '.gamedata')
    prefab_tests = PrefabTests(builds, live)
    precache = None if exact else PrecacheRunner(live, cache_root)
    # a new project's map name (outputnames.py): checked against the projects, the builds, the game install the
    # editor reads and the one Play in game uses (both followed when the page picks another install)
    import outputnames
    from settings import game_install
    projects.names = outputnames.Service(projects, builds.output, lambda: [
        (game_install(live.player.settings)[0], 'the game install'),
        (live.player.target()[0], 'the install Play in game uses')])

    def configure(new_settings):
        """Another game install chosen in the page: its maps listed (the exported ones kept), Play in game
        pointed at it."""
        fresh = load_catalogue(cache_root, allow_empty=True) if not exact else exported
        catalogue, exports = (fresh, None) if exact else install_catalogue(fresh, cache_root, new_settings, main_server)
        with live.player.lock:
            live.catalogue, live.exports = catalogue, exports
            live.player.settings, live.player.catalogue = new_settings, catalogue
            if live.library: live.library = LibraryRunner(cache_root, new_settings['game'])
    # the build queue (buildqueue.py): its context is what a build would use now, read from the settings file as
    # build.py reads it (and the server's own --install); nothing of its store is touched before activate
    def queue_context():
        from settings import game_install as read_game, install_game
        try: current = load_settings()
        except (OSError, ValueError) as error: raise ProjectError(409, f'The settings can\'t be read: {error}')
        game, note = read_game(current)
        if game is None: raise ProjectError(409, note)
        play = args.install or install_game(current)[0]
        check = [str(Path(play).resolve())] if play and not outputnames.same(play, game) else []
        return dict(projects=str(projects.root.resolve()), output=str(builds.output.resolve()),
                    cache=str(Path(cache_root).resolve()), game=str(Path(game).resolve()),
                    udk=str(Path(current['udk']).resolve()) if current.get('udk') else None, checkGames=check)
    queue = BuildQueue(projects, builds, queue_context)

    def settings_guard():
        queue.settings_guard()
        install_busy(live, precache)
    setup = GameSetup(configure, guard=settings_guard)
    server.RequestHandlerClass = partial(Handler, live=live, projects=projects, builds=builds, setup=setup,
                                         prefabs=prefabs, prefab_tests=prefab_tests, precache=precache, queue=queue)
    # the port is this server's: an earlier server's builds proved gone (or kept as busy until they are) and its
    # package swaps settled before any request can build (builds.py recover); a server that could not bind has
    # started nothing
    builds.recover()
    live.player.recover()       # (an earlier server's play left in the game: put back once it has closed)
    if not queue.activate(): print(queue.unavailable, flush=True)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"{url} (process {os.getpid()}; projects in {projects.root})",flush=True)
    if not args.no_open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        # a closing server stops its queue (its build drained, the queue left stopped for Resume)
        queue.close()


if __name__ == "__main__": main()
