"""Bridge to the AI authoring service (``services/ai-authoring``).

* ``proxy`` -- ``/api/ai/*`` is forwarded to the service as is;
* ``client`` -- server-side calls into the service (the archive importer).
"""
from api.user.ai.proxy import ai_proxy_router

__all__ = ["ai_proxy_router"]
