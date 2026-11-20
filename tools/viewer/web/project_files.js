// The Save and Load dialogs: a classic file picker over the projects folder, which the viewer's server keeps with one
// file per project, named after it (tools/viewer/projects.py). Load lists every project; Save lists this map's, with a name box. In
// Save a new name makes a new project, the open project's own name saves its next revision, and another project's
// name replaces that project after a confirm. Under the name box Save shows what the project builds as: a new
// project's map name, from the server (the project name as one word, at most 24 characters, numbered when taken), or
// the fixed one of the project saved onto. The caller does the opening and saving (document_session.js).
const byName = (a, b) => (a.name ?? '').localeCompare(b.name ?? '', undefined, { sensitivity: 'base' });
const SORTS = {
  name: byName,
  map: (a, b) => (a.map ?? '').localeCompare(b.map ?? '') || byName(a, b),
  revision: (a, b) => (a.revision ?? 0) - (b.revision ?? 0) || byName(a, b),
  savedAt: (a, b) => (a.savedAt ?? '').localeCompare(b.savedAt ?? '') || byName(a, b),
};
const same = (a, b) => a.trim().toLocaleLowerCase() === b.trim().toLocaleLowerCase();
export const savedWhen = iso => iso ? new Date(iso).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : '';

/**
 * els: the dialog's elements (root, form, title, folder, head, list, show, name, ok, cancel, close, confirm, message,
 * output). api: list() → { folder, projects }; names(name, map, target) → what saving under that name builds as (the
 * server's: output names plan). mapLabel(id): a map's display name.
 * onLoad(summary): open that project. onSave({ name, target, output }): target is the project summary to save onto, or
 * null for a new project, which gets `output`, the map name the dialog showed. A save the server refuses because that
 * name was taken meanwhile throws with detail.proposal: the dialog stays open and shows the name it would get now.
 */
export function createProjectDialog({ els, api, mapLabel, onLoad, onSave }) {
  let mode = 'load', context = {}, projects = [], chosen = null, sort = { key: 'savedAt', down: true };
  let lastFocus = null;
  let completion = null;
  // The map name shown (output names plan 3.3): the server's answer for a name and the project it saves onto
  // ({ key, result } or { key, error }); asked again as the name changes, an answer for an older name thrown away.
  // Save waits for the answer for what is typed now.
  let preview = null, asked = 0, previewTimer = null;
  // A save that fails leaves the dialog open, and whoever waits for it (a map or prefab change) waits on: the next
  // Save that succeeds goes on with it, Cancel calls it off (review finding 34).
  async function saveAndClose(request) {
    els.ok.disabled = true;
    try { const saved = await onSave(request); close(Boolean(saved)); }
    catch (error) {
      // the project replaced was saved again since the question showed it (review finding 4): asked again, with
      // its revision now
      if (request.target && error.status === 409 && Number.isInteger(error.body?.revision)) {
        await refresh();
        const fresh = projects.find(p => p.id === request.target.id && !p.error);
        if (fresh) {
          confirmReplace(fresh, request.name, `It was saved again meanwhile, from another window or tab.`);
          return;
        }
      }
      say(`Not saved: ${error.message}`);
      // the name shown was taken meanwhile: the one it would get now, for the next Save
      const proposal = error.body?.proposal;
      if (proposal?.output && !request.target) { preview = { key: previewKey(), result: { fresh: true, notes: [], conflicts: [], ...proposal } }; showOutput(); }
    }
    finally { update(); }
  }
  const targetFor = name => (chosen && same(chosen.name ?? '', name) ? chosen : shown().find(p => same(p.name ?? '', name)) ?? null);
  // what the preview depends on: the name as typed and the project it would save onto (the open one keeps its own),
  // known once the projects are listed
  let listed = false;
  function previewKey() {
    const name = els.name.value.trim(), target = name ? targetFor(name) : null;
    return `${name}\n${target?.id ?? ''}`;
  }
  function askPreview(soon = false) {
    if (mode !== 'save' || !api.names || !listed) return;
    clearTimeout(previewTimer);
    const key = previewKey(), name = els.name.value.trim();
    if (preview?.key === key) { showOutput(); return; }
    preview = null; showOutput();
    if (!name) return;
    previewTimer = setTimeout(async () => {
      const mine = ++asked, target = targetFor(name);
      try {
        const result = await api.names(name, context.mapId, target?.id ?? null);
        if (mine === asked && key === previewKey()) preview = { key, result };
      } catch (error) {
        if (mine === asked && key === previewKey()) preview = { key, error: error.message };
      }
      if (mine === asked) { showOutput(); update(); }
    }, soon ? 0 : 200);
  }
  function showOutput() {
    const box = els.output;
    if (!box) return;
    box.replaceChildren(); box.classList.remove('pending', 'warn');
    box.hidden = mode !== 'save' || !els.name.value.trim();
    if (box.hidden) return;
    const add = (text, cls, tag = 'span') => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; box.append(el); return el; };
    const current = preview?.key === previewKey() ? preview : null;
    if (!current) { box.classList.add('pending'); box.append('Builds as '); add('…', null, 'b'); return; }
    if (current.error) { box.classList.add('warn'); box.textContent = `The map name can't be worked out: ${current.error}`; return; }
    const r = current.result;
    if (!r.output) { box.classList.add('warn'); box.textContent = 'This project has no map name: Save as under a new name to give it one.'; return; }
    box.append('Builds as '); add(r.output.shipAs, null, 'b');
    box.append(r.fresh ? ` · map names keep to ${r.limit ?? 24} characters` : ' · fixed when the project was first saved');
    if (r.reason) add(`${r.reason[0].toUpperCase()}${r.reason.slice(1)}.`, 'why');
    for (const note of r.conflicts ?? []) add(`Taken elsewhere too: ${note}. Save as under a new name before building.`, 'why warn');
    for (const note of r.notes ?? []) add(`${note[0].toUpperCase()}${note.slice(1)}.`, 'why');
  }
  const previewReady = () => { const p = preview?.key === previewKey() ? preview : null; return Boolean(p?.result?.output); };
  const enabled = () => [...els.list.querySelectorAll('.filerow:not(:disabled)')];
  const shown = () => projects.filter(p => mode === 'load' ? els.show.value === 'all' || p.map === context.mapId : !p.error && p.map === context.mapId);

  function say(message) { els.message.textContent = message ?? ''; els.message.hidden = !message; }
  function choose(id, fill = true, focus = false) {
    chosen = projects.find(p => p.id === id) ?? null;
    for (const row of els.list.querySelectorAll('.filerow')) {
      const on = row.dataset.id === chosen?.id;
      row.classList.toggle('on', on); row.setAttribute('aria-selected', on);
      if (on) { row.scrollIntoView({ block: 'nearest' }); if (focus) row.focus(); }
    }
    if (chosen && fill) els.name.value = chosen.name ?? '';
    hideConfirm(); say(null); askPreview(true); update();
  }
  function update() {
    els.ok.disabled = mode === 'load' ? !chosen : !els.name.value.trim() || (Boolean(api.names) && !previewReady());
  }
  function render() {
    els.list.replaceChildren();
    for (const button of els.head.querySelectorAll('[data-sort]')) {
      button.classList.toggle('sorted', button.dataset.sort === sort.key);
      button.classList.toggle('down', button.dataset.sort === sort.key && sort.down);
    }
    const list = shown().sort((a, b) => (sort.down ? -1 : 1) * SORTS[sort.key](a, b));
    for (const p of list) {
      const row = document.createElement('button');
      Object.assign(row, { type: 'button', className: 'filerow' });
      row.dataset.id = p.id; row.setAttribute('role', 'option');
      const name = document.createElement('span'); name.className = 'fname';
      name.append(p.error ? p.id : (p.name ?? p.id));
      const tag = (label, title) => {
        const el = document.createElement('small'); el.textContent = label; el.title = title; name.append(el);
      };
      if (p.id === context.current) tag('open', 'The project open now');
      if (p.recovery) tag('unsaved changes kept', 'Opening it offers back changes that were never saved');
      const cells = [name, p.error ? 'unreadable' : mapLabel(p.map), p.error ? '' : String(p.revision ?? ''), savedWhen(p.savedAt)];
      for (const cell of cells) {
        if (typeof cell === 'string') { const el = document.createElement('span'); el.textContent = cell; row.append(el); }
        else row.append(cell);
      }
      row.title = p.error ? `${p.file ?? p.id}: ${p.error}`
        : `${p.name} · ${mapLabel(p.map)} · revision ${p.revision} · saved ${savedWhen(p.savedAt)}${p.file ? ` · ${p.file}` : ''}`;
      row.disabled = Boolean(p.error);
      row.onclick = () => choose(p.id);
      row.ondblclick = () => { choose(p.id); submit(); };
      els.list.append(row);
    }
    if (!list.length) {
      const empty = document.createElement('div'); empty.className = 'empty';
      empty.textContent = mode === 'save' ? 'No projects for this map yet: type a name to make one.'
        : els.show.value === 'all' ? 'No projects yet.' : 'No projects for this map. Show all maps to see the others.';
      els.list.append(empty);
    }
    if (chosen && !list.includes(chosen)) chosen = null;
    choose(chosen?.id, false);
  }
  async function refresh() {
    els.list.replaceChildren(Object.assign(document.createElement('div'), { className: 'empty', textContent: 'Reading the projects folder…' }));
    try {
      const found = await api.list();
      els.folder.textContent = found.folder; els.folder.title = found.folder;
      projects = found.projects;
    } catch (e) {
      projects = [];
      els.list.replaceChildren(Object.assign(document.createElement('div'), { className: 'empty', textContent: `The projects could not be listed: ${e.message}` }));
      listed = true; askPreview(true); update();
      return;
    }
    listed = true;
    render();
    // Load starts on the open project, or else the newest; Save on the name it was given.
    if (mode === 'load') choose((projects.find(p => p.id === context.current && !p.error) ?? enabled()[0]?.dataset)?.id ?? null, true);
    else matchName();
    if (document.activeElement !== els.name) { els.name.focus(); els.name.select(); }
  }
  // Typing a name: Save picks the project of that name, if there is one; Load goes to the first name that starts so.
  function matchName() {
    const typed = els.name.value.trim().toLocaleLowerCase(), visible = shown();
    let match = null;
    if (typed) {
      if (mode === 'save') match = (chosen && same(chosen.name ?? '', typed) ? chosen : null) ?? visible.find(p => same(p.name ?? '', typed));
      else match = visible.find(p => !p.error && (p.name ?? '').toLocaleLowerCase().startsWith(typed))
        ?? visible.find(p => !p.error && (p.name ?? '').toLocaleLowerCase().includes(typed));
    }
    choose(match?.id ?? null, false);
  }
  function hideConfirm() { els.confirm.hidden = true; els.confirm.replaceChildren(); }
  // Replace saves over the revision shown here and no other (document_session.js's saveProject takes target.revision
  // as the one expected).
  function confirmReplace(target, name, note = null) {
    els.confirm.replaceChildren();
    const message = document.createElement('div');
    message.textContent = `${note ? `${note} ` : ''}“${target.name}” already exists (revision ${target.revision}, saved ${savedWhen(target.savedAt)}). `
      + 'Replace it with what is on screen? It keeps its map name, and its revision before is kept as a backup.';
    const yes = document.createElement('button'), no = document.createElement('button');
    Object.assign(yes, { type: 'button', textContent: 'Replace', className: 'primary' });
    Object.assign(no, { type: 'button', textContent: "Don't replace" });
    yes.onclick = () => { hideConfirm(); saveAndClose({ name, target, output: null }); };
    no.onclick = () => { hideConfirm(); els.name.focus(); };
    els.confirm.append(message, yes, no);
    els.confirm.hidden = false;
    yes.focus();
  }
  function submit() {
    if (mode === 'load') {
      if (!chosen) { say(els.name.value.trim() ? `No project is called “${els.name.value.trim()}”.` : 'Choose a project to load.'); return; }
      const picked = chosen;
      close();
      if (picked.id !== context.current) onLoad(picked);
      return;
    }
    const name = els.name.value.trim();
    if (!name) { say('Type a name for the project.'); return; }
    if (name.length > 120) { say('A project name has at most 120 characters.'); return; }
    // the map name shown must be the one for what is typed now
    if (api.names && !previewReady()) { say(preview?.error ? `Not saved: ${preview.error}` : 'Working out the map name…'); askPreview(true); return; }
    const target = targetFor(name);
    if (target && target.id !== context.current) { confirmReplace(target, name); return; }
    saveAndClose({ name, target, output: target ? null : preview?.result?.output ?? null });
  }
  function move(step) {
    const rows = enabled();
    if (!rows.length) return;
    const at = rows.findIndex(r => r.dataset.id === chosen?.id);
    const next = rows[Math.max(0, Math.min(rows.length - 1, at < 0 ? (step > 0 ? 0 : rows.length - 1) : at + step))];
    choose(next.dataset.id, true);
  }

  els.form.addEventListener('submit', e => { e.preventDefault(); submit(); });
  els.name.addEventListener('input', () => { hideConfirm(); say(null); matchName(); askPreview(); update(); });
  els.show.addEventListener('change', render);
  els.cancel.onclick = () => close();
  els.close.onclick = () => close();
  for (const button of els.head.querySelectorAll('[data-sort]')) {
    button.onclick = () => {
      const key = button.dataset.sort;
      sort = sort.key === key ? { key, down: !sort.down } : { key, down: key === 'savedAt' || key === 'revision' };
      render();
    };
  }
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open. (Tab goes round its
  // controls as in every dialog: modal.js)
  els.root.addEventListener('keydown', e => {
    const key = e.key;
    if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f'].includes(key.toLowerCase())) e.preventDefault();
    else if (key === 'Escape') { e.preventDefault(); if (!els.confirm.hidden) { hideConfirm(); els.name.focus(); } else close(); }
    else if (key === 'ArrowDown' || key === 'ArrowUp') { e.preventDefault(); move(key === 'ArrowDown' ? 1 : -1); }
    else if (key === 'Enter' && e.target.closest('.filerow')) { e.preventDefault(); submit(); }
    e.stopPropagation();
  });

  function show(which, given) {
    mode = which; context = given; chosen = null;
    const saving = mode === 'save';
    els.title.textContent = saving ? 'Save project' : 'Open project';
    els.ok.textContent = saving ? 'Save' : 'Open';
    els.show.value = saving ? 'map' : 'all';
    els.show.disabled = saving;
    els.show.title = saving ? 'A project belongs to one map: saving lists this map\'s projects' : '';
    els.show.options[0].textContent = `This map (${mapLabel(context.mapId)})`;
    els.name.value = context.name ?? '';
    els.name.placeholder = saving ? 'Name of the project' : 'Type to find a project';
    hideConfirm(); say(null);
    preview = null; listed = false; clearTimeout(previewTimer); showOutput();
    lastFocus = document.activeElement;
    els.root.hidden = false;
    els.name.focus(); els.name.select();
    update();
    if (context.waitForSave) { refresh(); return new Promise(resolve => { completion = resolve; }); }
    return refresh();
  }
  function close(saved = false) {
    if (els.root.hidden) return;
    els.root.hidden = true; hideConfirm();
    clearTimeout(previewTimer); asked++;
    completion?.(saved); completion = null;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, get open() { return !els.root.hidden; }, get mode() { return mode; } };
}
