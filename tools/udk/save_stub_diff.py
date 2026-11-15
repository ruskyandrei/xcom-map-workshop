"""
Writes private/unrealscript/XComGame-stubs.diff: our changes to LiQuiD911's XComGame stub classes (iiiLiQuiDiii/UDK on
GitHub), which the authoring UDK compiles against. The stubs are third-party files with no licence, so neither they nor the diff are
committed: private/ is ignored by Git.

  python tools/udk/save_stub_diff.py [--udk <udk>] [--upstream <lab>\\upstream\\iiiLiQuiDiii-UDK\\UDK-2011-09]

--udk defaults to the udk setting, and <lab> is the lab setting (tools/viewer/settings.py).

Run it after changing a stub, before committing. Apply the diff to a fresh upstream checkout with
`git apply --directory=UDK-2011-09/Development/Src/XComGame/classes private/unrealscript/XComGame-stubs.diff` (or by
hand).
"""
import argparse, difflib, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import labpaths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--udk', help='UDK 2011-09 (default: the udk setting)')
ap.add_argument('--upstream', help=r'the upstream checkout (default: <lab>\upstream\iiiLiQuiDiii-UDK\UDK-2011-09)')
a = ap.parse_args()
a.udk = a.udk or str(labpaths.udk())
a.upstream = a.upstream or str(labpaths.lab_root() / 'upstream' / 'iiiLiQuiDiii-UDK' / 'UDK-2011-09')

rel = os.path.join('Development', 'Src', 'XComGame', 'classes')
ours, theirs = os.path.join(a.udk, rel), os.path.join(a.upstream, rel)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   'private', 'unrealscript', 'XComGame-stubs.diff')
os.makedirs(os.path.dirname(out), exist_ok=True)


def lines(p):
    with open(p, 'rb') as f:
        return f.read().decode('latin-1').replace('\r\n', '\n').splitlines(keepends=True)


parts, changed = [], []
for fn in sorted(set(os.listdir(ours)) | set(os.listdir(theirs))):
    if not fn.lower().endswith('.uc'):
        continue
    po, pt = os.path.join(ours, fn), os.path.join(theirs, fn)
    a_ = lines(pt) if os.path.exists(pt) else []
    b_ = lines(po) if os.path.exists(po) else []
    if a_ == b_:
        continue
    d = list(difflib.unified_diff(a_, b_, 'a/' + fn if a_ else '/dev/null', 'b/' + fn if b_ else '/dev/null'))
    for i, s in enumerate(d):
        if not s.endswith('\n'):
            d[i] = s + '\n\\ No newline at end of file\n'
    parts.append(''.join(d)); changed.append(fn)
with open(out, 'w', encoding='latin-1', newline='\n') as f:
    f.write(''.join(parts))
print('%d changed stub(s): %s; wrote %s' % (len(changed), ', '.join(changed) or '-', out))
