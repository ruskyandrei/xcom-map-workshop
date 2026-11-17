"""The project manager (the Project menu's Manage projects): every project with its last build, and what is done with
several at once: installed into the game for campaigns, or zipped into one map pack to hand on. Taking them out
again is the Game maps window's (gamemaps.py).

Play in game (play.py) installs one build under its own name with a record no campaign draws. The manager installs
builds for campaigns instead (installs.install_rotation), each in one of two ways:
- additional: the variant's records go into the rotation beside the base map's, so missions draw from both;
- replace: as well, the base map's own records are commented out, so missions draw the variant where they drew the
  map.
A variant's records copy the base map's, one per mission it serves, each in or out of rotation as the base map's is.
The missions whose records the install keeps out of rotation (council missions, the story's) get their map by its
record's display name: to replace it there the variant's record takes that name; beside it a variant is never picked,
but for bombs under Long War, whose mutator makes an extra bomb mission of each extra bomb record. Only abductions
have been played in the game with a variant. All of that is said as warnings, never refused.

  GET  /manager.json      every project: its saved revision, its last build (when, of which revision, by which editor
                          version, whether its lighting is baked), the missions its base map serves in the install,
                          what is in the game of it, and warnings (its build's, and each way's: modeWarnings); the
                          install the manager installs into
  POST /manager/install   {"projects": [id...], "mode": "additional" | "replace", "modes": {id: mode} optional}: each
                          project's last build installed its own way (modes), or else the request's (mode)
                          for campaigns; one that can't be is reported and the others go on
  POST /manager/pack      {"projects": [id...], "mode": ..., "modes": optional, "name": optional, "projectFiles":
                          optional}: one zip in <builds>/Map packs with every build's files laid out as the game
                          folder is, Install.cmd and Uninstall.cmd (which put the pack into a game folder and take it
                          out again: pack_scripts.py), a README, each build's own manifest and README, and pack.json,
                          which the scripts read; with "projectFiles": true, each packed map's saved editor project
                          too, under projects/ (the file as it is in the projects folder), for others to open and edit

The pack's config lines are worked out from the game install the editor reads (the same lines install_rotation would
add there); the README says so, since another install's records may differ.

Install and the pack read packages while the build queue may be building (build queue plan, 9.4): they lease the
projects' packages (builds.py lease), so a project being built, or about to be, is left out with the reason and the
queue waits before it starts one being read; and they hold each package's guard (publication.py) while they read and
copy it, so no build swaps it meanwhile. The pack takes all its packages' guards at once, in one order, and reads their
manifests again once it holds them.
"""
import datetime
import json
from pathlib import Path
import re
import zipfile

import installs
import pack_scripts
import publication
from projects import ProjectError
from settings import kind_label, lwr_game
from version import VERSION

PACKS = 'Map packs'             # in the builds folder; no variant can have the name (a space)
PACK_SCHEMA = 'xcom-map-workshop/map-pack'
EOL = '\r\n'
MODE_WORDS = dict(additional='as additional maps in the rotation', replace='replacing the original maps in the rotation',
                  mixed='some replacing the original maps, some as additional maps in the rotation')


def _manifest(builds, project_id, variant):
    """The manifest of the project's last package and its folder, or (None, None)."""
    if not variant or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', variant): return None, None
    folder = builds.output / variant
    try: m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None, None
    if (m.get('project') or {}).get('id') != project_id: return None, None
    return m, folder


def _lines(game):
    """The install's own DefaultMaps.ini lines (bytes), or None when they can't be read."""
    if game is None: return None
    try: return installs.pristine_lines(game)
    except (OSError, ValueError, installs.InstallError): return None


def _missions(lines, base):
    """The missions the base map serves in the install: [{type, label, group, inRotation, byName, bomb, firstMission
    (when true)}], or None when not known."""
    if lines is None or not base: return None
    import deploy_fixture as dep
    import maplist
    out = []
    for _, line in installs.base_records(lines, base):
        group, kind, label = maplist.mission_of(line.decode('latin-1'))
        first = installs._first_mission(line)
        out.append(dict(type=kind, label=label, group=group, inRotation=installs._in_rotation(line),
                        byName=not installs._in_rotation(line) or first, bomb=dep.unquoted(line, 'CouncilType') == 'eFCMType_Bomb',
                        **({'firstMission': True} if first else {})))
    return out


def _mode_warnings(lines, m, missions, base, mode, lwr):
    """What installing the project one way does to the missions (installs.mission_warnings): from its last build's
    records when it has one (which of the base map's missions it has records for, F-118), else from the base map's."""
    if m and lines is not None:
        try: plan = installs.rotation_plan(lines, m, '', mode)
        except (KeyError, TypeError, ValueError, installs.InstallError): plan = None
        if plan: return installs.mission_warnings(plan['missions'], base, mode, lwr=lwr, kept=plan['kept'])
    return installs.mission_warnings(missions, base, mode, lwr=lwr) if missions else []


def _targets(player):
    """(the game the manager installs into or None, why not, the game install the editor reads or None)."""
    if player is None: return None, 'This server installs nothing.', None
    game, note, _ = player.target()
    read, _ = lwr_game(player.settings)
    return game, None if game is not None else note, read


def listing(projects, builds, player):
    from settings import game_kind
    game, why, read = _targets(player)
    lwr = game_kind(game if game is not None else read) == 'lwr' if (game or read) is not None else True
    lines = _lines(game if game is not None else read)
    status = None
    if game is not None:
        why = installs.ready(game)
        try: status = installs.status(game)
        except (OSError, ValueError, installs.InstallError): status = None
    played = {i.get('map'): i for i in (status or {}).get('installed') or [] if i.get('kind') == 'project'}
    rotation = {e['variant']: e for e in (status or {}).get('rotation') or []}
    # being built now, or about to be (the build queue's next): the shared active-writer query
    building = builds.active_projects()
    rows = []
    for summary in projects.list():
        if summary.get('error'):
            rows.append(summary)
            continue
        try: document = projects.load(summary['id'])
        except ProjectError as error:
            rows.append(dict(summary, error=error.message))
            continue
        variant = (document.get('output') or {}).get('shipAs')
        m, folder = _manifest(builds, summary['id'], variant)
        build = None
        if m:
            build = dict(buildId=m.get('buildId'), builtAt=m.get('builtAt'), revision=(m.get('project') or {}).get('revision'),
                         editorVersion=m.get('editorVersion'), quick=bool(m.get('quick')),
                         lightingUnchanged=bool(m.get('lightingUnchanged')), seconds=m.get('seconds'), folder=str(folder),
                         stale=(m.get('project') or {}).get('revision') != summary.get('revision'))
        missions = _missions(lines, summary.get('map'))
        warnings = []
        if build and build['quick']: warnings.append('Its last build is a quick one: its lighting is not baked.')
        if build and build['stale']:
            warnings.append(f'Its last build is of revision {build["revision"]}; the project is at revision {summary.get("revision")}.')
        by_mode = {mode: _mode_warnings(lines, m, missions, summary.get('map'), mode, lwr) for mode in installs.ROTATION_MODES}
        in_game = None
        if variant in played or variant in rotation:
            entry = rotation.get(variant)
            in_game = dict(play=variant in played, rotation=entry['mode'] if entry else None,
                           buildId=(entry or played[variant]).get('buildId'),
                           current=bool(build) and (entry or played[variant]).get('buildId') == build['buildId'])
        rows.append(dict(summary, variant=variant, build=build, missions=missions, warnings=warnings,
                         modeWarnings=by_mode, inGame=in_game,
                         building=summary['id'] in building))
    return dict(projects=rows, folder=str(projects.root), output=str(builds.output), editorVersion=VERSION,
                install=dict(folder=None if game is None else str(game), ready=game is not None and why is None, why=why,
                             kind=None if game is None else kind_label(game)))


def _request(request, need_mode=True):
    """The request's project ids (in order, once each) and mode, checked."""
    if not isinstance(request, dict) or not isinstance(request.get('projects'), list) or not request['projects'] \
            or not all(isinstance(p, str) for p in request['projects']):
        raise ProjectError(400, 'Send {"projects": [id...]}.')
    mode = request.get('mode')
    if need_mode and mode not in installs.ROTATION_MODES:
        raise ProjectError(400, 'Send "mode": "additional" or "replace".')
    modes = request.get('modes') or {}
    if not isinstance(modes, dict) or any(v not in installs.ROTATION_MODES for v in modes.values()):
        raise ProjectError(400, 'Send "modes": {project id: "additional" or "replace"}.')
    return list(dict.fromkeys(request['projects'])), mode, modes


def _chosen(projects, builds, request, building, need_mode=True):
    """The request's projects and mode: ([(id, name, manifest or None, folder, why not, its mode)], mode). A project's
    mode is its own where the request's "modes" ({id: mode}) names it, else the request's "mode". `building`: the
    projects being built (the lease's), which are left out."""
    ids, mode, modes = _request(request, need_mode)
    out = []
    for project_id in ids:
        try: document = projects.load(project_id)
        except ProjectError as error:
            out.append((project_id, project_id, None, None, error.message, mode))
            continue
        name = document.get('name') or project_id
        m, folder = _manifest(builds, project_id, (document.get('output') or {}).get('shipAs'))
        why = ('It is building; it can be used when the build ends.' if project_id in building
               else None if m else 'It has not been built yet.')
        out.append((project_id, name, m if why is None else None, folder, why, modes.get(project_id, mode)))
    return out, mode


def _game(player, what):
    game, why, _ = _targets(player)
    if game is None: raise ProjectError(409 if player is not None else 404, f'{what}: {why}')
    return game


def install(projects, builds, player, request):
    """Each chosen project's last build installed for campaigns (installs.install_rotation); the results, one per
    project, and the listing afterwards."""
    ids, _, _ = _request(request)
    game = _game(player, 'Not installed')
    results = []
    with builds.lease(ids) as building:
        chosen, mode = _chosen(projects, builds, request, building)
        with player.lock:
            why = installs.ready(game)
            if why: raise ProjectError(409, f'Not installed: {why}.')
            for project_id, name, m, folder, why, its in chosen:
                if m is None:
                    results.append(dict(id=project_id, name=name, ok=False, error=why))
                    continue
                try:
                    # the package's guard held while it is read and copied: no build swaps it meanwhile
                    with publication.guard(folder.parent, folder.name):
                        done = installs.install_rotation(game, folder, its)
                    results.append(dict(id=project_id, name=name, ok=True, mode=its, variant=done['variant'], base=done['base'],
                                        switchedOff=done['switchedOff'], quick=done['quick'], warnings=done['warnings'],
                                        missions=[x['label'] for x in done['missions'] if x['inRotation']]))
                except (OSError, ValueError, KeyError, installs.InstallError, publication.PublishError) as error:
                    results.append(dict(id=project_id, name=name, ok=False, error=str(error)))
    return dict(listing(projects, builds, player), results=results, mode=mode)


def _safe(name):
    return re.sub(r'\s+', ' ', re.sub(r'[^A-Za-z0-9 _.()-]', '', name or '')).strip(' .')[:60]


def pack_readme(pack, parts):
    """The map pack's README: what is in it and how it goes into a game by hand. parts: one per build, dict(name,
    variant, base, mode, files, records (text lines), switch (the base map's display names to comment out), keep
    (those of its records to leave in use: the build has no record for their missions), landingZones (text lines or None), warnings, quick)."""
    replace = any(p['mode'] == 'replace' for p in parts)
    mixed = pack['mode'] == 'mixed'
    lines = [
        '%s: %d map%s made with the XCOM Map Workshop %s, %s.' % (pack['name'], len(parts), '' if len(parts) == 1 else 's',
                                                              pack['editorVersion'], MODE_WORDS[pack['mode']]),
        'Made on %s from %s.' % (pack['madeAt'], pack['game'] or 'a game install'),
        '',
        'Maps:',
    ]
    for p in parts:
        lines += ['  %s: %s, a variant of %s%s%s' % (p['variant'], p['name'], p['base'],
                                                   (', replacing it' if p['mode'] == 'replace' else ', beside it') if mixed else '',
                                                   ' (QUICK BUILD: its lighting is not baked)' if p['quick'] else '')]
    lines += [
        '',
        'To install (with XCOM closed): unzip the whole pack, then double-click Install.cmd. It asks for the game folder',
        '(the one with the XEW folder in it; it offers the Steam install it finds), keeps a copy of DefaultMaps.ini as it',
        'is, copies the files and adds the lines below. Uninstall.cmd takes the pack out again: the lines it added go, the',
        'lines it commented out come back and its files are deleted, and it says whether DefaultMaps.ini is then exactly',
        'as it was. Both can be given the game folder instead: Install.cmd "D:\\Steam\\steamapps\\common\\XCom-Enemy-Unknown".',
        'What the scripts did is written down in <game>\\XCOM Map Workshop\\packs, with the copies of the files from before.',
        'A map whose base map this game has no record for is left out, and so is one the game already has a record for.',
        '',
        'By hand instead (what Install.cmd does):',
        '',
        '1. Files. Copy the XEW folder of this zip over the XEW folder of the game (...\\XCom-Enemy-Unknown\\XEW). It adds',
        '   these files to XEW\\XComGame\\CookedPCConsole and replaces none of the game\'s own:',
    ]
    lines += ['     %s' % f for p in parts for f in p['files']]
    lines += [
        '',
        '2. XEW\\XComGame\\Config\\DefaultMaps.ini (keep a copy of the file first). For each map below, add its lines to the',
        '   [XComGame.XComMapManager] list, after the last line that has Name="<its base map>".' + (
            ' Then, for a map that replaces its' if mixed else ' Then, on the base map\'s' if replace else ''),
    ]
    if mixed: lines += ['   base map: on the base map\'s own lines named under it, put a ; at the start of the line (that comments it out),',
                        '   so that missions use the new map where they used the original.']
    elif replace: lines += ['   own lines named under it, put a ; at the start of the line (that comments it out), so that missions use the',
                          '   new map where they used the original.']
    for p in parts:
        lines += ['', '   %s (after %s\'s records):' % (p['variant'], p['base'])] + p['records']
        if p['mode'] == 'replace' and p['switch']:
            lines += ['', '   %s\'s own records to comment out (a ; before the line), by their DisplayName:' % p['base']]
            lines += ['     %s' % d for d in p['switch']]
        elif p['mode'] == 'replace' and not p.get('keep'):
            lines += ['', '   %s has no live record here: nothing to comment out.' % p['base']]
        if p['mode'] == 'replace' and p.get('keep'):
            lines += ['', '   %s\'s own records to leave as they are (the map has no record for their missions, so the' % p['base'],
                      '   original stays in use there):']
            lines += ['     %s' % d for d in p['keep']]
    zones = [p for p in parts if p['landingZones']]
    if zones:
        lines += ['', '3. XEW\\XComGame\\Config\\DefaultLZMutator.ini (Long War\'s landing zones; skip this without Long War): add each',
                  '   map\'s lines beside its base map\'s.']
        for p in zones:
            lines += ['', '   %s (beside %s\'s):' % (p['variant'], p['base'])] + p['landingZones']
    shared = pack.get('projects') or []
    if shared:
        lines += ['', 'Editor projects. The projects folder has the XCOM Map Workshop project of %s, to open and change in the'
                  % ('this map' if len(shared) == 1 else 'these maps'),
                  'editor: copy the .json file into the editor\'s projects folder (by default <editor folder>\\projects), then open',
                  'it with Load in the Project menu. The editor reads the base map from your own game install.']
        for s in shared:
            later = s['revision'] != s['buildRevision'] and s['buildRevision'] is not None
            lines += ['  projects\\%s%s' % (s['file'], ' (saved after this build: the project is at revision %s, the map is of revision %s)'
                                            % (s['revision'], s['buildRevision']) if later else '')]
    warned = [p for p in parts if p['warnings']]
    if warned:
        lines += ['', 'Notes:']
        for p in warned:
            lines += ['  %s: %s' % (p['variant'], ' '.join(p['warnings']))]
    lines += [
        '',
        'The lines above copy the records of the install this pack was made from. A game with other records for these maps',
        '(another Long War version, plain Enemy Within) may want its own: copy the base map\'s lines there, change Name to',
        'the new map\'s name and DisplayName to anything of your own, and keep the streamed maps this pack adds (the',
        'StreamingMaps entries the lines above have and the base map\'s don\'t). The packages folder has each map\'s own',
        'README and manifest, with every detail.',
        '',
        'Start a new mission afterwards: a tactical save from before does not use the new maps.',
        'To take it out by hand: remove the lines you added, take the ; off the lines you commented out, and delete the files',
        'listed above.',
        '',
    ]
    return EOL.join(lines)


def pack(projects, builds, player, request, now=None):
    """One zip of the chosen projects' last builds (see the module notes). Projects without a build are left out and
    named; with none left it is an error."""
    ids, _, _ = _request(request)
    with builds.lease(ids) as building:
        chosen, mode = _chosen(projects, builds, request, building)
        variants = [folder.name for _, _, m, folder, _, _ in chosen if m is not None]
        try:
            # every package's guard at once, in one order, while they are read and zipped (their manifests read again
            # once held: _pack's read_package)
            with publication.guards(builds.output, variants):
                return _pack(projects, builds, player, request, chosen, mode, now)
        except publication.Busy as error:
            raise ProjectError(409, f'Not made: {error}')


def _pack(projects, builds, player, request, chosen, mode, now):
    import deploy_fixture as dep
    from settings import game_kind
    _, _, read = _targets(player)
    game = read if read is not None else _targets(player)[0]
    lines = _lines(game)
    if lines is None: raise ProjectError(409, 'Not made: the game install\'s DefaultMaps.ini can\'t be read, and the pack\'s config lines come from it.')
    lz_path = installs.config(game, installs.LZ)
    try: lz = dep.lines_of(lz_path.read_bytes()) if lz_path.is_file() else None
    except (OSError, ValueError): lz = None
    now = now or datetime.datetime.now()
    stamp = now.strftime('%Y%m%d-%H%M%S')
    note = f'{installs.RECORD_NOTE}, {stamp[:8]}'
    parts, skipped, files = [], [], {}
    for project_id, name, m, folder, why, its in chosen:
        if m is None:
            skipped.append(dict(id=project_id, name=name, error=why))
            continue
        try:
            m, package_files = installs.read_package(folder)
            plan = installs.rotation_plan(lines, m, note, its)
            base, variant = m['source']['map'], m['variant']
            for src, _, digest in package_files:
                if files.get(src.name, (src, digest))[1] != digest:
                    raise installs.InstallError(f'{src.name} is in two of the builds with different contents')
                files[src.name] = (src, digest)
            # replacing: the base map's live records the build has records for are commented out (switch), the others
            # stay in use (keep, F-118); a map whose records the install comments out has none
            live = [l for l in lines if dep.is_record(l) and dep.field(l, 'Name') == base] if its == 'replace' else []
            stands = set(plan['standsFor'])
            switch = [dep.field(l, 'DisplayName') or '' for l in live if l.decode('latin-1') in stands]
            keep = [dep.field(l, 'DisplayName') or '' for l in live if l.decode('latin-1') not in stands]
            _, zones = installs.plan_variant_lz(lz, m, note) if lz is not None else (None, [])
            parts.append(dict(id=project_id, name=name, variant=variant, base=base, mode=its, quick=bool(m.get('quick')),
                              revision=(m.get('project') or {}).get('revision'), buildId=m.get('buildId'), folder=folder,
                              files=sorted(src.name for src, _, _ in package_files),
                              records=[l.decode('latin-1') for l in plan['block']], switch=switch, keep=keep,
                              landingZones=[l.decode('latin-1') for l in zones] or None,
                              **({'ownZones': True} if (m.get('config') or {}).get('landingZonesFromProject') else {}),
                              # the maps its pieces of other maps came from, for the record (no folder of this PC)
                              donors=[{k: d.get(k) for k in ('map', 'sha256', 'pieces')} for d in m.get('donors') or []],
                              warnings=(['Its lighting is not baked (a quick build).'] if m.get('quick') else [])
                              + installs.mission_warnings(plan['missions'], base, its, lwr=game_kind(game) == 'lwr', kept=plan['kept'])))
        except (OSError, ValueError, KeyError, installs.InstallError) as error:
            skipped.append(dict(id=project_id, name=name, error=str(error)))
    if not parts:
        raise ProjectError(409, 'Not made: none of the chosen projects has a build to pack. '
                           + ' '.join(f'{s["name"]}: {s["error"]}' for s in skipped), skipped=skipped)
    # the packed maps' editor projects, when asked for: each saved file as it is on disk, under projects/
    shared, project_data = [], {}
    if request.get('projectFiles') is True:
        for p in parts:
            try: document, data, digest, path = projects.capture(p['id'])
            except ProjectError as error:
                p['warnings'].append(f'Its editor project is not in the pack: {error.message}')
                continue
            project_data[path.name] = data
            shared.append(dict(id=p['id'], name=p['name'], file=path.name, revision=document.get('revision'),
                               buildRevision=p['revision'], sha256=digest))
    # the pack's mode: its maps' own, or "mixed" when some replace and some are added
    mode = parts[0]['mode'] if len({p['mode'] for p in parts}) == 1 else 'mixed'
    name = _safe(request.get('name') if isinstance(request.get('name'), str) else '') or (
        _safe(parts[0]['name']) if len(parts) == 1 else f'Map pack of {len(parts)}') or 'Map pack'
    described = dict(schema=PACK_SCHEMA, schemaVersion=1, editorVersion=VERSION, name=name, mode=mode,
                     id=re.sub(r'[^A-Za-z0-9_.-]+', '-', f'{name}-{stamp}'),
                     madeAt=now.isoformat(timespec='seconds'), game=kind_label(game) if game is not None else None,
                     maps=[{**{k: p[k] for k in ('id', 'name', 'variant', 'base', 'mode', 'quick', 'revision', 'buildId', 'files',
                                              'records', 'switch', 'keep', 'landingZones', 'donors', 'warnings')},
                           **({'ownZones': True} if p.get('ownZones') else {})} for p in parts],
                     files={n: digest for n, (_, digest) in sorted(files.items())},
                     **({'projects': shared} if shared else {}))
    folder = builds.output / PACKS
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{name} {stamp}.zip'
    temp = target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.txt', pack_readme(described, parts).encode('latin-1', 'replace'))
        z.writestr('pack.json', json.dumps(described, indent=1) + '\n')
        z.writestr('Install.cmd', pack_scripts.INSTALL_CMD)
        z.writestr('Uninstall.cmd', pack_scripts.UNINSTALL_CMD)
        z.writestr('pack-tools/pack.ps1', pack_scripts.PS1)
        for n, (src, _) in sorted(files.items()):
            z.write(src, f'XEW/XComGame/CookedPCConsole/{n}')
        for p in parts:
            for n in ('README.txt', 'manifest.json'):
                if (p['folder'] / n).is_file(): z.write(p['folder'] / n, f'packages/{p["variant"]}/{n}')
        for n, data in sorted(project_data.items()):
            z.writestr(f'projects/{n}', data)
    temp.replace(target)
    return dict(zip=str(target), name=name, mode=mode, size=target.stat().st_size,
                packed=[dict(id=p['id'], name=p['name'], variant=p['variant'], mode=p['mode'], warnings=p['warnings']) for p in parts],
                skipped=skipped, projects=[s['file'] for s in shared])
