"""Saved map packs: what the project manager remembers of each pack it exported, so that the pack can be exported
again with the same maps, folder and card number (LWR map packs plan, section 7).

A record is <projects>\\packs\\<Folder>.json, written at every export:

  {schema: "xcom-map-workshop/pack", schemaVersion: 1, name, folder, card, version, author, projectFiles,
   maps: [{project (id), name, variant, mode}], exportedAt, zip (the file's name in <builds>\\Map packs)}

- folder: the pack's name made one word (letters, digits and _, 24 characters at most), fixed at the first export. It
  is the folder a player copies into CookedPCConsole, the record's file name and the pack's id in a game's ledger.
- card: the number of the pack's card, LWRMapPack_<nnnn>.upk, drawn at random at the first export from the numbers no
  other record and no card in the install the editor reads has, and kept from then on (a player with two packs of one
  number renames one card).
- version: 1 at the first export, raised by one at each.

The same record is the `pack` part of pack.json in the pack's zip, so a pack whose record is gone (another computer,
a cleared folder) is offered from its zip in <builds>\\Map packs (`listing`: source "zip"); choosing it makes the
record. A zip from before cards (pack.json schema 1) gives its name and maps and gets a number when exported.
"""
import copy
import json
from pathlib import Path
import random
import re
import threading
import zipfile

SCHEMA = 'xcom-map-workshop/pack'
FOLDER = 'packs'
FOLDER_LIMIT = 24
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,%d}' % (FOLDER_LIMIT - 1))
CARD = re.compile(r'LWRMapPack_(\d{4})\.upk', re.I)
# what the game strips from a map's name before it looks for the map's own picture (LWR's PackMapPicture)
PICTURE_ENDINGS = ('_Bomb', '_Rescue', '_Extraction', '_Assault')


class PackError(Exception):
    pass


def folder_name(name):
    """A pack's name as one word: 'Night maps, vol. 2' -> 'Night_maps_vol_2'."""
    word = re.sub(r'[^A-Za-z0-9]+', '_', name or '').strip('_')
    if not word or not word[0].isalpha(): word = f'Pack_{word}'.rstrip('_')
    return word[:FOLDER_LIMIT].rstrip('_')


def root(projects_root):
    return Path(projects_root) / FOLDER


def valid(record):
    return (isinstance(record, dict) and record.get('schema') == SCHEMA and isinstance(record.get('folder'), str)
            and bool(NAME.fullmatch(record['folder'])) and isinstance(record.get('name'), str)
            and isinstance(record.get('maps'), list)
            and (record.get('card') is None or (isinstance(record['card'], int) and 0 <= record['card'] <= 9999)))


def load(projects_root, folder):
    """The record of the pack whose folder is `folder`, or None."""
    if not isinstance(folder, str) or not NAME.fullmatch(folder): return None
    try: record = json.loads((root(projects_root) / f'{folder}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    return record if valid(record) and record['folder'].lower() == folder.lower() else None


def records(projects_root):
    out = []
    folder = root(projects_root)
    if folder.is_dir():
        for path in sorted(folder.glob('*.json')):
            record = load(projects_root, path.stem)
            if record: out.append(record)
    return out


def save(projects_root, record):
    if not valid(record): raise PackError('not a pack record')
    folder = root(projects_root)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{record["folder"]}.json'
    temp = target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    temp.replace(target)
    return record


def forget(projects_root, folder):
    """The record removed (no zip is deleted); True when there was one."""
    if load(projects_root, folder) is None: return False
    (root(projects_root) / f'{folder}.json').unlink()
    return True


def installed_cards(cooked):
    """{number: where} of every card under an install's CookedPCConsole (sub-folders too)."""
    out = {}
    if cooked is None or not Path(cooked).is_dir(): return out
    for path in Path(cooked).rglob('LWRMapPack_*.upk'):
        m = CARD.fullmatch(path.name)
        if m: out.setdefault(int(m.group(1)), path)
    return out


def draw_number(taken, rng=random):
    """A card number from 0000 to 9999 that is not in `taken`."""
    free = [n for n in range(10000) if n not in taken]
    if not free: raise PackError('every card number from 0000 to 9999 is in use')
    return rng.choice(free)


_ZIPS = {}          # a zip as it is (path, size, time) -> its record or None: every packs.json read opened every zip
_ZIPS_LOCK = threading.Lock()


def from_zip(path):
    """The record a pack's zip holds (pack.json's `pack`), or one made from a zip of before cards (its name and maps,
    no card number, version 0), or None when the zip is no pack. Read once for the file as it is (its size and time;
    review finding 50)."""
    try:
        stat = Path(path).stat()
        key = (str(Path(path).resolve()), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None
    with _ZIPS_LOCK:
        if key in _ZIPS:
            found = _ZIPS[key]
            return copy.deepcopy(found) if found is not None else None
    found = _read_zip(path)
    with _ZIPS_LOCK:
        _ZIPS[key] = found
        while len(_ZIPS) > 256:
            _ZIPS.pop(next(iter(_ZIPS)))
    return copy.deepcopy(found) if found is not None else None


def _read_zip(path):
    try:
        with zipfile.ZipFile(path) as z: described = json.loads(z.read('pack.json'))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile): return None
    if not isinstance(described, dict) or not isinstance(described.get('maps'), list): return None
    held = described.get('pack')
    if valid(held): return dict(held, zip=Path(path).name)
    name = described.get('name') if isinstance(described.get('name'), str) else Path(path).stem
    maps = [dict(project=m.get('id'), name=m.get('name'), variant=m.get('variant'),
                 mode=m.get('mode') or (described.get('mode') if described.get('mode') in ('additional', 'replace') else 'additional'))
            for m in described['maps'] if isinstance(m, dict)]
    record = dict(schema=SCHEMA, schemaVersion=1, name=name, folder=folder_name(name), card=None, version=0, author='',
                  projectFiles=bool(described.get('projects')), maps=maps, exportedAt=described.get('madeAt'),
                  zip=Path(path).name)
    return record if valid(record) else None


def listing(projects_root, zips):
    """Every saved pack and, after them, every pack found only as a zip in `zips` (the newest zip of each folder):
    the records, each with source 'record' or 'zip'."""
    out = [dict(r, source='record') for r in records(projects_root)]
    known = {r['folder'].lower() for r in out}
    found = {}
    if zips is not None and Path(zips).is_dir():
        for path in sorted(Path(zips).glob('*.zip'), key=lambda p: p.stat().st_mtime):
            record = from_zip(path)
            if record and record['folder'].lower() not in known: found[record['folder'].lower()] = dict(record, source='zip')
    return out + sorted(found.values(), key=lambda r: r['name'].lower())


def resolve(projects_root, zips, folder):
    """The record to export a named pack from: the saved one, else the one its zip holds. None when neither."""
    record = load(projects_root, folder)
    if record: return record
    for found in listing(projects_root, zips):
        if found['folder'].lower() == str(folder).lower():
            return {k: v for k, v in found.items() if k != 'source'}
    return None


def new_folder(projects_root, zips, name):
    """A folder name for a new pack called `name`, one no saved or zipped pack has (…_2, _3 after the plain one)."""
    taken = {r['folder'].lower() for r in listing(projects_root, zips)}
    stem = folder_name(name)
    for n in range(1, 1000):
        ending = '' if n == 1 else f'_{n}'
        candidate = stem[:FOLDER_LIMIT - len(ending)].rstrip('_') + ending
        if candidate.lower() not in taken: return candidate
    raise PackError(f'no free folder name for {name}')


def package_guid(path):
    """A package file's GUID (16 bytes), or None when the file can't be read as a package."""
    import struct
    try:
        with open(path, 'rb') as f: head = f.read(4096)
        if struct.unpack_from('<I', head, 0)[0] != 0x9E2A83C1: return None
        count = struct.unpack_from('<i', head, 12)[0]
        at = 16 + (count if count >= 0 else -count * 2)      # after the folder name
        at += 4 + 7 * 4 + 4 * 4                               # package flags, the tables, the GUID tables and thumbnails
        guid = head[at:at + 16]
        return guid if len(guid) == 16 else None
    except (OSError, struct.error): return None


def picture_ending(variant):
    """The ending the game strips from this map's name before looking for its own picture, or None."""
    lower = variant.lower()
    return next((e for e in PICTURE_ENDINGS if e.lower() in lower), None)
