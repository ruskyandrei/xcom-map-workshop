"""The lightmap codec: its formulas, and how it matches UDK Lightmass's own bakes (EXP-18) when they are present."""
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lightmap_encode as enc  # noqa: E402
import udk_calib_read  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# the calibration scenes (<lab>\bake-calib) and UDK's bakes of them (<udk>\UDKGame\Content\Maps\calib), from the settings
CALIB = labpaths.configured('lab', 'bake-calib')
MAPS = labpaths.configured('udk', 'UDKGame', 'Content', 'Maps', 'calib')
FLAT = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]])    # the template floor's top face: tangent +X, binormal -Y


def flat_frames(n):
    return np.repeat(FLAT[None], n, 0)


class Formulas(unittest.TestCase):
    def test_basis_is_unit_and_35_degrees_up(self):
        self.assertTrue(np.allclose(np.linalg.norm(enc.BASIS, axis=1), 1))
        self.assertTrue(np.allclose(enc.BASIS[:, 2], 1 / math.sqrt(3)))
        az = np.degrees(np.arctan2(enc.BASIS[:, 1], enc.BASIS[:, 0])) % 360
        self.assertTrue(np.allclose(az, [90, 210, 330]))

    def test_directional_light_matches_the_directional_fit(self):
        # BakeCalib3: S(45 deg) = 1.53-1.55 for a directional light (LightSourceAngle 3 degrees)
        s = enc.elevation_term(math.sin(math.radians(45)), math.radians(3))
        self.assertAlmostEqual(float(s), 1.54, delta=0.04)
        light = dict(kind='directional', toLight=[0, -math.sqrt(0.5), math.sqrt(0.5)], brightness=1, color=[1, 1, 1])
        coef = enc.coefficients([light], np.zeros((1, 3)), flat_frames(1))[0]
        l_ts = FLAT @ np.array(light['toLight'])
        want = float(s) * np.maximum(0, enc.BASIS @ l_ts)
        self.assertTrue(np.allclose(coef[:, 0], want) and np.allclose(coef[:, 1], want))

    def test_point_light_falloff_and_spot_cone(self):
        point = dict(kind='point', location=[0, 0, 100], radius=200, falloffExponent=2, lightSourceRadius=0,
                     brightness=1, color=[1, 1, 1])
        world = np.array([[0, 0, 0], [0, 0, -150], [500, 0, 0]], float)   # below, out of range, out of range
        coef = enc.coefficients([point], world, flat_frames(3))
        # straight down: e = 90 deg, A = (1 - 0.25)^2, S = 2
        self.assertTrue(np.allclose(coef[0, :, 0], 2 * 0.5625 * enc.BASIS[:, 2]))
        self.assertTrue(np.all(coef[1:] == 0))
        spot = dict(point, kind='spot', direction=[1, 0, 0], innerConeAngle=10, outerConeAngle=30)
        self.assertTrue(np.all(enc.coefficients([spot], world[:1], flat_frames(1)) == 0))   # texel behind the cone
        spot['direction'] = [0, 0, -1]
        self.assertTrue(np.allclose(enc.coefficients([spot], world[:1], flat_frames(1)), coef[:1]))

    def test_texels_inside_a_lights_source_sphere_stay_non_negative(self):
        # URB_Bar's ceiling has texels a few units from lamps of source radius 32: alpha near 90 degrees, past the
        # fit's range, where the uncapped S(e, alpha) went negative and the encoder wrote NaN
        lamp = dict(kind='spot', location=[0, 0, 10], direction=[0, 0, -1], innerConeAngle=60, outerConeAngle=80,
                    radius=1270, falloffExponent=6, lightSourceRadius=32, brightness=1, color=[1, 0.6, 0.3])
        world = np.array([[0, 0, 0], [20, 0, 0], [40, 0, 0], [0, 0, -100]], float)
        coef = enc.coefficients([lamp], world, flat_frames(4))
        self.assertTrue(np.all(coef >= 0))
        self.assertTrue(np.all(coef[0].sum(0) > 0))
        out = enc.encode(coef)
        self.assertTrue(all(np.isfinite(out[k]).all() for k in ('nac', 'dmc')))
        capped = enc.elevation_term(np.array([1.0]), np.array([np.pi / 2]))
        self.assertAlmostEqual(float(capped[0]), float(enc.elevation_term(np.array([1.0]), np.array([enc.ALPHA_MAX]))[0]))

    def test_an_edited_lights_direct_light_stops_at_its_radius_before_and_after(self):
        # editor lights plan 4.7, case 4, direct light only: a spot shrunk, rotated at its place and switched off.
        # Each state's direct light is zero beyond its radius and outside its cone; the receivers the old state lit
        # lose it (the relight revisits them); bounce beyond the radius is the relight's (edit_reaches pads it)
        spot = dict(kind='spot', location=[0, 0, 300], radius=600, falloffExponent=2, lightSourceRadius=0,
                    brightness=1, color=[1, 1, 1], direction=[0, 0, -1], innerConeAngle=0, outerConeAngle=60)
        world = np.array([[0, 0, 0], [400, 0, 0], [0, 0, -400]], float)   # under it, out to the side, beyond reach
        lit = enc.coefficients([spot], world, flat_frames(3)).sum((1, 2))
        self.assertTrue(lit[0] > 0 and lit[1] > 0 and lit[2] == 0)
        shrunk = enc.coefficients([dict(spot, radius=350)], world, flat_frames(3)).sum((1, 2))
        self.assertTrue(shrunk[0] > 0 and shrunk[1] == 0)            # (400, 0, 0) is 500 away: beyond 350
        turned = enc.coefficients([dict(spot, direction=[1, 0, 0])], world, flat_frames(3)).sum((1, 2))
        self.assertTrue(turned[0] == 0 and turned[1] > 0)
        self.assertTrue(np.all(enc.coefficients([dict(spot, brightness=0)], world, flat_frames(3)) == 0))
        # a stored 580-degree cone lights as the effective 89.99 one (lights.effective_cone)
        wide = enc.coefficients([dict(spot, outerConeAngle=580)], world, flat_frames(3))
        self.assertTrue(np.allclose(wide, enc.coefficients([dict(spot, outerConeAngle=89.99)], world, flat_frames(3))))

    def test_light_below_the_surface_adds_nothing(self):
        light = dict(kind='directional', toLight=[0, 0, -1], brightness=1, color=[1, 1, 1])
        self.assertTrue(np.all(enc.coefficients([light], np.zeros((1, 3)), flat_frames(1)) == 0))

    def test_encode_normalises_colour_and_scales_each_channel(self):
        coef = np.zeros((2, 3, 3))
        coef[0] = [[2.0, 1.0, 0.5], [0.0, 0.0, 0.0], [1.0, 0.5, 0.25]]
        coef[1] = [[1.0, 1.0, 1.0], [0.4, 0.4, 0.4], [0.0, 0.0, 0.0]]
        out = enc.encode(coef)
        self.assertTrue(np.allclose(out['nacLinear'][0], [1, 0.5, 0.25]))
        self.assertTrue(np.allclose(out['nacLinear'][1], [1, 1, 1]))
        self.assertEqual(out['dmcScale'], [2.0, 0.4, 1.0])
        self.assertTrue(np.allclose(out['dmc'] ** enc.GAMMA, [[1, 0, 1], [0.5, 1, 0]]))
        nac, dmc = enc.decode(out['nac'], out['dmc'], out['dmcScale'])
        self.assertTrue(np.allclose(dmc, coef.max(2)))


@unittest.skipUnless(CALIB and MAPS and (MAPS / 'BakeCalib7.udk').exists() and (CALIB / 'calib6' / 'scene.json').exists(),
                     'UDK calibration bakes not on this machine (or the lab and udk settings not set)')
class AgainstLightmass(unittest.TestCase):
    """The codec on UDK's own bakes: texels compared one by one where the prediction is clear of noise."""

    def compare(self, udk, scene_path, names):
        scene = json.loads(scene_path.read_text(encoding='utf-8'))
        texels = {}
        udk_calib_read.read(udk, scene, texels)
        lights = []
        for lt in scene['pointLights']:
            lights.append(dict(lt, kind='point', color=np.array(lt.get('color', [255] * 3)) / 255))
        for lt in scene['spotLights']:
            lights.append(dict(lt, kind='spot', color=np.array(lt.get('color', [255] * 3)) / 255))
        out = {}
        for rec, light in zip(scene['receivers'], lights):
            if rec['name'] not in names:
                continue
            k = rec['name']
            world, frame = texels[f'{k}/world'], texels[f'{k}/frame']
            coef = enc.coefficients([light], world, np.repeat(frame[None], len(world), 0))
            pred = coef.max(2)
            meas = texels[f'{k}/dmc'] ** enc.GAMMA * texels[f'{k}/scales'][1]
            strong = pred >= 0.3 * pred.max(1, keepdims=True)
            stats = []
            for use in (pred > 0.05, (pred > 0.05) & strong):
                ratio = meas[use] / pred[use]
                stats.append((float(np.median(ratio)), float(np.sqrt(np.mean((ratio - 1) ** 2)))))
            out[k] = stats
        return out

    def test_point_and_spot_lights_with_the_bars_source_radius(self):
        res = self.compare(MAPS / 'BakeCalib7.udk', CALIB / 'calib6' / 'scene.json', {'a32', 'e32', 's32', 'a0', 'b0'})
        self.assertEqual(len(res), 5)
        for name, ((median, rms), (strong_median, strong_rms)) in res.items():
            # every channel the model lights clearly, then the channels that carry at least 30% of the texel's light
            self.assertAlmostEqual(median, 1.0, delta=0.05, msg=name)
            self.assertLess(rms, 0.12, msg=name)
            self.assertAlmostEqual(strong_median, 1.0, delta=0.04, msg=name)
            self.assertLess(strong_rms, 0.06, msg=name)


if __name__ == '__main__':
    unittest.main()
