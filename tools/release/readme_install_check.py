"""Install a variant package by following its README.txt alone, as a modder would, into a scratch copy of a game
install's config, and check that the result reads back as a playable map (preview checklist item 2, the M1
acceptance's last step). It reads the README, never the manifest, so a step the README leaves out fails here.

  python tools/release/readme_install_check.py <package folder> <game install> <scratch folder>

The scratch folder gets XEW\\XComGame\\Config (copies of the install's DefaultMaps.ini, DefaultLZMutator.ini,
DefaultMiniMods.ini and DefaultRandomSpawns.ini where it has them) and XEW\\XComGame\\CookedPCConsole (the package's files only); the install is
only read. Steps, each as the README words it:
1. copy the files it lists into CookedPCConsole;
2. add its DefaultMaps.ini records at the end of the [XComGame.XComMapManager] list, its landing-zone lines beside the
   base map's, its mini-mod rules beside the base map's, its drop-in exclusion line (a project that leaves scripted
   drop-ins where placed) after the drop-in section's ExcludeMaps lines;
3. its "By hand" step: set bInRotation=True on the variant's records, and False on the base map's own.
Then it checks: every file the README lists is there; each added record is the variant's, well formed, and streams
only packages that are in the scratch CookedPCConsole or the install's; the editor's own map list (maplist) reads the
variant with the base map's missions; the landing zones match the base map's; after step 3, the variant's records are
in rotation and the base map's are not. Prints what it did; exit 1 on the first failed check.
"""
import re
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'viewer'))
import maplist  # noqa: E402
import spawnrules  # noqa: E402

FIELD = lambda name: re.compile(r'(?<![A-Za-z])%s="([^"]*)"' % name)  # noqa: E731


def fail(message):
    print('FAILED: %s' % message)
    raise SystemExit(1)


def sections(readme):
    """The README's file list and its config blocks: {files: [...], DefaultMaps.ini: [...], ...}."""
    lines = readme.replace('\r\n', '\n').split('\n')
    out, current = {'files': []}, None
    for line in lines:
        if line.startswith('Files: copy the contents of CookedPCConsole'): current = 'files'; continue
        match = re.match(r'(Default\w+\.ini)[,:]', line)
        if match and ('nothing to add' not in line): current = match.group(1); out.setdefault(current, []); continue
        if match: current = None; continue
        if not line.strip(): current = None if current != 'files' or out['files'] else current; continue
        if current == 'files' and line.startswith('  '): out['files'].append(line.strip())
        elif current and current != 'files': out[current].append(line)
    return out


def insert_after_last(lines, predicate, new):
    last = max((i for i, l in enumerate(lines) if predicate(l)), default=None)
    if last is None: fail('nowhere to add %d lines: no line to put them beside' % len(new))
    return lines[:last + 1] + new + lines[last + 1:]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3: print(__doc__.split('\n\n')[1]); return 2
    package, game, scratch = map(Path, argv)
    readme = (package / 'README.txt').read_bytes().decode('latin-1')
    s = sections(readme)
    variant = readme.split(':', 1)[0].strip()
    base = re.search(r'a variant of (\S+)', readme.split('\n', 1)[0]).group(1)
    print('package %s: %s, a variant of %s; %d files, %s' % (package.name, variant, base, len(s['files']),
                                                            ', '.join('%s %d lines' % (k, len(v)) for k, v in s.items() if k != 'files')))
    config, cooked = scratch / 'XEW' / 'XComGame' / 'Config', scratch / 'XEW' / 'XComGame' / 'CookedPCConsole'
    if scratch.exists(): shutil.rmtree(scratch)
    config.mkdir(parents=True); cooked.mkdir(parents=True)
    source = Path(game) / 'XEW' / 'XComGame'
    for name in ('DefaultMaps.ini', 'DefaultLZMutator.ini', 'DefaultMiniMods.ini', 'DefaultRandomSpawns.ini'):
        if (source / 'Config' / name).is_file(): shutil.copyfile(source / 'Config' / name, config / name)
    # 1. the files
    for name in s['files']:
        if not (package / 'CookedPCConsole' / name).is_file(): fail('the README lists %s, which the package lacks' % name)
        shutil.copyfile(package / 'CookedPCConsole' / name, cooked / name)
    shipped = {p.name for p in (package / 'CookedPCConsole').iterdir()}
    if shipped != set(s['files']): fail('the package has files the README does not list: %s' % sorted(shipped - set(s['files'])))
    print('1. copied %s' % ', '.join(s['files']))
    # 2. the config lines
    def read(name): return (config / name).read_bytes().decode('latin-1').replace('\r\n', '\n').split('\n')
    def write(name, lines): (config / name).write_bytes('\r\n'.join(lines).encode('latin-1'))
    records = s.get('DefaultMaps.ini') or fail('the README gives no DefaultMaps.ini records')
    maps = read('DefaultMaps.ini')
    start = maps.index('[XComGame.XComMapManager]')
    end = next((i for i in range(start + 1, len(maps)) if maps[i].startswith('[')), len(maps))
    section = insert_after_last(maps[start:end], lambda l: l.lstrip().startswith('Maps=('), records)
    write('DefaultMaps.ini', maps[:start] + section + maps[end:])
    for name, key in (('DefaultLZMutator.ini', 'MapName="%s"' % base), ('DefaultMiniMods.ini', 'Map="%s")' % base)):
        if name not in s: continue
        if not (config / name).is_file(): fail('the README adds to %s, which the install has not' % name)
        write(name, insert_after_last(read(name), lambda l, k=key: k in l and not l.lstrip().startswith(';'), s[name]))
    if 'DefaultRandomSpawns.ini' in s:
        if not (config / 'DefaultRandomSpawns.ini').is_file(): fail('the README adds to DefaultRandomSpawns.ini, which the install has not')
        rs = read('DefaultRandomSpawns.ini')
        head = '[%s]' % spawnrules.DROP_IN_SECTION
        if head not in rs: fail('DefaultRandomSpawns.ini has no %s section' % head)
        start = rs.index(head)
        end = next((i for i in range(start + 1, len(rs)) if rs[i].startswith('[')), len(rs))
        part = insert_after_last(rs[start:end], lambda l: re.match(r'\s*;*\s*ExcludeMaps\s*=', l), s['DefaultRandomSpawns.ini'])
        write('DefaultRandomSpawns.ini', rs[:start] + part + rs[end:])
    print('2. added %d records%s' % (len(records), ''.join(', %d lines to %s' % (len(s[n]), n) for n in s if n not in ('files', 'DefaultMaps.ini'))))
    # checks on what the README put in
    for record in records:
        if FIELD('Name').search(record).group(1) != variant: fail('a record is not the variant\'s: %s' % record[:120])
        if record.count('(') != record.count(')'): fail('a record\'s brackets do not close: %s' % record[:120])
        for stream in FIELD('MapName').findall(record):
            if not ((cooked / ('%s.upk' % stream)).is_file() or (source / 'CookedPCConsole' / ('%s.upk' % stream)).is_file()):
                fail('the variant streams %s, which neither the package nor the install has' % stream)
    text = (config / 'DefaultMaps.ini').read_bytes().decode('latin-1')
    listed = {r for r in maplist.live_records(text) if FIELD('Name').search(r) and FIELD('Name').search(r).group(1) == variant}
    if len(listed) != len(records): fail('the map list reads %d of the variant\'s %d records' % (len(listed), len(records)))
    # the base map's records: its live ones, or a switched-off map's commented-out ones (maplist.records)
    theirs = [maplist.mission_of(r)[2] for r in maplist.records(text) if FIELD('Name').search(r) and FIELD('Name').search(r).group(1) == base]
    ours = [maplist.mission_of(r)[2] for r in listed]
    if sorted(set(ours)) != sorted(set(theirs)): fail('the variant serves %s, the base map %s' % (sorted(set(ours)), sorted(set(theirs))))
    if 'DefaultLZMutator.ini' in s:
        lz = read('DefaultLZMutator.ini')
        mine = [l for l in lz if 'MapName="%s"' % variant in l and not l.lstrip().startswith(';')]
        base_zones = [l for l in lz if 'MapName="%s"' % base in l and not l.lstrip().startswith(';')]
        if len(mine) != len(base_zones): fail('%d landing zones for the variant, %d for the base map' % (len(mine), len(base_zones)))
    if 'DefaultRandomSpawns.ini' in s:
        found = spawnrules.random_spawns((config / 'DefaultRandomSpawns.ini').read_bytes())
        if not spawnrules.excluded(found['excludeMaps'], variant): fail('Long War\'s drop-in mutator does not read the variant as excluded')
        print('   checked: the drop-in mutator reads %s as excluded' % variant)
    print('   checked: the records are the variant\'s and read back (%s), their streams are there, the landing zones match'
          % ', '.join(sorted(set(ours))))
    # 3. the README's "By hand" rotation step
    if 'set bInRotation=True on the records' not in readme: fail('the README does not say how to put the variant in rotation')
    lines = read('DefaultMaps.ini')
    turned = 0
    for i, line in enumerate(lines):
        name = FIELD('Name').search(line).group(1) if line.lstrip().startswith('Maps=(') and FIELD('Name').search(line) else None
        if name in (variant, base):
            new = re.sub(r'(?<![A-Za-z])bInRotation=\w+', 'bInRotation=%s' % ('True' if name == variant else 'False'), line, count=1)
            turned += new != line
            lines[i] = new
    write('DefaultMaps.ini', lines)
    text = (config / 'DefaultMaps.ini').read_bytes().decode('latin-1')
    rotation = {(FIELD('Name').search(r).group(1), re.search(r'bInRotation=(\w+)', r).group(1))
                for r in maplist.live_records(text) if FIELD('Name').search(r) and FIELD('Name').search(r).group(1) in (variant, base)}
    # a switched-off base map (Act1_IntroLevel in LWR) has no live record to take out of rotation
    base_live = any(FIELD('Name').search(r) and FIELD('Name').search(r).group(1) == base for r in maplist.live_records(text))
    want = {(variant, 'True')} | ({(base, 'False')} if base_live else set())
    if rotation != want: fail('after the rotation step: %s' % sorted(rotation))
    print('3. in rotation instead of %s (%d records changed)' % (base, turned))
    print('passed: %s installs by its README alone' % variant)
    return 0


if __name__ == '__main__':
    sys.exit(main())
