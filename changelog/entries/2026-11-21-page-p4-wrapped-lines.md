### Stage P4's new comments and ARCHITECTURE.md lines wrapped at 120 characters

Editor follow-ups, stage P4. Words only: the Factories paragraph of [ARCHITECTURE.md](../../ARCHITECTURE.md) ("The
page") and two comments the stage wrote, in [made_panel.js](../../tools/viewer/web/made_panel.js) (`wallLookName`) and
[library.js](../../tools/viewer/web/library.js) (its `plural`), ran past 120 characters a line; they are wrapped, the
made panel's reworded to fit.

Checked: `web_names` clean and the node suite; `browser_smoke.py --all` passed on the stage's head before this
(10 runs of 10, Play too, 78 checks).
