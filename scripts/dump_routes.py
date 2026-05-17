"""Dump route inventory from api_server.py for comparison."""
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
