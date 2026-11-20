// Shared light rules for the page (editor lights plan, section 9.2). effectiveCone is the twin of
// lights.effective_cone in tools/viewer/lights.py; both are tested against tests/cone_cases.json.

const RAD = Math.PI / 180;
/** The limits of a light's values an edit may set (compiler.py LIGHT_RANGES; pinned in tests/twin_constants.json,
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
