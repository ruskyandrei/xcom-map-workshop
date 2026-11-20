### Packages the server opens are freed, and the collision cache keeps a bounded number by package

Review finding 19.

- [package.py](../../tools/viewer/package.py): `Package.properties` kept its answers with `@lru_cache` on the method,
  whose key held the package, so no package the server opened was ever freed (on URB_Bar 61 MB after its properties
  were read, still alive after `del`). The answers are now kept in a dictionary on the package itself and go with it.
  The sound cache's limit of 8 packages, and the library's packages opened per request, now free what they let go.
- [collision.py](../../tools/viewer/collision.py): the collision cache is keyed by the package's SHA-256, so a
  re-export of the same file reads nothing again (before, it opened a second copy keyed by the export's folder), keeps
  only the last two decoded packages open and the answers of the last sixteen, and answers a mesh it has from those
  without opening the package. The collision route ([viewer.py](../../tools/viewer/viewer.py)) reads each export's
  scene.json once per size and time for its mesh list and source, not on every request.
- Checked: [test_package_lifetime.py](../../tools/viewer/tests/test_package_lifetime.py) (new) opens a small package
  made by `pack_card`, reads its properties, lets it go and checks with a weak reference that it is freed; checks that
  the collision cache opens a file once for two generations, lets the first package go at a limit of one, gives the same
  answers after, and that the route's scene is read once. The viewer suite passes.
