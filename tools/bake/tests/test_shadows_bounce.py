"""Shadows (Embree), bounce gathering, albedo and the full relight of the bar's pool-table floor."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bounce  # noqa: E402
import lightmap_encode as codec  # noqa: E402
import shadows  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'
UP = np.array([0.0, 0.0, 1.0])


def quad(x0, x1, y0, y1, z, up=True):
    """Two triangles of a horizontal rectangle, wound so Embree's normal points up (or down)."""
    a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    tris = np.array([[a, b, c], [a, c, d]], np.float32)
    return tris if up else tris[:, ::-1].copy()


def point_light(z=200.0, radius=10.0):
    return dict(kind='point', location=[0.0, 0.0, z], radius=1000.0, falloffExponent=2.0, lightSourceRadius=radius,
                brightness=1.0, color=[1.0, 1.0, 1.0])


class Occlusion(unittest.TestCase):
    def test_a_square_blocks_segments_through_it_only(self):
        occ = shadows.Occluder(quad(-10, 10, -10, 10, 50))
        origins = np.array([[0, 0, 0], [30, 0, 0], [0, 0, 60]], float)
        targets = np.array([[0, 0, 100], [30, 0, 100], [0, 0, 100]], float)
        self.assertEqual(occ.blocked(origins, targets).tolist(), [True, False, False])

    def test_shadow_umbra_penumbra_and_open_floor(self):
        occ = shadows.Occluder(quad(-20, 20, -20, 20, 100))
        world = np.array([[0, 0, 0], [30, 0, 0], [200, 0, 0]], float)
        vis = shadows.light_visibility(occ, point_light(radius=30.0), world, np.tile(UP, (3, 1)), samples=64)
        self.assertEqual(vis[0], 0.0)
        self.assertTrue(0.0 < vis[1] < 1.0)
        self.assertEqual(vis[2], 1.0)

    def test_a_lamp_in_an_open_shade_still_lights_the_floor_below(self):
        # a box around the light, open at the bottom: the side walls reach below the light's centre
        z, r = 200.0, 32.0
        walls = []
        for x0, x1, y0, y1 in ((-40, 40, -40, -40), (-40, 40, 40, 40), (-40, -40, -40, 40), (40, 40, -40, 40)):
            a, b = (x0, y0, z - 20), (x1, y1, z - 20)
            c, d = (x1, y1, z + 40), (x0, y0, z + 40)
            walls += [[a, b, c], [a, c, d]]
        occ = shadows.Occluder(np.array(walls, np.float32))
        vis = shadows.light_visibility(occ, point_light(z, r), np.array([[0.0, 0.0, 0.0]]), UP[None], samples=64)
        self.assertGreater(vis[0], 0.95)

    def test_ray_start_scales_with_the_level(self):
        # a rug 1.4 units above the floor: blocked from 0.5 units up, clear from 1.5 (URB_Bar's level scale 0.5)
        occ = shadows.Occluder(quad(-50, 50, -50, 50, 1.4))
        world, n = np.array([[0.0, 0.0, 0.0]]), UP[None]
        light = point_light(radius=0.0)
        self.assertEqual(shadows.light_visibility(occ, light, world, n, samples=4, level_scale=0.5 / 3)[0], 0.0)
        self.assertEqual(shadows.light_visibility(occ, light, world, n, samples=4, level_scale=0.5)[0], 1.0)


class OneMesh:
    """A package of an actor (export 1) at x 100, its mesh component (2) and the component's mesh (3): the viewer
    tests' triangle, which has one UV channel."""

    def __init__(self, lightmap_index):
        self.exports = [dict(outer=0), dict(outer=1), dict(outer=0)]
        self.values = {(1, 'Location'): [100.0, 0.0, 0.0], (2, 'StaticMesh'): 3,
                       (3, 'LightMapCoordinateIndex'): lightmap_index}

    def effective(self, index, key, default=None):
        return self.values.get((index, key), default)

    def name(self, index):
        return ('Actor', 'Actor.Component', 'Mesh')[index - 1]

    def native(self, index):
        sys.path.insert(0, str(HERE.parents[1] / 'viewer' / 'tests'))
        from test_formats import minimal_mesh
        from package import Reader
        return Reader(minimal_mesh())


class Casters(unittest.TestCase):
    def test_a_mesh_without_its_lightmap_uvs_still_casts_and_only_rasterising_refuses_it(self):
        """CLrgScout_Stonewall's CemeteryFoliage.Meshes.VineTop_2: LightMapCoordinateIndex 1 on a mesh of one UV
        channel (lit per vertex). It is a shadow caster all the same."""
        import lightmap_texels
        p = OneMesh(lightmap_index=1)
        mesh = lightmap_texels.component_mesh(p, 2)
        self.assertIsNone(mesh['uv'])
        self.assertEqual(mesh['positions'].shape, (3, 3))
        tris, owners, mats = shadows.caster_triangles(p, [2], materials=True)
        self.assertEqual(tris.shape, (1, 3, 3))
        self.assertEqual(sorted(tris[0, :, 0].tolist()), [100.0, 100.0, 101.0])
        self.assertEqual(owners.tolist(), [2])
        with self.assertRaisesRegex(ValueError, 'Mesh has no UV channel 1'):
            lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, 2),
                                      dict(coordinateScale=[1, 1], coordinateBias=[0, 0]), [4, 4])

    def test_a_mesh_with_its_lightmap_uvs_carries_them(self):
        import lightmap_texels
        self.assertEqual(lightmap_texels.component_mesh(OneMesh(lightmap_index=0), 2)['uv'].shape, (3, 2))


def box(x0, x1, y0, y1, z0, z1):
    """Twelve triangles of a closed box, wound so Embree's normals point out."""
    tris = [quad(x0, x1, y0, y1, z1), quad(x0, x1, y0, y1, z0, up=False)]
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        a, b, c, d = (ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)
        tris.append(np.array([[a, b, c], [a, c, d]], np.float32))
    return np.concatenate(tris)


class Buried(unittest.TestCase):
    def test_floor_under_a_closed_box_is_buried_beside_it_not(self):
        # a wall standing in the floor (its foot 10 units below), and the open-shade walls of the lamp test above
        occ = shadows.Occluder(box(-20, 20, -100, 100, -10, 200))
        world = np.array([[0.0, 0.0, 0.0], [0.0, 90.0, 0.0], [40.0, 0.0, 0.0], [0.0, 0.0, 200.0]])
        frames = np.tile(np.eye(3), (4, 1, 1))
        self.assertEqual(bounce.buried_texels(occ, world, frames, level_scale=0.5).tolist(),
                         [True, True, False, False])

    def test_a_lamp_shade_over_the_floor_does_not_bury_it(self):
        z = 60.0
        walls = []
        for x0, x1, y0, y1 in ((-40, 40, -40, -40), (40, 40, -40, 40), (40, -40, 40, 40), (-40, -40, 40, -40)):
            a, b, c, d = (x0, y0, z), (x1, y1, z), (x1, y1, z + 40), (x0, y0, z + 40)
            walls += [[a, b, c], [a, c, d]]
        occ = shadows.Occluder(np.array(walls, np.float32))
        self.assertFalse(bounce.buried_texels(occ, np.zeros((1, 3)), np.eye(3)[None], level_scale=0.5)[0])


class Sources(unittest.TestCase):
    def test_smoothed_sources_carry_light_under_a_table(self):
        # a floor under the sun, a table 60 units square above its middle: the disc of radius 50 around the floor
        # under the table's centre is lit outside the table's shadow (about 54% of its area)
        tris = np.concatenate([quad(-500, 500, -500, 500, 0), box(-30, 30, -30, 30, 50, 60)])
        occ = shadows.Occluder(tris)
        sun = dict(kind='directional', toLight=[0.0, 0.0, 1.0], brightness=1.0, color=[1.0, 1.0, 1.0],
                   lightSourceAngle=0.0)
        src = bounce.SourceIrradiance(occ, tris, [sun], radius=50, per_disc=200, seed=1)
        pts = np.array([[0.0, 0.0, 0.0], [300.0, 0.0, 0.0]])
        e = src(pts, np.tile(UP, (2, 1)))
        exact = bounce.direct_irradiance(occ, [sun], pts + 0.5 * UP, np.tile(UP, (2, 1)))
        self.assertEqual(exact[0, 0], 0.0)
        self.assertAlmostEqual(e[0, 0], 0.54, delta=0.08)
        self.assertAlmostEqual(e[1, 0], 1.0, delta=1e-6)
        # the table's underside (facing down) takes no floor samples: its own, unlit
        self.assertEqual(src(np.array([[0.0, 0.0, 50.0]]), -UP[None])[0, 0], 0.0)

    def test_density_estimate_falls_at_the_edge_of_a_surface(self):
        # a sunlit floor ending at x = 500: in the middle the photon map's estimate is the floor's light, at its edge
        # half (half the disc has no floor), as the mean of the samples found would not say
        tris = quad(-500, 500, -500, 500, 0)
        occ = shadows.Occluder(tris)
        sun = dict(kind='directional', toLight=[0.0, 0.0, 1.0], brightness=1.0, color=[1.0, 1.0, 1.0],
                   lightSourceAngle=0.0)
        pts = np.array([[0.0, 0.0, 0.0], [500.0, 0.0, 0.0]])
        normals = np.tile(UP, (2, 1))
        dens = bounce.SourceIrradiance(occ, tris, [sun], radius=100, per_disc=1600, seed=2, estimate='density')
        mean = bounce.SourceIrradiance(occ, tris, [sun], radius=100, per_disc=1600, seed=2, estimate='mean')
        e = dens(pts, normals)
        self.assertAlmostEqual(e[0, 0], 1.0, delta=0.08)
        self.assertAlmostEqual(e[1, 0], 0.5, delta=0.06)
        self.assertTrue(np.allclose(mean(pts, normals)[:, 0], 1.0))
        with self.assertRaises(ValueError):
            bounce.SourceIrradiance(occ, tris, [sun], radius=100, estimate='median')


class Gather(unittest.TestCase):
    def test_groups_split_the_bounce_by_the_surface_it_left(self):
        # a point on a ceiling (facing down) over two floor halves of different materials, lit from below the
        # ceiling: each half's column is its share, the columns add up to the bounce's flat light, and doubling one
        # half's albedo doubles its column
        tris = np.concatenate([quad(-400, 0, -400, 400, 0), quad(0, 400, -400, 400, 0), quad(-400, 400, -400, 400, 100,
                                                                                        up=False)])
        occ = shadows.Occluder(tris)
        light = point_light(z=90.0)
        frames = np.array([[[1.0, 0, 0], [0, 1.0, 0], [0, 0, -1.0]]])
        world = np.array([[-50.0, 0.0, 100.0]])
        index = np.array([0, 0, 1, 1, 2, 2])
        alb = np.full((6, 3), 0.5)
        coef, split = bounce.gather(occ, tris, alb, [light], world, frames, rays=256, groups=(index, 3))
        self.assertEqual(split.shape, (1, 3))
        self.assertAlmostEqual(float(split.sum()), float(coef.sum()), places=6)
        self.assertGreater(split[0, 0], split[0, 1])       # the half under the point gives more
        self.assertEqual(split[0, 2], 0.0)                 # the ceiling itself is never hit from it
        alb[2:4] = 1.0
        _, doubled = bounce.gather(occ, tris, alb, [light], world, frames, rays=256, groups=(index, 3))
        self.assertAlmostEqual(float(doubled[0, 1]), 2 * float(split[0, 1]), places=6)
        self.assertAlmostEqual(float(doubled[0, 0]), float(split[0, 0]), places=6)

    def test_hemisphere_directions_cover_equal_solid_angles(self):
        d = bounce.hemisphere_directions(64)
        self.assertEqual(len(d), 64)
        self.assertTrue(np.allclose(np.linalg.norm(d, axis=1), 1))
        self.assertAlmostEqual(float(d[:, 2].mean()), 0.5, places=6)    # uniform in solid angle
        self.assertTrue((d[:, 2] > 0).all())

    def test_open_sky_lights_the_three_channels_alike(self):
        occ = shadows.Occluder(np.zeros((0, 3, 3), np.float32))
        frames = np.array([[[1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]]])
        coef = bounce.gather(occ, np.zeros((0, 3, 3)), np.zeros((0, 3)), [], np.zeros((1, 3)), frames, rays=256,
                             environment=(0.1, 0.2, 0.3))[0]
        # each channel: sum over rays of radiance x solid angle x S(e, 0) x lobe; isotropic, so equal per channel
        self.assertTrue(np.allclose(coef[:, 0], coef[0, 0], rtol=0.03))
        self.assertTrue(np.allclose(coef[0] / coef[0, 0], [1, 2, 3], rtol=1e-6))
        # against a fine numerical integral of the same quantity
        fine = bounce.hemisphere_directions(40000)
        want = 2 * math.pi / len(fine) * (codec.elevation_term(fine[:, 2], np.zeros(len(fine)))[:, None] *
                                          codec.lobes(fine, np.zeros(len(fine)))).sum(0) * 0.1
        self.assertTrue(np.allclose(coef[:, 0], want, rtol=0.03))

    def test_a_lit_white_ceiling_bounces_light_down(self):
        # floor point at the origin under a white ceiling at z 100, lit from below by a point light
        ceiling = quad(-500, 500, -500, 500, 100, up=False)
        occ = shadows.Occluder(ceiling)
        light = dict(point_light(z=50.0, radius=0.0), radius=400.0)
        frames = np.array([[[1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]]])
        coef, occlusion = bounce.gather(occ, ceiling, np.full((2, 3), 0.8), [light], np.zeros((1, 3)), frames,
                                        rays=256, occlusion_distance=150.0)
        self.assertTrue((coef > 0).all())
        # rays meet the ceiling (98.5 units above the ray start) within 150 units when steeper than z = 98.5 / 150
        self.assertAlmostEqual(float(occlusion[0]), 1 - (100 - bounce.GATHER_OFFSET) / 150, delta=0.05)
        dark = bounce.gather(occ, ceiling, np.zeros((2, 3)), [light], np.zeros((1, 3)), frames, rays=64)
        self.assertTrue(np.all(dark == 0))                                # a black ceiling reflects nothing

    def test_spot_lights_bounce_sources_through_a_doubled_cone(self):
        # a wall point 45 degrees off a spot's axis: outside its 30-degree cone for direct light, inside the doubled
        # cone Lightmass uses for bounce sources (UDK BakeCalib9)
        spot = dict(kind='spot', location=[0.0, 0.0, 0.0], direction=[1.0, 0.0, 0.0], innerConeAngle=20.0,
                    outerConeAngle=30.0, radius=1000.0, falloffExponent=2.0, lightSourceRadius=0.0, brightness=1.0,
                    color=[1.0, 1.0, 1.0])
        occ = shadows.Occluder(np.zeros((0, 3, 3), np.float32))
        point, normal = np.array([[200.0, 200.0, 0.0]]), np.array([[-1.0, 0.0, 0.0]])
        widened = bounce.direct_irradiance(occ, [spot], point, normal)
        real = bounce.direct_irradiance(occ, [spot], point, normal, spot_cone_scale=1.0)
        self.assertTrue((widened > 0).all())
        self.assertTrue((real == 0).all())
        # on the axis both agree
        axis = bounce.direct_irradiance(occ, [spot], np.array([[200.0, 0.0, 0.0]]), normal)
        self.assertTrue(np.allclose(axis, bounce.direct_irradiance(occ, [spot], np.array([[200.0, 0.0, 0.0]]), normal,
                                                                   spot_cone_scale=1.0)))

    def test_smooth_reproduces_and_fills(self):
        gw = np.array([[0.0, 0, 0], [10.0, 0, 0]])
        gn = np.tile(UP, (2, 1))
        gv = np.array([[1.0], [3.0]])
        on = bounce.smooth(gw, gn, gv, np.array([[0.0, 0, 0]]), UP[None], sigma=0.5)
        self.assertAlmostEqual(float(on[0, 0]), 1.0, places=6)                 # a narrow filter keeps the point
        mid = bounce.smooth(gw, gn, gv, np.array([[5.0, 0, 0]]), UP[None], sigma=5.0)
        self.assertAlmostEqual(float(mid[0, 0]), 2.0, places=6)                # halfway takes both equally
        # a texel facing the other way takes no gather point that disagrees, so falls back to the nearest
        flip = bounce.smooth(gw, gn, gv, np.array([[4.0, 0, 0]]), -UP[None], sigma=50)
        self.assertAlmostEqual(float(flip[0, 0]), 1.0, places=6)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import lighting_records as lighting
        import relight
        cls.relight = relight
        cls.p = lighting.Package(BAR)
        cls.scene = relight.Scene(cls.p, samples=16, bounce_rays=16, stride=4)
        cls._shared = {}

    def shared(self, key, make):
        """make() worked out once for the class: what several tests only read (review finding 61; the relight is
        deterministic, Determinism)."""
        if key not in self._shared:
            self._shared[key] = make()
        return self._shared[key]

    def unedited(self):
        """The floor relit in the scene as it is, with no edit (read by three tests)."""
        return self.shared('unedited', lambda: self.relight.relight_component(self.p, FLOOR, self.scene))

    def moved_table(self):
        """(the pool table, where it goes, the scene after it is moved there turned a quarter): read by two tests."""
        table, at = 'XComDestructibleActor_491', [-48.0, 240.0, 24.0]
        after = self.shared('moved table', lambda: self.relight.Scene(
            self.p, samples=16, bounce_rays=16, stride=4, remove_casters=[table],
            add_casters=[dict(source=table, location=at, rotation=[0, 16384, 0])]))
        return table, at, after

    def test_scene_reads_the_maps_lightmass_settings(self):
        s = self.scene
        self.assertEqual(s.level_scale, 0.5)
        self.assertTrue(np.allclose(s.environment, (np.array([64, 69, 97]) / 255) ** 2.2 * bounce.ENVIRONMENT_SCALE,
                                    atol=1e-6))
        self.assertEqual(s.counts['areaLights'], 137)
        self.assertGreater(s.counts['transmittingTriangles'], 0)
        self.assertGreater(s.counts['casters'], 700)
        self.assertTrue((s.albedo_per_triangle >= 0).all() and (s.albedo_per_triangle <= 0.95).all())

    def test_floor_triangles_face_up_in_embree(self):
        import lightmap_texels
        floor = self.p.by_name[FLOOR]
        tris = self.scene.triangles[self.scene.owners == floor]
        ng = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        top = tris[:, :, 2].min(1) > 17.9
        self.assertGreater(top.sum(), 10)
        self.assertTrue((ng[top, 2] > 0).all())
        self.assertIsNotNone(lightmap_texels)

    def test_shadowed_relight_matches_the_original_and_checker_keeps_it(self):
        r = self.relight.relight_component(self.p, FLOOR, self.scene, checker=192.0)
        rep = r['report']
        self.assertGreater(rep['flatLight']['correlation'], 0.95)
        self.assertGreater(rep['flatLight']['within10pct'], 0.5)
        self.assertAlmostEqual(rep['texels']['ours'] / rep['texels']['covered'], 0.5, delta=0.1)
        # the original's squares, re-encoded under the shared scale, still give the original's light
        b, a, cov = r['before'], r['after'], r['covered']
        sel = cov & (b.sum(2) > 0.2)
        ratio = a.sum(2)[sel] / b.sum(2)[sel]
        self.assertGreater(np.mean(np.abs(ratio - 1) < 0.05), 0.45)

    def test_floor_texels_under_the_walls_are_left_out(self):
        # the pool-table floor runs under the room's wall pieces: those texels are buried, not relit
        r = self.unedited()
        t = r['report']['texels']
        self.assertGreater(t['buried'], 0.05 * (t['covered'] + t['buried']))
        self.assertLess(t['buried'], 0.3 * (t['covered'] + t['buried']))

    def test_an_edit_changes_only_what_it_reaches(self):
        # delta mode: the pool table casts no shadow and one ceiling spot over the open floor is off
        after = self.relight.Scene(self.p, samples=16, bounce_rays=16, stride=4,
                                   remove_casters=['XComDestructibleActor_491'], remove_lights=['SpotLight_3'])
        self.assertEqual((after.counts['casters'], len(after.lights)),
                         (self.scene.counts['casters'] - 1, len(self.scene.lights) - 1))
        r = self.relight.relight_component(self.p, FLOOR, self.scene, after=after)
        b, a, cov = r['before'].sum(2), r['after'].sum(2), r['covered']
        lit = cov & (b > 0.05)
        ratio = a[lit] / b[lit]
        self.assertGreater(r['report']['delta']['texelsChanged'], 2000)
        # most of the floor keeps the original bake (re-encoded), and nothing goes black that was lit
        self.assertGreater(np.mean(np.abs(ratio - 1) < 0.05), 0.75)
        self.assertGreater(ratio.min(), 0.0)
        # the spot's pool, under it on the floor, loses most of its light
        self.assertLess(np.percentile(ratio, 2), 0.5)
        self.assertTrue(np.isfinite(a).all())

    def test_removing_a_piece_that_casts_no_shadow_removes_nothing_and_an_unknown_name_is_refused(self):
        # a light's actor is in the map and casts nothing (F-59: pieces with CastShadow off on URB_PoliceStation)
        after = self.relight.Scene(self.p, samples=4, bounce_rays=0, emissive=False, remove_casters=['SpotLight_3'])
        self.assertEqual((len(after.triangles), after.edit_boxes), (len(self.scene.triangles), []))
        with self.assertRaisesRegex(ValueError, 'no actor or component named'):
            self.relight.Scene(self.p, samples=4, bounce_rays=0, emissive=False, remove_casters=['NoSuchActor_1'])

    def test_a_removed_piece_opens_the_floor_under_it(self):
        # the island counter's sections stand solid on the floor: the floor inside one is buried until it goes
        after = self.relight.Scene(self.p, samples=16, bounce_rays=16, stride=4,
                                   remove_casters=['XComFracLevelActor_20'])
        r = self.relight.relight_component(self.p, FLOOR, self.scene, after=after)
        t = r['report']['texels']
        self.assertGreater(t['opened'], 100)
        base = self.unedited()['report']['texels']
        self.assertEqual(t['buried'] + t['opened'], base['buried'])
        # the opened floor was black in the original bake and is lit now
        b, a, cov = r['before'].sum(2), r['after'].sum(2), r['covered']
        self.assertGreater(int((cov & (b < 0.01) & (a > 0.1)).sum()), 0.5 * t['opened'])
        self.assertTrue(np.isfinite(a).all())

    def test_a_copy_where_its_source_stood_changes_nothing(self):
        # the pool table removed and a copy of it put back at its own pose: the same triangles, the same light
        table = 'XComDestructibleActor_491'
        loc, rot = self.p.effective(self.p.by_name['TheWorld.PersistentLevel.' + table], 'Location'), [0, 0, 0]
        after = self.relight.Scene(self.p, samples=16, bounce_rays=16, stride=4, remove_casters=[table],
                                   add_casters=[dict(source=table, location=loc, rotation=rot)])
        self.assertEqual(after.counts['triangles'], self.scene.counts['triangles'])
        self.assertEqual(after.copies[0]['triangles'], 1348)
        r = self.relight.relight_component(self.p, FLOOR, self.scene, after=after)
        self.assertLessEqual(r['report']['delta']['texelsChanged'], 5)

    def test_a_moved_copy_shadows_the_floor_at_its_new_place(self):
        # the pool table moved into the ceiling spot's pool by the island counter's corner, turned a quarter
        import lightmap_fields
        import lightmap_texels
        table, at, after = self.moved_table()
        r = self.relight.relight_component(self.p, FLOOR, self.scene, after=after)
        ci = self.p.by_name[FLOOR]
        fields = lightmap_fields.component_fields(self.p, ci)['lods'][0]['lightmap']
        tex = lightmap_fields.texture_fields(self.p, fields['slots'][1]['index'])
        size = [tex['mips'][0]['width'], tex['mips'][0]['height']]
        geo = lightmap_texels.rasterise(lightmap_texels.component_mesh(self.p, ci),
                                        lightmap_texels.world_matrix(self.p, ci), fields, size)
        w, x0, y0 = geo['world'], geo['rect'][0], geo['rect'][1]
        b = r['before'].sum(2)[geo['py'] - y0, geo['px'] - x0]
        a = r['after'].sum(2)[geo['py'] - y0, geo['px'] - x0]
        # under the copy (yaw 90: 218 units along x, 120 along y) most of the pool's light goes
        under = (np.abs(w[:, 0] - at[0]) < 90) & (np.abs(w[:, 1] - at[1]) < 45) & (b > 0.5)
        self.assertGreater(under.sum(), 100)
        self.assertLess(np.median(a[under] / b[under]), 0.5)
        # far from both places the floor keeps its bake
        far = (np.hypot(w[:, 0] - at[0], w[:, 1] - at[1]) > 600) & (np.hypot(w[:, 0] - 528, w[:, 1] - 670) > 600)
        far &= b > 0.05
        self.assertGreater(np.mean(np.abs(a[far] / b[far] - 1) < 0.02), 0.95)

    def test_an_edit_knows_where_it_changes_and_which_receivers_are_near(self):
        table, at, after = self.moved_table()
        old, new = after.edit_boxes
        self.assertTrue(467 < old[0] < 470 and 588 < old[1] < 590 and 560 < old[2] < 562 and 778 < old[3] < 780)
        # the table stands centred on its origin; its copy, turned a quarter, is 218 units along x and 121 along y,
        # centred on its new place
        self.assertAlmostEqual(new[1] - new[0], old[3] - old[2], delta=1)
        self.assertAlmostEqual(new[3] - new[2], old[1] - old[0], delta=1)
        self.assertAlmostEqual((new[0] + new[1]) / 2, at[0], delta=3)
        self.assertAlmostEqual((new[2] + new[3]) / 2, at[1], delta=3)
        near = self.relight.receivers_near(self.p, after.edit_boxes, 32)     # the table's legs stand on the floor
        self.assertIn(FLOOR, near)
        wide = self.relight.receivers_near(self.p, after.edit_boxes, 1024)
        self.assertTrue(set(near) < set(wide))
        lit = self.relight.receivers_near(self.p, [[-1e9, 1e9, -1e9, 1e9, -1e9, 1e9]], 0)
        self.assertTrue(set(wide) < set(lit))
        self.assertEqual(self.relight.receivers_near(self.p, [], 1024), [])

    def test_an_edit_that_reaches_nothing_changes_nothing(self):
        far = max((l for l in self.scene.lights if 'location' in l and l['role'] == 'static'),
                  key=lambda l: np.linalg.norm(np.asarray(l['location'][:2]) - [400.0, 500.0]) - l['radius'])
        after = self.relight.Scene(self.p, samples=16, bounce_rays=16, stride=4, remove_lights=[far['component']])
        r = self.relight.relight_component(self.p, FLOOR, self.scene, after=after)
        self.assertEqual(r['report']['delta']['texelsChanged'], 0)
        b, a, cov = r['before'].sum(2), r['after'].sum(2), r['covered']
        lit = cov & (b > 0.05)
        self.assertGreater(np.mean(np.abs(a[lit] / b[lit] - 1) < 0.02), 0.95)

    def test_unrelit_texels_keep_the_original_under_the_new_scale(self):
        r = self.unedited()
        b, a = r['before'].sum(2), r['after'].sum(2)
        self.assertGreater(r['report']['texels']['keptOriginal'], 0)
        self.assertTrue(r['images']['nac_mask'].all())
        # every texel in the rectangle is written; those far from our texels decode to the original's light
        far = ~self.relight.lightmap_texels.dilate(np.zeros(r['covered'].shape + (1,)), r['covered'])[1]
        sel = far & (b > 0.05)
        if sel.any():
            self.assertGreater(np.mean(np.abs(a[sel] / b[sel] - 1) < 0.05), 0.9)


class Determinism(unittest.TestCase):
    def test_a_points_samples_do_not_depend_on_the_batch(self):
        pts = np.array([[1.0, 2.0, 3.0], [100.5, -20.25, 7.0], [0.0, 0.0, 0.0]])
        alone = shadows.point_turns(pts[1:2], seed=5)
        batch = shadows.point_turns(pts, seed=5)
        self.assertEqual(float(alone[0]), float(batch[1]))
        self.assertNotEqual(float(batch[0]), float(batch[1]))
        self.assertNotEqual(float(shadows.point_turns(pts[1:2], seed=6)[0]), float(alone[0]))
        self.assertTrue(((batch >= 0) & (batch < 2 * math.pi)).all())
        # spread: many points give angles all round the circle
        many = shadows.point_turns(np.random.default_rng(0).uniform(-500, 500, (4000, 3)), seed=1)
        self.assertLess(np.abs(np.histogram(many, 8, (0, 2 * math.pi))[0] / 500 - 1).max(), 0.15)


if __name__ == '__main__':
    unittest.main()
