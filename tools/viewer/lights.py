"""Placed light records: game-space values over the UDK engine's class defaults.

Records stay in game units (Z up, native rotators); the viewer converts them at the
render boundary. A map's baked lightmaps are not decoded: the viewer lights everything
dynamically from these records instead.
"""
import math
from pathlib import Path
import sys

from export_math import forward

# UDK 2011-09 Engine/Classes defaultproperties, for values a placed component leaves unset.
# Its archetypes are engine imports, so the package itself never holds these.
LIGHT_DEFAULTS = dict(Brightness=1.0, LightColor=[1.0, 1.0, 1.0, 1.0], bEnabled=True, CastShadows=True)
COMPONENT_DEFAULTS = {
    "PointLightComponent": dict(Radius=1024.0, FalloffExponent=2.0),
    "SpotLightComponent": dict(Radius=1024.0, FalloffExponent=2.0, InnerConeAngle=0.0, OuterConeAngle=44.0),
    "SkyLightComponent": dict(LowerBrightness=0.0, LowerColor=[1.0, 1.0, 1.0, 1.0], CastShadows=False),
    "DirectionalLightComponent": {},
    "DominantDirectionalLightComponent": {},
}
KINDS = {"PointLightComponent": "point", "SpotLightComponent": "spot", "SkyLightComponent": "sky",
         "DirectionalLightComponent": "directional", "DominantDirectionalLightComponent": "directional"}
# SpotLight and DirectionalLight (and their subclasses) point straight down by default.
DOWN = [-16384, 0, 0]
ACTOR_ROTATION = {"SpotLight": DOWN, "SpotLightToggleable": DOWN, "SpotLightMovable": DOWN,
                  "GeneratedMeshAreaLight": DOWN, "DirectionalLight": DOWN, "DominantDirectionalLight": DOWN}
# Lightmass makes these for emissive surfaces; in game they reach only dynamic objects,
# and static surfaces get the same light from the bake.
ROLES = {"GeneratedMeshAreaLight": "area", "DominantDirectionalLight": "dominant", "SkyLight": "sky",
         "SpotLightToggleable": "toggleable"}


def effective_cone(inner, outer):
    """A spot light's effective (inner, outer) cone half-angles in radians, from its stored degrees: UE3 clamps the
    inner cone to 0..89 degrees and the outer cone to just above the inner one and below 90 (editor lights plan, 2.7
    and 9.2). Stored values stay as stored; light is computed and drawn with these. Its twin is effectiveCone in
    web/light_rules.js, both tested against tests/cone_cases.json."""
    i = math.radians(min(max(float(inner), 0.0), 89.0))
    o = min(max(math.radians(float(outer)), i + 0.001), math.radians(89.99))
    return i, o


def effective_cone_degrees(inner, outer):
    """effective_cone in degrees."""
    return tuple(math.degrees(v) for v in effective_cone(inner, outer))


def storable_cone(inner, outer):
    """A spot light's (inner, outer) cone in degrees as a light the Build makes may hold it (the compiler's ranges:
    inner 0 to 89, outer 0 to 89.99, inner no wider than outer), lighting as the stored cone does: the stored values
    when they are in range, else the effective cone (a map's stored 100 or 580 lights as 89.99). A prefab's lights are
    made lights, so a map light copied into one takes this. Its twin is storableCone in web/light_rules.js."""
    if 0.0 <= float(inner) <= 89.0 and float(inner) <= float(outer) <= 89.99:
        return inner, outer
    i, o = effective_cone_degrees(inner, outer)
    i = min(round(i, 4), 89.0)
    return i, min(max(round(o, 4), i), 89.99)


def light_record(p, actor, prefix="", layer="base"):
    """The actor's light component as a record, or None when it has no supported one."""
    component = p.own(actor, "LightComponent", 0)
    if component <= 0: return None
    cls = p.cls(component)
    if cls not in KINDS: raise ValueError(f"Unsupported light component {cls}")
    for key in ("Translation", "Rotation", "AbsoluteTranslation", "AbsoluteRotation"):
        if p.effective(component, key) not in (None, False, [0, 0, 0], [0.0, 0.0, 0.0]):
            raise ValueError(f"Unsupported light component {key}")
    defaults = {**LIGHT_DEFAULTS, **COMPONENT_DEFAULTS[cls]}
    def value(key): return p.effective(component, key, defaults.get(key))
    actor_class = p.cls(actor)
    rotation = p.effective(actor, "Rotation", ACTOR_ROTATION.get(actor_class, [0, 0, 0]))
    record = dict(id=f"{prefix}light:{actor}", actor=p.name(actor), component=p.name(component),
                  actorClass=actor_class, componentClass=cls, sourcePackage=p.path.stem, layer=layer,
                  kind=KINDS[cls], role=ROLES.get(actor_class, "static"),
                  location=p.effective(actor, "Location", [0, 0, 0]), rotation=rotation,
                  direction=forward(rotation), color=value("LightColor")[:3], brightness=value("Brightness"),
                  enabled=bool(value("bEnabled")), castShadows=bool(value("CastShadows")))
    if record["kind"] in ("point", "spot"):
        record.update(radius=value("Radius"), falloffExponent=value("FalloffExponent"))
    if record["kind"] == "spot":
        record.update(innerConeAngle=value("InnerConeAngle"), outerConeAngle=value("OuterConeAngle"))
    if record["kind"] == "sky":
        record.update(lowerColor=value("LowerColor")[:3], lowerBrightness=value("LowerBrightness"))
    return record


def light_records(p, actors, prefix="", layer="base", warn=None):
    records = []
    for actor in actors:
        if p.own(actor, "LightComponent") is None: continue
        try:
            record = light_record(p, actor, prefix, layer)
            if record: records.append(record)
        except ValueError as error:
            if warn: warn(p.name(actor), error)
    return records


def guid_hex(value):
    """A saved Guid struct as 32 lower-case hex digits (relight.guid_hex), None when not saved."""
    return bytes(value).hex() if isinstance(value, (bytes, bytearray)) and len(value) == 16 else None


def toggle_light_actions(p):
    """Light actor (export index) -> the destructible actions that switch it, as "<actor> ToggleLight (<action>)"
    (editor lights plan 2.4: URB_Bar's XComDestructibleActor_14 switches SpotLightToggleable_2 off when it breaks)."""
    out = {}
    for i in range(1, len(p.exports) + 1):
        if 'ToggleLight' not in p.cls(i): continue
        try:
            props = p.properties(i)[0]
        except Exception:      # an action whose properties don't read names no light we can tell
            continue
        owner = p.name(p.exports[i - 1]['outer']).rsplit('.', 1)[-1]
        for (key, _), item in props.items():
            if item['kind'] == 'ObjectProperty' and isinstance(item['value'], int) and item['value'] > 0:
                out.setdefault(item['value'], []).append(f"{owner} ToggleLight ({p.name(i).rsplit('.', 1)[-1]})")
    return out


def light_metadata(p, lights, objects, kismet, warn=None):
    """Export 18's light fields (editor lights plan 4.1 and 9.3), added to each record of `lights` (this package's):
    its GUIDs, the objects (of `objects`, this package's, by id) whose LOD-0 lightmap lists either GUID (`bakedInto`)
    or whose LOD-0 shadow map names its LightGuid (`shadowMapped`), whether it picks its lighting channels
    (`channels`), which properties its component saves (`saved`) and what names it (`referencedBy`: `kismet`, the
    package's Kismet references by actor export index, and destructibles' ToggleLight actions). A component whose
    lightmap records don't read (a skeletal mesh) lists no light."""
    upk = str(Path(__file__).resolve().parents[1] / 'upk')
    if upk not in sys.path: sys.path.append(upk)
    import lighting_records
    listed, shadowed = {}, {}
    for obj in objects:
        ci = p.by_name.get(obj['component'])
        if not ci or 'StaticMeshComponent' not in p.cls(ci): continue
        try:
            lods = lighting_records.component_record(p, ci)['lods']
        except Exception as error:
            if warn: warn(obj['component'], f'lightmap record not read: {error}')
            continue
        if not lods: continue
        for guid in lods[0]['lightmap'].get('lightGuids') or []:
            listed.setdefault(guid, set()).add(obj['id'])
        for sm in lods[0]['shadowMaps']:
            if sm > 0:
                guid = guid_hex(p.own(sm, 'LightGuid'))
                if guid: shadowed.setdefault(guid, set()).add(obj['id'])
    toggles = toggle_light_actions(p)
    for record in lights:
        ci, ai = p.by_name.get(record['component']), p.by_name.get(record['actor'])
        if not ci or not ai: continue
        props = p.properties(ci)[0]
        lightmap, light = guid_hex(p.own(ci, 'LightmapGuid')), guid_hex(p.own(ci, 'LightGuid'))
        record.update(
            lightmapGuid=lightmap, lightGuid=light,
            bakedInto=sorted(set().union(*(listed.get(g, set()) for g in (lightmap, light) if g))),
            shadowMapped=sorted(shadowed.get(light, set())) if light else [],
            channels=p.effective(ci, 'LightAffectsClassification') == 'LAC_USER_SELECTED',
            saved=sorted({name for name, _ in props}),
            referencedBy=sorted(set(kismet.get(ai, [])) | set(toggles.get(ai, []))))
    return lights


# XComMapEdSun's class defaults (unrealscript/XComMapEd/Classes/XComMapEdSun.uc): all dynamic, no shadows.
SUN_COLOR = [240 / 255, 242 / 255, 1.0]
SUN_SKY_COLOR = [210 / 255, 220 / 255, 1.0]


def sun_records(name, sun, sky, yaw, pitch):
    """The directional and sky light a patch's sun or photo object adds."""
    rotation = [-round(pitch * 65536 / 360), round(yaw * 65536 / 360), 0]
    common = dict(actorClass="XComMapEdSun", sourcePackage="patch", layer="patch", role="patch",
                  location=[0, 0, 0], rotation=rotation, castShadows=False)
    return [dict(common, id=f"{name}:sun", actor=f"Preview.{name}", component="Sun",
                 componentClass="DirectionalLightComponent", kind="directional", direction=forward(rotation),
                 color=SUN_COLOR, brightness=sun, enabled=sun > 0),
            dict(common, id=f"{name}:sky", actor=f"Preview.{name}", component="Sky",
                 componentClass="SkyLightComponent", kind="sky", direction=forward(rotation),
                 color=SUN_SKY_COLOR, brightness=sky, lowerColor=[1.0, 1.0, 1.0], lowerBrightness=0.2,
                 enabled=sky > 0)]
