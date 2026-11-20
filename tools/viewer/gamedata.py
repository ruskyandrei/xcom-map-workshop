"""What a game install's own data says about its soldiers, SHIVs and equipment: the catalogue the test squad is set up
from (private/plans/done/test-squad-plan.md, section 5.2).

Three sources, all of the install the squad plays in:
- the enums of its XComGame.upk (tools/upk/script_enums.py): which entry each item, class, perk, stat, country and
  traversal is. An enum name refers to a slot of the game's tables, not to a meaning: Long War renumbers and
  repurposes slots (LWR's Tactical Vest is item 57, eItem_END_WEAPONS), so an entry is known by its full name and
  labelled from the localisation;
- its DefaultGameCore.ini: the base characters (Characters, the soldier's and the tank's rows), the armours (Armors)
  and weapons and items (Weapons), and which items have a cost row (ItemBalance_*: equipment XCOM makes, against the
  aliens' own). The game builds its config from this file; a generated XComGameCore.ini beside it (a game started
  with -nohomedir keeps it there) that is newer and differs in those rows is named in `diagnostics`, as the game
  may read it instead;
- its localisation (XComGame and XComStrategyGame, the language DefaultEngine.ini names, else INT): the names of
  items, perks, classes, ranks, countries and characters, by full enum name or by number, falling back to INT and
  then to the entry's own name.

`load(game, cache)` reads them into a Catalogue, keeping the enums in `cache` (by package hash and reader version);
its `fingerprint` changes whenever any file read changes (the package, the config, the localisation, the language,
or PARSER_VERSION), so a saved choice checked against one catalogue is checked again against another.

The INI reader keeps what the game's own reading does with these files: sections of the same name are one section;
`Key=` and `.Key=` add a value, `+Key=` adds it when not there yet, `-Key=` removes it and `!Key=` clears the key;
a line starting with ; is a comment. A struct value runs from its opening bracket to the matching closing one
(quoted strings may hold commas and brackets), and what follows it on the line (LWR's `;Tac Vest`) is ignored.
Enum values are matched without regard to case, as the game does (`eWP_Anyclass`).
"""
import codecs
import hashlib
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'upk'))
import script_enums  # noqa: E402
from script_enums import Enum  # noqa: E402

PARSER_VERSION = 1
CORE = 'XComGame.XGTacticalGameCore'
ENUMS = ('EItemType', 'ECharacter', 'ESoldierClass', 'EPerkType', 'EAbility', 'ECharacterProperty', 'ECharacterStat',
         'ETraversalType', 'EArmorProperty', 'EWeaponProperty', 'EItemSize', 'ECountry')
# the stats a base character's config row names, and the ECharacterStat entry each is (not by a guess at prefixes:
# CritHitChance is eStat_CriticalShot)
ROW_STATS = dict(HP='eStat_HP', Offense='eStat_Offense', Defense='eStat_Defense', Mobility='eStat_Mobility',
                 SightRadius='eStat_SightRadius', Will='eStat_Will', ShieldHP='eStat_ShieldHP',
                 CritHitChance='eStat_CriticalShot', CritWoundChance='eStat_CriticalWoundChance',
                 FlightFuel='eStat_FlightFuel', Reaction='eStat_Reaction')
TRAVERSALS = ('Normal', 'ClimbOver', 'ClimbOnto', 'ClimbLadder', 'DropDown', 'Grapple', 'Landing', 'BreakWindow',
              'KickDoor', 'JumpUp', 'WallClimb', 'BreakWall')


class GameDataError(Exception):
    """The install lacks something the catalogue cannot do without (its package, its config)."""


def read_text(path):
    """A config or localisation file's text: UTF-16 with a byte-order mark, UTF-8 with one, else Windows-1252."""
    data = Path(path).read_bytes()
    if data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE): return data.decode('utf-16')
    if data[:3] == codecs.BOM_UTF8: return data[3:].decode('utf-8')
    return data.decode('cp1252', errors='replace')


# ---- INI ----

def ini_entries(text):
    """[(section, op, key, value)] in file order: op is '', '.', '+', '-' or '!'."""
    out, section = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(';'): continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip()
            continue
        if section is None or '=' not in line: continue
        op = line[0] if line[0] in '.+-!' else ''
        key, value = line[len(op):].split('=', 1)
        out.append((section, op, key.strip(), value.strip()))
    return out


def ini_values(entries, section, key):
    """The values of one key of one section after the operators, in order (sections and keys without case)."""
    values, s, k = [], section.lower(), key.lower()
    for sec, op, name, value in entries:
        if sec.lower() != s or name.lower() != k: continue
        if op == '!': values = []
        elif op == '-': values = [v for v in values if v != value]
        elif op == '+':
            if value not in values: values.append(value)
        else: values.append(value)
    return values


def ini_value(entries, section, key, default=None):
    values = ini_values(entries, section, key)
    return values[-1] if values else default


def _struct_text(value):
    """The bracketed struct at the start of a config value, with what follows dropped."""
    value = value.strip()
    if not value.startswith('('): raise ValueError(f'not a struct: {value[:40]!r}')
    depth, quoted, escaped = 0, False, False
    for i, ch in enumerate(value):
        if quoted:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': quoted = False
        elif ch == '"': quoted = True
        elif ch == '(': depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0: return value[1:i]
    raise ValueError(f'unclosed struct: {value[:40]!r}')


def _split_top(text):
    parts, depth, quoted, escaped, start = [], 0, False, False, 0
    for i, ch in enumerate(text):
        if quoted:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': quoted = False
        elif ch == '"': quoted = True
        elif ch == '(': depth += 1
        elif ch == ')': depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$')


def parse_struct(value):
    """A config struct as a dict: a plain key's value is its text (a quoted string unquoted, a nested struct a dict),
    and an array key's values a dict of index to text (ABILITIES[0]=... gives {'ABILITIES': {0: ...}}). Repeated keys
    keep the last value. A ValueError says what could not be read."""
    out = {}
    for part in _split_top(_struct_text(value)):
        if '=' not in part: raise ValueError(f'no value in {part[:40]!r}')
        key, text = (s.strip() for s in part.split('=', 1))
        match = _KEY.match(key)
        if not match: raise ValueError(f'bad key {key!r}')
        if text.startswith('('): parsed = parse_struct(text)
        elif text.startswith('"') and text.endswith('"') and len(text) >= 2:
            parsed = re.sub(r'\\(.)', r'\1', text[1:-1])
        else: parsed = text
        name, index = match.group(1), match.group(2)
        if index is None: out[name] = parsed
        else: out.setdefault(name, {})[int(index)] = parsed
    return out


def array(struct, key, length):
    """An array key of a parsed struct as a list of `length` texts ('0' where unset)."""
    found = struct.get(key) or {}
    return [found.get(i, '0') for i in range(length)]


# ---- localisation ----

LANGUAGES = ('INT', 'FRA', 'DEU', 'ITA', 'ESN', 'POL', 'RUS', 'JPN', 'KOR', 'CHT')


def game_language(game):
    """The language the install's engine config names (DefaultEngine.ini, else BaseEngine.ini), else INT."""
    for path in (Path(game) / 'XEW' / 'XComGame' / 'Config' / 'DefaultEngine.ini',
                 Path(game) / 'XEW' / 'Engine' / 'Config' / 'BaseEngine.ini'):
        try: found = ini_value(ini_entries(read_text(path)), 'Engine.Engine', 'Language')
        except OSError: continue
        if found and found.upper() in LANGUAGES: return found.upper()
    return 'INT'


class Localisation:
    """The localised lines of a few files: `table(file, section, key)` is {index text: line} for an array key, its
    index texts as the file writes them (a full enum name, or a number)."""
    FILES = ('XComGame', 'XComStrategyGame')

    def __init__(self, game, language='INT'):
        self.root = Path(game) / 'XEW' / 'XComGame' / 'Localization'
        self.language = language
        self.paths, self._entries = [], {}
        for lang in dict.fromkeys((language, 'INT')):
            for stem in self.FILES:
                path = self.root / lang / f'{stem}.{lang.lower()}'
                if path.is_file(): self.paths.append(path)

    def _file(self, lang, stem):
        key = (lang, stem)
        if key not in self._entries:
            path = self.root / lang / f'{stem}.{lang.lower()}'
            try: self._entries[key] = _array_lines(read_text(path))
            except OSError: self._entries[key] = {}
        return self._entries[key]

    def table(self, stem, section, key):
        """{index text (lower case): line}, the selected language's over INT's."""
        merged = {}
        for lang in dict.fromkeys(('INT', self.language)):
            merged.update(self._file(lang, stem).get((section.lower(), key.lower()), {}))
        return merged

    def label(self, stem, section, key, enum, index):
        """The line for the enum entry at `index`, by its full name or its number, or None."""
        lines = self.table(stem, section, key)
        name = enum.name(index) if enum is not None else None
        for want in ((name or '').lower(), str(index)):
            if want and lines.get(want): return lines[want]
        return None


def _array_lines(text):
    out, section = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(';'): continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip().lower()
            continue
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\[([^\]]+)\]\s*=\s*(.*)$', line)
        if not match or section is None: continue
        value = match.group(3).strip()
        if value.startswith('"'):
            end = value.rfind('"')
            value = value[1:end] if end > 0 else value[1:]
        out.setdefault((section, match.group(1).lower()), {})[match.group(2).strip().lower()] = value
    return out


# ---- the catalogue ----

def _package(game): return Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole' / 'XComGame.upk'
def _config(game, name): return Path(game) / 'XEW' / 'XComGame' / 'Config' / name


def input_files(game, language='INT'):
    """Every file load() may read for a game folder (some may not exist)."""
    game = Path(game)
    files = [_package(game), _config(game, 'DefaultGameCore.ini'), _config(game, 'XComGameCore.ini'),
             _config(game, 'DefaultEngine.ini'), game / 'XEW' / 'Engine' / 'Config' / 'BaseEngine.ini']
    root = game / 'XEW' / 'XComGame' / 'Localization'
    for lang in dict.fromkeys(('INT', language)):
        files += [root / lang / f'{stem}.{lang.lower()}' for stem in Localisation.FILES]
    return files


def signature(game):
    """The size and time of each file load() reads: a catalogue read when they were the same is still the install's."""
    out = []
    for path in input_files(game, game_language(game)):
        try:
            stat = path.stat()
            out.append((str(path), stat.st_size, stat.st_mtime_ns))
        except OSError: out.append((str(path), None, None))
    return tuple(out)


def _digest(paths, extra):
    digest = hashlib.sha256(repr(extra).encode())
    for path in paths:
        digest.update(str(Path(path).name).encode())
        try: digest.update(script_enums.sha256(path).encode())
        except OSError: digest.update(b'missing')
    return digest.hexdigest()


class Catalogue:
    """An install's squad-relevant data. enums: {name: script_enums.Enum}; characters: {'eChar_Soldier': row, ...};
    armours and weapons: {item index: row}; costed: the item indices with a cost row; diagnostics: [what was odd].
    A row is the parsed struct with 'index' (the item's or character's entry) added."""

    def __init__(self, game, family, language, enums, entries, localisation, fingerprint, files):
        self.game, self.family, self.language = Path(game), family, language
        self.enums, self.localisation, self.fingerprint, self.files = enums, localisation, fingerprint, files
        self.diagnostics = []
        self.characters, self.armours, self.weapons, self.costed = {}, {}, {}, set()
        self._read_rows(entries)

    # an enum value as written in the config (a full name, any case, or a number) to its index, or None
    def resolve(self, enum_name, text):
        enum = self.enums.get(enum_name)
        text = (text or '').strip()
        if re.fullmatch(r'-?\d+', text): return int(text)
        if enum is None or not text: return None
        lowered = text.lower()
        hits = [i for i, name in enumerate(enum.entries) if name.lower() == lowered]
        return hits[0] if len(hits) == 1 else None

    def _read_rows(self, entries):
        for kind, target, enum in (('Characters', self.characters, 'ECharacter'), ('Armors', self.armours, 'EItemType'),
                                   ('Weapons', self.weapons, 'EItemType')):
            for value in ini_values(entries, CORE, kind):
                try: row = parse_struct(value)
                except ValueError as error:
                    self.diagnostics.append(f'A {kind} row could not be read ({error})')
                    continue
                index = self.resolve(enum, row.get('iType'))
                if index is None:
                    self.diagnostics.append(f'A {kind} row names {row.get("iType")!r}, which is not an entry of {enum}')
                    continue
                key = self.enums[enum].name(index) if kind == 'Characters' else index
                if key in target:
                    # XGTacticalGameCore.BuildWeapon/BuildArmor/BuildCharacter store each row at its type's index,
                    # in file order: a later row replaces an earlier one
                    self.diagnostics.append(f'{kind} has two rows for {self.enums[enum].name(index) or index}; the later one is used')
                target[key] = dict(row, index=index)
        for section_key in [k for (s, _, k, _) in entries if s.lower() == CORE.lower() and k.lower().startswith('itembalance')]:
            for value in ini_values(entries, CORE, section_key):
                try: row = parse_struct(value)
                except ValueError: continue
                index = self.resolve('EItemType', row.get('eItem'))
                if index: self.costed.add(index)

    def item_label(self, index):
        return self.localisation.label('XComGame', 'XLocalizedData', 'm_aItemNames', self.enums.get('EItemType'), index)

    def label(self, kind, index):
        """The localised name of an entry: kind is item, perk, class, rank, country or character."""
        enums, loc = self.enums, self.localisation
        if kind == 'item': return self.item_label(index)
        if kind == 'perk':
            return (loc.label('XComGame', 'XComPerkManager', 'm_strPassiveTitle', enums.get('EPerkType'), index)
                    or loc.label('XComGame', 'XComPerkManager', 'm_strBonusTitle', enums.get('EPerkType'), index))
        if kind == 'class': return loc.label('XComGame', 'XGTacticalGameCore', 'm_aSoldierClassNames', enums.get('ESoldierClass'), index)
        if kind == 'rank': return loc.label('XComGame', 'XGTacticalGameCoreNativeBase', 'm_aRankNames', None, index)
        if kind == 'country': return loc.label('XComStrategyGame', 'XGLocalizedData', 'CountryNames', enums.get('ECountry'), index)
        if kind == 'character': return loc.label('XComGame', 'XLocalizedData', 'm_aCharacterName', enums.get('ECharacter'), index)
        raise ValueError(kind)

    def ranks(self):
        """[(rank, label)] for the ranks the localisation names (0 up)."""
        lines = self.localisation.table('XComGame', 'XGTacticalGameCoreNativeBase', 'm_aRankNames')
        out = []
        for rank in range(32):
            if str(rank) not in lines: break
            out.append((rank, lines[str(rank)]))
        return out

    def flags(self, row, key, enum_name, length):
        """The non-zero entries of an array key of a row, as enum full names (texts that resolve to nothing kept as
        written)."""
        enum = self.enums.get(enum_name)
        out = []
        for text in array(row, key, length):
            index = self.resolve(enum_name, text)
            if index == 0: continue
            out.append(enum.name(index) if index is not None and enum is not None and enum.name(index) else text)
        return out


def load(game, cache=None, family=None, language=None):
    """The Catalogue of a game folder. cache: a folder for the enums (None: read each time). family: settings.game_kind
    (worked out when None). A GameDataError says what the install lacks."""
    from settings import game_kind
    game = Path(game)
    family = family or game_kind(game)
    if family is None: raise GameDataError(f'{game} is not a game folder')
    package, core = _package(game), _config(game, 'DefaultGameCore.ini')
    if not package.is_file(): raise GameDataError(f'{game} has no XEW\\XComGame\\CookedPCConsole\\XComGame.upk')
    if not core.is_file(): raise GameDataError(f'{game} has no XEW\\XComGame\\Config\\DefaultGameCore.ini')
    language = language or game_language(game)
    try: found = script_enums.cached(package, cache)
    except (OSError, script_enums.EnumError) as error: raise GameDataError(f'XComGame.upk could not be read: {error}')
    missing = [name for name in ENUMS if name not in found]
    if missing: raise GameDataError(f'XComGame.upk has no {", ".join(missing)}')
    enums = {name: Enum(found[name]) for name in ENUMS}
    entries = ini_entries(read_text(core))
    localisation = Localisation(game, language)
    generated = _config(game, 'XComGameCore.ini')
    files = [package, core] + localisation.paths
    fingerprint = _digest(files + ([generated] if generated.is_file() else []),
                          (PARSER_VERSION, script_enums.READER_VERSION, family, language))
    catalogue = Catalogue(game, family, language, enums, entries, localisation, fingerprint, files)
    if generated.is_file():
        try:
            if generated.stat().st_mtime > core.stat().st_mtime:
                theirs = ini_entries(read_text(generated))
                if any(ini_values(theirs, CORE, k) and ini_values(theirs, CORE, k) != ini_values(entries, CORE, k)
                       for k in ('Characters', 'Armors', 'Weapons')):
                    catalogue.diagnostics.append('XComGameCore.ini beside DefaultGameCore.ini is newer and has other '
                                                 'character, armour or weapon rows: the game may read those')
        except OSError: pass
    return catalogue
