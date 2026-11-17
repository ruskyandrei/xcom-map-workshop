// What the Effects view says of the map's effects, sounds and lens flares (private/plans/todo/effects-and-sounds-plan.md,
// Part B, stage FX1): each one's name, its chips, the lines of its panel and whether a clear keeps it, from export 28's
// records (tools/viewer/effects_metadata.py). No three.js here: effects_view.js draws, app.js wires the view, and
// tools/viewer/tests/effects_rules_test.mjs checks these.

export const KIND_LABEL = { effect: 'Effect', sound: 'Sound', flare: 'Lens flare' };
const short = path => String(path ?? '').split('.').at(-1);
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
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
               table: 'as its class has it', unresolved: 'unknown: its archetype is in another package' };

/** The particle parameters an effect saves, as rows: [{ name, kind ('scalar', 'range', 'vector', 'colour', 'other'),
 *  text, colour ([r, g, b] 0-1 for a swatch, or null), note }]. A vector shows as a colour only where the system's
 *  parameter of that name feeds a particle's colour or the map saved it as a colour. */
export function parameterRows(r, data) {
  const offers = data?.effectSystems?.[r.system]?.offers ?? [];
  return (r.parameters ?? []).map(p => {
    const colourOffer = offers.some(o => o.name === p.name && o.kind === 'vector' && o.colour);
    const note = p.offered === 'otherKind' ? `its system reads ${p.name} as a ${p.type.includes('Scalar') ? 'vector' : 'scalar'}`
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

/** Whether a cleared map keeps a record (tools/bake/native_copy.py clear_level): every sound stays; an effect or a
 *  flare goes unless it is the landing's, its carrying piece survives the clear moved (the Build keeps a moved
 *  piece's effects), or the clear keeps the scenery outside the play area and it stands outside it.
 *  ctx: { cleared, outside(x, y): whether the clear keeps that point as outside scenery, carrierMoved: whether the
 *  piece that carries it is kept and moved }. */
export function survivesClear(r, ctx) {
  if (!ctx?.cleared || r.kind === 'sound' || r.stream) return true;
  if (r.landingActor) return true;
  if (r.carriedBy && ctx.carrierMoved) return true;
  return Boolean(ctx.outside?.(r.location[0], r.location[1]));
}
