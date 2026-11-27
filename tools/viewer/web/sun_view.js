// The time of day's marker in the view (the game-likeness plan, T-S1): the sun or moon on its arc over the map, the
// arcs the sun and the moon travel for the dial's heading, and a faint line from the marker down to the map's middle
// (the way the light falls). Drawn plainly where it is in view and faintly through what covers it, as the Lights view's
// markers are (lights_view.js); three.js alone, nothing of the page: sun_wiring.js says where and when.
import * as THREE from 'three';

// The marker keeps one size on screen: a fraction of the camera's distance (a light's marker is 0.016).
const MARKER_SCALE = 0.026;
const ARC = { sun: 0xffb060, moon: 0x9fb4ff };

const line = (color, opacity) => {
  const l = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthTest: false, depthWrite: false }));
  l.renderOrder = 8; l.raycast = () => {}; l.frustumCulled = false;
  return l;
};

/** The marker and its arcs, added to `world`, hidden until shown. */
export function createSunMarker(world) {
  const group = new THREE.Group();
  group.visible = false;
  const arcs = { sun: line(ARC.sun, 0.5), moon: line(ARC.moon, 0.5) };
  const ray = line(0xffffff, 0.25);
  const geometry = new THREE.SphereGeometry(0.6, 16, 12);
  const solid = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const ghost = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.35, depthTest: false, depthWrite: false });
  const rimMaterial = new THREE.MeshBasicMaterial({ color: 0x0d1418, side: THREE.BackSide, transparent: true, opacity: 0.85, depthTest: false, depthWrite: false });
  const marker = new THREE.Group();
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost), rim = new THREE.Mesh(geometry, rimMaterial);
  rim.scale.setScalar(1.3); behind.renderOrder = 9; rim.renderOrder = 8;
  for (const m of [rim, front, behind]) { m.raycast = () => {}; marker.add(m); }
  group.add(arcs.sun, arcs.moon, ray, marker);
  world.add(group);

  /** Where things stand (view points): each arc's points, the marker's place and the middle it shines on; the marker's
   *  colour (fractions, sRGB), whether the moon is up, and whether the pointer is over it or it is held. */
  function draw({ sunPoints, moonPoints, at, middle, colour, moon, lit = false }) {
    arcs.sun.geometry.setFromPoints(sunPoints); arcs.moon.geometry.setFromPoints(moonPoints);
    arcs.sun.material.opacity = moon ? 0.3 : 0.75; arcs.moon.material.opacity = moon ? 0.75 : 0.3;
    ray.geometry.setFromPoints([at, middle]);
    marker.position.copy(at);
    const c = new THREE.Color().setRGB(...colour, THREE.SRGBColorSpace);
    // (a dim moon's own colour is too dark to find: lifted toward white, the more the darker it is)
    const lift = Math.max(0, 0.55 - Math.max(...colour));
    c.lerp(new THREE.Color(0xffffff), lit ? 0.5 : lift);
    solid.color.copy(c); ghost.color.copy(c);
    rimMaterial.color.setHex(lit ? 0xffc040 : 0x0d1418);
  }
  /** Keep the marker one size on screen (each frame it is shown); its size in the view, for picking. */
  function scale(camera) {
    const s = Math.max(1e-3, camera.position.distanceTo(marker.position) * MARKER_SCALE);
    marker.scale.setScalar(s);
    return s * 0.6;
  }
  return { draw, group, marker, scale };
}
