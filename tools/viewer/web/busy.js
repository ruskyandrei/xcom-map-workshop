// The busy mark for slow steps and the page giving way (refactor stage P9): the turning ring with what is being done,
// put up once a step has run for about a third of a second or at once (busyStart, busyPaint, busy), the view's clicks
// and keys held while a mark put up at once is shown (busyHeld, with its listeners on the window), a long loop on the
// page's thread giving way to draw (nextFrame, breather), and many pieces built a few at a time (buildRoots).
//
// createBusy takes `$` and the scene's pieces' buildRoot when app.js makes it, where this code always was: its
// listeners on the window are set then. Its own state is inside it (the steps under way, busyJobs).

export function createBusy({ $, buildRoot }) {
  // The busy mark for slow steps (map buildings plan, 4a): the build window's turning ring with what is being done, put
  // up once a step has run for about a third of a second, so quick steps never show it. busyStart(message) returns the
  // function that ends it. A long step on the page's own thread, which no timer interrupts (a paste of many pieces),
  // asks for it `now`: the mark is drawn first and a frame let through (nextFrame) before the work runs.
  const BUSY_AFTER = 330, BUSY_PIECES = 60, WORK_SLICE = 12, BUILD_CHUNK = 16;
  const busyJobs = [];
  function busyStart(message, now = false, hold = false) {
    const job = { message, shown: now, hold, done: 0, total: null };
    busyJobs.push(job);
    const timer = now ? null : setTimeout(() => { job.shown = true; busyPaint(); }, BUSY_AFTER);
    busyPaint();
    const end = () => { clearTimeout(timer); const at = busyJobs.indexOf(job); if (at >= 0) busyJobs.splice(at, 1); busyPaint(); };
    end.job = job;
    return end;
  }
  function busyPaint() {
    const job = busyJobs.filter(j => j.shown).at(-1);
    $('busyMark').hidden = !job;
    if (!job) return;
    const counted = job.total > 0;
    $('busyText').textContent = counted ? `${job.message} ${Math.min(job.done, job.total)} of ${job.total}` : job.message;
    $('busyBar').hidden = !counted;
    if (counted) $('busyBar').firstElementChild.style.width = `${Math.round(100 * Math.min(1, job.done / job.total))}%`;
  }
  // After the next frame is drawn (or a moment, where the page is in the background and draws none).
  const nextFrame = () => new Promise(resolve => { requestAnimationFrame(() => setTimeout(resolve, 0)); setTimeout(resolve, 80); });
  // One way to be busy (plan "sturdier prefabs, faster editor", L1): busy(message, work, { total, now }) puts the mark
  // up (after a third of a second, or at once and with a frame let through when the caller knows the step is large),
  // runs work(step) and takes the mark down whatever happens. step(done, total, message) moves the bar and the count
  // ("212 of 458"); without a total the ring alone shows. While a mark put up at once is shown, clicks and keys meant
  // for the view are ignored (busyHeld), so a second Ctrl+V does not queue behind the first; a mark that comes up late
  // (a read that may be quick) holds nothing unless asked to.
  async function busy(message, work, { total = null, now = false, hold = now } = {}) {
    const end = busyStart(message, now, hold), job = end.job;
    job.total = total;
    const step = (done, of = job.total, text = null) => { job.done = done; job.total = of; if (text) job.message = text; busyPaint(); };
    try {
      if (now) await nextFrame();
      return await work(step);
    } finally { end(); }
  }
  const busyHeld = () => busyJobs.some(j => j.hold && j.shown);
  for (const type of ['keydown', 'pointerdown', 'wheel'])
    window.addEventListener(type, e => {
      if (!busyHeld()) return;
      const view = type === 'keydown' ? !e.target.closest?.('input, textarea, select, [contenteditable], dialog') : e.target.tagName === 'CANVAS';
      if (view) { e.stopImmediatePropagation(); e.preventDefault(); }
    }, { capture: true, passive: false });
  // A long loop on the page's own thread gives way once it has held it for WORK_SLICE ms: `const rest = breather()`
  // before the loop, `await rest()` in it. The ring keeps turning and the bar moves; a short loop never waits.
  function breather(slice = WORK_SLICE) {
    let since = performance.now();
    return async () => { if (performance.now() - since < slice) return; await nextFrame(); since = performance.now(); };
  }
  // Many pieces made (buildRoot each), a few at a time, giving way by time and counting for the busy mark. With `failed`
  // (a list), a piece that can't be drawn (its mesh, a material or a texture not had) is left out of what is given back
  // and named there, { obj, error }, as the map's own load leaves one out (review finding 29); without, it throws.
  async function buildRoots(objs, step = null, failed = null) {
    const built = [], rest = breather();
    for (let k = 0; k < objs.length; k += BUILD_CHUNK) {
      const chunk = objs.slice(k, k + BUILD_CHUNK);
      const made = await Promise.all(chunk.map(obj => (failed ? buildRoot(obj).catch(error => { failed.push({ obj, error }); return null; }) : buildRoot(obj))));
      built.push(...made.filter(Boolean));
      step?.(k + chunk.length, objs.length);
      await rest();
    }
    return built;
  }

  return { BUSY_PIECES, buildRoots, busy, busyPaint, busyStart, nextFrame };
}
