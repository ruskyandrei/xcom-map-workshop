"""The game install chosen in the page, and the doctor's checks shown there (preview checklist item 3): on a first run
the page asks for the install before anything else, and the Project menu's "Game install and checks" opens the same
dialog later.

  GET  /setup.json         the settings, the game install (folder, kind, what was found), the installs found on this
                           computer, and (unless ?checks=0) the doctor's checks
  POST /setup/game         {"folder": path}: set the game setting (a game folder, or a folder holding one: LWR or plain
                           Enemy Within); the server then lists that install's maps, with no restart
  POST /setup/browse       a Windows folder dialog on this computer: {"folder": the folder chosen, or null}

Installs are found in Steam's libraries (its registry keys, then each library in libraryfolders.vdf): every game
folder under steamapps\\common, the lab copy marked as such.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from projects import ProjectError
from version import NAME, VERSION
from settings import (KINDS, LAB_MARKER, doctor, game_kind, game_setting, is_game, load_settings, resolve_game,
                      save_settings, settings_path)


def steam_folders():
    """Steam's own folders this computer's registry names (and the usual place), existing ones only, no repeats."""
    found = []
    if sys.platform == 'win32':
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key) as k: found.append(Path(winreg.QueryValueEx(k, value)[0]))
            except OSError: pass
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles')):
        if base: found.append(Path(base) / 'Steam')
    seen, out = set(), []
    for folder in found:
        key = os.path.normcase(os.path.abspath(folder))
        if key not in seen and folder.is_dir(): seen.add(key); out.append(folder)
    return out


def steam_libraries(steam_dirs=None):
    """Each Steam library folder: Steam's own, then those its steamapps\\libraryfolders.vdf lists."""
    libraries = []
    for steam in steam_dirs if steam_dirs is not None else steam_folders():
        libraries.append(Path(steam))
        vdf = Path(steam) / 'steamapps' / 'libraryfolders.vdf'
        try: text = vdf.read_text(encoding='utf-8', errors='replace')
        except OSError: continue
        libraries += [Path(p.replace('\\\\', '\\')) for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    seen, out = set(), []
    for folder in libraries:
        key = os.path.normcase(os.path.abspath(folder))
        if key not in seen: seen.add(key); out.append(folder)
    return out


def find_installs(steam_dirs=None):
    """The game folders in Steam's libraries: [{folder, kind, label, lab}], the lab copy last."""
    found = []
    for library in steam_libraries(steam_dirs):
        common = library / 'steamapps' / 'common'
        try: children = sorted(c for c in common.iterdir() if c.is_dir())
        except OSError: continue
        for child in children:
            if not is_game(child): continue
            lab = (child / LAB_MARKER).is_file()
            kind = game_kind(child)
            found.append(dict(folder=str(child), kind=kind, label=KINDS.get(kind, kind) + (' (the lab copy)' if lab else ''), lab=lab))
    return sorted(found, key=lambda f: f['lab'])


BROWSE = r'''
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false }
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose the XCOM: Enemy Within game folder (the one holding XEW), with Long War Rebalance or plain'
$dialog.ShowNewFolderButton = $false
if ($env:WORKSHOP_START -and (Test-Path -LiteralPath $env:WORKSHOP_START)) { $dialog.SelectedPath = $env:WORKSHOP_START }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.SelectedPath) }
'''


def browse(start=None):
    """A Windows folder dialog on this computer (Windows PowerShell, always there): the folder chosen, or None."""
    if sys.platform != 'win32': raise ProjectError(404, 'The folder dialog is Windows only: type the folder instead.')
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    env = dict(os.environ, WORKSHOP_START=str(start or ''))
    out = subprocess.run([str(powershell), '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-Command', BROWSE],
                         capture_output=True, text=True, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    folder = out.stdout.strip()
    return folder or None


class GameSetup:
    def __init__(self, configure=None, load=load_settings, save=save_settings, find=find_installs, pick=browse, guard=None):
        """configure(settings): the server lists the new install's maps (viewer.py); load/save/find/pick: settings and
        the computer's installs (tests give their own); guard(): raises ProjectError when the install can't change now
        (the build queue's, while it runs: buildqueue.py settings_guard), before anything is saved."""
        self.configure, self.load, self.save, self.find, self.pick = configure, load, save, find, pick
        self.guard = guard
        self.lock = threading.Lock()

    def status(self, checks=True):
        settings = self.load()
        setting = game_setting(settings)
        game, note = resolve_game(setting) if setting is not None else (None, 'not set')
        kind = game_kind(game) if game else None
        out = dict(name=NAME, version=VERSION, settingsFile=str(settings_path()),
                   settings={k: (None if v is None else str(v)) for k, v in settings.items() if k != 'lwr'},
                   game=dict(setting=None if setting is None else str(setting), folder=None if game is None else str(game),
                             kind=kind, label=KINDS.get(kind), note=note),
                   found=self.find())
        if checks: out['checks'] = doctor(settings)
        return out

    def choose(self, request):
        folder = request.get('folder') if isinstance(request, dict) else None
        if not isinstance(folder, str) or not folder.strip(): raise ProjectError(400, 'Send {"folder": the game folder}.')
        folder = Path(folder.strip().strip('"'))
        game, note = resolve_game(folder)
        if game is None: raise ProjectError(409, f'Not a game install: {note}.')
        with self.lock:
            if self.guard: self.guard()
            settings = self.save({'game': folder})
            if self.configure: self.configure(settings)
        return self.status(checks=False)

    def browse(self):
        settings = self.load()
        start = game_setting(settings)
        return dict(folder=self.pick(start))


def main(argv=None):
    """The installer's front end (tools/release/installer.iss runs `set`): `find` prints the installs found, as JSON; `set <folder>`
    sets the game setting and prints the install (exit 1 with {"error"} when the folder is no game install)."""
    import argparse
    import json
    ap = argparse.ArgumentParser(description='Find the game installs, or set the game setting')
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('find')
    chosen = sub.add_parser('set')
    chosen.add_argument('folder')
    args = ap.parse_args(argv)
    if args.command == 'find':
        print(json.dumps(find_installs()))
        return 0
    try:
        status = GameSetup().choose(dict(folder=args.folder))
    except ProjectError as error:
        print(json.dumps(dict(error=error.message)))
        return 1
    print(json.dumps(dict(status['game'], settingsFile=status['settingsFile'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
