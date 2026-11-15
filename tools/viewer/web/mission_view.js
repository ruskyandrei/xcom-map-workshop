// A mission's objects in the view (private/plans/done/mission-types-plan.md, C2): the objects of the streams the
// header's Mission picker shows (export 24: streams[<name>].missionObjects, tools/viewer/scene_metadata.py
// mission_objects), each a marker one size on screen and faint through walls, as lights' are. A click on one shows
// what it is ("Capture point 1 of 2, Data recovery"), the group it moves with and what lists it. The page's gizmo
// moves a picked object with its group (Part E: app.js missionMoves); the Build moves them in the stream's copy.
import * as THREE from 'three';

// kind -> what it is called, its colour and its marker's shape. Kinds left out (a bomb's emitters, rebuild volumes,
// triggers, wave systems, the squad's visible point) are listed with the object they go with, not marked.
export const KINDS = {
  dropIn: { label: 'Drop-in point', colour: 0xff6b6b, shape: 'arrow' },
  pod: { label: 'Pod', colour: 0xff9f43, shape: 'ring' },
  landing: { label: 'Landing', colour: 0x4dd0e1, shape: 'dot' },
  soldier: { label: 'Soldier\'s point', colour: 0x4dd0e1, shape: 'dot' },
  operative: { label: 'Covert operative\'s point', colour: 0x26de81, shape: 'dot' },
  vip: { label: 'VIP\'s point', colour: 0x26de81, shape: 'dot' },
  loot: { label: 'Loot point', colour: 0xfed330, shape: 'dot' },
  point: { label: 'Point', colour: 0xb8c4cc, shape: 'dot' },
  capturePoint: { label: 'Capture point', colour: 0xa55eea, shape: 'gem' },
  radar: { label: 'Radar array', colour: 0xa55eea, shape: 'gem' },
  bomb: { label: 'The bomb', colour: 0xeb3b5a, shape: 'gem' },
  powerNode: { label: 'Power node', colour: 0xfa8231, shape: 'gem' },
  use: { label: 'Thing to use', colour: 0x45aaf2, shape: 'gem' },
  meld: { label: 'Meld point', colour: 0x20bf6b, shape: 'dot' },
};
const ROLE_WORDS = { bomb: 'the bomb', button: 'its button', waypoint: 'its floor marker', effect: 'an effect', rebuild: 'its rebuild volume',
                     visible: 'its visible point', node: 'the node', volume: 'the capture volume', captured: 'the actor it captures', actor: 'a capture actor' };
const GROUP_WORDS = g => g === 'bomb' ? 'the bomb' : g.startsWith('node:') ? `power node ${g.slice(5)}` : g.startsWith('capture:') ? `capture point ${g.slice(8)}` : g;

/** Whether an object gets a marker: its kind is one of KINDS, and it isn't a group's helper part. */
export const marked = o => Boolean(KINDS[o.kind]) && !['effect', 'rebuild', 'visible', 'waypoint'].includes(o.role);

function shape(kind) {
  switch (KINDS[kind]?.shape) {
    case 'arrow': return new THREE.ConeGeometry(0.45, 1.1, 10).rotateX(Math.PI).translate(0, 0.55, 0);
    case 'ring': return new THREE.TorusGeometry(0.55, 0.14, 6, 18).rotateX(Math.PI / 2);
    case 'gem': return new THREE.OctahedronGeometry(0.6);
    default: return new THREE.SphereGeometry(0.4, 12, 8);
  }
}

/** A marker: a solid shape, and the same faint over everything, so it shows through walls. */
export function makeMissionMarker(kind) {
  const colour = new THREE.Color(KINDS[kind]?.colour ?? 0xffffff);
  const solid = new THREE.MeshBasicMaterial({ color: colour });
  const ghost = new THREE.MeshBasicMaterial({ color: colour, transparent: true, opacity: 0.3, depthTest: false, depthWrite: false });
  const geometry = shape(kind), marker = new THREE.Group();
  const front = new THREE.Mesh(geometry, solid), behind = new THREE.Mesh(geometry, ghost);
  behind.renderOrder = 6;
  for (const m of [front, behind]) { m.raycast = () => {}; marker.add(m); }
  marker.userData = { front, behind, solid, ghost, colour };
  return marker;
}

/** A marker brighter while its object is picked. */
export function paintMissionMarker(marker, picked) {
  const { solid, ghost, colour } = marker.userData;
  const c = colour.clone();
  if (picked) c.lerp(new THREE.Color(0xffffff), 0.45);
  solid.color.copy(c); ghost.color.copy(c); ghost.opacity = picked ? 0.6 : 0.3;
}

/** What the panel says of an object: {title, lines}. objects: its stream's; missionLabel: the mission picked. */
export function describe(o, objects, missionLabel) {
  const same = objects.filter(x => x.kind === o.kind && marked(x) && (o.kind !== 'capturePoint' || x.role === o.role));
  const k = same.indexOf(o), label = KINDS[o.kind]?.label ?? o.kind;
  const title = `${label}${same.length > 1 && k >= 0 ? ` ${k + 1} of ${same.length}` : ''}${missionLabel ? `, ${missionLabel}` : ''}`;
  const lines = [`${o.actor.split('.').pop()} (${o.actorClass}${o.archetype ? `, ${o.archetype}` : ''}).`];
  if (o.group) {
    const members = objects.filter(x => x.group === o.group && x !== o).map(x => ROLE_WORDS[x.role] ?? x.role);
    lines.push(`Part of ${GROUP_WORDS(o.group)} (${ROLE_WORDS[o.role] ?? o.role}); it moves with ${members.length ? [...new Set(members)].join(', ') : 'nothing else'}.`);
  }
  lines.push(o.referencedBy?.length ? `Listed by ${o.referencedBy.slice(0, 6).join('; ')}${o.referencedBy.length > 6 ? `; and ${o.referencedBy.length - 6} more` : ''}.`
    : 'Nothing in the stream lists it by name.');
  return { title, lines };
}
