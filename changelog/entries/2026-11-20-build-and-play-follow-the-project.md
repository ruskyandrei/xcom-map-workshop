### Build and Play follow the open project and the build chosen; a look at the install changes nothing

Review finding 10, the play half of finding 45, and the watch's lock of finding 50.

- **The open project's build status** (finding 10). A copy saved from a project at revision 1 showed the other
  project's "last built: revision 1" and offered to play it, as the check compared revision numbers only.
  - [app.js](../../tools/viewer/web/app.js) keeps the status with the project it was asked for. Save as or Replace
    asks the new project's own. An answer for a project no longer open is dropped.
  - Play last build needs the same project as well as the same revision.
- **The build played is the one chosen** (finding 10). A project's play names it: Play last build sends the
  `buildId` shown, and a play after a build sends that build's `attempt`.
  - [play.py](../../tools/viewer/play.py) checks it against the package's manifest under the package's guard.
  - A package another window or the build queue swapped in since starts nothing, and the refusal says which build
    is there now.
- **`GET /play.json` only looks** (finding 45). It started the watch that puts the game's config back and clears a
  play's files. Now `Player.recover` does that once the server holds its port
  ([viewer.py](../../tools/viewer/viewer.py), one line), and the next play does it first, as before.
- **The watch is started under the player's lock** only (finding 50): `status()` no longer starts one.
- The [viewer README](../../tools/viewer/README.md) says so.
- Checked:
  - [test_play.py](../../tools/viewer/tests/test_play.py): a build swapped in after the one named, by `buildId` and
    by `attempt`, starts nothing and installs nothing; bad requests are refused; the build named plays.
  - The config and saves an earlier server left are put back by `recover`, and `status()` alone leaves them and
    starts no watch. The same for a ledger from before the split.
  - [browser_documents.py](../../tools/viewer/tests/browser_documents.py) `build-binding`: a project whose last
    package is of revision 1, saved as a copy at revision 1, shows no package for the copy.
- Not run in a browser: Play itself (it needs a scratch game folder and a build); the play request's build is
  checked by the unit tests.
