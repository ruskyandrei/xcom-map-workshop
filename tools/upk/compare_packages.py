"""Compare two v845 packages: header fields, export counts by class, imports and named exports.

  python -I tools/upk/compare_packages.py <a.upk> <b.upk>

Read-only. Uses upkinfo's experimental readers (decompresses LZO packages in memory).
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkinfo

FIELDS = ('ver', 'lic', 'engine', 'cooker', 'compflags', 'flags', 'guid', 'namecount', 'expcount', 'impcount')


def read(path):
    data, header = upkinfo.load(path)
    names, imps, exps = upkinfo.tables(data, header)
    classes = collections.Counter(upkinfo.clsname(e['cls'], imps, exps) for e in exps)
    imports = collections.Counter(upkinfo.objname(-(n + 1), imps, exps) for n in range(len(imps)))
    exports = collections.Counter('%s %s' % (upkinfo.clsname(e['cls'], imps, exps), upkinfo.objname(n + 1, imps, exps))
                                  for n, e in enumerate(exps))
    return header, classes, imports, exports


def show_diff(title, a, b):
    keys = sorted(set(a) | set(b))
    rows = [(k, a.get(k, 0), b.get(k, 0)) for k in keys if a.get(k, 0) != b.get(k, 0)]
    print('%s: %d differ' % (title, len(rows)))
    for k, x, y in rows:
        print('  %4d %4d  %s' % (x, y, k))


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    ha, ca, ia, ea = read(a_path)
    hb, cb, ib, eb = read(b_path)
    print('A =', a_path)
    print('B =', b_path)
    for f in FIELDS:
        print('  %-10s %-34s %-34s %s' % (f, ha[f], hb[f], '' if ha[f] == hb[f] else '<- differs'))
    show_diff('export classes (A B)', ca, cb)
    show_diff('imports (A B)', ia, ib)
    show_diff('exports by class and path (A B)', ea, eb)


if __name__ == '__main__':
    main()
