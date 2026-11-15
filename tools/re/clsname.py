"""Map UE3 PrivateStaticClass pointer variables to class names (read-only)."""
import os, sys, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy
p = PE(exe_copy())

def wstr(v):
    o = p.va2off(v)
    if o is None: return None
    s = []
    for i in range(64):
        c = struct.unpack_from('<H', p.b, o + 2*i)[0]
        if c == 0: break
        if not (32 <= c < 127): return None
        s.append(chr(c))
    return ''.join(s) if len(s) >= 2 else None

def gpsc_name(f):
    """Class name pushed in a GetPrivateStaticClass function: push name; push 0; push 0."""
    o = p.va2off(f)
    for i in range(o, o + 0xA0):
        if p.b[i] == 0x68:
            v = struct.unpack_from('<I', p.b, i+1)[0]
            w = wstr(v)
            if w and p.b[i+5:i+7] == bytes([0x6a, 0]):
                return w
    return None

cache = {}
def name_of(P):
    if P in cache: return cache[P]
    pat = b'\xa3' + struct.pack('<I', P)
    for m in re.finditer(re.escape(pat), p.b):
        i = m.start()
        if p.b[i-8] == 0xE8:
            rel = struct.unpack_from('<i', p.b, i-7)[0]
            f = p.off2va(i-8) + 5 + rel
            n = gpsc_name(f)
            if n:
                cache[P] = n; return n
    cache[P] = None
    return None

def annotate(path):
    """Append class names to 'ds:[01Dxxxxx]' references in a dumpbin listing."""
    out = []
    for line in open(path):
        line = line.rstrip('\n')
        for m in re.finditer(r'ds:\[(01D[0-9A-F]{5})h\]', line):
            n = name_of(int(m.group(1), 16))
            if n: line += '    ; ' + n + '::StaticClass'
        out.append(line)
    return '\n'.join(out)

if __name__ == '__main__':
    if sys.argv[1] == '-a':
        print(annotate(sys.argv[2]))
    else:
        for a in sys.argv[1:]:
            print(a, name_of(int(a, 16)))
