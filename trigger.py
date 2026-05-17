#!/usr/bin/env python3
# trigger.py - Trigger Kaggle execution via official Python API (GitHub Actions compatible)
import os, sys, time, json
from kaggle.api.kaggle_api_extended import KaggleApi

def setup_kaggle_auth(username: str, key: str) -> bool:
    """
    Set up Kaggle authentication for GitHub Actions environment.
    Creates ~/.kaggle/kaggle.json with proper format.
    """
    try:
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        
        kaggle_file = os.path.join(kaggle_dir, "kaggle.json")
        creds = {"username": username, "key": key}
        
        with open(kaggle_file, "w") as f:
            json.dump(creds, f)
        os.chmod(kaggle_file, 0o600)
        
        # Verify file is valid JSON
        with open(kaggle_file, "r") as f:
            json.load(f)
        
        print(f"✅ Kaggle auth file created: {kaggle_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to set up Kaggle auth: {e}")
        return False

def trigger_kaggle_execution(folder_path: str, kernel_id: str, max_wait_minutes: int = 0):
    """
    Push notebook config to Kaggle and optionally wait for completion.
    """
    print(f"🔐 Initializing Kaggle API client...")
    
    try:
        api = KaggleApi()
        api.authenticate()
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("💡 Ensure KAGGLE_USERNAME and KAGGLE_KEY are valid")
        return False
    
    try:
        print(f"📤 Pushing configuration from '{folder_path}'...")
        response = api.kernels_push(folder_path)
        
        print("✅ Push successful!")
        print(f"🔗 Remote URL: {response.get('url', 'N/A')}")
        print(f"📊 Initial status: {response.get('status', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ Push failed: {e}")
        # Print more debug info
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Load credentials from environment (set in GitHub Actions)
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    
    if not username or not key:
        print("❌ ERROR: KAGGLE_USERNAME or KAGGLE_KEY not set in environment")
        sys.exit(1)
    
    # Set up auth BEFORE initializing API client
    if not setup_kaggle_auth(username, key):
        sys.exit(1)
    
    # Configuration
    folder_path = os.environ.get("KAGGLE_PUSH_FOLDER", "./kaggle_deploy")
    kernel_id = os.environ.get("KAGGLE_KERNEL_ID", "muhammadasjad2008/content-factory-engine")
    wait_minutes = int(os.environ.get("KAGGLE_WAIT_MINUTES", "0"))
    sync_wait = int(os.environ.get("KAGGLE_SYNC_WAIT_SECONDS", "50"))
    
    # Wait for GitHub-Kaggle sync to register new pipeline_data.json
    print(f"⏳ Waiting {sync_wait}s for GitHub-Kaggle sync...")
    time.sleep(sync_wait)
    
    # Trigger execution
    success = trigger_kaggle_execution(folder_path, kernel_id, wait_minutes)
    
    sys.exit(0 if success else 1)
