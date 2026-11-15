"""Compare a game tree with a SHA-256 manifest written by the lab baseline step.

    python -I tools/lab/verify_tree.py <root> <manifest.sha256>

Manifest lines are "<sha256>  <bytes>  <relative/path>". Prints JSON listing files that are new,
missing or changed relative to the manifest; exit code 1 when anything differs.
"""
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor


def sha256(path):
    d = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            d.update(block)
    return d.hexdigest()


def main(root, manifest_path):
    expected = {}
    with open(manifest_path, encoding='utf-8') as f:
        for line in f:
            digest, size, rel = line.rstrip('\n').split('  ', 2)
            expected[rel] = (digest, int(size))
    actual = {os.path.relpath(os.path.join(dp, n), root).replace(os.sep, '/'): os.path.join(dp, n)
              for dp, _, names in os.walk(root) for n in names}
    common = sorted(set(actual) & set(expected))
    with ThreadPoolExecutor(8) as ex:
        digests = dict(zip(common, ex.map(lambda r: sha256(actual[r]), common)))
    result = {
        'new': sorted(set(actual) - set(expected)),
        'missing': sorted(set(expected) - set(actual)),
        'changed': [r for r in common if digests[r] != expected[r][0]],
        'checked': len(common),
    }
    print(json.dumps(result, indent=1))
    return 1 if result['new'] or result['missing'] or result['changed'] else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
