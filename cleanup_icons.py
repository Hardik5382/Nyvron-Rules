import json
import os

with open("catalog/webapps.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Get all expected icon filenames from the catalog
expected_icons = set()
for app in data.get("apps", []):
    icon_url = app.get("iconUrl", "")
    if icon_url:
        expected_icons.add(icon_url.split("/")[-1])

# List all actual files in the icons folder
actual_icons = set(os.listdir("icons"))

# Find orphans
orphans = actual_icons - expected_icons

print(f"Expected icons in catalog: {len(expected_icons)}")
print(f"Total icons in folder: {len(actual_icons)}")
print(f"Orphaned icons to remove: {len(orphans)}")

# Delete orphans
removed_count = 0
for orphan in orphans:
    if orphan.endswith(".webp"):
        os.remove(os.path.join("icons", orphan))
        print(f"Removed: {orphan}")
        removed_count += 1

print(f"Successfully removed {removed_count} orphaned icons.")
