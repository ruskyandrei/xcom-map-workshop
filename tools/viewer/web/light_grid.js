// Conservative XY light lists. The GPU follows each cell's offset/count into a
// packed index texture, so a dense cell has no fixed per-cell light limit.
export const CELL = 128;
// A light can reach far past the map: Lightmass's generated mesh area lights carry radii in the millions (Deluge's
// GeneratedMeshAreaLight_369: 2.4 million units, 120 000 units out). The grid covers only where the map has something
// to light (clip), and its cells double in size past this many cells, so one such light never asks for billions.
export const MAX_CELLS = 1 << 18;

export function buildLightGrid(lights, { clip = null, maxCells = MAX_CELLS, maxSide = 4096 } = {}) {
  const none = { bounds: null, lists: [], local: lights, cell: CELL, deepest: 0 };
  if (!lights.length) return none;
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (const l of lights) {
    if (!(Number.isFinite(l.radius) && l.radius > 0) || !l.location.every(Number.isFinite)) {
      throw Error('Invalid local light bounds');
    }
    x0 = Math.min(x0, l.location[0]-l.radius); x1 = Math.max(x1, l.location[0]+l.radius);
    z0 = Math.min(z0, l.location[1]-l.radius); z1 = Math.max(z1, l.location[1]+l.radius);
  }
  if (clip) {
    x0 = Math.max(x0, clip.x0); x1 = Math.min(x1, clip.x1);
    z0 = Math.max(z0, clip.z0); z1 = Math.min(z1, clip.z1);
    if (!(x1 > x0 && z1 > z0)) return none;   // no light reaches anything the map has
  }
  let cell = CELL, nx, nz;
  for (;;) {
    nx = Math.max(1, Math.ceil((x1-x0)/cell)); nz = Math.max(1, Math.ceil((z1-z0)/cell));
    if (nx*nz <= maxCells && nx <= maxSide && nz <= maxSide) break;
    cell *= 2;
  }
  const lists = Array.from({length: nx*nz}, () => []);
  lights.forEach((l, id) => {
    const [x,z] = l.location, r = l.radius;
    for (let i=Math.max(0,Math.floor((x-r-x0)/cell)); i<Math.min(nx,Math.ceil((x+r-x0)/cell)); i++) {
      for (let j=Math.max(0,Math.floor((z-r-z0)/cell)); j<Math.min(nz,Math.ceil((z+r-z0)/cell)); j++) {
        const dx=Math.max(x0+i*cell-x,0,x-x0-(i+1)*cell);
        const dz=Math.max(z0+j*cell-z,0,z-z0-(j+1)*cell);
        if (dx*dx+dz*dz < r*r) lists[j*nx+i].push(id);
      }
    }
  });
  return {bounds:{x0,z0,nx,nz}, lists, local:lights, cell,
          deepest:lists.reduce((n,c)=>Math.max(n,c.length),0)};
}

/** The XY box (UE x and y: the grid's x and z) that holds the scene's pieces (each piece by its mesh's bounds; not
 *  the sky's environment pieces) and its play area, widened by margin for pieces moved or added past it: a light
 *  lights only pieces, wherever it stands. Null when the scene has neither (the prefab workspace). */
export function sceneLightClip(scene, margin = 4096) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  const take = (x, z, r = 0) => {
    if (!Number.isFinite(x) || !Number.isFinite(z) || !Number.isFinite(r)) return;
    x0 = Math.min(x0, x-r); x1 = Math.max(x1, x+r); z0 = Math.min(z0, z-r); z1 = Math.max(z1, z+r);
  };
  const meshes = scene.meshes || {};
  for (const o of scene.objects || []) {
    // The sky dome and its ground plane (environment pieces) wrap the map hundreds of thousands of units out.
    if (!Array.isArray(o.location) || o.environment) continue;
    // Mesh bounds: box origin, box half extents, sphere radius; the reach is the smaller of the sphere and the box's.
    const b = meshes[o.mesh]?.bounds, s = Math.max(1, ...(o.scale || []).map(Math.abs));
    take(o.location[0], o.location[1],
         Array.isArray(b) ? (Math.hypot(b[0], b[1], b[2]) + Math.min(b[6], Math.hypot(b[3], b[4], b[5]))) * s : 0);
  }
  const play = scene.playableBounds;   // view axes: [x, height, y]
  if (play) { take(play.min[0], play.min[2]); take(play.max[0], play.max[2]); }
  if (!(x1 >= x0)) return null;
  return { x0: x0-margin, z0: z0-margin, x1: x1+margin, z1: z1+margin };
}

export function packLightGrid(grid, include = () => true, maxTextureSize = 4096) {
  const {bounds,lists,local} = grid;
  if (!bounds) return null;
  if (bounds.nx > maxTextureSize || bounds.nz > maxTextureSize) throw Error('Light grid exceeds GPU texture dimensions');
  const cells = new Float32Array(bounds.nx*bounds.nz*4), ids = [];
  let deepest = 0;
  lists.forEach((cell,c) => {
    const start=ids.length;
    for (const id of cell) if (include(local[id])) ids.push(id);
    const count=ids.length-start;
    cells[c*4]=start; cells[c*4+1]=count; deepest=Math.max(deepest,count);
  });
  // Float32 stores every integer up to 2^24 exactly. Refuse unsupported sizes
  // explicitly, instead of losing indices or silently dropping contributions.
  const texels=Math.max(1,Math.ceil(ids.length/4));
  const width=Math.min(maxTextureSize,Math.ceil(Math.sqrt(texels))), height=Math.ceil(texels/width);
  if (ids.length > 2**24 || height > maxTextureSize) throw Error('Light index texture exceeds GPU capacity');
  const indices=new Float32Array(width*height*4);
  indices.set(ids);
  return {cells,indices,width,height,entries:ids.length,deepest};
}
