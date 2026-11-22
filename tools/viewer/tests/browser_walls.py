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
numbers, plain, in its kind's default look brought from URB_Bar.

The made pieces' other paths (the refactor's follow-ups, item 4.6), each a check of its own on a page of its own:
- made-break (any map with a fracturing piece; the made pieces are made of it, of one the game keeps whole if the map
  has one): Break (B and a click) on a made wall, a made floor and a made roof sets off one blast where clicked, one
  undo step; Breaks further in battle, shown on a broken piece the game keeps whole, ticked, one undo step; Repair
  mends it, one undo step.
- made-openings (any such map): with the second of a wall's two gaps last touched (its row pointed at), Delete takes
  that gap out and leaves the wall; with the first one's handle clicked, Delete takes that one; a floor's hole the same
  way; each one undo step. A free-form floor off the tile lines: its Floor section and the tile grid say on which
  tiles it is floor and that those it covers in part are not, as the Build's rule has it (F-147).
- rock-corner (any such map): a rock's corner point clicked takes the point gizmo; its arrow dragged moves the corner
  along it (the snap off: by what was dragged), one undo step; Escape lets it go.
- room-buttons (the police station, its ground): a room drawn from the Build menu and picked whole: Lower and Taller
  step all its walls a storey, the walls' Choose... gives them a look from the picker and Plain takes it back; a room
  with a roof has no Lower or Taller, and its roof's Choose... and Plain do the same; each one undo step. Its walls
  given the look of one of the map's walls, with the walls' catalogue then forgotten and its read refused, the Room
  section names the look by the donor's mesh, as a wall's own Wall section does once the room is ungrouped.
- free-handles and texture-mapping (the police station): the made pieces' handles of the custom geometry improvements
  plan's designs A and B (check_free_handles and check_texture_mapping say what each walks through)."""
import json
import math

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


# (the checks below draw under tile snap, as they were written: whole tiles and quarter turns; since 21 November 2026 a
# drawing follows the snap setting, smooth with snap off. build_menu and start_build put tile snap on, and the drag
# that draws puts snap off again once it lets go)
DRAWING = {'snap_back': False}


def drag(page, a, b, steps=12, alt=False):
    page.mouse.move(*a)
    if alt: page.keyboard.down('Alt')
    page.mouse.down()
    page.mouse.move(*b, steps=steps)
    page.mouse.up()
    if alt: page.keyboard.up('Alt')
    if DRAWING['snap_back']:
        DRAWING['snap_back'] = False
        page.evaluate("viewer.setSnapMode('off')")


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
    page.evaluate("viewer.setSnapMode('tile')"); DRAWING['snap_back'] = True
    page.locator('#editAdd').hover()
    button = page.locator(f'#buildFlyout button[data-build="{key}"]')
    button.click()
    page.wait_for_function('k => viewer.buildTool() === k && viewer.wallDrawing()?.ready', arg=key, timeout=90000)
    assert 'on' in (button.get_attribute('class') or '').split(), button.get_attribute('class')


def start_build(page, key):
    """The Build menu's tool `key` started by script (as its button does); its template read."""
    page.evaluate("viewer.setSnapMode('tile')"); DRAWING['snap_back'] = True
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
    # every gap has all five handles; the start's handle a tile out under tile snap: the wall in the free form, its
    # start a tile back, its origin and gaps where they were (the improvements plan, D1)
    h = page.evaluate('viewer.wallHandles()')
    # (gaps a set at a time, design A: the picked gap's five handles, the others' middle; the first gap picked)
    assert {'end:x0', 'end:x1', 'open:1:middle'} | {f'open:0:{p}' for p in PARTS} <= set(h), sorted(h)
    assert 'open:1:x0' not in h, sorted(h)
    page.evaluate("viewer.setSnapMode('tile')")
    drag(page, h['end:x0'][:2], h['end:x0'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    s = state(page, wall)
    assert s['generated']['version'] == 5 and s['generated']['wall']['free'] == 1, s
    assert (s['generated']['wall']['x0'], s['generated']['wall']['x1']) == (-96, 384) and s['location'][0] == start[0], s
    assert [o['x0'] for o in s['generated']['wall']['openings']] == [96, 192], s
    mesh_ready(page, wall)
    # the window's middle a tile on, to the wall's end, with the snap at whole tiles (a gap's handles follow the snap)
    page.evaluate("viewer.setSnapMode('tile')")
    h = page.evaluate('viewer.wallHandles()')
    drag(page, h['open:1:middle'][:2], h['open:1:middle'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    assert [o['x0'] for o in state(page, wall)['generated']['wall']['openings']] == [96, 288], state(page, wall)
    assert 'Gap, 1 tile wide, from 72 over the floor to 168, at its end' in page.evaluate('viewer.wallPanelText()'), page.evaluate('viewer.wallPanelText()')
    # flip: the faces swap, the gaps stay in the world
    before_flip = state(page, wall)
    page.locator('#wallFlip').click()
    f = state(page, wall)
    assert f['rotation'][1] == 32768 and f['location'][0] == before_flip['location'][0], f      # (about its origin)
    # (its numbers mirrored about its origin: the window first now, from -384; the doorway from -192)
    assert [(o['x0'], o['z0']) for o in f['generated']['wall']['openings']] == [(-384, 72), (-192, 8)], f
    # undo and redo step through: flip, the slide, the end, the window, the doorway
    for expected in (before_flip, None):
        page.evaluate('viewer.gizmo.undo()')
        if expected: assert state(page, wall) == expected, (state(page, wall), expected)
    page.evaluate('viewer.gizmo.redo()'); page.evaluate('viewer.gizmo.redo()')
    assert state(page, wall) == f, (state(page, wall), f)
    # with the snap off a gap's top moves smoothly (not in steps of 8): the doorway's top dragged up about 20; Delete
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
    page.evaluate("viewer.setSnapMode('tile')")
    drag(page, h['end:top'][:2], h['end:top'][2:])
    low = state(page, wall)['generated']['wall']
    # (in levels of 64 under tile snap: the top lower by whole levels, its bottom where it was, its gaps under the top)
    assert low['z1'] < 384 and (384 - low['z1']) % 64 == 0 and low['z0'] == -16, low
    assert max(o['z1'] for o in low['openings']) <= low['z1'], low
    mesh_ready(page, wall)
    # the mesh drawn is the free form's (its key and request carry its numbers)
    mesh = page.evaluate("id => [...viewer.roots.values()].find(r => r.userData.source.id === id).userData.source.mesh", wall)
    assert '"free":1' in mesh and f'"z1":{low["z1"]}' in mesh, mesh
    out['lowered'] = low
    h = page.evaluate('viewer.wallHandles(150)')
    drag(page, h['end:top'][:2], h['end:top'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    assert state(page, wall)['generated']['wall']['z1'] > low['z1'], state(page, wall)
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
    # (a wall's length is x1 less x0: the first is in the free form, its x0 not 0)
    length = lambda w: w['x1'] - w['x0']    # noqa: E731
    first_through = length(kept['generated']['wall']) >= length(s2['generated']['wall'])
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
    page.evaluate("viewer.setSnapMode('tile')")
    drag(page, h['side:x1'][:2], h['side:x1'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    assert state(page, slab)['generated']['slab']['x1'] == 384 and state(page, slab)['generated']['version'] == 4, state(page, slab)
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
    page.evaluate("viewer.setSnapMode('fine')")
    drag(page, h['end:top'][:2], h['end:top'][2:])
    page.evaluate("viewer.setSnapMode('off')")
    g = state(page, ramp)['generated']['ground']
    raised = g['z1'] - g['z0']
    assert raised > 96 and raised % 24 == 0, g
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
    assert p['generated']['version'] == 5 and isinstance(p['generated']['ground'].get('look'), dict), p     # (still free)
    same = {k: v for k, v in p['generated']['ground'].items() if k != 'look'} == {k: v for k, v in t['generated']['ground'].items() if k != 'plain'}
    assert same and p['location'] == t['location'], (p, t)
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


# ---- the made pieces' other paths (item 4.6) -------------------------------------------------------------------------
# Made pieces pasted four tiles along y from one of the map's own fracturing pieces, which they are made of: the first
# one the game keeps whole when broken (a roof or floor: then Breaks further shows on them), else the first. Their ids
# in the order given, and whether their donor keeps its pieces.
MADE = """async ([made, along]) => {
  const T = await import('/vendor/three/three.module.js');
  const fracs = [...viewer.roots.values()].filter(r => !r.userData.source.added && !r.userData.deleted && r.visible
    && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
    && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length));
  const frac = fracs.find(r => r.userData.source.keepsPieces) ?? fracs[0];
  if (!frac) return null;
  const entries = made.map(generated => ({ source: frac.userData.source, matrix: frac.matrix.clone(),
    state: { tinted: false, flags: null, generated, blasts: null, breaksFurther: false } }));
  await viewer.pasteSnapshot({ entries, pivotIndex: 0, name: 'made pieces' }, new T.Matrix4().makeTranslation(0, 0, along));
  return { ids: viewer.gizmo.picks().ids, keeps: Boolean(frac.userData.source.keepsPieces) };
}"""
# the same, each piece turned `angle` (radians) about the vertical where it stands: their ids
MADE_TURNED = """async ([made, along, angle]) => {
  const T = await import('/vendor/three/three.module.js');
  const fracs = [...viewer.roots.values()].filter(r => !r.userData.source.added && !r.userData.deleted && r.visible
    && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
    && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length));
  const frac = fracs.find(r => r.userData.source.keepsPieces) ?? fracs[0];
  const entries = made.map(generated => ({ source: frac.userData.source,
    matrix: frac.matrix.clone().multiply(new T.Matrix4().makeRotationY(angle)),
    state: { tinted: false, flags: null, generated, blasts: null, breaksFurther: false } }));
  await viewer.pasteSnapshot({ entries, pivotIndex: 0, name: 'made pieces' }, new T.Matrix4().makeTranslation(0, 0, along));
  return viewer.gizmo.picks().ids;
}"""
BREAK_WALL = dict(kind='fracWall', version=4, wall=dict(x0=0, x1=288, openings=[], seed=3))
BREAK_FLOOR = dict(kind='fracSlab', version=3, slab=dict(x0=0, x1=192, y0=0, y1=192, holes=[], seed=1, look='floor'))
BREAK_ROOF = dict(kind='fracSlab', version=3, slab=dict(x0=0, x1=192, y0=0, y1=192, holes=[], seed=2))      # (no look: the roof)
OPEN_WALL = dict(kind='fracWall', version=4, wall=dict(x0=0, x1=480, seed=3, openings=[
    dict(x0=96, x1=192, z0=8, z1=160), dict(x0=288, x1=384, z0=72, z1=168)]))
OPEN_FLOOR = dict(kind='fracSlab', version=3, slab=dict(x0=0, x1=288, y0=0, y1=288, seed=1, look='floor', holes=[
    dict(x0=0, x1=96, y0=0, y1=96), dict(x0=192, x1=288, y0=192, y1=288)]))
SEEDED_ROCK = dict(kind='ground', version=4, ground=dict(shape='rock', x0=0, x1=192, y0=0, y1=192, height=96, seed=5))
# EXP-90's floor B in the free form, without its hole (F-147)
FREE_FLOOR = dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0.0, x1=230.5, y0=0.0, y1=170.25, z0=192.0, z1=194.0,
                                                        holes=[], seed=902, look='floor'))


def made_pieces(page, made):
    """The made pieces `made` pasted (MADE): their ids, each checked to be of its kind, and whether they keep pieces."""
    got = page.evaluate(MADE, [made, 384])
    assert got, 'this map has no fracturing piece of its own to make pieces of'
    ids = got['ids'][:len(made)]
    for piece, g in zip(ids, made):
        page.wait_for_function('id => viewer.wallMeshReady(id)', arg=piece, timeout=60000)
        assert page.evaluate('id => viewer.wallState(id).generated.kind', piece) == g['kind'], (piece, g)
    return ids, got['keeps']


def generated(page, piece):
    return page.evaluate('id => viewer.wallState(id).generated', piece)


def key(page, keys):
    """Keys pressed with nothing focused (a button clicked before keeps the focus)."""
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press(keys)


def break_made(page, piece, row):
    """Break on a made piece as the user does: picked and framed, B (the panel's Break lit), a click on it, the map's
    other pieces hidden so that the click's ray meets it (the pick takes drawn pieces only), then Escape; its blasts."""
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', piece)
    page.wait_for_timeout(300)      # (a frame drawn where it was framed: screenOf reads its matrices)
    key(page, 'b')
    assert 'on' in (page.locator(f'#{row}Break').get_attribute('class') or '').split(), row
    hidden = page.evaluate("""id => { const out = [];
      for (const r of viewer.roots.values()) if (r.visible && r.userData.source.id !== id) { r.visible = false; out.push(r.userData.source.id); }
      return out; }""", piece)
    box = page.evaluate('id => viewer.pieceBox(id)', piece)
    blasts = []
    for fz in (0.5, 0.8, 0.2):
        for fx, fy in ((0.5, 0.5), (0.3, 0.5), (0.7, 0.5), (0.5, 0.3), (0.5, 0.7), (0.2, 0.2), (0.8, 0.8)):
            at = [box[0] + fx * (box[1] - box[0]), box[2] + fy * (box[3] - box[2]), box[4] + fz * (box[5] - box[4])]
            page.mouse.click(*page.evaluate('p => viewer.screenOf(p)', at))
            blasts = generated(page, piece).get('blasts') or []
            if blasts: break
        if blasts: break
    page.evaluate('ids => { for (const id of ids) viewer.roots.get(id).visible = true; }', hidden)
    key(page, 'Escape')
    assert 'on' not in (page.locator(f'#{row}Break').get_attribute('class') or '').split(), row
    return blasts


def check_made_break(browser, url, open_viewer, skip):
    errors = []
    page = open_viewer(browser, url, errors)
    ids, keeps = made_pieces(page, [BREAK_WALL, BREAK_FLOOR, BREAK_ROOF])
    out = dict(keeps=keeps)
    for piece, row, what in zip(ids, ('wall', 'slab', 'slab'), ('wall', 'floor', 'roof')):
        before = generated(page, piece)
        size = int(page.locator(f'#{row}BlastSize').input_value())
        blasts = break_made(page, piece, row)
        assert len(blasts) == 1 and blasts[0]['radius'] == 96 * size, (what, blasts)
        assert page.locator(f'#{row}Broken').inner_text() == 'Broken by 1 blast', (what, page.locator(f'#{row}Broken').inner_text())
        # (the floor and the roof by their look: the slab panel says which)
        if row == 'slab': assert page.locator('#slabHead').text_content().startswith('Floor' if what == 'floor' else 'Roof'), page.locator('#slabHead').text_content()
        # the blast is one undo step
        key(page, 'Control+z')
        assert not generated(page, piece).get('blasts'), (what, generated(page, piece))
        key(page, 'Control+y')
        assert generated(page, piece).get('blasts') == blasts, (what, generated(page, piece))
        # Breaks further in battle: shown on a broken piece the game keeps whole; ticked, one undo step
        further = page.locator(f'#{row}Further')
        if keeps:
            assert page.locator(f'#{row}FurtherRow').is_visible() and not further.is_checked(), what
            further.check()
            assert generated(page, piece).get('breaksFurther') is True, (what, generated(page, piece))
            key(page, 'Control+z')
            assert not generated(page, piece).get('breaksFurther') and generated(page, piece).get('blasts') == blasts, (what, generated(page, piece))
            key(page, 'Control+y')
            assert generated(page, piece).get('breaksFurther') is True, what
        else:
            assert page.locator(f'#{row}FurtherRow').is_hidden(), what
        # Repair mends it whole (its blasts and Breaks further gone), one undo step
        page.locator(f'#{row}Repair').click()
        assert generated(page, piece) == before, (what, generated(page, piece), before)
        assert page.locator(f'#{row}Repair').is_disabled() and page.locator(f'#{row}Broken').inner_text() == '', what
        assert page.locator(f'#{row}FurtherRow').is_hidden(), what
        key(page, 'Control+z')
        assert generated(page, piece).get('blasts') == blasts and bool(generated(page, piece).get('breaksFurther')) == keeps, (what, generated(page, piece))
        out[what] = dict(at=blasts[0]['at'], radius=blasts[0]['radius'])
    if not keeps: skip('made-break', 'Breaks further: the map has no fracturing piece the game keeps whole to make the pieces of')
    page.close()
    assert not errors, errors
    return out


def check_made_openings(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    (wall, floor), _ = made_pieces(page, [OPEN_WALL, OPEN_FLOOR])
    openings = lambda: generated(page, wall)['wall']['openings']     # noqa: E731
    stands = lambda id: page.evaluate('id => Boolean(viewer.roots.get(id) && !viewer.roots.get(id).userData.deleted)', id)   # noqa: E731
    first, second = OPEN_WALL['wall']['openings']
    # the second gap last touched, its row in the panel pointed at: Delete takes it out, the wall stays; one undo step
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#wallBox:not([hidden]) #wallOpenings .wallopening')
    assert page.locator('#wallOpenings .wallopening').count() == 2
    page.locator('#wallOpenings .wallopening').nth(1).hover()
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    key(page, 'Delete')
    assert openings() == [first] and stands(wall), (openings(), stands(wall))
    assert 'Removed the opening' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth + 1
    key(page, 'Control+z')
    assert openings() == [first, second], openings()
    # the first gap's handle clicked (no drag): Delete takes that one
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', wall)
    page.wait_for_timeout(300)
    page.wait_for_function('id => viewer.wallMeshReady(id)', arg=wall, timeout=30000)
    handle = page.evaluate('viewer.wallHandles()')['open:0:middle']
    page.mouse.click(*handle[:2])
    assert openings() == [first, second], openings()       # (a click on a handle moves nothing)
    key(page, 'Delete')
    assert openings() == [second] and stands(wall), (openings(), stands(wall))
    key(page, 'Control+z')
    assert openings() == [first, second], openings()
    # a floor's hole the same way: the second's row pointed at, Delete fills it; one undo step
    holes = lambda: generated(page, floor)['slab']['holes']     # noqa: E731
    page.evaluate('id => viewer.select(id)', floor)
    page.wait_for_selector('#slabBox:not([hidden]) #slabHoles .wallopening')
    page.locator('#slabHoles .wallopening').nth(1).hover()
    key(page, 'Delete')
    assert holes() == OPEN_FLOOR['slab']['holes'][:1] and stands(floor), (holes(), stands(floor))
    assert 'Filled the hole' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    key(page, 'Control+z')
    assert holes() == OPEN_FLOOR['slab']['holes'], holes()
    floor_tiles = check_free_floor_tiles(page)
    page.close()
    assert not errors, errors
    return dict(gaps=len(OPEN_WALL['wall']['openings']), holes=len(OPEN_FLOOR['slab']['holes']), floorTiles=floor_tiles)


def made_cursors_module():
    """tools/bake/made_cursors.py, the Build's rule for a made slab's tiles, for the page's answers to be held to."""
    import sys
    from pathlib import Path
    bake = str(Path(__file__).resolve().parents[2] / 'bake')
    if bake not in sys.path:
        sys.path.append(bake)
    import made_cursors
    return made_cursors


def check_free_floor_tiles(page):
    """A free-form floor 230.5 by 170.25 (EXP-90's B, F-147), off the tile lines: its section's line and notes say on
    how many tiles it is floor and that those it covers in part are not, and the tile grid fills the tiles it is floor
    on and outlines the others, as the Build's rule (made_cursors.tiles) has them for where it stands."""
    made_cursors = made_cursors_module()
    (slab,), _ = made_pieces(page, [FREE_FLOOR])
    page.evaluate('id => viewer.select(id)', slab)
    page.wait_for_selector('#slabBox:not([hidden])')
    state = page.evaluate('id => viewer.wallState(id)', slab)
    corner = page.evaluate('viewer.data.tileGrid.tiles ?? viewer.data.tileGrid.origin.map(v => v - 1)')
    want = made_cursors.tiles([dict(outline=made_cursors.outline(state['location'], state['rotation'], state['generated']['slab']),
                                    holes=[])], corner)
    assert want['part'], (state, corner, want)       # (a floor of this size covers some tile in part wherever it stands)
    n, m = len(want['floor']), len(want['part'])
    line = page.locator('#slabState').inner_text()
    assert line.endswith('floor on %d of %d tiles' % (n, n + m)), line
    text = page.evaluate('viewer.slabPanelText()')
    assert 'at its edge it covers in part %s no floor at its height' % ('is' if m == 1 else 'are') in text, text
    grid = page.evaluate('viewer.tileGrid()')
    assert sorted(grid['tiles']) == sorted('%d,%d' % (i, j) for i, j in want['floor']), (grid, want)
    assert sorted(grid['edges']) == sorted('%d,%d' % (i, j) for i, j, _ in want['part']), (grid, want)
    note = page.locator('#tileNote').inner_text()
    assert note.startswith('%d floor tile' % n) and ('%d in part: no floor' % m) in note, note
    # turned 20 degrees about the vertical (EXP-90's E), a storey and a half lower so that its floor's break is one of
    # its own: its cursor floors stand in steps (made_cursors.steps), each floor of them over the steps' area, not
    # over the box round it
    turned = dict(FREE_FLOOR, slab=dict(FREE_FLOOR['slab'], x1=288.0, y1=192.0, z0=140.0, z1=142.0))
    ids = page.evaluate(MADE_TURNED, [[turned], 1152, 0.349])
    page.wait_for_function('id => viewer.wallMeshReady(id)', arg=ids[0], timeout=60000)
    state = page.evaluate('id => viewer.wallState(id)', ids[0])
    assert made_cursors.turned(state['rotation']), state['rotation']
    steps = made_cursors.steps([dict(outline=made_cursors.outline(state['location'], state['rotation'], state['generated']['slab']),
                                     holes=[])], 0.0, 1.0, corner)
    want = sum((b[3] - b[0]) * (b[4] - b[1]) for b in steps)
    lo = [min(b[k] for b in steps) - 0.01 for k in (0, 1)]
    hi = [max(b[k + 3] for b in steps) + 0.01 for k in (0, 1)]
    bands = {}
    for s in page.evaluate('viewer.cursorStoreys()') or []:
        b = s['box']
        if s.get('slab') and lo[0] <= b[0] and b[3] <= hi[0] and lo[1] <= b[1] and b[4] <= hi[1]:
            bands[round(b[2], 3)] = bands.get(round(b[2], 3), 0.0) + (b[3] - b[0]) * (b[4] - b[1])
    assert bands and all(abs(a - want) < 1.0 for a in bands.values()), (bands, want, len(steps))
    return dict(floor=n, part=m, steps=len(steps))


# The point gizmo's arrow along the rock's own x on the screen, for the corner it stands on: [x, y] at `a` and at `b`
# gizmo units along it (TransformControls draws its handles `factor` / 4 world units to a unit, `factor` from the
# camera's distance and field of view; the arrow's grip runs 0 to 0.6 each way), and the world units a unit is.
POINT_ARROW = """async ([id, index, a, b]) => {
  const T = await import('/vendor/three/three.module.js');
  const root = viewer.roots.get(id), g = viewer.wallState(id).generated.ground;
  const p = (g.points ?? viewer.rockCorners().map(([, v]) => v).find(v => v?.points)?.points)[index];
  root.updateMatrixWorld(true);
  const at = new T.Vector3(p[0], p[2], p[1]).applyMatrix4(root.matrixWorld);
  const along = new T.Vector3(1, 0, 0).transformDirection(root.matrixWorld);
  const c = viewer.camera, factor = at.distanceTo(c.position) * Math.min(1.9 * Math.tan(Math.PI * c.fov / 360) / c.zoom, 7);
  const r = viewer.renderer.domElement.getBoundingClientRect();
  const screen = k => { const v = at.clone().addScaledVector(along, k * factor / 4).project(c);
                        return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height]; };
  return { a: screen(a), b: screen(b), unit: factor / 4, point: p };
}"""


def check_rock_corner(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    (rock,), _ = made_pieces(page, [SEEDED_ROCK])
    page.evaluate("viewer.setSnapMode('off')")
    assert page.evaluate('viewer.gizmo.snap') == 'off'
    page.evaluate('id => viewer.select(id)', rock)
    box = page.evaluate('id => viewer.pieceBox(id)', rock)
    middle = [(box[0] + box[1]) / 2, (box[2] + box[3]) / 2, box[4]]
    look_at(page, middle)
    # its corners come from the server: a blue point on each
    page.wait_for_function("Object.keys(viewer.wallHandles()).some(k => k.startsWith('point:'))", timeout=30000)
    handles = page.evaluate('viewer.wallHandles()')
    corners = sorted(int(k.split(':')[1]) for k in handles if k.startswith('point:'))
    before = page.evaluate("viewer.rockCorners().map(([, v]) => v).find(v => v?.points)?.points")
    # a corner of the rock's foot (no up arrow): clicked, it takes the point gizmo
    index = next((i for i in corners if i < 7), corners[0])
    page.mouse.click(*handles[f'point:{index}'][:2])
    picked = page.evaluate('viewer.rockPoint()')
    assert picked and picked['id'] == rock and picked['index'] == index and picked['gizmo'] and picked['up'] == (index >= 7), picked
    assert 'A corner of the rock' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    # its arrow along the rock's x dragged toward the rock's middle (the foot stays the size it is): the corner moves
    # along x by what was dragged, nothing else does
    inward = -1 if before[index][0] > (SEEDED_ROCK['ground']['x0'] + SEEDED_ROCK['ground']['x1']) / 2 else 1
    arrow = page.evaluate(POINT_ARROW, [rock, index, -0.5 * inward, -0.25 * inward])
    page.mouse.move(*arrow['a'])
    page.mouse.down()
    page.mouse.move(*arrow['b'], steps=6)
    page.mouse.up()
    page.wait_for_function('id => Boolean(viewer.wallState(id).generated.ground.points)', arg=rock, timeout=10000)
    moved = generated(page, rock)['ground']['points']
    shift = moved[index][0] - before[index][0]
    expected = 0.25 * inward * arrow['unit']
    assert abs(shift - expected) < 0.35 * abs(expected), (shift, expected, before[index], moved[index])
    assert all(abs(moved[index][k] - before[index][k]) < 0.01 for k in (1, 2)), (before[index], moved[index])
    assert all(math.dist(m, b) < 0.01 for k, (m, b) in enumerate(zip(moved, before)) if k != index), 'another point moved'
    # one undo step; redo moves it again
    key(page, 'Control+z')
    assert not generated(page, rock)['ground'].get('points'), generated(page, rock)
    key(page, 'Control+y')
    assert generated(page, rock)['ground']['points'] == moved
    # Escape lets the corner go
    key(page, 'Escape')
    page.wait_for_function('viewer.rockPoint() === null', timeout=5000)
    page.close()
    assert not errors, errors
    return dict(corner=index, shift=round(shift, 1), expected=round(expected, 1))


# the police station's open ground the walls check draws its room on (game units, its corners)
ROOM_AT = ([-1344.0, -2304.0, 16.0], [-1056.0, -2496.0, 16.0])
CARDS = '.lookpicker .lookcard'


def draw_room(page, tool):
    """A room (or a room with a roof: `tool` 'roomroof') drawn from the Build menu on ROOM_AT, seen from straight
    above, and picked whole: its pieces' ids."""
    before = set(page.evaluate('[...viewer.roots.keys()]'))
    start_build(page, tool)
    a, b = ROOM_AT
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 1, c[2] + 1400, c[1] + 1);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", [(a[k] + b[k]) / 2 for k in range(3)])
    page.wait_for_timeout(300)      # (a frame drawn from where the camera was put: screenOf reads its matrices)
    drag(page, ground_point(page, a), ground_point(page, b))
    count = 5 if tool == 'roomroof' else 4
    page.wait_for_function('n => viewer.roots.size === n', arg=len(before) + count, timeout=60000)
    if page.evaluate('viewer.wallDrawing()'): page.keyboard.press('Escape')
    made = [i for i in page.evaluate('[...viewer.roots.keys()]') if i not in before]
    for piece in made: mesh_ready(page, piece)
    page.evaluate('id => viewer.select(id)', made[0])
    page.wait_for_selector('#roomBox:not([hidden])')
    return made


def room_walls(page):
    """The picked room's walls: their ids and their numbers."""
    picked = page.evaluate('viewer.roomPicked()')
    assert picked, 'no room picked'
    return picked, [generated(page, w)['wall'] for w in picked['walls']]


def room_look(page, chooser, words, kind, plain):
    """The room panel's Choose... (`chooser`) gives the look of the picker's second card, then its Plain (`plain`) takes
    it back, each one undo step: the words of the panel's look line (`words`) at each step."""
    page.locator(f'#{chooser}').click()
    page.wait_for_function("([k, s]) => viewer.lookMode() === k && document.querySelectorAll(s).length > 1", arg=[kind, CARDS], timeout=60000)
    card = page.locator(CARDS).nth(1)
    name = card.locator('strong').text_content()
    old = page.evaluate('viewer.roomPicked()')
    card.click()
    page.wait_for_function("([o, n, want]) => { const r = viewer.roomPicked(); return r && JSON.stringify(r) !== JSON.stringify(o)"
                           " && document.getElementById(n).textContent.endsWith(want); }", arg=[old, words, ': ' + name], timeout=90000)
    chosen = page.locator(f'#{words}').text_content()
    assert page.locator(f'#{plain}').is_enabled(), plain
    looked = page.evaluate('viewer.roomPicked()')
    page.locator(f'#{plain}').click()
    page.wait_for_function("([o, n]) => { const r = viewer.roomPicked(); return r && JSON.stringify(r) !== JSON.stringify(o)"
                           " && document.getElementById(n).textContent.endsWith('no look chosen'); }", arg=[looked, words], timeout=90000)
    assert page.locator(f'#{plain}').is_disabled(), plain
    # each one undo step: back to the look, back to plain
    key(page, 'Control+z')
    page.wait_for_function("([n, want]) => viewer.roomPicked() && document.getElementById(n).textContent.endsWith(want)", arg=[words, ': ' + name], timeout=30000)
    key(page, 'Control+z')
    page.wait_for_function("n => viewer.roomPicked() && document.getElementById(n).textContent.endsWith('no look chosen')", arg=words, timeout=30000)
    return chosen


def check_room_buttons(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    # (the points above are on the police station's ground: on another map they mean nothing)
    assert page.evaluate('viewer.mapId') == 'URB_PoliceStation', f"open the police station (?map=URB_PoliceStation), not {page.evaluate('viewer.mapId')}"
    page.evaluate("for (const k of ['workshop.wallLook', 'workshop.slabLook', 'workshop.groundLook']) localStorage.removeItem(k)")
    out = {}
    # a room: picked whole, its panel the room's (no wall's own), four walls of two storeys, no roof row
    made = draw_room(page, 'room')
    assert page.locator('#wallBox').is_hidden() and page.locator('#roomRoofRow').is_hidden() and page.locator('#roomStoreysRow').is_visible()
    assert page.locator('#roomHead').text_content() == f'Room {DOT} 3 by 2 tiles', page.locator('#roomHead').text_content()
    picked, walls = room_walls(page)
    assert sorted(picked['walls']) == sorted(made) and not any('storeys' in w for w in walls), walls
    # Lower: every wall one storey, one undo step; Taller: two again
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    page.locator('#roomShorter').click()
    assert all(w.get('storeys') == 1 for w in room_walls(page)[1]), room_walls(page)[1]
    assert 'one storey' in page.locator('#roomState').text_content() and page.evaluate('viewer.gizmo.undoDepth()') == depth + 1
    page.locator('#roomStoreys').click()
    assert not any('storeys' in w for w in room_walls(page)[1]), room_walls(page)[1]
    key(page, 'Control+z')
    assert all(w.get('storeys') == 1 for w in room_walls(page)[1])
    key(page, 'Control+z')
    assert not any('storeys' in w for w in room_walls(page)[1]) and page.evaluate('viewer.gizmo.undoDepth()') == depth
    # the walls' Choose... and Plain
    assert page.locator('#roomWallsLook').text_content() == 'Walls: no look chosen' and page.locator('#roomWallsPlain').is_disabled()
    out['walls'] = room_look(page, 'roomWallsChoose', 'roomWallsLook', 'wall', 'roomWallsPlain')
    # taken back (one undo step: the room drawn), and a room with a roof drawn in its place: no Lower or Taller, its
    # roof's Choose... and Plain
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.gizmo.undo()')
    page.wait_for_function('ids => ids.every(id => !viewer.roots.get(id) || viewer.roots.get(id).userData.deleted)', arg=made, timeout=30000)
    draw_room(page, 'roomroof')
    assert page.locator('#roomRoofRow').is_visible() and page.locator('#roomStoreysRow').is_hidden()
    assert page.evaluate('viewer.roomPicked().roof'), page.evaluate('viewer.roomPicked()')
    assert page.locator('#roomRoofLook').text_content() == 'Roof: no look chosen' and page.locator('#roomRoofPlain').is_disabled()
    out['roof'] = room_look(page, 'roomRoofChoose', 'roomRoofLook', 'slab', 'roomRoofPlain')
    out['uncatalogued'] = room_uncatalogued(page)
    page.close()
    assert not errors, errors
    return out


def room_uncatalogued(page):
    """The picked room's walls given the look of a police station wall the walls' catalogue holds, then the catalogue
    forgotten and its read refused: the Room section names the look by its donor's mesh, as a wall's own Wall section
    does once the room is ungrouped (decision D6 of the follow-ups; it said "made from numbers" before)."""
    found = page.evaluate("""async () => {
      window.looksModule = await import('/looks.js');
      await looksModule.loadLooks('wall');
      for (const o of viewer.data.objects) {
        const name = viewer.data.meshes[o.mesh]?.name, entry = name && looksModule.entryForPiece('wall', name);
        if (entry) return { actor: o.actor, mesh: name, name: entry.name };
      }
      return null; }""")
    assert found, 'no wall of the map in the walls\' catalogue'
    old = page.evaluate('viewer.roomPicked()')
    page.evaluate("""([id, f]) => viewer.setMadeLook(id, 'wall', looksModule.lookFromEntry('wall', looksModule.entryForPiece('wall', f.mesh),
                                                                                      { package: viewer.mapId, actor: f.actor }))""",
                  [old['walls'][0], found])
    page.wait_for_function("([o, want]) => { const r = viewer.roomPicked(); return r && JSON.stringify(r) !== JSON.stringify(o)"
                           " && document.getElementById('roomWallsLook').textContent === want; }",
                           arg=[old, f"Walls: {found['name']}"], timeout=90000)
    walls = page.evaluate('viewer.roomPicked()')['walls']
    page.route('**/looks/walls.json', lambda route: route.abort())
    page.evaluate('looksModule.forgetLooks()')
    page.evaluate('viewer.select(null)')
    page.evaluate('id => viewer.select(id)', walls[0])
    page.wait_for_selector('#roomBox:not([hidden])')
    mesh = found['mesh'].split('.')[-1]
    words = page.locator('#roomWallsLook').text_content()
    key(page, 'Control+Shift+g')
    page.wait_for_function('!viewer.roomPicked()', timeout=30000)
    page.evaluate('id => viewer.select(id)', walls[0])
    page.wait_for_selector('#wallBox:not([hidden])')
    head = page.locator('#wallHead').text_content()
    page.unroute('**/looks/walls.json')
    assert (words, head) == (f'Walls: {mesh}', f'Wall {DOT} {mesh}'), (words, head)
    return dict(mesh=found['mesh'], room=words, wall=head)


if __name__ == '__main__':
    print(json.dumps(dict(note='run through browser_smoke.py --only walls --projects')))


FREE_WALL = dict(kind='fracWall', version=5, wall=dict(free=1, x0=0, x1=480, y0=-8, y1=8, z0=-16, z1=600, tall='repeat', seed=3,
                                                       openings=[dict(x0=96, x1=192, z0=8, z1=160), dict(x0=288, x1=384, z0=72, z1=168)]))
FREE_SLAB = dict(kind='fracSlab', version=4, slab=dict(free=1, x0=0, x1=288, y0=0, y1=192, z0=190, z1=194, holes=[], seed=1, look='floor'))


def check_free_handles(browser, url, open_viewer):
    """The made pieces' handles and commands of the chosen design (the custom geometry improvements plan, 10.6, design
    A): a wall's thickness and bottom handles, white on stems, under tile snap a tile thicker and a level lower, its
    origin kept; its gaps a set at a time (the picked one's five handles, the others' middle alone); a floor's top and
    underside; Pivot to corner keeping it where it is; Taller than its look's Stretch; Join ends on two walls."""
    errors = []
    page = open_viewer(browser, url, errors)
    (wall, slab, off), _ = made_pieces(page, [FREE_WALL, FREE_SLAB, dict(FREE_WALL, wall=dict(FREE_WALL['wall'], x0=-96))])
    page.evaluate("viewer.setSnapMode('tile')")
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', wall)
    page.wait_for_timeout(400)
    mesh_ready(page, wall)
    h = page.evaluate('viewer.wallHandles()')
    assert {'end:x0', 'end:x1', 'end:top', 'end:bottom', 'end:face'} <= set(h), sorted(h)
    # gaps a set at a time: nothing picked, the middles alone
    assert {k for k in h if k.startswith('open:')} == {'open:0:middle', 'open:1:middle'}, sorted(h)
    start = state(page, wall)
    drag(page, h['end:face'][:2], h['end:face'][2:])
    w = state(page, wall)['generated']['wall']
    assert w['y1'] - w['y0'] == 16 + 96 and state(page, wall)['location'] == start['location'], w
    page.keyboard.press('Control+z')
    h = page.evaluate('viewer.wallHandles(-72)')
    drag(page, h['end:bottom'][:2], h['end:bottom'][2:])
    w = state(page, wall)['generated']['wall']
    assert w['z0'] == -16 + 64 and w['z1'] == 600, w            # (the handle's axis is down: 72 up it is a level, under tile snap)
    page.keyboard.press('Control+z')
    # a gap's middle clicked: its five handles
    h = page.evaluate('viewer.wallHandles()')
    page.mouse.click(*h['open:1:middle'][:2])
    h = page.evaluate('viewer.wallHandles()')
    assert {f'open:1:{p}' for p in PARTS} <= set(h) and 'open:0:x0' not in h, sorted(h)
    # Taller than its look (600 tall, past the Bar look's 400): Stretch, one undo step
    page.wait_for_selector('#wallTallRow:not([hidden])')
    page.locator('#wallTall button[data-value="stretch"]').click()
    assert generated(page, wall)['wall']['tall'] == 'stretch', generated(page, wall)
    mesh_ready(page, wall)
    page.keyboard.press('Control+z')
    assert generated(page, wall)['wall']['tall'] == 'repeat'
    # Pivot to corner: an off-corner wall renumbered from 0, its place moved by as much, nothing moving in the world
    page.evaluate('id => viewer.select(id)', off)
    page.wait_for_selector('#wallBox:not([hidden]) #wallPivot')
    before = state(page, off)
    page.locator('#wallPivot').click()
    after = state(page, off)
    assert after['generated']['wall']['x0'] == 0 and after['generated']['wall']['x1'] == 576, after
    # (its origin moved to where its x0 was: 96 back along its own direction, whatever its yaw)
    import math
    yaw = before['rotation'][1] * 2 * math.pi / 65536
    want = [before['location'][0] - 96 * math.cos(yaw), before['location'][1] - 96 * math.sin(yaw)]
    assert all(abs(after['location'][k] - want[k]) < 0.01 for k in (0, 1)), (before, after, want)
    assert [o['x0'] for o in after['generated']['wall']['openings']] == [192, 384], after
    # a floor's top and underside handles
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', slab)
    page.wait_for_timeout(400)
    mesh_ready(page, slab)
    assert {'end:top', 'end:bottom'} <= set(page.evaluate('viewer.wallHandles()'))
    # Join ends: two walls picked, their nearer ends brought to where their lines cross
    (second,), _ = made_pieces(page, [dict(FREE_WALL, wall=dict(FREE_WALL['wall'], openings=[]))])
    # (the second turned a quarter from the first, alone, so their lines cross)
    page.evaluate("id => viewer.select(id)", second)
    yaw = state(page, wall)['rotation'][1] * 360 / 65536
    page.evaluate("y => viewer.gizmo.setPose(null, [0, y, 0])", yaw + 90)
    # (and moved off the first's start, so the crossing is along both: (the made pieces paste at one place)
    import math
    r = state(page, wall)['rotation'][1] * 2 * math.pi / 65536
    d, n = (math.cos(r), math.sin(r)), (-math.sin(r), math.cos(r))
    loc = state(page, second)['location']
    page.evaluate("p => viewer.gizmo.setPose(p, null)", [loc[0] + d[0] * 240 - n[0] * 200, loc[1] + d[1] * 240 - n[1] * 200, loc[2]])
    page.evaluate("([a, b]) => { viewer.select(a); viewer.select(b, true); }", [wall, second])
    was = [state(page, wall)['generated']['wall'], state(page, second)['generated']['wall']]
    page.wait_for_selector('#wallJoin:not([hidden])')
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    page.locator('#wallJoin').click()
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth + 1, page.locator('#dragHint').inner_text()
    now = [state(page, wall)['generated']['wall'], state(page, second)['generated']['wall']]
    assert now != was and 'mitred corner' in page.locator('#dragHint').inner_text(), (was, now)
    page.evaluate("viewer.setSnapMode('off')")
    page.close()
    assert not errors, errors
    return dict(handles=5)


TEX_WALL = dict(FREE_WALL, wall=dict(FREE_WALL['wall'], openings=[]))


def surface_now(page, piece, role):
    g = generated(page, piece)
    numbers = g[{'fracWall': 'wall', 'fracSlab': 'slab', 'ground': 'ground'}[g['kind']]]
    return ((numbers.get('mapping') or {}).get('surfaces') or {}).get(role)


def alone_click(page, piece, at):
    """A click at `at` with the map's other pieces hidden, so that its ray meets the made piece (the pick takes drawn
    pieces only)."""
    hidden = page.evaluate("""id => { const out = [];
      for (const r of viewer.roots.values()) if (r.visible && r.userData.source.id !== id) { r.visible = false; out.push(r.userData.source.id); }
      return out; }""", piece)
    page.mouse.click(*at)
    page.evaluate('ids => { for (const id of ids) viewer.roots.get(id).visible = true; }', hidden)


def check_texture_mapping(browser, url, open_viewer):
    """A made piece's texture mapping as chosen (the custom geometry improvements plan, 10.6, design B): the Texture
    mapping fold opened on a made wall puts its size handles and the move gizmo aside and picks the face toward the
    camera; Tab picks the other face and a click the one clicked; Size takes the look's repeat (one undo step); the
    blue dot slides the pattern a tile under tile snap, Esc during a drag puts it back, the ring turns it in steps of
    15 under fine snap about its corner, the white dot sizes a repeat in tiles under tile snap and smoothly with snap
    off (u and v alike), each one undo step; the fields set a value exactly; Aligned to the world puts the piece's
    place in its mesh's request; Original and Reset surface take the surface's mapping out; a floor's top and
    underside picked by clicking them, Tab back to the top, the gizmo still aside; the fold shut, the size handles and
    the gizmo back."""
    errors = []
    page = open_viewer(browser, url, errors)
    (wall, slab), _ = made_pieces(page, [TEX_WALL, FREE_SLAB])
    page.evaluate("viewer.setSnapMode('tile')")
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', wall)
    page.wait_for_timeout(400)
    mesh_ready(page, wall)
    assert page.evaluate('viewer.wallHandles()'), 'the size handles show while the fold is shut'
    assert page.evaluate('viewer.gizmo.controls.enabled'), 'the move gizmo shows while the fold is shut'
    # the fold opened: the size handles and the gizmo step aside, the face toward the camera picked, no handles while
    # Original
    page.locator('#texFold > summary').click()
    page.wait_for_function('viewer.texturePicked()')          # (a fold's toggle comes after the click)
    picked = page.evaluate('viewer.texturePicked()')
    assert picked and picked['id'] == wall and picked['role'] == 'faces' and picked['side'] in ('y0', 'y1'), picked
    assert page.evaluate('viewer.wallHandles()') == {}, page.evaluate('viewer.wallHandles()')
    assert not page.evaluate('viewer.gizmo.controls.enabled'), 'the move gizmo steps aside while the fold is open'
    # (the turn gizmo too: R changes its mode, not whether it shows)
    key(page, 'r')
    assert not page.evaluate('viewer.gizmo.controls.enabled'), 'the turn gizmo stays aside while the fold is open'
    key(page, 'g')
    assert page.locator('#texFoldVal').inner_text() == 'faces: original', page.locator('#texFoldVal').inner_text()
    assert page.evaluate('viewer.textureHandles()')['slide'] is None
    side = picked['side']
    # Tab: the other face; a click on the face seen picks it again
    key(page, 'Tab')
    assert page.evaluate('viewer.texturePicked()')['side'] != side, page.evaluate('viewer.texturePicked()')
    alone_click(page, wall, page.evaluate('s => viewer.textureSurfaceAt("faces", s)', side))
    assert page.evaluate('viewer.texturePicked()')['side'] == side, page.evaluate('viewer.texturePicked()')
    assert page.evaluate('viewer.gizmo.picks().ids') == [wall], 'the click picked a surface, not a piece'
    # Size: the look's repeat (the Bar look gives none: 192), one undo step
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    page.locator('#texMode button[data-value="size"]').click()
    assert surface_now(page, wall, 'faces') == dict(mode='size', u=192, v=192), surface_now(page, wall, 'faces')
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth + 1
    assert page.locator('#texFoldVal').inner_text() == 'faces: size 192', page.locator('#texFoldVal').inner_text()
    mesh_ready(page, wall)
    h = page.evaluate('viewer.textureHandles()')
    assert h['slide'] and h['turn'] and h['size'], h
    point = lambda ab: page.evaluate('([s, ab]) => viewer.textureSurfaceAt("faces", s, ab)', [side, ab])   # noqa: E731
    # the blue dot under tile snap: 100 along and 10 up is a tile along (half a repeat of 192), nothing up
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    drag(page, h['slide'], point([h['at'][0] + 100, h['at'][1] + 10]))
    s = surface_now(page, wall, 'faces')
    assert s.get('offsetU') == -0.5 and 'offsetV' not in s, s
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth + 1
    # Esc during a drag puts it back
    h = page.evaluate('viewer.textureHandles()')
    page.mouse.move(*h['slide'])
    page.mouse.down()
    page.mouse.move(*point([h['at'][0] + 250, h['at'][1] + 130]), steps=6)
    assert page.evaluate('viewer.textureDragging()')
    page.keyboard.press('Escape')
    page.mouse.up()
    assert surface_now(page, wall, 'faces') == s and not page.evaluate('viewer.textureDragging()'), surface_now(page, wall, 'faces')
    # the white dot under tile snap: 100 further out along its way is a tile on the repeat at the dot, `reach` repeats out
    page.evaluate("viewer.setSnapMode('tile')")
    h = page.evaluate('viewer.textureHandles()')
    at, out = h['at'], h['sizeAt']
    way = [out[0] - at[0], out[1] - at[1]]
    length = math.hypot(*way)
    way = [v / length for v in way]
    drag(page, h['size'], point([out[0] + 100 * way[0], out[1] + 100 * way[1]]))
    s = surface_now(page, wall, 'faces')
    want = 192 * (length + 96) / length
    assert abs(s['u'] - want) < 1e-3 and s['u'] == s['v'], (s, want, h['reach'])
    # with snap off, smoothly: the dot taken to twice as far doubles the repeat
    page.evaluate("viewer.setSnapMode('off')")
    h = page.evaluate('viewer.textureHandles()')
    at, out, was = h['at'], h['sizeAt'], s['u']
    drag(page, h['size'], point([at[0] + 2 * (out[0] - at[0]), at[1] + 2 * (out[1] - at[1])]))
    s = surface_now(page, wall, 'faces')
    assert abs(s['u'] - 2 * was) < was * 0.02 and s['u'] == s['v'], (s, was)
    key(page, 'Control+z')
    assert abs(surface_now(page, wall, 'faces')['u'] - was) < 1e-6, surface_now(page, wall, 'faces')
    # the ring under fine snap: its grip turned 40 degrees on the surface (clockwise on its axes) turns the pattern 45
    # the other way round the surface's axes, as the pointer went, about its corner, which stays put
    page.evaluate("viewer.setSnapMode('fine')")
    h = page.evaluate('viewer.textureHandles()')
    at, grip, phi = h['at'], h['turnAt'], math.radians(-40)
    off = [grip[0] - at[0], grip[1] - at[1]]
    to = [at[0] + off[0] * math.cos(phi) - off[1] * math.sin(phi), at[1] + off[0] * math.sin(phi) + off[1] * math.cos(phi)]
    drag(page, h['turn'], point(to))
    s = surface_now(page, wall, 'faces')
    assert s.get('turn') == 45, s
    stays = page.evaluate("""async ([id, corner]) => { const m = await import('/made_mapping.js');
      const w = viewer.wallState(id).generated.wall, s = w.mapping.surfaces.faces;
      return m.patternPoint(s, [w.x0, w.x1, w.z0, w.z1], [0, 0], corner); }""", [wall, h['corner']])
    assert all(abs(stays[k] - at[k]) < 1e-3 for k in (0, 1)), (h, stays)
    # the fields: a value as typed, one undo step each
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    page.locator('#texU').fill('64')
    page.locator('#texU').press('Enter')
    s = surface_now(page, wall, 'faces')
    assert s['u'] == 64 and abs(s['v'] - was) < 1e-6 and s['turn'] == 45, s
    page.locator('#texFlipU').check()
    assert surface_now(page, wall, 'faces').get('flipU') is True
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth + 2
    # Aligned to the world: the piece's place goes into its mesh's request
    page.locator('#texWorld').check()
    assert surface_now(page, wall, 'faces').get('world') is True
    mesh_ready(page, wall)
    mesh = page.evaluate('id => viewer.roots.get(id).userData.source.mesh', wall)
    assert '"mappingOrigin":{"faces":[' in mesh, mesh
    # Original takes the surface's mapping out (and the mapping with it); Reset surface the same
    page.locator('#texMode button[data-value="original"]').click()
    assert 'mapping' not in generated(page, wall)['wall'], generated(page, wall)
    assert page.evaluate('viewer.textureHandles()')['slide'] is None
    key(page, 'Control+z')
    assert surface_now(page, wall, 'faces').get('world') is True
    page.locator('#texReset').click()
    assert 'mapping' not in generated(page, wall)['wall'], generated(page, wall)
    # a floor: its top picked by clicking it from above, its underside from below, Tab back to the top
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', slab)
    page.wait_for_timeout(400)
    mesh_ready(page, slab)
    assert page.locator('#slabBox #texFold').count() == 1, 'the fold in the Floor section'
    alone_click(page, slab, page.evaluate('viewer.textureSurfaceAt("top")'))
    assert page.evaluate('viewer.texturePicked()')['role'] == 'top', page.evaluate('viewer.texturePicked()')
    box = page.evaluate('id => viewer.pieceBox(id)', slab)
    middle = [(box[0] + box[1]) / 2, (box[2] + box[3]) / 2, box[4]]
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 260, c[2] - 120, c[1] + 260);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", middle)
    page.wait_for_timeout(300)
    alone_click(page, slab, page.evaluate('viewer.textureSurfaceAt("underside")'))
    assert page.evaluate('viewer.texturePicked()')['role'] == 'underside', page.evaluate('viewer.texturePicked()')
    key(page, 'Tab')
    assert page.evaluate('viewer.texturePicked()')['role'] == 'top', page.evaluate('viewer.texturePicked()')
    assert not page.evaluate('viewer.gizmo.controls.enabled'), 'the gizmo still aside on the floor picked with the fold open'
    # the fold shut: no surface picked, the size handles and the gizmo back
    page.locator('#texFold > summary').click()
    page.wait_for_function('viewer.texturePicked() === null')
    assert page.evaluate('viewer.wallHandles()'), 'the size handles back once the fold is shut'
    assert page.evaluate('viewer.gizmo.controls.enabled'), 'the gizmo back once the fold is shut'
    page.close()
    assert not errors, errors
    return dict(surfaces=3, turn=45)
