/**
 * The static mesh component of XComMapEdDestructible copies (windows, door frames): a class of their own, so that the
 * game's `set` console command can switch on bCutoutMask for our copies only, as XComMapEdFracMeshComponent does for
 * the wall copies (EXP-07, findings register F-35).
 */
class XComMapEdMeshComponent extends StaticMeshComponent;
