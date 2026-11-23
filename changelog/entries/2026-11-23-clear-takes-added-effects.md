### Clear map takes the project's added effects too

The user found a clear leaving the reported boat's effects standing. The map's own effects already went (by the
cleared mark: the page's `survivesClear`, the Build's `clear_level`, which took the hive's 71 emitters out), but the
clear took out the project's added pieces and lights and left its added effects, ambient sounds and lens flares: on
the boat, 35 copies of the hive's own steam, fire, fog and goo emitters. A map effect the project had moved survived
too (the cleared mark keeps a moved effect), where a moved piece is deleted.

Now the clear ([clear_map.js](../../tools/viewer/web/clear_map.js) `clearPlan`, `clearMap`, `clearedEffects`) takes the
project's added effects, sounds and flares out as its added pieces, and marks a moved map effect deleted as a moved
piece; the landing's effects and those outside a kept play area stay, as before. Its window counts them by the same
rule ("Removes 446 pieces, 53 lights, 35 effects…" on the boat). One undo step brings everything back.
[app.js](../../tools/viewer/web/app.js) hands the clear the effects' add and remove;
[test_api.js](../../tools/viewer/web/test_api.js)'s `clearPlan` counts them.

Checked: the browser check `clear-map` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) seeds an added
effect and a moved map effect on URB_Bar, clears (the copy gone, the moved one deleted, no effect left in the saved
state) and undoes; `api-names`; by hand on a test server, the boat's clear window and plan; the node suite.
