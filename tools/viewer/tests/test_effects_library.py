"""Effects and sounds in the library (effects_library.py, stage FX4): what makes two placed actors one entry, the
panel's kinds and what keeps one from another map. Made-up records: no install needed."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import effects_library as fx  # noqa: E402


def effect(**changes):
    out = dict(kind='effect', actor='TheWorld.PersistentLevel.Emitter_3', actorClass='Emitter',
               template='FX_SmokeB.Misc.Steam_Small', parameters=[], scale=[1.0, 1.0, 1.0], componentPose=None,
               startsOn=True, can=dict(move=True, copy=True, delete=True), why={}, stream=None, landingActor=False,
               landingRole=None, location=[0.0, 0.0, 0.0])
    out.update(changes)
    return out


def sound(**changes):
    out = dict(kind='sound', actor='TheWorld.PersistentLevel.AmbientSoundSimple_2', actorClass='AmbientSoundSimple',
               cue=dict(path='TheWorld.PersistentLevel.AmbientSoundSimple_2.SoundCue_3', private=True, sharedBy=0),
               nodes=['SoundNodeAmbient'], waves=['URB_Bar|SoundEngineIdles.CarTaxiIdle'],
               values=dict(radiusMin=400.0, radiusMax=1200.0), startsOn=True, can=dict(copy=True), why={},
               stream=None, landingActor=False, landingRole=None)
    out.update(changes)
    return out


class Recipes(unittest.TestCase):
    def test_the_same_thing_placed_elsewhere_is_one_recipe(self):
        a, b = effect(), effect(actor='TheWorld.PersistentLevel.Emitter_9', location=[500.0, 0.0, 0.0])
        self.assertEqual(fx.recipe_key(a), fx.recipe_key(b))
        self.assertRegex(fx.recipe_key(a), r'^[0-9a-f]{16}$')
        # a private cue's path names its actor: two maps' taxis are one sound
        c = sound(actor='TheWorld.PersistentLevel.AmbientSoundSimple_7',
                  cue=dict(path='TheWorld.PersistentLevel.AmbientSoundSimple_7.SoundCue_1', private=True, sharedBy=0),
                  waves=['URB_Pier|SoundEngineIdles.CarTaxiIdle'])
        self.assertEqual(fx.recipe_key(sound()), fx.recipe_key(c))

    def test_what_changes_how_it_plays_is_another_recipe(self):
        base = fx.recipe_key(effect())
        for change in (dict(scale=[2.0, 2.0, 2.0]), dict(startsOn=False), dict(template='FX_SmokeB.Misc.Steam_Large'),
                       dict(parameters=[dict(name='Spawn', kind='scalar', value=3.0)]), dict(actorClass='EmitterSpawnable'),
                       dict(componentPose=dict(translation=[0.0, 0.0, 10.0], rotation=[0, 0, 0], scale=1.0))):
            self.assertNotEqual(fx.recipe_key(effect(**change)), base, change)
        # two cues that reach one wave are two sounds; a game asset's cue is named by its path
        shared = sound(cue=dict(path='SoundAmbience.HumCue', private=False, sharedBy=2), nodes=['SoundNodeAttenuation'])
        self.assertNotEqual(fx.recipe_key(shared), fx.recipe_key(sound()))
        self.assertEqual(fx.recipe(shared)['cue'], 'SoundAmbience.HumCue')
        self.assertIsNone(fx.recipe(sound())['cue'])
        self.assertNotEqual(fx.recipe_key(sound(values=dict(radiusMin=400.0, radiusMax=2000.0))), fx.recipe_key(sound()))
        # (float noise under the fourth decimal is no change)
        self.assertEqual(fx.recipe_key(effect(scale=[1.00001, 1.0, 1.0])), base)


class Kinds(unittest.TestCase):
    def test_kinds_from_the_system_or_the_wave(self):
        cases = [('effect', 'FX_Environmental.Animals.P_Moths_Wandering', 'Nature'),
                 ('effect', 'FX_Environmental.Animals.P_Rats_Scrambling', 'Nature'),
                 ('effect', 'FX_Fire_B.P_Fire_Mid_No_Chunks', 'Fire'),
                 ('effect', 'Fog_Cones.HeadLight_Beam_Cheap', 'Light beams and glows'),
                 ('effect', 'FX_SmokeB.Misc.Steam_Small', 'Smoke and steam'),
                 ('effect', 'FX_Water.Deep_Water.P_SeaFoam_Line', 'Water'),
                 ('effect', 'FX_Trash.Blowing.P_Trash_Blowing_Constant', 'Wreckage and trash'),
                 ('effect', 'FX_Something.P_Unknown', 'Other'),
                 ('effect', None, 'Other'),
                 ('sound', 'SoundBarMuzak.BarMuzakStereo', 'Music and voices'),
                 ('sound', 'SoundEngineIdles.CarTaxiIdle', 'Engines'),
                 ('sound', 'SoundAmbience.AlienNavModule', 'Alien'),
                 ('sound', 'SoundAmbience.StreamFlowing', 'Nature and weather'),
                 ('sound', 'SoundAmbience.ElectricalMachineHum06', 'Machines'),
                 ('sound', 'SoundAmbience.Nothing', 'Other')]
        for kind, path, label in cases:
            self.assertEqual(fx.kind_of(kind, path), label, path)

    def test_names(self):
        self.assertEqual(fx.name_of(effect()), 'Steam_Small')
        self.assertEqual(fx.name_of(sound()), 'CarTaxiIdle')
        self.assertEqual(fx.name_of(sound(waves=[], cue=dict(path='SoundAmbience.HumCue', private=False))), 'HumCue')
        self.assertEqual(fx.name_of(effect(template=None)), 'Emitter_3')
        self.assertEqual(fx.kind_path(sound()), 'SoundEngineIdles.CarTaxiIdle')


class Blocked(unittest.TestCase):
    def test_what_keeps_one_from_another_map(self):
        self.assertIsNone(fx.blocked(effect()))
        self.assertIn('stream', fx.blocked(effect(stream='patch_bar')))
        self.assertIn('landing mutator', fx.blocked(effect(landingActor=True)))
        self.assertIn('landing mutator', fx.blocked(sound(landingRole='skyranger')))
        self.assertEqual(fx.blocked(effect(can=dict(copy=False), why=dict(copy='it plays no particle system'))),
                         'it plays no particle system')
        self.assertIn('can\'t be copied', fx.blocked(effect(can={}, why={})))


if __name__ == '__main__':
    unittest.main()
