### The growing writer's check decodes only the blocks a write made

Editor follow-ups, stage B1 (items 1.1, 1.3 and 1.2). [package_grow.py](../../tools/upk/package_grow.py)'s
`Grower.write` read back every map it wrote through the pure-Python LZO decoder, whole: 147 of the bake suite's 269
package decodes, and over half of a test build. It still reads the written file back from disk and makes every
comparison it made (the logical bytes, the tables, each export's place, no item across a chunk boundary). What changed
is how the file's decoded bytes are had:

- **[decomp.py](../../tools/upk/decomp.py)'s `decompress_written`**, beside `decompress_pkg`, takes the source's
  compressed bytes, summary and decoded image (the Grower holds all three). A block of the written file whose packed
  bytes are those of the source's block at the same logical offset, of the same size, is taken from the source's image
  (the decode of the same bytes); every other block (the blocks an edit re-encoded, the new chunks) is decoded. Each
  chunk is read by `read_chunk` and held against the chunk table as `_decode` reads it (`decode_written`). The image
  is kept in the memo and the work folder under the written file's hash, as the whole decode was, so the next reader
  of the file (the copy tool's own checks, the relight in its own process) decodes nothing.
- **Blocks, not chunks:** the plan named chunks. A chunk that holds an edit keeps its other blocks' packed bytes, so the
  same rule taken block by block decodes 14 blocks of a bar build's 237 instead of whole chunks of eight.
- **`decomp.STATS`** counts these reads as `written` (the relight's timing record shows the key); `decoded` counts
  whole decodes only.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the rule that a writer reads back what it wrote says a read-back may take
  the blocks kept from the source from the source's decode.

Numbers (on this computer with four other stages at work, one of them running the bake suite: clock times are noisy,
CPU times are the measure):

| | before (0012083) | after |
| --- | --- | --- |
| the bake suite, clock (not alone: see above) | 388 s | 305 s |
| whole package decodes in the bake suite, all processes (decoding seconds summed) | 298, 177.8 s | 167, 110.4 s |
| of them in the test process | 269 | 126 (3 of them the new test's own) |
| of them in `Grower.write`'s read-back | 149, 83.7 s CPU | none; 153 reads from the source, 1.9 s CPU (28,079 blocks taken, 1,770 decoded) |
| `Grower.write` in the bake suite (157 calls before, 158 after) | 97.5 s CPU, 0.62 s a call | 15.3 s CPU, 0.10 s a call |
| one test build of the bar (a car's assembly moved, a lamp copied), three runs | 1.12 to 1.19 s CPU | 0.50 to 0.52 s CPU |
| the same build's read-back | 0.67 s | 0.03 s (reading and hashing the file) |

- **1.3, `edit_columns`' scan, is not done:** it costs 0.10 to 0.12 s CPU a build (the bar build above, three runs;
  61 calls in the bake suite, 6.8 s CPU summed), under the plan's 0.25 s a build.
- **1.2, the memo's size:** with this in, a bake run decodes 142 maps whole at `MEMO_SIZE` 8 against 167 at 4 (the
  test process 101 against 126): 12.6 s CPU of decoding saved. A decoded map holds 28.5 MB (the median of the suite's
  decodes; 36 MB the largest), so 4 hold up to about 145 MB and 8 about 290 MB. Under the plan's 15 s, so the default
  stays 4 and the bake fixtures do not change it.
- **The relight's kept pieces:** its piece cache's key takes the hash of `decomp.py` (`relight.TOOL_FILES`), so a
  project's next baked Build after this change relights its kept pieces once.

Tests: [test_package_grow.py](../../tools/upk/tests/test_package_grow.py): with made-up chunks (no game file), only
the blocks a write made or moved are decoded and the image is the whole decode's, and a chunk whose size disagrees
with its table is refused; on URB_Bar, URB_PoliceStation and DLC2_3_Furies (stored uncompressed), the read-back is the
whole decode; a byte changed on disk in a new chunk, a byte changed on disk in a block kept from the source, and a
writer that leaves an edited block as the source had it each fail the check; the written map is decoded zero times
(one `written` read) and kept for the next reader and another process.
[test_native_copy.py](../../tools/bake/tests/test_native_copy.py): the three maps the NativeCopy class writes read back
as a whole decode reads them; a build decodes the bar once (twice before).

Checked: the bake suite (703 tests, 1 skip for the ring of base maps) and the upk suite with the install's maps (181
tests, 3 skips: no private copy of the reference writer in a worktree) pass; over a whole bake run every growing
write's read-back (151; the rest were the same file again, from the memo) was held against a whole decode of the file:
all equal; `build_outputs.py` recorded on 0012083 and on this change: the same, the ten inputs' quick and baked
Builds; the two real baked Builds (moved bar floor, EXP-77's made ground) against the follow-ups' baseline: every game
file (the grown and lit maps, the package's map and texture cache) byte for byte the same; the manifests and readmes
differ by the build's time, stamp and folders only.

Known gaps: `package_edit.write_edited`'s own check (with `verify`, as the relight's writes call it) still decodes the
written file whole: 12 decodes of the bake suite, 7.3 s CPU. It is not in this stage's files.
