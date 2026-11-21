### Old made walls and their cuts held byte for byte

Before the made walls' free form is built (the custom geometry improvements plan, stage 2), walls of today's numbers
are hashed as they build, so that the free form can be shown to leave them alone: seven walls (the Bar's look whole,
joined, one storey and as a piece of a longer wall; two measured looks of the catalogue, one at its own storeys, one
lowered to one storey, and a piece), each one's written mesh, collision, fragment boxes, lightmap rectangle, counts
and mesh name; and the pieces of a tall wall, a long wall and a large slab as the splitter cuts them.

- [test_frac_wall.py](../../tools/bake/tests/test_frac_wall.py): `OldNumbers`.
- [test_made_split.py](../../tools/bake/tests/test_made_split.py): `OldNumbersTests`.

Checked: the hashes were recorded on the commit the stage starts from and the tests pass there
(`run_tests.py bake -k OldNumbers`).
