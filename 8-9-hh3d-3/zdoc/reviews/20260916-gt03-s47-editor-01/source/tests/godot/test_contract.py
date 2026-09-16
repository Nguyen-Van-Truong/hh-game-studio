"""GT03 catalog checks use inert snapshots; no Godot/filesystem effect exists."""
import copy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_contract', STUDIO/'godot-addon/contract.py')
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)
from studio.protocol.core import Discovery, Request, ValidationError, canonical_bytes


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.context = contract.ValidationContext('project.fixture', 'sha256:'+'1'*64, 1,
            'lease.fixture', 7, 31_000, 1000,
            (contract.NodeState('root', None, 'Node3D', 'Fixture'),
             contract.NodeState('box', 'root', 'MeshInstance3D', 'Box', box_size=(1, 1, 1))),
            ((contract.SCENE_PATH, '2'*64), (contract.SCRIPT_PATH, '3'*64)), True, True)

    def request(self, operation='scene.node.update', *, target=None, payload=None, **changes):
        if payload is None:
            payload = {'expected_generation': 1, 'changes': {'position': [1, 2, 3]}}
        if target is None:
            target = {'stable_id': 'box'}
        values = dict(command_id='command.fixture', project_id='project.fixture', operation=operation,
            lease_id='lease.fixture', fencing_epoch=7, expected_revision='sha256:'+'1'*64,
            target=target, payload=payload, payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=2000)
        values.update(changes)
        return Request(**values)

    def assert_reject(self, request, code, *, context=None):
        before = copy.deepcopy((request.as_dict(), context or self.context))
        with self.assertRaises(ValidationError) as raised:
            contract.validate_request(request, context or self.context)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual((request.as_dict(), context or self.context), before)

    def create_payload(self, node_type='MeshInstance3D'):
        value = {'expected_generation': 1, 'stable_id': 'new-box', 'node_type': node_type,
            'name': 'NewBox', 'position': [0, 0, 0], 'rotation_degrees': [0, 0, 0], 'scale': [1, 1, 1]}
        if node_type == 'MeshInstance3D':
            value['box_size'] = [1, 2, 3]
        return value

    def test_declared_catalog_does_not_advertise_runtime_without_explicit_backend(self):
        declared = contract.catalog()
        self.assertTrue(all(not row['implemented'] and not row['runtime_enabled'] for row in declared['operations'].values()))
        self.assertEqual(contract.discovery('project.fixture').capabilities, ())
        enabled = frozenset({'scene.inspect', 'scene.node.update'})
        found = Discovery.from_dict(contract.discovery('project.fixture', implemented=enabled,
            runtime_enabled=enabled).as_dict())
        self.assertTrue(found.supports('scene.node.update'))
        self.assertFalse(found.supports('scene.save'))
        self.assertFalse(found.supports('script_text.replace'))
        with self.assertRaisesRegex(ValidationError, 'GODOT_INVALID_RUNTIME_CATALOG'):
            contract.discovery('project.fixture', runtime_enabled=enabled)
        declared['operations'].clear()
        self.assertEqual(len(contract.catalog()['operations']), 9)

    def test_shared_digest_projection_and_preview_copy_without_authorization_or_io(self):
        request = self.request()
        before = copy.deepcopy((request.as_dict(), self.context))
        # Import has read the fixed catalog. Validation itself must open nothing.
        with (mock.patch('builtins.open', side_effect=AssertionError('file effect')),
              mock.patch.object(Path, 'open', side_effect=AssertionError('path effect'))):
            result = contract.validate_request(request, self.context)
        self.assertEqual(result.request_digest, request.digest)
        self.assertEqual(set(result.projection), {'operation','command_id','expected_revision',
            'expected_generation','target_stable_id','payload'})
        self.assertEqual(result.preview['affected_files'], [contract.SCENE_PATH])
        self.assertFalse(result.preview['changes_applied'])
        self.assertFalse(result.preview['runtime_authorized'])
        self.assertEqual(result.preview['diff'][0]['before']['position'], [0, 0, 0])
        self.assertEqual(result.preview['diff'][0]['after']['position'], [1, 2, 3])
        result.projection['payload']['changes']['position'][0] = 900
        result.preview['affected_files'].clear()
        self.assertEqual(result.projection['payload']['changes']['position'], [1, 2, 3])
        self.assertEqual((request.as_dict(), self.context), before)

    def test_create_typed_mesh_and_node_with_exact_resource_policy(self):
        for node_type in ('Node3D', 'MeshInstance3D'):
            payload = self.create_payload(node_type)
            request = self.request('scene.node.create', target={'stable_id':'root'}, payload=payload)
            result = contract.validate_request(request, self.context)
            self.assertEqual(result.preview['diff'][0]['after']['parent_id'], 'root')
            self.assertEqual('box_size' in result.preview['diff'][0]['after'], node_type == 'MeshInstance3D')
        for payload in (self.create_payload('Camera3D'), {**self.create_payload('Node3D'), 'box_size':[1,1,1]},
                        {k:v for k,v in self.create_payload().items() if k!='box_size'}):
            with self.assertRaises(ValidationError):
                contract.validate_request(self.request('scene.node.create',target={'stable_id':'root'},payload=payload),self.context)

    def test_finite_strict_numeric_caps_and_properties_have_no_effect(self):
        cases = [('position', [True,0,0], 'GODOT_INVALID_COMPONENT'),
                 ('position', [10001,0,0], 'GODOT_INVALID_COMPONENT'),
                 ('rotation_degrees',[0,361,0], 'GODOT_INVALID_COMPONENT'),
                 ('scale',[1,0,1], 'GODOT_INVALID_COMPONENT'),
                 ('box_size',[1,1001,1], 'GODOT_INVALID_COMPONENT'),
                 ('position',[1,2], 'GODOT_INVALID_VECTOR'),
                 ('name','../outside', 'GODOT_INVALID_NAME'),
                 ('script','res://evil.gd', 'GODOT_UNSUPPORTED_PROPERTY')]
        for name,value,code in cases:
            with self.subTest(name=name,value=value):
                self.assert_reject(self.request(payload={'expected_generation':1,'changes':{name:value}}),code)
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValidationError):
                self.request(payload={'expected_generation':1,'changes':{'position':[value,0,0]}})
        self.assert_reject(self.request(target={'stable_id':'root'},payload={'expected_generation':1,
            'changes':{'box_size':[1,1,1]}}),'GODOT_RESOURCE_SCOPE')

    def test_revision_generation_project_lease_deadline_and_stop_are_separate_checks(self):
        cases=[({'expected_revision':'sha256:'+'4'*64},'GODOT_STALE_REVISION'),
               ({'project_id':'other'},'GODOT_PROJECT_MISMATCH'),
               ({'lease_id':'other'},'GODOT_STALE_LEASE'),
               ({'fencing_epoch':8},'GODOT_STALE_LEASE'),
               ({'deadline_ms':1000},'GODOT_DEADLINE_EXPIRED'),
               ({'deadline_ms':31001},'GODOT_DEADLINE_EXPIRED')]
        for changes,code in cases:
            with self.subTest(changes=changes): self.assert_reject(self.request(**changes),code)
        self.assert_reject(self.request(payload={'expected_generation':2,'changes':{'position':[0,0,0]}}),'GODOT_STALE_GENERATION')
        self.assert_reject(self.request(payload={'expected_generation':True,'changes':{'position':[0,0,0]}}),'GODOT_INVALID_INTEGER')
        self.assert_reject(self.request(),'GODOT_STOPPED',context=replace(self.context,stopped=True))
        read=self.request('scene.inspect',target={'stable_id':'root'},payload={'expected_generation':1,'offset':0,'limit':64})
        contract.validate_request(read,replace(self.context,stopped=True))

    def test_stable_identity_hierarchy_and_name_collision_before_apply(self):
        self.assert_reject(self.request(target={'stable_id':'missing'}),'GODOT_STALE_STABLE_ID')
        for field,value,code in [('stable_id','box','GODOT_DUPLICATE_STABLE_ID'),
                                 ('stable_id','../../x','GODOT_INVALID_STABLE_ID'),
                                 ('name','Box','GODOT_DUPLICATE_SIBLING_NAME')]:
            payload=self.create_payload();payload[field]=value
            self.assert_reject(self.request('scene.node.create',target={'stable_id':'root'},payload=payload),code)
        nodes=self.context.nodes+(contract.NodeState('box', 'root', 'Node3D', 'Duplicate'),)
        self.assert_reject(self.request(),'GODOT_DUPLICATE_STABLE_ID',context=replace(self.context,nodes=nodes))
        nodes=(self.context.nodes[0],contract.NodeState('orphan','missing','Node3D','Orphan'))
        self.assert_reject(self.request(),'GODOT_INVALID_HIERARCHY',context=replace(self.context,nodes=nodes))

    def test_node_count_depth_caps_and_remove_leaf_checkpoint(self):
        nodes=(self.context.nodes[0],)+tuple(contract.NodeState('n'+str(i),'root','Node3D','N'+str(i)) for i in range(63))
        request=self.request('scene.node.create',target={'stable_id':'root'},payload=self.create_payload())
        self.assert_reject(request,'GODOT_NODE_LIMIT',context=replace(self.context,nodes=nodes))
        nodes=(self.context.nodes[0],)+tuple(contract.NodeState('n'+str(i),'root' if i==1 else 'n'+str(i-1),
            'Node3D','N'+str(i)) for i in range(1,16))
        request=self.request('scene.node.create',target={'stable_id':'n15'},payload=self.create_payload())
        self.assert_reject(request,'GODOT_DEPTH_LIMIT',context=replace(self.context,nodes=nodes))
        request=self.request('scene.node.remove',payload={'expected_generation':1})
        self.assertTrue(contract.validate_request(request,self.context).preview['checkpoint_required'])
        root=self.request('scene.node.remove',target={'stable_id':'root'},payload={'expected_generation':1})
        self.assert_reject(root,'GODOT_ROOT_REMOVE_FORBIDDEN')
        nodes=self.context.nodes+(contract.NodeState('child','box','Node3D','Child'),)
        self.assert_reject(request,'GODOT_NONLEAF_REMOVE_FORBIDDEN',context=replace(self.context,nodes=nodes))

    def test_script_is_bounded_data_and_path_is_exact_before_any_parser(self):
        text='@tool\nextends Node3D\n# deliberately invalid code remains data\n!!!\n'
        payload={'expected_generation':1,'expected_sha256':'3'*64,'text':text}
        request=self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},payload=payload)
        result=contract.validate_request(request,self.context)
        self.assertEqual(result.projection['payload']['text'],text)
        self.assertEqual(result.preview['script_parse_status'],'NOT_RUN')
        self.assertEqual(result.preview['diff'][0]['after_sha256'],hashlib.sha256(text.encode()).hexdigest())
        for path in ('res://scripts/fixture_actor.gd','Scripts/fixture_actor.gd','scripts\\fixture_actor.gd',
                     '../scripts/fixture_actor.gd','scripts/fixture_actor.gd:stream','C:/fixture_actor.gd',
                     '//host/share/fixture_actor.gd','scripts/./fixture_actor.gd','scripts/fixture_actor.gd ',
                     'scripts/fixture_acto\u0301r.gd'):
            with self.subTest(path=path):
                self.assert_reject(self.request('script_text.replace',target={'path':path},payload=payload),'GODOT_PATH_NOT_ALLOWED')
        for text,code in [('é'*9000,'GODOT_SCRIPT_LIMIT'),('line\r\n','GODOT_INVALID_SCRIPT_TEXT'),('\0','GODOT_INVALID_SCRIPT_TEXT')]:
            self.assert_reject(self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},
                payload={**payload,'text':text}),code)
        self.assert_reject(self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},
            payload={**payload,'expected_sha256':'4'*64}),'GODOT_STALE_SCRIPT')

    def test_preview_reuses_semantics_but_rejects_recursion_and_generation_conflict(self):
        inner={'operation':'scene.node.update','target':{'stable_id':'box'},
               'payload':{'expected_generation':1,'changes':{'position':[2,3,4]}}}
        request=self.request('scene.preview',target={'stable_id':'root'},payload={'expected_generation':1,**inner})
        result=contract.validate_request(request,self.context)
        self.assertEqual(result.preview['preview_of'],'scene.node.update')
        self.assertFalse(result.preview['changes_applied'])
        self.assertEqual(set(result.projection['preview_command']), {'operation','command_id','expected_revision',
            'expected_generation','target_stable_id','payload'})
        for operation in ('scene.preview','scene.save','scene.inspect','os.execute'):
            self.assert_reject(self.request('scene.preview',target={'stable_id':'root'},
                payload={'expected_generation':1,**inner,'operation':operation}),'GODOT_PREVIEW_OPERATION_FORBIDDEN')
        self.assert_reject(self.request('scene.preview',target={'stable_id':'root'},payload={'expected_generation':1,
            **inner,'payload':{'expected_generation':2,'changes':{'position':[2,3,4]}}}),'GODOT_STALE_GENERATION')

    def test_save_fixed_complete_file_set_and_history_revision_without_false_diff(self):
        files=dict(self.context.file_hashes)
        request=self.request('scene.save',target={'stable_id':'root'},payload={'expected_generation':1,'expected_files':files})
        result=contract.validate_request(request,self.context)
        self.assertEqual(result.preview['affected_files'],[contract.SCENE_PATH,contract.SCRIPT_PATH])
        self.assertEqual(result.preview['diff'][0]['after_files'],'requires_godot_staged_save_readback')
        for changed in ({contract.SCENE_PATH:'2'*64},{**files,'outside':'4'*64}):
            self.assert_reject(self.request('scene.save',target={'stable_id':'root'},
                payload={'expected_generation':1,'expected_files':changed}),'GODOT_INVALID_SHAPE')
        self.assert_reject(self.request('scene.save',target={'stable_id':'root'},payload={'expected_generation':1,
            'expected_files':{**files,contract.SCENE_PATH:'4'*64}}),'GODOT_STALE_FILE')
        for operation in ('scene.undo','scene.redo'):
            request=self.request(operation,target={'stable_id':'root'},payload={'expected_generation':1,'steps':1})
            contract.validate_request(request,self.context)
            self.assert_reject(request,'GODOT_HISTORY_UNAVAILABLE',context=replace(self.context,can_undo=False,can_redo=False))
            self.assert_reject(self.request(operation,target={'stable_id':'root'},
                payload={'expected_generation':1,'steps':2}),'GODOT_INVALID_INTEGER')

    def test_shared_envelope_tamper_unknown_fields_and_inspect_bounds(self):
        request=self.request().as_dict()
        request['payload']['changes']['position']=[2,3,4]
        with self.assertRaises(ValidationError) as error:
            contract.validate_request(request,self.context)
        self.assertEqual(error.exception.code,'PAYLOAD_HASH_MISMATCH')
        self.assert_reject(self.request(payload={'expected_generation':1,'changes':{'position':[1,2,3]},'eval':'x'}),'GODOT_INVALID_SHAPE')
        for offset,limit in ((-1,1),(0,0),(0,65),(False,1)):
            self.assert_reject(self.request('scene.inspect',target={'stable_id':'root'},
                payload={'expected_generation':1,'offset':offset,'limit':limit}),'GODOT_INVALID_INTEGER')


if __name__ == '__main__':
    unittest.main()
