"""The project's time of day (`sun`, schema 10; the game-likeness plan, T-S1) in the compiler: read for its shape alone
(light_edits.sun_mark, by tools/viewer/sun_curve.py's `problem` on the record cases the page's node test reads too); a
project with one compiles, makes no lane yet and is told in a note that the Build does not write it; one of another
shape is left out. A made-up scene: no install needed."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from compiler import compile_project, native_split, stream_only  # noqa: E402
from editor_fixtures import document, scene  # noqa: E402

CASES = HERE.parents[1] / 'viewer' / 'tests' / 'sun_record_cases.json'


def codes(entries):
    return sorted(e['code'] for e in entries)


class Sun(unittest.TestCase):
    def build(self, sun):
        spec, report = compile_project(document([], sun=sun), scene())
        native = native_split(stream_only(spec))[1] if spec else None
        return spec, report, native

    def test_the_record_cases(self):
        for case in json.loads(CASES.read_text(encoding='utf-8'))['cases']:
            with self.subTest(case['why']):
                spec, report, native = self.build(case['record'])
                self.assertTrue(report['ok'], report['errors'])
                if case['valid']:
                    self.assertEqual(codes(report['notes']), ['sun-not-built'])
                    self.assertEqual(report['leftOut'], [])
                else:
                    self.assertEqual(codes(report['leftOut']), ['sun-shape'])
                    self.assertNotIn('sun-not-built', codes(report['notes']))
                # no lane yet: the Build's is stage T-S2's
                self.assertNotIn('sun', spec or {})
                self.assertNotIn('sun', native or {})

    def test_the_note_says_the_time(self):
        record = json.loads(CASES.read_text(encoding='utf-8'))['cases'][1]['record']
        spec, report, native = self.build(record)
        note, = report['notes']
        self.assertIn('07:10', note['message'])
        self.assertIn('does not write it into the map yet', note['message'])
        self.assertEqual(report['warnings'], [])

    def test_no_record_says_nothing(self):
        spec, report, native = self.build(None)
        self.assertNotIn('sun-not-built', codes(report['notes']))
        self.assertEqual(report['leftOut'], [])


if __name__ == '__main__':
    unittest.main()
