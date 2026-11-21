### The near-black made blocks' 29/255 measured in light: a preview's scale, no stored texel

Editor follow-ups, stage R1 (item 2.4, decision D2). The refactor's final checks found two made ground blocks of the
made-ground real baked Build whose relit images moved up to 29/255 with the DXT1 reading of the original bakes. The
findings register's [T-50](../../research/findings-register.md) has the measurement; in short:

- The two blocks are made pieces lit from nothing (`--fresh-copy`), whose written lightmaps don't read the original
  bake: built with the reading of today and with the Pillow reading before it, they are byte for byte the same (the
  largest difference 0, against URB_Bar's median lit level of 0.443). The images that moved are the relight's
  previews, which divide by the original's 99th percentile: the donor's cloned near-black bake, read 31% higher by
  the exact decoder.
- Decision D2's rule (a difference under a 255th of the median lit level changes no code) leaves
  [relight.py](../../tools/bake/relight.py)' `apply_change` as it is; the guessed cause (its weight near a zero
  original) does not touch these pieces.
- Where the reading does move the light (pieces of the map relit as a change, at most 0.022 before the encoding and
  as much as each Build's own DXT1 error once stored) is the move the DXT1 reading was accepted with.

Checked: the ground Build run with the Pillow reading in a scratch copy of the tools reproduces the final checks'
moves exactly (181 of 214 previews, largest 29/255, 274 texels over 6/255); each relit component's lightmap decoded
from the two variant maps; an absolute relight of the two blocks in the built map (scratch scripts, not checked in).
No code changed.
