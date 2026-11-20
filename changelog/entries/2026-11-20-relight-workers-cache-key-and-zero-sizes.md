### The relight uses the workers it is allowed, keeps pieces only for the code they came from, and reads a 0 as 0

Review findings 41, 42 and two relight items of 44, all in [relight.py](../../tools/bake/relight.py).

- **Workers (41).** The worker count was cut to the number of pieces before a large piece was cut into bands, and
  bands were made only with more than one worker: an edit that reached one large floor ran on one worker, unbanded,
  and two large floors ran their bands on two. `plan_jobs` now cuts the queue for the workers allowed, then gives it
  no more workers than it has jobs. Measured on URB_Bar's pool-table floor (61,628 texels, 5 bands) with the Build's
  settings: with the pool table taken out, the pieces' stage went from 24.1 s on one worker before the change to
  13.6 s on five after it; with the ceiling spot over it off, from 28.9 s on one worker to 10.6 s on five, and the
  relit images and the map came out byte for byte the same. Not done: preparing a large piece once and handing its
  bands their texels. Each worker that takes a
  band prepares the piece again, but that preparation measured 0.7 to 1.2 s against 4.2 to 6.0 s for one of its bands
  (the bands run side by side), so it would save about a second a large piece for a change to how jobs are handed out.
- **Kept pieces (42).** The piece cache's key hashed six files. It now hashes every module of the tools the relight
  loads (the decode of the original bake, the map's, meshes' and materials' readers among them), but the writer of the
  variant, and the release's version as well, so an upgrade never takes a stale piece as good.
- **A source size of 0 (44).** A light's `lightSourceRadius` or `lightSourceAngle` of 0 was read as the default (100
  units, 3 degrees), so the reach tests grew the edit boxes more than meant; the dominant light's quick shadow-map test
  (angle 0) included. `light_source_radius` and `light_source_angle` take the default only when there is no value.
- **A piece that covers no texel (44)** is left out of the relight ("covers no texel of its lightmap") whatever the
  scene; a direct-only relight of one raised `AttributeError`.
- Checked: [test_faster_bake.py](../../tools/bake/tests/test_faster_bake.py) tests `plan_jobs` (one large floor gets
  its bands and a worker each; two get as many workers as allowed), that every module the relight loads is in the
  key's list and that the key changes with the release, and a 0 source size against the default in `shadow_meets`
  and `texel_reach`; [test_relight.py](../../tools/bake/tests/test_relight.py) relights a piece with no texel and no
  scene. Each failed before its change.
