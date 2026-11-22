### A made piece's mesh making in a module of its own: the wall generator under the guideline size

The part of the wall generator that turns polygons into a mesh, which the slab and ground generators already called
there, moves unchanged into a module of its own: the polygons and their charts, the lightmap rectangle they are
packed into, the vertices with their tangent frames, the triangles, the fragments' records and the kDOP tree.
`frac_wall.py` goes from 1,611 lines to 1,378, under the guideline size; what stays is the wall's own: its looks, the
free form, its cells, faces and collision.

- [made_mesh.py](../../tools/bake/made_mesh.py) (new): `Faces`, `poly_area3`, `pack_rect`, `collinear_corner`,
  `tangent_frame`, `assemble` and the small vector helpers they use (`_packed`, `_sub`, `_cross`, `_dot`, `_norm`).
- [frac_wall.py](../../tools/bake/frac_wall.py) imports what its own code uses of them (`Faces`, `assemble`,
  `poly_area3`, `_dot`, `_norm`); [frac_slab.py](../../tools/bake/frac_slab.py) and
  [ground.py](../../tools/bake/ground.py) call `made_mesh.Faces` and `made_mesh.assemble`.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the copy tool's paragraph names the module, section 2 has its row, and
  section 4 no longer lists `frac_wall.py`.

Checked: `tools/repo/moved_code.py` (the thirteen functions the same; frac_wall.py's other 64 the same; frac_slab.py's
and ground.py's differing by the calls alone), `test_structure.py --sizes`, the bake, editor and repo suites, and the
Builds' outputs (`build_outputs.py`, the eleven inputs) against the commit before: every package file the same, the
manifests' list of the code that made them naming the new module.
