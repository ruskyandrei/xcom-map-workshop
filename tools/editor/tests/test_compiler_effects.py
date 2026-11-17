"""Effects and ambient sounds in the compiler (the effects and sounds plan, Part C, stages FX3 to FX5): their
overrides and added records, checked against the export's effects and sounds (export 28: `can`, `why`, carrying, the
landing's, the mission's script), the families' gates, carrying taken away by a record of the effect's own, the
floors' note, their values (stage FX5) and the native edit's `effects` and `sounds` lanes. A made-up scene: no
install needed."""
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
from test_compiler import DONOR_SHA, PL, document, scene, target  # noqa: E402

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
            before=dict(location=[700.0, 0.0, 0.0], rotation=[0, 0, 0]))], deletes=[], copies=[], values=[])])

    @families_off()
    def test_each_family_its_own_gate(self):
        records = [moved('Emitter_43', (710, 0, 0)), moved('AmbientSoundSimple_50', (110, 0, 0))]
        _, report = compile_project(doc(records), effects_scene(), enable=('effect',))
        self.assertEqual([(e['code'], e.get('family')) for e in report['leftOut']], [('family', 'sound')])
        _, report = compile_project(doc(records), effects_scene(), enable=('effect', 'sound'))
        self.assertEqual(codes(report), [])
        self.assertEqual(report['counts']['effects'], dict(moved=1, deleted=0, added=0, valued=0))
        self.assertEqual(report['counts']['sounds'], dict(moved=1, deleted=0, added=0, valued=0))

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

    def test_a_copy_of_a_landing_actor_is_warned_of(self):
        """Long War's landing mutator destroys the landing's actors by archetype at every load (F-120): a copy of one
        builds, with the warning."""
        spec, report = self.compile([], [copied('Emitter_41', 7, (900, 0, 0))])
        self.assertEqual(codes(report), [])
        self.assertEqual([w['code'] for w in report['warnings']], ['effect-landing-copy'])
        self.assertIn('Long War', report['warnings'][0]['message'])
        _, report = self.compile([], [copied('Emitter_44', 8, (900, 0, 0))])
        self.assertEqual(report['warnings'], [])

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
        # (values while their families don't build: the gate's refusal, stage FX5's)
        cases = [(moved('Emitter_43', (710, 0, 0), effect=dict(scale=2.0)), 'family'),
                 (moved('Emitter_43', (710, 0, 0), effect=dict(colour=1)), 'malformed'),
                 (moved('Emitter_43', (710, 0, 0), effect=dict(follow='sometimes')), 'malformed'),
                 (moved('Emitter_43', (710, 0, 0), sound=dict(volume=[1, 1])), 'malformed'),
                 (moved('AmbientSoundSimple_50', (110, 0, 0), sound=dict(radiusMax=900)), 'family'),
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



class FakeEffects:
    """The library as the compiler asks it for another map's effect or sound (Library.effect): URB_PierA's, by actor;
    `entry` changes the index entry, `record` the export 28 record."""

    def __init__(self, fail=None, entry=None, record=None):
        self.fail, self.entry, self.record, self.asked = fail, entry or {}, record or {}, []

    def effect(self, wanted):
        self.asked.append(wanted)
        if self.fail:
            raise compiler.LibraryError(self.fail, 'the library says %s' % self.fail)
        name = wanted['actor'].rsplit('.', 1)[-1]
        kind = 'sound' if name.startswith('Ambient') else 'effect'
        rec = effect(name, at=(5000, 5000, 0), kind=kind, cls='AmbientSoundSimple' if kind == 'sound' else 'Emitter',
                     sourcePackage='URB_PierA', **self.record)
        template = dict(kind=kind, key='fx', record=rec, systems={}, waves={},
                        source=dict(kind='map', package='URB_PierA', level='base', actor=name, sha256=DONOR_SHA))
        # (held by the foreign gate until its game check: placeable as any copy, FOREIGN_SOFT)
        return template, dict(dict(key='fx', family=kind, placeable=False, blocked='family', reason='later'), **self.entry)


def foreign(name, serial, at, kind='effect'):
    return dict(copied(name, serial, at, kind=kind), **{'from': target(name, package='URB_PierA')})


class Foreign(unittest.TestCase):
    """Copies of other maps' effects and sounds (stage FX4): from the library, staged by the Build with their donor."""

    def compile(self, added, library):
        return compile_project(doc([], added), effects_scene(), (), library)

    def test_they_reach_the_lanes_with_their_donor(self):
        library = FakeEffects()
        spec, report = self.compile([foreign('Emitter_10', 1, (100, 100, 0)), foreign('Emitter_10', 2, (300, 100, 0)),
                                     foreign('AmbientSoundSimple_1', 3, (200, 0, 0), kind='sound')], library)
        self.assertEqual(codes(report), [])
        self.assertEqual(report['warnings'], [])
        _, native = native_split(stream_only(spec))
        donor = dict(package='URB_PierA', sha256=DONOR_SHA)
        self.assertEqual(native['effects']['copies'], [
            dict(id='00000000-0000-4000-8000-000000000001', name='Emitter_10_copy1', source='Emitter_10', actorClass='Emitter',
                 location=[100.0, 100.0, 0.0], rotation=[0, 0, 0], donor=donor),
            dict(id='00000000-0000-4000-8000-000000000002', name='Emitter_10_copy2', source='Emitter_10', actorClass='Emitter',
                 location=[300.0, 100.0, 0.0], rotation=[0, 0, 0], donor=donor)])
        self.assertEqual([(c['source'], c['donor']) for c in native['sounds']['copies']], [('AmbientSoundSimple_1', donor)])
        self.assertEqual(native['copies'], [])
        self.assertEqual(report['donors'], [dict(donor, pieces=['AmbientSoundSimple_1', 'Emitter_10'])])
        self.assertEqual(report['counts']['effects'], dict(moved=0, deleted=0, added=2, valued=0))
        self.assertEqual({e['donor']['package'] for e in report['entities']}, {'URB_PierA'})
        self.assertEqual(library.asked[0], target('Emitter_10', package='URB_PierA'))

    def test_the_donors_record_is_checked_as_a_copys_source(self):
        """What the donor's record says goes as for a copy of the map's own: a copy that starts off is warned of, one
        its map's script names is noted, one of another kind than the record says is malformed."""
        _, report = self.compile([foreign('Emitter_10', 1, (0, 0, 0))],
                                 FakeEffects(record=dict(startsOn=False, referencedBy=['SeqAct_Toggle_1'])))
        self.assertEqual([w['code'] for w in report['warnings']], ['effect-starts-off'])
        self.assertIn('effect-script-copy', [n['code'] for n in report['notes']])
        _, report = self.compile([foreign('Emitter_10', 1, (0, 0, 0), kind='sound')], FakeEffects())
        self.assertEqual(codes(report), ['malformed'])

    def test_what_the_library_can_not_bring_is_refused(self):
        cases = [(FakeEffects(entry=dict(blocked='unavailable', reason='It can not be brought: it rides on X.')), 'not-placeable'),
                 (FakeEffects(entry=dict(blocked='closure', reason='It needs a TextureMovie.')), 'not-placeable'),
                 (FakeEffects(fail='donor-changed'), 'donor-changed'),
                 (FakeEffects(fail='donor-missing'), 'donor-missing'),
                 (None, 'no-library')]
        for library, code in cases:
            _, report = self.compile([foreign('Emitter_10', 1, (0, 0, 0))], library)
            self.assertEqual(codes(report), [code], code)
        _, report = self.compile([foreign('Emitter_10', 1, (0, 0, 0))], FakeEffects(entry=dict(placeable=True, blocked=None)))
        self.assertEqual(codes(report), [])


def values_scene():
    """effects_scene with values that can change: Emitter_43 (scalar Opacity, vector Color, colour Tint, a random
    Wobble saved; its system offers Opacity, Color and Spawn, and Size both as a number and as a vector) and the
    simple sound AmbientSoundSimple_50 (radii 400 to 2,000); AmbientSound_51 plays a shared cue."""
    s = effects_scene()
    fx = {e['actor']: e for e in s['effects'] + s['sounds']}
    fx[PL + 'Emitter_43'].update(system='URB_Bar|FX.Glow', parameters=[
        dict(name='Opacity', type='PSPT_Scalar', scalar=1.0, offered='yes'),
        dict(name='Color', type='PSPT_Vector', vector=[1.0, 0.5, 0.0], offered='yes'),
        dict(name='Tint', type='PSPT_Color', colour=[1.0, 1.0, 1.0, 1.0], offered='no'),
        dict(name='Wobble', type='PSPT_ScalarRand', scalar=1.0, scalarLow=0.5, offered='no'),
        dict(name='Opacity', type='PSPT_Vector', vector=[0, 0, 0], offered='otherKind')])
    fx[PL + 'Emitter_44'].update(system='URB_Bar|FX.Glow', parameters=[])
    for name in ('Emitter_43', 'Emitter_44', 'AmbientSoundSimple_50'):
        fx[PL + name]['can'] = dict(fx[PL + name]['can'], values=True)
    fx[PL + 'AmbientSoundSimple_50']['values'] = dict(radiusMin=400.0, radiusMax=2000.0, volumeMin=0.7, volumeMax=0.7,
                                                      pitchMin=1.0, pitchMax=1.0)
    fx[PL + 'AmbientSound_51']['why'] = dict(values='its cue Hum is a game asset, not its own')
    offer = lambda name, kind: dict(name=name, kind=kind, module='M', property='P', modes=['DPM_Direct'], constant=1.0,
                                    input=[0.0, 1.0], output=[0.0, 1.0], colour=False)
    s['effectSystems'] = {'URB_Bar|FX.Glow': dict(path='FX.Glow', offers=[
        offer('Color', 'vector'), offer('Opacity', 'scalar'), offer('Size', 'scalar'), offer('Size', 'vector'),
        offer('Spawn', 'scalar')])}
    return s


class Values(unittest.TestCase):
    """An effect's size, starting state and parameters and a sound's radii, volume, pitch and starting state (stage
    FX5): checked against the export's record and its system, and passed to the lanes as the writer takes them."""
    ON = ('effect', 'sound', 'effect-values', 'sound-values')

    def compile(self, overrides=(), added=(), enable=ON):
        return compile_project(doc(overrides, added), values_scene(), enable=enable)

    def test_their_gates_are_their_own(self):
        self.assertFalse(compiler.FAMILIES['effect-values']['builds'] or compiler.FAMILIES['sound-values']['builds'])
        records = [dict(target=target('Emitter_43'), effect=dict(scale=2.0)),
                   dict(target=target('AmbientSoundSimple_50'), sound=dict(radiusMax=900.0))]
        _, report = self.compile(records, enable=('effect', 'sound'))
        self.assertEqual(sorted((e['code'], e.get('family')) for e in report['errors'] + report['leftOut']),
                         [('family', 'effect-values'), ('family', 'sound-values')])
        _, report = self.compile(records, enable=('effect', 'sound', 'effect-values'))
        self.assertEqual([(e['code'], e.get('family')) for e in report['errors'] + report['leftOut']],
                         [('family', 'sound-values')])
        # a move alone builds whatever the value gates say
        _, report = self.compile([moved('Emitter_43', (710, 0, 0))], enable=('effect',))
        self.assertEqual(codes(report), [])

    def test_values_alone_reach_the_values_lane(self):
        spec, report = self.compile([
            dict(target=target('Emitter_43'), effect=dict(scale=2.5, startsOn=True, parameters=[
                dict(name='Opacity', value=0.5), dict(name='Color', value=[0.2, 0.4, 3.0]),
                dict(name='Tint', value=[1.0, 0.0, 0.0, 1.0]), dict(name='Spawn', value=4)])),
            dict(target=target('AmbientSoundSimple_50'), sound=dict(radiusMax=900.0, volume=[0.5, 0.9], pitch=[0.9, 1.1],
                                                                     startsOn=False))])
        self.assertEqual(codes(report), [])
        _, native = native_split(stream_only(spec))
        self.assertEqual(native['effects']['values'], [dict(name='Emitter_43', actorClass='Emitter', effect=dict(
            scale=2.5, startsOn=True, parameters=[
                dict(name='Opacity', type='PSPT_Scalar', value=0.5),
                dict(name='Color', type='PSPT_Vector', value=[0.2, 0.4, 3.0]),
                dict(name='Tint', type='PSPT_Color', value=[1.0, 0.0, 0.0, 1.0]),
                dict(name='Spawn', type='PSPT_Scalar', value=4.0)]))])
        self.assertEqual(native['sounds']['values'], [dict(name='AmbientSoundSimple_50', actorClass='AmbientSoundSimple', sound=dict(
            radiusMax=900.0, volume=[0.5, 0.9], pitch=[0.9, 1.1], startsOn=False))])
        self.assertEqual((native['effects']['moves'], native['sounds']['moves']), ([], []))
        self.assertEqual(report['counts']['effects']['valued'], 1)
        # the script switches Emitter_43 (SeqAct_Toggle_3): what it starts as lasts until then; the sound starts off
        # with nothing to switch it on
        self.assertEqual(sorted(w['code'] for w in report['warnings']), ['effect-starts-off', 'mission-linked'])
        self.assertEqual([e['op'] for e in report['entities']], ['values', 'values'])

    def test_a_move_with_values_and_a_copy_with_values(self):
        spec, report = self.compile([moved('Emitter_44', (130, 120, 200), effect=dict(scale=0.5))],
                                    [copied('Emitter_43', 1, (720, 0, 0), effect=dict(startsOn=True, parameters=[dict(name='Opacity', value=2)])),
                                     copied('AmbientSoundSimple_50', 2, (150, 0, 0), kind='sound', sound=dict(radiusMin=100.0))])
        self.assertEqual(codes(report), [])
        _, native = native_split(stream_only(spec))
        self.assertEqual([m['name'] for m in native['effects']['moves']], ['Emitter_44'])
        self.assertEqual(native['effects']['values'], [dict(name='Emitter_44', actorClass='Emitter', effect=dict(scale=0.5))])
        self.assertEqual(native['effects']['copies'][0]['values'], dict(startsOn=True, parameters=[
            dict(name='Opacity', type='PSPT_Scalar', value=2.0)]))
        self.assertEqual(native['sounds']['copies'][0]['values'], dict(radiusMin=100.0))
        # the copy of Emitter_43 (which starts off) is set to start on: no starts-off warning
        self.assertNotIn('effect-starts-off', [w['code'] for w in report['warnings']])
        self.assertEqual(report['counts']['effects']['valued'], 2)

    def test_a_copy_set_to_start_off_is_warned_of(self):
        _, report = self.compile([], [copied('Emitter_44', 1, (720, 0, 0), effect=dict(startsOn=False))])
        self.assertEqual([w['code'] for w in report['warnings']], ['effect-starts-off'])
        self.assertIn('set to start off', report['warnings'][0]['message'])

    def test_parameters_the_script_sets_are_warned_of(self):
        s = values_scene()
        next(e for e in s['effects'] if e['actor'] == PL + 'Emitter_44')['referencedBy'] = ['SeqAct_SetParticleSysParam_1 Target']
        _, report = compile_project(doc([dict(target=target('Emitter_44'), effect=dict(parameters=[dict(name='Opacity', value=0.1)]))]),
                                    s, enable=self.ON)
        self.assertEqual(codes(report), [])
        self.assertEqual([w['code'] for w in report['warnings']], ['mission-linked'])
        self.assertIn('replaces these', report['warnings'][0]['message'])

    def test_deletion_wins(self):
        spec, report = self.compile([dict(target=target('Emitter_43'), deleted=True, effect=dict(scale=2.0))])
        self.assertEqual(codes(report), [])
        _, native = native_split(stream_only(spec))
        self.assertEqual((native['effects']['values'], [d['name'] for d in native['effects']['deletes']]), ([], ['Emitter_43']))

    def test_what_can_not_be_set(self):
        cases = [
            # the export says its values can't change: a shared cue's, an effect with no particle component
            (dict(target=target('AmbientSound_51'), sound=dict(radiusMax=900.0)), 'effect-view-only', 'game asset'),
            (dict(target=target('Emitter_40'), effect=dict(scale=2.0)), 'effect-view-only', 'values'),
            # parameters: a random one is kept; a name its system reads as both kinds; a name it doesn't have
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Wobble', value=1)])), 'effect-view-only', 'PSPT_ScalarRand'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Size', value=1)])), 'effect-view-only', 'both'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Glow', value=1)])), 'malformed', 'no parameter Glow'),
            # shapes and ranges
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Color', value=1)])), 'malformed', 'three numbers'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Tint', value=[2, 0, 0, 1])])), 'malformed', 'colour'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Opacity', value=float('inf'))])), 'malformed', 'a number'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=[dict(name='Opacity', value=1), dict(name='Opacity', value=2)])), 'malformed', 'twice'),
            (dict(target=target('Emitter_43'), effect=dict(parameters=dict(Opacity=1))), 'malformed', 'list'),
            (dict(target=target('Emitter_43'), effect=dict(scale=0)), 'malformed', 'multiplier'),
            (dict(target=target('Emitter_43'), effect=dict(scale=100)), 'malformed', 'multiplier'),
            (dict(target=target('Emitter_43'), effect=dict(startsOn='yes')), 'malformed', 'true or false'),
            (dict(target=target('AmbientSoundSimple_50'), sound=dict(radiusMin=3000.0)), 'malformed', 'beyond its outer'),
            (dict(target=target('AmbientSoundSimple_50'), sound=dict(radiusMax=-1)), 'malformed', '0 to'),
            (dict(target=target('AmbientSoundSimple_50'), sound=dict(volume=[0.9, 0.5])), 'malformed', 'least, most'),
            (dict(target=target('AmbientSoundSimple_50'), sound=dict(pitch=[0, 1])), 'malformed', 'least, most'),
            (dict(target=target('AmbientSoundSimple_50'), sound=dict(volume=0.5)), 'malformed', 'least, most')]
        for record, code, words in cases:
            _, report = self.compile([record])
            self.assertEqual(codes(report), [code], record)
            self.assertIn(words, (report['errors'] + report['leftOut'])[0]['message'], record)
        # a copy's values are checked against its source as an override's are
        _, report = self.compile([], [copied('AmbientSound_51', 1, (0, 0, 0), kind='sound', sound=dict(volume=[1, 1]))])
        self.assertEqual(codes(report), ['effect-view-only'])

    def test_a_foreign_copys_values_are_checked_against_its_donor(self):
        library = FakeEffects(record=dict(system='URB_PierA|FX.Foam', can=dict(CAN, values=True), parameters=[]))
        original = library.effect

        def effect_with_system(wanted):
            template, entry = original(wanted)
            template['systems'] = {'URB_PierA|FX.Foam': dict(offers=[dict(name='Spawn', kind='scalar')])}
            return template, entry
        library.effect = effect_with_system
        spec, report = compile_project(doc([], [dict(foreign('Emitter_10', 1, (0, 0, 0)), effect=dict(parameters=[dict(name='Spawn', value=3)]))]),
                                       effects_scene(), self.ON, library)
        self.assertEqual(codes(report), [])
        _, native = native_split(stream_only(spec))
        self.assertEqual(native['effects']['copies'][0]['values'], dict(parameters=[dict(name='Spawn', type='PSPT_Scalar', value=3.0)]))
        _, report = compile_project(doc([], [dict(foreign('Emitter_10', 1, (0, 0, 0)), effect=dict(parameters=[dict(name='Opacity', value=3)]))]),
                                    effects_scene(), self.ON, library)
        self.assertEqual(codes(report), ['malformed'])


if __name__ == '__main__':
    unittest.main()
