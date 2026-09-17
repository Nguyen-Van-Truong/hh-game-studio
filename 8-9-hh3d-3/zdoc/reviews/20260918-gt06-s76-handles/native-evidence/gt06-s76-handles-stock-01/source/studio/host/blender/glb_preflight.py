"""Bounded GLB inspection for the internal box-only exporter profile.

No URI fetching, decompression, texture decoding, arbitrary extensions or importer.
This does not replace Khronos validation or Godot import required by GT05.
"""
from __future__ import annotations
import hashlib
import math
import struct
from studio.protocol.core import parse_json

MAX_BYTES=4*1024*1024


class GLBRejected(ValueError):pass


def need(value,code):
    if not value:raise GLBRejected(code)


def integer(value,lo=0,hi=MAX_BYTES):return type(value) is int and lo<=value<=hi


def bind_snapshot(preflight,snapshot):
    """Check actual local vertices and node TRS against the source XYZ scene.

    The pinned exporter converts Blender Z-up to glTF Y-up as (x,z,-y).
    Quaternion sign is immaterial. No mesh/name inference from positional order.
    """
    expected=snapshot['objects'];actual=preflight['meshes']
    need(len(actual)==len(expected),'GLB_SOURCE_OBJECT_COUNT')
    by_name={row['name']:row for row in actual}
    need(len(by_name)==len(actual) and set(by_name)=={row['name'] for row in expected},'GLB_SOURCE_NAMES')
    def close(a,b):return len(a)==len(b) and all(math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-6) for x,y in zip(a,b))
    for source in expected:
        row=by_name[source['name']]
        x,y,z=source['location'];need(close(row['translation'],[x,z,-y]),'GLB_SOURCE_TRANSLATION')
        x,y,z=source['scale'];need(close(row['scale'],[x,z,y]),'GLB_SOURCE_SCALE')
        x,y,z=[angle/2 for angle in source['rotation']]
        cx,cy,cz=math.cos(x),math.cos(y),math.cos(z)
        sx,sy,sz=math.sin(x),math.sin(y),math.sin(z)
        # Blender XYZ uses qz*qy*qx; basis conversion maps (qx,qy,qz) to (qx,qz,-qy).
        quaternion=[sx*cy*cz-cx*sy*sz,cx*cy*sz-sx*sy*cz,-(cx*sy*cz+sx*cy*sz),cx*cy*cz+sx*sy*sz]
        need(close(row['rotation'],quaternion) or close(row['rotation'],[-v for v in quaternion]),'GLB_SOURCE_ROTATION')
        vertices=sorted([x,z,-y] for x,y,z in source['vertices'])
        need(len(vertices)==len(row['unique_positions']) and all(close(a,b) for a,b in zip(vertices,row['unique_positions'])),
             'GLB_SOURCE_VERTICES')
        material=source.get('material');observed=row.get('material')
        if material is None:need(observed is None,'GLB_SOURCE_UNEXPECTED_MATERIAL')
        else:
            need(type(observed) is dict and observed['name']==material['name']
                and close(observed['base_color'],material['base_color'])
                and close([observed['metallic'],observed['roughness']],[material['metallic'],material['roughness']])
                and observed['double_sided']==material['double_sided']
                and observed['alpha_mode']==material['alpha_mode'],'GLB_SOURCE_MATERIAL')
    return True


def inspect_glb(raw):
    need(type(raw) is bytes and 28<=len(raw)<=MAX_BYTES,'GLB_BYTE_CAP')
    magic,version,total=struct.unpack_from('<4sII',raw)
    need(magic==b'glTF' and version==2 and total==len(raw),'GLB_HEADER')
    chunks=[];offset=12
    while offset<len(raw):
        need(len(chunks)<2 and offset+8<=len(raw),'GLB_CHUNK_COUNT')
        length,kind=struct.unpack_from('<II',raw,offset);offset+=8
        need(length%4==0 and offset+length<=len(raw),'GLB_CHUNK_BOUNDS')
        chunks.append((kind,raw[offset:offset+length]));offset+=length
    need(len(chunks)==2 and chunks[0][0]==0x4e4f534a and chunks[1][0]==0x004e4942,'GLB_CHUNK_ORDER')
    value=parse_json(chunks[0][1]);binary=chunks[1][1]
    need(type(value) is dict and set(value)<= {'asset','scene','scenes','nodes','meshes','accessors','bufferViews','buffers','materials'},
         'GLB_EXTENSION_OR_DEPENDENCY')
    asset=value.get('asset')
    need(type(asset) is dict and set(asset)<= {'version','generator'} and asset.get('version')=='2.0','GLB_ASSET')
    buffers=value.get('buffers')
    need(type(buffers) is list and len(buffers)==1 and set(buffers[0])=={'byteLength'},'GLB_EXTERNAL_BUFFER')
    size=buffers[0]['byteLength']
    need(integer(size,1) and 0<=len(binary)-size<=3 and not any(binary[size:]),'GLB_BUFFER_LENGTH')
    views=value.get('bufferViews');accessors=value.get('accessors')
    need(type(views) is list and 1<=len(views)<=64 and type(accessors) is list and 1<=len(accessors)<=64,'GLB_ACCESSOR_CAP')
    spans=[]
    for view in views:
        need(type(view) is dict and set(view)<= {'buffer','byteOffset','byteLength','byteStride','target'}
             and integer(view.get('buffer'),0,0),'GLB_VIEW_SHAPE')
        start=view.get('byteOffset',0);length=view.get('byteLength')
        need(integer(start) and integer(length,1) and start+length<=size,'GLB_VIEW_BOUNDS')
        if 'byteStride' in view:need(integer(view['byteStride'],4,252) and view['byteStride']%4==0,'GLB_STRIDE')
        if 'target' in view:need(view['target'] in (34962,34963) and type(view['target']) is int,'GLB_TARGET')
        spans.append((start,start+length))
    spans.sort();need(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])),'GLB_ALIASED_VIEWS')
    decoded=[]
    for accessor in accessors:
        need(type(accessor) is dict and set(accessor)<= {'bufferView','byteOffset','componentType','count','type','min','max'},
             'GLB_ACCESSOR_SHAPE')
        index=accessor.get('bufferView');count=accessor.get('count');kind=accessor.get('type');component=accessor.get('componentType')
        need(integer(index,0,len(views)-1) and integer(count,1,384) and kind in ('SCALAR','VEC3')
             and type(component) is int and component in (5123,5125,5126),'GLB_ACCESSOR_TYPE')
        need((kind=='VEC3' and component==5126) or (kind=='SCALAR' and component in (5123,5125)),'GLB_ACCESSOR_PROFILE')
        width=3 if kind=='VEC3' else 1;fmt={5123:'H',5125:'I',5126:'f'}[component]
        component_size=struct.calcsize(fmt);element_size=component_size*width
        view=views[index];start=accessor.get('byteOffset',0);stride=view.get('byteStride',element_size)
        need(integer(start) and start%component_size==0 and (view.get('byteOffset',0)+start)%component_size==0
             and stride>=element_size and start+(count-1)*stride+element_size<=view['byteLength'],'GLB_ACCESSOR_BOUNDS')
        data=[struct.unpack_from('<'+fmt*width,binary,view.get('byteOffset',0)+start+i*stride) for i in range(count)]
        need(all(math.isfinite(number) and abs(number)<=1e6 for row in data for number in row),'GLB_NONFINITE_OR_RANGE')
        for name,func in (('min',min),('max',max)):
            if name in accessor:
                declared=accessor[name]
                need(type(declared) is list and len(declared)==width and all(type(x) in (float,int) and math.isfinite(x) for x in declared),
                     'GLB_DECLARED_BOUNDS')
                actual=[func(row[axis] for row in data) for axis in range(width)]
                need(all(abs(a-b)<=1e-6 for a,b in zip(actual,declared)),'GLB_FALSE_BOUNDS')
        decoded.append(data)
    nodes=value.get('nodes');meshes=value.get('meshes');scenes=value.get('scenes')
    need(type(nodes) is list and 1<=len(nodes)<=16 and type(meshes) is list and len(meshes)==len(nodes)
         and type(scenes) is list and len(scenes)==1 and integer(value.get('scene'),0,0),'GLB_SCENE_CAP')
    need(set(scenes[0])<= {'name','nodes'} and scenes[0].get('nodes')==list(range(len(nodes))),'GLB_SCENE_HIERARCHY')
    materials=value.get('materials',[]);material_rows=[];used_materials=set()
    need(type(materials) is list and len(materials)<=4,'GLB_MATERIAL_CAP')
    for material in materials:
        need(type(material) is dict and set(material)<= {'name','pbrMetallicRoughness','doubleSided','alphaMode'}
            and type(material.get('name')) is str and 0<len(material['name'])<=128,'GLB_MATERIAL_GRAMMAR')
        pbr=material.get('pbrMetallicRoughness',{})
        need(type(pbr) is dict and set(pbr)<= {'baseColorFactor','metallicFactor','roughnessFactor'},'GLB_PBR_GRAMMAR')
        color=pbr.get('baseColorFactor',[1,1,1,1]);metal=pbr.get('metallicFactor',1);rough=pbr.get('roughnessFactor',1)
        need(type(color) is list and len(color)==4 and color[3]==1
            and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in color+[metal,rough])
            and type(material.get('doubleSided',False)) is bool and material.get('alphaMode','OPAQUE')=='OPAQUE',
            'GLB_PBR_RANGE')
        material_rows.append({'name':material['name'],'base_color':color,'metallic':metal,'roughness':rough,
            'double_sided':material.get('doubleSided',False),'alpha_mode':'OPAQUE'})
    need(len({row['name'] for row in material_rows})==len(material_rows),'GLB_DUPLICATE_MATERIAL_NAME')
    mesh_ids=set();used=set();reports=[]
    for node in nodes:
        need(type(node) is dict and set(node)<= {'mesh','name','translation','rotation','scale'}
             and integer(node.get('mesh'),0,len(meshes)-1),'GLB_NODE_PROFILE')
        mesh_id=node['mesh'];need(mesh_id not in mesh_ids,'GLB_INSTANCING_UNSUPPORTED');mesh_ids.add(mesh_id)
        for field,count in (('translation',3),('rotation',4),('scale',3)):
            if field in node:need(type(node[field]) is list and len(node[field])==count
                and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<=10000 for x in node[field]),'GLB_NODE_TRANSFORM')
        if 'rotation' in node:need(abs(sum(x*x for x in node['rotation'])-1)<1e-5,'GLB_QUATERNION')
        mesh=meshes[mesh_id]
        need(type(mesh) is dict and set(mesh)<= {'name','primitives'} and len(mesh.get('primitives',[]))==1,'GLB_MESH_PROFILE')
        primitive=mesh['primitives'][0]
        need(type(primitive) is dict and set(primitive)<= {'attributes','indices','mode','material'} and primitive.get('mode',4)==4
             and type(primitive.get('mode',4)) is int,'GLB_PRIMITIVE')
        attributes=primitive.get('attributes')
        need(type(attributes) is dict and set(attributes)=={'POSITION','NORMAL'},'GLB_VERTEX_ATTRIBUTES')
        references=[attributes['POSITION'],attributes['NORMAL'],primitive.get('indices')]
        need(all(integer(index,0,len(accessors)-1) for index in references),'GLB_ACCESSOR_REFERENCE')
        positions,normals,indices=[decoded[index] for index in references];used.update(references)
        need(accessors[references[0]]['type']==accessors[references[1]]['type']=='VEC3'
             and accessors[references[2]]['type']=='SCALAR' and len(positions)==len(normals)<=48
             and len(indices)==36 and all(0<=row[0]<len(positions) for row in indices),'GLB_TRIANGLE_INDEX_BOUNDS')
        need(len(set(positions))==8,'GLB_BOX_VERTEX_COUNT')
        need(all(abs(sum(x*x for x in normal)-1)<1e-5 for normal in normals),'GLB_NORMALS')
        reports.append({'name':node.get('name'),'mesh':mesh_id,'vertices':len(positions),'triangles':12,
            'unique_positions':[list(row) for row in sorted(set(positions))],
            'translation':node.get('translation',[0,0,0]),'rotation':node.get('rotation',[0,0,0,1]),
            'scale':node.get('scale',[1,1,1])})
        if 'material' in primitive:
            index=primitive['material'];need(integer(index,0,len(material_rows)-1),'GLB_MATERIAL_REFERENCE')
            need(index not in used_materials,'GLB_SHARED_MATERIAL_UNSUPPORTED');used_materials.add(index)
            reports[-1]['material']=material_rows[index]
    need(used==set(range(len(accessors))),'GLB_UNUSED_ACCESSORS')
    need(used_materials==set(range(len(material_rows))),'GLB_UNUSED_MATERIALS')
    return {'schema':'HH-GLB-BOX-PREFLIGHT-1','sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw),
        'objects':len(nodes),'triangles':12*len(nodes),'decoded_buffer_bytes':size,'texture_decoded_bytes':0,
        'materials':len(material_rows),'images':0,'extensions':[],'uri_count':0,'meshes':reports,'public_ack':False}
