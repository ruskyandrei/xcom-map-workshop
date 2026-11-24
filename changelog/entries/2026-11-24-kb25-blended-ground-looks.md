### KB-25 recorded: a blended ground look shows one of its textures in the editor

A material that mixes textures by vertex colour, such as ENV_ForestGround's Rocks River Vert Paint, is drawn in the
editor in one texture picked by name (here Rock, which the game's shader never samples), while the game mixes Dirt,
mud and grass by the vertex colours: a made ground in it is rock in the editor and green grass in the game. Recorded
as [KB-25](../../KNOWN-BUGS.md) and [F-167](../../research/findings-register.md), with the mix read from the
material's compiled pixel shader; left as it is until a plan to draw the game's mix is agreed.

Checked: read offline (the material's parameters in COverseer_TheBarrens, its shader map and pixel shader in the
install's RefShaderCache, the made piece's vertex colour as the Build works it out, the four textures and their mix
worked out); the `repo` suite.
