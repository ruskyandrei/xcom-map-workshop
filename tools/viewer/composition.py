"""Compose static scene layers while retaining nonvisual patch records and identity."""
import copy


def content_records(p):
    records=[]
    for index,name in enumerate(p.paths,1):
        if not name.startswith('TheWorld.PersistentLevel.'):continue
        cls=p.cls(index)
        if name.count('.')!=2 and not cls.startswith(('SeqAct_','SeqCond_','SeqEvent_','SeqVar_')):continue
        if cls in ('Model','Polys','BrushComponent','TextBuffer'):continue
        records.append(dict(path=name,export=index,actorClass=cls,location=p.effective(index,'Location'),
                            hidden=p.effective(index,'bHidden',False)))
    return records


def compose_scene(base,layers):
    out=copy.deepcopy(base)
    for key in ('meshes','materials','textures'):out[key]=base[key]
    ids={o['id'] for o in out['objects']}
    out['inheritedPatches']=[]
    for layer in layers:
        package=layer['source']['file']
        objects=copy.deepcopy(layer['objects'])
        for obj in objects:
            if obj['id'] in ids:raise ValueError(f'Duplicate composed object {obj["id"]}')
            ids.add(obj['id']);obj['layer']='inherited'
        out['objects'].extend(objects)
        lights=copy.deepcopy(layer.get('lights',[]))
        for light in lights:
            if light['id'] in ids:raise ValueError(f'Duplicate composed light {light["id"]}')
            ids.add(light['id']);light['layer']='inherited'
        out.setdefault('lights',[]).extend(lights)
        out.setdefault('buildings',[]).extend(copy.deepcopy(layer.get('buildings',[])))
        out['diagnostics'].extend(layer['diagnostics'])
        out['inheritedPatches'].append(dict(name=layer['name'],source=layer['source'],
            components=len(objects),lights=len(lights),hiddenComponents=sum(o['hidden'] for o in objects),
            records=layer.get('content',[]),runtimeScriptsExecuted=False))
    return out
