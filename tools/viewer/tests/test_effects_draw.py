"""What the page draws an effect's likeness from (export 29; tools/viewer/effects_draw.py; the effects and sounds
plan, Part J1, stage FXV1). The first tests run on made-up values: a lookup table's shape, which texture is the
picture and which the mask. The install tests pin systems of URB_Bar whose numbers are known from the map."""
import struct
import sys
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


class Pictures(unittest.TestCase):
    def pick(self, names, grid=False):
        return ed.pick_textures([(str(n), 'Pkg.' + name, parameter, alpha) for n, (name, parameter, alpha) in enumerate(names)], grid)

    def test_a_normal_map_is_no_picture_and_a_mask_is_the_mask(self):
        self.assertEqual(self.pick([('T_Smoke_Cloud_Scrolling_NML', None, False), ('T_FireSmoke_Scrolling', None, False),
                                    ('T_Fire_Licks', 'Flame_Mask', False)]), ('1', '2'))
        self.assertEqual(self.pick([('T_softSmoke2', None, False), ('t_Smoke_Alpha_Light', 'Mask', False)]), ('0', '1'))

    def test_a_mask_alone_shapes_a_plain_colour(self):
        self.assertEqual(self.pick([('T_Distortion_Wave_NonClamped', None, False), ('T_square_edge_mask', None, False)]), (None, '1'))

    def test_sub_images_take_the_texture_named_for_them(self):
        self.assertEqual(self.pick([('T_Fire', None, False), ('T_Chunk_SubUV', None, False)], grid=True)[0], '1')
        self.assertEqual(self.pick([('T_Fire', None, False), ('T_Chunk_SubUV', None, False)])[0], '0')

    def test_nothing_to_pick(self):
        self.assertEqual(self.pick([]), (None, None))


class Stub:
    """An exporter that keeps nothing: a texture's key is its export index."""
    def __init__(self, p):
        self.p, self.textures = p, {}

    def texture(self, index):
        self.textures[str(index)] = dict(format=self.p.effective(index, 'Format'))
        return str(index)

    def particle_mesh(self, mesh, override=0):
        return 'mesh-%d' % mesh, ['material']


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
        self.assertTrue(d['picture'] and d['opacity'] in ('alpha', 'brightness'))
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


if __name__ == '__main__':
    unittest.main()
