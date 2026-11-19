"""The Map picture dialog in the browser (map_picture.js; LWR map packs plan, 4.2 and 4.5), on a test server with a
scratch projects folder (it saves a project):

  python tools/viewer/tests/browser_map_picture.py --url http://127.0.0.1:<port> [--map URB_Bar] [--shots <folder>]

With no project open the menu item asks for a save first. With one: the dialog shows what the game shows now (the base
map's picture, where the install has one) with nothing to use or remove; an image chosen gets the largest 2:1 frame
around its middle; the frame is dragged, resized by a corner and by the wheel and stays inside the image; the result
is drawn at 512 x 256; Use this picture keeps it and marks the project changed, and the next save names it by its
SHA-256; the project manager's row says "own picture"; the dialog then shows the map's own picture and Remove picture
takes it away; a file dropped on the dialog is taken as a chosen one is; Take from the view gives the 3D view as the
image, its helpers hidden for that frame. No game is started and nothing is built.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright


def picture_file(folder, size=(1600, 900)):
    """A made-up image to crop: four coloured quarters under a gradient."""
    w, h = size
    image = Image.new('RGB', size)
    for k, colour in enumerate([(200, 60, 40), (40, 160, 70), (50, 80, 200), (220, 200, 60)]):
        image.paste(colour, ((k % 2) * w // 2, (k // 2) * h // 2, (k % 2 + 1) * w // 2, (k // 2 + 1) * h // 2))
    path = Path(folder) / 'chosen picture.png'
    image.save(path)
    return path


def state(page):
    return page.evaluate('viewer.mapPicture.state()')


def sound(s):
    f = s['frame']
    assert abs(f['w'] - 2 * f['h']) < 1e-6, f
    assert f['x'] >= -1e-6 and f['y'] >= -1e-6 and f['x'] + f['w'] <= s['width'] + 1e-6 and f['y'] + f['h'] <= s['height'] + 1e-6, s
    return f


def result_pixels(page):
    """The result canvas's mean colour and whether anything is drawn on it."""
    return page.evaluate("""() => {
      const c = document.getElementById('mapPictureResult'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let r = 0, g = 0, b = 0;
      for (let k = 0; k < d.length; k += 4) { r += d[k]; g += d[k + 1]; b += d[k + 2]; }
      const n = d.length / 4;
      return { mean: [r / n, g / n, b / n], drawn: r + g + b > 0, size: [c.width, c.height] };
    }""")


def open_dialog(page):
    page.locator('#mapButton').click()
    page.locator('#projectPicture').click()
    page.wait_for_selector('#mapPictureDialog:not([hidden])')


def canvas_box(page):
    return page.locator('#mapPictureCanvas').bounding_box()


def check(page, base, map_id, shots, errors):
    out = {}
    name = 'Picture check ' + datetime.now().strftime('%H%M%S')     # (a name no earlier run of the check left)
    page.goto(f'{base}/?map={map_id}', wait_until='load')
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
    # no project: the item is there and asks for a save
    page.locator('#mapButton').click()
    assert page.locator('#projectPicture').is_visible()
    page.locator('#projectPicture').click()
    assert page.locator('#mapPictureDialog').is_hidden()
    assert 'Save the project first' in page.locator('#projectBanner').inner_text()
    # a project
    page.locator('#projectButton').click()
    page.locator('#projectSaveAs').click()
    page.wait_for_selector('#fileDialog:not([hidden]) .filerow, #fileDialog:not([hidden]) .filelist .empty')
    page.locator('#fileName').fill(name)
    page.wait_for_function("() => !document.getElementById('fileOk').disabled")
    page.locator('#fileName').press('Enter')
    page.wait_for_function("viewer.project()?.revision === 1", timeout=60000)
    project = page.evaluate('viewer.project().id')

    # the dialog with no picture of the project's own
    open_dialog(page)
    assert page.locator('#mapPictureTitle').inner_text() == f'Map picture of {name}'
    assert page.locator('#mapPictureUse').is_disabled() and page.locator('#mapPictureRemove').is_disabled()
    assert page.locator('#mapPictureCanvas').is_hidden() and page.locator('#mapPictureEmpty').is_visible()
    page.wait_for_function("document.getElementById('mapPictureResultNote').textContent.length > 0", timeout=30000)
    note = page.locator('#mapPictureResultNote').inner_text()
    base_shown = 'borrows' in note
    assert base_shown or 'the game has none' in note, note
    if base_shown:
        page.wait_for_function("""() => { const c = document.getElementById('mapPictureResult');
          return c.getContext('2d').getImageData(0, 0, c.width, c.height).data.some((v, k) => k % 4 < 3 && v > 0); }""", timeout=30000)
    out['base'] = note
    if shots: page.screenshot(path=str(shots / 'map-picture-1-base.png'))

    # an image chosen: the largest 2:1 frame around the middle
    with tempfile.TemporaryDirectory() as folder:
        chosen = picture_file(folder)
        page.set_input_files('#mapPictureFile', str(chosen))
        page.wait_for_function('viewer.mapPicture.state() !== null')
        s = state(page)
        assert (s['width'], s['height']) == (1600, 900) and s['frame'] == dict(x=0, y=50, w=1600, h=800), s
        assert page.locator('#mapPictureCanvas').is_visible() and page.locator('#mapPictureEmpty').is_hidden()
        assert not page.locator('#mapPictureUse').is_disabled()
        box = canvas_box(page)
        scale = box['width'] / 1600
        assert abs(box['height'] - 900 * scale) < 2 and box['width'] <= 513, box
        # dragged down: stopped at the image's bottom
        cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        page.mouse.move(cx, cy); page.mouse.down(); page.mouse.move(cx + 30, cy + 200, steps=4); page.mouse.up()
        f = sound(state(page))
        assert (f['x'], f['y'], f['w']) == (0, 100, 1600), f
        # its top left corner dragged in: smaller, the bottom right corner where it was
        page.mouse.move(box['x'] + 1, box['y'] + 100 * scale + 1); page.mouse.down()
        page.mouse.move(box['x'] + 800 * scale, box['y'] + 500 * scale, steps=4); page.mouse.up()
        f = sound(state(page))
        assert abs(f['x'] + f['w'] - 1600) < 1e-6 and abs(f['y'] + f['h'] - 900) < 1e-6 and 700 < f['w'] < 900, f
        # moved up and left, then the wheel: larger and smaller about the pointer, never out of the image
        mx, my = box['x'] + (f['x'] + f['w'] / 2) * scale, box['y'] + (f['y'] + f['h'] / 2) * scale
        page.mouse.move(mx, my); page.mouse.down(); page.mouse.move(mx - 120, my - 90, steps=4); page.mouse.up()
        moved = sound(state(page))
        assert moved['x'] < f['x'] and moved['y'] < f['y'] and abs(moved['w'] - f['w']) < 1e-6, (f, moved)
        page.mouse.move(box['x'] + 20, box['y'] + 20)
        for _ in range(60): page.mouse.wheel(0, 120)
        page.wait_for_function('viewer.mapPicture.state().frame.w === 1600')     # (the wheel's events arrive one by one)
        wide = sound(state(page))
        assert abs(wide['w'] - 1600) < 1e-6, wide
        for _ in range(12): page.mouse.wheel(0, -120)
        page.wait_for_function('viewer.mapPicture.state().frame.w < 800')
        page.wait_for_timeout(300)
        f = sound(state(page))
        assert 500 < f['w'] < 800, f
        # the keyboard: arrows move it
        page.locator('#mapPictureCanvas').focus()
        page.keyboard.press('ArrowRight'); page.keyboard.press('ArrowDown')
        keyed = sound(state(page))
        assert keyed['x'] > f['x'] and keyed['y'] > f['y'], (f, keyed)
        # the result, 512 x 256, drawn from the frame: its top left quarter of the image is red
        page.mouse.move(box['x'] + 5, box['y'] + 5)
        for _ in range(80): page.mouse.wheel(0, -120)
        page.wait_for_function('viewer.mapPicture.state().frame.w === 32')
        page.mouse.move(box['x'] + 2, box['y'] + 2)
        page.mouse.down(); page.mouse.move(box['x'] - 300, box['y'] - 300, steps=3); page.mouse.up()
        f = sound(state(page))
        # (so small a frame is all corner: the drag resized it from its top left, as far as the image's corner let it)
        assert f['w'] < 100 and f['x'] == 0 and f['y'] < 20, f
        page.wait_for_timeout(900)      # (the server's answer for the frame, after its short wait)
        pixels = result_pixels(page)
        assert pixels['size'] == [512, 256] and pixels['mean'][0] > 150 and pixels['mean'][2] < 90, pixels
        page.mouse.move(box['x'] + 5, box['y'] + 5)
        for _ in range(80): page.mouse.wheel(0, 120)
        page.wait_for_function('viewer.mapPicture.state().frame.w === 1600')
        page.wait_for_timeout(900)
        pixels = result_pixels(page)
        assert pixels['drawn'] and 90 < pixels['mean'][0] < 170, pixels
        out['frame'] = sound(state(page))
        if shots: page.screenshot(path=str(shots / 'map-picture-2-crop.png'))

        # Use this picture: kept by the server, the project changed, named by the next save
        page.locator('#mapPictureUse').click()
        page.wait_for_selector('#mapPictureDialog', state='hidden')
        page.wait_for_function('viewer.project().dirty')
        page.keyboard.press('Control+s')
        page.wait_for_function('viewer.project().revision === 2 && !viewer.project().dirty', timeout=60000)
        doc = page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", project)
        digest = doc['picture']['sha256']
        kept = page.evaluate("""async ([id, sha]) => {
          const blob = await (await fetch(`/projects/${id}/picture.png?sha256=${sha}`)).blob();
          const image = await createImageBitmap(blob);
          const hash = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
          return { size: [image.width, image.height], sha: [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('') };
        }""", [project, digest])
        assert kept == dict(size=[512, 256], sha=digest), (kept, digest)
        out['kept'] = digest

        # the manager's row says whose picture it is
        page.locator('#projectButton').click()
        page.locator('#projectManage').click()
        page.wait_for_selector('#managerDialog:not([hidden]) .mrow')
        meta = page.locator('#managerList .mrow', has_text=name).locator('.pmmeta').inner_text()
        assert meta.endswith('own picture'), meta
        out['manager'] = meta
        page.locator('#managerClose').click()

        # opened again: the map's own picture, and it can be removed
        open_dialog(page)
        page.wait_for_function("document.getElementById('mapPictureResultNote').textContent.includes('own picture')", timeout=30000)
        assert not page.locator('#mapPictureRemove').is_disabled() and page.locator('#mapPictureUse').is_disabled()
        page.wait_for_function("""() => { const c = document.getElementById('mapPictureResult');
          return c.getContext('2d').getImageData(0, 0, c.width, c.height).data.some((v, k) => k % 4 < 3 && v > 0); }""", timeout=30000)
        if shots: page.screenshot(path=str(shots / 'map-picture-3-own.png'))

        # a file dropped on the dialog is taken as a chosen one
        data = list(chosen.read_bytes())
        page.evaluate("""bytes => {
          const transfer = new DataTransfer();
          transfer.items.add(new File([new Uint8Array(bytes)], 'dropped.png', { type: 'image/png' }));
          const form = document.getElementById('mapPictureForm');
          for (const type of ['dragenter', 'dragover', 'drop'])
            form.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: transfer }));
        }""", data)
        page.wait_for_function('viewer.mapPicture.state() !== null')
        assert state(page)['frame'] == dict(x=0, y=50, w=1600, h=800)
        # a file that is no image says so and changes nothing
        page.set_input_files('#mapPictureFile', files=[dict(name='notes.txt', mimeType='text/plain', buffer=b'not an image')])
        page.wait_for_function("document.getElementById('mapPictureStatus').textContent.includes('not an image')")
        assert state(page)['frame'] == dict(x=0, y=50, w=1600, h=800)

        # Take from the view: the 3D view as the image (stage C8), where the dialog offers it
        if page.locator('#mapPictureTake').is_visible():
            # (the helpers are hidden only for the frame taken: what shows in the view is as before afterwards)
            shown = "viewer.world.children.map(c => c.visible).join()"
            before = page.evaluate(shown)
            page.locator('#mapPictureTake').click()
            page.wait_for_function("viewer.mapPicture.state() && viewer.mapPicture.state().width !== 1600")
            taken = state(page)
            sound(taken)
            view = page.evaluate('[viewer.renderer.domElement.width, viewer.renderer.domElement.height]')
            assert [taken['width'], taken['height']] == view, (taken, view)
            assert page.evaluate(shown) == before
            page.wait_for_timeout(900)
            assert result_pixels(page)['drawn']
            out['taken'] = [taken['width'], taken['height']]
            if shots: page.screenshot(path=str(shots / 'map-picture-4-view.png'))

        # Remove picture: gone from the project at its next save
        page.locator('#mapPictureRemove').click()
        page.wait_for_selector('#mapPictureDialog', state='hidden')
        page.wait_for_function('viewer.project().dirty')
        page.keyboard.press('Control+s')
        page.wait_for_function('viewer.project().revision === 3 && !viewer.project().dirty', timeout=60000)
        doc = page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", project)
        assert 'picture' not in doc, doc.get('picture')
        open_dialog(page)
        page.wait_for_function("document.getElementById('mapPictureResultNote').textContent.length > 0")
        assert page.locator('#mapPictureRemove').is_disabled()
        assert 'own picture' not in page.locator('#mapPictureResultNote').inner_text()
        page.keyboard.press('Escape')
        page.wait_for_selector('#mapPictureDialog', state='hidden')
    out['errors'] = sorted(errors)
    assert not errors, errors
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--url', required=True, help='the test server, as http://127.0.0.1:8797')
    a.add_argument('--map', default='URB_Bar')
    a.add_argument('--shots', type=Path, help='a folder for pictures of the dialog (kept out of the repository)')
    args = a.parse_args()
    if args.shots: args.shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport=dict(width=1400, height=900))
        errors = set()
        page.on('pageerror', lambda e: errors.add(str(e)))
        page.on('console', lambda m: errors.add(m.text) if m.type == 'error' and 'favicon' not in m.text else None)
        try:
            print(json.dumps(check(page, args.url.rstrip('/'), args.map, args.shots, errors), indent=1))
        finally:
            browser.close()


if __name__ == '__main__':
    main()
