"""The wall tool in the browser (custom geometry plan, stage M1; the editing plan's Build menu and plain pieces, E1 and
E2), on a test server: run through browser_smoke.py --only walls --projects (it saves a project and builds it: a server
started with --projects and --builds in scratch folders, never the main one).

On the map open (one that hasn't the Bar's wall, so the plain wall's template is read from URB_Bar: the police station,
whose ground the points below are on, opened by a --url ending ?map=URB_PoliceStation): the Build menu's tools, none of the made recipes left in the Add panel, the find box naming the tools; the
Build menu's Wall (shown on hovering Add) draws a wall by dragging along a tile line (tile edge to tile edge, along x),
its numbers and pose; it is plain (its kind's plain version on the plain material, its panel's Look row saying none
chosen), the Bar's look chosen makes it version 1 and Plain plain again, each one undo step; Add gap puts
a gap shaped as a doorway in a free tile (its threshold under it) and one shaped as a window is added beside it (the
page's own call), their words and play in the panel, no Lower, Taller or Put a door in it buttons, every gap
with all five handles; the end's handle drags the wall a tile longer at its start with the gaps left where they are in
the world; with the snap at whole tiles a gap's middle slides it a tile; Flip sides swaps the faces with the gaps in
place; undo and redo step through each change; with the snap off a gap's top moves smoothly, and Delete with its handle
last touched takes only the gap out; the top's handle makes it one storey and two again (M2); grouped with a prop,
the group can break together (M3); a second wall joined at a corner, a room, a roof with a hole, a room with a roof and
its building, a ramp (its look then chosen in the look picker, its cards ramps; no swatches) and a rock, all drawn plain; saved and reopened, the wall is as it was; a quick Build makes it from
numbers, plain, in its kind's default look brought from URB_Bar."""
import json

# the Build menu's tools (made_drawing.js BUILD_TOOLS), each kind's plain version (PLAIN_VERSION), a gap's handles
# (walls.js openingParts)
BUILD_TOOLS = ['wall', 'room', 'roomroof', 'floor', 'roof', 'patch', 'block', 'ramp', 'rock']
PLAIN = {'fracWall': 4, 'fracSlab': 3, 'ground': 3}
PARTS = ['middle', 'x0', 'x1', 'z1', 'z0']
DOT = '·'


def ground_point(page, at):
    """The point of the page (CSS pixels) where game point `at` is drawn."""
    return page.evaluate('p => viewer.screenOf(p)', at)


def wall_ids(page):
    return page.evaluate("[...viewer.roots.values()].filter(r => r.userData.source.added?.generated?.kind === 'fracWall').map(r => r.userData.source.id)")


def made_ids(page, kind, but=()):
    """The made pieces of `kind` ('fracWall', 'fracSlab', 'ground') standing now, but those in `but`."""
    return page.evaluate("""([kind, but]) => [...viewer.roots.values()].filter(r => !r.userData.deleted
      && r.userData.source.added?.generated?.kind === kind && !but.includes(r.userData.source.id)).map(r => r.userData.source.id)""",
                         [kind, list(but)])


def look_at(page, at):
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 500, c[2] + 900, c[1] + 900);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", at)
    page.wait_for_timeout(300)      # (a frame drawn from where the camera was put: screenOf reads its matrices)


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
    """The wall's record and place; the place to a thousandth, since it comes back through the piece's matrix
    (single precision: -1343.9998 for -1344)."""
    s = page.evaluate('id => viewer.wallState(id)', wall)
    if s and s.get('location'): s['location'] = [round(v, 3) + 0.0 for v in s['location']]
    return s


def build_menu(page, key):
    """The Build menu's tool `key` picked as the user does: Add hovered, the tool's button clicked; it draws at once,
    its button lit."""
    page.locator('#editAdd').hover()
    button = page.locator(f'#buildFlyout button[data-build="{key}"]')
    button.click()
    page.wait_for_function('k => viewer.buildTool() === k && viewer.wallDrawing()?.ready', arg=key, timeout=90000)
    assert 'on' in (button.get_attribute('class') or '').split(), button.get_attribute('class')


def start_build(page, key):
    """The Build menu's tool `key` started by script (as its button does); its template read."""
    page.evaluate('k => viewer.startBuild(k)', key)
    page.wait_for_function('k => viewer.buildTool() === k && viewer.wallDrawing()?.ready', arg=key, timeout=90000)


def look_row(page, kind):
    """A made piece's Look row (E2): the look's words, and whether Choose... and Plain can be used."""
    change = page.locator(f'#{kind}LookChange')
    return dict(name=page.locator(f'#{kind}LookName').text_content(), plain=page.locator(f'#{kind}LookPlain').is_enabled(),
                choose=change.is_enabled() if change.count() else None)


def check_walls(browser, url, open_viewer, type_project_name, project_url, at=(-1200.0, -2200.0, 16.0),
                start=(-1344.0, -2208.0, 16.0), end=(-960.0, -2208.0, 16.0)):
    errors = []
    page = open_viewer(browser, url, errors)
    # (the points above are on the police station's ground: on another map they mean nothing)
    assert page.evaluate('viewer.mapId') == 'URB_PoliceStation', f"open the police station (?map=URB_PoliceStation), not {page.evaluate('viewer.mapId')}"
    out = dict(map=page.evaluate('viewer.data.name'))
    # (the looks the picker lists first, whatever was chosen before)
    page.evaluate("for (const k of ['workshop.wallLook', 'workshop.slabLook', 'workshop.groundLook']) localStorage.removeItem(k)")
    # (E1) the Build menu's tools; the Add panel no longer lists the made recipes or the look entries
    assert page.evaluate('viewer.buildTools()') == BUILD_TOOLS, page.evaluate('viewer.buildTools()')
    page.keyboard.press('p')
    page.wait_for_selector('#libMap .libitem')
    kinds = page.evaluate("[...document.querySelectorAll('#libKind option')].map(o => o.value)")
    assert not {'Walls', 'Floors and roofs'} & set(kinds), kinds
    for words, gone in (('bar inside wall', ('wall-bar-inside', 'room-bar-inside')), ('look', ('looks-wall', 'looks-slab', 'looks-ground'))):
        page.locator('#libFilter').fill(words)       # (the list is drawn again in the box's input listener, which fill runs)
        assert not any(page.locator(f'#libMap .libitem[data-id="{i}"]').count() for i in gone), (words, gone)
    page.locator('#libFilter').fill('')
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('p')
    assert not page.locator('#libMap').is_visible()
    # the Build menu's Wall, from hovering Add: drawn by dragging, one wall, then it stops (Shift keeps drawing)
    look_at(page, list(at))
    build_menu(page, 'wall')
    a, b = ground_point(page, list(start)), ground_point(page, list(end))
    drag(page, a, b)
    page.wait_for_function("viewer.gizmo.active && viewer.wallState(viewer.gizmo.active)", timeout=60000)
    wall = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, wall)
    s = state(page, wall)
    assert s['generated']['wall']['x0'] == 0 and s['generated']['wall']['x1'] == 384, s
    assert s['location'][:2] == [start[0], start[1]] and s['rotation'] == [0, 0, 0], s
    assert not page.evaluate('viewer.wallDrawing()') and page.evaluate('viewer.buildTool()') is None
    out['drawn'] = dict(location=s['location'], seed=s['generated']['wall']['seed'])
    # (E2) plain: its kind's plain version with no look in its numbers, on the plain material; the panel says so
    assert s['generated']['version'] == PLAIN['fracWall'] and 'look' not in s['generated']['wall'], s
    assert page.evaluate('id => viewer.isPlain(id)', wall)
    materials = page.evaluate('id => viewer.roots.get(id).userData.source.materials', wall)
    assert 'plain:made' in materials, materials
    assert page.locator('#wallHead').text_content() == f'Wall {DOT} plain', page.locator('#wallHead').text_content()
    assert look_row(page, 'wall') == dict(name='Look: none chosen', plain=False, choose=True), look_row(page, 'wall')
    # the Bar's inside wall chosen (its kind's default look, by its id): made again where it stands at version 1, one
    # undo step; Plain makes it plain again; two undos give the drawn wall back
    page.evaluate("id => { const { plain, ...bar } = viewer.plainLook('wall'); return viewer.setMadeLook(id, 'wall', bar); }", wall)
    page.wait_for_function("old => viewer.gizmo.active && viewer.gizmo.active !== old", arg=wall, timeout=60000)
    (barred,) = made_ids(page, 'fracWall')
    g = state(page, barred)
    assert g['generated']['version'] == 1 and 'look' not in g['generated']['wall'] and g['location'] == s['location'], g
    assert g['generated']['wall'] == s['generated']['wall'], (g, s)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent === 'Look: Bar inside wall'", timeout=30000)
    assert look_row(page, 'wall') == dict(name='Look: Bar inside wall', plain=True, choose=True), look_row(page, 'wall')
    assert not page.evaluate('id => viewer.isPlain(id)', barred)
    assert 'plain:made' not in page.evaluate('id => viewer.roots.get(id).userData.source.materials', barred)
    page.locator('#wallLookPlain').click()
    page.wait_for_function("old => viewer.gizmo.active && viewer.gizmo.active !== old", arg=barred, timeout=60000)
    (plain,) = made_ids(page, 'fracWall')
    assert state(page, plain)['generated'] == s['generated'], (state(page, plain), s)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent === 'Look: none chosen'", timeout=30000)
    page.evaluate('viewer.gizmo.undo()'); page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('id => viewer.roots.get(id) && !viewer.roots.get(id).userData.deleted', arg=wall, timeout=30000)
    assert made_ids(page, 'fracWall') == [wall] and state(page, wall) == s, (made_ids(page, 'fracWall'), state(page, wall), s)
    page.evaluate('id => viewer.select(id)', wall)
    out['looks'] = dict(chosen=g['generated']['version'], plain=s['generated']['version'])
    # gaps: Add gap's, shaped as a doorway (its threshold, 8, left under it), and one shaped as a window (the page's
    # own call: the panel has the one button since 19 November 2026); no Lower or Taller (the top handle does it)
    page.wait_for_selector('#wallBox:not([hidden]) #wallGap')
    assert page.locator('#wallStoreys, #wallShorter, #wallDoor, #wallWindow').count() == 0
    page.locator('#wallGap').click(); page.evaluate("viewer.addWallOpening('window')")
    page.wait_for_function("id => viewer.wallState(id).generated.wall.openings.length === 2", arg=wall)
    openings = state(page, wall)['generated']['wall']['openings']
    # (the middle tiles tie: the lower one first)
    assert openings == [dict(x0=96, x1=192, z0=8, z1=160), dict(x0=192, x1=288, z0=72, z1=168)], openings
    text = page.evaluate('viewer.wallPanelText()')
    assert 'Gap, 1 tile wide, from 72 over the floor to 168' in text and 'Gap, 1 tile wide, from 8 over the floor to 160' in text, text
    # (how each plays: walked through with no cover, so it wants a door; the window's wall gives low cover)
    assert 'A unit in a gap with no door has cover toward its sides: put a door in it' in text, text
    assert 'the wall under it gives low cover' in text, text
    assert page.locator('#wallBox .walldoorput').count() == 0      # (no Put a door in it: a door from the Add panel)
    mesh_ready(page, wall)
    # every gap has all five handles; the start's handle a tile out: a tile longer, the gaps where they were in the world
    h = page.evaluate('viewer.wallHandles()')
    assert {'end:x0', 'end:x1'} | {f'open:{i}:{p}' for i in (0, 1) for p in PARTS} <= set(h), sorted(h)
    drag(page, h['end:x0'][:2], h['end:x0'][2:])
    s = state(page, wall)
    assert s['generated']['wall']['x1'] == 480 and s['location'][0] == start[0] - 96, s
    assert [o['x0'] for o in s['generated']['wall']['openings']] == [192, 288], s
    mesh_ready(page, wall)
    # the window's middle a tile on, to the wall's end, with the snap at whole tiles (a gap's handles follow the snap)
    page.evaluate("viewer.setSnapMode('tile')")
    h = page.evaluate('viewer.wallHandles()')
    drag(page, h['open:1:middle'][:2], h['open:1:middle'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    assert [o['x0'] for o in state(page, wall)['generated']['wall']['openings']] == [192, 384], state(page, wall)
    assert 'Gap, 1 tile wide, from 72 over the floor to 168, at its end' in page.evaluate('viewer.wallPanelText()'), page.evaluate('viewer.wallPanelText()')
    # flip: the faces swap, the gaps stay in the world
    before_flip = state(page, wall)
    page.locator('#wallFlip').click()
    f = state(page, wall)
    assert f['rotation'][1] == 32768 and f['location'][0] == before_flip['location'][0] + 480, f
    assert [(o['x0'], o['z0']) for o in f['generated']['wall']['openings']] == [(0, 72), (192, 8)], f
    # undo and redo step through: flip, the slide, the end, the window, the doorway
    for expected in (before_flip, None):
        page.evaluate('viewer.gizmo.undo()')
        if expected: assert state(page, wall) == expected, (state(page, wall), expected)
    page.evaluate('viewer.gizmo.redo()'); page.evaluate('viewer.gizmo.redo()')
    assert state(page, wall) == f, (state(page, wall), f)
    # with the snap off a gap's top moves smoothly (steps of 1, not 8): the doorway's top dragged up about 20; Delete
    # with its handle last touched takes the gap out, not the wall
    mesh_ready(page, wall)
    h = page.evaluate('viewer.wallHandles(20)')
    drag(page, h['open:1:z1'][:2], h['open:1:z1'][2:], steps=4)
    raised = state(page, wall)['generated']['wall']['openings'][1]
    assert 177 <= raised['z1'] <= 183 and raised['z0'] == 8, raised
    out['smooth'] = raised['z1']
    page.keyboard.press('Delete')
    s = state(page, wall)
    assert s and len(s['generated']['wall']['openings']) == 1, s
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function("id => viewer.wallState(id)?.generated.wall.openings.length === 2", arg=wall)
    kept = state(page, wall)
    # (M2) the top's handle down past half a storey: one storey, its gaps under its top; up again, two; undo steps
    # back through both
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
    h = page.evaluate('viewer.wallHandles(150)')
    drag(page, h['end:top'][:2], h['end:top'][2:])
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
    start_build(page, 'wall')
    look_at(page, corner)
    drag(page, ground_point(page, corner), ground_point(page, [corner[0], corner[1] - 384, corner[2]]))
    page.wait_for_function('n => viewer.roots.size > n && viewer.gizmo.active', arg=len(before_ids), timeout=60000)
    second = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, second)
    s2 = state(page, second)
    assert s2['location'][:2] == corner[:2] and s2['rotation'][1] % 65536 == 49152, (s2, kept)
    assert s2['generated']['version'] == PLAIN['fracWall'], s2
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
    # (M3 item 6) a room: a rectangle dragged south of the wall gives four plain walls in one step, their corners joined
    # (the longer sides running through), one gap shaped as a doorway, in the side nearest the camera
    before_ids = set(page.evaluate('[...viewer.roots.keys()]'))
    start_build(page, 'room')
    assert page.evaluate('viewer.wallDrawing().room')
    # (south of the wall's own span, on the open ground the wall was drawn on)
    west = min(corner[0], kept['location'][0])
    a, b = [west + 96, corner[1] - 96, corner[2]], [west + 384, corner[1] - 288, corner[2]]
    # (seen from straight above, so no wall or building beside it hides any of it)
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 1, c[2] + 1400, c[1] + 1);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, corner[2]])
    page.wait_for_timeout(300)      # (a frame drawn from where the camera was put: screenOf reads its matrices)
    drag(page, ground_point(page, a), ground_point(page, b))
    page.wait_for_function('n => viewer.roots.size === n + 4', arg=len(before_ids), timeout=60000)
    room = page.evaluate("""before => [...viewer.roots.values()].filter(r => !before.includes(r.userData.source.id))
      .map(r => r.userData.source.id)""", list(before_ids))
    for r in room:
        mesh_ready(page, r)
    states = [state(page, r) for r in room]
    assert sorted(s['generated']['wall']['x1'] for s in states) == [192, 192, 288, 288], states
    assert all(s['generated']['version'] == PLAIN['fracWall'] for s in states), states
    gaps = [o for s in states for o in s['generated']['wall']['openings']]
    assert len(gaps) == 1 and (gaps[0]['z0'], gaps[0]['z1']) == (8, 160), states
    page.wait_for_function("ids => ids.filter(id => (" + mesh_of + ")(id).includes('\"ends\":[\"through\",\"through\"]')).length === 2",
                           arg=room, timeout=30000)
    out['room'] = dict(walls=len(room), door=[s['location'] for s in states if s['generated']['wall']['openings']][0])
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    if page.evaluate('viewer.wallDrawing()'):
        page.keyboard.press('Escape')
    page.evaluate('id => viewer.select(id)', wall)
    # (M5) a roof from the Build menu, dragged out over the same ground (no made walls round it: two storeys up), plain;
    # its edge's handle a tile out, a hole from the panel, each one undo step; a room with a roof: four walls, the roof
    # on their tops (plain with them) and a building round them, two undo steps
    before_ids = set(page.evaluate('[...viewer.roots.keys()]'))
    start_build(page, 'roof')
    assert page.evaluate('viewer.wallDrawing().slab')
    drag(page, ground_point(page, a), ground_point(page, b))
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=len(before_ids), timeout=60000)
    slab = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, slab)
    s = state(page, slab)
    assert s['generated']['kind'] == 'fracSlab' and s['generated']['slab']['x1'] == 288 and s['generated']['slab']['y1'] == 192, s
    assert abs(s['location'][2] - (corner[2] + 384)) < 1e-3 and s['rotation'] == [0, 0, 0], s
    assert s['generated']['version'] == PLAIN['fracSlab'] and page.evaluate('id => viewer.isPlain(id)', slab), s
    assert page.locator('#slabHead').text_content() == f'Roof {DOT} plain', page.locator('#slabHead').text_content()
    assert look_row(page, 'slab') == dict(name='Look: none chosen', plain=False, choose=True), look_row(page, 'slab')
    h = page.evaluate('viewer.wallHandles()')
    assert {'side:x0', 'side:x1', 'side:y0', 'side:y1'} <= set(h), sorted(h)
    drag(page, h['side:x1'][:2], h['side:x1'][2:])
    assert state(page, slab)['generated']['slab']['x1'] == 384, state(page, slab)
    page.locator('#slabHole').click()
    page.wait_for_function("id => viewer.wallState(id).generated.slab.holes.length === 1", arg=slab)
    assert 'Hole, 1 by 1 tile' in page.evaluate('viewer.slabPanelText()'), page.evaluate('viewer.slabPanelText()')
    mesh_ready(page, slab)
    page.evaluate('viewer.gizmo.undo()'); page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function("id => viewer.wallState(id)?.generated.slab.x1 === 288 && !viewer.wallState(id).generated.slab.holes.length", arg=slab)
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    out['slab'] = dict(location=s['location'], tiles=[3, 2])
    start_build(page, 'roomroof')
    assert page.evaluate('viewer.wallDrawing().roof')
    named = [b['name'] for b in page.evaluate('viewer.buildingsNow()')]
    houses = len(named)
    drag(page, ground_point(page, a), ground_point(page, b))
    page.wait_for_function('n => viewer.roots.size === n + 5', arg=len(before_ids), timeout=60000)
    page.wait_for_function('n => viewer.buildingsNow().length === n + 1', arg=houses, timeout=30000)
    made = page.evaluate("""before => [...viewer.roots.values()].filter(r => !before.includes(r.userData.source.id))
      .map(r => r.userData.source.id)""", list(before_ids))
    roof = [m for m in made if state(page, m)['generated']['kind'] == 'fracSlab']
    assert len(roof) == 1 and abs(state(page, roof[0])['location'][2] - (corner[2] + 384)) < 1e-3, [state(page, m) for m in made]
    assert all(state(page, m)['generated']['version'] == PLAIN[state(page, m)['generated']['kind']] for m in made), [state(page, m) for m in made]
    (house,) = [b for b in page.evaluate('viewer.buildingsNow()') if b['name'] not in named]
    assert len(house['floors']) == 3 and house['name'].startswith('Building'), house
    # (a floor a storey, breaking at the storeys' heights, and one for the roof: the game lists a slab in the floor it
    # is the bottom of; EXP-76 run E)
    tops = sorted(round(max(bx[5] for bx in f) - corner[2], 3) for f in house['floors'])
    assert tops == [192, 384, 576], (tops, house)
    page.evaluate('viewer.gizmo.undo()')          # (one undo step: the pieces and the building)
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    page.wait_for_function('n => viewer.buildingsNow().length === n', arg=houses, timeout=30000)
    if page.evaluate('viewer.wallDrawing()'):
        page.keyboard.press('Escape')
    # (M6) ground: a ramp from the Build menu dragged east rises east (its frame's x the world's), plain, no swatch on;
    # its top handle raises it in steps of 8 and the panel says its slope; Turn makes it rise the next way round on the
    # same tiles; a swatch gives it that look (version 1); each one undo step
    start_build(page, 'ramp')
    assert page.evaluate('viewer.wallDrawing().ground') == 'ramp'
    ga, gb = [a[0], a[1], a[2]], [b[0], a[1] - 96, a[2]]
    drag(page, ground_point(page, ga), ground_point(page, gb))
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=len(before_ids), timeout=60000)
    ramp = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, ramp)
    s = state(page, ramp)
    assert s['generated']['kind'] == 'ground' and s['generated']['ground']['shape'] == 'ramp', s
    assert s['rotation'] == [0, 0, 0] and s['generated']['ground']['x1'] == 288 and s['generated']['ground']['height'] == 96, s
    assert s['generated']['version'] == PLAIN['ground'] and 'look' not in s['generated']['ground'], s
    assert 'no cover' in page.evaluate('viewer.groundPanelText()'), page.evaluate('viewer.groundPanelText()')
    assert look_row(page, 'ground') == dict(name='Look: none chosen', plain=False, choose=True), look_row(page, 'ground')
    assert page.locator('#groundSwatches').count() == 0      # (no swatches: its Choose... opens the look picker)
    h = page.evaluate('viewer.wallHandles(40)')
    assert {'side:x0', 'side:x1', 'side:y0', 'side:y1', 'end:top'} <= set(h), sorted(h)
    drag(page, h['end:top'][:2], h['end:top'][2:])
    raised = state(page, ramp)['generated']['ground']['height']
    assert raised > 96 and raised % 8 == 0, raised
    page.locator('#groundTurn').click()
    t = state(page, ramp)
    assert t['rotation'][1] == 16384 and t['generated']['ground']['x1'] == 96, t
    page.locator('#groundLookChange').click()
    page.wait_for_function("s => viewer.lookMode() === 'ground' && document.querySelectorAll(s).length > 1", arg='.lookpicker .lookcard', timeout=60000)
    assert page.evaluate('viewer.lookPickerState().sample') == 'ramp'
    card = page.locator('.lookpicker .lookcard').nth(1)
    swatch_name = card.locator('strong').text_content()
    card.click()
    page.wait_for_function("old => viewer.gizmo.active && viewer.gizmo.active !== old", arg=ramp, timeout=60000)
    (painted,) = made_ids(page, 'ground')
    p = state(page, painted)
    assert p['generated']['version'] == 2 and isinstance(p['generated']['ground'].get('look'), dict), p
    assert {k: v for k, v in p['generated']['ground'].items() if k != 'look'} == t['generated']['ground'] and p['location'] == t['location'], (p, t)
    page.wait_for_function("n => document.getElementById('groundLookName').textContent === 'Look: ' + n", arg=swatch_name, timeout=30000)
    assert look_row(page, 'ground')['plain'], look_row(page, 'ground')
    for _ in range(4):
        page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    out['ground'] = dict(raised=raised, turned=t['location'], look=p['generated']['ground']['look'])
    if page.evaluate('viewer.wallDrawing()'):
        page.keyboard.press('Escape')
    # (M6 item 6) a rock: drawn plain with a seed, its mesh the server's, standing level whatever its look's donor;
    # Another rock gives the next seed in one undo step
    start_build(page, 'rock')
    assert page.evaluate('viewer.wallDrawing().ground') == 'rock'
    drag(page, ground_point(page, ga), ground_point(page, [a[0] + 192, a[1] - 96, a[2]]))
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=len(before_ids), timeout=60000)
    rock = page.evaluate('viewer.gizmo.active')
    mesh_ready(page, rock)
    k = state(page, rock)
    g = k['generated']['ground']
    assert g['shape'] == 'rock' and isinstance(g['seed'], int) and k['rotation'] == [0, 0, 0], k
    assert k['generated']['version'] == PLAIN['ground'], k
    assert 'stands in the way' in page.evaluate('viewer.groundPanelText()'), page.evaluate('viewer.groundPanelText()')
    assert page.locator('#groundAnother').is_visible() and not page.locator('#groundTurn').is_visible()
    page.locator('#groundAnother').click()
    k2 = state(page, rock)
    assert k2['generated']['ground']['seed'] == (g['seed'] + 1) % 2 ** 31, k2
    mesh_ready(page, rock)
    for _ in range(2):
        page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before_ids), timeout=30000)
    out['rock'] = dict(seed=g['seed'])
    if page.evaluate('viewer.wallDrawing()'):
        page.keyboard.press('Escape')
    page.evaluate('id => viewer.select(id)', wall)
    # saved and reopened: the wall as it was, plain
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
    assert again == kept and page.evaluate('id => viewer.isPlain(id)', ids[0]), (again, kept)
    # a quick Build: the plain wall made from numbers in its kind's default look, on URB_Bar's materials
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
