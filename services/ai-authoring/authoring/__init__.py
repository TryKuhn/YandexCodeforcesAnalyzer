"""AI authoring service: AI-assisted creation and maintenance of Polygon problems.

The service owns its own tables (``authoring_*``) in the shared Postgres and
talks to Polygon only through the backend's ``/api/polygon`` routes.

Layout:

* ``settings`` / ``db`` / ``models`` / ``auth`` -- infrastructure;
* ``llm`` -- model registry, OpenRouter client, prompts, output protocols;
* ``polygon`` -- REST client for the backend's Polygon routes;
* ``sync`` -- problem snapshots, their diff and the materials text for models;
* ``pipeline`` -- runs (chat, generation, groups, build + repair) and the worker;
* ``api`` -- HTTP routes (``/api/ai/...``).
"""
