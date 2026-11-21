### A Build whose files would pass Windows' path limit stops before it starts, saying by how much

Where Windows' long paths are off (the usual), a Build whose files would pass its 260 characters stopped part-way with
a `FileNotFoundError`: a prefab test's at the grown map's temporary file (KB-12), a project's at its package's intro
copy or a preview of the relight under a builds folder of about 130 to 150 characters. Now the Build works out the
deepest files it writes and, past 259 characters (247 for a folder), stops with the error code `path-too-long`, saying
which file, by how many characters, and that the builds folder should be on a path at least that much shorter
(Setup, or the output setting) ([build.py](../../tools/editor/build.py), `check_paths`; decision D4 of the follow-ups
plan). For a project's Build and a prefab test alike:

- **Before the snapshot stage,** once the project's names are read: the compile report, the edited map's temporary
  file (`<map>.upk.grow-tmp`), the staged map's, in a baked Build the relight's previews (`<variant>-<actor>-shadow.png`,
  the actor's name taken at 32 characters, the game's longest being 28), and the package's maps (the variant and the
  copies of the intros its base map's records stream, read from the install) in the work folder and in place.
- **Again in preflight,** with every name the compile adds (a patch, the copies of the streams the edit changes),
  before the costly stages.
- **Not where long paths are on** (`long_paths`: Windows' own answer for this Python, which the Build's tools run on):
  there is no limit to keep to, so nothing is refused.
- **The decoded maps the Build keeps in its work folder** (`<work>/unpacked/<64 characters>.unpacked`, the deepest of
  all) are not counted: one whose name is too long is not kept, and each tool decodes the map again, which is slower
  and stops nothing (decomp.py). The snapshot stage says so in a note instead. Counting them, as the plan's list did,
  would have refused projects' quick Builds that build today, under builds folders of about 110 to 160 characters.

Checked:
- New tests in [test_build.py](../../tools/editor/tests/test_build.py), each failing before: a prefab test under a
  builds folder of 160 characters stops with `path-too-long` before the snapshot stage, nothing run or made, its words
  naming the file and the 9 characters; one of 145 builds, with the note; with long paths on the same Build is not
  refused; a project's Build whose stream copy would pass the limit stops in preflight, after its compile (before,
  it stopped at the package with `FileNotFoundError`).
- Seen in the build window on a test server (8793) with a builds folder of 170 characters: "EXP-88 wall groups didn't
  build", the log's `build failed code: path-too-long` and the refusal's words (21 characters too long).
- The editor suite (375 tests).
