// Piece flags on the page (piece flags plan): the five settings of a placed piece that decide how the game's tile build
// and its mouse use it. The class table, the limits' words and which properties each role reads come from the server
// (families.json `pieceFlags`: tools/viewer/piece_flags.py contract()); this file mirrors that module's roles() and
// plan() over them, and tools/viewer/tests/piece_flag_cases.json holds both to one answer (piece_flags_test.mjs, and
// test_piece_flags.py on the Python side). These are settings, the inputs the game's filters read, not a prediction of
// the finished tiles.

export const ROLES = ['walking', 'cover', 'sight', 'floor', 'mouse'];
export const TILE_ROLES = ['walking', 'cover', 'sight', 'floor'];

const asBool = (raw, prop) => (raw[prop] === undefined || raw[prop] === null ? null : Boolean(raw[prop]));
const stateOf = v => (v === null ? 'unknown' : v ? 'on' : 'off');

/** {role: {state, value, why?, limits?}} as piece_flags.roles gives it. */
export function roles(contract, cls, raw, facts = {}) {
  const family = contract.classes[cls];
  const out = {};
  if (!family) {
    for (const r of ROLES) out[r] = { state: 'n/a', value: null, why: `the flags are not a setting of a ${cls}` };
    return out;
  }
  const kind = contract.kindWords[cls] ?? cls;
  for (const r of ROLES) {
    const why = contract.notRead[`${family}|${r}`];
    if (why !== undefined) out[r] = { state: 'n/a', value: null, why: why.includes('%s') ? why.replace('%s', kind) : why };
  }
  if (family === 'prop' && asBool(raw, 'bInteractive')) out.cover = { state: 'n/a', value: null, why: contract.limits.interactive };
  const gated = contract.gated.includes(family);
  const gate = gated ? asBool(raw, 'bIgnoreForPathing') : false;
  const occupancy = asBool(raw, 'bAlwaysConsiderForCover');
  const floorFlag = asBool(raw, 'bPathColliding'), step = asBool(raw, 'bCanStepUpOn');
  const floor = floorFlag === null || (floorFlag && step === null) ? null : Boolean(floorFlag && step);
  if (!out.walking) {
    let v;
    if (gated) v = occupancy === false ? false : occupancy === null || gate === null ? null : gate ? 'partial' : true;
    else v = occupancy;
    out.walking = v === 'partial' ? { state: 'partial', value: null } : { state: stateOf(v), value: v };
  }
  if (!out.cover) {
    const ignore = asBool(raw, 'bIgnoreForCover');
    let v = ignore === null ? null : !ignore;
    if (gated && v && gate !== false) v = gate === null ? null : false;
    out.cover = { state: stateOf(v), value: v };
  }
  if (!out.sight) {
    const block = asBool(raw, 'bBlockUnitVisibility');
    let v = block;
    if (gated && block) {
      if (gate === null) v = null;
      else if (gate) v = floor === null ? null : floor ? 'partial' : false;
    }
    out.sight = v === 'partial' ? { state: 'partial', value: null } : { state: stateOf(v), value: v };
  }
  out.floor = { state: stateOf(floor), value: floor };
  if (!out.mouse) {
    const ignore = asBool(raw, 'bIgnoreFor3DCursorCollision');
    const v = ignore === null ? null : !ignore;
    out.mouse = { state: stateOf(v), value: v };
  }
  const limits = Object.fromEntries(ROLES.map(r => [r, []]));
  if (family === 'ladder') limits.walking.push('ladder-occupancy');
  if (family === 'door') { for (const r of TILE_ROLES) limits[r].push('door-state'); limits.cover.push('height-test'); }
  if (family === 'prop') limits.cover.push('height-test');
  if (gated && gate) {
    for (const r of ['walking', 'cover', 'sight']) limits[r].push('gate');
    if (out.sight.state === 'partial') limits.sight.push('sight-floor');
  }
  if (floorFlag && step === false) limits.floor.push('stops-floor');
  if (out.floor.value && raw.bIsValidDestination === false) limits.floor.push('destination');
  if (facts.collides === false) for (const r of ROLES) limits[r].push('no-collision');
  else {
    if (facts.bodySetup === false) for (const r of ['walking', 'cover', 'sight']) limits[r].push('no-body-setup');
    if (facts.low && ['on', 'partial'].includes(out.walking.state)) limits.walking.push('low');
  }
  const assumed = new Set(facts.assumed ?? []);
  for (const r of ROLES) {
    if (out[r].state !== 'n/a' && contract.roleInputs[r].some(p => assumed.has(p))) limits[r].push('assumed');
    if (limits[r].length && out[r].state !== 'n/a') out[r].limits = limits[r];
  }
  return out;
}

/** Whether a piece with the world box [x0, x1, y0, y1, z0, z1] is too low to stop units on a map whose tiles are
 * counted from the height cornerZ (piece_flags.low_piece's twin): it reaches less than contract.stopsFrom over the
 * bottom of its level. null when either is unknown. */
export function lowPiece(contract, box, cornerZ) {
  if (!box || cornerZ === null || cornerZ === undefined) return null;
  const level = contract.level ?? 64, bottom = cornerZ + level * Math.floor((box[4] + 8 - cornerZ) / level);
  return box[5] - bottom < (contract.stopsFrom ?? 60);
}

export function states(contract, cls, raw) {
  return Object.fromEntries(Object.entries(roles(contract, cls, raw)).map(([r, v]) => [r, v.state]));
}

/** The property writes that set one role: [[property, value]]. */
export function primaryWrites(role, want) {
  if (role === 'walking') return [['bAlwaysConsiderForCover', Boolean(want)]];
  if (role === 'cover') return [['bIgnoreForCover', !want]];
  if (role === 'sight') return [['bBlockUnitVisibility', Boolean(want)]];
  if (role === 'floor') return want ? [['bPathColliding', true], ['bCanStepUpOn', true]] : [['bPathColliding', false]];
  if (role === 'mouse') return [['bIgnoreFor3DCursorCollision', !want]];
  throw Error(`no role ${role}`);
}

const roleWords = (contract, role, state) => `${contract.labels[role]} is ${state === 'partial' ? 'partly on' : state}`;

/** What a sparse request ({role: bool}) does, as piece_flags.plan gives it (writes as [[property, value]]). */
export function plan(contract, cls, raw, request, assumed = []) {
  const family = contract.classes[cls];
  const before = states(contract, cls, raw);
  const out = { before, after: { ...before }, writes: [], companions: [], effects: [], unsupported: {}, conflicts: {}, unmet: {}, tiles: false };
  if (!family) {
    for (const r of Object.keys(request)) out.unsupported[r] = `the flags are not a setting of a ${cls}`;
    return out;
  }
  const asked = {};
  let described = null;
  for (const [role, want] of Object.entries(request)) {
    if (!ROLES.includes(role) || typeof want !== 'boolean') out.unsupported[role] = 'not a setting of a piece';
    else if (before[role] === 'n/a') { described ??= roles(contract, cls, raw); out.unsupported[role] = described[role].why; }
    else asked[role] = want;
  }
  const writes = {};
  for (const [role, want] of Object.entries(asked)) for (const [p, v] of primaryWrites(role, want)) writes[p] = v;
  const gated = contract.gated.includes(family);
  const gate = gated ? raw.bIgnoreForPathing : false;
  const opened = gated && gate !== false && ['walking', 'cover', 'sight'].some(r => asked[r]);
  if (opened) writes.bIgnoreForPathing = false;
  for (const role of ROLES) {
    if (role in asked) continue;
    const now = states(contract, cls, { ...raw, ...writes })[role];
    if (now !== before[role] && ['on', 'off'].includes(before[role]) && ['cover', 'sight'].includes(role)) {
      for (const [p, v] of primaryWrites(role, before[role] === 'on')) writes[p] = v;
      out.companions.push(role);
    }
  }
  const after = states(contract, cls, { ...raw, ...writes });
  for (const role of ROLES) {
    if (role in asked || after[role] === before[role]) continue;
    if (role === 'sight' && !opened && 'floor' in asked) { out.effects.push(role); continue; }
    const by = Object.keys(asked).filter(r => asked[r] && contract.tileRoles.includes(r)).map(r => contract.labels[r]).join(' and ');
    out.conflicts[role] = `${roleWords(contract, role, before[role])} now, and ${by} opens the prop's pathing gate (bIgnoreForPathing), which turns it ${after[role]}: set ${contract.labels[role]} too`;
  }
  if (Object.keys(out.conflicts).length) return out;
  for (const [role, want] of Object.entries(asked))
    if (after[role] !== (want ? 'on' : 'off')) out.unmet[role] = `${contract.labels[role]} is ${after[role]} after the writes (an input is unknown)`;
  const assumedSet = new Set(assumed);
  out.writes = contract.props.filter(p => p in writes && (raw[p] === null || raw[p] === undefined || Boolean(raw[p]) !== writes[p] || assumedSet.has(p)))
    .map(p => [p, writes[p]]);
  out.after = after;
  out.tiles = TILE_ROLES.some(r => after[r] !== before[r]);
  return out;
}

/** The smallest part of a request that makes the same after-state (piece_flags.normalize). */
export function normalize(contract, cls, raw, request, assumed = [], collides = true) {
  const full = plan(contract, cls, raw, request, assumed);
  if (Object.keys(full.conflicts).length || Object.keys(full.unsupported).length) return { ...request };
  let keep = { ...request };
  const before = states(contract, cls, raw), assumedSet = new Set(assumed);
  for (const role of Object.keys(request)) {
    if (before[role] !== (request[role] ? 'on' : 'off') || contract.roleInputs[role].some(p => assumedSet.has(p))) continue;
    if (role === 'floor' && request[role] === false && collides === false) continue;
    const trial = Object.fromEntries(Object.entries(keep).filter(([r]) => r !== role));
    const p = plan(contract, cls, raw, trial, assumed);
    if (!Object.keys(p.conflicts).length && ROLES.every(r => p.after[r] === full.after[r])) keep = trial;
  }
  return keep;
}

/** The raw settings and the assumed properties of an export record (piece_flags.describe's). */
export function rawOf(record) {
  const raw = {}, assumed = [];
  for (const [k, [v, source]] of Object.entries(record?.raw ?? {})) { raw[k] = v; if (source === 'assumed') assumed.push(k); }
  return { raw, assumed };
}

/** [class, raw, source] of a piece made from numbers (generated kind `kind`) on a donor of class `cls` with these
 * settings, as the Build makes it: piece_flags.made_settings' twin (contract.madeGround, contract.classDefaults). */
export function madeSettings(contract, cls, raw, source, kind) {
  const g = contract.madeGround;
  if (kind !== 'ground' || !g) return [cls, { ...raw }, { ...source }];
  const next = g.retyped[cls] ?? cls, family = contract.classes[next];
  if (!family) return [next, {}, {}];
  const table = contract.classDefaults?.[next] ?? {}, outRaw = {}, outSource = {};
  for (const prop of contract.familyProps[family]) {
    if (prop in raw && (next === cls || ['actor', 'archetype'].includes(source[prop]))) { outRaw[prop] = raw[prop]; outSource[prop] = source[prop] ?? 'class'; }
    else { outRaw[prop] = table[prop] ?? false; outSource[prop] = source[prop] === 'assumed' ? 'assumed' : 'table'; }
  }
  for (const [prop, w] of Object.entries(g.always))
    if (w.classes.includes(cls) && prop in outRaw) { outRaw[prop] = w.value; outSource[prop] = 'build'; }
  for (const [prop, value] of Object.entries(g.saved))
    if (outSource[prop] === 'actor') { outRaw[prop] = value; outSource[prop] = 'build'; }
  return [next, outRaw, outSource];
}

/** [class, record] of a piece made from numbers on a donor whose export record is `record`: piece_flags.made's twin
 * (its settings as the Build makes them, simple collision of its own, and a ground shape collides). */
export function made(contract, cls, record, kind) {
  const raw = {}, source = {};
  for (const [k, [v, s]] of Object.entries(record?.raw ?? {})) { raw[k] = v; source[k] = s; }
  const [next, r, s] = madeSettings(contract, cls, raw, source, kind);
  const collides = kind === 'ground' ? true : record?.collides;
  const out = { ...record, family: contract.classes[next] ?? null, raw: Object.fromEntries(Object.keys(r).map(k => [k, [r[k], s[k]]])),
                collides, bodySetup: true };
  if (contract.classes[next]) {
    const facts = { collides, bodySetup: true, assumed: Object.keys(s).filter(k => s[k] === 'assumed') };
    out.roles = Object.fromEntries(Object.entries(roles(contract, next, r, facts)).map(([k, v]) => [k, v.state]));
  }
  return [next, out];
}

/** A project record's flags: an object of known roles, each strictly boolean (project.js validFlags is the twin). */
export const validFlags = f => f !== null && typeof f === 'object' && !Array.isArray(f)
  && Object.keys(f).length > 0 && Object.entries(f).every(([k, v]) => ROLES.includes(k) && typeof v === 'boolean');
