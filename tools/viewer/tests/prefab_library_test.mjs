// The prefab library store (prefab_library.js; the prefab menus plan, stage M0), driven with a stand-in for the
// server: the list, rename, duplicate (its picture with it), export, delete, an import and its clash, and a view told
// of each change. Run: node tools/viewer/tests/prefab_library_test.mjs
import assert from 'node:assert/strict';
import { createPrefabLibrary } from '../web/prefab_library.js';

// A stand-in for the server's routes (prefabs.js `api`): documents by id, a picture per id, a list of summaries.
function server() {
  const docs = new Map(), pictures = new Map(), calls = [];
  const summary = d => ({ id: d.id, name: d.name, revision: d.revision, file: `${d.name}.json`, picture: pictures.has(d.id), pieces: d.pieces.length });
  const put = (doc, revision) => { docs.set(doc.id, { ...doc, revision }); return { revision }; };
  put({ id: 'a', name: 'Shed', pieces: [1, 2] }, 3);
  put({ id: 'b', name: 'Fence', pieces: [1] }, 1);
  pictures.set('a', 'picture of a');
  const api = {
    list: async () => { calls.push('list'); return { folder: '<prefabs>', prefabs: [...docs.values()].map(summary).concat([{ file: 'broken.json', error: 'not JSON' }]) }; },
    load: async id => { calls.push(`load ${id}`); if (!docs.has(id)) throw Object.assign(Error('gone'), { status: 404 }); return structuredClone(docs.get(id)); },
    save: async (id, doc, expected) => {
      calls.push(`save ${id}`);
      const here = docs.get(id);
      if ((here?.revision ?? 0) !== expected) throw Object.assign(Error('saved elsewhere'), { status: 409 });
      return put({ ...doc, id }, expected + 1);
    },
    remove: async id => { calls.push(`remove ${id}`); docs.delete(id); return {}; },
    importFile: async (doc, clash, expectedRevision) => {
      calls.push(`import ${clash ?? 'ask'}`);
      const here = docs.get(doc.id);
      if (here && !clash) throw Object.assign(Error('clash'), { status: 409, body: { clash: { name: here.name, revision: here.revision } } });
      if (here && clash === 'copy') { put({ ...doc, id: `${doc.id}-copy`, name: `${doc.name} (imported)` }, 1); return { name: `${doc.name} (imported)`, revision: 1 }; }
      if (here) { assert.equal(expectedRevision, here.revision); put(doc, here.revision + 1); return { name: doc.name, revision: here.revision + 1, replaced: true }; }
      put(doc, 1); return { name: doc.name, revision: 1 };
    },
    picture: (id, revision) => `/prefabs/${id}/picture.png?r=${revision}`,
    pictureBlob: async id => pictures.get(id) ?? null,
    putPicture: async (id, blob) => { pictures.set(id, blob); },
  };
  return { api, docs, pictures, calls };
}

const { api, docs, pictures, calls } = server();
const downloads = [];
const library = createPrefabLibrary({ api, download: (name, doc) => downloads.push([name, doc]) });
let told = 0;
const stop = library.onChange(() => { told += 1; });

// the list, the folder, the usable prefabs (a broken file listed but not usable)
assert.equal(library.loaded, false);
await library.refresh();
assert.equal(library.loaded, true);
assert.equal(library.folder(), '<prefabs>');
assert.equal(library.list().length, 3);
assert.deepEqual(library.usable().map(p => p.name), ['Shed', 'Fence']);
assert.equal(told, 1, 'a view is told when the list is read');
assert.equal(library.byName(' shed ')?.id, 'a');
assert.equal(library.byId('b')?.name, 'Fence');
assert.equal(library.picture(library.byId('a')), '/prefabs/a/picture.png?r=3');
// two refreshes at once ask the server once
calls.length = 0;
await Promise.all([library.refresh(), library.refresh()]);
assert.deepEqual(calls, ['list']);

// rename: a new revision under the new name; the same name or an empty one changes nothing
told = 0;
assert.equal(await library.rename(library.byId('a'), 'Big shed'), true);
assert.equal(docs.get('a').name, 'Big shed');
assert.equal(docs.get('a').revision, 4);
assert.equal(library.byId('a').name, 'Big shed', 'the list is read again after a change');
assert.equal(told, 1);
calls.length = 0;
assert.equal(await library.rename(library.byId('a'), '  '), false);
assert.equal(await library.rename(library.byId('a'), 'Big shed'), false);
assert.deepEqual(calls, [], 'nothing asked of the server for no change');

// duplicate: a free name, revision 1, the picture taken along
assert.equal(library.freeName('Fence'), 'Fence 2');
const name = await library.duplicate(library.byId('a'), () => 'c');
assert.equal(name, 'Big shed copy');
assert.equal(docs.get('c').name, 'Big shed copy');
assert.equal(docs.get('c').revision, 1);
assert.equal(pictures.get('c'), 'picture of a');
assert.equal(await library.duplicate(library.byId('a'), () => 'd'), 'Big shed copy 2', 'a second copy takes the next free name');

// export: the document as saved, under its file's name
const exported = await library.exportFile(library.byId('b'));
assert.equal(exported.name, 'Fence');
assert.deepEqual(downloads.map(d => d[0]), ['Fence.json']);

// delete
told = 0;
await library.remove(library.byId('d'));
assert.equal(docs.has('d'), false);
assert.equal(library.byId('d'), null);
assert.equal(told, 1);

// import: a new prefab; one whose id is here already is a clash with what is here, answered by replace or copy
await library.importDocument({ id: 'e', name: 'Crate', pieces: [] });
assert.equal(library.byId('e')?.name, 'Crate');
const clash = await library.importDocument({ id: 'b', name: 'Fence from a friend', pieces: [] }).catch(e => e);
assert.equal(clash.status, 409);
assert.deepEqual(clash.body.clash, { name: 'Fence', revision: 1 });
assert.equal(docs.get('b').name, 'Fence', 'a clash changes nothing');
const replaced = await library.importDocument({ id: 'b', name: 'Fence from a friend', pieces: [] }, 'replace', 1);
assert.equal(replaced.replaced, true);
assert.equal(library.byId('b').name, 'Fence from a friend');
await library.importDocument({ id: 'b', name: 'Fence', pieces: [] }, 'copy');
assert.equal(library.byName('Fence (imported)')?.id, 'b-copy');

// a change that fails still reads the list again, and the failure reaches the caller
told = 0;
const failed = await library.rename({ id: 'gone', name: 'Old' }, 'New').catch(e => e);
assert.equal(failed.status, 404);
assert.equal(told, 1);

// a list that cannot be read: empty, not loaded, its error kept for the views
const broken = createPrefabLibrary({ api: { ...api, list: async () => { throw Object.assign(Error('no library'), { status: 404 }); } }, download: () => {} });
await broken.refresh();
assert.equal(broken.loaded, false);
assert.equal(broken.error.status, 404);
assert.deepEqual(broken.list(), []);

// a view that stops listening hears no more
stop();
told = 0;
await library.refresh();
assert.equal(told, 0);

console.log('prefab library store: ok');
