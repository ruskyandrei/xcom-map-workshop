/**
 * The overview view, a lab aid for overview screenshots of a patched map (EXP-07 runs 33-35; patchtool's photo object).
 * The authoring UDK can't open Firaxis maps, so an overview has to come from the game itself. A short while after load,
 * and again every few seconds:
 * - the overhead camera's defaults become FOV, Distance and Pitch, through the game's own
 *   XGCameraView.ChangeOverheadCameraDefaults (what the cheat SetOverheadCameraParameters calls). A negative pitch
 *   looks down (run 33: +55 put the camera under the map, looking up);
 * - an XComMapEdSun lights the whole map: a dynamic directional light of brightness Sun from SunYaw, SunPitch degrees
 *   down, and a sky light of brightness Sky. A night map otherwise stays dark: the post-process highlights and mid
 *   tones (Highlights, MidTones) did nothing visible on their own (run 34). They are still applied, as in the shot kept
 *   as the default (run 35);
 * - with bHideUI, the game's UI screens are hidden as for a cinematic (XComPresentationLayerBase.HideUIForCinematics).
 *
 * The defaults are run 35's settings: from the front of URB_Bar's L layout, the whole map in view.
 */
class XComMapEdPhoto extends Actor
	placeable;

var() float FOV, Distance, Pitch;
var() float Sun, Sky, SunYaw, SunPitch;
var() float Highlights, MidTones;
var() bool bHideUI;
var transient int Times;
var transient XComMapEdSun Light;
/** The brightened settings, laid over the view each tick through the player camera (which resets its override every frame). */
var transient PostProcessSettings Settings;
var transient bool bTickSettings;

simulated event PostBeginPlay()
{
	super.PostBeginPlay();
	SetTimer(2.0, false, 'Apply');
}

function Apply()
{
	local PostProcessVolume V;
	local XComPresentationLayerBase P;
	local rotator R;
	local int n;

	if (Distance > 0)
		class'XGCameraView'.static.ChangeOverheadCameraDefaults(FOV, Distance, Pitch);
	if (Highlights > 0)
	{
		Brighten(WorldInfo.DefaultPostProcessSettings);
		Settings = WorldInfo.DefaultPostProcessSettings;
		if (!bTickSettings)
		{
			bTickSettings = true;
			SetTickGroup(TG_PostUpdateWork);
		}
		foreach AllActors(class'PostProcessVolume', V)
		{
			Brighten(V.Settings);
			n++;
		}
	}
	if ((Sun > 0 || Sky > 0) && Light == none)
	{
		R.Pitch = -int(SunPitch * 65536.0 / 360.0);
		R.Yaw = int(SunYaw * 65536.0 / 360.0);
		R.Roll = 0;
		Light = Spawn(class'XComMapEdSun', , , Location + vect(0, 0, 2000), R);
		if (Light != none)
			Light.Setup(Sun, Sky);
	}
	if (bHideUI)
		foreach AllActors(class'XComPresentationLayerBase', P)
			P.HideUIForCinematics();
	`log("XComMapEd:" @ self @ "photo view: camera FOV" @ FOV @ "distance" @ Distance @ "pitch" @ Pitch $ "; light" @ Light @ "sun" @ Sun
		@ "sky" @ Sky @ "from yaw" @ SunYaw @ "pitch" @ SunPitch $ "; highlights" @ Highlights @ "mid tones" @ MidTones @ "on the defaults and"
		@ n @ "post-process volume(s); UI hidden" @ bHideUI);
	Times++;
	if (Times == 1)
		SetTimer(6.0, false, 'Apply');
	else if (Times == 2)
		SetTimer(12.0, false, 'Apply');
	else
		SetTimer(10.0, false, 'Apply');
}

event Tick(float DeltaTime)
{
	local PlayerController PC;

	if (!bTickSettings)
		return;
	foreach LocalPlayerControllers(class'PlayerController', PC)
		if (PC.PlayerCamera != none)
		{
			PC.PlayerCamera.CamPostProcessSettings = Settings;
			PC.PlayerCamera.CamOverridePostProcessAlpha = 1.0;
		}
}

function Brighten(out PostProcessSettings S)
{
	S.bOverride_Scene_HighLights = true;
	S.Scene_HighLights = vect(1, 1, 1) * Highlights;
	if (MidTones > 0)
	{
		S.bOverride_Scene_MidTones = true;
		S.Scene_MidTones = vect(1, 1, 1) * MidTones;
	}
}

defaultproperties
{
	FOV=45
	Distance=7000
	Pitch=-55
	Sun=1.2
	Sky=0.5
	SunYaw=138
	SunPitch=50
	Highlights=1.6
	MidTones=1.5
	bHideUI=true
	bHidden=true
}
