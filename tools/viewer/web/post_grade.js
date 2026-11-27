// The map's bloom and grade as the game draws them (game-likeness plan, C3): the values in effect at a place (the
// world's post-process settings, with the members a volume overrides over them) and the game's sums, read from its
// global shader cache on 27 November 2026. Pure: numbers and GLSL text, no three.js; post_chain.js draws with them.
//
// The game's order (the bloom gather, the DOF and bloom blend, the gamma pass with its colour LUT, the LUT blender):
//   bloom  = blur(average over a quarter-size gather of c * saturate((max(c.r, c.g, c.b) - Bloom_Threshold) / 2))
//            * Bloom_Scale
//   c      = saturate(c + bloom * Bloom_Tint * saturate(2^(-3 * luminance(c)) * Bloom_ScreenBlendThreshold))
//   g      = c ^ (1 / 2.2)                                        (the colour LUT is looked up in gamma space)
//   g      = saturate(g - Scene_Shadows) / Scene_HighLights;  g = max(g, 1e-8) ^ Scene_MidTones
//   g      = g * (1 - Scene_Desaturation) + dot(g, (0.3, 0.59, 0.11) * Scene_Desaturation);  g = g * Scene_Colorize
// and the LUT, stored in eight bits, keeps g between 0 and 1. The display gamma is UE3's 2.2, so the LUT blender's
// last power is 1. The game's scene colour is linear, and so is the page's floating-point target.

/** The members the chain reads, with the classes' defaults (atmosphere_defaults.json's, the same for the world and a
 *  volume): a volume's member it flags but did not save takes these. */
export const POST_DEFAULTS = Object.freeze({
  bEnableBloom: true, Bloom_Scale: 1, Bloom_Threshold: 1, Bloom_Tint: [1, 1, 1, 0], Bloom_ScreenBlendThreshold: 10,
  DOF_BlurBloomKernelSize: 16, bEnableSceneEffect: true, Scene_Shadows: [0, 0, 0], Scene_HighLights: [1, 1, 1],
  Scene_MidTones: [1, 1, 1], Scene_Desaturation: 0, Scene_Colorize: [1, 1, 1],
});

/** The flag that says a volume overrides a member (bEnableBloom's is bOverride_EnableBloom). */
export const overrideFlag = name => (name.startsWith('bEnable') ? `bOverride_${name.slice(1)}` : `bOverride_${name}`);

const inside = (box, point) => [0, 1, 2].every(k => point[k] >= box.min[k] && point[k] <= box.max[k]);

/** The volume in effect at `point` (game axes): the enabled one of the highest priority that holds it (an unbound
 *  volume holds every place), the first listed on a tie; null where none does. */
export function volumeAt(atmosphere, point) {
  let best = null;
  for (const volume of atmosphere?.volumes ?? []) {
    if (!volume.enabled || !volume.settings) continue;
    if (!volume.unbound && !(point && volume.box && inside(volume.box, point))) continue;
    if (!best || Number(volume.priority) > Number(best.priority)) best = volume;
  }
  return best;
}

/** The chain's members in effect at `point`: the world's, each one a volume there flags taken from the volume.
 *  `volume` names the volume (null for the world's own). A map exported before atmospheres has the defaults. */
export function postSettings(atmosphere, point = null) {
  const world = atmosphere?.world?.postProcess ?? {};
  const settings = {};
  for (const [name, fallback] of Object.entries(POST_DEFAULTS)) settings[name] = world[name] ?? fallback;
  const volume = volumeAt(atmosphere, point);
  if (volume) {
    for (const [name, fallback] of Object.entries(POST_DEFAULTS)) {
      if (volume.settings[overrideFlag(name)]) settings[name] = volume.settings[name] ?? fallback;
    }
  }
  settings.volume = volume?.name ?? null;
  return settings;
}

const three = (value, fallback) => [0, 1, 2].map(k => (Array.isArray(value) && Number.isFinite(Number(value[k])) ? Number(value[k]) : fallback));

/** The chain's uniforms' values for a set of settings and the Brightness slider's value (a scale of the scene's
 *  light before the bloom and the grade). */
export function postUniforms(settings, brightness = 1) {
  const s = settings ?? postSettings(null);
  const desaturation = Number(s.Scene_Desaturation) || 0;
  const grade = s.bEnableSceneEffect !== false;
  return {
    brightness: Number(brightness) || 1,
    bloomOn: s.bEnableBloom !== false && Number(s.Bloom_Scale) > 0 ? 1 : 0,
    bloomScale: Number(s.Bloom_Scale) || 0,
    bloomThreshold: Number(s.Bloom_Threshold) || 0,
    bloomTint: three(s.Bloom_Tint, 1),
    bloomScreenBlend: Number(s.Bloom_ScreenBlendThreshold ?? 10),
    bloomKernel: Math.max(1, Number(s.DOF_BlurBloomKernelSize) || 16),
    shadows: grade ? three(s.Scene_Shadows, 0) : [0, 0, 0],
    inverseHighlights: grade ? three(s.Scene_HighLights, 1).map(v => 1 / Math.max(v, 1e-4)) : [1, 1, 1],
    midTones: grade ? three(s.Scene_MidTones, 1) : [1, 1, 1],
    keep: grade ? 1 - desaturation : 1,
    luminance: grade ? [0.3, 0.59, 0.11].map(v => v * desaturation) : [0, 0, 0],
    colorize: grade ? three(s.Scene_Colorize, 1) : [1, 1, 1],
  };
}

const clamp01 = v => Math.min(1, Math.max(0, v));

/** A linear colour of the scene (no bloom) as the game shows it, in display values from 0 to 1: the node test holds
 *  the GLSL's sums to it. */
export function gradePixel(u, rgb) {
  const c = rgb.map(v => clamp01(v * u.brightness));
  let g = c.map(v => Math.pow(v, 1 / 2.2));
  g = g.map((v, k) => Math.pow(Math.max(clamp01(v - u.shadows[k]) * u.inverseHighlights[k], 1e-8), u.midTones[k]));
  const grey = g[0] * u.luminance[0] + g[1] * u.luminance[1] + g[2] * u.luminance[2];
  return g.map((v, k) => clamp01((v * u.keep + grey) * u.colorize[k]));
}

/** The uniforms' declarations (each `grade` and postUniforms' name: three's own chunks have a luminance()) and the grade
 *  as a GLSL function of a linear colour (bloom added before it). */
export const GRADE_GLSL = `uniform vec3 gradeShadows;
uniform vec3 gradeInverseHighlights;
uniform vec3 gradeMidTones;
uniform float gradeKeep;
uniform vec3 gradeLuminance;
uniform vec3 gradeColorize;
vec3 gameGrade( vec3 colour ) {
	vec3 g = pow( clamp( colour, 0.0, 1.0 ), vec3( 1.0 / 2.2 ) );
	g = pow( max( clamp( g - gradeShadows, 0.0, 1.0 ) * gradeInverseHighlights, vec3( 1e-8 ) ), gradeMidTones );
	g = g * gradeKeep + dot( g, gradeLuminance );
	return clamp( g * gradeColorize, 0.0, 1.0 );
}`;

/** A gather tap's weight: how far its brightest channel is over the threshold (the game's bloom gather). */
export const bloomWeight = (rgb, threshold) => clamp01((Math.max(...rgb) - threshold) * 0.5);

/** How much of the bloom a pixel takes: all of it where the scene is dark, less where it is bright already. */
export const bloomShare = (rgb, screenBlend) => clamp01(2 ** (-3 * (0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2])) * screenBlend);
