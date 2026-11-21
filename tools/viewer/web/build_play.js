// Build and Play in game (refactor stage P4): the Build window's and Play's wiring and state.
// - Build: its panel asks whether to bake the lighting (build_options.js), the open project is saved first if it has
//   unsaved changes, and the server builds the saved revision; a window covers the editor while the build runs and
//   follows it to its end (the window's words: build_window.js).
// - Play in game: the game started in a battle on the open map, or on the open project's build, built first when the
//   last build isn't of what is on screen (its words and requests: play.js); a finished build's window plays it too.
// - With them: the header's Build and Play buttons and the Game menu's Installs, the test squad's line, the prefab
//   builder's Test in game opened, and the build queue's chip in the top bar.
//
// createBuildPlay takes what it needs of app.js as one argument object, when app.js makes it: the views and dialogs
// it opens (Prepare, the Save dialog, a spawn point's marker, the landing zones), the selection, the document
// session's banner and save, and the prefab builder's document. Its own state is inside it (the build its window
// follows, a play waiting for its build, the next play's landing zone, mission and saving); the play status, which the
// Missions panel reads too, the picked landing zone and the mission picker's value are editor_state.js's.
import { activeMapId, buildTimer, builderMode, landingZones, lastBuild, missionPickValue, pickedZone, playStatus, project,
         saving, setBuildTimer, setLastBuildValue, setPlayStatus } from './editor_state.js';
import { createBuildOptions, savingHelp } from './build_options.js';
import { chipWords, clock } from './build_queue.js';
import { buildBar, buildSteps, leftOutList, logText, missionWarnings, secondsBetween } from './build_window.js';
import { ADDED_KINDS, kindKey, missionNote, setParagraphs } from './missions.js';
import { missionRequest, playApi, playBlocked, playedMessage, renderInstalls } from './play.js';
import { PREFAB_TILES, prefabStageLevels } from './prefab_document.js';
import { createPrefabTest } from './prefab_test.js';
import { api as projectApi, uuid } from './project.js';
import { createSquadDialog, squadLine } from './squad.js';
import { plural, short, text } from './dom_words.js';

export function createBuildPlay({ $, bakeNote, banner, builder, builderDocument, builderRecords, dirty, dragHint,
                                  flashHint, gizmo, headerMissions, mapLabel, needsPrepare, projectsAvailable,
                                  saveProject, selectActors, setZones, showFileDialog, showPop, showPrepare, showSpawn,
                                  zonesNow }) {
  // Build (Ctrl+B, the header's Build): a panel first asks whether to bake the lighting (build_options.js; off by default),
  // then the open project is saved if it has unsaved changes (Save itself never builds) and the server builds the saved
  // revision (tools/viewer/builds.py runs tools/editor/build.py, with --quick when not baking): the variant package in the
  // builds folder. Nothing is installed. While it runs, a window covers the editor, since the build takes
  // the saved revision and nothing should change under it. The window shows:
  // - the steps with their times, and the step running with its progress (relight.py counts the pieces it relights);
  // - the log's latest lines;
  // - the time so far against the project's last build, which gives the bar its estimate.
  // When the build ends, the window shows the package or why it failed, and closes with Close or Esc.
  let buildTicker = null, buildView = null;     // (the build status and the next ask for it: editor_state.js)
  // (the window's words: build_window.js)
  // Whether Build can start now: false (with a hint) without a saved project or while a build runs.
  function canBuild() {
    if (!projectsAvailable() || saving) return false;
    if (!project) { flashHint('Name and save the project first: Build makes a package of a saved project'); showFileDialog('save'); return false; }
    if (lastBuild?.state === 'running') { flashHint('The build is still running'); return false; }
    return true;
  }
  // Build's panel: whether to bake the lighting, then buildProject.
  function openBuild() {
    if (buildOptions.open || !canBuild() || needsPrepare()) return;
    buildOptions.show({
      title: `Build ${project.doc.name}`,
      note: `${dirty() ? 'What is on screen, saved first as a new revision' : `Revision ${project.revision}, as saved`}, into its variant package in the builds folder (${project.doc.output?.shipAs}). It replaces the last package and installs nothing.`,
      times: lastBuild?.package?.times ?? {}, bakeNote: bakeNote(),
      ok: 'Build', onBuild: ({ quick }) => buildProject(quick),
    });
  }
  // quick: the edit made in the map without baking its lighting (build.py --quick): seconds, not minutes.
  async function buildProject(quick = false) {
    if (!canBuild()) return;
    if (dirty() && !(await saveProject())) return;
    try {
      const id = project.doc.id, status = await projectApi.build(id, quick);
      // Play in game asked for this very build: its attempt, so no other build of the project (the queue's) plays
      if (playAfterBuild && !playAfterBuild.attempt && status.job?.project === playAfterBuild.project) playAfterBuild.attempt = status.job.attempt;
      followBuild(status, id);
    }
    catch (e) { banner(`Not built: ${e.message}`); }
  }
  // The build status of the open project (review finding 10): kept with the id it was asked for, and an answer for a
  // project no longer open (the page saved as another since) thrown away. False when it was.
  function setLastBuild(id, status) {
    if (!project || project.doc.id !== id) return false;
    setLastBuildValue({ ...status, project: id });
    return true;
  }
  // Each status from the server (every 2 s while the build runs). A build that ended before this page saw it running
  // opens no window: its package shows in the Project menu. A build of the build queue's (job.origin 'queue') opens no
  // window either: the editor stays usable, and the chip and the project manager follow it. `id`: the project it was
  // asked for (a late answer for another is dropped).
  function followBuild(status, id = project?.doc.id) {
    clearTimeout(buildTimer);
    if (!setLastBuild(id, status)) return;
    const job = status.job;
    if (!project || !job) return;
    if (job.origin === 'queue' && buildView?.attempt !== job.attempt) { renderPlayItems(); return; }
    if (buildView?.attempt !== (job.attempt ?? job.startedAt)) {
      if (status.state !== 'running') return;
      // the estimate: how long the project's last build of the same kind (full or quick) took
      const times = status.package?.times;
      buildView = { attempt: job.attempt ?? job.startedAt, started: job.startedAt, estimate: (job.quick ? times?.quick : times?.full) || null,
                    failures: 0, fullLog: false, thenInstall: Boolean(job.attempt) && playAfterBuild?.attempt === job.attempt, install: null };
      $('buildPlaySaving').checked = false;           // the window's Enable saving: off for each build
      openBuildWindow();
    }
    Object.assign(buildView, { status, failures: 0 });
    if (status.state === 'failed' && !buildView.ended) buildView.fullLog = true;
    buildView.ended = status.state !== 'running';
    // Play in game asked for this build: play it once built (this attempt alone).
    if (buildView.ended && job.attempt && playAfterBuild?.attempt === job.attempt) {
      playAfterBuild = null;
      if (status.state === 'built') playBuilt(job.project, job.attempt);
    }
    renderBuild(); renderPlayItems();
    if (!buildView.ended) setBuildTimer(setTimeout(pollBuild, 2000));
    else {
      clearInterval(buildTicker); $('buildClose').focus();
      // the window's Play in game goes by the installs as they are now
      if (status.state === 'built') refreshInstalls().then(() => { if (!$('buildModal').hidden) renderBuild(); });
    }
  }
  function pollBuild() {
    if (!project) return;
    const id = project.doc.id;
    projectApi.buildStatus(id).then(status => followBuild(status, id), () => {
      buildView.failures++;
      renderBuild();
      setBuildTimer(setTimeout(pollBuild, 5000));
    });
  }
  function openBuildWindow() {
    const el = $('buildModal');
    el.hidden = false;
    document.activeElement?.blur?.();
    el.focus();
    gizmo.cancel(); dragHint(false);
    clearInterval(buildTicker);
    buildTicker = setInterval(() => { if (buildView && !buildView.ended) renderBuild(); }, 1000);
  }
  // Closed while the build still runs (only when the server stopped answering): keep asking, and open it again if the
  // server answers with the build still running.
  function closeBuildWindow() {
    clearInterval(buildTicker); clearTimeout(buildTimer);
    $('buildModal').hidden = true;
    if (buildView && !buildView.ended) { buildView.attempt = null; setBuildTimer(setTimeout(pollBuild, 5000)); }
  }
  function renderBuild() {
    const { status, estimate, failures } = buildView, job = status.job;
    const running = status.state === 'running', built = status.state === 'built';
    const elapsed = secondsBetween(job.startedAt, job.finishedAt);
    $('buildIcon').className = `buildicon ${running ? 'spin' : status.state}`;
    const cancelled = status.state === 'cancelled';
    // a quick build (the edit without its lighting baked) says so in its title, and once built, what that means
    const quick = Boolean(job.quick), kind = quick ? ' (lighting not baked)' : '';
    // Play in game, once built: the package installed and the game started on it, from the window (playFinished)
    const install = buildView.install, playable = built && Boolean(status.package) && !playStatus?.unavailable;
    $('buildTitle').textContent = running ? `Building ${job.name}${kind}` : built ? `Built ${job.name}${kind}` : cancelled ? `${job.name}: build cancelled` : `${job.name} didn't build`;
    $('buildClock').textContent = clock(elapsed);
    $('buildNote').textContent = failures >= 3
      ? 'The viewer\'s server isn\'t answering (was it restarted?). The build may still be running; trying again every 5 s.'
      : running ? `Revision ${job.revision}, as saved${quick ? ', its lighting not baked' : ''}${buildView.thenInstall ? '; played in the game once built' : ''}. The editor waits until the build ends.`
      : built ? `Revision ${job.revision}, in ${clock(elapsed)}.${quick ? ' Its lighting is not baked: in the game the edit\'s lighting is wrong, while pathing, cover and line of sight are as a full build makes them. Build with Bake the lighting ticked for the proper lighting.' : ''}${buildView.thenInstall || install ? ''
        : playable ? ' Nothing is installed yet: Play in game installs it and starts the game in a battle on it.' : ' Nothing is installed: the package\'s README says how.'}`
      : `Revision ${job.revision}, stopped after ${clock(elapsed)}.`;
    // the steps: done with their times, the one running with its progress (build_window.js buildSteps)
    const stages = Object.fromEntries((job.stages || []).map(s => [s.stage, s]));
    const list = $('buildSteps');
    list.replaceChildren();
    for (const step of buildSteps(status)) {
      const li = text(list, 'li', '', step.state);
      text(li, 'span', '', 'stepmark');
      const what = text(li, 'span', step.label, 'what');
      if (step.detail) text(what, 'small', step.detail);
      if (step.progress !== null) text(text(what, 'span', '', 'stepbar'), 'span').style.width = `${(100 * step.progress).toFixed(1)}%`;
      text(li, 'span', step.time, 'time');
    }
    // the pieces left out of the build: it goes on without them; a row selects its piece
    const gone = leftOutList(status), goneList = $('buildLeftOut');
    goneList.hidden = !gone;
    goneList.replaceChildren();
    if (gone) {
      text(goneList, 'li', gone.head, 'head');
      for (const row of gone.rows) {
        const li = text(goneList, 'li', row.message, row.actor ? 'pick' : '');
        if (row.actor) { li.title = `Select ${short(row.actor)}`; li.onclick = () => selectActors([row.actor]); }
      }
      if (gone.more) text(goneList, 'li', gone.more);
    }
    // what the edit does to the missions the variant keeps, by mission: a row shows its object's marker
    const warned = missionWarnings(status), missionList = $('buildMissions');
    missionList.hidden = !warned;
    missionList.replaceChildren();
    if (warned) {
      text(missionList, 'li', warned.head, 'head');
      for (const [mission, rows] of warned.missions) {
        text(missionList, 'li', mission ?? 'A mission', 'mission');
        for (const row of rows) {
          const li = text(missionList, 'li', row.message.replace(/^[^:]*: /, ''), row.actor ? 'pick' : '');
          if (row.actor) { li.title = `Show ${short(row.actor)} (its marker, the Normal button's Spawn points and objectives)`; li.onclick = () => showSpawn(row.actor, row.stream ?? null); }
        }
      }
      if (warned.more) text(missionList, 'li', warned.more);
    }
    // the bar: the time so far against the last build's, or a moving bar when there is none to go by
    const bar = $('buildBar'), shownBar = buildBar(status, estimate, elapsed);
    bar.className = shownBar.className;
    bar.firstElementChild.style.width = `${(100 * shownBar.share).toFixed(1)}%`;
    $('buildBarText').textContent = shownBar.text;
    // the log: its latest lines, or all the server keeps (the last 40)
    // (written only when it changes; the full log follows its end unless it was scrolled up to read)
    const log = $('buildLog'), shown = logText(job, buildView.fullLog);
    const wasFull = log.classList.contains('full'), atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 4;
    if (log.textContent !== shown) log.textContent = shown;
    log.classList.toggle('full', buildView.fullLog);
    if (buildView.fullLog && (atEnd || !wasFull)) log.scrollTop = log.scrollHeight;
    $('buildLogToggle').textContent = buildView.fullLog ? 'Latest lines only' : 'Show the log';
    // the result
    const result = $('buildResult'), pkg = status.package;
    // the compiler found no export new enough (compiler.ExportMissing's code, the job's errorCode): Prepare the map does it from here
    const wantsPrepare = status.state === 'failed' && job.errorCode === 'export-missing';
    result.replaceChildren();
    result.hidden = running;
    result.classList.toggle('error', status.state === 'failed');
    if (built && pkg) {
      pathLink(result, pkg.folder);
      text(result, 'small', pkg.files.join(' · '));
      // the relight's writes reached the lightmaps of pieces it was not relighting (build.py other_pieces_changed)
      const other = stages.light?.otherPiecesChanged;
      if (other) {
        const piece = p => { const parts = String(p).split('.'); return parts.length > 1 && /Component/.test(parts.at(-1)) ? parts.at(-2) : parts.at(-1); };
        text(result, 'div', `Writing the lighting also changed ${other.texels} texels (by up to ${Math.round(100 * (other.largest ?? 0))}%) in the lightmaps of ${plural(other.count, 'piece')} it did not relight: ${(other.pieces ?? []).slice(0, 6).map(piece).join(', ')}${other.count > 6 ? ', …' : ''}. Their lighting there differs from the map's own bake.`);
      }
    } else if (status.state === 'failed' || cancelled) {
      if (wantsPrepare) text(result, 'div', `The editor's copy of ${mapLabel(activeMapId)} is older than this build needs. Prepare the map again, then build.`, 'remedy');
      text(result, 'div', job.error ?? 'See the log.');
    }
    if (buildView.reportPath) pathLink(result, buildView.reportPath, 'Bug report saved (its path is copied): ');
    else if (buildView.report) text(result, 'div', buildView.report, 'path');
    if (install) setParagraphs(text(result, 'div', '', `install ${install.state}`), install.state === 'running' ? 'Installing it and starting the game…' : install.message);
    const play = $('buildPlay'), cantPlay = playBlocked(playStatus);
    play.hidden = !playable;
    play.disabled = install?.state === 'running' || Boolean(cantPlay);
    // Enable saving beside it: off unless ticked, fixed on for a mission that needs it (the header's)
    const savingRow = $('buildPlaySavingRow'), saving = $('buildPlaySaving'), forced = savingFor(missionPickValue);
    savingRow.hidden = !playable;
    if (forced) saving.checked = true;
    else if (saving.dataset.forced) saving.checked = false;   // fixed on for the mission before: off again
    saving.dataset.forced = forced ? '1' : '';
    saving.disabled = Boolean(forced) || play.disabled;
    savingRow.title = forced ?? savingHelp(playStatus?.saveKey ?? 'F5');
    play.title = cantPlay ? `Not now: ${cantPlay}`
      : `Install this build in ${playStatus?.install?.sameAsLwr === false ? 'the install under Installs' : 'the game install'} under its own name and start the game in a battle on it: no campaign to start, and nothing of the game's own is changed`;
    $('buildCopy').hidden = !(built && pkg);
    $('buildPrepare').hidden = !wantsPrepare;
    $('buildClose').classList.toggle('primary', !wantsPrepare);
    $('buildCancel').hidden = !running || failures >= 3;
    $('buildReport').hidden = running;
    $('buildClose').hidden = running && failures < 3;
  }
  // A path of the builds folder as a link: a click shows it in Windows Explorer (builds.py reveal); before: words ahead.
  function pathLink(parent, path, before = '') {
    const line = text(parent, 'div', before);
    const link = text(line, 'a', path, 'path');
    link.href = '#';
    link.title = 'Show in Windows Explorer';
    link.onclick = async e => {
      e.preventDefault();
      try { await projectApi.reveal(path); }
      catch (error) { link.title = `Not shown: ${error.message}`; link.classList.add('failed'); }
    };
    return link;
  }
  $('buildLogToggle').onclick = () => { buildView.fullLog = !buildView.fullLog; renderBuild(); };
  $('buildCopy').onclick = () => {
    navigator.clipboard?.writeText(buildView.status.package.folder).then(() => { $('buildCopy').textContent = 'Copied'; },
      () => { $('buildCopy').textContent = 'Copy failed'; });
    setTimeout(() => { $('buildCopy').textContent = 'Copy the folder path'; }, 1500);
  };
  $('buildClose').onclick = closeBuildWindow;
  // Play in game from a finished build's window: that build installed and the game started on it (playBuilt), the
  // outcome shown in the window. It asks the server first, as the header's Play does (XCOM may be open).
  async function playFinished() {
    const id = buildView.status.job.project;
    playZone = null;                                  // the window's own Play: no landing zone of a Land here
    playMission = missionPickValue;                   // and the header's mission
    playSaving = $('buildPlaySaving').checked;        // and its own Enable saving
    buildView.install = { state: 'running' };
    renderBuild();
    let why;
    try { setPlayStatus(await playApi.status()); why = playBlocked(playStatus); }
    catch (e) { why = e.message; }
    if (why) { buildView.install = { state: 'failed', message: `Not started: ${why}.` }; renderBuild(); return; }
    playBuilt(id, buildView.status.job.attempt);
  }
  $('buildPlay').onclick = playFinished;
  $('buildPrepare').onclick = () => { closeBuildWindow(); showPrepare('failed', true); };
  // Cancel stops the build and its tools (builds.py); the package swaps in only at the end, so the last good one stays.
  $('buildCancel').onclick = async () => {
    $('buildCancel').disabled = true;
    try { const id = buildView.status.job.project; followBuild(await projectApi.cancelBuild(id, buildView.status.job.attempt), id); }
    catch (e) { buildView.report = `Not cancelled: ${e.message}`; buildView.reportPath = null; renderBuild(); }
    finally { $('buildCancel').disabled = false; }
  };
  // A bug report: the project, the build's logs and manifest zipped in the builds folder (builds.py report).
  $('buildReport').onclick = async () => {
    $('buildReport').disabled = true;
    try {
      const r = await projectApi.report(buildView.status.job.project);
      buildView.report = null; buildView.reportPath = r.zip;
      navigator.clipboard?.writeText(r.zip).catch(() => {});
    } catch (e) { buildView.report = `No bug report: ${e.message}`; buildView.reportPath = null; }
    finally { $('buildReport').disabled = false; renderBuild(); }
  };
  // While the build window is open the editor takes no keys (Ctrl shortcuts included); the window's buttons keep theirs,
  // and Esc closes it once the build has ended.
  window.addEventListener('keydown', e => {
    if ($('buildModal').hidden) return;
    e.stopImmediatePropagation();
    if (e.key === 'Escape' && !$('buildClose').hidden) { e.preventDefault(); closeBuildWindow(); }
    else if ((e.ctrlKey || e.metaKey) && !['c', 'r'].includes(e.key.toLowerCase())) e.preventDefault();
  }, true);
  const BUILD_TITLE = $('projectBuild').title;
  // Play in game and Remove from game (play.js, tools/viewer/play.py): the game started straight in a battle on the open
  // map, in the game install the settings name (the install setting, else the game install the editor reads). With a
  // project open it plays the project's build, building first when the last build isn't of what is on screen; with a map
  // alone, the original map (no edits). The Game menu's Installs section says what the editor works with.
  // playAfterBuild: { project, attempt } once Build and play has asked for a build (its attempt once the server took it)
  let playAfterBuild = null;     // (the play status, playStatus: editor_state.js)
  // Land here (Clear map plan, section 4): the landing zone, by id, the next play of the project lands at, else null
  let playZone = null;
  // The mission the next play is (mission types plan, A4): one of playMissions()'s values, chosen in the play dialog
  let playMission = null;
  // Whether the next play has saving on (play.py): the game starts at its main menu and a key there opens the battle
  let playSaving = false;
  // Why a play of the mission (a playMissions() value) has saving on whatever is chosen (Long War's EXALT missions:
  // the server's table of kinds), or null
  function savingFor(value) {
    const m = headerMissions().find(x => x.value === String(value));
    return playStatus?.missionKinds?.[kindKey(m?.mission)]?.saving ?? null;
  }
  // the Build panel's saving row for a play (build_options.js show's `saving`)
  const savingOption = mission => ({ key: playStatus?.saveKey ?? 'F5', mission, forcedFor: savingFor });
  // The missions a play can be, as the play dialog lists them: the map's records (the export's `missions`, the
  // header's Mission picker), each with its kind's line from the server's table.
  function playMissions() {
    return headerMissions().map(m => ({ value: m.value, label: m.label }));
  }
  function playMissionNote(value) {
    const m = headerMissions().find(x => x.value === String(value));
    if (m?.entry) {
      return [ADDED_KINDS[m.entry.kind]?.needs,
        ...missionNote(playStatus?.missionKinds, m.mission).split('\n').slice(1)].filter(Boolean).join('\n');
    }
    return missionNote(playStatus?.missionKinds, m?.mission);
  }
  // (a play's mission as the server takes it: play.js missionRequest)
  // The header's picker follows the mission played, so the streams on screen are that mission's.
  function followPlayedMission(value) {
    const v = String(value);
    if (v === missionPickValue || !headerMissions().some(m => m.value === v)) return;
    $('mission').value = v;
    $('mission').onchange({ target: $('mission') });
  }
  // (the open project's own package, of what is on screen: the same project, not just the same revision number, review
  // finding 10)
  const builtAsShown = () => Boolean(project) && !dirty() && lastBuild?.project === project.doc.id && lastBuild?.package?.revision === project.revision;
  async function refreshInstalls() {
    try { setPlayStatus(await playApi.status()); }
    catch (e) { setPlayStatus({ error: e.message, unavailable: e.status === 404 }); }
    drawInstalls();
  }
  // The Game menu's Installs and the header's play items from the play status as it is: the server's answer to a
  // status read (refreshInstalls) or to a play, which is a whole status too, so the menu says what the play installed
  // without being opened again.
  function drawInstalls() {
    renderInstalls($('installInfo'), playStatus, mapLabel);
    renderPlayItems();
  }
  // (why the game can't be played now: play.js playBlocked)
  // The header's Build and Play buttons and the Game menu's Game maps: what each can do now, and why not.
  function renderPlayItems() {
    const s = playStatus, play = $('projectPlay'), maps = $('projectMaps'), build = $('projectBuild');
    if (!builderMode) {
      build.disabled = !projectsAvailable() || !project || lastBuild?.state === 'running';
      build.title = !projectsAvailable() ? 'Build makes a project\'s map for the game: open the map from the map browser (M) and save a project on it'
        : !project ? 'Build makes the project\'s map for the game: save the edits as a project first (Ctrl+S)'
        : lastBuild?.state === 'running' ? 'The project is being built'
        : BUILD_TITLE;
    }
    play.hidden = maps.hidden = Boolean(s?.unavailable);
    $('playGroup').classList.toggle('alone', play.hidden && $('prefabTest').hidden);
    const ready = Boolean(s?.install?.ready), why = s?.install?.why ?? s?.error;
    const cantStart = ready && s?.launch && !s.launch.how ? s.launch.why : null;
    const where = s?.install?.sameAsLwr ? 'the game install' : 'the install the Game menu names under Installs';
    play.disabled = !projectsAvailable() || !ready || Boolean(cantStart) || lastBuild?.state === 'running';
    play.title = !projectsAvailable() ? 'Play in game starts the game on a map\'s original layout or a project on it: open the map from the map browser (M)'
      : !ready ? `Not now: ${why ?? 'asking the server'}`
      : cantStart ? `Not possible: ${cantStart}`
      : project ? `Start the game in a battle on ${project.doc.name}, in ${where}: no campaign to start, and nothing of the game's own is changed. Build's panel asks first whether to bake the lighting${builtAsShown()
          ? `, or to play its last build as it is (revision ${project.revision}, lighting ${lastBuild.package.quick ? 'not baked' : 'baked'})` : ''}`
      : `Start the game in a battle on the original ${mapLabel(activeMapId)} (no project open, so no edits), in ${where}: no campaign to start, and nothing is installed (but a copy of the map's record where the game comments its records out: the tutorial's map)`;
    maps.title = `The map records of ${where} as the game reads them now: which are in rotation, which a project's build replaces or adds to, and each one switched off or on. It undoes what the editor changed${s?.game?.anything ? ' (there is something of the editor\'s in the game now)' : ''}`;
  }
  // (the "Starting XCOM" message: play.js playedMessage)
  async function playInGame(zoned) {
    if (zoned !== true) playZone = null;
    showPop(null);
    if (!projectsAvailable() || saving) return;
    if (lastBuild?.state === 'running') { flashHint('The build is still running'); return; }
    try { setPlayStatus(await playApi.status()); }
    catch (e) { banner(`Not started: ${e.message}`); return; }
    if (!playStatus.install.ready) { banner(`Not started: ${playStatus.install.why}.`, [['Try again', playAgain]]); return; }
    if (playStatus.launch && !playStatus.launch.how) { banner(`Not started: ${playStatus.launch.why}.`); return; }
    const missions = playMissions();
    if (!project) {
      // a map alone: the play dialog, for which of its missions and whether saving is on
      if (buildOptions.open) return;
      const only = missions.length < 2 ? missions[0]?.value ?? '0' : null;
      buildOptions.show({
        title: `Play ${mapLabel(activeMapId)} in the game`, build: false, ok: 'Play',
        note: `Plays the original map (no edits) in ${playStatus.install.sameAsLwr ? 'the game install' : 'the install under Installs'}.`,
        missions, mission: missionPickValue, missionNote: playMissionNote, saving: savingOption(only ?? missionPickValue),
        squad: squadLine(playStatus.squad),
        onBuild: ({ mission, saving }) => {
          const chosen = mission ?? only ?? 0;
          followPlayedMission(chosen);
          sendPlay({ map: activeMapId, mission: missionRequest(chosen), saving }, mapLabel(activeMapId));
        },
      });
      return;
    }
    if (needsPrepare()) return;
    // A project opens Build's panel (build_options.js): build it, baked or not, and play it once built; or, when its
    // last build is of what is on screen, play that as it is (then the default).
    if (buildOptions.open) return;
    const where = playStatus.install.sameAsLwr ? 'the game install' : 'the install under Installs';
    const current = builtAsShown() ? lastBuild.package : null;
    const what = dirty() ? 'What is on screen, saved first as a new revision,' : `Revision ${project.revision}`;
    const zoneAt = playZone ? zonesNow().findIndex(z => z.id === playZone) : -1;
    buildOptions.show({
      title: `Play ${project.doc.name} in the game${zoneAt >= 0 ? `, landing at zone ${zoneAt + 1}` : ''}`,
      note: `${what} installed in ${where} under its own name, and the game started in a battle on it. ${current
        ? `Its last build (lighting ${current.quick ? 'not baked' : 'baked'}) can be played as it is, or it can be built again first.`
        : 'It is built first and played when the build ends.'}`,
      times: lastBuild?.package?.times ?? {}, bakeNote: bakeNote(),
      missions, mission: missionPickValue, missionNote: playMissionNote, saving: savingOption(missionPickValue),
      squad: squadLine(playStatus.squad),
      ok: 'Build and play', onBuild: ({ quick, mission, saving }) => playChosen(quick ? 'quick' : 'full', mission, saving),
      last: current ? 'Play last build' : null, onLast: ({ mission, saving }) => playChosen('last', mission, saving),
    });
  }
  async function playChosen(kind, mission = null, saving = false) {
    if (!project || lastBuild?.state === 'running') return;
    playMission = mission === null || mission === undefined ? missionPickValue : String(mission);
    playSaving = Boolean(saving);
    followPlayedMission(playMission);
    // (the build shown, named: a package swapped in since starts nothing, play.py)
    if (kind === 'last') { if (builtAsShown()) sendPlay(withZone({ project: project.doc.id, buildId: lastBuild.package.buildId }), project.doc.name); return; }
    // save and build it, and play it when that build ends (followBuild)
    playAfterBuild = { project: project.doc.id, attempt: null };
    await buildProject(kind === 'quick');
    // the build didn't start (not saved, or refused: the build queue holds the slot): no later build plays
    if (!playAfterBuild?.attempt) playAfterBuild = null;
  }
  async function sendPlay(request, label) {
    flashHint(`Starting the game on ${label}…`);
    try { const r = await playApi.start(request); setPlayStatus(r); drawInstalls(); banner(playedMessage(r, mapLabel), [], playedFor(r)); }
    catch (e) { banner(e.message, [['Try again', playAgain]]); }
  }
  // how long the "Starting XCOM …" message stays: a play with saving on keeps it until dismissed (it says the key)
  const playedFor = r => (r?.played?.saving ? {} : { timeout: PLAYED_FOR });
  const playAgain = () => playInGame(playZone !== null);
  const withZone = request => ({ ...request, ...(playZone ? { zone: playZone } : {}), mission: missionRequest(playMission ?? missionPickValue),
                                 saving: playSaving });
  // Land here: Play in game for the project, the squad landing at the picked zone (under LWR that zone's line alone is
  // installed; a zone that is one of the map's own landings opens on its spawn group). The build must carry the zone's
  // id, so a project still on the map's own lines takes them in first (one undo step), which makes it a change to build.
  function landHere() {
    if (!pickedZone || !project) return;
    if (!landingZones) setZones(zonesNow(), 'Took the map\'s landing zones into the project');
    playZone = pickedZone;
    playInGame(true);
  }
  const PLAYED_FOR = 12000;     // ms the "Starting XCOM …" message stays (a failure stays until dismissed)
  // After a build Play in game asked for: the outcome shows in the build window, or in a banner once it's closed.
  // `attempt`: that build's, so the play starts that package and no other (play.py checks it under its guard).
  async function playBuilt(id, attempt = null) {
    buildView.install = { state: 'running' };
    try {
      const r = await playApi.start(withZone({ project: id, ...(attempt ? { attempt } : {}) }));
      setPlayStatus(r); drawInstalls();
      buildView.install = { state: 'done', message: playedMessage(r, mapLabel), saving: Boolean(r.played?.saving) };
    }
    catch (e) { buildView.install = { state: 'failed', message: e.message }; }
    if (!$('buildModal').hidden) renderBuild();
    else if (buildView.install.state === 'failed') banner(buildView.install.message, [['Try again', playAgain]]);
    else banner(buildView.install.message, [], buildView.install.saving ? {} : { timeout: PLAYED_FOR });
  }
  // Build's panel: whether to bake the lighting, for Build (openBuild) and Play in game (playInGame).
  const buildOptions = createBuildOptions({
    els: { root: $('buildOptions'), form: $('buildForm'), title: $('buildOptionsTitle'), note: $('buildOptionsNote'),
           bake: $('buildBake'), bakeRow: $('buildBakeRow'), bakeNote: $('buildBakeNote'), estimate: $('buildEstimate'), ok: $('buildOptionsOk'), last: $('buildOptionsLast'),
           missionRow: $('buildMissionRow'), mission: $('buildMission'), missionNote: $('buildMissionNote'),
           mapBakeHelp: $('buildMapBakeHelp'), testBakeHelp: $('buildTestBakeHelp'),
           savingRow: $('buildSavingRow'), saving: $('buildSaving'), savingHelp: $('buildSavingHelp'),
           squadRow: $('buildSquadRow'), squad: $('buildSquad'),
           close: $('buildOptionsClose'), cancel: $('buildOptionsCancel') },
    onSquad: () => squadDialog.show() });
  // Test squad setup (squad.js; Settings menu, and the play dialog's squad line): the one squad every play lands with.
  // A save refreshes the play status, so the squad line of an open play dialog and the Settings menu follow it.
  const squadDialog = createSquadDialog({
    els: { root: $('squadDialog'), form: $('squadForm'), title: $('squadTitle'), intro: $('squadIntro'), problem: $('squadProblem'),
           name: $('squadName'), units: $('squadUnits'), add: $('squadAdd'), copy: $('squadCopy'), remove: $('squadRemove'),
           up: $('squadUp'), down: $('squadDown'), count: $('squadCount'), unit: $('squadUnit'), issues: $('squadIssues'),
           wide: $('squadWide'), status: $('squadStatus'), exportButton: $('squadExport'), importButton: $('squadImport'),
           importFile: $('squadImportFile'), reset: $('squadReset'), cancel: $('squadCancel'), save: $('squadSave'),
           close: $('squadClose') },
    onSaved: () => refreshSquadLine(true),
  });
  async function refreshSquadLine(saved = false) {
    try { setPlayStatus(await playApi.status()); }
    catch (e) { if (saved) flashHint(`Saved; the play status could not be read: ${e.message}`); return; }
    const line = squadLine(playStatus.squad);
    if (buildOptions.open) buildOptions.setSquad(line);
    const menu = $('settingsSquadLine');
    menu.textContent = line ? line.text : 'The squad is not known: this server starts no game.';
    menu.title = line?.title ?? '';
    menu.classList.toggle('warn', Boolean(line?.warn));
    if (saved && !buildOptions.open) flashHint('Saved the test squad: the next Play in game lands with it');
  }
  $('settingsSquad').onclick = () => { showPop(null); squadDialog.show(); };
  const prefabTest = createPrefabTest({
    els: { root: $('prefabTestModal'), icon: $('prefabTestIcon'), title: $('prefabTestTitle'), note: $('prefabTestNote'),
           bar: $('prefabTestBar'), status: $('prefabTestStatus'), issues: $('prefabTestIssues'), details: $('prefabTestDetails'),
           log: $('prefabTestLog'), close: $('prefabTestClose'), cancel: $('prefabTestCancel'), launch: $('prefabTestLaunch') },
    uuid, onPick: actor => selectActors([actor]),
  });
  // How many levels the test's stage gets (prefab_stage.py stage_levels): what the prefab needs, 18 at least, 30 at most.
  const testStageLevels = prefabStageLevels;     // (prefab_document.js: prefab_stage.stage_levels' twin)
  async function openPrefabTest() {
    showPop(null);
    if (!builderMode || builder.loading || buildOptions.open || prefabTest.showExisting()) return;
    let target;
    try {
      const status = await playApi.status();
      const blocked = playBlocked(status);
      if (blocked) { banner(blocked, [['Try again', openPrefabTest]]); return; }
      target = status.install.folder;
      setPlayStatus(status);
    } catch (e) { banner(e.message, [['Try again', openPrefabTest]]); return; }
    if (buildOptions.open || prefabTest.showExisting()) return;
    const { size } = builderRecords(), [x, y] = size.tiles;
    const label = builder.doc.revision ? builder.doc.name : 'Unsaved prefab';
    const revision = dirty() ? 'Unsaved changes included.' : builder.doc.revision ? `Revision ${builder.doc.revision}.` : '';
    buildOptions.show({
      title: builder.doc.revision ? `Test ${label} in game` : 'Test unsaved prefab in game',
      note: [`${x} × ${y} tiles, height ${size.bounds[2].toFixed(1)}–${size.bounds[5].toFixed(1)}, on a stage ${testStageLevels(size.bounds)} levels high`
        + '.',
        Math.max(x, y) > PREFAB_TILES ? `It is too large for the ${PREFAB_TILES} by ${PREFAB_TILES} tile stage: the test will say so.` : '',
        revision, `Game install ${target}`].filter(Boolean).join(' '),
      ok: 'Build and test', bake: false, prefabTest: true, saving: { key: playStatus?.saveKey ?? 'F5' },
      squad: squadLine(playStatus?.squad),
      onBuild: ({ quick, saving }) => prefabTest.start(builderDocument(), quick, dirty() || !builder.doc.revision, saving),
    });
  }
  function renderQueueChip(state, info) {
    const chip = $('queueChip'), words = chipWords(state);
    chip.hidden = !words;
    if (!words) return;
    chip.textContent = words.text + (info?.offline ? ' (not answering)' : '');
    chip.classList.toggle('warn', words.warn);
    chip.title = `The build queue: ${words.text}. Click to open the project manager and follow it`;
  }
  function followQueueForProject(state, info) {
    if (!project || builderMode) return;
    const id = project.doc.id, mine = state?.items?.find(i => i.project === id);
    const building = Boolean(mine && (mine.state === 'starting' || mine.state === 'building'));
    const shown = lastBuild?.state === 'running' && lastBuild.job?.origin === 'queue';
    if (building !== shown || info?.ended?.some(i => i.project === id))
      projectApi.buildStatus(id).then(s => { if (setLastBuild(id, s)) renderPlayItems(); }, () => {});
  }

  return { followBuild, followQueueForProject, landHere, openBuild, openPrefabTest, playInGame, prefabTest, refreshInstalls,
           refreshSquadLine, renderPlayItems, renderQueueChip, setLastBuild };
}
