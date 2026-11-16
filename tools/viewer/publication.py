"""A variant package put in place so that a build killed at any moment leaves a valid package after reconciliation
(build queue plan, 9.3).

A build writes its new package beside the builds folder's (<output>/.work/<Variant>-<stamp>/package) and swaps it in
last. That swap is two directory renames: the old package aside, the new one in. Two renames are not one atomic
operation, so the swap keeps a journal:

  1. with the variant's guard held, <output>/.work/publish/<variant>.json is written (and flushed) before anything
     moves: which build is going in, the paths of the package, the old one's backup and the new one;
  2. the old package is renamed to its backup (<output>/.work/publish/<variant>-<id>.old);
  3. the new package is renamed into place;
  4. the journal says committed;
  5. the backup is deleted and the journal with it.

`recover` reads a journal left by a build that died (run once its processes have all ended: the server's builds are
contained, procs.py, and a command-line build holds the guard) and settles it: a new package wholly in place and
matching its manifest is kept (the backup goes), otherwise the old one comes back from its backup. A journal it can't
read, or whose paths are not where a journal puts them, blocks the variant's output with the reason: nothing is
deleted or retried on a guess.

`guard(output, variant)` is the variant's lock, held by the operating system on <output>/.work/locks/<variant>.lock
(a byte-range lock on Windows, flock elsewhere): it is released when its holder ends, however it ends, and never taken
from a live holder because time passed. Builds take it to put a package in place, readers (Install in the game, the map
pack, Play in game) to read or copy one, so no reader sees half a swap. `FileLock` is the same lock for other files
(the server's ownership of its build queue: buildqueue.py).
"""
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

SCHEMA = 'xcom-map-workshop/publication'
SCHEMA_VERSION = 1
PUBLISH_WAIT = 1800.0       # a build waits this long for readers copying the package it replaces
READ_WAIT = 120.0           # a reader waits this long for a build putting its package in place
VARIANT = re.compile(r'[A-Za-z][A-Za-z0-9_]*')


class PublishError(Exception):
    pass


class Busy(PublishError):
    pass


class Blocked(PublishError):
    """A journal that can't be settled: the variant's output waits for a person."""


class FileLock:
    """An exclusive lock on a file, held by the operating system for this process until released or until it ends."""

    def __init__(self, path):
        self.path, self.fd = Path(path), None

    def acquire(self, wait=0.0, poll=0.1):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.monotonic() + wait
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fd = fd
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    return False
                time.sleep(poll)

    def release(self):
        fd, self.fd = self.fd, None
        if fd is None:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(fd)

    @property
    def held(self):
        return self.fd is not None


def lock_path(output, variant):
    return Path(output) / '.work' / 'locks' / ('%s.lock' % variant.lower())


@contextlib.contextmanager
def guard(output, variant, wait=READ_WAIT):
    """The variant's lock (see the module notes); Busy when another holds it for longer than `wait` seconds."""
    if not VARIANT.fullmatch(str(variant)):
        raise PublishError('%r is not a variant name' % (variant,))
    lock = FileLock(lock_path(output, variant))
    if not lock.acquire(wait):
        raise Busy('another build or reader is using %s (%s); try again' % (variant, lock.path))
    try:
        yield
    finally:
        lock.release()


@contextlib.contextmanager
def guards(output, variants, wait=READ_WAIT):
    """Several variants' locks, taken in one stable order (so two readers of the same packages can't deadlock)."""
    with contextlib.ExitStack() as stack:
        for variant in sorted({v.lower(): v for v in variants}.values(), key=str.lower):
            stack.enter_context(guard(output, variant, wait))
        yield


def journals(output):
    return Path(output) / '.work' / 'publish'


def journal_path(output, variant):
    return journals(output) / ('%s.json' % variant.lower())


def _write(path, data):
    temp = path.with_name('%s.%s.tmp' % (path.name, uuid.uuid4().hex[:8]))
    with open(temp, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=1)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _same(a, b):
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _within(path, root):
    path, root = os.path.normcase(os.path.abspath(str(path))), os.path.normcase(os.path.abspath(str(root)))
    return path.startswith(root.rstrip('\\/') + os.sep)


def _manifest(folder):
    try:
        m = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
        return m if isinstance(m, dict) else None
    except (OSError, ValueError):
        return None


def verified(folder, identity):
    """Whether the package in `folder` is the build `identity` names ({buildId, attempt?, project?}) and its files
    match its manifest (installs.read_package)."""
    m = _manifest(folder)
    if not m or m.get('buildId') != identity.get('buildId'):
        return False
    if identity.get('attempt') and m.get('attempt') != identity['attempt']:
        return False
    if identity.get('project') and (m.get('project') or {}).get('id') != identity['project']:
        return False
    try:
        import installs
        installs.read_package(folder)
    except Exception:       # noqa: BLE001 - any reason the files don't verify is a package that doesn't verify
        return False
    return True


def publish(output, variant, staging, existing, identity, boundary=None):
    """Put `staging` in place as <output>/<variant>, the variant's guard held by the caller. `existing`: the builds
    folder's package of the variant (its own folder, maybe in another case) or None; identity: {buildId, attempt,
    project} of the new package. boundary(name), when given, is called after each step (tests stop the process there).
    Returns a list of warnings (a backup that could not be deleted). A PublishError when the new package could not be
    put in place: the old one is then as it was."""
    output, staging = Path(output), Path(staging)
    boundary = boundary or (lambda name: None)
    settled = recover(output, variant)
    if settled and settled.get('state') == 'blocked':
        raise Blocked(settled['reason'])
    final = output / variant
    folder = journals(output)
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / ('%s-%s.old' % (variant.lower(), uuid.uuid4().hex[:12]))
    journal = journal_path(output, variant)
    previous = _manifest(existing) if existing is not None else None
    _write(journal, dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, variant=variant, state='prepared',
                         final=str(final), existing=str(existing) if existing is not None else None, backup=str(backup),
                         staging=str(staging), build=dict(identity),
                         previous=(previous or {}).get('buildId'), at=time.time()))
    boundary('journal')
    if existing is not None:
        Path(existing).rename(backup)
        boundary('old-aside')
    try:
        staging.rename(final)
    except OSError as error:
        if existing is not None:
            backup.rename(existing)
        journal.unlink(missing_ok=True)
        raise PublishError('the new package could not be put in place (%s); the last one is as it was' % error)
    boundary('new-in-place')
    data = json.loads(journal.read_text(encoding='utf-8'))
    _write(journal, dict(data, state='committed'))
    boundary('committed')
    warnings = []
    if backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as error:
            warnings.append('the last package\'s copy %s could not be deleted (%s); the next build deletes it' % (backup, error))
            return warnings
    boundary('cleaned')
    journal.unlink(missing_ok=True)
    return warnings


def recover(output, variant):
    """Settle a journal left for the variant (see the module notes), the guard held by the caller and none of the
    build's processes left. None when there is none, else dict(state, reason): committed (the new package kept),
    restored (the old one put back), kept (nothing had moved), none (no package before, and the new one never went
    in), blocked (the journal can't be settled; nothing changed)."""
    output = Path(output)
    journal = journal_path(output, variant)
    if not journal.is_file():
        return None
    try:
        data = json.loads(journal.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('schemaVersion') != SCHEMA_VERSION:
            raise ValueError('not a publication journal of this editor')
        final, backup = Path(data['final']), Path(data['backup'])
        existing = Path(data['existing']) if data.get('existing') else None
        build = data.get('build') or {}
        if not (_same(final, output / variant) and _within(backup, journals(output))
                and (existing is None or _same(existing.parent, output)) and isinstance(build.get('buildId'), str)
                and data.get('state') in ('prepared', 'committed')):
            raise ValueError('its paths or its state are not a journal\'s')
    except (OSError, ValueError, KeyError, TypeError) as error:
        return dict(state='blocked', reason='%s can\'t be settled (%s): the builds of %s wait until it is looked at and '
                                            'moved away' % (journal, error, variant))
    home = existing if existing is not None else final
    if data['state'] == 'committed' or (final.is_dir() and _manifest(final) and _manifest(final).get('buildId') == build['buildId']):
        if data['state'] != 'committed' and not verified(final, build):
            # the new package is in place but does not match its manifest: set aside, the old one back
            rejected = journals(output) / ('%s-%s.rejected' % (variant.lower(), uuid.uuid4().hex[:12]))
            final.rename(rejected)
            if backup.is_dir():
                backup.rename(home)
                journal.unlink(missing_ok=True)
                return dict(state='restored', reason='the new package did not match its manifest (kept in %s)' % rejected)
            journal.unlink(missing_ok=True)
            return dict(state='none', reason='the new package did not match its manifest (kept in %s)' % rejected)
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as error:
                return dict(state='committed', reason='the new package is in place; its old copy %s could not be deleted '
                                                      'yet (%s)' % (backup, error))
        journal.unlink(missing_ok=True)
        return dict(state='committed', reason='the new package %s is in place' % build['buildId'])
    if backup.is_dir():
        if final.exists() and not _same(final, home):
            return dict(state='blocked', reason='%s and the last package\'s copy %s are both there: the builds of %s wait '
                                                'until one is moved away' % (final, backup, variant))
        if home.exists():
            return dict(state='blocked', reason='%s and the last package\'s copy %s are both there: the builds of %s wait '
                                                'until one is moved away' % (home, backup, variant))
        backup.rename(home)
        journal.unlink(missing_ok=True)
        return dict(state='restored', reason='the last package (%s) is back in place' % data.get('previous'))
    if existing is not None and not existing.exists():
        return dict(state='blocked', reason='%s and its copy %s are both missing: the builds of %s wait until it is looked '
                                            'at' % (existing, backup, variant))
    journal.unlink(missing_ok=True)
    return dict(state='kept' if existing is not None else 'none',
                reason='nothing had moved: the last package is as it was' if existing is not None else 'no package was put in place')


def pending(output):
    """The variants with a journal in the builds folder: [variant name as the journal has it, or its file stem]."""
    folder = journals(output)
    found = []
    for path in sorted(folder.glob('*.json')) if folder.is_dir() else ():
        try:
            name = json.loads(path.read_text(encoding='utf-8')).get('variant')
        except (OSError, ValueError, AttributeError):
            name = None
        found.append(name if isinstance(name, str) and VARIANT.fullmatch(name) and name.lower() == path.stem else path.stem)
    return found


def recover_all(output, wait=0.0):
    """Every journal of the builds folder settled (recover), each under its guard: {variant: result}. A variant whose
    guard is held (a live command-line build) is left for later: {state: 'busy'}."""
    results = {}
    for variant in pending(output):
        if not VARIANT.fullmatch(variant):
            results[variant] = dict(state='blocked', reason='%s is not a journal of a variant' % journal_path(output, variant))
            continue
        try:
            with guard(output, variant, wait):
                results[variant] = recover(output, variant)
        except Busy:
            results[variant] = dict(state='busy', reason='a build is putting %s in place' % variant)
        except OSError as error:
            results[variant] = dict(state='blocked', reason='%s could not be settled: %s' % (variant, error))
    return results
