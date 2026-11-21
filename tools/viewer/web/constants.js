// The game's grid, written once for the page (review finding 56): a tile is 96 units across, a level 64 units up (a
// storey of a building is three levels: floors.js STOREY_HEIGHT), and a quarter turn is 16384 of an Unreal rotator's
// 65536. tools/editor/compiler.py has the same numbers on the Build's side. A map's own actors are named in its
// persistent level (PL: the name each begins with), as a new actor of the map's (a cover block, a recipe light) is.
export const TILE = 96, LEVEL = 64, QUARTER = 16384;
export const PL = 'TheWorld.PersistentLevel.';
