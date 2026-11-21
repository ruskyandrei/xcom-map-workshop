// Play in game (tools/viewer/play.py, installs.py, gamelaunch.py; taking it out again is the Game maps window's, gamemaps.js): the game started straight in
// a battle on the open map, or on the open project's build, in the game install the settings name (the install
// setting, else the game install the editor reads: LWR or plain Enemy Within), and everything the editor installed for
// that taken back out. The Game menu (the arrow beside Play) also shows the installs the editor works with: the game install it reads, the
// install it plays in, how the game is started there, and what the editor has installed in it.
import { call } from './api.js';

export const playApi = {
  status: () => call('GET', '/play.json'),
  start: request => call('POST', '/play/start', request),   // {project: id} or {map: id}
};

/** Why the game can't be played now, going by the server's play status (null: it can, or it isn't known yet). */
export const playBlocked = s => (!s ? null : s.error ?? (!s.install?.ready ? s.install?.why ?? 'asking the server' : s.launch && !s.launch.how ? s.launch.why : null));
/** A play's mission as the server takes it: a record's index, or an added kind (a value `kind:<kind>`). */
export const missionRequest = value => (String(value).startsWith('kind:') ? String(value).slice(5) : Number(value) || 0);
// The "Starting XCOM" message: what is played, what to do at the main menu when saving is on, and anything the play
// goes without or should know, one short paragraph each.
export function playedMessage(r, mapLabel) {
  const p = r.played;
  const what = (p.kind === 'project' ? `${p.project?.name}, revision ${p.project?.revision}${p.quick ? ' (lighting not baked)' : ''}`
    : `${mapLabel(p.map)} (original map)`) + (p.mission?.label ? `, ${p.mission.label}` : '');
  return [
    p.how === 'dry' ? `Starting XCOM is left out here (serve --dry-play): ${what}.` : `Starting XCOM: ${what}.`,
    p.how === 'steam' ? 'Pick Enemy Within if the game\'s launcher asks.' : null,
    p.saving ? `At the main menu, press ${p.saving.key} to start the battle.` : null,
    p.squad ? `Squad: ${p.squad.name}, ${p.squad.count} unit${p.squad.count === 1 ? '' : 's'}${p.squad.warnings?.length
      ? ` (${p.squad.warnings.length} warning${p.squad.warnings.length === 1 ? '' : 's'}: Test squad setup lists them)` : ''}.` : null,
    ...(p.mission?.missing ?? []),
    p.note,
  ].filter(Boolean).join('\n');
}

/** One thing the editor installed, in a few words. */
const installedName = i => i.kind === 'map' ? `a record for ${i.map} (its own are commented out)`
  : `${i.project?.name ?? 'a project'}, revision ${i.project?.revision} (${i.map})${i.quick ? ', lighting not baked' : ''}`;

/** What the editor has in the install, in a few words; null when that isn't known. */
export function inGame(game, mapLabel) {
  if (!game) return null;
  const parts = game.installed.map(installedName);
  // the project manager's installs for campaigns (manager.js)
  for (const r of game.rotation ?? []) parts.push(`${r.project?.name ?? r.variant} ${r.mode === 'replace' ? `in place of ${r.base}` : `in the rotation beside ${r.base}`}`);
  if (game.switchedOff) parts.push(`${game.switchedOff} map record${game.switchedOff === 1 ? '' : 's'} switched off`);
  return parts.length ? parts.join('; ') : 'Nothing of the editor\'s';
}

/** The Installs section of the Game menu, from /play.json (or {error, unavailable}). */
export function renderInstalls(el, status, mapLabel) {
  el.replaceChildren();
  const row = (term, value, title, warn = false) => {
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = term;
    // a long path breaks after its backslashes rather than anywhere
    value.split(/(?<=\\)/).forEach((part, i) => { if (i) dd.append(document.createElement('wbr')); dd.append(part); });
    if (title) dt.title = dd.title = title;
    if (warn) dd.className = 'warn';
    el.append(dt, dd);
  };
  if (status.error) { row('', status.unavailable ? 'This server starts no game.' : `Not known: ${status.error}`); return; }
  const { lwr, install, launch, game } = status;
  row('Game', lwr.folder ? `${lwr.folder}${lwr.kind ? ` (${lwr.kind})` : ''}` : lwr.note,
      lwr.folder ? `The game install the editor reads maps and their records from: LWR or plain Enemy Within (the game setting: ${lwr.setting})`
                 : 'Choose it with Game install and checks in Settings (the gear)',
      !lwr.folder);
  const where = install.sameAsLwr ? 'The game install' : install.folder ?? install.note;
  row('Plays in', install.ready ? where : `${where} · ${install.why}`,
      `The install Play in game starts, and installs a project's build into (${install.source}; python tools/viewer/viewer.py settings --install <game folder> picks another). It does both only while XCOM is closed`,
      !install.ready);
  if (launch) row('Started', launch.how === 'steam' ? 'Through Steam' : launch.how === 'direct' ? 'By its own XComEW.exe'
      : launch.how === 'dry' ? 'Not at all: this server only prepares a play (serve --dry-play)' : `Not possible: ${launch.why}`,
      launch.how === 'steam' ? 'Steam starts the game with the map to open; if the game\'s launcher asks which game, pick Enemy Within'
        : launch.how === 'direct' ? 'The game folder is in no Steam library, so its XComEW.exe is started with the map to open' : '',
      !launch.how);
  row('In the game', inGame(game, mapLabel) ?? (status.gameError ? `Not known: ${status.gameError}` : 'Not known'),
      game ? `What the editor has installed there: a project's build is installed under its own name, with a map record of its own that no campaign draws. A map of the game's needs nothing installed, but for one whose records the game comments out (the tutorial's map), which gets a copy of one. Game maps (the arrow beside Play) shows it and takes any of it out${game.configKept ? '. The game\'s XComContent.ini is kept aside for a play and goes back once the game has closed' : ''}` : '');
}
