"""The effects census's pure parts (audit_effects.py): what a plain preview would make of a particle system, the
spread of a list of sizes, and the summary over packages."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_effects as effects  # noqa: E402

M = 'ParticleModule'


def emitter(*modules, mesh=False, lods=1):
    return dict(lods=lods, typeData=M + 'TypeDataMesh' if mesh else None, modules=[M + m for m in modules])


class Preview(unittest.TestCase):
    def test_sprites_with_common_modules_are_core(self):
        self.assertEqual(effects.preview_kind([emitter('Color', 'Size', 'Lifetime', 'Velocity')]), 'sprites core')

    def test_one_rarer_module_makes_the_system_beyond(self):
        self.assertEqual(effects.preview_kind([emitter('Color', 'Size'), emitter('Size', 'Orbit')]), 'sprites beyond')

    def test_a_mesh_emitter_makes_it_meshes_and_may_use_the_mesh_modules(self):
        system = [emitter('Color', 'Size'), emitter('Size', 'MeshRotation', mesh=True)]
        self.assertEqual(effects.preview_kind(system), 'meshes core')
        self.assertEqual(effects.preview_kind(system + [emitter('Collision', mesh=True)]), 'meshes beyond')

    def test_a_mesh_module_on_a_sprite_system_is_beyond(self):
        self.assertEqual(effects.preview_kind([emitter('Size', 'MeshRotation')]), 'sprites beyond')

    def test_emitters_the_cook_stripped_are_left_out(self):
        self.assertEqual(effects.preview_kind([emitter('Orbit', lods=0), emitter('Size')]), 'sprites core')
        self.assertEqual(effects.preview_kind([emitter('Size', lods=0)]), 'empty')
        self.assertEqual(effects.preview_kind([]), 'empty')


class Spread(unittest.TestCase):
    def test_least_median_ninetieth_and_most(self):
        self.assertEqual(effects.spread(list(range(1, 11))), [1, 5.5, 10, 10])
        self.assertEqual(effects.spread([7]), [7, 7, 7, 7])
        self.assertIsNone(effects.spread([]))


class Lifecycle(unittest.TestCase):
    def test_by_the_live_emitters_loops(self):
        self.assertEqual(effects.lifecycle([dict(lods=1, loops=0), dict(lods=2)]), 'looping')
        self.assertEqual(effects.lifecycle([dict(lods=1, loops=1), dict(lods=1, loops=3)]), 'finite')
        self.assertEqual(effects.lifecycle([dict(lods=1, loops=0), dict(lods=1, loops=1)]), 'mixed')

    def test_stripped_emitters_do_not_count(self):
        self.assertEqual(effects.lifecycle([dict(lods=0, loops=1), dict(lods=1, loops=0)]), 'looping')
        self.assertEqual(effects.lifecycle([dict(lods=0, loops=1)]), 'empty')


class Inside(unittest.TestCase):
    BOX = dict(min=[0.0, 0.0, 0.0], max=[100.0, 50.0, 20.0])

    def test_a_point_in_any_box_with_slack(self):
        self.assertTrue(effects.inside([100.0, 25.0, 10.0], [self.BOX]))
        self.assertFalse(effects.inside([101.0, 25.0, 10.0], [self.BOX]))
        self.assertTrue(effects.inside([101.0, 25.0, 10.0], [self.BOX], 2.0))
        self.assertTrue(effects.inside([500.0, 0.0, 0.0], [self.BOX, dict(min=[400.0, -1.0, -1.0], max=[600.0, 1.0, 1.0])]))
        self.assertFalse(effects.inside([0.0, 0.0, 0.0], [None]))
        self.assertFalse(effects.inside([0.0, 0.0, 0.0], []))


class Copies(unittest.TestCase):
    def test_a_newer_package_of_the_same_guid_is_a_copy(self):
        found = dict(Bar=dict(guid='aa', modified=1000), Bar_Mine=dict(guid='aa', modified=1000 + 30 * 86400),
                     Pier=dict(guid='bb', modified=1000), Pier_Asian=dict(guid='bb', modified=1500),
                     Broken=dict(error='unreadable'), NoGuid=dict(guid='', modified=5))
        self.assertEqual(effects.copies(found), {'Bar_Mine'})


def package(role, licensee, emitters=None, sounds=None, systems=None, waves=None, closure=None):
    record = dict(role=role, licensee=licensee, emitters=emitters or {}, sounds=sounds or {}, flares={}, others={},
                  systems=systems or {}, waves=waves or {})
    if closure:
        record['closure'] = closure
    return record


class Summary(unittest.TestCase):
    def setUp(self):
        fire = dict(emitters=[emitter('Color', 'Size')], native=0)
        swarm = dict(emitters=[emitter('Size', 'Orbit')], native=0)
        hum = dict(size=1000, seconds=2.0, channels=1, rate=44100, oggAfterProperties=32)
        self.found = dict(
            Bar=package('base', 64, dict(count=3, kismetNamed=1, templates={'FX.Fire': 2, 'FX.Swarm': 1}),
                        dict(count=1, classes={'AmbientSoundSimple': 1}), {'FX.Fire': fire, 'FX.Swarm': swarm},
                        {'Snd.Hum': hum},
                        dict(Emitter=dict(ok=3, refused={}, cut={}, sizes=[(10, 100), (20, 300), (30, 200)]))),
            Pier=package('base', 64, dict(count=1, templates={'FX.Fire': 1}), dict(count=0), {'FX.Fire': fire},
                         {'Snd.Hum': hum},
                         dict(Emitter=dict(ok=1, refused={'no layout here': 1}, cut={'A -> B': 2}, sizes=[(40, 400)]))),
            patch_bar=package('stream', 0, dict(count=2, templates={'FX.Fire': 2}), dict(count=0), {'FX.Fire': fire}),
            Broken=dict(error='unreadable'))
        self.summary = effects.summarise(self.found)

    def test_packages_are_grouped_by_role_and_maker(self):
        groups = self.summary['groups']
        self.assertEqual(sorted(groups), ['base firaxis', 'stream lwr'])
        base = groups['base firaxis']
        self.assertEqual((base['packages'], base['withEmitters'], base['withSounds']), (2, 2, 1))
        self.assertEqual(base['emitters']['count'], 4)
        self.assertEqual(base['emitters']['templates'], {'FX.Fire': 3, 'FX.Swarm': 1})
        self.assertEqual(base['perMap']['emitters'], [1, 2.0, 3, 3])

    def test_a_system_and_a_wave_are_listed_once_with_their_packages(self):
        fire = self.summary['systems']['FX.Fire']
        self.assertEqual((fire['packages'], fire['placements'], fire['preview']), (2, 3, 'sprites core'))
        self.assertEqual(self.summary['waves']['Snd.Hum']['packages'], 2)
        self.assertEqual((self.summary['distinctSystems'], self.summary['systemsPlaced']), (2, 2))
        self.assertEqual((self.summary['distinctWaves'], self.summary['waveBytes']), (1, 1000))

    def test_lwr_patches_are_not_donors(self):
        # their emitters are counted in their group, but neither their systems nor their placements are the library's
        self.assertEqual(self.summary['groups']['stream lwr']['emitters']['count'], 2)
        self.assertEqual(self.summary['systems']['FX.Fire']['placements'], 3)

    def test_emitters_are_counted_by_their_systems_preview(self):
        self.assertEqual(self.summary['preview'], {'sprites core': 3, 'sprites beyond': 1})

    def test_closures_are_summed_and_their_sizes_spread(self):
        c = self.summary['closure']['Emitter']
        self.assertEqual((c['ok'], c['refused'], c['cut']), (4, {'no layout here': 1}, {'A -> B': 2}))
        self.assertEqual(c['objects'], [10, 25.0, 40, 40])
        self.assertEqual(c['bytes'], [100, 250.0, 400, 400])


if __name__ == '__main__':
    unittest.main()
