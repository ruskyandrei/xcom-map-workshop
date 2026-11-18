// The Effects view's words (effects_rules.js; private/plans/done/effects-and-sounds-plan.md, Part B, stage FX1): each
// record's name and chips, its panel lines, its parameters as rows, where a sound is heard and whether a clear keeps
// it, on records shaped as export 28 makes them (tools/viewer/effects_metadata.py; URB_Bar's actors); and their values
// (stage FX5): the parameters the panel offers, the record as edited, what a project saves.
// Run: node tools/viewer/tests/effects_rules_test.mjs
import assert from 'node:assert/strict';
import { colourNamed, effectRecords, keptValues, parameterControls, parameterRows, recordChips, recordLines, recordName, savedValues, soundReach,
         survivesClear, tintOf, tintVector, valuesViewOnly, withValues } from '../web/effects_rules.js';

const PL = 'TheWorld.PersistentLevel.';
const beam = {
  kind: 'effect', id: 'effect:2158', actor: `${PL}Emitter_4`, actorClass: 'Emitter', location: [-1669.3, 816.8, 333.3], rotation: [0, 0, 0],
  scale: [0.647, 0.647, 0.647], listed: true, prefab: null, referencedBy: [], attachedTo: null, landingRole: null, landingActor: false,
  template: 'Fog_Cones.HeadLight_Beam_Cheap', system: 'URB_Bar|Fog_Cones.HeadLight_Beam_Cheap', hidden: false,
  floors: [{ building: '11326', floor: 1 }], lit: false, startsOn: true, startsOnFrom: 'class',
  parameters: [{ name: 'Brightness', type: 'PSPT_Scalar', scalar: 0.5, offered: 'otherKind' },
               { name: 'Color', type: 'PSPT_Vector', vector: [1.2, 1.0, 0.5], offered: 'yes' }],
  parametersFrom: 'actor', carriedBy: null, carriedHow: null, can: { move: true, copy: true, delete: true, values: true }, why: {},
};
const data = {
  buildings: [{ id: '11326', actor: 'XComBuildingVolume_0' }],
  effectSystems: { 'URB_Bar|Fog_Cones.HeadLight_Beam_Cheap': {
    name: 'HeadLight_Beam_Cheap', emitters: [{ kind: null, lods: 0 }, { kind: 'sprite', lods: 1, loops: 1, bursts: 1 }],
    offers: [{ name: 'Color', kind: 'vector', colour: true }, { name: 'Brightness', kind: 'vector', colour: false }], fixedBox: null } },
  soundWaves: { 'URB_Bar|SoundParticleObjects.DropshipIdle': { path: 'SoundParticleObjects.DropshipIdle', name: 'DropshipIdle', seconds: 12.5, channels: 1, rate: 44100, playable: true } },
};
data.effects = [beam];

// ---- names and chips
assert.equal(recordName(beam, data), 'HeadLight_Beam_Cheap');
const chips = recordChips(beam, data).map(c => c.text);
assert.deepEqual(chips, ['Hides with XComBuildingVolume_0, floor 1']);
const off = { ...beam, startsOn: false, startsOnFrom: 'actor', referencedBy: ['SeqAct_Toggle_1 Target'], prefab: 'PrefabInstance_12', carriedBy: `${PL}XComLevelActor_116`, floors: [] };
assert.deepEqual(recordChips(off, data).map(c => c.text), ['Starts off', 'Named by the mission\'s script', 'Carried by XComLevelActor_116', 'Placed by a prefab']);
assert.equal(recordChips(off, data)[1].title, 'SeqAct_Toggle_1 Target');
// the landing's: the landing chip, not the carrying one
assert.deepEqual(recordChips({ ...off, landingRole: 'emitter', startsOn: true, referencedBy: [], prefab: null }, data).map(c => c.text), ['The landing\'s']);
const riding = { ...beam, floors: [], attachedTo: { actor: `${PL}XComUniverseCenter_0`, actorClass: 'XComUniverseCenter', bone: null },
                 can: { move: false, copy: false, delete: false, values: false },
                 why: { move: 'it rides on XComUniverseCenter_0 and moves with it', copy: 'it rides on XComUniverseCenter_0 and moves with it' } };
assert.deepEqual(recordChips(riding, data).map(c => c.text), ['Rides on XComUniverseCenter_0']);

// ---- the panel's lines
let { title, lines } = recordLines(beam, data);
assert.equal(title, 'Effect: HeadLight_Beam_Cheap');
assert.equal(lines[0], 'Emitter_4 (Emitter).');
assert.equal(lines[1], 'Plays Fog_Cones.HeadLight_Beam_Cheap: 1 emitter (sprites).');
assert.equal(lines[2], 'Starts with the mission (as its class has it).');
assert.equal(lines[3], 'Drawn at 0.647 times its size.');
assert.ok(lines.includes('Bounds unavailable: its system saves no fixed box, so the game works its size out as it plays.'));
assert.ok(!lines.some(l => l.startsWith('View only')));
assert.ok(recordLines(riding, data).lines.includes('View only: it rides on XComUniverseCenter_0 and moves with it.'));
const boxed = { ...data, effectSystems: { [beam.system]: { ...data.effectSystems[beam.system], fixedBox: { used: true, valid: true, min: [-60, -60, -1], max: [60, 60, 200] } } } };
assert.ok(recordLines(beam, boxed).lines.includes('Its box is the system\'s fixed bounds: 120 × 120 × 201 units before scaling.'));
assert.ok(recordLines({ ...beam, scale: [0.35, 0.35, 0.5] }, data).lines.includes('Drawn at 0.35 × 0.35 × 0.5 times its size (unevenly).'));

// ---- parameters: a colour only where the system's parameter feeds a colour (or the map saved a colour)
const rows = parameterRows(beam, data);
assert.deepEqual(rows.map(r => [r.name, r.kind, r.text]), [['Brightness', 'scalar', '0.5'], ['Color', 'colour', '1.2, 1, 0.5']]);
assert.deepEqual(rows[1].colour, [1, 1, 0.5]);           // clamped for the swatch; the text keeps the map's value
assert.equal(rows[0].note, 'its system reads Brightness as a vector, and takes this number for each part of it');
const odd = parameterRows({ ...beam, parameters: [{ name: 'Wind', type: 'PSPT_ScalarRand', scalar: 2, scalarLow: 1, offered: 'no' },
                                                  { name: 'Tint', type: 'PSPT_Color', colour: [0.2, 0.4, 0.6, 1], offered: 'yes' },
                                                  { name: 'Size', type: 'PSPT_Vector', vector: [2, 2, 2], offered: 'yes' }] }, data);
assert.deepEqual(odd.map(r => [r.kind, r.text]), [['range', '1 to 2'], ['colour', '0.2, 0.4, 0.6'], ['vector', '2, 2, 2']]);
assert.equal(odd[0].note, 'its system has no parameter of that name');

// ---- sounds
const sky = { kind: 'sound', id: 'sound:10', actor: `${PL}AmbientSoundSimpleToggleable_0`, actorClass: 'AmbientSoundSimpleToggleable', location: [560, -2971, 0],
              listed: true, referencedBy: [], landingRole: 'sound', startsOn: true, startsOnFrom: 'archetype',
              cue: { path: `${PL}AmbientSoundSimpleToggleable_0.SoundCue_0`, private: true, sharedBy: 0 },
              waves: ['URB_Bar|SoundParticleObjects.DropshipIdle'], noSound: null,
              values: { radiusMin: 500, radiusMax: 2000, volumeMin: 0.7, volumeMax: 0.7, pitchMin: 1, pitchMax: 1, attenuate: true },
              valuesFrom: { radiusMax: 'archetype' }, can: { move: false, audition: true }, why: { move: 'it is the landing\'s' } };
assert.equal(recordName(sky, data), 'DropshipIdle');
assert.deepEqual(soundReach(sky), { inner: 500, outer: 2000 });
({ title, lines } = recordLines(sky, data));
assert.equal(title, 'Sound: DropshipIdle');
assert.ok(lines.includes('Plays SoundParticleObjects.DropshipIdle: 12.5 s, mono, 44,100 samples a second.'));
assert.ok(lines.includes('Heard at full volume within 500 units, fading out by 2,000 (as its archetype has it).'));
assert.ok(lines.includes('Volume 0.7, pitch 1.'));
const silent = { ...sky, waves: [], noSound: 'a sound slot names no wave', landingRole: null };
assert.equal(recordName(silent, data), 'No sound set');
assert.ok(recordChips(silent, data).some(c => c.text === 'No sound set'));
assert.ok(recordLines(silent, data).lines.includes('Silent: a sound slot names no wave.'));
const hum = { ...sky, landingRole: null, cue: { path: 'SoundAmbience.StasisPodCollectibleCue', private: false, sharedBy: 18 },
              values: { radiusMin: 400, radiusMax: 800, attenuate: true }, valuesFrom: { radiusMax: 'cue' } };
assert.ok(recordChips(hum, data).find(c => c.text === 'Shared cue').title.includes('19 sounds of the map play it'));
assert.ok(recordLines(hum, data).lines.includes('Its cue is SoundAmbience.StasisPodCollectibleCue, a game asset that 18 other sounds of the map play too.'));
assert.equal(soundReach({ ...hum, values: { attenuate: false, radiusMax: 800 } }), null);
assert.equal(soundReach({ ...hum, values: {} }), null);
assert.equal(soundReach(beam), null);

// ---- a cleared map keeps the landing's, a moved carrier's effects and (when asked) the scenery outside; sounds go
const outsideOf = x => x < -1000;
assert.ok(survivesClear(beam, { cleared: false }));
assert.ok(!survivesClear(beam, { cleared: true, outside: () => false }));
assert.ok(survivesClear(beam, { cleared: true, outside: outsideOf }));                   // x -1669: outside the play area
assert.ok(!survivesClear({ ...sky, landingActor: false }, { cleared: true, outside: () => false }));     // a sound goes
assert.ok(survivesClear({ ...sky, landingActor: false, location: [-1669, 0, 0] }, { cleared: true, outside: outsideOf }));
assert.ok(survivesClear({ ...sky, landingActor: true }, { cleared: true, outside: () => false }));       // the landing's
assert.ok(survivesClear({ ...beam, landingActor: true }, { cleared: true }));
assert.ok(survivesClear(off, { cleared: true, carrierMoved: true }));
assert.ok(!survivesClear(off, { cleared: true, carrierMoved: false, outside: () => false }));
// (FX3) an effect the project moves itself stays, as the Build keeps it
assert.ok(survivesClear(beam, { cleared: true, moved: true, outside: () => false }));
assert.ok(survivesClear({ ...beam, stream: 'URB_Bar_Stream' }, { cleared: true }));      // a stream's own: never cleared

// ---- the records of an export and its streams
const exported = { ...data, sounds: [sky], flares: [], streams: { S: { effects: [{ ...beam, id: 'stream-S-effect:1', stream: 'S' }] }, T: { sounds: [sky] } } };
assert.deepEqual(effectRecords(exported, null).map(r => r.id), ['effect:2158', 'sound:10']);
assert.deepEqual(effectRecords(exported, new Set(['S'])).map(r => r.id), ['effect:2158', 'sound:10', 'stream-S-effect:1']);
assert.deepEqual(effectRecords({ effects: [{ actor: 'x' }] }, null), []);                 // export 23's records: no kind
assert.deepEqual(effectRecords(null, null), []);

// ---- values (stage FX5)
const glowSystems = { 'URB_Bar|FX.Glow': { emitters: [], offers: [
  { name: 'Brightness', kind: 'vector', colour: false, modes: ['DPM_Direct'], constant: [1, 1, 1] },
  { name: 'Color', kind: 'vector', colour: true, modes: ['DPM_Direct'], constant: [1, 1, 1] },
  { name: 'Opacity', kind: 'scalar', modes: ['DPM_Direct'], constant: 1, input: [0, 1], output: [0, 1] },
  { name: 'Speed', kind: 'scalar', modes: ['DPM_Normal'], constant: 1, input: [0, 4], output: [0, 1] },
  { name: 'Size', kind: 'scalar', modes: ['DPM_Direct'], constant: 1 }, { name: 'Size', kind: 'vector', colour: false, constant: [1, 1, 1] }] } };
const glow = { ...beam, system: 'URB_Bar|FX.Glow', parameters: [
  { name: 'Brightness', type: 'PSPT_Scalar', scalar: 0.5, offered: 'otherKind' },
  { name: 'Color', type: 'PSPT_Vector', vector: [1.5, 0.75, 0], offered: 'yes' },
  { name: 'Tint', type: 'PSPT_Color', colour: [1, 0, 0, 1], offered: 'no' },
  { name: 'Wobble', type: 'PSPT_ScalarRand', scalar: 1, scalarLow: 0.5, offered: 'no' },
  { name: 'Color', type: 'PSPT_Scalar', scalar: 9, offered: 'otherKind' }] };
const controls = parameterControls(glow, glowSystems);
// saved ones first in the type they are saved in (a scalar where the distribution is a vector stays a scalar); the
// first of a name only; then what the system offers that it doesn't save, in the distribution's kind
assert.deepEqual(controls.map(c => [c.name, c.control, c.type]), [
  ['Brightness', 'scalar', 'PSPT_Scalar'], ['Color', 'tint', 'PSPT_Vector'], ['Tint', 'colour', 'PSPT_Color'],
  ['Wobble', 'other', 'PSPT_ScalarRand'], ['Opacity', 'scalar', 'PSPT_Scalar'], ['Size', 'other', 'PSPT_None'], ['Speed', 'scalar', 'PSPT_Scalar']]);
assert.match(controls[3].readOnly, /scalarrand parameter/);
assert.match(controls[5].readOnly, /both as a number and as a vector/);
// a slider's guide: a Direct parameter from 0 past twice its value; a Normal one its input range
assert.deepEqual(controls.find(c => c.name === 'Opacity').guide, [0, 2]);
assert.deepEqual(controls.find(c => c.name === 'Speed').guide, [0, 4]);
assert.deepEqual(controls.find(c => c.name === 'Opacity').base, 1);
// a value outside the guide widens it, never the other way round
assert.deepEqual(parameterControls(glow, glowSystems, { Speed: 9 }).find(c => c.name === 'Speed').guide, [0, 9]);
// edits show as edited; a read-only one can't be
const edited = parameterControls(glow, glowSystems, { Opacity: 0.25, Wobble: 3 });
assert.deepEqual([edited.find(c => c.name === 'Opacity').value, edited.find(c => c.name === 'Opacity').edited], [0.25, true]);
assert.equal(edited.find(c => c.name === 'Wobble').edited, false);
// a vector named for a colour is a tint whatever reads it (P_Power_Core_Persistent's Color scales its colour over
// life); a colour scale that is no colour (Brightness) keeps its three numbers, called red, green and blue
const core = { ...beam, system: 'F|Core', parameters: [] };
const coreSystems = { 'F|Core': { emitters: [], offers: [
  { name: 'Color', kind: 'vector', colour: false, module: 'ParticleModuleColorScaleOverLife', modes: ['DPM_Direct'], constant: [0.2, 1, 0.1] },
  { name: 'Brightness', kind: 'vector', colour: false, module: 'ParticleModuleColorScaleOverLife', modes: ['DPM_Direct'], constant: [1, 1, 1] },
  { name: 'Acceleration', kind: 'vector', colour: false, module: 'ParticleModuleAcceleration', modes: ['DPM_Direct'], constant: [20, 0, 0] }] } };
const coreControls = parameterControls(core, coreSystems);
assert.deepEqual(coreControls.map(c => [c.name, c.control, c.channels]), [['Acceleration', 'vector', false], ['Brightness', 'vector', true], ['Color', 'tint', false]]);
assert.ok(colourNamed('Dark_Color') && colourNamed('colour') && colourNamed('Tint') && !colourNamed('Brightness') && !colourNamed(undefined));
assert.deepEqual(parameterRows({ ...core, parameters: [{ name: 'Color', type: 'PSPT_Vector', vector: [0.2, 1, 0.1], offered: 'yes' }] }, { effectSystems: coreSystems })[0].kind, 'colour');
// a colour saved with a vector and no colour field shows that vector (URB_Bar's webbing)
const webbing = parameterControls({ ...core, parameters: [{ name: 'Color', type: 'PSPT_Color', vector: [0.12, 0.18, 0.1], offered: 'yes' }] }, coreSystems);
assert.deepEqual(webbing.find(c => c.name === 'Color').base, [0.12, 0.18, 0.1, 1]);
// a tint: its colour and strength, and back
assert.deepEqual(tintOf([1.5, 0.75, 0]), { colour: [1, 0.5, 0], strength: 1.5 });
assert.deepEqual(tintVector([1, 0.5, 0], 3), [3, 1.5, 0]);
assert.deepEqual(tintOf([0, 0, 0]), { colour: [1, 1, 1], strength: 0 });

// the record as edited: an effect's size and starting state, a parameter changed and one added
const now = withValues(glow, { scale: 2, startsOn: false, parameters: { Brightness: 2, Opacity: 0.5 } }, glowSystems);
assert.deepEqual([now.startsOn, now.startsOnFrom, now.drawScale, now.scale], [false, 'edited', 2, [1.294, 1.294, 1.294]]);
assert.deepEqual(now.parameters.filter(p => ['Brightness', 'Opacity'].includes(p.name)).map(p => [p.name, p.type, p.scalar]),
                 [['Brightness', 'PSPT_Scalar', 2], ['Opacity', 'PSPT_Scalar', 0.5]]);
assert.equal(glow.parameters[0].scalar, 0.5);                 // the export's record untouched
assert.match(recordLines(now, { effectSystems: glowSystems }).lines.join(' '), /Starts off \(as set here\)/);
assert.equal(withValues(glow, null, glowSystems), glow);
// a sound's
const humming = { kind: 'sound', actor: `${PL}AmbientSoundSimple_0`, values: { radiusMin: 300, radiusMax: 750, volumeMin: 1, volumeMax: 1, pitchMin: 1, pitchMax: 1, attenuate: true },
              valuesFrom: { radiusMin: 'actor', radiusMax: 'actor' }, can: { values: true } };
const louder = withValues(humming, { radiusMax: 1200, volume: [0.5, 0.8] });
assert.deepEqual(soundReach(louder), { inner: 300, outer: 1200 });
assert.deepEqual([louder.values.volumeMin, louder.values.volumeMax, louder.valuesFrom.radiusMax, louder.valuesFrom.volumeMin], [0.5, 0.8, 'edited', 'edited']);
assert.equal(humming.values.radiusMax, 750);

// what a project saves, and back
assert.deepEqual(savedValues({ scale: 2, parameters: { Size: [1, 2, 3], Opacity: 0.5 }, startsOn: null }),
                 { scale: 2, parameters: [{ name: 'Opacity', value: 0.5 }, { name: 'Size', value: [1, 2, 3] }] });
assert.equal(savedValues({ parameters: {} }), null);
assert.equal(savedValues(null), null);
assert.deepEqual(keptValues({ follow: 'none', scale: 2, parameters: [{ name: 'Opacity', value: 0.5 }] }), { scale: 2, parameters: { Opacity: 0.5 } });
assert.equal(keptValues({ follow: 'none' }), null);
// why values can't be set
assert.equal(valuesViewOnly(glow), null);
assert.equal(valuesViewOnly({ ...humming, can: { values: false }, why: { values: 'its cue Hum is a game asset, not its own' } }), 'its cue Hum is a game asset, not its own');
assert.match(valuesViewOnly({ kind: 'flare' }), /lens flare/);

console.log('effects_rules: ok');
