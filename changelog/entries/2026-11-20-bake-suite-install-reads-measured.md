### The bake suite's package reads measured: no suite cache in the tests, the decodes are the code's

Editor refactor, stage T4 (the bake suite's time). No code changes: what was measured, what was tried and dropped,
and [ARCHITECTURE.md](../../ARCHITECTURE.md)'s rule for tests naming `fixtures.ModuleBuilds`, the builds several
classes of one module share (stage T2).

- Recorded over a whole bake run in one process (each compressed package read through `decomp.decompress_pkg` with
  its content's hash, each package opened, the test running and the code that asked; 694 tests, 409 s): 269 decodes
  took 148 s. Reading a cooked map decodes it in pure Python (about 0.7 s for the Bar), and the package reader keeps
  the last four decoded (`decomp.MEMO_SIZE`).
  - Packages the run wrote: 161 decodes, 90 s, nearly all the Grower's writer checking each package it writes by
    decoding it again (147, 81 s), the rest `package_edit` (10, 6 s).
  - The install's maps: 108 decodes, 58 s, of 49 maps. The tests' own reads made 64 (33 s), the transplant's donors
    18 (11 s), the equip, the copy tool and the catalogues the rest.
- Tried and dropped: a suite cache of the tests' own reads of the eleven install maps they come back to
  (`fixtures.installed`, 74 reads in 24 files). The tests' opens fell from 142 (37 s) to 63 (24 s), but the decodes
  in all stayed (269 to 262, 149 s both) and the run took 415 s against 411: the tests' reads had kept a map among
  the reader's last four for the next build, which then decoded it itself. A cache in the tests moves the decodes to
  the code under test; it does not save them.
- Replaying the run's reads against a reader keeping more: 8 maps, 238 decodes (129 s); 16, 229 (124 s); any number,
  205 (111 s). Both that and the writer's check (81 s, a fifth of the run) are product code (`tools/upk/decomp.py`,
  `package_grow.py`), left for a decision.
