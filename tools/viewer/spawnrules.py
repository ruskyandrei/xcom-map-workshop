"""What a game install does with a map's spawn points: Long War's tactical spawn mutators, read from the install's
config each time it is asked (private/plans/done/editor-spawns-implementation-plan.md, SP2 and SP8). Pure functions
over text, and `rules(game)`, which reads the two files.

- DefaultMutatorLoader.ini: `arrTacticalMutators` lines in [XComMutator.XComMutatorLoader], in order. The five
  spawn mutators are Long War's XComLZMutator classes (FAMILIES). A commented line (';') is no mutator.
- DefaultRandomSpawns.ini: the drop-in mutator's range, flags and `ExcludeMaps` list, the shared proximities, the bomb
  mutator's and the Meld mutator's numbers.

This is install detection: whether a mutator ran in a battle is the game log's to say. Plain Enemy Within has no
loader file: every family is then 'absent'. A loader file whose section can't be found gives 'unknown', never a
guess.

SP8's writer planning is here too: plan_exclusion() places the variant's `ExcludeMaps` line in
[XComLZMutator.XComSpawnAlienMutator] (spawnRules.dropIns = "placed": Long War's drop-in mutator then leaves every
scripted drop-in of the variant where the map puts it), and exclusion_lines() finds such lines again to take them
out.
"""
import re

LOADER = 'DefaultMutatorLoader.ini'
RANDOM_SPAWNS = 'DefaultRandomSpawns.ini'
LOADER_SECTION = 'XComMutator.XComMutatorLoader'
DROP_IN_SECTION = 'XComLZMutator.XComSpawnAlienMutator'
# family -> the loader's class name
FAMILIES = {
    'landing': 'XComLZMutator.XComLZMutator',
    'bomb': 'XComLZMutator.XComBombMutator',
    'meld': 'XComLZMutator.XComMeldSpawnMutator',
    'pods': 'XComLZMutator.XComPodSpawnMutator',
    'dropIns': 'XComLZMutator.XComSpawnAlienMutator',
}
# the numbers the page and the compiler say, by section and key
NUMBERS = {
    DROP_IN_SECTION: {'MIN_DROP_DIST': 'dropMin', 'MAX_DROP_DIST': 'dropMax', 'USE_OVERWATCH': 'useOverwatch',
                      'DROP_TO_COVER': 'dropToCover', 'REVEAL_SPAWN': 'revealSpawn'},
    'XComLZMutator.XComSpawnMutator': {'PLAYER_PROXIMITY': 'playerProximity', 'OP_PROXIMITY': 'operativeProximity',
                                       'AVOID_CAPTURE_ZONES': 'avoidCaptureZones'},
    'XComLZMutator.XComBombMutator': {'PLAYER_PROXIMITY': 'bombProximity', 'INITIAL_TIMER_VALUE': 'bombTimer'},
    'XComLZMutator.XComMeldSpawnMutator': {'NumContainers': 'meldContainers', 'EqSlope': 'meldSlope', 'EqConst': 'meldConst'},
}
SECTION = re.compile(r'^\s*\[([^\]]+)\]\s*$')
# a key line: optional ';' (commented), optional UE3 array prefix (+ - . !), key, '=', value
KEY = re.compile(r'^\s*(;+)?\s*([+\-.!]?)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$')


def _text(value):
    return value.decode('latin-1') if isinstance(value, (bytes, bytearray)) else str(value)


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1], True
    return value, False


def entries(text):
    """Every key line of an INI text: [dict(line (counted from 1), section, key, value, quoted, live, prefix)]. A
    commented line is listed with live False, so a writer can place beside it."""
    out, section = [], None
    for n, raw in enumerate(_text(text).splitlines(), 1):
        m = SECTION.match(raw)
        if m:
            section = m.group(1).strip()
            continue
        m = KEY.match(raw)
        if not m:
            continue
        value, quoted = _unquote(m.group(4))
        out.append(dict(line=n, section=section, key=m.group(3), value=value, quoted=quoted,
                        live=not m.group(1), prefix=m.group(2)))
    return out


def sections(text):
    """The section names of an INI text, in order."""
    return [m.group(1).strip() for raw in _text(text).splitlines() if (m := SECTION.match(raw))]


def loader(text):
    """The loader file's tactical mutators: dict(found (its section is there), tactical (live, in order), commented,
    families: {family: 'active' | 'absent'}), or found False with every family 'unknown'."""
    if LOADER_SECTION not in sections(text):
        return dict(found=False, tactical=[], commented=[], families={f: 'unknown' for f in FAMILIES})
    rows = [e for e in entries(text) if e['section'] == LOADER_SECTION and e['key'] == 'arrTacticalMutators'
            and e['prefix'] != '-']
    tactical = [e['value'] for e in rows if e['live']]
    commented = [e['value'] for e in rows if not e['live']]
    live = {t.casefold() for t in tactical}
    return dict(found=True, tactical=tactical, commented=commented,
                families={f: 'active' if c.casefold() in live else 'absent' for f, c in FAMILIES.items()})


def _number(value):
    v = value.strip().casefold()
    if v in ('true', 'false'): return v == 'true'
    try: return int(v)
    except ValueError: pass
    try: return float(v)
    except ValueError: return value


def random_spawns(text):
    """The RandomSpawns file: dict(found (the drop-in section is there), config: {name: value} for NUMBERS' keys (the
    last live line of each), excludeMaps: [dict(name, live, line, quoted)] in order, every ExcludeMaps line of the
    drop-in section, commented ones included)."""
    rows = entries(text)
    config = {}
    for e in rows:
        name = NUMBERS.get(e['section'], {}).get(e['key'])
        if name and e['live']: config[name] = _number(e['value'])
    exclude = [dict(name=e['value'], live=e['live'], line=e['line'], quoted=e['quoted']) for e in rows
               if e['section'] == DROP_IN_SECTION and e['key'] == 'ExcludeMaps' and e['prefix'] != '-']
    return dict(found=DROP_IN_SECTION in sections(text), config=config, excludeMaps=exclude)


def excluded(rules_or_list, name):
    """Whether a live ExcludeMaps entry names the map (Find on the mutator's string array: the name as the running
    map's, compared regardless of case as UE3's strings compare)."""
    rows = rules_or_list.get('excludeMaps', []) if isinstance(rules_or_list, dict) else rules_or_list
    return any(r['live'] and r['name'].casefold() == str(name).casefold() for r in rows)


def rules(game):
    """What the install at `game` does with spawn points: dict(kind ('lwr', 'longwar', 'ew' or None),
    landing/bomb/meld/pods/dropIns ('active' | 'absent' | 'unknown'), tactical (the loader's tactical mutators in
    order), config ({name: value}), excludeMaps ([dict(name, live, line, quoted)]), files ({name: path or None}),
    detected: 'install' (what the files say; the game log says what ran))."""
    from settings import game_config, game_kind
    out = dict(kind=None, **{f: 'unknown' for f in FAMILIES}, tactical=[], config={}, excludeMaps=[],
               files={LOADER: None, RANDOM_SPAWNS: None}, detected='install', dropInSection=False)
    if game is None:
        return out
    folder = game_config(game)
    out['kind'] = game_kind(game)
    load = folder / LOADER
    if not load.is_file():
        out.update({f: 'absent' for f in FAMILIES})
        return out
    out['files'][LOADER] = str(load)
    found = loader(load.read_bytes())
    out.update(found['families'], tactical=found['tactical'])
    spawn = folder / RANDOM_SPAWNS
    if spawn.is_file():
        out['files'][RANDOM_SPAWNS] = str(spawn)
        read = random_spawns(spawn.read_bytes())
        out.update(config=read['config'], excludeMaps=read['excludeMaps'], dropInSection=read['found'])
    return out


# ---------------------------------------------------------------- SP8: the variant's ExcludeMaps line

def exclusion_entry(variant):
    """The line that excludes a variant, written as the install's own lines are."""
    return 'ExcludeMaps = "%s"' % variant


def exclusion_block(variant, note):
    """The lines a variant's exclusion adds (bytes): a comment naming the editor and the project (`note`), then
    exclusion_entry(variant)."""
    return [(';%s: scripted drop-ins land where placed (%s)' % (variant, note)).encode('latin-1', 'replace'),
            exclusion_entry(variant).encode('latin-1')]


def plan_exclusion(lines, variant, note):
    """(at, new lines, why) for DefaultRandomSpawns.ini (lines of bytes): insert the new lines before index `at` (after
    the last ExcludeMaps line of the drop-in section, live or commented, else at the section's end): a comment naming
    the editor and the project (`note`), then exclusion_entry(variant). (None, [], None) when a live entry for the
    variant is there already; (None, [], why) when the file has no drop-in section (another version's file)."""
    texts = [_text(l) for l in lines]
    section, start, end, last = None, None, None, None
    for i, raw in enumerate(texts):
        m = SECTION.match(raw)
        if m:
            if section == DROP_IN_SECTION and end is None:
                end = i
            section = m.group(1).strip()
            if section == DROP_IN_SECTION and start is None:
                start = i
            continue
        if section != DROP_IN_SECTION:
            continue
        k = KEY.match(raw)
        if k and k.group(3) == 'ExcludeMaps' and k.group(2) != '-':
            value, _ = _unquote(k.group(4))
            if not k.group(1) and value.casefold() == variant.casefold():
                return None, [], None
            last = i
    if start is None:
        return None, [], 'the file has no [%s] section: it is another version\'s' % DROP_IN_SECTION
    if section == DROP_IN_SECTION and end is None:
        end = len(texts)
    if last is not None:
        at = last + 1
    else:
        at = end
        while at - 1 > start and not texts[at - 1].strip():
            at -= 1         # before the blank lines that end the section
    return at, exclusion_block(variant, note), None


def exclusion_lines(lines, variant):
    """The indices of a variant's live ExcludeMaps lines in the drop-in section (lines of bytes or text)."""
    out, section = [], None
    for i, raw in enumerate(_text(l) for l in lines):
        m = SECTION.match(raw)
        if m:
            section = m.group(1).strip()
            continue
        k = KEY.match(raw)
        if section == DROP_IN_SECTION and k and not k.group(1) and k.group(3) == 'ExcludeMaps':
            if _unquote(k.group(4))[0].casefold() == variant.casefold():
                out.append(i)
    return out
