"""The editor's controls in the browser (the editor controls and clipboard plan), on a test server, never the main one:
run through browser_smoke.py --only <name>.

- step-pick (Part B, Discord S16; needs Bar and Police Station in the library, the prefab builder's pieces): with the
  Ctrl key held, each notch of the wheel over the view selects the next thing under the cursor, nearest first. A piece
  hidden behind another is selected by a click on the front one and one notch, and by two notches from nothing, also
  with another piece's gizmo over the point; wheel up goes back, round at either end. Ctrl+C after a notch copies the
  stepped piece; with Shift the earlier selection stays and one piece is added; a pointer moved off starts a new list;
  a wheel event with ctrlKey set and no key down (a touchpad's pinch) zooms; ten quick notches fill the piece panel
  once. In a group, a click takes it whole and a notch takes one piece of it, which moves, undoes and redoes alone and
  is still in the group after (a click takes the group, the piece where it was moved to); deleted alone, the group
  keeps the rest. A room's wall is picked alone with its Wall section. On Bar, a car's glass is never picked without
  its body.
"""
import browser_walls as bw

# game point -> the camera looking at it along +y from `back` units, level with it
LOOK_ALONG_Y = """([c, back]) => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0], c[2], c[1] - back);
  viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }"""
# a piece of All maps placed with its pivot at a game point: its ids
PLACE = """async ([name, map, at]) => {
  const T = await import('three'), entry = viewer.library.entries().find(e => e.name === name && e.source.package === map);
  if (!entry) throw Error(`the check needs ${name} of ${map} in the library`);
  const t = await viewer.libraryTemplate(entry.source), before = new Set(viewer.roots.keys());
  const delta = new T.Matrix4().makeTranslation(at[0], at[2], at[1]).multiply(t.frame);
  await viewer.pasteSnapshot({entries: t.sources.map(source => ({source, matrix: new T.Matrix4().fromArray(source.matrix)})), volumes: [], pivotIndex: 0}, delta);
  return [...viewer.roots.keys()].filter(id => !before.has(id));
}"""
# the middle of a piece's box, game units
MIDDLE = "id => { const b = viewer.pieceBox(id); return [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]; }"
# the selection: what is picked, those picked alone, and every root it takes
PICKS = "(() => { const p = viewer.gizmo.picks(); return { ids: p.ids, loose: p.loose, all: viewer.gizmo.selection().map(r => r.userData.source.id).sort() }; })()"


def check_step_pick(browser, url, open_viewer):
    base = url.split('?')[0]
    errors = []
    page = open_viewer(browser, base + '?prefab=new', errors)
    hint = page.locator('#dragHint')
    page.evaluate('viewer.setLibraryScope("all"); viewer.showPieces(true)')
    page.wait_for_function('viewer.library.ready()', timeout=120000)
    page.evaluate('viewer.showPieces(false)')
    # An arcade machine, and a computer behind it: its middle on the line from the camera through the arcade's
    front = page.evaluate(PLACE, ['ArcadeMachineA', 'URB_Bar', [0, 0, 0]])[0]
    behind = page.evaluate(PLACE, ['Computer_A', 'URB_PoliceStation', [0, 600, 0]])[0]
    at, was = page.evaluate(MIDDLE, front), page.evaluate(MIDDLE, behind)
    page.evaluate('''async ([id, d]) => { const T = await import('three'); viewer.gizmo.setSelection([id]);
      viewer.gizmo.moveBy(new T.Matrix4().makeTranslation(d[0], d[2], d[1])); viewer.select(null); }''',
                  [behind, [at[0] - was[0], at[1] + 300 - was[1], at[2] - was[2]]])
    page.evaluate(LOOK_ALONG_Y, [at, 1400]); page.wait_for_timeout(300)
    point = page.evaluate('p => viewer.screenOf(p)', at)
    page.mouse.move(*point)

    def notch(down=True, shift=False):
        if shift: page.keyboard.down('Shift')
        page.mouse.wheel(0, 100 if down else -100)
        if shift: page.keyboard.up('Shift')
        page.wait_for_timeout(30)
        return page.evaluate(PICKS)

    def alone(picks, id): return picks['ids'] == [id] and picks['loose'] == [id], picks

    def fresh():        # (each hold of the Ctrl key steps through a list of its own)
        page.keyboard.up('Control'); page.keyboard.down('Control')
    # From nothing: the front piece, then the one behind it, then round to the front; wheel up goes back
    page.keyboard.down('Control')
    assert alone(notch(), front)
    assert hint.inner_text().startswith('1 of 2 under the cursor: '), hint.inner_text()
    assert alone(notch(), behind) and hint.inner_text().startswith('2 of 2 under the cursor')
    assert alone(notch(), front)
    assert alone(notch(down=False), behind)
    page.keyboard.up('Control')
    # A click takes the front piece; one notch the one behind it
    page.evaluate('viewer.select(null)')        # (the gizmo of the piece behind stands over the point: a click would take it)
    page.mouse.click(*point)
    assert page.evaluate(PICKS)['ids'] == [front]
    page.keyboard.down('Control')
    assert alone(notch(), behind)
    # The piece behind's gizmo over the point: a click would take a handle, the wheel steps through the pieces all the same
    page.keyboard.up('Control')
    handle = page.evaluate('id => viewer.screenOf(viewer.gizmo.pose().location)', behind)
    page.mouse.move(*handle)
    page.wait_for_function('viewer.gizmo.controls.axis !== null', timeout=5000)
    page.keyboard.down('Control')
    stepped = notch()
    assert stepped['ids'] in ([front], [behind]) and stepped['loose'] == stepped['ids'], stepped
    # Ctrl+C after a notch copies the stepped piece, Ctrl still down
    page.mouse.move(*point)
    page.evaluate('viewer.select(null)')
    fresh()
    assert alone(notch(), front) and alone(notch(), behind)
    page.keyboard.press('c')
    assert page.evaluate('viewer.clipboard().entries.map(e => e.source.id)') == [behind]
    # With Shift the selection before stays and one piece is added (what it holds already passed over)
    page.keyboard.up('Control'); page.evaluate('viewer.select(null)')
    page.mouse.click(*point)
    page.keyboard.down('Control')
    added = notch(shift=True)
    assert sorted(added['ids']) == sorted([front, behind]) and added['loose'] == [behind], added
    assert hint.inner_text().endswith('added to the selection'), hint.inner_text()
    # A pointer moved off starts a new list: over nothing, nothing to pick and the selection kept; back, a fresh list
    page.evaluate('viewer.select(null)')
    fresh()
    assert alone(notch(), front)
    page.mouse.move(point[0] + 600, point[1] - 300)
    assert alone(notch(), front) and hint.inner_text() == 'Nothing under the cursor to pick'
    page.mouse.move(*point)
    assert alone(notch(), behind)
    # Ten quick notches fill the piece panel once, once the wheel rests
    page.evaluate('''() => { window.__fills = 0; new MutationObserver(() => window.__fills++).observe(document.getElementById('details'), {childList: true}); }''')
    for _ in range(10): page.mouse.wheel(0, 100)
    page.wait_for_timeout(400)
    assert page.evaluate('window.__fills') == 1, page.evaluate('window.__fills')
    # A touchpad's pinch (ctrlKey set, no key down) zooms: the camera moves, the selection stays
    page.keyboard.up('Control')
    picks, camera = page.evaluate(PICKS), page.evaluate('viewer.camera.position.toArray()')
    page.evaluate('''([x, y]) => viewer.renderer.domElement.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, ctrlKey: true,
      clientX: x, clientY: y, bubbles: true, cancelable: true}))''', point)
    assert page.evaluate('viewer.camera.position.toArray()') != camera and page.evaluate(PICKS) == picks
    page.evaluate(LOOK_ALONG_Y, [at, 1400]); page.wait_for_timeout(300)
    # A group: a click takes it whole; a notch one piece of it, which moves, undoes and redoes alone, still a member
    page.evaluate('ids => viewer.gizmo.setSelection(ids)', [front, behind])
    page.keyboard.press('Control+g')
    assert len(page.evaluate('viewer.groupList()')) == 1
    page.evaluate('viewer.select(null)')
    page.mouse.click(*point)
    assert page.evaluate(PICKS)['all'] == sorted([front, behind])
    page.keyboard.down('Control')
    assert alone(notch(), front)
    page.keyboard.up('Control')
    page.wait_for_timeout(300)
    assert page.locator('#groupText').inner_text() == 'One of the 2 pieces of this group, picked on its own · a click picks the group', \
        page.locator('#groupText').inner_text()
    assert page.evaluate('viewer.highlight.material.color.getHex()') == 0x96e5d7
    before = page.evaluate('ids => ids.map(id => viewer.pieceBox(id))', [front, behind])
    page.evaluate("async () => { const T = await import('three'); viewer.gizmo.moveBy(new T.Matrix4().makeTranslation(96, 0, 0)); }")
    moved = page.evaluate('ids => ids.map(id => viewer.pieceBox(id))', [front, behind])
    assert abs(moved[0][0] - before[0][0] - 96) < 0.01 and moved[1] == before[1], (before, moved)
    page.keyboard.press('Control+z')
    assert page.evaluate('ids => ids.map(id => viewer.pieceBox(id))', [front, behind]) == before
    page.keyboard.press('Control+y')
    assert page.evaluate('ids => ids.map(id => viewer.pieceBox(id))', [front, behind]) == moved
    assert alone(page.evaluate(PICKS), front)
    assert len(page.evaluate('viewer.groupList()')[0]['members']) == 2
    page.evaluate('viewer.select(null)')
    page.mouse.click(*page.evaluate('p => viewer.screenOf(p)', [at[0] + 96, at[1], at[2]]))
    assert page.evaluate(PICKS)['all'] == sorted([front, behind]), page.evaluate(PICKS)
    # Deleted alone, the group keeps the rest; Ctrl+Z brings it back, picked alone as it was
    page.keyboard.down('Control')
    page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', [at[0] + 96, at[1], at[2]]))
    assert alone(notch(), front)
    page.keyboard.up('Control')
    page.keyboard.press('Delete')
    assert page.evaluate('ids => ids.map(id => viewer.roots.has(id))', [front, behind]) == [False, True]
    assert len(page.evaluate('viewer.groupList()')) == 1
    page.keyboard.press('Control+z')
    assert alone(page.evaluate(PICKS), front)
    # A room's wall picked alone shows the Wall section
    room = bw.draw_room(page, 'room')
    wall = room[0]
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#roomBox:not([hidden])')
    page.mouse.move(*page.evaluate('id => { const b = viewer.pieceBox(id); return viewer.screenOf([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, b[5] - 8]); }', wall))
    page.keyboard.down('Control')
    picked = notch()
    page.keyboard.up('Control')
    assert len(picked['all']) == 1 and picked['all'][0] in room, picked
    page.wait_for_selector('#wallBox:not([hidden])', timeout=5000)
    assert page.locator('#roomBox').is_hidden()
    page.close()
    # On Bar: a car's glass is never picked without its body (an assembly is one thing to the wheel)
    page = open_viewer(browser, base + '?map=URB_Bar', errors)
    # (linked pieces off: what still goes together is an actor's parts and an assembly)
    pair = page.evaluate('''() => { viewer.gizmo.setLinked(false); const ids = [...viewer.roots.values()].filter(r => !r.userData.deleted).map(r => r.userData.source.id);
      const keys = viewer.gizmo.looseKeys(ids), by = new Map();
      for (const [id, k] of keys) { const a = viewer.roots.get(id).userData.source.actor; if (!by.has(k)) by.set(k, new Map()); by.get(k).set(a, id); }
      const two = [...by.values()].find(m => m.size >= 2); return two ? [...two.values()] : null; }''')
    assert pair, 'Bar has no assembly of two actors (a car\'s body and glass)'
    page.evaluate('id => viewer.gizmo.select(id, false, true)', pair[1])
    assert set(pair) <= set(page.evaluate(PICKS)['all'])
    assert not errors, errors
    page.close()
    return dict(front=front, behind=behind, assembly=len(pair))


# the camera behind game point `a`, looking at it along the line from it to `b` (`up` units higher)
ALONG = """([a, b, back, up]) => { const V = viewer.camera.position.constructor, A = new V(a[0], a[2], a[1]), B = new V(b[0], b[2], b[1]);
  const d = B.clone().sub(A).normalize(); viewer.controls.target.copy(A);
  viewer.camera.position.copy(A).addScaledVector(d, -back).add(new V(0, up, 0)); viewer.camera.lookAt(A); viewer.controls.update(); }"""


def check_step_views(browser, url, open_viewer):
    """Ctrl and the wheel in the views of their own (Part B, stage B2), on Bar: two lights, two effects, two floor boxes,
    two spawn points and two landing zones, each pair one behind the other (or overlapping): a round of notches reaches
    both, the nearer first, in the view that is on (and only that view's things: the steps are what its picks take)."""
    errors = []
    page = open_viewer(browser, url.split('?')[0] + '?map=URB_Bar', errors)
    hint = page.locator('#dragHint')

    def steps(a, b, picked, back=900, up=0, at=None):
        page.evaluate(ALONG, [a, b, back, up]); page.wait_for_timeout(300)
        page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', at or a))
        # (a whole round: as many notches as the hint counts things under the cursor; others may stand on the line too)
        page.keyboard.down('Control')
        page.mouse.wheel(0, 100); page.wait_for_timeout(30)
        words = hint.inner_text()
        count = int(words.split(' of ')[1].split(' ')[0]) if ' under the cursor' in words else 1
        got = [page.evaluate(picked)]
        for _ in range(count - 1):
            page.mouse.wheel(0, 100); page.wait_for_timeout(30)
            got.append(page.evaluate(picked))
        page.keyboard.up('Control')
        return got, words

    def nearer_first(got, a, b):
        assert a in got and b in got and got.index(a) < got.index(b) and len(set(got)) == len(got), (got, a, b)

    out = {}
    # the Lights view: one of the map's lights and a copy of it behind
    page.evaluate('viewer.setLightsShown(true)')
    light = page.evaluate("[...viewer.lightRoots.values()].find(r => r.visible && !r.userData.source.added && r.userData.source.role !== 'area')?.userData.source.id")
    assert light, 'Bar has no light to copy'
    page.evaluate('id => viewer.select(id)', light)
    at = page.evaluate('id => { const p = viewer.lightRoots.get(id).position.clone().setFromMatrixPosition(viewer.lightRoots.get(id).matrix); return [p.x, p.z, p.y]; }', light)
    page.evaluate("async () => { const T = await import('three'); await viewer.pasteSnapshot(viewer.snapshot(), new T.Matrix4().makeTranslation(0, 0, 400)); }")
    copy = page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    got, words = steps(at, [at[0], at[1] + 400, at[2]], 'viewer.gizmo.active')
    nearer_first(got, light, copy)
    out['lights'] = words
    page.evaluate('viewer.setLightsShown(false)')
    # the Effects view: one of the map's effects and a copy of it behind
    page.evaluate('viewer.setEffectsShown(true)')
    marker = page.evaluate('viewer.effectMarkers().find(m => !m.derived && !m.added && m.screen)')
    assert marker, 'Bar has no effect to copy'
    page.evaluate('id => viewer.select(id)', marker['id'])
    page.evaluate("async () => { const T = await import('three'); await viewer.pasteSnapshot(viewer.snapshot(), new T.Matrix4().makeTranslation(0, 0, 400)); }")
    copy = page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    a = marker['at']
    got, words = steps(a, [a[0], a[1] + 400, a[2]], 'viewer.gizmo.active')
    nearer_first(got, marker['id'], copy)
    out['effects'] = words
    page.evaluate('viewer.setEffectsShown(false)')
    # the Buildings view: two floor boxes of a new building, one behind the other
    o = page.evaluate('viewer.data.tileGrid.origin')
    x, y, z = o[0] + 960, o[1] + 960, o[2]
    live = '[...viewer.volumeRoots.values()].filter(r => !r.userData.deleted).map(r => [r.userData.source.id, viewer.volumeBox(r)])'
    was = {i for i, _ in page.evaluate(live)}
    page.evaluate('b => { viewer.addVolumes(b); }', [dict(box=[x, y, z, x + 192, y + 192, z + 192], floor=0),
                                                    dict(box=[x, y + 480, z, x + 192, y + 672, z + 192], floor=0)])
    page.evaluate('viewer.setVolumesShown(true)')
    near, far = [i for i, b in sorted((e for e in page.evaluate(live) if e[0] not in was), key=lambda e: e[1][1])]
    middle = [x + 96, y + 96, z + 96]
    got, words = steps(middle, [middle[0], middle[1] + 480, middle[2]], 'viewer.gizmo.active', back=1200)
    nearer_first(got, near, far)
    out['buildings'] = words
    page.evaluate('viewer.setVolumesShown(false)')
    # the Spawns view: a spawn point and its copy a tile along x, the camera along x
    page.evaluate('viewer.setSpawnsShown(true)')
    spot = page.evaluate("viewer.spawns().find(s => s.layer === 'base' && s.marked && ['pod', 'meld'].includes(s.kind))")
    assert spot, 'Bar has no spawn point to copy'
    page.evaluate('k => viewer.copySpawn(k)', spot['key'])
    copy = page.evaluate('viewer.pickedSpawn()')
    page.evaluate('viewer.pickSpawn(null)')
    a = spot['at']
    got, words = steps(a, [a[0] + 96, a[1], a[2]], 'viewer.pickedSpawn()', back=700)
    nearer_first(got, spot['key'], copy)
    out['spawns'] = words
    page.evaluate('viewer.setSpawnsShown(false)')
    # the Landing zones view: a zone and its copy two tiles along x (Ctrl+D), seen from above where they overlap
    page.evaluate('viewer.setZonesShown(true)')
    zone = page.evaluate('viewer.zones()[0]')
    page.evaluate('id => viewer.pickZone(id)', zone['id'])
    page.keyboard.press('Control+d')
    copy = page.evaluate('viewer.pickedZone()')
    assert copy != zone['id']
    page.evaluate('viewer.pickZone(null)')
    l = zone['location']
    got, words = steps([l[0] + 96, l[1], l[2]], [l[0] + 96, l[1] + 1, l[2] - 2000], 'viewer.pickedZone()', back=1, up=1600)
    assert zone['id'] in got and copy in got, (got, zone['id'], copy)
    out['zones'] = words
    assert not errors, errors
    page.close()
    return out
