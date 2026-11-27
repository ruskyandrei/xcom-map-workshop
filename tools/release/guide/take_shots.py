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
  python tools/release/guide/take_shots.py --out <folder> [--server http://127.0.0.1:8790/] [--only window,header]

The scratch projects folder must be empty (the demo project is saved under a fixed name), and so must the prefabs
folder beside it (the Map menu's shot saves two, which the Prefabs tab and the Open window's Prefabs side show, and the
prefab builder's shot a third, which it opens). It needs the Bar exported in the server's cache (the mission objects' shot opens
URB_SlaughterhouseA and the diagonal cover shot CSmallScout_Farm, each read from the game on its first open),
Playwright (pip install playwright; it drives the installed Edge) and Pillow. The whole run takes about five minutes,
most of it the manager's builds.

The Game look's shots (looks, map-sun, sun-marker, view-options) need the Bar's export to carry its baked light (export
44 or later) and the library read (the time of day's skies are pieces of other maps). view-options opens the demo
project again and builds it with baking (a minute or two) unless its last Build baked, so that View options names
that Build: it comes after the project manager's shot, whose queue may have baked it already.

Some shots take more than one picture: project-menu also the Map menu and the Game menu (map-menu, game-menu),
diagonal also the Add panel's new mark (diagonal-add), prefab-builder the Prefab button's menu and the Add panel's
This prefab tab (prefab-menu, this-prefab), looks the Bar in the Neutral look, the Game look and the Game look at noon
(look-neutral, look-game, look-noon), map-sun the Map settings window's Fog and colour section too (fog-colour), and
made-walls also the look picker (look-picker), whose cards' pictures the page draws and the server keeps, so a
first run on a cache without them waits until every wall look's picture is drawn (some hundreds: minutes), and the
picture shows the picker without its "Drawing pictures" count. made-walls and texture-mapping each draw the same two
walls under fine snap, meeting in a mitred corner (made_corner), and undo them after.

The server's answers that would name a folder of this computer are replaced by a usual install's (typical()).
"""
import argparse
import io
from pathlib import Path
from urllib.parse import urlsplit

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
# the prefabs the Add panel's Prefabs tab and the Open window show, and the one the prefab builder's shot opens (saved
# there, after the others: three kegs, a claw machine and a pool table, for its This prefab tab's rows)
PREFABS = (('Keg stack', (KEG_A, KEG_B, KEG_C)), ('Roadblock', (SUV, ATM)))
BUILDER_PREFAB = ('Games corner', (KEG_A, KEG_B, KEG_C, CLAW_MACHINE, POOL_TABLE))
# cameras, in game units: what the camera looks at, and its offset from there
BAR_VIEW = ([150, 640, 20], [600, -1450, 1250])
# the Effects view's shots: the taxi's idle sound picked in the car park, with a webbing effect, the shop's sound and a
# lens flare marked round it; an alien vapour pod's smoke and its values; the fires of the other maps in the Add panel
TAXI_SOUND, SHOP_SOUND = ACTOR % 'AmbientSoundSimple_3', ACTOR % 'AmbientSoundSimple_2'
WEBBING, POD_SMOKE, FLARE = ACTOR % 'Emitter_75', ACTOR % 'Emitter_15', ACTOR % 'LensFlareSource_8'
SOUND_VIEW, SMOKE_VIEW = [700, -1500, 1100], [420, -800, 560]
LIGHT_VIEW = ([375, 300, 60], [500, -900, 700])
# the looks' shots: the Bar's front and its car park from above, no sky in the picture
LOOK_VIEW = ([100, -300, 20], [1100, -1300, 1300])
# the Spawns view's shot: a pod of the Bar's west room picked, with another pod, Meld points and a no-spawn volume
# round it; and a no-spawn volume picked (the one round the van in the street), with its handles
SPAWN_POD = ACTOR % 'XComAlienPod_Abduction_2'
SPAWN_VIEW = ([-1150, 650, 17], [480, -1180, 1000])
SPAWN_VOLUME = ACTOR % 'XComNoSpawnVolume_0'
VOLUME_VIEW = ([-560, -480, 100], [620, -780, 820])
SPOT_NEAR = [375, 245, 297]
# the Diagonal cover view's shots: the farm's crashed small scout, whose hull corners have eight marks of the map; at
# its south-east corner, by tile (x, y, level): the hull corner's mark (changed and picked), the next one as the map has
# it, and a hull tile with no mark, where a new one goes. The view looks north, so east is on the left; the corners by
# their index in diagonal_marks.js's CORNERS, the one added to the picked mark with its dot clear of the mark's gizmo
# (whose arrows run east and west, north, south and up)
FARM = 'CSmallScout_Farm'
PICKED_MARK, MAP_MARK, NEW_MARK = [51, 12, 0], [49, 10, 0], [49, 12, 0]
PICKED_CORNER, NEW_CORNER = 0, 1                 # north-west (up and right in the view), south-east
DIAGONAL_VIEW = ([2250, -2440, -117], [0, -560, 760])
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
        # (the rest of the answer names no folder: the missions' kinds, the save key, the test squad in a few words)
        answer = route.fetch()
        body = answer.json()
        body.update(
            lwr=dict(setting=GAME_FOLDER, folder=GAME_FOLDER, note=GAME_FOLDER, kind='Long War Rebalance'),
            install=dict(folder=GAME_FOLDER, note=GAME_FOLDER, source='the game install', sameAsLwr=True, ready=True, why=None),
            launch=dict(how='steam', why=None),
            game=dict(installed=[], intro=None, playFile=False, configKept=False, lastPlay=None, anything=False))
        body.pop('gameError', None)
        route.fulfill(response=answer, json=body)

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
        controls = ('#projectButton', '#mapButton', '#editCount', '#editUndo', '#editRedo', '#editResetAll', '#projectBuild',
                    '#projectPlay', '#playButton', '#settingsButton', '#notesButton', '#viewButton', '#helpButton')
        marks = [dict(n=k + 1, sel=s, side='bottom', gap=17) for k, s in enumerate(controls)]
        # in two halves, the empty middle left out, so that both show at their full size in the guide
        h = self.rect('header')[3] + 32
        last = self.rect('#missionPick') if self.page.locator('#missionPick').is_visible() else self.rect('#mapButton')
        count = self.rect('#editCount')
        self.shot('header-left', marks, clip=dict(x=0, y=0, width=last[0] + last[2] + 16, height=h))
        self.shot('header-right', marks, clip=dict(x=count[0] - 16, y=0, width=WIDTH - count[0] + 16, height=h))

    def rail(self):
        self.page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the Views button, whose list shows under the pointer)
        self.page.wait_for_timeout(300)
        controls = ('#editOff', '#editMove', '#editRotate', '#editBox', '#editAdd', '#viewsButton', '#editSpace', '#editPivot',
                    '#editSnap', '#editLinked', '#selected')
        marks = [dict(n=k + 1, sel=s, side='right', gap=20) for k, s in enumerate(controls)]
        self.shot('rail', marks, clip=self.around('#rail', pad=(8, 8, 40, 8)))

    def open_views(self):
        """The Views button clicked: its list kept open (pinned) with the pointer off it."""
        page = self.page
        page.locator('#viewsButton').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)
        page.wait_for_selector('#viewsFlyout', state='visible')
        page.wait_for_timeout(400)

    def close_views(self):
        page = self.page
        page.locator('#viewsButton').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)
        page.wait_for_selector('#viewsFlyout', state='hidden')

    def views_list(self):
        """The Views button's list, kept open by a click: a row for each view, the Normal view on with its four switches
        under its row, and Map grid."""
        page = self.page
        page.evaluate('viewer.select(null)')
        self.open_views()
        rows = [(1, '#editNormal'), (2, '#normalFlyout'), (3, '#editBuildings'), (4, '#editLights'), (5, '#editZones'),
                (6, '#editEffects'), (7, '#editSpawns'), (8, '#editDiagonal'), (9, '#editGrid')]
        self.shot('views-list', self.panel_rows('#viewsFlyout', rows, side='right'),
                  clip=self.around('#rail', '#viewsFlyout', pad=(8, 8, 44, 8)))
        self.close_views()

    def view_switches(self, name, switch, sub):
        """The Views list kept open with a view on (its switch, a test hook): that view's switches (sub) under its row."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate('s => viewer[s](true)', switch)
        self.open_views()
        page.wait_for_selector(sub, state='visible')
        self.shot(name, clip=self.around('#rail', '#viewsFlyout', pad=(8, 8, 8, 8)))
        self.close_views()
        page.evaluate('s => viewer[s](false)', switch)

    def dock(self):
        self.page.evaluate('viewer.select(null)')
        marks = [dict(n=k + 1, sel=s, side='top', gap=17) for k, s in enumerate(('#frame', '#lighting', '#scenery', '#floor'))]
        self.shot('dock', marks, clip=self.around('.dock', pad=(60, 40, 60, 10)))

    def project_menu(self):
        page = self.page
        page.locator('#projectButton').click()
        page.wait_for_selector('#projectRecent > *')
        page.wait_for_timeout(600)
        rows = [(1, '#projectInfo'), (2, '#projectSave'), (3, '#projectSaveAs'), (4, '#projectLoad'), (5, '#projectClose'),
                (6, '#projectRecent'), (7, '#projectManage')]
        self.shot('project-menu', self.panel_rows('#projectMenu', rows, side='right'),
                  clip=self.around('#projectButton', '#projectMenu', pad=(10, 6, 44, 12)))
        self.close_pops()
        self.save_prefabs(*PREFABS)            # (Open's A prefab… counts them)
        page.locator('#mapButton').click()
        page.wait_for_function("/^[1-9]/.test(document.getElementById('openPrefabsCount').textContent)")     # (the library's count)
        page.wait_for_timeout(300)
        # (Open's two buttons stand side by side: one mark for the pair)
        rows = [(1, '#docInfo'), (2, '#mapSettingsOpen'), (3, '#projectMissions'), (4, '#projectPicture'), (5, '#projectSize'),
                (6, '#projectClear'), (7, '#mapMenu .openpair'), (8, '#docNewPrefab')]
        self.shot('map-menu', self.panel_rows('#mapMenu', rows, side='right'),
                  clip=self.around('#mapButton', '#mapMenu', pad=(10, 6, 44, 12)))
        self.close_pops()
        page.locator('#playButton').click()
        page.wait_for_function("document.querySelectorAll('#installInfo dd').length === 4")
        page.wait_for_timeout(300)
        rows = [(1, '#settingsSquad'), (2, '#projectMaps'), (3, '#installInfo')]
        self.shot('game-menu', self.panel_rows('#playMenu', rows, side='left'),
                  clip=self.around('#playButton', '#playMenu', pad=(44, 6, 10, 12)))
        self.close_pops()

    def map_browser(self):
        """The Open window's Maps side, opened by the Map button's A map…: the switch in its head, the maps."""
        page = self.page
        page.locator('#mapButton').click()
        page.locator('#openMaps').click()
        page.wait_for_selector('#mapList .maprow')
        page.wait_for_timeout(500)
        x, y, w, h = self.rect('#mapList .maprow.on')
        marks = [dict(n=1, sel='#mapForm .opensides', side='top', gap=22),
                 dict(n=2, sel='#mapSearch', side='top', gap=22, at=0.55),
                 dict(n=3, sel='#mapForm .mapfind label', side='top', gap=22),
                 dict(n=4, sel='#mapGroups', side='left', gap=18),
                 dict(n=5, sel='#mapList .maprow.on', side='left', gap=18),
                 dict(n=6, rect=[x + w - 170, y, 170, h], side='top', gap=18, at=0.2, inset=8),
                 dict(n=7, sel='#mapCount', side='bottom', gap=20, at=0.2),
                 dict(n=8, sel='#mapOk', side='bottom', gap=20)]
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
        rows = [(1, '#details'), (2, '#editCopy'), (3, '#alignBox .alignto'), (4, '#flagsBox summary'), (5, '#posX'), (6, '#rotP'),
                (7, '#sourceDetails summary'), (8, '#copyPaths')]
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
        page.evaluate("document.getElementById('flagsBox').open = false")      # (folded again, as the later shots' panels have it)
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
        rows = [(1, '#alignBox .alignto'), (2, '#alignTarget'), (3, '#alignGo'), (4, '#alignText')]
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
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
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
        marks.append(dict(n=9, sel='#libraryLarge', side='top', gap=20))
        self.shot('add', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.locator('#libraryClose').click()

    def add_large(self):
        """The Add panel made large by its maximise button: This map's pieces as cards with large pictures. Put back
        after (the button again)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
        page.evaluate("viewer.setLibraryScope('map')")
        page.wait_for_selector('#libList .libitem')
        page.locator('#libraryLarge').click()
        page.wait_for_selector('#library.large')
        page.wait_for_function("[...document.querySelectorAll('#libList .libitem canvas')].slice(0, 18).every(c => c.dataset.drawn)", timeout=120000)
        page.wait_for_timeout(800)
        marks = [dict(n=1, sel='#libraryLarge', side='bottom', gap=24),
                 dict(n=2, sel='#libList .libitem', side='right', gap=22, at=0.3),
                 dict(n=3, sel='#libScope', side='right', gap=22)]
        self.shot('add-large', marks, resize=0.75)
        page.locator('#libraryLarge').click()
        page.wait_for_selector('#library:not(.large)')
        page.locator('#libraryClose').click()

    def add_all(self):
        """All maps: the pieces of the game's other maps. The server's cache must have the library scanned
        (`viewer.py library scan`)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
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

    def save_prefabs(self, *prefabs):
        """Prefabs (name, actors) saved from the demo's selections, those the library hasn't got yet; the selection let
        go after."""
        page = self.page
        have = page.evaluate('viewer.prefabApi.list().then(a => a.prefabs.map(p => p.name))')
        for name, actors in prefabs:
            if name in have: continue
            self.select(*actors)
            page.evaluate("name => viewer.savePrefab(name)", name)
        names = [name for name, _ in prefabs]
        page.wait_for_function("names => viewer.prefabApi.list().then(a => names.every(n => a.prefabs.some(p => p.name === n && p.picture)))",
                               arg=names, timeout=30000)
        page.evaluate('viewer.select(null)')
        self.close_pops()          # (the banner a save leaves)

    def prefabs(self):
        """The Prefabs tab with two prefabs saved from the demo's selections. The server's prefabs folder (beside its
        scratch projects folder) must be empty."""
        page = self.page
        self.save_prefabs(*PREFABS)
        page.locator('#editAdd').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
        page.evaluate("viewer.setLibraryScope('prefabs')")
        page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
        page.wait_for_timeout(1200)
        marks = [dict(n=1, sel='#libScope button[data-value="prefabs"]', side='top', gap=22, at=0.3),
                 dict(n=2, sel='#prefabFilter', side='right', gap=18),
                 dict(n=3, sel='#prefabNew', side='on', aty=0, dy=-2),
                 dict(n=4, sel='#prefabSave', side='on', aty=0, dy=-2),
                 dict(n=5, sel='#prefabList .libitem', side='right', gap=18),
                 dict(n=6, sel='#prefabList .libitem:nth-child(2) .prefabacts button', side='right', gap=18),
                 dict(n=7, sel='#prefabFoot', side='bottom', gap=22, at=0.2),
                 dict(n=8, sel='#prefabAll', side='right', gap=18)]
        self.shot('prefabs', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.evaluate("viewer.setLibraryScope('map')")
        page.locator('#libraryClose').click()

    def open_prefabs(self):
        """The Open window's Prefabs side, opened by the Map button's A prefab…: the New prefab card and the two prefabs
        the prefabs shot saved, the first chosen with its actions under the cards. Cancelled."""
        page = self.page
        self.save_prefabs(*PREFABS)
        page.locator('#mapButton').click()
        page.locator('#openPrefabs').click()
        page.wait_for_selector('#openPrefabDialog:not([hidden])')
        page.wait_for_function("document.querySelectorAll('#openPrefabCards .card').length === 3")
        page.wait_for_function("[...document.querySelectorAll('#openPrefabCards .card img')].every(i => i.complete && i.naturalWidth)", timeout=30000)
        page.locator('#openPrefabCards .card:not(.newcard)', has_text=PREFABS[0][0]).click()
        page.wait_for_selector('#openPrefabActs:not([hidden])')
        page.mouse.move(8, 8)
        page.wait_for_timeout(500)
        marks = [dict(n=1, sel='#openPrefabForm .opensides', side='top', gap=22),
                 dict(n=2, sel='#openPrefabFilter', side='top', gap=22, at=0.6),
                 dict(n=3, sel='#openPrefabOrder', side='top', gap=22),
                 dict(n=4, sel='#openPrefabPlace', side='left', gap=18, inset=-4),
                 dict(n=5, sel='#openPrefabCards .newcard', side='left', gap=18, at=0.3),
                 dict(n=6, sel='#openPrefabCards .card.on', side='bottom', gap=22),
                 dict(n=7, sel='#openPrefabActs', side='left', gap=18, inset=-4),
                 dict(n=8, sel='#openPrefabImport', side='bottom', gap=20),
                 dict(n=9, sel='#openPrefabOk', side='bottom', gap=20)]
        self.shot('open-prefabs', marks, clip=self.around('#openPrefabForm', pad=(36, 36, 16, 34)))
        page.locator('#openPrefabCancel').click()

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
        marks.append(dict(n=1, sel='#viewsButton', side='right', gap=20))
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
        marks = [dict(n=1, sel='#viewsButton', side='right', gap=20),
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
        marks = [dict(n=1, sel='#viewsButton', side='right', gap=20)]
        for n, actor, side in ((2, WEBBING, 'bottom'), (3, SHOP_SOUND, 'top'), (4, FLARE, 'bottom')):
            marks.append(dict(n=n, rect=self.marker(actor), side=side, gap=34, inset=3))
        for n, key in ((5, 'radiusMax'), (6, 'radiusMin')):
            s = handles[key]
            marks.append(dict(n=n, rect=[s[0] - 6, s[1] - 6, 12, 12], side='bottom', gap=40, inset=3))
        marks += self.panel_rows('#effectPanel', [(7, '#effectWaves .waverow'), (8, '#effectValues .check'),
                                                  (9, '#effectValues .valueline'), (10, '#effectValues .valuepair')])
        self.shot('effects', marks, resize=0.75)
        self.close_effects()

    def effects_switches(self):
        """The Views list with the Effects view on: a switch for each kind under its row."""
        self.view_switches('effects-switches', 'setEffectsShown', '#effectsFlyout')

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

        marks = [dict(n=1, sel='#viewsButton', side='right', gap=20),
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

    def spawns_switches(self):
        """The Views list with the Spawns view on: a switch for each family, Deleted points and Scripted drop-ins land
        where placed under its row."""
        page = self.page
        zones = page.evaluate('viewer.landingLayer.visible')
        self.view_switches('spawns-switches', 'setSpawnsShown', '#spawnsFlyout')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', zones)

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
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
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
        """Map grid: the play area's handles on the Bar as it is, and the panel, with the Views list kept open on its
        Map grid row."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#viewsButton').click()
        page.locator('#editGrid').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)
        b = page.evaluate('viewer.data.playableBounds')
        cx, cy = (b['min'][0] + b['max'][0]) / 2, (b['min'][2] + b['max'][2]) / 2
        # (the play area to the right of the middle: the far X side's handle clear of the Views list beside the rail)
        self.camera([cx + 600, cy + 330, 0], [2420, -4410, 3780])
        self.settle(3000)
        marks = [dict(n=1, sel='#editGrid', side='right', gap=20)]
        for n, axis, side in ((2, 0, 'right'), (3, 1, 'top'), (4, 2, 'top')):
            at = page.evaluate('a => viewer.gridHandleAt(a)', axis)
            if at is None: continue
            s = page.evaluate('p => viewer.screenOf(p)', at)
            marks.append(dict(n=n, rect=[s[0] - 8, s[1] - 8, 16, 16], side=side, gap=34, inset=3))
        marks += self.panel_rows('#gridPanel', [(5, '#gridSize'), (6, '#gridGround'), (7, '#gridOwn')])
        self.shot('map-grid', marks, resize=0.75)
        page.locator('#gridDone').click()          # (a click outside the list lets it go too)
        page.wait_for_selector('#viewsFlyout', state='hidden')

    # --- the Game look (game-likeness plan): the view as the game draws it, the time of day, fog and colour
    def game_look(self, look='game'):
        """The look put on ('game' or 'neutral'), waiting for the Game look's shaders and the map's baked light."""
        page = self.page
        if not page.evaluate('l => viewer.setLook(l)', look): raise SystemExit('the Game look can not be had on %s' % MAP)
        if look == 'game':
            page.wait_for_function('viewer.post.ready() && viewer.post.baked()?.on && viewer.post.baked().parts > 0', timeout=120000)

    def drag_time(self, hour):
        """The time bar at this hour (one undo step), the dial left on the map's own side."""
        self.page.evaluate('t => viewer.dragTime(t, viewer.timeOfDay().own.side)', hour)

    def undo_to(self, steps):
        while self.page.evaluate('viewer.gizmo.undoDepth()') > steps: self.page.keyboard.press('Control+z')

    def looks(self):
        """One view of the Bar three times: the Neutral look, the Game look at the map's own time (01:00, the moon), and
        the Game look with the time bar at 13:00 (look-neutral, look-game, look-noon). Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        page.locator('#floor button[data-value="all"]').click()
        self.camera(*LOOK_VIEW)
        clip = dict(x=250, y=120, width=940, height=640)
        self.settle(3000)
        self.shot('look-neutral', clip=clip, resize=0.5)
        self.game_look()
        self.settle(4000)
        self.shot('look-game', clip=clip, resize=0.5)
        self.drag_time(13)
        self.settle(4000)
        self.shot('look-noon', clip=clip, resize=0.5)
        self.undo_to(steps)
        self.game_look('neutral')
        page.locator('#floor button[data-value="1"]').click()

    def map_sun(self):
        """The Map settings window in the Game look, the time bar dragged to 19:30 (dusk): its Sun, moon and sky section
        with More unfolded (map-sun), then its Fog and colour section with both folds open (fog-colour). Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        self.game_look()
        self.drag_time(19.5)
        page.evaluate("document.getElementById('mapSettingsOpen').click()")
        page.wait_for_selector('#mapSettings:not([hidden])')
        page.evaluate("document.getElementById('mapSunFold').open = true")
        page.wait_for_timeout(800)
        rows = [(1, '#mapTimeBar'), (2, '#mapSunTime'), (3, '#mapSunDial'), (4, '#mapSunSkyRow'), (5, '#mapSunFold summary'),
                (6, '#mapSunColour'), (7, '#mapSunStrength'), (8, '#mapSkyColour'), (9, '#mapSkyStrength'), (10, '#mapSunGameTime'),
                (11, '#mapSunHour'), (12, '#skyList'), (13, '#mapSunReset')]
        self.shot('map-sun', self.panel_rows('#mapSettingsForm', rows),
                  clip=self.around('#mapSettingsTitle', '#mapSunSection', pad=(50, 12, 16, 12)))
        page.evaluate("""() => { document.getElementById('mapSunFold').open = false;
          for (const id of ['mapFogFold', 'mapColourFold']) document.getElementById(id).open = true;
          document.getElementById('mapLookSection').scrollIntoView();
          document.getElementById('mapSettingsForm').scrollTop -= 48; }""")      # (the section clear of the window's top)
        page.wait_for_timeout(800)
        rows = [(1, '#mapLooks > :first-child'), (2, '#mapLooks select'), (3, '#mapFogOn'), (4, '#mapFogSliders'), (5, '#mapFogAway'),
                (6, '#mapTint'), (7, '#mapColourSliders'), (8, '#mapLookReset')]
        self.shot('fog-colour', self.panel_rows('#mapSettingsForm', rows), clip=self.around('#mapLookSection', pad=(50, 12, 16, 12)))
        page.evaluate("for (const id of ['mapFogFold', 'mapColourFold']) document.getElementById(id).open = false")
        page.locator('#mapSettingsClose').click()
        page.wait_for_selector('#mapSettings', state='hidden')
        self.undo_to(steps)
        self.game_look('neutral')

    def sun_marker(self):
        """The Lights view in the Game look, the time bar at 17:30: the sun on its arc over the Bar, the moon's arc beside it,
        and a line down to the map. Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        self.game_look()
        page.evaluate('viewer.setLightsShown(true)')
        page.locator('#floor button[data-value="all"]').click()
        page.locator('#frame').click()
        self.settle(3000)
        # (a point of each arc: the marker where it stands at another hour)
        at = {}
        for name, hour in (('sun', 15), ('moon', 23.5), ('marker', 17.5)):
            self.drag_time(hour)
            page.wait_for_timeout(300)
            at[name] = page.evaluate('viewer.timeOfDay().markerAt')
            if not at[name]: raise SystemExit('the sun marker does not show at %s' % hour)
        self.settle(3000)
        spot = lambda p, r=6: [p[0] - r, p[1] - r, 2 * r, 2 * r]       # noqa: E731
        marks = [dict(n=1, rect=spot(at['marker'], 16), side='right', gap=30),
                 dict(n=2, rect=spot(at['sun']), side='top', gap=30),
                 dict(n=3, rect=spot(at['moon']), side='top', gap=30)]
        self.shot('sun-marker', marks, resize=0.75)
        self.undo_to(steps)
        page.evaluate('viewer.setLightsShown(false)')
        self.game_look('neutral')
        page.locator('#floor button[data-value="1"]').click()

    def open_project(self, name):
        """A saved project opened by the Project menu's Open… (the name typed; the page loads again)."""
        page = self.page
        if page.evaluate('viewer.project()?.name') == name: return
        page.evaluate("document.getElementById('projectLoad').click()")
        page.wait_for_selector('#fileDialog:not([hidden])')
        page.locator('#fileName').fill(name)
        page.locator('#fileOk').click()
        page.wait_for_function("n => window.viewer?.project?.()?.name === n && document.querySelector('#loading')?.hidden", arg=name,
                               timeout=180000)
        page.wait_for_timeout(1500)
        self.close_pops()

    def build_light_shown(self, timeout=30000):
        try: self.page.wait_for_function("!document.getElementById('buildLight').hidden", timeout=timeout)
        except Exception: return False
        return True

    def view_options(self):
        """View options in the Game look, the demo project open and lit by its last baked Build (built here with baking
        unless the project manager's queue baked it), one piece moved since. Undone after."""
        page = self.page
        page.evaluate('viewer.select(null)')
        self.open_project(PROJECT)
        self.game_look()
        if not self.build_light_shown():
            self.build_project(bake=True)
            if not self.build_light_shown(120000): raise SystemExit('View options shows no line of the baked Build')
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        self.nudge(POOL_TABLE, 48)
        page.wait_for_function("document.getElementById('buildLight').textContent.includes('1 piece changed since')", timeout=30000)
        page.locator('#viewButton').click()
        page.wait_for_timeout(600)
        rows = [(1, '#buildLight'), (2, '#areaLights'), (3, '#exposure'), (4, '#flyKeys'), (5, '#moveSpeed'), (6, '#turnSpeed'),
                (7, '#dragSpeed'), (8, '#skyOpen'), (9, '#playAreaToggle'), (10, '#grid'), (11, '#floorTiles'),
                (12, '#diagonalCover'), (13, '#likenessToggle'), (14, '#wire'), (15, '#hideHelpers'), (16, '#statsToggle')]
        hidden = [s for _, s in rows if not page.locator(s).is_visible()]
        if hidden: raise SystemExit('View options lacks %s on %s: the guide numbers them all' % (', '.join(hidden), MAP))
        self.shot('view-options', self.panel_rows('#viewOptions', rows), clip=self.around('#viewButton', '#viewOptions', pad=(44, 6, 8, 12)))
        self.close_pops()
        self.undo_to(steps)
        self.game_look('neutral')

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
            dict(n=1, sel='#viewsButton', side='right', gap=20),
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
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
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

    # --- made pieces: the Add button's Build menu (walls, rooms, floors, roofs, ground)
    def build_menu(self):
        """The Add button hovered: its Build menu."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#editAdd').hover()
        page.wait_for_selector('#buildFlyout', state='visible')
        page.wait_for_timeout(500)
        x, y, w, h = self.rect('#editAdd')
        fx, fy, fw, fh = self.rect('#buildFlyout')
        top = min(y, fy) - 10
        self.shot('build-menu', clip=dict(x=x - 8, y=top, width=fx + fw - x + 18, height=max(y + h, fy + fh) + 10 - top))
        page.mouse.move(WIDTH / 2, HEIGHT / 2)

    def draw(self, tool, a, b):
        """One of the Build menu's tools dragged over the ground from game point a to b: the ids of what it made."""
        page = self.page
        before = page.evaluate('[...viewer.roots.keys()]')
        page.evaluate('k => { viewer.startBuild(k); }', tool)
        page.wait_for_function('k => viewer.buildTool() === k && viewer.wallDrawing()?.ready', arg=tool, timeout=90000)
        p, q = (page.evaluate('p => viewer.screenOf(p)', at) for at in (a, b))
        page.mouse.move(*p)
        page.mouse.down()
        page.mouse.move((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, steps=6)
        page.mouse.move(*q, steps=6)
        page.mouse.up()
        page.wait_for_function('n => viewer.roots.size > n && !viewer.wallDrawing()', arg=len(before), timeout=60000)
        made = [i for i in page.evaluate('[...viewer.roots.keys()]') if i not in before]
        for i in made: page.wait_for_function('id => viewer.wallMeshReady(id)', arg=i, timeout=60000)
        return made

    def made_site(self):
        """The open asphalt of the car park, north of the lorry, with every floor shown, for the made pieces' shots: its
        south-east corner, at the ground's height (x runs west from there, y north)."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#scenery button[data-value="full"]').click()
        page.locator('#floor button[data-value="all"]').click()
        origin = page.evaluate('viewer.data.tileGrid.origin')
        spot = [origin[0] + 96 * 7, origin[1] + 96 * 10]
        spot.append(page.evaluate('([x, y]) => viewer.groundAt(x + 48, y + 48, 4096) ?? 0', spot))
        self.zones = page.evaluate('viewer.landingLayer.visible')
        page.evaluate('viewer.landingLayer.visible = false')     # the zones' numbers would be taken for the marks
        self.snap = page.evaluate('viewer.gizmo.snap')
        page.evaluate("viewer.setSnapMode('tile')")
        return spot

    def made_done(self, steps):
        """The made pieces undone, and the view as the demo has it."""
        page = self.page
        page.keyboard.press('Escape')
        while page.evaluate('viewer.gizmo.undoDepth()') > steps: page.keyboard.press('Control+z')
        page.evaluate('viewer.select(null)')
        page.evaluate('on => { viewer.landingLayer.visible = on; }', self.zones)
        page.evaluate('mode => viewer.setSnapMode(mode)', self.snap)
        page.locator('#scenery button[data-value="interior"]').click()
        page.locator('#floor button[data-value="1"]').click()

    def made_corner(self):
        """Two walls drawn from the Build menu on the car park under fine snap, meeting in a mitred corner, for the
        made walls' and the texture mapping's shots: the second drawn first, from the corner at 45 degrees away from
        the camera, then the first along the tiles up to the corner (five tiles long, so its end is the corner's
        point); the Bar's look chosen for the first (and so for the wall joined to it), and two gaps cut in it, a
        doorway and a window. Gives (the site, the first wall's id, the second's), the first picked."""
        page = self.page
        x, y, z = self.made_site()
        page.evaluate("viewer.setSnapMode('fine')")       # (drawn at any angle: steps of 24 and 15 degrees)
        self.camera([x + 560, y + 20, z + 110], [300, 1150, 780])
        self.settle(2000)
        corner = [x + 768, y + 96, z]
        self.draw('wall', corner, [corner[0] + 200, corner[1] - 200, z])
        (wall,) = self.draw('wall', [x + 288, y + 96, z], corner)
        page.evaluate("id => { const { plain, ...look } = viewer.plainLook('wall'); return viewer.setMadeLook(id, 'wall', look); }", wall)
        page.wait_for_function("old => viewer.gizmo.active && viewer.gizmo.active !== old && viewer.wallMeshReady(viewer.gizmo.active)", arg=wall, timeout=60000)
        wall = page.evaluate('viewer.gizmo.active')
        walls = "[...viewer.roots.values()].filter(r => !r.userData.deleted && r.userData.source.added?.generated?.kind === 'fracWall').map(r => r.userData.source.id)"
        (second,) = [i for i in page.evaluate(walls) if i != wall]
        page.wait_for_function('id => viewer.wallMeshReady(id)', arg=second, timeout=60000)
        page.evaluate('id => { viewer.select(null); viewer.select(id); }', wall)      # (the look took both: the first alone)
        gaps = "id => viewer.wallState(id).generated.wall.openings.length"
        page.locator('#wallGap').click()
        page.wait_for_function('id => (%s)(id) === 1' % gaps, arg=wall)
        page.evaluate("viewer.addWallOpening('window')")
        page.wait_for_function('id => (%s)(id) === 2' % gaps, arg=wall)
        page.wait_for_function('id => viewer.wallMeshReady(id)', arg=wall, timeout=60000)
        page.evaluate("document.getElementById('flagsBox').open = false")
        page.keyboard.press('v')
        page.mouse.move(8, 8)
        self.settle(2000)
        return (x, y, z), wall, second

    def made_walls(self):
        """Two walls drawn from the Build menu under fine snap (made_corner), meeting in a mitred corner, the first
        picked with its white size handles on their stems, its window's five blue handles (the doorway showing its
        middle alone), and its panel. Then the look picker, opened from the wall's Choose… Undone after."""
        page = self.page
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        (x, y, z), wall, second = self.made_corner()
        # the doorway picked (a click on its middle): its five handles, the window's middle alone (the face's handle
        # stands where no gap is, clear of their handles)
        h = page.evaluate('viewer.wallHandles()')
        window = min((k for k in h if k.endswith(':middle')), key=lambda k: page.evaluate(
            '([id, i]) => viewer.wallState(id).generated.wall.openings[i].z0', [wall, int(k.split(':')[1])]))
        page.mouse.click(*h[window][:2])
        page.mouse.move(250, 780)        # (off the handles but over the view, so that none stays lit as pointed at)
        self.settle(1500)
        h = page.evaluate('viewer.wallHandles()')
        keys = sorted(h)
        if not {'end:x0', 'end:top', 'end:bottom', 'end:face'} <= set(h): raise SystemExit('the made wall lacks a size handle: %s' % keys)
        picked = window.rsplit(':', 1)[0]
        others = [k for k in keys if k.endswith(':middle') and not k.startswith(picked + ':')]
        if not others or picked + ':x0' not in h: raise SystemExit('the gaps do not show a set at a time: %s' % keys)
        at = lambda k: [h[k][0] - 6, h[k][1] - 6, 12, 12]
        end = min(('end:x0', 'end:x1'), key=lambda k: h[k][0])
        meet = page.evaluate('p => viewer.screenOf(p)', [x + 768, y + 96, z + 300])
        marks = [dict(n=1, sel='#editAdd', side='right', gap=20),
                 dict(n=2, rect=at(end), side='bottom', gap=34, inset=3),
                 dict(n=3, rect=at('end:top'), side='top', gap=30, inset=3),
                 dict(n=4, rect=at('end:bottom'), side='bottom', gap=30, inset=3),
                 dict(n=5, rect=at('end:face'), side='bottom', gap=40, inset=3),
                 dict(n=6, rect=at(picked + ':z1'), side='top', gap=40, inset=3),
                 dict(n=6, rect=at(others[0]), side='bottom', gap=60, inset=3),
                 dict(n=7, rect=[meet[0] - 6, meet[1] - 6, 12, 12], side='top', gap=40, inset=3)]
        marks += self.panel_rows('#inspector', [(8, '#wallLookChange'), (9, '#texFold > summary'), (10, '#wallOpenings'),
                                                (11, '#wallGap'), (12, '#wallBreak')])
        self.shot('made-walls', marks, resize=0.75)
        # the look picker, from the wall's Choose…
        page.locator('#wallLookChange').click()
        page.wait_for_function("document.querySelectorAll('.lookpicker .lookcard').length > 8", timeout=60000)
        page.wait_for_function("[...document.querySelectorAll('.lookpicker .lookcard')].slice(0, 12).every(c => !c.querySelector('.lookwait'))", timeout=600000)
        # every look's picture drawn and kept (or given up on): the picker's line no longer counts them
        page.wait_for_function("!document.querySelector('.lookpicker .lookstatus').textContent.includes('Drawing pictures')", timeout=3600000)
        page.mouse.move(8, 8)
        page.wait_for_timeout(800)
        head = '.lookpicker .lookhead '
        marks = [dict(n=1, sel=head + 'input[type=search]', side='bottom', gap=18, at=0.93),
                 dict(n=2, sel=head + 'select', side='bottom', gap=18),
                 dict(n=3, sel=head + 'label.check input', side='bottom', gap=20),
                 dict(n=4, sel=head + 'button:not(.icon)', side='bottom', gap=18),
                 dict(n=5, sel='.lookpicker .lookcard', side='on', at=0.08, aty=0.1),
                 dict(n=6, sel='.lookpicker .lookcard:nth-child(2) .lookstar', side='bottom', gap=20)]
        self.shot('look-picker', marks, clip=self.around('.lookpicker .lookpanel', pad=(8, 8, 8, 8)), resize=0.75)
        page.evaluate('viewer.closeLookPicker()')
        self.made_done(steps)

    def texture_mapping(self):
        """The first of made_corner's walls with its Texture mapping fold open: its face toward the camera picked and
        outlined, mapped by size (repeats of 128, turned 15 degrees), with the blue dot, the ring and the white dot
        on it, and the fold's fields. Undone after."""
        page = self.page
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        (x, y, z), wall, second = self.made_corner()
        self.camera([x + 520, y + 96, z + 170], [150, 820, 330])
        page.locator('#texFold > summary').click()
        page.wait_for_function('id => viewer.texturePicked()?.id === id', arg=wall)
        page.locator('#texMode button[data-value="size"]').click()
        for field, value in (('#texU', '128'), ('#texV', '128'), ('#texTurn', '15')):
            page.locator(field).fill(value)
            page.locator(field).press('Enter')
        page.evaluate('document.activeElement?.blur()')
        page.wait_for_function('id => viewer.wallMeshReady(id)', arg=wall, timeout=60000)
        page.mouse.move(8, 8)
        self.settle(2500)
        h = page.evaluate('viewer.textureHandles()')
        if not (h and h['slide'] and h['turn'] and h['size']): raise SystemExit('the texture handles do not show: %s' % h)
        at = lambda p: [p[0] - 6, p[1] - 6, 12, 12]
        # (the picked face's outline: a point on its top edge, four fifths along)
        w = page.evaluate('id => viewer.wallState(id).generated.wall', wall)
        face = page.evaluate("([s, ab]) => viewer.textureSurfaceAt('faces', s, ab)", [h['picked'].get('side'), [w['x0'] + 0.8 * (w['x1'] - w['x0']), w['z1']]])
        marks = [dict(n=1, rect=at(face), side='top', gap=40, inset=3),
                 dict(n=2, rect=at(h['slide']), side='left', gap=40, inset=3),
                 dict(n=3, rect=at(h['turn']), side='top', gap=40, inset=3),
                 dict(n=4, rect=at(h['size']), side='right', gap=40, inset=3)]
        marks += self.panel_rows('#inspector', [(5, '#texFold > summary'), (6, '#texSurface'), (7, '#texMode'), (8, '#texRepeat'),
                                                (9, '#texFlipU'), (10, '#texReset')])
        self.shot('texture-mapping', marks, resize=0.75)
        page.locator('#texFold > summary').click()
        page.wait_for_function('viewer.texturePicked() === null')
        self.made_done(steps)

    def made_ground(self):
        """Ground drawn from the Build menu on the car park: a block, a ramp up to it, and a rock, the rock picked with
        its blue points, its white handles and its panel. Undone after."""
        page = self.page
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        x, y, z = self.made_site()
        self.camera([x + 560, y + 130, z + 40], [220, 950, 700])
        self.settle(2000)
        (block,) = self.draw('block', [x, y, z], [x + 192, y + 192, z])
        (ramp,) = self.draw('ramp', [x + 384, y, z], [x + 192, y + 192, z])
        (rock,) = self.draw('rock', [x + 576, y, z], [x + 768, y + 192, z])
        page.evaluate('id => viewer.select(id)', rock)
        page.keyboard.press('v')
        page.mouse.move(8, 8)
        page.wait_for_function("viewer.rockCorners().some(([k, v]) => v && v !== 'asking')", timeout=60000)
        self.settle(2500)
        h = page.evaluate('viewer.wallHandles()')
        side = next((k for k in sorted(h) if k.startswith('side')), None)
        if not side or 'end:top' not in h or 'end:bottom' not in h: raise SystemExit('the rock shows no handles: %s' % sorted(h))
        middle = "id => { const b = viewer.pieceBox(id); return viewer.screenOf([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, b[5]]); }"
        at = lambda p: [p[0] - 6, p[1] - 6, 12, 12]
        marks = [dict(n=1, rect=at(page.evaluate(middle, block)), side='top', gap=40, inset=3),
                 dict(n=2, rect=at(page.evaluate(middle.replace('b[5]]', '(b[4] + b[5]) / 2]'), ramp)), side='top', gap=40, inset=3),
                 dict(n=3, rect=at(page.evaluate(middle, rock)), side='top', gap=60, inset=3),
                 dict(n=4, rect=at(h[side]), side='bottom', gap=34, inset=3),
                 dict(n=4, rect=at(h['end:bottom']), side='bottom', gap=34, inset=3)]
        marks += self.panel_rows('#inspector', [(5, '#groundLookChange'), (6, '#groundAnother')])
        self.shot('made-ground', marks, resize=0.75)
        self.made_done(steps)

    def map_picture(self):
        """The Map menu's Map picture…: the 3D view taken as the image, its frame, and the result. Closed without
        using it: the project keeps no picture."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#floor button[data-value="all"]').click()
        self.camera([150, 640, 20], [900, -1900, 1300])
        self.settle(2500)
        page.evaluate("document.getElementById('projectPicture').click()")
        page.wait_for_selector('#mapPictureDialog:not([hidden])')
        page.locator('#mapPictureTake').click()
        page.wait_for_selector('#mapPictureCanvas:not([hidden])')
        page.wait_for_function("document.getElementById('mapPictureResultNote').textContent.startsWith('As the game')", timeout=30000)
        page.wait_for_timeout(600)
        marks = [dict(n=1, sel='#mapPictureCanvas', side='on', at=0.06, aty=0.1),
                 dict(n=2, sel='#mapPictureChoose', side='bottom', gap=18),
                 dict(n=3, sel='#mapPictureTake', side='bottom', gap=18),
                 dict(n=4, sel='#mapPictureResult', side='on', at=0.06, aty=0.12),
                 dict(n=5, sel='#mapPictureRemove', side='bottom', gap=20),
                 dict(n=6, sel='#mapPictureUse', side='bottom', gap=20)]
        self.shot('map-picture', marks, clip=self.around('#mapPictureForm', pad=(12, 12, 12, 36)), resize=0.75)
        page.locator('#mapPictureClose').click()
        page.locator('#floor button[data-value="1"]').click()

    def play(self):
        """The header's Play with a project open: the play window (Build's panel with the squad's line, Enable saving
        and Build and play). Cancelled: nothing is built or played."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#projectPlay').click()
        page.wait_for_selector('#buildForm', state='visible')
        page.wait_for_function("!document.getElementById('buildSquadRow').hidden", timeout=30000)
        page.wait_for_timeout(500)
        marks = [dict(n=1, sel='#buildSquad', side='left', gap=30),
                 dict(n=2, sel='#buildBake', side='left', gap=30),
                 dict(n=3, sel='#buildSaving', side='left', gap=30),
                 dict(n=4, sel='#buildOptionsOk', side='bottom', gap=20)]
        self.shot('play', marks, clip=self.around('#buildForm', pad=(40, 12, 12, 34)))
        page.keyboard.press('Escape')

    def clear_map(self):
        """The Clear map window on the Bar: its parts ticked with their counts. Cancelled: nothing is cleared."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.evaluate("document.getElementById('projectClear').click()")
        page.wait_for_selector('#clearMap:not([hidden])')
        page.wait_for_function("document.querySelector('#clearMapParts .tickval').textContent.trim() !== ''")
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
        """The Game menu's Test squad setup: the default six, the first unit open. Cancelled: nothing is saved."""
        page = self.page
        page.evaluate('viewer.select(null)')
        page.locator('#playButton').click()
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
        self.build_project(bake=False)

    def build_project(self, bake):
        """Builds the open project, with baking or without, and closes the build window."""
        page = self.page
        page.keyboard.press('Control+b')
        page.wait_for_selector('#buildForm', state='visible')
        if page.locator('#buildBake').is_checked() != bake: page.locator('#buildBake').click()
        page.locator('#buildOptionsOk').click()
        page.wait_for_function("""() => { const t = document.getElementById('buildTitle').textContent;
          return !document.getElementById('buildModal').hidden && !document.getElementById('buildClose').hidden && !t.startsWith('Building'); }""",
                               timeout=900000 if bake else 300000)
        title = page.locator('#buildTitle').text_content()
        page.locator('#buildClose').click()
        if not title.startswith('Built'): raise SystemExit('a build of %s failed: %s' % (page.evaluate('viewer.project()?.name'), title))

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
                 dict(n=9, sel='.pmpack .pmfield', side='left', gap=26, inset=-8),
                 dict(n=10, sel='#managerProjectFiles', side='left', gap=18),
                 dict(n=11, sel='#managerPack', side='left', gap=18)]
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

    def prefab_builder(self):
        """The prefab builder (another page: this shot comes after the Bar's): a prefab saved from the Bar (three kegs,
        a claw machine and a pool table) opened in it, the Prefab button's menu (prefab-menu), then the Add panel's
        This prefab tab, a row for each distinct piece with its count (this-prefab)."""
        page = self.page
        self.save_prefabs(BUILDER_PREFAB)
        name = BUILDER_PREFAB[0]
        prefab = page.evaluate('n => viewer.prefabApi.list().then(a => a.prefabs.find(p => p.name === n).id)', name)
        page.goto('%s?prefab=%s' % (self.server, prefab))
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.roots.size > 0", timeout=300000)
        page.wait_for_function("n => document.getElementById('mapTitle').textContent === n", arg=name)
        page.wait_for_timeout(1500)
        page.locator('#mapButton').click()
        page.wait_for_function("/^[1-9]/.test(document.getElementById('openPrefabsCount').textContent)")
        page.wait_for_timeout(300)
        # (Find missing pieces shows for a prefab with pieces of maps)
        if not page.locator('#prefabRecover').is_visible(): raise SystemExit('the Prefab menu shows no Find missing pieces for %s' % name)
        rows = [(3, '#docInfo'), (4, '#docPrefabSave'), (5, '#docPrefabSaveAs'), (6, '#docPrefabExport'), (7, '#prefabRecover'),
                (8, '#mapMenu .openpair'), (9, '#docNewPrefab')]
        self.shot('prefab-menu', [dict(n=1, sel='#projectButton', side='bottom', gap=18),
                                  dict(n=2, sel='#mapButton', side='right', gap=18)]
                  + self.panel_rows('#mapMenu', rows, side='right'),
                  clip=self.around('#projectButton', '#mapButton', '#mapMenu', pad=(10, 6, 44, 12)))
        self.close_pops()
        page.locator('#editAdd').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
        page.evaluate("viewer.setLibraryScope('map')")
        page.wait_for_function("document.querySelectorAll('#libList .libitem').length >= 3")
        page.wait_for_function("[...document.querySelectorAll('#libList .libitem canvas')].every(c => c.dataset.drawn)", timeout=60000)
        page.wait_for_timeout(500)
        row = """t => { const r = [...document.querySelectorAll('#libList .libitem')].find(i => i.querySelector('strong')?.textContent.startsWith(t));
          const b = r?.getBoundingClientRect(); return b && [b.left, b.top, b.width, b.height]; }"""
        kegs, block = page.evaluate(row, 'Keg'), page.evaluate(row, 'Cover block')
        if not kegs or not block: raise SystemExit('This prefab lists no kegs or no cover block: %s' % page.locator('#libList').inner_text())
        marks = [dict(n=1, sel='#libScope button[data-value="map"]', side='top', gap=22, at=0.9),
                 dict(n=2, rect=kegs, side='right', gap=18),
                 dict(n=3, rect=block, side='right', gap=18)]
        self.shot('this-prefab', marks, clip=self.around('#rail', '#library', pad=(8, 30, 44, 8)))
        page.locator('#libraryClose').click()

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
        page.evaluate('viewer.setNormalSpawns(true)')       # (the Normal view's Spawn points and objectives)
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

    # --- the Diagonal cover view, on the crashed small scout's farm (another map: these shots come last)
    def diagonal_at(self, tile, corner=None):
        """Where a tile's middle, or one of its corner dots, is in the window (at the tile's saved floor)."""
        return self.page.evaluate("""([t, c]) => { const f = (viewer.data.tactical.floorTiles ?? []).find(f => f.tile.every((v, k) => v === t[k]));
          return viewer.clientAt(viewer.diagonalPoint(t, f ? f.location[2] : -117, c)); }""", [tile, corner])

    def diagonal_click(self, tile, corner=None):
        x, y = self.diagonal_at(tile, corner)
        self.page.mouse.move(x - 2, y - 1)
        self.page.mouse.move(x, y)
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(200)

    def diagonal(self):
        """The Diagonal cover view on the farm's crashed scout, cut to its first floor, at its south-east corner: the
        Add panel's Diagonal cover entry chosen, its ghost mark at the pointer (diagonal-add), then put down there; the
        map's mark of the hull's corner given a second corner and picked, with its gizmo, corner dots and panel, beside
        another mark of the map as it is (diagonal). Undone after (no project is saved or built, so the panel's line of
        what the last build gave the mark isn't in the picture)."""
        page = self.page
        page.goto('%s?map=%s' % (self.server, FARM))
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=300000)
        page.wait_for_timeout(1500)
        if page.evaluate('viewer.diagonalMarks().length') < 8: raise SystemExit("%s has not its scout's eight marks" % FARM)
        page.keyboard.press('Shift+C')
        page.wait_for_function('viewer.diagonalOn()')
        page.wait_for_selector('#floor button[data-value="1"]', state='visible', timeout=60000)
        page.locator('#floor button[data-value="1"]').click()
        self.camera(*DIAGONAL_VIEW)
        self.settle(2500)
        steps = page.evaluate('viewer.gizmo.undoDepth()')
        at = lambda p, r=8: [p[0] - r, p[1] - r, 2 * r, 2 * r]
        # a new mark from the Add panel: its Diagonal cover kind's one entry, its ghost at the pointer, then put down
        page.locator('#editAdd').click()
        page.mouse.move(WIDTH / 2, HEIGHT / 2)      # (off the button, whose Build menu shows under a resting pointer)
        page.evaluate("viewer.setLibraryScope('map')")
        kind = page.locator('#libKind').input_value()
        page.locator('#libKind').select_option('diagonal')
        page.locator('#libList .libitem[data-id="diagonal-new"]').click()
        x, y = self.diagonal_at(NEW_MARK, NEW_CORNER)
        page.mouse.move(x + 6, y + 4)
        page.mouse.move(x, y, steps=3)
        self.settle(1200)
        marks = [dict(n=1, sel='#libKind', side='on', aty=0, dy=-2),
                 dict(n=2, sel='#libList .libitem', side='right', gap=18),
                 dict(n=3, rect=at([x, y], 10), side='bottom', gap=70, inset=3),
                 dict(n=4, sel='#dragHint', side='bottom', gap=18)]
        self.shot('diagonal-add', marks, resize=0.75)
        page.mouse.click(x, y)
        page.wait_for_function("viewer.diagonalMarks().some(m => m.kind === 'added')")
        page.locator('#libKind').select_option(kind)
        page.locator('#libraryClose').click()
        page.keyboard.press('Escape')
        # the hull corner's mark: a second corner, picked
        self.diagonal_click(PICKED_MARK)
        self.diagonal_click(PICKED_MARK, PICKED_CORNER)
        if page.evaluate('viewer.changes().diagonal') != 2 or page.evaluate('viewer.pickedMarks()') != ['%d,%d,%d' % tuple(PICKED_MARK)]:
            raise SystemExit('the marks did not take the clicks: %s' % page.evaluate('JSON.stringify(viewer.diagonalHand())'))
        page.mouse.move(300, 760)                         # (over the ground beside the hull: no mark or dot lit as pointed at)
        self.settle(1500)
        g = page.evaluate('viewer.screenOf(viewer.diagonalGizmo().at)')
        edge = page.evaluate("""([t]) => { const f = (viewer.data.tactical.floorTiles ?? []).find(f => f.tile.every((v, k) => v === t[k]));
          const m = viewer.diagonalPoint(t, f ? f.location[2] : -117, null); return viewer.clientAt([m[0] - 42, m[1] - 42, m[2]]); }""", [PICKED_MARK])
        dot = self.diagonal_at(PICKED_MARK, PICKED_CORNER)
        marks = [dict(n=1, sel='#viewsButton', side='right', gap=20),
                 dict(n=2, rect=at(edge, 4), side='bottom', gap=70, dx=40, inset=3),
                 dict(n=3, rect=at(g, 10), side='top', gap=120, dx=-60, inset=3),
                 dict(n=4, rect=at(dot, 7), side='right', gap=60, inset=3),
                 dict(n=5, rect=at(self.diagonal_at(MAP_MARK), 18), side='bottom', gap=60, inset=3),
                 dict(n=6, rect=at(self.diagonal_at(NEW_MARK), 18), side='top', gap=60, inset=3)]
        marks += self.panel_rows('#diagonalPanel', [(7, '#diagonalChip'), (8, '#diagonalWhere'), (9, '#diagonalCorners'),
                                                    (10, '#diagonalHeightRow'), (11, '#diagonalDelete')])
        self.shot('diagonal', marks, resize=0.75)
        page.keyboard.press('Escape')
        while page.evaluate('viewer.gizmo.undoDepth()') > steps: page.keyboard.press('Control+z')
        page.keyboard.press('Shift+C')

def prefab_test_shot(browser, server, out):
    from PIL import Image
    page = browser.new_page(viewport=dict(width=WIDTH, height=HEIGHT), device_scale_factor=SCALE)
    typical(page)
    page.goto(server.split('?')[0] + '?prefab=new')
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden")
    page.evaluate('viewer.addVolumes([{box:[-192,0,0,0,192,176],floor:0}])')
    page.locator('#prefabTest').click()
    png = page.locator('#buildForm').screenshot()
    image = Image.open(io.BytesIO(png)).convert('RGB')
    image.save(out / 'prefab-test.webp', 'WEBP', quality=QUALITY, method=6)
    print('prefab-test    %4d x %-4d' % image.size, flush=True)
    page.close()


# the manager runs builds and leaves its projects saved, view-options opens the demo project again and builds it with
# baking, and prefab-builder, mission-objects and diagonal open other pages: they come
# last (project-menu also takes map-menu and game-menu; made-walls also takes look-picker; looks takes look-neutral,
# look-game and look-noon; map-sun also takes fog-colour; prefab-builder also takes this-prefab, its first picture being
# prefab-menu; diagonal also takes diagonal-add)
ORDER = ('window', 'header', 'rail', 'views-list', 'build-menu', 'dock', 'project-menu', 'map-browser', 'piece-panel', 'flags', 'box-select', 'group-align', 'add', 'add-large', 'add-all', 'prefabs', 'open-prefabs', 'prefab-test', 'lights',
         'landing-zones', 'effects', 'effects-switches', 'effect-values', 'add-effects', 'spawns', 'spawns-volume', 'spawns-switches', 'map-grid', 'looks', 'map-sun', 'sun-marker', 'build', 'play', 'floors', 'buildings', 'cover-blocks',
         'made-walls', 'texture-mapping', 'made-ground', 'clear-map', 'missions', 'map-picture', 'squad',
         'manager', 'save-as', 'view-options', 'prefab-builder', 'mission-objects', 'diagonal')


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--server', default='http://127.0.0.1:8790/', help='the test server (default: %(default)s)')
    a.add_argument('--out', type=Path, required=True, help='where the pictures go: a scratch folder (the guide\'s own shots/ only '
                   'on purpose: the guide skill copies the chosen pictures there)')
    a.add_argument('--only', default='', help='only these shots, by name, comma-separated (default: all)')
    args = a.parse_args()
    if urlsplit(args.server).port == 8768:
        a.error('8768 is the main server, the one the user keeps open: take the shots on a test server (8790-8799); they save a project')
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
