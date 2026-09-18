"""Exact read-only external catalog; the native Blender catalog stays private."""
import hashlib
import re
from studio.protocol.core import (Capability,Discovery,PROTOCOL_VERSION,SCHEMA_VERSION,
    Request,ValidationError,canonical_bytes,validate_for_dispatch)

TARGET='blender.owned-scene'
MAX_COMMANDS=32
MAX_READ_MS=2000
MAX_LEASE_MS=30000
MAX_WIRE=65536
READ='scene.inspect'
OPERATIONS=frozenset({READ,'control.lookup','control.stop'})
DESCRIPTOR={
    'schema':'HH-BLENDER-READ-CLIENT-1','protocol_version':PROTOCOL_VERSION,'schema_version':SCHEMA_VERSION,
    'registration':'exact-live-owned-BlenderUIHost-source-pid-generation',
    'request':'Request','response':'Response','target':{'stable_id':TARGET},
    'operations':{READ:{'read_scopes':['blender.scene.read'],'write_scopes':[],
        'payload':{},'read_lease_required':True,'expected_revision':'exact registered live revision'}},
    'controls':['discovery','read-lease','lookup-own-session','stop'],
    'limits':{'max_commands':MAX_COMMANDS,'max_pending':1,'max_read_ms':MAX_READ_MS,
        'max_lease_ms':MAX_LEASE_MS,'max_response_bytes':MAX_WIRE},
    'retention':'bounded owner lifetime; no eviction or restart replay',
    'scene_durable':False,'writer_grants':False,'public_ack':False,
}
CATALOG_DIGEST='sha256:'+hashlib.sha256(canonical_bytes(DESCRIPTOR)).hexdigest()

def discovery(project_id,*,source_sha256,readable=True):
    capabilities=(Capability(READ,('blender.scene.read',),(),{
        'max_pending':1,'max_read_ms':MAX_READ_MS,'max_response_bytes':MAX_WIRE}),) if readable else ()
    return Discovery(PROTOCOL_VERSION,SCHEMA_VERSION,CATALOG_DIGEST,'hh.blender.readonly',
        source_sha256,project_id,capabilities,dict(DESCRIPTOR['limits']))

def validate_request(body,*,project_id,source_sha256):
    request=Request.from_dict(body)
    validate_for_dispatch(request,discovery(project_id,source_sha256=source_sha256))
    if dict(request.target)!={'stable_id':TARGET}:raise ValidationError('BLENDER_TARGET_MISMATCH','fixed scene required')
    if dict(request.payload)!={}:raise ValidationError('BLENDER_INVALID_PAYLOAD','empty inspect payload required')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',request.expected_revision):
        raise ValidationError('BLENDER_INVALID_REVISION','native revision required')
    if request.fencing_epoch!=0:raise ValidationError('BLENDER_READ_LEASE_REQUIRED','no writer fence')
    return request
