"""Optional Playwright check of our local viewer (no game interaction)."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
from playwright.sync_api import sync_playwright


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
    state = "(() => ({c: viewer.camera.position.toArray(), t: viewer.controls.target.toArray()}))()"

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
    assert page.evaluate("localStorage.getItem('viewer.flyKeys')") == '1'
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
    # Typing in a field keeps the keys.
    page.locator('#search').focus()
    before = page.evaluate(state)
    for key in ('ArrowUp', 'w', 'q', 'e'):
        page.keyboard.down(key); page.wait_for_timeout(200); page.keyboard.up(key)
    after = page.evaluate(state)
    assert camera_delta(before, after) < 1e-3, (before, after)
    page.locator('#search').fill('')
    page.evaluate('document.activeElement.blur()')


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
    assert page.evaluate("localStorage.getItem('viewer.moveSpeed')") == '0.5'
    assert page.locator('#moveSpeedValue').text_content() == '×0.50'
    page.locator('#moveSpeed').dispatch_event('dblclick')
    assert page.evaluate("document.getElementById('moveSpeed').value") == '1'
    assert page.evaluate("localStorage.getItem('viewer.moveSpeed')") == '1'
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
    assert page.evaluate("localStorage.getItem('viewer.pivot')") == 'centre'
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
    assert page.evaluate('viewer.gizmo.pivot') == 'origin' and page.evaluate("localStorage.getItem('viewer.pivot')") == 'origin'
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
    state = "(() => ({c: viewer.camera.position.toArray(), t: viewer.controls.target.toArray()}))()"
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
    state = "(() => ({c: viewer.camera.position.toArray(), t: viewer.controls.target.toArray()}))()"
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
        return
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
    if not page.locator('#scenery').is_visible(): return
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
    """Trial copies and deletions on the selected piece: copy, paste through the placing preview, undo/redo, delete
    and Reset all."""
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
    # fracturing piece of its own has a pose rule, as the assemblies do, kept under tile snap only (since 10 November:
    # snap off, it moves freely); a physics prop has none.
    single = ("cls => [...viewer.roots.keys()].find(id => { const r = viewer.roots.get(id), o = r.userData.source;"
              " return r.visible && !o.added && o.layer === 'base' && o.actorClass === cls"
              " && !(viewer.families()?.assemblies ?? []).some(a => a.members.includes(o.actor)); })")
    wall, physics_prop = (page.evaluate(single, c) for c in ('XComDecoFracLevelActor', 'KAsset'))
    if wall:
        page.evaluate('id => viewer.select(id)', wall)
        details = page.locator('#details').inner_text()
        assert 'Builds from' not in details and 'Recipe snap' not in details, details
        assert page.evaluate('viewer.gizmo.gridPiece && !viewer.gizmo.recipe')
        page.evaluate("viewer.setSnapMode('tile')")
        assert 'Recipe snap' in page.locator('#details').inner_text()
        assert page.locator('#snapBadge').inner_text() == 'R' and page.evaluate('viewer.gizmo.recipe')
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
    """The recipe snap (private/plans/done/cars-doors-ladders-plan.md, sections 3.2 and 8), on Bar: the page's pose rule passes
    the compiler's cases; the map's assemblies are served; a door selects with its frame, linked pieces on or off, and
    its copy keeps them together; a ladder, a car and a van move by whole tiles and storeys and turn by quarter turns
    from where their originals stand under tile snap, typed into the fields or pasted (turned while placing too); the
    rotate handles turn about the vertical only; the snap button says so while such a piece is selected. With snap
    off (since 10 November 2026) such a piece moves freely, and its chip says when it stands off the grid."""
    original = page.evaluate('viewer.gizmo.active')
    cases = json.loads((Path(__file__).resolve().parents[2] / 'editor' / 'tests' / 'pose_rule_cases.json').read_text(encoding='utf-8'))['cases']
    got = page.evaluate("""async cases => { const rule = await import('/poserule.js');
      return cases.map(c => ({ move: rule.gridMove(c.source.location, c.source.rotation, c.pose.location, c.pose.rotation, c.origin),
        nearest: rule.nearestGridPose(c.source.location, c.source.rotation, c.pose.location, c.pose.rotation, c.origin) })); }""", cases)
    for c, g in zip(cases, got):
        m, n = g['move'], g['nearest']
        assert (m['valid'], m['why'], m['turns']) == (c['valid'], c['why'], c['turns']), (c['case'], m)
        assert all(abs(a - b) < 1e-3 for a, b in zip(m['translation'], c['translation'])), (c['case'], m)
        assert n['rotation'] == c['nearest']['rotation'], (c['case'], n)
        assert all(abs(a - b) < 1e-3 for a, b in zip(n['location'], c['nearest']['location'])), (c['case'], n)
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
    assert page.locator('#snapBadge').inner_text() == '' and page.evaluate('viewer.gizmo.gridPiece && !viewer.gizmo.recipe')
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
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    assert 'Off the grid' not in page.locator('#details').inner_text()
    # Tile snap: the snap button and a chip say Recipe, and it builds (no milestone); a typed move and turn snap, a
    # typed tilt doesn't hold.
    page.evaluate("viewer.setSnapMode('tile')")
    assert page.locator('#snapBadge').inner_text() == 'R' and page.evaluate('viewer.gizmo.recipe')
    details = page.locator('#details').inner_text()
    assert 'Recipe snap' in details and 'Builds from' not in details, details
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
    page.locator('#editRotate').click()
    assert page.evaluate('[viewer.gizmo.controls.showX, viewer.gizmo.controls.showY, viewer.gizmo.controls.showZ]') == [False, True, False]
    page.locator('#editMove').click()
    assert page.evaluate('viewer.gizmo.controls.showX && viewer.gizmo.controls.showZ')
    # Copies of a door, a car and a van, pasted and turned while placing, keep the rule; the door's copies stay linked.
    for family, turns, dx in (('door', 0, 0), ('car', 1, 60), ('van', 1, -60)):
        assembly = first(family)
        page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', root_of(assembly['pivot']))
        before = set(page.evaluate('viewer.editState().added.map(a => a.id)'))
        paste(turns, dx)
        copies = page.evaluate('viewer.gizmo.selection().map(r => r.userData.source)')
        assert all(c['added'] for c in copies) and len({c['actor'] for c in copies}) == len(assembly['members']), (family, copies)
        assert page.evaluate('viewer.editState().added.length') == len(before) + len(assembly['members'])
    edits = page.evaluate(GRID_EDITS)
    assert all(e['valid'] for e in edits), [e for e in edits if not e['valid']]
    assert sorted(Counter(e['turns'] for e in edits).items()) == [(0, len(first('door')['members'])),
        (1, 1 + len(first('car')['members']) + len(first('van')['members']))], edits
    door_tags = {e['prefab'] for e in edits if e['actor'] in first('door')['members']}
    assert len(door_tags) == 1 and next(iter(door_tags)).endswith(':' + door['pivot'].split('.')[-1]), door_tags
    # A piece of no grid family takes the plain tile snap.
    page.evaluate('id => viewer.select(id)', original)
    assert page.locator('#snapBadge').inner_text() == '96' and not page.evaluate('viewer.gizmo.recipe')
    page.evaluate("viewer.setSnapMode('off')")
    assert page.locator('#snapBadge').inner_text() == '' and not page.evaluate('viewer.gizmo.recipe')
    page.locator('#editResetAll').click()
    assert page.evaluate('viewer.changes().total') == 0
    page.evaluate('id => viewer.select(id)', original)


ZOOM_STATE = """p => { const c = viewer.camera, t = viewer.controls.target, v = new THREE_V(...p);
  const s = v.clone().project(c), r = viewer.renderer.domElement.getBoundingClientRect();
  return { distance: c.position.distanceTo(v), target: c.position.distanceTo(t), near: c.near,
           screen: [r.left + (s.x + 1) / 2 * r.width, r.top + (1 - s.y) / 2 * r.height] }; }"""


def check_zoom(page):
    """The wheel zooms towards what is under the cursor (app.js wheelZoom), all the way in: framed on the whole map, a
    piece off to the side, far from the orbit target, is zoomed to from 40 notches until the camera is a few units
    from it, the point staying under the cursor; OrbitControls' own zoom stalled at the target's distance. Zoomed back
    out as far, the camera returns to about where it was."""
    page.evaluate('viewer.select(null); viewer.frame()')
    page.wait_for_timeout(300)    # the controls' damping settles
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
    page.wait_for_timeout(100)
    close = page.evaluate(state, spot['point'])
    assert close['distance'] < max(30.0, start['distance'] * 0.01), (start, close)
    assert close['distance'] < spot['away'] * 0.5, (spot, close)    # well past where the old zoom stalled
    assert abs(close['screen'][0] - spot['x']) < 3 and abs(close['screen'][1] - spot['y']) < 3, (spot, close)
    assert close['near'] <= start['near'] and abs(close['target'] - close['distance']) < close['distance'], close
    for _ in range(40):
        page.mouse.wheel(0, 100)
    page.wait_for_timeout(100)
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
    page.locator('#search').fill(page.evaluate('id => viewer.roots.get(id).userData.source.actor.split(".").at(-1)', a))
    assert page.locator('#objects .tag.group').count() >= 1 and page.locator('#objects .tag.group').first.inner_text() == 'group'
    page.locator('#search').fill('')
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
        assert page.locator('#groupBreak').is_disabled() and page.locator('#groupNote').is_visible()
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
    page.wait_for_timeout(300)
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
    page.keyboard.down('Shift'); page.mouse.down(); page.mouse.move(hx + ux * 60, hy + uy * 60, steps=5)
    assert 'copy' in page.locator('#dragHint').inner_text()
    assert page.evaluate('viewer.roots.size') == count
    page.keyboard.press('Escape'); page.mouse.up(); page.keyboard.up('Shift')
    page.wait_for_timeout(200)
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
    page.wait_for_timeout(300)
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
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 21"): return
    mine = "() => viewer.buildings().filter(b => b.replaces).map(b => b.id)"
    ids = page.evaluate(mine)
    if not ids: return
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
    # deleted (its boxes all gone: a deleted record), listed in the view with Restore, restored, both undone
    page.evaluate('ids => { viewer.gizmo.setSelection(ids, ids[0]); viewer.deleteVolumes(); }', [i for i, _ in page.evaluate(box_of, target)])
    assert page.evaluate('viewer.savedBuildings()') == [{'id': target, 'replaces': rec['replaces'], 'deleted': True}]
    assert page.locator('#volumeChanged').is_visible() and 'deleted' in page.locator('#volumeChanged').inner_text()
    page.locator('#volumeChanged button').first.click()
    assert page.evaluate(saved) == '[]' and page.locator('#volumeChanged').is_hidden()
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


def check_clear_map(page):
    """Clear map, the ground grid and the landing zones (private/plans/done/clear-map-plan.md, C2 to C4), on an export
    22 map: the dialog's counts; a clear at a smaller size as one undo step (the pieces deleted but the landing's, the
    grid, the ground grid over every tile); a landing zone turned, copied, deleted and undone; the clear undone and
    redone. Nothing is saved."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 22"): return
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
        page.mouse.move(*p0); page.wait_for_timeout(30)
        page.mouse.down(); page.mouse.move(p0[0] + d[0] * pixels, p0[1] + d[1] * pixels, steps=12); page.mouse.up()
        page.wait_for_timeout(50)
        return page.evaluate('viewer.gridTool().dims')
    page.evaluate("""() => { const b = viewer.data.playableBounds, c = [0, 1, 2].map(k => (b.min[k] + b.max[k]) / 2),
                             s = Math.max(b.max[0] - b.min[0], b.max[2] - b.min[2]);
                             viewer.camera.position.set(c[0] + s * 0.55, s * 0.95, c[2] - s * 0.75); viewer.controls.target.set(c[0], 0, c[2]); viewer.controls.update(); }""")
    page.wait_for_timeout(200)
    page.locator('#editGrid').click()
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
    # higher as it is (the user, 13 November): levels by the top handle, the panel saying the Build adds cursor storeys
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
    # the dialog: what goes and stays (no size: a clear keeps the grid)
    page.evaluate("document.getElementById('projectClear').click()")
    text = page.locator('#clearMap').inner_text()
    assert 'Removes %d piece' % plan['pieces'] in text and 'one landing zone' in text, text
    assert page.locator('#clearMap input[type=number]').count() == 0
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
    page.evaluate('size => viewer.clearMap(size)', small)
    assert page.evaluate('viewer.cleared()') and page.evaluate('viewer.stage()') == dict(grid=small)
    assert page.evaluate('viewer.data.tileGrid.dimensions') == small
    assert page.evaluate('viewer.groundGrid().bare') == small[0] * small[1]
    state = page.evaluate('viewer.editState()')
    assert state['cleared'] is True and sum(1 for o in state['overrides'] if o.get('deleted')) >= plan['pieces'], len(state['overrides'])
    assert page.evaluate('viewer.lastClearMs()') < 1000
    # one landing zone left: the map's own first landing, used by both games
    left = page.evaluate('viewer.zones()')
    first_own = next((z for z in before_zones if z.get('ew')), before_zones[0])
    assert len(left) == 1 and left[0]['id'] == first_own['id'] and left[0].get('lwr') is not False, left
    assert left[0].get('ew') is (True if page.evaluate('viewer.ownLandingCount()') else None), left
    # zones are picked in the Landing zones view only (Shift+Z): drawn over everything, a click on one (its number
    # badge here) picks it and never a piece; the normal view's clicks go to pieces; the Lights view takes over
    badge_at = """() => { let b = null; viewer.landingLayer.traverse(o => { if (o.userData.zoneBadge) b = o; });
                          return b && viewer.screenOf([b.position.x, b.position.z, b.position.y]); }"""
    page.evaluate('viewer.pickZone(null)')
    page.evaluate('viewer.setZonesShown(false)')
    page.wait_for_timeout(400)
    page.mouse.click(*page.evaluate(badge_at))
    assert page.evaluate('viewer.pickedZone()') is None and not page.evaluate('viewer.zonesOn()')
    page.evaluate('viewer.select(null)')
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Shift+Z')
    assert page.evaluate('viewer.zonesOn()') and page.locator('#editZones').get_attribute('aria-pressed') == 'true'
    page.wait_for_timeout(400)          # the camera eases to rest: the badge's place on screen is its last
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
    page.locator('#editGrid').click()
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
    page.evaluate('viewer.frame()'); page.wait_for_timeout(200)
    page.evaluate("p => viewer.camera.position.set(p[0] + 600, 1400, p[1] - 900)", g['at'])
    page.evaluate("p => { viewer.controls.target.set(p[0], 0, p[1]); viewer.controls.update(); }", g['at'])
    page.wait_for_timeout(200)

    def grab(axis, points):
        for pt in points:
            page.mouse.move(*pt); page.wait_for_timeout(25)
            if page.evaluate('viewer.zoneGizmo().axis') == axis: return pt
        raise AssertionError("the zone gizmo's %s handle not found" % axis)
    at = g['at']
    p0 = page.evaluate('p => viewer.screenOf(p)', at)
    px = page.evaluate('p => viewer.screenOf([p[0] + 100, p[1], p[2]])', at)
    n = ((px[0] - p0[0]) ** 2 + (px[1] - p0[1]) ** 2) ** 0.5
    d = [(px[0] - p0[0]) / n, (px[1] - p0[1]) / n]
    pt = grab('X', [[p0[0] + d[0] * r, p0[1] + d[1] * r] for r in range(20, 200, 5)])
    page.mouse.down(); page.mouse.move(pt[0] + d[0] * 160, pt[1] + d[1] * 160, steps=10); page.mouse.up()
    moved = page.evaluate('viewer.zones()[0]')
    dx = moved['location'][0] - z0['location'][0]
    assert dx > 0 and dx % 96 == 0 and moved['location'][1:] == z0['location'][1:], (moved, z0)
    assert page.evaluate('viewer.pickedZone()') == z0['id']           # the drag did not let the zone go
    # R: the ring, quarter turns about the vertical only
    page.keyboard.press('r'); page.wait_for_timeout(100)
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
    page.locator('#landingCopy').click()
    assert len(page.evaluate('viewer.zones()')) == len(zones) + 1
    assert not page.evaluate('viewer.zones().at(-1).ew')                # a copy is Long War's
    page.locator('#landingDelete').click()
    assert len(page.evaluate('viewer.zones()')) == len(zones)
    assert not page.evaluate('viewer.zoneGizmo()')['shown']           # no zone picked, no gizmo
    for _ in range(6): page.keyboard.press('Control+z')
    assert page.evaluate('viewer.editState().landingZones') is None or page.evaluate('viewer.zones()[0].direction') == zones[0]['direction']
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
    keep = page.evaluate('dims => viewer.clearPlan(dims)', dims)
    page.evaluate("document.getElementById('projectClear').click()")
    tick = page.locator('#clearMapKeepOutside')
    if tick.is_checked(): tick.uncheck()
    assert 'outside the play area' not in page.locator('#clearMapPlan').inner_text()
    tick.check()
    text = page.locator('#clearMapPlan').inner_text()
    assert ('Removes %d piece' % keep['pieces']) in text and 'outside the play area' in text, text
    tick.uncheck()                                      # (remembered: left as it was at first)
    page.keyboard.press('Escape')
    if keep['outside']:
        assert keep['pieces'] == plan['pieces'] - keep['outside'], (keep, plan)
        page.evaluate('dims => viewer.clearMap(dims, true)', dims)
        state = page.evaluate('viewer.editState()')
        assert state['cleared'] is True and state['clearKeepsOutside'] is True
        page.keyboard.press('Control+z')
        assert not page.evaluate('viewer.clearKeepsOutside()') and not page.evaluate('viewer.editState()')['clearKeepsOutside']


def check_floor_boxes(page):
    """View options' Floor boxes: off at first; on, the project's floor boxes are drawn in the normal view, where a
    click on a box's edge or the select box takes the whole building. It moves by whole tiles and turns by quarter
    turns with what is picked, is copied with a piece as a new building, and deleted; each one undo step."""
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"): return
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
    page.locator('#editNormal').hover()
    assert page.locator('#normalFlyout').is_visible()
    page.locator('#boxesToggle').check()
    page.mouse.move(700, 500)
    assert page.locator('#normalFlyout').is_hidden()
    assert page.evaluate('viewer.boxesShown()') and page.evaluate(shown, ids) == [True, True]
    page.evaluate('id => viewer.frame(viewer.volumeRoots.get(id))', ids[0])
    page.wait_for_timeout(300)
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
        page.wait_for_timeout(300)
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
        page.locator('#editNormal').hover()
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
    page.locator('#editNormal').hover()
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
    assert 0 < entries - lights - zones <= visible, (entries, lights, zones, visible)
    assert page.locator('.libitem').count() == entries and f'{entries - lights - zones} pieces' in page.locator('#libFoot').inner_text(), (
        page.locator('.libitem').count(), entries, lights, zones, page.locator('#libFoot').inner_text())
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
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): page.close(); return
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
    assert page.evaluate('viewer.library.shown().map(e => e.key)') == [f['key'] for f in kept['favourites'] if True][:len(kept['favourites'])] \
        or key in page.evaluate('viewer.library.shown().map(e => e.key)')
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
    type_project_name(page, 'Library smoke')
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
    assert page.locator('#buildTitle').inner_text().startswith('Built Library smoke'), page.locator('#buildModal').inner_text()
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
        page.close(); return
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
    page.locator('#libAllList .libitem').first.hover()
    page.wait_for_timeout(600)
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
    type_project_name(page, 'Library effects smoke')
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
    assert page.locator('#buildTitle').inner_text().startswith('Built Library effects smoke'), page.locator('#buildModal').inner_text()
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
        page.close(); return
    if not page.evaluate("viewer.families()?.families?.['effect-values']?.builds"):
        page.close(); return
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
    assert 'Starts off (as set here)' in page.locator('#effectInfo').inner_text()
    # the size handle: dragged out, the box and the panel follow; one undo step puts it back
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('f')
    page.wait_for_timeout(300)
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
    # a simple sound: its outer radius dragged, its volume and pitch set
    sound = root('AmbientSoundSimple_0')
    page.evaluate(f'viewer.pickEffect({sound!r})')
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press('f')
    page.wait_for_timeout(300)
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
    type_project_name(page, 'Effect values smoke')
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
    assert page.locator('#buildTitle').inner_text().startswith('Built Effect values smoke'), page.locator('#buildModal').inner_text()
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
        return
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
    assert sorted(page.evaluate('viewer.coverHandles()')) == ['+x', '+y', '+z', '-x', '-y', '-z']
    set_snap(page, 'tile')
    start = page.evaluate('viewer.gizmo.pose()')['location']
    drag_handle(page, '+x', 1.3)                      # a tile and a bit: one tile more
    assert cover()['size'] == [192, 96], cover()
    drag_handle(page, '-y', 1.2)                      # out on the low side: the corner moves, the far side stays
    assert cover()['size'] == [192, 192], cover()
    moved = page.evaluate('viewer.gizmo.pose()')['location']
    assert abs(moved[1] - (start[1] - 96)) < 0.01 and abs(moved[0] - start[0]) < 0.01, (start, moved)
    drag_handle(page, '+z', 1.1)                      # up a tile: today's tile heights
    assert cover()['heights'] == [high[0], high[1] + recipe['heightStep']], cover()
    drag_handle(page, '-z', -1.0)                     # the bottom up a tile: off the floor
    assert cover()['heights'] == [high[0] + recipe['heightStep'], high[1] + recipe['heightStep']], cover()
    assert [round(v) for v in drawn()] == [192, 192, round(high[0] + 96), round(high[1] + 96)], drawn()
    for _ in range(4):
        page.keyboard.press('Control+z')
    assert cover() == dict(type='high', size=[96, 96], heights=high), cover()
    assert page.evaluate('viewer.gizmo.pose()')['location'] == start
    # snap off: smooth, to a unit; 24: steps of 24
    set_snap(page, 'off')
    drag_handle(page, '+x', -0.5)                     # half a tile in
    x = cover()['size'][0]
    assert 40 <= x <= 56 and x == round(x), cover()
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


FLOOR_CASES = Path(__file__).resolve().parents[2] / 'bake' / 'tests' / 'floor_membership_cases.json'


def check_floor_rules(page):
    """floors.js's plain rules on synthetic cases: floors and decorations (a rug on a floor, an 18-unit sidewalk on
    the asphalt, a plate on the sidewalk, a plane on nothing, a wall), floor stamps (one component only), saved floors,
    the level height, the floor under a point, and the building-floor cases the Build passes too
    (tools/bake/tests/floor_membership_cases.json)."""
    cases = json.loads(FLOOR_CASES.read_text(encoding='utf-8'))
    failures = page.evaluate("""async (cases) => {
      const fl = await import('/floors.js'), out = [];
      const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
      const check = (name, ok, detail) => { if (!ok) out.push([name, detail ?? null]); };
      // boxes [x0, y0, z0, x1, y1, z1]
      const kinds = fl.classifyFloors([
        { actor: 'asphalt', box: [0, 0, 0, 960, 960, 0] }, { actor: 'sidewalk', box: [100, 100, -2, 868, 504, 16] },
        { actor: 'barfloor', box: [2000, 0, 0, 3152, 1152, 4] }, { actor: 'rug', box: [2100, 100, 4, 2338, 259, 9] },
        { actor: 'plate', box: [300, 300, 16, 492, 684, 16] }, { actor: 'lone', box: [5000, 0, 100, 5192, 192, 100] },
        { actor: 'wall', box: [0, 0, 0, 96, 960, 300] }, { actor: 'slab', box: [2100, 600, 4, 2300, 800, 24] },
        { actor: 'high rug', box: [2400, 100, 40, 2600, 200, 44] }]);
      check('kinds', same(Object.fromEntries(kinds), { asphalt: 'floor', sidewalk: 'floor', barfloor: 'floor', rug: 'decoration',
            plate: 'decoration', lone: 'floor', wall: 'other', slab: 'floor', 'high rug': 'floor' }), Object.fromEntries(kinds));
      // the actor's yawed, scaled box from its mesh bounds
      const box = fl.worldBox([{ mesh: 'm', location: [100, 200, 0], rotation: [0, 16384, 0], scale: [2, 1, 1] }], { m: { bounds: [10, 0, 5, 10, 4, 5, 20] } });
      check('world box', box.map(v => Math.round(v * 1000) / 1000).join() === '96,200,0,104,240,10', box);
      // saved floors: the median height on the most common level
      const tiles = [[0, 0, 0, 16], [1, 0, 0, 16], [2, 0, 0, 17], [0, 0, 1, 80]].map(([x, y, l, z]) => ({ tile: [x, y, l], location: [48 + 96 * x, 48, z], actor: 'S' }));
      const owned = fl.ownedFloors(tiles);
      check('owned floors', same(owned.get('S'), { z: 16, level: 0, count: 4 }), owned.get('S'));
      // floor stamps: one-component floor pieces only, with their saved floor over the pivot
      const part = (actor, mesh) => ({ actor, actorClass: 'XComLevelActor', archetype: 'None', mesh, materials: ['m'], scale: [1, 1, 1], tint: [1, 1, 1, 1] });
      const stamps = fl.floorStamps([{ actor: 'S', parts: [part('S', 'side')], location: [0, 0, 0] },
                                     { actor: 'V', parts: [part('V', 'roof'), part('V', 'cab')], location: [0, 0, 60] }],
                                    new Map([['S', 'floor'], ['V', 'floor']]), new Map([['S', { z: 16 }], ['V', { z: 75 }]]));
      check('floor stamps', stamps.size === 1 && stamps.get(fl.stampSignature([part('S', 'side')]))?.support === 16, [...stamps]);
      // the level height: a sidewalk (pivot 0, its floor 16 over it) on the road, on a sidewalk, upstairs; a storey's
      // floor (pivot 192, its floor 2 over it) dropped on the ground
      check('level height', fl.levelHeight(0, 16, 0) === 0 && fl.levelHeight(0, 16, 16) === 0 && fl.levelHeight(0, 16, 18) === 0
            && fl.levelHeight(0, 16, 208) === 192 && fl.levelHeight(192, 2, 2) === 0 && fl.levelHeight(192, 2, 66) === 64);
      // the floor under a point: the saved floor it lies on, else the point
      const grid = { origin: [0, 0, 0], size: [96, 96, 64], dims: [50, 50, 10] };
      const index = fl.floorIndex([{ tile: [5, 5, 0], location: [528, 528, 16], actor: 'A' }, { tile: [5, 5, 3], location: [528, 528, 208], actor: 'B' }]);
      check('floor under', fl.floorUnder(index, grid, [530, 530, 17]).z === 16 && fl.floorUnder(index, grid, [530, 530, 210]).z === 208
            && fl.floorUnder(index, grid, [530, 530, 60]).z === 16 && fl.floorUnder(index, grid, [700, 700, 3]).floor === null);
      // a building floor's walking height: its saved floor tiles near its bottom (not the 381 ones a level up, nor those
      // outside its volume), else its bottom; none without volumes
      const storey = { bottom: 208, boxes: [{ min: [0, 0, 208], max: [960, 960, 400] }] };
      const st = [[100, 100, 210], [200, 100, 210], [300, 100, 381], [5000, 5000, 210], [400, 100, 212]].map(location => ({ location }));
      check('storey height', fl.storeyHeight(storey, st) === 210 && fl.storeyHeight(storey, []) === 208 && fl.storeyHeight({ bottom: 0, boxes: [] }, st) === null,
            [fl.storeyHeight(storey, st), fl.storeyHeight(storey, [])]);
      // the building for a floor: the one standing over the point, else the nearest with that floor
      const v = (x0, x1) => ({ boxes: [{ min: [x0, 0, 0], max: [x1, 960, 200] }] });
      const bs = [{ floors: [v(0, 960), v(0, 960)] }, { floors: [v(2000, 2960)] }];
      check('building with floor', fl.buildingWithFloor(bs, 1, 2500, 100) === 0 && fl.buildingWithFloor(bs, 0, 2500, 100) === 1
            && fl.buildingWithFloor(bs, 0, 1500, 100) === 1 && fl.buildingWithFloor(bs, 0, 500, 100) === 0 && fl.buildingWithFloor(bs, 5, 0, 0) === -1);
      // the Build's building-floor cases
      for (const c of cases.floorAt) {
        const at = fl.floorAt(c.buildings.map(floors => ({ floors: floors.map(boxes => ({ boxes })) })), c.box);
        check(`floorAt: ${c.case}`, same(at ? [at.building, at.floor] : null, c.at), at);
      }
      for (const c of cases.copyFloors) {
        const got = fl.copyFloors(c.listings.map(([building, floor, cutdownFloor]) => ({ building, floor, cutdownFloor })),
          c.here && { building: c.here[0], floor: c.here[1] }, c.there && { building: c.there[0], floor: c.there[1] }, b => c.floors[b]);
        check(`copyFloors: ${c.case}`, same(got.map(l => [l.building, l.floor, l.cutdownFloor]), c.expect), got);
      }
      return out;
    }""", cases)
    assert not failures, failures


def look_down(page, xyz, height=3200):
    page.evaluate("""([[x, y, z], h]) => { viewer.controls.target.set(x, z, y); viewer.camera.position.set(x + 200, z + h, y + h * 0.28); viewer.controls.update(); }""", [xyz, height])
    page.wait_for_timeout(200)


def check_floor_placing(page, is_bar):
    """Floor pieces on the map: the piece list's Floors (flat pieces carrying the saved floor tiles, not decorations);
    placing one keeps its height in the map, moved by whole levels to the floor under the cursor, so it never stacks
    on the floor it is dropped on (Bar: a sidewalk dropped on a sidewalk stands at the sidewalks' height); a pasted
    floor piece snaps too; a decoration (Bar's rug) and any other piece are placed on the surface as before. Bar: with
    floor 2 chosen in the Floor picker, a sidewalk dropped on the road takes floor 2's height; Level snap off (L), it
    stacks on what it is dropped on; moved up with the gizmo, a floor piece steps by whole levels, unless Level snap is
    off."""
    count, original = page.evaluate('viewer.roots.size'), page.evaluate('viewer.gizmo.active')
    info = page.evaluate('viewer.floorPieces()')
    if not info['supports']: return
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
    page.mouse.move(*at); page.wait_for_timeout(100)
    page.mouse.click(*at)
    page.wait_for_function('viewer.editState().added.length === 1')
    z = page.evaluate("""() => [...viewer.roots.values()].find(r => r.userData.source.added).userData.source.location[2]""")
    expect = target['pivot'][2] + round((loc[2] - target['pivot'][2] - support) / 64) * 64
    assert abs(z - expect) < 0.01 and abs(z + support - loc[2]) <= 32, (z, expect, loc, support, target['pivot'])
    if is_bar: assert abs(z) < 0.01, z     # at the sidewalks' height, not stacked 16 to 18 units up
    page.keyboard.press('Control+z')
    assert page.evaluate('viewer.changes().total') == 0
    if is_bar:
        assert page.evaluate('viewer.levelSnap()') and 'on' in page.locator('#editLevels').get_attribute('class').split()
        side_entry = page.locator('#libList .libitem', has_text='SidewalkStrA8x4').first
        added_z = lambda: page.evaluate("""() => [...viewer.roots.values()].find(r => r.userData.source.added).userData.source.location[2]""")
        # Level snap off (L): the sidewalk dropped on the sidewalk stacks on it, as any piece does
        page.evaluate('document.activeElement && document.activeElement.blur()')
        page.keyboard.press('l')
        assert not page.evaluate('viewer.levelSnap()') and 'on' not in page.locator('#editLevels').get_attribute('class').split()
        side_entry.click()
        assert 'a floor piece' not in page.locator('#dragHint').inner_text()
        look_down(page, loc, 2200)
        page.mouse.move(*at); page.wait_for_timeout(100); page.mouse.click(*at)
        page.wait_for_function('viewer.editState().added.length === 1')
        assert added_z() > 10, added_z()
        page.keyboard.press('Control+z')
        page.keyboard.press('l')
        assert page.evaluate('viewer.levelSnap()')
        # The Floor picker: floor 2 chosen, a sidewalk dropped on the road (an asphalt plane's tile at z 0) takes floor
        # 2's height in the nearest building (the bar's: 210, so its pivot 192)
        road = page.evaluate("""() => { const k = viewer.floorPieces().kinds;
          return viewer.data.tactical.floorTiles.filter(t => k[t.actor] === 'floor' && Math.abs(t.location[2]) < 2
            && viewer.data.meshes[viewer.data.objects.find(o => o.actor === t.actor).mesh].name.endsWith('AsphaltPlaneFlat')).slice(0, 300).map(t => t.location); }""")
        choose(page, 'floor', '2')
        side_entry.click()
        assert "floor 2's height" in page.locator('#dragHint').inner_text(), page.locator('#dragHint').inner_text()
        spot2 = None
        for rl in road:
            look_down(page, rl, 2200)
            at2 = page.evaluate('p => viewer.screenOf(p)', rl)
            hit = page.evaluate('([x, y]) => { const h = viewer.pick(x, y); return h ? h.point.y : null; }', at2)
            if hit is not None and abs(hit - rl[2]) < 4: spot2 = (rl, at2); break
        assert spot2, 'no road tile clear under the cursor'
        rl, at2 = spot2
        page.mouse.move(*at2); page.wait_for_timeout(100); page.mouse.click(*at2)
        page.wait_for_function('viewer.editState().added.length === 1')
        chosen = page.evaluate('([x, y]) => viewer.chosenStorey(x, y)', rl[:2])
        assert chosen and chosen['floor'] == 1, chosen
        expect2 = target['pivot'][2] + round((chosen['z'] - target['pivot'][2] - support) / 64) * 64
        assert abs(added_z() - expect2) < 0.01 and expect2 > 100, (added_z(), expect2, chosen)
        page.keyboard.press('Control+z')
        choose(page, 'floor', 'all')
        assert page.evaluate('viewer.changes().total') == 0
    # a decoration (Bar's rug) and a piece that isn't a floor are placed as before: no level snapping
    if is_bar:
        page.locator('#libKind').select_option('all')
        page.locator('#libFilter').fill('rug')
        page.locator('#libList .libitem', has_text='RugRedPlane').first.click()
        assert page.evaluate('viewer.placing()?.floor') is None and 'a floor piece' not in page.locator('#dragHint').inner_text()
        page.locator('#libFilter').fill('')
    page.keyboard.press('Escape')
    page.keyboard.press('p')
    assert page.locator('#library').is_hidden()
    # a floor piece copied and pasted snaps the same way
    if is_bar:
        side = page.evaluate("""() => [...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComLevelActor_133')).userData.source.id""")
        page.evaluate('id => viewer.select(id)', side)
        page.evaluate('document.activeElement && document.activeElement.blur()')
        page.keyboard.press('Control+c'); page.keyboard.press('Control+v')
        assert page.evaluate('viewer.placing()?.floor') == 16
        page.keyboard.press('Escape')
        # Moved up with the gizmo's up arrow, the sidewalk steps by whole levels; with Level snap off, freely
        def drag_up(pixels):
            page.evaluate('id => { viewer.select(id); viewer.frame(viewer.roots.get(id)); }', side)
            page.evaluate('document.activeElement && document.activeElement.blur()')
            page.keyboard.press('g')
            page.wait_for_timeout(200)
            z0 = page.evaluate('viewer.gizmo.pose().location[2]')
            p0 = page.evaluate('viewer.screenOf(viewer.gizmo.pose().location)')
            up = page.evaluate('p => viewer.screenOf([p[0], p[1], p[2] + 100])', page.evaluate('viewer.gizmo.pose().location'))
            n = ((up[0] - p0[0]) ** 2 + (up[1] - p0[1]) ** 2) ** 0.5
            d = [(up[0] - p0[0]) / n, (up[1] - p0[1]) / n]
            grab = None
            for r in range(20, 160, 6):
                pt = [p0[0] + d[0] * r, p0[1] + d[1] * r]
                page.mouse.move(*pt); page.wait_for_timeout(30)
                if page.evaluate('viewer.gizmo.controls.axis') == 'Y': grab = pt; break
            assert grab, 'the gizmo\'s up arrow not found'
            page.mouse.down(); page.mouse.move(grab[0] + d[0] * pixels, grab[1] + d[1] * pixels, steps=8); page.mouse.up()
            return page.evaluate('viewer.gizmo.pose().location[2]') - z0
        rise = drag_up(140)
        assert rise > 1 and abs(rise / 64 - round(rise / 64)) < 1e-3, rise
        page.keyboard.press('Control+z')
        page.keyboard.press('l')
        rise = drag_up(140)
        assert rise > 1 and abs(rise / 64 - round(rise / 64)) > 1e-3, rise
        page.keyboard.press('Control+z')
        page.keyboard.press('l')
        assert page.evaluate('viewer.levelSnap()') and page.evaluate('viewer.changes().total') == 0
        page.keyboard.press('v')
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.roots.size') == count
    page.evaluate('id => viewer.select(id)', original)


def check_floor_tiles(page, is_bar):
    """View options, Floor tiles (private/plans/done/floor-brush-plan.md, 3.7): the saved floor tiles in one batched mesh, a
    deleted piece's hatched, a tile's piece named on hover and selected on a click; and a copy's building-floor
    listings following where it stands (3.8), on Bar's floor pieces."""
    total = page.evaluate('viewer.data.tactical?.floorTiles?.length ?? 0')
    if not total: return
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
    page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', t['tile']['location'])); page.wait_for_timeout(200)
    assert page.locator('#floorTip').is_visible() and t['tile']['actor'].split('.')[-1] in page.locator('#floorTip').inner_text()
    page.evaluate('id => viewer.select(id)', t['id'])
    page.keyboard.press('Delete')
    assert page.evaluate('viewer.floorTiles()') == drawn
    assert page.evaluate("viewer.world.children.some(g => g.userData.tiles && g.children.some(c => c.isLineSegments))")
    page.mouse.move(10, 10); page.mouse.move(*page.evaluate('p => viewer.screenOf(p)', t['tile']['location'])); page.wait_for_timeout(200)
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
    page.wait_for_timeout(300)
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
    choose(page, 'lighting', 'map'); page.wait_for_timeout(300)
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
        page.wait_for_timeout(300)
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
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): page.close(); return None
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
    if not done: page.close(); return None
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
    page.evaluate("""() => { const f = window.fetch; window.slowNames = true;
      window.fetch = (u, o) => String(u).includes('output-names') && window.slowNames
        ? new Promise(r => setTimeout(() => r(f(u, o)), 1500)) : f(u, o); }""")
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    page.locator('#fileName').fill(name)
    page.wait_for_timeout(400)
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
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"): return
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
    keeps it where the map has it. Everything is undone at the end, and the selection it found selected again."""
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"): return
    held = page.evaluate('viewer.gizmo.active')
    blur = lambda: page.evaluate('document.activeElement?.blur()')
    state = lambda id: page.evaluate('id => { viewer.effectMarkers(); return viewer.effectState(id); }', id)
    # a drag of the gizmo along game X, as TransformControls makes one (an effect's panel has no pose fields)
    drag = lambda dx: page.evaluate('''dx => { const c = viewer.gizmo.controls, p = c.object; c.dispatchEvent({type: 'mouseDown'});
        p.position.x += dx; p.updateMatrixWorld(true); c.dispatchEvent({type: 'objectChange'}); c.dispatchEvent({type: 'mouseUp'}); }''', dx)
    snap = page.evaluate('viewer.gizmo.snap')
    page.evaluate("viewer.gizmo.setSnap('off')")
    fx = page.evaluate("""[...viewer.effectRoots.values()].map(r => r.userData.source).find(o => o.kind === 'effect' && !o.stream
        && !o.carriedBy && !o.landingActor && o.can?.move && o.can?.delete && o.can?.copy)?.id ?? null""")
    if not fx: return
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
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"): return
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
    # switch on: the effect is inside, and the bar counts it
    page.evaluate('viewer.setNormalEffects(true)')
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
    if page.evaluate("!(viewer.data.exporterVersion >= 28) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"): return
    flare = page.evaluate("""(() => { const all = [...viewer.effectRoots.values()].map(r => r.userData.source).filter(o => o.kind === 'flare' && !o.stream
        && o.layer === 'base' && o.template && o.can?.move && o.can?.delete && o.can?.copy);
      return all.length ? { id: all[0].id, actor: all[0].actor, template: all[0].template, same: all.filter(o => o.template === all[0].template).length } : null; })()""")
    if not flare: return
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
    assert 'Shows ' + flare['template'] in page.locator('#effectInfo').inner_text()
    assert page.locator('#effectValues').is_hidden() and page.locator('#effectWaves').is_hidden()
    blur()
    done = lambda: (page.evaluate('s => { viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(false); viewer.gizmo.setSnap(s); }', snap),
                    page.evaluate('id => viewer.select(id)', held))
    if state(fx)['viewOnly']:
        assert not page.evaluate('viewer.families().families.flare.builds')
        page.keyboard.press('Delete')
        assert not state(fx)['deleted'] and 'lens flares are shown, not changed' in page.locator('#dragHint').inner_text()
        assert 'The gizmo' not in page.locator('#effectInfo').inner_text()
        done(); return
    assert page.evaluate('viewer.families().families.flare.builds')
    assert 'The gizmo moves and turns it, Ctrl+C and Ctrl+V copy it, Delete deletes it' in page.locator('#effectInfo').inner_text()
    depth = page.evaluate('viewer.gizmo.undoDepth()')
    # a move: an override with a pose and nothing else; undone
    start = state(fx)['at']
    drag(96)
    moved = state(fx)
    assert moved['moved'] and abs(moved['at'][0] - start[0] - 96) < 0.01, (start, moved)
    override, = page.evaluate('a => viewer.editState().overrides.filter(o => o.target.actor === a)', flare['actor'])
    assert sorted(override) == ['location', 'rotation', 'target'], override
    assert page.locator('#effectInfo').inner_text().startswith('Moved')
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
    assert page.locator('#effectInfo').inner_text().startswith('A copy of ' + flare['actor'].split('.')[-1])
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
    assert button.is_visible() and f"({flare['same'] + 1})" in button.inner_text() and flare['template'].split('.')[-1] in button.inner_text(), button.inner_text()
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
        page.close(); return
    page.evaluate("localStorage.removeItem('workshop.libraryView')")
    page.keyboard.press('p')
    choose(page, 'libScope', 'all')
    page.wait_for_function('viewer.library.ready()', timeout=60000)
    if not page.evaluate("viewer.library.entries().some(e => e.effect === 'flare')"):
        page.close(); return
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
    saved = page.evaluate("viewer.savePrefab('Smoke flares').then(s => ({ id: s.id, revision: s.revision }))")
    listed = page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs']
    prefab, = [p for p in listed if p['id'] == saved['id']]
    assert (prefab['pieces'], prefab['effects'], prefab['sounds'], prefab['flares']) == (0, 0, 0, 2), prefab
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 3 and all(sorted(p) == ['actor', 'from', 'kind', 'location', 'rotation'] and p['kind'] == 'flare' for p in doc['pieces']), doc['pieces']
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    page.wait_for_selector('#prefabList .libitem')
    item = page.locator('#prefabList .libitem', has_text='Smoke flares')
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
    type_project_name(page, 'Library flares smoke')
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
    assert page.locator('#buildTitle').inner_text().startswith('Built Library flares smoke'), page.locator('#buildModal').inner_text()
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
    if page.evaluate("!(viewer.data.exporterVersion >= 29) || viewer.data.scope !== 'map' || Boolean(viewer.data.preview)"): return None
    held = page.evaluate('viewer.gizmo.active')
    state = page.evaluate('viewer.projectState()')
    page.evaluate('viewer.select(null); viewer.setEffectsShown(false); viewer.setNormalEffects(false); viewer.setLikeness(true)')
    if page.locator('#scenery').is_visible(): choose(page, 'scenery', 'full')
    page.evaluate('viewer.frame()')
    page.wait_for_timeout(1500)
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
        page.wait_for_timeout(300)
        page.evaluate('viewer.setEffectsShown(false)')
        page.wait_for_timeout(700)
        assert target in like()['drawn'], like()
        page.evaluate('viewer.setLikeness(false)')
        page.wait_for_timeout(300)
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
        page.wait_for_timeout(300)
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
        page.wait_for_timeout(200)
        assert target not in like()['drawn'] and like()['effects'] < now['effects'], like()      # (its linked effects go with it)
        page.keyboard.press('Control+z')
        page.wait_for_timeout(200)
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
    if not sound: return
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
    if page.evaluate('!viewer.data.streams || Boolean(viewer.data.preview)'): return
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
    if not piece: return
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
    if not found: return
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
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview && Array.isArray(viewer.data.spawns)'): return
    normal = page.evaluate('viewer.normalSpawns()')
    page.evaluate('viewer.setNormalSpawns(false); viewer.select(null)')
    pod = page.evaluate("(viewer.spawns().find(s => s.kind === 'pod' && s.layer === 'base') ?? null)")
    if pod:
        page.evaluate('k => { const s = viewer.spawns().find(x => x.key === k); viewer.showSpawn(s.actor, null); viewer.pickSpawn(null); viewer.setNormalSpawns(false); }', pod['key'])
        page.wait_for_timeout(200)
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


def check_project_menu(page):
    """The Project menu, first after the name, and the Save and Load dialogs opened and cancelled (nothing saved)."""
    assert page.evaluate("document.querySelector('header .brand').nextElementSibling.id") == 'projectButton'
    kept = page.evaluate('viewer.gizmo.active')
    page.evaluate('id => viewer.select(id)', kept or page.evaluate('[...viewer.roots.keys()][0]'))
    changes = page.evaluate('viewer.changes()')
    page.locator('#projectButton').click()
    assert page.locator('#projectMenu').is_visible()
    labels = [t.strip() for t in page.locator('#projectMenu .menuitems button:visible span').all_inner_texts()]
    # Map grid and Clear map… on a whole map (Clear map plan)
    assert labels[:9] == ['Save', 'Save as…', 'Build…', 'Play in game', 'Game maps…', 'Map grid', 'Clear map…', 'Load…', 'Manage projects…'], labels
    page.wait_for_function("document.querySelector('#projectRecent').childElementCount > 0")
    # Installs: the game install, the install plays go to, how the game is started and what the editor has in it
    # (or why they are not known)
    page.wait_for_function("document.querySelectorAll('#installInfo dd').length === 4")
    assert page.locator('#installInfo dt').all_inner_texts() == ['Game', 'Plays in', 'Started', 'In the game']
    assert page.locator('#projectRecent .projectitem').count() <= 3
    page.keyboard.press('Escape')
    assert page.locator('#projectMenu').is_hidden()
    # Ctrl+O: the Load dialog over every map's projects; Escape closes it and leaves the selection alone.
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Control+o')
    page.wait_for_selector('#fileDialog:not([hidden])')
    assert page.locator('#fileTitle').inner_text() == 'Load project' and page.locator('#fileOk').inner_text() == 'Open'
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
    """Settings, just before Import notes, and Test squad setup (squad.js): the panel's list and unit editor, a kind
    change and what it cleared, an error for a name the game can't take, Escape and Cancel leaving the saved squad as
    it was, and the play dialog's squad line opening the panel over it. saves: the server's --squad is a scratch file,
    so the check also saves, sees a save from elsewhere refused with the draft kept, and puts the squad back."""
    assert page.evaluate("document.querySelector('#settingsButton').nextElementSibling.id") == 'notesButton'
    page.locator('#settingsButton').click()
    assert page.locator('#settingsMenu').is_visible()
    labels = [t.strip() for t in page.locator('#settingsMenu .menuitems button span').all_inner_texts()]
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
        page.locator('#settingsButton').click(); page.locator('#settingsSquad').click()
        page.wait_for_function("document.querySelectorAll('#squadUnits li').length > 0")
        page.fill('#squadName', 'Smoke squad')
        page.locator('#squadSave').click()
        page.wait_for_selector('#squadDialog', state='hidden')
        mine = page.evaluate("fetch('/squad.json').then(r => r.json())")
        assert mine['document']['name'] == 'Smoke squad' and mine['revision'] != saved['revision']
        page.locator('#settingsButton').click(); page.locator('#settingsSquad').click()
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
        page.locator('#projectButton').click(); page.locator('#projectPlay').click()
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
    replacing a project and renaming the open one, the Load dialog, and the recent list."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409,))
    if not page.evaluate('viewer.data.scope === "map" && !viewer.data.preview'): page.close(); return
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
    shown = type_project_name(page, 'Smoke test project')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    first = page.evaluate('viewer.project().id')
    assert f'project={first}' in page.url and page.locator('#projectTitle').inner_text() == 'Smoke test project'
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
    assert page.locator('#buildOptionsTitle').inner_text() == 'Build Smoke test project'
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
    save_dialog(page, 'Smoke test project')
    assert page.locator('.filerow.on').get_attribute('data-id') == first and 'open' in page.locator('.filerow.on').inner_text()
    type_project_name(page, 'Smoke test empty')
    assert page.locator('.filerow.on').count() == 0
    page.locator('#fileName').press('Enter')
    page.wait_for_function('id => viewer.project()?.id !== id && viewer.project().revision === 1', arg=first)
    empty = page.evaluate('viewer.project()')
    assert empty['doc']['output']['shipAs'] != doc['output']['shipAs']
    page.goto(project_url(page, empty['id']))
    page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=120000)
    assert page.evaluate('viewer.changes().total') == 0 and page.evaluate('viewer.project().name') == 'Smoke test empty'
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
    save_dialog(page, 'smoke TEST project')
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
    assert now['name'] == 'smoke TEST project' and now['doc']['output'] == doc['output'] and f'project={first}' in page.url
    assert page.evaluate('viewer.projectState()') == replaced
    assert page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", empty['id'])['revision'] == 3
    # The open project's own name in another case saves its next revision, renamed, without a confirm.
    save_dialog(page, 'Smoke Test Project')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 6')
    assert page.evaluate('viewer.project()')['name'] == 'Smoke Test Project' and page.evaluate('viewer.project().id') == first
    # Each project is one file named after it, renamed with it (the case too).
    files = {p['id']: p['file'] for p in page.evaluate("fetch('/projects.json').then(r => r.json())")['projects']}
    assert files == {first: 'Smoke Test Project.json', empty['id']: 'Smoke test empty.json'}, files
    # Ctrl+O, the Load dialog: it starts on the open project; typing finds another; Enter opens it.
    page.evaluate('document.activeElement && document.activeElement.blur()')
    page.keyboard.press('Control+o')
    page.wait_for_selector('#fileDialog:not([hidden]) .filerow')
    assert page.locator('.filerow.on').get_attribute('data-id') == first
    page.locator('#fileName').fill('smoke test em')
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


def check_prepare(browser, url, project_id=None):
    """The prepare-again dialog, with the server's answers stood in for (no map is exported): a map whose export is
    older than building needs opens with the dialog in the middle of the window; Later (or Esc) leaves a banner that
    opens it again; Prepare now shows the export's progress and reopens the map. With project_id (a saved project on
    this map, on a test server with scratch builds: a quick build of it really runs): Build asks to prepare instead
    of building; and a build that failed for want of a newer export offers Prepare the map, which starts it."""
    errors = []
    old = dict(on=True)
    asked = dict(count=0)

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

    def routed(page):
        page.route('**/maps/*/families.json', families)
        page.route('**/maps/*/export', export)
        page.route('**/maps/*/export.json', export_status)

    page = browser.new_page(viewport=dict(width=1600, height=1000), device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())
    routed(page)
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


def check_play(browser, url, project_id=None, screenshot=None):
    """Play in game in the Project menu, Game maps' Undo everything, and the menu's Installs section. Only against a test server
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
        if page.locator('#projectMenu').is_hidden(): page.locator('#projectButton').click()
        page.wait_for_function("document.querySelectorAll('#installInfo dd').length === 4")

    def undo_everything():
        """Game maps (Project menu), Undo everything: what it says it took out."""
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
    if screenshot: page.locator('#projectMenu').screenshot(path=str(screenshot.with_stem(screenshot.stem + '-play-menu')))
    if page.evaluate('viewer.data.scope === "map" && !viewer.data.preview && !viewer.project()'):
        page.locator('#projectPlay').click()
        if page.evaluate('(viewer.data.missions || []).length > 1'):
            # a map with several missions: the play dialog names the mission (the header's), with its kind's line
            page.wait_for_selector('#buildOptions', state='visible')
            assert page.locator('#buildMissionRow').is_visible() and page.locator('#buildBakeRow').is_hidden()
            assert 'Enemies:' in page.locator('#buildMissionNote').inner_text() and 'played' not in page.locator('#buildMissionNote').inner_text().lower(),                 page.locator('#buildMissionNote').inner_text()
            page.locator('#buildOptionsOk').click()
        page.wait_for_function("() => { const b = document.querySelector('#projectBanner'); return !b.hidden && b.textContent.startsWith('Starting XCOM'); }",
                               timeout=60000)
        assert '(original map)' in page.locator('#projectBanner').inner_text()
        # the "Starting XCOM …" message closes itself after 12 s (× closes it sooner; banner() above clicks it)
        page.wait_for_selector('#projectBanner', state='hidden', timeout=16000)
        now = status()['game']
        assert now['lastPlay']['map'] == page.evaluate('viewer.mapId') and now['installed'] == [] and now['playFile'], now
    assert undo_everything().startswith('Taken out of the game')
    assert status()['game']['anything'] is False
    menu()
    page.wait_for_function("document.querySelectorAll('#installInfo dd')[3].textContent.startsWith(\"Nothing of the editor's\")")
    # Game maps (Project menu): with nothing of the editor's in the game, Undo everything is greyed out
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
        menu()   # shown at once from the play's answer
        row = page.locator('#installInfo dd').nth(3).inner_text()
        assert row.endswith(f"({installed['map']})" + (', lighting not baked' if installed.get('quick') else '')), row
        if screenshot: page.locator('#projectMenu').screenshot(path=str(screenshot.with_stem(screenshot.stem + '-play-project')))
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
        page.locator('#buildClose').click()
        assert '1 map record' in undo_everything()
    page.close()
    assert not errors, errors


def check_prefabs(browser, url):
    """The prefab library (prefab plan stage P; prefabs.js, tools/viewer/prefabs.py). Only against a test server whose
    --projects is a scratch folder (its prefabs folder is beside it) and whose game install is set. On a map with a
    car: a car, a prop, a light and a building, the car and the prop grouped, saved as a prefab from the dialog;
    placed twice, once turned, each one group marked with the prefab, by whole tiles, one undo step; a prefab with two
    of the same car places two cars that move apart (the link tag), and so does a copy of both; the tab's Rename,
    Duplicate, Export, Delete and Import with its choice; then the prefab placed in another map, its pieces read from
    their home map, saved and built without baking."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409, 422))
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"): page.close(); return
    car = page.evaluate("(viewer.families()?.assemblies ?? []).find(a => a.family === 'car' && a.members.length > 1) ?? null")
    if not car: page.close(); return
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
    assert low[0] >= 0 and low[1] >= 0 and low[0] % 96 == 0 and low[1] % 96 == 0 and min(low[0], low[1]) < 96 * 3, records['buildings']
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
    assert 'Saved the prefab Smoke prefab' in page.locator('#dragHint').inner_text()
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
    assert clip == dict(entries=2 * ids['parts'], left=[], locked=True), clip
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
    # ---- the tab: filter, rename, duplicate, export, delete, import with its choice
    page.evaluate('viewer.select(null)')
    page.keyboard.press('p')
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
    page.locator('#prefabFilter').fill('two')
    assert page.locator('#prefabList .libitem').count() == 1 and '1 of 2 prefabs' in page.locator('#prefabFoot').inner_text()
    item = page.locator('#prefabList .libitem').first
    item.get_by_role('button', name='Rename').click()
    page.locator('.prefabrename').fill('Two sedans')
    page.locator('.prefabrename').press('Enter')
    page.locator('#prefabFilter').fill('')
    page.wait_for_function("[...document.querySelectorAll('#prefabList .libitem strong')].some(s => s.textContent === 'Two sedans')")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans']
    row = page.locator('#prefabList .libitem', has_text='Two sedans')
    row.get_by_role('button', name='Duplicate').click()
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 3")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans', 'Two sedans copy']
    with page.expect_download() as download:
        page.locator('#prefabList .libitem', has_text='Smoke prefab').get_by_role('button', name='Export').click()
    exported = json.loads(Path(download.value.path()).read_text(encoding='utf8'))
    assert download.value.suggested_filename == 'Smoke prefab.json' and exported['id'] == saved['id'] and exported['schema'] == 'xcom-map-workshop/prefab'
    assert 'mesh' not in json.dumps(exported).lower().replace('meshcomponent', '')     # references and numbers only
    copy = page.locator('#prefabList .libitem', has_text='Two sedans copy')
    copy.get_by_role('button', name='Delete').click()
    assert 'Delete Two sedans copy?' in copy.inner_text()
    copy.get_by_role('button', name='Keep it').click()
    assert len(listed()) == 3
    copy = page.locator('#prefabList .libitem', has_text='Two sedans copy')
    copy.get_by_role('button', name='Delete').click()
    copy.get_by_role('button', name='Delete it').click()
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 2")
    assert sorted(p['name'] for p in listed()) == ['Smoke prefab', 'Two sedans']
    # a file from elsewhere: one the library has already asks; Keep both stores it beside
    sent = dict(exported, name='Smoke prefab, sent back')
    payload = dict(name='sent.json', mimeType='application/json', buffer=json.dumps(sent).encode())
    page.locator('#prefabFile').set_input_files(payload)
    page.wait_for_function("document.getElementById('prefabNote').textContent.includes('already has this prefab')")
    assert 'Smoke prefab' in page.locator('#prefabNote').inner_text() and len(listed()) == 2
    page.locator('#prefabNote').get_by_role('button', name='Keep both').click()
    page.wait_for_function("document.querySelectorAll('#prefabList .libitem').length === 3")
    assert 'Smoke prefab, sent back (imported)' in [p['name'] for p in listed()]
    # one that is no prefab says why and changes nothing
    page.locator('#prefabFile').set_input_files(dict(name='bad.json', mimeType='application/json', buffer=json.dumps(dict(sent, pieces=[dict(actor='<b>')])).encode()))
    page.wait_for_function("document.getElementById('prefabNote').textContent.startsWith('Not imported')")
    assert len(listed()) == 3
    page.locator('#prefabNote button').click()
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
    if not other: return
    page = open_viewer(browser, url.split('?')[0] + f'?map={other}', errors)
    page.wait_for_timeout(500)
    if page.locator('#prepareModal').is_visible(): page.locator('#prepareLater').click()
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"): page.close(); return
    count = page.evaluate('viewer.roots.size')
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
    page.keyboard.press('p')
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, 'Prefab smoke')
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
    assert page.locator('#buildTitle').inner_text().startswith('Built Prefab smoke'), page.locator('#buildModal').inner_text()
    build = page.evaluate("id => fetch(`/projects/${id}/build.json`).then(r => r.json())", project)
    assert build['state'] == 'built' and build['package']['foreignPieces'] == ids['cars'] + 1, build
    assert [d['map'] for d in build['package']['donors']] == [here], build['package']['donors']
    page.locator('#buildClose').click()
    assert not errors, errors
    page.close()


def check_prefab_effects(browser, url):
    """Effects and sounds in a prefab (effects and sounds plan, stage FX6a), on URB_Bar against check_prefabs' kind of
    test server, after it (its prefab is deleted at the end): a prop, a free effect and a sound grouped and saved as
    a prefab (schema 3, each of its kind with its source, counted, no footprint from the sound's reach); placed in
    this map (copies of their kinds, one group marked with the prefab, the effect's likeness with the cursor); then
    in another map, read from their home map, saved, reopened and built without baking."""
    errors = []
    page = open_viewer(browser, url, errors, expected=(409, 422))
    if not page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && viewer.data.exporterVersion >= 29 && viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')"):
        page.close(); return
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
    if not ids: page.close(); return
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
    saved = page.evaluate("viewer.savePrefab('Smoke effects').then(s => ({ id: s.id, revision: s.revision }))")
    listed = lambda: page.evaluate("fetch('/prefabs.json').then(r => r.json())")['prefabs']
    row, = [p for p in listed() if p['id'] == saved['id']]
    assert (row['pieces'], row['lights'], row['effects'], row['sounds'], row['maps']) == (1, 0, 1, 1, [here]), row
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 3 and sorted(p.get('kind', 'piece') for p in doc['pieces']) == ['effect', 'piece', 'sound']
    page.keyboard.press('p')
    choose(page, 'libScope', 'prefabs')
    page.wait_for_selector('#prefabList .libitem')
    assert '1 piece, 1 effect and 1 sound' in page.locator('#prefabList .libitem', has_text='Smoke effects').inner_text()

    def place(page):
        count, fxs = page.evaluate('viewer.roots.size'), page.evaluate('viewer.effectRoots.size')
        page.locator('#prefabList .libitem', has_text='Smoke effects').click()
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
        assert marked['prefab']['name'] == 'Smoke effects' and len(marked['members']) == 3, marked
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
        page.wait_for_timeout(500)
        if page.locator('#prepareModal').is_visible(): page.locator('#prepareLater').click()
        if page.evaluate("viewer.data.scope === 'map' && !viewer.data.preview && Boolean(viewer.data.tileGrid?.origin)"):
            page.keyboard.press('p')
            choose(page, 'libScope', 'prefabs')
            page.wait_for_selector('#prefabList .libitem')
            added = place(page)
            assert page.evaluate("[...viewer.effectRoots.values()].filter(r => r.userData.source.added && r.userData.source.foreign?.package).length") == 2
            page.keyboard.press('p')
            page.keyboard.press('Control+s')
            page.wait_for_selector('#fileDialog:not([hidden])')
            type_project_name(page, 'Prefab effects smoke')
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
            assert page.locator('#buildTitle').inner_text().startswith('Built Prefab effects smoke'), page.locator('#buildModal').inner_text()
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",default="http://127.0.0.1:8768/")
    ap.add_argument("--screenshot",type=Path,required=True)
    ap.add_argument("--projects",action="store_true",help="Also check projects: saves into the server's projects folder, so "
                    "use a test server started with --projects <scratch folder>, never the main one")
    ap.add_argument("--play",action="store_true",help="Also check Play in game and Game maps' Undo everything: changes the server's "
                    "install, so only for a test server started with --install <a scratch game folder> --dry-play")
    ap.add_argument("--play-project",help="With --play: also play this project's build (it must be of its saved revision)")
    ap.add_argument("--squad",action="store_true",help="The server's --squad is a scratch file: the squad check also saves (and puts the squad back)")
    ap.add_argument("--only",help="Run only these checks once the map opens, comma-separated (floor-placing, floor-tiles, lights, library, library-all, library-effects, effect-values, library-assembly, prefabs, builder, prefab-test, cover, zoom, box-select, copy-drag, floor-boxes, pan, speeds, pivot, text-select, play-area, map-buildings, clear-map, streams, spawns, light-grid, output-names, squad, effects, flares, library-flares, likeness), and stop: "
                    "for working on them")
    args = ap.parse_args()
    args.screenshot.parent.mkdir(parents=True,exist_ok=True)
    errors = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge",headless=True)
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
        is_bar = page.evaluate("viewer.data.source.file.toLowerCase().endsWith('urb_bar.upk')")
        is_temple = page.evaluate("viewer.data.source.file.toLowerCase().endsWith('templeship.upk')")
        is_police = page.evaluate("viewer.data.source.file.toLowerCase().endsWith('urb_policestation.upk')")
        if args.only:
            only = {k.strip() for k in args.only.split(',')}
            if page.locator('#scenery').is_visible(): choose(page,'scenery','full')
            if 'floor-placing' in only: check_floor_rules(page); check_floor_placing(page, is_bar)
            if 'floor-tiles' in only: check_floor_tiles(page, is_bar)
            if 'lights' in only: check_lights(page, is_bar)
            if 'effects' in only: check_effects_view(page); check_effects_editing(page); check_effects_box(page)
            if 'flares' in only: check_flares(page)
            if 'library-flares' in only: check_library_flares(browser, page.url)
            if 'likeness' in only: print(json.dumps(dict(likeness=check_likeness(page))))
            if 'library' in only: check_library(page, is_bar)
            if 'library-all' in only: check_library_all(browser, page.url)
            if 'library-effects' in only: check_library_effects(browser, page.url)
            if 'effect-values' in only: print(json.dumps(dict(effectValues=check_effect_values(browser, page.url))))
            if 'prefabs' in only: check_prefabs(browser, page.url)
            if 'prefab_effects' in only: check_prefab_effects(browser, page.url)
            if 'prefab-test' in only:
                from browser_prefab_test import check_prefab_test
                print(json.dumps(dict(prefabTest=check_prefab_test(browser, page.url, args.screenshot)), indent=2))
            if 'builder' in only:
                from browser_builder import check_builder, check_real_sources, check_navigation, check_recovery_edges, check_recipe_recovery
                result = check_builder(browser, page.url, args.screenshot)
                result['realSources'] = check_real_sources(browser, page.url, result['buildingOnly'], args.screenshot)
                result['navigation'] = check_navigation(browser, page.url, result['buildingOnly'], result['realSources']['project'])
                result['recoveryEdges'] = check_recovery_edges(browser, page.url, result['buildingOnly'])
                result['recipeRecovery'] = check_recipe_recovery(browser, page.url)
                print(json.dumps(dict(builder=result), indent=2))
            if 'library-assembly' in only: print(json.dumps(dict(assembly=check_library_assembly(browser, page.url))))
            if 'cover' in only: check_cover(page)
            if 'zoom' in only: check_zoom(page)
            if 'box-select' in only: check_box_select(page)
            if 'copy-drag' in only: check_copy_drag(page)
            if 'floor-boxes' in only: check_floor_boxes(page)
            if 'map-buildings' in only: check_map_buildings(page)
            if 'clear-map' in only: check_clear_map(page)
            if 'streams' in only: check_streams(page)
            if 'spawns' in only: check_spawns_view(page)
            if 'pan' in only: check_arrow_pan(page)
            if 'speeds' in only: check_camera_speeds(page)
            if 'pivot' in only: check_pivot(page)
            if 'text-select' in only: check_text_select(page)
            if 'play-area' in only: check_play_area(page); check_interior_whole(page)
            if 'light-grid' in only: check_light_grid(page)
            if 'squad' in only: check_squad(page, saves=args.squad)
            if 'output-names' in only:
                found = []
                print(json.dumps(dict(outputNames=check_output_names(browser, page.url, found))))
                errors.update(found)
            page.screenshot(path=str(args.screenshot))
            errors -= EXPECTED
            print(json.dumps(dict(only=sorted(only), errors=sorted(errors)), indent=2))
            browser.close()
            if errors: raise SystemExit(1)
            return
        initial_view=value(page,'scenery')
        interior_count=None
        if is_temple and page.evaluate('viewer.data.exporterVersion >= 11'):
            assert initial_view=='interior'
            assert page.evaluate("[...viewer.roots.values()].every(r=>!['backdrop','roof','helper'].includes(r.userData.source.sceneryRole)||!r.visible)")
            assert page.evaluate("[...viewer.roots.values()].every(r=>r.userData.source.matrix.every((v,i)=>Math.abs(v-r.matrix.elements[i])<1e-5))")
            interior_count=page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
            page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-interior')))
        if page.locator('#scenery').is_visible(): choose(page,'scenery','full')
        # the map's pieces, and its missions' streamed packages' (export 13)
        assert page.evaluate('viewer.roots.size === viewer.data.objects.length + viewer.streamPieces')
        check_streams(page)
        check_spawns_view(page)
        if page.evaluate('viewer.data.exporterVersion >= 7'):
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
            if is_bar and page.evaluate('viewer.data.scope === "map"'): assert skin['rigs'] >= 21,skin
            assert skin['error'] < 0.02,skin
            assert skin['independent'],skin
            for actor_class,label in [('XComInteractiveLevelActor','door'),('KAsset','prop')]:
                if not page.evaluate('cls=>[...viewer.roots.values()].some(r=>r.userData.source.actorClass===cls)',actor_class):
                    continue
                page.evaluate("""cls=>{
                  window.detailVisibility=[...viewer.roots.values()].map(r=>[r,r.visible]);
                  const root=[...viewer.roots.values()].find(r=>r.userData.source.actorClass===cls);
                  for (const r of viewer.roots.values()) r.visible=r===root;
                  viewer.select(root.userData.source.id);viewer.frame(root);
                }""",actor_class)
                page.wait_for_timeout(300)
                page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-'+label)))
                page.evaluate('for (const [root,visible] of detailVisibility) root.visible=visible; viewer.frame();')
        if page.evaluate('viewer.data.exporterVersion >= 9 && viewer.data.scope === "map"'):
            # The map's own lights: neutral light by default (the user's choice, 7 November), the map's switchable, and
            # every local light inside the shader's grid.
            lights = page.evaluate("viewer.lighting.counts")
            assert lights['enabled'] > 0 and value(page,'lighting') == 'neutral', lights
            choose(page,'lighting','map')
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
            for mode in ('map-no-area', 'map', 'neutral'):
                choose(page,'lighting',mode)
                page.wait_for_timeout(300)
                page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-light-'+mode)))
            assert page.evaluate("viewer.sun.intensity > 0 && viewer.hemisphere.intensity > 0")
        # The search list shows only while there is text; a result selects the piece and opens its panel.
        page.keyboard.press('Escape')
        assert page.locator('#viewOptions').is_hidden()
        page.evaluate('viewer.select(null)')
        assert page.locator('#objects').is_hidden() and page.locator('#inspector').is_hidden()
        term = 'Dumpster_A' if is_bar else page.evaluate("viewer.data.meshes[viewer.data.objects.find(o=>!o.hidden && !o.environment).mesh].name.split('.').at(-1)")
        page.locator("#search").fill(term)
        assert page.locator('#objects').is_visible() and page.locator(".piece").count() > 0
        page.locator(".piece").first.click()
        assert page.locator('#objects').is_hidden()
        assert page.locator('#inspector').is_visible() and page.locator("#details h2").inner_text()
        page.locator("#search").fill("")
        assert page.locator('#objects').is_hidden()
        # A typed position moves the selection without turning it, as one undo step; so does a typed yaw.
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
        check_pivot(page)
        check_text_select(page)
        if is_bar and page.evaluate('viewer.data.exporterVersion >= 12'): check_recipe(page)
        if is_police and page.evaluate('viewer.data.exporterVersion >= 16'): check_light_bar(page)
        if page.evaluate('viewer.data.exporterVersion >= 17'): check_destruction(page, is_bar)
        check_adding(page, is_bar)
        check_zoom(page)
        check_groups(page)
        check_copy_drag(page)
        check_box_select(page)
        check_floor_boxes(page)
        check_map_buildings(page)
        check_clear_map(page)
        check_align(page)
        check_library(page, is_bar)
        check_cover(page)
        check_floor_rules(page)
        check_floor_placing(page, is_bar)
        check_floor_tiles(page, is_bar)
        if page.evaluate("viewer.data.scope === 'map'"): check_lights(page, is_bar)
        check_effects_view(page)
        check_effects_editing(page)
        check_effects_box(page)
        check_flares(page)
        check_likeness(page)
        check_project_menu(page)
        check_squad(page, saves=False)      # read-only unless --only squad --squad (its save sees a refusal: a 409 logged)
        if args.projects: check_projects(browser, page.url)
        if args.projects: check_prefabs(browser, page.url)
        if args.projects: check_prefab_effects(browser, page.url)
        if args.play: check_play(browser, page.url, args.play_project, args.screenshot)
        check_prepare(browser, page.url, args.play_project if args.play else None)
        page.locator("#selected").click()
        page.locator("#frame").click()
        if page.locator("#layout").is_visible():
            before = page.locator("#layout").inner_text()
            page.locator("#layout").click()
            assert page.locator("#layout").inner_text() != before
            page.locator("#layout").click()
        check_option(page,'grid',False)
        check_option(page,'grid',True)
        if is_bar and page.evaluate("viewer.data.exporterVersion >= 4 && viewer.data.buildings.length > 0"):
            assert page.evaluate("""() => {
              const roof=[...viewer.roots.values()].find(r => r.userData.source.actor.endsWith('.XComFracLevelActor_3'));
              if (!roof) return false;
              const materials=[]; roof.traverse(o=>{if(o.isMesh) materials.push(o.material)});
              return roof.visible && materials.every(m=>m.alphaTest===0 && !m.transparent && (!m.map || m.map.flipY===false));
            }""")
            choose(page,'floor','1')
            assert page.evaluate("""() => ![...viewer.roots.values()].find(r=>r.userData.source.actor.endsWith('.XComFracLevelActor_3')).visible""")
            assert page.evaluate("[...viewer.roots.values()].some(r=>r.visible && Number.isFinite(r.userData.cutHeight))")
            page.wait_for_timeout(300)
            page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-ground')))
            choose(page,'floor','all')
        elif page.evaluate('viewer.data.buildings.length > 0'):
            before=page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
            choose(page,'floor','1')
            after=page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')
            assert 0 < after <= before,(before,after)
            if is_temple: assert after < before,(before,after)
            page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-ground')))
            choose(page,'floor','all')
            assert page.evaluate('[...viewer.roots.values()].filter(r=>r.visible).length')==before
        if page.evaluate('viewer.data.exporterVersion >= 10'):
            check_dense_lighting(browser,args.url)
            assert page.evaluate("""async () => {
              const {buildLightGrid,packLightGrid}=await import('/light_grid.js');
              const lights=Array.from({length:300},(_,i)=>({location:[-30,20,0],radius:128,role:i%2?'area':'static'}));
              const grid=buildLightGrid(lights), packed=packLightGrid(grid), filtered=packLightGrid(grid,l=>l.role!=='area');
              return grid.deepest===300 && packed.deepest===300 && filtered.deepest===150
                && grid.lists.every((list,c)=>list.every((id,n)=>packed.indices[packed.cells[c*4]+n]===id));
            }""")
            check_light_grid(page)
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
            check_arrow_pan(page)
            check_play_area(page)
            check_interior_whole(page)
            if page.evaluate('Boolean(viewer.data.tileGrid)'):
                check_tile_grid(page)
                choose(page,'scenery','interior');page.locator('#frame').click()
            check_option(page,'wire',True)
            if page.evaluate('viewer.data.buildings.length > 0'):
                choose(page,'floor','1');choose(page,'floor','all')
            assert page.evaluate("""() => [...viewer.roots.values()].every(root=>{
              let ok=true;root.traverse(p=>{if(p.isMesh && p.userData.baseMaterial)ok &&= p.material.wireframe;});return ok;
            })""")
            check_option(page,'wire',False)
            if page.evaluate('viewer.data.exporterVersion >= 11'):
                check_tile_footprints(page)
                assert value(page,'scenery')=='interior'
                # cut at the sides and by the height, but a piece reaching into the area drawn whole (by the height only)
                assert page.evaluate("[...viewer.roots.values()].filter(r=>r.visible).every(r=>r.userData.clippingPlanes.length>=(r.userData.interiorWhole?2:6))")
                choose(page,'scenery','full')
            if is_temple:
                appearance=page.evaluate("""() => {
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
        page.wait_for_timeout(500)
        args.screenshot.parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(args.screenshot))
        report = page.evaluate("""() => ({status:document.querySelector('#status').textContent,
          objects:viewer.roots.size, calls:viewer.renderer.info.render.calls,
          triangles:viewer.renderer.info.render.triangles})""")
        previews=[]
        # patch previews have no menu any more: they open by address (?scene=preview-<n>.json)
        assert page.locator('#scene').count() == 0 and page.locator('#building').count() == 0
        options=page.evaluate("""fetch('/cache/'+encodeURIComponent(viewer.mapId)+'/scenes.json').then(r=>r.json())
          .then(s=>s.map(x=>x.url).filter(v=>v.startsWith('preview-')))""")
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
            page.wait_for_timeout(300)
            page.screenshot(path=str(args.screenshot.with_stem(args.screenshot.stem+'-'+option.removesuffix('.json'))))
            previews.append(page.evaluate("({name:viewer.data.name,pieces:[...viewer.roots.values()].filter(r=>r.visible).length,notes:viewer.data.preview.notes.length})"))
        report['previews']=previews
        errors-=EXPECTED
        result=dict(**report,initialView=initial_view,interiorPieces=interior_count,errors=sorted(errors),screenshot=str(args.screenshot))
        args.screenshot.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf8',newline='\n')
        print(json.dumps(result,indent=2))
        browser.close()
    if errors: raise SystemExit(1)


if __name__ == "__main__": main()
