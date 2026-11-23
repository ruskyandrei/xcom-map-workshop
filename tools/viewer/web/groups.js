// The user's groups (refactor stage P8; project.js holds a group's record: its key, its members' keys, a tree pruned
// of the groups left with one member). A group's pieces select and move as one, a group can hold groups, and its
// pieces can break together in the game. Here:
// - a group's pieces on the map now (liveMembers, liveKeys, ownKeys, liveGroup) and those of them that can break
//   together (breakableCount, breakBlockCount, breakWallCount);
// - what the selection is to the groups (selectionUnits, selectionGroup) and the piece panel's group section with the
//   group chip (groupPanel, which the edit hub runs after an edit: edit_hub.js);
// - the groups changed, each change one undo step (changeGroups): Lock as group (lockAsGroup), Add to group
//   (groupToAddTo, addToGroup), Ungroup (ungroup), and the keys' Ctrl+G and Ctrl+Shift+G (groupShortcut);
// - what a group's members are, by kind, in words (keyWords).
//
// The groups' basics are plain exports at the top, before the factory (they read only the groups and their index,
// editor_state.js's): a group's parent and chain and the outermost locked group it is in (parentGroup, groupChain,
// topLocked), a group's pieces (leafKeys), a piece's member record and key (memberRecord, memberOf), and the groups
// cloned (cloneGroup, cloneGroups); the gizmo, the clipboard and others are given them by app.js.
//
// createGroups takes what it needs of app.js as one argument object, when app.js makes it: the gizmo, what can be
// grouped, the selection's highlight and the group chip, the selection and the hints. It keeps no state of its own:
// the groups, their index and their pieces now (liveCache) are editor_state.js's.
import { isFloor } from './cover.js';
import { onHub } from './edit_hub.js';
import { effectRoots, effectsOn, groupIndex, groups, lightRoots, lightsOn, liveCache, roots, selected, setGroups,
         setLiveCache, volumeRoots } from './editor_state.js';
import { groupKey, memberKey, pruneGroups, uuid } from './project.js';
import { plural } from './dom_words.js';
import { isStream } from './piece_records.js';

// Groups (research/editor-contracts.md, section 2): pieces the user keeps together, saved in the project. A group
// selects and moves as one, with linked pieces on or off; Ungroup ends it. There is no unlocking (the user, 11
// November 2026: "just leave it to group/ungroup"): every group is locked, and a project's `locked` is always true.
// breakTogether is for the game: when one of its breakable pieces is damaged or destroyed, the others are too, and
// its cover blocks go with a destroyed one (the
// compiler and the copier link them).
// A member is also a light (as a piece: its target, or {added}) or one of the project's buildings ({building}; plan
// 5.4a): they move, copy and go with the group, and take no part in breaking together.
// Groups nest (prefab plan 5.4): a member is a piece or another group ({group}); a piece is a direct member of one
// group at most, and a group of one. A piece picked selects the outermost group it is in; Ungroup ends that one, so
// it peels one level; Ctrl+G on pieces and whole groups makes a group of them, the groups kept inside.
// (groups and groupIndex, and setGroups: editor_state.js)
export const parentGroup = g => groupIndex.get(groupKey(g.id));
// A group and the groups it is in, from the inside out.
export function groupChain(g) { const out = []; for (let x = g; x && out.length < 64; x = parentGroup(x)) out.push(x); return out; }
// The outermost locked group among a group and the ones it is in: what a piece of it selects and moves with.
export const topLocked = g => groupChain(g).filter(x => x.locked).at(-1) ?? null;
// The pieces of a group, those of the groups inside it too: their member keys.
export function leafKeys(g, out = [], depth = 0) {
  for (const [k, m] of g.members) {
    if (m.group === undefined) out.push(k);
    else if (groups.has(m.group) && depth < 64) leafKeys(groups.get(m.group), out, depth + 1);
  }
  return out;
}
// A piece's member key and record: an original by package, level and actor; an added piece by its output name.
// (a light is a member as a piece is; a floor box stands for its building, which is a member whole: plan 5.4a)
export const memberRecord = o => (o.isVolume ? { building: volumeRoots.get(o.id)?.userData.volume.building ?? '' }
  : o.added ? { added: o.actor } : { package: o.sourcePackage, level: o.layer, actor: o.actor });
export const memberOf = o => memberKey(memberRecord(o));
export const cloneGroup = g => ({ ...g, members: new Map(g.members) });
export const cloneGroups = (from = groups) => new Map([...from].map(([id, g]) => [id, cloneGroup(g)]));

export function createGroups({ $, flashHint, gizmo, groupables, groupChip, highlight, select }) {
  // Groups' pieces on the map now (deleted ones left out): member key -> its roots. Remade after any change of pieces.
  // (that cache, liveCache: editor_state.js)
  function liveMembers() {
    if (!liveCache) {
      setLiveCache(new Map());
      const live = r => {
        const k = memberOf(r.userData.source);
        if (!liveCache.has(k)) liveCache.set(k, []);
        liveCache.get(k).push(r);
      };
      for (const r of roots.values()) if (!r.userData.deleted) live(r);
      // lights, and the project's buildings by their boxes (a building's key holds all of them)
      for (const r of lightRoots.values()) if (!r.userData.deleted && !r.userData.derivedGone) live(r);
      for (const r of volumeRoots.values()) if (!r.userData.deleted) live(r);
      for (const r of effectRoots.values()) if (!r.userData.deleted && !r.userData.derivedGone && !isStream(r.userData.source)) live(r);
    }
    return liveCache;
  }
  // A group's pieces on the map, those of the groups inside it too; and its own (the ones it holds itself).
  const liveKeys = g => leafKeys(g).filter(k => liveMembers().has(k));
  const ownKeys = g => [...g.members].filter(([k, m]) => m.group === undefined && liveMembers().has(k)).map(([k]) => k);
  // "3 pieces, 1 light and 1 building": a group's members (their keys), by kind.
  function keyWords(keys) {
    const kind = k => { const r = liveMembers().get(k)?.[0]; return k.startsWith('building|') ? 'building' : r?.userData.light ? 'light'
      : r?.userData.effect ? (r.userData.source.kind === 'flare' ? 'lens flare' : r.userData.source.kind) : 'piece'; };
    const parts = ['piece', 'light', 'effect', 'sound', 'lens flare', 'building'].map(w => { const n = keys.filter(k => kind(k) === w).length; return n && plural(n, w); }).filter(Boolean);
    return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? plural(0, 'piece');
  }
  // The group of a piece, if two or more of its pieces are on the map (a delete can leave one; undo brings it back).
  const liveGroup = key => { const g = groupIndex.get(key); return g && liveKeys(g).length >= 2 ? g : undefined; };
  // Pieces that can break in the game: destructible props (collectibles build as such). Breaking together is over a
  // group's own pieces: the groups inside it have the option for themselves.
  const BREAKABLE = new Set(['XComDestructibleActor', 'XComCollectible']);
  const breakableCount = g => ownKeys(g).filter(k => BREAKABLE.has(liveMembers().get(k)[0].userData.source.actorClass)).length;
  // Its cover blocks (high or low, not invisible floors): in a group that breaks together the Build makes each as a
  // hidden prop, which goes when a breakable piece of the group is destroyed. One breakable piece is enough with a block.
  const breakBlockCount = g => ownKeys(g).filter(k => { const c = liveMembers().get(k)[0].userData.source.cover; return c && !isFloor(c); }).length;
  // Its made walls (custom geometry plan, M3 item 4): in a group that breaks together each lists the group's props and
  // cover blocks in the parts of it they stand by (the Build's frac_walls.group_columns), so they go when that part breaks.
  // With a made wall one prop or cover block is enough.
  const breakWallCount = g => ownKeys(g).filter(k => liveMembers().get(k)[0].userData.source.added?.generated?.kind === 'fracWall').length;
  // The selected pieces as units: each piece stands for the outermost group all of whose pieces are selected
  // (groupKey(id)), or for itself (its member key).
  function selectionUnits(keys) {
    const units = new Set(), whole = new Map(), isWhole = g => {
      if (!whole.has(g.id)) whole.set(g.id, liveKeys(g).every(k => keys.has(k)));
      return whole.get(g.id);
    };
    for (const k of keys) {
      let unit = k;
      for (const g of groupChain(groupIndex.get(k))) { if (!isWhole(g)) break; unit = groupKey(g.id); }
      units.add(unit);
    }
    return units;
  }
  // What the selection is to the groups: { kind, group, units }. 'whole': one group, all of its pieces on the map and
  // nothing else (the outermost such); 'part': some of one group's pieces or inner groups only (an unlocked group: the
  // innermost group that holds them all; `units` says how many pieces and whole groups they are); 'new': two or more
  // pieces or whole groups that no one group holds; null: nothing to do.
  function selectionGroup() {
    const keys = new Set(groupables().map(r => memberOf(r.userData.source)));
    if (!keys.size) return { kind: null };
    const units = selectionUnits(keys);
    if (units.size === 1 && [...units][0].startsWith('group|')) return { kind: 'whole', group: groups.get([...units][0].slice(6)), units: 1 };
    let common = null;
    for (const k of keys) {
      const chain = groupChain(groupIndex.get(k));
      common = common ? common.filter(g => chain.includes(g)) : chain;
      if (!common.length) break;
    }
    if (common?.length) return { kind: 'part', group: common[0], units: units.size };
    return { kind: units.size >= 2 ? 'new' : null, count: units.size, groups: [...units].filter(u => u.startsWith('group|')).length };
  }
  // The group section of the piece panel, the group chip and the colour of the selection box (gold for a group).
  const BREAK_TOGETHER_TITLE = $('groupBreakRow').title;
  function groupPanel() {
    const box = $('groupBox'), { kind, group: g, count, groups: wholeGroups, units } = selectionGroup();
    box.hidden = !kind;
    groupChip.hidden = !g;
    highlight.material.color.set(g && kind === 'whole' ? 0xe8bd5c : 0x96e5d7);
    if (!kind) return;
    const n = g ? liveKeys(g).length : count;
    box.classList.toggle('locked', Boolean(g));
    $('groupMake').hidden = kind !== 'new';
    const adding = kind === 'new' ? groupToAddTo() : null;
    $('groupAdd').hidden = !adding;
    $('groupDissolve').hidden = $('groupBreakRow').hidden = !g;
    if (!g) {
      $('groupTitle').textContent = 'Not grouped';
      $('groupText').textContent = wholeGroups
        ? `Group these ${n} (${plural(wholeGroups, 'group')}${n > wholeGroups ? ` and ${plural(n - wholeGroups, 'piece')}` : ''}) to select and move them as one. The groups stay as they are inside the new one.`
        : `Group these ${n} pieces to select and move them as one, and to give them group options.`;
      if (adding) $('groupText').textContent += ` Add to group puts the ${keyWords(adding.loose)} in the group instead, which keeps its options.`;
      $('groupNote').hidden = true;
      return;
    }
    groupChip.className = 'chip group';
    groupChip.textContent = `Group of ${n}`;
    groupChip.title = 'Its pieces select and move as one (Ctrl+Shift+G ungroups it)';
    const inner = [...g.members.values()].filter(m => m.group !== undefined && groups.has(m.group)).length;
    $('groupTitle').textContent = `${g.prefab ? `Prefab · ${g.prefab.name}` : 'Group'} · ${keyWords(liveKeys(g))}${inner ? `, ${plural(inner, 'group')} inside` : ''}`;
    // (some of its pieces picked on their own: Ctrl and the wheel, pick_step.js, or a light or effect in its own view)
    $('groupText').textContent = kind === 'part'
      ? `${units === 1 ? 'One' : units} of the ${n} pieces of this group, picked on ${units === 1 ? 'its' : 'their'} own${lightsOn || effectsOn ? '' : ' · a click picks the group'}`
      : (g.prefab ? `Placed from the prefab ${g.prefab.name} (revision ${g.prefab.revision}): a copy of its own, which changes to the prefab don't reach. ` : '')
      + (inner
      ? 'Everything in it selects and moves as one, whether linked pieces are on or off. Ungroup it to get the groups inside it back on their own.'
      : 'Its pieces select and move as one, whether linked pieces are on or off. Ungroup it to move one on its own.');
    $('groupBreak').checked = g.breakTogether;
    const breakable = breakableCount(g), blocks = breakBlockCount(g), walls = breakWallCount(g);
    const can = breakable >= 2 || (breakable >= 1 && blocks >= 1) || (walls >= 1 && breakable + blocks >= 1);
    $('groupBreakRow').classList.toggle('off', !can && !g.breakTogether);
    $('groupBreak').disabled = !can && !g.breakTogether;
    const note = $('groupNote');
    const own = ownKeys(g).length, stay = own - breakable - blocks - (can ? walls : 0);
    note.hidden = !(!can || (g.breakTogether && (stay > 0 || blocks || walls || inner)));
    note.classList.toggle('how', !can);
    $('groupBreakRow').title = !can ? 'Needs two breakable pieces (props) of the group\'s own, or one and a cover block or a made wall' : BREAK_TOGETHER_TITLE;
    note.textContent = !can
      ? `Breaking together needs two breakable pieces (props) of the group's own, or one and a cover block or a made wall: this group has ${breakable}${blocks ? ` and ${plural(blocks, 'cover block')}` : ''}${walls ? ` and ${plural(walls, 'made wall')}` : ''}. The map's walls and scenery move with a group but don't break with it${inner ? ', and the groups inside it have the option for themselves' : ''}.`
      : [walls ? `Its props and cover blocks go when the part of ${walls === 1 ? 'its made wall' : 'a made wall of it'} they stand by breaks.` : '',
         blocks ? `${blocks === 1 ? 'Its cover block goes' : `Its ${blocks} cover blocks go`} when a breakable piece of the group is destroyed${walls ? ' or the wall behind it breaks' : ''}; nothing else destroys ${blocks === 1 ? 'it' : 'them'}.` : '',
         stay > 0 ? `${plural(stay, 'piece')} of the group ${stay === 1 ? 'is' : 'are'} not breakable and stay${stay === 1 ? 's' : ''} standing.` : '',
         inner ? 'The groups inside it break by their own option.' : ''].filter(Boolean).join(' ');
  }
  // A change to the groups as one undo step; the panel and the selection follow.
  function changeGroups(edit, message) {
    const before = cloneGroups(), after = cloneGroups();
    edit(after);
    gizmo.record({ redo: () => setGroups(cloneGroups(after)), undo: () => setGroups(cloneGroups(before)) });
    select(gizmo.active, false, true);
    if (message) flashHint(message);
  }
  // Lock as group (Ctrl+G): the selected pieces and whole groups become one locked group, the groups kept as they
  // are inside it. Pieces picked out of a group leave it (a group left with fewer than two members ends), and the new
  // group breaks together if one of those did. When one group held them all, the new group is made inside it.
  function lockAsGroup() {
    const records = new Map(groupables().map(r => [memberOf(r.userData.source), memberRecord(r.userData.source)]));
    const units = selectionUnits(new Set(records.keys()));
    if (units.size < 2) { flashHint('Select two or more pieces or groups to group them'); return; }
    const from = [...units].map(u => groupIndex.get(u)), id = uuid();
    // one group holds them all (some of its pieces or inner groups): the new group is made inside it
    // (only some of a group's pieces can be selected when the rest can't be, a streamed patch's say)
    const held = selectionGroup(), within = held.kind === 'part' ? held.group : null;
    const breakTogether = [...units].some((u, k) => !u.startsWith('group|') && from[k]?.breakTogether);
    const inner = [...units].filter(u => u.startsWith('group|')).length;
    changeGroups(next => {
      const members = new Map();
      [...units].forEach((u, k) => {
        if (from[k]) next.get(from[k].id).members.delete(u);
        members.set(u, records.get(u) ?? { group: u.slice(6) });
      });
      next.set(id, { id, locked: true, breakTogether, members });
      if (within) next.get(within.id).members.set(groupKey(id), { group: id });
      pruneGroups(next);
    }, `Grouped ${inner ? `${plural(inner, 'group')}${units.size > inner ? ` and ${plural(units.size - inner, 'piece')}` : ''}` : plural(units.size, 'piece')}`
       + `${within ? ' inside its group' : ''} · they select and move as one`);
  }
  // Add to group (the user, 19 November 2026): a selection of one whole group and pieces (lights, buildings) that are in
  // no group puts those in that group, which keeps its options, rather than making a new group of them all. Gives
  // { group, loose (their member keys), records } when the selection is so, else null.
  function groupToAddTo() {
    const records = new Map(groupables().map(r => [memberOf(r.userData.source), memberRecord(r.userData.source)]));
    const units = [...selectionUnits(new Set(records.keys()))];
    const whole = units.filter(u => u.startsWith('group|')), loose = units.filter(u => !u.startsWith('group|'));
    const group = whole.length === 1 ? groups.get(whole[0].slice(6)) : null;
    return group && loose.length && loose.every(k => !groupIndex.get(k)) ? { group, loose, records } : null;
  }
  function addToGroup() {
    const add = groupToAddTo();
    if (!add) { flashHint('Select one group and pieces that are in no group to add them to it'); return; }
    const words = keyWords(add.loose);
    changeGroups(next => { const g = next.get(add.group.id); for (const k of add.loose) g.members.set(k, add.records.get(k)); },
      `Added ${words} to the group · ${add.loose.length === 1 ? 'it selects and moves' : 'they select and move'} with it`);
  }
  // Ungroup: the group ends; its pieces and the groups inside it stay, in the group it was in if it was in one.
  function ungroup(g) {
    const inner = [...g.members.values()].some(m => m.group !== undefined);
    changeGroups(next => {
      const gone = next.get(g.id), outer = [...next.values()].find(o => o.members.has(groupKey(g.id)));
      next.delete(g.id);
      if (outer) { outer.members.delete(groupKey(g.id)); for (const [k, m] of gone.members) outer.members.set(k, m); }
      pruneGroups(next);
    }, inner ? 'Ungrouped · the groups inside it stay groups' : 'Ungrouped · the pieces are separate again');
  }
  // Ctrl+G groups the selection; Ctrl+Shift+G ungroups the selected group.
  function groupShortcut(dissolve) {
    const { kind, group: g } = selectionGroup();
    if (dissolve) { if (g) ungroup(g); else flashHint('Select a group to ungroup it'); return; }
    if (kind === 'new') lockAsGroup();
    else if (g) flashHint('Already a group · Ctrl+Shift+G ungroups it');
    else flashHint('Select two or more pieces or groups to group them');
  }

  // After an edit (the edit hub, edit_hub.js). (a building's box is in no group)
  onHub('edit', 'groups', () => { if (volumeRoots.has(selected)) $('groupBox').hidden = true; else groupPanel(); });

  return { addToGroup, changeGroups, groupShortcut, liveGroup, liveKeys, liveMembers, lockAsGroup, selectionGroup,
           ungroup };
}
