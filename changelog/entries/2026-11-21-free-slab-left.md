### A free-form slab's holes are judged by its area, not by tile centres

The compiler's "its holes leave none of it" check of a free-form slab tested tile centres, as for the older slabs on
whole tiles; it now tests the cells its footprint's and holes' sides make, so a strip half a unit wide left between two
holes counts, and a slab off the tiles is judged by what is there.

- [made_edits.py](../../tools/editor/made_edits.py) `free_slab_left`, used by `free_generated`.

Checked: [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (a strip between two holes, the strip
covered).
