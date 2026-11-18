// The Effects view's drawing (private/plans/done/effects-and-sounds-plan.md, Part B, stage FX1): a marker for each
// effect, sound and lens flare, one size on screen and drawn over everything (a spark, a speaker, a star), the picked
// effect's fixed box and a picked sound's two spheres. What the markers say is effects_rules.js's; app.js keeps the
// view, the picking and the panel.
import * as THREE from 'three';

export const COLOURS = { effect: 0xffa94d, sound: 0x4dd0e1, flare: 0xfff1a8 };
const PICKED = new THREE.Color(0xffffff), DIM = new THREE.Color(0x7d8a92);
const SIZE = 0.034, PICKED_SIZE = 0.046;       // of the view's height (sizeAttenuation off)
const icons = new Map();

// An icon drawn white on a dark rim (the material's colour tints it): a spark (rays round a dot) for an effect, a
// speaker for a sound, a four-pointed star for a flare. Hollow: outline only (one that starts off).
function icon(kind, hollow) {
  const key = `${kind}|${hollow}`;
  if (icons.has(key)) return icons.get(key);
  const n = 64, canvas = document.createElement('canvas');
  canvas.width = canvas.height = n;
  const g = canvas.getContext('2d');
  g.translate(n / 2, n / 2); g.lineJoin = 'round'; g.lineCap = 'round';
  const shape = () => {
    g.beginPath();
    if (kind === 'effect') {
      for (let k = 0; k < 8; k++) {
        const a = (k / 8) * Math.PI * 2, r0 = 9, r1 = k % 2 ? 19 : 26;
        g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); g.lineTo(Math.cos(a) * r1, Math.sin(a) * r1);
      }
      g.moveTo(7, 0); g.arc(0, 0, 7, 0, Math.PI * 2);
    } else if (kind === 'sound') {
      g.moveTo(-22, -7); g.lineTo(-12, -7); g.lineTo(0, -18); g.lineTo(0, 18); g.lineTo(-12, 7); g.lineTo(-22, 7); g.closePath();
      g.moveTo(8, -9); g.arc(2, 0, 11, -0.95, 0.95);
      g.moveTo(14, -16); g.arc(3, 0, 20, -0.95, 0.95);
    } else {
      const pts = [[0, -27], [5, -5], [27, 0], [5, 5], [0, 27], [-5, 5], [-27, 0], [-5, -5]];
      pts.forEach(([x, y], k) => (k ? g.lineTo(x, y) : g.moveTo(x, y)));
      g.closePath();
    }
  };
  const filled = !hollow && kind !== 'effect';
  shape(); g.strokeStyle = 'rgba(10,16,20,0.9)'; g.lineWidth = 10; g.stroke();
  if (filled) { g.fillStyle = 'rgba(10,16,20,0.9)'; g.fill(); }
  shape(); g.strokeStyle = '#fff'; g.lineWidth = hollow ? 3 : 4.5; g.stroke();
  if (filled) { g.fillStyle = '#fff'; g.fill(); }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  icons.set(key, texture);
  return texture;
}

/** The marker's icon drawn into a 2D canvas (a row of the Add panel's All maps: stage FX4), in its kind's colour on
 *  the row's dark ground. */
export function drawEffectIcon(kind, hollow, canvas) {
  const image = icon(kind, hollow).image, g = canvas.getContext('2d'), n = canvas.width, pad = n * 0.16;
  g.clearRect(0, 0, n, n);
  g.drawImage(image, pad, pad, n - 2 * pad, n - 2 * pad);
  g.globalCompositeOperation = 'multiply';
  g.fillStyle = `#${(COLOURS[kind] ?? 0xffffff).toString(16).padStart(6, '0')}`;
  g.fillRect(0, 0, n, n);
  g.globalCompositeOperation = 'destination-in';
  g.drawImage(image, pad, pad, n - 2 * pad, n - 2 * pad);
  g.globalCompositeOperation = 'source-over';
}

/** A marker for a record (export 28's effect, sound or flare): a sprite one size on screen, over everything. */
export function makeEffectMarker(record) {
  const material = new THREE.SpriteMaterial({ map: icon(record.kind, record.startsOn === false), depthTest: false,
                                              depthWrite: false, transparent: true, sizeAttenuation: false });
  const sprite = new THREE.Sprite(material);
  sprite.renderOrder = 11; sprite.raycast = () => {};
  sprite.userData = { record, colour: new THREE.Color(COLOURS[record.kind] ?? 0xffffff) };
  paintEffectMarker(sprite, {});
  return sprite;
}

/** A marker's look: brighter and larger while picked; greyed for a streamed level's (view only) or a copy the Build
 *  makes with a piece (`derived`). */
export function paintEffectMarker(sprite, { picked = false, dim = false } = {}) {
  const c = sprite.userData.colour.clone();
  if (dim) c.lerp(DIM, 0.55);
  if (picked) c.lerp(PICKED, 0.5);
  sprite.material.color.copy(c);
  sprite.material.opacity = dim && !picked ? 0.7 : 1;
  sprite.scale.setScalar(picked ? PICKED_SIZE : SIZE);
}

/** The marker nearest a screen point within `radius` pixels, or null. */
export function nearestMarker(markers, camera, rect, clientX, clientY, radius = 13) {
  const p = new THREE.Vector3();
  let best = null, bestD = radius;
  for (const m of markers) {
    if (!m.visible) continue;
    m.updateWorldMatrix(true, false);
    p.setFromMatrixPosition(m.matrixWorld).project(camera);
    if (p.z > 1 || p.z < -1) continue;
    const d = Math.hypot(rect.left + (p.x + 1) / 2 * rect.width - clientX, rect.top + (1 - p.y) / 2 * rect.height - clientY);
    if (d < bestD) { bestD = d; best = m; }
  }
  return best;
}

const lineMaterial = (colour, opacity) => new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity, depthTest: false });

/** An effect's fixed box (game units, its component's frame) as lines, through `matrix` (the view basis: the actor's
 *  pose, its scale and its component's transform), or null where its system has no valid fixed box. */
export function boxShape(system, matrix, colour = COLOURS.effect) {
  const b = system?.fixedBox;
  if (!b?.used || !b.valid || !b.min || !b.max) return null;
  const corner = (i, j, k) => new THREE.Vector3(i ? b.max[0] : b.min[0], k ? b.max[2] : b.min[2], j ? b.max[1] : b.min[1]).applyMatrix4(matrix);
  const c = [corner(0, 0, 0), corner(1, 0, 0), corner(1, 1, 0), corner(0, 1, 0), corner(0, 0, 1), corner(1, 0, 1), corner(1, 1, 1), corner(0, 1, 1)];
  const points = [];
  for (const [i, j] of [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]) points.push(c[i], c[j]);
  const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial(colour, 0.85));
  lines.renderOrder = 10; lines.raycast = () => {};
  return lines;
}

// A wire sphere of three great circles about `centre` (view basis).
function sphere(centre, radius, colour, opacity) {
  const points = [], n = 64;
  for (const plane of [0, 1, 2]) {
    for (let k = 0; k < n; k++) {
      for (const j of [k, k + 1]) {
        const a = (j / n) * Math.PI * 2, c = Math.cos(a) * radius, s = Math.sin(a) * radius;
        points.push(centre.clone().add(plane === 0 ? new THREE.Vector3(c, s, 0) : plane === 1 ? new THREE.Vector3(c, 0, s) : new THREE.Vector3(0, c, s)));
      }
    }
  }
  const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial(colour, opacity));
  lines.renderOrder = 10; lines.raycast = () => {};
  return lines;
}

/** A sound's reach (effects_rules.soundReach: { inner, outer } in game units) at `centre` (view basis): the full
 *  volume sphere and, fainter, the one where it has faded out. */
export function reachShape(reach, centre, colour = COLOURS.sound) {
  const group = new THREE.Group();
  if (!reach) return group;
  group.add(sphere(centre, reach.outer, colour, 0.45));
  if (reach.inner > 1 && reach.inner < reach.outer - 1) group.add(sphere(centre, reach.inner, colour, 0.85));
  return group;
}
