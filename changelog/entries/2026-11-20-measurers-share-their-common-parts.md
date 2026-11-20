### The slab and ground catalogues checked against a fresh measure; the measurers share their common parts

Review finding 57, its first step.

- **A fresh measure against the checked-in catalogues.** [test_catalogues.py](../../tools/bake/tests/test_catalogues.py)
  `Fresh` measures three looks of [looks/slabs.json](../../tools/bake/looks/slabs.json) and three of
  [looks/ground.json](../../tools/bake/looks/ground.json), spread over each file, on their donors in the configured
  install, and compares each recipe, the facts the measure gives, the warnings and the twin verdict with the
  file's entry (as the walls' catalogue already is in test_wall_measure). A measurer changed without its version
  raised now fails a test. The older named looks (slab_looks.json, ground_looks.json) are not compared: they keep
  the recipes they were built with, in an earlier form.
- **What the measurers share** is in [measure_common.py](../../tools/bake/measure_common.py): `rounded` (the slab and
  ground measurers' `_round`, which was copied between them) and `verdict` (a twin check in words; each measurer, and
  the wall catalogue, says a row its own way, so every catalogue's verdicts stay word for word).
  [wall_measure.py](../../tools/bake/wall_measure.py) finds its donor with `find_placing`, as the other two do (a mesh
  named by its path is taken at its first placing at scale 1, else its first; a mesh nothing places still gives its
  own materials and lightmap). The catalogue names every wall by its actor, and by its actor the finder gives all
  344 walls the piece it gave before; named by its mesh (the measurer's command line), 9 of them now take another
  placing of the same mesh, the first at scale 1.

Checked: the catalogue, wall, slab and ground measurer tests, the made walls', slabs' and ground's tests, and the
looks tests; for every wall of the catalogue the old and new finders give the same piece by its actor.

Left, as decisions for a later step: the wall measurer's least-squares face fits, its 0.25-unit level bins and its
own `commonest` stay its own (moving them onto measure_common's planar map and bins changes the walls' numbers, so
it needs the measure's version raised and the catalogue rebuilt); the wall catalogue still opens maps through the
lab's paths, works from its frozen list of walls and takes `build|check` where the other two take
`build [--check]`.
