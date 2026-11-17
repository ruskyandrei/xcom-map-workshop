"""Effects in the Build (native_effects.py, native_sounds.py): carried by their piece, the tutorial's Skyranger moved,
copied and deleted with its lights (Emitter_4), on the configured install's Act1_IntroLevel; and the effects' and
sounds' lanes of the effects and sounds plan (stage FX3) on URB_Bar: moves in place, deletes off the level's list,
copies that own what is under them, the floors' effect lists, read back; and an effect and a sound of URB_PierA copied
into URB_Bar, staged by transplant.stage_edit first (stage FX4). Each skipped without its maps."""
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


if __name__ == '__main__':
    unittest.main()
