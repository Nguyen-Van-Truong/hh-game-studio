import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot,GLBRejected,MAX_BYTES
FIXTURE=Path(__file__).with_name('fixtures')


def unpack(raw):
    n=struct.unpack_from('<I',raw,12)[0]
    return json.loads(raw[20:20+n]),bytearray(raw[28+n:])


def pack(value,binary):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode();raw+=b' '*((-len(raw))%4)
    return struct.pack('<4sIIII',b'glTF',2,28+len(raw)+len(binary),len(raw),0x4e4f534a)+raw+struct.pack('<II',len(binary),0x004e4942)+binary


class GLBTests(unittest.TestCase):
    def setUp(self):
        self.raw=(FIXTURE/'box-export-baseline.glb').read_bytes()
        self.value,self.binary=unpack(self.raw)
    def reject(self,change):
        change(self.value)
        with self.assertRaises(ValueError):inspect_glb(pack(self.value,self.binary))
    def test_actual_native_baseline_hash_and_geometry(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),json.loads((FIXTURE/'box-export-baseline.json').read_bytes())['sha256'])
        row=inspect_glb(self.raw);self.assertEqual(row['triangles'],12);self.assertEqual(row['objects'],1)
        self.assertEqual(row['meshes'][0]['translation'],[2,4,3]);self.assertEqual(row['uri_count'],0)
    def test_total_length_tamper_and_truncation(self):
        for raw in (self.raw[:-1],self.raw+b'\0\0\0\0'):
            with self.assertRaises(GLBRejected):inspect_glb(raw)
    def test_frame_byte_cap(self):
        with self.assertRaisesRegex(GLBRejected,'BYTE_CAP'):inspect_glb(b'x'*(MAX_BYTES+1))
    def test_uri_never_fetched(self):self.reject(lambda d:d['buffers'][0].update(uri='http://127.0.0.1/private'))
    def test_unknown_extension_rejected(self):self.reject(lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression']))
    def test_image_and_material_data_rejected(self):
        self.reject(lambda d:d.update(images=[{'uri':'data:image/png;base64,AAAA'}]))
    def test_accessor_span_outside_buffer_rejected(self):self.reject(lambda d:d['accessors'][0].update(byteOffset=100000))
    def test_view_outside_binary_rejected(self):self.reject(lambda d:d['bufferViews'][0].update(byteLength=100000))
    def test_accessor_count_cap(self):self.reject(lambda d:d['accessors'][0].update(count=10**8))
    def test_boolean_reference_rejected(self):self.reject(lambda d:d['nodes'][0].update(mesh=False))
    def test_sparse_accessor_rejected(self):self.reject(lambda d:d['accessors'][0].update(sparse={}))
    def test_hierarchy_rejected(self):self.reject(lambda d:d['nodes'][0].update(children=[0]))
    def test_bad_stride_rejected(self):self.reject(lambda d:d['bufferViews'][0].update(byteStride=1))
    def test_false_declared_bounds_rejected(self):
        index=self.value['meshes'][0]['primitives'][0]['attributes']['POSITION']
        self.reject(lambda d:d['accessors'][index].update(min=[-999,-999,-999]))
    def test_nan_decoded_vertex_rejected(self):
        a=self.value['accessors'][self.value['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        v=self.value['bufferViews'][a['bufferView']]
        struct.pack_into('<f',self.binary,v.get('byteOffset',0)+a.get('byteOffset',0),float('nan'))
        with self.assertRaisesRegex(GLBRejected,'NONFINITE'):inspect_glb(pack(self.value,self.binary))
    def test_index_outside_vertex_array_rejected(self):
        a=self.value['accessors'][self.value['meshes'][0]['primitives'][0]['indices']]
        v=self.value['bufferViews'][a['bufferView']]
        struct.pack_into('<H' if a['componentType']==5123 else '<I',self.binary,v.get('byteOffset',0)+a.get('byteOffset',0),65535)
        with self.assertRaises(GLBRejected):inspect_glb(pack(self.value,self.binary))

    def source_snapshot(self):
        return {'objects':[{'name':'GT04_box','location':[2,-3,4],'rotation':[0,0,0],'scale':[1,2,1],
            'vertices':[[x,y,z] for x in (-.5,.5) for y in (-1,1) for z in (-1.5,1.5)]}]}

    def test_actual_output_binds_source_geometry_pose_and_name(self):
        self.assertTrue(bind_snapshot(inspect_glb(self.raw),self.source_snapshot()))

    def test_output_readback_must_match_source_not_merely_valid_glb(self):
        for field,value in (('name','wrong-box'),('translation',[2,4,4]),('scale',[1,1,1]),
                            ('rotation',[1,0,0,0]),('unique_positions',[[0,0,0]]*8)):
            report=inspect_glb(self.raw);report['meshes'][0][field]=value
            with self.subTest(field=field),self.assertRaises(GLBRejected):bind_snapshot(report,self.source_snapshot())

    def test_xyz_basis_rotation_quaternion_sign_equivalence(self):
        import math
        source=self.source_snapshot();source['objects'][0]['rotation']=[0,0,math.pi/2]
        report=inspect_glb(self.raw);report['meshes'][0]['rotation']=[0,-math.sqrt(.5),0,-math.sqrt(.5)]
        self.assertTrue(bind_snapshot(report,source))


if __name__=='__main__':unittest.main()
