import os
import json
import base64
import requests

# 1. Pull credentials out of GitHub action runner environments
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME")
KAGGLE_KEY = os.environ.get("KAGGLE_KEY")

# Define target workspace slugs
KERNEL_SLUG = "muhammadasjad2008/content-factory-engine"

# 2. Read the script file you want to execute (notebook.py)
with open("summa.py", "r") as f:
    code_content = f.read()

# 3. Formulate the explicit payload structure required by Kaggle v1 REST endpoints
payload = {
    "id": 0,
    "slug": "content-factory-engine",
    "newTitle": "Content Factory Engine",
    "textCode": code_content,
    "language": "python",
    "kernelType": "notebook",
    "isPrivate": True,
    "enableGpu": True,
    "enableInternet": True,
    "datasetSources": [],
    "competitionSources": [],
    "kernelSources": []
}

# 4. Fire direct network POST block over authorization gateways
url = "https://kaggle.com"
auth = (KAGGLE_USERNAME, KAGGLE_KEY)

print(f"📡 Dispatching execution signal directly to {url}...")
response = requests.post(url, auth=auth, json=payload)

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Kaggle GPU Engine Active. Version: {data.get('versionNumber')}")
else:
    print(f"❌ Failed. HTTP Status: {response.status_code}")
    print(response.text)
