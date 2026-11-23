// The kinds of mission (tools/viewer/missions.py, private/plans/done/mission-types-plan.md): which kind an export's
// mission is (its `kind`, which the export writes by missions.kind_key since export 37; an older export's from its
// type and council label, by the same rule), and what the play dialog says of it from the server's table
// (/play.json's missionKinds: its state on this path and what a play of it goes without).

const COUNCIL = { 'Council bomb': 'Bomb', 'Council assault': 'Assault', 'Council rescue': 'Rescue', 'Council extraction': 'Extraction' };

/** An export's mission ({type, label, kind}: scene.json's `missions`) as a kind: 'Abduction', 'Special/Bomb'...: its
 * `kind` (export 37), else, for an older export, from its type and its council label. */
export const kindKey = m => typeof m?.kind === 'string' ? m.kind
  : m?.type === 'Special' ? (COUNCIL[m.label] ? `Special/${COUNCIL[m.label]}` : 'Special') : (m?.type ?? '');

/** The mission types a landing zone line can be kept for (eMission_..., eFCMType_...), for an export's mission. */
export function missionTypes(m) {
  const key = kindKey(m), [type, council] = key.split('/');
  return { missionType: `eMission_${type}`, councilType: council ? `eFCMType_${council}` : null };
}

/** Whether a landing zone ({missionType, councilType}) is used on this mission: one kept for none is used on all. */
export function zoneServes(zone, m) {
  if (!zone?.missionType && !zone?.councilType) return true;
  if (!m) return true;
  const t = missionTypes(m);
  return (!zone.missionType || zone.missionType === t.missionType) && (!zone.councilType || zone.councilType === (t.councilType ?? 'eFCMType_None'));
}

/** What the play dialog says under the mission: its state where it has a problem, what the play goes without and the
 * notes, one short paragraph each, joined by line breaks; '' when not known. */
export function missionNote(kinds, m) {
  const k = kinds?.[kindKey(m)];
  if (!k) return '';
  return [k.words ? `${k.words}.` : '', ...(k.missing ?? []), ...(k.notes ?? [])].filter(Boolean).join('\n');
}

/** Text with line breaks as paragraphs: one <p> for each line, in `el` (its children replaced). */
export function setParagraphs(el, value) {
  el.replaceChildren(...String(value ?? '').split('\n').filter(Boolean).map(line => {
    const p = document.createElement('p'); p.textContent = line; return p;
  }));
}

// The kinds a record alone gives a map (missions.py ADDED_KINDS; mission types plan, D3): what each is called and
// needs, whether it is Long War's alone, whether it wants a UFO building and a ship type.
export const ADDED_KINDS = {
  Abduction: { label: 'Abduction', needs: 'Nothing under Long War (pods and Meld are placed at load); plain Enemy Within plays the base map\'s pods where they stood.' },
  TerrorSite: { label: 'Terror', needs: 'Nothing under Long War: civilians stand at cover the game finds.' },
  'Special/Bomb': { label: 'Council bomb', lwr: true, needs: 'Long War only: its bomb mutator places Slaughterhouse\'s bomb and power nodes on the map.' },
  Crash: { label: 'Crashed UFO', ufo: true, needs: 'A UFO building on the map (a UFO prefab): Long War puts the commander\'s pod in it.' },
  LandedUFO: { label: 'Landed UFO', ufo: true, needs: 'A UFO building on the map (a UFO prefab): Long War puts the commander\'s pod in it.' },
};
/** An added kind's mission as the export writes one ({type, label, streams}), for kindKey and the play dialog. */
export const addedMission = kind => ({ type: kind.split('/')[0], label: ADDED_KINDS[kind]?.label ?? kind, streams: [], added: true });

// What Long War Rebalance is told of a map (the project's `lwrMapInfo`, schema 6; missions.py's MAP_INFO, pinned by
// tests/twin_constants.json): LWR 3.00.00 beta 17's map info, which a map pack's card carries. Each of the project's
// keys with LWR's key and the values LWR takes. alienDensity: the largest abduction the map suits (a larger one is
// moved to another map). holdTheLine: No keeps Hold the Line off the map. A key left out is Unknown to LWR: any
// abduction size, Hold the Line can happen, and for a map that takes a vanilla map's place in a pack, that map's own.
export const MAP_INFO = { alienDensity: ['AlienDensity', ['Light', 'Moderate', 'Heavy', 'Swarming']], holdTheLine: ['HoldTheLine', ['No', 'Yes']] };
export const MAP_INFO_SINCE = 'Long War Rebalance 3.00.00 beta 17';
const infoShape = i => Boolean(i) && typeof i === 'object' && !Array.isArray(i);
/** Whether a project's map info is one the page reads: a record of MAP_INFO's keys, each with one of its values. */
export const validMapInfo = i => infoShape(i) && Object.entries(i).every(([k, v]) => MAP_INFO[k]?.[1].includes(v));
/** A map info one the server takes (a record of texts) but the page can't read: carried as saved, for the compiler
 * to leave out. */
export const carriedMapInfo = i => infoShape(i) && Object.values(i).every(v => typeof v === 'string');
/** A valid map info with its keys in MAP_INFO's order; null for an empty one (which says nothing). */
export function tidyMapInfo(info) {
  const out = {};
  for (const key of Object.keys(MAP_INFO)) if (info[key] !== undefined) out[key] = info[key];
  return Object.keys(out).length ? out : null;
}
/** The project's map info for the Map settings controls: the largest abduction chosen ('' for none) and whether
 * Hold the Line is kept off the map. A Yes the project has (written by hand) stays while Hold the Line is not kept
 * off. null when nothing is told. */
export function mapInfoRecord(density, noHold, before = null) {
  const kept = validMapInfo(before) && before.holdTheLine === 'Yes' ? 'Yes' : undefined;
  return tidyMapInfo({ alienDensity: MAP_INFO.alienDensity[1].includes(density) ? density : undefined,
                       holdTheLine: noHold ? 'No' : kept });
}
/** A map info in words: 'abductions up to Moderate, no Hold the Line'. */
export function mapInfoWords(info) {
  const words = [];
  if (info?.alienDensity) words.push(`abductions up to ${info.alienDensity}`);
  if (info?.holdTheLine) words.push(info.holdTheLine === 'No' ? 'no Hold the Line' : 'Hold the Line allowed');
  return words.join(', ');
}
