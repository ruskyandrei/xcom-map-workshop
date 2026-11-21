### A damaged package is refused, not read on: a damaged map-picture package no longer stops the Project manager's list (KB-9)

The package header reader, [upkinfo.py](../../tools/upk/upkinfo.py), now refuses a damaged or cut-short package with a
`ValueError` that says what it met and where, instead of a `struct.error` at the buffer's end, an `IndexError`, a
recursion that never ends or a name made up as `?N`:

- a string whose length runs past the bytes left (`R.fstr`);
- a count of names, imports, exports, generations, chunks or additional packages that the bytes left can't hold,
  refused before the loop that reads them; a field cut short inside a table names the table and the entry
  ("cut short in export 3 of 3: a field at byte ...");
- a name index out of range in the tables (an import's or export's name);
- an object or class reference out of range, its own or one of its outer chain's, and an outer chain that loops
  (`objname`, now a loop rather than a recursion, and `clsname`);
- a file under eight bytes (`load`).

The two other readers of a name index refuse one out of range too: [kismet_links.py](../../tools/upk/kismet_links.py)'s
`P.name` (it made up `?N`) and [schema.py](../../tools/upk/schema.py)'s closing-None check, where a negative index
wrapped round to a real name. A sweep of the LWR install's 8,183 packages (and the lab copy's 8,233) found no name
index out of range in the tables and none in the 40,290 name values of the 562 packages with Kismet that
`kismet_links` reads, so none is kept; the schema built from either install's script packages is the same as before.

[pictures.py](../../tools/viewer/pictures.py)' `_base_index` then skips a damaged map-picture package through the
catch it has (now `OSError` and `ValueError`, what the readers raise), so the other packages' pictures are listed, a
project's picture state is worked out and the Project manager lists its projects. Before, the `struct.error` or
`IndexError` went through that catch and the listing failed. KB-9 leaves [KNOWN-BUGS.md](../../KNOWN-BUGS.md).

Checked: new tests in [test_bad_input.py](../../tools/upk/tests/test_bad_input.py) (a made-up package from
[upk_fixtures.py](../../tools/upk/tests/upk_fixtures.py) cut at every byte of its header and tables, wild counts, bad
string lengths, names, outers and classes out of range, looping outer chains, the Kismet and schema readers) and in the
new [test_damaged_packages.py](../../tools/viewer/tests/test_damaged_packages.py) (six damaged forms of
`UILibrary_MapImages_SF.upk` beside a good DLC package: the picture index, `base_library`, `pictures.status` and the
Project manager's listing). Eight of the nine new upk tests and both viewer tests failed before the change (each of the
six damaged forms stopped the picture index with a `struct.error` or an `IndexError`). The sweep's hash of every
package's summary and tables is the same before and after; the tables' time is unchanged and a map's paths and classes
take about 1 ms more (some 27,000 names; times noisy, other work ran on the computer). The upk and viewer suites pass.
