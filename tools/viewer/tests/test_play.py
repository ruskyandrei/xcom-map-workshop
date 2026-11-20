"""Play in game and Remove from game (installs.py, gamelaunch.py, play.py and its routes), on temporary game installs:
in the LWR install the editor reads, and in a separate copy (the install setting). Nothing is started: the tests give
the player a start that records its command."""
from functools import partial
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'bake' / 'tests'))
from builds import BuildRunner  # noqa: E402
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import gamelaunch  # noqa: E402
import maplist  # noqa: E402
import missions  # noqa: E402
from play import Player  # noqa: E402
import playsaves  # noqa: E402
from projects import ProjectError, ProjectStore  # noqa: E402
from test_deploy import record  # noqa: E402
from test_projects import ID, OTHER, document  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402

VARIANT = 'URB_Bar_Remix_0f8b'
# Long War's loader with the drop-in mutator, and its drop-in settings (editor spawns plan, SP8)
MUTATOR_LOADER = b'[XComMutator.XComMutatorLoader]\r\narrTacticalMutators="XComLZMutator.XComSpawnAlienMutator"\r\n'
RANDOM_SPAWNS = dep.EOL.join([b'[XComLZMutator.XComSpawnAlienMutator]', b'MAX_DROP_DIST = 32', b'ExcludeMaps = "EWI_ChryssalidHive"',
                              b';ExcludeMaps = "DLC2_2_Deluge"', b'', b'[XComLZMutator.XComSpawnMutator]', b'PLAYER_PROXIMITY = 29', b''])
SLOT = installs.INTRO_SLOT


def bomb_record(name='URB_Bar'):
    """A council bomb record of URB_Bar, as LWR gives Boulevard, Fast Food and Street Hurricane theirs (plan 2.6): out
    of rotation, streaming Slaughterhouse's bomb stream."""
    line = record('bar')
    for field, value in (('MissionType', 'eMission_Special'), ('CouncilType', 'eFCMType_Bomb'), ('bInRotation', 'False')):
        line = dep.set_field(line, field, value, quoted=False)
    line = dep.set_field(line, 'DisplayName', f'{name}_Bomb (Mission Variant Bomb Defusal Bar) |0')
    return dep.add_stream(line, 'URB_Slaughterhouse_Stream')[0]


# DefaultContent.ini's lines that the civilians' looks come from (missions.civilian_content), as the install writes them
CONTENT = '\n'.join([
    '[XComGame.XComContentManager]',
    'BodyPackageInfo=(Id=3,CustomTag="Liam",ArchetypeName="B.A", Gender=eGender_Male, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Cold)',
    'BodyPackageInfo=(Id=4,ArchetypeName="B.B", Gender=eGender_Male, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Cold)',
    'BodyPackageInfo=(Id=6,ArchetypeName="B.C", Gender=eGender_Male, Character=eChar_Civilian, Race=eRace_African, Type=eCivilian_Warm)',
    'BodyPackageInfo=(Id=8,ArchetypeName="B.D", Gender=eGender_Male, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Warm)',
    'BodyPackageInfo=(Id=9,ArchetypeName="B.E", Gender=eGender_Male, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Warm)',
    'BodyPackageInfo=(Id=11,ArchetypeName="B.F", Gender=eGender_Female, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Warm)',
    'BodyPackageInfo=(Id=12,ArchetypeName="B.G", Gender=eGender_Female, Character=eChar_Civilian, Race=eRace_Caucasian, Type=eCivilian_Warm)',
    'BodyPackageInfo=(Id=40,ArchetypeName="B.S", Gender=eGender_Male, Character=eChar_Soldier, Race=eRace_Caucasian)',
    'HairPackageInfo=(Id=1,ArchetypeName="H.A", Gender=eGender_Female, bCanUseOnCivilian=true)',
    'HairPackageInfo=(Id=11,ArchetypeName="H.K", Gender=eGender_Female)',
    'HairPackageInfo=(Id=14,CustomTag="JoeKelly",ArchetypeName="H.M", Gender=eGender_Male, bCanUseOnCivilian=true)',
    'HairPackageInfo=(Id=19,ArchetypeName="H.F", Gender=eGender_Male, bCanUseOnCivilian=true)',
    'HeadPackageInfo=(Id=70,CustomTag="MinisterHutch",Gender=eGender_Male,Character=eChar_Civilian,Race=eRace_Caucasian,ArchetypeName="X.A")',
    'HeadPackageInfo=(Id=72,CustomTag="",Gender=eGender_Male,Character=eChar_Civilian,Race=eRace_African,ArchetypeName="X.B")',
    'HeadPackageInfo=(Id=73,CustomTag="",Gender=eGender_Female,Character=eChar_Civilian,Race=eRace_Caucasian,ArchetypeName="X.C")',
    'HeadPackageInfo=(Id=80,Gender=eGender_Male,Character=eChar_Soldier,Race=eRace_Caucasian,ArchetypeName="X.D")',
    ''])


def game_folder(game, slot, lz=b'LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))', kind='lwr'):
    (game / 'XEW/XComGame/Config').mkdir(parents=True)
    (game / 'XEW/XComGame/CookedPCConsole').mkdir(parents=True)
    (game / 'XEW/Binaries/Win32').mkdir(parents=True)
    (game / 'XEW/Binaries/Win32/XComEW.exe').write_bytes(b'exe')
    (game / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', record('bar'), slot, b'']))
    (game / 'XEW/XComGame/Config/DefaultLZMutator.ini').write_bytes(dep.EOL.join([b'[XComLZMutator.XComLZMutator]', lz, b'']))
    if kind == 'lwr': (game / 'XEW/XComGame/Config/DefaultLWRebalance.ini').write_bytes(b'')
    (game / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk').write_bytes(b'bar')
    (game / 'XEW/XComGame/CookedPCConsole/CIN_DropshipIntros.upk').write_bytes(b'intro')


class Play(unittest.TestCase):
    def setUp(self):
        running = installs.game_running
        self.addCleanup(setattr, installs, 'game_running', running)
        self.running = False
        installs.game_running = lambda: self.running
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        # LWR's own first mission: another map's record under the slot's DisplayName
        self.default = dep.set_field(record('liquorstore'), 'DisplayName', SLOT)
        self.lwr, self.copy = root / 'games' / 'LWR', root / 'games' / 'Copy'
        game_folder(self.lwr, self.default)
        game_folder(self.copy, self.default)
        self.output = root / 'builds'
        self.store = ProjectStore(root / 'projects')
        self.store.save(ID, document(output=dict(shipAs=VARIANT, patch='patch_' + VARIANT.lower())), 0)
        self.builds = BuildRunner(self.store, root / 'cache', self.output, command=lambda f: [sys.executable, '-c', ''])
        self.catalogue = dict(defaultMap='URB_Bar', maps=dict(URB_Bar=dict(id='URB_Bar', name='URB_Bar', root=root)))
        self.settings = dict(projects=root / 'projects', output=self.output, cache=root / 'cache', lwr=self.lwr,
                             install=None, udk=None, lab=None)
        # the user's Documents, with the game's own generated config in it
        self.documents = root / 'Documents'
        self.content = self.documents / 'My Games/XCOM - Enemy Within/XComGame/Config/XComContent.ini'
        self.content.parent.mkdir(parents=True)
        self.content.write_bytes(b'[XComGame.XComContentManager]\r\nthe game\'s own\r\n')
        self.started = []

    def player(self, install=None, **more):
        # cleanup off: these tests look at what a play installs, which a real play takes out again once the game has
        # closed (the tests of that pass cleanup=True)
        return Player(dict(self.settings, install=install), self.builds, self.catalogue, self.store,
                      start=lambda argv, cwd=None: self.started.append((argv, cwd)), steam=lambda: Path('steam.exe'),
                      user_documents=self.documents, **dict(dict(appear=0, every=0.01, cleanup=False), **more))

    def package(self, revision=1, quick=False, zones=None, ids=None, groups=None, maps=None, record_missions=None, exclusion=False):
        """A built package: the relit map, its cache and its own copy of the landing intro, streamed in its place; a
        quick build's has no cache. `zones`: the project's own landing-zone lines (config.landingZonesFromProject).
        `maps`: the Build's records (config.maps, text), with `record_missions` (config.recordMissions) when given."""
        folder = self.output / VARIANT
        (folder / 'CookedPCConsole').mkdir(parents=True, exist_ok=True)
        intro = f'CIN_DropshipIntros_{VARIANT}'
        files = {}
        for name, data in [(f'{VARIANT}.upk', b'relit map %d' % revision), ('Lighting_4242.tfc', b'lightmaps'),
                           (f'{intro}.upk', b'intro copy')]:
            if quick and name.endswith('.tfc'): continue
            (folder / 'CookedPCConsole' / name).write_bytes(data)
            files[f'CookedPCConsole/{name}'] = hashlib.sha256(data).hexdigest()
        m = dict(schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId=f'{VARIANT}-{revision}', builtAt='2026-11-08T12:00:00',
                 project=dict(id=ID, name='Bar remix', revision=revision), source=dict(map='URB_Bar', sha256='s' * 64),
                 variant=VARIANT, patch=None, files=files, streams=[], replaceStreams={'CIN_DropshipIntros': intro},
                 **({'quick': True} if quick else {}),
                 **({'config': dict(landingZones=zones, landingZonesFromProject=True, landingZoneIds=ids or [],
                                    **({'ownLandingGroups': groups} if groups else {}))} if zones is not None else {}))
        if exclusion:       # the project leaves scripted drop-ins where placed (build.drop_in_exclusion)
            m.setdefault('config', {})['dropInExclusion'] = dict(file='DefaultRandomSpawns.ini', section='XComLZMutator.XComSpawnAlienMutator',
                                                               line=f'ExcludeMaps = "{VARIANT}"')
        if maps is not None:
            m.setdefault('config', {}).update(maps=maps, missions=[missions.label(missions.kind_key(r)) for r in maps],
                                              **({'recordMissions': record_missions} if record_missions is not None else {}))
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')

    def files(self, game):
        return {n: (game / 'XEW/XComGame/Config' / n).read_bytes() for n in ('DefaultMaps.ini', 'DefaultLZMutator.ini')}

    def records(self, game, name):
        maps = dep.lines_of((game / 'XEW/XComGame/Config/DefaultMaps.ini').read_bytes())
        return [l for l in maps if dep.is_record(l) and dep.field(l, 'Name') == name]

    def settle(self, player):
        """Wait for the player's watch to end (the game 'closed')."""
        player.watching.join(timeout=10)
        self.assertFalse(player.watching.is_alive())

    def played(self, request):
        """A play by a player of its own, its watch ended before the next (two players' watches race each other on
        the kept files, which the server's one player never does)."""
        player = self.player()
        r = player.play(request)
        self.settle(player)
        return r

    def test_status_names_the_installs_and_how_the_game_starts(self):
        s = self.player().status()
        self.assertEqual((s['lwr']['folder'], s['install']['folder']), (str(self.lwr), str(self.lwr)))
        self.assertEqual((s['install']['source'], s['install']['sameAsLwr'], s['install']['ready']), ('the game install', True, True))
        self.assertEqual(s['launch'], dict(how='direct', why=None))           # a game folder in no Steam library
        self.assertEqual((s['game']['installed'], s['game']['intro'], s['game']['anything']), ([], None, False))
        s = self.player(self.copy).status()
        self.assertEqual((s['install']['folder'], s['install']['source'], s['install']['sameAsLwr']), (str(self.copy), 'the install setting', False))
        s = self.player(self.copy.parent / 'Nowhere').status()
        self.assertFalse(s['install']['ready'])
        self.assertIn('not a game folder', s['install']['why'])

    def test_a_map_of_the_games_plays_with_nothing_installed(self):
        before = self.files(self.lwr)
        player = self.player()
        r = player.play(dict(map='URB_Bar'))
        # these players have no test squad (test_squad_play.py plays with one): the game's own lands
        self.assertEqual((r['played']['kind'], r['played']['map'], r['played']['how'], r['played']['squad']), ('map', 'URB_Bar', 'direct', None))
        self.assertEqual(self.files(self.lwr), before)                         # no config line changed
        exe = self.lwr / 'XEW/Binaries/Win32/XComEW.exe'
        self.assertEqual(self.started, [([str(exe), f'-EXEC={installs.PLAY_FILE}'], exe.parent)])
        lines = (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii').split('\n')
        self.assertEqual((lines[0], lines[-2], lines[-1]), ('set XComContentManager bAllowJITLoad True', 'open URB_Bar', ''))
        self.assertEqual(lines[1], 'set XComOnlineProfileSettingsDataBlob m_eAlienType eChar_Sectoid')
        self.assertEqual(len(lines), 4)                                      # no squad line
        self.settle(player)
        self.assertEqual(player.status()['game']['lastPlay']['map'], 'URB_Bar')
        with self.assertRaises(ProjectError) as error: player.play(dict(map='Nowhere'))
        self.assertEqual(error.exception.status, 404)
        # Remove from game: the commands file goes, and nothing else was there
        done = player.remove()['removed']
        self.assertEqual((done['playFile'], done['records'], done['files']), (True, 0, []))
        self.assertFalse((self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).exists())
        self.assertFalse(player.status()['game']['anything'])

    def test_a_play_names_the_build_it_means_and_another_build_is_not_started(self):
        """Review finding 10: the play request names the build the page showed (buildId) or asked for (attempt),
        checked under the package's guard; a package swapped in since starts nothing and says which build is there."""
        player = self.player()
        self.package(revision=1)
        manifest = self.output / VARIANT / 'manifest.json'
        m = json.loads(manifest.read_text(encoding='utf-8'))
        manifest.write_text(json.dumps(dict(m, attempt='attempt-1')), encoding='utf-8')
        # another build lands after the page showed revision 1's
        self.package(revision=2)
        for request in (dict(project=ID, buildId=f'{VARIANT}-1'), dict(project=ID, attempt='attempt-1')):
            with self.assertRaises(ProjectError) as error: player.play(request)
            self.assertEqual((error.exception.status, error.exception.extra['buildId']), (409, f'{VARIANT}-2'))
            self.assertIn('another build now', error.exception.message)
        self.assertEqual(self.started, [])
        self.assertEqual(self.records(self.lwr, VARIANT), [])
        for bad in (dict(project=ID, buildId=3), dict(map='URB_Bar', buildId='x')):
            with self.assertRaises(ProjectError) as error: player.play(bad)
            self.assertEqual(error.exception.status, 400)
        r = player.play(dict(project=ID, buildId=f'{VARIANT}-2'))
        self.assertEqual(r['played']['project']['revision'], 2)
        self.settle(player)

    def test_a_project_gets_a_record_of_its_own_and_comes_out_byte_for_byte(self):
        before = self.files(self.lwr)
        player = self.player()
        with self.assertRaises(ProjectError) as error: player.play(dict(project=ID))
        self.assertIn('build the project first', error.exception.message)
        self.assertEqual(self.started, [])
        self.package()
        r = player.play(dict(project=ID))
        self.assertEqual((r['played']['map'], r['played']['project']['revision'], r['played']['quick']), (VARIANT, 1, False))
        self.assertEqual(self.started[-1][0][1], f'-EXEC={installs.PLAY_FILE}')
        self.assertIn(f'open {VARIANT}\n', (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii'))
        # a record of its own after Bar's, out of rotation, streaming its own copy of the landing intro
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        mine, = self.records(self.lwr, VARIANT)
        at = maps.index(mine)
        self.assertEqual(maps[at - 2], record('bar'))
        self.assertTrue(maps[at - 1].startswith(b'; ' + VARIANT.encode()))
        self.assertEqual((dep.field(mine, 'DisplayName'), dep.unquoted(mine, 'bInRotation'), dep.unquoted(mine, 'MissionType')),
                         (f'{VARIANT} (XCOM Map Workshop) |0', 'False', 'eMission_Abduction'))
        self.assertIn(f'CIN_DropshipIntros_{VARIANT}', dep.slot_streams(mine))
        self.assertNotIn('CIN_DropshipIntros', dep.slot_streams(mine))
        # the game's own lines are untouched: its first mission, and Bar's record
        self.assertEqual(dep.test_slot(self.lwr), self.default)
        self.assertEqual([l for l in maps if l not in maps[at - 1:at + 1]], dep.lines_of(before['DefaultMaps.ini']))
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        self.assertEqual((cooked / f'{VARIANT}.upk').read_bytes(), b'relit map 1')
        self.assertIn(f'MapName="{VARIANT}"'.encode(), self.files(self.lwr)['DefaultLZMutator.ini'])
        self.assertEqual([i['project']['name'] for i in r['game']['installed']], ['Bar remix'])
        # what the editor reads of the install is the game's own: the variant is no map, and Bar has its one record
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        self.assertNotIn(VARIANT, maplist.lwr_maps(self.lwr))
        self.assertEqual(len(maplist.lwr_maps(self.lwr)['URB_Bar']['missions']), 1)
        # a rebuild installs over the earlier one; a quick build's installs as any other, and the record says quick
        self.settle(player)
        self.package(revision=2, quick=True)
        r = player.play(dict(project=ID))
        self.assertTrue(r['played']['quick'] and r['game']['installed'][0]['quick'])
        self.assertEqual((cooked / f'{VARIANT}.upk').read_bytes(), b'relit map 2')
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 1)
        self.assertEqual(self.files(self.lwr)['DefaultLZMutator.ini'].count(f'MapName="{VARIANT}"'.encode()), 1)
        self.assertTrue((self.lwr / 'XCOM Map Workshop' / 'installs.json').is_file())      # the record lives in the install
        self.settle(player)
        done = player.remove()['removed']
        self.assertEqual((done['records'], done['landingZones'], sorted(done['files']), done['playFile'], done['intro']),
                         (1, 1, sorted(['Lighting_4242.tfc', f'{VARIANT}.upk', f'CIN_DropshipIntros_{VARIANT}.upk']), True, False))
        self.assertEqual(self.files(self.lwr), before)
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())
        self.assertFalse(any(player.remove()['removed'][k] for k in ('records', 'landingZones', 'files', 'playFile')))

    def build_line(self, base_line, label):
        """A record as the Build writes it for the variant (build.config_lines): renamed, out of rotation, its own
        landing intro streamed in place of the original."""
        line = dep.set_field(base_line, 'Name', VARIANT)
        line = dep.set_field(line, 'DisplayName', missions.display_name(dep.field(base_line, 'DisplayName'), VARIANT,
                                                                        f'Bar remix, {label}', ' |0'))
        line = dep.set_field(line, 'bInRotation', 'False', quoted=False)
        return line.replace(b'MapName="CIN_DropshipIntros"', f'MapName="CIN_DropshipIntros_{VARIANT}"'.encode()).decode('latin-1')

    def two_missions(self, game):
        """Bar with an abduction and a council bomb record in `game`'s DefaultMaps.ini, the bomb's stream in its
        packages."""
        (game / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join(
            [b'[XComGame.XComMapManager]', record('bar'), bomb_record(), self.default, b'']))
        (game / 'XEW/XComGame/CookedPCConsole/URB_Slaughterhouse_Stream.upk').write_bytes(b'bomb stream')

    def test_a_project_plays_the_mission_picked_with_the_builds_own_record(self):
        self.two_missions(self.lwr)
        before = self.files(self.lwr)
        lines = [self.build_line(record('bar'), 'Abduction'), self.build_line(bomb_record(), 'Council bomb')]
        self.package(maps=lines, record_missions=[[0], [1]])
        player = self.player()
        r = player.play(dict(project=ID, mission=1))
        # the Build's own line for the bomb, byte for byte: its kind, council type and streams, no abduction rewrite
        mine, = self.records(self.lwr, VARIANT)
        self.assertEqual(mine, lines[1].encode('latin-1'))
        self.assertEqual((dep.unquoted(mine, 'MissionType'), dep.unquoted(mine, 'CouncilType')), ('eMission_Special', 'eFCMType_Bomb'))
        self.assertEqual(dep.field(mine, 'DisplayName'), f'{VARIANT}_Bomb (Bar remix, Council bomb) |0')    # Long War's _Bomb kept
        self.assertIn('URB_Slaughterhouse_Stream', dep.slot_streams(mine))
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        self.assertTrue(maps[maps.index(mine) - 1].startswith(f"; {VARIANT}: the build's Council bomb record, out of rotation".encode()))
        m = r['played']['mission']
        self.assertEqual((m['id'], m['label'], m['kind'], m['state']), (1, 'Council bomb', 'Special/Bomb', 'works'))
        self.assertEqual(m['notes'], [missions.PODS_NOTE])
        self.assertNotIn('record', r['played'])
        self.assertEqual(r['game']['installed'][0]['mission'], dict(id=1, label='Council bomb'))
        text = (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii')
        self.assertTrue(text.endswith(f'\nopen {VARIANT}\n'))
        # absent, the first: the abduction's line
        r = player.play(dict(project=ID))
        mine, = self.records(self.lwr, VARIANT)
        self.assertEqual((mine, r['played']['mission']['label']), (lines[0].encode('latin-1'), 'Abduction'))
        # a mission the build hasn't, or no mission at all
        for bad, status in ((5, 409), ('TerrorSite', 409), (-1, 400), (True, 400), ('a kind?', 400)):
            with self.assertRaises(ProjectError) as error: player.play(dict(project=ID, mission=bad))
            self.assertEqual(error.exception.status, status, bad)
        self.assertIn('build it again', self._refused(player, 5))
        done = player.remove()['removed']
        self.assertEqual(done['records'], 1)
        self.assertEqual(self.files(self.lwr), before)
        # a build from before the manifest named them: one Build record per base record, picked by its index
        self.package(maps=lines)
        player.play(dict(project=ID, mission=1))
        self.assertEqual(self.records(self.lwr, VARIANT), [lines[1].encode('latin-1')])
        player.remove()
        # with no records in the manifest: the base map's record at that index, under the variant's name, of its kind
        self.package()
        player.play(dict(project=ID, mission=1))
        mine, = self.records(self.lwr, VARIANT)
        self.assertEqual((dep.unquoted(mine, 'MissionType'), dep.field(mine, 'DisplayName')),
                         ('eMission_Special', f'{VARIANT}_Bomb (XCOM Map Workshop) |0'))
        player.remove()
        self.assertEqual(self.files(self.lwr), before)

    def _refused(self, player, mission):
        try: player.play(dict(project=ID, mission=mission))
        except ProjectError as error: return error.message
        return ''

    def test_a_map_plays_the_mission_picked_from_a_copy_ahead_of_its_own(self):
        self.two_missions(self.lwr)
        before = self.files(self.lwr)
        player = self.player(cleanup=True, appear=30)
        # its first record: nothing installed, the game finds it anyway
        r = player.play(dict(map='URB_Bar', mission=0))
        self.assertEqual(self.files(self.lwr), before)
        self.assertEqual((r['played']['mission']['label'], r['played']['mission']['state']), ('Abduction', 'works'))
        self.close_game(player)
        # the bomb: an exact copy of its record, out of rotation, ahead of Bar's own (the game takes the first by name)
        r = player.play(dict(map='URB_Bar', mission=1))
        bar = self.records(self.lwr, 'URB_Bar')
        self.assertEqual(bar, [bomb_record(), record('bar'), bomb_record()])
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        at = maps.index(record('bar'))
        self.assertTrue(maps[at - 2].startswith(b'; URB_Bar: a copy of its Council bomb record for a play of that mission'))
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])     # the editor reads its own
        self.assertEqual(r['played']['mission']['label'], 'Council bomb')
        self.assertEqual((r['played']['recordCopy'], r['played'].get('note')), ('ahead', None))
        self.close_game(player)
        self.assertEqual(self.files(self.lwr), before)
        # an abduction in rotation gets a copy out of rotation; the next play of the first record takes it out again
        quiet = self.player()
        (self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join(
            [b'[XComGame.XComMapManager]', bomb_record(), record('bar'), self.default, b'']))
        before = self.files(self.lwr)
        quiet.play(dict(map='URB_Bar', mission=1))
        first = self.records(self.lwr, 'URB_Bar')[0]
        self.assertEqual(first, dep.set_field(record('bar'), 'bInRotation', 'False', quoted=False))
        quiet.play(dict(map='URB_Bar', mission=0))
        self.assertEqual(self.files(self.lwr), before)
        for bad, status in ((2, 409), ('TerrorSite', 400), (-1, 400)):
            with self.assertRaises(ProjectError) as error: quiet.play(dict(map='URB_Bar', mission=bad))
            self.assertEqual(error.exception.status, status, bad)
        quiet.remove()
        self.assertEqual(self.files(self.lwr), before)

    def test_the_commands_follow_the_mission_and_untried_ones_wait(self):
        self.two_missions(self.lwr)
        terror = dep.set_field(dep.set_field(record('bar'), 'MissionType', 'eMission_TerrorSite', quoted=False),
                               'DisplayName', 'URB_Bar (Terror) |0')
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(maps.read_bytes().replace(bomb_record(), bomb_record() + dep.EOL + terror))
        (self.lwr / 'XEW/XComGame/Config/DefaultContent.ini').write_text(CONTENT, encoding='latin-1', newline='\r\n')
        play_file = self.lwr / 'XEW/Binaries' / installs.PLAY_FILE
        civilians = ('set XComOnlineProfileSettingsDataBlob m_kCivilianContent '
                     '(iPawn=28,MaleBodies=(4,6,8),MaleHeads=(70,72,70),MaleHairs=(19,19,19),'
                     'FemaleBodies=(11,12),FemaleHeads=(73,73),FemaleHairs=(1,1))')
        # played and working (EXP-53 run 6, F-107): a terror play always gets the civilians' looks
        r = self.played(dict(map='URB_Bar', mission=2))
        self.assertEqual(play_file.read_text(encoding='ascii').split('\n')[-3:], [civilians, 'open URB_Bar', ''])
        self.assertEqual((r['played']['mission']['missing'], r['played']['mission']['words']), ([], ''))
        # an install whose DefaultContent.ini gives no looks: the play goes without them and says so
        content = self.lwr / 'XEW/XComGame/Config/DefaultContent.ini'
        content.write_text('[XComGame.XComContentManager]\n', encoding='latin-1', newline='\r\n')
        r = self.played(dict(map='URB_Bar', mission=2))
        self.assertTrue(play_file.read_text(encoding='ascii').endswith('\nopen URB_Bar\n'))
        self.assertEqual(r['played']['mission']['missing'], [missions.LINES['civilians']['missing']])
        self.assertIn('never leaves the loading screen', r['played']['mission']['missing'][0])
        content.write_text(CONTENT, encoding='latin-1', newline='\r\n')
        r = self.played(dict(map='URB_Bar', mission=0))
        self.assertEqual(r['played']['mission']['missing'], [])     # abductions play and work without the option
        self.assertIn('?Meld=1', missions.play_setup('MissionType=eMission_LandedUFO')['missing'][0])
        self.assertEqual(missions.play_setup('MissionType=eMission_Crash')['missing'], [])     # played and working
        # tried (serve --try-mission-lines): the open line's options too
        player = self.player(try_lines=True)
        self.assertTrue(player.status()['tryMissionLines'])
        r = player.play(dict(map='URB_Bar', mission=2))
        self.settle(player)
        text = play_file.read_text(encoding='ascii').split('\n')
        self.assertEqual((text[-3], text[-2], r['played']['mission']['missing']), (civilians, 'open URB_Bar', []))
        player.play(dict(map='URB_Bar', mission=0))
        self.assertEqual(play_file.read_text(encoding='ascii').split('\n')[-2], 'open URB_Bar?Meld=1')
        # the page's table of kinds
        kinds = player.status()['missionKinds']
        self.assertEqual((kinds['Abduction']['state'], kinds['TerrorSite']['words'], kinds['Special/Bomb']['group']),
                         ('works', '', 'council'))
        self.assertEqual(self.player().status()['missionKinds']['TerrorSite']['missing'], [])
        status = self.player().status()['missionKinds']
        # the dialog says a kind's state only for a problem: never that it is untried, or that it was tried (16
        # November 2026)
        self.assertEqual((status['Special/Bomb']['words'], status['Special/Assault']['words']), ('', ''))
        self.assertEqual((status['Special/Bomb']['state'], status['Special/Assault']['state']), ('works', 'untried'))
        # EXALT battles: LWR saves and reloads them as they start (F-109), so their plays have saving on (EXP-57 run 2
        # played a data recovery that way), and their pods are EXALT's; a UFO gets no commander (F-110)
        exalt = status['CaptureAndHold']
        self.assertEqual((exalt['state'], exalt['words'], exalt['saving']),
                         ('works', '', missions.SAVING_WHY))
        self.assertEqual(exalt['notes'], [missions.EXALT_PODS_NOTE, missions.OPERATIVE_NOTE])
        self.assertEqual((status['CovertOpsExtraction']['words'], status['ExaltRaid']['notes']),
                         ('', [missions.EXALT_PODS_NOTE]))
        self.assertIsNone(status['Abduction']['saving'])
        self.assertEqual(player.status()['saveKey'], gamelaunch.SAVE_KEY)
        self.assertEqual(status['Crash']['notes'], [missions.PODS_NOTE, missions.COMMANDER_NOTE])
        self.assertEqual(status['TerrorSite']['notes'], [missions.TERROR_PODS_NOTE])
        self.assertEqual(status['MPDeathmatch']['notes'], [missions.KINDS['MPDeathmatch']['note']])
        self.settle(player)             # (a remove while the play's watch puts files back races it)
        player.remove()

    def test_saving_starts_the_game_at_its_main_menu_and_a_key_opens_the_battle(self):
        """F-89, EXP-56: a battle opened after the main menu's login can be saved. With saving on the game starts on a
        commands file that binds the key to the play's commands and opens nothing; the input settings (the binding)
        and the profile (the logged-in game writes the play's squad into it) are kept aside and put back."""
        play_file, start_file = installs.play_file(self.lwr), installs.start_file(self.lwr)
        config = self.documents / 'My Games/XCOM - Enemy Within/XComGame/Config'
        save_data = self.documents / 'My Games/XCOM - Enemy Within/XComGame/SaveData'
        save_data.mkdir(parents=True)
        (config / 'XComInput.ini').write_bytes(b'[Engine.PlayerInput]\r\nBindings=(Name="F9",Command="shot")\r\n')
        (save_data / 'profile.bin').write_bytes(b'the user\'s profile')
        own = {p: p.read_bytes() for p in (config / 'XComInput.ini', save_data / 'profile.bin')}
        player = self.player(cleanup=True, appear=5)

        def start(argv, cwd=None):      # the game comes up, binds the key, logs in and writes the profile
            self.started.append((argv, cwd))
            self.running = True
            (config / 'XComInput.ini').write_bytes(b'[XComUIShell.XComShellInput]\r\nBindings=(Name="F5",Command="exec ...")\r\n')
            (save_data / 'profile.bin').write_bytes(b'the profile with the test squad in it')
            (self.lwr / 'XEW/XComGame/SaveData').mkdir(parents=True, exist_ok=True)
            (self.lwr / 'XEW/XComGame/SaveData/profile.bin').write_bytes(b'a profile the game made in its folder')
        player.start = start
        r = player.play(dict(map='URB_Bar', saving=True))
        self.assertEqual(r['played']['saving'], dict(key='F5', forced=None))
        self.assertEqual(self.started[-1][0][-1], f'-EXEC={installs.START_FILE}')
        self.assertEqual(start_file.read_text(encoding='ascii'), f'setbind F5 exec {installs.PLAY_FILE}\n')
        self.assertTrue(play_file.read_text(encoding='ascii').endswith('\nopen URB_Bar\n'))
        self.assertTrue(player.status()['game']['play'])
        self.running = False
        self.settle(player)
        # closed: the binding and the profile as they were, the profile the game made in its folder gone, and the
        # commands files gone with the rest of the play
        self.assertEqual({p: p.read_bytes() for p in own}, own)
        self.assertFalse((self.lwr / 'XEW/XComGame/SaveData/profile.bin').exists())
        self.assertFalse(play_file.exists() or start_file.exists())
        # saving off: the play's own file starts the game, and no start file
        player.start = lambda argv, cwd=None: self.started.append((argv, cwd))
        quiet = self.player()
        quiet.start = player.start
        r = quiet.play(dict(map='URB_Bar'))
        self.assertIsNone(r['played']['saving'])
        self.assertEqual(self.started[-1][0][-1], f'-EXEC={installs.PLAY_FILE}')
        self.assertFalse(start_file.exists())
        self.settle(quiet)
        with self.assertRaises(ProjectError) as error: quiet.play(dict(map='URB_Bar', saving='yes'))
        self.assertEqual(error.exception.status, 400)
        # an EXALT mission under Long War has saving on whatever is asked (F-109)
        exalt = dep.set_field(dep.set_field(record('bar'), 'MissionType', 'eMission_CaptureAndHold', quoted=False),
                              'DisplayName', 'URB_Bar (Data recovery) |0')
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(maps.read_bytes().replace(record('bar'), record('bar') + dep.EOL + exalt))
        r = quiet.play(dict(map='URB_Bar', mission=1))
        self.assertEqual(r['played']['saving'], dict(key='F5', forced=missions.SAVING_WHY))
        self.assertEqual(self.started[-1][0][-1], f'-EXEC={installs.START_FILE}')
        # its pods are EXALT's (EXP-57 run 2 had Sectoids): the commands set the profile's alien type to an operative
        commands = play_file.read_text(encoding='ascii').split('\n')
        self.assertIn(f'set XComOnlineProfileSettingsDataBlob m_eAlienType {missions.EXALT_ALIENS}', commands)
        self.assertNotIn(f'set XComOnlineProfileSettingsDataBlob m_eAlienType {gamelaunch.ALIENS}', commands)
        self.assertTrue(start_file.is_file())
        self.settle(quiet)              # (a reset while the play's watch runs races it)
        installs.reset(self.lwr)
        self.assertFalse(play_file.exists() or start_file.exists())
        # plain Enemy Within doesn't save and reload EXALT battles: nothing forced there
        self.assertIsNone(missions.play_setup('MissionType=eMission_CaptureAndHold', lwr=False)['saving'])
        self.assertEqual(missions.play_setup('MissionType=eMission_ExaltRaid', lwr=True)['saving'], missions.SAVING_WHY)

    def test_a_variant_of_the_intro_map_installs_and_comes_out_byte_for_byte(self):
        # Act1_IntroLevel's records are both commented out (maplist.SWITCHED_OFF): Launch's test has the record
        intro_variant = 'Act1_IntroLevel_Remix_0f8b'
        lines = [b'[XComGame.XComMapManager]', record('bar'), record('intro_abduction'), record('intro_tutorial'), b'']
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(dep.EOL.join(lines[:-1] + [self.default, b'']))
        before = self.files(self.lwr)
        folder = self.output / intro_variant
        (folder / 'CookedPCConsole').mkdir(parents=True)
        (folder / 'CookedPCConsole' / f'{intro_variant}.upk').write_bytes(b'intro remix')
        m = dict(schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId=f'{intro_variant}-1', builtAt='2026-11-10T12:00:00',
                 project=dict(id=ID, name='Intro remix', revision=1), source=dict(map='Act1_IntroLevel', sha256='s' * 64),
                 variant=intro_variant, patch=None, streams=[], replaceStreams={},
                 files={f'CookedPCConsole/{intro_variant}.upk': hashlib.sha256(b'intro remix').hexdigest()})
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        installs.install_package(self.lwr, folder)
        now = dep.lines_of(maps.read_bytes())
        mine, = self.records(self.lwr, intro_variant)
        self.assertEqual(now.index(mine), 4)
        self.assertEqual(now[2], record('intro_abduction'))
        self.assertEqual(self.records(self.lwr, 'Act1_IntroLevel'), [])       # no live record for the map itself
        self.assertIn('Act1_IntroLevel', maplist.lwr_maps(self.lwr))
        self.assertNotIn(intro_variant, maplist.lwr_maps(self.lwr))
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)

    def test_the_tutorial_map_alone_plays_with_a_copy_of_its_commented_out_record(self):
        # opened with no record the game crashed (EXP-30 run 1): a play of the map alone puts a live copy of its
        # abduction record in, out of rotation, after the commented-out one; Remove from game takes it out
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', record('bar'), record('intro_abduction'),
                                       record('intro_tutorial'), self.default, b'']))
        (self.lwr / 'XEW/XComGame/CookedPCConsole/Act1_IntroLevel.upk').write_bytes(b'intro')
        self.catalogue['maps']['Act1_IntroLevel'] = dict(id='Act1_IntroLevel', name='Act1_IntroLevel')
        before = self.files(self.lwr)
        player = self.player()
        r = player.play(dict(map='Act1_IntroLevel'))
        self.assertEqual(r['played']['recordCopy'], 'live')
        self.assertIn('open Act1_IntroLevel\n', (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii'))
        now = dep.lines_of(maps.read_bytes())
        mine, = self.records(self.lwr, 'Act1_IntroLevel')
        self.assertEqual(now.index(mine), 4)                                  # after the commented-out abduction
        self.assertTrue(now[3].startswith(b'; Act1_IntroLevel: its commented-out record'))
        self.assertEqual(mine, record('intro_abduction')[1:].replace(b'bInRotation=True', b'bInRotation=False'))
        self.assertEqual([i['kind'] for i in r['game']['installed']], ['map'])
        # what the editor reads of the install is still the install's own
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        self.assertEqual(len(maplist.lwr_maps(self.lwr)['Act1_IntroLevel']['missions']), 1)
        # a second play keeps one copy
        self.settle(player)
        player.play(dict(map='Act1_IntroLevel'))
        self.assertEqual(len(self.records(self.lwr, 'Act1_IntroLevel')), 1)
        # a map with a record of its own still installs nothing
        self.settle(player)
        self.assertNotIn('note', player.play(dict(map='URB_Bar'))['played'])
        self.settle(player)
        done = player.remove()['removed']
        self.assertEqual(done['records'], 1)
        self.assertEqual(self.files(self.lwr), before)

    def test_a_patchtool_record_of_the_variant_is_stood_in_for_and_put_back(self):
        # the lab's patchtool deploy of an earlier test of the project left a record of the variant (with landing zones)
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        theirs = dep.set_field(dep.set_field(record('bar'), 'Name', VARIANT), 'DisplayName', f'{VARIANT} (Bar remix) |0')
        comment = f"; {VARIANT}: URB_Bar's record under its own name, streaming patch_x in StreamingMaps[2] (patchtool, 6 Nov 2026)".encode()
        lines = dep.lines_of(maps.read_bytes())
        lines[2:2] = [comment, theirs]
        maps.write_bytes(dep.EOL.join(lines))
        lz = self.lwr / 'XEW/XComGame/Config/DefaultLZMutator.ini'
        lz.write_bytes(lz.read_bytes() + f'LZArray=(MapName="{VARIANT}",StartLoc=(X=1,Y=2,Z=3))'.encode() + dep.EOL)
        before = self.files(self.lwr)
        player = self.player()
        self.package()
        r = player.play(dict(project=ID))
        self.assertEqual(r['played']['map'], VARIANT)
        # the editor's record in its place, nothing else changed; the landing zones there already are kept as they are
        now = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        mine, = self.records(self.lwr, VARIANT)
        self.assertEqual(now.index(mine), 3)
        self.assertTrue(now[2].startswith(f'; {VARIANT}: URB_Bar\'s Abduction record under its own name, out of rotation (XCOM Map Workshop'.encode()))
        self.assertEqual(now[:2] + now[4:], lines[:2] + lines[4:])
        self.assertEqual(self.files(self.lwr)['DefaultLZMutator.ini'], before['DefaultLZMutator.ini'])
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        # a rebuild stands in for it again; Remove from game puts patchtool's record back byte for byte
        self.settle(player)
        self.package(revision=2)
        player.play(dict(project=ID))
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 1)
        self.settle(player)
        self.assertEqual(player.remove()['removed']['records'], 1)
        self.assertEqual(self.files(self.lwr), before)
        # a record of the variant that patchtool's comment doesn't vouch for is still refused
        lines[2] = b'; someone else'
        maps.write_bytes(dep.EOL.join(lines))
        with self.assertRaises(ProjectError) as error: player.play(dict(project=ID))
        self.assertIn('neither the editor nor patchtool wrote', error.exception.message)

    def test_the_projects_own_landing_zones_go_in_and_come_out_byte_for_byte(self):
        """Clear map plan, step C7: a project that set its landing zones installs its own lines, not a copy of the
        base map's."""
        before = self.files(self.lwr)
        player = self.player()
        lines = ['LZArray=(MapName="%s",ESpawnLoc=ESL_Normal,StartLoc=(X=1103,Y=1583,Z=64),StartDir=ELZD_East)' % VARIANT,
                 'LZArray=(MapName="%s",ESpawnLoc=ESL_Inside,StartLoc=(X=0,Y=0,Z=64),StartDir=ELZD_North)' % VARIANT]
        self.package(zones=lines)
        player.play(dict(project=ID))
        lz = dep.lines_of(self.files(self.lwr)['DefaultLZMutator.ini'])
        mine = [l for l in lz if f'MapName="{VARIANT}"'.encode() in l]
        self.assertEqual(mine, [l.encode() for l in lines])
        # after Bar's line, under a note of its own; Bar's own line is untouched and not copied
        at = lz.index(mine[0])
        self.assertIn(b'URB_Bar', lz[at - 2])
        self.assertTrue(lz[at - 1].startswith(b';' + VARIANT.encode()))
        self.settle(player)
        self.assertEqual(player.remove()['removed']['landingZones'], 1)
        self.assertEqual(self.files(self.lwr), before)
        # an empty list writes no line
        self.package(revision=2, zones=[])
        player.play(dict(project=ID))
        self.assertNotIn(f'MapName="{VARIANT}"'.encode(), self.files(self.lwr)['DefaultLZMutator.ini'])
        self.settle(player)
        player.remove()
        self.assertEqual(self.files(self.lwr), before)

    def test_a_projects_drop_in_rule_goes_in_with_the_play_and_comes_out_byte_for_byte(self):
        """Editor spawns plan, SP8: a package whose project leaves scripted drop-ins where placed adds the variant to Long
        War's ExcludeMaps list for a play, after the drop-in section's ExcludeMaps lines and under a note naming the
        editor and the project; removing takes it out byte for byte; a campaign install takes a play's line over; a
        rebuild installed again adds no second line. Without the drop-in mutator nothing is written, and the play says
        why."""
        import manager
        import spawnrules
        config = self.lwr / 'XEW/XComGame/Config'
        (config / 'DefaultMutatorLoader.ini').write_bytes(MUTATOR_LOADER)
        rs = config / 'DefaultRandomSpawns.ini'
        rs.write_bytes(RANDOM_SPAWNS)
        before, maps = rs.read_bytes(), self.files(self.lwr)
        self.package(exclusion=True)
        player = self.player()
        r = player.play(dict(project=ID))
        self.assertEqual(r['played']['dropInExclusion'], dict(written=True))
        lines = dep.lines_of(rs.read_bytes())
        at = lines.index(f'ExcludeMaps = "{VARIANT}"'.encode())
        self.assertEqual(lines[at - 2], b';ExcludeMaps = "DLC2_2_Deluge"')
        self.assertTrue(lines[at - 1].startswith(f';{VARIANT}: scripted drop-ins land where placed (XCOM Map Workshop'.encode()), lines[at - 1])
        self.assertIn(b'project Bar remix', lines[at - 1])
        self.assertTrue(spawnrules.excluded(spawnrules.random_spawns(rs.read_bytes())['excludeMaps'], VARIANT))
        self.assertEqual([b['variant'] for b in installs.read_ledger(self.lwr)['playExclusions']], [VARIANT])
        self.settle(player)
        self.assertEqual(player.remove()['removed']['dropInExclusions'], 1)
        self.assertEqual(rs.read_bytes(), before)
        self.assertEqual(self.files(self.lwr), maps)
        # played, then installed for campaigns: the play's line is the campaign's; a rebuild played adds none
        quiet = self.player()
        quiet.play(dict(project=ID))
        self.settle(quiet)
        manager.install(self.store, self.builds, quiet, dict(projects=[ID], mode='additional'))
        ledger = installs.read_ledger(self.lwr)
        self.assertEqual(([b['variant'] for b in ledger.get('dropInExclusions') or []], ledger.get('playExclusions')), ([VARIANT], []))
        self.assertEqual(installs.clear_play(self.lwr)['dropInExclusions'], 0)
        self.package(revision=2, exclusion=True)
        r = quiet.play(dict(project=ID))
        self.assertEqual(r['played']['dropInExclusion'], dict(written=False))
        self.assertEqual(rs.read_bytes().count(f'ExcludeMaps = "{VARIANT}"'.encode()), 1)
        self.settle(quiet)
        installs.reset(self.lwr)
        self.assertEqual(rs.read_bytes(), before)
        # the loader without the drop-in mutator: nothing written, and why
        (config / 'DefaultMutatorLoader.ini').write_bytes(b'[XComMutator.XComMutatorLoader]\r\n')
        r = player.play(dict(project=ID))
        self.assertFalse(r['played']['dropInExclusion']['written'])
        self.assertIn('no drop-in mutator', r['played']['dropInExclusion']['why'])
        self.assertEqual(rs.read_bytes(), before)
        self.settle(player)
        player.remove()

    def test_land_here_installs_one_zone_and_names_its_spawn_group(self):
        """Clear map plan, step C7: Play in game with one landing zone: under LWR its line alone; a zone that is one
        of the map's own landings opens the map with its spawn group."""
        player = self.player()
        lines = ['LZArray=(MapName="%s",ESpawnLoc=ESL_Normal,StartLoc=(X=1103,Y=1583,Z=64),StartDir=ELZD_East)' % VARIANT,
                 'LZArray=(MapName="%s",ESpawnLoc=ESL_Inside,StartLoc=(X=0,Y=0,Z=64),StartDir=ELZD_North)' % VARIANT]
        self.package(zones=lines, ids=['a', 'b'], groups=[dict(zone='a', index=0, group='Group0')])
        with self.assertRaises(ProjectError): player.play(dict(map='URB_Bar', zone='a'))
        r = player.play(dict(project=ID, zone='b'))
        lz = dep.lines_of(self.files(self.lwr)['DefaultLZMutator.ini'])
        self.assertEqual([l for l in lz if f'MapName="{VARIANT}"'.encode() in l], [lines[1].encode()])
        self.assertNotIn('?SpawnGroup', (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii'))
        self.settle(player)
        player.remove()
        r = player.play(dict(project=ID, zone='a'))
        self.assertEqual(r['played']['spawnGroup'], 'Group0')
        self.assertIn(f'open {VARIANT}?SpawnGroup=Group0' + chr(10), (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii'))
        self.settle(player)
        player.remove()

    def test_plain_ew_no_landing_zones_and_the_games_own_squad(self):
        plain = Path(self.temp.name) / 'games' / 'EW'
        game_folder(plain, dep.set_field(dep.set_field(record('bar'), 'Name', 'URB_Other'), 'DisplayName', 'URB_Other (plain)'), kind='ew')
        (plain / 'XEW/XComGame/Config/DefaultLZMutator.ini').unlink()
        maps = plain / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(maps.read_bytes().replace(b' |0"', b'"'))      # plain EW's names have no " |0"
        before = maps.read_bytes()
        self.settings['lwr'] = self.settings['game'] = plain
        player = self.player()
        self.package()
        r = player.play(dict(project=ID))
        self.assertFalse(r['played']['squad'])
        self.assertEqual((plain / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii'),
                         f'set XComContentManager bAllowJITLoad True\n'
                         f'set XComOnlineProfileSettingsDataBlob m_eAlienType eChar_Sectoid\nopen {VARIANT}\n')
        mine, = self.records(plain, VARIANT)
        self.assertEqual(dep.field(mine, 'DisplayName'), f'{VARIANT} (XCOM Map Workshop)')
        self.assertFalse((plain / 'XEW/XComGame/Config/DefaultLZMutator.ini').exists())
        self.settle(player)
        self.assertEqual(player.remove()['removed']['landingZones'], 0)
        self.assertEqual(maps.read_bytes(), before)

    def test_the_games_config_is_kept_aside_and_put_back_when_the_game_closes(self):
        own = self.content.read_bytes()
        player = self.player(appear=5)
        self.started = None      # the start stands in for the game: it comes up and writes its config

        def start(argv, cwd=None):
            self.running = True
            self.content.write_bytes(own + b'bAllowJITLoad=True\r\n')
        player.start = start
        player.play(dict(map='URB_Bar'))
        self.assertTrue(player.status()['game']['configKept'])
        self.assertTrue(player.watching.is_alive())
        self.assertNotEqual(self.content.read_bytes(), own)
        # while the game runs nothing is put back, and neither a play nor a removal goes ahead
        for change in (lambda: player.play(dict(map='URB_Bar')), player.remove):
            with self.assertRaises(ProjectError) as error: change()
            self.assertIn('XCOM is running', error.exception.message)
        self.running = False
        self.settle(player)
        self.assertEqual(self.content.read_bytes(), own)
        self.assertFalse(player.status()['game']['configKept'])
        self.assertEqual(list((self.lwr / 'XCOM Map Workshop' / 'play').iterdir()), [])
        # a file the game made during the play is taken away, so the game makes it afresh
        local = self.lwr / 'XEW/XComGame/Config/XComContent.ini'
        player.start = lambda argv, cwd=None: local.write_bytes(b'made during the play')
        player.play(dict(map='URB_Bar'))
        self.settle(player)
        self.assertFalse(local.exists())
        # a server that went away during a play: the next one puts the config back as it starts (recover); a look at
        # the install (GET /play.json) changes nothing (review finding 45)
        player.start = lambda argv, cwd=None: None
        installs.backup_config(self.lwr, gamelaunch.user_config(self.lwr, self.documents))
        self.content.write_bytes(b'changed by the game')
        fresh = self.player()
        self.assertTrue(fresh.status()['game']['configKept'])
        self.assertIsNone(fresh.watching)
        self.assertEqual(self.content.read_bytes(), b'changed by the game')
        self.assertTrue(fresh.recover())
        self.settle(fresh)
        self.assertEqual(self.content.read_bytes(), own)
        self.assertFalse(fresh.recover())       # nothing left: no watch

    def test_a_plays_saves_are_kept_apart_from_a_campaigns(self):
        """F-89: a battle started without the main menu's login writes its save to save1 whatever is there (EXP-53's
        EXALT runs), and broken: its 1 KB header again and again, then the data (EXP-56, the crash on loading it).
        With saving on the save is whole, in the slot after the highest, and stays."""
        def save(game, body, command=None, broken=False):
            def text(s):
                b = s.encode('latin-1') + b'\0'
                return struct.pack('<i', len(b)) + b
            command = command or ('open URB_Bar?game=XComGame.XComTacticalGame?' +
                                  ('LoadingFromShell=1?Meld=1' if game == 0 else 'LoadingFromStrategy=1'))
            head = struct.pack('<4i', 16, 0, game, 0) + text(f'Classic Game {game}') + text('11/15/2026 - 10:45') + \
                text(command)
            head += bytes(playsaves.HEADER - len(head))
            return head * (5 if broken else 1) + playsaves.PACKAGE_TAG + body
        mine, docs = self.lwr / 'XEW/XComGame/SaveData', self.documents / 'My Games/XCOM - Enemy Within/XComGame/SaveData'
        mine.mkdir(parents=True)
        docs.mkdir(parents=True)
        campaign1, old_play, campaign3 = save(7, b'campaign save one'), save(0, b'an older play'), save(7, b'three')
        old_broken = save(0, b'an older play, stuck', broken=True)
        (mine / 'save1').write_bytes(campaign1)
        (mine / 'save2').write_bytes(old_play)
        (mine / 'save3').write_bytes(campaign3)
        (mine / 'save999').write_bytes(old_broken)      # as the editor left one before broken saves were told
        strategy = save(7, b'at the base', 'open Command1?game=XComStrategyGame.XComHeadQuartersGame')
        (docs / 'save5').write_bytes(strategy)
        (mine / 'notes.txt').write_bytes(b'not a save')
        # the play's: without the main menu's login its save lands on save1, broken (F-89); with it (saving on) the
        # game gives the slot after the highest and the save is whole; one is saved over a campaign's from the menu
        stuck, logged_in = save(0, b'the play, stuck', broken=True), save(0, b'the play, logged in')
        over_three, docs_stuck = save(0, b'saved over the campaign\'s save 3'), save(0, b'in Documents', broken=True)
        later = save(9, b'a campaign loaded after the play and saved')
        aside = self.lwr / 'XCOM Map Workshop' / installs.BROKEN_SAVES
        player = self.player(appear=5)
        self.started = None

        def start(argv, cwd=None):      # the game comes up, and its saves land
            self.running = True
            (mine / 'save1').write_bytes(stuck)
            (mine / 'save4').write_bytes(logged_in)
            (mine / 'save3').write_bytes(over_three)
            (mine / 'save6').write_bytes(later)
            (docs / 'save1').write_bytes(docs_stuck)
        player.start = start
        player.play(dict(map='URB_Bar'))
        status = player.status()['game']
        self.assertTrue(status['savesKept'])
        # before the play: the older broken save set aside, the older whole play save left where it is, save1 to save9
        # copied aside
        self.assertEqual((mine / 'save2').read_bytes(), old_play)
        self.assertFalse((mine / 'save999').exists())
        self.assertEqual([p.read_bytes() for p in aside.iterdir()], [old_broken])
        self.running = False
        self.settle(player)
        # after it: the broken saves out of the game's folders and the campaign's save 1 back; the whole save in its new
        # slot left there; the one saved over save 3 moved to the slot after the highest and save 3 back; the rest as
        # they were
        self.assertEqual({p.name for p in mine.iterdir()}, {'save1', 'save2', 'save3', 'save4', 'save6', 'save7', 'notes.txt'})
        self.assertEqual([(mine / n).read_bytes() for n in ('save1', 'save2', 'save3', 'save4', 'save6', 'save7')],
                         [campaign1, old_play, campaign3, logged_in, later, over_three])
        self.assertEqual({p.name: p.read_bytes() for p in docs.iterdir()}, {'save5': strategy})
        self.assertEqual(sorted(p.read_bytes() for p in aside.iterdir()), sorted([old_broken, stuck, docs_stuck]))
        self.assertTrue(all(p.name.endswith('-save1') or p.name.endswith('-save999') for p in aside.iterdir()))
        status = player.status()['game']
        self.assertFalse(status['savesKept'])
        last = status['lastSaves']
        self.assertEqual([(m['name'], m['to']) for m in last['moved']], [('save3', 'save7')])
        self.assertEqual(sorted(m['name'] for m in last['setAside']), ['save1', 'save1'])
        self.assertEqual(sorted(r['name'] for r in last['restored']), ['save1', 'save3'])
        self.assertEqual(last['kept'], [])
        self.assertEqual([m['name'] for m in last['keptAside']], ['save999'])
        self.assertEqual(list((self.lwr / 'XCOM Map Workshop' / 'play').iterdir()), [])
        # a server that went away during a play: the next one sorts the saves as it starts (recover)
        installs.keep_saves(self.lwr, [mine])
        (mine / 'save1').write_bytes(save(0, b'made while no server watched', broken=True))
        fresh = self.player()
        self.assertTrue(fresh.status()['game']['savesKept'])
        self.assertTrue(fresh.recover())
        self.settle(fresh)
        self.assertEqual((mine / 'save1').read_bytes(), campaign1)
        self.assertEqual(len(list(aside.iterdir())), 4)

    def test_an_earlier_versions_intro_install_goes_back(self):
        # a ledger as Install as intro map left it: the slot line rewritten to Bar's record
        maps_path = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps = dep.lines_of(maps_path.read_bytes())
        at = dep.slot_index(maps, SLOT)
        written = dep.set_field(record('bar'), 'DisplayName', SLOT)
        before = maps_path.read_bytes()
        maps[at] = written
        maps_path.write_bytes(dep.EOL.join(maps))
        installs.write_ledger(self.lwr, dict(slot=dict(line=at + 1, original=self.default.decode('latin-1'), written=written.decode('latin-1'),
                                                       at='20261108-120000'), intro=dict(kind='map', map='URB_Bar')))
        player = self.player()
        self.assertEqual(player.status()['game']['intro'], dict(map='URB_Bar', ownMap='URB_LiquorStore'))
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before)      # read as the game's own meanwhile
        player.play(dict(map='URB_Bar'))
        self.assertEqual(maps_path.read_bytes(), before)
        self.assertIsNone(player.status()['game']['intro'])
        # and by Remove from game; a slot something else changed since is left
        self.settle(player)
        maps_path.write_bytes(dep.EOL.join(maps))
        installs.write_ledger(self.lwr, dict(installs.read_ledger(self.lwr), slot=dict(line=at + 1, original=self.default.decode('latin-1'),
                                                                                         written=written.decode('latin-1'), at='x')))
        self.assertTrue(player.remove()['removed']['intro'])
        self.assertEqual(maps_path.read_bytes(), before)
        maps[at] = dep.set_field(record('templeship'), 'DisplayName', SLOT)
        maps_path.write_bytes(dep.EOL.join(maps))
        installs.write_ledger(self.lwr, dict(installs.read_ledger(self.lwr), slot=dict(line=at + 1, original=self.default.decode('latin-1'),
                                                                                         written=written.decode('latin-1'), at='x')))
        done = player.remove()['removed']
        self.assertFalse(done['intro'])
        self.assertTrue(any('intro slot' in note for note in done['left']))

    def test_in_a_copy_the_game_install_is_untouched(self):
        player = self.player(self.copy)
        self.package()
        r = player.play(dict(project=ID))
        self.assertEqual(len(self.records(self.copy, VARIANT)), 1)
        self.assertEqual(self.files(self.lwr)['DefaultMaps.ini'].count(VARIANT.encode()), 0)
        self.assertEqual(Path(self.started[-1][0][0]).parents[3], self.copy)
        self.assertNotIn('note', r['played'])
        # a copy's map that differs from the game install's is said so
        self.settle(player)
        (self.copy / 'XEW/XComGame/CookedPCConsole/URB_Bar.upk').write_bytes(b'seeded bar')
        self.assertIn('differs', player.play(dict(map='URB_Bar'))['played']['note'])

    def test_what_changed_since_is_left_alone(self):
        player = self.player()
        self.package()
        player.play(dict(project=ID))
        self.settle(player)
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        (cooked / 'Lighting_4242.tfc').write_bytes(b'edited by hand')
        maps_path = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps_path.write_bytes(maps_path.read_bytes().replace(b'(XCOM Map Workshop)', b'(mine now)'))
        done = player.remove()['removed']
        self.assertTrue((cooked / 'Lighting_4242.tfc').exists())
        self.assertTrue(any('Lighting_4242.tfc' in note for note in done['left']))
        self.assertEqual((done['records'], len(self.records(self.lwr, VARIANT))), (0, 1))
        self.assertTrue(any('record for ' + VARIANT in note for note in done['left']))
        # a record of that name the editor didn't write: a build of the project isn't installed over it
        self.package(revision=3)
        with self.assertRaises(ProjectError) as error: player.play(dict(project=ID))
        self.assertIn('neither the editor nor patchtool wrote', error.exception.message)

    def snapshot(self, game):
        """The install's config files and every file of its CookedPCConsole with its bytes."""
        cooked = game / 'XEW/XComGame/CookedPCConsole'
        return self.files(game), {p.name: p.read_bytes() for p in cooked.iterdir()}

    def test_another_projects_variant_or_files_are_never_replaced(self):
        """Output names plan 3.4: a play's install and a campaign install check the whole package before anything is
        written; a variant installed for another project, a file the editor didn't put there (named in any case) and
        one changed since are refused, and the install is left exactly as it was."""
        self.package()
        folder, cooked = self.output / VARIANT, self.lwr / 'XEW/XComGame/CookedPCConsole'
        intro = f'CIN_DropshipIntros_{VARIANT}.upk'
        cases = [
            ('another project\'s variant', 'for another project',
             lambda: installs.write_ledger(self.lwr, dict(installed={VARIANT: dict(kind='project', map=VARIANT, project=dict(id=OTHER))}))),
            ('a file of the map\'s name in another case', 'didn\'t put it there',
             lambda: (cooked / f'{VARIANT.lower()}.upk').write_bytes(b'by hand')),
            ('an intro copy put there by hand', 'didn\'t put it there', lambda: (cooked / intro).write_bytes(b'by hand')),
            ('a file installed for another project', 'installed for another project',
             lambda: ((cooked / intro).write_bytes(b'theirs'),
                      installs.write_ledger(self.lwr, dict(playFiles={intro: installs.sha256(cooked / intro)}, owners={intro: OTHER})))),
            ('a file the editor noted for no project', 'nothing says for which project',
             lambda: ((cooked / intro).write_bytes(b'whose?'),
                      installs.write_ledger(self.lwr, dict(playFiles={intro: installs.sha256(cooked / intro)})))),
        ]
        for what, says, make in cases:
            for install in (lambda: installs.install_package(self.lwr, folder),
                            lambda: installs.install_rotation(self.lwr, folder, 'additional')):
                with self.subTest(what):
                    make()
                    try:
                        before = self.snapshot(self.lwr)
                        with self.assertRaisesRegex(installs.InstallError, says): install()
                        self.assertEqual(self.snapshot(self.lwr), before)
                    finally:
                        installs.reset(self.lwr)
                        for p in (cooked / f'{VARIANT.lower()}.upk', cooked / intro): p.unlink(missing_ok=True)
                        (self.lwr / 'XCOM Map Workshop/play.json').unlink(missing_ok=True)

    def test_a_projects_own_files_are_replaced_and_others_identical_ones_kept(self):
        """Output names plan 3.4: whose each file is goes in the ledger, so a newer build of the same project replaces
        its files; a file changed since is refused; one the editor never put there that has the package's bytes is
        used and left there; and a ledger from before owners were noted gives the files of the package's own list to
        the project it says installed the variant."""
        self.package()
        folder, cooked = self.output / VARIANT, self.lwr / 'XEW/XComGame/CookedPCConsole'
        installs.install_rotation(self.lwr, folder, 'additional')
        ledger = installs.read_ledger(self.lwr)
        self.assertEqual(set(ledger['owners']), set(ledger['files']))
        self.assertEqual(set(ledger['owners'].values()), {ID})
        self.package(revision=2)
        installs.install_rotation(self.lwr, folder, 'additional')
        self.assertEqual((cooked / f'{VARIANT}.upk').read_bytes(), b'relit map 2')
        # changed since: left alone
        (cooked / f'{VARIANT}.upk').write_bytes(b'touched')
        self.package(revision=3)
        before = self.snapshot(self.lwr)
        with self.assertRaisesRegex(installs.InstallError, 'has changed since'): installs.install_rotation(self.lwr, folder, 'additional')
        self.assertEqual(self.snapshot(self.lwr), before)
        installs.reset(self.lwr)
        # the file changed since stays, still noted as this project's (review finding 26); the others went
        self.assertEqual(installs.read_ledger(self.lwr).get('owners'), {f'{VARIANT}.upk': ID})
        # a ledger from before owners: the rotation entry says the variant is this project's
        (cooked / f'{VARIANT}.upk').unlink()
        installs.install_rotation(self.lwr, folder, 'additional')
        ledger = installs.read_ledger(self.lwr)
        old = dict(ledger)
        old.pop('owners')
        installs.write_ledger(self.lwr, old)
        self.package(revision=4)
        installs.install_rotation(self.lwr, folder, 'additional')
        self.assertEqual(set(installs.read_ledger(self.lwr)['owners'].values()), {ID})
        # ...and when it says another project, nothing is replaced
        ledger = installs.read_ledger(self.lwr)
        ledger.pop('owners')
        ledger['rotation'] = [dict(e, project=dict(e['project'], id=OTHER)) for e in ledger['rotation']]
        installs.write_ledger(self.lwr, ledger)
        self.package(revision=5)
        with self.assertRaisesRegex(installs.InstallError, 'for another project'): installs.install_package(self.lwr, folder)
        installs.reset(self.lwr)
        # a file the editor never put there with the package's bytes: used, not noted, and left by Remove from game
        (cooked / f'CIN_DropshipIntros_{VARIANT}.upk').write_bytes(b'intro copy')
        installs.install_package(self.lwr, folder)
        self.assertNotIn(f'CIN_DropshipIntros_{VARIANT}.upk', installs.read_ledger(self.lwr)['playFiles'])
        installs.reset(self.lwr)
        self.assertEqual((cooked / f'CIN_DropshipIntros_{VARIANT}.upk').read_bytes(), b'intro copy')
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())

    def lab(self, files):
        """A lab whose bake fixtures' installer put `files` (paths in a game) there with the bytes they have now, and
        the lab setting pointing at it for the rest of the test."""
        lab = Path(self.temp.name) / 'lab'
        (lab / 'bake-fixtures').mkdir(parents=True, exist_ok=True)
        (lab / 'bake-fixtures' / 'deployed.json').write_text(
            json.dumps({str(p): installs.sha256(p) for p in files}), encoding='utf-8')
        import settings
        configured = mock.patch.object(settings, 'configured', side_effect=lambda key: lab if key == 'lab' else None)
        configured.start()
        self.addCleanup(configured.stop)
        return lab

    def test_the_labs_earlier_tests_of_a_project_are_replaced_kept_and_put_back(self):
        """A file of the package's own names that the lab's deploy tools put in the lab copy before the editor could
        install is an earlier test of the project: a play and a campaign install replace it, keeping it in the change's
        backup folder, and it goes back when the editor's file comes out (the play's end, Remove from game). Outside the
        lab copy, or changed since the lab put it there, it is refused as any file the editor didn't put there."""
        self.package()
        folder, cooked = self.output / VARIANT, self.lwr / 'XEW/XComGame/CookedPCConsole'
        earlier, intro = cooked / f'{VARIANT}.upk', cooked / f'CIN_DropshipIntros_{VARIANT}.upk'
        earlier.write_bytes(b'an earlier fixture of the project')
        intro.write_bytes(b'its intro')
        self.lab([earlier, intro])
        lab_bytes = {p.name: p.read_bytes() for p in (earlier, intro)}
        # not the lab copy (no marker): refused
        before = self.snapshot(self.lwr)
        with self.assertRaisesRegex(installs.InstallError, 'didn\'t put it there'): installs.install_package(self.lwr, folder)
        self.assertEqual(self.snapshot(self.lwr), before)
        (self.lwr / 'XComLab-copy.txt').write_text('lab')
        for install, out in ((lambda: installs.install_package(self.lwr, folder), lambda: installs.clear_play(self.lwr)),
                             (lambda: installs.install_rotation(self.lwr, folder, 'additional'), lambda: installs.reset(self.lwr))):
            with self.subTest(install=install):
                install()
                self.assertEqual(earlier.read_bytes(), b'relit map 1')
                ledger = installs.read_ledger(self.lwr)
                self.assertEqual(set(ledger['labFiles']), set(lab_bytes))
                self.assertEqual({n: (self.lwr / p).read_bytes() for n, p in ledger['labFiles'].items()}, lab_bytes)
                self.assertTrue(all(p.startswith(installs.LEDGER_FOLDER) for p in ledger['labFiles'].values()))
                out()
                self.assertEqual({p.name: p.read_bytes() for p in (earlier, intro)}, lab_bytes)
                self.assertFalse(installs.read_ledger(self.lwr).get('labFiles'))
        # changed since the lab put it there: refused, nothing written
        earlier.write_bytes(b'edited by hand since')
        before = self.snapshot(self.lwr)
        with self.assertRaisesRegex(installs.InstallError, f'{VARIANT}.upk is in CookedPCConsole and the editor didn\'t put it there'):
            installs.install_package(self.lwr, folder)
        self.assertEqual(self.snapshot(self.lwr), before)

    def test_what_the_lab_deployed(self):
        """lab_deploys reads the bake fixtures' ledger (files of this game's CookedPCConsole, with their hash), the
        patches patchtool's deployed.txt names (no hash: any bytes) and the maps its seeded.txt seeded last."""
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        (cooked / 'Fixture_Map.upk').write_bytes(b'fixture')
        lab = self.lab([cooked / 'Fixture_Map.upk', self.copy / 'XEW/XComGame/CookedPCConsole' / 'URB_Bar.upk'])
        (lab / 'patchtool').mkdir()
        (lab / 'patchtool' / 'deployed.txt').write_text('patch_one\npatch_two\n# 9bad.name\n', encoding='utf-8')
        (lab / 'patchtool' / 'seeded.txt').write_text('t1\tSeeded_Map\tpatch_one\t3\tAAAA\nt2\tSeeded_Map\tpatch_one\t4\tBBBB\n'
                                                      'short\trow\n', encoding='utf-8')
        self.assertEqual(installs.lab_deploys(self.lwr), {})            # not the lab copy
        (self.lwr / 'XComLab-copy.txt').write_text('lab')
        found = installs.lab_deploys(self.lwr)
        self.assertEqual(found, {'fixture_map.upk': {installs.sha256(cooked / 'Fixture_Map.upk')}, 'patch_one.upk': {None},
                                 'patch_two.upk': {None}, 'seeded_map.upk': {'bbbb'}})
        self.assertTrue(installs.lab_file(found, 'PATCH_ONE.upk', 'any'))
        self.assertTrue(installs.lab_file(found, 'Seeded_Map.upk', 'BBBB'))
        self.assertFalse(installs.lab_file(found, 'Seeded_Map.upk', 'AAAA'))
        self.assertFalse(installs.lab_file(found, 'URB_Bar.upk', 'x'))
        self.assertEqual(installs.lab_deploys(self.lwr, lab=Path(self.temp.name) / 'no lab'), {})

    def test_a_rebuild_with_the_named_cache_leaves_the_old_one_until_everything_is_removed(self):
        """Output names plan 4: a campaign install of a package with Lighting_<n>.tfc, then of the project's rebuild
        with <Variant>_Lighting.tfc: both are in the game and noted as the project's; the old one is taken out only by
        Remove everything (reset), which takes both. A play's files go when the game closes, the old cache's too."""
        self.package()
        folder, cooked = self.output / VARIANT, self.lwr / 'XEW/XComGame/CookedPCConsole'
        installs.install_rotation(self.lwr, folder, 'additional')
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        (folder / 'CookedPCConsole' / 'Lighting_4242.tfc').unlink()
        (folder / 'CookedPCConsole' / f'{VARIANT}_Lighting.tfc').write_bytes(b'named lightmaps')
        files = {k: v for k, v in m['files'].items() if not k.endswith('Lighting_4242.tfc')}
        files[f'CookedPCConsole/{VARIANT}_Lighting.tfc'] = hashlib.sha256(b'named lightmaps').hexdigest()
        (folder / 'manifest.json').write_text(json.dumps(dict(m, files=files, cache=f'{VARIANT}_Lighting')), encoding='utf-8')
        installs.install_rotation(self.lwr, folder, 'additional')
        ledger = installs.read_ledger(self.lwr)
        self.assertTrue((cooked / 'Lighting_4242.tfc').is_file() and (cooked / f'{VARIANT}_Lighting.tfc').is_file())
        self.assertEqual({ledger['owners'][n] for n in ('Lighting_4242.tfc', f'{VARIANT}_Lighting.tfc')}, {ID})
        installs.reset(self.lwr)
        self.assertFalse((cooked / 'Lighting_4242.tfc').exists() or (cooked / f'{VARIANT}_Lighting.tfc').exists())
        # a play: both kinds of cache are the play's and go with it
        self.package()
        installs.install_package(self.lwr, folder)
        installs.clear_play(self.lwr)
        self.assertFalse((cooked / 'Lighting_4242.tfc').exists())

    def test_nothing_changes_while_xcom_runs(self):
        before = self.files(self.lwr)
        self.running = True
        player = self.player()
        self.assertEqual(player.status()['install']['why'], 'XCOM is running')
        for change in (lambda: player.play(dict(map='URB_Bar')), player.remove):
            with self.assertRaises(ProjectError) as error: change()
            self.assertEqual(error.exception.status, 409)
            self.assertIn('XCOM is running', error.exception.message)
        self.assertEqual((self.files(self.lwr), self.started), (before, []))

    def close_game(self, player):
        """The game comes up and closes again, and the player's watch ends."""
        self.running = True
        time.sleep(0.1)
        self.running = False
        self.settle(player)

    def test_a_play_leaves_nothing_in_the_game_once_it_has_closed(self):
        before = self.files(self.lwr)
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        self.package()
        player = self.player(cleanup=True, appear=30)
        r = player.play(dict(project=ID))
        # while the game is up the build is in: its record, landing zones and files, noted in the play's own ledger
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 1)
        self.assertTrue((cooked / f'{VARIANT}.upk').is_file())
        play = json.loads((self.lwr / 'XCOM Map Workshop/play.json').read_text(encoding='utf-8'))
        main = json.loads((self.lwr / 'XCOM Map Workshop/installs.json').read_text(encoding='utf-8'))
        self.assertEqual((play['schema'], [b['variant'] for b in play['records']], sorted(play['playFiles']), len(play['playZones'])),
                         (installs.PLAY_SCHEMA, [VARIANT], sorted(['Lighting_4242.tfc', f'{VARIANT}.upk', f'CIN_DropshipIntros_{VARIANT}.upk']), 1))
        self.assertFalse(any(main.get(k) for k in installs.PLAY_KEYS + ('files', 'landingZones', 'rotation')))
        self.assertTrue(r['game']['play'])
        # the game closes: all of it is out, and the config files are byte for byte as they were
        self.close_game(player)
        self.assertEqual(self.files(self.lwr), before)
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())
        self.assertFalse((self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).exists())
        s = player.status()['game']
        self.assertEqual((s['installed'], s['play'], s['anything'], s['lastPlay']['map']), ([], False, False, VARIANT))
        # a map alone: its commands file goes too
        player.play(dict(map='URB_Bar'))
        self.close_game(player)
        self.assertFalse(player.status()['game']['anything'])
        self.assertEqual(self.files(self.lwr), before)

    def test_clearing_a_play_leaves_what_is_installed_for_campaigns(self):
        import manager
        before = self.files(self.lwr)
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        self.package()
        player = self.player(cleanup=True, appear=30)
        # played first, then installed for campaigns while the game is... closed again, so the play was cleared
        player.play(dict(project=ID))
        self.close_game(player)
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        campaign = self.files(self.lwr)
        # a play of the same build beside it: its record goes when the game closes, the campaign's stay, files and all
        player.play(dict(project=ID))
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 2)
        self.close_game(player)
        self.assertEqual(self.files(self.lwr), campaign)
        self.assertTrue((cooked / f'{VARIANT}.upk').is_file())
        self.assertIn(f'MapName="{VARIANT}"'.encode(), campaign['DefaultLZMutator.ini'])
        # a play of a newer build of it: the newer file is the campaign's now and stays
        self.package(revision=2)
        player.play(dict(project=ID))
        self.close_game(player)
        self.assertEqual((cooked / f'{VARIANT}.upk').read_bytes(), b'relit map 2')
        self.assertEqual(self.files(self.lwr), campaign)
        # the other way round: in the game from a play, then installed for campaigns before the game closes... the
        # play's files and landing zones become the campaign's
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)
        quiet = self.player()                                       # no cleanup: the play's things stay in
        quiet.play(dict(project=ID))
        self.settle(quiet)
        manager.install(self.store, self.builds, quiet, dict(projects=[ID], mode='additional'))
        self.assertEqual(installs.clear_play(self.lwr)['files'], [])
        self.assertTrue((cooked / f'{VARIANT}.upk').is_file())
        self.assertIn(f'MapName="{VARIANT}"'.encode(), self.files(self.lwr)['DefaultLZMutator.ini'])
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 1)
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())

    def test_a_ledger_from_before_the_two_were_separate_is_read_as_the_plays(self):
        before = self.files(self.lwr)
        self.package()
        quiet = self.player()
        quiet.play(dict(project=ID))
        self.settle(quiet)
        # as an earlier version wrote it: everything in installs.json, no play.json
        folder = self.lwr / 'XCOM Map Workshop'
        play = json.loads((folder / 'play.json').read_text(encoding='utf-8'))
        main = json.loads((folder / 'installs.json').read_text(encoding='utf-8'))
        old = dict(main, schemaVersion=2, records=play['records'], installed=play['installed'], lastPlay=play['lastPlay'],
                   config=play['config'], files=play['playFiles'], landingZones=play['playZones'])
        (folder / 'installs.json').write_text(json.dumps(old), encoding='utf-8')
        (folder / 'play.json').unlink()
        # the next server's start clears it, the game being closed (a look at the install changes nothing)
        player = self.player(cleanup=True)
        self.assertTrue(player.status()['game']['play'])
        self.assertIsNone(player.watching)
        self.assertTrue(player.recover())
        self.settle(player)
        self.assertEqual(self.files(self.lwr), before)
        self.assertFalse(player.status()['game']['anything'])

    def test_the_routes_start_the_game_only_for_the_viewer_itself(self):
        player = self.player(self.copy)
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=self.catalogue, projects=self.store,
                                                       builds=self.builds, player=player))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            def call(method, path, body=None, origin=None):
                request = Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json', **({'Origin': origin} if origin else {})})
                try:
                    with urlopen(request, timeout=10) as r: return r.status, json.loads(r.read())
                except HTTPError as e: return e.code, json.loads(e.read())
            status, s = call('GET', '/play.json')
            self.assertEqual((status, s['install']['folder'], s['game']['anything']), (200, str(self.copy), False))
            self.assertEqual(call('POST', '/play/start', dict(map='URB_Bar'), origin='http://evil.example')[0], 403)
            self.assertEqual(call('POST', '/play/start', dict(map='URB_Bar', project=ID))[0], 400)
            self.assertEqual(self.started, [])
            status, r = call('POST', '/play/start', dict(map='URB_Bar'))
            self.assertEqual((status, r['played']['map'], len(self.started)), (200, 'URB_Bar', 1))
            self.settle(player)
            status, r = call('POST', '/play/remove', {})
            self.assertEqual((status, r['removed']['playFile'], r['game']['anything']), (200, True, False))
            self.assertEqual(call('GET', '/play/remove')[0], 405)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


class Launch(unittest.TestCase):
    """gamelaunch.py: the commands file's text and the command that starts the game (nothing is started)."""

    def test_the_commands_file_with_and_without_a_squad(self):
        # the six squaddies plays had before the setup panel (tests/squad_default_lwr.txt: squadrecords makes the same,
        # test_squad_records.py), set as the profile's soldiers
        squad = (HERE / 'squad_default_lwr.txt').read_text(encoding='ascii').strip()
        text = gamelaunch.play_text('URB_Bar', squad)
        self.assertEqual(text.split('\n'), ['set XComContentManager bAllowJITLoad True',
                                            'set XComOnlineProfileSettingsDataBlob m_eAlienType eChar_Sectoid',
                                            f'set XComOnlineProfileSettings m_aSoldiers {squad}', 'open URB_Bar', ''])
        text.encode('ascii')
        # no squad: the game's own lands
        self.assertNotIn('m_aSoldiers', gamelaunch.play_text('URB_Bar'))
        # a prefab test: no aliens (no pods are made of eChar_None)
        self.assertEqual(gamelaunch.play_text('URB_Bar', squad, aliens=False).split('\n')[1],
                         'set XComOnlineProfileSettingsDataBlob m_eAlienType eChar_None')
        for bad in ('URB Bar', 'URB_Bar?x=1', ''):
            with self.assertRaises(gamelaunch.LaunchError): gamelaunch.play_text(bad, squad)
        # a squad text that is not one line of printable ASCII soldiers is refused
        for bad in ('lwr', squad + '\nopen Other', squad.replace('Tom', 'Töm'), '((kChar=(x))'[:-1]):
            with self.assertRaises(gamelaunch.LaunchError): gamelaunch.play_text('URB_Bar', bad)

    def test_a_record_keeps_its_kind_unless_a_prefab_test_asks(self):
        # Temple Ship's record is the final mission's: its variant's is too, out of rotation (mission types plan, A1)
        lines = [b'[XComGame.XComMapManager]', record('bar'), record('templeship'), b'']
        at, (comment, new) = installs.plan_record(lines, 'TempleShip', 'TempleShip_Remix_0f8b', note='a test')
        self.assertEqual(at, 3)
        self.assertEqual(dep.unquoted(record('templeship'), 'MissionType'), 'eMission_Final')
        self.assertEqual((dep.field(new, 'Name'), dep.unquoted(new, 'MissionType'), dep.unquoted(new, 'bInRotation')),
                         ('TempleShip_Remix_0f8b', 'eMission_Final', 'False'))
        # the Temple Ship's name is matched in the display name (Long War's squad order): a variant of another name gets it
        _, (_, other) = installs.plan_record(lines, 'TempleShip', 'TS_Remix_0f8b', note='a test')
        self.assertEqual(dep.field(other, 'DisplayName'), 'TS_Remix_0f8b_TempleShip (XCOM Map Workshop)')
        self.assertEqual(dep.field(new, 'DisplayName'), 'TempleShip_Remix_0f8b (XCOM Map Workshop)')
        with self.assertRaises(ValueError): installs.plan_record(lines, 'TempleShip', 'x_y', note='a test', index=1)
        self.assertEqual(dep.slot_streams(new), dep.slot_streams(record('templeship')))
        self.assertTrue(comment.startswith(b'; TempleShip_Remix_0f8b: TempleShip'))
        with self.assertRaises(ValueError): installs.plan_record(lines, 'URB_Nowhere', 'URB_Nowhere_x', note='a test')
        # another kind on request; a prefab test's is an abduction (F-93: none crashed, a terror site stalled)
        _, (_, new) = installs.plan_record(lines, 'TempleShip', 'pt_x', note='a test', mission='eMission_Crash')
        self.assertEqual(dep.unquoted(new, 'MissionType'), 'eMission_Crash')
        self.assertEqual(installs.TEST_MISSION, 'eMission_Abduction')

    def test_the_base_map_is_found_whatever_the_case_of_its_name(self):
        # the farm's file is CsmallScout_Farm.upk and its records name CSmallScout_Farm: the game matches names whatever
        # their case, and so does Play in game (EXP-78 run F stopped with no record for CsmallScout_Farm)
        lines = [b'[XComGame.XComMapManager]', record('bar'), record('templeship'), b'']
        self.assertEqual([i for i, _ in installs.base_records(lines, 'templeSHIP')], [2])
        self.assertEqual(installs._after_base(lines, {}, 'TEMPLESHIP'), 3)
        _, (_, new) = installs.plan_record(lines, 'templeship', 'templeship_Remix_0f8b', note='a test')
        self.assertEqual(dep.field(new, 'Name'), 'templeship_Remix_0f8b')
        self.assertEqual(installs.base_records(lines, 'TempleShipX'), [])

    def test_the_kinds_of_mission_and_their_commands(self):
        self.assertEqual([missions.kind_key(r) for r in (record('bar'), bomb_record(), record('templeship'), record('gangplank'))],
                         ['Abduction', 'Special/Bomb', 'Final', 'LandedUFO'])
        self.assertEqual(missions.kind_of_export(dict(type='Special', label='Council rescue')), 'Special/Rescue')
        # export 37 says the kind itself: a reworded label no longer turns a council mission into a plain special one
        self.assertEqual(missions.kind_of_export(dict(type='Special', label='Council rescue (new words)', kind='Special/Rescue')),
                         'Special/Rescue')
        self.assertEqual(missions.kind('eMission_Unheard')['state'], 'untried')
        landed = 'MissionType=eMission_LandedUFO, ShipType=eShip_UFOSmallScout, CouncilType=eFCMType_None'
        hive = 'MapFamily="EWI_ChryssalidHive", MissionType=eMission_Special, CouncilType=eFCMType_Assault'
        extraction = 'MissionType=eMission_CovertOpsExtraction, CouncilType=eFCMType_None'     # (not played yet)
        for record_text, tried_lines, tried_options in (
                (landed, ['set XGBattleDesc m_eUFOType eShip_UFOSmallScout'], [('Meld', '1')]),
                (hive, ['set XGBattleDesc m_eCouncilType eFCM_ChryssalidHive'], []),
                (extraction, [], [('RadarArrays', '1')])):
            untried = missions.play_setup(record_text)
            self.assertEqual((untried['lines'], untried['options']), ([], []))
            self.assertEqual(len(untried['missing']), len(tried_lines) + bool(tried_options))
            tried = missions.play_setup(record_text, try_untried=True)
            self.assertEqual((tried['lines'], tried['options'], tried['missing']), (tried_lines, tried_options, []))
        # a council mission the script doesn't tell apart needs no council line
        self.assertEqual(missions.play_setup(bomb_record(), try_untried=True)['lines'], [])
        self.assertIsNone(missions.civilian_content('[XComGame.XComContentManager]'))
        # the commands file: the mission's lines before the open line, its options after the landing
        text = gamelaunch.play_text('URB_Bar', None, spawn_group='Group2', lines=['set XGBattleDesc m_eUFOType eShip_UFOSmallScout'],
                                    options=[('Meld', '1')])
        self.assertEqual(text.split('\n')[-3:], ['set XGBattleDesc m_eUFOType eShip_UFOSmallScout', 'open URB_Bar?SpawnGroup=Group2?Meld=1', ''])
        for bad in (dict(lines=['open Other']), dict(lines=['set a b c\nopen x']), dict(options=[('Meld', '1?x=2')])):
            with self.assertRaises(gamelaunch.LaunchError): gamelaunch.play_text('URB_Bar', None, **bad)
        # what the game matches in a display name, kept by a variant's
        self.assertEqual(missions.display_name('URB_Boulevard_Bomb (Bomb Defusal Boulevard) |0', 'URB_Boulevard_Mine', 'Mine, Council bomb', ' |0'),
                         'URB_Boulevard_Mine_Bomb (Mine, Council bomb) |0')
        self.assertEqual(missions.markers('URB_Bar (Abduction) |0', 'URB_Bar_Mine'), '')
        self.assertEqual(missions.matched('URB_Trainyard_Bomb (x)')[0][0], '_Bomb')
        self.assertIn('Zhang', missions.named_map('DLC1_1_LowFriends'))
        self.assertIsNone(missions.named_map('URB_Bar'))

    def test_a_variant_of_the_intro_map_copies_its_commented_out_abduction_record(self):
        # LWR comments out both of Act1_IntroLevel's records (maplist.SWITCHED_OFF): the variant's record is a live
        # copy of the abduction's, put after it; the commented-out lines stay as they were
        intro_variant = 'Act1_IntroLevel_Remix_0f8b'
        lines = [b'[XComGame.XComMapManager]', record('bar'), record('intro_abduction'), record('intro_tutorial'), b'']
        at, (comment, new) = installs.plan_record(lines, 'Act1_IntroLevel', intro_variant, note='a test')
        self.assertEqual(at, 3)
        self.assertTrue(dep.is_record(new))
        self.assertEqual((dep.field(new, 'Name'), dep.unquoted(new, 'MissionType'), dep.unquoted(new, 'bInRotation')),
                         (intro_variant, 'eMission_Abduction', 'False'))
        self.assertEqual(dep.slot_streams(new), ['CIN_DropshipIntros'])
        self.assertTrue(comment.startswith(b'; Act1_IntroLevel_Remix_0f8b: Act1_IntroLevel'))

    def test_steam_starts_the_folder_its_manifest_names(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / 'Lib' / 'steamapps'
            game, parked = library / 'common' / 'XCom-Enemy-Unknown', library / 'common' / 'XCom-Enemy-Unknown.LWR'
            for folder in (game, parked): (folder / 'XEW/Binaries/Win32').mkdir(parents=True)
            steam = lambda: Path('C:/Steam/steam.exe')  # noqa: E731
            with self.assertRaises(gamelaunch.LaunchError) as error: gamelaunch.command(game, 'play.txt', steam)
            self.assertIn('appmanifest_200510.acf', str(error.exception))
            (library / 'appmanifest_200510.acf').write_text('"AppState"\n{\n\t"appid"\t\t"200510"\n\t"installdir"\t\t"XCom-Enemy-Unknown"\n}\n', encoding='utf-8')
            argv, cwd, how = gamelaunch.command(game, 'play.txt', steam)
            self.assertEqual((argv, cwd, how), ([str(Path('C:/Steam/steam.exe')), '-applaunch', '200510', '-EXEC=play.txt'], None, 'steam'))
            with self.assertRaises(gamelaunch.LaunchError) as error: gamelaunch.command(parked, 'play.txt', steam)
            self.assertIn('Steam runs', str(error.exception))
            with self.assertRaises(gamelaunch.LaunchError) as error: gamelaunch.command(game, 'play.txt', lambda: None)
            self.assertIn('Steam was not found', str(error.exception))
            # outside a Steam library: the game's own program
            alone = Path(temp) / 'Games' / 'XCOM'
            with self.assertRaises(gamelaunch.LaunchError): gamelaunch.command(alone, 'play.txt', steam)
            (alone / 'XEW/Binaries/Win32').mkdir(parents=True)
            (alone / 'XEW/Binaries/Win32/XComEW.exe').write_bytes(b'')
            argv, cwd, how = gamelaunch.command(alone, 'play.txt', steam)
            self.assertEqual((argv[1:], cwd, how), (['-EXEC=play.txt'], alone / 'XEW/Binaries/Win32', 'direct'))


if __name__ == '__main__':
    unittest.main()
