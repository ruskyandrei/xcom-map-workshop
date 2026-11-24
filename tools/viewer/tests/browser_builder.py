"""Prefab builder acceptance, against an isolated viewer (8790-8799) with scratch stores."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright


def listen(page, errors, expected=()):
    """The page's errors, its console's errors and its failed requests into `errors` (HTTP statuses in `expected` are
    the check's own doing; a request a navigation cancels, net::ERR_ABORTED, is not a failure)."""
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and not any(f'status of {s}' in m.text for s in expected) else None)
    page.on('requestfailed', lambda r: errors.append(f'{r.url}: {r.failure}') if 'ERR_ABORTED' not in (r.failure or '') else None)


def check_builder(browser, url, screenshot=None):
    base = url.split('?')[0]
    assert 8790 <= urlsplit(base).port <= 8799, 'Use a test server and scratch prefab/project stores'
    errors, dialogs = [], []
    page = browser.new_page(viewport=dict(width=1600, height=1000))
    listen(page, errors, expected=(404,))      # (the pieces of an unavailable map asked for below are the check's own)
    page.on('dialog', lambda d: (dialogs.append(d.type), d.accept()))
    def opened(query):
        page.goto(base + query)
        page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    opened('?prefab=new')
    assert page.evaluate('viewer.builderMode && viewer.roots.size === 0 && !viewer.dirty()')
    assert page.locator('#projectBuild').is_hidden() and page.locator('#notesButton').is_hidden()
    # The bar in the builder (the prefab menus plan): Project says None, the second button is the prefab's, its menu
    # the prefab's items and Open; the Project menu holds Open… and the recent projects, no Save
    assert page.locator('#projectTitle').inner_text() == 'None'
    assert page.locator('#mapButton small').inner_text().strip().lower() == 'prefab'
    assert page.locator('#mapTitle').inner_text() == 'Untitled prefab'
    page.locator('#projectButton').click()
    labels = [t.strip() for t in page.locator('#projectMenu .menuitems button:visible span').all_inner_texts()]
    assert labels == ['Open…'], labels
    assert 'A prefab is open' in page.locator('#projectInfo').inner_text()
    assert page.locator('#projectRecent').is_visible()
    page.keyboard.press('Escape')
    page.locator('#mapButton').click()
    assert page.locator('#docHead').inner_text().strip().lower() == 'this prefab'
    assert page.locator('#mapItems').is_hidden() and page.locator('#prefabItems').is_visible()
    labels = [t.strip() for t in page.locator('#prefabItems button:visible span').all_inner_texts()]
    assert labels == ['Save', 'Save as…', 'Export to a file…'], labels
    assert page.locator('#docPrefabExport').is_disabled()       # (nothing saved yet: the file is the saved revision)
    assert page.locator('#openPrefabsKey').inner_text() == 'Ctrl+O'
    # The Open window's Prefabs side and the Add panel both offer a new prefab; neither offers Test in game.
    page.locator('#openPrefabs').click()
    page.wait_for_selector('#openPrefabDialog:not([hidden]) .card.newcard')
    page.locator('#openPrefabCancel').click()
    page.evaluate('viewer.showPieces(true); viewer.setLibraryScope("prefabs")')
    assert page.locator('#prefabNew').is_visible()
    assert page.get_by_role('button', name='Test in game', exact=True).count() == 0
    page.evaluate('viewer.showPieces(false)')
    # The Build menu draws made pieces here as in a map (until 21 November 2026 its tools did nothing in the builder):
    # a wall picked as the user does, a floor and a block by script; saved, they open again as they were drawn.
    import browser_walls as bw
    for key, a, b, kind in (('wall', [-192, 0, 0], [192, 0, 0], 'fracWall'), ('floor', [-192, 192, 0], [96, 384, 0], 'fracSlab'),
                            ('block', [288, 288, 0], [480, 384, 0], 'ground')):
        (bw.build_menu if key == 'wall' else bw.start_build)(page, key)
        bw.look_at(page, a)
        bw.drag(page, bw.ground_point(page, a), bw.ground_point(page, b))
        page.wait_for_function('k => viewer.wallState(viewer.gizmo.active)?.generated?.kind === k', arg=kind, timeout=60000)
        page.keyboard.press('Escape')
    made = page.evaluate("[...viewer.roots.values()].map(r => r.userData.source.added?.generated?.kind).sort()")
    assert made == ['fracSlab', 'fracWall', 'ground'], made
    assert page.evaluate('name => viewer.saveBuilder({name})', 'Builder made pieces ' + str(time.time_ns()))
    opened('?prefab=' + page.evaluate('viewer.builderDocument().id'))
    assert page.evaluate("[...viewer.roots.values()].map(r => r.userData.source.added?.generated?.kind).sort()") == made
    opened('?prefab=new')
    # Complete document, hidden boxes and light included. Variable-height floors and negative XY.
    doc = page.evaluate('''async () => {
      const doc = viewer.builderDocument();
      doc.buildings = [{id:'b-stable',name:'Workshop',kind:'building',floors:[
        {boxes:[[-384,-192,0,0,192,240]]},{boxes:[[-384,-192,240,0,192,480]]}]}];
      doc.pieces = [{actor:'TheWorld.PersistentLevel.PointLight_copy40',template:{kind:'point',version:1},
        light:structuredClone(viewer.families().lightRecipes.point.values),location:[-192,0,160],rotation:[0,0,0]}];
      doc.groups = [{id:'g-stable',breakTogether:false,members:[{building:'b-stable'},{added:doc.pieces[0].actor}]}];
      await viewer.applyPrefabDocument(doc); return doc;
    }''')
    assert page.evaluate('viewer.dirty() && viewer.copySerial() >= 40')
    assert page.evaluate('viewer.builderRecords().pieces.length === 1 && viewer.builderRecords().buildings.length === 1')
    name = 'Builder acceptance ' + str(time.time_ns())
    assert page.evaluate('name => viewer.saveBuilder({name})', name)
    prefab_id = page.evaluate('viewer.builderDocument().id')
    saved = page.evaluate('id => viewer.prefabApi.load(id)', prefab_id)
    assert saved['groups'][0]['id'] == 'g-stable' and saved['buildings'][0]['id'] == 'b-stable'
    assert saved['buildings'][0]['floors'][0]['boxes'][0] == [0, 0, 0, 384, 384, 240]
    assert saved['pieces'][0]['location'] == [192, 192, 160]
    assert page.evaluate('!viewer.dirty() && JSON.stringify(viewer.data.tileGrid.origin) === "[0,0,0]"')
    opened('?prefab=' + prefab_id)
    assert page.evaluate('!viewer.dirty()')
    assert page.evaluate('viewer.saveBuilder()')
    again = page.evaluate('id => viewer.prefabApi.load(id)', prefab_id)
    for key in ('pieces', 'groups', 'buildings', 'donors', 'floor'): assert saved[key] == again[key], key
    # Save as cannot replace itself, requires an explicit confirmation for another target, and can cancel.
    page.locator('#mapButton').click(); page.locator('#docPrefabSaveAs').click()
    page.locator('#prefabName').fill(name)
    page.wait_for_function('document.querySelector("#prefabOk").disabled')
    assert 'Use Save' in page.locator('#prefabStatus').inner_text()
    page.locator('#prefabCancel').click()
    # Whole-graph preservation with an unavailable piece and a partner link.
    mixed = json.loads(json.dumps(again))
    missing = dict(actor='TheWorld.PersistentLevel.Missing_copy90', components=['TheWorld.PersistentLevel.Missing.StaticMeshComponent_0'],
                   location=[96, 96, 64], rotation=[0, 0, 0], prefab='copy90:pair', partner=again['pieces'][0]['actor'],
                   recipe=dict(key='kept-key', name='Kept piece'))
    missing['from'] = dict(package='UnavailableBuilderMap', level='base', actor='TheWorld.PersistentLevel.Missing')
    mixed['pieces'].append(missing); mixed['groups'][0]['members'].append(dict(added=missing['actor']))
    mixed['donors'].append(dict(package='UnavailableBuilderMap', sha256='a' * 64))
    # (a replace names the revision it replaces: review finding 4)
    page.evaluate('doc => viewer.prefabApi.importFile(doc, "replace", doc.revision)', mixed)
    opened('?prefab=' + prefab_id)
    assert page.evaluate('viewer.builderRecords().size.unknown.length') == 1
    page.evaluate('viewer.addVolumes([{box:[-192,-96,0,-96,0,192],floor:0}])')
    # Recovery is the complete working document, not the next save's normalized coordinates.
    page.evaluate('viewer.keepRecovery()')
    working = page.evaluate('viewer.builderDocument()')
    recovered = page.evaluate('id => viewer.prefabApi.recovery(id)', prefab_id)
    assert recovered['document']['pieces'] == working['pieces']
    opened('?prefab=' + prefab_id)
    page.locator('#projectBanner').get_by_role('button', name='Restore them').click()
    page.locator('#projectBanner').get_by_text('1 piece still missing.', exact=False).wait_for()
    assert page.evaluate('viewer.dirty()')
    assert page.evaluate('viewer.builderDocument().pieces') == working['pieces']
    assert page.evaluate('viewer.saveBuilder()')
    fixed = page.evaluate('id => viewer.prefabApi.load(id)', prefab_id)
    kept = next(p for p in fixed['pieces'] if p['actor'] == missing['actor'])
    assert kept['recipe'] == missing['recipe']
    lamp = next(p for p in fixed['pieces'] if p.get('template'))
    assert kept['partner'] == lamp['actor'] and kept['location'] == [288, 192, 64]
    assert lamp['location'] == [384, 288, 160]
    assert page.evaluate('id => viewer.prefabApi.recovery(id)', prefab_id) is None
    # A stale second page cannot save or navigate on Save; Cancel preserves the working scene.
    stale = browser.new_page(); listen(stale, errors, expected=(404, 409))     # (the same unavailable piece; its refused save)
    stale.goto(base + '?prefab=' + prefab_id); stale.wait_for_function('window.viewer && !document.querySelector("#loading").hidden === false', timeout=120000)
    assert page.evaluate('viewer.saveBuilder()')
    assert stale.evaluate('viewer.saveBuilder()') is False
    assert 'saved elsewhere' in stale.locator('#projectBanner').inner_text()
    stale.close()
    # Over the height allowance the size warns and refuses nothing (plan "sturdier prefabs", R7; 30 levels, part H):
    # the size line says so, and the prefab is saved all the same.
    page.evaluate('viewer.addVolumes([{box:[0,0,2113,96,96,2305],floor:0}])')
    size = page.evaluate('viewer.builderRecords().size')
    assert size['supported'] and len(size['warnings']) == 1 and size['tall'] and not size['errors'], size
    assert 'larger than a map holds' in page.locator('#builderSize').inner_text()
    page.evaluate('void viewer.goTo({prefab:"new"})')
    page.locator('#leaveCancel').click()
    assert page.evaluate('viewer.dirty()')
    assert page.evaluate('viewer.saveBuilder()')
    page.evaluate('viewer.gizmo.undo()')
    assert not page.evaluate('viewer.builderRecords().size.warnings.length')
    assert page.evaluate('viewer.saveBuilder()')
    # The Problems chip: what a test would say, asked of the server without building (R5).
    page.wait_for_function("!['Checking…', ''].includes(document.querySelector('#problemsChip').textContent)", timeout=60000)
    assert page.locator('#builderProblems').is_visible()
    # Discard awaits queued writes and suppresses the browser's second leave prompt.
    page.evaluate('viewer.addVolumes([{box:[0,0,0,96,96,192],floor:0}]); void viewer.keepRecovery(); void viewer.goTo({prefab:"new"})')
    before = len(dialogs)
    page.locator('#leaveDiscard').click()
    page.wait_for_url('**/?prefab=new'); page.wait_for_function('window.viewer && !viewer.dirty()')
    assert len(dialogs) == before
    assert page.evaluate('id => viewer.prefabApi.recovery(id)', prefab_id) is None
    # Floor-box-only prefabs save, open and stamp without falling back to a first mesh.
    page.evaluate('viewer.addVolumes([{box:[-96,-96,0,96,96,192],floor:0}])')
    assert page.evaluate('name => viewer.saveBuilder({name})', name + ' boxes')
    box_id = page.evaluate('viewer.builderDocument().id')
    opened('?prefab=' + box_id)
    assert page.evaluate('viewer.roots.size === 0 && viewer.buildings().length === 1')
    await_stamp = '''async id => { const T = await import('three'); const doc = await viewer.prefabApi.load(id);
      const clip = await viewer.prefabClip(doc); await viewer.pasteSnapshot(clip, new T.Matrix4().makeTranslation(-960,0,-960));
      return viewer.buildings().length; }'''
    assert page.evaluate(await_stamp, box_id) == 2
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.buildings().length') == 1
    if screenshot: page.evaluate('viewer.frame()'); page.screenshot(path=str(screenshot))
    assert not errors, errors
    page.close()
    return dict(prefab=prefab_id, buildingOnly=box_id, errors=errors)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--url', default='http://127.0.0.1:8791/'); ap.add_argument('--screenshot', type=Path); ap.add_argument('--large', action='store_true')
    args = ap.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        result = check_builder(browser, args.url, args.screenshot)
        result['realSources'] = check_real_sources(browser, args.url, result['buildingOnly'], args.screenshot)
        result['navigation'] = check_navigation(browser, args.url, result['buildingOnly'], result['realSources']['project'])
        result['recoveryEdges'] = check_recovery_edges(browser, args.url, result['buildingOnly'])
        result['recipeRecovery'] = check_recipe_recovery(browser, args.url)
        result['thisPrefab'] = check_this_prefab(browser, args.url)
        if args.large: result['large'] = check_large_builder(browser, args.url)
        print(json.dumps(result, indent=2)); browser.close()


def check_recipe_recovery(browser, url):
    """Automatically repair an unavailable donor when placing or opening a prefab."""
    from uuid import uuid4
    base = url.split('?')[0]
    page = browser.new_page(); errors = []; listen(page, errors, expected=(404,))     # (UnavailableRecipeMap's pieces: the check's own)
    page.goto(base + '?prefab=new')
    page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    fixture = page.evaluate('''async () => {
      const {index} = await fetch('/library.json?index=1').then(r => r.json());
      const entry = index.entries.find(e => e.placeable && !e.assembly && e.source.package === 'URB_PoliceStation'
        && e.source.actor === 'XComLevelActor_15')
        ?? index.entries.find(e => e.placeable && !e.assembly && e.family === 'scenery' && e.recipe.parts.length === 1);
      const query = new URLSearchParams(entry.source);
      const record = await fetch(`/library/piece.json?${query}`).then(r => r.json());
      const actor = `TheWorld.PersistentLevel.${entry.source.actor}`;
      const doc = viewer.builderDocument();
      doc.pieces = [{actor: 'Lost_copy90', from:{package:'UnavailableRecipeMap',level:'base',actor},
        components:record.objects.filter(o => o.actor === actor).map(o => o.component),
        location:[96,96,64], rotation:[0,16384,0], recipe:record.recipes[actor]},
        {actor:'Kept_copy91',from:{package:'UnavailableRecipeMap',level:'base',actor:'Kept_0'},
          components:['Kept_0.StaticMeshComponent_0'], location:[192,192,64], rotation:[0,0,0]}];
      doc.donors = [{package:'UnavailableRecipeMap',sha256:'a'.repeat(64)}];
      doc.groups = [{id:'linked',members:[{added:'Lost_copy90'},{added:'Kept_copy91'}]}];
      return {doc, source:record.source};
    }''')
    doc, source = fixture['doc'], fixture['source']
    doc['id'], doc['name'] = str(uuid4()), 'Recipe recovery ' + str(time.time_ns())
    page.evaluate('doc => viewer.prefabApi.importFile(doc)', doc)
    placed = page.evaluate('''async ({id, name}) => {
      const clip = await viewer.choosePrefab({id, name});
      return {units:[...new Set(clip.entries.map(e => e.unit))], left:clip.left};
    }''', doc)
    assert placed['units'] == ['Lost_copy90'] and len(placed['left']) == 1, placed
    page.locator('#projectBanner').get_by_text('1 piece could not be placed.', exact=False).wait_for()
    page.goto(base + '?prefab=' + doc['id'])
    page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    notice = page.locator('#projectBanner')
    notice.get_by_text('Recovered 1 piece by recipe.', exact=False).wait_for(timeout=30000)
    assert '1 piece still missing. Kept_copy91:' in notice.inner_text()
    assert page.evaluate('viewer.builderRecords().size.unknown.length') == 1
    original = page.evaluate('id => viewer.prefabApi.load(id)', doc['id'])
    assert all(p['from']['package'] == 'UnavailableRecipeMap' for p in original['pieces'])
    restored = page.evaluate('viewer.builderDocument()')
    repaired = next(p for p in restored['pieces'] if p['actor'] == 'Lost_copy90')
    assert repaired['from']['package'] == source['package']
    assert repaired['location'] == [96, 96, 64] and repaired['rotation'] == [0, 16384, 0]
    assert {m['added'] for m in restored['groups'][0]['members']} == {'Lost_copy90', 'Kept_copy91'}
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.builderRecords().size.unknown.length') == 2
    page.evaluate('viewer.gizmo.redo()')
    assert page.evaluate('viewer.builderRecords().size.unknown.length') == 1
    assert page.evaluate('viewer.saveBuilder()')
    saved = page.evaluate('id => viewer.prefabApi.load(id)', doc['id'])
    assert next(p for p in saved['pieces'] if p['actor'] == 'Lost_copy90')['from'] == repaired['from']
    assert not page.evaluate('viewer.dirty()')
    assert not errors, errors
    page.close()
    return dict(recovered=source['package'], unresolved=1, placement=True, undo=True, saved=True)


def check_real_sources(browser, url, box_id, screenshot=None):
    base = url.split('?')[0]; page = browser.new_page(viewport=dict(width=1600, height=1000)); errors = []
    listen(page, errors); page.on('dialog', lambda d: d.accept())
    page.goto(base + '?prefab=new'); page.wait_for_function('window.viewer && document.querySelector("#loading").hidden')
    page.evaluate('viewer.showPieces(true)'); page.wait_for_function('viewer.library.ready()', timeout=120000)
    assert page.locator('#builderRecipes').count() == 0
    for kind, rows in [('lights', ['Point Light', 'Spot Light']), ('Invisible', ['Cover block', 'Invisible floor'])]:
        page.locator('#libAllKind').select_option(kind)
        assert page.locator('#libAllList .libitem strong').all_inner_texts() == rows
        page.wait_for_function("Array.from(document.querySelectorAll('#libAllList canvas')).every(c => c.dataset.drawn)")
        for name in rows:
            page.locator('#libAllList .libitem', has_text=name).click()
            assert page.evaluate('viewer.placing()?.fromList')
            page.keyboard.press('Escape')
    page.locator('#libAllKind').select_option('all')
    # Three pieces from two maps, using the same library templates as the Add panel.
    sources = page.evaluate('''async () => {
      const T = await import('three'), entries = viewer.library.entries(), used = [];
      const names = ['ArcadeMachineA','Computer_A','ArcadeMachineA'];
      for (let i=0; i<3; i++) {
        const entry = entries.find(e => e.name === names[i] && e.source.package === (i===1 ? 'URB_PoliceStation' : 'URB_Bar'));
        if (!entry) throw Error('The real-source check needs Bar and Police Station in the library');
        const t = await viewer.libraryTemplate(entry.source), at = [-960 + i*960, -192, 192];
        const delta = new T.Matrix4().makeTranslation(at[0], at[2], at[1]).multiply(t.frame);
        await viewer.pasteSnapshot({entries:t.sources.map(source=>({source,matrix:new T.Matrix4().fromArray(source.matrix)})),volumes:[],pivotIndex:0},delta);
        used.push({key:entry.key,package:entry.source.package});
      }
      viewer.showPieces(false); return used;
    }''')
    assert len({s['package'] for s in sources}) == 2
    page.evaluate('viewer.gizmo.setSelection([...viewer.roots.keys()])'); page.keyboard.press('Control+g')
    assert len(page.evaluate('viewer.groupList()')) == 1
    page.evaluate('''async () => { const T=await import('three'); await viewer.pasteSnapshot(viewer.snapshot(),new T.Matrix4().makeTranslation(0,0,768)); }''')
    assert len(page.evaluate('viewer.builderDocument().pieces')) == 6
    page.evaluate('viewer.gizmo.undo()')
    page.evaluate('viewer.setPickBox([-2000,-1000,-64,2000,2000,768]); viewer.takePickBox()')
    assert page.evaluate('viewer.gizmo.selection().length') >= 3
    page.keyboard.press('Escape')
    page.evaluate('''async id => { const T=await import('three'); const clip=await viewer.prefabClip(await viewer.prefabApi.load(id));
      await viewer.pasteSnapshot(clip,new T.Matrix4().makeTranslation(0,0,768)); }''', box_id)
    # A light and a second floor survive hidden marker switches and cutaway.
    page.evaluate('''async () => { const d=viewer.builderDocument(); d.buildings[0].floors.push({boxes:[[0,768,192,192,960,384]]});
      d.pieces.push({actor:'TheWorld.PersistentLevel.PointLight_copy200',template:{kind:'point',version:1},
        light:structuredClone(viewer.families().lightRecipes.point.values),location:[96,864,160],rotation:[0,0,0]}); await viewer.applyPrefabDocument(d); }''')
    assert page.evaluate('viewer.builderRecords().size.supported')
    assert page.evaluate('name=>viewer.saveBuilder({name})', 'Builder real sources ' + str(time.time_ns()))
    prefab_id = page.evaluate('viewer.builderDocument().id')
    saved = page.evaluate('id=>viewer.prefabApi.load(id)', prefab_id)
    size = page.evaluate('d=>viewer.prefabApi.size(d)', saved)
    assert size['supported'] and size['verified'], size
    assert all(p.get('recipe', {}).get('key') for p in saved['pieces'] if p.get('from'))
    page.reload(); page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    assert not page.evaluate('viewer.dirty()')
    assert page.evaluate('viewer.saveBuilder()')
    again = page.evaluate('id=>viewer.prefabApi.load(id)', prefab_id)
    for key in ('pieces', 'groups', 'buildings', 'donors', 'floor'): assert saved[key] == again[key], key
    # Foreign collision is available for floor/cover/light ground readings.
    assert page.evaluate('''() => [...viewer.roots.values()].some(r => {
      const b=viewer.pieceBox(r.userData.source.id); return b && viewer.groundAt((b[0]+b[1])/2,(b[2]+b[3])/2,b[5]+96) !== null;
    })''')
    if screenshot:
        page.evaluate('viewer.setBoxesShown(true); viewer.setNormalLights(true); viewer.frame()')
        page.screenshot(path=str(screenshot.with_stem('builder-real-sources')))
    # Turned placement in Bar, into a saved project ready for compiler readback.
    page.goto(base+'?map=URB_Bar'); page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    project = page.evaluate('''async id => {
      const T=await import('three'), {actorMatrix}=await import('/gizmo.js'), doc=await viewer.prefabApi.load(id), clip=await viewer.prefabClip(doc);
      const g=viewer.data.tileGrid, turn=actorMatrix([0,0,0],[0,16384,0]), dx=doc.floor.tiles[1]*96;
      const delta=new T.Matrix4().makeTranslation(g.origin[0]+dx+96,g.origin[2],g.origin[1]+96).multiply(turn)
        .multiply(new T.Matrix4().makeTranslation(-g.origin[0],-g.origin[2],-g.origin[1]));
      await viewer.pasteSnapshot(clip,delta);
      // (a new project is saved with the map names the server proposes for it: output names plan)
      const name='Builder '+Date.now(), names=await fetch('/projects/output-names',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,map:viewer.mapId,target:null})}).then(r=>r.json());
      if (!await viewer.saveProject({name,output:names.output})) throw Error('Project not saved');
      return viewer.project().doc;
    }''', prefab_id)
    assert len(project['buildings'][0]['floors']) == 2
    assert any(p.get('template', {}).get('kind') == 'point' for p in project['added'])
    if screenshot: screenshot.with_name('builder-project.json').write_text(json.dumps(project), encoding='utf8', newline='\n')
    assert not errors, errors; page.close()
    return dict(prefab=prefab_id, project=project['id'], size=size)


def check_this_prefab(browser, url):
    """The builder's This prefab tab (S19): an empty prefab says so; two pieces of one kind and one of another give two
    rows with their counts; a row's click places another of that kind; deleting the last of a kind takes its row; a
    made wall and a cover block give no row; the list follows the prefab without closing the panel. In a map, This map
    is the map as exported."""
    base = url.split('?')[0]; page = browser.new_page(viewport=dict(width=1600, height=1000)); errors = []
    listen(page, errors); page.on('dialog', lambda d: d.accept())
    def ready(): page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    own = "viewer.pieces.entries().filter(e => e.inPrefab).map(e => e.count).sort()"
    def rows(): return page.evaluate(own)
    def follows(counts): page.wait_for_function(f'want => JSON.stringify({own}) === JSON.stringify(want)', arg=counts, timeout=20000)
    page.goto(base + '?prefab=new'); ready()
    tab = page.locator('#libScope [data-value="map"]')
    page.evaluate('viewer.setLibraryScope("map"); viewer.showPieces(true)')
    assert tab.is_visible() and tab.inner_text() == 'This prefab', tab.inner_text()
    assert page.locator('#libFoot').inner_text() == 'Nothing in the prefab yet: All maps has every piece of the game'
    assert rows() == []
    # Two arcade machines of the Bar and a computer of the police station, read as the Add panel's All maps reads them
    page.evaluate('viewer.setLibraryScope("all")'); page.wait_for_function('viewer.library.ready()', timeout=120000)
    page.evaluate('''async () => {
      const T = await import('three'), entries = viewer.library.entries();
      const names = [['ArcadeMachineA', 'URB_Bar'], ['Computer_A', 'URB_PoliceStation'], ['ArcadeMachineA', 'URB_Bar']];
      for (const [k, [name, map]] of names.entries()) {
        const entry = entries.find(e => e.name === name && e.source.package === map);
        if (!entry) throw Error('This prefab\\'s check needs Bar and Police Station in the library');
        const t = await viewer.libraryTemplate(entry.source), at = [-960 + k * 960, -192, 192];
        const delta = new T.Matrix4().makeTranslation(at[0], at[2], at[1]).multiply(t.frame);
        await viewer.pasteSnapshot({entries: t.sources.map(source => ({source, matrix: new T.Matrix4().fromArray(source.matrix)})), volumes: [], pivotIndex: 0}, delta);
      }
    }''')
    page.evaluate('viewer.setLibraryScope("map")')
    assert rows() == [1, 2], rows()
    assert page.locator('#libList .libitem .tag', has_text='×2').count() == 1
    page.wait_for_function("Array.from(document.querySelectorAll('#libList canvas')).every(c => c.dataset.drawn)", timeout=30000)
    assert 'in this prefab' in page.locator('#libList .libitem .tag', has_text='×2').get_attribute('title')
    # A row's click puts a copy on the cursor; a click in the view places it, and the list follows
    pair = page.evaluate('viewer.pieces.entries().find(e => e.inPrefab && e.count === 2).id')
    page.locator(f'#libList .libitem[data-id="{pair}"]').click()
    assert page.evaluate('Boolean(viewer.placing())')
    page.evaluate('viewer.frame()')
    box = page.locator('#viewport > canvas').bounding_box()
    page.mouse.move(box['x'] + box['width'] * 0.3, box['y'] + box['height'] * 0.7)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(box['x'] + box['width'] * 0.3, box['y'] + box['height'] * 0.7)
    follows([1, 3])
    # (the copy is in no group, as its original is in none: a row is a piece)
    assert page.evaluate('viewer.groupList().length') == 0
    # Deleting the last of a kind takes its row
    lone = page.evaluate('viewer.pieces.entries().find(e => e.inPrefab && e.count === 1).sources.map(s => s.id)')
    page.evaluate('ids => { viewer.gizmo.setSelection(ids, ids[0]); document.activeElement?.blur(); }', lone)
    page.keyboard.press('Delete')
    follows([3])
    page.keyboard.press('Control+z')
    follows([1, 3])
    # A made wall and a cover block give no row
    import browser_walls as bw
    page.evaluate('viewer.showPieces(false)')
    bw.start_build(page, 'wall'); bw.look_at(page, [0, 960, 0])
    bw.drag(page, bw.ground_point(page, [-192, 960, 0]), bw.ground_point(page, [192, 960, 0]))
    page.wait_for_function("viewer.wallState(viewer.gizmo.active)?.generated?.kind === 'fracWall'", timeout=60000)
    page.keyboard.press('Escape')
    page.evaluate('viewer.showPieces(true)')
    cover = page.evaluate("viewer.pieces.entries().find(e => e.cover && e.cover.type !== 'floor').id")
    page.locator(f'#libList .libitem[data-id="{cover}"]').click()
    page.mouse.move(box['x'] + box['width'] * 0.6, box['y'] + box['height'] * 0.4)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(box['x'] + box['width'] * 0.6, box['y'] + box['height'] * 0.4)
    page.wait_for_function('[...viewer.roots.values()].some(r => r.userData.source.cover)')
    page.wait_for_timeout(300)
    assert rows() == [1, 3], rows()
    page.close()
    # In a map, This map is the map as exported: a copy placed adds no row, and none is the prefab's
    page = browser.new_page(viewport=dict(width=1600, height=1000)); listen(page, errors); page.on('dialog', lambda d: d.accept())
    page.goto(base + '?map=URB_Bar'); ready()
    page.evaluate('viewer.setLibraryScope("map"); viewer.showPieces(true)')
    assert page.locator('#libScope [data-value="map"]').inner_text() == 'This map'
    before = page.evaluate('viewer.pieces.entries().map(e => [e.key, e.count])')
    assert before and not page.evaluate('viewer.pieces.entries().some(e => e.inPrefab)')
    page.evaluate('''async () => { const T = await import('three'); const r = [...viewer.roots.values()].find(r => !r.userData.source.added && !r.userData.source.hidden);
      viewer.gizmo.setSelection([r.userData.source.id]); await viewer.pasteSnapshot(viewer.snapshot(), new T.Matrix4().makeTranslation(96, 0, 96)); }''')
    page.evaluate('viewer.showPieces(false); viewer.showPieces(true)')
    assert page.evaluate('viewer.pieces.entries().map(e => [e.key, e.count])') == before
    assert not errors, errors
    page.close()
    return dict(rows=[1, 3])


def check_navigation(browser, url, source_id, project_id):
    base = url.split('?')[0]; page = browser.new_page(viewport=dict(width=1600, height=1000)); errors, prompts = [], []
    listen(page, errors, expected=(500, 409))      # (the failed and stale writes below are the check's own)
    page.on('dialog', lambda d: (prompts.append(d.type), d.accept()))
    def open_source():
        page.goto(base+'?prefab='+source_id)
        page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    def changed(): page.evaluate('viewer.addVolumes([{box:[384,0,0,480,96,192],floor:0}])')
    def go(target):     # (goTo's answer is kept: true when it left, false when it stayed)
        page.evaluate('target=>{ window.goToAnswer = viewer.goTo(target); }', target); page.locator('#leaveDialog').wait_for(state='visible')
    open_source()
    source = page.evaluate('viewer.builderDocument()')
    target = page.evaluate('''async () => { const d=await viewer.prefabApi.load(viewer.builderDocument().id);
      d.id=crypto.randomUUID(); d.name='Replacement target '+Date.now(); await viewer.prefabApi.save(d.id,d,0); return d; }''')
    changed()
    def save_as(name):
        page.locator('#mapButton').click(); page.locator('#docPrefabSaveAs').click(); page.locator('#prefabName').fill(name)
    save_as(target['name'])
    page.wait_for_function('document.querySelector("#prefabOk").textContent === "Replace"')
    page.locator('#prefabOk').click(); assert page.locator('#prefabOk').inner_text() == 'Confirm replacement'
    page.locator('#prefabCancel').click()
    assert page.evaluate('viewer.builderDocument().id') == source_id
    assert page.evaluate('id=>viewer.prefabApi.load(id).then(d=>d.revision)', target['id']) == 1
    save_as(target['name']); page.wait_for_function('document.querySelector("#prefabOk").textContent === "Replace"')
    page.locator('#prefabOk').click(); page.locator('#prefabOk').click(); page.wait_for_url('**/?prefab='+target['id'])
    assert not page.evaluate('viewer.dirty()')
    assert page.evaluate('id=>viewer.prefabApi.load(id).then(d=>d.revision)', source_id) == source['revision']
    save_as(target['name']+' copy'); page.locator('#prefabOk').click()
    page.wait_for_function('id=>viewer.builderDocument().id !== id', arg=target['id'])
    assert page.evaluate('id=>viewer.prefabApi.load(id).then(d=>d.revision)', target['id']) == 2
    # Same guard for all editor navigation destinations, with actual successful saves and discards.
    destinations = [dict(prefab=target['id']), dict(map='URB_Bar', project=None), dict(map='URB_Bar', project=project_id)]
    for destination in destinations:
        open_source(); changed(); before = page.evaluate('viewer.builderDocument()'); old_url = page.url
        go(destination); page.locator('#leaveCancel').click()
        assert page.url == old_url and page.evaluate('viewer.dirty()')
        go(destination); count = len(prompts); page.locator('#leaveSave').click()
        page.wait_for_url(lambda u: str(u) != old_url, timeout=60000)
        page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
        assert len(prompts) == count
        saved = page.evaluate('id=>viewer.prefabApi.load(id)', source_id)
        assert saved['revision'] == before['revision']+1
        open_source(); changed(); page.evaluate('viewer.keepRecovery()')
        old_url = page.url; go(destination); count = len(prompts); page.locator('#leaveDiscard').click()
        page.wait_for_url(lambda u: str(u) != old_url, timeout=60000)
        page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
        assert len(prompts) == count
        assert page.evaluate('id=>viewer.prefabApi.recovery(id)', source_id) is None
    # A failed server write and a conflict both retain the dirty scene, without a second prompt.
    open_source(); changed()
    route = '**/prefabs/'+source_id+'/prefab.json'
    for status, body in [(500, dict(error='Simulated write failure')), (409, dict(error='Stale revision', revision=999))]:
        page.route(route, lambda r: r.fulfill(status=status, json=body) if r.request.method=='PUT' else r.continue_())
        old_url = page.url; go(dict(prefab=target['id'])); page.locator('#leaveSave').click()
        assert page.evaluate('window.goToAnswer') is False      # it stayed, the save having failed
        assert page.url == old_url and page.evaluate('viewer.dirty()')
        page.unroute(route)
    go(dict(prefab='new')); page.locator('#leaveDiscard').click(); page.wait_for_url('**/?prefab=new')
    page.wait_for_function('window.viewer && document.querySelector("#loading").hidden')
    changed(); go(dict(map='URB_Bar', project=None)); page.locator('#leaveSave').click()
    page.locator('#prefabDialog').wait_for(state='visible'); page.locator('#prefabCancel').click()
    assert 'prefab=new' in page.url and page.evaluate('viewer.dirty()')
    # A map with unnamed edits asks for a project name, waits for it, and only then opens the prefab.
    go(dict(map='URB_Bar', project=None)); page.locator('#leaveDiscard').click()
    page.wait_for_url('**/?map=URB_Bar'); page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    changed(); go(dict(prefab=source_id)); page.locator('#leaveSave').click()
    page.locator('#fileDialog').wait_for(state='visible'); page.locator('#fileCancel').click()
    assert 'map=URB_Bar' in page.url
    go(dict(prefab=source_id)); page.locator('#leaveSave').click()
    page.locator('#fileName').fill('Navigation project '+str(time.time_ns())); count=len(prompts); page.locator('#fileOk').click()
    page.wait_for_url('**/?prefab='+source_id, timeout=60000)
    assert len(prompts) == count
    assert not errors, errors; page.close()
    return dict(destinations=3, saveAsReplacement=True, failuresRetainScene=True, errors=errors)


def check_recovery_edges(browser, url, box_id):
    base = url.split('?')[0]; page = browser.new_page(viewport=dict(width=1600, height=1000)); errors = []
    # (404s are the check's own: an unavailable map's piece, and a draft asked for after it is gone)
    listen(page, errors, expected=(404,)); page.on('dialog', lambda d: d.accept())
    def ready(): page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    page.goto(base+'?prefab='+box_id); ready()
    before = page.evaluate('viewer.buildings().length')
    page.evaluate('viewer.addVolumes([{box:[192,0,0,288,96,192],floor:0}]); viewer.keepRecovery()')
    page.reload(); ready(); page.locator('#projectBanner').get_by_role('button', name='Restore them').click()
    page.wait_for_function('count => viewer.buildings().length === count + 1', arg=before)
    assert page.evaluate('viewer.saveBuilder()')
    # A missing-only document still opens, saves and recovers as a complete prefab.
    missing_id = page.evaluate('''async () => {
      const {newPrefab}=await import('/prefabs.js'), id=crypto.randomUUID();
      const doc=newPrefab(id,'Missing-only '+Date.now(),{tiles:[2,2],groups:[],buildings:[],donors:[{package:'UnavailableBuilderMap'}],pieces:[
        {actor:'TheWorld.PersistentLevel.Kept_copy300',from:{package:'UnavailableBuilderMap',level:'base',actor:'TheWorld.PersistentLevel.Kept'},
         components:['TheWorld.PersistentLevel.Kept.StaticMeshComponent_0'],location:[96,96,64],rotation:[0,0,0],prefab:null,partner:null,
         recipe:{key:'kept',name:'Unavailable source'}}]});
      await viewer.prefabApi.importFile(doc); return id;
    }''')
    page.goto(base+'?prefab='+missing_id); ready()
    assert page.evaluate('viewer.roots.size === 0 && viewer.builderDocument().pieces.length === 1')
    assert page.evaluate('viewer.saveBuilder()')
    route = '**/prefabs/'+missing_id+'/recovery.json'
    delayed = []
    def hold_write(r):
        if r.request.method == 'PUT': time.sleep(0.3); delayed.append(True)
        r.continue_()
    page.route(route, hold_write)
    # (the save done, and the held draft's write answered too: a draft it brought back after the save would show)
    put = lambda r: r.request.method == 'PUT' and '/prefabs/'+missing_id+'/recovery.json' in r.url  # noqa: E731
    with page.expect_response(put):
        page.evaluate('viewer.addVolumes([{box:[-96,0,0,0,96,192],floor:0}]); void viewer.keepRecovery(); window.delayedSave=viewer.saveBuilder()')
        assert page.evaluate('window.delayedSave')
    assert delayed and page.evaluate('id=>viewer.prefabApi.recovery(id)', missing_id) is None
    page.evaluate('viewer.addVolumes([{box:[-192,0,0,-96,96,192],floor:0}]); void viewer.keepRecovery(); void viewer.goTo({prefab:"new"})')
    page.locator('#leaveDiscard').click(); page.wait_for_url('**/?prefab=new'); ready()
    assert len(delayed) >= 2 and page.evaluate('id=>viewer.prefabApi.recovery(id)', missing_id) is None
    assert not errors, errors; page.close()
    return dict(missingOnly=True, buildingOnly=True, delayedWritesOrdered=True, errors=errors)


def check_large_builder(browser, url):
    base = url.split('?')[0]; page = browser.new_page(viewport=dict(width=1600, height=1000)); errors = []
    listen(page, errors); page.on('dialog', lambda d: d.accept())
    page.goto(base+'?map=URB_Bar'); page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=120000)
    selection = page.evaluate('''() => {
      viewer.setBoxesShown(true); viewer.setNormalLights(true);
      const buildings=viewer.data.buildings, volume=b=>b.floors.flatMap(f=>f.boxes).reduce((n,v)=>n+(v.max[0]-v.min[0])*(v.max[1]-v.min[1]),0);
      const building=[...buildings].sort((a,b)=>volume(b)-volume(a))[0], boxes=building.floors.flatMap(f=>f.boxes);
      const box=[0,1,2].map(k=>Math.min(...boxes.map(b=>b.min[k]))-1).concat([0,1,2].map(k=>Math.max(...boxes.map(b=>b.max[k]))+1));
      viewer.setPickBox(box); viewer.takePickBox();
      const records=viewer.prefabRecords(); return {pieces:records.pieces.length,buildings:records.buildings.length,size:records.size};
    }''')
    assert selection['pieces'] > 100 and selection['buildings'] > 0, selection
    saved = page.evaluate('viewer.savePrefab("Builder whole Bar "+Date.now())')
    doc = page.evaluate('id=>viewer.prefabApi.load(id)', saved['id'])
    began = time.monotonic(); page.goto(base+'?prefab='+saved['id'])
    page.wait_for_function('window.viewer && document.querySelector("#loading").hidden', timeout=240000)
    elapsed = round(time.monotonic()-began, 2)
    assert page.evaluate('viewer.builderRecords().size.verified && !viewer.dirty()')
    assert page.evaluate('viewer.saveBuilder()')
    again = page.evaluate('id=>viewer.prefabApi.load(id)', saved['id'])
    assert {p['actor']:p for p in doc['pieces']} == {p['actor']:p for p in again['pieces']}
    assert doc['groups'] == again['groups'] and doc['buildings'] == again['buildings']
    assert not errors, errors; page.close()
    return dict(**selection, openSeconds=elapsed)


if __name__ == '__main__': main()
