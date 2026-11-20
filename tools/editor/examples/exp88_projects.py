"""EXP-88's projects: the review fixes of 20 November 2026 played in the game (branch editor-review-fixes).

- walls (URB_Bar, check 1, review finding 36): three one-storey made walls in the car park (its cars and vans deleted,
  as in EXP-84), along x at y -1152 on the lot, each in a group that breaks together with:
  A: x -2016 to -1632, a copy of the ATM XComDestructibleActor_4 standing against its north face at x -1777;
  B: x -1344 to -864, two copies of the trash can XComDestructibleActor_0 against its north face, at its west tile
     (x -1297) and its east tile (x -913);
  C: x -672 to -288, a high cover block over the tile north of its third tile (x -577 to -481, y -1152 to -1056).
  Walls are copies of URB_Bar's inside wall XComDecoFracLevelActor_17 as the editor's tools make them.
- mouse (URB_HighwayFallen, check 2, finding 37): a copy of the sedan wreck XComDestructibleActor_80 with its glass
  XComFracLevelActor_14 (one assembly), 480 south of the original (-581, -3164), "Mouse picks it" off on both.
- farm (CsmallScout_Farm, checks 3 and 4, findings 37 and 44): PointLight_5's falloff exponent 2 -> 12,
  PointLight_6 switched off, and the tractor XComDestructibleActor_153 moved five tiles east, (-1, -1) -> (479, -1).
  Built with the lighting baked: a quick build leaves a changed light's pool baked as it was (build.QUICK_LIGHTS).
Game tiles on URB_Bar count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp88_projects.py walls|mouse|farm --store <projects folder> --builds <builds folder> [--build] [--quick]

The projects are saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages a build into the lab copy). The game and the cache are the settings'; each map must have been
exported into that cache."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'bake'))
import build  # noqa: E402
import compiler  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
LOT = 0.0
WALL_Y = -1152.0


def target(package, name):
    return dict(package=package, level='base', actor=PL + name)


def by_actor(scene):
    return {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}


def copy_of(scene, package, name, location, rotation, **extra):
    o = by_actor(scene)[PL + name]
    return dict(components=[o['component']], location=location, rotation=rotation,
                **{'from': target(package, name)}, **extra)


def lot_deletes(scene, package, box):
    """Delete records for the cars and vans standing in `box` (x0, x1, y0, y1), each assembly whole."""
    objs = by_actor(scene)
    out = []
    for pivot, a in sorted(compiler.assemblies(scene, package).items()):
        if a.get('family') not in ('car', 'van') or pivot not in objs:
            continue
        x, y = objs[pivot]['location'][:2]
        if box[0] <= x <= box[1] and box[2] <= y <= box[3]:
            out += [dict(target=dict(package=package, level='base', actor=m), deleted=True) for m in a['members']]
    return sorted(out, key=lambda r: r['target']['actor'])


def walls(scene):
    """URB_Bar: three walls, each grouped (Break together) with its props or its cover block."""
    m = 'URB_Bar'
    donor = 'XComDecoFracLevelActor_17'
    out, groups = [], []

    def wall(label, x0, length, seed):
        gen = dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=length, openings=[], seed=seed, storeys=1))
        out.append((label, copy_of(scene, m, donor, [x0, WALL_Y, LOT], [0, 0, 0], generated=gen)))
    # the ATM's box is y 0 to 90 from its pivot (rotation 0): 22 puts it 10 off the wall's north face (12)
    wall('A wall', -2016.0, 384.0, 881)
    out.append(('A ATM', copy_of(scene, m, 'XComDestructibleActor_4', [-1777.0, WALL_Y + 22.0, LOT], [0, 0, 0])))
    # the trash can's box is y -19 to 19: 35 puts it 4 off the face
    wall('B wall', -1344.0, 480.0, 882)
    out.append(('B can west', copy_of(scene, m, 'XComDestructibleActor_0', [-1297.0, WALL_Y + 35.0, LOT], [0, 0, 0])))
    out.append(('B can east', copy_of(scene, m, 'XComDestructibleActor_0', [-913.0, WALL_Y + 35.0, LOT], [0, 0, 0])))
    wall('C wall', -672.0, 384.0, 883)
    out.append(('C block', dict(template=dict(kind='cover', version=2),
                                cover=dict(type='high', size=[96.0, 96.0], heights=[-12.0, 96.0]),
                                location=[-576.0, WALL_Y, LOT], rotation=[0, 0, 0])))
    records = []
    for k, (label, f) in enumerate(out):
        stem = f['from']['actor'].split('.')[-1] if 'from' in f else 'CoverBlock'
        # (a cover block names no prefab or partner: it copies no piece)
        records.append(dict(id='00000000-0000-4000-8000-0000000e88%02d' % (k + 1), actor=PL + '%s_copy%d' % (stem, k + 1),
                            **(dict(prefab=None, partner=None) if 'from' in f else {}), **f))
    actor = {label: r['actor'] for (label, _), r in zip(out, records)}
    for k, (letter, members) in enumerate((('A', ['A wall', 'A ATM']), ('B', ['B wall', 'B can west', 'B can east']),
                                           ('C', ['C wall', 'C block']))):
        groups.append(dict(id='00000000-0000-4000-8000-0000000e88a%d' % (k + 1), locked=True, breakTogether=True,
                           members=[dict(added=actor[x]) for x in members]))
    return dict(map=m, id='00000000-0000-4000-8000-0000000e8801', name='EXP-88 wall groups',
                overrides=lot_deletes(scene, m, (-2112.0, 1440.0, -1536.0, -288.0)), added=records, groups=groups,
                labels=[label for label, _ in out], view=dict(camera=[-1100, 1400, -2600], target=[-1100, 0, -1100]))


def mouse(scene):
    """URB_HighwayFallen: a copy of a sedan wreck (body and glass) with "Mouse picks it" off."""
    m = 'URB_HighwayFallen'
    objs = by_actor(scene)
    pivot = PL + 'XComDestructibleActor_80'
    members = compiler.assemblies(scene, m)[pivot]['members']
    records, labels = [], []
    for k, member in enumerate(members):
        o = objs[member]
        name = member.split('.')[-1]
        records.append(dict(id='00000000-0000-4000-8000-0000000e88%02d' % (k + 11), actor=PL + '%s_copy%d' % (name, k + 1),
                            prefab=None, partner=None, components=[o['component']],
                            location=[o['location'][0], o['location'][1] - 480.0, o['location'][2]],
                            rotation=list(o['rotation']), flags=dict(mouse=False), **{'from': target(m, name)}))
        labels.append(name + ' copy (mouse off)')
    return dict(map=m, id='00000000-0000-4000-8000-0000000e8802', name='EXP-88 mouse off copy', overrides=[],
                added=records, groups=[], labels=labels, view=dict(camera=[-581, 1400, -3800], target=[-581, 448, -2900]))


def farm(scene):
    """CsmallScout_Farm: one point light's falloff changed, another switched off, the tractor moved five tiles east."""
    m = 'CsmallScout_Farm'
    objs = by_actor(scene)
    tractor = objs[PL + 'XComDestructibleActor_153']
    overrides = [dict(target=target(m, 'PointLight_5'), light=dict(falloffExponent=12.0)),
                 dict(target=target(m, 'PointLight_6'), light=dict(enabled=False)),
                 dict(target=target(m, 'XComDestructibleActor_153'),
                      location=[tractor['location'][0] + 480.0, tractor['location'][1], tractor['location'][2]],
                      rotation=list(tractor['rotation']))]
    return dict(map=m, id='00000000-0000-4000-8000-0000000e8803', name='EXP-88 farm lights and shadow',
                overrides=overrides, added=[], groups=[],
                labels=['PointLight_5 falloff 12', 'PointLight_6 off', 'tractor +480 x'],
                view=dict(camera=[700, 1600, 1200], target=[700, 0, -200]))


MAKERS = dict(walls=walls, mouse=mouse, farm=farm)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('which', choices=sorted(MAKERS))
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--build', action='store_true')
    a.add_argument('--quick', action='store_true', help='with --build: without baking')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    # the map's export: the maker needs the scene before it knows its map, so each maker names one
    m = dict(walls='URB_Bar', mouse='URB_HighwayFallen', farm='CsmallScout_Farm')[args.which]
    base = build.lwr_file(game, 'CookedPCConsole', m + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=m, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    print('base map %s (SHA-256 %s), export %s' % (base.name, sha[:12], export.parent.name))
    made = MAKERS[args.which](scene)
    store = projects.ProjectStore(args.store)
    project_id, name = made['id'], made['name']
    try:
        current = store.load(project_id)
    except projects.ProjectError:
        current = None
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']
    else:
        claims = outputnames.Claims(store.root, str(args.builds), [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, m))
        output.pop('reason', None)
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=m, package=m + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=made['overrides'], added=made['added'], groups=made['groups'], buildings=[],
               nextSerial=len(made['added']) + 1, view=made['view'])
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    print('notes', json.dumps([(w['code'], w['message'][:200]) for w in report['notes']], indent=1))
    if report.get('groups'):
        print('groups', json.dumps(report['groups']))
    _, native = compiler.native_split(compiler.stream_only(spec))
    for c in native.get('copies') or []:
        print('  %-44s at %-24s %s%s%s' % (c['label'], [round(v) for v in c['location']], (c.get('generated') or {}).get('kind', ''),
                                           ' flags %s' % c['flags'] if c.get('flags') else '',
                                           ''.join(' %s %s' % (k, c[k]) for k in ('breakGroup', 'wallGroup') if c.get(k))))
    for c in native.get('covers') or []:
        print('  cover %s at %s breakGroup %s' % (c.get('name'), c.get('location'), c.get('breakGroup')))
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    print('pieces:', ', '.join(made['labels']))
    if not args.build:
        return
    try:
        result = build.Build(store.path(project_id), s['cache'], args.builds, game, s['udk'], quick=args.quick).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: result.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
