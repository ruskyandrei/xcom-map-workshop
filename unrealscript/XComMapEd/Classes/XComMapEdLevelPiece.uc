/**
 * A working copy of one of the base map's plain level meshes (an XComLevelActor or StaticMeshActor placed in the
 * level: a floor slab, a ceiling part), made at run time by XComMapEdCopier (EXP-07).
 *
 * Lit dynamically, like XComMapEdDestructible: a copy has no lightmap of its own (findings register F-02). It takes
 * the source's mesh, materials, scale and, from an XComLevelActor, its cover, floor and line-of-sight settings.
 */
class XComMapEdLevelPiece extends XComLevelActor;

function CopyFrom(StaticMeshActor T)
{
	local XComLevelActor L;
	local int i;

	StaticMeshComponent.SetStaticMesh(T.StaticMeshComponent.StaticMesh, true);
	for (i = 0; i < T.StaticMeshComponent.Materials.Length; i++)
		StaticMeshComponent.SetMaterial(i, T.StaticMeshComponent.Materials[i]);
	StaticMeshComponent.bCastDynamicShadow = T.StaticMeshComponent.bCastDynamicShadow;
	SetDrawScale(T.DrawScale);
	SetDrawScale3D(T.DrawScale3D);
	// The rebuild only takes actors with bPathColliding as floor and walls to stand on; XComFracLevelActor and
	// XComDestructibleActor default it to false and the editor sets it on placed pieces (EXP-07 run 20: the copied
	// roof slab gave no floor, F-30).
	bPathColliding = T.bPathColliding;
	bCanStepUpOn = T.bCanStepUpOn;
	ReattachComponent(StaticMeshComponent);
	L = XComLevelActor(T);
	if (L != none)
	{
		VisibilityBlockingData = L.VisibilityBlockingData;
		CoverForceFlag = L.CoverForceFlag;
		CoverIgnoreFlag = L.CoverIgnoreFlag;
		bAlwaysConsiderForCover = L.bAlwaysConsiderForCover;
		bCanClimbOver = L.bCanClimbOver;
		bCanClimbOnto = L.bCanClimbOnto;
		bIsValidDestination = L.bIsValidDestination;
		bIgnoreForCover = L.bIgnoreForCover;
		bCanStepUpOn = L.bCanStepUpOn;
		bIgnoreFor3DCursorCollision = L.bIgnoreFor3DCursorCollision;
		TintColor = L.TintColor;
		UpdateTintColor();
	}
	Tag = T.Tag;
	SetTickIsDisabled(false);
}

/** A fractured piece's mesh drawn whole as a plain static mesh (EXP-07 lighting test), with its cover and vision settings. */
function CopyFromFrac(XComFracLevelActor T)
{
	local int i;

	StaticMeshComponent.SetStaticMesh(T.FracturedStaticMeshComponent.StaticMesh, true);
	for (i = 0; i < T.FracturedStaticMeshComponent.Materials.Length; i++)
		StaticMeshComponent.SetMaterial(i, T.FracturedStaticMeshComponent.Materials[i]);
	SetDrawScale(T.DrawScale);
	SetDrawScale3D(T.DrawScale3D);
	ReattachComponent(StaticMeshComponent);
	VisibilityBlockingData = T.VisibilityBlockingData;
	CoverForceFlag = T.CoverForceFlag;
	CoverIgnoreFlag = T.CoverIgnoreFlag;
	bAlwaysConsiderForCover = T.bAlwaysConsiderForCover;
	bIgnoreForCover = T.bIgnoreForCover;
	// The mouse picks through hidden, cut-away pieces; the game's roof-level pieces carry this flag (EXP-07 run 22, F-34).
	bIgnoreFor3DCursorCollision = T.bIgnoreFor3DCursorCollision;
	// The rebuild only takes actors with bPathColliding as floor and walls to stand on; XComFracLevelActor and
	// XComDestructibleActor default it to false and the editor sets it on placed pieces (EXP-07 run 20: the copied
	// roof slab gave no floor, F-30).
	bPathColliding = T.bPathColliding;
	bCanStepUpOn = T.bCanStepUpOn;
	Tag = T.Tag;
	SetTickIsDisabled(false);
}

/** Logs how this copy is lit (EXP-07: the lit reference for XComMapEdWall's lighting). */
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
			@ "tick disabled" @ bTickIsDisabled);
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
	Begin Object Class=DynamicLightEnvironmentComponent Name=MyLightEnvironment
		bEnabled=true
		bDynamic=true
		bForceNonCompositeDynamicLights=true
	End Object
	Components.Add(MyLightEnvironment)
	Begin Object Name=StaticMeshComponent0
		LightEnvironment=MyLightEnvironment
		bUsePrecomputedShadows=false
		bForceDirectLightMap=false
	End Object
}
