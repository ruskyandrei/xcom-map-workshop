"""Writes a UDK Lightmass calibration scene as T3D (baker design, section 4.7: the encoder reference).

The scene is flat receivers under static lights: directional (one or more), point and spot lights. Each receiver is UDK's template floor
(`MapTemplates.SM_Template_Map_Floor`: lightmap UVs in channel 1; top face tangent +X, binormal -Y, normal +Z), turned
and tilted so the light arrives from a different direction in its tangent space. Their top faces are coplanar or far
apart, so no receiver shadows or lights another. After a bake (`udk_bake.ps1`), `udk_calib_read.py` reads what
Lightmass wrote for each receiver.

  python -B tools/bake/udk_calib_scene.py tools/bake/examples/udk-calib1.json <lab>\\bake-calib\\calib1

Writes <out>/scene.t3d (for MAP IMPORTADD) and <out>/scene.json (the receivers' names and transforms, the light's
direction, and the spec's hash). Rotations are in UE units (65536 = 360 degrees).

Bake it on a base map without Lightmass environment light (`udk_calib_base.py`, then `udk_bake.ps1 -Map`): UDK's
template map keeps a sky-blue environment colour and ambient occlusion, which tinted the first calibration bake.

Spec (JSON):
  light: {pitch, yaw, brightness, color: [r, g, b] (0-255)} (a directional light; optional when the scene has point
         or spot lights and no receiver gives lightTangent)
  moreLights: [further lights in the same form] (optional; receivers' lightTangent refers to the first light)
  pointLights: [{location: [x, y, z], radius, falloffExponent, brightness, color, lightSourceRadius}] (optional, at
               most ten; lightSourceRadius is Lightmass's, UDK's default 100 when left out)
  spotLights: [{location, pitch, yaw, radius, falloffExponent, innerConeAngle, outerConeAngle (degrees), brightness,
               color, lightSourceRadius}] (optional, at most ten; a spot light shines along its rotation's X)
  receivers: [{name, location: [x, y, z], yaw, pitch, roll, scale, lightmapRes}]
             or, instead of yaw/pitch/roll, lightTangent: [azimuth, elevation] in degrees: the receiver is turned so
             the light arrives from there in its top face's tangent frame
  importanceVolume: {min: [x, y, z], max: [x, y, z]} (optional): a LightmassImportanceVolume box. Bounce light needs
             one: Lightmass emits photons outside any importance volume at 0.0005 of their density
             (BaseLightmass.ini OutsideImportanceVolumeDensityScale), and without one a small scene got none.
"""
import argparse
import hashlib
import json
import math
import uuid
from pathlib import Path

MESH = "StaticMesh'MapTemplates.SM_Template_Map_Floor'"
NAME_START = 900  # object-name numbers, clear of anything the editor's template map uses


def rotation_matrix(pitch, yaw, roll):
    """UE3 FRotationMatrix columns: the actor's X, Y, Z axes in world space."""
    p, y, r = (v / 65536 * 2 * math.pi for v in (pitch, yaw, roll))
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    x = (cp * cy, cp * sy, sp)
    yv = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    z = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    return x, yv, z


def rotator_from_axes(x, y, z):
    """UE3 pitch, yaw, roll (65536 units, rounded) of a rotation with these X, Y, Z axes (inverse of rotation_matrix)."""
    pitch = math.asin(max(-1.0, min(1.0, x[2])))
    yaw = math.atan2(x[1], x[0])
    roll = math.atan2(-y[2], z[2])
    return tuple(int(round(v / (2 * math.pi) * 65536)) for v in (pitch, yaw, roll))


def axes_for_tangent_light(to_light, azimuth, elevation):
    """Actor axes that put a light from world direction `to_light` at (azimuth, elevation) degrees in the template
    floor's top-face tangent frame (tangent = actor X, binormal = -actor Y, normal = actor Z)."""
    def unit(v):
        n = math.sqrt(sum(c * c for c in v))
        return tuple(c / n for c in v)

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    lt = unit(to_light)
    up = (0.0, 0.0, 1.0)
    p = unit(tuple(u - lt[2] * l for u, l in zip(up, lt)))   # up, made perpendicular to the light
    e, a = math.radians(elevation), math.radians(azimuth)
    n = unit(tuple(math.sin(e) * l + math.cos(e) * q for l, q in zip(lt, p)))
    d = unit(tuple(math.cos(e) * l - math.sin(e) * q for l, q in zip(lt, p)))   # towards the light, in the plane
    m = cross(d, n)
    t = tuple(math.cos(a) * dv - math.sin(a) * mv for dv, mv in zip(d, m))
    b = tuple(math.sin(a) * dv + math.cos(a) * mv for dv, mv in zip(d, m))
    return t, tuple(-v for v in b), n


def light_direction(pitch, yaw):
    """The unit vector from a surface towards a directional light (the light shines along its rotation's X)."""
    x, _, _ = rotation_matrix(pitch, yaw, 0)
    return tuple(-v for v in x)


def guid():
    a, b, c, d = (int.from_bytes(uuid.uuid4().bytes[k:k + 4], 'little', signed=True) for k in (0, 4, 8, 12))
    return f'(A={a},B={b},C={c},D={d})'


def f6(v):
    return f'{v:.6f}'


def note(n):
    # MAP IMPORTADD drops the file's first actor when that actor is not static (patchtool finding), so a Note leads.
    return f"""      Begin Actor Class=Note Name=Note_{n} Archetype=Note'Engine.Default__Note'
         Text="udk_calib_scene: Lightmass calibration scene"
         Location=(X=0.000000,Y=0.000000,Z=-512.000000)
         Name="Note_{n}"
         ObjectArchetype=Note'Engine.Default__Note'
      End Actor
"""


def light_block(n, spec):
    # Every component of the archetype, in its order (Default__DirectionalLight in UDK's Engine.u lists Sprite,
    # DirectionalLightComponent0, ArrowComponent0): an import matches Components(i) to the archetype's i-th
    # template, and the editor crashes on save
    # ("Mismatched load flags ... cannot be derived from Default__DirectionalLight:Sprite") when the light component
    # is given as Components(0) (first calibration bake, 6 November).
    r, g, b = spec.get('color', [255, 255, 255])
    return f"""      Begin Actor Class=DirectionalLight Name=DirectionalLight_{n} Archetype=DirectionalLight'Engine.Default__DirectionalLight'
         Begin Object Class=SpriteComponent Name=Sprite ObjName=SpriteComponent_{n} Archetype=SpriteComponent'Engine.Default__DirectionalLight:Sprite'
            Name="SpriteComponent_{n}"
            ObjectArchetype=SpriteComponent'Engine.Default__DirectionalLight:Sprite'
         End Object
         Begin Object Class=ArrowComponent Name=ArrowComponent0 ObjName=ArrowComponent_{n} Archetype=ArrowComponent'Engine.Default__DirectionalLight:ArrowComponent0'
            Name="ArrowComponent_{n}"
            ObjectArchetype=ArrowComponent'Engine.Default__DirectionalLight:ArrowComponent0'
         End Object
         Begin Object Class=DirectionalLightComponent Name=DirectionalLightComponent0 ObjName=DirectionalLightComponent_{n} Archetype=DirectionalLightComponent'Engine.Default__DirectionalLight:DirectionalLightComponent0'
            Brightness={f6(spec.get('brightness', 1.0))}
            LightColor=(B={b},G={g},R={r},A=0)
            LightGuid={guid()}
            LightmapGuid={guid()}
            CastDynamicShadows=False
            UseDirectLightMap=True
            Name="DirectionalLightComponent_{n}"
            ObjectArchetype=DirectionalLightComponent'Engine.Default__DirectionalLight:DirectionalLightComponent0'
         End Object
         LightComponent=DirectionalLightComponent'DirectionalLightComponent_{n}'
         Components(0)=SpriteComponent'SpriteComponent_{n}'
         Components(1)=DirectionalLightComponent'DirectionalLightComponent_{n}'
         Components(2)=ArrowComponent'ArrowComponent_{n}'
         Location=(X=0.000000,Y=0.000000,Z=2048.000000)
         Rotation=(Pitch={spec['pitch']},Yaw={spec['yaw']},Roll=0)
         Name="DirectionalLight_{n}"
         ObjectArchetype=DirectionalLight'Engine.Default__DirectionalLight'
      End Actor
"""


def subobject(cls, name, objname, archetype):
    return f"""         Begin Object Class={cls} Name={name} ObjName={objname} Archetype={cls}'{archetype}:{name}'
            Name="{objname}"
            ObjectArchetype={cls}'{archetype}:{name}'
         End Object
"""


def light_common(spec):
    r, g, b = spec.get('color', [255, 255, 255])
    text = f"""            Brightness={f6(spec.get('brightness', 1.0))}
            LightColor=(B={b},G={g},R={r},A=0)
            LightGuid={guid()}
            LightmapGuid={guid()}
            CastDynamicShadows=False
            UseDirectLightMap=True
"""
    if 'lightSourceRadius' in spec:
        # LightmassPointLightSettings (point and spot lights): UDK's default is 100 units; EW's maps set 32.
        text += f"            LightmassSettings=(LightSourceRadius={f6(spec['lightSourceRadius'])})\n"
    return text


def point_light_block(n, spec):
    # Default__PointLight in UDK's Engine.u lists Sprite, DrawLightRadius0, DrawLightSourceRadius0,
    # PointLightComponent0 (the directional light's crash shows the order must be kept).
    arch = 'Engine.Default__PointLight'
    x, y, z = spec['location']
    sprite, radius, source = f'SpriteComponent_{n}', f'DrawLightRadiusComponent_{n}', f'DrawLightRadiusComponent_{n}1'
    comp = f'PointLightComponent_{n}'
    return (f"""      Begin Actor Class=PointLight Name=PointLight_{n} Archetype=PointLight'{arch}'
""" + subobject('SpriteComponent', 'Sprite', sprite, arch)
            + subobject('DrawLightRadiusComponent', 'DrawLightRadius0', radius, arch)
            + subobject('DrawLightRadiusComponent', 'DrawLightSourceRadius0', source, arch)
            + f"""         Begin Object Class=PointLightComponent Name=PointLightComponent0 ObjName={comp} Archetype=PointLightComponent'{arch}:PointLightComponent0'
            Radius={f6(spec.get('radius', 1024.0))}
            FalloffExponent={f6(spec.get('falloffExponent', 2.0))}
            PreviewLightRadius=DrawLightRadiusComponent'{radius}'
            PreviewLightSourceRadius=DrawLightRadiusComponent'{source}'
""" + light_common(spec) + f"""            Name="{comp}"
            ObjectArchetype=PointLightComponent'{arch}:PointLightComponent0'
         End Object
         LightComponent=PointLightComponent'{comp}'
         Components(0)=SpriteComponent'{sprite}'
         Components(1)=DrawLightRadiusComponent'{radius}'
         Components(2)=DrawLightRadiusComponent'{source}'
         Components(3)=PointLightComponent'{comp}'
         Location=(X={f6(x)},Y={f6(y)},Z={f6(z)})
         Name="PointLight_{n}"
         ObjectArchetype=PointLight'{arch}'
      End Actor
""")


def spot_light_block(n, spec):
    # Default__SpotLight lists Sprite, DrawLightRadius0, DrawInnerCone0, DrawOuterCone0, DrawLightSourceRadius0,
    # SpotLightComponent0, ArrowComponent0.
    arch = 'Engine.Default__SpotLight'
    x, y, z = spec['location']
    sprite, radius, source = f'SpriteComponent_{n}', f'DrawLightRadiusComponent_{n}', f'DrawLightRadiusComponent_{n}1'
    inner, outer = f'DrawLightConeComponent_{n}', f'DrawLightConeComponent_{n}1'
    comp, arrow = f'SpotLightComponent_{n}', f'ArrowComponent_{n}'
    return (f"""      Begin Actor Class=SpotLight Name=SpotLight_{n} Archetype=SpotLight'{arch}'
""" + subobject('SpriteComponent', 'Sprite', sprite, arch)
            + subobject('DrawLightRadiusComponent', 'DrawLightRadius0', radius, arch)
            + subobject('DrawLightConeComponent', 'DrawInnerCone0', inner, arch)
            + subobject('DrawLightConeComponent', 'DrawOuterCone0', outer, arch)
            + subobject('DrawLightRadiusComponent', 'DrawLightSourceRadius0', source, arch)
            + subobject('ArrowComponent', 'ArrowComponent0', arrow, arch)
            + f"""         Begin Object Class=SpotLightComponent Name=SpotLightComponent0 ObjName={comp} Archetype=SpotLightComponent'{arch}:SpotLightComponent0'
            InnerConeAngle={f6(spec.get('innerConeAngle', 0.0))}
            OuterConeAngle={f6(spec.get('outerConeAngle', 44.0))}
            PreviewInnerCone=DrawLightConeComponent'{inner}'
            PreviewOuterCone=DrawLightConeComponent'{outer}'
            Radius={f6(spec.get('radius', 1024.0))}
            FalloffExponent={f6(spec.get('falloffExponent', 2.0))}
            PreviewLightRadius=DrawLightRadiusComponent'{radius}'
            PreviewLightSourceRadius=DrawLightRadiusComponent'{source}'
""" + light_common(spec) + f"""            Name="{comp}"
            ObjectArchetype=SpotLightComponent'{arch}:SpotLightComponent0'
         End Object
         LightComponent=SpotLightComponent'{comp}'
         Components(0)=SpriteComponent'{sprite}'
         Components(1)=DrawLightRadiusComponent'{radius}'
         Components(2)=DrawLightConeComponent'{inner}'
         Components(3)=DrawLightConeComponent'{outer}'
         Components(4)=DrawLightRadiusComponent'{source}'
         Components(5)=SpotLightComponent'{comp}'
         Components(6)=ArrowComponent'{arrow}'
         Location=(X={f6(x)},Y={f6(y)},Z={f6(z)})
         Rotation=(Pitch={spec.get('pitch', -16384)},Yaw={spec.get('yaw', 0)},Roll=0)
         Name="SpotLight_{n}"
         ObjectArchetype=SpotLight'{arch}'
      End Actor
""")


def receiver_block(n, rec):
    x, y, z = rec['location']
    s = rec.get('scale', 0.25)
    return f"""      Begin Actor Class=StaticMeshActor Name=StaticMeshActor_{n} Archetype=StaticMeshActor'Engine.Default__StaticMeshActor'
         Begin Object Class=StaticMeshComponent Name=StaticMeshComponent0 ObjName=StaticMeshComponent_{n} Archetype=StaticMeshComponent'Engine.Default__StaticMeshActor:StaticMeshComponent0'
            StaticMesh={MESH}
            bOverrideLightMapRes=True
            OverriddenLightMapRes={rec.get('lightmapRes', 64)}
            ReplacementPrimitive=None
            Name="StaticMeshComponent_{n}"
            ObjectArchetype=StaticMeshComponent'Engine.Default__StaticMeshActor:StaticMeshComponent0'
         End Object
         StaticMeshComponent=StaticMeshComponent'StaticMeshComponent_{n}'
         Components(0)=StaticMeshComponent'StaticMeshComponent_{n}'
         Location=(X={f6(x)},Y={f6(y)},Z={f6(z)})
         Rotation=(Pitch={rec.get('pitch', 0)},Yaw={rec.get('yaw', 0)},Roll={rec.get('roll', 0)})
         DrawScale3D=(X={f6(s)},Y={f6(s)},Z={f6(s)})
         CollisionComponent=StaticMeshComponent'StaticMeshComponent_{n}'
         Tag="{rec['name']}"
         Name="StaticMeshActor_{n}"
         ObjectArchetype=StaticMeshActor'Engine.Default__StaticMeshActor'
      End Actor
"""


def importance_volume_block(n, box):
    """A LightmassImportanceVolume over the box {min, max}: a six-sided brush around the actor at the box's centre.
    Each polygon lists its corners clockwise as seen from outside, with its outward normal, as the editor writes
    brushes. `Default__LightmassImportanceVolume` in UDK's Engine.u has one component, BrushComponent0."""
    lo, hi = [float(v) for v in box['min']], [float(v) for v in box['max']]
    if any(h <= l for l, h in zip(lo, hi)):
        raise ValueError('importanceVolume max must exceed min on every axis')
    centre = [(l + h) / 2 for l, h in zip(lo, hi)]
    half = [(h - l) / 2 for l, h in zip(lo, hi)]

    def vec(v):
        return ','.join(f6(c) for c in v)

    polys = []
    for axis in range(3):
        for sign in (-1.0, 1.0):
            u, v = [a for a in range(3) if a != axis]
            corners = []
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                c = [0.0, 0.0, 0.0]
                c[axis], c[u], c[v] = sign * half[axis], su * half[u], sv * half[v]
                corners.append(c)
            normal = [0.0, 0.0, 0.0]
            normal[axis] = sign
            e1 = [corners[1][k] - corners[0][k] for k in range(3)]
            e2 = [corners[2][k] - corners[0][k] for k in range(3)]
            cross = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
            if sum(cross[k] * normal[k] for k in range(3)) > 0:     # clockwise from outside: cross points inwards
                corners.reverse()
            tu, tv = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
            tu[u], tv[v] = 1.0, -1.0
            polys.append(f"""               Begin Polygon
                  Origin   {vec(corners[0])}
                  Normal   {vec(normal)}
                  TextureU {vec(tu)}
                  TextureV {vec(tv)}
""" + ''.join(f'                  Vertex   {vec(c)}\n' for c in corners) + '               End Polygon\n')
    x, y, z = centre
    # The brush comes before the component: the importer resolves the component's Brush= as it reads it, and with
    # the brush after it UDK logged "unresolved reference to 'Model'Model_860''" and Lightmass saw no volume
    # (importance bounds radius 0).
    return f"""      Begin Actor Class=LightmassImportanceVolume Name=LightmassImportanceVolume_{n} Archetype=LightmassImportanceVolume'Engine.Default__LightmassImportanceVolume'
         Begin Brush Name=Model_{n}
            Begin PolyList
{''.join(polys)}            End PolyList
         End Brush
         Begin Object Class=BrushComponent Name=BrushComponent0 ObjName=BrushComponent_{n} Archetype=BrushComponent'Engine.Default__LightmassImportanceVolume:BrushComponent0'
            Brush=Model'Model_{n}'
            ReplacementPrimitive=None
            Name="BrushComponent_{n}"
            ObjectArchetype=BrushComponent'Engine.Default__LightmassImportanceVolume:BrushComponent0'
         End Object
         Brush=Model'Model_{n}'
         BrushComponent=BrushComponent'BrushComponent_{n}'
         Components(0)=BrushComponent'BrushComponent_{n}'
         CollisionComponent=BrushComponent'BrushComponent_{n}'
         Location=(X={f6(x)},Y={f6(y)},Z={f6(z)})
         Name="LightmassImportanceVolume_{n}"
         ObjectArchetype=LightmassImportanceVolume'Engine.Default__LightmassImportanceVolume'
      End Actor
"""


def build(spec):
    """T3D text and the scene manifest for a spec."""
    light = spec.get('light')
    extra = spec.get('moreLights', [])
    points, spots = spec.get('pointLights', []), spec.get('spotLights', [])
    names = [r['name'] for r in spec['receivers']]
    if len(set(names)) != len(names):
        raise ValueError('receiver names must be unique')
    if len(extra) > 9:
        raise ValueError('at most nine more lights')
    if len(points) > 10 or len(spots) > 10:
        raise ValueError('at most ten point and ten spot lights')
    if light is None and (extra or not (points or spots)):
        raise ValueError('a scene needs a light; moreLights need a first light')
    if light is None and any('lightTangent' in r for r in spec['receivers']):
        raise ValueError('lightTangent refers to the directional light, and the spec has none')
    directional = ([light] if light else []) + extra
    # The first light keeps number 900; more lights take 891, 892, ...; point lights 880-889 and spot lights 870-879
    # (all clear of the receivers' 901 and up).
    numbers = ([NAME_START] if light else []) + [NAME_START - 9 + j for j in range(len(extra))]
    point_numbers = [NAME_START - 20 + j for j in range(len(points))]
    spot_numbers = [NAME_START - 30 + j for j in range(len(spots))]
    parts = ['Begin Map\n   Begin Level\n', note(NAME_START)]
    parts += [light_block(n, sp) for n, sp in zip(numbers, directional)]
    parts += [point_light_block(n, sp) for n, sp in zip(point_numbers, points)]
    parts += [spot_light_block(n, sp) for n, sp in zip(spot_numbers, spots)]
    receivers = []
    to_light = light_direction(light['pitch'], light['yaw']) if light else None
    for k, rec in enumerate(spec['receivers']):
        n = NAME_START + 1 + k
        if 'lightTangent' in rec:
            pitch, yaw, roll = rotator_from_axes(*axes_for_tangent_light(to_light, *rec['lightTangent']))
            rec = dict(rec, pitch=pitch, yaw=yaw, roll=roll)
        parts.append(receiver_block(n, rec))
        axes = rotation_matrix(rec.get('pitch', 0), rec.get('yaw', 0), rec.get('roll', 0))
        receivers.append(dict(name=rec['name'], actor=f'StaticMeshActor_{n}', component=f'StaticMeshComponent_{n}',
                              location=rec['location'], yaw=rec.get('yaw', 0), pitch=rec.get('pitch', 0),
                              roll=rec.get('roll', 0), scale=rec.get('scale', 0.25),
                              lightmapRes=rec.get('lightmapRes', 64),
                              axes=[list(map(lambda v: round(v, 9), a)) for a in axes]))
    volume = spec.get('importanceVolume')
    if volume:
        parts.append(importance_volume_block(NAME_START - 40, volume))      # 860, clear of lights and receivers
    parts.append('   End Level\nEnd Map\n')
    lights = [dict(sp, toLight=[round(v, 9) for v in light_direction(sp['pitch'], sp['yaw'])],
                   actor=f'DirectionalLight_{n}') for n, sp in zip(numbers, directional)]
    point_out = [dict(sp, actor=f'PointLight_{n}') for n, sp in zip(point_numbers, points)]
    spot_out = [dict(sp, actor=f'SpotLight_{n}',
                     direction=[round(v, 9) for v in rotation_matrix(sp.get('pitch', -16384), sp.get('yaw', 0), 0)[0]])
                for n, sp in zip(spot_numbers, spots)]
    manifest = dict(mesh=MESH, light=lights[0] if lights else None, lights=lights, pointLights=point_out,
                    spotLights=spot_out, receivers=receivers, importanceVolume=volume)
    return ''.join(parts), manifest


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('spec', type=Path)
    a.add_argument('out', type=Path)
    args = a.parse_args()
    raw = args.spec.read_bytes()
    t3d, manifest = build(json.loads(raw))
    manifest['spec'] = dict(path=str(args.spec), sha256=hashlib.sha256(raw).hexdigest())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'scene.t3d').write_text(t3d, encoding='ascii', newline='\r\n')
    (args.out / 'scene.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f"{len(manifest['receivers'])} receivers, {len(manifest['lights'])} directional, "
          f"{len(manifest['pointLights'])} point and {len(manifest['spotLights'])} spot lights -> {args.out}")


if __name__ == '__main__':
    main()
