/**
 * Gives a map shipped under a new name (patchtool's map.shipAs) its base map's dropship intro (EXP-08, F-45).
 *
 * The intro's Kismet is in the streamed CIN_DropshipIntros. XGBattle.PlayCinTacticalIntro fires its
 * SeqEvent_OnTacticalIntro with the map's name, and Switch String nodes pick the landing by that exact name: for
 * URB_Bar, the dropship goes to URB_Bar's landing and CIN_PlayDS_03 plays it. An unknown name such as URB_BarBlank
 * falls through every switch to CIN_DS_Stop, and there is no landing.
 *
 * So at load, before the intro, this renames the base map's entry (IntroMapName) in those switches to this map's
 * name, in the running game's copy of the sequence only. Until it finds the switches it tries again every 0.05 s,
 * for up to MaxWait seconds, in case CIN_DropshipIntros' sequence joins the game's after this actor starts.
 */
class XComMapEdIntro extends Actor
	placeable;

/** The base map's name as the intro's switches know it, for example URB_Bar. */
var() string IntroMapName;
/** Seconds to keep looking for the switches. */
var() float MaxWait;
var transient float Waited;

simulated event PostBeginPlay()
{
	super.PostBeginPlay();
	if (!Alias())
		SetTimer(0.05, true, 'TryAgain');
}

function TryAgain()
{
	Waited += 0.05;
	if (Alias() || Waited >= MaxWait)
	{
		ClearTimer('TryAgain');
		if (Waited >= MaxWait)
			`log("XComMapEd:" @ self @ "WARNING: found no intro switch naming" @ IntroMapName @ "in" @ MaxWait @ "s; the intro will not play");
	}
}

/** Renames IntroMapName to this map's name in every Switch String of the game's sequence; true once one is done. */
function bool Alias()
{
	local Sequence Root;
	local array<SequenceObject> Found;
	local SeqCond_SwitchString S;
	local string MapName;
	local int i, k, nSwitches, nRenamed;

	Root = WorldInfo.GetGameSequence();
	if (Root == none || IntroMapName == "")
		return false;
	MapName = WorldInfo.GetMapName();
	Root.FindSeqObjectsByClass(class'SeqCond_SwitchString', true, Found);
	for (i = 0; i < Found.Length; i++)
	{
		S = SeqCond_SwitchString(Found[i]);
		if (S == none)
			continue;
		nSwitches++;
		for (k = 0; k < S.StringArray.Length; k++)
		{
			if (S.StringArray[k].StringName ~= IntroMapName)
			{
				S.StringArray[k].StringName = MapName;
				nRenamed++;
				`log("XComMapEd:" @ self @ "intro:" @ S @ "in" @ S.Outer @ "now plays" @ IntroMapName $ "'s case (" $ k $ ") for" @ MapName);
			}
		}
	}
	if (nRenamed > 0)
		`log("XComMapEd:" @ self @ "intro: renamed" @ nRenamed @ "case(s) of" @ nSwitches @ "switch(es) after" @ Waited @ "s");
	return nRenamed > 0;
}

defaultproperties
{
	MaxWait=30
	bHidden=true
}
