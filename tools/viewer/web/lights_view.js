// Lights in the editor (private/plans/done/editor-lights-plan.md, 4.6): their markers, the shape of where a selected light
// emits, the outline of the pieces it is baked into, and Solo, which lights the selected lights alone with live
// shadows. The page (app.js) keeps the lights' roots, their edits and the inspector; this module draws.
import * as THREE from 'three';
import { effectiveCone, falloffRadius } from './light_rules.js';
import { linear, toView } from './lighting.js';

// UE3's local light terms in three.js's own lights, for Solo (lighting.js patches the map's materials the same way):
// the radial falloff (1 - (d/R)^2)^F, with three.js's decay carrying F and its distance R, and the spot cone
// square(saturate((cos - cosOuter) / (cosInner - cosOuter))), its penumbra cosine carrying the inner cone's. Before any
// material compiles (this module loads with the page); no other three.js point or spot light is used.
{
  const chunk = THREE.ShaderChunk.lights_pars_begin;
  const distance = /float getDistanceAttenuation\([^)]*\) \{[\s\S]*?\n\}/;
  const spot = /float getSpotAttenuation\([^)]*\) \{[\s\S]*?\n\}/;
  if (!distance.test(chunk) || !spot.test(chunk)) console.warn('three.js light attenuation not found: Solo uses three.js\'s own');
  else THREE.ShaderChunk.lights_pars_begin = chunk
    .replace(distance, 'float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {\n'
      + '\tif ( cutoffDistance <= 0.0 ) return 1.0;\n'
      + '\tfloat r = lightDistance / cutoffDistance;\n'
      + '\treturn pow( saturate( 1.0 - r * r ), decayExponent );\n}')
    .replace(spot, 'float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {\n'
      + '\treturn pow2( saturate( ( angleCosine - coneCosine ) / max( penumbraCosine - coneCosine, 1e-4 ) ) );\n}');
}


// The colour a marker takes: a light's own, grey for one that is view only.
const VIEW_ONLY = new THREE.Color(0x8a959c);
// Marker sizes are a fraction of the camera's distance, so a marker keeps one size on screen.
const MARKER_SCALE = 0.016;

// Marker shapes in the light actor's own frame (its X axis is where it points): a bulb for a point light, a cone with
// its tip at the light for a spot light, a small diamond for an area light.
const geometries = {
  point: new THREE.SphereGeometry(0.55, 12, 8),
  spot: new THREE.ConeGeometry(0.55, 1.3, 14, 1, false).translate(0, -0.65, 0).rotateZ(Math.PI / 2),
  area: new THREE.OctahedronGeometry(0.45),
};
// The view's Y-up basis to the actor's own X-forward one: markers are built about the actor's frame.
const markerShape = kind => geometries[kind] ?? geometries.point;

/** A light record (the export's, game units) with its pose and values now: values in the package's terms (plan 9.1,
 *  colour bytes), as the Map lighting mode and the markers read them. */
export function recordNow(source, values, location, rotation, direction) {
  return { ...source, location, rotation, direction, color: values.color.map(v => v / 255),
           brightness: values.brightness, enabled: values.enabled,
           ...(values.radius != null ? { radius: values.radius, falloffExponent: values.falloffExponent } : {}),
           ...(values.innerConeAngle != null ? { innerConeAngle: values.innerConeAngle, outerConeAngle: values.outerConeAngle } : {}) };
}

/** A light's editable values in the package's terms (plan 9.1) from an export record. */
export function valuesOf(record) {
  const out = { color: (record.color ?? [1, 1, 1]).slice(0, 3).map(v => Math.round(v * 255)), brightness: record.brightness,
                enabled: Boolean(record.enabled) };
  if (record.kind === 'point' || record.kind === 'spot') Object.assign(out, { radius: record.radius, falloffExponent: record.falloffExponent });
  if (record.kind === 'spot') Object.assign(out, { innerConeAngle: record.innerConeAngle, outerConeAngle: record.outerConeAngle });
  return out;
}

/** The marker for a light: drawn plainly where it is in view and faintly through what covers it. */
export function makeMarker(kind) {
  const solid = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const ghost = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.28, depthTest: false, depthWrite: false });
  const geometry = markerShape(kind);
  const marker = new THREE.Group();
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost);
  behind.renderOrder = 6;
  for (const m of [front, behind]) { m.raycast = () => {}; marker.add(m); }
  marker.userData = { front, behind, solid, ghost };
  return marker;
}

/** A marker's colour and fill: the light's colour (grey when view only), hollow (wire) when it is switched off,
 *  brighter when selected. */
export function paintMarker(marker, values, { viewOnly = false, selected = false } = {}) {
  const { solid, ghost } = marker.userData;
  const colour = viewOnly ? VIEW_ONLY.clone() : new THREE.Color().setRGB(...values.color.map(v => v / 255), THREE.SRGBColorSpace);
  if (selected) colour.lerp(new THREE.Color(0xffffff), 0.35);
  for (const m of [solid, ghost]) { m.color.copy(colour); m.wireframe = !values.enabled; }
  ghost.opacity = selected ? 0.55 : 0.28;
}

/** Keep markers one size on screen: called each frame for the visible ones. */
export function scaleMarker(marker, camera, worldPosition) {
  marker.scale.setScalar(Math.max(1e-3, camera.position.distanceTo(worldPosition) * MARKER_SCALE));
}

const lineMaterial = (color, opacity = 0.9, dashed = false) => (dashed
  ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, depthTest: false, dashSize: 12, gapSize: 8 })
  : new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthTest: false }));

/** Where a light emits, at its actor matrix (view basis): a point light's radius, and the fainter sphere where its light
 *  has fallen to 10% (UE3's falloff); a spot light's effective outer cone to its radius with its effective inner cone
 *  inside; both with the line down to `floorY` (viewer Y), or none when null. */
export function emissionShape(record, matrix, floorY = null) {
  const group = new THREE.Group();
  group.renderOrder = 7;
  const colour = new THREE.Color().setRGB(...record.color, THREE.SRGBColorSpace).lerp(new THREE.Color(0xffffff), 0.4);
  if (record.kind === 'spot') {
    const [inner, outer] = effectiveCone(record.innerConeAngle, record.outerConeAngle);
    for (const [angle, opacity] of [[outer, 0.9], [inner, 0.45]]) {
      if (angle <= 1e-3) continue;
      group.add(coneLines(record.radius, angle, colour, opacity));
    }
  } else if (record.kind === 'point') {
    group.add(sphereLines(record.radius, colour, 0.75));
    const tenth = falloffRadius(record.radius, record.falloffExponent, 0.1);
    if (tenth > 1 && tenth < record.radius - 1) group.add(sphereLines(tenth, colour, 0.35));
  }
  group.matrixAutoUpdate = false;
  group.matrix.copy(matrix);
  const holder = new THREE.Group();
  holder.add(group);
  if (floorY != null) {
    const at = new THREE.Vector3().setFromMatrixPosition(matrix);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([at, new THREE.Vector3(at.x, floorY, at.z)]),
                                lineMaterial(colour, 0.8, true));
    line.computeLineDistances(); line.renderOrder = 7;
    holder.add(line);
  }
  return holder;
}

// A wire sphere of three great circles, in the light's frame.
function sphereLines(radius, colour, opacity) {
  const points = [];
  const n = 48;
  for (const plane of [0, 1, 2]) {
    for (let k = 0; k < n; k++) {
      for (const j of [k, k + 1]) {
        const a = (j / n) * Math.PI * 2, c = Math.cos(a) * radius, s = Math.sin(a) * radius;
        points.push(plane === 0 ? new THREE.Vector3(c, s, 0) : plane === 1 ? new THREE.Vector3(c, 0, s) : new THREE.Vector3(0, c, s));
      }
    }
  }
  const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial(colour, opacity));
  lines.renderOrder = 7; lines.raycast = () => {};
  return lines;
}

// A cone of half-angle `angle` along the light frame's X axis (the light's direction in the view basis, where
// actorMatrix maps game X to view X), slant length `radius`: its rim and eight lines from the tip.
function coneLines(radius, angle, colour, opacity) {
  const points = [], n = 40, h = radius * Math.cos(angle), r = radius * Math.sin(angle);
  const rim = a => new THREE.Vector3(h, Math.cos(a) * r, Math.sin(a) * r);
  for (let k = 0; k < n; k++) points.push(rim((k / n) * Math.PI * 2), rim(((k + 1) / n) * Math.PI * 2));
  for (let k = 0; k < 8; k++) points.push(new THREE.Vector3(0, 0, 0), rim((k / 8) * Math.PI * 2));
  const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial(colour, opacity));
  lines.renderOrder = 7; lines.raycast = () => {};
  return lines;
}

// Drag handles on the selected light: its radius, and a spot light's outer and inner cones. Each runs along a curve in
// the view basis, at(value), for values lo..hi (units, or degrees for a cone); the page drags one by finding the value
// whose point comes nearest the pointer on screen (nearestValue). `side` (view basis, unit) is where the handles lean:
// the camera's left (the panel takes the view's right), so they sit at the shapes' left and right edges on screen.
// (an effect's size and a sound's radii: the effects and sounds plan, stage FX5)
const HANDLE_SIZES = { radius: 0.42, outer: 0.38, inner: 0.32, size: 0.42, radiusMax: 0.42, radiusMin: 0.34 };
export const HANDLE_COLOURS = { radius: 0xffffff, outer: 0xffe2a0, inner: 0xc8b88a, hover: 0xffc040, size: 0xffb070,
                                radiusMax: 0x9fd8ff, radiusMin: 0x6fb0e0 };
const HANDLE_RIM = new THREE.MeshBasicMaterial({ color: 0x0d1418, depthTest: false, depthWrite: false, transparent: true });
/** A handle: a dot in its colour (userData.material) on a dark rim, drawn over everything. */
export function makeHandle(key) {
  const handle = new THREE.Group(), r = HANDLE_SIZES[key];
  const dot = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8),
                             new THREE.MeshBasicMaterial({ color: HANDLE_COLOURS[key], depthTest: false, depthWrite: false, transparent: true }));
  const rim = new THREE.Mesh(new THREE.SphereGeometry(r * 1.4, 12, 8), HANDLE_RIM);
  rim.renderOrder = 9; dot.renderOrder = 10;
  for (const m of [rim, dot]) { m.raycast = () => {}; handle.add(m); }
  handle.userData.material = dot.material;
  return handle;
}
export function lightHandles(kind, values, matrix, side) {
  if (values.radius == null) return [];
  const origin = new THREE.Vector3().setFromMatrixPosition(matrix);
  if (kind !== 'spot') {
    const out = side.clone().normalize();
    return [{ key: 'radius', value: values.radius, lo: 1, hi: 16384, log: true, origin,
              at: s => origin.clone().addScaledVector(out, s) }];
  }
  const d = new THREE.Vector3().setFromMatrixColumn(matrix, 0).normalize();
  // across the cone, towards `side` (any square to the axis when the axis runs along it)
  let p = side.clone().addScaledVector(d, -side.dot(d));
  if (p.lengthSq() < 1e-6) p = new THREE.Vector3(0, 1, 0).cross(d);
  if (p.lengthSq() < 1e-6) p = new THREE.Vector3(1, 0, 0).cross(d);
  p.normalize();
  const [inner, outer] = effectiveCone(values.innerConeAngle, values.outerConeAngle).map(v => THREE.MathUtils.radToDeg(v));
  const R = values.radius, rim = sign => deg => {
    const a = THREE.MathUtils.degToRad(deg);
    return origin.clone().addScaledVector(d, R * Math.cos(a)).addScaledVector(p, sign * R * Math.sin(a));
  };
  return [{ key: 'radius', value: R, lo: 1, hi: 16384, log: true, origin, at: s => origin.clone().addScaledVector(d, s) },
          { key: 'outer', value: outer, lo: inner, hi: 89.99, origin, at: rim(1) },
          { key: 'inner', value: inner, lo: 0, hi: Math.min(89, outer), origin, at: rim(-1) }];
}
/** The value of `handle` whose point comes nearest `target` on screen ([x, y]); `project(v)` gives a point's screen
 *  position, or null behind the camera. Samples the range (log steps for a radius), then narrows in around the best. */
export function nearestValue(handle, project, target) {
  const { lo, hi } = handle, n = 480;
  const valueAt = t => (handle.log ? lo * Math.pow(hi / lo, t) : lo + (hi - lo) * t);
  const away = t => { const s = project(handle.at(valueAt(t))); return s ? Math.hypot(s[0] - target[0], s[1] - target[1]) : Infinity; };
  let best = -1, bestD = Infinity;
  for (let k = 0; k < n; k++) { const d = away(k / (n - 1)); if (d < bestD) { bestD = d; best = k; } }
  if (best < 0) return handle.value;
  let a = Math.max(0, best - 1) / (n - 1), b = Math.min(n - 1, best + 1) / (n - 1);
  for (let k = 0; k < 40; k++) {
    const m1 = a + (b - a) / 3, m2 = b - (b - a) / 3;
    if (away(m1) <= away(m2)) b = m2; else a = m1;
  }
  return valueAt((a + b) / 2);
}

/** One merged set of box outlines (instances share materials, so pieces are outlined, not recoloured). */
export function boxLines(boxes, color) {
  const points = [];
  for (const b of boxes) {
    const { min: a, max: z } = b;
    const c = [[a.x, a.y, a.z], [z.x, a.y, a.z], [z.x, z.y, a.z], [a.x, z.y, a.z], [a.x, a.y, z.z], [z.x, a.y, z.z], [z.x, z.y, z.z], [a.x, z.y, z.z]]
      .map(v => new THREE.Vector3(...v));
    for (const [i, j] of [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]) points.push(c[i], c[j]);
  }
  const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial(color, 0.7));
  lines.renderOrder = 5; lines.raycast = () => {};
  return lines;
}

/** Whether a box (view basis) comes within a light's radius of its location (game units): the pieces a light reaches. */
export function boxInReach(box, location, radius) {
  const p = toView(location);
  return box.distanceToPoint(p) <= radius;
}

export const SOLO_MAX = 4;

/** Solo: three.js lights for up to four lights, with live shadows, while the map dims (the page dims it). `records` are
 *  recordNow's. */
export function createSolo(world) {
  const made = [];
  function clear() {
    for (const light of made) { world.remove(light); if (light.target) world.remove(light.target); light.shadow?.map?.dispose(); light.dispose?.(); }
    made.length = 0;
  }
  // The lights are kept while the same kinds stay soloed, and only their values change: adding or taking away a
  // three.js light recompiles every material.
  function show(records) {
    const shown = records.slice(0, SOLO_MAX).filter(r => r.kind === 'point' || r.kind === 'spot');
    if (made.length !== shown.length || made.some((light, k) => light.isSpotLight !== (shown[k].kind === 'spot'))) {
      clear();
      for (const r of shown) {
        const light = r.kind === 'spot' ? new THREE.SpotLight() : new THREE.PointLight();
        if (light.isSpotLight) world.add(light.target);
        light.castShadow = true;
        light.shadow.mapSize.set(1024, 1024);
        light.shadow.bias = -0.0005; light.shadow.normalBias = 1;
        world.add(light);
        made.push(light);
      }
    }
    shown.forEach((r, k) => {
      const light = made[k];
      light.color.setRGB(...linear(r.color), THREE.LinearSRGBColorSpace);
      light.intensity = r.enabled ? r.brightness * Math.PI : 0;
      light.distance = r.radius;
      light.decay = r.falloffExponent;
      light.position.copy(toView(r.location));
      if (light.isSpotLight) {
        const [inner, outer] = effectiveCone(r.innerConeAngle, r.outerConeAngle);
        light.angle = outer; light.penumbra = 1 - inner / outer;
        light.target.position.copy(toView(r.location).add(toView(r.direction)));
        light.target.updateMatrixWorld();
      }
      // A placed light sits in its fixture (a lamp's head, a spot's housing), which would shadow all it lights in a live
      // shadow map: its shadows start past the fixture, 64 units out (the bar's parking-lot lamps stayed dark at 40).
      light.shadow.camera.near = Math.min(64, Math.max(4, r.radius / 4)); light.shadow.camera.far = Math.max(8, r.radius);
      light.shadow.camera.updateProjectionMatrix();
    });
    return made.length;
  }
  return { show, clear, get count() { return made.length; } };
}
