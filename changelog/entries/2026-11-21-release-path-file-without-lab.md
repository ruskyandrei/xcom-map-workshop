### The release's path file no longer names tools/lab

[make_release.py](../../tools/release/make_release.py) listed `tools/lab` among the folders the editor imports from
(`FOLDERS`), so the bundled Python's `._pth` named a folder the release does not hold: nothing shipped imports the lab
since the look measurers' fix (follow-up 3.7). `lab` leaves `FOLDERS` and so the path file. The lab is still searched
(`UNSHIPPED`): a shipped module that imports one of its tools now stops the release with a message naming the module,
the import and the folder, where before the lab tool would have gone into the zip unnoticed but for the release
test's check.

Checked: [test_release.py](../../tools/release/tests/test_release.py) gains two tests, both of which failed before
the change: every folder the path file names holds a shipped module (`lab` held none), and an entry importing
`labpaths` stops `modules()`. The release suite passes (17).
