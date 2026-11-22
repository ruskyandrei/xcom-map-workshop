"""The records and helpers the viewer suite's tests share (review finding 58: a fixtures module per suite, rather than
tests that import other tests). Named for its suite, as file names are unique across the repository (the bake suite's
is fixtures.py). The records more than one suite shares come from their one home, tools/tests/shared_fixtures.py.

- projects: two ids and a project document, and the second project the manager's and the packs' tests build;
- the temporary game installs the play, manager, pack, recovery and squad tests run on (PlayInstalls, and
  ManagerInstalls with the manager's and the packs' helpers), with the records and config lines they hold;
- the stand-in for build.py the build runner's and the queue's tests start (STANDIN);
- a scene of one piece (scene); the configured install's effects (INSTALL, records); a prefab and a server with a
  prefab library (prefab, PrefabServer); a picture's bytes (png)."""
from functools import partial
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, PngImagePlugin

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests'))
from builds import BuildRunner  # noqa: E402
from catalogue import load_catalogue  # noqa: E402
import effects_metadata as em  # noqa: E402
from export_math import transform  # noqa: E402
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import missions  # noqa: E402
from play import Player  # noqa: E402
import prefabs  # noqa: E402
from prefabs import PrefabStore  # noqa: E402
from projects import SCHEMA, SCHEMA_VERSION, ProjectStore  # noqa: E402
from resolver import place  # noqa: E402
from shared_fixtures import minimal_mesh, record  # noqa: E402,F401  (the records every suite shares)
from viewer import Handler, LocalServer  # noqa: E402

# ---------------------------------------------------------------- projects
# two projects' ids
ID = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc'
OTHER = '1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d'


def document(project_id=ID, **changes):
    """A project on Bar that deletes one piece, with `changes` over it."""
    doc = dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, id=project_id, name='Bar remix', mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256='a' * 64, exporterVersion=12),
               overrides=[dict(target=dict(package='URB_Bar', level='base', actor='TheWorld.PersistentLevel.A_1'), deleted=True)],
               added=[])
    doc.update(changes)
    return doc


# the second project on Bar, which ManagerInstalls.second builds (test_manager's OTHER_ID and OTHER)
SECOND_ID, SECOND_VARIANT = '1a2b3c4d-1d2a-4b6c-8e9f-123456789abc', 'URB_Bar_Second_1a2b'


# ---------------------------------------------------------------- the temporary game installs (test_play's)

VARIANT = 'URB_Bar_Remix_0f8b'
# Long War's loader with the drop-in mutator, and its drop-in settings (editor spawns plan, SP8)
MUTATOR_LOADER = b'[XComMutator.XComMutatorLoader]\r\narrTacticalMutators="XComLZMutator.XComSpawnAlienMutator"\r\n'
RANDOM_SPAWNS = dep.EOL.join([b'[XComLZMutator.XComSpawnAlienMutator]', b'MAX_DROP_DIST = 32', b'ExcludeMaps = "EWI_ChryssalidHive"',
                              b';ExcludeMaps = "DLC2_2_Deluge"', b'', b'[XComLZMutator.XComSpawnMutator]', b'PLAYER_PROXIMITY = 29', b''])
SLOT = installs.FIRST_MISSIONS[0]      # the first mission's record, which the game asks for by name


def game_folder(game, slot, lz=b'LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))', kind='lwr'):
    (game / 'XEW/XComGame/Config').mkdir(parents=True)
    (game / 'XEW/XComGame/CookedPCConsole').mkdir(parents=True)
    (game / 'XEW/Binaries/Win32').mkdir(parents=True)
    (game / 'XEW/Binaries/Win32/XComEW.exe').write_bytes(b'exe')
    (game / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', record('bar'), slot, b'']))
    (game / 'XEW/XComGame/Config/DefaultLZMutator.ini').write_bytes(dep.EOL.join([b'[XComLZMutator.XComLZMutator]', lz, b'']))
    if kind == 'lwr': (game / 'XEW/XComGame/Config/DefaultLWRebalance.ini').write_bytes(b'')
    (game / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk').write_bytes(b'bar')
    (game / 'XEW/XComGame/CookedPCConsole/CIN_DropshipIntros.upk').write_bytes(b'intro')


class PlayInstalls:
    """The play tests' temporary game installs, taken by the play, manager, pack, recovery and squad tests (as a base
    before unittest.TestCase, or method by method): an LWR install and a copy of it, a project on Bar with its build
    runner, the player's settings and the user's Documents; a built package, a player, the config files read back."""

    def setUp(self):
        running = installs.game_running
        self.addCleanup(setattr, installs, 'game_running', running)
        self.running = False
        installs.game_running = lambda *_: self.running
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        # LWR's own first mission: another map's record under the slot's DisplayName
        self.default = dep.set_field(record('liquorstore'), 'DisplayName', SLOT)
        self.lwr, self.copy = root / 'games' / 'LWR', root / 'games' / 'Copy'
        game_folder(self.lwr, self.default)
        game_folder(self.copy, self.default)
        self.output = root / 'builds'
        self.store = ProjectStore(root / 'projects')
        self.store.save(ID, document(output=dict(shipAs=VARIANT, patch='patch_' + VARIANT.lower())), 0)
        self.builds = BuildRunner(self.store, root / 'cache', self.output, command=lambda f: [sys.executable, '-c', ''])
        self.catalogue = dict(defaultMap='URB_Bar', maps=dict(URB_Bar=dict(id='URB_Bar', name='URB_Bar', root=root)))
        self.settings = dict(projects=root / 'projects', output=self.output, cache=root / 'cache', lwr=self.lwr,
                             install=None, udk=None, lab=None)
        # the user's Documents, with the game's own generated config in it
        self.documents = root / 'Documents'
        self.content = self.documents / 'My Games/XCOM - Enemy Within/XComGame/Config/XComContent.ini'
        self.content.parent.mkdir(parents=True)
        self.content.write_bytes(b'[XComGame.XComContentManager]\r\nthe game\'s own\r\n')
        self.started = []

    def player(self, install=None, **more):
        # cleanup off: these tests look at what a play installs, which a real play takes out again once the game has
        # closed (the tests of that pass cleanup=True)
        return Player(dict(self.settings, install=install), self.builds, self.catalogue, self.store,
                      start=lambda argv, cwd=None: self.started.append((argv, cwd)), steam=lambda: Path('steam.exe'),
                      user_documents=self.documents, **dict(dict(appear=0, every=0.01, cleanup=False), **more))

    def package(self, revision=1, quick=False, zones=None, ids=None, groups=None, maps=None, record_missions=None, exclusion=False):
        """A built package: the relit map, its cache and its own copy of the landing intro, streamed in its place; a
        quick build's has no cache. `zones`: the project's own landing-zone lines (config.landingZonesFromProject).
        `maps`: the Build's records (config.maps, text), with `record_missions` (config.recordMissions) when given."""
        folder = self.output / VARIANT
        (folder / 'CookedPCConsole').mkdir(parents=True, exist_ok=True)
        intro = f'CIN_DropshipIntros_{VARIANT}'
        files = {}
        for name, data in [(f'{VARIANT}.upk', b'relit map %d' % revision), ('Lighting_4242.tfc', b'lightmaps'),
                           (f'{intro}.upk', b'intro copy')]:
            if quick and name.endswith('.tfc'): continue
            (folder / 'CookedPCConsole' / name).write_bytes(data)
            files[f'CookedPCConsole/{name}'] = hashlib.sha256(data).hexdigest()
        m = dict(schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId=f'{VARIANT}-{revision}', builtAt='2026-11-08T12:00:00',
                 project=dict(id=ID, name='Bar remix', revision=revision), source=dict(map='URB_Bar', sha256='s' * 64),
                 variant=VARIANT, patch=None, files=files, streams=[], replaceStreams={'CIN_DropshipIntros': intro},
                 **({'quick': True} if quick else {}),
                 **({'config': dict(landingZones=zones, landingZonesFromProject=True, landingZoneIds=ids or [],
                                    **({'ownLandingGroups': groups} if groups else {}))} if zones is not None else {}))
        if exclusion:       # the project leaves scripted drop-ins where placed (build.drop_in_exclusion)
            m.setdefault('config', {})['dropInExclusion'] = dict(file='DefaultRandomSpawns.ini', section='XComLZMutator.XComSpawnAlienMutator',
                                                               line=f'ExcludeMaps = "{VARIANT}"')
        if maps is not None:
            m.setdefault('config', {}).update(maps=maps, missions=[missions.label(missions.kind_key(r)) for r in maps],
                                              **({'recordMissions': record_missions} if record_missions is not None else {}))
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')

    def files(self, game):
        return {n: (game / 'XEW/XComGame/Config' / n).read_bytes() for n in ('DefaultMaps.ini', 'DefaultLZMutator.ini')}

    def records(self, game, name):
        maps = dep.lines_of((game / 'XEW/XComGame/Config/DefaultMaps.ini').read_bytes())
        return [l for l in maps if dep.is_record(l) and dep.field(l, 'Name') == name]

    def settle(self, player):
        """Wait for the player's watch to end (the game 'closed')."""
        player.watching.join(timeout=10)
        self.assertFalse(player.watching.is_alive())


def pack_env(extra_modules=None):
    """The environment a pack's scripts run in when double-clicked (review finding 25): this one without the module
    path a shell may have set (PowerShell 7's, inherited by a suite started from it), so Windows PowerShell builds its
    own. `extra_modules`: folders put first on PSModulePath instead (a launch from PowerShell 7)."""
    import os
    env = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
    if extra_modules: env['PSModulePath'] = ';'.join(str(m) for m in extra_modules)
    return env


def powershell_report(env=None):
    """Which Windows PowerShell a pack's scripts get with this environment, its module path and whether it finds
    Get-FileHash (Microsoft.PowerShell.Utility), for a failure's message."""
    probe = ('"host: " + [Diagnostics.Process]::GetCurrentProcess().Path + " " + $PSVersionTable.PSVersion; '
             '"Get-FileHash: " + [bool](Get-Command Get-FileHash -ErrorAction SilentlyContinue); '
             '"PSModulePath: " + $env:PSModulePath')
    try:
        done = subprocess.run(['cmd', '/c', 'powershell', '-NoProfile', '-Command', probe], capture_output=True, text=True,
                              timeout=60, env=pack_env() if env is None else env)
        return 'Windows PowerShell as the scripts get it:\n' + done.stdout + done.stderr
    except (OSError, subprocess.SubprocessError) as error:
        return f'Windows PowerShell could not be asked ({error})'


class ManagerInstalls(PlayInstalls):
    """PlayInstalls with the project manager's and the map packs' helpers: Bar given more missions, a second project
    built, a game that reads pack cards, and a pack's scripts run."""

    def more_missions(self, game):
        """Bar given a terror record in rotation and a council record out of it, as LWR's maps have."""
        path = game / 'XEW/XComGame/Config/DefaultMaps.ini'
        lines = dep.lines_of(path.read_bytes())
        bar = record('bar')
        terror = dep.set_field(dep.set_field(bar, 'MissionType', 'eMission_TerrorSite', quoted=False), 'DisplayName', 'URB_Bar_Terror (Terror) |0')
        council = dep.set_field(dep.set_field(dep.set_field(bar, 'MissionType', 'eMission_Special', quoted=False),
                                              'CouncilType', 'eFCMType_Bomb', quoted=False), 'DisplayName', 'URB_Bar_Bomb (Bomb) |0')
        council = dep.set_field(council, 'bInRotation', 'False', quoted=False)
        at = lines.index(bar) + 1
        lines[at:at] = [terror, council]
        path.write_bytes(dep.EOL.join(lines))
        return terror, council

    def second(self):
        """Another project on Bar, built."""
        self.store.save(SECOND_ID, dict(document(output=dict(shipAs=SECOND_VARIANT, patch='patch_' + SECOND_VARIANT.lower())), id=SECOND_ID, name='Second bar'), 0)
        folder = self.output / SECOND_VARIANT
        (folder / 'CookedPCConsole').mkdir(parents=True)
        (folder / 'CookedPCConsole' / f'{SECOND_VARIANT}.upk').write_bytes(b'second map')
        m = dict(schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId=f'{SECOND_VARIANT}-1', builtAt='2026-11-09T12:00:00',
                 editorVersion='0.4.0', project=dict(id=SECOND_ID, name='Second bar', revision=1),
                 source=dict(map='URB_Bar', sha256='s' * 64), variant=SECOND_VARIANT, patch=None,
                 files={f'CookedPCConsole/{SECOND_VARIANT}.upk': hashlib.sha256(b'second map').hexdigest()}, streams=[], replaceStreams={})
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')

    def card_game(self, game):
        """The made-up game given a script that reads map pack cards, as LWR 3.00.00 beta 15's does."""
        (game / 'XEW/XComGame/CookedPCConsole/XComMutator.u').write_bytes(b'\0names\0LWRMapPackCard\0more')

    def run_script_with(self, folder, name, game, *more, env=None, code=0):
        """A pack's Install.cmd or Uninstall.cmd run on a game folder, with Windows PowerShell's environment as a
        double-click gives it (pack_env; review finding 25): its output. A failure's message says which PowerShell ran
        and whether it found the commands the scripts use."""
        done = subprocess.run(['cmd', '/c', str(folder / name), str(game), *more], capture_output=True, text=True, timeout=120,
                              env=pack_env() if env is None else env)
        if done.returncode != code:
            self.fail(f'{name} ended with {done.returncode}:\n{done.stdout}{done.stderr}\n{powershell_report(env)}')
        return done.stdout

    def run_script(self, folder, name, game):
        """A pack's Install.cmd or Uninstall.cmd run on a game folder: its output."""
        return self.run_script_with(folder, name, game)


# ---------------------------------------------------------------- the build runner's stand-in (test_builds')

VIEWER = str(Path(__file__).resolve().parents[1])
# Stands in for build.py: prints its stage lines (as build.py does), waits for a go file, then writes a package as
# build.py does (its id unique to the launch, the attempt in its manifest, swapped in with the journal) and prints the
# real success line. Outcomes: ok; fail; grand (a grandchild that waits, its id printed); linger (a grandchild left
# running after a good build); die-<step> (the process ends outright after that step of the swap).
STANDIN = r'''
import datetime, hashlib, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, %r)
import publication
project, output, go, outcome = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
rest = sys.argv[5:]
quick = '--quick' in rest
attempt = rest[rest.index('--attempt') + 1] if '--attempt' in rest else None
doc = json.loads(project.read_text(encoding='utf-8'))
print('snapshot: ' + json.dumps(dict(project=doc['id'], revision=doc['revision'])), flush=True)
print('compile: ' + json.dumps(dict(added=1)), flush=True)
if outcome in ('grand', 'linger'):
    grand = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    print('grandchild: %%d' %% grand.pid, flush=True)
if quick:
    print('running: making the edit in the map', flush=True)
    print('  $ python -B -u native_copy.py URB_Bar.upk lit variant --copies native-edit.json', flush=True)
else:
    print('running: patch and cook', flush=True)
    print('  $ pwsh -File patchtool.ps1 build', flush=True)
print('    progress: relighting 2/5', flush=True)
while not go.exists():
    time.sleep(0.02)
if outcome == 'fail':
    print('build failed: patchtool.ps1 failed (exit 1); see the log', flush=True)
    sys.exit(1)
for s in ('patch', 'light', 'seeds'):
    print(s + ': {}', flush=True)
variant = doc['output']['shipAs']
stamp = datetime.datetime.now().strftime('%%Y%%m%%d-%%H%%M%%S') + ('-' + attempt.replace('-', '')[:8] if attempt else '')
build_id = '%%s-%%s' %% (variant, stamp)
staging = output / '.work' / build_id / 'package'
(staging / 'CookedPCConsole').mkdir(parents=True)
content = ('%%s revision %%s' %% (build_id, doc['revision'])).encode()
(staging / 'CookedPCConsole' / ('%%s.upk' %% variant)).write_bytes(content)
m = dict(schema='xcom-map-workshop/variant-package', schemaVersion=1, buildId=build_id, builtAt='2026-11-07T12:00:00',
         seconds=241, project=dict(id=doc['id'], revision=doc['revision']), variant=variant,
         files={'CookedPCConsole/%%s.upk' %% variant: hashlib.sha256(content).hexdigest()},
         **({'attempt': attempt} if attempt else {}))
if quick:       # a full build's manifest is written as before quick builds: no times, no quick
    m.update(quick=True, seconds=6, times=dict(full=241, quick=6), foreignPieces=2,
             donors=[dict(map='URB_PoliceStation', sha256='d' * 64, file='somewhere', pieces=2, bytes=1234, cut=[])])
(staging / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
die = outcome[4:] if outcome.startswith('die-') else None
existing = output / variant if (output / variant).is_dir() else None
with publication.guard(output, variant):
    publication.publish(output, variant, staging, existing, dict(buildId=build_id, attempt=attempt, project=doc['id']),
                        boundary=lambda name: os._exit(70) if name == die else None)
print('built %%s: %%s (%%s.upk %%s)' %% (build_id, output / variant, variant, hashlib.sha256(content).hexdigest()[:12]), flush=True)
''' % VIEWER


# ---------------------------------------------------------------- landing zones (test_spawns')

def same_place(a, b, slack=2.0):
    """Whether two zones are the same place and direction, within `slack` units (Bar's first line is its own landing
    within two units)."""
    return a['direction'] == b['direction'] and all(abs(float(a['location'][k]) - float(b['location'][k])) <= slack
                                                    for k in range(3))


# ---------------------------------------------------------------- a scene (test_resolver's)

def scene():
    obj=dict(id='1:2',actor='TheWorld.PersistentLevel.Piece',actorClass='XComLevelActor',mesh='m',
             materials=[],location=[10,0,0],rotation=[0,0,0],scale=[1,1,1],hidden=False,floors=[],
             componentTransform=transform([0,0,0],[0,0,0],[1,1,1]))
    place(obj,obj['location'],obj['rotation'],obj['scale'])
    return dict(objects=[obj],meshes={'m':dict(bounds=[0,0,0,1,1,1,2])},materials={},textures={},
                buildings=[],diagnostics=[])


# ---------------------------------------------------------------- the configured install's effects (test_effects_metadata's)

INSTALL, WHY = None, 'no install configured'
try:
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    sys.path.insert(0, str(HERE.parents[1] / 'upk'))
    import labpaths  # noqa: E402
    INSTALL, WHY = labpaths.install_map('URB_Bar')
except Exception as error:      # noqa: BLE001
    WHY = str(error)
_CACHE = {}


def records(name, stream=None):
    """effects_metadata.describe on a package of the configured install, as the export calls it."""
    if (name, stream) not in _CACHE:
        import scene_metadata
        from package import Package
        p = Package(INSTALL.parent / (name + '.upk'))
        landings = [] if stream else scene_metadata.landing_metadata(p)
        carried = {} if stream else {e['actor']: dict(by=e['carriedBy'], how=e['carriedHow'])
                                     for e in scene_metadata.effect_metadata(p) if e['carriedBy']}
        out = em.describe(p, landings=landings, carried=carried, prefix=('stream-%s-' % stream) if stream else '',
                          layer='stream' if stream else 'base', stream=stream)
        out['by'] = {r['actor'].rsplit('.', 1)[-1]: r for r in out['effects'] + out['sounds'] + out['flares']}
        out['package'] = p
        _CACHE[(name, stream)] = out
    return _CACHE[(name, stream)]


# ---------------------------------------------------------------- prefabs (test_prefabs')

PL = 'TheWorld.PersistentLevel.'
LIGHT = dict(color=[255, 240, 200], brightness=1.5, radius=512.0, falloffExponent=2.0, innerConeAngle=0.0,
             outerConeAngle=44.0, enabled=True)


def prefab(prefab_id=ID, **changes):
    doc = dict(
        schema=prefabs.SCHEMA, schemaVersion=prefabs.SCHEMA_VERSION, id=prefab_id, name='Corner shop', floor=dict(tiles=[8, 6]),
        pieces=[
            dict(actor=PL + 'Wall_1_copy1', **{'from': dict(package='URB_Bar', level='base', actor=PL + 'Wall_1')},
                 components=[PL + 'Wall_1.StaticMeshComponent_3'], location=[96, 48, 0], rotation=[0, 16384, 0],
                 prefab=None, partner=None, recipe=dict(key='ab12cd', name='Core_384FloorB')),
            dict(actor=PL + 'Car_2_copy2', **{'from': dict(package='URB_Street', level='base', actor=PL + 'Car_2')},
                 components=[PL + 'Car_2.StaticMeshComponent_0'], location=[288, 96, 0], rotation=[0, 0, 0],
                 prefab='copy2:Car_2', partner=PL + 'Glass_2_copy3', tinted=True),
            dict(actor=PL + 'Glass_2_copy3', **{'from': dict(package='URB_Street', level='base', actor=PL + 'Glass_2')},
                 components=[PL + 'Glass_2.StaticMeshComponent_1'], location=[288, 96, 0], rotation=[0, 0, 0],
                 prefab='copy2:Car_2', partner=None),
            dict(actor=PL + 'CoverBlock_copy4', template=dict(kind='cover', version=1),
                 cover=dict(width=2, length=1, type='high', height=1), location=[0, 0, 12], rotation=[0, 0, 0]),
            dict(actor=PL + 'SpotLight_copy5', template=dict(kind='spot', version=1), light=dict(LIGHT),
                 location=[384, 288, 160], rotation=[-16384, 0, 0]),
        ],
        groups=[dict(id='g-inner', breakTogether=True, members=[dict(added=PL + 'Car_2_copy2'), dict(added=PL + 'Glass_2_copy3')]),
                dict(id='g-outer', members=[dict(group='g-inner'), dict(added=PL + 'Wall_1_copy1'), dict(building='b1')])],
        buildings=[dict(id='b1', name='Corner shop', kind='building', floors=[dict(boxes=[[0, 0, 0, 768, 576, 192]])])],
        donors=[dict(package='URB_Bar', sha256='a' * 64), dict(package='URB_Street')], mission=None)
    doc.update(changes)
    return doc


class PrefabServer:
    """A server with a prefab library of its own in a temporary folder (as a base before unittest.TestCase, or method
    by method), and `call` to ask it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        scene = root / 'cache' / 'URB_Bar' / 'current'; scene.mkdir(parents=True)
        (scene / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=12, name='URB_Bar', scope='map')), encoding='utf8', newline='\n')
        self.store = PrefabStore(root / 'prefabs')
        self.server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(root / 'cache'), prefabs=self.store))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=5)))

    def call(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, method=method,
                          headers={'Content-Type': 'image/png' if raw is not None else 'application/json', **(headers or {})})
        try:
            with urlopen(request) as response:
                payload = response.read()
                return response.status, (payload if response.headers['Content-Type'] == 'image/png' else json.loads(payload))
        except HTTPError as error: return error.code, json.load(error)


# ---------------------------------------------------------------- a picture (test_pictures')

def png(size=(512, 256), mode='RGB', colour=(40, 90, 160), text=None, alpha=None):
    """A PNG's bytes: one colour with a lighter block, of any size and mode; `text` adds a text chunk, `alpha` (0 to
    255) makes it RGBA with that alpha everywhere."""
    image = Image.new('RGB', size, colour)
    image.paste((200, 180, 60), (size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2))
    if alpha is not None:
        image = image.convert('RGBA')
        image.putalpha(alpha)
    elif mode != 'RGB':
        image = image.convert(mode)
    info = None
    if text:
        info = PngImagePlugin.PngInfo()
        info.add_text('Comment', text)
    out = io.BytesIO()
    image.save(out, 'PNG', pnginfo=info)
    return out.getvalue()
