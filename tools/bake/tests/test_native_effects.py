"""Effects carried by their piece in the Build (native_effects.py): the tutorial's Skyranger moved, copied and
deleted with its lights (Emitter_4), on the configured install's Act1_IntroLevel (skipped without it)."""
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
import native_copy  # noqa: E402
from package import Package  # noqa: E402

INTRO, NO_INTRO = labpaths.install_map('Act1_IntroLevel')
SKY, LIGHTS = 'XComLevelActor_116', 'Emitter_4'
PAIRS = {SKY: [LIGHTS]}
PL = 'TheWorld.PersistentLevel.'


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class CarriedEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(INTRO)
        cls.sky = cls.p.by_name[PL + SKY]
        cls.at = cls.p.own(cls.sky, 'Location')
        cls.turn = cls.p.own(cls.sky, 'Rotation')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def build(self, name, copies, hides):
        out = Path(self.tmp.name) / name
        m = native_copy.build(INTRO, out, name, copies, hides=hides, carried_effects=PAIRS)
        return m, Package(out / ('%s.upk' % name))

    def test_moved_with_it(self):
        to = [self.at[0] + 960.0, self.at[1] - 480.0, self.at[2]]
        m, q = self.build('Moved', [dict(actor=SKY, location=to, rotation=[0, self.turn[1] + 16384, 0],
                                         label='move:' + SKY)], [dict(name=SKY, label='move:' + SKY)])
        rec, = m['nativeCopies']['carriedEffects']
        self.assertEqual((rec['effect'], rec['how'], rec['piece']), (LIGHTS, 'moved', SKY))
        e = q.by_name[PL + LIGHTS]
        self.assertIn(e, native_copy.level_actors(q))
        got = q.own(e, 'Location')
        self.assertTrue(all(abs(got[k] - to[k]) < 2.5 for k in range(3)), (got, to))
        self.assertEqual(q.own(e, 'Rotation')[1] - self.p.own(self.p.by_name[PL + LIGHTS], 'Rotation', [0, 0, 0])[1], 16384)

    def test_copied_with_it(self):
        to = [self.at[0] - 960.0, self.at[1], self.at[2]]
        m, q = self.build('Copied', [dict(actor=SKY, location=to, rotation=list(self.turn), label='copy')], [])
        rec, = m['nativeCopies']['carriedEffects']
        self.assertEqual(rec['how'], 'copied')
        clone = q.by_name[PL + rec['copy']]
        self.assertEqual(q.cls(clone), 'Emitter')
        self.assertIn(clone, native_copy.level_actors(q))
        self.assertIn(q.by_name[PL + LIGHTS], native_copy.level_actors(q))      # the original stays where it was
        self.assertTrue(all(abs(q.own(clone, 'Location')[k] - to[k]) < 2.5 for k in range(3)))

    def test_deleted_with_it(self):
        m, q = self.build('Deleted', [], [dict(name=SKY, label='delete:' + SKY)])
        rec, = m['nativeCopies']['carriedEffects']
        self.assertEqual(rec['how'], 'deleted')
        self.assertNotIn(q.by_name[PL + LIGHTS], native_copy.level_actors(q))


if __name__ == '__main__':
    unittest.main()
