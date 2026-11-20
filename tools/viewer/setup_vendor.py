"""One-time download of the pinned MIT-licensed renderer; runtime is offline."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent / "web/vendor/three"
# the one place the pinned version is written (the release's notices read it too)
VERSION, TAG = "0.180.0", "r180"
FILES = {"three.module.js":"build/three.module.js", "three.core.js":"build/three.core.js",
         "addons/controls/OrbitControls.js":"examples/jsm/controls/OrbitControls.js",
         "addons/controls/TransformControls.js":"examples/jsm/controls/TransformControls.js",
         "addons/loaders/GLTFLoader.js":"examples/jsm/loaders/GLTFLoader.js",
         "addons/utils/BufferGeometryUtils.js":"examples/jsm/utils/BufferGeometryUtils.js",
         "addons/utils/SkeletonUtils.js":"examples/jsm/utils/SkeletonUtils.js", "LICENSE":"LICENSE"}
CHECKSUMS = {
    "three.module.js":"c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a",
    "three.core.js":"eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20",
    "addons/controls/OrbitControls.js":"b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c",
    "addons/controls/TransformControls.js":"621fb8894c0f748c2be2a6ff8a6bdd72c18a22b24ddfe21d506514544df5c84e",
    "addons/loaders/GLTFLoader.js":"67ac5551fdafa6e349bd80c8f8e5e39c136d6b2fb1ad647db9abb21dc86f9e4a",
    "addons/utils/BufferGeometryUtils.js":"fda7e946b8e0b5ab39b779206589e7a1079a22eb24efb89d7223e03fdfb1f751",
    "addons/utils/SkeletonUtils.js":"0761b1e003917b215d25dd81439d854b36034b5a57ce84c2cfe3b02428d7b253",
    "LICENSE":"bfe119ea4fd413f5f7ca3fcd63adb0c4a073ed39daa2fe7d3e6b769e21272601",
}


def main():
    # Download and verify everything before writing, so a failed checksum leaves
    # any existing install untouched rather than a mix of old and new files.
    downloads, records = {}, []
    for local, remote in FILES.items():
        url = f"https://raw.githubusercontent.com/mrdoob/three.js/{TAG}/" + remote
        data = urllib.request.urlopen(url,timeout=60).read()
        if hashlib.sha256(data).hexdigest() != CHECKSUMS[local]:
            raise ValueError(f"Checksum mismatch for {local}; no update installed")
        downloads[local] = data
        records.append(dict(file=local,source=url,sha256=CHECKSUMS[local]))
    for local, data in downloads.items():
        path = ROOT / local
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    import json
    (ROOT/"manifest.json").write_text(json.dumps(dict(version=VERSION,files=records),indent=2),encoding="utf-8")
    print(f"Installed three.js {VERSION} locally")


if __name__ == "__main__": main()
