// The Flags group of the piece panel and its chip (refactor stage P8; piece_flags.js holds the flags' rules: a piece's
// roles, what a request does and its normalized form). Five settings of a piece decide how the game's tiles and mouse
// use it (Blocks walking, Gives cover, Blocks sight, Floor, Mouse picks it); they are edited actor by actor for the
// pieces explicitly picked, an actor's components sharing one setting. Here:
// - why a piece takes no flags (flagBlock), the actors the group edits (flagTargets), what a piece's flags are planned
//   on (flagSource) and one actor's flags as the project has them (flagView);
// - the Flags chip (flagChip) and the Flags group (flagsPanel): a row per role over the picked actors, what limits
//   each, why a row is greyed;
// - a row clicked (flagClick) and the change made as one undo step (applyFlags, commitFlags), after asking where a
//   prop's pathing gate would change a half-on role (askFlags); Reset (resetFlags).
//
// createFlagsPanel takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the pieces'
// boxes and keys, the tile grid's corner, the selection and the panel's helpers. Its own state is inside it (the
// question open about a prop's pathing gate).
import { sentence } from './build_queue.js';
import { isFloor } from './cover.js';
import { data, families, lightsOn, roots, selected, volumesOn, zonesOn } from './editor_state.js';
import { lowPiece, made as madeFlags, normalize as normalizeFlags, plan as planFlags, rawOf as flagRaw,
         ROLES as FLAG_ROLES, roles as flagRoles } from './piece_flags.js';

export function createFlagsPanel({ $, boxOf, gizmo, isStream, plural, select, sourceKey, text, tileCorner }) {
  // Piece flags (piece flags plan; piece_flags.js): the five settings of a piece that decide how the game's tiles and
  // mouse use it (Blocks walking, Gives cover, Blocks sight, Floor, Mouse picks it), edited actor by actor for the
  // pieces explicitly picked (gizmo.picks, not the linked pieces the selection moves with); one actor's components
  // share one setting. root.userData.flags is the request the project saves, normalized (piece_flags.normalize: only
  // what the map doesn't have already, and what keeps a prop's other roles as they were); the export's pieceFlags
  // (export 27) are the map's own settings, an added piece's its template's. These are the settings the game's filters
  // read, not a prediction of the finished tiles.
  const FLAG_WORDS = { on: 'on', off: 'off', partial: 'partly on', unknown: 'unknown', 'n/a': '' };
  const flagContract = () => families?.pieceFlags ?? null;
  const flagKey = o => (o.added ? `added|${o.actor}` : `orig|${sourceKey(o)}`);
  const flagSentences = list => list.filter(Boolean).map(s => sentence(s).replace(/\.?$/, '.')).join(' ');
  // Why a piece takes no flags at all, or null.
  function flagBlock(o) {
    const c = flagContract();
    if (!c) return 'the editor\'s server is older than its page: restart it (xcom_editor.cmd restart) to set flags';
    if (o.cover) return isFloor(o.cover) ? 'an invisible floor\'s cover is its own' : 'a cover block\'s cover is its own (its Cover setting)';
    if (isStream(o)) return 'it is a piece of a streamed level, which the editor doesn\'t edit';
    if (o.hidden || o.environment) return 'it is hidden in the game';
    if (!o.pieceFlags) return c.classes[o.actorClass] ? 'its map was exported before flags: open the map again to prepare it' : `the flags are not a setting of a ${o.actorClass}`;
    return null;
  }
  // The actors the Flags group edits, each once with all its components: [{ key, source, roots }].
  function flagTargets(ids = gizmo.picks().ids) {
    const out = new Map();
    for (const id of ids) {
      const r = roots.get(id);
      if (!r || r.userData.deleted) continue;
      const key = flagKey(r.userData.source);
      if (!out.has(key)) out.set(key, { key, source: r.userData.source, roots: [] });
    }
    if (out.size) for (const r of roots.values()) out.get(flagKey(r.userData.source))?.roots.push(r);
    return [...out.values()];
  }
  // [class, flags record] a piece's flags are planned on: its own, or for a wall, floor or ground made from numbers what
  // the Build makes of its donor's (piece_flags.js made: collision of its own; a ground shape on a static mesh actor is
  // made a level piece that collides, the user, 19 November 2026: flags on made pieces).
  function flagSource(o) {
    const kind = o.added?.generated?.kind;
    return kind && o.pieceFlags ? madeFlags(flagContract(), o.actorClass, o.pieceFlags, kind) : [o.actorClass, o.pieceFlags];
  }
  // One actor's flags as the project has them: its settings, its request, what the request does, and each role after it
  // with its limits (a low piece's from what is drawn of it where it stands: piece_flags.js lowPiece).
  function flagView(t) {
    const c = flagContract(), [cls, pf] = flagSource(t.source), { raw, assumed } = flagRaw(pf);
    const request = t.roots[0]?.userData.flags ?? {};
    const plan = planFlags(c, cls, raw, request, assumed);
    const written = new Set(plan.writes.map(([k]) => k));
    const boxes = t.roots.map(r => boxOf(r)).filter(Boolean);
    const box = boxes.length ? boxes.reduce((a, b) => a.map((v, k) => (k % 2 ? Math.max(v, b[k]) : Math.min(v, b[k])))) : null;
    const roles = flagRoles(c, cls, { ...raw, ...Object.fromEntries(plan.writes) },
                            { collides: pf.collides, bodySetup: pf.bodySetup, assumed: assumed.filter(k => !written.has(k)),
                              low: lowPiece(c, box, tileCorner()?.[2]) });
    return { cls, collides: pf.collides, raw, assumed, request, plan, roles };
  }
  // The Flags chip: a piece with a setting off (or half on), or whose flags the project changes.
  function flagChip(chips, root) {
    const o = root.userData.source;
    if (flagBlock(o)) return;
    const v = flagView({ key: flagKey(o), source: o, roots: [root] }), c = flagContract();
    const off = FLAG_ROLES.filter(r => ['off', 'partial'].includes(v.plan.after[r]));
    const changed = Object.keys(v.request).length > 0;
    if (!off.length && !changed) return;
    const chip = text(chips, 'span', changed ? 'Flags · changed' : 'Flags', 'chip');
    chip.title = [...FLAG_ROLES.filter(r => v.plan.after[r] !== 'n/a').map(r => `${c.labels[r]}: ${FLAG_WORDS[v.plan.after[r]]}`
      + `${r in v.request ? ' (changed)' : ''}${(v.roles[r].limits ?? []).includes('assumed') ? ' (assumed)' : ''}`),
      'How the game\'s tiles and mouse use it; set in the Flags group below'].join('\n');
  }
  // The Flags group: a row per role over the picked actors (mixed where they differ), what limits each, why a row is
  // greyed, and how many of the pieces take it.
  let flagAsk = null;      // the question open about a prop's pathing gate: { key } (the picks it was asked for)
  const flagSelectionKey = () => gizmo.picks().ids.join('|');
  function closeFlagAsk() { flagAsk = null; $('flagsAsk').hidden = true; $('flagsAsk').replaceChildren(); }
  function flagsPanel() {
    const box = $('flagsBox');
    const all = !data || volumesOn || lightsOn || zonesOn ? [] : flagTargets();
    if (flagAsk && flagAsk.key !== flagSelectionKey()) closeFlagAsk();
    if (!all.length || all.every(t => t.source.cover)) { box.hidden = true; return; }
    box.hidden = false;
    const c = flagContract(), usable = [], blocked = new Map();
    for (const t of all) {
      const why = flagBlock(t.source);
      if (why) blocked.set(why, (blocked.get(why) ?? 0) + 1); else usable.push(t);
    }
    const views = new Map(usable.map(t => [t.key, flagView(t)]));
    const rows = $('flagsRows'), whyLine = $('flagsWhy');
    rows.replaceChildren();
    const showWhy = label => { whyLine.textContent = label?.dataset.why ? `${label.dataset.name}: ${label.dataset.why}` : whyLine.dataset.rest; };
    rows.onmouseleave = () => showWhy(null);
    // a limit that holds for several rows of one piece (a prop's gate) is said once, under the rows
    const one = usable.length === 1 ? views.get(usable[0].key) : null, seen = new Map();
    for (const role of FLAG_ROLES) for (const k of one?.roles[role].limits ?? []) seen.set(k, (seen.get(k) ?? 0) + 1);
    const shared = [...seen].filter(([, n]) => n > 1).map(([k]) => k);
    for (const role of FLAG_ROLES) {
      const eligible = usable.filter(t => views.get(t.key).plan.after[role] !== 'n/a');
      const states = eligible.map(t => views.get(t.key).plan.after[role]);
      const label = document.createElement('label');
      label.className = 'flagrow';
      const input = document.createElement('input');
      input.type = 'checkbox';
      label.append(input);
      const name = text(label, 'span', c?.labels[role] ?? role, 'flagname');
      const state = text(name, 'span', '', 'flagstate');
      const why = { textContent: '' };
      const same = states.length > 0 && states.every(x => x === states[0]);
      input.checked = states.length > 0 && states.every(x => x === 'on');
      input.indeterminate = states.length > 0 && (!same || states.some(x => x === 'partial' || x === 'unknown'));
      input.disabled = !eligible.length;
      label.classList.toggle('off', !eligible.length);
      label.classList.toggle('changed', eligible.some(t => role in views.get(t.key).request));
      state.textContent = !eligible.length ? '' : same ? FLAG_WORDS[states[0]] : 'mixed';
      if (!eligible.length) {
        why.textContent = flagSentences([usable.length ? views.get(usable[0].key).roles[role].why : [...blocked.keys()][0]]);
      } else {
        const notes = eligible.length === 1 ? (views.get(eligible[0].key).roles[role].limits ?? []).filter(k => !shared.includes(k)).map(k => c.limits[k]) : [];
        const without = usable.length - eligible.length;
        if (without) notes.push(`${eligible.length} of ${usable.length} pieces: ${plural(without, 'piece')} ${without === 1 ? 'has' : 'have'} no such setting (${[...new Set(usable.filter(t => !eligible.includes(t)).map(t => views.get(t.key).cls))].join(', ')})`);
        if (eligible.length > 1 && states.includes('partial')) notes.push('partly on: a prop\'s pathing gate passes it by in the sweeps, not in the occupancy step');
        why.textContent = flagSentences(notes);
      }
      input.title = `${c?.labels[role] ?? role}: click to turn it ${states.length && states.every(x => x === 'on') ? 'off' : 'on'} for ${eligible.length === 1 ? 'this piece' : `these ${eligible.length} pieces`}`;
      input.onchange = () => flagClick(role);
      // what limits the row, or why it is greyed: said in the one line under the rows while the pointer or the focus is on it
      label.dataset.name = c?.labels[role] ?? role;
      label.dataset.why = why.textContent;
      if (why.textContent) {
        label.classList.add('haswhy');
        label.title = why.textContent;
        label.insertAdjacentHTML('beforeend', '<svg class="i whymark" aria-hidden="true"><use href="#i-info"/></svg>');
      }
      label.onmouseenter = () => showWhy(label);
      input.onfocus = () => showWhy(label);
      rows.append(label);
    }
    whyLine.dataset.rest = rows.querySelector('.haswhy') ? 'Point at a marked flag for what limits it.' : '';
    showWhy(null);
    const changedRoles = rows.querySelectorAll('.changed').length;
    $('flagsCount').textContent = [changedRoles ? `${changedRoles} changed` : usable.length ? 'as the map has them' : 'not available',
      all.length > 1 ? plural(usable.length, 'piece') : ''].filter(Boolean).join(' · ');
    $('flagsCount').classList.toggle('changed', changedRoles > 0);
    const lines = [...shared.map(k => c.limits[k]), ...[...blocked].map(([why, n]) => `${all.length > 1 ? `${plural(n, 'piece')}: ` : ''}${why}`)];
    if (usable.some(t => t.roots.length > 1)) lines.push('a piece of several parts (a mesh and its glass) has one setting for all of them');
    const targeted = new Set(all.flatMap(t => t.roots));
    const carried = new Set(gizmo.selection().filter(r => !r.userData.light && !r.userData.volume && !r.userData.effect && !targeted.has(r)).map(r => flagKey(r.userData.source))).size;
    if (carried) lines.push(`${plural(carried, 'piece')} that ${carried === 1 ? 'moves' : 'move'} with the selection ${carried === 1 ? 'keeps its' : 'keep their'} own flags: pick ${carried === 1 ? 'it' : 'them'} too (or Select all) to set ${carried === 1 ? 'it' : 'them'}`);
    $('flagsTargets').textContent = flagSentences(lines);
    $('flagsReset').disabled = !usable.some(t => t.roots[0]?.userData.flags);
  }
  // A click on a row: every picked piece that has the role turned on, or off when all of them have it on.
  function flagClick(role) {
    const usable = flagTargets().filter(t => !flagBlock(t.source));
    const views = new Map(usable.map(t => [t.key, flagView(t)]));
    const eligible = usable.filter(t => views.get(t.key).plan.after[role] !== 'n/a');
    if (!eligible.length) { flagsPanel(); return; }
    applyFlags(eligible, { [role]: !eligible.every(t => views.get(t.key).plan.after[role] === 'on') });
  }
  // A change ({role: on}) made to these actors as one undo step, after asking where a prop's pathing gate would change a
  // half-on role (`resolve`: the answer, {actor key: {role: on}}).
  function applyFlags(targets, change, resolve = new Map()) {
    const c = flagContract(), next = new Map(), conflicts = new Map();
    for (const t of targets) {
      const v = flagView(t), request = { ...v.request, ...change, ...(resolve.get(t.key) ?? {}) };
      const p = planFlags(c, v.cls, v.raw, request, v.assumed);
      const open = Object.keys(p.conflicts);
      if (open.length) { conflicts.set(t.key, open); continue; }
      const n = normalizeFlags(c, v.cls, v.raw, request, v.assumed, v.collides);
      next.set(t.key, Object.keys(n).length ? n : null);
    }
    if (conflicts.size) { askFlags(targets, change, resolve, conflicts); return; }
    closeFlagAsk();
    commitFlags(targets, next);
  }
  function askFlags(targets, change, resolve, conflicts) {
    const c = flagContract(), roles = [...new Set([...conflicts.values()].flat())];
    const names = roles.map(r => c.labels[r]);
    const asked = Object.entries(change).map(([r, on]) => `${c.labels[r]} ${on ? 'on' : 'off'}`).join(' and ');
    flagAsk = { key: flagSelectionKey() };
    flagsPanel();
    const box = $('flagsAsk');
    box.replaceChildren();
    text(box, 'div', `${asked} opens the pathing gate (bIgnoreForPathing) of ${conflicts.size === 1 ? 'this prop' : plural(conflicts.size, 'prop')}. `
      + `${names.join(' and ')} ${roles.length === 1 ? 'is' : 'are'} partly on there and can't stay so: set ${roles.length === 1 ? 'it' : 'them'} too.`);
    const row = text(box, 'div', '', 'row');
    for (const on of [true, false]) {
      const b = text(row, 'button', `${roles.length === 1 ? names[0] : 'Them'} ${on ? 'on' : 'off'}`);
      b.type = 'button';
      b.onclick = () => {
        const more = new Map(resolve);
        for (const [key, open] of conflicts) more.set(key, { ...(more.get(key) ?? {}), ...Object.fromEntries(open.map(r => [r, on])) });
        applyFlags(targets, change, more);
      };
    }
    const cancel = text(row, 'button', 'Cancel');
    cancel.type = 'button';
    cancel.onclick = () => { closeFlagAsk(); flagsPanel(); };
    box.hidden = false;
    $('flagsBox').open = true;
    row.querySelector('button')?.focus();
  }
  // The actors' new requests (null: none) as one undo step; nothing when none changes.
  function commitFlags(targets, next) {
    const before = new Map(targets.map(t => [t.key, t.roots[0]?.userData.flags ?? null]));
    const changed = targets.filter(t => JSON.stringify(before.get(t.key)) !== JSON.stringify(next.get(t.key) ?? null));
    if (!changed.length) { flagsPanel(); return; }
    const set = values => { for (const t of changed) for (const r of t.roots) r.userData.flags = values.get(t.key) ? { ...values.get(t.key) } : null; };
    gizmo.record({ redo: () => { set(next); flagsChanged(); }, undo: () => { set(before); flagsChanged(); } });
  }
  function flagsChanged() { if (selected && roots.get(selected)) select(selected, false, true); }
  function resetFlags() {
    const targets = flagTargets().filter(t => !flagBlock(t.source) && t.roots[0]?.userData.flags);
    closeFlagAsk();
    if (targets.length) commitFlags(targets, new Map());
  }

  return { flagChip, flagContract, flagKey, flagSource, flagsPanel, resetFlags };
}
