### A prefab's Test in game failing on a long builds folder goes into the known bug register

The exploratory test of the editor after the refactor (every area of the page used through its real controls on
five maps, projects saved and reopened, quick and full Builds, the queue, the prefab builder) found no change from
the version before the refactor. It found one old bug that gives a wrong result, now
[KNOWN-BUGS.md](../../KNOWN-BUGS.md)'s KB-12: a prefab's Test in game stops with a `FileNotFoundError` on a
`.upk.grow-tmp` file when the builds folder's path is long, since its work folders add about 190 characters and pass
Windows' 260-character limit. Not fixed here.

Checked: reproduced under a deep builds folder and not under a short one, on both the refactored code and the
version before it. Not checked: the exact length at which it starts.
