// The prefab library as the page holds it (the prefab menus plan, stage M0): one list behind every view of it (the Add
// panel's Prefabs tab, the Open window's Prefabs side, the menu's count, a placed prefab's group), the folder it is
// kept in, and the actions on a prefab: rename, duplicate, export, delete and import. A view hears of every change
// (onChange) and draws again from the list, so a rename in one shows in the others without asking the server again.
//
// createPrefabLibrary takes the server's routes (prefabs.js `api`, which asks through api.js) and how to hand the
// user a file, so that its node test can give it stand-ins: it holds no document and no three.js. Made once by app.js
// and kept in editor_state.js (`prefabLibrary`).

/**
 * api: list, load, save, remove, importFile, picture, pictureBlob, putPicture (prefabs.js `api`).
 * download(name, document): hand the user a file.
 */
export function createPrefabLibrary({ api, download }) {
  let prefabs = [], folder = '', loaded = false, error = null, loading = null;
  const listeners = new Set();
  const tell = () => { for (const listener of [...listeners]) listener(); };
  const usable = () => prefabs.filter(p => !p.error);

  // The list asked of the server again (one request at a time: a second call while one runs waits for it).
  function refresh() {
    loading ??= api.list().then(answer => { prefabs = answer.prefabs ?? []; folder = answer.folder ?? ''; loaded = true; error = null; })
      .catch(failure => { prefabs = []; loaded = false; error = failure; })
      .finally(() => { loading = null; tell(); });
    return loading;
  }
  // A change on the server, then the list read again whatever came of it.
  async function changing(work) {
    try { return await work(); } finally { await refresh(); }
  }
  const byName = name => usable().find(p => p.name.toLowerCase() === String(name).trim().toLowerCase()) ?? null;
  const byId = id => prefabs.find(p => p.id === id) ?? null;
  // A name no prefab has: the base, else the base with the next number after it.
  function freeName(base) {
    const taken = new Set(usable().map(p => p.name.toLowerCase()));
    let name = base;
    for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${base} ${n}`;
    return name;
  }

  /** Renames a prefab (a new revision of it). Nothing changes for an empty name or the same one. */
  function rename(p, name) {
    name = String(name ?? '').trim();
    if (!name || name === p.name) return Promise.resolve(false);
    return changing(async () => { const doc = await api.load(p.id); await api.save(p.id, { ...doc, name }, doc.revision); return true; });
  }
  /** A copy of a prefab under a free name, its picture with it. Gives the copy's name. */
  function duplicate(p, makeId = () => crypto.randomUUID()) {
    return changing(async () => {
      const doc = await api.load(p.id), id = makeId(), name = freeName(`${p.name} copy`.slice(0, 110));
      const { revision, savedAt, created, ...rest } = doc;
      await api.save(id, { ...rest, id, name }, 0);
      if (p.picture) { const blob = await api.pictureBlob(p.id, p.revision); if (blob) await api.putPicture(id, blob); }
      return name;
    });
  }
  /** The prefab as saved, handed to the user as a file. */
  async function exportFile(p) {
    const doc = await api.load(p.id);
    download(p.file ?? `${p.name}.json`, doc);
    return doc;
  }
  /** Takes a prefab out of the library (the server keeps its file in the library's deleted folder). */
  function remove(p) {
    return changing(() => api.remove(p.id));
  }
  /**
   * A file from elsewhere, checked by the server. One whose id the library has already is refused with a 409 that
   * carries `clash` (the prefab here); `clash` 'replace' (with the revision shown) or 'copy' answers it.
   */
  function importDocument(doc, clash = null, revision = null) {
    return changing(() => api.importFile(doc, clash, clash === 'replace' ? revision : null));
  }

  return {
    refresh, rename, duplicate, exportFile, remove, importDocument, byName, byId, freeName,
    list: () => prefabs,
    usable,
    folder: () => folder,
    get loaded() { return loaded; },
    get error() { return error; },
    picture: p => api.picture(p.id, p.revision),
    /** Calls `listener` after every change of the list; gives a function that stops it. */
    onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
  };
}
