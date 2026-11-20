### The editor says a floor its holes leave none of at any size

Review finding 32, the editor's part. The mesh server ([generated.py](../../tools/viewer/generated.py)) now asks
`made_split.slab_left` about the whole slab before cutting it into the Build's pieces.

- A slab over 16 tiles is cut into pieces, and a piece its holes cover whole is dropped. One that was all holes
  therefore gave the page no pieces and no reason.
- It now gets "the slab's holes leave none of it", the words the compiler uses when it leaves such a slab out.
- Checked: a new test in [test_generated.py](../../tools/viewer/tests/test_generated.py) covers a 2-tile and a
  20-tile slab; the 20-tile case failed before.
