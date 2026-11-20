"""The page's names: a name in tools/viewer/web/*.js that is neither declared, imported nor a known global, and an
import nothing uses (refactor plan, decision D9).

  python tools/viewer/tests/web_names.py [--scratch <folder>] [<file.js> ...]

ESLint (ESLINT below, an exact version) with three rules only, no-undef, no-import-assign and an unused-import
rule, over the page's modules (not vendor/) as ES modules in the browser; the settings and the known globals, each
exception with its reason, are in web_names.config.mjs beside this. ESLint and the `globals` package are installed by npm into a scratch
folder (default <repo>/.scratch/eslint, which Git ignores; never a node_modules in the repository), made on the first
run (that needs the network), and run from there through npx. A move that leaves a name behind throws only when its
line runs, and no browser check runs every line: this finds it without running any.

Prints each finding as file:line: name, and exits 1 if there is any; 2 if node, npm or npx is missing or ESLint could
not be installed or run. Run by hand and by the page's refactor stages; run_tests.py does not run it.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ESLINT = '10.14.0'
GLOBALS = '17.14.0'
REPO = Path(__file__).resolve().parents[3]
WEB = REPO / 'tools' / 'viewer' / 'web'
CONFIG = Path(__file__).with_name('web_names.config.mjs')


def cannot(why):
    print(f'web_names: {why}', file=sys.stderr)
    raise SystemExit(2)


def installed(folder, package):
    try:
        return json.loads((folder / 'node_modules' / package / 'package.json').read_text(encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError):
        return None


def prepare(folder, npm):
    """The scratch folder with ESLINT and GLOBALS installed (installed again when either is another version)."""
    wanted = json.dumps(dict(private=True, dependencies=dict(eslint=ESLINT, globals=GLOBALS)), indent=1) + '\n'
    if installed(folder, 'eslint') == ESLINT and installed(folder, 'globals') == GLOBALS:
        return
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'package.json').write_text(wanted, encoding='utf-8', newline='\n')
    print(f'web_names: installing eslint {ESLINT} and globals {GLOBALS} into {folder}', file=sys.stderr, flush=True)
    done = subprocess.run([npm, 'install', '--no-audit', '--no-fund', '--loglevel=error'], cwd=folder, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    if done.returncode != 0 or installed(folder, 'eslint') != ESLINT:
        cannot(f'npm could not install ESLint into {folder}:\n{(done.stdout + done.stderr).strip()}')


def where(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('files', nargs='*', help='these files instead of the page\'s modules (tools/viewer/web/*.js)')
    ap.add_argument('--scratch', type=Path, default=REPO / '.scratch' / 'eslint',
                    help='the folder ESLint is installed into and run from (default: <repo>/.scratch/eslint)')
    args = ap.parse_args()
    tools = {name: shutil.which(name) for name in ('node', 'npm', 'npx')}
    missing = [name for name, path in tools.items() if not path]
    if missing: cannot(f'{", ".join(missing)} not found: this check needs Node.js (with npm and npx) on the path')
    folder = args.scratch.resolve()
    prepare(folder, tools['npm'])
    files = [Path(f).resolve() for f in args.files] or sorted(WEB.glob('*.js'))
    done = subprocess.run([tools['npx'], '--prefix', str(folder), '--no', '--', 'eslint', '--config', str(CONFIG), '--format', 'json',
                           *map(str, files)],
                          cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=dict(os.environ, WEB_NAMES_SCRATCH=str(folder)))
    try:
        results = json.loads(done.stdout) if done.returncode in (0, 1) else None
    except ValueError:
        results = None
    if results is None: cannot(f'ESLint did not run (exit {done.returncode}):\n{(done.stdout + done.stderr).strip()}')
    if len(results) != len(files): cannot(f'ESLint read {len(results)} of the {len(files)} files')
    found = []
    for result in results:      # (a file ESLint left out, or could not parse, is a finding too: its message says which)
        for m in result['messages']:
            name, rule, words = re.match(r"'([^']+)'", m['message']), m.get('ruleId'), m['message'].rstrip('.')
            found.append(f"{where(result['filePath'])}:{m.get('line', 0)}: "
                         + (f'{name.group(1)} ({rule}: {words})' if name and rule else f'{words} ({rule or "eslint"})'))
    for line in found: print(line)
    print(f'web_names: {len(results)} files, ' + (f'{len(found)} findings' if found else 'clean') + f' (eslint {ESLINT})')
    if found: raise SystemExit(1)


if __name__ == '__main__': main()
