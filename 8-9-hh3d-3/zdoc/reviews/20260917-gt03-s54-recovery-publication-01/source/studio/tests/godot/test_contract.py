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
        self.context = contract.ValidationContext('project.fixture', 'sha256:'+'1'*64, 'sha256:'+'4'*64, 1,
            'lease.fixture', 7, 31_000, 1000,
            (contract.NodeState('root', None, 'Node3D', 'Fixture'),
             contract.NodeState('box', 'root', 'MeshInstance3D', 'Box', box_size=(1, 1, 1))),
            ((contract.SCENE_PATH, '2'*64), (contract.SCRIPT_PATH, '3'*64)), True, True)

    def request(self, operation='scene.node.update', *, target=None, payload=None, bind_project=True, **changes):
        if payload is None:
            payload = {'expected_generation': 1, 'changes': {'position': [1, 2, 3]}}
        if target is None:
            target = {'stable_id': 'box'}
        payload=copy.deepcopy(payload)
        if bind_project and operation != 'scene.inspect':
            payload.setdefault('expected_project_revision',self.context.project_revision)
            if operation == 'scene.preview' and type(payload.get('payload')) is dict:
                payload['payload'].setdefault('expected_project_revision',self.context.project_revision)
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
        self.assertNotIn('expected_project_revision',result.projection['payload'])
        self.assertEqual(result.preview['scene_revision'],self.context.revision)
        self.assertEqual(result.preview['project_revision'],self.context.project_revision)
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
        for operation in ('scene.preview','scene.save','scene.inspect','scene.undo','scene.redo','os.execute'):
            self.assert_reject(self.request('scene.preview',target={'stable_id':'root'},
                payload={'expected_generation':1,**inner,'operation':operation}),'GODOT_PREVIEW_OPERATION_FORBIDDEN')
        self.assert_reject(self.request('scene.preview',target={'stable_id':'root'},payload={'expected_generation':1,
            **inner,'payload':{'expected_generation':2,'changes':{'position':[2,3,4]}}}),'GODOT_STALE_GENERATION')

    def test_save_fixed_complete_file_set_and_history_revision_without_false_diff(self):
        files=dict(self.context.file_hashes)
        request=self.request('scene.save',target={'stable_id':'root'},payload={'expected_generation':1,'expected_files':files})
        result=contract.validate_request(request,self.context)
        self.assertEqual(result.preview['affected_files'],[contract.SCENE_PATH])
        self.assertEqual(result.preview['save_policy']['history'],'checkpoint_then_reload_boundary')
        self.assertFalse(result.preview['save_policy']['artist_project_save'])
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

    def test_engine_id_generation_and_case_alias_contract_match(self):
        for identifier in ('Command.upper', 'command/path', 'x'*65):
            self.assert_reject(self.request(command_id=identifier),'GODOT_INVALID_COMMAND_ID')
        for generation in (0, 2147483648):
            self.assert_reject(self.request(),'GODOT_INVALID_INTEGER',context=replace(self.context,generation=generation))
        payload=self.create_payload();payload['name']='bOX'
        self.assert_reject(self.request('scene.node.create',target={'stable_id':'root'},payload=payload),
                           'GODOT_DUPLICATE_SIBLING_NAME')
        nodes=self.context.nodes+(contract.NodeState('other','root','Node3D','Other'),)
        self.assert_reject(self.request(target={'stable_id':'other'},payload={'expected_generation':1,'changes':{'name':'boX'}}),
                           'GODOT_DUPLICATE_SIBLING_NAME',context=replace(self.context,nodes=nodes))
        nodes=self.context.nodes+(contract.NodeState('other','root','Node3D','bOX'),)
        self.assert_reject(self.request(),'GODOT_DUPLICATE_SIBLING_NAME',context=replace(self.context,nodes=nodes))

    def test_generated_vectors_are_shared_canonical_envelopes_and_nonfinite_stays_raw_wire(self):
        from contract_vectors import generate_vectors
        vectors=generate_vectors()
        self.assertEqual(canonical_bytes(vectors),canonical_bytes(generate_vectors()))
        self.assertEqual(vectors['snapshot_mode'],'SYNTHETIC_TEST_ONLY')
        self.assertEqual(vectors['project_revision_mode'],'SYNTHETIC_TEST_ONLY')
        self.assertFalse(vectors['acceptance'])
        self.assertFalse(vectors['runtime_authorized'])
        self.assertEqual({row['id'] for row in vectors['valid']},{'inspect','create','update','remove','undo','redo','preview'})
        for row in vectors['valid']:
            request=Request.from_json(row['wire_json'])
            self.assertEqual(request.as_dict(),row['request'])
            self.assertEqual(canonical_bytes(row['engine_projection']).decode(),row['engine_projection_json'])
            self.assertFalse(row['expect']['committed'])
            self.assertEqual(row['projection']['command_id'],request.command_id)
            self.assertNotIn('expected_project_revision',row['engine_projection']['payload'])
            if request.operation != 'scene.inspect':
                self.assertEqual(request.payload['expected_project_revision'],vectors['context']['project_revision'])
        bad={row['id']:row for row in vectors['rejected']}
        self.assertEqual(len(bad),14)
        self.assertIn(b'NaN',bytes.fromhex(''.join(bad['nan_wire']['wire_hex_chunks'])))
        self.assertTrue(all(row['expected_no_effect'] and row['engine_projection'] is None for row in bad.values()))
        policy=vectors['decoder_policy']
        self.assertFalse(policy['generic_coercion'])
        self.assertFalse(policy['variant_decode'])
        self.assertEqual({row['path'] for row in policy['integer_fields']['common']},
                         {'expected_generation','payload.expected_generation'})

    def test_native_snapshot_adapter_preserves_full_revision_without_hashing_editable_subset(self):
        from contract_vectors import generate_vectors, context_from_snapshot
        snapshot=generate_vectors()['native_observation']
        # An observed complete-state revision can change because of native
        # stored metadata, which is not a writable NodeState field.
        snapshot['revision']='sha256:'+'a'*64
        snapshot['state']['nodes'][0]['stored']={'visible':False,'native_transform':{'type':18,'value':[1,0,0]}}
        before=copy.deepcopy(snapshot)
        context=context_from_snapshot(snapshot,project_revision=self.context.project_revision)
        self.assertIsNone(context.nodes[0].parent_id)
        self.assertEqual(context.revision,snapshot['revision'])
        vectors=generate_vectors(snapshot,project_revision=self.context.project_revision)
        self.assertEqual(vectors['snapshot_mode'],'SUPPLIED_NATIVE_OBSERVATION')
        self.assertEqual(vectors['project_revision_mode'],'SUPPLIED_TRUSTED_PROJECT_REVISION')
        self.assertEqual(vectors['context']['project_revision'],self.context.project_revision)
        self.assertFalse(vectors['revision_recomputed'])
        self.assertEqual(vectors['native_observation'],before)
        self.assertEqual(snapshot,before)
        self.assertTrue(all(row['engine_projection']['expected_revision']==snapshot['revision'] for row in vectors['valid']))
        self.assertEqual({row['id'] for row in vectors['deferred']},{'undo','redo'})

    def test_native_snapshot_adapter_refuses_partial_foreign_owner_and_missing_state(self):
        from contract_vectors import generate_vectors, context_from_snapshot
        snapshot=generate_vectors()['native_observation']
        for change in ({'offset':1},{'total':3},{'held':True}):
            with self.assertRaises(ValueError):context_from_snapshot({**snapshot,**change},project_revision=self.context.project_revision)
        bad=copy.deepcopy(snapshot);bad['state']['nodes'][1]['owner_id']='foreign'
        with self.assertRaisesRegex(ValueError,'VECTOR_OWNER_SCOPE'):context_from_snapshot(bad,project_revision=self.context.project_revision)
        bad=copy.deepcopy(snapshot);del bad['state']['nodes'][0]['stored']
        with self.assertRaises(ValueError):context_from_snapshot(bad,project_revision=self.context.project_revision)
        # An actual root-only observation cannot invent a removable child or history.
        root_only=copy.deepcopy(snapshot);root_only['state']['nodes']=root_only['state']['nodes'][:1];root_only['total']=1
        vectors=generate_vectors(root_only,project_revision=self.context.project_revision)
        self.assertEqual({row['id'] for row in vectors['deferred']},{'remove','undo','redo'})
        self.assertEqual({row['id'] for row in vectors['valid']},{'inspect','create','update','preview'})

    def project_bound_requests(self):
        """One otherwise-valid command for every new project-bound operation."""
        root={'stable_id':'root'}
        generation={'expected_generation':self.context.generation}
        return [
            self.request('scene.node.create',target=root,payload=self.create_payload()),
            self.request(),
            self.request('scene.node.remove',payload=generation),
            self.request('scene.undo',target=root,payload={**generation,'steps':1}),
            self.request('scene.redo',target=root,payload={**generation,'steps':1}),
            self.request('scene.save',target=root,payload={**generation,'expected_files':dict(self.context.file_hashes)}),
            self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},
                         payload={**generation,'expected_sha256':dict(self.context.file_hashes)[contract.SCRIPT_PATH],
                                  'text':'extends Node3D\n'}),
            self.request('scene.preview',target=root,payload={**generation,'operation':'scene.node.update',
                         'target':{'stable_id':'box'},'payload':{**generation,'changes':{'position':[1,2,3]}}}),
        ]

    def test_every_mutation_history_save_script_and_preview_requires_project_cas(self):
        for request in self.project_bound_requests():
            with self.subTest(operation=request.operation):
                result=contract.validate_request(request,self.context)
                self.assertNotIn('expected_project_revision',result.projection['payload'])
                self.assertEqual(result.preview['project_revision'],self.context.project_revision)
                missing=dict(request.payload);del missing['expected_project_revision']
                self.assert_reject(self.request(request.operation,target=request.target,payload=missing,
                                               bind_project=False),'GODOT_INVALID_SHAPE')
                wrong={**request.payload,'expected_project_revision':'sha256:'+'5'*64}
                self.assert_reject(self.request(request.operation,target=request.target,payload=wrong,
                                               bind_project=False),'GODOT_STALE_PROJECT_REVISION')
                for value in (None,True,1,'','sha256:'+'G'*64):
                    invalid={**request.payload,'expected_project_revision':value}
                    self.assert_reject(self.request(request.operation,target=request.target,payload=invalid,
                                                   bind_project=False),'GODOT_INVALID_PROJECT_REVISION')

    def test_trusted_context_requires_project_revision_even_for_inspection(self):
        request=self.request('scene.inspect',target={'stable_id':'root'},
                             payload={'expected_generation':1,'offset':0,'limit':64})
        for invalid in (None,True,1,'','sha256:'+'a'*63):
            self.assert_reject(request,'GODOT_INVALID_PROJECT_REVISION',
                               context=replace(self.context,project_revision=invalid))
        observed=contract.validate_request(request,self.context)
        self.assertEqual(observed.preview['scene_revision'],self.context.revision)
        self.assertEqual(observed.preview['project_revision'],self.context.project_revision)
        self.assertNotIn('expected_project_revision',observed.projection['payload'])
        changed=replace(self.context,project_revision='sha256:'+'5'*64)
        self.assertEqual(contract.validate_request(request,changed).preview['project_revision'],changed.project_revision)

    def test_preview_outer_and_nested_project_preconditions_must_both_match(self):
        original=self.project_bound_requests()[-1]
        valid=contract.validate_request(original,self.context)
        self.assertNotIn('expected_project_revision',valid.projection['payload']['payload'])
        self.assertNotIn('expected_project_revision',valid.projection['preview_command']['payload'])
        for layer in ('outer','inner'):
            for value,code in ((None,'GODOT_INVALID_SHAPE'),('sha256:'+'5'*64,'GODOT_STALE_PROJECT_REVISION')):
                with self.subTest(layer=layer,value=value):
                    payload=copy.deepcopy(dict(original.payload))
                    affected=payload if layer=='outer' else payload['payload']
                    if value is None:
                        del affected['expected_project_revision']
                    else:
                        affected['expected_project_revision']=value
                    request=self.request('scene.preview',target=original.target,payload=payload,bind_project=False)
                    self.assert_reject(request,code)
        # Two mutually equal stale values cannot authorize a preview either.
        payload=copy.deepcopy(dict(original.payload))
        payload['expected_project_revision']=payload['payload']['expected_project_revision']='sha256:'+'5'*64
        self.assert_reject(self.request('scene.preview',target=original.target,payload=payload,bind_project=False),
                           'GODOT_STALE_PROJECT_REVISION')

    def test_script_only_bundle_change_invalidates_stale_scene_mutation_and_save(self):
        spec=importlib.util.spec_from_file_location('gt03_contract_test_bundle',STUDIO/'godot-addon/bundle.py')
        bundle=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bundle;spec.loader.exec_module(bundle)
        original=bundle.create_bundle(b'[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n',
            b'extends Node3D\n',scene_revision=self.context.revision,engine_sha256='a'*64)
        changed=bundle.replace_script(original,b'extends Node3D\n# changed script only\n',
            expected_project_revision=original.project_revision,expected_script_sha256=original.script_sha256)
        self.assertEqual(changed.scene_revision,original.scene_revision)
        self.assertEqual(changed.scene_bytes,original.scene_bytes)
        self.assertNotEqual(changed.project_revision,original.project_revision)
        old_context=replace(self.context,project_revision=original.project_revision,
            file_hashes=((contract.SCENE_PATH,hashlib.sha256(original.scene_bytes).hexdigest()),
                         (contract.SCRIPT_PATH,original.script_sha256)))
        new_context=replace(old_context,project_revision=changed.project_revision,
            file_hashes=((contract.SCENE_PATH,hashlib.sha256(changed.scene_bytes).hexdigest()),
                         (contract.SCRIPT_PATH,changed.script_sha256)))
        for operation,payload,target in (
            ('scene.node.update',{'expected_generation':1,'changes':{'position':[1,2,3]}},{'stable_id':'box'}),
            ('scene.save',{'expected_generation':1,'expected_files':dict(new_context.file_hashes)},{'stable_id':'root'}),
        ):
            # For save, current raw hashes deliberately cannot mask a stale
            # complete-project precondition; the semantic scene hash is equal.
            stale=self.request(operation,target=target,payload={**payload,'expected_project_revision':original.project_revision})
            self.assert_reject(stale,'GODOT_STALE_PROJECT_REVISION',context=new_context)
            fresh=self.request(operation,target=target,payload={**payload,'expected_project_revision':changed.project_revision})
            self.assertFalse(contract.validate_request(fresh,new_context).preview['changes_applied'])
        stale_script=self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},payload={
            'expected_generation':1,'expected_project_revision':original.project_revision,
            'expected_sha256':changed.script_sha256,'text':'extends Node3D\n'})
        self.assert_reject(stale_script,'GODOT_STALE_PROJECT_REVISION',context=new_context)

    def test_project_cas_is_digest_bound_but_validator_is_not_retry_receipt_authority(self):
        request=self.request()
        first=contract.validate_request(request,self.context)
        repeated=contract.validate_request(request,self.context)
        self.assertEqual(first,repeated)
        changed=replace(self.context,project_revision='sha256:'+'5'*64)
        # A real host must look up the original terminal receipt BEFORE this
        # admission validator; it must not rerun an already admitted effect.
        self.assert_reject(request,'GODOT_STALE_PROJECT_REVISION',context=changed)
        refreshed=self.request(payload={**request.payload,'expected_project_revision':changed.project_revision})
        self.assertEqual(request.command_id,refreshed.command_id)
        self.assertNotEqual(request.digest,refreshed.digest)
        self.assertFalse(contract.validate_request(refreshed,changed).preview['runtime_authorized'])

    def test_actual_vectors_require_explicit_project_revision(self):
        from contract_vectors import generate_vectors,context_from_snapshot
        snapshot=generate_vectors()['native_observation']
        with self.assertRaisesRegex(ValueError,'VECTOR_PROJECT_REVISION_REQUIRED'):
            generate_vectors(snapshot)
        with self.assertRaises(TypeError):
            context_from_snapshot(snapshot)
        for invalid in (None,True,1,'','sha256:'+'a'*63):
            with self.assertRaisesRegex(ValueError,'VECTOR_PROJECT_REVISION_REQUIRED'):
                generate_vectors(snapshot,project_revision=invalid)
        vectors=generate_vectors(snapshot,project_revision=self.context.project_revision)
        self.assertEqual(vectors['context']['project_revision'],self.context.project_revision)
        self.assertEqual(vectors['project_revision_mode'],'SUPPLIED_TRUSTED_PROJECT_REVISION')

    def test_catalog_revision_contract_and_digest_change_without_runtime_enablement(self):
        catalog=contract.catalog()
        self.assertEqual(catalog['catalog_version'],'gt03-godot-4')
        self.assertEqual(set(catalog['revision_contract']['inspect_result']),{'scene_revision','project_revision'})
        self.assertEqual(contract.CATALOG_DIGEST,'sha256:'+hashlib.sha256(canonical_bytes(catalog)).hexdigest())
        for operation,row in catalog['operations'].items():
            self.assertEqual('expected_project_revision' in row['required'],operation!='scene.inspect')
            self.assertFalse(row['implemented'])
            self.assertFalse(row['runtime_enabled'])
        discovery=contract.discovery('project.fixture').as_dict()
        self.assertEqual(discovery['schema_digest'],contract.CATALOG_DIGEST)
        self.assertEqual(discovery['build'],'2.0')
        self.assertEqual(discovery['capabilities'],[])

    def script_command(self, before, after):
        digest=hashlib.sha256(before).hexdigest()
        context=replace(self.context,file_hashes=((contract.SCENE_PATH,'2'*64),(contract.SCRIPT_PATH,digest)))
        request=self.request('script_text.replace',target={'path':contract.SCRIPT_PATH},payload={
            'expected_generation':1,'expected_sha256':digest,'text':after})
        return contract.validate_request(request,context)

    def test_script_preview_contains_real_changed_lines_and_exact_full_hashes(self):
        before=b'extends Node3D\n@export var fixture_value: int = 7\n'
        after='extends Node3D\n@export var fixture_value: int = 9\n'
        command=self.script_command(before,after)
        result=contract.script_preview(before,command)
        row=result['diff'][0]; text=''.join(row['unified_diff'])
        self.assertIn('-@export var fixture_value: int = 7\n',text)
        self.assertIn('+@export var fixture_value: int = 9\n',text)
        self.assertFalse(row['diff_truncated'])
        self.assertEqual(row['after_sha256'],hashlib.sha256(after.encode()).hexdigest())
        self.assertEqual(result['request_digest'],command.request_digest)
        self.assertFalse(result['changes_applied']); self.assertFalse(result['runtime_authorized'])
        with self.assertRaisesRegex(ValidationError,'GODOT_STALE_SCRIPT'):
            contract.script_preview(before+b'# manual edit\n',command)

    def test_script_preview_truncation_keeps_full_hash_and_bounds_input_work(self):
        before=('old\n'*300).encode();after='new\n'*300
        result=contract.script_preview(before,self.script_command(before,after))['diff'][0]
        self.assertTrue(result['diff_truncated'])
        self.assertLessEqual(len(result['unified_diff']),256)
        self.assertLessEqual(result['display_utf8_bytes'],32768)
        self.assertEqual(result['after_sha256'],hashlib.sha256(after.encode()).hexdigest())
        with self.assertRaisesRegex(ValidationError,'GODOT_PREVIEW_LINE_LIMIT'):
            contract.script_preview(before,self.script_command(before,'new\n'*513))


if __name__ == '__main__':
    unittest.main()
