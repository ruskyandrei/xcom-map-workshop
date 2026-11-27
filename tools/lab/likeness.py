"""Track H of the game-likeness plan: the same places shot in the game and in the editor, put side by side and
scored, so that "closer to the game" is a number and a picture. A lab tool: not shipped, and no test fails on a score.

The shot list is likeness_shots.json beside this: for each of four maps three cameras, each the game's overhead
camera (what it looks at, its yaw, pitch and distance, its field of view across the picture's width).

  python -B tools/lab/likeness.py steps <map>
      the hidden run's steps that take the game's shots of a map (for hidden_game.py send, one shot a camera)
  python -B tools/lab/likeness.py editor --stage <stage> [--look neutral] [--maps <map> ...] [--port 8794]
      [--cache <cache>] [--flag <url flag> ...]
      the editor's shots: a test server on the cache, the page in Edge (Playwright), the same cameras
  python -B tools/lab/likeness.py sheet --stage <stage> [--look neutral]
      a sheet a map of the game's shots beside the editor's
  python -B tools/lab/likeness.py overlay <game.png> <editor.png> <out.png>
      the two pictures' edges laid over each other (a camera's check: a building's edges line up)
  python -B tools/lab/likeness.py score --stage <stage> [--look neutral] [--note <words>]
      the scores: scores.json beside the shots and rows of the plan's progress file

The game's shots are in <shots>/game/<id>.png (the reference, taken once), the editor's in
<shots>/<stage>/<look>/<id>.png; <shots> is private/shots/likeness unless --shots names another folder.

The score: both pictures blurred and shrunk to a grid of 32 by 18 cells, each cell's colour in CIELAB, and the mean
difference over the cells (CIE76), with its lightness part (the mean |dL|) and its hue part (the mean of the a, b
plane's distance) apart. It measures light, hue and fog, not detail. A shot list's `mask` (rectangles in fractions
of the picture: x0, y0, x1, y1) leaves out the cells under the game's interface.
"""
import argparse
import base64
import datetime
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHOTS_FILE = HERE / 'likeness_shots.json'
SHOTS = REPO / 'private' / 'shots' / 'likeness'
PROGRESS = REPO / 'private' / 'plans' / 'todo' / 'game-likeness-progress.md'
GRID = (32, 18)
LOOKS = ('neutral', 'map', 'map-no-area', 'game')


def shot_list(path=SHOTS_FILE):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def cameras(plan, maps=None):
    """[(map, camera)] of the shot list, in its order, for the maps named (all by default)."""
    out = []
    for name, shots in plan['maps'].items():
        if maps and name not in maps:
            continue
        out += [(name, shot) for shot in shots]
    return out


# ---------------------------------------------------------------------------------------------------------------
# The camera

def camera_place(shot, model=None):
    """The camera's place in game units (x, y, z up) for a shot: it stands `distance` back from the target along its
    view, which points by yaw (from +x toward +y) and pitch (negative looks down)."""
    yaw = math.radians(shot['yaw'] + (model or {}).get('yawOffset', 0))
    pitch = math.radians(shot['pitch'])
    look = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    t = shot['target']
    return [t[k] - shot['distance'] * look[k] for k in range(3)]


def vertical_fov(fov, size, model=None):
    """The field of view up the picture (three.js's), from the game's (across its width unless the model says
    otherwise)."""
    if (model or {}).get('fovAcross', 'width') == 'height':
        return fov
    w, h = size
    return math.degrees(2 * math.atan(math.tan(math.radians(fov) / 2) * h / w))


def game_steps(shots, hud=None):
    """hidden_game.py steps that take each shot of a map: the interface hidden (UIToggleVisibility) and the fog of war
    lifted (ToggleFOW toggles: once a run), then each camera put by console, a wait for its move and the textures,
    the game's own picture. Measured on 27 November 2026 (H1): the commands don't fight in this order."""
    steps = ['console ' + (hud or 'UIToggleVisibility'), 'console ToggleFOW']
    for shot in shots:
        x, y, z = shot['target']
        steps += ['console SetOverheadCameraParameters %g %g %g | SetCameraYaw %g'
                  % (shot['fov'], shot['distance'], shot['pitch'], shot['yaw']),
                  'console ViewLocation %g %g %g' % (x, y, z), 'wait 5', 'shot %s' % shot['id']]
    steps.append('console RemoveLookAt')
    return steps


# ---------------------------------------------------------------------------------------------------------------
# The editor's shots

SET_CAMERA = """([target, place, fov, size]) => {
  const v = window.viewer;
  v.select(null);
  v.controls.target.set(target[0], target[2], target[1]);
  v.camera.position.set(place[0], place[2], place[1]);
  v.camera.fov = fov; v.camera.aspect = size[0] / size[1];
  v.camera.updateProjectionMatrix(); v.controls.update();
}"""

# Members put over the map's atmosphere: a new atmosphere object (the Game look's frame works its values out again for
# a new one), the map's world settings with the members over them, and the look applied again (the fog's uniforms).
ATMOSPHERE = """over => {
  const v = window.viewer, a = v.data.atmosphere ?? { world: { fog: {}, postProcess: {} }, volumes: [] };
  v.data.atmosphere = { ...a, world: { ...a.world, fog: { ...a.world.fog, ...(over.fog ?? {}) },
                                       postProcess: { ...a.world.postProcess, ...(over.postProcess ?? {}) } } };
  v.setLook(document.getElementById('lighting').value === 'game' ? 'game' : 'neutral');
}"""

# The view taken at the shot's size without the editor's helpers (the page's grabView), then the renderer put back.
GRAB = """([target, place, fov, size]) => {
  const v = window.viewer, r = v.renderer;
  const w0 = r.domElement.width, h0 = r.domElement.height, ratio = r.getPixelRatio();
  const aspect0 = v.camera.aspect, fov0 = v.camera.fov;
  r.setPixelRatio(1); r.setSize(size[0], size[1], false);
  v.controls.target.set(target[0], target[2], target[1]);
  v.camera.position.set(place[0], place[2], place[1]);
  v.camera.fov = fov; v.camera.aspect = size[0] / size[1];
  v.camera.updateProjectionMatrix(); v.controls.update(); v.camera.updateMatrixWorld(true);
  try { return v.grabView(); }
  finally { r.setPixelRatio(ratio); r.setSize(w0 / ratio, h0 / ratio, false); v.camera.aspect = aspect0; v.camera.fov = fov0; v.camera.updateProjectionMatrix(); }
}"""


def wait_for(url, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            with urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise SystemExit('the test server did not answer at %s' % url)


def editor_shots(args):
    plan = shot_list(args.shots_file)
    size, model = plan['size'], plan.get('model')
    if not 8790 <= args.port <= 8799:
        raise SystemExit('use a test port, 8790 to 8799')
    out_dir = args.shots / args.stage / args.look
    out_dir.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='likeness-') as scratch:
        scratch = Path(scratch)
        for name in ('projects', 'prefabs', 'builds'):
            (scratch / name).mkdir()
        command = [sys.executable, '-B', str(REPO / 'tools' / 'viewer' / 'viewer.py'), 'serve',
                   *([args.cache] if args.cache else []), '--port', str(args.port), '--no-open',
                   '--projects', str(scratch / 'projects'), '--prefabs', str(scratch / 'prefabs'),
                   '--builds', str(scratch / 'builds'), '--dry-play']
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = 'http://127.0.0.1:%d/' % args.port
            wait_for(base + 'maps.json')
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=not args.headed)
                page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
                by_map = {}
                for name, shot in cameras(plan, args.maps):
                    by_map.setdefault(name, []).append(shot)
                for name, shots in by_map.items():
                    flags = ''.join('&' + f for f in args.flag)
                    page.goto(base + '?map=' + name + flags)
                    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && "
                                           "window.viewer.roots.size > 0", timeout=900000)
                    page.wait_for_timeout(1500)
                    page.keyboard.press('Escape')
                    # the look: game or neutral; map and map-no-area, the Game look with and without its area
                    # lights (the lighting modes' names before the look, G1)
                    page.evaluate("""m => { const area = document.getElementById('areaLights');
                      if (area) area.checked = m !== 'map-no-area';
                      if (viewer.setLook) viewer.setLook(m === 'neutral' ? 'neutral' : 'game');
                      else document.querySelector(`#lighting button[data-value="${m}"]`)?.click(); }""", args.look)
                    # members over the map's own atmosphere (as a project's would be, before the page has controls for
                    # it): the map's world settings with them over, the look applied again
                    if args.atmosphere:
                        page.evaluate(ATMOSPHERE, json.loads(Path(args.atmosphere).read_text(encoding='utf-8')))
                    # (the Game look's frame waits for its shaders: game-likeness plan, C3)
                    page.wait_for_function("!window.viewer.post || document.getElementById('lighting').value !== 'game'"
                                           " || window.viewer.post.ready()", timeout=300000)
                    for shot in shots:
                        # the floors control: the game cuts the roofs away near what the camera looks at, so the
                        # ground floor with the floors and roofs above it cut ("1") unless the shot says otherwise
                        floor = page.locator('#floor button[data-value="%s"]' % shot.get('floor', plan.get('floor', '1')))
                        if floor.count() and 'on' not in (floor.first.get_attribute('class') or ''):
                            floor.first.click()
                        values = [shot['target'], camera_place(shot, model),
                                  vertical_fov(shot['fov'], size, model), size]
                        page.evaluate(SET_CAMERA, values)
                        page.wait_for_timeout(args.settle * 1000)   # the textures of what comes into view
                        url = page.evaluate(GRAB, values)
                        if not url:
                            raise SystemExit('the page gave no picture for %s' % shot['id'])
                        path = out_dir / ('%s.png' % shot['id'])
                        path.write_bytes(base64.b64decode(url.split(',', 1)[1]))
                        print(path)
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()


# ---------------------------------------------------------------------------------------------------------------
# Sheets, overlays and scores

def load(path, size=None):
    from PIL import Image
    picture = Image.open(path).convert('RGB')
    if size and tuple(picture.size) != tuple(size):
        raise ValueError('%s is %d by %d, not %d by %d' % (path, *picture.size, *size))
    return picture


def sheet(args):
    from PIL import Image, ImageDraw
    plan = shot_list(args.shots_file)
    w, h = plan['size']
    half = (w // 2, h // 2)
    by_map = {}
    for name, shot in cameras(plan, args.maps):
        by_map.setdefault(name, []).append(shot)
    for name, shots in by_map.items():
        canvas = Image.new('RGB', (2 * half[0] + 30, len(shots) * (half[1] + 24) + 6), (24, 26, 30))
        draw = ImageDraw.Draw(canvas)
        for row, shot in enumerate(shots):
            y = 6 + row * (half[1] + 24)
            for col, path in enumerate((args.shots / 'game' / ('%s.png' % shot['id']),
                                        args.shots / args.stage / args.look / ('%s.png' % shot['id']))):
                x = 10 + col * (half[0] + 10)
                draw.text((x, y), '%s  %s' % (shot['id'], 'game' if col == 0 else '%s, %s' % (args.stage, args.look)),
                          fill=(230, 230, 230))
                if path.exists():
                    canvas.paste(load(path).resize(half), (x, y + 16))
                else:
                    draw.text((x + 20, y + 60), 'no picture: ' + path.name, fill=(240, 120, 120))
        out = args.shots / args.stage / ('sheet-%s-%s.png' % (args.look, name))
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out)
        print(out)


def overlay(game_path, editor_path, out_path):
    """The game's edges in red over the editor's in cyan, on a dim mix of the two."""
    import numpy as np
    from PIL import Image, ImageFilter
    a, b = load(game_path), load(editor_path)
    if a.size != b.size:
        b = b.resize(a.size)
    edges = [np.asarray(p.convert('L').filter(ImageFilter.FIND_EDGES), dtype=np.float32) for p in (a, b)]
    mix = (np.asarray(a, dtype=np.float32) + np.asarray(b, dtype=np.float32)) * 0.2
    mix[..., 0] += np.clip(edges[0] * 3, 0, 255)
    mix[..., 1] += np.clip(edges[1] * 3, 0, 255)
    mix[..., 2] += np.clip(edges[1] * 3, 0, 255)
    Image.fromarray(np.clip(mix, 0, 255).astype(np.uint8)).save(out_path)


def lab_cells(picture, mask=None):
    """The picture's 32 by 18 cells in CIELAB (D65), and a flag a cell for those left out by `mask`."""
    import numpy as np
    from PIL import ImageFilter
    w, h = picture.size
    blurred = picture.filter(ImageFilter.GaussianBlur(radius=max(w / GRID[0], h / GRID[1]) / 2))
    from PIL import Image
    small = np.asarray(blurred.resize(GRID, Image.BOX), dtype=np.float64) / 255.0
    linear = np.where(small <= 0.04045, small / 12.92, ((small + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = linear @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    lab = np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)
    keep = np.ones(GRID[::-1], dtype=bool)
    for x0, y0, x1, y1 in mask or ():
        for j in range(GRID[1]):
            for i in range(GRID[0]):
                cx0, cy0, cx1, cy1 = i / GRID[0], j / GRID[1], (i + 1) / GRID[0], (j + 1) / GRID[1]
                if cx0 < x1 and cx1 > x0 and cy0 < y1 and cy1 > y0:
                    keep[j, i] = False
    return lab, keep


def score_pair(game, editor, mask=None):
    """{'dE', 'L', 'hue'} of two pictures of one size (PIL images); ValueError when the sizes differ."""
    import numpy as np
    if game.size != editor.size:
        raise ValueError('the pictures differ in size: %d by %d and %d by %d' % (*game.size, *editor.size))
    a, keep = lab_cells(game, mask)
    b, _ = lab_cells(editor)
    d = a - b
    d = d[keep]
    return {'dE': round(float(np.sqrt((d ** 2).sum(axis=-1)).mean()), 2),
            'L': round(float(np.abs(d[:, 0]).mean()), 2),
            'hue': round(float(np.sqrt(d[:, 1] ** 2 + d[:, 2] ** 2).mean()), 2)}


def score(args):
    plan = shot_list(args.shots_file)
    size, mask = plan['size'], plan.get('mask')
    results, rows = {}, []
    by_map = {}
    for name, shot in cameras(plan, args.maps):
        game = args.shots / 'game' / ('%s.png' % shot['id'])
        editor = args.shots / args.stage / args.look / ('%s.png' % shot['id'])
        if not game.exists() or not editor.exists():
            print('left out %s: %s' % (shot['id'], 'no game shot' if not game.exists() else 'no editor shot'))
            continue
        result = score_pair(load(game, size), load(editor, size), (mask or []) + shot.get('mask', []))
        results[shot['id']] = result
        by_map.setdefault(name, []).append(result)
        print('%-8s %s' % (shot['id'], result))
    if not results:
        raise SystemExit('nothing to score')
    mean = lambda rs, k: round(sum(r[k] for r in rs) / len(rs), 2)
    summary = {name: {k: mean(rs, k) for k in ('dE', 'L', 'hue')} for name, rs in by_map.items()}
    every = list(results.values())
    summary['all'] = {k: mean(every, k) for k in ('dE', 'L', 'hue')}
    out = args.shots / args.stage / args.look / 'scores.json'
    out.write_text(json.dumps({'stage': args.stage, 'look': args.look, 'shots': results, 'maps': summary,
                               'note': args.note, 'date': datetime.date.today().isoformat()}, indent=1),
                   encoding='utf-8', newline='\n')
    print(out)
    if args.progress and PROGRESS.exists():
        lines = ['| %s | %s | %s | %d shots | %s | %s | %s |' % (args.stage, args.look, name, len(by_map.get(name, every)),
                                                                s['dE'], s['L'], s['hue']) for name, s in summary.items()]
        add_rows(PROGRESS, '## Scores (H2)', lines)
        print('rows added to', PROGRESS)


def add_rows(path, heading, lines):
    """The lines put at the end of the table under `heading` in a markdown file (its own line endings kept)."""
    raw = path.read_bytes().decode('utf-8')
    eol = '\r\n' if '\r\n' in raw else '\n'
    text = raw.split(eol)
    at = text.index(heading)
    k = at + 1
    while k < len(text) and not text[k].startswith('|'):
        k += 1
    while k < len(text) and text[k].startswith('|'):
        k += 1
    text[k:k] = lines
    path.write_bytes(eol.join(text).encode('utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--shots-file', type=Path, default=SHOTS_FILE)
    ap.add_argument('--shots', type=Path, default=SHOTS, help='the pictures folder (default: %(default)s)')
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('steps')
    s.add_argument('map')
    s.add_argument('--hud', help='the console command that hides the interface (default UIToggleVisibility)')
    e = sub.add_parser('editor')
    e.add_argument('--stage', required=True)
    e.add_argument('--look', default='neutral', choices=LOOKS)
    e.add_argument('--maps', nargs='*')
    e.add_argument('--port', type=int, default=8794)
    e.add_argument('--cache')
    e.add_argument('--flag', action='append', default=[], help='a URL flag for the page (name=value)')
    e.add_argument('--settle', type=int, default=6, help='seconds a camera waits for its textures')
    e.add_argument('--atmosphere', help='a JSON file of {"fog": {...}, "postProcess": {...}} members put over the map\'s '
                                        'own (as a project\'s atmosphere): the editor shot as a Build of it is shot in '
                                        'the game (EXP-98)')
    e.add_argument('--headed', action='store_true')
    for name in ('sheet', 'score'):
        p = sub.add_parser(name)
        p.add_argument('--stage', required=True)
        p.add_argument('--look', default='neutral', choices=LOOKS)
        p.add_argument('--maps', nargs='*')
        if name == 'score':
            p.add_argument('--note', default='')
            p.add_argument('--no-progress', dest='progress', action='store_false')
    o = sub.add_parser('overlay')
    o.add_argument('game', type=Path)
    o.add_argument('editor', type=Path)
    o.add_argument('out', type=Path)
    args = ap.parse_args(argv)
    if args.command == 'steps':
        shots = shot_list(args.shots_file)['maps'][args.map]
        for step in game_steps(shots, args.hud):
            print(step)
    elif args.command == 'editor':
        editor_shots(args)
    elif args.command == 'sheet':
        sheet(args)
    elif args.command == 'overlay':
        overlay(args.game, args.editor, args.out)
    elif args.command == 'score':
        score(args)


if __name__ == '__main__':
    main()
