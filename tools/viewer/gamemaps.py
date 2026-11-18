"""The Game maps window (Project menu): the map records of the game install's DefaultMaps.ini as the game reads them
now, what the editor changed of them, and undoing that.

One row per record. The install's own records say whether they are in use: live; commented out because a project's
build replaces them (the project manager's Replace: manager.py, installs.install_rotation; only the records of the
missions the build has records for, installs.replaced_records); switched off by hand
here; or commented out by the install itself (shown, never changed). The records the editor added sit under their base
map: a build's records for campaigns, and the one Play in game adds for a build. Everything comes from the editor's
ledger in the install (installs.py), so only its own changes can be undone, and undone they leave the file's lines as
the install had them.

Switching one of the install's records off comments its line out (a ';' before it), which is known to stop the game
using it (bInRotation=False is not); switching it on takes the ';' off again. A record a build replaces stays off
while it does.

  GET  /gamemaps.json     the install, its records by map, and what the editor has in it
  POST /gamemaps/use      {"records": [id...], "use": true | false}: the install's own records switched on or off
  POST /gamemaps/undo     {"variants": [name...]}: everything of these builds taken out of DefaultMaps.ini and the
                          landing zones (their records for campaigns, Play in game's record), the maps they replaced
                          live again; their files stay until everything is undone
Undo everything is Play in game's POST /play/remove (installs.reset): records, landing zones, files, the lot.
"""
import hashlib

import installs
import maplist
from projects import ProjectError
from settings import kind_label


def record_id(line):
    return hashlib.sha1(line).hexdigest()[:16]


def _game(player, what):
    if player is None: raise ProjectError(404, 'This server installs nothing.')
    game, note, _ = player.target()
    if game is None: raise ProjectError(409, f'{what}: {note}.')
    return game


def _row(line, **more):
    import deploy_fixture as dep
    text = line.decode('latin-1')
    group, kind, label = maplist.mission_of(text)
    return dict(id=record_id(line), name=dep.field(line, 'Name'), display=dep.field(line, 'DisplayName') or '',
                mission=label, group=group, type=kind, inRotation=installs._in_rotation(line), **more)


def listing(player):
    import deploy_fixture as dep
    game = _game(player, 'Not known')
    try:
        ledger = installs.read_ledger(game)
        pristine = installs.pristine_lines(game)
        status = installs.status(game)
    except (OSError, ValueError, installs.InstallError) as error:
        raise ProjectError(409, f'The install\'s DefaultMaps.ini can\'t be read: {error}')
    off = {c['original'] for c in ledger.get('linesOff') or []}
    manual = set(ledger.get('manualOff') or [])
    rotation = ledger.get('rotation') or []
    # each record a build replaces, with the projects replacing it (only the records the builds have records for)
    replaced = {text: [(e.get('project') or {}).get('name') or e['variant'] for e in entries]
                for text, entries in installs.replaced_records(ledger, pristine).items()}
    maps, order = {}, []

    def entry_of(name):
        if name not in maps:
            maps[name] = dict(name=name, records=[], displays=[])
            order.append(name)
        return maps[name]
    for line in pristine:
        if dep.is_record(line):
            name = dep.field(line, 'Name')
            if not name: continue
            text = line.decode('latin-1')
            state = 'replaced' if text in replaced and text in off else 'off' if text in off else 'on'
            row = _row(line, kind='own', state=state, manual=text in manual, by=replaced.get(text) if state == 'replaced' else None)
            entry_of(name)['records'].append(row)
            entry_of(name)['displays'].append(row['display'])
        else:
            commented = maplist.COMMENTED.match(line.decode('latin-1'))
            if not commented: continue
            record = commented.group(1).encode('latin-1')
            name = dep.field(record, 'Name')
            if not name: continue
            entry_of(name)['records'].append(_row(record, kind='own', state='install-off', manual=False, by=None))
    # what the editor added, under its base map
    played = {i.get('map'): i for i in status.get('installed') or []}
    for block in ledger.get('records') or []:
        info = played.get(block['variant']) or {}
        base = info.get('base') or block['variant']
        for line in block['lines'][1:]:
            entry_of(base)['records'].append(_row(line.encode('latin-1'), kind='play', state='added', variant=block['variant'],
                                                  project=(info.get('project') or {}).get('name'), mode=None,
                                                  quick=bool(info.get('quick'))))
    for entry in rotation:
        for line in entry['lines'][1:]:
            entry_of(entry['base'])['records'].append(_row(line.encode('latin-1'), kind='rotation', state='added', variant=entry['variant'],
                                                           project=(entry.get('project') or {}).get('name'), mode=entry['mode'],
                                                           quick=bool(entry.get('quick'))))
    out = []
    for name in order:
        entry = maps[name]
        out.append(dict(name=name, label=maplist.label_of(name, entry.pop('displays')), records=entry['records']))
    why = installs.ready(game)
    return dict(maps=out, install=dict(folder=str(game), kind=kind_label(game), ready=why is None, why=why),
                anything=status['anything'], files=len(ledger.get('files') or {}),
                backups=len(ledger.get('backups') or []))


def use(player, request):
    """The install's own records switched on or off."""
    import deploy_fixture as dep
    if not isinstance(request, dict) or not isinstance(request.get('records'), list) or not request['records'] \
            or not isinstance(request.get('use'), bool):
        raise ProjectError(400, 'Send {"records": [id...], "use": true or false}.')
    game = _game(player, 'Not changed')
    wanted = set(request['records'])
    with player.lock:
        try:
            lines = [l.decode('latin-1') for l in installs.pristine_lines(game) if dep.is_record(l) and record_id(l) in wanted]
            if not lines: raise ProjectError(409, 'Not changed: DefaultMaps.ini has no such record any more.')
            done = installs.set_records_use(game, lines, request['use'])
        except (OSError, ValueError, installs.InstallError) as error:
            raise ProjectError(409, f'Not changed: {error}')
    return dict(listing(player), changed=done['changed'], replaced=len(done['replaced']))


def undo(player, request):
    """Everything of these builds taken out of the install's config."""
    if not isinstance(request, dict) or not isinstance(request.get('variants'), list) or not request['variants'] \
            or not all(isinstance(v, str) for v in request['variants']):
        raise ProjectError(400, 'Send {"variants": [name...]}.')
    game = _game(player, 'Not undone')
    with player.lock:
        try: done = installs.remove_rotation(game, request['variants'], everything=True)
        except (OSError, ValueError, installs.InstallError) as error: raise ProjectError(409, f'Not undone: {error}')
    return dict(listing(player), undone=done)
