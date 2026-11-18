"""The wall tool in the browser (custom geometry plan, stage M1), on a test server: run through browser_smoke.py
--only walls --projects (it saves a project and builds it: a server started with --projects and --builds in scratch
folders, never the main one).

On the map open (one that hasn't the Bar's wall, so the donor is read from URB_Bar: the police station by default):
the Walls kind's entry, a wall drawn by dragging along a tile line (tile edge to tile edge, along x), its numbers
and pose; Add doorway and Add window put each in a free tile and their words in the panel; the end's handle drags the
wall a tile longer at its start with the openings left where they are in the world; an opening's middle slides it;
Flip sides swaps the faces with the openings in place; undo and redo step through each change; Delete with an
opening's handle last touched takes only the opening out; the top's handle makes it one storey and the panel's button
two again (M2); saved and reopened, the wall is as it was; a quick Build
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
    assert entries == [dict(name='Bar inside wall', kind='Walls', look='bar-inside')], entries
    # the Add panel lists it under its kind (pieces.js pieceRow): a row with the wall's icon
    page.keyboard.press('p')
    page.wait_for_selector('#libMap .libitem')
    page.locator('#libFilter').fill('bar inside wall')
    row = page.locator('#libMap .libitem', has_text='Bar inside wall')
    assert row.count() == 1 and 'Walls' in row.inner_text(), row.count()
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
