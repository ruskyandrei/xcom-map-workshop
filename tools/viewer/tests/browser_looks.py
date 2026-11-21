"""Looks from any piece in the browser (custom geometry plan, M4c; chosen afterwards since the editing plan's E2; a
panel of its own since the look picker plan, P2), on a test server: run through browser_smoke.py --only looks (it draws
walls and a rock but saves nothing). It needs the walls and ground catalogues (tools/bake/looks/*.json).

A wall drawn from the Build menu is plain: request version 4, no look in its numbers, its Look row saying none chosen.
Its panel's Choose... opens the look picker, a panel over the view: a card for each catalogued wall look, each saying it
gives the piece its look, the cards in view drawing their sample's picture (kept by the server); the find box narrows
them. A card makes the wall again in its look where it stands: request version 3 with its look named by its donor, its
piece a copy of the card's donor placing; the look is remembered, and its card is first and ringed when the picker
opens again, the pictures drawn before showing from the server. Another card makes it again in that look, one undo
step; Plain makes it plain again, one undo step. The panel's Pick from the view, opened from another plain wall's
Choose..., gives that wall the look of the wall clicked in the view; the eyedropper (I) while the Build menu's Wall
draws takes the look of the wall clicked and draws in it. A rock's Choose... opens the ground looks with rocks for
samples, and a card gives the rock that material, its shape and seed kept."""
from browser_walls import PLAIN, build_menu, drag, ground_point, look_at, look_row, made_ids, start_build

CARDS = '.lookpicker .lookcard'


def cards(page):
    return page.evaluate("""s => [...document.querySelectorAll(s)].map(c => ({ key: c.dataset.key, map: c.dataset.map,
        name: c.querySelector('strong')?.textContent, title: c.title, current: c.classList.contains('current'),
        kept: Boolean(c.querySelector('.lookpic img')), drawn: Boolean(c.querySelector('.lookpic canvas')) }))""", CARDS)


def card(page, key):
    return page.locator(f'{CARDS}[data-key="{key}"]')


def generated(page, id):
    return page.evaluate('id => viewer.roots.get(id).userData.source.added.generated', id)


def choose(page, piece, kind='wall'):
    """The piece picked and its panel's Choose... clicked: the look picker opens, its cards listed."""
    page.evaluate('id => viewer.select(id)', piece)
    page.wait_for_selector(f'#{kind}LookChange:not([disabled])')
    page.locator(f'#{kind}LookChange').click()
    page.wait_for_function("([k, s]) => viewer.lookMode() === k && document.querySelectorAll(s).length > 0", arg=[kind, CARDS], timeout=60000)


def pictures(page, n=2):
    """Waits for `n` cards to show a picture (drawn or kept); gives their keys."""
    page.wait_for_function("n => viewer.lookPickerState()?.cards.filter(c => c.picture === 'shown').length >= n", arg=n, timeout=90000)
    return [c['key'] for c in page.evaluate('viewer.lookPickerState().cards') if c['picture'] == 'shown']


def remade(page, old, act, kind='fracWall'):
    """`act` makes piece `old` again (a card clicked, Plain, an eyedropper's click): waits for it to go (a made piece
    deleted leaves `roots`) and gives the piece standing in its place."""
    before = set(made_ids(page, kind))
    act()
    page.wait_for_function('id => !viewer.roots.get(id) || viewer.roots.get(id).userData.deleted', arg=old, timeout=90000)
    page.wait_for_function('n => viewer.gizmo.active && !n.includes(viewer.gizmo.active)', arg=sorted(before), timeout=30000)
    (new,) = set(made_ids(page, kind)) - before
    return new


def undone(page, back):
    """Ctrl+Z: piece `back` stands again, the one made in its place gone."""
    page.keyboard.press('Control+z')
    page.wait_for_function('id => viewer.roots.get(id) && !viewer.roots.get(id).userData.deleted', arg=back, timeout=30000)


def from_above(page, c):
    page.evaluate("""c => { viewer.controls.target.set(c[0], c[2], c[1]); viewer.camera.position.set(c[0] + 1, c[2] + 1400, c[1] + 1);
      viewer.camera.lookAt(c[0], c[2], c[1]); viewer.controls.update(); }""", c)
    page.wait_for_timeout(300)      # (a frame drawn from where the camera was put: screenOf reads its matrices)


def check_looks(browser, url, open_viewer, at=(-1200.0, -2200.0, 16.0), start=(-1344.0, -2208.0, 16.0), end=(-960.0, -2208.0, 16.0)):
    errors = []
    page = open_viewer(browser, url, errors)
    # (the points above are on the police station's ground: on another map they mean nothing)
    assert page.evaluate('viewer.mapId') == 'URB_PoliceStation', f"open the police station (?map=URB_PoliceStation), not {page.evaluate('viewer.mapId')}"
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
    # its panel's Choose... opens the picker: a panel over the view, every card saying it gives the piece its look
    choose(page, drawn)
    assert page.locator('.lookpicker').is_visible() and not page.locator('#libAll').is_visible()
    listed = cards(page)
    out['cards'] = len(listed)
    assert all('click to give the piece this look' in c['title'] for c in listed), listed[:3]
    assert 'looks' in page.locator('.lookpicker .lookstatus').inner_text(), page.locator('.lookpicker .lookstatus').inner_text()
    # the cards in view draw their sample's picture
    shown = pictures(page)
    out['pictures'] = len(shown)
    # the find box narrows them by the look's name
    word = listed[0]['name'].split('_')[0][:6].lower()
    page.locator('.lookpicker input[type=search]').fill(word)       # (the cards are laid again in its input listener)
    narrowed = cards(page)
    assert narrowed and len(narrowed) < len(listed) and word in narrowed[0]['name'].lower() + narrowed[0]['title'].lower(), (word, narrowed[:3])
    page.locator('.lookpicker input[type=search]').fill('')
    # a card (one not listed first: the look chosen is listed first afterwards) makes the wall again in its look where
    # it stands: version 3, its look named by its donor, its piece a copy of the card's donor placing; the panel closes
    listed = cards(page)
    first = next(c for c in listed if c['name'] != listed[0]['name'])
    wall = remade(page, drawn, lambda: card(page, first['key']).click())
    assert page.evaluate('viewer.lookMode()') is None and not page.locator('.lookpicker').is_visible()
    donor = page.evaluate("viewer.storedLook('wall')?.donor")
    g = generated(page, wall)
    assert donor and g['version'] == 3 and g['wall']['look'] == donor and donor['mesh'] == first['key'], (g, donor, first)
    # (its numbers kept; storeys as its look's: a one-storey look's wall is one storey)
    assert all(g['wall'][k] == place['generated']['wall'][k] for k in ('x0', 'x1', 'openings', 'seed')), (g, place)
    now = page.evaluate('id => viewer.wallState(id)', wall)
    assert now['location'] == place['location'] and now['rotation'] == place['rotation'], (now, place)
    source = page.evaluate('id => viewer.roots.get(id).userData.source.added.from', wall)
    assert source['package'].lower() == first['map'].lower(), (source, first)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent !== 'Look: none chosen'", timeout=30000)
    assert look_row(page, 'wall') == dict(name=f'Look: {first["name"]}', plain=True, choose=True), (look_row(page, 'wall'), first)
    out['chosen'] = dict(version=g['version'], look=g['wall']['look']['mesh'], tiles=g['wall']['x1'] / 96)
    # Choose... again: the look chosen is first and ringed, the pictures drawn before shown from the server; another
    # card makes it again in that look, one undo step
    choose(page, wall)
    page.wait_for_function("([s, keys]) => keys.every(k => document.querySelector(`${s}[data-key=\"${k}\"] .lookpic img`))",
                           arg=[CARDS, shown], timeout=15000)
    listed = cards(page)
    assert listed[0]['name'] == first['name'] and listed[0]['current'], ([c['name'] for c in listed[:5]], first['name'])
    other = next((c for c in listed if c['name'] != first['name']), None)
    if other:
        changed = remade(page, wall, lambda: card(page, other['key']).click())
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
    # (its numbers as in the look, its storeys kept: the default look is two storeys, so a one-storey look's wall says
    # storeys 1)
    p = generated(page, plain)
    same = lambda w: {k: v for k, v in w.items() if k not in ('look', 'storeys')}
    assert p['version'] == PLAIN['fracWall'] and same(p['wall']) == same(g['wall']), (p, g)
    page.wait_for_function("() => document.getElementById('wallLookName').textContent === 'Look: none chosen'", timeout=30000)
    assert not page.locator('#wallLookPlain').is_enabled()
    undone(page, wall)
    assert generated(page, wall)['wall']['look'] == donor and made_ids(page, 'fracWall') == [wall], made_ids(page, 'fracWall')
    # the panel's Pick from the view: a second plain wall, south of the first (drawn seen from straight above), takes
    # the look of the first, clicked in the view
    south = [[start[0] + 96, start[1] - 192, start[2]], [start[0] + 288, start[1] - 192, start[2]]]
    start_build(page, 'wall')
    from_above(page, [(south[0][k] + south[1][k]) / 2 for k in range(3)])
    drag(page, ground_point(page, south[0]), ground_point(page, south[1]))
    page.wait_for_function('n => viewer.gizmo.active && !n.includes(viewer.gizmo.active) && viewer.wallState(viewer.gizmo.active)',
                           arg=[wall], timeout=60000)
    (second,) = set(made_ids(page, 'fracWall')) - {wall}
    assert generated(page, second)['version'] == PLAIN['fracWall'], generated(page, second)
    choose(page, second)
    page.locator('.lookpicker button', has_text='Pick from the view').click()
    page.wait_for_function("viewer.lookPicking()?.kind === 'wall' && viewer.lookMode() === null")
    look_at(page, list(at))
    # (nothing picked while it clicks: the picked wall's gizmo, drawn over the first wall from here, takes a click on it
    # as a move; the look still goes to the wall whose Choose... opened the picker)
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
    # a rock (south of the second wall): its Choose... opens the ground looks, its samples rocks; a card gives the rock
    # that material (the ground's donor version), its shape and seed kept, one undo step
    ra, rb = [start[0] + 96, start[1] - 384, start[2]], [start[0] + 288, start[1] - 480, start[2]]
    start_build(page, 'rock')
    from_above(page, [(ra[k] + rb[k]) / 2 for k in range(3)])
    drag(page, ground_point(page, ra), ground_point(page, rb))
    page.wait_for_function("viewer.gizmo.active && viewer.wallState(viewer.gizmo.active)?.generated.kind === 'ground'", timeout=60000)
    (rock,) = made_ids(page, 'ground')
    page.keyboard.press('Escape')
    r = generated(page, rock)
    assert r['ground']['shape'] == 'rock' and r['version'] == PLAIN['ground'], r
    choose(page, rock, 'ground')
    assert page.evaluate('viewer.lookPickerState().sample') == 'rock'
    pictures(page, 1)
    listed = cards(page)
    pick = listed[min(3, len(listed) - 1)]
    coloured = remade(page, rock, lambda: card(page, pick['key']).click(), kind='ground')
    r2 = generated(page, coloured)
    assert r2['version'] == 2 and r2['ground']['look']['mesh'] == pick['key'].split('|')[0], (r2, pick)
    assert {k: v for k, v in r2['ground'].items() if k != 'look'} == r['ground'], (r2, r)
    undone(page, rock)
    out['rock'] = dict(cards=len(listed), look=r2['ground']['look'])
    out['errors'] = sorted(errors)
    assert not errors, errors
    page.close()
    return out
