"""Editing in the page, in the browser (the whole-editor review of 20 November 2026), on a test server: run through
browser_smoke.py --only <name> on a server started with --projects and --builds in scratch folders (the prefab check
saves a prefab in the prefabs folder beside the projects), never the main one. Any map with one of its own fracturing
pieces will do (the pieces made here use it as their donor).

- made-prefab (finding 6): made pieces (a wall with an opening and a blast, a floor with a hole, a ramp, a rock with
  moved points) and a broken copy of a map's fracturing piece, put in a prefab from a selection, saved, read back and
  placed again, keep their numbers, blasts and flags; the placing preview draws the made pieces' own meshes; the
  prefab builder opens the prefab with them as they are, unchanged.
- modals (finding 11): in Missions, Map picture, Clear map and Prepare, Tab from the last control goes to the first
  and Shift+Tab from the first to the last; Delete, M and W don't reach the scene behind; Escape closes and the focus
  goes back to the control the dialog was opened from. Missions with no row ticked puts the focus on a row's tick.
- reset-all (finding 28): one of the map's fracturing pieces broken with Break (B and a click on it) is the only
  change: Reset all mends it, leaving the edit chip hidden and empty, and Ctrl+Z breaks it again; broken with another
  piece deleted, Reset all puts both back.
- draw-errors (finding 29, needs --projects): a project holding a copy of a piece whose mesh the browser can't load
  opens all the same, with the copy counted as a display error and its record kept and saved back; a paste of that
  piece says it could not be drawn and places nothing, and once the mesh can be had again the next paste places it
  (a failed load is not kept).
- look-undo (finding 30): a made wall's look changed while its new mesh is slow to come, with another piece deleted
  in that wait: the look change is one undo step of its own (Ctrl+Z puts the old wall back and leaves the other
  piece deleted, a second Ctrl+Z brings that back), and the wall keeps its flags and blasts in the new look.
- failed-reads (finding 31): a look catalogue whose read fails once is said in the banner and not kept (Try again
  reads it); a rock's corner points that fail once are said in the hint and asked for again; a map whose landing
  lines can't be read leaves the game unknown, not Long War: the banner says so, Clear map lists the bomb mission as
  Long War only, and the Missions panel leaves the council bomb tickable with a note.
- let-go (finding 33): the header's Mission select changed by a key gives the focus up (the next key changes nothing),
  a fracturing piece's blast size chosen by key leaves Delete and Ctrl+Z working on the piece, and a tick box in a
  dialog keeps the focus.
- paste-buildings (finding 34): a copy of a project's building pasted with a piece and undone takes its name back
  (the next paste is "... copy" again, not "... copy 2"); floor boxes of two buildings, one of them gone, pasted as one
  undo step, which takes the new building's name back too.
- squad-read (finding 34): Test squad setup after a read that fails has its controls off (keys on the list and a
  click on Add do nothing, with no error); read again they are back, and on an install that lands fewer units than
  the squad keeps (plain EW's six, stood in for) the count names both and Add goes by the squad's own limit.
- ladder-floor (finding 34): one of the map's ladders climbing to a roof: that roof's Floor turned off by its flags,
  the ladder's chip says it won't climb (as the Build warns); undone, it climbs.
- small-defects (finding 34): a warning note in the warning colour, the Floor field to 10, and a UFO mission whose
  ship type the editor doesn't know shown as it is with OK off until a ship is chosen; after a delete of 402 pieces
  and of one, Ctrl+Z, Ctrl+Y and Ctrl+Z each take the "Deleted ... · Ctrl+Z brings them back" hint away.
- grid-panel (the Map grid's panel once opened under the Selected piece panel, KB-8, and under the other right-hand
  panels; any map with a landing zone, a spawn point and an effect of its own): at 1280, 1024 and 800 pixels wide,
  for each right-hand panel that can show while the tool is on (the Selected piece, the Buildings view's, a landing
  zone's, a spawn point's, an effect's), shown before the rail's Map grid is opened and shown while it is on, the
  grid's panel and that panel stand apart, clear of the rail, and a click at the middle of the grid panel's Done puts
  the tool away and keeps what is picked.
- select-kind (the refactor's follow-ups, item 4.7; any map with a mesh three drawn pieces share, the Bar's dumpsters
  first): Select all on a picked piece (#editKind) picks every drawn piece of its mesh, its words and count saying how
  many, as no edit; the Flags group then sets them all as one undo step (undone, redone, Reset); a light picked beside
  the piece is dropped by a click and kept by Shift+click.
- flags-gate (item 4.7; a map with a prop whose pathing gate is open and a role half on, as the Bar's): a Flags row
  that would open the gate asks first and changes nothing; Cancel closes the question; an answer makes the change,
  the half-on role set as answered, one undo step; picking another piece closes an open question."""
import json
import math
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

WALL = dict(kind='fracWall', version=4, wall=dict(x0=0, x1=288, openings=[dict(x0=96, x1=192, z0=-16, z1=208)], seed=3),
            blasts=[dict(at=[48, 0, 96], radius=96)], breaksFurther=True)
FLOOR = dict(kind='fracSlab', version=3, slab=dict(x0=0, x1=192, y0=0, y1=288, holes=[dict(x0=96, x1=192, y0=96, y1=192)], seed=1))
RAMP = dict(kind='ground', version=3, ground=dict(shape='ramp', x0=0, x1=192, y0=0, y1=96, height=64))
# (a rock with moved points: ground.js ROCK, 24 points, the first 7 its ring on the ground)
ROCK_POINTS = [[round(96 + r * math.cos(k * 0.9), 1), round(96 + r * math.sin(k * 0.9), 1), z]
               for k, (r, z) in enumerate([(80, 0)] * 7 + [(50, 48 + 16 * (k % 3)) for k in range(17)])]
ROCK = dict(kind='ground', version=4, ground=dict(shape='rock', x0=0, x1=192, y0=0, y1=192, height=96, seed=5, points=ROCK_POINTS))
BLASTS = [dict(at=[10, 20, 30], radius=96), dict(at=[-5, 0, 64], radius=48)]

# the donor (one of the map's own fracturing pieces) and the pieces made of it, pasted four tiles along y
FIXTURE = """async ([made, blasts, along]) => {
  const T = await import('/vendor/three/three.module.js');
  const frac = [...viewer.roots.values()].find(r => !r.userData.source.added && !r.userData.deleted && r.visible
    && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
    && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length));
  if (!frac) return null;
  const entry = state => ({ source: frac.userData.source, matrix: frac.matrix.clone(),
                            state: { tinted: false, flags: null, generated: null, blasts: null, breaksFurther: false, ...state } });
  const entries = [...made.map((generated, k) => entry({ generated, flags: k ? null : { cover: false } })),
                   entry({ blasts, breaksFurther: true, flags: { walking: false } })];
  await viewer.pasteSnapshot({ entries, pivotIndex: 0, name: 'made pieces' }, new T.Matrix4().makeTranslation(0, 0, along));
  return viewer.gizmo.picks().ids;
}"""
# each picked piece's record as the project keeps it, by kind (the made kind, or 'broken')
RECORDS = """ids => { const actors = new Set(ids.map(id => viewer.roots.get(id)?.userData.source.actor));
  return viewer.editState().added.filter(e => actors.has(e.actor)).map(e => ({ kind: e.generated?.kind ?? 'broken', ground: e.generated?.ground?.shape ?? null,
    generated: e.generated ?? null, flags: e.flags ?? null, blasts: e.blasts ?? null, breaksFurther: e.breaksFurther ?? null }))
    .sort((a, b) => `${a.kind}${a.ground}`.localeCompare(`${b.kind}${b.ground}`)); }"""
# the size of what some roots draw, or of the placing preview's ghost
SIZE = """async ids => { const T = await import('/vendor/three/three.module.js'), box = new T.Box3();
  const objects = ids ? ids.map(id => viewer.roots.get(id)) : [viewer.placing().ghost];
  for (const o of objects) { o.updateMatrixWorld(true); box.expandByObject(o); }
  return box.getSize(new T.Vector3()).toArray().map(v => Math.round(v)); }"""


def check_made_prefab(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    ids = page.evaluate(FIXTURE, [[WALL, FLOOR, RAMP, ROCK], BLASTS, 384])
    assert ids, 'this map has no fracturing piece of its own to make pieces of'
    # (the paste has made their meshes when it returns: pasteSnapshot awaits them)
    before = page.evaluate(RECORDS, ids)
    assert [r['kind'] for r in before] == ['broken', 'fracSlab', 'fracWall', 'ground', 'ground'], before
    made = {r['kind'] + (r['ground'] or ''): r for r in before}
    assert made['fracWall']['generated'] == WALL and made['fracWall']['flags'] == dict(cover=False), made['fracWall']
    assert made['broken']['blasts'] == BLASTS and made['broken']['breaksFurther'] is True, made['broken']
    # the selection's prefab records carry them: nothing is left out
    page.evaluate('ids => viewer.gizmo.setSelection(ids, ids[0])', ids)
    records = page.evaluate("""() => { const r = viewer.prefabRecords(); return { pieces: r.pieces, left: r.left }; }""")
    assert records['left'] == [], records['left']
    what = lambda g, b, f, fl: json.dumps([g, b, f, fl], sort_keys=True)      # noqa: E731 (what a piece is, comparable)
    kept = sorted(what(p.get('generated'), p.get('blasts'), p.get('breaksFurther'), p.get('flags')) for p in records['pieces'] if p.get('from'))
    assert kept == sorted(what(r['generated'], r['blasts'], r['breaksFurther'], r['flags']) for r in before), kept
    # saved (the schema as it is now, 5), read back and placed again: each piece is what it was
    saved = page.evaluate("async () => viewer.savePrefab('Made pieces check')")
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 5, doc['schemaVersion']
    again = page.evaluate("""async ([id, along]) => {
      const T = await import('/vendor/three/three.module.js'), doc = await viewer.prefabApi.load(id), clip = await viewer.prefabClip(doc);
      if (clip.left.length) return { left: clip.left };
      await viewer.pasteSnapshot(clip, new T.Matrix4().makeTranslation(0, 0, along));
      return { ids: viewer.gizmo.picks().ids };
    }""", [saved['id'], 1152])
    assert 'ids' in again, again
    placed = [i for i in again['ids'] if page.evaluate('id => Boolean(viewer.roots.get(id))', i)]
    after = page.evaluate(RECORDS, placed)
    assert after == before, (after, before)
    # the placing preview draws the made pieces as they will stand: the size of what the paste made
    page.evaluate("async id => { const p = (await viewer.prefabApi.list()).prefabs.find(x => x.id === id); await viewer.choosePrefab(p); }", saved['id'])
    page.wait_for_function('Boolean(viewer.placing())', timeout=60000)
    ghost, drawn = page.evaluate(SIZE, None), page.evaluate(SIZE, placed)
    assert all(abs(a - b) <= 2 for a, b in zip(ghost, drawn)), (ghost, drawn)
    page.keyboard.press('Escape')
    # the prefab builder opens it with them as they are, and nothing changed
    builder = open_viewer(browser, url.split('?')[0] + f"?prefab={saved['id']}", errors)
    builder.wait_for_function('viewer.builderMode && viewer.builderDocument().pieces.length > 0', timeout=120000)
    pieces = builder.evaluate('viewer.builderDocument().pieces')
    assert sorted(what(p.get('generated'), p.get('blasts'), p.get('breaksFurther'), p.get('flags')) for p in pieces) == kept, pieces
    assert builder.evaluate('viewer.dirty()') is False
    builder.close()
    page.evaluate('id => viewer.prefabApi.remove(id)', saved['id'])
    page.close()
    assert not errors, errors
    return dict(map=url, pieces=len(before), ghost=ghost)


STOPS = """async id => { const { tabStops } = await import('/modal.js');
  return tabStops(document.getElementById(id)).map(el => el.id || el.textContent.trim().slice(0, 30) || el.outerHTML.slice(0, 60)); }"""
FOCUSED = """id => { const root = document.getElementById(id), a = document.activeElement;
  return { inside: root.contains(a), name: a?.id || a?.textContent?.trim().slice(0, 30) || a?.outerHTML?.slice(0, 60) || a?.tagName }; }"""
INSIDE = "id => document.getElementById(id).contains(document.activeElement)"
FOCUS_STOP = """async ([id, k]) => { const { tabStops } = await import('/modal.js'); tabStops(document.getElementById(id)).at(k).focus(); }"""


def until(page, expression, arg=None):
    """Wait up to 5 s for `expression` (a focus that moves a moment after a dialog shows or closes); when it never holds,
    the assertion after the wait says what was found instead."""
    try: page.wait_for_function(expression, arg=arg, timeout=5000)
    except PlaywrightTimeout: pass


def modal_case(page, root, opens):
    """One dialog, opened with the header's Map button focused: its Tab ring both ways, the scene's keys kept from what
    is behind, Escape, and the focus back on that button."""
    piece = page.evaluate("[...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden).userData.source.id")
    page.evaluate('id => viewer.select(id)', piece)
    page.evaluate("document.getElementById('mapButton').focus()")
    page.evaluate(opens)
    page.wait_for_selector(f'#{root}:not([hidden])')
    until(page, INSIDE, root)      # (a dialog's own focus comes a moment after it shows)
    assert page.evaluate(FOCUSED, root)['inside'], (root, page.evaluate(FOCUSED, root))
    stops = page.evaluate(STOPS, root)
    assert len(stops) >= 2, (root, stops)
    page.evaluate(FOCUS_STOP, [root, -1])
    page.keyboard.press('Tab')
    assert page.evaluate(FOCUSED, root)['name'] == stops[0], (root, page.evaluate(FOCUSED, root), stops)
    page.keyboard.press('Shift+Tab')
    assert page.evaluate(FOCUSED, root)['name'] == stops[-1], (root, page.evaluate(FOCUSED, root), stops)
    for _ in stops:
        page.keyboard.press('Tab')
        assert page.evaluate(FOCUSED, root)['inside'], root
    # the scene behind takes no keys: Delete leaves the picked piece, M opens no map browser, W moves no camera
    page.evaluate(FOCUS_STOP, [root, 0])
    camera = page.evaluate('viewer.camera.position.toArray()')
    page.keyboard.press('Delete')
    page.keyboard.press('m')
    page.keyboard.down('w')
    page.wait_for_timeout(250)      # (W held a while: a camera move would show; nothing should)
    page.keyboard.up('w')
    assert not page.evaluate('id => viewer.roots.get(id).userData.deleted', piece), root
    assert page.locator('#mapDialog').is_hidden(), root
    assert page.evaluate('viewer.camera.position.toArray()') == camera, root
    assert page.locator(f'#{root}').is_visible(), root
    page.keyboard.press('Escape')
    page.wait_for_selector(f'#{root}', state='hidden')
    until(page, "document.activeElement?.id === 'mapButton'")
    assert page.evaluate('document.activeElement?.id') == 'mapButton', (root, page.evaluate('document.activeElement?.id'))
    page.evaluate('viewer.select(null)')
    return len(stops)


def check_modals(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors, expected=(404,))
    out = {}
    out['clearMap'] = modal_case(page, 'clearMap', 'viewer.showClearMap()')
    out['prepareModal'] = modal_case(page, 'prepareModal', "viewer.showPrepare('open')")
    page.evaluate("document.getElementById('projectBanner').hidden = true")      # (Prepare's Later leaves its banner)
    out['mapPictureDialog'] = modal_case(page, 'mapPictureDialog', "viewer.mapPicture.show({ project: { id: "
                                         "'00000000-0000-4000-8000-000000000011', name: 'Keys check' }, map: viewer.mapId, own: null })")
    out['missionsDialog'] = modal_case(page, 'missionsDialog', 'viewer.showMissions()')
    # Missions with no row ticked: OK is off, and the focus is on the first row's tick, not left behind the dialog
    page.evaluate("document.getElementById('mapButton').focus()")
    page.evaluate("""viewer.missionsPanel.show({ title: 'Check', note: 'None ticked', onOk: () => {},
      rows: [{ entry: { record: 0 }, label: 'First', checked: false, disabled: 'not here' }, { entry: { record: 1 }, label: 'Second', checked: false }] })""")
    page.wait_for_selector('#missionsDialog:not([hidden])')
    until(page, "document.activeElement === document.querySelectorAll('#missionsList input')[1]")     # (as a dialog's own)
    assert page.locator('#missionsOk').is_disabled()
    assert page.evaluate("document.activeElement === document.querySelectorAll('#missionsList input')[1]"), page.evaluate(FOCUSED, 'missionsDialog')
    page.keyboard.press('Escape')
    page.wait_for_selector('#missionsDialog', state='hidden')
    assert page.evaluate('document.activeElement?.id') == 'mapButton'
    page.close()
    errors = [e for e in errors if 'status of 404' not in e]
    assert not errors, errors
    return out


# one of the map's own fracturing pieces, standing and drawn (Break works on it: made_breaking.js mapBreakable)
BREAKABLE = """[...viewer.roots.values()].filter(r => !r.userData.source.added && !r.userData.deleted && r.visible && !r.userData.source.hidden
  && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
  && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length)).map(r => r.userData.source.id)"""


def break_piece(page, ids):
    """One of the pieces `ids` broken as the user does: picked, framed, B, a click on it. Its id."""
    for piece in ids[:12]:
        page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); document.activeElement?.blur?.(); }', piece)
        page.wait_for_timeout(150)      # (a frame drawn where it was framed, before the screen points)
        page.keyboard.press('b')
        box = page.evaluate('id => viewer.pieceBox(id)', piece)
        for fx, fy in ((0.5, 0.5), (0.3, 0.5), (0.7, 0.5), (0.5, 0.3), (0.5, 0.7)):
            at = [box[0] + fx * (box[1] - box[0]), box[2] + fy * (box[3] - box[2]), (box[4] + box[5]) / 2]
            x, y = page.evaluate('p => viewer.screenOf(p)', at)
            page.mouse.click(x, y)
            if page.evaluate('id => viewer.roots.get(id).userData.blasts?.length ?? 0', piece):
                page.keyboard.press('Escape')
                return piece
        page.keyboard.press('Escape')
    raise AssertionError('no fracturing piece of this map could be clicked to break it')


def check_reset_all(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    ids = page.evaluate(BREAKABLE)
    assert ids, 'this map has no fracturing piece of its own'
    piece = break_piece(page, ids)
    page.evaluate('viewer.select(null)')
    blasts = page.evaluate('id => viewer.roots.get(id).userData.blasts', piece)
    assert page.evaluate('viewer.changes()')['broken'] == 1 and page.evaluate('viewer.changes().total') == 1
    # breakage the only change: Reset all shows, and mends it
    assert page.locator('#editResetAll').is_visible()
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0, page.evaluate('viewer.changes()')
    assert page.evaluate('id => viewer.roots.get(id).userData.blasts', piece) is None
    # nothing changed, no project open: the edit chip is hidden and keeps no words, as before any edit (it kept "not
    # saved", which a test reading the page's text took for shown)
    chip = page.evaluate("(() => { const c = document.getElementById('editCount'); return [c.hidden, c.textContent, c.title]; })()")
    assert chip == [True, '', ''], chip
    page.keyboard.press('Control+z')
    assert page.evaluate('id => viewer.roots.get(id).userData.blasts', piece) == blasts
    assert page.evaluate('viewer.changes().broken') == 1
    # with another piece deleted too: both back as the map has them
    other = page.evaluate("id => [...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden "
                          "&& r.userData.source.id !== id && r.userData.source.actor !== viewer.roots.get(id).userData.source.actor).userData.source.id", piece)
    page.evaluate('id => viewer.select(id)', other)
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.changes()')['deleted'] >= 1
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0, page.evaluate('viewer.changes()')
    assert not page.evaluate('id => viewer.roots.get(id).userData.deleted', other)
    assert page.evaluate('id => viewer.roots.get(id).userData.blasts', piece) is None
    page.close()
    assert not errors, errors
    return dict(piece=piece, blasts=len(blasts))


# a piece of the map whose mesh no other piece uses (one component, a static mesh): its id, actor and mesh file
LONE_PIECE = """() => { const uses = new Map();
  for (const o of viewer.data.objects) uses.set(o.mesh, (uses.get(o.mesh) ?? 0) + 1);
  const r = [...viewer.roots.values()].find(r => { const o = r.userData.source;
    return !o.added && r.visible && !o.hidden && uses.get(o.mesh) === 1 && viewer.data.meshes[o.mesh].kind === 'static'
      && viewer.data.objects.filter(x => x.actor === o.actor).length === 1; });
  const o = r.userData.source;
  return { id: o.id, actor: o.actor, file: viewer.data.meshes[o.mesh].url.split('/').at(-1) }; }"""
PASTE_SOURCE = """async actor => { const T = await import('/vendor/three/three.module.js');
  const o = viewer.data.objects.find(x => x.actor === actor);
  const placed = await viewer.pasteSnapshot({ entries: [{ source: o, matrix: new T.Matrix4().fromArray(o.matrix) }], pivotIndex: 0, name: 'the lone piece' },
                                            new T.Matrix4().makeTranslation(0, 0, 192));
  return { placed: placed.length, lost: placed.lost ?? 0, hint: document.getElementById('dragHint').textContent }; }"""


def check_draw_errors(browser, url, open_viewer, save_dialog):
    errors = []
    page = open_viewer(browser, url, errors)
    lone = page.evaluate(LONE_PIECE)
    # a project with a copy of it, saved
    page.evaluate('id => viewer.select(id)', lone['id'])
    page.keyboard.press('Control+c')
    page.evaluate('async () => { const c = viewer.clipboard(); const T = await import("/vendor/three/three.module.js");'
                  ' await viewer.pasteSnapshot(c, new T.Matrix4().makeTranslation(0, 0, 192)); }')
    save_dialog(page, f'Draw errors check {int(time.time())}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1', timeout=60000)
    project = page.evaluate('viewer.project()')
    copy = next(a for a in project['doc']['added'] if a['from']['actor'] == lone['actor'])
    page.close()
    # opened where that mesh can't be loaded: the project opens, the copy is a display error, its record is kept
    errors = []
    page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    blocked = lambda route: route.abort()      # noqa: E731
    page.route(f"**/{lone['file']}", blocked)
    page.goto(url.split('?')[0] + f"?map={project['doc']['source']['map']}&project={project['id']}")
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    opened = page.evaluate('viewer.project()')
    assert opened and opened['id'] == project['id'], opened
    assert any(a['actor'] == copy['actor'] for a in opened['carried']['added']), opened['carried']
    assert not page.evaluate('viewer.dirty()')
    # a paste of it: says so and places nothing; once the mesh can be had, the next paste places it
    tried = page.evaluate(PASTE_SOURCE, lone['actor'])
    assert tried['placed'] == 0 and tried['lost'] == 1 and 'could not be drawn' in tried['hint'], tried
    page.unroute(f"**/{lone['file']}", blocked)
    again = page.evaluate(PASTE_SOURCE, lone['actor'])
    assert again['placed'] == 1 and again['lost'] == 0, again
    # saved back: the copy that couldn't be drawn is still in the project
    page.keyboard.press('Control+s')
    page.wait_for_function('viewer.project()?.revision === 2', timeout=60000)
    saved = page.evaluate('viewer.project().doc.added')
    assert any(a['actor'] == copy['actor'] and a['from'] == copy['from'] for a in saved), saved
    # a state whose copy needs a material that can't be had (its texture is missing) is put on the map all the same:
    # the copy is a display error, said in the notes, and its record carried
    # (another piece of the map, drawn: the lone one's mesh was kept from this page's load)
    applied = page.evaluate("""async lone => {
      const root = [...viewer.roots.values()].find(r => { const s = r.userData.source;
        return !s.added && r.visible && !s.hidden && s.actor !== lone && viewer.data.objects.filter(x => x.actor === s.actor).length === 1; });
      const o = root.userData.source, actor = o.actor;
      viewer.data.textures['check:gone'] = { url: '/cache/no-such-map/no-such-texture.png', srgb: true };
      viewer.data.materials['check:gone'] = { ...viewer.data.materials[o.materials[0]], diffuse: 'check:gone', render: {} };
      const kept = o.materials; o.materials = o.materials.map(() => 'check:gone');
      const record = { id: 'draw-errors-check', actor: `${actor}_copy987`, from: { package: o.sourcePackage, level: 'base', actor },
                       components: [o.component], location: o.location.map((v, k) => v + (k === 1 ? 384 : 0)), rotation: [...o.rotation] };
      try {
        const carried = await viewer.applyState({ overrides: [], added: [record], groups: [] });
        return { copy: record.actor, carried: carried.added.map(a => a.actor), drawn: [...viewer.roots.values()].some(r => r.userData.source.actor === record.actor),
                 notes: document.getElementById('diagnostics').textContent };
      } finally { o.materials = kept; }
    }""", lone['actor'])
    assert applied['carried'] == [applied['copy']] and not applied['drawn'], applied
    assert 'could not be drawn' in applied['notes'], applied['notes']
    page.close()
    errors = [e for e in errors if 'no-such-texture' not in e]
    assert not errors, errors
    return dict(piece=lone['actor'], project=project['id'])


# the server's made meshes held back a second and a half in this page (as a slow server would be)
SLOW_MADE = """() => { const real = window.fetch; window.madeAsked = 0;
  window.fetch = (u, o) => ((u instanceof Request ? u.url : String(u)).includes('/generated/')
    ? (window.madeAsked++, new Promise(done => setTimeout(done, 1500)).then(() => real(u, o))) : real(u, o)); }"""
WALL_STANDS = """id => { const r = viewer.roots.get(id); return Boolean(r && !r.userData.deleted); }"""


def check_look_undo(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    plain = dict(WALL, version=4)
    plain.pop('breaksFurther')
    wall, = page.evaluate(FIXTURE.replace('entry({ blasts, breaksFurther: true, flags: { walking: false } })', ''), [[plain], BLASTS, 384])[:1]
    other = page.evaluate("id => [...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden "
                          "&& r.userData.source.id !== id).userData.source.id", wall)
    page.evaluate(SLOW_MADE)
    # the look change starts (a look of one of this map's own walls, from the catalogue: a new mesh the server makes, on
    # its way), and another piece is deleted meanwhile
    page.evaluate("""async id => { const map = viewer.data.name, { looks } = await (await fetch('/looks/walls.json')).json();
      const entry = looks.find(e => e.map.toLowerCase() === map.toLowerCase() && viewer.catalogued('wall', viewer.lookFromEntry('wall', e).donor));
      window.lookDone = viewer.setMadeLook(id, 'wall', viewer.lookFromEntry('wall', entry)); }""", wall)
    page.wait_for_function('window.madeAsked > 0')      # (its new mesh asked for, the answer held back)
    page.evaluate("id => { viewer.select(id); document.activeElement?.blur?.(); }", other)
    page.keyboard.press('Delete')
    assert page.evaluate('id => viewer.roots.get(id).userData.deleted', other)
    assert page.evaluate(WALL_STANDS, wall), 'the old wall went before its new look was there'
    page.evaluate('window.lookDone')
    page.wait_for_function('id => !viewer.roots.get(id) || viewer.roots.get(id).userData.deleted', arg=wall, timeout=30000)
    made = page.evaluate("""id => [...viewer.roots.values()].filter(r => !r.userData.deleted && r.userData.source.added?.generated?.kind === 'fracWall')
      .map(r => ({ id: r.userData.source.id, generated: r.userData.source.added.generated, flags: r.userData.flags }))""", wall)
    assert len(made) == 1 and made[0]['generated']['wall'].get('look', {}).get('mesh'), made
    assert made[0]['generated']['blasts'] == plain['blasts'] and made[0]['flags'] == dict(cover=False), made
    # one Ctrl+Z: the old wall back, the new one gone, the other piece still deleted; a second: that one back
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press('Control+z')
    assert page.evaluate(WALL_STANDS, wall) and not page.evaluate(WALL_STANDS, made[0]['id'])
    assert page.evaluate('id => viewer.roots.get(id).userData.deleted', other)
    page.keyboard.press('Control+z')
    assert not page.evaluate('id => viewer.roots.get(id).userData.deleted', other)
    assert page.evaluate(WALL_STANDS, wall)
    page.close()
    assert not errors, errors
    return dict(wall=wall, look=made[0]['generated']['kind'])


BANNER_SAYS = "words => document.getElementById('projectBanner').textContent.includes(words)"


def check_failed_reads(browser, url):
    errors = []

    def opened(routes):
        page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        for pattern, handler in routes.items(): page.route(pattern, handler)
        page.goto(url)
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
        return page

    asked = dict(slabs=0, corners=0)

    def slabs(route):
        asked['slabs'] += 1
        route.abort() if asked['slabs'] == 1 else route.continue_()

    def corners(route):
        asked['corners'] += 1
        if asked['corners'] == 1:
            route.fulfill(status=400, content_type='application/json', body=json.dumps(dict(error="The rock's corners can't be read: check")))
        else: route.continue_()

    # the slabs' looks fail once: said, not kept, and Try again reads them
    page = opened({'**/looks/slabs.json': slabs, '**/generated/ground-corners.json*': corners})
    page.wait_for_function(BANNER_SAYS, arg="looks couldn't be read", timeout=30000)
    page.evaluate("async () => { window.looksModule = await import('/looks.js'); }")
    assert page.evaluate("looksModule.looksLoaded('slab')") is None
    page.locator('#projectBanner button', has_text='Try again').click()
    page.wait_for_function("looksModule.looksLoaded('slab') !== null", timeout=30000)
    assert asked['slabs'] == 2, asked
    # a rock's corners fail once: said in the hint, not kept, asked for again
    rock = dict(ROCK, ground={k: v for k, v in ROCK['ground'].items() if k != 'points'})
    ids = page.evaluate(FIXTURE.replace('entry({ blasts, breaksFurther: true, flags: { walking: false } })', ''), [[rock], BLASTS, 384])
    page.evaluate('id => viewer.select(id)', ids[0])
    page.wait_for_function("document.getElementById('dragHint').textContent.includes(\"corner points couldn't be read (The rock's corners can't be read: check)\")",
                           timeout=30000)
    assert not any(v != 'asking' for _, v in page.evaluate('viewer.rockCorners()')), page.evaluate('viewer.rockCorners()')
    page.wait_for_function("viewer.rockCorners().some(([, v]) => v?.points)", timeout=30000)
    assert asked['corners'] == 2, asked
    page.close()
    # the landing lines can't be read: the game is unknown, not Long War
    page = opened({'**/landing-lines.json': lambda route: route.fulfill(status=500, content_type='application/json',
                                                                         body=json.dumps(dict(error='check: no answer')))})
    page.wait_for_function(BANNER_SAYS, arg="landing lines for this map couldn't be read (check: no answer)", timeout=30000)
    lines = page.evaluate('viewer.landingLines()')
    assert lines['kind'] is None and lines['failed'] == 'check: no answer', lines
    page.evaluate('viewer.showMissions()')
    page.wait_for_selector('#missionsDialog:not([hidden])')
    bomb = page.evaluate("""() => { const row = [...document.querySelectorAll('#missionsList .missionrow')].find(r => r.textContent.includes('Council bomb (added)'));
      return row && { disabled: row.querySelector('input').disabled, words: row.querySelector('small').textContent }; }""")
    assert bomb and not bomb['disabled'] and "Which game is set isn't known (the editor couldn't read it: check: no answer)" in bomb['words'], bomb
    page.close()
    assert not errors, errors
    return dict(asked=asked, bomb=bomb['words'][-90:])


FOCUSED_ID = "() => document.activeElement?.id || document.activeElement?.tagName"


def check_let_go(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    out = {}
    # the header's Mission select: a key changes it once, and the focus has left it, so the next key doesn't
    if page.locator('#missionPick').is_visible() and page.locator('#mission option').count() > 1:
        page.focus('#mission')
        before = page.input_value('#mission')
        page.keyboard.press('ArrowDown')
        changed = page.input_value('#mission')
        assert changed != before and page.evaluate(FOCUSED_ID) != 'mission', (before, changed, page.evaluate(FOCUSED_ID))
        page.keyboard.press('ArrowDown')
        assert page.input_value('#mission') == changed
        out['mission'] = [before, changed]
    # a fracturing piece's blast size: chosen by key, then Delete reaches the piece
    frac = page.evaluate("""() => [...viewer.roots.values()].find(r => !r.userData.source.added && !r.userData.deleted && r.visible
      && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
      && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length))?.userData.source.id""")
    page.evaluate('id => viewer.select(id)', frac)
    page.wait_for_selector('#pieceBlastSize', state='visible')
    page.focus('#pieceBlastSize')
    size = page.input_value('#pieceBlastSize')
    page.keyboard.press('ArrowDown' if page.evaluate("document.getElementById('pieceBlastSize').selectedIndex === 0") else 'ArrowUp')
    assert page.input_value('#pieceBlastSize') != size and page.evaluate(FOCUSED_ID) != 'pieceBlastSize', page.evaluate(FOCUSED_ID)
    page.keyboard.press('Delete')
    assert page.evaluate('id => viewer.roots.get(id).userData.deleted', frac)
    page.keyboard.press('Control+z')
    assert not page.evaluate('id => viewer.roots.get(id).userData.deleted', frac)
    out['blastSize'] = [size, page.input_value('#pieceBlastSize')]
    # in a dialog, a tick box keeps the focus (its Tab ring)
    page.evaluate('viewer.showMissions()')
    page.wait_for_selector('#missionsDialog:not([hidden])')
    page.evaluate("document.querySelector('#missionsList input:not(:disabled)').focus()")
    page.keyboard.press('Space')
    assert page.evaluate("document.activeElement === document.querySelector('#missionsList input:not(:disabled)')"), page.evaluate(FOCUSED_ID)
    page.keyboard.press('Escape')
    page.wait_for_selector('#missionsDialog', state='hidden')
    page.close()
    assert not errors, errors
    return out


LIVE_BOXES = "() => [...viewer.volumeRoots.values()].filter(r => !r.userData.deleted).map(r => r.userData.source.id)"
NAMES = "() => viewer.buildingsNow().map(b => b.name).sort()"


def check_paste_buildings(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    piece = page.evaluate("() => [...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden).userData.source.id")
    # a building of the project's, and a copy of it with a piece (the paste of a selection): undone, its name goes
    # with it, so the next paste is "… copy" again, not "… copy 2"
    first = page.evaluate("""id => { const b = viewer.pieceBox(id), at = [b[0], b[2], b[4]];
      const [box] = viewer.addVolumes([{ box: [at[0], at[1] + 960, at[2], at[0] + 96, at[1] + 1056, at[2] + 192], floor: 0 }], viewer.newBuilding());
      return box.userData.source.id; }""", piece)
    base = page.evaluate(NAMES)
    paste = """async ([box, id]) => { const T = await import('/vendor/three/three.module.js');
      viewer.gizmo.setSelection([box, id], id); const clip = viewer.snapshot();
      await viewer.pasteSnapshot(clip, new T.Matrix4().makeTranslation(192, 0, 0)); }"""
    page.evaluate(paste, [first, piece])
    copied = page.evaluate(NAMES)
    assert len(copied) == len(base) + 1 and any(n.endswith(' copy') for n in copied), (base, copied)
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate(NAMES) == base
    had = set(page.evaluate(LIVE_BOXES))
    page.evaluate(paste, [first, piece])
    assert page.evaluate(NAMES) == copied, (copied, page.evaluate(NAMES))
    # floor boxes of two buildings pasted (one of them gone by then): one undo step, which takes the new building's name
    page.evaluate('viewer.setVolumesShown(true)')
    copy_box, = set(page.evaluate(LIVE_BOXES)) - had
    page.evaluate("ids => { viewer.gizmo.setSelection(ids, ids[0]); viewer.copyVolumes(); viewer.gizmo.setSelection([ids[1]], ids[1]); viewer.deleteVolumes(); }",
                  [first, copy_box])
    boxes, names = page.evaluate(LIVE_BOXES), page.evaluate(NAMES)
    page.evaluate('viewer.pasteVolumes()')
    pasted = page.evaluate(NAMES)
    assert len(page.evaluate(LIVE_BOXES)) == len(boxes) + 2 and len(pasted) == len(names) + 1, (names, pasted)
    page.evaluate('viewer.gizmo.undo()')
    assert sorted(page.evaluate(LIVE_BOXES)) == sorted(boxes) and page.evaluate(NAMES) == names
    page.evaluate('viewer.pasteVolumes()')
    assert page.evaluate(NAMES) == pasted, (pasted, page.evaluate(NAMES))
    page.evaluate('viewer.setVolumesShown(false)')
    page.close()
    assert not errors, errors
    return dict(copy=[n for n in copied if n not in base], pasted=[n for n in pasted if n not in names])


SQUAD_CONTROLS = "() => ['squadAdd', 'squadCopy', 'squadName', 'squadExport', 'squadImport', 'squadSave'].map(id => document.getElementById(id).disabled)"


def check_squad_read(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors, expected=(500,))
    mode = dict(now='fail')

    def squad(route):
        if route.request.method != 'GET': return route.continue_()
        if mode['now'] == 'fail':
            return route.fulfill(status=500, content_type='application/json', body=json.dumps(dict(error='check: no squad')))
        answer = route.fetch().json()
        # (an install whose landing takes fewer units than the squad keeps, as plain EW's six)
        answer['choices'] = dict(answer.get('choices') or {}, maxUnits=6, familyLabel='Plain Enemy Within')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(answer))

    def open_squad():
        page.locator('#playButton').click()
        page.locator('#settingsSquad').click()
        page.wait_for_selector('#squadDialog:not([hidden])')

    page.route('**/squad.json', squad)
    # a read that fails: the controls that work on the squad are off, and keys on the list do nothing
    open_squad()
    page.wait_for_function("document.getElementById('squadStatus').textContent.includes('could not be read')", timeout=30000)
    assert all(page.evaluate(SQUAD_CONTROLS)), page.evaluate(SQUAD_CONTROLS)
    page.dispatch_event('#squadUnits', 'keydown', dict(key='ArrowDown'))
    page.evaluate("document.getElementById('squadAdd').onclick()")       # (as a click that got through would)
    page.keyboard.press('Escape')
    page.wait_for_selector('#squadDialog', state='hidden')
    # read again: the controls are back, and the count names the install's own limit beside the squad's
    mode['now'] = 'fewer'
    open_squad()
    page.wait_for_function("document.querySelectorAll('#squadUnits li').length > 0", timeout=30000)
    disabled = page.evaluate(SQUAD_CONTROLS)
    count = page.locator('#squadCount').inner_text()
    units = page.locator('#squadUnits li').count()
    assert not disabled[3] and not disabled[4] and not disabled[2], disabled
    assert f'of at most 8' in count and 'Plain Enemy Within lands at most 6' in count, count
    assert disabled[0] == (units >= 8), (disabled, units)
    page.keyboard.press('Escape')
    page.close()
    errors = [e for e in errors if 'check: no squad' not in e]
    assert not errors, errors
    return dict(count=count)


# one of the map's ladders that climbs, the piece whose floor its top stands on, and that floor tile
LADDER_ON_FLOOR = """() => { const tiles = viewer.data.tactical?.floorTiles ?? [];
  for (const r of viewer.roots.values()) { const s = r.userData.source;
    if (s.actorClass !== 'XComLadder' || s.added || s.layer === 'stream') continue;
    const ends = viewer.ladderEnds(s.id);
    if (!ends?.climbs) continue;
    const top = tiles.find(f => f.tile.join(',') === ends.linkedTop.join(','));
    const owner = top && [...viewer.roots.values()].find(o => o.userData.source.actor === top.actor && !o.userData.source.added && o.userData.source.pieceFlags);
    if (owner) return { ladder: s.id, roof: owner.userData.source.id, actor: top.actor, top: ends.linkedTop };
  }
  return null; }"""


def check_ladder_floor(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    found = page.evaluate(LADDER_ON_FLOOR)
    assert found, 'no ladder of the map climbs to a floor of a piece with flags'
    # the floor its top stands on made no floor by the piece's flags: the chip says it won't climb, as the Build warns
    page.evaluate('id => viewer.select(id)', found['roof'])
    page.evaluate("document.getElementById('flagsBox').open = true")
    row = page.locator('#flagsRows label', has_text='Floor').first
    assert row.locator('input').is_checked(), page.locator('#flagsRows').inner_text()
    row.locator('input').click()
    page.evaluate('id => viewer.select(id)', found['ladder'])
    ends = page.evaluate('id => viewer.ladderEnds(id)', found['ladder'])
    assert not ends['climbs'] and ends['why'] == ['top'], ends
    assert "Won't climb: no floor at its top" in page.locator('#details').inner_text()
    # undone: it climbs again
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('id => viewer.ladderEnds(id).climbs', found['ladder'])
    page.close()
    assert not errors, errors
    return dict(ladder=found['actor'], top=found['top'])


def check_small_defects(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    # a warning is drawn in the warning colour, not dimmer than a note
    colours = page.evaluate("""() => { const probe = document.createElement('p'); probe.className = 'optionsnote warn'; document.body.append(probe);
      const warn = getComputedStyle(probe).color; probe.className = 'optionsnote'; const note = getComputedStyle(probe).color; probe.remove();
      return { warn, note, token: getComputedStyle(document.documentElement).getPropertyValue('--warn').trim() }; }""")
    assert colours['warn'] != colours['note'] and colours['warn'] == 'rgb(231, 197, 148)', colours
    # the Floor field goes to the script's and the compiler's limit
    assert page.evaluate("document.getElementById('volumeFloor').max") == '10'
    # a UFO mission whose ship type the editor doesn't know: shown as it is, OK off until a ship is chosen
    page.evaluate("""() => { window.missionsChosen = null; viewer.missionsPanel.show({ title: 'Missions', note: '',
      rows: [{ entry: { kind: 'Crash', ship: 'eShip_Unheard' }, label: 'Crashed UFO (added)', checked: true, words: '', detail: '', ufo: true }],
      onOk: entries => { window.missionsChosen = entries; } }); }""")
    page.wait_for_selector('#missionsDialog:not([hidden])')
    ship = page.locator('#missionsList select.missionship')
    assert ship.input_value() == 'eShip_Unheard' and page.locator('#missionsOk').is_disabled()
    assert 'eShip_Unheard' in page.locator('#missionsWarn').inner_text()
    ship.select_option('eShip_UFOAbductor')
    assert page.locator('#missionsOk').is_enabled() and page.locator('#missionsWarn').is_hidden()
    page.locator('#missionsOk').click()
    assert page.evaluate('window.missionsChosen') == [dict(kind='Crash', ship='eShip_UFOAbductor')]
    # an undo or a redo puts the resting hint back (nothing to say here: none) in place of "Deleted 402 pieces · Ctrl+Z
    # brings them back", for a delete of many pieces (a step under the busy mark) and of one
    ids = page.evaluate(DRAWN_PIECES)
    assert len(ids) >= 60, len(ids)
    settled = "() => document.getElementById('busyMark').hidden"
    hints = []
    for count in (402, 1):
        page.evaluate('ids => { viewer.select(ids[0]); viewer.gizmo.setSelection(ids); }', ids[:count])     # (Delete needs a pick)
        page.evaluate('document.activeElement?.blur?.()')
        page.keyboard.press('Delete')
        page.wait_for_function(f"() => viewer.changes().deleted > 0 && ({settled})()")
        hints.append(page.locator('#dragHint').inner_text())
        assert hints[-1].startswith('Deleted '), hints
        for key, deleted in (('Control+z', False), ('Control+y', True), ('Control+z', False)):
            page.keyboard.press(key)
            page.wait_for_function(f"d => (viewer.changes().deleted > 0) === d && ({settled})()", arg=deleted)
            assert page.locator('#dragHint').is_hidden(), (count, key, page.locator('#dragHint').inner_text())
    page.close()
    assert not errors, errors
    return dict(colours=colours, hints=hints)


# one of the map's own pieces, drawn and pickable; and all of them
DRAWN_PIECE = """[...viewer.roots.values()].find(r => r.visible && !r.userData.deleted && !r.userData.source.added
  && !r.userData.source.hidden && !r.userData.source.environment)?.userData.source.id ?? null"""
DRAWN_PIECES = """[...viewer.roots.values()].filter(r => r.visible && !r.userData.deleted && !r.userData.source.added
  && !r.userData.source.hidden && !r.userData.source.environment).map(r => r.userData.source.id)"""


def apart(a, b):
    """Whether two boxes (Playwright's bounding boxes) share no point."""
    return (a['x'] + a['width'] <= b['x'] or b['x'] + b['width'] <= a['x']
            or a['y'] + a['height'] <= b['y'] or b['y'] + b['height'] <= a['y'])


# Meshes at least three drawn pieces of the map share, the Bar's dumpsters first: [{ name, ids (their roots), actors }]
SHARED_MESHES = """() => { const by = new Map();
  for (const r of viewer.roots.values()) { const o = r.userData.source, name = viewer.data.meshes[o.mesh]?.name;
    if (r.userData.deleted || !r.visible || o.added || o.cover || o.hidden || o.environment || o.layer === 'stream' || typeof name !== 'string') continue;
    if (!by.has(name)) by.set(name, { name, ids: [], actors: new Set() });
    by.get(name).ids.push(o.id); by.get(name).actors.add(o.actor); }
  return [...by.values()].filter(k => k.actors.size >= 3)
    .sort((a, b) => b.name.endsWith('Dumpster_A') - a.name.endsWith('Dumpster_A') || a.name.localeCompare(b.name))
    .map(k => ({ name: k.name, ids: k.ids, actors: k.actors.size })); }"""
KIND_NOW = """() => { const b = document.getElementById('editKind');
  return { picks: viewer.gizmo.picks().ids, text: b.textContent, count: document.getElementById('editKindCount').textContent, disabled: b.disabled,
           title: b.title, depth: viewer.gizmo.undoDepth(), changes: viewer.changes().total, hint: document.getElementById('dragHint').textContent,
           flagsCount: document.getElementById('flagsCount').textContent, reset: document.getElementById('flagsReset').disabled }; }"""
# The Flags group's rows: [label, ticked, half (indeterminate), greyed]; the project's flag records: {actor: flags}
FLAG_ROWS = """() => [...document.querySelectorAll('#flagsRows .flagrow')].map(l => { const i = l.querySelector('input');
  return [l.dataset.name, i.checked, i.indeterminate, i.disabled]; })"""
FLAG_RECORDS = """() => Object.fromEntries((viewer.editState().overrides ?? []).filter(o => o.flags).map(o => [o.target.actor, o.flags]))"""


def flag_row(page, label):
    return page.locator('#flagsRows .flagrow', has=page.locator('.flagname', has_text=label)).first.locator('input')


def check_select_kind(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    kinds = page.evaluate(SHARED_MESHES)
    assert kinds, 'no mesh of this map is shared by three drawn pieces'
    kind = kinds[0]
    word = page.evaluate("async n => (await import('/dom_words.js')).short(n)", kind['name'])
    n = kind['actors']
    page.evaluate('id => viewer.select(id)', kind['ids'][0])
    one = page.evaluate(KIND_NOW)
    assert one['count'] == str(n) and not one['disabled'], one
    assert one['title'].startswith(f'Select all {word}: every drawn piece with this mesh in the map: {n} pieces'), one['title']
    # every drawn piece of its mesh picked, said in the hint; no edit (no undo step, nothing to save); the button off
    page.locator('#editKind').click()
    picked = page.evaluate(KIND_NOW)
    assert sorted(picked['picks']) == sorted(kind['ids']), (picked['picks'], kind['ids'])
    assert picked['hint'] == f'{n} pieces of {word} selected' and picked['disabled'], picked
    assert picked['depth'] == one['depth'] and picked['changes'] == 0, picked
    assert picked['flagsCount'] == f'as the map has them · {n} pieces', picked['flagsCount']
    # the Flags group sets them all: a row on for all of them (Blocks sight on the Bar's dumpsters) turned off, one undo
    # step; undone, redone; Reset takes it back, one undo step
    page.evaluate("document.getElementById('flagsBox').open = true")
    rows = page.evaluate(FLAG_ROWS)
    label = next((r[0] for r in rows if r[0] == 'Blocks sight' and r[1] and not r[2] and not r[3]),
                 next((r[0] for r in rows if r[1] and not r[2] and not r[3]), None))
    assert label, rows
    flag_row(page, label).click()
    page.wait_for_function("() => !document.getElementById('flagsReset').disabled")
    records = page.evaluate(FLAG_RECORDS)
    assert len(records) == n and len({json.dumps(f, sort_keys=True) for f in records.values()}) == 1, records
    assert page.evaluate(KIND_NOW)['flagsCount'] == f'1 changed · {n} pieces' and page.evaluate(KIND_NOW)['depth'] == one['depth'] + 1
    assert {r[0]: r for r in page.evaluate(FLAG_ROWS)}[label][1:3] == [False, False], page.evaluate(FLAG_ROWS)
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press('Control+z')
    assert page.evaluate(FLAG_RECORDS) == {} and page.evaluate(KIND_NOW)['flagsCount'] == f'as the map has them · {n} pieces'
    page.keyboard.press('Control+y')
    assert page.evaluate(FLAG_RECORDS) == records
    page.locator('#flagsReset').click()
    assert page.evaluate(FLAG_RECORDS) == {} and page.evaluate(KIND_NOW)['depth'] == one['depth'] + 2
    # a light picked beside one of the pieces: a click picks the kind alone, Shift+click adds the kind to the light
    page.evaluate('viewer.setNormalLights(true)')
    light = page.evaluate("[...viewer.lightRoots.values()].find(r => r.visible && !r.userData.source.added && r.userData.source.layer === 'base')?.userData.source.id ?? null")
    assert light, 'the map has no light to pick beside the piece'
    for shift in (False, True):
        page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [kind['ids'][0], light])
        assert sorted(page.evaluate(KIND_NOW)['picks']) == sorted([kind['ids'][0], light])
        page.locator('#editKind').click(modifiers=['Shift'] if shift else [])
        assert sorted(page.evaluate(KIND_NOW)['picks']) == sorted(kind['ids'] + ([light] if shift else [])), (shift, page.evaluate(KIND_NOW)['picks'])
    page.evaluate('viewer.setNormalLights(false)')
    # nothing picked: nothing to match
    page.evaluate('viewer.select(null)')
    assert page.evaluate(KIND_NOW)['disabled'] and page.evaluate(KIND_NOW)['count'] == '', page.evaluate(KIND_NOW)
    page.close()
    assert not errors, errors
    return dict(mesh=kind['name'], pieces=n, flag=label)


# A prop of the map for which a click on one Flags row asks first (piece_flags.js plan: the row opens its pathing gate
# and another role is half on): its id, the row's label and role, and the half-on role's label
GATED = """async () => {
  const pf = await import('/piece_flags.js'), c = viewer.families().pieceFlags;
  for (const r of viewer.roots.values()) {
    const o = r.userData.source;
    if (!r.visible || r.userData.deleted || !o.pieceFlags || o.added || o.hidden || o.environment || o.cover || o.layer === 'stream') continue;
    if (!c.gated.includes(c.classes[o.actorClass])) continue;
    if ([...viewer.roots.values()].filter(x => x.userData.source.actor === o.actor).length !== 1) continue;
    const { raw, assumed } = pf.rawOf(o.pieceFlags), before = pf.states(c, o.actorClass, raw);
    for (const role of pf.ROLES) {
      if (before[role] === 'n/a') continue;
      const p = pf.plan(c, o.actorClass, raw, { [role]: before[role] !== 'on' }, assumed), open = Object.keys(p.conflicts);
      if (open.length === 1) return { id: o.id, actor: o.actor, role, label: c.labels[role], on: before[role] !== 'on', half: open[0], halfLabel: c.labels[open[0]] };
    }
  }
  return null; }"""
ASK = """() => { const a = document.getElementById('flagsAsk');
  return { hidden: a.hidden, text: a.querySelector('div')?.textContent ?? '', buttons: [...a.querySelectorAll('button')].map(b => b.textContent),
           focused: a.contains(document.activeElement) ? document.activeElement.textContent : null }; }"""


def check_flags_gate(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    gated = page.evaluate(GATED)
    assert gated, 'no prop of this map asks about its pathing gate'
    page.evaluate('id => viewer.select(id)', gated['id'])
    page.evaluate("document.getElementById('flagsBox').open = true")
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    state = lambda: (page.evaluate(FLAG_RECORDS).get(gated['actor']), page.evaluate('viewer.gizmo.undoDepth()') - depth)   # noqa: E731
    # the row clicked: the question, and nothing changed yet
    flag_row(page, gated['label']).click()
    asked = page.evaluate(ASK)
    want = f"{gated['label']} {'on' if gated['on'] else 'off'} opens the pathing gate (bIgnoreForPathing) of this prop. "
    assert not asked['hidden'] and asked['text'].startswith(want) and f"{gated['halfLabel']} is partly on there and can't stay so" in asked['text'], asked
    assert asked['buttons'] == [f"{gated['halfLabel']} on", f"{gated['halfLabel']} off", 'Cancel'] and asked['focused'] == asked['buttons'][0], asked
    assert state() == (None, 0) and page.locator('#flagsReset').is_disabled(), state()
    # Cancel: the question closes, nothing changed
    page.locator('#flagsAsk button', has_text='Cancel').click()
    assert page.evaluate(ASK)['hidden'] and state() == (None, 0)
    # asked again and answered: the change made with the half-on role as answered, one undo step
    flag_row(page, gated['label']).click()
    page.locator('#flagsAsk button', has_text=f"{gated['halfLabel']} on").click()
    flags, steps = state()
    assert page.evaluate(ASK)['hidden'] and steps == 1 and flags and flags.get(gated['role']) == gated['on'] and flags.get(gated['half']) is True, (flags, steps)
    rows = {r[0]: r for r in page.evaluate(FLAG_ROWS)}
    assert rows[gated['halfLabel']][1:3] == [True, False] and rows[gated['label']][1:3] == [gated['on'], False], rows
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press('Control+z')
    assert state() == (None, 0), state()
    page.keyboard.press('Control+y')
    assert state() == (flags, 1), state()
    page.locator('#flagsReset').click()
    assert state()[0] is None
    # an open question closes when another piece is picked, nothing changed
    flag_row(page, gated['label']).click()
    assert not page.evaluate(ASK)['hidden']
    other = page.evaluate("id => [...viewer.roots.values()].find(r => r.visible && !r.userData.source.added && r.userData.source.pieceFlags && r.userData.source.id !== id)?.userData.source.id", gated['id'])
    page.evaluate('id => viewer.select(id)', other)
    page.evaluate('id => viewer.select(id)', gated['id'])
    assert page.evaluate(ASK)['hidden'] and state()[0] is None, page.evaluate(ASK)
    page.close()
    assert not errors, errors
    return dict(prop=gated['actor'], row=gated['label'], half=gated['halfLabel'], flags=flags)


# The right-hand panels that can show while the Map grid is on (they stand where its panel does): each panel's id, how
# a check shows it (given the map's thing it shows, or nothing) and what it is given.
GRID_NEIGHBOURS = (
    ('inspector', 'id => viewer.select(id)', 'piece'),
    ('volumePanel', '() => viewer.setVolumesShown(true)', None),
    ('landingPanel', 'id => { viewer.setZonesShown(true); viewer.pickZone(id); }', 'zone'),
    ('spawnPanel', 'key => { viewer.setSpawnsShown(true); viewer.pickSpawn(key); }', 'spawn'),
    ('effectPanel', 'id => { viewer.setEffectsShown(true); viewer.pickEffect(id); }', 'effect'),
)


def check_grid_panel(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    things = dict(piece=page.evaluate(DRAWN_PIECE), zone=page.evaluate('viewer.zones()[0]?.id ?? null'),
                  spawn=page.evaluate('viewer.spawns().find(e => !e.readOnly)?.key ?? viewer.spawns()[0]?.key ?? null'),
                  effect=page.evaluate('[...viewer.effectRoots.keys()][0] ?? null'))
    assert all(things.values()) and page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview"), \
        ('needs a map with a piece, a landing zone, a spawn point and an effect of its own', things)
    out = {}
    for width, height in ((1280, 800), (1024, 768), (800, 700)):
        page.set_viewport_size(dict(width=width, height=height))
        for panel, show, given in GRID_NEIGHBOURS:
            for first in ('panel', 'tool'):
                where = (width, panel, first)
                if first == 'panel': page.evaluate(show, things.get(given))
                # (the Map grid's row is in the rail's Views list, shown while the pointer is over it)
                page.locator('#viewsButton').hover(); page.locator('#editGrid').click(); page.mouse.move(5, 300)
                if first == 'tool': page.evaluate(show, things.get(given))
                assert page.evaluate('viewer.gridTool().on') and page.locator('#gridPanel').is_visible() \
                    and page.locator(f'#{panel}').is_visible(), where
                grid, beside, rail = (page.locator(f'#{id}').bounding_box() for id in ('gridPanel', panel, 'rail'))
                assert apart(grid, beside) and apart(grid, rail), (where, grid, beside, rail)
                done = page.locator('#gridDone').bounding_box()
                at = [done['x'] + done['width'] / 2, done['y'] + done['height'] / 2]
                hit = page.evaluate("p => { const e = document.elementFromPoint(p[0], p[1]); "
                                    "return e?.closest('#gridDone') ? 'gridDone' : e?.closest('[id]')?.id ?? null; }", at)
                assert hit == 'gridDone', (where, hit, grid, beside)
                page.mouse.click(*at)
                assert not page.evaluate('viewer.gridTool().on') and page.locator('#gridPanel').is_hidden(), where
                # what is picked is kept: the tool only adds its panel
                assert page.locator(f'#{panel}').is_visible(), where
                if panel == 'inspector': assert page.evaluate('viewer.gizmo.active') == things['piece'], where
                page.locator('#viewsButton').hover(); page.locator('#editNormal').click(); page.mouse.move(5, 300)
                page.evaluate('viewer.select(null)')
                assert page.locator(f'#{panel}').is_hidden(), where
            out[f'{width} {panel}'] = dict(grid=[round(grid['x']), round(grid['width'])], panel=[round(beside['x']), round(beside['width'])])
    page.close()
    assert not errors, errors
    return out
