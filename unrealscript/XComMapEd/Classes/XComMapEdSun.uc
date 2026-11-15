/**
 * A map-wide light, all dynamic: a directional light and a sky light, on every lighting channel, so they reach the
 * map's static meshes as well as the dynamic copies and units. The actor's rotation is the sun's direction.
 *
 * - Placed by patchtool's sun object (EXP-08: the blank map's only light, after the hider took the base map's out),
 *   with SunBrightness and SkyBrightness.
 * - Spawned by XComMapEdPhoto for overview screenshots (EXP-07 run 35, a lab aid), which calls Setup itself.
 *   URB_Bar is a night map, and brightening its post-process settings did nothing visible (run 34).
 *
 * A plain Actor with light components, as XComMapEdLight: every Light class is bNoDelete and can't be spawned.
 */
class XComMapEdSun extends Actor
	placeable;

var() DirectionalLightComponent Sun;
var() SkyLightComponent Sky;
/** Brightness of the directional light and of the sky light (0: off), applied at load. */
var() float SunBrightness, SkyBrightness;

simulated event PostBeginPlay()
{
	super.PostBeginPlay();
	Setup(SunBrightness, SkyBrightness);
	`log("XComMapEd:" @ self @ "sun" @ SunBrightness @ "sky" @ SkyBrightness @ "from rotation" @ Rotation);
}

function Setup(float NewSun, float NewSky)
{
	SunBrightness = NewSun;
	SkyBrightness = NewSky;
	Sun.SetEnabled(NewSun > 0);
	if (NewSun > 0)
		Sun.SetLightProperties(NewSun);
	Sky.SetEnabled(NewSky > 0);
	if (NewSky > 0)
		Sky.SetLightProperties(NewSky);
}

defaultproperties
{
	SunBrightness=1.2
	SkyBrightness=0.5
	Begin Object Class=DirectionalLightComponent Name=SunComponent0
		Brightness=1.2
		LightColor=(R=240,G=242,B=255,A=255)
		CastShadows=false
		CastDynamicShadows=false
		UseDirectLightMap=false
		LightingChannels=(bInitialized=true,BSP=true,Static=true,Dynamic=true,CompositeDynamic=true)
		LightAffectsClassification=LAC_DYNAMIC_AND_STATIC_AFFECTING
	End Object
	Sun=SunComponent0
	Components.Add(SunComponent0)
	Begin Object Class=SkyLightComponent Name=SkyComponent0
		Brightness=0.5
		LowerBrightness=0.2
		LightColor=(R=210,G=220,B=255,A=255)
		CastShadows=false
		CastDynamicShadows=false
		UseDirectLightMap=false
		LightingChannels=(bInitialized=true,BSP=true,Static=true,Dynamic=true,CompositeDynamic=true)
		LightAffectsClassification=LAC_DYNAMIC_AND_STATIC_AFFECTING
	End Object
	Sky=SkyComponent0
	Components.Add(SkyComponent0)
	bStatic=false
	bMovable=true
	bNoDelete=false
	bHidden=true
}
