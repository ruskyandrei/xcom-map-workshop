// Select all of a kind (refactor stage P8): every drawn piece with the same mesh as a picked one, or every effect of
// the same particle system, sound of the same wave and lens flare of the same template, selected in one go, so that
// the Flags group (flags_panel.js) can set them all; with a box drawn (box select), only those inside it. Here: what
// counts as a kind (kindPiece, effectKind, kindMesh, kindSeeds), the pieces that match (kindMatches), the button and
// its words (kindButton, kindCount) and the selection made (selectKind).
//
// createSelectKind takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, the pieces'
// boxes, the Effects view's switch and what of an effect can change, box select's slack and its stop, the flags' key of
// an actor, the selection and the hints. It keeps no state of its own.
import { allRoots, data, effectRoots, pickBox, pickDrag, roots } from './editor_state.js';
import { recordName } from './effects_rules.js';

export function createSelectKind({ $, boxOf, effectsShown, effectViewOnly, flagKey, flashHint, gizmo, isStream,
                                   PICK_SLACK, plural, select, short, stopPickBox }) {
  // Select all of a kind (piece flags plan, 2.4): every drawn piece with the same mesh as a picked one, by the mesh's
  // full asset path (two packages' meshes of one short name are two kinds; another map's copy of a shared asset is the
  // same kind), selected in one go; with a box drawn (box select), only those whose middle is inside it, as Select
  // takes them. Hidden, deleted and streamed pieces, cover blocks, lights and floor boxes are left out. Selecting is no
  // edit: no undo step and nothing to save. Moving, copying and deleting still take each piece's linked pieces with it.
  function kindPiece(r) {
    const o = r.userData.source;
    return !r.userData.deleted && r.visible && !r.userData.light && !r.userData.volume && !isStream(o) && !o.cover && !o.hidden
      && !o.environment && typeof data.meshes[o.mesh]?.name === 'string';
  }
  // An effect's, a sound's or a lens flare's kind (effects and sounds plan, FX3b; a flare since FX6b): its particle
  // system, the waves it plays or its flare template; null for a sound with no wave, a flare with no template, one not
  // drawn or one the editor doesn't change.
  function effectKind(r) {
    const o = r.userData.source;
    if (!r.visible || r.userData.deleted || isStream(o) || !effectsShown()) return null;
    if (effectViewOnly(o, 'move') && effectViewOnly(o, 'copy') && effectViewOnly(o, 'delete')) return null;
    if (o.kind === 'effect' && o.system) return `system:${o.system}`;
    if (o.kind === 'sound' && o.waves?.length) return `waves:${[...o.waves].sort().join('+')}`;
    if (o.kind === 'flare' && o.template) return `flare:${o.template}`;
    return null;
  }
  // the mesh a piece counts as for Select all of a kind: a made wall as its look's (its template's)
  const kindMesh = r => { const m = data.meshes[r.userData.source.mesh]; return m.look ?? m.name; };
  function kindSeeds() {
    const seeds = new Map();     // full mesh path -> its short name; an effect's system or a sound's waves -> its name
    for (const id of gizmo.picks().ids) {
      const r = roots.get(id), fx = r ? null : effectRoots.get(id);
      if (r && kindPiece(r)) { const name = kindMesh(r); seeds.set(name, short(name)); }
      const kind = fx && effectKind(fx);
      if (kind) seeds.set(kind, recordName(fx.userData.source, data));
    }
    return seeds;
  }
  function kindMatches(seeds) {
    const box = pickBox && !pickDrag ? pickBox : null, out = [];
    const inBox = at => at.every((v, k) => v >= box[k] - PICK_SLACK && v <= box[k + 3] + PICK_SLACK);
    for (const r of roots.values()) {
      if (!kindPiece(r) || !seeds.has(kindMesh(r))) continue;
      if (box) {
        const b = boxOf(r);
        if (!b) continue;
        if (!inBox([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2])) continue;
      }
      out.push(r);
    }
    let effects = 0, flares = 0;
    for (const r of effectRoots.values()) {
      const kind = effectKind(r), e = r.matrix.elements;
      if (!kind || !seeds.has(kind) || (box && !inBox([e[12], e[14], e[13]]))) continue;
      out.push(r); effects++;
      if (r.userData.source.kind === 'flare') flares++;
    }
    return { roots: out, box: Boolean(box), effects, flares, actors: new Set(out.map(r => (r.userData.effect ? r.userData.source.id : flagKey(r.userData.source)))).size };
  }
  // what Select all of a kind counts, in words: pieces, or effects and sounds where only those match
  const kindCount = found => (found.flares && found.flares === found.roots.length ? plural(found.actors, 'lens flare')
    : found.effects && found.effects === found.roots.length ? `${found.actors} ${found.actors === 1 ? 'effect or sound' : 'effects and sounds'}` : plural(found.actors, 'piece'));
  function kindButton() {
    const button = $('editKind'), seeds = data ? kindSeeds() : new Map();
    // the effect panel's own button (a picked effect's or sound's panel stands in the piece panel's place)
    const twin = $('effectKind'), mirror = () => { twin.hidden = !seeds.size || ![...seeds.keys()].some(k => /^(system|waves|flare):/.test(k));
      twin.textContent = kindText; twin.title = button.title; twin.disabled = button.disabled; };
    let kindText = 'Select all';
    if (!seeds.size) {
      mirror();
      button.disabled = true; $('editKindCount').textContent = '';
      button.title = 'Select every piece with the same mesh as the one selected, or every effect of the same particle system, every sound of the same wave, every lens flare of the same template (a light, a cover block, a hidden or streamed piece has none to match)';
      return;
    }
    const found = kindMatches(seeds), picked = new Set(gizmo.picks().ids);
    const what = seeds.size === 1 ? [...seeds.values()][0] : `of these ${seeds.size} kinds`;
    kindText = `Select all${found.box ? ' in box' : ''} (${found.actors})`;
    $('editKindCount').textContent = String(found.actors);
    button.disabled = !found.roots.length || (found.roots.every(r => picked.has(r.userData.source.id)) && found.roots.length === picked.size);
    button.title = found.effects && found.effects === found.roots.length
      ? `Select all ${what}: every drawn effect of the same particle system, every sound of the same wave and every lens flare of the same template ${found.box ? 'inside the box' : 'in the map'}: ${kindCount(found)} (${[...seeds.values()].join(', ')}). Shift+click adds them to the selection.`
      : `Select all ${what}: every drawn piece ${seeds.size === 1 ? 'with this mesh' : 'with one of these meshes'} ${found.box ? 'whose middle is inside the box' : 'in the map'}: `
      + `${plural(found.actors, 'piece')} (${[...seeds.keys()].join(', ')}). Shift+click adds them to the selection. Hidden, deleted and streamed pieces `
      + 'are left out. The Flags group then sets them all; moving, copying and deleting still take each one\'s linked pieces with it.';
    mirror();
  }
  function selectKind(add = false) {
    const seeds = kindSeeds();
    if (!seeds.size) return;
    const found = kindMatches(seeds), was = gizmo.picks();
    if (!found.roots.length) { flashHint('Nothing drawn is of that kind'); return; }
    const ids = found.roots.map(r => r.userData.source.id);
    const next = add ? [...new Set([...was.ids.filter(id => allRoots.get(id)), ...ids])] : ids;
    if (found.box) stopPickBox();
    gizmo.setSelection(next, next.includes(was.active) ? was.active : next[0]);
    select(gizmo.active, false, true);
    flashHint(`${kindCount(found)} of ${seeds.size === 1 ? [...seeds.values()][0] : `${seeds.size} kinds`} selected${found.box ? ' in the box' : ''}`);
  }

  return { kindButton, selectKind };
}
