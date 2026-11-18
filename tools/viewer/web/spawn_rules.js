// What the game does with a spawn point or a mission's objective (private/plans/todo/editor-spawns-implementation-plan.md,
// SP2): the sentences the Spawns inspector shows under "In the game", from the record (export 33), the mission the
// header shows (an export's mission: {type, label}) and what the install does (/maps/<id>/spawn-rules.json:
// tools/viewer/spawnrules.py). Pure: no page, no three.js. The table follows the spawns plan's 2.3 and 2.4 and the
// decompiled Long War mutators (XComPodSpawnMutator, XComMeldSpawnMutator, XComSpawnAlienMutator, XComBombMutator).

/** Whether a family's Long War mutator is in the install's loader ('active'), from the rules; false on plain EW. */
export const active = (rules, family) => rules?.[family] === 'active';

const KIND_FAMILY = { pod: 'pods', meld: 'meld', dropIn: 'dropIns', bomb: 'bomb', powerNode: 'bomb' };
// the missions whose pods Long War leaves (XComPodSpawnMutator: the HQ assault, the final mission), and those where it
// keeps the map's commander (an alien base; a battleship or overseer's ship type is read in the game, not here)
const PODS_LEFT = new Set(['HQAssault', 'Final']);
const COMMANDER_KEPT = new Set(['AlienBase']);
const UFO_MISSIONS = new Set(['Crash', 'LandedUFO']);
// the missions the game spawns Meld on (XGBattleDesc.ShouldSpawnMeldCanisters, as the play's test mission notes)
const MELD_MISSIONS = new Set(['Abduction', 'Crash', 'LandedUFO']);
// the missions whose landing Long War leaves where the map puts it (XComLZMutator)
const LANDING_LEFT = new Set(['CovertOpsExtraction', 'CaptureAndHold', 'Special/Rescue', 'Special/Extraction']);

const key = m => (m?.type === 'Special' ? ({ 'Council bomb': 'Special/Bomb', 'Council rescue': 'Special/Rescue', 'Council extraction': 'Special/Extraction', 'Council assault': 'Special/Assault' }[m.label] ?? 'Special') : m?.type ?? '');
const short = path => String(path ?? '').split('.').pop();

/** A wave use's words: "destination of XComWaveSystem_0 set 1, wave 2, group 1 (3rd)". */
export function waveWords(u) {
  return `${u.role === 'origin' ? 'origin' : 'destination'} of ${u.by} set ${u.set}, wave ${u.wave}, group ${u.group}`;
}

/** The scripted actions that drop units at a point (direct and indirect Kismet uses by a SeqAct_SpawnAlien or an
 * object list that feeds one). */
export function scriptedUsers(record) {
  const out = [];
  for (const u of record?.uses ?? []) {
    if (u.how === 'direct' && u.byClass === 'SeqAct_SpawnAlien') out.push(u.by);
    else if (u.how === 'indirect') out.push(...(u.then?.length ? u.then : [u.by]));
  }
  return [...new Set(out)];
}

/** The sentences for a record under "In the game". context: { rules (spawn-rules.json, or null while not read),
 * mission (the header's: {type, label}), placed (spawnRules.dropIns === 'placed'), mapExcluded (the base map is in
 * ExcludeMaps), donor (an added kind's donor object) }. */
export function consumerWords(record, context = {}) {
  const { rules = null, mission = null, placed = false, mapExcluded = false } = context;
  const kind = record?.kind, mk = key(mission), lines = [];
  const lw = rules?.kind === 'lwr' || rules?.kind === 'longwar';
  const family = KIND_FAMILY[kind];
  const on = family ? active(rules, family) : false;
  const unknown = family && rules && rules[family] === 'unknown';
  switch (kind) {
    case 'pod': {
      lines.push('One of the places the game deploys pods at. It may stay empty: the squad decides how many are used, the nearest first.');
      if (record.values?.commander?.value) lines.push('A commander\'s place: the mission\'s commander pod takes it first.');
      if (record.values?.use?.value === false) lines.push('Its Use is off: the deployment leaves it out where the Overmind decides so.');
      if (on) {
        if (PODS_LEFT.has(mk)) lines.push(`Long War leaves the pods of ${mission?.label ?? 'this mission'} where the map has them: this one plays here.`);
        else {
          lines.push('Long War replaces the map\'s pods with places of its own when it finds enough; this one plays when it doesn\'t.');
          if (COMMANDER_KEPT.has(mk) && record.values?.commander?.value) lines.push('On an alien base Long War keeps the commander\'s place: this one stays.');
          if (UFO_MISSIONS.has(mk)) lines.push('On a UFO mission Long War first looks for a commander\'s place inside the UFO.');
        }
      }
      break;
    }
    case 'meld': {
      const v = record.values ?? {};
      const turn = v.destroyedOnTurn?.value;
      lines.push(`A candidate: the game draws from the points of its spawn group (${v.spawnGroup?.value ?? 0}), a hard one first; three points don't promise three canisters.`);
      if (turn !== undefined) lines.push(turn > 0 ? `${v.difficulty?.value ?? 'Easy'}; it is destroyed on turn ${turn}.` : `${v.difficulty?.value ?? 'Easy'}; no countdown.`);
      if (mission && !MELD_MISSIONS.has(mk)) lines.push(`${mission.label} spawns no Meld.`);
      if (on) lines.push(`Long War replaces every Meld point when it finds ${rules?.config?.meldContainers ?? 3} places; this one plays when it doesn't.`);
      break;
    }
    case 'dropIn': {
      const waves = (record.uses ?? []).filter(u => u.how === 'wave');
      const actions = scriptedUsers(record);
      if (actions.length) lines.push(`Used by ${actions.join(', ')}.`);
      for (const u of waves.slice(0, 4)) lines.push(`${waveWords(u)[0].toUpperCase()}${waveWords(u).slice(1)}.`);
      if (waves.length > 4) lines.push(`… and ${waves.length - 4} more wave places.`);
      if (!actions.length && !waves.length) lines.push('Nothing in its package was found using it (another layer or the game\'s code may).');
      if (actions.length && on) {
        if (placed) lines.push('The project leaves scripted drop-ins where placed: it plays here.');
        else if (mapExcluded) lines.push('The install\'s ExcludeMaps names the base map, not the variant: Long War would drop the unit near a soldier instead.');
        else lines.push(`Long War drops the unit near a soldier instead (${rules?.config?.dropMin ?? 7} to ${rules?.config?.dropMax ?? 32} tiles), unless the map is in its exclusion list.`);
      }
      if (waves.length && lw) lines.push('Long War does not move a wave\'s units.');
      break;
    }
    case 'bomb': case 'powerNode':
      if (on) lines.push('Long War moves the bomb and its nodes to places of its own when it finds one for each; they play here when it doesn\'t.');
      else lines.push('Plays where it stands.');
      break;
    case 'soldier': case 'start': case 'landing':
      lines.push(`The squad's landing${record.tag ? ` (${record.tag})` : ''}.`);
      if (active(rules, 'landing')) lines.push(LANDING_LEFT.has(mk) ? `Long War leaves the landing of ${mission?.label} where the map puts it.` : 'Long War lands the squad at one of the map\'s landing lines.');
      break;
    case 'operative': lines.push('Where the covert operative starts.'); break;
    case 'vip': lines.push('Where a VIP the mission escorts starts.'); break;
    case 'capturePoint': lines.push('A capture point: the squad holds it to take the data.'); break;
    case 'radar': lines.push('A radar array the mission\'s script uses.'); break;
    case 'pathNode': lines.push('A patrol node: the pods that list it walk their route through it.'); break;
    case 'noSpawn': lines.push('A no-spawn volume: the game places no unit inside it.'); break;
    default: break;
  }
  if (unknown) lines.push('Whether the install\'s Long War mutator for it is on could not be read.');
  if (!rules && family) lines.push('(What the install does is still being read.)');
  return lines;
}

/** The uses in the inspector's words: { usedBy: [...], uses: [...] } ("Used by" incoming, "Uses" outgoing). */
export function useLines(record) {
  const usedBy = [];
  for (const u of record?.uses ?? []) {
    if (u.how === 'wave') usedBy.push(waveWords(u));
    else if (u.how === 'event') usedBy.push(`${u.by} (fires when pod ${u.podId} is revealed)`);
    else if (u.how === 'typed') usedBy.push(`${u.by}'s ${u.property}`);
    else if (u.how === 'indirect') usedBy.push(`${u.by} ${u.link} (an object list${u.then?.length ? `, then ${u.then.join(', ')}` : ''})`);
    else if (u.how === 'variable') usedBy.push(`${u.by} (a Kismet variable nothing reads)`);
    else usedBy.push(`${u.by} ${u.link ?? ''}`.trim());
  }
  const uses = (record?.links ?? []).map(l => `${l.property}: ${short(l.actor)}`);
  return { usedBy: [...new Set(usedBy)], uses };
}

/** A value's provenance in words: "(the map's)", "(its archetype's)", "(the class's)". */
export function fromWords(from) {
  return { saved: '(the map\'s)', archetype: '(its archetype\'s)', class: '(the class\'s)', unknown: '(not read)',
           project: '(the project\'s)' }[from] ?? '';
}
