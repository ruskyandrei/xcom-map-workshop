### Effects hidden with their floor, and when saved hidden

Stage E5 of the game-likeness plan: an effect's likeness is drawn where the game draws the effect.

- **With its floor**: an effect a building's upper floor lists (the export's `floors`) is not drawn while the Floor
  picker cuts that floor away, as the game hides what a floor lists; a building's lowest listing decides, as for a
  piece. A moved, copied or added effect is listed as a Build lists it: by each upper floor (index 1 up) one of whose
  boxes holds its place within 2 units (`effects_rules.js` `effectFloors`, `shownOnFloor`; native_effects.floor_lists'
  rule), worked out again only when it has moved.
- **Saved hidden**: an effect saved hidden (`hidden`) is drawn only while it is picked, as one that starts off is: the
  game draws neither until something shows it.
- Where: [effects_rules.js](../../tools/viewer/web/effects_rules.js), [effects_wiring.js](../../tools/viewer/web/effects_wiring.js).
- Checked: [effects_rules_test.mjs](../../tools/viewer/tests/effects_rules_test.mjs) (the listings as saved, moved into
  an upper floor, onto the ground floor, at the box's edge and past it; the Floor picker's floors against one and two
  buildings' listings); the `likeness` browser check on URB_Bar (an effect its first floor lists goes with the Floor
  picker at the ground floor and comes back), `effects`. Track H's likeness (stage e5): all twelve 6.88 to 6.85 (URB_Bar
  5.20 to 5.10: its upper floor's effects no longer drawn with the floor cut away, as in the game's shots).
