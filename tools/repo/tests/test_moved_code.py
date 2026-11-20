"""The move checker (tools/repo/moved_code.py), on small made-up files: a function moved clean is the same, a changed
one differs with a diff, in Python (a method moved into another class) and in JavaScript (top-level functions)."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import moved_code  # noqa: E402

OLD_PY = '''\
import json


def helper(x):
    return x + 1


class Compiler:
    def effect_of(self, target):
        """The effect a target names,
        or None."""
        if not isinstance(target, dict):
            return None
        return self.effects.get(target['actor'],
                                None)  # by its actor

    def spec(self):
        return dict(effects=self.effects)
'''

NEW_PY = '''\
class EffectEdits:
    def __init__(self, c):
        self.c = c

    def effect_of(self, target):
        """The effect a target names, or None."""
        if not isinstance(target, dict):
            return None
        # a comment that was not there
        return self.c.effects.get(target['actor'], None)

    def spec(self):
        return dict(effects=self.c.effects, more=True)


def helper(x):
    return x + 1
'''

OLD_JS = '''\
import { x } from './x.js';
const PATTERN = /[{}\\/]+/g;   // braces in a regular expression

function plain(a, b) {
  const s = `a ${ {k: '}'}.k } b`;          // a brace in a template and a string
  return a.replace(PATTERN, '{') + s + b / 2;
}

export async function loaded(url) {
  /* a comment { with a brace */
  const r = await fetch(url);
  return r.json();
}

const short = (n) => n * 2;
const later = async ({ a, b } = {}) => {
  return a + b;
};
'''

NEW_JS = '''\
export function plain(a, b) {
    const s = `a ${ {k: '}'}.k } b`;   // a brace in a template and a string
    return a.replace(PATTERN, '{') +
        s + b / 2;
}

const short = (n) => n * 3;

export async function loaded(url) {
  /* a comment {
     with a brace */
  const r = await fetch(url);
  return r.json();
}
'''


class Python(unittest.TestCase):
    def test_a_method_moved_into_another_class(self):
        r = moved_code.compare(OLD_PY, NEW_PY, 'python', names=['effect_of', 'spec', 'helper'],
                               substs=[('self.', 'self.c.')])
        status = {label: s for label, s, _ in r['results']}
        # rewrapped docstring, a comment, a line break: the same tree
        self.assertEqual(status, {'effect_of': 'same', 'spec': 'DIFFERS', 'helper': 'same'})
        diff = dict((label, d) for label, _, d in r['results'])['spec']
        self.assertIn('-return dict(effects=self.c.effects)', diff.replace('    ', ''))
        self.assertIn('+return dict(effects=self.c.effects, more=True)', diff.replace('    ', ''))

    def test_without_the_substitution_the_move_differs(self):
        r = moved_code.compare(OLD_PY, NEW_PY, 'python', names=['effect_of'])
        self.assertEqual(r['results'][0][1], 'DIFFERS')

    def test_without_names_every_function_in_both_is_compared(self):
        r = moved_code.compare(OLD_PY, NEW_PY, 'python', substs=[('self.', 'self.c.')])
        status = {label: s for label, s, _ in r['results']}
        self.assertEqual(status, {'helper': 'same', 'Compiler.effect_of -> EffectEdits.effect_of': 'same',
                                  'Compiler.spec -> EffectEdits.spec': 'DIFFERS'})
        self.assertEqual((r['only_old'], r['only_new']), ([], ['EffectEdits.__init__']))

    def test_qualified_names_renames_and_missing_ones(self):
        r = moved_code.compare(OLD_PY, NEW_PY, 'python', substs=[('self.', 'self.c.')],
                               names=['Compiler.effect_of=EffectEdits.effect_of', 'gone', 'spec=__init__'])
        self.assertEqual([s for _, s, _ in r['results']], ['same', 'MISSING', 'DIFFERS'])
        self.assertEqual(r['results'][1][2], 'in neither file')

    def test_a_name_on_two_classes_must_be_qualified(self):
        two = NEW_PY + '\n\nclass Other:\n    def spec(self):\n        return 1\n'
        with self.assertRaises(moved_code.Ambiguous):
            moved_code.compare(OLD_PY, two, 'python', names=['spec'])
        r = moved_code.compare(OLD_PY, two, 'python', names=['spec=Other.spec'])
        self.assertEqual(r['results'][0][1], 'DIFFERS')

    def test_a_function_is_measured_from_its_def(self):
        funcs = moved_code.python_functions('@decorated\ndef f():\n    return 1\n\n\nclass Cls:\n    def g(self):\n'
                                            '        def inner():\n            pass\n        return inner\n')
        self.assertEqual(sorted(funcs), ['Cls.g', 'f'])
        self.assertEqual((funcs['f'].start_line, funcs['f'].end_line), (2, 3))
        self.assertEqual((funcs['Cls.g'].start_line, funcs['Cls.g'].end_line), (7, 10))
        self.assertTrue(funcs['f'].text.startswith('@decorated'))


class JavaScript(unittest.TestCase):
    def test_the_top_level_functions_are_found_whole(self):
        funcs = moved_code.js_functions(OLD_JS)
        self.assertEqual(sorted(funcs), ['later', 'loaded', 'plain', 'short'])
        self.assertEqual((funcs['plain'].start_line, funcs['plain'].end_line), (4, 7))
        self.assertEqual((funcs['loaded'].start_line, funcs['loaded'].end_line), (9, 13))
        self.assertEqual(funcs['short'].text, 'const short = (n) => n * 2')
        self.assertEqual((funcs['later'].start_line, funcs['later'].end_line), (16, 18))

    def test_moved_clean_and_changed(self):
        r = moved_code.compare(OLD_JS, NEW_JS, 'js')
        status = {label: s for label, s, _ in r['results']}
        # loaded re-indented with a comment rewrapped: the same; plain re-indented and a line broken, but now
        # exported: changed; n * 3: changed
        self.assertEqual(status, {'plain': 'DIFFERS', 'loaded': 'same', 'short': 'DIFFERS'})
        self.assertEqual(r['only_old'], ['later'])
        r = moved_code.compare(OLD_JS, NEW_JS.replace('export function plain', 'function plain'), 'js',
                               names=['plain', 'short'], substs=[('n * 2', 'n * 3')])
        self.assertEqual([s for _, s, _ in r['results']], ['same', 'same'])

    def test_the_top_level_statements_and_imports(self):
        starts, imports = moved_code.js_top_level(OLD_JS + "let a = 1, b;\nimport './side.js';\n"
                                                  "export { q } from './q.js';\nfunction f() { let inner; }\n")
        self.assertEqual([k for _, k in starts], ['import', 'const', 'export', 'const', 'const', 'let', 'import',
                                                  'export'])
        self.assertEqual([s for _, s in imports], ['./x.js', './side.js', './q.js'])

    def test_a_factorys_inner_functions(self):
        text = ('export function createThing(deps) {\n  let n = 0;\n  function one() {\n    return n;\n  }\n'
                '  const two = () => {\n    n += 1;\n  };\n  return { one, two };\n}\n')
        outer = moved_code.js_functions(text)['createThing']
        inner = moved_code.js_inner_functions(outer)
        self.assertEqual({k: (f.start_line, f.end_line) for k, f in inner.items()},
                         {'createThing.one': (3, 5), 'createThing.two': (6, 8)})

    def test_a_function_moved_into_a_factory_is_found_by_its_name(self):
        old = 'let n = 0;\nfunction one() {\n  return n;\n}\nfunction keep() {\n  return 1;\n}\n'
        new = ('export function createThing({ n }) {\n  function one() {\n    return n;\n  }\n  return { one };\n}\n'
               'function keep() {\n  return 1;\n}\n')
        named = moved_code.compare(old, new, 'js', names=['one'])
        self.assertEqual([(label, status) for label, status, _ in named['results']], [('one', 'same')])
        paired = moved_code.compare(old, new, 'js')
        self.assertIn(('one -> createThing.one', 'same'), [(label, status) for label, status, _ in paired['results']])
        self.assertIn(('keep', 'same'), [(label, status) for label, status, _ in paired['results']])
        changed = moved_code.compare(old, new.replace('return n;', 'return n + 1;'), 'js', names=['one'])
        self.assertEqual(changed['results'][0][1], 'DIFFERS')


@unittest.skipUnless(shutil.which('git'), 'needs Git')
class CommandLine(unittest.TestCase):
    def test_the_old_file_is_read_at_the_base_and_the_exit_status_says_if_anything_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'old.py').write_text(OLD_PY, encoding='utf-8', newline='\n')
            git = ['git', '-C', str(tmp), '-c', 'core.autocrlf=false']
            subprocess.run(git + ['init', '-q'], check=True)
            subprocess.run(git + ['add', 'old.py'], check=True)
            # a tree is enough for <base>:<path>, so no commit (and no identity) is needed
            base = subprocess.run(git + ['write-tree'], check=True, capture_output=True, text=True).stdout.strip()
            (tmp / 'old.py').write_text('# the working tree\'s copy is not the one read\n', encoding='utf-8')
            (tmp / 'new.py').write_text(NEW_PY, encoding='utf-8', newline='\n')
            tool = [sys.executable, '-B', str(HERE.parent / 'moved_code.py'), base, 'old.py', 'new.py']

            def run(*extra):
                return subprocess.run(tool + list(extra), cwd=tmp, capture_output=True, text=True)
            ok = run('--subst', 'self.=self.c.', '--names', 'effect_of,helper')
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertIn('2 compared: 2 the same', ok.stdout)
            bad = run('--subst', 'self.=self.c.', '--names', 'effect_of', '--names', 'spec')
            self.assertEqual(bad.returncode, 1)
            self.assertIn('DIFFERS  spec', bad.stdout)
            self.assertIn('+    return dict(effects=self.c.effects, more=True)', bad.stdout)
            # pairs from a file, for an OLD holding "=" (here the same substitution, written as a pair)
            (tmp / 'pairs.json').write_text('[["self.", "self.c."]]', encoding='utf-8')
            paired = run('--subst-file', 'pairs.json', '--names', 'effect_of,helper')
            self.assertEqual(paired.returncode, 0, paired.stdout + paired.stderr)
            (tmp / 'eq.json').write_text('[["dict(effects=self.effects)", "dict(effects=self.c.effects, more=True)"]]',
                                         encoding='utf-8')
            self.assertEqual(run('--names', 'spec').returncode, 1)
            self.assertEqual(run('--subst-file', 'eq.json', '--names', 'spec').returncode, 0)
            (tmp / 'bad.json').write_text('{"self.": "self.c."}', encoding='utf-8')
            self.assertEqual(run('--subst-file', 'bad.json').returncode, 2)
            self.assertEqual(run('--names', 'nowhere').returncode, 1)
            self.assertEqual(run('--names', 'spec', 'x').returncode, 2)       # argparse: an extra argument
            self.assertEqual(subprocess.run(tool[:3] + ['no-such-commit', 'old.py', 'new.py'], cwd=tmp,
                                            capture_output=True, text=True).returncode, 2)


if __name__ == '__main__':
    unittest.main()
