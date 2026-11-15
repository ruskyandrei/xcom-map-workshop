/**
 * The breakable glass of a spawned vehicle, made at run time from one of the game's XComFracLevelActor archetypes.
 *
 * A copy spawned straight from the archetype is an XComFracLevelActor, whose name comes from a counter that runs on for
 * the whole game session (_25 on the first load of a map, _46 on the next, ...). Saves find actors by name, so the
 * broken windows of such a copy are lost on a reload. This class lives in the patch's own package, which is loaded
 * afresh with every map, so its names start from _0 on every load, like XComMapEdDestructible's (EXP-05).
 *
 * Takes the mesh, materials and gameplay settings from the archetype. Firaxis-only engine settings can't be set from
 * UDK script and keep their defaults: the component's bUseVertexColorDestruction and EditorPaintedVisibleFragments,
 * and the rain-collision render channel that XComFracLevelActor.PostBeginPlay sets.
 */
class XComMapEdGlass extends XComFracLevelActor;

function CopyFrom(XComFracLevelActor T)
{
	local FracturedStaticMeshComponent C, TC;
	local int i;

	C = FracturedStaticMeshComponent;
	TC = T.FracturedStaticMeshComponent;
	C.SetStaticMesh(TC.StaticMesh, true);
	// Size the per-fragment health for the new mesh, as PostBeginPlay does when the mesh is there from the start.
	// Without it every hit logs "CachedFrag.FragIndex >= ChunkHealth.Num" and breaks nothing.
	ResetHealth();
	for (i = 0; i < TC.Materials.Length; i++)
		C.SetMaterial(i, TC.Materials[i]);
	C.FragmentBoundsMaxZ = TC.FragmentBoundsMaxZ;
	C.FragmentBoundsMinZ = TC.FragmentBoundsMinZ;
	C.bCastDynamicShadow = TC.bCastDynamicShadow;
	// As XComFracLevelActor.PostBeginPlay does, which ran during Spawn, before there was a mesh.
	if (FracturedStaticMesh(C.StaticMesh) != none)
	{
		FracturedStaticMesh(C.StaticMesh).bSpawnPhysicsChunks = false;
		FracturedStaticMesh(C.StaticMesh).UseSimpleRigidBodyCollision = true;
	}
	ReattachComponent(C);

	Toughness = T.Toughness;
	bAlwaysFracture = T.bAlwaysFracture;
	bAlwaysDestroyColumns = T.bAlwaysDestroyColumns;
	ImpactMaterialType = T.ImpactMaterialType;
	ImpactInstanceParameters = T.ImpactInstanceParameters;
	if (T.ImpactEffectsDefinition != none)
		ImpactEffectsDefinition = T.ImpactEffectsDefinition;
	VisibilityBlockingData = T.VisibilityBlockingData;
	HideableWhenBlockingObjectOfInterest = T.HideableWhenBlockingObjectOfInterest;
	bIgnoreFor3DCursorCollision = T.bIgnoreFor3DCursorCollision;
	CoverForceFlag = T.CoverForceFlag;
	CoverIgnoreFlag = T.CoverIgnoreFlag;
	bAlwaysConsiderForCover = T.bAlwaysConsiderForCover;
	bCanClimbOver = T.bCanClimbOver;
	bCanClimbOnto = T.bCanClimbOnto;
	bIsValidDestination = T.bIsValidDestination;
	bIgnoreForCover = T.bIgnoreForCover;
	bUseRigidBodyCollisionForCover = T.bUseRigidBodyCollisionForCover;
	bIsFloor = T.bIsFloor;
	Tag = T.Tag;
	TintColor = T.TintColor;
	UpdateTintColor();
}

/**
 * Broken glass is saved, and on load the save recreates it from the class defaults in place of the fresh one, without a
 * mesh (findings register F-17). As in XComMapEdDestructible.PostBeginPlay, the spawner gives the mesh back first; the
 * game's own ApplyCheckpointRecord then hides the fragments that were broken and restores the columns.
 */
simulated event PostBeginPlay()
{
	local XComMapEdSpawner S;

	super.PostBeginPlay();
	foreach AllActors(class'XComMapEdSpawner', S)
		if (S.Partner == self)
			S.RestoreLoaded(self);
}
