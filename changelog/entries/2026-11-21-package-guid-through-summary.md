### A map pack's GUID check reads the package summary through the one reader

[packs.py](../../tools/viewer/packs.py)' `package_guid`, which the map pack export uses to warn of a map file with an
all-zero GUID (LWR skips such a file's lines), copied the summary's field order by hand to find the GUID in the
file's first 4 KB. It now reads the file's first mebibyte (which holds any package's summary) through
[upkinfo.py](../../tools/upk/upkinfo.py)' `summary`, and answers `None` when the summary does not read (an `OSError` or
a `ValueError`) or the file is no package. One change of answer: a file cut short after its GUID but inside the rest of
its summary gave the GUID before and gives `None` now, as a damaged package should.

Checked: new tests in [test_damaged_packages.py](../../tools/viewer/tests/test_damaged_packages.py): a made-up
package's GUID, an all-zero one, a summary cut in its chunk table and inside its GUID, a three-byte file, a text file
and a missing file. The cut in the chunk table failed before (it gave the GUID). The pack export's and the Project
manager's tests pass (six of the manager's pack-script tests skipped: the game was running on the computer).
