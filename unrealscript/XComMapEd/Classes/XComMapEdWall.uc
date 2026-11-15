/**
 * A working copy of one of the base map's fractured pieces (a wall, a roof part; an XComFracLevelActor or
 * XComDecoFracLevelActor placed in the level), made at run time by XComMapEdCopier (EXP-07).
 *
 * Lit dynamically like XComMapEdDestructible: a copy has no lightmap of its own, and with the level's precomputed
 * lighting setup it would render black (findings register F-02). It takes the source's mesh, materials and gameplay
 * settings, and the source's baked fragment columns, moved to where the copy stands: the columns are what count the
 * wall's tiles, give cover and let it break (F-10, F-22).
 *
 * The deco and debris meshes an XComDecoFracLevelActor fits along broken edges are not copied.
 */
class XComMapEdWall extends XComFracLevelActor;

/** The copy's own light environment (EXP-07 run 4: not the FracturedStaticMeshActor's LightEnvironment0). */
var DynamicLightEnvironmentComponent WallLight;
/**
 * A plain, lit static mesh of the same mesh, drawn instead of the fractured one while the wall is whole (UseOverlay;
 * EXP-07 run 4 fallback for F-28). Not attached unless used. Gameplay stays on the hidden fractured component.
 */
var StaticMeshComponent Overlay;
var transient bool bOverlayShown;

function CopyFrom(XComFracLevelActor T)
{
	local FracturedStaticMeshComponent C, TC;
	local int i;

	C = FracturedStaticMeshComponent;
	TC = T.FracturedStaticMeshComponent;
	C.SetStaticMesh(TC.StaticMesh, true);
	ResetHealth();   // sizes the per-fragment health for the new mesh (see XComMapEdGlass)
	for (i = 0; i < TC.Materials.Length; i++)
		C.SetMaterial(i, TC.Materials[i]);
	C.FragmentBoundsMaxZ = TC.FragmentBoundsMaxZ;
	C.FragmentBoundsMinZ = TC.FragmentBoundsMinZ;
	C.bCastDynamicShadow = TC.bCastDynamicShadow;
	if (FracturedStaticMesh(C.StaticMesh) != none)
	{
		FracturedStaticMesh(C.StaticMesh).bSpawnPhysicsChunks = false;
		FracturedStaticMesh(C.StaticMesh).UseSimpleRigidBodyCollision = true;
	}
	SetDrawScale(T.DrawScale);
	SetDrawScale3D(T.DrawScale3D);
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
	// The rebuild only takes actors with bPathColliding as floor and walls to stand on; XComFracLevelActor and
	// XComDestructibleActor default it to false and the editor sets it on placed pieces (EXP-07 run 20: the copied
	// roof slab gave no floor, F-30).
	bPathColliding = T.bPathColliding;
	bCanStepUpOn = T.bCanStepUpOn;
	bIgnoreForCover = T.bIgnoreForCover;
	bUseRigidBodyCollisionForCover = T.bUseRigidBodyCollisionForCover;
	bIsFloor = T.bIsFloor;
	Tag = T.Tag;
	TintColor = T.TintColor;
	UpdateTintColor();
	SetTickIsDisabled(false);
}

/**
 * Takes T's fragment columns, moved as T was moved to make this copy: each column's world box goes through
 * Place (location of the copy's pivot, rotation by yaw steps of 90°). Fragment indices stay, since the mesh is the
 * same. Columns that name other actors (a picture hanging on the wall, a window in it) keep only those that were
 * copied too, as their copies (Sources / Copies, same order).
 */
function CopyColumns(XComFracLevelActor T, vector Pivot, vector Dest, rotator Turn, const out array<Actor> Sources, const out array<Actor> Copies)
{
	local FragmentColumn Col;
	local vector A, B;
	local int i, j, k;

	FragmentColumns.Length = 0;
	for (i = 0; i < T.FragmentColumns.Length; i++)
	{
		Col = T.FragmentColumns[i];
		A = Dest + ((Col.Bounds.Min - Pivot) >> Turn);
		B = Dest + ((Col.Bounds.Max - Pivot) >> Turn);
		Col.Bounds.Min.X = FMin(A.X, B.X); Col.Bounds.Min.Y = FMin(A.Y, B.Y); Col.Bounds.Min.Z = FMin(A.Z, B.Z);
		Col.Bounds.Max.X = FMax(A.X, B.X); Col.Bounds.Max.Y = FMax(A.Y, B.Y); Col.Bounds.Max.Z = FMax(A.Z, B.Z);
		for (j = 0; j < Col.FragCache.Length; j++)
			Col.FragCache[j].MinZ += Dest.Z - Pivot.Z;
		for (j = Col.DestructibleCache.Length - 1; j >= 0; j--)
		{
			k = Sources.Find(Col.DestructibleCache[j].DestructibleActor);
			if (k == INDEX_NONE || XComDestructibleActor(Copies[k]) == none)
				Col.DestructibleCache.Remove(j, 1);
			else
			{
				Col.DestructibleCache[j].DestructibleActor = XComDestructibleActor(Copies[k]);
				Col.DestructibleCache[j].MinZ += Dest.Z - Pivot.Z;
			}
		}
		for (j = Col.FracActorCache.Length - 1; j >= 0; j--)
		{
			k = Sources.Find(Col.FracActorCache[j].FracActor);
			if (k == INDEX_NONE || XComFracLevelActor(Copies[k]) == none)
				Col.FracActorCache.Remove(j, 1);
			else
				Col.FracActorCache[j].FracActor = XComFracLevelActor(Copies[k]);
		}
		Col.bDamaged = false;
		Col.bDestroyed = false;
		Col.bCoverDebrisPlaced = false;
		FragmentColumns.AddItem(Col);
		`log("XComMapEd:" @ self @ "column" @ i @ "box" @ Col.Bounds.Min @ "to" @ Col.Bounds.Max @ "fragments" @ Col.FragCache.Length
			@ "destructibles" @ T.FragmentColumns[i].DestructibleCache.Length $ "->" $ Col.DestructibleCache.Length
			@ "frac actors" @ T.FragmentColumns[i].FracActorCache.Length $ "->" $ Col.FracActorCache.Length);
	}
}

/** EXP-07 run 4 variant: no shadowing of the environment's lights by the level (the wall's own collision may block them). */
function NoEnvironmentShadow()
{
	WallLight.bShadowFromEnvironment = false;
	WallLight.ResetEnvironment();
}

/** EXP-07 run 4 variant: the lit plain mesh is drawn while the wall is whole; the first damage swaps in the fractured one. */
function UseOverlay()
{
	local int i;

	Overlay.SetStaticMesh(FracturedStaticMeshComponent.StaticMesh);
	for (i = 0; i < FracturedStaticMeshComponent.Materials.Length; i++)
		Overlay.SetMaterial(i, FracturedStaticMeshComponent.Materials[i]);
	AttachComponent(Overlay);
	FracturedStaticMeshComponent.SetHidden(true);
	bOverlayShown = true;
}

function CheckOverlay()
{
	if (!bOverlayShown)
		return;
	if (FracturedStaticMeshComponent.GetNumVisibleFragments() < FracturedStaticMeshComponent.GetNumFragments())
	{
		bOverlayShown = false;
		Overlay.SetHidden(true);
		FracturedStaticMeshComponent.SetHidden(false);
		`log("XComMapEd:" @ self @ "damaged:" @ FracturedStaticMeshComponent.GetNumVisibleFragments() @ "of"
			@ FracturedStaticMeshComponent.GetNumFragments() @ "fragments left; the fractured mesh is shown now");
	}
	else if (!FracturedStaticMeshComponent.HiddenGame)
	{
		`log("XComMapEd:" @ self @ "something showed the fractured mesh under the overlay; hiding it again");
		FracturedStaticMeshComponent.SetHidden(true);
	}
}

simulated event BreakOffPartsInRadius(vector Origin, float Radius, float RBStrength, bool bWantPhysChunksAndParticles)
{
	super.BreakOffPartsInRadius(Origin, Radius, RBStrength, bWantPhysChunksAndParticles);
	CheckOverlay();
}

simulated event TakeCollateralDamage(Actor FromActor, int ColumnIdx, float MaxZ, int DamageAmount)
{
	super.TakeCollateralDamage(FromActor, ColumnIdx, MaxZ, DamageAmount);
	CheckOverlay();
}

simulated event Tick(float DeltaTime)
{
	super.Tick(DeltaTime);
	CheckOverlay();
}

/** Logs how this copy is lit (EXP-07: which part of the dynamic lighting setup took). */
function LogLighting()
{
	local PrimitiveComponent P;

	foreach AllOwnedComponents(class'PrimitiveComponent', P)
		`log("XComMapEd:" @ self @ "lighting of" @ P.Class.Name $ ": hidden" @ P.HiddenGame @ "environment" @ P.LightEnvironment
			@ (P.LightEnvironment != none ? "enabled " $ P.LightEnvironment.IsEnabled() : "")
			@ (DynamicLightEnvironmentComponent(P.LightEnvironment) != none ? "dynamic " $ DynamicLightEnvironmentComponent(P.LightEnvironment).bDynamic
				$ " environment shadow " $ DynamicLightEnvironmentComponent(P.LightEnvironment).bShadowFromEnvironment : "")
			@ "precomputed shadows" @ P.bUsePrecomputedShadows @ "channels static" @ P.LightingChannels.Static
			@ "dynamic" @ P.LightingChannels.Dynamic @ "initialized" @ P.LightingChannels.bInitialized
			@ "tick disabled" @ bTickIsDisabled @ "state" @ GetStateName());
}

/** A copy rebuilt by a load (it was damaged when saved) asks its copier to copy it again (F-17). */
simulated event PostBeginPlay()
{
	local XComMapEdCopier K;

	super.PostBeginPlay();
	foreach AllActors(class'XComMapEdCopier', K)
		if (K.RestoreLoaded(self))
			break;
}

defaultproperties
{
	bTickIsDisabled=false
	// Its own light environment, made like XComMapEdLevelPiece's (whose copy of the same mesh renders lit).
	Begin Object Class=DynamicLightEnvironmentComponent Name=MyLightEnvironment
		bEnabled=true
		bDynamic=true
		bForceNonCompositeDynamicLights=true
	End Object
	Components.Add(MyLightEnvironment)
	WallLight=MyLightEnvironment
	// The main mesh, of our own class so that bCutoutMask can be switched on for copies only (F-35). Set up as the
	// parent's FracturedStaticMeshComponent0 (UDK FracturedStaticMeshActor's and the game's XComFracLevelActor's
	// templates). XComFracLevelActor takes only the Static lighting channel; the destructibles that light correctly as
	// copies (cars, windows) take Static and Dynamic (EXP-07 one-wall test: the copied wall rendered flat black; F-28).
	Begin Object Class=XComMapEdFracMeshComponent Name=MapEdFracMesh0
		WireframeColor=(R=111,G=63,B=254,A=255)
		bAllowApproximateOcclusion=true
		BlockRigidBody=true
		bAcceptsStaticDecals=false
		bAcceptsDynamicDecals=true
		bAcceptsDecalsDuringGameplay=false
		bUseDynamicIndexBuffer=true
		bUseDynamicIBWithHiddenFragments=true
		LightEnvironment=MyLightEnvironment
		bUsePrecomputedShadows=false
		bForceDirectLightMap=false
		LightingChannels=(bInitialized=true,Static=true,Dynamic=true)
	End Object
	Components.Remove(FracturedStaticMeshComponent0)
	Components.Add(MapEdFracMesh0)
	FracturedStaticMeshComponent=MapEdFracMesh0
	CollisionComponent=MapEdFracMesh0
	Begin Object Class=StaticMeshComponent Name=OverlayMesh0
		LightEnvironment=MyLightEnvironment
		bUsePrecomputedShadows=false
		bForceDirectLightMap=false
		CastShadow=false
		CollideActors=false
		BlockActors=false
		BlockZeroExtent=false
		BlockNonZeroExtent=false
		BlockRigidBody=false
	End Object
	Overlay=OverlayMesh0
}
