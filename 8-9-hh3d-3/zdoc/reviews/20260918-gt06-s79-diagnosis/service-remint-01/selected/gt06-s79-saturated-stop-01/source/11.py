"""Closed opaque Principled grammar for the original GT04 box fixture."""
import math
import struct

MAX_MATERIALS=4
STABLE_ID='hh_gt04_material_id'
DEFAULT_INPUTS={
    'Base Color':[0.800000011920929]*3+[1.0],'Metallic':0.0,'Roughness':0.5,
    'IOR':1.5,'Alpha':1.0,'Thin Wall':False,'Normal':[0.0]*3,'Weight':0.0,
    'Diffuse Roughness':0.0,'Subsurface Weight':0.0,
    'Subsurface Radius':[1.0,0.20000000298023224,0.10000000149011612],
    'Subsurface Scale':0.004999999888241291,'Subsurface IOR':1.399999976158142,
    'Subsurface Anisotropy':0.0,'Specular IOR Level':0.5,'Specular Tint':[1.0]*4,
    'Anisotropic':0.0,'Anisotropic Rotation':0.0,'Tangent':[0.0]*3,
    'Transmission Weight':0.0,'Coat Weight':0.0,'Coat Roughness':0.029999999329447746,
    'Coat IOR':1.5,'Coat Tint':[1.0]*4,'Coat Normal':[0.0]*3,'Sheen Weight':0.0,
    'Sheen Roughness':0.5,'Sheen Tint':[1.0]*4,'Emission Color':[1.0]*4,
    'Emission Strength':0.0,'Thin Film Thickness':0.0,'Thin Film IOR':1.3300000429153442}


class MaterialRejected(ValueError):pass
def need(value,code):
    if not value:raise MaterialRejected(code)
def rounded(value):return struct.unpack('f',struct.pack('f',value))[0]
def socket_value(socket):
    value=getattr(socket,'default_value',None)
    return list(value) if hasattr(value,'__len__') and not isinstance(value,str) else value


def inspect_material(material):
    import re
    stable=material.get(STABLE_ID)
    need(type(stable) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',stable),'MATERIAL_STABLE_ID')
    need(material.name=='HH_Material_'+stable and material.library is None and material.animation_data is None
        and material.use_nodes and not material.use_fake_user,'MATERIAL_OWNER_OR_ANIMATION')
    tree=material.node_tree
    need(tree is not None and tree.animation_data is None and len(tree.nodes)==2 and len(tree.links)==1,
        'MATERIAL_NODE_GRAMMAR')
    shader=next((node for node in tree.nodes if node.bl_idname=='ShaderNodeBsdfPrincipled'),None)
    output=next((node for node in tree.nodes if node.bl_idname=='ShaderNodeOutputMaterial'),None)
    need(shader is not None and output is not None and not shader.mute and not output.mute
        and output.is_active_output and output.target=='ALL','MATERIAL_NODE_GRAMMAR')
    link=tree.links[0]
    need(link.from_node==shader and link.from_socket==shader.outputs['BSDF']
        and link.to_node==output and link.to_socket==output.inputs['Surface'] and link.is_valid,
        'MATERIAL_SURFACE_LINK')
    need(shader.distribution=='MULTI_GGX' and shader.subsurface_method=='RANDOM_WALK'
        and material.surface_render_method=='DITHERED' and not material.use_backface_culling,
        'MATERIAL_UNSUPPORTED_PROPERTY')
    inputs={socket.name:socket_value(socket) for socket in shader.inputs}
    need(len(inputs)==len(shader.inputs) and set(inputs)==set(DEFAULT_INPUTS)
        and all(not socket.is_linked for socket in shader.inputs),'MATERIAL_INPUT_GRAMMAR')
    for name,value in inputs.items():
        if name not in ('Base Color','Metallic','Roughness'):
            need(type(value) is type(DEFAULT_INPUTS[name]) and value==DEFAULT_INPUTS[name],
                'MATERIAL_UNSUPPORTED_INPUT')
    color=inputs['Base Color'];metal=inputs['Metallic'];rough=inputs['Roughness']
    need(type(color) is list and len(color)==4 and color[3]==1.0
        and all(type(x) in (float,int) and math.isfinite(x) and 0<=x<=1 for x in color)
        and all(type(x) in (float,int) and math.isfinite(x) and 0<=x<=1 for x in (metal,rough)),
        'MATERIAL_PBR_RANGE')
    need(list(material.diffuse_color)==color and material.metallic==metal and material.roughness==rough,
        'MATERIAL_VIEWPORT_BINDING')
    return {'material_id':stable,'name':material.name,'base_color':color,'metallic':metal,
        'roughness':rough,'double_sided':True,'alpha_mode':'OPAQUE'}


def scene_materials(bpy):
    need(len(bpy.data.materials)<=MAX_MATERIALS,'MATERIAL_COUNT_CAP')
    materials={}
    for material in bpy.data.materials:
        row=inspect_material(material)
        need(row['material_id'] not in materials,'MATERIAL_DUPLICATE_ID')
        materials[row['material_id']]=row
    used=[]
    for obj in bpy.data.objects:
        if obj.type!='MESH':continue
        slots=obj.material_slots
        need(len(slots)<=1 and all(slot.link=='DATA' and slot.material is not None for slot in slots)
            and all(face.material_index==0 for face in obj.data.polygons),'MATERIAL_SLOT_GRAMMAR')
        if slots:used.append(slots[0].material.get(STABLE_ID))
    need(len(used)==len(set(used)) and set(used)==set(materials),'MATERIAL_UNOWNED_OR_SHARED')
    return materials


def apply(bpy,obj,payload):
    stable=payload['material_id']
    if obj.data.materials:material=obj.data.materials[0]
    else:
        material=bpy.data.materials.new('HH_Material_'+stable)
        material[STABLE_ID]=stable;material.use_nodes=True;obj.data.materials.append(material)
    shader=next(node for node in material.node_tree.nodes if node.bl_idname=='ShaderNodeBsdfPrincipled')
    color=payload['base_color']+[1.0]
    shader.inputs['Base Color'].default_value=color;material.diffuse_color=color
    shader.inputs['Metallic'].default_value=payload['metallic'];material.metallic=payload['metallic']
    shader.inputs['Roughness'].default_value=payload['roughness'];material.roughness=payload['roughness']
    return material
