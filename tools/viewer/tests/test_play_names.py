"""A play's own names (play_names.py, installs.play_taken and the install under them): Play in game installs a
project's build under <Map>_Play, so that a map pack carrying the same map, dropped into CookedPCConsole or installed
the classic way, or anything else of the build's names in the install, never meets the play."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import installs  # noqa: E402  (it puts tools/bake on the path)
import mapsini  # noqa: E402
import play_names  # noqa: E402
from viewer_fixtures import ID, PLAY, VARIANT, PlayInstalls, record  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# the game's landing intro, for a build's copy of it renamed for a play: without it that test skips
INTRO, NO_INTRO = labpaths.test_file('XCOM_INTRO_UPK', labpaths.lwr_cooked('CIN_DropshipIntros.upk'), 'CIN_DropshipIntros.upk')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Names(unittest.TestCase):
    def test_the_suffix_is_the_first_that_gives_no_package_a_name_the_install_has(self):
        stems = ['Map', 'CIN_DropshipIntros_Map']
        self.assertEqual(play_names.suffix(stems, set()), '_Play')
        self.assertEqual(play_names.suffix(stems, {'cin_dropshipintros_map_play'}), '_Play2')
        self.assertEqual(play_names.suffix(stems, {'map_play', 'map_play2'}), '_Play3')
        every = {'map_play'} | {f'map_play{n}' for n in range(2, play_names.TRIES + 1)}
        with self.assertRaisesRegex(play_names.PlayNameError, 'is taken'):
            play_names.suffix(stems, every)

    def test_a_display_name_starts_with_the_plays_map(self):
        # the words the game matches after the map's name (Long War's _Bomb) stay
        self.assertEqual(play_names.display('Map_Bomb (Bar remix, Council bomb) |0', 'Map', 'Map_Play'),
                         'Map_Play_Bomb (Bar remix, Council bomb) |0')
        self.assertEqual(play_names.display('map (Bar remix)', 'Map', 'Map_Play'), 'Map_Play (Bar remix)')
        self.assertEqual(play_names.display('Another name |0', 'Map', 'Map_Play'), 'Map_Play Another name |0')

    def test_map_names_are_renamed_whatever_their_case(self):
        line = b'Maps=( Name="Map", StreamingMaps[0]=( MapName = "cin_dropshipintros_map" ), StreamingMaps[1]=( MapName="Other" ) )'
        out = mapsini.renamed_maps(line, {'CIN_DropshipIntros_Map': 'CIN_DropshipIntros_Map_Play'})
        self.assertEqual(mapsini.slot_streams(out), ['CIN_DropshipIntros_Map_Play', 'Other'])
        self.assertEqual(mapsini.field(out, 'Name'), 'Map')
        self.assertEqual(mapsini.renamed_maps(line.decode('latin-1'), {}), line.decode('latin-1'))

    def test_the_manifest_names_the_plays_packages_everywhere(self):
        line = mapsini.set_field(mapsini.set_field(record('bar').decode('latin-1'), 'Name', 'Map'), 'DisplayName', 'Map (Bar remix) |0')
        line = line.replace('MapName="CIN_DropshipIntros"', 'MapName="CIN_DropshipIntros_Map"')
        line, _ = mapsini.add_stream(line, 'patch_map')
        m = dict(variant='Map', source=dict(map='URB_Bar'), streams=['patch_map'],
                 replaceStreams={'CIN_DropshipIntros': 'CIN_DropshipIntros_Map'},
                 config=dict(maps=[line], landingZones=['LZArray=(MapName="Map",StartLoc=(X=1,Y=2,Z=3))']))
        names = {'Map': 'Map_Play', 'CIN_DropshipIntros_Map': 'CIN_DropshipIntros_Map_Play', 'patch_map': 'patch_map_Play'}
        out = play_names.manifest(m, names)
        self.assertEqual((out['variant'], out['playOf'], out['streams'], out['replaceStreams']),
                         ('Map_Play', 'Map', ['patch_map_Play'], {'CIN_DropshipIntros': 'CIN_DropshipIntros_Map_Play'}))
        r, = out['config']['maps']
        self.assertEqual((mapsini.field(r, 'Name'), mapsini.field(r, 'DisplayName')), ('Map_Play', 'Map_Play (Bar remix) |0'))
        streams = mapsini.slot_streams(r)
        self.assertTrue({'CIN_DropshipIntros_Map_Play', 'patch_map_Play'} <= set(streams))
        self.assertFalse({'CIN_DropshipIntros_Map', 'patch_map'} & set(streams))
        self.assertEqual(out['config']['landingZones'], ['LZArray=(MapName="Map_Play",StartLoc=(X=1,Y=2,Z=3))'])
        self.assertEqual(m['variant'], 'Map')                   # the build's own manifest is left as it was
        self.assertEqual(m['config']['maps'], [line])

    def test_each_package_gets_the_suffix_and_a_texture_cache_keeps_its_name(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            files = []
            for name, data in (('Map.upk', b'map'), ('CIN_DropshipIntros_Map.upk', b'no name in it'), ('Map_Lighting.tfc', b'lightmaps')):
                (d / name).write_bytes(data)
                files.append((d / name, Path('game') / name, sha(data)))
            m = dict(variant='Map', source=dict(map='URB_Bar'), streams=[], replaceStreams={'CIN_DropshipIntros': 'CIN_DropshipIntros_Map'})
            out, played = play_names.for_play(m, files, {'map_play'}, d / 'scratch', installs.sha256)
            self.assertEqual(out['variant'], 'Map_Play2')
            self.assertEqual([(src.name, dst.name, h) for src, dst, h in played],
                             [('Map.upk', 'Map_Play2.upk', sha(b'map')),
                              ('CIN_DropshipIntros_Map.upk', 'CIN_DropshipIntros_Map_Play2.upk', sha(b'no name in it')),
                              ('Map_Lighting.tfc', 'Map_Lighting.tfc', sha(b'lightmaps'))])
            self.assertFalse((d / 'scratch').exists())           # an intro copy that names no map is copied as it is
            # an intro copy that names the map but can't be read is no play
            (d / 'CIN_DropshipIntros_Map.upk').write_bytes(b'... Map ...')
            with self.assertRaisesRegex(play_names.PlayNameError, "could not be given the play's map name"):
                play_names.for_play(m, files, set(), d / 'scratch', installs.sha256)
            with self.assertRaisesRegex(play_names.PlayNameError, 'has no Other.upk'):
                play_names.for_play(dict(m, variant='Other'), files, set(), d / 'scratch', installs.sha256)


class BesideAPack(PlayInstalls, unittest.TestCase):
    def snapshot(self, folder):
        return {p.name: p.read_bytes() for p in folder.iterdir()}

    def test_a_play_goes_beside_a_drop_in_pack_of_the_same_map(self):
        """LWR 3's drop-in pack: the same project's map and intro copy in a folder of CookedPCConsole, under the
        map's own names. The play's packages, record and landing zone take the play's names, and the pack is left
        as it is; a name the pack holds too takes the play to the next."""
        self.package()
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        pack = cooked / 'Bar_maps'
        pack.mkdir()
        for name, data in ((f'{VARIANT}.upk', b'packed map'), (f'CIN_DropshipIntros_{VARIANT}.upk', b'packed intro'),
                           ('LWRMapPack_1234.upk', b'card')):
            (pack / name).write_bytes(data)
        packed, before = self.snapshot(pack), self.files(self.lwr)
        player = self.player()
        r = player.play(dict(project=ID))
        self.assertEqual((r['played']['map'], r['played']['variant']), (PLAY, VARIANT))
        self.assertTrue((self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii').endswith(f'\nopen {PLAY}\n'))
        self.assertTrue((cooked / f'{PLAY}.upk').is_file() and (cooked / f'CIN_DropshipIntros_{PLAY}.upk').is_file())
        self.assertFalse((cooked / f'{VARIANT}.upk').exists())
        mine, = self.records(self.lwr, PLAY)
        self.assertTrue(mapsini.field(mine, 'DisplayName').startswith(PLAY))       # no pack line's display name
        self.assertEqual(self.snapshot(pack), packed)
        self.settle(player)
        player.remove()
        self.assertEqual((self.files(self.lwr), self.snapshot(pack)), (before, packed))
        self.assertFalse((cooked / f'{PLAY}.upk').exists())
        # a map of the play's own name in the pack: the play takes the next name, every package with it
        (pack / f'{PLAY}.upk').write_bytes(b'a map someone named so')
        r = player.play(dict(project=ID))
        second = VARIANT + '_Play2'
        self.assertEqual(r['played']['map'], second)
        self.assertTrue((cooked / f'{second}.upk').is_file() and (cooked / f'CIN_DropshipIntros_{second}.upk').is_file())
        self.assertEqual(mapsini.slot_streams(self.records(self.lwr, second)[0]).count(f'CIN_DropshipIntros_{second}'), 1)
        self.settle(player)
        player.remove()
        self.assertEqual(self.files(self.lwr), before)

    def test_a_play_goes_beside_a_pack_installed_the_classic_way(self):
        """A pack installed by its Install.cmd (plain Enemy Within, LWR 2): the map's files in CookedPCConsole itself
        and records of its name in DefaultMaps.ini, none of them the editor's. The play used to be refused; it goes
        beside them under its play names, and Remove from game leaves theirs byte for byte."""
        self.package()
        cooked = self.lwr / 'XEW/XComGame/CookedPCConsole'
        for name, data in ((f'{VARIANT}.upk', b'packed map'), (f'CIN_DropshipIntros_{VARIANT}.upk', b'packed intro')):
            (cooked / name).write_bytes(data)
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        lines = mapsini.lines_of(maps.read_bytes())
        theirs = mapsini.set_field(mapsini.set_field(record('bar'), 'Name', VARIANT), 'DisplayName', f'{VARIANT} (Bar remix) |0')
        lines[-1:-1] = [theirs]
        maps.write_bytes(mapsini.EOL.join(lines))
        before, files = self.files(self.lwr), self.snapshot(cooked)
        player = self.player()
        r = player.play(dict(project=ID))
        self.assertEqual(r['played']['map'], PLAY)
        self.assertEqual(self.records(self.lwr, VARIANT), [theirs])
        self.assertEqual({n: b for n, b in self.snapshot(cooked).items() if n in files}, files)
        self.settle(player)
        player.remove()
        self.assertEqual((self.files(self.lwr), self.snapshot(cooked)), (before, files))

    @unittest.skipUnless(INTRO and INTRO.exists(), NO_INTRO)
    def test_the_plays_intro_copy_picks_the_landing_by_the_plays_map(self):
        """The build's own copy of the landing intro (intro_copy.make on the game's) is installed for a play with its
        switches naming the play's map where they named the map, the Build's copy left as it was."""
        import intro_copy
        self.package()
        folder = self.output / VARIANT
        copy = folder / 'CookedPCConsole' / f'CIN_DropshipIntros_{VARIANT}.upk'
        intro_copy.make(INTRO, copy, 'URB_Bar', VARIANT)
        built = copy.read_bytes()
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        m['files'][f'CookedPCConsole/{copy.name}'] = sha(built)
        (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
        player = self.player()
        player.play(dict(project=ID))
        played = self.lwr / 'XEW/XComGame/CookedPCConsole' / f'CIN_DropshipIntros_{PLAY}.upk'

        def cases(path):
            p = intro_copy.lighting.Package(path)
            return {p.name(i): [t for _, t in e] for i, _, _, _, e in intro_copy.switches(p)}
        before, after = cases(copy), cases(played)
        self.assertEqual(after, {k: [PLAY if t == VARIANT else t for t in v] for k, v in before.items()})
        self.assertIn(PLAY, [t for v in after.values() for t in v])
        self.assertEqual(installs.read_ledger(self.lwr)['playFiles'][played.name], installs.sha256(played))
        self.assertEqual(copy.read_bytes(), built)
        self.settle(player)
        player.remove()
        self.assertFalse(played.exists())


if __name__ == '__main__':
    unittest.main()
