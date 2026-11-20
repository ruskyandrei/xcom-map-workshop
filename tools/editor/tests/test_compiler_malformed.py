"""Malformed records through the compiler (review finding 38): a record a hand edit, a copied project or a newer editor
wrote in a shape this compiler can't read is left out of the build and named, and the rest of the project builds. Each
case here crashed the compiler before (KeyError, AttributeError or TypeError), and the build window showed the
traceback's last line."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from compiler import compile_project  # noqa: E402
from test_compiler import PL, add, document, scene, target  # noqa: E402

# a copy that builds, beside each malformed record: the build goes on with it
GOOD = add('XComLevelActor_1', 1, (96, 96, 0))
POSE = dict(location=[0, 0, 0], rotation=[0, 0, 0])
CASES = {
    'a template of null and no source': ('added', dict(id='x', actor=PL + 'Foo_copy2', template=None, **POSE), 'malformed'),
    'a template of null with a source': ('added', dict(id='x', actor=PL + 'XComLevelActor_1_copy2', template=None,
                                                       components=[PL + 'XComLevelActor_1.StaticMeshComponent_0'],
                                                       **{'from': target('XComLevelActor_1')}, **POSE), 'malformed'),
    'a cover recipe whose version is a list': ('added', dict(id='x', actor=PL + 'CoverBlock_copy2',
                                                             template=dict(kind='cover', version=[1]),
                                                             cover=dict(type='high', size=[96, 96]), **POSE), 'cover-recipe'),
    'a light recipe whose kind is a list': ('added', dict(id='x', actor=PL + 'SpotLight_copy2',
                                                          template=dict(kind=['spot'], version=1), light={}, **POSE),
                                            'light-recipe'),
    'a made piece whose kind is a list': ('added', dict(add('XComLevelActor_2', 2, (0, 0, 0)), generated=dict(kind=['fracWall'])),
                                          'malformed'),
    'an override whose actor is a list': ('overrides', dict(target=dict(package='URB_Bar', level='base', actor=[1]),
                                                            deleted=True), 'malformed'),
}


class MalformedRecords(unittest.TestCase):
    def test_each_malformed_record_is_left_out_and_the_rest_builds(self):
        for name, (lane, record, code) in CASES.items():
            with self.subTest(name):
                doc = document(added=[GOOD] + ([record] if lane == 'added' else []),
                               overrides=[record] if lane == 'overrides' else [])
                spec, report = compile_project(doc, scene())
                self.assertTrue(report['ok'], report['errors'])
                self.assertIsNotNone(spec)
                where = 'added[1]' if lane == 'added' else 'overrides[0]'
                self.assertEqual([(e['record'], e['code']) for e in report['leftOut']], [(where, code)])
                # the good copy is built
                self.assertIn('XComLevelActor_1_copy1', [label for o in spec['objects'] for label in o.get('labels', [])])

    def test_a_mission_or_zone_whose_kind_is_a_list_is_read_as_malformed(self):
        """missions.valid_entry and spawns.valid_zone look a kind up in a table: a list there is a malformed entry,
        never a TypeError."""
        _, report = compile_project(document(added=[GOOD], missions=[dict(record=0), dict(kind=[1])]), scene())
        self.assertIn('missions', [e['code'] for e in report['errors'] + report['leftOut']])
        _, report = compile_project(document(added=[GOOD], landingZones=[dict(id=[1], location=[0, 0, 64], direction='north',
                                                                              kind=['normal'])]), scene())
        self.assertIn('landing-shape', [e['code'] for e in report['errors'] + report['leftOut']])

    def test_buildings_that_are_no_list_do_not_stop_the_groups(self):
        for buildings in (True, 1.5, [dict(id=[1], name='B', kind='building', floors=[])]):
            with self.subTest(buildings=buildings):
                _, report = compile_project(document(added=[GOOD], buildings=buildings), scene())
                self.assertIn('building-shape', [e['code'] for e in report['errors'] + report['leftOut']])


if __name__ == '__main__':
    unittest.main()
