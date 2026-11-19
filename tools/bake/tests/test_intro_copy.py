"""The variant's own landing intro (tools/bake/intro_copy.py, F-45), on the LWR install's CIN_DropshipIntros."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import intro_copy  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# XCOM_INTRO_UPK, else the LWR install's (tools/viewer/settings.py)
INTRO, NO_INTRO = labpaths.test_file('XCOM_INTRO_UPK', labpaths.lwr_cooked('CIN_DropshipIntros.upk'),
                                     'CIN_DropshipIntros.upk')
# F-106: the map whose entry saves no place, and one whose entry has its place
TERROR, NO_TERROR = labpaths.install_map('URB_StreetHurricane_Terror')
BAR, NO_BAR = labpaths.install_map('URB_Bar')


@unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
class IntroCopy(unittest.TestCase):
    def test_the_base_maps_landing_names_the_variant_and_nothing_else_changes(self):
        p = intro_copy.lighting.Package(INTRO)
        before = {p.name(i): [t for _, t in e] for i, _, _, _, e in intro_copy.switches(p)}
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_URB_Bar_Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'URB_Bar', 'URB_Bar_Test_1234')
            q = intro_copy.lighting.Package(dst)
            after = {q.name(i): [t for _, t in e] for i, _, _, _, e in intro_copy.switches(q)}
            self.assertEqual(len(q.exports), len(p.exports))
        # one switch had URB_Bar's landing (entry 3 of 36); now it names the variant, and every other entry and switch
        # is as it was
        self.assertEqual([(r['switch'].split('.')[-1], r['entries']) for r in report['renamed']],
                         [('SeqCond_SwitchString_8', [3])])
        self.assertEqual(report['copy'], str(dst))
        for name, strings in before.items():
            expected = ['URB_Bar_Test_1234' if s == 'URB_Bar' else s for s in strings]
            self.assertEqual(after[name], expected)
        self.assertNotIn('URB_Bar', [s for strings in after.values() for s in strings])
        self.assertIn('URB_Bar_Terror', after[[n for n in after if n.endswith('SeqCond_SwitchString_1')][0]])

    def test_a_map_named_in_another_case_is_renamed_too(self):
        # the intro names CsmallScout_Farm (the package's case), a project CSmallScout_Farm (its records'), T-17
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_CSmallScout__Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'CSmallScout_Farm', 'CSmallScout__Test_1234')
            q = intro_copy.lighting.Package(dst)
            after = {q.name(i).split('.')[-1]: [t for _, t in e] for i, _, _, _, e in intro_copy.switches(q)}
        self.assertEqual([r['switch'].split('.')[-1] for r in report['renamed']], ['SeqCond_SwitchString_6'])
        self.assertIn('CSmallScout__Test_1234', after['SeqCond_SwitchString_6'])
        self.assertNotIn('CsmallScout_Farm', after['SeqCond_SwitchString_6'])
        self.assertIn('LAbductor_FarmOutskirts', after['SeqCond_SwitchString_6'])

    def test_a_moved_landing_moves_its_flight(self):
        """Clear map plan, step C7 (F-97): URB_Bar's flight place moved by its landing's move, four tiles east and a
        quarter turn; the Farm's three, one for each group, only the moved one's."""
        move = dict(index=0, frame=dict(old=[[720.0, -1680.0, 0.0], 0], new=[[1103.0, -1681.0, 0.0], 16384]))
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_URB_Bar_Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'URB_Bar', 'URB_Bar_Test_1234', [move])
            q = intro_copy.lighting.Package(dst)
            after = intro_copy.anchors(q, 'URB_Bar_Test_1234')
        self.assertEqual(report['notFound'], [])
        self.assertEqual(len(report['moved']), 1)
        old = report['moved'][0]['old']
        # the place relative to the frame, turned a quarter: (x, y) -> (-y, x)
        rel = [old['location'][0] - 720.0, old['location'][1] + 1680.0]
        want = [1103.0 - rel[1], -1681.0 + rel[0]]
        self.assertEqual(len(after), 1)
        self.assertTrue(all(abs(after[0]['location'][k] - want[k]) < 0.01 for k in range(2)), (after, want))
        self.assertEqual(after[0]['rotation'][1], old['rotation'][1] + 16384)
        # the Farm: its landing 1 moved, its groups 0 and 2 as they were
        p = intro_copy.lighting.Package(INTRO)
        before = {a['group']: a for a in intro_copy.anchors(p, 'CsmallScout_Farm')}
        self.assertEqual(sorted(before), [0, 1, 2])
        move = dict(index=1, frame=dict(old=[[0.0, 0.0, 0.0], 0], new=[[96.0, 0.0, 0.0], 0]))
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_CSmallScout__Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'CSmallScout_Farm', 'CSmallScout__Test_1234', [move])
            got = {a['group']: a for a in intro_copy.anchors(intro_copy.lighting.Package(dst), 'CSmallScout__Test_1234')}
        self.assertEqual([m['group'] for m in report['moved']], [1])
        for g in (0, 2):
            self.assertEqual(got[g]['location'], before[g]['location'])
        self.assertAlmostEqual(got[1]['location'][0], before[1]['location'][0] + 96, places=2)
        # a landing the intro has no place for is reported, never an error
        report = intro_copy.make(INTRO, Path(tempfile.gettempdir()) / 'CIN_DropshipIntros_URB_Bar_T_9.upk', 'URB_Bar',
                                 'URB_Bar_T_9', [dict(move, index=2)])
        self.assertEqual(report['notFound'], [2])
        Path(report['copy']).unlink()

    @unittest.skipUnless(TERROR and TERROR.exists() and BAR and BAR.exists(), NO_TERROR or NO_BAR)
    def test_an_entry_with_no_place_gets_the_grounded_skyrangers(self):
        """F-106: URB_StreetHurricane_Terror's entry saves no place (the rig went to (0, 0, 0), the middle of the map);
        with the map given, the copy puts it at the map's grounded Skyranger, and a moved landing moves it from there.
        A map whose entry has a place (URB_Bar) keeps it."""
        p = intro_copy.lighting.Package(INTRO)
        action, = [a['action'] for a in intro_copy.anchors(p, 'URB_StreetHurricane_Terror')]
        self.assertIsNone(p.own(action, 'LocationValue'))
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_URB_Terror_Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'URB_StreetHurricane_Terror', 'URB_Terror_Test_1234', map_path=TERROR)
            q = intro_copy.lighting.Package(dst)
            got, = intro_copy.anchors(q, 'URB_Terror_Test_1234')
            self.assertEqual(len(q.exports), len(p.exports))
            # every other entry's place as it was
            others = {k: [a['location'] for a in intro_copy.anchors(p, k)] for k in ('URB_Bar', 'URB_StreetHurricane')}
            self.assertEqual({k: [a['location'] for a in intro_copy.anchors(q, k)] for k in others}, others)
        filled, = report['filled']
        self.assertEqual((filled['action'], filled['skyranger'], filled['landing']), ('SeqAct_SetLocation_34', 'XComLevelActor_91', 0))
        self.assertEqual([round(v) for v in got['location']], [3813, -134, 1])
        self.assertEqual(got['rotation'], [0, 18468, 0])
        # a moved landing (a quarter turn about the frame) moves the filled place from the Skyranger's
        frame = [2251.0, -524.0, 0.0]
        move = dict(index=0, frame=dict(old=[frame, 16384], new=[[frame[0], frame[1] + 960, 0.0], 32768]))
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_URB_Terror_Test_1234.upk'
            report = intro_copy.make(INTRO, dst, 'URB_StreetHurricane_Terror', 'URB_Terror_Test_1234', [move], TERROR)
            moved, = intro_copy.anchors(intro_copy.lighting.Package(dst), 'URB_Terror_Test_1234')
        rel = [got['location'][0] - frame[0], got['location'][1] - frame[1]]
        want = [frame[0] - rel[1], frame[1] + 960 + rel[0]]
        self.assertTrue(all(abs(moved['location'][k] - want[k]) < 0.01 for k in range(2)), (moved, want))
        self.assertEqual(moved['rotation'][1], 18468 + 16384)
        self.assertEqual(report['moved'][0]['old']['location'], got['location'])
        # URB_Bar's entry has its place: nothing filled
        with tempfile.TemporaryDirectory() as d:
            report = intro_copy.make(INTRO, Path(d) / 'CIN_DropshipIntros_URB_Bar_Test_1234.upk', 'URB_Bar', 'URB_Bar_Test_1234',
                                     map_path=BAR)
        self.assertNotIn('filled', report)

    def test_a_map_the_intro_has_no_landing_for_gets_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_URB_Nowhere_X.upk'
            report = intro_copy.make(INTRO, dst, 'URB_Nowhere', 'URB_Nowhere_X')
            self.assertFalse(dst.exists())
        self.assertEqual((report['copy'], report['renamed']), (None, []))

    def test_the_copy_needs_a_name_of_its_own(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            intro_copy.make(INTRO, Path(d) / 'CIN_DropshipIntros.upk', 'URB_Bar', 'URB_Bar_X')

    def test_a_packs_copy_adds_each_maps_case_after_its_bases(self):
        """F-142: one copy for a pack's maps. Two of URB_Bar and one of the farm get cases after their bases', with the
        base's output; the farm's moved place is written; a third of URB_Bar flying elsewhere and a map the intro has
        no case for are left out (they keep their own copies)."""
        p = intro_copy.lighting.Package(INTRO)
        before = {p.name(i).split('.')[-1]: [t for _, t in e] for i, _, _, _, e in intro_copy.switches(p)}
        farm = ([-286.02734375, 6877.921875, 0.0], [0, -32764, 0])
        maps = [dict(base='URB_Bar', variant='URB_Bar_One_1'), dict(base='URB_Bar', variant='Pinkbar'),
                dict(base='CSmallScout_Farm', variant='CSmallScout__Farm_x', places={'SeqAct_SetLocation_58': farm}),
                dict(base='URB_Bar', variant='URB_Bar_Moved', places={'SeqAct_SetLocation_84': ([1.0, 2.0, 0.0], [0, 0, 0])}),
                dict(base='URB_Nowhere', variant='URB_Nowhere_X')]
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_DropshipIntros_My_pack_0042.upk'
            report = intro_copy.pack_copy(INTRO, dst, maps)
            q = intro_copy.lighting.Package(dst)
            after = {q.name(i).split('.')[-1]: [t for _, t in e] for i, _, _, _, e in intro_copy.switches(q)}
            farm_after = {a['group']: a for a in intro_copy.anchors(q, 'CSmallScout__Farm_x')}
            farm_before = {a['group']: a for a in intro_copy.anchors(p, 'CsmallScout_Farm')}
            self.assertEqual(len(q.exports), len(p.exports))
        self.assertEqual(report['copy'], str(dst))
        self.assertEqual([(c['variant'], c['switches']) for c in report['cases']],
                         [('URB_Bar_One_1', ['SeqCond_SwitchString_8']), ('Pinkbar', ['SeqCond_SwitchString_8']),
                          ('CSmallScout__Farm_x', ['SeqCond_SwitchString_6'])])
        self.assertEqual([(l['variant'], l['why']) for l in report['left']],
                         [('URB_Bar_Moved', 'its landing flies otherwise than URB_Bar_One_1\'s'),
                          ('URB_Nowhere_X', 'the intro has no case for URB_Nowhere')])
        # each new case right after its base's, every case of the intro kept
        bar = before['SeqCond_SwitchString_8'].index('URB_Bar')
        self.assertEqual(after['SeqCond_SwitchString_8'], before['SeqCond_SwitchString_8'][:bar + 1] + ['URB_Bar_One_1', 'Pinkbar']
                         + before['SeqCond_SwitchString_8'][bar + 1:])
        self.assertEqual(len(after['SeqCond_SwitchString_6']), len(before['SeqCond_SwitchString_6']) + 1)
        self.assertEqual((after['SeqCond_SwitchString_1'], after['SeqCond_SwitchString_5']),
                         (before['SeqCond_SwitchString_1'], before['SeqCond_SwitchString_5']))
        # the farm flies to its moved place (its landing 0), its other landings as they were
        self.assertEqual([p_['action'] for p_ in report['places']], ['SeqAct_SetLocation_58'])
        self.assertEqual((farm_after[0]['location'], farm_after[0]['rotation']), (farm[0], farm[1]))
        for g in (1, 2):
            self.assertEqual(farm_after[g]['location'], farm_before[g]['location'])

    def test_a_packs_copy_takes_a_place_from_the_builds_own_copy(self):
        move = dict(index=0, frame=dict(old=[[720.0, -1680.0, 0.0], 0], new=[[1103.0, -1681.0, 0.0], 16384]))
        with tempfile.TemporaryDirectory() as d:
            own = Path(d) / 'CIN_DropshipIntros_URB_Bar_Test_1234.upk'
            report = intro_copy.make(INTRO, own, 'URB_Bar', 'URB_Bar_Test_1234', [move])
            action = report['moved'][0]['action']
            places = intro_copy.flight_places(own, [action])
            want, = intro_copy.anchors(intro_copy.lighting.Package(own), 'URB_Bar_Test_1234')
            dst = Path(d) / 'CIN_DropshipIntros_Pack_0001.upk'
            intro_copy.pack_copy(INTRO, dst, [dict(base='URB_Bar', variant='URB_Bar_Test_1234', places=places)])
            got, = intro_copy.anchors(intro_copy.lighting.Package(dst), 'URB_Bar_Test_1234')
            with self.assertRaises(ValueError): intro_copy.flight_places(own, ['SeqAct_Nothing_1'])
        self.assertEqual((got['location'], got['rotation']), (want['location'], want['rotation']))
        with tempfile.TemporaryDirectory() as d:          # no map in: no file
            report = intro_copy.pack_copy(INTRO, Path(d) / 'CIN_DropshipIntros_P_1.upk', [dict(base='URB_Nowhere', variant='X')])
            self.assertEqual((report['copy'], list(Path(d).iterdir())), (None, []))

    def test_strings_round_trip(self):
        for text in ('URB_Bar', '', 'Caf\u00e9', 'Mapa \u0434'):
            self.assertEqual(intro_copy.read_fstring(intro_copy.fstring(text), 0),
                             (text, len(intro_copy.fstring(text))))


# XCOM_ENTRANCE_UPK, else the LWR install's: the alien bases' entrance intro (F-76)
ENTRANCE, NO_ENTRANCE = labpaths.test_file('XCOM_ENTRANCE_UPK', labpaths.lwr_cooked('CIN_TP05A_EnteringAlienBase.upk'),
                                           'CIN_TP05A_EnteringAlienBase.upk')


@unittest.skipUnless(ENTRANCE and ENTRANCE.exists(), NO_ENTRANCE)
class EntranceCopy(unittest.TestCase):
    def test_the_alien_bases_switch_names_the_variant(self):
        # one switch ("Which alien base map are we in?"): AlienBase01, AlienBase02, Default. A variant of AlienBase01
        # matched none of them, so the intro never played and the battle never started (F-76)
        p = intro_copy.lighting.Package(ENTRANCE)
        before = [[t for _, t in e] for *_, e in intro_copy.switches(p)]
        self.assertEqual(before, [['AlienBase01', 'AlienBase02', 'Default']])
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_TP05A_EnteringAlienBase_AlienBase01_Test_1234.upk'
            report = intro_copy.make(ENTRANCE, dst, 'AlienBase01', 'AlienBase01_Test_1234')
            q = intro_copy.lighting.Package(dst)
            after = [[t for _, t in e] for *_, e in intro_copy.switches(q)]
            self.assertEqual(len(q.exports), len(p.exports))
        self.assertEqual([(r['switch'].split('.')[-1], r['entries'], r['of']) for r in report['renamed']],
                         [('SeqCond_SwitchString_1', [0], 3)])
        self.assertEqual(after, [['AlienBase01_Test_1234', 'AlienBase02', 'Default']])

    def test_a_packs_copy_of_the_entrance_has_a_case_for_each_alien_base(self):
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'CIN_TP05A_EnteringAlienBase_My_pack_0042.upk'
            report = intro_copy.pack_copy(ENTRANCE, dst, [dict(base='AlienBase01', variant='AlienBase01_One_1'),
                                                          dict(base='AlienBase02', variant='AlienBase02_Two_2'),
                                                          dict(base='AlienBase01', variant='AlienBase01_Three_3')])
            after = [[t for _, t in e] for *_, e in intro_copy.switches(intro_copy.lighting.Package(dst))]
        self.assertEqual(report['left'], [])
        self.assertEqual(after, [['AlienBase01', 'AlienBase01_One_1', 'AlienBase01_Three_3', 'AlienBase02', 'AlienBase02_Two_2',
                                  'Default']])


if __name__ == '__main__':
    unittest.main()
