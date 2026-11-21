// Switching the views (refactor stage P9): the five views (Buildings, Lights, Landing zones, Effects, Spawns) are on one
// at a time, or none (the normal view: setNormalView). After a view or one of the Normal button's switches changed:
// whether lights are drawn, what stays selected and the panel for it (syncLights), and the views' buttons, the Normal
// button's switches and View options' Area lights and reach outlines as they now are (lightButton). Each view's own
// switch (setLightsShown, setVolumesShown and the others) is its module's.
//
// createViews takes what it needs of app.js as one argument object, when app.js makes it, after the selection: the
// gizmo, the views' switches and refreshes, the Spawns view's layer and panel. It keeps no state: which view is on and
// the switches are editor_state.js's.
import { areaShown, boxesShown, data, effectsOn, lightRoots, lightsOn, lightsShown, normalEffects, normalLights,
         normalSpawns, ownSet, pickBox, reachShown, setLightsShownValue, setOwnPickedValue, spawnLayerReady, spawnsOn,
         volumeRoots, volumesOn, zonesOn } from './editor_state.js';

export function createViews({ $, gizmo, refreshLightShapes, refreshLightVisibility, refreshPickBox, refreshVolumes,
                              select, setEffectsShown, setLightsShown, setSpawnsShown, setVolumesShown, setZonesShown,
                              spawnLayer, spawnPanel, spawnsShown }) {
  // The normal view: out of the Buildings view, the Lights view, the Landing zones view and the Effects view.
  function setNormalView() {
    if (volumesOn) setVolumesShown(false);
    if (lightsOn) setLightsShown(false);
    if (zonesOn) setZonesShown(false);
    if (effectsOn) setEffectsShown(false);
    if (spawnsOn) setSpawnsShown(false);
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
    for (const [id, on] of [['editNormal', !volumesOn && !lightsOn && !zonesOn && !effectsOn && !spawnsOn], ['editBuildings', volumesOn], ['editLights', lightsOn],
                            ['editZones', zonesOn], ['editEffects', effectsOn], ['editSpawns', spawnsOn]]) {
      $(id).classList.toggle('on', on); $(id).setAttribute('aria-pressed', on);
    }
    $('normalLights').checked = normalLights; $('boxesToggle').checked = boxesShown; $('normalEffects').checked = normalEffects;
    $('normalSpawns').checked = normalSpawns;
    // (the spawn markers show with the view, or with the switch in the normal view)
    if (spawnLayerReady) { spawnLayer.visible = spawnsShown(); spawnPanel(); }
    $('areaToggle').checked = areaShown; $('reachToggle').checked = reachShown;
    $('areaToggle').disabled = $('reachToggle').disabled = !lightsShown;
  }

  return { lightButton, setNormalView, syncLights };
}
