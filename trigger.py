import os
import json
import subprocess
import sys


#check if kaggle is installed if not install kaggle module
try:
    import kaggle
except ImportError:
    print("-> 'kaggle' module missing. Initiating force-install sequence...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle"])
    print("✅ 'kaggle' package successfully injected into environment.")

# 1. Fetch credentials safely from the execution environment
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME")
KAGGLE_KEY = os.environ.get("KAGGLE_KEY")

if not KAGGLE_USERNAME or not KAGGLE_KEY:
    print("❌ Error: Missing KAGGLE_USERNAME or KAGGLE_KEY environment variables!")
    exit(1)

# Trim out any invisible newline or whitespace gaps
KAGGLE_USERNAME = KAGGLE_USERNAME.strip()
KAGGLE_KEY = KAGGLE_KEY.strip()

print("[1/3] Generating secure native token file...")

# 2. Re-create the secure credentials folder structure required by Kaggle
home_dir = os.path.expanduser("~")
kaggle_folder = os.path.join(home_dir, ".kaggle")
os.makedirs(kaggle_folder, exist_ok=True)

token_path = os.path.join(kaggle_folder, "kaggle.json")
with open(token_path, "w") as f:
    json.dump({"username": KAGGLE_USERNAME, "key": KAGGLE_KEY}, f)

# Lock down file system permissions so the client accepts it safely
os.chmod(token_path, 0o600)
print("✅ Token file created and locked down.")

# 3. Create the kernel-metadata.json file safely within Python
print("[2/3] Writing kernel control properties file...")
meta_payload = {
    "id": "muhammadasjad2008/content-factory-engine",
    "title": "Content Factory Engine",
    "code_file": "content-factory-engine.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": "true",
    "enable_gpu": "true",
    "enable_internet": "true",
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": []
}

with open("kernel-metadata.json", "w") as f:
    json.dump(meta_payload, f, indent=2)
print("✅ kernel-metadata.json created.")

# 4. 🔥 FIX: CALL THE CORRECT UNIVERSAL KERNELS_PUSH METHOD
print("[3/3] Launching official Kaggle push trigger protocol natively...")

try:
    # Import the official client class engine directly from Python memory
    from kaggle.api.kaggle_api_extended import KaggleApi
    
    # Initialize and authenticate the API connection from the token file we created
    api = KaggleApi()
    api.authenticate()
    
    # Execute the push function directly through universal standard attributes
    print("📡 Uploading files and initiating Kaggle T4 GPU instance...")
    api.kernels_push(".")
    
    print("🚀 SUCCESS! The trigger payload cleared gates safely via native code lines.")
    print("🔗 Monitor progress here: https://kaggle.com")

except Exception as e:
    print(f"❌ Critical Error: Kaggle native API engine failed to complete the push: {e}")
    exit(1)
