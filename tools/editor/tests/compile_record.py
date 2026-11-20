"""Every compile of the editor suite, recorded: what a refactor step of the compiler must leave as it was (the editor
refactor plan, stage 0.2).

`record` runs the editor suite's test files (tools/editor/tests/test_*.py, as run_tests.py finds them) in one process
with compiler.compile_project and compiler.native_split wrapped, and writes, for each call in order: the test that
made it, a hash of its inputs (the document, the scene, the families enabled and the families switched off, the kind
of library) and its outputs whole as sorted JSON (a compile: its spec, its report and the native split of its spec; a
native split a test or the Build makes itself: the patch spec and the native edit). The wrappers are put in place
before any test file is imported, so the test files that import the names themselves (from compiler import
compile_project) reach them too; a test that puts a stand-in of its own in their place (test_build's) makes no call
to record while it does.

  python -B tools/editor/tests/compile_record.py record --out <file> [-k PATTERN]
  python -B tools/editor/tests/compile_record.py compare <before file> <after file>

`compare` gives, for each test whose calls differ, the first differing call with the differing keys, and exits 1.
What a test makes fresh each run is masked (MASKS lists it). The record is the gate of a move, not a test: records
are not checked in, and run_tests.py does not run this. A stage records on its base (in a scratch worktree of that
commit, since a tool checks the code of the checkout it runs in) and on its head, and compares the two.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDITOR = HERE.parent
REPO = EDITOR.parents[1]
sys.path.insert(0, str(HERE))
from build_outputs import differing_keys  # noqa: E402
FORMAT = 1
# What a test makes fresh each run, masked: two records of one commit differ in these and nothing else (the tool's
# own check, with --no-masks). Only in the inputs: no output of a compile holds them. No folder (temporary or the
# checkout's) is in any call, so none is masked; a folder that came into one later would show as a difference.
INPUT_KEYS = ('lightGuid', 'lightmapGuid', 'savedAt')
MASKS = ('in the inputs, the values of lightGuid and lightmapGuid: test_compiler\'s light scene makes them from '
         'Python\'s string hash, which is new in each process',
         'in the inputs, the values of savedAt: test_prefab_stage saves its stage project at the time it runs')


class Masker:
    """The values of `keys` out of a JSON value, wherever they are."""

    def __init__(self, keys=()):
        self.keys = tuple(keys)

    def value(self, v):
        if isinstance(v, dict):
            return {k: '<masked>' if k in self.keys else self.value(x) for k, x in v.items()}
        if isinstance(v, list):
            return [self.value(x) for x in v]
        return v


def plain(v, masker):
    """A JSON value of `v` (Paths and other objects as text), masked."""
    return masker.value(json.loads(json.dumps(v, default=str)))


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


class Recorder:
    """The wrappers of compile_project and native_split, and the calls they saw."""

    def __init__(self, compiler):
        self.compiler = compiler
        self.real_compile = compiler.compile_project
        self.real_split = compiler.native_split
        self.calls = []
        self.test = None        # the running test's id
        self.masker = Masker()
        self.input_masker = Masker(() if self.no_masks else INPUT_KEYS)

    def families(self):
        """The families switched off now (a test may switch one off for its run: FAMILIES' builds)."""
        return sorted(name for name, f in self.compiler.FAMILIES.items() if not f.get('builds'))

    keep_inputs = False     # (--keep-inputs: each call's inputs whole too, to find what differs in them)
    no_masks = False        # (--no-masks: nothing masked, to find what a test makes fresh)

    def add(self, kind, inputs, outputs):
        given = plain(inputs, self.input_masker)
        self.calls.append(dict(n=len(self.calls), test=self.test, kind=kind, inputs=digest(given),
                               outputs=plain(outputs, self.masker), **({'given': given} if self.keep_inputs else {})))

    def compile_project(self, doc, scene, enable=(), library=None, foreign=()):
        inputs = dict(doc=doc, scene=scene, enable=list(enable or ()), foreign=list(foreign or ()),
                      library=type(library).__name__ if library is not None else None, off=self.families())
        before = copy.deepcopy(inputs)
        try:
            spec, report = self.real_compile(doc, scene, enable, library, foreign)
        except Exception as error:
            self.add('compile', before, dict(raised='%s: %s' % (type(error).__name__, error)))
            raise
        try:
            split = list(self.real_split(spec)) if spec is not None else None
        except Exception as error:     # (a spec native_split can't take: said, the test goes on)
            split = 'raised %s: %s' % (type(error).__name__, error)
        self.add('compile', before, dict(spec=spec, report=report, split=split))
        return spec, report

    def native_split(self, spec):
        before = copy.deepcopy(spec)
        try:
            out = self.real_split(spec)
        except Exception as error:
            self.add('split', dict(spec=before), dict(raised='%s: %s' % (type(error).__name__, error)))
            raise
        self.add('split', dict(spec=before), dict(split=list(out)))
        return out


class Result(unittest.TextTestResult):
    recorder = None

    def startTest(self, test):
        self.recorder.test = test.id()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self.recorder.test = None


def run_suite(recorder, pattern=None, stream=None):
    """The editor suite's test files in this process (unittest discover, as run_tests.py runs them): the result."""
    loader = unittest.TestLoader()
    if pattern:
        loader.testNamePatterns = ['*%s*' % pattern]
    suite = loader.discover(start_dir=str(HERE), pattern='test_*.py', top_level_dir=str(HERE))
    Result.recorder = recorder
    runner = unittest.TextTestRunner(stream=stream or sys.stderr, verbosity=1, resultclass=Result)
    return runner.run(suite)


def record(out, pattern=None):
    os.chdir(REPO)
    for p in (str(HERE), str(EDITOR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import compiler
    recorder = Recorder(compiler)
    # in place before any test file is imported: `from compiler import compile_project` takes the wrapper
    compiler.compile_project = recorder.compile_project
    compiler.native_split = recorder.native_split
    started = time.monotonic()
    log = Path(out).with_suffix('.log')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'w', encoding='utf-8', newline='\n') as stream:
        result = run_suite(recorder, pattern, stream)
    seconds = round(time.monotonic() - started, 1)
    compiles = sum(1 for c in recorder.calls if c['kind'] == 'compile')
    rec = dict(format=FORMAT, masks=list(MASKS), tests=result.testsRun, failures=len(result.failures),
               errors=len(result.errors), skipped=len(result.skipped), calls=recorder.calls, count=len(recorder.calls),
               compiles=compiles, splits=len(recorder.calls) - compiles, unattributed=sum(1 for c in recorder.calls if not c['test']))
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rec, sort_keys=True, indent=1, ensure_ascii=False) + '\n')
    print('recorded %d calls (%d compiles, %d native splits) of %d tests (%d failures, %d errors, %d skipped) in %.0f s: %s'
          % (len(recorder.calls), compiles, rec['splits'], result.testsRun, rec['failures'], rec['errors'], rec['skipped'],
             seconds, out))
    if result.failures or result.errors:
        print('the suite did not pass (its output: %s): a record of a failing suite is not one to compare' % log)
        return 1
    return 0


# ---------------------------------------------------------------------------------------------------- compare

def by_test(calls):
    out = {}
    for c in calls:
        out.setdefault(c['test'] or '(no test)', []).append(c)
    return out


def compare(before, after):
    a, b = (json.loads(Path(p).read_text(encoding='utf-8')) for p in (before, after))
    ta, tb = by_test(a['calls']), by_test(b['calls'])
    differ = 0
    for test in list(ta) + [t for t in tb if t not in ta]:
        ca, cb = ta.get(test, []), tb.get(test, [])
        if not ca or not cb:
            print('%s: calls only %s (%d)' % (test, 'before' if ca else 'after', len(ca or cb)))
            differ += 1
            continue
        for k in range(max(len(ca), len(cb))):
            x, y = (ca[k] if k < len(ca) else None), (cb[k] if k < len(cb) else None)
            if x is None or y is None:
                print('%s: call %d of the test only %s (%d calls before, %d after)'
                      % (test, k + 1, 'before' if y is None else 'after', len(ca), len(cb)))
                differ += 1
                break
            if (x['kind'], x['inputs'], x['outputs']) != (y['kind'], y['inputs'], y['outputs']):
                what = []
                if x['kind'] != y['kind']:
                    what.append('a %s before, a %s after' % (x['kind'], y['kind']))
                if x['inputs'] != y['inputs']:
                    what.append('its inputs differ' + (': %s' % ', '.join(differing_keys(x['given'], y['given']))
                                                       if 'given' in x and 'given' in y else ''))
                if x['outputs'] != y['outputs']:
                    what.append('outputs differ: %s' % ', '.join(differing_keys(x['outputs'], y['outputs'])))
                print('%s: call %d of the test (%s, call %d of the suite): %s'
                      % (test, k + 1, x['kind'], x['n'] + 1, '; '.join(what)))
                differ += 1
                break
    for key in ('tests', 'failures', 'errors'):
        if a.get(key) != b.get(key):
            print('the suite\'s %s: %s before, %s after' % (key, a.get(key), b.get(key)))
            differ += 1
    if differ:
        print('the records differ (%d test(s)); %d calls before, %d after' % (differ, a['count'], b['count']))
        return 1
    print('the records are the same: %d calls of %d tests' % (a['count'], a['tests']))
    return 0


def main(argv=None):
    sys.stdout.reconfigure(errors='replace')
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = a.add_subparsers(dest='command', required=True)
    r = sub.add_parser('record', help='run the editor suite and record every compile')
    r.add_argument('--out', required=True, help='the record to write (JSON; the suite\'s output goes beside it, .log)')
    r.add_argument('-k', dest='pattern', help='only the tests whose names hold this (unittest\'s -k)')
    r.add_argument('--keep-inputs', action='store_true', help=argparse.SUPPRESS)
    r.add_argument('--no-masks', action='store_true', help=argparse.SUPPRESS)
    c = sub.add_parser('compare', help='two records compared; exit 1 if they differ')
    c.add_argument('before')
    c.add_argument('after')
    args = a.parse_args(argv)
    if args.command == 'record':
        Recorder.keep_inputs, Recorder.no_masks = args.keep_inputs, args.no_masks
        return record(Path(args.out).resolve(), args.pattern)
    return compare(args.before, args.after)


if __name__ == '__main__':
    sys.exit(main())
