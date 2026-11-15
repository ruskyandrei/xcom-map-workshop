"""Census of what each mission of a game install holds: for every package a DefaultMaps.ini record streams for a
mission (its `_Stream`, `_Bomb`, `_CNH`, `_CovExt` and the like; landing intros and patches left out), and for every
base map, the classes of the actors placed in its level and of its Kismet objects, with the missions (mission type
and council type) that use it. Read-only; made for private/plans/done/mission-types-plan.md.

  python -B tools/upk/audit_missions.py <game install> <out.json>
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVEL = 'TheWorld.PersistentLevel.'
SKIPPED = ('cin_', 'patch_')    # landing intros and other cinematics, LWR's patches: not a mission's own


def field(line, key):
    m = re.search(r'\b' + key + r'\s*=\s*("[^"]*"|[^,\s)]+)', line)
    return m.group(1).strip('"') if m else None


def kind_of(line):
    """A record's kind: its mission type and council type without their prefixes."""
    return '%s/%s' % ((field(line, 'MissionType') or '').replace('eMission_', ''),
                      (field(line, 'CouncilType') or 'eFCMType_None').replace('eFCMType_', ''))


def records(game):
    text = (Path(game) / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini').read_text(encoding='latin-1')
    return [line for line in text.splitlines() if re.match(r'\s*\+?Maps\s*=', line)]


def package(game, name):
    for folder in (Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole', Path(game) / 'XComGame' / 'CookedPCConsole'):
        path = folder / (name + '.upk')
        if path.is_file():
            return path
    return None


def survey(path):
    """{placed: {class: count}, kismet: {class: count}} of one package."""
    sys.path.insert(0, str(HERE))
    import upkinfo as U
    b, h = U.load(str(path))
    _, imps, exps = U.tables(b, h)
    placed, kismet = collections.Counter(), collections.Counter()
    for n, e in enumerate(exps):
        cls = U.clsname(e['cls'], imps, exps)
        if cls.startswith(('Seq', 'XComSeq', 'InterpData')):
            kismet[cls] += 1
        elif U.objname(n + 1, imps, exps).startswith(LEVEL) and U.objname(n + 1, imps, exps).count('.') == 2:
            placed[cls] += 1
    return dict(placed=dict(sorted(placed.items())), kismet=dict(sorted(kismet.items())))


def census(game, progress=lambda text: None):
    streams, bases = {}, {}
    for line in records(game):
        name, kind = field(line, 'Name'), kind_of(line)
        bases.setdefault(name, set()).add(kind)
        for stream in re.findall(r'MapName="([^"]+)"', line):
            if not stream.lower().startswith(SKIPPED):
                streams.setdefault(stream, set()).add('%s on %s' % (kind, name))
    out = dict(streams={}, bases={})
    for part, found, key in (('streams', streams, 'usedBy'), ('bases', bases, 'kinds')):
        for name, used in sorted(found.items()):
            path = package(game, name)
            try:
                result = survey(path) if path else dict(missing=True)
            except Exception as error:  # noqa: BLE001
                result = dict(error=repr(error))
            out[part][name] = dict({key: sorted(used)}, **result)
            progress('%s %s' % (part, name))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('game', help='the game install (the folder with XEW in it)')
    parser.add_argument('out', help='the JSON file to write')
    args = parser.parse_args(argv)
    result = census(args.game, progress=lambda text: print(text, flush=True))
    Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    print('%d streams, %d base maps -> %s' % (len(result['streams']), len(result['bases']), args.out))


if __name__ == '__main__':
    main()
