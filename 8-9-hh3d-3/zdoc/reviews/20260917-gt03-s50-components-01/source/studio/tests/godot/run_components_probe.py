"""Native immutable staging + owned engine validation + readonly reopen.

No active selector, authenticated request or public save receipt is claimed.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

STUDIO = Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def frozen_run(output):
    sys.path.insert(0,str(STUDIO.parent))
    validate=load('component_validation',STUDIO/'godot-addon/validation_owner.py')
    storage=load('component_storage',STUDIO/'godot-addon/protected_bundle.py')
    from studio.host.core.safe_replace import ProtectedFileRoot
    factory=validate.factory
    if factory.bundle_codec is not storage.bundle_codec:
        raise ValueError('source-bound codec identity mismatch')
    temporary_base=Path(tempfile.gettempdir()).resolve()
    parent=Path(tempfile.mkdtemp(prefix='hh-gt03-components-',dir=temporary_base)).resolve()
    if parent.parent!=temporary_base or not parent.name.startswith('hh-gt03-components-'):
        raise ValueError('owned temporary root escaped expected parent')
    records=[]; store=None; validator=None; reopened=None; native_owner=None; extra_cleanup=None
    extra_is_api=False
    completed=False
    try:
        native_owner=ProtectedFileRoot.create(parent)
        store=storage.ProtectedBundleStore(native_owner)
        native_owner=None  # Exclusive lifecycle transferred only on success.
        root,identity=store.root,store.root_identity
        evidence=output/'validation';evidence.mkdir()
        validator=validate.ValidationOwner(evidence)
        first=factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
            scene_revision='sha256:'+hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
            engine_sha256=validate.executor.BINARY_SHA256)
        second=factory.bundle_codec.replace_script(first,
            b'extends Node3D\n@export var fixture_value: int = 11\n',
            expected_project_revision=first.project_revision,
            expected_script_sha256=first.script_sha256,expected_uid_sha256=first.uid_sha256)
        for index,bundle in enumerate((first,second)):
            command='component.'+str(index)
            factory.qualify(bundle)
            intent=store.prepare(command,bundle)
            if len(intent.names)!=12:
                raise ValueError('complete planned namespace missing')
            staged=store.stage(intent)
            actual=store.readback(staged)
            if actual.files!=bundle.files or actual.manifest_bytes!=bundle.manifest_bytes:
                raise ValueError('native staging bytes differ')
            receipt=validator.validate(command,actual)
            observation=validator.observation(receipt,actual)
            descriptor=store.descriptor(staged)
            row={'command_id':command,'project_revision':bundle.project_revision,
                'descriptor':descriptor,'validation_receipt':asdict(receipt),
                'observation':observation,'namespace_barrier_readback':True,
                'public_ack':False,'selected_state_verified':False,
                'semantic_scene_revision_verified':False}
            records.append(row);save(output/('component-'+str(index)+'.json'),row)
            print('HH_COMPONENT_VERIFIED '+json.dumps({'command_id':command,
                'project_revision':bundle.project_revision}),flush=True)
        if records[0]['observation']['script']['source_sha256']==records[1]['observation']['script']['source_sha256']:
            raise ValueError('script replacement not observed')
        store.close();store=None
        native_owner=ProtectedFileRoot.reopen_readonly(root,identity)
        reopened=storage.ProtectedBundleStore(native_owner)
        native_owner=None
        if not reopened.readonly:
            raise ValueError('reopen unexpectedly writable')
        for index,bundle in enumerate((first,second)):
            actual=reopened.read_descriptor(records[index]['descriptor'])
            if actual.manifest_bytes!=bundle.manifest_bytes or actual.files!=bundle.files:
                raise ValueError('readonly reopened bytes differ')
        rejected=False
        try:
            reopened.prepare('component.rearm',first)
        except storage.ProtectedBundleError:
            rejected=True
        if not rejected:
            raise ValueError('readonly mutation admitted')
        completed=True
    except BaseException as error:
        extra_cleanup=getattr(error,'cleanup_owner',None)
        if extra_cleanup is None:
            extra_cleanup=getattr(error,'cleanup_api',None)
            extra_is_api=extra_cleanup is not None
        raise
    finally:
        # Stop at a failed owner close; do not delete paths while custody is held.
        seen=set()
        for resource in (extra_cleanup,reopened,store,native_owner,validator):
            if resource is not None and id(resource) not in seen:
                seen.add(id(resource))
                if resource is extra_cleanup and extra_is_api:resource.close_owned()
                elif hasattr(resource,'close'):resource.close()
                else:resource.close_owned()
        # The checked absolute target is exactly our freshly allocated child.
        # There is no destructor fallback that could remove retained custody.
        if parent.resolve()!=parent or parent.parent!=temporary_base:
            raise ValueError('owned temporary path changed')
        shutil.rmtree(parent)
    save(output/'components.json',{'passed':completed,'components':len(records),
        'readonly_reopen_verified':completed,'temporary_removed':not parent.exists(),
        'public_ack':False,'selected_state_verified':False,'semantic_scene_revision_verified':False})
    return 0 if completed else 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True);args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.run_id):parser.error('run ID')
    output=args.output.resolve();output.relative_to(STUDIO.parent/'zdoc/reviews')
    output.mkdir(parents=True,exist_ok=False)
    freezer=load('components_freezer',STUDIO/'tests/godot/run_editor_probe.py')
    before=freezer.inputs();source=output/'source/studio'
    for name,digest in before.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest:raise ValueError('source changed during freeze')
    runner=load('components_owned',source/'build/bootstrap/run_fixture.py')
    closure=runner.source_closure_sha256(before)
    save(output/'source-closure.json',{'files':before,'source_closure_sha256':closure})
    code=('import importlib.util,sys;from pathlib import Path;'
          'p=Path("tests/godot/run_components_probe.py").resolve();'
          's=importlib.util.spec_from_file_location("frozen_components",p);'
          'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
          'sys.exit(m.frozen_run(Path(sys.argv[1])))')
    env=dict(os.environ)
    env['HH_STUDIO_LINUX_GODOT']=str(STUDIO/'.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host=runner.run_process([sys.executable,'-B','-c',code,str(output)],cwd=source,
        output=output,timeout=150,label='components',env=env)
    path=output/'components.json';result=json.loads(path.read_bytes()) if path.is_file() else None
    capture={'run_id':args.run_id,'source_closure_sha256':closure,'host':host,'result':result,
        'source_unchanged':before==freezer.inputs(),
        'snapshot_unchanged':all(sha(source/n)==h for n,h in before.items()),'public_ack':False}
    capture['passed']=bool(result and result['passed'] and result['temporary_removed']
        and host['exit_code']==host['wrapper_exit_code']==0 and host['tree_verified'] and not host['timed_out']
        and capture['source_unchanged'] and capture['snapshot_unchanged'])
    save(output/'capture.json',capture)
    print(json.dumps(capture))
    return 0 if capture['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
