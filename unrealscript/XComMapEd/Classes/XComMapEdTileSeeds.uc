/**
 * Rebuilds, at load, the tile data over the boxes whose tiles patchtool seeded in the base map's baked world data
 * (findings register F-29, research/native-code-notes.md, tools/upk/seed_map.py).
 *
 * The game's runtime rebuild only re-checks a tile whose baked static flags have one of the low 12 bits. A piece a
 * patch adds above the ground, where the map had nothing, is never seen there, so it blocks neither line of sight nor
 * movement. patchtool seeds bit 0x1 on those tiles in the lab's copy of the map, and the rebuild then computes their
 * flags from what stands there now. A seeded tile that is never rebuilt would keep the seed bit, so this actor rebuilds
 * every planned box, whatever the other actors rebuild themselves. patchtool places it last in the patch, from the same
 * plan it seeds the map with.
 */
class XComMapEdTileSeeds extends Actor
	placeable;

/** The world boxes to rebuild (each plan row's tiles plus a few units). */
var() array<box> SeedBoxes;
/** How many tiles the plan seeds, for the log. */
var() int PlannedTiles;

simulated event PostBeginPlay()
{
	super.PostBeginPlay();
	RebuildSeeded();
}

function RebuildSeeded()
{
	local XComWorldData World;
	local vector P, E;
	local int i;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
	{
		`log("XComMapEd:" @ self @ "has no world data to rebuild yet; retrying");
		SetTimer(0.5, false, 'RebuildSeeded');
		return;
	}
	World.SetRebuildTileProcessRate(100000);
	for (i = 0; i < SeedBoxes.Length; i++)
	{
		// The native takes const out vectors, which can't be array elements.
		P = (SeedBoxes[i].Min + SeedBoxes[i].Max) / 2.0;
		E = (SeedBoxes[i].Max - SeedBoxes[i].Min) / 2.0;
		World.RebuildTileDataExtents(P, E);
	}
	`log("XComMapEd:" @ self @ "rebuilding" @ SeedBoxes.Length @ "seeded box(es)," @ PlannedTiles @ "planned tiles");
	SetTimer(0.01, true, 'WaitForTiles');
}

function WaitForTiles()
{
	local XComWorldData World;

	World = class'XComWorldData'.static.GetWorldData();
	if (World != none && World.IsRebuildingTiles())
		return;
	ClearTimer('WaitForTiles');
	if (World != none)
		World.SetRebuildTileProcessRate(16);   // XComWorldData.DEFAULT_REBUILD_TILE_RATE
	`log("XComMapEd:" @ self @ "seeded tile rebuild finished");
}

defaultproperties
{
	bHidden=true
}
