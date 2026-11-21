"""Where a relight's time goes, inside its workers: relight.py run as it is, with timers round its parts (a research
tool for relight work; it does not ship).

  python -B tools/bake/relight_probe.py run --log <folder> -- <relight.py's arguments>
  python -B tools/bake/relight_probe.py report <folder> [--json <file>] [--top 12]
  python -B tools/bake/relight_probe.py replay <folder> [--relight-json <file>] [--workers 16]

`run` runs tools/bake/relight.py with the arguments after `--` (a Build's relight command, as its native-copy log
prints it; give it an output folder of its own and an empty piece cache, never a Build's). Every process, the main one
and each pool worker, appends one JSON line per timed call to <folder>/<pid>.jsonl: the function, its wall and CPU
seconds (CPU: every thread of the process), what it worked on, and the worker's job (its kind, piece, band, and for
a shadow map's job the shadow map). Nothing of the relight is changed: each timer calls the real function and hands
its result back. The workers are spawned processes: each imports this file as its main module and finds the folder
in the environment (RELIGHT_PROBE_LOG, which `run` sets), so the timers go on in them too.

`report` says what the logs hold: the workers' start (the map and both scenes), the jobs by kind, each piece's
preparation (how often it was paid, its parts), the band computations' parts, and each shadow map's job (its
component, its shadow map, its seconds and parts), slowest first.

`replay` plays the relight pool's clock again from the measured jobs, as relight.run_jobs hands them out (the shadow
maps first, then the pieces largest first, `--workers` workers), with what-ifs: a fresh piece's shadow maps of one
light but the last it lists not traced (a made piece that kept its donor's map before its own: follow-ups item 2.2;
needs the relight's record, `--relight-json`), the window search of the distance fields 4 times faster, and each
band's preparation paid once per piece.

The timed parts are listed in TIMED; a part the relight no longer has is reported at the start of `run` and left.
"""
import argparse
import collections
import functools
import heapq
import json
import os
from pathlib import Path
import statistics
import sys
import time

ENV = 'RELIGHT_PROBE_LOG'
CTX = dict(job=None, inside=[])
_out = [None]


# ------------------------------------------------------------------------------------------------------- the timers
def emit(rec):
    """One record into this process's log."""
    if _out[0] is None:
        folder = Path(os.environ[ENV])
        folder.mkdir(parents=True, exist_ok=True)
        _out[0] = open(folder / f'{os.getpid()}.jsonl', 'a', encoding='utf-8', newline='\n')
    rec.update(pid=os.getpid(), job=CTX['job'], inside=list(CTX['inside']))
    _out[0].write(json.dumps(rec, default=str) + '\n')
    _out[0].flush()


def short(path):
    """An export path's actor name (its second-last part), as the records name pieces."""
    return path.split('.')[-2] if isinstance(path, str) and '.' in path else str(path)


def last(path):
    return path.split('.')[-1] if isinstance(path, str) else str(path)


def n0(x):
    try:
        return int(len(x))
    except Exception:
        return None


def wrap(owner, name, info=None, label=None):
    """owner.name replaced by a timer round it that emits a record after each call (with `info(args, kwargs, result)`
    added). False where the owner has no such attribute."""
    real = getattr(owner, name, None)
    if real is None:
        return False
    label = label or name

    @functools.wraps(real)
    def wrapper(*a, **k):
        t0, c0 = time.perf_counter(), time.process_time()
        CTX['inside'].append(label)
        try:
            r = real(*a, **k)
        finally:
            CTX['inside'].pop()
        rec = dict(fn=label, wall=round(time.perf_counter() - t0, 4), cpu=round(time.process_time() - c0, 4))
        if info:
            try:
                rec.update(info(a, k, r))
            except Exception as error:      # the probe's own fault never stops the relight
                rec['infoError'] = repr(error)
        emit(rec)
        return r
    setattr(owner, name, wrapper)
    return True


def install():
    """The timers put on the relight's parts (in this process). Returns the parts that were not found."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import paths
    paths.use('bake', 'upk', 'viewer')
    import numpy as np
    import scipy.spatial
    import relight
    import bounce
    import lighting_records
    import lightmap_fields
    import lightmap_texels
    import shadowmaps
    import shadows

    real_job = relight._worker_job

    @functools.wraps(real_job)
    def _worker_job(job):
        kind, path = job[0], job[1]
        if kind == 'shadow':
            spec = job[4]
            CTX['job'] = dict(kind='shadow', path=short(spec.get('path')), fresh=bool(spec.get('fresh')),
                              copy=spec.get('source') is not None,
                              shadowMap=last((spec.get('sm') or {}).get('path')))
        else:
            CTX['job'] = dict(kind=kind, path=short(path), band=list(job[4:6]) if kind == 'band' else None,
                              fresh=bool(job[3]), copy=job[2] is not None)
        t0, c0 = time.perf_counter(), time.process_time()
        had = relight._WORKER.get('work')
        out = real_job(job)
        emit(dict(fn='JOB', wall=round(time.perf_counter() - t0, 4), cpu=round(time.process_time() - c0, 4),
                  reusedPrepared=bool(had and kind in ('band', 'assemble') and had[0] == (path, job[2], job[3])),
                  error=out.get('error')))
        CTX['job'] = None
        return out
    relight._worker_job = _worker_job

    def distance_info(a, k, r):
        g, light = a[0], a[1]
        transition = a[2] if len(a) > 2 else k.get('transition', shadowmaps.TRANSITION)
        only = a[3] if len(a) > 3 else k.get('only')
        return dict(shape=list(g['shape']), covered=int(g['covered'].sum()), reach=shadowmaps.reach_of(g, transition),
                    spacing=g['spacing'], only=None if only is None else int(np.count_nonzero(only)),
                    lit=int(np.count_nonzero(g['covered'] & light)))

    def prepared_info(a, k, r):
        rect = r['geo']['rect']
        return dict(path=short(a[1]), texels=n0(r['geo']['world']), inReach=n0(r['tidx']), gather=n0(r['gidx']),
                    rect=int((rect[2] - rect[0]) * (rect[3] - rect[1])), mode=r['mode'], buried=r['buried'])

    def shadow_info(a, k, r):
        sm = a[2]
        out = dict(path=short(a[0].name(a[1])), shadowMap=last(sm.get('path')))
        if r:
            x0, y0, x1, y1 = r['report']['rect']
            out.update(rect=[x0, y0, x1, y1], texels=int((x1 - x0) * (y1 - y0)))
        return out

    timed = [
        (relight, '_worker_start', None, 'worker_start (map + both scenes)'),
        (relight.Scene, '__init__', lambda a, k, r: dict(removes=len(k.get('remove_casters') or ()),
                                                          adds=len(k.get('add_casters') or ())), 'Scene.__init__'),
        (relight, 'prepare_component', prepared_info, None),
        (relight, 'compute_component', lambda a, k, r: dict(path=short(a[0]['path']), band=k.get('band')), None),
        (relight, 'assemble_component', lambda a, k, r: dict(path=short(a[1]['path'])), None),
        (relight, 'relight_component', lambda a, k, r: dict(path=short(a[1])), None),
        (relight, 'texel_reach', lambda a, k, r: dict(n=n0(a[0]), inReach=int(np.count_nonzero(r))), None),
        (relight, 'texel_size', lambda a, k, r: dict(n=n0(a[0]['world'])), None),
        (relight, 'direct_coefficients', lambda a, k, r: dict(n=n0(r)), None),
        (relight, 'gather_coefficients', lambda a, k, r: dict(n=n0(a[2])), None),
        (relight, 'smooth_indirect', lambda a, k, r: dict(n=n0(r[0])), None),
        (relight, 'shadow_map_job', None, None),
        (lighting_records, 'component_record', None, None),
        (lightmap_fields, 'component_fields', None, None),
        (lightmap_fields, 'texture_fields', None, None),
        (lightmap_texels, 'component_mesh', None, None),
        (lightmap_texels, 'rasterise', lambda a, k, r: dict(size=list(a[3]), n=n0(r['world'])), None),
        (lightmap_texels, 'dilate', None, None),
        (bounce, 'buried_texels', lambda a, k, r: dict(n=n0(a[1]), buried=int(np.count_nonzero(r))), None),
        (bounce, 'gather', lambda a, k, r: dict(n=n0(a[4])), None),
        (bounce, 'smooth', lambda a, k, r: dict(n=n0(a[3])), None),
        (shadows, 'light_visibility', lambda a, k, r: dict(n=n0(a[2]), samples=k.get('samples')), None),
        (shadows.Occluder, '__init__', lambda a, k, r: dict(n=n0(a[1])), 'Occluder.__init__ (Embree scene)'),
        (shadows.Occluder, 'blocked', lambda a, k, r: dict(rays=n0(a[1])), 'Occluder.blocked'),
        (shadowmaps, 'texture_top', None, None),
        (shadowmaps, 'sub_samples', lambda a, k, r: dict(n=n0(r['world']), rect=list(r['rect'])), None),
        (shadowmaps, 'lit', lambda a, k, r: dict(n=n0(r), lit=int(np.count_nonzero(r))), None),
        (shadowmaps, 'grid', lambda a, k, r: dict(shape=list(r['shape']), spacing=r['spacing']), None),
        (shadowmaps, 'signed_distance', distance_info, None),
        (shadowmaps, 'field', None, None),
        (shadowmaps, 'change', None, None),
        (shadowmaps, 'relight_shadow_map', shadow_info, None),
        (shadowmaps, 'fresh_shadow_map', shadow_info, None),
    ]
    missing = [f'{getattr(owner, "__name__", owner)}.{name}' for owner, name, info, label in timed
               if not wrap(owner, name, info, label)]

    real_tree = scipy.spatial.cKDTree

    class TimedTree:
        """cKDTree, its making and its queries timed."""

        def __init__(self, data, *a, **k):
            t0, c0 = time.perf_counter(), time.process_time()
            self._t = real_tree(data, *a, **k)
            emit(dict(fn='cKDTree build', wall=round(time.perf_counter() - t0, 4),
                      cpu=round(time.process_time() - c0, 4), n=n0(data)))

        def query(self, x, *a, **k):
            t0, c0 = time.perf_counter(), time.process_time()
            r = self._t.query(x, *a, **k)
            emit(dict(fn='cKDTree query', wall=round(time.perf_counter() - t0, 4),
                      cpu=round(time.process_time() - c0, 4), n=n0(x)))
            return r

        def __getattr__(self, name):
            return getattr(self._t, name)

    scipy.spatial.cKDTree = TimedTree
    return relight, missing


# (a spawned worker imports this file as its main module: the timers go on in it too)
if __name__ == '__mp_main__' and os.environ.get(ENV):
    install()


def run(log, relight_args):
    """relight.py's main with the timers on, its records in `log`. Returns its exit code."""
    os.environ[ENV] = str(Path(log).resolve())
    relight, missing = install()
    if missing:
        print('relight_probe: not in the relight any more, not timed: ' + ', '.join(missing))
    sys.argv = [str(Path(relight.__file__))] + list(relight_args)
    t0 = time.perf_counter()
    code = 0
    try:
        relight.main()
    except SystemExit as stop:
        code = stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
    emit(dict(fn='MAIN', wall=round(time.perf_counter() - t0, 3), cpu=round(time.process_time(), 3), exit=code))
    return code


# ---------------------------------------------------------------------------------------------------------- report
def load(folder):
    """{pid: [records]} from a run's log folder."""
    out = {}
    for f in sorted(Path(folder).glob('*.jsonl')):
        out[f.stem] = [json.loads(line) for line in f.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not out:
        raise SystemExit(f'no probe records in {folder}')
    return out


def attribute(records, parent):
    """Each `parent` call with the records nested in it (those emitted while it ran, in the same process)."""
    out, buf = [], []
    for r in records:
        if r['fn'] == parent and parent not in r['inside']:
            out.append((r, buf))
            buf = []
        elif parent in r['inside']:
            buf.append(r)
    return out


def parts_of(children, depth):
    """{fn: [wall, cpu, calls]} of the records one level below a parent at `depth`."""
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for c in children:
        if len(c['inside']) == depth + 1:
            a = acc[c['fn']]
            a[0] += c['wall']
            a[1] += c['cpu']
            a[2] += 1
    return acc


def summary(per_pid):
    """What a run's records say, as one dict (see the module's docstring)."""
    out = {}
    prep = collections.defaultdict(list)
    for pid, recs in per_pid.items():
        for rec, children in attribute(recs, 'prepare_component'):
            parts = parts_of(children, len(rec['inside']))
            prep[rec.get('path')].append(dict(
                pid=pid, wall=rec['wall'], cpu=rec['cpu'], texels=rec.get('texels'), rect=rec.get('rect'),
                mode=rec.get('mode'), job=rec.get('job'),
                parts={k: [round(v[0], 3), round(v[1], 3), v[2]] for k, v in parts.items()},
                buriedRays=sum(c.get('rays') or 0 for c in children if c['fn'] == 'Occluder.blocked')))
    rows = []
    for path, calls in prep.items():
        mean_cpu = statistics.mean(c['cpu'] for c in calls)
        parts = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
        for c in calls:
            for k, v in c['parts'].items():
                for j in range(3):
                    parts[k][j] += v[j] / len(calls)
        rows.append(dict(path=path, calls=len(calls), workers=len({c['pid'] for c in calls}),
                         byJobKind=dict(collections.Counter((c['job'] or {}).get('kind') for c in calls)),
                         rect=calls[0]['rect'], texels=calls[0]['texels'], mode=calls[0]['mode'],
                         meanWall=round(statistics.mean(c['wall'] for c in calls), 3), meanCpu=round(mean_cpu, 3),
                         totalCpu=round(sum(c['cpu'] for c in calls), 2),
                         repeatedCpu=round(sum(c['cpu'] for c in calls) - mean_cpu, 2),
                         buriedRays=calls[0]['buriedRays'],
                         partsMean={k: [round(v[0], 3), round(v[1], 3), round(v[2], 1)]
                                    for k, v in sorted(parts.items(), key=lambda x: -x[1][1])}))
    rows.sort(key=lambda r: -r['totalCpu'])
    out['prepare'] = rows
    banded = [r for r in rows if r['byJobKind'].get('band')]
    out['prepareSummary'] = dict(pieces=len(rows), calls=sum(r['calls'] for r in rows),
                                 cpu=round(sum(r['totalCpu'] for r in rows), 1), bandedPieces=len(banded),
                                 bandedCalls=sum(r['calls'] for r in banded),
                                 bandedCpu=round(sum(r['totalCpu'] for r in banded), 1),
                                 bandedRepeatedCpu=round(sum(r['repeatedCpu'] for r in banded), 1))
    jobs, starts, reused = collections.defaultdict(lambda: [0, 0.0, 0.0]), [], collections.Counter()
    for pid, recs in per_pid.items():
        for r in recs:
            if r['fn'] == 'JOB':
                k = r['job']['kind']
                jobs[k][0] += 1
                jobs[k][1] += r['wall']
                jobs[k][2] += r['cpu']
                if k in ('band', 'assemble'):
                    reused[(k, r['reusedPrepared'])] += 1
            elif r['fn'].startswith('worker_start'):
                starts.append(r)
            elif r['fn'] == 'MAIN':
                out['main'] = {k: r[k] for k in ('wall', 'cpu', 'exit') if k in r}
    out['jobs'] = {k: dict(count=v[0], wall=round(v[1], 1), cpu=round(v[2], 1)) for k, v in sorted(jobs.items())}
    out['bandOrAssembleReusingPrepared'] = {f'{k} reused={b}': n for (k, b), n in sorted(reused.items())}
    out['workerStarts'] = dict(count=len(starts), wall=round(sum(s['wall'] for s in starts), 1),
                               cpu=round(sum(s['cpu'] for s in starts), 1),
                               each=sorted(round(s['wall'], 2) for s in starts))
    sp = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for pid, recs in per_pid.items():
        for rec, children in attribute(recs, 'worker_start (map + both scenes)'):
            for k, v in parts_of(children, 0).items():
                for j in range(3):
                    sp[k][j] += v[j]
    out['workerStartParts'] = {k: [round(v[0], 1), round(v[1], 1), v[2]] for k, v in sp.items()}
    sm = []
    for pid, recs in per_pid.items():
        for parent in ('fresh_shadow_map', 'relight_shadow_map'):
            for rec, children in attribute(recs, parent):
                parts = parts_of(children, len(rec['inside']))
                sd = [c for c in children if c['fn'] == 'signed_distance']
                sm.append(dict(kind='fresh' if parent == 'fresh_shadow_map' else 'change', path=rec.get('path'),
                               shadowMap=rec.get('shadowMap'), rect=rec.get('rect'), texels=rec.get('texels'),
                               wall=rec['wall'], cpu=rec['cpu'],
                               rays=sum(c.get('rays') or 0 for c in children if c['fn'] == 'Occluder.blocked'),
                               subSamples=[c.get('n') for c in children if c['fn'] == 'lit'],
                               distance=[{k: c.get(k) for k in ('wall', 'cpu', 'shape', 'covered', 'lit', 'reach',
                                                                'only')} for c in sd],
                               parts={k: [round(v[0], 3), round(v[1], 3), v[2]]
                                      for k, v in sorted(parts.items(), key=lambda x: -x[1][1])}))
    sm.sort(key=lambda r: -r['cpu'])
    out['shadowMaps'] = sm
    out['shadowSummary'] = dict(
        maps=len(sm), fresh=sum(1 for s in sm if s['kind'] == 'fresh'), cpu=round(sum(s['cpu'] for s in sm), 1),
        wall=round(sum(s['wall'] for s in sm), 1), freshCpu=round(sum(s['cpu'] for s in sm if s['kind'] == 'fresh'), 1),
        distanceCpu=round(sum(d['cpu'] for s in sm for d in s['distance']), 1),
        litCpu=round(sum(s['parts'].get('lit', [0, 0])[1] for s in sm), 1),
        subSamplesCpu=round(sum(s['parts'].get('sub_samples', [0, 0])[1] for s in sm), 1),
        rays=sum(s['rays'] for s in sm))
    comp = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for pid, recs in per_pid.items():
        for rec, children in attribute(recs, 'compute_component'):
            for k, v in parts_of(children, len(rec['inside'])).items():
                for j in range(3):
                    comp[k][j] += v[j]
            comp['(compute_component itself)'][0] += rec['wall']
            comp['(compute_component itself)'][1] += rec['cpu']
            comp['(compute_component itself)'][2] += 1
    out['computeParts'] = {k: [round(v[0], 1), round(v[1], 1), v[2]] for k, v in comp.items()}
    return out


def report_lines(s, top=12):
    """`summary`'s dict as lines to read."""
    out = ['main %s' % json.dumps(s.get('main')), 'jobs %s' % json.dumps(s['jobs']),
           'band/assemble reusing the prepared work: %s' % json.dumps(s['bandOrAssembleReusingPrepared']),
           'worker starts %s' % json.dumps(s['workerStarts']),
           'worker start parts (wall, cpu, calls) %s' % json.dumps(s['workerStartParts']),
           'prepare summary %s' % json.dumps(s['prepareSummary'])]
    for r in s['prepare'][:top]:
        out.append('  %s %s rect %s texels %s calls %d workers %d %s mean cpu %s wall %s repeated cpu %s' % (
            r['path'], r['mode'], r['rect'], r['texels'], r['calls'], r['workers'], json.dumps(r['byJobKind']),
            r['meanCpu'], r['meanWall'], r['repeatedCpu']))
        out.append('     parts (wall, cpu, calls): %s' % json.dumps(r['partsMean']))
    out.append('compute parts (wall, cpu, calls) %s' % json.dumps(s['computeParts']))
    out.append('shadow maps %s' % json.dumps(s['shadowSummary']))
    for m in s['shadowMaps'][:top]:
        out.append('  %s %s %s rect %s (%s texels) wall %s cpu %s rays %s' % (
            m['kind'], m['path'], m['shadowMap'], m['rect'], m['texels'], m['wall'], m['cpu'], m['rays']))
        out.append('     parts %s' % json.dumps(m['parts']))
    return out


# ---------------------------------------------------------------------------------------------------------- replay
def measured_jobs(per_pid):
    """The jobs as measured: dict(job, wall, prep (its preparation's wall), distance (its window searches' wall))."""
    out = []
    for pid, recs in per_pid.items():
        pending = {}
        for r in recs:
            if r['fn'] == 'prepare_component' and r['job'] and r['job']['kind'] in ('band', 'assemble'):
                pending['prep'] = r['wall']
            if r['fn'] == 'signed_distance' and r['job']:
                pending['distance'] = pending.get('distance', 0.0) + r['wall']
            if r['fn'] == 'JOB':
                out.append(dict(job=r['job'], wall=r['wall'], prep=pending.get('prep', 0.0),
                                distance=pending.get('distance', 0.0)))
                pending = {}
    return out


def schedule(walls, workers):
    """List scheduling in queue order: when the last job ends."""
    free = [0.0] * workers
    heapq.heapify(free)
    end = 0.0
    for w in walls:
        t = heapq.heappop(free) + w
        end = max(end, t)
        heapq.heappush(free, t)
    return end


def second_maps(relit):
    """{(piece, shadow map)} of the relight record `relit`'s fresh shadow maps where a piece lists more than one of
    one light: all but the last listed (the record lists them in the piece's own order, and a made piece's own map
    was added after the donor's it kept: frac_walls.add_shadow_ref)."""
    by = collections.defaultdict(list)
    for s in relit.get('shadowMaps') or []:
        if s.get('fresh'):
            by[(short(s['component']), s.get('light'))].append(last(s['shadowMap']))
    return {(piece, name) for (piece, _), maps in by.items() for name in maps[:-1]}


def replay(per_pid, workers=16, relit=None):
    """The pool's clock replayed (see the module's docstring): dict of the measured and what-if ends."""
    jobs = measured_jobs(per_pid)
    shadow = [j for j in jobs if j['job']['kind'] == 'shadow']
    pieces = sorted((j for j in jobs if j['job']['kind'] != 'shadow'), key=lambda j: -j['wall'])
    seconds = second_maps(relit) if relit else set()

    def queue(drop_seconds=False, faster=1.0, prep_once=False):
        out, seen_band = [], set()
        for j in shadow:
            if drop_seconds and (j['job']['path'], j['job'].get('shadowMap')) in seconds:
                continue
            out.append(j['wall'] - j['distance'] + j['distance'] / faster)
        for j in pieces:
            w = j['wall']
            if prep_once and j['job']['kind'] == 'band':
                if j['job']['path'] in seen_band:
                    w -= j['prep']
                seen_band.add(j['job']['path'])
            out.append(w)
        return out
    rows = dict(workers=workers, jobs=len(jobs), summed=round(sum(j['wall'] for j in jobs), 1),
                shadowJobs=len(shadow), shadowSummed=round(sum(j['wall'] for j in shadow), 1),
                asRun=round(schedule(queue(), workers), 1),
                distance4x=round(schedule(queue(faster=4.0), workers), 1),
                prepareOnce=round(schedule(queue(prep_once=True), workers), 1),
                longestJob=round(max((j['wall'] for j in jobs), default=0.0), 1))
    if relit is not None:
        rows['secondMaps'] = sorted('%s.%s' % x for x in seconds)
        rows['secondMapsSummed'] = round(sum(j['wall'] for j in shadow
                                             if (j['job']['path'], j['job'].get('shadowMap')) in seconds), 1)
        rows['noSecondMaps'] = round(schedule(queue(drop_seconds=True), workers), 1)
    return rows


def main(argv=None):
    a = argparse.ArgumentParser(prog='relight_probe.py', description=__doc__.split('\n\n')[0],
                                epilog=__doc__.split('\n\n', 1)[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = a.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='relight.py with its timers on')
    r.add_argument('--log', type=Path, required=True, help='the folder the records go to (one file per process)')
    r.add_argument('relight', nargs=argparse.REMAINDER, help='-- then relight.py\'s arguments')
    rp = sub.add_parser('report', help='what a run\'s records say')
    rp.add_argument('log', type=Path)
    rp.add_argument('--json', type=Path, help='the whole summary written here too')
    rp.add_argument('--top', type=int, default=12, help='the slowest pieces and shadow maps listed')
    rr = sub.add_parser('replay', help='the pool\'s clock replayed, with what-ifs')
    rr.add_argument('log', type=Path)
    rr.add_argument('--relight-json', type=Path, help='the relight\'s record (<out>/<variant>.relight.json)')
    rr.add_argument('--workers', type=int, default=16)
    args = a.parse_args(argv)
    if args.command == 'run':
        rest = args.relight[1:] if args.relight[:1] == ['--'] else args.relight
        if not rest:
            a.error('run: relight.py\'s arguments follow --')
        return run(args.log, rest)
    per_pid = load(args.log)
    if args.command == 'report':
        s = summary(per_pid)
        if args.json:
            args.json.write_text(json.dumps(s, indent=1) + '\n', encoding='utf-8', newline='\n')
        print('\n'.join(report_lines(s, args.top)))
        return 0
    relit = json.loads(args.relight_json.read_text(encoding='utf-8')) if args.relight_json else None
    print(json.dumps(replay(per_pid, args.workers, relit), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
