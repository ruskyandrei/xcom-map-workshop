// Asking the editor's server (review finding 56): one fetch-and-throw helper for every module, in place of the twelve
// copies each module had. An answer's JSON is given back ({} when it has none); a refusal throws an Error whose message
// is the answer's own `error` (or the caller's fallback words), with `status` (the HTTP status) and `body` (the
// answer's JSON, {} when it had none). A read whose failure the page takes as "none" asks with `ask` (null when it
// fails), and a PNG goes with `sendPng` (follow-up 3.28). What stays a plain fetch elsewhere reads what these cannot: a
// picture read as a blob, the wave's range probe (effects_wiring.js) and the scene's layout read with its progress
// (loading.js); tests/one_home_test.mjs holds the list.

/** The words a refusal with no `error` of its own is thrown with, unless the caller gives others. */
export const serverSaid = response => `The server said ${response.status}`;

/** The Error a refused `response` is thrown as: its `error`, else fallback(response); { status, body } on it. */
export async function refusal(response, fallback = serverSaid) {
  const body = await response.json().catch(() => ({}));
  return Object.assign(new Error(body?.error || fallback(response)), { status: response.status, body });
}

/** The JSON of `response`, or its refusal thrown. */
export async function answer(response, fallback = serverSaid) {
  if (!response.ok) throw await refusal(response, fallback);
  return response.json().catch(() => ({}));
}

/** The 16 hex digits the server keeps a picture under (its key form), made from `text`: two 32-bit hashes of it. The
 *  library's effect pictures and the look picker's samples are kept by these. */
export function hex16(text) {
  let a = 0x811c9dc5, b = 0x01000193;
  for (const c of text) {
    a = Math.imul(a ^ c.charCodeAt(0), 0x01000193) >>> 0;
    b = Math.imul(b + c.charCodeAt(0), 0x85ebca6b) >>> 0; b ^= b >>> 13;
  }
  return a.toString(16).padStart(8, '0') + (b >>> 0).toString(16).padStart(8, '0');
}

/** Ask the server: `method` at `url`, `body` sent as JSON (undefined: no body). `fallback(response)`: the refusal's
 *  words when the answer has no `error`; `init`: more fetch options (cache, for one). */
export async function call(method, url, body, { fallback = serverSaid, init = {} } = {}) {
  const response = await fetch(url, { method, ...init,
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
  return answer(response, fallback);
}

/** The JSON of a GET of `url`, or null when it fails: refused, not answered, or not JSON. For the reads a failure leaves
 *  as none (a map's families, its collision, its spawn rules, the map list brought up to date, the kept pictures). */
export async function ask(url) {
  try {
    const response = await fetch(url);
    return response.ok ? await response.json() : null;
  } catch { return null; }
}

/** A PNG `blob` sent to the server, `method` at `url`: the response as fetch gives it, whose ok, JSON or blob the caller
 *  reads (a library thumbnail, a look sample, a prefab's picture, the map picture and its preview). */
export const sendPng = (method, url, blob) => fetch(url, { method, headers: { 'Content-Type': 'image/png' }, body: blob });
