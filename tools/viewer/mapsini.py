"""The game's map configuration files (DefaultMaps.ini, DefaultLZMutator.ini and their kind) as lines of bytes,
read and changed as the editor installs and removes its maps: a record's fields, the streams it names, the record a
first mission plays, a map's landing-zone lines copied under another name, and a change checked against its plan and
written through a temporary file.

The files are Windows text in the game's code page: lines end CRLF (a mixed file or one with a byte-order mark is
refused), and a field's value is read and written as Latin-1. Every function takes and gives lines of bytes, so a
file written back keeps every byte it had outside the planned change.

The installer (installs.py), the map browser (gamemaps.py) and the pack export (manager.py) use these, and the lab's
fixture installer (tools/bake/deploy_fixture.py) too.
"""
import os       # (the writes go through atomic_files; tools/bake/tests/test_deploy.py patches mapsini.os.replace)
from pathlib import Path
import re

import atomic_files

EOL = b'\r\n'
FIRST_MISSION = 'eMission_Abduction'      # the kind of mission a new campaign's first mission (the test slot) plays


def lines_of(data):
    if data.startswith(b'\xef\xbb\xbf'):
        raise ValueError('unexpected byte-order mark')
    if data.count(b'\n') != data.count(EOL):
        raise ValueError('mixed line endings')
    return data.split(EOL)


def is_record(line):
    return line.lstrip().startswith(b'Maps=(')


def field(line, name):
    m = re.search(rb'(?<![A-Za-z])' + name.encode() + rb'="([^"]*)"', line)
    return m.group(1).decode('latin1') if m else None


def set_field(line, name, value, quoted=True):
    pat = rb'(?<![A-Za-z])' + name.encode() + (rb'="[^"]*"' if quoted else rb'=[A-Za-z_]+')
    new = name.encode() + (b'="' + value.encode('latin1') + b'"' if quoted else b'=' + value.encode('latin1'))
    out, n = re.subn(pat, lambda _: new, line, count=1)
    if n != 1:
        raise ValueError(f'record has no {name}')
    return out


def unquoted(line, name):
    m = re.search(rb'(?<![A-Za-z])' + name.encode() + rb'=([A-Za-z_]+)', line)
    return m.group(1).decode('latin1') if m else None


def stream_slots(line):
    return [int(k) for k in re.findall(rb'StreamingMaps\[\s*(\d+)\s*\]\s*=', line)]


def add_stream(line, patch):
    """The record line with `patch` streamed in the lowest slot it does not use, written as patchtool writes one."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,62}', patch):
        raise ValueError(f'bad patch name {patch!r}')
    if re.search(rb'MapName="' + patch.encode() + rb'"', line, re.I):
        raise ValueError(f'the record streams {patch} already')
    used = set(stream_slots(line))
    k = min(set(range(len(used) + 1)) - used)
    close = line.rindex(b')')
    entry = f', StreamingMaps[{k}]=( MapName="{patch}", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) '
    return line[:close].rstrip() + entry.encode() + line[close:], k


def slot_record(lines, bases):
    """Which of a map's records (indices) the test slot plays: the first mission is an abduction, so the map's own
    abduction record if it has one, else its first record that is no council mission (whose type and streams a
    bomb or rescue needs), else its first."""
    council = lambda i: (unquoted(lines[i], 'CouncilType') or 'eFCMType_None') != 'eFCMType_None'  # noqa: E731
    return next((i for i in bases if unquoted(lines[i], 'MissionType') == FIRST_MISSION and not council(i)),
                next((i for i in bases if not council(i)), bases[0]))


def slot_streams(line):
    return [s.decode('latin1') for s in re.findall(rb'MapName="([^"]+)"', line)]


def plan_lz(lines, base, variant, note):
    tag = f'MapName="{variant}"'.encode()
    if any(tag in l for l in lines):
        return None, []
    mine = [i for i, l in enumerate(lines) if f'MapName="{base}"'.encode() in l and not l.lstrip().startswith(b';')]
    if not mine:
        # a map that lands no Skyranger (TempleShip) has none, and its variant needs none (patchtool warns likewise)
        return None, []
    new = [f';{variant} locations = copy of {base} ({note})'.encode()]
    new += [lines[i].replace(f'MapName="{base}"'.encode(), tag) for i in mine]
    return mine[-1] + 1, new


def check_change(old, new, replaced=(), inserted=None, removed=None):
    """new must be old with only these changes: lines replaced at the given indices, or a run of lines inserted
    (at, count) or removed (at, count)."""
    if inserted:
        at, n = inserted
        ok = new[:at] == old[:at] and new[at + n:] == old[at:]
    elif removed:
        at, n = removed
        ok = old[:at] == new[:at] and old[at + n:] == new[at:]
    else:
        ok = len(old) == len(new) and {i for i, (a, b) in enumerate(zip(old, new)) if a != b} <= set(replaced)
    if not ok:
        raise ValueError('planned change touches other lines')


def write_checked(path, new_lines):
    """The lines written to `path` through a temporary file beside it, read back, then put in its place with a replace:
    a crash or a forced stop mid-write never leaves the game's config file cut short, and one that does not read back
    as written never replaces it (review finding 2)."""
    path = Path(path)
    temp = path.with_name(f'.{path.name}.write.tmp')
    try:
        temp.write_bytes(EOL.join(new_lines))
        if lines_of(temp.read_bytes()) != new_lines:
            raise ValueError(f'{path} did not read back as written')
        # (tried again while another process holding the file a moment, a virus scanner or an editor, makes Windows
        # refuse the replace)
        atomic_files.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
