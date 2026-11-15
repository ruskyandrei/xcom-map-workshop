"""Small read-only PE helper for the XComEW.exe copy: sections, VA<->offset, string search, xref search.

The scripts here read the copy that exe_copy() names: `--exe <path>` on their command line, else
<lab>\\re\\XComEW-copy.exe (the lab setting, tools/lab/labpaths.py). `python pe.py [--exe <path>]` prints it (dis.sh)."""
import os, sys, struct, re


def exe_copy(argv=None):
    """The exe copy to read: the value of `--exe <path>` (taken out of argv, sys.argv by default), else
    <lab>\\re\\XComEW-copy.exe."""
    argv = sys.argv if argv is None else argv
    if '--exe' in argv:
        k = argv.index('--exe')
        if k + 1 >= len(argv):
            raise SystemExit('--exe needs the path of the XComEW.exe copy')
        path = argv[k + 1]
        del argv[k:k + 2]
        return path
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
    import labpaths
    return str(labpaths.lab_root() / 're' / 'XComEW-copy.exe')


class PE:
    def __init__(self, path):
        self.b = open(path, 'rb').read()
        b = self.b
        pe = struct.unpack_from('<I', b, 0x3c)[0]
        nsec = struct.unpack_from('<H', b, pe + 6)[0]
        optsz = struct.unpack_from('<H', b, pe + 20)[0]
        self.base = struct.unpack_from('<I', b, pe + 24 + 28)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 24 + optsz + i * 40
            name = b[o:o+8].rstrip(b'\0').decode()
            vsz, va, rsz, rptr = struct.unpack_from('<IIII', b, o + 8)
            self.secs.append((name, self.base + va, vsz, rptr, rsz))
    def sec(self, name):
        return [s for s in self.secs if s[0] == name][0]
    def off2va(self, off):
        for n, va, vsz, rp, rs in self.secs:
            if rp <= off < rp + rs: return va + off - rp
    def va2off(self, v):
        for n, va, vsz, rp, rs in self.secs:
            if va <= v < va + rs: return rp + v - va
    def u32(self, v): return struct.unpack_from('<I', self.b, self.va2off(v))[0]
    def find_str(self, s, wide=False):
        pat = (s.encode('utf-16-le') + b'\0\0') if wide else (s.encode() + b'\0')
        return [self.off2va(m.start()) for m in re.finditer(re.escape(pat), self.b)]
    def xrefs(self, target, secname=None):
        """All places whose 4 bytes equal target (absolute refs: push imm32, mov reg/mem imm32, data pointers)."""
        pat = struct.pack('<I', target)
        out = []
        for m in re.finditer(re.escape(pat), self.b):
            v = self.off2va(m.start())
            if v is None: continue
            n = [s[0] for s in self.secs if s[1] <= v < s[1] + s[4]][0]
            if secname is None or n == secname: out.append((n, v))
        return out
    def calls_to(self, target):
        """E8 rel32 calls and E9 jmps into target, from .text."""
        n, va, vsz, rp, rs = self.sec('.text')
        t = self.b[rp:rp+rs]
        out = []
        for m in re.finditer(b'[\xe8\xe9]', t):
            i = m.start()
            if i + 5 > len(t): break
            rel = struct.unpack_from('<i', t, i + 1)[0]
            if va + i + 5 + rel == target: out.append(va + i)
        return out

def func_start(p, va, maxback=0x4000):
    """Start of the function holding va: just after the nearest run of int3/nop padding before it."""
    o = p.va2off(va)
    for i in range(o, o - maxback, -1):
        if p.b[i-1] in (0xCC, 0x90) and p.b[i-2] in (0xCC, 0x90) and p.b[i] not in (0xCC, 0x90):
            return p.off2va(i)
    return None

def func_end(p, va, maxfwd=0x8000):
    o = p.va2off(va)
    for i in range(o, o + maxfwd):
        if p.b[i] in (0xC3, 0xC2) and p.b[i+1] == 0xCC if p.b[i] == 0xC3 else (p.b[i] == 0xC2 and p.b[i+3] == 0xCC):
            return p.off2va(i + (1 if p.b[i] == 0xC3 else 3))
    return None


if __name__ == '__main__':
    print(exe_copy())
