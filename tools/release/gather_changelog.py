"""The change ledger: one file per entry, gathered into month files at each release.

Each change adds one file to changelog/entries/, named <YYYY-MM-DD>-<what>.md (the day it went in, then a few words
in lower case joined by hyphens). The file holds one entry: a "### Title" line, then what changed, where, how it was
checked and any known gaps. Its links are relative to the entry file (../../tools/viewer/app.js). Because every
change has its own file, two branches never edit the same lines of the ledger.

Gathering moves every entry into changelog/<YYYY-MM>.md under its day's "## <d> <Month> <YYYY>" heading, newest first,
re-bases its links for the month file and deletes the entry file. Within a day, entries are ordered by when Git first
recorded them (an entry not committed yet counts as the newest), then by name. The release gathers before it is
built; nothing else has to.

  python tools/release/gather_changelog.py            gather every entry into its month file
  python tools/release/gather_changelog.py --check    check the entry files only (name, title line, links)
  python tools/release/gather_changelog.py --list     print the entries in the order they would be gathered
"""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
NAME = re.compile(r'^(\d{4})-(\d{2})-(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$')
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')
DAY = re.compile(r'^## (\d{1,2}) (' + '|'.join(MONTHS) + r') (\d{4})\s*$')
LINK = re.compile(r'(?<!\\)(\]\(\s*<?)([^)>\s]+)(>?(?:\s+"[^"]*")?\s*\))')
FENCE = re.compile(r'^\s*(```|~~~)')
SKIP = ('README.md',)


class EntryError(ValueError):
    pass


def folders(repo):
    return Path(repo) / 'changelog', Path(repo) / 'changelog' / 'entries'


def entry_files(repo):
    """The entry files, unsorted (README.md in the folder explains the folder and is not an entry)."""
    _, entries = folders(repo)
    if not entries.is_dir():
        return []
    return [p for p in entries.iterdir() if p.is_file() and p.suffix == '.md' and p.name not in SKIP]


def is_relative(target):
    return not (not target or target.startswith(('#', '/')) or re.match(r'[a-z][a-z0-9+.-]*:', target, re.I))


def _segments(line):
    """The line cut at inline code spans: [(is_code, text)]."""
    out, pos = [], 0
    for m in re.finditer(r'`+[^`]*`+', line):
        out.append((False, line[pos:m.start()]))
        out.append((True, m.group(0)))
        pos = m.end()
    out.append((False, line[pos:]))
    return out


def map_links(text, fn):
    """`text` with each relative Markdown link target outside code replaced by fn(target)."""
    lines, fenced = text.split('\n'), False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        parts = []
        for code, seg in _segments(line):
            if not code:
                seg = LINK.sub(lambda m: m.group(1) + (fn(m.group(2)) if is_relative(m.group(2)) else m.group(2))
                               + m.group(3), seg)
            parts.append(seg)
        lines[i] = ''.join(parts)
    return '\n'.join(lines)


def links(text):
    found = []
    map_links(text, lambda t: found.append(t) or t)
    return found


def rebase(text, src_dir, dst_dir, repo):
    """Links written relative to src_dir rewritten relative to dst_dir (both inside `repo`)."""
    src = PurePosixPath(Path(src_dir).resolve().relative_to(Path(repo).resolve()).as_posix())
    dst = PurePosixPath(Path(dst_dir).resolve().relative_to(Path(repo).resolve()).as_posix())

    def move(target):
        path, hash_, anchor = target.partition('#')
        if not path:
            return target
        parts = []
        for part in (src / path).as_posix().split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part not in ('.', ''):
                parts.append(part)
        rel = os.path.relpath('/' + '/'.join(parts), '/' + dst.as_posix() if str(dst) != '.' else '/').replace('\\', '/')
        if path.endswith('/') and not rel.endswith('/'):
            rel += '/'
        return rel + hash_ + anchor
    return map_links(text, move)


def parse(path):
    """(date as (y, m, d), title, text) of one entry file, or EntryError."""
    m = NAME.match(path.name)
    if not m:
        raise EntryError(f'{path.name}: the name must be <YYYY-MM-DD>-<what>.md (lower case, hyphens)')
    y, mo, d = (int(g) for g in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        raise EntryError(f'{path.name}: not a date')
    text = path.read_bytes().decode('utf-8')
    if '\r' in text:
        raise EntryError(f'{path.name}: write it with LF line endings')
    lines = text.strip('\n').split('\n')
    if not lines or not lines[0].startswith('### ') or not lines[0][4:].strip():
        raise EntryError(f'{path.name}: the first line must be "### <title>"')
    if any(DAY.match(line) or line.startswith('# ') for line in lines):
        raise EntryError(f'{path.name}: an entry holds no "#" or "## <day>" heading')
    return (y, mo, d), lines[0][4:].strip(), '\n'.join(lines) + '\n'


def check(repo=REPO):
    """Every problem with the entry files, as lines (empty when they are all well formed)."""
    problems = []
    for path in sorted(entry_files(repo)):
        try:
            parse(path)
        except EntryError as e:
            problems.append(str(e))
            continue
        for target in links(path.read_text(encoding='utf-8')):
            rel = target.split('#')[0].replace('%20', ' ')
            if rel and not (path.parent / rel).exists():
                problems.append(f'{path.name}: the link {target} leads nowhere (links are relative to the entry file)')
    return problems


def added_at(repo, path):
    """When Git first recorded the file (seconds), or None when it is not committed yet."""
    try:
        out = subprocess.run(['git', 'log', '--diff-filter=A', '--format=%ct', '--', str(path)], cwd=repo,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return int(out[-1]) if out else None


def ordered(repo=REPO, when=None):
    """[(date, path, title, text)] newest first: by day, then by when it was recorded, then by name."""
    when = when or (lambda p: added_at(repo, p))
    now = time.time() + 1
    rows = []
    for path in entry_files(repo):
        date, title, text = parse(path)
        t = when(path)
        rows.append((date, now if t is None else t, path.name, path, title, text))
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [(r[0], r[3], r[4], r[5]) for r in rows]


def month_header(y, mo):
    return (f'# Change ledger: {MONTHS[mo - 1]} {y}\n\nWhat changed in {MONTHS[mo - 1]} {y}, newest first. The '
            f'[index](../CHANGELOG.md) says how the ledger is kept.\n')


def insert(month_text, date, entries_text):
    """`month_text` with `entries_text` placed first under its day's heading (made, in date order, if missing)."""
    y, mo, d = date
    lines = month_text.rstrip('\n').split('\n')
    heading = f'## {d} {MONTHS[mo - 1]} {y}'
    block = entries_text.rstrip('\n').split('\n')
    for i, line in enumerate(lines):
        m = DAY.match(line)
        if not m:
            continue
        day = (int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1)))
        if day == date:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            new = lines[:i + 1] + [''] + block + ([''] if j < len(lines) else []) + lines[j:]
            return '\n'.join(new) + '\n'
        if day < date:
            new = lines[:i] + [heading, ''] + block + [''] + lines[i:]
            return '\n'.join(new) + '\n'
    new = lines + ['', heading, ''] + block
    return '\n'.join(new) + '\n'


def gather(repo=REPO, when=None, out=print):
    """Move every entry into its month file. Returns the month files written."""
    rows = ordered(repo, when)
    problems = check(repo)
    if problems:
        raise EntryError('the entry files have problems:\n' + '\n'.join(problems))
    changelog, entries = folders(repo)
    by_day = {}
    for date, path, title, text in rows:
        by_day.setdefault(date, []).append((path, title, text))
    written = set()
    # oldest day first, so each day's block lands above the older days already placed
    for date in sorted(by_day):
        y, mo, d = date
        month = changelog / f'{y:04d}-{mo:02d}.md'
        current = month.read_bytes().decode('utf-8') if month.exists() else month_header(y, mo)
        block = '\n'.join(rebase(text, entries, changelog, repo).rstrip('\n') + '\n' for _, _, text in by_day[date])
        month.write_bytes(insert(current, date, block).encode('utf-8'))
        written.add(month)
        for path, title, _ in by_day[date]:
            out(f'{month.name}: {d} {MONTHS[mo - 1]}: {title}')
    for _, path, _, _ in rows:
        path.unlink()
    return sorted(written)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true', help='check the entry files only')
    ap.add_argument('--list', action='store_true', help='print the entries in the order they would be gathered')
    args = ap.parse_args(argv)
    problems = check()
    if args.check or problems:
        for p in problems:
            print(p)
        print('entries: %d, problems: %d' % (len(entry_files(REPO)), len(problems)))
        return 1 if problems else 0
    if args.list:
        for date, path, title, _ in ordered():
            print('%04d-%02d-%02d  %s  (%s)' % (date + (title, path.name)))
        return 0
    written = gather()
    print('gathered into ' + (', '.join(p.name for p in written) or 'nothing (no entries)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
