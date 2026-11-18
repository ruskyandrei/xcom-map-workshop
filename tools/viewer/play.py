"""Play in game and Remove from game, from the editor's Project menu, and which installs the editor works with.

Play in game starts the game straight in a battle on the open map, with no campaign to start and nothing of the
game's own changed (gamelaunch.py, EXP-29). The work on the install is installs.py's, on the game install the settings
name: the install setting, else the game install the editor reads (settings.install_game; LWR or plain Enemy Within).
With a project open, the page asks for the project's last package, once Build's panel has built it (baked or not) or
the user chose to play the last build as it is (offered when that is of what is on screen): the package is installed
under its own name first. With a map alone, the original map plays (no edits), and nothing is installed, but for a map
whose records the install comments out (the tutorial's map: installs.install_map_record). Remove from
game takes everything the editor put in the install back out. (The JSON keeps the names lwr and sameAsLwr for the game
install.)

  GET  /play.json     the game install the editor reads (and its kind), the install it plays in and whether that can
                      be played now (the reason when not), how the game would be started, and what the editor has
                      installed there
  POST /play/start    {"project": id}: the project's last package; {"map": id}: the original map; either
                      with "mission": which of its missions (the index of one of the map's records in the export's
                      `missions` order, or a kind a project added; absent, the first), and "saving": true for a battle
                      that can be saved (below)
  POST /play/remove   everything the editor installed taken back out

A play is the mission picked (private/plans/done/mission-types-plan.md, Part A): a project's play installs the
Build's own record for that mission, a map's needs nothing when the mission is the map's first record and otherwise
gets a copy of that record ahead of the map's own for the play (installs.install_map_record). The commands file then
has what that kind of mission needs on this path (missions.play_setup: the open line's options, the civilians' looks,
the UFO type, the council type), each only once its run in the game has shown it works, or all of them on a server
started with --try-mission-lines (EXP-53); the result's `mission` says what the play goes without.

Saving (F-89, EXP-56): a battle opened from the start-up commands, before the main menu's login, can't be saved. A play
with saving on (asked for, or a kind missions.play_setup says needs it: Long War's EXALT missions, F-109) starts the
game with START_FILE instead, which binds gamelaunch.SAVE_KEY to exec the play's commands file and opens nothing: the
game stays at its main menu, logs in there, and the key opens the battle. Exit to Main Menu and the key again opens it
anew.

A play keeps the game's XComContent.ini aside and a watch puts it back once the game has closed (installs.py says
why); a file still kept when the server starts, or at the next play, goes back then. A play with saving on keeps
XComInput.ini (the key) and profile.bin (the logged-in game writes the play's squad into the profile) aside the same
way. The game's saves get the same care (playsaves.py): a battle started without the login writes its save to save1
whatever is there, and broken, so once the game has closed a broken one is set aside out of the game's folder and a
save it replaced is put back; a whole one (saving on) stays where the game wrote it.

A play lands with the test squad (squads.py: the one squad of Settings, Test squad setup), resolved once against the
install played in before anything there changes (squadrecords.py), so a squad saved meanwhile waits for the next play;
a squad that can't be played there (its file unreadable, or errors such as a name the game can't take) stops the play
before it installs anything. Every play does this: a map, a project, Land here, saving on or off, a prefab test.
`played.squad` keeps its name, its units in a few words and its warnings and notes.

A play leaves nothing in the game: the same watch then takes out what the play put in (installs.clear_play: the
build's record, landing zones and files, the commands file), and so does the next play before it installs, and the
first look at the install (status) when a play's things are still there with the game closed (the server was stopped
meanwhile). What the project manager installed for campaigns is another ledger's and stays. A server that only
prepares a play (serve --dry-play) starts no game, so it leaves the play's things in to be looked at.
"""
from pathlib import Path
import threading
import time

import gamelaunch
import installs
import missions
import publication
import playsaves
import squadrecords
from projects import ProjectError
from squads import SquadError
from settings import documents, game_kind, game_setting, install_game, kind_label, lwr_game


class Player:
    def __init__(self, settings, builds=None, catalogue=None, projects=None, install=None, start=gamelaunch.start,
                 steam=gamelaunch.steam_exe, command=gamelaunch.command, user_documents=None, appear=300, every=3,
                 cleanup=True, try_lines=False, squads=None):
        """settings: the editor's settings (load_settings); install: a game folder that overrides the install setting
        (serve --install: tests use a scratch copy). builds: the BuildRunner; catalogue: the server's maps. start, steam
        and command: gamelaunch's, which tests and serve --dry-play replace (a dry play starts nothing); user_documents: the Documents folder the game keeps its settings
        under. appear: the seconds the watch waits for the game to come up (the game's launcher, where an install still has it, waits for a click); every:
        how often it looks. cleanup: whether a play's things are taken out of the game once it has closed (not for a
        dry play). try_lines: put in the mission commands not yet known to work (serve --try-mission-lines: EXP-53).
        squads: the test squad (squads.SquadService, set by the server once the player exists, as it plays in the
        player's install); None: no squad is set and the game's own lands (tests)."""
        self.settings, self.override = settings, Path(install) if install else None
        self.builds, self.catalogue, self.projects = builds, catalogue, projects
        self.start, self.steam, self.command, self.documents = start, steam, command, user_documents
        self.appear, self.every, self.cleanup, self.try_lines = appear, every, cleanup, try_lines
        self.lock, self.watching, self.stop_watch = threading.Lock(), None, None
        self.test_watching = None
        self.squads = squads

    def target(self):
        """(the game folder plays go to or None, what was found, where the choice came from)."""
        if self.override: return self.override, str(self.override), 'serve --install'
        game, note = install_game(self.settings)
        return game, note, 'the install setting' if self.settings['install'] is not None else 'the game install'

    def launch(self, game):
        """How the game would be started: dict(how='steam' or 'direct', why=None), or how None and why not ('dry':
        this server starts nothing)."""
        try: return dict(how=self.command(game, installs.PLAY_FILE, self.steam)[2], why=None)
        except gamelaunch.LaunchError as error: return dict(how=None, why=str(error))

    def status(self):
        lwr, note = lwr_game(self.settings)
        game, target_note, source = self.target()
        why = installs.ready(game) if game else target_note
        setting = game_setting(self.settings)
        out = dict(lwr=dict(setting=None if setting is None else str(setting),
                            folder=None if lwr is None else str(lwr), note=note,
                            kind=None if lwr is None else kind_label(lwr)),
                   install=dict(folder=None if game is None else str(game), note=target_note, source=source,
                                sameAsLwr=installs.same_folder(lwr, game), ready=why is None, why=why),
                   launch=None, game=None, tryMissionLines=self.try_lines)
        out['missionKinds'] = missions.kinds_for_page(self.content_text(game), self.try_lines,
                                                      lwr=game is not None and game_kind(game) == 'lwr')
        out['saveKey'] = gamelaunch.SAVE_KEY
        # the test squad in a few words, for the play dialog's line
        try: out['squad'] = self.squads.summary() if self.squads else None
        except (OSError, ValueError, ProjectError) as error: out['squad'] = dict(problem=str(error), playable=False)
        if game is not None:
            out['launch'] = self.launch(game)
            try: out['game'] = installs.status(game)
            except (OSError, ValueError, installs.InstallError) as error: out['gameError'] = str(error)
            # left from an earlier run: the config kept aside, or a play's things in the game
            if out['game'] and (out['game']['configKept'] or out['game']['savesKept']
                                or (self.cleanup and out['game']['play'])):
                if not (out['game']['lastPlay'] or {}).get('prefabTest'):
                    self.watch(game, appear=0)
        return out

    @staticmethod
    def content_text(game):
        """The install's DefaultContent.ini (the civilians' looks come from it), or None."""
        path = installs.config(game, 'DefaultContent.ini') if game is not None else None
        try: return path.read_text(encoding='latin-1') if path is not None and path.is_file() else None
        except OSError: return None

    def _game(self, what):
        game, note, _ = self.target()
        if game is None: raise ProjectError(409, f'{what}: {note}.')
        return game

    def play(self, request):
        if not isinstance(request, dict) or not (('project' in request) ^ ('map' in request)) \
                or ('zone' in request and not ('project' in request and isinstance(request['zone'], str))):
            raise ProjectError(400, 'Send {"project": id}, {"project": id, "zone": a landing zone\'s id} or {"map": id}, '
                                    'each with "mission" if it isn\'t the first.')
        try: mission = installs.mission_id(request.get('mission'))
        except ValueError as error: raise ProjectError(400, f'Not started: {error}.')
        if 'map' in request and mission is not None and not isinstance(mission, int):
            raise ProjectError(400, 'Not started: a map with no project plays one of its own records.')
        saving = request.get('saving', False)
        if not isinstance(saving, bool): raise ProjectError(400, 'Not started: "saving" is true or false.')
        # Land here (Clear map plan, section 4): the project's landing zone `zone` alone
        make = (lambda game: self._install_project(game, request['project'], request.get('zone'), mission)) if 'project' in request else (
            lambda game: self._map(game, request['map'], mission))
        played = self._run(make, saving=saving)
        return dict(self.status(), played=played)

    def play_test(self, test, folder, manifest, expected_game, verify, finished, saving=False):
        """Launch an internally verified, private prefab test package (saving: with saving on)."""
        def make(game):
            return installs.install_package(game, folder, expected=manifest, test=test)
        return self._run(make, test=test, expected_game=expected_game, verify=verify, finished=finished, saving=saving)

    def _run(self, make, *, test=None, expected_game=None, verify=None, finished=None, saving=False):
        with self.lock:
            game = self._game('Not started')
            if expected_game and not installs.same_folder(game, expected_game):
                raise ProjectError(409, 'The test install changed. Start a new prefab test.', code='settings-changed')
            if self.test_watching and self.test_watching.is_alive():
                raise ProjectError(409, 'A prefab test is still in use by the game.')
            changed = False
            try:
                if why := installs.ready(game):
                    raise installs.InstallError(why)
                argv, cwd, how = self.command(game, installs.PLAY_FILE, self.steam)
                # the test squad, resolved once for this install before anything in it changes: the play writes this
                # snapshot, whatever is saved meanwhile (a SquadError, 409, says why there is none to play)
                try: squad = self.squads.snapshot(game) if self.squads else None
                except SquadError as error: raise ProjectError(409, f'Not started: {error.message}', code='squad') from None
                if verify: verify()
                installs.recover_test_install(game)
                installs.restore_config(game)       # an earlier play's, when its watch didn't see the game close
                installs.restore_saves(game)
                if self.cleanup: installs.clear_play(game)
                changed = True
                played = make(game)
                record = played.pop('record', None)
                # what this kind of mission needs on this path (a prefab test's map has no mission)
                setup = None if test else missions.play_setup(record, self.content_text(game), self.try_lines,
                                                              lwr=game_kind(game) == 'lwr')
                if setup:
                    played['mission'] = dict(played.get('mission') or {}, kind=setup['kind'], label=setup['label'],
                                             state=setup['state'], words=setup['words'], missing=setup['missing'],
                                             notes=setup['notes'], lines=len(setup['lines']),
                                             options=[f'{n}={v}' for n, v in setup['options']])
                # saving on (asked, or the kind needs it): the game starts at its main menu and the key opens the battle
                forced = setup['saving'] if setup else None
                saving = bool(saving or forced)
                played['saving'] = dict(key=gamelaunch.SAVE_KEY, forced=forced) if saving else None
                if saving: argv, cwd, how = self.command(game, installs.START_FILE, self.steam)
                installs.write_start_file(game, gamelaunch.start_text(installs.PLAY_FILE) if saving else None)
                # the pods: none in a prefab test, the mission's (EXALT's for its missions) or the game's default
                aliens = False if test else (setup and setup['aliens']) or True
                squad_value = None
                if squad:
                    document, resolved = squad
                    played['squad'] = dict(name=document['name'], count=len(document['units']), **resolved.receipt())
                    squad_value = resolved.text
                    # a covert operative takes the first unit's looks: a soldier lands first (missions.LEAD_NOTE)
                    if setup and setup['operative']:
                        led, moved = squadrecords.soldier_first(resolved)
                        mission = played['mission']
                        if led is None: mission['missing'] = mission['missing'] + [missions.NO_LEAD_MISSING]
                        else:
                            squad_value = led
                            if moved: mission['notes'] = mission['notes'] + [missions.LEAD_NOTE.format(name=moved)]
                else: played['squad'] = None
                installs.write_play_file(game, gamelaunch.play_text(played['map'], squad_value, aliens=aliens,
                                                                    spawn_group=played.get('spawnGroup'),
                                                                    lines=setup['lines'] if setup else (),
                                                                    options=setup['options'] if setup else ()), played)
                if not (test and how == 'dry'):
                    home = self.documents or documents()
                    installs.backup_config(game, gamelaunch.user_config(game, home)
                                           + (gamelaunch.saving_config(game, home) if saving else []))
                    # a play's saves land on save1 without the login (F-89): kept apart from a campaign's afterwards
                    installs.keep_saves(game, playsaves.folders(game, home))
                self.start(argv, cwd)
            except (OSError, ValueError, installs.InstallError, gamelaunch.LaunchError) as error:
                cleanup = None
                if test and changed:
                    try:
                        installs.recover_test_install(game)
                        installs.restore_config(game)
                        installs.restore_saves(game)
                        if self.test_installed(game, test):
                            installs.clear_play(game)
                    except (OSError, ValueError, installs.InstallError) as problem:
                        cleanup = str(problem)
                        if installs.game_running():
                            self.watch(game, appear=0, finished=finished)
                            self.test_watching = self.watching
                raise ProjectError(409, f'Not started: {error}', **({'cleanup': cleanup} if cleanup else {}))
            if not (test and how == 'dry'):
                self.watch(game, appear=self.appear, finished=finished)
                if test: self.test_watching = self.watching
        return dict(played, how=how)

    @staticmethod
    def test_installed(game, test):
        ledger = installs.read_ledger(game)
        if any(entry.get('prefabTest') == test for entry in (ledger.get('installed') or {}).values()):
            return True
        last = ledger.get('lastPlay') or {}
        return last.get('prefabTest') == test and (installs.play_file(game).is_file() or bool(ledger.get('config')))

    def watch(self, game, appear, finished=None):
        """Put the game's config back once the game has closed, and take the play's things out of the game: waits up
        to `appear` seconds for it to come up, then for it to close. One watch at a time; a play's replaces one that is only waiting for a game left running."""
        if self.watching is not None and self.watching.is_alive() and not appear and finished is None: return
        stop = threading.Event()
        previous, self.stop_watch = self.stop_watch, stop
        if previous is not None: previous.set()

        def run():
            deadline = time.monotonic() + appear
            appeared = installs.game_running()
            while not stop.is_set() and time.monotonic() < deadline and not appeared:
                stop.wait(self.every)
                appeared = installs.game_running()
            while not stop.is_set() and appeared and installs.game_running(): stop.wait(self.every)
            if stop.is_set(): return
            stop.wait(min(self.every, 2))           # the game writes its config as it closes
            error = None
            try:
                with self.lock:
                    if stop.is_set(): return
                    installs.recover_test_install(game)
                    installs.restore_config(game)
                    installs.restore_saves(game)        # the play's saves apart, a save they replaced back
                    if self.cleanup:
                        result = installs.clear_play(game)
                        if result and result['left']: error = '; '.join(result['left'])
            except (OSError, ValueError, installs.InstallError) as problem:
                error = str(problem)
            if finished: finished(appeared, error)
        self.watching = threading.Thread(target=run, name='play-watch', daemon=True)
        self.watching.start()

    def _install_project(self, game, project_id, zone=None, mission=None):
        if self.projects is None or self.builds is None: raise ProjectError(404, 'This server does not build.')
        document = self.projects.load(project_id)
        # its package leased (a project being built, or about to be, can't be played) and its guard held while it is
        # copied in: no build swaps it meanwhile (build queue plan, 9.4); another project building doesn't stop it
        with self.builds.lease([project_id]) as building:
            if project_id in building:
                raise ProjectError(409, 'Not started: the project is building; it can be played when the build ends.')
            package = self.builds.package(project_id, (document.get('output') or {}).get('shipAs'))
            if package is None: raise ProjectError(409, 'Not started: build the project first (Ctrl+B).')
            folder = Path(package['folder'])
            try:
                with publication.guard(folder.parent, folder.name):
                    return installs.install_package(game, folder, zone=zone, mission=mission)
            except publication.Busy as error:
                raise installs.InstallError(str(error))

    def _map(self, game, map_id, mission=None):
        entry = (self.catalogue or {}).get('maps', {}).get(map_id) if isinstance(map_id, str) else None
        if entry is None: raise ProjectError(404, f'No map {map_id!r}.')
        name = entry['name']
        if not (installs.cooked(game) / f'{name}.upk').is_file(): raise installs.InstallError(f'{game} has no {name}.upk')
        installs.restore_intro(game)        # an earlier version's intro install, taken out
        record = installs.map_record(game, name, mission)
        played = dict(kind='map', map=name, base=name, project=None, mission=dict(id=mission or 0),
                      record=record.decode('latin-1') if record else None)
        # the mission's record where the game wouldn't find it first by the map's name: a copy ahead of the map's own,
        # or a live copy for a map whose records the install comments out (the tutorial's map) or the editor did
        # (housekeeping the message leaves out: the copy comes out when the game closes)
        installed = installs.install_map_record(game, name, mission)
        if installed:
            played['recordCopy'] = 'ahead' if 'ahead' in installed.get('how', '') else 'live'
        lwr, _ = lwr_game(self.settings)
        if lwr is not None and not installs.same_folder(lwr, game):
            theirs, ours = installs.cooked(lwr) / f'{name}.upk', installs.cooked(game) / f'{name}.upk'
            if theirs.is_file() and installs.sha256(theirs) != installs.sha256(ours):
                played['note'] = (f'This install\'s {name}.upk differs from the one the editor shows; the game plays '
                                  'this install\'s.')
        return played

    def remove(self):
        with self.lock:
            game = self._game('Not removed')
            try:
                if self.test_watching and self.test_watching.is_alive():
                    raise installs.InstallError('A prefab test is still in use by the game.')
                installs.recover_test_install(game)
                done = installs.reset(game)
            except (OSError, ValueError, installs.InstallError) as error: raise ProjectError(409, f'Not removed: {error}')
        return dict(self.status(), removed=done)
