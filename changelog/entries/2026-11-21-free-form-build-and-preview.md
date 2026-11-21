### The Build and the editor's server make free-form slabs and ground

With the slab and ground generators' free form merged (their own ledger entry), the Build and the editor's mesh server
now take free-form pieces (the custom geometry improvements plan, stage 2):

- [frac_walls.py](../../tools/bake/frac_walls.py): request versions walls 4, slabs and ground 3 are the free form
  (`FREE_VERSION`); `check_free` resolves the look, checks a mapping (uv_mapping.py) and asks the generator's own
  `check_free`; `local_box` gives a free-form wall's box from its numbers and its ends' reach (a leaning end's inset less
  its lean across the faces). A free-form wall is said to need the wall generator's free form until it lands.
- [generated.py](../../tools/viewer/generated.py): `free_text`, `free_numbers`: a free-form request's numbers, their
  donor look in one spelling, checked by the generator, drawn from the same endpoints (`fracwall`, `fracslab`, `ground`,
  `ground-corners`).

Checked: [test_free_build.py](../../tools/bake/tests/test_free_build.py) (new: the Build's check of the free versions;
a free roof slab off the tiles with a hole across one and a ground block 72 tiles long and 500 high built into URB_Bar
and read back, the block's collision one box); the free slab and block made by the mesh server by hand; the bake
suite's free-form tests.
