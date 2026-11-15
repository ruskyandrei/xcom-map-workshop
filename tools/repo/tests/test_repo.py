"""What must never be committed: this repository is public.

The files checked are the ones Git has or would add (tracked, and untracked ones that are not ignored). Without Git
(a release's folder) the tests are skipped.

- No folder of one computer: a drive-letter path must be one of the made-up ones in ALLOWED, and a Windows profile
  folder must be a placeholder (C:\\Users\\you, <name>, %USERPROFILE%). Write <lab>, <game install>, <Steam common>,
  <repo>, <cache> or <udk> instead.
- Nothing from private/, no plan (they are kept in private/plans), no copy of another repository's files under research/evidence/upstream (the manifest names
  where they are), no stub diff, no picture of an experiment or check.
- Every relative Markdown link leads to a file that is there.
"""
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[3]
DRIVE = re.compile(rb'(?<![A-Za-z0-9])([A-Za-z]):(?:\\\\|\\|/)(?=[A-Za-z])((?:[A-Za-z0-9_.()+-]+ ?)+)')
# made-up paths in usage lines, tests and notes on defaults: the drive and how the path starts
ALLOWED = [(d, re.compile(p, re.I)) for d, p in (
    ('C', r'Users$'), ('C', r'Program Files'), ('C', r'Windows'), ('C', r'UDK'), ('C', r'Steam'), ('C', r'x$'),
    ('C', r'maps$'), ('C', r'Games'), ('D', r'Steam'), ('D', r'Games'))]
PROFILE = re.compile(rb'(?<![A-Za-z0-9])[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)([A-Za-z0-9_.<%-]+)')
PROFILE_OK = (b'you', b'<', b'%', b'Public', b'name', b'user')
LINK = re.compile(r'(?<!\\)\]\(\s*<?([^)>\s]+)>?(?:\s+"[^"]*")?\s*\)')
FENCE = re.compile(r'^(```|~~~)')
PICTURES = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def files():
    """The repository's files as Git sees them (relative, forward slashes), or None without Git."""
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=REPO,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [f for f in out.decode('utf-8').split('\0') if f and (REPO / f).is_file()]


def text(path):
    data = (REPO / path).read_bytes()
    return None if b'\0' in data[:8192] else data


class Public(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = files()
        if cls.files is None:
            raise unittest.SkipTest('not a Git checkout')

    def test_no_folder_of_one_computer(self):
        found = []
        for f in self.files:
            data = text(f)
            if data is None:
                continue
            for n, line in enumerate(data.split(b'\n'), 1):
                for m in DRIVE.finditer(line):
                    drive, first = m.group(1).decode().upper(), m.group(2).decode('latin-1').strip()
                    if not any(d == drive and p.match(first) for d, p in ALLOWED):
                        found.append('%s:%d: %s' % (f, n, m.group(0).decode('latin-1')))
                for m in PROFILE.finditer(line):
                    if not m.group(1).startswith(PROFILE_OK):
                        found.append('%s:%d: a profile folder' % (f, n))
        self.assertEqual(found, [], 'folders of one computer (write a placeholder such as <lab>):\n' + '\n'.join(found[:60]))

    def test_nothing_private_is_committed(self):
        bad = [f for f in self.files
               if f.startswith(('private/', 'research/plans/'))
               or (f.startswith('research/evidence/upstream/') and f != 'research/evidence/upstream/source-manifest.json')
               or f.endswith('XComGame-stubs.diff')
               or f.lower().endswith('discord-feedback.md')
               or (f.startswith('research/') and f.lower().endswith(PICTURES))]
        self.assertEqual(bad, [], 'these belong in private/ (ignored), not in the repository')

    def test_relative_links_lead_somewhere(self):
        present = set(self.files)
        broken = []
        for f in self.files:
            if not f.lower().endswith('.md'):
                continue
            fenced = False
            for n, line in enumerate((REPO / f).read_text(encoding='utf-8', errors='replace').split('\n'), 1):
                if FENCE.match(line.strip()):
                    fenced = not fenced
                if fenced:
                    continue
                for target in LINK.findall(re.sub(r'`[^`]*`', '', line)):
                    target = target.split('#')[0].replace('%20', ' ')
                    if not target or re.match(r'[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('/'):
                        continue
                    parts = []
                    for part in (Path(f).parent / target).as_posix().split('/'):
                        if part == '..':
                            if parts:
                                parts.pop()
                        elif part not in ('.', ''):
                            parts.append(part)
                    path = '/'.join(parts)
                    if path not in present and not (REPO / path).is_dir():
                        broken.append('%s:%d: %s' % (f, n, target))
        self.assertEqual(broken, [], 'links that lead nowhere:\n' + '\n'.join(broken[:80]))


if __name__ == '__main__':
    unittest.main()
