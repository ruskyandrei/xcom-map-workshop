// The Cache everything window (the Settings menu; the server's precache.py): every piece of the game's maps, and, as
// an option of its own, every map, read from the game now instead of the first time each is used; and every picture
// the look picker and the Add panel show, drawn now (precache_pictures.js: in this page, after the pieces are read
// when both are asked for). It shows what there is to do, a bar while the job runs (a second one while the pictures
// are drawn), and Cancel at any moment; what is cached so far stays. Closing the window leaves a running job running:
// opening it again shows where it is.
import { call as callServer } from './api.js';
import { clock } from './build_queue.js';

const call = (method, url, body) => callServer(method, url, body, { fallback: r => `The server answered ${r.status}` });
const count = n => Number(n).toLocaleString('en-GB');
// a count with its noun, as dom_words.js' plural, its digits grouped in British English (12,345 pieces)
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

/** What a line under an option says, from the plan (precache.py plan()). */
function piecesLine(plan) {
  const p = plan.pieces, e = plan.estimates.pieces;
  if (p.error) return p.error;
  if (!p.ready) return 'The library has not been read yet: it is read first (about half a minute), then every piece of it.';
  const stale = p.stale ? ' The game\'s maps changed since the library was read: it is read again first.' : '';
  if (!p.missing) return `All ${count(p.total)} pieces of ${plural(p.maps, 'map')} are cached.${stale}`;
  return `${count(p.missing)} of ${count(p.total)} pieces to read (${count(p.kept)} cached): ${duration(e.seconds)}, about ${size(e.bytes)}.${stale}`;
}
function picturesLine(p) {
  if (!p) return 'Counting…';
  if (p.error) return p.error;
  const todo = p.looks.missing + p.pieces.missing, total = p.looks.total + p.pieces.total;
  const unread = p.pieces.ready ? '' : ' The pieces\' pictures are counted once the pieces are read.';
  const problems = p.errors.length ? ` ${p.errors.join('. ')}.` : '';
  if (!todo) return `All ${count(total)} pictures are drawn.${unread}${problems}`;
  return `${count(todo)} of ${count(total)} pictures to draw (${count(p.looks.missing)} of the looks, ${count(p.pieces.missing)} of the pieces and effects): `
    + `${duration(p.estimate.seconds)}, about ${size(p.estimate.bytes)}. They are drawn in this page, so it has to stay open.${unread}${problems}`;
}
function mapsLine(plan) {
  const m = plan.maps, e = plan.estimates.maps, todo = m.missing + m.outdated;
  if (!m.available) return 'This server does not prepare maps.';
  if (!todo) return `All ${count(m.total)} maps are prepared.`;
  const old = m.outdated ? `, ${count(m.outdated)} of them prepared by an older version and done again` : '';
  return `${count(todo)} of ${count(m.total)} maps to prepare${old}: ${duration(e.seconds)}${e.bytes ? `, about ${size(e.bytes)}` : ''}. One map at a time.`;
}

// What the end of a run says: the server's job's, and the pictures'.
function serverWords(s) {
  const made = [s.pieces ? `${plural(s.pieces.made, 'piece')} read` : null, s.maps ? `${plural(s.maps.made, 'map')} prepared` : null].filter(Boolean).join(', ');
  return s.state === 'done' ? `Done in ${clock(s.seconds ?? 0)}${made ? `: ${made}` : ''}.`
    : s.state === 'cancelled' ? `Cancelled after ${clock(s.seconds ?? 0)}. What was cached stays.`
    : s.state === 'failed' ? `It stopped: ${s.error}` : '';
}
function pictureWords(d) {
  const skipped = d.skipped ? ` (${plural(d.skipped, 'effect picture')} left as the marker: nothing of the effect to draw)` : '';
  return d.state === 'done' ? `${plural(d.drawn, 'picture')} drawn in ${clock(d.seconds ?? 0)}${skipped}.`
    : d.state === 'cancelled' ? `Drawing the pictures was cancelled after ${clock(d.seconds ?? 0)}; the ${count(d.drawn)} drawn stay.`
    : d.state === 'failed' ? `Drawing the pictures stopped: ${d.error}` : '';
}

/**
 * els: root, close, pieces, maps and pictures (the checkboxes), piecesNote, mapsNote, picturesNote, space, bar, barText,
 * drawBar, drawText (the pictures'), failures, status, cancel, done, start. pictures(): the pictures' job
 * (precache_pictures.js createPicturePrecache; made after this, so asked for when used). onMapsDone(): maps were
 * prepared (the page's map list is out of date).
 */
export function createPrecache({ els, pictures = () => null, onMapsDone = () => {}, interval = 700 }) {
  let lastFocus = null, timer = null, plan = null, drawPlan = null, last = null, told = null;
  // the pictures asked for with the pieces, drawn once the server has read them
  let picturesAfter = false;
  const running = () => last?.state === 'running';
  const drawing = () => Boolean(pictures()?.running);

  function paint() {
    const s = last ?? { state: 'idle' }, d = pictures()?.state() ?? { state: 'idle' };
    const draws = d.state === 'running', busy = s.state === 'running' || draws || picturesAfter;
    if (plan) {
      els.piecesNote.textContent = piecesLine(plan);
      els.mapsNote.textContent = mapsLine(plan);
      els.pieces.disabled = busy || Boolean(plan.pieces.error);
      els.maps.disabled = busy || !plan.maps.available;
      if (els.pieces.disabled && !busy) els.pieces.checked = false;
      if (els.maps.disabled && !busy) els.maps.checked = false;
    }
    els.picturesNote.textContent = picturesLine(drawPlan);
    els.pictures.disabled = busy || !pictures() || Boolean(drawPlan?.error);
    if (els.pictures.disabled && !busy) els.pictures.checked = false;
    if (plan) {
      const need = (els.pieces.checked ? plan.estimates.pieces.bytes : 0) + (els.maps.checked ? plan.estimates.maps.bytes : 0)
        + (els.pictures.checked && drawPlan?.estimate ? drawPlan.estimate.bytes : 0);
      const short = plan.free != null && need > plan.free;
      els.space.textContent = plan.free == null ? '' : short
        ? `That is about ${size(need)}, and the cache's drive has ${size(plan.free)} free: it may fill up.`
        : `The cache's drive has ${size(plan.free)} free.`;
      els.space.classList.toggle('short', short);
    }
    const serving = s.state === 'running';
    if (serving && s.options) { els.pieces.checked = s.options.pieces; els.maps.checked = s.options.maps; }
    if (busy) els.pictures.checked = draws || picturesAfter;
    els.bar.hidden = !serving;
    els.bar.classList.toggle('indeterminate', serving && s.fraction == null);
    els.bar.firstElementChild.style.width = `${Math.round((s.fraction ?? 0) * 1000) / 10}%`;
    els.barText.textContent = !serving ? '' : `${s.what ?? 'Working'}${s.total ? ` · ${count(s.done)} of ${count(s.total)}` : ''} · ${clock(s.seconds ?? 0)}`;
    els.drawBar.hidden = !draws;
    els.drawBar.classList.toggle('indeterminate', draws && d.fraction == null);
    els.drawBar.firstElementChild.style.width = `${Math.round((d.fraction ?? 0) * 1000) / 10}%`;
    els.drawText.textContent = draws ? `${d.what}${d.total ? ` · ${count(d.done)} of ${plural(d.total, 'picture')}` : ''} · ${clock(d.seconds ?? 0)}`
      : picturesAfter ? 'The pictures are drawn once the pieces are read.' : '';
    const failures = [...(s.pieces?.failures ?? []), ...(s.maps?.failures ?? []), ...(d.failures ?? [])];
    const failed = (s.pieces?.failed ?? 0) + (s.maps?.failed ?? 0) + (d.failed ?? 0);
    els.failures.replaceChildren();
    els.failures.hidden = !failed;
    if (failed) {
      const head = document.createElement('li');
      head.className = 'head';
      head.textContent = `${plural(failed, 'item')} could not be read and ${failed === 1 ? 'was' : 'were'} skipped${failed > failures.length ? ` (the first ${failures.length})` : ''}:`;
      els.failures.append(head, ...failures.map(text => Object.assign(document.createElement('li'), { textContent: text })));
    }
    els.status.textContent = busy
      ? `You can keep working; closing this window leaves it running.${draws || picturesAfter ? ' The pictures are drawn in this page: leave it open.' : ''}`
      : [serverWords(s), pictureWords(d)].filter(Boolean).join(' ');
    els.cancel.hidden = !busy;
    els.cancel.disabled = false;
    els.start.hidden = busy;
    els.start.disabled = !plan || !(els.pieces.checked || els.maps.checked || els.pictures.checked);
    els.start.textContent = s.state === 'cancelled' || d.state === 'cancelled' ? 'Carry on' : 'Start';
  }

  // the pictures counted again (the window opened, a job ended)
  async function countPictures() {
    if (!pictures()) return;
    try { drawPlan = await pictures().plan(); }
    catch (error) { drawPlan = { error: `The pictures could not be counted: ${error.message}` }; }
    paint();
  }
  function startPictures() {
    picturesAfter = false;
    pictures()?.start();
  }
  /** The pictures' job changed (precache_pictures.js onChange): drawn again, and counted again once it ends. */
  function picturesChanged() {
    if (els.root.hidden) return;
    if (!drawing() && pictures()?.state().state !== 'idle' && drawPlan && !drawPlan.counting) {
      drawPlan.counting = true;
      countPictures();
    }
    paint();
  }
  function poll() {
    clearTimeout(timer);
    if ((running() && !els.root.hidden) || picturesAfter) timer = setTimeout(() => refresh(), interval);
  }

  async function refresh(withPlan = false) {
    try {
      const s = await call('GET', `/precache.json${withPlan ? '?plan=1' : ''}`);
      const was = last?.state;
      if (s.plan) plan = s.plan;
      last = s;
      // the pieces read (the job ended, or went on to the maps): the pictures asked for with them are drawn now; not
      // if it failed or was cancelled
      if (picturesAfter && (s.state !== 'running' || s.phase === 'maps')) {
        if (s.state === 'running' || s.state === 'done') startPictures(); else picturesAfter = false;
      }
      if (was === 'running' && s.state !== 'running') {
        // the job ended: the counts are other ones now, and prepared maps are in the server's list
        if (s.maps?.made && told !== s.startedAt) { told = s.startedAt; onMapsDone(); }
        if (!els.root.hidden && !drawing()) countPictures();
        return refresh(true);
      }
    } catch (error) {
      last = { state: 'failed', error: error.message };
      picturesAfter = false;
    }
    paint();
    poll();
  }

  function hide() {
    els.root.hidden = true;
    poll();         // (stopped, unless pictures wait for the pieces: their start is still watched for)
    lastFocus?.focus?.();
  }
  async function show() {
    lastFocus = document.activeElement;
    plan = null; drawPlan = null;
    els.piecesNote.textContent = els.mapsNote.textContent = 'Counting…';
    els.space.textContent = '';
    els.root.hidden = false;
    paint();
    els.done.focus();
    await Promise.all([refresh(true), countPictures()]);
  }
  els.start.onclick = async () => {
    els.start.disabled = true;
    const server = els.pieces.checked || els.maps.checked, draw = els.pictures.checked && Boolean(pictures());
    if (server) {
      try {
        last = await call('POST', '/precache/start', { pieces: els.pieces.checked, maps: els.maps.checked });
      } catch (error) {
        last = { state: 'failed', error: error.message };
      }
    }
    // (with the pieces, the pictures wait for them: a piece's picture is drawn from it)
    if (draw && !(server && last?.state === 'failed')) {
      if (server && last?.state === 'running' && last.options?.pieces && last.phase !== 'maps') picturesAfter = true;
      else startPictures();
    }
    paint();
    poll();
  };
  els.cancel.onclick = async () => {
    els.cancel.disabled = true;
    picturesAfter = false;
    pictures()?.cancel();
    if (running()) {
      try { await call('POST', '/precache/cancel'); } catch { /* the next reading says how it stands */ }
    }
    refresh();
  };
  els.pieces.onchange = els.maps.onchange = els.pictures.onchange = paint;
  els.done.onclick = els.close.onclick = hide;
  els.root.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { e.preventDefault(); hide(); } });
  return { show, hide, picturesChanged, get open() { return !els.root.hidden; } };
}
