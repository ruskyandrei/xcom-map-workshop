import * as THREE from 'three';

export function visibleBounds(roots, fallback = null) {
  const box = new THREE.Box3();
  for (const root of roots.values()) {
    const source=root.userData.source;
    if (root.visible && !source?.environment && !source?.hidden) box.union(new THREE.Box3().setFromObject(root));
  }
  if (box.isEmpty() && fallback) box.set(new THREE.Vector3(...fallback.min),new THREE.Vector3(...fallback.max));
  return box;
}

export function focusBounds(scene) {
  const source=(!scene.preview && scene.tactical?.focusBounds) || scene.playableBounds;
  return source ? new THREE.Box3(new THREE.Vector3(...source.min),new THREE.Vector3(...source.max)) : null;
}

export function interiorPlanes(scene) {
  const box=focusBounds(scene);
  if(!box)return [];
  return [new THREE.Plane(new THREE.Vector3(1,0,0),-box.min.x),new THREE.Plane(new THREE.Vector3(-1,0,0),box.max.x),
    new THREE.Plane(new THREE.Vector3(0,1,0),-box.min.y),new THREE.Plane(new THREE.Vector3(0,-1,0),box.max.y),
    new THREE.Plane(new THREE.Vector3(0,0,1),-box.min.z),new THREE.Plane(new THREE.Vector3(0,0,-1),box.max.z)];
}

// The map's tile grid in the viewer's basis: origin [x, z, y] of tile (0, 0, 0), tile size [x, z, y] and the count of
// tiles along each game axis. Maps without a saved grid get one over their playable bounds.
export function tileGridOf(scene) {
  const source=scene.tileGrid, box=scene.playableBounds;
  const origin=source?.origin || (box ? [box.min[0],box.min[2],box.min[1]] : [-480,-480,0]);
  const size=source?.size || [96,96,64];
  const dims=source?.dimensions || (box ? [Math.max(1,Math.round((box.max[0]-box.min[0])/size[0])),
    Math.max(1,Math.round((box.max[2]-box.min[2])/size[1])),1] : [10,10,1]);
  return {origin,size,dims};
}

// The corners of one saved floor tile's surface, 1.5 units above it, following its slope (a ramp's tiles tilt).
function floorQuad(floor,origin,size,lift=1.5) {
  const [tx,ty]=floor.tile,[nx,ny,nz]=floor.normal,points=[];
  for(const [dx,dy] of [[0,0],[1,0],[1,1],[0,1]]) {
    const x=origin[0]+(tx+dx)*size[0],z=origin[1]+(ty+dy)*size[1];
    const slope=Math.abs(nz)>0.5 ? -(nx*(x-floor.location[0])+ny*(z-floor.location[1]))/nz : 0;
    points.push([x,floor.location[2]+slope+lift,z]);
  }
  return points;
}

function hull(points) {
  // Andrew's monotone chain; points are [x, y] in game axes.
  const p=[...points].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  if(p.length<3)return p;
  const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
  const lower=[],upper=[];
  for(const q of p){while(lower.length>=2&&cross(lower.at(-2),lower.at(-1),q)<=0)lower.pop();lower.push(q);}
  for(const q of p.reverse()){while(upper.length>=2&&cross(upper.at(-2),upper.at(-1),q)<=0)upper.pop();upper.push(q);}
  return lower.slice(0,-1).concat(upper.slice(0,-1));
}

// Whether a convex polygon reaches into a rectangle (separating axes); touching edges do not count.
function reaches(poly,x0,y0,x1,y1) {
  const rect=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
  const axes=[[1,0],[0,1]];
  for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length];
    if(a[0]!==b[0]||a[1]!==b[1])axes.push([b[1]-a[1],a[0]-b[0]]);
  }
  for(const [nx,ny] of axes){
    let pmin=Infinity,pmax=-Infinity,rmin=Infinity,rmax=-Infinity;
    for(const p of poly){const d=p[0]*nx+p[1]*ny;pmin=Math.min(pmin,d);pmax=Math.max(pmax,d);}
    for(const p of rect){const d=p[0]*nx+p[1]*ny;rmin=Math.min(rmin,d);rmax=Math.max(rmax,d);}
    if(rmax<=pmin||rmin>=pmax)return false;
  }
  return true;
}

// Directions spread evenly over a sphere: a mesh's farthest vertex along each outlines its shape (a round fog pod as a
// many-sided solid, a box as its eight corners) far more closely than its bounding box does.
const DIRECTIONS=Array.from({length:96},(_,i)=>{
  const y=1-2*(i+0.5)/96,r=Math.sqrt(1-y*y),a=i*Math.PI*(3-Math.sqrt(5));
  return [Math.cos(a)*r,y,Math.sin(a)*r];
});
const extremes=new WeakMap();
// The geometry's farthest vertices along those directions, in its own space (once per geometry).
function extremePoints(geometry) {
  if(extremes.has(geometry))return extremes.get(geometry);
  const position=geometry.attributes.position,best=DIRECTIONS.map(()=>[-Infinity,-1]);
  for(let i=0;i<position.count;i++){
    const x=position.getX(i),y=position.getY(i),z=position.getZ(i);
    for(let d=0;d<DIRECTIONS.length;d++){const [a,b,c]=DIRECTIONS[d],v=a*x+b*y+c*z;if(v>best[d][0])best[d]=[v,i];}
  }
  const points=[...new Set(best.map(b=>b[1]).filter(i=>i>=0))].map(i=>new THREE.Vector3().fromBufferAttribute(position,i));
  extremes.set(geometry,points);
  return points;
}

// Tiles count as covered when the footprint reaches this far into them (a quarter tile), and as touched at the edge
// when it reaches in at all, by more than EDGE units.
const COVER_DEPTH=24, EDGE_DEPTH=2;
const point=new THREE.Vector3();
// The tiles a piece covers: each mesh's outline, turned and moved as drawn, laid flat on the map. Returns the tiles it
// covers and those it only reaches into at the edge ("x,y" keys), the outlines (in game x, y), its lowest point (viewer
// y) and that point's tile level; null when nothing is drawn or the piece lies off the map's grid. From the drawn
// mesh: the game decides from the piece's collision.
export function footprintOf(objects,scene,limit=4096) {
  const {origin,size,dims}=tileGridOf(scene);
  const outlines=[];let base=Infinity;
  for(const object of objects) object.traverse(part=>{
    if(!part.isMesh||!part.geometry?.attributes.position)return;
    for(let o=part;o;o=o.parent)if(!o.visible)return;
    const pts=[];
    for(const v of extremePoints(part.geometry)){
      point.copy(v).applyMatrix4(part.matrixWorld);pts.push([point.x,point.z]);base=Math.min(base,point.y);
    }
    if(pts.length)outlines.push(hull(pts));
  });
  if(!outlines.length)return null;
  const all=outlines.flat();
  const lo=[Math.min(...all.map(p=>p[0])),Math.min(...all.map(p=>p[1]))],hi=[Math.max(...all.map(p=>p[0])),Math.max(...all.map(p=>p[1]))];
  const t0=[0,1].map(k=>Math.max(scene.prefabWorkspace ? -Infinity : 0,Math.floor((lo[k]-origin[k])/size[k]))),t1=[0,1].map(k=>Math.min(scene.prefabWorkspace ? Infinity : dims[k]-1,Math.floor((hi[k]-origin[k])/size[k])));
  if(t0[0]>t1[0]||t0[1]>t1[1]||(t1[0]-t0[0]+1)*(t1[1]-t0[1]+1)>limit)return null;
  const into=(tx,ty,depth)=>{
    const x0=origin[0]+tx*size[0]+depth,y0=origin[1]+ty*size[1]+depth;
    const x1=origin[0]+(tx+1)*size[0]-depth,y1=origin[1]+(ty+1)*size[1]-depth;
    return outlines.some(poly=>poly.length>=3&&reaches(poly,x0,y0,x1,y1));
  };
  const tiles=new Set(),edges=new Set();
  for(let tx=t0[0];tx<=t1[0];tx++)for(let ty=t0[1];ty<=t1[1];ty++){
    if(into(tx,ty,COVER_DEPTH))tiles.add(`${tx},${ty}`);
    else if(into(tx,ty,EDGE_DEPTH))edges.add(`${tx},${ty}`);
  }
  if(!tiles.size&&!edges.size)return null;
  const level=Math.max(0,Math.min(dims[2]-1,Math.floor((base-origin[2])/size[2]+1e-3)));
  return {tiles,edges,outlines,base,level,range:[t0,t1]};
}

const floorIndex=new WeakMap();
function floorsOf(scene) {
  if(!floorIndex.has(scene)){
    const index=new Map();
    for(const floor of scene.tactical?.floorTiles || [])index.set(floor.tile.join(','),floor);
    floorIndex.set(scene,index);
  }
  return floorIndex.get(scene);
}

// The Floor tiles overlay (View options; private/plans/done/floor-brush-plan.md, 3.7): the map's saved floor tiles, each on its
// surface, in one batched mesh coloured per tile by colorOf(actor) (the piece that carries it), and grey with crossed
// lines where gone(actor) (a piece moved or deleted since: the Build's rebuild checks those tiles again). shown(floor)
// picks the tiles drawn. userData.tiles[i] is the tile of the mesh's triangles 2i and 2i+1, for picking. The saved
// data only: copies have no saved floor, so they show none.
const GONE_COLOR=0x7d8a93;
export function floorTilesOverlay(scene,{shown=()=>true,colorOf=()=>0x82d5ce,gone=()=>false}={}) {
  const {origin,size}=tileGridOf(scene),group=new THREE.Group(),tiles=[],pos=[],col=[],hatch=[],color=new THREE.Color();
  for(const floor of scene.preview ? [] : scene.tactical?.floorTiles || []){
    if(!shown(floor))continue;
    const q=floorQuad(floor,origin,size,2.5),c=[(q[0][0]+q[2][0])/2,(q[0][1]+q[2][1])/2,(q[0][2]+q[2][2])/2];
    const p=q.map(v=>[c[0]+(v[0]-c[0])*0.9,v[1],c[2]+(v[2]-c[2])*0.9]),isGone=gone(floor.actor);
    pos.push(...p[0],...p[1],...p[2],...p[0],...p[2],...p[3]);
    color.set(isGone ? GONE_COLOR : colorOf(floor.actor));
    for(let i=0;i<6;i++)col.push(color.r,color.g,color.b);
    if(isGone)hatch.push(...p[0],...p[2],...p[1],...p[3]);
    tiles.push(floor);
  }
  if(pos.length){
    const g=new THREE.BufferGeometry();
    g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('color',new THREE.Float32BufferAttribute(col,3));
    const mesh=new THREE.Mesh(g,new THREE.MeshBasicMaterial({vertexColors:true,transparent:true,opacity:0.42,side:THREE.DoubleSide,
      depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}));
    mesh.renderOrder=5;mesh.name='floorTiles';group.add(mesh);
  }
  if(hatch.length){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(hatch,3));
    const lines=new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:0xdbe7ec,transparent:true,opacity:0.6,depthWrite:false}));
    lines.renderOrder=6;lines.raycast=()=>{};group.add(lines);
  }
  group.userData={tiles};
  return group;
}

const GRID_COLOR=new THREE.Color(0x79d6ce), FOOT_COLOR=0xf2c46d, FLOAT_COLOR=0x8fb4ff;
// A piece whose lowest point is more than this above the floor under it is drawn as floating (EXP-11: a fog pod lifted
// 64 units gave no cover).
const FLOAT_GAP=8;
// The grid around a footprint: the tiles within `reach` of it at its tile level, fading out with distance. A tile lies
// on the map's saved floor surface at that level where there is one (unless its floor actor is hidden or cut away), and
// flat at the piece's lowest point elsewhere. The covered tiles are filled and outlined, also through the piece itself,
// and each mesh's outline is drawn at the piece's lowest point. Where the piece floats above the saved floor under it,
// its tiles are drawn in blue, with lines from the floor up to the piece. userData.gap is that height (null with no
// saved floor under it).
export function tileGridAround(foot,scene,actors=null,reach=3) {
  const {origin,size,dims}=tileGridOf(scene),floors=floorsOf(scene);
  const group=new THREE.Group();
  const [t0,t1]=foot.range,lines=[],colors=[],fill=[],edges=[],rims=[],edgeFill=[];
  let floorTop=-Infinity;
  const surface=(tx,ty)=>{
    const floor=scene.preview ? null : floors.get(`${tx},${ty},${foot.level}`);
    const actor=floor && actors?.get(floor.actor);
    if(floor && !(actor && (!actor.visible || floor.location[2]>actor.ceiling)))return floorQuad(floor,origin,size);
    const y=foot.base+1.5,x0=origin[0]+tx*size[0],z0=origin[1]+ty*size[1];
    return [[x0,y,z0],[x0+size[0],y,z0],[x0+size[0],y,z0+size[1]],[x0,y,z0+size[1]]];
  };
  for(let tx=Math.max(scene.prefabWorkspace ? -Infinity : 0,t0[0]-reach);tx<=Math.min(scene.prefabWorkspace ? Infinity : dims[0]-1,t1[0]+reach);tx++)
    for(let ty=Math.max(scene.prefabWorkspace ? -Infinity : 0,t0[1]-reach);ty<=Math.min(scene.prefabWorkspace ? Infinity : dims[1]-1,t1[1]+reach);ty++){
      const covered=foot.tiles.has(`${tx},${ty}`),edge=foot.edges.has(`${tx},${ty}`);
      // Distance in tiles to the footprint's box: the grid fades out over `reach` tiles.
      const d=Math.max(t0[0]-tx,tx-t1[0],t0[1]-ty,ty-t1[1],0);
      const q=surface(tx,ty);
      // Inset a little so neighbouring tiles' edges don't fall on one line.
      const c=[(q[0][0]+q[2][0])/2,(q[0][1]+q[2][1])/2,(q[0][2]+q[2][2])/2];
      const p=q.map(v=>[c[0]+(v[0]-c[0])*0.96,v[1],c[2]+(v[2]-c[2])*0.96]);
      if(covered||edge){
        // The saved floor under the piece: at its level, or the nearest one below it.
        for(let level=foot.level;level>=0 && !scene.preview;level--){
          const floor=floors.get(`${tx},${ty},${level}`),actor=floor && actors?.get(floor.actor);
          if(!floor || (actor && !actor.visible) || floor.location[2]>foot.base+FLOAT_GAP)continue;
          floorTop=Math.max(floorTop,floor.location[2]);break;
        }
      }
      if(edge){
        edgeFill.push(...p[0],...p[1],...p[2],...p[0],...p[2],...p[3]);
        for(let i=0;i<4;i++)rims.push(...p[i],...p[(i+1)%4]);
        continue;
      }
      if(covered){
        fill.push(...p[0],...p[1],...p[2],...p[0],...p[2],...p[3]);
        for(let i=0;i<4;i++)edges.push(...p[i],...p[(i+1)%4]);
        continue;
      }
      const alpha=0.45*(1-d/(reach+1));
      for(let i=0;i<4;i++){lines.push(...p[i],...p[(i+1)%4]);for(let k=0;k<2;k++)colors.push(GRID_COLOR.r,GRID_COLOR.g,GRID_COLOR.b,alpha);}
    }
  const geometry=(values,extra)=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(values,3));
    if(extra)g.setAttribute('color',new THREE.Float32BufferAttribute(extra,4));return g;};
  if(lines.length)group.add(new THREE.LineSegments(geometry(lines,colors),
    new THREE.LineBasicMaterial({vertexColors:true,transparent:true,depthWrite:false})));
  const gap=Number.isFinite(floorTop) ? foot.base-floorTop : null, floating=gap!=null && gap>FLOAT_GAP;
  const color=floating ? FLOAT_COLOR : FOOT_COLOR;
  if(fill.length){
    group.add(new THREE.Mesh(geometry(fill),new THREE.MeshBasicMaterial({color,transparent:true,opacity:floating ? 0.3 : 0.5,
      side:THREE.DoubleSide,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2})));
    // Through the piece standing on them: faint fill and full outlines.
    const through=new THREE.Mesh(geometry(fill),new THREE.MeshBasicMaterial({color,transparent:true,opacity:0.2,
      side:THREE.DoubleSide,depthWrite:false,depthTest:false}));
    through.renderOrder=10;group.add(through);
    const outline=new THREE.LineSegments(geometry(edges),new THREE.LineBasicMaterial({color,transparent:true,opacity:0.9,
      depthWrite:false,depthTest:false}));
    outline.renderOrder=11;group.add(outline);
  }
  if(rims.length){
    // Tiles it only reaches into at the edge: a light fill and an outline, the outline also through the piece.
    group.add(new THREE.Mesh(geometry(edgeFill),new THREE.MeshBasicMaterial({color,transparent:true,opacity:0.14,
      side:THREE.DoubleSide,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2})));
    const rim=new THREE.LineSegments(geometry(rims),new THREE.LineBasicMaterial({color,transparent:true,opacity:0.55,
      depthWrite:false,depthTest:false}));
    rim.renderOrder=11;group.add(rim);
  }
  const shape=[],stilts=[],y=foot.base+2;
  for(const poly of foot.outlines)for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length];shape.push(a[0],y,a[1],b[0],y,b[1]);
    if(floating)stilts.push(a[0],floorTop+1.5,a[1],a[0],foot.base,a[1]);
  }
  for(const [values,c,o] of [[shape,0xffffff,0.5],[stilts,FLOAT_COLOR,0.8]]){
    if(!values.length)continue;
    const s=new THREE.LineSegments(geometry(values),new THREE.LineBasicMaterial({color:c,transparent:true,opacity:o,
      depthWrite:false,depthTest:false}));
    s.renderOrder=12;group.add(s);
  }
  group.userData={tiles:[...foot.tiles],edges:[...foot.edges],level:foot.level,base:foot.base,gap,floating};
  return group;
}
