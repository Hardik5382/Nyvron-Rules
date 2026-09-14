import json
import os
import requests
from urllib.parse import urlparse
from PIL import Image
from io import BytesIO

with open("catalog/webapps.json", "r", encoding="utf-8") as f:
    data = json.load(f)

missing = 0
added = 0

for app in data.get("apps", []):
    icon_url = app.get("iconUrl", "")
    if not icon_url: continue
    
    filename = icon_url.split("/")[-1]
    local_path = os.path.join("icons", filename)
    
    if not os.path.exists(local_path):
        missing += 1
        domain = urlparse(app["url"]).netloc
        print(f"Fetching icon for {domain} -> {filename}...")
        
        try:
            res = requests.get(f"https://www.google.com/s2/favicons?domain={domain}&sz=256", timeout=10)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content))
                img.save(local_path, "WEBP")
                added += 1
            else:
                print(f"Failed to fetch {domain}: {res.status_code}")
        except Exception as e:
            print(f"Error for {domain}: {e}")

print(f"Missing: {missing}, Added: {added}")
