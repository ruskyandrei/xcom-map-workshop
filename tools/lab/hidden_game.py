"""Runs the lab copy's game where nobody sees it and works through a list of steps: a game check without a person.

  python tools/lab/hidden_game.py --map URB_Bar --step "waitlog 240 m_bTacticalIntroDone" --step "wait 45" --step "shot start"
  python tools/lab/hidden_game.py --steps <steps file> [--map <Map> | --play-file <commands file>] [--out <folder>]

The game runs on a private Windows desktop (HiddenRun.cs), so no window, sound focus or keyboard is taken from the
user. There DirectX 9 finds no hardware and the game has no working DirectX 11 (findings register T-43), so for the run
DXVK's 32-bit d3d9.dll (DirectX 9 over Vulkan) stands beside XComEW.exe and is taken away after. GameRemote.cs starts
the game there and does the steps (its header lists them: wait, waitlog, console, type, shot, key; no mouse).

- Which game: the folder Steam runs (<Steam common>\\XCom-Enemy-Unknown) and only while it is the lab copy (its
  marker XComLab-copy.txt); --game names another lab copy. Steam must be running, the game must not be.
- Started as XComEW.exe -FROMLAUNCHER itself, with SteamAppId and SteamGameId set (F-84), -nohomedir (settings, saves
  and logs stay inside the copy), -windowed at --res, and -EXEC of a commands file when a map is asked for:
  --map writes Play in game's commands (gamelaunch.play_text: the game's own squad, --no-aliens for none),
  --play-file takes a commands file as it is. With neither the game stops at its main menu.
- DXVK: unpack a release of github.com/doitsujin/dxvk into <lab>\\dxvk (so that <lab>\\dxvk\\<version>\\x32\\d3d9.dll
  exists); the newest one there is used. A d3d9.dll already beside the game is left alone when it is that one, and
  stops the run when it is another.
- What the game writes is put back: every .ini of XEW\\XComGame\\Config that the run changed or made (`set` saves the
  class's config, F-73), the commands files, the DLL.
- Out folder (default <lab>\\hidden-runs\\<time>): the shots as <name>.png, steps.txt, Launch.log, DXVK's log,
  run.log (what GameRemote printed).
- Exit code: GameRemote's (0, 1 the game ended, 3 a waitlog or shot ran out of time), 124 when --timeout ended the
  run, 2 when the run could not start.
"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'viewer')]
import gamelaunch  # noqa: E402
import labpaths  # noqa: E402
import settings  # noqa: E402

DESKTOP = 'XComLab-Game'
PLAY_FILE = 'XComMapWorkshop-hidden.txt'
HELPERS = {'HiddenRun.exe': ('HiddenRun.cs', ()), 'GameRemote.exe': ('GameRemote.cs', ('/r:System.Drawing.dll',))}
VERBS = ('wait', 'waitlog', 'console', 'type', 'shot', 'key')


class RunError(Exception):
    pass


def check_steps(lines):
    """The steps as GameRemote will read them, or RunError naming the first line it would refuse outright (an unknown
    step or none at all); GameRemote checks each step's arguments itself before it starts the game."""
    steps = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    if not steps: raise RunError('No steps: give --step or --steps')
    for step in steps:
        if step.split()[0].lower() not in VERBS:
            raise RunError(f'Unknown step {step!r} (one of {", ".join(VERBS)})')
    return steps


def version_key(folder):
    return [int(n) for n in re.findall(r'\d+', folder.name)]


def dxvk_dll(lab):
    """The newest unpacked DXVK's 32-bit d3d9.dll under <lab>\\dxvk."""
    found = sorted((p for p in (Path(lab) / 'dxvk').glob('*/x32/d3d9.dll')), key=lambda p: version_key(p.parents[1]))
    if not found:
        raise RunError(f'No DXVK under {Path(lab) / "dxvk"}: unpack a release of github.com/doitsujin/dxvk there, '
                       'so that <version>\\x32\\d3d9.dll exists')
    return found[-1]


def win32(game):
    return Path(game) / 'XEW' / 'Binaries' / 'Win32'


def config_folder(game):
    return Path(game) / 'XEW' / 'XComGame' / 'Config'


class Prepared:
    """The lab copy made ready for a hidden run, and put back by restore(): DXVK's DLL beside the game, the commands
    file, and the config files as they were."""

    def __init__(self, game, dll, play_text=None):
        self.game, self.placed, self.play = Path(game), None, None
        if not (self.game / settings.LAB_MARKER).is_file():
            raise RunError(f'{self.game} is not the lab copy (no {settings.LAB_MARKER}): hidden runs are for the lab copy')
        if not (win32(self.game) / 'XComEW.exe').is_file():
            raise RunError(f'No XComEW.exe in {win32(self.game)}')
        target = win32(self.game) / 'd3d9.dll'
        if target.exists():
            if target.read_bytes() != Path(dll).read_bytes():
                raise RunError(f'{target} is another d3d9.dll than {dll}: take it away first')
        else:
            shutil.copyfile(dll, target)
            self.placed = target
        folder = config_folder(self.game)
        self.config = {p: p.read_bytes() for p in folder.glob('*.ini')} if folder.is_dir() else {}
        if play_text is not None:
            self.play = self.game / 'XEW' / 'Binaries' / PLAY_FILE
            self.play.write_bytes(play_text.replace('\n', '\r\n').encode('ascii'))

    def restore(self):
        """Puts everything back; returns the names of the config files the run changed or made."""
        changed = []
        folder = config_folder(self.game)
        for path in (sorted(folder.glob('*.ini')) if folder.is_dir() else []):
            if path not in self.config:
                path.unlink(); changed.append(path.name)
            elif path.read_bytes() != self.config[path]:
                path.write_bytes(self.config[path]); changed.append(path.name)
        for path in self.config:
            if not path.exists():
                path.write_bytes(self.config[path]); changed.append(path.name)
        binaries = self.game / 'XEW' / 'Binaries'
        for path in binaries.glob('XComMapWorkshop-hidden*.txt'): path.unlink()
        if self.placed and self.placed.exists(): self.placed.unlink()
        return changed


def game_arguments(res, play_file=None):
    width, height = res
    out = ['-FROMLAUNCHER']
    if play_file: out.append(f'-EXEC={play_file}')
    return out + ['-nostartupmovies', '-nohomedir', '-forcelogflush', '-windowed', f'-ResX={width}', f'-ResY={height}']


def running(name):
    out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {name}', '/NH', '/FO', 'CSV'], capture_output=True, text=True).stdout
    return name.lower() in out.lower()


def csc():
    path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319' / 'csc.exe'
    if not path.is_file(): raise RunError(f'No C# compiler at {path}')
    return path


def helper(lab, name):
    """<lab>\\bin\\<name>, compiled when it is missing or older than its source."""
    source, extra = HELPERS[name]
    exe, src = Path(lab) / 'bin' / name, HERE / source
    if not exe.is_file() or exe.stat().st_mtime < src.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        done = subprocess.run([str(csc()), '/nologo', '/target:exe', '/platform:anycpu', *extra, f'/out:{exe}', str(src)],
                              capture_output=True, text=True)
        if done.returncode: raise RunError(f'Could not compile {src}:\n{done.stdout}{done.stderr}')
    return exe


def run(game, lab, steps, out, play_text=None, res=(1280, 720), timeout=900, echo=print):
    """One hidden run; returns (exit code, the config files put back). Raises RunError when it can't start."""
    steps = check_steps(steps)
    if not running('steam.exe'): raise RunError('Steam is not running: the game ends at once without it')
    if running('XComEW.exe'): raise RunError('The game is running: close it first')
    hidden_run, remote = helper(lab, 'HiddenRun.exe'), helper(lab, 'GameRemote.exe')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    steps_file = out / 'steps.txt'
    steps_file.write_text('\n'.join(steps) + '\n', encoding='utf-8', newline='\n')
    log = Path(game) / 'XEW' / 'XComGame' / 'Logs' / 'Launch.log'
    prepared = Prepared(game, dxvk_dll(lab), play_text)
    try:
        cmd = [str(hidden_run), '--desktop', DESKTOP, '--timeout', str(timeout), '--', str(remote),
               str(win32(game) / 'XComEW.exe'), str(steps_file), str(out), str(log),
               *game_arguments(res, PLAY_FILE if play_text is not None else None)]
        env = dict(os.environ, SteamAppId=gamelaunch.APP_ID, SteamGameId=gamelaunch.APP_ID, DXVK_LOG_PATH=str(out))
        lines = []
        with subprocess.Popen(cmd, cwd=win32(game), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace') as proc:
            for line in proc.stdout:
                line = line.rstrip('\n')
                lines.append(line)
                # the game's own chatter goes to run.log only; GameRemote's lines start with its clock
                if line.startswith('[') or line.startswith('HiddenRun'): echo(line)
            code = proc.wait()
        (out / 'run.log').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    finally:
        changed = prepared.restore()
    if log.is_file(): shutil.copyfile(log, out / 'Launch.log')
    return code, changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--map', help='start a battle on this map (Play in game\'s commands, the game\'s own squad)')
    ap.add_argument('--no-aliens', action='store_true', help='with --map: a battle without aliens')
    ap.add_argument('--play-file', type=Path, help='a commands file to start with, as it is, instead of --map')
    ap.add_argument('--step', action='append', default=[], help='a step (GameRemote.cs lists them); may be repeated')
    ap.add_argument('--steps', type=Path, help='a file of steps, one a line, done before any --step')
    ap.add_argument('--out', type=Path, help='the folder for shots and logs (default <lab>\\hidden-runs\\<time>)')
    ap.add_argument('--res', default='1280x720', help='the size the game renders at (default 1280x720)')
    ap.add_argument('--timeout', type=int, default=900, help='seconds after which the run is ended (default 900)')
    ap.add_argument('--game', type=Path, help='the lab copy (default: the folder Steam runs)')
    args = ap.parse_args(argv)
    try:
        if args.map and args.play_file: raise RunError('Give --map or --play-file, not both')
        size = re.fullmatch(r'(\d{3,5})x(\d{3,5})', args.res)
        if not size: raise RunError(f'{args.res!r} is not a size such as 1280x720')
        lines = (args.steps.read_text(encoding='utf-8').splitlines() if args.steps else []) + args.step
        play = None
        if args.map: play = gamelaunch.play_text(args.map, aliens=not args.no_aliens)
        elif args.play_file: play = args.play_file.read_text(encoding='ascii')
        lab = labpaths.lab_root()
        game = args.game or labpaths.active_game()
        out = args.out or Path(lab) / 'hidden-runs' / datetime.now().strftime('%Y%m%d-%H%M%S')
        code, changed = run(game, lab, lines, out, play, (int(size[1]), int(size[2])), args.timeout)
    except (RunError, gamelaunch.LaunchError, ValueError, OSError) as error:
        print(f'FAIL: {error}')
        return 2
    if changed: print('put back: ' + ', '.join(changed))
    if code == 124: print(f'FAIL: the run did not finish in {args.timeout} s and was ended')
    print(f'{"done" if code == 0 else f"FAIL (exit {code})"}: {out}')
    return code


if __name__ == '__main__':
    sys.exit(main())
