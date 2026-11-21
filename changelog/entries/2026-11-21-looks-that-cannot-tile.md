### Looks that draw a part of a larger texture: said in the Texture mapping fold and noted by the compiler

Some looks draw a window of a larger texture (an atlas): the subway car roof's top is the top half of its texture and
its underside the bottom half, a supply ship crate's walls a small corner of theirs. Size, Fit and Count map the whole
texture, so on such a surface they show its other parts. Each catalogued look now says, per surface a mapping takes
(a wall's faces side by side, a slab's top and underside, a ground look's top and sides), whether its texture tiles,
worked out where the catalogue is served from the recipe's planar maps over the donor face's extent; no catalogue was
rewritten and no map read again.

- The rule ([looks.py](../../tools/bake/looks.py) `tiling`, `surfaces`, in each row of `listing` as `surfaces`): along
  each axis the texture tiles where the face's coordinates run over a whole repeat or across a repeat's edge; where
  they stay inside one repeat, it tiles when the surface's two repeats are square (within a tenth: a texture laid by
  the world on a face narrower than its repeat) and is a part of a larger one when they are not (an unwrap fitted to a
  window) or when the coordinate doesn't change. On the checked-in catalogues: 22 wall faces of 17 looks, 8 slab
  surfaces of 6 looks and the tops of 32 of the 193 ground looks. Named atlases it finds: the subway car and engine
  roofs (top and underside), the subway engine's inner wall, the supply crate's walls, the UFO's outer walls (side B),
  the EXALT holo-globe wall, the HQ assault walls, the vault wall's strip, the flat roof corner trims, a cemetery roof's
  constant underside. Named tiling textures it keeps tiling, which the span alone would have called windows: the
  construction kit's core floors (88 across a 192 tile), its facades (168 of 192 up), its joint strips (52 up), the
  low stone walls, the truck stop's skylight walls, the police station's walls, the fishing shack's roof.
- A wall look's side with no face (its outline all trims, which a mapping doesn't take) is `None`: 71 faces of 50
  looks, both sides on 21. The faces' slots per side are listed, for a face of several materials up the wall.
- The fold ([made_mapping.js](../../tools/viewer/web/made_mapping.js) `lookSurface`, `textureNotes`;
  [made_mapping_wiring.js](../../tools/viewer/web/made_mapping_wiring.js); `texNotes` in
  [index.html](../../tools/viewer/web/index.html)): once a surface is mapped, "This look draws a part of a larger
  texture (an atlas) on its top: mapped, the whole texture repeats there, its other parts with it" (a wall's: on this
  face, its other face or both); before any mode, a wall look's side with no face ("the mapping takes this side
  alone", or no faces at all); once mapped, a wall's faces in several materials up it (plan item 5.3: a picture across
  the wall needs a look with one face material). Nothing is disabled.
- Size's first repeat for a catalogued wall look is now its faces' measured repeat (side A's, else side B's;
  `lookRepeat`), as it was for slabs; 192 for a look no catalogue holds, as before.
- The compiler notes a mapped surface its look draws from an atlas (`mapped-atlas`, a note: nothing goes wrong in the
  game; [made_edits.py](../../tools/editor/made_edits.py) through `looks.mapped_windows`).
- [ARCHITECTURE.md](../../ARCHITECTURE.md)'s texture mapping row and [UI-GUIDELINES.md](../../UI-GUIDELINES.md)'s
  texture paragraph say so.

Checked: [test_looks.py](../../tools/bake/tests/test_looks.py) (the rule along each axis, a wall's side with no face
and each slot over its band, the catalogues' named atlases and tiling textures, the mapped windows);
[test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (the subway roof's mapped top noted, the core
floor's not, nothing warned); [made_mapping_test.mjs](../../tools/viewer/tests/made_mapping_test.mjs) (the notes on a
stubbed catalogue, the walls' first repeat); the `texture-mapping` browser check (a roof in the subway look says so
once mapped and not in Original, a wall in the UFO doorway's look says it has no faces), `looks`, `walls` and
`api-names` on a test server; web_names clean.

Known gaps: the rule reads geometry, not the texture's pixels, so it can be wrong both ways: the Road House's walls (7
faces, a texture painted for the wall's height, non-square) are called windows along their height, which is right for
a mapping but not an atlas; a tiling texture whose repeats were laid non-square on a donor narrower than a repeat
would be called a window. A ground look's top has no measured place, so whether it crosses a repeat's edge isn't read
(its span alone), and several ground donors are props whose top is piecewise (no gradient at all: called windows, as
their constant colour is). Looks named by an id (the Bar's) have no catalogue entry and get no note.
