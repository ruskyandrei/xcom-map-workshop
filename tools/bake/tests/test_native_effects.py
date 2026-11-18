"""Effects in the Build (native_effects.py, native_sounds.py): carried by their piece, the tutorial's Skyranger moved,
copied and deleted with its lights (Emitter_4), on the configured install's Act1_IntroLevel; and the effects' and
sounds' lanes of the effects and sounds plan (stage FX3) on URB_Bar: moves in place, deletes off the level's list,
copies that own what is under them, the floors' effect lists, read back; an effect and a sound of URB_PierA copied
into URB_Bar, staged by transplant.stage_edit first (stage FX4); values set on originals and copies (stage FX5); and
the lens flares' lane (stage FX6b: native_flares.py), Bar's own two and two of AlienBase01's.
Each skipped without its maps."""
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


# ---------------------------------------------------------------- the effects and sounds lanes (plan Part D, FX3)
BAR, NO_BAR = labpaths.install_map('URB_Bar')
FLOOR1 = 'XComBuildingVolume_0'      # its floor 1 lists Emitter_4, _13, _14, _37 and _45 (plan 2.4)


def emitters(q, building):
    """Each floor's m_aCachedEmitters of a building (short names)."""
    rows = q.structs(q.own(q.by_name[PL + building], 'Floors'))
    return [sorted(q.name(r).split('.')[-1] for r in q.refs(row[('m_aCachedEmitters', 0)]['value']))
            if ('m_aCachedEmitters', 0) in row else [] for row in rows]


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Lanes(unittest.TestCase):
    """One build of Bar with the effects' and sounds' lanes (moves, deletes, copies), read back."""
    EFFECTS = dict(
        moves=[dict(name='Emitter_14', location=[-627.0, 1286.0, 50.0], rotation=[0, 0, 0]),     # out of floor 1
               dict(name='Emitter_1', location=[100.0, 500.0, 300.0], rotation=[0, 16384, 0])],  # into floor 1
        deletes=[dict(name='Emitter_45')],
        copies=[dict(id='a', name='Emitter_10_copy1', source='Emitter_10', location=[200.0, 600.0, 250.0], rotation=[0, 0, 0]),
                dict(id='b', name='Emitter_10_copy2', source='Emitter_10', location=[200.0, 600.0, 100.0], rotation=[0, 0, 0]),
                dict(id='c', name='Emitter_10_copy3', source='Emitter_10', location=[200.0, 600.0, 450.0], rotation=[0, 0, 0])])
    SOUNDS = dict(
        moves=[dict(name='AmbientSoundSimple_2', location=[0.0, 640.0, 73.0], rotation=[0, 0, 0])],
        deletes=[dict(name='AmbientSoundSimple_3')],
        copies=[dict(id='d', name='AmbientSoundSimple_0_copy4', source='AmbientSoundSimple_0', location=[-900.0, -550.0, 62.0],
                     rotation=[0, 0, 0]),
                dict(id='e', name='AmbientSoundSimple_0_copy5', source='AmbientSoundSimple_0', location=[-950.0, -550.0, 62.0],
                     rotation=[0, 0, 0])])

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        out = Path(cls.tmp.name) / 'Lanes'
        cls.m = native_copy.build(BAR, out, 'Lanes', [], effects=cls.EFFECTS, sounds=cls.SOUNDS)
        cls.q = Package(out / 'Lanes.upk')
        cls.section = cls.m['nativeCopies']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_moves_in_place(self):
        q, listed = self.q, set(native_copy.level_actors(self.q))
        for m in self.EFFECTS['moves'] + self.SOUNDS['moves']:
            i = q.by_name[PL + m['name']]
            self.assertEqual(i, self.p.by_name[PL + m['name']])         # the same export: what names it still does
            self.assertIn(i, listed)
            self.assertEqual(([round(v, 3) for v in q.own(i, 'Location')], list(q.own(i, 'Rotation', [0, 0, 0]))),
                             (m['location'], m['rotation']))

    def test_deletes_leave_the_list_and_keep_the_export(self):
        listed = set(native_copy.level_actors(self.q))
        for name in ('Emitter_45', 'AmbientSoundSimple_3'):
            self.assertIn(PL + name, self.q.by_name)
            self.assertNotIn(self.q.by_name[PL + name], listed)

    def test_copies_own_what_is_under_them(self):
        listed = set(native_copy.level_actors(self.q))
        rows = {r['actor']: r for r in self.section['effects'] + self.section['sounds'] if r['how'] == 'copied'}
        self.assertEqual(sorted(rows), ['AmbientSoundSimple_0_copy4', 'AmbientSoundSimple_0_copy5', 'Emitter_10_copy1',
                                        'Emitter_10_copy2', 'Emitter_10_copy3'])
        cues = set()
        for name, r in rows.items():
            i = self.q.by_name[PL + r['copy']]
            self.assertIn(i, listed)
            self.assertEqual(self.q.cls(i), self.p.cls(self.p.by_name[PL + r['source']]))
            if r['source'].startswith('AmbientSound'):
                component = self.q.own(i, 'AudioComponent')
                cue = self.q.own(component, 'SoundCue')
                node = self.q.own(i, 'SoundNodeInstance')
                self.assertTrue(self.q.name(cue).startswith(self.q.name(i) + '.'), self.q.name(cue))
                self.assertEqual(self.q.own(cue, 'FirstNode'), node)
                self.assertEqual(self.q.own(i, 'AmbientProperties'), node)
                cues.add(cue)
            else:
                component = self.q.own(i, 'ParticleSystemComponent')
                self.assertTrue(self.q.name(component).startswith(self.q.name(i) + '.'))
                source = self.p.by_name[PL + r['source']]
                self.assertEqual(self.q.own(component, 'Template'),
                                 self.p.own(self.p.own(source, 'ParticleSystemComponent'), 'Template'))
        self.assertEqual(len(cues), 2)      # each copy its own cue

    def test_sources_are_untouched(self):
        for name in ('Emitter_10', 'AmbientSoundSimple_0'):
            for i in native_copy.subtree(self.p, self.p.by_name[PL + name]):
                e, f = self.p.exports[i - 1], self.q.exports[self.q.by_name[self.p.name(i)] - 1]
                self.assertEqual(bytes(self.p.data[e['off']:e['off'] + e['size']]), bytes(self.q.data[f['off']:f['off'] + f['size']]),
                                 self.p.name(i))

    def test_floor_lists(self):
        got = emitters(self.q, FLOOR1)
        before = emitters(self.p, FLOOR1)
        self.assertEqual(before[1], ['Emitter_13', 'Emitter_14', 'Emitter_37', 'Emitter_4', 'Emitter_45'])
        copy = {r['actor']: r['copy'].split('.')[-1] for r in self.section['effects'] if r['how'] == 'copied'}
        # untouched ones keep their listing (Emitter_13, _37, _4 though they stand outside the boxes); the moved-out
        # and the deleted leave; the moved-in and the copy in floor 1's box join; floor 0 never lists
        self.assertEqual(got[0], before[0])
        self.assertEqual(got[1], sorted(['Emitter_13', 'Emitter_37', 'Emitter_4', 'Emitter_1', copy['Emitter_10_copy1']]))
        self.assertEqual(got[2], sorted(before[2] + [copy['Emitter_10_copy3']]))
        rows = {(f['effect'], f['floor'], f['how']) for f in self.section['floorEmitters']}
        self.assertEqual(rows, {('Emitter_14', 1, 'left'), ('Emitter_45', 1, 'left'), ('Emitter_1', 1, 'joined'),
                                (copy['Emitter_10_copy1'], 1, 'joined'), (copy['Emitter_10_copy3'], 2, 'joined')})
        # no other building's lists change
        for b in ('XComBuildingVolume_1', 'XComBuildingVolume_2', 'XComBuildingVolume_8'):
            self.assertEqual(emitters(self.q, b), emitters(self.p, b))

    def test_lane_refusals(self):
        out = Path(self.tmp.name) / 'Refused'
        at = dict(location=[0, 0, 0], rotation=[0, 0, 0])
        for effects, sounds, words in ((dict(moves=[dict(name='AmbientSoundSimple_2', **at)]), None, 'not an effect'),
                                       (dict(deletes=[dict(name='Emitter_999')]), None, 'no actor Emitter_999'),
                                       (dict(moves=[dict(name='Emitter_2', **at)], deletes=[dict(name='Emitter_2')]), None, 'twice'),
                                       (None, dict(copies=[dict(id='x', name='x', source='Emitter_2', **at)]), 'not an ambient sound')):
            with self.assertRaises(ValueError, msg=words) as caught:
                native_copy.build(BAR, out, 'Refused', [], effects=effects, sounds=sounds)
            self.assertIn(words, str(caught.exception))

    def test_a_cleared_map_keeps_the_moved_sound_the_copies_and_the_skyrangers(self):
        # (the user, 18 November 2026: Clear left a cleared Bar's ambient sounds in its play area) the map's own
        # sounds go with the clear, but one the project moved, its copies and the Skyranger's
        out = Path(self.tmp.name) / 'Cleared'
        m = native_copy.build(BAR, out, 'Cleared', [], sounds=dict(moves=self.SOUNDS['moves'], copies=self.SOUNDS['copies'][:1]),
                              cleared=dict(grid=[52, 39, 12]))
        q = Package(out / 'Cleared.upk')
        listed = set(native_copy.level_actors(q))
        self.assertIn(q.by_name[PL + 'AmbientSoundSimple_2'], listed)               # moved by the project: kept
        self.assertIn(q.by_name[PL + 'AmbientSoundSimpleToggleable_0'], listed)     # the Skyranger's
        for name in ('AmbientSoundSimple_0', 'AmbientSoundSimple_1', 'AmbientSoundSimple_3', 'AmbientSoundSimple_4'):
            self.assertNotIn(q.by_name[PL + name], listed)                          # the map's own: out with the clear
        copy, = [r['copy'] for r in m['nativeCopies']['sounds'] if r['how'] == 'copied']
        self.assertIn(q.by_name[PL + copy], listed)


# ---------------------------------------------------------------- values (plan Part D, stage FX5)
def component_bytes(p, actor, prop='ParticleSystemComponent'):
    i = p.own(p.by_name[PL + actor], prop)
    e = p.exports[i - 1]
    return bytes(p.data[e['off']:e['off'] + e['size']])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ValueLanes(unittest.TestCase):
    """One build of Bar with values: on originals in place (an effect's size, starting state and parameters, among
    them a scalar saved where its system's distribution is a vector, a colour and one it didn't save; a simple sound's
    radii, volume, pitch and starting state) and on copies (an effect that saves no parameters at all), read back."""
    EFFECTS = dict(
        values=[dict(name='Emitter_38', effect=dict(scale=2.0, startsOn=False, parameters=[
                    dict(name='Chunk_Brightness', type='PSPT_Scalar', value=3.0),
                    dict(name='Chunk_Color', type='PSPT_Color', value=[1.0, 0.0, 0.0, 1.0]),
                    dict(name='Dust_Desaturation', type='PSPT_Scalar', value=2.0)])),
                # the value it has already: the bytes stay as they were
                dict(name='Emitter_0', effect=dict(parameters=[dict(name='Speed', type='PSPT_Scalar', value=1.0)]))],
        copies=[dict(id='a', name='Emitter_10_copy1', source='Emitter_10', location=[200.0, 600.0, 250.0], rotation=[0, 0, 0],
                     values=dict(scale=0.5, startsOn=False, parameters=[
                         dict(name='Opacity', type='PSPT_Scalar', value=0.25),
                         dict(name='Size', type='PSPT_Vector', value=[2.0, 2.0, 3.0])])),
                dict(id='b', name='Emitter_10_copy2', source='Emitter_10', location=[220.0, 600.0, 250.0], rotation=[0, 0, 0])])
    SOUNDS = dict(
        values=[dict(name='AmbientSoundSimple_2', sound=dict(radiusMin=200.0, radiusMax=1500.0, volume=[0.4, 0.6],
                                                             pitch=[0.9, 1.1], startsOn=False))],
        copies=[dict(id='c', name='AmbientSoundSimple_0_copy3', source='AmbientSoundSimple_0', location=[-900.0, -550.0, 62.0],
                     rotation=[0, 0, 0], values=dict(radiusMax=1200.0)),
                dict(id='d', name='AmbientSoundSimple_0_copy4', source='AmbientSoundSimple_0', location=[-950.0, -550.0, 62.0],
                     rotation=[0, 0, 0])])

    @classmethod
    def setUpClass(cls):
        import native_effects
        cls.fx = native_effects
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        out = Path(cls.tmp.name) / 'Values'
        cls.m = native_copy.build(BAR, out, 'Values', [], effects=cls.EFFECTS, sounds=cls.SOUNDS)
        cls.q = Package(out / 'Values.upk')
        cls.section = cls.m['nativeCopies']
        cls.copy = {r['actor']: cls.q.by_name[PL + r['copy']] for r in cls.section['effects'] + cls.section['sounds']
                    if r['how'] == 'copied'}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def params(self, p, i):
        raw = p.own(p.own(i, 'ParticleSystemComponent'), 'InstanceParameters')
        return [{k[0]: v['value'] for k, v in row.items() if k[1] == 0} for row in p.structs(raw)] if raw else []

    def test_an_effects_values_in_place(self):
        q, i = self.q, self.q.by_name[PL + 'Emitter_38']
        got = self.fx.read_values(q, i, 'effect')
        self.assertEqual((got['drawScale'], got['startsOn']), (2.0, False))
        prm = got['parameters']
        self.assertEqual((prm['Chunk_Brightness']['type'], prm['Chunk_Brightness']['scalar']), ('PSPT_Scalar', 3.0))
        self.assertEqual((prm['Chunk_Color']['type'], prm['Chunk_Color']['colour']), ('PSPT_Color', [1.0, 0.0, 0.0, 1.0]))
        self.assertEqual((prm['Dust_Desaturation']['type'], prm['Dust_Desaturation']['scalar']), ('PSPT_Scalar', 2.0))
        # the others, their order and their fields as they were; the new one last
        before, after = self.params(self.p, self.p.by_name[PL + 'Emitter_38']), self.params(q, i)
        self.assertEqual([r['Name'] for r in after], [r['Name'] for r in before] + ['Dust_Desaturation'])
        for b, a in zip(before, after):
            if b['Name'] not in ('Chunk_Brightness', 'Chunk_Color'):
                self.assertEqual(a, b)
        self.assertEqual(after[0]['Vector'], before[0]['Vector'])          # Chunk_Color's other field kept
        # the same export: what names it still does
        self.assertEqual(i, self.p.by_name[PL + 'Emitter_38'])

    def test_an_unchanged_value_keeps_the_bytes(self):
        self.assertEqual(component_bytes(self.q, 'Emitter_0'), component_bytes(self.p, 'Emitter_0'))

    def test_a_copys_values_are_on_the_copy_alone(self):
        q = self.q
        got = self.fx.read_values(q, self.copy['Emitter_10_copy1'], 'effect')
        self.assertEqual((got['drawScale'], got['startsOn']), (0.5, False))
        self.assertEqual((got['parameters']['Opacity']['scalar'], got['parameters']['Size']['vector']), (0.25, [2.0, 2.0, 3.0]))
        # the other copy and the source as the map has them (the source saved no parameters at all)
        other = self.fx.read_values(q, self.copy['Emitter_10_copy2'], 'effect')
        self.assertEqual((other['drawScale'], other['parameters']), (1.0, {}))
        for name in ('Emitter_10', 'AmbientSoundSimple_0'):
            for j in native_copy.subtree(self.p, self.p.by_name[PL + name]):
                e, f = self.p.exports[j - 1], q.exports[q.by_name[self.p.name(j)] - 1]
                self.assertEqual(bytes(self.p.data[e['off']:e['off'] + e['size']]), bytes(q.data[f['off']:f['off'] + f['size']]),
                                 self.p.name(j))

    def test_a_sounds_values(self):
        q = self.q
        got = self.fx.read_values(q, q.by_name[PL + 'AmbientSoundSimple_2'], 'sound')
        self.assertEqual(got, dict(startsOn=False, radiusMin=200.0, radiusMax=1500.0, volume=[0.4000000059604645, 0.6000000238418579],
                                   pitch=[0.8999999761581421, 1.100000023841858]))
        # a copy's one value on its own node; what it didn't set as its source has it
        mine = self.fx.read_values(q, self.copy['AmbientSoundSimple_0_copy3'], 'sound')
        self.assertEqual((mine['radiusMin'], mine['radiusMax']), (300.0, 1200.0))
        other = self.fx.read_values(q, self.copy['AmbientSoundSimple_0_copy4'], 'sound')
        self.assertEqual((other['radiusMin'], other['radiusMax']), (300.0, 750.0))

    def test_export_28_reads_the_values(self):
        import effects_metadata
        import piece_flags
        scripts = piece_flags.ScriptDefaults.of(Path(BAR).parent)
        read = effects_metadata.describe(self.q, defaults=effects_metadata.Defaults(self.q, scripts))
        by = {r['actor'].rsplit('.', 1)[-1]: r for r in read['effects'] + read['sounds']}
        fx = by['Emitter_38']
        self.assertEqual((fx['drawScale'], fx['startsOn'], fx['startsOnFrom']), (2.0, False, 'actor'))
        self.assertEqual([(x['name'], x['offered']) for x in fx['parameters'] if x['name'] in ('Chunk_Brightness', 'Dust_Desaturation')],
                         [('Chunk_Brightness', 'otherKind'), ('Dust_Desaturation', 'yes')])
        sound = by['AmbientSoundSimple_2']
        self.assertEqual((sound['startsOn'], sound['startsOnFrom']), (False, 'actor'))
        self.assertEqual((sound['values']['radiusMin'], sound['values']['radiusMax']), (200.0, 1500.0))
        copy = by[self.q.name(self.copy['Emitter_10_copy1']).rsplit('.', 1)[-1]]
        self.assertEqual([(x['name'], x['type'], x['offered']) for x in copy['parameters']],
                         [('Opacity', 'PSPT_Scalar', 'yes'), ('Size', 'PSPT_Vector', 'yes')])

    def test_the_record_says_what_was_written(self):
        rows = {r['actor']: r for r in self.section['effects'] + self.section['sounds']}
        self.assertEqual(rows['Emitter_38']['how'], 'valued')
        self.assertEqual(rows['Emitter_38']['values']['drawScale'], 2.0)
        self.assertEqual(rows['AmbientSoundSimple_0_copy3']['values'], dict(radiusMax=1200.0))
        self.assertNotIn('values', rows['AmbientSoundSimple_0_copy4'])

    def test_value_refusals(self):
        out = Path(self.tmp.name) / 'Refused'
        bad = [(dict(values=[dict(name='Emitter_38', effect=dict(parameters=[dict(name='Chunk_Color', type='PSPT_Scalar', value=1.0)]))]),
                None, 'saved as PSPT_Color'),
               (dict(values=[dict(name='Emitter_38', effect=dict(parameters=[dict(name='X', type='PSPT_ScalarRand', value=1.0)]))]),
                None, 'not written'),
               (dict(values=[dict(name='Emitter_45', effect=dict(scale=2.0))], deletes=[dict(name='Emitter_45')]), None, 'deleted')]
        for effects, sounds, words in bad:
            with self.assertRaises(ValueError, msg=words) as caught:
                native_copy.build(BAR, out, 'Refused', [], effects=effects, sounds=sounds)
            self.assertIn(words, str(caught.exception))


# ---------------------------------------------------------------- another map's effects and sounds (plan Part D, FX4)
PIER, NO_PIER = labpaths.install_map('URB_PierA')


@unittest.skipUnless(BAR and BAR.exists() and PIER and PIER.exists(), NO_BAR or NO_PIER)
class ForeignLanes(unittest.TestCase):
    """The 17 November offline trial made a test (plan 2.7): URB_PierA's lit sea foam (Emitter_10) and air conditioner
    (AmbientSoundSimple_1), which URB_Bar lacks, staged in Bar by transplant.stage_edit and cloned by the lanes; two
    copies of the effect from the one staged actor."""
    FOAM, AIR = 'Emitter_10', 'AmbientSoundSimple_1'

    @classmethod
    def setUpClass(cls):
        import transplant
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        donor = dict(package='URB_PierA', sha256=transplant.sha256(PIER))
        at = lambda x, y, z: dict(location=[x, y, z], rotation=[0, 0, 0])
        cls.edit = dict(copies=[], effects=dict(moves=[], deletes=[], copies=[
            dict(id='a', name='Emitter_10_copy1', source=cls.FOAM, actorClass='Emitter', donor=donor, **at(200.0, -600.0, 2.0)),
            dict(id='b', name='Emitter_10_copy2', source=cls.FOAM, actorClass='Emitter', donor=donor, **at(400.0, -600.0, 2.0))]),
            sounds=dict(moves=[], deletes=[], copies=[
                dict(id='c', name='AmbientSoundSimple_1_copy3', source=cls.AIR, actorClass='AmbientSoundSimple', donor=donor,
                     **at(-300.0, -1000.0, 60.0))]))
        cls.staged, cls.new_edit, cls.report = transplant.stage_edit(BAR, out / 'transplant', cls.edit)
        cls.m = native_copy.build(cls.staged, out / 'build', 'Foreign', cls.new_edit['copies'],
                                  effects=cls.new_edit['effects'], sounds=cls.new_edit['sounds'])
        cls.q = Package(out / 'build' / 'Foreign.upk')
        cls.pier = Package(PIER)
        cls.section = cls.m['nativeCopies']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_donor_actor_is_staged_once_and_the_lanes_name_it(self):
        row, = self.report['donors']
        self.assertEqual((row['map'], row['pieces'], row['effects'], row['cut']), ('URB_PierA', 0, 2, []))
        self.assertEqual(self.report['foreignPieces'], 2)
        foam, again = self.new_edit['effects']['copies']
        air, = self.new_edit['sounds']['copies']
        self.assertEqual(foam['source'], row['staged'][self.FOAM])
        self.assertEqual(again['source'], foam['source'])
        self.assertEqual(air['source'], row['staged'][self.AIR])
        self.assertTrue(foam['staged'] and again['staged'] and air['staged'])
        self.assertEqual((foam['donor']['actor'], air['donor']['actor']), (self.FOAM, self.AIR))
        self.assertEqual(self.edit['effects']['copies'][0]['source'], self.FOAM)    # the edit given is not changed

    def test_the_clones_are_listed_and_the_staged_actors_not(self):
        q, listed = self.q, set(native_copy.level_actors(self.q))
        for name in (self.new_edit['effects']['copies'][0]['source'], self.new_edit['sounds']['copies'][0]['source']):
            self.assertNotIn(q.by_name[PL + name], listed)
        rows = {r['actor']: r for r in self.section['effects'] + self.section['sounds']}
        self.assertEqual(sorted(rows), ['AmbientSoundSimple_1_copy3', 'Emitter_10_copy1', 'Emitter_10_copy2'])
        foam = self.pier.own(self.pier.by_name[PL + self.FOAM], 'ParticleSystemComponent')
        for name in ('Emitter_10_copy1', 'Emitter_10_copy2'):
            i = q.by_name[PL + rows[name]['copy']]
            self.assertIn(i, listed)
            component = q.own(i, 'ParticleSystemComponent')
            self.assertTrue(q.name(component).startswith(q.name(i) + '.'))
            self.assertEqual(q.name(q.own(component, 'Template')), self.pier.name(self.pier.own(foam, 'Template')))
            self.assertGreater(q.own(i, 'LightEnvironment', 0), 0)               # lit: a light environment of its own
            self.assertTrue(q.name(q.own(i, 'LightEnvironment')).startswith(q.name(i) + '.'))
        sound = q.by_name[PL + rows['AmbientSoundSimple_1_copy3']['copy']]
        self.assertIn(sound, listed)
        cue = q.own(q.own(sound, 'AudioComponent'), 'SoundCue')
        self.assertTrue(q.name(cue).startswith(q.name(sound) + '.'))
        self.assertEqual(q.own(cue, 'FirstNode'), q.own(sound, 'SoundNodeInstance'))

    def test_export_28_reads_them_as_the_donor_has_them(self):
        import effects_metadata
        import piece_flags
        # (read with the install's script packages, as an export of the map in the install is)
        scripts = piece_flags.ScriptDefaults.of(Path(PIER).parent)
        mine = effects_metadata.describe(self.q, defaults=effects_metadata.Defaults(self.q, scripts))
        theirs = effects_metadata.describe(self.pier)
        copies = {r['actor'].rsplit('.', 1)[-1]: r for r in mine['effects'] + mine['sounds']}
        rows = {r['actor']: r['copy'].rsplit('.', 1)[-1] for r in self.section['effects'] + self.section['sounds']}
        home = {r['actor'].rsplit('.', 1)[-1]: r for r in theirs['effects'] + theirs['sounds']}
        for name, source in (('Emitter_10_copy1', self.FOAM), ('Emitter_10_copy2', self.FOAM),
                             ('AmbientSoundSimple_1_copy3', self.AIR)):
            r, h = copies[rows[name]], home[source]
            self.assertTrue(r['listed'])
            if r['kind'] == 'effect':
                self.assertEqual((r['template'], r['lit'], r['parameters']), (h['template'], h['lit'], h['parameters']))
                # (the fingerprint hashes the bytes, whose object indices the bring renumbers: what it says is compared)
                said = ('objects', 'lodLevels', 'emitters', 'offers', 'fixedBox')
                self.assertEqual({k: mine['systems'][r['system']][k] for k in said},
                                 {k: theirs['systems'][h['system']][k] for k in said})
            else:
                self.assertEqual([w.split('|')[1] for w in r['waves']], [w.split('|')[1] for w in h['waves']])
                self.assertTrue(all(mine['waves'][w]['playable'] for w in r['waves']))
                self.assertEqual(r['values'], h['values'])

    def test_a_staged_source_must_be_staged_and_unlisted(self):
        import native_effects
        q, listed = self.q, set(native_copy.level_actors(self.q))
        staged = self.new_edit['effects']['copies'][0]['source']
        with self.assertRaises(ValueError) as caught:
            native_effects.lane_actor(q, staged, ('Emitter',), listed, 'an effect')
        self.assertIn('not in the level', str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            native_effects.lane_actor(q, 'Emitter_2', ('Emitter',), listed, 'an effect', staged=True)
        self.assertIn('staged from another map', str(caught.exception))


# ---------------------------------------------------------------- lens flares (plan Part D, stage FX6b)
BASE, NO_BASE = labpaths.install_map('AlienBase01')


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class FlareLanes(unittest.TestCase):
    """One build of Bar with the flares' lane: its two lens flares (made from an archetype, which names their
    template) moved, deleted and copied, read back; and what a cleared map keeps of them."""
    FLARES = dict(
        moves=[dict(name='LensFlareSource_7', location=[900.0, -220.0, 300.0], rotation=[0, 8192, 0])],
        deletes=[dict(name='LensFlareSource_8')],
        copies=[dict(id='a', name='LensFlareSource_7_copy1', source='LensFlareSource_7', location=[0.0, 640.0, 200.0],
                     rotation=[0, 0, 0]),
                dict(id='b', name='LensFlareSource_8_copy2', source='LensFlareSource_8', location=[96.0, 640.0, 200.0],
                     rotation=[0, 16384, 0])])

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        out = Path(cls.tmp.name) / 'Flares'
        cls.m = native_copy.build(BAR, out, 'Flares', [], flares=cls.FLARES)
        cls.q = Package(out / 'Flares.upk')
        cls.section = cls.m['nativeCopies']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_flare_is_an_actor_and_its_component(self):
        p, i = self.p, self.p.by_name[PL + 'LensFlareSource_7']
        tree = native_copy.subtree(p, i)
        self.assertEqual(sorted(p.cls(j) for j in tree), ['LensFlareComponent', 'LensFlareSource'])
        self.assertEqual(p.cls(p.effective(p.own(i, 'LensFlareComp'), 'Template')), 'LensFlare')

    def test_the_move_is_in_place(self):
        q, m = self.q, self.FLARES['moves'][0]
        i = q.by_name[PL + m['name']]
        self.assertEqual(i, self.p.by_name[PL + m['name']])
        self.assertIn(i, native_copy.level_actors(q))
        self.assertEqual(([round(v, 3) for v in q.own(i, 'Location')], list(q.own(i, 'Rotation', [0, 0, 0]))),
                         (m['location'], m['rotation']))

    def test_the_delete_leaves_the_list_and_keeps_the_export(self):
        self.assertIn(PL + 'LensFlareSource_8', self.q.by_name)
        self.assertNotIn(self.q.by_name[PL + 'LensFlareSource_8'], native_copy.level_actors(self.q))

    def test_a_copy_has_a_component_of_its_own_and_shares_the_template(self):
        q, listed = self.q, set(native_copy.level_actors(self.q))
        rows = {r['actor']: r for r in self.section['flares'] if r['how'] == 'copied'}
        self.assertEqual(sorted(rows), ['LensFlareSource_7_copy1', 'LensFlareSource_8_copy2'])
        components = set()
        for name, r in rows.items():
            i = q.by_name[PL + r['copy']]
            source = self.p.by_name[PL + r['source']]
            self.assertIn(i, listed)
            self.assertEqual(q.cls(i), 'LensFlareSource')
            self.assertEqual(len(r['exports']), 2)                  # the actor and its component, nothing else
            component = q.own(i, 'LensFlareComp')
            self.assertTrue(q.name(component).startswith(q.name(i) + '.'), q.name(component))
            self.assertNotEqual(component, self.p.own(source, 'LensFlareComp'))
            components.add(component)
            # the template (its archetype's) and the colour as the source has them
            theirs = self.p.own(source, 'LensFlareComp')
            self.assertEqual(q.name(q.effective(component, 'Template')), self.p.name(self.p.effective(theirs, 'Template')))
            self.assertEqual(q.own(component, 'SourceColor'), self.p.own(theirs, 'SourceColor'))
            self.assertEqual(q.exports[i - 1]['arch'], self.p.exports[source - 1]['arch'])
            self.assertEqual([round(v, 3) for v in q.own(i, 'Location')], r['location'])
        self.assertEqual(len(components), 2)
        self.assertEqual(list(q.own(q.by_name[PL + rows['LensFlareSource_8_copy2']['copy']], 'Rotation')), [0, 16384, 0])

    def test_the_sources_are_untouched_but_for_the_move(self):
        for name in ('LensFlareSource_8', 'LensFlareSource_7.LensFlareComponent_7'):
            i = self.p.by_name[PL + name]
            e, f = self.p.exports[i - 1], self.q.exports[self.q.by_name[PL + name] - 1]
            self.assertEqual(bytes(self.p.data[e['off']:e['off'] + e['size']]), bytes(self.q.data[f['off']:f['off'] + f['size']]))

    def test_export_28_reads_them(self):
        import effects_metadata
        import piece_flags
        scripts = piece_flags.ScriptDefaults.of(Path(BAR).parent)
        read = effects_metadata.describe(self.q, defaults=effects_metadata.Defaults(self.q, scripts))
        by = {r['actor'].rsplit('.', 1)[-1]: r for r in read['flares']}
        copies = {r['actor']: r['copy'] for r in self.section['flares'] if r['how'] == 'copied'}
        self.assertEqual(by['LensFlareSource_7']['location'], [900.0, -220.0, 300.0])
        self.assertFalse(by['LensFlareSource_8']['listed'])
        for name in copies.values():
            r = by[name]
            self.assertTrue(r['listed'])
            self.assertEqual((r['template'], r['colour'], r['can']['copy']),
                             ('FX_Lens_Flares.LF_XCom_Base_C', by['LensFlareSource_7']['colour'], True))

    def test_lane_refusals(self):
        out = Path(self.tmp.name) / 'Refused'
        at = dict(location=[0, 0, 0], rotation=[0, 0, 0])
        for flares, words in ((dict(moves=[dict(name='Emitter_2', **at)]), 'not a lens flare'),
                              (dict(deletes=[dict(name='LensFlareSource_99')]), 'no actor LensFlareSource_99'),
                              (dict(copies=[dict(id='x', name='x', source='LensFlareSource_7', values=dict(scale=2.0), **at)]),
                               'no values to set'),
                              (dict(values=[dict(name='LensFlareSource_7', flare=dict(colour=[1, 0, 0, 1]))]),
                               'no values to set')):
            with self.assertRaises(ValueError, msg=words) as caught:
                native_copy.build(BAR, out, 'Refused', [], flares=flares)
            self.assertIn(words, str(caught.exception))

    def test_a_cleared_map_keeps_the_moved_one_and_the_copies(self):
        out = Path(self.tmp.name) / 'Cleared'
        flares = dict(moves=self.FLARES['moves'], copies=self.FLARES['copies'][:1])
        m = native_copy.build(BAR, out, 'Cleared', [], flares=flares, cleared=dict(grid=[52, 39, 12]))
        q = Package(out / 'Cleared.upk')
        listed = set(native_copy.level_actors(q))
        self.assertIn(q.by_name[PL + 'LensFlareSource_7'], listed)             # moved by the project: kept
        self.assertNotIn(q.by_name[PL + 'LensFlareSource_8'], listed)          # the map's own: out with the clear
        copy, = [r['copy'] for r in m['nativeCopies']['flares'] if r['how'] == 'copied']
        self.assertIn(q.by_name[PL + copy], listed)


@unittest.skipUnless(BAR and BAR.exists() and BASE and BASE.exists(), NO_BAR or NO_BASE)
class ForeignFlares(unittest.TestCase):
    """A lens flare of another map: AlienBase01's hyperwave beacon glare (LensFlareSource_0, which saves its template
    itself) and an alien ambient glow (LensFlareSource_1), neither of which URB_Bar has, staged in Bar by
    transplant.stage_edit and cloned by the flares' lane; two copies of the one staged actor."""
    BEACON, GLOW = 'LensFlareSource_0', 'LensFlareSource_1'

    @classmethod
    def setUpClass(cls):
        import transplant
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        donor = dict(package='AlienBase01', sha256=transplant.sha256(BASE))
        at = lambda x, y, z: dict(location=[x, y, z], rotation=[0, 0, 0])
        cls.edit = dict(copies=[], flares=dict(moves=[], deletes=[], copies=[
            dict(id='a', name='LensFlareSource_0_copy1', source=cls.BEACON, actorClass='LensFlareSource', donor=donor, **at(0.0, 640.0, 200.0)),
            dict(id='b', name='LensFlareSource_0_copy2', source=cls.BEACON, actorClass='LensFlareSource', donor=donor, **at(96.0, 640.0, 200.0)),
            dict(id='c', name='LensFlareSource_1_copy3', source=cls.GLOW, actorClass='LensFlareSource', donor=donor, **at(192.0, 640.0, 200.0))]))
        cls.staged, cls.new_edit, cls.report = transplant.stage_edit(BAR, out / 'transplant', cls.edit)
        cls.m = native_copy.build(cls.staged, out / 'build', 'ForeignFlares', cls.new_edit['copies'],
                                  flares=cls.new_edit['flares'])
        cls.q = Package(out / 'build' / 'ForeignFlares.upk')
        cls.base = Package(BASE)
        cls.section = cls.m['nativeCopies']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_is_staged_once_and_nothing_is_cut(self):
        row, = self.report['donors']
        self.assertEqual((row['map'], row['pieces'], row['effects'], row['cut']), ('AlienBase01', 0, 2, []))
        beacon, again, glow = self.new_edit['flares']['copies']
        self.assertEqual((beacon['source'], again['source'], glow['source']),
                         (row['staged'][self.BEACON], row['staged'][self.BEACON], row['staged'][self.GLOW]))
        self.assertTrue(beacon['staged'] and again['staged'] and glow['staged'])

    def test_the_clones_are_listed_with_their_templates_and_the_staged_actors_not(self):
        q, listed = self.q, set(native_copy.level_actors(self.q))
        for c in self.new_edit['flares']['copies']:
            self.assertNotIn(q.by_name[PL + c['source']], listed)
        rows = {r['actor']: r for r in self.section['flares']}
        self.assertEqual(sorted(rows), ['LensFlareSource_0_copy1', 'LensFlareSource_0_copy2', 'LensFlareSource_1_copy3'])
        for name, source in (('LensFlareSource_0_copy1', self.BEACON), ('LensFlareSource_0_copy2', self.BEACON),
                             ('LensFlareSource_1_copy3', self.GLOW)):
            i = q.by_name[PL + rows[name]['copy']]
            self.assertIn(i, listed)
            component = q.own(i, 'LensFlareComp')
            self.assertTrue(q.name(component).startswith(q.name(i) + '.'))
            theirs = self.base.own(self.base.by_name[PL + source], 'LensFlareComp')
            template = q.own(component, 'Template')
            self.assertEqual(q.name(template), self.base.name(self.base.own(theirs, 'Template')))
            self.assertEqual(q.cls(template), 'LensFlare')
            self.assertEqual(q.own(component, 'SourceColor'), self.base.own(theirs, 'SourceColor'))

    def test_export_28_reads_them_as_the_donor_has_them(self):
        import effects_metadata
        mine = {r['actor'].rsplit('.', 1)[-1]: r for r in effects_metadata.describe(self.q)['flares']}
        home = {r['actor'].rsplit('.', 1)[-1]: r for r in effects_metadata.describe(self.base)['flares']}
        rows = {r['actor']: r['copy'].rsplit('.', 1)[-1] for r in self.section['flares']}
        for name, source in (('LensFlareSource_0_copy1', self.BEACON), ('LensFlareSource_1_copy3', self.GLOW)):
            r, h = mine[rows[name]], home[source]
            self.assertTrue(r['listed'])
            self.assertEqual((r['template'], r['colour'], r['can']), (h['template'], h['colour'], h['can']))


if __name__ == '__main__':
    unittest.main()
