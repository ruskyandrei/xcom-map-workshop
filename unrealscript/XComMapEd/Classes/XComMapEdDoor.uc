/**
 * A copy of a door the base map placed (XComInteractiveLevelActor), so that a remixed layout can have doors while the
 * base map keeps its own (EXP-07 L layout: the bar still stands, and its wing needs doors in its copied frames).
 * XComMapEdCopier spawns it with bCopyDoors and fills it from its source: mesh, animations, interaction points,
 * damage and destruction events, toughness and cover. The tile rebuild over the copies then gives it interaction
 * points (where units open or kick it), as it does a moved door.
 *
 * After a load the game rebuilds a saved door bare, under its saved name (findings register F-17); PostBeginPlay asks
 * the copiers to fill it again before the saved record (open or closed, health) is applied.
 */
class XComMapEdDoor extends XComInteractiveLevelActor;

function CopyFrom(XComInteractiveLevelActor T)
{
	local SkeletalMeshComponent S;
	local int i;

	// The interaction data before the animation tree: the door looks up its animations when the tree starts.
	InteractionPoints = T.InteractionPoints;
	IconSocket = T.IconSocket;
	InteractionPrompt = T.InteractionPrompt;
	ActiveIdleAnim = T.ActiveIdleAnim;
	AnimNodeName = T.AnimNodeName;
	bUseRMATranslation = T.bUseRMATranslation;
	bUseRMARotation = T.bUseRMARotation;
	bTouchActivated = T.bTouchActivated;
	InteractRemoteEvent = T.InteractRemoteEvent;
	InteractionHandler = T.InteractionHandler;
	// The game works this out in PostBeginPlay (native CacheMustDestroy, 0xA5E740): a door must be destroyed, and can't
	// be opened, unless one of its interaction points has a unit animation. That ran during Spawn, before this copy had
	// any interaction points, so every copy came out must-destroy (EXP-07 run 28: "can't open the doors", F-37).
	bMustDestroy = true;
	for (i = 0; i < InteractionPoints.Length; i++)
		if (int(InteractionPoints[i].UnitInteractionAnim) != 0)
			bMustDestroy = false;

	// As XComMapEdDestructible copies a destructible.
	DamagedEvents = T.DamagedEvents;
	DestroyedEvents = T.DestroyedEvents;
	// The actions act on their outer, so this copy needs its own.
	for (i = 0; i < DamagedEvents.Length; i++)
		if (DamagedEvents[i].Action != none)
			DamagedEvents[i].Action = new(self) DamagedEvents[i].Action.Class (DamagedEvents[i].Action);
	for (i = 0; i < DestroyedEvents.Length; i++)
		if (DestroyedEvents[i].Action != none)
			DestroyedEvents[i].Action = new(self) DestroyedEvents[i].Action.Class (DestroyedEvents[i].Action);
	m_kAOEDamageMaterial = T.m_kAOEDamageMaterial;
	TimeBeforeDeath = T.TimeBeforeDeath;
	DestroyedDamageClass = T.DestroyedDamageClass;
	Toughness = T.Toughness;
	// PostBeginPlay ran during Spawn, before the toughness was known.
	TotalHealth = Toughness != none ? Toughness.Health : class'XComDestructibleActor_Toughness'.default.Health;
	Health = TotalHealth;
	VisibilityBlockingData = T.VisibilityBlockingData;
	CoverForceFlag = T.CoverForceFlag;
	CoverIgnoreFlag = T.CoverIgnoreFlag;
	bAlwaysConsiderForCover = T.bAlwaysConsiderForCover;
	bCanClimbOver = T.bCanClimbOver;
	bCanClimbOnto = T.bCanClimbOnto;
	bIsValidDestination = T.bIsValidDestination;
	bIgnoreFor3DCursorCollision = T.bIgnoreFor3DCursorCollision;
	bPathColliding = T.bPathColliding;
	bCanStepUpOn = T.bCanStepUpOn;
	bIgnoreForCover = T.bIgnoreForCover;
	Tag = T.Tag;
	TintColor = T.TintColor;

	// The door itself: a skeletal mesh with its physics asset (collision), animation sets and tree.
	S = T.SkeletalMeshComponent;
	SkeletalMeshComponent.SetSkeletalMesh(S.SkeletalMesh);
	SkeletalMeshComponent.SetPhysicsAsset(S.PhysicsAsset);
	SkeletalMeshComponent.AnimSets = S.AnimSets;
	for (i = 0; i < S.Materials.Length; i++)
		SkeletalMeshComponent.SetMaterial(i, S.Materials[i]);
	SkeletalMeshComponent.SetAnimTreeTemplate(S.AnimTreeTemplate);
	ReattachComponent(SkeletalMeshComponent);
	// The game's doors start in their auto state, _Pristine, and can be opened only there (CanInteract). A class
	// compiled against the stubs, which declare no states, never enters it (EXP-07 run 29 logged "state
	// XComMapEdDoor": the doors can't be opened, F-38).
	if (GetStateName() == Class.Name)
		GotoState('_Pristine');
	UpdateTintColor();
	SetTickIsDisabled(false);
	`log("XComMapEd:" @ self @ "copied door" @ T @ "(" $ S.SkeletalMesh $ "," @ InteractionPoints.Length @ "interaction points, tree"
		@ S.AnimTreeTemplate $ ", must destroy" @ bMustDestroy @ "(source" @ T.bMustDestroy $ "), state" @ GetStateName() $ ")");
}

/** A door copy rebuilt by a load asks its copier to copy it again (F-17). */
simulated event PostBeginPlay()
{
	local XComMapEdCopier K;

	super.PostBeginPlay();
	foreach AllActors(class'XComMapEdCopier', K)
		if (K.RestoreLoaded(self))
			break;
}
