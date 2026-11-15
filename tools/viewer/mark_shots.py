"""Marked editor shots for an in-game check: the project open in the editor, numbered circles on the pieces to look
at, a legend saying what each should do, from cameras the shots file chooses (an overview and close-ups).

The shots file (JSON) names the map, the project and the shots; points are in game coordinates (x, y, z up):

  {"map": "CSmallScout_Farm", "project": "<project id>",
   "mission": "2",                                       # optional: the header's mission (a record's index, or
                                                         # "kind:TerrorSite" for a kind the project adds)
   "shots": [{"out": "EXP-22-run2-shed.png",            # a file name, in the pictures folder (--out)
              "title": "EXP-22 run 2: the moved ladder",
              "target": [-1392, -1536, 120],             # what the camera looks at
              "camera": [-1300, -250, 900],              # the camera's offset from the target
              "box": [[x, y, z], ...],                   # optional: a dashed outline (an overview's area)
              "fov": 50,                                 # optional
              "floor": "1",                              # optional: the floors control ("all" by default)
              "lights": true,                            # optional: the light markers shown (Shift+L)
              "lighting": "map",                         # optional: the lighting mode (map, map-no-area, neutral)
              "missionObjects": true,                    # optional: View options' Mission objects shown
              "marks": [{"n": "1", "at": [-1392, -1392, 120], "color": "#5ad17a", "r": 36,
                         "side": "left",                 # optional: the number badge on the left
                         "text": "moved here: a route up it should show"}]}]}  # text: optional, for the legend

Run it against a test server (ports 8790-8799) serving the project's projects folder, and stop the server after:

  python tools/viewer/viewer.py serve --port 8790 --no-open --projects <projects> --builds <scratch>
  python tools/viewer/mark_shots.py <shots.json> [--server http://127.0.0.1:8790/] [--out <folder>]

The pictures go to private/shots in the repository unless --out names a folder. Pictures of experiments and checks
are never committed (private/ is ignored); the shots file is what the repository keeps.

It needs Playwright (pip install playwright) and drives the installed Edge.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

OVERLAY = """([marks, legend, title, box]) => {
  document.getElementById('markLayer')?.remove();
  const svgNS = 'http://www.w3.org/2000/svg', w = innerWidth, h = innerHeight;
  const svg = document.createElementNS(svgNS, 'svg');
  svg.id = 'markLayer';
  Object.assign(svg.style, { position: 'fixed', left: 0, top: 0, width: w + 'px', height: h + 'px', pointerEvents: 'none', zIndex: 9999 });
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  const el = (tag, attrs, parent = svg) => { const e = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); parent.append(e); return e; };
  if (box) el('polygon', { points: box.map(p => p.join(',')).join(' '), fill: 'none', stroke: '#ffffff', 'stroke-width': 3, 'stroke-dasharray': '10 6' });
  for (const m of marks) {
    el('circle', { cx: m.x, cy: m.y, r: m.r, fill: 'none', stroke: '#000', 'stroke-width': 7, opacity: 0.55 });
    el('circle', { cx: m.x, cy: m.y, r: m.r, fill: 'none', stroke: m.color, 'stroke-width': 4 });
    const lx = m.x + (m.side === 'left' ? -1 : 1) * m.r * 0.75, ly = m.y - m.r * 0.75;
    el('circle', { cx: lx, cy: ly, r: 15, fill: m.color, stroke: '#000', 'stroke-width': 2 });
    const t = el('text', { x: lx, y: ly + 6, 'text-anchor': 'middle', 'font-size': 18, 'font-weight': 700, fill: '#111', 'font-family': 'Segoe UI, sans-serif' });
    t.textContent = m.n;
  }
  const lines = [title, ...legend.map(l => `${l.n}  ${l.text}`)];
  const pad = 12, lh = 24, bw = Math.max(...lines.map(s => s.length)) * 9.2 + 2 * pad, bh = lines.length * lh + 2 * pad;
  const bx = 70, by = h - bh - 70;
  el('rect', { x: bx, y: by, width: bw, height: bh, rx: 6, fill: 'rgba(12,18,24,0.88)', stroke: '#44535e' });
  lines.forEach((s, k) => {
    const color = k === 0 ? '#ffffff' : legend[k - 1].color;
    const t = el('text', { x: bx + pad, y: by + pad + 17 + k * lh, 'font-size': k === 0 ? 17 : 16, 'font-weight': k === 0 ? 700 : 500,
                           fill: color, 'font-family': 'Segoe UI, sans-serif' });
    t.textContent = s;
  });
  document.body.append(svg);
}"""

# Game points to page pixels through the editor's camera (the viewer's basis is x, up, y).
PROJECT = """async ([points]) => {
  const T = await import('/vendor/three/three.module.js');
  viewer.camera.updateMatrixWorld(true);
  const r = viewer.renderer.domElement.getBoundingClientRect();
  return points.map(([x, y, z]) => { const v = new T.Vector3(x, z, y).project(viewer.camera);
    return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height]; });
}"""

MISSION_OBJECTS = """on => { const t = document.getElementById('missionObjectsToggle');
  if (t && !t.closest('[hidden]') && t.checked !== on) { t.checked = on; t.onchange({ target: t }); } }"""

CAMERA = """([t, c, fov]) => { viewer.controls.target.set(t[0], t[2], t[1]);
  viewer.camera.position.set(t[0] + c[0], t[2] + c[2], t[1] + c[1]); if (fov) viewer.camera.fov = fov;
  viewer.camera.updateProjectionMatrix(); viewer.controls.update(); }"""


def page_url(server, plan):
    query = dict(map=plan['map'])
    if plan.get('project'):
        query['project'] = plan['project']
    if plan.get('mission') is not None:
        query['mission'] = str(plan['mission'])
    return server.rstrip('/') + '/?' + urlencode(query)


def take(page, shot, out):
    page.evaluate('viewer.select(null)')
    page.keyboard.press('Escape')
    # the floors control: "1" shows the ground floor with the floors and roofs above cut away, "all" (the default) all
    floor = page.locator('#floor button[data-value="%s"]' % shot.get('floor', 'all'))
    if floor.count() and 'on' not in (floor.first.get_attribute('class') or ''):
        floor.first.click()
    page.evaluate('on => viewer.setLightsShown?.(on)', bool(shot.get('lights')))
    page.evaluate(MISSION_OBJECTS, bool(shot.get('missionObjects')))
    lighting = page.locator('#lighting button[data-value="%s"]' % shot.get('lighting', 'neutral'))
    if lighting.count():
        page.evaluate('m => document.querySelector(`#lighting button[data-value="${m}"]`).click()', shot.get('lighting', 'neutral'))
    page.evaluate(CAMERA, [shot['target'], shot['camera'], shot.get('fov')])
    page.evaluate("document.getElementById('projectBanner').hidden = true")   # the page's notices cover the view
    page.wait_for_timeout(4000)  # the textures of what comes into view
    points = page.evaluate(PROJECT, [[m['at'] for m in shot['marks']]])
    box = page.evaluate(PROJECT, [shot['box']]) if shot.get('box') else None
    marks = [dict(n=m['n'], x=p[0], y=p[1], r=m.get('r', 42), color=m['color'], side=m.get('side'))
             for m, p in zip(shot['marks'], points)]
    legend = [dict(n=m['n'], text=m['text'], color=m['color']) for m in shot['marks'] if m.get('text')]
    page.evaluate(OVERLAY, [marks, legend, shot['title'], box])
    page.wait_for_timeout(300)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('shots', type=Path, help='the shots file (JSON)')
    a.add_argument('--server', default='http://127.0.0.1:8790/', help='the test server (default: %(default)s)')
    a.add_argument('--width', type=int, default=1600)
    a.add_argument('--height', type=int, default=1000)
    a.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[2] / 'private' / 'shots',
                   help='the folder the pictures go to (default: private/shots in the repository)')
    args = a.parse_args()
    plan = json.loads(args.shots.read_text(encoding='utf-8'))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport=dict(width=args.width, height=args.height), device_scale_factor=1)
        page.goto(page_url(args.server, plan))
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
        page.wait_for_timeout(1500)
        changes = page.evaluate('viewer.changes()')
        if plan.get('project') and not changes.get('total'):
            raise SystemExit('the project %s opened with no changes: is the server serving its projects folder?'
                             % plan['project'])
        for shot in plan['shots']:
            out = args.out / Path(shot['out']).name
            take(page, shot, out)
            print(out, changes)
        browser.close()


if __name__ == '__main__':
    main()
