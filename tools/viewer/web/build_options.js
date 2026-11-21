// Build's panel (build_play.js opens it): whether to bake the lighting, before a build of the open project. Build…
// (Ctrl+B) opens it to build; Play in game opens it to build and then play, and, when the project's last build is of
// what is on screen, offers to play that as it is instead (then the default, so a baked build isn't replaced unasked).
// Baking is off each time the panel opens: without it a build takes seconds and suits checking pathing, cover and line
// of sight in the game, which are the same either way (findings register T-20); with it, minutes, and the lighting is
// right too. The build itself is build_play.js buildProject (build.py, --quick when not baking).
// Play in game also names the mission it plays (private/plans/done/mission-types-plan.md, A4): the header's Mission
// picker's, with a select to change it here and a line on what is known of that kind of mission when played this way.
// A map alone opens the panel for that choice only (no build, nothing to bake).
// Enable saving (play.py, F-89): off each time the panel opens; on, the game starts at its main menu, whose login
// readies saving, and a key there opens the battle. A mission that needs it (Long War's EXALT missions, F-109) has it
// on and fixed, its reason as the tooltip.
// A play also names the test squad it lands with (squad.js): a line under the mission that opens Test squad setup,
// refreshed when the squad is saved there (setSquad).
import { setParagraphs } from './missions.js';
// (the queue's clock: whole seconds down, so 119.6 s is 1:59, not 1:60; review finding 34)
import { clock } from './build_queue.js';

export const savingHelp = key => `XCOM opens at its main menu: press ${key} there to start the battle.`;
const SAVING_OFF = 'Off: the battle starts by itself and can\'t be saved.';

/** els: root, form, title, note, bake (the checkbox), estimate, ok (the submit button), last, close, cancel, the
 *  mission row: missionRow, mission (the select), missionNote, the saving row: savingRow, saving (the checkbox),
 *  savingHelp, and the squad's line: squadRow, squad (its button). onSquad(): the squad's line was clicked. */
export function createBuildOptions({ els, onSquad = null }) {
  let lastFocus = null, times = {}, onBuild = null, onLast = null, noteOf = null, building = true;
  let savingOf = null, savingWanted = false;      // savingOf: show's `saving`, or null (no saving row)
  function hide() {
    els.root.hidden = true;
    lastFocus?.focus?.();
  }
  // how long a build will take, going by the project's last build of the same kind
  function estimate() {
    if (!building) { els.estimate.textContent = ''; return; }
    const bake = els.bake.checked, last = bake ? times.full : times.quick;
    els.estimate.textContent = last ? `About ${clock(last)}, going by its last ${bake ? 'baked' : 'unbaked'} build`
      : bake ? 'Several minutes' : 'A few seconds';
  }
  // the saving row: fixed on (with the reason as its tooltip) for a mission that needs it, else what was ticked; the
  // line under it says how the battle starts
  function savingChanged() {
    if (!els.savingRow || !savingOf) return;
    const forced = savingOf.forcedFor?.(chosenMission() ?? savingOf.mission) ?? null;
    els.saving.checked = Boolean(forced) || savingWanted;
    els.saving.disabled = Boolean(forced);
    els.savingRow.title = els.saving.title = forced ?? 'Start the game at its main menu first, so the battle can be saved and loaded';
    els.savingHelp.textContent = els.saving.checked ? savingHelp(savingOf.key ?? 'F5') : SAVING_OFF;
  }
  // the line under the mission: what is known of that kind played this way
  function missionChanged() {
    savingChanged();
    if (!els.missionNote) return;
    const text = noteOf ? noteOf(els.mission.value) : '';
    setParagraphs(els.missionNote, text);
    els.missionNote.hidden = !text;
  }
  // the test squad's line ({text, warn, title} from squad.js squadLine), or none
  function setSquad(line) {
    if (!els.squadRow) return;
    els.squadRow.hidden = !line;
    if (!line) return;
    els.squad.textContent = line.text;
    els.squad.title = `${line.title}. Click for Test squad setup`;
    els.squad.classList.toggle('warn', Boolean(line.warn));
  }
  if (els.squad) els.squad.onclick = () => onSquad?.();
  const chosenMission = () => (els.missionRow && !els.missionRow.hidden ? els.mission.value : null);
  const chosenSaving = () => Boolean(savingOf && els.saving?.checked);
  /**
   * title and note: what the panel is for, in a few words; times: the project's last full and quick builds' seconds;
   * ok: the build button's label; onBuild({quick, mission}): build (quick when the lighting isn't baked). last: null,
   * or the label of a button that does without a build (onLast({mission})), focused as the default; otherwise the
   * build button is. bakeNote: a sentence under the checkbox on what baking does for this project (its pieces of other
   * maps), or null. missions: null, or [{value, label}] to choose from (shown when there are two or more), with
   * `mission` the value chosen first and missionNote(value) the line under it. build: false for a play that builds
   * nothing (a map alone): no bake option and no estimate. saving: null (a build alone: no saving row), or {key: the
   * key that starts the battle, mission: the mission value when there is no choice, forcedFor(value): why that
   * mission needs saving on, or null}; the callbacks then get `saving` too. squad: the test squad's line for a play
   * (squad.js squadLine), or null.
   * Enter presses the focused button, Space toggles the checkbox, Esc or Cancel closes.
   */
  function show({ title, note, times: seconds = {}, ok = 'Build', onBuild: buildIt, last = null, onLast: skip = null,
                  bakeNote = null, bake = false, prefabTest = false, missions = null, mission = null, missionNote = null,
                  build = true, saving = null, squad = null }) {
    lastFocus = document.activeElement;
    times = seconds; onBuild = buildIt; onLast = skip; noteOf = missionNote; building = build;
    savingOf = saving; savingWanted = false;
    if (els.savingRow) els.savingRow.hidden = !saving;
    setSquad(squad);
    els.title.textContent = title;
    els.note.textContent = note;
    els.ok.textContent = ok;
    els.last.hidden = !last;
    if (last) els.last.textContent = last;
    // the default is the primary button
    els.last.classList.toggle('primary', Boolean(last));
    els.ok.classList.toggle('primary', !last);
    els.bake.checked = bake;
    els.bakeRow.hidden = !build;
    els.mapBakeHelp.hidden = prefabTest;
    els.testBakeHelp.hidden = !prefabTest;
    if (els.bakeNote) { els.bakeNote.hidden = !bakeNote || !build; els.bakeNote.textContent = bakeNote ?? ''; }
    if (els.missionRow) {
      const list = missions ?? [];
      els.missionRow.hidden = list.length < 2;
      els.mission.replaceChildren(...list.map(m => new Option(m.label, String(m.value))));
      if (list.length) els.mission.value = String(mission ?? list[0].value);
      missionChanged();
    } else savingChanged();
    estimate();
    els.root.hidden = false;
    setTimeout(() => (last ? els.last : els.ok).focus(), 0);
  }
  els.bake.onchange = estimate;
  if (els.mission) els.mission.onchange = missionChanged;
  if (els.saving) els.saving.onchange = () => { if (!els.saving.disabled) savingWanted = els.saving.checked; savingChanged(); };
  els.form.onsubmit = e => {
    e.preventDefault();
    const quick = !els.bake.checked, buildIt = onBuild, mission = chosenMission(), saving = chosenSaving();
    hide();
    buildIt?.({ quick, mission, saving });
  };
  els.last.onclick = () => {
    const skip = onLast, mission = chosenMission(), saving = chosenSaving();
    hide();
    skip?.({ mission, saving });
  };
  els.close.onclick = els.cancel.onclick = hide;
  els.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hide(); } });
  return { show, setSquad, get open() { return !els.root.hidden; } };
}
