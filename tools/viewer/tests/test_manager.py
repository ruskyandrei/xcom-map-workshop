"""The project manager and the Game maps window (manager.py, gamemaps.py and their routes; installs.install_rotation,
remove_rotation and set_records_use), on the temporary game installs of viewer_fixtures.PlayInstalls: the listing, builds installed
for campaigns beside the base map or in its place, records switched off and on, all of it undone byte for byte, and
the map pack's zip."""
from functools import partial
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import gamemaps  # noqa: E402
import manager  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import pack_card  # noqa: E402
import maplist  # noqa: E402
from projects import ProjectError  # noqa: E402
from viewer_fixtures import (ID, MUTATOR_LOADER, PLAY, RANDOM_SPAWNS, VARIANT, ManagerInstalls, document,  # noqa: E402
                             record)
from viewer_fixtures import SECOND_ID as OTHER_ID, SECOND_VARIANT as OTHER  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# the game's landing intro, for the pack's one copy of it: without it that test skips
INTRO, NO_INTRO = labpaths.test_file('XCOM_INTRO_UPK', labpaths.lwr_cooked('CIN_DropshipIntros.upk'), 'CIN_DropshipIntros.upk')
UNBUILT_ID, MISSING_ID = '2b3c4d5e-1d2a-4b6c-8e9f-123456789abc', '3c4d5e6f-1d2a-4b6c-8e9f-123456789abc'


class Manager(ManagerInstalls, unittest.TestCase):
    def row(self, listed, project_id=ID):
        return next(p for p in listed['projects'] if p['id'] == project_id)

    def test_the_listing_gives_each_projects_last_build_and_its_warnings(self):
        self.more_missions(self.lwr)
        player = self.player()
        row = self.row(manager.listing(self.store, self.builds, player))
        self.assertEqual((row['variant'], row['build'], row['inGame'], row['map']), (VARIANT, None, None, 'URB_Bar'))
        self.assertEqual([(m['label'], m['inRotation']) for m in row['missions']],
                         [('Abduction', True), ('Terror', True), ('Council bomb', False)])
        # each way's warnings: a council bomb is an extra bomb mission under Long War when additional, and takes the
        # original's record name when it replaces; nothing says a mission is untried (16 November 2026)
        self.assertEqual(row['warnings'], [])
        add, replace = row['modeWarnings']['additional'], row['modeWarnings']['replace']
        self.assertEqual((len(add), len(replace)), (1, 1))
        self.assertIn('extra bomb mission', add[0])
        self.assertIn('by name', replace[0])
        self.assertNotIn('untested', ' '.join(add + replace))
        self.package(revision=1, quick=True)
        listed = manager.listing(self.store, self.builds, player)
        row = self.row(listed)
        self.assertEqual((row['build']['revision'], row['build']['quick'], row['build']['stale'], row['build']['builtAt']),
                         (1, True, False, '2026-11-08T12:00:00'))
        self.assertIn('not baked', row['warnings'][0])
        self.assertEqual((listed['install']['folder'], listed['install']['ready']), (str(self.lwr), True))
        # saved again since: the build is of an older revision
        self.store.save(ID, self.store.load(ID), 1)
        row = self.row(manager.listing(self.store, self.builds, player))
        self.assertTrue(row['build']['stale'])
        self.assertTrue(any('revision 1' in w for w in row['warnings']))
        # whose picture the map shows (pictures.py): none here (the made-up install has no map pictures), its own once
        # the project names one that is kept
        self.assertEqual(row['picture'], 'none')
        import pictures
        from viewer_fixtures import png
        digest = pictures.save_picture(self.store, ID, png())['sha256']
        self.store.save(ID, dict(self.store.load(ID), picture=dict(sha256=digest)), 2)
        self.assertEqual(self.row(manager.listing(self.store, self.builds, player))['picture'], 'own')

    def test_a_malformed_shared_project_is_a_row_of_its_own(self):
        """Review finding 9: one file the editor can't read (its base map a string) is listed with its reason, and the
        other projects are listed as before."""
        broken = '4d5e6f7a-1d2a-4b6c-8e9f-123456789abc'
        (self.store.root / 'from a friend.json').write_text(json.dumps(document(broken, source='URB_Bar')), encoding='utf8')
        listed = manager.listing(self.store, self.builds, self.player())
        self.assertEqual(self.row(listed)['variant'], VARIANT)
        bad = next(p for p in listed['projects'] if p['file'] == 'from a friend.json')
        self.assertIn('base map', bad['error'])

    def test_a_campaign_install_follows_the_builds_records_for_the_projects_missions(self):
        # mission types plan, D4: the Build's own records, in rotation as the base map's (an added terror in, a bomb out)
        terror, council = self.more_missions(self.lwr)
        line = lambda base, label, display=None: dep.set_field(dep.set_field(dep.set_field(base, 'Name', VARIANT), 'DisplayName',  # noqa: E731
                                                                             display or f'{VARIANT} (Bar remix, {label}) |0'),
                                                               'bInRotation', 'False', quoted=False).decode('latin-1')
        added_terror = dep.set_field(record('bar'), 'MissionType', 'eMission_TerrorSite', quoted=False)
        self.package(maps=[line(record('bar'), 'Abduction'), line(council, 'Council bomb', f'{VARIANT}_Bomb (Bar remix, Council bomb) |0'),
                           line(added_terror, 'Terror')], record_missions=[[0], [2], ['TerrorSite']])
        folder = self.output / VARIANT
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        m['config']['missionsFromProject'] = True
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        before = self.files(self.lwr)
        player = self.player()
        done = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))['results'][0]
        self.assertTrue(done['ok'], done)
        mine = self.records(self.lwr, VARIANT)
        self.assertEqual([(dep.unquoted(l, 'MissionType'), dep.unquoted(l, 'bInRotation'), dep.field(l, 'DisplayName')) for l in mine],
                         [('eMission_Abduction', 'True', f'{VARIANT} (Bar remix, Abduction) |0'),
                          ('eMission_Special', 'False', dep.field(council, 'DisplayName')),      # replacing: asked for by name
                          ('eMission_TerrorSite', 'True', f'{VARIANT} (Bar remix, Terror) |0')])
        self.assertFalse(any('played' in w for w in done['warnings']), done['warnings'])
        # F-118: Bar's own terror record, which the build has no record for, stays in use; the others are replaced
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [terror])
        self.assertTrue(any(w.startswith('Terror: the build has no record') for w in done['warnings']), done['warnings'])
        # a play of the added terror installs the Build's record for it
        r = player.play(dict(project=ID, mission='TerrorSite'))
        self.assertEqual(r['played']['mission']['label'], 'Terror')
        self.settle(player)             # the play's watch puts things back too: a reset while it runs races it
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)

    def test_additional_adds_the_variant_to_the_rotation_and_replace_comments_the_map_out(self):
        terror, council = self.more_missions(self.lwr)
        before = self.files(self.lwr)
        player = self.player()
        r = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        self.assertEqual((r['results'][0]['ok'], r['results'][0]['error']), (False, 'It has not been built yet.'))
        self.assertEqual(self.files(self.lwr), before)
        self.package()
        r = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        done = r['results'][0]
        self.assertEqual((done['ok'], done['missions'], done['switchedOff']), (True, ['Abduction', 'Terror'], 0))
        self.assertEqual(len(done['warnings']), 1)
        mine = self.records(self.lwr, VARIANT)
        self.assertEqual([(dep.unquoted(l, 'MissionType'), dep.unquoted(l, 'bInRotation')) for l in mine],
                         [('eMission_Abduction', 'True'), ('eMission_TerrorSite', 'True'), ('eMission_Special', 'False')])
        self.assertEqual([dep.field(l, 'DisplayName') for l in mine],
                         [f'{VARIANT} (Bar remix, Abduction) |0', f'{VARIANT} (Bar remix, Terror) |0',
                          f'{VARIANT}_Bomb (Bar remix, Council bomb) |0'])     # Long War's _Bomb kept (mission types plan, B)
        for l in mine:
            self.assertIn(f'CIN_DropshipIntros_{VARIANT}', dep.slot_streams(l))
            self.assertNotIn('CIN_DropshipIntros', dep.slot_streams(l))
        # after Bar's records, whose own lines are as they were
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        self.assertEqual(maps[maps.index(council) + 2], mine[0])
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [record('bar'), terror, council])
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        self.assertNotIn(VARIANT, maplist.lwr_maps(self.lwr))
        self.assertIn(f'MapName="{VARIANT}"'.encode(), self.files(self.lwr)['DefaultLZMutator.ini'])
        self.assertTrue((self.lwr / 'XEW/XComGame/CookedPCConsole' / f'{VARIANT}.upk').is_file())
        row = self.row(r)
        self.assertEqual(row['inGame'], dict(play=False, rotation='additional', buildId=f'{VARIANT}-1', current=True))
        # replace: Bar's own records are commented out, and the variant's council record has Bar's record name, which
        # the game asks for
        r = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        self.assertEqual((r['results'][0]['switchedOff'], self.row(r)['inGame']['rotation']), (3, 'replace'))
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [])
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        for line in (record('bar'), terror, council): self.assertIn(b';' + line, maps)
        mine = self.records(self.lwr, VARIANT)
        self.assertEqual([dep.field(l, 'DisplayName') for l in mine],
                         [f'{VARIANT} (Bar remix, Abduction) |0', f'{VARIANT} (Bar remix, Terror) |0', 'URB_Bar_Bomb (Bomb) |0'])
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        self.assertEqual(len(maplist.lwr_maps(self.lwr)['URB_Bar']['missions']), 3)       # the editor still reads Bar
        # Play in game's record goes in beside them under its play name (play_names.py), and comes out without
        # touching them
        player.play(dict(project=ID))
        self.settle(player)
        self.assertEqual(len(self.records(self.lwr, VARIANT)), 3)
        mine, = self.records(self.lwr, PLAY)
        self.assertEqual(dep.field(mine, 'DisplayName'), f'{PLAY} (XCOM Map Workshop) |0')
        self.assertEqual(self.row(manager.listing(self.store, self.builds, player))['inGame']['play'], True)
        # Bar itself still plays alone: with its records commented out it gets a copy for the play, named apart
        r = player.play(dict(map='URB_Bar'))
        self.settle(player)
        copy, = self.records(self.lwr, 'URB_Bar')
        self.assertEqual((dep.field(copy, 'DisplayName'), dep.unquoted(copy, 'bInRotation')), ('URB_Bar (XCOM Map Workshop) |0', 'False'))
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        # back to additional: Bar's records are live again
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        self.assertEqual(self.records(self.lwr, 'URB_Bar')[:3], [record('bar'), terror, council])
        self.assertEqual(len(self.records(self.lwr, PLAY)), 1)
        # Game maps undoes the build: its records for campaigns, Play in game's record and its landing zones
        r = gamemaps.undo(player, dict(variants=[VARIANT]))
        self.assertEqual((r['undone'], self.records(self.lwr, VARIANT), self.records(self.lwr, PLAY)), ([VARIANT, PLAY], [], []))
        self.assertEqual(self.files(self.lwr)['DefaultLZMutator.ini'], before['DefaultLZMutator.ini'])
        self.assertIsNone(self.row(manager.listing(self.store, self.builds, player))['inGame'])
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        done = player.remove()['removed']
        self.assertEqual((done['records'], done['rotation'], done['recordsBack'], done['left']), (1, 1, 3, []))
        self.assertEqual(self.files(self.lwr), before)

    def test_replace_takes_out_a_record_written_by_hand_with_spaces_around_its_equals_signs(self):
        # KB-11: a record of Bar's written by hand as Name = "URB_Bar" (the game reads it so, and so does the map
        # list) is one of Bar's records to the install too: Replace comments it out with the others, and Bar's
        # records read with the Build's records' missions
        terror, council = self.more_missions(self.lwr)
        path = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        spaced = re.sub(rb'(?<![A-Za-z])Name="URB_Bar"', b'Name = "URB_Bar"', terror, count=1)
        spaced = spaced.replace(b'MissionType=eMission_TerrorSite', b'MissionType = eMission_TerrorSite')
        self.assertNotEqual(spaced, terror)
        lines = dep.lines_of(path.read_bytes())
        lines[lines.index(terror)] = spaced
        path.write_bytes(dep.EOL.join(lines))
        before = self.files(self.lwr)
        self.package()
        player = self.player()
        done = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))['results'][0]
        self.assertTrue(done['ok'], done)
        self.assertEqual((done['missions'], done['switchedOff']), (['Abduction', 'Terror'], 3))
        maps = dep.lines_of(self.files(self.lwr)['DefaultMaps.ini'])
        for line in (record('bar'), spaced, council): self.assertIn(b';' + line, maps)
        self.assertNotIn(spaced, maps)
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [])
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)

    def test_a_map_stays_replaced_while_any_variant_replaces_it(self):
        before = self.files(self.lwr)
        player = self.player()
        self.package()
        self.second()
        r = manager.install(self.store, self.builds, player, dict(projects=[ID, OTHER_ID, MISSING_ID], mode='replace'))
        self.assertEqual([x['ok'] for x in r['results']], [True, True, False])
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [])
        self.assertEqual([dep.unquoted(self.records(self.lwr, v)[0], 'bInRotation') for v in (VARIANT, OTHER)], ['True', 'True'])
        gamemaps.undo(player, dict(variants=[VARIANT]))
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [])
        gamemaps.undo(player, dict(variants=[OTHER]))
        self.assertEqual(self.files(self.lwr)['DefaultMaps.ini'], before['DefaultMaps.ini'])
        # nothing changes while XCOM runs
        self.running = True
        with self.assertRaises(ProjectError) as error: manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        self.assertIn('XCOM is running', error.exception.message)
        self.assertEqual(self.files(self.lwr)['DefaultMaps.ini'], before['DefaultMaps.ini'])

    def test_game_maps_lists_the_records_and_switches_them_off_and_on(self):
        terror, council = self.more_missions(self.lwr)
        before = self.files(self.lwr)
        player = self.player()
        listed = gamemaps.listing(player)
        bar = next(m for m in listed['maps'] if m['name'] == 'URB_Bar')
        self.assertEqual([(r['mission'], r['inRotation'], r['state'], r['kind']) for r in bar['records']],
                         [('Abduction', True, 'on', 'own'), ('Terror', True, 'on', 'own'), ('Council bomb', False, 'on', 'own')])
        self.assertEqual((listed['anything'], listed['install']['ready']), (False, True))
        # the terror record switched off: its line commented out, the others as they were
        r = gamemaps.use(player, dict(records=[bar['records'][1]['id']], use=False))
        self.assertEqual(r['changed'], 1)
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [record('bar'), council])
        self.assertIn(b';' + terror, dep.lines_of(self.files(self.lwr)['DefaultMaps.ini']))
        bar = next(m for m in r['maps'] if m['name'] == 'URB_Bar')
        self.assertEqual([(x['state'], x['manual']) for x in bar['records']], [('on', False), ('off', True), ('on', False)])
        self.assertEqual(installs.maps_text(self.lwr).encode('latin-1'), before['DefaultMaps.ini'])
        # a build replaces Bar: every record of Bar's is off and says by whom, the build's records are listed under it
        self.package()
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        bar = next(m for m in gamemaps.listing(player)['maps'] if m['name'] == 'URB_Bar')
        self.assertEqual([(x['state'], x['by']) for x in bar['records'][:3]], [('replaced', ['Bar remix'])] * 3)
        self.assertEqual([(x['kind'], x['variant'], x['mode'], x['mission']) for x in bar['records'][3:]],
                         [('rotation', VARIANT, 'replace', m) for m in ('Abduction', 'Terror', 'Council bomb')])
        # switching the terror record on while replaced leaves it off; undoing the build brings back all but it...
        r = gamemaps.use(player, dict(records=[bar['records'][1]['id']], use=True))
        self.assertEqual((r['replaced'], self.records(self.lwr, 'URB_Bar')), (1, []))
        gamemaps.use(player, dict(records=[bar['records'][1]['id']], use=False))
        gamemaps.undo(player, dict(variants=[VARIANT]))
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [record('bar'), council])
        # ...and switched on again the file is the install's own
        r = gamemaps.use(player, dict(records=[bar['records'][1]['id']], use=True))
        self.assertEqual(self.files(self.lwr)['DefaultMaps.ini'], before['DefaultMaps.ini'])
        # Undo everything brings switched-off records back too
        gamemaps.use(player, dict(records=[x['id'] for x in bar['records'][:3]], use=False))
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [])
        self.assertEqual(player.remove()['removed']['recordsBack'], 3)
        self.assertEqual(self.files(self.lwr), before)
        with self.assertRaises(ProjectError): gamemaps.use(player, dict(records=['nothing'], use=False))

    def test_a_pack_zips_the_builds_with_the_lines_for_the_mode(self):
        self.more_missions(self.lwr)
        before = self.files(self.lwr)
        player = self.player()
        with self.assertRaises(ProjectError) as error: manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        self.assertEqual(error.exception.status, 409)
        self.package()
        self.second()
        self.store.save(UNBUILT_ID, dict(document(output=dict(shipAs='URB_Bar_Unbuilt_9', patch='patch_x')), id=UNBUILT_ID, name='Unbuilt'), 0)
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID, UNBUILT_ID], mode='replace', name='My: pack?'))
        self.assertEqual(([p['variant'] for p in r['packed']], [s['name'] for s in r['skipped']], r['name']),
                         ([VARIANT, OTHER], ['Unbuilt'], 'My pack'))
        target = Path(r['zip'])
        self.assertEqual(target.parent, self.output / manager.PACKS)
        with zipfile.ZipFile(target) as z:
            names = set(z.namelist())
            readme = z.read('README.txt').decode('latin-1')
            described = json.loads(z.read('pack.json'))
            self.assertEqual(z.read(f'CookedPCConsole/My_pack/{OTHER}.upk'), b'second map')
            held = pack_card.read(z.read(f'CookedPCConsole/My_pack/{described["card"]["file"]}'))
            inside = z.read('CookedPCConsole/My_pack/README.txt').decode('latin-1')
        # the pack is one folder: the maps, the card, a README (LWR map packs plan, 6.1)
        self.assertLessEqual({'README.txt', 'pack.json', f'CookedPCConsole/My_pack/{VARIANT}.upk',
                              f'CookedPCConsole/My_pack/CIN_DropshipIntros_{VARIANT}.upk',
                              f'packages/{VARIANT}/manifest.json', f'packages/{OTHER}/manifest.json'}, names)
        self.assertFalse(any(n.startswith('XEW/') for n in names))
        self.assertEqual((described['schemaVersion'], described['folder'], described['id'], target.name),
                         (2, 'My_pack', 'My_pack', 'My_pack v1.zip'))
        self.assertEqual((r['folder'], r['version'], r['card']), ('My_pack', 1, described['card']['number']))
        self.assertEqual(described['card']['file'], 'LWRMapPack_%04d.upk' % r['card'])
        self.assertIn(described['card']['file'], inside)
        # the card: every record of both maps, each under the display name of the base record it replaces (a card
        # comments nothing out: LWR swaps a line in by its display name), then each map's landing zones
        self.assertEqual((held['PackName'], held['Format']), ('My pack v1', 1))
        self.assertEqual([(m['Name'], m['DisplayName']) for m in held['Maps']],
                         [(v, d) for v in (VARIANT, OTHER)
                          for d in (dep.field(record('bar'), 'DisplayName'), 'URB_Bar_Terror (Terror) |0', 'URB_Bar_Bomb (Bomb) |0')])
        self.assertEqual([m['bInRotation'] for m in held['Maps']], [True, True, False] * 2)
        self.assertTrue(all(f'CIN_DropshipIntros_{VARIANT}' in [x['MapName'] for x in m['StreamingMaps']] for m in held['Maps'][:3]))
        self.assertEqual({z_['MapName'] for z_ in held['LZArray']}, {VARIANT, OTHER})
        self.assertEqual(held['Pictures'], [])                           # the made-up install has no map pictures
        self.assertEqual(described['card']['lines'][0], described['maps'][0]['cardLines'][0])
        self.assertTrue(any('have the display name' in n for n in r['notes']))    # two maps replacing one: the later line wins
        self.assertIn('LONG WAR REBALANCE 3.00.00 beta 15', readme)
        self.assertIn('     the folder My_pack', readme)
        self.assertEqual((described['schema'], described['mode'], [m['variant'] for m in described['maps']]),
                         (manager.PACK_SCHEMA, 'replace', [VARIANT, OTHER]))
        self.assertEqual([m['donors'] for m in described['maps']], [[], []])      # no piece of another map in either
        # the README has each variant's records, Bar's records to take out of rotation and the landing zones
        self.assertIn(f'Name="{VARIANT}"', readme)
        self.assertIn(f'DisplayName="{OTHER} (Second bar, Terror) |0"', readme)
        self.assertIn('URB_Bar_Terror (Terror) |0', readme)
        self.assertIn('     URB_Bar_Bomb (Bomb) |0', readme)             # the council record is commented out too
        self.assertIn(f'Name="{VARIANT}",', readme)
        self.assertEqual(readme.count('DisplayName="URB_Bar_Bomb (Bomb) |0"'), 2)      # each variant's council record takes its name
        self.assertIn(f'LZArray=(MapName="{VARIANT}"', readme)
        self.assertEqual(described['maps'][0]['switch'], [dep.field(record('bar'), 'DisplayName'), 'URB_Bar_Terror (Terror) |0', 'URB_Bar_Bomb (Bomb) |0'])
        self.assertEqual(self.files(self.lwr), before)                    # a pack installs nothing
        # additional: nothing of the base map's to change
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        with zipfile.ZipFile(r['zip']) as z: readme = z.read('README.txt').decode('latin-1')
        self.assertNotIn('comment out', readme)
        self.assertEqual(r['name'], 'Bar remix')
        self.assertEqual(r['projects'], [])                               # no editor project unless asked for
        with zipfile.ZipFile(r['zip']) as z:
            self.assertNotIn('projects', json.loads(z.read('pack.json')))
            self.assertFalse(any(n.startswith('projects/') for n in z.namelist()))

    def test_a_pack_carries_the_editor_projects_when_asked(self):
        self.package()
        self.second()
        saved = self.store.path(ID).read_bytes()
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID, OTHER_ID], mode='additional', projectFiles=True))
        files = sorted(self.store.path(i).name for i in (ID, OTHER_ID))
        self.assertEqual(sorted(r['projects']), files)
        with zipfile.ZipFile(r['zip']) as z:
            self.assertEqual(z.read(f'projects/{self.store.path(ID).name}'), saved)       # byte for byte as saved
            described = json.loads(z.read('pack.json'))
            readme = z.read('README.txt').decode('latin-1')
        self.assertEqual(sorted(s['file'] for s in described['projects']), files)
        self.assertEqual({s['id'] for s in described['projects']}, {ID, OTHER_ID})
        self.assertIn('Editor projects.', readme)
        self.assertIn(f'projects\\{self.store.path(OTHER_ID).name}', readme)
        # a project saved after its build says so
        document = self.store.load(OTHER_ID)
        self.store.save(OTHER_ID, document, document['revision'])
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[OTHER_ID], mode='additional', projectFiles=True))
        with zipfile.ZipFile(r['zip']) as z: readme = z.read('README.txt').decode('latin-1')
        self.assertIn('saved after this build', readme)

    def test_a_pack_beside_the_maps_keeps_names_of_its_own_and_borrows_pictures(self):
        self.more_missions(self.lwr)
        self.package()
        import pictures
        with mock.patch.object(pictures, 'base_library', lambda cooked, name: 'UILibrary_MapImages' if name == 'URB_Bar' else None):
            r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID], mode='additional', name='Beside', author='A. N. Author'))
        with zipfile.ZipFile(r['zip']) as z:
            names = set(z.namelist())
            described = json.loads(z.read('pack.json'))
            held = pack_card.read(z.read(f'CookedPCConsole/Beside/{described["card"]["file"]}'))
            readme = z.read('README.txt').decode('latin-1')
        # every file of the pack is in its folder: each map holds its lighting inside it
        self.assertEqual({n for n in names if n.startswith('CookedPCConsole/')},
                         {f'CookedPCConsole/Beside/{n}' for n in described['folderFiles']})
        self.assertNotIn('cacheFiles', described)
        self.assertEqual(described['files'][f'{VARIANT}.upk'], hashlib.sha256(b'relit map 1').hexdigest())
        self.assertEqual(held['PackName'], 'Beside v1 by A. N. Author')
        self.assertIn('By A. N. Author.', readme)
        # beside the base map: no record has a name of the game's own
        own = {dep.field(record('bar'), 'DisplayName'), 'URB_Bar_Terror (Terror) |0', 'URB_Bar_Bomb (Bomb) |0'}
        self.assertEqual(len(held['Maps']), 3)
        self.assertFalse(own & {m['DisplayName'] for m in held['Maps']})
        self.assertEqual(held['Pictures'], [dict(Map=VARIANT, Picture='UILibrary_MapImages.URB_Bar')])
        self.assertEqual(described['maps'][0]['pictureFrom'], 'UILibrary_MapImages.URB_Bar')
        self.assertEqual(r['notes'], [])

    def test_a_build_with_a_texture_cache_is_left_out_of_a_pack_until_it_is_built_again(self):
        """Every build keeps its lightmaps inside its map (the game finds a .tfc only in CookedPCConsole itself, F-140),
        so no .tfc goes along with a pack: a build from before, its cache beside the map, is left out and says to
        build it again, and the project manager's list says so too."""
        self.package()
        self.second()
        cooked = self.output / VARIANT / 'CookedPCConsole'
        (cooked / 'Lighting_4242.tfc').write_bytes(b'lightmaps')
        m = json.loads((self.output / VARIANT / 'manifest.json').read_text(encoding='utf-8'))
        m['files']['CookedPCConsole/Lighting_4242.tfc'] = hashlib.sha256(b'lightmaps').hexdigest()
        m['cache'] = 'Lighting_4242'
        (self.output / VARIANT / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        player = self.player()
        listed = manager.listing(self.store, self.builds, player)
        self.assertTrue(any('texture cache beside the map' in w for w in self.row(listed)['warnings']))
        self.assertFalse(any('texture cache' in w for w in self.row(listed, OTHER_ID)['warnings']))
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional', name='Inside'))
        skipped, = r['skipped']
        self.assertEqual(skipped['id'], ID)
        self.assertIn('build the project again', skipped['error'])
        with zipfile.ZipFile(r['zip']) as z:
            names = set(z.namelist())
            described = json.loads(z.read('pack.json'))
            readme = z.read('README.txt').decode('latin-1')
        self.assertFalse([n for n in names if n.lower().endswith('.tfc')])
        self.assertEqual([p['variant'] for p in described['maps']], [OTHER])
        self.assertNotIn('.tfc', readme)
        self.assertEqual([p.name for p in (self.output / manager.PACKS).iterdir()], [Path(r['zip']).name])

    def real_intro(self, variant, moves=None):
        """The build's own copy of the landing intro made for real (intro_copy.make on the game's), in its manifest
        (files, intros, replaceStreams) with its report when the project moves the landing (`moves`)."""
        import intro_copy
        folder = self.output / variant
        copy = f'CIN_DropshipIntros_{variant}'
        report = intro_copy.make(INTRO, folder / 'CookedPCConsole' / f'{copy}.upk', 'URB_Bar', variant, moves)
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        m['files'][f'CookedPCConsole/{copy}.upk'] = hashlib.sha256((folder / 'CookedPCConsole' / f'{copy}.upk').read_bytes()).hexdigest()
        m.update(intros=[dict(stream='CIN_DropshipIntros', copy=copy)], replaceStreams={'CIN_DropshipIntros': copy})
        if moves: m['stages'] = [dict(stage='intro', stream='CIN_DropshipIntros', moved=report['moved'])]
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        return folder / 'CookedPCConsole' / f'{copy}.upk'

    @unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
    def test_a_packs_maps_share_one_copy_of_the_landing_intro(self):
        """F-142: one copy of the intro for all the pack's maps, each map's case after its base map's, in place of each
        build's own; a map whose landing flies otherwise than another's of its base keeps its own copy; a moved flight
        goes into the pack's copy."""
        import intro_copy
        shutil.copyfile(INTRO, self.lwr / 'XEW/XComGame/CookedPCConsole/CIN_DropshipIntros.upk')
        self.package()
        self.second()
        self.real_intro(VARIANT)
        self.real_intro(OTHER)
        player = self.player()
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional', name='Intro pack'))
        shared = f'CIN_DropshipIntros_Intro_pack_{r["card"]:04d}'
        with zipfile.ZipFile(r['zip']) as z:
            names = set(z.namelist())
            described = json.loads(z.read('pack.json'))
            held = pack_card.read(z.read(f'CookedPCConsole/Intro_pack/{described["card"]["file"]}'))
            readme = z.read('README.txt').decode('latin-1')
            copy = Path(self.temp.name) / f'{shared}.upk'
            copy.write_bytes(z.read(f'CookedPCConsole/Intro_pack/{shared}.upk'))
        self.assertFalse([n for n in names if f'CIN_DropshipIntros_{VARIANT}' in n or f'CIN_DropshipIntros_{OTHER}' in n])
        self.assertEqual(described['introFiles'], {f'{shared}.upk': dict(stream='CIN_DropshipIntros', maps=[VARIANT, OTHER])})
        for m in held['Maps']:
            self.assertIn(shared, [s['MapName'] for s in m['StreamingMaps']])
        for m in described['maps']:
            self.assertIn(f'{shared}.upk', m['files'])
            self.assertNotIn(f'CIN_DropshipIntros_{m["variant"]}.upk', m['files'])
            self.assertEqual(m['introShared'], [dict(stream='CIN_DropshipIntros', file=f'{shared}.upk',
                                                     instead=f'CIN_DropshipIntros_{m["variant"]}.upk')])
            self.assertTrue(all(f'MapName="{shared}"' in l for l in m['records'] + m['cardLines'] if 'MapName="CIN_' in l))
        self.assertEqual(readme.count(f'     {shared}.upk'), 1)        # in the files to copy once, for both maps
        self.assertIn(f'{shared}.upk: the landing intro', readme)
        q = intro_copy.lighting.Package(copy)
        cases = {q.name(i).split('.')[-1]: [t for _, t in e] for i, _, _, _, e in intro_copy.switches(q)}
        at = cases['SeqCond_SwitchString_8'].index('URB_Bar')
        self.assertEqual(cases['SeqCond_SwitchString_8'][at:at + 3], ['URB_Bar', VARIANT, OTHER])
        self.assertFalse(r['packed'][0]['warnings'] or r['packed'][1]['warnings'])
        # the second bar's landing moved: its flight differs from the first's, so it keeps its own copy
        move = dict(index=0, frame=dict(old=[[720.0, -1680.0, 0.0], 0], new=[[1103.0, -1681.0, 0.0], 16384]))
        own = self.real_intro(OTHER, [move])
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional', name='Intro pack 2'))
        with zipfile.ZipFile(r['zip']) as z:
            names = set(z.namelist())
            described = json.loads(z.read('pack.json'))
        folder = described['folder']
        self.assertIn(f'CookedPCConsole/{folder}/CIN_DropshipIntros_{OTHER}.upk', names)
        first, second = described['maps']
        self.assertIn('introShared', first)
        self.assertEqual(second['introOwn'][0]['file'], f'CIN_DropshipIntros_{OTHER}.upk')
        self.assertIn(f'otherwise than {VARIANT}', second['introOwn'][0]['why'])
        self.assertTrue(any(f'MapName="CIN_DropshipIntros_{OTHER}"' in l for l in second['cardLines']))
        # alone, its moved flight goes into the pack's copy, the place its own copy has
        r = manager.pack(self.store, self.builds, player, dict(projects=[OTHER_ID], mode='additional', name='Moved'))
        with zipfile.ZipFile(r['zip']) as z:
            described = json.loads(z.read('pack.json'))
            (file, intro), = described['introFiles'].items()
            copy.write_bytes(z.read(f'CookedPCConsole/Moved/{file}'))
        self.assertEqual(intro['maps'], [OTHER])
        mine = intro_copy.anchors(intro_copy.lighting.Package(copy), OTHER)
        theirs = intro_copy.anchors(intro_copy.lighting.Package(own), OTHER)
        self.assertEqual([(a['location'], a['rotation']) for a in mine], [(a['location'], a['rotation']) for a in theirs])

    def test_a_saved_pack_keeps_its_folder_and_number_and_counts_its_versions(self):
        self.package()
        self.second()
        player = self.player()
        cards = self.lwr / 'XEW/XComGame/CookedPCConsole/Someone'
        cards.mkdir()
        taken = [n for n in range(10000) if n not in (7, 4242)]
        for n in (0, 9999): (cards / ('LWRMapPack_%04d.upk' % n)).write_bytes(b'')
        import packs
        # every number but two is another record's or an installed card's: the draw takes one of the two
        packs.save(self.store.root, dict(schema=packs.SCHEMA, schemaVersion=1, name='Other', folder='Other', card=7, version=3, maps=[]))
        with mock.patch.object(packs, 'installed_cards', lambda cooked: {n: cards for n in taken}):
            r = manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional', name='Night maps vol. 2'))
        self.assertEqual((r['folder'], r['card'], r['version'], Path(r['zip']).name), ('Night_maps_vol_2', 4242, 1, 'Night_maps_vol_2 v1.zip'))
        saved = packs.load(self.store.root, 'Night_maps_vol_2')
        self.assertEqual((saved['name'], saved['card'], saved['version'], saved['maps']),
                         ('Night maps vol. 2', 4242, 1, [dict(project=ID, name='Bar remix', variant=VARIANT, mode='additional')]))
        # exported again as that pack, with another selection: the folder and number stay, the version counts on
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional', modes={OTHER_ID: 'replace'},
                                                                pack='Night_maps_vol_2', projectFiles=True))
        self.assertEqual((r['folder'], r['card'], r['version'], r['name']), ('Night_maps_vol_2', 4242, 2, 'Night maps vol. 2'))
        saved = packs.load(self.store.root, 'Night_maps_vol_2')
        self.assertEqual(([m['mode'] for m in saved['maps']], saved['projectFiles'], saved['zip']),
                         (['additional', 'replace'], True, 'Night_maps_vol_2 v2.zip'))
        with zipfile.ZipFile(r['zip']) as z:
            described = json.loads(z.read('pack.json'))
            self.assertEqual(pack_card.read(z.read(f'CookedPCConsole/Night_maps_vol_2/LWRMapPack_4242.upk'))['PackName'], 'Night maps vol. 2 v2')
        self.assertEqual(described['pack'], saved)
        # a new pack of the same name gets a folder of its own
        r2 = manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional', name='Night maps vol. 2'))
        self.assertEqual(r2['folder'], 'Night_maps_vol_2_2')
        # the list: the saved packs, a project that is gone named; a pack whose record is gone comes from its zip
        self.store.delete(OTHER_ID) if hasattr(self.store, 'delete') else self.store.path(OTHER_ID).unlink()
        listed = {p['folder']: p for p in manager.pack_list(self.store, self.builds)['packs']}
        self.assertEqual([m['missing'] for m in listed['Night_maps_vol_2']['maps']], [False, True])
        self.assertEqual(listed['Night_maps_vol_2']['source'], 'record')
        manager.pack_forget(self.store, self.builds, 'Night_maps_vol_2')
        self.assertTrue(Path(r['zip']).is_file())                        # no zip is deleted
        listed = {p['folder']: p for p in manager.pack_list(self.store, self.builds)['packs']}
        self.assertEqual((listed['Night_maps_vol_2']['source'], listed['Night_maps_vol_2']['version'], listed['Night_maps_vol_2']['card']),
                         ('zip', 2, 4242))
        with self.assertRaises(ProjectError): manager.pack_forget(self.store, self.builds, 'Night_maps_vol_2')
        # chosen from its zip: the record is made again, the number kept
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional', pack='Night_maps_vol_2'))
        self.assertEqual((r['card'], r['version']), (4242, 3))
        with self.assertRaises(ProjectError) as error:
            manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional', pack='Nothing'))
        self.assertEqual(error.exception.status, 404)

    def test_a_pack_from_before_cards_is_offered_from_its_zip(self):
        import packs
        folder = self.output / manager.PACKS
        folder.mkdir(parents=True)
        with zipfile.ZipFile(folder / 'Old pack 20261110-120000.zip', 'w') as z:
            z.writestr('pack.json', json.dumps(dict(schema=manager.PACK_SCHEMA, schemaVersion=1, name='Old pack', mode='mixed',
                                                    madeAt='2026-11-10T12:00:00',
                                                    maps=[dict(id=ID, name='Bar remix', variant=VARIANT, mode='replace'),
                                                          dict(id='gone-1', name='Gone', variant='Gone_1')])))
        with zipfile.ZipFile(folder / 'not a pack.zip', 'w') as z: z.writestr('x.txt', 'x')
        listed, = manager.pack_list(self.store, self.builds)['packs']
        self.assertEqual((listed['source'], listed['name'], listed['folder'], listed['card'], listed['version']),
                         ('zip', 'Old pack', 'Old_pack', None, 0))
        self.assertEqual([(m['project'], m['mode'], m['missing']) for m in listed['maps']],
                         [(ID, 'replace', False), ('gone-1', 'additional', True)])
        self.package()
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID], mode='replace', pack='Old_pack'))
        self.assertEqual((r['folder'], r['version'], r['name']), ('Old_pack', 1, 'Old pack'))
        self.assertEqual(packs.load(self.store.root, 'Old_pack')['card'], r['card'])

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell'), 'the pack\'s scripts run with Windows PowerShell')
    def test_a_packs_scripts_copy_the_folder_where_the_game_reads_cards(self):
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        self.more_missions(self.copy)
        self.card_game(self.copy)
        cooked = self.copy / 'XEW/XComGame/CookedPCConsole'
        (cooked / 'Other pack').mkdir()
        before = self.files(self.copy)
        held = sorted(str(p.relative_to(cooked)) for p in cooked.rglob('*'))
        self.package()
        self.second()
        player = self.player()
        r = manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional', name='Card pack'))
        folder = Path(self.temp.name) / 'unzipped cards'
        with zipfile.ZipFile(r['zip']) as z: z.extractall(folder)
        card = 'LWRMapPack_%04d.upk' % r['card']
        out = self.run_script(folder, 'Install.cmd', self.copy)
        self.assertIn('as the map pack folder Card_pack', out)
        self.assertIn('No file of the game was changed', out)
        self.assertEqual(self.files(self.copy), before)                  # no config file is touched
        there = cooked / 'Card_pack'
        self.assertEqual(sorted(p.name for p in there.iterdir()),
                         sorted([card, 'README.txt', f'{VARIANT}.upk', f'CIN_DropshipIntros_{VARIANT}.upk', f'{OTHER}.upk']))
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())
        self.assertEqual((there / card).read_bytes(), (folder / 'CookedPCConsole' / 'Card_pack' / card).read_bytes())
        # a newer version over it: the earlier one's files go first, the folder is the new version's
        (there / 'Stray.upk').write_bytes(b'someone else\'s')
        r2 = manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional', pack='Card_pack'))
        newer = Path(self.temp.name) / 'unzipped cards 2'
        with zipfile.ZipFile(r2['zip']) as z: z.extractall(newer)
        self.run_script(newer, 'Install.cmd', self.copy)
        self.assertFalse((there / f'{OTHER}.upk').exists())
        self.assertTrue((there / 'Stray.upk').is_file())                 # not the pack's: it stays
        self.assertEqual(pack_card.read((there / card).read_bytes())['PackName'], 'Card pack v2')
        # another pack with a card of the same number, and a map of the same name elsewhere, are named
        (cooked / 'Other pack' / card).write_bytes(b'x')
        (cooked / 'Other pack' / f'{VARIANT}.upk').write_bytes(b'x')
        out = self.run_script(newer, 'Install.cmd', self.copy)
        self.assertIn('card has the same number', out)
        self.assertIn(f'{VARIANT}.upk is also in Other pack', out)
        (cooked / 'Other pack' / card).unlink()
        (cooked / 'Other pack' / f'{VARIANT}.upk').unlink()
        (there / 'Stray.upk').unlink()
        # taken out: the folder and the cache gone, everything else as it was
        out = self.run_script(newer, 'Uninstall.cmd', self.copy)
        self.assertIn('Taken out', out)
        self.assertEqual(sorted(str(p.relative_to(cooked)) for p in cooked.rglob('*')), held)
        self.assertEqual(self.files(self.copy), before)
        self.assertEqual(list((self.copy / 'XCOM Map Workshop/packs').iterdir()), [])
        # the classic way asked for on that install, then the cards way over it: the lines come out again
        self.run_script_with(newer, 'Install.cmd', self.copy, 'classic')
        self.assertTrue((cooked / f'{VARIANT}.upk').is_file())
        self.assertEqual(len(self.records(self.copy, VARIANT)), 1)
        self.run_script(newer, 'Install.cmd', self.copy)
        self.assertEqual(self.files(self.copy), before)
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())
        self.assertTrue((there / f'{VARIANT}.upk').is_file())
        self.run_script(newer, 'Uninstall.cmd', self.copy)
        self.assertEqual(sorted(str(p.relative_to(cooked)) for p in cooked.rglob('*')), held)

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell'), 'the pack\'s scripts run with Windows PowerShell')
    def test_a_packs_scripts_install_it_as_the_editor_does_and_take_it_out_byte_for_byte(self):
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        self.more_missions(self.lwr)
        self.more_missions(self.copy)
        before = self.files(self.copy)
        cooked = self.copy / 'XEW/XComGame/CookedPCConsole'
        player = self.player()
        self.package()
        self.second()
        # all replacing, all additional, and one of each in one pack
        for mode, modes in (('replace', {}), ('additional', {}), ('mixed', {ID: 'replace'})):
            request = dict(projects=[ID, OTHER_ID], mode='additional' if modes else mode, modes=modes)
            r = manager.pack(self.store, self.builds, player, dict(request, name=f'Two bars {mode}'))
            self.assertEqual((r['mode'], [p['mode'] for p in r['packed']]),
                             (mode, ['replace', 'additional'] if modes else [mode, mode]))
            folder = Path(self.temp.name) / f'unzipped {mode}'
            with zipfile.ZipFile(r['zip']) as z:
                self.assertLessEqual({'Install.cmd', 'Uninstall.cmd', 'pack-tools/pack.ps1'}, set(z.namelist()))
                z.extractall(folder)
            # the scripts in one game folder, the editor in the other: the same config files
            out = self.run_script(folder, 'Install.cmd', self.copy)
            self.assertIn('Installed 2 map(s)', out)
            done = manager.install(self.store, self.builds, player, request)
            self.assertEqual([x['mode'] for x in done['results']], [p['mode'] for p in r['packed']])
            self.assertEqual(self.files(self.copy), self.files(self.lwr))
            self.assertEqual(len(self.records(self.copy, 'URB_Bar')), 3 if mode == 'additional' else 0)
            if modes:
                # the one that replaces has Bar's council record name, the one beside it a name of its own
                self.assertEqual([dep.field(self.records(self.copy, v)[2], 'DisplayName') for v in (VARIANT, OTHER)],
                                 ['URB_Bar_Bomb (Bomb) |0', f'{OTHER}_Bomb (Second bar, Council bomb) |0'])
                self.assertEqual([(self.row(done, i)['inGame']['rotation']) for i in (ID, OTHER_ID)], ['replace', 'additional'])
                with zipfile.ZipFile(r['zip']) as z: readme = z.read('README.txt').decode('latin-1')
                self.assertIn('some replacing the original maps, some as additional maps', readme)
                self.assertIn(f'a variant of URB_Bar, replacing it', readme)
                self.assertIn(f'a variant of URB_Bar, beside it', readme)
            self.assertEqual((cooked / f'{OTHER}.upk').read_bytes(), b'second map')
            packs = self.copy / 'XCOM Map Workshop/packs'
            self.assertEqual((packs / f'{r["folder"]}-before' / 'DefaultMaps.ini').read_bytes(), before['DefaultMaps.ini'])
            # installed again over itself: no second set of records
            self.run_script(folder, 'Install.cmd', self.copy)
            self.assertEqual(self.files(self.copy), self.files(self.lwr))
            # taken out: the config files byte for byte as before, the files gone, nothing left behind
            out = self.run_script(folder, 'Uninstall.cmd', self.copy)
            self.assertIn('exactly as it was before the pack', out)
            self.assertEqual(self.files(self.copy), before)
            self.assertFalse((cooked / f'{VARIANT}.upk').exists() or (cooked / f'{OTHER}.upk').exists())
            self.assertEqual(list(packs.iterdir()), [])
            self.assertIn('not installed', self.run_script(folder, 'Uninstall.cmd', self.copy))
            installs.reset(self.lwr)
        # a game with no record for the base map: nothing is changed
        maps = self.copy / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(dep.EOL.join(l for l in dep.lines_of(maps.read_bytes()) if dep.field(l, 'Name') != 'URB_Bar'))
        bare = self.files(self.copy)
        out = self.run_script_with(folder, 'Install.cmd', self.copy, code=1)
        self.assertIn('no record for its base map', out)
        self.assertEqual(self.files(self.copy), bare)

    def test_a_packs_scripts_and_the_editor_install_a_projects_own_landing_zones_alike(self):
        """Clear map plan, step C7: the project's own lines, on a game whose landing-zone file has none for the base
        map (they go at its end), by the pack's scripts and by the editor, and out again byte for byte."""
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        for game in (self.lwr, self.copy):
            (game / 'XEW/XComGame/Config/DefaultLZMutator.ini').write_bytes(
                dep.EOL.join([b'[XComLZMutator.XComLZMutator]', b'LZArray=(MapName="URB_Other",StartLoc=(X=1,Y=2,Z=3))', b'']))
        before = self.files(self.copy)
        player = self.player()
        lines = ['LZArray=(MapName="%s",ESpawnLoc=ESL_Normal,StartLoc=(X=1103,Y=1583,Z=64),StartDir=ELZD_East)' % VARIANT]
        self.package(zones=lines)
        request = dict(projects=[ID], mode='additional', modes={})
        r = manager.pack(self.store, self.builds, player, dict(request, name='Own zones'))
        folder = Path(self.temp.name) / 'unzipped own zones'
        with zipfile.ZipFile(r['zip']) as z:
            z.extractall(folder)
        packed = json.loads((folder / 'pack.json').read_text(encoding='utf-8'))['maps'][0]
        self.assertEqual((packed['landingZones'][1:], packed['ownZones']), (lines, True))
        self.run_script(folder, 'Install.cmd', self.copy)
        manager.install(self.store, self.builds, player, request)
        self.assertEqual(self.files(self.copy), self.files(self.lwr))
        lz = dep.lines_of(self.files(self.copy)['DefaultLZMutator.ini'])
        self.assertEqual(lz[-2], lines[0].encode())
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual(self.files(self.copy), before)

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell'), 'the pack\'s scripts run with Windows PowerShell')
    def test_a_packs_scripts_and_the_editor_write_a_projects_drop_in_exclusion_alike(self):
        """Editor spawns plan, SP8: a project that leaves scripted drop-ins where placed: pack.json carries the variant's
        ExcludeMaps lines, the README a step for DefaultRandomSpawns.ini, and the pack's scripts and the editor's
        campaign install write the same lines after the drop-in section's ExcludeMaps lines; the scripts take them out
        byte for byte. A game whose file has no drop-in section gets nothing from the scripts."""
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        for game in (self.lwr, self.copy):
            (game / 'XEW/XComGame/Config/DefaultMutatorLoader.ini').write_bytes(MUTATOR_LOADER)
            (game / 'XEW/XComGame/Config/DefaultRandomSpawns.ini').write_bytes(RANDOM_SPAWNS)
        spawns = lambda game: (game / 'XEW/XComGame/Config/DefaultRandomSpawns.ini').read_bytes()  # noqa: E731
        before = spawns(self.copy)
        player = self.player()
        self.package(exclusion=True)
        request = dict(projects=[ID], mode='additional', modes={})
        r = manager.pack(self.store, self.builds, player, dict(request, name='Drop-ins placed'))
        folder = Path(self.temp.name) / 'unzipped drop-ins'
        with zipfile.ZipFile(r['zip']) as z:
            z.extractall(folder)
            readme = z.read('README.txt').decode('latin-1')
        packed = json.loads((folder / 'pack.json').read_text(encoding='utf-8'))['maps'][0]
        self.assertEqual(packed['dropInExclusion'][1], f'ExcludeMaps = "{VARIANT}"')
        self.assertTrue(packed['dropInExclusion'][0].startswith(f';{VARIANT}: scripted drop-ins land where placed (XCOM Map Workshop'))
        self.assertIn('DefaultRandomSpawns.ini', readme)
        self.assertIn(f'ExcludeMaps = "{VARIANT}"', readme)
        self.run_script(folder, 'Install.cmd', self.copy)
        manager.install(self.store, self.builds, player, request)
        self.assertEqual(spawns(self.copy), spawns(self.lwr))
        lines = dep.lines_of(spawns(self.copy))
        self.assertEqual(lines.index(f'ExcludeMaps = "{VARIANT}"'.encode()), lines.index(b';ExcludeMaps = "DLC2_2_Deluge"') + 2)
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual(spawns(self.copy), before)
        # no drop-in section in the game's file: the scripts add nothing there
        other = dep.EOL.join([b'[XComLZMutator.XComSpawnMutator]', b'PLAYER_PROXIMITY = 29', b''])
        (self.copy / 'XEW/XComGame/Config/DefaultRandomSpawns.ini').write_bytes(other)
        self.run_script(folder, 'Install.cmd', self.copy)
        self.assertEqual(spawns(self.copy), other)
        self.run_script(folder, 'Uninstall.cmd', self.copy)

    def first_mission_bar(self, game):
        """Bar made what LWR's URB_CommercialAlley_EWI is: its abduction record, in rotation, is the one a new campaign's
        first mission asks for by name (installs.FIRST_MISSION), and no other record has that name."""
        path = game / 'XEW/XComGame/Config/DefaultMaps.ini'
        lines = [l for l in dep.lines_of(path.read_bytes()) if l != self.default]
        first = dep.set_field(record('bar'), 'DisplayName', installs.FIRST_MISSIONS[0])
        lines[lines.index(record('bar'))] = first
        path.write_bytes(dep.EOL.join(lines))
        return first

    def named(self, game, display):
        """The Names of the live records with this DisplayName."""
        maps = dep.lines_of(self.files(game)['DefaultMaps.ini'])
        return [dep.field(l, 'Name') for l in maps if dep.is_record(l) and dep.field(l, 'DisplayName') == display]

    def test_a_variant_replacing_the_first_missions_map_takes_its_record_name(self):
        # F-117: the first mission asks for its map's record by DisplayName although the record is in rotation; a
        # variant that replaces the map took a name of its own, its original's record was commented out, and a new
        # campaign's first mission found no map
        first = self.first_mission_bar(self.lwr)
        before = self.files(self.lwr)
        player = self.player()
        row = self.row(manager.listing(self.store, self.builds, player))
        self.assertEqual([(m['label'], m['inRotation'], m['byName'], m.get('firstMission')) for m in row['missions']],
                         [('Abduction', True, True, True)])
        self.assertTrue(any('first mission' in w for w in row['modeWarnings']['replace']))
        self.assertEqual(row['modeWarnings']['additional'], [])
        self.package()
        done = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))['results'][0]
        self.assertTrue(done['ok'], done)
        self.assertTrue(any('first mission' in w for w in done['warnings']), done['warnings'])
        mine, = self.records(self.lwr, VARIANT)
        self.assertEqual((dep.field(mine, 'DisplayName'), dep.unquoted(mine, 'bInRotation')), (installs.FIRST_MISSIONS[0], 'True'))
        self.assertEqual(self.named(self.lwr, installs.FIRST_MISSIONS[0]), [VARIANT])
        self.assertIn(b';' + first, dep.lines_of(self.files(self.lwr)['DefaultMaps.ini']))
        # beside the original, the variant has a name of its own and the original keeps the first mission
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        self.assertEqual(self.named(self.lwr, installs.FIRST_MISSIONS[0]), ['URB_Bar'])
        self.assertNotEqual(dep.field(self.records(self.lwr, VARIANT)[0], 'DisplayName'), installs.FIRST_MISSIONS[0])
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)
        # a build with its own records (mission types plan, D4) does the same
        line = dep.set_field(dep.set_field(first, 'Name', VARIANT), 'DisplayName', f'{VARIANT} (Bar remix, Abduction) |0')
        self.package(maps=[line.decode('latin-1')], record_missions=[[0]])
        manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))
        self.assertEqual(self.named(self.lwr, installs.FIRST_MISSIONS[0]), [VARIANT])
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell'), 'the pack\'s scripts run with Windows PowerShell')
    def test_a_packs_scripts_give_the_first_missions_name_to_the_variant_that_replaces_its_map(self):
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        self.first_mission_bar(self.lwr)
        self.first_mission_bar(self.copy)
        before = self.files(self.copy)
        player = self.player()
        self.package()
        request = dict(projects=[ID], mode='replace', modes={})
        r = manager.pack(self.store, self.builds, player, dict(request, name='First mission'))
        folder = Path(self.temp.name) / 'unzipped first mission'
        with zipfile.ZipFile(r['zip']) as z: z.extractall(folder)
        packed = json.loads((folder / 'pack.json').read_text(encoding='utf-8'))['maps'][0]
        self.assertEqual([dep.field(l.encode('latin-1'), 'DisplayName') for l in packed['records'][1:]], [installs.FIRST_MISSIONS[0]])
        self.assertTrue(any('first mission' in w for w in packed['warnings']), packed['warnings'])
        self.run_script(folder, 'Install.cmd', self.copy)
        self.assertEqual(self.named(self.copy, installs.FIRST_MISSIONS[0]), [VARIANT])
        manager.install(self.store, self.builds, player, request)
        self.assertEqual(self.files(self.copy), self.files(self.lwr))
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual(self.files(self.copy), before)

    def covert_only(self, *games):
        """Bar as the first mission's map with a covert extraction record too, and a build for covert extraction only
        (mission types plan, D4): its one record stands for Bar's second record. Returns (first, covert)."""
        for game in games:
            first = self.first_mission_bar(game)
            path = game / 'XEW/XComGame/Config/DefaultMaps.ini'
            lines = dep.lines_of(path.read_bytes())
            covert = dep.set_field(dep.set_field(first, 'MissionType', 'eMission_CovertOpsExtraction', quoted=False),
                                   'DisplayName', 'URB_Bar (Covert Extraction) |0')
            lines[lines.index(first) + 1:lines.index(first) + 1] = [covert]
            path.write_bytes(dep.EOL.join(lines))
        line = dep.set_field(dep.set_field(covert, 'Name', VARIANT), 'DisplayName', f'{VARIANT} (Bar remix, Covert extraction) |0')
        self.package(maps=[line.decode('latin-1')], record_missions=[[1]])
        folder = self.output / VARIANT
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        m['config']['missionsFromProject'] = True
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        return first, covert

    def test_a_variant_for_other_missions_leaves_the_first_missions_record_in_use(self):
        # F-118: replacing commented out every record of the base map, also those of missions the build has no record
        # for, so a variant for covert extraction only left a new campaign's first mission with no map
        first, covert = self.covert_only(self.lwr)
        before = self.files(self.lwr)
        player = self.player()
        replace = self.row(manager.listing(self.store, self.builds, player))['modeWarnings']['replace']
        self.assertTrue(any('Abduction: the build has no record' in w and 'first mission' in w for w in replace), replace)
        done = manager.install(self.store, self.builds, player, dict(projects=[ID], mode='replace'))['results'][0]
        self.assertEqual((done['ok'], done['switchedOff']), (True, 1))
        self.assertTrue(any('first mission' in w for w in done['warnings']), done['warnings'])
        self.assertEqual(self.records(self.lwr, 'URB_Bar'), [first])
        self.assertEqual(self.named(self.lwr, installs.FIRST_MISSIONS[0]), ['URB_Bar'])
        self.assertIn(b';' + covert, dep.lines_of(self.files(self.lwr)['DefaultMaps.ini']))
        # the Game maps window: the abduction record in use, the covert extraction record replaced by the project
        bar = next(m for m in gamemaps.listing(player)['maps'] if m['name'] == 'URB_Bar')
        self.assertEqual([(x['mission'], x['state'], x['by']) for x in bar['records'][:2]],
                         [('Abduction', 'on', None), ('Covert extraction', 'replaced', ['Bar remix'])])
        # an install written before standsFor replaced every record of its base map, and still does
        ledger = installs.read_ledger(self.lwr)
        old = [{k: v for k, v in e.items() if k != 'standsFor'} for e in ledger['rotation']]
        self.assertEqual(set(installs.replaced_records(dict(ledger, rotation=old), dep.lines_of(before['DefaultMaps.ini']))),
                         {first.decode('latin-1'), covert.decode('latin-1')})
        installs.reset(self.lwr)
        self.assertEqual(self.files(self.lwr), before)

    @unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell'), 'the pack\'s scripts run with Windows PowerShell')
    def test_a_packs_scripts_leave_the_records_its_maps_have_none_for_in_use(self):
        real = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq XComEW.exe'], capture_output=True, text=True).stdout
        if 'XComEW.exe' in real: self.skipTest('XCOM is running: the scripts refuse, as they should')
        first, covert = self.covert_only(self.lwr, self.copy)
        before = self.files(self.copy)
        player = self.player()
        request = dict(projects=[ID], mode='replace', modes={})
        r = manager.pack(self.store, self.builds, player, dict(request, name='Covert only'))
        folder = Path(self.temp.name) / 'unzipped covert only'
        with zipfile.ZipFile(r['zip']) as z: z.extractall(folder)
        packed = json.loads((folder / 'pack.json').read_text(encoding='utf-8'))['maps'][0]
        self.assertEqual((packed['switch'], packed['keep']), (['URB_Bar (Covert Extraction) |0'], [installs.FIRST_MISSIONS[0]]))
        readme = (folder / 'README.txt').read_bytes().decode('latin-1')
        self.assertIn("URB_Bar's own records to leave as they are", readme)
        self.run_script(folder, 'Install.cmd', self.copy)
        self.assertEqual(self.records(self.copy, 'URB_Bar'), [first])
        self.assertEqual(self.named(self.copy, installs.FIRST_MISSIONS[0]), ['URB_Bar'])
        manager.install(self.store, self.builds, player, request)
        self.assertEqual(self.files(self.copy), self.files(self.lwr))
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual(self.files(self.copy), before)
        # a pack from before switch comments out every record of the base map, as it did
        described = json.loads((folder / 'pack.json').read_text(encoding='utf-8'))
        for m in described['maps']: m.pop('switch'); m.pop('keep')
        (folder / 'pack.json').write_text(json.dumps(described), encoding='utf-8')
        self.run_script(folder, 'Install.cmd', self.copy)
        self.assertEqual(self.records(self.copy, 'URB_Bar'), [])
        self.assertIn('exactly as it was before the pack', self.run_script(folder, 'Uninstall.cmd', self.copy))
        self.assertEqual(self.files(self.copy), before)

    def test_install_pack_and_play_lease_their_packages_and_hold_their_guards(self):
        """Build queue plan, 9.4: a reader leases the packages it reads (the queue can't start those projects meanwhile)
        and holds each one's guard while it reads and copies it (no build swaps it); a project being built, or about
        to be, is left out with the reason; leases and guards are let go when the reader fails."""
        import publication
        self.package()
        self.second()
        player = self.player()
        seen = []

        def watching(real):
            def run(game, folder, *args, **kwargs):
                seen.append((self.builds.claim(ID, 'queue'), self.busy(folder.name)))
                return real(game, folder, *args, **kwargs)
            return run
        with mock.patch.object(installs, 'install_rotation', watching(installs.install_rotation)):
            manager.install(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        self.assertEqual(seen, [(False, True)])         # the queue waited, the guard was held
        self.assertEqual((self.builds.leases, self.busy(VARIANT)), ({}, False))
        # about to be built (the queue's claim): left out, with why
        self.assertTrue(self.builds.claim(ID, 'queue'))
        r = manager.install(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional'))
        results = {x['id']: x for x in r['results']}
        self.assertEqual(results[ID]['error'], 'It is building; it can be used when the build ends.')
        self.assertTrue(results[OTHER_ID]['ok'])
        self.assertTrue(self.row(r)['building'])        # the listing says so too
        with self.assertRaises(ProjectError) as error: player.play(dict(project=ID))
        self.assertIn('is building', error.exception.message)
        self.builds.unclaim(ID, 'queue')
        # the pack holds every package's guard while it zips, and lets go of all of them after, even when it fails
        held = []
        real_write = zipfile.ZipFile.write

        def write(zf, src, *args, **kwargs):
            held.append((self.busy(VARIANT), self.busy(OTHER)))
            return real_write(zf, src, *args, **kwargs)
        with mock.patch.object(zipfile.ZipFile, 'write', write):
            manager.pack(self.store, self.builds, player, dict(projects=[ID, OTHER_ID], mode='additional'))
        self.assertTrue(held and all(h == (True, True) for h in held))
        with mock.patch.object(installs, 'read_package', side_effect=OSError('torn')):
            with self.assertRaises(ProjectError):
                manager.pack(self.store, self.builds, player, dict(projects=[ID], mode='additional'))
        self.assertEqual((self.builds.leases, self.busy(VARIANT), self.busy(OTHER)), ({}, False, False))
        # Play in game the same way
        with mock.patch.object(installs, 'install_package', watching(installs.install_package)):
            seen.clear()
            player.play(dict(project=ID))
        self.assertEqual(seen, [(False, True)])
        with mock.patch.object(installs, 'install_package', side_effect=installs.InstallError('copy failed')):
            with self.assertRaises(ProjectError): player.play(dict(project=ID))
        self.assertEqual((self.builds.leases, self.busy(VARIANT)), ({}, False))

    def busy(self, variant):
        """Whether the variant's guard is held (by anyone)."""
        import publication
        try:
            with publication.guard(self.output, variant, wait=0):
                return False
        except publication.Busy:
            return True

    def test_the_routes_change_things_only_for_the_viewer_itself(self):
        player = self.player()
        self.package()
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
            status, listed = call('GET', '/manager.json')
            self.assertEqual((status, self.row(listed)['build']['buildId']), (200, f'{VARIANT}-1'))
            self.assertEqual(call('POST', '/manager/install', dict(projects=[ID], mode='replace'), origin='http://evil.example')[0], 403)
            self.assertEqual(call('POST', '/manager/install', dict(projects=[ID]))[0], 400)
            self.assertEqual(call('POST', '/manager/install', dict(projects=[ID], mode='replace', modes={ID: 'sideways'}))[0], 400)
            self.assertEqual(call('POST', '/manager/install', dict(projects=[], mode='replace'))[0], 400)
            self.assertEqual(call('GET', '/manager/install')[0], 405)
            self.assertEqual(self.records(self.lwr, VARIANT), [])
            status, r = call('POST', '/manager/install', dict(projects=[ID], mode='additional'))
            self.assertEqual((status, r['results'][0]['ok'], len(self.records(self.lwr, VARIANT))), (200, True, 1))
            status, r = call('POST', '/manager/pack', dict(projects=[ID], mode='additional'))
            self.assertEqual((status, Path(r['zip']).is_file()), (200, True))
            # the saved packs: listed, exported again by their folder, forgotten only by the viewer itself
            status, saved = call('GET', '/manager/packs.json')
            self.assertEqual((status, [(x['folder'], x['version'], x['source']) for x in saved['packs']]), (200, [(r['folder'], 1, 'record')]))
            status, again = call('POST', '/manager/pack', dict(projects=[ID], mode='additional', pack=r['folder']))
            self.assertEqual((status, again['version'], again['card']), (200, 2, r['card']))
            self.assertEqual(call('POST', '/manager/packs.json', dict())[0], 405)
            self.assertEqual(call('DELETE', f'/manager/packs/{r["folder"]}', origin='http://evil.example')[0], 403)
            self.assertEqual(call('DELETE', '/manager/packs/Nothing')[0], 404)
            status, saved = call('DELETE', f'/manager/packs/{r["folder"]}')
            self.assertEqual((status, [x['source'] for x in saved['packs']]), (200, ['zip']))
            status, listed = call('GET', '/gamemaps.json')
            bar = next(m for m in listed['maps'] if m['name'] == 'URB_Bar')
            self.assertEqual((status, [x['kind'] for x in bar['records']]), (200, ['own', 'rotation']))
            self.assertEqual(call('POST', '/gamemaps/undo', dict(variants=[VARIANT]), origin='http://evil.example')[0], 403)
            self.assertEqual(call('POST', '/gamemaps/use', dict(records=[bar['records'][0]['id']]))[0], 400)
            status, r = call('POST', '/gamemaps/use', dict(records=[bar['records'][0]['id']], use=False))
            self.assertEqual((status, r['changed'], self.records(self.lwr, 'URB_Bar')), (200, 1, []))
            status, r = call('POST', '/gamemaps/undo', dict(variants=[VARIANT]))
            self.assertEqual((status, r['undone'], self.records(self.lwr, VARIANT)), (200, [VARIANT], []))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
