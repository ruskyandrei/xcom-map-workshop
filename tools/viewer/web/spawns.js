// Landing zones in the page (private/plans/done/clear-map-plan.md, section 4): where a zone puts the landing's
// actors, by the offsets of LWR's landing-zone mutator (XComLZMutator), and the project's starting list made from the
// map's own landings and the install's lines. tools/viewer/spawns.py has the same rules for the compiler and the
// Build; game units, x and y across, z up.
export const DIRECTIONS = ['north', 'east', 'south', 'west'];
export const QUARTER = 16384, GROUND = 64, INSIDE_BACK = 288, TILE = 96;
export const OFFSETS = { playerStart: [8, 189, 16], volume: [0, -47, 32], frame: [0, 0, -64], point: [-240, 432, -64] };
export const SOLDIERS = [[192, 384, -16], [0, 480, -16], [192, 192, -16], [0, 288, -16], [-192, 384, -16], [-192, 192, -16]];
export const EVAC_SIZE = [480, 288, 192];
// zones whose soldier points stand this close to a landing's are one place (F-99: 41 of the install's landings)
const SAME_PLACE = 4;

export const yawOf = direction => DIRECTIONS.indexOf(direction) * QUARTER;
/** A vector [x, y, z] turned by a yaw in rotation units (v >> Rotator(0, yaw, 0)); exact for quarter turns. */
export function turn(v, yaw) {
  let c, s;
  if (yaw % QUARTER === 0) [c, s] = [[1, 0], [0, 1], [-1, 0], [0, -1]][(((yaw / QUARTER) % 4) + 4) % 4];
  else { const a = yaw * Math.PI / 32768; c = Math.cos(a); s = Math.sin(a); }
  return [v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2]];
}
/** Where the zone puts each landing actor: { frame, volume, playerStart, point: { location, yaw }, soldiers: [{
 *  location, yaw }] * 6 } (spawns.py place). */
export function place(zone) {
  const start = zone.location.map(Number), yaw = yawOf(zone.direction), out = {};
  for (const [name, d] of Object.entries(OFFSETS)) { const o = turn(d, yaw); out[name] = { location: start.map((v, k) => v + o[k]), yaw }; }
  const kind = zone.kind ?? 'normal';
  let base = start, baseYaw = yaw;
  if (kind === 'alternate' && zone.alternate) { base = zone.alternate.location.map(Number); baseYaw = yawOf(zone.alternate.direction); }
  const back = ['inside', 'alternate', 'noEvac'].includes(kind) ? INSIDE_BACK : 0, face = (baseYaw + QUARTER) % 65536;
  out.soldiers = SOLDIERS.map(d => { const o = turn([d[0], d[1] - back, d[2]], baseYaw); return { location: base.map((v, k) => v + o[k]), yaw: face }; });
  return out;
}
export const groundOf = zone => Number(zone.location[2]) - GROUND;
/** The evac zone's box [x0, y0, z0, x1, y1, z1], about the volume's place, turned by the zone. */
export function evacBox(zone) {
  const { location: [x, y, z], yaw } = place(zone).volume;
  let [hx, hy] = [EVAC_SIZE[0] / 2, EVAC_SIZE[1] / 2];
  if ((yaw / QUARTER) % 2) [hx, hy] = [hy, hx];
  return [x - hx, y - hy, z - EVAC_SIZE[2] / 2, x + hx, y + hy, z + EVAC_SIZE[2] / 2];
}
/** The zone whose frame stands at `location`, turned by `yaw`. */
export const zoneOfFrame = (location, yaw) => ({ location: [location[0], location[1], location[2] + GROUND],
  direction: DIRECTIONS[(((Math.round(yaw / QUARTER)) % 4) + 4) % 4], kind: 'normal' });
/** The zone that best fits a landing with no drop zone frame (spawns.py fit_zone, the twin): the direction whose
 *  soldier offsets leave the least worst distance across from the points' mean place (ties to the first), the place
 *  whole units (halves up), its ground the lowest of each point's height less 48 and the PointInSpace's height.
 *  null without soldier points. */
export function fitZone(actors, bottom = null) {
  const by = Object.fromEntries((actors ?? []).map(a => [a.role, a]));
  const ns = [1, 2, 3, 4, 5, 6].filter(n => by[`soldier${n}`]);
  if (!ns.length) return null;
  const points = ns.map(n => by[`soldier${n}`].location), offsets = ns.map(n => SOLDIERS[n - 1]);
  let best = null;
  for (const direction of DIRECTIONS) {
    const yaw = yawOf(direction), offs = offsets.map(d => turn(d, yaw));
    const start = [0, 1].map(k => { let sum = 0; points.forEach((p, i) => { sum += p[k] - offs[i][k]; }); return sum / points.length; });
    let worst = 0;
    points.forEach((p, i) => { for (const k of [0, 1]) worst = Math.max(worst, Math.abs(p[k] - start[k] - offs[i][k])); });
    if (!best || worst < best.worst) best = { worst, direction, start };
  }
  const lows = [...points.map(p => p[2] - (GROUND - 16)), ...(by.point ? [by.point.location[2]] : [])];
  let ground = Math.min(...lows);
  // on the grid: down to the start of its level, where LWR's lines put a zone's ground (spawns.py fit_zone)
  if (bottom !== null && bottom !== undefined) ground = bottom + Math.floor((ground - bottom + 2) / 64) * 64;
  return { location: [Math.floor(best.start[0] + 0.5), Math.floor(best.start[1] + 0.5), Math.floor(ground + 0.5) + GROUND],
           direction: best.direction, kind: 'normal' };
}
/** Whether a zone stands where the map's own landing `own` has it (the same direction, the place within half a unit). */
const atOwnPlace = (zone, own) => Boolean(own) && zone.direction === own.zone.direction
  && [0, 1, 2].every(k => Math.abs(Number(zone.location[k]) - Number(own.zone.location[k])) < 0.5);
/** Whether a zone leaves the map's own landing `own` where the map has it, as the Build reckons it
 *  (tools/bake/native_spawns.py unmoved): the same direction, and the frame and the six soldier points within
 *  SAME_PLACE units of the landing's own; a landing with no frame, its fitted zone within half a unit (atOwnPlace).
 *  (The install's line a landing is joined with can stand a unit off its frame: the Bar's, 719 against 719.9998.) */
export function landingUnmoved(zone, own) {
  if (!own) return false;
  if (own.fitted) return atOwnPlace(zone, own);
  if (zone.direction !== own.zone.direction) return false;
  const at = place(zone), mine = place(own.zone), by = Object.fromEntries((own.landing?.actors ?? []).map(a => [a.role, a]));
  const near = (a, b) => a.every((v, j) => Math.abs(Number(v) - b[j]) <= SAME_PLACE);
  return near(by.frame?.location ?? mine.frame.location, at.frame.location)
    && at.soldiers.every((p, k) => near(by[`soldier${k + 1}`]?.location ?? mine.soldiers[k].location, p.location));
}
/** Where the squad stands for a zone: [{ location, yaw }], place()'s six, or for a landing with no frame whose zone
 *  has not moved, the landing's own points (spawns.py soldier_spots). */
export function soldierSpots(zone, own = null) {
  if (own?.fitted && atOwnPlace(zone, own)) {
    const by = Object.fromEntries((own.landing?.actors ?? []).map(a => [a.role, a]));
    return [1, 2, 3, 4, 5, 6].filter(n => by[`soldier${n}`]).map(n => ({ location: [...by[`soldier${n}`].location], yaw: by[`soldier${n}`].rotation[1] }));
  }
  return place(zone).soldiers;
}
const keptForMission = z => Boolean(z.missionType || z.councilType);
/** Whether the list says which zones plain EW plays (`ew: true`, the panel's Plain EW) rather than by order. */
export const explicitEw = zones => zones.some(z => 'ew' in z);
/** The indices of the zones that are also the map's own landings (spawns.py own_slots): those marked `ew: true`, the
 *  first ownCount of them; a list with none marked goes by order (the first zones that name no mission). */
export function ownSlots(zones, ownCount) {
  if (explicitEw(zones)) return zones.flatMap((z, k) => (z.ew === true ? [k] : [])).slice(0, ownCount);
  const out = [];
  zones.forEach((z, k) => { if (out.length < ownCount && !keptForMission(z)) out.push(k); });
  return out;
}
/** Whether two zones put their soldiers at the same places, within `slack` units. */
export function samePlace(a, b, slack = SAME_PLACE) {
  const pa = place(a).soldiers, pb = place(b).soldiers;
  return pa.every((p, k) => p.location.every((v, j) => Math.abs(v - pb[k].location[j]) <= slack));
}
/** The map's own landings as zones (export 22's `landings`, else its drop zone frames by actor name; spawns.py
 *  own_landings): [{ zone, group, frame, landing }]; a landing with no frame (fitZone) has frame null and fitted true. */
export function ownLandings(scene) {
  if (Array.isArray(scene.landings)) {
    const bottom = scene.tileGrid?.origin?.[2] ?? null;
    return scene.landings.map(l => {
      const frame = l.actors?.find(a => a.role === 'frame');
      if (frame) return { zone: zoneOfFrame(frame.location, frame.rotation[1]), group: l.group, frame: frame.path, landing: l };
      const zone = fitZone(l.actors, bottom);
      return zone ? { zone, group: l.group, frame: null, landing: l, fitted: true } : null;
    }).filter(Boolean);
  }
  const seen = new Set();
  return (scene.objects ?? []).filter(o => o.layer === 'base' && String(o.archetype ?? '').split('.').at(-1) === 'SoldierSpawns_DrpshipVol_12Arc0')
    .sort((a, b) => a.actor.localeCompare(b.actor)).filter(o => !seen.has(o.actor) && seen.add(o.actor))
    .map(o => ({ zone: zoneOfFrame(o.location, o.rotation[1]), group: null, frame: o.actor, landing: null }));
}
/** The project's starting list (the plan's rule 3): the map's own landings first, each joined with the install's
 *  line at the same place and marked `ew: true` (plain EW plays it), then the install's other lines in their order. A
 *  landing no line matches is a zone with `lwr: false`, so that the list unchanged gives LWR the lines it had. Each
 *  zone gets an id from `makeId`. */
export function startingZones(own, lines, makeId) {
  const used = new Set(), out = [];
  for (const o of own) {
    const k = lines.findIndex((l, i) => !used.has(i) && !keptForMission(l) && samePlace(l, o.zone));
    if (k >= 0) { used.add(k); out.push({ id: makeId(), ...lines[k], ew: true }); }
    else out.push({ id: makeId(), ...o.zone, lwr: false, ew: true });
  }
  lines.forEach((l, i) => { if (!used.has(i)) out.push({ id: makeId(), ...l }); });
  return out;
}
