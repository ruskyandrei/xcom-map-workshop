"""The user guide's screenshots (tools/release/guide/shots/*.webp): the editor driven through a small demo project
on the Bar, each shot with numbered marks on the controls the guide explains (guide.html's lists use the same
numbers). Run it again when the editor's window changes, then check each picture and guide.html's lists against it.
Take them into a scratch folder (--out) and compare them with the guide's own (guide_tools.py compare and sheet)
before copying the changed ones into shots/; the update-guide skill (.claude/skills/update-guide/SKILL.md) has the
whole process.

It saves projects and builds them (the project manager's shot: two quick builds and a queue of full builds, stopped
once its second build is under way), but never installs or plays, so run it against a test server (ports 8790-8799)
with scratch projects, builds and squad, and stop the server after:

  python tools/viewer/viewer.py serve --port 8790 --no-open --projects <scratch>/projects --builds <scratch>/builds --squad <scratch>/test-squad.json
  python tools/release/guide/take_shots.py [--server http://127.0.0.1:8790/] [--only window,header] [--out <folder>]

The scratch projects folder must be empty (the demo project is saved under a fixed name), and so must the prefabs
folder beside it (the prefabs shot saves two). It needs the Bar exported in the server's cache (the mission objects'
shot opens URB_SlaughterhouseA, read from the game on its first open), Playwright (pip install playwright; it drives
the installed Edge) and Pillow. The whole run takes about five minutes, most of it the manager's builds.

The server's answers that would name a folder of this computer are replaced by a usual install's (typical()).
"""
import argparse
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP = 'URB_Bar'
PROJECT = 'Bar remix'
WIDTH, HEIGHT, SCALE = 1440, 900, 2
TALL = 1200                     # the piece panel's shot: a window tall enough for the whole panel
QUALITY = 82

# pieces of the Bar the demo uses, by actor (the export's ids change with its version; actors don't)
ACTOR = 'TheWorld.PersistentLevel.%s'
POOL_TABLE, CLAW_MACHINE, ATM = (ACTOR % ('XComDestructibleActor_%s' % n) for n in ('491', '316', '4'))
KEG_A, KEG_B, KEG_C = (ACTOR % ('XComDestructibleActor_%s' % n) for n in ('157', '159', '108'))
SUV = ACTOR % 'XComDestructibleActor_14'
DUMPSTER = ACTOR % 'XComDestructibleActor_61'            # one of the Bar's six Dumpster_A
# the mission objects' shot: a council bomb's map and the stream with its bomb and power nodes
BOMB_MAP, BOMB_STREAM = 'URB_SlaughterhouseA', 'URB_Slaughterhouse_Stream'
# the project manager's shot: the demo saved again under these names, each with one more edit (the last never built)
MORE_PROJECTS = (('Car park cover', SUV), ('Back alley', KEG_C), ('Bar after hours', KEG_B))
# cameras, in game units: what the camera looks at, and its offset from there
BAR_VIEW = ([150, 640, 20], [600, -1450, 1250])
# the Effects view's shots: the taxi's idle sound picked in the car park, with a webbing effect, the shop's sound and a
# lens flare marked round it; an alien vapour pod's smoke and its values; the fires of the other maps in the Add panel
TAXI_SOUND, SHOP_SOUND = ACTOR % 'AmbientSoundSimple_3', ACTOR % 'AmbientSoundSimple_2'
WEBBING, POD_SMOKE, FLARE = ACTOR % 'Emitter_75', ACTOR % 'Emitter_15', ACTOR % 'LensFlareSource_8'
SOUND_VIEW, SMOKE_VIEW = [700, -1500, 1100], [420, -800, 560]
LIGHT_VIEW = ([375, 300, 60], [500, -900, 700])
# the Spawns view's shot: a pod of the Bar's west room picked, with another pod, Meld points and a no-spawn volume
# round it; and a no-spawn volume picked (the one round the van in the street), with its handles
SPAWN_POD = ACTOR % 'XComAlienPod_Abduction_2'
SPAWN_VIEW = ([-1150, 650, 17], [480, -1180, 1000])
SPAWN_VOLUME = ACTOR % 'XComNoSpawnVolume_0'
VOLUME_VIEW = ([-560, -480, 100], [620, -780, 820])
SPOT_NEAR = [375, 245, 297]
PROJECTS_FOLDER = r'C:\Users\you\AppData\Local\Programs\XCOM Map Workshop\projects'
GAME_FOLDER = r'C:\Program Files (x86)\Steam\steamapps\common\XCom-Enemy-Unknown'

# The marks: numbered badges beside the page's own controls, with a line to each, and dashed frames round regions.
MARKS = """(marks) => {
  document.getElementById('guideMarks')?.remove();
  if (!marks.length) return;
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
  svg.id = 'guideMarks';
  Object.assign(svg.style, { position: 'fixed', left: 0, top: 0, width: innerWidth + 'px', height: innerHeight + 'px', pointerEvents: 'none', zIndex: 99999 });
  svg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  const el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); svg.append(e); return e; };
  for (const m of marks) {
    let r = m.rect;
    if (!r) { const b = document.querySelector(m.sel)?.getBoundingClientRect();
      if (!b || !b.width) throw new Error('nothing to mark at ' + m.sel); r = [b.left, b.top, b.width, b.height]; }
    const [x, y, w, h] = r, gap = m.gap ?? 16, at = m.at ?? 0.5, R = m.r ?? 10.5;
    if (m.frame) el('rect', { x: x - 3, y: y - 3, width: w + 6, height: h + 6, rx: 7, fill: 'none', stroke: '#ffcf5a', 'stroke-width': 1.6, 'stroke-dasharray': '6 4' });
    // the badge's centre, and where its line ends on the control
    const side = m.side ?? 'bottom', inset = m.inset ?? 3;
    const [bx, by, tx, ty] = side === 'bottom' ? [x + w * at, y + h + gap, x + w * at, y + h - inset]
      : side === 'top' ? [x + w * at, y - gap, x + w * at, y + inset]
      : side === 'left' ? [x - gap, y + h * at, x + inset, y + h * at]
      : side === 'right' ? [x + w + gap, y + h * at, x + w - inset, y + h * at]
      : [x + w * at, y + h * (m.aty ?? 0.5), null, null];                 // 'on': the badge on the control itself
    const cx = bx + (m.dx ?? 0), cy = by + (m.dy ?? 0);
    if (tx !== null && !m.frame) {
      el('line', { x1: cx, y1: cy, x2: tx, y2: ty, stroke: '#12100a', 'stroke-width': 3.6, 'stroke-linecap': 'round', opacity: 0.8 });
      el('line', { x1: cx, y1: cy, x2: tx, y2: ty, stroke: '#ffcf5a', 'stroke-width': 1.6, 'stroke-linecap': 'round' });
      el('circle', { cx: tx, cy: ty, r: 2.4, fill: '#ffcf5a', stroke: '#12100a', 'stroke-width': 1 });
    }
    el('circle', { cx, cy, r: R, fill: '#ffcf5a', stroke: '#12100a', 'stroke-width': 1.6 });
    const t = el('text', { x: cx, y: cy + 4.2, 'text-anchor': 'middle', 'font-size': String(m.n).length > 1 ? 11.5 : 12.5, 'font-weight': 700, fill: '#191204', 'font-family': 'Segoe UI, Arial, sans-serif' });
    t.textContent = m.n;
  }
  document.body.append(svg);
}"""

CAMERA = """([t, c, fov]) => { viewer.controls.target.set(t[0], t[2], t[1]);
  viewer.camera.position.set(t[0] + c[0], t[2] + c[2], t[1] + c[1]); if (fov) viewer.camera.fov = fov;
  viewer.camera.updateProjectionMatrix(); viewer.controls.update(); }"""

ID_OF = "actor => viewer.data.objects.find(o => o.actor === actor && !o.hidden)?.id"


def typical(page):
    """The server's answers that name this computer's folders, replaced by a usual install's: the game in Steam's
    own library, played there through Steam, with nothing of the editor's installed; and the projects folder in
    the editor's own (installed for this user)."""
    def play(route):
        route.fulfill(json=dict(
            lwr=dict(setting=GAME_FOLDER, folder=GAME_FOLDER, note=GAME_FOLDER, kind='Long War Rebalance'),
            install=dict(folder=GAME_FOLDER, note=GAME_FOLDER, source='the game install', sameAsLwr=True, ready=True, why=None),
            launch=dict(how='steam', why=None),
            game=dict(installed=[], intro=None, playFile=False, configKept=False, lastPlay=None, anything=False)))

    def projects(route):
        answer = route.fetch()
        body = answer.json()
        body['folder'] = PROJECTS_FOLDER
        route.fulfill(response=answer, json=body)
    def install_named(route):
        """An answer that names the game install (the squad's and the project manager's), named as a usual one."""
        answer = route.fetch()
        body = answer.json()
        if isinstance(body.get('install'), dict):
            body['install'].update({k: GAME_FOLDER for k in ('folder', 'note') if k in body['install']})
        route.fulfill(response=answer, json=body)
    page.route('**/play.json', play)
    page.route('**/projects.json', projects)
    page.route('**/squad.json', install_named)
    page.route('**/manager.json', install_named)


class Shots:
    def __init__(self, page, out, only):
        self.page, self.out, self.only = page, out, only

    # --- helpers
    def id(self, actor):
        found = self.page.evaluate(ID_OF, actor)
        if not found: raise SystemExit('%s is not in the export of %s' % (actor, MAP))
        return found

    def select(self, *actors):
        self.page.evaluate('viewer.select(null)')
        for k, actor in enumerate(actors):
            self.page.evaluate('([id, add]) => viewer.select(id, add)', [self.id(actor), k > 0])

    def camera(self, target, offset, fov=None):
        self.page.evaluate(CAMERA, [target, offset, fov])

    def settle(self, ms=2500):
        self.page.wait_for_timeout(ms)

    def rect(self, selector):
        r = self.page.evaluate("s => { const b = document.querySelector(s)?.getBoundingClientRect(); return b && [b.left, b.top, b.width, b.height]; }", selector)
        if not r or not r[2]: raise SystemExit('nothing shows at %s' % selector)
        return r

    def around(self, *selectors, pad=(14, 14, 14, 14)):
        """The clip round these controls: pad is left, top, right, bottom."""
        rects = [self.rect(s) for s in selectors]
        x0, y0 = min(r[0] for r in rects) - pad[0], min(r[1] for r in rects) - pad[1]
        x1, y1 = max(r[0] + r[2] for r in rects) + pad[2], max(r[1] + r[3] for r in rects) + pad[3]
        view = self.page.viewport_size
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(view['width'], x1), min(view['height'], y1)
        return dict(x=x0, y=y0, width=x1 - x0, height=y1 - y0)

    def panel_rows(self, panel, rows, side='left', gap=16):
        """Marks beside a panel, one for each (number, selector): at the control's height, on the panel's edge."""
        px, _, pw, _ = self.rect(panel)
        marks = []
        for n, selector in rows:
            _, y, _, h = self.rect(selector)
            marks.append(dict(n=n, rect=[px, y, pw, h], side=side, gap=gap, inset=-2))
        return marks

    def shot(self, name, marks=(), clip=None, resize=1):
        from PIL import Image
        self.page.evaluate(MARKS, list(marks))
        self.page.wait_for_timeout(250)
        png = self.page.screenshot(clip=clip)
        self.page.evaluate(MARKS, [])
        path = self.out / ('%s.webp' % name)
        image = Image.open(io.BytesIO(png)).convert('RGB')
        if resize != 1: image = image.resize((round(image.width * resize), round(image.height * resize)), Image.LANCZOS)
        image.save(path, 'WEBP', quality=QUALITY, method=6)
        print('%-14s %4d x %-4d %4d KB' % (name, image.width, image.height, path.stat().st_size // 1024), flush=True)

    def close_pops(self):
        page = self.page
        page.keyboard.press('Escape')
        page.evaluate("document.querySelectorAll('.pop:not([hidden])').forEach(p => document.querySelector(`[data-pop=${p.id}]`)?.click())")
        page.evaluate("for (const id of ['projectBanner', 'dragHint']) document.getElementById(id).hidden = true")

    # --- the demo project: a moved piece, a copy and a deleted one, saved
    def demo_project(self):
        page = self.page
        page.locator('#scenery button[data-value="interior"]').click()
        page.locator('#floor button[data-value="1"]').click()
        self.select(POOL_TABLE)
        page.locator('#posX').fill('336')
        page.locator('#posX').press('Enter')
        self.select(ATM)
        page.keyboard.press('Delete')
        # a copy of the claw machine, placed by a click in the view
        self.camera([330, 900, 20], [300, -900, 900])
        self.settle(1500)
        self.select(CLAW_MACHINE)
        page.keyboard.press('Control+c')
        page.keyboard.press('Control+v')
        x, y = page.evaluate('viewer.screenOf([140, 620, 20])')
        page.mouse.move(x, y)
        page.mouse.move(x + 2, y + 1)
        page.mouse.click(x + 2, y + 1)
        page.wait_for_function('viewer.changes().total >= 3')
        self.copy = page.evaluate('(() => { const r = viewer.gizmo.selection()[0]; return [...viewer.roots.entries()].find(e => e[1] === r)[0]; })()')
        page.keyboard.press('Control+s')
        page.locator('#fileName').fill(PROJECT)
        page.locator('#fileOk').click()
        page.wait_for_function('viewer.project() && !viewer.project().dirty', timeout=20000)
        self.close_pops()

    # --- the shots
    def window(self):
        page = self.page
        self.select(POOL_TABLE)
        page.keyboard.press('w')
        self.camera(*BAR_VIEW)
        self.settle(4000)
        header, rail, panel, dock = (self.rect(s) for s in ('header', '#rail', '#inspector', '.dock'))
        view = [rail[0] + rail[2] + 60, header[3] + 60, panel[0] - rail[0] - rail[2] - 120, dock[1] - header[3] - 150]
        self.shot('window', [
            dict(n='A', rect=[4, 4, WIDTH - 8, header[3] - 8], frame=True, side='on', at=0.42, aty=1.0, dy=8),
            dict(n='B', sel='#rail', frame=True, side='right', gap=3, at=0.08),
            dict(n='C', rect=view, side='on', at=0.03, aty=0.04),
            dict(n='D', sel='#inspector', frame=True, side='left', gap=3, at=0.06),
            dict(n='E', sel='.dock', frame=True, side='top', gap=3, at=0.04),
            dict(n='F', sel='#tileNote', frame=True, side='top', gap=3, at=0.5),
        ], resize=0.75)

    def header(self):
        controls = ('#projectButton', '#mapButton', '#finder', '#editCount', '#editUndo', '#editRedo', '#editResetAll',
                    '#settingsButton', '#notesButton', '#viewButton', '#helpButton')
        marks = [dict(n=k + 1, sel=s, side='bottom', gap=17) for k, s in enumerate(controls)]
        # in two halves, the empty middle left out, so that both show at their full size in the guide
        h = self.rect('header')[3] + 32
        finder, count = self.rect('#finder'), self.rect('#editCount')
        self.shot('header-left', marks, clip=dict(x=0, y=0, width=finder[0] + finder[2] + 16, height=h))
        self.shot('header-right', marks, clip=dict(x=count[0] - 16, y=0, width=WIDTH - count[0] + 16, height=h))

    def rail(self):
        controls = ('#editOff', '#editMove', '#editRotate', '#editBox', '#editAdd', '#editNormal', '#editBuildings', '#editLights',
                    '#editZones', '#editEffects', '#editSpawns', '#editGrid', '#editSpace', '#editPivot', '#editSnap', '#editLevels',
                    '#editLinked', '#selected')
        marks = [dict(n=k + 1, sel=s, side='right', gap=20) for k, s in enumerate(controls)]
        self.shot('rail', marks, clip=self.around('#rail', pad=(8, 8, 40, 8)))

    def normal_flyout(self):
        """The Normal view button hovered: its flyout with the Lights, Floor boxes, Effects and sounds, and Spawn points
        and objectives switches."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editNormal').hover()
        page.wait_for_timeout(400)
        x, y, w, h = self.rect('#editNormal')
        fx, fy, fw, fh = self.rect('#normalFlyout')
        self.shot('normal-flyout', clip=dict(x=x - 8, y=min(y, fy) - 10, width=fx + fw - x + 18, height=max(h, fh) + 20))
        page.mouse.move(WIDTH / 2, HEIGHT / 2)

    def dock(self):
        self.page.evaluate('viewer.select(null)')
        marks = [dict(n=k + 1, sel=s, side='top', gap=17) for k, s in enumerate(('#frame', '#scenery', '#floor'))]
        self.shot('dock', marks, clip=self.around('.dock', pad=(60, 40, 60, 10)))

    def project_menu(self):
        page = self.page
        page.locator('#projectButton').click()
        page.wait_for_selector('#projectRecent > *')
        page.wait_for_timeout(600)
        rows = [(1, '#projectInfo'), (2, '#projectSave'), (3, '#projectSaveAs'), (4, '#projectBuild'), (5, '#projectPlay'),
                (6, '#projectMaps'), (7, '#projectSize'), (8, '#projectMissions'), (9, '#projectClear'), (10, '#projectLoad'),
                (11, '#projectManage'), (12, '#projectClose'), (13, '#projectCache'), (14, '#projectSetup'),
                (15, '#projectRecent'), (16, '#installInfo')]
        self.shot('project-menu', self.panel_rows('#projectMenu', rows, side='right'),
                  clip=self.around('#projectButton', '#projectMenu', pad=(10, 6, 44, 12)))
        self.close_pops()

    def map_browser(self):
        page = self.page
        page.locator('#mapButton').click()
        page.wait_for_selector('#mapList .maprow')
        page.wait_for_timeout(500)
        x, y, w, h = self.rect('#mapList .maprow.on')
        marks = [dict(n=1, sel='#mapSearch', side='top', gap=22, at=0.3),
                 dict(n=2, sel='#mapForm .mapfind label', side='top', gap=22),
                 dict(n=3, sel='#mapGroups', side='left', gap=18),
                 dict(n=4, sel='#mapList .maprow.on', side='left', gap=18),
                 dict(n=5, rect=[x + w - 170, y, 170, h], side='top', gap=18, at=0.2, inset=8),
                 dict(n=6, sel='#mapCount', side='bottom', gap=20, at=0.2),
                 dict(n=7, sel='#mapOk', side='bottom', gap=20)]
        self.shot('map-browser', marks, clip=self.around('#mapForm', pad=(36, 36, 16, 34)))
        page.keyboard.press('Escape')

    def piece_panel(self):
        page = self.page
        page.evaluate('id => { viewer.select(null); viewer.select(id); }', self.copy)
        page.keyboard.press('v')
        # (the folds as a first visit has them, Flags folded and Place open; Source unfolded for its fields)
        page.evaluate("document.getElementById('sourceDetails').open = true; document.getElementById('poseBox').open = true; document.getElementById('flagsBox').open = false")
        page.set_viewport_size(dict(width=WIDTH, height=TALL))      # the panel with its source fields is taller than the window
        page.wait_for_timeout(800)
        rows = [(1, '#details'), (2, '#editCopy'), (3, '#flagsBox summary'), (4, '#posX'), (5, '#rotP'), (6, '#sourceDetails summary'), (7, '#copyPaths')]
        self.shot('piece-panel', self.panel_rows('#inspector', rows), clip=self.around('#inspector', pad=(40, 8, 8, 8)))
        page.evaluate("document.getElementById('sourceDetails').open = false")
        page.set_viewport_size(dict(width=WIDTH, height=HEIGHT))
        page.wait_for_timeout(500)

    def flags(self):
        """The Flags group: the Bar's six dumpsters picked with Select all of a kind, Blocks sight turned off for them.
        Undone after."""
        page = self.page
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        page.locator('#floor button[data-value="all"]').click()
        self.select(DUMPSTER)
        page.locator('#editKind').click()
        page.wait_for_function('viewer.gizmo.selection().length > 1')
        page.evaluate("document.getElementById('flagsBox').open = true")
        page.locator('#flagsRows .flagrow').nth(2).locator('input').click()
        page.wait_for_function("document.getElementById('flagsReset').disabled === false")
        page.wait_for_timeout(500)
        chip = page.evaluate("""() => { const c = [...document.querySelectorAll('#details .chip')].find(c => c.textContent.startsWith('Flags'));
          const b = c?.getBoundingClientRect(); return b && [b.left, b.top, b.width, b.height]; }""")
        if not chip: raise SystemExit('no Flags chip on the picked dumpsters')
        marks = [dict(n=1, rect=chip, side='right', gap=18)]
        marks += self.panel_rows('#inspector', [(2, '#editKind'), (3, '#flagsRows .flagrow:nth-child(1)'),
                                                (4, '#flagsRows .flagrow:nth-child(3)'), (5, '#flagsReset')])
        self.shot('flags', marks, clip=self.around('#details', '#flagsBox', pad=(56, 14, 50, 12)))
        while page.evaluate('viewer.gizmo.undoDepth()') > steps: page.keyboard.press('Control+z')
        page.evaluate('viewer.select(null)')
        page.locator('#floor button[data-value="1"]').click()

    def box_select(self):
        """Box select: a box drawn over part of the car park, its top pulled down, with its handles and its bar. Put away
        after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#scenery button[data-value="full"]').click()
        page.locator('#floor button[data-value="all"]').click()
        origin = page.evaluate('viewer.data.tileGrid.origin')
        spot = [origin[0] + 96 * 6, origin[1] + 96 * 6, 0]
        self.camera([spot[0] + 40, spot[1] + 60, 110], [-560, -900, 760])
        self.settle(2500)
        a = page.evaluate('p => viewer.screenOf(p)', [spot[0] - 200, spot[1] - 200, 0])
        b = page.evaluate('p => viewer.screenOf(p)', [spot[0] + 260, spot[1] + 260, 0])
        page.keyboard.press('t')
        page.mouse.move(*a)
        page.mouse.down()
        page.mouse.move((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, steps=4)
        page.mouse.move(*b, steps=4)
        page.mouse.up()
        page.wait_for_function('viewer.pickBox()')
        box = page.evaluate('viewer.pickBox()')
        box[5] = box[2] + 300
        page.evaluate('b => viewer.setPickBox(b)', box)
        page.mouse.move(8, 8)
        self.settle(1200)
        handle = {key: page.evaluate('k => viewer.pickFaceHandle(k)', key) for key in ('z1', 'x1')}
        move = page.evaluate('viewer.pickMoveHandle()')
        corner = page.evaluate('p => viewer.screenOf(p)', [box[0], box[4], box[5]])
        self.shot('box-select', [
            dict(n=1, sel='#editBox', side='right', gap=20),
            dict(n=2, rect=[corner[0] - 5, corner[1] - 5, 10, 10], side='left', gap=26),
            dict(n=3, rect=[handle['z1'][0] - 5, handle['z1'][1] - 5, 10, 10], side='left', gap=26),
            dict(n=3, rect=[handle['x1'][0] - 5, handle['x1'][1] - 5, 10, 10], side='right', gap=26),
            dict(n=4, rect=[move[0] - 6, move[1] - 6, 12, 12], side='right', gap=26),
            dict(n=5, sel='#boxBar', side='bottom', gap=18),
        ], resize=0.75)
        page.keyboard.press('Escape')
        assert page.evaluate('viewer.pickBox()') is None
        # the later shots are of the demo's view: the play area, cut down to the ground floor
        page.locator('#scenery button[data-value="interior"]').click()
        page.locator('#floor button[data-value="1"]').click()

    def group_align(self):
        """Two kegs grouped (the group section), then a third keg picked with them (the align section)."""
        page = self.page
        self.select(KEG_A, KEG_B)
        page.keyboard.press('Control+g')
        page.locator('#groupBreak').check()
        page.wait_for_timeout(400)
        rows = [(1, '#groupHead'), (2, '#groupDissolve'), (3, '#groupBreakRow')]
        self.shot('group', self.panel_rows('#inspector', rows), clip=self.around('#groupBox', pad=(56, 14, 24, 12)))
        page.evaluate('([id]) => viewer.select(id, true)', [self.id(KEG_C)])
        page.locator('#alignX').check()
        page.evaluate("document.getElementById('alignBox').classList.add('showhow')")      # (its words, as its info button shows them)
        page.wait_for_timeout(400)
        rows = [(1, '#alignTarget'), (2, '#alignGo'), (3, '#alignText')]
        self.shot('align', self.panel_rows('#inspector', rows), clip=self.around('#alignBox', pad=(56, 14, 24, 12)))
        page.evaluate("document.getElementById('alignBox').classList.remove('showhow')")
        page.locator('#alignX').uncheck()
        self.select(KEG_A)
        page.keyboard.press('Control+Shift+G')
        page.evaluate('viewer.select(null)')

    def add(self):
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.evaluate("viewer.setLibraryScope('map')")
        page.wait_for_selector('#libList .libitem')
        page.wait_for_function("[...document.querySelectorAll('.libitem canvas')].slice(0, 12).every(c => c.dataset.drawn)", timeout=60000)
        page.wait_for_timeout(500)
        marks = [dict(n=1, sel='#libFilter', side='right', gap=18),
                 dict(n=5, sel='#libList .libitem', side='right', gap=18),
                 dict(n=6, sel='#libFoot', side='right', gap=18),
                 dict(n=7, sel='#libraryClose', side='right', gap=18)]
        for n, s in ((2, '#libKind'), (3, '#libWhere'), (4, '#libSort')):
            if page.locator(s).is_visible(): marks.append(dict(n=n, sel=s, side='on', aty=0, dy=-2))
        marks.append(dict(n=8, sel='#libScope button[data-value="all"]', side='top', gap=22, at=0.5))
        self.shot('add', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.locator('#libraryClose').click()

    def add_all(self):
        """All maps: the pieces of the game's other maps. The server's cache must have the library scanned
        (`viewer.py library scan`)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.evaluate("viewer.setLibraryScope('all')")
        page.wait_for_function('viewer.library.ready()', timeout=120000)
        page.locator('#libAllFilter').fill('lamp')
        page.wait_for_selector('#libAllList .libitem')
        page.wait_for_function("[...document.querySelectorAll('#libAllList .libitem canvas')].slice(0, 8).every(c => c.dataset.drawn)", timeout=180000)
        page.wait_for_timeout(500)
        marks = [dict(n=1, sel='#libScope button[data-value="all"]', side='top', gap=22, at=0.5),
                 dict(n=2, sel='#libAllFilter', side='right', gap=18),
                 dict(n=3, sel='#libAllHome', side='on', aty=0, dy=-2),
                 dict(n=4, sel='#libAllPlaceable', side='left', gap=14),
                 dict(n=5, sel='#libAllList .libitem', side='right', gap=18),
                 dict(n=6, sel='#libAllList .libitem .star', side='on', aty=0, dy=-2),
                 dict(n=7, sel='#libAllFoot', side='right', gap=18)]
        self.shot('add-all', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.locator('#libAllFilter').fill('')
        page.evaluate("viewer.setLibraryScope('map')")
        page.locator('#libraryClose').click()

    def prefabs(self):
        """The Prefabs tab with two prefabs saved from the demo's selections. The server's prefabs folder (beside its
        scratch projects folder) must be empty."""
        page = self.page
        for name, actors in (('Keg stack', (KEG_A, KEG_B, KEG_C)), ('Roadblock', (SUV, ATM))):
            self.select(*actors)
            page.evaluate("name => viewer.savePrefab(name)", name)
        page.wait_for_function("viewer.prefabApi.list().then(a => a.prefabs.length === 2 && a.prefabs.every(p => p.picture))", timeout=30000)
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.evaluate("viewer.setLibraryScope('prefabs')")
        page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
        page.wait_for_timeout(1200)
        marks = [dict(n=1, sel='#libScope button[data-value="prefabs"]', side='top', gap=22, at=0.5),
                 dict(n=2, sel='#prefabFilter', side='right', gap=18),
                 dict(n=3, sel='#prefabNew', side='on', aty=0, dy=-2),
                 dict(n=4, sel='#prefabSave', side='on', aty=0, dy=-2),
                 dict(n=5, sel='#prefabImport', side='on', aty=0, dy=-2),
                 dict(n=6, sel='#prefabList .libitem', side='right', gap=18),
                 dict(n=7, sel='#prefabList .libitem:nth-child(2) .prefabacts', side='right', gap=18),
                 dict(n=8, sel='#prefabFoot', side='right', gap=18)]
        self.shot('prefabs', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.evaluate("viewer.setLibraryScope('map')")
        page.locator('#libraryClose').click()

    def lights(self):
        page = self.page
        page.evaluate('viewer.setLightsShown(true)')
        light = page.evaluate("""at => { let best = null, d = Infinity;
          for (const r of viewer.lightRoots.values()) { const s = r.userData.source;
            if (s.role !== 'static' || s.kind !== 'spot' || s.channels || !s.bakedInto?.length) continue;
            const q = Math.hypot(...s.location.map((v, k) => v - at[k])); if (q < d) { d = q; best = s.id; } }
          viewer.select(null); viewer.select(best); return best; }""", SPOT_NEAR)
        if not light: raise SystemExit('no editable spot light on %s' % MAP)
        # its radius brought in to the floor under it, so that its handles are in the picture (undone after)
        page.locator('#lightRadius').fill('330')
        page.locator('#lightRadius').press('Enter')
        page.evaluate('document.activeElement?.blur()')
        page.keyboard.press('v')
        self.camera(*LIGHT_VIEW)
        self.settle(3500)
        by = {h['key']: h['screen'] for h in page.evaluate('viewer.lightHandles()')}
        marks = self.panel_rows('#inspector', [(5, '#lightColor'), (6, '#lightBrightness'), (7, '#lightInner'), (8, '#lightOn'),
                                               (9, '#lightReach'), (10, '#lightSolo')])
        marks.append(dict(n=1, sel='#editLights', side='right', gap=20))
        for n, key, side in ((2, 'radius', 'bottom'), (3, 'outer', 'left'), (4, 'inner', 'right')):
            marks.append(dict(n=n, rect=[by[key][0] - 5, by[key][1] - 5, 10, 10], side=side, gap=24, inset=3))
        self.shot('lights', marks, resize=0.75)
        page.keyboard.press('Control+z')
        page.evaluate('viewer.select(null)')
        page.evaluate('viewer.setLightsShown(false)')

    def landing_zones(self):
        """The Landing zones view: the Bar's own zone picked, with its gizmo and its panel."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate('viewer.setZonesShown(true)')
        zone = page.evaluate('viewer.zones()[0]')
        page.evaluate('id => viewer.pickZone(id)', zone['id'])
        x, y, z = zone['location']
        self.camera([x, y + 240, z - 64], [520, -1150, 820])
        self.settle(3000)
        # the picked zone's badge (each zone has one), at its place in the world
        badge = page.evaluate("""id => { let b = null; viewer.landingLayer.traverse(o => { if (o.userData.zoneBadge && o.userData.zoneId === id) b = o; });
                                         const p = b.getWorldPosition(b.position.clone()); return viewer.screenOf([p.x, p.z, p.y]); }""", zone['id'])
        frame = page.evaluate('p => viewer.screenOf(p)', [x, y, z])
        marks = [dict(n=1, sel='#editZones', side='right', gap=20),
                 dict(n=2, rect=[badge[0] - 18, badge[1] - 18, 36, 36], side='top', gap=26, inset=3),
                 dict(n=3, rect=[frame[0] - 8, frame[1] - 8, 16, 16], side='bottom', gap=110, inset=3)]
        rows = [(4, '#landingKind'), (5, '#landingLwr'), (6, '#landingCopy')]
        if page.locator('#landingPlay').is_visible(): rows.append((7, '#landingPlay'))
        marks += self.panel_rows('#landingPanel', rows)
        self.shot('landing-zones', marks, resize=0.75)
        page.evaluate('viewer.setZonesShown(false)')

    # --- the Effects view
    def effect_id(self, actor):
        found = self.page.evaluate("a => [...viewer.effectRoots.values()].find(r => r.userData.source.actor === a)?.userData.source.id", actor)
        if not found: raise SystemExit('%s is not among the effects of %s' % (actor, MAP))
        return found

    def marker(self, actor):
        """An effect's, sound's or flare's marker: a small rect round its screen point."""
        record = self.effect_id(actor)
        s = next((m['screen'] for m in self.page.evaluate('viewer.effectMarkers()') if m['id'] == record), None)
        if not s: raise SystemExit('%s has no marker on screen' % actor)
        return [s[0] - 7, s[1] - 7, 14, 14]

    def open_effects(self, actor, offset):
        """The Effects view with every floor shown, one effect picked and the camera on it."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#scenery button[data-value="full"]').click()
        page.locator('#floor button[data-value="all"]').click()
        page.evaluate('viewer.setEffectsShown(true)')
        self.zones = page.evaluate('viewer.landingLayer.visible')
        page.evaluate('viewer.landingLayer.visible = false')     # the zones' numbers would be taken for the marks
        record = self.effect_id(actor)
        page.evaluate('id => viewer.pickEffect(id)', record)
        self.camera(page.evaluate('id => viewer.effectState(id).at', record), offset)
        self.settle(3000)
        return {h['key']: h['screen'] for h in page.evaluate('viewer.lightHandles()')}

    def close_effects(self):
        page = self.page
        page.evaluate('viewer.pickEffect(null)')
        page.evaluate('viewer.setEffectsShown(false)')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', self.zones)
        page.locator('#scenery button[data-value="interior"]').click()
        page.locator('#floor button[data-value="1"]').click()

    def effects(self):
        """The Effects view on the car park: the taxi's idle sound picked, with its two spheres, their handles, its
        Wave preview and its values; an effect's, a sound's and a lens flare's markers round it."""
        handles = self.open_effects(TAXI_SOUND, SOUND_VIEW)
        marks = [dict(n=1, sel='#editEffects', side='right', gap=20)]
        for n, actor, side in ((2, WEBBING, 'bottom'), (3, SHOP_SOUND, 'top'), (4, FLARE, 'bottom')):
            marks.append(dict(n=n, rect=self.marker(actor), side=side, gap=34, inset=3))
        for n, key in ((5, 'radiusMax'), (6, 'radiusMin')):
            s = handles[key]
            marks.append(dict(n=n, rect=[s[0] - 6, s[1] - 6, 12, 12], side='bottom', gap=40, inset=3))
        marks += self.panel_rows('#effectPanel', [(7, '#effectWaves .waverow'), (8, '#effectValues .check'),
                                                  (9, '#effectValues .valueline'), (10, '#effectValues .valuepair')])
        self.shot('effects', marks, resize=0.75)
        self.close_effects()

    def effects_flyout(self):
        """The Effects view button hovered: its flyout with a switch for each kind."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editEffects').hover()
        page.wait_for_timeout(400)
        x, y, w, h = self.rect('#editEffects')
        fx, fy, fw, fh = self.rect('#effectsFlyout')
        self.shot('effects-flyout', clip=dict(x=x - 8, y=min(y, fy) - 10, width=fx + fw - x + 18, height=max(h, fh) + 20))
        page.mouse.move(WIDTH / 2, HEIGHT / 2)

    # --- the Spawns view
    def spawns(self):
        """The Spawns view on the Bar's ground floor: a pod picked, with its arrows and its panel (its values, what uses
        it, what the game does with it, Copy and Delete, its flags); another pod and a Meld point marked round
        it (no-spawn volumes have a shot of their own: spawns_volume)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        zones = page.evaluate('viewer.landingLayer.visible')
        page.evaluate('viewer.setSpawnsShown(true)')
        page.evaluate('viewer.landingLayer.visible = false')     # (the view shows the zones) a zone's number would be taken for a mark
        pod = page.evaluate('a => viewer.spawns().find(s => s.actor === a)', SPAWN_POD)
        if not pod: raise SystemExit('%s is not among the spawn points of %s' % (SPAWN_POD, MAP))
        page.evaluate('k => viewer.pickSpawn(k)', pod['key'])
        self.camera(*SPAWN_VIEW)
        self.settle(3000)
        top, bottom = self.rect('header')[3] + 40, self.rect('.dock')[1] - 30
        panel, rail = self.rect('#spawnPanel'), self.rect('#rail')
        spawns = page.evaluate('viewer.spawns()')
        at = next(s['screen'] for s in spawns if s['key'] == pod['key'])

        def nearest(kind):
            """The marker of a kind nearest the picked pod that shows in the picture, clear of the panel and the rail."""
            shown = [s['screen'] for s in spawns if s['kind'] == kind and s['marked'] and s['key'] != pod['key'] and s['screen']
                     and rail[0] + rail[2] + 60 < s['screen'][0] < panel[0] - 60 and top < s['screen'][1] < bottom]
            if not shown: raise SystemExit('no %s marker shows near %s' % (kind, SPAWN_POD))
            return min(shown, key=lambda p: (p[0] - at[0]) ** 2 + (p[1] - at[1]) ** 2)

        marks = [dict(n=1, sel='#editSpawns', side='right', gap=20),
                 dict(n=2, rect=[at[0] - 24, at[1] - 24, 48, 48], side='bottom', gap=70, inset=3)]
        for n, kind in ((3, 'pod'), (4, 'meld')):
            s = nearest(kind)
            marks.append(dict(n=n, rect=[s[0] - 10, s[1] - 10, 20, 20], side='top', gap=34, inset=3))
        marks += self.panel_rows('#spawnPanel', [(5, '#spawnInfo'), (6, '#spawnEdit .copyrow'), (7, '#spawnEdit label.check')])
        self.shot('spawns', marks, resize=0.75)
        page.evaluate('viewer.pickSpawn(null); viewer.setSpawnsShown(false)')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', zones)

    def spawns_volume(self):
        """A no-spawn volume picked in the Spawns view (the Bar's, round a parked van): its box, a side's white handle,
        its arrows, and its panel (its box in words, what the game does with it, Copy and Delete, what it keeps out)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        zones = page.evaluate('viewer.landingLayer.visible')
        page.evaluate('viewer.setSpawnsShown(true)')
        page.evaluate('viewer.landingLayer.visible = false')
        vol = page.evaluate('a => viewer.spawns().find(s => s.actor === a)', SPAWN_VOLUME)
        if not vol: raise SystemExit('%s is not among the spawn points of %s' % (SPAWN_VOLUME, MAP))
        page.evaluate('k => viewer.pickSpawn(k)', vol['key'])
        self.camera(*VOLUME_VIEW)
        self.settle(3000)
        b = vol['box']
        corners = page.evaluate('cs => cs.map(p => viewer.screenOf(p))', [[b[i], b[j], b[k]] for i in (0, 3) for j in (1, 4) for k in (2, 5)])
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        handles = page.evaluate('viewer.spawnVolumeHandles()')
        if not handles: raise SystemExit('%s shows no handles' % SPAWN_VOLUME)
        at = next(s['screen'] for s in page.evaluate('viewer.spawns()') if s['key'] == vol['key'])
        hx, hy = handles['x1']
        marks = [dict(n=1, rect=[min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], side='top', gap=30, frame=True),
                 dict(n=2, rect=[hx - 10, hy - 10, 20, 20], side='bottom', gap=40, inset=3),
                 dict(n=3, rect=[at[0] - 24, at[1] - 24, 48, 48], side='left', gap=90, inset=3)]
        marks += self.panel_rows('#spawnPanel', [(4, '#spawnInfo'), (5, '#spawnEdit .copyrow'), (6, '#spawnEdit label.check')])
        self.shot('spawns-volume', marks, resize=0.75)
        page.evaluate('viewer.pickSpawn(null); viewer.setSpawnsShown(false)')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', zones)

    def spawns_flyout(self):
        """The Spawns view button hovered: its flyout with a switch for each family and Scripted drop-ins land where
        placed."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editSpawns').hover()
        page.wait_for_timeout(400)
        x, y, w, h = self.rect('#editSpawns')
        fx, fy, fw, fh = self.rect('#spawnsFlyout')
        self.shot('spawns-flyout', clip=dict(x=x - 8, y=min(y, fy) - 10, width=fx + fw - x + 18, height=max(h, fh) + 20))
        page.mouse.move(WIDTH / 2, HEIGHT / 2)

    def effect_values(self):
        """An alien vapour pod's smoke picked: its likeness, its size handle and its panel with its values."""
        page = self.page
        handles = self.open_effects(POD_SMOKE, SMOKE_VIEW)
        page.evaluate("document.getElementById('effectAbout').open = true")      # (its sentences, folded by default)
        s = handles['size']
        marks = [dict(n=1, rect=self.marker(POD_SMOKE), side='top', gap=150, dx=70, inset=3),
                 dict(n=2, rect=[s[0] - 6, s[1] - 6, 12, 12], side='bottom', gap=60, inset=3)]
        marks += self.panel_rows('#effectPanel', [(3, '#effectChips'), (4, '#effectInfo'), (5, '#effectKind'),
                                                  (6, '#effectValues .check'), (7, '#effectValues .valueline'),
                                                  (8, '#effectValues .effectvalue'),
                                                  (9, '#effectValues .effectvalue:has(input[type=color])')])
        self.shot('effect-values', marks, resize=0.75)
        self.close_effects()

    def add_effects(self):
        """All maps with its Kind set to the fires: each row's picture is the effect's likeness, and the pointer on
        the first row plays it in the pane beside the panel. Put back after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.evaluate("viewer.setLibraryScope('all')")
        page.wait_for_function('viewer.library.ready()', timeout=120000)
        kind, sort = page.locator('#libAllKind').input_value(), page.locator('#libAllSort').input_value()
        page.locator('#libAllKind').select_option('fx:Fire')
        page.locator('#libAllSort').select_option('maps')
        page.locator('#libAllFilter').fill('P_Fire')
        page.wait_for_selector('#libAllList .libitem')
        page.wait_for_function("[...document.querySelectorAll('#libAllList .libitem canvas')].slice(0, 6).every(c => c.dataset.drawn)", timeout=180000)
        first = page.locator('#libAllList .libitem').first
        first.hover()
        page.wait_for_function('viewer.likenessPane().shown && viewer.likenessPane().particles > 0', timeout=60000)
        page.wait_for_timeout(2500)
        marks = [dict(n=1, sel='#libAllKind', side='on', aty=0, dy=-2),
                 dict(n=2, sel='#libAllList .libitem canvas', side='left', gap=14),
                 dict(n=3, sel='#libAllList .libitem', side='right', gap=18),
                 dict(n=4, sel='#likenessCanvas', side='right', gap=18, at=0.3),
                 dict(n=5, sel='#likenessText', side='right', gap=18)]
        self.shot('add-effects', marks, clip=self.around('#rail', '#library', '#likenessPane', pad=(8, 30, 44, 8)))
        page.mouse.move(WIDTH / 2, HEIGHT / 2)
        page.locator('#libAllFilter').fill('')
        page.locator('#libAllKind').select_option(kind)
        page.locator('#libAllSort').select_option(sort)
        page.evaluate("viewer.setLibraryScope('map')")
        page.locator('#libraryClose').click()

    def map_grid(self):
        """Map grid: the play area's handles on the Bar as it is, and the panel."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editGrid').click()
        b = page.evaluate('viewer.data.playableBounds')
        cx, cy = (b['min'][0] + b['max'][0]) / 2, (b['min'][2] + b['max'][2]) / 2
        self.camera([cx, cy, 0], [2300, -4200, 3600])
        self.settle(3000)
        marks = [dict(n=1, sel='#editGrid', side='right', gap=20)]
        for n, axis, side in ((2, 0, 'right'), (3, 1, 'top'), (4, 2, 'top')):
            at = page.evaluate('a => viewer.gridHandleAt(a)', axis)
            if at is None: continue
            s = page.evaluate('p => viewer.screenOf(p)', at)
            marks.append(dict(n=n, rect=[s[0] - 8, s[1] - 8, 16, 16], side=side, gap=34, inset=3))
        marks += self.panel_rows('#gridPanel', [(5, '#gridSize'), (6, '#gridGround'), (7, '#gridOwn')])
        self.shot('map-grid', marks, resize=0.75)
        page.locator('#gridDone').click()

    def view_options(self):
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#viewButton').click()
        page.wait_for_timeout(400)
        rows = [(1, '#lighting'), (2, '#exposure'), (3, '#flyKeys'), (4, '#moveSpeed'), (5, '#turnSpeed'), (6, '#dragSpeed'),
                (7, '#areaToggle'), (8, '#reachToggle'), (9, '#skyToggle'), (10, '#playAreaToggle'), (11, '#grid'),
                (12, '#floorTiles'), (13, '#likenessToggle'), (14, '#wire'), (15, '#hideHelpers'), (16, '#statsToggle')]
        hidden = [s for _, s in rows if not page.locator(s).is_visible()]
        if hidden: raise SystemExit('View options lacks %s on %s: the guide numbers them all' % (', '.join(hidden), MAP))
        self.shot('view-options', self.panel_rows('#viewOptions', rows), clip=self.around('#viewButton', '#viewOptions', pad=(44, 6, 8, 12)))
        self.close_pops()

    def build(self):
        page = self.page
        page.keyboard.press('Control+b')
        page.wait_for_selector('#buildForm')
        page.wait_for_timeout(400)
        marks = [dict(n=1, sel='#buildBake', side='left', gap=30),
                 dict(n=2, sel='#buildOptionsCancel', side='bottom', gap=20),
                 dict(n=3, sel='#buildOptionsOk', side='bottom', gap=20)]
        self.shot('build', marks, clip=self.around('#buildForm', pad=(40, 12, 12, 34)))
        page.keyboard.press('Escape')

    def floors(self):
        """The same view with every floor (the roof closed) and cut down to floor 1."""
        page = self.page
        page.evaluate('viewer.select(null)')
        self.camera(*BAR_VIEW)
        clip = dict(x=250, y=120, width=940, height=640)
        for value in ('all', '1'):
            page.locator('#floor button[data-value="%s"]' % value).click()
            self.settle(3000)
            self.shot('floors-%s' % value, clip=clip, resize=0.5)


    def buildings(self):
        """The Buildings view: a box being drawn over the car park, then that box with a second floor pasted on top
        of it and selected (its handles, the gizmo, the panel). Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#scenery button[data-value="full"]').click()
        page.locator('#floor button[data-value="all"]').click()
        origin = page.evaluate('viewer.data.tileGrid.origin')
        spot = [origin[0] + 96 * 6, origin[1] + 96 * 6, 0]
        self.camera([spot[0] + 40, spot[1] + 60, 110], [-560, -900, 760])
        page.keyboard.press('Shift+B')
        self.settle(2500)
        # a new box, drawn over three by three tiles: the picture is taken with the button still held
        a = page.evaluate('p => viewer.screenOf(p)', [spot[0] - 96, spot[1] - 96, 0])
        b = page.evaluate('p => viewer.screenOf(p)', [spot[0] + 150, spot[1] + 150, 0])
        page.keyboard.press('n')
        page.mouse.move(*a)
        page.mouse.down()
        page.mouse.move((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, steps=4)
        page.mouse.move(*b, steps=4)
        page.wait_for_timeout(600)
        self.shot('buildings-draw', [
            dict(n=1, sel='#editBuildings', side='right', gap=20),
            dict(n=2, sel='#volumeNew', side='left', gap=22),
            dict(n=3, rect=[a[0] - 5, a[1] - 5, 10, 10], side='left', gap=26),
            dict(n=4, rect=[b[0] - 5, b[1] - 5, 10, 10], side='right', gap=26),
            dict(n=5, sel='#dragHint', side='bottom', gap=18),
        ], resize=0.75)
        page.mouse.up()
        page.wait_for_function('viewer.volumeRoots.size >= 1 && viewer.gizmo.picks().ids.length === 1')
        # a second floor: a copy pasted on top, which is then the selected box
        page.keyboard.press('Control+c')
        page.keyboard.press('Control+v')
        # (the map's own buildings a project changes are listed too, with `replaces`)
        page.wait_for_function("(own => own.length === 1 && own[0].floors.length === 2)(viewer.buildings().filter(b => !b.replaces))")
        page.evaluate("document.getElementById('dragHint').hidden = true")
        self.settle(1500)
        handle = {key: page.evaluate('k => viewer.volumeHandle(k)', key) for key in ('z1', 'x1')}
        pose = page.evaluate('viewer.screenOf(viewer.gizmo.pose().location)')
        marks = self.panel_rows('#volumePanel', [(4, '#volumeBottom'), (5, '#volumeBuilding'), (6, '#volumeName'), (7, '#volumeNote'),
                                                 (8, '#volumeCopy')])
        # the cursor's floors: the yellow line where the second one starts, at the selected box's near corner
        line = page.evaluate("""() => { const b = viewer.volumeBox(viewer.volumeRoots.get(viewer.gizmo.picks().active));
          return viewer.screenOf([b[3] + 14, (b[1] + b[4]) / 2, 210]); }""")
        marks += [dict(n=9, rect=[line[0] - 5, line[1] - 5, 10, 10], side='right', gap=26)]
        marks += [dict(n=1, rect=[handle['z1'][0] - 5, handle['z1'][1] - 5, 10, 10], side='left', gap=26),
                  dict(n=2, rect=[handle['x1'][0] - 5, handle['x1'][1] - 5, 10, 10], side='right', gap=26),
                  dict(n=3, rect=[pose[0] - 6, pose[1] - 6, 12, 12], side='left', gap=60, dy=30)]
        self.shot('buildings-view', marks, resize=0.75)
        for _ in range(2): page.keyboard.press('Control+z')
        page.keyboard.press('Shift+B')
        page.evaluate('viewer.select(null)')
        self.close_pops()


    def cover_blocks(self):
        """Cover blocks and an invisible floor on the car park: a high block (selected, with its handles and panel), a
        low one and a floor, each placed from the piece list and sized as its handles would (viewer.setCover, one undo
        step). Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#scenery button[data-value="full"]').click()
        page.locator('#floor button[data-value="all"]').click()
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        origin = page.evaluate('viewer.data.tileGrid.origin')
        spot = [origin[0] + 96 * 6, origin[1] + 96 * 2, 0]      # the pavement south of the car park
        self.camera([spot[0], spot[1], 40], [-420, -760, 640])
        zones = page.evaluate('viewer.landingLayer.visible')
        page.evaluate('viewer.landingLayer.visible = false')     # the zones' marks would be taken for the blocks'
        snap = page.evaluate('viewer.gizmo.snap')
        page.evaluate("viewer.setSnapMode('tile')")               # placed on the tiles
        self.settle(2500)
        page.locator('#editAdd').click()
        page.evaluate("viewer.setLibraryScope('map')")
        page.locator('#libKind').select_option('Invisible')
        page.wait_for_selector('.libitem[data-id="cover-block"]')

        def place(entry, at, cover):
            count = page.evaluate('viewer.roots.size')
            page.locator('.libitem[data-id="%s"]' % entry).click()
            x, y = page.evaluate('p => viewer.screenOf(p)', at)
            page.mouse.move(x - 3, y - 2)
            page.mouse.move(x, y)
            page.wait_for_function('viewer.placing()?.ghost.visible')
            page.mouse.click(x, y)
            page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
            active = page.evaluate('viewer.gizmo.active')
            page.evaluate('([id, c]) => viewer.setCover(id, c)', [active, cover])
            return active

        floor = place('invisible-floor', [spot[0] + 96 * 2, spot[1] - 96, 0], dict(type='floor', size=[192, 192]))
        low = place('cover-block', [spot[0] - 96, spot[1] + 96, 0], dict(type='low', size=[288, 96], heights=[-12, 84]))
        high = place('cover-block', [spot[0] - 96 * 3, spot[1] - 96, 0], dict(type='high', size=[192, 96], heights=[-12, 192]))
        page.locator('#libraryClose').click()
        page.evaluate('id => viewer.select(id)', high)
        page.keyboard.press('v')
        self.settle(2500)
        middle = "id => { const b = viewer.pieceBox(id); return viewer.screenOf([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, b[5]]); }"
        marks = []
        for n, piece, side in ((1, high, 'top'), (2, low, 'top'), (3, floor, 'right')):
            s = page.evaluate(middle, piece)
            marks.append(dict(n=n, rect=[s[0] - 6, s[1] - 6, 12, 12], side=side, gap=40, inset=3))
        handle = page.evaluate('viewer.coverHandles()')['+z']
        marks.append(dict(n=4, rect=[handle[0] - 8, handle[1] - 8, 16, 16], side='right', gap=40, inset=3))
        marks += self.panel_rows('#inspector', [(5, '#coverHeight'), (6, '#coverSize')])
        self.shot('cover-blocks', marks, resize=0.75)
        while page.evaluate('viewer.gizmo.undoDepth()') > steps: page.keyboard.press('Control+z')
        page.evaluate('viewer.select(null)')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', zones)
        page.evaluate('mode => viewer.setSnapMode(mode)', snap)

    def clear_map(self):
        """The Clear map window on the Bar, with its counts. Cancelled: nothing is cleared."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate("document.getElementById('projectClear').click()")
        page.wait_for_selector('#clearMap:not([hidden])')
        page.wait_for_function("document.getElementById('clearMapPlan').textContent.trim() !== ''")
        page.wait_for_timeout(400)
        self.shot('clear-map', clip=self.around('#clearMapForm', pad=(12, 12, 12, 12)))
        page.locator('#clearMapCancel').click()

    def missions(self):
        """The Missions window on the Bar, Terror ticked as an added kind. Cancelled: nothing changes."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate("document.getElementById('projectMissions').click()")
        page.wait_for_selector('#missionsDialog:not([hidden]) #missionsList label')
        terror = page.locator('#missionsList label', has_text='Terror').first
        terror.locator('input').check()
        page.wait_for_timeout(400)
        base = page.locator('#missionsList label').first
        marks = [dict(n=1, rect=self.box(base), side='left', gap=22),
                 dict(n=2, rect=self.box(terror), side='left', gap=22),
                 dict(n=3, sel='#missionsOk', side='bottom', gap=20)]
        self.shot('missions', marks, clip=self.around('#missionsForm', pad=(40, 12, 12, 34)))
        page.locator('#missionsCancel').click()

    def squad(self):
        """Settings, Test squad setup: the default six, the first unit open. Cancelled: nothing is saved."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#settingsButton').click()
        page.locator('#settingsSquad').click()
        page.wait_for_function("document.querySelectorAll('#squadUnits > *').length >= 6", timeout=60000)
        page.wait_for_timeout(800)
        field = """t => { const f = [...document.querySelectorAll('#squadUnit .squadfield')].find(f => f.querySelector('span')?.textContent.trim() === t);
          const b = f?.getBoundingClientRect(); return b && [b.left, b.top, b.width, b.height]; }"""
        at = {t: page.evaluate(field, t) for t in ('Kind', 'First name', 'Armour', 'Weapons')}
        missing = [t for t, r in at.items() if not r]
        if missing: raise SystemExit('the squad panel has no %s field' % ', '.join(missing))
        marks = [dict(n=1, sel='#squadUnits', side='left', gap=22, at=0.25),
                 dict(n=2, sel='#squadAdd', side='top', gap=20),
                 dict(n=3, rect=at['Kind'], side='right', gap=22),
                 dict(n=4, rect=at['First name'], side='top', at=0.92, gap=12),
                 dict(n=5, rect=at['Armour'], side='right', gap=22),
                 dict(n=6, rect=at['Weapons'], side='right', gap=22),
                 dict(n=7, sel='#squadWide', side='bottom', gap=20),
                 dict(n=8, sel='#squadExport', side='bottom', gap=20),
                 dict(n=9, sel='#squadSave', side='bottom', gap=20)]
        self.shot('squad', marks, clip=self.around('#squadForm', pad=(40, 14, 40, 40)), resize=0.75)
        page.locator('#squadCancel').click()

    # --- the project manager: more projects, two quick builds, then a queue of full builds
    def box(self, locator):
        b = locator.bounding_box()
        if not b: raise SystemExit('nothing shows for %s' % locator)
        return [b['x'], b['y'], b['width'], b['height']]

    def nudge(self, actor, dx=96):
        """Moves a piece along X by typing its position (one edit)."""
        page = self.page
        self.select(actor)
        x = float(page.locator('#posX').input_value())
        page.locator('#posX').fill('%g' % (x + dx))
        page.locator('#posX').press('Enter')
        page.evaluate('viewer.select(null)')

    def save_project_as(self, name):
        page = self.page
        page.evaluate("document.getElementById('projectSaveAs').click()")
        page.wait_for_selector('#fileDialog:not([hidden])')
        page.locator('#fileName').fill(name)
        page.wait_for_function("document.getElementById('fileOutput').textContent.includes('Builds as')", timeout=20000)
        page.locator('#fileOk').click()
        page.wait_for_function('n => viewer.project()?.name === n && !viewer.project().dirty', arg=name, timeout=30000)
        self.close_pops()

    def quick_build(self):
        """Builds the open project without baking, and closes the build window."""
        page = self.page
        page.keyboard.press('Control+b')
        page.wait_for_selector('#buildForm', state='visible')
        if page.locator('#buildBake').is_checked(): page.locator('#buildBake').uncheck()
        page.locator('#buildOptionsOk').click()
        page.wait_for_function("""() => { const t = document.getElementById('buildTitle').textContent;
          return !document.getElementById('buildModal').hidden && !document.getElementById('buildClose').hidden && !t.startsWith('Building'); }""",
                               timeout=300000)
        title = page.locator('#buildTitle').text_content()
        page.locator('#buildClose').click()
        if not title.startswith('Built'): raise SystemExit('a build for the project manager failed: %s' % title)

    def manager(self):
        """The project manager with four projects: the demo, two quick builds (one saved again since) and one never
        built, the demo and the unbuilt one ticked and building as a queue of full builds, the demo done and the other
        building. The queue is stopped and cleared after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        for k, (name, actor) in enumerate(MORE_PROJECTS):
            self.nudge(actor)
            self.save_project_as(name)
            if k < 2: self.quick_build()
            if k == 1:                       # saved again after its build: out of date
                self.nudge(actor)
                page.keyboard.press('Control+s')
                page.wait_for_function('!viewer.project().dirty', timeout=30000)
        page.evaluate("document.getElementById('projectManage').click()")
        page.wait_for_selector('#managerList .mrow')
        page.wait_for_timeout(600)
        for name in (PROJECT, MORE_PROJECTS[-1][0]):
            page.locator('#managerList .mrow', has_text=name).first.click()
        page.locator('#managerBuild').click()
        page.wait_for_function("/Building 2 of 2/.test(document.getElementById('managerQueue').textContent)", timeout=600000)
        page.wait_for_timeout(5000)
        row = page.locator('#managerList .mrow', has_text=PROJECT).first
        marks = [dict(n=1, sel='#managerSearch', side='top', gap=20, at=0.3),
                 dict(n=2, sel='#managerShow', side='top', gap=20),
                 dict(n=3, sel='#managerSort', side='top', gap=20),
                 dict(n=4, rect=self.box(row.locator('.mbuild')), side='left', gap=22),
                 dict(n=5, sel='#managerPicked .pmitem', side='right', gap=22),
                 dict(n=6, sel='#managerPicked .pmseg', side='right', gap=22),
                 dict(n=7, sel='#managerQueue', side='left', gap=22, at=0.3),
                 dict(n=8, sel='#managerBuild', side='top', gap=20),
                 dict(n=9, sel='#managerProjectFiles', side='left', gap=18)]
        self.shot('manager', marks, clip=self.around('#managerForm', pad=(40, 30, 40, 40)), resize=0.75)
        page.locator('#managerQueueStop').click()
        page.wait_for_function("!document.getElementById('managerQueueClear').hidden && !document.getElementById('managerQueueClear').disabled",
                               timeout=120000)
        page.locator('#managerQueueClear').click()
        page.locator('#managerClose').click()

    def save_as(self):
        """Save as… with a new name typed: the projects listed, and what it would build as. Cancelled."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate("document.getElementById('projectSaveAs').click()")
        page.wait_for_selector('#fileDialog:not([hidden])')
        page.locator('#fileName').fill('Rooftop fight')
        page.wait_for_function("document.getElementById('fileOutput').textContent.includes('RooftopFight')", timeout=20000)
        page.wait_for_timeout(400)
        marks = self.panel_rows('#fileForm', [(1, '#fileList'), (2, '#fileName'), (3, '#fileShow'), (4, '#fileOutput')])
        self.shot('save-as', marks, clip=self.around('#fileForm', pad=(44, 12, 12, 12)))
        page.locator('#fileCancel').click()

    def mission_objects(self):
        """A council bomb's objects on its own map (another map: this shot comes last): the bomb picked, with its
        arrows and its panel, the power nodes, the drop-in points and the pods round it."""
        page = self.page
        page.goto('%s?map=%s' % (self.server, BOMB_MAP))
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=300000)
        page.wait_for_timeout(1500)
        index = page.evaluate('s => viewer.data.missions.findIndex(m => (m.streams ?? []).includes(s))', BOMB_STREAM)
        if index < 0: raise SystemExit('%s has no mission with %s' % (BOMB_MAP, BOMB_STREAM))
        page.locator('#mission').select_option(str(index))
        page.wait_for_timeout(1500)
        page.evaluate('viewer.setNormalSpawns(true)')       # (the Normal button's Spawn points and objectives)
        page.locator('#floor button[data-value="1"]').click()
        objects = page.evaluate('s => viewer.data.streams[s].missionObjects', BOMB_STREAM)
        bomb = next(o for o in objects if o['kind'] == 'bomb')
        page.evaluate('o => viewer.setPickedMission(o)', dict(stream=BOMB_STREAM, actor=bomb['actor']))
        at = page.evaluate('viewer.missionGizmo().at')
        self.camera([at[0] + 150, at[1] - 150, at[2]], [900, -1500, 1500])
        self.settle(3000)
        top, bottom = self.rect('header')[3] + 40, self.rect('.dock')[1] - 30
        panel = self.rect('#spawnPanel')

        def nearest(kind):
            """The object of a kind nearest the bomb that shows in the picture, clear of the panel."""
            best = None
            for o in objects:
                if o['kind'] != kind: continue
                s = page.evaluate('p => viewer.screenOf(p)', o['location'])
                if not (90 < s[0] < panel[0] - 40 and top < s[1] < bottom): continue
                d = sum((a - b) ** 2 for a, b in zip(o['location'], bomb['location']))
                if best is None or d < best[0]: best = (d, s)
            if not best: raise SystemExit('no %s of %s shows in the picture' % (kind, BOMB_STREAM))
            return best[1]
        g = page.evaluate('p => viewer.screenOf(p)', at)
        marks = [dict(n=1, sel='#missionPick', side='bottom', gap=20),
                 dict(n=2, rect=[g[0] - 8, g[1] - 8, 16, 16], side='left', gap=60, dy=-30)]
        for n, kind in ((3, 'powerNode'), (4, 'dropIn'), (5, 'pod')):
            s = nearest(kind)
            marks.append(dict(n=n, rect=[s[0] - 6, s[1] - 6, 12, 12], side='bottom', gap=34, inset=3))
        marks.append(dict(n=6, sel='#spawnPanel', frame=True, side='left', gap=3, at=0.1))
        self.shot('mission-objects', marks, resize=0.75)
        page.evaluate('viewer.setPickedMission(null)')


def prefab_test_shot(browser, server, out):
    from PIL import Image
    page = browser.new_page(viewport=dict(width=WIDTH, height=HEIGHT), device_scale_factor=SCALE)
    typical(page)
    page.goto(server.split('?')[0] + '?prefab=new')
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden")
    page.evaluate('viewer.addVolumes([{box:[-192,0,0,0,192,176],floor:0}])')
    page.locator('#projectButton').click()
    page.locator('#prefabTest').click()
    png = page.locator('#buildForm').screenshot()
    image = Image.open(io.BytesIO(png)).convert('RGB')
    image.save(out / 'prefab-test.webp', 'WEBP', quality=QUALITY, method=6)
    print('prefab-test    %4d x %-4d' % image.size, flush=True)
    page.close()


# the manager runs builds and leaves its projects saved, and mission-objects opens another map: they come last
ORDER = ('window', 'header', 'rail', 'normal-flyout', 'dock', 'project-menu', 'map-browser', 'piece-panel', 'flags', 'box-select', 'group-align', 'add', 'add-all', 'prefabs', 'prefab-test', 'lights',
         'landing-zones', 'effects', 'effects-flyout', 'effect-values', 'add-effects', 'spawns', 'spawns-volume', 'spawns-flyout', 'map-grid', 'view-options', 'build', 'floors', 'buildings', 'cover-blocks', 'clear-map', 'missions', 'squad',
         'manager', 'save-as', 'mission-objects')


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--server', default='http://127.0.0.1:8790/', help='the test server (default: %(default)s)')
    a.add_argument('--out', type=Path, default=HERE / 'shots', help='where the pictures go (default: shots, beside this script)')
    a.add_argument('--only', default='', help='only these shots, by name, comma-separated (default: all)')
    args = a.parse_args()
    only = [n for n in args.only.split(',') if n]
    unknown = [n for n in only if n not in ORDER]
    if unknown: a.error('no shot called %s (they are %s)' % (', '.join(unknown), ', '.join(ORDER)))
    args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        if not only or 'prefab-test' in only:
            prefab_test_shot(browser, args.server, args.out)
        if only == ['prefab-test']:
            browser.close()
            return
        page = browser.new_page(viewport=dict(width=WIDTH, height=HEIGHT), device_scale_factor=SCALE)
        typical(page)
        page.goto('%s?map=%s' % (args.server, MAP))
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
        page.wait_for_timeout(1500)
        shots = Shots(page, args.out, only)
        shots.server = args.server.split('?')[0]
        shots.demo_project()
        for name in ORDER:
            if name != 'prefab-test' and (not only or name in only): getattr(shots, name.replace('-', '_'))()
        browser.close()


if __name__ == '__main__':
    main()
