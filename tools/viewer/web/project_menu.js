// The Project menu (refactor stage P9): the header's Project menu drawn afresh as it opens (renderProjectMenu): the open
// project's name, revision, the map name it builds as and its last build (or the prefab's, in the builder), Save and
// Save as, and the three projects last opened or saved in this browser (the recent list it keeps: recentTimes,
// touchRecent, which the document session calls as a project opens or saves). And the windows the menu's items and the
// keys open, each after closing the menu and stopping a placing: the file dialog to open or save a project
// (showFileDialog; in the builder, Save as prefab), the project manager (showProjectManager), Game maps
// (showGameMaps) and Cache everything (showPrecache).
//
// createProjectMenu takes what it needs of app.js as one argument object, when app.js makes it, after the windows it
// opens (their factories stay in app.js, which makes them with their elements): the document session's unsaved state
// and load, the map's names, Play's items, the popups, Save as prefab and the panel's helpers. It keeps no state: the
// recent list is the browser's (storage.js).
import { projectsAvailable } from './document_session.js';
import { activeMapId, builder, builderMode, lastBuild, placing, project } from './editor_state.js';
import { api as projectApi } from './project.js';
import { savedWhen } from './project_files.js';
import { recall, remember } from './storage.js';

export function createProjectMenu({ $, dirty, fileDialog, gameMaps, loadProject, mapLabel, modalOpen, precache,
                                    projectManager, renderPlayItems, showPop, showPrefabDialog, stopPlacing, text }) {
  // Recent projects: when this browser last opened or saved each, beside when it was saved anywhere.
  const RECENT = 'workshop.recentProjects';
  function recentTimes() { try { return JSON.parse(recall(RECENT)) ?? {}; } catch { return {}; } }
  function touchRecent(id) {
    const times = { ...recentTimes(), [id]: new Date().toISOString() };
    remember(RECENT, JSON.stringify(Object.fromEntries(Object.entries(times).sort((a, b) => b[1].localeCompare(a[1])).slice(0, 20))));
  }
  async function renderProjectMenu() {
    const info = $('projectInfo');
    info.replaceChildren();
    if (builderMode) {
      text(info, 'strong', builder.doc?.name ?? 'New prefab');
      text(info, 'div', builder.doc?.revision ? `Revision ${builder.doc.revision}${dirty() ? ' · unsaved changes' : ''}` : 'Save to add this prefab to the library.');
      for (const id of ['projectSave', 'projectSaveAs']) $(id).disabled = false;
      return;
    }
    if (project) {
      text(info, 'strong', project.doc.name);
      text(info, 'div', `Revision ${project.revision} · saved ${savedWhen(project.doc.savedAt)}${dirty() ? ' · unsaved changes' : ''}`);
      text(info, 'div', `Builds as ${project.doc.output?.shipAs ?? '(no map name)'}`).title = 'The map\'s name in the game (its package and records), fixed when the project was first saved: Save as under a new name makes a new project that builds under a name of its own';
      const pkg = lastBuild?.package;
      if (lastBuild?.state === 'running') text(info, 'div', `Building revision ${lastBuild.job.revision}…`);
      else if (pkg) {
        const last = text(info, 'div', `Last built: revision ${pkg.revision} · ${savedWhen(pkg.builtAt)}${pkg.quick ? ' · lighting not baked' : ''}`);
        last.title = pkg.quick ? `${pkg.folder}\nBuilt without baking the lighting: its lighting isn't right in the game (pathing and cover are). Build with Bake the lighting ticked for the proper lighting` : pkg.folder;
      }
    } else if (projectsAvailable()) text(info, 'div', 'No project open: edits are a trial until you save them.');
    else text(info, 'div', 'This is a patch preview: projects edit a map\'s original layout. Open the map from the map browser (M) to save one; Load opens a project on its map.');
    for (const id of ['projectSave', 'projectSaveAs']) $(id).disabled = !projectsAvailable();
    $('projectClose').hidden = !project;
    renderPlayItems();
    // Recent: the three last opened or saved here (or else saved anywhere), the open one aside.
    const list = $('projectRecent');
    try {
      const { projects } = await projectApi.list(), times = recentTimes();
      const when = p => [times[p.id] ?? '', p.savedAt ?? ''].sort().at(-1);
      const recent = projects.filter(p => !p.error && p.id !== project?.doc.id).sort((a, b) => when(b).localeCompare(when(a))).slice(0, 3);
      list.replaceChildren();
      for (const p of recent) {
        const button = text(list, 'button', '', 'projectitem');
        button.type = 'button'; button.dataset.id = p.id;
        text(button, 'strong', p.name ?? p.id);
        text(button, 'small', `${mapLabel(p.map)} · revision ${p.revision} · ${savedWhen(p.savedAt)}${p.recovery ? ' · unsaved changes kept' : ''}`);
        button.title = `Open ${p.name}`;
        button.onclick = () => { showPop(null); loadProject(p); };
      }
      if (!recent.length) text(list, 'div', projects.some(p => p.id === project?.doc.id) ? 'No other projects yet.' : 'No projects yet.', 'empty');
    } catch (e) { list.replaceChildren(`Projects could not be listed: ${e.message}`); }
  }
  function showGameMaps() {
    if (modalOpen()) return;
    showPop(null);
    if (placing) stopPlacing();
    gameMaps.show();
  }
  function showPrecache() {
    if (modalOpen()) return;
    showPop(null);
    if (placing) stopPlacing();
    precache.show();
  }
  function showProjectManager() {
    if (modalOpen()) return;
    showPop(null);
    if (placing) stopPlacing();
    projectManager.show();
  }
  function showFileDialog(mode, waitForSave = false) {
    if (builderMode && mode === 'save') return showPrefabDialog(true);
    if (fileDialog.open || (mode === 'save' && !projectsAvailable())) return;
    showPop(null);
    if (placing) stopPlacing();
    return fileDialog.show(mode, { mapId: activeMapId, current: project?.doc.id ?? null, name: mode === 'save' ? project?.doc.name ?? '' : '', waitForSave });
  }

  return { renderProjectMenu, showFileDialog, showGameMaps, showPrecache, showProjectManager, touchRecent };
}
