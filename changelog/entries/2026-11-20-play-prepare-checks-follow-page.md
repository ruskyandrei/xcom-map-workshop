### The play and prepare browser checks follow the page as it is

Found by the editor refactor's stage P4 before it moved anything: the `play` check, and the `prepare` check's part
with a project (`--play --play-project <id>`), failed on the page as it was. Neither runs in `--all` without
`--play-install`, so neither had been run since the page changed under them. Only the checks change, not the page.

- **[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) `check_play`:**
  - Play in game on a map alone always opens the play dialog (whether saving is on, and with several missions which
    one). The check waited for it only on a map with several missions, so on the Bar (one mission) it never pressed
    Play. It now answers the dialog whenever it opens. It also checks that the dialog never offers baking and shows
    Enable saving, and hides the mission row for a map of one mission.
  - After a project's build was played, the check read the Game menu's "In the game" row as soon as the menu opened.
    The menu asks the server again as it opens (`refreshInstalls`), so the row could still show the state before the
    play. It now waits for that row's answer, then makes the same assertion.
- **`check_prepare`,** with a project: the build status it stands in for a build that stopped for want of a newer
  export now carries `errorCode: 'export-missing'`, as builds.py's do since the page went by the code (review finding
  55). With only the message, the page rightly offered no Prepare the map.

Checked: on a test server with a scratch game folder (copies of an install's `Default*.ini` files, `XComGame.upk`,
its `XComGame.int` and `XComStrategyGame.int` (which the test squad reads), and `URB_Bar.upk`), run as
`serve --install <scratch game> --dry-play`, with a project saved and quick-built from the page: `play` and `prepare`
with `--play --play-project` pass twice in a row on the page before stage P4 (46 s each, with other work on the
computer). Before this change they failed at the three places above.
