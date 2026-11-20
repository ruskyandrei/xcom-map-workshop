"""The builder's Test in game flow with a controllable build and launch service."""
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4


def check_prefab_test(browser, url, screenshot=None):
    base = url.split('?')[0]
    page = browser.new_page(viewport=dict(width=1440, height=900))
    errors, starts, attempts, cancellations = [], [], [], []
    response = {}
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: dialog.accept())

    def stub(route):
        path = urlsplit(route.request.url).path
        if path == '/play.json':
            # (the Game menu's Installs section reads the game install too: play.js renderInstalls)
            route.fulfill(json=dict(lwr=dict(folder='Scratch XCOM', kind='Long War Rebalance', setting='game'),
                                    install=dict(ready=True, folder='Scratch XCOM', source='a scratch install'), launch=dict(how='dry')))
            return
        if path == '/prefab-tests':
            body = route.request.post_data_json
            starts.append(body)
            response.clear()
            response.update(id=str(uuid4()), phase='building', label=body['snapshot']['name'], quick=body['quick'],
                            unsaved=body['unsaved'], placement=dict(grid=[36, 36]), issues=[],
                            build=dict(progress=dict(what='Relighting', done=2, total=5), lines=['build log']))
        elif path.endswith('/cancel'):
            cancellations.append(path.split('/')[2])
            response.update(phase='cancelled', cancelRequested=True)
        elif path.endswith('/play'):
            body = route.request.post_data_json
            attempts.append(body)
            assert body['buildId'] == response['buildId']
            if len(attempts) == 1:
                response.update(phase='failed', retryable=True, issues=[dict(code='launch-failed', message='Scratch launch failed.')])
            else:
                response.update(phase='dry', retryable=False, issues=[])
        route.fulfill(json=response)

    page.route('**/play.json', stub)
    page.route('**/prefab-tests**', stub)
    def ready():
        page.wait_for_function('window.viewer && document.querySelector("#loading").hidden')

    def options():
        page.locator('#prefabTest').click()
        page.locator('#buildOptions').wait_for(state='visible')
        assert not page.locator('#buildBake').is_checked()      # off by default: a quicker test

    def close():
        page.locator('#prefabTestClose').click()
        page.locator('#prefabTestModal').wait_for(state='hidden')

    # An unnamed document can test its current floor box. The build and launch use distinct identities.
    page.goto(base + '?prefab=new')
    ready()
    page.evaluate('viewer.addVolumes([{box:[-192,0,0,0,192,176],floor:0}])')
    before = page.evaluate('viewer.builderDocument()')
    options()
    if screenshot:
        page.locator('#buildForm').screenshot(path=str(Path(screenshot).with_name('prefab-test-options.png')))
    page.locator('#buildBake').check()          # baked when asked
    page.locator('#buildOptionsOk').click()
    page.wait_for_function('document.querySelector("#prefabTestStatus").textContent === "Relighting"')
    assert starts[0]['snapshot'] == before
    assert starts[0]['unsaved'] and not starts[0]['quick']
    response.update(phase='ready', buildId='exact-build-1')
    page.get_by_text('Scratch launch failed.', exact=True).wait_for()
    page.locator('#prefabTestLaunch').click()
    page.get_by_text('Dry launch prepared', exact=True).wait_for()
    assert len(attempts) == 2 and attempts[0]['attemptId'] != attempts[1]['attemptId']
    assert all(a['buildId'] == 'exact-build-1' for a in attempts)
    close()
    assert page.evaluate('viewer.dirty() && viewer.builderDocument().revision === undefined')
    assert page.evaluate('viewer.builderDocument()') == before
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.buildings().length') == 0

    # The saved revision and a later edit can both be tested. A save elsewhere cannot replace the submitted snapshot.
    page.evaluate('viewer.addVolumes([{box:[0,0,0,192,192,192],floor:0}])')
    name = 'T2 browser ' + str(uuid4())[:8]
    assert page.evaluate('name => viewer.saveBuilder({name})', name)
    prefab_id = page.evaluate('viewer.builderDocument().id')
    options()
    page.locator('#buildOptionsOk').click()     # the default: not baked
    page.locator('#prefabTestCancel').wait_for(state='visible')
    assert starts[-1]['quick'] and not starts[-1]['unsaved']
    test_id = response['id']
    page.locator('#prefabTestCancel').click()
    page.get_by_text('Prefab test cancelled', exact=True).wait_for()
    assert cancellations == [test_id]
    close()
    page.evaluate('viewer.addVolumes([{box:[192,0,0,384,192,192],floor:0}]); viewer.keepRecovery()')
    before = page.evaluate('viewer.builderDocument()')
    recovery = page.evaluate('id => viewer.prefabApi.recovery(id)', prefab_id)
    assert recovery
    options()
    page.locator('#buildOptionsOk').click()
    page.locator('#prefabTestCancel').wait_for(state='visible')
    assert starts[-1]['snapshot'] == before and starts[-1]['unsaved']
    assert page.evaluate('id => viewer.prefabApi.recovery(id)', prefab_id) == recovery
    assert page.evaluate('viewer.dirty()')
    other = browser.new_page()
    other.goto(base + '?prefab=' + prefab_id)
    other.wait_for_function('window.viewer')
    later = other.evaluate('''async id => { const doc = await viewer.prefabApi.load(id);
      const revision = doc.revision; delete doc.revision; delete doc.savedAt;
      doc.name += ' from another tab'; return viewer.prefabApi.save(id, doc, revision); }''', prefab_id)
    other.close()
    assert later['revision'] == before['revision'] + 1
    assert starts[-1]['snapshot'] == before and page.evaluate('viewer.builderDocument()') == before
    page.reload()
    ready()
    page.locator('#prefabTestModal').wait_for(state='visible')
    response.update(phase='ready', buildId='exact-build-2')
    page.locator('#prefabTestLaunch').wait_for(state='visible')
    assert len(attempts) == 2
    page.locator('#prefabTestLaunch').click()
    page.get_by_text('Dry launch prepared', exact=True).wait_for()
    assert len(attempts) == 3 and attempts[-1]['buildId'] == 'exact-build-2'
    close()
    page.goto(base + '?map=URB_Bar')
    ready()
    assert page.locator('#prefabTest').is_hidden()
    page.evaluate("viewer.showPieces(true); viewer.setLibraryScope('prefabs')")
    page.locator('#prefabList .libitem', has_text=name).wait_for(state='visible')
    assert page.locator('#prefabList').get_by_role('button', name='Test in game').count() == 0
    assert not errors, errors
    page.close()
    return dict(snapshots=len(starts), launchAttempts=len(attempts), cancelled=len(cancellations), errors=errors)
