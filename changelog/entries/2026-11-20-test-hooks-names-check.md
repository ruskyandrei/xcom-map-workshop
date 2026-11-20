### The test hooks' names recorded and checked (api-names), and --all on other ports

Editor refactor, stage 0 (item 0.4). The browser checks drive the page through `window.viewer`. A page module moved
must leave those hooks as they were.

- [api_names.py](../../tools/viewer/tests/api_names.py) reads `window.viewer`'s names in three places, each in a page
  of its own: the Bar (`?map=URB_Bar`), the blank map (`?map=CB2_MP_Blank`) and the prefab builder (`?prefab=new`).
  The pages share one browser context, apart from the run's pages.
- [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json) records them: three sorted lists keyed by
  place (`bar`, `blank`, `builder`). Each holds the same 240 names today, since `startScene` makes the hooks as one
  object wherever the page opens.
- [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py):
  - `--url <test server> --write-api-names` writes the record. It refuses to write if a page had an error, and prints
    what changed.
  - The check `api-names` (in the whole run, so in `--all`) compares the names with the record. It fails naming, by
    place, each name missing or added. A name added or taken out on purpose is written into the record in the same
    commit as the change, and the check's message says how.
  - `--all`'s scratch cache now exports CB2_MP_Blank too.
  - `--all --ports a,b,c,d` gives its test servers other ports than 8795-8798, so that two whole runs from two
    worktrees can run at once. It takes distinct ports of 8790-8799 only, and refuses 8768 (the main server) by name.
    `--ports` without `--all` is refused.
- Checked, on a test server with a scratch cache made by `--all`'s own cache step (the four maps and the library, a
  minute and a half):
  - The record was written (5 s), and `--only api-names` passes against it (8 s).
  - With the record changed (a name taken out of `bar`, a made-up one added to `builder`), the check fails with
    "bar: added groundAt; builder: missing noSuchHook".
  - `--write-api-names` refuses 8768. `--ports` refuses 8768, a repeated port, a port outside 8790-8799, and use
    without `--all`.
  - The node suite passes.
  - `--all` passes with `api-names` in its whole run, in 11 minutes on that cache. Its nine runs ran 70 checks. Play
    was left out, since no scratch game folder was given.
