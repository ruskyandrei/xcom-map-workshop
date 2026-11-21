### A save no longer fails while another program holds the file a moment: one writer for every file the server replaces whole (KB-10)

A new module, [atomic_files.py](../../tools/viewer/atomic_files.py), is the one writer of a file the editor replaces
whole. `write_bytes` and `write_text` write a temporary file beside the file and put it in its place with `replace`,
which tries `os.replace` again while Windows refuses it with a `PermissionError` (another program holding the file a
moment: a virus scanner, a backup or search indexer), 50 tries 0.02 s apart as the install's records always did, and
then raises the last refusal. A write that fails removes its temporary file and leaves the file as it was.

Every writer of `tools/viewer` goes through it now, each keeping its own lock, flush to the disk, read-back,
temporary file's name where something looks for it, and error words: a project and its drafts and its revision before
([projects.py](../../tools/viewer/projects.py)), a prefab's picture and a deleted prefab moved aside
([prefabs.py](../../tools/viewer/prefabs.py)), a map picture and the one before it
([pictures.py](../../tools/viewer/pictures.py)), a build's snapshot, its writer record and a report's zip
([builds.py](../../tools/viewer/builds.py)), the publication journal
([publication.py](../../tools/viewer/publication.py)), the build queue, its last good copy and a queue set aside
([buildqueue.py](../../tools/viewer/buildqueue.py)), the package digests
([catalogue.py](../../tools/viewer/catalogue.py)), the library's index, its pieces', effects' and area lights'
records, the favourites and the thumbnails ([library.py](../../tools/viewer/library.py)), the test squad and its
backup ([squads.py](../../tools/viewer/squads.py)), a play's saves put back and moved
([playsaves.py](../../tools/viewer/playsaves.py)), a pack's record and zip ([packs.py](../../tools/viewer/packs.py),
[manager.py](../../tools/viewer/manager.py)), the settings ([settings.py](../../tools/viewer/settings.py)), and the
install's ledgers, config files, package files and their roll-backs ([installs.py](../../tools/viewer/installs.py),
[mapsini.py](../../tools/viewer/mapsini.py), whose retries were the model and are now the module's).
`installs.replace_bytes` and `installs._put_bytes`, the same function twice, are one (the temporary file named for the
prefab test, or for the change under way).

What a user sees: a save, a picture, a build's record or an install that met a file held a moment now waits up to
about a second for it instead of stopping with "could not be written". A writer that left its temporary file behind
when it failed (a build's snapshot, the publication journal, a build's writer record, the install's ledger) now
removes it. Every file is written with the same bytes and names as before.

Left as they were: the folder moves of the export's publish ([export.py](../../tools/viewer/export.py)) and of a
package's swap ([publication.py](../../tools/viewer/publication.py)), which rely on `Path.rename` refusing a folder
that is there; and `write()` in [prefab_tests.py](../../tools/viewer/prefab_tests.py) (a prefab test's records), the
Build track's file, which still replaces once. The scan lists the three with their reasons.

Checked: the new [test_atomic_files.py](../../tools/viewer/tests/test_atomic_files.py) tries `replace` through two
refusals, through the last (raised, the file moved left where it was) and with another error (raised at once), and
`write_bytes` and `write_text` failing (no temporary file left); runs 18 writers (a project saved twice, a picture
saved twice, a build's snapshot, a prefab saved, pictured and deleted, a publication, the build queue, the package
digests, the library's index, area lights, favourites and a thumbnail, the settings, the squad saved twice, a pack, a
play's saves, the install's ledger, an install's change, its config files) with every replace refused twice, each
written in full with no temporary file left; and scans `tools/viewer/*.py` for `os.replace`, `os.rename` and a path's
`replace` or `rename`. Before the writers moved, 17 of the 18 writers failed (only the install's ledger tried again)
and the scan named 14 modules. [test_playsaves.py](../../tools/viewer/tests/test_playsaves.py) counts the moves at
`os.replace` itself, as `playsaves` no longer imports `os`. The viewer (662 tests; the 10 game-script tests skipped
while a lab copy of XCOM ran), editor (377), lab (49), release (17) and repo (44) suites pass, and the browser checks
of projects and prefabs pass on a test server with a scratch cache (whose library scan wrote its index through the
new writer). [build_outputs.py](../../tools/editor/tests/build_outputs.py)'s records before and after are the same (11
inputs, quick and baked Builds). KB-10 leaves [KNOWN-BUGS.md](../../KNOWN-BUGS.md).
