### A shadow map's distance field searched once per pair: the same bytes in a twelfth of the time (editor refactor, stage B6)

Every dominant-light shadow map the relight traces (a fresh piece's whole field, the region an edit changes in a
moved piece's) turns its sub-samples' views of the light into a signed distance field in
[shadowmaps.py](../../tools/bake/shadowmaps.py) `signed_distance`. Stage B5 measured that search as nearly all of a
fresh piece's shadow-map time: 100 of the bake suite's GroundShapes' 112 s of shadow CPU and 600 of 619 s in a Build
with made ground, at 35 to 57 ns per (sub-sample, window offset) pair, 16.6 s of it in the two 97 x 97 dilations
that find the sub-samples near the edge. It now gives the same arrays, bit for bit, in about a twelfth of the time,
and a baked Build with made ground takes about 47 s instead of 113:
- **The masks near the edge** are grown by `near`, a maximum filter, which grows the window's box along one axis and
  then the other: the same masks as the dilation by the whole box. `change` grows its region by it too.
- **The search** (`nearest_across`) meets each (lit, shadowed) pair within the window once, from the side with fewer
  sub-samples near the edge, and gives its distance to both ends. Only the pairs on the other side have a distance
  worked out, through one linear index into the padded grid, with the world's three axes as arrays of their own.
- **Equal distances** go as before. The old search took the window's offsets in raster order and kept a strictly
  shorter distance, so of equal distances the first offset in raster order set the step count (the half step taken
  off). The side searched from meets its offsets in that order and keeps a strictly shorter one; the other end of
  each pair meets the reverse offsets in reverse order and keeps one as short, so the last of equal ones, the first in
  raster order, wins. A distance is worked out as numpy's norm works one row out, `sqrt((x * x + y * y) + z * z)`, on
  the difference or its negation (which squares the same), so it is the same number from either end.

Checked:
- **B5's dumped inputs** (all 40 calls of GroundShapes' relight, kept by its probe): every answer the old one's, bit
  for bit; 90.3 s of CPU before, 7.6 s after (B5's benched form, the masks and the gather with each pair met from
  both ends, 20.7 s), one process on a loaded computer.
- **[test_shadowmaps.py](../../tools/bake/tests/test_shadowmaps.py)** keeps the old function as the reference
  (`old_signed_distance`) and gains `SearchAsBefore`: 40 made-up grids (whole units, where many distances are equal;
  stretched texels with a second island beside the first; a bent, noisy surface; coarse steps in height; holes;
  `only` masks; light on uncovered sub-samples), a case of two equal distances with different step counts met from
  either side, and `near` against the dilation by the box. Broken on purpose in a scratch copy (the found end keeping
  only a strictly shorter distance, the searched end keeping an equal one, `only` not widened, the squares summed in
  another order), the search fails these tests.
- **The images:** three real baked Builds (URB_Bar with its east floor `XComLevelActor_302` moved a tile; EXP-77's
  made-ground project; TempleShip with the console `XComDestructibleActor_35` moved a tile) and the GroundShapes and
  BarScene classes, each run on the code before and after with an empty piece cache in a scratch cache: every map,
  texture cache, picture, piece cache array and relight array the same bytes (the piece cache's report strings differ
  in their `albedoSources` key order only, as two runs of the same code do: a known follow-up).
- **The piece cache's key** is unchanged: `TOOL_FILES` does not hold shadowmaps.py, since no piece's lightmap images
  depend on it and the shadow maps are traced in every baked Build, never kept. A project's kept pieces stay kept.
- **The suites:** bake (701 tests, 1 skipped: XCOM_TRANSPLANT_RING; 679 s on the loaded computer), upk (175, 7
  skipped: the install checks and the reference writer), repo; the ten Builds (`build_outputs.py`, which records the
  relight's command and does not run it) the same before and after. No image changes, so no game check.

**Times** (wall clock and the CPU of the whole process tree, two rounds each, the code before and after taking turns;
other agents were working on this 32-thread computer, its load read at 0 to 54% before and after the runs; a first
round, run beside the rewrite's benches, was slower for both and is left out):

| Run | Before: wall, CPU | After: wall, CPU |
| --- | --- | --- |
| URB_Bar, a floor moved a tile | 55.4 and 52.8 s, 652 and 622 s | 51.1 and 52.1 s, 602 and 615 s |
| EXP-77's made ground | 114.3 and 111.8 s, 910 and 881 s (the relight's pieces 87.2 and 85.4 s) | 46.6 and 46.5 s, 348 and 343 s (pieces 20.4 and 20.1 s) |
| TempleShip, a console moved a tile | 16.9 and 16.8 s, 133 and 129 s | 17.0 and 17.2 s, 132 and 133 s |
| GroundShapes (the class alone) | 49.6 and 50.1 s, 212 and 213 s (pieces 39.0 and 39.5 s) | 19.0 and 18.9 s, 130 and 130 s (pieces 8.5 and 8.3 s) |
| BarScene (the class alone) | 53.2 and 53.6 s, 54 and 55 s | 53.4 and 53.6 s, 55 and 55 s |

A moved piece's shadow map searches only the region its edit changes, so the moved floor and the console gain little
(B5 put the floor's search at about 0.6 s); BarScene traces no shadow map.

**Not built: preparing a large piece once** (the plan's section 9, step 3: one preparation shared by the band jobs
that each prepare the whole piece again). B5 measured what it would save: the repeated preparations are 35.6 s of a
moved floor's Build's CPU (5.6%), the k-d tree in each 0.01 to 0.03 s, worth about 2 s of a 54 s Build's wall time and
nothing elsewhere; the step is dropped.

**Left as it is:** a made piece on an outdoor donor carries two moon shadow maps, the donor's cloned one and its own,
and both are traced; which one the game draws is a game check and the user's decision (the refactor's follow-ups).
ARCHITECTURE.md does not describe the distance field, so it is unchanged.
