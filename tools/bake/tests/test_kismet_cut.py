"""The map's Kismet let go of the pieces an edit deletes (kismet_cut.py): on URB_Bar of the configured install, its
landing's grounded Skyranger and drop zone (which its Kismet hides at the landing, F-63) and a trigger volume an event
fires from, their references emptied, the event switched off, written and read back. Skips without the install."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402
import kismet_cut  # noqa: E402
import native_copy  # noqa: E402
import package_grow  # noqa: E402
import lighting_records as lighting  # noqa: E402
import scene_metadata  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
PL = 'TheWorld.PersistentLevel.'


@unittest.skipUnless(BAR, NO_BAR)
class Cut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = lighting.Package(BAR)
        cls.p = p
        named, _, _, _ = scene_metadata.kismet_walk(p)
        held = {a for refs in named.values() for a, _ in refs}
        # the landing's two pieces, and one trigger volume an event's Originator names
        cls.pieces = [p.by_name[PL + n] for n in ('XComLevelActor_138', 'XComLevelActor_6')]
        cls.trigger = next(i for i in range(1, len(p.exports) + 1)
                           if p.cls(i).startswith('SeqEvent') and p.own(i, 'Originator') in held
                           and p.cls(p.own(i, 'Originator')) == 'TriggerVolume')
        cls.volume = p.own(cls.trigger, 'Originator')
        g = package_grow.Grower(str(BAR))
        cls.record = kismet_cut.cut(g, p, cls.pieces + [cls.volume])
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        lighting.link_caches(out.parent, Path(BAR).parent)
        cls.q = lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_references_are_emptied_and_read_back(self):
        actors = {r['actor'] for r in self.record['cut']}
        self.assertTrue({'XComLevelActor_138', 'XComLevelActor_6', self.p.name(self.volume).rsplit('.', 1)[-1]} <= actors, actors)
        kismet_cut.verify(self.q, self.record)
        named, _, _, _ = scene_metadata.kismet_walk(self.q)
        held = {a for refs in named.values() for a, _ in refs}
        gone = {self.q.by_name[PL + a] for a in actors}
        self.assertFalse(held & gone)

    def test_the_event_left_without_its_originator_is_switched_off(self):
        name = self.p.name(self.trigger).replace(PL, '', 1)
        self.assertIn(name, self.record['off'])
        i = self.q.by_name[self.p.name(self.trigger)]
        self.assertFalse(self.q.effective(i, 'bEnabled', True))
        self.assertEqual(self.q.own(i, 'Originator') or 0, 0)

    def test_the_rest_of_the_kismet_is_as_it_was(self):
        # every other reference the map's Kismet holds is still held
        before, _, _, _ = scene_metadata.kismet_walk(self.p)
        after, _, _, _ = scene_metadata.kismet_walk(self.q)
        gone = set(self.pieces + [self.volume])
        keep = {(self.p.name(i), self.p.name(a), prop) for i, refs in before.items() for a, prop in refs if a not in gone}
        now = {(self.q.name(i), self.q.name(a), prop) for i, refs in after.items() for a, prop in refs}
        self.assertTrue(keep and keep <= now)

    def test_nothing_named_is_nothing_done(self):
        self.assertIsNone(kismet_cut.cut(None, self.p, []))
        self.assertIsNone(kismet_cut.cut(None, self.p, [self.p.by_name[PL + 'WorldInfo_0']] if PL + 'WorldInfo_0' in self.p.by_name else []))


if __name__ == '__main__':
    unittest.main()
