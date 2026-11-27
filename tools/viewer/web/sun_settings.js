// The Map settings window's Sun, moon and sky section (the game-likeness plan, T-S1; design 3A, chosen 27 November
// 2026: a bar and a dial): the map's time of day as the project sets it (the project's `sun`, schema 10).
// - The time bar, 0:00 to 24:00, tinted with the light's colour at each hour, marked where the sun comes up and goes
//   down; its knob at the time shown (the map's best time until it is moved: nothing changes there). Dragging it sets
//   the sun or moon's height, side, colour and brightness, the sky light's, and the fog's colours, tint and shadows of
//   the hour together; the view follows as it moves; one undo step a drag. Arrow keys move it a few minutes, an hour
//   with Shift, a step each.
// - The dial: the side the light stands at its highest (N is the game's +X, E its +Y), dragged round in the Snap
//   setting's turn steps; a small mark on its rim for the way the view looks, a dot for where the light is now.
// - The line under it: "07:10 · dawn" and the light in words.
// - More, folded: the light's and the sky light's colour and strength (set by hand they leave the curve, marked custom),
//   the game's time of day (follows the light, Day, Night), the fog and colour of the hour (which members the time set,
//   which were changed by hand in the Fog and colour section and left alone), the map's own lights listed (#skyList,
//   lights_wiring.js's buildLights fills it) and As the map has it.
// The rules are sun_rules.js's; a change is made through sun_wiring.js (previewSun, endSunEdit, commitSun), which keeps
// the view and the marker in step. map_settings.js makes the section with the window.
import { compass, clock, gameTime, handSet, lightWords, partOfDay, phaseAt, sideAt, timeMarks, asTheMapHasIt, validSun,
         barColours, DAY } from './sun_rules.js';
import { colourHex, hexColour } from './atmosphere_rules.js';
import { data, projectAtmosphere, projectSun, snapMode } from './editor_state.js';
import { segmented } from './dom_words.js';
import { stepped, stepsOf } from './snap_steps.js';

const WORDS = { 'fog.LightInscatteringColor': 'the fog toward the light', 'fog.OppositeLightColor': 'the fog away from it',
                'postProcess.Scene_Colorize': 'the tint', 'postProcess.Scene_Shadows': 'the shadows' };
const CUSTOM_WORDS = { color: 'colour', brightness: 'strength', skyColor: 'sky colour', skyBrightness: 'sky strength' };

export function createSunSettings({ $, camera, projectsAvailable, sun }) {
  const { beginSunEdit, commitSun, endSunEdit, previewSun, previewSunRecord, sunCurve, sunOwn, sunShown } = sun;
  const els = { note: $('mapSunNote'), bar: $('mapTimeBar'), colours: $('mapTimeColours'), knob: $('mapTimeKnob'),
                dial: $('mapSunDial'), time: $('mapSunTime'), words: $('mapSunWords'), side: $('mapSunSide'),
                fold: $('mapSunFold'), colour: $('mapSunColour'), strength: $('mapSunStrength'), strengthOut: $('mapSunStrengthOut'),
                skyRow: $('mapSkyRows'), skyNone: $('mapSkyNone'), skyColour: $('mapSkyColour'), skyStrength: $('mapSkyStrength'),
                skyStrengthOut: $('mapSkyStrengthOut'), gameTime: $('mapSunGameTime'), hour: $('mapSunHour'),
                reset: $('mapSunReset'), controls: $('mapSunControls') };
  const chips = { color: $('mapSunColourCustom'), brightness: $('mapSunStrengthCustom'), skyColor: $('mapSkyColourCustom'),
                  skyBrightness: $('mapSkyStrengthCustom') };
  let barDrag = null, dialDrag = null, paintedCurve = null, slideFrom = null;
  const curve = () => sunCurve(), own = () => sunOwn();
  const editable = () => Boolean(curve()) && projectsAvailable();
  const record = () => (validSun(projectSun, curve()) ? projectSun : null);

  // ------------------------------------------------------------------------------------------------ the bar
  function paintBar() {
    const c = curve();
    if (!c || paintedCurve === c) return;
    paintedCurve = c;
    const canvas = els.colours, width = canvas.width = 480, height = canvas.height = 24, g = canvas.getContext('2d');
    barColours(c, width).forEach((css, x) => { g.fillStyle = css; g.fillRect(x, 0, 1, height); });
    // where the light changes: the sun coming up and going down
    g.fillStyle = 'rgba(255, 255, 255, 0.55)';
    for (const change of c.changes) g.fillRect(Math.round(change.time / DAY * width), 0, 1, height);
  }
  const timeAt = clientX => {
    const r = els.bar.getBoundingClientRect();
    return Math.round(Math.min(DAY * 60 - 1, Math.max(0, (clientX - r.left) / r.width * DAY * 60))) / 60;
  };
  els.bar.addEventListener('pointerdown', e => {
    if (e.button !== 0 || !editable()) return;
    e.preventDefault();
    els.bar.setPointerCapture(e.pointerId); els.bar.focus();
    barDrag = { pointerId: e.pointerId, heading: sunShown().heading };
    beginSunEdit();
    previewSun({ time: timeAt(e.clientX), heading: barDrag.heading });
  });
  els.bar.addEventListener('pointermove', e => {
    if (barDrag && e.pointerId === barDrag.pointerId) previewSun({ time: timeAt(e.clientX), heading: barDrag.heading });
  });
  const endBar = keep => {
    if (!barDrag) return;
    try { els.bar.releasePointerCapture(barDrag.pointerId); } catch { /* already released */ }
    barDrag = null;
    endSunEdit(keep);
  };
  els.bar.addEventListener('pointerup', e => { if (barDrag && e.pointerId === barDrag.pointerId) endBar(true); });
  els.bar.addEventListener('pointercancel', () => endBar(false));
  // a key: a few minutes (an hour with Shift), one step each; Escape during a drag puts it back (the window stays)
  els.bar.addEventListener('keydown', e => {
    if (e.key === 'Escape' && barDrag) { e.preventDefault(); e.stopPropagation(); endBar(false); return; }
    const by = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[e.key];
    if (!by || !editable()) return;
    e.preventDefault();
    const at = sunShown(), minutes = by * (e.shiftKey ? 60 : 5);
    previewSun({ time: ((Math.round(at.time * 60) + minutes) % 1440 + 1440) % 1440 / 60, heading: at.heading });
    endSunEdit(true);
  });

  // ------------------------------------------------------------------------------------------------ the dial
  const SVG = 'http://www.w3.org/2000/svg';
  const svg = (name, attrs, parent = els.dial) => {
    const el = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    parent.append(el);
    return el;
  };
  // (made once: the rim, the four points, the view's mark, the heading's hand and the light's dot)
  svg('circle', { r: 27, class: 'dialrim' });
  for (const [label, deg] of [['N', 0], ['E', 90], ['S', 180], ['W', 270]]) {
    const a = deg * Math.PI / 180;
    const t = svg('text', { x: (Math.sin(a) * 20).toFixed(1), y: (-Math.cos(a) * 20 + 3).toFixed(1), class: 'dialpoint' });
    t.textContent = label;
  }
  const viewMark = svg('path', { d: 'M -4 -31 L 4 -31 L 0 -26 Z', class: 'dialview' });
  const hand = svg('line', { x1: 0, y1: 0, x2: 0, y2: -24, class: 'dialhand' });
  const dot = svg('circle', { r: 3.5, class: 'dialdot' });
  const angleAt = (clientX, clientY) => {
    const r = els.dial.getBoundingClientRect();
    return ((Math.atan2(clientX - (r.left + r.width / 2), -(clientY - (r.top + r.height / 2))) * 180 / Math.PI) + 360) % 360;
  };
  const wrap = deg => ((deg % 360) + 360) % 360;
  const dialHeading = (drag, clientX, clientY) => wrap(drag.from + stepped(wrap(angleAt(clientX, clientY) - drag.angle + 180) - 180, stepsOf(snapMode).turn));
  els.dial.addEventListener('pointerdown', e => {
    if (e.button !== 0 || !editable()) return;
    e.preventDefault();
    els.dial.setPointerCapture(e.pointerId); els.dial.focus();
    const at = sunShown();
    dialDrag = { pointerId: e.pointerId, from: at.heading, angle: angleAt(e.clientX, e.clientY), time: at.time };
    beginSunEdit();
  });
  els.dial.addEventListener('pointermove', e => {
    if (dialDrag && e.pointerId === dialDrag.pointerId) previewSun({ time: dialDrag.time, heading: dialHeading(dialDrag, e.clientX, e.clientY) });
  });
  const endDial = keep => {
    if (!dialDrag) return;
    try { els.dial.releasePointerCapture(dialDrag.pointerId); } catch { /* already released */ }
    dialDrag = null;
    endSunEdit(keep);
  };
  els.dial.addEventListener('pointerup', e => { if (dialDrag && e.pointerId === dialDrag.pointerId) endDial(true); });
  els.dial.addEventListener('pointercancel', () => endDial(false));
  els.dial.addEventListener('keydown', e => {
    if (e.key === 'Escape' && dialDrag) { e.preventDefault(); e.stopPropagation(); endDial(false); return; }
    const by = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[e.key];
    if (!by || !editable()) return;
    e.preventDefault();
    const at = sunShown();
    previewSun({ time: at.time, heading: wrap(at.heading + by * (stepsOf(snapMode).turn || 5)) });
    endSunEdit(true);
  });

  // ------------------------------------------------------------------------------------------------ More
  segmented(els.gameTime, () => commitSun({ sun: handSet({ curve: curve(), own: own(), before: projectSun, atmosphere: projectAtmosphere,
                                                                 key: 'timeOfDay', value: els.gameTime.value }), atmosphere: projectAtmosphere }));
  const byHand = (key, value) => handSet({ curve: curve(), own: own(), before: slideFrom ?? projectSun, atmosphere: projectAtmosphere, key, value });
  // a colour: one step on its change, the view following while it is picked; a strength: one step on its release
  for (const [el, key, out] of [[els.colour, 'color'], [els.skyColour, 'skyColor'], [els.strength, 'brightness', els.strengthOut],
                                [els.skyStrength, 'skyBrightness', els.skyStrengthOut]]) {
    const value = () => (el.type === 'color' ? hexColour(el.value).slice(0, 3).map(v => Math.round(v * 255)) : Number(el.value));
    el.oninput = () => {
      if (out) out.textContent = String(Number(el.value));
      slideFrom ??= projectSun;
      previewSunRecord(byHand(key, value()));
    };
    el.onchange = () => { slideFrom = null; endSunEdit(true); };
  }
  els.reset.onclick = () => commitSun(asTheMapHasIt(projectSun, projectAtmosphere, own()));

  // ------------------------------------------------------------------------------------------------ painted
  /** The section as the project has it now. */
  function paint() {
    const c = curve(), mine = own();
    els.controls.hidden = !mine || !c;
    if (!mine) {
      els.note.textContent = data?.lights ? 'This map has no sun or moon, so it has no time of day to set.'
        : 'This export lists none of the map\'s lights: open the map again to export it anew.';
      return;
    }
    if (!c) { els.note.textContent = 'The time of day\'s curve can\'t be had: the editor\'s server did not give it.'; return; }
    paintBar();
    const can = editable(), r = record(), at = sunShown(), light = r?.light ?? { rotation: mine.rotation, color: mine.color, brightness: mine.brightness };
    els.note.textContent = 'Drag the bar for the time of day: the sun or moon, the sky light and the fog and colour of the hour, '
      + 'seen in the Game look (K). The Build does not write it into the map yet.'
      + (projectsAvailable() ? '' : ' It is set on a map opened from the map browser, not a preview.');
    for (const el of [els.colour, els.strength, els.skyColour, els.skyStrength, els.reset, ...els.gameTime.querySelectorAll('button')]) el.disabled = !can;
    els.bar.setAttribute('aria-disabled', String(!can)); els.dial.setAttribute('aria-disabled', String(!can));
    els.bar.classList.toggle('changed', Boolean(r));
    // the bar's knob and the words
    els.knob.style.left = `${at.time / DAY * 100}%`;
    els.bar.setAttribute('aria-valuenow', String(Math.round(at.time * 60)));
    els.bar.setAttribute('aria-valuetext', clock(at.time));
    const custom = (r?.custom ?? []).map(k => CUSTOM_WORDS[k]);
    els.time.textContent = `${clock(at.time)} · ${partOfDay(c, at.time)}${r ? '' : ' (the map\'s own)'}`;
    els.words.textContent = lightWords(c, { time: at.time, light }) + (custom.length ? ` · ${custom.join(', ')} set by hand` : '');
    const turned = r && (r.light.rotation[0] !== mine.rotation[0] || r.light.rotation[1] !== mine.rotation[1]);
    els.side.hidden = !turned;
    // the dial: the heading's hand, the light's side now, the way the view looks
    const turn = (el, deg) => el.setAttribute('transform', `rotate(${deg.toFixed(2)})`);
    turn(hand, at.heading);
    const side = sideAt(c, at.time, at.heading) * Math.PI / 180;
    dot.setAttribute('cx', (Math.sin(side) * 24).toFixed(2)); dot.setAttribute('cy', (-Math.cos(side) * 24).toFixed(2));
    dot.style.fill = `rgb(${light.color.join(', ')})`;
    const look = camera.getWorldDirection(camera.position.clone());      // (the view's x and z are the game's x and y)
    turn(viewMark, (Math.atan2(look.z, look.x) * 180 / Math.PI + 360) % 360);
    els.dial.setAttribute('aria-valuenow', String(Math.round(at.heading)));
    els.dial.setAttribute('aria-valuetext', `${Math.round(at.heading)}°, ${compass(at.heading)}`);
    els.dial.title = `The side the ${phaseAt(c, at.time).light} stands at its highest: ${compass(at.heading)} (${Math.round(at.heading)}°; N is the map's X axis). `
      + 'Drag it round, in the Snap setting\'s turns; the arrow keys turn it. One undo step';
    // More: the values as they are, which are set by hand, the game's time, the fog and colour of the hour
    els.colour.value = colourHex(light.color.map(v => v / 255));
    els.strength.value = String(light.brightness); els.strengthOut.textContent = String(Math.round(light.brightness * 100) / 100);
    els.skyRow.hidden = !mine.sky; els.skyNone.hidden = Boolean(mine.sky);
    const sky = r?.sky ?? mine.sky;
    if (sky) {
      els.skyColour.value = colourHex(sky.color.map(v => v / 255));
      els.skyStrength.value = String(sky.brightness); els.skyStrengthOut.textContent = String(Math.round(sky.brightness * 100) / 100);
    }
    for (const [key, chip] of Object.entries(chips)) chip.hidden = !(r?.custom ?? []).includes(key);
    els.gameTime.value = r?.timeOfDay ?? 'auto';
    const auto = els.gameTime.querySelector('[data-value="auto"]');
    auto.textContent = `Follows the light (${gameTime({ timeOfDay: 'auto', time: at.time }, c)})`;
    els.hour.textContent = hourWords(r);
  }
  // The fog and colour of the hour in words: what the time set, what was changed by hand and left alone
  function hourWords(r) {
    if (!data?.atmosphere) return 'Fog and colour of the hour: this export says nothing of the map\'s fog and colour; open the map again to export it anew.';
    if (!r) return 'Fog and colour of the hour: the bar sets the fog\'s colours, the tint and the shadows with the light.';
    const marks = timeMarks(r, projectAtmosphere);
    const set = Object.keys(marks).filter(k => marks[k] === 'time').map(k => WORDS[k]);
    const custom = Object.keys(marks).filter(k => marks[k] === 'custom').map(k => WORDS[k]);
    return `Fog and colour of the hour: ${set.length ? `${set.join(', ')} set by the time` : 'the map\'s own'}`
      + (custom.length ? `; ${custom.join(', ')} changed in Fog and colour, kept (custom)` : '') + '.';
  }

  /** What the browser checks read. */
  const sunSettingsState = () => ({ time: els.time.textContent, words: els.words.textContent, knob: parseFloat(els.knob.style.left),
                                    hour: els.hour.textContent, note: els.note.textContent, gameTime: els.gameTime.value,
                                    custom: Object.keys(chips).filter(k => !chips[k].hidden), turned: !els.side.hidden,
                                    shown: !els.controls.hidden });
  return { paintSun: paint, sunSettingsState };
}
