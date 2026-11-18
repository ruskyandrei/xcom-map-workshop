// The Add panel uses these kinds in both map scopes, including the prefab builder.
const CLASS_KIND = {
  XComDestructibleActor: 'Destructible', XComLevelActor: 'Scenery', XComOpacityFadeLevelActor: 'Scenery',
  StaticMeshActor: 'Scenery', XComFracLevelActor: 'Fracturing', XComDecoFracLevelActor: 'Fracturing',
  XComInteractiveLevelActor: 'Door', KAsset: 'Physics', XComLadder: 'Ladder', XComCollectible: 'Collectible',
};

// An effect's or a sound's kind in the Add panel (the effects and sounds plan, Part E: tools/viewer/effects_library.py
// names them): 'fx:Fire', 'snd:Engines'. The menu has Effects and Sounds for all of them, then each kind; lens
// flares (stage FX6b) are one kind, 'flare:Lens flare', under Lens flares.
export const effectKind = (family, kind) => `${family === 'sound' ? 'snd' : family === 'flare' ? 'flare' : 'fx'}:${kind ?? 'Other'}`;
const EFFECT_KINDS = ['Nature', 'Fire', 'Light beams and glows', 'Smoke and steam', 'Water', 'Alien', 'Wreckage and trash', 'Other'];
const SOUND_KINDS = ['Music and voices', 'Engines', 'Alien', 'Nature and weather', 'Machines', 'Other'];

export function pieceKind(actorClass, family) {
  if (family === 'car') return 'Car';
  if (family === 'van') return 'Van';
  if (family === 'door' || family === 'frameless-door') return 'Door';
  return CLASS_KIND[actorClass] ?? 'Other';
}

export function inKind(entry, kind) {
  if (kind === 'all') return true;
  if (kind === 'floors') return Boolean(entry.floor);
  if (kind === 'lights') return Boolean(entry.light);
  if (kind === 'landing') return Boolean(entry.zone);
  if (kind === 'spawns') return Boolean(entry.spawnAdd);
  if (kind === 'effects') return entry.effect === 'effect';
  if (kind === 'sounds') return entry.effect === 'sound';
  if (kind === 'flares') return entry.effect === 'flare';
  return entry.kind === kind;
}

export function setKindOptions(select, entries) {
  const value = select.value;
  const kinds = ['Car', 'Collectible', 'Destructible', 'Door', 'Fracturing', 'Invisible', 'Ladder',
                 'Other', 'Physics', 'Scenery', 'Van'];
  const counts = new Map();
  for (const entry of entries) {
    const kind = entry.light ? 'lights' : entry.zone ? 'landing' : entry.spawnAdd ? 'spawns' : entry.kind;
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
    if (entry.floor) counts.set('floors', (counts.get('floors') ?? 0) + 1);
    if (entry.effect) counts.set(`${entry.effect}s`, (counts.get(`${entry.effect}s`) ?? 0) + 1);
  }
  // the effects' and sounds' kinds only where the list has some (the map's own scope has none)
  const effects = counts.get('effects') ? [['effects', 'Effects'], ...EFFECT_KINDS.map(k => [effectKind('effect', k), `Effects: ${k}`])] : [];
  const sounds = counts.get('sounds') ? [['sounds', 'Sounds'], ...SOUND_KINDS.map(k => [effectKind('sound', k), `Sounds: ${k}`])] : [];
  const flares = counts.get('flares') ? [['flares', 'Lens flares']] : [];
  select.replaceChildren(new Option('All kinds', 'all'),
    ...[['floors', 'Floors'], ['lights', 'Lights'], ['landing', 'Landing zones'], ...(counts.get('spawns') ? [['spawns', 'Spawn points']] : []),
        ...kinds.map(k => [k, k]), ...effects, ...sounds, ...flares]
      .map(([key, label]) => new Option(`${label} (${(counts.get(key) ?? 0).toLocaleString()})`, key)));
  if ([...select.options].some(o => o.value === value)) select.value = value;
}
