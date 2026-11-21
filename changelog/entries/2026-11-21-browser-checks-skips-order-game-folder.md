### Browser checks: a check that skips itself whole is listed once, two order dependences gone, the scratch game folder described

Editor refactor, stage P10 (the browser checks), in [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) and
the [viewer README](../../tools/viewer/README.md):

- **A check that skips itself whole is reported as skipped only.** It was listed both as ran and as skipped
  (`previews` on a map whose export has no patch previews, for one). `skip(..., whole=True)` returns `WHOLE` where the
  skip ends a check before it did anything (34 places: a map, export or server the check can't use); the run then
  leaves the check out of `ran`. A check made of several parts on one page (`on_page`) is whole-skipped only when
  every part skipped itself whole (`effects` on a preview, say); a part skipped after others ran stays a part skip.
- **`clear-map` after `typed-pose`** (under `--only`) timed out clicking the Map grid's Done: `typed-pose` leaves its
  piece selected, and the Selected piece panel lies over the grid panel's Done. `clear-map` now starts with nothing
  selected.
- **`header` after `project-menu` and `prepare`** timed out clicking Selected, which is off with nothing selected
  (alone it passed only because the button had not been refreshed yet, so the click framed nothing). `header` now
  picks a piece itself, checks that Selected frames it (the camera's target inside the piece's box), and puts back the
  selection it found.
- **`--play-install`** (and `--play`'s help, the script's docstring and the README's `--play` paragraph) now say what
  the scratch game folder holds: copies of `XEW\XComGame\Config\Default*.ini`, `CookedPCConsole\XComGame.upk` and the
  map's package, `Localization\INT\XCom*.int`, and an empty `XEW\Binaries` (stages P4 and P8b found each the hard way).

Checked on a test server: `--only typed-pose,clear-map` and `--only project-menu,prepare,header` timed out at the base,
and pass five times in a row each; `--only previews,light-grid` lists `light-grid` as ran and `previews` as skipped
only; `browser_smoke.py --all` twice with `--play-install` (see the stage's next entry for the waits).
