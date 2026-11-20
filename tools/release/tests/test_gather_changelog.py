"""The change ledger kept as one file per entry (tools/release/gather_changelog.py): the real entry files are well
formed, and gathering puts entries under their day, newest first, with their links re-based."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gather_changelog as g  # noqa: E402


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))


class RealEntries(unittest.TestCase):
    def test_the_entry_files_are_well_formed(self):
        self.assertEqual(g.check(), [])


class Gathering(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        write(self.repo / 'tools' / 'a.py', 'x')
        write(self.repo / 'changelog' / 'entries' / 'README.md', '# not an entry\n')
        self.entries = self.repo / 'changelog' / 'entries'

    def entry(self, name, text):
        write(self.entries / name, text)
        return self.entries / name

    def test_entries_go_under_their_day_newest_first_with_links_rebased(self):
        write(self.repo / 'changelog' / '2026-11.md', g.month_header(2026, 11) + '\n## 19 November 2026\n\n### Old\n\nold text\n')
        times = {}
        times[self.entry('2026-11-20-first.md', '### First\n\nSee [a](../../tools/a.py) and `[b](x.py)`.\n')] = 10
        times[self.entry('2026-11-20-second.md', '### Second\n\nnothing\n')] = 20
        times[self.entry('2026-11-19-late.md', '### Late on the 19th\n\nmore\n')] = 5
        times[self.entry('2026-12-01-december.md', '### December\n\n[a](../../tools/a.py#L3)\n')] = 30
        g.gather(self.repo, when=lambda p: times[p], out=lambda *a: None)
        nov = (self.repo / 'changelog' / '2026-11.md').read_text(encoding='utf-8')
        order = [nov.index(s) for s in ('## 20 November', '### Second', '### First', '## 19 November', '### Late', '### Old')]
        self.assertEqual(order, sorted(order))
        self.assertIn('[a](../tools/a.py)', nov)
        self.assertIn('`[b](x.py)`', nov)              # code is left alone
        dec = (self.repo / 'changelog' / '2026-12.md').read_text(encoding='utf-8')
        self.assertTrue(dec.startswith('# Change ledger: December 2026'))
        self.assertIn('[a](../tools/a.py#L3)', dec)
        self.assertEqual(sorted(p.name for p in self.entries.iterdir()), ['README.md'])

    def test_an_uncommitted_entry_counts_as_the_newest(self):
        self.entry('2026-11-20-a.md', '### A\n\na\n')
        self.entry('2026-11-20-b.md', '### B\n\nb\n')
        rows = g.ordered(self.repo, when=lambda p: None if p.name == '2026-11-20-a.md' else 100)
        self.assertEqual([r[2] for r in rows], ['A', 'B'])

    def test_a_new_day_lands_between_older_and_newer_days(self):
        write(self.repo / 'changelog' / '2026-11.md',
              g.month_header(2026, 11) + '\n## 20 November 2026\n\n### New\n\nx\n\n## 5 November 2026\n\n### Old\n\ny\n')
        self.entry('2026-11-12-mid.md', '### Mid\n\nm\n')
        g.gather(self.repo, when=lambda p: 1, out=lambda *a: None)
        nov = (self.repo / 'changelog' / '2026-11.md').read_text(encoding='utf-8')
        order = [nov.index(s) for s in ('## 20 November', '## 12 November', '### Mid', '## 5 November')]
        self.assertEqual(order, sorted(order))

    def test_check_names_each_problem_and_gather_refuses_them(self):
        self.entry('Bad Name.md', '### X\n')
        self.entry('2026-11-20-no-title.md', 'text\n')
        self.entry('2026-11-20-broken-link.md', '### Y\n\n[gone](../../tools/gone.py)\n')
        self.entry('2026-11-20-crlf.md', '### Z\r\n')
        problems = '\n'.join(g.check(self.repo))
        for needed in ('Bad Name.md', 'no-title.md', 'gone.py', 'crlf.md'):
            self.assertIn(needed, problems)
        with self.assertRaises(g.EntryError):
            g.gather(self.repo, when=lambda p: 1, out=lambda *a: None)
        self.assertTrue((self.entries / '2026-11-20-broken-link.md').exists())


if __name__ == '__main__':
    unittest.main()
