import copy
import json
from pathlib import Path
import sys
import unittest
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.ui_host import load
from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot,GLBRejected
from test_glb_preflight import pack,unpack
import test_glb_preflight as baseline
queue=load('blender-addon/ui_queue.py')


class MaterialContractTests(unittest.TestCase):
    def value(self):
        return {'schema':queue.SCHEMA,'command_id':'material','operation':'material.set_principled',
            'expected_revision':'sha256:'+'1'*64,'expected_context':{'mode':'OBJECT','active_id':None,'selected_ids':[]},
            'payload':{'object_id':'box','material_id':'red','base_color':[.8,.1,.1],'metallic':.3,'roughness':.7}}
    def test_closed_typed_material_command(self):
        value=self.value();self.assertEqual(queue.parse(queue.c.canonical(value)),value)
    def test_material_range_types_and_texture_injection(self):
        for field,value in (('base_color',[1,0,0,.5]),('base_color',[True,0,0]),('metallic',True),
                            ('roughness',float('nan')),('roughness',1.01),('material_id','../escape'),('texture','arbitrary.png')):
            command=self.value();command['payload'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):queue.parse(queue.c.canonical(command))


class MaterialGLBTests(unittest.TestCase):
    def setUp(self):
        raw=(Path(__file__).with_name('fixtures')/'box-export-baseline.glb').read_bytes()
        self.value,self.binary=unpack(raw)
        self.material={'name':'HH_Material_red','pbrMetallicRoughness':{'baseColorFactor':[.8,.1,.1,1],
            'metallicFactor':.3,'roughnessFactor':.7},'doubleSided':True}
        self.value['materials']=[self.material];self.value['meshes'][0]['primitives'][0]['material']=0
    def test_bounded_material_binds_native_source(self):
        report=inspect_glb(pack(self.value,self.binary));self.assertEqual(report['materials'],1)
        source=baseline.GLBTests.source_snapshot(self)
        source['objects'][0]['material']={'material_id':'red','name':'HH_Material_red','base_color':[.8,.1,.1,1],
            'metallic':.3,'roughness':.7,'double_sided':True,'alpha_mode':'OPAQUE'}
        self.assertTrue(bind_snapshot(report,source))
        source['objects'][0]['material']['roughness']=.2
        with self.assertRaisesRegex(GLBRejected,'SOURCE_MATERIAL'):bind_snapshot(report,source)
    def test_material_profile_rejects_unsupported_data(self):
        changes=[lambda m:m.update(extensions={}),lambda m:m.update(alphaMode='BLEND'),
            lambda m:m['pbrMetallicRoughness'].update(baseColorTexture={'index':0}),
            lambda m:m['pbrMetallicRoughness'].update(metallicFactor=True),
            lambda m:m['pbrMetallicRoughness'].update(roughnessFactor=2),
            lambda m:m['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1,.5])]
        for change in changes:
            value=copy.deepcopy(self.value);change(value['materials'][0])
            with self.subTest(change=change),self.assertRaises(GLBRejected):inspect_glb(pack(value,self.binary))
    def test_unused_missing_and_boolean_material_references(self):
        for ref in (True,1,-1):
            value=copy.deepcopy(self.value);value['meshes'][0]['primitives'][0]['material']=ref
            with self.assertRaises(GLBRejected):inspect_glb(pack(value,self.binary))
        del self.value['meshes'][0]['primitives'][0]['material']
        with self.assertRaisesRegex(GLBRejected,'UNUSED_MATERIAL'):inspect_glb(pack(self.value,self.binary))


if __name__=='__main__':unittest.main()
