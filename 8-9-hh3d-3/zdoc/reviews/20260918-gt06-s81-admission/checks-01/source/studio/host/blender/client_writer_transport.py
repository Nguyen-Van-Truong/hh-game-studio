"""Explicit writer transport; read-only transports keep their route allowlist."""
from .client_transport import BlenderClientTransport
from .client_writer_owner import BlenderWriterClientOwner
from .client_session import need


class BlenderWriterClientTransport(BlenderClientTransport):
    work_routes = {**BlenderClientTransport.work_routes, '/v1/preview': 'preview'}

    def __init__(self, owner):
        need(type(owner) is BlenderWriterClientOwner, 'BLENDER_EXACT_WRITER_OWNER_REQUIRED')
        super().__init__(owner)
