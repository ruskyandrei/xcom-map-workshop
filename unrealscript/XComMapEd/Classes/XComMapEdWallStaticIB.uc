/**
 * EXP-07 run 4 lighting variant of XComMapEdWall: the fractured mesh is drawn with its static index buffer, not the
 * dynamic one the game's fractured pieces use (F-28: is the dynamic drawing path what renders the copies black?).
 */
class XComMapEdWallStaticIB extends XComMapEdWall;

defaultproperties
{
	Begin Object Name=MapEdFracMesh0
		bUseDynamicIndexBuffer=false
		bUseDynamicIBWithHiddenFragments=false
	End Object
}
