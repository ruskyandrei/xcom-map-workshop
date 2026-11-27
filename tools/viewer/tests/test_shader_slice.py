"""A material's program (shader_slice.py, shader_eval.py): made-up shaders for each rule (a lerp by the vertex
colour, a UV scaled in the pixel shader, an input it refuses), and on the install ENV_ForestGround's program as the
game mixes its layers, a one-texture prop, a tinted building, a cut-out, a material reading two UV channels, and the
colour sliced from the lightmap pass agreeing with the pass without one."""
from pathlib import Path
import json
import struct
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import shader_slice as ss  # noqa: E402
import shader_eval  # noqa: E402
import shader_cache  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'upk' / 'tests'))
from test_sm3 import op, CACHE, NO_CACHE  # noqa: E402

TYPES = {'r': 0, 'v': 1, 'c': 2, 'o': 6, 'oC': 8, 's': 10}


def reg_bits(kind, index):
    t = TYPES[kind]
    return index | ((t & 7) << 28) | ((t & 0x18) << 8) | 0x80000000


def d(kind, index, mask='xyzw', sat=False):
    bits = sum(1 << (16 + 'xyzw'.index(c)) for c in mask)
    return reg_bits(kind, index) | bits | (0x100000 if sat else 0)


def s(kind, index, swizzle='xyzw', mod=0):
    sw = sum('xyzw'.index(c) << (16 + 2 * k) for k, c in enumerate(swizzle))
    return reg_bits(kind, index) | sw | (mod << 24)


def ctab(constants):
    """A constant table comment: [(name, register set, index, count)]."""
    header = 28
    strings = b''
    names = []
    base = header + 20 * len(constants)
    for name, *_ in constants:
        names.append(base + len(strings))
        strings += name.encode() + b'\0'
    creator = base + len(strings)
    strings += b'test\0'
    target = base + len(strings)
    strings += b'ps_3_0\0'
    body = struct.pack('<7I', header, creator, 0, len(constants), header, 0, target)
    for (name, rset, index, count), at in zip(constants, names):
        body += struct.pack('<IHHHHII', at, rset, index, count, 0, 0, 0)
    body = b'CTAB' + body + strings
    body += b'\0' * (-len(body) % 4)
    return [0xFFFE | ((len(body) // 4) << 16)] + list(struct.unpack('<%dI' % (len(body) // 4), body))


def dcl(usage, index, register):
    return op(31, [0x80000000 | usage | (index << 16), register])


def code(words):
    return struct.pack('<%dI' % len(words), *words)


def floats(*values):
    return list(struct.unpack('<4I', struct.pack('<4f', *values)))


def vertex_shader():
    """vs_3_0: the vertex colour to color0, UV channel 0 to texcoord0 (z, w zero), the position through."""
    w = [0xFFFE0300]
    w += op(81, [d('c', 5)] + floats(0.00784313772, -1, 1, 0))
    w += dcl(0, 0, d('v', 0)) + dcl(10, 1, d('v', 1)) + dcl(5, 0, d('v', 2))
    w += dcl(10, 0, d('o', 0)) + dcl(5, 0, d('o', 1)) + dcl(5, 1, d('o', 3)) + dcl(0, 0, d('o', 2))
    w += op(1, [d('o', 0), s('v', 1)])                                  # mov o0, v1
    w += op(5, [d('o', 1), s('c', 5, 'zzww'), s('v', 2, 'xyxx')])        # mul o1, c5.zzww, v2.xyxx
    w += op(5, [d('o', 3), s('c', 6), s('v', 0, 'yyyy')])                # o3 = ViewProjection's row times y
    w += op(1, [d('o', 2), s('v', 0)])
    return code([w[0]] + ctab([('ViewProjectionMatrix', 2, 6, 4)]) + w[1:] + [0x0000FFFF])


def pixel_shader(body, constants):
    w = [0xFFFF0300] + ctab(constants)
    w += op(81, [d('c', 1)] + floats(4, 0.5, 1, 0))
    w += dcl(10, 0, d('v', 0, 'x')) + dcl(5, 0, d('v', 1, 'xy')) + dcl(5, 1, d('v', 2, 'xy'))
    w += op(31, [0x80000000 | (2 << 27), d('s', 0)]) + op(31, [0x80000000 | (2 << 27), d('s', 1)])
    return code(w + body + [0x0000FFFF])


COMMON = [('UniformPixelVector_0', 2, 0, 1), ('DiffuseOverrideParameter', 2, 4, 1),
          ('AmbientColorAndSkyFactor', 2, 9, 1), ('PixelTexture2D_0', 3, 0, 1), ('PixelTexture2D_1', 3, 1, 1)]
END = (op(4, [d('r', 2, 'xyz'), s('r', 2), s('c', 4, 'wwww'), s('c', 4)])      # mad r2.xyz, r2, c4.w, c4
       + op(5, [d('oC', 0, 'xyz'), s('r', 2), s('c', 9)])                      # mul oC0.xyz, r2, c9
       + op(1, [d('oC', 0, 'w'), s('c', 1, 'wwww')]))


class Fake:
    """What slice_material asks of a cache: a map's shaders and uniforms, a shader by ID."""

    def __init__(self, ps):
        self.codes = {b'P' * 16: ps, b'V' * 16: vertex_shader()}

    def shader_refs(self, m):
        return {'FLocalVertexFactory': {'TBasePassPixelShaderFNoLightMapPolicyNoSkyLightWithoutTranslucentFOW': b'P' * 16,
                                        'TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy': b'V' * 16}}

    def uniforms(self, m):
        return {'pixelVectors': [shader_cache.Expr('VectorParameter', {'name': 'Tint', 'default': [1, 1, 1, 1]})],
                'pixelScalars': [], 'textures2d': [shader_cache.Expr('TextureParameter', {'name': 'A', 'index': 0}),
                                                   shader_cache.Expr('TextureParameter', {'name': 'B', 'index': 1})],
                'texturesCube': [], 'vertexVectors': [], 'vertexScalars': []}

    def shader(self, sid):
        import sm3
        return sm3.decode(self.codes[sid])


def flat(colour):
    return lambda uv: np.tile(np.asarray(colour, dtype=np.float64), (len(uv), 1))


def run(program, colour=(1, 1, 1, 1), uv0=(0.25, 0.75), uv1=(0.5, 0.5), textures=None, n=1):
    inputs = {'uv0': np.tile(uv0, (n, 1)), 'uv1': np.tile(uv1, (n, 1)), 'color': np.tile(colour, (n, 1)),
              'cameraVector': np.tile([0, 0, 1.0], (n, 1)), 'worldPosition': np.tile([10, 20, -500, 1.0], (n, 1)),
              'worldTangent': np.tile([1.0, 0, 0], (n, 1)), 'worldBinormal': np.tile([0, 1.0, 0], (n, 1)),
              'worldNormal': np.tile([0, 0, 1.0], (n, 1))}
    return shader_eval.run(program, inputs, textures or {}, n=n)


class MadeUp(unittest.TestCase):
    def setUp(self):
        ss._VERTEX.clear()

    def test_lerp_by_vertex_colour(self):
        body = (op(66, [d('r', 0), s('v', 1), s('s', 0)]) + op(66, [d('r', 1), s('v', 1), s('s', 1)])
                + op(18, [d('r', 2, 'xyz'), s('v', 0, 'xxxx'), s('r', 1), s('r', 0)])   # lrp by vertex red
                + op(5, [d('r', 2, 'xyz'), s('r', 2), s('c', 0)]) + END)
        program = ss.slice_material(Fake(pixel_shader(body, COMMON)), None, {'vectors': {'Tint': [1, 0.5, 0.25, 1]}})
        textures = {k: flat((0.2, 0.4, 0.6, 1) if t['parameter'] == 'A' else (1, 0.8, 0.6, 1))
                    for k, t in program['textures'].items()}
        out = run(program, colour=(0.25, 0, 0, 0), textures=textures)['diffuse'][0]
        mix = 0.25 * np.array([1, 0.8, 0.6]) + 0.75 * np.array([0.2, 0.4, 0.6])
        np.testing.assert_allclose(out, mix * [1, 0.5, 0.25], rtol=1e-6)
        kinds = {src_['kind'] for srcs in program['inputs'].values() for src_ in srcs if src_}
        self.assertEqual(kinds, {'uv', 'color'})
        tint = next(k for k in program['constants'].values() if k.get('uniform') == 'Tint')
        self.assertEqual(tint['value'], [1, 0.5, 0.25, 1])

    def test_uv_scaled_in_the_pixel_shader(self):
        body = (op(5, [d('r', 0, 'xy'), s('v', 1), s('c', 1, 'xxxx')])                  # uv * 4
                + op(66, [d('r', 2), s('r', 0), s('s', 0)]) + END)
        program = ss.slice_material(Fake(pixel_shader(body, COMMON)), None, {})
        seen = []

        def sample(uv):
            seen.append(uv.copy())
            return np.tile([0.5, 0.5, 0.5, 1], (len(uv), 1))
        run(program, uv0=(0.25, 0.125), textures={k: sample for k in program['textures']})
        np.testing.assert_allclose(seen[0][0], [1.0, 0.5])

    def test_an_input_it_cannot_follow_is_refused(self):
        body = (op(66, [d('r', 2), s('v', 2), s('s', 0)]) + END)          # texcoord1: ViewProjection times y
        with self.assertRaises(ss.Refused) as caught:
            ss.slice_material(Fake(pixel_shader(body, COMMON)), None, {})
        self.assertIn('ViewProjectionMatrix', str(caught.exception))

    def test_folding_drops_a_zero_glow(self):
        body = (op(66, [d('r', 2), s('v', 1), s('s', 0)]) + END)
        program = ss.slice_material(Fake(pixel_shader(body, COMMON)), None, {})
        self.assertNotIn('glow', program['outputs'])            # the colour times a zero light: no glow
        self.assertNotIn('glow', program['refused'])


def particle_vertex_shader():
    """vs_3_0 of a particle factory with a dynamic parameter: the corner's UV (texcoord0), the particle's colour
    (texcoord1) and its dynamic parameter (texcoord3) passed through; the position made from the view-projection
    constants and written both as the position and as texcoord5 (the screen's place)."""
    w = [0xFFFE0300]
    w += dcl(0, 0, d('v', 0)) + dcl(5, 0, d('v', 4)) + dcl(5, 1, d('v', 5)) + dcl(5, 3, d('v', 6))
    w += dcl(5, 0, d('o', 0, 'xy')) + dcl(5, 1, d('o', 1)) + dcl(5, 2, d('o', 2)) + dcl(5, 5, d('o', 3)) + dcl(0, 0, d('o', 4))
    w += op(5, [d('r', 0), s('c', 0), s('v', 0, 'xxxx')])                     # mul r0, c0, v0.x
    w += op(4, [d('r', 0), s('c', 1), s('v', 0, 'yyyy'), s('r', 0)])          # mad r0, c1, v0.y, r0
    w += op(1, [d('o', 0, 'xy'), s('v', 4)]) + op(1, [d('o', 1), s('v', 5)]) + op(1, [d('o', 2), s('v', 6)])
    w += op(1, [d('o', 3), s('r', 0)]) + op(1, [d('o', 4), s('r', 0)])
    return code([w[0]] + ctab([('ViewProjectionMatrix', 2, 0, 4)]) + w[1:] + [0x0000FFFF])


def soft_particle_shader():
    """ps_3_0 of an unlit see-through particle: its texture times its colour, and its opacity faded where the scene
    behind is near (SceneColorTexture's alpha read at a level, MinZ_MaxZRatio, the dynamic parameter's w the fade
    distance), as UE3's soft particles compile."""
    w = [0xFFFF0300] + ctab([('ScreenPositionScaleBias', 2, 1, 1), ('MinZ_MaxZRatio', 2, 2, 1),
                             ('SceneColorTexture', 3, 0, 1), ('PixelTexture2D_0', 3, 1, 1)])
    w += op(81, [d('c', 5)] + floats(-1, 0, 0, 0))
    w += dcl(5, 0, d('v', 0, 'xy')) + dcl(5, 1, d('v', 1)) + dcl(5, 2, d('v', 2)) + dcl(5, 5, d('v', 3))
    w += op(31, [0x80000000 | (2 << 27), d('s', 0)]) + op(31, [0x80000000 | (2 << 27), d('s', 1)])
    w += op(66, [d('r', 1), s('v', 0), s('s', 1)])                             # texld r1, v0, s1
    w += op(5, [d('r', 1, 'xyz'), s('r', 1), s('v', 1)])                       # mul r1.xyz, r1, v1
    w += op(6, [d('r', 0, 'x'), s('v', 3, 'wwww')])                            # rcp r0.x, v3.w
    w += op(5, [d('r', 0, 'xy'), s('r', 0, 'xxxx'), s('v', 3, 'xyxx')])        # mul r0.xy, r0.x, v3.xy
    w += op(4, [d('r', 2, 'xy'), s('r', 0, 'xyxx'), s('c', 1, 'xyxx'), s('c', 1, 'wzzw')])
    w += op(1, [d('r', 2, 'zw'), s('c', 5, 'yyyy')])
    w += op(95, [d('r', 3), s('r', 2), s('s', 0)])                             # texldl r3, r2, s0
    w += op(2, [d('r', 0, 'z'), s('r', 3, 'wwww'), s('c', 2, 'yyyy')])         # depth + ratio.y
    w += op(2, [d('r', 0, 'z'), s('r', 0, 'zzzz'), s('c', 5, 'xxxx')])         # ... - 1
    w += op(6, [d('r', 0, 'z'), s('r', 0, 'zzzz')])
    w += op(4, [d('r', 0, 'z'), s('c', 2, 'xxxx', mod=1), s('r', 0, 'zzzz'), s('v', 3, 'wwww', mod=1)])
    w += op(6, [d('r', 0, 'w'), s('v', 2, 'wwww')])                            # 1 / the fade distance
    w += op(5, [d('r', 0, 'z', sat=True), s('r', 0, 'zzzz'), s('r', 0, 'wwww')])
    w += op(5, [d('r', 0, 'z'), s('r', 0, 'zzzz'), s('v', 1, 'wwww')])
    w += op(1, [d('oC', 0, 'xyz'), s('r', 1)]) + op(1, [d('oC', 0, 'w'), s('r', 0, 'zzzz')])
    return code(w + [0x0000FFFF])


class FakeParticle(Fake):
    FACTORY = 'FParticleDynamicParameterVertexFactory'

    def __init__(self):
        self.codes = {b'P' * 16: soft_particle_shader(), b'V' * 16: particle_vertex_shader()}

    def shader_refs(self, m):
        return {self.FACTORY: {'TBasePassPixelShaderFNoLightMapPolicyNoSkyLightWithTranslucentFOW': b'P' * 16,
                               'TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy': b'V' * 16}}

    def uniforms(self, m):
        return {'pixelVectors': [], 'pixelScalars': [], 'texturesCube': [], 'vertexVectors': [], 'vertexScalars': [],
                'textures2d': [shader_cache.Expr('TextureParameter', {'name': 'Smoke', 'index': 0})]}


class Particles(unittest.TestCase):
    """A particle's material (game-likeness plan, E1): its streams named by its vertex factory, the position's copy
    read as the clip position, the scene's depth as the page gives it, only where the slice is a particle's."""

    def setUp(self):
        ss._VERTEX.clear()

    def test_a_soft_particle(self):
        program = ss.slice_material(FakeParticle(), None, {}, translucent=True, factory=FakeParticle.FACTORY, particle=True)
        self.assertTrue(program['unlit'])
        self.assertEqual(program['shaders']['factory'], FakeParticle.FACTORY)
        kinds = {src['kind'] for srcs in program['inputs'].values() for src in srcs if src}
        self.assertEqual(kinds, {'uv', 'particleColor', 'dynamic', 'clipPosition'})
        engines = sorted(t.get('engine') or t.get('parameter') for t in program['textures'].values())
        self.assertEqual(engines, ['Smoke', 'sceneDepth'])
        self.assertTrue(any(row.get('texld') == 'lod' for row in program['code']))
        ratio = next(c for c in program['constants'].values() if c.get('engine') == 'minZMaxZRatio')
        self.assertEqual(ratio['value'], [-1.0, 1.0, 0.0, 0.0])
        smoke = next(k for k, t in program['textures'].items() if t.get('parameter') == 'Smoke')
        depth = next(k for k, t in program['textures'].items() if t.get('engine'))

        def opacity(behind, colour=(0.5, 0.25, 1, 0.5)):
            inputs = {'uv0': np.array([[0.25, 0.75]]), 'particleColor': np.array([colour]),
                      'dynamic': np.array([[1, 1, 1, 250.0]]), 'clipPosition': np.array([[10, 20, 90, 100.0]])}
            textures = {smoke: flat((0.4, 0.4, 0.4, 1)), depth: flat((0, 0, 0, 1 / behind))}
            return shader_eval.run(program, inputs, textures, engine={'screenPositionScaleBias': [0.5, 0.5, 0.5, 0.5]})
        far = opacity(600)
        np.testing.assert_allclose(far['glow'][0], [0.2, 0.1, 0.4], rtol=1e-6)
        np.testing.assert_allclose(far['opacity'][0], [0.5], rtol=1e-6)        # 500 units clear of the fade: whole
        np.testing.assert_allclose(opacity(150)['opacity'][0], [0.1], rtol=1e-6)    # 50 of 250: a fifth of 0.5

    def test_a_piece_slice_takes_no_screen_input(self):
        # the same shaders read as a mesh's (the local factory's names, no screen inputs): the depth is refused
        class AsPiece(FakeParticle):
            FACTORY = ss.FACTORY
        program = ss.slice_material(AsPiece(), None, {}, translucent=True)
        self.assertNotIn('opacity', program['outputs'])
        self.assertIn('texldl', program['refused']['opacity'])      # (its read at a level, then its engine texture)
        self.assertEqual({src['kind'] for srcs in program['inputs'].values() for src in srcs if src}, {'uv'})

    def test_a_mesh_particles_own_colour_is_an_input(self):
        class MeshParticle(Fake):
            def uniforms(self, m):
                u = super().uniforms(m)
                u['pixelVectors'] = [shader_cache.Expr('VectorParameter', {'name': 'MeshEmitterVertexColor', 'default': [1, 1, 1, 1]})]
                return u
        body = (op(66, [d('r', 2), s('v', 1), s('s', 0)]) + op(5, [d('r', 2, 'xyz'), s('r', 2), s('c', 0)]) + END)
        cache = MeshParticle(pixel_shader(body, COMMON))
        as_particle = ss.slice_material(cache, None, {}, particle=True)
        kinds = {src['kind'] for srcs in as_particle['inputs'].values() for src in srcs if src}
        self.assertIn('particleColor', kinds)
        self.assertFalse(any(c.get('uniform') == 'MeshEmitterVertexColor' for c in as_particle['constants'].values()))
        self.assertNotIn('specular', as_particle['refused'])    # (a particle's slice takes the base pass only)
        ss._VERTEX.clear()
        as_piece = ss.slice_material(cache, None, {})
        self.assertTrue(any(c.get('uniform') == 'MeshEmitterVertexColor' for c in as_piece['constants'].values()))
        inputs = {'uv0': np.array([[0.25, 0.75]]), 'particleColor': np.array([[0.5, 1, 0.25, 1]])}
        out = shader_eval.run(as_particle, inputs, {k: flat((0.5, 0.5, 0.5, 1)) for k in as_particle['textures']})
        np.testing.assert_allclose(out['diffuse'][0], [0.25, 0.5, 0.125], rtol=1e-6)   # the texel times its colour

    def test_streams(self):
        self.assertEqual(ss.stream('FParticleSubUVVertexFactory', 'texcoord', 0, 3), {'kind': 'uv', 'channel': 1, 'component': 1})
        self.assertEqual(ss.stream('FParticleSubUVVertexFactory', 'texcoord', 2, 0), {'kind': 'subImageLerp', 'component': 0})
        self.assertEqual(ss.stream('FParticleVertexFactory', 'texcoord', 1, 2), {'kind': 'particleColor', 'component': 2})
        self.assertEqual(ss.stream(ss.FACTORY, 'texcoord', 1, 0), {'kind': 'uv', 'channel': 1, 'component': 0})
        self.assertEqual(ss.stream(ss.FACTORY, 'color', 1, 3), {'kind': 'color', 'component': 3})
        self.assertIsNone(ss.stream('FParticleVertexFactory', 'texcoord', 3, 0))


@unittest.skipUnless(CACHE and CACHE.exists(), NO_CACHE)
class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = shader_cache.open_cache(CACHE)

    def program(self, base, values=None, switches=None):
        maps = [m for m in self.cache.find_maps(base) if sorted(m.switches) == sorted(switches or [])]
        self.assertTrue(maps, base)
        return ss.slice_material(self.cache, maps[0], values or {}), maps[0]

    def textures(self, program, colours):
        return {k: flat(colours[t.get('parameter')]) for k, t in program['textures'].items()}

    def test_forest_ground_mixes_as_the_game(self):
        program, _ = self.program('172d031942d928ea4848ee82989329c6')
        dirt, grass, leaves = np.array([0.3, 0.3, 0.3, 0.4]), np.array([0.5, 0.35, 0.2, 1]), np.array([0.1, 0.4, 0.1, 0.8])
        normal = (0.5, 0.5, 1, 1)
        colours = {'Dirt': dirt, 'Grass': grass, 'Leaves': leaves, 'Dirt_Normal': normal, 'Leaves_Normal': normal}
        for r, g in ((0.93, 0.89), (0.1, 0.3), (0.5, 1.0)):
            out = run(program, colour=(r, g, 0, 1), textures=self.textures(program, colours))['diffuse'][0]
            a = min(max(2 * r - dirt[3], 0), 1)
            colour = dirt[:3] + a * (grass[:3] - dirt[:3])
            b = min(max(leaves[3] * g, 0), 1)
            colour = colour + b * (leaves[:3] - colour)
            np.testing.assert_allclose(out, colour, rtol=1e-6)
        self.assertEqual({t['parameter'] for t in program['textures'].values()},
                         {'Dirt', 'Grass', 'Leaves', 'Dirt_Normal', 'Leaves_Normal'})     # never Rock
        power = program['outputs']['power']                    # SpcColor_SpcValue's w, kept a uniform
        self.assertEqual(program['constants'][power['r']]['uniform'], 'SpcColor_SpcValue')
        self.assertEqual(program['constants'][power['r']]['value'][3], 16.0)

    def test_one_texture_prop(self):
        program, _ = self.program('acad640d49963317188f94ad316e49b8')
        diffuse_textures = {program['textures'][s_['r']]['parameter'] for row in program['code']
                            if row['d'].startswith('bd') for s_ in row['s'] if s_['r'].startswith('t')}
        self.assertEqual(diffuse_textures, {'Diffuse'})
        colours = {t.get('parameter'): (0.3, 0.6, 0.9, 1) for t in program['textures'].values()}
        out = run(program, textures=self.textures(program, colours))['diffuse'][0]
        np.testing.assert_allclose(out, [0.3, 0.6, 0.9], rtol=1e-6)

    def test_tinted_building_multiplies_its_tint(self):
        values = {'vectors': {'CMod Color': [1, 0.2, 0.1, 1]}}
        program, _ = self.program('5a00b6cc443836f8d993a1bfaec71815', values)
        for alpha, tint in ((0.0, [1, 0.2, 0.1]), (1.0, [1, 1, 1])):
            colours = {t.get('parameter'): (0.5, 0.5, 0.5, alpha) for t in program['textures'].values()}
            out = run(program, textures=self.textures(program, colours))['diffuse'][0]
            np.testing.assert_allclose(out, 0.5 * np.array(tint), rtol=1e-6)

    def test_cut_out_is_the_alpha_against_its_clip_value(self):
        program, _ = self.program('acad640d49963317188f94ad316e49b8')
        self.assertIn('mask', program['outputs'])
        for alpha, kept in ((0.2, False), (0.5, True)):
            colours = {t.get('parameter'): (0.5, 0.5, 0.5, alpha) for t in program['textures'].values()}
            mask = run(program, textures=self.textures(program, colours))['mask'][0]
            self.assertEqual(bool((mask >= 0).all()), kept, (alpha, mask))

    def test_two_uv_channels_each_from_its_own(self):
        program, _ = self.program('210096484b8aa84db07faa8a4e2ba95b')
        channels = {}
        for srcs in program['inputs'].values():
            for s_ in srcs:
                if s_ and s_['kind'] == 'uv':
                    channels.setdefault(s_['channel'], set()).add(s_['component'])
        self.assertEqual(channels, {0: {0, 1}, 1: {0, 1}})

    def test_lightmap_pass_gives_the_same_colour(self):
        program, smap = self.program('172d031942d928ea4848ee82989329c6')
        refs = self.cache.shader_refs(smap)['FLocalVertexFactory']
        ps = ss.pick(refs, ss.LMAP_PS, ss.FOW)
        vs = ss.pick(refs, ss.LMAP_VS, ('',))
        other = {'version': 1, 'shaders': {}, 'ends': {}, 'inputs': {}, 'constants': {}, 'textures': {}, 'code': [],
                 'outputs': {}, 'refused': {}}
        vshader = self.cache.shader(refs[vs])
        part = ss.Part('x', ss.Flow(self.cache.shader(refs[ps])), ss.vertex_outputs(vshader),
                       self.cache.uniforms(smap), {}, other, kinds=ss.numeric_kinds(vshader))
        end, reg, comps, _ = ss.override_end(part.flow, 'DiffuseOverrideParameter')
        other['outputs']['diffuse'] = part.output(end, reg, comps, 'd')
        ss.fold(other)
        rng = np.random.default_rng(3)
        for _ in range(4):
            colours = {name: rng.random(4) for name in ('Dirt', 'Grass', 'Leaves', 'Dirt_Normal', 'Leaves_Normal')}
            colour = tuple(rng.random(4))
            a = run(program, colour=colour, textures=self.textures(program, colours))['diffuse'][0]
            b = run(other, colour=colour, textures=self.textures(other, colours))['diffuse'][0]
            np.testing.assert_allclose(a, b, rtol=1e-6)


class Cases(unittest.TestCase):
    """The case file material_program.js's node test reads: shader_eval gives its numbers, and (with the install)
    the slice still makes its programs."""

    def test_uniforms_that_move_with_time(self):
        # uniform_cases.json: the page works the same trees out each frame (material_program_test.mjs)
        doc = json.loads((HERE / 'uniform_cases.json').read_text(encoding='utf-8'))
        for case in doc['cases']:
            got = ss.evaluate_uniform(ss.expr_from_json(case['expr']), case['values'], case['time'])
            self.assertEqual([round(v, 9) for v in got], case['value'], case['name'])

    def test_eval_gives_the_cases_numbers(self):
        import material_program_cases as cases
        for case in json.loads(cases.FILE.read_text(encoding='utf-8')):
            self.assertEqual(cases.evaluate(case['program'], case['textures'], case['inputs']), case['expected'],
                             case['name'])

    @unittest.skipUnless(CACHE and CACHE.exists(), NO_CACHE)
    def test_the_slice_still_makes_them(self):
        import material_program_cases as cases
        kept = json.loads(cases.FILE.read_text(encoding='utf-8'))
        made = json.loads(json.dumps(cases.make(CACHE)))
        self.assertEqual([c['program'] for c in made], [c['program'] for c in kept],
                         'the slice changed: python -B tools/viewer/tests/material_program_cases.py --write')


if __name__ == '__main__':
    unittest.main()
