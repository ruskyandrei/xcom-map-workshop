"""Effects and ambient sounds in the compiler (the effects and sounds plan, Part C, stage FX3): their overrides and
added records, checked against the export's effects and sounds (export 28: `can`, `why`, carrying, the landing's,
the mission's script), the families' gates, carrying taken away by a record of the effect's own, the floors' note
and the native edit's `effects` and `sounds` lanes. A made-up scene: no install needed."""
import copy
import sys
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import compiler  # noqa: E402
from compiler import compile_project, native_split, stream_only  # noqa: E402
from test_compiler import PL, document, scene, target  # noqa: E402

CAN = dict(move=True, copy=True, delete=True, values=False)


def effect(name, at=(0, 0, 0), kind='effect', cls='Emitter', can=None, why=None, **extra):
    rec = dict(kind=kind, id='%s:%s' % (kind, name), actor=PL + name, actorClass=cls, sourcePackage='URB_Bar',
               layer='base', stream=None, location=list(map(float, at)), rotation=[0, 0, 0], listed=True,
               referencedBy=[], attachedTo=None, landingRole=None, carriedBy=None, floors=[], startsOn=True,
               can=dict(CAN, **(can or {})), why=dict(why or {}))
    rec.update(extra)
    return rec


def effects_scene():
    s = scene()
    s['exporterVersion'] = 28
    s['effects'] = [
        effect('Emitter_40', at=(0, 0, 0), carriedBy=PL + 'XComLevelActor_1'),
        effect('Emitter_41', at=(500, 500, 0), landingRole='skyranger',
               can=dict(move=False, delete=False), why=dict(move='it is the landing\'s', delete='it is the landing\'s')),
        effect('Emitter_42', at=(600, 0, 0), attachedTo=dict(actor=PL + 'InterpActor_1'),
               can=dict(move=False, copy=False, delete=False), why={k: 'it rides on InterpActor_1' for k in ('move', 'copy', 'delete')}),
        effect('Emitter_43', at=(700, 0, 0), startsOn=False, referencedBy=['SeqAct_Toggle_3']),
        effect('Emitter_44', at=(120, 120, 200), floors=[dict(building='7', floor=1)]),
    ]
    s['sounds'] = [effect('AmbientSoundSimple_50', at=(100, 0, 0), kind='sound', cls='AmbientSoundSimple'),
                   effect('AmbientSound_51', at=(200, 0, 0), kind='sound', cls='AmbientSound')]
    s['flares'] = [effect('LensFlareSource_60', at=(300, 0, 0), kind='flare', cls='LensFlareSource')]
    stream = effect('Emitter_9', at=(0, 0, 0), stream='patch_bar', can=dict(move=False, copy=False, delete=False))
    stream.update(sourcePackage='patch_bar', layer='stream')
    s['streams'] = {'patch_bar': dict(kind='lwr', effects=[stream], sounds=[], flares=[])}
    # a building whose floor 1 holds (0..240, 0..240, 128..320)
    box = lambda x0, y0, z0, x1, y1, z1: dict(min=[x0, y0, z0], max=[x1, y1, z1])
    s['buildings'] = [dict(id='7', name=PL + 'XComBuildingVolume_7', floors=[
        dict(index=0, boxes=[box(0, 0, 0, 240, 240, 128)], members=[]),
        dict(index=1, boxes=[box(0, 0, 128, 240, 240, 320)], members=[])])]
    return s


def doc(overrides=(), added=(), **changes):
    return document(overrides, added, schemaVersion=3, **changes)


def moved(name, at, rot=(0, 0, 0), **extra):
    return dict(target=target(name), location=list(at), rotation=list(rot), **extra)


def copied(name, serial, at, kind='effect', **extra):
    return dict(id='00000000-0000-4000-8000-%012d' % serial, actor=PL + '%s_copy%d' % (name, serial), kind=kind,
                **{'from': target(name)}, location=list(at), rotation=[0, 0, 0], **extra)


def codes(report):
    return [d['code'] for d in report['errors'] + report['leftOut']]


def families_off():
    """The effect and sound families held back, as they were until EXP-68 passed: their gate's refusal."""
    return mock.patch.dict(compiler.FAMILIES, {k: dict(compiler.FAMILIES[k], builds=False) for k in ('effect', 'sound')})


class Gates(unittest.TestCase):
    def test_on_since_exp68(self):
        self.assertTrue(compiler.FAMILIES['effect']['builds'] and compiler.FAMILIES['sound']['builds'])
        _, report = compile_project(doc([moved('Emitter_43', (710, 0, 0)), moved('AmbientSoundSimple_50', (110, 0, 0))]),
                                    effects_scene())
        self.assertEqual(codes(report), [])

    @families_off()
    def test_off_until_enabled(self):
        spec, report = compile_project(doc([moved('Emitter_43', (710, 0, 0))]), effects_scene())
        self.assertEqual(codes(report), ['family'])
        spec, report = compile_project(doc([moved('Emitter_43', (710, 0, 0))]), effects_scene(), enable=('effect',))
        self.assertEqual(codes(report), [])
        self.assertEqual(spec['objects'], [dict(type='effects', moves=[dict(
            name='Emitter_43', actorClass='Emitter', location=[710.0, 0.0, 0.0], rotation=[0, 0, 0],
            before=dict(location=[700.0, 0.0, 0.0], rotation=[0, 0, 0]))], deletes=[], copies=[])])

    @families_off()
    def test_each_family_its_own_gate(self):
        records = [moved('Emitter_43', (710, 0, 0)), moved('AmbientSoundSimple_50', (110, 0, 0))]
        _, report = compile_project(doc(records), effects_scene(), enable=('effect',))
        self.assertEqual([(e['code'], e.get('family')) for e in report['leftOut']], [('family', 'sound')])
        _, report = compile_project(doc(records), effects_scene(), enable=('effect', 'sound'))
        self.assertEqual(codes(report), [])
        self.assertEqual(report['counts']['effects'], dict(moved=1, deleted=0, added=0))
        self.assertEqual(report['counts']['sounds'], dict(moved=1, deleted=0, added=0))

    def test_schema_three(self):
        self.assertEqual((compiler.SCHEMA_VERSION, compiler.READ_VERSIONS), (3, (1, 2, 3)))
        _, report = compile_project(document([], schemaVersion=4), effects_scene())
        self.assertEqual(codes(report), ['schema'])


class Records(unittest.TestCase):
    ON = ('effect', 'sound')

    def compile(self, overrides=(), added=(), s=None, **changes):
        return compile_project(doc(overrides, added, **changes), s or effects_scene(), enable=self.ON)

    def test_move_delete_copy_reach_the_native_lanes(self):
        spec, report = self.compile([moved('Emitter_43', (710, 0, 0), (0, 16384, 0)), dict(target=target('AmbientSound_51'), deleted=True)],
                                    [copied('Emitter_43', 1, (720, 0, 0)), copied('AmbientSoundSimple_50', 2, (150, 0, 0), kind='sound')])
        self.assertEqual(codes(report), [])
        patch, native = native_split(stream_only(spec))
        self.assertEqual(patch['objects'], [])
        self.assertEqual([m['name'] for m in native['effects']['moves']], ['Emitter_43'])
        self.assertEqual(native['effects']['copies'], [dict(id='00000000-0000-4000-8000-000000000001', name='Emitter_43_copy1',
                                                            source='Emitter_43', actorClass='Emitter', location=[720.0, 0.0, 0.0],
                                                            rotation=[0, 0, 0])])
        self.assertEqual([d['name'] for d in native['sounds']['deletes']], ['AmbientSound_51'])
        self.assertEqual([c['source'] for c in native['sounds']['copies']], ['AmbientSoundSimple_50'])
        # the script names Emitter_43: moved, the script acts on it where it stands; its copy starts off with nothing
        # to switch it on
        self.assertEqual(sorted(w['code'] for w in report['warnings']), ['effect-starts-off', 'mission-linked'])
        self.assertIn('effect-script-copy', [n['code'] for n in report['notes']])

    def test_a_record_of_its_own_takes_it_from_its_piece(self):
        spec, _ = self.compile([moved('XComLevelActor_1', (0, 96, 0))])
        self.assertEqual(spec['carriedEffects'], {'XComLevelActor_1': ['Emitter_40']})
        for record in (moved('Emitter_40', (10, 0, 0)), dict(target=target('Emitter_40'), deleted=True),
                       dict(target=target('Emitter_40'), effect=dict(follow='none'))):
            spec, report = self.compile([moved('XComLevelActor_1', (0, 96, 0)), record])
            self.assertEqual(codes(report), [], record)
            self.assertNotIn('carriedEffects', spec, record)
        # follow auto: it follows as the map has it, and has no pose of its own
        spec, report = self.compile([moved('XComLevelActor_1', (0, 96, 0)), dict(target=target('Emitter_40'), effect=dict(follow='auto'))])
        self.assertEqual(spec['carriedEffects'], {'XComLevelActor_1': ['Emitter_40']})
        _, report = self.compile([moved('Emitter_40', (10, 0, 0), effect=dict(follow='auto'))])
        self.assertEqual(codes(report), ['malformed'])

    def test_what_the_export_says_can_not_be_done(self):
        for record, words in ((moved('Emitter_41', (510, 500, 0)), 'landing'), (dict(target=target('Emitter_42'), deleted=True), 'rides on'),
                              (moved('Emitter_9', (5, 0, 0)) | dict(target=target('Emitter_9', 'stream', 'patch_bar')), 'patch_bar'),
                              (moved('LensFlareSource_60', (305, 0, 0)), 'lens flare')):
            _, report = self.compile([record])
            self.assertEqual(codes(report), ['effect-view-only'], record)
            self.assertIn(words, (report['errors'] + report['leftOut'])[0]['message'])
        _, report = self.compile([], [copied('Emitter_42', 1, (0, 0, 0))])
        self.assertEqual(codes(report), ['effect-view-only'])

    def test_malformed_and_later_values(self):
        cases = [(moved('Emitter_43', (710, 0, 0), effect=dict(scale=2.0)), 'effect-values'),
                 (moved('Emitter_43', (710, 0, 0), effect=dict(colour=1)), 'malformed'),
                 (moved('Emitter_43', (710, 0, 0), effect=dict(follow='sometimes')), 'malformed'),
                 (moved('Emitter_43', (710, 0, 0), sound=dict(volume=[1, 1])), 'malformed'),
                 (moved('AmbientSoundSimple_50', (110, 0, 0), sound=dict(radiusMax=900)), 'effect-values'),
                 (dict(target=target('Emitter_43')), 'malformed'),
                 (moved('XComLevelActor_1', (0, 96, 0), effect=dict(follow='none')), 'malformed')]
        for record, code in cases:
            _, report = self.compile([record])
            self.assertEqual(codes(report), [code], record)
        added = [(copied('Emitter_43', 1, (0, 0, 0), kind='sound'), 'malformed'),
                 (copied('Emitter_43', 1, (0, 0, 0), components=['x']), 'malformed'),
                 (copied('Emitter_43', 1, (0, 0, 0), kind='decal'), 'malformed'),
                 (copied('Emitter_99', 1, (0, 0, 0)), 'missing'),
                 (copied('Emitter_43', 1, (0, 0, float('nan'))), 'malformed')]
        for record, code in added:
            _, report = self.compile([], [record])
            self.assertEqual(codes(report), [code], record)

    def test_unchanged_builds_nothing(self):
        spec, report = self.compile([moved('Emitter_43', (700, 0, 0))])
        self.assertIsNone(spec.get('effects'))
        self.assertEqual(spec['objects'], [])
        self.assertIn('unchanged', [n['code'] for n in report['notes']])

    def test_floors_note(self):
        # into floor 1's box: it joins floor 2's cutaway (floors counted from 1 in words)
        _, report = self.compile([moved('Emitter_43', (100, 100, 200))])
        note, = [n for n in report['notes'] if n['code'] == 'effect-floors']
        self.assertEqual((note['joins'], note['leaves']), ([['XComBuildingVolume_7', 1]], []))
        self.assertIn('joins the cutaway of floor 2 of XComBuildingVolume_7', note['message'])
        # out of it: Emitter_44 leaves the floor that lists it; on the lowest floor nothing lists it
        _, report = self.compile([moved('Emitter_44', (100, 100, 50))])
        note, = [n for n in report['notes'] if n['code'] == 'effect-floors']
        self.assertEqual((note['joins'], note['leaves']), ([], [['XComBuildingVolume_7', 1]]))
        # within the slack of 2 units outside the box: listed; 3 units out: not
        for x, joins in ((242.0, True), (243.0, False)):
            _, report = self.compile([], [copied('Emitter_43', 1, (x, 100, 200))])
            self.assertEqual(any(n['code'] == 'effect-floors' for n in report['notes']), joins, x)
        # a sound joins no floor
        _, report = self.compile([moved('AmbientSoundSimple_50', (100, 100, 200))])
        self.assertFalse(any(n['code'] == 'effect-floors' for n in report['notes']))

    def test_groups_hold_them_without_breaking(self):
        groups = [dict(id='g', locked=True, breakTogether=True, members=[target('Emitter_43'), {'added': PL + 'Emitter_43_copy1'},
                                                                        target('XComDestructibleActor_4')])]
        _, report = self.compile([], [copied('Emitter_43', 1, (720, 0, 0))], groups=groups)
        self.assertEqual(codes(report), [])
        self.assertFalse([w for w in report['warnings'] if w['code'] == 'group-member'])


if __name__ == '__main__':
    unittest.main()
