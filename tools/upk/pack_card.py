"""Long War Rebalance map pack cards: the writer and the reader.

LWR 3.00.00 beta 15 and later look, once per game session, for LWRMapPack_0000.upk to LWRMapPack_9999.upk anywhere
the engine finds packages (so in any folder under CookedPCConsole), and take the lines of each card's one object,
Card (class XComMutator.LWRMapPackCard), as if they stood in DefaultLWRMapPacks.ini: map records, borrowed pictures
and landing zones. A folder with a card and its maps is therefore a map pack that installs by being copied in.

The card is a small uncompressed package (version 845, licensee 0): seven names first, two imports (the package
XComMutator and the class LWRMapPackCard in it), one export, an empty depends entry, then the export's data: int32 0
and tagged properties. What is written here was read from beta 15's script (the struct fields and their defaults) and
from the engine's package format:

  PackName  string        Format  int (1; the game skips a card whose Format is higher)
  Maps      array of      MapFamily (name), Name, DisplayName, MissionType, bInRotation, TimeOfDay, ShipType (an
                          int in a card), eRegion, CouncilType, NewMap, InitialChance, InitialGain, DynamicAliens[0]
                          and [1], StreamingMaps (MapName, Loc, Rot; the game appends them in order, so a line whose
                          slots have a gap carries empty elements for the gap)
  Pictures  array of      Map, Picture (a texture's path, package.object)
  LZArray   array of      MapName, MissionType, CouncilType, StartLoc, StartDir (name), ESpawnLoc (name), AltSpawnLoc,
                          AltSpawnDir (name)

Every field of every line is written: LWR's guide says a field left out may load as 0, False or empty and not as an
ini line's default. The defaults used for a field a line does not give are the script's own (bInRotation and NewMap
True, InitialChance 20, InitialGain 1.04, the enums' None entries, everything else empty or 0).

Names. The engine keeps a name ending in _<number> (no leading zero) as a base and that number plus one, and a name
made from text at run time is split that way; a name stored whole in a package would then never equal it. Every value
that is a name (MapFamily, the enum values, the landing directions) is stored split.

  parse_record(text)                    one Maps=( ... ), Pictures=( ... ) or LZArray=( ... ) line -> Record or None
  map_line / picture_line / zone_line   a Record's fields -> the line as the card holds it (every field, typed)
  card(pack_name, maps, pictures, zones)    -> the card file's bytes
  from_lines(pack_name, lines)          the same from ini text lines (other lines are passed over) -> (bytes, warnings)
  read(data)                            a card file's bytes -> dict(PackName, Format, Maps, Pictures, LZArray)
  enum_warnings(card, enums)            the enum values the game's script does not have

  python tools/upk/pack_card.py read <LWRMapPack_NNNN.upk>
  python tools/upk/pack_card.py make <lines.txt> <folder> <number 0-9999> "<pack name>"
"""
from collections import namedtuple
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

FORMAT = 1
TAG = 0x9E2A83C1
VERSION, LICENSEE = 845, 0
ENGINE_VERSION = 8916                       # as LWR's own uncompressed script packages
NAME_FLAGS = 0x0007001000000000
OBJECT_FLAGS = 0x000F000400000000
EXPORT_SIZE = 68
FIRST_NAMES = ('Core', 'Package', 'Class', 'XComMutator', 'LWRMapPackCard', 'Card', 'None')
CARD_FILE = re.compile(r'LWRMapPack_(\d{4})\.upk', re.I)

# EShipType by position; a card holds the number (Long War's own UFOs, 10 to 14, have no entry and are written plain)
SHIPS = ('eShip_None', 'eShip_Interceptor', 'eShip_Skyranger', 'eShip_Firestorm', 'eShip_UFOSmallScout',
         'eShip_UFOLargeScout', 'eShip_UFOAbductor', 'eShip_UFOSupply', 'eShip_UFOBattle', 'eShip_UFOEthereal')
SHIP_NUMBER = {name.lower(): i for i, name in enumerate(SHIPS)}

# (field, kind, default) in the order written; the enum kinds name the game's enum
MAP_FIELDS = (('MapFamily', 'name', 'None'), ('Name', 'str', ''), ('DisplayName', 'str', ''),
              ('MissionType', 'EMissionType', 'eMission_None'), ('bInRotation', 'bool', True),
              ('TimeOfDay', 'EMissionTime', 'eMissionTime_None'), ('ShipType', 'ship', 0),
              ('eRegion', 'EMissionRegion', 'eMissionRegion_None'), ('CouncilType', 'EFCMissionType', 'eFCMType_None'),
              ('NewMap', 'bool', True), ('InitialChance', 'float', 20.0), ('InitialGain', 'float', 1.04))
ALIEN_ENUM, ALIEN_NONE = 'ECharacter', 'eChar_None'
ZONE_FIELDS = (('MapName', 'str', ''), ('MissionType', 'EMissionType', 'eMission_None'),
               ('CouncilType', 'EFCMissionType', 'eFCMType_None'), ('StartLoc', 'vector', (0.0, 0.0, 0.0)),
               ('StartDir', 'name', 'None'), ('ESpawnLoc', 'name', 'None'), ('AltSpawnLoc', 'vector', (0.0, 0.0, 0.0)),
               ('AltSpawnDir', 'name', 'None'))
PICTURE_FIELDS = (('Map', 'str', ''), ('Picture', 'str', ''))
KINDS = {'maps': 'Maps', 'pictures': 'Pictures', 'lzarray': 'LZArray'}
KEYS = {'Maps': [f for f, _, _ in MAP_FIELDS] + ['DynamicAliens', 'StreamingMaps'],
        'Pictures': [f for f, _, _ in PICTURE_FIELDS], 'LZArray': [f for f, _, _ in ZONE_FIELDS]}

Record = namedtuple('Record', 'kind fields')


class CardError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------------------------------
# ini lines
# ---------------------------------------------------------------------------------------------------------------------
_KEY = re.compile(r'([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?\s*=')
_BARE = re.compile(r'[^,)\s]+')
_HEAD = re.compile(r'\s*[+.]?\s*(Maps|Pictures|LZArray)\s*=\s*\(', re.I)


def _value(text, at):
    while at < len(text) and text[at] in ' \t': at += 1
    if at >= len(text): raise CardError('the line ends where a value should be')
    if text[at] == '"':
        end = text.find('"', at + 1)
        if end < 0: raise CardError('a quoted text is not closed')
        return text[at + 1:end], end + 1
    if text[at] == '(': return _struct(text, at)
    m = _BARE.match(text, at)
    if not m: raise CardError(f'no value at: {text[at:at + 30]}')
    return m.group(0), m.end()


def _struct(text, at):
    """( key=value, key[n]=value, ... ) at text[at] -> (dict, the position after it); key[n] gives {n: value}."""
    at += 1
    out = {}
    while True:
        while at < len(text) and text[at] in ' \t,': at += 1
        if at >= len(text): raise CardError('a bracket is not closed')
        if text[at] == ')': return out, at + 1
        m = _KEY.match(text, at)
        if not m: raise CardError(f'cannot read at: {text[at:at + 30]}')
        value, at = _value(text, m.end())
        if m.group(2) is None: out[m.group(1)] = value
        else: out.setdefault(m.group(1), {})[int(m.group(2))] = value


def _canonical(fields, known):
    """The fields with the known keys in their own spelling (ini keys are read without regard to capitals)."""
    by_lower = {k.lower(): k for k in known}
    return {by_lower.get(k.lower(), k): v for k, v in fields.items()}


def parse_record(text):
    """A Maps=( ... ), Pictures=( ... ) or LZArray=( ... ) ini line as Record(kind, fields): values as their text,
    nested brackets as dicts, key[n] as {n: value}; the known keys in their own spelling. None for any other line
    (comments, section names, blank lines). A line of one of the three kinds that can't be read raises CardError."""
    if isinstance(text, bytes): text = text.decode('latin-1')
    m = _HEAD.match(text)
    if not m: return None
    kind = KINDS[m.group(1).lower()]
    fields, _ = _struct(text, m.end() - 1)
    fields = _canonical(fields, KEYS[kind])
    for key in ('StartLoc', 'AltSpawnLoc'):
        if isinstance(fields.get(key), dict): fields[key] = _canonical(fields[key], 'XYZ')
    if isinstance(fields.get('StreamingMaps'), dict):
        fields['StreamingMaps'] = {
            n: ({k: (_canonical(v, 'XYZ') if k == 'Loc' and isinstance(v, dict)
                     else _canonical(v, ('Pitch', 'Yaw', 'Roll')) if k == 'Rot' and isinstance(v, dict) else v)
                 for k, v in _canonical(s, ('MapName', 'Loc', 'Rot')).items()} if isinstance(s, dict) else s)
            for n, s in fields['StreamingMaps'].items()}
    return Record(kind, fields)


def _bool(value):
    if isinstance(value, bool): return value
    return str(value).strip().lower() in ('true', '1', 'yes')


def _f32(value):
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]


def _vector(value, keys='XYZ'):
    if isinstance(value, dict): return tuple(_f32(value.get(k, 0)) for k in keys)
    if isinstance(value, (tuple, list)) and len(value) == 3: return tuple(_f32(v) for v in value)
    raise CardError(f'not a vector: {value!r}')


def _rotator(value):
    if isinstance(value, dict): return tuple(int(float(value.get(k, 0))) for k in ('Pitch', 'Yaw', 'Roll'))
    if isinstance(value, (tuple, list)) and len(value) == 3: return tuple(int(v) for v in value)
    raise CardError(f'not a rotator: {value!r}')


def ship_number(value):
    """A ShipType as a card holds it: the entry's number for an eShip_ name, a plain number as it is."""
    if isinstance(value, int) and not isinstance(value, bool): return value
    text = str(value).strip()
    if text.lower() in SHIP_NUMBER: return SHIP_NUMBER[text.lower()]
    try: return int(text)
    except ValueError: raise CardError(f'ShipType {text!r} is neither an eShip_ name nor a number') from None


def _typed(kind, value):
    if kind == 'str': return str(value)
    if kind == 'bool': return _bool(value)
    if kind == 'float': return _f32(value)
    if kind == 'ship': return ship_number(value)
    if kind == 'vector': return _vector(value)
    return str(value)       # a name or an enum value


def _line(fields, table):
    return {name: _typed(kind, fields[name]) if name in fields else _typed(kind, default) for name, kind, default in table}


def _stream(value):
    if value is None: value = {}
    if isinstance(value, str): value = {'MapName': value}
    return dict(MapName=str(value.get('MapName', '')), Loc=_vector(value.get('Loc', (0, 0, 0))),
                Rot=_rotator(value.get('Rot', (0, 0, 0))))


def map_line(fields):
    """A map record as the card holds it: every field, typed. `fields`: a Record's, or a line made before (the same
    comes back). StreamingMaps: {slot: stream} (ini) or a list; slots without a stream get an empty element."""
    line = _line(fields, MAP_FIELDS)
    aliens = fields.get('DynamicAliens') or {}
    if isinstance(aliens, dict): aliens = [aliens.get(0, ALIEN_NONE), aliens.get(1, ALIEN_NONE)]
    aliens = [str(a) if a else ALIEN_NONE for a in aliens]
    if len(aliens) > 2: raise CardError('DynamicAliens has two slots')
    line['DynamicAliens'] = (aliens + [ALIEN_NONE, ALIEN_NONE])[:2]
    streams = fields.get('StreamingMaps') or []
    if isinstance(streams, dict): streams = [streams.get(i) for i in range(max(streams) + 1)] if streams else []
    line['StreamingMaps'] = [_stream(s) for s in streams]
    return line


def zone_line(fields):
    return _line(fields, ZONE_FIELDS)


def picture_line(fields):
    return _line(fields, PICTURE_FIELDS)


def unknown_keys(record):
    """The keys of a Record that no card line carries."""
    return [k for k in record.fields if k not in KEYS[record.kind]]


# ---------------------------------------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------------------------------------
_NUMBERED = re.compile(r'(.+)_(0|[1-9]\d{0,9})')


def split_name(text):
    """A name as the engine keeps it: (base, number), the number being the trailing _<n> plus one, or 0 without one."""
    m = _NUMBERED.fullmatch(text)
    if m and int(m.group(2)) < 0x7FFFFFFF: return m.group(1), int(m.group(2)) + 1
    return text, 0


def fstring(text):
    if not text: return struct.pack('<i', 0)
    try: data = text.encode('ascii') + b'\0'
    except UnicodeEncodeError:
        data = text.encode('utf-16-le') + b'\0\0'
        return struct.pack('<i', -(len(data) // 2)) + data
    return struct.pack('<i', len(data)) + data


class _Writer:
    def __init__(self):
        self.names = list(FIRST_NAMES)
        self.index = {n: i for i, n in enumerate(self.names)}

    def fname(self, text, split=False):
        base, number = split_name(text) if split else (text, 0)
        if base not in self.index:
            self.index[base] = len(self.names)
            self.names.append(base)
        return struct.pack('<ii', self.index[base], number)

    def tag(self, name, kind, size, at=0):
        return self.fname(name) + self.fname(kind) + struct.pack('<ii', size, at)

    def value(self, name, kind, value, at=0):
        if kind == 'str':
            data = fstring(value)
            return self.tag(name, 'StrProperty', len(data), at) + data
        if kind == 'bool': return self.tag(name, 'BoolProperty', 0, at) + bytes([1 if value else 0])
        if kind == 'float': return self.tag(name, 'FloatProperty', 4, at) + struct.pack('<f', value)
        if kind in ('int', 'ship'): return self.tag(name, 'IntProperty', 4, at) + struct.pack('<i', value)
        if kind == 'name': return self.tag(name, 'NameProperty', 8, at) + self.fname(value, split=True)
        if kind == 'vector':
            return self.tag(name, 'StructProperty', 12, at) + self.fname('Vector') + struct.pack('<fff', *value)
        if kind == 'rotator':
            return self.tag(name, 'StructProperty', 12, at) + self.fname('Rotator') + struct.pack('<iii', *value)
        # an enum: its name after the tag, the value as a name
        return self.tag(name, 'ByteProperty', 8, at) + self.fname(kind) + self.fname(value, split=True)

    def fields(self, line, table):
        return b''.join(self.value(name, kind, line[name]) for name, kind, _ in table)

    def array(self, name, elements):
        body = struct.pack('<i', len(elements)) + b''.join(e + self.fname('None') for e in elements)
        return self.tag(name, 'ArrayProperty', len(body)) + body

    def map(self, line):
        out = self.fields(line, MAP_FIELDS)
        for at, alien in enumerate(line['DynamicAliens']): out += self.value('DynamicAliens', ALIEN_ENUM, alien, at)
        streams = [self.value('MapName', 'str', s['MapName']) + self.value('Loc', 'vector', s['Loc'])
                   + self.value('Rot', 'rotator', s['Rot']) for s in line['StreamingMaps']]
        return out + self.array('StreamingMaps', streams)


def card(pack_name, maps=(), pictures=(), zones=(), fmt=FORMAT):
    """The card file's bytes. maps, pictures, zones: lines as map_line, picture_line and zone_line make them, or the
    fields those take. The same lines give the same bytes (the package's GUID is made from its contents)."""
    maps = [map_line(m) for m in maps]
    pictures = [picture_line(p) for p in pictures]
    zones = [zone_line(z) for z in zones]
    w = _Writer()
    props = w.value('PackName', 'str', str(pack_name)) + w.value('Format', 'int', int(fmt))
    props += w.array('Maps', [w.map(m) for m in maps])
    props += w.array('Pictures', [w.fields(p, PICTURE_FIELDS) for p in pictures])
    props += w.array('LZArray', [w.fields(z, ZONE_FIELDS) for z in zones])
    data = struct.pack('<i', 0) + props + w.fname('None')         # the net index, then the tagged properties
    names = b''.join(fstring(n) + struct.pack('<Q', NAME_FLAGS) for n in w.names)
    imports = (w.fname('Core') + w.fname('Package') + struct.pack('<i', 0) + w.fname('XComMutator')
               + w.fname('Core') + w.fname('Class') + struct.pack('<i', -1) + w.fname('LWRMapPackCard'))
    digest = hashlib.sha256(names + data).digest()

    def summary(name_at, import_at, export_at, depends_at, size):
        s = struct.pack('<IHHi', TAG, VERSION, LICENSEE, size) + fstring('None') + struct.pack('<I', 1)   # package flags
        s += struct.pack('<iiiiiii', len(w.names), name_at, 1, export_at, 2, import_at, depends_at)
        s += struct.pack('<iiii', size, 0, 0, 0)        # import/export GUIDs (none), thumbnails (none)
        s += digest[:16]                                # the package's GUID: never all zeros in practice
        s += struct.pack('<iiii', 1, 1, len(w.names), 1)          # one generation: exports, names, net objects
        s += struct.pack('<iiIi', ENGINE_VERSION, 0, 0, 0)        # engine, cooker, compression flags, chunks
        s += digest[16:20] + struct.pack('<ii', 0, 0)             # package source; packages to cook, texture allocations
        return s

    name_at = len(summary(0, 0, 0, 0, 0))
    import_at = name_at + len(names)
    export_at = import_at + len(imports)
    depends_at = export_at + EXPORT_SIZE
    size = depends_at + 4
    export = (struct.pack('<iii', -2, 0, 0) + w.fname('Card') + struct.pack('<i', 0)      # class, super, outer, name, archetype
              + struct.pack('<Qii', OBJECT_FLAGS, len(data), size)                        # flags, size, offset
              + struct.pack('<Ii', 0, 0) + bytes(16) + struct.pack('<I', 0))              # export flags, net objects, GUID, package flags
    assert len(export) == EXPORT_SIZE
    return summary(name_at, import_at, export_at, depends_at, size) + names + imports + export + struct.pack('<i', 0) + data


def from_lines(pack_name, lines, fmt=FORMAT):
    """(the card's bytes, warnings) from ini text lines: the Maps, Pictures and LZArray lines in their order, every
    other line passed over. A warning names a key no card line carries."""
    maps, pictures, zones, warnings = [], [], [], []
    for text in lines:
        record = parse_record(text)
        if record is None: continue
        extra = unknown_keys(record)
        if extra:
            warnings.append('%s line %s: a card has no field %s' % (
                record.kind, record.fields.get('Name') or record.fields.get('MapName') or record.fields.get('Map') or '',
                ', '.join(extra)))
        {'Maps': maps, 'Pictures': pictures, 'LZArray': zones}[record.kind].append(record.fields)
    return card(pack_name, maps, pictures, zones, fmt), warnings


# ---------------------------------------------------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------------------------------------------------
class _Reader:
    def __init__(self, data):
        self.data, self.at = data, 0

    def unpack(self, fmt):
        try: values = struct.unpack_from(fmt, self.data, self.at)
        except struct.error: raise CardError('the file ends early') from None
        self.at += struct.calcsize(fmt)
        return values[0] if len(values) == 1 else values

    def string(self):
        count = self.unpack('<i')
        if count == 0: return ''
        size = count if count > 0 else -count * 2
        if self.at + size > len(self.data): raise CardError('a text runs past the file')
        raw = self.data[self.at:self.at + size]
        self.at += size
        return raw[:-1].decode('latin-1') if count > 0 else raw[:-2].decode('utf-16-le')


def _name(names, r):
    index, number = r.unpack('<ii')
    if not 0 <= index < len(names): raise CardError(f'name {index} is outside the name table')
    return names[index] if number == 0 else f'{names[index]}_{number - 1}'


def _properties(names, r, end, arrays):
    """Tagged properties up to None -> {name: value}; an array index above 0 makes the value a list."""
    out = {}
    while True:
        name = _name(names, r)
        if name == 'None': return out
        kind = _name(names, r)
        size, at = r.unpack('<ii')
        if kind == 'BoolProperty': value = bool(r.unpack('<B'))
        elif kind == 'StructProperty':
            what = _name(names, r)
            if size != 12 or what not in ('Vector', 'Rotator'): raise CardError(f'{name}: a {what} struct of {size} bytes')
            value = tuple(r.unpack('<fff' if what == 'Vector' else '<iii'))
        elif kind == 'ByteProperty':
            _name(names, r)                                  # the enum's name
            value = _name(names, r) if size == 8 else r.unpack('<B')
        else:
            stop = r.at + size
            if stop > end: raise CardError(f'{name} runs past the object')
            if kind == 'IntProperty': value = r.unpack('<i')
            elif kind == 'FloatProperty': value = r.unpack('<f')
            elif kind == 'StrProperty': value = r.string()
            elif kind == 'NameProperty': value = _name(names, r)
            elif kind == 'ArrayProperty' and name in arrays:
                value = [_properties(names, r, stop, arrays) for _ in range(r.unpack('<i'))]
            else: raise CardError(f'{name}: a {kind} is not something a card holds')
            if r.at != stop: raise CardError(f'{name}: its value ends at {r.at}, its tag says {stop}')
        if at:
            held = out.setdefault(name, [])
            if not isinstance(held, list): held = out[name] = [held]
            while len(held) < at: held.append(None)
            held.append(value)
        else: out[name] = value


def read(data):
    """A card file's bytes -> dict(PackName, Format, Maps, Pictures, LZArray), each line as map_line, picture_line
    and zone_line give it (a field the file does not hold takes the script's default). CardError when it is not a card."""
    if isinstance(data, (str, Path)): data = Path(data).read_bytes()
    r = _Reader(data)
    tag, version, licensee = r.unpack('<IHH')
    if tag != TAG: raise CardError('not a package')
    r.unpack('<i'); r.string(); flags = r.unpack('<I')
    if flags & 0x02000000: raise CardError('a compressed package')
    name_count, name_at, export_count, export_at, import_count, import_at = r.unpack('<iiiiii')
    r.at, names = name_at, []
    for _ in range(name_count):
        names.append(r.string()); r.unpack('<Q')
    r.at, imports = import_at, []
    for _ in range(import_count):
        r.at += 20
        imports.append(_name(names, r))
    r.at = export_at
    for _ in range(export_count):
        cls, _, _ = r.unpack('<iii')
        name = _name(names, r)
        r.unpack('<i'); r.unpack('<Q')
        size, offset = r.unpack('<ii')
        r.unpack('<I'); net = r.unpack('<i')
        r.at += 4 * net + 16 + 4
        if name != 'Card': continue
        if cls >= 0 or -cls - 1 >= len(imports) or imports[-cls - 1] != 'LWRMapPackCard':
            raise CardError('the object Card is not an LWRMapPackCard')
        body = _Reader(data)
        body.at = offset + 4
        props = _properties(names, body, offset + size, ('Maps', 'Pictures', 'LZArray', 'StreamingMaps'))
        if body.at != offset + size: raise CardError(f'the properties end at {body.at}, the object at {offset + size}')
        return dict(PackName=props.get('PackName', ''), Format=props.get('Format', 0), version=version, licensee=licensee,
                    Maps=[map_line(m) for m in props.get('Maps') or []],
                    Pictures=[picture_line(p) for p in props.get('Pictures') or []],
                    LZArray=[zone_line(z) for z in props.get('LZArray') or []])
    raise CardError('no object named Card')


def number_of(file_name):
    """A card file's number (LWRMapPack_0042.upk -> 42), or None when the name is not a card's."""
    m = CARD_FILE.fullmatch(Path(file_name).name)
    return int(m.group(1)) if m else None


def file_name(number):
    if not 0 <= int(number) <= 9999: raise CardError('a card\'s number is 0 to 9999')
    return 'LWRMapPack_%04d.upk' % int(number)


def enum_warnings(held, enums):
    """The enum values in a card (as read or as lines) that the game's script lacks. enums: {enum name: its entries'
    names}; an enum not in it is not checked."""
    lower = {enum: {str(v).lower() for v in values} for enum, values in enums.items()}
    out = []

    def check(where, enum, value):
        if enum in lower and value.lower() not in lower[enum]: out.append(f'{where}: the game has no {enum} {value}')
    for m in held.get('Maps') or []:
        m = map_line(m)
        for name, kind, _ in MAP_FIELDS:
            if kind[0] == 'E': check(m['DisplayName'] or m['Name'], kind, m[name])
        for alien in m['DynamicAliens']: check(m['DisplayName'] or m['Name'], ALIEN_ENUM, alien)
    for z in held.get('LZArray') or []:
        z = zone_line(z)
        for name, kind, _ in ZONE_FIELDS:
            if kind[0] == 'E': check('landing zone of ' + z['MapName'], kind, z[name])
    return out


def main(argv):
    if len(argv) == 3 and argv[1] == 'read':
        print(json.dumps(read(Path(argv[2]).read_bytes()), indent=1))
    elif len(argv) == 6 and argv[1] == 'make':
        data, warnings = from_lines(argv[5], Path(argv[2]).read_text(encoding='latin-1').splitlines())
        target = Path(argv[3]) / file_name(int(argv[4]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        held = read(data)
        print(target, '-', len(held['Maps']), 'map line(s),', len(held['Pictures']), 'picture line(s),',
              len(held['LZArray']), 'landing line(s)')
        for w in warnings: print('note:', w)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
