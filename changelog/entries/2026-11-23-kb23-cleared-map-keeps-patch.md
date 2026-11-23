### KB-23 recorded: a cleared map still gets its Long War patch level's lights, rework and script

- **Found by reading, nothing changed in the tools.** Asked whether a cleared map still gets the old map's patches:
  it does, in part. A cleared project's build streams its own copy of the map's patch level with the patch's pieces
  out ([mission_edits.py](../../tools/editor/mission_edits.py) names the export's `objects`,
  [stream_copy.py](../../tools/bake/stream_copy.py) empties their slots), and the patch's point lights, rebuild
  volumes and Kismet script stay in the copy. The script runs when the level loads and matches pieces by archetype,
  class and place, so it acts on the new map's pieces too. Recorded as [KB-23](../../KNOWN-BUGS.md).
- **What Long War's patch levels hold** is in the findings register,
  [F-163](../../research/findings-register.md): of the 90, 85 have rebuild volumes and 80 a script that changes the
  base map's own pieces as it loads (removes, resizes, hides, sets cover, rewrites destruction);
  `patch_hide_randomized_objects` decides per mission. So a patch can't be folded into a built map in general.
- **Checked**: every `patch_*.upk` of an LWR install tallied by class; `patch_farm`'s and
  `patch_hide_randomized_objects`' scripts read with [kismet_links.py](../../tools/upk/kismet_links.py); the farm's
  export 40 lists six pieces and 13 lights for `patch_farm`. The `repo` suite.
- **Not checked**: nothing was played; what a cleared farm shows of this in the game is not seen.
