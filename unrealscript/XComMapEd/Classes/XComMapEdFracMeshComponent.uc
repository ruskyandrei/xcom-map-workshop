/**
 * The fractured mesh component of XComMapEdWall copies: a class of their own, so that the game's `set` console
 * command can switch on bCutoutMask for our copies only (EXP-07, findings register F-35). The cutaway trims a wall
 * down at floor height and cuts it out in front of the camera only when its main mesh has bCutoutMask, which the
 * editor sets on placed pieces. The UDK engine classes don't know the property, so script can't set it; `set`
 * looks it up in the game's own class at run time.
 */
class XComMapEdFracMeshComponent extends FracturedStaticMeshComponent;
