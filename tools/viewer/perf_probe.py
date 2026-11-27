"""Times the editor's page on a map and a prefab, by hand, before and after a change that should make it faster
(private/plans/done/sturdier-prefabs-faster-editor-plan.md, P6 and L4). Not a test: times differ by computer, and
nothing here has a pass mark. The numbers go into the change's ledger entry.

  python -B tools/viewer/perf_probe.py --map <map id> [--prefab <prefab file.json>] [--port 8796] [--pieces 500]
      [--headed] [--cache <cache>] [--flag <name=value> ...]

It starts a viewer on a test port (8790 to 8799) with scratch folders for projects, prefabs and builds, opens the
page in Edge (Playwright), and prints:

- the map: how long it takes to open, a frame with and without the sun's shadow pass, the draw calls, the shader
  programs, the textures and their memory on the GPU (worked out from what they hold), a pick under
  the cursor, selecting --pieces pieces, an edit event with them selected, pasting them, undoing the paste;
- the prefab (copied into the scratch prefab folder): how long the builder takes to open it, an edit event, and the
  Problems check;
- every stretch over 300 ms in which the page's thread was held with no busy mark and no loading overlay up
  (PerformanceObserver "longtask"): the steps that still freeze without saying so.

A hidden or headless page draws no frames of its own, so the frame time is renderer.render with gl.finish, timed
here. --headed shows the window.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent

WATCH = """
window.__long = [];
new PerformanceObserver(list => {
  for (const entry of list.getEntries()) {
    const said = !document.getElementById('busyMark')?.hidden || !document.getElementById('loading')?.hidden;
    if (entry.duration > 300 && !said) window.__long.push({ ms: Math.round(entry.duration), during: window.__step ?? 'idle' });
  }
}).observe({ entryTypes: ['longtask'] });
"""

MAP = """async pieces => {
  const v = window.viewer, THREE = await import('three'), out = {}, gl = v.renderer.getContext();
  const timed = async (name, work, times = 1) => {
    window.__step = name;
    const started = performance.now();
    for (let k = 0; k < times; k++) await work();
    out[name] = +((performance.now() - started) / times).toFixed(1);
    window.__step = null;
  };
  const frame = shadow => () => { v.renderer.shadowMap.needsUpdate = shadow; v.renderer.render(v.world, v.camera); gl.finish(); };
  frame(true)();
  await timed('a frame with the shadow pass (ms)', frame(true), 5);
  await timed('a frame without it (ms)', frame(false), 5);
  out['draw calls'] = v.renderer.info.render.calls;
  out['pieces drawn'] = v.roots.size;
  out['shader programs'] = v.renderer.info.programs?.length ?? null;
  // texture memory on the GPU: a compressed texture's levels as stored, a picture's 4 bytes a pixel and a third more
  // for the mips the GPU makes
  const seen = new Set();
  let bytes = 0;
  v.world.traverse(o => {
    for (const m of [o.material].flat()) {
      if (!m) continue;
      for (const value of [...Object.values(m), ...(m.userData?.programTextures ?? [])]) {
        if (!value?.isTexture || seen.has(value)) continue;
        seen.add(value);
        if (value.isCompressedTexture) bytes += value.mipmaps.reduce((sum, level) => sum + level.data.byteLength, 0);
        else if (value.image?.width) bytes += value.image.width * value.image.height * 4 * 4 / 3;
      }
    }
  });
  out['textures'] = seen.size;
  out['texture memory (MB)'] = +(bytes / 1048576).toFixed(1);
  v.frame('playable'); v.camera.updateMatrixWorld(true);
  const rect = v.renderer.domElement.getBoundingClientRect(), points = [];
  for (let i = 1; i < 6; i++) for (let j = 1; j < 6; j++) points.push([rect.left + rect.width * i / 6, rect.top + rect.height * j / 6]);
  v.pick(...points[0]);
  await timed('a pick (ms)', () => { for (const p of points) v.pick(...p); });
  out['a pick (ms)'] = +(out['a pick (ms)'] / points.length).toFixed(2);
  const ids = [...v.roots.values()].filter(r => r.visible && !r.userData.source.hidden).slice(0, pieces).map(r => r.userData.source.id);
  out['pieces selected'] = ids.length;
  await timed('select them (ms)', () => { v.gizmo.setSelection(ids, ids[0]); v.select(ids[0], false, true); });
  await timed('an edit event with them selected (ms)', () => v.select(ids[0], false, true), 5);
  const clip = v.snapshot();
  await timed('paste them (ms)', () => v.pasteSnapshot(clip, new THREE.Matrix4().makeTranslation(960, 0, 960)));
  await timed('undo the paste (ms)', () => { v.gizmo.undo(); });
  return out;
}"""

BUILDER = """async () => {
  const v = window.viewer, out = {}, ids = [...v.roots.keys()];
  out['pieces'] = ids.length;
  window.__step = 'an edit event in the builder';
  const started = performance.now();
  for (let k = 0; k < 10; k++) v.select(ids[(k * 7) % ids.length]);
  out['an edit event in the builder (ms)'] = +((performance.now() - started) / 10).toFixed(1);
  window.__step = null;
  const chip = document.getElementById('problemsChip'), began = performance.now();
  while (['Checking…', 'Check for problems', ''].includes(chip.textContent) && performance.now() - began < 60000) await new Promise(r => setTimeout(r, 50));
  out['the Problems chip'] = chip.textContent;
  return out;
}"""


def wait_for(url, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            with urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise SystemExit('the test server did not answer at %s' % url)


def table(title, rows):
    print('\n' + title)
    width = max(len(k) for k in rows) if rows else 0
    for key, value in rows.items():
        print('  %-*s  %s' % (width, key, value))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--map', required=True, help='the map to open (its id in the map browser, such as URB_Bar)')
    ap.add_argument('--prefab', type=Path, help='a prefab file to open in the builder (copied to a scratch folder)')
    ap.add_argument('--port', type=int, default=8796)
    ap.add_argument('--pieces', type=int, default=500)
    ap.add_argument('--cache', help='the cache folder (default: the cache setting)')
    ap.add_argument('--headed', action='store_true', help='show the browser window')
    ap.add_argument('--flag', action='append', default=[], help='a page address flag (name=value), as texfallback=all')
    args = ap.parse_args(argv)
    if not 8790 <= args.port <= 8799:
        raise SystemExit('use a test port, 8790 to 8799')
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='perf-probe-') as scratch:
        scratch = Path(scratch)
        for name in ('projects', 'prefabs', 'builds'):
            (scratch / name).mkdir()
        prefab_id = None
        if args.prefab:
            document = json.loads(args.prefab.read_text(encoding='utf-8'))
            prefab_id = document['id']
            shutil.copyfile(args.prefab, scratch / 'prefabs' / args.prefab.name)
        command = [sys.executable, '-B', str(HERE / 'viewer.py'), 'serve', *([args.cache] if args.cache else []),
                   '--port', str(args.port), '--no-open', '--projects', str(scratch / 'projects'),
                   '--prefabs', str(scratch / 'prefabs'), '--builds', str(scratch / 'builds'), '--dry-play']
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = 'http://127.0.0.1:%d/' % args.port
            wait_for(base + 'prefabs.json')
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=not args.headed)
                page = browser.new_page(viewport=dict(width=1600, height=1000))
                page.add_init_script(WATCH)
                held = []

                def opened(query):
                    began = time.monotonic()
                    page.goto(base + query)
                    page.wait_for_function('window.viewer && document.querySelector("#loading").hidden && window.viewer.roots.size > 0',
                                           timeout=600000)
                    return round(time.monotonic() - began, 1)

                seconds = opened('?map=' + args.map + ''.join('&' + f for f in args.flag))
                page.wait_for_timeout(1500)
                rows = {'open the map (s)': seconds, **page.evaluate(MAP, args.pieces)}
                table('Map %s' % args.map, rows)
                held += page.evaluate('window.__long')
                if prefab_id:
                    seconds = opened('?prefab=' + prefab_id)
                    rows = {'open it in the builder (s)': seconds, **page.evaluate(BUILDER)}
                    table('Prefab %s' % args.prefab.name, rows)
                    held += page.evaluate('window.__long')
                print('\nHeld over 300 ms with nothing said: %s' % (
                    'none' if not held else ''.join('\n  %d ms during %s' % (h['ms'], h['during']) for h in held)))
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == '__main__':
    main()
