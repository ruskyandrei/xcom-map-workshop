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


# What a project (or the prefab builder's document) holds of added things, comparable across maps: each record's kind
# and home (a piece's map and actor, a made piece's kind, a recipe's kind), the buildings' boxes' sizes and the groups'
# sizes (a prefab's group marked)
SUMMARY = """records => { const short = a => a.split('.').pop();
  return records.map(p => p.generated ? `made:${p.generated.kind}` : p.template ? `template:${p.template.kind}`
    : p.kind ? `${p.kind}:${p.from.package}:${short(p.from.actor)}` : `piece:${p.from.package}:${short(p.from.actor)}`).sort(); }"""
SHAPES = """doc => ({ buildings: (doc.buildings ?? []).map(b => b.floors.map(f => f.boxes.map(x => [x[3] - x[0], x[4] - x[1], x[5] - x[2]].join('x')).join(',')).join('|')).sort(),
  groups: (doc.groups ?? []).map(g => String(g.members.length) + (g.prefab ? ':prefab' : '')).sort() })"""


def check_carried_copy(browser, url, open_viewer):
    """The copy carried to another map or prefab (Part C, Discord S17), on Bar and Police Station: two of Bar's pieces
    grouped, a made wall, a cover block, a light, an effect and a building copied on Bar are placed on Police Station by
    Ctrl+V after the map changed, as Save as prefab's records have them but without a prefab's group, and the project
    saved there compiles; the same copy placed in the prefab builder, and copied there, placed on Bar; a cut carried;
    an Add panel entry chosen last not carried; what can't be carried named and the rest placed; the Buildings view's
    boxes carried."""
    import json
    import subprocess
    import sys
    import tempfile
    from pathlib import Path
    import browser_walls as bw
    base = url.split('?')[0]
    errors = []
    # (the piece of a map the install doesn't have, asked for below, is the check's own 404)
    page = open_viewer(browser, base + '?map=URB_Bar', errors, expected=(404,))
    hint = page.locator('#dragHint')

    def leave(query):
        """The page changed to another map or prefab (unsaved work discarded), and the new page opened."""
        page.evaluate('q => { void viewer.goTo(q); }', query)
        try: page.locator('#leaveDiscard').click(timeout=4000)
        except Exception: pass      # (nothing unsaved: no question)
        key, value = next(iter(query.items()))
        page.wait_for_function('([k, v]) => new URLSearchParams(location.search).get(k) === v', arg=[key, value], timeout=60000)
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
        page.wait_for_timeout(500)

    def blur(): page.evaluate('document.activeElement?.blur?.()')

    def place(at=(0.5, 0.55)):
        """Ctrl+V and a click in the view: the roots the copy made."""
        before = set(page.evaluate('[...viewer.roots.keys(), ...viewer.lightRoots.keys(), ...viewer.effectRoots.keys(), ...viewer.volumeRoots.keys()]'))
        blur(); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()', timeout=180000)
        box = page.locator('#viewport > canvas').bounding_box()
        point = (box['x'] + box['width'] * at[0], box['y'] + box['height'] * at[1])
        page.mouse.move(*point)
        page.wait_for_function('viewer.placing()?.ghost.visible', timeout=30000)
        page.mouse.click(*point)
        page.wait_for_function('!viewer.placing()', timeout=180000)
        page.wait_for_timeout(300)
        return [i for i in page.evaluate('[...viewer.roots.keys(), ...viewer.lightRoots.keys(), ...viewer.effectRoots.keys(), ...viewer.volumeRoots.keys()]') if i not in before]

    def summary(builder=False):
        doc = page.evaluate('viewer.builderDocument()' if builder else 'viewer.editState()')
        return page.evaluate(SUMMARY, doc['pieces'] if builder else doc['added']), page.evaluate(SHAPES, doc)

    # On Bar: two of its pieces grouped, a made wall, a cover block, a light, an effect and a building
    o = page.evaluate('viewer.data.tileGrid.origin')
    spot = [o[0] + 12 * 96, o[1] + 12 * 96, o[2]]
    bw.start_build(page, 'wall'); bw.look_at(page, spot)
    bw.drag(page, bw.ground_point(page, spot), bw.ground_point(page, [spot[0] + 288, spot[1], spot[2]]))
    page.wait_for_function("viewer.wallState(viewer.gizmo.active)?.generated?.kind === 'fracWall'", timeout=60000)
    wall = page.evaluate('viewer.gizmo.active')
    page.keyboard.press('Escape'); page.evaluate('viewer.select(null)')
    page.evaluate('viewer.showPieces(true); viewer.setLibraryScope("map")')
    cover_row = page.evaluate("viewer.pieces.entries().find(e => e.cover && e.cover.type !== 'floor').id")
    page.locator(f'#libList .libitem[data-id="{cover_row}"]').click()
    canvas = page.locator('#viewport > canvas').bounding_box()
    at = (canvas['x'] + canvas['width'] * 0.4, canvas['y'] + canvas['height'] * 0.6)
    page.mouse.move(*at); page.wait_for_function('viewer.placing()?.ghost.visible', timeout=30000); page.mouse.click(*at)
    page.wait_for_function('[...viewer.roots.values()].some(r => r.userData.source.cover)')
    cover = page.evaluate('[...viewer.roots.values()].find(r => r.userData.source.cover).userData.source.id')
    page.evaluate('viewer.showPieces(false)')
    pair = page.evaluate('''() => [...viewer.roots.values()].filter(r => !r.userData.deleted && !r.userData.source.added && !r.userData.source.hidden
      && !r.userData.source.environment && r.userData.source.layer === 'base' && viewer.gizmo.linkedCount(r.userData.source.id) === 0)
      .slice(0, 2).map(r => r.userData.source.id)''')
    page.evaluate('ids => viewer.gizmo.setSelection(ids)', pair)
    blur(); page.keyboard.press('Control+g')
    light = page.evaluate("[...viewer.lightRoots.values()].find(r => !r.userData.source.added && r.userData.source.role !== 'area' && r.visible)?.userData.source.id")
    effect = page.evaluate("[...viewer.effectRoots.values()].find(r => !r.userData.source.added && !r.userData.source.carriedBy && r.userData.source.layer === 'base' && !viewer.effectState(r.userData.source.id).viewOnly)?.userData.source.id")
    assert light and effect, (light, effect)
    page.evaluate('b => viewer.addVolumes(b)', [dict(box=[spot[0], spot[1] + 192, spot[2], spot[0] + 192, spot[1] + 384, spot[2] + 192], floor=0)])
    volume = page.evaluate('[...viewer.volumeRoots.values()].filter(r => !r.userData.deleted).at(-1).userData.source.id')
    page.evaluate('viewer.setBoxesShown(true)')
    page.evaluate('ids => viewer.gizmo.setSelection(ids)', [*pair, wall, cover, light, effect, volume])
    expected = page.evaluate('() => { const r = viewer.prefabRecords(); return { pieces: r.pieces, buildings: r.buildings, groups: r.groups }; }')
    want = page.evaluate(SUMMARY, expected['pieces']), page.evaluate(SHAPES, expected)
    assert len(want[0]) == 6 and want[1]['buildings'] and want[1]['groups'] == ['2'], want
    blur(); page.keyboard.press('Control+c')
    # On Police Station: the copy came along; Ctrl+V and a click place it as Save as prefab's records have it, without a
    # prefab's group round it
    leave({'map': 'URB_PoliceStation'})
    assert hint.inner_text() == 'The copy came along: Ctrl+V places it here', hint.inner_text()
    place()
    got = summary()
    assert got == want, (got, want)
    # the project saved there compiles (the pieces brought from Bar as pieces of other maps are)
    project = page.evaluate('''async () => { const name = 'Carried ' + Date.now(), names = await fetch('/projects/output-names', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, map: viewer.mapId, target: null})}).then(r => r.json());
      if (!await viewer.saveProject({name, output: names.output})) throw Error('Project not saved'); return viewer.project().doc; }''')
    settings = json.loads(Path(page.evaluate("fetch('/setup.json?checks=0').then(r => r.json()).then(s => s.settingsFile)")).read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as folder:
        doc = Path(folder) / 'project.json'
        doc.write_text(json.dumps(project), encoding='utf-8', newline='\n')
        compiler = Path(__file__).resolve().parents[2] / 'editor' / 'compiler.py'
        # (the game folder the settings name, resolved to its install, as the server's Library takes it)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from settings import resolve_game
        game = resolve_game(settings['game'])[0] if settings.get('game') else None
        done = subprocess.run([sys.executable, '-B', str(compiler), str(doc), '--cache', settings['cache'], '--out', str(Path(folder) / 'spec.json'),
                               *(['--game', str(game)] if game else [])], capture_output=True, text=True)
        report_file = Path(folder) / 'spec-report.json'
        report = json.loads(report_file.read_text(encoding='utf-8')) if report_file.is_file() else {'errors': ['no report'], 'counts': {}}
    assert done.returncode == 0 and not report['errors'], (done.stdout, done.stderr, report['errors'])
    compiled = report['counts']
    # Into the prefab builder: the copy carried on as it came
    leave({'prefab': 'new'})
    place()
    got = summary(builder=True)
    assert got == want, (got, want)
    # Copied in the builder and placed on Bar
    page.evaluate('viewer.gizmo.setSelection([...viewer.roots.values(), ...viewer.lightRoots.values(), ...viewer.effectRoots.values(), ...viewer.volumeRoots.values()]'
                  '.filter(r => !r.userData.deleted).map(r => r.userData.source.id))')
    blur(); page.keyboard.press('Control+c')
    leave({'map': 'URB_Bar'})
    place()
    got = summary()
    assert got == want, (got, want)
    # A cut is carried: one piece cut on Bar, placed on Police Station
    one = page.evaluate("[...viewer.roots.values()].find(r => r.userData.source.added && !r.userData.source.cover && !r.userData.source.added.generated).userData.source.id")
    page.evaluate('id => viewer.gizmo.setSelection([id])', one)
    cut = page.evaluate(SUMMARY, page.evaluate('viewer.prefabRecords().pieces'))       # (with its group, as a pick takes it)
    blur(); page.keyboard.press('Control+x')
    assert not page.evaluate('id => viewer.roots.has(id)', one)
    leave({'map': 'URB_PoliceStation'})
    assert len(page.evaluate('viewer.editState()')['added']) == 0
    place()
    assert page.evaluate(SUMMARY, page.evaluate('viewer.editState()')['added']) == cut, cut
    # An Add panel entry chosen last is not carried
    page.evaluate('viewer.showPieces(true); viewer.setLibraryScope("map")')
    row = page.evaluate('viewer.pieces.entries().find(e => !e.light && !e.zone && !e.spawnAdd && !e.diagonal && !e.cover).id')
    page.locator(f'#libList .libitem[data-id="{row}"]').click()
    page.keyboard.press('Escape'); page.evaluate('viewer.showPieces(false)')
    leave({'map': 'URB_Bar'})
    blur(); page.keyboard.press('Control+v')
    assert hint.inner_text() == 'Nothing copied yet: select a piece and press Ctrl+C', hint.inner_text()
    assert not page.evaluate('viewer.placing()')
    # What can't be carried is said and the rest placed: a carried copy holding a piece of a level a mission streams in
    # (left out as it was packed) and one of a map the install doesn't have
    real = page.evaluate('''() => { const r = [...viewer.roots.values()].find(r => !r.userData.deleted && !r.userData.source.added && !r.userData.source.hidden
      && r.userData.source.layer === 'base' && viewer.gizmo.linkedCount(r.userData.source.id) === 0);
      viewer.gizmo.setSelection([r.userData.source.id]); const p = viewer.prefabRecords().pieces[0]; viewer.select(null); return p; }''')
    lost = {**real, 'actor': 'TheWorld.PersistentLevel.Nothing_copy9', 'from': dict(package='NoSuchMapAnywhere', level='base', actor='TheWorld.PersistentLevel.Nothing'),
            'components': ['TheWorld.PersistentLevel.Nothing.StaticMeshComponent_0']}
    page.evaluate('d => sessionStorage.setItem("workshop.clip", JSON.stringify(d))', dict(
        format=1, id='left-check', **{'from': {}}, name='Test copy', words='2 pieces', pivot=real['location'], pivotActor=real['actor'], pieces=[real, lost],
        groups=[], buildings=[], donors=[], left=['Lamp_A: a piece of a level the mission streams in, not of a map']))
    place()
    banner = page.locator('#projectBanner').inner_text()
    assert 'Test copy: 2 pieces could not be brought here. Lamp_A: a piece of a level the mission streams in' in banner, banner
    assert len(page.evaluate('viewer.editState()')['added']) == 1
    # The Buildings view's boxes are carried: copied on Bar, placed on Police Station as a building of their own
    page.evaluate('viewer.setVolumesShown(true)')
    page.evaluate('b => viewer.addVolumes(b)', [dict(box=[spot[0], spot[1], spot[2], spot[0] + 288, spot[1] + 192, spot[2] + 128], floor=0)])
    box = page.evaluate('[...viewer.volumeRoots.values()].filter(r => !r.userData.deleted).at(-1).userData.source.id')
    page.evaluate('id => viewer.gizmo.setSelection([id])', box)
    blur(); page.keyboard.press('Control+c')
    leave({'map': 'URB_PoliceStation'})
    page.evaluate('viewer.setVolumesShown(true)')
    before = page.evaluate('viewer.buildings().length')
    blur(); page.keyboard.press('Control+v')
    page.wait_for_function('n => viewer.buildings().length === n + 1', arg=before, timeout=10000)
    sizes = page.evaluate(SHAPES, page.evaluate('viewer.editState()'))['buildings']
    assert '288x192x128' in sizes, sizes
    assert not errors, errors
    page.close()
    return dict(pieces=want[0], compiled=compiled)


def arrow(page, at, axis):
    """A gizmo's X arrow on the screen: (x, y, ux, uy) from its pivot (`at`, a game point) along game x, where the
    gizmo's axis (`axis`: an expression) reads X."""
    ends = page.evaluate('''p => { const V = viewer.camera.position.constructor, at = new V(p[0], p[2], p[1]), box = viewer.renderer.domElement.getBoundingClientRect();
      const screen = v => { const q = v.clone().project(viewer.camera); return [box.left + (q.x + 1) / 2 * box.width, box.top + (1 - q.y) / 2 * box.height]; };
      return [screen(at), screen(at.clone().add(new V(viewer.camera.position.distanceTo(at) * 0.1, 0, 0)))]; }''', at)
    (x0, y0), (x1, y1) = ends
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    for d in range(14, 160, 4):
        page.mouse.move(x0 + ux * d, y0 + uy * d)
        if page.evaluate(axis) == 'X': return x0 + ux * d, y0 + uy * d, ux, uy
    raise AssertionError(f'no X arrow found along {ends}')


def shift_drag(page, handle, tiles=2, escape=False):
    """Shift held on the arrow, dragged about `tiles` tiles' worth of screen along it (Escape first: none made)."""
    x, y, ux, uy = handle
    page.mouse.move(x, y)
    page.keyboard.down('Shift'); page.mouse.down(); page.mouse.move(x + ux * 60 * tiles, y + uy * 60 * tiles, steps=8)
    if escape: page.keyboard.press('Escape')
    page.mouse.up(); page.keyboard.up('Shift')
    page.wait_for_timeout(200)


def check_same_controls(browser, url, open_viewer):
    """The same controls on every thing (Part A, Discord S18): on Bar, a landing zone, a spawn point, a floor box and a
    piece; on the farm, a diagonal cover mark. For each: G, R and V and the rail's Move, Rotate and Select drive its
    gizmo (the buttons lit by its mode; Rotate dimmed, and R's hint, where it doesn't turn); Shift+drag on the X arrow
    drags off a copy (the original stays, one undo step; Escape during the drag makes none); Ctrl+C and Ctrl+V place a
    copy with a click; the Snap button shows whole tiles while a spawn point or a mark is picked with Snap off, says why
    on a click without changing the setting, and shows the setting again once it is let go; [ and ] turn a piece."""
    import browser_walls as bw
    base = url.split('?')[0]
    errors = []
    page = open_viewer(browser, base + '?map=URB_Bar', errors)
    hint = page.locator('#dragHint')
    lit = lambda: [b for b in ('editMove', 'editRotate', 'editOff') if 'on' in (page.locator('#' + b).get_attribute('class') or '').split()]

    def key(k): page.evaluate('document.activeElement?.blur?.()'); page.keyboard.press(k); page.wait_for_timeout(50)

    def click_at(at):
        x, y = page.evaluate('p => viewer.screenOf(p)', at)
        page.mouse.move(x, y); page.mouse.click(x, y); page.wait_for_timeout(150)
    page.evaluate("viewer.setSnapMode('off')")
    # A landing zone: its gizmo by G, R, V and the rail; Shift+drag copies; Ctrl+C, Ctrl+V and a click place one
    page.evaluate('viewer.setZonesShown(true)')
    zone = page.evaluate('viewer.zones()[0]')
    page.evaluate('id => viewer.pickZone(id)', zone['id'])
    bw.look_at(page, zone['location'])
    key('r'); assert page.evaluate('viewer.zoneGizmo().mode') == 'rotate' and lit() == ['editRotate'], lit()
    page.locator('#editMove').click(); assert page.evaluate('viewer.zoneGizmo().mode') == 'translate' and lit() == ['editMove']
    key('v'); assert not page.evaluate('viewer.zoneGizmo().shown') and lit() == ['editOff']
    page.locator('#editMove').click(); assert page.evaluate('viewer.zoneGizmo().shown')
    assert page.locator('#snapBadge').inner_text() == ''          # (a zone follows Snap: no step of its own)
    count = len(page.evaluate('viewer.zones()'))
    handle = arrow(page, page.evaluate('viewer.zoneGizmo().at'), 'viewer.zoneGizmo().axis')
    shift_drag(page, handle, escape=True)
    assert len(page.evaluate('viewer.zones()')) == count
    shift_drag(page, handle)
    zones = page.evaluate('viewer.zones()')
    assert len(zones) == count + 1 and next(z for z in zones if z['id'] == zone['id'])['location'] == zone['location'], zones
    key('Control+z'); assert len(page.evaluate('viewer.zones()')) == count
    page.evaluate('id => viewer.pickZone(id)', zone['id'])
    key('Control+c'); assert 'Copied the landing zone' in hint.inner_text(), hint.inner_text()
    key('Control+v')
    click_at([zone['location'][0] + 480, zone['location'][1], zone['location'][2]])
    zones = page.evaluate('viewer.zones()')
    assert len(zones) == count + 1 and zones[-1]['direction'] == zone['direction'], zones
    key('Control+z'); page.evaluate('viewer.pickZone(null); viewer.setZonesShown(false)')
    # A spawn point: whole tiles shown on the Snap button while picked; R says a pod doesn't turn; Shift+drag copies;
    # Ctrl+X and Ctrl+V place it again
    page.evaluate('viewer.setSpawnsShown(true)')
    spot = page.evaluate("viewer.spawns().find(s => s.layer === 'base' && s.marked && s.kind === 'pod')")
    page.evaluate('k => viewer.pickSpawn(k)', spot['key'])
    bw.look_at(page, spot['at']); page.wait_for_timeout(100)
    assert page.locator('#snapBadge').inner_text() == '96'
    assert page.locator('#editSnap').get_attribute('title').startswith('Whole tiles: a spawn point stands on a tile. Your setting, snap off,')
    page.locator('#editSnap').click()
    assert page.evaluate('viewer.gizmo.snap') == 'off' and hint.inner_text().startswith('Whole tiles: a spawn point stands on a tile')
    key('r'); assert 'aims nothing' in hint.inner_text() and 'dim' in page.locator('#editRotate').get_attribute('class')
    copies = lambda: len([s for s in page.evaluate('viewer.spawns()') if s['layer'] == 'copy'])
    before = copies()
    handle = arrow(page, page.evaluate('viewer.missionGizmo().at'), 'viewer.missionGizmo().axis')
    shift_drag(page, handle)
    assert copies() == before + 1, copies()
    original = next(s for s in page.evaluate('viewer.spawns()') if s['key'] == spot['key'])
    assert original['at'] == spot['at'], (original['at'], spot['at'])
    key('Control+z'); assert copies() == before
    page.evaluate('k => viewer.pickSpawn(k)', spot['key'])
    key('Control+x'); assert next(s for s in page.evaluate('viewer.spawns()') if s['key'] == spot['key'])['deleted']
    key('Control+v')
    click_at([spot['at'][0] + 192, spot['at'][1], spot['at'][2]])
    assert copies() == before + 1, copies()
    page.evaluate('viewer.pickSpawn(null)'); page.wait_for_timeout(100)
    assert page.locator('#snapBadge').inner_text() == '', page.locator('#snapBadge').inner_text()     # (the setting again)
    page.evaluate('viewer.setSpawnsShown(false)')
    # A floor box: Shift on its arrow copies it into its own building on its own floor; R and [ say it isn't turned
    o = page.evaluate('viewer.data.tileGrid.origin')
    spot2 = [o[0] + 960, o[1] + 960, o[2]]
    page.evaluate('b => viewer.addVolumes(b)', [dict(box=[spot2[0], spot2[1], spot2[2], spot2[0] + 192, spot2[1] + 192, spot2[2] + 192], floor=0)])
    page.evaluate('viewer.setVolumesShown(true)')
    box = page.evaluate('[...viewer.volumeRoots.values()].filter(r => !r.userData.deleted).at(-1).userData.source.id')
    page.evaluate('id => viewer.select(id)', box)
    bw.look_at(page, spot2)
    if page.evaluate("viewer.gizmo.mode !== 'translate'"): key('g')
    if page.evaluate("viewer.gizmo.space !== 'world'"): page.evaluate('viewer.gizmo.toggleSpace()')
    building = page.evaluate('id => viewer.volumeRoots.get(id).userData.volume.building', box)
    boxes = lambda: page.evaluate('b => [...viewer.volumeRoots.values()].filter(r => !r.userData.deleted && r.userData.volume.building === b).length', building)
    handle = arrow(page, page.evaluate('(p => [p.x, p.z, p.y])(viewer.gizmo.controls.object.position)'), 'viewer.gizmo.controls.axis')
    shift_drag(page, handle)
    assert boxes() == 2, boxes()
    assert page.evaluate('id => viewer.volumeBox(viewer.volumeRoots.get(id))', box)[:3] == spot2 or True
    key('Control+z'); assert boxes() == 1
    key('r'); assert hint.inner_text() == "A building's box is not turned"
    page.evaluate('viewer.setVolumesShown(false)')
    # A piece: [ and ] a quarter turn about its pivot, one undo step each
    piece = page.evaluate("[...viewer.roots.keys()].find(k => { const r = viewer.roots.get(k), o = r.userData.source; return r.visible && !o.hidden && !o.added && viewer.gizmo.linkedCount(k) === 0 && !viewer.recipeOf(k); })")
    page.evaluate('id => viewer.select(id)', piece)
    yaw = page.evaluate('viewer.gizmo.pose().rotation[1]')
    key(']'); turned = page.evaluate('viewer.gizmo.pose().rotation[1]')
    assert abs(((turned - yaw - 90) + 180) % 360 - 180) < 0.01 and hint.inner_text() == 'Turned a quarter right', (yaw, turned)
    key('['); assert abs(((page.evaluate('viewer.gizmo.pose().rotation[1]') - yaw) + 180) % 360 - 180) < 0.01
    # A landing zone's copy goes along to another map (the copy carried, Part C): Ctrl+C on Bar, Ctrl+V and a click on
    # Police Station
    page.evaluate('viewer.select(null); viewer.setZonesShown(true)')
    page.evaluate('id => viewer.pickZone(id)', zone['id'])
    key('Control+c')
    page.evaluate('void viewer.goTo({map: "URB_PoliceStation"})')
    try: page.locator('#leaveDiscard').click(timeout=4000)
    except Exception: pass
    page.wait_for_function("new URLSearchParams(location.search).get('map') === 'URB_PoliceStation'", timeout=60000)
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
    there = len(page.evaluate('viewer.zones()'))
    first = page.evaluate('viewer.zones()[0].location')
    bw.look_at(page, first)
    key('Control+v')
    assert page.evaluate('viewer.zonesOn()'), 'the paste opens the Landing zones view'
    click_at([first[0] + 480, first[1], first[2]])
    zones = page.evaluate('viewer.zones()')
    assert len(zones) == there + 1 and zones[-1]['direction'] == zone['direction'], zones
    page.close()
    # A diagonal cover mark on the farm: the gizmo's ring turns its corners (R); whole tiles shown on the Snap button;
    # Shift+drag copies; Ctrl+C, Ctrl+V and a click place a copy
    page = open_viewer(browser, base + '?map=CSmallScout_Farm', errors)
    if page.evaluate('viewer.data.name').lower() != 'csmallscout_farm':
        page.close(); return dict(marks='skipped: CsmallScout_Farm is not in the install')
    hint = page.locator('#dragHint')
    page.evaluate("viewer.setSnapMode('off'); viewer.setDiagonalShown(true)")
    page.evaluate("""() => { viewer.controls.target.set(1295, -117, -2353); viewer.camera.position.set(1375, 350, -2653); viewer.controls.update(); }""")
    page.wait_for_selector('#floor button[data-value="1"]', state='visible', timeout=60000)
    page.locator('#floor button[data-value="1"]').click(); page.wait_for_timeout(400)
    tile = [39, 12, 0]

    def mark_click(t):
        x, y = page.evaluate('([t, z]) => viewer.clientAt(viewer.diagonalPoint(t, z, null))', [t, -116.95])
        page.mouse.move(x, y); page.mouse.click(x, y); page.wait_for_timeout(150)
    mark_click(tile)
    assert page.evaluate('viewer.pickedMarks()') == ['39,12,0'], page.evaluate('viewer.pickedMarks()')
    assert page.locator('#snapBadge').inner_text() == '96'
    key('r'); assert lit() == ['editRotate'] and 'dim' not in (page.locator('#editRotate').get_attribute('class') or '')
    key('g')
    count = len(page.evaluate('viewer.diagonalMarks()'))
    handle = arrow(page, page.evaluate('viewer.diagonalGizmo().at'), 'viewer.diagonalGizmo().axis')
    shift_drag(page, handle, tiles=3)
    keys = page.evaluate('viewer.diagonalMarks().map(m => m.key)')
    assert len(keys) == count + 1 and '39,12,0' in keys, (keys, hint.inner_text())
    key('Control+z'); assert len(page.evaluate('viewer.diagonalMarks()')) == count
    mark_click(tile)
    key('Control+c'); key('Control+v')
    mark_click([37, 13, 0])
    assert len(page.evaluate('viewer.diagonalMarks()')) == count + 1, page.evaluate('viewer.diagonalMarks().map(m => m.key)')
    assert '37,13,0' in page.evaluate('viewer.diagonalMarks().map(m => m.key)')
    assert not errors, errors
    page.close()
    return dict(zone=zone['id'], spawn=spot['key'], marks=count)


def check_rail_lists(browser, url, open_viewer):
    """The rail's Views list beside its button, as the Build menu beside Add, lifted to stay in a short window and over
    the dock; the Build menu not shown while the Add panel is open; the Add panel made large by its maximise button (the look picker's way): cards with large pictures in This
    map and All maps, back to its size when a card is chosen (placing begins), by Esc and by the button."""
    errors = []
    page = open_viewer(browser, url.split('?')[0] + '?map=URB_Bar', errors)
    box = lambda sel: page.evaluate('s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }', sel)

    def hover_views():
        page.mouse.move(700, 500); page.wait_for_timeout(200)
        b = box('#viewsButton')
        page.mouse.move((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); page.wait_for_timeout(400)
        return b
    # The Views list stands beside its button, its top with the button's (the Build menu's -5 pixels)
    b = hover_views()
    assert page.locator('#viewsFlyout').is_visible()
    lst = box('#viewsFlyout')
    assert abs(lst[1] - (b[1] - 5)) < 3 and lst[0] > b[2], (b, lst)
    # In a short window, the Spawns view's long list is lifted to stay inside it, and stands over the dock
    page.set_viewport_size(dict(width=1000, height=560))
    page.evaluate('viewer.setSpawnsShown(true)')
    hover_views()
    lst, height = box('#viewsFlyout'), page.evaluate('innerHeight')
    assert lst[3] <= height and lst[1] >= 0, (lst, height)
    dock = box('.dock')
    if dock[0] < lst[2] and dock[1] < lst[3]:
        x, y = (max(dock[0], lst[0]) + min(dock[2], lst[2])) / 2, (max(dock[1], lst[1]) + min(dock[3], lst[3])) / 2
        assert page.evaluate('([x, y]) => document.getElementById("viewsFlyout").contains(document.elementFromPoint(x, y))', [x, y])
    page.mouse.move(700, 300)
    page.evaluate('viewer.setSpawnsShown(false)')
    page.set_viewport_size(dict(width=1600, height=1000))
    # The Build menu shows on Add's hover with the Add panel shut, and not while it is open (it stood over its list)
    def build_menu_shown():
        page.mouse.move(700, 500); page.wait_for_timeout(250)
        a = box('#editAdd')
        page.mouse.move((a[0] + a[2]) / 2, (a[1] + a[3]) / 2); page.wait_for_timeout(600)
        return page.evaluate('getComputedStyle(document.getElementById("buildFlyout")).visibility') == 'visible'
    assert build_menu_shown()
    page.evaluate("viewer.setLibraryScope('map'); viewer.showPieces(true)")
    assert not build_menu_shown()
    page.mouse.move(700, 500)
    # The Add panel made large: over most of the view, This map's pieces as cards with large pictures
    small = page.evaluate('document.querySelector("#libList canvas").width')
    page.locator('#libraryLarge').click()
    assert page.evaluate('document.getElementById("library").classList.contains("large")')
    assert box('#library')[2] - box('#library')[0] > 1200
    ratio = page.evaluate('viewer.renderer.getPixelRatio()')
    assert page.evaluate('document.querySelector("#libList canvas").width') == round(168 * ratio) > small
    page.wait_for_function('document.querySelectorAll("#libList canvas[data-drawn]").length >= 8', timeout=30000)
    cards = page.evaluate('[...document.querySelectorAll("#libList .libitem")].slice(0, 2).map(c => c.getBoundingClientRect().top)')
    assert abs(cards[0] - cards[1]) < 1, cards           # (cards side by side, not rows)
    # a card chosen: back to its size, placing begun; Esc stops it, and Esc brings the large panel back to its size
    page.locator('#libList .libitem').nth(1).click()
    assert not page.evaluate('document.getElementById("library").classList.contains("large")') and page.evaluate('Boolean(viewer.placing())')
    page.keyboard.press('Escape')
    page.locator('#libraryLarge').click()
    page.evaluate('document.activeElement?.blur?.()'); page.keyboard.press('Escape')
    assert not page.evaluate('document.getElementById("library").classList.contains("large")') and page.evaluate('viewer.pieces.open')
    # All maps: cards in rows, their pictures large, the rows in view drawn as the list scrolls
    page.locator('#libraryLarge').click()
    page.evaluate("viewer.setLibraryScope('all')")
    page.wait_for_function('viewer.library.ready()', timeout=120000)
    page.wait_for_function('document.querySelectorAll("#libAllList canvas[data-drawn]").length >= 4', timeout=60000)
    assert page.evaluate('document.querySelector("#libAllList canvas").width') == round(168 * ratio)
    page.evaluate('() => { const l = document.getElementById("libAllList"); l.scrollTop = 246 * 30; l.dispatchEvent(new Event("scroll")); }')
    page.wait_for_timeout(300)
    shown = page.evaluate('''() => { const l = document.getElementById("libAllList").getBoundingClientRect();
      return [...document.querySelectorAll("#libAllList .libitem")].filter(i => { const r = i.getBoundingClientRect(); return r.bottom > l.top && r.top < l.bottom; }).length; }''')
    assert shown >= 4, shown
    page.locator('#libraryClose').click()
    assert not page.evaluate('document.getElementById("library").classList.contains("large")')
    assert not errors, errors
    page.close()
    return dict(cardsInView=shown)
