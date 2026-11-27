// The map's fog and colour as a project changes them (atmosphere_rules.js; game-likeness plan, C5b). Run:
// node tools/viewer/tests/atmosphere_rules_test.mjs
import assert from 'node:assert/strict';
import { atmosphereWith, colourHex, colourWords, fogWords, gradeVolumes, hexColour, liftOf, lookName, lookRecord,
         lookSwatch, spreadPicks, tidyAtmosphere, tintOf, tintParts, validAtmosphere, volumesOver,
         withMember } from '../web/atmosphere_rules.js';

const map = { world: { fog: { bEnabled: true, FogDensity: 0.02, FogHeight: 1000, FogHeightFalloff: 4, FogMaxOpacity: 1,
                              OppositeLightColor: [0.211765, 0.235294, 0.360784, 1], OppositeLightBrightness: 0.2,
                              LightInscatteringColor: [0.145098, 0.062745, 0.05098, 1], LightInscatteringBrightness: 1,
                              LightTerminatorAngle: 45, StartDistance: 0 },
                       postProcess: { Scene_Colorize: [1.1, 1, 1], Scene_Shadows: [0, 0, -0.05], Scene_Desaturation: 0,
                                      Bloom_Scale: 0.5, bEnableBloom: true } },
              volumes: [{ name: 'PostProcessVolume_1', enabled: true, settings: { bOverride_Scene_Colorize: true, Scene_Colorize: [1.2, 1.2, 1.2] } },
                        { name: 'PostProcessVolume_2', enabled: false, settings: { bOverride_Scene_Colorize: true } }] };

// a record keeps only what differs from the map's own, rounded; nothing that differs is no record
assert.equal(tidyAtmosphere({ fog: { FogDensity: 0.02 }, postProcess: { Bloom_Scale: 0.5 } }, map), null);
assert.deepEqual(tidyAtmosphere({ fog: { FogDensity: 0.0400000001, FogHeight: 1000 } }, map), { fog: { FogDensity: 0.04 } });
assert.equal(tidyAtmosphere(null, map), null);
assert.deepEqual(tidyAtmosphere({ sky: { x: 1 } }, map), { sky: { x: 1 } });          // (carried as it is)
assert.ok(validAtmosphere({ fog: { FogDensity: 1, bEnabled: false, OppositeLightColor: [1, 0, 0, 1] } }));
assert.ok(!validAtmosphere({ fog: { FogDensity: { x: 1 } } }) && !validAtmosphere({ sky: {} }) && !validAtmosphere([1]));
assert.ok(!validAtmosphere({ fog: { FogDensity: NaN } }));

// the view: the project's members over the map's world settings, the map's volumes kept, the map left as it was
const record = { fog: { FogDensity: 0.6, OppositeLightColor: [1, 0, 0, 1] }, postProcess: { Scene_Colorize: [0.6, 1.4, 0.6] } };
const view = atmosphereWith(map, record);
assert.equal(view.world.fog.FogDensity, 0.6);
assert.equal(view.world.fog.FogHeight, 1000);
assert.deepEqual(view.world.postProcess.Scene_Shadows, [0, 0, -0.05]);
assert.equal(view.volumes, map.volumes);
assert.equal(map.world.fog.FogDensity, 0.02);
assert.equal(atmosphereWith(map, null), map);

// one member set, tidied: back to the map's own value is no change
const one = withMember(null, map, 'fog', 'FogDensity', 0.1);
assert.deepEqual(one, { fog: { FogDensity: 0.1 } });
assert.equal(withMember(one, map, 'fog', 'FogDensity', 0.02), null);

// another map's look: its values where they differ from the map's own
const bar = { fog: { ...map.world.fog, FogDensity: 0.015, FogHeight: 500 }, postProcess: { ...map.world.postProcess, Scene_Colorize: [1, 1, 1.2] },
              maps: [{ map: 'URB_Bar', label: 'Urban Bar', time: ['Night'] }, { map: 'X', label: 'Another', time: ['Day'] }] };
assert.deepEqual(lookRecord(bar, map), { fog: { FogDensity: 0.015, FogHeight: 500 }, postProcess: { Scene_Colorize: [1, 1, 1.2] } });
assert.equal(lookName(bar), 'Urban Bar (night) and 1 more');
assert.equal(lookName({ maps: [{ label: 'Alien Base 01', time: ['None'] }] }), 'Alien Base 01');

// words
assert.equal(fogWords(map.world.fog), 'on, density 0.02, height 1000');
assert.equal(fogWords({ bEnabled: false }), 'off');
assert.equal(colourWords(map.world.postProcess), 'tint 1.1, 1, 1 · bloom 0.5');
assert.equal(colourWords({ Scene_Colorize: [1, 1, 1], Scene_Desaturation: 0.25, bEnableBloom: false }), 'tint 1, 1, 1 · grey 0.25 · bloom 0');

// colours: a Color as #rrggbb and back; the tint's colour and strength; the shadows' lift
assert.equal(colourHex([1, 0.5, 0, 1]), '#ff8000');
assert.deepEqual(hexColour('#ff8000').map(v => Math.round(v * 255)), [255, 128, 0, 255]);
assert.deepEqual(tintParts([1.2, 0.6, 0.6]), { hex: '#ff8080', strength: 1.2 });
assert.deepEqual(tintOf('#ff8080', 1.2), [1.2, 0.602, 0.602]);
assert.ok(Math.abs(liftOf([0, 0, -0.06]) - 0.02) < 1e-12);

// the swatch: three CSS colours, a red fog redder than a blue one
const red = lookSwatch({ fog: { ...map.world.fog, OppositeLightColor: [1, 0, 0, 1], LightInscatteringColor: [1, 0, 0, 1], OppositeLightBrightness: 1 }, postProcess: {} });
assert.equal(red.length, 3);
assert.ok(red.every(c => /^rgb\(\d+, \d+, \d+\)$/.test(c)));
const [r, g] = red[0].match(/\d+/g).map(Number);
assert.ok(r > g, red);
// picks spread apart, none the map's own look, never more than asked
const looks = [bar, { ...bar, maps: [{ label: 'Red' }], fog: { ...bar.fog, OppositeLightColor: [1, 0, 0, 1], LightInscatteringColor: [1, 0, 0, 1], OppositeLightBrightness: 1 } },
               { fog: map.world.fog, postProcess: map.world.postProcess, maps: [{ label: 'Same' }] }];
const picks = spreadPicks(looks, { fog: map.world.fog, postProcess: map.world.postProcess }, 4);
assert.ok(picks.length <= 2 && picks[0].maps[0].label === 'Red', picks.map(p => p.maps[0].label));

// the volumes: the ones that set the colour, read only, and those over a member the project changes
assert.deepEqual(gradeVolumes(map), [{ name: 'PostProcessVolume_1', words: 'tint 1.2, 1.2, 1.2' }]);
assert.deepEqual(volumesOver(map, record), [{ name: 'PostProcessVolume_1', members: ['Scene_Colorize'] }]);
assert.deepEqual(volumesOver(map, { fog: { FogDensity: 1 } }), []);
console.log('atmosphere rules: ok');
