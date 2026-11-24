### F-168 extended: the shader cache's layout, the game's light and grade formulas, decals' stored triangles

More read for the plan to draw the editor's view as the game shows it, added to F-168 in the
[findings register](../../research/findings-register.md): how the RefShaderCache is laid out (68,841 shaders and
4,801 material shader maps, both walked by their skip offsets), how a compiled shader names its inputs and why a
texture coordinate's number is not the mesh's UV channel, the forms the colour's mark takes, the game's lightmap and
colour-grade formulas as its shaders compute them, the fog and post-process structures, the triangles a cooked decal
keeps, that a baked Build's own pieces carry lightmaps, and what the page costs today. No tool changed.

Checked: read offline (scratch scripts over the install's two shader caches, CSmallScout_DirtRoad's and URB_Bar's
packages, two baked Builds; the page timed with perf_probe.py and by hand); a second reading by a review agent that
walked every shader; the `repo` suite.
