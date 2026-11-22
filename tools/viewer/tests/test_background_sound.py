"""A map's background sound (background_sound.py; export 39) and its triggers counted (scene_metadata.trigger_counts).
The first tests run on a made-up package; the rest on the install's maps, skipping without them: URB_Bar and
CSmallScout_Roadhouse, and every row of background_sounds.json against the map it names."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import background_sound as bs  # noqa: E402
from package import Package  # noqa: E402
import scene_metadata  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
ROADHOUSE, NO_ROADHOUSE = labpaths.install_map('CSmallScout_Roadhouse')


def obj(i):
    return dict(kind='ObjectProperty', value=i)


def outs(*ops):
    return dict(kind='ArrayProperty', value=[{('Links', 0): dict(kind='ArrayProperty', value=[
        {('LinkedOp', 0): obj(op), ('InputLinkIdx', 0): dict(kind='IntProperty', value=0)} for op in ops])}])


class MadeUp:
    """A level-loaded event (3) that leads through a delay (4) to a sound played at an emitter (5: it has a target)
    and to the background sound (6: none), with its volume; a cue import (-1)."""
    ROWS = {
        1: ('Level', 0, 'TheWorld.PersistentLevel', {}),
        2: ('Sequence', 1, 'Main_Sequence', {}),
        3: ('SeqEvent_LevelLoaded', 2, 'SeqEvent_LevelLoaded_0', {('OutputLinks', 0): outs(4)}),
        4: ('SeqAct_Delay', 2, 'SeqAct_Delay_0', {('OutputLinks', 0): outs(5, 6)}),
        5: ('SeqAct_PlaySound', 2, 'SeqAct_PlaySound_0', {('PlaySound', 0): obj(-1), ('VariableLinks', 0): dict(kind='ArrayProperty', value=[
            {('LinkedVariables', 0): dict(kind='ArrayProperty', value=[7])}])}),
        6: ('SeqAct_PlaySound', 2, 'SeqAct_PlaySound_1', {('PlaySound', 0): obj(-1),
                                                          ('VolumeMultiplier', 0): dict(kind='FloatProperty', value=0.5)}),
        7: ('SeqVar_Object', 2, 'SeqVar_Object_0', {}),
    }

    def __init__(self):
        self.exports = [dict(outer=self.ROWS[i][1]) for i in sorted(self.ROWS)]
        self.paths = ['TheWorld.PersistentLevel'] + ['TheWorld.PersistentLevel.' + (r[2] if r[1] == 1 else 'Main_Sequence.' + r[2])
                                                       for i, r in sorted(self.ROWS.items()) if i > 1]
        self.by_name = {path: i for i, path in enumerate(self.paths, 1)}

    def name(self, i): return 'Sounds.WindCue' if i == -1 else self.paths[i - 1]
    def cls(self, i): return self.ROWS[i][0]
    def properties(self, i): return self.ROWS[i][3], 0
    def structs(self, raw): return raw or []
    def refs(self, raw): return list(raw or [])


class MadeUpTests(unittest.TestCase):
    def test_the_sound_with_no_target_behind_a_delay(self):
        self.assertEqual(bs.background_sound(MadeUp()), dict(
            event='TheWorld.PersistentLevel.Main_Sequence.SeqEvent_LevelLoaded_0',
            op='TheWorld.PersistentLevel.Main_Sequence.SeqAct_PlaySound_1', cue='Sounds.WindCue', volume=0.5, fadeIn=None))

    def test_the_catalogue_and_its_words(self):
        rows = bs.catalogue()
        self.assertEqual(len(rows), 26)
        self.assertEqual(len({r['cue'] for r in rows}), 26)
        self.assertTrue(all(r['label'] and r['map'] and r['maps'] >= 1 for r in rows))
        self.assertEqual(bs.words('SoundAmbience-NorthAmerica.ForestAmbienceCue'), 'Forest')
        self.assertEqual(bs.words('Some.OtherCue'), 'Other')


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarTests(unittest.TestCase):
    def test_bars_wind_and_traffic_and_its_two_triggers(self):
        p = Package(BAR)
        found = bs.background_sound(p)
        self.assertEqual((found['cue'], found['op'].rsplit('.', 1)[-1]), ('SoundAmbience-NorthAmerica.LightWindTrafficPaperCue', 'SeqAct_PlaySound_0'))
        self.assertEqual(scene_metadata.trigger_counts(p), dict(volumes=2, water=0, sight=0))


@unittest.skipUnless(ROADHOUSE and ROADHOUSE.exists(), NO_ROADHOUSE)
class RoadhouseTests(unittest.TestCase):
    def test_the_night_and_the_marsh(self):
        p = Package(ROADHOUSE)
        self.assertEqual(bs.background_sound(p)['cue'], 'SoundAmbience-NorthAmerica.NightAmbienceCue')
        self.assertEqual(scene_metadata.trigger_counts(p), dict(volumes=5, water=8, sight=1))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class CatalogueTests(unittest.TestCase):
    def test_each_sounds_map_plays_it(self):
        # (the maps beside the Bar's, in the install's EW folder or the base game's)
        folders = [Path(BAR).parent, Path(BAR).parents[3] / 'XComGame' / 'CookedPCConsole']
        checked = 0
        for row in bs.catalogue():
            path = next((f / (row['map'] + '.upk') for f in folders if (f / (row['map'] + '.upk')).is_file()), None)
            if path is None:
                continue
            with self.subTest(row['cue']):
                p = Package(path)
                self.assertEqual(bs.background_sound(p)['cue'], row['cue'])
                # the waves the Map settings window plays for it (each a SoundNodeWave the cue's nodes reach)
                self.assertEqual(bs.waves(p, p.by_name[row['cue']]), row['waves'])
                checked += 1
        self.assertGreater(checked, 20)


if __name__ == '__main__':
    unittest.main()
