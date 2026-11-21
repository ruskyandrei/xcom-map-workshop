### The page's counts and names' last parts from dom_words.js only

Editor follow-ups, stage P4, item 3.22. Nothing the editor says changes.

- Nine modules wrote [dom_words.js](../../tools/viewer/web/dom_words.js)' `plural` out word for word and now import it:
  [build_queue.js](../../tools/viewer/web/build_queue.js), [build_window.js](../../tools/viewer/web/build_window.js),
  [effects_rules.js](../../tools/viewer/web/effects_rules.js), [gamemaps.js](../../tools/viewer/web/gamemaps.js),
  [ground.js](../../tools/viewer/web/ground.js), [manager.js](../../tools/viewer/web/manager.js),
  [prefabs.js](../../tools/viewer/web/prefabs.js) (`prefabWords`' own), [squad.js](../../tools/viewer/web/squad.js)
  and [walls.js](../../tools/viewer/web/walls.js). [pieces.js](../../tools/viewer/web/pieces.js) imports its `short`.
- The variants stay, each with a comment saying how it differs: [library.js](../../tools/viewer/web/library.js)' and
  [precache.js](../../tools/viewer/web/precache.js)' `plural` group the count's digits (the browser's way and the
  British way), and the `short` of effects_rules.js, [spawn_rules.js](../../tools/viewer/web/spawn_rules.js) and
  [spawns_view.js](../../tools/viewer/web/spawns_view.js) give '' for a missing path. spawns_view.js' `shortName`, a
  second copy of its own `short`, is gone.
- [one_home_test.mjs](../../tools/viewer/tests/one_home_test.mjs) finds a module's own `plural` or `short` (a function
  declared by that name) and fails unless it is one of those variants. It failed on the modules before this change,
  naming the ten. [ARCHITECTURE.md](../../ARCHITECTURE.md) ("The page", Modules) says so.

Checked: the node suite (36 files) and `web_names` clean; the twenty-edit recording the same as on the stage's start
commit (52 steps, on the stage's scratch test server); browser checks `spawns`, `library`, `effects`, `project-menu`,
`squad` and `header` pass on the Bar.
