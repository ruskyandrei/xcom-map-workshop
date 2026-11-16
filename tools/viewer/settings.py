"""Editor settings and the doctor check (first-editor plan, section 8).

Settings say where projects, builds, exported maps and the toolchain live: no tool in this repository hard-codes a
folder of one computer. They are kept as JSON in Documents\\XCOM Map Workshop\\settings.json, beside the projects,
where every program sees the same file (the Microsoft Store's Python redirects what it writes under %APPDATA% to a
folder of its own, out of sight of PowerShell and the lab tools; a file it left there is moved here when first read).
The XCOM_MAP_WORKSHOP_SETTINGS environment variable names another file (tests use it). Unset folders take defaults
(default_folders): in a release, projects and builds in the editor's own folder; else, and the cache always, under
Documents\\XCOM Map Workshop. The game install has no default: building needs it set. UDK is optional (only a
patch would need it, and no edit the editor builds has one). The doctor reports each prerequisite as found, missing
or wrong, with what to do.

The game install is XCOM: Enemy Within with Long War Rebalance, or plain Enemy Within (game_kind tells them apart):
what is Long War's in it (landing-zone and mini-mod config, LWR's streamed patches) is used where the install has it.
The setting was called lwr before 8 November 2026: a file with "lwr" is read the same, and load_settings gives the
game install under both names.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

APP = 'XCOM Map Workshop'
# projects/output: where the editor writes projects and builds. cache: exported maps, the viewer's cache (decoded game
# data, so never in a repository). game: the game install the editor reads (pristine maps and config lines), LWR or
# plain EW: the game folder itself, or a folder holding game folders (see resolve_game). install: optional, the game
# folder Play in game installs into and starts (tools/viewer/play.py); unset, the game install itself. udk: optional, UDK
# 2011-09 with the XComGame stubs, for a patch. lab: optional, our own lab's working folder (logs, fixtures, snapshots,
# compiled helpers): only the lab tools in tools/lab, tools/bake, tools/patch and tools/re use it, never the editor.
# prefabs: the user's prefab library (tools/viewer/prefabs.py), one file for each prefab; unset, a `prefabs` folder
# beside the projects folder.
KEYS = ('projects', 'output', 'cache', 'game', 'install', 'udk', 'lab', 'prefabs')
# Earlier names of settings, read and set as the setting they name now (load_settings gives both).
ALIASES = {'lwr': 'game'}


def documents():
    """The user's Documents folder (it can be redirected, so ask Windows), or ~/Documents elsewhere."""
    if sys.platform == 'win32':
        import ctypes
        class GUID(ctypes.Structure):
            _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]
        folder = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        path = ctypes.c_wchar_p()
        try:
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(path)) == 0:
                try: return Path(path.value)
                finally: ctypes.windll.ole32.CoTaskMemFree(path)
        except OSError: pass
    return Path.home() / 'Documents'


def settings_path():
    if os.environ.get('XCOM_MAP_WORKSHOP_SETTINGS'): return Path(os.environ['XCOM_MAP_WORKSHOP_SETTINGS'])
    path = documents() / APP / 'settings.json'
    if not path.is_file(): _move_old_settings(path)
    return path


def _move_old_settings(path):
    """Settings kept in %APPDATA%\\XCOM Map Workshop before 8 November 2026 move beside the projects (once)."""
    old = Path(os.environ['APPDATA']) / APP / 'settings.json' if os.environ.get('APPDATA') else None
    if old is None or not old.is_file(): return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(old.read_bytes())
        old.replace(old.with_name('settings.json.moved'))
    except OSError: pass


def _stored(path):
    if not path.is_file(): return {}
    data = json.loads(path.read_text(encoding='utf8'))
    if not isinstance(data, dict): raise ValueError(f'{path} does not hold a settings object')
    return data


def editor_folder():
    """A release's own folder (the one holding VERSION.txt, tools and python: make_release.py), else None: run from
    the repository, whose folder never takes projects or builds."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / 'VERSION.txt').is_file() and (root / 'python').is_dir() else None


_WRITABLE = {}


def _writable(folder):
    """Whether files can be made in the folder (once per run): an install for all users, in Program Files, isn't."""
    key = str(folder)
    if key not in _WRITABLE:
        probe = Path(folder) / f'.write-test-{os.getpid()}'
        try:
            probe.write_bytes(b'')
            probe.unlink()
            _WRITABLE[key] = True
        except OSError:
            _WRITABLE[key] = False
    return _WRITABLE[key]


def _holds_anything(folder):
    try: return Path(folder).is_dir() and any(Path(folder).iterdir())
    except OSError: return False


def default_folders(root=None, home=None):
    """Where projects, builds and the cache go when the settings don't say. In a release, projects and builds go in
    the editor's own folder (`root`, editor_folder()), beside tools and python: an upgrade keeps them there (the
    installer replaces tools and python only) and uninstalling leaves them. Under Documents\\XCOM Map Workshop
    (`home`) instead: run from the repository; an editor folder that can't be written (installed for all users); and
    for each of the two, while that Documents folder holds anything (an earlier release's projects or builds, so none
    go out of sight). The cache stays under Documents."""
    home = home or documents() / APP
    result = {'projects': home / 'projects', 'output': home / 'builds', 'cache': home / 'cache'}
    root = root if root is not None else editor_folder()
    if root is not None and _writable(root):
        for key, name in (('projects', 'projects'), ('output', 'builds')):
            if not _holds_anything(result[key]): result[key] = Path(root) / name
    return result


def load_settings(path=None):
    """Every setting as a Path, or None where unset and without a default."""
    path = path or settings_path()
    stored = _stored(path)
    result = dict(default_folders(), game=None, install=None, udk=None, lab=None, prefabs=None)
    for key in KEYS:
        value = stored.get(key)
        if value is None:
            value = next((stored[old] for old, new in ALIASES.items() if new == key and stored.get(old) is not None), None)
        if value is None: continue
        if not isinstance(value, str) or not value.strip(): raise ValueError(f'{path}: "{key}" must be a folder path')
        result[key] = Path(value)
    # the prefab library goes beside the projects, wherever they are
    if result['prefabs'] is None:
        beside_projects = result['projects'].parent / 'prefabs'
        previous = documents() / APP / 'prefabs'
        # A portable upgrade can find a standalone prefab library in Documents even with no projects there.
        result['prefabs'] = (previous if stored.get('projects') is None and _holds_anything(previous)
                             and not _holds_anything(beside_projects) else beside_projects)
    for old, new in ALIASES.items(): result[old] = result[new]
    return result


def save_settings(updates, path=None):
    """Set (a path) or clear (None) the given settings; other keys in the file are kept."""
    path = path or settings_path()
    stored = _stored(path)
    for key, value in updates.items():
        key = ALIASES.get(key, key)
        if key not in KEYS: raise ValueError(f'Unknown setting {key}')
        for old, new in ALIASES.items():
            if new == key: stored.pop(old, None)
        if value is None: stored.pop(key, None)
        else: stored[key] = str(Path(value).resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(stored, indent=2) + '\n', encoding='utf8', newline='\n')
    os.replace(temp, path)
    return load_settings(path)


LAB_MARKER = 'XComLab-copy.txt'
# The folder name Steam runs; tools/lab/switch_install.ps1 parks the other install beside it as .LWR or .Lab.
STEAM_NAME = 'XCom-Enemy-Unknown'


def is_game(folder):
    return (Path(folder) / 'XEW' / 'XComGame' / 'CookedPCConsole').is_dir()


# What a game folder holds, by the config only each has (XEW\XComGame\Config): LWR's own, then Long War's
# landing-zone mutator (Long War 1.0 and the mods built on it), else plain Enemy Within.
KINDS = {'lwr': 'Long War Rebalance', 'longwar': 'Long War, not LWR', 'ew': 'Enemy Within'}


def game_kind(folder):
    """'lwr', 'longwar' or 'ew' for a game folder (is_game), else None."""
    folder = Path(folder)
    if not is_game(folder): return None
    config = folder / 'XEW' / 'XComGame' / 'Config'
    if (config / 'DefaultLWRebalance.ini').is_file(): return 'lwr'
    if (config / 'DefaultLZMutator.ini').is_file(): return 'longwar'
    return 'ew'


def kind_label(folder):
    return KINDS.get(game_kind(folder), 'not a game folder')


def resolve_game(folder):
    """The game install a setting names: (game folder or None, what was found). The setting can be the game folder
    itself (an install anywhere), or a folder holding game folders, such as Steam's steamapps\\common, where
    switch_install swaps the lab copy and LWR between XCom-Enemy-Unknown and its parked names. In a folder, the game
    folder without the lab marker is the install; a lab copy is never taken for it."""
    folder = Path(folder)
    if is_game(folder):
        lab = (folder / LAB_MARKER).is_file()
        return (None if lab else folder), (f'{folder} is the lab copy, not the game install' if lab else f'{folder} ({kind_label(folder)})')
    if not folder.is_dir(): return None, f'{folder} does not exist'
    games = sorted(child for child in folder.iterdir() if child.is_dir() and is_game(child))
    plain = [g for g in games if not (g / LAB_MARKER).is_file()]
    if not games: return None, f'{folder} has no game folder (one holding XEW\\XComGame\\CookedPCConsole)'
    if not plain: return None, f'{folder} holds only the lab copy ({", ".join(g.name for g in games)}), not the game install'
    if len(plain) > 1:
        # Steam's own names first: the active folder, then the one switch_install parks LWR as.
        for name in (STEAM_NAME, STEAM_NAME + '.LWR'):
            pick = [g for g in plain if g.name == name]
            if pick: return pick[0], f'{pick[0]} ({kind_label(pick[0])}; in {folder}; also there: {", ".join(g.name for g in plain if g != pick[0])})'
        return None, f'{folder} holds several game folders ({", ".join(g.name for g in plain)}); set the one to read itself'
    return plain[0], f'{plain[0]} ({kind_label(plain[0])}; in {folder})'


def game_setting(settings):
    """The game setting of a settings dict (load_settings gives it as game and lwr; older callers' dicts have lwr)."""
    return settings['game'] if 'game' in settings else settings.get('lwr')


def game_install(settings):
    """(the game folder the game setting names, or None; what was found)."""
    folder = game_setting(settings)
    if folder is None: return None, 'The game install is not set (choose it in the editor, or viewer.py settings --game <folder>)'
    return resolve_game(folder)


# The names from before plain EW (8 November 2026), which the lab tools and tests still use.
resolve_lwr, lwr_game = resolve_game, game_install


def install_game(settings):
    """(the game folder Play in game installs into and starts, or None; what was found): the install setting, else the game
    install the editor reads."""
    folder = settings['install']
    if folder is None: return game_install(settings)
    return (folder, str(folder)) if is_game(folder) else (None, f'{folder} is not a game folder (no XEW\\XComGame\\CookedPCConsole)')


def configured(key):
    """A folder setting, or None when it is unset or the settings can't be read: defaults for tests and scripts."""
    try: return load_settings()[key]
    except (OSError, ValueError): return None


def lwr_cooked():
    """The game install's EW CookedPCConsole, or None: test fixtures default to its packages."""
    try: game, _ = game_install(load_settings())
    except (OSError, ValueError): return None
    return None if game is None else game / 'XEW' / 'XComGame' / 'CookedPCConsole'


def require(settings, key):
    """A folder setting a tool can't do without: its path, or a ValueError saying how to set it."""
    name = ALIASES.get(key, key)
    if settings.get(key) is None: raise ValueError(f'The {name} setting is not set: python tools/viewer/viewer.py settings --{name} <folder>')
    return settings[key]


def _check(name, status, detail, fix=''):
    return {'name': name, 'status': status, 'detail': detail, 'fix': fix}


def _writable_folder(name, folder):
    target = folder.absolute()
    try:
        parent = next((p for p in (target, *target.parents) if p.exists()), target)
        with tempfile.TemporaryFile(dir=parent):
            pass
    except OSError as error:
        return _check(name, 'wrong', f'{folder} is not writable ({error.strerror})',
                      f'Choose another folder: viewer.py settings --{name} PATH')
    return _check(name, 'ok', str(folder) if target == parent else f'{folder} (created on first use)')


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): digest.update(block)
    return digest.hexdigest()


def doctor(settings, sources=()):
    """Each prerequisite as {name, status: ok | missing | wrong | warn, detail, fix}. `sources` are exported maps'
    source records ({name, sha256}), checked against the game install's copies."""
    checks = [_check('settings', 'ok', f'{settings_path()}' + ('' if settings_path().is_file() else ' (not written yet: defaults in use)'))]
    checks.append(_writable_folder('projects', settings['projects']))
    if settings.get('prefabs'): checks.append(_writable_folder('prefabs', settings['prefabs']))
    checks.append(_writable_folder('output', settings['output']))
    checks.append(_writable_folder('cache', settings['cache']))
    version = sys.version_info
    checks.append(_check('python', 'ok' if version >= (3, 10) else 'wrong', sys.version.split()[0],
                         '' if version >= (3, 10) else 'Install Python 3.10 or later'))
    pwsh = shutil.which('pwsh')
    # PowerShell 7 runs patchtool, which only a patch needs (with UDK): optional, like UDK
    if not pwsh: checks.append(_check('powershell', 'ok', 'pwsh is not on PATH, and not needed: only a patch (with UDK) runs it'))
    else:
        try:
            out = subprocess.run([pwsh, '-NoProfile', '-Command', '$PSVersionTable.PSVersion.Major'], capture_output=True,
                                 text=True, timeout=30).stdout.strip()
            major = int(out)
            checks.append(_check('powershell', 'ok' if major >= 7 else 'warn', f'PowerShell {out} ({pwsh})',
                                 '' if major >= 7 else 'Optional (only a patch needs it): install PowerShell 7'))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            checks.append(_check('powershell', 'warn', f'{pwsh} did not report its version ({error})', 'Optional (only a patch needs it): reinstall PowerShell 7'))
    folder = game_setting(settings)
    found, note = resolve_game(folder) if folder is not None else (None, '')
    if folder is None:
        checks.append(_check('game', 'missing', 'The game install is not set',
                             'Choose it in the editor, or: viewer.py settings --game "<the XCOM: Enemy Within game folder (with LWR, or '
                             'plain), or the folder holding it, such as steamapps\\common>"'))
    elif found is None:
        checks.append(_check('game', 'wrong', note, 'Builds read pristine maps from the game install, never the lab copy: set its game folder, or the folder holding it'))
    else:
        checks.append(_check('game', 'ok', note, ''))
        for source in sources:
            local = found / 'XEW' / 'XComGame' / 'CookedPCConsole' / f"{source['name']}.upk"
            if not local.is_file():
                checks.append(_check(f"map {source['name']}", 'missing', f'{local} not found', 'Check the game install'))
                continue
            same = _sha256(local) == source['sha256']
            checks.append(_check(f"map {source['name']}", 'ok' if same else 'wrong',
                                 f'{local} ' + ('matches the exported map' if same else 'differs from the exported map'),
                                 '' if same else 'Re-export the map from this install, or set the install it was exported from'))
    if settings['install'] is not None:
        game, note = install_game(settings)
        checks.append(_check('install', 'ok' if game else 'wrong', note,
                             '' if game else 'Set the game folder Play in game installs into and starts, or clear it to use the game install'))
    # UDK is optional: every edit the editor builds is made in the map itself; only a patch (none today) would cook in it
    udk = settings['udk']
    if udk is None:
        checks.append(_check('udk', 'ok', 'not set, and not needed: every edit the editor builds is made in the map itself'))
    else:
        parts = {'UDK.com': udk / 'Binaries' / 'Win32' / 'UDK.com', 'XComGame stubs': udk / 'UDKGame' / 'Script' / 'XComGame.u',
                 'XComMapEd': udk / 'UDKGame' / 'Script' / 'XComMapEd.u'}
        gone = [name for name, path in parts.items() if not path.is_file()]
        checks.append(_check('udk', 'warn' if gone else 'ok', f'{udk}' + (f": no {', '.join(gone)}" if gone else ': UDK.com, XComGame stubs and XComMapEd found'),
                             'Optional (only a patch needs it): install UDK 2011-09 with the XComGame stubs and compile '
                             'XComMapEd (patchtool build does), or clear the setting' if gone else ''))
    lab = settings['lab']
    if lab is not None:
        checks.append(_check('lab', 'ok' if lab.is_dir() else 'wrong', f'{lab} (the lab tools\' working folder)',
                             '' if lab.is_dir() else 'Set the lab tools\' working folder, or clear it: the editor never uses it'))
    return checks
