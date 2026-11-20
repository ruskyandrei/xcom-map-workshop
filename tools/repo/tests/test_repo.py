"""What must never be committed: this repository is public.

The files checked are the ones Git has or would add (tracked, and untracked ones that are not ignored). Without Git
(a release's folder) the tests are skipped.

- No folder of one computer: a drive-letter path must be one of the made-up ones in ALLOWED (its first folder matched
  whole), and a Windows profile folder must be a placeholder (C:\\Users\\you, <name>, %USERPROFILE%), in Windows,
  Git Bash (/c/Users/<name>) and WSL (/mnt/c/Users/<name>) forms alike. A network path (\\\\host\\share) must name a made-up
  host. Write <lab>, <game install>, <Steam common>, <repo>, <cache> or <udk> instead.
- No account name: the name of the account running the tests (and its profile folder's) appears nowhere, nor any word
  in private/repo-denylist.txt when that file is there (one word per line; it is ignored by Git, so the names in it
  stay private).
- The pictures' metadata (PNG text chunks, WebP EXIF and XMP, JPEG application segments) is held to the same rules.
- Nothing from private/, no plan (they are kept in private/plans), no copy of another repository's files under research/evidence/upstream (the manifest names
  where they are), no stub diff, no picture of an experiment or check.
- Every relative Markdown link leads to a file that is there, or to a folder that holds a file Git has (a link into
  an ignored folder leads nowhere for anyone else).
"""
import os
from pathlib import Path
import re
import struct
import subprocess
import unittest
import zlib

REPO = Path(__file__).resolve().parents[3]
SEP = rb'(?:\\\\|\\|/)'
DRIVE = re.compile(rb'(?<![A-Za-z0-9])([A-Za-z]):' + SEP + rb'(?=[A-Za-z0-9_.~$-])((?:[A-Za-z0-9_.()+$~-]+ ?)+)')
# made-up paths in usage lines, tests and notes on defaults: the drive and its first folder, matched whole
ALLOWED = [(d, re.compile(p, re.I)) for d, p in (
    ('C', r'Users'), ('C', r'Program Files'), ('C', r'Program Files \(x86\)'), ('C', r'Windows'), ('C', r'UDK'),
    ('C', r'Steam'), ('C', r'x'), ('C', r'maps'), ('C', r'Games'), ('D', r'Steam'), ('D', r'SteamLibrary'),
    ('D', r'Games'))]
PROFILE = re.compile(rb'(?<![A-Za-z0-9])[A-Za-z]:' + SEP + rb'Users' + SEP + rb'([A-Za-z0-9_.<%-]+)')
# Git Bash's /c/Users/<name> and WSL's /mnt/c/Users/<name> (and /home/<name>)
POSIX_PROFILE = re.compile(rb'(?<![A-Za-z0-9_.])/(?:mnt/)?[A-Za-z]/Users/([A-Za-z0-9_.<%-]+)|(?<![A-Za-z0-9_.])/home/([A-Za-z0-9_.<%-]+)')
PROFILE_OK = (b'you', b'<', b'%', b'$', b'Public', b'name', b'user')
# \\host\share as written, or escaped in a string (\\\\host\\share); after a space, a quote, a bracket or the start
UNC = re.compile(rb'(?<![^\s"\'`(=\[,])(?:\\\\\\\\([A-Za-z0-9_.$?<>-]+)\\\\|\\\\([A-Za-z0-9_.$?<>-]+)\\(?!\\))')
UNC_OK = (b'host', b'server', b'?', b'.', b'wsl$', b'wsl.localhost', b'localhost', b'<')
LINK = re.compile(r'(?<!\\)\]\(\s*<?([^)>\s]+)>?(?:\s+"[^"]*")?\s*\)')
FENCE = re.compile(r'^(```|~~~)')
PICTURES = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
DENYLIST = REPO / 'private' / 'repo-denylist.txt'


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


def picture_metadata(data):
    """The text a picture carries besides its pixels: PNG text and EXIF chunks, WebP EXIF and XMP chunks, JPEG
    application and comment segments. b'' when there is none (or the format is not one of those)."""
    out = []
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        i = 8
        while i + 8 <= len(data):
            size, tag = struct.unpack('>I', data[i:i + 4])[0], data[i + 4:i + 8]
            body = data[i + 8:i + 8 + size]
            if tag == b'zTXt':
                key, _, rest = body.partition(b'\0')
                try:
                    body = key + b' ' + zlib.decompress(rest[1:])
                except zlib.error:
                    pass
            if tag in (b'tEXt', b'iTXt', b'zTXt', b'eXIf'):
                out.append(body)
            i += 12 + size
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        i = 12
        while i + 8 <= len(data):
            tag, size = data[i:i + 4], struct.unpack('<I', data[i + 4:i + 8])[0]
            if tag in (b'EXIF', b'XMP '):
                out.append(data[i + 8:i + 8 + size])
            i += 8 + size + (size & 1)
    elif data[:2] == b'\xff\xd8':
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker, size = data[i + 1], struct.unpack('>H', data[i + 2:i + 4])[0]
            if marker == 0xDA:        # start of scan: the pixels follow
                break
            if 0xE1 <= marker <= 0xEF or marker == 0xFE:
                out.append(data[i + 4:i + 2 + size])
            i += 2 + size
    return b'\n'.join(out)


def account_words():
    """Words that would name this computer's user: the account's name and its profile folder's, and the private
    denylist's words (four letters or more, so a short or common name can't match half the repository)."""
    words = {os.environ.get('USERNAME', ''), os.environ.get('USER', ''),
             Path(os.environ.get('USERPROFILE', '') or '~').name}
    if DENYLIST.is_file():
        words |= {line.strip() for line in DENYLIST.read_text(encoding='utf-8').splitlines()
                  if line.strip() and not line.startswith('#')}
    return sorted(w for w in words if len(w) >= 4 and w.lower() not in ('user', 'users', 'public', 'admin', 'name'))


def problems(name, data):
    """The places in `data` (bytes) that name a folder of one computer, a network host or an account."""
    found = []
    words = [re.compile(rb'(?<![A-Za-z0-9])' + re.escape(w.encode('utf-8')) + rb'(?![A-Za-z0-9])', re.I)
             for w in account_words()]
    for n, line in enumerate(data.split(b'\n'), 1):
        for m in DRIVE.finditer(line):
            drive, first = m.group(1).decode().upper(), m.group(2).decode('latin-1').strip()
            if not any(d == drive and p.fullmatch(first) for d, p in ALLOWED):
                found.append('%s:%d: %s' % (name, n, m.group(0).decode('latin-1')))
        for m in PROFILE.finditer(line):
            if not m.group(1).startswith(PROFILE_OK):
                found.append('%s:%d: a profile folder' % (name, n))
        for m in POSIX_PROFILE.finditer(line):
            if not (m.group(1) or m.group(2)).startswith(PROFILE_OK):
                found.append('%s:%d: a profile folder (Git Bash or WSL form)' % (name, n))
        for m in UNC.finditer(line):
            if not (m.group(1) or m.group(2)).startswith(UNC_OK):
                found.append('%s:%d: a network path %s' % (name, n, m.group(0).decode('latin-1')))
        for w in words:
            if w.search(line):
                found.append('%s:%d: the name of an account' % (name, n))
    return found


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
                if f.lower().endswith(PICTURES):
                    found += problems(f + ' (metadata)', picture_metadata((REPO / f).read_bytes()))
                continue
            found += problems(f, data)
        self.assertEqual(found, [], 'folders of one computer (write a placeholder such as <lab>):\n' + '\n'.join(found[:60]))

    def test_the_checks_see_each_form(self):
        # written in two halves, so that this file itself holds none of them
        bad = [b'C' + rb':\Games2\x', b'C' + rb':\GamesOfMine\x', b'D' + rb':\1st\x', b'C' + rb':\Users\someone\x',
               b'/c/Use' + b'rs/someone/x', b'/mnt/d/Use' + b'rs/someone/x', rb'"\\file' + rb'server\share\x"',
               rb'"\\\\file' + rb'server\\share"', b' /ho' + b'me/someone/x']
        for sample in bad:
            self.assertTrue(problems('sample', sample), sample)
        good = [rb'C:\Games\x', rb'C:\Program Files (x86)\Steam', rb'C:\Users\you\x', rb'/c/Users/<name>/x',
                rb'"\\host\share\f"', rb'<lab>\\builds\\x', rb'"\\\\?\\C:\\Windows"', rb'see %USERPROFILE%\x']
        for sample in good:
            self.assertEqual(problems('sample', sample), [], sample)
        # picture metadata: a PNG text chunk is read
        chunk = b'tEXt' + b'Source\0D:\\private-stuff\\x.png'
        png = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', len(chunk) - 4) + chunk + struct.pack('>I', zlib.crc32(chunk))
        self.assertTrue(problems('p', picture_metadata(png)))

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
        folders = {f.rsplit('/', k)[0] for f in present for k in range(1, f.count('/') + 1)}
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
                    if path not in present and path not in folders:
                        broken.append('%s:%d: %s' % (f, n, target))
        self.assertEqual(broken, [], 'links that lead nowhere (or into a folder Git ignores):\n' + '\n'.join(broken[:80]))


if __name__ == '__main__':
    unittest.main()
