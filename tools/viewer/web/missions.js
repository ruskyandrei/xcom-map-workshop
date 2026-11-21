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
