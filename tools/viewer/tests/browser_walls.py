"""The wall tool in the browser (custom geometry plan, stage M1), on a test server: run through browser_smoke.py
--only walls --projects (it saves a project and builds it: a server started with --projects and --builds in scratch
folders, never the main one).

On the map open (one that hasn't the Bar's wall, so the donor is read from URB_Bar: the police station by default):
the Walls kind's entry, a wall drawn by dragging along a tile line (tile edge to tile edge, along x), its numbers
and pose; Add doorway and Add window put each in a free tile and their words in the panel; the end's handle drags the
wall a tile longer at its start with the openings left where they are in the world; an opening's middle slides it;
Flip sides swaps the faces with the openings in place; undo and redo step through each change; Delete with an
opening's handle last touched takes only the opening out; the top's handle makes it one storey and the panel's button
two again (M2); grouped with a prop, the group can break together, and Put a door in it puts the map's door in the doorway (M3); saved and reopened, the wall is as it was; a quick Build
makes it from numbers, with the donor brought from URB_Bar and the doorway's warning."""
import json


def ground_point(page, at):
    """The point of the page (CSS pixels) where game point `at` is drawn."""
    return page.evaluate('p => viewer.screenOf(p)', at)


def wall_ids(page):
    return page.evaluate("[...viewer.roots.values()].filter(r => r.userData.source.added?.generated?.kind === 'fracWall').map(r => r.userData.source.id)")


def look_at(page, at):
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 500, c[2] + 900, c[1] + 900);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", at)
    page.wait_for_timeout(300)


def drag(page, a, b, steps=12, alt=False):
    page.mouse.move(*a)
    if alt: page.keyboard.down('Alt')
    page.mouse.down()
    page.mouse.move(*b, steps=steps)
    page.mouse.up()
    if alt: page.keyboard.up('Alt')


def mesh_ready(page, wall):
    page.wait_for_function('id => viewer.wallMeshReady(id)', arg=wall, timeout=30000)


def state(page, wall):
    return page.evaluate('id => viewer.wallState(id)', wall)


def check_walls(browser, url, open_viewer, type_project_name, project_url, at=(-1200.0, -2200.0, 16.0),
                start=(-1344.0, -2208.0, 16.0), end=(-960.0, -2208.0, 16.0)):
    errors = []
    page = open_viewer(browser, url, errors)
    out = dict(map=page.evaluate('viewer.data.name'))
    entries = page.evaluate('viewer.wallEntries().map(e => ({ name: e.name, kind: e.kind, look: e.wallLook.id }))')
    assert entries == [dict(name='Bar inside wall', kind='Walls', look='bar-inside'),
                       dict(name='Room of bar inside walls', kind='Walls', look='bar-inside')], entries
    # the Add panel lists it under its kind (pieces.js pieceRow): a row with the wall's icon
    page.keyboard.press('p')
    page.wait_for_selector('#libMap .libitem')
    page.locator('#libFilter').fill('bar inside wall')
    row = page.locator('#libMap .libitem[data-id="wall-bar-inside"]')
    assert row.count() == 1 and 'Walls' in row.inner_text(), row.count()
    assert page.locator('#libMap .libitem[data-id="room-bar-inside"]').count() == 1      # and its room (M3 item 6)
    row.click()
    page.wait_for_function('viewer.wallDrawing()?.ready', timeout=90000)
    page.keyboard.press('p') if page.locator('#libMap').is_visible() else None
    look_at(page, list(at))
    # (the panel closed with p stops the drawing: start it again where the view is free)
    if not page.evaluate('viewer.wallDrawing()'):
        page.evaluate('viewer.startWallDrawing(viewer.wallEntries()[0].wallLook)')
        page.wait_for_function('viewer.wallDrawing()?.ready', timeout=90000)
    a, b = ground_point(page, list(start)), ground_point(page, list(end))
    drag(page, a, b)
    page.wait_for_function("viewer.gizmo.active && viewer.wallState(viewer.gizmo.active)", timeout=60000)
    wall = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, wall)
    s = state(page, wall)
    assert s['generated']['wall']['x0'] == 0 and s['generated']['wall']['x1'] == 384, s
    assert s['location'][:2] == [start[0], start[1]] and s['rotation'] == [0, 0, 0], s
    assert not page.evaluate('viewer.wallDrawing()')          # one wall, then it stops (Shift keeps drawing)
    out['drawn'] = dict(location=s['location'], seed=s['generated']['wall']['seed'])
    # openings from the panel
    page.locator('#wallDoor').click(); page.locator('#wallWindow').click()
    page.wait_for_function("id => viewer.wallState(id).generated.wall.openings.length === 2", arg=wall)
    openings = state(page, wall)['generated']['wall']['openings']
    # (the middle tiles tie: the lower one first)
    assert openings == [dict(x0=96, x1=192, z0=-16, z1=160), dict(x0=192, x1=288, z0=72, z1=168)], openings
    text = page.evaluate('viewer.wallPanelText()')
    assert 'Window, 1 tile wide, 96 tall, its sill 72 over the floor' in text and 'Doorway, 1 tile wide, 160 tall' in text, text
    assert 'put a door in it' in text and 'the wall under it gives low cover' in text, text
    mesh_ready(page, wall)
    # the start's handle a tile out: a tile longer, the openings where they were in the world
    h = page.evaluate('viewer.wallHandles()')
    assert {'end:x0', 'end:x1', 'open:0:middle', 'open:1:z0', 'open:1:z1'} <= set(h), sorted(h)
    assert 'open:0:z0' not in h                               # a doorway has no sill
    drag(page, h['end:x0'][:2], h['end:x0'][2:])
    s = state(page, wall)
    assert s['generated']['wall']['x1'] == 480 and s['location'][0] == start[0] - 96, s
    assert [o['x0'] for o in s['generated']['wall']['openings']] == [192, 288], s
    mesh_ready(page, wall)
    # the window's middle a tile on, to the wall's end
    h = page.evaluate('viewer.wallHandles()')
    drag(page, h['open:1:middle'][:2], h['open:1:middle'][2:])
    assert [o['x0'] for o in state(page, wall)['generated']['wall']['openings']] == [192, 384], state(page, wall)
    # flip: the faces swap, the openings stay in the world
    before_flip = state(page, wall)
    page.locator('#wallFlip').click()
    f = state(page, wall)
    assert f['rotation'][1] == 32768 and f['location'][0] == before_flip['location'][0] + 480, f
    assert [(o['x0'], o['z0']) for o in f['generated']['wall']['openings']] == [(0, 72), (192, -16)], f
    # undo and redo step through: flip, the slide, the end, the window, the doorway
    for expected in (before_flip, None):
        page.evaluate('viewer.gizmo.undo()')
        if expected: assert state(page, wall) == expected, (state(page, wall), expected)
    page.evaluate('viewer.gizmo.redo()'); page.evaluate('viewer.gizmo.redo()')
    assert state(page, wall) == f, (state(page, wall), f)
    # Delete with an opening's handle last touched takes the opening out, not the wall
    mesh_ready(page, wall)
    h = page.evaluate('viewer.wallHandles()')
    drag(page, h['open:1:z1'][:2], h['open:1:z1'][2:], steps=2)      # the doorway's top up 96
    page.keyboard.press('Delete')
    s = state(page, wall)
    assert s and len(s['generated']['wall']['openings']) == 1, s
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function("id => viewer.wallState(id)?.generated.wall.openings.length === 2", arg=wall)
    kept = state(page, wall)
    # (M2) the top's handle down past half a storey: one storey, its openings under its top; the panel's button back to
    # two; undo steps back through both
    mesh_ready(page, wall)
    h = page.evaluate('viewer.wallHandles(-150)')
    assert 'end:top' in h, sorted(h)
    drag(page, h['end:top'][:2], h['end:top'][2:])
    low = state(page, wall)['generated']['wall']
    assert low.get('storeys') == 1 and max(o['z1'] for o in low['openings']) <= 168, low
    assert 'one storey (208 tall)' in page.evaluate('viewer.wallPanelText()'), page.evaluate('viewer.wallPanelText()')
    mesh_ready(page, wall)
    # the mesh drawn is the one-storey one (its key and request carry the storeys)
    mesh = page.evaluate("id => [...viewer.roots.values()].find(r => r.userData.source.id === id).userData.source.mesh", wall)
    assert '"storeys":1' in mesh, mesh
    out['oneStorey'] = low
    page.locator('#wallStoreys').click()
    assert 'storeys' not in state(page, wall)['generated']['wall'], state(page, wall)
    page.evaluate('viewer.gizmo.undo()'); page.evaluate('viewer.gizmo.undo()')
    assert state(page, wall) == kept, (state(page, wall), kept)
    # (M3) grouped with a prop of the map, the group can break together: its props go with the part of the wall they
    # stand by; ungrouped again
    prop = page.evaluate("""() => [...viewer.roots.values()].find(r => r.visible && !r.userData.deleted
      && r.userData.source.actorClass === 'XComDestructibleActor' && !r.userData.source.added)?.userData.source.id""")
    assert prop, 'no prop on the map'
    page.evaluate('ids => viewer.gizmo.setSelection(ids)', [wall, prop])
    page.keyboard.press('Control+g')
    page.wait_for_selector('#groupBreakRow:not([hidden])')
    assert page.locator('#groupBreak').is_enabled()
    page.locator('#groupBreak').check()
    note = page.locator('#groupNote').inner_text()
    assert 'go when the part of its made wall they stand by breaks' in note, note
    page.evaluate('viewer.gizmo.undo()'); page.evaluate('viewer.gizmo.undo()')
    page.evaluate('id => viewer.select(id)', wall)
    assert state(page, wall) == kept, (state(page, wall), kept)
    # (M3) Put a door in it: the station's own door (DoorSwingSingle, one tile) placed in the doorway, turned with the
    # wall and grouped with it; the panel then sees a door there; two undos take it out
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#wallBox:not([hidden]) .walldoorput')
    page.locator('#wallBox .walldoorput').first.click()
    page.wait_for_selector('#wallBox .walldoors button', timeout=60000)
    choices = page.locator('#wallBox .walldoors button').all_inner_texts()
    assert any('this map' in c for c in choices), choices
    before_ids = set(page.evaluate('[...viewer.roots.keys()]'))
    page.locator('#wallBox .walldoors button', has_text='this map').first.click()
    page.wait_for_function('n => viewer.roots.size > n', arg=len(before_ids), timeout=60000)
    page.wait_for_timeout(500)
    door = page.evaluate("""before => [...viewer.roots.values()].filter(r => !before.includes(r.userData.source.id)
      && r.userData.source.actorClass === 'XComInteractiveLevelActor').map(r => ({ id: r.userData.source.id, location: r.userData.source.location }))""",
                         list(before_ids))
    assert len(door) == 1, door
    page.evaluate('id => viewer.select(id)', wall)
    text = page.evaluate('viewer.wallPanelText()')
    assert 'put a door in it' not in text.lower() or 'Put a door in it' not in text, text
    assert 'A unit in a doorway with no door' not in text, text
    out['door'] = door[0]['location']
    page.evaluate('viewer.gizmo.undo()'); page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    page.evaluate('id => viewer.select(id)', wall)
    assert state(page, wall) == kept, (state(page, wall), kept)
    # (M3 item 2) a second wall drawn from the first one's far end, a quarter turn round (south, clear of the station):
    # an L. The longer runs through
    # (the first, along x, when as long), drawn with that end; the other butts; the panel says so. An undo takes the
    # second out and the first is free again.
    turn = round(kept['rotation'][1] / 16384) % 4
    step = [(1, 0), (0, 1), (-1, 0), (0, -1)][turn]
    corner = [kept['location'][0] + step[0] * kept['generated']['wall']['x1'],
              kept['location'][1] + step[1] * kept['generated']['wall']['x1'], kept['location'][2]]
    before_ids = set(page.evaluate('[...viewer.roots.keys()]'))
    page.evaluate('viewer.startWallDrawing(viewer.wallEntries()[0].wallLook)')
    page.wait_for_function('viewer.wallDrawing()?.ready', timeout=90000)
    look_at(page, corner)
    drag(page, ground_point(page, corner), ground_point(page, [corner[0], corner[1] - 384, corner[2]]))
    page.wait_for_function('n => viewer.roots.size > n && viewer.gizmo.active', arg=len(before_ids), timeout=60000)
    second = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, second)
    s2 = state(page, second)
    assert s2['location'][:2] == corner[:2] and s2['rotation'][1] % 65536 == 49152, (s2, kept)
    first_through = kept['generated']['wall']['x1'] >= s2['generated']['wall']['x1']
    mesh_of = "id => [...viewer.roots.values()].find(r => r.userData.source.id === id).userData.source.mesh"
    want = (wall, '"ends":["free","through"]') if first_through else (second, '"ends":["through","free"]')
    page.wait_for_function('([id, key]) => (' + mesh_of + ')(id).includes(key)', arg=list(want), timeout=30000)
    other = second if first_through else wall
    assert '"ends"' not in page.evaluate(mesh_of, other), page.evaluate(mesh_of, other)
    mesh_ready(page, want[0])
    page.evaluate('id => viewer.select(id)', want[0])
    text = page.evaluate('viewer.wallPanelText()')
    assert 'Joined: ' in text and 'runs through at a corner' in text, text
    page.evaluate('id => viewer.select(id)', other)
    assert 'butts on another wall at a corner' in page.evaluate('viewer.wallPanelText()')
    out['joined'] = dict(through='first' if first_through else 'second')
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    page.wait_for_function('id => !(' + mesh_of + ')(id).includes(\'"ends"\')', arg=wall, timeout=30000)
    page.evaluate('id => viewer.select(id)', wall)
    assert state(page, wall) == kept, (state(page, wall), kept)
    # (M3 item 6) a room: a rectangle dragged south of the wall gives four walls in one step, their corners joined (the
    # longer sides running through), one doorway, in the side nearest the camera
    before_ids = set(page.evaluate('[...viewer.roots.keys()]'))
    page.evaluate("viewer.startWallDrawing(viewer.wallEntries()[0].wallLook, { room: true })")
    page.wait_for_function('viewer.wallDrawing()?.ready && viewer.wallDrawing().room', timeout=90000)
    # (south of the wall's own span, on the open ground the wall was drawn on)
    west = min(corner[0], kept['location'][0])
    a, b = [west + 96, corner[1] - 96, corner[2]], [west + 384, corner[1] - 288, corner[2]]
    # (seen from straight above, so no wall or building beside it hides any of it)
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 1, c[2] + 1400, c[1] + 1);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, corner[2]])
    page.wait_for_timeout(300)
    drag(page, ground_point(page, a), ground_point(page, b))
    page.wait_for_function('n => viewer.roots.size === n + 4', arg=len(before_ids), timeout=60000)
    room = page.evaluate("""before => [...viewer.roots.values()].filter(r => !before.includes(r.userData.source.id))
      .map(r => r.userData.source.id)""", list(before_ids))
    for r in room:
        mesh_ready(page, r)
    states = [state(page, r) for r in room]
    assert sorted(s['generated']['wall']['x1'] for s in states) == [192, 192, 288, 288], states
    assert sum(len(s['generated']['wall']['openings']) for s in states) == 1, states
    page.wait_for_function("ids => ids.filter(id => (" + mesh_of + ")(id).includes('\"ends\":[\"through\",\"through\"]')).length === 2",
                           arg=room, timeout=30000)
    out['room'] = dict(walls=len(room), door=[s['location'] for s in states if s['generated']['wall']['openings']][0])
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    if page.evaluate('viewer.wallDrawing()'):
        page.keyboard.press('Escape')
    page.evaluate('id => viewer.select(id)', wall)
    # saved and reopened
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    name = 'Walls smoke %d' % page.evaluate('Date.now() % 100000')
    type_project_name(page, name)
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    page.goto(project_url(page, project))
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    ids = wall_ids(page)
    assert len(ids) == 1, ids
    again = state(page, ids[0])
    assert again == kept, (again, kept)
    # a quick Build: made from numbers on URB_Bar's materials, its doorway warned of
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    if page.locator('#buildBake').is_checked(): page.locator('#buildBake').click()
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=600000)
    assert page.locator('#buildTitle').inner_text().startswith('Built ' + name), page.locator('#buildModal').inner_text()
    steps = page.locator('#buildSteps').inner_text()
    assert '1 piece from URB_Bar' in steps, steps
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built', build
    out['build'] = build['output']
    page.locator('#buildClose').click()
    errors = [e for e in errors if 'favicon' not in e]
    assert not errors, errors
    page.close()
    return out


if __name__ == '__main__':
    print(json.dumps(dict(note='run through browser_smoke.py --only walls --projects')))
