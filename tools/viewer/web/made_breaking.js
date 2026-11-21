// Break and Repair (refactor stage P7; the custom geometry editing plan's B5 and E6): blasts set off on a made wall,
// floor or roof, or on one of the map's own fracturing pieces or a copy of one, each knocking out the fragments within
// its reach as the Build does (tools/bake/made_blasts.py), saved on the piece. Here:
// - the Break rows of the wall, floor and piece panels (breakRow) and their controls: Break, the blast's size, Repair
//   and Breaks further in battle;
// - the Break tool: the next click on the picked piece sets off a blast there (startBreak, stopBreak, blastAt,
//   breakAt), its marker following the pointer;
// - the map's own fracturing pieces broken (mapBreakable, changeBlasts, setBroken) and drawn without the fragments
//   their blasts knock out (drawBroken, knockedOut, middlesOf, fragmentSpans, sectionParts).
//
// createMadeBreaking takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the
// renderer and the scene, the picking, the made pieces' changes, the other tools it stops, the selection and the
// hints. Its own state is inside it (the blast's size, its marker, the fragments' middles by mesh); whether Break is on
// (breaking) is editor_state.js's, since app.js's keys and pointer handlers read it.
import * as THREE from 'three';
import { TILE } from './constants.js';
import { onHub } from './edit_hub.js';
import { breaking, data, roots, selected, setBreaking } from './editor_state.js';
import { cloneBlasts } from './piece_records.js';
import { recall, remember } from './storage.js';

export function createMadeBreaking({ $, changeWall, flashHint, gizmo, isMadeSlab, isMadeWall, madeRoot, pick, plural,
                                     renderer, select, stopLookPick, stopPlacing, stopWallDrawing, world }) {
  // ---- Break and Repair (custom geometry editing plan, B5): blasts set off on a made wall, floor or roof, each knocking
  // out the fragments within its reach as the Build does (tools/bake/made_blasts.py), saved on the piece as blasts (D-4)
  // so they stay where they are when it is made longer, taller or in another look.
  const MAX_BLASTS = 64;
  const BREAK_ROWS = ['wall', 'slab', 'piece'];     // the panels with a Break row: made walls, made slabs, the map's pieces (E6)
  // (breaking, the piece Break is on: editor_state.js)
  let blastTiles = 1;
  blastTiles = Math.min(3, Math.max(1, Math.round(Number(recall('workshop.blastTiles')) || 1)));
  const blastMarker = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0xff7a3d, transparent: true, opacity: 0.25, depthTest: false, depthWrite: false }));
  blastMarker.renderOrder = 9; blastMarker.visible = false; blastMarker.raycast = () => {}; world.add(blastMarker);
  // The Break row of the wall, floor or piece panel (`kind`) for the piece's request `g` (its blasts, breaksFurther):
  // Breaks further in battle shows on a broken piece the game keeps whole (`keeps`: the export's keepsPieces, its
  // donor's for a copy or a made piece), most roofs and floors (F-139).
  function breakRow(kind, g, keeps) {
    const n = g.blasts?.length ?? 0;
    $(`${kind}Break`).classList.toggle('on', Boolean(breaking));
    $(`${kind}BlastSize`).value = String(blastTiles);
    $(`${kind}Repair`).disabled = !n;
    $(`${kind}Broken`).textContent = n ? `Broken by ${plural(n, 'blast')}` : '';
    $(`${kind}FurtherRow`).hidden = !(keeps && n);
    $(`${kind}Further`).checked = Boolean(g.breaksFurther);
  }
  function startBreak() {
    const root = madeRoot(selected) ?? roots.get(selected), o = root?.userData.source;
    if (!root || !(isMadeWall(o) || isMadeSlab(o) || mapBreakable(o))) {
      flashHint('Pick a wall, floor or roof to break it: a made one, or one of the map\'s fracturing pieces'); return;
    }
    stopLookPick(); stopWallDrawing(); stopPlacing();
    setBreaking({ id: o.id });
    gizmo.hold(true);
    renderer.domElement.style.cursor = 'crosshair';
    for (const k of BREAK_ROWS) $(`${k}Break`).classList.add('on');
    flashHint(`Click the ${isMadeSlab(o) ? 'floor' : isMadeWall(o) ? 'wall' : 'piece'} where a blast goes off: it knocks out the fragments within ${plural(blastTiles, 'tile')} · Esc stops`);
  }
  function stopBreak() {
    if (!breaking) return;
    setBreaking(null);
    gizmo.hold(false);
    renderer.domElement.style.cursor = '';
    blastMarker.visible = false;
    for (const k of BREAK_ROWS) $(`${k}Break`).classList.remove('on');
  }
  // Where a blast at the pointer goes off on the piece being broken: { point (the view's), at (its frame's: x, y, z) }.
  function blastAt(x, y) {
    const root = breaking && roots.get(breaking.id), hit = root ? pick(x, y) : null;
    if (!hit || roots.get(hit.object.userData.objectId) !== root) return null;
    // (in its mesh's frame, the made numbers' frame: x along, y across, z up)
    hit.object.updateMatrixWorld();
    const p = hit.object.worldToLocal(hit.point.clone());
    return { point: hit.point, at: [p.x, p.z, p.y].map(v => Math.round(v * 10) / 10) };
  }
  function breakAt(x, y) {
    if (selected !== breaking.id) { stopBreak(); return; }
    const b = blastAt(x, y);
    if (!b) { flashHint('Click on the piece itself · Esc stops'); return; }
    const piece = roots.get(breaking.id);
    if (mapBreakable(piece?.userData.source)) {
      changeBlasts(piece, blasts => {
        if (blasts.length < MAX_BLASTS) return [...blasts, { at: b.at, radius: blastTiles * TILE }];
        flashHint(`It has the most blasts a piece takes (${MAX_BLASTS}): Repair mends it as the map has it`);
        return undefined;
      });
      return;
    }
    changeWall(s => {
      const blasts = s.generated.blasts ?? [];
      if (blasts.length >= MAX_BLASTS) { flashHint(`It has the most blasts a piece takes (${MAX_BLASTS}): Repair mends it whole`); return null; }
      return { ...s, generated: { ...s.generated, blasts: [...blasts, { at: b.at, radius: blastTiles * TILE }] } };
    });
  }
  renderer.domElement.addEventListener('pointermove', e => {
    if (!breaking) return;
    const b = blastAt(e.clientX, e.clientY);
    blastMarker.visible = Boolean(b);
    if (b) { blastMarker.position.copy(world.worldToLocal(b.point.clone())); blastMarker.scale.setScalar(blastTiles * TILE); }
  });
  for (const k of BREAK_ROWS) {
    $(`${k}Break`).onclick = () => (breaking ? stopBreak() : startBreak());
    $(`${k}BlastSize`).onchange = e => {
      blastTiles = Number(e.target.value) || 1;
      remember('workshop.blastTiles', String(blastTiles));
      for (const j of BREAK_ROWS) $(`${j}BlastSize`).value = String(blastTiles);
    };
    if (k === 'piece') {
      $('pieceRepair').onclick = () => { const r = roots.get(selected); if (mapBreakable(r?.userData.source)) changeBlasts(r, () => null); };
      $('pieceFurther').onchange = e => {
        const r = roots.get(selected);
        if (mapBreakable(r?.userData.source) && r.userData.blasts?.length) setBroken(r, { blasts: r.userData.blasts, further: e.target.checked });
      };
      continue;
    }
    $(`${k}Repair`).onclick = () => changeWall(s => {
      if (!s.generated.blasts) return null;
      const { blasts: _, breaksFurther: __, ...generated } = s.generated;
      return { ...s, generated };
    });
    $(`${k}Further`).onchange = e => changeWall(s => {
      if (!s.generated.blasts) return null;
      const { breaksFurther: _, ...generated } = s.generated;
      return { ...s, generated: e.target.checked ? { ...generated, breaksFurther: true } : generated };
    });
  }
  // ---- Break on the map's own fracturing pieces (custom geometry editing plan, E6, decision D-5): the same blasts on
  // any of the map's fracturing pieces or a copy of one, saved on its record (an override's or added copy's `blasts`,
  // in its mesh's frame). The Build paints out the fragments whose middle (that of their vertices' box) a blast
  // reaches, with those the map paints out (tools/bake/made_blasts.py fragment_centres, hidden_at); the page works the
  // middles out the same way from the mesh it draws and draws the piece without those fragments.
  const FRACTURING_CLASSES = new Set(['XComFracLevelActor', 'XComDecoFracLevelActor']);
  function mapBreakable(o) {
    return Boolean(o && !o.cover && !o.added?.generated && FRACTURING_CLASSES.has(o.actorClass)
      && data?.meshes[o.mesh]?.sections?.some(s => s.fragments?.length));
  }
  // A root's parts with the sections they draw: [{ section, part }] (the glb has a primitive for each section with
  // triangles, in order); none when they don't match.
  function sectionParts(root) {
    const parts = root.userData.parts ?? [], sections = (data.meshes[root.userData.source.mesh].sections ?? []).filter(s => s.count);
    return sections.length === parts.length ? sections.map((section, k) => ({ section, part: parts[k] })) : [];
  }
  // Where each fragment's triangles lie in a section's primitive: [start, count] in its indices (null: none drawn), as
  // the export wrote them (its fragments' ranges, packed in order where the map paints fragments out: export.py).
  function fragmentSpans(mesh, section) {
    const mask = mesh.fragmentMask;
    let packed = 0;
    return section.fragments.map(([first, triangles], i) => {
      if (!mask) return triangles ? [first - section.first, 3 * triangles] : null;
      if (!mask[i]) return null;
      const at = packed;
      packed += 3 * triangles;
      return triangles ? [at, 3 * triangles] : null;
    });
  }
  const fragmentMiddles = new Map();     // mesh key -> [[x, y, z] | null]: each fragment's middle in its mesh's frame
  function middlesOf(root) {
    const key = root.userData.source.mesh, mesh = data.meshes[key];
    if (fragmentMiddles.has(key)) return fragmentMiddles.get(key);
    const lo = [], hi = [];
    for (const { section, part } of sectionParts(root)) {
      const g = part.userData.baseGeometry ?? part.geometry, idx = g.index.array, pos = g.attributes.position;
      fragmentSpans(mesh, section).forEach((span, i) => {
        if (!span) return;
        for (let k = span[0]; k < span[0] + span[1]; ++k) {
          const v = idx[k], p = [pos.getX(v), pos.getZ(v), pos.getY(v)];     // (the mesh's frame: z up)
          if (!lo[i]) { lo[i] = [...p]; hi[i] = [...p]; continue; }
          for (let a = 0; a < 3; ++a) { lo[i][a] = Math.min(lo[i][a], p[a]); hi[i][a] = Math.max(hi[i][a], p[a]); }
        }
      });
    }
    const n = Math.max(0, ...(mesh.sections ?? []).map(s => s.fragments?.length ?? 0));
    const out = Array.from({ length: n }, (_, i) => (lo[i] ? lo[i].map((v, a) => (v + hi[i][a]) / 2) : null));
    fragmentMiddles.set(key, out);
    return out;
  }
  // The fragments a root's blasts knock out (made_blasts.hidden_at), in order.
  function knockedOut(root) {
    const blasts = root.userData.blasts ?? [];
    if (!blasts.length) return [];
    return middlesOf(root).flatMap((c, i) => (c && blasts.some(b => Math.hypot(c[0] - b.at[0], c[1] - b.at[1], c[2] - b.at[2]) <= b.radius) ? [i] : []));
  }
  // A root drawn without the fragments its blasts knock out (each part a geometry of its own then, with the mesh's
  // attributes and the kept triangles), or with its mesh's own again. (The old geometry isn't disposed: it shares the
  // mesh's attributes, which other pieces draw.)
  function drawBroken(root) {
    const mesh = data.meshes[root.userData.source.mesh], gone = new Set(knockedOut(root));
    for (const { section, part } of sectionParts(root)) {
      const base = part.userData.baseGeometry ?? part.geometry;
      if (!gone.size) { part.geometry = base; delete part.userData.baseGeometry; continue; }
      part.userData.baseGeometry = base;
      const idx = base.index.array, kept = [];
      fragmentSpans(mesh, section).forEach((span, i) => {
        if (span && !gone.has(i)) for (let k = span[0]; k < span[0] + span[1]; ++k) kept.push(idx[k]);
      });
      const g = new THREE.BufferGeometry();
      for (const [name, attribute] of Object.entries(base.attributes)) g.setAttribute(name, attribute);
      g.setIndex(kept);
      g.boundingBox = base.boundingBox?.clone() ?? null;
      g.boundingSphere = base.boundingSphere?.clone() ?? null;
      part.geometry = g;
    }
  }
  // One of the map's pieces given other blasts (`change` from its blasts to the new ones; null mends it, and takes
  // Breaks further in battle off with them; undefined changes nothing), as one undo step.
  function changeBlasts(root, change) {
    const before = root.userData.blasts ?? null, next = change(before ? cloneBlasts(before) : []);
    if (next === undefined) return;
    const after = next?.length ? next : null;
    if (JSON.stringify(after) === JSON.stringify(before)) return;
    setBroken(root, { blasts: after, further: Boolean(after && root.userData.breaksFurther) });
  }
  // One of the map's pieces broken as `after` says ({ blasts, further: Breaks further in battle }), as one undo step.
  function setBroken(root, after) {
    const before = { blasts: root.userData.blasts ?? null, further: Boolean(root.userData.breaksFurther) };
    const id = root.userData.source.id;
    const set = v => {
      root.userData.blasts = v.blasts ? cloneBlasts(v.blasts) : null; root.userData.breaksFurther = v.further;
      drawBroken(root); select(id, false, true);
    };
    gizmo.record({ redo: () => set(after), undo: () => set(before) });
  }

  // As something is picked (the edit hub's select runs, edit_hub.js): the Break row of one of the map's fracturing
  // pieces, shown for it and filled.
  onHub('select-sections', 'break', root => { $('pieceBreakBox').hidden = !mapBreakable(root?.userData.source); });
  onHub('select-piece', 'break', (root, obj) => {
    if (mapBreakable(obj)) breakRow('piece', { blasts: root.userData.blasts, breaksFurther: root.userData.breaksFurther }, obj.keepsPieces);
  });

  return { breakAt, breakRow, drawBroken, mapBreakable, startBreak, stopBreak };
}
