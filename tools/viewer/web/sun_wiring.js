// The time of day in the view (the game-likeness plan, T-S1): the project's `sun` (schema 10) as the view draws it, the
// one place a change of it is made, and its marker in the view.
// - The curve (/sun-curve.json, asked once) made the map's own as a map opens (sun_rules.js mapCurve: the map's own
//   light stands at its best time), and what the view draws for the record now (viewSun, which lighting.js reads).
// - A change: a drag of the Map settings window's time bar or dial (sun_settings.js) or of the marker is previewed
//   (previewSun: the record and the fog and colour of the hour set at once, the view following) and kept as one undo
//   step when it ends (endSunEdit); a change made at once (More's fields, As the map has it) is one step (commitSun).
// - Each frame (stepSun, from the draw loop): a new record lights the view again (lighting.js sunMoved) and asks for
//   the sun's shadows (touchShadows), so they are drawn again every frame while the bar is dragged and not after; the
//   marker drawn where the light is.
// - The marker (sun_view.js): the sun or moon on its arc over the map, shown in the Lights view and while the Map
//   settings window is open; dragged along its arc it sets the time, a second handle on the bar's value.
// - The sky (stage T-S6; stepDome, each frame): the record's dome, a sky dome of another of the game's maps, drawn in
//   the Game look where each of the map's own domes stands (those drawn no longer), as the Build makes it.
//
// createSunWiring takes what it needs of app.js as one argument object when app.js makes it (before the Map settings
// window, which is given its functions); its window keydown listener (Escape puts a drag of the marker back) is added
// then. Its state is inside it.
import { ask } from './api.js';
import { text } from './dom_words.js';
import { data, lighting, lightRadius, lightsOn, projectAtmosphere, projectSun, roots, setProjectAtmosphere,
         setProjectSun } from './editor_state.js';
import { HANDLE_PICK, gameToView } from './handles.js';
import { bestTime, clock, curveAt, DAY, directionOf, domeKey, isOwnDome, mapCurve, ownSun, phaseAt, shownTime, sideAt,
         spanAt, sunView, timeSet, validSun } from './sun_rules.js';
import { createSunMarker } from './sun_view.js';

const RAD = Math.PI / 180;

export function createSunWiring({ $, buildRoot, camera, cutaway, gizmo, libraryTemplate, projector, renderer, restingHint,
                                  sun, touchShadows, world, sunChanged = () => {} }) {
  let curve = null, curveWhy = null, mine = null, own = null;
  let viewKey, viewValue = null, drawnView, markerKey = '';
  let editFrom = null, drag = null, hover = false, windowOpen = false;
  // the sky chosen as the view draws it (stepDome): its key, the copies of its dome drawn where the map's own stand,
  // why it could not be drawn
  let domeDrawn = '', domeRoots = [], domeWhy = null;
  const marker = createSunMarker(world);

  async function loadCurve() {
    if (curve || curveWhy) return curve;
    curve = await ask('/sun-curve.json');
    curveWhy = curve ? null : 'the editor\'s server did not give the time of day\'s curve';
    return curve;
  }
  // As a map opens (app.js's startScene, after its lights are built): the map's own light, and the curve made its own
  async function startSun() {
    own = null; mine = null; viewKey = undefined; drawnView = undefined; markerKey = ''; editFrom = null;
    // (the last map's dome copies were in its scene: let go of them)
    for (const root of domeRoots) world.remove(root);
    domeRoots = []; domeDrawn = ''; domeWhy = null;
    if (drag) endSunDrag(false);
    if (data?.scope !== 'map' || data.preview) return;
    own = ownSun(data);
    if (own && await loadCurve()) mine = mapCurve(curve, own, bestTime(curve, own));
  }
  /** The time of day as the view draws it: sun_rules.js sunView of the project's record, or null for the map's own (one
   *  object while the record stays). */
  function viewSun() {
    if (viewKey !== projectSun) {
      viewKey = projectSun;
      viewValue = own && validSun(projectSun, curve) ? sunView(projectSun) : null;
    }
    return viewValue;
  }

  // ------------------------------------------------------------------------------------------------ changes
  const state = () => ({ sun: projectSun, atmosphere: projectAtmosphere });
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function put(s) { setProjectSun(s.sun); setProjectAtmosphere(s.atmosphere); sunChanged(); }
  /** A drag begins (the bar, the dial, the marker): the record and the fog and colour now, to undo to. */
  function beginSunEdit() { editFrom ??= state(); }
  /** While a drag lasts: the bar's time and the dial's heading set, judged against the record as the drag began. */
  function previewSun({ time, heading }) {
    if (!mine) return;
    beginSunEdit();
    const next = timeSet({ curve: mine, own, before: editFrom.sun, atmosphere: editFrom.atmosphere, time, heading });
    put({ sun: next.sun, atmosphere: next.atmosphere });
  }
  /** While a value set by hand moves (More's colours and strengths): the record set as it is, kept by endSunEdit. */
  function previewSunRecord(next) {
    beginSunEdit();
    put({ sun: next, atmosphere: projectAtmosphere });
  }
  /** The drag's end: kept as one undo step (`keep`), or put back. */
  function endSunEdit(keep = true) {
    if (!editFrom) return;
    const before = editFrom, after = state();
    editFrom = null;
    put(before);
    if (keep && !same(before, after)) gizmo.record({ redo: () => put(after), undo: () => put(before) });
  }
  /** A change made at once: one undo step from the record now to `next` ({ sun, atmosphere }). */
  function commitSun(next) {
    const before = state();
    if (same(before, next)) return;
    gizmo.record({ redo: () => put(next), undo: () => put(before) });
  }
  /** What the bar and the dial show now: { time, heading }, or null where the map has no sun or moon. */
  const sunShown = () => (mine ? shownTime(projectSun, own, mine) : null);

  // ------------------------------------------------------------------------------------------------ the marker
  // A point of the light's path in the view: its side and height at time t, `radius` from the map's middle
  function pathPoint(t, heading, radius) {
    const side = sideAt(mine, t, heading) * RAD, h = curveAt(mine, t).height * RAD;
    const to = [Math.cos(h) * Math.cos(side), Math.cos(h) * Math.sin(side), Math.sin(h)];
    return gameToView(to).multiplyScalar(radius).add(sun.target.position);
  }
  const markerRadius = () => lightRadius * 0.9;
  function placeMarker() {
    const at = sunShown(), record = validSun(projectSun, curve) ? projectSun : null;
    const key = `${at.time}|${at.heading}|${record?.light?.rotation}|${record?.light?.color}|${sun.target.position.toArray()}|${lightRadius}|${hover || drag ? 1 : 0}`;
    if (key !== markerKey) {
      markerKey = key;
      // (each light's arc from its coming up to its going down, the moon's across midnight)
      const radius = markerRadius(), points = light => {
        const span = spanAt(mine, mine.changes.find(c => c.light === light).time), out = [];
        for (let t = span.start; t <= span.end - 1 / 60; t += 1 / 6) out.push(pathPoint(t % DAY, at.heading, radius));
        out.push(pathPoint((span.end - 1 / 60) % DAY, at.heading, radius));
        return out;
      };
      // (the marker where the light shines from: the record's rotation, or the map's own light)
      const from = record ? directionOf(record.light.rotation).map(v => -v)
        : [Math.cos(own.height * RAD) * Math.cos(own.side * RAD), Math.cos(own.height * RAD) * Math.sin(own.side * RAD), Math.sin(own.height * RAD)];
      marker.draw({ sunPoints: points('sun'), moonPoints: points('moon'), at: gameToView(from).multiplyScalar(radius).add(sun.target.position),
                    middle: sun.target.position.clone(), moon: phaseAt(mine, at.time).light === 'moon', lit: hover || Boolean(drag),
                    colour: (record?.light?.color ?? own.color).map(v => v / 255) });
    }
    return marker.scale(camera);
  }
  /** The marker shown: a map with a sun or moon, in the Lights view or while the Map settings window is open. */
  const markerShown = () => Boolean(mine) && (lightsOn || windowOpen);
  /** The Map settings window opened or closed (map_settings.js). */
  function setSunWindow(open) { windowOpen = open; }

  // ------------------------------------------------------------------------------------------------ the sky
  // The sky chosen (the record's dome, stage T-S6) drawn in the Game look in place of the map's own domes, as the Build
  // makes it: a copy of the chosen dome (another map's piece, read as library_templates.js reads any: its sky material
  // drawn at the far plane, scene_pieces.js) where each of the map's own stands, at its turn and in its size: both are
  // the game's one sky dome mesh, so the copy takes the replaced dome's own matrix. (The Build's copy keeps the chosen
  // dome's size, F-202: in the game the turned-over one under the map then lies in the fog, the colour of all below the
  // horizon, while the view, which draws the sky with no fog, would show it as a second sky under the map.) The copies
  // are drawn things of the view (never picked, in no project's records); the map's own domes are drawn no longer while
  // they stand (the cutaway reads userData.skyReplaced).
  const ownDomeRoots = () => [...roots.values()].filter(r => isOwnDome(r.userData.source, data?.meshes));
  function placeDome(key) {
    for (const root of domeRoots) world.remove(root);
    domeRoots = []; domeWhy = null;
    for (const root of ownDomeRoots()) root.userData.skyReplaced = false;
    if (!key) { cutaway(); return; }
    const [map, actor] = key.split('|');
    libraryTemplate({ package: map, level: 'base', actor }).then(async template => {
      if (key !== domeDrawn) return;        // (another sky chosen meanwhile)
      const source = template.sources[0], made = [];
      for (const [k, owned] of ownDomeRoots().entries()) {
        const at = owned.userData.source;
        const root = await buildRoot({ ...source, id: `sky:${k}`, location: at.location, rotation: at.rotation, matrix: [...at.matrix] });
        made.push([root, owned]);
      }
      if (key !== domeDrawn) return;
      for (const [root, owned] of made) {
        root.visible = $('lighting').value === 'game';
        world.add(root); domeRoots.push(root); owned.userData.skyReplaced = true;
      }
      cutaway();
    }).catch(error => { if (key === domeDrawn) domeWhy = `the sky ${actor} of ${map} could not be read (${error.message})`; });
  }
  /** Each frame: the sky drawn as the record has it now, its copies shown in the Game look alone (as the map's own). */
  function stepDome() {
    const record = own && validSun(projectSun, curve) ? projectSun : null;
    const key = domeKey(record?.dome);
    if (key !== domeDrawn) { domeDrawn = key; placeDome(key); }
    const shown = $('lighting').value === 'game';
    for (const root of domeRoots) root.visible = shown;
  }

  /** Each frame (the draw loop): the view lit again for a new record, the sun's shadows asked for; the marker drawn. */
  function stepSun() {
    const view = viewSun();
    if (view !== drawnView) {
      drawnView = view;
      lighting?.sunMoved?.(sun.target.position, lightRadius);
      touchShadows();
    }
    stepDome();
    marker.group.visible = markerShown();
    if (marker.group.visible) placeMarker();
  }

  // Whether a screen point is on the marker
  function onMarker(x, y) {
    if (!marker.group.visible) return false;
    const project = projector(), s = project(marker.marker.position);
    if (!s) return false;
    const size = marker.scale(camera), edge = project(marker.marker.position.clone().addScaledVector(camera.up, size));
    const r = edge ? Math.hypot(edge[0] - s[0], edge[1] - s[1]) : 0;
    return Math.hypot(s[0] - x, s[1] - y) <= Math.max(HANDLE_PICK, r + 4);
  }
  // The time whose place on the arcs comes nearest a screen point: every ten minutes, then to the minute around the best
  function nearestTime(x, y, heading) {
    const project = projector(), radius = markerRadius();
    const away = t => { const s = project(pathPoint(t, heading, radius)); return s ? Math.hypot(s[0] - x, s[1] - y) : Infinity; };
    let best = 0, bestD = Infinity;
    for (let m = 0; m < DAY * 60; m += 10) { const d = away(m / 60); if (d < bestD) { bestD = d; best = m; } }
    for (let m = best - 10; m <= best + 10; m++) { const t = ((m % 1440) + 1440) % 1440, d = away(t / 60); if (d < bestD) { bestD = d; best = t; } }
    return best / 60;
  }
  function dragHint(time) {
    const hint = $('dragHint');
    hint.hidden = false;
    hint.replaceChildren(`${phaseAt(mine, time).light === 'moon' ? 'The moon' : 'The sun'} at ${clock(time)}: drag along its path for the time of day · `);
    text(hint, 'kbd', 'Esc'); hint.append(' cancels the drag');
  }
  /** A press on the marker: its drag begins (true), ahead of the gizmo, the camera and picking. */
  function startSunDrag(e) {
    if (e.button !== 0 || drag || gizmo.controls.dragging || !onMarker(e.clientX, e.clientY)) return false;
    renderer.domElement.setPointerCapture(e.pointerId);
    beginSunEdit();
    drag = { pointerId: e.pointerId, heading: sunShown().heading };
    renderer.domElement.style.cursor = 'grabbing';
    dragHint(sunShown().time);
    return true;
  }
  function moveSunDrag(e) {
    const time = nearestTime(e.clientX, e.clientY, drag.heading);
    previewSun({ time, heading: drag.heading });
    dragHint(time);
  }
  /** The marker's drag ends: one undo step, or (Escape, a cancelled pointer) put back. */
  function endSunDrag(keep) {
    const d = drag;
    if (!d) return false;
    drag = null;
    try { renderer.domElement.releasePointerCapture(d.pointerId); } catch { /* already released */ }
    renderer.domElement.style.cursor = hover ? 'grab' : '';
    endSunEdit(keep);
    restingHint();
    return true;
  }
  function hoverSun(e) {
    const over = e.buttons === 0 && !gizmo.controls.dragging && onMarker(e.clientX, e.clientY);
    if (over === hover) return;
    hover = over;
    renderer.domElement.style.cursor = over ? 'grab' : '';
    renderer.domElement.title = over ? 'The sun or moon: drag it along its path for the time of day (Map settings: Sun, moon and sky)' : '';
  }
  window.addEventListener('keydown', e => {
    if (!drag || e.key !== 'Escape') return;
    e.preventDefault(); e.stopImmediatePropagation();
    endSunDrag(false);
  }, { capture: true });

  /** What the browser checks read: the record, the map's own, the marker. */
  const sunState = () => ({ record: projectSun, ready: Boolean(mine), why: curveWhy, own: own && { time: mine?.own?.time ?? null, side: own.side, height: own.height, domes: own.domes },
                            shown: sunShown(), view: viewSun(), marker: marker.group.visible ? marker.marker.position.toArray() : null,
                            dragging: Boolean(drag),
                            dome: { key: domeDrawn, drawn: domeRoots.length, shown: domeRoots.filter(r => r.visible).length,
                                    replaced: ownDomeRoots().filter(r => r.userData.skyReplaced).length,
                                    ownShown: ownDomeRoots().filter(r => r.visible).length, why: domeWhy,
                                    materials: domeRoots.map(r => data.materials[r.userData.source.materials?.[0]]?.name ?? null) } });
  return { beginSunEdit, commitSun, endSunDrag, endSunEdit, hoverSun, loadCurve, moveSunDrag, previewSun, previewSunRecord, setSunWindow,
           startSun, startSunDrag, stepSun, sunCurve: () => mine, sunDrag: () => drag, sunOwn: () => own, sunShown,
           sunState, viewSun };
}
