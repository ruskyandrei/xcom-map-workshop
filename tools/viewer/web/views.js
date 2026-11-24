// Switching the views (refactor stage P9): the views (Buildings, Lights, Landing zones, Effects, Spawns) are on one at
// a time, or none (the normal view: setNormalView). After a view or one of the Normal view's switches changed:
// whether lights are drawn, what stays selected and the panel for it (syncLights), and the views' list, the Normal
// view's switches and the Lights view's Area lights and reach outlines as they now are (lightButton). Each view's own
// switch (setLightsShown, setVolumesShown and the others) is its module's.
//
// The views' place (the user's choice of 23 November 2026, design A with design C's switches; UI-GUIDELINES.md section
// 2): one Views button on the rail, showing the icon of the view that is on, and its list, a row for each view with its
// key and, under the row of the view that is on, that view's switches. VIEWS is the one table of them: the list's on
// marks, the button's icon and words and the views' keys (viewByKey, navigation.js) come from it.
//
// createViews takes what it needs of app.js as one argument object, when app.js makes it, after the selection: the
// gizmo, the views' switches and refreshes, the Spawns view's layer and its panel (made before it: follow-up 3.24). It
// keeps no state: which view is on and the switches are editor_state.js's.
import { areaShown, boxesShown, data, diagonalOn, effectsOn, lightRoots, lightsOn, lightsShown, normalEffects, normalLights,
         normalSpawns, ownSet, pickBox, reachShown, setLightsShownValue, setOwnPickedValue, spawnsOn, volumeRoots,
         volumesOn, zonesOn } from './editor_state.js';

// The views, in the list's order: the row's id, its name, its icon, its key (with Shift), whether it is on, and the
// name of its switch among createViews' arguments (the normal view's: setNormalView).
export const VIEWS = [
  { id: 'editNormal', name: 'Normal', icon: 'i-normal', key: 'n', on: () => !volumesOn && !lightsOn && !zonesOn && !effectsOn && !spawnsOn && !diagonalOn,
    switch: null },
  { id: 'editBuildings', name: 'Buildings', icon: 'i-building', key: 'b', on: () => volumesOn, switch: 'setVolumesShown' },
  { id: 'editLights', name: 'Lights', icon: 'i-light', key: 'l', on: () => lightsOn, switch: 'setLightsShown' },
  { id: 'editZones', name: 'Landing zones', icon: 'i-zone', key: 'z', on: () => zonesOn, switch: 'setZonesShown' },
  { id: 'editEffects', name: 'Effects', icon: 'i-effect', key: 'x', on: () => effectsOn, switch: 'setEffectsShown' },
  { id: 'editSpawns', name: 'Spawns', icon: 'i-spawn', key: 'u', on: () => spawnsOn, switch: 'setSpawnsShown' },
  // (C for cover: Shift+D is the camera's fast pan right)
  { id: 'editDiagonal', name: 'Diagonal cover', icon: 'i-diag', key: 'c', on: () => diagonalOn, switch: 'setDiagonalShown' },
];

/** The words of the Views button's tooltip: the view that is on and the keys. */
export function viewsTitle(view) {
  const keys = VIEWS.map(v => v.key.toUpperCase());
  return `Views: the ${view.name} view is on. Shift+${keys.slice(0, -1).join(', ')} and ${keys.at(-1)} switch them`;
}

export function createViews({ $, gizmo, refreshLightShapes, refreshLightVisibility, refreshPickBox, refreshVolumes,
                              select, setDiagonalShown, setEffectsShown, setLightsShown, setSpawnsShown, setVolumesShown,
                              setZonesShown, spawnLayer, spawnPanel, spawnsShown }) {
  const switches = { setDiagonalShown, setEffectsShown, setLightsShown, setSpawnsShown, setVolumesShown, setZonesShown };
  // The normal view: out of the Buildings view, the Lights view, the Landing zones view and the Effects view.
  function setNormalView() {
    for (const v of VIEWS) if (v.switch && v.on()) switches[v.switch](false);
  }
  /** A view's key (with Shift) switched: the view on, or off again where it is on (the normal view's key: the normal
   *  view); false for a key no view has. */
  function viewByKey(key) {
    const v = VIEWS.find(x => x.key === key);
    if (!v) return false;
    if (data) { if (!v.switch) setNormalView(); else switches[v.switch](!v.on()); }
    return true;
  }
  // After a view or a switch changed: whether lights are drawn, what stays selected, the buttons.
  function syncLights() {
    setLightsShownValue(lightsOn || (normalLights && !volumesOn));
    if (volumesOn || lightsOn || !boxesShown) { ownSet.clear(); if (!volumesOn) setOwnPickedValue(null); }
    const picks = gizmo.picks();
    const keep = picks.ids.filter(id => (lightRoots.has(id) ? lightsShown : volumeRoots.has(id) ? volumesOn || (boxesShown && !lightsOn) : !lightsOn));
    if (keep.length !== picks.ids.length) gizmo.setSelection(keep, picks.active); else gizmo.regroup();
    refreshLightVisibility(); lightButton(); refreshLightShapes(); refreshVolumes();
    if (pickBox) refreshPickBox(true);
    if (data) select(gizmo.active, false, true);
  }
  function lightButton() {
    // (the Diagonal cover view steps aside for another view turned on, which comes here once it is: its switch turns
    // the others off itself)
    if (diagonalOn && (volumesOn || lightsOn || zonesOn || effectsOn || spawnsOn)) { setDiagonalShown(false); return; }
    for (const v of VIEWS) {
      const on = v.on();
      $(v.id).classList.toggle('on', on); $(v.id).setAttribute('aria-pressed', on);
    }
    // the Views button: the icon of the view that is on, marked on while a view other than the normal one is
    const view = VIEWS.find(v => v.on()) ?? VIEWS[0];
    $('viewsIcon').setAttribute('href', `#${view.icon}`);
    $('viewsButton').classList.toggle('on', view !== VIEWS[0]);
    $('viewsButton').title = viewsTitle(view);
    $('normalLights').checked = normalLights; $('boxesToggle').checked = boxesShown; $('normalEffects').checked = normalEffects;
    $('normalSpawns').checked = normalSpawns;
    // (the spawn markers show with the view, or with the switch in the normal view)
    spawnLayer.visible = spawnsShown(); spawnPanel();
    $('areaToggle').checked = areaShown; $('reachToggle').checked = reachShown;
    $('areaToggle').disabled = $('reachToggle').disabled = !lightsShown;
  }
  // The Views button: a click keeps its list open (pinned) until a click elsewhere, for a hand that would rather not
  // hover; the list shows while the pointer is over the button or the list as the rail's other lists do
  const fly = $('viewsFly');
  function pin(on) { fly.classList.toggle('pinned', on); $('viewsButton').setAttribute('aria-expanded', String(on)); if (on) placeList(); }
  $('viewsButton').onclick = () => pin(!fly.classList.contains('pinned'));
  // The list stands beside its button, as the Build menu stands beside Add (the user, 24 November 2026); where it would
  // run past the window's foot it is lifted, as far as the window's top. Measured as it shows (hidden, it has no size).
  function placeList() {
    const list = $('viewsFlyout');
    requestAnimationFrame(() => {
      const b = $('viewsButton').getBoundingClientRect(), h = list.getBoundingClientRect().height;
      const over = b.top - 5 + h - (window.innerHeight - 12);
      list.style.top = `${-5 - (over > 0 ? Math.min(over, Math.max(0, b.top - 17)) : 0)}px`;
    });
  }
  fly.addEventListener('pointerenter', placeList);
  window.addEventListener('resize', () => { if (fly.classList.contains('pinned')) placeList(); });
  document.addEventListener('pointerdown', e => { if (fly.classList.contains('pinned') && !fly.contains(e.target)) pin(false); });

  return { lightButton, setNormalView, syncLights, viewByKey };
}
