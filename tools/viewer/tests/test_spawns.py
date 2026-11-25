"""Landing zones (tools/viewer/spawns.py; private/plans/done/clear-map-plan.md, section 4): LWR's lines read and
written back, and where a zone puts the landing's actors."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import spawns  # noqa: E402
import settings  # noqa: E402
from viewer_fixtures import same_place  # noqa: E402

BAR_1 = 'LZArray=(MapName="URB_Bar",ESpawnLoc=ESL_Normal,StartLoc=(X=719,Y=-1681,Z=64),StartDir=ELZD_North)'
ABDUCTION = ('LZArray=(MapName="EWI_MeldTutorial",MissionType=eMission_Abduction,ESpawnLoc=ESL_Normal,'
             'StartLoc=(X=-913,Y=-1969,Z=64),StartDir=ELZD_North)')


class Lines(unittest.TestCase):
    def test_a_line_read_and_written_back(self):
        name, zone = spawns.parse_line(BAR_1)
        self.assertEqual(name, 'URB_Bar')
        self.assertEqual(zone, dict(kind='normal', location=[719, -1681, 64], direction='north'))
        self.assertEqual(spawns.write_line('URB_Bar', zone), BAR_1)
        self.assertEqual(spawns.write_line('URB_Bar_Remix_5005', zone), BAR_1.replace('"URB_Bar"', '"URB_Bar_Remix_5005"'))
        name, zone = spawns.parse_line(ABDUCTION)
        self.assertEqual(zone['missionType'], 'eMission_Abduction')
        self.assertEqual(spawns.write_line(name, zone), ABDUCTION)

    def test_other_fields_stay_on_their_line(self):
        # `other` goes into the game's ini as written: a line break in it would write lines of its own
        zone = dict(id='z', location=[0, 0, 0], direction='north')
        self.assertTrue(spawns.valid_zone(dict(zone, other='Spare=(A=1,B="x,y")\tC=2')))
        for other in ('X=1)\r\n[Evil]\r\nfoo=(Y=2', 'a\nb', 'a\u2028b', 'a\x00b', 'x' * 4001):
            self.assertFalse(spawns.valid_zone(dict(zone, other=other)), repr(other))
            with self.assertRaises(ValueError):
                spawns.write_line('URB_Bar', dict(zone, other=other))

    def test_the_shared_zone_cases(self):
        # review finding 27: zone_cases.json, which the page's validLandingZone passes too (clear_map_test.mjs); a
        # mission name ending in a line break is refused (it would split the LZArray line), and so is null for a field
        import json
        cases = json.loads((HERE / 'zone_cases.json').read_text(encoding='utf8'))['cases']
        self.assertGreater(len(cases), 30)
        for case in cases:
            self.assertEqual(spawns.valid_zone(case['zone']), case['valid'], case['why'])

    def test_fields_it_does_not_know_and_other_orders_are_kept(self):
        line = BAR_1[:-1] + ',Spare=(A=1,B="x,y"))'
        name, zone = spawns.parse_line(line)
        self.assertEqual(zone['other'], 'Spare=(A=1,B="x,y")')
        self.assertEqual(spawns.write_line(name, zone), line)
        odd = 'LZArray=(StartDir=ELZD_East,MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))'
        name, zone = spawns.parse_line(odd)
        self.assertEqual((zone['direction'], zone['location']), ('east', [1, 2, 3]))
        self.assertEqual(spawns.write_line(name, zone), odd)
        # an alternate place, as the struct has it (no line of the install uses one)
        alt = BAR_1[:-1].replace('ESL_Normal', 'ESL_Alternate') + ',AltSpawnLoc=(X=1,Y=2,Z=64),AltSpawnDir=ELZD_West)'
        name, zone = spawns.parse_line(alt)
        self.assertEqual(zone['alternate'], dict(location=[1, 2, 64], direction='west'))
        self.assertEqual(spawns.write_line(name, zone), alt)

    def test_lines_that_are_not_zones(self):
        self.assertIsNone(spawns.parse_line(';' + BAR_1))
        self.assertIsNone(spawns.parse_line('[XComLZMutator.XComLZMutator]'))
        with self.assertRaises(ValueError):
            spawns.parse_line('LZArray=(ESpawnLoc=ESL_Normal)')
        text = '\r\n'.join(['[XComLZMutator.XComLZMutator]', BAR_1, ';' + BAR_1, ABDUCTION, BAR_1.replace('Z=64', 'Z=80')])
        self.assertEqual([z['location'][2] for z in spawns.map_lines(text, 'urb_bar')], [64, 80])

    def test_every_line_of_the_install_comes_back_byte_for_byte(self):
        try:
            install = settings.load_settings().get('install')
        except Exception:
            install = None
        ini = Path(install or '.') / 'XEW' / 'XComGame' / 'Config' / 'DefaultLZMutator.ini'
        if not install or not ini.is_file():
            self.skipTest('no LWR install with DefaultLZMutator.ini')
        lines = [l for l in ini.read_text(encoding='latin-1').splitlines() if l.startswith('LZArray=')]
        self.assertGreaterEqual(len(lines), 453)
        for line in lines:
            name, zone = spawns.parse_line(line)
            self.assertEqual(spawns.write_line(name, zone), line)


class Places(unittest.TestCase):
    def test_bar_first_line_is_its_own_landing(self):
        # URB_Bar's drop zone frame (XComLevelActor_6, SoldierSpawns_DrpshipVol_12Arc0) stands at (720, -1680, 0), yaw 0
        zone = spawns.parse_line(BAR_1)[1]
        frame, yaw = spawns.place(zone)['frame']
        self.assertEqual(yaw, 0)
        self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(frame, (720, -1680, 0))))
        own = spawns.zone_of_frame((720, -1680, 0), 0)
        self.assertTrue(same_place(own, zone))
        self.assertFalse(same_place(own, dict(zone, direction='east')))
        self.assertEqual(spawns.ground(zone), 0)

    def test_offsets_turn_with_the_direction(self):
        north = spawns.place(dict(location=[0, 0, 64], direction='north'))
        east = spawns.place(dict(location=[0, 0, 64], direction='east'))
        self.assertEqual(north['soldiers'][3], ([0, 288, 48], 16384))
        # a quarter turn takes +y to -x
        self.assertEqual(east['soldiers'][3], ([-288, 0, 48], 32768))
        self.assertEqual(east['frame'], ([0, 0, 0], 16384))
        self.assertEqual(spawns.place(dict(location=[0, 0, 64], direction='west'))['volume'][0], [-47, 0, 96])
        # inside: the six points 288 further back
        inside = spawns.place(dict(location=[0, 0, 64], direction='north', kind='inside'))
        self.assertEqual(inside['soldiers'][3][0], [0, 0, 48])
        self.assertEqual(inside['frame'], north['frame'])
        self.assertEqual(spawns.zone_of_frame((5, 6, 10), 16380)['direction'], 'east')

    def test_the_evac_box_turns(self):
        self.assertEqual(spawns.evac_box(dict(location=[0, 0, 64], direction='north')), [-240, -191, 0, 240, 97, 192])
        box = spawns.evac_box(dict(location=[0, 0, 64], direction='east'))
        self.assertEqual(box[3] - box[0], 288)


class Export22(unittest.TestCase):
    """The map's own landings in the export (scene_metadata.landing_metadata, export 22), read from the game's Bar and
    Farm."""

    def package(self, name):
        sys.path.insert(0, str(HERE.parents[1] / 'lab'))
        import labpaths
        path, why = labpaths.install_map(name)
        if not path or not path.exists():
            self.skipTest(why)
        from package import Package
        return Package(path)

    def test_bars_landing_its_ten_actors_and_the_skyranger(self):
        import scene_metadata
        landings = scene_metadata.landing_metadata(self.package('URB_Bar'))
        self.assertEqual(len(landings), 1)
        roles = sorted(a['role'] for a in landings[0]['actors'])
        self.assertEqual(roles, sorted(['frame', 'volume', 'playerStart', 'point'] + ['soldier%d' % k for k in range(1, 7)]))
        frame = next(a for a in landings[0]['actors'] if a['role'] == 'frame')
        self.assertEqual(frame['path'], 'TheWorld.PersistentLevel.XComLevelActor_6')
        self.assertEqual(sorted(a['role'] for a in landings[0]['skyranger']['actors']), ['dust', 'emitter', 'mesh', 'point', 'sound'])
        # (export 35) its dust, the emitter beside the prefab, goes with it
        dust = next(a for a in landings[0]['skyranger']['actors'] if a['role'] == 'dust')
        self.assertEqual((dust['path'], dust['actorClass']), ('TheWorld.PersistentLevel.Emitter_0', 'Emitter'))
        self.assertTrue(dust['archetype'].endswith('ARC_Skyranger_Ground_Periphery'))
        # the mutator's offsets from Bar's first line put every actor within two units of the map's own
        zone = spawns.parse_line(BAR_1)[1]
        at = spawns.place(zone)
        for a in landings[0]['actors']:
            want = at['soldiers'][int(a['role'][-1]) - 1][0] if a['role'].startswith('soldier') else at[a['role']][0]
            self.assertTrue(all(abs(x - y) <= 2.5 for x, y in zip(a['location'], want)), (a['role'], a['location'], want))
        own = spawns.own_landings(dict(landings=landings))
        self.assertTrue(same_place(own[0]['zone'], zone))

    def test_the_farms_three_landings_in_the_games_order(self):
        import scene_metadata
        landings = scene_metadata.landing_metadata(self.package('CsmallScout_Farm'))
        self.assertEqual([l['group'] for l in landings], ['Group0', 'Group1', 'Group2'])
        self.assertTrue(all(len(l['actors']) == 10 and l['skyranger'] for l in landings))



def frameless(zone, shuffle=None, height=None):
    """A landing with no frame whose soldier points and PointInSpace stand where `zone` puts them (or the points
    `shuffle` gives instead), as export 22 lists one."""
    at = spawns.place(zone)
    points = shuffle or [loc for loc, _ in at['soldiers']]
    actors = [dict(role='soldier%d' % (k + 1), path='TheWorld.PersistentLevel.XComSpawnPoint_%d' % k, location=list(p),
                   rotation=[0, at['soldiers'][k][1], 0]) for k, p in enumerate(points)]
    actors.append(dict(role='point', path='TheWorld.PersistentLevel.PointInSpace_1', location=list(at['point'][0]),
                       rotation=[0, 0, 0]))
    return dict(prefab='PrefabInstance_5', group='XComSpawnPoint', actors=actors, skyranger=None)


class Frameless(unittest.TestCase):
    """A landing with no drop zone frame (the tutorial's, TempleShip's, the alien bases'): the zone fitted to its
    points (13 November 2026: this map's LZ and others like it fixed)."""
    def test_a_standard_layout_gives_its_zone_back_in_every_direction(self):
        for direction in spawns.DIRECTIONS:
            zone = dict(location=[-1680.0, -336.0, -320.0], direction=direction, kind='normal')
            self.assertEqual(spawns.fit_zone(frameless(zone)['actors']), zone, direction)

    def test_the_tutorials_own_points(self):
        """Act1_IntroLevel's six points, their own layout floating over the road, and its PointInSpace at 48: east,
        on the road's level (ground 48)."""
        points = [(-625.1, -48.1, 112), (-721.1, -144.0, 112), (-721.1, -336.0, 112), (-625.1, -432.0, 112),
                  (-816.0, -336.0, 96), (-528.0, -144.0, 112)]
        actors = [dict(role='soldier%d' % (k + 1), location=list(p), rotation=[0, 32000, 0]) for k, p in enumerate(points)]
        actors.append(dict(role='point', location=[-864.0, -384.0, 48.0], rotation=[0, 16384, 0]))
        self.assertEqual(spawns.fit_zone(actors), dict(location=[-353.0, -240.0, 112.0], direction='east', kind='normal'))
        # on its grid (bottom 0): down to the start of its level, the road's (the gizmo moves it by whole levels)
        self.assertEqual(spawns.fit_zone(actors, -3.05e-05)['location'], [-353.0, -240.0, 64.0])
        self.assertEqual(spawns.fit_zone(actors, -384.0)['location'], [-353.0, -240.0, 64.0])
        self.assertEqual(spawns.fit_zone(actors, -48.0)['location'], [-353.0, -240.0, 80.0])
        self.assertIsNone(spawns.fit_zone([dict(role='point', location=[0, 0, 0], rotation=[0, 0, 0])]))

    def test_own_landings_spots_and_the_frame(self):
        zone = dict(location=[960.0, 480.0, 64.0], direction='west', kind='normal')
        odd = [[900, 400, 48], [1000, 400, 48], [900, 500, 48], [1000, 500, 48], [900, 600, 48], [1000, 600, 48]]
        landing = frameless(zone, shuffle=odd)
        own, = spawns.own_landings(dict(landings=[landing]))
        self.assertTrue(own['fitted'])
        self.assertIsNone(own['frame'])
        # unmoved: its own points as the map has them; moved: the mutator's six
        self.assertEqual([p for p, _ in spawns.soldier_spots(own['zone'], own)], odd)
        moved = dict(own['zone'], location=[own['zone']['location'][0] + 96] + own['zone']['location'][1:])
        self.assertEqual(spawns.soldier_spots(moved, own), spawns.place(moved)['soldiers'])
        location, yaw = spawns.frame_of(landing)
        self.assertEqual((location, yaw), spawns.place(own['zone'])['frame'])


INTRO, NO_INTRO = None, 'the configured install has no Act1_IntroLevel'
try:
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    sys.path.insert(0, str(HERE.parents[1] / 'upk'))
    import labpaths  # noqa: E402
    INTRO, NO_INTRO = labpaths.install_map('Act1_IntroLevel')
    TEMPLE, NO_TEMPLE = labpaths.install_map('TempleShip')
except Exception as error:      # no install configured
    TEMPLE, NO_TEMPLE = None, str(error)


@unittest.skipUnless(INTRO and INTRO.exists() and TEMPLE and TEMPLE.exists(), NO_INTRO)
class Export23(unittest.TestCase):
    """Export 23 on the configured install: the effects and the frameless landings."""
    def test_the_tutorials_skyranger_carries_its_lights_and_the_vortex_is_no_ones(self):
        import scene_metadata
        from package import Package
        effects = {e['actor'].rsplit('.', 1)[-1]: e for e in scene_metadata.effect_metadata(Package(INTRO))}
        self.assertEqual(effects['Emitter_4']['carriedBy'], 'TheWorld.PersistentLevel.XComLevelActor_116')
        self.assertEqual(effects['Emitter_4']['template'], 'FX_VH_Skyranger.P_Skyranger_Idle')
        self.assertEqual(sorted(k for k, e in effects.items() if e['carriedBy']), ['Emitter_4'])
        self.assertIsNone(effects['Emitter_99']['carriedBy'])          # a fire on the street
        temple = {e['actor'].rsplit('.', 1)[-1]: e for e in scene_metadata.effect_metadata(Package(TEMPLE))}
        self.assertIsNone(temple['Emitter_3']['carriedBy'])             # at the origin, with 38 pieces

    def test_frameless_landings_are_zones(self):
        import scene_metadata
        from package import Package
        landings = scene_metadata.landing_metadata(Package(INTRO))
        own, = spawns.own_landings(dict(landings=landings))
        self.assertEqual(own['zone'], dict(location=[-353.0, -240.0, 112.0], direction='east', kind='normal'))
        grid = dict(origin=[-5377.0, -1248.0, -3.0517578125e-05])
        self.assertEqual(spawns.own_landings(dict(landings=landings, tileGrid=grid))[0]['zone']['location'], [-353.0, -240.0, 64.0])
        self.assertIsNone(landings[0]['skyranger'])                     # the tutorial's Skyranger is a loose piece
        temple = scene_metadata.landing_metadata(Package(TEMPLE))
        self.assertTrue(spawns.own_landings(dict(landings=temple))[0]['fitted'])
        self.assertIsNotNone(temple[0]['skyranger'])                    # matched from the fitted zone's frame

if __name__ == '__main__':
    unittest.main()
