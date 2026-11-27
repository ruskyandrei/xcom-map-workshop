// The time of day (the game-likeness plan's track T, stage T-S1): the project's `sun` (schema 10), pure. The curve
// (tools/viewer/sun_curve.json, which the server gives at /sun-curve.json and Python's sun_curve.py reads too) blended
// at a time, the side's arc, the time that best matches the map's own light, the curve made the map's own (its light,
// sky light, fog and grade stand at that time), the record a time and a heading make, checked and tidied, the fog and
// grade the time sets with the members changed by hand left alone, what the view draws, and the words the Map settings
// window shows.
//
// Angles: a light's height over the horizon and its side, the bearing it shines from, in degrees; the side counts from
// the game's +X (the dial's N) toward its +Y (E), clockwise seen from above as a compass does. The record's rotation is
// the light actor's, in the game's units (65536 a turn): pitch, yaw (the way it shines) and roll.
import { tidyAtmosphere, validAtmosphere } from './atmosphere_rules.js';

export const DAY = 24;
const UNIT = 65536 / 360;
const RAD = Math.PI / 180;
/** The fog and grade members the time sets (the project's `atmosphere` holds them, `sun.atmosphere` marks them). */
export const TIME_MEMBERS = [['fog', 'LightInscatteringColor'], ['fog', 'OppositeLightColor'],
                             ['postProcess', 'Scene_Colorize'], ['postProcess', 'Scene_Shadows']];
const ROW_SECTION = { fog: 'fog', postProcess: 'grade' };
const TIMES_OF_DAY = ['auto', 'day', 'night'];
const KEYS = ['time', 'heading', 'timeOfDay', 'light', 'sky', 'custom', 'atmosphere'];

const isPlain = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const finite = v => typeof v === 'number' && Number.isFinite(v);
const round = (v, digits) => Math.round(v * 10 ** digits) / 10 ** digits + 0;
const wrap = (deg) => ((deg % 360) + 360) % 360;
const lerp = (a, b, f) => (Array.isArray(a) ? a.map((v, k) => v + (b[k] - v) * f) : a + (b - a) * f);
const bytes = c => c.slice(0, 3).map(v => Math.max(0, Math.min(255, Math.round(v))));
const fromUnit = c => (c ?? [1, 1, 1]).slice(0, 3).map(v => v * 255);

// ------------------------------------------------------------------------------------------------ the curve

/** The span of the light up at time t: { light, start, end } in hours, start <= t (yesterday's start before the day's
 *  first change). */
export function spanAt(curve, t) {
  const changes = [...curve.changes].sort((a, b) => a.time - b.time);
  let k = changes.length - 1;
  changes.forEach((c, i) => { if (c.time <= t) k = i; });
  const start = changes[k].time > t ? changes[k].time - DAY : changes[k].time;
  let end = changes[(k + 1) % changes.length].time;
  while (end <= start) end += DAY;
  return { light: changes[k].light, start, end };
}
/** t moved by whole days into [start, end). */
const into = (t, span) => (t < span.start ? t + DAY : t >= span.end ? t - DAY : t);
/** The light up at time t ('sun' or 'moon'), and how far through its time up: -1 coming up, 0 at its highest, 1 going
 *  down. */
export function phaseAt(curve, t) {
  const span = spanAt(curve, t), mid = (span.start + span.end) / 2, half = (span.end - span.start) / 2;
  return { light: span.light, phase: (into(t, span) - mid) / half };
}
/** The side the light stands at, at time t, for a dial's heading (its side at its highest): a quarter turn before as
 *  it comes up, a quarter turn after as it goes down. */
export const sideAt = (curve, t, heading) => wrap(heading + 90 * phaseAt(curve, t).phase);
/** The dial's heading that puts the light at `side` at time t. */
export const headingFor = (curve, t, side) => wrap(side - 90 * phaseAt(curve, t).phase);

// A row's values as numbers to blend: colours as bytes (unrounded), the fog's colours as the export's fractions
function rowValues(row) {
  const fog = Object.fromEntries(Object.entries(row.fog ?? {}).map(([k, v]) => [k, v.slice(0, 3).map(x => x / 255)]));
  return { light: row.light, height: row.height, color: row.color.slice(0, 3), brightness: row.brightness,
           sky: { color: row.sky.color.slice(0, 3), brightness: row.sky.brightness, lowerColor: row.sky.lowerColor.slice(0, 3),
                  lowerBrightness: row.sky.lowerBrightness },
           fog, grade: { ...(row.grade ?? {}) } };
}
function blend(a, b, f) {
  const mix = (x, y) => Object.fromEntries(Object.keys(x).map(k => [k, y[k] === undefined ? x[k] : lerp(x[k], y[k], f)]));
  return { light: a.light, height: lerp(a.height, b.height, f), color: lerp(a.color, b.color, f),
           brightness: lerp(a.brightness, b.brightness, f), sky: mix(a.sky, b.sky), fog: mix(a.fog, b.fog), grade: mix(a.grade, b.grade) };
}
/** The curve at time t: { light, height, color (bytes, unrounded), brightness, sky: { color, brightness, lowerColor,
 *  lowerBrightness }, fog: { member: [r, g, b] fractions }, grade: { member: [x, y, z] } }, blended between the rows
 *  of the light up (the nearest row's values before its first row and after its last). */
export function curveAt(curve, t) {
  const span = spanAt(curve, t), at = into(t, span);
  const rows = curve.rows.filter(r => r.light === span.light).map(r => ({ row: r, time: into(r.time, span) }))
    .sort((a, b) => a.time - b.time);
  if (!rows.length) throw new Error(`the curve has no row for the ${span.light}`);
  if (at <= rows[0].time) return rowValues(rows[0].row);
  if (at >= rows.at(-1).time) return rowValues(rows.at(-1).row);
  const k = rows.findIndex(r => r.time > at);
  const a = rows[k - 1], b = rows[k];
  return blend(rowValues(a.row), rowValues(b.row), (at - a.time) / (b.time - a.time));
}

// ------------------------------------------------------------------------------------------------ the map's own

/** The map's own sun or moon, sky light, fog and grade (the export's lights and atmosphere), or null for a map with no
 *  dominant light: { rotation, height, side, color (bytes), brightness, sky | null, fog, grade, atmosphere }. */
export function ownSun(scene) {
  const lights = scene?.lights ?? [];
  const dominant = lights.find(l => l.role === 'dominant' && l.kind === 'directional');
  if (!dominant) return null;
  const sky = lights.find(l => l.kind === 'sky') ?? null;
  const d = dominant.direction;
  const world = scene?.atmosphere?.world ?? null;
  return { rotation: (dominant.rotation ?? [0, 0, 0]).slice(0, 3),
           height: Math.asin(Math.max(-1, Math.min(1, -d[2]))) / RAD, side: wrap(Math.atan2(-d[1], -d[0]) / RAD),
           color: bytes(fromUnit(dominant.color)), brightness: dominant.brightness,
           sky: sky ? { color: bytes(fromUnit(sky.color)), brightness: sky.brightness, lowerColor: bytes(fromUnit(sky.lowerColor)),
                        lowerBrightness: sky.lowerBrightness ?? 0 } : null,
           atmosphere: world ? { fog: world.fog ?? {}, postProcess: world.postProcess ?? {} } : null };
}

/** The time whose light the map's own is likest (by height, then colour times brightness), to the bar's five minutes;
 *  of two as like, the earlier. */
export function bestTime(curve, own) {
  let best = 0, bestD = Infinity;
  for (let m = 0; m < DAY * 60; m += 5) {
    const c = curveAt(curve, m / 60);
    const d = ((own.height - c.height) / 15) ** 2
      + own.color.reduce((s, v, k) => s + ((v * own.brightness - c.color[k] * c.brightness) / 128) ** 2, 0);
    if (d < bestD - 1e-9) { bestD = d; best = m / 60; }
  }
  return best;
}

/** The curve made the map's own: a row of the map's light, sky light, fog and grade at its time t0, in place of the
 *  curve's rows of the same light within an hour and a half of it, so the bar at t0 changes nothing and the values go
 *  over to the curve's away from it. */
export function mapCurve(curve, own, t0) {
  const span = spanAt(curve, t0), at = into(t0, span), c = curveAt(curve, t0);
  const kept = curve.rows.filter(r => r.light !== span.light || Math.abs(into(r.time, span) - at) >= 1.5);
  // (a row's fog colours are bytes: the map's own fractions times 255, unrounded, so the blend gives them back)
  const members = (section, from) => Object.fromEntries(Object.keys(c[ROW_SECTION[section]]).map(name => {
    const v = Array.isArray(from?.[name]) ? from[name] : c[ROW_SECTION[section]][name];
    return [name, v.slice(0, 3).map(x => x * (section === 'fog' ? 255 : 1))];
  }));
  const row = { time: t0, light: span.light, height: own.height, color: own.color.slice(), brightness: own.brightness,
                sky: own.sky ? { ...own.sky } : { ...c.sky },
                fog: members('fog', own.atmosphere?.fog), grade: members('postProcess', own.atmosphere?.postProcess) };
  return { ...curve, rows: [...kept, row].sort((a, b) => a.time - b.time), own: { time: t0 } };
}

// ------------------------------------------------------------------------------------------------ the record

/** A light's rotation (game units) for its height and side, with the roll kept. */
export function rotationOf(height, side, roll = 0) {
  const yaw = Math.round(wrap(side + 180) * UNIT);
  return [Math.round(-height * UNIT), yaw >= 32768 ? yaw - 65536 : yaw, roll];
}
const sameTurn = (a, b) => Math.abs(((a - b) % 65536 + 98304) % 65536 - 32768) <= 2;
const sameRotation = (a, b) => sameTurn(a[0], b[0]) && sameTurn(a[1], b[1]) && sameTurn(a[2] ?? 0, b[2] ?? 0);
/** The way a light of this rotation shines, in game axes. */
export function directionOf(rotation) {
  const p = rotation[0] / UNIT * RAD, y = rotation[1] / UNIT * RAD;
  return [Math.cos(p) * Math.cos(y), Math.cos(p) * Math.sin(y), Math.sin(p)];
}
const sameNumbers = (a, b, eps = 1e-4) => Array.isArray(a) ? Array.isArray(b) && a.length === b.length && a.every((v, k) => Math.abs(v - b[k]) <= eps)
  : finite(a) && finite(b) && Math.abs(a - b) <= eps;

const colour = c => Array.isArray(c) && c.length === 3 && c.every(v => Number.isInteger(v) && v >= 0 && v <= 255);
const inRange = (v, range) => finite(v) && v >= range[0] && v <= range[1];
/** Whether a record is one the page reads (the curve's limits): the bar's time and the dial's heading, the game's time
 *  of day, the light's rotation, colour and brightness, the sky light's, the values set by hand and the fog and grade
 *  the time set. */
export function validSun(record, curve) {
  if (!isPlain(record) || !Object.keys(record).every(k => KEYS.includes(k))) return false;
  const limits = curve?.limits ?? { brightness: [0, 100], skyBrightness: [0, 100] };
  const light = record.light, sky = record.sky;
  return inRange(record.time, [0, DAY]) && record.time < DAY && finite(record.heading) && TIMES_OF_DAY.includes(record.timeOfDay)
    && isPlain(light) && Array.isArray(light.rotation) && light.rotation.length === 3 && light.rotation.every(Number.isInteger)
    && colour(light.color) && inRange(light.brightness, limits.brightness)
    && (sky === undefined || (isPlain(sky) && colour(sky.color) && inRange(sky.brightness, limits.skyBrightness)
                              && colour(sky.lowerColor) && inRange(sky.lowerBrightness, limits.skyBrightness)))
    && (record.custom === undefined || (Array.isArray(record.custom) && record.custom.every(k => (curve?.custom ?? []).includes(k))))
    && (record.atmosphere === undefined || validAtmosphere(record.atmosphere));
}

const markOf = (sun, section, name) => sun?.atmosphere?.[section]?.[name];
/** What a member the time sets is now: 'time' (the project's value is the one the time set), 'custom' (changed by hand
 *  since, or set before the time touched it), or null (the map's own). */
export function memberMark(sun, atmosphere, section, name) {
  const value = atmosphere?.[section]?.[name];
  if (value === undefined) return null;
  const mark = markOf(sun, section, name);
  return mark !== undefined && sameNumbers(mark, value, 1e-6) ? 'time' : 'custom';
}
/** The marks of every member the time sets: { 'fog.LightInscatteringColor': 'time' | 'custom' | null, ... }. */
export const timeMarks = (sun, atmosphere) => Object.fromEntries(TIME_MEMBERS.map(([s, n]) => [`${s}.${n}`, memberMark(sun, atmosphere, s, n)]));

/** The record a project saves, tidied against the map's own: the fog and grade marks that are the map's own values
 *  dropped, and null when it sets nothing the map has not (its light, sky light and time of day the map's own, nothing
 *  set by hand, no mark left). A record the page can't read is carried as it is. */
export function tidySun(record, own, curve) {
  if (record == null) return null;
  if (!validSun(record, curve)) return isPlain(record) ? { ...record } : null;
  const out = { time: round(record.time, 4), heading: round(wrap(record.heading), 2), timeOfDay: record.timeOfDay,
                light: { rotation: record.light.rotation.slice(), color: record.light.color.slice(), brightness: round(record.light.brightness, 4) } };
  if (record.sky) out.sky = { color: record.sky.color.slice(), brightness: round(record.sky.brightness, 4),
                              lowerColor: record.sky.lowerColor.slice(), lowerBrightness: round(record.sky.lowerBrightness, 4) };
  if (record.custom?.length) out.custom = [...new Set(record.custom)].sort();
  const marks = tidyAtmosphere(record.atmosphere ?? null, own?.atmosphere ? { world: own.atmosphere } : null);
  if (marks) out.atmosphere = marks;
  if (!own) return out;
  const ownLight = sameRotation(out.light.rotation, own.rotation) && sameNumbers(out.light.color, own.color, 0)
    && sameNumbers(out.light.brightness, own.brightness);
  const ownSky = !out.sky || !own.sky || (sameNumbers(out.sky.color, own.sky.color, 0) && sameNumbers(out.sky.brightness, own.sky.brightness)
    && sameNumbers(out.sky.lowerColor, own.sky.lowerColor, 0) && sameNumbers(out.sky.lowerBrightness, own.sky.lowerBrightness));
  return ownLight && ownSky && out.timeOfDay === 'auto' && !out.custom && !out.atmosphere ? null : out;
}

/** The time and heading the bar and dial show for a record: the record's, or the map's own (its best time, and the
 *  heading that puts the light where the map has it). */
export function shownTime(sun, own, curve) {
  if (validSun(sun, curve)) return { time: sun.time, heading: sun.heading };
  const t0 = bestTime(curve, own);
  return { time: t0, heading: headingFor(curve, t0, own.side) };
}

/** The bar moved to `time` (and the dial to `heading`): the project's next `sun` and `atmosphere`. `curve` is the map's
 *  own (mapCurve); `before` the record now, `atmosphere` the project's fog and colour now. The values set by hand (the
 *  record's `custom`, and the fog and grade members changed in the Fog and colour section) are left as they are. */
export function timeSet(args) {
  const { record, atmosphere } = recordAt(args);
  return { sun: tidySun(record, args.own, args.curve), atmosphere };
}
// (timeSet's record before it is tidied)
function recordAt({ curve, own, before = null, atmosphere = null, time, heading, timeOfDay }) {
  const ready = validSun(before, curve) ? before : null;
  const custom = ready?.custom ?? [];
  const c = curveAt(curve, time);
  let rotation = rotationOf(c.height, sideAt(curve, time, heading), own.rotation[2] ?? 0);
  if (sameRotation(rotation, own.rotation)) rotation = own.rotation.slice();
  const light = { rotation, color: custom.includes('color') ? ready.light.color.slice() : bytes(c.color),
                  brightness: custom.includes('brightness') ? ready.light.brightness : round(c.brightness, 4) };
  const record = { time, heading, timeOfDay: timeOfDay ?? ready?.timeOfDay ?? 'auto', light };
  if (own.sky) record.sky = { color: custom.includes('skyColor') ? ready.sky.color.slice() : bytes(c.sky.color),
                              brightness: custom.includes('skyBrightness') ? ready.sky.brightness : round(c.sky.brightness, 4),
                              lowerColor: bytes(c.sky.lowerColor), lowerBrightness: round(c.sky.lowerBrightness, 4) };
  if (custom.length) record.custom = custom.slice();
  let nextAtmosphere = atmosphere;
  if (own.atmosphere) {
    const marks = { fog: { ...(ready?.atmosphere?.fog ?? {}) }, postProcess: { ...(ready?.atmosphere?.postProcess ?? {}) } };
    const next = { fog: { ...(atmosphere?.fog ?? {}) }, postProcess: { ...(atmosphere?.postProcess ?? {}) } };
    for (const [section, name] of TIME_MEMBERS) {
      if (memberMark(ready, atmosphere, section, name) === 'custom') continue;
      let value = c[ROW_SECTION[section]][name];
      if (value === undefined) continue;
      if (section === 'fog') value = [...value.slice(0, 3).map(v => round(v, 6)), own.atmosphere.fog[name]?.[3] ?? 1];
      else value = value.map(v => round(v, 6));
      marks[section][name] = value; next[section][name] = value;
    }
    record.atmosphere = marks;
    nextAtmosphere = tidyAtmosphere(next, { world: own.atmosphere });
  }
  return { record, atmosphere: nextAtmosphere };
}

/** A value set by hand (More's light and sky colours and strengths, marked as set by hand so the bar leaves them; the
 *  game's time of day): the project's next `sun`. */
export function handSet({ curve, own, before = null, atmosphere = null, key, value }) {
  const at = shownTime(before, own, curve);
  const base = validSun(before, curve) ? before : recordAt({ curve, own, atmosphere, time: at.time, heading: at.heading }).record;
  const next = structuredClone(base);
  if (key === 'color') next.light.color = bytes(value);
  else if (key === 'brightness') next.light.brightness = value;
  else if (key === 'skyColor' && next.sky) next.sky.color = bytes(value);
  else if (key === 'skyBrightness' && next.sky) next.sky.brightness = value;
  else if (key === 'timeOfDay') { next.timeOfDay = value; return tidySun(next, own, curve); }
  next.custom = [...new Set([...(next.custom ?? []), key])];
  return tidySun(next, own, curve);
}

/** "As the map has it": no record, and the fog and grade members the time set taken out of the project's atmosphere
 *  (those changed by hand stay). */
export function asTheMapHasIt(sun, atmosphere, own) {
  if (!atmosphere) return { sun: null, atmosphere: null };
  const next = { fog: { ...(atmosphere.fog ?? {}) }, postProcess: { ...(atmosphere.postProcess ?? {}) } };
  for (const [section, name] of TIME_MEMBERS) if (memberMark(sun, atmosphere, section, name) === 'time') delete next[section][name];
  return { sun: null, atmosphere: tidyAtmosphere(next, own?.atmosphere ? { world: own.atmosphere } : null) };
}

/** The game's time of day a record says: 'day' or 'night' ('auto' follows the light: night while the moon is up). */
export const gameTime = (sun, curve) => (sun.timeOfDay !== 'auto' ? sun.timeOfDay : phaseAt(curve, sun.time).light === 'moon' ? 'night' : 'day');

/** What the view draws for a record: the dominant light's direction (game axes), colour (fractions) and brightness,
 *  and the sky light's, or null for the map's own. */
export function sunView(sun) {
  if (!sun?.light || !Array.isArray(sun.light.rotation)) return null;
  const unit = c => c.map(v => v / 255);
  return { light: { direction: directionOf(sun.light.rotation), color: unit(sun.light.color), brightness: sun.light.brightness },
           sky: sun.sky ? { color: unit(sun.sky.color), brightness: sun.sky.brightness, lowerColor: unit(sun.sky.lowerColor),
                            lowerBrightness: sun.sky.lowerBrightness } : null };
}

// ------------------------------------------------------------------------------------------------ words

/** A time on the bar: "07:10". */
export function clock(t) {
  const m = Math.round(wrap(t * 15) / 15 * 60) % (DAY * 60);
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}
/** The part of the day: night while the moon is up; dawn, morning, midday, afternoon, dusk through the sun's time. */
export function partOfDay(curve, t) {
  const { light, phase } = phaseAt(curve, t);
  if (light === 'moon') return 'night';
  return phase < -0.6 ? 'dawn' : phase < -0.2 ? 'morning' : phase <= 0.2 ? 'midday' : phase <= 0.6 ? 'afternoon' : 'dusk';
}
const POINTS = ['north', 'north-north-east', 'north-east', 'east-north-east', 'east', 'east-south-east', 'south-east',
                'south-south-east', 'south', 'south-south-west', 'south-west', 'west-south-west', 'west', 'west-north-west',
                'north-west', 'north-north-west'];
/** A side as a point of the compass (the dial's N is the game's +X). */
export const compass = side => POINTS[Math.round(wrap(side) / 22.5) % 16];
/** The light in words: "Sun low in the east-north-east, warm, long shadows". */
export function lightWords(curve, sun) {
  const p = sun.light.rotation[0] / UNIT, height = -p;
  const side = wrap(sun.light.rotation[1] / UNIT + 180);
  const [r, g, b] = sun.light.color;
  const which = phaseAt(curve, sun.time).light === 'moon' ? 'Moon' : 'Sun';
  const up = height < 20 ? 'low' : height < 45 ? 'half way up' : 'high';
  const tint = b > r ? 'blue' : g < 0.75 * r ? 'warm' : 'white';
  const shadows = height < 20 ? ', long shadows' : height >= 50 ? ', short shadows' : '';
  return `${which} ${up} in the ${compass(side)}, ${tint}${shadows}`;
}

/** The bar's colours, `n` of them from 0:00 to 24:00: the light's colour at each time, darker where it is weaker or
 *  lower, and at night. */
export function barColours(curve, n = 96) {
  const out = [];
  for (let k = 0; k < n; k++) {
    const c = curveAt(curve, (k + 0.5) * DAY / n);
    const f = Math.min(1, c.brightness) * (0.35 + 0.65 * Math.sin(Math.max(0, c.height) * RAD)) * (c.light === 'moon' ? 0.55 : 1);
    out.push(`rgb(${c.color.map(v => Math.round(Math.min(255, v * f))).join(', ')})`);
  }
  return out;
}
