"""The Diagonal cover view in the browser (private/plans/done/diagonal-cover-by-hand-and-views-plan.md, stages M3 and
M5; KNOWN-BUGS.md KB-20), on a test server: run through browser_smoke.py --only diagonal (it opens CsmallScout_Farm,
whose scout has eight marked corners, on a page of its own: the server exports it the first time).

The rail's Views list has the Diagonal cover row (Shift+C); on, the Views button shows its icon and the other views are
off. It behaves as the other views do (the user, 23 November 2026): hovering a tile adds nothing. On the scout's corner
(39, 12, 0), cut to its first floor: a click picks the mark (its gizmo and its four corner dots shown, the panel's
chip); a click on a corner dot gives it that corner too (one undo step: the project's own mark with its home, the edit
count, the panel's corner buttons, two on); undo and redo; ] turns its corners a quarter; the gizmo's X arrow dragged
moves it by whole tiles, whatever Snap says (Moved, its home named), and Reset puts it back, picked at home; Delete
deletes it (pale with Deleted marks, picked: Deleted, Reset); the Add panel's Diagonal cover entry and a click on an
empty tile add a mark there, toward the corner nearest the click; Escape lets the picked go; Shift+C leaves the view
and Shift+L turns it off for the Lights view; a piece selected from a list leaves it. Then the marks follow their
pieces (stage M5): the hull chunk moved, turned a quarter and 30 degrees, and deleted."""


def check_diagonal(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url.split('?')[0] + '?map=CSmallScout_Farm', errors)
    if page.evaluate('viewer.data.name').lower() != 'csmallscout_farm':
        page.close()
        return dict(skipped='CsmallScout_Farm is not in the install')
    marks = page.evaluate('viewer.diagonalMarks().map(m => m.key)')
    assert '39,12,0' in marks and len(marks) == 8, marks
    # the view: its row in the Views list (the list stays up while the pointer goes from the button to the row in small
    # steps, over the gap between them: it closed there once), the button's icon, the other views off
    page.evaluate('viewer.setLightsShown(true)')
    b, r = page.locator('#viewsButton').bounding_box(), None
    page.mouse.move(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
    r = page.locator('#editDiagonal').bounding_box()
    page.mouse.move(r['x'] + 30, r['y'] + r['height'] / 2, steps=25)
    assert page.locator('#viewsFlyout').is_visible()
    page.mouse.click(r['x'] + 30, r['y'] + r['height'] / 2)
    assert page.evaluate('viewer.diagonalOn() && !viewer.lightsOn()')
    page.keyboard.press('Shift+C'); page.keyboard.press('Shift+C')       # (its key: off and on again)
    assert page.evaluate('viewer.diagonalOn()')
    assert page.locator('#viewsIcon').get_attribute('href') == '#i-diag'
    assert page.locator('#editDiagonal').get_attribute('aria-pressed') == 'true'
    # the scout's corner seen from above, its first floor cut
    page.evaluate("""() => { viewer.controls.target.set(1295, -117, -2353); viewer.camera.position.set(1375, 350, -2653);
                             viewer.controls.update(); }""")
    # (the Floor picker's buttons come once the map's buildings are read)
    page.wait_for_selector('#floor button[data-value="1"]', state='visible', timeout=60000)
    page.locator('#floor button[data-value="1"]').click()
    page.wait_for_timeout(400)

    def at(tile, corner=None, z=-116.95):
        x, y = page.evaluate('([t, z, c]) => viewer.clientAt(viewer.diagonalPoint(t, z, c))', [tile, z, corner])
        return x, y

    def click(tile, corner=None, z=-116.95):
        x, y = at(tile, corner, z)
        page.mouse.move(x, y); page.mouse.click(x, y)

    hand = 'viewer.diagonalHand()'
    # hovering an empty tile and clicking it adds nothing, picks nothing
    click([37, 13, 0], 1)
    assert page.evaluate(hand) is None and page.evaluate('viewer.pickedMarks()') == []
    # a click picks the scout's mark: its gizmo and its panel
    click([39, 12, 0])
    assert page.evaluate('viewer.pickedMarks()') == ['39,12,0']
    assert page.evaluate('viewer.diagonalGizmo().shown') and page.locator('#diagonalChip').text_content() == "Map's own"
    # its corner dot (corner 3: [1, 1]; its own is [-1, -1]) gives it that corner too
    click([39, 12, 0], 3)
    h = page.evaluate(hand)
    assert h['marks'] == [dict(at=[1295, -2353, -97], toward=[[-1, -1], [1, 1]], **{'from': [1295, -2353, -97]})], h
    assert page.evaluate('viewer.changes().diagonal') == 1
    assert page.locator('#diagonalChip').text_content() == 'Changed'
    assert page.locator('#diagonalCorners button').count() == 4 and page.locator('#diagonalCorners button.on').count() == 2
    page.keyboard.press('Control+z')
    assert page.evaluate(hand) is None
    page.keyboard.press('Control+y')
    assert page.evaluate(hand)['marks'][0]['toward'] == [[-1, -1], [1, 1]]
    # ] turns its corners a quarter (clockwise in game axes): [-1, -1] and [1, 1] to [-1, 1] and [1, -1]
    page.keyboard.press(']')
    assert page.evaluate(hand)['marks'][0]['toward'] == [[-1, 1], [1, -1]], page.evaluate(hand)
    page.keyboard.press('Control+z')
    # Cover: full, as the scout's mark is; Half makes both its corners half cover, one undo step
    assert page.locator('#diagonalHeight').input_value() == 'full'
    page.locator('#diagonalHeight').select_option('half')
    h = page.evaluate(hand)
    assert h['marks'][0]['low'] == [[-1, -1], [1, 1]] == h['marks'][0]['toward'], h
    assert page.locator('#diagonalHeight').input_value() == 'half'
    page.keyboard.press('Control+z')
    assert 'low' not in page.evaluate(hand)['marks'][0] and page.locator('#diagonalHeight').input_value() == 'full'
    # the gizmo's X arrow dragged: whole tiles along x, whatever Snap says (here off); Reset puts it back, picked at home
    page.evaluate("viewer.setSnapMode('off')")
    g = page.evaluate('viewer.diagonalGizmo()')
    p0 = page.evaluate('p => viewer.screenOf(p)', g['at'])
    px = page.evaluate('p => viewer.screenOf([p[0] + 100, p[1], p[2]])', g['at'])
    n = ((px[0] - p0[0]) ** 2 + (px[1] - p0[1]) ** 2) ** 0.5
    d = [(px[0] - p0[0]) / n, (px[1] - p0[1]) / n]
    for r in range(8, 160, 3):
        pt = [p0[0] + d[0] * r, p0[1] + d[1] * r]
        page.mouse.move(*pt)
        if page.evaluate('viewer.diagonalGizmo().axis') == 'X':
            break
    else:
        raise AssertionError("the mark gizmo's X handle not found")
    tile_px = n * 0.96            # (a tile is 96 units: the screen length of 100 units, less a little)
    page.mouse.down(); page.mouse.move(pt[0] + d[0] * tile_px * 2.2, pt[1] + d[1] * tile_px * 2.2, steps=12); page.mouse.up()
    kinds = page.evaluate("viewer.diagonalMarks().filter(m => m.kind !== 'map').map(m => m.key + ':' + m.kind)")
    assert kinds == ['41,12,0:moved'], kinds
    assert page.locator('#diagonalChip').text_content() == 'Moved' and 'tile 39, 12' in page.locator('#diagonalWhere').text_content()
    page.locator('#diagonalReset').click()
    assert page.evaluate(hand) is None and page.evaluate('viewer.pickedMarks()') == ['39,12,0']
    # Delete: deleted, drawn pale with Deleted marks, picked there: Deleted, Delete off, Reset on
    page.keyboard.press('Delete')
    assert page.evaluate(hand) == dict(marks=[], removed=[[1295, -2353, -97]])
    page.evaluate("document.getElementById('diagonalShowDeleted').click()")
    click([39, 12, 0])
    assert page.locator('#diagonalChip').text_content() == 'Deleted'
    assert page.locator('#diagonalDelete').is_disabled() and page.locator('#diagonalReset').is_visible()
    page.locator('#diagonalReset').click()
    assert page.evaluate(hand) is None
    # the Add panel's Diagonal cover: a click on an empty tile near its corner [1, -1] adds a mark there, picked
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('p')
    page.wait_for_selector('#library:not([hidden])')
    if page.locator('#libMap').is_hidden(): page.locator('#libScope button[data-value="map"]').click()
    page.locator('#libKind').select_option('diagonal')
    entry = page.locator('#libList .libitem[data-id="diagonal-new"]')
    assert entry.count() == 1 and 'Diagonal cover' in entry.inner_text()
    entry.click()
    x, y = at([37, 13, 0], 1)
    page.mouse.move(x, y); page.mouse.click(x, y)
    state = page.evaluate('viewer.editState().diagonalCover')
    assert state and len(state['marks']) == 1 and state['marks'][0]['toward'] == [[1, -1]] and 'from' not in state['marks'][0], state
    assert page.locator('#diagonalChip').text_content() == 'Added' and page.evaluate('viewer.pickedMarks()') == ['37,13,0']
    page.locator('#libKind').select_option('all')
    page.keyboard.press('p')
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.pickedMarks()') == [] and page.locator('#diagonalPanel').is_hidden()
    # Shift+C leaves the view; on again, Shift+L turns it off for the Lights view; a piece picked from a list leaves it
    page.keyboard.press('Shift+C')
    assert not page.evaluate('viewer.diagonalOn()') and page.locator('#viewsIcon').get_attribute('href') == '#i-normal'
    page.keyboard.press('Shift+C'); page.keyboard.press('Shift+L')
    assert page.evaluate('viewer.lightsOn() && !viewer.diagonalOn()')
    page.evaluate('viewer.setLightsShown(false)'); page.evaluate('viewer.setDiagonalShown(true)')
    piece = page.evaluate('[...viewer.roots.keys()][0]')
    page.evaluate('id => viewer.select(id)', piece)
    assert not page.evaluate('viewer.diagonalOn()')
    page.keyboard.press('Control+z')         # (the mark added, taken back: the page is left as it opened)
    # marks follow their pieces (stage M5, export 40's walls): the hull chunk XComLevelActor_3 makes the corners (39, 12)
    # and (41, 10); moved two tiles along x and one along y, they go with it; turned a quarter, their corner turns; a
    # turn of 30 degrees leaves the diagonals (skew); deleted, they go; the project names them for the Build
    walls = page.evaluate("viewer.data.tactical.diagonalCover.map(t => t.directions[0].wall?.split('.').pop())")
    assert walls[0] == 'XComLevelActor_3', walls
    chunk = page.evaluate("[...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComLevelActor_3') && !r.userData.source.added).userData.source.id")
    page.evaluate('id => viewer.select(id)', chunk)
    pose = page.evaluate('viewer.gizmo.pose()')
    page.evaluate('l => viewer.gizmo.setPose(l, null)', [pose['location'][0] + 192, pose['location'][1] + 96, pose['location'][2]])
    carried = "viewer.diagonalMarks().filter(m => m.kind === 'carried').map(m => m.key + ':' + m.toward.map(c => c.join('/')).join('+') + (m.skew ? ':skew' : '')).sort()"
    assert page.evaluate(carried) == ['41,13,0:-1/-1', '43,11,0:-1/-1'], page.evaluate(carried)
    saved = page.evaluate('viewer.editState().diagonalCover')
    assert sorted(m['by'].rsplit('.', 1)[-1] for m in saved['marks']) == ['XComLevelActor_3'] * 2 and all(m.get('moves') for m in saved['marks']), saved
    page.evaluate('r => viewer.gizmo.setPose(null, r)', [pose['rotation'][0], pose['rotation'][1] + 90, pose['rotation'][2]])
    assert all(k.endswith(':1/-1') for k in page.evaluate(carried)), page.evaluate(carried)
    page.evaluate('r => viewer.gizmo.setPose(null, r)', [pose['rotation'][0], pose['rotation'][1] + 30, pose['rotation'][2]])
    assert all(k.endswith(':skew') for k in page.evaluate(carried)), page.evaluate(carried)
    page.keyboard.press('Delete')
    assert page.evaluate(carried) == [] and '39,12,0' not in page.evaluate('viewer.diagonalMarks().map(m => m.key)')
    assert all(m.get('gone') for m in page.evaluate('viewer.editState().diagonalCover')['marks'])
    for _ in range(4):
        page.keyboard.press('Control+z')
    assert page.evaluate(carried) == [] and page.evaluate('viewer.editState().diagonalCover') is None
    assert not errors, errors
    page.close()
    return dict(marks=len(marks))
