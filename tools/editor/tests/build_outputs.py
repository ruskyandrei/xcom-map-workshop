"""The Builds of the project inputs, byte for byte: the check that a change to the compiler, the Build, the copy tool,
the package tools or the relight leaves a Build's output as it was where it should, and names every file and record
it changed.

The project inputs (INPUTS) are chosen so that together their native edits (compiler.native_split, which
tools/bake/native_copy.py reads) hold every lane the native edit has, and their Builds take the Build's routes into
the relight: bar-grid, whose only edit is a larger grid, sends its baked Build to the relight alone, on the copy of
the map the growing writer names (build.py named_base, tools/upk/package_grow.py). Each is the document of a generator in
tools/editor/examples, or the documents of two or three generators on one map merged into one project (merged), with
at most a field or a piece added in code (EXTRAS: a spawn rule, an invisible floor); every generator runs in a process
of its own on scratch settings, its compile recorded and its own Build refused (capture_main). The documents are made
the same each run (revision 1, savedAt fixed). For each input `record` runs a quick Build and a baked Build into
scratch folders, with the Build's
`run` hook a recorder: every tool runs as in a real Build except the relight (tools/bake/relight.py, or
native_copy.py --bake), whose command line and the hashes of the files it names are recorded, and which is not run;
in its place native_copy.py makes the edit without --bake (the baked Build's map is then the quick one's, unlit) and
a stand-in relight record lets the Build go on. It writes <out>/outputs.json: for each input and each Build, the
SHA-256 of every file of the package (the variant map, the patch, the intro and stream copies, the readme), the
manifest and the compile report with times, attempt ids, tool hashes and folders masked, the relight's command with
folders masked, the Build's native edit and patch spec as it wrote them; and for each input its project document,
the compile's whole spec, report and native edit (the compiler's boundary), and the export of its map it read.

  python -B tools/editor/tests/build_outputs.py record --out <folder> [--only NAME ...] [--game <install>] [--cache <cache>] [--keep]
  python -B tools/editor/tests/build_outputs.py compare <before folder> <after folder>
  python -B tools/editor/tests/build_outputs.py --list [--game <install>] [--cache <cache>]

`compare` lists the differing files and records by input, and exits 1 if anything differs; an input recorded on one
side only is named as such. `--list` makes and compiles the inputs (no Build) and prints the lanes each one's native
edit holds. `record` fails when a lane of the native edit is in none of the inputs.

The install and the cache come from the settings (tools/viewer/viewer.py settings) or --game and --cache; without
them the tool says so and exits 2. The cache is only read: the scene.json of the exports the inputs need and the
library's index are copied into a scratch cache under <out>, where the library makes the pieces of other maps afresh
from the install. Everything is written under <out> (its scratch folder is removed at the end unless --keep); never
the user's projects, builds or cache. A whole record takes about two minutes. It is a tool, not a test: run_tests.py
does not run it (test_record_tools.py tests its compare, masks, lanes, merge and plant).

A stage uses it so (a tool checks the code of the checkout it runs in): record on the stage's base in a scratch
worktree of that commit, record on the stage's head, compare the two. Both records must read the same exports: if
the cache gets a newer export of an input's map between them, compare says so (the input's `export`).
"""
import argparse
import copy
import datetime
import hashlib
import inspect
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDITOR = HERE.parent
TOOLS = EDITOR.parent
REPO = TOOLS.parent
EXAMPLES = EDITOR / 'examples'
VIEWER = TOOLS / 'viewer'

FORMAT = 1
NOW = datetime.datetime(2026, 1, 1, 0, 0, 0)       # every Build's clock: its id, stamp and builtAt
SAVED_AT = '2026-01-01T00:00:00Z'                   # every input document's savedAt and created
KINDS = ('quick', 'baked')

# The native edit's lanes: compiler.native_split's keys, and the one the Build adds (streamTiles, from streamMoves).
# The tool also reads the lanes from native_split's and native_copy.py's code (code_lanes), so a lane added later is
# required too.
LANES = ('copies', 'breakOriginals', 'hides', 'lights', 'covers', 'pieceFlags', 'pieceFlagLadders', 'pieceBlasts',
         'buildings', 'buildingEdits', 'assemblies', 'streamHides', 'streamMoves', 'streamTiles', 'cleared',
         'landingZones', 'spawnRules', 'carriedEffects', 'effects', 'sounds', 'flares', 'spawns', 'backgroundSound')
BUILD_LANES = ('streamTiles',)      # added by the Build (Build.compile), not by the compiler
OPS = ('moves', 'deletes', 'copies', 'values')
LIGHT_OPS = ('deletes', 'changes', 'adds', 'area')
COPY_PARTS = ('breakGroup', 'wallGroup', 'donor', 'untried', 'flags', 'generated', 'blasts', 'breaksFurther', 'ladder')

# The inputs: `parts`, the generators of tools/editor/examples whose documents make it (merged when there are
# several), each with its arguments ({out}, {store}, {builds} and {cache} are scratch folders of the input) and the
# document picked from the compiles it makes (its name; None: the last); `extras`, what is added in code (EXTRAS);
# `maps`, the maps whose exports it reads, and `donors`, maps whose exports help it (copied when the cache has them).
def part(script, *args, pick=None):
    return dict(script=script, args=list(args), pick=pick)


BAR, POLICE = ['URB_Bar'], ['URB_PoliceStation']
OUT = ('{out}', '--compile')            # a generator that takes its scratch folder and stops after the compile
STORE = ('--store', '{store}', '--builds', '{builds}')      # one that saves into a scratch store and builds nothing
CACHE = ('--cache', '{cache}')          # one that saves into the settings' projects (the scratch ones)
INPUTS = [
    dict(name='bar-pieces', maps=BAR, parts=[part('exp24_cars_project.py', *CACHE), part('exp26_projects.py', *CACHE)],
         what='URB_Bar: pieces copied, moved and deleted, cars among them (assemblies); lights changed, added, deleted'),
    dict(name='bar-effects', maps=BAR, parts=[part('exp68_project.py', *OUT), part('exp71_project.py', *OUT)],
         what='URB_Bar: effects and sounds moved, copied and deleted; lens flares moved, deleted, copied (two from '
              'another map)'),
    dict(name='bar-spawns', maps=BAR, extras=['spawn rule'],
         parts=[part('exp72_sp6_project.py', '{store}', '{builds}', *CACHE, '--compile'),
                part('exp72_sp7_project.py', '{store}', '{builds}', *CACHE, '--compile')],
         what='URB_Bar: spawn points moved, given values, copied and deleted; drop-ins placed (a spawn rule)'),
    dict(name='bar-made', maps=BAR, parts=[part('exp84_project.py', *STORE), part('exp82_project.py', *STORE)],
         what='URB_Bar: made walls with openings and flags, made ground and a rock, a door of another map; a made roof '
              'built broken and the map\'s own pieces broken where they stand'),
    dict(name='bar-groups', maps=BAR, extras=['invisible floor'],
         parts=[part('exp88_projects.py', 'walls', *STORE), part('exp52_project.py', *OUT), part('exp50_project.py', *OUT)],
         what='URB_Bar: made walls that break with a prop and a cover block; cover blocks that break with their group, '
              'the map\'s own pieces among them; the map\'s own buildings edited; an invisible floor'),
    dict(name='bar-clear', maps=BAR, parts=[part('clear_bar_project.py', '{out}', '--grid', '60', '45', '12', '--zones',
                                                 '--sound', 'SoundAmbience-NorthAmerica.ForestAmbienceCue', '--compile')],
         what='URB_Bar cleared (its triggers taken out), on a larger grid (60 by 45 by 12), with two landing zones (its '
              'own moved, one added) and another map\'s background sound (the forest\'s, brought from CLrgScout_DeepWoods)'),
    dict(name='bar-foreign', maps=BAR, parts=[part('exp40_project.py', *OUT)],
         what='URB_Bar: a car, a door with its frame and a ladder from other maps'),
    dict(name='bar-flags', maps=BAR, parts=[part('exp62_project.py', *OUT), part('exp76_project.py', *STORE),
                                            part('exp70_project.py', *OUT)],
         what='URB_Bar: pieces\' flags on copies and in place, a ladder\'s among them; a made upper floor and roof over '
              'a room of made walls with doorways, as a building of the project; effects\' and sounds\' values set'),
    dict(name='police', maps=POLICE, donors=BAR,
         parts=[part('exp24_police_project.py', *CACHE), part('exp73_project.py', *STORE)],
         what='URB_PoliceStation: cars copied, moved and deleted; walls made from URB_Bar\'s wall'),
    dict(name='police-streams', maps=POLICE, parts=[part('exp55_project.py', *OUT)],
         what='URB_PoliceStation\'s data recovery: a capture point of its mission stream moved (a mission\'s objects '
              'moved in their stream)'),
    dict(name='bar-grid', maps=BAR, parts=[part('grid_bar_project.py', '{out}', '--grid', '56', '43', '--compile')],
         what='URB_Bar on a larger grid (56 by 43) and nothing else: its baked Build relights a copy of the map the '
              'growing writer names (KB-2: a real one stops in the relight)'),
]


# ---------------------------------------------------------------------------------------------------- small helpers

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + '\n')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def use_paths():
    for p in (VIEWER, EDITOR):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def install_and_cache(args):
    """(game install folder, cache folder) from --game/--cache or the settings; None for one that is not there."""
    use_paths()
    import settings as settings_module
    try:
        s = settings_module.load_settings()
    except (OSError, ValueError):
        s = {}
    game = Path(args.game) if args.game else s.get('game')
    cache = Path(args.cache) if args.cache else s.get('cache')
    install = settings_module.resolve_game(game)[0] if game else None
    return install, (Path(cache) if cache and Path(cache).is_dir() else None)


class Masker:
    """Folders of this run out of strings (each root as a placeholder, either slash, any case), times, attempt ids
    and the code's own hashes out of records."""
    TIME_KEYS = {'seconds', 'times'}      # (the Build's stage and build times, and the project's last times)

    def __init__(self, roots):
        # the longest first: the scratch folder may be inside the repository
        self.roots = sorted(((str(Path(r)), name) for r, name in roots.items() if r), key=lambda x: -len(x[0]))
        self.patterns = []
        for root, name in self.roots:
            for form in {root, root.replace('\\', '/'), root.replace('\\', '\\\\')}:
                self.patterns.append((re.compile(re.escape(form), re.IGNORECASE), name))

    def text(self, s):
        for pattern, name in self.patterns:
            s = pattern.sub(lambda _m, n=name: n, s)
        return s

    def value(self, v, key=None):
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                if k in self.TIME_KEYS:
                    out[k] = '<time>'
                elif k == 'attempt':
                    out[k] = '<attempt>'
                elif k == 'tools' and isinstance(x, dict):
                    # the code's own files' hashes: a refactor changes them by design
                    out[k] = {t: '<sha256>' for t in x}
                else:
                    out[k] = self.value(x, k)
            return out
        if isinstance(v, list):
            return [self.value(x, key) for x in v]
        if isinstance(v, str):
            return self.text(v)
        return v

    MASKS = ('folders of the run (scratch, repository, install, cache, python) as placeholders',
             'times: every "seconds" and "times" value',
             'attempt ids: every "attempt" value',
             "the code's own hashes: the manifest's tools values (keys kept)",
             "the Build's clock is fixed (2026-01-01 00:00:00), so build ids, stamps and builtAt are the same each run")


def flat(v, prefix=''):
    """{dotted key: leaf} of a JSON value, for comparing records key by key."""
    out = {}
    if isinstance(v, dict) and v:
        for k in sorted(v):
            out.update(flat(v[k], '%s.%s' % (prefix, k) if prefix else str(k)))
    elif isinstance(v, list) and v:
        for i, x in enumerate(v):
            out.update(flat(x, '%s[%d]' % (prefix, i)))
    else:
        out[prefix] = v
    return out


def differing_keys(a, b, limit=12):
    """The dotted keys whose leaves differ, the first `limit` of them (an empty container on one side that holds
    something on the other is named by what it holds)."""
    fa, fb = flat(a), flat(b)
    keys = sorted(k for k in set(fa) | set(fb) if fa.get(k, '<absent>') != fb.get(k, '<absent>'))
    keys = [k for k in keys if not any(o != k and (k == '' or o.startswith((k + '.', k + '['))) for o in keys)]
    keys = [k or '(the whole value)' for k in keys]
    return keys[:limit] + (['... %d more' % (len(keys) - limit)] if len(keys) > limit else [])


# ---------------------------------------------------------------------------------------------------- lanes

def code_lanes():
    """The lanes named in the code: native_split's keys (its native[...] and dict(...) keys and the effect lanes it
    takes) and the native edit's keys native_copy.py reads (doc.get(...)), with LANES."""
    use_paths()
    import compiler
    found = set(LANES)
    try:
        src = inspect.getsource(compiler.native_split)
        found |= set(re.findall(r"native\['(\w+)'\]", src))
        m = re.search(r"native = dict\(([^)]*)\)", src)
        if m:
            found |= set(re.findall(r'(\w+)=', m.group(1)))
        for group in re.findall(r"obj\.get\('type'\) in \(([^)]*)\)", src):
            if 'effects' in group:
                found |= set(re.findall(r"'(\w+)'", group))
    except (OSError, TypeError):
        pass
    copier = TOOLS / 'bake' / 'native_copy.py'
    try:
        text = copier.read_text(encoding='utf-8')
        block = text[text.index('if isinstance(doc, dict):'):text.index('for c in doc:')]
        found |= set(re.findall(r"doc\.get\('(\w+)'\)", block))
    except (OSError, ValueError):
        pass
    return sorted(found)


def lanes_of(native):
    """(lanes, parts) a native edit holds: its non-empty top-level keys, and their parts (a light lane's and an
    effect lane's ops, a copy's fields and assembly family)."""
    lanes, parts = set(), set()
    for k, v in (native or {}).items():
        if v in (None, [], {}, False) and k != 'landingZones':
            continue
        if k == 'landingZones' and v is None:
            continue
        if k == 'lights':
            ops = [op for op in LIGHT_OPS if v.get(op)]
            if not ops:
                continue
            parts |= {'lights.' + op for op in ops}
        elif k in ('effects', 'sounds', 'flares', 'spawns'):
            ops = [op for op in OPS if (v or {}).get(op)]
            if not ops:
                continue
            parts |= {'%s.%s' % (k, op) for op in ops}
        elif k == 'copies':
            for c in v:
                parts |= {'copies.' + f for f in COPY_PARTS if c.get(f)}
                if c.get('family'):
                    parts.add('copies.family.' + c['family'])
                if (c.get('generated') or {}).get('kind'):
                    parts.add('copies.generated.' + c['generated']['kind'])
        elif k == 'covers':
            parts |= {'covers.' + str(c.get('kind')) for c in v}
        lanes.add(k)
    return sorted(lanes), sorted(parts)


# ---------------------------------------------------------------------------------------------------- the inputs

def capture_main(argv):
    """In a process of its own (`_capture <generator> <calls.json> -- args`): the generator run as a script with
    every compile it makes recorded ({doc, enable, foreign}) and the Build refused, so it builds nothing."""
    script, out, args = argv[0], Path(argv[1]), argv[3:] if len(argv) > 2 and argv[2] == '--' else argv[2:]
    use_paths()
    import build
    import compiler
    calls = []
    real = compiler.compile_project

    def compile_project(doc, scene, enable=(), library=None, foreign=()):
        calls.append(dict(doc=copy.deepcopy(doc), enable=list(enable or ()), foreign=list(foreign or ())))
        write_json(out, calls)
        return real(doc, scene, enable, library, foreign)

    class Refused(Exception):
        pass

    def refuse(self):
        raise Refused()

    compiler.compile_project = compile_project
    build.Build.run = refuse
    write_json(out, calls)
    sys.argv = [script] + list(args)
    code = 0
    try:
        runpy.run_path(script, run_name='__main__')
    except Refused:
        print('build_outputs: the generator\'s own Build was not run')
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if not isinstance(e.code, int) and e.code is not None:
            print(e.code)
    print('build_outputs: %d compile(s) recorded' % len(calls))
    return code


def scratch_settings(folder, cache, install):
    """A settings file for the generators: projects, builds and prefabs in `folder`, the scratch cache, the install."""
    path = folder / 'settings.json'
    write_json(path, dict(projects=str(folder / 'projects'), output=str(folder / 'builds'), cache=str(cache),
                          game=str(install), install=str(install), prefabs=str(folder / 'prefabs')))
    return path


def normalised(doc):
    """The document as the Build reads it, the same each run: revision 1, savedAt and created fixed."""
    doc = copy.deepcopy(doc)
    doc['revision'] = 1
    doc['savedAt'] = SAVED_AT
    doc['created'] = SAVED_AT
    return doc


def plant(doc):
    """One byte of the document changed in one copy's pose (the tool's own check): the x of the last added piece
    copied from a piece (`from`) whose x changes in one digit alone when moved one unit away from zero (in
    bar-pieces a plain copy, the destructible of EXP-26, not a car's part)."""
    before = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False)
    for rec in reversed(doc.get('added') or []):
        loc = rec.get('location')
        if not (rec.get('from') and isinstance(loc, list) and loc and isinstance(loc[0], (int, float))):
            continue
        old = loc[0]
        loc[0] = old + (1 if old >= 0 else -1)
        after = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False)
        if len(after) == len(before) and sum(a != b for a, b in zip(before, after)) == 1:
            return '%s: location x %r -> %r (one byte of the document)' % (rec.get('actor'), old, loc[0])
        loc[0] = old
    raise SystemExit('nothing to plant in: the input adds no copy whose x changes in one byte')


def run_generator(name, part, folder, settings_path, cache):
    """One generator run in a process of its own on the scratch settings: the compile it made that `part` picks
    ({doc, enable, foreign})."""
    for sub in ('out', 'store', 'builds'):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    args = [a.format(out=folder / 'out', store=folder / 'store', builds=folder / 'builds', cache=cache)
            for a in part['args']]
    calls_path, log = folder / 'calls.json', folder / 'generator.log'
    env = dict(os.environ, XCOM_MAP_WORKSHOP_SETTINGS=str(settings_path), PYTHONIOENCODING='utf-8')
    with open(log, 'w', encoding='utf-8', newline='\n') as f:
        proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '_capture',
                               str(EXAMPLES / part['script']), str(calls_path), '--'] + args,
                              cwd=str(REPO), env=env, stdout=f, stderr=subprocess.STDOUT)
    calls = read_json(calls_path) if calls_path.is_file() else []
    pick = part.get('pick')
    chosen = [c for c in calls if pick is None or c['doc'].get('name') == pick]
    if not chosen:
        tail = log.read_text(encoding='utf-8', errors='replace').splitlines()[-15:]
        raise SystemExit('%s: %s made no compile%s (exit %s); its log %s ends:\n  %s'
                         % (name, part['script'], ' of %r' % pick if pick else '', proc.returncode, log,
                            '\n  '.join(tail)))
    return chosen[-1]


# the list fields of a project document that merge by concatenation, and what names an item of each
MERGED_LISTS = {'added': lambda r: ('id', r.get('id')), 'overrides': lambda r: json.dumps(r.get('target'), sort_keys=True),
                'groups': lambda r: r.get('id'), 'buildings': lambda r: r.get('id'),
                'areaLightBindings': lambda r: json.dumps(r, sort_keys=True), 'landingZones': lambda r: r.get('id'),
                'missions': lambda r: json.dumps(r, sort_keys=True)}
PER_RUN = ('revision', 'savedAt', 'created')


def merged(name, docs):
    """Several generators' documents of one map as one project: the first's id, names and view; every list field
    (MERGED_LISTS) concatenated, an item named twice kept once when it is the same and refused when not (an added
    piece's id or actor, an override's target...); any other field taken where one document has it, refused when two
    disagree; the newest schema version and the largest nextSerial."""
    out = copy.deepcopy(docs[0])
    if len({((d.get('source') or {}).get('map'), (d.get('source') or {}).get('sha256')) for d in docs}) > 1:
        raise SystemExit('%s: its documents are not of one map' % name)
    for doc in docs[1:]:
        for k, v in doc.items():
            if k in MERGED_LISTS:
                have = out.setdefault(k, [])
                keys = {MERGED_LISTS[k](r): r for r in have}
                actors = {r.get('actor'): r for r in have if k == 'added' and r.get('actor')}
                for r in v:
                    key = MERGED_LISTS[k](r)
                    if key in keys or (k == 'added' and r.get('actor') in actors):
                        if keys.get(key, actors.get(r.get('actor'))) != r:
                            raise SystemExit('%s: its documents disagree on %s %s' % (name, k, key))
                        continue
                    have.append(copy.deepcopy(r))
                    keys[key] = r
                    if k == 'added' and r.get('actor'):
                        actors[r['actor']] = r
            elif k == 'schemaVersion':
                out[k] = max(out.get(k) or 0, v)
            elif k == 'nextSerial':
                out[k] = max(out.get(k) or 0, v)
            elif k in ('id', 'name', 'output', 'view', 'source') or k in PER_RUN:
                continue
            elif k not in out:
                out[k] = copy.deepcopy(v)
            elif out[k] != v:
                raise SystemExit('%s: its documents disagree on %s' % (name, k))
    return out


# What an input adds to its generators' documents in code (only maps every install has): a project document's
# fields as the editor saves them.
def spawn_rule(doc, scene):
    """Scripted drop-ins land where placed (schema 4's spawnRules; the spawns plan, SP8)."""
    doc['spawnRules'] = dict(dropIns='placed')
    doc['schemaVersion'] = max(doc.get('schemaVersion') or 0, 4)


def invisible_floor(doc, scene):
    """An invisible floor (a cover block of type floor, by recipe version 2), 2 by 2 tiles, a storey over the bar's
    pavement east of the cover blocks of EXP-52 and EXP-58 (the pavement's top at 16, its south row y -288)."""
    serial = max([doc.get('nextSerial') or 0] + [len(doc.get('added') or [])]) + 1
    doc.setdefault('added', []).append({
        'id': '00000000-0000-4000-8000-%012d' % (990000 + serial), 'actor': 'TheWorld.PersistentLevel.Floor_copy%d' % serial,
        'template': dict(kind='cover', version=2), 'cover': dict(width=2, length=2, type='floor', height=1),
        'location': [480.0, -288.0, 80.0], 'rotation': [0, 0, 0]})
    doc['nextSerial'] = serial + 1


EXTRAS = {'spawn rule': spawn_rule, 'invisible floor': invisible_floor}


def make_input(entry, folder, settings_path, cache):
    """The input's document ({doc, enable, foreign}): its generators run, their documents merged, its extras added."""
    calls = [run_generator(entry['name'], part, folder / ('generator-%d' % k), settings_path, cache)
             for k, part in enumerate(entry['parts'])]
    doc = merged(entry['name'], [c['doc'] for c in calls]) if len(calls) > 1 else copy.deepcopy(calls[0]['doc'])
    for extra in entry.get('extras') or ():
        EXTRAS[extra](doc, None)
    enable = list(dict.fromkeys(f for c in calls for f in c['enable']))
    foreign = list(dict.fromkeys(f for c in calls for f in c['foreign']))
    return dict(doc=doc, enable=enable, foreign=foreign)


def prepare_cache(user_cache, install, folder, inputs):
    """The scratch cache: each needed map's export (the generation the cache's newest qualifying one is: its
    scene.json alone) and the library's index. {map: {generation, sha256}} of the exports copied."""
    use_paths()
    import compiler
    import game_files
    folder.mkdir(parents=True, exist_ok=True)
    exports, missing = {}, []
    wanted = [(m, True) for e in inputs for m in e['maps']] + [(m, False) for e in inputs for m in e.get('donors', ())]
    for name, required in wanted:
        if name in exports:
            continue
        base = game_files.lwr_file(install, 'CookedPCConsole', '%s.upk' % name)
        if not base.is_file():
            if required:
                missing.append('%s (not in the install)' % name)
            continue
        sha = sha256_file(base)
        try:
            scene, _ = compiler.find_export(user_cache, dict(source=dict(map=name, sha256=sha)))
        except compiler.ExportMissing:
            if required:
                missing.append('%s (no export in the cache: prepare the map in the editor first)' % name)
            continue
        dst = folder / name / scene.parent.name / 'scene.json'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(scene, dst)
        exports[name] = dict(generation=scene.parent.name, sha256=sha256_file(scene))
    index = Path(user_cache) / 'library' / 'index.json'
    if index.is_file():
        (folder / 'library').mkdir(parents=True, exist_ok=True)
        shutil.copy2(index, folder / 'library' / 'index.json')
        exports['library index'] = dict(sha256=sha256_file(index))
    else:
        missing.append('the library index (scan the library: the Add panel\'s All maps)')
    return exports, missing


def compile_input(doc, enable, foreign, cache, install):
    """The compile the Build makes of the document, whole: (spec, report, patch spec, native edit)."""
    use_paths()
    import compiler
    spec, report = compiler.compile_project(doc, compiler.find_export(cache, doc)[1], enable,
                                            compiler.Library(cache, install), foreign)
    if spec is None:
        return None, report, None, None
    patch, native = compiler.native_split(compiler.stream_only(spec))
    return spec, report, patch, native


# ---------------------------------------------------------------------------------------------------- the Builds

RELIGHT_ONLY = {'--bake': 0, '--cache': 1, '--receivers-near': 1, '--jobs': 1, '--edit-spec': 1, '--piece-cache': 1,
                '--base': 1}


class Recorder:
    """The Build's `run` hook: every tool run as the Build runs it (its own _run), but the relight, which is recorded
    (its command and the SHA-256 of each file it names) and not run. In its place, for native_copy.py --bake, the same
    command without the relight's options makes the edit in the map; for relight.py alone, the map it would relight is
    the variant. Then a stand-in relight record (no texel written, lighting not unchanged) lets the Build go on."""

    def __init__(self):
        self.build = None
        self.relights = []
        self.ran = []

    def __call__(self, args, log):
        args = [str(a) for a in args]
        k = next((i for i, a in enumerate(args) if a.endswith(('.py', '.ps1'))), 0)
        tool = Path(args[k]).name
        self.ran.append(tool)
        if tool == 'relight.py' or (tool == 'native_copy.py' and '--bake' in args):
            self.relights.append(dict(tool=tool, args=args, files={a: sha256_file(a) for a in args[k + 1:]
                                                                   if os.path.isfile(a)}))
            lit, variant = Path(args[k + 2]), args[k + 3]
            if tool == 'native_copy.py':
                rest, i = [], 0
                while i < len(args):
                    if args[i] in RELIGHT_ONLY:
                        i += 1 + RELIGHT_ONLY[args[i]]
                        continue
                    rest.append(args[i])
                    i += 1
                self.build._run(rest, log)
            else:
                lit.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(args[k + 1], lit / ('%s.upk' % variant))
            (lit / ('%s.relight.json' % variant)).write_text(json.dumps(dict(
                components=[], unchanged=[], skipped=[], lightingUnchanged=False, recordedNotRun=True)) + '\n',
                encoding='utf-8', newline='\n')
            return
        self.build._run(args, log)


def run_build(project, cache, install, output, quick, enable, foreign, log):
    """One Build of the project into `output`: (manifest or None, error or None, recorder, work folder or None)."""
    use_paths()
    import build
    import decomp
    rec = Recorder()
    lines = []
    b = build.Build(build.BuildInputs(project, cache, output, install, None, now=NOW, run=rec, echo=lines.append,
                                      quick=quick, enable=enable, foreign=foreign, games=()))
    rec.build = b
    # (the Build points the decoders at its work folder and the cache's kept images through the environment)
    saved = {k: os.environ.get(k) for k in (decomp.WORK_ENV, decomp.KEEP_ENV)}
    error = m = None
    try:
        m = b.run()
    except build.BuildError as e:
        error = str(e)
    finally:
        Path(log).write_text('\n'.join(str(x) for x in lines) + '\n', encoding='utf-8', newline='\n')
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return m, error, rec, b.work


def package_files(folder):
    """{relative path: SHA-256} of every file of a package folder but its manifest (kept whole, masked)."""
    out = {}
    for p in sorted(Path(folder).rglob('*')):
        if p.is_file() and p.name != 'manifest.json':
            out[p.relative_to(folder).as_posix()] = sha256_file(p)
    return out


def build_record(m, error, rec, work, output, masker):
    """What one Build is recorded by."""
    out = dict(error=masker.text(error) if error else None, tools=rec.ran,
               relight=[dict(tool=r['tool'], args=[masker.text(a) for a in r['args']],
                             files={masker.text(f): h for f, h in r['files'].items()}) for r in rec.relights])
    if m is not None:
        folder = Path(output) / m['variant']
        out['files'] = package_files(folder)
        out['manifest'] = masker.value(read_json(folder / 'manifest.json'))
    if work is not None and Path(work).is_dir():
        records = {}
        report = Path(work) / 'compile-report.json'
        if report.is_file():
            out['compileReport'] = masker.value(read_json(report))
        for name in ('native-edit.json', 'transplant/native-edit.staged.json'):
            p = Path(work) / name
            if p.is_file():
                records[name] = masker.value(read_json(p))
        # the patch spec the Build wrote (<patch>.json) and its other records, masked, by their hashes
        for p in sorted(Path(work).glob('*.json')):
            if p.name not in ('compile-report.json', 'native-edit.json'):
                records[p.name] = sha256_text(json.dumps(masker.value(read_json(p)), sort_keys=True))
        out['work'] = records
    return out


# ---------------------------------------------------------------------------------------------------- record

def selected(only):
    names = [e['name'] for e in INPUTS]
    for n in only or ():
        if n not in names:
            raise SystemExit('no input %r; the inputs: %s' % (n, ', '.join(names)))
    return [e for e in INPUTS if not only or e['name'] in only]


def make_all(entries, scratch, user_cache, install, plant_in=None, say=print, tolerant=False):
    """Each input made and compiled in the scratch folder: {name: dict(entry, doc, enable, foreign, compiled...)}."""
    cache = scratch / 'cache'
    exports, missing = prepare_cache(user_cache, install, cache, entries)
    if missing:
        say('the cache lacks what the inputs need:\n  ' + '\n  '.join(missing))
        raise SystemExit(2)
    settings_path = scratch_settings(scratch / 'generators', cache, install)
    made = {}
    for e in entries:
        t = time.monotonic()
        folder = scratch / e['name']
        try:
            call = make_input(e, folder, settings_path, cache)
        except SystemExit as error:
            if not tolerant:
                raise
            say(str(error))
            continue
        doc = normalised(call['doc'])
        planted = plant(doc) if plant_in == e['name'] else None
        spec, report, patch, native = compile_input(doc, call['enable'], call['foreign'], cache, install)
        lanes, parts = lanes_of(native)
        made[e['name']] = dict(entry=e, doc=doc, enable=call['enable'], foreign=call['foreign'], spec=spec,
                               report=report, patch=patch, native=native, lanes=lanes, parts=parts, planted=planted)
        say('  %-16s made and compiled in %5.1f s: %s' % (e['name'], time.monotonic() - t, ', '.join(lanes) or 'no lane'))
    return made, exports, cache


def project_file(folder, doc):
    path = folder / 'project' / ('%s.json' % doc.get('id', 'project'))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
    return path


def uncovered(made, built=False):
    """The lanes of the native edit in none of the inputs: of the compiler's alone, or with `built` those the Build
    adds too."""
    held = {lane for x in made.values() for lane in x['lanes']}
    return [lane for lane in code_lanes() if lane not in held and (built or lane not in BUILD_LANES)]


def record(args):
    install, user_cache = install_and_cache(args)
    if install is None or user_cache is None:
        print('build_outputs needs a game install and a prepared viewer cache: set them in the settings '
              '(python tools/viewer/viewer.py settings --game <folder> --cache <folder>) or give --game and --cache')
        return 2
    out = Path(args.out).resolve()
    scratch = out / 'scratch'
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    started = time.monotonic()
    entries = selected(args.only)
    print('making and compiling %d input(s) in %s' % (len(entries), scratch))
    made, exports, cache = make_all(entries, scratch, user_cache, install, getattr(args, 'plant', None))
    if not args.only:
        gaps = uncovered(made)
        if gaps:
            print('lanes of the native edit in none of the inputs: %s' % ', '.join(gaps))
            return 1
    masker = Masker({str(scratch): '<scratch>', str(REPO): '<repo>', str(install): '<game>',
                     str(user_cache): '<cache>', str(Path(sys.executable)): '<python>'})
    result = dict(format=FORMAT, masks=list(Masker.MASKS), exports=exports, inputs={})
    if getattr(args, 'plant', None):
        result['planted'] = args.plant
    for name, x in made.items():
        folder = scratch / name
        project = project_file(folder, x['doc'])
        entry = dict(generators=x['entry']['parts'], extras=x['entry'].get('extras') or [],
                     what=x['entry'].get('what'), lanes=x['lanes'], laneParts=x['parts'],
                     exports={m: exports.get(m) for m in [*x['entry']['maps'], *x['entry'].get('donors', ()), 'library index']},
                     project=x['doc'], projectSha256=sha256_file(project), enable=x['enable'], foreign=x['foreign'],
                     compile=masker.value(dict(spec=x['spec'], report=x['report'], patch=x['patch'], native=x['native'])),
                     builds={})
        if x['planted']:
            entry['planted'] = x['planted']
        for kind in KINDS:
            t = time.monotonic()
            output = folder / kind
            m, error, rec, work = run_build(project, cache, install, output, kind == 'quick', x['enable'],
                                            x['foreign'], folder / ('%s-build.log' % kind))
            entry['builds'][kind] = build_record(m, error, rec, work, output, masker)
            print('  %-16s %-5s Build in %5.1f s: %s' % (name, kind, time.monotonic() - t,
                                                         'failed: %s' % error[:200] if error else
                                                         '%d file(s)%s' % (len(entry['builds'][kind]['files']),
                                                                           ', relight recorded' if rec.relights else '')))
        result['inputs'][name] = entry
        # (the lanes, from the native edit the quick Build wrote, the streamTiles it adds among them)
        quick = (entry['builds']['quick'].get('work') or {}).get('native-edit.json')
        if quick is not None:
            entry['lanes'] = sorted(set(entry['lanes']) | set(lanes_of(quick)[0]))
    gaps = uncovered(result['inputs'], built=True) if not args.only else []
    if gaps:
        result['lanesInNone'] = gaps
    result['seconds'] = round(time.monotonic() - started, 1)
    write_json(out / 'outputs.json', result)
    if not args.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    if gaps:
        print('lanes of the native edit in none of the inputs: %s (the record is not one to compare)' % ', '.join(gaps))
        return 1
    print('recorded %d input(s) in %.0f s: %s' % (len(made), result['seconds'], out / 'outputs.json'))
    return 0


# ---------------------------------------------------------------------------------------------------- compare

def compare_input(a, b):
    """The differences of one input's records: [line]."""
    lines = []
    for m in sorted(set(a.get('exports') or {}) | set(b.get('exports') or {})):
        if (a.get('exports') or {}).get(m) != (b.get('exports') or {}).get(m):
            lines.append('export of %s differs (%s / %s): the cache, not the code' % (
                m, ((a.get('exports') or {}).get(m) or {}).get('generation'),
                ((b.get('exports') or {}).get(m) or {}).get('generation')))
    if a.get('projectSha256') != b.get('projectSha256') or a.get('project') != b.get('project'):
        lines.append('project document differs: %s' % ', '.join(differing_keys(a.get('project'), b.get('project'))))
    for part in ('spec', 'report', 'patch', 'native'):
        x, y = (a.get('compile') or {}).get(part), (b.get('compile') or {}).get(part)
        if x != y:
            lines.append('compile %s differs: %s' % (part, ', '.join(differing_keys(x, y))))
    for kind in KINDS:
        x, y = (a.get('builds') or {}).get(kind) or {}, (b.get('builds') or {}).get(kind) or {}
        if x.get('error') != y.get('error'):
            lines.append('%s: the Build %s / %s' % (kind, 'failed (%s)' % x['error'] if x.get('error') else 'built',
                                                    'failed (%s)' % y['error'] if y.get('error') else 'built'))
        fx, fy = x.get('files') or {}, y.get('files') or {}
        for f in sorted(set(fx) | set(fy)):
            if f not in fx:
                lines.append('%s: %s only after' % (kind, f))
            elif f not in fy:
                lines.append('%s: %s only before' % (kind, f))
            elif fx[f] != fy[f]:
                lines.append('%s: %s differs' % (kind, f))
        for part, label in (('manifest', 'manifest.json'), ('compileReport', 'compile-report.json'),
                            ('relight', 'relight command'), ('tools', 'tools run')):
            if x.get(part) != y.get(part):
                lines.append('%s: %s differs: %s' % (kind, label, ', '.join(differing_keys(x.get(part), y.get(part)))))
        wx, wy = x.get('work') or {}, y.get('work') or {}
        for f in sorted(set(wx) | set(wy)):
            if wx.get(f) != wy.get(f):
                detail = differing_keys(wx.get(f), wy.get(f)) if isinstance(wx.get(f), dict) and isinstance(wy.get(f), dict) else []
                lines.append('%s: work record %s differs%s' % (kind, f, (': ' + ', '.join(detail)) if detail else ''))
    return lines


def compare(before, after):
    a, b = read_json(Path(before) / 'outputs.json'), read_json(Path(after) / 'outputs.json')
    differ = False
    names = list(a['inputs']) + [n for n in b['inputs'] if n not in a['inputs']]
    for name in names:
        if name not in b['inputs'] or name not in a['inputs']:
            print('%s: recorded only %s' % (name, 'before' if name in a['inputs'] else 'after'))
            differ = True
            continue
        lines = compare_input(a['inputs'][name], b['inputs'][name])
        if lines:
            differ = True
            print('%s:' % name)
            for line in lines:
                print('  ' + line)
    if differ:
        print('the records differ')
        return 1
    print('the records are the same: %d input(s), quick and baked Builds' % len(names))
    return 0


# ---------------------------------------------------------------------------------------------------- list

def list_inputs(args):
    install, user_cache = install_and_cache(args)
    if install is None or user_cache is None:
        print('--list makes and compiles the inputs, so it needs a game install and a prepared viewer cache: set them '
              'in the settings or give --game and --cache')
        return 2
    out = Path(args.out).resolve() if args.out else (REPO / '.scratch' / 'build-outputs-list')
    scratch = out / 'scratch'
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    made, _, _ = make_all(selected(args.only), scratch, user_cache, install, tolerant=True)
    for name, x in made.items():
        print('%s: %s' % (name, x['entry'].get('what') or ''))
        print('  from: %s' % ' + '.join(['%s %s' % (p['script'], ' '.join(p['args'])) for p in x['entry']['parts']]
                                         + list(x['entry'].get('extras') or [])))
        print('  lanes: %s' % (', '.join(x['lanes']) or 'none'))
        print('  parts: %s' % (', '.join(x['parts']) or 'none'))
        r = x['report']
        print('  compile: %s, %d left out, %d warning(s)%s' % (
            'ok' if x['spec'] is not None else 'NOT COMPILED', len(r.get('leftOut') or []), len(r.get('warnings') or []),
            ''.join('\n    left out: %s' % d['message'][:160] for d in (r.get('leftOut') or [])[:5])
            + ''.join('\n    error: %s' % d['message'][:160] for d in (r.get('errors') or [])[:5])))
        if 'streamMoves' in x['lanes']:
            print('  (the Build adds streamTiles to it from streamMoves)')
    gaps = uncovered(made)
    print('lanes of the native edit: %s' % ', '.join(code_lanes()))
    print('in none of these inputs: %s' % (', '.join(gaps) or 'none'))
    if not args.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sys.stdout.reconfigure(errors='replace')
    if argv and argv[0] == '_capture':
        return capture_main(argv[1:])
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--list', action='store_true', help='make and compile the inputs, and print the lanes of each')
    sub = a.add_subparsers(dest='command')
    r = sub.add_parser('record', help='the inputs\' Builds recorded into <out>/outputs.json')
    r.add_argument('--out', required=True, help='the folder to record into (outputs.json; a scratch folder under it)')
    r.add_argument('--plant', help=argparse.SUPPRESS)       # the tool's own check: one byte changed in an input
    c = sub.add_parser('compare', help='two records compared; exit 1 if they differ')
    c.add_argument('before')
    c.add_argument('after')
    for p in (a, r):
        p.add_argument('--only', nargs='+', metavar='NAME', help='only these inputs')
        p.add_argument('--game', help='the game install (default: the settings\')')
        p.add_argument('--cache', help='the viewer cache, only read (default: the settings\')')
        p.add_argument('--keep', action='store_true', help='keep the scratch folder')
    a.add_argument('--out', help=argparse.SUPPRESS)
    args = a.parse_args(argv)
    if args.command == 'compare':
        return compare(args.before, args.after)
    if args.command == 'record':
        return record(args)
    if args.list:
        return list_inputs(args)
    a.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
