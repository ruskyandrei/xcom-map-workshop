# Destructible floors, falling units and building collapse

18 November 2026. Read-only follow-up to [EXP-28](EXP-28-fracturing-physics.md). The evidence comes from the
custom geometry branch, the installed LWR maps and scripts, a copy of the EW executable, and earlier game runs.
The occupied-floor comparison described below is still unplayed.

## What belongs in the map

| Desired effect | What the editor could bake | What remains to prove or implement |
| --- | --- | --- |
| A blast opens a hole in an upper floor | A walkable fractured slab, its collision, fragments, damage columns and toughness. The M5 floor and roof work is building this. | A generated slab must lose its tactical floor tile when it breaks. Test walking, traces and the floor below independently of the visible hole. |
| Furniture goes with the floor | Link a particular slab column to a destructible prop. The ordinary prop can break, lose its collision or swap to a wreck through its authored actions. | Collateral damage can leave a tough prop standing. An intact desk coming to rest downstairs, still providing cover, needs movement and a tile update. |
| A soldier or alien ends up downstairs | The game already has a post-destruction ground snap that excludes active fliers. A walkable prop which swaps its mesh has a confirmed route to the event. | Find out whether an ordinary fractured slab fires it. An occupied or invalid landing, a fall animation and height-based tactical damage are separate questions. |
| Losing two of three posts drops one balcony | Cook the posts as distinct destructibles and a Kismet sequence that counts their destruction once and operates a specific balcony. A whole-panel prop makes a plausible target. | The editor would need to emit the sequence, the panel would need a working destruction action, and partial progress must survive a reload. |
| Failure spreads through several storeys | Mark the foundation, load-bearing posts or wall sections, and the floor and wall sections that depend on them. | A reusable gameplay controller must evaluate surviving support, trigger further losses and resolve the occupants. It could ship with the maps as a script package or live in LWR. |

### What the current slabs actually contain

The M5 audit at commit `64766d3` on `fracturing-wall-poc` surveyed 151 listed maps. It identified 55 distinct
slab meshes placed 175 times on 38 maps. Summing the mesh records gives 3,442 fragments, all marked destroyable,
zero root fragments and no core fragment on any of the 55 meshes. These are the audit's floor and roof candidates.
Plain floors and terrain fall outside its selection.

We looked up all 175 placed actors again in the installed packages, following their toughness through the archetype
with [the viewer's destruction reader](../../tools/viewer/scene_metadata.py). Of 63 floor actors, 54 specify masonry
(80), six metal (90) and three wood (40). Of 112 roofs, 72 specify masonry, 28 metal and 12 name no toughness.
These are asset toughness values. Both M5 donors on Bar, upper floor `XComFracLevelActor_17` and roof
`XComFracLevelActor_3`, specify masonry. Use one of these as the stock control for the generated slab.

EXP-28 already found four new walkable tiles over a copied Bar floor strip. A duct left the other six with
insufficient headroom. The run did not break that floor. On the branch, EXP-67 established that generated walls
fracture in combat and keep their damage through reload. At the time of inspection a slab generator was in
progress and the M5 game check was pending. A useful caution from the slab audit is that 24 of 39 sampled
tile centres over *pre-hidden* floor fragments still had the baked floor bit. A live break can rebuild those
tiles. Any coincident static floor, invisible standing plate or remaining collision must still be accounted for.

### What can go with a broken tile

The maps already encode specific furniture dependencies. In `Act2_Pier`, slab `XComFracLevelActor_0`, columns 12
and 13, names crate stack `XComDestructibleActor_381` immediately above it. Across the audited slabs there are
31,087 destructible references, including 15,239 above and over the slab and 9,572 below and over it. These count
references, so one prop can occur many times. They describe collateral damage links. A map author needs to
distinguish furniture resting on a floor from a light hanging beneath it and items merely caught by the blast.

When a fragment breaks on the ordinary cascading path, the column can send damage to its listed props. For a
prop whose destruction should be compulsory, EW also has linked prop states (`AffectedChildren`). The editor has
played that mechanism with a disappearing cover block. The custom wall branch also writes links from generated
wall columns to nearby props and cover blocks. A static decoration has no prop damage state. A falling physics
chunk can supply the visual effect, but a usable object below needs valid collision, cover and checkpoint state.
[EXP-52](EXP-52-breaking-cover-blocks.md)

## How the game moves a unit after destruction

The installed game scripts contain `XComUnitPawnNativeBase.MoveToGroundAfterDestruction`, shared by soldier
and alien pawns. It retries after 0.1 seconds while `XComWorldData.IsRebuildingTiles()` is true. Once the rebuild
finishes it checks for a game unit and tests its current `IsFlying()` state. For a grounded unit it calls the
**pawn's** `SnapToGround(1024)`, then `XGUnit.ProcessNewPosition()`. The latter updates cover, visibility and an
active path. A flight-capable unit standing on a floor is eligible.

The underlying `Actor.SnapToGround` traces straight down and places the pawn over the first collision hit,
offset by its collision height. The pawn override restores its old position if the tactical location is invalid.
It does not search successively lower tactical tiles or choose a free adjacent square. For LWR, use the observed
change in the unit's standing height to measure a successful drop. An invalid snap can return the underlying hit
result even after the override restored the old position.

The native caller matters. In the examined EW executable, the class registration and constructor for
`XComDestructibleActor_Action_SwapStaticMesh` identify its `Activate` method. After the mesh operation it
dispatches the event to pawns whose `Actor.Base` is the prop. The fractured slab's normal damage path hides
fragments on the existing actor. We found no equivalent dispatch on that path. The map-only comparison is
therefore a slab against a walkable, mesh-swapping prop panel, with a pawn based on each. A working whole-panel
drop would be an option even if individual slab fragments need a small script hook.

There is a concrete donor for that comparison. The wooden pallet `Act2_Pier.XComDestructibleActor_85` has
path collision, wood toughness (40), and a destroyed-state mesh swap with `bDisableCollision` set. An elevated
panel can use that action setup. First confirm the pawn actually stands on the panel and names it as its base.

The snap event contains no HP change. The shipped `Engine.Pawn.Landed` can call `TakeFallingDamage` for a physical
landing, which uses vertical speed and `DmgType_Fell`. The snap follows a trace and changes position directly.
Neither that generic physics routine nor the voluntary `XGAction_DropDown` establishes a damage-per-storey rule
for a tactical unit. LWR has an appropriate place to define that rule and apply tactical damage once after a
confirmed landing. Its existing `RebalanceMutator.FixBadLocation` can search sideways or for a random valid point
and finishes a successful repair with `ProcessNewPosition`. That is useful precedent for updating a unit but
would give different landing behaviour.

## How far destruction propagates

**One joint.** On an eligible hit, a fragment column sends the same damage and height limit to the neighbouring
columns in its `FracActorCache`. The receiving actor's `TakeCollateralDamage` calls `DamageColumn` with further
cascading disabled. A hit can therefore damage both sides of a joint. Adding links A to B and B to C does not
make that hit on A travel onward to C. A fresh explosion can start another damage event. EXP-05 run 14 already
showed one burning car damaging three others. That produces an explosive chain with blast damage of its own.
[EXP-05](EXP-05-game-art-mesh.md)

**One mesh.** UE3 supports anchoring chunks within a fractured mesh. EW has a real island routine whose
implementation calls the component's fragment-group finder. A mesh combining the posts and one balcony section,
with roots at the feet of the posts, is worth comparing against an unrooted twin. The normal EW damage path's
use of that routine, the remaining collision and the pawn notification all need a game check. Roots on one
actor cannot express which separate floor or wall actors depend on it. [Epic's UE3 fracture documentation](https://docs.unrealengine.com/udk/Three/FractureTool.html)

**One authored collapse.** EW's `XComDestructibleActor` emits `SeqEvent_DestructibleStatusChanged` on entering
its damaged and destroyed states. The game's Kismet packages include integer increment and comparison nodes,
gates, and `SeqAct_SetDestructibleActorState`. The shipped Chryssalid Hive map contains instances of that last
action with `eDestroyed` selected. For a balcony, each post's first destroyed event could count once.
At two losses, a one-shot output could drive the balcony's destroyed state. That action casts its target to
`XComDestructibleActor`. A fractured slab is a different class, so it would need a different actuator, such as a
tested damage relay or a script call to damage its columns. A relay using radial damage can also hit the occupants
and muddle fall damage measurements. This recipe is feasible to prototype as map logic, with authoring and
save/load work still to do. [Epic's Kismet reference](https://docs.unrealengine.com/udk/Three/KismetReference.html)

**A whole building.** In EXP-74 a grenade removed the entire bottom wall of a stacked pair. The upper wall
remained suspended 192 units above the ground. A separate two-storey wall kept its upper section across a
four-tile gap. That build preceded the new joint links. The native limit of one damage hop still applies to
those links. Building and floor volumes handle visibility and cutaway. They carry no demonstrated load paths.
[EXP-44](EXP-44-hut-building.md)

For a reusable rule, the map can specify which sections carry which loads and what counts as adequate support.
For example, a balcony needs any two of three posts and an upper wall needs that balcony. A runtime controller
can count surviving posts, queue each failed section once, and repeat until nothing else loses support. It can
then resolve occupants against the final floors so a unit falling through two collapsing storeys is placed and
damaged once. Persist or reconstruct the lost supports across turns and reloads. A companion script package
would let maps opt in without a global LWR change. LWR integration would also let the same rule govern
marked sections across the mod's maps. Existing maps would need authored support data or a separate inference rule.
The existing native calls provide candidates for a script implementation. Reliable notification of actual
fragment loss and the handling of blocked landings are the main integration questions.

## What would settle the gameplay questions

1. Put a stock Bar floor, an M5 slab and a walkable destructible prop with a destroyed-state mesh swap over
   clear, walkable ground. Give the props distinguishable tile positions. Check the empty panels first. Record
   visible fragments, the upper and lower floor bits, pathing and cover before and after destruction.
2. Repeat with a stationary soldier, a grounded alien and an actively flying unit. Break the surface without
   directly damaging the occupant if possible. Otherwise use a matching blast over an intact floor and record
   blast damage separately. Record the pawn's base, old and new positions, tactical HP and next legal move.
   Repeat over a surviving middle floor, an occupied landing and a column with no floor in reach. Reload the
   broken state and check the same facts.
3. Destroy one of three posts, save and reload, then destroy a second one outside the balcony's direct blast
   radius. Its bay should fall once, a neighbouring supported bay should stand, and an upper section relying on
   the lost bay should fail only with the authored second stage. A final reload should retain the hole, the
   unit's position and its HP. This distinguishes a support rule from two pieces simply sharing a blast radius.

### Evidence trail

- Slab counts and attachments come from `research/evidence/slab-audit-2026-11-18.json` at `64766d3`.
  To repeat the toughness check, group its `placed` entries by map, open each installed package with
  [Package](../../tools/viewer/package.py) and call `scene_metadata.destruction` on
  `TheWorld.PersistentLevel.<actor>`. Root and destroyable counts are per distinct mesh in `meshes`.
- The branch's `research/native/frac-neighbours.md` at `5c744af` traces the one-hop limit. The played
  wall result is in `research/experiments/EXP-74-wall-light.md` at `1951165`. Both are available with
  `git show <commit>:<path>` in a checkout containing the custom geometry work.
- Script checks used [UeDecompile](../../tools/upk/UeDecompile.cs) on copies of the EW packages and the local
  LWR script reference. For the native check, `MoveToGroundAfterDestruction` resolves to the name at
  `0x01D3E280` in the inspected executable. Its dispatch at `0x00C32411` follows the base comparison at
  `0x00C32404`. `Actor.IsBasedOn` reads the same base field. The mesh-swap constructor installs the table at
  `0x01AB3318`, whose activation slot resolves to `0x00C32130`. The two XCOM fracture classes' island
  routine forwards to `0x009B7AF0`, which calls the same group finder as `GetFragmentGroups`. These
  addresses identify this binary. The [read-only PE tools](../../tools/re/pe.py) can reproduce the lookups.
