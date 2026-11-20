"""The test hooks' names: window.viewer's names on the Bar, on the blank map and in the prefab builder, against the
lists recorded in viewer_api_names.json beside this (editor refactor, item 0.4: a page module moved leaves the hooks
the checks use as they were).

browser_smoke.py --url <test server> --write-api-names writes the lists; its check api-names (in the whole run, and so
in --all) compares them and fails naming each name missing or added. A name added or taken out on purpose is written
into the file in the same commit as the change.
"""
import json
from pathlib import Path

RECORD = Path(__file__).with_name('viewer_api_names.json')
# Each place the names are read: its page (from the server's root), and what says the page has opened there. The
# blank map is the game's CB2_MP_Blank (exported on its first open if the cache lacks it: up to a few minutes).
PLACES = {
    'bar': ('?map=URB_Bar', "viewer.mapId === 'URB_Bar' && !viewer.builderMode"),
    'blank': ('?map=CB2_MP_Blank', "viewer.mapId === 'CB2_MP_Blank' && !viewer.builderMode"),
    'builder': ('?prefab=new', 'viewer.builderMode'),
}
MAPS = ('URB_Bar', 'CB2_MP_Blank')


def read(browser, url, errors):
    """{place: window.viewer's names, sorted} from the server `url` names, each place in a page of its own (one
    context of their own, so that no page of the run shares their storage); the pages' errors go into `errors`."""
    base = url.split('?')[0].rstrip('/') + '/'
    context = browser.new_context(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    try:
        listed = {m['id'] for m in context.request.get(base + 'maps.json').json()['maps']}
        absent = [m for m in MAPS if m not in listed]
        assert not absent, f'the server lists no {", ".join(absent)}: the hooks\' names are read on {", ".join(MAPS)} and in the builder'
        names = {}
        for place, (query, opened) in PLACES.items():
            page = context.new_page()
            page.on('pageerror', lambda e: errors.add(str(e)))
            page.on('console', lambda m: errors.add(m.text) if m.type == 'error' else None)
            page.goto(base + query)
            page.wait_for_function(f"window.viewer && document.querySelector('#loading').hidden && {opened}", timeout=300000)
            names[place] = sorted(page.evaluate('Object.keys(window.viewer)'))
            page.close()
        return names
    finally:
        context.close()


def differences(recorded, now):
    """Each place's names missing from `now` and added to it, against `recorded` (a place of either side alone too)."""
    out = []
    for place in sorted(set(recorded) | set(now)):
        was, got = set(recorded.get(place, ())), set(now.get(place, ()))
        if place not in now: out.append(f'{place}: not read')
        elif place not in recorded: out.append(f'{place}: not recorded')
        if was - got and place in now: out.append(f'{place}: missing {", ".join(sorted(was - got))}')
        if got - was and place in recorded: out.append(f'{place}: added {", ".join(sorted(got - was))}')
    return out


def check(ctx):
    """browser_smoke's api-names check: the names now, against the record."""
    now = read(ctx.browser, ctx.page.url, ctx.errors)
    recorded = json.loads(RECORD.read_text(encoding='utf-8'))
    wrong = differences(recorded, now)
    assert not wrong, (f"window.viewer's names differ from {RECORD.name}: " + '; '.join(wrong) + '. A name added or taken out '
                       f'on purpose: write the lists again (browser_smoke.py --url <test server> --write-api-names) and '
                       f'commit {RECORD.name} with the change')
    return {place: len(names) for place, names in now.items()}


def write(url):
    """--write-api-names: the names now, written into the record (refused if a page had an error)."""
    from playwright.sync_api import sync_playwright
    errors = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        try:
            now = read(browser, url, errors)
        finally:
            browser.close()
    if errors: raise SystemExit('not written: the pages had errors:\n' + '\n'.join(sorted(errors)))
    old = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.is_file() else {}
    RECORD.write_text(json.dumps(now, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'{RECORD.name}: ' + ', '.join(f'{place} {len(names)}' for place, names in now.items())
          + ''.join(f'\n  {line}' for line in differences(old, now)))
