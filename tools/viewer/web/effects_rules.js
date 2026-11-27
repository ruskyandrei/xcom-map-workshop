// What the Effects view says of the map's effects, sounds and lens flares (private/plans/done/effects-and-sounds-plan.md,
// Part B, stage FX1): each one's name, its chips, the lines of its panel and whether a clear keeps it, from export 28's
// records (tools/viewer/effects_metadata.py). No three.js here: effects_view.js draws, effects_wiring.js wires the view, and
// tools/viewer/tests/effects_rules_test.mjs checks these.
import { plural } from './dom_words.js';

export const KIND_LABEL = { effect: 'Effect', sound: 'Sound', flare: 'Lens flare' };
// a name's last part, as dom_words.js' short, but '' for a missing path (null or undefined)
const short = path => String(path ?? '').split('.').at(-1);
const round = (v, places = 2) => Number(Number(v).toFixed(places));
const number = v => (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('en-GB') : String(round(v)));

/** The records of an export, the map's own and those of the streams in `streams` (a Set of names, or null for none). */
export function effectRecords(data, streams = null) {
  const out = [...(data?.effects ?? []), ...(data?.sounds ?? []), ...(data?.flares ?? [])].filter(r => r.kind);
  for (const [name, s] of Object.entries(data?.streams ?? {})) {
    if (!streams?.has(name)) continue;
    out.push(...(s.effects ?? []), ...(s.sounds ?? []), ...(s.flares ?? []));
  }
  return out;
}

/** What a record is called: an effect by its particle system, a sound by its wave, a flare by its template. */
export function recordName(r, data) {
  if (r.kind === 'effect') return r.template ? short(r.template) : 'No particle system';
  if (r.kind === 'flare') return r.template ? short(r.template) : 'No flare template';
  const waves = (r.waves ?? []).map(w => data?.soundWaves?.[w]?.name ?? short(String(w).split('|').at(-1)));
  return waves.length ? waves.join(', ') : 'No sound set';
}

function buildingWords(data, entry) {
  const b = (data?.buildings ?? []).find(x => x.id === entry.building);
  return `${b ? b.actor : 'a building'}, floor ${entry.floor}`;
}

/** The chips a record shows: [{ text, title }]. */
export function recordChips(r, data) {
  const out = [];
  const sound = r.kind === 'sound';
  if (r.stream) out.push({ text: `Stream: ${r.stream}`, title: 'The streamed level\'s own, shown for the mission the header\'s Mission picker shows. The editor doesn\'t change it' });
  if (r.listed === false) out.push({ text: 'Not loaded', title: 'It isn\'t in the level\'s actor list, so the game doesn\'t load it' });
  if (r.startsOn === false) {
    out.push({ text: 'Starts off', title: sound ? 'It is saved not to play when the mission starts: only the mission\'s script starts it, if anything does'
                                                 : 'Its particles are saved not to start with the mission: only the mission\'s script starts them, if anything does' });
  }
  if (r.referencedBy?.length) out.push({ text: 'Named by the mission\'s script', title: r.referencedBy.join('; ') });
  if (r.landingRole) out.push({ text: 'The landing\'s', title: 'One of the landing\'s actors: it moves with its zone in the Landing zones view' });
  else if (r.carriedBy) out.push({ text: `Carried by ${short(r.carriedBy)}`, title: 'It stands at that piece\'s own place: the Build moves, copies and deletes it with the piece' });
  for (const f of r.floors ?? []) {
    out.push({ text: `Hides with ${buildingWords(data, f)}`, title: 'The game hides it when the camera cuts that floor away (the floor lists it)' });
  }
  if (r.prefab) out.push({ text: 'Placed by a prefab', title: `${r.prefab} placed it with the other actors of its prefab` });
  if (r.attachedTo) out.push({ text: `Rides on ${short(r.attachedTo.actor)}`, title: `It is attached to ${short(r.attachedTo.actor)}${r.attachedTo.bone ? ` (bone ${r.attachedTo.bone})` : ''} and moves with it` });
  if (sound && !(r.waves ?? []).length) out.push({ text: 'No sound set', title: r.noSound ? `Silent: ${r.noSound}` : 'Silent: it plays no wave' });
  if (sound && r.cue && !r.cue.private) {
    out.push({ text: 'Shared cue', title: `Its cue, ${short(r.cue.path)}, is a game asset${r.cue.sharedBy ? `: ${plural(r.cue.sharedBy + 1, 'sound')} of the map play it` : ''}` });
  }
  if (r.kind !== 'sound' && r.hidden) out.push({ text: 'Hidden', title: 'It is saved hidden: the game doesn\'t draw it until something shows it' });
  return out;
}

const FROM = { actor: 'as saved', cue: 'as its cue saves it', archetype: 'as its archetype has it', class: 'as its class has it',
               table: 'as its class has it', unresolved: 'unknown: its archetype is in another package', edited: 'as set here' };

/** The particle parameters an effect saves, as rows: [{ name, kind ('scalar', 'range', 'vector', 'colour', 'other'),
 *  text, colour ([r, g, b] 0-1 for a swatch, or null), note }]. A vector shows as a colour only where the system's
 *  parameter of that name feeds a particle's colour, its name says it is one, or the map saved it as a colour. */
export function parameterRows(r, data) {
  const offers = data?.effectSystems?.[r.system]?.offers ?? [];
  return (r.parameters ?? []).map(p => {
    const colourOffer = colourNamed(p.name) || offers.some(o => o.name === p.name && o.kind === 'vector' && o.colour);
    // (the game reads it all the same: a number on each axis of the vector, EXP-70 run 2)
    const note = p.offered === 'otherKind' ? `its system reads ${p.name} as a ${p.type.includes('Scalar') ? 'vector, and takes this number for each part of it' : 'scalar'}`
      : p.offered === 'no' ? 'its system has no parameter of that name' : null;
    if (p.colour) return { name: p.name ?? '(no name)', kind: 'colour', text: p.colour.slice(0, 3).map(v => round(v)).join(', '), colour: p.colour.slice(0, 3), note };
    if (p.vector) {
      const colour = colourOffer ? p.vector.map(v => Math.max(0, Math.min(1, v))) : null;
      return { name: p.name ?? '(no name)', kind: colour ? 'colour' : 'vector', text: p.vector.map(v => round(v)).join(', '), colour, note };
    }
    if (p.scalar != null && p.scalarLow != null) return { name: p.name ?? '(no name)', kind: 'range', text: `${round(p.scalarLow)} to ${round(p.scalar)}`, colour: null, note };
    if (p.scalar != null) return { name: p.name ?? '(no name)', kind: 'scalar', text: String(round(p.scalar)), colour: null, note };
    return { name: p.name ?? '(no name)', kind: 'other', text: p.actor ? short(p.actor) : p.material ? short(p.material) : '—', colour: null, note };
  });
}

/** Where a sound is heard, for its spheres: { inner, outer } in game units, or null where its values don't give
 *  them (no attenuation, no values read). */
export function soundReach(r) {
  const v = r?.values ?? {};
  if (r?.kind !== 'sound' || v.attenuate === false || !(v.radiusMax > 0)) return null;
  return { inner: Math.max(0, Math.min(v.radiusMin ?? 0, v.radiusMax)), outer: v.radiusMax };
}

const EMITTER_KINDS = { sprite: 'sprites', mesh: 'mesh particles', ribbon: 'ribbons', beam: 'beams', trail: 'trails' };

/** The panel's lines for a record: { title, lines }. */
export function recordLines(r, data) {
  const lines = [`${short(r.actor)} (${r.actorClass}${r.stream ? `, ${r.stream}` : ''}).`];
  const from = src => FROM[src] ?? 'as saved';
  if (r.kind === 'effect') {
    const system = data?.effectSystems?.[r.system];
    if (r.template) lines.push(`Plays ${r.template}${system ? `: ${plural(system.emitters.filter(e => e.lods).length, 'emitter')}`
      + ` (${[...new Set(system.emitters.filter(e => e.lods).map(e => EMITTER_KINDS[e.kind] ?? e.kind))].join(', ')})` : ''}.`);
    else lines.push('It plays no particle system.');
    if (r.startsOn != null) lines.push(r.startsOn ? `Starts with the mission (${from(r.startsOnFrom)}).` : `Starts off (${from(r.startsOnFrom)}).`);
    const s = r.scale ?? [1, 1, 1];
    if (s.some(v => Math.abs(v - 1) > 1e-3)) lines.push(new Set(s.map(v => round(v, 3))).size === 1 ? `Drawn at ${round(s[0], 3)} times its size.`
      : `Drawn at ${s.map(v => round(v, 3)).join(' × ')} times its size (unevenly).`);
    const box = system?.fixedBox;
    if (box?.used && box.valid) lines.push(`Its box is the system's fixed bounds: ${box.min.map((v, k) => number(box.max[k] - v)).join(' × ')} units before scaling.`);
    else lines.push('Bounds unavailable: its system saves no fixed box, so the game works its size out as it plays.');
    if (r.lit) lines.push('Its particles are lit by the map\'s lights (it has a light environment of its own).');
  } else if (r.kind === 'sound') {
    const waves = (r.waves ?? []).map(w => data?.soundWaves?.[w]).filter(Boolean);
    for (const w of waves) {
      lines.push(`Plays ${w.path}: ${w.seconds != null ? `${round(w.seconds, 1)} s, ` : ''}${w.channels === 1 ? 'mono' : w.channels === 2 ? 'stereo' : `${w.channels} channels`}`
        + `${w.rate ? `, ${Number(w.rate).toLocaleString('en-GB')} samples a second` : ''}.`);
    }
    if (!waves.length) lines.push(`Silent: ${r.noSound ?? 'it plays no wave'}.`);
    if (r.cue) lines.push(r.cue.private ? 'Its cue is its own.' : `Its cue is ${r.cue.path}, a game asset${r.cue.sharedBy ? ` that ${plural(r.cue.sharedBy, 'other sound')} of the map play${r.cue.sharedBy === 1 ? 's' : ''} too` : ''}.`);
    if (r.startsOn != null) lines.push(r.startsOn ? `Plays from the start (${from(r.startsOnFrom)}).` : `Starts off (${from(r.startsOnFrom)}): the mission's script starts it, if anything does.`);
    const v = r.values ?? {}, reach = soundReach(r);
    if (reach) lines.push(`Heard at full volume within ${number(reach.inner)} units, fading out by ${number(reach.outer)} (${from(r.valuesFrom?.radiusMax)}).`);
    else if (v.attenuate === false) lines.push('Heard at one volume however far away (it doesn\'t fade with distance).');
    if (v.volumeMin != null) lines.push(`Volume ${v.volumeMin === v.volumeMax ? round(v.volumeMin) : `${round(v.volumeMin)} to ${round(v.volumeMax)}`}`
      + `, pitch ${v.pitchMin === v.pitchMax ? round(v.pitchMin) : `${round(v.pitchMin)} to ${round(v.pitchMax)}`}.`);
  } else {
    lines.push(r.template ? `Shows ${r.template}.` : 'It names no flare template.');
    if (r.colour) lines.push(`Its colour is ${r.colour.slice(0, 3).map(v => round(v)).join(', ')}${r.colour[3] != null ? `, strength ${round(r.colour[3])}` : ''}.`);
  }
  if (r.referencedBy?.length) {
    const by = r.referencedBy;
    lines.push(`The mission's script names it: ${by.slice(0, 6).join('; ')}${by.length > 6 ? `; and ${by.length - 6} more` : ''}.`);
  }
  // what the editor may not do with it, where its own data says so (the same reason for every capability shows once)
  const why = [...new Set(Object.entries(r.why ?? {}).filter(([k]) => k !== 'audition').map(([, v]) => v))];
  if (why.length && Object.entries(r.can ?? {}).every(([k, v]) => k === 'audition' || !v)) lines.push(`View only: ${why[0]}.`);
  return { title: `${KIND_LABEL[r.kind] ?? r.kind}: ${recordName(r, data)}`, lines };
}

// ---------------------------------------------------------------- values (the effects and sounds plan, stage FX5)
// What a value may be, as the compiler checks it (effect_edits.py EFFECT_SCALE, SOUND_RADIUS_MAX, SOUND_VOLUME_MAX,
// SOUND_PITCH, PARAMETER_MAX)
export const VALUE_LIMITS = { scale: [1 / 64, 64], radius: [0, 65536], volume: [0, 16], pitch: [1 / 16, 16], parameter: 1e6 };
const PARAMETER_TYPES = { PSPT_Scalar: 'scalar', PSPT_Vector: 'vector', PSPT_Color: 'colour' };
/** Whether a parameter's name says it is a colour (Color, Colour, Tint): a vector of that name is shown and edited as
 *  a colour whatever its system reads it with (P_Power_Core_Persistent's Color scales its colour over life). */
export const colourNamed = name => /colou?r|tint/i.test(String(name ?? ''));
const clean = v => Number(Number(v).toPrecision(6));

/** The parameters of an effect as the panel offers them: [{ name, control ('scalar', 'vector', 'tint': a vector that
 *  feeds a particle's colour or is named for one, shown as a colour and a strength, 'colour': saved as a colour),
 *  channels (a vector read by a colour module: its parts are red, green, blue), type (the PSPT_ type an
 *  edit writes), base (the value as the map has it: the saved entry's, else the system's own constant), value (as
 *  edited), guide ([least, most] for a slider, a scalar's), edited, readOnly (why it can't change, or null) }]. A
 *  parameter its effect saves keeps the type it is saved in (the first entry of the name, as the game reads it); one
 *  it doesn't save is offered in the kind its system's distribution has. Sorted: saved ones first, as saved. */
export function parameterControls(r, systems, edits = {}) {
  const offers = systems?.[r?.system]?.offers ?? [];
  const byName = new Map();
  for (const o of offers) { if (!byName.has(o.name)) byName.set(o.name, []); byName.get(o.name).push(o); }
  const out = [], seen = new Set();
  const tinted = name => { const vs = (byName.get(name) ?? []).filter(o => o.kind === 'vector'); return colourNamed(name) || (vs.length > 0 && vs.every(o => o.colour)); };
  const guideOf = (name, value) => {
    const o = (byName.get(name) ?? []).find(x => x.kind === 'scalar');
    let lo = 0, hi = 1;
    if (o && !String(o.modes?.[0] ?? '').includes('Direct') && o.input?.[1] > o.input?.[0]) [lo, hi] = o.input;
    else { const c = Math.abs(Number(o?.constant ?? 1)); hi = Math.max(1, 2 * c, 2 * Math.abs(value)); lo = Math.min(0, value); }
    return [Math.min(lo, value), Math.max(hi, value)];
  };
  const row = (name, type, base, readOnly = null) => {
    const control = type === 'PSPT_Vector' && tinted(name) ? 'tint' : PARAMETER_TYPES[type] ?? 'other';
    const edited = Object.prototype.hasOwnProperty.call(edits, name) && !readOnly;
    const value = edited ? edits[name] : base;
    // (a vector its system reads in a colour module that is no colour itself, a colour scale such as Brightness: its
    // three numbers are red, green and blue, not x, y and z)
    const channels = control === 'vector' && (byName.get(name) ?? []).some(o => o.kind === 'vector' && /Color/.test(String(o.module ?? '')));
    return { name, control, type, base, value, edited, readOnly, channels, guide: control === 'scalar' ? guideOf(name, Number(value)) : null };
  };
  for (const p of r?.parameters ?? []) {
    if (!p.name || seen.has(p.name)) continue;
    seen.add(p.name);
    if (!PARAMETER_TYPES[p.type]) { out.push(row(p.name, p.type, null, `it is a ${String(p.type).replace('PSPT_', '').toLowerCase()} parameter, kept as the map has it`)); continue; }
    // (a colour saved with a vector and no colour field, as URB_Bar's webbing's, shows that vector: effects_sim.parametersOf)
    const base = p.type === 'PSPT_Scalar' ? p.scalar ?? 0 : p.type === 'PSPT_Vector' ? [...(p.vector ?? [0, 0, 0])]
      : [...(p.colour ?? (p.vector ? [...p.vector.slice(0, 3), 1] : [0, 0, 0, 0]))];
    out.push(row(p.name, p.type, base));
  }
  for (const [name, list] of [...byName].sort((a, b) => a[0].localeCompare(b[0]))) {
    if (seen.has(name)) continue;
    const kinds = new Set(list.map(o => o.kind));
    if (kinds.size > 1) { out.push(row(name, 'PSPT_None', null, 'its system reads it both as a number and as a vector')); continue; }
    const o = list[0];
    out.push(row(name, o.kind === 'scalar' ? 'PSPT_Scalar' : 'PSPT_Vector', o.kind === 'scalar' ? Number(o.constant ?? 0) : [...(o.constant ?? [0, 0, 0])]));
  }
  return out;
}

/** A tint's colour and strength from a vector ([r, g, b], any size): { colour ([r, g, b], 0 to 1), strength }. */
export function tintOf(v) {
  const strength = Math.max(...v.map(x => Math.abs(x)), 0);
  return { colour: strength > 0 ? v.map(x => Math.max(0, x) / strength) : [1, 1, 1], strength: clean(strength) };
}
/** And back: the vector a tint's colour and strength make. */
export const tintVector = (colour, strength) => colour.map(c => clean(c * strength));

/** The record as the project has it: `r` with `values` (an effect's { scale, startsOn, parameters: {name: value} }, a
 *  sound's { radiusMin, radiusMax, volume, pitch, startsOn }) put on it, what they set said to be set here. */
export function withValues(r, values, systems) {
  if (!values || !Object.keys(values).length) return r;
  const out = { ...r };
  if (values.startsOn != null) Object.assign(out, { startsOn: values.startsOn, startsOnFrom: 'edited' });
  if (r.kind === 'effect') {
    if (values.scale != null) {
      const m = Number(values.scale);
      Object.assign(out, { drawScale: (r.drawScale ?? 1) * m, scale: (r.scale ?? [1, 1, 1]).map(v => v * m) });
    }
    const edits = values.parameters ?? {};
    if (Object.keys(edits).length) {
      const params = (r.parameters ?? []).map(p => ({ ...p }));
      for (const c of parameterControls(r, systems, edits)) {
        if (!c.edited) continue;
        const field = { scalar: 'scalar', vector: 'vector', tint: 'vector', colour: 'colour' }[c.control];
        const at = params.find(p => p.name === c.name);
        if (at) at[field] = Array.isArray(c.value) ? [...c.value] : c.value;
        else params.push({ name: c.name, type: c.type, [field]: Array.isArray(c.value) ? [...c.value] : c.value, offered: 'yes' });
      }
      Object.assign(out, { parameters: params, parametersFrom: 'edited' });
    }
    return out;
  }
  if (r.kind === 'sound') {
    const v = { ...(r.values ?? {}) }, from = { ...(r.valuesFrom ?? {}) };
    for (const k of ['radiusMin', 'radiusMax']) if (values[k] != null) { v[k] = values[k]; from[k] = 'edited'; }
    for (const k of ['volume', 'pitch']) if (values[k]) { [v[`${k}Min`], v[`${k}Max`]] = values[k]; from[`${k}Min`] = from[`${k}Max`] = 'edited'; }
    Object.assign(out, { values: v, valuesFrom: from });
  }
  return out;
}

/** The values object a project saves for an effect or a sound (its `effect` or `sound`, without `follow`): only what
 *  is set, the parameters as [{name, value}] sorted by name; null when nothing is. */
export function savedValues(values) {
  if (!values) return null;
  const out = {};
  for (const [k, v] of Object.entries(values)) {
    if (v == null) continue;
    if (k === 'parameters') {
      const list = Object.entries(v).sort((a, b) => a[0].localeCompare(b[0])).map(([name, value]) => ({ name, value: Array.isArray(value) ? [...value] : value }));
      if (list.length) out.parameters = list;
    } else out[k] = Array.isArray(v) ? [...v] : v;
  }
  return Object.keys(out).length ? out : null;
}
/** And back: a saved values object (an override's or a copy's `effect` or `sound`) as the page keeps it. */
export function keptValues(saved) {
  if (!saved || typeof saved !== 'object') return null;
  const out = {};
  for (const [k, v] of Object.entries(saved)) {
    if (k === 'follow' || v == null) continue;
    if (k === 'parameters') {
      if (Array.isArray(v) && v.length) out.parameters = Object.fromEntries(v.filter(p => p && typeof p.name === 'string').map(p => [p.name, Array.isArray(p.value) ? [...p.value] : p.value]));
    } else out[k] = Array.isArray(v) ? [...v] : v;
  }
  return Object.keys(out).length ? out : null;
}

/** Why the values of `r` (an original's record, or a copy's original) can't be set here, or null. */
export function valuesViewOnly(r) {
  if (r?.stream) return `it belongs to the stream ${r.stream}`;
  if (r?.kind === 'flare') return 'a lens flare\'s template and colour aren\'t edited';
  return r?.can?.values ? null : (r?.why?.values ?? 'the map\'s export doesn\'t say its values can change');
}

/** Whether a cleared map keeps a record (tools/bake/native_copy.py clear_level): an effect, a sound or a flare goes
 *  unless it is the landing's (the Skyranger's lights, dust and sound stay with it), the project moved it itself or
 *  its carrying piece survives the clear moved (the Build keeps both), or the clear keeps the scenery outside the play
 *  area and it stands outside it. (A copy is made after the clear: it always stays. Sounds stayed too before
 *  18 November 2026, when a cleared Bar's jukebox and hum were found left in its play area.)
 *  ctx: { cleared, outside(x, y): whether the clear keeps that point as outside scenery, carrierMoved: whether the
 *  piece that carries it is kept and moved, moved: whether the project moves it itself }. */
export function survivesClear(r, ctx) {
  if (!ctx?.cleared || r.stream) return true;
  if (r.landingActor || ctx.moved) return true;
  if (r.carriedBy && ctx.carrierMoved) return true;
  return Boolean(ctx.outside?.(r.location[0], r.location[1]));
}

/** How far outside a floor's box an effect a Build moves or adds may stand and be listed by it (native_effects.SLACK). */
export const FLOOR_SLACK = 2;
/** The building floors that list an effect, as a Build leaves them (native_effects.floor_lists): its own listings
 *  (the export's `floors`: { building: an id of the export's buildings, floor }) where it stands as the map saves it;
 *  where `moved` (moved, copied or added) each upper floor (index 1 up) one of whose boxes holds `at` (game units)
 *  within FLOOR_SLACK. `buildings`: the export's. */
export function effectFloors(record, buildings, at, moved) {
  if (!moved) return record.floors ?? [];
  const out = [];
  for (const b of buildings ?? []) {
    (b.floors ?? []).forEach((floor, k) => {
      if (k < 1) return;
      const holds = (floor.boxes ?? []).some(v => [0, 1, 2].every(a => v.min[a] - FLOOR_SLACK <= at[a] && at[a] <= v.max[a] + FLOOR_SLACK));
      if (holds) out.push({ building: b.id, floor: k });
    });
  }
  return out;
}
/** Whether the game draws an effect listed on `floors` with the Floor picker at `picked` ('all', or the floor shown,
 *  from 1): a floor cut away hides what it lists, the floors run top to bottom so a building's lowest listing decides,
 *  as for a piece (cutaway.js), and an effect no floor lists always shows. */
export function shownOnFloor(floors, picked) {
  if (picked === 'all' || picked == null || !floors?.length) return true;
  const idx = Number(picked) - 1, lowest = new Map();
  for (const f of floors) if (!lowest.has(f.building) || f.floor < lowest.get(f.building)) lowest.set(f.building, f.floor);
  return [...lowest.values()].some(f => f <= idx);
}
