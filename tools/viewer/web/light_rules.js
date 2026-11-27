// Shared light rules for the page (editor lights plan, section 9.2). effectiveCone is the twin of
// lights.effective_cone in tools/viewer/lights.py; both are tested against tests/cone_cases.json.

const RAD = Math.PI / 180;
/** The limits of a light's values an edit may set (light_edits.py LIGHT_RANGES; pinned in tests/twin_constants.json,
 *  review finding 55). */
export const LIGHT_LIMITS = { brightness: [0, 100], radius: [1, 16384], falloffExponent: [0.1, 64], innerConeAngle: [0, 89], outerConeAngle: [0, 89.99] };
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

/** A spot light's effective inner and outer cone half-angles in radians, from its stored degrees: UE3 clamps the
 * inner cone to 0..89 degrees and the outer cone to just above the inner one and below 90. */
export function effectiveCone(inner, outer) {
  const i = clamp(Number(inner), 0, 89) * RAD;
  const o = clamp(Number(outer) * RAD, i + 0.001, 89.99 * RAD);
  return [i, o];
}

/** effectiveCone in degrees. */
export function effectiveConeDegrees(inner, outer) {
  return effectiveCone(inner, outer).map(v => v / RAD);
}

/** A spot light's [inner, outer] cone in degrees as a light the Build makes may hold it (inner 0 to 89, outer 0 to
 * 89.99, inner no wider than outer), lighting as the stored cone does: the stored values when they are in range, else
 * the effective cone (a map's stored 100 or 580 lights as 89.99). Twin of lights.storable_cone. */
export function storableCone(inner, outer) {
  inner = Number(inner); outer = Number(outer);
  if (inner >= 0 && inner <= 89 && inner <= outer && outer <= 89.99) return [inner, outer];
  const round4 = v => Math.round(v * 1e4) / 1e4;
  const [i0, o0] = effectiveConeDegrees(inner, outer);
  const i = Math.min(round4(i0), 89);
  return [i, Math.min(Math.max(round4(o0), i), 89.99)];
}

/** Where a light's falloff (1 - (d/R)^2)^F has fallen to `fraction` of its peak: R * sqrt(1 - fraction^(1/F)). */
export function falloffRadius(radius, exponent, fraction = 0.1) {
  if (!(exponent > 0)) return radius;
  return radius * Math.sqrt(Math.max(0, 1 - Math.pow(fraction, 1 / exponent)));
}

/** The light at a place for a surface facing `normal` (game-likeness plan, E2: a lit particle's material, which the
 *  game lights by its light environment there): [r, g, b], linear, as a diffuse colour is multiplied by. `state`:
 *  { sky, ground: [r, g, b] (the sky light's upper and lower colours, each by its brightness), sun: [r, g, b] (by its
 *  brightness), toSun: a unit vector toward it, up: the unit vector up, locals: [{ position, radius, colour (by its
 *  brightness), falloff, direction (a spot's, the way it shines), cosOuter (-2: a point light), coneScale }] }. The sky
 *  as three's hemisphere light gives it (ground to sky by the normal's height), the sun and each light by the cosine to
 *  it and UE3's falloff (1 - (d/R)^2)^F and cone (lighting.js' shader); no shadow. Vectors in any one set of axes. */
export function lightAt(state, at, normal) {
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const out = [0, 0, 0], up = state.up ?? [0, 1, 0];
  const h = 0.5 * dot(normal, up) + 0.5;
  for (let k = 0; k < 3; k++) out[k] += (state.ground?.[k] ?? 0) * (1 - h) + (state.sky?.[k] ?? 0) * h;
  if (state.sun && state.toSun) {
    const c = Math.max(0, dot(normal, state.toSun));
    for (let k = 0; k < 3; k++) out[k] += state.sun[k] * c;
  }
  for (const l of state.locals ?? []) {
    const d = [l.position[0] - at[0], l.position[1] - at[1], l.position[2] - at[2]];
    const d2 = dot(d, d) / (l.radius * l.radius);
    if (!(d2 < 1)) continue;
    const n = Math.sqrt(dot(d, d)) || 1, w = d.map(v => v / n);
    let att = Math.pow(1 - d2, l.falloff);
    if (l.cosOuter > -1.5) {
      const cone = clamp((-dot(w, l.direction) - l.cosOuter) * l.coneScale, 0, 1);
      att *= cone * cone;
    }
    const c = Math.max(0, dot(normal, w)) * att;
    for (let k = 0; k < 3; k++) out[k] += l.colour[k] * c;
  }
  return out;
}
