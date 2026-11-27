"""The editor's page in a headless browser (Playwright and Edge), against a test server, never the main one (8768).

  python tools/viewer/tests/browser_smoke.py --url http://127.0.0.1:<port>/?map=URB_Bar --screenshot <png>
         [--projects] [--squad] [--play [--play-project <id>]] [--only <checks>]
  python tools/viewer/tests/browser_smoke.py --all [--scratch <folder>] [--cache <scratch cache>] [--play-install <a scratch game folder>]
         [--ports a,b,c,d]
  python tools/viewer/tests/browser_smoke.py --url http://127.0.0.1:<port>/ --write-api-names

The checks are one table (CHECKS, listed by --help): each one's name, what it does, what the server must be started
with and the maps it can run on. With no --only, the whole run does the table's checks in order; --only names some
(those run only when named too) and refuses a name it doesn't know. The report (printed, and written beside the
screenshot as .json) lists what ran and what was skipped, with why (a check that skipped itself whole is listed as
skipped only), and the server's answers of status 500 and above that any check's page met, with their address (a
failure prints them too). A check --only asked for that did nothing (skipped whole, or its server or map can't have
it) fails the run; a part of a check that skipped is listed and fails nothing. What the checks save is named after
the run, so a check runs again against the same projects folder. --all runs every check on fresh test servers of its
own (ports 8795-8798, or --ports, scratch folders, a scratch cache and a scratch settings file, --dry-play), one after
another, each stopped after its run, and reports each run's lists. --write-api-names writes the test hooks' names
that the check api-names compares (api_names.py).

--all's Play run (and --play on a server of your own) installs into a scratch game folder, never a real install
(--play-install, the server's --install; without it --all makes one in its scratch folder, copying these files of the
game install the settings name when they come to less than 300 MB, else it skips Play). It holds copies of an LWR
install's files at the same places under XEW:
  XEW\\XComGame\\Config\\Default*.ini            (DefaultMaps.ini and DefaultLZMutator.ini take the play's record; the
                                              test squad reads DefaultGameCore.ini and DefaultEngine.ini)
  XEW\\XComGame\\CookedPCConsole\\XComGame.upk   (the test squad's game data)
  XEW\\XComGame\\CookedPCConsole\\<map>.upk      (the map played: URB_Bar.upk for --all)
  XEW\\XComGame\\Localization\\INT\\XCom*.int     (the test squad's words)
  XEW\\Binaries\\                               (empty: a play writes its commands file there)
No game is started.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Callable, NamedTuple
import urllib.request
from urllib.parse import quote, urlsplit, urlunsplit
from playwright.sync_api import sync_playwright

MAIN_PORT = 8768        # the user's own server: never checked against
# the camera's place and target, for settled()
CAMERA = "(() => ({c: viewer.camera.position.toArray(), t: viewer.controls.target.toArray()}))()"
# What the run left out, and why (review finding 24): skip() records each, and the report lists them.
SKIPPED = []
# What a check gives back when it skipped itself whole: the report lists it as skipped, not as ran too.
WHOLE = object()
# This run's mark, in the names of what the checks save (projects, prefabs): a check run again against the same
# projects folder saves under names of its own, not the last run's.
RUN = f'{int(time.time()) % 1_000_000:06d}'
# The server's answers of status 500 and above that any check's page met, with their address and the check (a console
# error says only "the server responded with a status of 500"): watch_answers records them, the report lists them and
# a failure prints them. CURRENT names the check running.
SERVER_ERRORS = []
CURRENT = dict(check=None)


def watch_answers(page):
    """The page, its answers of status 500 and above recorded in SERVER_ERRORS from now on."""
    page.on('response', lambda r: SERVER_ERRORS.append(dict(check=CURRENT['check'], status=r.status, method=r.request.method, url=r.url))
            if r.status >= 500 else None)
    return page


def print_server_errors():
    if SERVER_ERRORS:
        print('Answers of status 500 and above during the run:\n' + '\n'.join(
            f"  {e['status']} {e['method']} {e['url']} ({e['check'] or 'opening the map'})" for e in SERVER_ERRORS), file=sys.stderr, flush=True)


def skip(check, reason, page=None, whole=False):
    """Record that `check`, or the part of it the reason names, was left out, and why; closes the check's own page
    when given. `whole`: the check (or this part of an on_page check) did nothing else, and the skip ends it: returns
    WHOLE, for `return skip(...)` to give back to the run. Otherwise returns None, so `return skip(...)` ends a check
    as a bare return did."""
    if page is not None: page.close()
    SKIPPED.append(dict(check=check, reason=reason))
    return WHOLE if whole else None


def check_light_grid(page):
    """A Lightmass area light 120 000 units out with a 2.4 million unit radius (Deluge) opened no map: the grid
    covers only the map's pieces, with cells doubled past MAX_CELLS, and still reaches every piece."""
    assert page.evaluate("""async () => {
      const {buildLightGrid,packLightGrid,sceneLightClip,MAX_CELLS,CELL}=await import('/light_grid.js');
      const far={location:[122899,2500,28972],radius:2438430},near={location:[0,0,0],radius:300};
      const scene={objects:[{location:[0,0,0],mesh:'m',scale:[1,1,1]},
                            {location:[0,0,0],mesh:'m',scale:[1024,1024,1024],environment:true}],
                   meshes:{m:{bounds:[0,0,0,500,500,10,700]}},
                   playableBounds:{min:[-800,0,-800],max:[800,500,800]},lights:[far,near]};
      const clip=sceneLightClip(scene), grid=buildLightGrid([far,near],{clip}), packed=packLightGrid(grid);
      const free=buildLightGrid([far,near],{clip:{x0:-1e5,z0:-1e5,x1:1e5,z1:1e5}});
      const at=(g,x,z)=>g.lists[Math.floor((z-g.bounds.z0)/g.cell)*g.bounds.nx+Math.floor((x-g.bounds.x0)/g.cell)];
      return clip.x1-clip.x0 < 20000 && grid.cell===CELL && packed.deepest===2
        && at(grid,0,0).length===2 && free.cell>CELL && free.lists.length<=MAX_CELLS
        && at(free,0,0).length===2 && buildLightGrid([near],{clip:{x0:5000,z0:5000,x1:6000,z1:6000}}).bounds===null;
    }""")


def check_dense_lighting(browser, url):
    """Only light 300 emits: a rendered red pixel proves lights past 128 reach the GPU."""
    probe=browser.new_page()
    probe.route('**/app.js',lambda route:route.fulfill(status=200,content_type='text/javascript',body=''))
    probe.goto(url)
    result=probe.evaluate("""async () => {
      const T=await import('/vendor/three/three.module.js');
      const {createMapLighting,withLocalLights}=await import('/lighting.js');
      const renderer=new T.WebGLRenderer(),world=new T.Scene();
      const sun=new T.DirectionalLight(0,0),hemisphere=new T.HemisphereLight(0,0,0);
      world.add(sun,sun.target,hemisphere);
      const lights=Array.from({length:300},(_,i)=>({kind:'point',enabled:true,role:'static',
        location:[0,0,10],direction:[0,0,-1],radius:100,color:[1,0,0],brightness:i===299?1:0,falloffExponent:2}));
      const lighting=createMapLighting({world,sun,hemisphere,scene:{lights},maxTextureSize:renderer.capabilities.maxTextureSize});
      lighting.apply('map',new T.Vector3(),100);
      const geometry=new T.PlaneGeometry(10,10),material=withLocalLights(new T.MeshPhongMaterial({color:0xffffff}));
      const plane=new T.Mesh(geometry,material);plane.rotation.x=-Math.PI/2;world.add(plane);
      const camera=new T.PerspectiveCamera(45,1,0.1,100);camera.position.set(0,10,10);camera.lookAt(0,0,0);
      const target=new T.WebGLRenderTarget(32,32),pixel=new Uint8Array(4);
      renderer.setRenderTarget(target);renderer.render(world,camera);renderer.readRenderTargetPixels(target,16,16,1,1,pixel);
      target.dispose();geometry.dispose();material.dispose();renderer.dispose();renderer.forceContextLoss();
      return {pixel:[...pixel],deepest:lighting.packed.deepest};
    }""")
    probe.close()
    assert result['deepest']==300 and result['pixel'][0]>50 and max(result['pixel'][1:3])<5,result


def value(page, id):
    """The value of a select or of a row of segmented buttons."""
    return page.evaluate("id => document.getElementById(id).value", id)


def open_view_options(page):
    if page.locator('#viewOptions').is_hidden(): page.locator('#viewButton').click()


def choose(page, id, option):
    """Click one of a segmented control's buttons: scene and floors in the dock, lighting in the view options."""
    if id == 'lighting': open_view_options(page)
    page.locator(f'#{id} button[data-value="{option}"]').click()
    assert value(page, id) == option, (id, option)


def check_option(page, id, on):
    open_view_options(page)
    page.locator('#'+id).set_checked(on)


def camera_delta(before, after):
    return max(abs(a - b) for key in ('c', 't') for a, b in zip(before[key], after[key]))


def check_arrow_pan(page):
    """The arrow keys and WASD move the camera: target and camera together. By default they pan across the map at a
    constant height; with View options' Keys move along the view, forward and back follow the camera's facing."""
    page.evaluate('document.activeElement && document.activeElement.blur()')
    state = CAMERA

    def held(key):
        before = page.evaluate(state)
        page.keyboard.down(key); page.wait_for_timeout(300); page.keyboard.up(key); page.wait_for_timeout(100)
        after = page.evaluate(state)
        dc = [a - b for a, b in zip(after['c'], before['c'])]
        dt = [a - b for a, b in zip(after['t'], before['t'])]
        assert all(abs(a - b) < 1e-3 for a, b in zip(dc, dt)), (key, dc, dt)
        return before, dc

    keys = (('ArrowUp', 'w', 1), ('ArrowDown', 's', -1), ('ArrowRight', 'd', 1), ('ArrowLeft', 'a', -1))
    for arrow, letter, sign in keys:
        for key in (arrow, letter):
            before, dc = held(key)
            assert abs(dc[1]) < 1e-3 and (dc[0] ** 2 + dc[2] ** 2) ** 0.5 > 10, (key, dc)
            # Forward is the view's direction laid flat; right is across it.
            f = [before['t'][0] - before['c'][0], before['t'][2] - before['c'][2]]
            along = (dc[0] * f[0] + dc[2] * f[1]) / ((f[0] ** 2 + f[1] ** 2) ** 0.5)
            across = (dc[0] * -f[1] + dc[2] * f[0]) / ((f[0] ** 2 + f[1] ** 2) ** 0.5)
            if arrow in ('ArrowUp', 'ArrowDown'):
                assert along * sign > 10 and abs(across) < 1, (key, along, across)
            else:
                # Right of the view: forward x up, (-f.z, f.x) on the ground, as for a camera looking down -z.
                assert across * sign > 10 and abs(along) < 1, (key, along, across)
    # The same speed close in as far out (it once followed the distance to the point looked at).
    far = page.evaluate("viewer.camera.position.distanceTo(viewer.controls.target)")
    moves = []
    for scale in (1, 1 / 8):
        page.evaluate('''s => { const c = viewer.camera, t = viewer.controls.target;
          c.position.sub(t).multiplyScalar(s).add(t); viewer.controls.update(); }''', scale)
        moves.append(sum(x * x for x in held('ArrowUp')[1]) ** 0.5)
        page.evaluate('''s => { const c = viewer.camera, t = viewer.controls.target;
          c.position.sub(t).multiplyScalar(1 / s).add(t); viewer.controls.update(); }''', scale)
    assert 0.5 < moves[1] / moves[0] < 2, (far, moves)
    # Along the view: forward and back follow the camera's facing, tilt and all; sideways stays level.
    check_option(page, 'flyKeys', True)
    page.keyboard.press('Escape')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    assert page.evaluate("localStorage.getItem('workshop.flyKeys')") == '1'
    try:
        for arrow, letter, sign in keys:
            for key in (arrow, letter):
                before, dc = held(key)
                f = [t - c for t, c in zip(before['t'], before['c'])]
                fn = sum(x * x for x in f) ** 0.5
                f = [x / fn for x in f]
                dn = sum(x * x for x in dc) ** 0.5
                assert dn > 10, (key, dc)
                along = sum(a * b for a, b in zip(dc, f))
                if arrow in ('ArrowUp', 'ArrowDown'):
                    # the whole move is along the facing, which tilts down: forward descends
                    assert along * sign > 0 and abs(abs(along) - dn) < 1e-3 * dn, (key, dc, f)
                    assert abs(f[1]) < 0.05 or dc[1] * f[1] * sign > 0, (key, dc, f)
                else:
                    assert abs(dc[1]) < 1e-3 and abs(along) < 1e-3 * dn, (key, dc, f)
                    across = (dc[0] * -f[2] + dc[2] * f[0]) / ((f[0] ** 2 + f[2] ** 2) ** 0.5)
                    assert across * sign > 10, (key, across)
        check_turn(page, fly=True)
        check_drag_look(page, fly=True)
    finally:
        check_option(page, 'flyKeys', False)
        page.keyboard.press('Escape')
    check_turn(page, fly=False)
    check_drag_look(page, fly=False)
    check_tool_keys(page)
    check_camera_speeds(page)
    # Typing in a field keeps the keys. (The Add panel's filter: the panel opened first, as a hidden field takes no
    # focus, and the keys then went to the camera: why the full run failed here since the camera checks moved on.)
    page.keyboard.press('p')
    page.locator('#libFilter').wait_for(state='visible')
    page.locator('#libFilter').focus()
    assert page.evaluate("document.activeElement?.id") == 'libFilter'
    before = settled(page, state)
    for key in ('ArrowUp', 'w', 'q', 'e'):
        page.keyboard.down(key); page.wait_for_timeout(200); page.keyboard.up(key)
    after = page.evaluate(state)
    assert camera_delta(before, after) < 1e-3, (before, after)
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('p')
    page.locator('#libFilter').wait_for(state='hidden')


def check_camera_speeds(page):
    """View options' camera speeds (Discord feedback S2, S3) scale the keys' move and turn and the drag's orbit,
    remembered, a double-click putting a slider back to 1; and Shift pressed while a move key is already held speeds it
    up at once (Discord feedback B1)."""
    page.evaluate('document.activeElement && document.activeElement.blur()')
    measure = """async ([key, shiftAfter]) => {
      const wait = ms => new Promise(r => setTimeout(r, ms)), cam = viewer.camera, t = viewer.controls.target;
      const send = (type, k, shift) => document.dispatchEvent(new KeyboardEvent(type, {key: k, shiftKey: shift, bubbles: true}));
      const angle = () => Math.atan2(cam.position.x - t.x, cam.position.z - t.z);
      const sample = async () => {
        const p = cam.position.clone(), a = angle(), t0 = performance.now();
        await wait(400);
        const s = (performance.now() - t0) / 1000, d = angle() - a;
        return {move: cam.position.distanceTo(p) / s, turn: Math.abs(Math.atan2(Math.sin(d), Math.cos(d))) / s};
      };
      send('keydown', key, false); await wait(120);
      const plain = await sample();
      let fast = null;
      if (shiftAfter) { send('keydown', 'Shift', true); await wait(80); fast = await sample(); send('keyup', 'Shift', false); }
      send('keyup', key, false); await wait(80);
      return {plain, fast};
    }"""
    def slide(id, v):
        page.evaluate("([id, v]) => { const e = document.getElementById(id); e.value = String(v); e.dispatchEvent(new Event('input')); }", [id, v])
    base = page.evaluate(measure, ['w', True])
    assert base['plain']['move'] > 100, base
    assert 2.6 < base['fast']['move'] / base['plain']['move'] < 3.4, base       # Shift during the hold: three times
    slide('moveSpeed', 0.5)
    half = page.evaluate(measure, ['w', False])
    assert 0.4 < half['plain']['move'] / base['plain']['move'] < 0.6, (base, half)
    assert page.evaluate("localStorage.getItem('workshop.moveSpeed')") == '0.5'
    assert page.locator('#moveSpeedValue').text_content() == '×0.50'
    page.locator('#moveSpeed').dispatch_event('dblclick')
    assert page.evaluate("document.getElementById('moveSpeed').value") == '1'
    assert page.evaluate("localStorage.getItem('workshop.moveSpeed')") == '1'
    turn = page.evaluate(measure, ['q', False])
    slide('turnSpeed', 2)
    turned = page.evaluate(measure, ['q', False])
    assert 1.6 < turned['plain']['turn'] / turn['plain']['turn'] < 2.4, (turn, turned)
    slide('turnSpeed', 1)
    slide('dragSpeed', 2)
    assert page.evaluate('viewer.controls.rotateSpeed') == 2
    slide('dragSpeed', 1)
    assert page.evaluate('viewer.controls.rotateSpeed') == 1


def check_pivot(page):
    """C, or the rail's pivot button, puts the gizmo on the selection's centre (Discord feedback S4): a typed turn then
    turns about the middle, so the piece's box stays where it was; with tile snap the pivot keeps to a tile's centre or
    corner. Back to the origin, the gizmo sits on the piece's own pivot again. The selection it found is put back:
    the checks after it go on with the piece selected before it."""
    page.evaluate('document.activeElement && document.activeElement.blur()')
    before = page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    picked = page.evaluate("""async () => {
      const T = await import('/vendor/three/three.module.js');
      // a visible piece whose own pivot stands well off its middle across (game x, y are the viewer's x, z)
      const root = [...viewer.roots.values()].find(r => {
        const o = r.userData.source;
        if (!r.visible || r.userData.deleted || o.light || !o.location) return false;
        const box = new T.Box3().setFromObject(r), s = box.getSize(new T.Vector3()), c = box.getCenter(new T.Vector3());
        return s.x > 60 && s.z > 60 && s.x < 2000 && s.z < 2000 && Math.hypot(c.x - o.location[0], c.z - o.location[1]) > 40;
      });
      return root ? root.userData.source.id : null;
    }""")
    assert picked, 'no piece to turn'
    page.evaluate('id => viewer.select(id)', picked)
    middle = """async () => {
      const T = await import('/vendor/three/three.module.js');
      const box = new T.Box3();
      for (const r of viewer.gizmo.selection()) box.expandByObject(r);
      return {box: box.getCenter(new T.Vector3()).toArray(), proxy: viewer.gizmo.controls.object.position.toArray()};
    }"""
    assert page.evaluate('viewer.gizmo.pivot') == 'origin'
    at_origin = page.evaluate(middle)
    page.keyboard.press('c')
    assert page.evaluate('viewer.gizmo.pivot') == 'centre'
    assert page.evaluate("localStorage.getItem('workshop.pivot')") == 'centre'
    assert page.locator('#editPivot').get_attribute('aria-pressed') == 'true'
    at_centre = page.evaluate(middle)
    assert max(abs(a - b) for a, b in zip(at_centre['proxy'], at_centre['box'])) < 0.01, at_centre
    assert max(abs(a - b) for a, b in zip(at_origin['proxy'], at_origin['box'])) > 1, at_origin
    # the pose fields still show the piece's own pivot
    start = page.evaluate('viewer.gizmo.pose()')
    assert max(abs(a - b) for a, b in zip(start['location'], [at_origin['proxy'][0], at_origin['proxy'][2], at_origin['proxy'][1]])) < 0.01
    # a typed half turn about the middle: the box's middle stays, the piece's pivot moves
    page.locator('#rotY').fill(f"{start['rotation'][1] + 180:.2f}"); page.locator('#rotY').press('Enter')
    turned, after = page.evaluate('viewer.gizmo.pose()'), page.evaluate(middle)
    assert max(abs(a - b) for a, b in zip(after['box'], at_centre['box'])) < 0.5, (at_centre, after)
    assert max(abs(a - b) for a, b in zip(turned['location'], start['location'])) > 1, (start, turned)
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.gizmo.edited().length') == 0
    # a half turn on the ring, as TransformControls makes one: the handle turned in place between its mouseDown and
    # mouseUp; the same holds
    page.evaluate("""async () => {
      const T = await import('/vendor/three/three.module.js');
      const c = viewer.gizmo.controls, p = c.object;
      viewer.gizmo.setMode('rotate');
      c.dispatchEvent({type: 'mouseDown'});
      p.quaternion.premultiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), Math.PI)); p.updateMatrixWorld(true);
      c.dispatchEvent({type: 'objectChange'}); c.dispatchEvent({type: 'mouseUp'});
      viewer.gizmo.setMode('translate');
    }""")
    dragged, after = page.evaluate('viewer.gizmo.pose()'), page.evaluate(middle)
    assert max(abs(a - b) for a, b in zip(after['box'], at_centre['box'])) < 0.5, (at_centre, after)
    assert max(abs(a - b) for a, b in zip(dragged['location'], turned['location'])) < 0.5, (turned, dragged)
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.gizmo.edited().length') == 0
    # tile snap: the pivot on a tile corner or centre across
    if page.evaluate('Boolean(viewer.data.tileGrid?.origin)'):
        was = page.evaluate('viewer.gizmo.snap')
        page.evaluate("viewer.gizmo.setSnap('tile')")
        p = page.evaluate('viewer.gizmo.controls.object.position.toArray()')
        o = page.evaluate('viewer.data.tileGrid.origin')
        steps = [(p[0] - o[0]) / 48, (p[2] - o[1]) / 48]
        assert all(abs(s - round(s)) < 1e-3 for s in steps) and round(steps[0]) % 2 == round(steps[1]) % 2, (p, o)
        page.evaluate('s => viewer.gizmo.setSnap(s)', was)
    page.locator('#editPivot').click()
    assert page.evaluate('viewer.gizmo.pivot') == 'origin' and page.evaluate("localStorage.getItem('workshop.pivot')") == 'origin'
    back = page.evaluate(middle)
    assert max(abs(a - b) for a, b in zip(back['proxy'], at_origin['proxy'])) < 0.01, (at_origin, back)
    page.evaluate('id => viewer.select(id)', before)


def check_text_select(page):
    """The page's text doesn't select (Discord feedback S7); a piece's details and the build log do."""
    styles = page.evaluate("""() => Object.fromEntries(['body', '#details', '#buildLog', '#dragHint', '#help']
      .map(s => [s, getComputedStyle(document.querySelector(s)).userSelect]))""")
    assert styles['body'] == 'none' and styles['#dragHint'] == 'none' and styles['#help'] == 'none', styles
    assert styles['#details'] == 'text' and styles['#buildLog'] == 'text', styles


def check_turn(page, fly):
    """Q and E turn the view left and right about the vertical, keeping the tilt: round the point it looks at, or with
    Keys move along the view, where the camera stands."""
    page.evaluate('document.activeElement && document.activeElement.blur()')
    state = CAMERA
    for key, sign in (('q', 1), ('e', -1)):
        before = page.evaluate(state)
        page.keyboard.down(key); page.wait_for_timeout(300); page.keyboard.up(key); page.wait_for_timeout(100)
        after = page.evaluate(state)
        fixed, swung = ('c', 't') if fly else ('t', 'c')
        assert all(abs(a - b) < 1e-3 for a, b in zip(after[fixed], before[fixed])), (key, fly, before, after)
        f0 = [t - c for t, c in zip(before['t'], before['c'])]
        f1 = [t - c for t, c in zip(after['t'], after['c'])]
        # the same distance and tilt, the flat direction turned
        assert abs(f1[1] - f0[1]) < 1e-3 * abs(f0[1]) + 1e-3, (key, f0, f1)
        assert abs(sum(x * x for x in f1) - sum(x * x for x in f0)) < 1e-4 * sum(x * x for x in f0), (key, f0, f1)
        # turning left swings forward towards the screen's left: (f0.z, -f0.x) on the ground, as for a camera looking down -z
        left = f1[0] * f0[2] - f1[2] * f0[0]
        assert left * sign > 0 and abs(left) > 1e-3 * (f0[0] ** 2 + f0[2] ** 2), (key, fly, f0, f1)


def settled(page, state, timeout=10000):
    """The camera's state once it has stopped moving (OrbitControls' damping eases a drag out over a second or more)."""
    last = page.evaluate(state)
    for _ in range(timeout // 250):
        page.wait_for_timeout(250)
        now = page.evaluate(state)
        if camera_delta(last, now) < 1e-4:
            return now
        last = now
    raise AssertionError(f'the camera kept moving: {last}')


def check_drag_look(page, fly):
    """A left-drag along the view looks round from where the camera stands: the camera keeps its place, the point it
    looks at swings round it at the same distance (right looks right, up looks up). Otherwise the drag orbits: the
    point stays and the camera moves."""
    page.evaluate('viewer.select(null)')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    state = CAMERA
    box = page.locator('#viewport').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    for dx, dy in ((120, 0), (0, -80)):
        before = page.evaluate(state)
        page.mouse.move(cx, cy); page.mouse.down(); page.mouse.move(cx + dx, cy + dy, steps=6); page.mouse.up()
        after = settled(page, state)    # the orbit's damping eases out
        moved = lambda key: max(abs(a - b) for a, b in zip(after[key], before[key]))
        f0 = [t - c for t, c in zip(before['t'], before['c'])]
        f1 = [t - c for t, c in zip(after['t'], after['c'])]
        if not fly:
            assert moved('t') < 1e-3 and moved('c') > 1, (dx, dy, before, after)
            continue
        assert moved('c') < 1e-3 and moved('t') > 1, (dx, dy, before, after)
        n0, n1 = (sum(x * x for x in f) ** 0.5 for f in (f0, f1))
        assert abs(n1 - n0) < 1e-3 * n0, (n0, n1)
        if dx:
            # right of the old flat forward: (-f0.z, f0.x)
            right = f1[2] * f0[0] - f1[0] * f0[2]
            assert right > 0 and abs(f1[1] - f0[1]) < 1e-3 * n0, (f0, f1)
        else:
            assert f1[1] / n1 > f0[1] / n0 + 0.05, (f0, f1)
    assert page.evaluate('viewer.gizmo.active') is None    # a drag is no click


def check_tool_keys(page):
    """G, R and X are Move, Rotate and the axes (WASD, Q and E move and turn the camera)."""
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.evaluate("viewer.select([...viewer.roots.keys()][0])")
    page.keyboard.press('r'); assert page.evaluate('viewer.gizmo.mode') == 'rotate'
    page.keyboard.press('g'); assert page.evaluate('viewer.gizmo.mode') == 'translate'
    space = page.evaluate('viewer.gizmo.space')
    page.keyboard.press('x'); assert page.evaluate('viewer.gizmo.space') != space
    page.keyboard.press('x'); assert page.evaluate('viewer.gizmo.space') == space
    for key in ('q', 'e', 'w', 'a', 's', 'd'):
        page.keyboard.press(key)
    assert page.evaluate('viewer.gizmo.mode') == 'translate' and page.evaluate('viewer.gizmo.space') == space
    assert page.locator('#library').is_hidden()
    # While placing, R turns the piece and leaves the tool alone.
    page.keyboard.press('Control+c')
    box = page.locator('#viewport').bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.keyboard.press('Control+v')
    page.wait_for_function('Boolean(viewer.placing())')
    page.keyboard.press('r')
    assert page.evaluate('viewer.placing().turns') == 1 and page.evaluate('viewer.gizmo.mode') == 'translate'
    page.keyboard.press('Escape')
    assert not page.evaluate('viewer.placing()')
    page.keyboard.press('v')
    page.keyboard.press('Escape')


def check_play_area(page):
    """The play area (the level volume) is drawn as amber walls and edges on its bounds; B and View options' Play area
    show and hide it, remembered."""
    if not page.evaluate("viewer.data.scope === 'map' && Boolean(viewer.data.playableBounds)"):
        assert page.evaluate('viewer.playArea.children.length') == 0 and page.locator('#playAreaRow').is_hidden()
        return skip('play-area', 'the map has no play area (none drawn and its row hidden: checked)')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    drawn = page.evaluate("""async () => {
      const T = await import('/vendor/three/three.module.js');
      const box = new T.Box3().setFromObject(viewer.playArea), b = viewer.data.playableBounds;
      return {visible: viewer.playArea.visible, parts: viewer.playArea.children.length,
              off: Math.max(...[0, 1, 2].flatMap(k => [Math.abs(box.min.getComponent(k) - b.min[k]), Math.abs(box.max.getComponent(k) - b.max[k])]))};
    }""")
    assert drawn['visible'] and drawn['parts'] == 3 and drawn['off'] < 1, drawn
    page.keyboard.press('b')
    assert not page.evaluate('viewer.playArea.visible') and not page.locator('#playAreaToggle').is_checked()
    assert page.evaluate("localStorage.getItem('workshop.playArea')") == '0'
    page.keyboard.press('b')
    assert page.evaluate('viewer.playArea.visible') and page.evaluate("localStorage.getItem('workshop.playArea')") == '1'
    check_option(page, 'playAreaToggle', False)
    assert not page.evaluate('viewer.playArea.visible')
    check_option(page, 'playAreaToggle', True)
    assert page.evaluate('viewer.playArea.visible')
    page.keyboard.press('Escape')


def check_interior_whole(page):
    """Interior draws a piece that reaches into its area whole across the map (cut by height only), unless it reaches
    more than four tiles past the area's sides; such pieces, and the ones outside, stay cut at the sides."""
    if not page.locator('#scenery').is_visible(): return skip('play-area', 'Interior whole: the map has no Full and Interior choice', whole=True)
    was = value(page, 'scenery')
    choose(page, 'scenery', 'interior')
    found = page.evaluate("""async () => {
      const T = await import('/vendor/three/three.module.js');
      const f = viewer.data.tactical?.focusBounds || viewer.data.playableBounds;
      const focus = new T.Box3(new T.Vector3(...f.min), new T.Vector3(...f.max));
      const sides = planes => planes.filter(p => Math.abs(p.normal.y) < 0.5).length;
      let whole = 0, sticking = 0, cut = 0, wrong = [];
      for (const r of viewer.roots.values()) {
        if (!r.visible) continue;
        const box = new T.Box3().setFromObject(r);
        const over = Math.max(focus.min.x - box.min.x, box.max.x - focus.max.x, focus.min.z - box.min.z, box.max.z - focus.max.z);
        const planes = r.userData.clippingPlanes || [];
        const meant = !box.isEmpty() && box.intersectsBox(focus) && over <= 384;
        if (meant !== Boolean(r.userData.interiorWhole) || sides(planes) !== (meant ? 0 : 4)) wrong.push(r.userData.source.id);
        if (meant) { whole++; if (over > 1) sticking++; } else cut++;
      }
      return {whole, sticking, cut, wrong: wrong.slice(0, 5)};
    }""")
    assert not found['wrong'] and found['whole'] and found['sticking'], found
    choose(page, 'scenery', was)
    assert page.evaluate('[...viewer.roots.values()].every(r => !r.userData.interiorWhole)') or was == 'interior'


def check_tile_grid(page):
    """The tile grid shows only around the selection or the piece being placed, with its tiles filled."""
    # Escape clears the selection, with the inspector and the grid (the pointer on the view, not in a field).
    page.evaluate('document.activeElement && document.activeElement.blur()')
    if not page.evaluate('viewer.gizmo.active'):
        page.evaluate("""viewer.select([...viewer.roots.keys()][0])""")
    assert page.evaluate('viewer.gizmo.active')
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.gizmo.active') is None and page.locator('#inspector').is_hidden()
    assert page.evaluate('viewer.tileGrid()') is None and page.locator('#tileNote').is_hidden()
    # A visible piece of the play area, inside the map's tile grid.
    piece = page.evaluate("""() => {
      const g=viewer.data.tileGrid;
      const found=[...viewer.roots.entries()].find(([,r])=>r.visible && ['XComLevelActor','StaticMeshActor'].includes(r.userData.source.actorClass)
        && r.userData.source.sceneryRole==='interior' && r.userData.source.location.every((v,k)=>k>1 || (v>g.origin[k]+200 && v<g.origin[k]+g.dimensions[k]*g.size[k]-200)));
      return found && found[0];
    }""")
    assert piece
    page.evaluate(f'viewer.select({piece!r})')
    info = page.evaluate('viewer.tileGrid()')
    assert info and len(info['tiles']) > 0 and info['level'] >= 0, info
    assert page.locator('#tileNote').is_visible() and 'level' in page.locator('#tileNote').inner_text()
    # It follows the selection (with its linked pieces): moved a tile along x, its tiles move with it.
    before = sorted(tuple(map(int, t.split(','))) for t in info['tiles'])
    shift = "dx => viewer.gizmo.selection().forEach(r => { r.matrix.elements[12] += dx; r.matrixWorldNeedsUpdate = true; })"
    page.evaluate(f'({shift})(96)')
    after = sorted(tuple(map(int, t.split(','))) for t in page.evaluate('viewer.tileGrid()')['tiles'])
    page.evaluate(f'({shift})(-96)')
    assert after == sorted((x + 1, y) for x, y in before), (before, after)
    # Off, there is none.
    check_option(page, 'grid', False)
    assert page.evaluate('viewer.tileGrid()') is None and page.locator('#tileNote').is_hidden()
    check_option(page, 'grid', True)
    assert page.evaluate('viewer.tileGrid()')
    page.evaluate('viewer.select(null)')


def check_tile_footprints(page):
    """Which tiles a turned box covers, and floating above a saved floor."""
    assert page.evaluate("""async () => {
      const T=await import('/vendor/three/three.module.js');
      const {footprintOf,tileGridAround}=await import('/view_layout.js');
      const scene={tileGrid:{origin:[0,0,0],dimensions:[10,10,3],size:[96,96,64]},tactical:{floorTiles:[]}};
      for(let x=0;x<10;x++)for(let y=0;y<10;y++)scene.tactical.floorTiles.push({tile:[x,y,0],location:[x*96+48,y*96+48,0],normal:[0,0,1],actor:'ground'});
      const box=(w,d,h,x,y,z,yaw=0)=>{const m=new T.Mesh(new T.BoxGeometry(w,h,d).translate(0,h/2,0));
        m.position.set(x,z,y);m.rotation.y=yaw;m.updateMatrixWorld(true);return m;};
      const keys=(f,k='tiles')=>[...f[k]].sort().join(' ');
      // 90 x 90 on a tile centre: one tile; on a tile corner: four. Reaching 1 unit over an edge doesn't count, 5 units
      // is at the edge, and 30 (more than a quarter tile) covers the tile.
      let ok=keys(footprintOf([box(90,90,50,240,240,0)],scene))==='2,2';
      ok &&= footprintOf([box(90,90,50,192,192,0)],scene).tiles.size===4;
      let f=footprintOf([box(96,96,50,241,240,0)],scene);ok &&= keys(f)==='2,2' && f.edges.size===0;
      f=footprintOf([box(96,96,50,245,240,0)],scene);ok &&= keys(f)==='2,2' && keys(f,'edges')==='3,2';
      f=footprintOf([box(96,96,50,270,240,0)],scene);ok &&= keys(f)==='2,2 3,2' && f.edges.size===0;
      // Turned 45 degrees, a 90-unit box on a tile centre reaches 15.6 units into its four edge neighbours.
      f=footprintOf([box(90,90,50,240,240,0,Math.PI/4)],scene);ok &&= f.tiles.size===1 && f.edges.size===4;
      // A round piece (a cylinder of radius 58) on a tile centre reaches 10 units into the four edge neighbours, not
      // the corner ones: its bounding box would have reached all eight.
      const round=new T.Mesh(new T.CylinderGeometry(58,58,50,48).translate(0,25,0));round.position.set(240,0,240);round.updateMatrixWorld(true);
      f=footprintOf([round],scene);ok &&= keys(f)==='2,2' && keys(f,'edges')==='1,2 2,1 2,3 3,2';
      // On the floor it is amber; lifted 64 units it floats.
      const ground=tileGridAround(footprintOf([box(90,90,50,240,240,0)],scene),scene);
      const lifted=tileGridAround(footprintOf([box(90,90,50,240,240,64)],scene),scene);
      ok &&= !ground.userData.floating && ground.userData.gap===0 && lifted.userData.floating && lifted.userData.gap===64;
      // Off the map's grid there is no footprint.
      ok &&= footprintOf([box(90,90,50,-500,-500,0)],scene)===null;
      return ok;
    }""")


def check_light_bar(page):
    """Police Station (export 16): a sedan's standalone police light bar, which no prefab places with it, is in its
    car's assembly (compiler.assemblies, from the glass's `breaks`): it selects with the sedan, and a pasted copy's
    light bar shares the copied sedan's link tag, so it moves with the copy and not with the original."""
    pl = 'TheWorld.PersistentLevel.'
    find = """name => [...viewer.roots.values()].find(r => r.userData.source.actor === name && r.userData.source.layer === 'base')
                ?.userData.source.id"""
    body, bar = (page.evaluate(find, pl + n) for n in ('XComDestructibleActor_1056', 'XComDestructibleActor_468'))
    assert body and bar, (body, bar)
    before = page.evaluate('viewer.gizmo.active')
    page.evaluate('id => viewer.select(id)', bar)
    chosen = page.evaluate('viewer.gizmo.selection().map(r => r.userData.source.actor)')
    assert pl + 'XComDestructibleActor_1056' in chosen and pl + 'XComFracLevelActor_192' in chosen, chosen
    count, parts = page.evaluate('viewer.roots.size'), len(chosen)
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.keyboard.press('Control+c'); page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + parts)
    tags = page.evaluate("""() => [...new Set([...viewer.roots.values()].filter(r => r.userData.source.added)
                                     .map(r => r.userData.source.prefab))]""")
    assert len(tags) == 1 and tags[0], tags
    copied_bar = page.evaluate("""() => [...viewer.roots.values()].find(r => r.userData.source.added
                                     && r.userData.source.added.from.actor.endsWith('XComDestructibleActor_468')).userData.source.id""")
    page.evaluate('id => viewer.select(id)', copied_bar)
    assert page.evaluate('viewer.gizmo.selection().length') == parts
    assert page.evaluate('viewer.gizmo.selection().every(r => r.userData.source.added)')
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count
    page.evaluate('id => viewer.select(id)', before)


def check_destruction(page, is_bar):
    """Export 17: every piece says what the game's damage does to it (`destruction`), and the panel's source details
    show it as Destructible and Health lines. On the Bar: a car (500, Toughness_SMALLCAR), its glass (a fracturing
    piece, 10, fragile) and a ground plane (no health)."""
    assert page.evaluate("viewer.data.objects.every(o => 'destruction' in o)")
    fields = """id => { viewer.select(id); const out = {};
                  for (const dt of document.querySelectorAll('#sourceFields dt')) out[dt.textContent] = dt.nextElementSibling.textContent;
                  return out; }"""
    find = """name => [...viewer.roots.values()].find(r => r.userData.source.actor === name && r.userData.source.layer === 'base')
                ?.userData.source.id"""
    before = page.evaluate('viewer.gizmo.active')
    shown = page.evaluate(fields, before)
    assert shown.get('Destructible'), shown
    if is_bar:
        pl = 'TheWorld.PersistentLevel.'
        glass = page.evaluate(f"viewer.data.objects.find(o => o.actor === '{pl}XComDestructibleActor_20').partner")
        car, pane, ground = (page.evaluate(fields, page.evaluate(find, name))
                             for name in (pl + 'XComDestructibleActor_20', glass, pl + 'XComLevelActor_242'))
        assert car['Destructible'] == 'Yes, not by bullets' and car['Health'] == '500 (Toughness_SMALLCAR)', car
        assert pane['Destructible'] == 'Yes, a part at a time' and pane['Health'] == '10 (Toughness_GLASS, fragile)', pane
        assert ground['Destructible'] == 'No' and 'Health' not in ground, ground
    page.evaluate('id => viewer.select(id)', before)


def check_adding(page, is_bar):
    """Trial copies and deletions on a piece it picks (typed-pose's): copy, paste through the placing preview,
    undo/redo, delete and Reset all."""
    page.evaluate('id => viewer.select(id)', own_piece(page, is_bar))
    count = page.evaluate('viewer.roots.size')
    group = page.evaluate('viewer.gizmo.selection().length')
    original = page.evaluate('viewer.gizmo.active')
    start = page.evaluate('viewer.gizmo.pose()')
    near = lambda a, b, tolerance=0.01: all(abs(x - y) < tolerance for x, y in zip(a, b))
    # Copy, then paste: the copy follows the cursor as a preview, with the gizmo held, and nothing is added until a
    # click; Escape drops it. A click puts the pivot on the point under the cursor, turned as its source, and the
    # copies become the selection.
    page.locator('#editCopy').click()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(cx, cy)
    hit = page.evaluate('([x, y]) => { const h = viewer.pick(x, y); return h && [h.point.x, h.point.z, h.point.y]; }', [cx, cy])
    page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    assert page.evaluate('viewer.roots.size') == count and not page.evaluate('viewer.gizmo.controls.enabled')
    assert 'Placing' in page.locator('#dragHint').inner_text()
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.placing()') is None and page.evaluate('viewer.roots.size') == count
    assert page.evaluate('viewer.gizmo.active') == original and page.evaluate('viewer.changes().total') == 0
    page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + group)
    assert page.evaluate('viewer.placing()') is None
    assert page.evaluate("viewer.gizmo.controls.enabled === (viewer.gizmo.mode !== 'off')")
    pasted = page.evaluate('viewer.gizmo.pose()')
    assert page.evaluate('viewer.gizmo.selection().every(r => r.userData.source.added)')
    assert page.evaluate('viewer.gizmo.selection().length') == group
    if hit: assert near(pasted['location'], hit), (hit, pasted)
    else: assert abs(pasted['location'][2] - start['location'][2]) < 0.01, (start, pasted)
    assert near(pasted['rotation'], start['rotation']), (start, pasted)
    assert 'added' in page.locator('#editCount').inner_text()
    # Undo takes the paste away and gives the selection back; redo pastes the same pieces again.
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    assert page.evaluate('viewer.gizmo.active') == original
    page.keyboard.press('Control+y')
    assert page.evaluate('viewer.roots.size') == count + group
    page.keyboard.press('Control+z')
    # Whole-tile snap and a quarter turn: the copy lands whole tiles from its source, turned 90 degrees (R).
    page.locator('#editSnap').click(); page.locator('#editSnap').click()
    assert page.locator('#snapBadge').inner_text() == '96'
    page.mouse.move(cx, cy)
    page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.keyboard.press('r')
    assert page.evaluate('viewer.placing().turns') == 1 and '90' in page.locator('#dragHint').inner_text()
    page.mouse.click(cx + 40, cy + 30)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + group)
    turned = page.evaluate('viewer.gizmo.pose()')
    for axis in (0, 1):
        steps = (turned['location'][axis] - start['location'][axis]) / 96
        assert abs(steps - round(steps)) < 1e-3, (start, turned)
    assert abs((turned['rotation'][1] - start['rotation'][1] - 90 + 180) % 360 - 180) < 0.01, (start, turned)
    page.locator('#editSnap').click()
    assert page.evaluate('viewer.gizmo.snap') == 'off' and page.locator('#snapBadge').inner_text() == ''
    page.keyboard.press('Control+z'); page.keyboard.press('Control+y')
    # Delete removes the pasted copy; deleting an original hides it until Reset all (or undo).
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.roots.size') == count and page.locator('#inspector').is_hidden()
    page.evaluate('id => viewer.select(id)', original)
    page.keyboard.press('Delete')
    assert page.evaluate('id => viewer.roots.get(id).userData.deleted && !viewer.roots.get(id).visible', original)
    assert 'deleted' in page.locator('#editCount').inner_text()
    page.locator('#editResetAll').click()
    assert page.evaluate('id => !viewer.roots.get(id).userData.deleted && viewer.roots.get(id).visible', original)
    assert page.evaluate('viewer.changes().total') == 0 and page.locator('#editCount').is_hidden()
    page.keyboard.press('Control+z')
    assert page.evaluate('id => viewer.roots.get(id).userData.deleted', original)
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.roots.size') == count
    if is_bar and page.evaluate('viewer.data.exporterVersion >= 12'):
        # A copied car keeps its parts together, linked to each other and not to the original car.
        car = page.evaluate("[...viewer.roots.keys()].find(id => !viewer.roots.get(id).userData.source.hidden && viewer.gizmo.linkedCount(id) >= 2)")
        parts = page.evaluate('id => viewer.gizmo.linkedCount(id) + 1', car)
        page.evaluate('id => viewer.select(id)', car)
        page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
        page.mouse.click(cx, cy)
        page.wait_for_function('n => viewer.roots.size === n', arg=count + parts)
        assert page.evaluate('viewer.gizmo.selection().length') == parts
        assert page.evaluate("""() => {
          const copies = [...viewer.roots.values()].filter(r => r.userData.source.added);
          viewer.select(copies.at(-1).userData.source.id);
          return viewer.gizmo.selection().length === copies.length && viewer.gizmo.selection().every(r => r.userData.source.added);
        }""")
        page.evaluate('id => viewer.select(id)', car)
        assert page.evaluate('viewer.gizmo.selection().every(r => !r.userData.source.added)')
        page.keyboard.press('Control+z')
        assert page.evaluate('viewer.roots.size') == count
    # Two copies of one original, pasted together, stay two actors with names of their own: a project keeps an actor's
    # pieces together by name (EXP-14 run 8: two stacked consoles pasted as a group were saved as one).
    page.evaluate('id => viewer.select(id)', original)
    page.keyboard.press('Control+c')
    for k, dx in enumerate((0, 80)):
        page.mouse.move(cx + dx, cy); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(cx + dx, cy)
        page.wait_for_function('n => viewer.roots.size === n', arg=count + group * (k + 1))
        if k == 0: per_paste = len(page.evaluate('viewer.editState().added'))
    page.evaluate("() => { const ids = [...viewer.roots.values()].filter(r => r.userData.source.added).map(r => r.userData.source.id);"
                  " viewer.gizmo.setSelection(ids, ids[0]); }")
    page.keyboard.press('Control+c'); page.mouse.move(cx - 80, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(cx - 80, cy)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + group * 4)
    added = page.evaluate('viewer.editState().added')
    names = [a['actor'] for a in added]
    assert len(added) == 4 * per_paste and len(set(names)) == len(names), names
    assert all(len(a['components']) == len(set(a['components'])) for a in added), added
    for _ in range(3): page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    # Destructible props build in M1 (EXP-13); a car's body, which names its glass as partner, and a van's since EXP-24;
    # The scout's frameless door also builds with the native door recipe.
    prop = page.evaluate("() => [...viewer.roots.keys()].find(id => { const r = viewer.roots.get(id), o = r.userData.source;"
                         " return r.visible && !o.added && o.actorClass === 'XComDestructibleActor' && !o.partner; })")
    body = ("family => { const a = (viewer.families()?.assemblies ?? []).find(a => a.family === family);"
            " return a && [...viewer.roots.keys()].find(id => { const o = viewer.roots.get(id).userData.source;"
            " return !o.added && o.layer === 'base' && o.actor === a.pivot; }); }")
    car_body, van_body, ufo_door = (page.evaluate(body, f) for f in ('car', 'van', 'frameless-door'))
    if prop:
        page.evaluate('id => viewer.select(id)', prop)
        assert 'Builds from' not in page.locator('#details').inner_text()
    if car_body:
        page.evaluate('id => viewer.select(id)', car_body)
        assert 'Builds from' not in page.locator('#details').inner_text()
    if van_body:
        page.evaluate('id => viewer.select(id)', van_body)
        assert 'Builds from' not in page.locator('#details').inner_text()
    if ufo_door:
        page.evaluate('id => viewer.select(id)', ufo_door)
        assert 'Builds from' not in page.locator('#details').inner_text()
    # Fracturing pieces (walls, storey floors) and physics props build since 9 November 2026: no milestone chip. A
    # fracturing piece of its own has a pose rule, as the assemblies do: Align to game pose puts it on it (since
    # 21 November 2026; it moves as any piece under every snap); a physics prop has none.
    single = ("cls => [...viewer.roots.keys()].find(id => { const r = viewer.roots.get(id), o = r.userData.source;"
              " return r.visible && !o.added && o.layer === 'base' && o.actorClass === cls"
              " && !(viewer.families()?.assemblies ?? []).some(a => a.members.includes(o.actor)); })")
    wall, physics_prop = (page.evaluate(single, c) for c in ('XComDecoFracLevelActor', 'KAsset'))
    if wall:
        page.evaluate('id => viewer.select(id)', wall)
        details = page.locator('#details').inner_text()
        assert 'Builds from' not in details and 'Recipe snap' not in details, details
        assert page.evaluate('viewer.gizmo.gridPiece')
        assert page.locator('#alignPose').is_visible()
        page.evaluate("viewer.setSnapMode('tile')")
        assert page.locator('#snapBadge').inner_text() == '96'
        page.evaluate("viewer.setSnapMode('off')")
    if physics_prop:
        page.evaluate('id => viewer.select(id)', physics_prop)
        details = page.locator('#details').inner_text()
        assert 'Builds from' not in details and 'Recipe snap' not in details, details
    # Collectibles (Temple Ship's power cores) build in M1 too, marked as mission loot.
    core = page.evaluate("() => [...viewer.roots.keys()].find(id => { const r = viewer.roots.get(id), o = r.userData.source;"
                         " return r.visible && !o.added && o.actorClass === 'XComCollectible'; })")
    if core:
        page.evaluate('id => viewer.select(id)', core)
        details = page.locator('#details').inner_text()
        assert 'Builds from' not in details and 'Mission loot' in details, details
    # a collectible's copy is loot too, as the Build makes it (compiler.py LOOT_NOTES; Discord S15: the chip said not)
    copy_note = page.evaluate("async () => (await import('/pieces.js')).lootNote({ actorClass: 'XComCollectible', added: {} })")
    assert copy_note['label'] == 'Mission loot' and 'counts it as mission loot' in copy_note['title'], copy_note
    page.evaluate('id => viewer.select(id)', original)


# What the recipe snap checks: every edit of a ladder, door, car or van (an original moved, a copy) against the pose
# rule (poserule.js gridMove), from the project state the page would save.
GRID_EDITS = """async () => {
  const rule = await import('/poserule.js'), state = viewer.editState(), origin = viewer.data.tileGrid.origin;
  const key = t => `${t.package}|${t.level}|${t.actor}`;
  const originals = new Map([...viewer.roots.values()].map(r => r.userData.source).filter(o => !o.added)
    .map(o => [key({ package: o.sourcePackage, level: o.layer, actor: o.actor }), o]));
  const records = [...state.overrides.filter(o => !o.deleted).map(o => ({ from: o.target, location: o.location, rotation: o.rotation })),
                   ...state.added.map(a => ({ from: a.from, location: a.location, rotation: a.rotation, prefab: a.prefab }))];
  return records.flatMap(({ from: target, ...rec }) => {
    rec.actor = target.actor;
    const o = originals.get(key(target)), from = o && viewer.recipeOf(o.id);
    if (!from) return [];
    const m = rule.gridMove(from.location, from.rotation, rec.location, rec.rotation, origin);
    return [{ actor: rec.actor, prefab: rec.prefab ?? null, valid: m.valid, why: m.why, turns: m.turns, translation: m.translation }];
  });
}"""


def check_recipe(page):
    """The pose rule of ladders, doors, cars and vans (private/plans/done/cars-doors-ladders-plan.md, sections 3.2 and
    8), on Bar (the page's pose rule on the compiler's cases is shared_cases_test.mjs's): the map's assemblies are
    served; a door selects with its frame, linked pieces on or off, and its copy keeps them together. Such a piece moves
    as any piece does under every snap (the recipe snap went on 21 November 2026: the custom geometry improvements
    plan, D4): with snap off a typed move takes it off the grid, its chip says so, and the piece panel's Align to Game
    pose puts it back on its rule; under tile snap a typed move and turn step whole tiles, levels and quarter turns
    from where it stands, so a piece on its rule stays on it; copies pasted and turned while placing are put on the
    rule by Game pose."""
    original = page.evaluate('viewer.gizmo.active')
    families = page.evaluate('viewer.families()')
    assert families and Counter(a['family'] for a in families['assemblies']) == {'car': 13, 'door': 7, 'van': 4, 'ladder': 2}, families
    first = lambda family: next(a for a in families['assemblies'] if a['family'] == family)
    pl = 'TheWorld.PersistentLevel.'
    root_of = lambda actor: page.evaluate("a => [...viewer.roots.keys()].find(k => { const o = viewer.roots.get(k).userData.source;"
                                          " return !o.added && o.actor === a; })", actor)
    selected_actors = lambda: sorted(set(page.evaluate('viewer.gizmo.selection().map(r => r.userData.source.actor)')))
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2

    def paste(turns=0, dx=0):
        page.keyboard.press('Control+c')
        page.mouse.move(cx + dx, cy); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible')
        for _ in range(turns): page.keyboard.press('r')
        n = page.evaluate('viewer.roots.size')
        page.mouse.click(cx + dx, cy)
        page.wait_for_function('n => viewer.roots.size > n', arg=n)

    # A door selects with its frame, whatever linked pieces says.
    door = first('door')
    linked_on = 'on' in (page.locator('#editLinked').get_attribute('class') or '')
    for _ in range(2):
        page.evaluate('id => viewer.select(id)', root_of(door['pivot']))
        assert selected_actors() == door['members'], (selected_actors(), door)
        page.locator('#editLinked').click()
    assert ('on' in (page.locator('#editLinked').get_attribute('class') or '')) == linked_on
    # A ladder with snap off: no pose rule held, and a typed move takes it off the grid (its chip says so; the Build
    # warns); undone, the chip goes.
    ladder = pl + 'XComLadder_3'
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', root_of(ladder))
    assert page.evaluate('viewer.gizmo.snap') == 'off'
    assert page.locator('#snapBadge').inner_text() == '' and page.evaluate('viewer.gizmo.gridPiece')
    details = page.locator('#details').inner_text()
    assert 'Recipe snap' not in details and 'Off the grid' not in details and 'Builds from' not in details, details
    start = page.evaluate('viewer.gizmo.pose()')
    type_pose(page, 'posX', 150); type_pose(page, 'rotY', 30)
    moved = page.evaluate('viewer.gizmo.pose()')
    assert abs(moved['location'][0] - start['location'][0] - 150) < 0.01, (start, moved)
    assert abs((moved['rotation'][1] - start['rotation'][1] - 30 + 180) % 360 - 180) < 0.01, (start, moved)
    assert 'Off the grid' in page.locator('#details').inner_text()
    edits = page.evaluate(GRID_EDITS)
    assert [e['actor'] for e in edits] == [ladder] and not edits[0]['valid'], edits
    assert set(edits[0]['why']) == {'whole tiles', 'quarter turns'}, edits
    # Align to Game pose (the piece panel's Align section) puts it on its rule: the chip goes, one undo step
    assert page.locator('#alignPose').is_visible()
    page.locator('#alignPose').click()
    assert 'Off the grid' not in page.locator('#details').inner_text()
    edits = page.evaluate(GRID_EDITS)
    assert [e['actor'] for e in edits] == [ladder] and edits[0]['valid'], edits
    for _ in range(3): page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    assert 'Off the grid' not in page.locator('#details').inner_text()
    # Tile snap: the snap button says 96, and it builds (no milestone); a typed move and turn step from where it
    # stands, so it stays on its rule; a typed tilt under a step of 90 leaves it as it was.
    page.evaluate("viewer.setSnapMode('tile')")
    assert page.locator('#snapBadge').inner_text() == '96'
    details = page.locator('#details').inner_text()
    assert 'Recipe snap' not in details and 'Builds from' not in details, details
    # Its climb's ends (ladders.js, the twin of ladders.py): foot (11, 23, 0), top (12, 23, 6) on the roof; its helper
    # in patch_bar. Moved four tiles along its wall (-Y), its top lands where the roof ends: marked, and the chip says so.
    ends = page.evaluate('id => viewer.ladderEnds(id)', root_of(ladder))
    assert (ends['footTile'], ends['linkedTop'], ends['climbs']) == ([11, 23, 0], [12, 23, 6], True), ends
    assert 'Climbs' in details and 'Patch helper' in details, details
    assert [h['actor'] for h in families['helpers'][ladder]] == [pl + 'XComLadder_11']
    assert page.evaluate('viewer.ladderMarks.visible')
    type_pose(page, 'posY', -384)
    ends = page.evaluate('id => viewer.ladderEnds(id)', root_of(ladder))
    assert (ends['footTile'], ends['climbs'], ends['why']) == ([11, 19, 0], False, ['top']), ends
    assert "Won't climb: no floor at its top" in page.locator('#details').inner_text()
    page.keyboard.press('Control+z')
    # Export 15: the landing's Kismet hides the grounded Skyranger, so its chip says Mission script (mission-linked)
    if page.evaluate('viewer.data.exporterVersion') >= 15:
        page.evaluate('id => viewer.select(id)', root_of(pl + 'XComLevelActor_138'))
        assert 'Mission script' in page.locator('#details').inner_text()
        page.evaluate('id => viewer.select(id)', root_of(ladder))
    assert page.evaluate('id => viewer.ladderEnds(id).climbs', root_of(ladder))
    start = page.evaluate('viewer.gizmo.pose()')
    type_pose(page, 'posX', 150)
    moved = page.evaluate('viewer.gizmo.pose()')
    assert abs(moved['location'][0] - start['location'][0] - 192) < 0.01, (start, moved)
    type_pose(page, 'posZ', 40); type_pose(page, 'rotY', 50); type_pose(page, 'rotP', 20)
    turned = page.evaluate('viewer.gizmo.pose()')
    assert abs(turned['location'][2] - start['location'][2] - 64) < 0.01, (start, turned)
    assert abs((turned['rotation'][1] - start['rotation'][1] - 90 + 180) % 360 - 180) < 0.01, (start, turned)
    assert abs(turned['rotation'][0]) < 0.01 and abs(turned['rotation'][2]) < 0.01, turned
    edits = page.evaluate(GRID_EDITS)
    assert [e['actor'] for e in edits] == [ladder] and edits[0]['valid'] and edits[0]['turns'] == 1, edits
    # Copies of a door, a car and a van, pasted and turned while placing, are put on the rule by Game pose; the door's
    # copies stay linked.
    for family, turns, dx in (('door', 0, 0), ('car', 1, 60), ('van', 1, -60)):
        assembly = first(family)
        page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', root_of(assembly['pivot']))
        before = set(page.evaluate('viewer.editState().added.map(a => a.id)'))
        paste(turns, dx)
        page.evaluate('viewer.alignToGamePose()')
        copies = page.evaluate('viewer.gizmo.selection().map(r => r.userData.source)')
        assert all(c['added'] for c in copies) and len({c['actor'] for c in copies}) == len(assembly['members']), (family, copies)
        assert page.evaluate('viewer.editState().added.length') == len(before) + len(assembly['members'])
    edits = page.evaluate(GRID_EDITS)
    assert all(e['valid'] for e in edits), [e for e in edits if not e['valid']]
    assert sorted(Counter(e['turns'] for e in edits).items()) == [(0, len(first('door')['members'])),
        (1, 1 + len(first('car')['members']) + len(first('van')['members']))], edits
    door_tags = {e['prefab'] for e in edits if e['actor'] in first('door')['members']}
    assert len(door_tags) == 1 and next(iter(door_tags)).endswith(':' + door['pivot'].split('.')[-1]), door_tags
    # A piece of no grid family has no Game pose.
    page.evaluate('id => viewer.select(id)', original)
    assert page.locator('#snapBadge').inner_text() == '96' and not page.evaluate('viewer.gizmo.gridPiece')
    assert page.locator('#alignPose').is_hidden()
    page.evaluate("viewer.setSnapMode('off')")
    assert page.locator('#snapBadge').inner_text() == ''
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0
    page.evaluate('id => viewer.select(id)', original)


ZOOM_STATE = """p => { const c = viewer.camera, t = viewer.controls.target, v = new THREE_V(...p);
  const s = v.clone().project(c), r = viewer.renderer.domElement.getBoundingClientRect();
  return { distance: c.position.distanceTo(v), target: c.position.distanceTo(t), near: c.near,
           screen: [r.left + (s.x + 1) / 2 * r.width, r.top + (1 - s.y) / 2 * r.height] }; }"""


def check_zoom(page):
    """The wheel zooms towards what is under the cursor (navigation.js wheelZoom), all the way in: framed on the whole
    map, a piece off to the side, far from the orbit target, is zoomed to from 40 notches until the camera is a few
    units from it, the point staying under the cursor; OrbitControls' own zoom stalled at the target's distance. Zoomed
    back out as far, the camera returns to about where it was."""
    page.evaluate('viewer.select(null); viewer.frame()')
    settled(page, CAMERA)
    box = page.locator('#viewport > canvas').bounding_box()
    # a point under which a piece stands, as far from the orbit target as can be found; whole pixels, as the wheel
    # events give them (a quarter pixel is some 15 units on the map framed whole)
    spot = page.evaluate("""b => { let best = null;
      for (let i = 1; i < 8; i++) for (let j = 1; j < 8; j++) {
        const x = Math.round(b.x + b.width * i / 8), y = Math.round(b.y + b.height * j / 8), hit = viewer.pick(x, y);
        if (!hit) continue;
        const away = hit.point.distanceTo(viewer.controls.target);
        if (!best || away > best.away) best = { x, y, away, point: hit.point.toArray() };
      }
      return best; }""", box)
    assert spot, 'nothing under the cursor anywhere on the framed map'
    state = ZOOM_STATE.replace('THREE_V', 'viewer.camera.position.constructor')
    start = page.evaluate(state, spot['point'])
    assert spot['away'] > start['target'] * 0.15, (spot, start)
    page.mouse.move(spot['x'], spot['y'])
    for _ in range(40):
        page.mouse.wheel(0, -100)
    settled(page, CAMERA)
    close = page.evaluate(state, spot['point'])
    assert close['distance'] < max(30.0, start['distance'] * 0.01), (start, close)
    assert close['distance'] < spot['away'] * 0.5, (spot, close)    # well past where the old zoom stalled
    assert abs(close['screen'][0] - spot['x']) < 3 and abs(close['screen'][1] - spot['y']) < 3, (spot, close)
    assert close['near'] <= start['near'] and abs(close['target'] - close['distance']) < close['distance'], close
    for _ in range(40):
        page.mouse.wheel(0, 100)
    settled(page, CAMERA)
    back = page.evaluate(state, spot['point'])
    assert abs(back['distance'] - start['distance']) < start['distance'] * 0.05, (start, back)
    assert back['near'] == start['near'], (start, back)
    page.evaluate('viewer.frame()')


def check_groups(page):
    """Groups: two pieces grouped (Ctrl+G) select and move as one, shown by the panel, a chip, a gold selection box
    and a search tag; there is no unlocking; break together is a group option (for breakable pieces); a copied group
    pastes as a new group; Ctrl+Shift+G ungroups; groups nest. Each is one undo step."""
    original = page.evaluate('viewer.gizmo.active')
    free = ("cls => [...viewer.roots.keys()].filter(k => { const r = viewer.roots.get(k), o = r.userData.source;"
            " return r.visible && !o.hidden && !o.environment && !o.added && viewer.gizmo.linkedCount(k) === 0 && !viewer.recipeOf(k)"
            " && (!cls || o.actorClass === cls); }).slice(0, 2)")
    pair = page.evaluate(free, 'XComDestructibleActor')
    breakable = len(pair) == 2
    if not breakable: pair = page.evaluate(free, None)
    a, b = pair
    actors = "() => [...new Set(viewer.gizmo.selection().map(r => r.userData.source.id))].sort()"
    groups = 'viewer.editState().groups'
    gold = 'viewer.highlight.material.color.getHex() === 0xe8bd5c'
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', pair)
    assert page.locator('#groupBox').is_visible() and page.locator('#groupMake').is_visible()
    assert page.locator('#groupTitle').text_content() == 'Not grouped' and not page.evaluate(gold)
    page.keyboard.press('Control+g')
    [g] = page.evaluate(groups)
    assert g['locked'] and not g['breakTogether'] and len(g['members']) == 2, g
    assert page.locator('#groupTitle').text_content() == 'Group · 2 pieces' and page.evaluate(gold)
    assert page.locator('#details .chip.group').inner_text() == 'Group of 2'
    assert page.locator('#groupMake').is_hidden() and page.locator('#groupDissolve').is_visible()
    assert page.locator('#groupLock, #groupPick, #groupOuter').count() == 0
    # One piece picked selects the group, linked pieces on or off, and a move takes both.
    page.locator('#editLinked').click()
    page.evaluate('id => viewer.select(id)', a)
    assert page.evaluate(actors) == sorted(pair) and page.evaluate(gold)
    type_pose(page, 'posX', 96)
    assert len(page.evaluate('viewer.editState().overrides')) == 2
    page.locator('#editLinked').click()
    # No unlocking: Ctrl+G on a group leaves it as it is.
    page.evaluate('id => viewer.select(id)', b)
    page.keyboard.press('Control+g')
    assert page.evaluate(groups) == [g] and page.evaluate(actors) == sorted(pair)
    # Break together, for breakable pieces only.
    if breakable:
        assert page.locator('#groupBreak').is_enabled()
        page.locator('#groupBreak').check()
        assert page.evaluate(groups)[0]['breakTogether']
    else:
        assert page.locator('#groupBreak').is_disabled() and page.locator('#groupNote').text_content().startswith('Breaking together needs')
    # A copied group pastes as a new group of the copies, with the same lock and options; undo takes both away.
    page.keyboard.press('Control+c')
    box = page.locator('#viewport > canvas').bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.wait_for_function('viewer.editState().groups.length === 2')
    pasted = [x for x in page.evaluate(groups) if x['id'] != g['id']][0]
    assert all('added' in m for m in pasted['members']) and pasted['locked'] and pasted['breakTogether'] == breakable, pasted
    page.keyboard.press('Control+z')
    assert len(page.evaluate(groups)) == 1
    # Ungroup ends it; undo brings it back; Reset all clears groups with the rest.
    page.evaluate('id => viewer.select(id)', a)
    page.keyboard.press('Control+Shift+g')
    assert page.evaluate(groups) == [] and page.evaluate(actors) == [a]
    page.keyboard.press('Control+z')
    assert len(page.evaluate(groups)) == 1
    # Add to group (19 November 2026): the group and a piece in no group selected: Add to group beside Group
    # puts the piece in the group (no new group), one undo step; two loose pieces, or the group alone, have no Add to group
    loose = [k for k in page.evaluate(free.replace('.slice(0, 2)', '.slice(0, 6)'), None) if k not in pair]
    if len(loose) >= 2:
        third, fourth = loose[:2]
        [kept] = page.evaluate(groups)
        page.evaluate('([a, c]) => { viewer.select(a); viewer.select(c, true); }', [a, third])
        assert page.locator('#groupMake').is_visible() and page.locator('#groupAdd').is_visible()
        assert 'Add to group puts the 1 piece in the group instead' in page.locator('#groupText').text_content()
        page.locator('#groupAdd').click()
        [added] = page.evaluate(groups)
        assert added['id'] == g['id'] and len(added['members']) == 3 and added['breakTogether'] == kept['breakTogether'], added
        page.evaluate('id => viewer.select(id)', third)
        assert page.evaluate(actors) == sorted([a, b, third]) and page.locator('#groupTitle').text_content() == 'Group · 3 pieces'
        assert page.locator('#groupAdd').is_hidden()
        page.keyboard.press('Control+z')
        [back] = page.evaluate(groups)
        assert len(back['members']) == 2, back
        page.evaluate('([c, d]) => { viewer.select(c); viewer.select(d, true); }', [third, fourth])
        assert page.locator('#groupAdd').is_hidden()
    page.locator('#editResetAll').click()
    assert page.evaluate(groups) == [] and page.evaluate('viewer.changes().total') == 0
    # Groups nest (prefab plan 5.4): two groups grouped; a piece picks the outermost group; ungrouping peels one
    # level; a copy pastes the tree.
    four = page.evaluate(free.replace('.slice(0, 2)', '.slice(0, 4)'), None)
    if len(four) == 4:
        w, x, y, z = four
        pick = "ids => { viewer.select(ids[0]); for (const i of ids.slice(1)) viewer.select(i, true); }"
        for pair2 in ([w, x], [y, z]):
            page.evaluate(pick, pair2); page.keyboard.press('Control+g')
        page.evaluate(pick, [w, y])
        assert page.evaluate(actors) == sorted(four) and page.locator('#groupTitle').text_content() == 'Not grouped'
        page.keyboard.press('Control+g')
        tree = page.evaluate(groups)
        assert len(tree) == 3 and sum(1 for g in tree for m in g['members'] if 'group' in m) == 2, tree
        page.evaluate('id => viewer.select(id)', x)
        assert page.evaluate(actors) == sorted(four) and '2 groups inside' in page.locator('#groupTitle').text_content()
        page.keyboard.press('Control+g')        # already a group: nothing changes
        assert page.evaluate(groups) == tree and page.evaluate(actors) == sorted(four)
        count = page.evaluate('viewer.roots.size')
        page.evaluate('id => viewer.select(id)', z)
        page.keyboard.press('Control+c')
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.wait_for_function('n => viewer.roots.size === n', arg=count + 4)
        assert len(page.evaluate(groups)) == 6 and len(page.evaluate(actors)) == 4
        page.keyboard.press('Control+z')
        assert len(page.evaluate(groups)) == 3 and page.evaluate('viewer.roots.size') == count
        page.evaluate('id => viewer.select(id)', z)
        page.keyboard.press('Control+Shift+g')  # the outer group ends, the two inside stay
        assert len(page.evaluate(groups)) == 2
        page.evaluate('id => viewer.select(id)', z)
        assert page.evaluate(actors) == sorted([y, z])
        page.locator('#editResetAll').click()
        assert page.evaluate(groups) == [] and page.evaluate('viewer.changes().total') == 0
    page.evaluate('id => viewer.select(id)', original)


def check_copy_drag(page):
    """Shift held as a move handle is taken drags a copy along that axis: the original stays (a stand-in is drawn in
    its place meanwhile), the copy lands where it was dragged to and is the selection, as one undo step. Escape during
    the drag makes no copy."""
    original = page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    steps = page.evaluate('viewer.gizmo.undoDepth()')     # the checks before this one leave undo steps (a Reset all)
    a = page.evaluate("() => [...viewer.roots.keys()].find(k => { const r = viewer.roots.get(k), o = r.userData.source;"
                      " return r.visible && !o.hidden && !o.environment && !o.added && !o.stream && viewer.gizmo.linkedCount(k) === 0"
                      " && !viewer.recipeOf(k) && viewer.pieceBox(k); })")
    page.evaluate('id => { viewer.select(id); viewer.frame(); }', a)
    settled(page, CAMERA)
    if page.evaluate("viewer.gizmo.mode !== 'translate'"): page.evaluate("viewer.gizmo.setMode('translate')")
    if page.evaluate("viewer.gizmo.space !== 'world'"): page.evaluate('viewer.gizmo.toggleSpace()')
    count, group = page.evaluate('viewer.roots.size'), page.evaluate('viewer.gizmo.selection().length')
    matrix = "id => viewer.roots.get(id).matrix.elements.slice()"
    before, start = page.evaluate(matrix, a), page.evaluate('viewer.gizmo.pose()')
    # the X arrow on the screen: from the pivot towards a point further along the axis, until the handle lights up
    ends = page.evaluate("""async () => { const T = await import('/vendor/three/three.module.js');
      const c = viewer.gizmo.controls, at = c.object.getWorldPosition(new T.Vector3()), box = viewer.renderer.domElement.getBoundingClientRect();
      const screen = v => { const p = v.clone().project(viewer.camera); return [box.left + (p.x + 1) / 2 * box.width, box.top + (1 - p.y) / 2 * box.height]; };
      return [screen(at), screen(at.clone().add(new T.Vector3(viewer.camera.position.distanceTo(at) * 0.1, 0, 0)))]; }""")
    (x0, y0), (x1, y1) = ends
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    assert length > 5, ends
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    for d in range(20, 140, 6):
        page.mouse.move(x0 + ux * d, y0 + uy * d)
        if page.evaluate('viewer.gizmo.controls.axis') == 'X': break
    assert page.evaluate('viewer.gizmo.controls.axis') == 'X', ends
    hx, hy = x0 + ux * d, y0 + uy * d
    # Escape during a Shift drag: nothing is copied or moved
    serial = page.evaluate('viewer.copySerial()')
    page.keyboard.down('Shift'); page.mouse.down(); page.mouse.move(hx + ux * 60, hy + uy * 60, steps=5)
    assert 'copy' in page.locator('#dragHint').inner_text()
    assert page.evaluate('viewer.roots.size') == count
    page.keyboard.press('Escape'); page.mouse.up(); page.keyboard.up('Shift')
    # the release handled (the gizmo's mouseUp, which hands the copy on), and no paste begun: a paste numbers its copies
    # before anything it waits for, so one begun would show in the serial at once
    page.wait_for_function('!viewer.gizmo.controls.dragging')
    assert page.evaluate('viewer.copySerial()') == serial, (serial, page.evaluate('viewer.copySerial()'))
    assert page.evaluate('viewer.roots.size') == count and page.evaluate(matrix, a) == before
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.gizmo.undoDepth()') == steps
    # the drag itself: the copy along X only, the original where it was
    page.mouse.move(hx, hy)
    assert page.evaluate('viewer.gizmo.controls.axis') == 'X'
    page.keyboard.down('Shift'); page.mouse.down(); page.mouse.move(hx + ux * 80, hy + uy * 80, steps=6)
    page.mouse.up(); page.keyboard.up('Shift')
    page.wait_for_function('n => viewer.roots.size === n', arg=count + group)
    assert page.evaluate(matrix, a) == before
    assert page.evaluate('viewer.gizmo.selection().every(r => r.userData.source.added)')
    assert page.evaluate('viewer.gizmo.selection().length') == group
    placed, changes = page.evaluate('viewer.gizmo.pose()'), page.evaluate('viewer.changes()')
    assert abs(placed['location'][0] - start['location'][0]) > 1, (start, placed)
    assert all(abs(placed['location'][k] - start['location'][k]) < 0.01 for k in (1, 2)), (start, placed)
    assert all(abs(p - q) < 0.01 for p, q in zip(placed['rotation'], start['rotation'])), (start, placed)
    assert changes['moved'] == 0 and changes['added'] >= 1, changes
    # one undo step takes the copy away and gives the selection back
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    assert page.evaluate('viewer.gizmo.active') == a and page.evaluate('viewer.gizmo.undoDepth()') == steps
    # without Shift the handle moves the piece itself
    page.mouse.move(hx, hy); page.mouse.down(); page.mouse.move(hx + ux * 80, hy + uy * 80, steps=6); page.mouse.up()
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().moved') >= 1
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    page.evaluate('id => viewer.select(id)', original)

def check_box_select(page):
    """Box select: T arms the tool and a drag over the view draws the box; its bar counts the pieces whose middle is
    inside; a face handle stretches it and the middle dot moves it; Enter selects what is inside (a group whole),
    Shift+Enter adds to the selection; Escape and the Buildings view put it away. Nothing of it is an edit."""
    original = page.evaluate('viewer.gizmo.active')
    state = page.evaluate('viewer.projectState()')
    page.evaluate('viewer.select(null)')
    free = ("() => [...viewer.roots.keys()].filter(k => { const r = viewer.roots.get(k), o = r.userData.source;"
            " return r.visible && !o.hidden && !o.environment && !o.added && !o.stream && viewer.gizmo.linkedCount(k) === 0"
            " && !viewer.recipeOf(k) && viewer.pieceBox(k); })")
    ids = page.evaluate(free)
    middle = "id => { const b = viewer.pieceBox(id); return [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]; }"
    a = ids[0]
    at = page.evaluate(middle, a)
    # a second piece whose middle is well away from the first's
    b = next(k for k in ids[1:] if max(abs(p - q) for p, q in zip(page.evaluate(middle, k), at)) > 60)
    around = lambda c, r=10: [c[0] - r, c[1] - r, c[2] - r, c[0] + r, c[1] + r, c[2] + r]
    actors = "() => [...new Set(viewer.gizmo.selection().map(r => r.userData.source.id))].sort()"
    # T arms the tool; a drag over the view draws the box, and the tool is done
    page.evaluate('viewer.frame()')
    settled(page, CAMERA)
    page.keyboard.press('t')
    assert page.evaluate('viewer.pickTool()') and 'on' in page.locator('#editBox').get_attribute('class')
    assert 'Box select' in page.locator('#dragHint').inner_text() and page.locator('#boxBar').is_hidden()
    view = page.locator('#viewport > canvas').first.bounding_box()
    cx, cy = view['x'] + view['width'] / 2, view['y'] + view['height'] / 2
    page.mouse.move(cx - 60, cy + 40); page.mouse.down(); page.mouse.move(cx + 80, cy + 120, steps=6); page.mouse.up()
    box = page.evaluate('viewer.pickBox()')
    assert box and box[3] - box[0] >= 8 and box[4] - box[1] >= 8 and box[5] > box[2], box
    assert not page.evaluate('viewer.pickTool()') and page.locator('#boxBar').is_visible()
    assert 'on' in page.locator('#editBox').get_attribute('class')
    # the bar counts the pieces whose middle is inside: one small box around a piece's middle holds it
    page.evaluate('box => viewer.setPickBox(box)', around(at))
    hits = page.evaluate('viewer.pickHits()')
    assert a in hits and b not in hits, (a, hits)
    assert page.locator('#boxBarText').inner_text() == f"{len(hits)} piece{'' if len(hits) == 1 else 's'} inside"
    # a face handle stretches that face alone; the middle dot moves the box and keeps its size
    before = page.evaluate('viewer.pickBox()')
    hx, hy = page.evaluate("viewer.pickFaceHandle('z1')")
    mx, my = page.evaluate('viewer.pickMoveHandle()')
    page.mouse.move(hx, hy); page.mouse.down(); page.mouse.move(hx, hy - 60, steps=6); page.mouse.up()
    after = page.evaluate('viewer.pickBox()')
    assert after[5] > before[5] and after[:5] == before[:5], (before, after)
    mx, my = page.evaluate('viewer.pickMoveHandle()')
    page.mouse.move(mx, my); page.mouse.down(); page.mouse.move(mx + 70, my + 10, steps=6); page.mouse.up()
    moved = page.evaluate('viewer.pickBox()')
    assert moved != after and moved[2] == after[2] and moved[5] == after[5], (after, moved)
    assert [round(moved[k + 3] - moved[k]) for k in range(3)] == [round(after[k + 3] - after[k]) for k in range(3)]
    # Enter selects what is inside, and the box goes
    page.evaluate('box => viewer.setPickBox(box)', around(at))
    page.keyboard.press('Enter')
    assert a in page.evaluate(actors) and b not in page.evaluate(actors)
    assert page.evaluate('viewer.pickBox()') is None and page.locator('#boxBar').is_hidden()
    assert 'on' not in page.locator('#editBox').get_attribute('class')
    # Shift+Enter adds to the selection
    page.evaluate('id => viewer.select(id)', b)
    page.evaluate('box => viewer.setPickBox(box)', around(at))
    page.keyboard.press('Shift+Enter')
    picked = page.evaluate(actors)
    assert a in picked and b in picked, picked
    # an empty box selects nothing and stays
    page.evaluate('box => viewer.setPickBox(box)', [at[0], at[1], at[2] + 90000, at[0] + 10, at[1] + 10, at[2] + 90010])
    assert page.locator('#boxBarText').inner_text() == 'No piece inside' and page.locator('#boxTake').is_disabled()
    page.keyboard.press('Enter')
    assert page.evaluate('viewer.pickBox()') and page.evaluate(actors) == picked
    # a group comes whole: one of its pieces inside takes the other
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [a, b])
    page.keyboard.press('Control+g')
    page.evaluate('viewer.select(null)')
    page.evaluate('box => viewer.setPickBox(box)', around(at))
    assert b not in page.evaluate('viewer.pickHits()')
    page.locator('#boxTake').click()
    assert a in page.evaluate(actors) and b in page.evaluate(actors)
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.editState().groups') == []
    # Escape puts the tool and the box away; so does the Buildings view
    page.keyboard.press('t')
    assert page.evaluate('viewer.pickTool()')
    page.keyboard.press('Escape')
    assert not page.evaluate('viewer.pickTool()') and page.locator('#dragHint').is_hidden()
    page.evaluate('box => viewer.setPickBox(box)', around(at))
    page.locator('#boxCancel').click()
    assert page.evaluate('viewer.pickBox()') is None
    if page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview"):
        page.evaluate('box => viewer.setPickBox(box)', around(at))
        page.evaluate('viewer.setVolumesShown(true)')
        assert page.evaluate('viewer.pickBox()') is None and page.locator('#boxBar').is_hidden()
        page.evaluate('viewer.setVolumesShown(false)')
    # nothing of it is an edit
    assert page.evaluate('viewer.projectState()') == state
    page.evaluate('id => viewer.select(id)', original)


def check_map_buildings(page):
    """The map's own buildings made editable (private/plans/done/map-buildings-editable-plan.md, E4): drawn as the
    project's are, a box stretched, a storey pasted on top (a new box, no volume of the map's), a building deleted and
    restored, each undone; what the project would save holds only the changed ones."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 21"):
        return skip('map-buildings', 'needs a map (not a preview) of export 21 or later', whole=True)
    mine = "() => viewer.buildings().filter(b => b.replaces).map(b => b.id)"
    ids = page.evaluate(mine)
    if not ids: return skip('map-buildings', 'the map has no building of its own', whole=True)
    saved = "() => JSON.stringify(viewer.savedBuildings())"
    assert page.evaluate(saved) == '[]' and page.evaluate('viewer.mapEdits()') == {'changed': [], 'gone': []}
    # each editable building of the map is the export's, one id from its actor, every box naming its floor volume
    for b in page.evaluate("viewer.buildings().filter(b => b.replaces)"):
        assert b['id'].startswith('map:PersistentLevel.') and all(v for f in b['floors'] for v in f['volumes']), b
    target = ids[-1]
    box_of = "id => [...viewer.volumeRoots.values()].filter(r => r.userData.volume.building === id && !r.userData.deleted)" \
             ".sort((a, b) => a.userData.volume.floor - b.userData.volume.floor).map(r => [r.userData.source.id, viewer.volumeBox(r)])"
    page.evaluate('viewer.setVolumesShown(true)')
    [(first, box), *_] = page.evaluate(box_of, target)
    # stretched a tile: saved with replaces and the box's own volume; undone, nothing saved
    page.evaluate('([id, b]) => viewer.putVolume(id, [b[0], b[1], b[2], b[3] + 96, b[4], b[5]])', [first, box])
    assert page.evaluate('viewer.mapEdits()')['changed'] == [target]
    [rec] = page.evaluate('viewer.savedBuildings()')
    assert rec['replaces']['actor'].endswith(target.split('.')[-1]) and all(v for f in rec['floors'] for v in f['volumes']), rec
    page.keyboard.press('Control+z')
    assert page.evaluate(saved) == '[]'
    # a storey pasted on top of the top floor: a new box, with no volume of the map's
    *_, (top, _) = page.evaluate(box_of, target)
    page.evaluate('id => viewer.select(id)', top)
    page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
    [rec] = page.evaluate('viewer.savedBuildings()')
    assert None in [v for f in rec['floors'] for v in f['volumes']], rec
    page.keyboard.press('Control+z')
    assert page.evaluate(saved) == '[]'
    # deleted (its boxes all gone: a deleted record), with no list of changed buildings in the view (taken out on
    # 23 November 2026), restored, both undone
    page.evaluate('ids => { viewer.gizmo.setSelection(ids, ids[0]); viewer.deleteVolumes(); }', [i for i, _ in page.evaluate(box_of, target)])
    assert page.evaluate('viewer.savedBuildings()') == [{'id': target, 'replaces': rec['replaces'], 'deleted': True}]
    assert page.locator('#volumeChanged').count() == 0 and 'Restore the map' not in page.locator('#volumePanel').inner_text()
    page.evaluate('id => viewer.restoreMapBuildings([id])', target)
    assert page.evaluate(saved) == '[]'
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.mapEdits()')['gone'] == [target]
    page.keyboard.press('Control+z')
    assert page.evaluate(saved) == '[]'
    # building edits alone count as changes: the chip says so and Reset all is offered; it puts the map's building
    # back and takes the project's own boxes away, as one undo step
    before = page.evaluate('viewer.changes().total')
    page.evaluate('([id, b]) => viewer.putVolume(id, [b[0], b[1], b[2], b[3] + 96, b[4], b[5]])', [first, box])
    own = page.evaluate('([b]) => viewer.addVolumes([{ box: [b[0], b[1], b[2], b[0] + 96, b[1] + 96, b[2] + 192], floor: 0 }], viewer.newBuilding()).length', [box])
    assert own == 1 and len(page.evaluate('viewer.savedBuildings()')) == 2
    count = page.evaluate('viewer.changes()')
    assert count['buildings'] == 2 and count['total'] == before + 2, count
    assert '2 buildings' in page.locator('#editCount').inner_text() and page.locator('#editResetAll').is_visible()
    page.evaluate('viewer.setVolumesShown(false)')
    page.locator('#editResetAll').click()
    assert page.evaluate(saved) == '[]' and page.evaluate('viewer.changes().buildings') == 0
    page.keyboard.press('Control+z')
    assert len(page.evaluate('viewer.savedBuildings()')) == 2
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate(saved) == '[]'
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.setVolumesShown(false)')


# the parts a clear marks in the project (web/clear_parts.js CLEAR_PARTS)
CLEAR_PARTS = ('pieces', 'lights', 'effects', 'triggers')


def check_clear_map(page):
    """Clear map, the ground grid and the landing zones (private/plans/done/clear-map-plan.md, C2 to C4), on an export
    22 map: the dialog's parts and counts (the clear-by-parts plan, section 3); a clear at a smaller size as one undo step
    (the pieces deleted but the landing's, the grid, the ground grid over every tile); a landing zone turned, copied,
    deleted and undone; the clear undone and redone; each part alone and two clears over each other. Nothing is
    saved."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 22"):
        return skip('clear-map', 'needs a map (not a preview) of export 22 or later', whole=True)
    # (a piece a check before left selected, typed-pose's, stays selected: the Map grid's panel opens beside its panel,
    # and its Done is clicked below)
    page.wait_for_function("viewer.zones().length > 0 || viewer.landingLines().lines.length === 0", timeout=10000)
    plan = page.evaluate('viewer.clearPlan()')
    # the landing's pieces the clear keeps: its frame and grounded Skyranger, none on a landing with no frame (the
    # tutorial's: its Skyranger a loose piece)
    framed = page.evaluate("(viewer.data.landings ?? []).some(l => l.actors.some(a => a.role === 'frame'))")
    assert plan['pieces'] > 0 and plan['landing'] >= (1 if framed else 0), plan
    dims = page.evaluate('[...viewer.data.tileGrid.dimensions]')
    bare = page.evaluate('viewer.groundGrid().bare')
    assert bare < dims[0] * dims[1], (bare, dims)       # a map as it is: the grid over holes only
    # the rail's Map grid on the map as it is: handles on the far X and Y sides and the top; a drag out grows the grid by
    # whole tiles or levels, one undo step; a drag in can't make it smaller or lower than the map's own
    import math

    def drag_grid(axis, pixels):
        at = page.evaluate('a => viewer.gridHandleAt(a)', axis)
        p0 = page.evaluate('p => viewer.screenOf(p)', at)
        p1 = page.evaluate('p => viewer.screenOf(p)', [at[k] + (100 if k == axis else 0) for k in range(3)])
        n = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); d = [(p1[0] - p0[0]) / n, (p1[1] - p0[1]) / n]
        # (the press takes the handle under its own point and the release sets the size, in their listeners, which
        # the mouse calls wait for)
        page.mouse.move(*p0)
        page.mouse.down(); page.mouse.move(p0[0] + d[0] * pixels, p0[1] + d[1] * pixels, steps=12); page.mouse.up()
        return page.evaluate('viewer.gridTool().dims')
    page.evaluate("""() => { const b = viewer.data.playableBounds, c = [0, 1, 2].map(k => (b.min[k] + b.max[k]) / 2),
                             s = Math.max(b.max[0] - b.min[0], b.max[2] - b.min[2]);
                             viewer.camera.position.set(c[0] + s * 0.55, s * 0.95, c[2] - s * 0.75); viewer.controls.target.set(c[0], 0, c[2]); viewer.controls.update(); }""")
    settled(page, CAMERA)
    page.locator('#viewsButton').hover(); page.locator('#editGrid').click(); page.mouse.move(5, 300)
    g = page.evaluate('viewer.gridTool()')
    assert g['on'] and g['handles'] == [0, 1, 2] and page.locator('#gridPanel').is_visible(), g
    grown = drag_grid(0, 140)
    assert grown[0] > dims[0] and grown[1:] == dims[1:], (grown, dims)
    assert page.evaluate('viewer.stage()') == dict(grid=grown[:2])
    # a change like any other: counted, and said in the header
    assert page.evaluate('viewer.changes()')['grid'] == 1 and page.evaluate('viewer.changes().total') >= 1
    assert ('grid %d × %d' % (grown[0], grown[1])) in page.locator('#editCount').inner_text()
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes()')['grid'] == 0
    assert page.evaluate('viewer.gridTool().dims') == dims and page.evaluate('viewer.stage()') is None
    assert drag_grid(1, -140) == dims and page.evaluate('viewer.stage()') is None     # never under the map's own
    # higher as it is (13 November): levels by the top handle, the panel saying the Build adds cursor storeys
    if dims[2] < 18:
        higher = drag_grid(2, 120)
        assert higher[2] > dims[2] and higher[:2] == dims[:2], (higher, dims)
        assert page.evaluate('viewer.stage()') == dict(grid=higher), page.evaluate('viewer.stage()')
        assert 'storeys the Build adds' in page.locator('#gridNotes').inner_text()
        page.keyboard.press('Control+z')
        assert page.evaluate('viewer.gridTool().dims') == dims and page.evaluate('viewer.stage()') is None
        assert drag_grid(2, -120) == dims and page.evaluate('viewer.stage()') is None
    page.locator('#gridDone').click()
    assert not page.evaluate('viewer.gridTool()')['on'] and page.locator('#gridPanel').is_hidden()
    # the dialog (the clear-by-parts plan, section 3: design A): a tick for each part with a short count, every part
    # ticked on a map with nothing cleared, the button saying it clears the map (23 November 2026: a short
    # count, no breakdown; no size: a clear keeps the grid)
    page.evaluate("document.getElementById('projectClear').click()")
    text = page.locator('#clearMap').inner_text()
    rows = page.evaluate("""[...document.querySelectorAll('#clearMapParts .check')].map(r => ({ part: r.dataset.part,
        ticked: r.querySelector('input').checked, open: !r.querySelector('input').disabled, words: r.querySelector('.tickval').textContent }))""")
    assert [r['part'] for r in rows] == ['pieces', 'lights', 'effects', 'spawns', 'zones', 'triggers'], rows
    assert all(r['ticked'] == r['open'] for r in rows), rows
    assert rows[0]['words'] == ('%d piece%s' % (plan['pieces'], '' if plan['pieces'] == 1 else 's')), rows[0]
    assert page.locator('#clearMapOk').inner_text() == 'Clear map'
    assert 'SeqAct_' not in text and page.locator('#clearMap input[type=number]').count() == 0, text
    # the map's ambient sounds go with the effects, but the landing's (18 November 2026)
    sounds = page.evaluate("[...viewer.effectRoots.values()].map(r => r.userData.source).filter(o => o.kind === 'sound' && !o.landingActor && !o.stream && !o.added).length")
    if sounds:
        assert ('%d sound' % sounds) in rows[2]['words'], rows[2]
    # the triggers' row counts them from the export (39), and has nothing to take on a map with none
    counts = page.evaluate('viewer.data.triggerCounts ?? null')
    if counts and not counts['volumes'] + counts['sight']:
        assert rows[5]['words'] == 'none' and not rows[5]['open'], rows[5]
    elif counts:
        assert rows[5]['open'] and ('trigger' in rows[5]['words'] or 'sight point' in rows[5]['words']), rows[5]
    # unticked, a part's leftovers that may surprise are said, and the button counts the parts
    tick = lambda part, on: page.locator('#clearMapParts [data-part="%s"] input' % part).set_checked(on)  # noqa: E731
    open_parts = [r['part'] for r in rows if r['open']]
    for part in ('lights', 'effects'):
        if part in open_parts:
            tick(part, False)
    notes = page.locator('#clearMapPlan').inner_text()
    if 'lights' in open_parts and rows[1]['words'] != 'none':
        assert "The map's lights stay where they are" in notes, notes
    if 'effects' in open_parts and rows[2]['words'] != 'none':
        assert 'smoke, fire and sounds stay' in notes, notes
    assert page.locator('#clearMapOk').inner_text() == 'Clear %d parts' % (len(open_parts) - 2)
    # the lights alone: the pieces keep their baked light, and nothing asks what the map is for
    for r in rows:
        if r['open']:
            tick(r['part'], r['part'] == 'lights')
    assert page.locator('#clearMapOk').inner_text() == 'Clear 1 part'
    assert 'keep the light baked into them' in page.locator('#clearMapPlan').inner_text()
    assert page.locator('#clearMapMissions').is_hidden()
    for r in rows:
        tick(r['part'], False) if r['open'] else None
    assert page.locator('#clearMapOk').is_disabled()
    page.keyboard.press('Escape')
    page.evaluate("document.getElementById('projectClear').click()")
    assert all(page.locator('#clearMapParts [data-part="%s"] input' % r['part']).is_checked() == r['open'] for r in rows)
    # the window at the narrow widths (UI-GUIDELINES.md section 3): no part of it past the window's sides, its rows on
    # one line each
    size = page.viewport_size
    for width in (1280, 1024, 800):
        page.set_viewport_size(dict(width=width, height=size['height']))
        box = page.locator('#clearMapForm').bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= width, (width, box)
        assert page.evaluate("(() => { const f = document.getElementById('clearMapForm'); return f.scrollWidth <= f.clientWidth; })()"), width
        heights = page.evaluate("[...document.querySelectorAll('#clearMapParts .check')].map(r => r.getBoundingClientRect().height)")
        assert max(heights) < 40, (width, heights)
    page.set_viewport_size(size)
    # a window taller than the screen (a large zoom) scrolls under its buttons, which stay in view
    size = page.viewport_size
    tall = page.evaluate("document.getElementById('clearMapForm').scrollHeight")
    low = max(150, int(tall * 0.6))
    page.set_viewport_size(dict(width=1280, height=low))
    form = page.evaluate("(() => { const f = document.getElementById('clearMapForm'); f.scrollTop = 0; return [f.scrollHeight, f.clientHeight]; })()")
    assert form[0] > form[1], form
    for at in (0, 10 ** 5):
        page.evaluate("t => { document.getElementById('clearMapForm').scrollTop = t; }", at)
        box = page.locator('#clearMapOk').bounding_box()
        assert box and box['y'] >= 0 and box['y'] + box['height'] <= low, (at, box)
        assert page.evaluate("(() => { const b = document.getElementById('clearMapOk').getBoundingClientRect(); return document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)?.id; })()") == 'clearMapOk'
    page.set_viewport_size(size)
    page.keyboard.press('Escape')
    # what the cleared map is for (mission types plan, D2): the dialog says it asks; a clear from the dialog asks "What
    # is this map for?", the header's abduction or terror ticked (else an abduction); OK sets the missions, one undo
    # step apart from the clear; undone, the clear takes them back to the base map's
    page.evaluate("document.getElementById('projectClear').click()")
    assert 'what the cleared map is for' in page.locator('#clearMapMissions').inner_text()
    page.locator('#clearMapOk').click()
    page.wait_for_selector('#missionsDialog', state='visible', timeout=60000)
    assert page.locator('#missionsTitle').inner_text() == 'What is this map for?'
    default = page.evaluate('viewer.missions()')
    assert len(default) == 1 and (default[0].get('record') is not None or default[0].get('kind') == 'Abduction'), default
    rows = page.locator('#missionsDialog .missionrowwrap')
    assert rows.count() >= len(page.evaluate('viewer.data.missions ?? []')) + 1
    terror = page.locator('#missionsDialog .missionrowwrap', has_text='Terror (added)')
    if terror.count():
        terror.locator('input').check()
        page.locator('#missionsOk').click()
        assert page.evaluate('viewer.missions()') == default + [dict(kind='TerrorSite')]
        assert page.evaluate("[...document.querySelectorAll('#mission option')].map(o => o.value)")[-1] == 'kind:TerrorSite'
        page.keyboard.press('Control+z')
    else:
        page.locator('#missionsCancel').click()
    assert page.evaluate('viewer.missions()') == default and page.evaluate('viewer.cleared()')
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.missions()') is None and not page.evaluate('viewer.cleared()')
    before_zones = page.evaluate('viewer.zones()')
    assert page.locator('#clearMap').is_hidden()
    small = [max(1, dims[0] - 12), max(1, dims[1] - 9), max(1, dims[2] - 4)]
    # the project's added effects go with a clear as its added pieces do, and a map effect it moved is deleted as a
    # moved piece is (23 November 2026: a clear left a boat's 35 added effects standing)
    fx = page.evaluate("""() => [...viewer.effectRoots.values()].map(r => r.userData.source)
                            .filter(o => o.kind === 'effect' && !o.added && !o.stream && !o.landingActor && !o.carriedBy).slice(0, 2)
                            .map(o => ({ actor: o.actor, location: o.location, rotation: o.rotation, id: o.id }))""")
    if len(fx) == 2:
        seeded = page.evaluate("""fx => { const s = viewer.editState(), pkg = viewer.data.name;
            s.added = [...s.added, { id: 'c1ea0000-0000-4000-8000-000000000001', actor: fx[0].actor + '_copy901', kind: 'effect',
                                     from: { package: pkg, level: 'base', actor: fx[0].actor },
                                     location: [fx[0].location[0] + 96, fx[0].location[1], fx[0].location[2]], rotation: fx[0].rotation }];
            s.overrides = [...s.overrides, { target: { package: pkg, level: 'base', actor: fx[1].actor },
                                             location: [fx[1].location[0] + 96, fx[1].location[1], fx[1].location[2]], rotation: fx[1].rotation }];
            return viewer.applyState(s).then(() => fx[0].actor + '_copy901'); }""", fx)
        copied = "a => [...viewer.effectRoots.values()].some(r => r.userData.source.actor === a)"
        assert page.evaluate(copied, seeded)
        assert page.evaluate("id => viewer.effectState(id).moved", fx[1]['id'])
        assert page.evaluate('viewer.clearPlan().addedEffects') == 1 and page.evaluate('viewer.clearPlan().movedEffects') == 1
        page.evaluate('size => viewer.clearMap(size)', small)
        assert not page.evaluate(copied, seeded)
        assert page.evaluate("id => viewer.effectState(id).deleted", fx[1]['id'])
        assert not [o for o in page.evaluate('viewer.editState().added') if o.get('kind') == 'effect']
        page.keyboard.press('Control+z')
        assert page.evaluate(copied, seeded) and not page.evaluate("id => viewer.effectState(id).deleted", fx[1]['id'])
        # (the seeded edits out again: the check goes on from the map as it was)
        page.evaluate("""() => { const s = viewer.editState(); s.added = s.added.filter(o => o.kind !== 'effect' || !o.actor.endsWith('_copy901'));
                                 s.overrides = s.overrides.filter(o => !o.location || !String(o.target.actor).includes('Emitter'));
                                 return viewer.applyState(s); }""")
    page.evaluate('size => viewer.clearMap(size)', small)
    assert page.evaluate('viewer.cleared()') and page.evaluate('viewer.stage()') == dict(grid=small)
    assert page.evaluate('viewer.data.tileGrid.dimensions') == small
    assert page.evaluate('viewer.groundGrid().bare') == small[0] * small[1]
    state = page.evaluate('viewer.editState()')
    assert state['cleared'] == {k: {} for k in CLEAR_PARTS} and sum(1 for o in state['overrides'] if o.get('deleted')) >= plan['pieces'], len(state['overrides'])
    assert page.evaluate('viewer.lastClearMs()') < 1000
    # nothing of Long War's patch levels is drawn on the cleared map: their pieces, lights, effects and spawn points
    # (its build streams none of them, KB-23)
    lwr = "o => o?.stream && viewer.data.streams?.[o.stream]?.kind === 'lwr'"
    assert not [s for s in page.evaluate('viewer.spawns()') if s['layer'] == 'patch']
    assert page.evaluate(f"() => {{ const lwr = {lwr}; return [...viewer.lightRoots.values()].filter(r => r.visible && lwr(r.userData.source)).length; }}") == 0
    page.evaluate('viewer.effectMarkers()')
    assert page.evaluate(f"() => {{ const lwr = {lwr}; return [...viewer.effectRoots.values()].filter(r => r.userData.there && lwr(r.userData.source)).length; }}") == 0
    # the map's pods, Meld points and drop-in points go with it, but one something names; its no-spawn volumes stay; the
    # deleted points draw no marker (18 November 2026)
    if page.evaluate('viewer.spawnAddEntries().length'):
        recs = page.evaluate('(viewer.data.spawns ?? []).filter(o => !o.landing)')
        gone = {m['actor'] for m in page.evaluate('viewer.spawnEdits()') if m.get('deleted')}
        want = {o['actor'] for o in recs if o['kind'] in ('pod', 'meld', 'dropIn') and o.get('listed') is not False and not o.get('unread')
                and not o.get('uses') and not o.get('referencedBy')}
        assert gone == want, (gone ^ want)
        assert not any(s['marked'] for s in page.evaluate('viewer.spawns()') if s['actor'] in gone)
    # one landing zone left: the map's own first landing, used by both games
    left = page.evaluate('viewer.zones()')
    first_own = next((z for z in before_zones if z.get('ew')), before_zones[0])
    assert len(left) == 1 and left[0]['id'] == first_own['id'] and left[0].get('lwr') is not False, left
    assert left[0].get('ew') is (True if page.evaluate('viewer.ownLandingCount()') else None), left
    # the zone left is where the map has its landing (the Bar's line a unit off its frame), so its Skyranger isn't
    # taken for moved and hidden; it stays with its lights, dust and sound, and no other effect or sound is left
    assert page.evaluate('viewer.movedLandingActors()') == [], page.evaluate('viewer.movedLandingActors()')
    page.evaluate('viewer.effectMarkers()')
    left_fx = page.evaluate("""() => [...viewer.effectRoots.values()].filter(r => r.userData.there).map(r => r.userData.source)
                                .filter(o => !o.added && !o.stream).map(o => [o.actor, o.kind, Boolean(o.landingActor)])""")
    assert all(landing for _, _, landing in left_fx), left_fx
    # zones are picked in the Landing zones view only (Shift+Z): drawn over everything, a click on one (its number
    # badge here) picks it and never a piece; the normal view's clicks go to pieces; the Lights view takes over
    badge_at = """() => { let b = null; viewer.landingLayer.traverse(o => { if (o.userData.zoneBadge) b = o; });
                          return b && viewer.screenOf([b.position.x, b.position.z, b.position.y]); }"""
    page.evaluate('viewer.pickZone(null)')
    page.evaluate('viewer.setZonesShown(false)')
    settled(page, CAMERA)
    page.mouse.click(*page.evaluate(badge_at))
    assert page.evaluate('viewer.pickedZone()') is None and not page.evaluate('viewer.zonesOn()')
    page.evaluate('viewer.select(null)')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Shift+Z')
    assert page.evaluate('viewer.zonesOn()') and page.locator('#editZones').get_attribute('aria-pressed') == 'true'
    settled(page, CAMERA)               # the camera eases to rest: the badge's place on screen is its last
    at = page.evaluate(badge_at)
    page.mouse.click(*at)
    assert page.evaluate('viewer.pickedZone()') == left[0]['id'] and page.evaluate('viewer.gizmo.active') is None, \
        (page.evaluate('viewer.pickedZone()'), page.evaluate('viewer.gizmo.active'), at, page.evaluate('p => viewer.zoneHit(p[0], p[1])', at), page.evaluate(
            "p => { const e = document.elementFromPoint(p[0], p[1]); return [e?.tagName, e?.id, innerWidth, innerHeight]; }", at))
    # a piece selected another way than a click on the view (a list, a paste), or box select, leaves the view: one
    # gizmo at a time, and Delete is the zone's only while a zone is what is picked
    some_piece = page.evaluate("[...viewer.roots.keys()].find(id => !viewer.roots.get(id).userData.deleted)")
    page.evaluate('id => viewer.select(id)', some_piece)
    assert not page.evaluate('viewer.zonesOn()') and page.evaluate('viewer.pickedZone()') is None \
        and page.evaluate('viewer.gizmo.active') == some_piece
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.setZonesShown(true)')
    page.evaluate('id => viewer.pickZone(id)', left[0]['id'])
    page.evaluate('viewer.setPickTool(true)')
    assert not page.evaluate('viewer.zonesOn()') and page.evaluate('viewer.pickedZone()') is None
    page.evaluate('viewer.setPickTool(false)')
    page.evaluate('viewer.setZonesShown(true)')
    page.evaluate('id => viewer.pickZone(id)', left[0]['id'])
    page.keyboard.press('Shift+L')
    assert not page.evaluate('viewer.zonesOn()') and page.evaluate('viewer.lightsShown()') and page.evaluate('viewer.pickedZone()') is None
    page.keyboard.press('Shift+N')
    assert page.locator('#editNormal').get_attribute('aria-pressed') == 'true'
    # the Add panel's Landing zones kind: its one entry, then a click on a tile places a zone (one undo step)
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('p')
    page.wait_for_selector('#library:not([hidden])')
    if page.locator('#libMap').is_hidden(): page.locator('#libScope button[data-value="map"]').click()
    page.locator('#libKind').select_option('landing')
    entry = page.locator('#libList .libitem[data-id="zone-new"]')
    assert entry.count() == 1 and 'Landing zone' in entry.inner_text()
    entry.click()
    z = left[0]['location']
    spot = page.evaluate('p => viewer.screenOf(p)', [z[0] + 6 * 96, z[1], z[2] - 64])
    page.mouse.click(*spot)
    assert len(page.evaluate('viewer.zones()')) == 2
    page.keyboard.press('Control+z')
    assert len(page.evaluate('viewer.zones()')) == 1
    page.locator('#libKind').select_option('all')
    page.keyboard.press('p')
    # the Map grid on the cleared map: the top too, and smaller as well as larger
    page.locator('#viewsButton').hover(); page.locator('#editGrid').click(); page.mouse.move(5, 300)
    assert page.evaluate('viewer.gridTool()')['handles'] == [0, 1, 2]
    lower = drag_grid(2, -90)
    assert lower[2] < small[2] and lower[:2] == small[:2], (lower, small)
    narrower = drag_grid(0, -120)
    assert narrower[0] < small[0], (narrower, small)
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.gridTool().dims') == small
    page.keyboard.press('Escape')                                      # Esc puts the handles away
    assert not page.evaluate('viewer.gridTool()')['on']
    # a landing zone: moved and turned with its gizmo, turned by key, copied, deleted, each one undo step
    zones = page.evaluate('viewer.zones()')
    page.evaluate('id => viewer.pickZone(id)', zones[0]['id'])
    assert page.locator('#landingPanel').is_visible()
    assert page.locator('#landingPlay').is_hidden()     # Land here plays a project's build: none is open
    assert page.locator('#landingPanel button', has_text='Turn left').count() == 0
    g = page.evaluate('viewer.zoneGizmo()')
    assert g['enabled'] and g['shown'] and g['mode'] == 'translate', g
    z0 = zones[0]
    assert [round(v) for v in g['at'][:2]] == [round(v) for v in z0['location'][:2]], (g, z0)
    page.evaluate('viewer.frame()'); settled(page, CAMERA)
    page.evaluate("p => viewer.camera.position.set(p[0] + 600, 1400, p[1] - 900)", g['at'])
    page.evaluate("p => { viewer.controls.target.set(p[0], 0, p[1]); viewer.controls.update(); }", g['at'])
    settled(page, CAMERA)

    def grab(axis, points):
        for pt in points:
            page.mouse.move(*pt)        # (the gizmo takes its hovered axis in its pointermove listener, as copy-drag's does)
            if page.evaluate('viewer.zoneGizmo().axis') == axis: return pt
        raise AssertionError("the zone gizmo's %s handle not found" % axis)
    at = g['at']
    p0 = page.evaluate('p => viewer.screenOf(p)', at)
    px = page.evaluate('p => viewer.screenOf([p[0] + 100, p[1], p[2]])', at)
    n = ((px[0] - p0[0]) ** 2 + (px[1] - p0[1]) ** 2) ** 0.5
    d = [(px[0] - p0[0]) / n, (px[1] - p0[1]) / n]
    # its moves follow the snap setting (21 November 2026): whole tiles under tile snap, and smoothly with snap
    # off; either keeps its height (the police station's zone stands 48 over its grid's first level)
    snap_was = page.evaluate('viewer.gizmo.snap')

    def drag_x(snap, length):
        page.evaluate('s => viewer.setSnapMode(s)', snap)
        pt = grab('X', [[p0[0] + d[0] * r, p0[1] + d[1] * r] for r in range(20, 200, 5)])
        page.mouse.down(); page.mouse.move(pt[0] + d[0] * length, pt[1] + d[1] * length, steps=10); page.mouse.up()
        return page.evaluate('viewer.zones()[0]')
    moved = drag_x('tile', 160)
    dx = moved['location'][0] - z0['location'][0]
    assert dx > 0 and dx % 96 == 0 and moved['location'][1:] == z0['location'][1:], (moved, z0)
    assert page.evaluate('viewer.pickedZone()') == z0['id']           # the drag did not let the zone go
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.zones()[0]')['location'] == z0['location']
    moved = drag_x('off', 70)
    dx = moved['location'][0] - z0['location'][0]
    assert dx > 0 and dx % 24 and moved['location'][1:] == z0['location'][1:], (moved, z0)
    page.evaluate('s => viewer.setSnapMode(s)', snap_was)
    # R: the ring, quarter turns about the vertical only
    page.keyboard.press('r'); page.wait_for_timeout(100)    # (a frame drawn: the ring's handles are placed by a render)
    g = page.evaluate('viewer.zoneGizmo()')
    assert g['mode'] == 'rotate', g
    import math
    p0 = page.evaluate('p => viewer.screenOf(p)', g['at'])
    ring = [[p0[0] + r * math.cos(a / 18 * math.pi), p0[1] + r * math.sin(a / 18 * math.pi)] for r in range(40, 220, 8) for a in range(36)]
    pt = grab('Y', ring)
    v = [pt[0] - p0[0], pt[1] - p0[1]]
    t = [-v[1], v[0]]; m = (t[0] ** 2 + t[1] ** 2) ** 0.5
    page.mouse.down()
    for k in range(1, 13): page.mouse.move(pt[0] + t[0] / m * 15 * k + v[0] * 0.05 * k, pt[1] + t[1] / m * 15 * k + v[1] * 0.05 * k)
    page.mouse.up()
    turned = page.evaluate('viewer.zones()[0]')
    assert turned['direction'] != z0['direction'] and turned['location'] == moved['location'], (turned, z0)
    page.keyboard.press('g')
    page.keyboard.press(']')
    assert page.evaluate('viewer.zones()[0].direction') != turned['direction']
    # Used by: no order buttons; Plain EW on as many zones as the map has landings, and on one at least
    assert page.locator('#landingPanel button', has_text='Earlier').count() == 0
    own = page.evaluate('viewer.zones().filter(z => z.ew).length')
    assert own >= 1 and page.locator('#landingEw').is_checked() == bool(page.evaluate('viewer.zones()[0].ew'))
    marked = page.evaluate('viewer.zones().filter(z => z.ew).map(z => z.id)')
    unmarked = page.evaluate('viewer.zones().filter(z => !z.ew).map(z => z.id)')
    if unmarked and len(marked) >= page.evaluate('viewer.ownLandingCount()'):
        page.evaluate('id => viewer.pickZone(id)', unmarked[0])
        page.locator('#landingEw').click()           # (refused: the box goes back)
        assert not page.locator('#landingEw').is_checked() and 'uncheck Plain EW' in page.locator('#projectBanner').inner_text()
        assert page.evaluate('viewer.zones().filter(z => z.ew).length') == own
    if len(marked) == 1:
        page.evaluate('id => viewer.pickZone(id)', marked[0])
        page.locator('#landingEw').click()
        assert page.locator('#landingEw').is_checked() and 'check Plain EW on another' in page.locator('#projectBanner').inner_text()
    page.evaluate('id => viewer.pickZone(id)', z0['id'])
    lwr = page.locator('#landingLwr').is_checked()
    page.locator('#landingLwr').click()
    assert (page.evaluate('viewer.zones()[0].lwr') is not False) == (not lwr)
    # (the panel's Copy copies, as a piece's does: Ctrl+V and a click place it; Ctrl+D makes one beside at once)
    page.locator('#landingCopy').click()
    assert page.evaluate('viewer.clipboard()?.thing') == 'zone' and len(page.evaluate('viewer.zones()')) == len(zones)
    page.evaluate('document.activeElement?.blur?.()'); page.keyboard.press('Control+d')
    assert len(page.evaluate('viewer.zones()')) == len(zones) + 1
    assert not page.evaluate('viewer.zones().at(-1).ew')                # a copy is Long War's
    page.locator('#landingDelete').click()
    assert len(page.evaluate('viewer.zones()')) == len(zones)
    assert not page.evaluate('viewer.zoneGizmo()')['shown']           # no zone picked, no gizmo
    for _ in range(6): page.keyboard.press('Control+z')
    first = page.evaluate('viewer.zones()[0]')        # the six zone edits undone: the first zone faces and stands as it did
    assert (first['direction'], first['location']) == (z0['direction'], z0['location']) and len(page.evaluate('viewer.zones()')) == len(zones), (first, z0)
    # the clear undone: the map's size, the pieces and the mark come back; redone, cleared again
    page.keyboard.press('Escape')
    page.keyboard.press('Control+z')
    assert not page.evaluate('viewer.cleared()') and page.evaluate('viewer.data.tileGrid.dimensions') == dims
    assert [z['id'] for z in page.evaluate('viewer.zones()')] == [z['id'] for z in before_zones]
    assert not any(o.get('deleted') for o in page.evaluate('viewer.editState()')['overrides'])
    page.keyboard.press('Control+y')
    assert page.evaluate('viewer.cleared()')
    # Reset all: the map as exported, its grid, its landing zones and no clear mark; one undo step
    assert page.evaluate('viewer.changes()')['zones'] == 1 and 'landing zones changed' in page.locator('#editCount').inner_text()
    page.locator('#editResetAll').click()
    assert not page.evaluate('viewer.cleared()') and page.evaluate('viewer.stage()') is None
    assert page.evaluate('viewer.editState().landingZones') is None and page.evaluate('viewer.changes().total') == 0
    assert page.evaluate('viewer.data.tileGrid.dimensions') == dims
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.cleared()') and page.evaluate('viewer.data.tileGrid.dimensions') == small
    page.keyboard.press('Control+z')
    assert not page.evaluate('viewer.cleared()')
    # keeping the scenery outside the play area: the window's tick changes its counts; the clear leaves the pieces
    # wholly outside and the lights placed outside, and saves the mark; undone, all of it goes back
    keep, whole = page.evaluate('dims => viewer.clearPlan(dims)', dims), page.evaluate('viewer.clearPlan()')
    page.evaluate("document.getElementById('projectClear').click()")
    tick = page.locator('#clearMapKeepOutside')
    pieces_words = lambda: page.locator('#clearMapParts [data-part="pieces"] .tickval').inner_text()  # noqa: E731
    if tick.is_checked(): tick.uncheck()
    assert pieces_words().startswith('%d piece' % whole['pieces']), pieces_words()
    tick.check()
    assert pieces_words().startswith('%d piece' % keep['pieces']), pieces_words()
    tick.uncheck()                                      # (remembered: left as it was at first)
    page.keyboard.press('Escape')
    if keep['outside']:
        assert keep['pieces'] == plan['pieces'] - keep['outside'], (keep, plan)
        page.evaluate('dims => viewer.clearMap(dims, true)', dims)
        state = page.evaluate('viewer.editState()')
        # (schema 9: every part cleared, each keeping the outside)
        assert state['cleared'] == {k: {'keepOutside': True} for k in CLEAR_PARTS}, state['cleared']
        page.keyboard.press('Control+z')
        assert page.evaluate('viewer.clearedParts()') is None and page.evaluate('viewer.editState()')['cleared'] is None
    # the old clear that kept the triggers (the project's clearKeepsTriggers): every part but the triggers
    page.evaluate('dims => viewer.clearMap(dims, false, true)', dims)
    state = page.evaluate('viewer.editState()')
    assert state['cleared'] == {k: {} for k in CLEAR_PARTS if k != 'triggers'}, state['cleared']
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.clearedParts()') is None and page.evaluate('viewer.editState()')['cleared'] is None
    # each part alone (the clear-by-parts plan, section 2), each one undo step that leaves the rest as it was
    pieces_gone = lambda: page.evaluate("[...viewer.roots.values()].filter(r => r.userData.deleted).length")  # noqa: E731
    lights_gone = lambda: page.evaluate("[...viewer.lightRoots.values()].filter(r => r.userData.deleted).length")  # noqa: E731
    editable = page.evaluate('viewer.clearPlan().editableLights')
    # the lights: the editable ones deleted, the mark set; no piece, no grid, no missions touched; the window then shows
    # the part cleared, counting none, and ticks the rest
    page.evaluate("viewer.clearParts(['lights'])")
    assert page.evaluate('viewer.clearedParts()') == {'lights': {}} and not page.evaluate('viewer.cleared()')
    assert lights_gone() == editable and pieces_gone() == 0, (lights_gone(), editable, pieces_gone())
    assert page.evaluate('viewer.missions()') is None and page.evaluate('viewer.stage()') is None
    assert page.locator('#missionsDialog').is_hidden()
    page.evaluate("document.getElementById('projectClear').click()")
    row = page.locator('#clearMapParts [data-part="lights"]')
    assert row.locator('.chip').is_visible() and not row.locator('input').is_checked(), row.inner_text()
    assert page.locator('#clearMapParts [data-part="pieces"] input').is_checked()
    page.keyboard.press('Escape')
    # then the pieces over it: both marked; undone twice, nothing
    page.evaluate('dims => viewer.clearParts(["pieces"], { size: dims })', dims)
    assert page.evaluate('viewer.clearedParts()') == {'pieces': {}, 'lights': {}} and page.evaluate('viewer.cleared()')
    assert pieces_gone() > 0 and lights_gone() == editable
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.clearedParts()') == {'lights': {}} and pieces_gone() == 0 and lights_gone() == editable
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.clearedParts()') is None and lights_gone() == 0
    # the triggers alone: the mark only
    page.evaluate("viewer.clearParts(['triggers'])")
    assert page.evaluate('viewer.clearedParts()') == {'triggers': {}} and pieces_gone() == 0 and lights_gone() == 0
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.clearedParts()') is None
    # the landing zones alone: one kept, no mark
    page.evaluate("viewer.clearParts(['zones'])")
    assert len(page.evaluate('viewer.zones()')) == 1 and page.evaluate('viewer.clearedParts()') is None
    page.keyboard.press('Control+z')
    assert [z['id'] for z in page.evaluate('viewer.zones()')] == [z['id'] for z in before_zones]
    # the spawn points alone: the map's pods and the like deleted, no mark, no piece
    if page.evaluate('viewer.spawnAddEntries().length'):
        page.evaluate("viewer.clearParts(['spawns'])")
        assert page.evaluate('viewer.clearedParts()') is None and pieces_gone() == 0
        assert any(m.get('deleted') for m in page.evaluate('viewer.spawnEdits()'))
        page.keyboard.press('Control+z')
        assert not any(m.get('deleted') for m in page.evaluate('viewer.spawnEdits()'))


def check_fog_and_colour(page, steps):
    """The window's Fog and colour section (game-likeness plan, C5b; the project's atmosphere, schema 10), on a map of
    export 43: the map's own look first and ringed, four others and every map's in a list; a look taken is one undo
    step, kept as the project's atmosphere (the members that differ), drawn in the Game look's fog and grade and counted
    in the header; a slider is one undo step on release; Reset puts the map's own back."""
    if not page.evaluate('Boolean(viewer.data.atmosphere)'):
        return
    page.wait_for_function('viewer.mapSettings().atmosphere.looks.length > 1', timeout=10000)
    st = page.evaluate('viewer.mapSettings().atmosphere')
    assert st['looks'][0]['name'] == "This map's own" and st['looks'][0]['on'] and st['record'] is None, st
    assert 3 <= len(st['looks']) <= 5 and st['all'] > 10 and not st['changed'], st
    assert st['fog'] and st['colour'].startswith('tint '), st
    # a look of another map: one undo step, the project's record, the view's grade, the header
    page.locator('#mapLooks button.lookcard').nth(1).click()
    taken = page.evaluate('viewer.mapSettings().atmosphere')
    assert taken['record'] and taken['looks'][1]['on'] and taken['changed'], taken
    assert page.evaluate('viewer.editState().atmosphere') == taken['record']
    assert page.evaluate('viewer.changes().atmosphere') == 1 and 'fog and colour changed' in page.locator('#editCount').inner_text()
    colorize = taken['record'].get('postProcess', {}).get('Scene_Colorize')
    if colorize:
        assert page.evaluate('viewer.post.now().settings.Scene_Colorize') == colorize
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.mapSettings().atmosphere.record') is None
    # a slider: the fog's density, one undo step on release
    page.locator('#mapFogFold summary').click()
    page.evaluate("""() => { const s = document.querySelector('#mapFogSliders input'); s.value = '0.25';
                             s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change')); }""")
    assert page.evaluate('viewer.mapSettings().atmosphere.record') == dict(fog=dict(FogDensity=0.25))
    page.locator('#mapLookReset').click()
    assert page.evaluate('viewer.mapSettings().atmosphere.record') is None
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.mapSettings().atmosphere.record') == dict(fog=dict(FogDensity=0.25))
    page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.mapSettings().atmosphere.record') is None
    assert page.evaluate('viewer.changes().atmosphere') == 0 and page.evaluate('viewer.gizmo.canUndo()') == steps


def check_map_settings(page):
    """The Map settings window (map_settings.js; export 39), the user's design B with the volume as a bar: opened from
    the Map menu and from View options' "Sun, moon and sky…"; it lists the sun and sky light; its background sound
    offers the map's own first, the game's other beds and None; a choice and a volume are each one undo step, kept as
    the project's backgroundSound and counted in the header; the server serves each wave of a bed for Play; Esc closes
    it. Its Long War Rebalance section (the project's lwrMapInfo, schema 6): the largest abduction and Hold the Line
    kept off the map, each one undo step, counted in the header. Nothing is saved."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 39"):
        return skip('map-settings', 'needs a map (not a preview) of export 39 or later', whole=True)
    own = page.evaluate('viewer.data.backgroundSound')
    page.evaluate("document.getElementById('mapButton').click()")
    page.locator('#mapSettingsOpen').click()
    page.wait_for_function('viewer.mapSettings().open && (viewer.mapSettings().choices.length > 0 || !viewer.data.backgroundSound)',
                           timeout=10000)
    assert page.locator('#mapSettings').is_visible() and page.locator('#skyList').inner_text().strip()
    st = page.evaluate('viewer.mapSettings()')
    if not own:
        assert 'no background sound' in st['note'] and page.locator('#mapSound').is_disabled(), st
        page.keyboard.press('Escape')
        return
    choices = st['choices']
    assert choices[0]['value'] == own['cue'] and "(this map's)" in choices[0]['label'], choices[:2]
    assert choices[-1] == dict(value='', label='None') and len(choices) >= 27, len(choices)
    assert st['choice'] == own['cue'] and abs(st['volume'] - (own['volume'] or 1)) < 1e-6, st
    other = next(c['value'] for c in choices[1:] if c['value'])
    # a bed chosen: one undo step, kept and counted
    steps = page.evaluate('viewer.gizmo.canUndo()')
    page.select_option('#mapSound', other)
    assert page.evaluate('viewer.backgroundSound()') == dict(cue=other)
    assert page.evaluate('viewer.editState()')['backgroundSound'] == dict(cue=other)
    assert page.evaluate('viewer.changes()')['sound'] == 1 and 'background sound changed' in page.locator('#editCount').inner_text()
    # its volume, set by the bar under the choice: one step on release
    page.evaluate("""() => { const v = document.getElementById('mapSoundVolume'); v.value = '0.5';
                             v.dispatchEvent(new Event('input')); v.dispatchEvent(new Event('change')); }""")
    assert page.evaluate('viewer.backgroundSound()') == dict(cue=other, volume=0.5)
    assert page.locator('#mapSoundVolumeValue').inner_text() == '50%'
    # Play: the server serves every wave of the bed (an Ogg stream); the button plays and stops
    waves = page.evaluate("""async cue => { const beds = (await (await fetch('/background-sounds.json')).json()).sounds;
                                            const row = beds.find(b => b.cue === cue);
                                            return Promise.all(row.waves.map(async (_, k) => { const r = await fetch(`/background-sound.ogg?cue=${encodeURIComponent(cue)}&wave=${k}`, { method: 'HEAD' });
                                                                                               return [r.status, r.headers.get('content-type')]; })); }""", other)
    assert waves and all(w == [200, 'audio/ogg'] for w in waves), waves
    # (a bed the list lacks is 404: the page's log of it is expected)
    bogus = page.evaluate("location.origin + '/background-sound.ogg?cue=No.SuchCue&wave=0'")
    EXPECTED.update({'Failed to load resource: the server responded with a status of 404 (Not Found)', f'HTTP 404: {bogus}'})
    assert page.evaluate("u => fetch(u, { method: 'HEAD' }).then(r => r.status)", bogus) == 404
    page.locator('#mapSoundPlay').click()
    assert page.evaluate('viewer.mapSettings().playing') == other or page.evaluate('viewer.mapSettings().status'), page.evaluate('viewer.mapSettings()')
    if page.evaluate('viewer.mapSettings().playing'):
        page.locator('#mapSoundPlay').click()
        assert page.evaluate('viewer.mapSettings().playing') is None
    # None: no volume of its own, and the bar can't be moved
    page.select_option('#mapSound', '')
    assert page.evaluate('viewer.backgroundSound()') == dict(cue=None) and page.locator('#mapSoundVolume').is_disabled()
    # three steps, undone: the map's own again, and the window follows
    for _ in range(3):
        page.evaluate('viewer.gizmo.undo()')
    assert page.evaluate('viewer.backgroundSound()') is None and page.evaluate('viewer.changes()')['sound'] == 0
    assert page.evaluate('viewer.mapSettings().choice') == own['cue']
    assert page.evaluate('viewer.gizmo.canUndo()') == steps
    # what Long War Rebalance is told of the map: nothing at first; a size and Hold the Line kept off are a step each
    lwr = page.evaluate('viewer.mapSettings().lwr')
    assert page.evaluate('viewer.lwrMapInfo()') is None and (lwr['density'], lwr['noHold']) == ('', False), lwr
    assert [c['value'] for c in lwr['choices']] == ['', 'Light', 'Moderate', 'Heavy', 'Swarming'], lwr['choices']
    assert 'beta 17' in lwr['note'], lwr['note']
    if lwr['shown'] and not lwr['disabled']:
        assert page.locator('#mapLwrSection').is_visible()
        page.select_option('#mapLwrDensity', 'Moderate')
        assert page.evaluate('viewer.lwrMapInfo()') == dict(alienDensity='Moderate')
        page.locator('#mapLwrNoHold').check()
        assert page.evaluate('viewer.lwrMapInfo()') == dict(alienDensity='Moderate', holdTheLine='No')
        assert page.evaluate('viewer.editState()')['lwrMapInfo'] == dict(alienDensity='Moderate', holdTheLine='No')
        assert page.evaluate('viewer.changes()')['info'] == 1 and 'Long War Rebalance map info set' in page.locator('#editCount').inner_text()
        page.select_option('#mapLwrDensity', '')
        assert page.evaluate('viewer.lwrMapInfo()') == dict(holdTheLine='No')
        for _ in range(3):
            page.evaluate('viewer.gizmo.undo()')
        lwr = page.evaluate('viewer.mapSettings().lwr')
        assert page.evaluate('viewer.lwrMapInfo()') is None and (lwr['density'], lwr['noHold']) == ('', False), lwr
        assert page.evaluate('viewer.changes()')['info'] == 0 and page.evaluate('viewer.gizmo.canUndo()') == steps
    else:
        # plain Enemy Within reads none of it: no section there until a project tells something
        assert not lwr['shown'] and page.evaluate("viewer.landingLines().kind === 'ew'"), lwr
    check_fog_and_colour(page, steps)
    page.keyboard.press('Escape')
    assert not page.evaluate('viewer.mapSettings().open')
    # View options' row opens it too
    page.evaluate("document.getElementById('viewButton').click()")
    page.locator('#skyOpen').click()
    assert page.evaluate('viewer.mapSettings().open')
    page.keyboard.press('Escape')
    assert not page.evaluate('viewer.mapSettings().open')


def check_cursor_floors(page):
    """A building's floors as the cursor's (the building cursor floors plan): the Buildings view's tick on a building of
    the project's, on for a new one (decision D2, since EXP-96); off, the cursor's floors over it are the map's; on, its
    own (each 2 under its box's bottom, the building's floor numbers), the panel says where they start and warns of
    none for the map's, the record says cursorFloors and the project keeps it; Ctrl+Z takes it off again. A floor
    starting under the one before it is warned of."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"
                         " && viewer.data.exporterVersion >= 20"):
        return skip('cursor-floors', 'needs a map (not a preview) with a tile grid and cursor floors', whole=True)
    page.evaluate('viewer.select(null)')
    x0, y0, z0 = (round(v) for v in page.evaluate('viewer.data.tileGrid.origin'))
    low = [x0 + 96 * 4, y0 + 96 * 4, z0, x0 + 96 * 6, y0 + 96 * 5, z0 + 160]         # floors 160 and 192 high
    high = low[:2] + [z0 + 160] + low[3:5] + [z0 + 352]
    page.evaluate('viewer.setVolumesShown(true)')
    ids = page.evaluate("boxes => viewer.addVolumes(boxes.map((box, floor) => ({ box, floor })), viewer.newBuilding())"
                        ".map(r => r.userData.source.id)", [low, high])
    page.evaluate('id => viewer.select(id)', ids[0])
    mine = "() => viewer.buildings().filter(b => !b.replaces)"
    # a new building has it on; taken off (one undo step), the map's floors are over it
    assert page.locator('#volumeCursorRow').is_visible() and page.locator('#volumeCursor').is_checked()
    assert page.evaluate(mine)[0].get('cursorFloors') is True
    page.locator('#volumeCursor').uncheck()
    assert 'cursorFloors' not in page.evaluate(mine)[0]
    over = "([x, y]) => viewer.cursorStoreys().filter(s => s.box[0] <= x && x <= s.box[3] && s.box[1] <= y && y <= s.box[4])" \
           ".map(s => [Math.round(s.box[2]), s.floor, s.building ?? null]).sort((a, b) => a[0] - b[0])"
    mid = [low[0] + 96, low[1] + 48]
    before = page.evaluate(over, mid)
    assert all(b[2] is None for b in before), before
    # ticked: one undo step; the floors over it its own, the panel's line says so
    page.locator('#volumeCursor').check()
    [rec] = page.evaluate(mine)
    assert rec['cursorFloors'] is True, rec
    assert page.evaluate(over, mid) == [[z0 - 2, 1, rec['name']], [z0 + 158, 2, rec['name']]], page.evaluate(over, mid)
    note = page.locator('#volumeNote').text_content()
    assert "are its own" in note and f'1 at {z0}, 2 at {z0 + 160}' in note, note
    assert 'mouse wheel would not stop' not in (page.locator('#volumeWarn').text_content() or '')
    assert page.evaluate('viewer.editState().buildings').__len__() >= 1
    assert any(b.get('cursorFloors') for b in page.evaluate('viewer.editState().buildings'))
    # a floor out of order is warned of: floor 2 dragged under floor 1's bottom
    page.evaluate('([id, b]) => viewer.putVolume(id, [b[0], b[1], b[2] - 200, b[3], b[4], b[5]])', [ids[1], high])
    page.evaluate('id => viewer.select(id)', ids[0])
    assert 'does not stop at it there' in page.locator('#volumeWarn').text_content()
    page.keyboard.press('Control+z')
    # saved as a prefab, the prefab's building has it; copied and pasted, the copy has it (prefab plan's clip)
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.setVolumesShown(false)')
    page.evaluate('viewer.setBoxesShown(true)')
    page.evaluate('id => viewer.select(id)', ids[0])
    doc = page.evaluate('viewer.prefabRecords()')
    assert [b.get('cursorFloors') for b in doc['buildings']] == [True], doc['buildings']
    page.keyboard.press('Control+c')
    page.keyboard.press('Control+v')
    view = page.locator('#viewport > canvas').first.bounding_box()
    page.mouse.click(view['x'] + view['width'] / 2, view['y'] + view['height'] / 2)
    page.wait_for_function('viewer.buildings().filter(b => !b.replaces).length === 2')
    copy = next(b for b in page.evaluate(mine) if b['name'].endswith(' copy'))
    assert copy.get('cursorFloors') is True, copy
    page.keyboard.press('Control+z')
    assert len(page.evaluate(mine)) == 1
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.setBoxesShown(false)')
    page.evaluate('viewer.setVolumesShown(true)')
    # Ctrl+Z takes the tick off, and once more puts it back on as the building was made
    page.keyboard.press('Control+z')
    assert 'cursorFloors' not in page.evaluate(mine)[0]
    assert page.evaluate(over, mid) == before
    page.keyboard.press('Control+z')
    assert page.evaluate(mine)[0].get('cursorFloors') is True
    page.keyboard.press('Control+z')
    assert page.evaluate(mine) == []
    page.evaluate('viewer.select(null)')
    page.evaluate('viewer.setVolumesShown(false)')


def check_floor_boxes(page):
    """View options' Floor boxes: off at first; on, the project's floor boxes are drawn in the normal view, where a
    click on a box's edge or the select box takes the whole building. It moves by whole tiles and turns by quarter
    turns with what is picked, is copied with a piece as a new building, and deleted; each one undo step."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"):
        return skip('floor-boxes', 'needs a map (not a preview) with a tile grid', whole=True)
    state = page.evaluate('viewer.projectState()')
    page.evaluate('viewer.select(null)')
    assert not page.evaluate('viewer.boxesShown()') and not page.locator('#boxesToggle').is_checked()
    x0, y0, z0 = (round(v) for v in page.evaluate('viewer.data.tileGrid.origin'))
    low = [x0 + 96 * 4, y0 + 96 * 4, z0, x0 + 96 * 6, y0 + 96 * 5, z0 + 192]         # two tiles by one
    high = low[:2] + [z0 + 192] + low[3:5] + [z0 + 384]
    ids = page.evaluate("boxes => viewer.addVolumes(boxes.map((box, floor) => ({ box, floor }))).map(r => r.userData.source.id)", [low, high])
    page.evaluate('viewer.select(null)')
    boxes = "() => viewer.buildings().filter(b => !b.replaces).map(b => b.floors.map(f => f.boxes))"
    assert page.evaluate(boxes) == [[[low], [high]]]
    shown = "ids => ids.map(id => viewer.volumeRoots.get(id).visible)"
    assert page.evaluate(shown, ids) == [False, False] and page.evaluate('([x, y]) => viewer.pickVolumeEdge(x, y)', [10, 10]) is None
    # on: drawn, and an edge picks the building whole
    # (the Normal view's switches stand under its row in the rail's Views list, shown while the pointer is over it)
    page.locator('#viewsButton').hover()
    assert page.locator('#normalFlyout').is_visible()
    page.locator('#boxesToggle').check()
    page.mouse.move(700, 500)
    assert page.locator('#normalFlyout').is_hidden()
    assert page.evaluate('viewer.boxesShown()') and page.evaluate(shown, ids) == [True, True]
    page.evaluate('id => viewer.frame(viewer.volumeRoots.get(id))', ids[0])
    settled(page, CAMERA)
    edge = page.evaluate('p => viewer.screenOf(p)', [(low[0] + low[3]) / 2, low[1], low[5]])
    assert page.evaluate('([x, y]) => viewer.pickVolumeEdge(x, y)', edge) in ids
    picked = "() => viewer.gizmo.selection().map(r => r.userData.source.id).sort()"
    page.evaluate('id => viewer.select(id)', ids[0])
    assert page.evaluate(picked) == sorted(ids)
    assert page.locator('#volumePanel').is_visible() and page.locator('#volumeHead').text_content().startswith('Building')
    assert page.locator('#volumeNew').is_hidden() and page.locator('#volumeFloor').is_disabled() and page.locator('#inspector').is_hidden()
    # moved by a tile, then turned a quarter turn about the picked box's middle: both boxes follow, and stay boxes
    at = page.evaluate('viewer.gizmo.pose().location')
    page.evaluate('at => viewer.gizmo.setPose(at, null)', [at[0] + 96, at[1], at[2]])
    shift = lambda b, dx: [b[0] + dx, b[1], b[2], b[3] + dx, b[4], b[5]]
    assert page.evaluate(boxes) == [[[shift(low, 96)], [shift(high, 96)]]]
    page.evaluate('viewer.gizmo.setPose(null, [0, 77, 0])')         # rounded to a quarter turn
    turned = page.evaluate(boxes)[0]
    for (b,), was in zip(turned, (low, high)):
        assert [b[3] - b[0], b[4] - b[1], b[5] - b[2]] == [was[4] - was[1], was[3] - was[0], 192], (b, was)
    assert (turned[0][0][0] + turned[0][0][3]) / 2 == (low[0] + low[3]) / 2 + 96
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate(boxes) == [[[low], [high]]]
    # the select box takes it, with the pieces
    page.evaluate('viewer.select(null)')
    page.evaluate('box => viewer.setPickBox(box)', [low[0] + 80, low[1] + 30, low[2] + 80, low[0] + 110, low[1] + 60, low[2] + 110])
    assert ids[0] in page.evaluate('viewer.pickHits()') and 'floor box' in page.locator('#boxBarText').inner_text()
    page.keyboard.press('Enter')
    assert set(ids) <= set(page.evaluate(picked))
    # Floor boxes alone now copy too (prefab builder W); with a piece they still make a new building.
    page.evaluate('id => viewer.select(id)', ids[0])
    page.keyboard.press('Control+c')
    assert '1 building' in page.locator('#dragHint').inner_text()
    assert page.evaluate('viewer.snapshot().entries.length === 0 && viewer.snapshot().volumes.length === 2')
    piece = page.evaluate("[...viewer.roots.keys()].find(k => { const r = viewer.roots.get(k), o = r.userData.source;"
                          " return r.visible && !o.hidden && !o.environment && !o.added && !o.stream && viewer.gizmo.linkedCount(k) === 0 && !viewer.recipeOf(k); })")
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [piece, ids[0]])
    assert len(page.evaluate(picked)) == 3
    page.keyboard.press('Control+c')
    assert '1 building' in page.locator('#dragHint').inner_text()
    page.keyboard.press('Control+v')
    view = page.locator('#viewport > canvas').first.bounding_box()
    page.mouse.click(view['x'] + view['width'] / 2, view['y'] + view['height'] / 2)
    page.wait_for_function('viewer.buildings().filter(b => !b.replaces).length === 2')
    copy = next(b for b in page.evaluate('viewer.buildings()') if b['name'].endswith(' copy'))
    assert [len(f['boxes']) for f in copy['floors']] == [1, 1]
    assert [b - a for a, b in zip(copy['floors'][0]['boxes'][0][:3], copy['floors'][0]['boxes'][0][3:])] == [192, 96, 192]
    assert len(page.evaluate(picked)) == 3 and len(page.evaluate('viewer.editState().added')) >= 1
    page.keyboard.press('Control+z')
    assert page.evaluate(boxes) == [[[low], [high]]]
    # deleted, and back
    page.evaluate('id => viewer.select(id)', ids[1])
    page.keyboard.press('Delete')
    assert page.evaluate(boxes) == [] and '1 building' in page.locator('#dragHint').inner_text()
    page.keyboard.press('Control+z')
    assert page.evaluate(boxes) == [[[low], [high]]]
    # the map's buildings that stay fixed (a van's) show in grey here too: picked by an edge or the select box, and
    # copied with a piece as a building of the project; they are never moved or deleted
    own = page.evaluate('viewer.ownBoxes()')
    if own:
        page.evaluate('viewer.select(null); viewer.frame()')
        settled(page, CAMERA)
        spot = None
        for o in own:
            b = o['box']
            x, y = page.evaluate('p => viewer.screenOf(p)', [(b[0] + b[3]) / 2, b[1], b[5]])
            if 320 < x < 1150 and 150 < y < 800 and page.evaluate('([x, y]) => viewer.ownEdge(x, y)', [x, y]) == o['building']:
                spot = (o, x, y); break
        assert spot, 'no box of the map has an edge in view'
        o, x, y = spot
        page.mouse.click(x, y)
        assert page.evaluate('viewer.ownSelected()') == [o['building']] and page.evaluate(picked) == []
        assert page.locator('#volumePanel').is_visible() and "The map's box" in page.locator('#volumeTitle').text_content()
        assert 'building of your own' in page.locator('#volumeNote').text_content()
        page.keyboard.press('Delete')
        assert 'not deleted' in page.locator('#dragHint').inner_text()
        page.keyboard.press('Escape')
        assert page.evaluate('viewer.ownSelected()') == [] and page.locator('#volumePanel').is_hidden()
        b = o['box']
        mid = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2]
        page.evaluate('box => viewer.setPickBox(box)', [mid[0] - 1, mid[1] - 1, mid[2] - 1, mid[0] + 1, mid[1] + 1, mid[2] + 1])
        assert any(i.startswith('own:') for i in page.evaluate('viewer.pickHits()')) and 'floor box' in page.locator('#boxBarText').inner_text()
        page.keyboard.press('Enter')
        assert o['building'] in page.evaluate('viewer.ownSelected()')
        # with a piece (Ctrl+click on the edge adds it), a copy has a building of the project with the same boxes
        page.evaluate('id => viewer.select(id)', piece)
        assert page.evaluate('viewer.ownSelected()') == []
        page.keyboard.press('v')        # (no gizmo in the way of the click)
        page.keyboard.down('Control'); page.mouse.click(x, y); page.keyboard.up('Control')
        page.keyboard.press('g')
        assert page.evaluate('viewer.ownSelected()') == [o['building']] and page.evaluate(picked) == [piece]
        page.keyboard.press('Control+c')
        assert '1 building' in page.locator('#dragHint').inner_text()
        page.keyboard.press('Control+v')
        view = page.locator('#viewport > canvas').first.bounding_box()
        page.mouse.click(view['x'] + view['width'] / 2, view['y'] + view['height'] / 2)
        page.wait_for_function('viewer.buildings().filter(b => !b.replaces).length === 2')
        copy = next(c for c in page.evaluate('viewer.buildings()') if c['name'].endswith(' copy'))
        assert sum(len(f['boxes']) for f in copy['floors']) == sum(1 for q in own if q['building'] == o['building']), copy
        assert copy['name'] == o['building'].split('.')[-1] + ' copy' and page.evaluate('viewer.ownBoxes()') == own
        page.keyboard.press('Control+z')
        assert page.evaluate(boxes) == [[[low], [high]]]
        page.evaluate('viewer.select(null)')
    # grouped with a piece, the building is a member: the piece takes it along, the boxes drawn or not
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [ids[0], piece])
    page.keyboard.press('Control+g')
    [g] = page.evaluate('viewer.editState().groups')
    building = page.evaluate('viewer.buildings().find(b => !b.replaces).id')
    assert {'building': building} in g['members'] and len(g['members']) == 2, g
    assert '1 piece and 1 building' in page.locator('#groupTitle').text_content()
    page.evaluate('viewer.setBoxesShown(false)')
    page.evaluate('id => viewer.select(id)', piece)
    assert set(ids) <= set(page.evaluate(picked)) and page.evaluate(shown, ids) == [False, False]
    at = page.evaluate('viewer.gizmo.pose().location')
    page.evaluate('at => viewer.gizmo.setPose(at, null)', [at[0] + 96, at[1], at[2]])
    assert page.evaluate(boxes) == [[[shift(low, 96)], [shift(high, 96)]]]
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate(boxes) == [[[low], [high]]] and page.evaluate('viewer.editState().groups') == []
    page.evaluate('viewer.setBoxesShown(true)')
    # a light is a member as a piece is: grouped with a piece, the piece takes it along with the lights hidden
    lamp = page.evaluate("[...viewer.lightRoots.values()].find(r => r.userData.source.role === 'static' && r.userData.source.layer === 'base'"
                         " && !r.userData.source.referencedBy?.length)?.userData.source")
    if lamp:
        page.locator('#viewsButton').hover()
        page.locator('#normalLights').check()
        page.mouse.move(700, 500)
        assert page.evaluate('viewer.normalLights() && viewer.lightsShown() && !viewer.lightsOn()')
        page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [lamp['id'], piece])
        if len(page.evaluate(picked)) == 2:      # (a light shown to be read only joins no selection)
            page.keyboard.press('Control+g')
            [g] = page.evaluate('viewer.editState().groups')
            assert {'package': lamp['sourcePackage'], 'level': 'base', 'actor': lamp['actor']} in g['members'], g
            assert '1 piece and 1 light' in page.locator('#groupTitle').text_content()
            page.evaluate('viewer.setNormalLights(false)')
            page.evaluate('id => viewer.select(id)', piece)
            assert lamp['id'] in page.evaluate(picked)
            # the Lights view: only lights are picked, and a grouped light moves on its own
            page.keyboard.press('Shift+L')
            assert page.evaluate('viewer.lightsOn()') and page.evaluate(picked) == []
            assert 'on' in page.locator('#editLights').get_attribute('class') and 'on' not in page.locator('#editNormal').get_attribute('class')
            assert page.evaluate(shown, ids) == [False, False]
            view = page.locator('#viewport > canvas').first.bounding_box()
            page.mouse.click(view['x'] + view['width'] / 2, view['y'] + view['height'] / 2)
            assert all(i.startswith('light') for i in page.evaluate(picked)), page.evaluate(picked)
            page.evaluate('id => viewer.select(id)', lamp['id'])
            assert page.evaluate(picked) == [lamp['id']]
            page.evaluate('box => viewer.setPickBox(box)', [lamp['location'][0] - 20, lamp['location'][1] - 20, lamp['location'][2] - 20,
                                                             lamp['location'][0] + 20, lamp['location'][1] + 20, lamp['location'][2] + 20])
            assert page.evaluate('viewer.pickHits()') == [lamp['id']]
            page.keyboard.press('Escape')
            # a piece picked from a list leaves the view; Shift+N is the normal view's key
            page.evaluate('id => viewer.select(id)', piece)
            assert not page.evaluate('viewer.lightsOn()') and 'on' in page.locator('#editNormal').get_attribute('class')
            page.keyboard.press('Shift+L'); page.keyboard.press('Shift+B')
            assert page.evaluate('viewer.volumesOn() && !viewer.lightsOn() && !viewer.lightsShown()')
            page.keyboard.press('Shift+N')
            assert not page.evaluate('viewer.volumesOn() || viewer.lightsOn()')
            page.keyboard.press('Control+z')
            assert page.evaluate('viewer.editState().groups') == []
        page.evaluate('viewer.setNormalLights(false)')
        page.evaluate('viewer.select(null)')
    # off: the boxes go from the view and from the selection, the piece stays
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [piece, ids[0]])
    page.locator('#viewsButton').hover()
    page.locator('#boxesToggle').uncheck()
    page.mouse.move(700, 500)
    assert page.evaluate(shown, ids) == [False, False] and page.evaluate(picked) == [piece]
    # the Buildings view still has each box on its own
    page.evaluate('viewer.setVolumesShown(true)')
    page.evaluate('id => viewer.select(id)', ids[0])
    assert page.evaluate(picked) == [ids[0]] and page.locator('#volumeHead').text_content().startswith('Buildings view')
    assert page.locator('#volumeNew').is_visible() and not page.locator('#volumeFloor').is_disabled()
    page.evaluate('viewer.setVolumesShown(false)')
    page.keyboard.press('Control+z')
    assert page.evaluate(boxes) == [] and page.evaluate('viewer.projectState()') == state


def check_align(page):
    """Align: with two pieces selected, the other lines up with the target (by default the last one picked) along the
    ticked game axes (here X and Z, by low edges), keeping its Y; one undo step. Choosing the other as the target
    moves the last one picked instead. A group lines up as one."""
    original = page.evaluate('viewer.gizmo.active')
    free = page.evaluate("""() => {
      const count = new Map();
      for (const r of viewer.roots.values()) count.set(r.userData.source.actor, (count.get(r.userData.source.actor) || 0) + 1);
      return [...viewer.roots.keys()].filter(k => { const r = viewer.roots.get(k), o = r.userData.source;
        return r.visible && !o.hidden && !o.environment && !o.added && count.get(o.actor) === 1 && viewer.gizmo.linkedCount(k) === 0
          && !viewer.recipeOf(k); }).slice(0, 40);
    }""")
    boxes = """async ids => { const T = await import('/vendor/three/three.module.js');
      return ids.map(id => { const x = new T.Box3().expandByObject(viewer.roots.get(id)); return [...x.min.toArray(), ...x.max.toArray()]; }); }"""
    near = lambda p, q: all(abs(x - y) < 0.01 for x, y in zip(p, q))
    # Two pieces whose low edges differ on game X and Z (pieces in a row may already line up), and a third.
    found = page.evaluate(boxes, free)
    a = free[0]
    b = next(k for k, x in zip(free[1:], found[1:]) if abs(x[0] - found[0][0]) > 1 and abs(x[1] - found[0][1]) > 1)
    c = next(k for k in free[1:] if k != b)
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [a, b])
    assert page.locator('#alignBox').is_visible()
    target = page.locator('#alignTarget')
    assert target.input_value() == b and '(last picked)' in target.locator('option:checked').inner_text()
    assert target.locator('option').count() == 2
    for axis, on in (('X', True), ('Y', False), ('Z', True)): page.locator(f'#align{axis}').set_checked(on)
    page.locator('#alignBy').select_option('min')
    (ba, bb) = page.evaluate(boxes, [a, b])
    page.locator('#alignGo').click()
    (na, nb) = page.evaluate(boxes, [a, b])
    # Viewer axes: x is game X, y is up (game Z), z is game Y. Low edges meet on X and Z; Y stays.
    assert not near(na, ba) and abs(na[0] - nb[0]) < 0.01 and abs(na[1] - nb[1]) < 0.01, (na, nb)
    assert abs(na[2] - ba[2]) < 0.01 and nb == bb, (ba, na, bb, nb)
    page.keyboard.press('Control+z')
    assert near(page.evaluate(boxes, [a])[0], ba)
    # The first one picked as the target: now b moves to a, and a stays.
    target.select_option(a)
    assert target.input_value() == a and page.evaluate('viewer.gizmo.active') == b
    page.locator('#alignGo').click()
    (na, nb) = page.evaluate(boxes, [a, b])
    assert near(na, ba) and not near(nb, bb) and abs(na[0] - nb[0]) < 0.01 and abs(na[1] - nb[1]) < 0.01 and abs(nb[2] - bb[2]) < 0.01, (ba, na, bb, nb)
    page.keyboard.press('Control+z')
    assert near(page.evaluate(boxes, [b])[0], bb)
    # A group (a and c) lines up as one: both move by the same step. A new selection starts again from the
    # last one picked.
    page.evaluate('([a, c]) => { viewer.select(a); viewer.select(c, true); }', [a, c])
    page.keyboard.press('Control+g')
    page.evaluate('([a, b]) => { viewer.select(a); viewer.select(b, true); }', [a, b])
    assert target.input_value() == b and target.locator('option').count() == 2, target.input_value()
    assert target.locator('option').first.inner_text().startswith('The group of')
    for axis, on in (('X', True), ('Y', True), ('Z', False)): page.locator(f'#align{axis}').set_checked(on)
    page.locator('#alignBy').select_option('centre')
    assert 'line up with the target' in page.locator('#alignText').inner_text()
    (ba, bc) = page.evaluate(boxes, [a, c])
    page.locator('#alignGo').click()
    (na, nc, nb) = page.evaluate(boxes, [a, c, b])
    step = [na[i] - ba[i] for i in (0, 2)]
    assert all(abs(step[k] - (nc[i] - bc[i])) < 0.01 for k, i in enumerate((0, 2))), (step, bc, nc)
    assert abs(na[1] - ba[1]) < 0.01 and abs(nc[1] - bc[1]) < 0.01
    # The group's box centre meets b's on X and Y.
    for i in (0, 2):
        assert abs((min(na[i], nc[i]) + max(na[i + 3], nc[i + 3])) / 2 - (nb[i] + nb[i + 3]) / 2) < 0.01, (na, nc, nb)
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.editState().groups') == []
    page.evaluate('id => viewer.select(id)', original)


def check_library(page, is_bar):
    """The piece list (P): one entry per distinct piece with a drawn thumbnail; filters and sorting; choosing an entry
    places a copy where the view is clicked (Shift+click keeps placing), as one undo step each."""
    count, original = page.evaluate('viewer.roots.size'), page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    assert page.locator('#library').is_visible() and 'on' in page.locator('#editAdd').get_attribute('class')
    entries = page.evaluate('viewer.pieces.entries().length')
    lights = page.evaluate('viewer.pieces.entries().filter(e => e.light).length')
    visible = page.evaluate('[...viewer.roots.values()].filter(r => !r.userData.source.hidden && !r.userData.source.environment).length')
    zones = page.evaluate('viewer.pieces.entries().filter(e => e.zone).length')   # the Landing zones kind's one entry
    assert zones == 1, zones
    # the Spawn points kind's Pod and Meld point, where the spawn family builds: recipes, not pieces
    spawns = page.evaluate('viewer.pieces.entries().filter(e => e.spawnAdd).length')
    pieces = entries - lights - zones - spawns
    assert 0 < pieces <= visible, (entries, lights, zones, spawns, visible)
    assert page.locator('.libitem').count() == entries and f'{pieces} pieces' in page.locator('#libFoot').inner_text(), (
        page.locator('.libitem').count(), entries, lights, zones, spawns, page.locator('#libFoot').inner_text())
    if lights: assert f'and {lights} light' in page.locator('#libFoot').inner_text()
    # Entries are distinct: no two alike in every part.
    assert page.evaluate('new Set(viewer.pieces.entries().map(e => e.key)).size') == entries
    # Thumbnails are drawn a few per frame; each holds a picture, not just the background.
    page.wait_for_function("[...document.querySelectorAll('.libitem canvas')].every(c => c.dataset.drawn)", timeout=60000)
    assert page.evaluate("""() => [...document.querySelectorAll('.libitem canvas')].slice(0, 20).some(c => {
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, colours = new Set();
      for (let i = 0; i < d.length; i += 16) colours.add(d[i] << 16 | d[i + 1] << 8 | d[i + 2]);
      return colours.size > 20;
    })""")
    # A kind shows its own entries only; its option carries their number.
    option = page.locator('#libKind option').nth(1)
    kind, label = option.get_attribute('value'), option.inner_text()
    page.locator('#libKind').select_option(kind)
    assert page.locator('.libitem').count() == int(re.search(r'\((\d+)\)', label).group(1))
    # Build milestones stay on the affected rows, and both scopes share the same category labels.
    later = page.evaluate('viewer.pieces.entries().filter(e => e.milestone > 1).length')
    page.locator('#libKind').select_option('all')
    assert page.locator('.libitem .tag.later').count() == later
    options = page.locator('#libKind option').all_inner_texts()
    assert not any(' · M' in t or 'first build' in t for t in options), options
    assert page.evaluate("viewer.pieces.entries().filter(e => ['Fracturing', 'Physics'].includes(e.kind) && e.milestone > 1).length") == 0
    # Largest first: each entry's size is no bigger than the one above it.
    page.locator('#libSort').select_option('size')
    extents = page.evaluate("""() => [...document.querySelectorAll('.libitem')].map(b =>
      viewer.pieces.entries().find(e => e.id === b.dataset.id).extent)""")
    assert all(a >= b for a, b in zip(extents, extents[1:]))
    page.locator('#libSort').select_option('name')
    # Filtering by name narrows the list to that piece.
    name = page.evaluate('viewer.pieces.entries()[0].name')
    page.locator('#libFilter').fill(name)
    assert 0 < page.locator('.libitem').count() < entries
    page.locator('#libFilter').fill('')
    # The Lights kind (export 18): Point Light and Spot Light, each with a drawn icon; choosing one places a new light.
    if lights:
        page.locator('#libKind').select_option('lights')
        assert sorted(page.locator('.libitem strong').all_inner_texts()) == sorted(
            page.evaluate("viewer.pieces.entries().filter(e => e.light).map(e => e.name)")), page.locator('.libitem strong').all_inner_texts()
        assert page.evaluate("[...document.querySelectorAll('.libitem canvas')].every(c => c.dataset.drawn)")
        n = page.evaluate('viewer.lightRoots.size')
        first = page.evaluate("viewer.pieces.entries().find(e => e.light).id")
        page.locator(f'.libitem[data-id="{first}"]').click()
        assert page.evaluate('viewer.placing()?.fromList') and page.evaluate('viewer.lightsShown()')
        box = page.locator('#viewport > canvas').bounding_box()
        page.mouse.move(box['x'] + box['width'] * 0.6, box['y'] + box['height'] / 2)
        page.wait_for_function('viewer.placing()?.ghost.visible')
        page.mouse.click(box['x'] + box['width'] * 0.6, box['y'] + box['height'] / 2)
        page.wait_for_function('n => viewer.lightRoots.size === n + 1', arg=n)
        assert page.locator('#lightBox').is_visible() and page.evaluate('viewer.changes().lights') == 1
        page.keyboard.press('Control+z')
        assert page.evaluate('viewer.lightRoots.size') == n and page.evaluate('viewer.changes().total') == 0
        page.keyboard.press('Shift+L')
        page.locator('#libKind').select_option('all')
    # Choose the entry with the most parts (a car, a van on the Bar) and place it with a click in the view.
    key, parts = page.evaluate("""() => { const e = viewer.pieces.entries().reduce((a, b) => b.sources.length > a.sources.length ? b : a);
      return [e.id, e.sources.length]; }""")
    if is_bar and page.evaluate('viewer.data.exporterVersion >= 12'): assert parts >= 2, parts
    page.locator(f'.libitem[data-id="{key}"]').click()
    assert page.locator(f'.libitem[data-id="{key}"]').get_attribute('class').split().count('on') == 1
    assert 'Placing' in page.locator('#dragHint').inner_text()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.6, box['y'] + box['height'] / 2
    page.mouse.move(cx, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + parts)
    page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")
    assert page.evaluate('viewer.placing()') is None
    assert page.evaluate('viewer.gizmo.selection().length') == parts
    assert page.evaluate('viewer.gizmo.selection().every(r => r.userData.source.added)')
    assert page.evaluate('viewer.changes().added') == parts
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    # Shift+click keeps placing until Escape; each placement is its own undo step.
    page.locator(f'.libitem[data-id="{key}"]').click()
    page.mouse.move(cx, cy)
    page.keyboard.down('Shift')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n', arg=count + parts)
    page.mouse.click(cx + 60, cy)
    page.keyboard.up('Shift')
    page.wait_for_function('n => viewer.roots.size === n', arg=count + 2 * parts)
    assert page.evaluate('Boolean(viewer.placing())')
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.placing()') is None and page.locator('#dragHint').is_hidden()
    assert page.locator('.libitem.on').count() == 0
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    page.keyboard.press('p')
    assert page.locator('#library').is_hidden() and 'on' not in page.locator('#editAdd').get_attribute('class').split()
    page.evaluate('id => viewer.select(id)', original)


def check_library_all(browser, url):
    """The Add panel's All maps (library.js): the pieces of every map of the game. Only against a test server (its
    --projects and --builds scratch folders, and XCOM_MAP_WORKSHOP_SETTINGS a scratch settings file, beside which the
    favourites are written) whose cache has the library scanned (`viewer.py library scan`; without it the panel
    offers the scan, which is then run here). The list drawn only where it shows, its filters, a favourite kept by the
    server, a piece of another map placed, saved, reopened and built without baking."""
    errors = []
    page = open_viewer(browser, url, errors)
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): return skip('library-all', 'needs a map, not a preview', page, whole=True)
    count = page.evaluate('viewer.roots.size')
    page.evaluate("localStorage.removeItem('workshop.libraryScope'); localStorage.removeItem('workshop.libraryView')")
    page.keyboard.press('p')
    # the panel opens on This map, as before; All maps is the other scope
    assert page.locator('#libMap').is_visible() and page.locator('#libAll').is_hidden() and value(page, 'libScope') == 'map'
    mine = page.locator('.libitem').count()
    assert mine == page.evaluate('viewer.pieces.entries().length')
    choose(page, 'libScope', 'all')
    assert page.locator('#libAll').is_visible() and page.locator('#libMap').is_hidden()
    # first use offers the scan and follows it
    page.wait_for_function("viewer.library.ready() || !document.getElementById('libScan').hidden", timeout=30000)
    if not page.evaluate('viewer.library.ready()'):
        assert 'about half a minute' in page.locator('#libScan').inner_text()
        page.locator('#libScan button').click()
        page.wait_for_function("document.getElementById('libScan').textContent.includes('Reading the game')")
        page.wait_for_function('viewer.library.ready()', timeout=300000)
    assert page.locator('#libScan').is_hidden()
    kinds = "id => [...document.getElementById(id).options].map(o => [o.value, o.textContent.split(' (')[0]])"
    # (All maps lists the base maps' effects and sounds too: their kinds after the pieces')
    effect_kinds = "id => [...document.getElementById(id).options].filter(o => /^(effects|sounds|fx:|snd:)/.test(o.value)).length"
    assert page.evaluate(kinds, 'libAllKind')[:len(page.evaluate(kinds, 'libKind'))] == page.evaluate(kinds, 'libKind')
    assert page.evaluate(effect_kinds, 'libAllKind') > 2 and page.evaluate(effect_kinds, 'libKind') == 0
    for kind in ('Invisible', 'lights'):
        page.locator('#libAllKind').select_option(kind)
        assert page.locator('#libAllList .libitem strong').all_inner_texts() == page.evaluate(
            "kind => viewer.pieces.entries().filter(e => kind === 'lights' ? e.light : e.cover).map(e => e.name).sort()", kind)
    if page.evaluate('viewer.library.entries().some(e => e.floor && e.placeable)'):
        page.locator('#libAllKind').select_option('floors')
        assert page.evaluate('viewer.library.shown().length > 0 && viewer.library.shown().every(e => e.floor)')
    page.locator('#libAllKind').select_option('all')
    total, placeable = page.evaluate('[viewer.library.entries().length, viewer.library.entries().filter(e => e.placeable).length]')
    assert 0 < placeable < total, (placeable, total)
    # only what can be placed, by default; and only the rows in view are in the page
    assert page.evaluate('viewer.library.shown().filter(e => e.library).length') == placeable and page.locator('#libAllPlaceable').is_checked()
    assert 0 < page.locator('#libAllList .libitem').count() < 40
    assert f'{placeable:,} of {total:,} pieces' in page.locator('#libAllFoot').inner_text()
    page.locator('#libAllPlaceable').uncheck()
    assert page.evaluate('viewer.library.shown().filter(e => e.library).length') == total
    # what the library only holds back (hidden, linked, a kind not switched on, waiting for its game test) is placed
    # since 14 November 2026, and since 16 November 2026 nothing says it is untried; what can't be brought stays off
    soft = "['hidden', 'assembly', 'family', 'check']"
    later = page.evaluate("viewer.library.shown().findIndex(e => e.library && !e.effect && !e.placeable && !%s.includes(e.blocked))" % soft)
    if later >= 0:
        page.evaluate("i => { document.getElementById('libAllList').scrollTop = i * 61; }", later)
        page.wait_for_selector('#libAllList .libitem.off .tag.later')
        # a piece that can't be placed yet says why, and is not placed
        page.locator('#libAllList .libitem.off').first.click()
        assert "can't be placed yet" in page.locator('#dragHint').inner_text() and page.evaluate('viewer.placing()') is None
    untried = page.evaluate("viewer.library.shown().findIndex(e => e.library && !e.effect && !e.placeable && %s.includes(e.blocked))" % soft)
    if untried >= 0:
        page.evaluate("i => { document.getElementById('libAllList').scrollTop = i * 61; }", untried)
        row = page.locator(f'#libAllList .libitem:not(.off)[data-key="{page.evaluate("i => viewer.library.shown()[i].key", untried)}"]')
        row.wait_for()
        assert not page.locator('#libAllList .tag', has_text='Untried').count()
        row.click()
        assert 'untried' not in page.locator('#dragHint').inner_text().lower(), page.locator('#dragHint').inner_text()
        page.wait_for_function('viewer.placing()', timeout=60000)      # (read from the game the first time)
        page.keyboard.press('Escape')
        assert page.evaluate('viewer.placing()') is None
    page.locator('#libAllPlaceable').check()
    # the kinds and the maps carry their counts; a map narrows the list to the pieces placed in it
    home = page.evaluate("[...document.getElementById('libAllHome').options].find(o => o.textContent.startsWith('URB_PoliceStation ')).value")
    page.locator('#libAllHome').select_option(home)
    station = page.evaluate('viewer.library.shown().length')
    assert 0 < station < placeable
    assert page.evaluate("h => viewer.library.shown().every(e => e.placed.in.includes(Number(h)))", home)
    # Not in this map leaves out what the open map has
    page.locator('#libAllElsewhere').check()
    assert page.evaluate('viewer.library.shown().length') <= station and page.evaluate('viewer.library.shown().every(e => !e.here)')
    page.locator('#libAllElsewhere').uncheck()
    # largest first
    page.locator('#libAllSort').select_option('size')
    extents = page.evaluate('viewer.library.shown().slice(0, 50).map(e => e.extent)')
    assert all(a >= b for a, b in zip(extents, extents[1:]))
    page.locator('#libAllSort').select_option('name')
    # a search by name finds a piece: the Police Station's lamp post (EXP-37's)
    page.locator('#libAllFilter').fill('parklamppost_b')
    found = page.evaluate('viewer.library.shown().map(e => [e.key, e.source.package, e.source.actor])')
    assert len(found) == 1 and found[0][1] == 'URB_PoliceStation', found
    key = found[0][0]
    row = page.locator(f'#libAllList .libitem[data-key="{key}"]')
    assert 'URB_PoliceStation' in row.inner_text()
    # its picture: read from the server, or drawn from the piece and then kept there
    page.wait_for_function("k => document.querySelector(`#libAllList .libitem[data-key=\"${k}\"] canvas`)?.dataset.drawn", arg=key, timeout=60000)
    assert page.evaluate("""k => { const c = document.querySelector(`#libAllList .libitem[data-key="${k}"] canvas`);
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, colours = new Set();
      for (let i = 0; i < d.length; i += 16) colours.add(d[i] << 16 | d[i + 1] << 8 | d[i + 2]);
      return colours.size > 5; }""", key)
    page.wait_for_function("k => fetch('/library.json?index=1').then(r => r.json()).then(a => a.thumbs.includes(k))", arg=key, timeout=20000)
    # a favourite is kept by the server (a file beside the settings), and the Favourites filter shows it alone
    before = page.evaluate("fetch('/library/state.json').then(r => r.json())")
    was = any(f['key'] == key for f in before['favourites'])
    if was:
        row.locator('.star').click()
        page.wait_for_function("k => !viewer.library.state().favourites.some(f => f.key === k)", arg=key)
    row.locator('.star').click()
    page.wait_for_function("k => viewer.library.state().favourites.some(f => f.key === k)", arg=key)
    kept = page.evaluate("fetch('/library/state.json').then(r => r.json())")
    assert any(f['key'] == key and f['name'] == 'ParkLampPost_B' for f in kept['favourites']), kept
    page.locator('#libAllFilter').fill('')
    page.locator('#libAllHome').select_option('all')
    page.locator('#libAllFavourites').check()
    assert sorted(page.evaluate('viewer.library.shown().map(e => e.key)')) == sorted(f['key'] for f in kept['favourites']), kept
    assert 'on' in page.locator(f'#libAllList .libitem[data-key="{key}"] .star').get_attribute('class').split()
    # placing it: the piece is read from its home map, a preview follows the cursor, a click puts it down
    page.locator(f'#libAllList .libitem[data-key="{key}"]').click()
    page.wait_for_function('viewer.placing()?.fromList', timeout=60000)
    assert 'on' in page.locator(f'#libAllList .libitem[data-key="{key}"]').get_attribute('class').split()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.6, box['y'] + box['height'] / 2
    page.mouse.move(cx, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")
    added = page.evaluate('viewer.editState().added')
    assert len(added) == 1 and added[0]['from'] == dict(package='URB_PoliceStation', level='base', actor='TheWorld.PersistentLevel.' + found[0][2]), added
    assert added[0]['actor'].endswith(found[0][2] + '_copy1') and len(added[0]['components']) == 1
    # the piece panel says where it is from
    assert 'From URB_PoliceStation' in page.locator('#details .chips').inner_text()
    # it heads the recently used pieces
    page.wait_for_function("k => viewer.library.state().recent[0]?.key === k", arg=key)
    # a copy of the copy is of the same piece of the same map; undo and redo as any piece
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count
    page.keyboard.press('Control+y')
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.keyboard.press('p')
    assert page.locator('#library').is_hidden() and page.locator('.libitem').count() == mine
    # saved and reopened: the piece is read from its home map again, and nothing is carried
    state = page.evaluate('viewer.projectState()')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Library smoke {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    assert page.evaluate('viewer.projectState()') == state and page.evaluate('viewer.roots.size') == count + 1
    carried = page.evaluate('viewer.project().carried')
    assert not any(carried.values()), carried
    assert page.evaluate("[...viewer.roots.values()].filter(r => r.userData.source.foreign).length") == 1
    # the panel reopens on All maps (the scope is remembered), with the piece first under Recently used
    page.keyboard.press('p')
    assert page.locator('#libAll').is_visible()
    page.wait_for_function('viewer.library.ready() && viewer.library.state()')
    page.locator('#libAllSort').select_option('recent')
    assert page.evaluate('viewer.library.shown()[0].key') == key
    page.locator('#libAllSort').select_option('name')
    page.keyboard.press('p')
    # Build: the panel says what baking does for a piece of another map; the lighting can be baked or not
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    assert page.locator('#buildBake').is_enabled() and not page.locator('#buildBake').is_checked()
    assert '1 piece from other maps: baked, it is lit for where it stands' in page.locator('#buildBakeNote').inner_text()
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=300000)
    assert page.locator('#buildTitle').inner_text().startswith(f'Built Library smoke {RUN}'), page.locator('#buildModal').inner_text()
    steps = page.locator('#buildSteps').inner_text()
    assert 'Bring the pieces from other maps' in steps and '1 piece from URB_PoliceStation' in steps, steps
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built' and build['package']['quick'], build      # (a baked one: test_transplant FreshLight)
    assert build['package']['foreignPieces'] == 1 and [d['map'] for d in build['package']['donors']] == ['URB_PoliceStation'], build['package']
    page.locator('#buildClose').click()
    assert not errors, errors
    page.close()


def check_library_effects(browser, url):
    """Effects and sounds of other maps in the Add panel's All maps (effects and sounds plan, stage FX4), on URB_Bar:
    their kinds, a row's picture and words, a landing's listed and not placed; an effect (moths, which Bar lacks) and a
    sound with a shared cue (a hyperwave beacon) placed, their panel and the Wave preview through the library's route;
    saved, reopened (read from their maps again) and built without baking. Only against a test server as
    check_library_all's (its --projects and --builds scratch folders, its cache's library scanned at index 9)."""
    errors = []
    page = open_viewer(browser, url, errors)
    if not page.evaluate("viewer.data.scope === 'map' && viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')"):
        return skip('library-effects', 'URB_Bar only', page, whole=True)
    page.evaluate("localStorage.removeItem('workshop.libraryView')")
    page.keyboard.press('p')
    choose(page, 'libScope', 'all')
    page.wait_for_function('viewer.library.ready()', timeout=60000)
    fx = page.evaluate("viewer.library.entries().filter(e => e.effect).length")
    assert fx > 1000, fx
    # placeable since EXP-69 (the compiler's foreign gate lists effects and sounds)
    page.locator('#libAllKind').select_option('effects')
    assert page.evaluate("viewer.library.shown().length > 0 && viewer.library.shown().every(e => e.effect === 'effect' && e.placeable)")
    # (what the editor can't bring, a landing's, shows with Placeable only off)
    page.locator('#libAllPlaceable').uncheck()
    # the kinds: Effects, Sounds and each of theirs, with counts
    page.locator('#libAllKind').select_option('effects')
    assert page.evaluate("viewer.library.shown().length > 0 && viewer.library.shown().every(e => e.effect === 'effect')")
    page.locator('#libAllKind').select_option('snd:Alien')
    assert page.evaluate("viewer.library.shown().every(e => e.effect === 'sound' && e.group === 'Alien')")
    page.locator('#libAllKind').select_option('all')
    # a landing's actor is listed and can't be placed, with the reason
    page.locator('#libAllFilter').fill('P_Skyranger_Idle')
    page.wait_for_selector('#libAllList .libitem.off .tag.later')
    assert page.locator('#libAllList .libitem.off .tag.later').first.inner_text() == 'Not brought'
    page.locator('#libAllList .libitem.off').first.click()
    assert "can't be placed" in page.locator('#dragHint').inner_text() and 'landing' in page.locator('#dragHint').inner_text()
    assert page.evaluate('viewer.placing()') is None
    count = page.evaluate('viewer.effectRoots.size')

    def place(words, at):
        page.locator('#libAllFilter').fill(words)
        key = page.evaluate("w => viewer.library.shown().find(e => e.effect && e.name === w && e.source.package !== 'URB_Bar')?.key", words)
        assert key, words
        row = page.locator(f'#libAllList .libitem[data-key="{key}"]')
        row.wait_for()
        entry = page.evaluate("k => viewer.library.entry(k)", key)
        # its picture is the Effects view's marker, drawn at once; its lines say what it is and where it is from
        page.wait_for_function("k => document.querySelector(`#libAllList .libitem[data-key=\"${k}\"] canvas`)?.dataset.drawn", arg=key)
        text = row.inner_text()
        assert ('Effect: ' if entry['effect'] == 'effect' else 'Sound: ') + entry['group'] in text, text
        row.click()
        page.wait_for_function('viewer.placing()', timeout=60000)
        box = page.locator('#viewport > canvas').bounding_box()
        x, y = box['x'] + box['width'] * at[0], box['y'] + box['height'] * at[1]
        page.mouse.move(x, y)
        page.wait_for_function('viewer.placing()?.ghost.visible')
        # an effect's likeness comes with the cursor (stage FXV3)
        if entry['effect'] == 'effect': page.wait_for_function('viewer.ghostLikenesses() >= 1')
        page.mouse.click(x, y)
        page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")
        return entry

    # stage FXV3: an effect's row shows its likeness, kept by the server; the pointer on a row plays it in the pane
    page.locator('#libAllPlaceable').check()
    page.locator('#libAllKind').select_option('effects')
    page.locator('#libAllFilter').fill('Fire')
    page.wait_for_function("[...document.querySelectorAll('#libAllList .libitem canvas')].some(c => c.dataset.likeness)", timeout=120000)
    # The pane hides on its row's mouseleave. The list is drawn again (its rows put back) whenever its size changes,
    # which the busy row under it does while the pictures in view are read and drawn; the one time the wait for the
    # pane to hide timed out (1 of 76 hovers, five pages at once), the list had been drawn again during that hover. So
    # the pointer goes on a row once the list has settled: every picture in view drawn, none being read.
    page.wait_for_function("[...document.querySelectorAll('#libAllList .libitem canvas')].every(c => c.dataset.drawn)"
                           " && document.querySelector('#libAll .busyrow').hidden", timeout=120000)
    key = page.evaluate("document.querySelector('#libAllList .libitem canvas[data-likeness]').closest('.libitem').dataset.key")
    row = page.locator(f'#libAllList .libitem[data-key="{key}"]')
    row.hover()
    page.wait_for_function('!viewer.likenessPane().hidden && viewer.likenessPane().shown', timeout=60000)
    assert page.locator('#likenessPane').is_visible()
    page.mouse.move(900, 500)
    page.wait_for_function('viewer.likenessPane().hidden')
    # (sounds keep their marker: no likeness, no pane)
    page.locator('#libAllKind').select_option('sounds')
    page.wait_for_function("document.querySelector('#libAllList .libitem canvas')?.dataset.drawn")
    assert page.evaluate("![...document.querySelectorAll('#libAllList .libitem canvas')].some(c => c.dataset.likeness)")
    first = page.locator('#libAllList .libitem').first
    first.hover()
    # (a row whose likeness the pane is to show takes the row's tip at once, on the pointer's arrival, the pane coming
    # after: a sound's row has taken none)
    assert first.evaluate('row => row.dataset.tip === undefined'), first.evaluate('row => [row.dataset.tip, row.title]')
    assert page.evaluate('viewer.likenessPane().hidden')
    page.mouse.move(900, 500)
    page.locator('#libAllPlaceable').uncheck()
    page.locator('#libAllKind').select_option('all')
    page.locator('#libAllFilter').fill('')

    moths = place('P_Moths_Wandering', (0.45, 0.5))
    beacon = place('HyperWaveBeacon', (0.6, 0.55))
    assert page.evaluate('viewer.effectRoots.size') == count + 2
    added = page.evaluate('viewer.editState().added')
    assert sorted((a['kind'], a['from']['package']) for a in added) == [('effect', moths['source']['package']), ('sound', beacon['source']['package'])], added
    assert all(not a.get('components') for a in added)
    # selected once placed, which shows the Effects view (as a paste of the map's own does)
    assert page.evaluate('viewer.effectsOn()')
    page.keyboard.press('p')
    sound = page.evaluate("[...viewer.effectRoots.values()].find(r => r.userData.source.added && r.userData.source.kind === 'sound').userData.source.id")
    page.evaluate(f'viewer.pickEffect({sound!r})')
    info = page.locator('#effectPanel').inner_text()
    assert f"of {beacon['source']['package']}" in info and 'the Build brings it into this map' in info, info
    # the Wave preview plays the beacon's wave from its own map (/library/wave.ogg)
    wave = page.locator('#effectWaves button[data-wave]').first
    assert wave.is_enabled(), page.locator('#effectWaves').inner_html()
    wave.click()
    page.wait_for_function("viewer.wave() && ['playing', 'failed'].includes(viewer.wave().state)", timeout=15000)
    assert page.evaluate('viewer.wave().state') == 'playing', page.evaluate('viewer.wave()')
    page.evaluate('viewer.stopWave()')
    # a copy of the copy is another copy of the same map's sound
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('Control+c')
    assert 'Copied 1 sound' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.6
    page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.effectRoots.size === n + 3', arg=count)
    copy = page.evaluate('viewer.gizmo.active')
    assert page.evaluate('id => viewer.effectRoots.get(id).userData.source.added.from.package', copy) == beacon['source']['package']
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.effectRoots.size') == count + 2
    page.evaluate('viewer.pickEffect(null)')
    # saved and reopened: each read from its map again, nothing carried
    state = page.evaluate('viewer.projectState()')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Library effects smoke {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    assert page.evaluate('viewer.projectState()') == state
    carried = page.evaluate('viewer.project().carried')
    assert not any(carried.values()), carried
    assert page.evaluate("[...viewer.effectRoots.values()].filter(r => r.userData.source.added?.base?.foreign).length") == 2
    # Build: the step says what comes from which map
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=300000)
    assert page.locator('#buildTitle').inner_text().startswith(f'Built Library effects smoke {RUN}'), page.locator('#buildModal').inner_text()
    steps = page.locator('#buildSteps').inner_text()
    assert 'Bring the pieces from other maps' in steps and '2 effects and sounds from' in steps, steps
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built' and build['package']['foreignEffects'] == 2, build['package']
    assert sorted(d['map'] for d in build['package']['donors']) == sorted([moths['source']['package'], beacon['source']['package']])
    page.locator('#buildClose').click()
    assert not errors, errors
    page.close()


def check_effect_values(browser, url):
    """An effect's and a sound's values (effects and sounds plan, stage FX5), on URB_Bar against a test server whose
    page edits them (serve --family effect-values --family sound-values, its --projects and --builds scratch
    folders): Emitter_38's starting state, a parameter it saves (a scalar on a vector distribution), its colour and
    one it doesn't save; its size handle dragged (one undo step); a simple sound's radius handle, volume and pitch;
    a copy keeps the values it was copied with; a shared cue's sound shows no values; saved, reopened, built without
    baking, the Build's values read in its report."""
    errors = []
    page = open_viewer(browser, url, errors)
    if not page.evaluate("viewer.data.scope === 'map' && viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')"):
        return skip('effect-values', 'URB_Bar only', page, whole=True)
    if not page.evaluate("viewer.families()?.families?.['effect-values']?.builds"):
        return skip('effect-values', 'the server doesn\'t build effect values (families.json)', page, whole=True)
    page.evaluate('viewer.setEffectsShown(true)')
    root = lambda actor: page.evaluate("a => [...viewer.effectRoots.values()].find(r => r.userData.source.actor.endsWith('.' + a)).userData.source.id", actor)
    fx = root('Emitter_38')
    page.evaluate(f'viewer.pickEffect({fx!r})')
    page.wait_for_selector('#effectValues:not([hidden])')
    row = lambda name: page.locator('#effectValues .effectvalue').filter(has=page.locator('.name', has_text=name)).first
    # (every saved parameter first, as saved; then what its system offers that it doesn't save)
    names = page.locator('#effectValues .effectvalue .name').all_inner_texts()
    assert names[:2] == ['Chunk_Color', 'Chunk_Brightness'] and 'Dust_Desaturation' in names, names
    page.locator('#effectValues input[type=checkbox]').uncheck()
    row('Chunk_Brightness').locator('input[type=number]').fill('3')
    row('Chunk_Brightness').locator('input[type=number]').press('Enter')
    page.wait_for_function("id => viewer.effectState(id).values?.parameters?.Chunk_Brightness === 3", arg=fx)
    row('Dust_Desaturation').locator('input[type=number]').fill('0.5')
    row('Dust_Desaturation').locator('input[type=number]').press('Enter')
    page.wait_for_function("id => viewer.effectState(id).values?.parameters?.Dust_Desaturation === 0.5", arg=fx)
    row('Chunk_Color').locator('input[type=color]').evaluate("e => { e.value = '#ff0000'; e.dispatchEvent(new Event('change')); }")
    page.wait_for_function("id => viewer.effectState(id).values?.parameters?.Chunk_Color?.[0] === 1", arg=fx)
    assert 'edited' in row('Chunk_Brightness').get_attribute('class')
    assert 'Starts off (as set here)' in page.locator('#effectInfo').text_content()
    # the size handle: dragged out, the box and the panel follow; one undo step puts it back
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('f')
    settled(page, CAMERA)
    handle = page.evaluate('viewer.lightHandles()')
    assert [h['key'] for h in handle] == ['size'], handle
    hx, hy = handle[0]['screen']
    ox, oy = handle[0]['origin']
    page.mouse.move(hx, hy); page.mouse.down(); page.mouse.move(hx + (hx - ox) * 0.6, hy, steps=6); page.mouse.up()
    scale = page.evaluate('id => viewer.effectState(id).values.scale', fx)
    assert scale and scale > 1.2, scale
    assert f'Size {scale} times' in page.locator('#effectValues .valueline').inner_text()
    page.keyboard.press('Control+z')
    assert page.evaluate('id => viewer.effectState(id).values.scale', fx) is None
    page.keyboard.press('Control+y')
    assert page.evaluate('id => viewer.effectState(id).values.scale', fx) == scale
    # a copy keeps what it was copied with
    page.keyboard.press('Control+c')
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.4, box['y'] + box['height'] * 0.6
    page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function("id => viewer.gizmo.active && viewer.gizmo.active !== id && viewer.effectRoots.get(viewer.gizmo.active)?.userData.source.added", arg=fx)
    copy = page.evaluate('viewer.gizmo.active')
    assert page.evaluate('id => viewer.effectState(id).values', copy) == page.evaluate('id => viewer.effectState(id).values', fx)
    # the copy's panel, its About line a long one: every value row and field inside the panel, none cut off at its
    # right edge (Discord B6: the rows were laid out as wide as that line)
    page.wait_for_function("() => document.getElementById('effectAboutSum').textContent.startsWith('A copy of')")
    over = page.evaluate("""() => { const p = document.getElementById('effectPanel'), right = p.getBoundingClientRect().right;
      return { wider: p.scrollWidth - p.clientWidth, cut: [...document.querySelectorAll('#effectValues .effectvalue, #effectValues input')]
        .filter(e => e.getBoundingClientRect().right > right + 0.5).length }; }""")
    assert over == dict(wider=0, cut=0), over
    # a simple sound: its outer radius dragged, its volume and pitch set
    sound = root('AmbientSoundSimple_0')
    page.evaluate(f'viewer.pickEffect({sound!r})')
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('f')
    settled(page, CAMERA)
    handles = {h['key']: h for h in page.evaluate('viewer.lightHandles()')}
    assert sorted(handles) == ['radiusMax', 'radiusMin'], handles
    hx, hy = handles['radiusMax']['screen']
    ox, oy = handles['radiusMax']['origin']
    page.mouse.move(hx, hy); page.mouse.down(); page.mouse.move(hx + (hx - ox) * 0.3, hy, steps=6); page.mouse.up()
    outer = page.evaluate('id => viewer.effectState(id).values?.radiusMax', sound)
    assert outer and outer > 750, (outer, handles, page.evaluate('viewer.lightHandles()'))
    pair = page.locator('#effectValues .valuepair').first.locator('input[type=number]')
    pair.nth(0).fill('0.5'); pair.nth(0).press('Enter')
    page.wait_for_function("id => viewer.effectState(id).values?.volume?.[0] === 0.5", arg=sound)
    pitch = page.locator('#effectValues .valuepair').nth(1).locator('input[type=number]')
    pitch.nth(1).fill('1.2'); pitch.nth(1).press('Enter')
    page.wait_for_function("id => viewer.effectState(id).values?.pitch?.[1] === 1.2", arg=sound)
    assert page.evaluate('id => viewer.effectState(id).values', sound) == dict(radiusMax=outer, volume=[0.5, 1], pitch=[1, 1.2])
    # a sound that plays a shared cue: no values to set, what it has shown
    shared = page.evaluate("[...viewer.effectRoots.values()].find(r => r.userData.source.kind === 'sound' && r.userData.source.cue && !r.userData.source.cue.private)?.userData.source.id")
    if shared:
        page.evaluate(f'viewer.pickEffect({shared!r})')
        assert page.locator('#effectValues').is_hidden()
    page.evaluate('viewer.pickEffect(null)')
    # saved and reopened as they were
    saved = [o for o in page.evaluate('viewer.editState().overrides') if o['target']['actor'].endswith(('.Emitter_38', '.AmbientSoundSimple_0'))]
    assert sorted(o['target']['actor'].rsplit('.', 1)[1] for o in saved) == ['AmbientSoundSimple_0', 'Emitter_38'], saved
    assert next(o for o in saved if 'Emitter' in o['target']['actor'])['effect']['parameters'] == [
        dict(name='Chunk_Brightness', value=3), dict(name='Chunk_Color', value=[1, 0, 0, 1]), dict(name='Dust_Desaturation', value=0.5)]
    state = page.evaluate('viewer.projectState()')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Effect values smoke {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    assert page.evaluate('viewer.projectState()') == state
    # built: the report counts them and the Build's record says what it wrote
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=300000)
    assert page.locator('#buildTitle').inner_text().startswith(f'Built Effect values smoke {RUN}'), page.locator('#buildModal').inner_text()
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built', build
    page.locator('#buildClose').click()
    assert not errors, errors
    page.close()
    return project


def check_blocker(page, recipe, count, cx, cy, drawn):
    """The blocker (Discord feedback S6): a cover block with Cover set to None is of type 'block' (blocks walking, no
    cover), saved by a recipe version that makes it; a block saved by version 1 turned into a blocker is saved by the
    latest version, and back to high cover keeps its own."""
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.locator('#libKind').select_option('Invisible')
    page.locator('.libitem[data-id="cover-block"]').click()
    page.mouse.move(cx, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.keyboard.press('p')
    page.locator('#coverHeight').select_option('block')
    assert page.locator('#details h2').inner_text() == 'Blocker' and page.locator('#coverHead').text_content() == 'Blocker'
    assert page.locator('#coverHeight').input_value() == 'block'
    assert 'blocks walking, no cover' in page.locator('#details .sub').inner_text()
    assert 'Units beside it get no cover from it' in page.locator('#coverNote').inner_text()
    assert page.locator('#coverSight').inner_text() == 'Sight: units see and shoot through it.'
    block = recipe['heights']['block']
    assert [round(v) for v in drawn()] == [96, 96, round(block[0]), round(block[1])], drawn()
    [rec] = page.evaluate('viewer.editState().added')
    assert rec['template'] == dict(kind='cover', version=recipe['latest']) and rec['cover']['type'] == 'block', rec
    # a version 1 block (as an older project saved it): a blocker needs the latest version; high cover keeps version 1
    page.evaluate("viewer.roots.get(viewer.gizmo.active).userData.source.added.template.version = 1")
    page.locator('#coverHeight').select_option('high')
    assert page.locator('#details h2').inner_text() == 'Cover block'
    assert page.evaluate('viewer.editState().added[0].template.version') == 1
    page.locator('#coverHeight').select_option('block')
    assert page.evaluate('viewer.editState().added[0].template.version') == recipe['latest']
    for _ in range(4):      # the three cover changes, the placing
        page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0


def check_cover(page):
    """Cover blocks and invisible floors (cover.js): the Add panel's Invisible kind (a Cover block and an Invisible floor,
    with drawn thumbnails); the block placed by its first tile (1 x 1, one tall, high cover) is a selected added piece
    with the cover section; its size, height and cover change as one undo step each; the project saves it as a cover
    recipe record at its corner; copy and paste make a second one alike. The floor: placed the same way, its top 1 unit
    over the ground at its tile's centre (where the game looks for a floor), its panel without height or cover but with
    that height over the ground and Fit to ground, its plate two units thin under its location, saved as a floor
    record."""
    recipe = page.evaluate('viewer.families()?.coverRecipes')
    if not recipe:
        return skip('cover', 'the server builds no cover blocks (families.json has no cover recipes)', whole=True)
    count = page.evaluate('viewer.roots.size')
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.locator('#libKind').select_option('Invisible')
    names = page.locator('.libitem strong').all_inner_texts()
    assert sorted(names) == ['Cover block', 'Invisible floor'], names
    page.wait_for_function("[...document.querySelectorAll('.libitem canvas')].every(c => c.dataset.drawn)", timeout=30000)
    page.locator('.libitem[data-id="cover-block"]').click()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.6, box['y'] + box['height'] / 2
    page.mouse.move(cx, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.keyboard.press('p')
    assert page.evaluate('viewer.changes().added') == 1
    assert page.locator('#coverBox').is_visible() and page.locator('#details h2').inner_text() == 'Cover block'
    assert page.locator('#coverHeight').input_value() == 'high' and page.locator('#coverTypeRow').is_visible()
    assert page.locator('#coverSize').inner_text() == '1 × 1 tiles across, from 12 units below its floor to 1 tile above it.'
    assert page.locator('#coverWidth').count() == 0       # sized with its handles, not fields
    high = recipe['heights']['high']
    def cover():
        return page.evaluate('viewer.editState().added[0].cover')
    assert cover() == dict(type='high', size=[96, 96], heights=high), cover()
    def drawn():
        return page.evaluate("""() => { const part = viewer.roots.get(viewer.gizmo.active).userData.parts[0];
          part.geometry.computeBoundingBox(); const g = part.geometry.boundingBox;   // the actor's frame, viewer basis
          return [g.max.x - g.min.x, g.max.z - g.min.z, g.min.y, g.max.y]; }""")
    # its six handles; each drag one undo step, by the snap setting's steps (the block framed, so a tile is many pixels)
    page.keyboard.press('f')
    # (once the view has come to it: a handle behind the camera has no place on the screen)
    page.wait_for_function("(() => { try { return Object.keys(viewer.coverHandles()).length === 6; } catch { return false; } })()")
    assert sorted(page.evaluate('viewer.coverHandles()')) == ['+x', '+y', '+z', '-x', '-y', '-z']
    set_snap(page, 'tile')
    start = page.evaluate('viewer.gizmo.pose()')['location']
    drag_handle(page, '+x', 1.3)                      # a tile and a bit: one tile more
    assert cover()['size'] == [192, 96], cover()
    drag_handle(page, '-y', 1.2)                      # out on the low side: the corner moves, the far side stays
    assert cover()['size'] == [192, 192], cover()
    moved = page.evaluate('viewer.gizmo.pose()')['location']
    assert abs(moved[1] - (start[1] - 96)) < 0.01 and abs(moved[0] - start[0]) < 0.01, (start, moved)
    drag_handle(page, '+z', 0.8)                      # up a level (64: tile snap's step up, the distance dragged)
    assert cover()['heights'] == [high[0], high[1] + 64], cover()
    drag_handle(page, '-z', -0.6)                     # the bottom up a level: off the floor
    assert cover()['heights'] == [high[0] + 64, high[1] + 64], cover()
    assert [round(v) for v in drawn()] == [192, 192, round(high[0] + 64), round(high[1] + 64)], drawn()
    for _ in range(4):
        page.keyboard.press('Control+z')
    assert cover() == dict(type='high', size=[96, 96], heights=high), cover()
    assert page.evaluate('viewer.gizmo.pose()')['location'] == start
    # snap off: smooth, not rounded; 24: steps of 24 dragged
    set_snap(page, 'off')
    drag_handle(page, '+x', -0.5)                     # half a tile in
    x = cover()['size'][0]
    assert 40 <= x <= 56, cover()
    assert 'units across' in page.locator('#coverSize').inner_text()
    page.keyboard.press('Control+z')
    set_snap(page, 'fine')
    drag_handle(page, '+y', 0.3)
    assert cover()['size'][1] % 24 == 0 and cover()['size'][1] > 96, cover()
    page.keyboard.press('Control+z')
    set_snap(page, 'off')
    # Esc during a drag puts it back
    h = page.evaluate('viewer.coverHandles()')['+x']
    page.mouse.move(h[0], h[1]); page.mouse.down(); page.mouse.move(h[2], h[3], steps=4)
    assert cover()['size'][0] > 150, cover()
    page.keyboard.press('Escape'); page.mouse.up()
    assert cover()['size'] == [96, 96], cover()
    # what the panel says the game makes of blocks smaller than a tile (coverTiles, research/native/cover-build.md),
    # each put on the tile lines by the position fields: EXP-59's five places
    ox, oy, oz = page.evaluate('viewer.data.tileGrid.origin')
    loc = page.evaluate('viewer.gizmo.pose()')['location']
    # on the tile lines, its floor 16 over its level's bottom (as the Bar's pavement)
    x0, y0, z0 = (round(ox + 96 * round((loc[0] - ox) / 96), 2), round(oy + 96 * round((loc[1] - oy) / 96), 2),
                  round(oz + 64 * ((loc[2] - oz) // 64) + 16, 2))
    steps = page.evaluate('viewer.gizmo.undoDepth()')

    def words_at(x, y, c):
        for field, v in (('#posX', x), ('#posY', y), ('#posZ', z0)):
            page.locator(field).fill(str(v)); page.locator(field).press('Enter')
        got = [round(v, 2) for v in page.evaluate('viewer.gizmo.pose()')['location']]
        assert got == [x, y, z0], (got, [x, y, z0])
        page.evaluate('c => viewer.setCover(viewer.gizmo.active, c)', c)
        return page.locator('#coverNote').inner_text()
    note = words_at(x0 + 24, y0 + 24, dict(type='high', size=[48, 48], heights=[-12, 96]))        # in a tile's middle
    assert "Units can't stand in the tile whose middle it fills." in note and 'the 4 tiles beside it get high cover' in note, note
    assert page.locator('#coverSight').inner_text().startswith('Sight: it blocks line of sight as a wall does')
    note = words_at(x0 + 92, y0, dict(type='high', size=[8, 96], heights=[-12, 96]))                # along a tile edge
    assert 'units can stand in the tiles it reaches into' in note and 'crossing the tile edge it stands across' in note \
        and 'the 2 tiles beside it get high cover' in note, note
    note = words_at(x0, y0, dict(type='high', size=[24, 24], heights=[-12, 96]))                    # in a tile's corner
    assert 'units walk past it' in note and 'off the lines the game looks for cover along' in note, note
    note = words_at(x0, y0, dict(type='high', size=[96, 96], heights=[-12, 40]))                    # short
    assert 'units can stand in the tile it reaches into' in note and 'Its top is under 44' in note, note
    sight = page.locator('#coverSight').inner_text()
    assert sight == "Sight: it doesn't stand across eye height (80 over its floor), so units see and shoot past it.", sight
    note = words_at(x0 + 95, y0, dict(type='high', size=[2, 96], heights=[-12, 96]))                # 2 units thin
    assert 'Under 4 units through' in note and 'crossing the tile edge it stands across' in note and 'No tile looks' in note, note
    while page.evaluate('viewer.gizmo.undoDepth()') > steps:
        page.keyboard.press('Control+z')
    assert cover() == dict(type='high', size=[96, 96], heights=high), cover()
    # the cover: low takes low cover's first top
    page.locator('#coverHeight').select_option('low')
    low = recipe['heights']['low']
    assert cover() == dict(type='low', size=[96, 96], heights=low), cover()
    assert 'low cover' in page.locator('#details .sub').inner_text()
    assert page.locator('#coverSight').inner_text() == 'Sight: units see and shoot over it, as over any low cover.'
    rec = page.evaluate('viewer.editState().added')[0]
    assert rec['template'] == dict(kind='cover', version=recipe['latest']), rec
    assert 'from' not in rec and 'components' not in rec and rec['actor'].endswith(tuple(f'_copy{n}' for n in range(1, 1000)))
    assert [round(v) for v in drawn()] == [96, 96, round(low[0]), round(low[1])], drawn()
    # copy and paste: a second block alike
    page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
    page.mouse.move(cx + 80, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx + 80, cy)
    page.wait_for_function('n => viewer.roots.size === n + 2', arg=count)
    added = page.evaluate('viewer.editState().added')
    assert len(added) == 2 and all(a['cover'] == dict(type='low', size=[96, 96], heights=low) for a in added), added
    assert len({a['actor'] for a in added}) == 2
    for _ in range(3):      # the paste, the cover, the placing
        page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0
    if 'block' in recipe['heights']: check_blocker(page, recipe, count, cx, cy, drawn)
    # the invisible floor: no height or cover to set, a thin plate under its location
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.locator('#libKind').select_option('Invisible')
    page.locator('.libitem[data-id="invisible-floor"]').click()
    # the ground's collision (collision.json), asked for as the entry is chosen: the floor goes 1 unit over it
    page.wait_for_function('viewer.collisionRead() !== null', timeout=60000)
    page.mouse.move(cx, cy)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.keyboard.press('p')
    assert page.locator('#details h2').inner_text() == 'Invisible floor' and page.locator('#coverHead').text_content() == 'Invisible floor'
    assert not page.locator('#coverTypeRow').is_visible()
    assert page.locator('#coverFit').is_visible()
    assert sorted(page.evaluate('viewer.coverHandles()')) == ['+x', '+y', '-x', '-y']      # its height is the Z arrow's
    assert 'it carries one tile' in page.locator('#coverSize').inner_text()
    assert not page.locator('#coverSight').is_visible()          # a floor has no sight line
    note = page.locator('#coverNote').inner_text()
    assert 'Its top is 1 unit over the ground' in note, note
    assert ("(The ground's collision, as the game sees it.)" if page.evaluate('viewer.collisionRead()')
            else 'Measured from the drawn ground') in note, note
    page.locator('#posZ').fill(str(float(page.locator('#posZ').input_value()) + 30)); page.locator('#posZ').press('Enter')
    note = page.locator('#coverNote').inner_text()
    assert 'Its top is 31 units over the ground' in note, note
    page.locator('#coverFit').click()
    note = page.locator('#coverNote').inner_text()
    assert 'Its top is 1 unit over the ground' in note, note
    page.keyboard.press('f')
    set_snap(page, 'tile')
    drag_handle(page, '+x', 1.2)
    set_snap(page, 'off')
    floor = recipe['heights']['floor']
    assert [round(v) for v in drawn()] == [192, 96, round(floor[0]), round(floor[1])], drawn()
    assert 'it carries 2 tiles' in page.locator('#coverSize').inner_text()
    added = page.evaluate('viewer.editState().added')
    assert len(added) == 1 and added[0]['cover'] == dict(type='floor', size=[192, 96]), added
    assert '_copy' in added[0]['actor'] and 'InvisibleFloor' in added[0]['actor'], added[0]['actor']
    for _ in range(4):      # the width, Fit to ground, the Z typed, the placing
        page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and page.evaluate('viewer.changes().total') == 0


def set_snap(page, mode):
    """The rail's snap button pressed until the snap is `mode` ('off', 'fine' or 'tile')."""
    for _ in range(3):
        if page.evaluate('viewer.gizmo.snap') == mode: return
        page.locator('#editSnap').click()
    assert page.evaluate('viewer.gizmo.snap') == mode


def drag_handle(page, key, tiles):
    """The selected cover piece's handle `key` dragged out along its face's axis by `tiles` tiles (in: below 0)."""
    x, y, x1, y1 = page.evaluate('t => viewer.coverHandles(t)', tiles)[key]
    assert abs(x1 - x) + abs(y1 - y) > 20, (key, x, y, x1, y1)      # far enough on the screen to drag by
    page.mouse.move(x, y); page.mouse.down()
    page.mouse.move(x1, y1, steps=6)
    page.mouse.up()


def look_down(page, xyz, height=3200):
    page.evaluate("""([[x, y, z], h]) => { viewer.controls.target.set(x, z, y); viewer.camera.position.set(x + 200, z + h, y + h * 0.28); viewer.controls.update(); }""", [xyz, height])
    settled(page, CAMERA)


def check_floor_placing(page, is_bar):
    """Floor pieces on the map: the piece list's Floors (flat pieces carrying the saved floor tiles, not decorations);
    one is placed as any piece is (Level snap went on 21 November 2026: the custom geometry improvements plan, D5), and
    the piece panel's Align to Level puts it at its height in its map moved by whole levels, the nearest (Bar: a
    sidewalk dropped on a sidewalk stacks on it, and Level puts it back at the sidewalks' height); a pasted floor piece
    is known as one too; a decoration (Bar's rug) is no floor piece. Moved up with the gizmo with snap off, a floor
    piece moves freely, and Level puts it back on a level."""
    count, original = page.evaluate('viewer.roots.size'), page.evaluate('viewer.gizmo.active')
    info = page.evaluate('viewer.floorPieces()')
    if not info['supports']: return skip('floor-placing', 'the map has no floor pieces to stand on', whole=True)
    kind_of = lambda suffix: next((k for a, k in info['kinds'].items() if a.endswith(suffix)), None)
    if is_bar:
        assert kind_of('.XComLevelActor_133') == 'floor', kind_of('.XComLevelActor_133')
        rugs = page.evaluate("""() => [...new Set(viewer.data.objects.filter(o => viewer.data.meshes[o.mesh].name.endsWith('RugRedPlane')).map(o => o.actor))]""")
        assert rugs and all(info['kinds'].get(a) == 'decoration' for a in rugs), (rugs, [info['kinds'].get(a) for a in rugs])
    # the piece list's Floors: every floor stamp's entry, each saying its size in tiles
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('p')
    page.wait_for_selector('#library:not([hidden])')
    floors = page.evaluate('viewer.pieces.entries().filter(e => e.floor).map(e => e.name)')
    assert floors, 'no floor entries'
    assert page.locator('#libKind option[value=floors]').inner_text() == f'Floors ({len(floors)})'
    page.locator('#libKind').select_option('floors')
    rows = page.locator('#libList .libitem')
    assert rows.count() == len(floors), (rows.count(), floors)
    assert all('floor, ' in t for t in rows.all_inner_texts())
    if is_bar:
        assert 'SidewalkStrA8x4' in floors and not any('Rug' in n for n in floors), floors
        assert 'floor, 8 × 4 tiles' in page.locator('#libList .libitem', has_text='SidewalkStrA8x4').first.inner_text()
    # the floor piece to place, and a saved floor tile to drop it on with the cursor on that floor: Bar's sidewalk on
    # the top of another sidewalk (XComLevelActor_133); elsewhere the first floor entry on one of its own kind's
    # tiles on another level if there is one
    target = page.evaluate("""(isBar) => {
      const entries = viewer.pieces.entries().filter(e => e.floor), kinds = viewer.floorPieces().kinds;
      const entry = isBar ? entries.find(e => e.name === 'SidewalkStrA8x4') : entries[0];
      const src = entry.sources[entry.pivotIndex], tiles = viewer.data.tactical.floorTiles.filter(t => kinds[t.actor] === 'floor');
      const mine = tiles.filter(t => isBar ? t.actor.endsWith('.XComLevelActor_133') : true);
      const level = Math.round(src.location[2] / 64);
      mine.sort((a, b) => (Math.abs(Math.round(b.location[2] / 64) - level) - Math.abs(Math.round(a.location[2] / 64) - level)));
      return { name: entry.name, pivot: src.location, tiles: mine.slice(0, 400).map(t => t.location) }; }""", is_bar)
    page.locator('#libList .libitem', has_text=target['name']).first.click()
    placing = page.evaluate('({ name: viewer.placing()?.name, floor: viewer.placing()?.floor })')
    assert placing['floor'] is not None, placing
    assert 'a floor piece' in page.locator('#dragHint').inner_text()
    if is_bar: assert placing['floor'] == 16, placing
    support = placing['floor']
    spot = None
    for loc in target['tiles']:
        look_down(page, loc, 2200)
        at = page.evaluate('p => viewer.screenOf(p)', loc)
        hit = page.evaluate('([x, y]) => { const h = viewer.pick(x, y); return h ? h.point.y : null; }', at)
        if hit is not None and abs(hit - loc[2]) < 4: spot = (loc, at); break
    assert spot, 'no saved floor tile clear under the cursor'
    loc, at = spot
    page.mouse.move(*at); page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(*at)
    page.wait_for_function('viewer.editState().added.length === 1')
    added_z = lambda: page.evaluate('viewer.editState().added[0].location[2]')
    expect = target['pivot'][2] + round((loc[2] - target['pivot'][2]) / 64) * 64
    if is_bar: assert added_z() > 10, added_z()       # placed as any piece: on the sidewalk's top, 16 to 18 up
    # Align to Level (the piece panel's Align section): its height in its map moved by whole levels, the nearest
    page.wait_for_selector('#alignLevel:not([hidden])')
    page.locator('#alignLevel').click()
    z = added_z()
    assert abs((z - target['pivot'][2]) / 64 - round((z - target['pivot'][2]) / 64)) < 1e-6, (z, target['pivot'])
    assert abs(z - expect) <= 64, (z, expect, loc, support, target['pivot'])
    if is_bar: assert abs(z) < 0.01, z     # at the sidewalks' height, not stacked 16 to 18 units up
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    # a decoration (Bar's rug) and a piece that isn't a floor are no floor pieces
    if is_bar:
        page.locator('#libKind').select_option('all')
        page.locator('#libFilter').fill('rug')
        page.locator('#libList .libitem', has_text='RugRedPlane').first.click()
        assert page.evaluate('viewer.placing()?.floor') is None and 'a floor piece' not in page.locator('#dragHint').inner_text()
        page.locator('#libFilter').fill('')
    page.keyboard.press('Escape')
    page.keyboard.press('p')
    assert page.locator('#library').is_hidden()
    # a floor piece copied and pasted is one too
    if is_bar:
        side = page.evaluate("""() => [...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComLevelActor_133')).userData.source.id""")
        page.evaluate('id => viewer.select(id)', side)
        page.evaluate('document.activeElement && document.activeElement.blur()')
        page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
        assert page.evaluate('viewer.placing()?.floor') == 16
        page.keyboard.press('Escape')
        # Moved up with the gizmo's up arrow (snap off), the sidewalk moves freely; Level puts it back on a level
        page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', side)
        page.evaluate('document.activeElement && document.activeElement.blur()')
        page.keyboard.press('g')
        page.wait_for_timeout(200)      # (a frame drawn where it was framed, before the screen points)
        z0 = page.evaluate('viewer.gizmo.pose().location[2]')
        p0 = page.evaluate('viewer.screenOf(viewer.gizmo.pose().location)')
        up = page.evaluate('p => viewer.screenOf([p[0], p[1], p[2] + 100])', page.evaluate('viewer.gizmo.pose().location'))
        n = ((up[0] - p0[0]) ** 2 + (up[1] - p0[1]) ** 2) ** 0.5
        d = [(up[0] - p0[0]) / n, (up[1] - p0[1]) / n]
        grab = None
        for r in range(20, 160, 6):
            pt = [p0[0] + d[0] * r, p0[1] + d[1] * r]
            page.mouse.move(*pt)    # (the gizmo takes its hovered axis in its pointermove listener)
            if page.evaluate('viewer.gizmo.controls.axis') == 'Y': grab = pt; break
        assert grab, "the gizmo's up arrow not found"
        page.mouse.down(); page.mouse.move(grab[0] + d[0] * 140, grab[1] + d[1] * 140, steps=8); page.mouse.up()
        rise = page.evaluate('viewer.gizmo.pose().location[2]') - z0
        assert rise > 1 and abs(rise / 64 - round(rise / 64)) > 1e-3, rise
        page.locator('#alignLevel').click()
        rise = page.evaluate('viewer.gizmo.pose().location[2]') - z0
        assert abs(rise / 64 - round(rise / 64)) < 1e-6, rise
        page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
        assert page.evaluate('viewer.changes().total') == 0
        page.keyboard.press('v')
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.roots.size') == count
    page.evaluate('id => viewer.select(id)', original)


# The floor tile tip shown and saying `arg` (the draw loop writes it once the pointer has moved)
TIP_SAYS = "t => !document.getElementById('floorTip').hidden && document.getElementById('floorTip').textContent.includes(t)"


def check_floor_tiles(page, is_bar):
    """View options, Floor tiles (private/plans/done/floor-brush-plan.md, 3.7): the saved floor tiles in one batched mesh, a
    deleted piece's hatched, a tile's piece named on hover and selected on a click; and a copy's building-floor
    listings following where it stands (3.8), on Bar's floor pieces."""
    total = page.evaluate('viewer.data.tactical?.floorTiles?.length ?? 0')
    if not total: return skip('floor-tiles', 'the export has no saved floor tiles', whole=True)
    original = page.evaluate('viewer.gizmo.active')
    check_option(page, 'floorTiles', True)
    page.keyboard.press('Escape')
    drawn = page.evaluate('viewer.floorTiles()')
    assert 0.5 * total < drawn <= total, (drawn, total)
    assert page.evaluate("viewer.world.children.some(g => g.userData.tiles && g.children.filter(c => c.isMesh).length === 1)")
    # a tile's piece: hovered, named; deleted, its tiles hatched and still drawn; a click on another tile selects its piece
    # a tile whose piece is the first thing under it from above (no prop standing on it)
    t = None
    for k in range(0, 400, 7):
        t = page.evaluate("""(k) => { const tiles = viewer.data.tactical.floorTiles.filter(f => [...viewer.roots.values()].some(r => r.userData.source.actor === f.actor && r.visible && !r.userData.source.added));
          const f = tiles[k % tiles.length], r = [...viewer.roots.values()].find(r => r.userData.source.actor === f.actor && !r.userData.source.added && r.visible);
          return { tile: f, id: r.userData.source.id }; }""", k)
        look_down(page, t['tile']['location'], 2400)
        if page.evaluate("""f => { const h = viewer.pick(...viewer.screenOf(f.location)); return h && viewer.roots.get(h.object.userData.objectId).userData.source.actor === f.actor; }""", t['tile']): break
    else: raise AssertionError('no clear floor tile')
    page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', t['tile']['location']))
    page.wait_for_function(TIP_SAYS, arg=t['tile']['actor'].split('.')[-1])
    assert page.locator('#floorTip').is_visible() and t['tile']['actor'].split('.')[-1] in page.locator('#floorTip').inner_text()
    page.evaluate('id => viewer.select(id)', t['id'])
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.floorTiles()') == drawn
    assert page.evaluate("viewer.world.children.some(g => g.userData.tiles && g.children.some(c => c.isLineSegments))")
    page.mouse.move(10, 10); page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', t['tile']['location']))
    page.wait_for_function(TIP_SAYS, arg='deleted since')
    assert 'deleted since' in page.locator('#floorTip').inner_text()
    page.keyboard.press('Control+z')
    page.evaluate('viewer.select(null)')
    page.mouse.click(*page.evaluate('p => viewer.screenOf(p)', t['tile']['location']))
    assert page.evaluate('viewer.roots.get(viewer.gizmo.active)?.userData.source.actor') == t['tile']['actor']
    check_option(page, 'floorTiles', False)
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.floorTiles()') is None
    if is_bar and page.evaluate('viewer.data.exporterVersion >= 15'):
        # Bar's XComLevelActor_104 is in floor 0 of XComBuildingVolume_0's cutaway: its copy beside it, in the same floor
        # volume, is listed there; out on the road, nowhere; back where its original stands, there again
        src = page.evaluate("""() => { const r = [...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComLevelActor_104')); viewer.select(r.userData.source.id);
          return [r.userData.source.id, r.userData.source.location, r.userData.source.floors]; }""")
        page.locator('#editCopy').click()
        box = page.locator('#viewport > canvas').bounding_box()
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible')
        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.wait_for_function('viewer.gizmo.selection().every(r => r.userData.source.added)')
        copy, steps = page.evaluate('viewer.gizmo.active'), 1
        for (x, y, z), expect in (((src[1][0] + 96, src[1][1], src[1][2]), src[2]), ((-2600, -1800, 0), [])):
            for k, (field, value) in enumerate((('posX', x), ('posY', y), ('posZ', z))):
                delta = value - page.evaluate(f'viewer.gizmo.pose().location[{k}]')
                if abs(delta) > 0.01: type_pose(page, field, delta); steps += 1
            assert page.evaluate('id => viewer.listingsNow(id)', copy) == expect, (x, y, page.evaluate('id => viewer.listingsNow(id)', copy), expect)
        for _ in range(steps): page.keyboard.press('Control+z')
        assert page.evaluate('viewer.changes().total') == 0, page.evaluate('viewer.changes()')
    if original: page.evaluate('id => viewer.select(id)', original)


def check_lights(page, is_bar):
    """Lights in the editor (private/plans/done/editor-lights-plan.md, 4.6): Shift+L shows the map's point and spot lights as
    markers; a click on a marker selects its light (ahead of the piece behind it) and opens the light panel; a typed
    brightness is one undo step and changes the reach note; Solo dims the map to the selected light; a light copies,
    pastes, deletes and comes back; the Map lighting mode takes the lights as edited; on Bar, a glowing piece moved or
    copied takes its generated lights along. An export older than 18 shows the lights view only and offers Prepare.
    Reset all puts it all back."""
    blur = lambda: page.evaluate('document.activeElement?.blur()')
    if page.evaluate('viewer.data.exporterVersion < 18'):
        assert 'Prepare now' in page.locator('#projectBanner').inner_text()
        some = page.evaluate("[...viewer.lightRoots.values()].find(r => r.userData.source.role === 'static')?.userData.source.id")
        if some:
            page.evaluate('id => viewer.select(id)', some)
            assert page.locator('#lightBrightness').is_disabled() and 'export 18' in page.locator('#lightNote').inner_text()
            page.evaluate('viewer.select(null)')
        return
    original = page.evaluate('viewer.gizmo.active')
    base = page.evaluate('viewer.lightRoots.size')
    placed = page.evaluate("viewer.data.lights.filter(l => ['point', 'spot'].includes(l.kind) && Array.isArray(l.location)).length")
    assert base >= placed > 0, (base, placed)
    blur()
    page.evaluate('viewer.setNormalLights(false); viewer.setLightsShown(false)')     # (a light added earlier turned the switch on)
    layer_shown = "[...viewer.lightRoots.values()][0].parent.visible"
    assert not page.evaluate(layer_shown) and page.evaluate('viewer.pickLight(0, 0)') is None
    page.keyboard.press('Shift+L')
    assert page.evaluate('viewer.lightsShown()') and page.evaluate(layer_shown)
    assert 'on' in page.locator('#editLights').get_attribute('class')
    # a click on an editable light's marker selects it
    light = page.evaluate("""() => { const r = [...viewer.lightRoots.values()].find(r => r.userData.source.role === 'static'
        && !r.userData.source.channels && r.userData.source.bakedInto?.length && r.visible);
      viewer.select(null); viewer.frame(r); return r.userData.source.id; }""")
    settled(page, CAMERA)
    at = page.evaluate("""id => { const r = viewer.lightRoots.get(id), front = r.userData.marker.userData.front;
      viewer.world.updateMatrixWorld(true); front.geometry.computeBoundingSphere();
      const p = front.geometry.boundingSphere.center.clone().applyMatrix4(front.matrixWorld).project(viewer.camera);
      const rect = viewer.renderer.domElement.getBoundingClientRect();
      return [rect.left + (p.x + 1) / 2 * rect.width, rect.top + (1 - p.y) / 2 * rect.height]; }""", light)
    page.mouse.click(*at)
    assert page.evaluate('viewer.gizmo.active') == light, page.evaluate('viewer.gizmo.active')
    assert page.locator('#lightBox').is_visible() and 'Baked into' in page.locator('#lightReach').inner_text()
    # the outlines of the pieces it reaches are View options' choice, off at first
    shapes, reach_toggle = 'viewer.lightShapes.children.length', "document.getElementById('reachToggle')"
    assert not page.evaluate(reach_toggle + '.checked') and page.evaluate(shapes) == 1
    page.evaluate(reach_toggle + '.click()')
    assert page.evaluate(shapes) == 2 and '(outlined)' in page.locator('#lightReach').inner_text()
    page.evaluate(reach_toggle + '.click()')
    assert page.evaluate(shapes) == 1 and '(outlined)' not in page.locator('#lightReach').inner_text()
    values = lambda: page.evaluate('id => viewer.lightRoots.get(id).userData.values', light)
    start = values()
    page.locator('#lightBrightness').fill(str(start['brightness'] + 1)); page.locator('#lightBrightness').press('Enter')
    assert values()['brightness'] == start['brightness'] + 1 and page.evaluate('viewer.changes().lights') == 1
    assert 'Reaches about' in page.locator('#lightReach').inner_text()
    page.locator('#lightBrightness').fill('500'); page.locator('#lightBrightness').press('Enter')   # out of range: refused
    assert values() == {**start, 'brightness': start['brightness'] + 1}
    blur()
    page.keyboard.press('Control+z')
    assert values() == start and page.evaluate('viewer.changes().total') == 0
    page.keyboard.press('Control+y')
    assert values()['brightness'] == start['brightness'] + 1
    # Solo: the map dimmed, the light alone
    page.keyboard.press('o')
    assert page.evaluate('viewer.soloOn() && viewer.hemisphere.intensity < 0.2 && viewer.sun.intensity === 0')
    page.keyboard.press('o')
    assert page.evaluate('!viewer.soloOn() && viewer.hemisphere.intensity > 0.2')
    # copy, paste, delete, undo
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.55
    page.keyboard.press('Control+c'); page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.lightRoots.size > n', arg=base)
    copy = page.evaluate('viewer.gizmo.active')
    assert page.evaluate('id => viewer.lightRoots.get(id).userData.source.added.from.actor', copy) == \
        page.evaluate('id => viewer.lightRoots.get(id).userData.source.actor', light)
    assert page.evaluate('id => viewer.lightRoots.get(id).userData.values.brightness', copy) == start['brightness'] + 1
    blur()
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.lightRoots.size') == base
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.lightRoots.size') == base + 1
    # the Map lighting mode takes the lights as edited
    choose(page, 'lighting', 'game'); page.wait_for_function('viewer.lighting.counts.all === viewer.lightRecords().length')
    assert page.evaluate('viewer.lighting.counts.all === viewer.lightRecords().length')
    assert page.evaluate('id => viewer.lightRecords().some(l => l.actor === viewer.lightRoots.get(id).userData.source.actor)', copy)
    choose(page, 'lighting', 'neutral')
    page.keyboard.press('Escape')
    # drag handles: a spot light's outer cone and a point light's radius follow the pointer live, the camera stays, the
    # release is one undo step, and Escape during a drag puts it back
    values_of = lambda i: page.evaluate('id => viewer.lightRoots.get(id).userData.values', i)
    for kind, field, keys in (('spot', 'outerConeAngle', {'radius', 'outer', 'inner'}), ('point', 'radius', {'radius'})):
        lid = page.evaluate("""([kind, skip]) => { const r = [...viewer.lightRoots.values()].find(r => r.userData.source.kind === kind
            && r.userData.source.role === 'static' && !r.userData.source.channels && !r.userData.source.added && r.visible
            && r.userData.source.id !== skip && r.userData.values.radius > 150 && r.userData.values.radius < 900
            && (kind !== 'spot' || (r.userData.values.outerConeAngle > 20 && r.userData.values.outerConeAngle < 89
                                    && r.userData.values.innerConeAngle < 10)));
          viewer.select(r.userData.source.id); const e = r.matrix.elements, R = r.userData.values.radius;
          viewer.controls.target.set(e[12], e[13] - (kind === 'spot' ? R * 0.4 : 0), e[14]);
          viewer.camera.position.set(e[12] + R * 1.8, e[13] + R * 1.2, e[14] + R * 1.8); viewer.controls.update();
          return r.userData.source.id; }""", [kind, light])
        settled(page, CAMERA)
        handles = {h['key']: h for h in page.evaluate('viewer.lightHandles()')}
        assert set(handles) == keys, (kind, handles)
        start_at = handles['outer' if kind == 'spot' else 'radius']['screen']
        if kind == 'spot':   # half way to the end of its axis: narrower
            end = handles['radius']['screen']
            to = [start_at[0] + (end[0] - start_at[0]) * 0.5, start_at[1] + (end[1] - start_at[1]) * 0.5]
        else:                # further from the light: wider
            o = handles['radius']['origin']
            to = [start_at[0] + (start_at[0] - o[0]) * 0.4, start_at[1] + (start_at[1] - o[1]) * 0.4]
        before, edits = values_of(lid), page.evaluate('viewer.changes().lights')
        cam = page.evaluate('viewer.camera.position.toArray()')
        page.mouse.move(*start_at); page.mouse.down(); page.mouse.move(*to, steps=8)
        assert page.evaluate('viewer.lightDragging()') and values_of(lid)[field] != before[field], values_of(lid)
        page.keyboard.press('Escape'); page.mouse.up()
        assert values_of(lid) == before and not page.evaluate('viewer.lightDragging()')
        page.mouse.move(*start_at); page.mouse.down(); page.mouse.move(*to, steps=8); page.mouse.up()
        after = values_of(lid)
        assert (after[field] < before[field]) if kind == 'spot' else (after[field] > before[field]), (kind, before, after)
        assert {k for k in after if after[k] != before[k]} == {field}, (before, after)
        assert max(abs(a - b) for a, b in zip(page.evaluate('viewer.camera.position.toArray()'), cam)) < 1
        assert page.evaluate('viewer.changes().lights') == edits + 1 and page.evaluate('viewer.gizmo.active') == lid
        blur()
        page.keyboard.press('Control+z')
        assert values_of(lid) == before, (before, values_of(lid))
    page.keyboard.press('Escape')
    if is_bar:
        # the claw machine glows: its 33 generated lights follow it, and its copy gets copies of them
        claw = page.evaluate("""() => { const r = [...viewer.roots.values()].find(r => !r.userData.source.added
            && r.userData.source.actor.endsWith('.XComDestructibleActor_316')); viewer.select(r.userData.source.id); viewer.frame(r);
          return r.userData.source.id; }""")
        mine = "[...viewer.lightRoots.values()].filter(r => r.userData.source.emitterAttachment?.owner?.target?.actor?.endsWith('.XComDestructibleActor_316'))"
        assert page.evaluate(mine + '.length') == 33
        piece_x = 'id => viewer.roots.get(id).matrix.elements[12]'
        before, piece_before = page.evaluate(mine + '[0].matrix.elements[12]'), page.evaluate(piece_x, claw)
        assert 'Glows · 33 lights' in page.locator('#details').inner_text()
        type_pose(page, 'posX', 192)
        moved = page.evaluate(piece_x, claw) - piece_before
        assert abs(moved - 192) < 0.01 and abs(page.evaluate(mine + '[0].matrix.elements[12]') - before - moved) < 1e-3, moved
        assert page.evaluate('viewer.gizmo.active') == claw
        blur()
        page.keyboard.press('Control+c'); page.mouse.move(cx, cy); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible')
        n = page.evaluate('viewer.roots.size')
        page.mouse.click(cx, cy)
        page.wait_for_function('n => viewer.roots.size > n', arg=n)
        try:
            page.wait_for_function('viewer.derivedCopies().length === 33', timeout=5000)
        except Exception:
            raise AssertionError(page.evaluate("""() => ({ derived: viewer.derivedCopies().length,
              added: [...viewer.roots.values()].filter(r => r.userData.source.added).map(r => r.userData.source.actor) })"""))
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.lightRoots.size') == base
    assert page.evaluate('id => JSON.stringify(viewer.lightRoots.get(id).userData.values)', light) == json.dumps(start, separators=(',', ':'))
    # (selecting a piece on the way left the Lights view: back to the normal view either way)
    page.keyboard.press('Shift+N')
    assert not page.evaluate('viewer.lightsShown() || viewer.lightsOn()')
    page.evaluate('id => viewer.select(id)', original)


def check_library_assembly(browser, url):
    """An assembly of another map from All maps (a car: its body, glass and parts are one entry): placed as one, its
    parts linked to each other and not to the car they come from, saved and reopened. Only against a test server as
    check_library_all's, whose scanned library has such an entry that can be placed and that the open map lacks; a
    ladder of another map, if the library has one to place, is placed too and keeps to the grid. Returns what it
    placed."""
    errors = []
    page = open_viewer(browser, url, errors)
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): return skip('library-assembly', 'needs a map, not a preview', page, whole=True)
    count = page.evaluate('viewer.roots.size')
    page.keyboard.press('p')
    choose(page, 'libScope', 'all')
    page.wait_for_function('viewer.library.ready()', timeout=60000)
    done = {}
    box = page.locator('#viewport > canvas').bounding_box()
    spots = dict(car=(0.6, 0.5), door=(0.45, 0.6), ladder=(0.7, 0.65))
    for family in ('car', 'door', 'ladder'):
        entry = page.evaluate("""f => viewer.library.entries().find(e => e.placeable && !e.here && e.family === f
            && (f === 'ladder' || e.assembly)) ?? null""", family)
        if entry is None: continue
        key, parts = entry['key'], (entry.get('assembly') or dict(members=1))['members']
        page.locator('#libAllFilter').fill(entry['name'])
        at = page.evaluate('k => viewer.library.shown().findIndex(e => e.key === k)', key)
        assert at >= 0, entry['name']
        page.evaluate("i => { document.getElementById('libAllList').scrollTop = i * 61; }", at)
        row = page.locator(f'#libAllList .libitem[data-key="{key}"]')
        row.wait_for()
        if parts > 1: assert f'{parts} pieces placed as one' in row.get_attribute('title')
        before = set(page.evaluate('viewer.editState().added.map(a => a.id)'))
        row.click()
        page.wait_for_function('viewer.placing()?.fromList', timeout=120000)
        cx, cy = box['x'] + box['width'] * spots[family][0], box['y'] + box['height'] * spots[family][1]
        page.mouse.move(cx, cy)
        page.wait_for_function('viewer.placing()?.ghost.visible')
        page.mouse.click(cx, cy)
        page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")
        added = [a for a in page.evaluate('viewer.editState().added') if a['id'] not in before]
        # one record for each part, each from its own actor of the home map
        assert len(added) == parts, (family, len(added), parts)
        assert {a['from']['package'] for a in added} == {entry['source']['package']}, (added, entry['source'])
        assert len({a['from']['actor'] for a in added}) == parts and len({a['actor'] for a in added}) == parts
        if parts > 1:
            # the parts share one link tag of this copy, so they move, copy and delete as one
            tags = {a.get('prefab') for a in added}
            assert len(tags) == 1 and re.match(r'copy\d+:', next(iter(tags)) or ''), tags
        if family == 'car':
            # the body's partner is the glass of this copy, not the home map's
            partners = [a['partner'] for a in added if a.get('partner')]
            assert partners and all(p in {a['actor'] for a in added} for p in partners), partners
        # it is of its family for the page's rules too: it stands on this map's tile grid as on its own
        assert page.evaluate("""n => { const picked = viewer.gizmo.picks().ids; return picked.length >= n; }""", parts)
        done[family] = dict(name=entry['name'], package=entry['source']['package'], parts=parts)
    if not done: return skip('library-assembly', 'no assembly of another map could be placed', page, whole=True)
    page.keyboard.press('p')
    total = page.evaluate('viewer.roots.size')
    assert total > count
    state = page.evaluate('viewer.projectState()')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, 'Library assembly smoke %d' % page.evaluate('Date.now() % 100000'))   # a name of its own, run after run
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    assert page.evaluate('viewer.projectState()') == state and page.evaluate('viewer.roots.size') == total
    assert not any(page.evaluate('viewer.project().carried').values())
    assert errors == [], errors
    page.close()
    return done


def open_viewer(browser, url, errors, expected=()):
    """A page of its own, with its errors collected (HTTP statuses in `expected` are a test's own doing)."""
    page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and not any(f'status of {s}' in m.text for s in expected) else None)
    page.on('dialog', lambda d: d.accept())
    page.goto(url)
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    return page


def project_url(page, project_id):
    return page.url.split('?')[0] + f"?map={page.evaluate('viewer.mapId')}&project={project_id}"


def wait_recovery(page, present):
    for _ in range(60):
        kept = page.evaluate("id => fetch(`/projects/${id}/recovery.json`).then(r => r.json())", page.evaluate('viewer.project().id'))
        if (kept is not None) == present: return kept
        page.wait_for_timeout(250)
    raise AssertionError(f'recovery state never became {"present" if present else "absent"}')


def type_pose(page, field, delta):
    """Move or turn the selection by typing into the piece panel (one undo step)."""
    index = ['posX', 'posY', 'posZ', 'rotP', 'rotY', 'rotR'].index(field)
    pose = page.evaluate('viewer.gizmo.pose()')
    value = (pose['location'] + pose['rotation'])[index] + delta
    page.locator('#' + field).fill(f'{value:.2f}'); page.locator('#' + field).press('Enter')


def wait_opened(page, project_id):
    """After a project was chosen in the Load dialog or the recent list: the page reloads on it."""
    for _ in range(240):
        if f'project={project_id}' in page.url: break
        page.wait_for_timeout(250)
    else:
        raise AssertionError(f'never opened {project_id}: still at {page.url}, dialog '
                             f'{"open" if page.locator("#fileDialog").is_visible() else "closed"}, '
                             f'project {page.evaluate("viewer.project() && viewer.project().id")}')
    page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                           arg=project_id, timeout=120000)


def type_project_name(page, name):
    """The Save dialog's name box filled in, and the map name it builds as worked out by the server (Save waits for
    it: output names plan 3.3)."""
    page.locator('#fileName').fill(name)
    page.wait_for_function("() => !document.getElementById('fileOk').disabled")
    return page.locator('#fileOutput').inner_text()


def save_dialog(page, name):
    """Save as…: the Save dialog, a name typed into it (and its map name worked out)."""
    page.locator('#projectButton').click()
    page.locator('#projectSaveAs').click()
    page.wait_for_selector('#fileDialog:not([hidden]) .filerow, #fileDialog:not([hidden]) .filelist .empty')
    assert page.locator('#fileTitle').inner_text() == 'Save project' and page.locator('#fileOk').inner_text() == 'Save'
    return type_project_name(page, name)


def check_output_names(browser, url, errors):
    """Output names plan 3.3 and 5: Save shows a new project's map name (its name as one word, at most 24 characters)
    before writing anything, and nothing while the answer for what is typed is still coming; a name another project
    has is numbered, saying why; one taken between the answer and the save is refused with the next, the dialog left
    open with nothing lost; the open project and one replaced keep their own. Saves projects: a test server with
    --projects <scratch folder> only."""
    page = open_viewer(browser, url, errors, expected=(409,))
    stamp = page.evaluate('Date.now() % 100000')
    name, word = f'Names smoke {stamp}', f'NamesSmoke{stamp}'
    # the server's answer held back: Save stays disabled and no name is shown meanwhile
    page.evaluate("""() => { const f = window.fetch; window.slowNames = true; window.namesAsked = null;
      window.fetch = (u, o) => String(u).includes('output-names') && window.slowNames
        ? (window.namesAsked = JSON.parse(o.body).name, new Promise(r => setTimeout(() => r(f(u, o)), 1500))) : f(u, o); }""")
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    page.locator('#fileName').fill(name)
    page.wait_for_function('n => window.namesAsked === n', arg=name)     # (the name typed asked for, its answer held back)
    assert page.locator('#fileOk').is_disabled() and page.locator('#fileOutput').inner_text() == 'Builds as …'
    page.wait_for_function("() => !document.getElementById('fileOk').disabled")
    page.evaluate('window.slowNames = false')
    assert page.locator('#fileOutput').inner_text() == f'Builds as {word} · map names keep to 24 characters', page.locator('#fileOutput').inner_text()
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    first = page.evaluate('viewer.project()')
    assert first['doc']['output'] == dict(shipAs=word, patch='patch_' + word.lower()), first['doc']['output']
    # another project's name as one word: numbered, and why
    shown = save_dialog(page, f'names-smoke {stamp}')
    assert f'Builds as {word}_2' in shown and 'is taken' in shown, shown
    # taken meanwhile (another tab saves a project under it): refused with the next, the dialog stays open
    other = page.evaluate("""async ([name, shipAs]) => {
      const id = crypto.randomUUID(), doc = { ...viewer.project().doc, id, name, output: { shipAs, patch: 'patch_' + shipAs.toLowerCase() },
        overrides: [], added: [], groups: [], areaLightBindings: [] };
      delete doc.revision; delete doc.savedAt; delete doc.created;
      const r = await fetch(`/projects/${id}/project.json`, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expectedRevision: 0, document: doc }) });
      return [r.status, id]; }""", [f'Names  smoke {stamp}', f'{word}_2'])     # another name, the same as one word
    assert other[0] == 200, other
    page.locator('#fileName').press('Enter')
    page.wait_for_function("() => document.getElementById('fileMessage').textContent.includes('Not saved')")
    assert page.locator('#fileDialog').is_visible() and page.evaluate('viewer.project().id') == first['id']
    assert f'Builds as {word}_3' in page.locator('#fileOutput').inner_text(), page.locator('#fileOutput').inner_text()
    page.locator('#fileName').press('Enter')
    page.wait_for_function('id => viewer.project()?.id !== id && viewer.project().revision === 1', arg=first['id'])
    third = page.evaluate('viewer.project()')
    assert third['doc']['output']['shipAs'] == f'{word}_3'
    # the open project's own name (another case): its fixed name, kept
    shown = save_dialog(page, f'NAMES-smoke {stamp}')
    assert shown == f'Builds as {word}_3 · fixed when the project was first saved', shown
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 2')
    assert page.evaluate('viewer.project().doc.output.shipAs') == f'{word}_3'
    # another project's name: replaced, its own map name kept
    shown = save_dialog(page, name)
    assert shown.startswith(f'Builds as {word} · fixed'), shown
    page.locator('#fileName').press('Enter')
    page.locator('#fileConfirm button.primary').click()
    page.wait_for_function('id => viewer.project()?.id === id && viewer.project().revision === 2', arg=first['id'])
    assert page.evaluate('viewer.project().doc.output') == first['doc']['output']
    page.locator('#projectButton').click()
    assert f'Builds as {word}' in page.locator('#projectInfo').inner_text()
    page.close()
    return dict(first=word, numbered=f'{word}_3')


def check_effects_view(page):
    """The Effects view (export 28; effects and sounds plan, FX1): Shift+X shows a marker for each effect, sound and lens
    flare (Full scene), a click on one picks it (never a piece) and its panel says what it is, a picked sound shows its
    reach, the flyout's boxes hide a kind, Escape lets the picked one go, and plain X still flips the gizmo's axes.
    The selection it found is selected again at its end."""
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"):
        return skip('effects', 'the Effects view: needs a map (not a preview) of export 28 or later', whole=True)
    held = page.evaluate('viewer.gizmo.active')
    page.evaluate('viewer.select(null)')
    if page.locator('#scenery').is_visible(): choose(page, 'scenery', 'full')
    page.keyboard.press('Shift+X')
    assert page.evaluate('viewer.effectsOn()') and page.locator('#editEffects').get_attribute('aria-pressed') == 'true'
    marks = page.evaluate('viewer.effectMarkers()')
    own = page.evaluate('(viewer.data.effects ?? []).length + (viewer.data.sounds ?? []).length + (viewer.data.flares ?? []).length')
    assert len([m for m in marks if not m['derived'] and not m['id'].startswith('stream-')]) == own, (len(marks), own)
    if not marks:
        page.keyboard.press('Shift+X'); page.evaluate('id => viewer.select(id)', held); return
    box = page.evaluate('(() => { const r = viewer.renderer.domElement.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()')
    on_screen = [m for m in marks if m['screen'] and box[0] + 40 < m['screen'][0] < box[2] - 340 and box[1] + 40 < m['screen'][1] < box[3] - 80]
    if on_screen:
        target = on_screen[0]
        page.mouse.click(*target['screen'])
        assert page.evaluate('viewer.pickedEffect()') == target['id'], (page.evaluate('viewer.pickedEffect()'), target)
        assert page.locator('#effectPanel').is_visible() and page.evaluate('viewer.gizmo.picks().ids') == [target['id']]
        assert re.match(r'(Effect|Sound|Lens flare): ', page.locator('#effectTitle').inner_text(), re.I)
        page.keyboard.press('Escape')
        assert page.evaluate('viewer.pickedEffect()') is None and page.locator('#effectPanel').is_hidden()
    heard = page.evaluate("(viewer.data.sounds ?? []).find(s => s.values?.radiusMax > 0 && s.values?.attenuate !== false)?.id ?? null")
    if heard:
        page.evaluate(f'viewer.pickEffect({heard!r})')
        assert page.evaluate('viewer.effectShapes.children.length') == 1
        page.evaluate('viewer.pickEffect(null)')
    check_wave_preview(page)
    # the flyout's Sounds box hides the sounds and brings them back
    count = lambda kind: page.evaluate(f"viewer.effectMarkers().filter(m => m.kind === {kind!r}).length")
    if count('sound'):
        page.evaluate("(() => { const b = document.getElementById('effectShow-sound'); b.checked = false; b.onchange({ target: b }); })()")
        assert count('sound') == 0
        page.evaluate("(() => { const b = document.getElementById('effectShow-sound'); b.checked = true; b.onchange({ target: b }); })()")
        assert count('sound') > 0
    space = page.evaluate('viewer.gizmo.space')
    page.keyboard.press('x')
    assert page.evaluate('viewer.gizmo.space') != space and page.evaluate('viewer.effectsOn()')
    page.keyboard.press('x')
    page.keyboard.press('Shift+X')
    assert not page.evaluate('viewer.effectsOn()') and not page.evaluate('viewer.effectMarkers().length')
    page.evaluate('id => viewer.select(id)', held)


def check_effects_editing(page):
    """Effects and sounds edited (effects and sounds plan, FX3), in the Effects view: with their families held back
    (the server's default until their game check passes) a picked effect is view only and Delete says why. With them
    built (serve --family effect --family sound): a typed move and Delete are undo steps; a copy pastes as a copy of
    the effect, its hint naming an effect; the normal view's Effects and sounds switch draws and picks them with
    pieces; a piece and an effect grouped move together; an effect a piece carries follows it, and Keep where it is
    keeps it where the map has it. Everything is undone at the end, and the selection it found selected again; the
    snap setting it found is put back on every way out (a skip, an effect that is view only, a failure)."""
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"):
        return skip('effects', 'effect edits: needs a map (not a preview) of export 28 or later', whole=True)
    snap = page.evaluate('viewer.gizmo.snap')
    page.evaluate("viewer.gizmo.setSnap('off')")
    try:
        return effects_editing(page, snap)
    finally:
        if not page.is_closed(): page.evaluate('s => viewer.gizmo.setSnap(s)', snap)


def effects_editing(page, snap):
    """check_effects_editing's edits, with the snap off (`snap`: the setting it found, put back as it ends)."""
    held = page.evaluate('viewer.gizmo.active')
    blur = lambda: page.evaluate('document.activeElement?.blur()')
    state = lambda id: page.evaluate('id => { viewer.effectMarkers(); return viewer.effectState(id); }', id)
    # a drag of the gizmo along game X, as TransformControls makes one (an effect's panel has no pose fields)
    drag = lambda dx: page.evaluate('''dx => { const c = viewer.gizmo.controls, p = c.object; c.dispatchEvent({type: 'mouseDown'});
        p.position.x += dx; p.updateMatrixWorld(true); c.dispatchEvent({type: 'objectChange'}); c.dispatchEvent({type: 'mouseUp'}); }''', dx)
    fx = page.evaluate("""[...viewer.effectRoots.values()].map(r => r.userData.source).find(o => o.kind === 'effect' && !o.stream
        && !o.carriedBy && !o.landingActor && o.can?.move && o.can?.delete && o.can?.copy)?.id ?? null""")
    if not fx: return skip('effects', 'effect edits: the map has no effect that can be moved, copied and deleted', whole=True)
    page.evaluate('viewer.select(null); viewer.setNormalEffects(false); viewer.setEffectsShown(true)')
    page.evaluate('id => viewer.pickEffect(id)', fx)
    assert page.evaluate('viewer.effectsOn()') and page.evaluate('viewer.pickedEffect()') == fx
    blur()
    if state(fx)['viewOnly']:
        page.keyboard.press('Delete')
        assert not state(fx)['deleted'] and 'shown, not changed' in page.locator('#dragHint').inner_text()
        page.keyboard.press('Control+c')
        assert "It isn't copied" in page.locator('#dragHint').inner_text()
        page.keyboard.press('Shift+X'); page.evaluate('([s, id]) => { viewer.gizmo.setSnap(s); viewer.select(id); }', [snap, held]); return
    edits = 'viewer.gizmo.undoDepth()'
    depth = page.evaluate(edits)
    # a move, undone
    start = state(fx)['at']
    drag(96)
    moved = state(fx)
    assert moved['moved'] and abs(moved['at'][0] - start[0] - 96) < 0.01, (start, moved)
    actor = page.evaluate('id => viewer.effectRoots.get(id).userData.source.actor', fx)
    assert page.evaluate('a => viewer.editState().overrides.some(o => o.target.actor === a && o.location)', actor)
    blur(); page.keyboard.press('Control+z')
    assert not state(fx)['moved'] and state(fx)['at'] == start
    # Delete, undone
    page.evaluate('id => viewer.pickEffect(id)', fx); blur()
    page.keyboard.press('Delete')
    assert state(fx)['deleted'] and not state(fx)['visible']
    page.keyboard.press('Control+z')
    assert not state(fx)['deleted'] and state(fx)['visible']
    # a copy pasted: a copy of the effect, said as one
    roots = 'viewer.effectRoots.size'
    base = page.evaluate(roots)
    page.evaluate('id => viewer.pickEffect(id)', fx); blur()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.55
    page.keyboard.press('Control+c')
    assert 'Copied 1 effect' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.effectRoots.size > n', arg=base)
    copy = page.evaluate('viewer.gizmo.active')
    assert copy.startswith('effect-added:') and state(copy)['added'] and state(copy)['kind'] == 'effect', copy
    assert page.evaluate('id => viewer.effectRoots.get(id).userData.source.added.from.actor', copy) == actor
    blur(); page.keyboard.press('Control+z')
    assert page.evaluate(roots) == base
    page.keyboard.press('Shift+X')
    assert not page.evaluate('viewer.effectsOn()')
    # the normal view's switch: effects drawn and picked with pieces; a piece and an effect grouped move together
    page.evaluate('viewer.setNormalEffects(true)')
    assert page.evaluate('viewer.normalEffects()') and page.evaluate('viewer.effectMarkers().length') > 0 and not page.evaluate('viewer.effectsOn()')
    piece = page.evaluate("""[...viewer.roots.values()].find(r => r.visible && !r.userData.deleted && !r.userData.source.hidden
        && !r.userData.source.environment && !r.userData.source.cover && !r.userData.source.stream && r.userData.source.layer === 'base'
        && r.userData.source.actorClass === 'XComLevelActor')?.userData.source.id ?? null""")
    if piece:
        page.evaluate('id => viewer.select(id)', piece)
        page.evaluate('id => viewer.pickEffect(id, true)', fx)
        assert not page.evaluate('viewer.effectsOn()') and sorted(page.evaluate('viewer.gizmo.picks().ids')) == sorted([piece, fx])
        blur(); page.keyboard.press('Control+g')
        group = page.evaluate('viewer.editState().groups')
        assert len(group) == 1 and len(group[0]['members']) == 2, group
        start = state(fx)['at']
        page.evaluate('id => viewer.select(id)', piece)
        assert sorted(page.evaluate('viewer.gizmo.selection().map(r => r.userData.source.id)')) == sorted([piece, fx])
        drag(96)
        assert abs(state(fx)['at'][0] - start[0] - 96) < 0.01, (start, state(fx))
        blur(); page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
        assert state(fx)['at'] == start and not page.evaluate('viewer.editState().groups')
    # an effect a piece carries follows it; Keep where it is keeps it where the map has it
    carried = page.evaluate("""(() => { const own = r => [...viewer.roots.values()].find(p => p.userData.source.actor === r.userData.source.carriedBy
        && !p.userData.source.added && !p.userData.deleted);
      const r = [...viewer.effectRoots.values()].find(r => r.userData.source.carriedBy && !r.userData.source.landingActor
        && !r.userData.source.stream && r.visible && own(r));
      return r ? [r.userData.source.id, own(r).userData.source.id] : null; })()""")
    if carried and not state(carried[0])['viewOnly']:
        effect, carrier = carried
        start = state(effect)['at']
        page.evaluate('id => viewer.select(id)', carrier)
        drag(96)
        assert abs(state(effect)['at'][0] - start[0] - 96) < 0.5, (start, state(effect))
        page.evaluate('id => viewer.pickEffect(id)', effect)
        assert page.locator('#effectStay').is_visible()
        page.locator('#effectStay').click()
        kept = state(effect)
        assert kept['stays'] and max(abs(a - b) for a, b in zip(kept['at'], start)) < 0.01, (start, kept)
        held = page.evaluate('id => viewer.effectRoots.get(id).userData.source.actor', effect)
        assert page.evaluate("a => viewer.editState().overrides.some(o => o.target.actor === a && o.effect?.follow === 'none')", held)
        blur(); page.keyboard.press('Control+z')
        assert not state(effect)['stays'] and abs(state(effect)['at'][0] - start[0] - 96) < 0.5
        page.keyboard.press('Control+z')
        assert state(effect)['at'] == start
        # a copy of the carrier carries a copy of the effect, drawn as its own marker (the view threw on it before)
        pieces = page.evaluate('viewer.roots.size')
        page.evaluate('id => viewer.select(id)', carrier); blur()
        page.keyboard.press('Control+c')
        page.mouse.move(cx, cy); page.keyboard.press('Control+v')
        page.wait_for_function('viewer.placing()?.ghost.visible')
        page.mouse.click(cx, cy)
        page.wait_for_function('n => viewer.roots.size > n', arg=pieces)
        page.evaluate('viewer.setEffectsShown(true)')
        assert any(m['derived'] and m['id'] == effect for m in page.evaluate('viewer.effectMarkers()'))
        page.evaluate('viewer.setEffectsShown(false)')
        blur(); page.keyboard.press('Control+z')
        assert page.evaluate('viewer.roots.size') == pieces
    page.evaluate('s => { viewer.select(null); viewer.setNormalEffects(false); viewer.gizmo.setSnap(s); }', snap)
    assert page.evaluate(edits) == depth and not page.evaluate('viewer.effectMarkers().length')
    page.evaluate('id => viewer.select(id)', held)


def check_effects_box(page):
    """Box select and effects (effects and sounds plan, FX3b): in the normal view the box takes pieces only until the
    Normal button's Effects and sounds switch is on, then the effects and sounds inside with them, counted in the
    bar; in the Effects view it takes markers only and the view stays; Select all of a kind takes every effect of a
    picked one's particle system, in the box where one is drawn. Nothing of it is an edit."""
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"):
        return skip('effects', 'the effect box: needs a map (not a preview) of export 28 or later', whole=True)
    held = page.evaluate('viewer.gizmo.active')
    state = page.evaluate('viewer.projectState()')
    page.evaluate('viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(true)')
    fx = page.evaluate("""(() => { viewer.effectMarkers(); const all = [...viewer.effectRoots.values()].filter(r => r.visible && !r.userData.source.stream
        && r.userData.source.kind === 'effect' && r.userData.source.system && !viewer.effectState(r.userData.source.id).viewOnly);
      const by = new Map(); for (const r of all) by.set(r.userData.source.system, (by.get(r.userData.source.system) ?? 0) + 1);
      const r = all.find(r => by.get(r.userData.source.system) > 1) ?? all[0];
      return r ? { id: r.userData.source.id, at: viewer.effectState(r.userData.source.id).at, same: by.get(r.userData.source.system) } : null; })()""")
    if not fx:
        page.evaluate('viewer.setNormalEffects(false)'); page.evaluate('id => viewer.select(id)', held); return
    at = fx['at']
    around = lambda r: [at[0] - r, at[1] - r, at[2] - r, at[0] + r, at[1] + r, at[2] + r]
    wide = around(400)
    # switch off: the box holds pieces only
    page.evaluate('viewer.setNormalEffects(false)')
    page.evaluate('box => viewer.setPickBox(box)', wide)
    assert fx['id'] not in page.evaluate('viewer.pickHits()')
    # switch on: the effect is inside, and the bar counts it (the markers drawn first: a frame draws them otherwise)
    page.evaluate('viewer.setNormalEffects(true); viewer.effectMarkers()')
    page.evaluate('box => viewer.setPickBox(box)', wide)
    hits = page.evaluate('viewer.pickHits()')
    assert fx['id'] in hits, hits
    words = page.locator('#boxBarText').inner_text()
    assert re.search(r'\d+ effects?\b', words) and words.endswith(' inside'), words
    page.keyboard.press('Enter')
    assert fx['id'] in page.evaluate('viewer.gizmo.picks().ids') and page.evaluate('viewer.pickBox()') is None
    assert not page.evaluate('viewer.effectsOn()')
    # the Effects view: markers only, and the view stays
    page.evaluate('viewer.select(null); viewer.setEffectsShown(true)')
    page.keyboard.press('t')
    assert page.evaluate('viewer.pickTool()') and page.evaluate('viewer.effectsOn()')
    page.keyboard.press('Escape')
    page.evaluate('box => viewer.setPickBox(box)', wide)
    hits = page.evaluate('viewer.pickHits()')
    assert fx['id'] in hits and all(page.evaluate('id => viewer.effectRoots.has(id)', h) for h in hits), hits
    assert 'piece' not in page.locator('#boxBarText').inner_text()
    page.locator('#boxTake').click()
    picked = page.evaluate('viewer.gizmo.picks().ids')
    assert fx['id'] in picked and page.evaluate('viewer.effectsOn()'), picked
    page.evaluate('box => viewer.setPickBox(box)', [at[0], at[1], at[2] + 90000, at[0] + 10, at[1] + 10, at[2] + 90010])
    assert page.locator('#boxBarText').inner_text() == 'No effect or sound inside'
    page.locator('#boxCancel').click()
    # Select all of a kind: every drawn effect of the same system; with a box, those inside
    page.evaluate('id => { viewer.select(null); viewer.pickEffect(id); }', fx['id'])
    button = page.locator('#effectKind')
    if fx['same'] > 1:
        assert button.is_enabled() and f"({fx['same']})" in button.inner_text(), button.inner_text()
        button.click()
        assert len(page.evaluate('viewer.gizmo.picks().ids')) == fx['same']
        page.evaluate('id => { viewer.select(null); viewer.pickEffect(id); }', fx['id'])
        page.evaluate('box => viewer.setPickBox(box)', around(6))
        assert 'in box (1)' in button.inner_text(), button.inner_text()
        page.locator('#boxCancel').click()
    page.evaluate('viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(false)')
    assert page.evaluate('viewer.projectState()') == state
    page.evaluate('id => viewer.select(id)', held)


def check_flares(page):
    """Lens flares edited (effects and sounds plan, stage FX6b), on a map with a free one, in the Effects view. With
    the flare family held back (the server's default until its game check) a picked flare is view only and Delete says
    why. With it built (serve --family flare): its panel says what it is and offers no values; a move and Delete are
    undo steps and its override has a pose and nothing else; a copy pastes as a copy of the flare, saved with its kind
    and no values; box select takes it and counts it; Select all of a kind takes the flares of its template; a prefab
    of it holds a flare piece. Everything is undone at the end."""
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"):
        return skip('flares', 'lens flares: needs a map (not a preview) of export 28 or later', whole=True)
    flare = page.evaluate("""(() => { const all = [...viewer.effectRoots.values()].map(r => r.userData.source).filter(o => o.kind === 'flare' && !o.stream
        && o.layer === 'base' && o.template && o.can?.move && o.can?.delete && o.can?.copy);
      return all.length ? { id: all[0].id, actor: all[0].actor, template: all[0].template, same: all.filter(o => o.template === all[0].template).length } : null; })()""")
    if not flare: return skip('flares', 'the map has no lens flare that can be moved, copied and deleted', whole=True)
    held = page.evaluate('viewer.gizmo.active')
    before = page.evaluate('viewer.projectState()')
    blur = lambda: page.evaluate('document.activeElement?.blur()')
    state = lambda id: page.evaluate('id => { viewer.effectMarkers(); return viewer.effectState(id); }', id)
    drag = lambda dx: page.evaluate("""dx => { const c = viewer.gizmo.controls, p = c.object; c.dispatchEvent({type: 'mouseDown'});
        p.position.x += dx; p.updateMatrixWorld(true); c.dispatchEvent({type: 'objectChange'}); c.dispatchEvent({type: 'mouseUp'}); }""", dx)
    snap = page.evaluate('viewer.gizmo.snap')
    page.evaluate("viewer.gizmo.setSnap('off')")
    fx = flare['id']
    page.evaluate('viewer.select(null); viewer.setNormalEffects(false); viewer.setEffectsShown(true)')
    page.evaluate('id => viewer.pickEffect(id)', fx)
    assert page.evaluate('viewer.pickedEffect()') == fx
    assert page.locator('#effectTitle').text_content() == 'Lens flare: ' + flare['template'].split('.')[-1]
    assert 'Shows ' + flare['template'] in page.locator('#effectInfo').text_content()
    assert page.locator('#effectValues').is_hidden() and page.locator('#effectWaves').is_hidden()
    blur()
    done = lambda: (page.evaluate('s => { viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(false); viewer.gizmo.setSnap(s); }', snap),
                    page.evaluate('id => viewer.select(id)', held))
    if state(fx)['viewOnly']:
        assert not page.evaluate('viewer.families().families.flare.builds')
        page.keyboard.press('Delete')
        assert not state(fx)['deleted'] and 'lens flares are shown, not changed' in page.locator('#dragHint').inner_text()
        assert 'The gizmo' not in page.locator('#effectInfo').text_content()
        done(); return
    assert page.evaluate('viewer.families().families.flare.builds')
    assert 'The gizmo moves and turns it, Ctrl+C and Ctrl+V copy it, Delete deletes it' in page.locator('#effectInfo').text_content()
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    # a move: an override with a pose and nothing else; undone
    start = state(fx)['at']
    drag(96)
    moved = state(fx)
    assert moved['moved'] and abs(moved['at'][0] - start[0] - 96) < 0.01, (start, moved)
    override, = page.evaluate('a => viewer.editState().overrides.filter(o => o.target.actor === a)', flare['actor'])
    assert sorted(override) == ['location', 'rotation', 'target'], override
    assert page.locator('#effectInfo').text_content().startswith('Moved')
    blur(); page.keyboard.press('Control+z')
    assert not state(fx)['moved'] and state(fx)['at'] == start
    # Delete, undone
    page.evaluate('id => viewer.pickEffect(id)', fx); blur()
    page.keyboard.press('Delete')
    assert state(fx)['deleted'] and not state(fx)['visible']
    assert page.evaluate('a => viewer.editState().overrides.find(o => o.target.actor === a)', flare['actor']) == dict(
        target=dict(package=page.evaluate('viewer.data.name'), level='base', actor=flare['actor']), deleted=True)
    page.keyboard.press('Control+z')
    assert not state(fx)['deleted'] and state(fx)['visible']
    # a copy pasted: a copy of the flare, said and saved as one, with no values
    base = page.evaluate('viewer.effectRoots.size')
    page.evaluate('id => viewer.pickEffect(id)', fx); blur()
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.55
    page.keyboard.press('Control+c')
    assert 'Copied 1 lens flare' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.effectRoots.size > n', arg=base)
    copy = page.evaluate('viewer.gizmo.active')
    assert copy.startswith('effect-added:') and state(copy)['added'] and state(copy)['kind'] == 'flare', copy
    added, = page.evaluate('viewer.editState().added')
    assert sorted(added) == ['actor', 'from', 'id', 'kind', 'location', 'rotation'] and added['kind'] == 'flare', added
    assert added['from']['actor'] == flare['actor'] and added['actor'].startswith(flare['actor'] + '_copy')
    assert page.locator('#effectTitle').text_content().startswith('Lens flare: ')
    assert page.locator('#effectInfo').text_content().startswith('A copy of ' + flare['actor'].split('.')[-1])
    assert page.locator('#effectValues').is_hidden()
    # a prefab of the copy and its original holds two flare pieces, each where it stands
    page.evaluate('([a, b]) => { viewer.pickEffect(a); viewer.pickEffect(b, true); }', [fx, copy])
    records = page.evaluate("(() => { const r = viewer.prefabRecords(); return { pieces: r.pieces, left: r.left, counts: r.counts, donors: r.donors }; })()")
    assert records['left'] == [] and (records['counts']['flares'], records['counts']['pieces'], records['counts']['effects']) == (2, 0, 0), records
    assert all(sorted(p) == ['actor', 'from', 'kind', 'location', 'rotation'] and p['kind'] == 'flare' and p['from']['actor'] == flare['actor']
               for p in records['pieces']), records['pieces']
    # Select all of a kind: the flares of its template (the copy among them)
    page.evaluate('id => { viewer.select(null); viewer.pickEffect(id); }', fx)
    button = page.locator('#effectKind')
    assert button.is_visible() and f"({flare['same'] + 1})" in button.inner_text() and flare['template'].split('.')[-1] in button.get_attribute('title'), button.inner_text()      # (the kind's name is in its tooltip)
    button.click()
    assert len(page.evaluate('viewer.gizmo.picks().ids')) == flare['same'] + 1
    assert 'lens flare' in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
    # box select takes it and counts it
    page.evaluate('viewer.select(null)')
    at = state(fx)['at']
    page.evaluate('box => viewer.setPickBox(box)', [at[0] - 6, at[1] - 6, at[2] - 6, at[0] + 6, at[1] + 6, at[2] + 6])
    assert fx in page.evaluate('viewer.pickHits()')
    assert re.search(r'\d+ lens flares?\b', page.locator('#boxBarText').inner_text()), page.locator('#boxBarText').inner_text()
    page.locator('#boxCancel').click()
    page.evaluate('id => viewer.pickEffect(id)', copy)
    blur(); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.effectRoots.size') == base
    done()
    assert page.evaluate('viewer.gizmo.undoDepth()') == depth and page.evaluate('viewer.projectState()') == before


def check_library_flares(browser, url):
    """Lens flares of other maps and in a prefab (effects and sounds plan, stage FX6b), on URB_Bar against a test
    server started with --family flare, --projects and --builds scratch folders, its cache's library scanned at index
    10: All maps lists them under Lens flares, each row with the view's star and its template; one of another map
    (a hyperwave beacon's glare) is placed, its panel naming its map; it and one of Bar's own are saved as a prefab
    (two flare pieces, two donors), which is placed; the project is saved, reopened and built without baking, the
    step naming the lens flare brought."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409, 422))
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')"
                         " && Boolean(viewer.families()?.families?.flare?.builds)"):
        return skip('library-flares', 'needs URB_Bar (not a preview) on a server that builds lens flares', page, whole=True)
    page.evaluate("localStorage.removeItem('workshop.libraryView')")
    page.keyboard.press('p')
    choose(page, 'libScope', 'all')
    page.wait_for_function('viewer.library.ready()', timeout=60000)
    if not page.evaluate("viewer.library.entries().some(e => e.effect === 'flare')"):
        return skip('library-flares', 'the library lists no lens flare (scan it again: viewer.py library scan)', page, whole=True)
    page.locator('#libAllPlaceable').uncheck()
    page.locator('#libAllKind').select_option('flares')
    shown = page.evaluate("viewer.library.shown().map(e => ({ effect: e.effect, kind: e.kind, blocked: e.blocked, name: e.name }))")
    assert len(shown) > 10 and all(e['effect'] == 'flare' and e['kind'] == 'flare:Lens flare' for e in shown), shown[:3]
    assert re.match(r'Lens flares \(\d+\)', page.locator('#libAllKind option:checked').inner_text())
    # one that rides on another actor is listed and can't be placed
    assert any(e['blocked'] == 'unavailable' for e in shown)
    page.locator('#libAllFilter').fill('LF_Hyperwave_Beacon')
    key = page.evaluate("viewer.library.shown().find(e => e.effect === 'flare' && e.source.package !== 'URB_Bar')?.key")
    assert key
    entry = page.evaluate('k => viewer.library.entry(k)', key)
    row = page.locator(f'#libAllList .libitem[data-key="{key}"]')
    row.wait_for()
    page.wait_for_function("k => document.querySelector(`#libAllList .libitem[data-key=\"${k}\"] canvas`)?.dataset.drawn", arg=key)
    assert 'Lens flare · FX_Lens_Flares' in row.inner_text() and 'Flare template: FX_Lens_Flares.LF_Hyperwave_Beacon' in row.get_attribute('title'), row.inner_text()
    count = page.evaluate('viewer.effectRoots.size')
    row.click()
    page.wait_for_function('viewer.placing()', timeout=60000)
    box = page.locator('#viewport > canvas').bounding_box()
    x, y = box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.5
    page.mouse.move(x, y)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(x, y)
    page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")
    assert page.evaluate('viewer.effectRoots.size') == count + 1 and page.evaluate('viewer.effectsOn()')
    added, = page.evaluate('viewer.editState().added')
    assert (added['kind'], added['from']['package']) == ('flare', entry['source']['package']) and 'flare' not in added and 'components' not in added, added
    page.keyboard.press('p')
    foreign = page.evaluate("[...viewer.effectRoots.values()].find(r => r.userData.source.added).userData.source.id")
    page.evaluate('id => viewer.pickEffect(id)', foreign)
    info = page.locator('#effectPanel').inner_text()
    assert f"of {entry['source']['package']}" in info and 'with the flare template it needs' in info, info
    # it and one of Bar's own as a prefab: two flare pieces, two donors
    own = page.evaluate("[...viewer.effectRoots.values()].map(r => r.userData.source).find(o => o.kind === 'flare' && !o.added && !o.stream && o.can?.copy).id")
    page.evaluate('([a, b]) => { viewer.pickEffect(a); viewer.pickEffect(b, true); }', [foreign, own])
    records = page.evaluate("(() => { const r = viewer.prefabRecords(); return { pieces: r.pieces, left: r.left, counts: r.counts, donors: r.donors }; })()")
    assert records['left'] == [] and records['counts']['flares'] == 2 and records['counts']['pieces'] == 0, records
    assert sorted(d['package'] for d in records['donors']) == sorted(['URB_Bar', entry['source']['package']])
    saved = page.evaluate("n => viewer.savePrefab(n).then(s => ({ id: s.id, revision: s.revision }))", f'Smoke flares {RUN}')
    listed = page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs']
    prefab, = [p for p in listed if p['id'] == saved['id']]
    assert (prefab['pieces'], prefab['effects'], prefab['sounds'], prefab['flares']) == (0, 0, 0, 2), prefab
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 5 and all(sorted(p) == ['actor', 'from', 'kind', 'location', 'rotation'] and p['kind'] == 'flare' for p in doc['pieces']), doc['pieces']
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    page.wait_for_selector('#prefabList .libitem')
    item = page.locator('#prefabList .libitem', has_text=f'Smoke flares {RUN}')
    assert '2 lens flares' in item.inner_text(), item.inner_text()
    fxs = page.evaluate('viewer.effectRoots.size')
    item.click()
    page.wait_for_function('viewer.placing()?.fromList', timeout=180000)
    px, py = box['x'] + box['width'] * 0.6, box['y'] + box['height'] * 0.6
    page.mouse.move(px, py)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(px, py)
    page.wait_for_function('n => viewer.effectRoots.size === n + 2', arg=fxs)
    added = page.evaluate('viewer.editState().added')
    assert [a['kind'] for a in added] == ['flare'] * 3 and sorted({a['from']['package'] for a in added}) == sorted(['URB_Bar', entry['source']['package']]), added
    page.keyboard.press('p')
    page.evaluate('viewer.pickEffect(null)')
    state = page.evaluate('viewer.projectState()')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Library flares smoke {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=120000)
    assert page.evaluate('viewer.projectState()') == state and not any(page.evaluate('viewer.project().carried').values())
    assert page.evaluate("[...viewer.effectRoots.values()].filter(r => r.userData.source.added && r.userData.source.kind === 'flare').length") == 3
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=600000)
    assert page.locator('#buildTitle').inner_text().startswith(f'Built Library flares smoke {RUN}'), page.locator('#buildModal').inner_text()
    steps = page.locator('#buildSteps').inner_text()
    assert f"1 lens flare from {entry['source']['package']}" in steps, steps
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    donor, = build['package']['donors']
    assert build['state'] == 'built' and donor['map'] == entry['source']['package'] and donor['effects'] == 1, build['package']
    page.locator('#buildClose').click()
    page.evaluate('id => viewer.prefabApi.remove(id)', saved['id'])
    assert not errors, errors
    page.close()


def check_likeness(page):
    """The likeness (effects and sounds plan, FXV2; export 29): every effect the map has and the page can draw is
    drawn in the normal view, with no marker shown, stepped while it is in the picture; the picture round a framed
    effect differs with View options' Effects as they look on and off; switched off nothing is drawn or stepped, and
    the choice is kept; a deleted effect's likeness goes and Ctrl+Z brings it back; nothing of it is an edit. Gives
    the frame time with and without it."""
    if page.evaluate("!(viewer.data.exporterVersion >= 29) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"):
        return skip('likeness', 'needs a map (not a preview) of export 29 or later', whole=True)
    held = page.evaluate('viewer.gizmo.active')
    state = page.evaluate('viewer.projectState()')
    page.evaluate('viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(false); viewer.setLikeness(true)')
    if page.locator('#scenery').is_visible(): choose(page, 'scenery', 'full')
    page.evaluate('viewer.frame()')
    page.wait_for_timeout(1500)     # (the likenesses drawn a while, their textures read, before the frame time)
    like = lambda: page.evaluate('viewer.likenessState()')
    can = page.evaluate("""[...viewer.effectRoots.values()].filter(r => r.userData.source.kind === 'effect' && !r.userData.source.stream
        && r.userData.source.startsOn !== false && viewer.data.effectSystems[r.userData.source.system]?.emitters.some(e => e.draw)).map(r => r.userData.source.id)""")
    now = like()
    assert now['on'] and not page.evaluate('viewer.effectMarkers().length')
    if not can:
        assert now['effects'] == 0
        page.evaluate('id => viewer.select(id)', held); return None
    assert now['effects'] >= len(can), now      # (seen whole from afar, a large map's are too small to step)
    assert page.locator('#likenessToggle').is_checked()

    def frame_time():
        return page.evaluate("""() => new Promise(done => { let n = 0, t0 = performance.now(); const tick = () => { if (++n === 60) done((performance.now() - t0) / 60); else requestAnimationFrame(tick); }; requestAnimationFrame(tick); })""")
    with_it = frame_time()
    # one effect close: the picture with the likeness is not the picture without (a system that spawns seldom, as far
    # traffic does, may show nothing for a while: the next is tried)
    ranked = page.evaluate("""ids => ids.map(id => viewer.effectRoots.get(id).userData.source).sort((a, b) =>
        (viewer.data.effectSystems[b.system].emitters.filter(e => e.draw).length) - (viewer.data.effectSystems[a.system].emitters.filter(e => e.draw).length))
        .filter((o, i, all) => all.findIndex(x => x.system === o.system) === i).map(o => o.id)""", can)
    box = page.locator('#viewport > canvas').first.bounding_box()
    clip = dict(x=box['x'] + box['width'] / 2 - 200, y=box['y'] + box['height'] / 2 - 200, width=400, height=400)
    without = seen = target = None
    for target in ranked[:6]:
        page.evaluate('viewer.setLikeness(true)')
        page.evaluate('id => { viewer.setEffectsShown(true); viewer.pickEffect(id); }', target)
        page.keyboard.press('f')
        page.wait_for_timeout(300)      # (the camera framed on it drawn, before its pictures)
        page.evaluate('viewer.setEffectsShown(false)')
        page.wait_for_function('id => viewer.likenessState().drawn.includes(id)', arg=target)     # (stepped in the picture)
        assert target in like()['drawn'], like()
        page.evaluate('viewer.setLikeness(false)')
        page.wait_for_function('() => { const s = viewer.likenessState(); return !s.on && s.effects === 0 && s.particles === 0; }')
        off = like()
        assert not off['on'] and off['effects'] == 0 and off['particles'] == 0, off
        assert not page.locator('#likenessToggle').is_checked() and page.evaluate("localStorage.getItem('workshop.likeness')") == '0'
        hidden = page.screenshot(clip=clip)
        for _ in range(5):                                   # (the camera's glide to the effect may still be ending)
            again = page.screenshot(clip=clip)
            if again == hidden: break
            hidden = again; page.wait_for_timeout(400)
        assert page.screenshot(clip=clip) == hidden          # (a still picture without it)
        without = without or frame_time()
        page.evaluate('viewer.setLikeness(true)')
        page.wait_for_function('n => viewer.likenessState().effects >= n', arg=len(can))
        assert like()['effects'] >= len(can) and page.evaluate("localStorage.getItem('workshop.likeness')") == '1'
        for _ in range(12):                                  # (its textures and meshes are read first)
            if page.screenshot(clip=clip) != hidden: seen = target; break
            page.wait_for_timeout(250)
        if seen: break
    assert seen, 'no likeness changes anything in the picture'
    # a deleted effect is not drawn; Ctrl+Z draws it again (where the editor changes effects)
    page.evaluate('id => { viewer.setEffectsShown(true); viewer.pickEffect(id); }', target)
    if not page.evaluate('id => viewer.effectState(id).viewOnly', target):
        page.evaluate('document.activeElement?.blur()')
        page.keyboard.press('Delete')
        page.wait_for_function('([id, n]) => { const s = viewer.likenessState(); return !s.drawn.includes(id) && s.effects < n; }',
                               arg=[target, now['effects']])
        assert target not in like()['drawn'] and like()['effects'] < now['effects'], like()      # (its linked effects go with it)
        page.keyboard.press('Control+z')
        page.wait_for_function('n => viewer.likenessState().effects === n', arg=now['effects'])
        assert like()['effects'] == now['effects']
    page.evaluate('viewer.select(null); viewer.setEffectsShown(false)')
    assert page.evaluate('viewer.projectState()') == state
    page.evaluate('viewer.frame()')
    page.evaluate('id => viewer.select(id)', held)
    return dict(effects=now['effects'], particles=now['particles'], frameWith=round(with_it, 2), frameWithout=round(without, 2))


# what a check makes go wrong on purpose (a refused request it asks for): left out of the run's errors
EXPECTED = set()


def check_wave_preview(page):
    """The Effects view's Wave preview (effects and sounds plan, FX2; /maps/<id>/wave.ogg, audio.py): a click on a
    sound's Play plays its wave, decoded by the browser at the length the export gives; a seek moves it and it lets go
    at its end; Stop, Escape and picking something else stop it; an id the map doesn't list shows the server's reason."""
    sound = page.evaluate("(viewer.data.sounds ?? []).find(s => (s.waves ?? []).some(w => viewer.data.soundWaves?.[w]?.playable))?.id ?? null")
    if not sound: return skip('effects', 'the Wave preview: the map has no sound with a playable wave')
    page.evaluate(f'viewer.pickEffect({sound!r})')
    wave = page.evaluate(f"viewer.data.sounds.find(s => s.id === {sound!r}).waves.find(w => viewer.data.soundWaves[w].playable)")
    button = page.locator('#effectWaves button[data-wave]').filter(has_text='Play').first
    assert page.locator('#effectWaves').is_visible() and button.get_attribute('data-wave') == wave
    playing = "viewer.wave() && ['playing', 'failed'].includes(viewer.wave().state)"
    button.click()
    page.wait_for_function(playing, timeout=15000)
    state = page.evaluate('viewer.wave()')
    assert state['state'] == 'playing' and state['wave'] == wave and state['volume'] == 0.6, state
    seconds = page.evaluate(f'viewer.data.soundWaves[{wave!r}].seconds')
    if seconds and state['duration']: assert abs(state['duration'] - seconds) < 0.1, (state, seconds)
    stop = page.locator(f'#effectWaves button[data-wave]').first
    assert stop.inner_text() == 'Stop'
    page.evaluate(f"viewer.seekWave({max(0, (state['duration'] or 0) - 0.5)})")
    page.wait_for_function('viewer.wave() === null', timeout=10000)     # the end lets it go
    assert stop.inner_text() == 'Play'
    stop.click()
    page.wait_for_function(playing, timeout=15000)
    stop.click()                                                        # Stop
    assert page.evaluate('viewer.wave()') is None and stop.inner_text() == 'Play'
    stop.click()
    page.wait_for_function(playing, timeout=15000)
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.wave()') is None and page.evaluate('viewer.pickedEffect()') is None
    page.evaluate(f'viewer.pickEffect({sound!r})')
    bogus = page.evaluate("viewer.data.name + '|No.Such.Wave'")
    page.evaluate(f"viewer.playWave({bogus!r})")
    page.wait_for_function('viewer.wave()?.why', timeout=10000)
    assert 'not one of this map' in page.evaluate('viewer.wave().why')
    refused = page.evaluate("w => location.origin + '/maps/' + encodeURIComponent(viewer.mapId) + '/wave.ogg?id=' + encodeURIComponent(w)", bogus)
    # another map's wave (a copy of its sound, FX4) is asked of the library, which says what it can't find
    page.evaluate("viewer.playWave('URB_NoSuchMap|No.Such.Wave')")
    page.wait_for_function("viewer.wave()?.wave === 'URB_NoSuchMap|No.Such.Wave' && viewer.wave()?.why", timeout=10000)
    assert 'URB_NoSuchMap' in page.evaluate('viewer.wave().why'), page.evaluate('viewer.wave()')
    elsewhere = page.evaluate("location.origin + '/library/wave.ogg?' + new URLSearchParams({ package: 'URB_NoSuchMap', id: 'URB_NoSuchMap|No.Such.Wave' })")
    EXPECTED.update({'Failed to load resource: the server responded with a status of 404 (Not Found)', f'HTTP 404: {refused}',
                     f'HTTP 404: {elsewhere}'})
    page.evaluate('viewer.stopWave(); viewer.pickEffect(null)')


def check_streams(page):
    """The packages the map's missions stream (export 13): their pieces show with the chosen mission only, LWR's hidden
    helpers hidden by default (Hide patch helpers) and as a wireframe when it is unticked, and a streamed piece can be
    inspected but never moved, deleted or saved."""
    if page.evaluate('!viewer.data.streams || Boolean(viewer.data.preview)'):
        return skip('streams', 'the map (or preview) has no streamed packages', whole=True)
    shown = """() => [...viewer.roots.values()].filter(r => r.userData.source.layer === 'stream' && r.visible)
                 .map(r => r.userData.source.stream)"""
    def consistent():
        streams = set(page.evaluate('viewer.data.missions[viewer.mission()]?.streams ?? []'))
        assert set(page.evaluate(shown)) <= streams, (page.evaluate(shown), streams)
    consistent()
    helpers = """() => [...viewer.roots.values()].filter(r => r.userData.source.layer === 'stream' && r.userData.source.hidden
                   && r.visible).length"""
    if page.evaluate("[...viewer.roots.values()].some(r => r.userData.source.layer === 'stream' && r.userData.source.hidden)"):
        assert page.locator('#hideHelpers').is_checked() and page.evaluate(helpers) == 0
        check_option(page, 'hideHelpers', False)
        assert page.evaluate(helpers) > 0
        check_option(page, 'hideHelpers', True)
        assert page.evaluate(helpers) == 0
    missions = page.evaluate('viewer.data.missions.length')
    assert page.locator('#missionPick').is_visible() == (missions > 1)
    if missions > 1:
        for i in list(range(missions)) + [0]:
            page.locator('#mission').select_option(str(i))
            assert page.evaluate('viewer.mission()') == i
            consistent()
        assert 'mission=' not in page.url
    piece = page.evaluate("[...viewer.roots.values()].find(r => r.userData.source.layer === 'stream' && r.visible)?.userData.source.id")
    if not piece: return skip('streams', 'a streamed piece edited: none is drawn')
    before = page.evaluate('viewer.changes().total')
    page.evaluate('id => viewer.select(id)', piece)
    assert page.evaluate('viewer.gizmo.selection().length') == 0
    assert page.locator('#posX').is_disabled() and page.locator('#editDelete').is_disabled()
    assert 'not editable' in ' '.join(page.locator('#details .chip').all_text_contents())
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.changes().total') == before
    assert not any(o['target']['level'] == 'stream' for o in page.evaluate('viewer.editState().overrides'))
    page.evaluate('viewer.select(null)')
    # a mission's object moves with its group (mission types plan, Part E): its gizmo on its marker, the group's parts
    # saved as stream overrides, its streamed mesh drawn where it stands; one undo step puts it all back
    found = page.evaluate("""() => {
      for (const [k, m] of (viewer.data.missions ?? []).entries())
        for (const s of m.streams ?? []) {
          const o = (viewer.data.streams[s]?.missionObjects ?? []).find(x => x.group && ['powerNode', 'bomb', 'capturePoint'].includes(x.kind));
          if (o) return { mission: k, stream: s, actor: o.actor, parts: viewer.data.streams[s].missionObjects.filter(x => x.group === o.group).length };
        }
      return null; }""")
    if not found: return skip('streams', 'a mission object\'s group: no streamed package has one')
    page.locator('#mission').select_option(str(found['mission'])) if missions > 1 else None
    normal = page.evaluate('viewer.normalSpawns()')
    page.evaluate('viewer.setNormalSpawns(true)')       # (the Normal button's Spawn points and objectives)
    page.evaluate('o => viewer.setPickedMission({ stream: o.stream, actor: o.actor })', found)
    assert page.evaluate('viewer.missionGizmo().enabled') and page.locator('#spawnPanel').is_visible()
    at = page.evaluate('viewer.missionGizmo().at')
    assert page.evaluate('o => viewer.moveMissionGroup(o.stream, o.actor, [96, 0, 0])', found)
    moved = page.evaluate("viewer.editState().overrides.filter(o => o.target.level === 'stream')")
    assert len(moved) == found['parts'] and all(o['target']['package'] == found['stream'] for o in moved), moved
    assert abs(page.evaluate('viewer.missionGizmo().at')[0] - (at[0] + 96)) < 1e-3
    assert 'mission object' in page.locator('#editCount').inner_text()
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.missionMoves().length') == 0 and page.evaluate('viewer.changes().total') == before
    page.evaluate('viewer.setPickedMission(null)')
    page.evaluate('on => viewer.setNormalSpawns(on)', normal)
    if missions > 1: page.locator('#mission').select_option('0')


def check_spawns_view(page):
    """The Spawns view and the Normal button's switch (editor spawns implementation plan, SP3): the view entered with
    the switch off picks a pod through the walls by a click, never a piece; back in Normal with the switch on a click
    picks a marker ahead of the piece behind it; with the switch off no marker picks and no gizmo is left. On a map
    with a council bomb record: one marker for the bomb and one for each power node, none on another record and
    nothing left picked; the bomb and a node moved apart and undone, the bomb's group with its helper."""
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview && Array.isArray(viewer.data.spawns)'):
        return skip('spawns', 'the Spawns view: needs a map (not a preview) of an export with spawn points', whole=True)
    normal = page.evaluate('viewer.normalSpawns()')
    page.evaluate('viewer.setNormalSpawns(false); viewer.select(null)')
    pod = page.evaluate("(viewer.spawns().find(s => s.kind === 'pod' && s.layer === 'base') ?? null)")
    if pod:
        page.evaluate('k => { const s = viewer.spawns().find(x => x.key === k); viewer.showSpawn(s.actor, null); viewer.pickSpawn(null); viewer.setNormalSpawns(false); }', pod['key'])
        page.wait_for_timeout(200)      # (a frame drawn where showSpawn put the camera, before the screen point)
        pod = page.evaluate('k => viewer.spawns().find(x => x.key === k)', pod['key'])
        x, y = pod['screen']
        page.evaluate('document.activeElement && document.activeElement.blur()')
        page.keyboard.press('Shift+U')
        assert page.evaluate('viewer.spawnsOn()') and page.locator('#editSpawns').get_attribute('aria-pressed') == 'true'
        page.mouse.click(x, y)
        assert page.evaluate('viewer.pickedSpawn()') == pod['key'] and page.evaluate('viewer.gizmo.active') is None
        assert page.locator('#spawnPanel').is_visible() and page.locator('#spawnTitle').text_content().startswith('Pod')
        assert 'In the game' in page.locator('#spawnInfo').inner_text()
        page.keyboard.press('Shift+N')
        assert not page.evaluate('viewer.spawnsOn()') and not page.evaluate('viewer.spawnLayer.visible')
        assert page.locator('#spawnPanel').is_hidden()
        page.evaluate('viewer.setNormalSpawns(true)')
        assert page.evaluate('viewer.spawnLayer.visible') and page.locator('#normalSpawns').is_checked()
        page.mouse.click(x, y)
        assert page.evaluate('viewer.pickedSpawn()') == pod['key'] and page.evaluate('viewer.gizmo.active') is None
        page.evaluate('viewer.setNormalSpawns(false)')
        assert page.evaluate('viewer.pickedSpawn()') is None and not page.evaluate('viewer.missionGizmo().enabled')
        page.mouse.click(x, y)
        assert page.evaluate('viewer.pickedSpawn()') is None
        page.evaluate('viewer.select(null)')
    bomb_record = page.evaluate("viewer.headerMissions().find(m => m.label === 'Council bomb')?.value ?? null")
    if bomb_record is None:
        page.evaluate('on => viewer.setNormalSpawns(on)', normal)
        return
    page.evaluate('viewer.setSpawnsShown(true)')
    page.locator('#mission').select_option(bomb_record)
    marked = page.evaluate("viewer.spawns().filter(s => s.marked && ['bomb', 'powerNode'].includes(s.kind)).map(s => s.kind)")
    assert sorted(marked) == ['bomb'] + ['powerNode'] * 8, marked
    bomb = page.evaluate("viewer.spawns().find(s => s.kind === 'bomb')")
    node = page.evaluate("viewer.spawns().find(s => s.kind === 'powerNode')")
    page.evaluate('k => viewer.pickSpawn(k)', bomb['key'])
    assert page.evaluate('viewer.missionGizmo().enabled')
    before = page.evaluate('viewer.changes().total')
    assert page.evaluate('b => viewer.moveMissionGroup(b.stream, b.actor, [288, 0, 0])', bomb)
    moved = page.evaluate("viewer.editState().overrides.filter(o => o.target.level === 'stream').map(o => o.target.actor.split('.').pop())")
    assert len(moved) == 11 and 'PointInSpace_0' in moved, moved
    assert page.evaluate('n => viewer.moveMissionGroup(n.stream, n.actor, [0, 96, 0])', node)
    assert page.evaluate("viewer.editState().overrides.filter(o => o.target.level === 'stream').length") == 16
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Control+z')
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.missionMoves().length') == 0 and page.evaluate('viewer.changes().total') == before
    # a project from before export 33 moved the bomb without its helper: opening it adds the helper's move
    page.evaluate('b => viewer.moveMissionGroup(b.stream, b.actor, [288, 0, 0])', bomb)
    fixed = page.evaluate("""() => { const all = viewer.missionMoves(); viewer.gizmo.undo();
      const without = new Map(all.filter(m => !m.actor.endsWith('PointInSpace_0')).map(m => [`${m.stream}|${m.actor}`, m]));
      const fix = viewer.bombHelperFix(without); return fix ? [...fix.values()].map(m => m.actor.split('.').pop()) : null; }""")
    assert fixed and len(fixed) == 11 and 'PointInSpace_0' in fixed, fixed
    abduction = page.evaluate("viewer.headerMissions().find(m => m.label === 'Abduction')?.value ?? null")
    if abduction is not None:
        page.evaluate('k => viewer.pickSpawn(k)', bomb['key'])
        page.locator('#mission').select_option(abduction)
        assert not page.evaluate("viewer.spawns().some(s => s.marked && ['bomb', 'powerNode'].includes(s.kind))")
        assert page.evaluate('viewer.pickedSpawn()') is None and not page.evaluate('viewer.missionGizmo().enabled')
    page.evaluate('viewer.setSpawnsShown(false)')
    page.locator('#mission').select_option('0')
    page.evaluate('on => viewer.setNormalSpawns(on)', normal)


def check_spawn_edits(page):
    """The spawn edits where the spawn family builds (editor spawns implementation plan, SP6 to SP8, and the Add
    panel's spawn points): every marker in a halo, the picked one's larger; a base pod moved a tile, turned a quarter
    by ] and given a value, an undo step each; Ctrl+D copies a plain pod a tile east, picked, and Delete takes the copy
    away; Delete deletes a base Meld point; the Add panel's entries, Escape cancelling a placing, and a pod placed by a
    click, whole tiles from its template; the drop-in rule's box ticked and undone; all of it undone back to as the
    map was."""
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview && Array.isArray(viewer.data.spawns)'):
        return skip('spawns', 'spawn edits: needs a map (not a preview) of an export with spawn points', whole=True)
    entries = page.evaluate('viewer.spawnAddEntries().map(e => e.name)')
    if not entries: return skip('spawns', 'spawn edits: the spawn family doesn\'t build on this server', whole=True)
    assert set(entries) <= {'Pod', 'Meld point', 'No-spawn volume'} and 'No-spawn volume' in entries, entries
    # a map with no no-spawn volume of its own (Act1_IntroLevel) offers a fresh one, which has no actor: the Add panel
    # opened on it threw before (18 November 2026)
    fresh = page.evaluate('''() => { const kept = viewer.data.spawns;
        viewer.data.spawns = kept.filter(o => o.kind !== 'noSpawn');
        try { return viewer.spawnAddEntries().find(e => e.spawnAdd === 'noSpawn')?.pkg ?? null; } finally { viewer.data.spawns = kept; } }''')
    assert fresh == "made from one of the map's volumes", fresh
    normal = page.evaluate('viewer.normalSpawns()')
    before = page.evaluate('viewer.changes().total')
    page.evaluate('viewer.select(null); viewer.pickSpawn(null); viewer.setSpawnsShown(true)')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    spawns = lambda: page.evaluate('viewer.spawns()')
    moves = lambda: page.evaluate('viewer.missionMoves()')
    halo = lambda key: page.evaluate('k => viewer.spawnLayer.children.find(m => m.userData.spawn === k)?.userData.halo?.scale.x ?? null', key)
    undo = lambda n=1: [page.keyboard.press('Control+z') for _ in range(n)]
    shown = page.evaluate('viewer.spawnLayer.children.filter(m => m.userData.spawn).map(m => m.userData.halo ? m.userData.halo.scale.x : null)')
    assert shown and all(s == 2.6 for s in shown), shown
    # multiplayer teams' starts get no marker; a no-spawn volume is drawn with its box
    mp = page.evaluate("(viewer.data.spawns ?? []).filter(o => o.kind === 'point' && [8, 9].includes(o.unitType)).map(o => o.actor)")
    assert not any(s['marked'] for s in spawns() if s['actor'] in mp)
    assert page.evaluate("viewer.spawnLayer.children.filter(m => m.userData.spawnBox).length") == \
        sum(1 for s in spawns() if s['kind'] == 'noSpawn' and s['marked'])
    # a plain pod: one Ctrl+D copies (a pod with a flag, a forced type or links isn't copied)
    pods = [s for s in spawns() if s['kind'] == 'pod' and s['layer'] == 'base']
    pod = copy = None
    for p in pods:
        page.evaluate('k => viewer.pickSpawn(k)', p['key'])
        page.keyboard.press('Control+d')
        if page.evaluate('viewer.pickedSpawn()') != p['key']:
            pod, copy = p, page.evaluate('viewer.pickedSpawn()')
            break
    if pod:
        c = next(s for s in spawns() if s['key'] == copy)
        assert c['layer'] == 'copy' and abs(c['at'][0] - pod['at'][0] - 96) < 1e-3 and abs(c['at'][1] - pod['at'][1]) < 1e-3, c
        assert halo(copy) > 2.6 and halo(pod['key']) == 2.6
        page.keyboard.press('Delete')
        assert not any(s['key'] == copy for s in spawns()) and not moves()
        # the pod moved a tile and given a value: two undo steps; a pod has no turn (its facing aims nothing), so
        # neither its panel nor ] turns it
        page.evaluate('k => viewer.pickSpawn(k)', pod['key'])
        assert page.evaluate('viewer.spawnEditShown()')
        assert page.locator('#spawnEdit button', has_text='Turn').count() == 0
        assert page.evaluate('p => viewer.moveMissionGroup(null, p.actor, [96, 0, 0])', pod)
        at = next(s for s in spawns() if s['key'] == pod['key'])['at']
        assert abs(at[0] - pod['at'][0] - 96) < 1e-3, at
        yaw = lambda: next(m for m in moves() if m['stream'] is None and m['actor'] == pod['actor'])['rotation'][1]
        was = yaw()
        page.keyboard.press(']')
        assert yaw() == was, (was, yaw())
        assert page.evaluate("a => viewer.editBaseSpawn(a, { spawn: { commander: true } }) || viewer.editBaseSpawn(a, { spawn: { commander: false } })", pod['actor'])
        assert page.evaluate('viewer.changes().total') > before
        undo(2)
        assert not moves(), moves()
    meld = next((s for s in spawns() if s['kind'] == 'meld' and s['layer'] == 'base'), None)
    if meld:
        page.evaluate('k => viewer.pickSpawn(k)', meld['key'])
        page.keyboard.press('Delete')
        assert [m.get('deleted') for m in moves() if m['actor'] == meld['actor']] == [True], moves()
        # (a deleted point shows only with the flyout's Deleted points switch)
        assert not next(s for s in spawns() if s['key'] == meld['key'])['marked']
        page.evaluate("viewer.setSpawnFilter('deleted', true)")
        assert next(s for s in spawns() if s['key'] == meld['key'])['marked']
        page.evaluate("viewer.setSpawnFilter('deleted', false)")
        undo()
        assert not moves()
    # a no-spawn volume: its east side's handle dragged two tiles out (whole tiles, one undo step), its arrows moving it
    # a tile and a level, Ctrl+D copying it a tile east with its size, its civilians tick off; four undo steps
    vol = next((s for s in spawns() if s['kind'] == 'noSpawn' and s['layer'] == 'base'), None)
    if vol:
        page.evaluate('a => viewer.showSpawn(a, null)', vol['actor'])
        page.evaluate("document.activeElement && document.activeElement.blur(); viewer.setNormalSpawns(false); viewer.setSpawnsShown(true)")
        page.evaluate('k => viewer.pickSpawn(k)', vol['key'])
        page.wait_for_timeout(100)      # (a frame drawn where showSpawn put the camera, before the handles' screen points)
        handles = page.evaluate('viewer.spawnVolumeHandles()')
        assert handles and sorted(handles) == ['x0', 'x1', 'y0', 'y1', 'z0', 'z1'], handles
        b0 = vol['box']
        mid = [(b0[1] + b0[4]) / 2, (b0[2] + b0[5]) / 2]
        a = page.evaluate('p => viewer.screenOf(p)', [b0[3], *mid])
        b = page.evaluate('p => viewer.screenOf(p)', [b0[3] + 192, *mid])
        h = handles['x1']
        # (the press takes the handle under its own point and the release keeps the box, in their listeners, which the
        # mouse calls wait for)
        page.mouse.move(*h)
        page.mouse.down(); page.mouse.move(h[0] + b[0] - a[0], h[1] + b[1] - a[1], steps=12); page.mouse.up()
        now = next(s for s in spawns() if s['key'] == vol['key'])['box']
        # (an edited box is kept to a thousandth of a unit: the map's -863.9998 is -864)
        assert all(abs(now[k] - b0[k] - (192 if k == 3 else 0)) < 1e-2 for k in range(6)), (b0, now)
        assert [m['box'] for m in moves() if m['actor'] == vol['actor']] == [now], moves()
        assert page.evaluate('v => viewer.moveMissionGroup(null, v.actor, [0, 96, 64])', vol)
        moved = next(s for s in spawns() if s['key'] == vol['key'])['box']
        assert moved == [now[0], now[1] + 96, now[2] + 64, now[3], now[4] + 96, now[5] + 64], moved
        page.keyboard.press('Control+d')
        c = next(s for s in spawns() if s['key'] == page.evaluate('viewer.pickedSpawn()'))
        assert c['layer'] == 'copy' and c['box'] == [moved[0] + 96, moved[1], moved[2], moved[3] + 96, moved[4], moved[5]], c
        assert page.evaluate("a => viewer.editBaseSpawn(a, { spawn: { civilians: false } })", vol['actor'])
        assert [m['spawn'] for m in moves() if m['actor'] == vol['actor']] == [{'civilians': False}]
        undo(4)
        assert not moves(), moves()
    # the Add panel's No-spawn volume: placed over whole tiles round the click
    page.evaluate('viewer.pickSpawn(null)')
    page.evaluate("viewer.startSpawnPlacing('noSpawn')")
    cx, cy = page.evaluate("(() => { const r = viewer.renderer.domElement.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    page.mouse.click(cx, cy)
    made = [m for m in moves() if m.get('copy')]
    assert len(made) == 1 and made[0]['copy']['kind'] == 'noSpawn', moves()
    origin = page.evaluate('viewer.data.tileGrid.origin')
    assert all(abs((made[0]['box'][k] - origin[k % 3]) / 96 - round((made[0]['box'][k] - origin[k % 3]) / 96)) < 1e-3 for k in (0, 1, 3, 4)), made
    undo()
    assert not moves()
    # the Add panel's spawn points: Escape cancels a placing; a click places a copy of the kind's template (a map with
    # no plain pod and no Meld point, as Act1_IntroLevel, has nothing more to place)
    if 'Pod' not in entries and 'Meld point' not in entries: return skip('spawns', 'the Add panel\'s spawn points: the map has no plain pod or Meld point to copy')
    kind = 'pod' if 'Pod' in entries else 'meld'
    page.evaluate('k => viewer.startSpawnPlacing(k)', kind)
    assert page.evaluate('viewer.spawnPlacing()') == kind
    page.keyboard.press('Escape')
    assert page.evaluate('viewer.spawnPlacing()') is None and not moves()
    page.evaluate('viewer.pickSpawn(null)')     # no picked point's arrows under the click
    page.evaluate('k => viewer.startSpawnPlacing(k)', kind)
    # the middle of the 3D view, where the camera looks at the map
    x, y = page.evaluate("(() => { const r = viewer.renderer.domElement.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    assert page.evaluate('([x, y]) => document.elementFromPoint(x, y) === viewer.renderer.domElement', [x, y])
    page.mouse.click(x, y)
    assert page.evaluate('viewer.spawnPlacing()') is None
    added = [m for m in moves() if m.get('copy')]
    assert len(added) == 1, moves()
    template = next(o for o in page.evaluate('viewer.data.spawns') if o['actor'] == added[0]['copy']['from'])
    steps = [(added[0]['location'][i] - template['location'][i]) / 96 for i in (0, 1)]
    assert all(abs(s - round(s)) < 1e-3 for s in steps), (added[0]['location'], template['location'])
    assert page.evaluate('viewer.pickedSpawn()') == next(s['key'] for s in spawns() if s['layer'] == 'copy')
    undo()
    assert not moves()
    # the drop-in rule's box (where the install has Long War's drop-in mutator)
    box = page.locator('#dropInsPlaced')
    if not box.is_disabled() and not box.is_checked():
        page.evaluate("() => { const b = document.getElementById('dropInsPlaced'); b.checked = true; b.dispatchEvent(new Event('change')); }")
        assert page.evaluate('viewer.projectSpawnRules()') == {'dropIns': 'placed'}
        page.evaluate('document.activeElement && document.activeElement.blur()')
        undo()
        assert page.evaluate('viewer.projectSpawnRules()') is None and not box.is_checked()
    assert page.evaluate('viewer.changes().total') == before
    page.evaluate('viewer.pickSpawn(null); viewer.setSpawnsShown(false)')
    page.evaluate('on => viewer.setNormalSpawns(on)', normal)


def check_project_menu(page):
    """The header's menus (Project first after the name, then Map; Build, Play and the Game menu; Settings) and the
    Save and Open dialogs opened and cancelled (nothing saved)."""
    assert page.evaluate("document.querySelector('header .brand').nextElementSibling.id") == 'projectButton'
    # the logo (logo.svg) drawn on the bar, the page's tab icon the same file, served as an SVG
    assert page.evaluate("(() => { const i = document.querySelector('header .brand img.logo'); return i.complete && i.naturalWidth > 0; })()")
    assert page.evaluate("document.querySelector('link[rel=icon]').getAttribute('href')") == 'logo.svg'
    assert page.evaluate("fetch('logo.svg').then(r => r.headers.get('content-type'))") == 'image/svg+xml'
    kept = page.evaluate('viewer.gizmo.active')
    page.evaluate('id => viewer.select(id)', kept or page.evaluate('[...viewer.roots.keys()][0]'))
    changes = page.evaluate('viewer.changes()')
    page.locator('#projectButton').click()
    assert page.locator('#projectMenu').is_visible()
    labels = [t.strip() for t in page.locator('#projectMenu .menuitems button:visible span').all_inner_texts()]
    project = page.evaluate('Boolean(viewer.project())')
    assert labels == ['Save', 'Save as…', 'Open…'] + (['Close project'] if project else []) + ['Manage projects…'], labels
    page.wait_for_function("document.querySelector('#projectRecent').childElementCount > 0")
    assert page.locator('#projectRecent .projectitem').count() <= 3
    page.keyboard.press('Escape')
    assert page.locator('#projectMenu').is_hidden()
    # the menu of the map that is open, next (the prefab menus plan): the map's name, on a whole map its settings,
    # missions, picture, grid and Clear map; then Open's two buttons, A map… and A prefab… with their counts, and New
    # prefab; no prefab's items. A map… opens the map browser and gives the focus back to the button
    assert page.evaluate("document.querySelector('#projectButton').nextElementSibling.id") == 'mapButton'
    assert page.locator('#mapButton small').inner_text().strip().lower() == 'map'
    page.locator('#mapButton').click()
    assert page.locator('#mapMenu').is_visible() and page.locator('#mapDialog').is_hidden()
    assert page.locator('#docHead').inner_text().strip().lower() == 'this map'
    assert page.locator('#docInfo strong').inner_text() == page.locator('#mapTitle').inner_text()
    if page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'):
        labels = [t.strip() for t in page.locator('#mapItems button:visible span').all_inner_texts()]
        assert labels == ['Map settings…', 'Missions…', 'Map picture…', 'Map grid', 'Clear map…'], labels
    assert page.locator('#prefabItems').is_hidden()
    assert [t.strip() for t in page.locator('.openpair button span').all_inner_texts()] == ['A map…', 'A prefab…']
    page.wait_for_function("/^[0-9]+ prefabs?$/.test(document.getElementById('openPrefabsCount').textContent)")
    assert page.locator('#openMapsCount').inner_text().endswith('maps')
    assert page.locator('#docNewPrefab').is_visible()
    page.locator('#openMaps').click()
    assert page.locator('#mapMenu').is_hidden()
    page.wait_for_selector('#mapDialog:not([hidden])')
    page.keyboard.press('Escape')
    assert page.locator('#mapDialog').is_hidden()
    assert page.evaluate('document.activeElement?.id') == 'mapButton'
    # Build and Play in the header, the Game menu on Play's arrow. Its Installs: the game install, the install plays
    # go to, how the game is started and what the editor has in it (or why they are not known)
    assert page.locator('#projectBuild').is_visible() and page.locator('#projectBuild').is_disabled() != project
    assert page.evaluate("document.querySelector('#playGroup').nextElementSibling.id") == 'settingsButton'
    page.locator('#playButton').click()
    assert page.locator('#playMenu').is_visible()
    labels = [t.strip() for t in page.locator('#playMenu .menuitems button:visible span').all_inner_texts()]
    assert labels == ['Test squad setup…', 'Game maps…'], labels
    page.wait_for_function("document.querySelectorAll('#installInfo dd').length === 4")
    assert page.locator('#installInfo dt').all_inner_texts() == ['Game', 'Plays in', 'Started', 'In the game']
    page.keyboard.press('Escape')
    assert page.locator('#playMenu').is_hidden()
    page.locator('#settingsButton').click()
    labels = [t.strip() for t in page.locator('#settingsMenu .menuitems button span').all_inner_texts()]
    assert labels == ['Game install and checks…', 'Cache everything…'], labels
    page.keyboard.press('Escape')
    # Ctrl+F is the browser's own now: the header has no find box
    assert page.locator('#search').count() == 0
    # Ctrl+O: the Open dialog over every map's projects; Escape closes it and leaves the selection alone.
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Control+o')
    page.wait_for_selector('#fileDialog:not([hidden])')
    assert page.locator('#fileTitle').inner_text() == 'Open project' and page.locator('#fileOk').inner_text() == 'Open'
    assert page.locator('#fileShow').input_value() == 'all' and not page.locator('#fileShow').is_disabled()
    page.wait_for_function("!document.querySelector('#fileList').textContent.includes('Reading')")
    assert page.locator('#fileFolder').inner_text()
    page.keyboard.press('Delete'); page.keyboard.press('Escape')
    assert page.locator('#fileDialog').is_hidden() and page.evaluate('viewer.gizmo.active') is not None
    assert page.evaluate('viewer.changes()') == changes
    if page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'):
        # Save as…: the Save dialog lists this map's projects only.
        page.locator('#projectButton').click()
        page.locator('#projectSaveAs').click()
        page.wait_for_selector('#fileDialog:not([hidden])')
        assert page.locator('#fileTitle').inner_text() == 'Save project' and page.locator('#fileShow').is_disabled()
        page.locator('#fileCancel').click()
        assert page.locator('#fileDialog').is_hidden()
    if not kept: page.evaluate('viewer.select(null)')


def check_squad(page, saves=False):
    """The Game menu (Play's arrow), just before Settings, and its Test squad setup (squad.js): the panel's list and unit editor, a kind
    change and what it cleared, an error for a name the game can't take, Escape and Cancel leaving the saved squad as
    it was, and the play dialog's squad line opening the panel over it. saves: the server's --squad is a scratch file,
    so the check also saves, sees a save from elsewhere refused with the draft kept, and puts the squad back."""
    assert page.evaluate("document.querySelector('#settingsButton').nextElementSibling.id") == 'notesButton'
    page.locator('#playButton').click()
    assert page.locator('#playMenu').is_visible()
    labels = [t.strip() for t in page.locator('#playMenu .menuitems button span').all_inner_texts()]
    assert labels[0] == 'Test squad setup…', labels
    page.wait_for_function("document.querySelector('#settingsSquadLine').textContent.startsWith('Squad')")
    page.locator('#settingsSquad').click()
    page.wait_for_selector('#squadDialog:not([hidden])')
    page.wait_for_function("document.querySelectorAll('#squadUnits li').length > 0")
    saved = page.evaluate("fetch('/squad.json').then(r => r.json())")
    units = page.locator('#squadUnits li').count()
    assert units == len(saved['document']['units'])
    if units < 8:
        page.locator('#squadAdd').click()
        assert page.locator('#squadUnits li').count() == units + 1
        page.select_option('#squad-kind', 'mec')
        assert 'Now a MEC trooper' in page.locator('.squadkindnote').inner_text()
        assert page.locator('#squad-armour').input_value().startswith('eItem_Mec')
        page.select_option('#squad-kind', 'shiv')
        assert page.locator('#squad-last').count() == 0 and page.locator('#squad-look').count() == 0
        page.fill('#squad-first', 'Bad"Name')
        page.wait_for_function("document.querySelector('#squadUnits li.on.bad')")
        assert 'letters, digits, spaces' in page.locator('.squadunitissues').inner_text()
        page.locator('#squadUp').click()
        assert page.locator('#squadUnits li.on .squadnum').inner_text() == str(units)
        page.locator('#squadCopy').click()
        assert page.locator('#squadUnits li').count() == units + 2
        page.locator('#squadRemove').click(); page.locator('#squadRemove').click()
        assert page.locator('#squadUnits li').count() == units
    page.locator('#squadWide').check()
    page.locator('#squadWide').uncheck()
    page.keyboard.press('Escape')
    assert page.locator('#squadDialog').is_hidden()
    assert page.evaluate("fetch('/squad.json').then(r => r.json())")['revision'] == saved['revision']
    if saves:
        page.locator('#playButton').click(); page.locator('#settingsSquad').click()
        page.wait_for_function("document.querySelectorAll('#squadUnits li').length > 0")
        page.fill('#squadName', 'Smoke squad')
        page.locator('#squadSave').click()
        page.wait_for_selector('#squadDialog', state='hidden')
        mine = page.evaluate("fetch('/squad.json').then(r => r.json())")
        assert mine['document']['name'] == 'Smoke squad' and mine['revision'] != saved['revision']
        page.locator('#playButton').click(); page.locator('#settingsSquad').click()
        page.wait_for_function("document.querySelectorAll('#squadUnits li').length > 0")
        page.evaluate("""async revision => { const s = await (await fetch('/squad.json')).json();
          await fetch('/squad.json', {method: 'PUT', headers: {'Content-Type': 'application/json'},
                                      body: JSON.stringify({expectedRevision: revision, document: {...s.document, name: 'Elsewhere'}})}); }""",
                      mine['revision'])
        page.fill('#squadName', 'Mine')
        page.locator('#squadSave').click()
        page.wait_for_function("document.querySelector('#squadStatus').textContent.includes('Saved elsewhere')")
        assert page.locator('#squadName').input_value() == 'Mine' and page.locator('#squadDialog').is_visible()
        page.locator('#squadCancel').click()
        restore = page.evaluate("fetch('/squad.json').then(r => r.json())")
        page.evaluate("""([revision, document]) => fetch('/squad.json', {method: 'PUT', headers: {'Content-Type': 'application/json'},
                         body: JSON.stringify({expectedRevision: revision, document})})""", [restore['revision'], saved['document']])
    if page.evaluate("!document.querySelector('#projectPlay').hidden && !document.querySelector('#projectPlay').disabled"):
        page.locator('#projectPlay').click()
        page.wait_for_selector('#buildOptions:not([hidden])')
        if page.locator('#buildSquadRow').is_visible():
            assert page.locator('#buildSquad').inner_text().startswith('Squad')
            page.locator('#buildSquad').click()
            page.wait_for_selector('#squadDialog:not([hidden])')
            page.locator('#squadCancel').click()
            assert page.locator('#squadDialog').is_hidden() and page.locator('#buildOptions').is_visible()
        page.locator('#buildOptionsCancel').click()
        assert page.locator('#buildOptions').is_hidden()


def check_projects(browser, url):
    """Projects (first-editor plan E1). Only against a test server whose --projects is a scratch folder: it saves
    projects there. Saving, reopening identically, recovery after a lost tab, a stale save refused and overwritten,
    a project of the untouched map, and edits naming pieces this export lacks kept unchanged. Then the Save dialog
    replacing a project and renaming the open one, the Load dialog, and the recent list. Its projects are named after
    the run (RUN), so it runs again against the same folder, after other checks' projects too."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409,))
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): return skip('projects', 'needs a map, not a preview', page, whole=True)
    before = {p['id'] for p in page.evaluate("fetch('/projects.json').then(r => r.json())")['projects']}
    visible = page.evaluate("[...viewer.roots.keys()].filter(id => { const r = viewer.roots.get(id), o = r.userData.source;"
                            " return r.visible && !o.hidden && viewer.gizmo.linkedCount(id) === 0 && !viewer.recipeOf(id); })")
    linked = page.evaluate("[...viewer.roots.keys()].find(id => viewer.roots.get(id).visible && viewer.gizmo.linkedCount(id) >= 1)")
    # Edits of each kind: a moved and turned original, a deleted one, and a pasted copy (of a linked group if any).
    page.evaluate('id => viewer.select(id)', visible[5])
    type_pose(page, 'posX', 96); type_pose(page, 'rotY', 30)
    page.evaluate('id => viewer.select(id)', visible[9])
    page.keyboard.press('Delete')
    page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', linked or visible[12])
    page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
    box = page.locator('#viewport > canvas').bounding_box()
    page.mouse.click(box['x'] + box['width'] * 0.6, box['y'] + box['height'] * 0.6)
    page.wait_for_function('viewer.changes().added > 0')
    # The pasted copy and the moved original, locked as a group: saved and reopened with the rest.
    page.evaluate('id => viewer.select(id, true)', visible[5])
    page.keyboard.press('Control+g')
    assert len(page.evaluate('viewer.editState().groups')) == 1
    assert 'not saved' in page.locator('#editCount').inner_text()
    edited, counts = page.evaluate('viewer.projectState()'), page.evaluate('viewer.changes()')
    # Ctrl+S without a project opens the Save dialog; Enter saves revision 1 and puts the project in the address.
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    assert page.locator('#fileTitle').inner_text() == 'Save project' and page.locator('#fileName').input_value() == ''
    assert page.locator('#fileOk').is_disabled()
    shown = type_project_name(page, f'Smoke test project {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    first = page.evaluate('viewer.project().id')
    assert f'project={first}' in page.url and page.locator('#projectTitle').inner_text() == f'Smoke test project {RUN}'
    assert 'saved' in page.locator('#editCount').inner_text() and 'unsaved' not in page.locator('#editCount').inner_text()
    doc = page.evaluate('viewer.project().doc')
    # The project's name as one word, at most 24 characters (numbered when another project has it), as the dialog
    # showed; its patch patch_<name>, 30 at most (T-09).
    assert doc['output']['shipAs'].startswith('SmokeTestProject') and len(doc['output']['shipAs']) <= 24
    assert shown.startswith('Builds as %s · ' % doc['output']['shipAs']), shown
    assert len(doc['output']['patch']) <= 30 and doc['output']['patch'] == 'patch_' + doc['output']['shipAs'].lower()
    assert doc['source']['sha256'] == page.evaluate('viewer.data.source.sha256')
    assert len(doc['groups']) == 1 and doc['groups'][0]['locked'], doc['groups']
    # Reopened, the scene is what was saved: same edits, nothing unsaved, no history to undo.
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    assert page.evaluate('viewer.projectState()') == edited and page.evaluate('viewer.changes()') == counts
    assert page.evaluate('viewer.project().revision') == 1 and not page.evaluate('viewer.project().dirty')
    assert not page.evaluate('viewer.gizmo.canUndo()')
    # Ctrl+B opens Build's panel with Bake the lighting off; ticking it changes the estimate; Esc closes it, unbuilt.
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    assert not page.locator('#buildBake').is_checked()
    assert page.locator('#buildOptionsTitle').inner_text() == f'Build Smoke test project {RUN}'
    assert page.locator('#buildOptionsNote').inner_text().startswith('Revision 1, as saved')
    page.wait_for_function("document.activeElement?.id === 'buildOptionsOk'")
    assert page.locator('#buildOptionsOk').inner_text() == 'Build' and page.locator('#buildOptionsLast').is_hidden()
    unbaked = page.locator('#buildEstimate').inner_text()
    page.locator('#buildBake').check()
    assert page.locator('#buildEstimate').inner_text() not in ('', unbaked)
    page.keyboard.press('Escape')
    assert page.locator('#buildOptions').is_hidden()
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", first)
    assert build['state'] == 'idle', build['state']
    # An unsaved change is kept for recovery, and offered back after the tab is lost.
    page.evaluate('id => viewer.select(id)', visible[14])
    type_pose(page, 'posY', -48)
    assert page.evaluate('viewer.project().dirty') and 'unsaved' in page.locator('#editCount').inner_text()
    unsaved = page.evaluate('viewer.projectState()')
    wait_recovery(page, True)
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    assert page.evaluate('viewer.projectState()') == edited
    page.locator('#projectBanner button', has_text='Restore them').click()
    page.wait_for_function('s => viewer.projectState() === s', arg=unsaved)
    assert page.evaluate('viewer.project().dirty')
    # Ctrl+S saves revision 2 and drops the recovery state.
    page.keyboard.press('Control+s')
    page.wait_for_function('viewer.project()?.revision === 2 && !viewer.project().dirty')
    wait_recovery(page, False)
    # A save based on an older revision is refused: another tab saved first. Overwriting saves on top of it.
    other = open_viewer(browser, project_url(page, first), errors)
    other.evaluate('id => viewer.select(id)', visible[16]); other.keyboard.press('Delete')
    other.keyboard.press('Control+s')
    other.wait_for_function('viewer.project()?.revision === 3')
    other.close()
    page.evaluate('id => viewer.select(id)', visible[18])
    type_pose(page, 'posZ', 8)
    page.keyboard.press('Control+s')
    page.wait_for_selector('#projectBanner:not([hidden])')
    assert 'saved elsewhere' in page.locator('#projectBanner').inner_text() and page.evaluate('viewer.project().revision') == 2
    page.locator('#projectBanner button', has_text='Overwrite').click()
    page.wait_for_function('viewer.project()?.revision === 4 && !viewer.project().dirty')
    # A project of the untouched map: Reset all, then Save as… a new name; it reopens with no edits and its own names.
    # The Save dialog starts on the open project: its name typed in, its row chosen and marked open.
    page.locator('#editResetAll').click()
    save_dialog(page, f'Smoke test project {RUN}')
    assert page.locator('.filerow.on').get_attribute('data-id') == first and 'open' in page.locator('.filerow.on').inner_text()
    type_project_name(page, f'Smoke test empty {RUN}')
    assert page.locator('.filerow.on').count() == 0
    page.locator('#fileName').press('Enter')
    page.wait_for_function('id => viewer.project()?.id !== id && viewer.project().revision === 1', arg=first)
    empty = page.evaluate('viewer.project()')
    assert empty['doc']['output']['shipAs'] != doc['output']['shipAs']
    page.goto(project_url(page, empty['id']))
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.project().name') == f'Smoke test empty {RUN}'
    # Records naming pieces this export does not have are kept, noted, and saved back unchanged.
    status = page.evaluate("""async id => {
      const doc = await (await fetch(`/projects/${id}/project.json`)).json();
      doc.overrides.push({ target: { package: doc.source.map, level: 'base', actor: 'TheWorld.PersistentLevel.NotInThisExport_1' }, deleted: true });
      doc.added.push({ id: '00000000-0000-4000-8000-000000000001', actor: 'TheWorld.PersistentLevel.NotInThisExport_2_copy99',
        from: { package: doc.source.map, level: 'base', actor: 'TheWorld.PersistentLevel.NotInThisExport_2' }, components: ['C'],
        location: [0, 0, 0], rotation: [0, 0, 0], prefab: null, partner: null });
      return (await fetch(`/projects/${id}/project.json`, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expectedRevision: doc.revision, document: doc }) })).status;
    }""", empty['id'])
    assert status == 200
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    carried = page.evaluate('viewer.project().carried')
    assert (len(carried['overrides']), len(carried['added'])) == (1, 1), carried
    assert 'do not have' in page.locator('#diagnostics').inner_text().replace('does not have', 'do not have')
    page.evaluate('viewer.saveProject()')
    page.wait_for_function('viewer.project()?.revision === 3')
    saved = page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", empty['id'])
    assert [o['target']['actor'] for o in saved['overrides']] == ['TheWorld.PersistentLevel.NotInThisExport_1']
    assert [a['actor'] for a in saved['added']] == ['TheWorld.PersistentLevel.NotInThisExport_2_copy99'] and saved['nextSerial'] >= 99
    # A project that cannot be found is said so, and the map opens without it.
    missing = open_viewer(browser, project_url(page, '00000000-0000-4000-8000-00000000dead'), errors, expected=(404,))
    assert 'could not be opened' in missing.locator('#projectBanner').inner_text() and missing.evaluate('viewer.project()') is None
    missing.close()
    # Save as… the name of another project of this map (in another case): a confirm, then that project replaced.
    # It keeps its id and output names; the project open before is unchanged.
    page.evaluate('id => viewer.select(id)', visible[20])
    type_pose(page, 'posX', -96)
    replaced = page.evaluate('viewer.projectState()')
    save_dialog(page, f'smoke TEST project {RUN}')
    assert page.locator('.filerow.on').get_attribute('data-id') == first
    page.locator('#fileName').press('Enter')
    assert 'already exists' in page.locator('#fileConfirm').inner_text()
    page.locator('#fileConfirm button', has_text="Don't replace").click()
    assert page.locator('#fileConfirm').is_hidden() and page.locator('#fileDialog').is_visible()
    page.locator('#fileName').press('Enter')
    assert page.locator('#fileConfirm button.primary').inner_text() == 'Replace'
    page.locator('#fileConfirm button.primary').click()
    page.wait_for_function('id => viewer.project()?.id === id && viewer.project().revision === 5 && !viewer.project().dirty', arg=first)
    now = page.evaluate('viewer.project()')
    assert now['name'] == f'smoke TEST project {RUN}' and now['doc']['output'] == doc['output'] and f'project={first}' in page.url
    assert page.evaluate('viewer.projectState()') == replaced
    assert page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", empty['id'])['revision'] == 3
    # The open project's own name in another case saves its next revision, renamed, without a confirm.
    save_dialog(page, f'Smoke Test Project {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 6')
    assert page.evaluate('viewer.project()')['name'] == f'Smoke Test Project {RUN}' and page.evaluate('viewer.project().id') == first
    # Each project is one file named after it, renamed with it (the case too): the two this check saved, beside what
    # the folder held before it
    files = {p['id']: p['file'] for p in page.evaluate("fetch('/projects.json').then(r => r.json())")['projects'] if p['id'] not in before}
    assert files == {first: f'Smoke Test Project {RUN}.json', empty['id']: f'Smoke test empty {RUN}.json'}, files
    # Ctrl+O, the Load dialog: it starts on the open project; typing finds another; Enter opens it.
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Control+o')
    page.wait_for_selector('#fileDialog:not([hidden]) .filerow')
    assert page.locator('.filerow.on').get_attribute('data-id') == first
    page.locator('#fileName').fill(f'smoke test empty {RUN}')
    assert page.locator('.filerow.on').get_attribute('data-id') == empty['id']
    page.locator('#fileName').press('Enter')
    wait_opened(page, empty['id'])
    # The recent list: at most three, the open project aside, the one open before at the top; a click opens it.
    page.locator('#projectButton').click()
    page.wait_for_selector('#projectRecent .projectitem')
    recent = page.locator('#projectRecent .projectitem').evaluate_all('rows => rows.map(r => r.dataset.id)')
    assert 1 <= len(recent) <= 3 and empty['id'] not in recent and recent[0] == first, recent
    page.locator('#projectRecent .projectitem').first.click()
    wait_opened(page, first)
    assert page.evaluate('viewer.projectState()') == replaced
    page.close()
    assert not errors, errors


def stand_in_export(page, old, asked):
    """The server's answers about the map's export stood in for on `page` (no map is exported): while old['on'], the
    families say the export is older than building needs; a prepare's export starts at once and reports 40% until its
    third status read (asked['count']), then ready."""
    def families(route):
        answer = route.fetch()
        body = answer.json()
        if old['on']: body['exportProblem'] = 'older than export 18 (the smoke test says so)'
        route.fulfill(response=answer, json=body)

    def export(route):
        if route.request.method == 'POST': route.fulfill(json=dict(state='running'))
        else: route.continue_()

    def export_status(route):
        asked['count'] += 1
        route.fulfill(json=dict(state='running', progress=dict(fraction=0.4)) if asked['count'] < 3 else dict(state='ready'))

    page.route('**/maps/*/families.json', families)
    page.route('**/maps/*/export', export)
    page.route('**/maps/*/export.json', export_status)


def check_prepare(browser, url, project_id=None):
    """The prepare-again dialog, with the server's answers stood in for (no map is exported): a map whose export is
    older than building needs opens with the dialog in the middle of the window; Later (or Esc) leaves a banner that
    opens it again; Prepare now shows the export's progress and reopens the map. With project_id (a saved project on
    this map, on a test server with scratch builds: a quick build of it really runs): Build asks to prepare instead
    of building; and a build that failed for want of a newer export offers Prepare the map, which starts it."""
    errors = []
    old = dict(on=True)
    asked = dict(count=0)
    page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())
    stand_in_export(page, old, asked)
    page.goto(url)
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    modal = page.locator('#prepareModal')
    modal.wait_for(state='visible')
    assert 'needs preparing again' in page.locator('#prepareTitle').inner_text()
    assert 'about half a minute' in page.locator('#prepareNote').inner_text()
    page.wait_for_function("document.activeElement?.id === 'prepareOk'")
    box, view = page.locator('#prepareModal section').bounding_box(), page.viewport_size
    assert abs(box['x'] + box['width'] / 2 - view['width'] / 2) < 4 and abs(box['y'] + box['height'] / 2 - view['height'] / 2) < 40, box
    page.keyboard.press('Escape')
    modal.wait_for(state='hidden')
    assert 'Prepare now' in page.locator('#projectBanner').inner_text()
    page.locator('#projectBanner button', has_text='Prepare now').click()
    modal.wait_for(state='visible')
    page.locator('#prepareLater').click()
    modal.wait_for(state='hidden')
    if project_id:
        page.goto(project_url(page, project_id))
        page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                               arg=project_id, timeout=120000)
        modal.wait_for(state='visible')
        page.locator('#prepareLater').click()
        # Build (Ctrl+B) asks to prepare the map instead of opening its panel
        page.keyboard.press('Control+b')
        modal.wait_for(state='visible')
        assert 'can\'t be built yet' in page.locator('#prepareNote').inner_text()
        assert page.locator('#buildOptions').is_hidden()
        page.locator('#prepareLater').click()
        # a build that stopped for want of a newer export: its window offers Prepare the map, which starts it
        old['on'] = False

        def failed(route):
            answer = route.fetch()
            body = answer.json()
            if body.get('job'):
                error = ('no export of URB_Bar with SHA-256 0123 at version 18 or newer in <cache>: prepare the map (re-export it: '
                         'the map browser\'s Prepare, or python tools/viewer/viewer.py export "<game>/x.upk" --scope map) and restart the editor')
                body['state'] = body['job']['state'] = 'failed'
                body['job']['error'] = error
                body['job']['errorCode'] = 'export-missing'     # (the page goes by the code: compiler.ExportMissing's, builds.py's errorCode)
            route.fulfill(response=answer, json=body)
        page.reload()
        page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                               arg=project_id, timeout=120000)
        assert modal.is_hidden()
        page.keyboard.press('Control+b')
        page.wait_for_selector('#buildOptions:not([hidden])')
        page.route('**/projects/*/build.json', failed)
        # the panel focuses Build just after it shows: Enter before that presses nothing
        page.wait_for_function("document.activeElement?.id === 'buildOptionsOk'")
        page.keyboard.press('Enter')
        page.locator('#buildPrepare').wait_for(state='visible', timeout=60000)
        assert 'Prepare the map again, then build' in page.locator('#buildResult').inner_text()
        asked['count'] = 0
        page.locator('#buildPrepare').click()
        page.locator('#buildModal').wait_for(state='hidden')
        modal.wait_for(state='visible')
        assert 'why it stopped' in page.locator('#prepareNote').inner_text()
        assert page.locator('#prepareLater').is_hidden() and page.locator('#prepareOk').is_disabled()
        page.wait_for_function("document.querySelector('#prepareStatus').textContent.includes('40%')", timeout=20000)
        # prepared: the page opens again
        page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id && "
                               "document.querySelector('#prepareModal').hidden", arg=project_id, timeout=120000)
        page.unroute('**/projects/*/build.json', failed)
        # the quick build this started on the server really runs: let it end before anything else builds or plays
        page.wait_for_function("id => fetch(`/projects/${id}/build.json`).then(r => r.json()).then(s => s.state !== 'running')",
                               arg=project_id, timeout=300000, polling=2000)
    else:
        asked['count'] = 0
        page.locator('#projectBanner button', has_text='Prepare now').click()
        page.locator('#prepareOk').click()
        page.wait_for_function("document.querySelector('#prepareStatus').textContent.includes('40%')", timeout=20000)
        old['on'] = False
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && document.querySelector('#prepareModal').hidden",
                               timeout=120000)
    page.close()
    assert not errors, errors


def check_prepare_routes(browser, url):
    """Build's routes into Prepare (the refactor's follow-ups, item 4.8), for a project saved here (named after the run)
    with the server's answers stood in for, so that no Build runs and no map is exported: while the export is older
    than building needs, Build (Ctrl+B) asks to prepare the map instead of opening its panel (needsPrepare); and a
    build that stopped for want of a newer export (the build's status answered: failed, code export-missing) offers
    Prepare the map in its window, which starts the prepare at once and opens the map again when it is ready."""
    errors = []
    page = open_viewer(browser, url, errors)
    piece = page.evaluate("[...viewer.roots.values()].find(r => r.visible && !r.userData.source.added && !r.userData.source.hidden"
                          " && !r.userData.source.environment)?.userData.source.id")
    page.evaluate('id => viewer.select(id)', piece)
    type_pose(page, 'posX', 96)
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Prepare routes check {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project()')
    page.close()
    old, asked, started = dict(on=True), dict(count=0), dict(count=0)
    page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())
    stand_in_export(page, old, asked)
    job = dict(project=project['id'], name=project['name'], revision=1, variant=project['doc']['output']['shipAs'], quick=True,
               state='running', attempt='prepare-routes-check', origin='page', stage=None, stages=[], lines=[],
               startedAt='2026-11-21T00:00:00Z', finishedAt=None, error=None, errorCode=None, running=None, progress=None)

    def build(route):
        # a build asked for: answered as started, nothing run
        if route.request.method != 'POST': return route.continue_()
        started['count'] += 1
        status = json.loads(urllib.request.urlopen(url.split('?')[0] + f"projects/{project['id']}/build.json", timeout=30).read())
        route.fulfill(json=dict(status, state='running', job=job))

    def build_status(route):
        # its status: stopped for want of a newer export (compiler.ExportMissing's code, builds.py's errorCode)
        answer = route.fetch()
        error = ('no export of URB_Bar with SHA-256 0123 at version 18 or newer in <cache>: prepare the map (re-export it: '
                 'the map browser\'s Prepare, or python tools/viewer/viewer.py export "<game>/x.upk" --scope map) and restart the editor')
        route.fulfill(response=answer, json=dict(answer.json(), state='failed', job=dict(job, state='failed', error=error, errorCode='export-missing',
                                                                                          finishedAt='2026-11-21T00:00:05Z')))

    modal = page.locator('#prepareModal')
    page.goto(url.split('?')[0] + f"?map={project['doc']['source']['map']}&project={project['id']}")
    page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id", arg=project['id'], timeout=120000)
    # the map opens with the dialog (the export too old); Later
    modal.wait_for(state='visible')
    page.locator('#prepareLater').click()
    modal.wait_for(state='hidden')
    # Build asks to prepare the map instead of opening its panel; Later again
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press('Control+b')
    modal.wait_for(state='visible')
    assert 'can\'t be built yet' in page.locator('#prepareNote').inner_text(), page.locator('#prepareNote').inner_text()
    assert page.locator('#buildOptions').is_hidden() and started['count'] == 0
    page.locator('#prepareLater').click()
    modal.wait_for(state='hidden')
    # the export new enough as far as the page knows: Build's panel opens, and the build it starts stops for want of a
    # newer export; its window offers Prepare the map (the button that matters), which starts the prepare at once
    old['on'] = False
    page.route('**/projects/*/build', build)
    page.route('**/projects/*/build.json', build_status)
    page.reload()
    page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id", arg=project['id'], timeout=120000)
    assert modal.is_hidden()
    page.evaluate('document.activeElement?.blur?.()')
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    page.wait_for_function("document.activeElement?.id === 'buildOptionsOk'")
    page.keyboard.press('Enter')
    page.locator('#buildModal').wait_for(state='visible')
    page.locator('#buildPrepare').wait_for(state='visible', timeout=60000)
    assert started['count'] == 1
    assert 'Prepare the map again, then build' in page.locator('#buildResult').inner_text(), page.locator('#buildResult').inner_text()
    assert 'primary' not in (page.locator('#buildClose').get_attribute('class') or '').split()
    asked['count'] = 0
    page.locator('#buildPrepare').click()
    page.locator('#buildModal').wait_for(state='hidden')
    modal.wait_for(state='visible')
    assert 'why it stopped' in page.locator('#prepareNote').inner_text(), page.locator('#prepareNote').inner_text()
    assert page.locator('#prepareLater').is_hidden() and page.locator('#prepareOk').is_disabled()
    page.wait_for_function("document.querySelector('#prepareStatus').textContent.includes('40%')", timeout=20000)
    # prepared: the page opens again on the project
    page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id && "
                           "document.querySelector('#prepareModal').hidden", arg=project['id'], timeout=120000)
    page.close()
    # nothing was built: the server's own status of the project has no job
    status = json.loads(urllib.request.urlopen(url.split('?')[0] + f"projects/{project['id']}/build.json", timeout=30).read())
    assert status['state'] == 'idle' and not status['job'], status
    assert not errors, errors
    return dict(project=project['id'], builds=started['count'])


def check_play(browser, url, project_id=None, screenshot=None):
    """Play in the header, the Game menu's Game maps and its Undo everything, and the menu's Installs section. Only against a test server
    started with --install <a scratch game folder> --dry-play (it refuses any other): it changes that install, and a
    server without --dry-play would start the game. The open map plays unedited, with nothing installed; with
    project_id, that project (its build must be of its saved revision, so that nothing builds) is installed and
    played, answering Build's panel with its default there, Play last build; Remove takes it back out."""
    errors = []
    page = open_viewer(browser, url, errors)
    status = lambda: page.evaluate("fetch('/play.json').then(r => r.json())")  # noqa: E731
    first = status()
    assert first['install']['source'] == 'serve --install', f"refusing: this server plays in {first['install']['folder']} ({first['install']['source']})"
    assert first['launch']['how'] == 'dry', f"refusing: this server would start the game ({first['launch']})"
    assert first['install']['ready'], first['install']

    def menu():
        if page.locator('#playMenu').is_hidden(): page.locator('#playButton').click()
        page.wait_for_function("document.querySelectorAll('#installInfo dd').length === 4")

    def undo_everything():
        """Game maps (the Game menu), Undo everything: what it says it took out."""
        menu()
        page.locator('#projectMaps').click()
        page.wait_for_function("document.querySelector('#gameMapsCount').textContent !== ''")
        page.locator('#gameMapsUndoAll').click()
        page.wait_for_function("/^(Taken out of the game|The editor had nothing)/.test(document.querySelector('#gameMapsMessage').textContent)", timeout=60000)
        text = page.locator('#gameMapsMessage').inner_text()
        page.locator('#gameMapsDone').click()
        return text

    def banner(start):
        page.wait_for_function("t => { const b = document.querySelector('#projectBanner'); return !b.hidden && b.textContent.startsWith(t); }",
                               arg=start, timeout=60000)
        text = page.locator('#projectBanner').inner_text()
        page.locator('#projectBanner .close').click()
        return text

    menu()
    assert page.locator('#installInfo dt').all_inner_texts() == ['Game', 'Plays in', 'Started', 'In the game']
    rows = page.locator('#installInfo dd').all_inner_texts()
    # the game install's row: its folder and kind ("... (Long War Rebalance)"), or why it isn't known
    game = f"{first['lwr']['folder']} ({first['lwr']['kind']})" if first['lwr']['folder'] else first['lwr']['note']
    assert rows[0] == game and rows[1] == first['install']['folder'], rows
    if screenshot: page.locator('#playMenu').screenshot(path=str(screenshot.with_stem(screenshot.stem + '-play-menu')))
    if page.evaluate('viewer.data.scope === "map" && !viewer.data.preview && !viewer.project()'):
        page.locator('#projectPlay').click()
        # a map alone: the play dialog, whether saving is on (and with several missions, which one), never baking
        page.wait_for_selector('#buildOptions', state='visible')
        assert page.locator('#buildBakeRow').is_hidden() and page.locator('#buildSavingRow').is_visible()
        if page.evaluate('(viewer.data.missions || []).length > 1'):
            # a map with several missions: the play dialog names the mission (the header's), with its kind's line
            assert page.locator('#buildMissionRow').is_visible() and page.locator('#buildBakeRow').is_hidden()
            assert 'Enemies:' in page.locator('#buildMissionNote').inner_text() and 'played' not in page.locator('#buildMissionNote').inner_text().lower(),                 page.locator('#buildMissionNote').inner_text()
        else: assert page.locator('#buildMissionRow').is_hidden()
        page.evaluate("document.querySelectorAll('#installInfo dd').forEach(dd => { dd.dataset.drawn = 'before the play'; })")
        page.locator('#buildOptionsOk').click()
        page.wait_for_function("() => { const b = document.querySelector('#projectBanner'); return !b.hidden && b.textContent.startsWith('Starting XCOM'); }",
                               timeout=60000)
        assert '(original map)' in page.locator('#projectBanner').inner_text()
        # the Game menu's Installs drawn again from the play's answer as the message shows, the menu not opened again
        # (it closed for the play): new rows, the last saying what the play left in the game (nothing, for a map alone)
        drawn = page.evaluate("[...document.querySelectorAll('#installInfo dd')].map(dd => [dd.dataset.drawn ?? null, dd.textContent])")
        assert len(drawn) == 4 and not any(before for before, _ in drawn), drawn
        played = status()['game']
        if not (played['installed'] or played.get('rotation') or played.get('switchedOff')):
            assert drawn[3][1] == "Nothing of the editor's", drawn
        # the "Starting XCOM …" message closes itself after 12 s (× closes it sooner; banner() above clicks it)
        page.wait_for_selector('#projectBanner', state='hidden', timeout=16000)
        now = status()['game']
        assert now['lastPlay']['map'] == page.evaluate('viewer.mapId') and now['installed'] == [] and now['playFile'], now
    assert undo_everything().startswith('Taken out of the game')
    assert status()['game']['anything'] is False
    menu()
    page.wait_for_function("document.querySelectorAll('#installInfo dd')[3].textContent.startsWith(\"Nothing of the editor's\")")
    # Game maps (the Game menu): with nothing of the editor's in the game, Undo everything is greyed out
    page.locator('#projectMaps').click()
    page.wait_for_function("document.querySelector('#gameMapsCount').textContent.includes('nothing changed by the editor')")
    assert page.locator('#gameMapsUndoAll').is_disabled()
    page.locator('#gameMapsDone').click()
    if project_id:
        page.goto(project_url(page, project_id))
        page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                               arg=project_id, timeout=120000)
        build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project_id)
        assert build['package'] and build['package']['revision'] == page.evaluate('viewer.project().revision'), \
            'the project\'s build is not of its saved revision: Play would build it'
        menu()
        assert 'or to play its last build as it is' in page.locator('#projectPlay').get_attribute('title')
        page.locator('#projectPlay').click()
        # Build's panel opens for it: Build and play (Bake the lighting off), or, the default here since the last
        # build is of what is on screen, Play last build
        page.wait_for_selector('#buildOptions:not([hidden])')
        assert page.locator('#buildOptionsTitle').inner_text().startswith('Play ')
        assert not page.locator('#buildBake').is_checked()
        assert page.locator('#buildOptionsOk').inner_text() == 'Build and play'
        assert page.locator('#buildOptionsLast').is_visible()
        page.wait_for_function("document.activeElement?.id === 'buildOptionsLast'")
        page.keyboard.press('Enter')
        assert banner('Starting XCOM').count('revision') == 1
        assert page.locator('#buildModal').is_hidden()
        installed, = status()['game']['installed']
        assert installed['map'] == build['package']['folder'].split('\\')[-1] and installed['project']['id'] == project_id, installed
        # the Game menu's Installs, drawn from the play's answer: its row names the build at once, the menu not opened
        row = page.evaluate("document.querySelectorAll('#installInfo dd')[3].textContent")
        assert row.endswith(f"({installed['map']})" + (', lighting not baked' if installed.get('quick') else '')), row
        menu()
        if screenshot: page.locator('#playMenu').screenshot(path=str(screenshot.with_stem(screenshot.stem + '-play-project')))
        assert '1 map record' in undo_everything()
        # a finished build's window offers Play in game: a quick build (Ctrl+B, Bake the lighting off), then played
        # from the window, the outcome shown in it
        page.keyboard.press('Control+b')
        page.wait_for_selector('#buildOptions:not([hidden])')
        assert not page.locator('#buildBake').is_checked()
        page.wait_for_function("document.activeElement?.id === 'buildOptionsOk'")
        page.keyboard.press('Enter')
        page.locator('#buildModal').wait_for(state='visible')
        assert page.locator('#buildPlay').is_hidden()
        page.locator('#buildPlay').wait_for(state='visible', timeout=300000)
        page.wait_for_function("!document.querySelector('#buildPlay').disabled")
        assert 'Play in game installs it' in page.locator('#buildNote').inner_text()
        assert page.locator('#buildPlay').get_attribute('title').startswith('Install this build in ')
        if screenshot: page.locator('#buildModal .buildbox').screenshot(path=str(screenshot.with_stem(screenshot.stem + '-play-built')))
        page.locator('#buildPlay').click()
        page.wait_for_function("document.querySelector('#buildResult .install.done')?.textContent.startsWith('Starting XCOM')", timeout=60000)
        assert page.locator('#buildPlay').is_enabled() and page.locator('#buildModal').is_visible()
        installed, = status()['game']['installed']
        assert installed['project']['id'] == project_id and installed.get('quick'), installed
        # (the Installs row drawn from that play's answer too)
        row = page.evaluate("document.querySelectorAll('#installInfo dd')[3].textContent")
        assert row.endswith(f"({installed['map']}), lighting not baked"), row
        page.locator('#buildClose').click()
        assert '1 map record' in undo_everything()
    page.close()
    assert not errors, errors


def check_prefabs(browser, url):
    """The prefab library check (prefab_library), then the prefabs it made deleted, whether it passed or not, so that
    it runs again on the same folder (review finding 59): those the folder lists that it didn't list before."""
    base = url.split('?')[0]
    listed = lambda: json.loads(urllib.request.urlopen(base + 'prefabs.json', timeout=30).read())['prefabs']   # noqa: E731
    before = {p['id'] for p in listed()}
    try:
        return prefab_library(browser, url)
    finally:
        for p in listed():
            if p['id'] not in before:
                urllib.request.urlopen(urllib.request.Request(base + f"prefabs/{quote(p['id'])}/prefab.json", method='DELETE'), timeout=30)


def answer_prepare(page):
    """Later on the Prepare dialog when the map opened with it. The page shows it in startScene before it sets
    window.viewer, which open_viewer waits for, so once that wait is over the dialog is up or not coming."""
    if page.locator('#prepareModal').is_visible(): page.locator('#prepareLater').click()


def prefab_library(browser, url):
    """The prefab library (prefab plan stage P; prefabs.js, tools/viewer/prefabs.py). Only against a test server whose
    --projects is a scratch folder (its prefabs folder is beside it) and whose game install is set. On a map with a
    car: a car, a prop, a light and a building, the car and the prop grouped, saved as a prefab from the dialog;
    placed twice, once turned, each one group marked with the prefab, by whole tiles, one undo step; a prefab with two
    of the same car places two cars that move apart (the link tag), and so does a copy of both; the tab's Rename,
    Duplicate, Export, Delete and Import with its choice; then the prefab placed in another map, its pieces read from
    their home map, saved and built without baking."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409, 422))
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"):
        return skip('prefabs', 'needs a map (not a preview) with a tile grid', page, whole=True)
    car = page.evaluate("(viewer.families()?.assemblies ?? []).find(a => a.family === 'car' && a.members.length > 1) ?? null")
    if not car: return skip('prefabs', 'the map has no car of more than one piece', page, whole=True)
    here = page.evaluate('viewer.data.name')
    assert page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs'] == [], 'the prefabs folder is not a fresh one'
    page.evaluate("localStorage.removeItem('workshop.libraryScope')")
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    assert page.locator('#libPrefabs').is_visible() and page.locator('#libMap').is_hidden() and page.locator('#libAll').is_hidden()
    page.wait_for_function("document.getElementById('prefabFoot').textContent.startsWith('No prefabs yet')")
    # nothing selected: nothing to save
    page.evaluate('viewer.select(null)')
    page.locator('#prefabSave').click()
    assert page.locator('#prefabDialog').is_hidden() and 'Select what should be the prefab' in page.locator('#dragHint').inner_text()
    page.keyboard.press('p')
    # the car (its parts come as one), a prop of the map near it, a light, and a building round them
    ids = page.evaluate("""car => {
      const roots = [...viewer.roots.values()].filter(r => r.userData.source.layer === 'base' && !r.userData.source.hidden && !r.userData.source.environment);
      const body = roots.find(r => r.userData.source.actor === car.pivot), at = body.userData.source.location;
      const far = r => Math.hypot(r.userData.source.location[0] - at[0], r.userData.source.location[1] - at[1]);
      const prop = roots.filter(r => r.userData.source.actorClass === 'XComLevelActor' && !car.members.includes(r.userData.source.actor) && !viewer.recipeOf(r.userData.source.id))
        .sort((a, b) => far(a) - far(b))[0];
      const lamp = kind => [...viewer.lightRoots.values()].filter(r => r.userData.source.kind === kind && r.userData.source.role === 'static' && !r.userData.source.added
        && r.userData.source.layer === 'base' && !viewer.families().lightRules?.[r.userData.source.id]).sort((a, b) => far(a) - far(b))[0]?.userData.source.id ?? null;
      return { body: body.userData.source.id, prop: prop.userData.source.id, light: lamp('spot'), point: lamp('point'), at,
               parts: roots.filter(r => car.members.includes(r.userData.source.actor)).length, cars: car.members.length };
    }""", car)
    gx, gy, gz = (round(v) for v in page.evaluate('viewer.data.tileGrid.origin'))
    tx, ty = round((ids['at'][0] - gx) / 96), round((ids['at'][1] - gy) / 96)
    box = [gx + (tx - 2) * 96, gy + (ty - 2) * 96, gz, gx + (tx + 2) * 96, gy + (ty + 2) * 96, gz + 192]
    roof = box[:2] + [gz + 192] + box[3:5] + [gz + 256]
    volumes = page.evaluate("boxes => viewer.addVolumes(boxes.map((box, floor) => ({ box, floor }))).map(r => r.userData.source.id)", [box, roof])
    building = page.evaluate('viewer.buildings()[0].id')
    page.evaluate("viewer.setBoxesShown(true)")
    if ids['light'] or ids['point']: page.evaluate('viewer.setNormalLights(true)')
    page.evaluate("ids => { viewer.select(ids.body); viewer.select(ids.prop, true); }", ids)
    page.keyboard.press('Control+g')
    assert len(page.evaluate('viewer.groupList()')) == 1
    page.evaluate("([ids, volume]) => { for (const id of [ids.light, ids.point]) if (id) viewer.select(id, true); viewer.select(volume, true); }", [ids, volumes[0]])
    records = page.evaluate("(() => { const r = viewer.prefabRecords(); return { tiles: r.tiles, pieces: r.pieces, groups: r.groups, buildings: r.buildings, donors: r.donors, left: r.left, counts: r.counts }; })()")
    lights = sum(1 for k in ('light', 'point') if ids[k])
    assert records['counts'] == dict(pieces=ids['cars'] + 1, lights=lights, effects=0, sounds=0, flares=0, buildings=1, tiles=records['tiles']), records['counts']
    assert records['left'] == [] and [d['package'] for d in records['donors']] == [here] and len(records['donors'][0]['sha256']) == 64
    # in a space of its own: whole tiles from the origin, a tile corner at the building's ground; the floors as they were
    (low,), (high,) = (f['boxes'] for f in records['buildings'][0]['floors'])
    # (how far in depends on how near the map's nearest lights are: inside the prefab's tiles, on any map)
    assert low[0] >= 0 and low[1] >= 0 and low[0] % 96 == 0 and low[1] % 96 == 0, records['buildings']
    assert low[3] <= records['tiles'][0] * 96 and low[4] <= records['tiles'][1] * 96, (records['buildings'], records['tiles'])
    # W's physical envelope includes geometry below the boxes; selection saves normalize
    # from the lowest physical content, so both floors may stand above prefab ground.
    assert [low[3] - low[0], low[4] - low[1], low[5] - low[2]] == [384, 384, 192] and low[2] >= 0
    assert high == low[:2] + [low[2] + 192] + low[3:5] + [low[2] + 256], records['buildings']
    assert records['tiles'][0] >= 4 and records['tiles'][1] >= 4
    parts = [p for p in records['pieces'] if p.get('from') and p['from']['actor'] in car['members']]
    assert len(parts) == ids['cars'] and len({p['prefab'] for p in parts}) == 1 and parts[0]['prefab'].startswith('copy1:'), parts
    assert all(p['from'] == dict(package=here, level='base', actor=p['from']['actor']) and p['actor'].startswith(p['from']['actor'] + '_copy') for p in parts)
    # the car and the prop are a group of the prefab; the light and the building stand beside it
    assert len(records['groups']) == 1 and len(records['groups'][0]['members']) == ids['cars'] + 1, records['groups']
    # the lights are recipe lights, with every value, so they need no map: a spot light, and a point light without cones
    lamps = {p['template']['kind']: p for p in records['pieces'] if p.get('template')}
    assert sorted(lamps) == sorted(k for k, i in (('spot', ids['light']), ('point', ids['point'])) if i), lamps
    if ids['light']:
        assert lamps['spot']['template'] == dict(kind='spot', version=1) and sorted(lamps['spot']['light']) == sorted(['color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled'])
    if ids['point']:
        assert lamps['point']['template'] == dict(kind='point', version=1) and lamps['point']['rotation'] == [0, 0, 0] \
            and sorted(lamps['point']['light']) == sorted(['color', 'brightness', 'radius', 'falloffExponent', 'enabled']), lamps['point']
    # the dialog: what goes in, a name to start from, and the save
    # (with a floor box picked last the building's panel is up: its button saves the same selection)
    assert page.locator('#selectionPrefab').is_hidden() and page.locator('#volumePrefab').is_visible()
    page.locator('#volumePrefab').click()
    page.wait_for_selector('#prefabDialog:not([hidden])')
    what = page.locator('#prefabWhat').inner_text()
    assert f"{ids['cars'] + 1} pieces" in what and '1 building' in what and f'pieces of {here}' in what and '1 group' in what, what
    assert page.locator('#prefabLeft').is_hidden() and page.locator('#prefabOk').inner_text() == 'Save'
    page.locator('#prefabName').fill('')
    assert page.locator('#prefabOk').is_disabled()
    page.locator('#prefabName').fill('Smoke prefab')
    page.locator('#prefabName').press('Enter')
    page.wait_for_selector('#prefabDialog', state='hidden')
    # the banner says so, with Edit in the builder (the prefab menus plan, P8)
    banner = page.locator('#projectBanner')
    assert banner.is_visible() and 'Saved the prefab Smoke prefab' in banner.inner_text(), banner.inner_text()
    assert banner.get_by_role('button', name='Edit in the builder').is_visible()
    listed = lambda: page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs']
    saved, = listed()
    assert (saved['name'], saved['revision'], saved['pieces'], saved['lights'], saved['buildings'], saved['maps']) == ('Smoke prefab', 1, ids['cars'] + 1, lights, 1, [here]), saved
    # its picture is drawn from the selection and kept
    page.wait_for_function("fetch('/prefabs.json').then(r => r.json()).then(a => a.prefabs[0].picture)", timeout=20000)
    # the same name again offers to replace it: the next revision of the same prefab
    page.locator('#volumePrefab').click()
    page.wait_for_selector('#prefabDialog:not([hidden])')
    page.locator('#prefabName').fill('smoke PREFAB')
    page.wait_for_function("document.getElementById('prefabOk').textContent === 'Replace'")
    assert 'revision 1' in page.locator('#prefabStatus').inner_text()
    page.locator('#prefabOk').click()
    page.wait_for_selector('#prefabDialog', state='hidden')
    saved, = listed()
    assert (saved['id'], saved['name'], saved['revision']) == (saved['id'], 'smoke PREFAB', 2), saved
    page.evaluate("id => viewer.prefabApi.load(id).then(d => viewer.prefabApi.save(id, { ...d, name: 'Smoke prefab' }, d.revision))", saved['id'])
    state = page.evaluate('viewer.editState()')
    assert len(state['added']) == 0 and len(state['buildings']) == 1 and len(state['groups']) == 1
    # placed from the tab: a preview with the building's boxes, by whole tiles; one group, marked with the prefab
    count, lit = page.evaluate('viewer.roots.size'), page.evaluate('viewer.lightRoots.size')
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.wait_for_selector('#prefabList .libitem')
    row = page.locator('#prefabList .libitem').first
    assert 'Smoke prefab' in row.inner_text() and '1 building' in row.inner_text()
    page.evaluate("viewer.frame('playable')")
    canvas = page.locator('#viewport > canvas').bounding_box()
    spot = lambda fx, fy: (canvas['x'] + canvas['width'] * fx, canvas['y'] + canvas['height'] * fy)

    def click_placement(at, turns=0):
        page.mouse.move(*at)
        page.wait_for_function('viewer.placing()?.ghost.visible')
        for _ in range(turns): page.keyboard.press('r')
        if page.evaluate('at => viewer.placementProblem(at)', list(at)):
            candidates = [spot(x, y) for y in (0.5, 0.6, 0.7, 0.8, 0.4, 0.3) for x in (0.62, 0.72, 0.52, 0.82, 0.42)]
            at = next((p for p in candidates if page.evaluate('at => viewer.placementProblem(at)', list(p)) is None), None)
            assert at is not None, 'No visible placement fits the destination map'
            page.mouse.move(*at)
        before = page.evaluate('viewer.roots.size')
        page.mouse.click(*at)
        page.wait_for_function('n => viewer.roots.size > n', arg=before)

    def place(at, turns=0):
        page.locator('#prefabList .libitem').first.click()
        page.wait_for_function('viewer.placing()?.fromList', timeout=60000)
        assert 'on' in page.locator('#prefabList .libitem').first.get_attribute('class').split()
        click_placement(at, turns)
        page.wait_for_function("document.querySelector('#dragHint').textContent.startsWith('Placed')")

    place(spot(0.62, 0.5))
    assert page.evaluate('viewer.roots.size') == count + ids['parts'] + 1 and page.evaluate('viewer.lightRoots.size') == lit + lights
    state = page.evaluate('viewer.editState()')
    assert len(state['buildings']) == 2 and sorted(b['name'] for b in state['buildings'])[-1] != ''
    made = sorted(e['template']['kind'] for e in state['added'] if e.get('template'))
    assert made == sorted(lamps), made
    if ids['point']:    # the point light placed keeps the values it was saved with
        assert next(e for e in state['added'] if e.get('template', {}).get('kind') == 'point')['light'] == lamps['point']['light']
    added = [e for e in state['added'] if e.get('from')]
    assert len(added) == ids['cars'] + 1 and all(e['from']['package'] == here for e in added), added
    wheels = [e for e in added if e['from']['actor'] in car['members']]
    assert len({e['prefab'] for e in wheels}) == 1 and wheels[0]['prefab'].startswith('copy'), wheels
    originals = {o['actor']: o for o in page.evaluate("viewer.data.objects.filter(o => o.layer === 'base').map(o => ({ actor: o.actor, location: o.location, rotation: o.rotation }))")}
    for e in wheels:       # the car keeps the pose rule: whole tiles and storeys from where its original stands
        moved = [a - b for a, b in zip(e['location'], originals[e['from']['actor']]['location'])]
        assert abs(moved[0] / 96 - round(moved[0] / 96)) < 1e-3 and abs(moved[1] / 96 - round(moved[1] / 96)) < 1e-3 and abs(moved[2] / 64 - round(moved[2] / 64)) < 1e-3, (e, moved)
        assert e['rotation'] == originals[e['from']['actor']]['rotation']
    groups = page.evaluate('viewer.groupList()')
    outer, = [g for g in groups if g['prefab']]
    assert outer['prefab'] == dict(id=saved['id'], name='Smoke prefab', revision=3) and len(groups) == 3, groups
    assert len(outer['members']) == 2 + lights and sum(m.startswith('group|') for m in outer['members']) == 1 \
        and sum(m.startswith('building|') for m in outer['members']) == 1, outer
    # it is selected whole, and the panel says what it is
    assert page.evaluate('viewer.gizmo.selection().length') == ids['parts'] + 1 + lights + 2
    assert page.locator('#groupTitle').inner_text().upper().startswith('PREFAB · SMOKE PREFAB')
    assert 'Placed from the prefab Smoke prefab (revision 3)' in page.locator('#groupText').inner_text()
    # and offers the prefab in the builder while the library has it (the prefab menus plan)
    assert page.locator('#groupPrefabOpen').is_visible() and page.locator('#groupPrefabOpen').inner_text() == 'Open Smoke prefab in the builder'
    # one undo step takes all of it back; redo brings it again
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == count and len(page.evaluate('viewer.editState().buildings')) == 1 and len(page.evaluate('viewer.groupList()')) == 1
    page.keyboard.press('Control+y')
    page.wait_for_function('n => viewer.roots.size > n', arg=count)
    assert len(page.evaluate('viewer.groupList()')) == 3
    # again, turned a quarter turn: a second car with a link tag of its own, turned with everything else
    place(spot(0.42, 0.62), turns=1)
    state = page.evaluate('viewer.editState()')
    wheels = [e for e in state['added'] if e.get('from') and e['from']['actor'] in car['members']]
    assert len(wheels) == 2 * ids['cars'] and len({e['prefab'] for e in wheels}) == 2, wheels
    yaw = lambda e: (e['rotation'][1] - originals[e['from']['actor']]['rotation'][1]) % 65536
    assert sorted({yaw(e) for e in wheels}) == [0, 16384], sorted({yaw(e) for e in wheels})
    assert len(state['buildings']) == 3 and len({b['name'] for b in state['buildings']}) == 3
    turned = [b for b in state['buildings'] if b['id'] != building][-1]
    assert all(len(f['boxes']) == 1 for b in state['buildings'] for f in b['floors'])
    assert len([g for g in page.evaluate('viewer.groupList()') if g['prefab']]) == 2
    # a copy of both placed cars pasted together: two cars still (each set of linked pieces has a tag of its own)
    bodies = page.evaluate("pivot => [...viewer.roots.values()].filter(r => r.userData.source.added && r.userData.source.added.from.actor === pivot).map(r => r.userData.source.id)", car['pivot'])
    assert len(bodies) >= 2
    page.keyboard.press('p')
    page.evaluate("ids => { viewer.select(ids[0]); viewer.select(ids[1], true); }", bodies)
    page.keyboard.press('Control+c')
    page.keyboard.press('Control+v')
    click_placement(spot(0.5, 0.4))
    wheels = [e for e in page.evaluate('viewer.editState().added') if e.get('from') and e['from']['actor'] in car['members']]
    assert len(wheels) == 4 * ids['cars'] and len({e['prefab'] for e in wheels}) == 4, sorted({e['prefab'] for e in wheels})
    page.keyboard.press('Control+z')
    # a prefab with two of the same car, written by hand and imported: two cars, each moving on its own
    doc = page.evaluate("id => viewer.prefabApi.load(id)", saved['id'])
    one = [p for p in doc['pieces'] if p.get('from') and p['from']['actor'] in car['members']]
    two = [dict(p, actor=p['actor'] + '0', location=[p['location'][0] + 384, p['location'][1], p['location'][2]], prefab='copy9:second',
                partner=(p['partner'] + '0') if p.get('partner') else None) for p in one]
    twin = dict(schema=doc['schema'], schemaVersion=1, id='0f8b2c4e-1d2a-4b6c-8e9f-123456789abc', name='Two cars',
                floor=dict(tiles=[doc['floor']['tiles'][0] + 4, doc['floor']['tiles'][1]]), pieces=one + two, groups=[], buildings=[],
                donors=doc['donors'], mission=None)
    taken = page.evaluate("doc => viewer.prefabApi.importFile(doc)", twin)
    assert taken['revision'] == 1 and len(listed()) == 2
    before = page.evaluate('viewer.roots.size')
    clip = page.evaluate("id => viewer.choosePrefab(viewer.prefabs.list().find(p => p.id === id) ?? { id, name: 'Two cars' }).then(c => ({ entries: c.entries.length, left: c.left, locked: c.gridLocked }))", twin['id'])
    # (placed as the snap setting says: a prefab of pieces with a pose rule is held to whole tiles no longer, since
    # 21 November 2026; Align to game pose puts a piece on its rule; a prefab with floor boxes still goes by tiles)
    assert clip == dict(entries=2 * ids['parts'], left=[], locked=False), clip
    click_placement(spot(0.55, 0.45))
    assert page.evaluate('viewer.roots.size') == before + 2 * ids['parts']
    fresh = [e for e in page.evaluate('viewer.editState().added') if e.get('from') and e['from']['actor'] in car['members']][-2 * ids['cars']:]
    marked = [g for g in page.evaluate('viewer.groupList()') if g['prefab'] and g['prefab']['name'] == 'Two cars']
    assert len(marked) == 1 and len(marked[0]['members']) == 2 * ids['cars'], marked
    tags = page.evaluate("pivot => [...viewer.roots.values()].filter(r => r.userData.source.added?.from.actor === pivot).map(r => r.userData.source.prefab)", car['pivot'])
    assert len(set(tags)) == len(tags) == 4, tags
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.roots.size') == before
    page.keyboard.press('Escape')
    # ---- the tab: filter, a row's Edit alone; the Open window's Prefabs side (All prefabs…, the prefab menus plan's
    # decision P9): rename, duplicate, export, delete, import with its choice, the tab hearing of each
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
    page.locator('#prefabFilter').fill('two')
    assert page.locator('#prefabList .libitem').count() == 1 and '1 of 2 prefabs' in page.locator('#prefabFoot').inner_text()
    assert [t.strip() for t in page.locator('#prefabList .libitem').first.locator('.prefabacts button').all_inner_texts()] == ['Edit']
    page.locator('#prefabFilter').fill('')
    page.locator('#prefabAll').click()
    page.wait_for_selector('#openPrefabDialog:not([hidden])')
    page.wait_for_function("document.querySelectorAll('#openPrefabCards .card:not(.newcard)').length === 2")
    card = lambda prefab_id: page.locator(f'#openPrefabCards .card[data-id="{prefab_id}"]')     # noqa: E731
    acts = page.locator('#openPrefabActs')
    page.locator('#openPrefabFilter').fill('two')
    assert page.locator('#openPrefabCards .card:not(.newcard)').count() == 1 and '1 of 2 prefabs' in page.locator('#openPrefabCount').inner_text()
    assert page.locator('#openPrefabCards .card').first.get_attribute('data-id') == 'new'      # (New prefab first, whatever the filter)
    page.locator('#openPrefabCards .card:not(.newcard)').first.click()
    acts.get_by_role('button', name='Rename').click()
    acts.locator('.prefabrename').fill('Two sedans')
    acts.locator('.prefabrename').press('Enter')
    page.locator('#openPrefabFilter').fill('')
    page.wait_for_function("[...document.querySelectorAll('#openPrefabCards .card strong')].some(s => s.textContent === 'Two sedans')")
    page.wait_for_function("[...document.querySelectorAll('#prefabList .libitem strong')].some(s => s.textContent === 'Two sedans')")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans']
    sedans = next(p['id'] for p in listed() if p['name'] == 'Two sedans')
    card(sedans).click()
    acts.get_by_role('button', name='Duplicate').click()
    page.wait_for_function("document.querySelectorAll('#openPrefabCards .card:not(.newcard)').length === 3")
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 3")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans', 'Two sedans copy']
    card(saved['id']).click()
    with page.expect_download() as download:
        acts.get_by_role('button', name='Export').click()
    exported = json.loads(Path(download.value.path()).read_text(encoding='utf8'))
    assert download.value.suggested_filename == 'Smoke prefab.json' and exported['id'] == saved['id'] and exported['schema'] == 'xcom-map-workshop/prefab'
    assert 'mesh' not in json.dumps(exported).lower().replace('meshcomponent', '')     # references and numbers only
    copy = next(p['id'] for p in listed() if p['name'] == 'Two sedans copy')
    card(copy).click()
    acts.get_by_role('button', name='Delete').click()
    assert 'Delete Two sedans copy?' in acts.inner_text()
    acts.get_by_role('button', name='Keep it').click()
    assert len(listed()) == 3
    acts.get_by_role('button', name='Delete').click()
    acts.get_by_role('button', name='Delete it').click()
    page.wait_for_function("document.querySelectorAll('#openPrefabCards .card:not(.newcard)').length === 2")
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans']
    # a file from elsewhere: one the library has already asks; Keep both stores it beside
    sent = dict(exported, name='Smoke prefab, sent back')
    payload = dict(name='sent.json', mimeType='application/json', buffer=json.dumps(sent).encode())
    page.locator('#openPrefabFile').set_input_files(payload)
    page.wait_for_function("document.getElementById('openPrefabNote').textContent.includes('already has this prefab')")
    assert 'Smoke prefab' in page.locator('#openPrefabNote').inner_text() and len(listed()) == 2
    page.locator('#openPrefabNote').get_by_role('button', name='Keep both').click()
    page.wait_for_function("document.querySelectorAll('#openPrefabCards .card:not(.newcard)').length === 3")
    assert 'Smoke prefab, sent back (imported)' in [p['name'] for p in listed()]
    # one that is no prefab says why and changes nothing
    page.locator('#openPrefabFile').set_input_files(dict(name='bad.json', mimeType='application/json', buffer=json.dumps(dict(sent, pieces=[dict(actor='<b>')])).encode()))
    page.wait_for_function("document.getElementById('openPrefabNote').textContent.startsWith('Not imported')")
    assert len(listed()) == 3
    page.locator('#openPrefabNote button').click()
    page.locator('#openPrefabCancel').click()
    page.wait_for_selector('#openPrefabDialog', state='hidden')
    page.keyboard.press('p')
    # ---- in another map: a prefab of the car and the prop alone, read from their home map, saved and built
    maps = page.evaluate("fetch('/maps.json').then(r => r.json())")['maps']
    ready = [m['id'] for m in maps if m.get('ready') and not m.get('outdated') and m['id'] != page.evaluate('viewer.mapId')]
    other = next((m for m in ('URB_PoliceStation', 'URB_Bar') if m in ready), ready[0] if ready else None)
    plain = dict(schema=doc['schema'], schemaVersion=1, id='1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d', name='Car and prop',
                 floor=doc['floor'], pieces=[p for p in doc['pieces'] if p.get('from')], groups=doc['groups'], buildings=[],
                 donors=doc['donors'], mission=None)
    page.evaluate("doc => viewer.prefabApi.importFile(doc)", plain)
    assert not errors, errors
    page.close()
    if not other: return skip('prefabs', 'placed in another map: no other map is ready')
    page = open_viewer(browser, url.split('?')[0] + f'?map={other}', errors)
    answer_prepare(page)
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"):
        return skip('prefabs', f'placed in another map: {other} has no tile grid', page)
    count = page.evaluate('viewer.roots.size')
    # (placed under tile snap, as the user keeps pieces with a pose rule on the grid: a prefab of such pieces follows
    # the snap setting since 21 November 2026, smoothly with snap off)
    page.evaluate("viewer.setSnapMode('tile')")
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    page.wait_for_selector('#prefabList .libitem')
    page.locator('#prefabList .libitem', has_text='Car and prop').click()
    page.wait_for_function('viewer.placing()?.fromList', timeout=180000)
    page.evaluate("viewer.frame('playable')")
    canvas = page.locator('#viewport > canvas').bounding_box()
    at = (canvas['x'] + canvas['width'] * 0.6, canvas['y'] + canvas['height'] / 2)
    if page.evaluate('at=>viewer.placementProblem(at)', list(at)):
        points = [(canvas['x']+canvas['width']*x, canvas['y']+canvas['height']*y) for y in (0.5,0.6,0.7,0.4,0.3) for x in (0.6,0.7,0.5,0.8,0.4)]
        # (a place inside the map's grid if the view has one; outside it the prefab is placed with a warning, not
        # refused: plan "sturdier prefabs", R7)
        at = next((p for p in points if page.evaluate('at=>viewer.placementProblem(at)', list(p)) is None), at)
    page.mouse.move(*at)
    page.wait_for_function('viewer.placing()?.ghost.visible')
    page.mouse.click(*at)
    page.wait_for_function('n => viewer.roots.size > n', arg=count)
    assert page.evaluate('viewer.roots.size') == count + ids['parts'] + 1
    state = page.evaluate('viewer.editState()')
    assert len(state['added']) == ids['cars'] + 1 and all(e['from']['package'] == here for e in state['added']), state['added']
    assert len({e['prefab'] for e in state['added'] if e['from']['actor'] in car['members']}) == 1
    marked, = [g for g in page.evaluate('viewer.groupList()') if g['prefab']]
    assert marked['prefab']['name'] == 'Car and prop'
    assert page.evaluate("[...viewer.roots.values()].filter(r => r.userData.source.foreign).length") == ids['parts'] + 1
    # every piece that keeps the pose rule stands on this map's grid as it stood on its own
    assert page.evaluate("[...viewer.roots.values()].filter(r => r.userData.source.added).every(r => { const m = viewer.gridNow(r.userData.source.id); return !m || m.valid; })")
    page.evaluate("viewer.setSnapMode('off')")
    page.keyboard.press('p')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Prefab smoke {RUN}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    saved_groups = page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json()).then(d => d.groups)", project)
    assert any(g.get('prefab', {}).get('name') == 'Car and prop' for g in saved_groups), saved_groups
    # reopened: the same state, the mark kept
    key = page.evaluate('viewer.projectState()')
    page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=180000)
    assert page.evaluate('viewer.projectState()') == key and not any(page.evaluate('viewer.project().carried').values())
    assert [g for g in page.evaluate('viewer.groupList()') if g['prefab']]
    page.keyboard.press('Control+b')
    page.wait_for_selector('#buildOptions:not([hidden])')
    page.locator('#buildOptionsOk').click()
    page.locator('#buildModal').wait_for(state='visible')
    page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=600000)
    assert page.locator('#buildTitle').inner_text().startswith(f'Built Prefab smoke {RUN}'), page.locator('#buildModal').inner_text()
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built' and build['package']['foreignPieces'] == ids['cars'] + 1, build
    assert [d['map'] for d in build['package']['donors']] == [here], build['package']['donors']
    page.locator('#buildClose').click()
    assert not errors, errors
    page.close()


def check_prefab_effects(browser, url):
    """The prefab-effects check (prefab_effects), then the prefabs it made deleted, whether it passed or not, as
    check_prefabs does: a failure leaves no prefab behind for the prefab library check, which wants a fresh folder."""
    base = url.split('?')[0]
    listed = lambda: json.loads(urllib.request.urlopen(base + 'prefabs.json', timeout=30).read())['prefabs']   # noqa: E731
    before = {p['id'] for p in listed()}
    try:
        return prefab_effects(browser, url)
    finally:
        for p in listed():
            if p['id'] not in before:
                urllib.request.urlopen(urllib.request.Request(base + f"prefabs/{quote(p['id'])}/prefab.json", method='DELETE'), timeout=30)


def prefab_effects(browser, url):
    """Effects and sounds in a prefab (effects and sounds plan, stage FX6a), on URB_Bar against check_prefabs' kind of
    test server, after it (its prefab is deleted at the end): a prop, a free effect and a sound grouped and saved as
    a prefab (schema 3, each of its kind with its source, counted, no footprint from the sound's reach); placed in
    this map (copies of their kinds, one group marked with the prefab, the effect's likeness with the cursor); then
    in another map, read from their home map, saved, reopened and built without baking."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409, 422))
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 29 && viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')"):
        return skip('prefab-effects', 'URB_Bar (not a preview) of export 29 or later only', page, whole=True)
    here = page.evaluate('viewer.data.name')
    page.evaluate('viewer.setNormalEffects(true)')
    ids = page.evaluate("""(() => { viewer.effectMarkers();
      const free = kind => [...viewer.effectRoots.values()].find(r => { const o = r.userData.source; return !o.stream && o.layer === 'base' && o.kind === kind
        && !o.carriedBy && !o.landingActor && !viewer.effectState(o.id).viewOnly && (kind !== 'effect' || viewer.data.effectSystems[o.system]?.emitters.some(e => e.draw)); });
      const fx = free('effect'), snd = free('sound');
      if (!fx || !snd) return null;
      const at = fx.userData.source.location, far = r => Math.hypot(r.userData.source.location[0] - at[0], r.userData.source.location[1] - at[1]);
      const prop = [...viewer.roots.values()].filter(r => { const o = r.userData.source; return o.layer === 'base' && o.actorClass === 'XComLevelActor' && !o.hidden && !o.environment
        && !viewer.recipeOf(o.id) && !(viewer.families()?.assemblies ?? []).some(a => a.members.includes(o.actor)); }).sort((a, b) => far(a) - far(b))[0];
      return { fx: fx.userData.source.id, snd: snd.userData.source.id, prop: prop.userData.source.id,
               fxActor: fx.userData.source.actor, sndActor: snd.userData.source.actor, sndAt: snd.userData.source.location, fxAt: at }; })()""")
    if not ids: return skip('prefab-effects', 'the Bar has no free effect and sound to group', page, whole=True)
    page.evaluate("ids => { viewer.select(ids.prop); viewer.select(ids.fx, true); viewer.select(ids.snd, true); }", ids)
    page.keyboard.press('Control+g')
    assert len(page.evaluate('viewer.groupList()')) == 1
    records = page.evaluate("(() => { const r = viewer.prefabRecords(); return { tiles: r.tiles, pieces: r.pieces, groups: r.groups, donors: r.donors, left: r.left, counts: r.counts }; })()")
    assert records['left'] == [] and {k: records['counts'][k] for k in ('pieces', 'lights', 'effects', 'sounds')} == dict(pieces=1, lights=0, effects=1, sounds=1), records
    fx, = [p for p in records['pieces'] if p.get('kind') == 'effect']
    snd, = [p for p in records['pieces'] if p.get('kind') == 'sound']
    assert fx['from'] == dict(package=here, level='base', actor=ids['fxActor']) and snd['from'] == dict(package=here, level='base', actor=ids['sndActor'])
    assert all(sorted(p) == ['actor', 'from', 'kind', 'location', 'rotation'] and p['actor'].startswith(p['from']['actor'] + '_copy') for p in (fx, snd)), (fx, snd)
    # they are where they stand: the footprint spans the three places, not the sound's reach
    reach = max(abs(ids['sndAt'][k] - ids['fxAt'][k]) for k in (0, 1)) / 96 + 12
    assert max(records['tiles']) <= reach, (records['tiles'], reach)
    assert len(records['groups']) == 1 and sorted(m['added'] for m in records['groups'][0]['members']) == sorted(p['actor'] for p in records['pieces'])
    assert [d['package'] for d in records['donors']] == [here]
    saved = page.evaluate("n => viewer.savePrefab(n).then(s => ({ id: s.id, revision: s.revision }))", f'Smoke effects {RUN}')
    listed = lambda: page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs']
    row, = [p for p in listed() if p['id'] == saved['id']]
    assert (row['pieces'], row['lights'], row['effects'], row['sounds'], row['maps']) == (1, 0, 1, 1, [here]), row
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    # (effects and sounds came with schema 4; later schemas keep them)
    assert doc['schemaVersion'] >= 4 and sorted(p.get('kind', 'piece') for p in doc['pieces']) == ['effect', 'piece', 'sound']
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    page.wait_for_selector('#prefabList .libitem')
    assert '1 piece, 1 effect and 1 sound' in page.locator('#prefabList .libitem', has_text=f'Smoke effects {RUN}').inner_text()

    def place(page):
        count, fxs = page.evaluate('viewer.roots.size'), page.evaluate('viewer.effectRoots.size')
        page.locator('#prefabList .libitem', has_text=f'Smoke effects {RUN}').click()
        page.wait_for_function('viewer.placing()?.fromList', timeout=180000)
        page.evaluate("viewer.frame('playable')")
        canvas = page.locator('#viewport > canvas').bounding_box()
        points = [(canvas['x'] + canvas['width'] * x, canvas['y'] + canvas['height'] * y) for y in (0.5, 0.6, 0.7, 0.4, 0.3) for x in (0.6, 0.7, 0.5, 0.8, 0.4)]
        at = next((p for p in points if page.evaluate('at=>viewer.placementProblem(at)', list(p)) is None), points[0])
        page.mouse.move(*at)
        page.wait_for_function('viewer.placing()?.ghost.visible')
        page.wait_for_function('viewer.ghostLikenesses() >= 1')      # the effect's likeness comes with the cursor
        page.mouse.click(*at)
        page.wait_for_function('n => viewer.effectRoots.size === n + 2', arg=fxs)
        assert page.evaluate('viewer.roots.size') == count + 1
        added = page.evaluate('viewer.editState().added')
        assert sorted(a.get('kind', 'piece') for a in added) == ['effect', 'piece', 'sound'], added
        assert all(a['from']['package'] == here for a in added) and {a['from']['actor'] for a in added if a.get('kind')} == {ids['fxActor'], ids['sndActor']}
        marked, = [g for g in page.evaluate('viewer.groupList()') if g['prefab']]
        assert marked['prefab']['name'] == f'Smoke effects {RUN}' and len(marked['members']) == 3, marked
        return added

    here_added = place(page)
    # each copy is its own: the copies stand apart from their originals as the prop's copy does from the prop
    assert page.evaluate("[...viewer.effectRoots.values()].filter(r => r.userData.source.added).length") == 2
    page.keyboard.press('Control+z')
    page.wait_for_function("![...viewer.effectRoots.values()].some(r => r.userData.source.added && !r.userData.deleted && r.parent)")
    assert not errors, errors
    maps = page.evaluate("fetch('/maps.json').then(r => r.json())")['maps']
    ready = [m['id'] for m in maps if m.get('ready') and not m.get('outdated') and m['id'] != page.evaluate('viewer.mapId')]
    page.close()
    other = ready[0] if ready else None
    if other:
        page = open_viewer(browser, url.split('?')[0] + f'?map={other}', errors, expected=(409, 422))
        answer_prepare(page)
        if page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"):
            page.keyboard.press('p')
            choose(page, 'libScope', 'prefabs')
            page.wait_for_selector('#prefabList .libitem')
            added = place(page)
            assert page.evaluate("[...viewer.effectRoots.values()].filter(r => r.userData.source.added && r.userData.source.foreign?.package).length") == 2
            page.keyboard.press('p')
            page.keyboard.press('Control+s')
            page.wait_for_selector('#fileDialog:not([hidden])')
            type_project_name(page, f'Prefab effects smoke {RUN}')
            page.locator('#fileName').press('Enter')
            page.wait_for_function('viewer.project()?.revision === 1')
            project = page.evaluate('viewer.project().id')
            key = page.evaluate('viewer.projectState()')
            page.reload(); page.wait_for_function("window.viewer && document.querySelector('#loading').hidden && viewer.project()", timeout=180000)
            assert page.evaluate('viewer.projectState()') == key and not any(page.evaluate('viewer.project().carried').values())
            page.keyboard.press('Control+b')
            page.wait_for_selector('#buildOptions:not([hidden])')
            page.locator('#buildOptionsOk').click()
            page.locator('#buildModal').wait_for(state='visible')
            page.wait_for_function("!document.getElementById('buildTitle').textContent.startsWith('Building')", timeout=600000)
            assert page.locator('#buildTitle').inner_text().startswith(f'Built Prefab effects smoke {RUN}'), page.locator('#buildModal').inner_text()
            build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
            donor, = build['package']['donors']
            assert build['state'] == 'built' and donor['map'] == here and donor['effects'] == 2 and build['package']['foreignPieces'] == 1, build['package']
            page.locator('#buildClose').click()
        assert not errors, errors
        page.evaluate('id => viewer.prefabApi.remove(id)', saved['id'])
        page.close()
    else:
        page = open_viewer(browser, url, errors)
        page.evaluate('id => viewer.prefabApi.remove(id)', saved['id'])
        page.close()


def check_temple_interior(ctx):
    """TempleShip (export 11) opens in Interior: its backdrop, roof and helpers hidden, every piece where its matrix
    says; the report counts the pieces then drawn."""
    page = ctx.page
    assert ctx.report['initialView'] == 'interior'
    assert page.evaluate("[...viewer.roots.values()].every(r=>!['backdrop','roof','helper'].includes(r.userData.source.sceneryRole)||!r.visible)")
    assert page.evaluate("[...viewer.roots.values()].every(r=>r.userData.source.matrix.every((v,i)=>Math.abs(v-r.matrix.elements[i])<1e-5))")
    ctx.report['interiorPieces'] = page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
    page.screenshot(path=str(ctx.shot('interior')))


def check_skins(ctx):
    """Skinned meshes (export 7) posed by their own skeletons, copies with skeletons of their own; a door and a prop
    pictured alone."""
    page = ctx.page
    skin=page.evaluate("""async () => {
      const T=await import('/vendor/three/three.module.js');
      const rigs=[];let error=0;
      viewer.world.updateMatrixWorld(true);
      for (const root of viewer.roots.values()) root.traverse(part=>{
        if (!part.isSkinnedMesh) return;
        part.skeleton.update();rigs.push(part);
        const position=part.geometry.attributes.position;
        for (let i=0;i<Math.min(12,position.count);i++) {
          const original=new T.Vector3().fromBufferAttribute(position,i);
          const posed=part.applyBoneTransform(i,original.clone());
          error=Math.max(error,original.distanceTo(posed));
        }
      });
      const copies=rigs.filter(r=>r.geometry===rigs[0].geometry && r!==rigs[0]);
      return {rigs:rigs.length,error,independent:copies.every(r=>r.skeleton!==rigs[0].skeleton && r.skeleton.bones[0]!==rigs[0].skeleton.bones[0])};
    }""")
    expected=page.evaluate("viewer.data.objects.filter(o=>viewer.data.meshes[o.mesh].kind==='skeletal').length")
    assert skin['rigs'] >= expected,skin
    if ctx.is_bar and page.evaluate('viewer.data.scope === "map"'): assert skin['rigs'] >= 21,skin
    assert skin['error'] < 0.02,skin
    assert skin['independent'],skin
    for actor_class,label in [('XComInteractiveLevelActor','door'),('KAsset','prop')]:
        if not page.evaluate('cls=>[...viewer.roots.values()].some(r=>r.userData.source.actorClass===cls)',actor_class):
            skip('skins', f'the map has no {label} ({actor_class}) to picture')
            continue
        page.evaluate("""cls=>{
          window.detailVisibility=[...viewer.roots.values()].map(r=>[r,r.visible]);
          const root=[...viewer.roots.values()].find(r=>r.userData.source.actorClass===cls);
          for (const r of viewer.roots.values()) r.visible=r===root;
          viewer.select(root.userData.source.id);viewer.frame(root);
        }""",actor_class)
        settled(page, CAMERA)
        page.screenshot(path=str(ctx.shot(label)))
        page.evaluate('for (const [root,visible] of detailVisibility) root.visible=visible; viewer.frame();')


def check_map_lights(ctx):
    """The map's own lights (export 9): neutral light by default (chosen 7 November), the map's
    switchable, and every local light inside the shader's grid; each lighting mode pictured."""
    page = ctx.page
    lights = page.evaluate("viewer.lighting.counts")
    assert lights['enabled'] > 0 and value(page,'lighting') == 'neutral', lights
    assert page.evaluate("document.getElementById('areaLights').disabled")      # (no say in the Neutral look)
    choose(page,'lighting','game')
    assert not page.evaluate("document.getElementById('areaLights').disabled")
    assert page.evaluate("viewer.lighting.grid.local.length") == lights['local']
    assert 'local lights' in page.locator('#lightCount').text_content()
    assert 'dropped' not in page.locator('#lightCount').text_content()
    if page.evaluate('viewer.data.exporterVersion >= 10'):
        assert page.evaluate("""() => {
          const {cells,indices}=viewer.lighting.packed;
          return viewer.lighting.grid.lists.every((list,c)=>{
            const first=cells[c*4],count=cells[c*4+1];
            return count===list.length && list.every((id,n)=>indices[first+n]===id);
          });
        }""")
    check_game_frame(page)
    check_baked_light(page)
    # the Game look without and with its area lights, then the Neutral look, each pictured; K switches the look
    for mode, area in (('game', False), ('game', True), ('neutral', True)):
        page.evaluate('on => { const a = document.getElementById("areaLights"); a.checked = on; a.onchange(); }', area)
        choose(page,'lighting',mode)
        page.wait_for_timeout(300)      # (a frame drawn in the new light for the picture)
        page.screenshot(path=str(ctx.shot('light-%s%s' % (mode, '' if area else '-no-area'))))
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('k')
    assert value(page, 'lighting') == 'game'
    page.keyboard.press('k')
    assert value(page, 'lighting') == 'neutral'
    assert page.evaluate("viewer.sun.intensity > 0 && viewer.hemisphere.intensity > 0")


GAME_FRAME = """async () => {
  const T = await import('/vendor/three/three.module.js');
  const v = viewer, r = v.renderer, gl = r.getContext(), size = new T.Vector2();
  const read = (x, y) => { const p = new Uint8Array(4); gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p); return [...p.slice(0, 3)]; };
  const middle = () => { r.getDrawingBufferSize(size); return [Math.floor(size.x / 2), Math.floor(size.y / 2)]; };
  // a helper's square before the camera, and one under the map's ground at the camera's target (hidden by it)
  const square = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ color: 0xd04020, side: T.DoubleSide }));
  const away = new T.Vector3(); v.camera.getWorldDirection(away);
  square.position.copy(v.camera.position).addScaledVector(away, 10); square.lookAt(v.camera.position); square.scale.setScalar(2);
  v.world.add(square);
  try {
    const [x, y] = middle();
    v.post.draw(true); const game = read(x, y);
    r.render(v.world, v.camera); const neutral = read(x, y);
    square.position.copy(v.controls.target).addScaledVector(away, 3000); square.scale.setScalar(400); square.updateMatrixWorld(true);
    v.post.draw(true); const hidden = read(x, y);
    r.render(v.world, v.camera); const hiddenBefore = read(x, y);
    return { game, neutral, hidden, hiddenBefore };
  } finally { v.world.remove(square); square.geometry.dispose(); square.material.dispose(); }
}"""

FOG_BANDS = """async () => {
  const v = viewer, fog = v.post.fog.fogOn, on = fog.value;
  // a low camera over the map: the picture's top is far away, its bottom near
  const box = new (v.camera.position.constructor)(), centre = v.controls.target.clone();
  v.camera.position.copy(centre).add(box.set(0, 900, -2400)); v.controls.update(); v.camera.updateMatrixWorld(true);
  const pixels = async () => {
    const picture = new Image(); picture.src = v.grabView(); await picture.decode();
    const c = document.createElement('canvas'), w = c.width = picture.width, h = c.height = picture.height, g = c.getContext('2d');
    g.drawImage(picture, 0, 0);
    return { w, h, data: g.getImageData(0, 0, w, h).data };
  };
  try {
    const fogged = await pixels(); fog.value = 0; const clear = await pixels();
    // how much the fog changed each tenth of the picture, top to bottom (the sky and the background take none)
    const bands = [];
    for (let b = 0; b < 10; b++) {
      let sum = 0, n = 0;
      for (let y = Math.floor(fogged.h * b / 10); y < Math.floor(fogged.h * (b + 1) / 10); y++) {
        for (let i = y * fogged.w * 4; i < (y + 1) * fogged.w * 4; i += 4) { sum += Math.abs(fogged.data[i] - clear.data[i]) + Math.abs(fogged.data[i + 1] - clear.data[i + 1]) + Math.abs(fogged.data[i + 2] - clear.data[i + 2]); n++; }
      }
      bands.push(+(sum / n).toFixed(2));
    }
    return bands;
  } finally { fog.value = on; v.frame(); }
}"""


BAKED_POOL = """async () => {
  const v = viewer;
  // the first of the map's static spot lights that points down: its beam meets the ground below it
  const lamp = v.lightRecords().find(l => l.role === 'static' && l.kind === 'spot' && l.enabled && l.direction[2] < -0.9);
  if (!lamp) return null;
  const t = lamp.location[2] / -lamp.direction[2];
  const hit = [0, 1, 2].map(k => lamp.location[k] + lamp.direction[k] * t);
  v.controls.target.set(hit[0], 0, hit[1]); v.camera.position.set(hit[0] + 1, 1200, hit[1] + 1);
  v.controls.update(); v.camera.updateMatrixWorld(true);
  const picture = new Image(); picture.src = v.grabView(); await picture.decode();
  const c = document.createElement('canvas'), w = c.width = picture.width, h = c.height = picture.height, g = c.getContext('2d');
  g.drawImage(picture, 0, 0);
  const mean = (x0, y0, size) => { const d = g.getImageData(x0, y0, size, size).data; let s = 0; for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2]; return s / (d.length / 4); };
  const s = Math.round(h / 12), centre = mean(Math.round(w / 2 - s / 2), Math.round(h / 2 - s / 2), s);
  const corners = [mean(0, 0, s), mean(w - s, 0, s), mean(0, h - s, s), mean(w - s, h - s, s)];
  v.frame();
  return { lamp: lamp.id, centre, corners };
}"""


def check_baked_light(page):
    """The map's baked light in the Game look (game-likeness plan, B2 and B3), on a map of export 44: the lightmaps
    loaded once the Game look is on, every lightmapped piece's parts lit by them with the materials still shared; a
    street lamp's pool on the ground is where the map's light is (its static light is drawn by the lightmap alone);
    the sun's shadow maps packed and taken."""
    if page.evaluate('(viewer.data.exporterVersion || 0) < 44 || !viewer.data.objects.some(o => o.lightmap)'):
        return
    page.wait_for_function('viewer.post.ready() && viewer.post.baked() && viewer.post.baked().on', timeout=120000)
    baked = page.evaluate('viewer.post.baked()')
    assert baked['parts'] > 100 and baked['atlas'], baked
    # B3: the sun's shadow from the pieces' shadow maps, packed into one atlas; none of the sun on a piece wholly in
    # its shadow (export 45)
    if page.evaluate('viewer.data.objects.some(o => o.lightmap && o.sunShadow && !o.sunShadow.factor)'):
        assert baked['shadows'] > 0 and baked['shadowAtlas'] and baked['sunShadows'], baked
    if page.evaluate('viewer.data.objects.some(o => o.lightmap && o.sunIrrelevant)'):
        assert baked['sunless'] > 0, baked
    pool = page.evaluate(BAKED_POOL)
    if pool:
        assert pool['centre'] > max(pool['corners']) and pool['centre'] > 1.5 * sum(pool['corners']) / 4, pool


def check_game_frame(page):
    """The Game look's frame (game-likeness plan, C2 and C3): drawn through the chain once its shaders are compiled, a
    helper drawn after it keeps its own colour and is still hidden behind the map's pieces; the map's fog changes the
    far part of the view more than the near."""
    page.wait_for_function('viewer.post.ready()', timeout=300000)
    probe = page.evaluate(GAME_FRAME)
    assert all(abs(a - b) <= 2 for a, b in zip(probe['game'], probe['neutral'])), probe        # (its own colour)
    assert probe['game'][0] > probe['game'][1] + 40, probe
    # under the ground: hidden in the Game look wherever the Neutral look's frame hides it (by the scene's depth)
    square = lambda p: all(abs(a - b) <= 6 for a, b in zip(p, probe['game']))
    assert square(probe['hidden']) == square(probe['hiddenBefore']), probe
    if page.evaluate('Boolean(viewer.data.atmosphere?.world?.fog?.bEnabled)'):
        bands = page.evaluate(FOG_BANDS)
        assert max(bands[:8]) > 1.2 * bands[9] and max(bands) > 1, bands      # (farther up the picture: more fog)


def own_piece(page, is_bar):
    """The piece typed-pose and adding pick: a dumpster on the Bar, else the first of the map's drawn pieces' meshes."""
    term = 'Dumpster_A' if is_bar else page.evaluate("viewer.data.meshes[viewer.data.objects.find(o=>!o.hidden && !o.environment).mesh].name.split('.').at(-1)")
    return page.evaluate("term => [...viewer.roots].find(([, r]) => !r.userData.source.hidden && !r.userData.source.environment"
                         " && viewer.data.meshes[r.userData.source.mesh].name.endsWith(term))[0]", term)


def check_typed_pose(ctx):
    """A picked piece opens its panel; a typed position moves the selection without turning it, as one undo step, and
    so does a typed yaw."""
    page = ctx.page
    page.keyboard.press('Escape')
    assert page.locator('#viewOptions').is_hidden()
    page.evaluate('viewer.select(null)')
    assert page.locator('#inspector').is_hidden() and page.locator('#finder').count() == 0
    page.evaluate('id => viewer.select(id)', own_piece(page, ctx.is_bar))
    assert page.locator('#inspector').is_visible() and page.locator("#details h2").inner_text()
    start = page.evaluate('viewer.gizmo.pose()')
    page.locator('#posX').fill(f"{start['location'][0] + 48:.2f}"); page.locator('#posX').press('Enter')
    moved = page.evaluate('viewer.gizmo.pose()')
    assert abs(moved['location'][0] - start['location'][0] - 48) < 0.01, (start, moved)
    assert all(abs(moved['location'][i] - start['location'][i]) < 1e-6 for i in (1, 2)), (start, moved)
    assert all(abs(moved['rotation'][i] - start['rotation'][i]) < 1e-6 for i in range(3)), (start, moved)
    assert page.locator('#editCount').is_visible() and page.locator('#editUndo').is_visible()
    assert page.locator('#editResetAll').is_visible() and not page.locator('#editReset').is_disabled()
    page.locator('#rotY').fill(f"{start['rotation'][1] + 90:.2f}"); page.locator('#rotY').press('Enter')
    turned = page.evaluate('viewer.gizmo.pose()')
    assert abs((turned['rotation'][1] - start['rotation'][1] - 90 + 180) % 360 - 180) < 0.01, (start, turned)
    assert all(abs(turned['location'][i] - moved['location'][i]) < 0.01 for i in range(3)), (moved, turned)
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.gizmo.edited().length') == 0
    assert page.locator('#editCount').is_hidden() and page.locator('#editResetAll').is_hidden()


def check_squad_run(ctx):
    """The squad check; with --squad (the server's --squad a scratch file) it saves too and puts the squad back."""
    check_squad(ctx.page, saves=ctx.args.squad)
    # (with --squad its save from elsewhere is refused on purpose: the 409 the page logs is the check's own)
    if ctx.args.squad:
        ctx.errors.difference_update({e for e in ctx.errors if '409' in e and ('/squad.json' in e or e.startswith('Failed to load resource'))})


# the header's parts: how far it overflows, the Project and Map buttons' widths, the edit summary
HEADER_PARTS = """() => { const h = document.querySelector('header'), chip = document.getElementById('editCount');
  const width = id => document.getElementById(id).getBoundingClientRect().width;
  return { over: h.scrollWidth - h.clientWidth, project: width('projectButton'), map: width('mapButton'),
           chip: chip.hidden ? null : { text: chip.textContent, title: chip.title, cut: chip.scrollWidth > chip.clientWidth,
                                        ellipsis: getComputedStyle(chip).textOverflow === 'ellipsis' } }; }"""


def check_narrow_header(browser, url):
    """In a window 1024 wide, a long edit summary (a clear's: pieces deleted, lights, landing zones, buildings, spawn
    points) is cut with an ellipsis and whole in its title, the Project and Map buttons keep their widths, and nothing
    is pushed out of the header. A page of its own; nothing is saved."""
    errors = []
    page = open_viewer(browser, url, errors)
    answer_prepare(page)
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 22 && !viewer.project()"):
        return skip('header', 'the narrow header\'s long summary needs a map of export 22 or later to clear, with no project open', page)
    page.set_viewport_size(dict(width=1024, height=768))
    rest = page.evaluate(HEADER_PARTS)
    assert rest['over'] <= 0 and rest['chip'] is None, rest
    page.evaluate('viewer.clearMap(null)')
    page.wait_for_function('viewer.changes().total > 0')
    long = page.evaluate(HEADER_PARTS)
    assert long['chip'] and long['chip']['cut'] and long['chip']['ellipsis'] and long['chip']['title'] == long['chip']['text'], long
    assert long['over'] <= 0 and long['project'] == rest['project'] and long['map'] == rest['map'], (rest, long)
    page.close()
    assert not errors, errors
    return dict(rest=rest, long=long)


def check_header(ctx):
    """The header's Selected, framing a piece it picks (the button is off with nothing selected, as a check before it
    may leave things), and Frame, and View options' grid. The selection it found is put back. Then, on a page of its
    own, the header 1024 wide with a long edit summary (check_narrow_header)."""
    page = ctx.page
    held = page.evaluate('viewer.gizmo.active')
    piece = page.evaluate("""[...viewer.roots.values()].find(r => r.visible && !r.userData.deleted && !r.userData.source.hidden
      && !r.userData.source.environment)?.userData.source.id ?? null""")
    assert piece, 'no piece drawn to select'
    page.evaluate('id => viewer.select(id)', piece)
    page.locator("#selected").click()
    assert page.evaluate("""async id => { const T = await import('/vendor/three/three.module.js');
      return new T.Box3().setFromObject(viewer.roots.get(id)).expandByScalar(2).containsPoint(viewer.controls.target); }""", piece)
    page.locator("#frame").click()
    check_option(page,'grid',False)
    check_option(page,'grid',True)
    page.evaluate('id => viewer.select(id)', held)
    narrow = check_narrow_header(ctx.browser, page.url)
    return dict(narrow=narrow) if narrow else None


def check_floors_cut(ctx):
    """The floor picker cuts the buildings: on Bar (export 4) the roof's fracturing piece drawn opaque and hidden on
    the ground floor, the pieces cut by height; elsewhere fewer pieces drawn on the ground floor and all again."""
    page = ctx.page
    if ctx.is_bar and page.evaluate("viewer.data.exporterVersion >= 4 && viewer.data.buildings.length > 0"):
        assert page.evaluate("""() => {
          const roof=[...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComFracLevelActor_3'));
          if (!roof) return false;
          const materials=[]; roof.traverse(o=>{if(o.isMesh) materials.push(o.material)});
          return roof.visible && materials.every(m=>m.alphaTest===0 && !m.transparent && (!m.map || m.map.flipY===false));
        }""")
        choose(page,'floor','1')
        assert page.evaluate("""() => ![...viewer.roots.values()].find(r=>r.userData.source.actor.endsWith('.XComFracLevelActor_3')).visible""")
        assert page.evaluate("[...viewer.roots.values()].some(r=>r.visible && Number.isFinite(r.userData.cutHeight))")
        page.wait_for_timeout(300)      # (a frame drawn cut for the picture)
        page.screenshot(path=str(ctx.shot('ground')))
        choose(page,'floor','all')
    elif page.evaluate('viewer.data.buildings.length > 0'):
        before=page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
        choose(page,'floor','1')
        after=page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
        assert 0 < after <= before,(before,after)
        if ctx.is_temple: assert after < before,(before,after)
        page.screenshot(path=str(ctx.shot('ground')))
        choose(page,'floor','all')
        assert page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')==before
    else:
        return skip('floors-cut', 'the map has no buildings', whole=True)


def check_dense(ctx):
    """Lights past 128 reach the GPU (check_dense_lighting), and the light grid packs 300 lights in one cell, with the
    area lights filtered out on request."""
    check_dense_lighting(ctx.browser, ctx.args.url)
    assert ctx.page.evaluate("""async () => {
      const {buildLightGrid,packLightGrid}=await import('/light_grid.js');
      const lights=Array.from({length:300},(_,i)=>({location:[-30,20,0],radius:128,role:i%2?'area':'static'}));
      const grid=buildLightGrid(lights), packed=packLightGrid(grid), filtered=packLightGrid(grid,l=>l.role!=='area');
      return grid.deepest===300 && packed.deepest===300 && filtered.deepest===150
        && grid.lists.every((list,c)=>list.every((id,n)=>packed.indices[packed.cells[c*4]+n]===id));
    }""")


def check_frame_bounds(ctx):
    """Frame puts the visible bounds (the play area's) wholly in view."""
    page = ctx.page
    page.locator('#frame').click()
    assert page.evaluate("""async () => {
      const T=await import('/vendor/three/three.module.js');
      const {visibleBounds}=await import('/view_layout.js');
      const box=visibleBounds(viewer.roots,viewer.data.playableBounds);
      viewer.camera.updateMatrixWorld(true);
      return [0,1].every(x=>[0,1].every(y=>[0,1].every(z=>{
        const v=new T.Vector3(x?box.max.x:box.min.x,y?box.max.y:box.min.y,z?box.max.z:box.min.z).project(viewer.camera);
        return Math.abs(v.x)<=1 && Math.abs(v.y)<=1 && Math.abs(v.z)<=1;
      })));
    }""")


def check_tile_grid_view(ctx):
    """check_tile_grid, then Interior chosen and framed (as the tile footprints are looked at)."""
    check_tile_grid(ctx.page)
    choose(ctx.page,'scenery','interior');ctx.page.locator('#frame').click()


def check_wire(ctx):
    """View options' Wire draws every piece as wire, on the floors cut too, and off again."""
    page = ctx.page
    check_option(page,'wire',True)
    if page.evaluate('viewer.data.buildings.length > 0'):
        choose(page,'floor','1');choose(page,'floor','all')
    assert page.evaluate("""() => [...viewer.roots.values()].every(root=>{
      let ok=true;root.traverse(p=>{if(p.isMesh && p.userData.baseMaterial)ok &&= p.material.wireframe;});return ok;
    })""")
    check_option(page,'wire',False)


def check_footprints(ctx):
    """check_tile_footprints in Interior, which cuts at the sides and by the height, but draws a piece reaching into the
    area whole (by the height only); Full again after."""
    page = ctx.page
    check_tile_footprints(page)
    if value(page,'scenery') != 'interior': choose(page,'scenery','interior')
    assert page.evaluate("[...viewer.roots.values()].filter(r=>r.visible).every(r=>r.userData.clippingPlanes.length>=(r.userData.interiorWhole?2:6))")
    choose(page,'scenery','full')


def check_temple_look(ctx):
    """TempleShip's alien materials: emissive maps and glowing energy, and no alpha test where the material isn't
    masked."""
    appearance=ctx.page.evaluate("""() => {
      let emissive=0,energy=0,wrongMasks=0;
      for(const root of viewer.roots.values()) root.traverse(part=>{
        if(!part.isMesh)return;
        const material=part.userData.baseMaterial;
        const info=viewer.data.materials[root.userData.source.materials[0]];
        if(info?.render.family==='alien' && material.emissiveMap)emissive++;
        if(info?.render.family==='alien-energy' && material.emissiveIntensity>0)energy++;
        if(info?.render.family==='alien' && !info.staticSwitches.OpacityMasked && material.alphaTest!==0)wrongMasks++;
      });
      return {emissive,energy,wrongMasks};
    }""")
    assert appearance['emissive']>0 and appearance['energy']>0 and appearance['wrongMasks']==0,appearance


def check_previews(ctx):
    """The map's patch previews (no menu: they open by address, ?scene=preview-<n>.json): copies and the six spawns
    drawn, patch_bar's inherited records and lights, the hidden pieces staying hidden on every floor; each pictured.
    It leaves the map, so it comes last."""
    page = ctx.page
    previews=[]
    assert page.locator('#scene').count() == 0 and page.locator('#building').count() == 0
    # the export's previews (export 37 lists them nowhere): preview-0.json, preview-1.json, ... while the server has
    # them, asked outside the page (no console error for the first one missing)
    folder = urlunsplit((*urlsplit(page.url)[:2], f"/cache/{quote(page.evaluate('viewer.mapId'))}/", '', ''))
    options = []
    while page.request.head(f'{folder}preview-{len(options)}.json').ok: options.append(f'preview-{len(options)}.json')
    if not options: return skip('previews', 'the map\'s export has no patch previews (an export with --spec makes them)', whole=True)
    for option in options:
        url=urlsplit(page.url)
        query='&'.join(p for p in url.query.split('&') if p and not p.startswith(('scene=','project=')))
        page.goto(urlunsplit((url.scheme,url.netloc,url.path,f'{query}&scene={option}'.lstrip('&'),'')),wait_until='load')
        page.wait_for_function("window.viewer && viewer.data.preview && document.querySelector('#loading').hidden",timeout=120000)
        assert page.locator('#previewChip').is_visible()
        assert page.evaluate("[...viewer.roots.values()].some(r=>r.userData.source.provenance?.type==='copy')")
        assert page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.provenance?.type==='spawn').length") == 6
        if page.evaluate('viewer.data.exporterVersion >= 7'):
            assert page.evaluate('viewer.data.preview.notes.length') == 0
            if option=='preview-0.json':
                assert page.evaluate("viewer.data.inheritedPatches[0].name")=='patch_bar'
                assert page.evaluate('viewer.data.inheritedPatches[0].components')==17
                assert page.evaluate("viewer.data.inheritedPatches[0].records.filter(r=>r.actorClass==='XComRebuildWorldDataVolume').length")==8
                assert page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.layer==='inherited' && r.visible).length")==0
                assert page.locator('#hideHelpers').is_checked()   # hidden by default
                check_option(page,'hideHelpers',False)
                # EXP-07 explicitly hides XComLevelActor_44 by short name;
                # that also removes the inherited actor with that name.
                assert page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.layer==='inherited' && r.visible).length")==16
                check_option(page,'hideHelpers',True)
            else:assert page.evaluate('viewer.data.inheritedPatches?.length || 0')==0
        if page.evaluate('viewer.data.exporterVersion >= 9'):
            lights=page.evaluate("viewer.data.lights.map(l=>[l.layer,l.enabled])")
            if option=='preview-0.json':
                assert sum(1 for layer,_ in lights if layer=='inherited')==3, lights
            else:
                # The blank layout's hider takes the map's lights; its own sun object lights the map.
                assert any(layer=='patch' and on for layer,on in lights), lights
                assert not any(layer=='base' and on for layer,on in page.evaluate(
                    "viewer.data.lights.filter(l=>l.kind==='directional'||l.kind==='sky').map(l=>[l.layer,l.enabled])"))
        hidden=page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.hiddenBy != null).length")
        assert hidden>0
        choose(page,'floor','1')
        assert page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.hiddenBy != null && r.visible).length") == 0
        choose(page,'floor','all')
        assert page.evaluate("[...viewer.roots.values()].filter(r=>r.userData.source.hiddenBy != null && r.visible).length") == 0
        page.wait_for_timeout(300)      # (a frame drawn for the picture)
        page.screenshot(path=str(ctx.shot(option.removesuffix('.json'))))
        previews.append(page.evaluate("({name:viewer.data.name,pieces:[...viewer.roots.values()].filter(r=>r.visible).length,notes:viewer.data.preview.notes.length})"))
    ctx.report['previews']=previews


def editing(name, *more):
    """A check of browser_editing.py: run(browser, url, open_viewer, *more)."""
    def run(ctx):
        import browser_editing
        extra = [dict(save_dialog=save_dialog)[m] for m in more]
        return getattr(browser_editing, f'check_{name}')(ctx.browser, ctx.page.url, *([] if name == 'failed_reads' else [open_viewer]), *extra)
    return run


def run_builder(ctx):
    from browser_builder import (check_builder, check_real_sources, check_navigation, check_recovery_edges, check_recipe_recovery,
                                 check_this_prefab)
    url = ctx.page.url
    result = check_builder(ctx.browser, url, ctx.args.screenshot)
    result['realSources'] = check_real_sources(ctx.browser, url, result['buildingOnly'], ctx.args.screenshot)
    result['navigation'] = check_navigation(ctx.browser, url, result['buildingOnly'], result['realSources']['project'])
    result['recoveryEdges'] = check_recovery_edges(ctx.browser, url, result['buildingOnly'])
    result['recipeRecovery'] = check_recipe_recovery(ctx.browser, url)
    result['thisPrefab'] = check_this_prefab(ctx.browser, url)
    return result


def run_output_names(ctx):
    found = []
    result = check_output_names(ctx.browser, ctx.page.url, found)
    ctx.errors.update(found)
    return result


def on_page(*checks):
    """A run that does each check(page) on the main page; skipped whole (WHOLE) when each of them skipped itself whole."""
    def run(ctx):
        done = [check(ctx.page) for check in checks]
        return WHOLE if all(d is WHOLE for d in done) else None
    return run


def version(n):
    return lambda c: None if c.version >= n else f'needs export {n} or later (this map is export {c.version})'


def all_of(*tests):
    return lambda c: next((why for test in tests if (why := test(c))), None)


ON_MAP = lambda c: None if c.scope == 'map' else f'needs a map, not a {c.scope}'                       # noqa: E731
ON_BAR = lambda c: None if c.is_bar else 'URB_Bar only (it checks the Bar\'s own pieces)'               # noqa: E731
ON_POLICE = lambda c: None if c.is_police else 'URB_PoliceStation only'                                # noqa: E731
ON_TEMPLE = lambda c: None if c.is_temple else 'TempleShip only'                                       # noqa: E731
WITH_TILE_GRID = lambda c: None if c.tile_grid else 'the map has no tile grid'                         # noqa: E731


class Check(NamedTuple):
    """A check the run can do. run(ctx) returns a result for the report, or None. needs: what the server must be
    started with (NEEDS). when(ctx): None, or why this map can't have the check. full: the whole run does it (the rest
    only when --only names them)."""
    name: str
    run: Callable
    words: str
    needs: tuple = ()
    when: Callable = None
    full: bool = True


# What a check can need of the server: the flag that says so (None: asked of the server itself), and the words.
NEEDS = {
    'projects': ('projects', 'needs --projects: a test server started with --projects and --builds in scratch folders (it saves)'),
    'play': ('play', 'needs --play: a test server started with --install <a scratch game folder> --dry-play'),
    'settings': (None, 'needs a test server whose settings file is a scratch one (XCOM_MAP_WORKSHOP_SETTINGS): it writes '
                       'the favourites and recently used pieces beside it'),
}

# Every check, in the order the whole run does them (the view is set to Full after temple-interior; the picture and
# the report's numbers are taken before previews, which leaves the map).
CHECKS = (
    Check('temple-interior', check_temple_interior, 'TempleShip opens in Interior, its backdrop, roof and helpers hidden',
          when=all_of(ON_TEMPLE, version(11))),
    Check('api-names', lambda c: __import__('api_names').check(c), 'window.viewer\'s names on the Bar, the blank map and in the '
          'builder, as viewer_api_names.json records them (pages of its own)'),
    Check('streams', on_page(check_streams), 'the missions\' streamed packages, their mission select and pieces'),
    Check('spawns', on_page(check_spawns_view, check_spawn_edits), 'the Spawns view and spawn edits'),
    Check('skins', check_skins, 'skinned meshes posed by their own skeletons; a door and a prop pictured', when=version(7)),
    Check('map-lights', check_map_lights, 'the map\'s own lights: neutral by default, the map\'s switchable, the shader\'s grid',
          when=all_of(version(9), ON_MAP)),
    Check('typed-pose', check_typed_pose, 'a picked piece\'s panel; a typed position and yaw, each one undo step'),
    Check('pivot', on_page(check_pivot), 'the orbit pivot'),
    Check('text-select', on_page(check_text_select), 'text is selectable only where it is meant to be'),
    Check('recipe', on_page(check_recipe), 'doors, ladders, cars and vans: linked pieces and the recipe snap',
          when=all_of(ON_BAR, version(12))),
    Check('light-bar', on_page(check_light_bar), 'the police station\'s light bar', when=all_of(ON_POLICE, version(16))),
    Check('destruction', lambda c: check_destruction(c.page, c.is_bar), 'what breaks and what it leaves', when=version(17)),
    Check('adding', lambda c: check_adding(c.page, c.is_bar), 'the Add panel\'s pieces placed'),
    Check('zoom', on_page(check_zoom), 'the wheel zooms to the point under the cursor'),
    Check('groups', on_page(check_groups), 'groups: Group, Ungroup, nested, the panel'),
    Check('copy-drag', on_page(check_copy_drag), 'a copy dragged off with Alt'),
    Check('box-select', on_page(check_box_select), 'box select'),
    Check('floor-boxes', on_page(check_floor_boxes), 'buildings\' floor boxes'),
    Check('cursor-floors', on_page(check_cursor_floors), 'a building\'s floors as the cursor\'s'),
    Check('map-buildings', on_page(check_map_buildings), 'the map\'s own buildings edited'),
    Check('clear-map', on_page(check_clear_map), 'Clear map, the map grid and the landing zones'),
    Check('map-settings', on_page(check_map_settings), 'Map settings: the sun and sky listed, the background sound and its volume, what '
                                                             'Long War Rebalance is told of the map'),
    Check('align', on_page(check_align), 'Align'),
    Check('library', lambda c: check_library(c.page, c.is_bar), 'the Add panel: this map\'s pieces'),
    Check('cover', on_page(check_cover), 'cover blocks and invisible floors'),
    Check('floor-placing', lambda c: check_floor_placing(c.page, c.is_bar), 'floor pieces placed and stacked'),
    Check('floor-tiles', lambda c: check_floor_tiles(c.page, c.is_bar), 'View options\' Floor tiles'),
    Check('lights', lambda c: check_lights(c.page, c.is_bar), 'lights edited, Solo, copied and deleted', when=ON_MAP),
    Check('effects', on_page(check_effects_view, check_effects_editing, check_effects_box), 'the Effects view and effect edits'),
    Check('flares', on_page(check_flares), 'lens flares'),
    Check('likeness', lambda c: check_likeness(c.page), 'effects drawn by their likeness'),
    Check('project-menu', on_page(check_project_menu), 'the Project menu'),
    Check('squad', check_squad_run, 'the test squad (it saves only with --squad)'),
    Check('projects', lambda c: check_projects(c.browser, c.page.url), 'projects saved, reopened and recovered', needs=('projects',)),
    Check('prefabs', lambda c: check_prefabs(c.browser, c.page.url), 'the prefab library', needs=('projects',)),
    Check('prefab-effects', lambda c: check_prefab_effects(c.browser, c.page.url), 'a prefab with an effect and a sound',
          needs=('projects',)),
    Check('play', lambda c: check_play(c.browser, c.page.url, c.args.play_project, c.args.screenshot),
          'Play in game, Game maps\' Undo everything, Installs', needs=('play',)),
    Check('prepare', lambda c: check_prepare(c.browser, c.page.url, c.args.play_project if c.args.play else None),
          'the prepare-again dialog'),
    Check('header', check_header, 'the header\'s Selected and Frame; View options\' grid; a long edit summary 1024 wide'),
    Check('floors-cut', check_floors_cut, 'the floor picker cuts the buildings'),
    Check('dense-lighting', check_dense, 'lights past 128 reach the GPU; the light grid packs 300', when=version(10)),
    Check('light-grid', on_page(check_light_grid), 'the light grid covers only the map\'s pieces'),
    Check('frame-bounds', check_frame_bounds, 'Frame shows the visible bounds whole', when=version(10)),
    Check('pan', on_page(check_arrow_pan), 'the arrow keys pan, but not in a text field'),
    Check('play-area', on_page(check_play_area, check_interior_whole), 'the play area\'s walls; Interior draws whole pieces'),
    Check('tile-grid', check_tile_grid_view, 'the tile grid', when=WITH_TILE_GRID),
    Check('wire', check_wire, 'View options\' Wire', when=version(10)),
    Check('tile-footprints', check_footprints, 'the tile footprints; Interior\'s cuts', when=version(11)),
    Check('temple-look', check_temple_look, 'TempleShip\'s alien materials', when=all_of(ON_TEMPLE, version(10))),
    Check('previews', check_previews, 'the map\'s patch previews (it leaves the map, so it is last)'),
    # only when named (--all runs them on servers of their own)
    Check('speeds', on_page(check_camera_speeds), 'the camera\'s speeds', full=False),
    Check('library-all', lambda c: check_library_all(c.browser, c.page.url), 'the Add panel\'s All maps', needs=('settings',),
          full=False),
    Check('library-effects', lambda c: check_library_effects(c.browser, c.page.url), 'effects and sounds from All maps',
          needs=('settings',), full=False),
    Check('effect-values', lambda c: check_effect_values(c.browser, c.page.url), 'an effect\'s and a sound\'s values', full=False),
    Check('library-flares', lambda c: check_library_flares(c.browser, c.page.url), 'lens flares from All maps',
          needs=('settings',), full=False),
    Check('library-assembly', lambda c: check_library_assembly(c.browser, c.page.url), 'assemblies from All maps',
          needs=('settings',), full=False),
    Check('output-names', run_output_names, 'maps named after the project', needs=('projects',), full=False),
    Check('builder', run_builder, 'the prefab builder and its This prefab tab', needs=('projects',), full=False),
    Check('prefab-test', lambda c: __import__('browser_prefab_test').check_prefab_test(c.browser, c.page.url, c.args.screenshot),
          'the builder\'s Test in game', needs=('projects',), full=False),
    Check('walls', lambda c: __import__('browser_walls').check_walls(c.browser, c.page.url, open_viewer, type_project_name, project_url),
          'made walls, floors and ground drawn, edited, saved and built (on the police station)', needs=('projects',), full=False),
    Check('looks', lambda c: __import__('browser_looks').check_looks(c.browser, c.page.url, open_viewer),
          'the look picker (on the police station)', full=False),
    Check('precache-pictures', lambda c: __import__('browser_precache').check_precache_pictures(c.browser, c.page.url, open_viewer),
          "Cache everything's pictures: a few drawn in the page and kept, what they loaded let go; Start and Cancel with only "
          'them ticked (it puts pictures into the cache it serves)', full=False),
    Check('made-break', lambda c: __import__('browser_walls').check_made_break(c.browser, c.page.url, open_viewer, skip),
          'Break, Breaks further and Repair on a made wall, floor and roof', when=ON_MAP, full=False),
    Check('made-openings', lambda c: __import__('browser_walls').check_made_openings(c.browser, c.page.url, open_viewer),
          'Delete takes out the gap or hole last touched; a free floor\'s tiles and a turned one\'s cursor steps; a wall in '
          'a tile row', when=ON_MAP, full=False),
    Check('rock-corner', lambda c: __import__('browser_walls').check_rock_corner(c.browser, c.page.url, open_viewer),
          'a rock\'s corner moved with the point gizmo', when=ON_MAP, full=False),
    Check('room-buttons', lambda c: __import__('browser_walls').check_room_buttons(c.browser, c.page.url, open_viewer),
          'a room\'s Lower, Taller, Choose... and Plain (on the police station)', when=ON_POLICE, full=False),
    Check('free-handles', lambda c: __import__('browser_walls').check_free_handles(c.browser, c.page.url, open_viewer),
          "a made wall's thickness and bottom handles, its gaps a set at a time, Pivot to corner, Stretch and Join ends",
          when=ON_POLICE, full=False),
    Check('texture-mapping', lambda c: __import__('browser_walls').check_texture_mapping(c.browser, c.page.url, open_viewer),
          "a made wall's and floor's Texture mapping: surfaces picked, Size, its slide, turn and size handles, the fields, "
          'world alignment, Original and Reset surface', when=ON_POLICE, full=False),
    Check('made-prefab', editing('made_prefab'), 'made pieces kept through a prefab', needs=('projects',), full=False),
    Check('modals', editing('modals'), 'dialogs keep the focus and the keys', full=False),
    Check('reset-all', editing('reset_all'), 'Reset all mends a broken piece', full=False),
    Check('draw-errors', editing('draw_errors', 'save_dialog'), 'a piece the browser can\'t draw', needs=('projects',), full=False),
    Check('look-undo', editing('look_undo'), 'a look change is one undo step', full=False),
    Check('failed-reads', editing('failed_reads'), 'reads that fail once are said and asked again', full=False),
    Check('let-go', editing('let_go'), 'controls give the keys back', full=False),
    Check('paste-buildings', editing('paste_buildings'), 'pasted buildings\' names', full=False),
    Check('squad-read', editing('squad_read'), 'the squad read again', full=False),
    Check('ladder-floor', editing('ladder_floor'), 'a ladder\'s floor count', full=False),
    Check('small-defects', editing('small_defects'), 'small page defects', full=False),
    Check('grid-panel', editing('grid_panel'), 'the Map grid\'s panel beside each right-hand panel (1280, 1024 and 800 wide)', full=False),
    Check('step-pick', lambda c: __import__('browser_controls').check_step_pick(c.browser, c.page.url, open_viewer),
          'Ctrl and the wheel step through what is under the cursor, a piece of a group picked alone (in the prefab builder, '
          "with Bar's and Police Station's pieces; and on Bar)", full=False),
    Check('step-views', lambda c: __import__('browser_controls').check_step_views(c.browser, c.page.url, open_viewer),
          'Ctrl and the wheel in the Lights, Effects, Buildings, Spawns and Landing zones views (on Bar)', full=False),
    Check('carried-copy', lambda c: __import__('browser_controls').check_carried_copy(c.browser, c.page.url, open_viewer),
          'a copy carried to another map and to the prefab builder (Bar and Police Station), the project there compiled',
          needs=('projects',), full=False),
    Check('same-controls', lambda c: __import__('browser_controls').check_same_controls(c.browser, c.page.url, open_viewer),
          'the same controls on a landing zone, a spawn point, a floor box and a piece (Bar) and a diagonal cover mark (the farm)', full=False),
    Check('open-window', lambda c: __import__('browser_open_window').check_open_window(c.browser, c.page.url, open_viewer),
          "the button for the map or the prefab, its menu and the Open window's Maps and Prefabs sides", needs=('projects',), full=False),
    Check('rail-lists', lambda c: __import__('browser_controls').check_rail_lists(c.browser, c.page.url, open_viewer),
          'the Views list beside its button and over the dock; the Add panel made large, cards with large pictures', needs=('settings',), full=False),
    Check('diagonal', lambda c: __import__('browser_diagonal').check_diagonal(c.browser, c.page.url, open_viewer),
          'the Diagonal cover view on the farm: corners switched, a mark moved, deleted, reset and added', full=False),
    Check('select-kind', editing('select_kind'), 'Select all of a kind on pieces, and their flags set together', when=ON_MAP, full=False),
    Check('flags-gate', editing('flags_gate'), 'the Flags group asks before opening a prop\'s pathing gate', when=ON_MAP, full=False),
    Check('prepare-routes', lambda c: check_prepare_routes(c.browser, c.page.url), 'Build\'s routes into Prepare, the build\'s '
          'status answered by the check (no Build runs)', needs=('projects',), when=ON_MAP, full=False),
    Check('documents', lambda c: __import__('browser_documents').check_all(c.browser, c.page.url),
          'two windows, replacing, failed saves, builds and first opens', needs=('projects',), full=False),
)
CHECK = {c.name: c for c in CHECKS}


def scratch_settings(page):
    """Why the server's settings file is the user's own (None when it is a scratch one): /setup.json names it."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from settings import APP, documents
    named = page.evaluate("fetch('/setup.json?checks=0').then(r => r.json()).then(s => s.settingsFile)")
    own = documents() / APP / 'settings.json'
    if os.path.normcase(os.path.abspath(named)) == os.path.normcase(os.path.abspath(own)):
        return f'the server reads the user\'s own settings ({own.name} in Documents\\{APP})'
    return None


def refuse_main_server(url):
    if urlsplit(url).port == MAIN_PORT:
        raise SystemExit(f'refusing {url}: {MAIN_PORT} is the main server, the one the user keeps open; check a test server (8790-8799)')


def run_checks(ctx, names):
    """Each check of the table that `names` holds, in the table's order: those whose server or map can't have them
    are skipped with why; a result goes in the report."""
    for check in CHECKS:
        if check.name not in names or (check.name == 'temple-interior') != ctx.opening: continue
        if check.name == 'previews': closing(ctx)
        why = next((NEEDS[n][1] for n in check.needs if NEEDS[n][0] and not getattr(ctx.args, NEEDS[n][0])), None)
        if not why and 'settings' in check.needs and (own := scratch_settings(ctx.page)):
            if ctx.args.only: raise SystemExit(f'refusing {check.name}: {own}. {NEEDS["settings"][1]}')
            why = f'{NEEDS["settings"][1]} ({own})'
        why = why or (check.when(ctx) if check.when else None)
        if why:
            skip(check.name, why)
            continue
        CURRENT['check'] = check.name
        try:
            result = check.run(ctx)
        except BaseException as error:
            ctx.failed = dict(check=check.name, error=(str(error).strip().splitlines() or [type(error).__name__])[0][:500])
            raise
        if result is WHOLE: continue        # (it skipped itself whole, with why: listed as skipped only)
        ctx.ran.append(check.name)
        if result is not None: ctx.results[check.name] = result


def closing(ctx):
    """The screenshot and the report's numbers, once, before the previews leave the map (or at the end)."""
    if ctx.closed: return
    ctx.closed = True
    page = ctx.page
    page.wait_for_timeout(500)      # (a frame drawn for the picture)
    page.screenshot(path=str(ctx.args.screenshot))
    ctx.report.update(page.evaluate("""() => ({status:document.querySelector('#status').textContent,
      objects:viewer.roots.size, calls:viewer.renderer.info.render.calls,
      triangles:viewer.renderer.info.render.triangles})"""))


def smoke(args):
    """One run against the server args.url names: the checks --only names, or the whole run's."""
    names = {k.strip() for k in args.only.split(',') if k.strip()} if args.only else {c.name for c in CHECKS if c.full}
    args.screenshot.parent.mkdir(parents=True,exist_ok=True)
    errors = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge",headless=True)
        # every page a check opens (through this browser, in any check module) records its answers of 500 and above
        new_page = browser.new_page
        browser.new_page = lambda *a, **k: watch_answers(new_page(*a, **k))
        page = browser.new_page(viewport=dict(width=1600,height=1000),device_scale_factor=1)
        page.on("pageerror",lambda e: errors.add(str(e)))
        page.on("console",lambda msg: errors.add(msg.text) if msg.type == "error" else None)
        page.on('requestfailed',lambda req:errors.add(f'{req.url}: {req.failure}'))
        page.on('response',lambda response:errors.add(f'HTTP {response.status}: {response.url}') if response.status >= 400 else None)
        page.goto(args.url)
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden",timeout=120000)
        assert page.evaluate("document.getElementById('mapTitle').textContent") not in ('','…','None')
        if page.locator('#prepareModal').is_visible():      # an export older than building needs: the dialog, then its banner
            page.locator('#prepareLater').click()
            assert 'Prepare now' in page.locator('#projectBanner').inner_text()
        source = page.evaluate("viewer.data.source.file.toLowerCase()")
        ctx = SimpleNamespace(page=page, browser=browser, args=args, errors=errors, ran=[], results={}, closed=False, opening=True, failed=None,
                              is_bar=source.endswith('urb_bar.upk'), is_temple=source.endswith('templeship.upk'),
                              is_police=source.endswith('urb_policestation.upk'),
                              version=page.evaluate('viewer.data.exporterVersion ?? 0'), scope=page.evaluate('viewer.data.scope'),
                              tile_grid=page.evaluate('Boolean(viewer.data.tileGrid)'),
                              report=dict(initialView=value(page,'scenery'), interiorPieces=None),
                              shot=lambda label: args.screenshot.with_stem(args.screenshot.stem + '-' + label))
        try:
            run_checks(ctx, names)          # (temple-interior: the map as it opened)
            ctx.opening = False
            if page.locator('#scenery').is_visible(): choose(page,'scenery','full')
            # the map's pieces, and its missions' streamed packages' (export 13)
            assert page.evaluate('viewer.roots.size === viewer.data.objects.length + viewer.streamPieces')
            run_checks(ctx, names)
            closing(ctx)
        except BaseException:
            print_server_errors()
            raise
        finally:
            # the report, a check's failure too: what ran before it, what was skipped, and which failed and why
            errors -= EXPECTED
            result = dict(**({'only': sorted(names)} if args.only else {}), **ctx.report, ran=ctx.ran, skipped=SKIPPED,
                          **({'failed': ctx.failed} if ctx.failed else {}), results=ctx.results, errors=sorted(errors),
                          serverErrors=SERVER_ERRORS, screenshot=str(args.screenshot))
            args.screenshot.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf8',newline='\n')
            print(json.dumps(result,indent=2))
        browser.close()
    if errors:
        print_server_errors()
        raise SystemExit(1)
    # under --only, a check asked for that did nothing (skipped whole, or its server or map can't have it) fails the
    # run, and so a run in which everything skipped does; a part of a check that skipped is listed, and fails nothing
    if args.only:
        parts = [s for s in SKIPPED if s['check'] in ctx.ran]
        if parts: print('skipped in part: ' + '; '.join(f"{s['check']}: {s['reason']}" for s in parts), flush=True)
        left = [n for n in sorted(names) if n not in ctx.ran]
        if left: raise SystemExit('asked for and skipped: ' + '; '.join(
            f"{n}: {'; '.join(s['reason'] for s in SKIPPED if s['check'] == n) or 'not run'}" for n in left))


# --all: everything, on fresh test servers of its own -------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]
ALL_PORTS = (8795, 8796, 8797, 8798)        # (--ports gives others: two whole runs from two worktrees at once)


def ports(text):
    """--ports a,b,c,d: test servers' ports (8790-8799), never the main server's."""
    got = tuple(int(p) for p in text.split(',') if p.strip()) if re.fullmatch(r'[\d, ]+', text) else ()
    if MAIN_PORT in got: raise argparse.ArgumentTypeError(f'{MAIN_PORT} is the main server, the one the user keeps open')
    if not got or len(set(got)) != len(got) or not all(8790 <= p <= 8799 for p in got):
        raise argparse.ArgumentTypeError(f'{text!r}: distinct test server ports (8790-8799), comma-separated')
    return got


# Each run: the map it opens, this script's arguments (or another script of this folder), and whether it plays.
ALL_RUNS = (
    dict(name='whole', map='URB_Bar', smoke=['--projects', '--squad']),
    dict(name='named', map='URB_Bar', smoke=['--projects', '--only', 'speeds,library-all,library-effects,effect-values,library-flares,'
                                                                      'library-assembly,output-names']),
    dict(name='builder', map='URB_Bar', smoke=['--projects', '--only', 'builder,prefab-test']),
    dict(name='editing', map='URB_Bar', smoke=['--projects', '--only', 'made-prefab,modals,reset-all,draw-errors,look-undo,failed-reads,'
                                                                        'let-go,paste-buildings,squad-read,ladder-floor,small-defects,'
                                                                        'grid-panel,made-break,made-openings,rock-corner,select-kind,diagonal,'
                                                                        'flags-gate,prepare-routes']),
    dict(name='documents', map='URB_Bar', smoke=['--projects', '--only', 'documents']),
    dict(name='police', map='URB_PoliceStation', smoke=['--projects', '--only', 'walls,looks,room-buttons,light-bar,free-handles,texture-mapping']),
    dict(name='temple', map='TempleShip', smoke=['--only', 'temple-interior,temple-look']),
    dict(name='map-picture', map='URB_Bar', script='browser_map_picture.py'),
    dict(name='maps', map='URB_Bar', script='browser_maps_smoke.py'),
    dict(name='play', map='URB_Bar', smoke=['--play', '--only', 'play'], play=True),
)


def all_covered():
    """Every check of the table is in one of --all's runs."""
    named = {n for run in ALL_RUNS if '--only' in run.get('smoke', ()) for n in run['smoke'][run['smoke'].index('--only') + 1].split(',')}
    whole = {c.name for c in CHECKS if c.full} if any('--only' not in run.get('smoke', ['--only']) for run in ALL_RUNS) else set()
    return sorted(set(CHECK) - named - whole)


def port_taken(port):
    import socket
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1): return True
    except OSError:
        return False


def own_game():
    """The game install the user's settings name (read only), or None."""
    sys.path.insert(0, str(REPO / 'tools' / 'viewer'))
    from settings import load_settings
    return load_settings().get('game')


def scratch_cache(root, cache):
    """The cache --all serves: `cache` when given, else <root>/cache with the maps its runs open exported into it
    (viewer.py export, about half a minute a map) and the whole game's library scanned (library scan: the library
    checks count every map's pieces and effects). Never the user's cache: a test server writes into the cache it
    serves (a map exported on first open or again when outdated, the library's pieces and pictures)."""
    if cache: return Path(cache)
    cache = root / 'cache'
    sys.path.insert(0, str(REPO / 'tools' / 'viewer'))
    from installs import cooked
    from settings import resolve_game
    game = own_game()
    if not game: raise SystemExit('the settings name no game install to export the maps from: give --cache <a prepared scratch cache>')
    folder = cooked(resolve_game(game)[0])
    viewer = [sys.executable, '-B', str(REPO / 'tools' / 'viewer' / 'viewer.py')]
    maps = sorted({run['map'] for run in ALL_RUNS} | set(__import__('api_names').MAPS))
    for name in maps:
        print(f'exporting {name} into {cache}', flush=True)
        subprocess.run([*viewer, 'export', str(folder / f'{name}.upk'), '--cache', str(cache)], cwd=REPO, check=True, capture_output=True)
    print(f'scanning the library into {cache}', flush=True)
    subprocess.run([*viewer, 'library', 'scan', '--cache', str(cache)], cwd=REPO, check=True, capture_output=True)
    return cache


# What a scratch game folder for the Play check holds (the module docstring and --play-install's help list them), at
# their places under the install, and the most --all copies of the settings' install to make one itself.
PLAY_FILES = (('XEW/XComGame/Config', 'Default*.ini'), ('XEW/XComGame/CookedPCConsole', 'XComGame.upk'),
              ('XEW/XComGame/CookedPCConsole', '{map}.upk'), ('XEW/XComGame/Localization/INT', 'XCom*.int'))
PLAY_COPY_LIMIT = 300 * 2 ** 20


def scratch_play_install(root, map_name):
    """--all's Play run without --play-install: (a scratch game folder in `root`, None) made of copies of the files
    PLAY_FILES names from the game install the settings name, which is only read; or (None, why not), when they can't
    be found or come to PLAY_COPY_LIMIT or more."""
    game = own_game()
    if not game: return None, 'the settings name no game install to copy the Play check\'s files from'
    from settings import resolve_game
    source, note = resolve_game(game)
    if source is None: return None, f'no game install to copy the Play check\'s files from: {note}'
    files, missing = [], []
    for folder, pattern in PLAY_FILES:
        found = sorted(f for f in (source / folder).glob(pattern.format(map=map_name)) if f.is_file())
        files += found
        if not found: missing.append(f'{folder}/{pattern.format(map=map_name)}')
    if missing: return None, f'{source} has no {", ".join(missing)}'
    size = sum(f.stat().st_size for f in files)
    if size >= PLAY_COPY_LIMIT:
        return None, f'the Play check\'s files of {source} come to {size // 2 ** 20} MB, too many to copy: give --play-install'
    target = root / 'play-install'
    for f in files:
        to = target / f.relative_to(source)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, to)
    (target / 'XEW' / 'Binaries').mkdir(parents=True, exist_ok=True)
    print(f'made the Play check\'s scratch install in {target}: {len(files)} files ({size // 2 ** 20} MB) copied from {source}', flush=True)
    return target, None


def start_server(port, folder, cache, extra=()):
    """A test server on `port` with scratch projects, builds, squad and settings in `folder` (the settings name the
    scratch cache and the user's game install, read only) and --dry-play, so that nothing starts the game."""
    if port_taken(port): raise SystemExit(f'port {port} is taken: --all starts servers of its own there; free it first, or give --ports')
    game = own_game()
    (folder / 'settings.json').write_text(json.dumps(dict(cache=str(cache), **({'game': str(game)} if game else {})), indent=1),
                                          encoding='utf-8', newline='\n')
    log = open(folder / 'server.log', 'wb')
    proc = subprocess.Popen([sys.executable, '-B', str(REPO / 'tools' / 'viewer' / 'viewer.py'), 'serve', '--port', str(port), '--no-open',
                             '--projects', str(folder / 'projects'), '--builds', str(folder / 'builds'), '--squad', str(folder / 'squad.json'),
                             '--dry-play', *extra],
                            cwd=REPO, env=dict(os.environ, XCOM_MAP_WORKSHOP_SETTINGS=str(folder / 'settings.json')), stdout=log,
                            stderr=subprocess.STDOUT)
    end = time.time() + 120
    while time.time() < end and proc.poll() is None:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/maps.json', timeout=3): return proc, log
        except OSError:
            time.sleep(0.5)
    stop_server(proc, log, port)
    raise SystemExit(f'the test server on {port} did not answer: {folder / "server.log"}')


def stop_server(proc, log, port):
    proc.terminate()
    try: proc.wait(15)
    except subprocess.TimeoutExpired: proc.kill()
    if sys.platform == 'win32':     # (the Store's Python runs the server as a child of what was started: stop the port's owner)
        subprocess.run(['powershell', '-NoProfile', '-Command', f'Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction '
                        'SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }'], capture_output=True)
    for _ in range(60):
        if not port_taken(port): break
        time.sleep(0.5)
    log.close()


def run_all(args):
    """Each of ALL_RUNS on a fresh test server, one after another, each stopped after; the report lists each run's
    checks ran and skipped, with why, and its errors (all.json in the scratch folder)."""
    left = all_covered()
    assert not left, f'--all runs no check called {", ".join(left)}: add it to ALL_RUNS'
    # (whole: the servers run from the repository, and take their folders and the Play install from here)
    root = (Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix='workshop-smoke-'))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    print(f'scratch folder: {root}', flush=True)
    cache = scratch_cache(root, args.cache)
    report, failed = [], False
    play_install = args.play_install
    for k, run in enumerate(ALL_RUNS):
        port, folder = args.ports[k % len(args.ports)], root / run['name']
        if run.get('play') and not play_install:
            play_install, why = scratch_play_install(root, run['map'])
            if not play_install:
                report.append(dict(name=run['name'], skipped=f'{why} (Play installs into a scratch game folder: --play-install)'))
                print(f"SKIP {run['name']}: {report[-1]['skipped']}", flush=True)
                continue
        folder.mkdir(parents=True, exist_ok=False)
        url = f"http://127.0.0.1:{port}/?map={run['map']}"
        if 'script' in run:
            command = [sys.executable, '-B', str(Path(__file__).with_name(run['script'])), '--url', f'http://127.0.0.1:{port}']     # (the server alone: each script opens its map)
            command += ['--screenshot', str(folder / 'maps.png')] if run['script'] == 'browser_maps_smoke.py' else ['--map', run['map']]
        else:
            command = [sys.executable, '-B', __file__, '--url', url, '--screenshot', str(folder / 'smoke.png'), *run['smoke']]
        proc, log = start_server(port, folder, cache, ['--install', str(play_install)] if run.get('play') else [])
        started = time.time()
        try:
            done = subprocess.run(command, cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3600)
            code, out = done.returncode, done.stdout + done.stderr
        except subprocess.TimeoutExpired as e:
            code, out = 'timeout', str(e)
        finally:
            stop_server(proc, log, port)
        (folder / 'run.log').write_text(out, encoding='utf-8', newline='\n')
        entry = dict(name=run['name'], port=port, map=run['map'], exit=code, seconds=round(time.time() - started))
        shown = folder / 'smoke.json'
        if shown.is_file():
            got = json.loads(shown.read_text(encoding='utf-8'))
            entry.update(ran=got['ran'], skipped=got['skipped'], errors=got['errors'], **({'failed': got['failed']} if 'failed' in got else {}),
                         **({'serverErrors': got['serverErrors']} if got.get('serverErrors') else {}))
        if code != 0:
            failed = True
            entry['last'] = (out.strip().splitlines() or [''])[-1]
        report.append(entry)
        print(f"{'PASS' if code == 0 else 'FAIL'} {run['name']} ({port}, {entry['seconds']} s): {len(entry.get('ran', []))} ran, "
              f"{len(entry.get('skipped', []))} skipped" + (f"; {entry['failed']['check']} failed" if entry.get('failed') else '')
              + (f": {entry['last']}" if code != 0 else ''), flush=True)
        for s in entry.get('skipped', []): print(f"    skipped {s['check']}: {s['reason']}", flush=True)
        if code != 0:
            for e in entry.get('serverErrors', []): print(f"    answered {e['status']}: {e['method']} {e['url']} ({e['check']})", flush=True)
    (root / 'all.json').write_text(json.dumps(report, indent=2), encoding='utf-8', newline='\n')
    print(f'report: {root / "all.json"}')
    if failed: raise SystemExit(1)


def main():
    words = '\n'.join(f'  {c.name:<17}{c.words}' + (f' [{", ".join(c.needs)}]' if c.needs else '') + ('' if c.full else ' (only when named)')
                      for c in CHECKS)
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], epilog='checks:\n' + words, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url",help="the test server and map, as http://127.0.0.1:<port>/?map=URB_Bar (never 8768, the main server)")
    ap.add_argument("--screenshot",type=Path,help="the picture; the report is written beside it as .json")
    ap.add_argument("--projects",action="store_true",help="Also check projects: saves into the server's projects folder, so "
                    "use a test server started with --projects <scratch folder>, never the main one")
    ap.add_argument("--play",action="store_true",help="Also check Play in game and Game maps' Undo everything: changes the server's "
                    "install, so only for a test server started with --install <a scratch game folder> --dry-play (--play-install "
                    "says what that folder holds)")
    ap.add_argument("--play-project",help="With --play: also play this project's build (it must be of its saved revision)")
    ap.add_argument("--squad",action="store_true",help="The server's --squad is a scratch file: the squad check also saves (and puts the squad back)")
    ap.add_argument("--only",help="Run only these checks (the names below, comma-separated), in the table's order, and stop: "
                    "for working on them")
    ap.add_argument("--all",action="store_true",help="Run every check on fresh test servers of its own (ports 8795-8798), one after another")
    ap.add_argument("--ports",type=ports,default=ALL_PORTS,help="With --all: the test servers' ports instead, as a,b,c,d (8790-8799)")
    ap.add_argument("--write-api-names",action="store_true",help="Write window.viewer's names on the Bar, the blank map and in the "
                    "builder, read from the test server --url names, into viewer_api_names.json (what api-names compares), and stop")
    ap.add_argument("--scratch",help="With --all: the folder for the servers' scratch folders and the report (default: a new temporary one)")
    ap.add_argument("--play-install",help="With --all: a scratch game folder for the Play check, never a real install. It holds copies "
                    "of an LWR install's XEW\\XComGame\\Config\\Default*.ini, XEW\\XComGame\\CookedPCConsole\\XComGame.upk and "
                    "URB_Bar.upk, XEW\\XComGame\\Localization\\INT\\XCom*.int, and an empty XEW\\Binaries folder (where a play "
                    "writes its commands file). Without it, --all makes one in its scratch folder from the game install the "
                    "settings name (only read), when those files come to less than 300 MB; else Play is skipped")
    ap.add_argument("--cache",help="With --all: a scratch cache holding exports of URB_Bar, URB_PoliceStation, TempleShip and CB2_MP_Blank, and the "
                    "game's library scanned (default: made in the scratch folder); never the user's own")
    args = ap.parse_args()
    if args.write_api_names:
        if not args.url or args.all or args.only: ap.error('--write-api-names reads the server --url names, and runs no check')
        refuse_main_server(args.url)
        return __import__('api_names').write(args.url)
    if args.all:
        if args.url or args.only: ap.error('--all starts its own servers and runs every check: no --url or --only with it')
        return run_all(args)
    if args.ports != ALL_PORTS: ap.error('--ports is for --all (with --url, the server is the one it names)')
    if not args.url or not args.screenshot: ap.error('--url and --screenshot are needed (or --all)')
    refuse_main_server(args.url)
    if args.only:
        names = [k.strip() for k in args.only.split(',') if k.strip()]
        unknown = [n for n in names if n not in CHECK]
        if unknown or not names: ap.error('no check called %s (they are %s)' % (', '.join(unknown) or "''", ', '.join(CHECK)))
        for name in names:
            missing = [NEEDS[n][1] for n in CHECK[name].needs if NEEDS[n][0] and not getattr(args, NEEDS[n][0])]
            if missing: ap.error(f'{name} {missing[0]}')
    smoke(args)


if __name__ == "__main__": main()
