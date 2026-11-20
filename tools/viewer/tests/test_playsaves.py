"""A play's saves put apart from a campaign's (playsaves.py, F-89; review finding 1): the campaign's save in a slot the
play wrote over goes back and the play's own save moves to a fresh slot, with one slot, contiguous slots or gaps, and a
restore stopped after any of its moves and copies, run again, loses neither save."""
from pathlib import Path
import os
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import playsaves  # noqa: E402


def save(game, body, broken=False):
    """A save's bytes: a campaign's (game number above 0) or a play's (game 0, opened from the shell), whole or broken
    (its header again and again before the data, F-89)."""
    def text(s):
        b = s.encode('latin-1') + b'\0'
        return struct.pack('<i', len(b)) + b
    command = 'open URB_Bar?game=XComGame.XComTacticalGame?' + ('LoadingFromShell=1' if game == 0 else 'LoadingFromStrategy=1')
    head = struct.pack('<4i', 16, 0, game, 0) + text(f'Game {game}') + text('11/20/2026 - 10:45') + text(command)
    head += bytes(playsaves.HEADER - len(head))
    return head * (5 if broken else 1) + playsaves.PACKAGE_TAG + body


class Stop(Exception):
    """The restore stopped here (a failed copy, a stopped server)."""


class Faults:
    """Counts the restore's moves and copies (shutil.copy2 and move, os.replace, Path.replace, a copy's unlink) and stops
    it at one of them: before it does anything, or just after it is done."""
    def __init__(self, at=None, after=False):
        self.at, self.after, self.count, self.inside = at, after, 0, False

    def wrap(self, real):
        def step(*args, **kwargs):
            if self.inside: return real(*args, **kwargs)      # (Path.replace calls os.replace: one step)
            self.count += 1
            n = self.count
            if self.at == n and not self.after: raise Stop(f'stopped before step {n}')
            self.inside = True
            try: out = real(*args, **kwargs)
            finally: self.inside = False
            if self.at == n and self.after: raise Stop(f'stopped after step {n}')
            return out
        return step

    def __enter__(self):
        real_unlink = Path.unlink

        def unlink(path, missing_ok=False):
            if path.name.endswith('.restore.tmp'): return real_unlink(path, missing_ok=missing_ok)
            return self.wrap(real_unlink)(path, missing_ok=missing_ok)
        self.patches = [mock.patch.object(playsaves.shutil, 'copy2', self.wrap(shutil.copy2)),
                        mock.patch.object(playsaves.shutil, 'move', self.wrap(shutil.move)),
                        mock.patch.object(playsaves.os, 'replace', self.wrap(os.replace)),
                        mock.patch.object(Path, 'replace', self.wrap(Path.replace)),
                        mock.patch.object(Path, 'unlink', unlink)]
        for p in self.patches: p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches): p.stop()
        return False


class Restore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.n = 0

    def scenario(self, campaign, play, broken=False):
        """A save folder with the campaign's saves {slot: bytes}, readied for a play (keep), then the play's save
        written over slot `play`. Returns (folder, entry, the play's save bytes)."""
        self.n += 1
        root = Path(self.temp.name) / f'run{self.n}'
        folder = root / 'SaveData'
        folder.mkdir(parents=True)
        for n, data in campaign.items(): (folder / f'save{n}').write_bytes(data)
        entry = playsaves.keep(folder, root / 'copies', root / 'aside', 'p')
        mine = save(0, b'the play, in slot %d' % play, broken=broken)
        (folder / f'save{play}').write_bytes(mine)
        os.utime(folder / f'save{play}', ns=(1, 1))       # changed since keep, whatever the clock's grain
        return folder, entry, mine

    def check(self, folder, entry, campaign, mine, broken=False):
        """Every campaign save in its slot byte for byte, the play's save once (in a fresh slot, or set aside when broken),
        no copy and no temporary file left."""
        here = {p.name: p.read_bytes() for p in folder.iterdir()}
        for n, data in campaign.items(): self.assertEqual(here.pop(f'save{n}'), data, f'save{n}')
        if broken:
            self.assertEqual(here, {})
            aside = Path(entry['aside'])
            self.assertEqual([p.read_bytes() for p in aside.iterdir()], [mine])
        else:
            self.assertEqual(list(here.values()), [mine])
            slot = int(playsaves.SAVE.fullmatch(next(iter(here))).group(1))
            self.assertGreater(slot, max(campaign))
        self.assertFalse(any(Path(c['copy']).exists() for c in entry['copies'].values()))

    def test_one_slot_contiguous_slots_and_gaps(self):
        """With one occupied slot the move went to the play's own slot and the copy then overwrote the play's save
        (the first review's fixture); with contiguous slots the same happens when the play wrote the highest."""
        cases = [({1: save(7, b'one')}, 1), ({1: save(7, b'one'), 2: save(7, b'two'), 3: save(7, b'three')}, 3),
                 ({1: save(7, b'one'), 2: save(7, b'two'), 3: save(7, b'three')}, 1),
                 ({1: save(7, b'one'), 5: save(7, b'five')}, 1), ({2: save(7, b'two'), 9: save(7, b'nine')}, 9)]
        for campaign, play in cases:
            with self.subTest(slots=sorted(campaign), play=play):
                folder, entry, mine = self.scenario(campaign, play)
                done = playsaves.restore(entry)
                self.check(folder, entry, campaign, mine)
                self.assertEqual([r['name'] for r in done['restored']], [f'save{play}'])
                self.assertEqual(done['left'], [])
                # run again (the ledger not yet written when the server stopped): nothing changes
                playsaves.restore(entry)
                self.check(folder, entry, campaign, mine)

    def test_a_restore_stopped_after_any_move_or_copy_loses_neither_save(self):
        for campaign, play, broken in [({1: save(7, b'one')}, 1, False), ({1: save(7, b'one'), 2: save(7, b'two')}, 2, False),
                                       ({1: save(7, b'one'), 4: save(7, b'four')}, 1, False), ({1: save(7, b'one')}, 1, True)]:
            folder, entry, mine = self.scenario(campaign, play, broken)
            with Faults() as counted: playsaves.restore(entry)
            steps = counted.count
            self.assertGreaterEqual(steps, 3)       # a move or a setting aside, the copy back, its replace, the copy's removal
            for at in range(1, steps + 1):
                for after in (False, True):
                    with self.subTest(slots=sorted(campaign), play=play, broken=broken, step=at, after=after):
                        folder, entry, mine = self.scenario(campaign, play, broken)
                        with self.assertRaises(Stop), Faults(at, after): playsaves.restore(entry)
                        playsaves.restore(entry)       # the next try: from the copies as well as the slots
                        self.check(folder, entry, campaign, mine, broken)

    def test_a_copy_that_is_not_the_save_copied_stays(self):
        campaign = {1: save(7, b'one')}
        folder, entry, mine = self.scenario(campaign, 1)
        Path(entry['copies']['save1']['copy']).write_bytes(b'damaged')
        done = playsaves.restore(entry)
        self.assertEqual([l['name'] for l in done['left']], ['save1'])
        self.assertFalse((folder / 'save1').exists())             # nothing put back that isn't the save
        self.assertEqual((folder / 'save2').read_bytes(), mine)    # the play's own moved, whole
        self.assertTrue(Path(entry['copies']['save1']['copy']).is_file())
        self.assertEqual([p.name for p in folder.iterdir()], ['save2'])


if __name__ == '__main__':
    unittest.main()
