"""The code's shape, as far as a test can hold it (ARCHITECTURE.md, section 4 "The limits and the exceptions"),
with its numbers in tools/repo/structure.json.

- File size: a tracked Python file or page module over the file limit fails unless structure.json lists it with a
  ceiling; a listed one fails over its ceiling.
- Function size: the same for a function over the function limit in what the release ships (its modules and page
  files, as tools/release/make_release.py lists them). Python's functions and methods by their syntax tree; the
  page's top-level functions by their text, and a factory (`createX`, declaring its functions inside: a module made
  as a closure) by the functions it declares.
- app.js's top level: its module-level `let`s and its top-level functions, each with a ceiling.
- The page's imports: no page module imports app.js; no import cycle among them beyond those listed.
- What ships imports: no shipped module imports a module of the lab, the research tools or the tests (structure.json
  names their paths) beyond those listed, each with its reason.
- The import path: no shipped function changes sys.path itself (paths.use() is the way) beyond those listed, each
  with its reason.
- Compiler families: a module listed as a family of the compiler does not import the compiler.
- structure.json's form: sorted, one entry a line, so that changes to different entries merge cleanly.

A ceiling follows its file down and never back up: a listed file or function fails when it has shrunk more than a
twentieth under its ceiling (lower the ceiling), when it is within the limit again (take its entry out), and when it
is gone (take its entry out, or write it under its new name). Every message names its rule and the section of
ARCHITECTURE.md that explains it.

The files are the ones Git has or would add (tracked, and untracked ones that are not ignored), so a new file counts
before it is committed. To check another checkout (a scratch copy with planted breaks):

  python -B tools/repo/tests/test_structure.py --root <folder>

prints its problems by rule and exits 1 if there are any.
"""
import argparse
import ast
from fnmatch import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import moved_code  # noqa: E402

CONFIG = 'tools/repo/structure.json'
DOC = 'ARCHITECTURE.md'
SECTION = '4 "The limits and the exceptions"'
# the rules, each the heading of its part of the document's section 4
RULES = ('File size', 'Function size', "app.js's top level", "The page's imports", 'What ships imports',
         'The import path', 'Compiler families', "structure.json's form")
SLACK = 1 / 20
WEB = 'tools/viewer/web/'
APP = WEB + 'app.js'
FACTORY = re.compile(r'^create[A-Z]')
PATH_CALLS = {'insert', 'append', 'extend', 'remove', 'pop', 'clear'}


def where(rule):
    return '(%s, section %s: %s)' % (DOC, SECTION, rule)


def lines(data):
    """The number of lines in a file's bytes (a last line without a line break counts)."""
    return data.count(b'\n') + (1 if data and not data.endswith(b'\n') else 0)


def sized(rule, kind, sizes, ceilings, limit):
    """The problems of one sized rule: `sizes` {key: lines} of what is measured, `ceilings` {key: lines} of the
    listed exceptions, `limit` the rule's limit."""
    found = []
    for key, n in sorted(sizes.items()):
        if n > limit and key not in ceilings:
            found.append('%s: %s %s has %d lines, over the limit of %d: split it, or put the new code in a module of '
                         'its own %s' % (rule, kind, key, n, limit, where(rule)))
    for key, ceiling in sorted(ceilings.items()):
        n = sizes.get(key)
        if n is None:
            found.append('%s: %s %s is listed in %s but not there: take its entry out, or write it under its new '
                         'name %s' % (rule, kind, key, CONFIG, where(rule)))
        elif n > ceiling:
            found.append('%s: %s %s has %d lines, over its ceiling of %d: the change belongs in another module, or a '
                         'ceiling is raised only with the user\'s word %s' % (rule, kind, key, n, ceiling, where(rule)))
        elif n <= limit:
            found.append('%s: %s %s has %d lines, within the limit of %d now: take its entry out of %s %s'
                         % (rule, kind, key, n, limit, CONFIG, where(rule)))
        elif n < ceiling * (1 - SLACK):
            found.append('%s: %s %s has %d lines, more than a twentieth under its ceiling of %d: lower the ceiling '
                         'to %d in %s %s' % (rule, kind, key, n, ceiling, n, CONFIG, where(rule)))
    return found


def counted(rule, what, n, ceiling):
    """The problems of a count with a ceiling that follows it down."""
    if n > ceiling:
        return ['%s: %s is %d, over its ceiling of %d: new code goes into the module that owns its area %s'
                % (rule, what, n, ceiling, where(rule))]
    if n < ceiling * (1 - SLACK):
        return ['%s: %s is %d, more than a twentieth under its ceiling of %d: lower the ceiling to %d in %s %s'
                % (rule, what, n, ceiling, n, CONFIG, where(rule))]
    return []


def cycles(graph):
    """The import cycles of {module: {modules it imports}}: each strongly connected group of two or more modules (or
    a module importing itself), as its sorted names joined by spaces."""
    index, low, stack, on, out = {}, {}, [], set(), []

    def visit(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in sorted(graph.get(v, ())):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            group = []
            while True:
                w = stack.pop()
                on.discard(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1 or v in graph.get(v, ()):
                out.append(' '.join(sorted(group)))
    for v in sorted(graph):
        if v not in index:
            visit(v)
    return sorted(out)


class Tree:
    """A checkout's files and structure.json, read once."""

    def __init__(self, root):
        self.root = Path(root)
        self.config = json.loads((self.root / CONFIG).read_text(encoding='utf-8'))
        out = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=self.root,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        self.files = sorted(f for f in out.decode('utf-8').split('\0') if f and (self.root / f).is_file())
        self.page = [f for f in self.files if f.startswith(WEB) and f.endswith('.js') and '/vendor/' not in f]
        self._shipped = None
        self._trees, self._js = {}, {}

    def text(self, path):
        return (self.root / path).read_text(encoding='utf-8')

    def tree(self, path):
        if path not in self._trees:
            self._trees[path] = ast.parse(self.text(path), filename=path)
        return self._trees[path]

    def js(self, path):
        """(the top-level functions, (the top-level statements, the imports)) of a page module."""
        if path not in self._js:
            text = self.text(path)
            self._js[path] = (moved_code.js_functions(text), moved_code.js_top_level(text))
        return self._js[path]

    def shipped(self):
        """(the shipped Python modules, the shipped page modules), repo-relative: the release's own lists, from this
        checkout's make_release.py."""
        if self._shipped is None:
            code = ('import json, sys; sys.path.insert(0, sys.argv[1]); import make_release as m; '
                    'rel = lambda ps: [p.relative_to(m.REPO).as_posix() for p in ps]; '
                    'print(json.dumps([rel(m.modules()), rel(m.page_files())]))')
            out = subprocess.run([sys.executable, '-B', '-c', code, str(self.root / 'tools' / 'release')],
                                 cwd=self.root, capture_output=True, text=True)
            if out.returncode:
                raise RuntimeError('make_release.py could not list what ships: %s' % out.stderr.strip())
            modules, page = json.loads(out.stdout.strip().splitlines()[-1])
            self._shipped = (sorted(modules), sorted(p for p in page if p.endswith('.js') and '/vendor/' not in p))
        return self._shipped

    def kind(self, path):
        """'the lab', 'a research tool' or 'a test' when structure.json names `path` as one of those, else None."""
        for kind, patterns in sorted(self.config['not shipped'].items()):
            if any(fnmatch(path, p) for p in patterns):
                return kind
        return None


def imported_names(tree):
    """The top-level names a Python module imports, anywhere in it (absolute imports only), with their lines."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split('.')[0], node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split('.')[0], node.lineno


def file_size(t):
    sizes = {}
    for f in t.files:
        if f.endswith('.py') or f in t.page:
            sizes[f] = lines((t.root / f).read_bytes())
    return sized('File size', 'file', sizes, t.config['file lines'], t.config['limits']['file lines'])


def function_sizes(t):
    """{path::name: lines} of every function the function rule measures in what ships."""
    modules, page = t.shipped()
    sizes = {}
    for path in modules:
        for name, f in moved_code.python_functions(t.text(path)).items():
            sizes['%s::%s' % (path, name)] = f.end_line - f.start_line + 1
    for path in page:
        for name, f in t.js(path)[0].items():
            inner = moved_code.js_inner_functions(f) if FACTORY.match(name) else {}
            for key, g in (inner or {name: f}).items():
                sizes['%s::%s' % (path, key)] = g.end_line - g.start_line + 1
    return sizes


def function_size(t):
    return sized('Function size', 'function', function_sizes(t), t.config['function lines'],
                 t.config['limits']['function lines'])


def app_top_level(t):
    found, (starts, _) = t.js(APP)
    lets = sum(1 for _, keyword in starts if keyword == 'let')
    functions = len(found)
    ceilings = t.config['app.js']
    rule = "app.js's top level"
    return (counted(rule, "app.js's count of module-level lets", lets, ceilings['lets'])
            + counted(rule, "app.js's count of top-level functions", functions, ceilings['functions']))


def page_graph(t):
    """{page module's file name: {page modules it imports}} (relative imports of the page's own modules only)."""
    names = {Path(f).name for f in t.page}
    graph = {}
    for f in t.page:
        _, imports = t.js(f)[1]
        graph[Path(f).name] = {spec[2:] for _, spec in imports if spec.startswith('./') and spec[2:] in names}
    return graph


def page_imports(t):
    rule = "The page's imports"
    graph = page_graph(t)
    found = ['%s: %s imports app.js: no module imports the page\'s entry file; one that needs app.js\'s functions '
             'takes them as one argument object when it is made %s' % (rule, f, where(rule))
             for f, imports in sorted(graph.items()) if 'app.js' in imports]
    now, listed = cycles(graph), sorted(t.config['page cycles'])
    for c in now:
        if c not in listed:
            found.append('%s: an import cycle not listed: %s. Break it (a module that needs another\'s functions '
                         'takes them when it is made), or, if it is one listed that changed, write it as it is now '
                         'in %s %s' % (rule, c, CONFIG, where(rule)))
    for c in listed:
        if c not in now:
            found.append('%s: the listed import cycle %s is not there as listed: write the list as it is now (%s) '
                         'in %s %s' % (rule, c, '; '.join(now) or 'no cycles', CONFIG, where(rule)))
    return found


def shipped_imports(t):
    """{"<module> imports <module>": line} of each shipped module's import of a lab, research or test module."""
    modules, _ = t.shipped()
    by_name = {}
    for f in t.files:
        if f.endswith('.py'):
            by_name.setdefault(Path(f).stem, f)
    found = {}
    for path in modules:
        for name, line in imported_names(t.tree(path)):
            target = by_name.get(name)
            if target and t.kind(target):
                found.setdefault('%s imports %s' % (path, target), (line, t.kind(target)))
    return found


def what_ships_imports(t):
    rule = 'What ships imports'
    found, listed = shipped_imports(t), t.config['shipped imports']
    out = ['%s: %s (line %d), a module of %s: what the release ships does not import the lab, the research tools '
           'or a test; move what it needs into a product module %s' % (rule, key, line, kind, where(rule))
           for key, (line, kind) in sorted(found.items()) if key not in listed]
    out += ['%s: %s is listed in %s but no longer happens: take its entry out %s' % (rule, key, CONFIG, where(rule))
            for key in sorted(listed) if key not in found]
    return out


def is_sys_path(node):
    return (isinstance(node, ast.Attribute) and node.attr == 'path' and isinstance(node.value, ast.Name)
            and node.value.id == 'sys')


def path_changes(tree):
    """[(line, function name)] of the changes of sys.path inside functions of a module: a call of sys.path's insert,
    append, extend, remove, pop or clear, and an assignment to (or deletion from) sys.path or a part of it."""
    out = []

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            inside = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else \
                (function or '<lambda>') if isinstance(child, ast.Lambda) else function
            if inside:
                changed = False
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) \
                        and child.func.attr in PATH_CALLS and is_sys_path(child.func.value):
                    changed = True
                targets = (child.targets if isinstance(child, (ast.Assign, ast.Delete)) else
                           [child.target] if isinstance(child, (ast.AugAssign, ast.AnnAssign)) else [])
                for target in targets:
                    if is_sys_path(target) or (isinstance(target, ast.Subscript) and is_sys_path(target.value)):
                        changed = True
                if changed:
                    out.append((child.lineno, inside))
            visit(child, inside)
    visit(tree, None)
    return sorted(set(out))


def import_path(t):
    rule = 'The import path'
    modules, _ = t.shipped()
    found = {}
    for path in modules:
        for line, function in path_changes(t.tree(path)):
            found.setdefault('%s::%s' % (path, function), line)
    listed = t.config['path changes']
    out = ['%s: %s (line %d) changes sys.path inside a function: a folder goes on the path through paths.use(), at '
           'the top of the module %s' % (rule, key, line, where(rule))
           for key, line in sorted(found.items()) if key not in listed]
    out += ['%s: %s is listed in %s but changes sys.path no longer: take its entry out %s'
            % (rule, key, CONFIG, where(rule)) for key in sorted(listed) if key not in found]
    return out


def compiler_families(t):
    rule = 'Compiler families'
    out = []
    for path in sorted(t.config['compiler families']):
        if not (t.root / path).is_file():
            out.append('%s: %s is listed as a family of the compiler but not there: take its entry out, or write it '
                       'under its new name %s' % (rule, path, where(rule)))
            continue
        for name, line in imported_names(t.tree(path)):
            if name == 'compiler':
                out.append('%s: %s line %d imports the compiler: a family takes the tables it shares with the compiler '
                           'from a module both import, and reports through the compiler object it is given %s'
                           % (rule, path, line, where(rule)))
    return out


def config_form(t):
    rule = "structure.json's form"
    text = (t.root / CONFIG).read_text(encoding='utf-8')
    want = json.dumps(t.config, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    if text == want:
        return []
    got, wanted = text.splitlines(), want.splitlines()
    n = next((k for k, (a, b) in enumerate(zip(got, wanted)) if a != b), min(len(got), len(wanted)))
    return ['%s: %s is not sorted with one entry a line (two-space indent, LF): line %d is %r, should be %r %s'
            % (rule, CONFIG, n + 1, got[n] if n < len(got) else '', wanted[n] if n < len(wanted) else '', where(rule))]


CHECKS = (('File size', file_size), ('Function size', function_size), ("app.js's top level", app_top_level),
          ("The page's imports", page_imports), ('What ships imports', what_ships_imports),
          ('The import path', import_path), ('Compiler families', compiler_families),
          ("structure.json's form", config_form))


def problems(root):
    """{rule: [problem]} of the checkout at `root`."""
    t = Tree(root)
    return {rule: check(t) for rule, check in CHECKS}


class Structure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.t = Tree(ROOT)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest('not a Git checkout')

    def check(self, check):
        found = check(self.t)
        self.assertEqual(found, [], '\n' + '\n'.join(found))

    def test_file_size(self):
        self.check(file_size)

    def test_function_size(self):
        self.check(function_size)

    def test_app_js_top_level(self):
        self.check(app_top_level)

    def test_page_imports(self):
        self.check(page_imports)

    def test_what_ships_imports(self):
        self.check(what_ships_imports)

    def test_import_path(self):
        self.check(import_path)

    def test_compiler_families(self):
        self.check(compiler_families)

    def test_structure_json_form(self):
        self.check(config_form)

    def test_the_document_has_a_part_for_each_rule(self):
        doc = (ROOT / DOC).read_text(encoding='utf-8')
        self.assertIn('## 4. The limits and the exceptions', doc)
        part = doc.split('## 4. The limits and the exceptions', 1)[1].split('\n## ', 1)[0]
        self.assertEqual([r for r in RULES if '### %s\n' % r not in part], [])
        self.assertEqual([rule for rule, _ in CHECKS], list(RULES))


class Rules(unittest.TestCase):
    """The rules' own logic, on made-up numbers."""

    def test_a_ceiling_follows_its_file_down(self):
        ceilings = {'a.py': 2000, 'b.py': 2000, 'c.py': 2000, 'gone.py': 1800, 'listed.py': 1700}
        sizes = {'a.py': 2001, 'b.py': 1899, 'c.py': 1901, 'new.py': 1600, 'small.py': 1500, 'listed.py': 1400}
        found = '\n'.join(sized('File size', 'file', sizes, ceilings, 1500))
        self.assertIn('a.py has 2001 lines, over its ceiling of 2000', found)
        self.assertIn('b.py has 1899 lines, more than a twentieth under its ceiling of 2000: lower the ceiling to 1899',
                      found)
        self.assertNotIn('c.py', found)                          # under its ceiling by less than a twentieth
        self.assertIn('new.py has 1600 lines, over the limit of 1500', found)
        self.assertNotIn('small.py', found)                      # at the limit is within it
        self.assertIn('gone.py is listed', found)
        self.assertIn('listed.py has 1400 lines, within the limit of 1500 now: take its entry out', found)
        self.assertTrue(all(line.endswith('section %s: File size)' % SECTION) for line in found.splitlines()))

    def test_a_count_follows_down(self):
        self.assertEqual(counted('r', 'x', 100, 100), [])
        self.assertIn('over its ceiling of 100', counted('r', 'x', 101, 100)[0])
        self.assertIn('lower the ceiling to 94', counted('r', 'x', 94, 100)[0])
        self.assertEqual(counted('r', 'x', 96, 100), [])

    def test_cycles_are_the_strongly_connected_groups(self):
        graph = {'a.js': {'b.js'}, 'b.js': {'c.js'}, 'c.js': {'a.js', 'd.js'}, 'd.js': set(), 'e.js': {'e.js'},
                 'f.js': {'d.js'}}
        self.assertEqual(cycles(graph), ['a.js b.js c.js', 'e.js'])

    def test_path_changes_inside_functions_are_found(self):
        tree = ast.parse('import sys\nsys.path.insert(0, "x")\n'
                         'def f():\n    sys.path.insert(0, "y")\n    paths.use("bake")\n'
                         'class Cls:\n    def g(self):\n        sys.path[:0] = ["z"]\n        sys.path.append("w")\n'
                         'h = lambda: sys.path.remove("v")\n')
        self.assertEqual(path_changes(tree), [(4, 'f'), (8, 'g'), (9, 'g'), (10, '<lambda>')])


def main(argv=None):
    ap = argparse.ArgumentParser(description='Check the code shape of a checkout (structure.json\'s rules).')
    ap.add_argument('--root', type=Path, required=True, help='the checkout to check (a Git checkout)')
    args = ap.parse_args(argv)
    found = problems(args.root)
    for rule, items in found.items():
        print('%-24s %s' % (rule, 'ok' if not items else '%d problem(s)' % len(items)))
        for item in items:
            print('  ' + item)
    return 1 if any(found.values()) else 0


if __name__ == '__main__':
    if '--root' in sys.argv:
        sys.exit(main())
    unittest.main()
