### The Build's imports inside functions stay, with why beside them

The compiler part of the editor refactor asks for no import inside a function in `tools/editor`, and moves one to its
module's top only where the order in which Python loads modules stays the same. [build.py](../../tools/editor/build.py)
has fifteen in nine functions: `inline_map` (`inline_lighting`), `Build._seed` (`seed_map`, `seed_tiles`),
`Build.shell` (`shell`, `package`), `Build.named_base` (`lightmap_writer`, `package`), `Build._name_copy`
(`package_grow`), `Build._picture` (`map_frame`), `Build.own_landing_groups` (`scene_metadata`, `package`),
`Build.landing_moves` (`native_spawns`, `scene_metadata`, `package`) and `Build.stream_tile_boxes` (`stream_copy`).

None moves. `python -X importtime -c "import build"` shows none of the eleven modules loaded when build.py's top has
run, so each would load earlier, in every process that imports the Build (the tests, the record tools, the examples),
and the order changes. Each is the module of one stage, and most Builds never reach some of them: a quick Build has
no relight, a Build without a patch never seeds from a plan, without a map picture never writes one, without moved
landings or a mission's moved objects never reads them. Importing one after build.py adds, measured with other work
running on the computer, from one module (`map_frame`, 2 ms) to 43 (`shell`, about 110 ms; `stream_copy` 35, about
80 ms; `lightmap_writer` 27 and `inline_lighting` 26, about 25 ms each). The bake's modules also need `tools/bake`
on the path, which their functions put there with `paths.use('bake')` and build.py's top does not. None imports
build.py back, so no cycle keeps them where they are. The server no longer imports build.py at all (since
[game_files.py](../../tools/editor/game_files.py)), so its load order is not in question.

A comment at build.py's imports now says so, for whoever wants to move one.

Checked: `moved_code.py` on build.py: every function the same (a comment only). Against the stage's start,
`import build` loads the repository's own modules in the same order, with `game_files` added; of the standard
library, `dataclasses` (the Build's inputs record) is new, and `ast` (the manifest's modules) loads at the top, where
the compiler's imports loaded it later before.
