// The Cache everything window (the Settings menu; the server's precache.py): every piece of the game's maps, and, as
// an option of its own, every map, read from the game now instead of the first time each is used. It shows what
// there is to do, a bar while the job runs, and Cancel at any moment; what is cached so far stays. Closing the window
// leaves a running job running: opening it again shows where it is.

const call = async (method, url, body) => {
  const response = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : {},
                                      body: body ? JSON.stringify(body) : undefined });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `The server answered ${response.status}`);
  return result;
};
const count = n => Number(n).toLocaleString('en-GB');
const plural = (n, word) => `${count(n)} ${word}${n === 1 ? '' : 's'}`;
export function duration(seconds) {
  if (seconds < 90) return seconds < 45 ? 'under a minute' : 'about a minute';
  if (seconds < 3600) return `about ${Math.round(seconds / 60)} minutes`;
  const hours = seconds / 3600;
  return hours < 1.25 ? 'about an hour' : `about ${hours < 10 ? hours.toFixed(1).replace('.0', '') : Math.round(hours)} hours`;
}
export function size(bytes) {
  if (bytes < 1e9) return `${Math.max(1, Math.round(bytes / 1e6))} MB`;
  return `${(bytes / 1e9).toFixed(bytes < 1e10 ? 1 : 0)} GB`;
}
const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/** What a line under an option says, from the plan (precache.py plan()). */
export function piecesLine(plan) {
  const p = plan.pieces, e = plan.estimates.pieces;
  if (p.error) return p.error;
  if (!p.ready) return 'The library has not been read yet: it is read first (about half a minute), then every piece of it.';
  const stale = p.stale ? ' The game\'s maps changed since the library was read: it is read again first.' : '';
  if (!p.missing) return `All ${count(p.total)} pieces of ${plural(p.maps, 'map')} are cached.${stale}`;
  return `${count(p.missing)} of ${count(p.total)} pieces to read (${count(p.kept)} cached): ${duration(e.seconds)}, about ${size(e.bytes)}.${stale}`;
}
export function mapsLine(plan) {
  const m = plan.maps, e = plan.estimates.maps, todo = m.missing + m.outdated;
  if (!m.available) return 'This server does not prepare maps.';
  if (!todo) return `All ${count(m.total)} maps are prepared.`;
  const old = m.outdated ? `, ${count(m.outdated)} of them prepared by an older version and done again` : '';
  return `${count(todo)} of ${count(m.total)} maps to prepare${old}: ${duration(e.seconds)}${e.bytes ? `, about ${size(e.bytes)}` : ''}. One map at a time.`;
}

/**
 * els: root, close, pieces and maps (the checkboxes), piecesNote, mapsNote, space, bar, barText, failures, status,
 * cancel, done, start. onMapsDone(): maps were prepared (the page's map list is out of date).
 */
export function createPrecache({ els, onMapsDone = () => {}, interval = 700 }) {
  let lastFocus = null, timer = null, plan = null, last = null, told = null;
  const running = () => last?.state === 'running';

  function paint() {
    const s = last ?? { state: 'idle' }, busy = s.state === 'running';
    if (plan) {
      els.piecesNote.textContent = piecesLine(plan);
      els.mapsNote.textContent = mapsLine(plan);
      els.pieces.disabled = busy || Boolean(plan.pieces.error);
      els.maps.disabled = busy || !plan.maps.available;
      if (els.pieces.disabled && !busy) els.pieces.checked = false;
      if (els.maps.disabled && !busy) els.maps.checked = false;
      const need = (els.pieces.checked ? plan.estimates.pieces.bytes : 0) + (els.maps.checked ? plan.estimates.maps.bytes : 0);
      const short = plan.free != null && need > plan.free;
      els.space.textContent = plan.free == null ? '' : short
        ? `That is about ${size(need)}, and the cache's drive has ${size(plan.free)} free: it may fill up.`
        : `The cache's drive has ${size(plan.free)} free.`;
      els.space.classList.toggle('short', short);
    }
    if (busy && s.options) { els.pieces.checked = s.options.pieces; els.maps.checked = s.options.maps; }
    els.bar.hidden = !busy;
    els.bar.classList.toggle('indeterminate', busy && s.fraction == null);
    els.bar.firstElementChild.style.width = `${Math.round((s.fraction ?? 0) * 1000) / 10}%`;
    els.barText.textContent = !busy ? '' : `${s.what ?? 'Working'}${s.total ? ` · ${count(s.done)} of ${count(s.total)}` : ''} · ${clock(s.seconds ?? 0)}`;
    const failures = [...(s.pieces?.failures ?? []), ...(s.maps?.failures ?? [])];
    const failed = (s.pieces?.failed ?? 0) + (s.maps?.failed ?? 0);
    els.failures.replaceChildren();
    els.failures.hidden = !failed;
    if (failed) {
      const head = document.createElement('li');
      head.className = 'head';
      head.textContent = `${plural(failed, 'item')} could not be read and ${failed === 1 ? 'was' : 'were'} skipped${failed > failures.length ? ` (the first ${failures.length})` : ''}:`;
      els.failures.append(head, ...failures.map(text => Object.assign(document.createElement('li'), { textContent: text })));
    }
    const made = [s.pieces ? `${plural(s.pieces.made, 'piece')} read` : null, s.maps ? `${plural(s.maps.made, 'map')} prepared` : null].filter(Boolean).join(', ');
    els.status.textContent = s.state === 'done' ? `Done in ${clock(s.seconds ?? 0)}${made ? `: ${made}` : ''}.`
      : s.state === 'cancelled' ? `Cancelled after ${clock(s.seconds ?? 0)}. What was cached stays.`
      : s.state === 'failed' ? `It stopped: ${s.error}`
      : busy ? 'You can keep working; closing this window leaves it running.' : '';
    els.cancel.hidden = !busy;
    els.cancel.disabled = false;
    els.start.hidden = busy;
    els.start.disabled = !plan || !(els.pieces.checked || els.maps.checked);
    els.start.textContent = s.state === 'cancelled' ? 'Carry on' : 'Start';
  }

  async function refresh(withPlan = false) {
    try {
      const s = await call('GET', `/precache.json${withPlan ? '?plan=1' : ''}`);
      const was = last?.state;
      if (s.plan) plan = s.plan;
      last = s;
      if (was === 'running' && s.state !== 'running') {
        // the job ended: the counts are other ones now, and prepared maps are in the server's list
        if (s.maps?.made && told !== s.startedAt) { told = s.startedAt; onMapsDone(); }
        return refresh(true);
      }
    } catch (error) {
      last = { state: 'failed', error: error.message };
    }
    paint();
    clearTimeout(timer);
    if (running() && !els.root.hidden) timer = setTimeout(() => refresh(), interval);
  }

  function hide() {
    els.root.hidden = true;
    clearTimeout(timer);
    lastFocus?.focus?.();
  }
  async function show() {
    lastFocus = document.activeElement;
    plan = null;
    els.piecesNote.textContent = els.mapsNote.textContent = 'Counting…';
    els.space.textContent = '';
    els.root.hidden = false;
    paint();
    els.done.focus();
    await refresh(true);
  }
  els.start.onclick = async () => {
    els.start.disabled = true;
    try {
      last = await call('POST', '/precache/start', { pieces: els.pieces.checked, maps: els.maps.checked });
    } catch (error) {
      last = { state: 'failed', error: error.message };
    }
    paint();
    clearTimeout(timer);
    if (running()) timer = setTimeout(() => refresh(), interval);
  };
  els.cancel.onclick = async () => {
    els.cancel.disabled = true;
    try { await call('POST', '/precache/cancel'); } catch { /* the next reading says how it stands */ }
    refresh();
  };
  els.pieces.onchange = els.maps.onchange = paint;
  els.done.onclick = els.close.onclick = hide;
  els.root.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { e.preventDefault(); hide(); } });
  return { show, hide, get open() { return !els.root.hidden; } };
}
