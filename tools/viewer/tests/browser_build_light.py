"""A baked Build's own light in the browser (game-likeness plan, B4, its second half), on a test server: run through
browser_smoke.py --only build-light --projects (it saves a project: a server started with --projects and --builds in
scratch folders, never the main one), on a map of export 45 with lightmaps (URB_Bar).

A lightmapped piece of the map is copied and placed, and the project saved. A made-up Build of it then stands in for
the server's (the page's routes answered here, as builds.py and build_light.py answer them): its package says it has
a light of its own, and its light names the added piece's built actor, the project as built, and the added piece's
built component with a lightmap in an atlas of its own (the map's own atlas file under a name of the Build's). Opened
again on the project, in the Game look: the Build's light is asked for and packed in; the added piece is lit by its
record (its parts marked 5 to 7), the map's pieces as built by theirs (5 to 7); View options says the Build's time and
that nothing changed since. The added piece moved is lit live (4), one piece changed since, and back after Undo. A
static light's brightness changed lights the pieces its bake lists live and is drawn live on the pieces as built
(its record's sinceBuild), until Undo. The Neutral look hides the line. No error on the page."""

PL = 'TheWorld.PersistentLevel.'
BUILD_ID = 'BuildLightSmoke-20261127-120000-0a1b2c3d'
MARK = "id => viewer.roots.get(id).userData.parts[0].geometry.attributes.bakedScale0.getW(0)"


def check_build_light(browser, url, open_viewer, type_project_name, choose, skip, run):
    errors = []
    page = open_viewer(browser, url, errors)
    if not page.evaluate('viewer.data.objects.some(o => o.lightmap)'):
        return skip('build-light', 'the map\'s export has no lightmaps', page, whole=True)
    # a lightmapped piece of the map with one component, standing alone (not of an assembly), copied and placed
    template = page.evaluate("""() => {
      const roots = [...viewer.roots.values()], by = new Map();
      for (const r of roots) by.set(r.userData.source.actor, (by.get(r.userData.source.actor) ?? 0) + 1);
      const r = roots.find(r => { const o = r.userData.source; return o.lightmap && !o.hidden && !o.added && o.layer === 'base'
        && o.actorClass === 'StaticMeshActor' && by.get(o.actor) === 1 && r.userData.parts?.length && !o.partner && !o.prefab; });
      return r ? r.userData.source.id : null; }""")
    assert template, 'no lightmapped static mesh actor of one component on this map'
    page.evaluate('id => viewer.select(id)', template)
    count = page.evaluate('viewer.roots.size')
    box = page.locator('#viewport > canvas').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.keyboard.press('Control+c'); page.mouse.move(cx, cy); page.keyboard.press('Control+v')
    page.wait_for_function('viewer.placing()?.ghost.visible'); page.mouse.click(cx, cy)
    page.wait_for_function('n => viewer.roots.size === n + 1', arg=count)
    page.keyboard.press('Control+s')
    page.wait_for_selector('#fileDialog:not([hidden])')
    type_project_name(page, f'Build light smoke {run}')
    page.locator('#fileName').press('Enter')
    page.wait_for_function('viewer.project()?.revision === 1')
    project = page.evaluate('viewer.project().id')
    doc = page.evaluate("id => fetch(`/projects/${id}/project.json`).then(r => r.json())", project)
    added, = doc['added']
    built_actor = PL + 'StaticMeshActor_9001'
    component = built_actor + '.' + added['components'][0].split('.')[-1]
    # the template's lightmap, its atlases as the Build's own (the map's files, under names of the Build's)
    lightmap, textures = page.evaluate("""id => { const o = viewer.roots.get(id).userData.source, t = viewer.data.textures;
      return [o.lightmap, { colour: t[o.lightmap.colour], directions: t[o.lightmap.directions] }]; }""", template)
    light = dict(buildId=BUILD_ID, builtAt='2026-11-27T12:00:00', revision=1, map=page.evaluate('viewer.data.name'),
                 actors={added['actor']: built_actor}, project=doc,
                 pieces={component: dict(lightmap=dict(lightmap, colour='build-901', directions='build-902'), sunIrrelevant=True)},
                 textures={'build-901': dict(textures['colour'], name='BuildLightSmokeColour'),
                           'build-902': dict(textures['directions'], name='BuildLightSmokeDirections')},
                 base='/cache/%s/' % page.evaluate('encodeURIComponent(viewer.mapId)'))
    asked = dict(light=0)

    def status(route):
        body = dict(state='idle', job=None, busy=False, output='', package=dict(
            folder='', buildId=BUILD_ID, builtAt=light['builtAt'], seconds=60, quick=False, times=dict(full=60),
            foreignPieces=0, foreignEffects=0, donors=[], revision=1, files=[], light=True))
        route.fulfill(json=body)

    def answer(route):
        asked['light'] += 1
        route.fulfill(json=light)
    page.route('**/projects/*/build.json', status)
    page.route('**/projects/*/build-light.json', answer)
    page.reload()
    page.wait_for_function("id => window.viewer && document.querySelector('#loading').hidden && viewer.project()?.id === id",
                           arg=project, timeout=120000)
    # nothing asked for before the Game look is on
    assert asked['light'] == 0, asked
    choose(page, 'lighting', 'game')
    page.wait_for_function('id => viewer.post.baked()?.build?.id === id && viewer.post.buildLight().build === id && viewer.post.baked().on',
                           arg=BUILD_ID, timeout=120000)
    page.wait_for_function("viewer.post.baked().build.own >= 1")
    copy = page.evaluate("() => [...viewer.roots.values()].find(r => r.userData.source.added).userData.source.id")
    baked = page.evaluate('viewer.post.baked()')
    assert 5 <= page.evaluate(MARK, copy) <= 7, (page.evaluate(MARK, copy), baked)
    assert 5 <= page.evaluate(MARK, template) <= 7, page.evaluate(MARK, template)
    assert baked['build']['records'] == 1 and baked['build']['lit'] > 100 and baked['live'] == 0, baked
    line = page.locator('#buildLight')
    assert line.is_visible() and line.inner_text().endswith('nothing changed since'), line.inner_text()
    assert 'Lit by the Build of' in line.inner_text()
    # the copy moved: lit live, one piece changed since; back on the Build's light after Undo
    page.evaluate('id => viewer.select(id)', copy)
    start = page.evaluate('viewer.gizmo.pose()')
    page.locator('#posX').fill(f"{start['location'][0] + 48:.2f}"); page.locator('#posX').press('Enter')
    page.wait_for_function('id => viewer.post.buildLight().changed === 1', arg=copy)
    assert page.evaluate(MARK, copy) == 4 and page.evaluate('viewer.post.baked().live') == 1, page.evaluate('viewer.post.baked()')
    assert line.inner_text().endswith('1 piece changed since'), line.inner_text()
    page.keyboard.press('Control+z')
    page.wait_for_function('viewer.post.buildLight().changed === 0')
    assert 5 <= page.evaluate(MARK, copy) <= 7 and page.evaluate('viewer.post.baked().live') == 0
    # a static light changed since: the pieces its bake lists lit live, and it drawn live on the pieces as built
    lamp = page.evaluate("(viewer.data.lights.find(l => l.role === 'static' && l.bakedInto?.length && l.enabled) || {}).id")
    if lamp:
        page.evaluate('id => viewer.select(id)', lamp)
        page.locator('#lightBrightness').fill('7.5'); page.locator('#lightBrightness').press('Enter')
        page.wait_for_function('viewer.post.baked().live > 0')
        assert page.evaluate("id => viewer.lightRecords().find(l => l.id === id).sinceBuild", lamp)
        listed = page.evaluate("id => viewer.data.lights.find(l => l.id === id).bakedInto.filter(k => viewer.roots.get(k)?.userData.source.lightmap)", lamp)
        assert all(page.evaluate(MARK, k) == 4 for k in listed[:5]), listed[:5]
        page.keyboard.press('Control+z')
        page.wait_for_function('viewer.post.baked().live === 0')
        assert not page.evaluate("id => viewer.lightRecords().find(l => l.id === id).sinceBuild", lamp)
    page.evaluate('viewer.select(null)')
    # a frame drawn with the Build's marks; the Neutral look hides the line
    page.evaluate('viewer.post.draw(true)')
    choose(page, 'lighting', 'neutral')
    assert line.is_hidden()
    assert asked['light'] == 1, asked
    page.unroute('**/projects/*/build.json', status)
    page.unroute('**/projects/*/build-light.json', answer)
    assert not errors, errors
    page.close()
    return dict(lit=baked['build']['lit'], live=baked['live'])
