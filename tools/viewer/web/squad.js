// Test squad setup (Settings menu; tools/viewer/squads.py, squadrecords.py): the one squad every Play in game lands
// with, unit by unit. The panel edits a draft of the saved squad: Save writes it (test-squad.json beside the
// settings), Cancel leaves the saved one as it was, and Import, Reset to default and every edit change only the draft.
// What the install offers (its armours, weapons, items, perks, classes, base stats) comes from the server, read from
// the install Play in game uses; each edit is checked there (POST /squad/check), and the unit list and the lines under
// it say what a play would do with the squad: errors stop a play, warnings don't. A selection that install doesn't
// have stays in the squad, shown as not on this install.

async function call(method, url, body) {
  const response = await fetch(url, { method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(value.error || `The server said ${response.status}`), { status: response.status, value });
  return value;
}
export const squadApi = {
  get: () => call('GET', '/squad.json'),
  save: (expectedRevision, document) => call('PUT', '/squad.json', { expectedRevision, document }),
  check: document => call('POST', '/squad/check', { document }),
  importText: text => call('POST', '/squad/import', { text }),
  exportDocument: document => call('POST', '/squad/export', { document }),
};

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
/** The squad in a few words for the play dialog, from /play.json's `squad`; null when not known. */
export function squadLine(summary) {
  if (!summary) return null;
  if (summary.problem) return { text: 'Squad: its file can\'t be read', warn: true, title: summary.problem };
  const text = `Squad: ${summary.name} · ${plural(summary.units, 'unit')}`;
  if (!summary.playable) return { text: `${text} · can't be played here`, warn: true, title: summary.errors.join('\n') };
  return { text, warn: false, title: summary.warnings ? `${plural(summary.warnings, 'warning')}: Test squad setup lists them` : 'Every Play in game lands with this squad' };
}

const clone = value => JSON.parse(JSON.stringify(value));
const el = (tag, props = {}, ...children) => { const e = Object.assign(document.createElement(tag), props); e.append(...children.filter(c => c != null)); return e; };
const KIND_WORDS = { soldier: 'Soldier', mec: 'MEC trooper', shiv: 'SHIV' };
const SLOT_WORDS = { armour: 'Armour', sidearm: 'Sidearm', weapons: 'Weapons', items: 'Items' };

/**
 * els: root, form, title, intro, problem, name, units, add, copy, remove, up, down, count, unit (the right pane),
 * issues, wide (Show every item), status, exportButton, importButton, importFile, reset, cancel, save, close.
 * onSaved(status): after a save. onClosed(): after the panel closes either way.
 */
export function createSquadDialog({ els, api = squadApi, onSaved = () => {}, onClosed = () => {} }) {
  let status = null, draft = null, check = null, selected = null, dirty = false, lastFocus = null, timer = null;
  let checking = 0, kindNote = null, conflict = false, busy = false;

  const choices = () => status?.choices ?? null;
  const items = () => choices()?.items ?? {};
  const unitOf = id => draft?.units.find(u => u.id === id) ?? null;
  const checkOf = id => check?.units?.find(u => u.id === id) ?? null;
  const label = id => (id == null ? 'None' : items()[id]?.label ?? id);
  const fullName = u => (u.kind === 'shiv' ? u.first : `${u.first} ${u.last}`).trim() || '(no name)';

  function say(text, warn = false) {
    els.status.textContent = text ?? '';
    els.status.classList.toggle('warn', Boolean(warn));
  }
  function changed() {
    dirty = true; conflict = false;
    clearTimeout(timer);
    timer = setTimeout(recheck, 250);
    renderList();
  }
  async function recheck() {
    if (!draft) return;
    const ticket = ++checking;
    try {
      const r = await api.check(draft);
      if (ticket !== checking) return;
      check = r.check;
      renderList(); renderIssues(); renderUnitIssues();
    } catch (e) {
      if (ticket === checking) { check = null; say(`Not checked: ${e.message}`, true); renderIssues(); }
    }
  }
  const newId = () => { let n = draft.units.length + 1; while (draft.units.some(u => u.id === `unit-${n}`)) n += 1; return `unit-${n}`; };

  // ---- the unit list ----
  function renderList() {
    els.units.replaceChildren();
    draft.units.forEach((u, i) => {
      const c = checkOf(u.id), errors = c?.errors?.length ?? 0, warnings = c?.warnings?.length ?? 0;
      const li = el('li', { className: `squadrow${u.id === selected ? ' on' : ''}${errors ? ' bad' : warnings ? ' warn' : ''}`, tabIndex: u.id === selected ? 0 : -1 });
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(u.id === selected));
      li.dataset.id = u.id;
      li.append(el('span', { className: 'squadnum', textContent: `${i + 1}` }),
        el('span', { className: 'squadwho' }, el('strong', { textContent: fullName(u) }),
          el('small', { textContent: c?.summary ?? KIND_WORDS[u.kind] })));
      if (errors || warnings) li.append(el('span', { className: 'squadmark', textContent: errors ? '✕' : '!', title: [...(c.errors ?? []), ...(c.warnings ?? [])].join('\n') }));
      li.onclick = () => { select(u.id); };
      els.units.append(li);
    });
    // (the count and Add go by the same limit, the squad's own; an install that lands fewer is named beside it, and its
    // check says when the squad has more: review finding 34)
    const keep = status?.limits?.units ?? 8, max = choices()?.maxUnits ?? keep;
    els.count.textContent = `${plural(draft.units.length, 'unit')} of at most ${keep}, landing in this order`
      + (max < keep ? `; ${choices().familyLabel ?? 'this install'} lands at most ${max}` : '');
    els.add.disabled = els.copy.disabled = draft.units.length >= keep || busy;
    els.remove.disabled = draft.units.length <= 1 || busy;
    const at = draft.units.findIndex(u => u.id === selected);
    els.up.disabled = at <= 0 || busy;
    els.down.disabled = at < 0 || at >= draft.units.length - 1 || busy;
  }
  function select(id) {
    selected = id; kindNote = null;
    renderList(); renderUnit();
  }
  els.units.addEventListener('keydown', e => {
    if (!draft) return;
    const at = draft.units.findIndex(u => u.id === selected);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const next = draft.units[Math.max(0, Math.min(draft.units.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)))];
      if (next) { select(next.id); els.units.querySelector(`[data-id="${CSS.escape(next.id)}"]`)?.focus(); }
    }
  });
  els.add.onclick = () => {
    if (!draft) return;
    const template = clone(choices()?.templates?.soldier ?? draft.units.at(-1));
    const unit = { ...template, id: newId(), first: 'New', last: `Soldier ${draft.units.length + 1}` };
    draft.units.push(unit); select(unit.id); changed();
  };
  els.copy.onclick = () => {
    const at = draft ? draft.units.findIndex(u => u.id === selected) : -1;
    if (at < 0) return;
    const copy = { ...clone(draft.units[at]), id: newId() };
    draft.units.splice(at + 1, 0, copy); select(copy.id); changed();
  };
  els.remove.onclick = () => {
    const at = draft ? draft.units.findIndex(u => u.id === selected) : -1;
    if (at < 0 || draft.units.length <= 1) return;
    draft.units.splice(at, 1);
    select(draft.units[Math.min(at, draft.units.length - 1)].id); changed();
  };
  const move = step => {
    const at = draft ? draft.units.findIndex(u => u.id === selected) : -1, to = at + step;
    if (at < 0 || to < 0 || to >= draft.units.length) return;
    const [unit] = draft.units.splice(at, 1);
    draft.units.splice(to, 0, unit); changed();
  };
  els.up.onclick = () => move(-1);
  els.down.onclick = () => move(1);
  els.name.oninput = () => { if (draft) { draft.name = els.name.value; changed(); } };

  // ---- the selected unit ----
  const options = (select, list, value, { none = null, missing = 'not on this install' } = {}) => {
    select.replaceChildren();
    if (none !== null) select.append(new Option(none, ''));
    for (const o of list) select.append(new Option(o.label, o.id));
    if (value != null && value !== '' && !list.some(o => o.id === value)) {
      const known = items()[value];
      select.append(new Option(`${known?.label ?? value} (${known ? 'not in this list' : missing})`, value));
    }
    select.value = value ?? '';
  };
  const slotList = (kind, slot) => {
    const c = choices();
    const ids = (els.wide.checked ? c?.slotsAll : c?.slots)?.[kind]?.[slot] ?? [];
    return ids.map(id => ({ id, label: items()[id]?.label ?? id }));
  };
  const field = (labelText, control, help = null) => el('label', { className: 'squadfield' }, el('span', { textContent: labelText }), control, help);
  function armourLine(id) {
    const a = items()[id]?.armour;
    if (!a) return id ? 'Not an armour of this install' : '';
    const bits = [`HP +${a.hp}`, `defence ${a.defence >= 0 ? '+' : ''}${a.defence}`, `mobility ${a.mobility >= 0 ? '+' : ''}${a.mobility}`];
    if (a.will) bits.push(`will +${a.will}`);
    if (a.fuel) bits.push(`flight fuel ${a.fuel}`);
    bits.push(`${plural(a.large, 'large slot')}, ${plural(a.small, 'small slot')}`);
    const props = (a.properties ?? []).map(p => p.replace(/^eAP_/, '')).filter(p => !['Tank', 'MEC'].includes(p));
    const abilities = (a.abilities ?? []).map(p => p.replace(/^eAbility_/, ''));
    return [bits.join(' · '), [...abilities, ...props].join(', ')].filter(Boolean).join(' · ');
  }
  function listEditor(unit, slot, kind) {
    const box = el('div', { className: 'squadlist' });
    const values = unit[slot];
    const list = slotList(kind, slot);
    values.forEach((value, i) => {
      const s = el('select', { id: `squad-${slot}-${i}` });
      s.setAttribute('aria-label', `${SLOT_WORDS[slot]} ${i + 1}`);
      options(s, list, value);
      s.onchange = () => { values[i] = s.value; changed(); renderUnit(s.id); };
      const remove = el('button', { type: 'button', className: 'icon squadx', textContent: '×', title: `Take ${label(value)} out` });
      remove.onclick = () => { values.splice(i, 1); changed(); renderUnit(`squad-${slot}-add`); };
      box.append(el('div', { className: 'squadlistrow' }, el('span', { className: 'squadnum', textContent: `${i + 1}` }), s, remove));
    });
    const add = el('select', { id: `squad-${slot}-add` });
    add.setAttribute('aria-label', `Add to ${SLOT_WORDS[slot].toLowerCase()}`);
    options(add, list, '', { none: `Add ${slot === 'weapons' ? 'a weapon' : slot === 'items' ? 'an item' : ''}…` });
    add.disabled = values.length >= 16;
    add.onchange = () => { if (add.value) { values.push(add.value); changed(); renderUnit(`squad-${slot}-add`); } };
    box.append(add);
    return box;
  }
  function perksEditor(unit) {
    const box = el('div', { className: 'squadperks' });
    const all = choices()?.perks ?? [];
    const byId = Object.fromEntries(all.map(p => [p.id, p]));
    const chips = el('div', { className: 'squadchips' });
    unit.perks.forEach((id, i) => {
      const p = byId[id];
      const chip = el('button', { type: 'button', className: `chip${p ? '' : ' warn'}`, textContent: `${p?.label ?? id}${p ? '' : ' (not on this install)'} ×`, title: `Take ${p?.label ?? id} off` });
      chip.onclick = () => { unit.perks.splice(i, 1); changed(); renderUnit('squad-perk-find'); };
      chips.append(chip);
    });
    if (!unit.perks.length) chips.append(el('span', { className: 'squadnone', textContent: 'None' }));
    const listId = 'squadPerkList';
    const find = el('input', { id: 'squad-perk-find', type: 'search', placeholder: 'Add a perk: type its name', autocomplete: 'off', spellcheck: false });
    find.setAttribute('list', listId);
    const data = el('datalist', { id: listId });
    for (const p of all) if ((p.normal || els.wide.checked) && !unit.perks.includes(p.id)) data.append(el('option', { value: p.label }));
    const take = () => {
      const want = find.value.trim().toLowerCase();
      const hit = all.find(p => p.label.toLowerCase() === want && (p.normal || els.wide.checked));
      if (hit && !unit.perks.includes(hit.id)) { unit.perks.push(hit.id); changed(); renderUnit('squad-perk-find'); }
    };
    find.onchange = take;
    find.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); take(); } });
    box.append(chips, find, data);
    return box;
  }
  function statsEditor(unit) {
    const base = choices()?.base?.[unit.kind] ?? {};
    const grid = el('div', { className: 'squadstats' });
    for (const s of choices()?.stats ?? []) {
      const input = el('input', { id: `squad-stat-${s.id}`, type: 'number', min: status.limits.stats[0], max: status.limits.stats[1], step: 1,
                                  value: unit.stats[s.id] ?? '', placeholder: base[s.id] ?? '' });
      input.oninput = () => {
        const v = input.value.trim();
        if (v === '') delete unit.stats[s.id];
        else if (/^\d+$/.test(v)) unit.stats[s.id] = Number(v);
        changed();
      };
      grid.append(el('label', {}, el('span', { textContent: s.label }), input));
    }
    const reset = el('button', { type: 'button', textContent: 'Use the install\'s', title: 'Clear the numbers set here: the unit gets the install\'s base stats for its kind' });
    reset.disabled = !Object.keys(unit.stats).length;
    reset.onclick = () => { unit.stats = {}; changed(); renderUnit(); };
    return el('div', {}, grid, el('div', { className: 'squadstatsfoot' },
      el('small', { textContent: 'Empty is the install\'s base. Armour, weapons, perks and the game\'s own rules add to these.' }), reset));
  }
  function changeKind(unit, kind) {
    const template = choices()?.templates?.[kind];
    if (!template || kind === unit.kind) return;
    const before = clone(unit), cleared = [];
    const keep = new Set([...(choices()?.slots?.[kind]?.items ?? [])]);      // the new kind's usual items stay
    for (const slot of ['armour', 'sidearm']) if (unit[slot] && unit[slot] !== template[slot]) cleared.push(`${SLOT_WORDS[slot].toLowerCase()} (${label(unit[slot])})`);
    if (unit.weapons.length) cleared.push(`weapons (${unit.weapons.map(label).join(', ')})`);
    const dropped = unit.items.filter(i => !keep.has(i));
    if (dropped.length) cleared.push(`items (${dropped.map(label).join(', ')})`);
    if (Object.keys(unit.stats).length) cleared.push('base stats set here');
    Object.assign(unit, { kind, class: template.class, armour: template.armour, sidearm: template.sidearm, weapons: [...template.weapons],
                          items: unit.items.filter(i => keep.has(i)), stats: {} });
    if (kind === 'shiv') Object.assign(unit, { look: null, country: null, last: '', first: unit.first || template.first });
    else Object.assign(unit, { look: unit.look ?? template.look, country: unit.country ?? template.country });
    kindNote = { text: cleared.length ? `Now a ${KIND_WORDS[kind]}: its ${cleared.join(', ')} changed to the ${KIND_WORDS[kind]}'s.` : `Now a ${KIND_WORDS[kind]}.`, before };
    changed(); renderUnit('squad-kind');
  }
  function renderUnitIssues() {
    const box = els.unit.querySelector('.squadunitissues');
    if (!box) return;
    const c = checkOf(selected);
    box.replaceChildren(...[...(c?.errors ?? []).map(t => el('li', { className: 'bad', textContent: t })),
                            ...(c?.warnings ?? []).map(t => el('li', { className: 'warn', textContent: t })),
                            ...(c?.notes ?? []).map(t => el('li', { textContent: t }))]);
    box.hidden = !box.children.length;
  }
  function renderUnit(focusId = null) {
    const unit = unitOf(selected), c = choices();
    els.unit.replaceChildren();
    if (!unit) return;
    if (!c) { els.unit.append(el('p', { className: 'optionsnote warn', textContent: `The install's soldier data could not be read${status?.install?.error ? `: ${status.install.error}` : ''}. The squad is kept as it is.` })); return; }
    const kind = el('select', { id: 'squad-kind' });
    for (const k of c.kinds) { const o = new Option(k.label, k.id); o.disabled = !k.available && k.id !== unit.kind; if (!k.available) o.title = k.why ?? ''; kind.append(o); }
    kind.value = unit.kind;
    kind.onchange = () => changeKind(unit, kind.value);
    const head = el('div', { className: 'squadunithead' }, field('Kind', kind));
    els.unit.append(head);
    if (kindNote) {
      const undo = el('button', { type: 'button', className: 'link', textContent: 'Undo' });
      undo.onclick = () => { Object.assign(unit, kindNote.before); kindNote = null; changed(); renderUnit('squad-kind'); };
      els.unit.append(el('p', { className: 'optionsnote squadkindnote' }, kindNote.text, ' ', undo));
    }
    els.unit.append(el('ul', { className: 'squadunitissues', hidden: true }));
    const names = el('div', { className: 'squadrow2' });
    const text = (key, labelText) => {
      const input = el('input', { id: `squad-${key}`, value: unit[key], maxLength: status.limits.name, spellcheck: false, autocomplete: 'off' });
      input.oninput = () => { unit[key] = input.value; changed(); };
      return field(labelText, input);
    };
    if (unit.kind === 'shiv') names.append(text('first', 'Name'));
    else names.append(text('first', 'First name'), text('last', 'Last name'));
    els.unit.append(names);
    const who = el('div', { className: 'squadrow2' });
    if (unit.kind === 'soldier') {
      const cls = el('select', { id: 'squad-class' });
      options(cls, c.classes, unit.class, { missing: 'not a class here' });
      cls.onchange = () => { unit.class = cls.value; changed(); };
      who.append(field('Class', cls));
    } else who.append(field('Class', el('output', { textContent: unit.kind === 'mec' ? (c.classes.find(x => x.id === unit.class)?.label ?? 'MEC trooper') : 'None (a SHIV)' })));
    const rank = el('select', { id: 'squad-rank' });
    for (const r of c.ranks) rank.append(new Option(r.label, String(r.value)));
    if (!c.ranks.some(r => r.value === unit.rank)) rank.append(new Option(`Rank ${unit.rank}`, String(unit.rank)));
    rank.value = String(unit.rank);
    rank.onchange = () => { unit.rank = Number(rank.value); changed(); };
    who.append(field('Rank', rank, el('small', { textContent: 'The badge: no stats or perks come with it here' })));
    els.unit.append(who);
    if (unit.kind !== 'shiv') {
      const looks = el('div', { className: 'squadrow2' });
      const look = el('select', { id: 'squad-look' });
      options(look, c.looks, unit.look, { missing: 'not a look here' });
      look.onchange = () => { unit.look = look.value; changed(); };
      const country = el('select', { id: 'squad-country' });
      options(country, c.countries, unit.country, { missing: 'not a country here' });
      country.onchange = () => { unit.country = country.value; changed(); };
      looks.append(field('Look', look), field('Country', country));
      els.unit.append(looks);
    }
    const armour = el('select', { id: 'squad-armour' });
    options(armour, slotList(unit.kind, 'armour'), unit.armour);
    armour.onchange = () => { unit.armour = armour.value; changed(); renderUnit('squad-armour'); };
    els.unit.append(field(unit.kind === 'mec' ? 'MEC suit' : unit.kind === 'shiv' ? 'Chassis' : 'Armour', armour,
                          el('small', { textContent: armourLine(unit.armour) })));
    if (unit.kind === 'soldier') {
      const sidearm = el('select', { id: 'squad-sidearm' });
      options(sidearm, [...slotList('soldier', 'sidearm'), ...(unit.class === 'eSC_HeavyWeapons' ? slotList('soldier', 'weapons').filter(o => items()[o.id]?.roles.includes('primary')) : [])],
              unit.sidearm, { none: 'None' });
      sidearm.onchange = () => { unit.sidearm = sidearm.value || null; changed(); };
      els.unit.append(field('Sidearm', sidearm, el('small', { textContent: unit.class === 'eSC_HeavyWeapons'
        ? 'A heavy can carry its main gun here and its launcher as its weapon, as the default heavy does' : 'The pistol\'s place' })));
    }
    els.unit.append(field(unit.kind === 'mec' ? 'Gun and modules' : unit.kind === 'shiv' ? 'Gun' : 'Weapons', listEditor(unit, 'weapons', unit.kind),
      el('small', { textContent: unit.kind === 'mec' ? 'The gun first, then its modules (kinetic strike, flamethrower…)' : unit.kind === 'shiv' ? 'A SHIV fires its first gun' : 'The weapon first' })));
    const capacity = items()[unit.armour]?.armour?.small;
    els.unit.append(field('Items', listEditor(unit, 'items', unit.kind),
      el('small', { textContent: capacity == null ? '' : `${unit.items.length} of the ${plural(capacity, 'small slot')} the ${unit.kind === 'shiv' ? 'chassis' : 'armour'} has` })));
    els.unit.append(field('Perks', perksEditor(unit)));
    els.unit.append(el('fieldset', { className: 'squadstatsbox' }, el('legend', { textContent: 'Base stats' }), statsEditor(unit)));
    renderUnitIssues();
    if (focusId) document.getElementById(focusId)?.focus();
  }

  // ---- the lines under the panel ----
  function renderIssues() {
    const lines = [...(check?.errors ?? []).map(t => ['bad', t]), ...(check?.warnings ?? []).map(t => ['warn', t]),
                   ...(check?.notes ?? []).map(t => ['', t]), ...(choices()?.diagnostics ?? []).map(t => ['warn', t])];
    els.issues.replaceChildren(...lines.map(([cls, t]) => el('li', { className: cls, textContent: t })));
    els.issues.hidden = !lines.length;
    if (!busy && !conflict) {
      if (!check) say(status?.choices ? '' : 'Not checked', !status?.choices);
      else if (!check.playable) say(`${plural(check.errors.length + check.units.reduce((n, u) => n + u.errors.length, 0), 'error')}: Play in game can't use this squad until it is put right`, true);
      else say(dirty ? 'Changed: Save keeps it' : status.saved ? 'Saved' : 'The default squad (not saved yet)');
    }
  }
  function renderAll(focus = true) {
    const install = status.install ?? {};
    els.intro.textContent = install.folder
      ? `Every Play in game lands with this squad. Its choices are those of the install it plays in: ${install.folder}${choices() ? ` (${choices().familyLabel})` : ''}.`
      : `Every Play in game lands with this squad. No install to play in: ${install.note ?? 'not set'}.`;
    els.problem.hidden = !status.problem;
    els.problem.textContent = status.problem ? `The saved squad's file can't be used: ${status.problem}. It is left as it is until you save a squad here (its bytes are then kept beside it). Reset to default starts one.` : '';
    els.name.value = draft?.name ?? '';
    els.name.disabled = !draft;
    for (const b of [els.exportButton, els.save]) b.disabled = !draft || busy;
    if (!draft) { els.units.replaceChildren(); els.unit.replaceChildren(); renderIssues(); return; }
    if (!unitOf(selected)) selected = draft.units[0]?.id ?? null;
    renderList(); renderUnit(); renderIssues();
    if (focus) setTimeout(() => els.units.querySelector('.on')?.focus(), 0);
  }

  async function show() {
    lastFocus = document.activeElement;
    els.root.hidden = false;
    busy = true; conflict = false; dirty = false; kindNote = null;
    say('Reading the squad…');
    els.units.replaceChildren(); els.unit.replaceChildren(); els.issues.hidden = true;
    els.importButton.disabled = els.reset.disabled = false;     // (off after a failed read; renderAll sets the rest)
    try {
      status = await api.get();
      draft = status.document ? clone(status.document) : null;
      check = status.check;
      selected = draft?.units[0]?.id ?? null;
      busy = false;
      renderAll();
    } catch (e) {
      // (nothing to edit: every control that works on the squad is off until it is read, review finding 34)
      busy = false; status = null; draft = null; check = null; selected = null;
      els.name.value = '';
      for (const c of [els.add, els.copy, els.remove, els.up, els.down, els.name, els.exportButton, els.importButton, els.reset, els.save]) c.disabled = true;
      say(`The squad could not be read: ${e.message}. Close the panel and open it again to try again.`, true);
    }
  }
  function hide() {
    clearTimeout(timer);
    els.root.hidden = true;
    lastFocus?.focus?.();
    onClosed();
  }
  async function save(force = false) {
    if (!draft || busy) return;
    busy = true; say('Saving…');
    try {
      let revision = status.revision;
      if (force) revision = (await api.get()).revision;
      const r = await api.save(revision, draft);
      status = { ...status, ...r, choices: status.choices };
      busy = false; dirty = false;
      onSaved(status);
      hide();
    } catch (e) {
      busy = false;
      if (e.status === 409) {
        conflict = true;
        say('Saved elsewhere meanwhile (another tab, or the file was changed). Your changes are still here.', true);
        const use = el('button', { type: 'button', className: 'link', textContent: 'Use the saved squad' });
        use.onclick = () => show();
        const over = el('button', { type: 'button', className: 'link', textContent: 'Save mine over it' });
        over.onclick = () => save(true);
        els.status.append(' ', use, ' · ', over);
      } else say(`Not saved: ${e.message}`, true);
      renderList();
    }
  }
  els.form.onsubmit = e => { e.preventDefault(); save(); };
  els.cancel.onclick = els.close.onclick = hide;
  els.reset.onclick = () => {
    if (!status?.default) { say('No default squad for this install', true); return; }
    draft = clone(status.default); selected = draft.units[0].id; kindNote = null;
    changed(); renderAll(false); say('The default squad: Save keeps it');
  };
  els.wide.onchange = () => renderUnit();
  els.exportButton.onclick = async () => {
    try {
      const { name, text } = await api.exportDocument(draft);
      const link = el('a', { href: URL.createObjectURL(new Blob([text], { type: 'application/json' })), download: name });
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      say(`Exported as ${name}`);
    } catch (e) { say(`Not exported: ${e.message}`, true); }
  };
  els.importButton.onclick = () => { els.importFile.value = ''; els.importFile.click(); };
  els.importFile.onchange = async () => {
    const file = els.importFile.files?.[0];
    if (!file) return;
    try {
      const r = await api.importText(await file.text());
      draft = r.document; check = r.check; selected = draft.units[0].id; kindNote = null;
      dirty = true; renderAll(false);
      say(`Imported ${draft.name} from ${file.name}: Save keeps it`);
    } catch (e) { say(`Not imported: ${e.message}`, true); }
  };
  els.root.addEventListener('keydown', e => {
    e.stopPropagation();      // the editor behind takes no keys while the panel is open
    if (e.key === 'Escape') { e.preventDefault(); hide(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  return { show, get open() { return !els.root.hidden; } };
}
