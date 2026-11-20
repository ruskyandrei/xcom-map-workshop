"""Editing in the page, in the browser (the whole-editor review of 20 November 2026), on a test server: run through
browser_smoke.py --only <name> on a server started with --projects and --builds in scratch folders (the prefab check
saves a prefab in the prefabs folder beside the projects), never the main one. Any map with one of its own fracturing
pieces will do (the pieces made here use it as their donor).

- made-prefab (finding 6): made pieces (a wall with an opening and a blast, a floor with a hole, a ramp, a rock with
  moved points) and a broken copy of a map's fracturing piece, put in a prefab from a selection, saved, read back and
  placed again, keep their numbers, blasts and flags; the placing preview draws the made pieces' own meshes; the
  prefab builder opens the prefab with them as they are, unchanged."""
import json
import math

WALL = dict(kind='fracWall', version=4, wall=dict(x0=0, x1=288, openings=[dict(x0=96, x1=192, z0=-16, z1=208)], seed=3),
            blasts=[dict(at=[48, 0, 96], radius=96)], breaksFurther=True)
FLOOR = dict(kind='fracSlab', version=3, slab=dict(x0=0, x1=192, y0=0, y1=288, holes=[dict(x0=96, x1=192, y0=96, y1=192)], seed=1))
RAMP = dict(kind='ground', version=3, ground=dict(shape='ramp', x0=0, x1=192, y0=0, y1=96, height=64))
# (a rock with moved points: ground.js ROCK, 24 points, the first 7 its ring on the ground)
ROCK_POINTS = [[round(96 + r * math.cos(k * 0.9), 1), round(96 + r * math.sin(k * 0.9), 1), z]
               for k, (r, z) in enumerate([(80, 0)] * 7 + [(50, 48 + 16 * (k % 3)) for k in range(17)])]
ROCK = dict(kind='ground', version=4, ground=dict(shape='rock', x0=0, x1=192, y0=0, y1=192, height=96, seed=5, points=ROCK_POINTS))
BLASTS = [dict(at=[10, 20, 30], radius=96), dict(at=[-5, 0, 64], radius=48)]

# the donor (one of the map's own fracturing pieces) and the pieces made of it, pasted four tiles along y
FIXTURE = """async ([made, blasts, along]) => {
  const T = await import('/vendor/three/three.module.js');
  const frac = [...viewer.roots.values()].find(r => !r.userData.source.added && !r.userData.deleted && r.visible
    && ['XComFracLevelActor', 'XComDecoFracLevelActor'].includes(r.userData.source.actorClass)
    && viewer.data.meshes[r.userData.source.mesh]?.sections?.some(s => s.fragments?.length));
  if (!frac) return null;
  const entry = state => ({ source: frac.userData.source, matrix: frac.matrix.clone(),
                            state: { tinted: false, flags: null, generated: null, blasts: null, breaksFurther: false, ...state } });
  const entries = [...made.map((generated, k) => entry({ generated, flags: k ? null : { cover: false } })),
                   entry({ blasts, breaksFurther: true, flags: { walking: false } })];
  await viewer.pasteSnapshot({ entries, pivotIndex: 0, name: 'made pieces' }, new T.Matrix4().makeTranslation(0, 0, along));
  return viewer.gizmo.picks().ids;
}"""
# each picked piece's record as the project keeps it, by kind (the made kind, or 'broken')
RECORDS = """ids => { const actors = new Set(ids.map(id => viewer.roots.get(id)?.userData.source.actor));
  return viewer.editState().added.filter(e => actors.has(e.actor)).map(e => ({ kind: e.generated?.kind ?? 'broken', ground: e.generated?.ground?.shape ?? null,
    generated: e.generated ?? null, flags: e.flags ?? null, blasts: e.blasts ?? null, breaksFurther: e.breaksFurther ?? null }))
    .sort((a, b) => `${a.kind}${a.ground}`.localeCompare(`${b.kind}${b.ground}`)); }"""
# the size of what some roots draw, or of the placing preview's ghost
SIZE = """async ids => { const T = await import('/vendor/three/three.module.js'), box = new T.Box3();
  const objects = ids ? ids.map(id => viewer.roots.get(id)) : [viewer.placing().ghost];
  for (const o of objects) { o.updateMatrixWorld(true); box.expandByObject(o); }
  return box.getSize(new T.Vector3()).toArray().map(v => Math.round(v)); }"""


def check_made_prefab(browser, url, open_viewer):
    errors = []
    page = open_viewer(browser, url, errors)
    ids = page.evaluate(FIXTURE, [[WALL, FLOOR, RAMP, ROCK], BLASTS, 384])
    assert ids, 'this map has no fracturing piece of its own to make pieces of'
    # (the paste has made their meshes when it returns: pasteSnapshot awaits them)
    before = page.evaluate(RECORDS, ids)
    assert [r['kind'] for r in before] == ['broken', 'fracSlab', 'fracWall', 'ground', 'ground'], before
    made = {r['kind'] + (r['ground'] or ''): r for r in before}
    assert made['fracWall']['generated'] == WALL and made['fracWall']['flags'] == dict(cover=False), made['fracWall']
    assert made['broken']['blasts'] == BLASTS and made['broken']['breaksFurther'] is True, made['broken']
    # the selection's prefab records carry them: nothing is left out
    page.evaluate('ids => viewer.gizmo.setSelection(ids, ids[0])', ids)
    records = page.evaluate("""() => { const r = viewer.prefabRecords(); return { pieces: r.pieces, left: r.left }; }""")
    assert records['left'] == [], records['left']
    what = lambda g, b, f, fl: json.dumps([g, b, f, fl], sort_keys=True)      # noqa: E731 (what a piece is, comparable)
    kept = sorted(what(p.get('generated'), p.get('blasts'), p.get('breaksFurther'), p.get('flags')) for p in records['pieces'] if p.get('from'))
    assert kept == sorted(what(r['generated'], r['blasts'], r['breaksFurther'], r['flags']) for r in before), kept
    # saved (schema 4), read back and placed again: each piece is what it was
    saved = page.evaluate("async () => viewer.savePrefab('Made pieces check')")
    doc = page.evaluate('id => viewer.prefabApi.load(id)', saved['id'])
    assert doc['schemaVersion'] == 4, doc['schemaVersion']
    again = page.evaluate("""async ([id, along]) => {
      const T = await import('/vendor/three/three.module.js'), doc = await viewer.prefabApi.load(id), clip = await viewer.prefabClip(doc);
      if (clip.left.length) return { left: clip.left };
      await viewer.pasteSnapshot(clip, new T.Matrix4().makeTranslation(0, 0, along));
      return { ids: viewer.gizmo.picks().ids };
    }""", [saved['id'], 1152])
    assert 'ids' in again, again
    placed = [i for i in again['ids'] if page.evaluate('id => Boolean(viewer.roots.get(id))', i)]
    after = page.evaluate(RECORDS, placed)
    assert after == before, (after, before)
    # the placing preview draws the made pieces as they will stand: the size of what the paste made
    page.evaluate("async id => { const p = (await viewer.prefabApi.list()).prefabs.find(x => x.id === id); await viewer.choosePrefab(p); }", saved['id'])
    page.wait_for_function('Boolean(viewer.placing())', timeout=60000)
    ghost, drawn = page.evaluate(SIZE, None), page.evaluate(SIZE, placed)
    assert all(abs(a - b) <= 2 for a, b in zip(ghost, drawn)), (ghost, drawn)
    page.keyboard.press('Escape')
    # the prefab builder opens it with them as they are, and nothing changed
    builder = open_viewer(browser, url.split('?')[0] + f"?prefab={saved['id']}", errors)
    builder.wait_for_function('viewer.builderMode && viewer.builderDocument().pieces.length > 0', timeout=120000)
    pieces = builder.evaluate('viewer.builderDocument().pieces')
    assert sorted(what(p.get('generated'), p.get('blasts'), p.get('breaksFurther'), p.get('flags')) for p in pieces) == kept, pieces
    assert builder.evaluate('viewer.dirty()') is False
    builder.close()
    page.evaluate('id => viewer.prefabApi.remove(id)', saved['id'])
    page.close()
    assert not errors, errors
    return dict(map=url, pieces=len(before), ghost=ghost)
