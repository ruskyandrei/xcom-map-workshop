// The Map settings window (the Map menu's Map settings…, and View options' "Sun, moon and sky…"): what the map has
// everywhere and at no place. The sun, moon and sky light, listed (lights_wiring.js's buildLights fills the list), and
// the map's background sound (export 39's backgroundSound; the project's `backgroundSound`, schema 5): a choice of
// the map's own, the game's other beds (/background-sounds.json) or None, a Play button that plays the choice here
// (every wave of its cue at once, looping, through /background-sound.ogg: viewer.py, audio.py), and its volume, a
// slider under the choice. A change of the choice or of the volume (on the slider's release) is one undo step; the
// rules are background_sound_rules.js's. This is the design chosen on 22 November 2026 (mock design B, the volume as
// a bar).
// Between the sky and the sound, the map's fog and colour (the project's `atmosphere`, schema 10; the game-likeness
// plan's C5b): atmosphere_settings.js's section.
// Below them, what Long War Rebalance is told of the map (the project's `lwrMapInfo`, schema 6; missions.js's
// MAP_INFO): the largest abduction it suits and Hold the Line kept off it, which LWR 3.00.00 beta 17 and later reads
// from the map's pack. Each change is one undo step. The section is not shown where the game set is plain Enemy
// Within and the project tells nothing (23 November 2026: a section for Long War Rebalance alone, with
// room for what it reads later).
import { bedLabel, ownVolume, previewVolume, soundChoices, soundNow, soundRecord, VOLUME_SLIDER, volumeWords } from './background_sound_rules.js';
import { ask } from './api.js';
import { builderMode, data, landingLines, projectBackgroundSound, projectMapInfo, setProjectBackgroundSound,
         setProjectMapInfo } from './editor_state.js';
import { MAP_INFO, MAP_INFO_SINCE, mapInfoRecord, validMapInfo } from './missions.js';
import { createAtmosphereSettings } from './atmosphere_settings.js';

export function createMapSettings({ $, gizmo, projectsAvailable, showPop }) {
  const els = { root: $('mapSettings'), form: $('mapSettingsForm'), close: $('mapSettingsClose'), sound: $('mapSoundSection'),
                note: $('mapSoundNote'), choice: $('mapSound'), play: $('mapSoundPlay'), volume: $('mapSoundVolume'),
                volumeValue: $('mapSoundVolumeValue'), status: $('mapSoundStatus'), lwr: $('mapLwrSection'),
                lwrNote: $('mapLwrNote'), density: $('mapLwrDensity'), noHold: $('mapLwrNoHold') };
  els.density.append(new Option('Not set (any size)', ''), ...MAP_INFO.alienDensity[1].map(v => new Option(v, v)));
  Object.assign(els.volume, { min: VOLUME_SLIDER.min, max: VOLUME_SLIDER.max, step: VOLUME_SLIDER.step });
  let beds = null, bedsWhy = null, player = null, lastFocus = null;
  const { atmosphereState, paintAtmosphere, showAtmosphere } = createAtmosphereSettings({ $, gizmo, projectsAvailable });

  // the game's beds, asked once
  async function loadBeds() {
    if (beds) return beds;
    beds = (await ask('/background-sounds.json'))?.sounds ?? null;
    bedsWhy = beds ? null : 'the editor\'s server did not list them';
    return beds;
  }
  const own = () => data?.backgroundSound ?? null;
  const say = (message, warn = false) => { els.status.textContent = message; els.status.hidden = !message; els.status.classList.toggle('warn', warn); };

  // The window's controls as the project has the sound now
  function paint() {
    const mine = own(), editable = Boolean(mine && beds && projectsAvailable());
    els.choice.disabled = els.volume.disabled = els.play.disabled = !editable;
    if (!mine) {
      els.note.textContent = data?.backgroundSound === undefined ? 'This export says nothing of the map\'s background sound: open the map again to export it anew.'
        : 'This map starts no background sound when it loads, so there is none to change.';
      els.choice.replaceChildren(); els.volumeValue.textContent = '';
      return;
    }
    const now = soundNow(projectBackgroundSound, mine);
    els.note.textContent = `The sound bed the map plays everywhere from the start. This map's: ${bedLabel(beds ?? [], mine.cue)}.`;
    if (!projectsAvailable()) els.note.textContent += ' It is changed on a map opened from the map browser, not a preview.';
    // (while the list is asked for, the controls wait; only a refusal is said)
    if (!beds) { if (bedsWhy) say(`The game's other sounds can't be listed: ${bedsWhy}.`, true); return; }
    if (els.choice.options.length === 0) {
      for (const c of soundChoices(beds, mine)) els.choice.append(new Option(c.label, c.value));
    }
    els.choice.value = now.cue ?? '';
    els.volume.value = String(now.volume);
    els.volumeValue.textContent = volumeWords(now.volume);
    els.volume.disabled = !editable || now.cue === null;
  }
  // A change, one undo step: the project's record for the choice and the volume in the window now
  function commit() {
    const mine = own();
    if (!mine) return;
    const cue = els.choice.value || null, next = soundRecord(cue, Number(els.volume.value), mine), before = projectBackgroundSound;
    if (JSON.stringify(next) === JSON.stringify(before)) return;
    gizmo.record({ redo: () => { setProjectBackgroundSound(next); paint(); },
                   undo: () => { setProjectBackgroundSound(before); paint(); } });
  }

  // What Long War Rebalance is told of the map, as the project has it now
  function paintLwr() {
    const told = projectMapInfo, readable = told === null || validMapInfo(told), editable = projectsAvailable() && readable;
    // (plain Enemy Within reads none of it: the section shows there only for a project that tells something)
    els.lwr.hidden = landingLines?.kind === 'ew' && !told;
    els.density.disabled = els.noHold.disabled = !editable;
    els.density.value = readable ? told?.alienDensity ?? '' : '';
    els.noHold.checked = readable && told?.holdTheLine === 'No';
    els.lwrNote.textContent = `What ${MAP_INFO_SINCE} and later is told of this map. It travels with the map in a map pack (Manage projects, Export map pack).`
      + (landingLines?.kind === 'ew' ? ' Plain Enemy Within reads none of it.' : '')
      + (!readable ? ' This project\'s was written by a newer editor: it is kept as saved, and this editor\'s Build leaves it out.' : '')
      + (!projectsAvailable() ? ' It is set on a map opened from the map browser, not a preview.' : '');
  }
  function commitLwr() {
    const before = projectMapInfo, next = mapInfoRecord(els.density.value, els.noHold.checked, before);
    if (JSON.stringify(next) === JSON.stringify(before)) return;
    gizmo.record({ redo: () => { setProjectMapInfo(next); paintLwr(); },
                   undo: () => { setProjectMapInfo(before); paintLwr(); } });
  }
  els.density.onchange = commitLwr;
  els.noHold.onchange = commitLwr;

  // The preview: every wave of the chosen bed at once, looping, at the volume set (a choice of None plays nothing)
  function stopSound() {
    if (player) for (const audio of player.audios) { audio.pause(); audio.removeAttribute('src'); audio.load(); }
    player = null;
    els.play.textContent = 'Play'; els.play.classList.remove('on');
  }
  function playSound() {
    const cue = els.choice.value, row = (beds ?? []).find(b => b.cue === cue);
    stopSound();
    if (!row) { say(cue ? 'This sound is not one the editor can play here.' : 'None plays nothing.'); return; }
    say('');
    const mine = player = { cue, audios: [] };
    for (let k = 0; k < row.waves.length; k++) {
      const url = `/background-sound.ogg?${new URLSearchParams({ cue, wave: String(k) })}`, audio = new Audio();
      audio.loop = true; audio.volume = previewVolume(Number(els.volume.value));
      audio.addEventListener('error', () => { if (player === mine) failed(url); });
      audio.src = url;
      audio.play().catch(e => { if (player === mine && e.name !== 'AbortError') failed(url, e); });
      mine.audios.push(audio);
    }
    els.play.textContent = 'Stop'; els.play.classList.add('on');
  }
  async function failed(url, error) {
    stopSound();
    let why = error?.name === 'NotAllowedError' ? 'the browser did not let it play' : 'the browser could not decode it';
    try {
      const reply = await fetch(url, { headers: { Range: 'bytes=0-0' } });
      if (!reply.ok) why = (await reply.json().catch(() => null))?.error ?? `the server answered ${reply.status}`;
    } catch { why = 'the server did not answer'; }
    say(`Not played: ${why}`, true);
  }

  els.choice.onchange = () => {
    const playing = Boolean(player);
    // (None plays nothing: its volume goes back to the map's own, so the record is { cue: null } alone)
    if (!els.choice.value) els.volume.value = String(ownVolume(own()));
    commit();
    if (playing) playSound();
  };
  els.volume.oninput = () => {
    els.volumeValue.textContent = volumeWords(Number(els.volume.value));
    if (player) for (const audio of player.audios) audio.volume = previewVolume(Number(els.volume.value));
  };
  els.volume.onchange = () => commit();
  els.play.onclick = () => (player ? stopSound() : playSound());

  async function showMapSettings() {
    if (!data || builderMode || data.scope !== 'map') return;
    showPop(null);
    lastFocus = document.activeElement;
    say('');
    els.choice.replaceChildren();
    els.sound.hidden = false;
    els.root.hidden = false;
    paint(); paintLwr(); paintAtmosphere();
    showAtmosphere();
    if (own()) { await loadBeds(); if (!els.root.hidden) paint(); }
    setTimeout(() => $('mapSettingsDone').focus(), 0);
  }
  function hideMapSettings() {
    stopSound();
    els.root.hidden = true;
    lastFocus?.focus?.();
  }
  els.form.onsubmit = e => { e.preventDefault(); hideMapSettings(); };
  els.close.onclick = hideMapSettings;
  els.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hideMapSettings(); } });
  $('mapSettingsOpen').onclick = showMapSettings;
  $('skyOpen').onclick = showMapSettings;

  // As a map opens (app.js's startScene): the window closed, its preview stopped and its choices made anew
  function startMapSettings() {
    stopSound();
    els.root.hidden = true; lastFocus = null;
    els.choice.replaceChildren();
  }
  // What the browser checks read
  const mapSettingsState = () => ({ open: !els.root.hidden, choices: [...els.choice.options].map(o => ({ value: o.value, label: o.text })),
                                    choice: els.choice.value, volume: Number(els.volume.value), playing: player?.cue ?? null,
                                    note: els.note.textContent, status: els.status.hidden ? '' : els.status.textContent,
                                    lwr: { shown: !els.lwr.hidden, density: els.density.value, noHold: els.noHold.checked,
                                           disabled: els.density.disabled, note: els.lwrNote.textContent,
                                           choices: [...els.density.options].map(o => ({ value: o.value, label: o.text })) },
                                    atmosphere: atmosphereState() });
  return { hideMapSettings, mapSettingsState, showMapSettings, startMapSettings, stopSound };
}
