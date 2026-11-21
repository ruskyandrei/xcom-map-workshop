// The prefab builder's session (refactor stage P5; prefab plan 5.6b, plan "sturdier prefabs"): the page opened on a
// prefab (?prefab=<id>, or new) edits it with the map's roots, history and tools, as a complete document instead of a
// delta against a map; the pieces that can't be made here stay members of it, carried as the file had them.
// - The document: the scene as the prefab's records (builderDocument), what Save compares (builderKey), the records
//   with their size (builderRecords), opened with a draft offered back (openPrefabDocument) and saved (saveBuilder).
// - The size line and the ground drawn under the prefab (refreshBuilder), Align to grid, the missing pieces looked
//   for by recipe, and the Problems check: what Test in game would say of the prefab, asked of the server without
//   building anything.
//
// createBuilderSession takes what it needs of app.js as one argument object, when app.js makes it: the roots' makers
// and readers, the gizmo, the camera's target, the document session's banner and drafts, the scene to and from a
// document (applyState, editState), and the Save as prefab dialog and records (prefab_place.js). Its own state is
// inside it (the boxes worked out, the ground's key, the Problems check's); the builder's document, the edit hub's
// memo and what prefabs saved and placed share with it are editor_state.js's.
import * as THREE from 'three';
import { call } from './api.js';
import { TILE } from './constants.js';
import { allRoots, builder, builderMode, data, donorHashes, effectRoots, eventMemo, groups, lightRoots, prefabPictures,
         prefabTab, recoveryTimer, roots, saving, setAdoptedDraft, setRecoveryKept, setRecoveryTrouble, setSaving,
         volumeRoots } from './editor_state.js';
import { PIECE_FIELDS } from './piece_records.js';
import { gridMove, nearestGridPose } from './poserule.js';
import { PREFAB_GRID_LEVELS, PREFAB_GRID_TOP, PREFAB_MAX_Z, PREFAB_MIN_Z, PREFAB_TILES, normalizePrefab,
         reconcilePrefab } from './prefab_document.js';
import { api as prefabApi, newPrefab } from './prefabs.js';
import { uuid } from './project.js';
import { savedWhen } from './project_files.js';
import { plural, short, text } from './dom_words.js';

export function createBuilderSession({ $, SESSION, actorPose, addRoots, addedObject, applyState, banner, boxOf,
                                       buildRoot, controls, dirty, discardAndGo, discardDraft, documentWrites,
                                       draftWords, dropAdopted, editChanged, editState, flashHint, frame, gizmo,
                                       gridNow, gridOrigin, isStream, libraryTemplate, lightPose, loadingState,
                                       movedMatrix, openingProgress, prefabRecords, projectChanged, recipeOf,
                                       removeRoots, rootName, sceneChanged, selectActors, showFileDialog,
                                       showPrefabDialog, snapshot, templateFor, volumeBox, world }) {
  // The prefab builder uses the same roots, history and tools, with a complete document
  // instead of a delta against a map. Missing pieces remain members of that document.
  const physicalBoxes = new WeakMap();
  function physicalBox(root) {
    if (root.userData.light) { const p = lightPose(root).location; return [...p, ...p]; }
    if (root.userData.volume) return volumeBox(root);
    if (root.userData.effect) return null;
    const key = root.matrix.elements.join(',') + ':' + root.userData.source.mesh;
    if (physicalBoxes.get(root)?.key === key) return physicalBoxes.get(root).box;
    const b = boxOf(root, true), box = b ? [b[0], b[2], b[4], b[1], b[3], b[5]] : null;
    physicalBoxes.set(root, { key, box }); return box;
  }
  // (PIECE_FIELDS, the record fields this editor knows, are piece_records.js's)
  function builderDocument() {
    if (!eventMemo) return builderDocumentNow();
    return eventMemo.document ??= builderDocumentNow();
  }
  function builderDocumentNow() {
    const state = editState(), known = state.added.map(({ id, ...p }) => {
      const original = builder.metadata.get(p.actor);
      // (a field of a newer editor's, which this one doesn't know, is carried as the file had it: prefabs.py `carried`)
      const carried = original ? Object.fromEntries(Object.entries(original).filter(([k]) => !PIECE_FIELDS.has(k))) : {};
      return { ...carried, ...p, ...(p.from && original?.recipe && !p.recipe ? { recipe: original.recipe } : {}) };
    });
    const pieces = [...known, ...builder.kept].sort((a, b) => a.actor.localeCompare(b.actor));
    const reconciled = reconcilePrefab(pieces, state.buildings, [...groups.values()].map(g => ({ ...g, members: [...g.members.values()] })));
    const donors = new Map((builder.doc?.donors ?? []).map(d => [d.package.toLowerCase(), d]));
    for (const p of pieces) if (p.from && !donors.has(p.from.package.toLowerCase())) {
      const sha256 = donorHashes.get(p.from.package.toLowerCase());
      donors.set(p.from.package.toLowerCase(), { package: p.from.package, ...(sha256 ? { sha256 } : {}) });
    }
    const used = new Set(pieces.filter(p => p.from).map(p => p.from.package.toLowerCase()));
    return { ...builder.doc, pieces: reconciled.pieces, groups: reconciled.groups, buildings: state.buildings,
      donors: [...donors].filter(([key]) => used.has(key)).map(([, d]) => d).sort((a, b) => a.package.localeCompare(b.package)) };
  }
  function builderKey() {
    if (eventMemo?.key) return eventMemo.key;
    const { pieces, groups, buildings, donors } = builderDocument();
    const key = JSON.stringify({ pieces, groups, buildings, donors, envelope: builder.envelope });
    if (eventMemo) eventMemo.key = key;
    return key;
  }
  function builderBounds() {
    const boxes = [...allRoots.values()].filter(r => !r.userData.deleted).map(r => [rootName(r), physicalBox(r)]).filter(([, b]) => b);
    for (const p of builder.kept) if (['point', 'spot'].includes(p.template?.kind) || (p.kind && !p.template)) boxes.push([p.actor, [...p.location, ...p.location]]);
    // (an effect, a sound or a lens flare is where it stands)
    for (const r of effectRoots.values()) {
      if (r.userData.deleted || !r.userData.source.added) continue;
      const p = actorPose(r.userData.source, r.matrix).location;
      boxes.push([short(r.userData.source.actor), [...p, ...p]]);
    }
    return boxes;
  }
  function builderRecords() {
    const doc = builderDocument(), clip = snapshot([...allRoots.values()], new Set()) ?? { entries: [], volumes: [], name: doc.name };
    const records = normalizePrefab(doc, builderBounds(), { envelope: builder.envelope, unknown: builder.kept.filter(p => !p.kind || p.template).map(p => p.actor) });
    const lights = records.pieces.filter(p => ['point', 'spot'].includes(p.template?.kind)).length;
    const [effects, sounds, flares] = ['effect', 'sound', 'flare'].map(kind => records.pieces.filter(p => !p.template && p.kind === kind).length);
    const b = records.size.bounds;
    return { ...records, clip, left: [], offGrid: [...roots.values()].filter(r => gridNow(r)?.valid === false).map(rootName),
      counts: { pieces: records.pieces.length - lights - effects - sounds - flares, lights, effects, sounds, flares, buildings: records.buildings.length, tiles: records.tiles },
      box: new THREE.Box3(new THREE.Vector3(b[0], b[2], b[1]), new THREE.Vector3(b[3], b[5], b[4])) };
  }
  // Align to grid (the builder's warning, prefab plan 5.6b): the pieces keeping the pose rule (doors, ladders, cars, vans,
  // fracturing pieces) that stand off their grid, and the one smallest shift of the whole prefab that puts every such
  // piece on it: each off piece's nearest whole tile and level (poserule.js nearestGridPose), the least of those that
  // suits them all. { off: [{ root, name }], delta, pivot (a root id) } or, with no such shift, turned (pieces a shift
  // can't help: turned off quarter turns, or pitched) or clash (no one shift suits them all).
  function gridAlignment() {
    const origin = gridOrigin(), ruled = [];
    if (!origin) return { off: [] };
    for (const [id, r] of roots) {
      if (r.userData.deleted || isStream(r.userData.source) || r.userData.light) continue;
      const from = recipeOf(r.userData.source);
      if (!from) continue;
      const pose = actorPose(r.userData.source, r.matrix);
      ruled.push({ id, r, from, pose, move: gridMove(from.location, from.rotation, pose.location, pose.rotation, origin) });
    }
    const off = ruled.filter(p => !p.move.valid);
    const named = [...new Map(off.map(p => [rootName(p.r), { root: p.r, id: p.id, name: rootName(p.r) }])).values()];
    if (!off.length) return { off: [] };
    const turned = named.filter(n => off.some(p => p.r === n.root && p.move.why.some(w => w === 'pitch or roll' || w === 'quarter turns')));
    if (turned.length) return { off: named, turned };
    const suits = d => ruled.every(p => gridMove(p.from.location, p.from.rotation, p.pose.location.map((v, k) => v + d[k]), p.pose.rotation, origin).valid);
    const best = off.map(p => ({ p, delta: nearestGridPose(p.from.location, p.from.rotation, p.pose.location, p.pose.rotation, origin)
      .location.map((v, k) => Number((v - p.pose.location[k]).toFixed(4))) }))
      .sort((a, b) => Math.hypot(...a.delta) - Math.hypot(...b.delta)).find(c => suits(c.delta));
    return best ? { off: named, delta: best.delta, pivot: best.p.id } : { off: named, clash: true };
  }
  // The shift made: everything of the prefab (pieces, lights, floor boxes) moved as one, one undo step; the selection
  // is given back.
  function alignToGrid() {
    const plan = gridAlignment();
    if (!plan.delta || builder.kept.length || gizmo.controls.dragging) return false;
    const before = gizmo.picks();
    const ids = [roots, lightRoots, volumeRoots].flatMap(m => [...m].filter(([, r]) => !r.userData.deleted).map(([id]) => id));
    gizmo.setSelection(ids, plan.pivot);
    const pose = gizmo.pose();
    if (pose) gizmo.setPose(pose.location.map((v, k) => v + plan.delta[k]), null);
    gizmo.setSelection(before.ids.filter(id => allRoots.has(id)), before.active);
    editChanged();
    flashHint(`Moved the prefab ${shiftWords(plan.delta)}: every door, ladder and fracturing piece is on the grid`);
    return Boolean(pose);
  }
  const shiftWords = d => [['east', 'west'], ['south', 'north'], ['up', 'down']]
    .map(([plus, minus], k) => Math.abs(d[k]) > 0.005 ? `${Math.abs(Number(d[k].toFixed(2)))} ${d[k] > 0 ? plus : minus}` : '')
    .filter(Boolean).join(', ') || 'nowhere';
  // The warning over the size: what stands off the grid, Show (select those pieces) and Align to grid.
  function gridWarning() {
    const plan = gridAlignment(), box = $('gridWarning');
    box.hidden = !plan.off.length;
    if (box.hidden) return;
    const names = plan.off.map(n => n.name);
    $('gridWarningText').textContent = `${plural(names.length, 'piece')} off the tile grid: ${names.slice(0, 3).join(', ')}`
      + `${names.length > 3 ? ' …' : ''}`;
    const why = builder.kept.length ? 'Some pieces could not be read: align once they can, so they move too.'
      : plan.turned ? `${plan.turned.map(n => n.name).join(', ')} ${plan.turned.length === 1 ? 'is' : 'are'} turned off quarter turns or tilted: turn ${plan.turned.length === 1 ? 'it' : 'them'} first (Show selects ${plan.turned.length === 1 ? 'it' : 'them'}).`
      : plan.clash ? 'No single shift puts them all on the grid: move them apart from each other first (Show selects them).'
      : `Align to grid moves the whole prefab ${shiftWords(plan.delta)}, the nearest place where they all are.`;
    box.title = 'Doors, ladders, cars, vans and fracturing pieces keep to the tile grid: whole tiles (96) and levels (64) from '
      + 'where their originals stand. Off it they build where they stand, and the Build and Test in game say so. ' + why;
    $('gridAlign').disabled = !plan.delta || builder.kept.length > 0;
    $('gridAlign').title = plan.delta && !builder.kept.length ? `Moves everything ${shiftWords(plan.delta)} as one: one undo step` : why;
  }
  $('gridAlign').onclick = () => { alignToGrid(); };
  $('gridShow').onclick = () => {
    const plan = gridAlignment(), ids = (plan.turned ?? plan.off).map(n => n.id);
    if (!ids.length) return;
    gizmo.setSelection(ids, ids[0]); editChanged(); frame(roots.get(ids[0]));
  };
  const builderGround = new THREE.Group(); world.add(builderGround);
  let builderGroundKey = '';
  function refreshBuilder() {
    if (!builderMode || builder.loading || !data) return;
    const records = builderRecords(), { size } = records, b = size.bounds;
    $('prefabRecover').hidden = !records.pieces.some(p => p.from && !p.kind);
    $('prefabRecover').disabled = builder.repairing;
    $('builderSize').textContent = `${size.tiles[0]} × ${size.tiles[1]} tiles · height ${b[2].toFixed(0)}–${b[5].toFixed(0)}, grid 0–${PREFAB_GRID_TOP}`
      + (size.warnings.length ? ' · larger than a map holds' : size.unknown.length ? ' · size unverified: missing pieces kept'
        : size.outside.length ? ' · sticks out of the grid' : '');
    $('builderSize').title = [...size.warnings.map(w => `${w}. It is saved and placed all the same.`),
      `A map is at most ${PREFAB_TILES} by ${PREFAB_TILES} tiles; the tile grid is 0 to ${PREFAB_GRID_TOP} units high (${PREFAB_GRID_LEVELS} levels), `
      + `and anything may stick out to ${PREFAB_MIN_Z} under it and ${PREFAB_MAX_Z} over it, roofs and floor boxes `
      + 'included. Out of the grid there are no tiles: nothing can be stood on there or give cover.',
      size.outside.length ? `Out of the grid: ${size.outside.slice(0, 8).join(', ')}${size.outside.length > 8 ? ' …' : ''}.` : ''].filter(Boolean).join('\n');
    $('builderSize').classList.toggle('warn', size.warnings.length > 0 || !size.verified);
    gridWarning();
    const lo = [0, 1].map(k => Math.floor((Math.min(-576, b[k], controls.target[k ? 'z' : 'x'] - 576) - 192) / TILE) * TILE);
    const hi = [0, 1].map(k => Math.ceil((Math.max(576, b[k + 3], controls.target[k ? 'z' : 'x'] + 576) + 192) / TILE) * TILE);
    const key = [...lo, ...hi, ...size.origin, ...size.tiles, size.warnings.length].join(',');
    if (key === builderGroundKey) return;
    builderGroundKey = key;
    for (const child of [...builderGround.children]) { child.geometry.dispose(); child.material.dispose(); builderGround.remove(child); }
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(hi[0] - lo[0], hi[1] - lo[1]).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0x778c91, transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide }));
    plane.position.set((hi[0] + lo[0]) / 2, -0.2, (hi[1] + lo[1]) / 2); builderGround.add(plane);
    const lines = [], line = (x, y, X, Y) => lines.push(x, 0, y, X, 0, Y);
    // Bound drawing cost even when repairing a very large legacy prefab.
    const step = Math.max(TILE, Math.ceil(Math.max(hi[0] - lo[0], hi[1] - lo[1]) / (256 * TILE)) * TILE);
    for (let x = lo[0]; x <= hi[0]; x += step) line(x, lo[1], x, hi[1]);
    for (let y = lo[1]; y <= hi[1]; y += step) line(lo[0], y, hi[0], y);
    builderGround.add(new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(lines, 3)),
      new THREE.LineBasicMaterial({ color: 0x91a9ac, transparent: true, opacity: 0.14 })));
    const [x, y] = size.origin, [nx, ny] = size.tiles;
    const outline = [x, 0.4, y, x + nx * TILE, 0.4, y, x + nx * TILE, 0.4, y + ny * TILE, x, 0.4, y + ny * TILE, x, 0.4, y];
    builderGround.add(new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(outline, 3)),
      new THREE.LineBasicMaterial({ color: size.warnings.length ? 0xef9979 : 0x82d5ce })));
    for (const child of builderGround.children) child.raycast = () => {};
  }
  async function applyPrefabDocument(doc, { envelope = null, nextSerial = 0 } = {}, progress = null) {
    builder.loading = true;
    builder.metadata = new Map(doc.pieces.map(p => [p.actor, structuredClone(p)]));
    for (const d of doc.donors ?? []) if (d.sha256) donorHashes.set(d.package.toLowerCase(), d.sha256);
    // Reserve names and link serials even when none of their pieces can be displayed.
    for (const p of doc.pieces) for (const s of [/_copy(\d+)$/.exec(p.actor)?.[1], /^copy(\d+):/.exec(p.prefab ?? '')?.[1]]) nextSerial = Math.max(nextSerial, Number(s) || 0);
    builder.kept = doc.pieces;
    let carried;
    // (loading ends whatever happens: a failed open never leaves the builder thinking it is still reading)
    try { carried = await applyState({ overrides: [], added: doc.pieces.map(p => ({ ...p, id: p.actor })), groups: doc.groups ?? [], buildings: doc.buildings ?? [], nextSerial }, progress); }
    finally { builder.loading = false; }
    builder.kept = carried.added.map(({ id, ...p }) => p);
    builder.envelope = builder.kept.length ? envelope ?? [0, 0, 0, doc.floor.tiles[0] * TILE, doc.floor.tiles[1] * TILE, 0] : null;
    refreshBuilder(); editChanged();
  }
  // The page dressed as the prefab builder's as its scene opens (app.js's startScene).
  function builderPage() {
    document.body.classList.add('prefab-builder');
    $('builderSize').hidden = false;
    $('prefabTest').hidden = false;
    $('projectButton').querySelector('small').textContent = 'Prefab';
    $('projectMenu').querySelector('h3').textContent = 'Prefab';
    $('projectButton').title = 'Prefab: Save and Open';
    $('mapButton').querySelector('small').textContent = 'Prefab';
    $('mapButton').title = 'Open a map or prefab (M)';
    $('projectLoad').querySelector('span').textContent = 'Open…';
    const loadProjectButton = text($('projectLoad').parentElement, 'button', 'Load project…');
    loadProjectButton.type = 'button'; loadProjectButton.onclick = () => showFileDialog('load');
  }
  async function openPrefabDocument(id) {
    // the loading overlay while a saved prefab is read and its pieces made (those of other maps are read from them)
    if (id !== 'new') { $('loading').hidden = false; loadingState('Opening the prefab…'); }
    try {
      builder.doc = id === 'new' ? newPrefab(uuid(), 'Untitled prefab', { tiles: [1, 1], pieces: [], groups: [], buildings: [], donors: [] }) : await prefabApi.load(id);
      if (id !== 'new') loadingState(`Opening ${builder.doc.name}: reading its ${plural(builder.doc.pieces.length, 'piece')}…`, 0);
      await applyPrefabDocument(builder.doc, {}, openingProgress(builder.doc.name));
    } finally { $('loading').hidden = true; }
    builder.savedKey = builderKey();
    Object.assign(problems, { result: null, error: null, key: null, open: false });
    builderTitle(); frame(); editChanged();     // (the status was drawn while loading, before the saved state was known)
    if (id === 'new') return;
    checkPrefab();
    const recovery = await prefabApi.recovery(id).catch(() => null);
    const missing = builder.kept.length;
    if (recovery?.document) banner(`Unsaved changes to ${builder.doc.name} from ${savedWhen(recovery.savedAt)} were kept.` +
      draftWords(recovery, builder.doc.revision) +
      (missing ? ` The saved version has ${plural(missing, 'missing piece')}. Choose which version to open before looking for sources.` : ''), [
      ['Restore them', async () => {
        builder.doc.donors = recovery.document.donors;
        await applyPrefabDocument(recovery.document, recovery);
        setAdoptedDraft({ owner: recovery.owner, savedAt: recovery.savedAt });
        setRecoveryKept(true); projectChanged();
        await recoverOpenedPrefabSources();
      }],
      ['Discard them', async () => { await discardDraft(prefabApi, id, recovery); await recoverOpenedPrefabSources(); }],
    ]);
    else await recoverOpenedPrefabSources();
  }

  function prefabSourceNotice(repaired, unresolved = [], error = '') {
    const missing = new Map(builder.kept.map(p => [p.actor, p.from && !p.recipe ? 'No recipe was saved.' : 'Could not load its source.']));
    for (const p of unresolved) missing.set(p.actor, p.reason);
    const messages = [];
    if (repaired) messages.push(`Recovered ${plural(repaired, 'piece')} by recipe. Save to keep the new sources.`);
    if (error) messages.push(`Could not look up prefab sources: ${error}`);
    if (missing.size) {
      const names = [...missing].slice(0, 3).map(([actor, reason]) => `${short(actor)}: ${reason}`);
      messages.push(`${plural(missing.size, 'piece')} still missing. ${names.join(' ')}${missing.size > names.length ? ` And ${missing.size - names.length} more.` : ''}`);
    }
    banner(messages.join(' ') || 'All prefab sources are available.');
  }

  async function recoverOpenedPrefabSources() {
    if (!builder.kept.length) return;
    if (builder.kept.some(p => p.from && p.recipe)) await recoverPrefabSources();
    else prefabSourceNotice(0);
  }

  async function recoverPrefabSources() {
    if (!builderMode || builder.loading || builder.repairing || saving || gizmo.controls.dragging) return;
    const before = builderKey(), doc = builderDocument();
    builder.repairing = $('prefabRecover').disabled = true;
    flashHint('Looking for the missing pieces in the map catalogue…');
    try {
      const result = await prefabApi.recoverSources(doc);
      const repaired = new Set(result.repaired);
      if (!repaired.size) {
        prefabSourceNotice(0, result.unresolved);
        return;
      }
      const replacements = result.document.pieces.filter(p => repaired.has(p.actor));
      const hashes = new Map(result.document.donors.map(d => [d.package.toLowerCase(), d.sha256]));
      const made = await Promise.all(replacements.flatMap(p => p.components.map(async component => {
        const { record } = await libraryTemplate(p.from);
        if (record.source.sha256 !== hashes.get(p.from.package.toLowerCase()))
          throw Error('The game package changed while this prefab was open. Reopen the prefab and try again.');
        const source = templateFor(p.from, component);
        if (!source) throw Error(`Could not load ${short(p.actor)} from ${p.from.package}.`);
        return buildRoot(addedObject(source, movedMatrix(source, p.location, p.rotation), { ...p, entity: p.actor }));
      })));
      if (before !== builderKey() || saving || gizmo.controls.dragging) throw Error('The prefab changed during the search. Try again.');
      const old = [...roots.values()].filter(r => repaired.has(r.userData.source.actor));
      const picks = gizmo.picks(), removed = new Set(old.map(r => r.userData.source.id));
      const kept = builder.kept, envelope = builder.envelope, metadata = builder.metadata, donors = builder.doc.donors;
      const remaining = kept.filter(p => !repaired.has(p.actor));
      const updated = new Map(metadata);
      for (const p of replacements) updated.set(p.actor, p);
      gizmo.record({
        redo() {
          removeRoots(old); addRoots(made);
          Object.assign(builder, { kept: remaining, envelope: remaining.length ? envelope : null, metadata: updated });
          builder.doc.donors = result.document.donors;
          gizmo.setSelection(picks.ids.filter(id => !removed.has(id)), removed.has(picks.active) ? null : picks.active);
          sceneChanged();
        },
        undo() {
          removeRoots(made); addRoots(old);
          Object.assign(builder, { kept, envelope, metadata });
          builder.doc.donors = donors;
          gizmo.setSelection(picks.ids, picks.active);
          sceneChanged();
        },
      });
      prefabSourceNotice(repaired.size, result.unresolved);
    } catch (error) {
      prefabSourceNotice(0, [], error.message);
    } finally {
      builder.repairing = false;
      refreshBuilder();
    }
  }

  function builderTitle() {
    $('projectTitle').textContent = builder.doc?.name ?? 'Untitled prefab';
    $('mapTitle').textContent = builder.doc?.name ?? 'New prefab';
    document.title = `${builder.doc?.name ?? 'New prefab'} · Prefab · XCOM Map Workshop`;
    $('projectButton').classList.toggle('unsaved', dirty());
  }
  async function saveBuilder({ name = null, replace = null } = {}) {
    if (saving || builder.loading || gizmo.controls.dragging) return false;
    if (!name && !builder.doc.revision) return showPrefabDialog(true);
    setSaving(true); clearTimeout(recoveryTimer);
    try {
      await documentWrites.wait();
      const records = prefabRecords({ complete: true }), before = builderKey(), previous = builder.doc.id;
      if (!records.pieces.length && !records.buildings.length) throw Error('The prefab is empty. Add a piece, light or floor box first.');
      if (!records.size.supported) throw Error(records.size.errors.join('; '));
      const target = name ? replace : builder.doc, id = target?.id ?? uuid();
      const doc = newPrefab(id, name ?? builder.doc.name, records);
      if (target?.created) doc.created = target.created;
      else if (replace) doc.created = (await prefabApi.load(id)).created;
      const result = await prefabApi.save(id, doc, target?.revision ?? 0, { owner: SESSION });
      // (the server dropped this page's draft of `id`; saved as another prefab, its draft of the one open before goes,
      // and a draft restored into it: what they held is saved now)
      if (previous !== id) documentWrites.run(() => prefabApi.dropRecovery(previous, SESSION)).catch(() => {});
      dropAdopted(prefabApi, previous);
      const withRecipes = list => list.map(p => result.recipes?.[p.actor] ? { ...p, recipe: result.recipes[p.actor] } : p);
      const baseline = JSON.parse(before);
      baseline.pieces = withRecipes(baseline.pieces);
      builder.doc = { ...doc, pieces: withRecipes(doc.pieces), revision: result.revision, created: result.created, savedAt: result.savedAt };
      builder.savedKey = JSON.stringify(baseline); setRecoveryKept(false); setRecoveryTrouble(null);
      setTimeout(checkPrefab, 0);
      builder.metadata = new Map(withRecipes(records.pieces).map(p => [p.actor, structuredClone(p)]));
      history.replaceState(null, '', `?prefab=${encodeURIComponent(id)}`);
      prefabPictures.push({ id, entries: records.clip.entries, volumes: records.clip.volumes, box: records.box });
      prefabTab.refresh(); builderTitle();
      flashHint(`Saved ${doc.name} · revision ${result.revision}${!result.size?.verified ? ' · size unverified: missing pieces kept' : ''}`);
      return true;
    } catch (error) {
      if (error.status === 409 && Number.isInteger(error.body?.revision) && !name) {
        setRecoveryTrouble('stale');      // (told here: the drafts kept meanwhile say nothing more of it)
        banner(`${builder.doc.name} was saved elsewhere (revision ${error.body.revision}).`, [
          ['Overwrite it with this', () => { builder.doc.revision = error.body.revision; saveBuilder(); }],
          ['Open the saved one', () => discardAndGo({ prefab: builder.doc.id })],
        ]);
      }
      else banner(`Not saved: ${error.message}`);
      return false;
    } finally { setSaving(false); projectChanged(); }
  }
  // The builder's Problems check (plan "sturdier prefabs", R5): what a test of the prefab as it stands would say,
  // asked of the server without building anything (POST /prefab-tests/check: the test's prepare step). The chip under
  // the size line counts the pieces that would be left out and the warnings; it opens the list, where a row selects
  // and frames its piece. Checked when a prefab is opened and saved, and on demand; after an edit the chip says the
  // list is from before it.
  const problems = { result: null, key: null, running: false, error: null, open: false };
  async function checkPrefab() {
    if (!builderMode || builder.loading || problems.running) return;
    const doc = builderDocument(), key = builderKey();
    if (!doc.pieces.length && !doc.buildings.length) { Object.assign(problems, { result: null, error: null, key }); problemsPaint(); return; }
    problems.running = true; problemsPaint();
    try {
      const value = await call('POST', '/prefab-tests/check', { snapshot: doc }, { fallback: r => `the server said ${r.status}` });
      Object.assign(problems, { result: value, error: null, key });
    } catch (error) { Object.assign(problems, { result: null, error: error.message, key }); }
    finally { problems.running = false; problemsPaint(); }
  }
  function problemsPaint(stale = Boolean(problems.result) && builderMode && !builder.loading && problems.key !== builderKey()) {
    const box = $('builderProblems'), chip = $('problemsChip'), list = $('problemsList'), r = problems.result;
    box.hidden = !builderMode || builder.loading;
    if (box.hidden) return;
    const issues = r?.issues ?? [], gone = r?.leftOut ?? 0, warnings = issues.length - gone;
    chip.textContent = problems.running ? 'Checking…' : problems.error ? 'Not checked' : !r ? 'Check for problems'
      : !r.ready ? 'Not checked yet' : r.refused ? 'Can\'t be tested'
      : (gone || warnings ? [gone && `${gone} left out`, warnings && plural(warnings, 'warning')].filter(Boolean).join(' · ') : 'No problems')
        + (stale ? ' (before the last edit)' : '');
    chip.classList.toggle('warn', Boolean(gone || r?.refused || problems.error));
    chip.title = problems.error ? `The check could not be run: ${problems.error}. Click to try again.`
      : !r ? 'What Test in game would say of this prefab, without building it: the pieces it would leave out and its warnings'
      : !r.ready ? r.message : `${r.refused ? `${r.refused} ` : ''}Click to ${problems.open ? 'close' : 'open'} the list${stale ? '; it is from before the last edit: Check again in the list brings it up to date' : ''}.`;
    list.hidden = !problems.open || !r?.ready;
    list.replaceChildren();
    if (list.hidden) return;
    const again = text(list, 'li', '', 'again'), button = text(again, 'button', problems.running ? 'Checking…' : 'Check again');
    button.type = 'button'; button.disabled = problems.running; button.onclick = () => checkPrefab();
    if (r.stage) text(again, 'small', ` test stage ${r.stage[0]} × ${r.stage[1]} tiles, ${r.stage[2]} levels`);
    if (r.refused) text(list, 'li', r.refused, 'leftout');
    for (const issue of issues.slice(0, 200)) {
      const li = text(list, 'li', issue.actor && !issue.leftOut ? `${short(issue.actor)} · ${issue.message}` : issue.message, issue.leftOut ? 'leftout' : '');
      if (issue.actor) { li.classList.add('pick'); li.title = `Select ${short(issue.actor)}`; li.onclick = () => selectActors([issue.actor]); }
    }
    if (issues.length > 200) text(list, 'li', `… and ${issues.length - 200} more`);
    if (!issues.length && !r.refused) text(list, 'li', 'Nothing would be left out, and the compiler has no warning.');
  }
  $('problemsChip').onclick = () => {
    if (!problems.result?.ready || problems.error) { checkPrefab(); return; }
    problems.open = !problems.open; problemsPaint();
  };

  return { applyPrefabDocument, builderBounds, builderDocument, builderKey, builderPage, builderRecords, builderTitle,
           openPrefabDocument, physicalBox, problemsPaint, recoverPrefabSources, refreshBuilder, saveBuilder };
}
