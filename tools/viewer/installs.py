"""What Play in game puts into a game install and Remove from game takes back out, for any LWR or plain Enemy Within
install: the editor's own install step, nothing here knows a particular computer or our lab.

The game opens a map by its name (Play in game starts it that way: gamelaunch.py, EXP-29) and takes the map's patch and
landing streams from the first DefaultMaps.ini record with that Name. So:
- a map as the install has it needs nothing installed: its own records are there. The exception is Act1_IntroLevel,
  the tutorial's map, whose records LWR comments out (maplist.SWITCHED_OFF): opened with no record, the game crashed
  8 s into the battle (EXP-30 run 1), so a play of it gets a live copy of its abduction record, out of rotation
  (install_map_record);
- a variant package (tools/editor/build.py) gets a record of its own, added after the base map's records: one of the
  base map's records (its abduction where it has one) under the variant's name and out of rotation, so no campaign
  draws it, streaming the package's patch and its own copy of the landing intro in place of the original. The
  package's files are copied into CookedPCConsole (each checked against the manifest first) and the base map's landing
  zones are added under the variant's name in DefaultLZMutator.ini (Long War's file: an install without it, plain EW,
  gets no landing-zone lines).
No line the install had is changed: the first mission of a new campaign stays the game's own. The one exception is a
record of the same variant that the lab's patchtool deploy wrote (an earlier test of the same project, its comment line
saying so: patchtool_record): the editor's record takes its place, and Remove from game puts it back.

The project manager (manager.py) installs builds for campaigns instead (install_rotation): a variant gets a record for
each record of its base map, in or out of rotation as the base map's is, after the base map's records and after any
record Play in game added (which stays the first of the variant's name). Installed to replace its base map, the base
map's own records are commented out (a ';' before each: that is known to stop the game using a record, which
bInRotation=False is not), and the variant's records for the missions the game asks for by name (council missions,
whose records are out of rotation) keep the base map's display names. The Game maps window switches single records
of the install off and on the same way (set_records_use). These are the cases where lines of the install are changed:
each is kept in the ledger (linesOff) and put back when the reason goes (remove_rotation, set_records_use, reset). A
map with no live record left still plays alone: install_map_record gives it a copy for the play.

What the editor changed is kept in the install itself, in <game>\\XCOM Map Workshop, in two ledgers. play.json holds
what a play put in (PLAY_KEYS): Play in game is not meant to leave anything behind, so all of it is taken out again
once the game has closed (clear_play, from play.py's watch) or, failing that, before the next play. installs.json holds
what is meant to stay until it is undone: the project manager's installs for campaigns and the records switched off in
Game maps. A file or landing-zone block is noted in one of them only, the campaign's first, so clearing a play never
takes away what a campaign install needs. There are copies of both
INI files as they were before each change: the record and landing-zone lines it added, the files it copied, the file of
console commands a play starts the game with (XEW\\Binaries\\PLAY_FILE) and the game's own config files kept aside for a
play (below). The record travels with the game folder if it is renamed or moved.

The game's config during a play: the console commands that give a play its squad make the game write its
XComContent.ini again with them in it (the engine saves a class's config after `set`: findings register F-73). So a
play keeps the file aside first (backup_config) and it is put back once the game has closed (restore_config: by the
server's watch, or else before the next play or by Remove from game).

Remove from game takes all of that back out: the lines it added, the files it copied that are unchanged since, the
commands file, and the config kept aside. Afterwards the install's config files are byte for byte as they were.

Before 9 November 2026 the editor installed a map as the first mission of a new campaign instead (Install as intro
map): it rewrote the one record whose DisplayName is LWR's Commercial Alley Redux (INTRO_SLOTS). A ledger of that time
is still read: the next play, or Remove from game, puts the install's own line back (restore_intro).

All of these refuse while XCOM runs. A play's install and a campaign install check the whole package first, before a
file is copied or a line changed (preflight): a variant the editor installed for another project is never replaced,
and a package file already in CookedPCConsole (the name compared regardless of case) is replaced only when the editor
put it there for the same project and it is unchanged since. Whose each file is goes in the ledger (`owners`, since
16 November 2026); for a ledger from before, a file of the package's own list is the project's the ledger says
installed its variant, and anything else that nothing says is refused. A file the editor never put there is never
overwritten (it stays whoever's it is when it already has the package's bytes), but for one the lab's own deploy tools
put there before the editor could install, with the bytes they gave it (lab_deploys: only in the lab copy, with the
lab setting set). Its name is one of the project's own output names, so it is an earlier test of the same project: it
is kept in that change's backup folder (`labFiles` in the ledger) before the build's file replaces it, and goes back
when the editor takes its file out again (a play's end, Remove from game).

maps_text(game) is the install's DefaultMaps.ini as the install has it, the editor's lines taken out: the map list, the
exporter and Build read the install through it, so an install of the editor's never shows up as a map or a record
there.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bake'))

LEDGER_FOLDER = 'XCOM Map Workshop'
SCHEMA = 'xcom-map-workshop/installs'
PLAY_SCHEMA = 'xcom-map-workshop/play'
# what a play puts in, kept in play.json and taken out when the game closes (clear_play): the records it added, what
# they are, the last play, the config kept aside, the save folders noted (and what was done with the play's saves
# after the last one), and the files and landing zones a play copied in
PLAY_KEYS = ('records', 'installed', 'lastPlay', 'config', 'saves', 'lastSaves', 'playFiles', 'playZones')
PACKAGE_SCHEMA = 'xcom-map-workshop/variant-package'
# The first mission's record, by its DisplayName: LWR's, then plain EW's as a guess (the same without LWR's " |0").
# Only an install from before Play in game changed it (restore_intro).
INTRO_SLOTS = ('URB_CommercialAlley_EWI (Commercial Alley Redux) |0', 'URB_CommercialAlley_EWI (Commercial Alley Redux)')
INTRO_SLOT = INTRO_SLOTS[0]
# A record in rotation that the game also asks for by its DisplayName: a new campaign's first mission
# (XGGeoscape.TakeFirstMission -> DetermineMap, EXP-03). A variant that replaces its map keeps this name on the record
# that stands for it, or the first mission finds no map (F-117).
FIRST_MISSION = frozenset(INTRO_SLOTS)
LZ = 'DefaultLZMutator.ini'     # Long War's landing zones: absent from plain EW
PACKAGE_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]*')     # a package's name (the lab's ledgers name packages: lab_deploys)
PLAY_FILE = 'XComMapWorkshop-play.txt'      # in XEW\Binaries, where the game's exec command looks
# A play with saving on starts the game with this one instead: it binds a key to the play's commands and leaves the
# game at its main menu, whose login readies saving (F-89, EXP-56); the key then opens the battle.
START_FILE = 'XComMapWorkshop-start.txt'
RECORD_NOTE = 'XCOM Map Workshop'           # in a variant record's DisplayName and its comment line
ROTATION_MODES = ('additional', 'replace')  # install_rotation: beside the base map in the rotation, or instead of it


class InstallError(Exception):
    pass


def config(game, name):
    return Path(game) / 'XEW' / 'XComGame' / 'Config' / name


def cooked(game):
    return Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole'


# A prefab test's record is an abduction's, as every other play's (so Meld comes: the game spawns it on abductions,
# crashed and landed UFOs, XGBattleDesc.ShouldSpawnMeldCanisters). Tried for no Meld (F-93): eMission_None crashed the
# game as the battle started, at the address a map with no record crashed at (F-78); eMission_TerrorSite spawned
# civilians with no looks and a stray Chryssalid and Sectoid, and the battle never left the loading screen.
TEST_MISSION = 'eMission_Abduction'


def play_file(game):
    return Path(game) / 'XEW' / 'Binaries' / PLAY_FILE


def start_file(game):
    return Path(game) / 'XEW' / 'Binaries' / START_FILE


def _commands_out(game):
    """The commands files a play left in XEW\\Binaries taken away; whether there were any."""
    found = False
    for path in (play_file(game), start_file(game)):
        if path.is_file():
            path.unlink()
            found = True
    return found


def ledger_path(game):
    return Path(game) / LEDGER_FOLDER / 'installs.json'


def play_ledger_path(game):
    return Path(game) / LEDGER_FOLDER / 'play.json'


# One ledger file read or written at a time in this process: on Windows a read open while another thread renames the
# file over it is refused (and the rename too), so the server's status reads and a play's watch would collide.
_LEDGER_IO = threading.Lock()


def _read_json(path, schema):
    with _LEDGER_IO:
        if not path.is_file(): return None
        text = path.read_text(encoding='utf-8')
    data = json.loads(text)
    if data.get('schema') != schema: raise InstallError(f'{path} is not an install record (schema {data.get("schema")!r})')
    return data


def read_ledger(game):
    """Both ledgers as one dict: installs.json (what stays in the game: the project manager's installs for campaigns,
    the records switched off in Game maps) and play.json (what a play put in, which goes when the game closes:
    PLAY_KEYS). {} when there is neither. An installs.json from before the two were separate holds a play's things
    too: they are read as the play's (its files and landing zones too, unless a campaign install was there already)."""
    data = _read_json(ledger_path(game), SCHEMA) or {}
    play = _read_json(play_ledger_path(game), PLAY_SCHEMA)
    if play is not None:
        data.update({k: play[k] for k in PLAY_KEYS if k in play})
    elif data and 'playFiles' not in data and data.get('schemaVersion', 0) < 3:
        campaign = {e['variant'] for e in data.get('rotation') or []}
        zones = data.get('landingZones') or []
        data['playZones'] = [z for z in zones if z['variant'] not in campaign]
        data['landingZones'] = [z for z in zones if z['variant'] in campaign]
        data['playFiles'] = {} if campaign else data.pop('files', None) or {}
    return data


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    text = json.dumps(data, indent=1) + '\n'
    with _LEDGER_IO:
        temp.write_text(text, encoding='utf-8', newline='\n')
        # another process holding the file (a virus scanner, an editor) makes Windows refuse the rename for a moment
        for attempt in range(50):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                if attempt == 49: raise
                time.sleep(0.02)


def write_ledger(game, data):
    """The dict read_ledger gives, written back as the two files; play.json only once a play has put something in."""
    play = {k: data[k] for k in PLAY_KEYS if k in data}
    main = {k: v for k, v in data.items() if k not in PLAY_KEYS}
    _write_json(ledger_path(game), dict(main, schema=SCHEMA, schemaVersion=3))
    if any(play.values()) or play_ledger_path(game).is_file():
        _write_json(play_ledger_path(game), dict(play, schema=PLAY_SCHEMA, schemaVersion=1))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def game_running():
    """Whether XCOM: Enemy Within is running (any install)."""
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
    return 'XComEW.exe' in out


def plan_variant_lz(lz, m, note, zone=None):
    """(where, lines) to add to DefaultLZMutator.ini (lines of bytes) for a package's variant: the project's own
    landing-zone lines when it set them (the manifest's config.landingZonesFromProject; Clear map plan, section 4),
    after the base map's last line or at the end of the file, else a copy of the base map's (deploy_fixture.plan_lz).
    Nothing when the variant has lines already, or the project's list writes none. `zone` (Land here: a zone's id):
    that zone's line alone."""
    import deploy_fixture as dep
    base, variant, c = m['source']['map'], m['variant'], m.get('config') or {}
    if not c.get('landingZonesFromProject'):
        return dep.plan_lz(lz, base, variant, note)
    tag = f'MapName="{variant}"'.encode()
    lines = c.get('landingZones') or []
    if zone is not None:
        lines = [l for z, l in zip(c.get('landingZoneIds') or [], lines) if z == zone]
    if any(tag in l for l in lz) or not lines:
        return None, []
    mine = [i for i, l in enumerate(lz) if f'MapName="{base}"'.encode() in l and not l.lstrip().startswith(b';')]
    at = mine[-1] + 1 if mine else (len(lz) - 1 if lz and lz[-1] == b'' else len(lz))
    return at, [f';{variant} locations = the project\'s landing zones ({note})'.encode()] + \
        [l.encode('latin-1') for l in lines]


def intro_slot(lines):
    """The DisplayName of the install's intro slot (INTRO_SLOTS: the first that exactly one record has), or a
    ValueError."""
    import deploy_fixture as dep
    for name in INTRO_SLOTS:
        if sum(1 for l in lines if dep.is_record(l) and dep.field(l, 'DisplayName') == name) == 1: return name
    raise ValueError('expected one record named %s' % ' or '.join(f'"{n}"' for n in INTRO_SLOTS))


def _ours(ledger, lines):
    """The intro slot's index when an earlier version's install is still in it (its line the one that wrote), else
    None."""
    slot = ledger.get('slot')
    if not slot: return None
    at = slot['line'] - 1
    return at if 0 <= at < len(lines) and lines[at] == slot['written'].encode('latin-1') else None


def _run(lines, want):
    """Where the run of lines `want` starts in `lines`, or None."""
    return next((i for i in range(len(lines) - len(want) + 1) if lines[i:i + len(want)] == want), None) if want else None


def _encoded(block, key='lines'):
    return [l.encode('latin-1') for l in block.get(key) or []]


def _take_out(lines, block):
    """The editor's record block taken out of `lines` (in place), and the lines it stood in for put back where it was
    (a patchtool record of the same variant, below); False when the block isn't there as written."""
    found = _run(lines, _encoded(block))
    if found is None: return False
    lines[found:found + len(block['lines'])] = _encoded(block, 'original')
    return True


def patchtool_record(lines, variant):
    """Where a record of the variant that the lab's patchtool deploy wrote starts (its comment line, then the record:
    "; <variant>: <base>'s record under its own name, ... (patchtool, <date>)"), else None. The variant's name comes
    from its project, so such a record is an earlier test of the same project: the editor stands in for it while its
    build is installed and puts it back with Remove from game."""
    import deploy_fixture as dep
    at = [i for i, l in enumerate(lines) if dep.is_record(l) and dep.field(l, 'Name') == variant]
    if len(at) != 1 or at[0] == 0: return None
    comment = lines[at[0] - 1]
    ok = comment.startswith(f'; {variant}: '.encode()) and b"'s record under its own name" in comment and b'(patchtool' in comment
    return at[0] - 1 if ok else None


def _rotation_out(lines, ledger, variant=None):
    """The rotation records the editor added (install_rotation) taken out of `lines` (in place): every variant's, or
    one's. Returns what could not be taken out, in words."""
    left = []
    for entry in ledger.get('rotation') or []:
        if variant is not None and entry['variant'] != variant: continue
        found = _run(lines, _encoded(entry))
        if found is None:
            left.append(f'the rotation records for {entry["variant"]} have changed; take them out by hand')
            continue
        del lines[found:found + len(entry['lines'])]
    return left


def _base_back(lines, changes):
    """The install's own records the editor commented out ([{original, written}]) put back in `lines` (in place);
    returns how many are no longer there as written."""
    missing = 0
    for change in changes:
        written = change['written'].encode('latin-1')
        at = next((i for i, l in enumerate(lines) if l == written), None)
        if at is None: missing += 1
        else: lines[at] = change['original'].encode('latin-1')
    return missing


def _strip_rotation(lines, ledger):
    """Everything a rotation install or a record switched off changed undone in `lines` (in place): the variants'
    records out, the install's own records the editor commented out live again."""
    _rotation_out(lines, ledger)
    _base_back(lines, ledger.get('linesOff') or [])


def pristine_lines(game, lines=None):
    """DefaultMaps.ini's lines (bytes, CRLF split) as the install has them: the editor's variant records taken out
    (any record one stood in for put back), its rotation installs undone, and an earlier version's intro line swapped
    back."""
    import deploy_fixture as dep
    lines = list(lines if lines is not None else dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes()))
    ledger = read_ledger(game)
    at = _ours(ledger, lines)
    if at is not None: lines[at] = ledger['slot']['original'].encode('latin-1')
    for block in ledger.get('records') or []:
        _take_out(lines, block)
    _strip_rotation(lines, ledger)
    return lines


def maps_text(game):
    """The install's DefaultMaps.ini text (latin-1) with the editor's lines taken out; the file's own text when the
    editor has changed nothing (or the file's line endings are mixed, which an install of the editor's never writes)."""
    path = config(game, 'DefaultMaps.ini')
    data = path.read_bytes()
    data = data[3:] if data.startswith(bytes([0xEF, 0xBB, 0xBF])) else data
    ledger = read_ledger(game)
    if not ledger.get('slot') and not ledger.get('records') and not ledger.get('rotation') and not ledger.get('linesOff'): return data.decode('latin-1')
    try: return b'\r\n'.join(pristine_lines(game)).decode('latin-1')
    except ValueError: return data.decode('latin-1')


def ready(game):
    """None when the install can be changed and played now, else why not."""
    game = Path(game)
    if not config(game, 'DefaultMaps.ini').is_file(): return f'{game} has no XEW\\XComGame\\Config\\DefaultMaps.ini'
    if not cooked(game).is_dir(): return f'{game} has no XEW\\XComGame\\CookedPCConsole'
    try:
        import deploy_fixture as dep
        dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
        read_ledger(game)
    except (OSError, ValueError, InstallError) as error:
        return f'its DefaultMaps.ini or the editor\'s record of it can\'t be read ({error})'
    if game_running(): return 'XCOM is running'
    return None


def status(game):
    """What the editor has in the install: the variants it installed (the last first), whether the commands file and
    config kept aside for a play are there, and an earlier version's intro install, if one is still in."""
    import deploy_fixture as dep
    ledger = read_ledger(game)
    lines = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    installed = sorted((ledger.get('installed') or {}).values(), key=lambda i: i.get('installedAt') or '', reverse=True)
    at = _ours(ledger, lines)
    intro = None if at is None else dict(map=dep.field(lines[at], 'Name'),
                                         ownMap=dep.field(ledger['slot']['original'].encode('latin-1'), 'Name'))
    rotation = [{k: v for k, v in entry.items() if k != 'lines'} for entry in ledger.get('rotation') or []]
    off = ledger.get('linesOff') or []
    return dict(installed=installed, intro=intro, playFile=play_file(game).is_file(), rotation=rotation,
                recordsOff=len(off), switchedOff=len(ledger.get('manualOff') or []),
                configKept=bool(ledger.get('config')), savesKept=bool(ledger.get('saves')),
                lastSaves=ledger.get('lastSaves'), lastPlay=ledger.get('lastPlay'),
                play=bool(ledger.get('records') or ledger.get('playZones') or ledger.get('playFiles') or play_file(game).is_file()
                         or start_file(game).is_file()),
                anything=bool(installed or intro or rotation or off or ledger.get('records') or ledger.get('landingZones') or ledger.get('files')
                              or ledger.get('playZones') or ledger.get('playFiles')
                              or ledger.get('config') or play_file(game).is_file() or start_file(game).is_file()))


def _check_ready(game):
    why = ready(game)
    if why: raise InstallError(why)


def _backup(game, stamp):
    folder = Path(game) / LEDGER_FOLDER / 'backups' / stamp
    k = 2
    while folder.exists(): folder, k = folder.with_name(f'{stamp}-{k}'), k + 1
    folder.mkdir(parents=True)
    for name in ('DefaultMaps.ini', LZ):
        if config(game, name).is_file(): shutil.copy2(config(game, name), folder / name)
    return folder


def _now(now):
    now = now or datetime.datetime.now()
    return now, now.strftime('%Y%m%d-%H%M%S')


def base_records(lines, base):
    """[(index, record)] of the base map's records in DefaultMaps.ini's lines (bytes): its live records, or, for a map
    whose records are commented out that the editor takes (maplist.SWITCHED_OFF: Act1_IntroLevel), those records
    without the ';'."""
    import deploy_fixture as dep
    import maplist
    live = [(i, l) for i, l in enumerate(lines) if dep.is_record(l) and dep.field(l, 'Name') == base]
    if live or base not in maplist.SWITCHED_OFF: return live
    found = []
    for i, l in enumerate(lines):
        record = maplist.switched_off(l.decode('latin-1'), ())
        if record and maplist.field(record, 'Name') == base: found.append((i, record.encode('latin-1')))
    return found


def _after_base(lines, ledger, base):
    """The index after the base map's last record in `lines`: its live records, the ones the editor commented out
    (a replaced map's, or switched off in the Game maps window), or, for a map the install comments out that the editor
    takes (maplist.SWITCHED_OFF), those. None when it has none."""
    import deploy_fixture as dep
    off = {c['written'].encode('latin-1') for c in ledger.get('linesOff') or [] if c.get('base') == base}
    at = [i for i, l in enumerate(lines) if (dep.is_record(l) and dep.field(l, 'Name') == base) or l in off]
    if not at: at = [i for i, _ in base_records(lines, base)]
    return max(at) + 1 if at else None


def plan_record(lines, base, variant, streams=(), replace=None, note='', mission=None, index=None):
    """(where to insert, [a comment line, the record]): one of the base map's records under the variant's name and
    out of rotation: the one at `index` (the base map's records in file order: the export's `missions` order), else
    deploy_fixture.slot_record's (its abduction where it has one), streaming `streams` in free slots and each stream in
    `replace` (old name -> new) under its new name (the variant's own copy of the landing intro, F-45; a replacement
    the record doesn't stream is left out, and a `replace` it streams none of is an error). It goes after the base
    map's last record (base_records: a switched-off map's commented-out one, made live in the copy). The DisplayName
    keeps the base record's " |n" ending (LWR's records have one) and the text the game matches in it (missions.py,
    '_Bomb'). The record keeps its kind (a play is the mission's own: mission types plan, A1); `mission` puts another
    in its place (TEST_MISSION: a prefab test, whose map has no mission)."""
    import deploy_fixture as dep
    import missions
    found = base_records(lines, base)
    if not found: raise ValueError(f'no record for {base}')
    records = [r for _, r in found]
    if index is not None and not 0 <= index < len(records): raise ValueError(f'{base} has no mission {index + 1}')
    new = records[dep.slot_record(records, list(range(len(records)))) if index is None else index]
    display = dep.field(new, 'DisplayName') or ''
    ending = re.search(r' \|\d+$', display)
    new = dep.set_field(new, 'Name', variant)
    new = dep.set_field(new, 'DisplayName', missions.display_name(display, variant, RECORD_NOTE, ending.group(0) if ending else ''))
    if dep.unquoted(new, 'bInRotation') is None: raise ValueError(f'{base}\'s record has no bInRotation to turn off')
    new = dep.set_field(new, 'bInRotation', 'False', quoted=False)
    if mission and dep.unquoted(new, 'MissionType') != mission: new = dep.set_field(new, 'MissionType', mission, quoted=False)
    for patch in streams:
        new, _ = dep.add_stream(new, patch)
    present = {was: now for was, now in (replace or {}).items() if f'MapName="{was}"'.encode() in new}
    if replace and not present: raise ValueError(f'the record streams none of {", ".join(replace)} to replace')
    for was, now in present.items():
        new = new.replace(f'MapName="{was}"'.encode(), f'MapName="{now}"'.encode())
    comment = f'; {variant}: {base}\'s record under its own name, out of rotation ({note})'.encode()
    return found[-1][0] + 1, [comment, new]


def mission_id(value):
    """A mission as a play names it (POST /play/start's `mission`): the index of one of the map's records (the
    export's `missions` order, an int) or a kind a project adds that its base map has no record of (a KINDS key such as
    'TerrorSite', Part D of the mission types plan). None stays None (the first). A ValueError otherwise."""
    if value is None: return None
    if isinstance(value, bool): raise ValueError('a mission is a record\'s index or a kind')
    if isinstance(value, int):
        if 0 <= value < 1000: return value
        raise ValueError(f'no mission {value}')
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z]{1,40}(/[A-Za-z]{1,40})?', value): return value
    raise ValueError('a mission is a record\'s index or a kind')


def build_record(m, pristine, mission=None):
    """The record a play of a package installs for one of its missions (mission types plan, A1): (record bytes, its
    mission id, the mission's label, whether it is the Build's own line). It is the Build's own line for that mission (the manifest's config.maps: under
    the variant's name, out of rotation, streaming the package's patch and its own copies of the intros and streams,
    with its display name), so the battle is the mission's own kind, with its council type, streams and DynamicAliens.
    mission: one of the package's missions (config.recordMissions, one list of ids per record: the index of the base
    map's record it was made from, or the kind a project added, Part D); None, its first record. A package from
    before the manifest named them (no recordMissions) takes the record at that index of config.maps when there is one
    per base map record, else (or with no config.maps) the base map's record at that index from the install, as
    plan_record makes it (then the fourth value, own, is False)."""
    import deploy_fixture as dep
    import missions
    c = m.get('config') or {}
    maps, ids = c.get('maps') or [], c.get('recordMissions')
    base, variant = m['source']['map'], m['variant']
    if ids is not None and len(ids) == len(maps) and maps:
        at = 0 if mission is None else next((k for k, these in enumerate(ids) if mission in these), None)
        if at is None:
            raise InstallError(f'the last build of {variant} has no such mission (it was built for '
                               f'{", ".join(c.get("missions") or []) or "other missions"}): build it again')
        record = maps[at].encode('latin-1')
        return record, ids[at][0], missions.label(missions.kind_key(record)), True
    if not isinstance(mission, (int, type(None))):
        raise InstallError(f'the last build of {variant} has no such mission: build it again')
    index = mission or 0
    if maps and len(maps) == len(base_records(pristine, base)):
        record = maps[index].encode('latin-1') if index < len(maps) else None
        if record is not None: return record, index, missions.label(missions.kind_key(record)), True
    try:
        _, (_, record) = plan_record(pristine, base, variant, streams=m.get('streams') or [],
                                     replace=m.get('replaceStreams') or {}, index=index)
    except ValueError as error: raise InstallError(str(error))
    return record, index, missions.label(missions.kind_key(record)), False


def _restore_intro(ledger, maps):
    """An earlier version's intro install taken out of `maps` (in place): True when the slot line went back."""
    at = _ours(ledger, maps)
    if at is not None: maps[at] = ledger['slot']['original'].encode('latin-1')
    ledger['slot'], ledger['intro'] = None, None
    return at is not None


def read_package(folder, game=None):
    """A variant package's manifest and its files, each checked against the manifest: (manifest, [(file, where it goes
    in `game`'s CookedPCConsole or None without a game, sha256)])."""
    folder = Path(folder)
    try: m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as error: raise InstallError(f'{folder} has no readable manifest ({error})')
    if not isinstance(m, dict) or m.get('schema') != PACKAGE_SCHEMA or not isinstance(m.get('files'), dict):
        raise InstallError(f'{folder} is not a variant package')
    files = []
    for rel, digest in m['files'].items():
        if not re.fullmatch(r'CookedPCConsole/[A-Za-z0-9_.-]+', rel) or Path(rel).name in ('.', '..'):
            raise InstallError(f'{folder} names a file outside its package')
        src = folder / rel
        if not src.is_file(): raise InstallError(f'{src} is missing')
        if sha256(src) != digest: raise InstallError(f'{src} differs from its manifest; build the project again')
        files.append((src, cooked(game) / src.name if game is not None else None, digest))
    return m, files


def noted_files(ledger):
    """{file name in lower case: (its name, its hash as installed)} of the files the editor copied in and still notes
    (a campaign's `files` and a play's `playFiles`)."""
    return {k.lower(): (k, v) for key in ('files', 'playFiles') for k, v in (ledger.get(key) or {}).items()}


def file_owners(ledger):
    """{file name in lower case: project id} for the files the editor copied in, as noted since 16 November 2026
    (`owners`). A ledger from before notes the files alone."""
    return {k.lower(): v for k, v in (ledger.get('owners') or {}).items() if isinstance(v, str) and v}


def lab_deploys(game, lab=None):
    """{file name in lower case: {the SHA-256s it was put there with, or None for any bytes}} of the files the lab's own
    deploy tools put into `game`'s CookedPCConsole before the editor could install, and noted in no ledger of the
    editor's:
    - the bake fixtures' installer (tools/bake/deploy_fixture.py): its ledger <lab>/bake-fixtures/deployed.json, each
      file's path and hash;
    - the lab's patchtool (<lab>/patchtool): the patches its deployed.txt names (it notes no hash) and the maps its
      seeded.txt seeded last, with their hash (deploy_fixture.patchtool_owns reads them the same way).
    Their names come from projects' output names, so such a file is a project's earlier test. Only for the lab copy (its
    XComLab-copy.txt marker) with the lab setting set (`lab` stands in for it); for any other install, or with no lab,
    nothing. A ledger that can't be read adds nothing."""
    import settings
    game = Path(game)
    if not (game / settings.LAB_MARKER).is_file(): return {}
    lab = settings.configured('lab') if lab is None else Path(lab)
    if lab is None: return {}
    here = os.path.normcase(os.path.abspath(cooked(game)))
    found = {}

    def add(name, digest):
        found.setdefault(name.lower(), set()).add(digest.lower() if isinstance(digest, str) else None)
    try: fixtures = json.loads((lab / 'bake-fixtures' / 'deployed.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): fixtures = {}
    for path, digest in fixtures.items() if isinstance(fixtures, dict) else ():
        if isinstance(path, str) and isinstance(digest, str) and os.path.normcase(os.path.abspath(Path(path).parent)) == here:
            add(Path(path).name, digest)
    patchtool = lab / 'patchtool'
    try: names = (patchtool / 'deployed.txt').read_text(encoding='utf-8', errors='replace').split()
    except OSError: names = []
    for name in names:
        if PACKAGE_NAME.fullmatch(name): add(f'{name}.upk', None)
    try: rows = (patchtool / 'seeded.txt').read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError: rows = []
    last = {}
    for row in (line.split('\t') for line in rows if line.strip()):
        if len(row) >= 5 and PACKAGE_NAME.fullmatch(row[1].strip()): last[row[1].strip().lower()] = row[4].strip()
    for name, digest in last.items(): add(f'{name}.upk', digest)
    return found


def lab_file(deploys, name, digest):
    """Whether lab_deploys' `deploys` say the lab put the file `name` there with these bytes (`digest`)."""
    put = deploys.get(name.lower())
    return bool(put) and (None in put or digest.lower() in put)


def recorded_variants(ledger):
    """{variant: project id or None} for what the editor installed under a name of its own: the variants Play in game
    installed (`installed`, a map's record there too) and the campaign installs (`rotation`)."""
    found = {}
    for name, entry in (ledger.get('installed') or {}).items():
        found[entry.get('map') or name] = (entry.get('project') or {}).get('id') if entry.get('kind') == 'project' else None
    for entry in ledger.get('rotation') or []:
        found[entry['variant']] = (entry.get('project') or {}).get('id')
    return found


def _owner(ledger, name, m, files):
    """The project whose a file the editor noted is: as `owners` says, else (a ledger from before owners were noted)
    the project the ledger says installed this package's variant, for a file of this package's own list (the
    variant's names are its project's, so that is the earlier build of it). None when nothing says."""
    owner = file_owners(ledger).get(name.lower())
    if owner: return owner
    if not any(dst.name.lower() == name.lower() for _, dst, _ in files): return None
    variant = m['variant'].lower()
    return next((p for v, p in recorded_variants(ledger).items() if v.lower() == variant and p), None)


def preflight(game, ledger, m, files):
    """Before a package is installed, nothing written yet: refused (an InstallError naming each problem) when its
    variant is installed for another project, or when one of its files is in CookedPCConsole (any case) and may not be
    replaced. A file may be replaced only where the editor noted it, for this project (file_owners, or for a ledger
    from before, _owner), unchanged since it was copied; a file the editor never put there is left alone, and stays
    whoever's it is when it already has the package's bytes. The one exception: a file of the package's own names that
    the lab's deploy tools put there, with the bytes they gave it (lab_deploys), is an earlier test of the project and
    may be replaced (_copy_files keeps it first)."""
    project = (m.get('project') or {}).get('id')
    variant = m['variant']
    problems = []
    lab = None
    for name, owner in recorded_variants(ledger).items():
        if name.lower() == variant.lower() and owner != project:
            problems.append(f'{name} is installed in this game for another project; remove it from the game (Remove '
                            f'from game, or the project manager) or save this project under a new name')
    there = {p.name.lower(): p for p in cooked(game).iterdir()} if cooked(game).is_dir() else {}
    noted = noted_files(ledger)
    for _, dst, digest in files:
        path = there.get(dst.name.lower())
        if path is None: continue
        current = sha256(path)
        entry = noted.get(dst.name.lower())
        if entry is None:
            if current != digest:
                lab = lab_deploys(game) if lab is None else lab
                if lab_file(lab, path.name, current): continue
                problems.append(f'{path.name} is in CookedPCConsole and the editor didn\'t put it there; it is left '
                                f'alone (move it away to install this build)')
            continue
        owner = _owner(ledger, path.name, m, files)
        if owner is None:
            problems.append(f'{path.name} was installed by the editor, and nothing says for which project; take '
                            f'everything back out (Remove from game) first')
        elif owner != project:
            problems.append(f'{path.name} was installed for another project; remove that one from the game first')
        elif current != digest and current != entry[1]:
            problems.append(f'{path.name} has changed since the editor installed it; it is left alone (move it '
                            f'away to install this build)')
    if problems:
        raise InstallError('Not installed: ' + '; '.join(problems) + '.')


def _copy_files(game, ledger, files, play=False, atomic=None, project=None, keep=None):
    """A package's files copied into the install (read_package's list), the ones the editor put there noted in the
    ledger, which is written. A file is noted once: in `files` when an install for campaigns needs it, else in
    `playFiles` (a play's, which go when the game closes). So an install for campaigns takes over a file a play put
    there, and a play that brings a newer build of a variant installed for campaigns leaves the file the campaign's.
    `project`: whose the noted files are (`owners`). Run preflight first: this replaces what it is given. `keep`: the
    change's backup folder (_backup), where a file the editor didn't put there (preflight lets through only the lab's
    earlier tests of the project: lab_deploys) is copied before it is replaced, and noted (`labFiles`: its name -> the
    copy, from the game folder) so that _files_out puts it back."""
    kept, played = ledger.setdefault('files', {}), ledger.setdefault('playFiles', {})
    owners = ledger.setdefault('owners', {})
    noted = noted_files(ledger)
    for src, dst, digest in files:
        name = dst.name
        if not (dst.exists() and sha256(dst) == digest):
            if keep is not None and dst.exists() and name.lower() not in noted:
                (Path(keep) / 'CookedPCConsole').mkdir(parents=True, exist_ok=True)
                copy = Path(keep) / 'CookedPCConsole' / name
                shutil.copy2(dst, copy)
                ledger.setdefault('labFiles', {})[name] = str(copy.relative_to(game))
            target = test_temp(dst, atomic) if atomic else dst
            try:
                shutil.copyfile(src, target)
                if sha256(target) != digest: raise InstallError(f'{dst} did not copy intact')
                if atomic:
                    if dst.exists(): raise InstallError(f'{dst} appeared while the test was installing')
                    os.replace(target, dst)
            finally:
                if atomic: target.unlink(missing_ok=True)
            if play and name not in kept: played[name] = digest
            else: kept[name] = digest
        elif not play and name in played:
            kept[name] = played[name]       # already there as built by a play: the campaign's from now on
        # else already there as built (ours, or put there by another tool: then it stays theirs)
        if name in kept: played.pop(name, None)
        # a noted file is this project's (preflight has made sure of that)
        if project and (name in kept or name in played): owners[name] = project
    write_ledger(game, ledger)


def test_install_path(game):
    return play_ledger_path(game).with_name('prefab-test-install.json')


def test_temp(path, test):
    return path.with_name(f'.{path.name}.{test}.tmp')


def replace_bytes(path, data, test):
    temp = test_temp(path, test)
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def begin_test_install(game, test, files, writes):
    """Keep enough of this play's planned writes to undo an interrupted install."""
    journal = test_install_path(game)
    if journal.exists(): raise InstallError('The previous prefab test install needs to be restored.')
    created = {}
    for _, dst, digest in files:
        if dst.exists():
            if sha256(dst) != digest:
                raise InstallError(f'{dst.name} already exists with different contents.')
        else:
            created[dst.name] = digest
    play = play_ledger_path(game)
    _write_json(journal, dict(test=test, files=created, play=play.read_bytes().hex() if play.exists() else None,
                              config={name: dict(before=config(game, name).read_bytes().hex(),
                                                 after=hashlib.sha256(data).hexdigest())
                                      for name, data in writes.items()}))


def recover_test_install(game):
    journal = test_install_path(game)
    if not journal.is_file(): return
    if game_running(): raise InstallError('XCOM is running')
    pending = json.loads(journal.read_text(encoding='utf-8'))
    test = pending['test']
    if not re.fullmatch(r'[0-9a-f-]{36}', test): raise InstallError('Invalid test install journal.')
    for name, change in pending['config'].items():
        if name not in ('DefaultMaps.ini', LZ): raise InstallError('Unknown file in the test install journal.')
        path = config(game, name)
        original = bytes.fromhex(change['before'])
        actual = sha256(path)
        if actual == change['after']:
            replace_bytes(path, original, test)
        elif actual != hashlib.sha256(original).hexdigest():
            raise InstallError(f'{name} changed during the test install and needs to be restored.')
        test_temp(path, test).unlink(missing_ok=True)
    for name, digest in pending['files'].items():
        if Path(name).name != name: raise InstallError('Unknown package file in the test install journal.')
        path = cooked(game) / name
        if path.is_file():
            if sha256(path) != digest: raise InstallError(f'{name} changed during the test install.')
            path.unlink()
        test_temp(path, test).unlink(missing_ok=True)
    play = play_ledger_path(game)
    if pending['play'] is None:
        play.unlink(missing_ok=True)
    else:
        replace_bytes(play, bytes.fromhex(pending['play']), test)
    journal.unlink()


def _zones_out(game, ledger, key, variants=None):
    """The landing-zone lines the ledger notes under `key` taken out of DefaultLZMutator.ini (every variant's, or
    these): (how many variants' lines went, what was left in words). The ledger's list is updated, not written."""
    import deploy_fixture as dep
    blocks = [b for b in ledger.get(key) or [] if variants is None or b['variant'] in variants]
    if not blocks or not config(game, LZ).is_file(): return 0, []
    lz = dep.lines_of(config(game, LZ).read_bytes())
    done, left = 0, []
    for block in blocks:
        want = _encoded(block)
        found = _run(lz, want)
        if found is None:
            left.append(f'the landing-zone lines for {block["variant"]} have changed; take them out by hand')
            continue
        new_lz = lz[:found] + lz[found + len(want):]
        dep.check_change(lz, new_lz, removed=(found, len(want)))
        lz = new_lz
        done += 1
    if done: dep.write_checked(config(game, LZ), lz)
    ledger[key] = [b for b in ledger.get(key) or [] if b not in blocks]
    return done, left


def _files_out(game, ledger, key):
    """The files the ledger notes under `key` deleted from the install, unless changed since: (names, what was left).
    A file that replaced one of the lab's (`labFiles`: _copy_files kept it) has the lab's back in its place."""
    done, left = [], []
    lab = ledger.get('labFiles') or {}
    for name, digest in sorted((ledger.get(key) or {}).items()):
        path = cooked(game) / name
        if not path.exists(): continue
        if sha256(path) != digest:
            left.append(f'{name} has changed since it was installed; it stays')
            continue
        earlier = Path(game) / lab[name] if name in lab else None
        if earlier is not None and earlier.is_file():
            temp = path.with_name(f'.{name}.lab.tmp')
            shutil.copy2(earlier, temp)
            os.replace(temp, path)
        else:
            path.unlink()
        done.append(name)
    ledger[key] = {}
    # whose each file is, and the lab's files kept, for the files still noted
    noted = {k for other in ('files', 'playFiles') for k in ledger.get(other) or {}}
    for what in ('owners', 'labFiles'):
        if what in ledger:
            ledger[what] = {k: v for k, v in ledger[what].items() if k in noted}
    return done, left


def clear_play(game, now=None):
    """What a play put in the install taken out again (play.json): the record of the build or map played, the landing
    zones and files a play copied in, and the commands file. The installs for campaigns and the records switched off
    stay. Run once the game has closed (play.py's watch), and before the next play. Returns what it did, or None when
    there was nothing."""
    import deploy_fixture as dep
    game = Path(game)
    ledger = read_ledger(game)
    records = ledger.get('records') or []
    if not (records or ledger.get('playZones') or ledger.get('playFiles') or play_file(game).is_file()
            or start_file(game).is_file()): return None
    _check_ready(game)
    now, stamp = _now(now)
    done = dict(records=0, landingZones=0, files=[], left=[], playFile=False)
    if records:
        maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
        ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
        new_maps, kept = list(maps), []
        for block in records:
            if _take_out(new_maps, block): done['records'] += 1
            else:
                done['left'].append(f'the record for {block["variant"]} has changed; take it out by hand')
                kept.append(block)
        if new_maps != maps: dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
        ledger['records'] = kept
        ledger['installed'] = {k: v for k, v in (ledger.get('installed') or {}).items() if k in {b['variant'] for b in kept}}
    done['landingZones'], left = _zones_out(game, ledger, 'playZones')
    done['left'] += left
    done['files'], left = _files_out(game, ledger, 'playFiles')
    done['left'] += left
    done['playFile'] = _commands_out(game)
    ledger.setdefault('history', []).append(dict(at=now.isoformat(timespec='seconds'), playCleared=True, records=done['records'],
                                                  files=len(done['files'])))
    write_ledger(game, ledger)
    return done


# One install into a game at a time in this process (the server's), from the preflight to the last write; two servers
# on one install are not kept apart.
_INSTALLING = threading.RLock()


def install_package(game, folder, now=None, **options):
    with _INSTALLING: return _install_package(game, folder, now, **options)


def _install_package(game, folder, now=None, *, expected=None, test=None, zone=None, mission=None):
    """Install a variant package (a folder with manifest.json) so that the game can open it by name; returns what was
    installed. An earlier build of the same variant, of the same project, is replaced; anything of another project's,
    or a file the editor didn't put there, is never replaced (preflight, before anything is written). `mission` (mission_id): which of the package's
    missions the record is (build_record: the Build's own line for it; None, its first); a prefab test's is
    plan_record's with TEST_MISSION. The result's `record` is the record's text, for the play's commands
    (missions.play_setup), and `mission` its id and label. `zone` (Land here: one of the project's landing
    zones, by id): under LWR that zone's line alone goes in; for a zone that is one of the map's own landings the
    result's `spawnGroup` names its group, for the play's open command (a plain install plays no lines)."""
    import deploy_fixture as dep
    game, folder = Path(game), Path(folder)
    m, files = read_package(folder, game)
    if expected is not None and m != expected:
        raise InstallError('The package changed since the prefab test verified it.')
    _check_ready(game)
    variant, base = m['variant'], m['source']['map']
    ledger = read_ledger(game)
    if test and any(entry['variant'] == variant for entry in ledger.get('rotation') or []):
        raise InstallError(f'{variant} already belongs to a campaign install.')
    now, stamp = _now(now)
    note = f'{RECORD_NOTE}, {stamp[:8]}'
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    lz = dep.lines_of(config(game, LZ).read_bytes()) if config(game, LZ).is_file() else None
    pristine = pristine_lines(game, maps)
    foreign = [i for i, l in enumerate(pristine) if dep.is_record(l) and (dep.field(l, 'Name') or '').lower() == variant.lower()]
    if foreign and patchtool_record(pristine, variant) is None:
        raise InstallError(f'DefaultMaps.ini has a record named {variant} (line {foreign[0] + 1}) that neither the editor '
                           'nor patchtool wrote; take it out first')
    if test:
        _, block = plan_record(pristine, base, variant, streams=m.get('streams') or [], replace=m.get('replaceStreams') or {},
                               note=note, mission=TEST_MISSION)
        chosen = None
    else:
        record, picked, label, own = build_record(m, pristine, mission)
        what = f'the build\'s {label} record' if own else f'{base}\'s {label} record under its own name'
        block = [f'; {variant}: {what}, out of rotation ({note})'.encode(), record]
        chosen = dict(id=picked, label=label)
    for patch in list(m.get('streams') or []) + list((m.get('replaceStreams') or {}).values()):
        if not any(dst.name.lower() == f'{patch}.upk'.lower() for _, dst, _ in files) and not (cooked(game) / f'{patch}.upk').is_file():
            raise InstallError(f'{patch}.upk is in neither the package nor the install')
    preflight(game, ledger, m, files)
    lz_at, lz_new = plan_variant_lz(lz, m, note, zone) if lz is not None else (None, [])
    # DefaultMaps.ini: an earlier build's record of this variant out (what it stood in for back), an earlier version's
    # intro line back, the new record in place of a patchtool record of the variant, else after the base map's last one
    new_maps = list(maps)
    records = ledger.get('records') or []
    for old in [b for b in records if b['variant'] == variant]:
        if not _take_out(new_maps, old): raise InstallError(f'the record the editor wrote for {variant} has changed; take it out by hand')
    intro_back = _restore_intro(ledger, new_maps)
    entry = dict(variant=variant, lines=[l.decode('latin-1') for l in block])
    stands_in = patchtool_record(new_maps, variant)
    if stands_in is not None:
        entry['original'] = [l.decode('latin-1') for l in new_maps[stands_in:stands_in + 2]]
        new_maps[stands_in:stands_in + 2] = block
    else:
        at = _after_base(new_maps, ledger, base)
        if at is None: raise InstallError(f'DefaultMaps.ini has no record for {base}')
        new_maps[at:at] = block
    # the result without the editor's lines must be the install's own lines
    check = list(new_maps)
    for b in [entry] + [b for b in records if b['variant'] != variant]:
        _take_out(check, b)
    _strip_rotation(check, ledger)
    if check != pristine: raise InstallError('planned change touches other lines')
    new_lz = None
    if lz_new:
        new_lz = lz[:lz_at] + lz_new + lz[lz_at:]
        dep.check_change(lz, new_lz, inserted=(lz_at, len(lz_new)))
    kept = _backup(game, stamp)
    ledger['backups'] = ledger.get('backups', []) + [str(kept.relative_to(game))]
    writes = {'DefaultMaps.ini': dep.EOL.join(new_maps)}
    if new_lz is not None:
        writes[LZ] = dep.EOL.join(new_lz)
    if test:
        begin_test_install(game, test, files, writes)
    _copy_files(game, ledger, files, play=True, atomic=test, project=(m.get('project') or {}).get('id'),
                keep=None if test else kept)
    if test:
        for name, data in writes.items():
            replace_bytes(config(game, name), data, test)
    else:
        dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
        if new_lz is not None: dep.write_checked(config(game, LZ), new_lz)
    ledger['records'] = [b for b in records if b['variant'] != variant] + [entry]
    if lz_new:
        ledger.setdefault('playZones', []).append(dict(variant=variant, lines=[l.decode('latin-1') for l in lz_new]))
    project = m.get('project') or {}
    installed = dict(kind='project', map=variant, base=base, buildId=m.get('buildId'), installedAt=now.isoformat(timespec='seconds'),
                     project=dict(id=project.get('id'), name=project.get('name'), revision=project.get('revision')),
                     quick=bool(m.get('quick')))     # a quick build: its lighting not baked
    if test:
        installed['prefabTest'] = test
    if chosen:
        installed['mission'] = chosen
    ledger.setdefault('installed', {})[variant] = installed
    ledger.setdefault('history', []).append(dict(at=installed['installedAt'], installed=variant, buildId=m.get('buildId'),
                                                 **({'introBack': True} if intro_back else {}),
                                                 **({'standsInFor': 'patchtool'} if 'original' in entry else {})))
    write_ledger(game, ledger)
    if test:
        test_install_path(game).unlink()
    group = next((g['group'] for g in (m.get('config') or {}).get('ownLandingGroups') or [] if g['zone'] == zone), None) \
        if zone is not None else None
    return dict(installed, introBack=intro_back, standsInFor='patchtool' if 'original' in entry else None,
                record=block[1].decode('latin-1'),
                **({'zone': zone} if zone is not None else {}), **({'spawnGroup': group} if group else {}))


def map_record(game, name, mission=None):
    """The record a play of a map alone plays for `mission` (an index into the map's records in file order, the
    export's `missions` order; None, the first): its text (bytes), from the install's own lines (the editor's taken
    out), or None for a map with no record. An InstallError for an index the map hasn't."""
    import deploy_fixture as dep
    found = base_records(pristine_lines(game, dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())), name)
    if not found: return None
    index = mission or 0
    if not isinstance(index, int) or not 0 <= index < len(found):
        raise InstallError(f'{name} has no such mission (it has {len(found)} record{"s" if len(found) != 1 else ""})')
    return found[index][1]


def install_map_record(game, name, mission=None, now=None):
    """Before a play of a map alone: the record of the mission picked (`mission`: map_record's index; None, the
    first), where the game wouldn't find it first by the map's name. The game takes the first record in the file
    whose Name is the map (F-105), and with none it crashes 8 s into the battle (EXP-30 run 1). So:
    - a map whose first live record is that record needs nothing (None is returned);
    - otherwise a copy of the record goes in, out of rotation, ahead of the map's first live record (after its last
      record when none is live). The game then finds it first by the map's name, and again by its display name for
      the streams. It keeps its display name (and with it what the game matches there: missions.py), and is otherwise
      the record exactly (mission types plan, A1, decision 3). The exceptions: a map whose records the install
      comments out (maplist.SWITCHED_OFF: Act1_IntroLevel) gets its record live, and a copy of a record the editor
      commented out (a project's build replaces the map, or it was switched off in the Game maps window) gets a display
      name of its own, so that no mission the game asks for by name finds it.
    Returns what was installed, or None. An earlier play's copy is replaced; Remove from game takes it out."""
    import deploy_fixture as dep
    import maplist
    import missions
    game = Path(game)
    ledger = read_ledger(game)
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    pristine = pristine_lines(game, maps)
    found = base_records(pristine, name)
    if not found: return None
    index = mission or 0
    if not isinstance(index, int) or not 0 <= index < len(found): raise InstallError(f'{name} has no such mission')
    target = found[index][1]
    switched = not any(dep.is_record(l) and dep.field(l, 'Name') == name for l in pristine)
    new_maps = list(maps)
    old = [b for b in ledger.get('records') or [] if b['variant'] == name]
    for b in old:
        if not _take_out(new_maps, b): raise InstallError(f'the record the editor wrote for {name} has changed; take it out by hand')
    live = [i for i, l in enumerate(new_maps) if dep.is_record(l) and dep.field(l, 'Name') == name]
    if live and new_maps[live[0]] == target:
        if old:     # an earlier play's copy, no longer needed
            _check_ready(game)
            now, stamp = _now(now)
            ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
            dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
            ledger['records'] = [b for b in ledger.get('records') or [] if b['variant'] != name]
            (ledger.get('installed') or {}).pop(name, None)
            write_ledger(game, ledger)
        return None
    _check_ready(game)
    now, stamp = _now(now)
    new = dep.set_field(target, 'bInRotation', 'False', quoted=False)
    off = not switched and not any(l == target for l in new_maps)     # the editor commented it out
    label = missions.label(missions.kind_key(target))
    if switched:
        why = 'its commented-out record, live for a play of the map, out of rotation'
    elif off:
        display = dep.field(new, 'DisplayName') or ''
        ending = re.search(r' \|\d+$', display)
        new = dep.set_field(new, 'DisplayName', missions.display_name(display, name, RECORD_NOTE, ending.group(0) if ending else ''))
        why = f'a copy of its {label} record for a play of the map, out of rotation, while its own are commented out'
    else:
        why = f'a copy of its {label} record for a play of that mission, out of rotation, ahead of its own'
    block = [f'; {name}: {why} ({RECORD_NOTE}, {stamp[:8]})'.encode(), new]
    ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
    at = live[0] if live else _after_base(new_maps, ledger, name)
    if at is None: raise InstallError(f'DefaultMaps.ini has no record for {name}')
    new_maps[at:at] = block
    entry = dict(variant=name, lines=[l.decode('latin-1') for l in block])
    others = [b for b in ledger.get('records') or [] if b['variant'] != name]
    check = list(new_maps)
    for b in [entry] + others:
        _take_out(check, b)
    _strip_rotation(check, ledger)
    if check != pristine: raise InstallError('planned change touches other lines')
    dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
    ledger['records'] = others + [entry]
    how = 'switched off' if switched else 'commented out by the editor' if off else 'ahead of its own'
    installed = dict(kind='map', map=name, base=name, installedAt=now.isoformat(timespec='seconds'), project=None,
                     mission=dict(id=index, label=label), how=how)
    ledger.setdefault('installed', {})[name] = installed
    ledger.setdefault('history', []).append(dict(at=installed['installedAt'], installed=name, mission=index, record=how))
    write_ledger(game, ledger)
    return installed


def _in_rotation(line):
    import deploy_fixture as dep
    return (dep.unquoted(line, 'bInRotation') or '').lower() == 'true'


def _first_mission(line):
    """Whether a record of the install is the one a new campaign's first mission asks for by name (FIRST_MISSION)."""
    import deploy_fixture as dep
    return (dep.field(line, 'DisplayName') or '') in FIRST_MISSION


def rotation_plan(lines, m, note='', mode='additional'):
    """A package's records for campaigns, from the install's own lines (pristine_lines) and the package's manifest:
    one record per record of the base map (its missions), each under the variant's name, in or out of rotation as the
    base map's record is, streaming the package's patch (if any) in a free slot and its own copies of the intros in
    place of the originals. dict(block=[a comment line, the records], missions=[{type, label, group, inRotation,
    byName, bomb, firstMission (when true)}] one per record). Two records the renaming makes the same give one.

    Display names: the game asks for a council mission's map (and the story's) by its record's DisplayName, not through
    the rotation; those records are out of rotation in the install (byName). So does a new campaign's first mission,
    whose record is in rotation (FIRST_MISSION, F-117). To replace the map, the variant's record for such a mission
    keeps the base map's DisplayName, whose own record is commented out (install_rotation). Every other record gets a
    name of its own: <variant> (<project>[, <mission>])."""
    import deploy_fixture as dep
    import maplist
    import missions as missions_module
    variant, base = m['variant'], m['source']['map']
    found = base_records(lines, base)
    if not found: raise ValueError(f'no record for {base}')
    c = m.get('config') or {}
    if c.get('maps') and isinstance(c.get('recordMissions'), list) and len(c['recordMissions']) == len(c['maps']):
        return _rotation_from_build(found, m, note, mode)
    name = re.sub(r'[^\x20-\x7E]|"|\|', '', (m.get('project') or {}).get('name') or '').strip()[:80] or 'variant'
    records, missions, seen = [], [], {}
    for _, line in found:
        group, kind, label = maplist.mission_of(line.decode('latin-1'))
        seen[label] = seen.get(label, 0) + 1
        mission = label if seen[label] == 1 else f'{label} {seen[label]}'      # a map with two records of one mission
        in_rotation, first = _in_rotation(line), _first_mission(line)
        by_name = not in_rotation or first
        new = dep.set_field(line, 'Name', variant)
        if not (by_name and mode == 'replace'):
            display = dep.field(line, 'DisplayName') or ''
            ending = re.search(r' \|\d+$', display)
            new = dep.set_field(new, 'DisplayName', missions_module.display_name(
                display, variant, '%s%s' % (name, f', {mission}' if len(found) > 1 else ''), ending.group(0) if ending else ''))
        for patch in m.get('streams') or []:
            new, _ = dep.add_stream(new, patch)
        for was, now in (m.get('replaceStreams') or {}).items():
            new = new.replace(f'MapName="{was}"'.encode(), f'MapName="{now}"'.encode())
        if new in records: continue
        records.append(new)
        missions.append(dict(type=kind, label=mission, group=group, inRotation=in_rotation, byName=by_name,
                             bomb=dep.unquoted(line, 'CouncilType') == 'eFCMType_Bomb', **({'firstMission': True} if first else {})))
    how = 'in place of' if mode == 'replace' else 'beside'
    comment = f'; {variant}: {base}\'s records under its own name, {how} {base}\'s ({note})'.encode()
    return dict(block=[comment] + records, missions=missions)


def _rotation_from_build(found, m, note, mode):
    """rotation_plan for a package whose manifest names the base map record (or added kind) each of its records stands
    for (config.recordMissions): the Build's own records (the project's missions only, mission types plan D4), each in
    or out of rotation as the base map's record is (an added kind as ADDED_KINDS says: a bomb out, the rest in), and
    in replace mode a record the game asks for by name (out of rotation, or the first mission's) with the base map's
    display name."""
    import deploy_fixture as dep
    import maplist
    import missions as missions_module
    variant, base = m['variant'], m['source']['map']
    records, out = [], []
    for line, ids in zip(m['config']['maps'], m['config']['recordMissions']):
        new = line.encode('latin-1')
        first = ids[0] if ids else None
        base_line = found[first][1] if isinstance(first, int) and 0 <= first < len(found) else None
        if base_line is not None:
            in_rotation = _in_rotation(base_line)
        else:
            in_rotation = (missions_module.ADDED_KINDS.get(first) or {}).get('rotation', True)
        first = base_line is not None and _first_mission(base_line)
        by_name = not in_rotation or first
        if dep.unquoted(new, 'bInRotation') is not None:
            new = dep.set_field(new, 'bInRotation', 'True' if in_rotation else 'False', quoted=False)
        if by_name and mode == 'replace' and base_line is not None:
            new = dep.set_field(new, 'DisplayName', dep.field(base_line, 'DisplayName') or '')
        if new in records: continue
        records.append(new)
        group, kind, label = maplist.mission_of(new.decode('latin-1'))
        out.append(dict(type=kind, label=label, group=group, inRotation=in_rotation, byName=by_name,
                        bomb=dep.unquoted(new, 'CouncilType') == 'eFCMType_Bomb',
                        **({} if base_line is not None else {'added': True}), **({'firstMission': True} if first else {})))
    how = 'in place of' if mode == 'replace' else 'beside'
    what = 'the records of the missions the project is for' if m['config'].get('missionsFromProject') else f'{base}\'s records'
    comment = f'; {variant}: {what} under its own name, {how} {base}\'s ({note})'.encode()
    return dict(block=[comment] + records, missions=out)


def mission_warnings(missions, base, mode, lwr=True):
    """What happens to the missions when a variant with these records (rotation_plan's missions) is installed for
    campaigns, in sentences. The missions whose records are out of rotation (council missions, the story's) get their
    map by its record's name: a variant can replace that map but not stand beside it, except that Long War's mutator
    makes an extra bomb mission of each extra bomb record. A replacing variant's first-mission record (in rotation, but
    asked for by name too: F-117) takes the original's name, so the variant plays a new campaign's first mission.
    Nothing here says a mission is untried (the user, 16 November 2026)."""
    named = [x for x in missions if not x['inRotation']]
    out = []
    if mode == 'replace':
        for x in missions:
            if x.get('firstMission'):
                out.append(f'{x["label"]}: a new campaign\'s first mission asks for {base}\'s record by name, so the variant '
                           'takes that record\'s name and plays the first mission.')
    if named and mode == 'replace':
        out.append(f'{", ".join(x["label"] for x in named)}: the game asks for {"these missions\' map" if len(named) > 1 else "this mission\'s map"} '
                   f'by name, so the variant takes {base}\'s record name there.')
    elif named:
        bombs = [x for x in named if x.get('bomb')] if lwr else []
        rest = [x for x in named if x not in bombs]
        if bombs:
            out.append(f'{", ".join(x["label"] for x in bombs)}: Long War makes an extra bomb mission of an extra bomb record, '
                       'so the variant turns up as one.')
        if rest:
            out.append(f'{", ".join(x["label"] for x in rest)}: the game asks for {"these missions\' map" if len(rest) > 1 else "this mission\'s map"} '
                       f'by name, so an additional map is never picked for {"them" if len(rest) > 1 else "it"}. '
                       'Replace the original to play the variant there.')
    return out


def _sync_off(lines, ledger, pristine):
    """The install's own records in `lines` (in place) commented out or live again, to follow the ledger: a record is
    commented out (a ';' before it: the game then never uses it, where bInRotation=False is not known to stop it)
    while a variant replaces its map (a rotation install with mode 'replace') or it is switched off by hand (manualOff:
    the Game maps window). What is commented out is kept in the ledger's linesOff ([{base, original, written}])."""
    import deploy_fixture as dep
    replaced = {e['base'] for e in ledger.get('rotation') or [] if e['mode'] == 'replace'}
    own = [l for l in pristine if dep.is_record(l)]
    manual = set(ledger.get('manualOff') or []) & {l.decode('latin-1') for l in own}
    want = [l for l in own if dep.field(l, 'Name') in replaced or l.decode('latin-1') in manual]
    wanted = {l.decode('latin-1') for l in want}
    kept = []
    for change in ledger.get('linesOff') or []:
        if change['original'] in wanted: kept.append(change)
        elif _base_back(lines, [change]):
            raise InstallError(f'a record of {change.get("base")} that the editor commented out has changed since; put it back by hand')
    have = {c['original'] for c in kept}
    for line in want:
        text = line.decode('latin-1')
        if text in have: continue
        at = next((i for i, l in enumerate(lines) if l == line), None)
        if at is None: raise InstallError(f'a record of {dep.field(line, "Name")} is not in DefaultMaps.ini as the editor knows it')
        lines[at] = b';' + line
        kept.append(dict(base=dep.field(line, 'Name'), original=text, written=';' + text))
        have.add(text)
    ledger['linesOff'], ledger['manualOff'] = kept, sorted(manual)


def _plan_rotation(ledger, new_maps, entries, pristine):
    """`new_maps` and the ledger (both in place) with the rotation installs `entries` (the install's own records
    following them and the ledger's manualOff: _sync_off), checked: the editor's changes undone leave the install's
    own lines. Writes nothing."""
    ledger['rotation'] = entries
    _sync_off(new_maps, ledger, pristine)
    check = list(new_maps)
    for b in ledger.get('records') or []:
        _take_out(check, b)
    _strip_rotation(check, ledger)
    if check != pristine: raise InstallError('planned change touches other lines')


def _write_rotation(game, ledger, maps, new_maps, entries, pristine):
    """DefaultMaps.ini written with the rotation installs `entries` (_plan_rotation)."""
    import deploy_fixture as dep
    _plan_rotation(ledger, new_maps, entries, pristine)
    if new_maps != maps: dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)


def install_rotation(game, folder, mode, now=None):
    with _INSTALLING: return _install_rotation(game, folder, mode, now)


def _install_rotation(game, folder, mode, now=None):
    """Install a variant package for campaigns: its files, its landing zones and its records for the rotation
    (rotation_plan), after the base map's own records. mode 'additional': the base map's records stay as they are, so
    missions draw from both; 'replace': the base map's own records are commented out, and the variant's records for
    the missions the game asks for by name take their names (they go back when no variant replaces the map any more:
    remove_rotation, reset). An earlier rotation install of the variant, of the same project, is replaced; what belongs
    to another project, or a file the editor didn't put there, is never replaced: everything is checked (preflight,
    the planned config lines) before anything is written. The record Play in game adds (install_package) is separate and stays first, so a play still
    opens the variant by it. Returns what was installed, with mission_warnings."""
    import deploy_fixture as dep
    if mode not in ROTATION_MODES: raise InstallError(f'mode must be one of {", ".join(ROTATION_MODES)}')
    game = Path(game)
    m, files = read_package(folder, game)
    _check_ready(game)
    variant, base = m['variant'], m['source']['map']
    ledger = read_ledger(game)
    now, stamp = _now(now)
    note = f'{RECORD_NOTE}, {stamp[:8]}'
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    lz = dep.lines_of(config(game, LZ).read_bytes()) if config(game, LZ).is_file() else None
    pristine = pristine_lines(game, maps)
    foreign = [i for i, l in enumerate(pristine) if dep.is_record(l) and (dep.field(l, 'Name') or '').lower() == variant.lower()]
    if foreign and patchtool_record(pristine, variant) is None:
        raise InstallError(f'DefaultMaps.ini has a record named {variant} (line {foreign[0] + 1}) that neither the editor '
                           'nor patchtool wrote; take it out first')
    plan = rotation_plan(pristine, m, note, mode)
    for patch in list(m.get('streams') or []) + list((m.get('replaceStreams') or {}).values()):
        if not any(dst.name.lower() == f'{patch}.upk'.lower() for _, dst, _ in files) and not (cooked(game) / f'{patch}.upk').is_file():
            raise InstallError(f'{patch}.upk is in neither the package nor the install')
    preflight(game, ledger, m, files)
    lz_at, lz_new = plan_variant_lz(lz, m, note) if lz is not None else (None, [])
    new_maps = list(maps)
    left = _rotation_out(new_maps, ledger, variant)
    if left: raise InstallError(left[0])
    at = _after_base(new_maps, ledger, base)
    if at is None: raise InstallError(f'DefaultMaps.ini has no record for {base}')
    # after the base map's last record, and after the records Play in game added there (they stay first)
    blocks = [_encoded(b) for b in ledger.get('records') or []]
    while True:
        block = next((b for b in blocks if b and new_maps[at:at + len(b)] == b), None)
        if block is None: break
        at += len(block)
    new_maps[at:at] = plan['block']
    project = m.get('project') or {}
    entry = dict(variant=variant, base=base, mode=mode, lines=[l.decode('latin-1') for l in plan['block']],
                 installedAt=now.isoformat(timespec='seconds'), buildId=m.get('buildId'), quick=bool(m.get('quick')),
                 project=dict(id=project.get('id'), name=project.get('name'), revision=project.get('revision')),
                 missions=plan['missions'])
    others = [e for e in ledger.get('rotation') or [] if e['variant'] != variant]
    # the planned lines checked on copies before anything is written
    _plan_rotation(json.loads(json.dumps(ledger)), list(new_maps), others + [entry], pristine)
    new_lz = None
    if lz_new:
        new_lz = lz[:lz_at] + lz_new + lz[lz_at:]
        dep.check_change(lz, new_lz, inserted=(lz_at, len(lz_new)))
    kept = _backup(game, stamp)
    ledger['backups'] = ledger.get('backups', []) + [str(kept.relative_to(game))]
    _copy_files(game, ledger, files, project=project.get('id'), keep=kept)
    _write_rotation(game, ledger, maps, new_maps, others + [entry], pristine)
    if new_lz is not None:
        dep.write_checked(config(game, LZ), new_lz)
        ledger.setdefault('landingZones', []).append(dict(variant=variant, lines=[l.decode('latin-1') for l in lz_new]))
    else:
        # the variant's landing zones a play put there are the campaign's from now on
        taken = [b for b in ledger.get('playZones') or [] if b['variant'] == variant]
        ledger['playZones'] = [b for b in ledger.get('playZones') or [] if b not in taken]
        ledger['landingZones'] = (ledger.get('landingZones') or []) + taken
    ledger.setdefault('history', []).append(dict(at=entry['installedAt'], rotation=variant, mode=mode, buildId=m.get('buildId')))
    write_ledger(game, ledger)
    import settings
    warnings = mission_warnings(plan['missions'], base, mode, lwr=settings.game_kind(game) == 'lwr')
    rivals = [e['variant'] for e in others if e['base'] == base and e['mode'] == 'replace'] if mode == 'replace' else []
    if rivals and any(x['byName'] for x in plan['missions']):
        warnings.append(f'{", ".join(rivals)} replace{"s" if len(rivals) == 1 else ""} {base} too: for a mission the game asks for by name, it plays one of them.')
    return dict({k: v for k, v in entry.items() if k != 'lines'},
                switchedOff=sum(1 for c in ledger.get('linesOff') or [] if c.get('base') == base) if mode == 'replace' else 0,
                warnings=warnings)


def remove_rotation(game, variants, now=None, everything=False):
    """Take these variants' records out of the rotation again (install_rotation's), and uncomment a base map's own
    records once no variant replaces it. everything: also the record Play in game added for each (install_package's,
    or install_map_record's for a map's name) and their landing zones. Their files stay (reset takes everything out).
    Returns the variants something was taken out for."""
    import deploy_fixture as dep
    game = Path(game)
    ledger = read_ledger(game)
    variants = list(dict.fromkeys(variants))
    mine = [e['variant'] for e in ledger.get('rotation') or [] if e['variant'] in variants]
    played = [b for b in ledger.get('records') or [] if b['variant'] in variants] if everything else []
    zones = [b for key in ('landingZones', 'playZones') for b in ledger.get(key) or [] if b['variant'] in variants] if everything else []
    if not mine and not played and not zones: return []
    _check_ready(game)
    now, stamp = _now(now)
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    pristine = pristine_lines(game, maps)
    new_maps = list(maps)
    for variant in mine:
        left = _rotation_out(new_maps, ledger, variant)
        if left: raise InstallError(left[0])
    for block in played:
        if not _take_out(new_maps, block): raise InstallError(f'the record the editor wrote for {block["variant"]} has changed; take it out by hand')
    ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
    ledger['records'] = [b for b in ledger.get('records') or [] if b not in played]
    for block in played: (ledger.get('installed') or {}).pop(block['variant'], None)
    _write_rotation(game, ledger, maps, new_maps, [e for e in ledger.get('rotation') or [] if e['variant'] not in mine], pristine)
    if zones:
        for key in ('landingZones', 'playZones'): _zones_out(game, ledger, key, variants)     # one changed since is left
    done = list(dict.fromkeys(mine + [b['variant'] for b in played] + [b['variant'] for b in zones]))
    ledger.setdefault('history', []).append(dict(at=now.isoformat(timespec='seconds'), **{'undone' if everything else 'rotationOut': done}))
    write_ledger(game, ledger)
    return done


def set_records_use(game, originals, use, now=None):
    """Switch records of the install's own off (commented out: the game then never uses them) or back on, from the Game
    maps window. originals: the records' lines as the install has them (text). A record whose map a variant replaces
    stays commented out while it does, whatever is asked here. Returns dict(changed, replaced: the lines that stay off
    because a variant replaces their map)."""
    import deploy_fixture as dep
    game = Path(game)
    _check_ready(game)
    ledger = read_ledger(game)
    now, stamp = _now(now)
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    pristine = pristine_lines(game, maps)
    own = {l.decode('latin-1') for l in pristine if dep.is_record(l)}
    unknown = [o for o in originals if o not in own]
    if unknown: raise InstallError('DefaultMaps.ini has no such record any more; open the window again')
    manual = set(ledger.get('manualOff') or [])
    before = {c['original'] for c in ledger.get('linesOff') or []}
    manual = (manual - set(originals)) if use else (manual | set(originals))
    ledger['manualOff'] = sorted(manual)
    new_maps = list(maps)
    ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
    _write_rotation(game, ledger, maps, new_maps, ledger.get('rotation') or [], pristine)
    after = {c['original'] for c in ledger['linesOff']}
    ledger.setdefault('history', []).append(dict(at=now.isoformat(timespec='seconds'), records='on' if use else 'off', count=len(originals)))
    write_ledger(game, ledger)
    return dict(changed=len(before ^ after), replaced=[o for o in originals if use and o in after])


def restore_intro(game, now=None):
    """An earlier version's intro install taken out: the install's own first mission again. True when it changed."""
    import deploy_fixture as dep
    game = Path(game)
    ledger = read_ledger(game)
    if not ledger.get('slot'): return False
    _check_ready(game)
    now, stamp = _now(now)
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    new_maps = list(maps)
    changed = _restore_intro(ledger, new_maps)
    if changed:
        ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
        dep.check_change(maps, new_maps, replaced=[i for i, (a, b) in enumerate(zip(maps, new_maps)) if a != b])
        dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
        ledger.setdefault('history', []).append(dict(at=now.isoformat(timespec='seconds'), introBack=True))
    write_ledger(game, ledger)
    return changed


def write_play_file(game, text, played, now=None):
    """The console commands a play starts the game with, in XEW\\Binaries (PLAY_FILE), and what is played in the
    ledger."""
    game = Path(game)
    _check_ready(game)
    path = play_file(game)
    if not path.parent.is_dir(): raise InstallError(f'{game} has no XEW\\Binaries')
    path.write_text(text, encoding='ascii', newline='\n')
    ledger = read_ledger(game)
    now, _ = _now(now)
    ledger['lastPlay'] = dict(played, at=now.isoformat(timespec='seconds'))
    write_ledger(game, ledger)
    return path


def write_start_file(game, text):
    """A play with saving on: the commands the game starts with (START_FILE, beside PLAY_FILE), or none (text None:
    an earlier play's taken away)."""
    path = start_file(game)
    if text is None:
        if path.is_file(): path.unlink()
        return None
    if not path.parent.is_dir(): raise InstallError(f'{game} has no XEW\\Binaries')
    path.write_text(text, encoding='ascii', newline='\n')
    return path


def backup_config(game, paths, now=None):
    """Before a play: the game's own config files it will write again (module text), kept aside in the install's
    ledger folder. A file that isn't there is noted, so that the one the game then makes is taken away afterwards and
    the game makes it afresh. Refuses while files of an earlier play are still kept: restore_config first."""
    game = Path(game)
    ledger = read_ledger(game)
    if ledger.get('config'): raise InstallError('the config kept aside for the last play is not back yet')
    _, stamp = _now(now)
    folder = game / LEDGER_FOLDER / 'play'
    entries = []
    for k, path in enumerate(Path(p) for p in paths):
        entry = dict(path=str(path), existed=path.is_file(), backup=None, sha256=None)
        if entry['existed']:
            folder.mkdir(parents=True, exist_ok=True)
            kept = folder / f'{stamp}-{k}-{path.name}'
            shutil.copy2(path, kept)
            entry.update(backup=str(kept.relative_to(game)), sha256=sha256(kept))
        entries.append(entry)
    ledger['config'] = entries
    write_ledger(game, ledger)
    return entries


def restore_config(game):
    """After a play: each config file kept aside put back as it was, with its time (one that is unchanged is left),
    and one the game made meanwhile taken away. Returns the files put back or taken away; none when nothing is kept.
    Refuses while XCOM runs: the game writes its config as it closes."""
    game = Path(game)
    ledger = read_ledger(game)
    entries = ledger.get('config') or []
    if not entries: return []
    if game_running(): raise InstallError('XCOM is running')
    done = []
    for entry in entries:
        path = Path(entry['path'])
        if entry['existed']:
            kept = game / entry['backup']
            if kept.is_file():
                if not path.is_file() or sha256(path) != entry['sha256']:
                    shutil.copy2(kept, path)
                    done.append(str(path))
                kept.unlink()
        elif path.is_file():
            path.unlink()
            done.append(str(path))
    ledger['config'] = []
    write_ledger(game, ledger)
    return done


BROKEN_SAVES = 'broken saves'      # in LEDGER_FOLDER: a play's broken saves, out of the game's load list (F-89)


def keep_saves(game, folders, now=None):
    """Before a play: the game's save folders readied for it (playsaves.keep: a play's broken saves set aside in the
    install's `XCOM Map Workshop\\broken saves`, its whole ones out of the ordinary slots, the low slots copied aside in
    the install's ledger folder, the saves noted). Returns the entries. Refuses while an earlier play's are still
    noted: restore_saves first."""
    import playsaves
    game = Path(game)
    ledger = read_ledger(game)
    if ledger.get('saves'): raise InstallError('the saves noted for the last play are not sorted yet')
    _, stamp = _now(now)
    entries = [playsaves.keep(folder, game / LEDGER_FOLDER / 'play' / f'{stamp}-saves-{k}',
                              game / LEDGER_FOLDER / BROKEN_SAVES, f'{stamp}-{k}') for k, folder in enumerate(folders)]
    ledger['saves'] = entries
    write_ledger(game, ledger)
    return entries


def restore_saves(game, now=None):
    """After a play: its saves moved out of the ordinary slots and the saves they replaced put back (playsaves.restore);
    what was done is kept as lastSaves. Returns it; None when no saves are noted. Refuses while XCOM runs."""
    import playsaves
    game = Path(game)
    ledger = read_ledger(game)
    entries = ledger.get('saves') or []
    if not entries: return None
    if game_running(): raise InstallError('XCOM is running')
    # kept: what keep_saves did before the play (whole saves to the play range, broken ones set aside)
    done = dict(moved=[], setAside=[], restored=[], kept=[m for e in entries for m in e.get('moved') or []],
                keptAside=[m for e in entries for m in e.get('setAside') or []])
    for entry in entries:
        result = playsaves.restore(entry)
        done['moved'] += result['moved']
        done['setAside'] += result['setAside']
        done['restored'] += result['restored']
    for entry in entries:
        for copy in entry.get('copies', {}).values():
            folder = Path(copy['copy']).parent
            if folder.is_dir() and not any(folder.iterdir()): folder.rmdir()
    ledger['saves'] = []
    ledger['lastSaves'] = dict(done, at=_now(now)[0].isoformat(timespec='seconds'))
    write_ledger(game, ledger)
    return done


def reset(game, now=None):
    """Take everything of the editor's back out of the install: the records and landing-zone lines it added, the files
    it copied, the commands file, the config kept aside for a play, and an earlier version's intro install. Returns
    what it did."""
    import deploy_fixture as dep
    game = Path(game)
    _check_ready(game)
    ledger = read_ledger(game)
    now, stamp = _now(now)
    maps = dep.lines_of(config(game, 'DefaultMaps.ini').read_bytes())
    done = dict(records=0, rotation=0, recordsBack=0, landingZones=0, files=[], left=[], intro=False, playFile=False, config=[])
    records = ledger.get('records') or []
    if records or any(ledger.get(k) for k in ('landingZones', 'playZones', 'files', 'playFiles', 'slot', 'rotation', 'linesOff')):
        ledger['backups'] = ledger.get('backups', []) + [str(_backup(game, stamp).relative_to(game))]
    new_maps = list(maps)
    had_slot = bool(ledger.get('slot'))
    done['intro'] = _restore_intro(ledger, new_maps)
    if had_slot and not done['intro']: done['left'].append('the intro slot was changed by something else since; it is left as it is')
    for block in records:
        if not _take_out(new_maps, block):
            done['left'].append(f'the record for {block["variant"]} has changed; take it out by hand')
            continue
        done['records'] += 1
    # the rotation installs: the variants' records out, the base maps' own back in rotation
    left = _rotation_out(new_maps, ledger)
    done['left'] += left
    done['rotation'] = len(ledger.get('rotation') or []) - len(left)
    off = ledger.get('linesOff') or []
    missing = _base_back(new_maps, off)
    done['recordsBack'] = len(off) - missing
    if missing:
        done['left'].append(f'{missing} of the install\'s own records that the editor commented out have changed since; put them back by hand')
    if new_maps != maps: dep.write_checked(config(game, 'DefaultMaps.ini'), new_maps)
    for key in ('landingZones', 'playZones'):
        count, left = _zones_out(game, ledger, key)
        done['landingZones'] += count
        done['left'] += left
    for key in ('files', 'playFiles'):
        names, left = _files_out(game, ledger, key)
        done['files'] += names
        done['left'] += left
    done['files'].sort()
    if _commands_out(game): done['playFile'] = True
    ledger.update(slot=None, records=[], landingZones=[], files={}, playZones=[], playFiles={}, intro=None, installed={},
                  lastPlay=None, rotation=[], linesOff=[], manualOff=[], owners={})
    ledger.setdefault('history', []).append(dict(at=now.isoformat(timespec='seconds'), reset=True, records=done['records'],
                                                  files=len(done['files']), **({'introBack': True} if done['intro'] else {})))
    write_ledger(game, ledger)
    done['config'] = restore_config(game)
    done['saves'] = restore_saves(game)
    return done


def same_folder(a, b):
    return a is not None and b is not None and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
