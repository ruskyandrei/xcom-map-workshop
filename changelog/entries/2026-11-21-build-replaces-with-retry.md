### A Build no longer fails when another program holds its map a moment

The Build put two maps in place with a bare `os.replace`: the map with the project's picture written into it, and
the map with its lightmaps put inside it ([build.py](../../tools/editor/build.py), `picture` and `lighting_inside`).
On Windows a replace is refused for a moment while another program holds the file (a virus scanner, a search
indexer), so a Build could stop with a `PermissionError` at its last steps, after a finished bake. Both now go through
[atomic_files.py](../../tools/viewer/atomic_files.py)'s `replace`, which tries again through that moment (about a
second, as the server's writers do since KB-10's fix) and raises the last refusal.

Checked: a new Build test in [test_build.py](../../tools/editor/tests/test_build.py) refuses each of the two replaces
twice and sees the Build finish with the picture and the lightmaps in the map and the manifest's hash the map's (it
failed before with the `PermissionError`); the editor suite passes (379 tests).
