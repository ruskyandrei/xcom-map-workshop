"""Cache everything's pictures in the browser (precache_pictures.js), on a test server with a scratch cache (it puts
pictures into the cache it serves): run through browser_smoke.py --only precache-pictures. It needs the library read
(viewer.py library scan) and the walls, slabs and ground catalogues.

Settings' Cache everything... has a third option, every look's and piece's picture, ticked, its line counting what there
is to draw. A few looks' samples and a few pieces' and effects' pictures are drawn through the job (viewer's
precachePictures, limited to them): each is then kept by the server, and the page's tables (meshes, materials, textures,
pieces' records) hold no more than before, what the drawing loaded let go. Counted again, the line has that many fewer
to draw. With only the pictures ticked, Start shows their bar and says the page draws them; Cancel stops them, the
window saying the pictures drawn stay. With the pieces ticked too (where the server has read every piece already),
the pictures start once the server's job has read them."""

NOTE = '#cachePicturesNote'


def counts(page):
    plan = page.evaluate('viewer.precachePictures.plan()')
    return dict(looks=plan['looks']['missing'], pieces=plan['pieces']['missing'], total=plan['looks']['total'] + plan['pieces']['total'],
                ready=plan['pieces']['ready'], errors=plan['errors'])


def run_limited(page, types, limit):
    """The job started on the first `limit` items of `types`, waited for: its state."""
    page.evaluate('([types, limit]) => viewer.precachePictures.start({ types, limit })', [types, limit])
    page.wait_for_function("viewer.precachePictures.state().state !== 'running'", timeout=240000)
    return page.evaluate('viewer.precachePictures.state()')


def check_precache_pictures(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    out = dict(map=page.evaluate('viewer.data.name'))
    # the window: a third option, ticked, counting what there is to draw
    page.locator('#settingsButton').click()
    page.locator('#projectCache').click()
    page.wait_for_function("s => !document.querySelector(s).textContent.startsWith('Counting')", arg=NOTE, timeout=120000)
    assert page.locator('#cachePictures').is_checked() and page.locator('#cachePictures').is_enabled()
    note = page.locator(NOTE).inner_text()
    before = counts(page)
    assert before['ready'], f'the library is not read on this server: {before}'
    assert before['looks'] + before['pieces'] > 0, f'nothing to draw: give the check a cache whose pictures are not all drawn ({before})'
    assert 'pictures to draw' in note and 'drawn in this page' in note, note
    out['plan'] = before
    tables = page.evaluate('viewer.pageTables()')
    # a few of each, drawn: kept by the server, the tables as they were
    drawn = {}
    for types, limit in ((['look'], 6), (['piece', 'effect'], 8)):
        state = run_limited(page, types, limit)
        assert state['state'] == 'done' and state['drawn'] > 0, state
        assert not state['failures'], state['failures']
        drawn[types[0]] = state['drawn']
        out[f"{types[0]}s"] = dict(drawn=state['drawn'], skipped=state['skipped'], seconds=state['seconds'])
    after = page.evaluate('viewer.pageTables()')
    assert after == tables, f'what the drawing loaded was not let go: {tables} before, {after} after'
    kept = page.evaluate("""async () => {
        const pictures = (await (await fetch('/library/pictures.json')).json()).pictures;
        const thumbs = (await (await fetch('/library.json?index=1')).json()).thumbs;
        return { pictures: pictures.length, thumbs: thumbs.length };
    }""")
    out['kept'] = kept
    again = counts(page)
    assert again['looks'] == before['looks'] - drawn['look'], (before, again, drawn)
    assert again['pieces'] == before['pieces'] - drawn['piece'], (before, again, drawn)     # (an effect skipped stays to draw)
    # the window, with only the pictures ticked: Start shows their bar; Cancel stops them, what was drawn kept
    page.locator('#cacheClose').click()
    page.locator('#settingsButton').click()
    page.locator('#projectCache').click()
    page.wait_for_function("s => !document.querySelector(s).textContent.startsWith('Counting')", arg=NOTE, timeout=120000)
    for box in ('#cachePieces', '#cacheMaps'):
        if page.locator(box).is_checked():
            page.locator(box).uncheck()
    page.locator('#cachePictures').check()
    page.locator('#cacheStart').click()
    page.wait_for_selector('#cacheDrawBar:not([hidden])', timeout=60000)
    status = page.locator('#cacheStatus').inner_text()
    assert 'drawn in this page' in status, status
    assert page.locator('#cacheBar').is_hidden()        # (the server's bar: nothing asked of it)
    page.wait_for_function("viewer.precachePictures.state().done > 0", timeout=120000)
    page.locator('#cacheCancel').click()
    page.wait_for_function("viewer.precachePictures.state().state === 'cancelled'", timeout=60000)
    page.wait_for_function("!document.querySelector('#cacheStatus').textContent.includes('leave it open')", timeout=60000)
    status = page.locator('#cacheStatus').inner_text()
    assert 'cancelled' in status and 'stay' in status, status
    assert page.locator('#cacheStart').inner_text() == 'Carry on'
    assert page.locator('#cacheDrawBar').is_hidden()
    out['cancelled'] = status
    # with the pieces ticked too, the pictures wait for them and start once they are read (only where every piece is
    # read already: else the pieces alone take ten minutes)
    pieces_left = page.evaluate("fetch('/precache.json?plan=1').then(r => r.json()).then(s => s.plan.pieces.missing)")
    if pieces_left == 0:
        page.locator('#cachePieces').check()
        page.locator('#cachePictures').check()
        page.locator('#cacheStart').click()
        page.wait_for_selector('#cacheDrawBar:not([hidden])', timeout=120000)
        page.wait_for_function("viewer.precachePictures.state().state === 'running'", timeout=60000)
        page.locator('#cacheCancel').click()
        page.wait_for_function("viewer.precachePictures.state().state === 'cancelled'", timeout=60000)
        out['after pieces'] = 'started once the pieces were read'
    else:
        out['after pieces'] = f'not tried: {pieces_left} pieces still to read on this server'
    assert not errors, errors
    page.close()
    return out
