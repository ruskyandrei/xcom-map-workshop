"""What the page draws an effect's likeness from (export 29, draw version 4 since export 31;
tools/viewer/effects_draw.py; the effects and sounds plan, Part J1, stage FXV1). The first tests run on made-up values:
a lookup table's shape, what a texture's pixels hold, which texture gives the colour and which the shape. The install
tests pin systems of URB_Bar whose numbers are known from the map."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import effects_draw as ed  # noqa: E402
import effects_metadata as em  # noqa: E402
from test_effects_metadata import INSTALL, WHY, records  # noqa: E402


def raw(values):
    return struct.pack('<i%df' % len(values), len(values), *values)


class Tables(unittest.TestCase):
    def test_a_constant(self):
        t = ed.table(dict(LookupTable=raw([3, 3, 3, 3])), vector=False)
        self.assertEqual((t['op'], t['chunk'], t['entries'], t['min'], t['max']), (1, 1, [[3.0], [3.0]], 3.0, 3.0))

    def test_a_random_range_and_a_vector(self):
        t = ed.table(dict(Op=2, LookupTableNumElements=2, LookupTableChunkSize=2, LookupTable=raw([0.6, 0.5, 0.6, 0.5, 0.6, 0.5])), False)
        self.assertEqual((t['op'], t['chunk'], len(t['entries'])), (2, 2, 2))
        self.assertEqual([round(v, 3) for v in t['entries'][0]], [0.6, 0.5])
        v = ed.table(dict(Op=2, Type=4, LookupTableChunkSize=6, LookupTable=raw([0.1, 1] + [0.1] * 3 + [1] * 3 + [0.1] * 3 + [1] * 3)), True)
        self.assertEqual((v['lock'], v['chunk'], len(v['entries']), len(v['entries'][0])), (4, 6, 2, 6))

    def test_a_curve_over_a_life(self):
        values = [0.0, 1.0] + [k / 20 for k in range(21)]
        t = ed.table(dict(LookupTableTimeScale=20.0, LookupTable=raw(values)), False)
        self.assertEqual((len(t['entries']), t['scale'], t['start']), (21, 20.0, 0.0))

    def test_the_width_follows_the_operation_where_it_is_not_saved(self):
        t = ed.table(dict(Op=3, LookupTable=raw([-0.5, 0.5] + [-0.5] * 3 + [0.5] * 3 + [-0.5] * 3 + [0.5] * 3)), True)
        self.assertEqual((t['op'], t['chunk']), (3, 6))

    def test_another_shape_is_not_read(self):
        self.assertIsNone(ed.table(dict(LookupTable=raw([1, 1])), False))                     # no entry
        self.assertIsNone(ed.table(dict(LookupTable=raw([1, 1, 1, 1, 1, 1])), True))          # not whole entries
        self.assertIsNone(ed.table(dict(Op=1, LookupTableChunkSize=2, LookupTable=raw([1, 1, 1, 1])), False))
        self.assertIsNone(ed.table(dict(Op=7, LookupTable=raw([1, 1, 1, 1])), False))
        self.assertIsNone(ed.table({}, False))


class Traits(unittest.TestCase):
    """texture_traits on made-up pictures (64 by 64 PNGs), each standing for one kind the game's effects use."""
    def traits(self, rgba):
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 't.png'
            Image.fromarray(np.asarray(rgba, dtype=np.uint8), 'RGBA').save(path)
            return ed.texture_traits(path)

    def picture(self, rgb, alpha=255):
        import numpy as np
        ramp = np.linspace(0, 1, 64)[None, :, None] * np.ones((64, 1, 1))
        out = np.concatenate([ramp * np.asarray(rgb, dtype=float)[None, None, :], np.full((64, 64, 1), 0.0)], axis=2)
        out[..., 3] = alpha if not callable(alpha) else alpha(ramp[..., 0])
        return out

    def test_a_grey_ramp_is_grey_and_holds_no_shape(self):
        t = self.traits(self.picture([200, 200, 200]))
        self.assertEqual((t['grey'], t['packed'], t['shape']), (True, False, False))

    def test_an_orange_flame_is_a_colour(self):
        t = self.traits(self.picture([255, 140, 20]))
        self.assertEqual((t['grey'], t['packed']), (False, False))

    def test_magenta_and_blue_are_packed_channels(self):
        # the night smoke's T_Roiling_Smoke_SubUV: red the light from below, green from above, blue the density
        t = self.traits(self.picture([230, 20, 200]))
        self.assertEqual((t['grey'], t['packed']), (False, True))
        self.assertGreater(t['redShare'], 0.9)
        glare = self.traits(self.picture([2, 40, 230]))
        self.assertTrue(glare['packed'])
        self.assertLess(glare['redShare'], 0.33)       # its red is all but empty: it shapes by its brightness

    def test_red_and_green_unrelated_with_no_blue_are_packed(self):
        import numpy as np
        rng = np.random.default_rng(1)
        out = np.zeros((64, 64, 4))
        out[..., 0], out[..., 1], out[..., 3] = rng.uniform(0, 250, (64, 64)), rng.uniform(0, 250, (64, 64)), 255
        self.assertTrue(self.traits(out)['packed'])

    def test_an_alpha_shape_and_a_nearly_empty_alpha(self):
        self.assertTrue(self.traits(self.picture([200, 160, 90], alpha=lambda r: r * 255))['shape'])
        # GEN_MaterialParents' Flame: an alpha that varies but stays near nothing holds no shape
        self.assertFalse(self.traits(self.picture([255, 140, 20], alpha=lambda r: (r > 0.97) * 59))['shape'])


def texture(key, name, parameter=None, grey=False, shape=False, packed=False, red=1.0, bright=0.5):
    return dict(key=key, name='Pkg.' + name, parameter=parameter, grey=grey, shape=shape, packed=packed, redShare=red, bright=bright)


class Pictures(unittest.TestCase):
    def pick(self, candidates, grid=False, solid=False, added=False):
        d = ed.pick_textures(candidates, grid, solid, added)
        return d['picture'], d['opacity'], d['mask'], d['maskFrom']

    def test_the_fire_colour_from_its_flame_and_its_shape_from_a_grey_mask(self):
        # M_Fire_Chunk: a colour picture whose alpha holds nothing, the grey licks, the packed scrolling noise
        self.assertEqual(self.pick([texture('0', 'Flame'), texture('1', 'T_Fire_Licks_Large', grey=True),
                                    texture('2', 'T_Roiling_Smoke_Scrolling', packed=True, red=0.7)]),
                         ('0', 'brightness', '1', 'brightness'))

    def test_a_normal_map_is_neither(self):
        self.assertEqual(self.pick([texture('0', 'T_Smoke_Cloud_Scrolling_NML'), texture('1', 'T_FireSmoke_Scrolling'),
                                    texture('2', 'T_Fire_Licks', 'Flame_Mask', grey=True)]), ('1', 'brightness', '2', 'brightness'))

    def test_the_steam_is_shaped_by_its_packed_dust_not_its_grey_blast(self):
        self.assertEqual(self.pick([texture('0', 'T_Dust_Grainy_3Channel', packed=True, red=0.497),
                                    texture('1', 'T_fireyblast01', grey=True, bright=0.086)]), (None, 'none', '0', 'red'))

    def test_the_night_smoke_has_no_colour_picture(self):
        self.assertEqual(self.pick([texture('0', 'T_Roiling_Smoke_Soft_SubUV', 'Smoke_SubUV', packed=True, red=1.0),
                                    texture('1', 'T_Smoke_Cloud_Scrolling_Blurred_NML'),
                                    texture('2', 'T_Roiling_Smoke_Scrolling', packed=True, red=0.7)], grid=True),
                         (None, 'none', '0', 'red'))

    def test_a_packed_mask_with_no_red_shapes_by_its_brightness(self):
        self.assertEqual(self.pick([texture('0', 'T_Circle_Glare', packed=True, red=0.03)]), (None, 'none', '0', 'brightness'))

    def test_a_moth_on_a_card_is_cut_by_its_alpha_and_nothing_else(self):
        self.assertEqual(self.pick([texture('0', 'T_Moth_Blurry', shape=True), texture('1', 'T_Moth_Sharp', shape=True)]),
                         ('0', 'alpha', None, None))

    def test_an_added_glow_takes_its_grey_texture_as_its_picture(self):
        # the police lights: a round grey glow with its shape in its alpha, never a gradient that fills the quad alone
        glow = texture('0', 'T_glowBit', grey=True, shape=True, bright=0.159)
        self.assertEqual(self.pick([glow], added=True), ('0', 'alpha', None, None))
        core = [glow, texture('1', 'T_StarburstBW', grey=True), texture('2', 'T_Beam_Gradient_Vertical_3Channel', red=1.0)]
        self.assertEqual(self.pick(core, added=True), ('0', 'alpha', '2', 'red'))        # its gradient is named as a mask
        # see-through, the same glow alone shapes the particle's own colour by its alpha
        self.assertEqual(self.pick([glow]), (None, 'none', '0', 'alpha'))
        # with no picture, a texture with an alpha shape shapes before a packed one
        self.assertEqual(self.pick([texture('0', 'T_Noise_Specks_Sparse', packed=True, red=0.38),
                                    texture('1', 'T_ExplosionDust_3Channel', shape=True, packed=True, red=1.0)]), (None, 'none', '1', 'red'))

    def test_a_grey_picture_where_nothing_else_is(self):
        self.assertEqual(self.pick([texture('0', 'T_softSmoke2', grey=True), texture('1', 't_Smoke_Alpha_Light', 'Mask', grey=True)]),
                         ('0', 'brightness', '1', 'brightness'))
        self.assertEqual(self.pick([texture('0', 'Fogged_Body_Webbing_SubUV', grey=True)]), (None, 'none', '0', 'brightness'))

    def test_a_solid_picture_is_cut_by_its_alpha_only(self):
        self.assertEqual(self.pick([texture('0', 'T_Log_Masked', shape=True)], solid=True), ('0', 'alpha', None, None))
        self.assertEqual(self.pick([texture('0', 'Rough_Debris')], solid=True), ('0', 'none', None, None))

    def test_sub_images_take_the_texture_named_for_them(self):
        both = [texture('0', 'T_Fire'), texture('1', 'T_Chunk_SubUV')]
        self.assertEqual(self.pick(both, grid=True)[0], '1')
        self.assertEqual(self.pick(both)[0], '0')

    def test_nothing_to_pick(self):
        self.assertEqual(self.pick([]), (None, 'none', None, None))


class MaterialColours(unittest.TestCase):
    def test_only_colours_and_tints_and_no_specular(self):
        class P:
            children = {5: [6, 7, 8, 9]}
            classes = {6: 'MaterialExpressionVectorParameter', 7: 'MaterialExpressionVectorParameter',
                       8: 'MaterialExpressionVectorParameter', 9: 'MaterialExpressionTextureSampleParameter2D'}
            values = {6: ('Dark_Color', [0.015, 0.017, 0.027, 1.0]), 7: ('SPC_Color', [1, 1, 1, 64]), 8: ('Tiling', [2, 2, 0, 1])}

            def own(self, index, key, default=None):
                if key == 'Parent':
                    return 0
                if key == 'VectorParameterValues':
                    return None
                name, value = self.values.get(index, (None, None))
                return {'ParameterName': name, 'DefaultValue': value}.get(key, default)

            def cls(self, index):
                return self.classes.get(index, 'Material')

            def structs(self, raw):
                return []
        self.assertEqual(ed.material_colours(P(), 5), {'Dark_Color': [0.015, 0.017, 0.027]})


# what URB_Bar's textures' pixels hold (texture_traits on the export's PNGs), for an exporter that writes none
BAR_TRAITS = {'T_Dust_Grainy_3Channel': dict(grey=False, shape=False, packed=True, redShare=0.497, bright=0.418),
              'T_fireyblast01': dict(grey=True, shape=False, packed=False, redShare=0.998, bright=0.086),
              'T_Moth_Blurry': dict(grey=False, shape=True, packed=False, redShare=1.0, bright=0.49),
              'T_Moth_Sharp': dict(grey=False, shape=True, packed=False, redShare=1.0, bright=0.481)}


class Stub:
    """An exporter that keeps nothing: a texture's key is its export index (its traits as BAR_TRAITS has them)."""
    def __init__(self, p):
        self.p, self.textures = p, {}

    def texture(self, index):
        info = dict(format=self.p.effective(index, 'Format'))
        known = BAR_TRAITS.get(self.p.name(index).rsplit('.', 1)[-1])
        if known:
            info['traits'] = dict(known)
        self.textures[str(index)] = info
        return str(index)

    def particle_mesh(self, mesh, override=0):
        return 'mesh-%d' % mesh, ['material'], [override]


@unittest.skipUnless(INSTALL and INSTALL.exists(), WHY)
class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import copy
        from export import compiled_textures
        bar = records('URB_Bar')
        cls.by, cls.p = bar['by'], bar['package']
        cls.systems = copy.deepcopy(bar['systems'])
        ed.attach(cls.p, em.Defaults(cls.p), cls.systems, Stub(cls.p), compiled_textures)

    def system(self, actor):
        return self.systems[self.by[actor]['system']]

    def test_the_steam(self):
        steam = self.system('Emitter_16')
        self.assertEqual(steam['name'], 'Steam_Small')
        self.assertEqual(steam['drawVersion'], ed.DRAW_VERSION)
        live = [e['draw'] for e in steam['emitters'] if e['draw']]
        self.assertTrue(live)
        d = live[0]
        self.assertEqual((d['kind'], d['blend'], d['facing'], d['subImages'], d['loops']), ('sprite', 'BLEND_Translucent', 'PSA_Square', [1, 1], 0))
        # no colour picture: its shape is the red channel of its packed dust (not its grey blast), its colour its own
        names = {t['key']: t['name'] for t in d['textures']}
        self.assertIsNone(d['picture'])
        self.assertEqual((names[d['mask']], d['maskFrom'], d['opacity']), ('FX_Shared.T_Dust_Grainy_3Channel', 'red', 'none'))
        # its rate is fed by the Wind_Strength parameter; its colour by Color, as its offers say
        self.assertEqual((d['rate']['parameter'], d['rate']['kind'], d['rate']['output']), ('Wind_Strength', 'scalar', [1.0, 4.0]))
        colour = next(m for m in d['modules'] if m['cls'] == 'Color')
        self.assertEqual(colour['StartColor']['parameter'], 'Color')
        # a random size between two vectors, a life held from the class's default shape
        size = next(m for m in d['modules'] if m['cls'] == 'Size')['StartSize']
        self.assertEqual((size['op'], size['chunk'], len(size['entries'][0])), (2, 6, 6))
        # its life too is the parameter's: longer in less wind
        life = next(m for m in d['modules'] if m['cls'] == 'Lifetime')['Lifetime']
        self.assertEqual((life['parameter'], [round(v, 2) for v in life['output']]), ('Wind_Strength', [2.8, 0.7]))
        turn = next(m for m in d['modules'] if m['cls'] == 'Rotation')['StartRotation']
        self.assertEqual((turn['op'], turn['chunk']), (2, 2))

    def test_a_beam_is_one_burst(self):
        beam = self.system('Emitter_4')
        d, = [e['draw'] for e in beam['emitters'] if e.get('draw')]
        self.assertEqual((d['loops'], len(d['bursts'])), (1, 1))
        self.assertGreater(d['bursts'][0]['count'], 0)

    def test_mesh_particles(self):
        moths = next(s for s in self.systems.values() if s and s['name'] == 'P_Moths_Centered')
        d = next(e['draw'] for e in moths['emitters'] if e.get('draw'))
        self.assertEqual(d['kind'], 'mesh')
        self.assertTrue(d['mesh'].startswith('mesh-') and d['materials'])
        self.assertIn('Orbit', d['ignored'])
        self.assertEqual(d['rateScale']['parameter'], 'Spawn')
        # a mesh turn saved as nothing but its floats: the shape is the class default's (random, two vectors)
        turn = next(m for m in d['modules'] if m['cls'] == 'MeshRotation')['StartRotation']
        self.assertEqual((turn['op'], turn['chunk']), (2, 6))

    def test_every_emitter_is_drawn_or_says_why(self):
        unread = []
        for s in self.systems.values():
            for e in (s or {}).get('emitters', []):
                self.assertIn('draw', e)
                if e['draw'] is None:
                    self.assertTrue(e['why'])
                    continue
                self.assertNotIn('why', e)
                for m in e['draw']['modules']:
                    unread += [v['unread'] for v in m.values() if isinstance(v, dict) and 'unread' in v]
        # what isn't read is a curve the cook kept as an object, never a table of another shape
        self.assertTrue(all(why.startswith('kept as Distribution') for why in unread), unread)
        self.assertLess(len(unread), 6)

    def test_an_emitter_that_only_sends_events_says_so(self):
        # each fire's last emitter (CsmallScout_Farm's P_Fire_Big's seventh): the engine's default particle material,
        # one particle after ten seconds and an event generator, nothing the game shows (no material missing)
        import copy
        from export import compiled_textures
        farm = records('CsmallScout_Farm')
        systems = copy.deepcopy(farm['systems'])
        ed.attach(farm['package'], em.Defaults(farm['package']), systems, Stub(farm['package']), compiled_textures)
        fire = next(s for s in systems.values() if s and s['name'] == 'P_Fire_Big')
        self.assertEqual(fire['emitters'][6].get('why'), 'it only sends events: nothing is seen')
        whys = [e.get('why') for s in systems.values() for e in (s or {}).get('emitters', []) if e.get('draw') is None]
        self.assertNotIn('its material is in another package', whys)


if __name__ == '__main__':
    unittest.main()
