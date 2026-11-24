### Cache everything draws the look picker's and the Add panel's pictures too

A user ran Cache everything and the look picker still said *Drawing…* on most cards: those pictures are drawn by
the page (WebGL), not read by the server, so the server's job never made them.

- Cache everything has a third option, **Every look's and piece's picture** (ticked by default), with its count,
  time and disk estimate: every look's sample for the look picker (each wall and floor or roof look, each ground look
  in its four shapes) and every piece's and effect's picture for the Add panel's All maps, at the list's size and the
  large panel's. The page draws them with the panels' own drawing, so they are the same pictures, and puts them to
  the server under the same keys; a second bar shows them. Ticked with the pieces, they start once the server's job
  has read the pieces. Cancel stops them; Carry on picks up. An effect with nothing to draw keeps its marker, as in
  the panel. ([precache_pictures.js](../../tools/viewer/web/precache_pictures.js),
  [precache.js](../../tools/viewer/web/precache.js), [index.html](../../tools/viewer/web/index.html))
- They go a few donor maps at a time, six read ahead of their painting, painted in the frame loop before the view.
  After each batch, what it loaded into the page's tables (meshes, materials, textures, the pieces' records and
  collision) is taken out and freed unless the view draws it or it is still loading, so the page holds about one
  map's worth at a time. That runs in one go, and only once the Add panel, the look picker and the prefab pictures
  are not drawing a picture of their own (theirs is painted a frame after its piece is read, from those tables:
  `busy()` on each).
- The Add panel and the look picker are told of each picture kept (`markKept`), so they show it from the server
  rather than drawing it again ([library.js](../../tools/viewer/web/library.js) `thumbKeys`, `THUMB_SIZES`;
  [look_picker.js](../../tools/viewer/web/look_picker.js)); the two paints the panel used inline are shared from
  [app.js](../../tools/viewer/web/app.js). `GROUND_SHAPES` is exported from [ground.js](../../tools/viewer/web/ground.js).
- Test hooks `precachePictures` and `pageTables` ([test_api.js](../../tools/viewer/web/test_api.js),
  [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json)); the guide's Cache everything item, All maps
  paragraph and look picker legend say so ([guide.html](../../tools/release/guide/guide.html)); a row in
  [ARCHITECTURE.md](../../ARCHITECTURE.md).

Checked: [precache_pictures_test.mjs](../../tools/viewer/tests/precache_pictures_test.mjs) (what there is to draw,
the batches, the estimate, and the tables let go but for what the view draws); the browser check
`precache-pictures` ([browser_precache.py](../../tools/viewer/tests/browser_precache.py)) on a test server with a
scratch cache: looks and pieces drawn and kept, the page's tables the same size after as before, the counts lower by
as many, Start and Cancel with only the pictures, and the pictures starting after the pieces; the `looks` and
`api-names` checks again. Timed in headless Edge with every piece read: a piece's two pictures 0.03 s, an effect's
0.25 s, a look's sample 0.3 to 0.4 s (the server makes its mesh), the page's heap steady at 100 to 130 MB over 850
items; about 18 minutes for all 23,901 pictures of the game. With the look picker open and drawing, both go on, and
Cancel ends the job in under a second. A contact sheet of the pictures drawn matched the panel's; the few blank ones
are effects with almost nothing alive at their start, which the panel draws blank too.

Known gaps: the page must stay open while the pictures are drawn, and a hidden tab draws nothing until it shows
again; the time estimate is from runs on one computer; an effect that draws nothing is counted as still to draw
the next time.
