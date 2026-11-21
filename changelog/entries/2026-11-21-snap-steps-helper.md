### One table of snap steps for the editor

The snap setting's steps (across the floor, up, a turn) are now written once, in a module every path that steps is to
take them from: snap off continuous, fine 24 units and 15°, tile 96 across, 64 up and 90°. The landing zones' gizmo,
the first path built to that table, now takes its steps from it; it moves as it did. The other paths follow in the
next changes (the custom geometry improvements plan, stage 1).

- [snap_steps.js](../../tools/viewer/web/snap_steps.js): `SNAP_STEPS`, `stepsOf`, `stepped`, `steppedMove`.
- [spawns.js](../../tools/viewer/web/spawns.js) loses `ZONE_STEPS` and `snapZoneMove`;
  [zones_wiring.js](../../tools/viewer/web/zones_wiring.js) steps the zone's move with `steppedMove`.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) section 2 gains the module's row.

Checked: node tests [snap_steps_test.mjs](../../tools/viewer/tests/snap_steps_test.mjs) (new) and
[clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) (the zone's step cases, unchanged, now through the
helper).
