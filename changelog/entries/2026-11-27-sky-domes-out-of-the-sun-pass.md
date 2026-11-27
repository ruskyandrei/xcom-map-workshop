### The sky domes take no part in a turned sun's shadows

A Build with baking whose sun turned traces the sun's shadows for the whole map (relight.py `--sun-turned`). The
level's sky domes, the map's own and the copies of another map's that a project's sky makes in their place (the
`SkyDome_time<n>` copies), now take no part in it: [relight.py](../../tools/bake/relight.py) leaves them out of
both its scenes as casters, and [sun_bake.py](../../tools/bake/sun_bake.py) out of the whole-map trace
(`whole_map_jobs`), out of the pieces given a shadow map of their own (`irrelevant_pieces`) and out of the scene that
decides which those are (`listed_scene`); `dome_actors` finds them by
[native_copy.py](../../tools/bake/native_copy.py)'s `sky_dome`. A dome stands round the map or turned over under it,
127,000 units across, and some cast shadows: a copy standing round the map would have shaded all of it from the sun.

Checked by the bake suite's [test_sun_bake.py](../../tools/bake/tests/test_sun_bake.py): URB_Bar's two domes found
and left out of the jobs (706 of the map's shadow maps traced, two fewer); a scratch copy of URB_Bar with its bowl
under the map turned upright round it, relit with `--sun-turned`: in a scene of every caster it shades over 99% of the
moon's lit lighting samples, in the sun pass's under 1%, and the written marks stay the map's (within 10 of 222). The
whole bake suite passes on the branch with the sky choice merged. F-197 notes it.

Known gaps: a dome's own shadow map of the sun keeps the field it had (a copy's, its home map's sun's); nothing is
seen in the game yet (EXP-100).
