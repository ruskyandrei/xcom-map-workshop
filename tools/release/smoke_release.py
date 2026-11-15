"""Basic smoke tests of a made release (the release skill, .claude/skills/release): run after make_release.py, before
anything is published. Nothing is installed in the game and nothing outside dist/ is written.

  python tools/release/smoke_release.py [--version <v>] [--dist dist/release] [--port 8795] [--map URB_Bar]
                                        [--only <browser smoke checks>] [--no-browser] [--keep]

1. The files: XCOM-Map-Workshop-<v>.zip and -Setup.exe are there; their sizes and SHA-256s are printed.
2. The zip read back: one folder XCOM-Map-Workshop-<v>; VERSION.txt names the version; README.md is
   tools/release/GETTING-STARTED.md; "User Guide.html" has the version's "New in <v>" table; the launcher, the licence
   files and the bundled Python are there; every file of ours under tools/ (compiled .pyc aside) equals the repository's.
3. The zip unpacked to dist/smoke-<v> (a short path: the bundled Python's paths pass Windows' 260 characters in the
   scratchpad) and started with its own Python, as its launcher does, on a test port (8790-8799), with scratch
   projects and builds folders and --dry-play: /setup.json names the version and the editor; / and /maps.json answer;
   the map is listed.
4. In a headless browser (Playwright, Edge, as the browser smoke): the map opens, the help names
   "XCOM Map Workshop <v> (preview)", and the page logs no errors; then tools/viewer/tests/browser_smoke.py --only
   <checks> (read-only checks: light-grid and text-select by default) against the same server.
5. The server stopped and the unpacked folder deleted (--keep leaves it).

Prints PASS or FAIL for each step, and exits 1 if any failed. The installer itself isn't run: it writes the editor's
settings and shortcuts on this computer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / 'tools' / 'viewer'))
from version import NAME, VERSION  # noqa: E402

NEEDED = ('VERSION.txt', 'README.md', 'User Guide.html', 'XCOM Map Workshop.cmd', 'LICENSE.txt',
          'THIRD-PARTY-NOTICES.txt', 'python/python.exe', 'tools/viewer/viewer.py')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def check_zip(zip_path, version, repo=REPO):
    """Problems found reading the zip back (empty: none), and how many of our files were compared."""
    problems, compared = [], 0
    root = 'XCOM-Map-Workshop-%s/' % version
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        if not names:
            return ['the zip is empty'], 0
        outside = [n for n in names if not n.startswith(root)]
        if outside:
            problems.append('%d entries outside %s (first: %s)' % (len(outside), root, outside[0]))
        have = set(names)
        for needed in NEEDED:
            if root + needed not in have:
                problems.append('missing: %s' % needed)
        if root + 'VERSION.txt' in have:
            text = z.read(root + 'VERSION.txt').decode('ascii', 'replace').strip()
            if text != '%s %s' % (NAME, version):
                problems.append('VERSION.txt says %r' % text)
        if root + 'README.md' in have and z.read(root + 'README.md') != (repo / 'tools/release/GETTING-STARTED.md').read_bytes():
            problems.append('README.md is not tools/release/GETTING-STARTED.md')
        if root + 'User Guide.html' in have and ('New in %s' % version).encode() not in z.read(root + 'User Guide.html'):
            problems.append('the user guide has no "New in %s" table' % version)
        for name in names:
            rel = name[len(root):]
            if not rel.startswith('tools/') or rel.endswith('.pyc') or '/__pycache__/' in rel:
                continue
            ours = repo / rel
            if not ours.is_file():
                problems.append('not in the repository: %s' % rel)
            elif z.read(name) != ours.read_bytes():
                problems.append('differs from the repository: %s' % rel)
            else:
                compared += 1
    return problems, compared


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def wait_up(base, proc, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            if get(base + 'maps.json', 3)[0] == 200:
                return True
        except OSError:
            time.sleep(0.5)
    return False


def browser_check(url, version):
    """Open the map in headless Edge: the scene opens, the help names the version, no page errors."""
    from playwright.sync_api import sync_playwright
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport=dict(width=1600, height=1000))
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.goto(url)
        page.wait_for_function("window.viewer && document.querySelector('#loading').hidden", timeout=180000)
        help_ok = page.evaluate('v => document.body.textContent.includes(`XCOM Map Workshop ${v} (preview)`)', version)
        status = page.evaluate("document.getElementById('status')?.textContent || ''")
        browser.close()
    return help_ok, status, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--version', default=VERSION, help='the release to check (default tools/viewer/version.py\'s)')
    ap.add_argument('--dist', type=Path, default=REPO / 'dist' / 'release', help='where the zip and installer are')
    ap.add_argument('--port', type=int, default=8795, help='a test port, 8790-8799 (never 8768, the main server)')
    ap.add_argument('--map', default='URB_Bar', help='a map ready in the cache, opened in the browser check')
    ap.add_argument('--only', default='light-grid,text-select', help='browser_smoke.py --only checks to run')
    ap.add_argument('--no-browser', action='store_true', help='skip the browser checks')
    ap.add_argument('--keep', action='store_true', help='leave the unpacked folder')
    args = ap.parse_args(argv)
    if not 8790 <= args.port <= 8799:
        raise SystemExit('use a test port, 8790-8799')
    results = []

    def step(name, ok, detail=''):
        results.append(ok)
        print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, ': ' + detail if detail else ''), flush=True)

    v = args.version
    zip_path, setup = args.dist / ('XCOM-Map-Workshop-%s.zip' % v), args.dist / ('XCOM-Map-Workshop-%s-Setup.exe' % v)
    for path in (zip_path, setup):
        if path.is_file():
            step('file ' + path.name, True, '%.1f MB, SHA-256 %s' % (path.stat().st_size / 1e6, sha256(path)))
        else:
            step('file ' + path.name, False, 'missing')
    if not zip_path.is_file():
        return 1

    problems, compared = check_zip(zip_path, v)
    step('zip read back', not problems, '%d of our files equal the repository\'s' % compared if not problems
         else '; '.join(problems[:8]) + (' (and %d more)' % (len(problems) - 8) if len(problems) > 8 else ''))

    trial = REPO / 'dist' / ('smoke-%s' % v)
    shutil.rmtree(trial, ignore_errors=True)
    trial.mkdir(parents=True)
    zipfile.ZipFile(zip_path).extractall(trial)
    app = trial / ('XCOM-Map-Workshop-%s' % v)
    for sub in ('projects', 'builds'):
        (trial / sub).mkdir()
    base = 'http://127.0.0.1:%d/' % args.port
    try:
        get(base + 'maps.json', 2)
        step('port %d free' % args.port, False, 'something already answers there')
        return 1
    except OSError:
        pass
    log = open(trial / 'server.log', 'wb')
    proc = subprocess.Popen([str(app / 'python' / 'python.exe'), '-B', r'tools\viewer\viewer.py', 'serve', '--port', str(args.port),
                             '--no-open', '--projects', str(trial / 'projects'), '--builds', str(trial / 'builds'), '--dry-play'],
                            cwd=app, stdout=log, stderr=subprocess.STDOUT)
    try:
        up = wait_up(base, proc)
        step('the release starts with its own Python', up, base if up else 'no answer on %s' % base)
        if up:
            setup_json = json.loads(get(base + 'setup.json?checks=0')[1])
            step('/setup.json', setup_json.get('version') == v and setup_json.get('name') == NAME,
                 '%s %s' % (setup_json.get('name'), setup_json.get('version')))
            step('the page', get(base)[0] == 200)
            maps = json.loads(get(base + 'maps.json')[1])
            listed = maps.get('maps', maps) if isinstance(maps, dict) else maps
            entry = next((m for m in listed if args.map in (m.get('id'), m.get('name'))), None)
            step('map %s listed' % args.map, entry is not None, 'ready' if entry and entry.get('ready') else 'not prepared yet'
                 if entry else '')
            if not args.no_browser and entry and entry.get('ready'):
                url = base + '?map=' + args.map
                try:
                    help_ok, status, errors = browser_check(url, v)
                    step('map opens in the browser', bool(status) and not errors, status + ('; errors: %s' % errors[:3] if errors else ''))
                    step('help names %s %s (preview)' % (NAME, v), help_ok)
                except Exception as e:  # noqa: BLE001 - reported as a failed step
                    step('map opens in the browser', False, str(e).splitlines()[0])
                if args.only:
                    shot = trial / 'smoke.png'
                    run = subprocess.run([sys.executable, str(REPO / 'tools/viewer/tests/browser_smoke.py'), '--url', url,
                                          '--screenshot', str(shot), '--only', args.only], capture_output=True, text=True)
                    tail = (run.stdout + run.stderr).strip().splitlines()[-1:] or ['']
                    step('browser_smoke --only %s' % args.only, run.returncode == 0, '' if run.returncode == 0 else tail[0])
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        if not all(results):
            print('server log: %s' % (trial / 'server.log') if args.keep else
                  'server log (last lines):\n' + '\n'.join((trial / 'server.log').read_text('utf-8', 'replace').splitlines()[-15:]))
        if not args.keep:
            shutil.rmtree(trial, ignore_errors=True)
    print('%s: %d of %d steps passed' % ('PASS' if all(results) else 'FAIL', sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
