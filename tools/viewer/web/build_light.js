// The project's last baked Build's own light on the page (game-likeness plan, stage B4, its second half). A baked
// Build relights the map; its manifest names the built actor each project piece became and keeps the project as
// built, and the server exports its lightmaps into the cache (tools/viewer/build_light.py, GET
// /projects/<id>/build-light.json). Here, once the Game look has been on and the open project's last package is such
// a Build of this map:
// - its light is asked for once (and again for a newer Build) and handed to baked_light.js (setBuild), which packs its
//   atlases with the map's;
// - after each edit (plan, which app.js's refreshBaked hands to baked_light.js's refresh) each piece that is as built
//   (build_light_rules.js: its record now the one it had as built) is lit by the Build's lightmaps: one of the map's
//   by its own component (the Build's record where it relit it), a moved original or an added piece by the component
//   the Build made for it. A piece changed since is lit live, and so are the pieces a light changed since reaches (its
//   bake's pieces for one of the map's, and those its sphere meets now and as built), which lighting.js then draws
//   live (lightsSinceBuild). A made piece (drawn whole from its numbers, where the Build may have cut it into parts)
//   and a cover block (not drawn in the game) stay live;
// - View options says so under the look: the Build's time and how many pieces changed since.
// Without such a Build, the map's lightmaps light the map's pieces and every edited one is lit live (plan's `built`
// null: B4's first half).
import { buildWords, builtComponent, changedSince, lightPlace, movedAsBuilt, recordsByKey } from './build_light_rules.js';
import { data, lastBuild, lightRoots, lightsSinceBuild, project, roots, setLightsDirty, setLightsSinceBuild } from './editor_state.js';
import { isStream } from './piece_records.js';
import { api as projectApi, memberKey } from './project.js';
import { savedWhen } from './project_files.js';

export function createBuildLight({ $, bakedLight, editState, reachedPieces, refresh, relitPieces }) {
  // the scene's baked light the Build's light was handed to; the Build's light in use (the server's answer); the
  // Build being asked for, and the last one whose asking failed (not asked again); how many pieces changed since
  let scene = null, light = null, asking = null, failed = null, changed = 0;

  const keyOf = o => memberKey(o.added ? { added: o.actor } : { package: o.sourcePackage, level: o.layer, actor: o.actor });
  // the open project's last package, where it has a light of its own (builds.py: a baked Build's)
  function wanted() {
    const pkg = project && lastBuild?.project === project.doc.id ? lastBuild.package : null;
    return pkg?.light && typeof pkg.buildId === 'string' ? pkg.buildId : null;
  }
  // the Build's light asked for once the Game look has been on (the lightmaps asked for), and let go without one
  function sync(baked) {
    if (baked !== scene) { scene = baked; light = null; asking = null; }
    const id = baked?.asked() ? wanted() : null;
    if (!id) {
      if (light) { light = null; void baked?.setBuild(null).then(() => refresh()); }
      return;
    }
    if (light?.buildId === id || asking === id || failed === id) return;
    asking = id;
    projectApi.buildLight(project.doc.id).then(answer => {
      if (asking !== id) return;
      asking = null;
      if (answer.buildId !== id || wanted() !== id || bakedLight() !== baked
          || String(answer.map ?? '').toLowerCase() !== String(data?.name ?? '').toLowerCase()) return;
      light = answer;
      return baked.setBuild(answer).then(() => refresh());
    }, error => {
      if (asking === id) { asking = null; failed = id; }
      console.warn(`The last Build's own light was not read: ${error.message}`);
    });
  }

  // the place a light stands at now, in game units, with its reach
  const placeNow = root => ({ location: [root.matrix.elements[12], root.matrix.elements[14], root.matrix.elements[13]],
                              radius: root.userData.values?.radius ?? 0 });
  /** What lights each piece now, for baked_light.js's refresh: { live: the ids lit live, built: null without a Build's
   *  light in use, else id -> the built component whose record lights it (null: its own, where the map has it) }. */
  function plan() {
    const baked = bakedLight();
    sync(baked);
    if (!light || baked !== scene) { since(null); changed = 0; show(); return { live: relitPieces(), built: null }; }
    const now = editState(), records = recordsByKey(light.project), differ = changedSince(now, light.project);
    const live = new Set(), built = new Map(), pieceKeys = new Set();
    for (const root of roots.values()) {
      const o = root.userData.source;
      if (!o || isStream(o) || o.layer === 'inherited') continue;
      const key = keyOf(o);
      pieceKeys.add(key);
      if (differ.has(key)) { live.add(o.id); continue; }
      if (o.added) {
        // (a made piece is drawn whole from its numbers, a cover block not at all in the game: both stay live)
        const component = o.cover || o.added.generated ? null : builtComponent(light.actors, { actor: o.actor, component: o.component, copied: true });
        if (component && light.pieces[component]) built.set(o.id, component);
        continue;
      }
      const record = records.get(key);
      if (record?.deleted) continue;
      if (!movedAsBuilt(record)) { built.set(o.id, null); continue; }
      const component = builtComponent(light.actors, { actor: o.actor, component: o.component, copied: true });
      if (component && light.pieces[component]) built.set(o.id, component); else live.add(o.id);
    }
    // the lights changed since: their pieces lit live, and the lights drawn live on the pieces as built
    const exported = new Map((data.lights ?? []).map(l => [l.actor, l]));
    const lightKeys = new Map();
    for (const root of lightRoots.values()) if (!isStream(root.userData.source)) lightKeys.set(keyOf(root.userData.source), root);
    const isLight = r => Boolean(r && (r.light || ['spot', 'point'].includes(r.template?.kind) || exported.has(r.target?.actor) || exported.has(r.from?.actor)));
    const moved = new Set();
    for (const key of differ) {
      const root = lightKeys.get(key), record = records.get(key);
      if (!root && !isLight(record)) continue;
      const reached = [];
      if (root) {
        moved.add(root.userData.source.id);
        for (const id of root.userData.source.bakedInto ?? []) live.add(id);
        reached.push(placeNow(root));
      }
      reached.push(lightPlace(record, exported.get(record?.target?.actor ?? record?.from?.actor)));
      for (const place of reached) if (place?.radius > 0) for (const id of reachedPieces(place.location, place.radius)) live.add(id);
    }
    for (const id of live) built.delete(id);
    since(moved);
    for (const [key, record] of records) if (key.startsWith('added|') && (record.components || record.cover)) pieceKeys.add(key);
    changed = [...differ].filter(key => pieceKeys.has(key)).length;
    show();
    return { live, built };
  }
  // the lights changed since the Build, for lighting.js (lights_wiring.js's records): the lights synced again on a change
  function since(next) {
    const same = next === lightsSinceBuild || (next && lightsSinceBuild && next.size === lightsSinceBuild.size
                                                && [...next].every(id => lightsSinceBuild.has(id)));
    if (same) return;
    setLightsSinceBuild(next);
    setLightsDirty(true);
  }
  /** View options' line under the look: the Build's light in use, in the Game look. */
  function show() {
    const line = $('buildLight');
    if (!line) return;
    const on = Boolean(light) && $('lighting').value === 'game';
    line.hidden = !on;
    if (!on) return;
    const words = buildWords(savedWhen(light.builtAt), changed);
    line.textContent = words.text;
    line.title = words.title;
  }
  /** What the checks read: the Build's light in use, and how many pieces changed since. */
  const state = () => ({ build: light?.buildId ?? null, asking, failed, changed });
  return { plan, show, state };
}
