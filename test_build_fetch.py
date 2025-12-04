import sys
import os

# Auto-activate venv if not already active
if sys.prefix == sys.base_prefix:
    # Assuming 'venv' is in the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, "venv", "bin", "python")
    
    # If not found, check current working directory
    if not os.path.exists(venv_python):
         venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")

    if os.path.exists(venv_python):
        # Re-execute the script with the venv python
        os.execv(venv_python, [venv_python] + sys.argv)

import requests
import os
import base64
import json

# Configuration from deployment_dev.py
ORG_URL = "https://mpcoderepo.visualstudio.com"
PROJECT = "DigitalExperience"
BUILD_DEFINITION_ID = "3274"  # DEV pipeline

def get_azure_devops_headers():
    """Get Azure DevOps API headers with PAT token"""
    pat_token = os.environ.get('AZURE_DEVOPS_PAT')
    if not pat_token:
        print("❌ AZURE_DEVOPS_PAT environment variable not set")
        return None
    
    pat_encoded = base64.b64encode(f":{pat_token}".encode()).decode()
    return {
        "Authorization": f"Basic {pat_encoded}",
        "Content-Type": "application/json"
    }

def test_fetch_builds():
    headers = get_azure_devops_headers()
    if not headers:
        return

    # Fetch top 50 builds
    url = f"{ORG_URL}/{PROJECT}/_apis/build/builds?definitions={BUILD_DEFINITION_ID}&api-version=7.0&$top=50"
    
    print(f"🔍 Fetching builds from: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            builds = data.get('value', [])
            print(f"✅ Found {len(builds)} builds. Listing recent ones:")
            print("-" * 80)
            print(f"{'Build Number':<20} | {'Result':<15} | {'Status':<10} | {'Tags':<30} | {'Branch':<30}")
            print("-" * 120)
            
            for build in builds:
                build_num = build.get('buildNumber', 'N/A')
                result = build.get('result', 'N/A')
                status = build.get('status', 'N/A')
                tags = ", ".join(build.get('tags', []))
                branch = build.get('sourceBranch', 'N/A').replace('refs/heads/', '')
                
                print(f"{build_num:<20} | {result:<15} | {status:<10} | {tags:<30} | {branch:<30}")
            
            print("\n🔍 Searching all builds for 'Full Stack'...")
            found_fullstack = False
            for build in builds:
                build_json = json.dumps(build)
                if "Full Stack" in build_json or "fullstack" in build_json.lower():
                    print(f"\n✅ FOUND 'Full Stack' in build {build.get('buildNumber')}")
                    # Print context around the match if possible, or just the whole thing if it's not too huge
                    # For now, let's print the keys that contain the value
                    for key, value in build.items():
                        if "Full Stack" in str(value) or "fullstack" in str(value).lower():
                            print(f"   Key: {key}")
                            print(f"   Value: {value}")
                    found_fullstack = True
                    break
            
            if not found_fullstack:
                print("\n❌ 'Full Stack' NOT found in any of the fetched builds.")
                
        else:
            print(f"❌ Failed to fetch builds. Status: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_fetch_builds()
