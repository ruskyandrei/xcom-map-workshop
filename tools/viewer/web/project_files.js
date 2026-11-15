// The Save and Load dialogs: a classic file picker over the projects folder, which the viewer's server keeps with one
// file per project, named after it (tools/viewer/projects.py). Load lists every project; Save lists this map's, with a name box. In
// Save a new name makes a new project, the open project's own name saves its next revision, and another project's
// name replaces that project after a confirm. The caller does the opening and saving (app.js).
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
 * els: the dialog's elements (root, form, title, folder, head, list, show, name, ok, cancel, close, confirm, message).
 * api: list() → { folder, projects }. mapLabel(id): a map's display name.
 * onLoad(summary): open that project. onSave({ name, target }): target is the project summary to save onto, or null
 * for a new project.
 */
export function createProjectDialog({ els, api, mapLabel, onLoad, onSave }) {
  let mode = 'load', context = {}, projects = [], chosen = null, sort = { key: 'savedAt', down: true };
  let lastFocus = null;
  let completion = null;
  async function saveAndClose(request) {
    els.ok.disabled = true;
    try { const saved = await onSave(request); close(Boolean(saved)); }
    catch (error) { say(`Not saved: ${error.message}`); completion?.(false); completion = null; }
    finally { update(); }
  }
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
    hideConfirm(); say(null); update();
  }
  function update() {
    els.ok.disabled = mode === 'load' ? !chosen : !els.name.value.trim();
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
      const listed = await api.list();
      els.folder.textContent = listed.folder; els.folder.title = listed.folder;
      projects = listed.projects;
    } catch (e) {
      projects = [];
      els.list.replaceChildren(Object.assign(document.createElement('div'), { className: 'empty', textContent: `The projects could not be listed: ${e.message}` }));
      return;
    }
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
  function confirmReplace(target, name) {
    els.confirm.replaceChildren();
    const message = document.createElement('div');
    message.textContent = `“${target.name}” already exists (revision ${target.revision}, saved ${savedWhen(target.savedAt)}). `
      + 'Replace it with what is on screen? It keeps its output names, and its revision before is kept as a backup.';
    const yes = document.createElement('button'), no = document.createElement('button');
    Object.assign(yes, { type: 'button', textContent: 'Replace', className: 'primary' });
    Object.assign(no, { type: 'button', textContent: "Don't replace" });
    yes.onclick = () => { hideConfirm(); saveAndClose({ name, target }); };
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
    const target = chosen && same(chosen.name ?? '', name) ? chosen : shown().find(p => same(p.name ?? '', name)) ?? null;
    if (target && target.id !== context.current) { confirmReplace(target, name); return; }
    saveAndClose({ name, target });
  }
  function move(step) {
    const rows = enabled();
    if (!rows.length) return;
    const at = rows.findIndex(r => r.dataset.id === chosen?.id);
    const next = rows[Math.max(0, Math.min(rows.length - 1, at < 0 ? (step > 0 ? 0 : rows.length - 1) : at + step))];
    choose(next.dataset.id, true);
  }

  els.form.addEventListener('submit', e => { e.preventDefault(); submit(); });
  els.name.addEventListener('input', () => { hideConfirm(); say(null); matchName(); update(); });
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
  // The dialog keeps its keys: nothing reaches the editor's shortcuts behind it while it is open.
  els.root.addEventListener('keydown', e => {
    const key = e.key;
    if ((e.ctrlKey || e.metaKey) && ['s', 'o', 'f'].includes(key.toLowerCase())) e.preventDefault();
    else if (key === 'Escape') { e.preventDefault(); if (!els.confirm.hidden) { hideConfirm(); els.name.focus(); } else close(); }
    else if (key === 'ArrowDown' || key === 'ArrowUp') { e.preventDefault(); move(key === 'ArrowDown' ? 1 : -1); }
    else if (key === 'Enter' && e.target.closest('.filerow')) { e.preventDefault(); submit(); }
    else if (key === 'Tab') {
      // Focus stays in the dialog.
      const items = [...els.root.querySelectorAll('button:not(:disabled), input, select:not(:disabled)')].filter(el => el.offsetParent);
      const i = items.indexOf(document.activeElement), next = items[(i + (e.shiftKey ? -1 : 1) + items.length) % items.length];
      if (next) { e.preventDefault(); next.focus(); }
    }
    e.stopPropagation();
  });

  function show(which, given) {
    mode = which; context = given; chosen = null;
    const saving = mode === 'save';
    els.title.textContent = saving ? 'Save project' : 'Load project';
    els.ok.textContent = saving ? 'Save' : 'Open';
    els.show.value = saving ? 'map' : 'all';
    els.show.disabled = saving;
    els.show.title = saving ? 'A project belongs to one map: saving lists this map\'s projects' : '';
    els.show.options[0].textContent = `This map (${mapLabel(context.mapId)})`;
    els.name.value = context.name ?? '';
    els.name.placeholder = saving ? 'Name of the project' : 'Type to find a project';
    hideConfirm(); say(null);
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
    completion?.(saved); completion = null;
    if (lastFocus?.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
    else document.activeElement?.blur?.();
  }
  return { show, close, get open() { return !els.root.hidden; }, get mode() { return mode; } };
}
