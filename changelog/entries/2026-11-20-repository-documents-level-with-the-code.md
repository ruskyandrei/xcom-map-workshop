### The viewer README, the build contract and the test times are level with the code

Review finding 64, the repository documents' part (the page's help and the docstrings go with their code).

- **[tools/viewer/README.md](../../tools/viewer/README.md):**
  - Test in game's stage is at least 18 levels and up to 30.
  - Its dialog starts with Bake off.
  - The test warns and leaves pieces out as the Build does; only an empty snapshot, no room for the squad or a
    stage that can't be prepared stops it.
  - Groups have no locking.
  - Mission objects' markers come from the Normal view's switch.
  - The `game` setting replaced `lwr`.
  - An outdated map re-exports when it opens.
  - There is no search list.
  - Tests run through `run_tests.py`.
- **[research/editor-contracts.md](../../research/editor-contracts.md):**
  - The map and the test stage hold 256 tiles a side.
  - The pieces of a kind the Build had not made before are described as the code builds them: no `class-untried`
    or `foreign-untried` warning and no "Untried" chip (`foreign-held` warns only for what the game shows).
  - The table's footnote no longer says no edited piece was ever tried in the game.
  - The Effects section no longer says the view edits nothing.
- **Test times:** the [README](../../README.md) and the release skill give the times of the 20 November run: bake
  about 7 minutes, every suite about 11. The update-guide skill gives the guide's length as about 3,000 lines.
- [squads.py](../../tools/viewer/squads.py), [squadrecords.py](../../tools/viewer/squadrecords.py) and
  [gamedata.py](../../tools/viewer/gamedata.py) point at the test squad plan where it is now (`done/`).
- Checked: repo and release suites. Each claim was read in the code: `prefab_stage.stage_levels`,
  `prefab_bounds.MAX_TILES`, `compiler.untried`, `class_untried` and `settings.ALIASES`, and `index.html`'s Bake text.
