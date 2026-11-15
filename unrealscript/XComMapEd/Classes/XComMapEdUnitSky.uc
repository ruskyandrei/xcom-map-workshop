/**
 * A sky light for units only, spawned in place of a map's sky light that light environments take (XComMapEdSkyFree,
 * F-52, EXP-14 run 12). Its one channel is Gameplay_1: the units' meshes have it (XComUnitPawn's default mesh is
 * Dynamic and Gameplay_1), our pieces' light environments don't. Most maps set their own sky lights up so.
 *
 * The lower hemisphere is const and can't be set at run time, so it is left out (Temple Ship's is 0.01).
 */
class XComMapEdUnitSky extends Actor;

var() SkyLightComponent Sky;

defaultproperties
{
	Begin Object Class=SkyLightComponent Name=UnitSkyComponent0
		Brightness=0.3
		LowerBrightness=0
		LightColor=(R=255,G=255,B=255,A=255)
		CastShadows=false
		CastDynamicShadows=false
		UseDirectLightMap=false
		LightingChannels=(bInitialized=true,BSP=false,Static=false,Dynamic=false,CompositeDynamic=false,Gameplay_1=true)
		LightAffectsClassification=LAC_DYNAMIC_AFFECTING
	End Object
	Sky=UnitSkyComponent0
	Components.Add(UnitSkyComponent0)
	bStatic=false
	bMovable=true
	bNoDelete=false
	bHidden=true
}
