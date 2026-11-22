// The map's background sound in the Map settings window (map_settings.js), as pure rules: the choices, the project's
// record for a choice and a volume, and what plays now. The map's own sound is export 39's `backgroundSound` ({ cue,
// volume, ... }: tools/viewer/background_sound.py); the game's beds are /background-sounds.json's rows ({ cue, label,
// map, maps, waves }); the project's record is project.js's validBackgroundSound: null for the map's own, else { cue: a
// cue's path or null (none), volume?: a multiplier }.

// The window's volume slider (the game's maps play their beds at 0.5 to 2; the compiler takes 0 to 4)
export const VOLUME_SLIDER = { min: 0, max: 2, step: 0.05 };
// A volume within this of another is the same (a slider's step is 0.05)
const SAME_VOLUME = 0.005;

/** The map's own volume: its sound's, else 1 (the game's default for a sound it doesn't save one for). */
export const ownVolume = own => (Number.isFinite(own?.volume) ? own.volume : 1);

/** A bed's label: the list's, else its name without its package and a trailing "Cue". */
export function bedLabel(beds, cue) {
  const row = beds.find(b => b.cue === cue);
  return row ? row.label : String(cue).split('.').pop().replace(/_?Cue$/, '') || String(cue);
}

/** The choices: [{ value, label }], the map's own first (marked), the game's other beds in the list's order, then
 *  None (value ''). A value is a cue's path. */
export function soundChoices(beds, own) {
  const out = [{ value: own.cue, label: `${bedLabel(beds, own.cue)} (this map's)` }];
  for (const b of beds) if (b.cue !== own.cue) out.push({ value: b.cue, label: b.label });
  out.push({ value: '', label: 'None' });
  return out;
}

/** What plays now: { cue (null: none), volume }, from the project's record and the map's own sound. */
export function soundNow(record, own) {
  if (!record) return { cue: own.cue, volume: ownVolume(own) };
  return { cue: record.cue, volume: Number.isFinite(record.volume) ? record.volume : ownVolume(own) };
}

/** The project's record for `cue` (null: none) at `volume`: null when it is the map's own sound at its own volume,
 *  else { cue, volume? }, the volume only where it is not the map's own. */
export function soundRecord(cue, volume, own) {
  const sameVolume = Math.abs(volume - ownVolume(own)) < SAME_VOLUME;
  if (cue === own.cue && sameVolume) return null;
  return { cue, ...(sameVolume ? {} : { volume: Number(volume.toFixed(4)) + 0 }) };
}

/** The preview's volume for the page's player (0 to 1): half the sound's multiplier, so the game's loudest bed (2) is
 *  the player's whole volume. */
export const previewVolume = volume => Math.max(0, Math.min(1, volume / 2));

/** A volume in words: a percentage. */
export const volumeWords = volume => `${Math.round(volume * 100)}%`;
