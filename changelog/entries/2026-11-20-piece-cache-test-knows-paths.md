### The kept pieces' key test leaves paths.py out of what the images depend on

Since the product's functions reach other folders through `paths.use()` (review finding 54), the relight loads
`tools/paths.py`, and [test_faster_bake.py](../../tools/bake/tests/test_faster_bake.py)'s check that the piece cache's
key covers every module the relight loads failed on it. `paths.py` only puts folders on the import path (and
`test_names.py` keeps which file a name finds from depending on that), so the test leaves it out, as it leaves out the
variant's writer; the key's file list (`relight.TOOL_FILES`) is unchanged.

Found by the full suites run once after the review's second round merged (every other suite passed: viewer 639,
editor 359, upk 172, bake 693 of 694 with the opt-in ring skipped, lab 48, release 14, repo 11, node 31 files).
Checked: the `KeptPieces` class.
