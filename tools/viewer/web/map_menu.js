// The menu of the map or the prefab that is open, and the way to another (refactor stage P9; the prefab menus plan,
// stage M2). The header's second button names what is open: Map and the map's name, or Prefab and the prefab's (a map
// and a prefab are never open together). Its menu, drawn afresh as it opens (renderMapMenu), holds:
// - what is open: the map's name and its own items (Map settings, Missions, Map picture, Map grid, Clear map: their
//   handlers are their areas', scene_start.js shows them as the scene allows), or the prefab's name, revision and its
//   items (Save, Save as, Export to a file, Find missing pieces);
// - Open: two buttons, A map… and A prefab…, each with how many there are, each opening its side of the Open window
//   (showOpen; M and, in the builder, Ctrl+O call it too);
// - New prefab.
// Here too: the server's list of maps and the map browser made from it as the page opens (map_browser.js is the
// dialog itself), a map's name in the lists (mapLabel), the list brought up to the server's after maps were prepared
// elsewhere (refreshMapList), and choosing a map opening it (makeMapBrowser, from app.js's open). The map list and the
// browser (mapCatalogue, mapBrowser) are editor_state.js's: app.js's open sets the list and shows the browser on a map
// not prepared yet.
//
// createMapMenu takes what it needs of app.js as one argument object, when app.js makes it, where mapLabel was (the
// build window, the file dialog and the project manager are given it after): the menu's handlers are set then.
import { ask } from './api.js';
import { plural, text } from './dom_words.js';
import { activeMapId, builder, builderMode, mapBrowser, mapCatalogue, placing, prefabLibrary, setLeaving,
         setMapBrowser } from './editor_state.js';
import { createMapBrowser } from './map_browser.js';
import { api as prefabApi } from './prefabs.js';
import { modalOpen } from './modal.js';

export function createMapMenu({ $, dirty, flashHint, goTo, recoverPrefabSources, saveProject, showPop, showPrefabDialog,
                                stopPlacing }) {
  const mapLabel = id => mapCatalogue?.maps.find(m => m.id === id)?.label ?? id ?? '';
  // Maps were prepared outside the map browser: the list it shows is brought up to the server's, entry by entry (the
  // browser keeps the array it was given).
  async function refreshMapList() {
    if (!mapCatalogue) return;
    try {
      const fresh = await ask('/maps.json');
      if (!fresh) return;
      for (const map of fresh.maps) {
        const mine = mapCatalogue.maps.find(m => m.id === map.id);
        if (mine) { delete mine.outdated; Object.assign(mine, map); } else mapCatalogue.maps.push(map);
      }
    } catch { /* the list stays as it was; a reload brings it */ }
  }
  // The map browser, made as the page opens (app.js's open, given the map the address asks for and the address's
  // parameters).
  function makeMapBrowser(activeMap, parameters) {
      // (the map the address asks for, when it isn't prepared yet: kept now, as the browser marks its entry ready)
      const askedUnprepared = !builderMode && activeMap && !activeMap.ready ? activeMapId : null;
      setMapBrowser(createMapBrowser({ els: { root: $('mapDialog'), form: $('mapForm'), search: $('mapSearch'), prepared: $('mapPrepared'),
        groups: $('mapGroups'), list: $('mapList'), count: $('mapCount'), message: $('mapMessage'), bar: $('mapBar'), ok: $('mapOk'),
        // On a patch preview the open map counts as not open: choosing it opens its original layout.
        cancel: $('mapCancel'), close: $('mapClose') }, maps: mapCatalogue.maps,
        current: activeMap?.ready && !parameters.get('scene') ? activeMapId : null,
        prefabs: async () => (await prefabApi.list()).prefabs, onPrefab: id => goTo({ prefab: id }),
        // The map asked for but not prepared yet opens as asked once it is ready: the address as it was, its project,
        // mission and layout too (review finding 7; nothing is open meanwhile). Any other map chosen is a switch of map,
        // which opens it alone.
        onOpen: id => {
          mapBrowser.close();
          if (id === askedUnprepared) { setLeaving(true); location.reload(); return; }
          goTo({ map: id, scene: null, project: null, mission: null });
        } }));
  }
  /** The Open window on a side, 'maps' or 'prefabs': after closing the menu and stopping a placing. */
  function showOpen(side = 'maps') {
    if (!mapBrowser || modalOpen()) return;
    // (from the menu, the window gives the focus back to the menu's button as it closes, not to a button now hidden)
    if ($('mapMenu').contains(document.activeElement)) $('mapButton').focus({ preventScroll: true });
    showPop(null);
    if (placing) stopPlacing();
    if (side === 'prefabs') mapBrowser.show(null, { prefabGroup: true });
    else mapBrowser.show();
  }

  // Open's two counts: the maps the install plays, the prefabs the library holds (once it has answered).
  function counts() {
    $('openMapsCount').textContent = plural(mapCatalogue?.maps.length ?? 0, 'map');
    $('openPrefabsCount').textContent = prefabLibrary?.loaded ? plural(prefabLibrary.usable().length, 'prefab')
      : prefabLibrary?.error ? 'no library' : 'Prefabs';
  }
  let hearing = false;
  // The menu drawn as it opens (popups.js showPop): what is open, its items, the counts.
  function renderMapMenu() {
    const info = $('docInfo');
    info.replaceChildren();
    if (builderMode) {
      $('docHead').textContent = 'This prefab';
      const doc = builder.doc, saved = Boolean(doc?.revision);
      text(info, 'strong', doc?.name ?? 'New prefab');
      text(info, 'div', saved ? `Revision ${doc.revision}${dirty() ? ' · unsaved changes' : ''}` : 'Save to add this prefab to the library.');
      const exportButton = $('docPrefabExport');
      exportButton.disabled = !saved;
      exportButton.title = !saved ? 'Save the prefab first: the file is its saved revision'
        : dirty() ? `Save the prefab as a file to pass on: its revision ${doc.revision} as saved, without the changes not saved yet`
        : 'Save the prefab as a file to pass on: references and numbers only, no game data';
    } else {
      $('docHead').textContent = 'This map';
      text(info, 'strong', mapLabel(activeMapId) || 'No map open');
    }
    // (a patch preview's map has no items of its own: its menu is Open alone)
    $('mapItems').hidden = builderMode || ![...$('mapItems').querySelectorAll('button')].some(b => !b.hidden);
    $('prefabItems').hidden = !builderMode;
    $('openPrefabsKey').textContent = builderMode ? 'Ctrl+O' : '';
    $('openPrefabs').title = `Open a prefab in the builder: your prefabs, with their pictures${builderMode ? ' (Ctrl+O)' : ''}`;
    if (!hearing && prefabLibrary) { prefabLibrary.onChange(counts); hearing = true; }
    counts();
    prefabLibrary?.refresh();
  }

  $('openMaps').onclick = () => showOpen('maps');
  $('openPrefabs').onclick = () => showOpen('prefabs');
  $('docNewPrefab').onclick = () => { showPop(null); goTo({ prefab: 'new' }); };
  $('docPrefabSave').onclick = () => { showPop(null); saveProject(); };
  $('docPrefabSaveAs').onclick = () => { showPop(null); showPrefabDialog(true); };
  $('docPrefabExport').onclick = async () => {
    showPop(null);
    const doc = builder.doc;
    if (!doc?.revision) return;
    try {
      await prefabLibrary.exportFile({ id: doc.id, name: doc.name, file: prefabLibrary.byId(doc.id)?.file });
      flashHint(`Exported ${doc.name} (revision ${doc.revision}): the file holds references and numbers only, no game data`);
    } catch (error) { flashHint(`Not exported: ${error.message}`); }
  };
  $('prefabRecover').onclick = () => { showPop(null); recoverPrefabSources(); };

  return { makeMapBrowser, mapLabel, refreshMapList, renderMapMenu, showOpen };
}
