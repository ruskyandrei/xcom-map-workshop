// The piece panel's sections of a made piece (refactor stage P7; the custom geometry plan's M1 to M6 and the custom
// geometry editing plan's B3 and B4). Here:
// - the Wall section (wallPanel): the wall's size, look and joins, its openings listed with how each plays (a gap
//   units walk through wants a door: doorBoxes, openingWorldBox, boxesMeet), and its buttons: Add gap
//   (addWallOpening), Flip and Shuffle; Delete with an opening's handle last touched takes that opening out
//   (deleteWallOpening);
// - the Floor section (slabPanel): a slab's size and look, its holes, Add hole and Shuffle;
// - the Ground section (groundPanel): a ground shape's size, slope and look, Turn, Another rock and Reset points;
// - the Room section: a drawn room picked whole (roomOfSelection, roomPanel), its walls' and roof's looks, and its
//   walls a storey lower or taller (storeyButtons, roomStoreys).
//
// createMadePanel takes what it needs of app.js as one argument object, when app.js makes it: the made pieces' state,
// changes and handles, their looks and Break row, the groups and the selection's group, and the hints. Its own state
// is the room shown; the opening last touched is editor_state.js's (wallFocus, which the handles set too).
import * as THREE from 'three';
import { TILE } from './constants.js';
import { onHub } from './edit_hub.js';
import { data, roots, selected, setWallFocus, volumeRoots, wallFocus } from './editor_state.js';
import { anotherRock, GROUND, groundLookOf, groundWords as groundShapeWords, resetRock, slopeOf, slopeWords, toolGround,
         turnedGround } from './ground.js';
import { catalogued } from './looks.js';
import { flippedWall, holeWords, joinWords, openingPlay, openingWords, playWords, reshuffled, reshuffledSlab, SLAB,
         slabLookOf, slabTiles, slabWords, sortedOpenings, steppedStoreys, storeysOf, storeyWords, toolSlab, toolWall,
         WALL, wallSpec, wallTop, wallWords, withHole, withOpening, withoutHole, withoutOpening,
         withStoreys } from './walls.js';
import { plural, short } from './dom_words.js';

export function createMadePanel({ $, boxOf, breakRow, changeWall, flashHint, gizmo, handleWall, isMadeGround,
                                  isMadeSlab, isMadeWall, isPlain, liveKeys, liveMembers, lookRow, madeRoot,
                                  madeWallRoot, openLookPicker, originalOf, plainLook, selectionGroup, setMadeLook,
                                  setWall, wallLookOf, wallPiecesWords, wallState }) {
  // ---- the piece panel's Wall section
  function wallPanel(root) {
    const o = root.userData.source, g = o.added.generated, w = g.wall, look = wallLookOf(o), tool = toolWall(w);
    const lookName = look?.name ?? catalogued('wall', w?.look)?.name ?? short(data.meshes[originalOf(o)?.mesh]?.name ?? 'made from numbers');
    $('wallHead').textContent = `Wall · ${isPlain(g) ? 'plain' : lookName}`;
    lookRow('wall', g, lookName, tool);
    $('wallState').textContent = tool ? wallWords(w) : `${Math.round(w.x1 - w.x0)} long, made elsewhere: no handles here`;
    $('wallSize').textContent = tool ? `${wallWords(w)}. Its white handles lengthen or shorten it by whole tiles; the one on top adds or takes storeys.${wallPiecesWords(w)}`
      : `${Math.round(w.x1 - w.x0)} long: numbers this tool doesn't draw (made elsewhere), so it has no handles here; the Build makes it as it is.`;
    root.userData.joinsShown = root.userData.joins?.joins ?? [];
    const joined = joinWords(root.userData.joinsShown);
    if (joined) $('wallSize').textContent += ` ${joined}`;
    const list = $('wallOpenings'), openings = sortedOpenings(w.openings ?? []);
    const doors = doorBoxes(root);
    list.replaceChildren(...openings.map((p, index) => {
      const row = document.createElement('div');
      row.className = 'wallopening';
      row.classList.toggle('on', wallFocus?.id === o.id && wallFocus.index === index);
      // (a gap units walk through, with no wall under it to give cover, is a doorway: it wants a door; one they walk
      // through over a wall that gives cover, or one they neither walk through nor see through, plays oddly)
      const play = openingPlay(w, p), door = play.walk && doors.some(b => boxesMeet(openingWorldBox(root, p), b, 8));
      const words = playWords(w, p, { door });
      const warn = !play.tiles || (play.walk ? play.cover !== 'none' || !door : play.cover === 'none' || !play.sight);
      row.append(Object.assign(document.createElement('strong'), { textContent: openingWords(p, w) }),
                 Object.assign(document.createElement('small'), { textContent: words, className: warn ? 'warn' : '' }));
      row.title = words;
      if (warn) row.insertAdjacentHTML('beforeend', '<svg class="i warnmark" role="img" aria-label="Plays oddly"><use href="#i-warn"/></svg>');
      const remove = Object.assign(document.createElement('button'), { type: 'button', textContent: '\u00d7', title: 'Remove: take this gap out of the wall' });
      remove.setAttribute('aria-label', 'Remove this gap');
      remove.disabled = !tool;
      remove.onclick = () => { setWallFocus(null); changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } })); };
      row.append(remove);
      row.onmouseenter = () => { setWallFocus({ id: o.id, index }); };
      return row;
    }));
    $('wallGap').disabled = !(tool && withOpening(w, 'doorway'));
    $('wallFlip').disabled = $('wallShuffle').disabled = !tool;
    breakRow('wall', g, o.keepsPieces);
    $('wallNote').textContent = `Made from numbers on ${look ? `${look.package}'s` : 'its donor\'s'} materials: it breaks as the game's walls do, `
      + 'a fragment at a time. Doorways, windows and holes are walked, seen and shot through by the lines between tiles\' centres. '
      + 'A break passes to the walls, floors and other fracturing pieces it touches, and from them to it, as between the game\'s.';
  }
  // The Lower and Taller buttons of the room panel (`kind` 'room': a picked wall's own top handle does it) for the wall
  // `w` (null: neither).
  function storeyButtons(kind, w) {
    const down = w && steppedStoreys(w, -1), up = w && steppedStoreys(w, 1), spec = w ? wallSpec(w) : null;
    const tall = x => `${storeyWords(storeysOf(x.wall))} (${Math.round(wallTop(x.wall) - spec.bottom)} tall)`;
    $(`${kind}Shorter`).disabled = !down;
    $(`${kind}Storeys`).disabled = !up;
    $(`${kind}Shorter`).title = down ? `Lower: ${tall(down)}${down.removed ? '; openings over its top go' : ''}`
      : w ? 'As low as its look is made' : '';
    $(`${kind}Storeys`).title = up ? `Taller: ${tall(up)}${storeysOf(up.wall) > spec.storeys ? `; the Build stacks walls of its look's ${storeyWords(spec.storeys)}` : ''}`
      : w ? `As tall as a wall is drawn here (${storeyWords(WALL.maxStoreys)})` : '';
  }
  // ---- the piece panel's Floor section (made slabs)
  function slabPanel(root) {
    const o = root.userData.source, s = o.added.generated.slab, look = slabLookOf(s), tool = toolSlab(s);
    $('slabHead').textContent = `${look?.role === 'roof' ? 'Roof' : 'Floor'} · ${isPlain(o.added.generated) ? 'plain' : look?.name ?? 'made from numbers'}`;
    lookRow('slab', o.added.generated, look?.name ?? 'made from numbers', tool);
    const cut = slabTiles(s).some(n => n > SLAB.pieceTiles)
      ? ` The Build makes it as slabs of at most ${SLAB.pieceTiles} by ${SLAB.pieceTiles} tiles side by side: they break as one.` : '';
    breakRow('slab', o.added.generated, o.keepsPieces);
    $('slabState').textContent = tool ? slabWords(s) : 'Made elsewhere: no handles here';
    $('slabSize').textContent = tool ? `${slabWords(s)}. Its white handles grow or shrink it by whole tiles.${cut}`
      : 'Numbers this tool doesn\'t draw (made elsewhere), so it has no handles here; the Build makes it as it is.';
    const holes = s.holes ?? [];
    $('slabHoles').replaceChildren(...holes.map((h, index) => {
      const row = document.createElement('div');
      row.className = 'wallopening';
      row.classList.toggle('on', wallFocus?.id === o.id && wallFocus.index === index);
      row.append(Object.assign(document.createElement('strong'), { textContent: holeWords(h) }),
                 Object.assign(document.createElement('small'), { textContent: 'Open: units fall through it only as the game lets them (they don\'t); a ladder or stairs of the game\'s go in it' }));
      row.title = row.querySelector('small').textContent;
      const remove = Object.assign(document.createElement('button'), { type: 'button', textContent: '\u00d7', title: 'Remove: fill this hole' });
      remove.setAttribute('aria-label', 'Remove this hole');
      remove.disabled = !tool;
      remove.onclick = () => { setWallFocus(null); changeWall(st => ({ ...st, generated: { ...st.generated, slab: withoutHole(st.generated.slab, index) } })); };
      row.append(remove);
      row.onmouseenter = () => { setWallFocus({ id: o.id, index }); };
      return row;
    }));
    $('slabHole').disabled = !tool || !withHole(s);
    $('slabShuffle').disabled = !tool;
    $('slabNote').textContent = `Made from numbers on ${look ? `${look.package}'s` : 'its donor\'s'} materials: it breaks as the game's `
      + `${look?.role === 'roof' ? 'roofs do' : 'floors do'}, a piece at a time, and a break passes to the walls and pieces it touches. `
      + (look?.role === 'roof' ? 'It is cut away with its building\'s top floor when the cursor is inside, and takes no clicks.'
        : 'Units walk on it where there is standing room over it; a hole in it is no floor.');
  }
  $('slabHole').onclick = () => {
    const root = madeRoot(selected);
    if (!root || !isMadeSlab(root.userData.source)) return;
    const r = withHole(root.userData.source.added.generated.slab);
    if (!r) { flashHint('Every tile of it is a hole'); return; }
    setWallFocus({ id: root.userData.source.id, index: r.index });
    changeWall(st => ({ ...st, generated: { ...st.generated, slab: r.slab } }));
    flashHint('Added a hole, one tile · its blue handles move and size it');
  };
  $('slabShuffle').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, slab: reshuffledSlab(st.generated.slab) } }));
  // ---- the piece panel's Ground section (M6)
  function groundPanel(root) {
    const o = root.userData.source, g = o.added.generated.ground, look = groundLookOf(g), tool = toolGround(g);
    const plain = isPlain(o.added.generated);
    $('groundHead').textContent = `Ground · ${plain ? 'plain' : look?.name ?? 'made from numbers'}`;
    lookRow('ground', o.added.generated, look?.name ?? 'made from numbers', tool);
    $('groundState').textContent = tool ? groundShapeWords(g) : 'Made elsewhere: no handles here';
    $('groundSize').textContent = tool ? `${groundShapeWords(g)}. Its white handles size it by whole tiles${g.shape === 'patch' ? '' : '; the one on top raises or lowers it'}.`
      : 'Numbers this tool doesn\'t draw (made elsewhere), so it has no handles here; the Build makes it as it is.';
    const words = slopeWords(g);
    $('groundSlope').hidden = !words;
    $('groundSlope').textContent = words ? words[0].toUpperCase() + words.slice(1) + '.' : '';
    $('groundSlope').classList.toggle('warn', slopeOf(g) > GROUND.sloped);
    $('groundTurn').hidden = g.shape !== 'ramp';
    $('groundTurn').disabled = !tool;
    $('groundAnother').hidden = $('groundResetPoints').hidden = g.shape !== 'rock';
    $('groundAnother').disabled = !tool;
    $('groundResetPoints').disabled = !tool || !g.points;
    if (g.shape === 'rock' && tool)
      $('groundSize').textContent += g.points ? ' Its corners have been moved: its blue points move them again (click one, then drag its arrows).'
        : ' Its blue points are its corners: click one, then drag its arrows to move it.';
    $('groundNote').textContent = `Made from numbers on ${look ? `${look.package}'s ${look.name.toLowerCase()}` : 'its donor\'s material'}: `
      + (g.shape === 'rock' ? 'it stands in the way and gives cover by its height, as the game\'s rocks do, and it doesn\'t break.'
        : 'units walk on it and it doesn\'t break.')
      + (g.shape === 'patch' ? ' Its top lies level with the ground it covers, its plate under it.' : '');
  }
  $('groundAnother').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, ground: anotherRock(st.generated.ground) } }));
  $('groundResetPoints').onclick = () => changeWall(st => ({ ...st, generated: { ...st.generated, ground: resetRock(st.generated.ground) } }));
  $('groundTurn').onclick = () => changeWall(st => {
    const t = turnedGround(st.generated.ground, st.location, st.rotation);
    return { generated: { ...st.generated, ground: t.ground }, location: t.location, rotation: t.rotation };
  });
  // ---- a room (custom geometry editing plan, B3): a drawn room is one locked group; picked whole, the panel is the
  // room's, its walls' and roof's own sections hidden (Ungroup edits them one by one)
  function madeLookName(root) {
    const o = root.userData.source, g = o.added.generated;
    if (isPlain(g)) return null;
    if (g.kind === 'fracWall') return wallLookOf(o)?.name ?? catalogued('wall', g.wall?.look)?.name ?? 'made from numbers';
    if (g.kind === 'fracSlab') return slabLookOf(g.slab)?.name ?? 'made from numbers';
    return groundLookOf(g.ground)?.name ?? 'made from numbers';
  }
  // The picked group as a room: its made walls (three or more, each joined at both ends to another of them) and the
  // made slab on them (its roof), with nothing else but its building; or null.
  function roomOfSelection() {
    const { kind, group: g } = selectionGroup();
    if (kind !== 'whole' || !g) return null;
    const keys = liveKeys(g), rs = keys.filter(k => !k.startsWith('building|')).map(k => liveMembers().get(k)?.[0]).filter(Boolean);
    const walls = rs.filter(r => isMadeWall(r.userData.source)), slabs = rs.filter(r => isMadeSlab(r.userData.source));
    if (walls.length < 3 || slabs.length > 1 || walls.length + slabs.length !== rs.length) return null;
    const ids = new Set(walls.map(r => r.userData.source.id));
    if (!walls.every(r => new Set((r.userData.joins?.joins ?? []).filter(j => ids.has(j.other)).map(j => j.end)).size === 2)) return null;
    return { group: g, walls, roof: slabs[0] ?? null };
  }
  let roomShown = null;
  function roomPanel() {
    const room = roomShown = volumeRoots.has(selected) ? null : roomOfSelection();
    $('roomBox').hidden = !room;
    if (!room) return;
    $('wallBox').hidden = $('slabBox').hidden = true;
    const box = new THREE.Box3();
    for (const r of room.walls) box.expandByObject(r);
    const tiles = [Math.round((box.max.x - box.min.x) / TILE), Math.round((box.max.z - box.min.z) / TILE)];
    const w = room.walls[0].userData.source.added.generated.wall, names = new Set(room.walls.map(madeLookName));
    const tool = room.walls.every(r => toolWall(r.userData.source.added.generated.wall));
    $('roomHead').textContent = `Room · ${tiles[0]} by ${tiles[1]} tiles`;
    $('roomState').textContent = `${plural(room.walls.length, 'wall')}, ${storeyWords(storeysOf(w))}${room.roof ? ', a roof' : ''} · picked as one`;
    $('roomSize').textContent = `${plural(room.walls.length, 'wall')}, ${storeyWords(storeysOf(w))}${room.roof ? ', a roof' : ''}. Picked as one: it moves, turns and copies whole. Ungroup it to edit its walls one by one: their gaps, doors and own looks.`;
    const wallWord = names.size > 1 ? 'Walls: mixed looks' : names.has(null) ? 'Walls: no look chosen' : `Walls: ${[...names][0]}`;
    $('roomWallsLook').textContent = wallWord;
    $('roomWallsLook').classList.toggle('warn', names.has(null));
    $('roomWallsChoose').disabled = !tool;
    $('roomWallsPlain').disabled = !tool || (names.size === 1 && names.has(null));
    $('roomRoofRow').hidden = !room.roof;
    if (room.roof) {
      const name = madeLookName(room.roof);
      $('roomRoofLook').textContent = name ? `Roof: ${name}` : 'Roof: no look chosen';
      $('roomRoofLook').classList.toggle('warn', !name);
      $('roomRoofPlain').disabled = !name;
    }
    // (a room with a roof keeps its height: its roof and building stand on its walls' tops)
    $('roomStoreysRow').hidden = Boolean(room.roof);
    storeyButtons('room', tool && !room.roof ? w : null);
  }
  $('roomWallsChoose').onclick = () => { const r = roomShown; if (r) openLookPicker('wall', { onChoose: look => setMadeLook(r.walls[0], 'wall', look) }); };
  $('roomWallsPlain').onclick = () => { const r = roomShown; if (r) setMadeLook(r.walls[0], 'wall', plainLook('wall')); };
  $('roomRoofChoose').onclick = () => { const r = roomShown; if (r?.roof) openLookPicker('slab', { onChoose: look => setMadeLook(r.roof, 'slab', look) }); };
  $('roomRoofPlain').onclick = () => { const r = roomShown; if (r?.roof) setMadeLook(r.roof, 'slab', plainLook('slab', r.roof.userData.source.added.generated.slab)); };
  // (a room with no roof: its walls a storey lower or taller, in one undo step)
  function roomStoreys(step) {
    const r = roomShown;
    if (!r) return;
    const stepped = steppedStoreys(r.walls[0].userData.source.added.generated.wall, step);
    if (!stepped) return;
    const next = storeysOf(stepped.wall), before = r.walls.map(wallState);
    r.walls.forEach((root, k) => setWall(root, { ...before[k], generated: { ...before[k].generated, wall: withStoreys(before[k].generated.wall, next).wall } }, before[k]));
    gizmo.joinLast(r.walls.length);
    flashHint(`Its walls now ${storeyWords(next)} · Ctrl+Z puts them back`);
  }
  $('roomStoreys').onclick = () => roomStoreys(1);
  $('roomShorter').onclick = () => roomStoreys(-1);
  // The boxes of the doors drawn now (copies, and the map's own where they stand), game units [x0, x1, y0, y1, z0, z1].
  function doorBoxes(except) {
    const out = [];
    for (const r of roots.values()) {
      if (r === except || r.userData.deleted || !r.visible || r.userData.source.actorClass !== 'XComInteractiveLevelActor') continue;
      const b = boxOf(r);
      if (b) out.push(b);
    }
    return out;
  }
  function openingWorldBox(root, p) {
    root.updateMatrixWorld(true);
    const pts = [], half = wallSpec(root.userData.source.added?.generated?.wall).half;
    for (const x of [p.x0, p.x1]) for (const y of [-half, half]) for (const z of [p.z0, p.z1]) {
      const v = new THREE.Vector3(x, z, y).applyMatrix4(root.matrixWorld);
      pts.push([v.x, v.z, v.y]);
    }
    return [0, 1, 2].flatMap(k => [Math.min(...pts.map(q => q[k])), Math.max(...pts.map(q => q[k]))]);
  }
  // (as the compiler's overlaps_by: across at all, along and up by more than `least`)
  function boxesMeet(a, b, least) {
    const along = a[1] - a[0] >= a[3] - a[2] ? 0 : 1, over = [0, 1, 2].map(k => Math.min(a[2 * k + 1], b[2 * k + 1]) - Math.max(a[2 * k], b[2 * k]));
    return over[along] > least && over[2] > least && over[1 - along] > 0;
  }
  // Add gap (the user, 19 November 2026: one button for the doorway's and the window's, as gaps are one kind): a gap
  // shaped as the game's doorways, which its middle handle takes up to make a window. (`kind` 'window': the tests'.)
  $('wallGap').onclick = () => addWallOpening('doorway');
  function addWallOpening(kind = 'doorway') {
    const root = madeWallRoot(selected);
    if (!root) return;
    const r = withOpening(root.userData.source.added.generated.wall, kind);
    if (!r) { flashHint('Every tile of the wall has an opening'); return; }
    setWallFocus({ id: root.userData.source.id, index: r.index });
    changeWall(s => ({ ...s, generated: { ...s.generated, wall: r.wall } }));
    flashHint('Added a gap · its blue handles move and size it, and cut the wall to its edges; drag its middle up to make a window');
  }
  $('wallFlip').onclick = () => changeWall(s => {
    const f = flippedWall(s.generated.wall, s.location, s.rotation);
    return { generated: { ...s.generated, wall: f.wall }, location: f.location, rotation: f.rotation };
  });
  $('wallShuffle').onclick = () => changeWall(s => ({ ...s, generated: { ...s.generated, wall: reshuffled(s.generated.wall) } }));
  // Delete with an opening's handle last touched takes that opening out (the wall stays): true when it did.
  function deleteWallOpening() {
    const slabRoot = madeRoot(selected);
    if (slabRoot && isMadeSlab(slabRoot.userData.source) && wallFocus?.id === slabRoot.userData.source.id && handleWall()) {
      const index = wallFocus.index;
      if (index >= (slabRoot.userData.source.added.generated.slab.holes ?? []).length) return false;
      setWallFocus(null);
      changeWall(st => ({ ...st, generated: { ...st.generated, slab: withoutHole(st.generated.slab, index) } }));
      flashHint('Filled the hole · Ctrl+Z opens it again');
      return true;
    }
    const root = madeWallRoot(selected);
    if (!root || wallFocus?.id !== root.userData.source.id || !handleWall()) return false;
    const index = wallFocus.index;
    if (index >= (root.userData.source.added.generated.wall.openings ?? []).length) return false;
    setWallFocus(null);
    changeWall(s => ({ ...s, generated: { ...s.generated, wall: withoutOpening(s.generated.wall, index) } }));
    flashHint('Removed the opening · Ctrl+Z puts it back');
    return true;
  }

  // After an edit (the edit hub, edit_hub.js).
  onHub('edit', 'room', () => { roomPanel(); });
  // As something is picked (the edit hub's select runs): a made piece's sections shown for it, and filled.
  onHub('select-sections', 'made', root => {
    $('wallBox').hidden = !isMadeWall(root?.userData.source);
    $('slabBox').hidden = !isMadeSlab(root?.userData.source);
    $('groundBox').hidden = !isMadeGround(root?.userData.source);
  });
  onHub('select-piece', 'made', (root, obj) => {
    if (isMadeWall(obj)) wallPanel(root);
    if (isMadeSlab(obj)) slabPanel(root);
    if (isMadeGround(obj)) groundPanel(root);
  });

  return { addWallOpening, deleteWallOpening, groundPanel, roomOfSelection, slabPanel, wallPanel };
}
