// The map's fog and colour as a project changes them (game-likeness plan, C5b): the project's `atmosphere` (schema
// 10), {fog?: {member: value}, postProcess?: {member: value}}, only the members it changes of the map's height fog and
// its post-process settings, in the export's form (tools/viewer/atmosphere.py). Pure: the map's values with the
// project's over them, the record tidied to what differs, a look of another map taken, the words and the swatch the
// Map settings window shows. The compiler holds each value to its member's kind (tools/editor/atmosphere_edits.py).
import { fogUniforms } from './atmosphere_shader.js';
import { gradePixel, postSettings, postUniforms } from './post_grade.js';

export const SECTIONS = ['fog', 'postProcess'];

/** The values the window's folds edit, with their sliders' ranges (the rest a look of another map brings). */
export const FOG_SLIDERS = [
  { key: 'FogDensity', label: 'Density', min: 0, max: 0.5, step: 0.005 },
  { key: 'FogHeight', label: 'Height', min: -1000, max: 4000, step: 50 },
  { key: 'FogHeightFalloff', label: 'Falloff', min: 0, max: 20, step: 0.5 },
];
export const COLOUR_SLIDERS = [
  { key: 'Scene_Desaturation', label: 'Grey', min: 0, max: 1, step: 0.05 },
  { key: 'Bloom_Scale', label: 'Bloom', min: 0, max: 2, step: 0.05 },
];
/** The shadows' lift, one slider for the three channels: the game subtracts Scene_Shadows in gamma space, so a lift L
 *  is (-L, -L, -L). */
export const LIFT = { label: 'Shadows', min: -0.1, max: 0.1, step: 0.005 };
/** The tint's strength (Scene_Colorize's largest channel; its colour is the three over it). */
export const STRENGTH = { label: 'Strength', min: 0.5, max: 2, step: 0.05 };

const isPlain = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const isValue = v => (typeof v === 'number' && Number.isFinite(v)) || typeof v === 'boolean' || typeof v === 'string'
  || (Array.isArray(v) && v.length >= 3 && v.length <= 4 && v.every(n => typeof n === 'number' && Number.isFinite(n)));

/** Whether a record is one the page reads: sections of plain values. */
export function validAtmosphere(record) {
  return isPlain(record) && Object.keys(record).every(k => SECTIONS.includes(k))
    && SECTIONS.every(k => record[k] === undefined || (isPlain(record[k]) && Object.values(record[k]).every(isValue)));
}

const round = v => (typeof v === 'number' ? Math.round(v * 1e6) / 1e6 : Array.isArray(v) ? v.map(round) : v);
const same = (a, b) => (Array.isArray(a) && Array.isArray(b) ? a.length === b.length && a.every((v, k) => Math.abs(v - b[k]) < 1e-6)
  : typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-6 : a === b);

/** The record a project saves: only the members whose value differs from the map's own, rounded; null when nothing
 *  does (the map's own fog and colour). A record the page can't read is carried as it is. */
export function tidyAtmosphere(record, map) {
  if (record == null) return null;
  if (!validAtmosphere(record)) return isPlain(record) ? { ...record } : null;
  const out = {};
  for (const key of SECTIONS) {
    const own = map?.world?.[key] ?? {};
    for (const [name, value] of Object.entries(record[key] ?? {})) {
      if (own[name] !== undefined && same(own[name], value)) continue;
      (out[key] ??= {})[name] = round(value);
    }
  }
  return Object.keys(out).length ? out : null;
}

/** The map's atmosphere (the export's) with the project's members over its world settings: a new object, its volumes
 *  the map's; the map's own where the project changes nothing. */
export function atmosphereWith(map, record) {
  if (!map || !validAtmosphere(record) || !record) return map;
  const world = map.world ?? {};
  return { ...map, world: { ...world, fog: { ...(world.fog ?? {}), ...(record.fog ?? {}) },
                            postProcess: { ...(world.postProcess ?? {}), ...(record.postProcess ?? {}) } } };
}

/** The record that gives the map another map's look (an entry of /atmospheres.json's looks): its fog and grade where
 *  they differ from the map's own. */
export function lookRecord(look, map) {
  return tidyAtmosphere({ fog: { ...(look?.fog ?? {}) }, postProcess: { ...(look?.postProcess ?? {}) } }, map);
}

/** The project's record with one member set (a slider, a colour, the fog's tick), tidied against the map. */
export function withMember(record, map, key, name, value) {
  const next = { fog: { ...(record?.fog ?? {}) }, postProcess: { ...(record?.postProcess ?? {}) } };
  next[key][name] = value;
  return tidyAtmosphere(next, map);
}

const fixed = (v, digits = 3) => String(Math.round(Number(v) * 10 ** digits) / 10 ** digits);

/** The fog's values in words: "on, density 0.02, height 1000" or "off". */
export function fogWords(fog = {}) {
  if (!fog.bEnabled) return 'off';
  return `on, density ${fixed(fog.FogDensity ?? 0)}, height ${fixed(fog.FogHeight ?? 0, 0)}`;
}
/** The colour's values in words: "tint 1.2, 1.2, 1.2 · bloom 0.5", with the grey where there is some. */
export function colourWords(post = {}) {
  const tint = (post.Scene_Colorize ?? [1, 1, 1]).map(v => fixed(v, 2)).join(', ');
  const grey = Number(post.Scene_Desaturation) > 0 ? ` · grey ${fixed(post.Scene_Desaturation, 2)}` : '';
  return `tint ${tint}${grey} · bloom ${fixed(post.bEnableBloom === false ? 0 : post.Bloom_Scale ?? 1, 2)}`;
}

// colours: a Color member (four numbers from 0 to 1) and the colour picker's #rrggbb
const hex2 = v => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, '0');
export const colourHex = c => `#${hex2(c?.[0] ?? 0)}${hex2(c?.[1] ?? 0)}${hex2(c?.[2] ?? 0)}`;
export const hexColour = (hex, alpha = 1) => [1, 3, 5].map(k => parseInt(hex.slice(k, k + 2), 16) / 255).concat([alpha]);
/** Scene_Colorize as the picker shows it: its colour (the channels over the largest) and its strength (the largest). */
export function tintParts(colorize = [1, 1, 1]) {
  const strength = Math.max(1e-3, ...colorize);
  return { hex: colourHex(colorize.map(v => v / strength)), strength };
}
export const tintOf = (hex, strength) => hexColour(hex).slice(0, 3).map(v => Math.round(v * strength * 1000) / 1000);
/** The shadows' lift a Scene_Shadows says (the mean of the three, turned: the game subtracts it). */
export const liftOf = shadows => -((shadows?.[0] ?? 0) + (shadows?.[1] ?? 0) + (shadows?.[2] ?? 0)) / 3;

/** A look's swatch: three display colours, top to bottom (the fog far away, a floor half way, a floor near), worked out
 *  as the Game look would show a grey floor under the look's moonlight-less light: its fog's colours and its grade. */
export function lookSwatch(look) {
  const world = { fog: look?.fog ?? {}, postProcess: look?.postProcess ?? {} };
  const fog = fogUniforms(world.fog, [0, 0, -1]);
  const far = fog.fogOn ? fog.fogOpposite.map((v, k) => (v + fog.fogInscatter[k]) / 2) : [0.02, 0.02, 0.03];
  const u = postUniforms(postSettings({ world }));
  const mix = (ground, t) => far.map((f, k) => ground * t + f * (1 - t));
  const css = rgb => `rgb(${gradePixel(u, rgb).map(v => Math.round(v * 255)).join(', ')})`;
  return [css(mix(0, 0)), css(mix(0.05, fog.fogOn ? 0.55 : 1)), css(mix(0.12, fog.fogOn ? 0.85 : 1))];
}

const parse = css => css.match(/\d+/g).map(Number);
const distance = (a, b) => Math.hypot(...a.map((v, k) => v - b[k]));
/** `n` looks spread apart (by their swatches' middle and near colours), none like the map's own: the window's row. */
export function spreadPicks(looks, ownLook, n = 4) {
  const key = look => lookSwatch(look).slice(1).flatMap(parse);
  const chosen = [key(ownLook)], picks = [];
  const pool = looks.map(look => ({ look, key: key(look) }));
  while (picks.length < n && pool.length) {
    let best = 0, bestScore = -1;
    pool.forEach((c, i) => { const score = Math.min(...chosen.map(k => distance(k, c.key))); if (score > bestScore) { bestScore = score; best = i; } });
    const [c] = pool.splice(best, 1);
    if (bestScore < 1) break;          // (nothing left that looks different)
    picks.push(c.look); chosen.push(c.key);
  }
  return picks;
}

/** A look's name: its first map's label and time ("Urban Bar (night)"), and how many maps share it. */
export function lookName(look) {
  const first = look?.maps?.[0];
  if (!first) return 'A look';
  const time = (first.time ?? []).filter(t => t !== 'None').map(t => t.toLowerCase()).join(' and ');
  return `${first.label}${time ? ` (${time})` : ''}${look.maps.length > 1 ? ` and ${look.maps.length - 1} more` : ''}`;
}

/** The map's post-process volumes that set its colour where the camera is inside them, in words (read only: the
 *  editor does not change a volume): [{ name, words }]. */
export function gradeVolumes(map) {
  const flag = name => (name.startsWith('bEnable') ? `bOverride_${name.slice(1)}` : `bOverride_${name}`);
  const members = ['Scene_Colorize', 'Scene_Shadows', 'Scene_Desaturation', 'Scene_HighLights', 'Scene_MidTones', 'Bloom_Scale', 'bEnableBloom'];
  return (map?.volumes ?? []).filter(v => v.enabled !== false && members.some(m => v.settings?.[flag(m)]))
    .map(v => {
      const set = Object.fromEntries(members.filter(m => v.settings?.[flag(m)]).map(m => [m, v.settings[m]]));
      const words = [set.Scene_Colorize && `tint ${set.Scene_Colorize.map(x => fixed(x, 2)).join(', ')}`,
                     set.Scene_Desaturation !== undefined && `grey ${fixed(set.Scene_Desaturation, 2)}`,
                     set.Scene_Shadows && `shadows ${fixed(liftOf(set.Scene_Shadows), 3)}`,
                     set.Bloom_Scale !== undefined && `bloom ${fixed(set.Bloom_Scale, 2)}`].filter(Boolean).join(' · ');
      return { name: v.name, words: words || 'its own colour' };
    });
}

/** The map's post-process volumes that set members the project changes: [{ name, members }] (where the camera is in
 *  one, the game shows the volume's value). */
export function volumesOver(map, record) {
  const changed = Object.keys(record?.postProcess ?? {});
  const flag = name => (name.startsWith('bEnable') ? `bOverride_${name.slice(1)}` : `bOverride_${name}`);
  return (map?.volumes ?? []).filter(v => v.enabled !== false)
    .map(v => ({ name: v.name, members: changed.filter(name => v.settings?.[flag(name)]) }))
    .filter(v => v.members.length);
}
