"""The bar's button for the map or the prefab that is open, its menu and the Open window with its Maps and Prefabs sides
(the prefab menus plan, stage M3), on a test server with fresh stores, never the main one: run through browser_smoke.py
--only open-window (it saves a prefab, so it needs --projects).

- In a map (Bar): the bar reads the logo, Project, Map; the menu holds This map with the map's items, Open's two buttons
  with their counts and New prefab, no Change map and no prefab's items. A map… and M open the window on Maps, A prefab…
  on Prefabs; the switch in each head crosses over, the focus on its lit half, the two sides the same size and place;
  Esc closes either and gives the focus back to the button. The Maps side lists no prefab and counts maps alone; the
  Prefabs side lists New prefab first and the library. With an unsaved edit New prefab asks to save, and Cancel leaves
  the map as it was. A piece copied in the map is placed by Ctrl+V in the prefab the window opens.
- In the builder: Project says None, the button Prefab and the prefab's name, with the unsaved mark after an edit; the
  Project menu holds Open… and the recent projects, no Save; Ctrl+O opens the window on Prefabs and marks the open
  prefab, M on Maps; Ctrl+S on a saved prefab saves it; the Add panel's first tab reads This prefab.
- With no map open (an address naming none listed): the window shows on Maps with its message, its switch leads to the
  prefabs, and New prefab there opens the builder.
- Narrow: at 1280, 1024 and 800 wide nothing is pushed out of the header, and the menu and the window stay in the page.
"""

import time

HEADER_OVER = "document.querySelector('header').scrollWidth - document.querySelector('header').clientWidth"
BOX = "s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"


def ready(page):
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)


def shown(page, selector):
    page.wait_for_selector(f'{selector}:not([hidden])')


def check_open_window(browser, url, open_viewer):
    base = url.split('?')[0]
    errors = []
    out = {}
    # ---- in a map
    page = open_viewer(browser, base + '?map=URB_Bar', errors)
    order = page.evaluate("[...document.querySelector('header').children].filter(e => !e.hidden && e.offsetParent).slice(0, 3).map(e => e.id || e.className)")
    assert order == ['brand', 'projectButton', 'mapButton'], order
    assert page.locator('#mapButton small').inner_text().strip().lower() == 'map'
    page.locator('#mapButton').click()
    shown(page, '#mapMenu')
    assert page.locator('#docHead').inner_text().strip().lower() == 'this map'
    labels = [t.strip() for t in page.locator('#mapItems button:visible span').all_inner_texts()]
    assert labels == ['Map settings…', 'Missions…', 'Map picture…', 'Map grid', 'Clear map…'], labels
    assert page.locator('#prefabItems').is_hidden() and page.locator('#mapChange').count() == 0
    page.wait_for_function("/^[0-9]+ prefabs?$/.test(document.getElementById('openPrefabsCount').textContent)")
    maps = page.evaluate("fetch('/maps.json').then(r => r.json()).then(j => j.maps.length)")
    assert page.locator('#openMapsCount').inner_text() == f'{maps} maps', page.locator('#openMapsCount').inner_text()
    # A map…: the Maps side, with no prefab in it and its count the maps'
    page.locator('#openMaps').click()
    shown(page, '#mapDialog')
    assert page.locator('#mapMenu').is_hidden()
    assert page.locator('#mapDialogTitle').inner_text() == 'Open'
    assert page.locator('#mapList .maprow[data-id^="prefab:"]').count() == 0
    assert page.locator('#mapGroups [data-group="prefabs"]').count() == 0
    assert page.locator('#mapCount').inner_text().startswith(f'{maps} of {maps} maps'), page.locator('#mapCount').inner_text()
    assert page.locator('#mapDialog .opensides button.on').get_attribute('data-side') == 'maps'
    maps_box = page.evaluate(BOX, '#mapForm')
    # the switch: Prefabs in the same place, the focus on its lit half; and back
    page.locator('#mapDialog .opensides button[data-side="prefabs"]').click()
    shown(page, '#openPrefabDialog')
    assert page.locator('#mapDialog').is_hidden()
    assert page.evaluate("document.activeElement?.closest('#openPrefabDialog .opensides') && document.activeElement.dataset.side") == 'prefabs'
    prefabs_box = page.evaluate(BOX, '#openPrefabForm')
    assert all(abs(a - b) <= 1 for a, b in zip(maps_box, prefabs_box)), (maps_box, prefabs_box)
    page.wait_for_function("document.querySelectorAll('#openPrefabCards .card').length >= 1")
    assert page.locator('#openPrefabCards .card').first.get_attribute('data-id') == 'new'
    listed = page.evaluate("fetch('/prefabs.json').then(r => r.json()).then(j => j.prefabs.filter(p => !p.error).length)")
    page.wait_for_function("n => document.querySelectorAll('#openPrefabCards .card:not(.newcard)').length === n", arg=listed)
    assert page.locator('#openPrefabPlace').is_visible()       # (placing is the Add panel's: said in a map)
    page.locator('#openPrefabDialog .opensides button[data-side="maps"]').click()
    shown(page, '#mapDialog')
    assert page.locator('#openPrefabDialog').is_hidden()
    assert page.evaluate("document.activeElement?.dataset?.side") == 'maps'
    page.keyboard.press('Escape')
    page.wait_for_selector('#mapDialog', state='hidden')
    assert page.evaluate('document.activeElement?.id') == 'mapButton', page.evaluate('document.activeElement?.id')
    # A prefab…: the Prefabs side; Esc closes it, the focus back on the button
    page.locator('#mapButton').click(); page.locator('#openPrefabs').click()
    shown(page, '#openPrefabDialog')
    page.keyboard.press('Escape')
    page.wait_for_selector('#openPrefabDialog', state='hidden')
    assert page.evaluate('document.activeElement?.id') == 'mapButton'
    # M: the Maps side
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('m')
    shown(page, '#mapDialog')
    page.keyboard.press('Escape')
    # New prefab with an unsaved edit asks to save; Cancel leaves the map as it was
    piece = page.evaluate("[...viewer.roots.values()].find(r => !r.userData.source.added && r.visible && !r.userData.source.hidden).userData.source.id")
    page.evaluate('document.activeElement.blur()')
    page.evaluate('id => viewer.select(id)', piece)
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.changes().total') == 1       # (a trial's edit, no project: leaving asks all the same)
    page.locator('#mapButton').click(); page.locator('#docNewPrefab').click()
    shown(page, '#leaveDialog')
    page.locator('#leaveCancel').click()
    page.wait_for_selector('#leaveDialog', state='hidden')
    assert page.evaluate("viewer.mapId") == 'URB_Bar' and page.evaluate('id => viewer.roots.get(id).userData.deleted', piece)
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    # a piece copied here comes along to the prefab the window opens (New prefab, then Open)
    page.evaluate('id => viewer.select(id)', piece)
    page.keyboard.press('Control+c')
    page.evaluate('viewer.select(null)')
    page.locator('#mapButton').click(); page.locator('#openPrefabs').click()
    shown(page, '#openPrefabDialog')
    page.locator('#openPrefabCards .card.newcard').click()
    assert page.locator('#openPrefabOk').inner_text() == 'New prefab'
    with page.expect_navigation(wait_until='load'):
        page.locator('#openPrefabOk').click()
    ready(page)
    assert page.evaluate('viewer.builderMode')
    page.wait_for_function("document.getElementById('dragHint').textContent.includes('The copy came along')")
    page.keyboard.press('Control+v')
    page.wait_for_function("viewer.placementProblem([0, 0, 0]) !== 'No placement'")
    page.keyboard.press('Escape')
    # ---- in the builder
    assert page.locator('#projectTitle').inner_text() == 'None'
    assert page.locator('#mapButton small').inner_text().strip().lower() == 'prefab'
    assert page.locator('#mapTitle').inner_text() == 'Untitled prefab'
    assert page.locator('#libScope [data-value="map"]').inner_text() == 'This prefab'
    page.evaluate('viewer.addVolumes([{ box: [0, 0, 0, 96, 96, 192], floor: 0 }])')
    page.wait_for_function("document.getElementById('mapButton').classList.contains('unsaved')")
    assert not page.locator('#projectButton').evaluate("b => b.classList.contains('unsaved')")
    page.locator('#projectButton').click()
    labels = [t.strip() for t in page.locator('#projectMenu .menuitems button:visible span').all_inner_texts()]
    assert labels == ['Open…'], labels
    assert page.locator('#projectRecent').is_visible()
    page.keyboard.press('Escape')
    # saved through the menu's Save as…, then Ctrl+S saves its next revision
    page.locator('#mapButton').click(); page.locator('#docPrefabSaveAs').click()
    shown(page, '#prefabDialog')
    name = f'Open window check {time.time_ns()}'      # (a name no earlier run left in the library)
    page.locator('#prefabName').fill(name)
    page.locator('#prefabOk').click()
    page.wait_for_function("name => document.getElementById('mapTitle').textContent === name && !document.getElementById('mapButton').classList.contains('unsaved')", arg=name)
    saved = page.evaluate("viewer.builderDocument().id")
    page.evaluate('viewer.addVolumes([{ box: [96, 0, 0, 192, 96, 192], floor: 0 }])')
    page.wait_for_function("document.getElementById('mapButton').classList.contains('unsaved')")
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('Control+s')
    page.wait_for_function("id => fetch(`/prefabs/${id}/prefab.json`).then(r => r.json()).then(d => d.revision === 2)", arg=saved)
    page.wait_for_function("!document.getElementById('mapButton').classList.contains('unsaved')")
    # Export to a file…: the saved revision
    page.locator('#mapButton').click()
    assert page.locator('#docPrefabExport').is_enabled()
    with page.expect_download() as download:
        page.locator('#docPrefabExport').click()
    assert download.value.suggested_filename.endswith('.json')
    # Ctrl+O: the Prefabs side, the open prefab marked; M: the Maps side
    page.keyboard.press('Control+o')
    shown(page, '#openPrefabDialog')
    page.wait_for_function("id => document.querySelector(`#openPrefabCards .card[data-id='${id}'] .tag.open`)", arg=saved)
    assert page.locator('#openPrefabPlace').is_hidden()
    assert page.locator(f'#openPrefabCards .card[data-id="{saved}"]').evaluate("c => c.classList.contains('on')")
    page.keyboard.press('Escape')
    page.wait_for_selector('#openPrefabDialog', state='hidden')
    page.keyboard.press('m')
    shown(page, '#mapDialog')
    page.keyboard.press('Escape')
    out['saved'] = saved
    page.close()
    # ---- with no map open: the Maps side with the start message, its switch to the prefabs, New prefab
    page = browser.new_page(viewport=dict(width=1280, height=900))
    page.on('pageerror', lambda e: errors.append(str(e)))
    # (an address naming no listed map: the page opens nothing and shows the Maps side with its message, as it does
    # with no map at all; with no map named it opens the server's default map)
    page.goto(base + '?map=NoSuchMapForTheCheck')
    page.wait_for_selector('#mapDialog:not([hidden])', timeout=120000)
    assert 'No map called NoSuchMapForTheCheck' in page.locator('#mapMessage').inner_text(), page.locator('#mapMessage').inner_text()
    page.locator('#mapDialog .opensides button[data-side="prefabs"]').click()
    shown(page, '#openPrefabDialog')
    page.locator('#openPrefabCards .card.newcard').dblclick()
    page.wait_for_url('**prefab=new**', timeout=60000)
    ready(page)
    assert page.evaluate('viewer.builderMode')
    page.close()
    # ---- narrow: the header, the menu and the window inside the page at three widths
    page = open_viewer(browser, base + '?map=URB_Bar', errors)
    narrow = {}
    for width in (1280, 1024, 800):
        page.set_viewport_size(dict(width=width, height=800)); page.wait_for_timeout(200)
        over = page.evaluate(HEADER_OVER)
        page.locator('#mapButton').click()
        menu = page.evaluate(BOX, '#mapMenu')
        page.locator('#openPrefabs').click()
        shown(page, '#openPrefabDialog')
        window = page.evaluate(BOX, '#openPrefabForm')
        page.keyboard.press('Escape')
        assert over <= 0, (width, over)
        assert menu[2] <= width and menu[3] <= 800, (width, menu)
        assert window[0] >= 0 and window[2] <= width and window[3] <= 800, (width, window)
        narrow[width] = dict(menu=[round(v) for v in menu], window=[round(v) for v in window])
    out['narrow'] = narrow
    page.close()
    assert not errors, errors
    return out
