/**
 * A destructible object (car, crate, ...) made at run time from one of the game's XComDestructibleActor archetypes,
 * but lit dynamically, like a unit, instead of by the lightmap a level bakes for each placed copy.
 *
 * A copy spawned straight from the archetype keeps the archetype's static-lighting setup (bUsePrecomputedShadows,
 * from StaticMeshActor) with no lightmap of its own, so it renders black; ForceDLELighting can't change that, and the
 * flag is const in script (EXP-05). This class sets it off in its defaults and takes everything else that makes the
 * object behave like the original from the archetype: mesh, materials, toughness, cover and the damage and
 * destruction events.
 *
 * Level actors don't tick (bTickIsDisabled), and an actor that doesn't tick doesn't tick its components either, so its
 * light environment never computes any light. This one ticks.
 */
class XComMapEdDestructible extends XComDestructibleActor;

/** Explosion actions held back while a load applies the saved state, by DestroyedEvents index (see HoldBackBlasts). */
var transient array<XComDestructibleActor_Action> HeldBlasts;
/**
 * The other pieces of this copy's break group (XComMapEdCopier.LinkBreakGroups, the editor's "Break together"): when a
 * hit moves this copy to a worse damage state, each of them still in a better one is moved to it as well, as the
 * game's own linked pieces follow their parent (AffectedChildren). Damaged, then destroyed; never back.
 */
var transient array<XComDestructibleActor> BreakPartners;

function CopyFrom(XComDestructibleActor T)
{
	local int i;

	SetStaticMesh(T.StaticMeshComponent.StaticMesh);
	for (i = 0; i < T.StaticMeshComponent.Materials.Length; i++)
		StaticMeshComponent.SetMaterial(i, T.StaticMeshComponent.Materials[i]);
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
	// A collectible (mission loot, such as a UFO power core) destroys itself as soon as it is damaged: the game calls
	// XComCollectible.BecomeDamaged only on its own collectibles. With one health point the copy breaks at its first
	// damage too, with the original's destruction events. It is not a collectible, so it isn't loot.
	if (XComCollectible(T) != none)
	{
		TotalHealth = 1;
		Health = 1;
		`log("XComMapEd:" @ self @ "copied collectible" @ T @ "(type" @ XComCollectible(T).CollectibleType $ "): breaks at its first damage; not loot");
	}

	VisibilityBlockingData = T.VisibilityBlockingData;
	CoverForceFlag = T.CoverForceFlag;
	CoverIgnoreFlag = T.CoverIgnoreFlag;
	bAlwaysConsiderForCover = T.bAlwaysConsiderForCover;
	bCanClimbOver = T.bCanClimbOver;
	bCanClimbOnto = T.bCanClimbOnto;
	bIsValidDestination = T.bIsValidDestination;
	// The mouse picks through hidden, cut-away pieces; the game's roof-level pieces carry this flag (EXP-07 run 22, F-34).
	bIgnoreFor3DCursorCollision = T.bIgnoreFor3DCursorCollision;
	// The rebuild only takes actors with bPathColliding as floor and walls to stand on; XComFracLevelActor and
	// XComDestructibleActor default it to false and the editor sets it on placed pieces (EXP-07 run 20: the copied
	// roof slab gave no floor, F-30).
	bPathColliding = T.bPathColliding;
	bCanStepUpOn = T.bCanStepUpOn;
	bIgnoreForCover = T.bIgnoreForCover;
	bCanStepUpOn = T.bCanStepUpOn;
	// A unit can break through a window only if it is interactive. URB_Bar's windows (ComKitWindows archetypes) set
	// it; a copy spawned from the class defaults had it off, so the wing's windows couldn't be run through (EXP-07
	// run 30, F-40).
	bInteractive = T.bInteractive;
	bIgnoreForPathing = T.bIgnoreForPathing;
	Tag = T.Tag;
	TintColor = T.TintColor;
	// The game's destructibles start in their auto state, _Pristine; a window can be run through only there
	// (BreakWindow). A class compiled against the stubs never enters it (EXP-07 run 29: the copied windows can't be
	// run through, F-38). Its BeginState turns ticking off, so this comes before SetTickIsDisabled(false).
	if (GetStateName() == Class.Name)
		GotoState('_Pristine');
	UpdateTintColor();
	SetTickIsDisabled(false);
	if (Toughness != none && Toughness.bFragile)
		`log("XComMapEd:" @ self @ "copied glass" @ T @ "(" $ T.Tag $ "): interactive" @ bInteractive @ "ignore for pathing" @ bIgnoreForPathing
			@ "state" @ GetStateName());
}

/**
 * How the copy's light environment draws the light it gathers (F-52, EXP-14 runs 5 to 7).
 * - Mode 0 is the engine's default: the strongest light as one synthesized directional light, the rest as a two-colour
 *   sky light.
 * - Mode 1 is the game's setting for its doors (XComInteractiveLevelActor), which are lit the same live way among
 *   baked walls: no synthesized directional light, and all of it as a spherical-harmonic light.
 * - bBooleanShadow: the map's lights are shadowed by the static world with a cheap on/off test (the engine's default;
 *   XComDestructibleActor turns it off).
 * Neither changed much in the trials; what made copies match the map was leaving out its units-only sky light
 * (XComMapEdSkyFree). Also tried and dropped: the light environment's own lighting channels (with Dynamic it still
 * takes that sky light, without Dynamic no light at all). AmbientGlow showed nothing when set in play (EXP-14 run 5),
 * but that copy had stopped following light changes (below), so it is not yet really tried.
 * Setting these in play and reattaching the mesh left a copy no longer following light changes, so only
 * ResetEnvironment asks for a full update here.
 */
function SetLighting(byte Mode, bool bBooleanShadow)
{
	local DynamicLightEnvironmentComponent E;

	E = DynamicLightEnvironmentComponent(StaticMeshComponent.LightEnvironment);
	if (E == none)
	{
		`log("XComMapEd:" @ self @ "has no dynamic light environment to set");
		return;
	}
	E.bSynthesizeSHLight = Mode == 1;
	E.bSynthesizeDirectionalLight = Mode != 1;
	E.bUseBooleanEnvironmentShadowing = bBooleanShadow;
	E.ResetEnvironment();
}

/** The light environment's settings, as SetLighting sets them, for the log. */
function string LightingText()
{
	local DynamicLightEnvironmentComponent E;

	E = DynamicLightEnvironmentComponent(StaticMeshComponent.LightEnvironment);
	if (E == none)
		return "no dynamic light environment";
	return "SH light" @ E.bSynthesizeSHLight @ "directional" @ E.bSynthesizeDirectionalLight @ "boolean shadow" @ E.bUseBooleanEnvironmentShadowing
		@ "enabled" @ E.IsEnabled() @ "dynamic" @ E.bDynamic @ "mesh channels" @ class'XComMapEdSkyFree'.static.ChannelsText(StaticMeshComponent.LightingChannels);
}

/**
 * Logs every hit before the game applies it (EXP-05: which hits reach this car, and how hard), with the fire spots the
 * damage has collected so far (XComWorldData.PotentialFireColumns). An explosion starts its fires at some of these
 * once all its hits are dealt; a fire burning on a car destroys it at the next turn change.
 */
simulated function ApplyDamageToMe(const out DamageEvent Dmg)
{
	local XComWorldData World;
	local string Spots;
	local vector P;
	local int i;
	local name Before;

	World = class'XComWorldData'.static.GetWorldData();
	if (World != none)
		for (i = 0; i < World.PotentialFireColumns.Length; i++)
		{
			P = World.PotentialFireColumns[i];
			Spots = Spots @ "(" $ P $ (World.IsLocationFlammable(P) ? " flammable" : "") $ ")";
		}
	`log("XComMapEd:" @ self @ "hit by" @ Dmg.DamageType @ "amount" @ Dmg.DamageAmount @ "from" @ Dmg.DamageCauser @ "health" @ Health @ "of" @ TotalHealth @ "state" @ GetStateName() @ "fire spots so far" @ (World != none ? World.PotentialFireColumns.Length : -1) $ Spots);
	// The game changes the damage state inside this call (GotoState '_Damaged' or '_Destroyed').
	Before = GetStateName();
	super.ApplyDamageToMe(Dmg);
	// What the hit did: the game scales the damage by chance and by distance, and a piece is damaged at 3/4 of its
	// health or less (EXP-14 run 13: a grenade's hit left a low cover whole).
	`log("XComMapEd:" @ self @ "after the hit: health" @ Health @ "of" @ TotalHealth @ "state" @ GetStateName()
		$ (BreakPartners.Length > 0 ? (GetStateName() != Before ? "; its break partners follow" : "; its break partners stay as they are") : ""));
	if (GetStateName() != Before)
		BreakWithPartners();
}

/** Puts each break partner still in a better damage state than this copy in this copy's (damaged or destroyed). */
function BreakWithPartners()
{
	local int i;
	local name Worse;

	if (DamageRank(GetStateName()) == 0 || BreakPartners.Length == 0)
		return;
	Worse = DamageRank(GetStateName()) >= 2 ? '_Destroyed' : '_Damaged';
	for (i = 0; i < BreakPartners.Length; i++)
	{
		if (BreakPartners[i] == none || BreakPartners[i].bDeleteMe || DamageRank(BreakPartners[i].GetStateName()) >= DamageRank(Worse))
			continue;
		`log("XComMapEd:" @ self @ "is" @ GetStateName() $ "; its break partner" @ BreakPartners[i] @ "goes from" @ BreakPartners[i].GetStateName() @ "to" @ Worse);
		BreakPartners[i].GotoState(Worse);
	}
}

/** 0 for whole (_Pristine), 1 for damaged, 2 for destroyed (or Dead, after it). */
static function int DamageRank(name S)
{
	if (S == '_Damaged')
		return 1;
	if (S == '_Destroyed' || S == 'Dead')
		return 2;
	return 0;
}

/**
 * A save keeps only damaged destructibles. On load it can't match a spawned one to its record by name, so it recreates
 * it from the class defaults in place of the fresh one, under the same name: no mesh, materials or events (findings
 * register F-17). Then the spawner's Main already points here, which it never does during a normal spawn (it is set
 * after Spawn returns), and the spawner gives back what it took from the archetype before the saved state is applied.
 */
simulated event PostBeginPlay()
{
	local XComMapEdSpawner S;
	local XComMapEdCopier K;

	super.PostBeginPlay();
	foreach AllActors(class'XComMapEdSpawner', S)
		if (S.Main == self)
			S.RestoreLoaded(self);
	// A copy rebuilt by a load asks its copier to copy it again (F-17).
	foreach AllActors(class'XComMapEdCopier', K)
		if (K.RestoreLoaded(self))
			break;
}

/**
 * Applying a saved record replays the destruction actions that had fired, the explosion included, so a wreck would
 * blow up again on every load and damage its neighbours (EXP-05 run 16: car 8's wreck destroyed the burning car 7 at
 * load). So while the record is applied the explosion actions are taken out; ReleaseBlasts puts them back a second
 * later, marked as fired if the save says they had. A car saved burning, before its explosion, still explodes later.
 */
function HoldBackBlasts()
{
	local int i;

	HeldBlasts.Length = DestroyedEvents.Length;
	for (i = 0; i < DestroyedEvents.Length; i++)
	{
		if (XComDestructibleActor_Action_RadialDamage(DestroyedEvents[i].Action) != none)
		{
			HeldBlasts[i] = DestroyedEvents[i].Action;
			DestroyedEvents[i].Action = none;
		}
	}
	SetTimer(1.0, false, 'ReleaseBlasts');
}

function ReleaseBlasts()
{
	local int i;

	for (i = 0; i < HeldBlasts.Length; i++)
	{
		if (HeldBlasts[i] != none)
		{
			DestroyedEvents[i].Action = HeldBlasts[i];
			HeldBlasts[i].bActivated = i < DestroyedEventActivates.Length && DestroyedEventActivates[i] != 0;
		}
	}
	HeldBlasts.Length = 0;
}

/**
 * As the game's Dead state, but it keeps ticking: a car that is loaded straight into Dead would otherwise never compute
 * its light environment, and its wreck would render black (F-02).
 */
simulated state Dead
{
	ignores Tick;

	simulated event BeginState(name PreviousStateName)
	{
		bCurrentStateRequiresTick = false;
	}
}

defaultproperties
{
	bTickIsDisabled=false
	Begin Object Name=MyNEWLightEnvironment
		bEnabled=true
		bDynamic=true
	End Object
	// The main mesh, of our own class so that bCutoutMask can be switched on for copies only (F-35). Set up as the
	// parents' StaticMeshComponent0 (UDK StaticMeshActor's, the game's XComLevelActor's and XComDestructibleActor's
	// templates), lit by the copy's own light environment.
	Begin Object Class=XComMapEdMeshComponent Name=MapEdMesh0
		WireframeColor=(R=0,G=255,B=128,A=255)
		bAllowApproximateOcclusion=true
		RBChannel=RBCC_GameplayPhysics
		RBCollideWithChannels=(Default=true,GameplayPhysics=true,EffectPhysics=true,BlockingVolume=true)
		LightingChannels=(bInitialized=true,Static=true,Dynamic=true)
		LightEnvironment=MyNEWLightEnvironment
		bUsePrecomputedShadows=false
		bForceDirectLightMap=false
	End Object
	Components.Remove(StaticMeshComponent0)
	Components.Add(MapEdMesh0)
	StaticMeshComponent=MapEdMesh0
	CollisionComponent=MapEdMesh0
}
