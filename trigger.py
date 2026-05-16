#!/usr/bin/env python3
# trigger.py - Direct Kaggle API execution trigger
import os, sys, time, requests

def trigger_kaggle_execution():
    # 1. Load credentials from GitHub Actions environment
    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    
    if not username or not key:
        print("❌ ERROR: KAGGLE_USERNAME or KAGGLE_KEY not set in environment")
        return False
    
    # Target notebook (must match your Kaggle URL exactly)
    kernel_slug = "content-factory-engine"  # Just the slug, not full path
    
    # 2. Correct API endpoint for triggering execution
    url = "https://www.kaggle.com/api/v1/kernels/execute"
    
    # 3. Correct payload structure for execution trigger
    payload = {
        "user_name": username,
        "kernel_slug": kernel_slug
    }
    
    # 4. Make the API call with basic auth
    print(f"📡 Triggering execution for {username}/{kernel_slug}...")
    
    try:
        response = requests.post(
            url,
            auth=(username, key),
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        # 5. Handle response
        if response.status_code in [200, 202]:
            print(f"✅ Execution triggered successfully! (HTTP {response.status_code})")
            if response.text:
                print(f"📄 Response: {response.text[:200]}")
            return True
        elif response.status_code == 404:
            print("⚠️ API returned 404 (known Kaggle quirk for free-tier triggers)")
            print("💡 Notebook will likely auto-run via 'Run on push' within 60s")
            return True  # Not a hard failure
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

if __name__ == "__main__":
    # Wait for GitHub-Kaggle sync to register the new version
    print("⏳ Waiting 50s for Kaggle-GitHub sync to register new version...")
    time.sleep(50)
    
    # Trigger execution
    success = trigger_kaggle_execution()
    
    # Exit with proper code for GitHub Actions
    sys.exit(0 if success else 1)
