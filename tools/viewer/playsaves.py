"""The game's save files around a play (F-89): a play's saves kept apart from a campaign's.

A battle started from the console (Play in game, a prefab test) never logs in, so the game doesn't read its save
list and writes a save to `save1` whatever is there, over a campaign's save 1 (EXP-53's EXALT runs did, 15 November
2026). Such a save is easy to tell apart: its header's game number is 0 and its map command has `LoadingFromShell=1`
(a campaign's saves have the campaign's number and `LoadingFromStrategy=1`, or a strategy map).

Such a save is broken, too (F-89, EXP-56): the write never finishes, the game writes the 1 KB header again every
frame and the checkpoint data only when it closes, so the file is hundreds of headers and then the data. A whole save
has its compressed data (UE3's package tag, 0x9E2A83C1) right after the first header, at byte 1024. Loading a broken
one crashes the game (a divide by zero in the chunk reader, which reads a chunk size of 0 from the second header).

A play with saving on (play.py) opens its battle after the main menu's login, and its saves are whole: the game names
a new save the highest number in its list plus one (EXP-56 run 1: save21 with save20 the highest and save1 free), so
such a save never takes a campaign's slot, and it stays where the game wrote it, in the load list with the rest.

So, around each play (installs.keep_saves, installs.restore_saves):
- before it, a play's broken saves anywhere in a save folder are set aside (moved out of the folder, to the
  install's `XCOM Map Workshop\\broken saves`, where the game doesn't list them), the low slots a play without the
  login writes (save1 to save9) are copied aside, and the folder's saves are noted;
- once the game has closed, each play's save the play wrote or changed is set aside if broken, and the save it
  replaced, if any, is put back from its copy. A whole one stays, unless it took a copied save's slot (overwritten
  from the save menu): then it moves to the next slot and the copy goes back. A campaign's saves, and anything that
  isn't a save, are left as they are.
(The first version, 15 November, moved play saves to save999 down: the game numbers the next save after the highest,
so a campaign saved after that would have gone on at save1000. A save999 it made is left where it is.)

The save folders are the user's (Documents\\My Games\\XCOM - Enemy Within\\XComGame\\SaveData) and the install's own
(XEW\\XComGame\\SaveData, where a game started with -nohomedir or a lab copy keeps them): each one that is there."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct

SAVE = re.compile(r'save(\d+)', re.I)
LOW = range(1, 10)                      # the slots a play writes without asking: copied aside before it
HEADER = 1024                           # a save's header block; its compressed data follows
PACKAGE_TAG = struct.pack('<I', 0x9E2A83C1)


def folders(game, documents):
    """The save folders a play may write to, those that are there."""
    found = [Path(documents) / 'My Games' / 'XCOM - Enemy Within' / 'XComGame' / 'SaveData',
             Path(game) / 'XEW' / 'XComGame' / 'SaveData']
    return [f for f in found if f.is_dir()]


def _fstring(b, o):
    """An FString at offset o: (text, next offset), or None."""
    if o + 4 > len(b): return None
    n = struct.unpack_from('<i', b, o)[0]
    o += 4
    if n == 0: return '', o
    if n > 0:
        if n > 4096 or o + n > len(b): return None
        return b[o:o + n].rstrip(b'\0').decode('latin-1'), o + n
    n = -n
    if n > 4096 or o + 2 * n > len(b): return None
    return b[o:o + 2 * n].decode('utf-16-le', 'replace').rstrip('\0'), o + 2 * n


def header(path):
    """A save file's header: dict(version, game, description, time, command), or None when it isn't one."""
    try:
        with open(path, 'rb') as f: b = f.read(4096)
    except OSError:
        return None
    if len(b) < 20: return None
    version, _, game, _ = struct.unpack_from('<4i', b, 0)
    if not 0 < version < 0x100: return None
    out, o = dict(version=version, game=game), 16
    for key in ('description', 'time', 'command'):
        got = _fstring(b, o)
        if got is None: return None
        out[key], o = got
    return out if out['command'].lower().startswith(('open ', 'servertravel ')) else None


def is_play_save(head):
    """A save of a battle started without a campaign (a play's): game 0, the map opened from the shell."""
    return bool(head) and head['game'] == 0 and 'loadingfromshell=1' in head['command'].lower()


def is_whole(path):
    """Whether a save's compressed data follows its header (a broken save has more headers there)."""
    try:
        with open(path, 'rb') as f:
            f.seek(HEADER)
            return f.read(4) == PACKAGE_TAG
    except OSError:
        return False


def saves(folder):
    """{number: path} of the folder's save<N> files."""
    out = {}
    for p in Path(folder).iterdir():
        m = SAVE.fullmatch(p.name)
        if m and p.is_file(): out[int(m.group(1))] = p
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def _stamp(path):
    s = path.stat()
    return [s.st_size, s.st_mtime_ns]


def _move_to_next_slot(folder, path, taken, moved):
    """A whole play save that took a campaign save's slot moved to the slot the game would give a new save (the
    highest number plus one, EXP-56). `taken` holds every slot in use or to be filled again (the play save's own
    included, and the slots whose copies go back), so the slot is a fresh one: never the play save's own, never a
    copied slot, never a file that is there."""
    n = max(taken | {0}) + 1
    while (Path(folder) / f'save{n}').exists(): n += 1
    target = Path(folder) / f'save{n}'
    path.replace(target)
    taken.add(n)
    moved.append(dict(folder=str(folder), name=path.name, to=target.name))
    return target


def _put_back(copy, path):
    """A copied save put back in its slot through a temporary file (not a save<N> name, so the game never lists it),
    its bytes checked against the copy's recorded hash before and after. Returns None, or why it was not put back."""
    kept = Path(copy['copy'])
    temp = path.with_name(f'.{path.name}.restore.tmp')
    try:
        shutil.copy2(kept, temp)
        if _sha256(temp) != copy['sha256']: return f'its copy ({kept}) is not the save that was copied; it is kept'
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    if _sha256(path) != copy['sha256']: return f'it did not read back as its copy ({kept}); the copy is kept'
    return None


def _set_aside(folder, path, aside, prefix, out):
    """A broken play save moved out of the save folder into `aside`, as <prefix>-<name>."""
    aside = Path(aside)
    aside.mkdir(parents=True, exist_ok=True)
    target, k = aside / f'{prefix}-{path.name}', 1
    while target.exists():
        k += 1
        target = aside / f'{prefix}-{path.name}-{k}'
    shutil.move(str(path), str(target))
    out.append(dict(folder=str(folder), name=path.name, to=str(target)))


def keep(folder, backup, aside, prefix):
    """Before a play, one save folder: a play's broken saves set aside in `aside` (named <prefix>-saveN), the low slots
    copied to `backup`, the saves noted. Returns the ledger entry: dict(folder, files: {name: [size, mtime_ns]},
    copies: {name: dict(copy, sha256)}, moved: [] (kept for ledgers of the first version), setAside: [...], aside,
    prefix)."""
    folder, backup = Path(folder), Path(backup)
    found, set_aside = saves(folder), []
    for n, path in sorted(found.items()):
        if is_play_save(header(path)) and not is_whole(path):
            _set_aside(folder, path, aside, prefix, set_aside)
    copies = {}
    for n, path in sorted(saves(folder).items()):
        if n in LOW:
            backup.mkdir(parents=True, exist_ok=True)
            kept = backup / path.name
            shutil.copy2(path, kept)
            copies[path.name] = dict(copy=str(kept), sha256=_sha256(kept))
    files = {p.name: _stamp(p) for p in saves(folder).values()}
    return dict(folder=str(folder), files=files, copies=copies, moved=[], setAside=set_aside, aside=str(aside),
                prefix=prefix)


def restore(entry):
    """After a play, one save folder (keep's entry): each play's save the play wrote or changed set aside if broken,
    and left where it is if whole, unless it took the slot of a save copied before the play: then it moves to the
    next slot. Then the copies, each by its own: a copied save whose slot is empty is put back from its copy (through
    a temporary file, checked against its hash); a copy is taken away only once its slot holds its bytes (or holds a
    campaign's own newer save). So a restore that stopped part-way (a failed copy, a stopped server) is run again
    from the copies as well as from the slots, and loses neither save. Returns dict(moved, setAside, restored, left)."""
    folder = Path(entry['folder'])
    moved, set_aside, restored, left = [], [], [], []
    copies = entry.get('copies') or {}
    if folder.is_dir():
        found = saves(folder)
        # every slot in use, and the copied ones (put back below): a play save moves past all of them
        taken = set(found) | {int(m.group(1)) for m in map(SAVE.fullmatch, copies) if m}
        for n, path in sorted(found.items()):
            if entry['files'].get(path.name) == _stamp(path): continue
            if not is_play_save(header(path)): continue
            copy = copies.get(path.name)
            whole = is_whole(path) or not entry.get('aside')   # (an entry from before broken saves were told)
            if whole and not copy: continue                     # a new slot, as the game gives once logged in
            if whole: _move_to_next_slot(folder, path, taken, moved)
            else: _set_aside(folder, path, entry['aside'], entry['prefix'], set_aside)
    for name, copy in copies.items():
        path, kept = folder / name, Path(copy['copy'])
        if path.is_file() and _sha256(path) == copy['sha256']:
            pass                                                # in its slot: untouched, or put back already
        elif path.is_file():
            if is_play_save(header(path)) and kept.is_file():   # a play save the loop above could not move
                left.append(dict(folder=str(folder), name=name, why=f'a play\'s save is in its slot; its copy {kept} is kept'))
                continue
            # a campaign's own save written there since (the copy is the older one): the slot is left as it is
        elif kept.is_file():
            why = _put_back(copy, path) if folder.is_dir() else f'its folder is gone; its copy {kept} is kept'
            if why:
                left.append(dict(folder=str(folder), name=name, why=why))
                continue
            restored.append(dict(folder=str(folder), name=name))
        try: kept.unlink()
        except FileNotFoundError: pass
    return dict(moved=moved, setAside=set_aside, restored=restored, left=left)
