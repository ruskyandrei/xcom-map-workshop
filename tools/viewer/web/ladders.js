// A ladder's climb ends, as tools/viewer/ladders.py has them (its ends(); private/plans/done/cars-doors-ladders-plan.md 2.1 and
// 5.2): the foot tile (the tile of B = L − 16·fwd + (0, 0, 8)) must have floor, and the top tile (of T = L + 76·fwd +
// (0, 0, h + 8), h = 2 × (the mesh's bounds extent z + 1)) or the tile below it must have floor too: that one, T′,
// gets the down link. The compiler warns of a ladder copy that fails (ladder-climb); the inspector marks both ends.
// (exported for tests/twin_constants_test.mjs, which holds them to tests/twin_constants.json as ladders.py's)
export const TOP_REACH = 76, FOOT_BACK = 16, END_LIFT = 8, TURN = 65536;
// A flat piece the project adds is expected to give floor, as the compiler has it (floor_edits.py added_floors;
// EXP-45): no more than FLOOR_THICK high, with HEADROOM clear over a tile (F-71).
export const FLOOR_THICK = 40, HEADROOM = 150;

/** The floor the project's own pieces are expected to give: a Set of 'x,y,z' tiles. `boxes`: the world boxes
 *  [x0, x1, y0, y1, z0, z1] of the pieces the project adds or moves (no ladders). A flat one gives each tile whose
 *  centre it covers, at the level of its top, unless another hangs less than HEADROOM over it there. */
export function addedFloors(boxes, origin, dimensions) {
  const flat = boxes.filter(Boolean), out = new Set();
  for (const b of flat) {
    if (b[5] - b[4] > FLOOR_THICK) continue;
    const z = Math.floor((b[5] + 2 - origin[2]) / 64);
    if (z < 0 || (dimensions && z >= dimensions[2])) continue;
    for (let x = Math.ceil((b[0] - origin[0]) / 96 - 0.5); x <= Math.floor((b[1] - origin[0]) / 96 - 0.5); x++) {
      for (let y = Math.ceil((b[2] - origin[1]) / 96 - 0.5); y <= Math.floor((b[3] - origin[1]) / 96 - 0.5); y++) {
        const cx = origin[0] + 96 * (x + 0.5), cy = origin[1] + 96 * (y + 0.5);
        const over = flat.some(o => o !== b && o[0] <= cx && cx <= o[1] && o[2] <= cy && cy <= o[3] && b[5] + 8 < o[4] && o[4] < b[5] + HEADROOM);
        if (!over) out.add(`${x},${y},${z}`);
      }
    }
  }
  return out;
}

/** The climb's top and foot points for a ladder at `location` turned `rotation` (rotator units). */
function ladderPoints(location, rotation, extentZ) {
  const yaw = rotation[1] * 2 * Math.PI / TURN, fx = Math.cos(yaw), fy = Math.sin(yaw), h = 2 * (extentZ + 1);
  return { top: [location[0] + TOP_REACH * fx, location[1] + TOP_REACH * fy, location[2] + h + END_LIFT],
           foot: [location[0] - FOOT_BACK * fx, location[1] - FOOT_BACK * fy, location[2] + END_LIFT] };
}

export const tileOf = (point, origin, size = [96, 96, 64]) => point.map((v, k) => Math.floor((v - origin[k]) / size[k]));

/** The ends against `floors` (a Set of 'x,y,z' tiles with floor), their tiles counted from `origin`, the corner the
 *  game counts its tiles from (map_grid.js tileCorner): { top, foot, topTile, footTile, linkedTop (or null), footFloor,
 *  climbs, why }. */
export function ladderEnds(location, rotation, extentZ, origin, floors) {
  const { top, foot } = ladderPoints(location, rotation, extentZ);
  const t = tileOf(top, origin), f = tileOf(foot, origin), below = [t[0], t[1], t[2] - 1];
  const has = tile => floors.has(tile.join(','));
  const linkedTop = has(t) ? t : has(below) ? below : null;
  const why = [['foot', has(f)], ['top', Boolean(linkedTop)]].filter(([, ok]) => !ok).map(([w]) => w);
  return { top, foot, topTile: t, footTile: f, linkedTop, footFloor: has(f), climbs: !why.length, why };
}
