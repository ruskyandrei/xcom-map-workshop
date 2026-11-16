// The build queue's page side (tools/viewer/buildqueue.py; private build queue plan, sections 4, 5 and 9.5): what the
// project manager and the editor's chip show of the queue, worked out without the page (the node tests read it), and
// the one controller that asks the server for the queue for both of them.

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
export const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
export const ordinal = n => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`;
const sentence = s => s.charAt(0).toUpperCase() + s.slice(1);
export const ACTIVE = ['waiting', 'starting', 'building'];

// The manager's Show choice "Needs a full build": a readable project not built, built quick (its lighting not
// baked), built from an older revision, or built by another or an unknown editor version. A full build that kept the
// lighting as it was (lightingUnchanged) is a full build. It goes by revisions and versions, not by every change of
// the code or the map a build would bring.
export function needsFullBuild(p, editorVersion) {
  if (!p || p.error) return false;
  const b = p.build;
  return !b || Boolean(b.quick) || Boolean(b.stale) || !b.editorVersion || b.editorVersion !== editorVersion;
}

// The ids Build sends: the ticked projects in the list's sort order, those the filter hides included (`sorted` is
// every project, sorted), unreadable ones never.
export function requestOrder(sorted, picked) {
  return sorted.filter(p => picked.has(p.id) && !p.error).map(p => p.id);
}

// The step a row's build is at, in words: what a tool is counting, or the stage.
export function stepWords(job) {
  if (!job) return '';
  const p = job.progress;
  if (p) return sentence(p.total ? `${p.what}: ${p.done} of ${p.total}` : `${p.what}…`);
  if (job.running) return `${sentence(job.running)}…`;
  return job.stage ? `${sentence(STAGE_WORDS[job.stage] ?? job.stage)} done` : 'Starting…';
}
const STAGE_WORDS = { snapshot: 'reading the project', compile: 'compiling the edit', patch: 'the patch', shell: 'the map grid',
                      transplant: 'bringing the pieces from other maps', light: 'the edit and its lighting', seeds: 'seeding' };

// A row's line in the manager's Last build column: { kind, text, title, progress (0..1, the stage's own) }, or null
// when the queue has no row for the project.
export function rowLine(item, q) {
  if (!item) return null;
  const stopped = q?.state === 'stopped' || q?.state === 'stopping';
  if (item.state === 'waiting') {
    if (stopped) return { kind: 'stopped', text: 'Stopped: starts again on Resume', title: item.interrupted ?? 'The queue is stopped' };
    return { kind: 'waiting', text: `Waiting (${ordinal(item.position ?? 1)})`, title: item.interrupted ?? 'Built when its turn comes, as it is saved then' };
  }
  if (item.state === 'starting') return { kind: 'building', text: 'Starting…', title: 'Its saved project is being read' };
  if (item.state === 'building') {
    const job = item.job, p = job?.progress;
    return { kind: 'building', text: `Building: ${stepWords(job).replace(/^./, c => c.toLowerCase())}`,
             title: `A full build of revision ${item.revision ?? '?'}, as it was saved when its turn came`,
             progress: p?.total ? Math.min(1, p.done / p.total) : null };
  }
  if (item.state === 'built') return { kind: 'built', text: 'Built', title: item.result?.buildId ? `${item.result.buildId}, revision ${item.result.revision}` : 'Built' };
  return { kind: 'failed', text: `Failed: ${item.error ?? 'see its build'}`, title: item.error ?? '' };
}

// The time the queue may still take (9.5): { current: { name, elapsed, estimate, left, longer } | null, known (seconds
// of the rows whose last full build is known), unknown (how many rows have none), waiting (it waits for another's
// build or a reader: when that ends is not known) }.
export function timing(q) {
  const out = { current: null, known: 0, unknown: 0, waiting: Boolean(q?.waitingFor) };
  for (const item of q?.items ?? []) {
    if (!ACTIVE.includes(item.state)) continue;
    const estimate = typeof item.estimate === 'number' && Number.isFinite(item.estimate) && item.estimate > 0 ? item.estimate : null;
    if (item.state === 'waiting') {
      if (estimate === null) out.unknown++; else out.known += estimate;
      continue;
    }
    const elapsed = item.elapsed ?? 0;
    const left = estimate === null ? null : Math.max(0, estimate - elapsed);
    out.current = { name: item.name, elapsed, estimate, left, longer: estimate !== null && elapsed > estimate };
    if (left === null) out.unknown++; else out.known += left;
  }
  return out;
}

export function timingWords(q) {
  const t = timing(q);
  const parts = [];
  if (t.current?.longer) parts.push(`${t.current.name ?? 'This project'} is taking longer than its last build (${clock(t.current.estimate)}).`);
  if (t.waiting) parts.push('When the build it waits for ends is not known.');
  if (!t.unknown && t.known) parts.push(`About ${clock(t.known)} left, going by each project's last full build (approximate).`);
  else if (t.unknown && t.known) parts.push(`About ${clock(t.known)} for the projects built before, and ${plural(t.unknown, 'project')} without a full build to go by.`);
  else if (t.unknown) parts.push(`No time to go by: ${t.unknown === 1 ? 'the project has' : `${plural(t.unknown, 'project')} have`} no full build before.`);
  return parts.join(' ');
}

const current = q => q?.items?.find(i => i.state === 'starting' || i.state === 'building');

// The strip above the manager's footer: { title, step, progress (0..1 processed of all), note, failures: [text] }.
export function stripWords(q) {
  if (!q || q.state === 'unavailable') return null;
  if (q.state === 'unreadable') return { title: 'The build queue can\'t be read', step: '', progress: 0, note: q.error ?? '', failures: [] };
  if (q.state === 'idle' || !q.items?.length) return null;
  const c = q.counts ?? {}, total = c.total ?? q.items.length, processed = c.processed ?? 0, now = current(q);
  const failures = q.items.filter(i => i.state === 'failed').map(i => `${i.name ?? i.project}: ${i.error ?? 'see its build'}`);
  const out = { title: '', step: '', progress: total ? processed / total : 0, note: '', failures };
  if (q.state === 'running') {
    const next = q.items.find(i => i.state === 'waiting');
    const w = q.waitingFor;
    if (now) {
      out.title = `Building ${processed + 1} of ${total}: ${now.name ?? now.project}`;
      out.step = now.state === 'starting' ? 'Reading the saved project…' : stepWords(now.job);
      out.stage = now.job?.progress?.total ? now.job.progress.done / now.job.progress.total : null;
    } else if (w?.kind === 'build') out.title = `Waiting for ${w.name ?? 'another build'} to end; then ${next?.name ?? 'the next project'} (${processed + 1} of ${total})`;
    else if (w?.kind === 'reader') out.title = `Waiting while ${w.name ?? 'the next project'}'s last build is being installed or zipped (${processed + 1} of ${total})`;
    else if (w?.kind === 'recovering') out.title = 'Making sure the builds from before the restart have ended…';
    else out.title = `Starting ${next?.name ?? 'the next project'} (${processed + 1} of ${total})`;
    out.note = timingWords(q);
  } else if (q.state === 'stopping') {
    out.title = `Stopping: ${now?.name ?? 'the build'} is being stopped`;
    out.note = 'Its last package, if it has one, stays as it was.';
  } else if (q.state === 'stopped') {
    out.title = q.recovering ? 'Queue stopped: making sure the builds from before the restart have ended…'
      : `Queue stopped: ${processed} of ${total} done, ${plural(c.waiting ?? 0, 'project')} waiting`;
    out.note = q.contextChanged ? 'The settings changed since the queue started (the game install or a folder): clear it, then queue the projects again.'
      : q.reason ?? 'Resume builds the waiting projects from the first, each as it is saved then.';
  } else if (q.state === 'finished') {
    out.title = `${plural(c.built ?? 0, 'project')} built${c.failed ? `, ${c.failed} failed` : ''}`;
    out.note = c.failed ? 'Each failure says why below; build them again once mended.' : 'Every project in the queue is built.';
  }
  if (q.fault) out.note = `${q.fault} ${out.note}`.trim();
  if (q.notice) out.note = `${out.note} ${q.notice}`.trim();
  return out;
}

// The editor's chip in the top bar, or null when there is nothing to say.
export function chipWords(q) {
  if (!q || q.state === 'idle' || q.state === 'unavailable') return null;
  if (q.state === 'unreadable') return { text: 'Build queue: can\'t be read', warn: true };
  const c = q.counts ?? {}, total = c.total ?? 0, processed = c.processed ?? 0;
  if (!total) return null;
  if (q.state === 'running') return { text: `Building ${Math.min(processed + 1, total)} of ${total}`, warn: Boolean(q.fault) };
  if (q.state === 'stopping') return { text: 'Stopping the queue', warn: false };
  if (q.state === 'stopped') return { text: 'Queue stopped', warn: true };
  return { text: `${c.built ?? 0} built${c.failed ? `, ${c.failed} failed` : ''}`, warn: Boolean(c.failed) };
}

export const CADENCE = { open: 2000, active: 5000, idle: 15000, max: 60000 };
const isActive = q => q?.state === 'running' || q?.state === 'stopping';

// The one controller of the page (9.5): asks the server for the queue, about every 2 s while the manager is open and
// the queue runs, 5 s while it runs with the manager closed, 15 s otherwise (another tab may start one), at once on
// refresh() (focus, the manager opening); one request at a time, an answer older than the newest dropped, slower while
// the server doesn't answer (the last status kept, never a made-up end), and nothing more once the server says it has
// no queue (404). Changes go through send() with the envelope of the queue last seen; an answer carrying the queue
// (a 409's too) is taken as the newest.
// get(): the queue; post(action, body): the answer, or throws an Error with .status and .body; onChange(queue, info):
// info = { ended: [rows that have ended since the last answer], offline, disabled }.
export function createQueueController({ get, post, onChange, uuid = () => crypto.randomUUID(),
                                        timers = { set: (fn, ms) => setTimeout(fn, ms), clear: id => clearTimeout(id) } }) {
  let state = null, open = false, timer = null, inflight = false, ask = 0, failures = 0, disabled = false, again = false;
  const receivedAt = { at: 0 };
  function delay() {
    if (disabled) return null;
    const base = isActive(state) ? (open ? CADENCE.open : CADENCE.active) : CADENCE.idle;
    return failures ? Math.min(CADENCE.max, base * 2 ** failures) : base;
  }
  function schedule() {
    timers.clear(timer);
    const d = delay();
    timer = d === null ? null : timers.set(poll, d);
  }
  function accept(value, force = false) {
    if (!value || typeof value !== 'object') return;
    if (!force && state && value.queueId && value.queueId === state.queueId && typeof value.revision === 'number'
        && value.revision < state.revision) return;            // older than what was seen
    const before = new Map((state?.items ?? []).map(i => [i.itemId, i.state]));
    const ended = (value.items ?? []).filter(i => ACTIVE.includes(before.get(i.itemId)) && !ACTIVE.includes(i.state));
    state = value;
    receivedAt.at = Date.now();
    onChange?.(state, { ended, offline: false, disabled });
  }
  async function poll() {
    if (disabled) return;
    if (inflight) { again = true; return; }
    inflight = true;
    const mine = ++ask;
    try {
      const value = await get();
      if (mine === ask) { failures = 0; accept(value); }
    } catch (e) {
      if (mine === ask) {
        if (e?.status === 404) disabled = true;
        else failures = Math.min(failures + 1, 5);
        onChange?.(state, { ended: [], offline: !disabled, disabled });
      }
    } finally {
      inflight = false;
      if (again && !disabled) { again = false; poll(); } else schedule();
    }
  }
  async function send(action, fields = {}) {
    const body = { queueId: state?.queueId ?? null, expectedRevision: state?.revision ?? 0, requestId: uuid(), ...fields };
    ask++;                  // a poll already on its way is older than this answer
    try {
      const answer = await post(action, body);
      accept(answer?.queue, true);
      schedule();
      return answer;
    } catch (e) {
      if (e?.body?.queue) accept(e.body.queue, true);
      throw e;
    }
  }
  return {
    start: () => poll(),
    refresh: () => poll(),
    send,
    setOpen(value) { const was = open; open = Boolean(value); if (open && !was) poll(); else schedule(); },
    // the time the queue has been active, counted on between answers while it runs
    activeSeconds: () => !state ? 0 : (state.activeSeconds ?? 0) + (state.state === 'running' ? (Date.now() - receivedAt.at) / 1000 : 0),
    get state() { return state; },
    get disabled() { return disabled; },
    stop() { timers.clear(timer); disabled = true; },
  };
}
