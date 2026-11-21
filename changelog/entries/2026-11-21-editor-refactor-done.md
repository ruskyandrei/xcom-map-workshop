### The editor refactor's last stage: the guidance closed, and the numbers against where it started

Editor refactor, stage G1 (the last). The refactor that followed the editor review (findings 22, 23, 51, 52, 54-58,
61) is done on its branch: the page's app.js is split into its areas' modules, the compiler into its edit families,
the Build into its steps, the bake suite's builds shared, the package walkers on one reader. Nothing the editor does
changed but what the stages' own entries name.

- [ARCHITECTURE.md](../../ARCHITECTURE.md) was read whole against the code and put into one voice (its own entry,
  2026-11-21-architecture-one-voice). [README.md](../../README.md) says the structure test holds the import rules and
  lists the sizes, which are guidance (it said "the code's limits"). [AGENTS.md](../../AGENTS.md)'s bullet stays as it
  is. Four bugs the last stage found are in [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-8 to KB-11, their own entry).
- The waiting feature plans (custom geometry improvements, the Size tool, the prefab menus, the sun and time of day)
  were read against the refactored code and placed by `ARCHITECTURE.md`.

The final checks, at the branch's tip before this stage (nothing else running):

- **Every suite passes:** 10 min 48 s, against about 13 min when the refactor started. Viewer 640 tests 139 s (639,
  139 s), editor 371 17 s (369, 8 s), upk 175 106 s (172, 105 s), bake 701 (1 skip) 368 s (694, 523 s), lab 49, release
  15, repo 42, node 34 files. The bake suite's slow classes: NativeCopy 21.6 s (38.4), GroundShapes 17.8 s (47.3),
  BarLights 12.5 s (24.7), FlagsBuilt 7.2 s (14.2), RebuildTemplate 4.6 s (11.3); BarScene, OnTheBar, FreshLight and
  Bar as they were.
- **The ten Builds** ([build_outputs.py](../../tools/editor/tests/build_outputs.py)) against the record made when the
  refactor started: the same but for the three differences its stages made and accepted: the manifest's tools record
  names the split modules; four inputs' made-wall light, from reading the original lightmaps as DXT1 (stage B3); a
  baked Build whose light is unchanged says so (the unchanged-light entry).
- **Two real baked Builds** (a moved floor on the Bar, made ground), each run twice: the same file for file but times.
  Against the code when the refactor started, only the relit lightmaps moved (B3's DXT1 reading), by at most 4/255 on
  the Bar; on made ground by at most 6/255 but for two near-black blocks, up to 29/255 there (274 texels), bisected to
  the same B3 change. Times: the made-ground Build 103 s to 43 s, the Bar's 48 s to 47 s.
- **The release's smoke test** passes (11 steps, a trial build; the installer not run).
- **`browser_smoke.py --all`** passes with Play (ten runs, 70 checks), on the page as it is at the end.
- **Sizes** (guidance): app.js 12,792 lines to 1,294, its top-level functions 812 to 11, its `let`s 112 to 5, its
  `startScene` 303 lines to 73; compiler.py 5,622 to 1,969, the `Compiler` class 116 methods to 45; `native_copy.build`
  544 lines to 169. Over 1,500 lines or 150 a function among what ships: 15, against 16 when it started.

Known gaps: the near-black made-ground blocks' larger move is not looked at in the game (a follow-up); the
follow-ups the stages found outside their own scope wait in a plan of their own.
