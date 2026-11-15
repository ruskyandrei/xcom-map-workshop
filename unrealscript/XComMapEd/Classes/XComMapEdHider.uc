/**
 * Takes part of the base map out of play at load (EXP-07, the hide test): every actor the level placed whose centre lies
 * in the box (the spawner's location, half-size HideExtent) is hidden and loses its collision, and the tile data over
 * the box is rebuilt so that units can walk, see and take cover there as if it had never been built.
 *
 * - Only actors of the base map's own level and of this patch's level count; other streamed levels (the dropship
 *   intro sits at the origin) are left alone.
 * - Hidden: static meshes and level actors (walls, floors above the ground, roofs, props), fractured actors, doors,
 *   ladders, physics actors, emitters, lens flares and decals. Doors also lose their interaction points. Level and
 *   fractured actors are also taken out of the cover and occupancy count (bAlwaysConsiderForCover off,
 *   bIgnoreForCover on) and stop blocking line of sight (VisibilityBlockingData), and fractured ones lose every
 *   fragment and have their columns marked destroyed (bHideFragments), as a wall blown open does. Doors go to their
 *   _Inactive state, as the game's own "disable interactive actor" does.
 * - Kept: anything whose whole box lies below KeepGroundHeight above the box's floor (the ground slab, rugs, sidewalks,
 *   puddles, decals there), the actors named in KeepNames, lights (unless bHideLights), spawn points, anything a
 *   patch spawned, and base-map pieces a copier moved into place (Tag XComMapEdMoved: doors, ladders).
 * - Diagnostics: the first hidden actor of each class logs the collision flags it is left with, and an optional
 *   probe line (ProbeStart to ProbeEnd) is traced before and after.
 * - Volumes: the base map's building and floor volumes whose centre is in the box lose their collision
 *   (bHideVolumes). A unit is inside a building while it touches one of its floor volumes, so this also stops the
 *   roof and floor cutaway there. Cursor volumes are kept unless bHideCursorVolumes: in URB_Bar they span the whole
 *   map, and without them the cursor can't go up a level anywhere (EXP-07 run 1, F-21). A patch's own volumes (its
 *   new building) are never touched.
 * - Logs a census of the box before and after (per level: tiles counted as floor, occupied, high and low cover) and
 *   rows of the ground level ('#' occupied, '.' floor, ':' cover, ' ' none). Every 3 s, all mission, it also checks
 *   that nothing it hid has come back (the cutaway shows and hides floors natively), and hides it again if it has.
 *
 * A bStatic actor can't be destroyed or moved, so hiding it is the only way to take it out (see the findings register).
 *
 * Exact targets (bExactTargets, the editor's compiler, E3): only the actors named in AlsoHide are hidden, wherever they
 * stand, and nothing else: no box, no ground rule, no volumes, so a deleted piece's neighbours stay. Names are matched
 * in the base map's own level only, never in a patch's, since short names repeat across levels (EXP-07). The tile
 * data is rebuilt over each hidden actor's own box (taken before hiding) plus RebuildPad. There is no census, which
 * counts a box.
 */
class XComMapEdHider extends Actor
	placeable;

/** Half-size of the box, around the actor's location. */
var() vector HideExtent;
/** Actors lying wholly below this height above the bottom of the box are kept (the ground they stand on). */
var() float KeepGroundHeight;
/** Actors to leave alone even inside the box (their names in the level, such as XComLevelActor_91). */
var() array<name> KeepNames;
/** Doors and ladders to hide where they stand; any other hidden door or ladder is moved under the map. */
var() array<name> HideInPlace;
/** Actors to hide even outside the box. */
var() array<name> AlsoHide;
/** Also hide lights in the box (off by default: the base map's lights can light what a patch builds there). */
var() bool bHideLights;
/** Take the base map's building and floor volumes in the box out of play. */
var() bool bHideVolumes;
/** Also take the cursor volumes in the box out of play (off: they can span the whole map; F-21). */
var() bool bHideCursorVolumes;
/** Also hide every fragment of fractured actors and mark their columns destroyed, as an explosion would. */
var() bool bHideFragments;
/** Tiles around the box that are rebuilt as well. */
var() float RebuildPad;

/**
 * EXP-07 run 6 test: run the game's full world data build (XComWorldData.BuildWorldData, as the map's baked tile data
 * was made) once after hiding, before the usual rebuild. A rebuild re-checks a tile above the ground only where the
 * baked data had something; copied walls on tiles that were empty don't block line of sight there (F-29).
 */
var() bool bFullWorldBuild;

/** Optional line, as two points, traced before and after hiding to show what still blocks there (EXP-07). */
var() vector ProbeStart, ProbeEnd;

/** Hide exactly the base map's actors named in AlsoHide, and nothing in a box (see above). */
var() bool bExactTargets;
/** With bExactTargets: a label per AlsoHide entry for the log (the editor's target). */
var() array<string> TargetLabels;

var transient array<Actor> HiddenActors;
var transient int Checks;
var transient array<name> FlagsLogged;
/** With bExactTargets: each hidden actor's box, taken before hiding, to rebuild. */
var transient array<box> TargetBoxes;

simulated event PostBeginPlay()
{
	super.PostBeginPlay();
	if (bExactTargets)
	{
		HideTargets();
		RebuildTiles();
		SetTimer(0.01, true, 'WaitForTiles');
		SetTimer(3.0, true, 'CheckHidden');
		return;
	}
	`log("XComMapEd:" @ self @ "census before hiding:" @ Census());
	LogGroundRows("before");
	Probe("before");
	HideAll();
	Probe("after hiding");
	RebuildTiles();
	SetTimer(0.01, true, 'WaitForTiles');
	SetTimer(3.0, true, 'CheckHidden');
}

function box HideBox()
{
	local box B;

	B.Min = Location - HideExtent;
	B.Max = Location + HideExtent;
	return B;
}

/**
 * The box around A's primitive components, from each one's own Bounds. Actor.GetComponentsBoundingBox comes back empty
 * for the level's walls and props (EXP-07 run 1: 190 of them read as lying on the ground). False if no component has
 * bounds.
 */
static function bool ActorBox(Actor A, out box AB)
{
	local PrimitiveComponent P;
	local vector Lo, Hi;
	local bool bAny;

	foreach A.AllOwnedComponents(class'PrimitiveComponent', P)
	{
		if (P.Bounds.BoxExtent.X <= 0 && P.Bounds.BoxExtent.Y <= 0 && P.Bounds.BoxExtent.Z <= 0)
			continue;
		Lo = P.Bounds.Origin - P.Bounds.BoxExtent;
		Hi = P.Bounds.Origin + P.Bounds.BoxExtent;
		if (!bAny)
		{
			AB.Min = Lo;
			AB.Max = Hi;
			bAny = true;
			continue;
		}
		AB.Min.X = FMin(AB.Min.X, Lo.X); AB.Min.Y = FMin(AB.Min.Y, Lo.Y); AB.Min.Z = FMin(AB.Min.Z, Lo.Z);
		AB.Max.X = FMax(AB.Max.X, Hi.X); AB.Max.Y = FMax(AB.Max.Y, Hi.Y); AB.Max.Z = FMax(AB.Max.Z, Hi.Z);
	}
	return bAny;
}

static function bool InBox(vector P, box B)
{
	return P.X >= B.Min.X && P.X <= B.Max.X && P.Y >= B.Min.Y && P.Y <= B.Max.Y && P.Z >= B.Min.Z && P.Z <= B.Max.Z;
}

/**
 * Whether A is a kind of actor this hider takes out (not where it is; see HideAll). Placed destructibles are neither
 * bStatic nor bNoDelete, so the classes decide, and nothing a patch spawns is taken.
 */
function bool IsHideable(Actor A)
{
	if (A == self || A.bDeleteMe)
		return false;
	// Only the base map's own level and this patch's: streamed levels such as CIN_DropshipIntros sit at the origin,
	// which can be inside the box (EXP-07 run 2 hid its emitters).
	if (A.Outer != WorldInfo.Outer && A.Outer != Outer)
		return false;
	if (XComMapEdDestructible(A) != none || XComMapEdGlass(A) != none || XComMapEdBorrowedMesh(A) != none
		|| XComMapEdSpawner(A) != none || XComMapEdHider(A) != none || XComMapEdWall(A) != none
		|| XComMapEdLevelPiece(A) != none || XComMapEdCopier(A) != none || XComMapEdTileSeeds(A) != none
		|| XComMapEdDoor(A) != none)
		return false;
	// Nor anything else of this package: door copies are doors to the class test below, and run 27's hider took five
	// of them under the map (F-36).
	if (A.Class.Outer != none && A.Class.Outer.Name == 'XComMapEd')
		return false;
	// Base-map pieces a copier moved into the new layout (doors, ladders).
	if (A.Tag == 'XComMapEdMoved')
		return false;
	if (KeepNames.Find(A.Name) != INDEX_NONE)
		return false;
	if (Light(A) != none)
		return bHideLights;
	return StaticMeshActor(A) != none || FracturedStaticMeshActor(A) != none || XComInteractiveLevelActor(A) != none
		|| SkeletalMeshActor(A) != none || KActor(A) != none || KAsset(A) != none || Emitter(A) != none
		|| DecalActor(A) != none || LensFlareSource(A) != none;
}

function HideAll()
{
	local XComWorldData World;
	local Actor A;
	local box B, AB;
	local vector C;
	local int nKeptGround, nVolumes, nNoBounds;
	local string Names;

	World = class'XComWorldData'.static.GetWorldData();
	B = HideBox();
	foreach AllActors(class'Actor', A)
	{
		if (bHideVolumes && (XComBuildingVolume(A) != none || XComFloorVolume(A) != none || (bHideCursorVolumes && XComCursorVolume(A) != none))
			&& A.Outer == WorldInfo.Outer && InBox(A.Location, B) && KeepNames.Find(A.Name) == INDEX_NONE)
		{
			DisableVolume(A);
			nVolumes++;
			Names = Names @ A.Name;
			continue;
		}
		if (!IsHideable(A))
			continue;
		if (AlsoHide.Find(A.Name) == INDEX_NONE)
		{
			if (Emitter(A) != none || DecalActor(A) != none || Light(A) != none || LensFlareSource(A) != none)
			{
				// Placed by location. Only decals can count as ground; effects and lights never do.
				C = A.Location;
				AB.Min = C;
				AB.Max = C;
				if (DecalActor(A) == none)
					AB.Max.Z = C.Z + KeepGroundHeight;
			}
			else if (ActorBox(A, AB))
				C = (AB.Min + AB.Max) / 2.0;
			else
			{
				// No bounds: placed by its location, and never counted as ground.
				C = A.Location;
				AB.Min = C;
				AB.Max = C + vect(0, 0, 1) * KeepGroundHeight;
				if (InBox(C, B))
				{
					nNoBounds++;
					`log("XComMapEd:" @ self @ A @ "(" $ A.Class.Name $ ") has no component bounds; using its location" @ C);
				}
			}
			if (!InBox(C, B))
				continue;
			if (AB.Max.Z < B.Min.Z + KeepGroundHeight)
			{
				`log("XComMapEd:" @ self @ "kept" @ A @ "(" $ A.Class.Name $ ") on the ground, box z" @ AB.Min.Z @ "to" @ AB.Max.Z);
				nKeptGround++;
				continue;
			}
		}
		HideActor(A, World);
	}
	`log("XComMapEd:" @ self @ "hid" @ HiddenActors.Length @ "actors in" @ B.Min @ "to" @ B.Max $ ", kept" @ nKeptGround @ "on the ground," @ nNoBounds @ "without bounds; took" @ nVolumes @ "volumes out:" $ Names);
}

/** " (label)" for AlsoHide entry i's log lines, when the spec gave labels. */
function string TargetLabel(int i)
{
	return (i < TargetLabels.Length && TargetLabels[i] != "") ? "(" $ TargetLabels[i] $ ")" : "";
}

/** Exact targets: hides the base map's actors named in AlsoHide, each where it stands, and logs any it can't find. */
function HideTargets()
{
	local XComWorldData World;
	local Actor A;
	local box AB;
	local array<int> Found;
	local int i, n;

	World = class'XComWorldData'.static.GetWorldData();
	Found.Length = AlsoHide.Length;
	foreach AllActors(class'Actor', A)
	{
		if (A.Outer != WorldInfo.Outer)
			continue;
		i = AlsoHide.Find(A.Name);
		if (i == INDEX_NONE)
			continue;
		Found[i] = 1;
		if (!IsHideable(A))
		{
			`log("XComMapEd:" @ self @ "WARNING: can't hide" @ A @ "(" $ A.Class.Name $ ")" @ TargetLabel(i));
			continue;
		}
		if (!ActorBox(A, AB))
		{
			AB.Min = A.Location - vect(48, 48, 32);
			AB.Max = A.Location + vect(48, 48, 32);
		}
		TargetBoxes.AddItem(AB);
		HideActor(A, World);
		n++;
	}
	for (i = 0; i < AlsoHide.Length; i++)
		if (Found[i] == 0)
			`log("XComMapEd:" @ self @ "WARNING: no" @ AlsoHide[i] @ "in the base map" @ TargetLabel(i));
	`log("XComMapEd:" @ self @ "hid" @ n @ "of" @ AlsoHide.Length @ "exact targets");
}

function HideActor(Actor A, XComWorldData World)
{
	local PrimitiveComponent P;
	local FracturedStaticMeshComponent F;
	local XComFracLevelActor G;
	local array<byte> Vis;
	local int i;

	// The rebuild's occupancy step goes through the cover interface. Level and fractured actors default to
	// bAlwaysConsiderForCover, and with it they still filled their tiles in run 2 with no collision (F-22).
	if (XComLevelActor(A) != none)
	{
		XComLevelActor(A).SetPrimitiveHidden(true);
		XComLevelActor(A).bAlwaysConsiderForCover = false;
		XComLevelActor(A).bIgnoreForCover = true;
		// Line of sight ignores collision and follows this flag (run 3: units couldn't see across the old walls, and
		// XComWorldData.WorldTrace still hit the hidden front wall; F-25).
		XComLevelActor(A).VisibilityBlockingData.bBlockUnitVisibility = false;
	}
	else if (XComFracLevelActor(A) != none)
	{
		G = XComFracLevelActor(A);
		G.SetPrimitiveHidden(true);
		G.bAlwaysConsiderForCover = false;
		G.bIgnoreForCover = true;
		G.VisibilityBlockingData.bBlockUnitVisibility = false;
		// Destroyed columns are how a wall blown open stops filling its tiles.
		if (bHideFragments)
			for (i = 0; i < G.FragmentColumns.Length; i++)
			{
				G.FragmentColumns[i].bDamaged = true;
				G.FragmentColumns[i].bDestroyed = true;
			}
	}
	A.SetHidden(true);
	A.SetCollision(false, false);
	foreach A.AllOwnedComponents(class'PrimitiveComponent', P)
	{
		P.SetHidden(true);
		P.SetActorCollision(false, false);
		P.SetTraceBlocking(false, false);
		P.SetBlockRigidBody(false);
		F = FracturedStaticMeshComponent(P);
		if (bHideFragments && F != none)
		{
			Vis.Length = F.GetNumFragments();
			for (i = 0; i < Vis.Length; i++)
				Vis[i] = 0;
			F.SetVisibleFragments(Vis);
		}
	}
	if (Light(A) != none && Light(A).LightComponent != none)
		Light(A).LightComponent.SetEnabled(false);
	if (Emitter(A) != none && Emitter(A).ParticleSystemComponent != none)
		Emitter(A).ParticleSystemComponent.DeactivateSystem();
	// A door: as the game's own OnDisableInteractiveActor does, so the rebuild's interaction step leaves it out (run 3
	// still offered "open door" where a hidden door was). Its points are removed again after the rebuild.
	if (XComInteractiveLevelActor(A) != none)
	{
		A.GotoState('_Inactive');
		if (World != none)
			World.RemoveInteractionPoints(XComInteractiveLevelActor(A));
	}
	// The rebuild gives a door kick links and a ladder a climb wherever they stand, hidden or not (EXP-07 runs 18 to
	// 20: a soldier kicked the hidden double door inside the new block; the old north side stayed climbable). So
	// hidden ones go under the map, out of every tile.
	if ((XComInteractiveLevelActor(A) != none || XComLadder(A) != none) && HideInPlace.Find(A.Name) == INDEX_NONE)
	{
		A.SetCollision(false, false);
		A.SetLocation(A.Location - vect(0, 0, 4000));
		`log("XComMapEd:" @ self @ "moved hidden" @ A @ "under the map, to" @ A.Location);
	}
	HiddenActors.AddItem(A);
	`log("XComMapEd:" @ self @ "hid" @ A @ "(" $ A.Class.Name $ ") at" @ A.Location @ "visible" @ !A.bHidden);
	if (FlagsLogged.Find(A.Class.Name) == INDEX_NONE)
	{
		FlagsLogged.AddItem(A.Class.Name);
		LogFlags(A);
	}
}

/** The collision flags left on A and its components after hiding, once per class (EXP-07 run 3). */
function LogFlags(Actor A)
{
	local PrimitiveComponent P;
	local string S;

	foreach A.AllOwnedComponents(class'PrimitiveComponent', P)
		S = S @ "[" $ P.Class.Name @ "collide" @ P.CollideActors @ "block" @ P.BlockActors @ "zero" @ P.BlockZeroExtent
			@ "nonzero" @ P.BlockNonZeroExtent @ "rigid" @ P.BlockRigidBody @ "hidden" @ P.HiddenGame $ "]";
	`log("XComMapEd:" @ self @ "flags of" @ A @ "(" $ A.Class.Name $ ") after hiding: static" @ A.bStatic @ "collide" @ A.bCollideActors
		@ "block" @ A.bBlockActors @ "hidden" @ A.bHidden $ S);
}

/** Traces ProbeStart to ProbeEnd, as a line and as a unit-sized box, and logs what each hits first. */
function Probe(string When)
{
	local vector HitLocation, HitNormal;
	local Actor HitActor;
	local XComWorldData World;

	if (ProbeStart == ProbeEnd)
		return;
	HitActor = Trace(HitLocation, HitNormal, ProbeEnd, ProbeStart, true);
	`log("XComMapEd:" @ self @ "probe" @ When $ ": line hits" @ HitActor @ "at" @ HitLocation);
	HitActor = Trace(HitLocation, HitNormal, ProbeEnd, ProbeStart, true, vect(24, 24, 24));
	`log("XComMapEd:" @ self @ "probe" @ When $ ": box hits" @ HitActor @ "at" @ HitLocation);
	World = class'XComWorldData'.static.GetWorldData();
	HitActor = none;
	if (World != none && World.WorldTrace(ProbeStart, ProbeEnd, HitLocation, HitNormal, HitActor))
		`log("XComMapEd:" @ self @ "probe" @ When $ ": WorldTrace hits" @ HitActor @ "at" @ HitLocation);
	else
		`log("XComMapEd:" @ self @ "probe" @ When $ ": WorldTrace hits nothing");
}

function DisableVolume(Actor A)
{
	local PrimitiveComponent P;

	A.SetCollision(false, false);
	foreach A.AllOwnedComponents(class'PrimitiveComponent', P)
		P.SetActorCollision(false, false);
	`log("XComMapEd:" @ self @ "took" @ A @ "(" $ A.Class.Name $ ") out of play, at" @ A.Location);
}

function RebuildTiles()
{
	local XComWorldData World;
	local vector P, E;
	local int i;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
	{
		`log("XComMapEd:" @ self @ "has no world data to rebuild yet; retrying");
		SetTimer(1.0, false, 'RebuildTiles');
		return;
	}
	if (bExactTargets)
	{
		World.SetRebuildTileProcessRate(100000);
		for (i = 0; i < TargetBoxes.Length; i++)
		{
			P = (TargetBoxes[i].Min + TargetBoxes[i].Max) / 2.0;
			E = (TargetBoxes[i].Max - TargetBoxes[i].Min) / 2.0 + vect(1, 1, 0) * RebuildPad + vect(0, 0, 64);
			World.RebuildTileDataExtents(P, E);
		}
		`log("XComMapEd:" @ self @ "rebuilding tile data around each of" @ TargetBoxes.Length @ "hidden targets, pad" @ RebuildPad);
		return;
	}
	if (bFullWorldBuild)
		FullWorldBuild(World);
	P = Location;
	E = HideExtent + vect(1, 1, 0) * RebuildPad + vect(0, 0, 64);
	World.SetRebuildTileProcessRate(100000);
	World.RebuildTileDataExtents(P, E);
	`log("XComMapEd:" @ self @ "rebuilding tile data around" @ P @ "extent" @ E);
}

/** The full build over the level volume (the log's timestamps show how long it took). */
function FullWorldBuild(XComWorldData World)
{
	local XComLevelVolume V, Found;
	local int n;

	foreach AllActors(class'XComLevelVolume', V)
	{
		n++;
		if (Found == none)
			Found = V;
	}
	if (Found == none)
	{
		`log("XComMapEd:" @ self @ "WARNING: no XComLevelVolume; no full world data build");
		return;
	}
	`log("XComMapEd:" @ self @ "full world data build over" @ Found @ "(" $ n @ "level volume(s)); census before:" @ Census());
	World.BuildWorldData(Found);
	`log("XComMapEd:" @ self @ "full world data build done; census after:" @ Census());
}

function WaitForTiles()
{
	local XComWorldData World;
	local Actor A;

	World = class'XComWorldData'.static.GetWorldData();
	if (World != none && World.IsRebuildingTiles())
		return;
	ClearTimer('WaitForTiles');
	if (World != none)
		World.SetRebuildTileProcessRate(16);   // XComWorldData.DEFAULT_REBUILD_TILE_RATE
	foreach HiddenActors(A)
		if (XComInteractiveLevelActor(A) != none && World != none)
			World.RemoveInteractionPoints(XComInteractiveLevelActor(A));
	if (bExactTargets)
	{
		`log("XComMapEd:" @ self @ "tile rebuild finished");
		return;
	}
	`log("XComMapEd:" @ self @ "tile rebuild finished; census after:" @ Census());
	LogGroundRows("after");
	Probe("after the rebuild");
}

/**
 * Hides again anything that has come back into view, all mission long. The building cutaway still shows the effects
 * its floor volumes list now and then, though its volumes are switched off (run 4: five of the bar's emitters, about
 * once a quarter-minute; F-27). Logs the first 20 times.
 */
function CheckHidden()
{
	local Actor A;
	local int n;

	foreach HiddenActors(A)
	{
		if (A != none && !A.bHidden)
		{
			if (Checks < 20)
				`log("XComMapEd:" @ self @ "WARNING:" @ A @ "was shown again; hiding it again");
			A.SetHidden(true);
			if (Emitter(A) != none && Emitter(A).ParticleSystemComponent != none)
				Emitter(A).ParticleSystemComponent.DeactivateSystem();
			n++;
		}
	}
	if (n > 0 && Checks < 20)
		`log("XComMapEd:" @ self @ "hid" @ n @ "actors again");
	if (++Checks == 2 && !bExactTargets)
		`log("XComMapEd:" @ self @ "census after the level start:" @ Census());
}

/**
 * Per height level over the box, from its bottom: "Z32 floor 120 occupied 30 high 12 low 8 of 510", counted at tile
 * centres. Tiles are 96 units across and 64 high, counted from XComWorldData.WorldBounds.Min.
 */
function string Census()
{
	local XComWorldData World;
	local vector O, P;
	local box B;
	local int tx, ty, tz, x, y, z, z0, nFloor, nOcc, nHigh, nLow, m;
	local string S;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return "no world data";
	B = HideBox();
	O = World.WorldBounds.Min;
	z0 = Max(0, FFloor((B.Min.Z - O.Z) / 64.0));
	for (tz = z0; O.Z + tz * 64.0 < B.Max.Z; tz++)
	{
		nFloor = 0; nOcc = 0; nHigh = 0; nLow = 0; m = 0;
		P.Z = O.Z + (tz + 0.5) * 64.0;
		for (tx = FFloor((B.Min.X - O.X) / 96.0); O.X + tx * 96.0 < B.Max.X; tx++)
		{
			for (ty = FFloor((B.Min.Y - O.Y) / 96.0); O.Y + ty * 96.0 < B.Max.Y; ty++)
			{
				P.X = O.X + (tx + 0.5) * 96.0;
				P.Y = O.Y + (ty + 0.5) * 96.0;
				World.GetTileCoordinatesFromPosition(P, x, y, z);
				m++;
				if (World.IsPositionOnFloor(P)) nFloor++;
				if (World.IsTileOccupied(x, y, z)) nOcc++;
				if (World.IsLocationHighCover(P)) nHigh++;
				else if (World.IsLocationLowCover(P)) nLow++;
			}
		}
		S = S $ (S == "" ? "" : "; ") $ "Z" $ int(P.Z) @ "floor" @ nFloor @ "occupied" @ nOcc @ "high" @ nHigh @ "low" @ nLow @ "of" @ m;
	}
	return S;
}

/**
 * One log line per tile row of the box, at the level of a unit standing 16 units above the bottom of the box: '#'
 * occupied, ':' cover, '.' floor, ' ' none.
 */
function LogGroundRows(string When)
{
	local XComWorldData World;
	local vector O, P;
	local box B;
	local int tx, ty, tx0, x, y, z;
	local string S;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	B = HideBox();
	O = World.WorldBounds.Min;
	tx0 = FFloor((B.Min.X - O.X) / 96.0);
	P.Z = O.Z + (FFloor((B.Min.Z + 16.0 - O.Z) / 64.0) + 0.5) * 64.0;   // the level a unit standing on the ground is in
	for (ty = FFloor((B.Min.Y - O.Y) / 96.0); O.Y + ty * 96.0 < B.Max.Y; ty++)
	{
		S = "";
		for (tx = tx0; O.X + tx * 96.0 < B.Max.X; tx++)
		{
			P.X = O.X + (tx + 0.5) * 96.0;
			P.Y = O.Y + (ty + 0.5) * 96.0;
			World.GetTileCoordinatesFromPosition(P, x, y, z);
			if (World.IsTileOccupied(x, y, z)) S = S $ "#";
			else if (World.IsLocationHighCover(P) || World.IsLocationLowCover(P)) S = S $ ":";
			else if (World.IsPositionOnFloor(P)) S = S $ ".";
			else S = S $ " ";
		}
		`log("XComMapEd:" @ self @ "ground row" @ When @ ty @ "from tile" @ tx0 $ ": [" $ S $ "]");
	}
}

defaultproperties
{
	bHidden=true
	HideExtent=(X=512,Y=512,Z=256)
	KeepGroundHeight=40
	bHideVolumes=true
	bHideFragments=true
	RebuildPad=96
}
