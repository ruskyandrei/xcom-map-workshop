"""Runs the lab copy's game where nobody sees it and works through a list of steps: a game check without a person.

  python tools/lab/hidden_game.py --map URB_Bar --step "waitlog 240 m_bTacticalIntroDone" --step "wait 45" --step "shot start"
  python tools/lab/hidden_game.py --steps <steps file> [--map <Map> | --play-file <commands file>] [--out <folder>]
  python tools/lab/hidden_game.py --map URB_Bar --out <folder> --step "waitlog 240 m_bTacticalIntroDone" --serve 600
  python tools/lab/hidden_game.py send <folder> "console getall XComHumanPawn Location" "shot now"

The game runs on a private Windows desktop (HiddenRun.cs), so no window, sound focus or keyboard is taken from the
user. There DirectX 9 finds no hardware and the game has no working DirectX 11 (findings register T-43), so for the run
DXVK's 32-bit d3d9.dll (DirectX 9 over Vulkan) stands beside XComEW.exe and is taken away after. GameRemote.cs starts
the game there and does the steps (its header lists them: wait, waitlog, console, type, shot, key; no mouse).

- Which game: the folder Steam runs (<Steam common>\\XCom-Enemy-Unknown) and only while it is the lab copy (its
  marker XComLab-copy.txt); --game names another lab copy. Steam must be running, the game must not be.
- Started as XComEW.exe -FROMLAUNCHER itself, with SteamAppId and SteamGameId set (F-84), -nohomedir (settings, saves
  and logs stay inside the copy), -windowed at --res, and -EXEC of a commands file when a map is asked for:
  --map writes Play in game's commands (gamelaunch.play_text; --squad <file> for the squad, without it the game's
  own, whose soldiers stand but can't walk; --no-aliens for none),
  --play-file takes a commands file as it is. With neither the game stops at its main menu.
- DXVK: unpack a release of github.com/doitsujin/dxvk into <lab>\\dxvk (so that <lab>\\dxvk\\<version>\\x32\\d3d9.dll
  exists); the newest one there is used. A d3d9.dll already beside the game is left alone when it is that one, and
  stops the run when it is another.
- What the game writes is put back: every .ini of XEW\\XComGame\\Config that the run changed or made (`set` saves the
  class's config, F-73), the commands files, the DLL.
- A session: --serve <idle seconds> keeps the game running after the steps and takes more from `send`, which hands
  its steps to the run with that out folder, waits until they are done and prints what the game's log gained
  meanwhile (a console command's answer, `getall` lines), so a later step can go by an earlier one's answer. The run
  ends at `send <folder> quit`, or after <idle seconds> without a send. Start it in the background.
- Playing in a session, without a mouse (the game takes none on a private desktop):
    hidden_game.py goto <folder> <x> <y>            the active soldier walks to that tile (world units, 96 a tile)
    hidden_game.py aim <folder> <x> <y> [steps...]   the game's 3D cursor on that tile, the steps done there (a
                                                     console command that works at the cursor: DropSectoid,
                                                     TeleportToCursor), the camera put back
  Both turn the camera straight down on the active soldier with a field of view and a yaw that put the picture's
  top left corner, where the game's mouse stands, over the tile; goto then runs the game's own right-click
  functions. --floor <n> first sets the storey the cursor picks on (the mouse wheel's count): 0 is the ground and
  the inside of a building with its roof cut away, a roof or an upper storey needs a higher one (URB_Bar's roof: 3),
  and a move there takes the ladder or stairs by itself. A tile nobody can stand on (a table, a counter) gives no
  path and goto says he did not move; after a move the game goes on to the next soldier, and one without moves left
  is no longer in Tab's round. A shot goes by its ability key and Enter (`key 1`, `key RETURN`), the next soldier by `key TAB`, the
  turn's end by `console EndTurn`. A grenade's aim follows the same corner while its view is open: set the camera by
  hand then (aim_camera gives the field of view and yaw). What a soldier sees and his cover come back from `getall`
  (XGUnit m_bInCover, m_iCurrentCoverValue, Location).
- Sounds: `hidden_game.py listen <folder> <x> <y> <z> [--distance <d>]` puts the camera <d> world units from that
  place and prints the game's own list of what it is playing (ListWaves: volume, wave, the actor it belongs to).
  The game hears from the camera, so whether an ambient sound is heard goes by the camera's distance from it and
  the sound's radii (getall SoundNodeAmbient RadiusMin / RadiusMax / SoundSlots).
- No sound comes out: GameRemote mutes the game's audio session in Windows for the run and unmutes it before the
  game ends (Windows keeps an application's mute for its next start). The game still plays its sounds, so `listen`
  works. XCOM_HIDDEN_SOUND=1 in the environment leaves the sound on.
- Out folder (default <lab>\\hidden-runs\\<time>): the shots as <name>.png, steps.txt, Launch.log, DXVK's log,
  run.log (what GameRemote printed).
- Exit code: GameRemote's (0, 1 the game ended, 3 a waitlog or shot ran out of time), 124 when --timeout ended the
  run, 2 when the run could not start.
"""
import argparse
import math
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'viewer')]
import gamelaunch  # noqa: E402
import labpaths  # noqa: E402
import settings  # noqa: E402

DESKTOP = 'XComLab-Game'
PLAY_FILE = 'XComMapWorkshop-hidden.txt'
HELPERS = {'HiddenRun.exe': ('HiddenRun.cs', ()), 'GameRemote.exe': ('GameRemote.cs', ('/r:System.Drawing.dll',))}
VERBS = ('wait', 'waitlog', 'console', 'type', 'shot', 'key', 'serve', 'quit')


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
        for path in list(binaries.glob('XComMapWorkshop-hidden*.txt')) + list(binaries.glob('xmwh*.txt')): path.unlink()
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


LOG_LINE = re.compile(r'^\[[\d.]+\] (Log|ExecWarning|Warning|ScriptLog|Error|Cmd): ')


def log_gain(text):
    """The lines of a piece of the game's log that answer a console command: its Log, warning and error lines,
    without the script warnings' call stacks and the note that a commands file ran."""
    return [line for line in text.splitlines() if LOG_LINE.match(line) and 'Execing ' not in line]


def send(out, steps, log, wait=300, echo=print):
    """Hands steps to the serving run of `out` and waits for them; returns 0 when they were done, 3 when the run
    said one failed, 1 when no answer came in `wait` seconds (no run serving there)."""
    steps = check_steps(steps)
    inbox = Path(out) / 'inbox'
    if not inbox.is_dir(): raise RunError(f'No run is serving {out} (no inbox there yet)')
    start = Path(log).stat().st_size if Path(log).is_file() else 0
    name = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    part = inbox / (name + '.part')
    part.write_text('\n'.join(steps) + '\n', encoding='utf-8', newline='\n')
    part.rename(inbox / (name + '.txt'))
    done, until = inbox / (name + '.done'), time.monotonic() + wait
    while not done.is_file():
        if time.monotonic() > until:
            echo(f'FAIL: no answer in {wait} s; is the run still going?')
            return 1
        time.sleep(0.2)
    result = done.read_text(encoding='utf-8').strip()
    done.unlink()
    if Path(log).is_file():
        with open(log, 'rb') as stream:
            stream.seek(start)
            for line in log_gain(stream.read().decode('utf-8', errors='replace')): echo(line)
    echo(result)
    return 0 if result == 'ok' else 3


# Pointing without a mouse (findings register T-43). On a private desktop the game's mouse stands at the top left
# corner of the picture, and the tile under that corner is where its 3D cursor is. Looking straight down at the
# active soldier, that corner's tile is a fixed way from him: its distance goes by the field of view, its direction
# by the camera's yaw. So a field of view and a yaw put the cursor on any tile, and the game's own right-click
# functions order the move there.
AIM_DISTANCE, AIM_PITCH = 1256, -89     # the camera of the game's F2 preset: straight down
AIM_REACH = 1440.0      # world units from the view's centre to the corner's tile, per unit of tan(field of view / 2)
AIM_ANGLE = 72.0        # the direction of that tile from the centre (degrees, atan2(y, x)) less the camera's yaw
PLAY_CAMERA = 'SetOverheadCameraParameters 70 1256 -45'      # the game's F4 preset, put back after aiming
VECTOR = re.compile(r'\(X=(-?[\d.]+),Y=(-?[\d.]+),Z=(-?[\d.]+)\)')
TILE = 96


def aim_camera(unit, target):
    """(field of view, yaw) that put the picture's top left corner over `target`, looking down at `unit` (x, y)."""
    dx, dy = target[0] - unit[0], target[1] - unit[1]
    reach = math.hypot(dx, dy)
    if reach < TILE / 2: raise RunError('The target is the tile the soldier stands on')
    fov = 2 * math.degrees(math.atan(reach / AIM_REACH))
    if fov > 150: raise RunError(f'The target is {reach / TILE:.0f} tiles away, too far to point at')
    return fov, (math.degrees(math.atan2(dy, dx)) - AIM_ANGLE) % 360


def ask(out, log, steps, wait=120):
    """send() without printing; the log lines it gained. RunError when the steps were not done."""
    lines = []
    if send(out, steps, log, wait, lines.append) != 0: raise RunError(lines[-1] if lines else 'no answer')
    return lines[:-1]


def vectors(lines, prop='Location'):
    """{object name: (x, y, z)} of getall's lines for a vector property."""
    out = {}
    for line in lines:
        found = re.search(r'\) \S+ \S*?([A-Za-z0-9_]+)\.' + prop + ' = ', line)
        vector = VECTOR.search(line)
        if found and vector: out[found[1]] = tuple(float(n) for n in vector.groups())
    return out


def active_unit(out, log):
    """(name, (x, y, z)) of the soldier whose turn it is."""
    lines = ask(out, log, ['console getall XComTacticalController m_kActiveUnit | getall XGUnit Location'])
    named = next((re.search(r"m_kActiveUnit = XGUnit'\S*?(XGUnit_\d+)'", line) for line in lines if 'm_kActiveUnit' in line), None)
    places = vectors(lines)
    if not named or named[1] not in places: raise RunError('No soldier is active (is it the squad\'s turn?)')
    return named[1], places[named[1]]


def on_tile(a, b):
    return abs(a[0] - b[0]) < TILE / 2 and abs(a[1] - b[1]) < TILE / 2


def aim(out, log, target, echo=print):
    """Puts the game's 3D cursor on the tile of `target` (x, y in world units) and leaves the camera so; returns the
    cursor's place. The cursor is read back and the aim corrected, up to three times: a roof or a prop under the
    corner moves the tile it picks."""
    name, unit = active_unit(out, log)
    point = target
    for _ in range(6):
        fov, yaw = aim_camera(unit, point)
        ask(out, log, [f'console SetOverheadCameraParameters {fov:.2f} {AIM_DISTANCE} {AIM_PITCH} | SetCameraYaw {yaw:.2f}'])
        cursor = None
        for _ in range(10):         # the camera turns over a second or two: wait until the cursor stays
            lines = ask(out, log, ['wait 1', 'console getall XCom3DCursor Location'])
            before, cursor = cursor, next(iter(vectors(lines).values()), None)
            if cursor is None: raise RunError('The cursor\'s place did not come back')
            if before and math.dist(before, cursor) < 1: break
        if on_tile(cursor, target):
            echo(f'{name} at {unit[0]:.0f},{unit[1]:.0f}; cursor on {cursor[0]:.0f},{cursor[1]:.0f},{cursor[2]:.0f}')
            return name, unit, cursor
        point = (point[0] + target[0] - cursor[0], point[1] + target[1] - cursor[1])
    ask(out, log, ['console ' + PLAY_CAMERA])
    raise RunError(f'The cursor lands on {cursor[0]:.0f},{cursor[1]:.0f}, not on {target[0]:.0f},{target[1]:.0f}')


def goto(out, log, target, wait=40, echo=print):
    """Orders the active soldier to the tile of `target` and waits until he stands; 0 when he is there, else 3."""
    name, start, _ = aim(out, log, target, echo)
    # press and release in two frames: the game counts a right click by the time the button was down
    ask(out, log, ['console Right_Mouse_Button_Press', 'console Right_Mouse_Button_Release'])
    last, until = None, time.monotonic() + wait
    while True:
        lines = ask(out, log, ['wait 1.5', 'console getall XGUnit Location'])
        here = vectors(lines).get(name)
        for line in lines:
            if 'Combat Log Message' in line: echo(re.sub(r'<[^>]+>', '', line.split('Combat Log Message: ', 1)[1]))
        if here and last and on_tile(here, last) and math.dist(here, last) < 1: break
        if time.monotonic() > until: break
        last = here
    ask(out, log, ['console ' + PLAY_CAMERA])
    arrived = bool(here) and on_tile(here, target)
    echo(f'{name} {"stands on" if arrived else "is at"} {here[0]:.0f},{here[1]:.0f},{here[2]:.0f}'
         + ('' if arrived else f', not on {target[0]:.0f},{target[1]:.0f}' + (' (he did not move)' if on_tile(here, start) else '')))
    return 0 if arrived else 3


def set_floor(out, log, floor, echo=print):
    """Sets the storey the game's cursor picks on: 0 the ground (and the inside of a building, its roof cut away),
    higher ones the storeys and roofs above. It is the mouse wheel's count (m_iRequestedFloor), one notch a frame,
    and it stays until it is set again."""
    for _ in range(8):
        lines = ask(out, log, ['console getall XCom3DCursor m_iRequestedFloor'])
        found = next((re.search(r'm_iRequestedFloor = (-?\d+)', line) for line in lines if 'm_iRequestedFloor' in line), None)
        if not found: raise RunError('The cursor\'s floor did not come back')
        now = int(found[1])
        if now == floor:
            echo(f'cursor floor {now}')
            return
        ask(out, log, ['console ' + ('Mouse_Scroll_Up' if now < floor else 'Mouse_Scroll_Down'), 'wait 1'])
    raise RunError(f'The cursor\'s floor stays at {now}, not {floor} (the map has no such storey here?)')


WAVE = re.compile(r'Log:\s+\d+\.\s+(Yes|No)\s+[\d.]+\s+([\d.]+)\s+(\S+)\s+(\S+)\s*$')


def waves(lines):
    """[(volume, wave, owner)] of ListWaves' lines: the sounds the game is playing now."""
    return [(float(m[2]), m[3], m[4]) for m in map(WAVE.search, lines) if m]


def listen(out, log, place, distance=None, echo=print):
    """What the game plays with the camera looking at `place` (x, y, z) from `distance` world units (default: the
    play camera's 1256): [(volume, wave, owner)], loudest first. The game hears from the camera itself, not from
    the place it looks at, so an ambient sound with a reach shorter than the distance is not heard."""
    x, y, z = place
    camera = PLAY_CAMERA if distance is None else f'SetOverheadCameraParameters 70 {distance:g} -45'
    lines = ask(out, log, [f'console ViewLocation {x:g} {y:g} {z:g} | {camera}', 'wait 5', 'console ListWaves',
                           'console RemoveLookAt | ' + PLAY_CAMERA])
    heard = sorted(waves(lines), reverse=True)
    if not any('Total:' in line for line in lines): raise RunError('ListWaves did not answer')
    for volume, wave, owner in heard: echo(f'{volume:.2f}  {wave}  ({owner})')
    echo(f'{len(heard)} sounds playing')
    return heard


def session_command(argv):
    """send, aim and goto: the commands that talk to a serving run."""
    verb = argv[0]
    ap = argparse.ArgumentParser(prog=f'hidden_game.py {verb}')
    ap.add_argument('out', type=Path, help="the serving run's out folder")
    if verb == 'send':
        ap.description = 'Hand steps to a serving run and wait for them.'
        ap.add_argument('steps', nargs='+', help='the steps (GameRemote.cs lists them)')
    elif verb == 'listen':
        ap.description = 'List the sounds the game plays with the camera looking at a place.'
        ap.add_argument('x', type=float, help='the place the camera looks at, in world units')
        ap.add_argument('y', type=float)
        ap.add_argument('z', type=float)
        ap.add_argument('--distance', type=float, help='how far the camera is from the place (default 1256, the '
                        'play camera; the game hears from the camera)')
    else:
        ap.description = ('Order the active soldier to a tile and wait until he stands there.' if verb == 'goto' else
                          'Put the game\'s 3D cursor on a tile (for a console command that works at the cursor), do '
                          'the steps, and put the camera back.')
        ap.add_argument('x', type=float, help='the tile\'s place in world units (a tile is 96 wide)')
        ap.add_argument('y', type=float)
        if verb == 'aim': ap.add_argument('steps', nargs='*', help='steps to do while the cursor is there')
        ap.add_argument('--floor', type=int, help='the storey to pick on first: 0 the ground and the inside of a '
                        'building, higher ones the storeys and roofs above (it stays set)')
    ap.add_argument('--game', type=Path, help='the lab copy (default: the folder Steam runs)')
    ap.add_argument('--wait', type=int, default=300 if verb == 'send' else 40, help='seconds to wait')
    args = ap.parse_args(argv[1:])
    try:
        log = Path(args.game or labpaths.active_game()) / 'XEW' / 'XComGame' / 'Logs' / 'Launch.log'
        if verb == 'send': return send(args.out, args.steps, log, args.wait)
        if verb == 'listen':
            listen(args.out, log, (args.x, args.y, args.z), args.distance)
            return 0
        if getattr(args, 'floor', None) is not None: set_floor(args.out, log, args.floor)
        if verb == 'goto': return goto(args.out, log, (args.x, args.y), args.wait)
        aim(args.out, log, (args.x, args.y))
        code = send(args.out, args.steps, log, 300) if args.steps else 0
        ask(args.out, log, ['console ' + PLAY_CAMERA])
        return code
    except (RunError, ValueError, OSError) as error:
        print(f'FAIL: {error}')
        return 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] in (['send'], ['aim'], ['goto'], ['listen']): return session_command(argv)
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--map', help='start a battle on this map (Play in game\'s commands, the game\'s own squad)')
    ap.add_argument('--squad', type=Path, help='with --map: a file holding the squad to land, the value of m_aSoldiers '
                    '(squadrecords.squad_text; tools/viewer/tests/squad_default_lwr.txt is the default test squad '
                    "for LWR). The game's own squad for this path can't walk (T-43)")
    ap.add_argument('--no-aliens', action='store_true', help='with --map: a battle without aliens')
    ap.add_argument('--play-file', type=Path, help='a commands file to start with, as it is, instead of --map')
    ap.add_argument('--step', action='append', default=[], help='a step (GameRemote.cs lists them); may be repeated')
    ap.add_argument('--steps', type=Path, help='a file of steps, one a line, done before any --step')
    ap.add_argument('--serve', type=int, metavar='IDLE', help='after the steps, take more from `send` until a quit '
                    'step or IDLE seconds without one')
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
        if args.serve: lines.append(f'serve {args.serve}')
        play = None
        squad = args.squad.read_text(encoding='ascii').strip() if args.squad else None
        if args.map: play = gamelaunch.play_text(args.map, squad=squad, aliens=not args.no_aliens)
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
