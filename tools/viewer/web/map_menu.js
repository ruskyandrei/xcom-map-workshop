// The map browser's wiring (refactor stage P9): the server's list of maps and the map browser made from it as the page
// opens (map_browser.js is the dialog itself). Here: a map's name in the lists (mapLabel), the list brought up to the
// server's after maps were prepared elsewhere (refreshMapList), the browser made, choosing a map opening it
// (makeMapBrowser, from app.js's open), and the Map menu's button and Change map, and M, opening the browser
// (showMapBrowser). The map list and the browser (mapCatalogue, mapBrowser) are editor_state.js's: app.js's open sets
// the list and shows the browser on a map not prepared yet, and the prefab builder's Open shows it.
//
// createMapMenu takes what it needs of app.js as one argument object, when app.js makes it, where mapLabel was (the
// build window, the file dialog and the project manager are given it after): the Map menu's handlers are set then.
import { ask } from './api.js';
import { activeMapId, builderMode, mapBrowser, mapCatalogue, placing, setLeaving,
         setMapBrowser } from './editor_state.js';
import { createMapBrowser } from './map_browser.js';
import { api as prefabApi } from './prefabs.js';

export function createMapMenu({ $, goTo, modalOpen, projectsAvailable, showPop, stopPlacing }) {
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
  function showMapBrowser() {
    if (!mapBrowser || modalOpen()) return;
    showPop(null);
    if (placing) stopPlacing();
    mapBrowser.show();
  }
  // The Map menu: Change map and the map's own things (missions, picture, grid, Clear map). Where it would hold Change
  // map alone (a prefab, a patch preview), the button opens the map browser itself.
  $('mapButton').onclick = () => {
    if (builderMode || !projectsAvailable()) { showMapBrowser(); return; }
    showPop($('mapMenu').hidden ? 'mapMenu' : null);
  };
  $('mapChange').onclick = showMapBrowser;

  return { makeMapBrowser, mapLabel, refreshMapList, showMapBrowser };
}
