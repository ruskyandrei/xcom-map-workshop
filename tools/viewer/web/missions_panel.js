// The Missions panel (Map menu; private/plans/done/mission-types-plan.md, D2): the missions the project is for.
// Each row is one of the base map's missions (ticked: the Build writes its record) or a kind a record alone gives the
// map (an added kind: abduction, terror, a council bomb under LWR, a crashed or landed UFO with a UFO building), with
// what is known of it played and what it needs. A cleared map is asked "What is this map for?" when Clear map runs.
// OK needs one row ticked at least: the Build writes a record for each, and a package with none can't be played.

export const SHIPS = [['eShip_UFOSmallScout', 'Small scout'], ['eShip_UFOLargeScout', 'Large scout'], ['eShip_UFOAbductor', 'Abductor'],
                      ['eShip_UFOSupply', 'Supply ship'], ['eShip_UFOBattle', 'Battleship'], ['eShip_UFOEthereal', 'Overseer']];

/** els: root, form, title, note, list, warn, ok, close, cancel. */
export function createMissionsPanel({ els }) {
  let lastFocus = null, onOk = null, rows = [];
  function hide() { els.root.hidden = true; lastFocus?.focus?.(); }
  function ticked() {
    return rows.filter(r => r.box.checked && !r.box.disabled).map(r => (r.ship ? { ...r.entry, ship: r.ship.value } : { ...r.entry }));
  }
  function changed() {
    const none = ticked().length === 0;
    els.ok.disabled = none;
    els.warn.hidden = !none;
    els.warn.textContent = none ? 'Tick at least one mission: the Build writes a record for each, and a package with none can\'t be played.' : '';
    for (const r of rows) if (r.ship) r.ship.hidden = !r.box.checked;
  }
  /**
   * title, note: what the panel asks; rows: [{entry ({record: i} or {kind, ship?}), label, checked, words (its state
   * played this way), detail (what it needs, its objects), disabled (why not, or null), ufo (a ship type to choose)}];
   * onOk(entries): the ticked rows' entries, in the rows' order.
   */
  function show({ title, note, rows: given, onOk: ok }) {
    lastFocus = document.activeElement;
    onOk = ok;
    els.title.textContent = title;
    els.note.textContent = note;
    els.list.replaceChildren();
    rows = given.map(row => {
      const label = document.createElement('label'), box = document.createElement('input'), body = document.createElement('span');
      label.className = 'bakeoption missionrow';
      box.type = 'checkbox'; box.checked = Boolean(row.checked) && !row.disabled; box.disabled = Boolean(row.disabled);
      const name = document.createElement('strong'); name.textContent = row.label;
      const small = document.createElement('small');
      small.textContent = [row.words, row.detail, row.disabled].filter(Boolean).join(' ');
      body.append(name, small);
      label.title = row.disabled ? row.disabled : '';
      label.append(box, body);
      const wrap = document.createElement('div');
      wrap.className = 'missionrowwrap';
      wrap.append(label);
      let ship = null;
      if (row.ufo) {     // beside the row, not in its label: a click in it doesn't toggle the row
        ship = document.createElement('select');
        ship.className = 'missionship';
        ship.title = 'The UFO the mission is: its ship type goes in the record (Long War\'s pods read it)';
        ship.append(...SHIPS.map(([value, text]) => new Option(text, value)));
        ship.value = row.entry.ship ?? SHIPS[0][0];
        wrap.append(ship);
      }
      els.list.append(wrap);
      box.onchange = changed;
      return { entry: row.entry, box, ship };
    });
    changed();
    els.root.hidden = false;
    setTimeout(() => els.ok.focus(), 0);
  }
  els.form.onsubmit = e => {
    e.preventDefault();
    const entries = ticked();
    if (!entries.length) return;
    const ok = onOk;
    hide();
    ok?.(entries);
  };
  els.close.onclick = els.cancel.onclick = hide;
  els.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hide(); } });
  return { show, get open() { return !els.root.hidden; } };
}
