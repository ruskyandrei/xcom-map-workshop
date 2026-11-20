"""The library of pieces across the game's maps (library.py): the index, the user's favourites file, the server's
routes and its scan runner. The scan of real maps and a piece's export read the configured install
(tools/viewer/settings.py) and skip without it."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lab'))
from catalogue import load_catalogue
import library
from projects import ProjectError
from viewer import Handler, LocalServer
import labpaths

BAR, NO_BAR = labpaths.install_map('URB_Bar')
KEY, OTHER = 'a' * 16, 'b' * 16
PNG = library.PNG + b'not much of a picture'


def piece(actor, cls='XComLevelActor', mesh='Kit.Meshes.Crate', size=1000, **changes):
    recipe = dict(actorClass=cls, archetype='None', parts=[dict(mesh=mesh, materials=[])], tint=None)
    out = dict(actor=actor, key=library.recipe_key(recipe), recipe=recipe, actorClass=cls, name=mesh.rsplit('.', 1)[-1],
               size=[96.0, 96.0, 96.0], hidden=False, partner=False, closure=dict(objects=4, bytes=size), refused=None,
               cuts=[])
    out.update(changes)
    return out


def donor(package, pieces, role='base', effects=()):
    return dict(package=package, role=role, sha256='0' * 64, size=1, mtime=1, pieces=pieces, effects=list(effects))


def effect_piece(actor, kind='effect', system='FX_SmokeB.Misc.Steam_Small', size=500, **changes):
    """scan_effects' row for an effect or a sound."""
    recipe = dict(v=1, kind=kind, actorClass='Emitter' if kind == 'effect' else 'AmbientSoundSimple',
                  system=system if kind == 'effect' else None)
    out = dict(kind=kind, actor=actor, key=library.recipe_key(recipe), recipe=recipe, name=system.rsplit('.', 1)[-1],
               actorClass=recipe['actorClass'], group='Smoke and steam' if kind == 'effect' else 'Machines',
               system=system if kind == 'effect' else None, emitters=['sprite'] if kind == 'effect' else [], lit=False,
               startsOn=True, scripted=False, waves=[] if kind == 'effect' else ['SoundAmbience.Hum'], seconds=None,
               cue=None, sharedCue=False, closure=dict(objects=10, bytes=size), refused=None, cuts=[], reason=None)
    out.update(changes)
    return out


class DonorTests(unittest.TestCase):
    def test_the_donors_are_the_maps_the_editor_lists_the_tutorial_map_among_them(self):
        # The tutorial's map has only commented-out records, which the map list takes (maplist.SWITCHED_OFF): a map
        # that can be opened, and a prefab saved from, must be a map whose pieces can be read back (the user's statue
        # of Act1_IntroLevel, 12 November 2026). Other commented-out records name no donor.
        import struct
        import tempfile
        from pathlib import Path as P
        from unittest import mock
        record = ('Maps=( MapFamily="%s", Name="%s", DisplayName="x", MissionType=eMission_Abduction, '
                  'StreamingMaps[0]=( MapName="%s" ) )')
        text = '\n'.join([record % ('URB_One', 'URB_One', 'URB_One_Stream'),
                           ';' + record % ('Act1_IntroLevel', 'Act1_IntroLevel', 'CIN_Intro'),
                           ';' + record % ('URB_Off', 'URB_Off', 'URB_Off_Stream')])
        with tempfile.TemporaryDirectory() as d:
            cooked = library.cooked_of(d)
            cooked.mkdir(parents=True)
            for name in ('URB_One', 'URB_One_Stream', 'Act1_IntroLevel', 'CIN_Intro', 'URB_Off', 'URB_Off_Stream'):
                (cooked / (name + '.upk')).write_bytes(struct.pack('<IHH', 0x9E2A83C1, 845, 64))
            with mock.patch('installs.maps_text', return_value=text):
                found = library.donors(P(d))
                # listed once for the install as it stands: asked again, no map is opened; a changed folder is seen
                with mock.patch('library._list_donors', side_effect=AssertionError('listed again')):
                    self.assertEqual(library.donors(P(d)), found)
                (cooked / 'URB_One_Stream.upk').unlink()
                self.assertEqual([name for name, _, _ in library.donors(P(d))], ['Act1_IntroLevel', 'CIN_Intro', 'URB_One'])
        self.assertEqual([(name, role) for name, role, _ in found],
                         [('Act1_IntroLevel', 'base'), ('CIN_Intro', 'stream'), ('URB_One', 'base'), ('URB_One_Stream', 'stream')])


class IndexTests(unittest.TestCase):
    def test_a_recipe_two_maps_place_is_one_entry_from_the_map_that_brings_least(self):
        index = library.build_index([
            donor('URB_Two', [piece('XComLevelActor_7', size=900), piece('XComLevelActor_8', size=900)]),
            donor('URB_One', [piece('XComLevelActor_3', size=5000, floor=True)]),
            dict(package='URB_Broken', role='stream', error='FormatError: no')])
        self.assertEqual([d['package'] for d in index['donors']], ['URB_One', 'URB_Two'])
        self.assertEqual(index['failed'], [dict(package='URB_Broken', role='stream', error='FormatError: no')])
        (entry,) = index['entries']
        self.assertEqual(entry['source'], dict(kind='map', package='URB_Two', level='base', actor='XComLevelActor_7'))
        self.assertEqual(entry['placed'], {'maps': 2, 'count': 3, 'in': [0, 1]})
        self.assertEqual(entry['floorMaps'], [0])
        self.assertEqual((entry['placeable'], entry['reason'], entry['family'], entry['kind'], entry['name']),
                         (True, None, 'scenery', 'Scenery', 'Crate'))
        self.assertEqual(entry['closure'], dict(objects=4, bytes=900))
        self.assertRegex(entry['key'], library.KEY)
        self.assertEqual(library.summary(index)['placeable'], 1)

    def test_another_material_or_tint_is_another_entry(self):
        a, b = piece('A_1'), piece('A_2')
        b['recipe'] = dict(b['recipe'], tint=[1.0, 0.5, 0.5, 1.0])
        b['key'] = library.recipe_key(b['recipe'])
        self.assertEqual(len(library.build_index([donor('URB_One', [a, b])])['entries']), 2)

    def test_what_is_not_placeable_says_why(self):
        import compiler
        self.addCleanup(setattr, compiler, 'FOREIGN_FAMILIES', compiler.FOREIGN_FAMILIES)
        compiler.FOREIGN_FAMILIES = ('scenery',)     # the family gate, as it stood before the families' game checks
        index = library.build_index([donor('URB_One', [
            piece('D_1', cls='XComLadder', mesh='Kit.Meshes.Barrel'),
            piece('L_1', mesh='Kit.Meshes.Helper', hidden=True),
            piece('L_2', mesh='Kit.Meshes.Body', partner=True),
            piece('L_3', mesh='Kit.Meshes.Wall', closure=None,
                  refused='Kit.Meshes.Wall_F: a FracturedStaticMesh has 512 bytes of native data and no layout here'),
            piece('V_1', cls='XComSomethingElse', mesh='Kit.Meshes.Odd')])])
        why = {e['name']: e['reason'] for e in index['entries']}
        self.assertTrue(all(not e['placeable'] for e in index['entries']))
        self.assertIn('a ladder', why['Barrel'])
        self.assertIn('hidden', why['Helper'])
        self.assertIn('linked to other pieces', why['Body'])
        blocked = {e['name']: e['blocked'] for e in index['entries']}
        self.assertEqual(blocked['Body'], 'assembly')
        self.assertTrue(set(blocked.values()) <= {'assembly', 'hidden', 'closure', 'family'}, blocked)
        self.assertIn('class FracturedStaticMesh', why['Wall'])
        self.assertIn('later step', why['Odd'])

    def test_the_families_a_game_check_passed_are_placeable(self):
        index = library.build_index([donor('URB_One', [
            piece('D_1', cls='XComDestructibleActor', mesh='Kit.Meshes.Barrel'),
            piece('F_1', cls='XComFracLevelActor', mesh='Kit.Meshes.Wall', cuts=['XComDestructibleActor']),
            piece('D_2', cls='XComDestructibleActor', mesh='Kit.Meshes.Linked', cuts=['XComDestructibleActor'])])])
        blocked = {e['name']: e['blocked'] for e in index['entries']}
        # (a fracturing piece's cut references are its columns' lists of its neighbours: no assembly)
        self.assertEqual(blocked, dict(Barrel=None, Wall=None, Linked='assembly'))

    def test_a_way_of_bringing_that_waits_for_its_check_holds_the_entry(self):
        import compiler
        self.addCleanup(setattr, compiler, 'FOREIGN_UNCHECKED', compiler.FOREIGN_UNCHECKED)
        pieces = [
            # a prop that lists what it takes down with it: the list is emptied, the prop comes
            piece('D_1', cls='XComDestructibleActor', mesh='Kit.Meshes.Pallet', cuts=['XComDestructibleActor'],
                  links=['AffectedChildren']),
            # one linked by anything else stays an assembly's part
            piece('D_2', cls='XComDestructibleActor', mesh='Kit.Meshes.Odd', cuts=['XComDestructibleActor'],
                  links=['AffectedChildren', 'SwapActor']),
            piece('D_3', cls='XComDestructibleActor', mesh='Kit.Meshes.Body', cuts=['XComFracLevelActor'],
                  links=['HidingPartner'], partner=True),
            # a piece whose Prefab can only come as a shell
            piece('D_4', cls='XComDestructibleActor', mesh='Kit.Meshes.ContainerWall', shelled=True),
            piece('L_1', mesh='Kit.Meshes.Crate')]
        compiler.FOREIGN_UNCHECKED = ('links', 'prefab')
        entries = {e['name']: e for e in library.build_index([donor('URB_One', pieces)])['entries']}
        self.assertEqual({n: (e['blocked'], e.get('held')) for n, e in entries.items()},
                         dict(Pallet=('check', ['links']), Odd=('assembly', ['links']), Body=('assembly', ['links']),
                              ContainerWall=('check', ['prefab']), Crate=(None, None)))
        self.assertIn('game test', entries['Pallet']['reason'])
        compiler.FOREIGN_UNCHECKED = ('prefab',)
        entries = {e['name']: e for e in library.build_index([donor('URB_One', pieces)])['entries']}
        self.assertEqual({n: e['placeable'] for n, e in entries.items()},
                         dict(Pallet=True, Odd=False, Body=False, ContainerWall=False, Crate=True))

    def test_an_assembly_is_one_entry_held_back_by_its_own_gate(self):
        import compiler
        car = piece('B_1', cls='XComDestructibleActor', mesh='Kit.Meshes.Body', cuts=['XComDestructibleActor'],
                    assembly=dict(family='car', members=3))
        door = piece('I_1', cls='XComInteractiveLevelActor', mesh='Kit.Meshes.Leaf', assembly=dict(family='door', members=2))
        van = piece('B_2', cls='XComDestructibleActor', mesh='Kit.Meshes.Van', assembly=dict(family='van', members=7))
        before = compiler.FOREIGN_ASSEMBLIES
        self.addCleanup(setattr, compiler, 'FOREIGN_ASSEMBLIES', before)
        compiler.FOREIGN_ASSEMBLIES = ()
        entries = {e['name']: e for e in library.build_index([donor('URB_One', [car, door, van])])['entries']}
        self.assertEqual({n: (e['family'], e['kind'], e['blocked'], e['assembly']['members']) for n, e in entries.items()},
                         dict(Body=('car', 'Car', 'family', 3), Leaf=('door', 'Door', 'family', 2),
                              Van=('van', 'Van', 'family', 7)))
        self.assertIn('a car', entries['Body']['reason'])
        self.assertIn('a van', entries['Van']['reason'])
        compiler.FOREIGN_ASSEMBLIES = ('car', 'door')
        entries = {e['name']: e for e in library.build_index([donor('URB_One', [car, door, van])])['entries']}
        # (what a whole car's glass lists of its neighbours is cut, and no reason to hold it back)
        self.assertEqual({n: e['placeable'] for n, e in entries.items()}, dict(Body=True, Leaf=True, Van=False))

    def test_effects_and_sounds_are_entries_of_their_own(self):
        """The base maps' effects and ambient sounds (scan_effects, stage FX4): one entry per recipe, from the map that
        brings least; held by the foreign gate until their game check, never by a later step's refusal."""
        import compiler
        index = library.build_index([
            donor('URB_One', [piece('XComLevelActor_3')], effects=[effect_piece('Emitter_1', size=900),
                                                                    effect_piece('AmbientSoundSimple_2', kind='sound', system='Hum')]),
            donor('URB_Two', [], effects=[effect_piece('Emitter_7', size=300), effect_piece('Emitter_8', size=300)])])
        self.assertEqual([d['effects'] for d in index['donors']], [2, 2])
        fx = {e['name']: e for e in index['entries'] if e['family'] in library.EFFECT_FAMILIES}
        steam, hum = fx['Steam_Small'], fx['Hum']
        self.assertEqual(steam['source'], dict(kind='map', package='URB_Two', level='base', actor='Emitter_7'))
        self.assertEqual(steam['placed'], {'maps': 2, 'count': 3, 'in': [0, 1]})
        self.assertEqual((steam['family'], steam['kind'], steam['actorClass'], steam['system'], steam['emitters']),
                         ('effect', 'Smoke and steam', 'Emitter', 'FX_SmokeB.Misc.Steam_Small', ['sprite']))
        self.assertEqual((hum['family'], hum['kind'], hum['waves']), ('sound', 'Machines', ['SoundAmbience.Hum']))
        self.assertNotIn('mesh', steam)
        gated = 'effect' not in compiler.FOREIGN_FAMILIES
        self.assertEqual((steam['placeable'], steam['blocked']), (not gated, 'family' if gated else None))
        if gated:
            self.assertIn('an effect', steam['reason'])
        # what the foreign gate lists is placeable, in a fresh index and in one read back
        self.addCleanup(setattr, compiler, 'FOREIGN_FAMILIES', compiler.FOREIGN_FAMILIES)
        compiler.FOREIGN_FAMILIES = compiler.FOREIGN_FAMILIES + ('effect', 'sound')
        again = library.build_index([donor('URB_One', [], effects=[effect_piece('Emitter_1')])])
        self.assertEqual(again['entries'][0]['blocked'], None)
        with tempfile.TemporaryDirectory() as d:
            path = library.index_path(d)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(index), encoding='utf-8')
            read = {e['name']: e for e in library.load_index(d)['entries']}
            self.assertEqual((read['Steam_Small']['placeable'], read['Hum']['placeable']), (True, True))

    def test_lens_flares_are_entries_of_their_own(self):
        """The base maps' lens flares (stage FX6b, index 10): one entry per recipe, family flare, held by the foreign
        gate until their game check."""
        import compiler
        import effects_library

        def glare(actor, template='FX_Lens_Flares.LF_Alien_Ambient_A', **changes):
            recipe = dict(v=1, kind='flare', actorClass='LensFlareSource', template=template, colour=[3.0, 0.5, 0.2, 1.0])
            return effect_piece(actor, kind='flare', system=template, **dict(dict(
                key=library.recipe_key(recipe), recipe=recipe, actorClass='LensFlareSource', group=effects_library.FLARE_KIND,
                emitters=[], waves=[], flare=template, colour=[3.0, 0.5, 0.2, 1.0], closure=dict(objects=40, bytes=50000)),
                **changes))
        self.assertGreaterEqual(library.INDEX_VERSION, 10)
        self.assertIn('flare', library.EFFECT_FAMILIES)
        index = library.build_index([
            donor('AlienBase01', [], effects=[glare('LensFlareSource_1'), glare('LensFlareSource_3'), effect_piece('Emitter_1'),
                                              glare('LensFlareSource_9', template='FX_Lens_Flares.LF_Riding', closure=None,
                                                    reason='it rides on SkeletalMeshActor_1 and moves with it')]),
            donor('URB_Two', [], effects=[glare('LensFlareSource_0')])])
        by = {e['name']: e for e in index['entries']}
        one = by['LF_Alien_Ambient_A']
        self.assertEqual((one['family'], one['kind'], one['actorClass'], one['flare'], one['colour'], one['system'], one['waves']),
                         ('flare', 'Lens flare', 'LensFlareSource', 'FX_Lens_Flares.LF_Alien_Ambient_A', [3.0, 0.5, 0.2, 1.0], None, []))
        self.assertEqual(one['placed'], {'maps': 2, 'count': 3, 'in': [0, 1]})
        self.assertEqual(one['closure'], dict(objects=40, bytes=50000))
        gated = 'flare' not in compiler.FOREIGN_FAMILIES or not compiler.FAMILIES['flare']['builds']
        self.assertEqual((one['placeable'], one['blocked']), (not gated, 'family' if gated else None))
        if gated:
            self.assertIn('a lens flare', one['reason'])
        self.assertEqual((by['LF_Riding']['blocked'], by['LF_Riding']['placeable']), ('unavailable', False))
        self.assertIn('rides on', by['LF_Riding']['reason'])
        # (an effect's entry has the flare's fields empty)
        self.assertEqual((by['Steam_Small']['flare'], by['Steam_Small']['colour']), (None, None))

    def test_an_effect_that_can_not_be_brought_says_why(self):
        index = library.build_index([donor('URB_One', [], effects=[
            effect_piece('Emitter_1', system='FX.Landing', closure=None,
                         reason='it is one of the landing\'s actors, which Long War\'s landing mutator takes out'),
            effect_piece('Emitter_2', system='FX.Movie', closure=None,
                         refused='FX.Movie.T: a TextureMovie has 900 bytes of native data and no layout here'),
            effect_piece('Emitter_3', system='FX.Riding', cuts=['InterpActor'])])])
        why = {e['name']: (e['blocked'], e['reason'], e['placeable']) for e in index['entries']}
        self.assertEqual(why['Landing'][0], 'unavailable')
        self.assertIn('landing mutator', why['Landing'][1])
        self.assertEqual(why['Movie'][:1] + (('TextureMovie' in why['Movie'][1]),), ('closure', True))
        self.assertEqual(why['Riding'][0], 'closure')
        self.assertIn('InterpActor', why['Riding'][1])
        self.assertFalse(any(v[2] for v in why.values()))

    def test_a_placeable_instance_is_the_exemplar_before_a_smaller_one_that_is_not(self):
        index = library.build_index([donor('URB_One', [piece('A_1', size=10, hidden=True)]),
                                     donor('URB_Two', [piece('A_2', size=999)])])
        (entry,) = index['entries']
        self.assertEqual((entry['source']['package'], entry['placeable']), ('URB_Two', True))


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'library.json'

    def test_made_on_first_write_and_a_stale_revision_is_refused(self):
        self.assertEqual(library.load_state(self.path), library.empty_state())
        self.assertFalse(self.path.exists())
        saved = library.save_state(dict(favourites=[dict(key=KEY, name='Crate')], recent=[]), 0, self.path)
        self.assertEqual((saved['revision'], saved['favourites'][0]['key'], saved['favourites'][0]['name']), (1, KEY, 'Crate'))
        self.assertTrue(saved['favourites'][0]['addedAt'])
        self.assertEqual(library.load_state(self.path), saved)
        with self.assertRaises(ProjectError) as stale:
            library.save_state(dict(favourites=[], recent=[]), 0, self.path)
        self.assertEqual((stale.exception.status, stale.exception.extra), (409, dict(revision=1)))
        self.assertEqual(library.load_state(self.path), saved)
        self.assertEqual(library.save_state(dict(favourites=[], recent=[]), 1, self.path)['revision'], 2)

    def test_recent_keeps_thirty_and_a_key_once(self):
        keys = ['%016x' % n for n in range(40)]
        saved = library.save_state(dict(favourites=[dict(key=KEY), dict(key=KEY)],
                                        recent=[dict(key=k, name='n') for k in keys]), 0, self.path)
        self.assertEqual([r['key'] for r in saved['recent']], keys[:30])
        self.assertEqual(len(saved['favourites']), 1)

    def test_what_is_not_a_list_of_keys_is_refused(self):
        for bad in (None, [], dict(favourites=[]), dict(favourites=[dict(key='../x')], recent=[]),
                    dict(favourites='x', recent=[]), dict(favourites=[], recent=[dict(name='no key')])):
            with self.assertRaises(ProjectError) as refused:
                library.save_state(bad, 0, self.path)
            self.assertEqual(refused.exception.status, 400, bad)
        self.assertFalse(self.path.exists())

    def test_a_malformed_file_is_reported_and_left_alone(self):
        for text in ('{not json', json.dumps(dict(schema='something-else', schemaVersion=1)),
                     json.dumps(dict(library.empty_state(), favourites='x'))):
            self.path.write_text(text, encoding='utf-8')
            for act in (lambda: library.load_state(self.path),
                        lambda: library.save_state(dict(favourites=[], recent=[]), 0, self.path)):
                with self.assertRaises(ProjectError) as broken:
                    act()
                self.assertEqual(broken.exception.status, 500)
            self.assertEqual(self.path.read_text(encoding='utf-8'), text)

    def test_two_saves_at_once_never_both_win(self):
        """Review finding 21: two windows save from revision 0 at once (a star each, or a star and a recently used
        piece): one gets revision 1, the other a 409 with that revision, and the accepted change is the one on disk;
        reloaded and applied again, the second gets its own revision."""
        both_read = threading.Barrier(2)
        real = library.load_state
        def slow_read(path=None):
            state = real(path)
            try: both_read.wait(timeout=1)      # each would have read revision 0 before either writes
            except threading.BrokenBarrierError: pass
            return state
        results = {}
        def save(name, document):
            try: results[name] = library.save_state(document, 0, self.path)['revision']
            except ProjectError as error: results[name] = (error.status, error.extra.get('revision'))
        other = '%016x' % 7
        from unittest import mock
        with mock.patch.object(library, 'load_state', slow_read):
            threads = [threading.Thread(target=save, args=('star', dict(favourites=[dict(key=KEY)], recent=[]))),
                       threading.Thread(target=save, args=('recent', dict(favourites=[], recent=[dict(key=other)])))]
            for t in threads: t.start()
            for t in threads: t.join(timeout=20)
        self.assertEqual(sorted(results.values(), key=str), sorted([1, (409, 1)], key=str))
        winner = next(name for name, value in results.items() if value == 1)
        on_disk = library.load_state(self.path)
        self.assertEqual(on_disk['revision'], 1)
        self.assertEqual(bool(on_disk['favourites']), winner == 'star')
        merged = dict(favourites=[dict(key=KEY)], recent=[dict(key=other)])
        self.assertEqual(library.save_state(merged, 1, self.path)['revision'], 2)
        self.assertEqual([p.name for p in self.path.parent.glob('*.part')], [])


INDEX = dict(version=library.INDEX_VERSION, exporterVersion=19, scannedAt='2026-11-11T12:00:00', seconds=1.0,
             donors=[dict(package='URB_One', role='base', sha256='0' * 64, size=1, mtime=1, pieces=1)], failed=[],
             entries=[dict(key=KEY, name='Crate', placeable=True)])
# a scan that takes no install: it says how far it is and writes an index
SCAN = ("import json, sys, pathlib\n"
        "print('progress: scanning the maps 0/2', flush=True)\n"
        "print('progress: scanning the maps 2/2', flush=True)\n"
        "p = pathlib.Path(sys.argv[1]) / 'library'\n"
        "p.mkdir(parents=True, exist_ok=True)\n"
        "(p / 'index.json').write_text(sys.argv[2])\n"
        "print('done')\n")


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'cache').mkdir()
        (self.root / 'game' / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
        (self.root / 'game' / 'XEW' / 'XComGame' / 'Config').mkdir()
        (self.root / 'game' / 'XEW' / 'XComGame' / 'Config' / 'DefaultMaps.ini').write_bytes(b'[XComGame.XComMapManager]')
        self.serve()

    def serve(self, command=None):
        cache = self.root / 'cache'
        command = command or (lambda game: [sys.executable, '-c', SCAN, str(cache), json.dumps(INDEX)])
        self.runner = library.LibraryRunner(cache, None, command=command, state=self.root / 'library.json')
        self.runner.install = lambda: self.root / 'game'
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(cache, allow_empty=True),
                                                       library=self.runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.base = f'http://127.0.0.1:{server.server_port}'
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))

    def call(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, method=method,
                          headers={'Content-Type': 'image/png' if raw is not None else 'application/json', **(headers or {})})
        try:
            with urlopen(request) as response:
                payload = response.read()
                return response.status, json.loads(payload) if response.headers['Content-Type'] == 'application/json' else payload
        except HTTPError as error: return error.code, json.load(error)

    def test_a_scan_is_followed_and_its_index_served(self):
        status, before = self.call('GET', '/library.json')
        self.assertEqual((status, before['status']['ready'], before['status']['scan']['state'], before['index']),
                         (200, False, 'idle', None))
        self.assertEqual(self.call('POST', '/library/scan')[0], 202)
        for _ in range(100):
            scan = self.call('GET', '/library/scan.json')[1]
            if scan['state'] != 'running': break
            time.sleep(0.1)
        self.assertEqual((scan['state'], scan['error'], scan['progress']['done'], scan['progress']['fraction']),
                         ('ready', None, 2, 1.0))
        status, after = self.call('GET', '/library.json?index=1')
        self.assertEqual((after['index'], after['thumbs']), (INDEX, []))
        self.assertEqual((after['status']['ready'], after['status']['summary']['entries'],
                          after['status']['summary']['placeable']), (True, 1, 1))
        # the install has no such donor any more: the index says it is behind
        self.assertEqual(after['status']['stale'], dict(changed=['URB_One'], missing=[]))
        self.assertIsNone(self.call('GET', '/library.json')[1]['index'])

    def test_a_scan_that_fails_says_its_last_line(self):
        self.serve(lambda game: [sys.executable, '-c', "import sys; print('no maps here'); sys.exit(3)"])
        self.call('POST', '/library/scan')
        for _ in range(100):
            scan = self.call('GET', '/library/scan.json')[1]
            if scan['state'] != 'running': break
            time.sleep(0.1)
        self.assertEqual((scan['state'], scan['error']), ('failed', 'no maps here'))

    def test_the_favourites_outlast_the_server_and_a_stale_write_is_refused(self):
        self.assertEqual(self.call('GET', '/library/state.json'), (200, library.empty_state()))
        body = dict(expectedRevision=0, document=dict(favourites=[dict(key=KEY, name='Crate')], recent=[dict(key=OTHER)]))
        status, saved = self.call('PUT', '/library/state.json', body)
        self.assertEqual((status, saved['revision']), (200, 1))
        status, refused = self.call('PUT', '/library/state.json', body)
        self.assertEqual((status, refused['revision']), (409, 1))
        self.assertEqual(self.call('PUT', '/library/state.json', dict(expectedRevision=1, document=dict(favourites=3)))[0], 400)
        self.serve()                                                # another server on the same folder
        status, kept = self.call('GET', '/library/state.json')
        self.assertEqual((kept['revision'], [f['key'] for f in kept['favourites']], [r['key'] for r in kept['recent']]),
                         (1, [KEY], [OTHER]))

    def test_thumbnails_are_kept_by_key(self):
        self.assertEqual(self.call('GET', f'/library/thumbs/{KEY}.png')[0], 404)
        self.assertEqual(self.call('PUT', f'/library/thumbs/{KEY}.png', raw=PNG), (200, dict(ok=True)))
        self.assertEqual(self.call('GET', f'/library/thumbs/{KEY}.png'), (200, PNG))
        self.assertEqual(self.runner.thumbs(), [KEY])      # the index's answer lists the pictures kept
        self.assertEqual((self.root / 'cache' / 'library' / 'thumbs' / f'{KEY}.png').read_bytes(), PNG)
        self.assertEqual(self.call('PUT', f'/library/thumbs/{KEY}.png', raw=b'GIF89a')[0], 400)
        self.assertEqual(self.call('PUT', '/library/thumbs/nokey.png', raw=PNG)[0], 400)
        self.assertEqual(self.call('PUT', f'/library/thumbs/{KEY}.png', raw=PNG + bytes(library.THUMB_LIMIT))[0], 400)

    def test_the_look_pickers_pictures_are_kept_by_key_and_listed(self):
        # (the look picker plan, P0) larger pictures, a folder of their own, listed for the picker
        self.assertEqual(self.call('GET', '/library/pictures.json'), (200, dict(pictures=[])))
        self.assertEqual(self.call('GET', f'/library/pictures/{KEY}.png')[0], 404)
        big = PNG + bytes(library.THUMB_LIMIT)          # (more than a thumbnail takes)
        self.assertEqual(self.call('PUT', f'/library/pictures/{KEY}.png', raw=big), (200, dict(ok=True)))
        self.assertEqual(self.call('GET', f'/library/pictures/{KEY}.png'), (200, big))
        self.assertEqual(self.call('GET', '/library/pictures.json'), (200, dict(pictures=[KEY])))
        self.assertEqual(self.runner.thumbs(), [])     # (not the Add panel's thumbnails)
        self.assertEqual(self.call('PUT', f'/library/pictures/{KEY}.png', raw=PNG + bytes(library.PICTURE_LIMIT))[0], 400)
        self.assertEqual(self.call('PUT', '/library/pictures/nokey.png', raw=PNG)[0], 400)

    def test_changes_come_from_the_page_only_and_files_from_the_pieces_folder_only(self):
        elsewhere = {'Origin': 'http://example.invalid'}
        self.assertEqual(self.call('PUT', '/library/state.json', dict(expectedRevision=0, document={}), elsewhere)[0], 403)
        self.assertEqual(self.call('POST', '/library/scan', headers=elsewhere)[0], 403)
        self.assertEqual(self.call('PUT', f'/library/thumbs/{KEY}.png', raw=PNG, headers=elsewhere)[0], 403)
        folder = self.root / 'cache' / 'library' / 'pieces' / 'URB_One' / 'abc-v19'
        folder.mkdir(parents=True)
        (folder / 'mesh-1.glb').write_bytes(b'glTF')
        (self.root / 'cache' / 'library' / 'secret.txt').write_text('no')
        self.assertEqual(self.call('GET', '/cache-library/URB_One/abc-v19/mesh-1.glb'), (200, b'glTF'))
        for path in ('/cache-library/../secret.txt', '/cache-library/%2e%2e/secret.txt', '/cache-library/URB_One/../../secret.txt'):
            with self.assertRaises(HTTPError) as denied:
                urlopen(self.base + path)
            self.assertEqual(denied.exception.code, 404, path)
        self.assertEqual(self.call('GET', '/library/piece.json?package=../x&actor=A_1')[0], 400)
        self.assertEqual(self.call('GET', '/library/piece.json?package=URB_One&actor=A_1')[0], 404)    # no such donor

    def test_a_server_without_a_library_says_so(self):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(self.root / 'cache', allow_empty=True)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))
        self.base = f'http://127.0.0.1:{server.server_port}'
        self.assertEqual(self.call('GET', '/library.json')[0], 404)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class GameTests(unittest.TestCase):
    """Two maps of the install scanned, and a piece exported."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.cache = Path(cls.temp.name)
        cls.game = BAR.parents[3]
        cls.index = library.scan(cls.game, cls.cache, jobs=2, only=['URB_Bar', 'urb_policestation'])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_index_of_two_maps(self):
        index = self.index
        self.assertEqual([(d['package'], d['role']) for d in index['donors']],
                         [('URB_Bar', 'base'), ('URB_PoliceStation', 'base')])
        self.assertEqual(index['failed'], [])
        self.assertEqual(library.load_index(self.cache), index)
        pieces = [e for e in index['entries'] if e['family'] not in library.EFFECT_FAMILIES]
        self.assertEqual(sum(e['placed']['count'] for e in pieces), sum(d['pieces'] for d in index['donors']))
        self.assertEqual(len({e['key'] for e in index['entries']}), len(index['entries']))
        both = [e for e in pieces if e['placed']['in'] == [0, 1]]
        self.assertGreater(len(both), 10)                               # recipes both maps place: one entry each
        lamp = next(e for e in pieces if e['mesh'] == 'parkLampPost.Meshes.ParkLampPost_B')
        self.assertEqual((lamp['placeable'], lamp['family'], lamp['source']['package'], lamp['placed']['in'], lamp['cuts']),
                         (True, 'scenery', 'URB_PoliceStation', [1], []))
        self.assertGreater(lamp['closure']['bytes'], 30000)             # against a map with none of it
        self.assertTrue(all(20 < v < 400 for v in lamp['size']), lamp['size'])   # a post, by its mesh's bounds
        for e in pieces:
            self.assertEqual(e['placeable'], e['reason'] is None)
            if e['placeable']:
                import compiler
                self.assertIn(e['family'], compiler.FOREIGN_ASSEMBLIES if e.get('assembly') else compiler.FOREIGN_FAMILIES)
                self.assertFalse(e['hidden'])
                self.assertIsNotNone(e['closure'])
        # a car is one entry with all its parts (Police Station's sedans: body, glass, and a light bar or doors); a
        # van is listed and can't be placed; neither's parts are entries of their own
        cars = [e for e in index['entries'] if e.get('assembly') and e['family'] == 'car']
        self.assertGreater(len(cars), 3)
        self.assertTrue(all(e['assembly']['members'] >= 2 and e['kind'] == 'Car' and e['actorClass'] == 'XComDestructibleActor'
                            for e in cars))
        # a van is one entry too, and what it brings counts its building and floor volumes with their brushes
        import compiler
        vans = [e for e in index['entries'] if e['family'] == 'van']
        self.assertTrue(vans and all(e['closure'] and e['assembly']['members'] >= 5 for e in vans), vans)
        self.assertTrue(all(e['placeable'] == ('van' in compiler.FOREIGN_ASSEMBLIES) for e in vans))
        self.assertFalse([e for e in pieces if not e.get('assembly') and e['recipe']['parts'][0]['mesh'].endswith('Glass_FRACTURED')])
        doors = [e for e in index['entries'] if e.get('assembly') and e['family'] == 'door']
        self.assertTrue(doors and all(e['assembly']['members'] == 2 and e['actorClass'] == 'XComInteractiveLevelActor' for e in doors))
        self.assertEqual(library.stale(index, self.game)[0], [])
        self.assertGreater(len(library.stale(index, self.game)[1]), 100)   # the install's other donors

    def test_the_base_maps_effects_and_sounds_are_entries(self):
        import compiler
        import effects_library
        index = self.index
        fx = [e for e in index['entries'] if e['family'] in library.EFFECT_FAMILIES]
        self.assertEqual(sum(e['placed']['count'] for e in fx), sum(d['effects'] for d in index['donors']))
        self.assertEqual(index['donors'][0]['effects'], 78)            # Bar's 71 effects, 5 ambient sounds, 2 lens flares
        for e in fx:
            self.assertEqual(e['placeable'], e['reason'] is None)
            self.assertIn(e['blocked'], (None, 'family', 'unavailable', 'closure'))
            self.assertEqual(e['kind'], effects_library.kind_of(e['family'], e['system'] or (e['waves'] or [e['cue']])[0]))
        # the landing's (the grounded Skyranger's idle glow and sound, its dust): not brought
        landing = [e for e in fx if e['name'] in ('P_Skyranger_Idle', 'P_Skyranger_Ground_Periphery', 'DropshipIdle')]
        # (the two maps' own recipes of them: each map's are placed its own way)
        self.assertEqual({e['name'] for e in landing}, {'P_Skyranger_Idle', 'P_Skyranger_Ground_Periphery', 'DropshipIdle'})
        self.assertTrue(all(e['blocked'] == 'unavailable' and 'landing' in e['reason'] for e in landing))
        steam = next(e for e in fx if e['system'] == 'FX_SmokeB.Misc.Steam_Small')
        self.assertEqual((steam['family'], steam['kind'], steam['actorClass']), ('effect', 'Smoke and steam', 'Emitter'))
        self.assertEqual(steam['blocked'], None if 'effect' in compiler.FOREIGN_FAMILIES else 'family')
        self.assertGreater(steam['closure']['bytes'], 1000)
        music = next(e for e in fx if e['waves'] == ['SoundBarMuzak.BarMuzakStereo'])
        self.assertEqual((music['family'], music['kind'], music['source']['actor'], music['sharedCue']),
                         ('sound', 'Music and voices', 'AmbientSoundSimple_2', False))
        self.assertGreater(music['seconds'], 60)
        # Bar's two lens flares are one entry (one template, one colour), which brings its template and archetype
        glare, = [e for e in fx if e['family'] == 'flare']
        self.assertEqual((glare['name'], glare['kind'], glare['flare'], glare['placed']['count'], glare['cuts']),
                         ('LF_XCom_Base_C', 'Lens flare', 'FX_Lens_Flares.LF_XCom_Base_C', 2, []))
        self.assertIn(glare['source']['actor'], ('LensFlareSource_7', 'LensFlareSource_8'))
        self.assertGreater(glare['closure']['bytes'], 1000)
        self.assertIn(glare['blocked'], (None, 'family'))

    def test_an_effect_or_sound_is_read_as_a_template(self):
        steam = library.effect(self.cache, self.game, dict(package='urb_bar', level='base', actor='Emitter_16'))
        self.assertEqual((steam['kind'], steam['source']['package'], steam['source']['actor']), ('effect', 'URB_Bar', 'Emitter_16'))
        self.assertEqual(steam['source']['sha256'], self.index['donors'][0]['sha256'])
        self.assertEqual(list(steam['systems']), [steam['record']['system']])
        self.assertEqual(steam['record']['actor'], 'TheWorld.PersistentLevel.Emitter_16')
        self.assertEqual(next(e for e in self.index['entries'] if e['key'] == steam['key'])['family'], 'effect')
        folder = self.cache / 'library' / 'pieces' / 'URB_Bar'
        self.assertTrue(any((g / ('effects-v%d.json' % library.EFFECTS_VERSION)).is_file() for g in folder.iterdir()))
        music = library.effect(self.cache, self.game, dict(package='URB_Bar', actor='AmbientSoundSimple_2'))
        glare = library.effect(self.cache, self.game, dict(package='URB_Bar', actor='LensFlareSource_7'))
        self.assertEqual((glare['kind'], glare['record']['template'], glare['systems'], glare['waves'], glare['draw']),
                         ('flare', 'FX_Lens_Flares.LF_XCom_Base_C', {}, {}, None))
        self.assertEqual(next(e for e in self.index['entries'] if e['key'] == glare['key'])['family'], 'flare')
        self.assertEqual(list(music['waves']), ['URB_Bar|SoundBarMuzak.BarMuzakStereo'])
        self.assertTrue(music['waves']['URB_Bar|SoundBarMuzak.BarMuzakStereo']['playable'])
        # many at once, and what can't be had
        runner = library.LibraryRunner(self.cache, self.game)
        got = runner.effects([dict(package='URB_Bar', actor='Emitter_16'), dict(package='URB_Bar', actor='Emitter_99999'),
                              dict(package='URB_NoSuchMap', actor='A_1')])
        self.assertEqual((got[0]['record']['key'], got[0]['record']['source']), (steam['key'], steam['source']))
        self.assertIn('Emitter_99999', got[1]['error'])
        self.assertIn('URB_NoSuchMap', got[2]['error'])
        for bad, status in ((dict(package='URB_Bar', actor='Emitter_99999'), 404), (dict(package='URB_Bar', actor='no such!'), 400),
                            (dict(package='URB_Bar', level='stream', actor='Emitter_16'), 400)):
            with self.assertRaises(ProjectError) as caught:
                library.effect(self.cache, self.game, bad)
            self.assertEqual(caught.exception.status, status)
        # the Wave preview reads a donor's wave by its records
        path, scene = runner.wave_scene('URB_Bar')
        self.assertEqual((path.name, scene['name'], scene['source']['sha256']), ('URB_Bar.upk', 'URB_Bar', steam['source']['sha256']))
        self.assertIn('URB_Bar|SoundBarMuzak.BarMuzakStereo', scene['soundWaves'])

    def test_the_effect_routes(self):
        """GET /library/effect.json, POST /library/effects.json and GET or HEAD /library/wave.ogg (a donor's wave for
        the Wave preview) over the install's URB_Bar."""
        from urllib.parse import quote, urlencode
        import audio
        runner = library.LibraryRunner(self.cache, self.game)
        kept = Handler.wave_cache
        Handler.wave_cache = audio.WaveCache()
        self.addCleanup(setattr, Handler, 'wave_cache', kept)
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(self.cache, allow_empty=True),
                                                       library=runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))
        base = f'http://127.0.0.1:{server.server_port}'

        def get(path, method='GET', body=None):
            request = Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json'})
            try:
                with urlopen(request) as r:
                    payload = r.read()
                    return r.status, r.headers, payload
            except HTTPError as error:
                return error.code, error.headers, error.read()
        status, _, payload = get('/library/effect.json?' + urlencode(dict(package='URB_Bar', actor='AmbientSoundSimple_2')))
        music = json.loads(payload)
        self.assertEqual((status, music['kind'], list(music['waves'])), (200, 'sound', ['URB_Bar|SoundBarMuzak.BarMuzakStereo']))
        status, _, payload = get('/library/effects.json', 'POST', dict(sources=[dict(package='URB_Bar', actor='Emitter_16'),
                                                                                dict(package='URB_Bar', actor='Emitter_99999')]))
        both = json.loads(payload)['effects']
        self.assertEqual((status, both[0]['record']['kind'], 'error' in both[1]), (200, 'effect', True))
        self.assertEqual(get('/library/effects.json', 'POST', dict(sources='x'))[0], 400)
        wave = base + '/library/wave.ogg?' + urlencode(dict(package='URB_Bar', id='URB_Bar|SoundBarMuzak.BarMuzakStereo'))
        with urlopen(wave) as r:
            whole = r.read()
            self.assertEqual((r.status, r.headers['Content-Type']), (200, 'audio/ogg'))
        self.assertEqual(audio.validate(whole)['channels'], 2)
        with urlopen(Request(wave, method='HEAD')) as r:
            self.assertEqual((r.status, int(r.headers['Content-Length']), r.read()), (200, len(whole), b''))
        for query, code in ((dict(package='URB_Bar', id='URB_Bar|No.Such'), 404), (dict(package='URB_NoSuchMap', id='x'), 404),
                            (dict(package='URB_Bar', id='URB_PoliceStation|' + quote('SoundBarMuzak.BarMuzakStereo')), 404)):
            self.assertEqual(get('/library/wave.ogg?' + urlencode(query))[0], code, query)

    def test_an_assemblys_record_has_all_its_parts(self):
        car = next(e for e in self.index['entries'] if e.get('assembly') and e['family'] == 'car'
                   and e['source']['package'] == 'URB_PoliceStation')
        record = library.piece(self.cache, self.game, dict(car['source']))
        whole = record['assembly']
        self.assertEqual((record['key'], whole['family'], len(whole['members'])), (car['key'], 'car', car['assembly']['members']))
        self.assertEqual(whole['pivot'], 'TheWorld.PersistentLevel.' + car['source']['actor'])
        self.assertEqual({o['actor'] for o in record['objects']}, set(whole['members']))
        body = next(o for o in record['objects'] if o['actor'] == whole['pivot'])
        self.assertIn(body['partner'], whole['members'])                        # its glass
        glass = next(o for o in record['objects'] if o['actor'] == body['partner'])
        self.assertIn(whole['pivot'], glass['breaks'])
        self.assertEqual(len(record['grid']), 3)
        # asked for by another part, it is the same assembly
        other = library.piece(self.cache, self.game, dict(package='URB_PoliceStation', level='base',
                                                          actor=body['partner'].rsplit('.', 1)[-1]))
        self.assertEqual((other['key'], other['assembly']), (record['key'], whole))

    def test_a_piece_is_exported_once_as_a_template(self):
        source = dict(package='urb_policestation', level='base', actor='XComLevelActor_15')
        record = library.piece(self.cache, self.game, source)
        self.assertEqual(record['source']['package'], 'URB_PoliceStation')
        folder = self.cache / 'library' / 'pieces' / 'URB_PoliceStation'
        (generation,) = [p.name for p in folder.iterdir()]
        self.assertEqual(record['base'], f'/cache-library/URB_PoliceStation/{generation}/')
        (obj,) = record['objects']
        self.assertEqual((obj['actor'], obj['actorClass']), ('TheWorld.PersistentLevel.XComLevelActor_15', 'XComLevelActor'))
        self.assertTrue(obj['mesh'].startswith('lib-URB_PoliceStation-'))
        self.assertEqual(record['meshes'][obj['mesh']]['name'], 'parkLampPost.Meshes.ParkLampPost_B')
        for key, mesh in record['meshes'].items():
            self.assertTrue((folder / generation / mesh['url']).is_file())
        self.assertTrue(all(m in record['materials'] for m in obj['materials']))
        self.assertGreaterEqual(len(record['textures']), 3)
        for texture in record['textures'].values():
            self.assertTrue((folder / generation / texture['url']).is_file())
        stamp = (folder / generation / 'XComLevelActor_15.json').stat().st_mtime_ns
        self.assertEqual(library.piece(self.cache, self.game, source), record)
        self.assertEqual((folder / generation / 'XComLevelActor_15.json').stat().st_mtime_ns, stamp)
        # many at once, as a prefab's opening asks: the records themselves, and why one could not be had
        runner = library.LibraryRunner(self.cache, self.game)
        both = runner.records([source, dict(package='URB_NoSuchMap', actor='A_1')])
        self.assertEqual(both[0], dict(record=record))
        self.assertIn('URB_NoSuchMap', both[1]['error'])
        for bad, status in ((dict(package='URB_PoliceStation', actor='XComLevelActor_99999'), 404),
                            (dict(package='URB_NoSuchMap', actor='A_1'), 404),
                            (dict(package='URB_PoliceStation', actor='../A'), 400),
                            (dict(package='URB_PoliceStation', actor='A_1', level='stream'), 400)):
            with self.assertRaises(ProjectError) as refused:
                library.piece(self.cache, self.game, bad)
            self.assertEqual(refused.exception.status, status, bad)


if __name__ == '__main__':
    unittest.main()
