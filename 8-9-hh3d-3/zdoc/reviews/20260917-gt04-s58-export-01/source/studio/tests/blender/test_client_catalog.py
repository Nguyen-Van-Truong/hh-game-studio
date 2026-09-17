"""Pure common-envelope/catalog checks; no Blender or native storage."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender import client_catalog as catalog
from studio.protocol.core import Request,Discovery,ValidationError,canonical_bytes,SCHEMA_VERSION

def request_body(**changes):
    values=dict(command_id='read.1',project_id='blender.test',operation='scene.inspect',lease_id='read.test',
        fencing_epoch=0,expected_revision='sha256:'+'a'*64,target={'stable_id':catalog.TARGET},payload={},
        payload_hash='sha256:'+hashlib.sha256(b'{}').hexdigest(),deadline_ms=999999999999)
    values.update(changes)
    return Request(**values).as_dict()

class CatalogTests(unittest.TestCase):
    def validate(self,body):return catalog.validate_request(body,project_id='blender.test',source_sha256='sha256:'+'b'*64)
    def test_common_request_roundtrip_and_exact_digest(self):
        value=self.validate(request_body());self.assertEqual(Request.from_json(canonical_bytes(value.as_dict())),value)
    def test_discovery_advertises_only_read_scope(self):
        value=catalog.discovery('blender.test',source_sha256='sha256:'+'b'*64)
        self.assertEqual(Discovery.from_dict(value.as_dict()),value)
        self.assertEqual([c.operation for c in value.capabilities],['scene.inspect'])
        self.assertEqual(value.capabilities[0].write_scopes,())
        self.assertEqual(value.schema_digest,catalog.CATALOG_DIGEST)
        self.assertEqual(catalog.discovery('blender.test',source_sha256='sha256:'+'b'*64,readable=False).capabilities,())
    def test_mutation_and_open_lane_explicit(self):
        for operation,code in [('mesh.create_box','UNSUPPORTED_OPERATION'),('open_lane.python','UNSUPPORTED_OPEN_LANE')]:
            with self.subTest(operation=operation),self.assertRaisesRegex(ValidationError,code):self.validate(request_body(operation=operation))
    def test_project_and_fixed_target_rejected(self):
        for changes,code in [({'project_id':'other'},'PROJECT_MISMATCH'),({'target':{'path':'x.blend'}},'BLENDER_TARGET_MISMATCH')]:
            with self.subTest(changes=changes),self.assertRaisesRegex(ValidationError,code):self.validate(request_body(**changes))
    def test_nonempty_payload_and_writer_fence_rejected(self):
        with self.assertRaisesRegex(ValidationError,'INVALID_PAYLOAD'):
            self.validate(request_body(payload={'a':1},payload_hash='sha256:'+hashlib.sha256(canonical_bytes({'a':1})).hexdigest()))
        with self.assertRaisesRegex(ValidationError,'READ_LEASE_REQUIRED'):self.validate(request_body(fencing_epoch=1))
    def test_bad_payload_hash_schema_or_digest(self):
        for field,value in [('payload_hash','sha256:'+'0'*64),('schema_version','unknown'),('digest','sha256:'+'0'*64)]:
            body=request_body();body[field]=value
            with self.subTest(field=field),self.assertRaises(ValidationError):self.validate(body)
    def test_descriptor_copy_does_not_change_digest(self):
        value=copy.deepcopy(catalog.DESCRIPTOR);value['writer_grants']=True
        self.assertNotEqual('sha256:'+hashlib.sha256(canonical_bytes(value)).hexdigest(),catalog.CATALOG_DIGEST)

if __name__=='__main__':unittest.main()
