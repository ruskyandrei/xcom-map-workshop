/**
 * Copies pieces the base map placed (walls, roofs, floors, windows, props: SourceNames) to a new place at load
 * (EXP-07). The pieces are moved as one group: the point Pivot of the sources lands on this actor's location, and
 * the group turns by this actor's yaw (in 90° steps, so that the copies stay on the tile grid). A whole block of the
 * bar, whose pieces share one pivot, can be copied in one go.
 *
 * - Fractured pieces (XComFracLevelActor, XComDecoFracLevelActor) become XComMapEdWall, with the source's baked
 *   fragment columns moved along.
 * - Destructibles (windows, door frames, props) become XComMapEdDestructible.
 * - Plain level meshes (XComLevelActor, StaticMeshActor) become XComMapEdLevelPiece.
 * - Doors (XComInteractiveLevelActor) and ladders (XComLadder) are moved, not copied: the base map's own actor goes
 *   to its place in the new layout, keeping its name (so saves find it, F-15). Each can be used once. A door's
 *   interaction points at the old place are removed; the tile rebuild adds them at the new one. Moved pieces are
 *   tagged XComMapEdMoved, and hiders leave them alone.
 * - With bCopyDoors, doors are copied instead (XComMapEdDoor), so the base map keeps its own: the L layout's wing
 *   copies the bar's doors while the bar still stands. The tile rebuild over the copies gives them their interaction
 *   points.
 * - Pieces in PrePlaced already stand in their new place: patchtool baked them there in the lab's copy of the map
 *   (a bake object). A ladder needs that, as the game re-makes its climb links from where it stood at load (F-30).
 *   They are treated as moved pieces (tag, building caches, logs), but not moved again.
 * - Anything else is not copied, and is logged.
 *
 * With BuildingName, the copies join the patch's own building volume (patchtool places it, with its floor volumes,
 * from the spec's building field). The cutaway hides and shows a building's pieces floor by floor from its floors'
 * cached actors, which the editor bakes; RebuildCachedActors at run time finds none of our copies (EXP-07 run 13,
 * F-31). So each copy gets the entry its source has in the base map's baked caches (the same floor and cutdown
 * floor), and a moved piece also leaves the base map's caches.
 *
 * All copies are lit dynamically. The tile data over the copies is rebuilt at once, before the level start places
 * anything. Copy objects must come before any hide object in a patch, so that they read the sources before the
 * hider changes them.
 *
 * Not done yet: saves. A save keeps only damaged copies and recreates them bare on load (findings register F-17).
 *
 * Absolute poses (bAbsolutePoses, the editor's compiler, E3): each copy stands at its own PoseLocations(i) with its
 * own PoseRotations(i), a full rotator (pitch, yaw and roll), rather than moving with the group from Pivot by this
 * actor's yaw. A source may be named more than once, for two copies of one piece. Each copy's own box is rebuilt,
 * not one box around them all, and each copy's pose is logged at load and 5 s later, with how far it is from the
 * pose asked for. Fractured pieces, doors and ladders are not placed this way yet (their columns, interaction points
 * and climbs follow the group transform): they are logged and left alone.
 */
class XComMapEdCopier extends Actor
	placeable;

/** The pieces to copy, by their names in the base map's level (e.g. XComDecoFracLevelActor_10). */
var() array<name> SourceNames;
/** The point of the sources that lands on this actor's location. */
var() vector Pivot;
/** Copy doors as XComMapEdDoor instead of moving the base map's own (EXP-07 L layout). */
var() bool bCopyDoors;
/**
 * Copy ladders as plain meshes (XComMapEdLevelPiece) with no collision, instead of moving the base map's own: the
 * visible ladder. The climb comes from a ladder placed in the patch itself (patchtool's ladder object), since the
 * game makes climb links only for real XComLadder actors (F-30). Avoid it: the mesh copy made the ladder's foot tile
 * unwalkable, so the climb was never made (EXP-07 run 29, F-39). A visible ladder object does both.
 */
var() bool bCopyLadders;
/**
 * Seconds after load to rebuild, once more and last, the foot tile of every ladder standing by the copies (0: not),
 * logging what the climb needs there. The rebuild makes a ladder's climb when it rebuilds the foot tile, and a later
 * rebuild of the top tile drops the way down (research/native-code-notes.md, "How ladder links are made").
 */
var() float LadderFootRebuild;
/**
 * Logs the 3D cursor's position and tile whenever its tile changes, so that the user can point at a spot in the game
 * and the spot can be read back from the log (EXP-07 run 31: where to put things).
 */
var() bool bLogCursor;
var transient int CursorX, CursorY, CursorZ;
/**
 * Seconds after load to rebuild the tile data over the copies once more, when every copy, door and floor of the patch
 * exists (0: not). A ladder's climb and a door's links are made when the rebuild processes their tiles, from what
 * stands there at that moment (EXP-07 run 28).
 */
var() float LateRebuild;
/** Scales each copy's DrawScale3D, per axis (0,0,0: not): a 13-tile floor laid over a 12-tile room (EXP-07 run 29). */
var() vector CopyScale;
/** Sources (also in SourceNames) that already stand in their new place, baked into the map: not moved again. */
var() array<name> PrePlaced;
/** Tiles around the copies that are rebuilt as well. */
var() float RebuildPad;
/** Fractured sources to copy as plain meshes (XComMapEdLevelPiece) instead: no fragments, drawn as a static mesh (EXP-07 lighting test). */
var() array<name> AsLevelPiece;
/** If above 0, spawns one movable point light (XComMapEdLight) at the world point TestLightAt, for a lighting test. */
var() float TestLightRadius;
var() float TestLightBrightness;
var() vector TestLightAt;
/** The class fractured pieces are copied as (EXP-07 run 4 lighting variants: XComMapEdWall or a subclass). */
var() class<XComMapEdWall> WallClass;
/** Lighting variants for the wall copies (EXP-07 run 4): no environment shadowing; the lit overlay while whole. */
var() bool bWallNoEnvShadow;
var() bool bWallOverlay;
/** EXP-07 run 7 tile test (F-29): wall copies are not world geometry. */
var() bool bWallNoWorldGeometry;
/**
 * EXP-07 run 8 tile test (F-29): before the rebuild, every tile the copies cross above the ground is marked as water
 * (XComWorldData.SetIsWaterTile), so that it is no longer empty in the tile data; 5 s after load, once logged, the
 * marks are cleared and the tiles rebuilt again, and logged once more 5 s later.
 */
var() bool bWaterTiles;
var transient array<int> WaterX, WaterY, WaterZ;
/**
 * EXP-07 run 9 tile test (F-29): sets XComWorldData.UpdateBuildHeightTiles (read only by native code) before the
 * rebuild. The guess: a rebuild only goes up a tile column as far as the baked geometry reached.
 */
var() bool bUpdateBuildHeightTiles;
/** Optional line traced 5 s after load, to show what blocks there (line, box and XComWorldData.WorldTrace). */
var() vector ProbeStart, ProbeEnd;
/** The patch's building volume for the copies: its floor caches are rebuilt once the copies exist. */
var() name BuildingName;
/**
 * With BuildingName, the floor (index into the building's Floors) that every copy joins in its floor caches, cutdown
 * floor 0, in place of its source's entries (-1: the sources' entries). A floor slab copied up into a storey its source
 * never stood on (EXP-08 run 3: the block's second floor) must join that storey to be cut away with it.
 */
var() int BuildingFloor;
/** Log the tile data along each copy 5 s after load (EXP-07 step 3a). */
var() bool bLogTiles;
/** Pairs of points (start, end): the A* path between each pair is logged at load and 5 s later (EXP-07 ladders). */
var() array<vector> PathProbes;
/** Points whose floor tile is logged at load and 5 s later (EXP-07 ladders: is there a floor at the top?). */
var() array<vector> FloorProbes;
/** Log every XComLadder in the world (level, place, flags, height) at load and 5 s later. */
var() bool bLogLadders;
/** Log every pawn's building and floor volumes whenever they change, every 2 s (EXP-07 cutaway). */
var() bool bProbeIndoor;
var transient array<Pawn> ProbePawns;
var transient array<string> ProbeLast;

/** Place each copy at its own pose (PoseLocations, PoseRotations) instead of moving the group (see above). */
var() bool bAbsolutePoses;
/** With bAbsolutePoses: copy i's location and full rotation, one per SourceNames entry. */
var() array<vector> PoseLocations;
var() array<rotator> PoseRotations;
/** With bAbsolutePoses: a label per copy for the log (the editor's output name), to match each logged pose. */
var() array<string> CopyLabels;

/**
 * How a destructible copy's light environment draws its light (XComMapEdDestructible.SetLighting): Mode 0 is the
 * engine's default, mode 1 the game's door setting (an SH light); bBooleanShadow shadows the map's lights by the
 * static world with an on/off test. EXP-14 runs 5 and 7 saw no clear gain from either; kept for trials.
 */
struct CopyLight
{
	var() byte Mode;
	var() bool bBooleanShadow;
};
/** By copy index. Copies past its end keep their light environment as it is. */
var() array<CopyLight> CopyLights;
/**
 * Break groups (the editor's groups with "Break together"): by copy index, the group each copy breaks with (0: none).
 * BreakOriginals names the base map's own pieces, left in place, that break with group BreakOriginalGroups(i). When
 * one piece of a group is damaged or destroyed, the others are put in the same state (LinkBreakGroups).
 */
var() array<int> BreakGroups;
var() array<name> BreakOriginals;
var() array<int> BreakOriginalGroups;
/**
 * Copies of the map's baked pieces leave out a sky light that lights units only (XComMapEdSkyFree, F-52), unless this
 * is set. Copied doors aren't registered: the map lights its own doors the same live way. Once a piece registers, the
 * swap is the map's: units take that sky light on Gameplay_1, and doors (the map's and copied ones) lose it.
 */
var() bool bKeepSkyLight;

var transient array<Actor> Sources, Copies;
/** Base-map pieces moved rather than copied (doors, ladders), and where they stood. */
var transient array<Actor> Moved;
var transient array<vector> MovedFrom;

simulated event PostBeginPlay()
{
	local Actor A;
	local int i, n;

	super.PostBeginPlay();
	if (!bAbsolutePoses && Rotation.Yaw % 16384 != 0)
		`log("XComMapEd:" @ self @ "WARNING: yaw" @ Rotation.Yaw @ "is not a multiple of 90 degrees; the copies will be off the tile grid");
	if (bAbsolutePoses && (PoseLocations.Length != SourceNames.Length || PoseRotations.Length != SourceNames.Length))
	{
		`log("XComMapEd:" @ self @ "ERROR:" @ SourceNames.Length @ "sources but" @ PoseLocations.Length @ "pose locations and" @ PoseRotations.Length
			@ "pose rotations; copying nothing");
		return;
	}
	Sources.Length = SourceNames.Length;
	Copies.Length = SourceNames.Length;
	// Every entry naming the actor gets it: with absolute poses a source can be copied more than once.
	foreach AllActors(class'Actor', A)
	{
		if (A.Outer != WorldInfo.Outer)
			continue;
		for (i = 0; i < SourceNames.Length; i++)
			if (SourceNames[i] == A.Name)
				Sources[i] = A;
	}
	for (i = 0; i < Sources.Length; i++)
	{
		if (Sources[i] == none)
			`log("XComMapEd:" @ self @ "WARNING: no" @ SourceNames[i] @ "in the base map" @ Label(i));
		else
		{
			Copies[i] = CopyOne(i);
			if (Copies[i] != none)
				n++;
		}
	}
	// Columns last, once every copy exists, so a wall's columns can name the copied windows and pictures.
	for (i = 0; i < Copies.Length; i++)
		if (XComMapEdWall(Copies[i]) != none)
		{
			XComMapEdWall(Copies[i]).CopyColumns(XComFracLevelActor(Sources[i]), Pivot, Location, MakeRotator(0, Rotation.Yaw, 0), Sources, Copies);
			`log("XComMapEd:" @ self @ Copies[i] @ "has" @ XComMapEdWall(Copies[i]).FragmentColumns.Length @ "fragment columns from" @ Sources[i]);
		}
	if (bAbsolutePoses)
	{
		`log("XComMapEd:" @ self @ "copied" @ n @ "of" @ SourceNames.Length @ "pieces, each to its own pose");
		LogPoses("at load");
	}
	else
		`log("XComMapEd:" @ self @ "copied" @ n @ "of" @ SourceNames.Length @ "pieces from pivot" @ Pivot @ "to" @ Location @ "yaw" @ Rotation.Yaw
			@ "(" $ Moved.Length @ "of them moved)");
	EnableCutout();
	for (i = 0; i < Copies.Length; i++)
	{
		LightCopy(i);
		LeaveOutSkyLight(Copies[i]);
	}
	LinkBreakGroups();
	if (BuildingName != '')
	{
		LogSourceFloors();
		SetupBuilding("at load");
	}
	LogCopiesLighting();
	SetTimer(5.0, false, 'LogLightingLater');
	if (TestLightRadius > 0)
		SpawnTestLight();
	if (bWaterTiles)
		MarkWaterTiles(true);
	if (bUpdateBuildHeightTiles)
		SetBuildHeightFlag();
	RebuildTiles();
	SetTimer(0.01, true, 'WaitForTiles');
	if (LateRebuild > 0)
		SetTimer(LateRebuild, false, 'RebuildTiles');
	if (LadderFootRebuild > 0)
		SetTimer(LadderFootRebuild, false, 'RebuildLadderFeet');
	if (bLogCursor)
	{
		CursorX = -1;
		SetTimer(0.5, true, 'LogCursor');
	}
	LogPathProbes("at load");
	LogFloorProbes("at load");
	if (bLogLadders)
		LogLadders("at load");
	if (bProbeIndoor)
		SetTimer(2.0, true, 'ProbeIndoor');
	if (BuildingName != '')
	{
		RegisterBuilding();
		SetTimer(2.0, true, 'RegisterBuilding');
	}
}

/** The A* path between each pair of PathProbes: a ladder whose links work gives a short climb from bottom to top. */
function LogPathProbes(string When)
{
	local XComWorldData World;
	local array<TTile> Path;
	local vector A, B;
	local int i, j;
	local string S;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	for (i = 0; i + 1 < PathProbes.Length; i += 2)
	{
		A = PathProbes[i];
		B = PathProbes[i + 1];
		Path.Length = 0;
		World.GetAStarPath(Path, A, B, false, true);
		S = "";
		for (j = 0; j < Path.Length && j < 40; j++)
			S = S @ "(" $ Path[j].X $ "," $ Path[j].Y $ "," $ Path[j].Z $ ")";
		`log("XComMapEd:" @ self @ "path" @ When @ "from" @ A @ "to" @ B $ ":" @ Path.Length @ "tiles" $ S);
	}
}

/** Each FloorProbes point: on a floor or not, its floor tile and floor height. */
function LogFloorProbes(string When)
{
	local XComWorldData World;
	local vector P;
	local int i, X, Y, Z;
	local bool bOn, bTile;
	local float FZ;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	for (i = 0; i < FloorProbes.Length; i++)
	{
		P = FloorProbes[i];
		bOn = World.IsPositionOnFloor(P);
		X = -1; Y = -1; Z = -1;
		bTile = World.GetFloorTileForPosition(P, X, Y, Z, false);
		FZ = World.GetFloorZForPosition(P, false);
		`log("XComMapEd:" @ self @ "floor" @ When @ "at" @ P $ ": on floor" @ bOn @ "| floor tile" @ bTile @ "(" $ X $ "," $ Y $ "," $ Z $ ") | floor z" @ FZ);
	}
}

/** Every ladder in the world, with what might decide whether the rebuild gives it a climb. */
function LogLadders(string When)
{
	local XComLadder L;

	foreach AllActors(class'XComLadder', L)
		`log("XComMapEd:" @ self @ "ladder" @ When @ L @ "in" @ L.Outer @ "at" @ L.Location @ "yaw" @ L.Rotation.Yaw @ "height" @ L.GetHeight()
			@ "type" @ L.eType @ "tag" @ L.Tag @ "hidden" @ L.bHidden @ "collide" @ L.bCollideActors @ "block" @ L.bBlockActors
			@ "static" @ L.bStatic @ "cover always/ignore" @ L.bAlwaysConsiderForCover $ "/" $ L.bIgnoreForCover);
}

/** Each pawn's (and the cursor's) building and floor volumes, logged when they change. */
function ProbeIndoor()
{
	local XComPawn P;
	local XComBuildingVolume Found;
	local string S;
	local int i, k;

	Found = FindBuilding();
	foreach WorldInfo.AllPawns(class'XComPawn', P)
	{
		if (P.IndoorInfo == none)
			continue;
		S = "building" @ P.IndoorInfo.CurrentBuildingVolume @ "floor volumes";
		for (i = 0; i < P.IndoorInfo.CurrentFloorVolumes.Length; i++)
			S = S @ P.IndoorInfo.CurrentFloorVolumes[i];
		if (Found != none)
			S = S @ "| inside" @ Found @ Found.EncompassesPoint(P.Location);
		k = ProbePawns.Find(P);
		if (k == INDEX_NONE)
		{
			ProbePawns.AddItem(P);
			ProbeLast.AddItem("");
			k = ProbePawns.Length - 1;
		}
		if (ProbeLast[k] != S)
		{
			ProbeLast[k] = S;
			`log("XComMapEd:" @ self @ "indoor:" @ P @ "at" @ P.Location @ S);
		}
	}
}

/** What touches the patch building's floor volumes. */
function LogFloorTouching()
{
	local XComBuildingVolume Found;
	local Actor A;
	local string S;
	local int i, j;

	Found = FindBuilding();
	if (Found == none)
		return;
	for (i = 0; i < Found.Floors.Length; i++)
		for (j = 0; j < Found.Floors[i].FloorVolumes.Length; j++)
		{
			S = "";
			foreach Found.Floors[i].FloorVolumes[j].TouchingActors(class'Actor', A)
				S = S @ A;
			`log("XComMapEd:" @ self @ "floor" @ i @ Found.Floors[i].FloorVolumes[j] @ "collide" @ Found.Floors[i].FloorVolumes[j].bCollideActors
				@ "touched by:" $ S);
		}
}

/** " (label)" for copy i's log lines, when the spec gave labels. */
function string Label(int i)
{
	return (i < CopyLabels.Length && CopyLabels[i] != "") ? "(" $ CopyLabels[i] $ ")" : "";
}

/** Where copy i of source S goes: its own pose, or moved with the group from Pivot and turned by this actor's yaw. */
function TargetPose(int i, Actor S, out vector P, out rotator R)
{
	if (bAbsolutePoses)
	{
		P = PoseLocations[i];
		R = PoseRotations[i];
		return;
	}
	P = Location + ((S.Location - Pivot) >> MakeRotator(0, Rotation.Yaw, 0));
	R = S.Rotation;
	R.Yaw += Rotation.Yaw;
}

/** How far apart two rotator components are, in rotation units, over whole turns (70000 and 4464 are the same). */
static function int TurnDiff(int A, int B)
{
	local int D;

	D = (A - B) & 65535;
	return D > 32768 ? 65536 - D : D;
}

/** Each copy's pose against the pose asked for (absolute poses): the largest distance and rotator difference. */
function LogPoses(string When)
{
	local int i, dR, Worst;
	local float dP, WorstP;
	local Actor C;

	for (i = 0; i < Copies.Length; i++)
	{
		C = Copies[i];
		if (C == none)
			continue;
		dP = VSize(C.Location - PoseLocations[i]);
		dR = Max(Max(TurnDiff(C.Rotation.Pitch, PoseRotations[i].Pitch), TurnDiff(C.Rotation.Yaw, PoseRotations[i].Yaw)),
			TurnDiff(C.Rotation.Roll, PoseRotations[i].Roll));
		WorstP = FMax(WorstP, dP);
		Worst = Max(Worst, dR);
		`log("XComMapEd:" @ self @ "pose" @ When @ C @ Label(i) @ "from" @ SourceNames[i] @ "at (" $ C.Location.X $ "," $ C.Location.Y $ "," $ C.Location.Z
			$ ") rotation (" $ C.Rotation.Pitch $ "," $ C.Rotation.Yaw $ "," $ C.Rotation.Roll $ ") scale" @ C.DrawScale @ C.DrawScale3D
			@ "| off by" @ dP @ "units," @ dR @ "rotation units | hidden" @ C.bHidden @ "collide" @ C.bCollideActors);
	}
	`log("XComMapEd:" @ self @ "poses" @ When $ ": at most" @ WorstP @ "units and" @ Worst @ "rotation units from the poses asked for");
}

function Actor CopyOne(int i)
{
	local vector P;
	local rotator R;
	local Actor C, S;

	S = Sources[i];
	if (bAbsolutePoses && (XComFracLevelActor(S) != none || XComInteractiveLevelActor(S) != none || XComLadder(S) != none))
	{
		`log("XComMapEd:" @ self @ "can't place" @ S @ "(" $ S.Class.Name $ ") by an absolute pose yet" @ Label(i) $ "; not copied");
		return none;
	}
	if (PrePlaced.Find(S.Name) != INDEX_NONE)
	{
		Moved.AddItem(S);
		MovedFrom.AddItem(S.Location);
		S.Tag = 'XComMapEdMoved';
		`log("XComMapEd:" @ self @ S @ "(" $ S.Class.Name $ ") was baked in place at" @ S.Location @ "yaw" @ S.Rotation.Yaw);
		return S;
	}
	TargetPose(i, S, P, R);
	if (S.bHidden)
		`log("XComMapEd:" @ self @ "WARNING:" @ S @ "is already hidden; a hide object ran first and may have changed it");
	// Doors and ladders first: they are a destructible and a level actor too.
	if (XComInteractiveLevelActor(S) != none && bCopyDoors)
		C = Spawn(class'XComMapEdDoor', , , P, R, , true);
	else if (XComLadder(S) != none && bCopyLadders)
		C = Spawn(class'XComMapEdLevelPiece', , , P, R, , true);
	else if (XComInteractiveLevelActor(S) != none || XComLadder(S) != none)
		return MoveOne(S, P, R) ? S : none;
	else if (XComFracLevelActor(S) != none && AsLevelPiece.Find(S.Name) != INDEX_NONE)
		C = Spawn(class'XComMapEdLevelPiece', , , P, R, , true);
	else if (XComFracLevelActor(S) != none)
		C = Spawn(WallClass != none ? WallClass : class'XComMapEdWall', , , P, R, , true);
	else if (XComDestructibleActor(S) != none)
		C = Spawn(class'XComMapEdDestructible', , , P, R, , true);
	else if (StaticMeshActor(S) != none)
		C = Spawn(class'XComMapEdLevelPiece', , , P, R, , true);
	else
	{
		`log("XComMapEd:" @ self @ "can't copy" @ S @ "(" $ S.Class.Name $ ") yet");
		return none;
	}
	if (C != none)
		FillCopy(S, C);
	if (bAbsolutePoses)
		`log("XComMapEd:" @ self @ "copied" @ S @ "(" $ S.Class.Name $ ") as" @ C @ Label(i) @ "at" @ P @ "rotation (" $ R.Pitch $ "," $ R.Yaw $ "," $ R.Roll $ ")");
	else
		`log("XComMapEd:" @ self @ "copied" @ S @ "(" $ S.Class.Name $ ") as" @ C @ "at" @ P @ "yaw" @ R.Yaw);
	return C;
}

/** Makes C a copy of S: mesh, materials, gameplay flags (its class decides how). Used at spawn and after a load. */
function FillCopy(Actor S, Actor C)
{
	if (XComMapEdDoor(C) != none && XComInteractiveLevelActor(S) != none)
		XComMapEdDoor(C).CopyFrom(XComInteractiveLevelActor(S));
	else if (XComMapEdLevelPiece(C) != none && XComFracLevelActor(S) != none)
		XComMapEdLevelPiece(C).CopyFromFrac(XComFracLevelActor(S));
	else if (XComMapEdLevelPiece(C) != none && StaticMeshActor(S) != none)
	{
		XComMapEdLevelPiece(C).CopyFrom(StaticMeshActor(S));
		// A ladder's look only: with collision it blocks its own top tile (run 18), and the tiles must not take it
		// as a wall or floor.
		if (XComLadder(S) != none)
		{
			C.SetCollision(false, false);
			XComMapEdLevelPiece(C).bPathColliding = false;
			XComMapEdLevelPiece(C).bIgnoreFor3DCursorCollision = true;
			XComMapEdLevelPiece(C).StaticMeshComponent.SetActorCollision(false, false);
			XComMapEdLevelPiece(C).StaticMeshComponent.SetBlockRigidBody(false);
		}
	}
	else if (XComMapEdWall(C) != none && XComFracLevelActor(S) != none)
	{
		XComMapEdWall(C).CopyFrom(XComFracLevelActor(S));
		if (bWallNoEnvShadow)
			XComMapEdWall(C).NoEnvironmentShadow();
		if (bWallOverlay)
			XComMapEdWall(C).UseOverlay();
		if (bWallNoWorldGeometry)
			C.bWorldGeometry = false;
	}
	else if (XComMapEdDestructible(C) != none && XComDestructibleActor(S) != none)
	{
		XComMapEdDestructible(C).CopyFrom(XComDestructibleActor(S));
		C.SetDrawScale(S.DrawScale);
		C.SetDrawScale3D(S.DrawScale3D);
	}
	if (CopyScale != vect(0, 0, 0))
		C.SetDrawScale3D(S.DrawScale3D * CopyScale);
}

/**
 * Copies a source onto its copy again after a load (F-17). A save keeps only damaged pieces. On load the game rebuilds
 * each saved one in place, under its saved name, from its class defaults and the saved record (health, state, broken
 * columns): the copier's reference still holds, but the copy has lost its mesh. The copy calls this from its
 * PostBeginPlay, before the game applies the record; during a normal spawn it isn't in Copies yet, so nothing happens.
 */
function bool RestoreLoaded(Actor C)
{
	local int i;
	local vector P;
	local rotator R;

	i = Copies.Find(C);
	if (i == INDEX_NONE || Sources[i] == none)
		return false;
	TargetPose(i, Sources[i], P, R);
	if (VSize(C.Location - P) > 1)
		C.SetLocation(P);
	C.SetRotation(R);
	FillCopy(Sources[i], C);
	if (XComMapEdWall(C) != none)
		XComMapEdWall(C).CopyColumns(XComFracLevelActor(Sources[i]), Pivot, Location, MakeRotator(0, Rotation.Yaw, 0), Sources, Copies);
	EnableCutout();
	LightCopy(i);
	LeaveOutSkyLight(C);
	// The copy was made again from its class defaults: its links are gone.
	LinkBreakGroups();
	`log("XComMapEd:" @ self @ "restored" @ C @ "from" @ Sources[i] @ "after a load, at" @ C.Location @ "(was it moved:" @ (VSize(C.Location - P) > 1) $ ")");
	return true;
}

/**
 * Links the pieces of each break group, so that a piece made of several (two consoles stacked into one) never stands
 * half broken. A copy (XComMapEdDestructible) passes its own damage state on to the rest of its group from its hits
 * (BreakPartners). A base-map piece left in place does it through the game's own link, AffectedChildren, which its
 * damage states follow (SyncChildStates), as URB_Bar links a van's parts; there it is one way, from that piece to the
 * rest. Called at load and after a load restores a copy; linking again changes nothing.
 */
function LinkBreakGroups()
{
	local array<XComDestructibleActor> Originals, Members;
	local array<int> Numbers;
	local XComDestructibleActor D;
	local int i, j, k, g;
	local string Names;

	if (BreakGroups.Length == 0 && BreakOriginals.Length == 0)
		return;
	Originals.Length = BreakOriginals.Length;
	if (BreakOriginals.Length > 0)
		foreach AllActors(class'XComDestructibleActor', D)
			if (D.Outer == WorldInfo.Outer)
				for (i = 0; i < BreakOriginals.Length; i++)
					if (BreakOriginals[i] == D.Name)
						Originals[i] = D;
	for (i = 0; i < BreakGroups.Length; i++)
		if (BreakGroups[i] > 0 && Numbers.Find(BreakGroups[i]) == INDEX_NONE)
			Numbers.AddItem(BreakGroups[i]);
	for (i = 0; i < BreakOriginalGroups.Length; i++)
		if (BreakOriginalGroups[i] > 0 && Numbers.Find(BreakOriginalGroups[i]) == INDEX_NONE)
			Numbers.AddItem(BreakOriginalGroups[i]);
	for (j = 0; j < Numbers.Length; j++)
	{
		g = Numbers[j];
		Members.Length = 0;
		for (i = 0; i < BreakGroups.Length && i < Copies.Length; i++)
		{
			if (BreakGroups[i] != g)
				continue;
			D = XComDestructibleActor(Copies[i]);
			if (D == none)
				`log("XComMapEd:" @ self @ "WARNING: copy" @ i @ Label(i) @ "(" $ Copies[i] $ ") is not a destructible piece; it can't break with group" @ g);
			else
				Members.AddItem(D);
		}
		for (i = 0; i < BreakOriginals.Length; i++)
		{
			if (i >= BreakOriginalGroups.Length || BreakOriginalGroups[i] != g)
				continue;
			if (Originals[i] == none)
				`log("XComMapEd:" @ self @ "WARNING: no destructible" @ BreakOriginals[i] @ "in the base map; it can't break with group" @ g);
			else
				Members.AddItem(Originals[i]);
		}
		if (Members.Length < 2)
		{
			`log("XComMapEd:" @ self @ "WARNING: break group" @ g @ "has" @ Members.Length @ "piece(s); nothing to link");
			continue;
		}
		Names = "";
		for (i = 0; i < Members.Length; i++)
		{
			if (XComMapEdDestructible(Members[i]) != none)
			{
				XComMapEdDestructible(Members[i]).BreakPartners = Members;
				XComMapEdDestructible(Members[i]).BreakPartners.RemoveItem(Members[i]);
			}
			else
				for (k = 0; k < Members.Length; k++)
					if (k != i && Members[i].AffectedChildren.Find(Members[k]) == INDEX_NONE)
						Members[i].AffectedChildren.AddItem(Members[k]);
			Names = Names @ string(Members[i].Name) $ (XComMapEdDestructible(Members[i]) != none ? "" : " (the map's own)") @ "in" @ Members[i].GetStateName() $ ";";
		}
		`log("XComMapEd:" @ self @ "break group" @ g $ ":" $ Names @ "when one is damaged or destroyed, so are the others");
	}
}

/** Sets copy i's light environment from CopyLights, if it has an entry there. */
function LightCopy(int i)
{
	if (i >= CopyLights.Length || XComMapEdDestructible(Copies[i]) == none)
		return;
	XComMapEdDestructible(Copies[i]).SetLighting(CopyLights[i].Mode, CopyLights[i].bBooleanShadow);
	`log("XComMapEd:" @ self @ "lit" @ Copies[i] @ Label(i) @ "mode" @ CopyLights[i].Mode $ ":" @ XComMapEdDestructible(Copies[i]).LightingText());
}

/**
 * Has a copy of one of the map's baked pieces leave out a units-only sky light (XComMapEdSkyFree). Not a copied door
 * (the map's own doors are lit live too, sky light included), nor a base-map piece moved as itself.
 */
function LeaveOutSkyLight(Actor C)
{
	if (bKeepSkyLight || C == none)
		return;
	if (XComMapEdDestructible(C) != none || XComMapEdWall(C) != none || XComMapEdLevelPiece(C) != none)
		class'XComMapEdSkyFree'.static.Add(self, C);
}

/**
 * Moves a base-map piece that can't be copied yet (a door or a ladder) to its place in the new layout, as itself. A
 * door's interaction points at its old place are removed first; the tile rebuild over the copies, which runs after
 * this, adds them at the new place (the rebuild's interactions step).
 */
function bool MoveOne(Actor S, vector P, rotator R)
{
	local XComWorldData World;
	local bool bCollide, bBlock, bMoved;

	World = class'XComWorldData'.static.GetWorldData();
	if (XComInteractiveLevelActor(S) != none && World != none)
		World.RemoveInteractionPoints(XComInteractiveLevelActor(S));
	Moved.AddItem(S);
	MovedFrom.AddItem(S.Location);
	bCollide = S.bCollideActors;
	bBlock = S.bBlockActors;
	S.SetCollision(false, false);
	bMoved = S.SetLocation(P);
	S.SetRotation(R);
	S.SetCollision(bCollide, bBlock);
	S.Tag = 'XComMapEdMoved';
	`log("XComMapEd:" @ self @ (bMoved ? "moved" : "FAILED to move") @ S @ "(" $ S.Class.Name $ ") from" @ MovedFrom[MovedFrom.Length - 1]
		@ "to" @ S.Location @ "yaw" @ S.Rotation.Yaw @ "(static" @ S.bStatic @ "movable" @ S.bMovable $ ")");
	return bMoved;
}

/**
 * Puts the patch's building in the tactical HUD's and the 3D cursor's building lists. Both fill them once, in their
 * PostBeginPlay, from the buildings there at that moment, which can be before this patch level streams in. The mouse
 * pick treats a walkable hit outside every listed building as final, so the cursor stuck to our roof (EXP-07 run 22,
 * F-34). Runs every 2 s, since the HUD or the cursor may also start after this.
 */
function RegisterBuilding()
{
	local XComBuildingVolume B;
	local XComTacticalHUD H;
	local XCom3DCursor C;

	B = FindBuilding();
	if (B == none)
		return;
	foreach AllActors(class'XComTacticalHUD', H)
		if (H.m_arrBuildingVolumes.Find(B) == INDEX_NONE)
		{
			H.m_arrBuildingVolumes.AddItem(B);
			`log("XComMapEd:" @ self @ "added" @ B @ "to" @ H $ "'s building list, now" @ H.m_arrBuildingVolumes.Length);
		}
	foreach AllActors(class'XCom3DCursor', C)
		if (C.m_arrBuildingVolumes.Find(B) == INDEX_NONE)
		{
			C.m_arrBuildingVolumes.AddItem(B);
			`log("XComMapEd:" @ self @ "added" @ B @ "to" @ C $ "'s building list, now" @ C.m_arrBuildingVolumes.Length);
		}
}

/**
 * Switches on bCutoutMask for the copies' mesh classes (XComMapEdFracMeshComponent for walls, XComMapEdMeshComponent
 * for windows and door frames) with the game's `set` console command, which finds the property in the game's own engine class, and reattaches the copies' meshes. Without it a
 * building's walls aren't trimmed down or cut out in front of the camera (F-35). Logs what `get` reads back, since a
 * shipped game may refuse `set` for a property that isn't config.
 */
function EnableCutout()
{
	local string S, G;
	local int i, n;

	S = ConsoleCommand("set XComMapEdFracMeshComponent bCutoutMask true", false);
	S $= ConsoleCommand("set XComMapEdMeshComponent bCutoutMask true", false);
	G = ConsoleCommand("get XComMapEdFracMeshComponent bCutoutMask", false) @ "/" @ ConsoleCommand("get XComMapEdMeshComponent bCutoutMask", false);
	for (i = 0; i < Copies.Length; i++)
		if (XComMapEdWall(Copies[i]) != none)
		{
			Copies[i].ReattachComponent(XComMapEdWall(Copies[i]).FracturedStaticMeshComponent);
			n++;
		}
		else if (XComMapEdDestructible(Copies[i]) != none)
		{
			Copies[i].ReattachComponent(XComMapEdDestructible(Copies[i]).StaticMeshComponent);
			n++;
		}
	`log("XComMapEd:" @ self @ "cutout: set said '" $ S $ "', get says (walls / destructibles) '" $ G $ "'; reattached" @ n @ "mesh(es)");
}

/** The patch's building volume (BuildingName). */
function XComBuildingVolume FindBuilding()
{
	local XComBuildingVolume BV;

	foreach AllActors(class'XComBuildingVolume', BV)
		if (BV.Name == BuildingName)
			return BV;
	`log("XComMapEd:" @ self @ "WARNING: no building volume" @ BuildingName);
	return none;
}

/**
 * Puts the copies into the patch's building: its floor volumes learn their building, its floors their heights, and
 * each copy gets its source's entry from the base map's baked floor caches (same floor index, same cutdown floor).
 * A moved piece is taken out of the base map's caches, so its old building no longer cuts it away.
 */
function SetupBuilding(string When)
{
	local XComBuildingVolume BV, Found;
	local FloorActorInfo FAI;
	local int i, j, k, n, nRemoved;

	Found = FindBuilding();
	if (Found == none)
		return;
	Found.CacheBuildingVolumeInChildrenFloorVolumes();
	Found.CacheFloorCenterAndExtent();
	foreach AllActors(class'XComBuildingVolume', BV)
	{
		if (BV.Outer != WorldInfo.Outer)
			continue;
		for (i = 0; i < BV.Floors.Length; i++)
			for (j = BV.Floors[i].m_aCachedActors.Length - 1; j >= 0; j--)
			{
				k = Sources.Find(BV.Floors[i].m_aCachedActors[j].ResidentActor);
				if (k == INDEX_NONE || Copies[k] == none)
					continue;
				if (BuildingFloor < 0 && i < Found.Floors.Length && !InFloorCache(Found, i, Copies[k]))
				{
					FAI.ResidentActor = Copies[k];
					FAI.CutdownFloor = BV.Floors[i].m_aCachedActors[j].CutdownFloor;
					Found.Floors[i].m_aCachedActors.AddItem(FAI);
					n++;
				}
				if (Copies[k] == Sources[k])
				{
					BV.Floors[i].m_aCachedActors.Remove(j, 1);
					nRemoved++;
				}
			}
	}
	if (BuildingFloor >= 0 && BuildingFloor < Found.Floors.Length)
	{
		for (k = 0; k < Copies.Length; k++)
			if (Copies[k] != none && Copies[k] != Sources[k] && !InFloorCache(Found, BuildingFloor, Copies[k]))
			{
				FAI.ResidentActor = Copies[k];
				FAI.CutdownFloor = 0;
				Found.Floors[BuildingFloor].m_aCachedActors.AddItem(FAI);
				n++;
			}
	}
	else if (BuildingFloor >= 0)
		`log("XComMapEd:" @ self @ "WARNING:" @ Found @ "has" @ Found.Floors.Length @ "floors, no floor" @ BuildingFloor);
	`log("XComMapEd:" @ self @ "gave" @ Found @ n @ "cached floor entries" @ "(BuildingFloor" @ BuildingFloor $ "; -1: the base map's), and took" @ nRemoved @ "moved pieces out of the base map's caches (" $ When $ ")");
	LogBuilding(Found, When);
	LogFloorsOf(Found, Copies, "copy");
}

function bool InFloorCache(XComBuildingVolume BV, int i, Actor A)
{
	local int j;

	for (j = 0; j < BV.Floors[i].m_aCachedActors.Length; j++)
		if (BV.Floors[i].m_aCachedActors[j].ResidentActor == A)
			return true;
	return false;
}

function LogBuilding(XComBuildingVolume BV, string When)
{
	local int i, j, nOurs;
	local string S;

	for (i = 0; i < BV.Floors.Length; i++)
	{
		nOurs = 0;
		for (j = 0; j < BV.Floors[i].m_aCachedActors.Length; j++)
			if (Copies.Find(BV.Floors[i].m_aCachedActors[j].ResidentActor) != INDEX_NONE)
				nOurs++;
		S = S $ "; floor" @ i $ ":" @ BV.Floors[i].FloorVolumes.Length @ "volume(s), centre z" @ BV.Floors[i].fCenterZ
			@ "extent" @ BV.Floors[i].fExtent $ "," @ BV.Floors[i].m_aCachedActors.Length @ "cached actors (" $ nOurs
			@ "ours)," @ BV.Floors[i].m_aCachedEmitters.Length @ "emitters";
	}
	`log("XComMapEd:" @ self @ "building" @ BV @ When $ ":" @ BV.Floors.Length @ "floors, inside" @ BV.IsInside $ S);
}

/** Which floor of BV caches each actor of List, with its cutdown floor. */
function LogFloorsOf(XComBuildingVolume BV, array<Actor> List, string What)
{
	local int i, j, k;
	local string S;

	for (i = 0; i < BV.Floors.Length; i++)
		for (j = 0; j < BV.Floors[i].m_aCachedActors.Length; j++)
		{
			k = List.Find(BV.Floors[i].m_aCachedActors[j].ResidentActor);
			if (k != INDEX_NONE)
				S = S @ List[k].Name $ ":" $ i $ "/" $ BV.Floors[i].m_aCachedActors[j].CutdownFloor;
		}
	`log("XComMapEd:" @ self @ What @ "floors in" @ BV @ "(actor:floor/cutdown floor):" $ S);
}

/** The base map's baked floor caches for our sources: what the game itself does for these pieces. */
function LogSourceFloors()
{
	local XComBuildingVolume BV;

	foreach AllActors(class'XComBuildingVolume', BV)
		if (BV.Outer == WorldInfo.Outer && BV.Floors.Length > 0)
		{
			LogBuilding(BV, "as baked");
			LogFloorsOf(BV, Sources, "source");
		}
}

/** Where the moved pieces are, and a door's interaction points at its new and old places. */
function LogMoved()
{
	local XComWorldData World;
	local array<XComInteractPoint> Pts;
	local int i, j, nNew, nOld;
	local string S;

	World = class'XComWorldData'.static.GetWorldData();
	for (i = 0; i < Moved.Length; i++)
	{
		if (Moved[i] == none)
			continue;
		if (XComInteractiveLevelActor(Moved[i]) != none && World != none)
		{
			S = "";
			nNew = 0;
			Pts.Length = 0;
			World.GetInteractionPoints(Moved[i].Location, 192, 192, Pts);
			for (j = 0; j < Pts.Length; j++)
				if (Pts[j].InteractiveActor == Moved[i])
				{
					nNew++;
					S = S @ Pts[j].InteractSocketName $ "@" $ Pts[j].Location;
				}
			nOld = 0;
			Pts.Length = 0;
			World.GetInteractionPoints(MovedFrom[i], 192, 192, Pts);
			for (j = 0; j < Pts.Length; j++)
				if (Pts[j].InteractiveActor == Moved[i])
					nOld++;
			`log("XComMapEd:" @ self @ "moved door" @ Moved[i] @ "at" @ Moved[i].Location @ "state" @ Moved[i].GetStateName() @ "hidden" @ Moved[i].bHidden
				$ ":" @ nNew @ "interaction point(s) there" $ S $ "," @ nOld @ "left at the old place" @ MovedFrom[i]);
		}
		else
			`log("XComMapEd:" @ self @ "moved" @ Moved[i] @ "(" $ Moved[i].Class.Name $ ") is at" @ Moved[i].Location @ "yaw" @ Moved[i].Rotation.Yaw
				@ "hidden" @ Moved[i].bHidden @ "collide" @ Moved[i].bCollideActors);
	}
}

/** The first wall's lighting again once the level has run a few seconds, every copy's flags, and the probe line. */
function LogLightingLater()
{
	local vector HitLocation, HitNormal;
	local Actor HitActor, C;
	local XComWorldData World;
	local int i;

	LogCopiesLighting();
	for (i = 0; i < CopyLights.Length && i < Copies.Length; i++)
		if (XComMapEdDestructible(Copies[i]) != none)
			`log("XComMapEd:" @ self @ "5 s after load," @ Copies[i] @ Label(i) $ ":" @ XComMapEdDestructible(Copies[i]).LightingText());
	if (bAbsolutePoses)
		LogPoses("5 s after load");
	World = class'XComWorldData'.static.GetWorldData();
	if (bUpdateBuildHeightTiles && World != none)
		`log("XComMapEd:" @ self @ "UpdateBuildHeightTiles is now" @ World.UpdateBuildHeightTiles @ "(rebuilds so far" @ World.NumRebuilds $ ")");
	LogMoved();
	LogPathProbes("5 s after load");
	LogFloorProbes("5 s after load");
	if (bLogLadders)
		LogLadders("5 s after load");
	if (BuildingName != '' && FindBuilding() != none)
	{
		LogFloorTouching();
		LogBuilding(FindBuilding(), "5 s after load");
		LogFloorsOf(FindBuilding(), Copies, "copy");
	}
	if (bLogTiles)
		foreach Copies(C)
		{
			if (XComMapEdWall(C) != none || XComMapEdLevelPiece(C) != none)
				LogWallTiles(C);
			else if (XComMapEdDestructible(C) != none)
			{
				LogWallTiles(C);
				LogCopyTiles(C);
			}
		}
	if (bWaterTiles && WaterX.Length > 0)
	{
		MarkWaterTiles(false);
		RebuildTiles();
		SetTimer(5.0, false, 'LogTilesAgain');
	}
	foreach Copies(C)
		if (C != none)
			`log("XComMapEd:" @ self @ "flags of" @ C $ ": world geometry" @ C.bWorldGeometry @ "collide" @ C.bCollideActors
				@ "block" @ C.bBlockActors @ "hidden" @ C.bHidden
				@ "blocks vision" @ (XComFracLevelActor(C) != none ? string(XComFracLevelActor(C).VisibilityBlockingData.bBlockUnitVisibility)
					: (XComLevelActor(C) != none ? string(XComLevelActor(C).VisibilityBlockingData.bBlockUnitVisibility) : "-")));
	if (ProbeStart == ProbeEnd)
		return;
	HitActor = Trace(HitLocation, HitNormal, ProbeEnd, ProbeStart, true);
	`log("XComMapEd:" @ self @ "probe: line hits" @ HitActor @ "at" @ HitLocation);
	HitActor = Trace(HitLocation, HitNormal, ProbeEnd, ProbeStart, true, vect(24, 24, 24));
	`log("XComMapEd:" @ self @ "probe: box hits" @ HitActor @ "at" @ HitLocation);
	World = class'XComWorldData'.static.GetWorldData();
	HitActor = none;
	if (World != none && World.WorldTrace(ProbeStart, ProbeEnd, HitLocation, HitNormal, HitActor))
		`log("XComMapEd:" @ self @ "probe: WorldTrace hits" @ HitActor @ "at" @ HitLocation);
	else
		`log("XComMapEd:" @ self @ "probe: WorldTrace hits nothing");
}

/**
 * The tile data along one wall copy (EXP-07 run 5, F-29): for every tile row the wall crosses, two tiles on each side
 * of it, each with its cover flags (XComWorldData COVER_*, decimal) and occupancy; whether the game counts the two
 * tiles touching the wall as visible to each other (IsAdjacentTileVisible); and WorldTrace across the wall at 80 and
 * 160 units high. Works for walls running north-south (copies turned by 90 or 270 degrees).
 */
function LogWallTiles(Actor C)
{
	local XComWorldData World;
	local XComCoverPoint CP;
	local box B;
	local vector P, W, E, HitLocation, HitNormal;
	local Actor HitActor;
	local int TX, TY, TZ, X0, Y0, Y1, Y, X, Flags;
	local string Line, Hit80, Hit160;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none || !class'XComMapEdHider'.static.ActorBox(C, B))
		return;
	if (B.Max.Y - B.Min.Y < B.Max.X - B.Min.X)
	{
		`log("XComMapEd:" @ self @ "tiles of" @ C $ ": not a north-south wall, skipped");
		return;
	}
	P = (B.Min + B.Max) / 2.0;
	P.Z = 80;
	World.GetTileCoordinatesFromPosition(P, TX, TY, TZ);
	// The tile whose east edge is nearest the wall's centre line is the first tile west of it.
	X0 = TX;
	if (World.GetPositionFromTileCoordinates(TX, TY, TZ).X > P.X)
		X0 = TX - 1;
	P.Y = B.Min.Y + 8;
	World.GetTileCoordinatesFromPosition(P, TX, Y0, TZ);
	P.Y = B.Max.Y - 8;
	World.GetTileCoordinatesFromPosition(P, TX, Y1, TZ);
	`log("XComMapEd:" @ self @ "tiles of" @ C $ " (world" @ World.NumX $ "x" $ World.NumY $ "x" $ World.NumZ @ "=" @ World.NumX * World.NumY * World.NumZ
		@ "tiles, NumTiles" @ World.NumTiles $ "): wall x" @ (B.Min.X + B.Max.X) / 2.0 @ "between tiles" @ X0 @ "and" @ X0 + 1
		@ "rows" @ Y0 @ "to" @ Y1 @ "z tile" @ TZ @ "(cells: x:flags/occupied/fully)");
	for (Y = Y0 - 1; Y <= Y1 + 1; Y++)
	{
		Line = "";
		for (X = X0 - 1; X <= X0 + 2; X++)
		{
			P = World.GetPositionFromTileCoordinates(X, Y, TZ);
			Flags = -1;
			if (World.GetCoverPoint(P, CP))
				Flags = CP.Flags;
			Line = Line @ X $ ":" $ Flags $ "/" $ (World.IsTileOccupied(X, Y, TZ) ? "o" : "-") $ (World.IsTileFullyOccupied(X, Y, TZ) ? "F" : "-");
		}
		W = World.GetPositionFromTileCoordinates(X0, Y, TZ);
		E = World.GetPositionFromTileCoordinates(X0 + 1, Y, TZ);
		W.Z = 80; E.Z = 80;
		HitActor = none;
		Hit80 = World.WorldTrace(W, E, HitLocation, HitNormal, HitActor) ? string(HitActor) : "-";
		W.Z = 160; E.Z = 160;
		HitActor = none;
		Hit160 = World.WorldTrace(W, E, HitLocation, HitNormal, HitActor) ? string(HitActor) : "-";
		W.Z = 80; E.Z = 80;
		`log("XComMapEd:" @ self @ "row" @ Y $ ":" $ Line @ "| vis index" @ World.GetVisibilityMapTileIndex(X0, Y, TZ) $ "/" $ World.GetVisibilityMapTileIndex(X0 + 1, Y, TZ)
			@ "| adjacent visible" @ World.IsAdjacentTileVisible(W, E)
			@ "| trace 80" @ Hit80 @ "160" @ Hit160);
	}
}

/** Marks (or, with false, clears) every tile over the copies' boxes from the first level above the ground as water. */
function MarkWaterTiles(bool bWater)
{
	local XComWorldData World;
	local Actor C;
	local box B;
	local vector P;
	local int X0, Y0, Z0, X1, Y1, Z1, X, Y, Z, i, n, ok;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	if (bWater)
	{
		WaterX.Length = 0; WaterY.Length = 0; WaterZ.Length = 0;
		foreach Copies(C)
		{
			if (C == none || !class'XComMapEdHider'.static.ActorBox(C, B))
				continue;
			P = B.Min + vect(1, 1, 0);
			P.Z = B.Min.Z + 64 + 16;
			World.GetTileCoordinatesFromPosition(P, X0, Y0, Z0);
			P = B.Max - vect(1, 1, 1);
			World.GetTileCoordinatesFromPosition(P, X1, Y1, Z1);
			for (X = X0; X <= X1; X++)
				for (Y = Y0; Y <= Y1; Y++)
					for (Z = Z0; Z <= Z1; Z++)
					{
						WaterX.AddItem(X); WaterY.AddItem(Y); WaterZ.AddItem(Z);
					}
		}
	}
	n = WaterX.Length;
	for (i = 0; i < n; i++)
		if (World.SetIsWaterTile(WaterX[i], WaterY[i], WaterZ[i], bWater))
			ok++;
	`log("XComMapEd:" @ self @ (bWater ? "marked" : "cleared") @ n @ "tiles as water (" $ ok @ "returned true)");
}

function SetBuildHeightFlag()
{
	local XComWorldData World;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	`log("XComMapEd:" @ self @ "UpdateBuildHeightTiles was" @ World.UpdateBuildHeightTiles $ "; setting it");
	World.UpdateBuildHeightTiles = true;
}

function LogTilesAgain()
{
	local Actor C;

	`log("XComMapEd:" @ self @ "tiles again, after clearing the water marks and rebuilding:");
	foreach Copies(C)
		if (XComMapEdWall(C) != none || XComMapEdLevelPiece(C) != none)
			LogWallTiles(C);
}

/**
 * Occupancy of every tile a copy's box covers, from the level its base stands on up (EXP-07 run 10: do destructible
 * copies register there?). Until EXP-14 it started 80 units above the base, which skipped the tile a piece on a raised
 * walk stands on.
 */
function LogCopyTiles(Actor C)
{
	local XComWorldData World;
	local box B;
	local vector P;
	local int X0, Y0, Z0, X1, Y1, Z1, X, Y, Z;
	local string Line;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none || !class'XComMapEdHider'.static.ActorBox(C, B))
		return;
	P = B.Min + vect(1, 1, 0);
	P.Z = B.Min.Z + 8;
	World.GetTileCoordinatesFromPosition(P, X0, Y0, Z0);
	P = B.Max - vect(1, 1, 1);
	World.GetTileCoordinatesFromPosition(P, X1, Y1, Z1);
	`log("XComMapEd:" @ self @ "tiles under" @ C @ "box" @ B.Min @ "to" @ B.Max $ ": x" @ X0 $ ".." $ X1 @ "y" @ Y0 $ ".." $ Y1 @ "levels" @ Z0 $ ".." $ Z1);
	for (Z = Z0; Z <= Z1; Z++)
	{
		Line = "";
		for (Y = Y0; Y <= Y1; Y++)
			for (X = X0; X <= X1; X++)
				Line = Line @ X $ "," $ Y $ ":" $ (World.IsTileOccupied(X, Y, Z) ? "o" : "-") $ (World.IsTileFullyOccupied(X, Y, Z) ? "F" : "-");
		`log("XComMapEd:" @ self @ "level" @ Z $ ":" $ Line);
	}
}

/** Every wall and plain-mesh copy's lighting setup. */
function LogCopiesLighting()
{
	local Actor C;

	foreach Copies(C)
	{
		if (XComMapEdWall(C) != none)
			XComMapEdWall(C).LogLighting();
		else if (XComMapEdLevelPiece(C) != none)
			XComMapEdLevelPiece(C).LogLighting();
	}
}

/** One movable point light near the copies (EXP-07 lighting test): do the copies take real dynamic light? */
function SpawnTestLight()
{
	local XComMapEdLight L;

	L = Spawn(class'XComMapEdLight', , , TestLightAt);
	if (L == none)
	{
		`log("XComMapEd:" @ self @ "WARNING: could not spawn the test light");
		return;
	}
	L.Setup(TestLightRadius, TestLightBrightness > 0 ? TestLightBrightness : 3.0);
	`log("XComMapEd:" @ self @ "spawned test light" @ L @ "at" @ L.Location @ "radius" @ L.Light.Radius @ "brightness" @ L.Light.Brightness);
}

/** The box around all copies (false: no copy has one). */
function bool CopiesBox(out box All)
{
	local box B;
	local bool bAny;
	local int i;

	for (i = 0; i < Copies.Length; i++)
	{
		if (Copies[i] == none || !class'XComMapEdHider'.static.ActorBox(Copies[i], B))
			continue;
		if (!bAny)
			All = B;
		else
		{
			All.Min.X = FMin(All.Min.X, B.Min.X); All.Min.Y = FMin(All.Min.Y, B.Min.Y); All.Min.Z = FMin(All.Min.Z, B.Min.Z);
			All.Max.X = FMax(All.Max.X, B.Max.X); All.Max.Y = FMax(All.Max.Y, B.Max.Y); All.Max.Z = FMax(All.Max.Z, B.Max.Z);
		}
		bAny = true;
	}
	return bAny;
}

/**
 * The ladders whose foot is within RebuildPad of the copies: with each one's foot and top points as the game works
 * them out (native 0x777580), whether there is floor at each, and whether something occupies those tiles.
 */
function LogLadderFeet(string When, bool bRebuild)
{
	local XComWorldData World;
	local XComLadder L;
	local box All;
	local vector Fwd, Foot, Top, Below, E;
	local int FX, FY, FZ, TX, TY, TZ;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none || !CopiesBox(All))
		return;
	foreach AllActors(class'XComLadder', L)
	{
		Fwd = vector(L.Rotation);
		Foot = L.Location - 16 * Fwd + vect(0, 0, 8);
		if (Foot.X < All.Min.X - RebuildPad || Foot.X > All.Max.X + RebuildPad || Foot.Y < All.Min.Y - RebuildPad || Foot.Y > All.Max.Y + RebuildPad)
			continue;
		Top = L.Location + 76 * Fwd;
		Top.Z = L.Location.Z + L.GetHeight() + 8;
		Below = Top - vect(0, 0, 64);
		World.GetTileCoordinatesFromPosition(Foot, FX, FY, FZ);
		World.GetTileCoordinatesFromPosition(Top, TX, TY, TZ);
		`log("XComMapEd:" @ self @ "ladder" @ L @ When $ ": foot" @ Foot @ "tile (" $ FX $ "," $ FY $ "," $ FZ $ ") floor" @ World.IsPositionOnFloor(Foot)
			@ "occupied" @ World.IsTileOccupied(FX, FY, FZ) @ "| top" @ Top @ "tile (" $ TX $ "," $ TY $ "," $ TZ $ ") floor" @ World.IsPositionOnFloor(Top)
			@ "or below" @ World.IsPositionOnFloor(Below) @ "occupied" @ World.IsTileOccupied(TX, TY, TZ) $ "/" $ World.IsTileOccupied(TX, TY, TZ - 1)
			@ "| hidden" @ L.bHidden @ "collide" @ L.bCollideActors);
		E = vect(8, 8, 8);
		if (bRebuild)
			World.RebuildTileDataExtents(Foot, E);
	}
}

function LogCursor()
{
	local XComWorldData World;
	local XCom3DCursor C;
	local int X, Y, Z;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
		return;
	foreach AllActors(class'XCom3DCursor', C)
	{
		World.GetTileCoordinatesFromPosition(C.Location, X, Y, Z);
		if (X != CursorX || Y != CursorY || Z != CursorZ)
		{
			CursorX = X; CursorY = Y; CursorZ = Z;
			`log("XComMapEd:" @ self @ "cursor at" @ C.Location @ "tile (" $ X $ "," $ Y $ "," $ Z $ ") floor z" @ World.GetFloorZForPosition(C.Location, false));
		}
		break;
	}
}

function RebuildLadderFeet()
{
	LogLadderFeet("before its last foot rebuild", true);
	SetTimer(2.0, false, 'LogAfterLadderFeet');
}

function LogAfterLadderFeet()
{
	LogLadderFeet("after its last foot rebuild", false);
	LogPathProbes("after the ladder foot rebuild");
	LogFloorProbes("after the ladder foot rebuild");
}

/** Rebuilds the tile data over all copies (their boxes plus RebuildPad) at load speed. */
function RebuildTiles()
{
	local XComWorldData World;
	local box All;
	local vector P, E;

	World = class'XComWorldData'.static.GetWorldData();
	if (World == none)
	{
		SetTimer(1.0, false, 'RebuildTiles');
		return;
	}
	if (bAbsolutePoses)
	{
		RebuildEachCopy(World);
		return;
	}
	if (!CopiesBox(All))
		return;
	P = (All.Min + All.Max) / 2.0;
	E = (All.Max - All.Min) / 2.0 + vect(1, 1, 0) * RebuildPad + vect(0, 0, 64);
	World.SetRebuildTileProcessRate(100000);
	World.RebuildTileDataExtents(P, E);
	`log("XComMapEd:" @ self @ "rebuilding tile data around" @ P @ "extent" @ E);
}

/** Absolute poses: each copy's own box plus RebuildPad (copies can stand far apart, so no box around them all). */
function RebuildEachCopy(XComWorldData World)
{
	local box B;
	local vector P, E;
	local int i, n;

	World.SetRebuildTileProcessRate(100000);
	for (i = 0; i < Copies.Length; i++)
	{
		if (Copies[i] == none || !class'XComMapEdHider'.static.ActorBox(Copies[i], B))
			continue;
		P = (B.Min + B.Max) / 2.0;
		E = (B.Max - B.Min) / 2.0 + vect(1, 1, 0) * RebuildPad + vect(0, 0, 64);
		World.RebuildTileDataExtents(P, E);
		n++;
	}
	`log("XComMapEd:" @ self @ "rebuilding tile data around each of" @ n @ "copies, pad" @ RebuildPad);
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
	`log("XComMapEd:" @ self @ "tile rebuild finished");
}

defaultproperties
{
	bHidden=true
	RebuildPad=96
	bLogTiles=true
	BuildingFloor=-1
	WallClass=class'XComMapEdWall'
}
