"""Dump route inventory from api_server.py for comparison.

Verification utility used during the Agent Boundary Refactor (Task 5)
to capture pre-change and post-change HTTP route inventories. Outputs
sorted "METHOD PATH" lines for all registered FastAPI routes, excluding
only HEAD and OPTIONS. FastAPI documentation routes such as /docs, /redoc,
and /openapi.json are intentionally included so two inventories from the
same app factory can be diffed exactly.

Usage:
    uv run python scripts/dump_routes.py

Output example:
    DELETE /datasources/{datasource_id}
    GET /health
    POST /analyze
    ...

The output is designed to be diffed against a saved baseline to verify
that route grouping refactors did not change public endpoint paths or methods.
"""

import sys
import os
import logging

logging.disable(logging.CRITICAL)

os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("KIMI_API_KEY", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.api_server import create_api_server

app = create_api_server("./config.jsonc", start_services=False)

routes = []
for route in app.routes:
    if hasattr(route, "methods") and hasattr(route, "path"):
        for method in sorted(route.methods):
            if method not in ("HEAD", "OPTIONS"):
                routes.append(f"{method} {route.path}")

for r in sorted(routes):
    print(r)
