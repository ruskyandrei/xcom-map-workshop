### Rules written twice in Python written once; the Prepare prompt goes by a code

Review finding 55, the items the first round left (the council kind went with export 37).

- **The landing zones' offsets.** [audit_clear.py](../../tools/upk/audit_clear.py), the clear survey, takes LWR's
  landing-zone offsets, the six soldier points and an inside zone's step back from the editor's own
  [spawns.py](../../tools/viewer/spawns.py) instead of a copy (its `evac` is spawns' `volume`); the values and their
  order are the same as the copy's.
- **The mission summary.** [installs.py](../../tools/viewer/installs.py) `base_mission` (was `_base_mission`) is the one
  place a base map record's mission is summed up (type, label, group, in rotation, asked for by name, bomb, first
  mission): `rotation_plan` and the project manager's `_missions` ([manager.py](../../tools/viewer/manager.py)) take it
  instead of building the same dictionary themselves.
- **The installer's game kind.** [test_release.py](../../tools/release/tests/test_release.py) pins
  [installer.iss](../../tools/release/installer.iss)' `GameKind` to [settings.py](../../tools/viewer/settings.py): the
  same folder, the lab marker, the config files in the same order (settings tells the same kinds from folders built
  from the installer's list), and labels that are settings' `KINDS` (plain Enemy Within's said "(plain)").
- **The Prepare prompt.** It matched the compiler's error by its words. Now `compiler.ExportMissing` has a code,
  `export-missing`; [build.py](../../tools/editor/build.py)'s `BuildError` carries it and `main` prints it on a
  `build failed code:` line before the reason; [builds.py](../../tools/viewer/builds.py) keeps it as the job's
  `errorCode`; and the build window's prompt ([app.js](../../tools/viewer/web/app.js)) tests that alone.

Checked: the editor and release suites (the new code in
[test_export_choice.py](../../tools/editor/tests/test_export_choice.py), the installer test), `test_builds` (the code
line kept), `test_manager`, `test_play`, `test_install_recovery`, and `test_audit_clear` of the upk suite.

Not done: the other Python twins the finding lists (`collides` three times, the landing tables, the van building
rule, the intro list, the Kismet walk, the level's actor list, setting a pose) are for their modules' next change.
