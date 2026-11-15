/**
 * EXP-07 run 7 tile test (F-29): XComMapEdWall with the game's Firaxis-only bStaticCollision flag off, as on
 * destructibles. A runtime tile rebuild doesn't find wall copies above the ground on tiles that were empty in the
 * map's baked data; the game's wall and level-piece classes set bStaticCollision, its destructibles don't.
 */
class XComMapEdWallNoStatic extends XComMapEdWall;

defaultproperties
{
	bStaticCollision=false
}
