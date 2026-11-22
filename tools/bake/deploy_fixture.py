"""Put a lighting fixture (lighting_fixture.py output) into the lab copy's test slot, and put the slot back after.

deploy:
- copies <variant>.upk and the variant texture cache into the lab's EW CookedPCConsole, never over a file this tool
  did not put there (its ledger is <work>/deployed.json), except one the lab's patchtool did (a patch in its
  deployed.txt, or a map whose bytes its seeded.txt last recorded: an earlier patchtool build of the same project),
  which is backed up first and listed in the deploy record's `replaced`;
- copies the base map's landing zones in LWR's DefaultLZMutator.ini under the variant's name, after the base map's
  lines, with a comment (unless lines for that name are there already; a base map with none, such as TempleShip, gets
  none);
- rewrites the test slot (the one uncommented Maps= line whose DisplayName the first mission loads) as the base map's
  record with the variant's Name, keeping the slot's DisplayName and eRegion, so the first mission of a new campaign
  plays the variant with the base map's streams and time of day. The first mission is an abduction: a base map of
  another kind (TempleShip's record is eMission_Final) plays as one, with the slot's map family, as patchtool's test
  slot played Temple in EXP-14;
- with --stream <patch> (repeatable), also streams that patch map in the slot line, in the lowest StreamingMaps slot
  the base record does not use, as patchtool's `"free"` slot does: an editor patch built with
  `compiler.py --stream-only` (its hider and copies) plays on the relit variant. The patch must be in the lab already
  (patchtool deploy) or among the fixture's outputs (an editor build's package, tools/lab/lab_install.py);
- with --seed-plan <plan.tsv> (repeatable; patchtool's `seed-plan-built.tsv` for a patch with `map.seedExternally`),
  deploys the variant map with that plan's tile seeds (`tools/upk/seed_map.py apply`), written to
  <work>/seeded/<variant>-<stamp>.upk first, so the patch's copies block and give cover on tiles the map left empty
  (F-29). The patch's XComMapEdTileSeeds actor rebuilds them at load;
- backs up both INI files first, checks that the new text differs only in the planned lines, and writes it byte for
  byte (CRLF kept);
- writes a deploy record with the old lines, for restore.

reset: writes the LWR install's own record for the test slot's DisplayName back in the slot (LWR's first mission,
URB_CommercialAlley_EWI), with a deploy record as deploy writes one, so restore undoes it and a later deploy chains to
it. The landing-zone lines and files earlier deploys added stay, harmless while no slot names them.

restore <deploy record>: puts the old test slot line back and takes out the landing-zone lines it added, after checking
they are still the ones it wrote. A deploy made over an earlier one records it as `previous`, and restore undoes the
chain, so one restore of the latest record gets back to the slot as it was before the first. The copied map and cache
stay (they are harmless until a slot names them).

Refuses to run unless the lab copy is the active install (its XComLab-copy.txt marker) and XCOM is closed.

The folders come from the settings (tools/lab/labpaths.py), read when first used: the game folder is the one Steam runs
(<Steam common>\\XCom-Enemy-Unknown, from the lwr setting), <work> is <lab>\\bake-fixtures and the lab's patchtool
work folder <lab>\\patchtool. Each function's game, work and patchtool arguments override them.

  python -B tools/bake/deploy_fixture.py deploy <out>/<variant>.fixture.json [--stream <patch>] [--seed-plan <tsv>]
      [--dry-run]
  python -B tools/bake/deploy_fixture.py reset <the LWR game folder> [--dry-run]
  python -B tools/bake/deploy_fixture.py restore <work>/deploys/<record>.json [--dry-run]
"""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'upk'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lab'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
import labpaths  # noqa: E402
import installs  # noqa: E402
# the game's config lines (tools/viewer/mapsini.py: the editor's installer reads and writes them the same way)
from mapsini import (EOL, FIRST_MISSION, add_stream, check_change, field, is_record, lines_of, plan_lz,  # noqa: E402,F401
                     set_field, slot_record, slot_streams, stream_slots, unquoted, write_checked)
import seed_map  # noqa: E402
import seed_tiles  # noqa: E402


def default_game():
    """The game folder Steam runs (the lab copy while it is active), from the settings."""
    return labpaths.active_game()


def default_work():
    """This tool's work folder: <lab>\\bake-fixtures."""
    return labpaths.lab_root() / 'bake-fixtures'


def default_patchtool():
    """The lab's patchtool work folder, for its deploy and seed ledgers: <lab>\\patchtool, or None without a lab."""
    return labpaths.configured('lab', 'patchtool')


def __getattr__(name):
    """GAME, WORK and PATCHTOOL: the defaults above, read from the settings when asked for."""
    lazy = dict(GAME=default_game, WORK=default_work, PATCHTOOL=default_patchtool)
    if name in lazy:
        return lazy[name]()
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


# the record a new campaign's first mission asks for by name, LWR's (installs.FIRST_MISSIONS: one home for the name)
TEST_SLOT = installs.FIRST_MISSIONS[0]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slot_index(lines, slot_name=TEST_SLOT):
    """The index of the test slot's line: the one record with the slot's DisplayName."""
    slots = [i for i, l in enumerate(lines) if is_record(l) and field(l, 'DisplayName') == slot_name]
    if len(slots) != 1:
        raise ValueError(f'expected one test slot line, found {len(slots)}')
    return slots[0]


def test_slot(game, slot_name=TEST_SLOT):
    """The test slot's line in a game folder's DefaultMaps.ini: in the lab, what the first mission plays; in the LWR
    install, LWR's own first mission."""
    lines = lines_of((Path(game) / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini').read_bytes())
    return lines[slot_index(lines, slot_name)]


def plan_maps(lines, base, variant, slot_name=TEST_SLOT, streams=(), replace=None):
    """The test slot's line made one of the base map's records (slot_record) under the variant's name, streaming
    `streams` in free slots, and with each stream in `replace` (old name -> new) streamed under its new name: a
    variant's own copy of the landing intro (tools/bake/intro_copy.py, F-45). A replacement the record doesn't stream
    is left out (another record of the map lands by the other intro); a `replace` the record streams none of is an
    error."""
    slot = slot_index(lines, slot_name)
    bases = [i for i, l in enumerate(lines) if is_record(l) and field(l, 'Name') == base]
    if not bases:
        raise ValueError(f'no record for {base}')
    old = lines[slot]
    new = set_field(lines[slot_record(lines, bases)], 'Name', variant)
    new = set_field(new, 'DisplayName', slot_name)
    region = unquoted(old, 'eRegion')
    if region:
        new = set_field(new, 'eRegion', region, quoted=False)
    if unquoted(new, 'MissionType') != FIRST_MISSION:
        # another kind of map (TempleShip, eMission_Final) as the first mission's abduction, as EXP-14 played it; the
        # base map's own record stays the only one of its kind in rotation
        new = set_field(new, 'MissionType', FIRST_MISSION, quoted=False)
        family = field(old, 'MapFamily')
        if family:
            new = set_field(new, 'MapFamily', family)
    for patch in streams:
        new, _ = add_stream(new, patch)
    present = {was: now for was, now in (replace or {}).items() if f'MapName="{was}"'.encode() in new}
    if replace and not present:
        raise ValueError(f'the record streams none of {", ".join(replace)} to replace')
    for was, now in present.items():
        new = new.replace(f'MapName="{was}"'.encode(), f'MapName="{now}"'.encode())
    return slot, old, new


def game_running(game=None):
    """Whether XCOM: Enemy Within is running: one look at the process table (tools/viewer/procs.py), as the editor's
    install step asks it; with `game` (an install's folder), only that install's game (another copy's may run beside,
    T-52)."""
    viewer = str(Path(__file__).resolve().parents[1] / 'viewer')
    if viewer not in sys.path:
        sys.path.append(viewer)
    import procs
    return procs.running('XComEW.exe', game)


def checks(game):
    if not (game / 'XComLab-copy.txt').exists():
        raise SystemExit('the active install is not the lab copy (no XComLab-copy.txt); refusing')
    if game_running(game):
        raise SystemExit('XCOM is running; close it first')


def unused(path):
    """path, or path with -2, -3, ... before its suffix: the first that does not exist (two deploys in one second)."""
    k, out = 2, path
    while out.exists():
        out = path.with_name(f'{path.stem}-{k}{path.suffix}')
        k += 1
    return out


def backup(path, work, stamp):
    dst = unused(work / 'backups' / f'{path.name}.{stamp}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def seed_variant(src, dst, plans):
    """A copy of the variant map at dst with the plans' tile seeds; returns the seeder's report line."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        seed_map.apply(str(src), str(dst), [str(p) for p in plans], seed_tiles.SEED_DEFAULT)
    return out.getvalue().strip()


def patchtool_owns(dst, patchtool=None):
    """Whether the lab's patchtool put this game file there: a patch it deployed (its ledger deployed.txt names it), or
    a map it last seeded with exactly these bytes (seeded.txt: time, map, patch, tiles, SHA-256 of the map)."""
    patchtool = default_patchtool() if patchtool is None else patchtool
    if patchtool is None:
        return False
    name = Path(dst).stem
    deployed = Path(patchtool) / 'deployed.txt'
    if deployed.exists() and name in deployed.read_text(encoding='utf-8', errors='replace').split():
        return True
    seeded = Path(patchtool) / 'seeded.txt'
    if seeded.exists():
        rows = [l.split('\t') for l in seeded.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
        mine = [r for r in rows if len(r) >= 5 and r[1].lower() == name.lower()]
        if mine and mine[-1][4].strip().lower() == sha256(dst):
            return True
    return False


def previous_record(work, slot_at, old_slot):
    """The deploy record whose slot line is the one about to be replaced, if any: restore undoes the chain."""
    previous = None
    for rec in sorted((work / 'deploys').glob('*.json')) if (work / 'deploys').exists() else []:
        prior = json.loads(rec.read_text(encoding='utf-8'))
        if prior.get('testSlotLine') == slot_at + 1 and prior.get('testSlotNew') == old_slot.decode('latin1'):
            previous = str(rec)
    return previous


def deploy(manifest_path, game=None, work=None, dry=False, now=None, streams=(), seed_plans=(), patchtool=None,
           replace_streams=None):
    """Deploy a fixture manifest (a path, or the manifest itself: variant, source, outputs). `replace_streams` (old
    name -> new) streams the variant's own copy of a stream in its place (plan_maps)."""
    game = default_game() if game is None else Path(game)
    work = default_work() if work is None else Path(work)
    m = manifest_path if isinstance(manifest_path, dict) else json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    variant, base = m['variant'], Path(m['source']).stem
    cooked = game / 'XEW' / 'XComGame' / 'CookedPCConsole'
    config = game / 'XEW' / 'XComGame' / 'Config'
    maps_path, lz_path = config / 'DefaultMaps.ini', config / 'DefaultLZMutator.ini'
    stamp = (now or datetime.datetime.now()).strftime('%Y%m%d-%H%M%S')
    ledger_path = work / 'deployed.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}

    copies, replaces = [], []
    for src, digest in m['outputs'].items():
        src = Path(src)
        if sha256(src) != digest:
            raise ValueError(f'{src} changed since the fixture was built')
        dst = cooked / src.name
        if dst.exists() and ledger.get(str(dst)) != sha256(dst):
            # a file of the lab's patchtool (an earlier patchtool build of the same project) is replaced, backed up
            # first; any other file is never overwritten
            if not patchtool_owns(dst, patchtool):
                raise ValueError(f'{dst} exists and was not put there by this tool or patchtool')
            replaces.append(dst)
        copies.append((src, dst, digest))
    copied = {dst.name.lower() for _, dst, _ in copies}
    for patch in list(streams) + list((replace_streams or {}).values()):
        if f'{patch}.upk'.lower() not in copied and not (cooked / f'{patch}.upk').exists():
            raise ValueError(f'{cooked / patch}.upk is missing; deploy the patch first (patchtool deploy)')
    seed_plans = [Path(s) for s in seed_plans]
    missing = [str(s) for s in seed_plans if not s.exists()]
    if missing:
        raise ValueError(f'no seed plan {missing}')
    map_copy = [k for k, (src, _, _) in enumerate(copies) if src.name.lower() == f'{variant}.upk'.lower()]
    if seed_plans and len(map_copy) != 1:
        raise ValueError(f'the fixture has no {variant}.upk to seed')

    maps = lines_of(maps_path.read_bytes())
    lz = lines_of(lz_path.read_bytes())
    slot_at, old_slot, new_slot = plan_maps(maps, base, variant, streams=streams, replace=replace_streams)
    lz_at, lz_new = plan_lz(lz, base, variant, f'bake fixture, {stamp[:8]}')
    previous = previous_record(work, slot_at, old_slot)
    plan = dict(variant=variant, base=base, copies=[(str(s), str(d)) for s, d, _ in copies],
                testSlotLine=slot_at + 1, testSlotOld=old_slot.decode('latin1'),
                testSlotNew=new_slot.decode('latin1'), lzInsertAt=None if lz_at is None else lz_at + 1,
                lzLines=[l.decode('latin1') for l in lz_new], streams=list(streams),
                replaceStreams=dict(replace_streams or {}),
                seedPlans=[str(s) for s in seed_plans], previous=previous,
                replaces=[str(d) for d in replaces])
    if dry:
        return plan

    checks(game)
    if seed_plans:
        k = map_copy[0]
        src, dst, _ = copies[k]
        seeded = unused(work / 'seeded' / f'{variant}-{stamp}.upk')
        report = seed_variant(src, seeded, seed_plans)
        copies[k] = (seeded, dst, sha256(seeded))
        plan['seeded'] = dict(file=str(seeded), sha256=copies[k][2], report=report)
        plan['copies'] = [(str(s), str(d)) for s, d, _ in copies]
    plan['backups'] = [str(backup(maps_path, work, stamp)), str(backup(lz_path, work, stamp))]
    # patchtool's files this replaces, kept (restore leaves the copied files, as it always has; these put them back)
    plan['replaced'] = {str(d): str(backup(d, work, stamp)) for d in replaces}
    for src, dst, digest in copies:
        shutil.copyfile(src, dst)
        if sha256(dst) != digest:
            raise ValueError(f'{dst} copy differs')
        ledger[str(dst)] = digest
    new_maps = list(maps)
    new_maps[slot_at] = new_slot
    check_change(maps, new_maps, replaced=[slot_at])
    write_checked(maps_path, new_maps)
    if lz_new:
        new_lz = lz[:lz_at] + lz_new + lz[lz_at:]
        check_change(lz, new_lz, inserted=(lz_at, len(lz_new)))
        write_checked(lz_path, new_lz)
    work.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=1) + '\n', encoding='utf-8', newline='\n')
    record = unused(work / 'deploys' / f'{variant}-{stamp}.json')
    record.parent.mkdir(parents=True, exist_ok=True)
    plan['record'] = str(record)
    plan['configHashesAfter'] = {str(maps_path): sha256(maps_path), str(lz_path): sha256(lz_path)}
    record.write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8', newline='\n')
    return plan


def reset(lwr, game=None, work=None, dry=False, now=None, slot_name=TEST_SLOT):
    """Write the LWR install's own record for the test slot (LWR's first mission) back in the lab's slot, with a
    deploy record. None when the slot holds that line already."""
    game = default_game() if game is None else Path(game)
    work = default_work() if work is None else Path(work)
    default = test_slot(lwr, slot_name)
    maps_path = game / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini'
    maps = lines_of(maps_path.read_bytes())
    at = slot_index(maps, slot_name)
    old = maps[at]
    if old == default:
        return None
    stamp = (now or datetime.datetime.now()).strftime('%Y%m%d-%H%M%S')
    plan = dict(variant=None, base=field(default, 'Name'), reset=str(lwr), copies=[], testSlotLine=at + 1,
                testSlotOld=old.decode('latin1'), testSlotNew=default.decode('latin1'), lzInsertAt=None, lzLines=[],
                streams=[], replaceStreams={}, seedPlans=[], previous=previous_record(work, at, old), replaces=[])
    if dry:
        return plan
    checks(game)
    plan['backups'] = [str(backup(maps_path, work, stamp))]
    new_maps = list(maps)
    new_maps[at] = default
    check_change(maps, new_maps, replaced=[at])
    write_checked(maps_path, new_maps)
    record = unused(work / 'deploys' / f'default-{stamp}.json')
    record.parent.mkdir(parents=True, exist_ok=True)
    plan['record'] = str(record)
    plan['configHashesAfter'] = {str(maps_path): sha256(maps_path)}
    record.write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8', newline='\n')
    return plan


def restore(record_path, game=None, dry=False, chain=True):
    """Undo one deploy; with chain, also the deploys before it that this one replaced in the test slot."""
    game = default_game() if game is None else Path(game)
    r = json.loads(Path(record_path).read_text(encoding='utf-8'))
    done = [_restore_one(r, game, dry)]
    while chain and r.get('previous'):
        r = json.loads(Path(r['previous']).read_text(encoding='utf-8'))
        if dry:
            done.append(dict(testSlotLine=r['testSlotLine'], lzLinesRemoved=len(r['lzLines']), chained=True))
            continue
        done.append(_restore_one(r, game, dry))
    return done


def _restore_one(r, game, dry):
    config = game / 'XEW' / 'XComGame' / 'Config'
    maps_path, lz_path = config / 'DefaultMaps.ini', config / 'DefaultLZMutator.ini'
    maps = lines_of(maps_path.read_bytes())
    lz = lines_of(lz_path.read_bytes())
    k = r['testSlotLine'] - 1
    if maps[k].decode('latin1') != r['testSlotNew']:
        raise ValueError(f'DefaultMaps.ini line {k + 1} is no longer the line deploy wrote; restore it by hand from '
                         f'{r.get("backups")}')
    new_maps = list(maps)
    new_maps[k] = r['testSlotOld'].encode('latin1')
    check_change(maps, new_maps, replaced=[k])
    new_lz = None
    if r['lzLines']:
        at = r['lzInsertAt'] - 1
        want = [l.encode('latin1') for l in r['lzLines']]
        if lz[at:at + len(want)] != want:
            raise ValueError('the landing-zone lines deploy added have moved or changed; take them out by hand')
        new_lz = lz[:at] + lz[at + len(want):]
        check_change(lz, new_lz, removed=(at, len(want)))
    if dry:
        return dict(testSlotLine=k + 1, lzLinesRemoved=len(r['lzLines']))
    checks(game)
    write_checked(maps_path, new_maps)
    if new_lz is not None:
        write_checked(lz_path, new_lz)
    return dict(testSlotLine=k + 1, lzLinesRemoved=len(r['lzLines']))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('action', choices=['deploy', 'reset', 'restore'])
    a.add_argument('file', type=Path, help='deploy: the fixture manifest; reset: the LWR game folder; restore: a deploy record')
    a.add_argument('--stream', action='append', default=[], metavar='PATCH',
                   help='deploy: also stream this patch map (already in the lab) in a free slot of the test slot line')
    a.add_argument('--seed-plan', action='append', default=[], metavar='TSV',
                   help="deploy: seed the variant map with this plan (patchtool's seed-plan-built.tsv)")
    a.add_argument('--dry-run', action='store_true')
    args = a.parse_args()
    if (args.stream or args.seed_plan) and args.action != 'deploy':
        a.error('--stream and --seed-plan are for deploy')
    if args.action == 'deploy':
        result = deploy(args.file, dry=args.dry_run, streams=args.stream, seed_plans=args.seed_plan)
    elif args.action == 'reset':
        result = reset(args.file, dry=args.dry_run) or "the test slot holds LWR's own record already"
    else:
        result = restore(args.file, dry=args.dry_run)
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
