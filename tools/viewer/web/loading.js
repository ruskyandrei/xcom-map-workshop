// The loading overlay (refactor stage P9): what the page says while a map, a project or a prefab opens. Here: the
// overlay's message, its bar when the share done is known and its detail line (loadingState), what an opening
// document's steps say on it (openingProgress, OPENING), and a JSON file read with its progress (fetchJson, the scene's
// layout as a map opens).
//
// createLoading takes app.js's `$` when app.js makes it (early: nothing of it runs as the page loads, and the
// document session, the prefab builder's and the scene's pieces show it); it keeps no state.
import { plural } from './dom_words.js';

export function createLoading({ $ }) {
  // The loading overlay: what is happening, a progress bar when the share done is known, and a detail line.
  // What an opening document's steps say on the loading overlay: the pieces of other maps read (the first 40% of the
  // bar), loaded with their meshes (to 70%) and the document's own pieces made (the rest).
  const OPENING = { reading: [0, 0.4, 'reading'], loading: [0.4, 0.3, 'loading'], making: [0.7, 0.3, 'making'] };
  const openingProgress = name => (phase, done, total) => {
    const [from, share, word] = OPENING[phase];
    loadingState(`Opening ${name}: ${word} ${done} of ${plural(total, 'piece')}…`, from + share * (total ? done / total : 1));
  };
  function loadingState(message, fraction = null, detail = '') {
    $('loadingText').textContent = message;
    $('loadingBar').hidden = fraction == null;
    if (fraction != null) $('loadingBar').firstElementChild.style.width = `${Math.round(100 * Math.min(1, Math.max(0, fraction)))}%`;
    $('loadingDetail').textContent = detail;
  }
  // A JSON file read with its progress (onProgress(share) as it arrives; the server sends its length).
  async function fetchJson(url, onProgress) {
    const response = await fetch(url);
    if (!response.ok) throw Error(`Scene request failed: ${response.status}`);
    const length = Number(response.headers.get('Content-Length')) || 0;
    if (!length || !response.body) return response.json();
    const reader = response.body.getReader(), chunks = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value); received += value.length;
      onProgress(received / length);
    }
    return JSON.parse(new TextDecoder().decode(await new Blob(chunks).arrayBuffer()));
  }

  return { fetchJson, loadingState, openingProgress };
}
