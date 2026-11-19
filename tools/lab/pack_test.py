"""The map pack game test's hands: a pack put into a lab copy as a player would, taken out again with a check that
nothing else changed, a card that makes a new campaign's first mission play a pack map, and the game's log read.

  python tools/lab/pack_test.py put <pack folder or zip> --game <lab copy>
  python tools/lab/pack_test.py first-mission <map> --game <lab copy>        (--off takes the card away)
  python tools/lab/pack_test.py take --game <lab copy>
  python tools/lab/pack_test.py read <Launch.log> [--pack <pack.json or card .upk>] [--json]

Long War Rebalance 3.00.00 beta 15 and later read map packs from cards (tools/upk/pack_card.py): a folder with a card
and its maps, copied into XEW\\XComGame\\CookedPCConsole, is installed.

- put: copies the pack's folder (the one holding LWRMapPack_NNNN.upk; from a zip, the folder in it that does) into
  CookedPCConsole and does nothing else. Before the first put it notes what the copy's Config and CookedPCConsole
  hold (Config by SHA-256; CookedPCConsole by size and time, --hash for SHA-256 there too, which takes minutes) in
  <lab copy>\\XComLab-pack-test.json. A folder of the same name is replaced, as copying a newer version over does not:
  give --over to copy over what is there instead.
- first-mission: a new campaign's first mission asks for its map by one display name (installs.INTRO_SLOT). The
  test card, LWRMapPack_9999.upk in a folder of its own, holds one line: that display name and the install's own
  record for it, with the file, family and streamed maps of a pack line for <map> (looked up in the cards under
  CookedPCConsole). The highest card number wins a display name, so the first mission plays <map>. A lab tool only:
  left in, every new campaign on that copy starts there.
- take: deletes the folders put and the test card, then compares the copy with the note: nothing else may differ.
  Only lab copies (the marker XComLab-copy.txt) are written to.
- read: the log's map pack lines as a table: the cards found, lines skipped and why, lines in several packs, what
  `Mutate LWRMapTest Packs` listed, each mission start with its map line and streamed levels, pictures, landing
  lines. With --pack (a pack.json of schema 2, or the card itself) a verdict per map: found and used, or why not.
  Exit code 1 when a map of the pack was skipped or not used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'viewer'), str(HERE.parent / 'upk')]
import pack_card  # noqa: E402

MARKER = 'XComLab-copy.txt'
NOTE = 'XComLab-pack-test.json'
FIRST_FOLDER = 'XComLabFirstMission'
FIRST_NUMBER = 9999
INTRO_SLOTS = ('URB_CommercialAlley_EWI (Commercial Alley Redux) |0', 'URB_CommercialAlley_EWI (Commercial Alley Redux)')


class TestError(Exception):
    pass


def cooked(game): return Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole'
def config(game): return Path(game) / 'XEW' / 'XComGame' / 'Config'


def check_copy(game):
    game = Path(game)
    if not cooked(game).is_dir(): raise TestError(f'{game} is not a game folder (no XEW\\XComGame\\CookedPCConsole)')
    if not (game / MARKER).is_file(): raise TestError(f'{game} is not a lab copy (no {MARKER}): nothing is written there')
    return game


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): digest.update(block)
    return digest.hexdigest()


def survey(game, skip=(), hashed=False):
    """What the copy holds: {'config': {name: sha256}, 'cooked': {relative path: [size, time] or sha256}}, the
    folders named in `skip` (directly under CookedPCConsole) left out."""
    skip = {s.lower() for s in skip}
    held = {'config': {}, 'cooked': {}}
    for path in sorted(config(game).rglob('*')):
        if path.is_file(): held['config'][path.relative_to(config(game)).as_posix()] = _sha256(path)
    root = cooked(game)
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if relative.parts[0].lower() in skip or not path.is_file(): continue
        stat = path.stat()
        held['cooked'][relative.as_posix()] = _sha256(path) if hashed else [stat.st_size, stat.st_mtime_ns]
    return held


def differences(before, after):
    """What differs between two surveys, as lines."""
    out = []
    for part in ('config', 'cooked'):
        a, b = before[part], after[part]
        out += [f'{part}: {name} is gone' for name in a if name not in b]
        out += [f'{part}: {name} is new' for name in b if name not in a]
        out += [f'{part}: {name} changed' for name in a if name in b and a[name] != b[name]]
    return out


def read_note(game):
    try: return json.loads((Path(game) / NOTE).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def write_note(game, note):
    (Path(game) / NOTE).write_text(json.dumps(note, indent=1) + '\n', encoding='utf-8', newline='\n')


def pack_folder(source):
    """The folder of a pack that holds its card: `source` itself, or the one folder under it that does."""
    source = Path(source)
    if not source.is_dir(): raise TestError(f'{source} is not a folder')
    def has_card(folder): return any(pack_card.number_of(p.name) is not None for p in folder.iterdir() if p.is_file())
    if has_card(source): return source
    found = [p for p in sorted(source.iterdir()) if p.is_dir() and has_card(p)]
    if len(found) != 1:
        raise TestError(f'{source}: {len(found)} folders with a card (LWRMapPack_NNNN.upk) in it; one is wanted')
    return found[0]


def put(source, game, over=False, hashed=False, echo=print):
    """The pack's folder copied into the copy's CookedPCConsole. Returns the folder there."""
    game = check_copy(game)
    source = Path(source)
    with tempfile.TemporaryDirectory() as temp:
        if source.is_file():
            with zipfile.ZipFile(source) as z: z.extractall(temp)
            source = Path(temp)
        folder = pack_folder(source)
        note = read_note(game)
        if note is None:
            echo('noting what the copy holds ...')
            note = dict(schema='xcom-lab/pack-test', hashed=hashed, before=survey(game, hashed=hashed), folders=[])
            write_note(game, note)
        target = cooked(game) / folder.name
        if target.exists() and folder.name not in note['folders']:
            raise TestError(f'{target} is there already and this test did not put it')
        if target.exists() and not over: shutil.rmtree(target)
        shutil.copytree(folder, target, dirs_exist_ok=True)
        if folder.name not in note['folders']: note['folders'].append(folder.name)
        write_note(game, note)
        files = sorted(p.name for p in target.iterdir())
        echo(f'put {target}: {len(files)} file(s)')
        for name in files: echo(f'  {name}')
        return target


def installed_cards(game):
    """[(path, the card read)] of every card under the copy's CookedPCConsole, by number."""
    out = []
    for path in cooked(game).rglob('*.upk'):
        if pack_card.number_of(path.name) is None: continue
        try: out.append((path, pack_card.read(path.read_bytes())))
        except (OSError, pack_card.CardError): continue
    return sorted(out, key=lambda item: pack_card.number_of(item[0].name))


def intro_record(game):
    """The install's own record for the first mission's display name, as a card line."""
    for raw in (config(game) / 'DefaultMaps.ini').read_bytes().splitlines():
        try: record = pack_card.parse_record(raw)
        except pack_card.CardError: continue
        if record is not None and record.kind == 'Maps' and record.fields.get('DisplayName') in INTRO_SLOTS:
            return pack_card.map_line(record.fields)
    raise TestError('the copy\'s DefaultMaps.ini has no record with the first mission\'s display name')


def first_mission_line(game, map_name, cards=None):
    """The test card's one line: the first mission's record with the file, family and streams of a pack line for
    `map_name` (an abduction's line when the map has one)."""
    cards = installed_cards(game) if cards is None else cards
    lines = [m for _, held in cards for m in held['Maps'] if m['Name'].lower() == map_name.lower()]
    if not lines: raise TestError(f'no card under CookedPCConsole has a line for the map {map_name}')
    lines.sort(key=lambda m: m['MissionType'] != 'eMission_Abduction')
    line = dict(intro_record(game))
    line.update(Name=lines[0]['Name'], MapFamily=lines[0]['MapFamily'], StreamingMaps=lines[0]['StreamingMaps'])
    return line


def first_mission(game, map_name=None, off=False, echo=print):
    game = check_copy(game)
    folder = cooked(game) / FIRST_FOLDER
    if off:
        if folder.exists(): shutil.rmtree(folder)
        echo(f'the first mission card is out of {game}')
        return None
    line = first_mission_line(game, map_name)
    if read_note(game) is None:
        echo('noting what the copy holds ...')
        write_note(game, dict(schema='xcom-lab/pack-test', hashed=False, before=survey(game), folders=[]))
    folder.mkdir(exist_ok=True)
    target = folder / pack_card.file_name(FIRST_NUMBER)
    target.write_bytes(pack_card.card('First mission test', [line]))
    echo(f'{target}: a new campaign\'s first mission plays {line["Name"]}')
    echo(f'  as {line["DisplayName"]!r}, streams {[s["MapName"] for s in line["StreamingMaps"] if s["MapName"]]}')
    return target


def take(game, echo=print):
    """The folders put and the test card deleted; True when the copy is then as the note says it was."""
    game = check_copy(game)
    note = read_note(game)
    if note is None: raise TestError(f'{game} has no note of a pack test ({NOTE})')
    for name in note['folders'] + [FIRST_FOLDER]:
        target = cooked(game) / name
        if target.exists():
            shutil.rmtree(target)
            echo(f'deleted {target}')
    different = differences(note['before'], survey(game, hashed=note.get('hashed', False)))
    if different:
        echo(f'the copy differs from before the test in {len(different)} place(s):')
        for line in different[:60]: echo(f'  {line}')
        echo(f'the note stays ({game / NOTE})')
        return False
    (game / NOTE).unlink()
    echo('the copy is as it was before the test')
    return True


# ---------------------------------------------------------------------------------------------------------------------
# The log
# ---------------------------------------------------------------------------------------------------------------------
_SCAN = re.compile(r'(?P<when>.*): looked for map pack cards LWRMapPack_0000 to (?P<last>\d+) in (?P<ms>-?\d+) ms: (?P<found>\d+) found; '
                   r'DefaultLWRMapPacks\.ini has (?P<ini>\d+) map line')
_CARD = re.compile(r'card (?P<number>\d{4}) \'(?P<name>.*)\' \(format (?P<format>\d+)\): (?P<maps>\d+) map line\(s\), '
                   r'(?P<pictures>\d+) picture line\(s\), (?P<zones>\d+) LZ line\(s\)')
_CARD_SKIPPED = re.compile(r'card (?P<number>\d{4}) \'(?P<name>.*)\': SKIPPED, card format (?P<format>\d+)')
_SKIPPED = re.compile(r'skipped \'(?P<display>.*)\' \((?P<source>.*)\): map file \'(?P<file>[^\']*)\' is not installed')
_SEVERAL = re.compile(r'\'(?P<display>.*)\' is in several packs: (?P<source>.*) \(file \'(?P<file>[^\']*)\'\) is used, over (?P<lost>.*)')
_LOOKED = re.compile(r'looked for (?P<looked>\d+) map file\(s\), (?P<missing>\d+) missing')
_MERGED = re.compile(r'(?P<when>.*): merged - (?P<count>.*)')
_FINDS = re.compile(r'\s*\'(?P<display>.*)\': the game finds it \(file \'(?P<file>[^\']*)\', type (?P<type>\d+), in rotation (?P<rotation>\w+)\)')
_NOT_FOUND = re.compile(r'\s*\'(?P<display>.*)\': the game does NOT find it')
_LISTED = re.compile(r'\s*\'(?P<display>.*)\', file \'(?P<file>[^\']*)\', from (?P<source>.*?): (?P<state>used|NOT used.*)')
_START = re.compile(r'mission start \(from a save (?P<save>\w+)\): map file \'(?P<mapFile>[^\']*)\'; the game\'s map line '
                    r'\'(?P<display>.*)\' \(file \'(?P<file>[^\']*)\', type (?P<type>\d+)\); streamed levels:(?P<levels>.*)')
_NO_PICTURE = re.compile(r'no picture for pack map (?P<map>\S+)')
_ZONES = re.compile(r'XComLZMutator: (?P<count>\d+) LZ line\(s\) from map packs added')
_ZONE_VALUE = re.compile(r'XComLZMutator: map pack LZ value \'(?P<value>.*)\' not known')


def read_log(text):
    """The log's map pack lines, sorted by kind (see the module notes)."""
    out = dict(scans=[], cards=[], cardsSkipped=[], skipped=[], several=[], looked=[], merged=[], finds=[], notFound=[],
               listed=[], starts=[], peeks=[], noPicture=[], frames=[], zonesAdded=[], zoneValues=[], other=[])
    for raw in text.splitlines():
        frame = raw.find('MAPFRAME')
        if frame >= 0 and 'LWRMAPPACK' not in raw:
            out['frames'].append(raw[frame:].strip())
            continue
        for pattern, key in ((_ZONES, 'zonesAdded'), (_ZONE_VALUE, 'zoneValues')):
            m = pattern.search(raw)
            if m: out[key].append(int(m['count']) if key == 'zonesAdded' else m['value'])
        at = raw.find('LWRMAPPACK:')
        if at < 0: continue
        line = raw[at + len('LWRMAPPACK:'):].rstrip()
        body = line.strip()
        for pattern, key in ((_SCAN, 'scans'), (_CARD_SKIPPED, 'cardsSkipped'), (_CARD, 'cards'), (_SKIPPED, 'skipped'),
                             (_SEVERAL, 'several'), (_LOOKED, 'looked'), (_START, 'starts'), (_FINDS, 'finds'),
                             (_NOT_FOUND, 'notFound'), (_LISTED, 'listed'), (_NO_PICTURE, 'noPicture'), (_MERGED, 'merged')):
            m = pattern.search(body) if key not in ('finds', 'notFound', 'listed') else pattern.match(body)
            if not m: continue
            found = m.groupdict()
            for number in ('ms', 'found', 'ini', 'last', 'format', 'maps', 'pictures', 'zones', 'looked', 'missing', 'type'):
                if number in found: found[number] = int(found[number])
            if key == 'cards' or key == 'cardsSkipped': found['number'] = int(found['number'])
            if key == 'starts':
                found['save'] = found['save'].lower() == 'true'
                found['levels'] = [level.strip() for level in re.split(r'[,;]|\s{2,}', found['levels']) if level.strip()]
            if key == 'noPicture': found = found['map']
            if found not in out[key] or key in ('scans', 'starts'): out[key].append(found)
            break
        else:
            if body.startswith('Peek '): out['peeks'].append(body)
            else: out['other'].append(body)
    return out


def pack_lines(source):
    """[(DisplayName, Name)] of a pack's map lines, from its pack.json (schema 2: card.lines) or its card."""
    source = Path(source)
    if source.suffix.lower() == '.upk':
        return [(m['DisplayName'], m['Name']) for m in pack_card.read(source.read_bytes())['Maps']]
    described = json.loads(source.read_text(encoding='utf-8'))
    lines = (described.get('card') or {}).get('lines')
    if lines is None: raise TestError(f'{source} has no card lines (a pack from before cards)')
    records = [pack_card.parse_record(line) for line in lines]
    return [(r.fields.get('DisplayName', ''), r.fields.get('Name', '')) for r in records if r is not None and r.kind == 'Maps']


def verdicts(log, lines):
    """One verdict per pack line: (DisplayName, file, ok, what the log says)."""
    skipped = {(s['display'].lower(), s['file'].lower()) for s in log['skipped']}
    lost = {}
    for s in log['several']: lost.setdefault(s['display'].lower(), s)
    listed = {(l['display'].lower(), l['file'].lower()): l['state'] for l in log['listed']}
    started = {}
    for s in log['starts']: started.setdefault(s['mapFile'].lower(), []).append(s)
    out = []
    for display, name in lines:
        key = (display.lower(), name.lower())
        said, ok = [], True
        if not log['scans']: said, ok = ['the log has no card scan'], False
        elif key in skipped: said, ok = ['skipped: its map file is not installed'], False
        elif key in listed:
            said.append(listed[key])
            ok = listed[key] == 'used'
        elif display.lower() in lost and lost[display.lower()]['file'].lower() != name.lower():
            said, ok = [f'another pack\'s line is used: {lost[display.lower()]["source"]}'], False
        else: said.append('not skipped')
        for s in started.get(name.lower(), []):
            same = s['display'].lower() == display.lower() and s['file'].lower() == name.lower()
            if same: said.append('a mission started on it under this line' + (' (from a save)' if s['save'] else ''))
        out.append((display, name, ok, '; '.join(said)))
    return out


def report(log, lines=None, echo=print):
    """The log's lines as a table; True when no map of the pack (`lines`) was skipped or left unused."""
    for s in log['scans']:
        echo(f'scan ({s["when"]}): {s["found"]} card(s) in {s["ms"]} ms; DefaultLWRMapPacks.ini has {s["ini"]} map line(s)')
    if not log['scans']: echo('no card scan in this log')
    for c in log['cards']:
        echo(f'card {c["number"]:04d} {c["name"]!r}: {c["maps"]} map, {c["pictures"]} picture, {c["zones"]} landing line(s)')
    for c in log['cardsSkipped']: echo(f'card {c["number"]:04d} {c["name"]!r}: SKIPPED, its format {c["format"]} is newer')
    for l in log['looked']: echo(f'map files looked for: {l["looked"]}, missing: {l["missing"]}')
    for m in log['merged']: echo(f'merged ({m["when"]}): {m["count"]}')
    for s in log['skipped']: echo(f'skipped: {s["display"]!r} ({s["source"]}): file {s["file"]} not installed')
    for s in log['several']: echo(f'in several packs: {s["display"]!r}: {s["source"]} (file {s["file"]}) used, over {s["lost"]}')
    for l in log['listed']: echo(f'listed: {l["display"]!r}, file {l["file"]}, from {l["source"]}: {l["state"]}')
    for f in log['finds']: echo(f'found by the game: {f["display"]!r} (file {f["file"]}, type {f["type"]}, in rotation {f["rotation"]})')
    for f in log['notFound']: echo(f'NOT found by the game: {f["display"]!r}')
    for s in log['starts']:
        echo(f'mission start{" (from a save)" if s["save"] else ""}: map file {s["mapFile"]}; map line {s["display"]!r} '
             f'(file {s["file"]}, type {s["type"]}); streamed: {", ".join(s["levels"]) or "none"}')
    for n in log['zonesAdded']: echo(f'landing lines from packs added: {n}')
    for v in log['zoneValues']: echo(f'landing value not known: {v}')
    for p in log['peeks']: echo(f'peek: {p}')
    for m in log['noPicture']: echo(f'no picture for pack map {m}')
    for f in log['frames']: echo(f'frame: {f}')
    for o in log['other']: echo(f'other: {o}')
    if lines is None: return True
    echo('')
    good = True
    for display, name, ok, said in verdicts(log, lines):
        good = good and ok
        echo(f'{"ok " if ok else "NOT"} {name}: {display!r}: {said}')
    return good


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='verb', required=True)
    p = sub.add_parser('put')
    p.add_argument('source', type=Path)
    p.add_argument('--over', action='store_true', help='copy over a folder of the same name, as a player copying a newer version does')
    p.add_argument('--hash', action='store_true', help='note CookedPCConsole by SHA-256 (minutes)')
    f = sub.add_parser('first-mission')
    f.add_argument('map', nargs='?')
    f.add_argument('--off', action='store_true')
    t = sub.add_parser('take')
    for s in (p, f, t): s.add_argument('--game', type=Path, required=True, help='the lab copy')
    r = sub.add_parser('read')
    r.add_argument('log', type=Path)
    r.add_argument('--pack', type=Path, help='the pack\'s pack.json or its card')
    r.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        if args.verb == 'put': put(args.source, args.game, over=args.over, hashed=args.hash)
        elif args.verb == 'first-mission':
            if not args.off and not args.map: ap.error('first-mission wants a map, or --off')
            first_mission(args.game, args.map, off=args.off)
        elif args.verb == 'take': return 0 if take(args.game) else 1
        else:
            log = read_log(args.log.read_text(encoding='utf-16' if args.log.read_bytes()[:2] in (b'\xff\xfe', b'\xfe\xff') else 'latin-1'))
            if args.json:
                print(json.dumps(log, indent=1))
                return 0
            return 0 if report(log, pack_lines(args.pack) if args.pack else None) else 1
    except (TestError, pack_card.CardError, OSError) as error:
        print(f'pack_test: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
