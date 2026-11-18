"""Inventory of the spawn-related actors in every map and streamed level a game install's DefaultMaps.ini names:
soldier start points and landing zones, alien pods, alien (drop-in) spawn points, Meld spawn points, wave systems and
the Kismet actions that spawn aliens. Read-only; made for private/plans/todo/editor-spawns-plan.md.

  python -B tools/upk/audit_spawns.py <game install> <out.json> [--jobs 6] [--detail]
  python -B tools/upk/audit_spawns.py <game install> <out.json> --values [--jobs 6]

Per package: whether a record names it as a base map or as a stream, the actors of each class placed in its level,
and tallies of the properties that decide what an editor can do with them (tags, unit types, archetypes, the pods'
flags and references). --detail adds every such actor with its saved properties (large). The install's
DefaultLZMutator.ini (Long War's landing zones), where it has one, is counted per map.

--values (export 33; private/plans/todo/editor-spawns-implementation-plan.md, SP1) runs the editor's own reader
(tools/viewer/scene_metadata.spawn_metadata) over every base map instead: the effective values and where each came
from, the links and uses, tallied, with every actor it could not read listed by map, so the reader is proved over the
whole install before the page depends on it.
"""
import argparse
import collections
import json
import multiprocessing
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PLACED = ('PlayerStart', 'XComSpawnPoint', 'XComSpawnPoint_Alien', 'XComAlienPod', 'XComAlienPod_Abduction',
          'XComAlienPod_Terror', 'XComAlienPod_Hunter', 'XComMeldContainerSpawnPoint', 'XComAlienPathNode',
          'XComWaveSystem', 'XComNoSpawnVolume', 'XComAlienSpawnVolume', 'XComCapturePointVolume')
KISMET = ('SeqAct_SpawnAlien', 'SeqAct_SpawnReinforcement', 'SeqAct_SpawnCivilian', 'SeqAct_SpawnUnit',
          'SeqAct_RespawnAlienPod')
LEVEL = 'TheWorld.PersistentLevel.'


def numbered(text):
    return re.sub(r'\d+', 'N', text)


def survey(job):
    path, detail = job
    sys.path.insert(0, HERE)
    import upkinfo as U
    import props as P
    name = Path(path).stem
    try:
        b, h = U.load(path)
        names, imps, exps = U.tables(b, h)
    except Exception as error:  # noqa: BLE001
        return name, dict(error=repr(error))
    counts, kismet, tallies, actors = collections.Counter(), collections.Counter(), collections.Counter(), []
    for n, e in enumerate(exps):
        cls = U.clsname(e['cls'], imps, exps)
        if cls in KISMET:
            kismet[cls] += 1
            continue
        if cls not in PLACED:
            continue
        full = U.objname(n + 1, imps, exps)
        if not full.startswith(LEVEL) or full.count('.') != 2:
            continue    # an archetype's copy outside the level, or a component
        counts[cls] += 1
        try:
            saved, _ = P.read_props(b, P.props_start(b, e, names), e['off'] + e['size'], names, imps, exps)
            saved = [str(p) for p in saved]
        except Exception as error:  # noqa: BLE001
            saved = ['error ' + repr(error)]
        values = {p.split('[')[0]: p.split(' = ', 1)[-1] for p in saved}
        arch = U.objname(e['arch'], imps, exps) if e['arch'] else None
        if cls == 'XComSpawnPoint':
            tallies['XComSpawnPoint UnitType ' + values.get('UnitType', '(default: soldier)')] += 1
            tallies['XComSpawnPoint Tag ' + numbered(values.get('Tag', '(none)'))] += 1
            tallies['XComSpawnPoint archetype ' + (numbered(arch.split('.')[-1]) if arch else '(none)')] += 1
        elif cls == 'XComMeldContainerSpawnPoint':
            tallies['Meld m_iSpawnGroup ' + values.get('m_iSpawnGroup', '0')] += 1
            tallies['Meld m_eDifficulty ' + values.get('m_eDifficulty', '(default: easy)').split('_')[-1]] += 1
        elif cls == 'PlayerStart':
            tallies['PlayerStart archetype ' + (numbered(arch.split('.')[-1]) if arch else '(none)')] += 1
        for key in values:
            if cls.startswith('XComAlienPod') or cls == 'XComSpawnPoint_Alien':
                tallies['%s saves %s' % ('pod' if cls.startswith('XComAlienPod') else 'alien point', key)] += 1
        if detail:
            actors.append(dict(actor=full[len(LEVEL):], cls=cls, archetype=arch, properties=saved))
    out = dict(counts=dict(counts), kismet=dict(kismet), tallies=dict(tallies))
    if detail:
        out['actors'] = actors
    return name, out


def value_survey(path):
    """The editor's reader over one base map (--values): per kind counts, every unread actor, and tallies of the
    values (with where each came from), links and uses that decide what the editor can do with the points."""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'viewer'))
    from package import Package
    import scene_metadata
    name = Path(path).stem
    warnings = []
    try:
        p = Package(path)
        landings = scene_metadata.landing_metadata(p, lambda s, m: warnings.append('%s: %s' % (s, m)))
        records = scene_metadata.spawn_metadata(p, landings, lambda s, m: warnings.append('%s: %s' % (s, m)))
    except Exception as error:  # noqa: BLE001
        return name, dict(error=repr(error))
    kinds, tallies, unread, odd = collections.Counter(), collections.Counter(), [], []
    for r in records:
        kinds[r['kind']] += 1
        short = r['actor'].rsplit('.', 1)[-1]
        if 'unread' in r:
            unread.append(dict(actor=short, why=r['unread']))
        if r['listed'] is False:
            odd.append('%s not in the level list' % short)
        family = r['kind'] if r['kind'] in ('pod', 'meld', 'dropIn') else 'point' if r['actorClass'] == 'XComSpawnPoint' else None
        for key, v in r.get('values', {}).items():
            value = v['value']
            if key in ('podIndex', 'aliensMin', 'aliensMax', 'seekRadius'):
                value = 'n' if isinstance(value, (int, float)) else value
            tallies['%s %s=%s (%s)' % (family, key, value, v['from'])] += 1
        for link in r.get('links', []):
            tallies['%s links %s' % (r['kind'], link['property'])] += 1
        for use in r.get('uses', []):
            tallies['%s used %s%s' % (r['kind'], use['how'], ' ' + use['byClass'] if 'byClass' in use else '')] += 1
        for other in r.get('other', []):
            tallies['%s saves %s' % (r['actorClass'], other)] += 1
        if r['based']:
            tallies['%s based' % r['kind']] += 1
    pods = [r['values'].get('podIndex', {}).get('value') for r in records if r['kind'] == 'pod']
    if len(pods) != len(set(pods)):
        odd.append('pod indices repeat: %s' % sorted(pods, key=str))
    return name, dict(kinds=dict(kinds), unread=unread, odd=odd, warnings=warnings, tallies=dict(tallies))


def values_main(a, base, files):
    names = sorted({n.lower() for n in base} & set(files))
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        found = dict(pool.imap_unordered(value_survey, [str(files[n]) for n in names], chunksize=2))
    tallies, kinds = collections.Counter(), collections.Counter()
    for entry in found.values():
        tallies.update(entry.get('tallies', {}))
        kinds.update(entry.get('kinds', {}))
    summary = dict(maps=len(found), errors=sorted(n for n, e in found.items() if 'error' in e),
                   unread=sum(len(e.get('unread', [])) for e in found.values()),
                   withOddities=sorted(n for n, e in found.items() if e.get('odd')),
                   kinds=dict(kinds.most_common()), tallies=dict(sorted(tallies.items())))
    Path(a.out).write_text(json.dumps(dict(scope='every base map named by a live DefaultMaps.ini record, read by the '
                                                 "editor's spawn reader (scene_metadata.spawn_metadata, export 33)",
                                           summary=summary, maps={n: found[n] for n in sorted(found, key=str.lower)}),
                                      indent=1) + '\n', encoding='utf-8', newline='\n')
    print('%d base maps read, %d not, %d actors unread, %d maps with oddities'
          % (len(found), len(summary['errors']), summary['unread'], len(summary['withOddities'])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=6); ap.add_argument('--detail', action='store_true')
    ap.add_argument('--values', action='store_true', help="the editor's spawn reader over every base map instead")
    a = ap.parse_args()
    config = Path(a.install) / 'XEW' / 'XComGame' / 'Config'
    base, streams = set(), set()
    for line in (config / 'DefaultMaps.ini').read_bytes().decode('latin-1').splitlines():
        if line.lstrip().startswith(';'):
            continue
        base.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
        streams.update(re.findall(r'MapName="([^"]+)"', line))
    zones = collections.Counter()
    lz = config / 'DefaultLZMutator.ini'
    if lz.is_file():
        for line in lz.read_bytes().decode('latin-1').splitlines():
            m = re.match(r'\s*LZArray=\(MapName="([^"]+)"', line)
            if m:
                zones[m.group(1).lower()] += 1
    files = {p.stem.lower(): p for p in (Path(a.install) / 'XEW' / 'XComGame' / 'CookedPCConsole').glob('*.upk')}
    if a.values:
        values_main(a, base, files)
        return
    wanted = {n.lower() for n in base | streams}
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        found = dict(pool.imap_unordered(survey, [(str(files[n]), a.detail) for n in sorted(wanted) if n in files],
                                         chunksize=2))
    base_low = {n.lower() for n in base}
    packages, totals = {}, dict(base=collections.Counter(), stream=collections.Counter())
    holders = dict(base=collections.Counter(), stream=collections.Counter())
    tallies = dict(base=collections.Counter(), stream=collections.Counter())
    for name in sorted(found, key=str.lower):
        role = 'base' if name.lower() in base_low else 'stream'
        entry = dict(role=role, **found[name])
        if role == 'base' and lz.is_file():
            entry['landingZones'] = zones.get(name.lower(), 0)
        packages[name] = entry
        for cls, n in {**entry.get('counts', {}), **entry.get('kismet', {})}.items():
            totals[role][cls] += n
            holders[role][cls] += 1
        tallies[role].update(entry.get('tallies', {}))
        if not a.detail:
            entry.pop('tallies', None)
    summary = {role: dict(packages=sum(1 for e in packages.values() if e['role'] == role),
                          actors={cls: dict(actors=n, packages=holders[role][cls]) for cls, n in totals[role].most_common()},
                          tallies=dict(sorted(tallies[role].items())))
               for role in ('base', 'stream')}
    if lz.is_file():
        summary['landingZones'] = dict(entries=sum(zones.values()),
                                       baseMapsWith=sum(1 for n in base_low if zones.get(n)),
                                       baseMapsWithout=sorted(n for n, e in packages.items()
                                                              if e['role'] == 'base' and not e.get('landingZones')))
    missing = sorted(n for n in base | streams if n.lower() not in files)
    Path(a.out).write_text(json.dumps(dict(scope='every base map and stream named by a live DefaultMaps.ini record',
                                           missingPackages=missing, summary=summary, packages=packages), indent=1) + '\n',
                           encoding='utf-8', newline='\n')
    print('%d packages (%d base maps, %d streams), %d named but not found'
          % (len(packages), summary['base']['packages'], summary['stream']['packages'], len(missing)))


if __name__ == '__main__':
    main()
