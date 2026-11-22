// The Map settings window's background sound rules (background_sound_rules.js): the choices, what plays now, the
// project's record (null for the map's own at its own volume) and the preview's volume.
import assert from 'node:assert/strict';
import { bedLabel, ownVolume, previewVolume, soundChoices, soundNow, soundRecord, volumeWords } from '../web/background_sound_rules.js';

const BAR = 'SoundAmbience-NorthAmerica.LightWindTrafficPaperCue', FOREST = 'SoundAmbience-NorthAmerica.ForestAmbienceCue';
const beds = [{ cue: FOREST, label: 'Forest' }, { cue: BAR, label: 'Light wind, traffic and paper' },
              { cue: 'SoundHarbor.HarborCue', label: 'Harbour' }];
const own = { cue: BAR, volume: null };

assert.equal(ownVolume(own), 1);
assert.equal(ownVolume({ cue: BAR, volume: 0.5 }), 0.5);
assert.equal(bedLabel(beds, FOREST), 'Forest');
assert.equal(bedLabel(beds, 'Some.OtherCue'), 'Other');

// the map's own first, the others in the list's order, None last
assert.deepEqual(soundChoices(beds, own), [
  { value: BAR, label: "Light wind, traffic and paper (this map's)" }, { value: FOREST, label: 'Forest' },
  { value: 'SoundHarbor.HarborCue', label: 'Harbour' }, { value: '', label: 'None' }]);
// a cue the list lacks is still the map's own choice
assert.equal(soundChoices(beds, { cue: 'X.WindCue' })[0].label, "Wind (this map's)");
assert.equal(soundChoices(beds, { cue: 'X.WindCue' }).length, 5);

// what plays now
assert.deepEqual(soundNow(null, own), { cue: BAR, volume: 1 });
assert.deepEqual(soundNow({ cue: FOREST }, own), { cue: FOREST, volume: 1 });
assert.deepEqual(soundNow({ cue: null, volume: 0.5 }, own), { cue: null, volume: 0.5 });

// the record: none for the map's own at its own volume; the volume only where it differs
assert.equal(soundRecord(BAR, 1, own), null);
assert.equal(soundRecord(BAR, 1.002, own), null);
assert.deepEqual(soundRecord(FOREST, 1, own), { cue: FOREST });
assert.deepEqual(soundRecord(BAR, 0.5, own), { cue: BAR, volume: 0.5 });
assert.deepEqual(soundRecord(null, 1, own), { cue: null });
assert.deepEqual(soundRecord(FOREST, 1, { cue: BAR, volume: 0.5 }), { cue: FOREST, volume: 1 });
assert.deepEqual(soundRecord(FOREST, 0.35000000000000003, own), { cue: FOREST, volume: 0.35 });

assert.equal(previewVolume(1), 0.5);
assert.equal(previewVolume(2), 1);
assert.equal(previewVolume(3), 1);
assert.equal(previewVolume(0), 0);
assert.equal(volumeWords(0.85), '85%');
