"""Exercise the map browser (every LWR map, by mission type), independent layouts, URLs and browser history.

--prepare MAP also opens a map not exported yet and waits for the server to export it (export on first open); point
that at a test server on a scratch cache root, since the export lands in the cache it serves.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from playwright.sync_api import sync_playwright


def ready(page,map_id,preview=False,timeout=120000):
    page.wait_for_function("""expected=>window.viewer && document.querySelector('#loading').hidden
      && viewer.mapId===expected.map && Boolean(viewer.data.preview)===expected.preview""",
      arg=dict(map=map_id,preview=preview),timeout=timeout)
    label=page.evaluate("id=>fetch('/maps.json').then(r=>r.json()).then(c=>c.maps.find(m=>m.id===id).label)",map_id)
    assert page.locator('#mapTitle').text_content()==label,(page.locator('#mapTitle').text_content(),label)
    assert page.evaluate('viewer.roots.size===viewer.data.objects.length+viewer.streamPieces')


def select(page,control,value):
    with page.expect_navigation(wait_until='load'):page.locator(control).select_option(value)


def rows(page):
    return page.locator('#mapList .maprow')


def pick(page,map_id):
    """Open the map browser, choose the map, and open it."""
    if page.locator('#mapDialog').is_hidden():
        page.locator('#mapButton').click()     # the Map menu, or the browser itself where the menu would hold one item
        if page.locator('#mapMenu').is_visible():page.locator('#mapChange').click()
    page.locator('#mapSearch').fill('')
    page.locator('#mapGroups [data-group="all"]').click()
    page.locator(f'#mapList .maprow[data-id="{map_id}"]').first.click()
    with page.expect_navigation(wait_until='load'):page.locator('#mapOk').click()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',required=True,help='a test server, as http://127.0.0.1:<port>/ (never 8768, the main server)')
    ap.add_argument('--screenshot',type=Path,required=True)
    ap.add_argument('--prepare',help='Also open this map, not exported yet, and wait for its export (scratch caches only)')
    args=ap.parse_args();args.screenshot.parent.mkdir(parents=True,exist_ok=True)
    url=urlsplit(args.url);base=urlunsplit((url.scheme,url.netloc,'/','',''))
    if url.port==8768:ap.error('8768 is the main server, the one the user keeps open: check a test server (8790-8799)')
    errors=set();requests=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport=dict(width=1600,height=1000))
        page.on('pageerror',lambda e:errors.add(str(e)))
        page.on('console',lambda m:errors.add(m.text) if m.type=='error' else None)
        page.on('requestfailed',lambda r:errors.add(f'{r.url}: {r.failure}'))
        page.on('response',lambda r:errors.add(f'HTTP {r.status}: {r.url}') if r.status>=400 else None)
        page.on('request',lambda r:requests.append(urlsplit(r.url).path))
        page.goto(base+'?map=URB_Bar');ready(page,'URB_Bar')
        catalogue=page.evaluate("fetch('/maps.json').then(r=>r.json())")
        maps={m['id']:m for m in catalogue['maps']}
        assert {'URB_Bar','TempleShip'}<=set(maps) and maps['URB_Bar']['ready'] and maps['TempleShip']['checked']
        assert page.locator('#scene').count()==0 and page.locator('#building').count()==0   # no layout or building menus

        # The browser: sections by mission type, a map under each type it serves, search, the type chips.
        page.keyboard.press('m')
        assert page.locator('#mapDialog').is_visible()
        assert page.locator('#mapSearch').evaluate('e=>e===document.activeElement')
        sections=page.locator('#mapList .mapgroup').all_text_contents()
        groups={g for m in maps.values() for g in m['groups']}
        # (a section of the prefab library's own comes first where there are prefabs: it is no mission type)
        assert len([t for t in sections if not t.startswith('Prefabs')])==len(groups),(sections,groups)
        several=next((m for m in maps.values() if len(m['groups'])>1),None)
        if several:assert page.locator(f'#mapList .maprow[data-id="{several["id"]}"]').count()==len(several['groups'])
        assert page.locator('#mapList .maprow[data-id="URB_Bar"].on').count()>=1   # starts on the open map
        assert page.locator('#mapList .maprow[data-id="URB_Bar"] small').first.text_content()=='open'
        assert page.locator('#mapOk').is_disabled()
        page.locator('#mapSearch').fill('temple ship')
        assert [r.get_attribute('data-id') for r in rows(page).all()]==['TempleShip']
        assert 'Checked' in rows(page).first.locator('.mstate').text_content()
        page.locator('#mapSearch').fill('')
        for group in sorted(groups):
            page.locator(f'#mapGroups [data-group="{group}"]').click()
            shown={r.get_attribute('data-id') for r in rows(page).all()}
            assert shown=={m['id'] for m in maps.values() if group in m['groups']},group
        page.locator('#mapGroups [data-group="all"]').click()
        page.locator('#mapPrepared').check()
        assert {r.get_attribute('data-id') for r in rows(page).all()}&set(maps)=={m['id'] for m in maps.values() if m['ready']}   # (prefabs' rows aside)
        page.locator('#mapPrepared').uncheck()
        page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-browser')))
        page.keyboard.press('Escape')
        assert page.locator('#mapDialog').is_hidden()

        if page.locator('#viewOptions').is_hidden():page.locator('#viewButton').click()   # Wireframe is in View options
        page.locator('#wire').check()
        requests.clear();pick(page,'TempleShip');ready(page,'TempleShip')
        assert 'scene=' not in page.url
        assert not page.evaluate('Boolean(viewer.data.preview)')
        assert page.evaluate("document.getElementById('scenery').value")=='interior'
        assert not page.locator('#wire').is_checked()
        assert page.locator('#helpersRow').is_hidden()   # Temple has no inherited patch helpers
        assert all(path.startswith('/cache/TempleShip/') for path in requests if path.startswith('/cache/'))
        page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-temple')))
        page.reload();ready(page,'TempleShip')
        requests.clear();pick(page,'URB_Bar');ready(page,'URB_Bar')
        assert not page.evaluate('Boolean(viewer.data.preview)')
        assert page.evaluate("document.getElementById('scenery').value")=='full'
        assert 'scene=' not in page.url
        assert all(path.startswith('/cache/URB_Bar/') for path in requests if path.startswith('/cache/'))
        page.screenshot(path=str(args.screenshot))
        # a patch preview, where this cache has the Bar's (made by the lab's tools: most caches have none)
        preview=page.request.head(base+'cache/URB_Bar/preview-1.json').ok   # (asked outside the page: no console error)
        if preview:
            page.goto(base+'?map=URB_Bar&scene=preview-1.json');ready(page,'URB_Bar',True)   # previews open by address only
            assert 'map=URB_Bar' in page.url and 'scene=preview-1.json' in page.url
            page.go_back(wait_until='load');ready(page,'URB_Bar')
            page.go_forward(wait_until='load');ready(page,'URB_Bar',True)
            pick(page,'TempleShip');ready(page,'TempleShip')
            page.go_back(wait_until='load');ready(page,'URB_Bar',True)
        page.set_viewport_size(dict(width=1000,height=800))
        assert page.evaluate("""() => ['mapButton'].every(id=>{
          const r=document.getElementById(id).getBoundingClientRect();return r.width>70 && r.left>=0 && r.right<=innerWidth;
        })""")
        page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-compact')))

        # A map that isn't listed opens the browser with a note; choosing one opens it.
        recovery=browser.new_page()
        recovery.goto(base+'?map=NotListed')
        recovery.wait_for_selector('#mapDialog:not([hidden])')
        assert 'NotListed' in recovery.locator('#mapMessage').text_content()
        pick(recovery,'TempleShip');ready(recovery,'TempleShip');recovery.close()

        prepared=None
        if args.prepare:
            # Export on first open: the browser prepares the map asked for, then the page opens it.
            assert not maps[args.prepare]['ready'],f'{args.prepare} is already exported here'
            fresh=browser.new_page(viewport=dict(width=1600,height=1000))
            fresh.on('pageerror',lambda e:errors.add(str(e)))
            fresh.goto(base+f'?map={args.prepare}')
            fresh.wait_for_selector('#mapDialog:not([hidden])')
            fresh.wait_for_function("document.querySelector('#mapMessage').textContent.startsWith('Preparing')")
            fresh.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-preparing')))
            ready(fresh,args.prepare,timeout=300000)
            prepared=dict(map=args.prepare,objects=fresh.evaluate('viewer.data.objects.length'))
            fresh.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-prepared')))
            fresh.close()
        result=dict(maps=len(maps),ready=sorted(m for m in maps if maps[m]['ready']),sections=sections,
                    switched=True,layoutReset=True,history=True,compactHeader=True,prepared=prepared,errors=sorted(errors))
        args.screenshot.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf8',newline='\n')
        print(json.dumps(result,indent=2));browser.close()
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
