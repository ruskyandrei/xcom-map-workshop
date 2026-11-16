"""The enums of a script package (XComGame.upk): each entry's position, its full name, and whether that name is unique.

A cooked enum export is the object's net index, its tagged properties (none, in the packages read so far: one None),
UField's Next, then UEnum's names: a count and that many FNames. An FName is a name-table index and an unsigned
number; the number makes `base_<number - 1>` (0: the base alone), so two entries can share a base and differ by number. Mods that
padded an enum by hex edits leave entries whose full names repeat (LWR's ESoldierClass holds eSC_Psi_12 twice, at 19
and 20) or carry huge numbers (ECharacter's eChar_MAX_16777215): an entry is known by its position, and a name names
an entry only when no other entry has it (`index` refuses an ambiguous one).

`read` takes a package image (or path) and gives every enum in it; `cached` keeps the result as JSON in a folder,
keyed by the package's SHA-256 and READER_VERSION (raised whenever what is read changes), written beside its final
name and moved into place.

  python tools/upk/script_enums.py <XComGame.upk> [EnumName ...]     the enums' entries, by position
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo  # noqa: E402

READER_VERSION = 1


class EnumError(ValueError):
    pass


def full_name(names, index, number):
    if not 0 <= index < len(names): raise EnumError(f'name index {index} is outside the name table ({len(names)})')
    return names[index] if number == 0 else f'{names[index]}_{number - 1}'


def _skip_properties(raw, at, names, end):
    """The offset after the tagged properties starting at `at` (up to and including None)."""
    while True:
        if at + 8 > end: raise EnumError('the properties run past the export')
        name = full_name(names, *struct.unpack_from('<iI', raw, at))
        at += 8
        if name == 'None': return at
        if at + 16 > end: raise EnumError(f'property {name} runs past the export')
        kind = full_name(names, *struct.unpack_from('<iI', raw, at))
        size, _ = struct.unpack_from('<ii', raw, at + 8)
        at += 16
        if kind == 'StructProperty' or kind == 'ByteProperty': at += 8     # the struct's or the enum's name
        elif kind == 'BoolProperty': at += 1
        if size < 0 or at + size > end: raise EnumError(f'property {name} has a bad size {size}')
        at += size


def entries(raw, names):
    """The full names of an enum export's entries, in order. An EnumError says why the export is not one."""
    end = len(raw)
    if end < 4 + 8 + 4 + 4: raise EnumError(f'{end} bytes is too short for an enum')
    at = _skip_properties(raw, 4, names, end) + 4          # the net index, the properties, then UField's Next
    if at + 4 > end: raise EnumError('no name count')
    count, = struct.unpack_from('<i', raw, at)
    at += 4
    if count < 0 or at + 8 * count != end:
        raise EnumError(f'{count} names do not fill the export ({end - at} bytes after the count)')
    return [full_name(names, *struct.unpack_from('<iI', raw, at + 8 * k)) for k in range(count)]


def _image(source):
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        return data, upkinfo.summary(data)
    return upkinfo.load(str(source))


def read(source):
    """{enum name: {'path': Outer.Name, 'entries': [full names], 'ambiguous': [names held by two or more entries]}}
    for every enum of a package (an image or a path). An enum name two exports share is kept under its path alone,
    and listed under '' as {name: [paths]}."""
    data, header = _image(source)
    names, imports, exports = upkinfo.tables(data, header)
    found, paths = {}, {}
    for export in exports:
        if upkinfo.clsname(export['cls'], imports, exports) != 'Enum': continue
        path = _path(export, imports, exports)
        raw = data[export['off']:export['off'] + export['size']]
        try: listed = entries(raw, names)
        except EnumError as error: raise EnumError(f'{path}: {error}') from None
        seen, twice = set(), []
        for name in listed:
            if name in seen and name not in twice: twice.append(name)
            seen.add(name)
        found[path] = dict(path=path, entries=listed, ambiguous=twice)
        paths.setdefault(export['name'], []).append(path)
    result = {}
    shared = {}
    for name, held in paths.items():
        if len(held) == 1: result[name] = found[held[0]]
        else: shared[name] = held
        for path in held:
            if len(held) > 1: result[path] = found[path]
    if shared: result[''] = shared
    return result


def _path(export, imports, exports):
    outer = export['outer']
    return (upkinfo.objname(outer, imports, exports) + '.' if outer else '') + export['name']


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): digest.update(block)
    return digest.hexdigest()


def cached(path, folder):
    """read(path), kept in `folder` (None: not kept) as enums-<sha256>.json for this READER_VERSION."""
    key = sha256(path)
    target = Path(folder) / f'enums-{key[:24]}-r{READER_VERSION}.json' if folder else None
    if target is not None and target.is_file():
        try:
            kept = json.loads(target.read_text(encoding='utf-8'))
            if kept.get('reader') == READER_VERSION and kept.get('sha256') == key: return kept['enums']
        except (OSError, ValueError, KeyError): pass
    found = read(path)
    if target is not None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(f'{target.name}.{os.getpid()}.tmp')
            temp.write_text(json.dumps(dict(reader=READER_VERSION, sha256=key, enums=found)), encoding='utf-8',
                            newline='\n')
            os.replace(temp, target)
        except OSError: pass        # an unwritable folder costs the next reader its reading
    return found


class Enum:
    """One enum's entries: `index(name)` the position a name holds (an EnumError for a name not there, or held twice),
    `name(i)` the full name at a position (None outside it)."""
    def __init__(self, record):
        self.path, self.entries = record['path'], list(record['entries'])
        self.ambiguous = set(record['ambiguous'])
        self._at = {}
        for i, name in enumerate(self.entries): self._at.setdefault(name, i)

    def __len__(self): return len(self.entries)

    def __contains__(self, name): return name in self._at and name not in self.ambiguous

    def index(self, name):
        if name in self.ambiguous: raise EnumError(f'{name} names more than one entry of {self.path}')
        if name not in self._at: raise EnumError(f'{self.path} has no {name}')
        return self._at[name]

    def name(self, i):
        return self.entries[i] if isinstance(i, int) and 0 <= i < len(self.entries) else None

    def unique(self, i):
        """The full name at position i when it names that entry alone, else None."""
        name = self.name(i)
        return name if name is not None and name not in self.ambiguous else None


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    enums = read(sys.argv[1])
    for wanted in sys.argv[2:] or sorted(k for k in enums if k):
        record = enums.get(wanted)
        if record is None: print(f'{wanted}: not in the package'); continue
        print(f"{record['path']} ({len(record['entries'])}){' ambiguous: ' + ', '.join(record['ambiguous']) if record['ambiguous'] else ''}")
        if len(sys.argv) > 2:
            for i, name in enumerate(record['entries']): print(f'  {i:4d} {name}')
