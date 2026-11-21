### The header's edit summary gives way before the Project and Map buttons

A long edit summary in the header (after a clear: "964 deleted · 116 light edits · landing zones changed · 2
buildings · 9 spawn point edits · not saved") squeezed the Project and Map buttons: at 1024 pixels wide on the Bar both
were 11 pixels wide, and the header was still 62 pixels too wide, so the Help button was pushed out of the window.
Now ([the stylesheet](../../tools/viewer/web/style.css)):

- the Project and Map buttons don't shrink, and the summary chip cuts its words with an ellipsis; the chip carries
  its whole text as its title ([piece_status.js](../../tools/viewer/web/piece_status.js), and the prefab builder's
  saved state in [document_session.js](../../tools/viewer/web/document_session.js));
- in a window up to 1100 pixels wide the two buttons cap their names at 140 pixels (200 before), and up to 800 wide at
  80 pixels, with the brand mark hidden there, so that a long project name, the Mission picker and the edit buttons
  still fit the header.

Measured on a test server with a long project name, before any edit, after one deletion and after a clear, on the Bar
and on the police station (whose Mission picker shows): at 1024 and at 800 pixels wide the header holds everything in
every case, and the buttons keep their widths. In the narrowest case (800 wide, a long name, the Mission picker and
the edit buttons) the Mission picker and the summary are squeezed small.

Checked: the `header` browser check ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) opens a page of its
own 1024 wide and clears the Bar: the summary is cut with an ellipsis and whole in its title, the buttons' widths are
those before the clear, and the header does not overflow. It failed before the change (buttons 11 pixels wide, the
header 62 pixels over, the chip neither cut nor titled). `--only header` passes.
