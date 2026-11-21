// The document session (refactor stage P3): the open document's life on the page. A project is opened (its state put
// on the scene; records naming what this export lacks are carried and saved back unchanged), saved (its next revision,
// Save as, Replace) and left (asked first whether to save); its unsaved state is kept on the server as a draft against
// a lost tab, and offered back when it opens (a draft belongs to the page session that keeps it: review finding 3);
// the banner under the header says what happened. The prefab builder's document (builder_session.js) shares the
// drafts, the leaving and the banner.
//
// createDocumentSession takes what it needs of app.js as one argument object, when app.js makes it: the scene to and
// from a document (applyState, editState), the gizmo, the camera, the dialogs and panels it opens or paints, and the
// page session's id (SESSION). Its own state is inside it (navigating, the banner's timer); what other areas share
// with it (leaving, saving, the drafts' timer, owner and trouble, the build status, the copies' serial) is
// editor_state.js's.
import { onHub } from './edit_hub.js';
import { activeMapId, adoptedDraft, buildTimer, builderMode, copySerial, data, landingRead, looksReady, project, recoveryKept,
         recoveryTimer, recoveryTrouble, saving, setAdoptedDraft, setAskedPick, setLastBuildValue, setLeaving, setProject,
         setRecoveryKept, setRecoveryTimer, setRecoveryTrouble, setSaving } from './editor_state.js';
import { api as projectApi, newDocument, sortState, sourceOf, stateKey, validAdded, validBinding, validBuilding, validGroup,
         validOverride, validStage, SCHEMA_VERSION as PROJECT_SCHEMA_VERSION } from './project.js';
import { api as prefabApi } from './prefabs.js';
import { setParagraphs } from './missions.js';

export function createDocumentSession({ $, SESSION, applyState, bombHelperFix, builder, builderDocument, builderTitle, camera, controls,
                                        dirty, documentWrites, editChanged, editState, flashHint, followBuild, gizmo, loadingState,
                                        openingProgress, ownSize, plural, problemsPaint, projectNote, projectsAvailable,
                                        refreshBuilder, renderPlayItems, saveBuilder, saveState, setLastBuild, setMissionMoves,
                                        showFileDialog, text, touchRecent, unsavedDocument }) {
  // a switch of document under way (asking, saving, leaving): no other starts, and no draft is kept meanwhile
  let navigating = false;
  // Discarding the changes on screen: this page's own draft goes, and a draft it restored; other pages' stay.
  async function clearDocumentRecovery() {
    clearTimeout(recoveryTimer);
    const id = builderMode ? builder.doc?.id : project?.doc.id, api = builderMode ? prefabApi : projectApi;
    const adopted = adoptedDraft;
    setAdoptedDraft(null);
    await documentWrites.run(async () => {
      if (!id) return;
      await api.dropRecovery(id, SESSION);
      if (adopted) await api.dropRecovery(id, adopted.owner, adopted.savedAt);
    });
    setRecoveryKept(false);
  }
  // A draft the user restored, deleted once this page's own draft or a save holds its changes.
  function dropAdopted(api, id) {
    const adopted = adoptedDraft;
    if (!adopted || !id) return Promise.resolve();
    setAdoptedDraft(null);
    return documentWrites.run(() => api.dropRecovery(id, adopted.owner, adopted.savedAt)).catch(() => {});
  }
  // A draft the user was shown and discarded: that one alone, while it is still the one shown.
  function discardDraft(api, id, draft) {
    return documentWrites.run(() => api.dropRecovery(id, draft.owner, draft.savedAt))
      .catch(error => banner(`The kept changes could not be discarded: ${error.message}`));
  }
  // What a draft offered back says beside its time: based on an older revision (another page saved since), and how
  // many more are kept.
  function draftWords(draft, revision) {
    const words = [];
    if (Number.isInteger(draft.baseRevision) && draft.baseRevision !== revision)
      words.push(` They were made on revision ${draft.baseRevision}; it has been saved since (revision ${revision}), so restoring them puts revision ${draft.baseRevision}'s state back with these changes, and saving that replaces what was saved since.`);
    if (draft.others) words.push(` ${plural(draft.others, 'other set')} of unsaved changes ${draft.others === 1 ? 'is' : 'are'} kept too, from other windows or tabs.`);
    return words.join('');
  }
  // A draft write that failed, or was kept against an older revision than the saved one: said once, until a write
  // goes through again.
  function recoveryProblem(kind, message) {
    if (recoveryTrouble === kind) return;
    setRecoveryTrouble(kind);
    banner(message);
  }
  async function discardAndGo(change) {
    await clearDocumentRecovery(); setLeaving(true); navigate(change);
  }
  function askLeave() {
    return new Promise(resolve => {
      const modal = $('leaveDialog'); modal.hidden = false;
      $('leaveName').textContent = `Save changes to ${builderMode ? builder.doc.name : project?.doc.name ?? 'this map'} before opening something else?`;
      const done = value => { modal.hidden = true; resolve(value); };
      $('leaveSave').onclick = () => done('save'); $('leaveDiscard').onclick = () => done('discard'); $('leaveCancel').onclick = () => done('cancel');
      modal.onkeydown = e => { e.stopPropagation(); if (e.key === 'Escape') done('cancel'); };
      $('leaveCancel').focus();
    });
  }
  // A message under the header with its actions (recovered edits, a save conflict, a project that cannot open).
  // timeout (ms): a passing message closes itself after that long (Play in game's "Starting XCOM …"); hovering it
  // keeps it open, and × still closes it sooner. Without one it stays until dismissed.
  let bannerTimer = null;
  function banner(message, actions = [], { timeout = 0 } = {}) {
    const el = $('projectBanner');
    clearTimeout(bannerTimer);
    el.onmouseenter = el.onmouseleave = null;
    // a message with line breaks: one paragraph each
    if (typeof message === 'string' && message.includes('\n')) {
      const body = document.createElement('div'); body.className = 'bannertext';
      setParagraphs(body, message);
      el.replaceChildren(body);
    } else el.replaceChildren(message);
    // (an action that fails says so in the banner, as Restore them does when a recovered piece can't be read: review
    // finding 29)
    for (const [label, run] of actions) {
      const button = text(el, 'button', label);
      button.type = 'button';
      button.onclick = () => {
        el.hidden = true;
        try { run()?.catch?.(error => banner(`${label} could not be done: ${error?.message ?? error}`)); }
        catch (error) { banner(`${label} could not be done: ${error?.message ?? error}`); }
      };
    }
    const close = text(el, 'button', '×', 'close');
    Object.assign(close, { type: 'button', title: 'Dismiss' });
    close.onclick = () => { el.hidden = true; };
    el.hidden = false;
    if (timeout) {
      const arm = () => { clearTimeout(bannerTimer); bannerTimer = setTimeout(() => { el.hidden = true; }, timeout); };
      el.onmouseenter = () => clearTimeout(bannerTimer);
      el.onmouseleave = arm;
      arm();
    }
  }
  function navigate(change) {
    const parameters = new URLSearchParams(location.search);
    if ('prefab' in change) for (const key of ['map', 'project', 'scene', 'mission']) parameters.delete(key);
    else if ('map' in change || 'project' in change) parameters.delete('prefab');
    for (const [key, value] of Object.entries(change)) { if (value == null) parameters.delete(key); else parameters.set(key, value); }
    location.search = parameters.toString();
  }
  async function goTo(change) {
    if (navigating || saving) return false;
    navigating = true;
    try {
      if (unsavedDocument()) {
        const decision = await askLeave();
        if (decision === 'cancel') return false;
        if (decision === 'save') {
          const saved = builderMode ? await saveBuilder() : project ? await saveProject() : await showFileDialog('save', true);
          if (!saved || (builderMode ? dirty() : !project || dirty())) return false;
        }
      }
      await discardAndGo(change); return true;
    } catch (error) { banner(`Could not leave: ${error.message}`); return false; }
    finally { navigating = false; }
  }
  async function openProject(id) {
    if (!projectsAvailable()) { banner('Projects edit a map\'s original layout, so this layout opened without the project.'); return; }
    let doc;
    try { doc = await projectApi.load(id); }
    catch (e) { banner(`The project could not be opened: ${e.message}`); return; }
    await looksReady;
    await landingRead;      // (the starting landing zones come from it: review finding 31)
    if (doc.source?.map !== activeMapId) { goTo({ map: doc.source?.map, scene: null, project: id }); return new Promise(() => {}); }
    // (the server opens only a project it can read: projects.shape_problem. A document whose edits are not lists is
    // refused here too, rather than opened without them and saved back so: review finding 9)
    const listOrNone = value => value === undefined || Array.isArray(value);
    if (!listOrNone(doc.overrides) || !listOrNone(doc.added) || typeof doc.source?.sha256 !== 'string') {
      banner(`The project could not be opened: ${doc.name ?? id} is not a project this editor can read (its edits or its base map are not as a project has them).`);
      return;
    }
    $('loading').hidden = false; loadingState(`Opening ${doc.name}…`, 0);
    const docOverrides = doc.overrides ?? [], docAdded = doc.added ?? [];
    const docGroups = Array.isArray(doc.groups) ? doc.groups : [];
    const docBindings = Array.isArray(doc.areaLightBindings) ? doc.areaLightBindings : [];
    const malformed = { overrides: docOverrides.filter(r => !validOverride(r)), added: docAdded.filter(e => !validAdded(e)),
                        groups: docGroups.filter(g => !validGroup(g)), areaLightBindings: docBindings.filter(b => !validBinding(b)) };
    const carried = await applyState({ overrides: docOverrides.filter(validOverride), added: docAdded.filter(validAdded),
                                       groups: docGroups.filter(validGroup), areaLightBindings: docBindings.filter(validBinding),
                                       stage: doc.stage, buildings: Array.isArray(doc.buildings) ? doc.buildings : [],
                                       cleared: doc.cleared === true, clearKeepsOutside: doc.clearKeepsOutside === true,
                                       landingZones: Array.isArray(doc.landingZones) ? doc.landingZones : null,
                                       missions: Array.isArray(doc.missions) ? doc.missions : null,
                                       spawnRules: doc.spawnRules ?? null, picture: doc.picture ?? null,
                                       nextSerial: doc.nextSerial }, openingProgress(doc.name));
    // a building this page can't read is kept and saved back unchanged, and so is one of the map's it can't edit
    carried.buildings = [...(carried.buildings ?? []), ...(Array.isArray(doc.buildings) ? doc.buildings : []).filter(b => !validBuilding(b))];
    carried.overrides.push(...malformed.overrides); carried.added.push(...malformed.added); carried.groups.push(...malformed.groups);
    carried.areaLightBindings.push(...malformed.areaLightBindings);
    setProject({ doc, revision: doc.revision, carried, savedKey: stateKey(editState()) });
    // a bomb moved before export 33 left its helper point behind (F-124; decision D6): the helper gets the move now, and
    // the project shows as changed until it is saved
    const helped = bombHelperFix();
    if (helped) {
      setMissionMoves(helped);
      banner('The bomb\'s helper point now moves with it: Long War\'s bomb mutator finds the bomb again and places it where it finds places, the project\'s place being where it plays when it finds none. Save the project to keep it.');
    }
    setAskedPick(null);     // (the address's added kind is picked by now, if the project adds it)
    touchRecent(id);
    // its last package, and a build still running (opened again, or the page reloaded mid-build): follow it
    projectApi.buildStatus(id).then(s => { if (!setLastBuild(id, s)) return; renderPlayItems(); if (s.state === 'running') followBuild(s, id); }, () => {});
    $('loading').hidden = true;
    const kept = carried.overrides.length + carried.added.length + carried.groups.length + carried.areaLightBindings.length
      + carried.buildings.filter(validBuilding).length;
    if (kept) projectNote(`${doc.name}: ${plural(kept, 'edit')} name pieces this export does not have; they are kept and saved back unchanged.`);
    if (doc.source.sha256 !== data.source.sha256) {
      projectNote(`${doc.name} was made on another ${doc.source.package} (SHA-256 ${doc.source.sha256.slice(0, 12)}…, this one ${data.source.sha256.slice(0, 12)}…).`);
      banner(`${doc.name} was made on a different ${doc.source.package}. Its edits are shown where their pieces match; check them before building.`);
    }
    if (doc.view?.camera?.length === 3 && doc.view.target?.length === 3) {
      camera.position.fromArray(doc.view.camera); controls.target.fromArray(doc.view.target); controls.update();
    }
    await offerProjectDraft(id, doc);
    editChanged();
  }
  // The newest draft of the project another page session kept (a lost tab's, or another window's), offered back: one
  // that is the saved state already is spent, and goes (the next is offered then).
  async function offerProjectDraft(id, doc, tries = 4) {
    const recovery = await projectApi.recovery(id).catch(() => null);
    if (recovery && Array.isArray(recovery.overrides) && Array.isArray(recovery.added)) {
      const state = { overrides: recovery.overrides.filter(validOverride), added: recovery.added.filter(validAdded),
                      groups: (Array.isArray(recovery.groups) ? recovery.groups : []).filter(validGroup),
                      areaLightBindings: (Array.isArray(recovery.areaLightBindings) ? recovery.areaLightBindings : []).filter(validBinding),
                      stage: validStage(recovery.stage, ownSize()?.dims) ? recovery.stage : null,
                      buildings: (Array.isArray(recovery.buildings) ? recovery.buildings : []).filter(validBuilding),
                      cleared: recovery.cleared === true, clearKeepsOutside: recovery.clearKeepsOutside === true,
                      landingZones: Array.isArray(recovery.landingZones) ? recovery.landingZones : null,
                      missions: Array.isArray(recovery.missions) ? recovery.missions : null,
                      spawnRules: recovery.spawnRules ?? null, picture: recovery.picture ?? null,
                      nextSerial: recovery.nextSerial };
      if (stateKey(sortState(state)) !== project.savedKey) {
        const when = new Date(recovery.savedAt).toLocaleString();
        banner(`Unsaved changes to ${doc.name} from ${when} were kept.${draftWords(recovery, project.revision)}`, [
          ['Restore them', async () => {
            await applyState(state);
            setAdoptedDraft({ owner: recovery.owner, savedAt: recovery.savedAt });
            setRecoveryKept(true); projectChanged();
          }],
          ['Discard them', async () => {
            await discardDraft(projectApi, id, recovery);
            if (recovery.others && project?.doc.id === id) await offerProjectDraft(id, doc, tries - 1);
          }],
        ]);
      } else if (tries > 0) {
        const { dropped } = await documentWrites.run(() => projectApi.dropRecovery(id, recovery.owner, recovery.savedAt)).catch(() => ({ dropped: false }));
        if (dropped && recovery.others) await offerProjectDraft(id, doc, tries - 1);
      }
    }
  }
  // The project's own state in the header, and its unsaved state kept on the server against a lost tab.
  function projectChanged() {
    if (builderMode) {
      if (builder.loading) return;
      builderTitle(); refreshBuilder(); problemsPaint(); clearTimeout(recoveryTimer);
      // (the status says saved or unsaved: a save changes it with no edit)
      if (builder.doc?.revision) { $('editCount').hidden = false; $('editCount').textContent = saveState(); $('editCount').classList.toggle('warn', saveState() !== 'saved'); }
      if (!navigating && !saving) setRecoveryTimer(setTimeout(keepRecovery, 1000));
      return;
    }
    $('projectTitle').textContent = project ? project.doc.name : 'None';
    renderPlayItems();
    if (!project) return;
    $('projectButton').classList.toggle('unsaved', dirty());
    clearTimeout(recoveryTimer);
    setRecoveryTimer(setTimeout(keepRecovery, 1000));
  }
  async function keepRecovery() {
    if (builderMode) {
      if (!builder.doc?.revision || builder.loading || saving || navigating) return;
      if (gizmo.controls.dragging) { setRecoveryTimer(setTimeout(keepRecovery, 1000)); return; }
      const id = builder.doc.id, state = { owner: SESSION, baseRevision: builder.doc.revision, document: builderDocument(), envelope: builder.envelope, nextSerial: copySerial };
      const changed = dirty();
      if (!changed && !recoveryKept) return;
      try {
        const kept = await documentWrites.run(() => changed ? prefabApi.keepRecovery(id, state) : prefabApi.dropRecovery(id, SESSION));
        setRecoveryKept(changed);
        if (changed) { keptDraft(kept, builder.doc.name); dropAdopted(prefabApi, id); }
      } catch (error) {
        recoveryProblem('failed', `Unsaved changes to ${builder.doc.name} could not be kept for recovery: ${error.message}. They are still on screen; save to keep them.`);
      }
      return;
    }
    if (!project || saving || navigating) return;
    // A drag in progress is never kept half done.
    if (gizmo.controls.dragging) { setRecoveryTimer(setTimeout(keepRecovery, 1000)); return; }
    const state = editState(), id = project.doc.id;
    try {
      if (stateKey(state) !== project.savedKey) {
        const snapshot = { owner: SESSION, baseRevision: project.revision, nextSerial: copySerial, ...state };
        const kept = await documentWrites.run(() => projectApi.keepRecovery(id, snapshot));
        setRecoveryKept(true);
        keptDraft(kept, project.doc.name);
        dropAdopted(projectApi, id);
      } else if (recoveryKept) { await documentWrites.run(() => projectApi.dropRecovery(id, SESSION)); setRecoveryKept(false); }
    } catch (error) {
      // (said in the page, as a prefab's is: review finding 3)
      recoveryProblem('failed', `Unsaved changes to ${project?.doc.name ?? 'the project'} could not be kept for recovery: ${error.message}. They are still on screen; save to keep them.`);
    }
  }
  // A draft the server kept: one kept against an older revision than the saved one says so once (another window or tab
  // saved meanwhile; saving then asks whether to overwrite that).
  function keptDraft(kept, name) {
    if (kept?.stale) recoveryProblem('stale', `${name} was saved elsewhere since this page opened it (revision ${kept.revision}). `
      + 'These unsaved changes are kept for recovery; saving asks whether to overwrite that revision.');
    else setRecoveryTrouble(null);
  }
  // Save (Ctrl+S): the open project's next revision; without one, the Save dialog asks for a name first.
  // The Save dialog calls it with { name, output } for a new project from what is on screen, with the map name it showed
  // (the server's: output names plan); { name, replace } to put what is on screen into that saved project, which keeps
  // its id and map name; or { rename } for the open project's next revision under that name (the dialog matches names
  // regardless of case), its map name kept. A new project's save that the server refuses because its map name was
  // taken meanwhile throws, so the dialog can show the name it would get now; other failures say so in a banner.
  async function saveProject({ name = null, replace = null, rename = null, output = null } = {}) {
    if (builderMode) return saveBuilder({ name, replace });
    if (!projectsAvailable() || saving || gizmo.controls.dragging) return false;
    if (!project && !name) { showFileDialog('save'); return false; }
    setSaving(true);
    clearTimeout(recoveryTimer); await documentWrites.wait();
    const state = editState(), carried = project?.carried ?? { overrides: [], added: [], groups: [], areaLightBindings: [] };
    const previous = project?.doc.id, fresh = Boolean(name) && !replace;
    // What is on screen was made against the open project's map, or else this export. A project of this very package
    // opened on a newer export is bound to it on saving: what is on screen is that export's, and the Build compiles
    // against the export the project names (compiler.find_export), so a newer export's data (export 23's effects) reaches
    // it.
    const source = project ? { ...project.doc.source } : sourceOf(activeMapId, data);
    if (project && source.sha256 === data?.source?.sha256 && Number(data.exporterVersion) > Number(source.exporterVersion ?? 0))
      source.exporterVersion = data.exporterVersion;
    let base = project?.doc, expected = project?.revision;
    try {
      if (replace) {
        // the revision the dialog showed is the one replaced, and no other (review finding 4): one saved since is asked
        // about again (the dialog shows its revision now)
        const target = await projectApi.load(replace.id);
        if (target.source?.map !== activeMapId) throw new Error(`${target.name} is a project of another map.`);
        if (target.revision !== replace.revision)
          throw Object.assign(new Error(`${target.name} was saved again meanwhile (revision ${target.revision})`), { status: 409, body: { revision: target.revision } });
        base = { ...target, name, source }; expected = replace.revision;
      } else if (fresh) {
        if (!output) throw new Error('the map name is still being worked out; save again in a moment');
        base = { ...newDocument(name, activeMapId, data, output), source }; expected = 0;
      }
      else if (rename && project) base = { ...project.doc, name: rename };
      const document = { ...base, schemaVersion: PROJECT_SCHEMA_VERSION, ...sortState({ overrides: [...state.overrides, ...carried.overrides], added: [...state.added, ...carried.added],
                                                 groups: [...state.groups, ...carried.groups],
                                                 areaLightBindings: [...state.areaLightBindings, ...(carried.areaLightBindings ?? [])],
                                                 stage: state.stage, buildings: [...(state.buildings ?? []), ...(carried.buildings ?? [])],
                                                 cleared: state.cleared, clearKeepsOutside: state.clearKeepsOutside,
                                                 landingZones: state.landingZones, missions: state.missions, spawnRules: state.spawnRules,
                                                 picture: state.picture }),
                         nextSerial: copySerial, view: { camera: camera.position.toArray(), target: controls.target.toArray() } };
      if (project && !replace && !fresh) document.source = source;     // a newer export of the same package binds it
      if (!document.stage) delete document.stage;     // the map's own size is said by saying nothing
      if (!document.buildings.length) delete document.buildings;
      if (!document.cleared) delete document.cleared;
      if (!document.clearKeepsOutside) delete document.clearKeepsOutside;
      if (document.landingZones == null) delete document.landingZones;     // the map's own landings and lines
      if (document.missions == null) delete document.missions;     // every mission of the base map
      if (document.picture == null) delete document.picture;       // no picture of its own
      delete document.revision; delete document.savedAt;
      if (fresh) delete document.created;
      // saved as another project: its map picture is kept by project, so the server copies the file to the new one
      // within the save, byte for byte, before the document is written (review finding 8)
      const pictureFrom = previous && previous !== document.id && document.picture ? { pictureFrom: previous } : {};
      const result = await projectApi.save(document.id, document, expected, { owner: SESSION, ...pictureFrom });
      if (result.pictureMissing)
        banner(`The map picture was not copied to ${document.name}: the project saved from keeps it no more. Choose it again in Map picture.`);
      // Saved under another project: this page's draft of the one open before is in it now, and so is a draft restored
      // (the server dropped this page's draft of the one saved).
      if (previous && previous !== document.id) documentWrites.run(() => projectApi.dropRecovery(previous, SESSION)).catch(() => {});
      dropAdopted(projectApi, previous);
      setRecoveryTrouble(null);
      const { pictureMissing, note, ...saved } = result;
      if (note) banner(`Saved ${document.name}. ${note}`);      // (saved, with something left to say: projects.py)
      setProject({ doc: { ...document, ...saved }, revision: result.revision, carried, savedKey: stateKey(state) });
      if (previous !== document.id) {
        // another project now (Save as, or Replace): its own build status, not the one saved from's (review finding 10)
        setLastBuildValue(null); clearTimeout(buildTimer);
        const id = document.id;
        projectApi.buildStatus(id).then(s => { if (setLastBuild(id, s)) { renderPlayItems(); if (s.state === 'running') followBuild(s, id); } }, () => {});
      }
      setRecoveryKept(false);
      touchRecent(document.id);
      const parameters = new URLSearchParams(location.search);
      parameters.set('map', activeMapId); parameters.delete('scene'); parameters.set('project', document.id);
      history.replaceState(null, '', `?${parameters}`);
      flashHint(`Saved ${document.name} · revision ${result.revision}`);
      return true;
    } catch (e) {
      // the map name shown was taken meanwhile: the dialog shows the one it would get now, and nothing is lost
      if (fresh && e.status === 409 && e.body?.proposal) throw e;
      // the project replaced was saved again since the dialog showed it: the dialog asks again
      if (replace && e.status === 409 && Number.isInteger(e.body?.revision)) throw e;
      if (e.status === 409 && Number.isInteger(e.body?.revision) && !name && !replace) {
        setRecoveryTrouble('stale');      // (told here: the drafts kept meanwhile say nothing more of it)
        banner(`${project.doc.name} was saved elsewhere since you opened it (revision ${e.body.revision}).`, [
          ['Overwrite it with this', () => { project.revision = e.body.revision; saveProject(); }],
          ['Open the saved one', () => discardAndGo({ map: activeMapId, project: project.doc.id, scene: null })],
        ]);
      } else banner(`Not saved: ${e.message}`);
      return false;
    } finally { setSaving(false); editChanged(); }
  }
  // Opening another project reloads the page on its map (the browser asks first if there are unsaved changes).
  function loadProject(p) { if (p.id !== project?.doc.id) goTo({ map: p.map, scene: null, project: p.id }); }
  // Build in the manager saves the open project first when it is ticked and has unsaved changes, as the editor's own
  // Build does; a save that fails or is refused queues nothing, and neither does a project switched meanwhile.
  async function ensureSavedFor(ids) {
    if (builderMode || !project || !ids.includes(project.doc.id) || !dirty()) return true;
    const id = project.doc.id;
    const saved = await saveProject();
    return Boolean(saved) && project?.doc.id === id && !dirty();
  }

  // After an edit (the edit hub, edit_hub.js).
  onHub('edit', 'project', () => { projectChanged(); });

  return { banner, discardAndGo, discardDraft, draftWords, dropAdopted, ensureSavedFor, goTo, keepRecovery, loadProject,
           openProject, projectChanged, saveProject };
}
