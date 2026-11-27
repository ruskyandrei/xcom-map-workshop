"""The release (preview checklist items 6 and 9): the editor's own tools with everything they need bundled, as a
Windows installer and as a portable zip. No Python, no internet and no UDK are needed on a tester's computer.
- XCOM-Map-Workshop-<version>-Setup.exe: a standard installer wizard (installer.iss, Inno Setup) with a page for the
  game folder and one for where to install; it writes the editor's settings and makes the shortcuts.
- XCOM-Map-Workshop-<version>.zip: the same files to unpack anywhere; "XCOM Map Workshop.cmd" starts the editor,
  whose first run asks for the game folder in the page.

  python tools/release/make_release.py [--out <folder>] [--keep] [--iscc <ISCC.exe>] [--no-installer]

--out is dist/release by default; a trial build in a worktree in a deep folder (an agent's, under .claude/worktrees)
goes to a short one, dist/rf, or its paths pass Windows' 260 characters.

The installer needs Inno Setup's compiler (6 or 7, free for any use: jrsoftware.org): --iscc, else the ISCC
environment variable, else the usual install folders. Without it the zip alone is made, with a note.

What goes in (dist/release/XCOM-Map-Workshop-<version>/, then the zip and the installer beside):
- the editor's modules: every module of ours the editor's entry points import (the server, the Build and the bake
  tools it runs: ENTRIES), found by reading their imports, with the folders they sit in (tools/viewer, tools/editor,
  tools/bake, tools/upk, which the bundled Python's ._pth names; tools/lab is searched too, and a shipped module that
  imports one of its tools stops the release, since the lab ships nothing; tools/ itself for paths.py), plus EXTRAS
  that are run as subprocesses by path or read as data; the page (the
  files Git tracks in tools/viewer/web, so an untracked file there never ships) with its pinned three.js (checked
  against setup_vendor.py's checksums). A working tree with uncommitted changes under tools/ gets a warning;

- Python: the official embeddable package for Windows (python.org, PYTHON_ZIP pinned by SHA-256), its ._pth naming
  the tools' folders (an embedded Python adds no script folder to the path), and requirements.txt's packages installed
  into it as Windows wheels (pip --only-binary, from PyPI);
- the launcher and the getting-started README (tools/release/), the licence (LICENSE) and THIRD-PARTY-NOTICES.txt
  (Python's licence, each package's licence files, three.js's, and a line for Inno Setup, which makes the installer);
- the user guide as one page, "User Guide.html" (tools/release/guide/guide.html with its pictures put inside it and
  the version filled in: tools/viewer/guide.py), which the installer makes a shortcut to and offers to open, and
  the editor's ? menu links to;
- every module compiled ahead (compileall, unchecked hashes), so the editor and the Build's tools start without
  compiling numpy's and SciPy's code each time, and write nothing beside themselves.

Nothing from a game install or decoded from one goes in: the modules and the page only. Downloads are cached in
dist/.downloads (the Python zip, pip's wheels). The version is tools/viewer/version.py's.
"""
import argparse
import ast
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TOOLS = REPO / 'tools'
sys.path.insert(0, str(TOOLS / 'viewer'))
import guide  # noqa: E402
import setup_vendor  # noqa: E402
from version import NAME, VERSION  # noqa: E402

PYTHON_VERSION = '3.12.10'
PYTHON_ZIP = 'https://www.python.org/ftp/python/%s/python-%s-embed-amd64.zip' % (PYTHON_VERSION, PYTHON_VERSION)
# SHA-256 of that zip, as downloaded over HTTPS from python.org on 8 November 2026; its MD5 matched the one python.org's
# release page publishes (fe8ef205f2e9c3ba44d0cf9954e1abd3). The pin keeps every later release on the same bytes.
PYTHON_SHA256 = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'
# the folders whose modules the editor imports, in the order its scripts put them on the path
FOLDERS = ('viewer', 'editor', 'bake', 'upk')
# folders searched too, whose tools never ship: a shipped module that imports one of them stops the release
UNSHIPPED = ('lab',)
ENTRIES = ('viewer/viewer.py', 'viewer/gamesetup.py', 'viewer/setup_vendor.py', 'editor/build.py', 'bake/native_copy.py',
           'bake/relight.py', 'bake/intro_copy.py', 'bake/stream_copy.py')
# run by path as subprocesses, which reading imports doesn't find
# and the data the modules read from beside themselves: the looks of made walls, floors and ground, the game's background
# sounds, the atmosphere's defaults and member kinds, the game's maps' looks and the time of day's curve (test_release.py
# finds every data file a shipped module names beside itself and checks it is here)
EXTRAS = ('viewer/requirements.txt', 'viewer/version.py',
          'bake/wall_looks.json', 'bake/slab_looks.json', 'bake/ground_looks.json',
          'bake/looks/walls.json', 'bake/looks/slabs.json', 'bake/looks/ground.json',
          'viewer/background_sounds.json', 'viewer/atmosphere_defaults.json', 'viewer/atmospheres.json',
          'viewer/sun_curve.json')
TEMPLATES = {'XCOM Map Workshop.cmd': 'XCOM Map Workshop.cmd', 'README.md': 'GETTING-STARTED.md'}
INSTALLER = HERE / 'installer.iss'
ISCC_PLACES = ('Inno Setup 7', 'Inno Setup 6')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def modules():
    """Our modules the entries import, transitively (repo-relative paths under tools/)."""
    def find(name):
        # tools/ itself holds paths.py (review finding 54), which the ._pth lists as it lists the folders
        for path in [TOOLS / folder / ('%s.py' % name) for folder in FOLDERS] + [TOOLS / ('%s.py' % name)]:
            if path.is_file() and path.name != 'run_tests.py': return path
        return None

    def unshipped(name):
        return next((TOOLS / f / ('%s.py' % name) for f in UNSHIPPED if (TOOLS / f / ('%s.py' % name)).is_file()), None)
    seen, todo = set(), [TOOLS / e for e in ENTRIES]
    while todo:
        path = todo.pop()
        if path in seen: continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for name in names:
                found = find(name.split('.')[0])
                if found: todo.append(found)
                elif unshipped(name.split('.')[0]):
                    raise SystemExit('%s imports %s, a tool of %s, which the release does not ship' % (
                        path.name, name, unshipped(name.split('.')[0]).parent.relative_to(REPO).as_posix()))
    names = {}
    for path in seen:
        if path.name in names and names[path.name] != path:
            raise SystemExit('two modules called %s (%s, %s): the embedded path would find one' % (path.name, names[path.name], path))
        names[path.name] = path
    return sorted(seen)


def download(url, cache, expect=None, fetch=None):
    """The file at `url`, kept in `cache`. A download is checked against `expect` before it is kept, so a bad one
    never stays in the cache; a cached file that no longer matches is fetched again."""
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / url.rsplit('/', 1)[1]
    if path.is_file():
        data = path.read_bytes()
        if not expect or sha256(data) == expect:
            return data
        print('%s is not the pinned file: downloading it again' % path)
    print('downloading %s' % url)
    data = (fetch or (lambda u: urllib.request.urlopen(u, timeout=120).read()))(url)
    if expect and sha256(data) != expect:
        raise SystemExit('%s has SHA-256 %s, not the pinned %s (nothing kept)' % (url, sha256(data), expect))
    part = path.with_name(path.name + '.part')
    part.write_bytes(data)
    os.replace(part, path)
    return data


def python(stage, cache):
    """The embeddable Python in stage/python, its ._pth naming the tools' folders, and the packages."""
    data = download(PYTHON_ZIP, cache, PYTHON_SHA256)
    print('Python %s embeddable: SHA-256 %s' % (PYTHON_VERSION, sha256(data)))
    target = stage / 'python'
    zipfile.ZipFile(io.BytesIO(data)).extractall(target)
    pth = next(target.glob('python3*._pth'))
    zipname = next(target.glob('python3*.zip')).name
    # relative to the ._pth's folder; `import site` makes Lib\site-packages work as usual
    lines = ([zipname, '.', r'Lib\site-packages'] + [r'..\tools\%s' % f for f in FOLDERS] + [r'..\tools']
             + ['import site'])
    pth.write_text('\r\n'.join(lines) + '\r\n', encoding='ascii', newline='')
    site = target / 'Lib' / 'site-packages'
    site.mkdir(parents=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-compile', '--target', str(site),
                    '--only-binary=:all:', '--platform', 'win_amd64', '--python-version', PYTHON_VERSION.rsplit('.', 1)[0],
                    '--implementation', 'cp', '--cache-dir', str(cache / 'pip'),
                    '-r', str(TOOLS / 'viewer' / 'requirements.txt')], check=True)
    for junk in site.glob('*/__pycache__'):
        shutil.rmtree(junk)
    shutil.rmtree(site / 'bin', ignore_errors=True)
    return target


def vendor(stage):
    """The page's three.js, as setup_vendor.py pins it (run it once here if it is missing)."""
    root = TOOLS / 'viewer' / 'web' / 'vendor' / 'three'
    for local, digest in setup_vendor.CHECKSUMS.items():
        path = root / local
        if not path.is_file() or sha256(path.read_bytes()) != digest:
            raise SystemExit('%s is missing or not the pinned file: run python tools/viewer/setup_vendor.py' % path)


def notices(stage, pythondir):
    """THIRD-PARTY-NOTICES.txt: Python's licence, each bundled package's licence files, three.js's."""
    parts = ['Third-party software in %s %s' % (NAME, VERSION), '=' * 60, '',
             'The editor itself is under the MIT licence (LICENSE). It bundles the software below, each under its own',
             'licence, reproduced in full.', '']

    def add(title, text):
        parts.extend(['-' * 60, title, '-' * 60, text.strip(), ''])
    add('Python %s (embeddable package, python.org)' % PYTHON_VERSION, (pythondir / 'LICENSE.txt').read_text(encoding='utf-8', errors='replace'))
    site = pythondir / 'Lib' / 'site-packages'
    for info in sorted(site.glob('*.dist-info')):
        files = sorted(p for p in info.rglob('*') if p.is_file() and any(k in p.name.upper() for k in ('LICEN', 'COPYING', 'NOTICE')))
        meta = (info / 'METADATA').read_text(encoding='utf-8', errors='replace') if (info / 'METADATA').is_file() else ''
        name = next((l.split(':', 1)[1].strip() for l in meta.splitlines() if l.startswith('Name:')), info.name)
        version = next((l.split(':', 1)[1].strip() for l in meta.splitlines() if l.startswith('Version:')), '')
        licence = next((l.split(':', 1)[1].strip() for l in meta.splitlines() if l.startswith(('License-Expression:', 'License:'))), '')
        body = '\n\n'.join('[%s]\n%s' % (p.relative_to(info).as_posix(), p.read_text(encoding='utf-8', errors='replace')) for p in files)
        add('%s %s%s (PyPI)' % (name, version, ' - %s' % licence if licence else ''), body or '(no licence file in the wheel; see %s)' % licence)
    add('three.js %s (github.com/mrdoob/three.js, %s)' % (setup_vendor.VERSION, setup_vendor.TAG),
        (TOOLS / 'viewer' / 'web' / 'vendor' / 'three' / 'LICENSE').read_text(encoding='utf-8'))
    add('Inno Setup (jrsoftware.org)', 'The Windows installer is made with Inno Setup, Copyright (C) 1997-2026 Jordan '
        'Russell, portions Copyright (C) 2000-2026 Martijn Laan. https://jrsoftware.org/')
    (stage / 'THIRD-PARTY-NOTICES.txt').write_text('\r\n'.join('\n'.join(parts).split('\n')), encoding='utf-8', newline='')


def tracked(folder):
    """The files Git tracks under `folder` (absolute paths), or None without Git."""
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '--', str(folder.relative_to(REPO).as_posix())], cwd=REPO,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [REPO / f for f in out.decode('utf-8').split('\0') if f]


def page_files():
    """The page: the files Git tracks in tools/viewer/web (an untracked file there doesn't ship), and the vendored
    three.js that setup_vendor.py pins and vendor() checks (Git ignores it)."""
    web = TOOLS / 'viewer' / 'web'
    files = tracked(web)
    if files is None:
        raise SystemExit('the page is copied from what Git tracks: run make_release.py in a Git checkout')
    vendor_root = web / 'vendor' / 'three'
    files += [vendor_root / local for local in setup_vendor.CHECKSUMS]
    return sorted(p for p in set(files) if p.is_file())


def dirty():
    """The working tree's changes (git status lines) that would ship or be missed, or [] when clean."""
    try:
        out = subprocess.run(['git', 'status', '--porcelain', '--', 'tools', 'LICENSE'], cwd=REPO,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in out.splitlines() if line.strip()]


def copy_tools(stage):
    files = [p for p in modules()] + [TOOLS / e for e in EXTRAS] + page_files()
    for path in files:
        dst = stage / path.relative_to(REPO)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
    return files


def precompile(stage):
    """Every module compiled ahead, with hashes the interpreter doesn't check against the sources' times (installers
    and zips don't keep them reliably), so nothing is compiled or written at run time."""
    exe = stage / 'python' / 'python.exe'
    subprocess.run([str(exe), '-m', 'compileall', '-q', '-j', '0', '--invalidation-mode', 'unchecked-hash',
                    str(stage / 'python' / 'Lib' / 'site-packages'), str(stage / 'tools')], check=True, cwd=str(stage))


def find_iscc(given=None):
    """Inno Setup's compiler: --iscc, the ISCC environment variable, else the usual install folders."""
    candidates = [given, os.environ.get('ISCC')]
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        if base: candidates += [os.path.join(base, place, 'ISCC.exe') for place in ISCC_PLACES]
    candidates.append(REPO / 'dist' / '.downloads' / 'innosetup' / 'ISCC.exe')
    return next((Path(c) for c in candidates if c and Path(c).is_file()), None)


def installer(stage, out, iscc):
    """XCOM-Map-Workshop-<version>-Setup.exe from the staged folder (installer.iss)."""
    subprocess.run([str(iscc), '/Q', '/DVersion=%s' % VERSION, '/DStage=%s' % stage, '/DOutput=%s' % out, str(INSTALLER)],
                   check=True)
    return out / ('XCOM-Map-Workshop-%s-Setup.exe' % VERSION)


def check(stage):
    """The bundled Python imports the packages and the editor's modules, and the doctor runs."""
    exe = stage / 'python' / 'python.exe'
    subprocess.run([str(exe), '-B', '-c', 'import numpy, scipy.ndimage, scipy.spatial, PIL.Image, embreex.rtcore_scene; '
                    'import viewer, build, native_copy, relight, gamesetup, prefabs, prefab_stage, prefab_tests; '
                    'print("imports ok")'], check=True, cwd=str(stage))
    viewer = [str(exe), '-B', str(stage / 'tools' / 'viewer' / 'viewer.py')]
    with tempfile.TemporaryDirectory(dir=stage.parent, prefix='setup-check-') as temp:
        root = Path(temp)
        settings = root / 'settings.json'
        config = {key: str(root / name) for key, name in [('projects', 'projects'), ('output', 'builds'), ('cache', 'cache')]}
        settings.write_text(json.dumps(config), encoding='utf-8', newline='\n')
        env = dict(os.environ, XCOM_MAP_WORKSHOP_SETTINGS=str(settings))
        out = subprocess.run(viewer + ['settings'], capture_output=True, text=True, cwd=stage, env=env)
        if out.returncode or str(root / 'prefabs') not in out.stdout:
            raise SystemExit('the staged editor does not resolve its prefab library: %s' % (out.stderr or out.stdout))
        out = subprocess.run(viewer + ['doctor'], capture_output=True, text=True, cwd=stage, env=env)
        statuses = {fields[1]: fields[0] for line in out.stdout.splitlines() if len(fields := line.split()) >= 2}
        if out.returncode != 1 or statuses.get('game') != 'MISSING' or statuses.get('prefabs') != 'OK':
            raise SystemExit('the staged editor failed its first-run doctor check: %s' % (out.stderr or out.stdout))
    # the editor there serves the release's own guide (the ? menu's link)
    out = subprocess.run([str(exe), '-B', '-c', 'import guide, sys; sys.stdout.write(str(len(guide.page() or b"")))'],
                         capture_output=True, text=True, cwd=str(stage))
    if out.returncode or int(out.stdout or 0) != (stage / guide.KIT_NAME).stat().st_size:
        raise SystemExit('the staged editor does not find %s: %s' % (guide.KIT_NAME, out.stderr or out.stdout))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', type=Path, default=REPO / 'dist' / 'release',
                    help='where the folder and zip go (default dist/release). In a worktree in a deep folder (an agent\'s '
                         'under .claude/worktrees) give a short one, dist/rf: with a longer name the compiled files of '
                         'SciPy\'s tests pass Windows\' 260 characters and the build stops')
    ap.add_argument('--keep', action='store_true', help='keep the unzipped folder beside the zip')
    ap.add_argument('--iscc', type=Path, help='Inno Setup\'s compiler, ISCC.exe (default: the ISCC variable, else its usual folders)')
    ap.add_argument('--no-installer', action='store_true', help='make the zip only')
    args = ap.parse_args(argv)
    args.out = args.out.resolve()       # the staged Python runs from the staged folder, where a relative path leads nowhere
    iscc = None if args.no_installer else find_iscc(args.iscc)
    name = 'XCOM-Map-Workshop-%s' % VERSION
    stage = args.out / name
    changes = dirty()
    if changes:
        # the modules are copied from the working tree, so these changes ship (or are missed) as they stand
        print('warning: the working tree has %d uncommitted change(s) under tools/; the release takes the files as they '
              'are on disk:\n  %s' % (len(changes), '\n  '.join(changes[:20])))
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    vendor(stage)
    files = copy_tools(stage)
    pythondir = python(stage, REPO / 'dist' / '.downloads')
    for dst, src in TEMPLATES.items():
        (stage / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / src, stage / dst)
    (stage / guide.KIT_NAME).write_bytes(guide.inline(version=VERSION))
    shutil.copyfile(REPO / 'LICENSE', stage / 'LICENSE.txt')
    notices(stage, pythondir)
    (stage / 'VERSION.txt').write_text('%s %s\r\n' % (NAME, VERSION), encoding='ascii', newline='')
    precompile(stage)
    check(stage)
    zpath = args.out / ('%s.zip' % name)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                z.write(path, '%s/%s' % (name, path.relative_to(stage).as_posix()))
    print('%s: %d of our files, %.1f MB, SHA-256 %s' % (zpath, len(files), zpath.stat().st_size / 1e6, sha256(zpath.read_bytes())))
    if iscc:
        setup = installer(stage, args.out, iscc)
        print('%s: %.1f MB, SHA-256 %s (Inno Setup: %s)' % (setup, setup.stat().st_size / 1e6, sha256(setup.read_bytes()), iscc))
    elif not args.no_installer:
        print('No installer made: Inno Setup\'s compiler (ISCC.exe, Inno Setup 6 or 7 from jrsoftware.org) was not found. '
              'Install it, or pass --iscc <ISCC.exe>.')
    if not args.keep: shutil.rmtree(stage)
    return 0


if __name__ == '__main__':
    sys.exit(main())
