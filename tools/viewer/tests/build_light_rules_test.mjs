// A baked Build's own light on the page (build_light_rules.js; game-likeness plan, B4): which pieces are as built,
// their built components, a light's place as built, the View options line. Run:
// node tools/viewer/tests/build_light_rules_test.mjs
import assert from 'node:assert/strict';
import { buildWords, builtComponent, changedSince, lightPlace, movedAsBuilt, recordsByKey, sameRecord } from '../web/build_light_rules.js';

const PL = 'TheWorld.PersistentLevel.';
const target = actor => ({ package: 'URB_Bar', level: 'base', actor: PL + actor });
const built = {
  overrides: [{ target: target('XComLevelActor_44'), location: [100, 200, 0], rotation: [0, 16384, 0] },
              { target: target('XComLevelActor_45'), deleted: true },
              { target: target('XComLevelActor_46'), flags: { walking: false } }],
  added: [{ id: 'a', actor: `${PL}XComLevelActor_9_copy1`, from: target('XComLevelActor_9'), components: [`${PL}XComLevelActor_9.StaticMeshComponent_3`],
            location: [0, 0, 0], rotation: [0, 0, 0] },
          { id: 'b', actor: `${PL}SpotLight_copy2`, template: { kind: 'spot', version: 1 }, location: [10, 20, 30], rotation: [0, 0, 0],
            light: { radius: 512, brightness: 2 } }],
};

// the records by key, as the groups key them
const keys = recordsByKey(built);
assert.deepEqual([...keys.keys()], [`orig|URB_Bar|base|${PL}XComLevelActor_44`, `orig|URB_Bar|base|${PL}XComLevelActor_45`,
                                    `orig|URB_Bar|base|${PL}XComLevelActor_46`, `added|${PL}XComLevelActor_9_copy1`, `added|${PL}SpotLight_copy2`]);
assert.equal(recordsByKey(null).size, 0);

// the same for a piece's light: a pose read again within a thousandth, flags and labels left aside, undefined as absent
assert.ok(sameRecord({ location: [1, 2, 3], rotation: [0, 1, 0] }, { location: [1.0004, 2, 3], rotation: [0, 1, 0] }));
assert.ok(!sameRecord({ location: [1, 2, 3] }, { location: [1.01, 2, 3] }));
assert.ok(sameRecord({ location: [1, 2, 3], flags: { cover: true }, prefab: 'x' }, { location: [1, 2, 3], partner: null }));
assert.ok(sameRecord({ location: [1, 2, 3], tinted: undefined }, { location: [1, 2, 3] }));
assert.ok(!sameRecord({ deleted: true }, { location: [1, 2, 3] }));
// (a nested `flags` is a value like any other: only the record's own are its settings)
assert.ok(!sameRecord({ generated: { flags: 1 } }, { generated: { flags: 2 } }));
assert.ok(!sameRecord({ components: ['a', 'b'] }, { components: ['a'] }));

// changed since: nothing for the project as built (its flags changed: no light changes); a move, a delete undone, a
// piece added, a piece of the Build's taken away, a light's value
assert.equal(changedSince(built, built).size, 0);
const now = structuredClone(built);
now.overrides[2].flags = { walking: true };
assert.equal(changedSince(now, built).size, 0);
now.overrides[0].location = [148, 200, 0];
now.overrides.splice(1, 1);
now.added[1].light.radius = 600;
now.added.push({ id: 'c', actor: `${PL}XComLevelActor_9_copy3`, from: target('XComLevelActor_9'), components: [], location: [0, 0, 0], rotation: [0, 0, 0] });
assert.deepEqual([...changedSince(now, built)].sort(), [`added|${PL}SpotLight_copy2`, `added|${PL}XComLevelActor_9_copy3`,
                                                         `orig|URB_Bar|base|${PL}XComLevelActor_44`, `orig|URB_Bar|base|${PL}XComLevelActor_45`]);
const gone = structuredClone(built);
gone.added.splice(0, 1);
assert.deepEqual([...changedSince(gone, built)], [`added|${PL}XComLevelActor_9_copy1`]);

// moved as built: a pose, not deleted, not flags alone
assert.deepEqual(built.overrides.map(movedAsBuilt), [true, false, false]);
assert.equal(movedAsBuilt(undefined), false);

// the built component: the Build's actor with the component's own name; none where the Build names no actor or cut
// the piece into parts; an original where the map has it keeps its own
const actors = { [`${PL}XComLevelActor_9_copy1`]: `${PL}XComLevelActor_412`, [`${PL}XComLevelActor_44`]: `${PL}XComLevelActor_413`,
                 [`${PL}XComFracLevelActor_2_copy4`]: [`${PL}XComFracLevelActor_88`, `${PL}XComFracLevelActor_89`] };
assert.equal(builtComponent(actors, { actor: `${PL}XComLevelActor_9_copy1`, component: `${PL}XComLevelActor_9.StaticMeshComponent_3`, copied: true }),
             `${PL}XComLevelActor_412.StaticMeshComponent_3`);
assert.equal(builtComponent(actors, { actor: `${PL}XComLevelActor_44`, component: `${PL}XComLevelActor_44.StaticMeshComponent_7`, copied: true }),
             `${PL}XComLevelActor_413.StaticMeshComponent_7`);
assert.equal(builtComponent(actors, { actor: `${PL}XComFracLevelActor_2_copy4`, component: `${PL}XComFracLevelActor_2.FracturedStaticMeshComponent_1`, copied: true }), null);
assert.equal(builtComponent(actors, { actor: `${PL}Nothing_copy9`, component: `${PL}Nothing.StaticMeshComponent_1`, copied: true }), null);
assert.equal(builtComponent(actors, { actor: `${PL}XComLevelActor_50`, component: `${PL}XComLevelActor_50.StaticMeshComponent_1`, copied: false }),
             `${PL}XComLevelActor_50.StaticMeshComponent_1`);
assert.equal(builtComponent(null, { actor: 'x', component: 'x.c', copied: true }), null);

// a light's place as built: an override's pose and values over the light as exported; an added light's own
const exported = { location: [1, 2, 3], radius: 256 };
assert.deepEqual(lightPlace({ target: target('PointLight_1') }, exported), { location: [1, 2, 3], radius: 256 });
assert.deepEqual(lightPlace({ target: target('PointLight_1'), location: [5, 6, 7], light: { radius: 300 } }, exported), { location: [5, 6, 7], radius: 300 });
assert.deepEqual(lightPlace(built.added[1]), { location: [10, 20, 30], radius: 512 });
assert.equal(lightPlace({ target: target('PointLight_1'), deleted: true }, exported), null);
assert.equal(lightPlace({ location: [0, 0, 0] }, { radius: 0 }), null);
assert.equal(lightPlace(null, exported), null);

// View options' line
assert.equal(buildWords('27/11/2026, 14:05', 0).text, 'Lit by the Build of 27/11/2026, 14:05 · nothing changed since');
assert.equal(buildWords('x', 1).text, 'Lit by the Build of x · 1 piece changed since');
assert.equal(buildWords('x', 3).text, 'Lit by the Build of x · 3 pieces changed since');
assert.match(buildWords('x', 3).title, /lit live/);

console.log('build_light_rules: ok');
