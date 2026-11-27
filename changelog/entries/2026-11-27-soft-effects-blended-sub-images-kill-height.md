### Soft effects against the map, blended sub-images, kill heights and world-space particles

Stage E3 of the game-likeness plan, on the likenesses drawn by their programs (E1).

- **Soft edges (the Game look)**: a soft particle's material reads the depth behind it and fades where a wall or the
  ground is near (UE3's depth-faded opacity, sliced in E1). The Game look's frame (`post_chain.js`) now draws the
  effects' likenesses in a pass of their own after the map's pieces, into the same target, and hands them the pieces'
  resolved depth (`soft`; `effects_preview.js` `setSceneDepth`, the `progSceneDepth` the programs read: 1 / the
  distance). Three invalidates the multisampled colour once it has resolved it, so the pass first draws the resolved
  colour back (a quad under the likenesses, in the same draw); the depth it keeps. The Neutral look and the Add panel's
  pictures have no depth: nothing is behind, so nothing fades there.
- **Sub-images blended**: an emitter that blends its sub-images (PSUVIM_Linear_Blend) gives its program the next
  sub-image's UVs and the index's fraction as the blend, as the game's SubUV factory does; the others the one image.
- **KillHeight** (`effects_sim.js`): a particle past the height dies, under it where it is a floor, else over it; an
  absolute height is the world's, measured from the effect's own height (the likeness's `step` takes it).
- **Local space**: an emitter whose particles are in the world (not bUseLocalSpace) leaves them where they were when
  the effect moves (a drag, a copy on the cursor): each step takes what moved since back off them.
- Where: [post_chain.js](../../tools/viewer/web/post_chain.js), [app.js](../../tools/viewer/web/app.js) (`drawFrame`
  hands the likenesses' layer and the depth's setter), [effects_preview.js](../../tools/viewer/web/effects_preview.js),
  [effects_sim.js](../../tools/viewer/web/effects_sim.js), [effects_wiring.js](../../tools/viewer/web/effects_wiring.js),
  [ARCHITECTURE.md](../../ARCHITECTURE.md).
- Checked: [effects_sim_test.mjs](../../tools/viewer/tests/effects_sim_test.mjs) (a floor in the world and one under the
  emitter); the `likeness` browser check (the Game look's frame drew the likenesses' pass) on URB_Bar and
  CSmallScout_DirtRoad, with `map-lights`, `time-of-day`, `sky-choice`, `effects`, `dense-lighting` and `api-names` on
  URB_Bar. Track H's likeness (stage e3): all twelve 6.93 to 6.88 (CSmallScout_DirtRoad 5.09 to 4.88: its smoke no
  longer cut hard where it meets the ground). The likenesses' pass costs the Game look's frame about 0.5 to 0.7 ms
  (perf_probe.py headless, A/B of the pass on AlienBase01 and CSmallScout_DirtRoad; the computer busy, its spread as
  large); the Neutral look draws as before.
- Gaps: PSUVIM_Random_Blend changes no image over a life; a world-space emitter's particles keep their own turn when
  the effect is turned; no soft edge outside the Game look.
