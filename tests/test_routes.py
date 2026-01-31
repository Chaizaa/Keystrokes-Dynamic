"""
Test Blueprint Application - Route Verification
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app

# Create application instance
app = create_app("development")

print("=" * 60)
print("Blueprint Application - Route Verification")
print("=" * 60)

# List all registered routes
print("\n✅ Registered Blueprints:")
for blueprint_name, blueprint in app.blueprints.items():
    print(f"   - {blueprint_name}: {blueprint.import_name}")

print("\n✅ All Routes:")
routes = []
for rule in app.url_map.iter_rules():
    routes.append(
        {
            "endpoint": rule.endpoint,
            "methods": ",".join(rule.methods - {"HEAD", "OPTIONS"}),
            "path": str(rule),
        }
    )

# Group by blueprint
from collections import defaultdict

grouped_routes = defaultdict(list)
for route in routes:
    blueprint = route["endpoint"].split(".")[0] if "." in route["endpoint"] else "static"
    grouped_routes[blueprint].append(route)

for blueprint, routes in sorted(grouped_routes.items()):
    print(f"\n📁 {blueprint.upper()}:")
    for route in sorted(routes, key=lambda x: x["path"]):
        print(f"   {route['methods']:15} {route['path']}")

print("\n" + "=" * 60)
print(f"Total Routes: {len(app.url_map._rules)}")
print("=" * 60)

# Test configuration
print("\n📋 Configuration:")
print(f"   DEBUG: {app.config.get('DEBUG')}")
print(f"   SECRET_KEY: {'***' if app.config.get('SECRET_KEY') else 'NOT SET'}")
print(f"   DATABASE: {app.config.get('DATABASE_PATH')}")

print("\n✅ Blueprint Application Structure: OK")
