/**
 * Lights the pieces a patch adds like the map's own (findings register F-52, EXP-14 runs 7 to 12).
 *
 * A map's own pieces carry the light its editor baked. Copies and spawned pieces have none: a light environment lights
 * them while the game runs, as it lights units, and takes every light aimed at units. Every sky light found in the
 * game's maps is such a light. Its BSP and Static channels are off, so it lights no baked surface, and it fills the
 * units with a blue or lavender light. Most maps put it in Gameplay_1, which units have and our pieces don't. Temple
 * Ship's keeps CompositeDynamic, which every light environment with the Dynamic channel takes (run 6), so its copies
 * came out lavender beside the map's own pieces.
 *
 * Such a sky light (enabled, no BSP or Static channel, CompositeDynamic or Dynamic) is switched off when the first piece
 * registers, and an XComMapEdUnitSky with its brightness and colour lights the units in its place, on Gameplay_1 only.
 * Damage can't bring it back on our pieces. Runs 7 to 11 switched it off only while the pieces took their light, then
 * fixed that light; damage resets a piece's light environment, and a relight at the moment of damage came out lavender
 * all the same (run 11).
 *
 * Each registered piece's light environments take their light at once, even off screen, for FreeTime seconds, then
 * keep it (bDynamic off), as the map's baked pieces do. They trace their lights from their bounds' centre, the engine's
 * default: run 12 traced from the bounds' closest point (bTraceFromClosestBoundsPoint) for the black console of F-56,
 * which stayed black, and that setting lets a light behind a wall reach a piece standing against it.
 *
 * On other maps the sky lights are left alone. One per level: pieces added during a pass join it, later ones (after a
 * save is loaded) start another.
 */
class XComMapEdSkyFree extends Actor;

/** Seconds the pieces' light environments update freely before their light is fixed. */
var float FreeTime;
var transient bool bChecked;
/** The map's sky lights switched off, and the units-only lights in their place. */
var transient array<LightComponent> SkiesOff;
var transient array<XComMapEdUnitSky> UnitSkies;
/** The light environments taking their light in this pass. */
var transient array<DynamicLightEnvironmentComponent> Pending;

/** Registers Piece (one of the patch's copies or spawned pieces) with the level's XComMapEdSkyFree, made if needed. */
static function Add(Actor Caller, Actor Piece)
{
	local XComMapEdSkyFree F;

	if (Caller == none || Piece == none)
		return;
	foreach Caller.AllActors(class'XComMapEdSkyFree', F)
		break;
	if (F == none)
		F = Caller.Spawn(class'XComMapEdSkyFree');
	if (F != none)
		F.Register(Piece);
}

/** Has a piece take its light now (at load or after a load), without the sky lights that reach light environments. */
function Register(Actor A)
{
	local DynamicLightEnvironmentComponent E;
	local int n;

	if (!bChecked)
	{
		bChecked = true;
		SwapSkyLights();
	}
	foreach A.AllOwnedComponents(class'DynamicLightEnvironmentComponent', E)
	{
		if (Pending.Find(E) != INDEX_NONE)
			continue;
		E.bDynamic = true;
		E.InvisibleUpdateTime = 0;
		E.MinTimeBetweenFullUpdates = 0.1;
		E.ResetEnvironment();
		Pending.AddItem(E);
		n++;
	}
	if (n > 0 && !IsTimerActive('FixLight'))
		SetTimer(FreeTime, false, 'FixLight');
}

/**
 * Switches off each sky light that lights no baked surface but reaches light environments, and spawns a units-only
 * one in its place. Logs every sky light and the choice.
 */
function SwapSkyLights()
{
	local SkyLight S;
	local LightComponent L;
	local SkyLightComponent SL;
	local XComMapEdUnitSky U;
	local bool bSwap;

	// A loaded save may bring back the last load's units-only lights; the swap below makes them again.
	foreach AllActors(class'XComMapEdUnitSky', U)
		U.Destroy();
	foreach AllActors(class'SkyLight', S)
	{
		L = S.LightComponent;
		if (L == none)
			continue;
		bSwap = L.bEnabled && !L.LightingChannels.BSP && !L.LightingChannels.Static
			&& (L.LightingChannels.CompositeDynamic || L.LightingChannels.Dynamic);
		`log("XComMapEd:" @ self @ "sky light" @ S @ "brightness" @ L.Brightness @ "enabled" @ L.bEnabled @ "channels" @ ChannelsText(L.LightingChannels)
			$ (bSwap ? ": lights units only and reaches light environments; units take it on Gameplay_1 instead" : ": left as it is"));
		if (!bSwap)
			continue;
		U = Spawn(class'XComMapEdUnitSky');
		if (U == none || U.Sky == none)
		{
			`log("XComMapEd:" @ self @ "WARNING: could not spawn a units-only sky light;" @ S @ "left on");
			continue;
		}
		U.Sky.SetLightProperties(L.Brightness, L.LightColor);
		L.SetEnabled(false);
		SkiesOff.AddItem(L);
		UnitSkies.AddItem(U);
		SL = SkyLightComponent(L);
		`log("XComMapEd:" @ self @ S @ "switched off;" @ U @ "lights the units in its place: brightness" @ U.Sky.Brightness
			@ "colour" @ U.Sky.LightColor.R $ "," $ U.Sky.LightColor.G $ "," $ U.Sky.LightColor.B @ "channels" @ ChannelsText(U.Sky.LightingChannels)
			$ (SL != none ? "; lower hemisphere left out (" $ SL.LowerBrightness @ SL.LowerColor.R $ "," $ SL.LowerColor.G $ "," $ SL.LowerColor.B $ ")" : ""));
	}
	if (SkiesOff.Length == 0)
		`log("XComMapEd:" @ self @ "no sky light to swap in this map");
}

/** Fixes the pieces' light as taken, as a baked piece's. */
function FixLight()
{
	local int i;

	for (i = 0; i < Pending.Length; i++)
	{
		if (Pending[i] == none)
			continue;
		Pending[i].bDynamic = false;
		Pending[i].InvisibleUpdateTime = class'DynamicLightEnvironmentComponent'.default.InvisibleUpdateTime;
		Pending[i].MinTimeBetweenFullUpdates = class'DynamicLightEnvironmentComponent'.default.MinTimeBetweenFullUpdates;
	}
	`log("XComMapEd:" @ self @ "the light of" @ Pending.Length @ "light environments is fixed as taken");
	Pending.Length = 0;
}

/** A lighting channel set as text: the channels that matter here. */
static function string ChannelsText(LightingChannelContainer C)
{
	return "(" $ (C.BSP ? "BSP " : "") $ (C.Static ? "Static " : "") $ (C.Dynamic ? "Dynamic " : "")
		$ (C.CompositeDynamic ? "CompositeDynamic " : "") $ (C.Gameplay_1 ? "Gameplay_1 " : "") $ (C.Skybox ? "Skybox" : "") $ ")";
}

defaultproperties
{
	bHidden=true
	FreeTime=2.0
}
