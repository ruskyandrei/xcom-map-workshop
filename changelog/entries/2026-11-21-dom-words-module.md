### The page's small DOM and word helpers in a module of their own (dom_words.js)

Editor refactor, stage P9, third part: the first of the helpers app.js still declared goes to a module that owns it.
Nothing the editor does changes.

- **[dom_words.js](../../tools/viewer/web/dom_words.js)** is new and pure (it imports nothing, keeps no state): `short`
  (a name's last part), `text` (an element of text), `field` (a term and its value in a list), `plural` (a count with
  its noun), `copyText` (a copy to the clipboard, told on its button), `segmented` and `segButton` (a row of buttons
  used like a select), moved verbatim from app.js with `export`; and `sentence` (a sentence's first letter made a
  capital), moved verbatim from [build_queue.js](../../tools/viewer/web/build_queue.js), which imported nothing else of
  the page's words and now imports it from there, as [build_window.js](../../tools/viewer/web/build_window.js),
  [flags_panel.js](../../tools/viewer/web/flags_panel.js) and [lights_wiring.js](../../tools/viewer/web/lights_wiring.js)
  do (follow-up 3.17's "a words module would hold it").
- **[app.js](../../tools/viewer/web/app.js)** imports the seven and gives them to the factories as before. 1,848 lines
  to 1,815; top-level functions 88 to 81.
- [dom_words_test.mjs](../../tools/viewer/tests/dom_words_test.mjs) is new: the words, and the elements made on a
  stand-in document. [ARCHITECTURE.md](../../ARCHITECTURE.md): the module in how the page fits, and its row.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the seven functions the same as app.js's at the commit
before (`export` aside), `sentence` the same as build_queue.js's, app.js's other 81 the same; every name the moved code
reads resolves as before (a script of the stage's, by eslint-scope); `web_names` clean (90 files); the node suite; the
twenty-edit recording (stage P9a's 52 steps on the Bar) the same as on the stage's start commit, all 52 steps.
