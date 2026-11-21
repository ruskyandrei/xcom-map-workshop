// The pose rule of ladders, doors, cars and vans (private/plans/done/cars-doors-ladders-plan.md, section 3.2), as the compiler
// has it (tools/editor/compiler.py grid_move and nearest_grid_pose). Such a piece moves by whole tiles (96 across) and
// storeys (64 up) and turns by quarter turns of yaw from where its original stands, about tile corners, with pitch and
// roll as they were: everything the map saves per tile then maps exactly. The editor's Align to game pose puts a piece
// at nearestGridPose. Both pass the cases in tools/editor/tests/pose_rule_cases.json.
// Locations are game units (x, y, z up), rotations rotator units (pitch, yaw, roll), the origin the tile grid's corner.
import { LEVEL as STOREY, QUARTER, TILE } from './constants.js';
export const POSE_SLACK = 0.5;

// Half away from zero, as the compiler rounds (game_round).
const gameRound = n => (n >= 0 ? Math.floor(n + 0.5) : Math.ceil(n - 0.5));
const tidy = v => { const r = Math.round(v * 1e4) / 1e4; return r === 0 ? 0 : r; };

/** (x, y) turned by `turns` quarter turns of yaw, as the game turns an actor (+yaw takes X towards Y). */
export function turned([x, y], turns) {
  for (let i = 0; i < ((turns % 4) + 4) % 4; i++) [x, y] = [-y, x];
  return [x, y];
}

/** How a pose moves its original: { turns (0 to 3), translation, valid, why } (why: what breaks the rule). */
export function gridMove(srcLocation, srcRotation, location, rotation, origin) {
  const dyaw = rotation[1] - srcRotation[1], turns = gameRound(dyaw / QUARTER), why = [];
  if (Math.abs(rotation[0] - srcRotation[0]) > POSE_SLACK || Math.abs(rotation[2] - srcRotation[2]) > POSE_SLACK) why.push('pitch or roll');
  if (Math.abs(dyaw - turns * QUARTER) > POSE_SLACK) why.push('quarter turns');
  const r = turned(srcLocation, turns), o = turned(origin, turns);
  const t = [location[0] - r[0], location[1] - r[1], location[2] - srcLocation[2]];
  const off = v => Math.abs(v - gameRound(v));
  if ([(o[0] + t[0] - origin[0]) / TILE, (o[1] + t[1] - origin[1]) / TILE].some(v => off(v) * TILE > POSE_SLACK)) why.push('whole tiles');
  if (off(t[2] / STOREY) * STOREY > POSE_SLACK) why.push('whole storeys');
  return { turns: ((turns % 4) + 4) % 4, translation: t, valid: !why.length, why };
}

/** The valid pose nearest a proposed one: { location, rotation }. The nearest quarter turn and storey, and in X and Y
 *  the nearest of the places c + 96·(i, j), c = o − R(o − L0). */
export function nearestGridPose(srcLocation, srcRotation, location, rotation, origin) {
  const turns = gameRound((rotation[1] - srcRotation[1]) / QUARTER);
  const ro = turned([origin[0] - srcLocation[0], origin[1] - srcLocation[1]], turns);
  const c = [origin[0] - ro[0], origin[1] - ro[1]];
  const xy = [0, 1].map(k => c[k] + TILE * gameRound((location[k] - c[k]) / TILE));
  const z = srcLocation[2] + STOREY * gameRound((location[2] - srcLocation[2]) / STOREY);
  return { location: [tidy(xy[0]), tidy(xy[1]), tidy(z)],
           rotation: [Math.trunc(srcRotation[0]), Math.trunc(srcRotation[1]) + turns * QUARTER, Math.trunc(srcRotation[2])] };
}
