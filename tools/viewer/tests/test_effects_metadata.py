"""Effects, sounds and flares in the export (export 28; tools/viewer/effects_metadata.py; the effects and sounds
plan, Part A, stage FX1). The first tests run on made-up objects: where a value comes from, a wave's bulk records,
saved particle parameters against what a system offers, and what may be done with an actor. The install tests pin
the plan's fixture list (section 7.1) to actors of the configured install."""
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import effects_metadata as em  # noqa: E402
from package import Reader  # noqa: E402


class Fake:
    """Just enough of a Package for Defaults and wave_record: exports with (class, archetype, properties)."""
    def __init__(self, objects, imports=(), data=b'', stem='Fake'):
        # objects: [(path, class, arch, {key: value})]; imports: [path] (index -1, -2, ...)
        self.objects, self.imports, self.data = objects, list(imports), data
        self.exports = [dict(arch=arch, off=0, size=len(data), outer=0) for _, _, arch, _ in objects]
        self.by_name = {path: i for i, (path, _, _, _) in enumerate(objects, 1)}
        self.path = Path(stem + '.upk')
        self.ends = {}

    def name(self, i):
        return self.objects[i - 1][0] if i > 0 else self.imports[-i - 1]

    def cls(self, i):
        return self.objects[i - 1][1]

    def properties(self, i):
        props = {(k, 0): dict(kind='FloatProperty', subtype=None, value=v) for k, v in self.objects[i - 1][3].items()}
        return props, self.ends.get(i, 0)

    def own(self, i, key, default=None):
        return self.objects[i - 1][3].get(key, default)


def scripts():
    """Made-up script packages: Engine with a class default chain and a class default's subobject."""
    engine = Fake([
        ('Default__Actor', 'Actor', -1, {'DrawScale': 1.0}),
        ('Default__Emitter', 'Emitter', 1, {}),
        ('Default__Emitter.ParticleSystemComponent0', 'ParticleSystemComponent', 0, {}),
        ('Default__ParticleSystemComponent', 'ParticleSystemComponent', 5, {'bAutoActivate': True}),
        ('Default__PrimitiveComponent', 'PrimitiveComponent', 0, {'Scale': 1.0}),
    ], imports=['Core.Default__Object'])
    core = Fake([('Default__Object', 'Object', 0, {})])
    return {'Engine': engine, 'Core': core, 'XComGame': Fake([])}


class WhereValuesComeFrom(unittest.TestCase):
    def map(self):
        # 1 an Emitter placed with no archetype; 2 its component, archetype the class default's subobject (import -1);
        # 3 a prefab archetype in the map; 4 a component placed from it; 5 a component whose archetype is in a
        # package the map doesn't hold (import -2)
        return Fake([
            ('TheWorld.PersistentLevel.Emitter_0', 'Emitter', 0, {'Location': [1, 2, 3]}),
            ('TheWorld.PersistentLevel.Emitter_0.ParticleSystemComponent_0', 'ParticleSystemComponent', -1, {}),
            ('Pkg.Prefabs.Arc0.Comp', 'ParticleSystemComponent', -1, {'bAutoActivate': False}),
            ('TheWorld.PersistentLevel.Emitter_1.ParticleSystemComponent_0', 'ParticleSystemComponent', 3, {}),
            ('TheWorld.PersistentLevel.Emitter_2.ParticleSystemComponent_0', 'ParticleSystemComponent', -2, {}),
        ], imports=['Engine.Default__Emitter.ParticleSystemComponent0', 'OtherPkg.Prefabs.Arc0.Comp'])

    def test_own_archetype_class_and_unresolved(self):
        d = em.Defaults(self.map(), scripts())
        self.assertEqual(d.value(1, 'Location'), ([1, 2, 3], 'actor'))
        # a class default's subobject saves nothing: its own class's default
        self.assertEqual(d.value(2, 'bAutoActivate', False), (True, 'class'))
        self.assertEqual(d.value(3, 'bAutoActivate', False), (False, 'actor'))
        self.assertEqual(d.value(4, 'bAutoActivate', False), (False, 'archetype'))
        self.assertEqual(d.value(5, 'bAutoActivate', False), (None, 'unresolved'))
        # a placed actor saves no archetype: its class's default, up the chain to the top
        self.assertEqual(d.value(1, 'DrawScale', 0.0), (1.0, 'class'))
        self.assertEqual(d.value(1, 'bHidden', False), (False, 'class'))      # nothing saves it: the type's zero

    def test_the_table_where_the_script_packages_are_missing(self):
        d = em.Defaults(self.map(), {})
        self.assertIsNone(d.scripts)
        self.assertEqual(d.value(2, 'bAutoActivate', False), (True, 'table'))
        self.assertEqual(d.value(1, 'DrawScale', 0.0), (None, 'unresolved'))  # no table for Emitter
        self.assertEqual(d.value(0, 'Location'), (None, 'unresolved'))


def wave(records, props_end=8):
    """A made-up SoundNodeWave export: `props_end` bytes of properties, then bulk records [(flags, count, payload)]."""
    data = bytearray(b'\0' * props_end)
    for flags, count, payload in records:
        at = len(data) + 16
        data += struct.pack('<IiiI', flags, count, len(payload), at) + payload
    p = Fake([('Sounds.Hum', 'SoundNodeWave', 0, {'Duration': 2.0, 'NumChannels': 1, 'SampleRate': 44100})],
             data=bytes(data), stem='URB_Test')
    p.ends[1] = props_end
    return p


class Waves(unittest.TestCase):
    OGG = b'OggS' + b'\0' * 60

    def test_the_pc_record_in_the_export(self):
        r = em.wave_record(wave([(0, 0, b''), (0, len(self.OGG), self.OGG), (0, 0, b''), (0, 0, b''), (0, 0, b'')]), 1)
        self.assertTrue(r['playable'])
        self.assertEqual((r['ogg'], r['seconds'], r['channels'], r['rate'], r['name']), (64, 2.0, 1, 44100, 'Hum'))
        self.assertIsNone(r['why'])

    def test_what_is_not_played(self):
        cases = [([(0, 0, b''), (0, 10, self.OGG)], 'compressed'),
                 ([(0, 0, b''), (0, 64, b'RIFF' + b'\0' * 60)], 'not an Ogg stream'),
                 ([(0, 0, b'')], 'no PC sound data'),
                 ([(0, 0, b''), (0, 0, b'')], 'no PC sound data')]
        for records, words in cases:
            r = em.wave_record(wave(records), 1)
            self.assertFalse(r['playable'], words)
            self.assertIn(words, r['why'])
        # stored outside the map (flag 1: the payload is elsewhere)
        p = wave([(0, 0, b'')])
        p.data += struct.pack('<IiiI', 1, 64, 64, 0)
        p.exports[0]['size'] = len(p.data)
        self.assertIn('outside the map', em.wave_record(p, 1)['why'])
        # an offset that isn't the payload's own place
        p = wave([(0, 0, b''), (0, 64, self.OGG)])
        data = bytearray(p.data)
        struct.pack_into('<I', data, 8 + 16 + 12, 5)
        p.data = bytes(data)
        self.assertIn('not where its header says', em.wave_record(p, 1)['why'])


class Parameters(unittest.TestCase):
    def test_saved_values_against_the_offers(self):
        class P:
            def structs(self, raw):
                return raw

            def name(self, i):
                return 'Pkg.Thing'
        rows = [{('Name', 0): dict(value='Color'), ('ParamType', 0): dict(value='PSPT_Vector'), ('Vector', 0): dict(value=[1, 0.5, 0])},
                {('Name', 0): dict(value='Brightness'), ('ParamType', 0): dict(value='PSPT_Scalar'), ('Scalar', 0): dict(value=0.5)},
                {('Name', 0): dict(value='Wind'), ('ParamType', 0): dict(value=2), ('Scalar', 0): dict(value=1.0),
                 ('Scalar_Low', 0): dict(value=0.5)},
                {('Name', 0): dict(value='None')}]
        offers = [dict(name='Color', kind='vector'), dict(name='Brightness', kind='vector')]
        got = em.parameters(P(), rows, offers)
        self.assertEqual([(r['name'], r['type'], r['offered']) for r in got],
                         [('Color', 'PSPT_Vector', 'yes'), ('Brightness', 'PSPT_Scalar', 'otherKind'),
                          ('Wind', 'PSPT_ScalarRand', 'no'), (None, 'PSPT_None', 'no')])
        self.assertEqual((got[0]['vector'], got[2]['scalar'], got[2]['scalarLow']), ([1, 0.5, 0], 1.0, 0.5))
        self.assertEqual({r['offered'] for r in em.parameters(P(), rows, None)}, {'unknown'})


class Capabilities(unittest.TestCase):
    CAPS = dict(move=None, copy='it plays no particle system', delete=None, values=None)

    def test_reasons(self):
        r = em.capabilities(dict(listed=True, attachedTo=None, stream=None), dict(self.CAPS))
        self.assertEqual(r['can'], dict(move=True, copy=False, delete=True, values=True))
        self.assertEqual(r['why'], dict(copy='it plays no particle system'))
        for record, words in ((dict(listed=True, stream='URB_Bar_Stream'), 'belongs to the stream URB_Bar_Stream'),
                              (dict(listed=False), 'isn\'t in the level\'s actor list'),
                              (dict(listed=True, attachedTo=dict(actor='TheWorld.PersistentLevel.XComUniverseCenter_0')),
                               'rides on XComUniverseCenter_0')):
            r = em.capabilities(record, dict(self.CAPS))
            self.assertFalse(any(r['can'].values()), words)
            self.assertTrue(all(words in v for v in r['why'].values()), r['why'])

    def test_no_untried_words(self):
        # the editor never says a thing is untried (the user's rule of 16 November 2026)
        source = (HERE.parent / 'effects_metadata.py').read_text(encoding='utf-8').casefold()
        for word in ('untried', 'not played', 'not been tried', 'experimental', 'not yet'):
            self.assertNotIn(word, source)

    def test_the_script_packages_are_piece_flags(self):
        import piece_flags
        self.assertEqual(em.SCRIPT_PACKAGES, piece_flags.SCRIPT_PACKAGES)

    def test_struct_helpers(self):
        self.assertEqual(em.box(struct.pack('<6fB', -1, -2, -3, 1, 2, 3, 1)), dict(min=[-1, -2, -3], max=[1, 2, 3], valid=True))
        self.assertIsNone(em.box(b'\0' * 24))
        self.assertEqual(em.floats(struct.pack('<i3f', 3, 1, 2, 3)), [1, 2, 3])
        self.assertEqual(em.floats(struct.pack('<i2f', 3, 1, 2)), [])
        self.assertEqual(em.floats(None), [])


# ---------------------------------------------------------------- the configured install

INSTALL, WHY = None, 'no install configured'
try:
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    sys.path.insert(0, str(HERE.parents[1] / 'upk'))
    import labpaths  # noqa: E402
    INSTALL, WHY = labpaths.install_map('URB_Bar')
except Exception as error:      # noqa: BLE001
    WHY = str(error)
PL = 'TheWorld.PersistentLevel.'
_CACHE = {}


def records(name, stream=None):
    """effects_metadata.describe on a package of the configured install, as the export calls it."""
    if (name, stream) not in _CACHE:
        import scene_metadata
        from package import Package
        p = Package(INSTALL.parent / (name + '.upk'))
        landings = [] if stream else scene_metadata.landing_metadata(p)
        carried = {} if stream else {e['actor']: dict(by=e['carriedBy'], how=e['carriedHow'])
                                     for e in scene_metadata.effect_metadata(p) if e['carriedBy']}
        out = em.describe(p, landings=landings, carried=carried, prefix=('stream-%s-' % stream) if stream else '',
                          layer='stream' if stream else 'base', stream=stream)
        out['by'] = {r['actor'].rsplit('.', 1)[-1]: r for r in out['effects'] + out['sounds'] + out['flares']}
        out['package'] = p
        _CACHE[(name, stream)] = out
    return _CACHE[(name, stream)]


@unittest.skipUnless(INSTALL and INSTALL.exists(), WHY)
class Fixtures(unittest.TestCase):
    """The plan's fixture list (7.1), pinned to actors of the configured install."""

    def test_bar_effects(self):
        bar = records('URB_Bar')
        by, p = bar['by'], bar['package']
        building = str(p.by_name[PL + 'XComBuildingVolume_0'])
        # the five listed by floor 1 of the building though they stand 36 units past its wall (plan 2.4)
        for n in ('Emitter_4', 'Emitter_13', 'Emitter_14', 'Emitter_37', 'Emitter_45'):
            self.assertEqual(by[n]['floors'], [dict(building=building, floor=1)], n)
        # four named by the mission's script
        self.assertEqual(sorted(n for n, r in by.items() if r['kind'] == 'effect' and r['referencedBy']),
                         ['Emitter_0', 'Emitter_18', 'Emitter_19', 'Emitter_78'])
        self.assertEqual(by['Emitter_18']['referencedBy'], ['SeqAct_SetParticleSysParam_1 Target'])
        # a finite system (one burst of a headlight beam) and a looping one (steam)
        beam = bar['systems'][by['Emitter_4']['system']]
        live = [e for e in beam['emitters'] if e['lods']]
        self.assertEqual([(e['kind'], e['loops'], e['bursts']) for e in live], [('sprite', 1, 1)])
        steam = bar['systems'][by['Emitter_16']['system']]
        self.assertEqual(steam['name'], 'Steam_Small')
        self.assertEqual({e['loops'] for e in steam['emitters'] if e['lods']}, {0})
        # lit mesh particles (rats), an uneven scale (alien vapour)
        self.assertTrue(by['Emitter_18']['lit'])
        self.assertIn('mesh', {e['kind'] for e in bar['systems'][by['Emitter_18']['system']]['emitters']})
        self.assertGreater(len(set(by['Emitter_15']['drawScale3D'])), 1)
        # the fog pod's five smoke emitters stand around the pod, placed by a prefab instance at the pod's own place:
        # the pod carries them (export 30; F-50), each keeping its offset
        pod = {by[n]['carriedBy'] for n in ('Emitter_39', 'Emitter_43', 'Emitter_48', 'Emitter_49', 'Emitter_50')}
        self.assertEqual(len(pod), 1)
        self.assertTrue(next(iter(pod)).startswith('TheWorld.PersistentLevel.XComLevelActor_'), pod)
        for n in ('Emitter_39', 'Emitter_43', 'Emitter_48', 'Emitter_49', 'Emitter_50'):
            self.assertEqual((by[n]['prefab'], by[n]['carriedHow']), ('PrefabInstance_12', 'prefab'), n)
            self.assertGreater(max(abs(a - b) for a, b in zip(by[n]['location'], by['Emitter_39']['location'])) if n != 'Emitter_39' else 9, 2)
        # (one standing on its piece is carried by its place, as before)
        self.assertEqual({e['carriedHow'] for e in by.values() if e['carriedBy']}, {'place', 'prefab'})
        # the grounded Skyranger's lights and dust: the landing's, which a clear keeps
        self.assertEqual(by['Emitter_78']['landingRole'], 'emitter')
        self.assertFalse(by['Emitter_78']['can']['move'])
        self.assertTrue(by['Emitter_0']['landingActor'])                 # its dust, by LANDING_EXTRA
        self.assertTrue(all(r['startsOn'] is True for r in bar['effects']))
        self.assertEqual({r['startsOnFrom'] for r in bar['effects']}, {'class'})

    def test_bar_parameters_against_the_offers(self):
        bar = records('URB_Bar')
        e = bar['by']['Emitter_4']
        self.assertEqual([(r['name'], r['type'], r['offered']) for r in e['parameters']],
                         [('Brightness', 'PSPT_Scalar', 'otherKind'), ('Color', 'PSPT_Vector', 'yes')])
        self.assertEqual(e['parametersFrom'], 'actor')
        offers = {o['name']: o for o in bar['systems'][e['system']]['offers']}
        self.assertTrue(offers['Color']['colour'])
        self.assertEqual((offers['Color']['module'], offers['Color']['property']), ('ParticleModuleColor', 'StartColor'))
        self.assertFalse(offers['Brightness']['colour'])                 # a colour scale, not a colour
        self.assertEqual(offers['Opacity']['kind'], 'scalar')

    def test_bar_sounds_and_flares(self):
        bar = records('URB_Bar')
        by = bar['by']
        silent = by['AmbientSoundSimple_4']
        self.assertEqual((silent['waves'], silent['noSound']), ([], 'a sound slot names no wave'))
        self.assertEqual((silent['can']['audition'], silent['why']['audition']), (False, 'No sound set'))
        self.assertTrue(silent['can']['values'])
        sky = by['AmbientSoundSimpleToggleable_0']        # the Skyranger prefab's: its values are the archetype's
        self.assertEqual((sky['values']['radiusMin'], sky['values']['radiusMax']), (500.0, 2000.0))
        self.assertEqual((sky['valuesFrom']['radiusMin'], sky['valuesFrom']['volumeMin']), ('archetype', 'class'))
        self.assertEqual((sky['startsOn'], sky['startsOnFrom'], sky['landingRole']), (True, 'archetype', 'sound'))
        self.assertEqual((sky['can']['move'], sky['can']['copy'], sky['can']['audition']), (False, True, True))
        self.assertEqual(sky['waves'], ['URB_Bar|SoundParticleObjects.DropshipIdle'])
        self.assertTrue(all(w['playable'] for w in bar['waves'].values()))
        flare = by['LensFlareSource_7']
        self.assertEqual(flare['template'], 'FX_Lens_Flares.LF_XCom_Base_C')
        self.assertEqual((flare['can']['move'], flare['can']['values']), (True, False))

    def test_pier_shared_cue_attached_and_carried(self):
        pier = records('URB_PierA')['by']
        self.assertTrue(pier['Emitter_10']['lit'])
        self.assertEqual(pier['Emitter_10']['template'], 'FX_Water.Deep_Water.P_SeaFoam_Line')
        sound = pier['AmbientSoundSimple_1']
        self.assertEqual(sound['waves'], ['URB_PierA|SoundAmbience.IndustrialAirConditioningUnit'])
        self.assertEqual((sound['values']['radiusMin'], sound['values']['radiusMax']), (150.0, 350.0))
        base = records('AlienBase01')['by']
        hum = base['AmbientSound_0']                    # a cue asset nineteen of the map's sounds play
        self.assertEqual(hum['cue'], dict(path='SoundAmbience.StasisPodCollectibleCue', private=False, sharedBy=18))
        self.assertFalse(hum['can']['values'])
        self.assertIn('shared by 19', hum['why']['values'])
        self.assertEqual((hum['values']['radiusMax'], hum['valuesFrom']['radiusMax']), (800.0, 'cue'))
        self.assertTrue(hum['can']['audition'])
        off = base['Emitter_101']                       # starts off; the script switches it on
        self.assertEqual((off['startsOn'], off['startsOnFrom']), (False, 'actor'))
        self.assertTrue(off['referencedBy'])
        hq = records('Command1')['by']
        self.assertEqual(hq['Emitter_0']['attachedTo']['actor'], PL + 'XComUniverseCenter_0')
        self.assertFalse(any(hq['Emitter_0']['can'].values()))
        self.assertIsNone(hq['LensFlareSource_0']['attachedTo'])
        self.assertEqual(hq['LensFlareSource_1']['attachedTo']['actorClass'], 'XComUniverseCenter')
        intro = records('Act1_IntroLevel')['by']
        self.assertEqual((intro['Emitter_4']['carriedBy'], intro['Emitter_4']['carriedHow']),
                         (PL + 'XComLevelActor_116', 'place'))
        self.assertIsNone(intro['Emitter_4']['landingRole'])            # the tutorial's Skyranger is a loose piece

    def test_a_streams_own_are_read_only(self):
        furies = records('DLC2_3_Furies_Stream', stream='DLC2_3_Furies_Stream')
        self.assertTrue(furies['effects'] and furies['sounds'])
        for r in furies['effects'] + furies['sounds']:
            self.assertEqual((r['layer'], r['stream']), ('stream', 'DLC2_3_Furies_Stream'))
            self.assertTrue(r['id'].startswith('stream-DLC2_3_Furies_Stream-'))
            self.assertFalse(any(v for k, v in r['can'].items() if k != 'audition'), r['actor'])
        silent = furies['by']['AmbientSoundSimpleToggleable_0']          # a slotless node: nothing to hear
        self.assertEqual((silent['noSound'], silent['why']['audition']), ('its node has no sound slots', 'No sound set'))
        self.assertTrue(any(r['can']['audition'] for r in furies['sounds']))   # hearing changes nothing

    def test_class_defaults_are_what_the_script_packages_save(self):
        bar = records('URB_Bar')
        d = em.Defaults(bar['package'])
        self.assertIsNotNone(d.scripts)
        for cls, table in em.CLASS_DEFAULTS.items():
            for prop, value in table.items():
                found = d._script(None, cls, prop)
                self.assertIsNotNone(found, (cls, prop))
                got = False if found[1] is em.ZERO else found[1]
                self.assertAlmostEqual(got, value, places=5, msg=(cls, prop))

    def test_the_landing_rule_is_the_builds(self):
        sys.path.insert(0, str(HERE.parents[1] / 'bake'))
        import native_copy
        self.assertEqual(em.LANDING_PREFABS, native_copy.LANDING_PREFABS)
        self.assertEqual(em.LANDING_EXTRA, native_copy.LANDING_EXTRA)

    def test_the_exporter_carries_them(self):
        import export
        from package import Package
        import scene_metadata
        import tempfile
        self.assertGreaterEqual(export.EXPORT_VERSION, 29)
        p = Package(INSTALL)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ex = export.Exporter(p, Path(tmp.name))
        ex.prefabs, ex.kismet = scene_metadata.prefab_members(p), scene_metadata.kismet_references(p)
        found = ex.effects('map')
        self.assertEqual((len(found['effects']), len(found['sounds']), len(found['flares'])), (70, 6, 2))
        self.assertEqual(found['defaults'], 'script')
        # export 29: every emitter drawn or saying why, its textures and meshes written beside the map's
        emitters = [e for s in found['systems'].values() if s for e in s['emitters']]
        self.assertTrue(all('draw' in e and (e['draw'] or e['why']) for e in emitters))
        drawn = [e['draw'] for e in emitters if e['draw']]
        for d in drawn:
            if d['kind'] == 'mesh':
                self.assertTrue((Path(tmp.name) / ex.meshes[d['mesh']]['url']).is_file())
                self.assertTrue(all(m in ex.materials for m in d['materials']))
            for t in d.get('textures', []):
                self.assertTrue((Path(tmp.name) / ex.textures[t['key']]['url']).is_file())
        self.assertGreater(sum(1 for d in drawn if d['kind'] == 'sprite' and (d['picture'] or d['mask'])), 20)
        self.assertEqual(len(ex.landings), len(scene_metadata.landing_metadata(p)))
        # export 23's carriedBy is still there, for the compiler's carried effects
        self.assertEqual(sorted(e['actor'] for e in found['effects'] if e['carriedBy']),
                         sorted(e['actor'] for e in scene_metadata.effect_metadata(p) if e['carriedBy']))
        self.assertEqual(ex.effects('sample')['effects'], [])
        inherited = export.Exporter(p, None, namespace='inherited-patch_bar')
        inherited.prefabs, inherited.kismet = ex.prefabs, ex.kismet
        self.assertEqual(inherited.effects('map')['effects'], [])


if __name__ == '__main__':
    unittest.main()
