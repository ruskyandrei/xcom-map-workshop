"""Checks that a move of code changed nothing: each function in the new file is the one it was in the old file.

  python tools/repo/moved_code.py <base commit> <old file> <new file> [--subst OLD=NEW ...] [--names a,b,c ...]

The old file is read as it was at <base commit> (through Git); the new one as it is in the working tree. They can be
the same path (a function moved inside its file) or two (functions moved out into a new module).

- Python: each function's or method's syntax tree, after the substitutions, is the old one's: a change of whitespace,
  line breaks, comments or a docstring's wrapping is no difference; anything else is. Methods may change class
  (`Compiler.effect_of` into `EffectEdits.effect_of`).
- JavaScript: each top-level function's text (`function f(...)`, `async function f`, `export function f`, and
  `const f = (...) =>` or `const f = function`), its tokens compared with whitespace and comments' wrapping aside.

--subst OLD=NEW (repeatable) replaces the text OLD by NEW in each old function before the comparison, in the order
given; the text before the first `=` is replaced by the text after it (`--subst self.=self.c.`).

--names picks the functions (comma-separated, repeatable). A name finds a function or method of that name in any
class (`effect_of`); a dotted name qualifies it (`Compiler.effect_of`, `Outer.Inner.f`); `OLD=NEW` names it on each
side (`Compiler.effect_of=EffectEdits.effect_of`, or a rename `_spec=spec`). A name that finds two functions on a side
is refused: qualify it. Without --names, every function in both files is compared (by its qualified name, else by its
own name when that name is in one class only on each side), and those in only one file are listed.

It prints each function compared, a diff of each that differs, and those missing. Exit status 1 if any differs or a
named one is missing on either side, 2 if it could not compare (an unknown commit, a file that does not parse, a name
that needs qualifying), else 0.

The function readers (python_functions, js_functions, js_tokens) are also what the structure test
(tools/repo/tests/test_structure.py) measures functions and app.js's top level with.
"""
import argparse
import ast
import bisect
from collections import namedtuple
import difflib
import os
from pathlib import Path
import subprocess
import sys
import textwrap

Token = namedtuple('Token', 'kind value start end depth')
Function = namedtuple('Function', 'name start_line end_line text')

# after these a `/` starts a regular expression, not a division
REGEX_AFTER_PUNCT = set('(,=:[!&|?{};+-*%<>~^') | {'=>', '...', '&&', '||', '??', '==', '===', '!=', '!==', '<=',
                                                   '>=', '+=', '-=', '*=', '/=', '%=', '&&=', '||=', '??='}
REGEX_AFTER_WORD = {'return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void', 'throw', 'case', 'do',
                    'else', 'yield', 'await'}
PUNCT3 = ('>>>=', '...', '===', '!==', '**=', '<<=', '>>=', '>>>', '&&=', '||=', '??=')
PUNCT2 = ('=>', '==', '!=', '<=', '>=', '&&', '||', '??', '?.', '++', '--', '+=', '-=', '*=', '/=', '%=', '&=', '|=',
          '^=', '**', '<<', '>>')
OPENERS, CLOSERS = '([{', ')]}'
# a line break does not end an arrow function's expression body after or before these
CONTINUES_AFTER = {'=>', '(', '[', '{', ',', '.', '?.', '?', ':', '=', '+', '-', '*', '/', '%', '**', '&&', '||', '??',
                   '==', '===', '!=', '!==', '<', '>', '<=', '>=', '&', '|', '^', '!', '~', '<<', '>>', '>>>', 'new',
                   'typeof', 'await', 'in', 'of', 'instanceof', 'void', 'delete'}
CONTINUES_BEFORE = {'.', '?.', '?', ':', '+', '-', '*', '/', '%', '**', '&&', '||', '??', '==', '===', '!=', '!==', '<',
                    '>', '<=', '>=', '&', '|', '^', ')', ']', '}', '=>', 'in', 'of', 'instanceof', ',', '<<', '>>', '>>>'}


def _is_name_char(c):
    return c.isalnum() or c in '_$' or ord(c) > 127


def js_tokens(text):
    """The tokens of JavaScript source: [Token(kind, value, start, end, depth)], kind one of name, number, string,
    template (a part of a template literal, up to its end or a `${`), regex, comment, punct. `depth` counts the
    brackets open around the token (an opener's depth is the one outside it, a closer's too), so the top level's
    tokens have depth 0."""
    tokens, stack, prev = [], [], None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace() or c == '﻿':
            i += 1
            continue
        start = i
        if text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            tokens.append(Token('comment', text[i:j], i, j, len(stack)))
            i = j
            continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            tokens.append(Token('comment', text[i:j], i, j, len(stack)))
            i = j
            continue
        if c in '\'"':
            j = i + 1
            while j < n and text[j] != c and text[j] != '\n':
                j += 2 if text[j] == '\\' else 1
            j = min(j + 1, n)
            prev = Token('string', text[i:j], i, j, len(stack))
            tokens.append(prev)
            i = j
            continue
        if c == '`' or (c == '}' and stack and stack[-1] == '${'):
            if c == '}':
                stack.pop()
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '`':
                    j += 1
                    break
                if text.startswith('${', j):
                    j += 2
                    break
                j += 1
            depth = len(stack)
            if text[start:j].endswith('${'):
                stack.append('${')
            prev = Token('template', text[start:j], start, j, depth)
            tokens.append(prev)
            i = j
            continue
        if c == '/':
            regex = (prev is None or (prev.kind == 'punct' and prev.value in REGEX_AFTER_PUNCT)
                     or (prev.kind == 'name' and prev.value in REGEX_AFTER_WORD)
                     or (prev.kind == 'template' and prev.value.endswith('${')))
            if regex:
                j, in_class = i + 1, False
                while j < n and text[j] != '\n':
                    ch = text[j]
                    if ch == '\\':
                        j += 2
                        continue
                    if ch == '[':
                        in_class = True
                    elif ch == ']':
                        in_class = False
                    elif ch == '/' and not in_class:
                        break
                    j += 1
                j += 1
                while j < n and _is_name_char(text[j]):
                    j += 1
                prev = Token('regex', text[i:j], i, j, len(stack))
                tokens.append(prev)
                i = j
                continue
        if _is_name_char(c) and not c.isdigit() or c == '#':
            j = i + 1
            while j < n and _is_name_char(text[j]):
                j += 1
            prev = Token('name', text[i:j], i, j, len(stack))
            tokens.append(prev)
            i = j
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and text[i + 1].isdigit()):
            j = i + 1
            while j < n and (_is_name_char(text[j]) or text[j] == '.'
                             or (text[j] in '+-' and text[j - 1] in 'eE' and not text[i:j].lower().startswith('0x'))):
                j += 1
            prev = Token('number', text[i:j], i, j, len(stack))
            tokens.append(prev)
            i = j
            continue
        value = next((p for p in PUNCT3 if text.startswith(p, i)), None) or \
            next((p for p in PUNCT2 if text.startswith(p, i)), None) or c
        if value == '?.' and i + 2 < n and text[i + 2].isdigit():
            value = '?'                     # a ? b : .5
        if value in OPENERS:
            prev = Token('punct', value, i, i + 1, len(stack))
            stack.append(value)
        elif value in CLOSERS:
            if stack:
                stack.pop()
            prev = Token('punct', value, i, i + 1, len(stack))
        else:
            prev = Token('punct', value, i, i + len(value), len(stack))
        tokens.append(prev)
        i = prev.end
    return tokens


def _pairs(tokens):
    """{index of an opener: index of its closer} over `tokens` (template parts' `${` are not counted)."""
    pairs, stack = {}, []
    for k, t in enumerate(tokens):
        if t.kind == 'punct' and t.value in OPENERS:
            stack.append(k)
        elif t.kind == 'punct' and t.value in CLOSERS and stack:
            pairs[stack.pop()] = k
    return pairs


class _Lines:
    def __init__(self, text):
        self.starts = [0] + [k + 1 for k, c in enumerate(text) if c == '\n']

    def line(self, offset):
        return bisect.bisect_right(self.starts, offset)


def _arrow_end(code, b, lines):
    """The index of the last token of an arrow function's expression body starting at code[b]."""
    k = b
    while True:
        if code[k].kind == 'punct' and code[k].value in OPENERS:
            k = code[k].pair
        nxt = k + 1
        if nxt >= len(code):
            return k
        t, last = code[nxt], code[k]
        if t.depth == 0 and t.kind == 'punct' and t.value in (';', ','):
            return k
        if lines.line(t.start) > lines.line(last.end) and t.depth == 0 \
                and not (last.kind in ('punct', 'name') and last.value in CONTINUES_AFTER) \
                and not (t.kind in ('punct', 'name') and t.value in CONTINUES_BEFORE) \
                and t.kind != 'template':
            return k
        k = nxt


def js_functions(text):
    """{name: Function(name, start_line, end_line, text)} of the top-level functions of JavaScript source: function
    declarations (export, default, async, generators) and `const|let|var NAME = ` an arrow function or a function
    expression. Lines are counted from 1; the text runs from the first token (`export`, `async`, `function`, `const`)
    to the function's last."""
    all_tokens = js_tokens(text)
    code = [t for t in all_tokens if t.kind != 'comment']
    pairs = _pairs(code)
    code = [_Tok(*t, pair=pairs.get(k)) for k, t in enumerate(code)]
    lines = _Lines(text)
    out = {}

    def val(k):
        return code[k].value if k < len(code) and code[k].kind in ('name', 'punct') else None

    def add(name, first, last):
        start, end = code[first].start, code[last].end
        out[name] = Function(name, lines.line(start), lines.line(end - 1), text[start:end])

    k = 0
    while k < len(code):
        if not _statement_start(code, k, lines):
            k += 1
            continue
        j = k
        if val(j) == 'export':
            j += 1
        if val(j) == 'default':
            j += 1
        f = j + 1 if val(j) == 'async' and val(j + 1) == 'function' else j
        if val(f) == 'function':
            f += 1
            if val(f) == '*':
                f += 1
            if f < len(code) and code[f].kind == 'name' and val(f + 1) == '(' and code[f + 1].pair is not None:
                close = code[f + 1].pair
                if val(close + 1) == '{' and code[close + 1].pair is not None:
                    add(code[f].value, k, code[close + 1].pair)
                    k = code[close + 1].pair + 1
                    continue
        if val(j) in ('const', 'let', 'var') and j + 1 < len(code) and code[j + 1].kind == 'name' and val(j + 2) == '=':
            name, v = code[j + 1].value, j + 3
            if val(v) == 'async' and (val(v + 1) in ('(', 'function') or
                                      (v + 1 < len(code) and code[v + 1].kind == 'name' and val(v + 2) == '=>')):
                v += 1
            body = None
            if val(v) == 'function':
                g = v + 1
                if val(g) == '*':
                    g += 1
                if g < len(code) and code[g].kind == 'name' and val(g + 1) == '(':
                    g += 1
                if val(g) == '(' and code[g].pair is not None and val(code[g].pair + 1) == '{':
                    end = code[code[g].pair + 1].pair
                    if end is not None:
                        add(name, k, end)
                        k = end + 1
                        continue
            elif val(v) == '(' and code[v].pair is not None and val(code[v].pair + 1) == '=>':
                body = code[v].pair + 2
            elif v < len(code) and code[v].kind == 'name' and val(v + 1) == '=>':
                body = v + 2
            if body is not None and body < len(code):
                end = code[body].pair if val(body) == '{' else _arrow_end(code, body, lines)
                if end is not None:
                    add(name, k, end)
                    k = end + 1
                    continue
        k += 1
    return out


_Tok = namedtuple('_Tok', 'kind value start end depth pair')


def js_inner_functions(function):
    """The functions declared at the top of a JavaScript function's body (as js_functions finds them at a file's top
    level), named `outer.inner`, their lines counted in the file the outer function is in."""
    toks = [t for t in js_tokens(function.text) if t.kind != 'comment']
    params = False
    for t in toks:
        params = params or (t.depth == 0 and t.value in (')', '=>'))
        if params and t.depth == 0 and t.value == '{':
            break
    else:
        return {}
    body = function.text[t.end:toks[-1].start]
    shift = function.start_line - 1 + function.text[:t.end].count('\n')
    return {'%s.%s' % (function.name, name): Function('%s.%s' % (function.name, name), f.start_line + shift,
                                                      f.end_line + shift, f.text)
            for name, f in js_functions(body).items()}


def _statement_start(code, k, lines):
    """Whether code[k] can begin a top-level statement: it is at depth 0, and first, or after a `;` or a `}` of the
    top level, or on a later line than the token before it."""
    t = code[k]
    if t.depth != 0:
        return False
    if k == 0:
        return True
    before = code[k - 1]
    return (before.kind == 'punct' and before.value in (';', '}')) or lines.line(before.end - 1) < lines.line(t.start)


def js_top_level(text):
    """The top-level statements' first tokens of JavaScript source that `js_functions` would not see inside a
    function: [(line, keyword)] for each `let`, `const`, `var`, `import` and `export` beginning a statement at the
    top level, and the modules it imports ([(line, specifier)], static `import ... from '...'` and
    `export ... from '...'`)."""
    code = [t for t in js_tokens(text) if t.kind != 'comment']
    pairs = _pairs(code)
    code = [_Tok(*t, pair=pairs.get(k)) for k, t in enumerate(code)]
    lines = _Lines(text)
    starts, imports = [], []
    for k, t in enumerate(code):
        if t.kind != 'name' or not _statement_start(code, k, lines):
            continue
        if t.value in ('let', 'const', 'var', 'import', 'export'):
            starts.append((lines.line(t.start), t.value))
        if k + 1 >= len(code):
            continue
        nxt = code[k + 1]
        if t.value == 'import' and nxt.kind == 'string':
            imports.append((lines.line(t.start), nxt.value[1:-1]))                 # import './x.js'
        elif (t.value == 'import' and nxt.value not in ('(', '.')) or (t.value == 'export' and nxt.value in ('{', '*')):
            # import a, {b, c} from '...' / import * as n from '...' / export {a} from '...' / export * from '...'
            m, steps = k + 1, 0
            while m < len(code) and steps < 12 and code[m].value not in ('from', ';'):
                m = (code[m].pair + 1) if code[m].value == '{' and code[m].pair is not None else m + 1
                steps += 1
            if m + 1 < len(code) and code[m].value == 'from' and code[m + 1].kind == 'string':
                imports.append((lines.line(t.start), code[m + 1].value[1:-1]))
    return starts, imports


def js_normal(text):
    """JavaScript text as compared: its tokens, a run of line comments joined into one, a comment's words joined by
    single spaces (so rewrapping a comment is no change)."""
    out, comment = [], None
    for t in js_tokens(text):
        if t.kind == 'comment':
            words = t.value[2:-2] if t.value.startswith('/*') else t.value[2:]
            if t.value.startswith('//') and comment is not None:
                comment += words.split()
            else:
                if comment is not None:
                    out.append('//' + ' '.join(comment))
                    comment = None
                if t.value.startswith('//'):
                    comment = words.split()
                else:
                    out.append('/*' + ' '.join(words.split()) + '*/')
            continue
        if comment is not None:
            out.append('//' + ' '.join(comment))
            comment = None
        out.append(t.value)
    if comment is not None:
        out.append('//' + ' '.join(comment))
    return out


def python_functions(text):
    """{qualified name: Function(name, start_line, end_line, text)} of the module-level functions and the methods of
    classes (at any depth of classes: `Outer.Inner.f`) in Python source; a function's own nested functions belong to
    it. Its lines run from its `def` to its last line; its text from its first decorator to its last line, the first
    line's indentation taken off each."""
    tree = ast.parse(text)
    lines = text.splitlines()
    out = {}

    def walk(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                seg = lines[first - 1:node.end_lineno]
                indent = len(seg[0]) - len(seg[0].lstrip())
                seg = [line[indent:] if line[:indent].isspace() else line.lstrip() if not line.strip() else line
                       for line in seg]
                out[prefix + node.name] = Function(prefix + node.name, node.lineno, node.end_lineno, '\n'.join(seg) + '\n')
            elif isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + '.')
            elif isinstance(node, ast.If):
                walk(node.body, prefix)
                walk(node.orelse, prefix)
            elif isinstance(node, ast.Try):
                walk(node.body, prefix)
                for h in node.handlers:
                    walk(h.body, prefix)
                walk(node.orelse, prefix)
                walk(node.finalbody, prefix)
            elif isinstance(node, ast.With):
                walk(node.body, prefix)

    walk(tree.body, '')
    return out


def python_normal(text):
    """A Python function's text as compared: its syntax tree without its name and line numbers, docstrings' words
    joined by single spaces (so re-indenting or rewrapping a docstring is no change)."""
    fn = ast.parse(text).body[0]
    fn.name = ''
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body \
                and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body[0].value.value = ' '.join(node.body[0].value.value.split())
    return ast.dump(fn, include_attributes=False)


def kind_of(path):
    suffix = Path(path).suffix.lower()
    if suffix == '.py':
        return 'python'
    if suffix in ('.js', '.mjs'):
        return 'js'
    raise ValueError('%s: neither Python (.py) nor JavaScript (.js, .mjs)' % path)


def functions(text, kind):
    return python_functions(text) if kind == 'python' else js_functions(text)


def substitute(text, substs):
    for old, new in substs:
        text = text.replace(old, new)
    return text


class Ambiguous(ValueError):
    pass


def find(funcs, spec, side):
    """The qualified name in `funcs` that `spec` names (a name, or a dotted one matched on whole components), or None."""
    found = [q for q in funcs if q == spec or q.endswith('.' + spec)]
    if len(found) > 1:
        raise Ambiguous('%s names %d functions in the %s file (%s): qualify it' % (spec, len(found), side, ', '.join(found)))
    return found[0] if found else None


def pairs_of(old, new, names):
    """[(label, old qualified name or None, new qualified name or None)] to compare, and the lists of functions only
    in the old and only in the new file (empty when names are given)."""
    if names:
        out = []
        for spec in names:
            a, _, b = spec.partition('=')
            b = b or a
            out.append((spec, find(old, a, 'old'), find(new, b, 'new')))
        return out, [], []
    both = [q for q in old if q in new]
    rest_old = [q for q in old if q not in new]
    rest_new = [q for q in new if q not in old]
    out = [(q, q, q) for q in both]

    def own(q):
        return q.rsplit('.', 1)[-1]
    for q in list(rest_old):
        mine = [r for r in rest_old if own(r) == own(q)]
        theirs = [r for r in rest_new if own(r) == own(q)]
        if len(mine) == 1 and len(theirs) == 1:
            out.append(('%s -> %s' % (q, theirs[0]), q, theirs[0]))
            rest_old.remove(q)
            rest_new.remove(theirs[0])
    return out, rest_old, rest_new


def unified(before, after, old_label, new_label):
    """A unified diff of two functions' texts that leaves out lines differing only in whitespace (a re-indented
    continuation line is no change here either)."""
    a, b = textwrap.dedent(before).splitlines(), textwrap.dedent(after).splitlines()
    key = [' '.join(line.split()) for line in a], [' '.join(line.split()) for line in b]
    out = ['--- %s\n' % old_label, '+++ %s\n' % new_label]
    for group in difflib.SequenceMatcher(None, *key, autojunk=False).get_grouped_opcodes(2):
        out.append('@@ -%d +%d @@\n' % (group[0][1] + 1, group[0][3] + 1))
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                out += [' %s\n' % line for line in a[i1:i2]]
                continue
            out += ['-%s\n' % line for line in a[i1:i2]]
            out += ['+%s\n' % line for line in b[j1:j2]]
    return ''.join(out)


def compare(old_text, new_text, kind, names=(), substs=()):
    """The comparison of two versions of a file: dict(results=[(label, status, diff)], only_old=[...],
    only_new=[...]); status is 'same', 'DIFFERS' or 'MISSING' (with the side in the diff's place)."""
    old, new = functions(old_text, kind), functions(new_text, kind)
    pairs, only_old, only_new = pairs_of(old, new, names)
    results = []
    for label, a, b in pairs:
        if a is None or b is None:
            results.append((label, 'MISSING', 'not in the %s file' % ('old' if a is None else 'new')
                            if (a is None) != (b is None) else 'in neither file'))
            continue
        before, after = substitute(old[a].text, substs), new[b].text
        if kind == 'python':
            try:
                same = python_normal(before) == python_normal(after)
            except SyntaxError as e:
                raise ValueError('%s does not parse after the substitutions: %s' % (a, e))
        else:
            same = js_normal(before) == js_normal(after)
        diff = '' if same else unified(before, after, 'old %s%s' % (a, ' (after the substitutions)' if substs else ''),
                                       'new %s' % b)
        results.append((label, 'same' if same else 'DIFFERS', diff))
    return dict(results=results, only_old=only_old, only_new=only_new)


def read_old(base, path):
    """The file at `path` (as given on the command line) as it was at commit `base`."""
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if top.returncode:
        raise ValueError('not in a Git checkout: %s' % top.stderr.strip())
    rel = os.path.relpath(os.path.abspath(path), top.stdout.strip()).replace('\\', '/')
    out = subprocess.run(['git', 'show', '%s:%s' % (base, rel)], capture_output=True, cwd=top.stdout.strip())
    if out.returncode:
        raise ValueError('cannot read %s at %s: %s' % (rel, base, out.stderr.decode('utf-8', 'replace').strip()))
    return out.stdout.decode('utf-8')


def report(result, out=sys.stdout):
    """Prints the comparison; returns the exit status (1 if a function differs or is missing)."""
    counts = {'same': 0, 'DIFFERS': 0, 'MISSING': 0}
    for label, status, diff in result['results']:
        counts[status] += 1
        print('%-8s %s%s' % (status, label, ': ' + diff if status == 'MISSING' else ''), file=out)
        if status == 'DIFFERS':
            print(diff.rstrip('\n'), file=out)
    for side in ('old', 'new'):
        rest = result['only_' + side]
        if rest:
            print('only in the %s file (%d): %s' % (side, len(rest), ', '.join(rest)), file=out)
    print('%d compared: %d the same, %d differ, %d missing' % (
        len(result['results']), counts['same'], counts['DIFFERS'], counts['MISSING']), file=out)
    return 1 if counts['DIFFERS'] or counts['MISSING'] else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('base', help='the commit the old file is read at')
    ap.add_argument('old', help='the old file (its path in the working tree; read at the base commit)')
    ap.add_argument('new', help='the new file (read from the working tree)')
    ap.add_argument('--subst', action='append', default=[], metavar='OLD=NEW',
                    help='replace OLD by NEW in each old function before comparing (repeatable, in order)')
    ap.add_argument('--names', action='append', default=[], metavar='a,b,c',
                    help='the functions to compare (comma-separated, repeatable): name, Class.name, or old=new')
    args = ap.parse_args(argv)
    substs = []
    for s in args.subst:
        if '=' not in s:
            ap.error('--subst %r has no =: write OLD=NEW' % s)
        substs.append(tuple(s.split('=', 1)))
    names = [n.strip() for group in args.names for n in group.split(',') if n.strip()]
    try:
        kind = kind_of(args.new)
        if kind_of(args.old) != kind:
            raise ValueError('%s and %s are not the same language' % (args.old, args.new))
        old_text = read_old(args.base, args.old)
        new_text = Path(args.new).read_text(encoding='utf-8')
        print('old: %s at %s\nnew: %s (working tree)' % (args.old, args.base, args.new))
        result = compare(old_text, new_text, kind, names, substs)
    except (ValueError, OSError, SyntaxError) as e:
        print('moved_code: %s' % e, file=sys.stderr)
        return 2
    return report(result)


if __name__ == '__main__':
    sys.exit(main())
