"""Original producer's pure geometry/path tests; no native or acceptance claim."""
import math
import json
from collections import Counter
import struct
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pipeline.naming import validate_catalog
from pipeline.producer import contract as c
from pipeline.producer.run_blender import image_observation


EXPECTED_EXPORT_WARNINGS = {
    'Armature must be the parent of skinned meshArmature is selected by its name, but may be false in case of instances':4,
    'More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.':1,
}


def verify_direct_glb(raw, report):
    """Independent bounded matrix/channel readback, not an intake/acceptance gate.

    Does not import Blender, Godot or the producer's coordinate conversion.
    Quaternion matrices normalize input; opposite quaternion signs are equal.
    """
    need=c.need
    need(28<=len(raw)<=c.MAX_ARTIFACT and raw[:4]==b'glTF','DIRECT_GLB_HEADER')
    version,total,size,kind=struct.unpack_from('<4I',raw,4)
    need(version==2 and total==len(raw) and kind==0x4e4f534a and size<=262144 and 28+size<=len(raw),'DIRECT_GLB_HEADER')
    length,kind=struct.unpack_from('<2I',raw,20+size)
    need(kind==0x004e4942 and length+28+size==len(raw),'DIRECT_GLB_BINARY')
    g=json.loads(raw[20:20+size]); binary=raw[28+size:]; observed=report['observed']
    need(len(g['nodes'])<=256 and len(g['accessors'])<=2048 and len(g['bufferViews'])<=2048,'DIRECT_GLB_LIMIT')
    need(not g.get('extensionsUsed') and not g.get('extensionsRequired'),'DIRECT_GLB_EXTENSION')
    identity=[[float(i==j) for j in range(4)] for i in range(4)]
    def mul(a,b):
        return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    def matrix(v):
        t,q,s=v['position'],v['rotation_xyzw'],v['scale']
        need(len(t)==3 and len(q)==4 and len(s)==3 and all(math.isfinite(x) for x in [*t,*q,*s]),'DIRECT_TRS')
        length=math.sqrt(sum(x*x for x in q));need(abs(length-1)<.0001,'DIRECT_QUATERNION')
        x,y,z,w=[value/length for value in q]
        a=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),t[0]],
           [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),t[1]],
           [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),t[2]], [0,0,0,1]]
        for i in range(3):
            for j in range(3):a[i][j]*=s[j]
        return a
    def error(a,b):return max(abs(x-y) for aa,bb in zip(a,b) for x,y in zip(aa,bb))
    def accessor(index):
        a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
        need(a['componentType']==5126 and 0<a['count']<=60 and not a.get('sparse'),'DIRECT_ACCESSOR')
        n={'SCALAR':1,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        stride=v.get('byteStride',4*n);start=v.get('byteOffset',0);off=start+a.get('byteOffset',0)
        need(v['buffer']==0 and 4*n<=stride<=252 and stride%4==0 and start<=off
             and off+(a['count']-1)*stride+4*n<=start+v['byteLength']<=len(binary),'DIRECT_ACCESSOR_BOUNDS')
        return [struct.unpack_from('<'+'f'*n,binary,off+i*stride) for i in range(a['count'])]
    names={n['name']:i for i,n in enumerate(g['nodes'])}
    need(len(names)==len(g['nodes']),'DIRECT_NODE_NAMES')
    parents={}
    for i,n in enumerate(g['nodes']):
        need('matrix' not in n,'DIRECT_NODE_MATRIX')
        for child in n.get('children',[]):
            need(type(child) is int and 0<=child<len(g['nodes']) and child not in parents,'DIRECT_PARENT')
            parents[child]=i
    base={i:{'position':n.get('translation',[0,0,0]),'rotation_xyzw':n.get('rotation',[0,0,0,1]),
             'scale':n.get('scale',[1,1,1])} for i,n in enumerate(g['nodes'])}
    def worlds(local):
        result={};active=set()
        def visit(i):
            need(i not in active and len(active)<32,'DIRECT_CYCLE_DEPTH')
            if i not in result:
                active.add(i)
                result[i]=mul(visit(parents[i]),matrix(local[i])) if i in parents else matrix(local[i])
                active.remove(i)
            return result[i]
        for i in local:visit(i)
        return result
    world=worlds(base);bones=observed['rig']['bones'];max_rest=0;max_bind=0;max_pose=0;max_socket=0
    need(0<len(bones)<=60,'DIRECT_BONE_COUNT')
    for name,bone in bones.items():
        i=names[name];parent=g['nodes'][parents[i]]['name'] if i in parents else None
        need(parent==(bone['parent'] or observed['rig']['name']),'DIRECT_BONE_PARENT')
        max_rest=max(max_rest,error(matrix(base[i]),matrix(bone['rest_gltf_local'])),
                     error(world[i],matrix(bone['rest_gltf_world'])))
    need(len(g['skins'])==1,'DIRECT_SKIN_COUNT')
    for skin in g['skins']:
        need(len(skin['joints'])==len(bones) and {g['nodes'][i]['name'] for i in skin['joints']}==set(bones),'DIRECT_SKIN_JOINTS')
        matrices=accessor(skin['inverseBindMatrices']);need(len(matrices)==len(bones),'DIRECT_INVERSE_BIND_COUNT')
        for joint,packed in zip(skin['joints'],matrices):
            ibm=[[packed[j*4+i] for j in range(4)] for i in range(4)]
            max_bind=max(max_bind,error(mul(world[joint],ibm),identity))
    skins=[n for n in g['nodes'] if 'skin' in n]
    need(len({n['skin'] for n in skins})==1 and skins[0]['skin']==0
         and all(names[n['name']] not in parents for n in skins),'DIRECT_SKIN_ROOT_BINDING')
    need({n['name'] for n in skins}=={name for name,m in observed['meshes'].items() if m['skinned']},'DIRECT_SKIN_MESH_SET')
    channels=0;pose_bones=0
    need({a['name'] for a in g['animations']}==set(observed['clips']) and len(g['animations'])==len(observed['clips']),'DIRECT_CLIP_SET')
    for animation in g['animations']:
        samplers=[];seen=set()
        for ch in animation['channels']:
            sampler=animation['samplers'][ch['sampler']]
            need(sampler.get('interpolation','LINEAR')=='LINEAR','DIRECT_INTERPOLATION')
            times=[v[0] for v in accessor(sampler['input'])];values=accessor(sampler['output'])
            need(len(times)==len(values)==31 and all(abs(t-i/30)<1e-6 for i,t in enumerate(times)),'DIRECT_SAMPLE_RATE')
            node=ch['target']['node'];path=ch['target']['path'];key={'translation':'position','rotation':'rotation_xyzw','scale':'scale'}[path]
            need(g['nodes'][node]['name'] in bones and (node,key) not in seen,'DIRECT_CHANNEL_BINDING')
            seen.add((node,key));samplers.append((node,key,times,values));channels+=1
        need(len(seen)==3*len(bones),'DIRECT_CHANNEL_COUNT')
        for sample in observed['clips'][animation['name']]['samples']:
            need(set(sample['bones'])==set(bones) and 0<=sample['time']<=1,'DIRECT_POSE_SET')
            local={i:dict(v) for i,v in base.items()};time=sample['time']
            for node,key,times,values in samplers:
                left=max(i for i,t in enumerate(times) if t<=time+1e-7);right=min(left+1,30)
                alpha=0 if left==right else max(0,min(1,(time-times[left])/(times[right]-times[left])))
                a,b=values[left],values[right]
                if key=='rotation_xyzw' and sum(x*y for x,y in zip(a,b))<0:b=[-v for v in b]
                local[node][key]=[x*(1-alpha)+y*alpha for x,y in zip(a,b)]
            actual=worlds(local)
            for name,pose in sample['bones'].items():
                max_pose=max(max_pose,error(matrix(local[names[name]]),matrix(pose['local'])),error(actual[names[name]],matrix(pose['world'])))
                pose_bones+=1
            max_socket=max(max_socket,error(actual[names['socket_hand_r']],matrix(sample['socket_world'])))
    need(max_rest<2e-5,'DIRECT_REST_TRANSFORM')
    need(max_bind<2e-5,'DIRECT_INVERSE_BIND')
    need(max_pose<2e-5,'DIRECT_POSE_TRANSFORM')
    need(max_socket<2e-5,'DIRECT_SOCKET_TRANSFORM')
    return {'bones':len(bones),'skins':1,'skin_meshes':len(skins),'animation_channels':channels,
        'sampled_bones':pose_bones,'max_rest_matrix_component_error':max_rest,
        'max_inverse_bind_identity_error':max_bind,'max_pose_matrix_component_error':max_pose,
        'max_socket_matrix_component_error':max_socket,'formal_acceptance':False}


def verify_native_fixture(run_root):
    """Read fixed diagnostic slots, bind source snapshots, hashes and host exit."""
    root=Path(run_root); inputs={}
    def read(name,cap=c.MAX_ARTIFACT):
        with (root/name).open('rb') as stream:raw=stream.read(cap+1)
        c.need(len(raw)<=cap,'DIRECT_INPUT_CAP');inputs[name]=c.sha(raw);return raw
    report=json.loads(read('fixture/producer-report.json'))
    c.need(report['schema']==c.SCHEMA and report['catalog']==c.asset_catalog(),'DIRECT_FIXTURE_CONTRACT')
    c.need(report['observed_sha256']==c.digest(report['observed']),'DIRECT_OBSERVATION_HASH')
    c.need(set(report['observed']['rig']['bones'])=={b[0] for b in c.BONES}
           and set(report['observed']['clips'])==set(c.CLIPS)
           and all(len(clip['samples'])==33 for clip in report['observed']['clips'].values()),'DIRECT_FIXTURE_SET')
    raw=read('fixture/fixture.glb');blend=read('fixture/fixture.blend')
    for name,data in (('fixture.glb',raw),('fixture.blend',blend)):
        c.need(report['artifacts'][name]=={'sha256':c.sha(data),'bytes':len(data)},'DIRECT_ARTIFACT_HASH')
    sources=report['pins']['source_files'];c.need(len(sources)<=64,'DIRECT_SOURCE_CAP')
    for name,wanted in sources.items():
        c.need(not Path(name).is_absolute() and '..' not in Path(name).parts,'DIRECT_SOURCE_PATH')
        c.need(c.sha(read('source/'+name))==wanted,'DIRECT_SOURCE_HASH')
    c.need(c.digest(sources)==report['pins']['source_sha256'],'DIRECT_SOURCE_AGGREGATE')
    capture=json.loads(read('host/capture.json',262144));exit_row=json.loads(read('host/process-exit.json',262144))
    c.need(capture['natural_tree_exit'] and capture['wrapper_exit_code']==exit_row['exit_code']==0
           and capture['actual_process_exit']==exit_row and capture['job']['zero_observed']
           and capture['job']['active_count']==0 and not capture['job']['tainted'],'DIRECT_HOST_EXIT')
    stdout=read('host/stdout.txt',262144).decode('utf-8');stderr=read('host/stderr.txt',262144)
    c.need(stderr==b'' and 'ERROR' not in stdout,'DIRECT_ENGINE_ERROR')
    lines=[line for line in stdout.splitlines() if 'WARNING' in line]
    c.need(all('| WARNING: ' in line for line in lines),'DIRECT_WARNING_FORMAT')
    warnings=dict(Counter(line.split('| WARNING: ',1)[1] for line in lines))
    c.need(warnings==EXPECTED_EXPORT_WARNINGS,'DIRECT_WARNING_SET')
    result=verify_direct_glb(raw,report)
    result.update({'input_sha256':inputs,'source_sha256':report['pins']['source_sha256'],
        'observed_sha256':report['observed_sha256'],'warnings':warnings,
        'exported_images':c.exported_image_observation(raw,report['observed']['images']),
        'proof_scope':'bounded host source/GLB bone, inverse-bind, animation, socket and image readback; not acceptance'})
    return result


def extents(vertices):
    return tuple((min(v[i] for v in vertices), max(v[i] for v in vertices)) for i in range(3))


def volume(vertices, faces):
    total = 0.0
    for face in faces:
        a = vertices[face[0]]
        for i in range(1, len(face)-1):
            b, d = vertices[face[i]], vertices[face[i+1]]
            cross = (b[1]*d[2]-b[2]*d[1], b[2]*d[0]-b[0]*d[2], b[0]*d[1]-b[1]*d[0])
            total += sum(a[k]*cross[k] for k in range(3))/6
    return total


class ProducerContractTests(unittest.TestCase):
    def direct_fixture(self, mutation=None):
        binary=b'';views=[];accessors=[]
        def add(values,kind):
            nonlocal binary
            payload=struct.pack('<'+'f'*sum(len(v) for v in values),*(v for row in values for v in row))
            views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(payload)})
            binary+=payload
            accessors.append({'bufferView':len(views)-1,'componentType':5126,'type':kind,'count':len(values)})
            return len(accessors)-1
        time=add([(i/30,) for i in range(31)],'SCALAR')
        position=add([(.02 if mutation=='pose' else 0,0,0)]*31,'VEC3')
        rotation=add([(0,0,0,1)]*31,'VEC4');scale=add([(1,1,1)]*31,'VEC3')
        ibm=[float(i%5==0) for i in range(16)]
        if mutation=='bind':ibm[0]=.5
        bind=add([ibm],'MAT4')
        nodes=[{'name':c.RIG,'children':[1]},{'name':'bn_root','children':[2]},
               {'name':'socket_hand_r'},{'name':'chr_fixture_avatar_lod0','skin':0}]
        if mutation=='rest':nodes[1]['translation']=[.1,0,0]
        if mutation=='socket':nodes[2]['translation']=[.1,0,0]
        samplers=[{'input':time,'output':value,'interpolation':'LINEAR'} for value in (position,rotation,scale)]
        channels=[{'sampler':i,'target':{'node':1,'path':key}} for i,key in enumerate(('translation','rotation','scale'))]
        document={'nodes':nodes,'skins':[{'joints':[1],'inverseBindMatrices':bind}],
            'accessors':accessors,'bufferViews':views,
            'animations':[{'name':name,'channels':channels,'samplers':samplers} for name in c.CLIPS]}
        encoded=c.encoded(document);encoded+=b' '*(-len(encoded)%4)
        raw=b'glTF'+struct.pack('<4I',2,28+len(encoded)+len(binary),len(encoded),0x4e4f534a)+encoded+struct.pack('<2I',len(binary),0x004e4942)+binary
        identity={'position':[0,0,0],'rotation_xyzw':[0,0,0,1],'scale':[1,1,1]}
        report={'observed':{'rig':{'name':c.RIG,'bones':{'bn_root':{'parent':None,'rest_gltf_local':identity,'rest_gltf_world':identity}}},
            'meshes':{'chr_fixture_avatar_lod0':{'skinned':True}},
            'clips':{name:{'samples':[{'time':t,'bones':{'bn_root':{'local':identity,'world':identity}},'socket_world':identity}
                                     for t in (0,.5,1)]} for name in c.CLIPS}}}
        return raw,report

    def test_independent_glb_pose_inverse_bind_and_socket_verifier(self):
        result=verify_direct_glb(*self.direct_fixture())
        self.assertEqual(result['sampled_bones'],6)
        self.assertEqual(result['animation_channels'],6)
        for mutation,code in (('rest','DIRECT_REST_TRANSFORM'),('bind','DIRECT_INVERSE_BIND'),
                              ('pose','DIRECT_POSE_TRANSFORM'),('socket','DIRECT_SOCKET_TRANSFORM')):
            with self.subTest(mutation=mutation),self.assertRaisesRegex(c.ProducerRejected,code):
                verify_direct_glb(*self.direct_fixture(mutation))

    def test_fixed_catalog_and_shared_names(self):
        catalog = c.asset_catalog()
        self.assertEqual(validate_catalog(catalog), {'schema':'HH-ASSET-NAMES-1','assets':8,'nodes':13})
        assets = {a['asset_id']:a for a in catalog['assets']}
        names = [n['name'] for a in assets.values() for n in a['nodes']]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(c.BONES), 12)
        seen = set()
        for name, parent, head, tail in c.BONES:
            self.assertTrue(parent is None or parent in seen)
            self.assertNotEqual(head, tail)
            seen.add(name)
        for material, owner in c.MATERIAL_OWNERS.items():
            self.assertIn(material, assets[owner]['materials'])
        self.assertEqual(assets['chr_fixture_avatar']['sockets'], ['socket_hand_r'])

    def test_box_winding_volume_and_triangles(self):
        for divisions in (1,2):
            vertices, faces, weights = c.box_geometry([((2,-3,4),(.3,.5,.7),'bn_root')],divisions)
            self.assertAlmostEqual(volume(vertices,faces),.3*.5*.7)
            self.assertEqual(sum(len(f)-2 for f in faces),12*divisions**2)
            self.assertEqual(len(vertices),len(weights))
            self.assertEqual(set(weights), {'bn_root'})
            self.assertTrue(all(len(set(f))==len(f) for f in faces))

    def test_arrow_axis_and_positive_winding(self):
        expected = {'x':(0,1),'y':(1,1),'z':(2,1),'front':(1,-1)}
        for axis, (component,sign) in expected.items():
            vertices, faces, weights = c.arrow_geometry((0,0,0),axis)
            self.assertAlmostEqual(volume(vertices,faces),.045*.045*.5 + .22*.22*.25/3)
            self.assertEqual(sum(len(f)-2 for f in faces),18)
            low, high = extents(vertices)[component]
            self.assertEqual((low,high),(0,.75) if sign>0 else (-.75,0))
            self.assertEqual(set(weights),{None})

    def test_lods_keep_bounds_rig_and_reduce_triangles(self):
        bones = {b[0] for b in c.BONES}
        for parts, expected in ((c.BODY,(576,144)),(c.OUTFIT,(288,72))):
            lods = [c.box_geometry(parts,d) for d in (2,1)]
            for a,b in zip(extents(lods[0][0]),extents(lods[1][0])):
                for x,y in zip(a,b): self.assertAlmostEqual(x,y)
            for lod, (vertices,faces,weights) in enumerate(lods):
                self.assertEqual(sum(len(f)-2 for f in faces),expected[lod])
                self.assertTrue(set(weights)<=bones)
                self.assertEqual(len(vertices),len(weights))
                self.assertGreater(volume(vertices,faces),0)
            self.assertEqual(set(lods[0][2]),set(lods[1][2]))

    def test_in_place_loop_and_distinct_animation(self):
        for clip in c.CLIPS:
            for frame in range(31):
                pose = c.pose_angles(clip,frame)
                self.assertEqual(pose['bn_root'],[0,0,0])
                self.assertEqual(set(pose),{b[0] for b in c.BONES})
                self.assertTrue(all(math.isfinite(v) for angles in pose.values() for v in angles))
            for name in c.pose_angles(clip,0):
                for a,b in zip(c.pose_angles(clip,0)[name],c.pose_angles(clip,30)[name]):
                    self.assertAlmostEqual(a,b,places=12)
        self.assertNotEqual(c.pose_angles('idle',7.5), c.pose_angles('walk',7.5))
        for clip,frame in (('run',0),('idle',True),('walk',31),('walk',float('nan'))):
            with self.assertRaises(c.ProducerRejected): c.pose_angles(clip,frame)

    def test_original_png_roundtrip_and_corruption_rejection(self):
        pixels = [(i/15,.5,1,1) for i in range(16)]
        raw = c.png_rgba8(pixels)
        rgba = bytes(round(v*255) for p in pixels for v in p)
        self.assertEqual(c.source_png_pixels(raw),rgba)
        self.assertLess(len(raw),256)
        for bad in (raw[:-1],raw+b'external',b'x'+raw[1:],raw[:40]+bytes([raw[40]^1])+raw[41:]):
            with self.assertRaises(c.ProducerRejected): c.source_png_pixels(bad)
        with self.assertRaises(c.ProducerRejected): c.png_rgba8([(0,0,0,2)]*16)

    def test_exported_pixels_bind_actual_png_and_material_samplers(self):
        pngs=[c.png_rgba8([color]*16) for color in ((.8,.2,.1,1),(.5,.5,1,1),(1,.55,.3,1))]
        names=list(c.TEXTURE_BINDINGS.values())
        expected={name:{'packed_png_sha256':c.sha(png),'rgba8_sha256':c.sha(c.source_png_pixels(png))}
                  for name,png in zip(names,pngs)}
        def glb(payloads, sampler=None):
            binary=b''; views=[]
            for png in payloads:
                views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(png)})
                binary+=png+b'\0'*(-len(png)%4)
            document={'images':[{'name':name,'bufferView':i,'mimeType':'image/png'} for i,name in enumerate(names)],
                'bufferViews':views,'textures':[{'source':i,'sampler':0} for i in range(3)],
                'samplers':[sampler or {'magFilter':9728,'minFilter':9984}],
                'materials':[{'name':'mat_fixture_crate','normalTexture':{'index':1},
                    'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicRoughnessTexture':{'index':2}}}]}
            encoded=c.encoded(document);encoded+=b' '*(-len(encoded)%4)
            return (b'glTF'+struct.pack('<4I',2,28+len(encoded)+len(binary),len(encoded),0x4e4f534a)
                    +encoded+struct.pack('<2I',len(binary),0x004e4942)+binary)
        result=c.exported_image_observation(glb(pngs),expected)
        self.assertEqual(len(result['images']),3)
        self.assertTrue(result['exact_source_pngs'])
        # Regression: native01 packed correct source bytes but exported black pixels.
        black=c.png_rgba8([(0,0,0,1)]*16)
        with self.assertRaisesRegex(c.ProducerRejected,'EXPORT_IMAGE_PIXELS'):
            c.exported_image_observation(glb([black]*3),expected)
        with self.assertRaisesRegex(c.ProducerRejected,'EXPORT_SAMPLER'):
            c.exported_image_observation(glb(pngs,{'magFilter':9729,'minFilter':9984}),expected)

    def test_native_byte_image_pixels_are_encoded_bottom_up(self):
        png=c.png_rgba8([(i/15,.55,.28,1) for i in range(16)])
        rgba=c.source_png_pixels(png)
        native=[value/255 for y in reversed(range(4)) for value in rgba[y*16:(y+1)*16]]
        img=SimpleNamespace(source='FILE',is_dirty=False,is_float=False,size=(4,4),channels=4,
            colorspace_settings=SimpleNamespace(name='sRGB'),packed_file=SimpleNamespace(data=png),pixels=native)
        self.assertEqual(image_observation(img)['native_pixels_max_error'],0)
        img.pixels=[0]*64
        with self.assertRaisesRegex(ValueError,'IMAGE_NATIVE_PIXEL_MISMATCH'):
            image_observation(img)
        img.pixels=[v if i%4==3 else v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
                    for i,v in enumerate(native)]
        with self.assertRaisesRegex(ValueError,'IMAGE_NATIVE_PIXEL_MISMATCH'):
            image_observation(img)

    def test_only_empty_absolute_child_root_and_fixed_slots(self):
        with tempfile.TemporaryDirectory() as base:
            parent=Path(base)
            child=parent/'run'; child.mkdir()
            slots=c.admit_root(child,parent)
            self.assertEqual(set(slots),set(c.SLOTS))
            self.assertTrue(all(p.parent==child for p in slots.values()))
            for bad in (parent,Path('relative'),parent/'run'/'..'/'run',parent.parent):
                with self.assertRaises(c.ProducerRejected): c.admit_root(bad,parent)
            (child/'unexpected').write_text('occupied')
            with self.assertRaises(c.ProducerRejected): c.admit_root(child,parent)

    def test_symlink_staging_rejected_where_supported(self):
        with tempfile.TemporaryDirectory() as base:
            parent=Path(base); target=parent/'target'; target.mkdir()
            link=parent/'link'
            try: link.symlink_to(target,target_is_directory=True)
            except OSError: self.skipTest('Host does not grant symlink creation')
            with self.assertRaises(c.ProducerRejected): c.admit_root(link,parent)


if __name__=='__main__':
    unittest.main()
