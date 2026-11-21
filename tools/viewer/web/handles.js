// The drag handles' helpers (refactor stage P9): what every area's drag handles share. How near the mouse a handle is
// picked (HANDLE_PICK, in screen pixels), a game point as a point of the view (gameToView: the view's basis is x, up,
// y), screen positions of points in the view, or null behind the camera (projector), and how far along a line the
// mouse's ray passes closest, a handle's drag along its axis (alongLine). The Lights, Buildings, Spawns and Landing
// zones views, the cover blocks, the made pieces, the map grid and the test hooks use them.
//
// createHandles takes the camera, the renderer and the scene's pieces' ray when app.js makes it (before the first area
// given its functions; nothing of it runs as the page loads). HANDLE_PICK and gameToView read only their arguments and
// are plain exports at the top. It keeps no state.
import * as THREE from 'three';

export const HANDLE_PICK = 10;
// A game point (x, y, z) as a point of the view, whose basis is x, up, y (the Spawns and Landing zones views and the
// test hooks)
export const gameToView = p => new THREE.Vector3(p[0], p[2], p[1]);

export function createHandles({ camera, rayAt, renderer }) {
  // Screen positions (client pixels) for points in the view, or null behind the camera.
  function projector() {
    const rect = renderer.domElement.getBoundingClientRect(), p = new THREE.Vector3();
    return v => {
      p.copy(v).project(camera);
      if (p.z < -1 || p.z > 1) return null;
      return [rect.left + (p.x + 1) / 2 * rect.width, rect.top + (1 - p.y) / 2 * rect.height];
    };
  }
  // How far along a line (origin, unit dir) the mouse's ray passes closest: the handle's drag
  function alongLine(clientX, clientY, origin, dir) {
    const ray = rayAt(clientX, clientY).ray, w = origin.clone().sub(ray.origin);
    const b = dir.dot(ray.direction), c = ray.direction.dot(ray.direction), d = dir.dot(w), e = ray.direction.dot(w);
    const den = c - b * b;
    return Math.abs(den) < 1e-9 ? null : (b * e - c * d) / den;
  }

  return { alongLine, projector };
}
