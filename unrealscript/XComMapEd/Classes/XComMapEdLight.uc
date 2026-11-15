/**
 * A movable point light that can be spawned at run time (EXP-07 lighting tests). The engine's PointLightMovable
 * can't: like every Light it is bNoDelete, and Spawn refuses those ("could not spawn the test light", run 3).
 */
class XComMapEdLight extends Actor;

var() PointLightComponent Light;

function Setup(float Radius, float Brightness)
{
	Light.Radius = Radius;
	Light.SetLightProperties(Brightness);
}

defaultproperties
{
	Begin Object Class=PointLightComponent Name=PointLightComponent0
		Radius=400
		Brightness=3
		LightColor=(R=255,G=232,B=200,A=255)
		CastShadows=false
		CastDynamicShadows=false
		UseDirectLightMap=false
		LightingChannels=(bInitialized=true,Dynamic=true)
		LightAffectsClassification=LAC_DYNAMIC_AND_STATIC_AFFECTING
	End Object
	Light=PointLightComponent0
	Components.Add(PointLightComponent0)
	bStatic=false
	bMovable=true
	bNoDelete=false
	bHidden=true
}
