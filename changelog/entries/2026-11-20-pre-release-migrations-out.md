### Three migrations from before the first release taken out

Review finding 63, its last part. Each read a state that only the editor of before 9 November 2026 could leave, and
the first published release (0.3.1) came on 10 November; the local previews 0.1.0 and 0.2.0 were already past the
first two (the ledger: settings in Documents and one file per project, both 8 November), and Install as intro map was
replaced by Play in game before 0.2.0.

- **The intro install** ([installs.py](../../tools/viewer/installs.py)): `INTRO_SLOT(S)`, `intro_slot`, `_ours`,
  `_restore_intro` and `restore_intro` are gone, with the `slot` checks in `pristine_lines`, `maps_text`, `install`
  and `reset`, `intro` in the install's status and in what Undo everything reports, and `introBack` in an install's
  answer and history; [play.py](../../tools/viewer/play.py) no longer calls `restore_intro` before a play. The first
  mission's display names stay, as `FIRST_MISSIONS` (`FIRST_MISSION` is their set, as before).
- **Project folders of the old layout** (`<id>\project.json`; [projects.py](../../tools/viewer/projects.py)
  `_migrate`, with `_free`, which only it used) are no longer moved on each listing.
- **Settings in %APPDATA%** ([settings.py](../../tools/viewer/settings.py) `_move_old_settings`) are no longer moved
  to Documents.

The docs that described them ([README](../../tools/viewer/README.md), [editor-contracts](../../research/editor-contracts.md),
[pack_test.py](../../tools/lab/pack_test.py)'s usage) say so no more. The page still has three lines that show the
removed fields when they are there (play.js, gamemaps.js, app.js); they now never are.

Checked: `test_projects` (the six migration tests taken out with it), `test_play` (the intro test taken out),
`test_manager`, `test_install_recovery`.
