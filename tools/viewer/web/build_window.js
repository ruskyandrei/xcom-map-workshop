// The build window's words (review finding 22: moved out of app.js, which draws them): what a build status from the
// server (tools/viewer/builds.py, tools/editor/build.py's stages) says, worked out without the page, so the node tests
// read it. app.js renderBuild puts these in the window's elements.
import { clock } from './build_queue.js';
import { sentence } from './dom_words.js';

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const kilobytes = bytes => (bytes >= 1 << 20 ? `${(bytes / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
const copyCount = n => (n === 1 ? '1 copy' : `${n} copies`);

/** The build's steps in order: [stage key, label]. */
export const BUILD_ROWS = [['snapshot', 'Read the project and its base map'], ['compile', 'Compile the edit'],
  ['patch', 'Build and cook the patch in UDK'], ['transplant', 'Bring the pieces from other maps'], ['light', 'Make the edit in the map and bake its lighting'],
  ['package', 'Write the variant folder']];
/** Seconds from time `a` to time `b` (ISO strings; no `b`: now), never below 0. */
export const secondsBetween = (a, b) => Math.max(0, ((b ? new Date(b).getTime() : Date.now()) - new Date(a).getTime()) / 1000);

/** The Build's light counts (build.py light_counts) in words: placed lights moved, changed, added and deleted, and the
 *  glow lights following their pieces. */
export function lightWords(l) {
  if (!l) return '';
  const placed = [l.moved && `${l.moved} moved`, l.changed && `${l.changed} changed`,
                  l.added && `${l.added} added${l.recipeSpots ? ` (${l.recipeSpots} from the recipe)` : ''}`, l.deleted && `${l.deleted} deleted`];
  const glow = l.area ? (l.area.moved || 0) + (l.area.copied || 0) + (l.area.deleted || 0) : 0;
  return [placed.some(Boolean) && `lights ${placed.filter(Boolean).join(', ')}`,
          glow && `${plural(glow, 'glow light')} following ${plural(l.area.pieces?.length ?? 0, 'piece')}`].filter(Boolean).join('; ');
}
/** The writer's record of pieces' flags (build.py flag_record) in words: the pieces written and read back, any it
 *  refused. */
export function flagWords(f) {
  if (!f) return '';
  const pieces = (f.inPlace ?? 0) + (f.onCopies ?? 0) - (f.refused?.length ?? 0);
  return [`flags written on ${plural(pieces, 'piece')}`, f.regions && `${plural(f.regions, 'tile region')} worked out again`,
          f.refused?.length && `not written on ${f.refused.join(', ')}`].filter(Boolean).join(', ');
}
/** A step's line under its name: what it made once done, or what it is doing while it runs (`running`). */
export function stepDetail(key, stage, job, running) {
  if (key === 'compile' && stage) {
    const say = (parts, where) => ((parts = parts.filter(Boolean)).length ? `${parts.join(' and ')} ${where}` : '');
    return [say([stage.nativeCopies && copyCount(stage.nativeCopies), stage.hides && plural(stage.hides, 'hidden piece')], 'made in the map'),
            say([stage.copierCopies && copyCount(stage.copierCopies), stage.patchHides && plural(stage.patchHides, 'hidden piece')], 'for the patch'),
            lightWords(stage.lights), stage.pieceFlags && `${plural(stage.pieceFlags, 'piece')} with flags changed in place`,
            stage.leftOut ? `${plural(stage.leftOut, 'piece')} left out (listed below)` : '']
      .filter(Boolean).join('; ');
  }
  if (key === 'patch' && stage?.bytes) return `${Math.round(stage.bytes / 1024)} KB cooked`;
  if (key === 'transplant' && stage) {
    // pieces, and effects and sounds (effects and sounds plan, FX4) and lens flares (FX6b: counted among the
    // effects, and of their own), each donor's actors staged once
    const sum = k => stage.donors.reduce((n, d) => n + (d[k] ?? 0), 0), pieces = sum('pieces'), flares = sum('flares'), effects = sum('effects') - flares;
    const what = [pieces && plural(pieces, 'piece'), effects && `${effects} ${effects === 1 ? 'effect or sound' : 'effects and sounds'}`,
                  flares && plural(flares, 'lens flare')]
      .filter(Boolean).join(' and ') || plural(stage.foreignPieces, 'piece');
    return `${what} from ${stage.donors.map(d => d.map).join(', ')}: ${kilobytes(sum('bytes'))} more in the map`;
  }
  if (key === 'light' && stage?.baked === false)    // a quick build's: the edit made, nothing relit
    return [stage.nativeCopies && `${copyCount(stage.nativeCopies)} made`, stage.hidden && `${stage.hidden} taken out`,
            stage.lights && 'light edits made', flagWords(stage.pieceFlags), 'lighting not baked'].filter(Boolean).join(', ');
  // a build whose light edits change no texel (a light added switched off) keeps the map's lighting
  if (key === 'light' && stage?.lightingUnchanged) return ['lighting unchanged: no texel to relight', flagWords(stage.pieceFlags)].filter(Boolean).join('; ');
  if (key === 'light' && stage) return [`${plural(stage.written, 'piece')} relit`, `${stage.unchanged} unchanged`,
                                        stage.hidden && `${stage.hidden} taken out`, flagWords(stage.pieceFlags),
                                        stage.otherPiecesChanged && `${plural(stage.otherPiecesChanged.count, 'piece')} not relit changed too (below)`]
    .filter(Boolean).join(', ');
  if (!running) return '';
  const p = job.progress;
  if (p) return sentence(p.total ? `${p.what}: ${p.done} of ${p.total}` : `${p.what}…`);
  return job.running ? `${sentence(job.running)}…` : '';
}

/** The window's step list for a build status: [{ key, label, state ('done', 'now', 'failed', 'todo'), detail,
 *  progress (0 to 1, or null), time (words: the step's time, or '') }]. The patch's step shows only once the compile
 *  leaves the patch something (no project the compiler accepts does today: its edit is made in the map itself), the
 *  transplant's only for pieces from other maps. */
export function buildSteps(status) {
  const job = status.job, running = status.state === 'running', built = status.state === 'built', quick = Boolean(job.quick);
  const stages = Object.fromEntries((job.stages || []).map(s => [s.stage, s]));
  const compiled = stages.compile;
  const patchMade = Boolean(stages.patch ? !stages.patch.skipped : compiled?.copierCopies || compiled?.patchHides);
  const rows = [];
  let from = job.startedAt, reached = false;
  for (const [key, label] of BUILD_ROWS) {
    const end = key === 'package' ? (built ? job.finishedAt : null) : stages[key]?.at;
    if (key === 'patch' && !patchMade) { if (end) from = end; continue; }
    if (key === 'transplant' && !(stages.transplant || compiled?.foreignCopies)) continue;
    const state = end ? 'done' : reached ? 'todo' : running ? 'now' : built ? 'done' : 'failed';
    if (state === 'now' || state === 'failed') reached = true;
    rows.push({ key, state, label: key === 'light' && quick ? 'Make the edit in the map (lighting not baked)' : label,
                detail: stepDetail(key, stages[key], job, state === 'now'),
                progress: state === 'now' && job.progress?.total ? job.progress.done / job.progress.total : null,
                time: ['done', 'now', 'failed'].includes(state) ? clock(secondsBetween(from, end ?? job.finishedAt)) : '' });
    if (end) from = end;
  }
  return rows;
}

/** The pieces the compiler left out (plan "sturdier prefabs", R4) and those the Build itself could not make (its
 *  `leftout` stage, build.py drop_untried): null for none, else { head, rows (at most 50: { message, actor }), more
 *  (the line for the rest, or null) }. The head's count and the "… and N more" line's agree. */
export function leftOutList(status) {
  const job = status.job, running = status.state === 'running', built = status.state === 'built';
  const stages = Object.fromEntries((job.stages || []).map(s => [s.stage, s])), compiled = stages.compile;
  const gone = [...(compiled?.leftOutPieces ?? []), ...(stages.leftout?.pieces ?? [])];
  if (!gone.length) return null;
  const count = (compiled?.leftOut ?? compiled?.leftOutPieces?.length ?? 0) + (stages.leftout?.count ?? 0) || gone.length;
  const shown = Math.min(gone.length, 50);
  return { head: `${plural(count, 'piece')} left out of this build: ${gone.length === 1 ? 'it' : 'they'} can't be built. The rest ${running ? 'is being built' : built ? 'is built' : 'was being built'}.`,
           rows: gone.slice(0, 50), more: count > shown ? `… and ${count - shown} more (the build's compile-report.json has them all)` : null };
}

/** What the edit does to the missions the variant keeps (the compiler's mission warnings, mission types plan C3), by
 *  mission: null for none, else { head, missions: [[mission, rows]], more }. Warnings only: the build goes on. */
export function missionWarnings(status) {
  const compiled = (status.job.stages || []).find(s => s.stage === 'compile');
  const warned = compiled?.missionWarnings ?? [];
  if (!warned.length) return null;
  const count = compiled.missionWarningCount ?? warned.length, byMission = new Map();
  for (const row of warned) { if (!byMission.has(row.mission)) byMission.set(row.mission, []); byMission.get(row.mission).push(row); }
  return { head: `${plural(count, 'mission warning')}: what the edit does to ${byMission.size === 1 ? 'a mission' : `${byMission.size} missions`} the variant keeps. The build goes on; move the piece, or drop the mission from the project.`,
           missions: [...byMission], more: count > warned.length ? `… and ${count - warned.length} more (the build's compile-report.json has them all)` : null };
}

/** The bar: the time so far against the last build's of the same kind (`estimate`, seconds, or none), or a moving bar
 *  when there is none to go by. { className, share (0 to 1), text }. */
export function buildBar(status, estimate, elapsed) {
  const running = status.state === 'running', built = status.state === 'built', quick = Boolean(status.job.quick);
  const share = running ? (estimate ? Math.min(elapsed / estimate, 0.97) : 0.3) : built ? 1 : Math.min(elapsed / (estimate || elapsed || 1), 1);
  const last = quick ? 'the last unbaked build' : 'the last baked build';
  const text = !running ? '' : !estimate ? `This project hasn't had ${quick ? 'an unbaked' : 'a baked'} build before, so there is no time to go by.`
    : elapsed < estimate ? `About ${clock(estimate - elapsed)} left, going by ${last} (${clock(estimate)}).`
    : `Taking longer than ${last} (${clock(estimate)}).`;
  return { className: `buildbar ${status.state}${running && !estimate ? ' indeterminate' : ''}`, share, text };
}

/** The log as the window shows it: its latest four lines (the tools' own records and commands left out), or all the
 *  server keeps (`full`: the last 40); '…' for none yet. */
export function logText(job, full) {
  const lines = (job.lines || []).filter(l => !/^\w+: \{/.test(l) && !l.trimStart().startsWith('$ ')).map(l => l.trim()).filter(Boolean);
  return (full ? job.lines || [] : lines.slice(-4)).join('\n') || '…';
}
