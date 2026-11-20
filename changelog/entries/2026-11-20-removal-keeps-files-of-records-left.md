### A map's files stay while its record stays in the game, what a removal leaves stays noted, and a pack's scripts run from PowerShell 7

Review findings 26 and 25.

**Finding 26.** Three removal paths reported a record they could not take out, then deleted its map's files anyway.
That left a live record naming a package that was no longer there, which the game could draw. The paths are a
play's clean-up, Remove from game and a pack's Uninstall. One edited line is enough to cause it: a mod manager or a
hand edit.

- [installs.py](../../tools/viewer/installs.py) `clear_play` and `reset`:
  - **What stays noted.** A record block or campaign entry that no longer stands as written stays noted while any
    live record of its name is in `DefaultMaps.ini`. So do landing-zone lines and drop-in lines it couldn't take
    out, a file changed since it was installed, and a commented-out record of the game's own it couldn't put back.
    `reset` used to empty the ledger of them, after which they counted as the install's own.
  - **The variant's files stay too.** They are the files of that variant's project, from the ledger's `owners`, and
    the answer's `left` says so. Once the records are taken out by hand, so that no record of the name is left, the
    next removal takes the files.
  - **Reading the install's own lines.** While such a block stays noted, its lines that still stand as written are
    not read as the install's own: in `pristine_lines`, and in the checks every install makes against it. So the
    variant is not listed as a game map.
- [pack_scripts.py](../../tools/viewer/pack_scripts.py), the pack's Uninstall:
  - **Classic way.** It keeps a map whose records were edited in the game and its files: the install now notes each
    map's files with its records, and a state from before keeps every file. What it couldn't take out stays in the
    pack's state file for the next Uninstall, instead of the state file being deleted. An install over an earlier
    one with such leftovers stops until they are put right.
  - **Cards way.** A card changed since keeps the pack's maps and caches.
  - **Its counts** say what it took out.
  - **The cards install** said "No file of the game was changed" right after adding lines to
    `DefaultRandomSpawns.ini`. It now says "No other file" when it added them.

**Finding 25.** Started from PowerShell 7, the pack-script tests failed: the child Windows PowerShell inherited 7's
module path and didn't find `Get-FileHash`. A user who runs `Install.cmd` from a PowerShell 7 window hits the same
thing.

- `Install.cmd` and `Uninstall.cmd` now clear `PSModulePath` before starting Windows PowerShell, which then builds its
  own.
- The tests' helper in [test_manager.py](../../tools/viewer/tests/test_manager.py) runs the scripts with that
  environment. A failure's message now names the PowerShell host and version, whether it finds `Get-FileHash`, and
  the module path.

Checked:
- [test_install_recovery.py](../../tools/viewer/tests/test_install_recovery.py)'s `Removal` covers a play's clean-up
  and Remove from game, each with one added record edited before removal. The record and its files stay and stay
  noted, the variant is no map of the install, and after the records are taken out by hand the next removal leaves
  the install byte for byte as before. Landing-zone lines left stay noted.
- [test_pack_scripts.py](../../tools/viewer/tests/test_pack_scripts.py) runs the scripts:
  - the classic Uninstall with one map's record edited (its files stay and the other map's go, the state file
    keeps only what is left, an install over it stops, and the next Uninstall finishes it);
  - a card edited since, which keeps the maps;
  - the cards install message with a drop-in line;
  - Install and Uninstall with PowerShell 7's module path. This test fails with the old `Install.cmd`, and its message
    shows `Get-FileHash: False`.
- One assertion of [test_play.py](../../tools/viewer/tests/test_play.py) pinned the old forgetting: the file changed
  since now stays noted as the project's.
- The viewer suite passes, started from PowerShell 7 and from Git Bash.
