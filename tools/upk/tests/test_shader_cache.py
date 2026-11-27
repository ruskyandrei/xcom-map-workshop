"""The RefShaderCache index (shader_cache.py): a made-up cache of two shaders and one map reads, a damaged one is
refused, and on the install the counts and ENV_ForestGround's maps are as F-168 measured them."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import shader_cache  # noqa: E402
from package import FormatError  # noqa: E402
import test_sm3  # noqa: E402  (its hand-made shader)

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

CACHE, NO_CACHE = test_sm3.CACHE, test_sm3.NO_CACHE

NAMES = ['None', 'ShaderCache', 'TBasePassPixelShaderFNoLightMapPolicySkyLightWithoutTranslucentFOW',
         'TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy', 'FLocalVertexFactory',
         'FMaterialUniformExpressionVectorParameter', 'FMaterialUniformExpressionTextureParameter',
         'FMaterialUniformExpressionFoldedMath', 'FMaterialUniformExpressionTime',
         'FMaterialUniformExpressionConstant', 'SpcColor_SpcValue', 'Diffuse', 'Use_Rock']
N = {n: k for k, n in enumerate(NAMES)}
PS_ID, VS_ID, BASE = bytes(range(16)), bytes(range(16, 32)), bytes(range(100, 116))


def name(n, number=0):
    return struct.pack('<ii', N[n], number)


class Fake:
    """What Cache reads of a package: its bytes, names, exports and class names."""

    def __init__(self, data):
        self.data, self.names = data, NAMES
        self.exports = [dict(off=0, size=len(data))]

    def cls(self, index):
        return 'ShaderCache'


def made_up(code=None, versions=(845, 64)):
    code = code or test_sm3.hand_made()
    out = bytearray(struct.pack('<i', -1) + name('None') + bytes(9) + struct.pack('<i', 2))
    for kind, sid in (('TBasePassPixelShaderFNoLightMapPolicySkyLightWithoutTranslucentFOW', PS_ID),
                      ('TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy', VS_ID)):
        start = len(out)
        record = name(kind) + sid + bytes(20)
        tail = struct.pack('<i', 2) + struct.pack('<2H', 7, 9) + bytes([0, 0]) + struct.pack('<i', len(code)) + code
        out += record + struct.pack('<i', start + len(record) + 4 + len(tail)) + tail
    out += struct.pack('<i', 1)
    key = BASE + struct.pack('<i', 1) + name('Use_Rock') + struct.pack('<ii', 1, 1) + bytes(16)
    key += struct.pack('<iii', 0, 0, 0)
    vector = name('FMaterialUniformExpressionVectorParameter') + name('SpcColor_SpcValue') + struct.pack('<4f', 1, 2, 3, 16)
    folded = (name('FMaterialUniformExpressionFoldedMath') + name('FMaterialUniformExpressionTime')
              + name('FMaterialUniformExpressionConstant') + struct.pack('<4f', 0.5, 0, 0, 0) + b'\x0f' + b'\x02')
    texture = name('FMaterialUniformExpressionTextureParameter') + name('Diffuse') + struct.pack('<i', 0)
    shaders = struct.pack('<i', 2)
    for kind, sid in (('TBasePassPixelShaderFNoLightMapPolicySkyLightWithoutTranslucentFOW', PS_ID),
                      ('TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy', VS_ID)):
        shaders += name(kind) + sid + name(kind)
    body = (struct.pack('<i', 0) + struct.pack('<i', 1) + shaders + name('FLocalVertexFactory') + BASE
            + struct.pack('<i', 5) + b'Mine\0' + key
            + struct.pack('<i', 1) + vector + struct.pack('<i', 1) + folded + struct.pack('<i', 1) + texture
            + struct.pack('<iii', 0, 0, 0) + bytes(8))
    start = len(out) + len(key) + 12
    out += key + struct.pack('<iii', *versions, start + len(body)) + body
    return bytes(out)


class MadeUp(unittest.TestCase):
    def test_reads(self):
        cache = shader_cache.Cache('made-up', Fake(made_up()))
        self.assertEqual(len(cache.shaders), 2)
        self.assertEqual(len(cache.maps), 1)
        m = cache.maps[0]
        self.assertEqual(m.switches, [('Use_Rock', True, True)])
        self.assertEqual(cache.find_maps(BASE, {'Use_Rock': True}), [m])
        self.assertEqual(cache.find_maps(BASE, {'Use_Rock': False}), [])
        self.assertEqual(cache.find_maps(shader_cache.guid_text(BASE)), [m])
        self.assertEqual(cache.name(m), 'Mine')
        refs = cache.shader_refs(m)
        self.assertEqual(set(refs), {'FLocalVertexFactory'})
        self.assertEqual(refs['FLocalVertexFactory']['TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy'], VS_ID)
        u = cache.uniforms(m)
        self.assertEqual(u['pixelVectors'][0].fields, {'name': 'SpcColor_SpcValue', 'default': [1, 2, 3, 16]})
        folded = u['pixelScalars'][0]
        self.assertEqual((folded.kind, folded.fields['op'], [a.kind for a in folded.args]),
                         ('FoldedMath', 'mul', ['Time', 'Constant']))
        self.assertEqual(u['textures2d'][0].fields, {'name': 'Diffuse', 'index': 0})
        self.assertEqual(cache.shader(PS_ID).kind, 'ps')
        self.assertEqual(cache.shader_code(VS_ID), test_sm3.hand_made())

    def test_damaged_refused(self):
        with self.assertRaises(FormatError):
            shader_cache.Cache('bad', Fake(made_up(versions=(845, 0))))
        data = bytearray(made_up())
        data[25:29] = struct.pack('<i', 10 ** 8)        # a shader record's next offset past the export
        with self.assertRaises(FormatError):
            shader_cache.Cache('bad', Fake(bytes(data)))

    def test_unknown_expression_spoils_that_map_only(self):
        data = made_up().replace(name('FMaterialUniformExpressionTime'), name('Diffuse'))
        cache = shader_cache.Cache('made-up', Fake(data))
        self.assertEqual(cache.name(cache.maps[0]), 'Mine')
        with self.assertRaises(FormatError):
            cache.uniforms(cache.maps[0])


@unittest.skipUnless(CACHE and CACHE.exists(), NO_CACHE)
class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = shader_cache.open_cache(CACHE)

    def test_counts(self):
        self.assertEqual(len(self.cache.shaders), 68841)
        self.assertEqual(len(self.cache.maps), 4801)

    def test_every_map_reads(self):
        for m in self.cache.maps:
            self.cache.uniforms(m)

    def test_forest_ground(self):
        maps = self.cache.find_maps('172d0319' '42d928ea' '4848ee82' '989329c6')
        self.assertEqual(sorted(sorted(s for s in m.switches) for m in maps),
                         [[], [('Rock_DifNrm', False, False)], [('Rock_DifNrm', True, True)]])
        for m in maps:
            self.assertEqual(self.cache.name(m), 'ENV_ForestGround')
            refs = self.cache.shader_refs(m)
            self.assertEqual(len(refs['FLocalVertexFactory']), 35)
        plain = next(m for m in maps if not m.switches)
        u = self.cache.uniforms(plain)
        self.assertEqual([e.fields['name'] for e in u['textures2d']],
                         ['Dirt_Normal', 'Dirt', 'Leaves_Normal', 'Leaves', 'Grass'])
        self.assertEqual([e.fields['name'] for e in u['pixelVectors']], ['SelectionColor', 'SpcColor_SpcValue'])


if __name__ == '__main__':
    unittest.main()
