"""Browser checks of the project and prefab documents across pages (review findings 3, 4, 7 and 10): drafts kept for
recovery by the page session that owns them, Replace saving over the revision it showed and no other, a first-open
project link finishing as asked, and Build's status following the open project.

Only against test servers with scratch folders (they save projects and prefabs there):

    python -B tools/viewer/tests/browser_documents.py --url http://127.0.0.1:8795/ --screenshot <scratch>/documents.png
    [--cold-url http://127.0.0.1:8796/]      a server on the same projects folder and an empty scratch cache: the
                                             first-open check then really exports URB_Bar there (about a minute)

Run from browser_smoke.py too: --only documents (the warm checks).
"""
import argparse
import json
from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_smoke import open_viewer, type_pose, type_project_name     # noqa: E402

MAP = 'URB_Bar'


def base(url):
    return url.split('?')[0]


def ready(page):
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)


def drafts(page, project_id):
    """The project's drafts as the server lists them: (the newest's owner, how many)."""
    kept = page.evaluate("id => fetch(`/projects/${id}/recovery.json`).then(r => r.json())", project_id)
    return (None, 0) if kept is None else (kept['owner'], kept['others'] + 1)


def wait_drafts(page, project_id, want, owner=None):
    for _ in range(80):
        found = drafts(page, project_id)
        if found[1] == want and (owner is None or found[0] == owner): return found
        page.wait_for_timeout(250)
    raise AssertionError(f'drafts never became {want} (owner {owner}): {drafts(page, project_id)}')


def pieces(page):
    return page.evaluate("[...viewer.roots.keys()].filter(id => { const r = viewer.roots.get(id), o = r.userData.source;"
                         " return r.visible && !o.hidden && viewer.gizmo.linkedCount(id) === 0 && !viewer.recipeOf(id); })")


def edit(page, piece, field='posX', delta=96):
    page.evaluate('id => viewer.select(id)', piece)
    type_pose(page, field, delta)
    page.wait_for_function('viewer.project() ? viewer.project().dirty : viewer.changes().total > 0')


def save_new(page, name):
    """Ctrl+S on a page with no project: the Save dialog, a name, Enter; the project's id."""
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, name)
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    return page.evaluate('viewer.project().id')


def leave(page, discard=True):
    """Another map (the same one, no project): the leave question answered Discard when it asks."""
    old = page.url
    page.evaluate('m => void viewer.goTo({ map: m, project: null, scene: null })', MAP)
    if discard:
        page.locator('#leaveDiscard').click()
    page.wait_for_url(lambda u: str(u) != old, timeout=60000)
    ready(page)


def open_project(browser, url, project_id, errors, expected=()):
    page = open_viewer(browser, f'{base(url)}?map={MAP}&project={project_id}', errors, expected)
    page.wait_for_function('id => viewer.project()?.id === id', arg=project_id, timeout=120000)
    return page


def check_two_windows(browser, url):
    """Finding 3: two dirty pages keep a draft each; a clean third page's leaving deletes neither; a save and a discard
    delete their own page's only, in either order; a draft kept after another page saved is stale and said so; a
    draft restored in another page becomes that page's; a failed draft write is said, and reopening offers the draft
    kept before it."""
    errors = []
    a = open_viewer(browser, f'{base(url)}?map={MAP}', errors)
    visible = pieces(a)
    edit(a, visible[5])
    project_id = save_new(a, f'Two windows {time.time_ns()}')
    b = open_project(browser, url, project_id, errors, expected=(409,))
    c = open_project(browser, url, project_id, errors)
    session = {p: p.evaluate('viewer.session') for p in (a, b, c)}
    assert len(set(session.values())) == 3, session
    # two dirty pages: a draft each
    edit(a, visible[6])
    wait_drafts(a, project_id, 1, session[a])
    edit(b, visible[7])
    wait_drafts(a, project_id, 2, session[b])
    # a clean third page leaves: both stay
    leave(c, discard=False)
    assert drafts(a, project_id) == (session[b], 2)
    c.close()
    # A saves: its draft goes, B's stays
    a.keyboard.press('Control+s')
    a.wait_for_function('viewer.project()?.revision === 2 && !viewer.project().dirty')
    wait_drafts(a, project_id, 1, session[b])
    # B's next draft is kept against revision 1, now stale: kept, and said once
    edit(b, visible[8])
    b.wait_for_function("document.querySelector('#projectBanner').textContent.includes('saved elsewhere since this page opened it')")
    kept = b.evaluate("id => fetch(`/projects/${id}/recovery.json`).then(r => r.json())", project_id)
    assert (kept['owner'], kept['baseRevision']) == (session[b], 1), kept
    # B discards: its draft goes
    leave(b)
    wait_drafts(a, project_id, 0)
    b.close()
    # the other order: B (fresh, at revision 2) saves first, A discards after
    b = open_project(browser, url, project_id, errors)
    session[b] = b.evaluate('viewer.session')
    edit(a, visible[9])
    wait_drafts(a, project_id, 1, session[a])
    edit(b, visible[10])
    wait_drafts(a, project_id, 2, session[b])
    b.keyboard.press('Control+s')
    b.wait_for_function('viewer.project()?.revision === 3 && !viewer.project().dirty')
    wait_drafts(a, project_id, 1, session[a])
    leave(a)
    wait_drafts(b, project_id, 0)
    a.close()
    # a lost tab's draft, restored in another page: that page's own now, the lost one's gone
    edit(b, visible[11])
    wait_drafts(b, project_id, 1, session[b])
    lost = b.evaluate('viewer.projectState()')
    b.close()
    d = open_project(browser, url, project_id, errors)
    assert 'were kept' in d.locator('#projectBanner').inner_text()
    d.locator('#projectBanner button', has_text='Restore them').click()
    d.wait_for_function('s => viewer.projectState() === s', arg=lost)
    wait_drafts(d, project_id, 1, d.evaluate('viewer.session'))
    d.keyboard.press('Control+s')
    d.wait_for_function('viewer.project()?.revision === 4 && !viewer.project().dirty')
    wait_drafts(d, project_id, 0)
    # a draft write that fails is said; reopening offers the draft kept before it
    edit(d, visible[12])
    wait_drafts(d, project_id, 1, d.evaluate('viewer.session'))
    first = d.evaluate('viewer.projectState()')
    route = f'**/projects/{project_id}/recovery.json'
    d.route(route, lambda r: r.fulfill(status=500, json=dict(error='Simulated full disk')) if r.request.method == 'PUT' else r.continue_())
    edit(d, visible[13])
    d.wait_for_function("document.querySelector('#projectBanner').textContent.includes('could not be kept for recovery')")
    assert 'Simulated full disk' in d.locator('#projectBanner').inner_text()
    d.unroute(route)
    d.close()
    e = open_project(browser, url, project_id, errors)
    e.locator('#projectBanner button', has_text='Restore them').click()
    e.wait_for_function('s => viewer.projectState() === s', arg=first)
    leave(e)
    wait_drafts(e, project_id, 0)
    e.close()
    errors = [x for x in errors if 'Simulated full disk' not in x and 'status of 500' not in x]
    assert not errors, errors
    return dict(project=project_id, pages=5)


def check_replace_confirmed(browser, url):
    """Finding 4: Replace saves over the revision the question showed. One saved since is asked about again, with its
    revision now, and keeps its changes until the new choice; then Replace saves over that one. The same for a prefab
    file imported over one of the library's."""
    errors = []
    a = open_viewer(browser, f'{base(url)}?map={MAP}', errors)
    visible = pieces(a)
    edit(a, visible[3])
    name = f'Replace target {time.time_ns()}'
    target = save_new(a, name)
    a.close()
    # a page with edits of its own, saving as the target's name: the question shows revision 1
    p = open_viewer(browser, f'{base(url)}?map={MAP}', errors)
    edit(p, visible[4], 'posY', -96)
    mine = p.evaluate('viewer.projectState()')
    p.locator('#projectButton').click(); p.locator('#projectSaveAs').click()
    p.wait_for_selector('#fileDialog:not([hidden]) .filerow')
    type_project_name(p, name)
    p.locator('#fileName').press('Enter')
    assert 'revision 1' in p.locator('#fileConfirm').inner_text()
    # meanwhile another page saves the target again
    other = open_project(browser, url, target, errors)
    other.evaluate('id => viewer.select(id)', visible[15]); other.keyboard.press('Delete')
    other.keyboard.press('Control+s')
    other.wait_for_function('viewer.project()?.revision === 2')
    theirs = other.evaluate('viewer.projectState()')
    other.close()
    # Replace: asked again, revision 2 shown, nothing saved over it
    p.locator('#fileConfirm button.primary').click()
    p.wait_for_function("document.querySelector('#fileConfirm').textContent.includes('saved again meanwhile')")
    assert 'revision 2' in p.locator('#fileConfirm').inner_text() and p.locator('#fileDialog').is_visible()
    saved = p.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", target)
    assert saved['revision'] == 2 and len(saved['overrides']) == 2, saved['overrides']
    # Don't replace leaves it; asked again and confirmed, revision 2 is replaced
    p.locator('#fileConfirm button', has_text="Don't replace").click()
    assert p.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json()).then(d => d.revision)", target) == 2
    p.locator('#fileName').press('Enter')
    assert 'revision 2' in p.locator('#fileConfirm').inner_text()
    p.locator('#fileConfirm button.primary').click()
    p.wait_for_function('id => viewer.project()?.id === id && viewer.project().revision === 3 && !viewer.project().dirty', arg=target)
    assert p.evaluate('viewer.projectState()') == mine and mine != theirs
    p.close()
    # a prefab file over one of the library's: Replace replaces the revision it showed
    q = open_viewer(browser, f'{base(url)}?map={MAP}', errors, expected=(409,))
    doc = q.evaluate('''async () => {
      const { newPrefab } = await import('/prefabs.js');
      const id = crypto.randomUUID();
      const doc = newPrefab(id, 'Imported twice ' + Date.now(), { tiles: [1, 1], groups: [], donors: [], pieces: [],
        buildings: [{ id: 'b1', name: 'Box', kind: 'building', floors: [{ boxes: [[0, 0, 0, 96, 96, 192]] }] }] });
      await viewer.prefabApi.importFile(doc);
      return doc;
    }''')
    q.evaluate('viewer.showPieces(true); viewer.setLibraryScope("prefabs")')
    path = Path(__file__).resolve().parents[3] / '.scratch' / 'imported-twice.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(doc, name=doc['name'] + ' (theirs)')), encoding='utf8', newline='\n')
    q.locator('#prefabFile').set_input_files(str(path))
    q.locator('#prefabNote', has_text='(revision 1)').wait_for()
    # saved again meanwhile (another page renames it)
    q.evaluate("async id => { const d = await viewer.prefabApi.load(id); await viewer.prefabApi.save(id, { ...d, name: d.name + ' (renamed)' }, d.revision); }", doc['id'])
    q.locator('#prefabNote button', has_text='Replace it').click()
    q.locator('#prefabNote', has_text='saved again meanwhile').wait_for()
    assert '(revision 2)' in q.locator('#prefabNote').inner_text()
    assert q.evaluate("id => viewer.prefabApi.load(id).then(d => d.name)", doc['id']).endswith('(renamed)')
    q.locator('#prefabNote button', has_text='Replace it').click()
    q.wait_for_function("id => viewer.prefabApi.load(id).then(d => d.revision === 3 && d.name.endsWith('(theirs)'))", arg=doc['id'])
    q.close()
    assert not errors, errors
    return dict(project=target, prefab=doc['id'])


def check_failed_save_waits(browser, url):
    """Finding 34: a map change that waits for a project's first save waits on through a failed save: the next save
    that succeeds goes on to it."""
    errors = []
    p = open_viewer(browser, f'{base(url)}?map={MAP}', errors, expected=(500,))
    edit(p, pieces(p)[2])
    p.evaluate('void viewer.goTo({ prefab: "new" })')
    p.locator('#leaveSave').click()
    p.locator('#fileDialog').wait_for(state='visible')
    # the save refused as its map name was taken meanwhile (the dialog stays open with the name it would get now)
    route = '**/projects/*/project.json'

    def taken(r):
        if r.request.method != 'PUT': r.continue_(); return
        output = json.loads(r.request.post_data)['document']['output']
        r.fulfill(status=409, json=dict(error='Simulated: the map name was taken meanwhile',
                                        proposal=dict(output=output, reason='the name as typed', limit=24)))
    p.route(route, taken)
    type_project_name(p, f'Waiting change {time.time_ns()}')
    p.locator('#fileName').press('Enter')
    p.locator('#fileMessage', has_text='Simulated: the map name was taken').wait_for()
    assert p.locator('#fileDialog').is_visible() and 'map=' in p.url
    p.unroute(route)
    p.locator('#fileOk').click()
    p.wait_for_url('**/?prefab=new', timeout=60000)
    ready(p)
    p.close()
    errors = [x for x in errors if 'status of 409' not in x]
    assert not errors, errors
    return dict(waited=True)


def check_build_binding(browser, url):
    """Finding 10: a project's build status is its own. A copy saved from a project with a package of revision 1 is at
    revision 1 too, and shows no package: the one saved from's is not taken for its own."""
    errors = []
    a = open_viewer(browser, f'{base(url)}?map={MAP}', errors)
    visible = pieces(a)
    edit(a, visible[2])
    first = save_new(a, f'Build binding {time.time_ns()}')
    # the first project's last package, of its revision 1, as the server would say it (nothing is built here)
    package = dict(folder='<builds>/BuildBinding', buildId='BuildBinding-1', builtAt='2026-11-20T10:00:00', seconds=5,
                   quick=True, times=dict(quick=5), foreignPieces=0, foreignEffects=0, donors=[], revision=1, files=[])

    def status(route):
        answer = route.fetch(); body = answer.json(); body['package'] = package
        route.fulfill(response=answer, json=body)
    a.route(f'**/projects/{first}/build.json', status)
    a.reload(); ready(a)
    a.wait_for_function("id => viewer.lastBuild()?.project === id && viewer.lastBuild().package?.revision === 1", arg=first)
    a.locator('#projectButton').click(); a.locator('#projectSaveAs').click()
    a.wait_for_selector('#fileDialog:not([hidden]) .filerow')
    type_project_name(a, f'Build binding copy {time.time_ns()}')
    a.locator('#fileName').press('Enter')
    a.wait_for_function('id => viewer.project()?.id !== id && viewer.project().revision === 1', arg=first)
    copy = a.evaluate('viewer.project().id')
    a.wait_for_function("id => viewer.lastBuild()?.project === id", arg=copy)
    status = a.evaluate('viewer.lastBuild()')
    assert not status.get('package'), status
    a.close()
    assert not errors, errors
    return dict(first=first, copy=copy)


def check_first_open(browser, url, project_id=None, cold_url=None):
    """Finding 7: a project link opened on a map not prepared yet opens the project once the map is (its mission
    too); an export that fails and is tried again opens it too; a map chosen by hand meanwhile opens that map alone.
    Warm: the server's map list is answered as if URB_Bar were not prepared, and its export stood in for. Cold (with
    cold_url, a server on the same projects folder and an empty scratch cache): URB_Bar really exported."""
    errors = []
    page = open_viewer(browser, f'{base(url)}?map={MAP}', errors)
    if project_id is None:
        edit(page, pieces(page)[1])
        project_id = save_new(page, f'First open {time.time_ns()}')
    state = page.evaluate('viewer.projectState()')
    missions = page.evaluate('viewer.data.missions?.length ?? 0')
    mission = '1' if missions > 1 else '0'
    page.close()
    result = dict(project=project_id, mission=mission)

    def unprepared(page, fail_first=False):
        stage = dict(asked=0, posted=0, done=False)

        def maps(route):
            answer = route.fetch(); body = answer.json()
            if not stage['done']:
                for m in body['maps']:
                    if m['id'] == MAP: m['ready'] = False
            route.fulfill(response=answer, json=body)

        def export(route):
            stage['posted'] += 1
            if fail_first and stage['posted'] == 1: route.fulfill(status=500, json=dict(error='Simulated export failure'))
            else: route.fulfill(json=dict(state='running'))

        def export_status(route):
            stage['asked'] += 1
            if stage['asked'] < 2: route.fulfill(json=dict(state='running', progress=dict(fraction=0.5, what='its pieces', done=1, total=2)))
            else: stage['done'] = True; route.fulfill(json=dict(state='ready'))
        page.route('**/maps.json', maps)
        page.route(f'**/maps/{MAP}/export', export)
        page.route(f'**/maps/{MAP}/export.json', export_status)
        return stage

    def fresh():
        p = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
        p.on('pageerror', lambda e: errors.append(str(e)))
        p.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 500' not in m.text else None)
        p.on('dialog', lambda d: d.accept())
        return p

    link = f'?map={MAP}&project={project_id}&mission={mission}'
    # warm: prepared (stood in for), then the project opens with its mission
    p = fresh(); unprepared(p)
    p.goto(base(url) + link)
    p.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                        arg=project_id, timeout=120000)
    assert f'project={project_id}' in p.url and f'mission={mission}' in p.url, p.url
    assert p.evaluate('viewer.projectState()') == state
    p.close()
    # an export that fails, then tried again
    p = fresh(); unprepared(p, fail_first=True)
    p.goto(base(url) + link)
    p.locator('#mapMessage', has_text='could not be prepared').wait_for(timeout=60000)
    p.locator('#mapOk').click()
    p.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                        arg=project_id, timeout=120000)
    assert f'mission={mission}' in p.url, p.url
    p.close()
    # another map chosen by hand while it prepares: that map, without the project
    p = fresh(); stage = unprepared(p)
    stage['asked'] = -1000        # (it stays preparing)
    p.goto(base(url) + link)
    p.locator('#mapMessage', has_text='Preparing').wait_for(timeout=60000)
    other = p.evaluate("[...document.querySelectorAll('.maprow')].find(r => r.dataset.id !== 'URB_Bar' && !r.dataset.id.startsWith('prefab:')"
                       " && r.querySelector('.mstate.ready, .mstate.checked'))?.dataset.id")
    assert other, 'no other prepared map to choose'
    p.locator(f'.maprow[data-id="{other}"]').first.dblclick()
    p.wait_for_url(lambda u: f'map={other}' in str(u), timeout=60000)
    ready(p)
    assert p.evaluate('viewer.project()') is None and 'project=' not in p.url, p.url
    result['otherMap'] = other
    p.close()
    if cold_url:
        # cold: the map really exported into the cold server's scratch cache, then the project opens there
        p = fresh()
        started = time.monotonic()
        p.goto(base(cold_url) + link)
        p.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                            arg=project_id, timeout=600000)
        assert f'mission={mission}' in p.url, p.url
        assert p.evaluate('viewer.projectState()') == state
        result['coldSeconds'] = round(time.monotonic() - started)
        p.close()
    assert not errors, errors
    return result


CHECKS = {'two-windows': ('twoWindows', check_two_windows), 'replace': ('replace', check_replace_confirmed),
          'waiting-save': ('waitingSave', check_failed_save_waits), 'build-binding': ('buildBinding', check_build_binding),
          'first-open': ('firstOpen', check_first_open)}


def check_all(browser, url, only=None):
    """The warm checks (browser_smoke.py --only documents)."""
    return {key: run(browser, url) for name, (key, run) in CHECKS.items() if only is None or name in only}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True, help='a test server with scratch projects (never the main one, 8768)')
    ap.add_argument('--cold-url', help='a test server on the same projects folder with an empty scratch cache')
    ap.add_argument('--screenshot', type=Path, required=True)
    ap.add_argument('--only', help='two-windows, replace, waiting-save, build-binding, first-open (comma-separated)')
    args = ap.parse_args()
    assert ':8768' not in args.url, 'only against a test server'
    only = set(args.only.split(',')) if args.only else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        wanted = set(CHECKS) if only is None else only
        out = check_all(browser, args.url, wanted - {'first-open'})
        if 'first-open' in wanted: out['firstOpen'] = check_first_open(browser, args.url, cold_url=args.cold_url)
        page = browser.new_page(); page.goto(args.url); page.screenshot(path=str(args.screenshot)); browser.close()
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
