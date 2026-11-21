### The Game menu's Installs drawn from a play's answer

After **Play in game**, the Game menu's Installs section (the arrow beside Play) kept the rows it had before the play
until the menu was opened again, which asks the server anew: a project just installed was not named under **In the
game** meanwhile. A play's answer is a whole play status, so now the play draws the Installs and the header's play
items from it as soon as it comes, through the one function that draws them after a status read too
(`drawInstalls` in [build_play.js](../../tools/viewer/web/build_play.js)). This holds for the header's Play (a map
alone, or a project's last build) and for Play in game from a finished build's window.

Checked: the `play` browser check ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) now reads the rows
straight after a play, without opening the menu again. For a map alone (the part `--all`'s play run does) the rows
are drawn anew as the "Starting XCOM" message shows, and the last says nothing of the editor's is in the game; this
failed before the change (the rows were still those drawn before the play). With `--play-project`, the row names the
project's build at once after Play last build and after Play in game from the build window, where the check used to
open the menu and wait for its answer. `--play --only play`, with and without `--play-project`, passes on a test
server with a scratch game folder and `--dry-play`.
