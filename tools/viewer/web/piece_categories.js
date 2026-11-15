// The Add panel uses these kinds in both map scopes, including the prefab builder.
const CLASS_KIND = {
  XComDestructibleActor: 'Destructible', XComLevelActor: 'Scenery', XComOpacityFadeLevelActor: 'Scenery',
  StaticMeshActor: 'Scenery', XComFracLevelActor: 'Fracturing', XComDecoFracLevelActor: 'Fracturing',
  XComInteractiveLevelActor: 'Door', KAsset: 'Physics', XComLadder: 'Ladder', XComCollectible: 'Collectible',
};

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
  return entry.kind === kind;
}

export function setKindOptions(select, entries) {
  const value = select.value;
  const kinds = ['Car', 'Collectible', 'Destructible', 'Door', 'Fracturing', 'Invisible', 'Ladder',
                 'Other', 'Physics', 'Scenery', 'Van'];
  const counts = new Map();
  for (const entry of entries) {
    const kind = entry.light ? 'lights' : entry.zone ? 'landing' : entry.kind;
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
    if (entry.floor) counts.set('floors', (counts.get('floors') ?? 0) + 1);
  }
  select.replaceChildren(new Option('All kinds', 'all'),
    ...[['floors', 'Floors'], ['lights', 'Lights'], ['landing', 'Landing zones'], ...kinds.map(k => [k, k])]
      .map(([key, label]) => new Option(`${label} (${(counts.get(key) ?? 0).toLocaleString()})`, key)));
  if ([...select.options].some(o => o.value === value)) select.value = value;
}
