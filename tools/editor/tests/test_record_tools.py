"""The refactor's two record tools, their own logic (no install): build_outputs.py's masks, lanes, merge, plant and
compare, and compile_record.py's masks and compare. The tools themselves run Builds and the suite; these tests check
that what they compare is compared, and that a difference is said for its input or test alone."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import build_outputs as bo  # noqa: E402
import compile_record as cr  # noqa: E402

PL = 'TheWorld.PersistentLevel.'


def build_rec(files=None, manifest=None):
    return dict(error=None, tools=['native_copy.py'], relight=[], files=dict(files or {'CookedPCConsole/X.upk': 'a' * 64}),
                manifest=copy.deepcopy(manifest or dict(variant='X', stages=[dict(stage='light', seconds='<time>')])),
                compileReport=dict(counts=dict(moved=1)), work={'native-edit.json': dict(copies=[])})


def input_rec():
    return dict(exports={'URB_Bar': dict(generation='g-v37-map', sha256='e' * 64)}, project=dict(id='p', added=[]),
                projectSha256='p' * 64, compile=dict(spec=dict(objects=[]), report=dict(ok=True), patch=None, native={}),
                builds=dict(quick=build_rec(), baked=build_rec()))


def quiet(f, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = f(*args)
    return code, out.getvalue()


class BuildOutputsTests(unittest.TestCase):
    def test_the_same_records_compare_equal_and_a_file_differs_for_its_input_alone(self):
        a = dict(inputs=dict(one=input_rec(), two=input_rec()))
        b = copy.deepcopy(a)
        with tempfile.TemporaryDirectory() as tmp:
            for name, rec in (('a', a), ('b', b)):
                bo.write_json(Path(tmp) / name / 'outputs.json', rec)
            code, said = quiet(bo.compare, Path(tmp) / 'a', Path(tmp) / 'b')
            self.assertEqual(code, 0, said)
            b['inputs']['two']['builds']['baked']['files']['CookedPCConsole/X.upk'] = 'b' * 64
            bo.write_json(Path(tmp) / 'b' / 'outputs.json', b)
            code, said = quiet(bo.compare, Path(tmp) / 'a', Path(tmp) / 'b')
        self.assertEqual(code, 1)
        self.assertIn('two:\n  baked: CookedPCConsole/X.upk differs', said)
        self.assertNotIn('one:', said)

    def test_each_part_of_a_record_is_compared(self):
        a = input_rec()
        self.assertEqual(bo.compare_input(a, copy.deepcopy(a)), [])
        cases = [
            (lambda r: r['exports']['URB_Bar'].update(generation='g-v38-map'), 'export of URB_Bar differs'),
            (lambda r: r['project']['added'].append(1), 'project document differs'),
            (lambda r: r['compile']['native'].update(copies=[1]), 'compile native differs: copies[0]'),
            (lambda r: r['builds']['quick']['manifest']['stages'][0].update(stage='seeds'),
             'quick: manifest.json differs: stages[0].stage'),
            (lambda r: r['builds']['quick']['files'].pop('CookedPCConsole/X.upk'), 'quick: CookedPCConsole/X.upk only before'),
            (lambda r: r['builds']['baked'].update(relight=[dict(args=['x'])]), 'baked: relight command differs'),
            (lambda r: r['builds']['baked'].update(error='boom'), 'baked: the Build built / failed (boom)'),
            (lambda r: r['builds']['quick']['work']['native-edit.json']['copies'].append(dict(actor='A')),
             'quick: work record native-edit.json differs: copies[0].actor'),
        ]
        for change, words in cases:
            b = copy.deepcopy(a)
            change(b)
            lines = bo.compare_input(a, b)
            self.assertTrue(any(words in line for line in lines), (words, lines))

    def test_the_masks_take_folders_times_attempts_and_tool_hashes(self):
        # (made-up folders of the forms the repo suite allows in a tracked file)
        m = bo.Masker({r'C:\Games\repo\.scratch\out\scratch': '<scratch>', r'C:\Games\repo': '<repo>'})
        v = m.value(dict(work=r'C:\Games\REPO\.scratch\out\scratch\bar\quick\.work', file='C:/Games/repo/tools/x.py',
                         seconds=12.5, times=dict(full=3), attempt='abc', tools={'tools/editor/build.py': 'f' * 64},
                         stages=[dict(seconds=1.0, stage='light')], kept='C:\\Users\\you\\x'))
        self.assertEqual(v, dict(work=r'<scratch>\bar\quick\.work', file='<repo>/tools/x.py', seconds='<time>',
                                 times='<time>', attempt='<attempt>', tools={'tools/editor/build.py': '<sha256>'},
                                 stages=[dict(seconds='<time>', stage='light')], kept='C:\\Users\\you\\x'))

    def test_lanes_and_their_parts(self):
        native = dict(copies=[dict(actor='A', donor=dict(package='M'), family='car', generated=dict(kind='fracWall'))],
                      hides=[], breakOriginals=[], lights=dict(deletes=[1], changes=[], adds=[], area=[]),
                      effects=dict(moves=[], deletes=[], copies=[], values=[]), sounds=dict(moves=[1]),
                      covers=[dict(kind='floor')], landingZones=dict(zones=[]))
        lanes, parts = bo.lanes_of(native)
        self.assertEqual(lanes, ['copies', 'covers', 'landingZones', 'lights', 'sounds'])
        self.assertEqual(parts, ['copies.donor', 'copies.family.car', 'copies.generated', 'copies.generated.fracWall',
                                 'covers.floor', 'lights.deletes', 'sounds.moves'])

    def test_the_lanes_named_in_the_code_hold_the_listed_ones(self):
        found = bo.code_lanes()
        self.assertTrue(set(bo.LANES) <= set(found))
        # native_split's own keys are read from its code, and native_copy.py's
        self.assertIn('pieceFlagLadders', found)
        self.assertIn('streamTiles', found)

    def test_documents_merge_and_disagreements_are_refused(self):
        src = dict(map='URB_Bar', sha256='s' * 64)
        one = dict(id='1', name='one', source=dict(src, exporterVersion=19), schemaVersion=1, nextSerial=3,
                   added=[dict(id='a1', actor=PL + 'X_copy1')], overrides=[dict(target=dict(actor='Y'), deleted=True)])
        two = dict(id='2', name='two', source=dict(src, exporterVersion=37), schemaVersion=4, nextSerial=9,
                   added=[dict(id='a2', actor=PL + 'Z_copy1')], overrides=[dict(target=dict(actor='Y'), deleted=True)],
                   spawnRules=dict(dropIns='placed'))
        doc = bo.merged('t', [one, two])
        self.assertEqual((doc['id'], doc['name'], doc['schemaVersion'], doc['nextSerial']), ('1', 'one', 4, 9))
        self.assertEqual([r['id'] for r in doc['added']], ['a1', 'a2'])
        self.assertEqual(len(doc['overrides']), 1)      # the same delete, kept once
        self.assertEqual(doc['spawnRules'], dict(dropIns='placed'))
        for change in (lambda d: d['overrides'][0].update(deleted=False),            # one target, two edits
                       lambda d: d['added'][0].update(actor=PL + 'X_copy1'),        # one actor, two pieces
                       lambda d: d['source'].update(map='URB_PoliceStation')):      # another map
            bad = copy.deepcopy(two)
            change(bad)
            with self.assertRaises(SystemExit):
                bo.merged('t', [one, bad])

    def test_the_plant_changes_one_byte_of_one_copy(self):
        doc = dict(added=[dict(actor='A', location=[1259.0, 0.0, 0.0]),
                          dict(actor='B', **{'from': dict(actor='S')}, location=[-1250.5, 3.0, 0.0]),
                          dict(actor='C', **{'from': dict(actor='S')}, location=[129.0, 3.0, 0.0])])
        before = json.dumps(doc, indent=1, sort_keys=True)
        said = bo.plant(doc)
        after = json.dumps(doc, indent=1, sort_keys=True)
        self.assertIn('B', said)        # C's 129 would become 130 (two bytes); A copies nothing
        self.assertEqual(len(before), len(after))
        self.assertEqual(sum(x != y for x, y in zip(before, after)), 1)
        self.assertEqual(doc['added'][1]['location'][0], -1251.5)


class CompileRecordTests(unittest.TestCase):
    @staticmethod
    def call(n, test, outputs, inputs='i'):
        return dict(n=n, test=test, kind='compile', inputs=inputs, outputs=outputs)

    def record(self, calls):
        return dict(tests=2, failures=0, errors=0, count=len(calls), calls=calls)

    def test_the_first_differing_call_of_each_test(self):
        a = self.record([self.call(0, 't.A', dict(spec=dict(x=1))), self.call(1, 't.A', dict(spec=dict(x=2))),
                         self.call(2, 't.B', dict(spec=dict(y=1)))])
        b = copy.deepcopy(a)
        with tempfile.TemporaryDirectory() as tmp:
            pa, pb = Path(tmp) / 'a.json', Path(tmp) / 'b.json'
            pa.write_text(json.dumps(a), encoding='utf-8')
            pb.write_text(json.dumps(b), encoding='utf-8')
            code, said = quiet(cr.compare, pa, pb)
            self.assertEqual(code, 0, said)
            b['calls'][1]['outputs']['spec']['x'] = 3
            b['calls'][2]['inputs'] = 'j'
            pb.write_text(json.dumps(b), encoding='utf-8')
            code, said = quiet(cr.compare, pa, pb)
        self.assertEqual(code, 1)
        self.assertIn('t.A: call 2 of the test (compile, call 2 of the suite): outputs differ: spec.x', said)
        self.assertIn('t.B: call 1 of the test (compile, call 3 of the suite): its inputs differ', said)

    def test_a_call_more_or_fewer_is_a_difference(self):
        a = self.record([self.call(0, 't.A', {}), self.call(1, 't.A', {})])
        b = self.record([self.call(0, 't.A', {})])
        with tempfile.TemporaryDirectory() as tmp:
            pa, pb = Path(tmp) / 'a.json', Path(tmp) / 'b.json'
            pa.write_text(json.dumps(a), encoding='utf-8')
            pb.write_text(json.dumps(b), encoding='utf-8')
            code, said = quiet(cr.compare, pa, pb)
        self.assertEqual(code, 1)
        self.assertIn('t.A: call 2 of the test only before', said)

    def test_only_the_listed_input_keys_are_masked(self):
        m = cr.Masker(cr.INPUT_KEYS)
        v = m.value(dict(doc=dict(savedAt='now', name='n'), scene=dict(lights=[dict(lightGuid='1', lightmapGuid='2',
                                                                                     brightness=1.0)])))
        self.assertEqual(v, dict(doc=dict(savedAt='<masked>', name='n'),
                                 scene=dict(lights=[dict(lightGuid='<masked>', lightmapGuid='<masked>', brightness=1.0)])))
        self.assertEqual(cr.Masker().value(dict(savedAt='now')), dict(savedAt='now'))


if __name__ == '__main__':
    unittest.main()
