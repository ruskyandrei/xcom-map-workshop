// Prepare (refactor stage P8): an export older than what lights and builds need (families.json's exportProblem)
// exported again (POST /maps/<id>/export with prepare), then the page reopened. Here the dialog in the middle of the
// window that asks, when the map opens, before a build or a play of a project, and from a build that failed for want
// of it, with Later's banner and the run with its progress (showPrepare); and a build or a play waiting for it
// (needsPrepare).
//
// createPrepare takes what it needs of app.js as one argument object, when app.js makes it: the banner, the map's
// label and the popups. Its own state is inside it (whether a prepare is under way); the export's problem
// (exportProblem: app.js's scene start sets it) is editor_state.js's.
import { call } from './api.js';
import { activeMapId, data, exportProblem, setExportProblem } from './editor_state.js';
import { recallSession, rememberSession } from './storage.js';

export function createPrepare({ $, banner, mapLabel, projectsAvailable, showPop }) {
  // Prepare: an export older than what lights and builds need (families.json's exportProblem) exported again (POST
  // /maps/<id>/export with prepare), then the page reopened. A dialog in the middle of the window asks: when the map
  // opens, before a build or a play of a project, and from a build that failed for want of it (its Prepare the map
  // button, which starts it at once). Later leaves a banner with the same offer. 'update': the map's export is older
  // than this editor's exporter, so it is prepared again at once when it opens (an update's drawing fixes, export 19).
  let preparing = false;     // (exportProblem: editor_state.js)
  const prepareWhy = {
    open: 'is older than what editing lights and building need',
    build: 'is older than a build needs, so the project can\'t be built yet',
    failed: 'is older than the build needs, which is why it stopped',
  };
  function showPrepare(why = 'open', start = false) {
    const els = { root: $('prepareModal'), title: $('prepareTitle'), note: $('prepareNote'), bar: $('prepareBar'), status: $('prepareStatus'),
                  ok: $('prepareOk'), later: $('prepareLater'), close: $('prepareClose') };
    const label = mapLabel(activeMapId);
    const hide = () => { els.root.hidden = true; };
    const update = why === 'update';
    const later = () => {
      if (preparing) return;
      hide();
      if (update) banner(`Map schema updated: ${label} wasn't re-exported, so some pieces may draw wrong.`,
                         [['Re-export', () => showPrepare('update')]]);
      else banner(`${label}'s copy in the editor is older than what editing lights and building need. Prepare it again (about half a minute; projects and edits are kept).`,
                  [['Prepare now', () => showPrepare('open')]]);
    };
    const progress = fraction => {
      els.bar.hidden = false;
      els.bar.className = `buildbar${fraction == null ? ' indeterminate' : ''}`;
      els.bar.firstElementChild.style.width = `${(100 * (fraction ?? 0.3)).toFixed(1)}%`;
    };
    async function run() {
      if (preparing) return;
      preparing = true;
      els.ok.disabled = true; els.ok.textContent = update ? 'Re-exporting…' : 'Preparing…'; els.later.hidden = els.close.hidden = true;
      const reading = update ? 'Re-exporting' : 'Reading the map from the game again';
      els.status.textContent = `${reading}: about half a minute…`;
      progress(null);
      const at = `/maps/${encodeURIComponent(activeMapId)}/export`;
      try {
        await call('POST', at, { prepare: true }, { fallback: r => `the server said ${r.status}` });
        for (;;) {
          await new Promise(done => setTimeout(done, 1500));
          const s = await call('GET', `${at}.json`);
          if (s.state === 'failed') throw Error(s.error || 'the export failed');
          if (s.state === 'ready') { els.status.textContent = update ? 'Re-exported: opening it…' : 'Prepared: opening it again…'; progress(1); location.reload(); return; }
          if (s.progress) { progress(s.progress.fraction); els.status.textContent = `${reading}: ${Math.round(s.progress.fraction * 100)}%…`; }
        }
      } catch (e) {
        preparing = false;
        els.bar.hidden = true;
        els.status.textContent = `${label} could not be ${update ? 're-exported' : 'prepared'}: ${e.message}`;
        els.ok.disabled = false; els.ok.textContent = 'Try again'; els.later.hidden = els.close.hidden = false;
      }
    }
    els.title.textContent = update ? label : `${label} needs preparing again`;
    els.note.textContent = update
      ? 'Map schema updated. Re-exporting.'
      : `The editor's copy of ${label} ${prepareWhy[why] ?? prepareWhy.open}. Preparing reads the map from the game again, which takes about half a minute, and opens it afresh. Your projects are kept, and so are edits not saved yet.`;
    els.ok.textContent = update ? 'Re-export' : 'Prepare now'; els.ok.disabled = false;
    els.later.hidden = els.close.hidden = false;
    els.bar.hidden = true; els.status.textContent = '';
    els.ok.onclick = run; els.later.onclick = els.close.onclick = later;
    els.root.onkeydown = e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); later(); } };
    els.root.hidden = false;
    showPop(null);
    if (start) run(); else setTimeout(() => els.ok.focus(), 0);
  }
  // The map's export checked as it opens (app.js's startScene, given the families' answer and the server's map list).
  function prepareOpened(familyTable, mapCatalogue) {
    // An export older than what lights and Builds need (export 18 and its glowing pieces): prepare it again.
    // An export older than the server's exporter (the catalogue's outdated: an update since the map was prepared) is
    // prepared again at once, so the update's fixes reach it (its dialog says so; a failure leaves the offer in a banner).
    setExportProblem(projectsAvailable() ? familyTable?.exportProblem ?? null : null);
    const outdated = Boolean(mapCatalogue?.maps?.find(m => m.id === activeMapId)?.outdated) && data.scope === 'map' && !data.preview;
    // once a session per map: should it come back still outdated, the dialog waits for a click rather than looping
    const tried = `workshop.updated.${activeMapId}`;
    const again = recallSession(tried) === '1';     // (no session storage: start)
    rememberSession(tried, outdated ? '1' : '0');
    if (outdated) showPrepare('update', !again);
    else if (exportProblem) showPrepare('open');
  }
  // A build or a play of a project waits for the map to be prepared: true when the dialog was shown instead.
  function needsPrepare() {
    if (!exportProblem) return false;
    showPrepare('build');
    return true;
  }

  return { needsPrepare, prepareOpened, showPrepare };
}
