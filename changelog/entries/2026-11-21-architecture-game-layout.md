### ARCHITECTURE.md names the game folder's layout helpers and the Build's running line

[ARCHITECTURE.md](../../ARCHITECTURE.md)'s "Where new code goes" gains a row for a folder of the game install: the
helpers of [settings.py](../../tools/viewer/settings.py) (`game_cooked`, `game_config`, `cooked_folders`,
`ew_folder`, `COOKED`), which [test_game_layout.py](../../tools/viewer/tests/test_game_layout.py) holds (follow-ups
item 6.8). Its "One home" rule that code never decides by a message's words names the Build's `running: <label>`
line, which the server reads in place of the echoed command line (item 6.4).

Checked: the repo suite passes.
