"""Python's side of tests/twin_constants.json (review finding 55): constants the page and Python each write, pinned in
one file both sides' tests read (twin_constants_test.mjs checks the page's), as limits.json is."""
import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
for folder in (TOOLS / 'viewer', TOOLS / 'editor', TOOLS / 'bake', TOOLS / 'upk'):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

TWIN = json.loads(Path(__file__).with_name('twin_constants.json').read_text(encoding='utf-8'))


class TwinConstants(unittest.TestCase):
    def test_the_compilers_limits(self):
        import compiler
        self.assertEqual({k: list(v) for k, v in compiler.LIGHT_RANGES.items()}, TWIN['lightRanges'])
        self.assertEqual(dict(scale=list(compiler.EFFECT_SCALE), radiusMax=compiler.SOUND_RADIUS_MAX, volumeMax=compiler.SOUND_VOLUME_MAX,
                              pitch=list(compiler.SOUND_PITCH), parameterMax=compiler.PARAMETER_MAX), TWIN['effectValues'])
        self.assertEqual(list(compiler.FOREIGN_SOFT), TWIN['softFamilies'])

    def test_made_pieces(self):
        import frac_wall
        import generated
        import ground
        self.assertEqual(dict(minLength=generated.MIN_LENGTH, maxLength=generated.MAX_LENGTH), TWIN['madeWall'])
        self.assertEqual(dict(frac_wall.END_INSETS), TWIN['endInsets'])
        import made_edits
        self.assertEqual(dict(half=made_edits.WALL_ROOM['half'], z=list(made_edits.WALL_ROOM['z'])), TWIN['wallRoom'])
        want = dict(TWIN['ground'])
        self.assertAlmostEqual(ground.SLOPED, want.pop('sloped'), places=9)
        self.assertEqual(dict(maxTiles=ground.MAX_TILES, maxHeight=ground.MAX_HEIGHT, rockSeeds=ground.ROCK_SEEDS, steep=ground.STEEP), want)

    def test_landings_missions_and_buildings(self):
        import buildings
        import missions
        import spawns
        self.assertEqual(dict(quarter=spawns.QUARTER, ground=spawns.GROUND, insideBack=spawns.INSIDE_BACK,
                              offsets={k: list(v) for k, v in spawns.OFFSETS.items()}, soldiers=[list(s) for s in spawns.SOLDIERS],
                              evacSize=list(spawns.EVAC_SIZE)), TWIN['landing'])
        self.assertEqual(list(missions.UFO_TYPES), TWIN['ships'])
        self.assertEqual(list(buildings.LISTED), TWIN['listedClasses'])

    def test_ladders(self):
        # a ladder's climb ends (web/ladders.js ladderEnds) and the floor the project's flat pieces give (its
        # addedFloors)
        import compiler_tables
        import ladders
        self.assertEqual(dict(topReach=ladders.TOP_REACH, footBack=ladders.FOOT_BACK, endLift=ladders.END_LIFT,
                              turn=ladders.TURN, floorThick=compiler_tables.FLOOR_THICK,
                              headroom=compiler_tables.HEADROOM), TWIN['ladders'])

    def test_what_long_war_rebalance_is_told_of_a_map(self):
        # the project's lwrMapInfo keys with LWR's keys and values (web/missions.js MAP_INFO); the card's writer
        # knows the same keys and values (pack_card.INFO_VALUES)
        import missions
        import pack_card
        self.assertEqual({k: [key, list(values)] for k, (key, values) in missions.MAP_INFO.items()}, TWIN['lwrMapInfo'])
        self.assertEqual(list(missions.MAP_INFO), list(TWIN['lwrMapInfo']))
        self.assertEqual({key: values for key, values in missions.MAP_INFO.values()}, pack_card.INFO_VALUES)
        self.assertEqual(missions.map_info_lines('EXP_Market', dict(holdTheLine='No', alienDensity='Moderate')),
                         [pack_card.info_text('EXP_Market', 'AlienDensity', 'Moderate'), pack_card.info_text('EXP_Market', 'HoldTheLine', 'No')])
        self.assertTrue(missions.valid_map_info({}))
        self.assertFalse(missions.valid_map_info(dict(alienDensity='Huge')))
        self.assertEqual(missions.map_info_words(dict(alienDensity='Heavy', holdTheLine='No')), 'abductions up to Heavy, no Hold the Line')

    def test_the_parts_a_clear_marks(self):
        # the project's `cleared` keys (schema 9): the server's, the compiler's and the Build's, which web/clear_parts.js
        # writes (the clear-by-parts plan)
        import mission_edits
        import native_copy
        import projects
        self.assertEqual(list(projects.CLEAR_PARTS), TWIN['clearParts'])
        self.assertEqual(list(mission_edits.CLEAR_PARTS), TWIN['clearParts'])
        self.assertEqual(list(native_copy.CLEAR_PARTS), TWIN['clearParts'])

    def test_schema_versions(self):
        # the document versions the server's stores save (web/project.js and web/prefabs.js save the same)
        import prefabs
        import projects
        self.assertEqual(dict(project=projects.SCHEMA_VERSION, prefab=prefabs.SCHEMA_VERSION), TWIN['schemaVersions'])
        self.assertIn(projects.SCHEMA_VERSION, projects.READ_VERSIONS)
        self.assertIn(prefabs.SCHEMA_VERSION, prefabs.READ_VERSIONS)


if __name__ == '__main__':
    unittest.main()
