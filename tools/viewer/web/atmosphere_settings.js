// The Map settings window's Fog and colour section (game-likeness plan, C5b; design 2B, chosen 27 November 2026): the
// map's height fog and its colour grade as the project changes them (the project's `atmosphere`, schema 10). The game's
// maps' looks first, as swatches (/atmospheres.json: the map's own, four looks spread apart, and every map in a list),
// then the values in two folds: the fog (on or off, density, height, falloff, its two colours) and the colour (tint,
// shadows, grey, bloom). The Game look draws them at once; a slider is one undo step on its release, a swatch, a colour,
// the tick and Reset one each. A map's post-process volume that sets its colour is named, read only. The rules are
// atmosphere_rules.js's; map_settings.js makes the section with the window.
// The members the time of day sets (the Sun, moon and sky section's bar: the fog's two colours, the tint, the shadows;
// sun_rules.js) are marked while the project sets a time: "the hour" where the time set them, "custom" where they
// were changed here since, which the time then leaves as they are.
import { ask } from './api.js';
import { COLOUR_SLIDERS, FOG_SLIDERS, LIFT, STRENGTH, atmosphereWith, colourHex, colourWords, fogWords, gradeVolumes,
         hexColour, liftOf, lookName, lookRecord, lookSwatch, spreadPicks, tintOf, tintParts, volumesOver,
         withMember } from './atmosphere_rules.js';
import { data, projectAtmosphere, projectSun, setProjectAtmosphere } from './editor_state.js';
import { timeMarks } from './sun_rules.js';

export function createAtmosphereSettings({ $, gizmo, projectsAvailable, changed = () => {} }) {
  const els = { note: $('mapLookNote'), looks: $('mapLooks'), changedChip: $('mapLookChanged'), fogOn: $('mapFogOn'),
                fogWords: $('mapFogWords'), colourWords: $('mapColourWords'), away: $('mapFogAway'), toward: $('mapFogToward'),
                tint: $('mapTint'), volumes: $('mapLookVolumes'), reset: $('mapLookReset'), fogSliders: $('mapFogSliders'),
                colourSliders: $('mapColourSliders') };
  let catalogue = null, catalogueWhy = null, dragFrom = undefined;
  const own = () => data?.atmosphere ?? null;
  const ownLook = () => ({ fog: own()?.world?.fog ?? {}, postProcess: own()?.world?.postProcess ?? {} });
  const now = () => atmosphereWith(own(), projectAtmosphere)?.world ?? { fog: {}, postProcess: {} };

  // the sliders, made once: each a label, a range and its value
  function slider(parent, spec, title) {
    const label = document.createElement('label');
    label.className = 'slider'; label.title = `${title} One undo step on release`;
    const name = document.createElement('span'); name.textContent = spec.label;
    const input = Object.assign(document.createElement('input'), { type: 'range', min: spec.min, max: spec.max, step: spec.step });
    const out = document.createElement('output');
    label.append(name, input, out); parent.append(label);
    return { input, out };
  }
  const sliders = {
    ...Object.fromEntries(FOG_SLIDERS.map(s => [s.key, { ...slider(els.fogSliders, s, `The fog's ${s.label.toLowerCase()}.`), section: 'fog', spec: s }])),
    lift: { ...slider(els.colourSliders, LIFT, 'Lifts the darkest colours (to the right) or deepens them (to the left).'), spec: LIFT },
    strength: { ...slider(els.colourSliders, STRENGTH, 'How strongly the tint is laid on: 1 leaves the picture as it is.'), spec: STRENGTH },
    ...Object.fromEntries(COLOUR_SLIDERS.map(s => [s.key, { ...slider(els.colourSliders, s, s.key === 'Bloom_Scale' ? 'How much the brightest light glows.' : 'How grey the picture is.'), section: 'postProcess', spec: s }])),
  };
  const show = (s, v) => { s.input.value = String(v); s.out.textContent = String(Math.round(Number(v) * 1000) / 1000); };
  // the marks of the members the time of day sets (the shadows' beside its slider)
  const shadowsMark = Object.assign(document.createElement('span'), { className: 'chip timemark', hidden: true });
  sliders.lift.input.parentElement.append(shadowsMark);
  const marks = { 'fog.OppositeLightColor': $('mapFogAwayMark'), 'fog.LightInscatteringColor': $('mapFogTowardMark'),
                  'postProcess.Scene_Colorize': $('mapTintMark'), 'postProcess.Scene_Shadows': shadowsMark };
  function paintMarks() {
    const now = projectSun && typeof projectSun === 'object' ? timeMarks(projectSun, projectAtmosphere) : {};
    for (const [key, chip] of Object.entries(marks)) {
      const mark = now[key] ?? null;
      chip.hidden = !mark;
      chip.textContent = mark === 'custom' ? 'custom' : 'the hour';
      chip.classList.toggle('custom', mark === 'custom');
      chip.title = mark === 'custom' ? 'Changed here: the time of day (Sun, moon and sky) leaves it as it is'
        : 'Set by the time of day (Sun, moon and sky)';
    }
  }

  // The record each control makes from the window as it is now (one member, or two for the tint)
  function recordFrom(key) {
    const before = projectAtmosphere, map = own();
    if (FOG_SLIDERS.some(s => s.key === key)) return withMember(before, map, 'fog', key, Number(sliders[key].input.value));
    if (COLOUR_SLIDERS.some(s => s.key === key)) {
      const value = Number(sliders[key].input.value);
      const next = withMember(before, map, 'postProcess', key, value);
      // bloom on again when it is turned up on a map whose bloom is off
      return key === 'Bloom_Scale' && value > 0 && now().postProcess.bEnableBloom === false ? withMember(next, map, 'postProcess', 'bEnableBloom', true) : next;
    }
    if (key === 'lift') { const l = Number(sliders.lift.input.value); return withMember(before, map, 'postProcess', 'Scene_Shadows', [-l, -l, -l]); }
    if (key === 'tint' || key === 'strength') return withMember(before, map, 'postProcess', 'Scene_Colorize', tintOf(els.tint.value, Number(sliders.strength.input.value)));
    if (key === 'fogOn') return withMember(before, map, 'fog', 'bEnabled', els.fogOn.checked);
    const colour = key === 'away' ? ['OppositeLightColor', els.away] : ['LightInscatteringColor', els.toward];
    const alpha = now().fog[colour[0]]?.[3] ?? 1;
    return withMember(before, map, 'fog', colour[0], hexColour(colour[1].value, alpha));
  }
  // A change, one undo step from `before` (the record as it was when a drag began)
  function commit(next, before = projectAtmosphere) {
    if (JSON.stringify(next) === JSON.stringify(before)) { setProjectAtmosphere(before); changed(); paint(); return; }
    gizmo.record({ redo: () => { setProjectAtmosphere(next); changed(); paint(); },
                   undo: () => { setProjectAtmosphere(before); changed(); paint(); } });
  }
  // While a control moves: the view follows, the record not yet kept
  function preview(key) {
    if (dragFrom === undefined) dragFrom = projectAtmosphere;
    setProjectAtmosphere(recordFrom(key)); changed(); words();
  }
  function release(key) {
    const before = dragFrom === undefined ? projectAtmosphere : dragFrom;
    dragFrom = undefined;
    setProjectAtmosphere(before);
    commit(recordFromAt(before, key), before);
  }
  // (the record a control makes over `before`, the window's values being what the control shows)
  function recordFromAt(before, key) {
    const saved = projectAtmosphere;
    setProjectAtmosphere(before);
    try { return recordFrom(key); } finally { setProjectAtmosphere(saved); }
  }
  for (const [key, s] of Object.entries(sliders)) {
    s.input.oninput = () => { s.out.textContent = String(Math.round(Number(s.input.value) * 1000) / 1000); preview(key); };
    s.input.onchange = () => release(key);
  }
  for (const [key, el] of [['away', els.away], ['toward', els.toward], ['tint', els.tint]]) {
    el.oninput = () => preview(key);
    el.onchange = () => release(key);
  }
  els.fogOn.onchange = () => commit(recordFrom('fogOn'));
  els.reset.onclick = () => commit(null);

  // the looks' swatches: the map's own, four spread apart, and every map's in a list
  function card(look, name, record) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'lookcard';
    const [top, middle, near] = lookSwatch(look);
    const swatch = document.createElement('div');
    swatch.className = 'swatch'; swatch.style.background = `linear-gradient(${top}, ${middle} 55%, ${near})`;
    const label = document.createElement('span'); label.textContent = name;
    button.append(swatch, label);
    button.title = record ? `Give this map the fog and colour of ${name}. One undo step` : 'This map\'s own fog and colour. One undo step';
    button.onclick = () => commit(record);
    button.dataset.record = JSON.stringify(record);
    return button;
  }
  function looks() {
    els.looks.replaceChildren();
    if (!own()) return;
    const map = own(), mine = ownLook();
    const others = (catalogue ?? []).filter(l => lookRecord(l, map));
    els.looks.append(card(mine, 'This map\'s own', null));
    for (const look of spreadPicks(others, mine, 4)) els.looks.append(card(look, lookName(look), lookRecord(look, map)));
    if (others.length) {
      const all = document.createElement('label');
      all.className = 'lookcard all'; all.title = 'The fog and colour of any of the game\'s maps. One undo step';
      const list = document.createElement('select');
      list.setAttribute('aria-label', 'All maps\' looks');
      list.append(new Option('All maps…', ''));
      const rows = others.flatMap(l => l.maps.map(m => ({ look: l, label: `${m.label}${(m.time ?? []).filter(t => t !== 'None').length ? ` (${m.time.filter(t => t !== 'None').join(', ').toLowerCase()})` : ''}` })))
        .sort((a, b) => a.label.localeCompare(b.label));
      rows.forEach((row, k) => list.append(new Option(row.label, String(k))));
      list.onchange = () => { const row = rows[Number(list.value)]; list.value = ''; if (row) commit(lookRecord(row.look, map)); };
      all.append(list);
      els.looks.append(all);
    }
  }
  function words() {
    const v = now();
    els.fogWords.textContent = fogWords(v.fog);
    els.colourWords.textContent = colourWords(v.postProcess);
    els.changedChip.hidden = !projectAtmosphere;
    paintMarks();
  }

  // The section as the project has it now
  function paint() {
    const map = own(), editable = Boolean(map && projectsAvailable());
    for (const el of [els.fogOn, els.away, els.toward, els.tint, els.reset, ...Object.values(sliders).map(s => s.input)]) el.disabled = !editable;
    if (!map) {
      els.note.textContent = 'This export says nothing of the map\'s fog and colour: open the map again to export it anew.';
      els.looks.replaceChildren(); els.volumes.hidden = true; els.changedChip.hidden = true;
      return;
    }
    els.note.textContent = 'The map\'s height fog and colour grade, seen in the Game look (K). The Build writes them on the map.'
      + (projectsAvailable() ? '' : ' They are changed on a map opened from the map browser, not a preview.')
      + (catalogueWhy ? ` The game's maps' looks can't be listed: ${catalogueWhy}.` : '');
    const v = now();
    els.fogOn.checked = Boolean(v.fog.bEnabled);
    for (const s of FOG_SLIDERS) show(sliders[s.key], v.fog[s.key] ?? 0);
    els.away.value = colourHex(v.fog.OppositeLightColor);
    els.toward.value = colourHex(v.fog.LightInscatteringColor);
    const tint = tintParts(v.postProcess.Scene_Colorize ?? [1, 1, 1]);
    els.tint.value = tint.hex; show(sliders.strength, tint.strength);
    show(sliders.lift, liftOf(v.postProcess.Scene_Shadows));
    show(sliders.Scene_Desaturation, v.postProcess.Scene_Desaturation ?? 0);
    show(sliders.Bloom_Scale, v.postProcess.bEnableBloom === false ? 0 : v.postProcess.Bloom_Scale ?? 1);
    words();
    const current = JSON.stringify(projectAtmosphere);
    for (const b of els.looks.querySelectorAll('button.lookcard')) b.classList.toggle('on', b.dataset.record === current);
    // the map's volumes that set its colour where the camera is inside them: named, read only
    const volumes = gradeVolumes(map), over = new Map(volumesOver(map, projectAtmosphere).map(v => [v.name, v.members]));
    els.volumes.hidden = !volumes.length;
    els.volumes.textContent = volumes.map(v => `Inside ${v.name} the game shows that volume's colour (${v.words})`
      + (over.get(v.name) ? `, over this project's ${over.get(v.name).join(', ')}` : '') + '.').join(' ');
  }

  async function showAtmosphere() {
    if (!catalogue && !catalogueWhy) {
      const reply = await ask('/atmospheres.json');
      catalogue = reply?.looks ?? null;
      catalogueWhy = catalogue ? null : 'the editor\'s server did not list them';
    }
    looks(); paint();
  }
  // What the browser checks read
  const atmosphereState = () => ({ looks: [...els.looks.querySelectorAll('button.lookcard')].map(b => ({ name: b.textContent, on: b.classList.contains('on'),
                                                                                                      record: JSON.parse(b.dataset.record) })),
                                   all: els.looks.querySelector('select')?.options.length ?? 0, fog: els.fogWords.textContent,
                                   colour: els.colourWords.textContent, changed: !els.changedChip.hidden, note: els.note.textContent,
                                   volumes: els.volumes.hidden ? '' : els.volumes.textContent, record: projectAtmosphere });
  return { atmosphereState, paintAtmosphere: paint, showAtmosphere };
}
