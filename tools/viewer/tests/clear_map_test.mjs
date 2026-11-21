// Clear map, the ground grid and landing zones (private/plans/done/clear-map-plan.md): the project records
// (project.js) and the page's plain functions. Run: node tools/viewer/tests/clear_map_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validLandingZone, tidyLandingZone, sortState, stateKey, validStage, stageMax } from '../web/project.js';

// ---- C1: the records
const zone = { id: 'z1', location: [719, -1681, 64], direction: 'north', kind: 'normal' };
assert.ok(validLandingZone(zone));
assert.ok(validLandingZone({ ...zone, other: 'Spare=(A=1,B="x,y")' }));
for (const other of ['X=1)\r\n[Evil]\r\nfoo=(Y=2', 'a\nb', 'a\u2028b', 'a\x00b', 'x'.repeat(4001)]) assert.ok(!validLandingZone({ ...zone, other }), JSON.stringify(other));
assert.ok(validLandingZone({ id: 'z2', location: [1, 2, 3], direction: 'west' }));             // kind defaults to normal
assert.ok(validLandingZone({ ...zone, kind: 'inside', missionType: 'eMission_Abduction', councilType: 'eFCMType_Extraction',
                             alternate: { location: [0, 0, 64], direction: 'east' }, lwr: false, other: 'Foo=1' }));
for (const bad of [null, [], { ...zone, id: '' }, { ...zone, location: [1, 2] }, { ...zone, location: [1, 2, NaN] },
                   { ...zone, direction: 'up' }, { ...zone, kind: 'outside' }, { ...zone, alternate: { location: [0, 0, 0] } }, { ...zone, lwr: true }, { ...zone, missionType: 'a b' },
                   { ...zone, alternate: [1] }, { ...zone, other: 3 }, { ...zone, extra: 1 }, { ...zone, ew: 1 }])
  assert.ok(!validLandingZone(bad), JSON.stringify(bad));
// the cases spawns.py valid_zone passes too (zone_cases.json, test_spawns.py; review finding 27)
{
  const { cases } = JSON.parse(readFileSync(new URL('./zone_cases.json', import.meta.url), 'utf8'));
  assert.ok(cases.length > 30);
  for (const c of cases) assert.equal(validLandingZone(c.zone), c.valid, c.why);
}
assert.deepEqual(tidyLandingZone({ id: 'z2', location: [1.000001, 2, 3], direction: 'west' }),
                 { id: 'z2', location: [1, 2, 3], direction: 'west', kind: 'normal' });
assert.deepEqual(tidyLandingZone({ ...zone, lwr: false, missionType: '' }), { ...zone, lwr: false });
// sortState: the zones keep their order; a malformed one is carried in place; absent is null, an empty list is no zone
const odd = { id: 'odd', location: 'here' };
const sorted = sortState({ overrides: [], added: [], landingZones: [{ ...zone, id: 'b' }, odd, { ...zone, id: 'a' }] });
assert.deepEqual(sorted.landingZones.map(z => z.id), ['b', 'odd', 'a']);
assert.equal(sortState({ overrides: [], added: [] }).landingZones, null);
assert.deepEqual(sortState({ overrides: [], added: [], landingZones: [] }).landingZones, []);
// cleared is part of the state's key, and so are the zones
const plain = sortState({ overrides: [], added: [] });
assert.equal(plain.cleared, false);
assert.notEqual(stateKey(plain), stateKey(sortState({ overrides: [], added: [], cleared: true })));
assert.notEqual(stateKey(plain), stateKey(sortState({ overrides: [], added: [], landingZones: [] })));
assert.equal(stateKey(plain), stateKey(sortState({ overrides: [], added: [], cleared: false, landingZones: null })));
// a smaller grid and three numbers are valid stages (the compiler says where they may be used)
assert.ok(validStage({ grid: [20, 30, 4] }));
assert.ok(!validStage({ grid: [0, 30, 4] }));
assert.ok(validStage({ grid: [20, 30, 30] }));
assert.ok(!validStage({ grid: [20, 30, 31] }));
// up to 256 tiles a side (the user, 16 November 2026; 128 before)
assert.deepEqual(stageMax(), [256, 256, 30]);
assert.ok(validStage({ grid: [256, 256] }) && !validStage({ grid: [257, 39] }));
assert.ok(validStage({ grid: [45, 256] }, [45, 203, 15]) && !validStage({ grid: [45, 257] }, [45, 203, 15]));   // TempleShip
// a map past the limits at its own size keeps its own as its limit on that axis (stageMax, mission_edits.py stage_max's
// twin; T-41: TempleShip, 45 by 203 by 15, snapped back while the limit was 128), and the project keeps it. A
// stand-in map 45 by 300 by 15 keeps the case.
const past = [45, 300, 15];
assert.deepEqual(stageMax(past), [256, 300, 30]);
assert.ok(!validStage({ grid: [46, 300] }));
for (const grid of [[46, 300], [256, 300], [45, 300, 30], [40, 150, 8]]) assert.ok(validStage({ grid }, past), JSON.stringify(grid));
for (const grid of [[257, 300], [45, 301], [45, 300, 31]]) assert.ok(!validStage({ grid }, past), JSON.stringify(grid));
assert.deepEqual(sortState({ overrides: [], added: [], stage: { grid: [46, 300], ground: false } }).stage, { grid: [46, 300], ground: false });
assert.equal(sortState({ overrides: [], added: [], stage: { grid: [46, 300.5] } }).stage, null);

// ---- C4: spawns.js, the twin of spawns.py
import { place, evacBox, zoneOfFrame, ownSlots, samePlace, startingZones, ownLandings } from '../web/spawns.js';
const bar1 = { location: [719, -1681, 64], direction: 'north', kind: 'normal' };
assert.deepEqual(place(bar1).frame, { location: [719, -1681, 0], yaw: 0 });
assert.deepEqual(place({ location: [0, 0, 64], direction: 'east' }).soldiers[3], { location: [-288, 0, 48], yaw: 32768 });
assert.deepEqual(place({ location: [0, 0, 64], direction: 'north', kind: 'inside' }).soldiers[3].location, [0, 0, 48]);
assert.deepEqual(evacBox({ location: [0, 0, 64], direction: 'north' }), [-240, -191, 0, 240, 97, 192]);
assert.equal(zoneOfFrame([5, 6, 10], 16380).direction, 'east');
assert.ok(samePlace(zoneOfFrame([720, -1680, 0], 0), bar1));
assert.ok(!samePlace(zoneOfFrame([720, -1680, 0], 16384), bar1));
assert.deepEqual(ownSlots([{ missionType: 'eMission_Abduction' }, {}, {}], 1), [1]);
// the starting list: the own landing joined with its line first, then the other lines; an own landing no line
// matches gets lwr: false
let n = 0;
const id = () => `z${++n}`;
const lines = [{ ...bar1, location: [-1297, -1681, 80] }, bar1];
const own = ownLandings({ objects: [{ layer: 'base', actor: 'X_6', archetype: 'A.B.SoldierSpawns_DrpshipVol_12Arc0', location: [720, -1680, 0], rotation: [0, 0, 0] }] });
assert.deepEqual(startingZones(own, lines, id), [{ id: 'z1', ...bar1, ew: true }, { id: 'z2', ...lines[0] }]);
const far = ownLandings({ landings: [{ group: 'Group0', actors: [{ role: 'frame', path: 'F', location: [0, 0, 0], rotation: [0, 16384, 0] }] }] });
assert.deepEqual(startingZones(far, lines, id).map(z => [z.lwr, z.direction, z.ew]), [[false, 'east', true], [undefined, 'north', undefined], [undefined, 'north', undefined]]);
// Plain EW marked on zones (the panel's Plain EW): the marked zones, in order, up to the map's count; with none
// marked anywhere, the old rule by order
assert.deepEqual(ownSlots([{}, { ew: true }, {}, { ew: true }], 1), [1]);
assert.deepEqual(ownSlots([{}, { ew: true }, {}, { ew: true }], 3), [1, 3]);
assert.deepEqual(ownSlots([{}, {}], 1), [0]);
assert.ok(validLandingZone({ ...zone, ew: true }) && !validLandingZone({ ...zone, ew: false }));
assert.deepEqual(tidyLandingZone({ ...zone, ew: true }), { ...zone, ew: true });

// The cursor's floors on a grown grid (floors.js cursorStoreys, floor_edits.py cursor_storeys' twin; shell.py
// grow_cursors)
const { cursorStoreys } = await import('../web/floors.js');
const map = { exporterVersion: 22, tileGrid: { origin: [0, 0, 0], dimensions: [60, 45, 18], size: [96, 96, 64] },
              cursorVolumes: [{ floor: 1, box: { min: [-10, -10, 0], max: [52 * 96 + 5, 39 * 96, 192] } },
                              { floor: 2, box: { min: [100, 100, 192], max: [900, 39 * 96 - 0.5, 400] } },
                              { floor: 4, stair: true, box: { min: [0, 0, 0], max: [52 * 96, 39 * 96, 900] } }] };
const grown = cursorStoreys(map, { own: [52, 39, 12] });
assert.deepEqual(grown.slice(0, 2).map(s => s.box), [[-10, -10, 0, 60 * 96, 45 * 96, 192], [100, 100, 192, 900, 45 * 96, 400]]);
assert.deepEqual(grown.slice(2).map(s => [s.floor, s.box[2], s.box[5]]), [[3, 400, 592], [4, 592, 784], [5, 784, 976], [6, 976, 1152]]);
assert.deepEqual(cursorStoreys({ ...map, tileGrid: { ...map.tileGrid, dimensions: [52, 39, 12] } }, { own: [52, 39, 12] }).map(s => s.floor), [1, 2]);
// cleared: even storeys from the bottom, one more for each 192 of a taller grid, the map's own left out
assert.deepEqual(cursorStoreys(map, { cleared: true, own: [52, 39, 12] }).map(s => [s.floor, s.box[2], s.box[5]]),
                 [[1, 0, 192], [2, 192, 384], [3, 384, 576], [4, 576, 768], [5, 768, 960], [6, 960, 1152]]);

// A landing with no drop zone frame (spawns.js fitZone, soldierSpots; spawns.py's twins and their tests' numbers)
const { fitZone, soldierSpots, ownLandings: own2, place: place2 } = await import('../web/spawns.js');
const introPoints = [[-625.1, -48.1, 112], [-721.1, -144.0, 112], [-721.1, -336.0, 112], [-625.1, -432.0, 112], [-816.0, -336.0, 96], [-528.0, -144.0, 112]];
const introActors = [...introPoints.map((p, k) => ({ role: `soldier${k + 1}`, location: p, rotation: [0, 32000, 0] })),
                     { role: 'point', location: [-864, -384, 48], rotation: [0, 16384, 0] }];
assert.deepEqual(fitZone(introActors), { location: [-353, -240, 112], direction: 'east', kind: 'normal' });
assert.deepEqual(fitZone(introActors, -3.05e-5).location, [-353, -240, 64]);
assert.deepEqual(fitZone(introActors, -48).location, [-353, -240, 80]);
assert.deepEqual(own2({ tileGrid: { origin: [0, 0, -3.05e-5] }, landings: [{ group: 'g', actors: introActors }] })[0].zone.location, [-353, -240, 64]);
for (const direction of ['north', 'east', 'south', 'west']) {
  const z = { location: [-1680, -336, -320], direction, kind: 'normal' }, at = place2(z);
  const actors = [...at.soldiers.map((s, k) => ({ role: `soldier${k + 1}`, location: s.location, rotation: [0, s.yaw, 0] })), { role: 'point', location: at.point.location, rotation: [0, 0, 0] }];
  assert.deepEqual(fitZone(actors), z, direction);
}
const [intro] = own2({ landings: [{ group: 'XComSpawnPoint', actors: introActors }] });
assert.ok(intro.fitted && intro.frame === null);
assert.deepEqual(soldierSpots(intro.zone, intro).map(s => s.location), introPoints);

// Whether a zone leaves the map's own landing in place, as the Build reckons it (spawns.js landingUnmoved,
// native_spawns.unmoved): the Bar's line, a unit off its frame, keeps it (the view hid a cleared Bar's Skyranger at
// half a unit, while its lights stayed drawn); a tile off, or turned, moves it; a frameless landing by its fitted zone
const { landingUnmoved } = await import('../web/spawns.js');
const barFrame = { role: 'frame', path: 'F', location: [719.9998779296875, -1679.9998779296875, 0], rotation: [0, 0, 0] };
const barOwn = own2({ landings: [{ group: 'XComSpawnPoint', actors: [barFrame, ...place(bar1).soldiers.map((s, k) => ({ role: `soldier${k + 1}`, location: s.location.map(v => v + 0.4), rotation: [0, s.yaw, 0] }))] }] })[0];
assert.ok(landingUnmoved(bar1, barOwn));
assert.ok(!landingUnmoved({ ...bar1, location: [815, -1681, 64] }, barOwn));
assert.ok(!landingUnmoved({ ...bar1, direction: 'east' }, barOwn));
assert.ok(!landingUnmoved(bar1, null));
assert.ok(landingUnmoved(intro.zone, intro) && !landingUnmoved({ ...intro.zone, location: [-352, -240, 64] }, intro));
// A landing whose soldier points stand off the mutator's layout for its frame is unmoved by its own zone (KB-13,
// T-51): the police station's stand on raised ground, 3 to 5 units across and 38 to 70 higher, and many maps' a third
// of a tile off. Only the zone's layout is compared with the own zone's; a zone moved, turned or of another kind at
// the same place still moves it.
for (const off of [[3, -5, 38], [-4, 5, 70], [32, 0, 0], [0, -384, 16]]) {
  const ownZone = zoneOfFrame(barFrame.location, 0);
  const actors = [barFrame, ...place(ownZone).soldiers.map((s, k) => ({ role: `soldier${k + 1}`, rotation: [0, s.yaw, 0],
    location: s.location.map((v, j) => v + (k % 2 ? off[j] : 0)) }))];
  const [own] = own2({ landings: [{ group: 'XComSpawnPoint', actors }] });
  assert.ok(landingUnmoved(own.zone, own), JSON.stringify(off));
  assert.ok(landingUnmoved(bar1, own), JSON.stringify(off));
  assert.ok(!landingUnmoved({ ...own.zone, location: [own.zone.location[0] + 96, own.zone.location[1], 64] }, own));
  assert.ok(!landingUnmoved({ ...own.zone, direction: 'east' }, own));
  assert.ok(!landingUnmoved({ ...own.zone, kind: 'inside' }, own));
}
// A zone dragged keeps its own height, moved by the drag (the police station's lines and own landing stand at 64,
// their ground 48 over the grid's first level, -48): only a zone saved under the grid comes onto its nearest level
const { draggedHeight, snapZoneMove, placedZone } = await import('../web/spawns.js');
assert.equal(draggedHeight(63.99999141531498, 0, -48), 63.99999141531498);
assert.equal(draggedHeight(64, 64, -48), 128);
assert.equal(draggedHeight(64, 10.5, -48), 74.5);
assert.equal(draggedHeight(64, -64, -48), 0);       // (moved under the grid it stays: the compiler warns)
assert.equal(draggedHeight(79, 0, -48), 79);
assert.equal(draggedHeight(64, 0, null), 64);
assert.equal(draggedHeight(48, 0, 0), 64);          // the tutorial's old zone, 16 under the grid
assert.equal(draggedHeight(48, 64, 0), 128);        // (its first move puts it on a level)
assert.equal(draggedHeight(63.5, 0, 0), 63.5);      // a unit's slack under the bottom
// The zone gizmo's steps follow the snap setting (the user, 21 November): smooth with snap off, 24 on fine, whole
// tiles across and storeys up on tile
assert.deepEqual(snapZoneMove([37.3, -50.2, 10.7], 'off'), [37.3, -50.2, 10.7]);
assert.deepEqual(snapZoneMove([37.3, -50.2, 10.7], 'fine'), [48, -48, 0]);
assert.deepEqual(snapZoneMove([150, -50.2, 40], 'tile'), [192, -96, 64]);
// a zone placed: a unit off a tile corner under tile snap (as LWR's lines), on 24's under fine, where clicked with
// snap off
assert.deepEqual(placedZone(770.4, -1700.2, [-1728, -2496, -48], 'tile'), [767, -1729]);
assert.deepEqual(placedZone(770.4, -1700.2, [-1728, -2496, -48], 'fine'), [768, -1704]);
assert.deepEqual(placedZone(770.4, -1700.2, [-1728, -2496, -48], 'off'), [770.4, -1700.2]);
const shifted = { ...intro.zone, location: [intro.zone.location[0] + 96, intro.zone.location[1], intro.zone.location[2]] };
assert.deepEqual(soldierSpots(shifted, intro), place2(shifted).soldiers);

console.log('clear map tests passed');
