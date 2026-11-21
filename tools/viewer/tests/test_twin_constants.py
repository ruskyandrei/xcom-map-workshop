"""Python's side of tests/twin_constants.json (review finding 55): constants the page and Python each write, pinned in
one file both sides' tests read (twin_constants_test.mjs checks the page's), as limits.json is."""
import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[2]
for folder in (TOOLS / 'viewer', TOOLS / 'editor', TOOLS / 'bake'):
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

    def test_schema_versions(self):
        # the document versions the server's stores save (web/project.js and web/prefabs.js save the same)
        import prefabs
        import projects
        self.assertEqual(dict(project=projects.SCHEMA_VERSION, prefab=prefabs.SCHEMA_VERSION), TWIN['schemaVersions'])
        self.assertIn(projects.SCHEMA_VERSION, projects.READ_VERSIONS)
        self.assertIn(prefabs.SCHEMA_VERSION, prefabs.READ_VERSIONS)


if __name__ == '__main__':
    unittest.main()
