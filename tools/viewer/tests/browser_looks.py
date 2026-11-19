"""Looks from any piece in the browser (custom geometry plan, M4c; chosen afterwards since the editing plan's E2), on a
test server: run through browser_smoke.py --only looks (it draws walls but saves nothing). It needs the walls catalogue
(tools/bake/looks/walls.json) and the library's index of the install's maps (All maps).

A wall drawn from the Build menu is plain: request version 4, no look in its numbers, its Look row saying none chosen.
Its panel's Choose… opens All maps in look mode: only the pieces that are catalogued walls, each row saying it draws in
its look; the search narrows them. A row makes the wall again in its look where it stands: request version 3 with its
look named by its donor, its piece a copy of that row's placing; the look is remembered, and listed first when the
picker opens again. Choose… and another row make it again in that look, one undo step; Plain makes it plain again, one
undo step. The picker's Pick from the view, opened from another plain wall's Choose…, gives that wall the look of the
wall clicked in the view; the eyedropper (I) while the Build menu's Wall draws takes the look of the wall clicked and
draws in it."""
import re

from browser_walls import PLAIN, build_menu, drag, ground_point, look_at, look_row, made_ids, start_build


def rows(page):
    return page.evaluate("""[...document.querySelectorAll('#libAllList .libitem')].map(i => ({ key: i.dataset.key,
        name: i.querySelector('strong')?.textContent, title: i.title }))""")


def generated(page, id):
    return page.evaluate('id => viewer.roots.get(id).userData.source.added.generated', id)


def choose(page, wall):
    """The wall picked and its panel's Choose… clicked: the look picker opens, its rows listed."""
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#wallLookChange:not([disabled])')
    page.locator('#wallLookChange').click()
    page.wait_for_function("viewer.lookMode() === 'wall' && document.querySelectorAll('#libAllList .libitem').length > 0", timeout=60000)


def remade(page, old, act):
    """`act` makes wall `old` again (a row clicked, Plain, an eyedropper's click): waits for it to go (a made piece
    deleted leaves `roots`) and gives the wall standing in its place."""
    before = set(made_ids(page, 'fracWall'))
    act()
    page.wait_for_function('id => !viewer.roots.get(id) || viewer.roots.get(id).userData.deleted', arg=old, timeout=90000)
    page.wait_for_function('n => viewer.gizmo.active && !n.includes(viewer.gizmo.active)', arg=sorted(before), timeout=30000)
    (new,) = set(made_ids(page, 'fracWall')) - before
    return new


def undone(page, back):
    """Ctrl+Z: wall `back` stands again, the one made in its place gone."""
    page.keyboard.press('Control+z')
    page.wait_for_function('id => viewer.roots.get(id) && !viewer.roots.get(id).userData.deleted', arg=back, timeout=30000)


def check_looks(browser, url, open_viewer, at=(-1200.0, -2200.0, 16.0), start=(-1344.0, -2208.0, 16.0), end=(-960.0, -2208.0, 16.0)):
    errors = []
    page = open_viewer(browser, url, errors)
    page.evaluate("for (const k of ['workshop.wallLook', 'workshop.slabLook', 'workshop.groundLook']) localStorage.removeItem(k)")
    out = dict(map=page.evaluate('viewer.data.name'))
    # a wall from the Build menu: plain
    look_at(page, list(at))
    build_menu(page, 'wall')
    drag(page, ground_point(page, list(start)), ground_point(page, list(end)))
    page.wait_for_function("viewer.gizmo.active && viewer.wallState(viewer.gizmo.active)", timeout=60000)
    (drawn,) = made_ids(page, 'fracWall')
    g = generated(page, drawn)
    assert g['version'] == PLAIN['fracWall'] and 'look' not in g['wall'], g
    assert look_row(page, 'wall') == dict(name='Look: none chosen', plain=False, choose=True), look_row(page, 'wall')
    place = page.evaluate('id => viewer.wallState(id)', drawn)
    # its panel's Choose… opens the picker
    choose(page, drawn)
    listed = rows(page)
    out['rows'] = len(listed)
    assert all('click to draw in this look' in r['title'] for r in listed), listed[:3]
    assert 'look' in page.locator('#libAllFoot').inner_text(), page.locator('#libAllFoot').inner_text()
    # the search narrows them by the look's name
    word = listed[0]['name'].split('_')[0][:6].lower()
    page.locator('#libAllFilter').fill(word)
    page.wait_for_timeout(200)
    narrowed = rows(page)
    assert narrowed and all(word in (r['name'] + r['title']).lower() for r in narrowed), (word, narrowed[:3])
    page.locator('#libAllFilter').fill('')
    page.wait_for_timeout(200)
    # a row (one not listed first: the look chosen is listed first afterwards) makes the wall again in its look where
    # it stands: version 3, its look named by its donor, its piece a copy of the row's placing; the picker closes
    listed = rows(page)
    first = next(r for r in listed if r['name'] != listed[0]['name'])
    wall = remade(page, drawn, lambda: page.locator(f'#libAllList .libitem[data-key="{first["key"]}"]').click())
    assert page.evaluate('viewer.lookMode()') is None
    donor = page.evaluate("viewer.storedLook('wall')?.donor")
    g = generated(page, wall)
    assert donor and g['version'] == 3 and g['wall']['look'] == donor, (g, donor)
    # (its numbers kept; storeys as its look's: a one-storey look's wall is one storey)
    assert all(g['wall'][k] == place['generated']['wall'][k] for k in ('x0', 'x1', 'openings', 'seed')), (g, place)
    now = page.evaluate('id => viewer.wallState(id)', wall)
    assert now['location'] == place['location'] and now['rotation'] == place['rotation'], (now, place)
    brought = re.search(r'brought from (\S+)', first['title']).group(1)
    source = page.evaluate('id => viewer.roots.get(id).userData.source.added.from', wall)
    assert source['package'].lower() == brought.lower(), (source, brought)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent !== 'Look: none chosen'", timeout=30000)
    assert look_row(page, 'wall') == dict(name=f'Look: {first["name"]}', plain=True, choose=True), (look_row(page, 'wall'), first)
    out['chosen'] = dict(version=g['version'], look=g['wall']['look']['mesh'], tiles=g['wall']['x1'] / 96)
    # Choose… again: the look chosen is listed first; another row makes it again in that look, one undo step
    choose(page, wall)
    listed = rows(page)
    assert listed[0]['name'] == first['name'], ([r['name'] for r in listed[:5]], first['name'])
    other = next((r for r in listed if r['name'] != first['name']), None)
    if other:
        changed = remade(page, wall, lambda: page.locator(f'#libAllList .libitem[data-key="{other["key"]}"]').click())
        g2 = generated(page, changed)
        assert g2['version'] == 3 and g2['wall']['look']['mesh'] != donor['mesh'], g2
        undone(page, wall)
        assert generated(page, wall)['wall']['look'] == donor and made_ids(page, 'fracWall') == [wall], made_ids(page, 'fracWall')
        out['changed'] = g2['wall']['look']['mesh']
    else:
        page.keyboard.press('Escape')
    # Plain: made plain again where it stands (version 4, no look), one undo step
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#wallLookPlain:not([disabled])')
    plain = remade(page, wall, lambda: page.locator('#wallLookPlain').click())
    # (its numbers as in the look, storeys too: the default look the Build makes it in can be one storey)
    p = generated(page, plain)
    assert p['version'] == PLAIN['fracWall'] and p['wall'] == {k: v for k, v in g['wall'].items() if k != 'look'}, (p, g)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent === 'Look: none chosen'", timeout=30000)
    assert not page.locator('#wallLookPlain').is_enabled()
    undone(page, wall)
    assert generated(page, wall)['wall']['look'] == donor and made_ids(page, 'fracWall') == [wall], made_ids(page, 'fracWall')
    # the picker's Pick from the view: a second plain wall, south of the first (drawn seen from straight above), takes
    # the look of the first, clicked in the view
    south = [[start[0] + 96, start[1] - 192, start[2]], [start[0] + 288, start[1] - 192, start[2]]]
    start_build(page, 'wall')
    middle = [(south[0][k] + south[1][k]) / 2 for k in range(3)]
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 1, c[2] + 1400, c[1] + 1);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", middle)
    page.wait_for_timeout(300)
    drag(page, ground_point(page, south[0]), ground_point(page, south[1]))
    page.wait_for_function('n => viewer.gizmo.active && !n.includes(viewer.gizmo.active) && viewer.wallState(viewer.gizmo.active)',
                           arg=[wall], timeout=60000)
    (second,) = set(made_ids(page, 'fracWall')) - {wall}
    assert generated(page, second)['version'] == PLAIN['fracWall'], generated(page, second)
    choose(page, second)
    page.locator('#libAll .lookbanner button', has_text='Pick from the view').click()
    page.wait_for_function("viewer.lookPicking()?.kind === 'wall' && viewer.lookMode() === null")
    look_at(page, list(at))
    # (nothing picked while it clicks: the picked wall's gizmo, drawn over the first wall from here, takes a click on it
    # as a move; the look still goes to the wall whose Choose… opened the picker)
    page.evaluate('viewer.select(null)')
    mid = [(start[k] + end[k]) / 2 for k in range(3)]
    mid[2] += 120
    taken = remade(page, second, lambda: page.mouse.click(*ground_point(page, mid)))
    g3 = generated(page, taken)
    assert g3['version'] == 3 and g3['wall']['look'] == donor and g3['wall']['x1'] == 192, g3
    assert not page.evaluate('viewer.lookPicking()')
    out['picked'] = g3['wall']['look']['mesh']
    # the eyedropper (I) while the Build menu's Wall draws: the look of the wall clicked, drawn in at once
    start_build(page, 'wall')
    page.keyboard.press('i')
    page.wait_for_function("viewer.lookPicking()?.kind === 'wall' && !viewer.wallDrawing()")
    page.evaluate('viewer.select(null)')
    page.mouse.click(*ground_point(page, mid))
    page.wait_for_function('viewer.wallDrawing()?.donor || !viewer.lookPicking()', timeout=30000)
    picked = page.evaluate('viewer.wallDrawing()?.donor ?? null')
    assert picked == donor, picked
    out['eyedropper'] = picked['mesh']
    page.keyboard.press('Escape')
    out['errors'] = sorted(errors)
    assert not errors, errors
    page.close()
    return out
