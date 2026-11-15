/**
 * Spawns a real game object from an archetype that is already loaded, normally from the base map a patch streams
 * into, for example the compact car 'VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1' (an
 * XComDestructibleActor) with its glass 'VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc0' (an
 * XComFracLevelActor) as partner, while URB_Bar is loaded (EXP-05). The spawned actors are the game's own: collision,
 * cover, toughness, damage and destruction, materials and tint all come from the archetype.
 *
 * - A destructible archetype becomes an XComMapEdDestructible, a copy that is lit dynamically (a straight copy of the
 *   archetype has no lightmap and renders black). A fracturing one (glass) becomes an XComMapEdGlass, whose names stay
 *   the same on every load so that saves find it. Other archetypes are spawned as they are.
 * - A fracturing partner (the glass) gets fragment columns. The level editor bakes these into every placed
 *   XComFracLevelActor, but the archetype has none, and without them damage breaks nothing. Each column is the part of
 *   the glass inside one world tile. It lists the fragments there and the main actor, which then takes collateral
 *   damage when the glass breaks; that is what sets a car alight.
 * - Tile data (pathing, cover) is rebuilt around the spawn point as soon as it spawns. The level start places Meld
 *   canisters, alien pods and the landing zone on tiles a fraction of a second later (LWR's spawn mutators, in
 *   XGBattle_SP.PostLevelLoaded), and would otherwise see the ground under the object as open floor.
 * - A save keeps damaged objects only. On load it recreates each one from its class defaults under the same name,
 *   replacing the fresh one spawned here; the object then calls RestoreLoaded to get its archetype's mesh and the rest
 *   back before the saved state is applied (findings register F-17).
 */
class XComMapEdSpawner extends Actor
	placeable;

/** Full path of the main actor's archetype in memory. */
var() string ArchetypePath;
/** Optional second archetype spawned with it (the glass of a vehicle); it becomes the main actor's HidingPartner. */
var() string PartnerPath;
/** Partner position relative to the main actor, in the spawner's rotation. */
var() vector PartnerOffset;
/** Paint colour for the spawned actors (XComLevelActor / XComFracLevelActor TintColor), if bTint. */
var() bool bTint;
var() LinearColor Tint;
/** Half-size of the box whose tile data is rebuilt after spawning. */
var() vector RebuildExtent;
/** If above 0, also logs the health and state of the level's own destructibles within this distance (EXP-05). */
var() float WatchRadius;
/**
 * EXP-05 control: rebuilds the tile data over the watched destructibles once, at runtime as for our own objects, and
 * logs their flammable tiles before and after. Shows whether a runtime rebuild keeps the map's baked flammability.
 */
var() bool bRebuildWatched;
/**
 * EXP-05 variant: spawns a destructible archetype as a straight copy of its own class instead of an
 * XComMapEdDestructible. It renders black (F-02); it shows whether our class changes how the tiles are built.
 */
var() bool bPlainCopy;
/**
 * With BuildingName, the spawned pieces join that building's floor BuildingFloor in its floor caches (cutdown floor 0,
 * as the roof pieces copied there have), so the cutaway hides them with that floor: a car on the L layout's copied
 * roof (EXP-07 run 31). The cutaway works only from the baked caches (F-31).
 */
var() name BuildingName;
var() int BuildingFloor;
/**
 * Moves the spawned pieces (by up to half a tile in x and y) so that the body fills whole tiles, as the map's own cars
 * stand: each side of its bounds is rounded to whole tiles, and the body's centre goes on a tile edge across an even
 * count and in a tile's middle across an odd one. Off the grid, a car's nose and tail reach into the next tiles and
 * block them, so its ends give no cover (EXP-07 run 31, F-41). Only for a yaw within 10 degrees of a multiple of 90.
 */
var() bool bSnapToTiles;
/** The spawned pieces leave out a sky light that lights units only (XComMapEdSkyFree, F-52), unless this is set. */
var() bool bKeepSkyLight;
var transient vector SnapShift;

var transient Actor Main, Partner;
var transient int LastHealth, LastFragments;
var transient name LastState;
var transient array<XComDestructibleActor> Others;
var transient array<int> OtherHealth;
var transient array<name> OtherState;
var transient array<Actor> SeenVolumes;
var transient int WatchedRebuild;   // 0 not yet, 1 rebuilding, 2 done and logged

simulated event PostBeginPlay()
{
	local XComWorldData World;
	local box B;

	super.PostBeginPlay();
	if (ArchetypePath == "")
		return;
	Main = SpawnPart(ArchetypePath, vect(0, 0, 0));
	if (Main == none)
		return;
	if (PartnerPath != "")
		Partner = SpawnPart(PartnerPath, PartnerOffset);
	if (XComLevelActor(Main) != none)
		XComLevelActor(Main).HidingPartner = Partner;   // the archetype points at the other archetype
	if (bSnapToTiles)
		SnapToTiles();
	if (bTint)
	{
		TintActor(Main);
		TintActor(Partner);
	}
	World = class'XComWorldData'.static.GetWorldData();
	if (World != none)
	{
		Main.GetComponentsBoundingBox(B);
		`log("XComMapEd:" @ self @ "flammable tiles under" @ Main @ "before the rebuild:" @ FlammableByLevel(World, B));
	}
	LeaveOutSkyLight(Main);
	LeaveOutSkyLight(Partner);
	RebuildTiles(true);
	SetTimer(0.01, true, 'WaitForTiles');
	SetTimer(1.0, false, 'CheckPlacements');
	SetTimer(1.0, true, 'WatchMain');
	if (BuildingName != '')
		SetTimer(0.5, true, 'JoinBuilding');
}

/** See bSnapToTiles. */
function SnapToTiles()
{
	local XComWorldData World;
	local box B;
	local vector Mid, T, Back;
	local int X, Y, Z, X2, Y2, Z2, Quarter;
	local float EdgeX, EdgeY;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none || Main == none)
		return;
	Quarter = Main.Rotation.Yaw & 16383;
	if (Quarter > 1820 && Quarter < 16384 - 1820)
	{
		`log("XComMapEd:" @ self @ "did not snap" @ Main @ "to the tiles: yaw" @ Main.Rotation.Yaw @ "is not near a multiple of 90 degrees");
		return;
	}
	Main.GetComponentsBoundingBox(B);
	if (B.Max.X - B.Min.X > 1500 || B.Max.Y - B.Min.Y > 1500 || B.Max.X <= B.Min.X || B.Max.Y <= B.Min.Y)
	{
		`log("XComMapEd:" @ self @ "did not snap" @ Main @ "to the tiles: its bounds" @ B.Min @ "to" @ B.Max @ "look wrong");
		return;
	}
	// A tile edge: GetPositionFromTileCoordinates gives the tile's centre or its corner; a point 47 units back from a
	// centre is still in the tile.
	Mid = (B.Min + B.Max) / 2.0;
	World.GetTileCoordinatesFromPosition(Mid, X, Y, Z);
	T = World.GetPositionFromTileCoordinates(X, Y, Z);
	Back = T - vect(47, 47, 0);
	World.GetTileCoordinatesFromPosition(Back, X2, Y2, Z2);
	EdgeX = X2 == X ? T.X - 48 : T.X;
	EdgeY = Y2 == Y ? T.Y - 48 : T.Y;
	SnapShift.X = SnapAxis(B.Min.X, B.Max.X, EdgeX);
	SnapShift.Y = SnapAxis(B.Min.Y, B.Max.Y, EdgeY);
	SnapShift.Z = 0;
	Main.SetLocation(Main.Location + SnapShift);
	if (Partner != none)
		Partner.SetLocation(Partner.Location + SnapShift);
	`log("XComMapEd:" @ self @ "snapped" @ Main @ "to the tiles: bounds" @ B.Min @ "to" @ B.Max @ "(" $ Round((B.Max.X - B.Min.X) / 96.0) @ "x"
		@ Round((B.Max.Y - B.Min.Y) / 96.0) @ "tiles), moved by" @ SnapShift $ "; now at" @ Main.Location);
}

/** The shift along one axis that puts a body spanning Lo..Hi on whole tiles, given any tile edge. */
function float SnapAxis(float Lo, float Hi, float Edge)
{
	local int n;
	local float Mid, Target;

	n = Max(1, Round((Hi - Lo) / 96.0));
	Mid = (Lo + Hi) / 2.0;
	if ((n & 1) == 0)
		Target = Edge + 96.0 * Round((Mid - Edge) / 96.0);
	else
		Target = Edge + 48.0 + 96.0 * Round((Mid - Edge - 48.0) / 96.0);
	return Target - Mid;
}

/** Puts the spawned pieces into BuildingName's floor BuildingFloor (retried until the building has that floor). */
function JoinBuilding()
{
	local XComBuildingVolume BV;
	local FloorActorInfo FAI;
	local int j, n;
	local bool bMain, bPartner;

	foreach AllActors(class'XComBuildingVolume', BV)
		if (BV.Name == BuildingName)
			break;
	if (BV == none || BV.Name != BuildingName || BuildingFloor >= BV.Floors.Length || Main == none)
		return;
	ClearTimer('JoinBuilding');
	for (j = 0; j < BV.Floors[BuildingFloor].m_aCachedActors.Length; j++)
	{
		bMain = bMain || BV.Floors[BuildingFloor].m_aCachedActors[j].ResidentActor == Main;
		bPartner = bPartner || BV.Floors[BuildingFloor].m_aCachedActors[j].ResidentActor == Partner;
	}
	FAI.CutdownFloor = 0;
	if (!bMain)
	{
		FAI.ResidentActor = Main;
		BV.Floors[BuildingFloor].m_aCachedActors.AddItem(FAI);
		n++;
	}
	if (Partner != none && !bPartner)
	{
		FAI.ResidentActor = Partner;
		BV.Floors[BuildingFloor].m_aCachedActors.AddItem(FAI);
		n++;
	}
	`log("XComMapEd:" @ self @ "put" @ n @ "piece(s) into" @ BV @ "floor" @ BuildingFloor $ "'s cache, now" @ BV.Floors[BuildingFloor].m_aCachedActors.Length @ "actors");
}

/** Logs every change of the spawned destructible's health or state, and of its glass's visible fragments (EXP-05). */
function WatchMain()
{
	local XComDestructibleActor D;
	local XComFracLevelActor G;
	local int Fragments;

	D = XComDestructibleActor(Main);
	if (D == none || D.bDeleteMe)
	{
		ClearTimer('WatchMain');
		return;
	}
	if (D.Health != LastHealth || D.GetStateName() != LastState)
	{
		`log("XComMapEd:" @ self @ D @ "health" @ LastHealth @ "->" @ D.Health @ "of" @ D.TotalHealth @ "state" @ LastState @ "->" @ D.GetStateName());
		LastHealth = D.Health;
		LastState = D.GetStateName();
	}
	G = XComFracLevelActor(Partner);
	if (G != none && !G.bDeleteMe)
	{
		Fragments = G.FracturedStaticMeshComponent.GetNumVisibleFragments();
		if (Fragments != LastFragments)
		{
			`log("XComMapEd:" @ self @ G @ "visible fragments" @ LastFragments @ "->" @ Fragments @ "of" @ G.FracturedStaticMeshComponent.GetNumFragments() @ "columns damaged/destroyed" @ CountColumns(G, false) $ "/" $ CountColumns(G, true) @ "of" @ G.FragmentColumns.Length);
			LastFragments = Fragments;
		}
	}
	WatchOthers();
}

static function int CountColumns(XComFracLevelActor G, bool bDestroyed)
{
	local int i, n;

	for (i = 0; i < G.FragmentColumns.Length; i++)
		if (bDestroyed ? G.FragmentColumns[i].bDestroyed : G.FragmentColumns[i].bDamaged)
			n++;
	return n;
}

/** Logs changes in the health or state of the level's own destructibles near this spawner (see WatchRadius). */
function WatchOthers()
{
	local XComDestructibleActor A;
	local XComWorldData World;
	local Actor V;
	local box B;
	local int i;

	if (WatchRadius <= 0)
		return;
	World = class'XComWorldData'.static.GetWorldData();
	// Every new fire, smoke or other volume on the map (EXP-05: does a blast on our cars make fires at all?).
	foreach DynamicActors(class'Actor', V)
	{
		if (V.Class.Name == 'XGVolume' && SeenVolumes.Find(V) == -1)
		{
			SeenVolumes.AddItem(V);
			`log("XComMapEd:" @ self @ "new volume" @ V @ "at" @ V.Location @ "radius" @ CylinderComponent(V.CollisionComponent).CollisionRadius @ "height" @ CylinderComponent(V.CollisionComponent).CollisionHeight @ "flammable there" @ World.IsLocationFlammable(V.Location));
		}
	}
	if (Others.Length == 0)
	{
		foreach AllActors(class'XComDestructibleActor', A)
		{
			if (XComMapEdDestructible(A) == none && VSize(A.Location - Location) < WatchRadius)
			{
				Others.AddItem(A);
				OtherHealth.AddItem(A.Health);
				OtherState.AddItem(A.GetStateName());
				A.GetComponentsBoundingBox(B);
				`log("XComMapEd:" @ self @ "watching" @ A @ PathName(A.ObjectArchetype) @ "at" @ A.Location @ "health" @ A.Health @ "of" @ A.TotalHealth @ "state" @ A.GetStateName() @ "toughness" @ A.Toughness @ "flammable tiles:" @ FlammableByLevel(World, B));
			}
		}
		if (Others.Length == 0)
			WatchRadius = 0;
		return;
	}
	if (bRebuildWatched && WatchedRebuild == 0 && !World.IsRebuildingTiles())
	{
		for (i = 0; i < Others.Length; i++)
			RebuildOver(Others[i], World);
		WatchedRebuild = 1;
	}
	else if (WatchedRebuild == 1 && !World.IsRebuildingTiles())
	{
		for (i = 0; i < Others.Length; i++)
		{
			Others[i].GetComponentsBoundingBox(B);
			`log("XComMapEd:" @ self @ "level's" @ Others[i] @ "flammable tiles after a runtime rebuild:" @ FlammableByLevel(World, B));
		}
		WatchedRebuild = 2;
	}
	for (i = 0; i < Others.Length; i++)
	{
		A = Others[i];
		if (A == none || A.bDeleteMe)
			continue;
		if (A.Health != OtherHealth[i] || A.GetStateName() != OtherState[i])
		{
			`log("XComMapEd:" @ self @ "level's" @ A @ "health" @ OtherHealth[i] @ "->" @ A.Health @ "of" @ A.TotalHealth @ "state" @ OtherState[i] @ "->" @ A.GetStateName() @ "last damage" @ A.LastDamage.DamageType @ A.LastDamage.DamageAmount @ "from" @ A.LastDamage.DamageCauser);
			OtherHealth[i] = A.Health;
			OtherState[i] = A.GetStateName();
		}
	}
}

/**
 * Gives the glass G fragment columns like the ones the level editor bakes, one per world tile it covers. A column's
 * bounds are the fragments' boxes clipped to its tile; in height they reach from below ground up to 192 above the
 * glass's bottom, so that their centre, where a fire starts, is in the ground-level tile. Its fragment list is sorted
 * by bottom height, and it names the main actor D for collateral damage.
 */
function BuildFragmentColumns(XComFracLevelActor G, XComDestructibleActor D, XComWorldData World)
{
	local FracturedStaticMeshComponent C;
	local array<box> Boxes;
	local box All, DB, Cell, Part;
	local FragmentColumn Col, Empty;
	local FragmentCacheEntry F;
	local DestructibleCacheEntry DE;
	local vector O;
	local int i, j, n, tx, ty;

	C = G.FracturedStaticMeshComponent;
	n = C.GetNumFragments();
	if (n == 0)
		return;
	for (i = 0; i < n; i++)
	{
		Boxes[i] = C.GetFragmentBox(i);
		All = i == 0 ? Boxes[i] : UnionBox(All, Boxes[i]);
	}
	D.GetComponentsBoundingBox(DB);
	O = World.WorldBounds.Min;
	G.FragmentColumns.Length = 0;
	for (tx = FFloor((All.Min.X - O.X) / 96.0); O.X + tx * 96.0 < All.Max.X; tx++)
	{
		for (ty = FFloor((All.Min.Y - O.Y) / 96.0); O.Y + ty * 96.0 < All.Max.Y; ty++)
		{
			Cell.Min.X = O.X + tx * 96.0;
			Cell.Min.Y = O.Y + ty * 96.0;
			Cell.Max.X = Cell.Min.X + 96.0;
			Cell.Max.Y = Cell.Min.Y + 96.0;
			Col = Empty;
			for (i = 0; i < n; i++)
			{
				if (Boxes[i].Max.X <= Cell.Min.X || Boxes[i].Min.X >= Cell.Max.X || Boxes[i].Max.Y <= Cell.Min.Y || Boxes[i].Min.Y >= Cell.Max.Y)
					continue;
				Part = Boxes[i];
				Part.Min.X = FMax(Part.Min.X, Cell.Min.X);
				Part.Min.Y = FMax(Part.Min.Y, Cell.Min.Y);
				Part.Max.X = FMin(Part.Max.X, Cell.Max.X);
				Part.Max.Y = FMin(Part.Max.Y, Cell.Max.Y);
				Col.Bounds = Col.FragCache.Length == 0 ? Part : UnionBox(Col.Bounds, Part);
				F.FragIndex = i;
				F.MinZ = Boxes[i].Min.Z;
				for (j = 0; j < Col.FragCache.Length && Col.FragCache[j].MinZ <= F.MinZ; j++)
					;
				Col.FragCache.InsertItem(j, F);
			}
			if (Col.FragCache.Length == 0)
				continue;
			// The baked columns span the glass's bottom to 192 above it. When a column is destroyed, the game makes the
			// centre of its bounds a fire spot (XComWorldData.PotentialFireColumns), and a fire only takes on a tile
			// counted as flammable. A runtime tile rebuild marks only the ground-level tile under a flammable object,
			// never the window-height one that the map's bake marks (findings register F-14). So the bottom is lowered
			// to put the centre in the ground-level tile, half a level above the car's bottom; the top stays.
			Col.Bounds.Max.Z = FMax(All.Max.Z, All.Min.Z + 192.0);
			Col.Bounds.Min.Z = 2 * (DB.Min.Z + 32.0) - Col.Bounds.Max.Z;
			Col.Bounds.IsValid = 1;
			DE.DestructibleActor = D;
			DE.MinZ = DB.Min.Z;
			Col.DestructibleCache.AddItem(DE);
			G.FragmentColumns.AddItem(Col);
		}
	}
	LastFragments = C.GetNumVisibleFragments();
	`log("XComMapEd:" @ self @ "gave" @ G @ G.FragmentColumns.Length @ "fragment columns over" @ n @ "fragments, collateral to" @ D);
}

static function box UnionBox(box A, box B)
{
	A.Min.X = FMin(A.Min.X, B.Min.X);
	A.Min.Y = FMin(A.Min.Y, B.Min.Y);
	A.Min.Z = FMin(A.Min.Z, B.Min.Z);
	A.Max.X = FMax(A.Max.X, B.Max.X);
	A.Max.Y = FMax(A.Max.Y, B.Max.Y);
	A.Max.Z = FMax(A.Max.Z, B.Max.Z);
	A.IsValid = 1;
	return A;
}

function Actor SpawnPart(string Path, vector Offset)
{
	local Actor Template, A;
	local XComMapEdDestructible D;
	local XComMapEdGlass G;

	Template = Actor(FindObject(Path, class'Actor'));
	if (Template == none)
	{
		`log("XComMapEd:" @ self @ "did not find archetype" @ Path);
		return none;
	}
	if (XComDestructibleActor(Template) != none && !bPlainCopy)
	{
		D = Spawn(class'XComMapEdDestructible', , , Location + (Offset >> Rotation), Rotation, , true);
		if (D != none)
			D.CopyFrom(XComDestructibleActor(Template));
		A = D;
	}
	else if (XComFracLevelActor(Template) != none)
	{
		G = Spawn(class'XComMapEdGlass', , , Location + (Offset >> Rotation), Rotation, , true);
		if (G != none)
			G.CopyFrom(XComFracLevelActor(Template));
		A = G;
	}
	else
		A = Spawn(Template.Class, , , Location + (Offset >> Rotation), Rotation, Template, true);
	`log("XComMapEd:" @ self @ "spawned" @ A @ "from" @ PathName(Template));
	return A;
}

/** Has one of the spawned pieces (our own classes only) leave out a units-only sky light (XComMapEdSkyFree). */
function LeaveOutSkyLight(Actor A)
{
	if (!bKeepSkyLight && (XComMapEdDestructible(A) != none || XComMapEdGlass(A) != none))
		class'XComMapEdSkyFree'.static.Add(self, A);
}

function TintActor(Actor A)
{
	if (XComLevelActor(A) != none)
	{
		XComLevelActor(A).TintColor = Tint;
		XComLevelActor(A).UpdateTintColor();
	}
	else if (XComFracLevelActor(A) != none)
	{
		XComFracLevelActor(A).TintColor = Tint;
		XComFracLevelActor(A).UpdateTintColor();
	}
}

/**
 * Rebuilds the tile data in RebuildExtent around the spawner. The game spreads a rebuild over several frames, 16 tiles a
 * frame by default, so ten cars would take about two seconds. At load (bAtLoad) the rate is raised so that the rebuild is
 * done in one update, before the level start places anything; WaitForTiles sets it back afterwards.
 */
function RebuildTiles(optional bool bAtLoad)
{
	local XComWorldData World;
	local vector P, E;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
	{
		`log("XComMapEd:" @ self @ "has no world data to rebuild yet; retrying");
		SetTimer(2.0, false, 'RebuildTiles');
		return;
	}
	if (XComFracLevelActor(Partner) != none && XComFracLevelActor(Partner).FragmentColumns.Length == 0 && XComDestructibleActor(Main) != none)
		BuildFragmentColumns(XComFracLevelActor(Partner), XComDestructibleActor(Main), World);
	P = Location + SnapShift;
	E = RebuildExtent;
	if (bAtLoad)
		World.SetRebuildTileProcessRate(100000);
	World.RebuildTileDataExtents(P, E);
	`log("XComMapEd:" @ self @ "rebuilt tile data around" @ P @ "extent" @ E);
}

/** Waits for the load-time rebuild to finish, logs when it did, and sets the rebuild rate back to the game's default. */
function WaitForTiles()
{
	local XComWorldData World;

	World = class'XComWorldData'.static.GetWorldData();
	if (World != none && World.IsRebuildingTiles())
		return;
	ClearTimer('WaitForTiles');
	if (World != none)
		World.SetRebuildTileProcessRate(16);   // XComWorldData.DEFAULT_REBUILD_TILE_RATE
	`log("XComMapEd:" @ self @ "tile rebuild finished");
}

/**
 * Logs anything the level start placed inside the spawned object: Meld canisters, their spawn points and units (EXP-05:
 * a canister landed inside a car while the tile rebuild still ran a second after spawning). Also logs how much of the
 * object the game counts as flammable; fires from explosions only burn there.
 */
function CheckPlacements()
{
	local XComWorldData World;
	local box B;
	local Actor A;

	if (Main == none || Main.bDeleteMe)
		return;
	Main.GetComponentsBoundingBox(B);
	foreach DynamicActors(class'Actor', A)
	{
		if ((XComMeldContainerActor(A) != none || XComMeldContainerSpawnPoint(A) != none || XComUnitPawn(A) != none)
			&& A.Location.X > B.Min.X && A.Location.X < B.Max.X && A.Location.Y > B.Min.Y && A.Location.Y < B.Max.Y)
			`log("XComMapEd:" @ self @ "WARNING:" @ A @ "was placed inside" @ Main @ "at" @ A.Location);
	}
	World = class'XComWorldData'.static.GetWorldData();
	if (World != none)
		`log("XComMapEd:" @ self @ "flammable tiles under" @ Main @ "after the rebuild:" @ FlammableByLevel(World, B));
}

/** Rebuilds the tile data over A's bounding box plus one tile around it, as RebuildTiles does for our own objects. */
function RebuildOver(Actor A, XComWorldData World)
{
	local box B;
	local vector P, E;

	A.GetComponentsBoundingBox(B);
	P = (B.Min + B.Max) / 2.0;
	E = (B.Max - B.Min) / 2.0 + vect(96, 96, 64);
	World.RebuildTileDataExtents(P, E);
	`log("XComMapEd:" @ self @ "rebuilt tile data over the level's" @ A @ "around" @ P @ "extent" @ E);
}

/**
 * How many of the tiles over the box the game counts as flammable, per height level, from the level of the box's
 * bottom four levels up: "Z32 3/8, Z96 0/8, ..." (each level's centre height, flammable tiles of all). Tiles are 96
 * units across and 64 high, counted from XComWorldData.WorldBounds.Min.
 */
static function string FlammableByLevel(XComWorldData World, box B)
{
	local vector O, P;
	local int tx, ty, tz, z0, n, m;
	local string S;

	O = World.WorldBounds.Min;
	z0 = FFloor((B.Min.Z - O.Z) / 64.0);
	for (tz = z0; tz < z0 + 4; tz++)
	{
		n = 0;
		m = 0;
		P.Z = O.Z + (tz + 0.5) * 64.0;
		for (tx = FFloor((B.Min.X - O.X) / 96.0); O.X + tx * 96.0 < B.Max.X; tx++)
		{
			for (ty = FFloor((B.Min.Y - O.Y) / 96.0); O.Y + ty * 96.0 < B.Max.Y; ty++)
			{
				P.X = O.X + (tx + 0.5) * 96.0;
				P.Y = O.Y + (ty + 0.5) * 96.0;
				m++;
				if (World.IsLocationFlammable(P))
					n++;
			}
		}
		S = S $ (S == "" ? "" : ", ") $ "Z" $ int(P.Z) @ n $ "/" $ m;
	}
	return S;
}

/**
 * Gives a spawned object that a save is recreating (A is Main or Partner, now bare class defaults under the same name,
 * in its PostBeginPlay; findings register F-17) back what it took from the archetype at spawn: mesh, materials, events,
 * toughness, cover and paint. The game then applies the saved record, which puts back the health and replays the wreck,
 * fire and broken glass. The tiles are rebuilt once that is done.
 */
function RestoreLoaded(Actor A)
{
	local Actor T;

	T = Actor(FindObject(A == Main ? ArchetypePath : PartnerPath, class'Actor'));
	if (XComMapEdDestructible(A) != none && XComDestructibleActor(T) != none)
	{
		XComMapEdDestructible(A).CopyFrom(XComDestructibleActor(T));
		XComMapEdDestructible(A).HoldBackBlasts();
	}
	else if (XComMapEdGlass(A) != none && XComFracLevelActor(T) != none)
		XComMapEdGlass(A).CopyFrom(XComFracLevelActor(T));
	if (bTint)
		TintActor(A);
	if (XComLevelActor(Main) != none)
		XComLevelActor(Main).HidingPartner = Partner;
	LeaveOutSkyLight(A);
	`log("XComMapEd:" @ self @ "restored" @ A @ "from" @ PathName(T) @ "after a load, at" @ A.Location);
	SetTimer(0.5, false, 'RebuildTiles');
}

defaultproperties
{
	bHidden=true
	RebuildExtent=(X=192,Y=256,Z=160)
}
