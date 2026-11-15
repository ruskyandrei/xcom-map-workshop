// This tab authorizes the first launch only while following the build it submitted.
const SESSION = 'workshop.prefabTest';
const ACTIVE = new Set(['preparing', 'building', 'launching', 'playing']);
const LABEL = {
  preparing: 'Preparing prefab test', building: 'Building prefab test', ready: 'Ready to launch',
  launching: 'Starting XCOM', playing: 'Prefab test in progress', finished: 'Prefab test finished',
  dry: 'Dry launch prepared', cancelled: 'Prefab test cancelled', failed: 'Prefab test failed',
};

async function call(path, body) {
  const response = await fetch(`/prefab-tests${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw Object.assign(new Error(result.error ?? response.statusText), result, { status: response.status });
  return result;
}

function keep(id) {
  try { if (id) sessionStorage.setItem(SESSION, id); else sessionStorage.removeItem(SESSION); } catch {}
}

export function createPrefabTest({ els, uuid, onPick = null }) {
  let state = null, error = null, pending = null, sending = false, authorize = false;
  let launchId = null, timer = null, focus = null, generation = 0;
  function render() {
    const phase = state?.phase ?? 'preparing', running = ACTIVE.has(phase);
    els.title.textContent = LABEL[phase];
    const tiles = state?.placement?.grid;
    els.note.textContent = state ? [state.label, state.unsaved ? 'unsaved snapshot' : null,
      tiles ? `${tiles[0]} × ${tiles[1]} stage` : null, state.quick ? 'lighting not baked' : 'baked lighting',
      state.saving ? 'saving on' : null].filter(Boolean).join(' · ') : '';
    const step = state?.build?.progress ?? state?.preparation?.progress;
    els.status.textContent = error ?? (state?.cancelRequested && running ? 'Cancelling…'
      : step?.what ?? state?.build?.running ?? ({
        preparing: 'Reading the snapshot and fitting the stage…', building: 'Building the blank stage…',
        ready: state?.leftOut ? 'Built without the pieces left out (listed below). Launch test plays it as it is.' : 'Launch the verified build from this snapshot.',
        launching: 'Installing this build and starting the game…',
        playing: state?.played?.saving
          ? `At XCOM's main menu, press ${state.played.saving.key} to start the test. Close XCOM when you’re done to restore the test install.`
          : 'Close XCOM when you’re done to restore the test install.',
        finished: 'The test install has been restored.',
        dry: 'The test package was installed in the scratch game folder.',
      })[phase] ?? '');
    els.bar.hidden = !['preparing', 'building', 'launching'].includes(phase);
    const fraction = step?.total ? Math.max(0, Math.min(1, step.done / step.total)) : 0;
    els.bar.firstElementChild.style.width = `${fraction * 100}%`;
    els.bar.classList.toggle('indeterminate', !step?.total);
    els.icon.classList.toggle('spin', running && phase !== 'playing');
    els.icon.classList.toggle('built', ['ready', 'finished', 'dry'].includes(phase));
    els.icon.classList.toggle('failed', phase === 'failed');
    // what the test says: the pieces left out first (it builds and plays without them), then the warnings. A row
    // with a piece's name selects and frames that piece in the builder.
    const issues = state?.issues ?? [], gone = issues.filter(i => i.leftOut).length;
    const row = issue => {
      const li = Object.assign(document.createElement('li'), { textContent: issue.actor && !issue.leftOut ? `${issue.actor} · ${issue.message}` : issue.message });
      li.classList.toggle('leftout', Boolean(issue.leftOut));
      if (issue.actor && onPick) { li.classList.add('pick'); li.title = `Select ${issue.actor}`; li.onclick = () => { if (onPick(issue.actor)) close(); }; }
      return li;
    };
    els.issues.replaceChildren(...issues.slice(0, 50).map(row));
    if (gone) els.issues.prepend(Object.assign(document.createElement('li'), { className: 'leftout head',
      textContent: `${gone} piece${gone === 1 ? ' is' : 's are'} left out of this test: it can't be built. The rest builds and plays.` }));
    if (issues.length > 50) els.issues.append(Object.assign(document.createElement('li'), { textContent: `And ${issues.length - 50} more issues.` }));
    if (state?.cleanup) els.issues.append(Object.assign(document.createElement('li'), { textContent: state.cleanup }));
    els.issues.hidden = !els.issues.childElementCount;
    const lines = state?.build?.lines ?? state?.preparation?.lines ?? [];
    els.details.hidden = !lines.length;
    els.log.textContent = lines.join('\n');
    els.cancel.hidden = !state || !(['preparing', 'building', 'ready'].includes(phase)
      || phase === 'launching' && !state.launchCommitted);
    els.cancel.disabled = sending || state?.cancelRequested;
    els.close.hidden = !error && (sending || ['preparing', 'building', 'launching'].includes(phase));
    els.launch.hidden = !(pending && error && !state || phase === 'ready' || phase === 'failed' && state.retryable);
    els.launch.disabled = sending;
    els.launch.textContent = pending && error && !state ? 'Retry request' : phase === 'failed' ? 'Retry launch' : 'Launch test';
  }
  function show() {
    if (els.root.hidden) focus = document.activeElement;
    els.root.hidden = false;
    render();
    els.root.focus();
  }
  function close() {
    els.root.hidden = true;
    authorize = false;
    focus?.focus();
    if (state && !ACTIVE.has(state.phase) && state.phase !== 'ready') {
      state = null;
      keep(null);
    }
  }
  function follow(delay = 350) {
    clearTimeout(timer);
    if (!state || !ACTIVE.has(state.phase)) return;
    const id = state.id, serial = generation;
    timer = setTimeout(async () => {
      try {
        const result = await call(`/${id}.json`);
        if (serial !== generation) return;
        if (!sending) { state = result; error = null; }
        // (a test with pieces left out waits for Launch test, so the list is read first)
        if (state.phase === 'ready' && authorize && !sending && !state.leftOut) await launch();
      } catch (e) {
        if (serial !== generation) return;
        if (!sending) error = e.message;
        if (e.status === 404) { keep(null); state = null; }
      }
      render();
      follow(error ? 1500 : 350);
    }, delay);
  }
  async function submit() {
    if (sending) return;
    sending = true;
    error = null;
    show();
    try {
      state = await call('', pending);
      keep(state.id);
      pending = null;
    } catch (e) {
      if (e.code === 'test-busy' && e.test) {
        authorize = false;
        try { state = await call(`/${e.test}.json`); keep(state.id); pending = null; }
        catch (failed) { error = failed.message; }
      } else {
        error = e.message;
        if (e.status) pending = null;
      }
    } finally {
      sending = false;
      render();
    }
    if (state?.phase === 'ready' && authorize && !state.leftOut) await launch();
    follow(0);
  }
  async function launch() {
    if (!state?.buildId || sending) return;
    authorize = false;
    sending = true;
    error = null;
    launchId ??= uuid();
    render();
    try {
      state = await call(`/${state.id}/play`, { buildId: state.buildId, attemptId: launchId });
      launchId = null;
    } catch (e) {
      error = e.message;
    } finally {
      sending = false;
      render();
      follow();
    }
  }
  els.cancel.onclick = async () => {
    authorize = false;
    sending = true;
    render();
    try { state = await call(`/${state.id}/cancel`, {}); error = null; }
    catch (e) { error = e.message; }
    finally { sending = false; render(); follow(0); }
  };
  els.close.onclick = close;
  els.launch.onclick = () => pending && !state ? submit() : launch();
  window.addEventListener('keydown', event => {
    if (els.root.hidden) return;
    event.stopImmediatePropagation();
    if (event.key === 'Escape' && !els.close.hidden) { event.preventDefault(); close(); }
    else if ((event.ctrlKey || event.metaKey) && !['c', 'r'].includes(event.key.toLowerCase())) event.preventDefault();
  }, true);
  return {
    showExisting() {
      if (!(sending || state && (ACTIVE.has(state.phase) || state.phase === 'ready' || state.retryable))) return false;
      show();
      return true;
    },
    // saving: the test's Enable saving (the Build panel's): the game opens at its main menu and a key there starts it
    start(snapshot, quick, unsaved, saving = false) {
      if (sending) return;
      generation++;
      state = null;
      launchId = null;
      authorize = true;
      pending = { snapshot: structuredClone(snapshot), quick, unsaved, ...(saving ? { saving: true } : {}), requestId: uuid() };
      submit();
    },
    async reconnect() {
      const serial = generation;
      let id;
      try { id = sessionStorage.getItem(SESSION); } catch {}
      if (!id) return;
      try {
        const result = await call(`/${id}.json`);
        if (serial !== generation) return;
        state = result;
        if (ACTIVE.has(state.phase) || state.phase === 'ready' || state.retryable) { show(); follow(); }
        else keep(null);
      } catch (e) { if (e.status === 404) keep(null); }
    },
  };
}
