// The page's one fetch-and-throw helper (web/api.js, review finding 56): the answer's JSON, a refusal thrown with the
// answer's own words (else the caller's), its status and body; JSON sent only with a body; more fetch options passed.
// Run: node tools/viewer/tests/api_test.mjs
import assert from 'node:assert/strict';
import { answer, call, hex16, refusal, serverSaid } from '../web/api.js';

const reply = (status, text, statusText = '') => ({ ok: status >= 200 && status < 300, status, statusText,
  json: async () => JSON.parse(text) });
const asked = [];
globalThis.fetch = async (url, init) => { asked.push([url, init]); return next; };
let next = reply(200, '{"revision": 3}');

// an answer's JSON; a GET carries no body and no content type, a body goes as JSON
assert.deepEqual(await call('GET', '/projects.json'), { revision: 3 });
assert.deepEqual(asked.at(-1), ['/projects.json', { method: 'GET' }]);
await call('PUT', '/squad.json', { expectedRevision: 1 }, { init: { cache: 'no-store' } });
assert.deepEqual(asked.at(-1), ['/squad.json', { method: 'PUT', cache: 'no-store',
  headers: { 'Content-Type': 'application/json' }, body: '{"expectedRevision":1}' }]);
// an empty or unreadable answer is {}
next = reply(200, '');
assert.deepEqual(await call('POST', '/precache/cancel'), {});

// a refusal: the answer's error, its status and the whole body
next = reply(409, '{"error": "Saved elsewhere", "revision": 7}');
await assert.rejects(call('PUT', '/projects/x/project.json', {}), e => e.message === 'Saved elsewhere' && e.status === 409
  && e.body.revision === 7);
// no error of its own: the caller's words, or "The server said <status>"
next = reply(500, 'not json', 'Internal Server Error');
await assert.rejects(call('GET', '/x'), e => e.message === 'The server said 500' && e.status === 500 && Object.keys(e.body).length === 0);
await assert.rejects(call('GET', '/x', undefined, { fallback: r => `${r.status} ${r.statusText}` }), { message: '500 Internal Server Error' });
assert.equal(serverSaid({ status: 404 }), 'The server said 404');
// refusal() and answer() alone (a picture's PUT, a blob's answer)
const e = await refusal(reply(400, '{"error": "Not a PNG"}'));
assert.equal(e.message, 'Not a PNG'); assert.equal(e.status, 400);
assert.deepEqual(await answer(reply(200, '{"sha256": "ab"}')), { sha256: 'ab' });

// the server's picture key: 16 hex digits, the same for the same text (the library's and the look picker's pictures
// were kept under the hash each wrote out before it was shared, so it must not change)
const before = text => {
  let a = 0x811c9dc5, b = 0x01000193;
  for (const c of text) { a = Math.imul(a ^ c.charCodeAt(0), 0x01000193) >>> 0; b = Math.imul(b + c.charCodeAt(0), 0x85ebca6b) >>> 0; b ^= b >>> 13; }
  return (a >>> 0).toString(16).padStart(8, '0') + (b >>> 0).toString(16).padStart(8, '0');
};
for (const text of ['', 'URB_Bar|Emitter_13|likeness2', 'look-sample|1|wall|a|wall|512x384'])
  assert.equal(hex16(text), before(text));
assert.match(hex16('x'), /^[0-9a-f]{16}$/);
console.log('api: ok');
