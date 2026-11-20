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
  change: Reset all mends it, and Ctrl+Z breaks it again; broken with another piece deleted, Reset all puts both back."""
import json
import math

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
    # saved (schema 4), read back and placed again: each piece is what it was
    saved = page.evaluate("async () => viewer.savePrefab('Made pieces check')")
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 4, doc['schemaVersion']
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
FOCUS_STOP = """async ([id, k]) => { const { tabStops } = await import('/modal.js'); tabStops(document.getElementById(id)).at(k).focus(); }"""


def modal_case(page, root, opens):
    """One dialog, opened with the header's Map button focused: its Tab ring both ways, the scene's keys kept from what
    is behind, Escape, and the focus back on that button."""
    piece = page.evaluate("[...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden).userData.source.id")
    page.evaluate('id => viewer.select(id)', piece)
    page.evaluate("document.getElementById('mapButton').focus()")
    page.evaluate(opens)
    page.wait_for_selector(f'#{root}:not([hidden])')
    page.wait_for_timeout(150)      # (a dialog's own focus comes a moment after it shows)
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
    page.wait_for_timeout(250)
    page.keyboard.up('w')
    assert not page.evaluate('id => viewer.roots.get(id).userData.deleted', piece), root
    assert page.locator('#mapDialog').is_hidden(), root
    assert page.evaluate('viewer.camera.position.toArray()') == camera, root
    assert page.locator(f'#{root}').is_visible(), root
    page.keyboard.press('Escape')
    page.wait_for_selector(f'#{root}', state='hidden')
    page.wait_for_timeout(50)
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
    page.wait_for_timeout(150)
    assert page.locator('#missionsOk').is_disabled()
    assert page.evaluate("document.activeElement === document.querySelectorAll('#missionsList input')[1]"), page.evaluate(FOCUSED, 'missionsDialog')
    page.keyboard.press('Escape')
    page.wait_for_selector('#missionsDialog', state='hidden')
    assert page.evaluate('document.activeElement?.id') == 'mapButton'
    page.close()
    errors = [e for e in errors if 'status of 404' not in e]
    assert not errors, errors
    return out


# one of the map's own fracturing pieces, standing and drawn (Break works on it: app.js mapBreakable)
BREAKABLE = """[...viewer.roots.values()].filter(r => !r.userData.source.added && !r.userData.deleted && r.visible && !r.userData.source.hidden
  && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
  && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length)).map(r => r.userData.source.id)"""


def break_piece(page, ids):
    """One of the pieces `ids` broken as the user does: picked, framed, B, a click on it. Its id."""
    for piece in ids[:12]:
        page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); document.activeElement?.blur?.(); }', piece)
        page.wait_for_timeout(150)
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
