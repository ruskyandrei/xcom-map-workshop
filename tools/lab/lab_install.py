"""Install the editor's variant packages (tools/editor/build.py) in our lab copy's test slot, to test them in the game.

This is our own lab step, kept out of the editor's build: a modder installs a package as its README says, or uses it
some other way. Here a package plays as the first mission of a new campaign, as the lighting fixtures did (EXP-17).
Until 9 November 2026 the editor's Project menu ran the same install (Install as intro map); its Play in game now
starts the game on a map by name instead (tools/viewer/play.py, EXP-29), and the test slot is this tool's alone
(deploy_fixture.py reset puts LWR's own first mission back).

  python -B tools/lab/lab_install.py install [<package folder>] [--dry-run]
  python -B tools/lab/lab_install.py watch [--every 10] [--pending]
  python -B tools/lab/lab_install.py status
  python -B tools/lab/lab_install.py uninstall <deploy record> [--dry-run]

- install: the given package, or else the newest package in the builds folder that is new (its manifest's buildId is
  not in the ledger, <work>/installed-builds.json). It is tools/bake/deploy_fixture.py's deploy with the package's
  files: they are copied into the lab's CookedPCConsole (never over a file the lab tools did not put there); the test
  slot becomes one of the base map's records (its abduction where it has one: deploy_fixture.slot_record) under the
  variant's name, with the package's patch streamed in a free slot and its own copy of the landing intro streamed in
  place of the original (the manifest's replaceStreams, F-45); the
  base map's landing zones are copied under the variant's name. The package's map is relit and seeded by the build,
  so no seed plan is applied here. Each file's hash is checked against the manifest first.
- watch: looks every few seconds for a package built since it started and installs the newest (`--pending` also
  takes the new packages that were there already). While XCOM runs, or the lab copy isn't
  the active install, it waits. A package that fails to install is recorded with the error and not tried again;
  building the project again gives a new buildId.
- status: the last installs and the test slot's map.
- uninstall: deploy_fixture.py restore of an install's deploy record (the record named in the ledger), which also
  undoes the deploys it replaced.

The builds folder is the editor's settings' output folder (tools/viewer/settings.py), or --builds. The lab copy and
the work folder are deploy_fixture's, from the same settings (tools/lab/labpaths.py).
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'bake'))
sys.path.insert(0, str(TOOLS / 'viewer'))
import deploy_fixture  # noqa: E402

SCHEMA = 'xcom-map-workshop/variant-package'


def ledger_path(work):
    return Path(work) / 'installed-builds.json'


def read_ledger(work):
    path = ledger_path(work)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def write_ledger(work, ledger):
    path = ledger_path(work)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(ledger, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def read_package(folder):
    folder = Path(folder)
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if m.get('schema') != SCHEMA:
        raise ValueError(f'{folder} is not a variant package (schema {m.get("schema")!r})')
    return m


def packages(builds):
    """(manifest, folder) of every finished package in the builds folder, oldest build first."""
    found = []
    for manifest in Path(builds).glob('*/manifest.json'):
        if manifest.parent.name.startswith('.'):
            continue
        try:
            found.append((read_package(manifest.parent), manifest.parent))
        except (OSError, ValueError) as error:
            print(f'skipping {manifest.parent}: {error}')
    return sorted(found, key=lambda mf: mf[0].get('builtAt') or '')


def fixture(m, folder):
    """The package as deploy_fixture's manifest: the variant, its base map (by name) and its files with hashes."""
    outputs = {}
    for rel, digest in m['files'].items():
        path = Path(folder) / rel
        if not path.is_file():
            raise ValueError(f'{path} is missing')
        if deploy_fixture.sha256(path) != digest:
            raise ValueError(f'{path} differs from its manifest')
        outputs[str(path)] = digest
    return dict(variant=m['variant'], source=f'{m["source"]["map"]}.upk', outputs=outputs)


def install(folder, game=None, work=None, dry=False, now=None):
    game = deploy_fixture.default_game() if game is None else Path(game)
    work = deploy_fixture.default_work() if work is None else Path(work)
    m = read_package(folder)
    plan = deploy_fixture.deploy(fixture(m, folder), game=game, work=work, dry=dry, now=now, streams=m['streams'],
                                 replace_streams=m.get('replaceStreams') or {})
    if not dry:
        ledger = read_ledger(work)
        ledger[m['buildId']] = dict(package=str(folder), project=m['project'], variant=m['variant'],
                                    record=plan['record'], installedAt=(now or datetime.datetime.now()).isoformat(timespec='seconds'))
        write_ledger(work, ledger)
    return m, plan


def new_packages(builds, work):
    ledger = read_ledger(work)
    return [(m, f) for m, f in packages(builds) if m['buildId'] not in ledger]


def ready(game):
    """None when the lab can take an install, else why not."""
    if not (Path(game) / 'XComLab-copy.txt').exists():
        return 'the lab copy is not the active install'
    if deploy_fixture.game_running(game):
        return 'XCOM is running'
    return None


def watch(builds, every, game=None, work=None, once=False, pending=True):
    """Install new packages as they come; with pending False, only those built after the watch starts."""
    game = deploy_fixture.default_game() if game is None else Path(game)
    work = deploy_fixture.default_work() if work is None else Path(work)
    waiting = None
    there = set() if pending else {m['buildId'] for m, _ in new_packages(builds, work)}
    print(f'watching {builds} every {every:g} s for new packages' +
          (f' (leaving the {len(there)} already there; --pending takes them too)' if there else ''))
    while True:
        new = [(m, f) for m, f in new_packages(builds, work) if m['buildId'] not in there]
        if new:
            why = ready(game)
            if why:
                if why != waiting:
                    print(f'{len(new)} new package(s); waiting: {why}')
                    waiting = why
            else:
                waiting = None
                m, folder = new[-1]
                try:
                    _, plan = install(folder, game=game, work=work)
                    print(f'{datetime.datetime.now():%H:%M:%S} installed {m["buildId"]} ({m["project"]["name"]}, '
                          f'revision {m["project"]["revision"]}): the test slot plays {m["variant"]} with '
                          f'{", ".join(m["streams"]) or "no patch"}'
                          + ''.join(f', {new} for {old}' for old, new in (m.get('replaceStreams') or {}).items())
                          + f'; deploy record {plan["record"]}')
                except (OSError, ValueError, SystemExit) as error:
                    ledger = read_ledger(work)
                    ledger[m['buildId']] = dict(package=str(folder), failed=str(error),
                                                at=datetime.datetime.now().isoformat(timespec='seconds'))
                    write_ledger(work, ledger)
                    print(f'{m["buildId"]} failed to install: {error}')
                ledger = read_ledger(work)
                for older, f in new[:-1]:      # builds overtaken by a newer one before they were installed
                    ledger.setdefault(older['buildId'], dict(package=str(f), superseded=m['buildId']))
                write_ledger(work, ledger)
        if once:
            return
        time.sleep(every)


def status(work, game=None):
    game = deploy_fixture.default_game() if game is None else Path(game)
    ledger = read_ledger(work)
    for build, entry in sorted(ledger.items(), key=lambda kv: kv[1].get('installedAt') or kv[1].get('at') or '')[-5:]:
        state = ('installed ' + entry['installedAt']) if 'installedAt' in entry else (
            'failed: ' + entry['failed'] if 'failed' in entry else 'superseded by ' + entry.get('superseded', '?'))
        print(f'{build}: {state}')
    maps = deploy_fixture.lines_of((Path(game) / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini').read_bytes())
    slot = [l for l in maps if deploy_fixture.is_record(l) and deploy_fixture.field(l, 'DisplayName') == deploy_fixture.TEST_SLOT]
    if slot:
        line = slot[0]
        print('test slot:', deploy_fixture.field(line, 'Name'), 'streams',
              [s.decode('latin1') for s in __import__('re').findall(rb'MapName="([^"]+)"', line)])


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('action', choices=['install', 'watch', 'status', 'uninstall'])
    a.add_argument('target', nargs='?', type=Path, help='install: a package folder; uninstall: a deploy record')
    a.add_argument('--builds', type=Path, help="the builds folder (default: the editor settings' output folder)")
    a.add_argument('--every', type=float, default=10.0, help='watch: seconds between looks (default %(default)g)')
    a.add_argument('--pending', action='store_true',
                   help='watch: also install new packages that were in the builds folder before it started')
    a.add_argument('--dry-run', action='store_true')
    args = a.parse_args(argv)
    if args.builds is None:
        import settings
        args.builds = settings.load_settings()['output']
    if args.action == 'install':
        folder = args.target
        if folder is None:
            new = new_packages(args.builds, deploy_fixture.default_work())
            if not new:
                print(f'no new package in {args.builds}')
                return 0
            folder = new[-1][1]
        m, plan = install(folder, dry=args.dry_run)
        print(json.dumps(dict(buildId=m['buildId'], **plan), indent=1))
    elif args.action == 'watch':
        try:
            watch(args.builds, args.every, pending=args.pending)
        except KeyboardInterrupt:
            pass
    elif args.action == 'status':
        status(deploy_fixture.default_work())
    else:
        if args.target is None:
            a.error('uninstall needs the deploy record')
        print(json.dumps(deploy_fixture.restore(args.target, dry=args.dry_run), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
