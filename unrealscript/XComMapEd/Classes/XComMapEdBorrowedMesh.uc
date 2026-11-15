/**
 * Shows game art that is already loaded, normally from the base map a patch streams into, so the art keeps its
 * own, precompiled game materials, which a cooked copy of it would lose (EXP-05).
 *
 * Firaxis maps put a mesh's materials on the placed component, not on the mesh, so a bare mesh renders flat grey.
 * The best source is therefore an actor or archetype that already wears the mesh, given by CopyFromPath, for example
 * 'VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1' while URB_Bar is loaded: its first static mesh
 * component's mesh and materials are copied. MeshPath and MaterialPaths name a mesh and materials directly.
 *
 * Purely visual: no collision, no cover. Put a hidden cover patch next to it for gameplay.
 * The StaticMesh set in the editor is only a placeholder; it stays visible if nothing is found.
 */
class XComMapEdBorrowedMesh extends DynamicSMActor
	placeable;

/** Full path of an actor or archetype in memory whose mesh and materials to copy: Package.Group.Name. */
var() string CopyFromPath;
/** Full path of a StaticMesh in memory; used when CopyFromPath is empty or not found. */
var() string MeshPath;
/** Materials by element index, full paths of materials in memory; applied last, empty entries are skipped. */
var() array<string> MaterialPaths;

simulated event PostBeginPlay()
{
	local Actor Source;
	local StaticMeshComponent From;
	local StaticMesh Mesh;
	local MaterialInterface Mat;
	local int i;

	super.PostBeginPlay();
	if (CopyFromPath != "")
	{
		Source = Actor(FindObject(CopyFromPath, class'Actor'));
		if (Source == none)
			`log("XComMapEd:" @ self @ "did not find actor" @ CopyFromPath);
		else
		{
			for (i = 0; i < Source.Components.Length && From == none; i++)
			{
				From = StaticMeshComponent(Source.Components[i]);
				if (From != none && From.StaticMesh == none)
					From = none;
			}
			if (From == none)
				`log("XComMapEd:" @ self @ "found no static mesh on" @ CopyFromPath);
		}
	}
	if (From != none)
		Mesh = From.StaticMesh;
	else if (MeshPath != "")
		Mesh = StaticMesh(FindObject(MeshPath, class'StaticMesh'));
	if (Mesh == none)
	{
		`log("XComMapEd:" @ self @ "found no mesh (CopyFromPath" @ CopyFromPath $ ", MeshPath" @ MeshPath $ "); keeping the placeholder");
		return;
	}
	StaticMeshComponent.SetStaticMesh(Mesh, true);
	if (From != none)
	{
		for (i = 0; i < From.Materials.Length; i++)
		{
			if (From.Materials[i] != none)
				StaticMeshComponent.SetMaterial(i, From.Materials[i]);
		}
	}
	for (i = 0; i < MaterialPaths.Length; i++)
	{
		if (MaterialPaths[i] == "")
			continue;
		Mat = MaterialInterface(FindObject(MaterialPaths[i], class'MaterialInterface'));
		if (Mat != none)
			StaticMeshComponent.SetMaterial(i, Mat);
		else
			`log("XComMapEd:" @ self @ "did not find material" @ MaterialPaths[i]);
	}
	LightEnvironment.SetEnabled(true);
	`log("XComMapEd:" @ self @ "now shows" @ PathName(Mesh) @ (From != none ? "with the materials of " $ PathName(From) : ""));
}

defaultproperties
{
	Begin Object Name=StaticMeshComponent0
		CollideActors=false
		BlockActors=false
		BlockZeroExtent=false
		BlockNonZeroExtent=false
		BlockRigidBody=false
	End Object
	bCollideActors=false
	bBlockActors=false
	CollisionType=COLLIDE_NoCollision
}
