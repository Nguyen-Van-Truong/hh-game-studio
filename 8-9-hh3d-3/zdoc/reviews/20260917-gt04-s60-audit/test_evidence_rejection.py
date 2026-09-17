"""Read-only fault injection into audit reads; never rewrites captured evidence."""
from pathlib import Path
import importlib.util
import json
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
with patch.object(sys,'argv',[str(HERE/'verify_evidence.py'),'scene']):
    spec=importlib.util.spec_from_file_location('s60_negative_audit',HERE/'verify_evidence.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class RejectCorruptEvidence(unittest.TestCase):
    def setUp(self):
        audit.base.FILES.clear();audit.base.COPIES.clear();audit.base.CHECKS.clear()

    def reject(self,name,mutate):
        original=audit.base.raw
        touched=[]
        def altered(path,**options):
            data=original(path,**options)
            if path.name==name:
                value=json.loads(data);mutate(value);touched.append(str(path))
                return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
            return data
        with patch.object(audit.base,'raw',side_effect=altered),patch.object(audit,'raw',side_effect=altered):
            with self.assertRaises((ValueError,AssertionError,KeyError)): audit.verify()
        self.assertTrue(touched)

    def test_changed_snapshot_digest(self):
        self.reject('source-closure.json',lambda v:v['files'].__setitem__('host/blender/client_preview.py','0'*64))

    def test_empty_client_stderr_is_required_in_portable_inventory(self):
        self.assertTrue(audit.verify()['passed'])
        key=(audit.PACKAGE/'client-stderr.txt').relative_to(audit.ROOT).as_posix()
        self.assertEqual(audit.base.FILES[key],audit.sha(b''))

    def test_stale_closure(self):
        self.reject('capture.json',lambda v:v.__setitem__('source_closure_sha256','0'*64))

    def test_fabricated_zero_exit(self):
        self.reject('native-host.json',lambda v:v.__setitem__('exit_code',False))

    def test_missing_runtime_file(self):
        self.reject('launch.json',lambda v:v['source_files'].pop('host/blender/client_preview.py'))

    def test_retained_native_job(self):
        self.reject('close.json',lambda v:v['job'].__setitem__('handle_retained',True))

    def test_wrong_native_exit_pid(self):
        self.reject('process-exit.json',lambda v:v.__setitem__('pid',1))

    def test_foreign_bundle_profile(self):
        self.reject('publication.json',lambda v:v['manifest'].__setitem__('publication_profile','export.publish'))

    def test_forged_artifact_digest(self):
        self.reject('publication.json',lambda v:v['publication']['receipt']['artifacts']['scene.glb'].__setitem__('sha256','0'*64))

    def test_fabricated_file_preview_hash(self):
        # Keep the parsed client and its stdout marker aligned, so rejection
        # must also bind exact HTTP wires/native/publication, not just reports.
        original=audit.base.raw
        def change(value):
            for call in value['calls']:
                if call['route']=='/v1/preview' and call['request']['operation']=='scene.save':
                    response=json.loads(call['response_wire'])
                    response['requested_diff']['artifact_hashes']={'checkpoint.blend':'0'*64}
                    wire=json.dumps(response,sort_keys=True,separators=(',',':'))
                    call['response_wire']=wire
                    call['response_sha256']='sha256:'+audit.sha(wire.encode())
            return value
        def altered(path,**options):
            data=original(path,**options)
            if path.name=='client.json':
                return json.dumps(change(json.loads(data)),sort_keys=True,separators=(',',':')).encode()
            if path.name=='client-stdout.txt':
                lines=data.decode().splitlines(keepends=True)
                marker='GT04_WRITER_HTTP_COMPLETE '
                return ''.join(marker+json.dumps(change(json.loads(line[len(marker):])),sort_keys=True,separators=(',',':'))+'\n'
                    if line.startswith(marker) else line for line in lines).encode()
            return data
        with patch.object(audit.base,'raw',side_effect=altered),patch.object(audit,'raw',side_effect=altered):
            with self.assertRaises(ValueError): audit.verify()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RejectCorruptEvidence))
    report={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':len(result.skipped),'passed':result.wasSuccessful(),'native_handles_opened':0,'formal_acceptance':False}
    (HERE/'negative-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.wasSuccessful())
