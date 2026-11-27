"""The SM3 bytecode decoder (sm3.py): a shader made by hand decodes and lists back, bad bytes are refused, and on the
install a fixed sample of the RefShaderCache's shaders lists as Windows' disassembler lists them (skipped without the
install or D3DCompiler_47)."""
from pathlib import Path
import random
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sm3  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

CACHE, NO_CACHE = labpaths.test_file('XCOM_SHADER_CACHE_UPK', labpaths.lwr_cooked('RefShaderCache-PC-D3D-SM3.upk'),
                                     'the RefShaderCache')

TYPES = {'r': 0, 'v': 1, 'c': 2, 'oC': 8, 's': 10}


def reg_bits(kind, index):
    t = TYPES[kind]
    return index | ((t & 7) << 28) | ((t & 0x18) << 8) | 0x80000000


def dest(kind, index, mask='xyzw', sat=False):
    bits = sum(1 << (16 + 'xyzw'.index(c)) for c in mask)
    return reg_bits(kind, index) | bits | (0x100000 if sat else 0)


def src(kind, index, swizzle='xyzw', mod=0):
    sw = sum('xyzw'.index(c) << (16 + 2 * k) for k, c in enumerate(swizzle))
    return reg_bits(kind, index) | sw | (mod << 24)


def op(code, params):
    return [code | (len(params) << 24)] + params


def hand_made():
    """ps_3_0: a texture read through a UV, scaled and biased by two constants, written saturated."""
    words = [0xFFFF0300]
    words += op(31, [0x80000005, dest('v', 0, 'xy')])                     # dcl_texcoord v0.xy
    words += op(31, [0x80000000 | (2 << 27), dest('s', 0)])                # dcl_2d s0
    words += op(81, [dest('c', 1)] + list(struct.unpack('<4I', struct.pack('<4f', 0.5, 1, -0.25, 0))))
    words += op(66, [dest('r', 0), src('v', 0), src('s', 0)])              # texld r0, v0, s0
    words += op(4, [dest('r', 0, 'xyz'), src('r', 0), src('c', 0, 'xxxx'), src('c', 1, 'yzwx', mod=1)])
    words += op(1, [dest('oC', 0, sat=True), src('r', 0)])                 # mov_sat oC0, r0
    words += [0x0000FFFF]
    return struct.pack('<%dI' % len(words), *words)


LISTED = """ps_3_0
dcl_texcoord v0.xy
dcl_2d s0
def c1, 0.5, 1, -0.25, 0
texld r0, v0, s0
mad r0.xyz, r0, c0.x, -c1.yzwx
mov_sat oC0, r0"""


class HandMade(unittest.TestCase):
    def test_decodes(self):
        shader = sm3.decode(hand_made())
        self.assertEqual((shader.kind, shader.major, shader.minor), ('ps', 3, 0))
        ops = [i.op for i in shader.instructions]
        self.assertEqual(ops, ['dcl', 'dcl', 'def', 'texld', 'mad', 'mov'])
        mad = shader.instructions[4]
        self.assertEqual(mad.dest.mask, 'xyz')
        self.assertEqual(mad.srcs[1].swizzle, (0, 0, 0, 0))
        self.assertEqual(mad.srcs[2].mod, 'neg')
        self.assertEqual(shader.literals()[sm3.Register('c', 1)], [0.5, 1, -0.25, 0])
        dcl = shader.instructions[0]
        self.assertEqual((dcl.usage, dcl.usage_index, dcl.dest.mask), ('texcoord', 0, 'xy'))
        self.assertEqual(shader.instructions[1].sampler, '2d')
        self.assertTrue(shader.instructions[5].dest.sat)

    def test_lists_back(self):
        self.assertEqual(sm3.listing(sm3.decode(hand_made())), LISTED)

    @unittest.skipUnless(sm3.oracle(hand_made()) is not None, 'no D3DCompiler_47')
    def test_oracle_agrees(self):
        self.assertEqual(sm3.oracle_lines(sm3.oracle(hand_made())), LISTED.splitlines())

    def test_bad_bytes_refused(self):
        for bad in (b'', b'\0' * 6, struct.pack('<2I', 0x12340300, 0xFFFF),
                    hand_made()[:-4],                                    # no end token
                    struct.pack('<3I', 0xFFFF0300, 4 | (5 << 24), 0)):   # an instruction past the end
            with self.assertRaises(sm3.FormatError):
                sm3.decode(bad)

    def test_numbers_as_the_disassembler_writes_them(self):
        self.assertEqual(sm3.number(1.0), '1')
        self.assertEqual(sm3.number(-0.0), '-0')
        self.assertEqual(sm3.number(struct.unpack('<f', struct.pack('<f', 1e-6))[0]), '9.99999997e-007')
        self.assertEqual(sm3.number(struct.unpack('<f', struct.pack('<f', 0.8))[0]), '0.800000012')


@unittest.skipUnless(CACHE and CACHE.exists(), NO_CACHE)
class Install(unittest.TestCase):
    def test_sample_lists_as_the_disassembler(self):
        import shader_cache
        cache = shader_cache.open_cache(CACHE)
        ids = sorted(cache.shaders)
        if sm3.oracle(cache.shader_code(ids[0])) is None:
            self.skipTest('no D3DCompiler_47')
        sample = random.Random(845).sample(ids, 500)
        for sid in sample:
            code = cache.shader_code(sid)
            mine = sm3.listing(sm3.decode(code)).splitlines()
            self.assertEqual(mine, sm3.oracle_lines(sm3.oracle(code)), shader_cache.guid_text(sid))


if __name__ == '__main__':
    unittest.main()
