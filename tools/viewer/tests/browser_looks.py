"""Looks from any piece in the browser (custom geometry plan, M4c), on a test server: run through browser_smoke.py
--only looks (it draws walls but saves nothing). It needs the walls catalogue (tools/bake/looks/walls.json) and the
library's index of the install's maps (All maps).

The Walls kind's Choose a wall look opens All maps in look mode: only the pieces that are catalogued walls, each row
saying it draws in its look; the search narrows them. A row starts drawing in its look; a wall dragged out carries
request version 3 with its look named by its donor, and its piece is a copy of that row's placing. The wall panel's
Look… opens the picker again, and another row makes the wall again in that look where it stands, one undo step. The
eyedropper (I) takes the look of the wall clicked in the view. The look chosen is the Walls kind's from then on."""
from browser_walls import drag, ground_point, look_at, wall_ids


def rows(page):
    return page.evaluate("""[...document.querySelectorAll('#libAllList .libitem')].map(i => ({ key: i.dataset.key,
        name: i.querySelector('strong')?.textContent, title: i.title }))""")


def check_looks(browser, url, open_viewer, at=(-1200.0, -2200.0, 16.0), start=(-1344.0, -2208.0, 16.0), end=(-960.0, -2208.0, 16.0)):
    errors = []
    page = open_viewer(browser, url, errors)
    page.evaluate("for (const k of ['workshop.wallLook', 'workshop.slabLook', 'workshop.groundLook']) localStorage.removeItem(k)")
    out = dict(map=page.evaluate('viewer.data.name'))
    # the Walls kind's Choose a wall look opens the picker
    page.keyboard.press('p')
    page.wait_for_selector('#libMap .libitem')
    page.locator('#libFilter').fill('choose a wall look')
    page.locator('#libMap .libitem[data-id="looks-wall"]').click()
    page.wait_for_function("viewer.lookMode() === 'wall' && document.querySelectorAll('#libAllList .libitem').length > 0", timeout=60000)
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
    # a row starts drawing in its look; the picker closes
    first = rows(page)[0]
    page.locator(f'#libAllList .libitem[data-key="{first["key"]}"]').click()
    page.wait_for_function('viewer.wallDrawing()?.ready && viewer.wallDrawing().donor', timeout=90000)
    donor = page.evaluate('viewer.wallDrawing().donor')
    assert page.evaluate('viewer.lookMode()') is None
    assert page.evaluate("viewer.storedLook('wall')?.donor?.mesh") == donor['mesh']
    entries = page.evaluate('viewer.wallEntries().map(e => e.wallLook?.donor?.mesh ?? e.lookPicker)')
    assert entries[:2] == [donor['mesh'], donor['mesh']] and entries[-1] == 'wall', entries
    # dragged out: request version 3, its look named by its donor
    if page.locator('#libAll').is_visible(): page.keyboard.press('p')
    if not page.evaluate('viewer.wallDrawing()'):
        page.evaluate("viewer.startWallDrawing(viewer.wallEntries()[0].wallLook)")
        page.wait_for_function('viewer.wallDrawing()?.ready', timeout=90000)
    look_at(page, list(at))
    before = set(wall_ids(page))
    drag(page, ground_point(page, list(start)), ground_point(page, list(end)))
    page.wait_for_function('n => viewer.roots.size && [...viewer.roots.values()].filter(r => r.userData.source.added?.generated?.kind === "fracWall").length > n',
                           arg=len(before), timeout=30000)
    (wall,) = set(wall_ids(page)) - before
    g = page.evaluate('id => viewer.roots.get(id).userData.source.added.generated', wall)
    assert g['version'] == 3 and g['wall']['look'] == donor, g
    out['drawn'] = dict(version=g['version'], look=g['wall']['look']['mesh'], tiles=g['wall']['x1'] / 96)
    page.keyboard.press('Escape')
    # Look… makes it again in another look where it stands, one undo step
    page.evaluate('id => viewer.select(id)', wall)
    page.wait_for_selector('#wallLookChange:not([disabled])')
    page.locator('#wallLookChange').click()
    page.wait_for_function("viewer.lookMode() === 'wall'", timeout=30000)
    other = next((r for r in rows(page) if r['name'] != first['name']), None)
    if other:
        page.locator(f'#libAllList .libitem[data-key="{other["key"]}"]').click()
        page.wait_for_function('n => [...viewer.roots.values()].filter(r => !r.userData.deleted && r.userData.source.added?.generated?.wall?.look?.mesh && r.userData.source.added.generated.wall.look.mesh !== n).length === 1',
                               arg=donor['mesh'], timeout=60000)
        now = [i for i in wall_ids(page) if not page.evaluate('id => viewer.roots.get(id).userData.deleted', i)]
        changed = page.evaluate('ids => ids.map(id => viewer.roots.get(id).userData.source.added.generated.wall.look.mesh)', now)
        assert donor['mesh'] not in changed, changed
        page.keyboard.press('Control+z')
        page.wait_for_function('id => !viewer.roots.get(id).userData.deleted', arg=wall, timeout=30000)
        out['changed'] = changed
    else:
        page.keyboard.press('Escape')
    # the eyedropper takes the look of the wall clicked
    page.evaluate("viewer.openLookPicker('wall')")
    page.wait_for_function("viewer.lookMode() === 'wall'")
    page.keyboard.press('i')
    page.wait_for_function("viewer.lookPicking()?.kind === 'wall'")
    page.evaluate('viewer.stopWallDrawing()')
    page.evaluate('id => viewer.select(null)')
    mid = [(start[k] + end[k]) / 2 for k in range(3)]
    mid[2] += 120
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
