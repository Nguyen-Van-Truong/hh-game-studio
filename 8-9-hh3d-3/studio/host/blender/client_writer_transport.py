"""Explicit writer transport; read-only transports keep their route allowlist."""
from .client_transport import BlenderClientTransport
from .client_writer_owner import BlenderWriterClientOwner
from .client_session import need


class BlenderWriterClientTransport(BlenderClientTransport):
    work_routes = {**BlenderClientTransport.work_routes, '/v1/preview': 'preview'}

    def __init__(self, owner):
        need(type(owner) is BlenderWriterClientOwner, 'BLENDER_EXACT_WRITER_OWNER_REQUIRED')
        with owner._attachment_lock:
            need(owner._queue_dispatcher is None and owner._transport is None,
                 'BLENDER_OWNER_ALREADY_ATTACHED')
            super().__init__(owner)
            owner._transport = self

    def close(self):
        # A failed drain retains the attachment for cleanup retry.
        super().close()
        with self.owner._attachment_lock:
            if self.owner._transport is self:
                self.owner._transport = None
