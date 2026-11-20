// Settings kept per browser (review finding 56): every key is `workshop.<name>`. The keys of the two older styles
// (`viewer.<name>`, a bare name and `xcom-map-workshop.<module>.<name>`) are read once and moved to their new names, so
// nothing a browser kept is lost. Storage can be missing or blocked: a read then gives null and a write is dropped.

const MOVED = {
  'workshop.stats': 'viewer.stats', 'workshop.sourceDetails': 'viewer.sourceDetails', 'workshop.pivot': 'viewer.pivot',
  'workshop.flyKeys': 'viewer.flyKeys', 'workshop.moveSpeed': 'viewer.moveSpeed', 'workshop.turnSpeed': 'viewer.turnSpeed',
  'workshop.dragSpeed': 'viewer.dragSpeed', 'workshop.gameMapsGroup': 'gameMapsGroup',
  'workshop.managerProjectFiles': 'xcom-map-workshop.manager.projectFiles',
};
/** The older name a key was kept under, or null: the table's, and a panel section's fold `viewer.fold.<name>`. */
export const oldKey = key => MOVED[key] ?? (key.startsWith('workshop.fold.') ? `viewer.fold.${key.slice('workshop.fold.'.length)}` : null);

/** The value kept under `key` (a key of the older style moved to it the first time), or null. */
export function recall(key) {
  try {
    const value = localStorage.getItem(key), old = value === null ? oldKey(key) : null;
    if (old === null) return value;
    const kept = localStorage.getItem(old);
    if (kept !== null) { localStorage.setItem(key, kept); localStorage.removeItem(old); }
    return kept;
  } catch { return null; }
}
export const remember = (key, value) => { try { localStorage.setItem(key, value); } catch { /* not kept */ } };
export const forget = key => { try { localStorage.removeItem(key); } catch { /* not kept */ } };
