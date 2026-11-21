### The editor follow-ups done: the final checks against where they started

The follow-ups the editor refactor's stages found outside their own scope (71 items) were judged and planned, and
the ones worth doing built, on branch `editor-followups` after the refactor: fifteen stages and a closing one, each
with its own entries. Five items wait for later and two were dropped; the rest were built, a few in part.

- Five known bugs are fixed and gone from [KNOWN-BUGS.md](../../KNOWN-BUGS.md): the Map grid's panel under the
  right-hand panels (KB-8), the package header read without bounds (KB-9), writers without the retry (KB-10), the
  DefaultMaps record read three ways (KB-11), a prefab's Test in game on a long builds folder (KB-12). One found and
  left: the police station's own landing read as moved (KB-13, its own entry).
- What a Build writes changed in one place: a made piece on an outdoor donor lists one moon shadow map, its own, and
  no longer the donor's clone beside it (seen in the game: EXP-89, F-144). A made-ground Build's map is 12.9 MB
  smaller for it.

The final checks, at the branch's tip:

- **Every suite passes**, the game closed: viewer 673 tests (no skips), editor 380, upk 190, bake 714 (1 skip), lab
  49, release 17, repo 44, node 36 files. The bake suite alone took 512 s with another game running on the computer
  (every module about 1.5 times its time at the follow-ups' first merge point, 325 s).
- **The eleven Builds** ([build_outputs.py](../../tools/editor/tests/build_outputs.py)) against the record made when
  the follow-ups started: the same but for the manifest's tools list (now from the Build's own imports), the new
  `bar-grid` input, and the two inputs with made pieces on outdoor donors (one shadow map).
- **Two real baked Builds** (a moved floor on the Bar, made ground), each run twice: the same file for file but times
  and dates. Against the start: the Bar's map byte for byte the same; the made-ground map 12.9 MB smaller (the cloned
  shadow maps gone). The made-ground Build took 40 s (43 s at the start).
- **The release's smoke test** passes (11 steps, a trial build; the installer not run).
- **`browser_smoke.py --all`** passes with Play: ten runs, 78 checks. A first run, on a cache copied from a stage's
  folder and given by a relative path, failed the `prefabs` check (its Build found no scanned library); the second,
  on `--all`'s own cache, passed every run.
- **Sizes** (guidance): app.js 1,294 lines to 1,268, 5 `let`s and 11 top-level functions as before; 9 files over 1,500
  lines and 8 shipped functions over 150.

Known gaps: the follow-ups' own notes on what they saw outside their scope, and the five items left for later, wait in
a short list of their own.
