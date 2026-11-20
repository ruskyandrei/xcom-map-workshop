### A paste makes its copies through optionsOf

Editor refactor, stage P2: `pasteSnapshot` in [app.js](../../tools/viewer/web/app.js), which every copy and paste,
placing, drawn wall, floor or ground piece, look change and placed prefab goes through, makes `addedObject`'s options
for each copied piece with [piece_records.js](../../tools/viewer/web/piece_records.js)'s `optionsOf`. Its record-like
input is the copy's new names, its pose and its links named anew, and its state is the clip entry's own. Nothing a
paste makes changes.

The options' keys now come in `optionsOf`'s order (names, links, pose, state), where the paste put the pose before the
links. `addedObject` takes its options by name, so the order is not seen anywhere. A paste's lights and effects are
made from the copied root's source, not from a record, so `addedLight` and `addedEffect` are called as before.

Checked: the browser recording of every kind of piece (the first of these entries says what it holds) gives, for the
copy and paste of all of it and for the placed prefab, the same arguments to `addedObject` as on the commit before
(14 of the 20 calls with the options' keys in the new order, the same values), the same roots, and the same records
after. [moved_code.py](../../tools/repo/moved_code.py) over app.js: 810 of its 811 functions are the same, and
`pasteSnapshot` differs. `web_names` is clean.
