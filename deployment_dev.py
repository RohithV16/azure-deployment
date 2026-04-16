#!/usr/bin/env python3
"""
DEV Pipeline Deployment Automation Script
Automates deployment workflow for DEV pipeline (dev branch)
"""

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
import json
import os
import sys
import base64
import time
import argparse
import threading
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Azure DevOps configuration
ORG_URL = "https://mpcoderepo.visualstudio.com"
PROJECT = "DigitalExperience"
BUILD_DEFINITION_ID = "3274"  # DEV pipeline
BRANCH = "dev"  # DEV pipeline uses dev branch

# Repository name for PR detection and tagging
REPOSITORY_NAME = "aemaacs-life"

# Teams webhook URL
TEAMS_WEBHOOK_URL = "https://aegisdentsunetwork.webhook.office.com/webhookb2/c448e610-8c38-45ad-a939-db5a4ece46d5@6e8992ec-76d5-4ea5-8eae-b0c5e558749a/IncomingWebhook/0dc0e4fca542427fb3d6a02281a88574/d881b4fa-b65f-4e61-bb1a-b48354c99b1c/V2WHmoL-a3Tw0P84hKNYK4FI_U6TSWBShEDdqyLnsn9p41"

POWER_AUTOMATE_WEBHOOK_URL = "https://default6e8992ec76d54ea58eaeb0c5e55874.9a.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/1c9b143d398747a6892388f31a230f87/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=tzPM2LVcleQ3UCpAWZG46rQ7-3W5qtXOgrTjAHHYIcw"

# DEV pipeline configuration - no need for mapping functions

# ============================================================================
# AZURE DEVOPS FUNCTIONS
# ============================================================================

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

def get_repository_id(repo_name=None):
    """Get the repository ID for the DigitalExperience project"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repos_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories?api-version=7.0"
    
    try:
        response = requests.get(repos_url, headers=headers)
        if response.status_code in [200, 202]:
            repos_data = response.json()
            if repos_data.get('value'):
                # If repo_name is specified, find that repo, otherwise return first one
                if repo_name:
                    for repo in repos_data['value']:
                        if repo.get('name') == repo_name:
                            repo_id = repo.get('id')
                            print(f"✅ Found repository: {repo_name} (ID: {repo_id})")
                            return repo_id
                    print(f"❌ Repository '{repo_name}' not found")
                    return None
                else:
                    repo_id = repos_data['value'][0].get('id')
                    repo_name_found = repos_data['value'][0].get('name')
                    print(f"✅ Found repository: {repo_name_found} (ID: {repo_id})")
                    return repo_id
        else:
            print(f"❌ Failed to get repositories: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting repository ID: {e}")
        return None

def get_last_build_info(definition_id=None, include_in_progress=False):
    """Get the last successful build information from Azure DevOps"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Use provided definition_id or default
    def_id = definition_id or BUILD_DEFINITION_ID
    builds_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds?definitions={def_id}&api-version=7.0&$top=200"
    
    try:
        response = requests.get(builds_url, headers=headers)
        if response.status_code in [200, 202]:
            builds = response.json()
            if builds.get('count', 0) > 0:
                valid_builds = []
                in_progress_builds = []
                
                for build in builds['value']:
                    build_result = build.get('result')
                    build_status = build.get('status')
                    build_number = build.get('buildNumber', '')
                    
                    # Collect successful builds - ONLY fullstack
                    if build_result in ['succeeded', 'partiallySucceeded']:
                        # Check templateParameters for deploymentType: Full Stack
                        template_params = build.get('templateParameters', {})
                        deployment_type = template_params.get('deploymentType', '')
                        
                        if deployment_type == 'Full Stack':
                            valid_builds.append(build)
                        else:
                            # Debug: print skipped builds
                            # print(f"   Skipping non-fullstack build: {build_number} (Type: {deployment_type})")
                            pass
                    
                    # Collect in-progress builds (if requested)
                    if include_in_progress and build_status in ['inProgress', 'notStarted']:
                        in_progress_builds.append(build)
                
                # If include_in_progress and we have in-progress builds, use the most recent one
                if include_in_progress and in_progress_builds:
                    latest_in_progress = in_progress_builds[0]
                    print(f"✅ Found in-progress build: {latest_in_progress.get('buildNumber')} (Status: {latest_in_progress.get('status')})")
                    return {
                        'build_number': latest_in_progress.get('buildNumber'),
                        'build_id': latest_in_progress.get('id'),
                        'source_version': latest_in_progress.get('sourceVersion'),
                        'start_time': latest_in_progress.get('startTime'),
                        'result': latest_in_progress.get('result'),
                        'status': latest_in_progress.get('status')
                    }
                
                # Otherwise, use the most recent successful build
                if valid_builds:
                    latest_valid_build = valid_builds[0]
                    print(f"✅ Found last successful build: {latest_valid_build.get('buildNumber')} (Result: {latest_valid_build.get('result')})")
                    
                    return {
                        'build_number': latest_valid_build.get('buildNumber'),
                        'build_id': latest_valid_build.get('id'),
                        'source_version': latest_valid_build.get('sourceVersion'),
                        'start_time': latest_valid_build.get('startTime'),
                        'result': latest_valid_build.get('result'),
                        'status': latest_valid_build.get('status')
                    }
                else:
                    print("⚠️  No successful builds found. All recent builds may be cancelled or failed.")
                    return None
            else:
                print("⚠️  No builds found for this definition.")
                return None
    except Exception as e:
        print(f"✗ Error getting build info: {e}")
    
    return None

def get_build_status_dynamic(build_id):
    """Get dynamic build status from Azure DevOps API"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    build_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds/{build_id}?api-version=7.0"
    
    try:
        response = requests.get(build_url, headers=headers)
        if response.status_code in [200, 202]:
            build_data = response.json()
            return {
                'source_version': build_data.get('sourceVersion', 'latest'),
                'start_time': build_data.get('startTime'),
                'result': build_data.get('result'),
                'status': build_data.get('status'),
                'build_number': build_data.get('buildNumber'),
                'build_id': build_data.get('id')
            }
        else:
            print(f"❌ Failed to get dynamic build info: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting dynamic build info: {e}")
        return None

def get_build_status(build_id):
    """Get current build status from Azure DevOps"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    build_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds/{build_id}?api-version=7.0"
    
    try:
        print(f"🔍 Checking build status for ID: {build_id}")
        response = requests.get(build_url, headers=headers)
        
        if response.status_code in [200, 202]:
            build_data = response.json()
            # Extract deployment type from template parameters
            template_params = build_data.get('templateParameters', {})
            deployment_type = template_params.get('deploymentType', '')
            
            status_info = {
                'status': build_data.get('status'),
                'result': build_data.get('result'),
                'build_number': build_data.get('buildNumber'),
                'finish_time': build_data.get('finishTime'),
                'start_time': build_data.get('startTime'),
                'deployment_type': deployment_type
            }
            print(f"✅ Build status retrieved: {status_info['status']} - {status_info['result']}")
            return status_info
        else:
            print(f"❌ Failed to get build status: {response.status_code}")
            # print(f"Response: {response.text}") # Reduce noise
            return None
    except Exception as e:
        print(f"❌ Error getting build status: {e}")
        return None

def get_build_timeline(build_id):
    """Get the timeline for a specific build to check stage status"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    url = f"{ORG_URL}/{PROJECT}/_apis/build/builds/{build_id}/timeline?api-version=7.0"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            print(f"❌ Failed to fetch timeline: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error fetching timeline: {e}")
        return None

def is_stage_active_or_completed(timeline, stage_name):
    """Check if a specific stage is active (in progress) or completed"""
    if not timeline or 'records' not in timeline:
        return False
    
    for record in timeline['records']:
        if record.get('type') == 'Stage' and record.get('name') == stage_name:
            state = record.get('state')
            # User wants to switch to Phase 2 when stage is "approved and in progress"
            # So we check if it's inProgress or already completed
            if state in ['inProgress', 'completed']:
                return True
    
    return False

def trigger_new_build(definition_id=None, branch=None, tag=None):
    """Trigger a new build for specified definition and branch or tag"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Use provided definition_id or default
    def_id = definition_id or BUILD_DEFINITION_ID
    
    # Determine source reference (tag takes priority for STAGE, otherwise use branch)
    if tag:
        # Use tag reference format: refs/tags/tag-name
        source_ref = tag if tag.startswith("refs/tags/") else f"refs/tags/{tag}"
        source_display = tag.replace("refs/tags/", "")
        source_type = "tag"
    else:
        # Get branch - use provided branch or default to DEV branch
        if not branch:
            branch = BRANCH  # Default to "dev" for DEV pipeline
        
        # Ensure branch format is correct
        if not branch.startswith("refs/heads/"):
            source_ref = f"refs/heads/{branch}"
        else:
            source_ref = branch
        source_display = branch.replace("refs/heads/", "")
        source_type = "branch"
    
    build_payload = {
        "definition": {
            "id": int(def_id)
        },
        "sourceBranch": source_ref
    }
    
    trigger_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds?api-version=7.0"
    
    try:
        pipeline_name = "DEV" if def_id == "3274" else "STAGE" if def_id == "3308" else f"Definition {def_id}"
        print(f"🚀 Triggering new build for {pipeline_name} pipeline ({source_type}: {source_display})...")
        response = requests.post(trigger_url, headers=headers, json=build_payload)
        
        if response.status_code in [200, 201]:
            build_data = response.json()
            build_id = build_data.get('id')
            build_number = build_data.get('buildNumber')
            
            print(f"✅ New build triggered successfully!")
            print(f"   Build ID: {build_id}")
            print(f"   Build Number: {build_number}")
            
            return {
                'build_id': build_id,
                'build_number': build_number,
                'status': 'triggered'
            }
        else:
            print(f"❌ Failed to trigger build: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error triggering build: {e}")
        return None

def get_latest_tag(repo_name=REPOSITORY_NAME):
    """Get the latest tag from the repository"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    tags_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=tags&api-version=7.0"
    
    try:
        response = requests.get(tags_url, headers=headers)
        if response.status_code in [200, 202]:
            refs_data = response.json()
            tags = refs_data.get('value', [])
            
            if not tags:
                print("ℹ️  No tags found in repository - will start with v1.0.0")
                return None
            
            # Extract tag names and sort them
            tag_names = []
            for tag in tags:
                tag_ref = tag.get('name', '')
                if tag_ref.startswith('refs/tags/'):
                    tag_name = tag_ref.replace('refs/tags/', '')
                    tag_names.append(tag_name)
            
            if not tag_names:
                print("ℹ️  No valid tags found - will start with v1.0.0")
                return None
            
            # Sort tags by version number (assuming semantic versioning)
            def version_key(tag):
                try:
                    # Remove 'v' prefix if present
                    version = tag.lstrip('vV')
                    parts = version.split('.')
                    # Convert to tuple for proper sorting
                    return tuple(int(p) for p in parts)
                except:
                    return (0, 0, 0)
            
            sorted_tags = sorted(tag_names, key=version_key, reverse=True)
            latest_tag = sorted_tags[0]
            print(f"✅ Found latest tag: {latest_tag}")
            return latest_tag
        else:
            print(f"❌ Failed to get tags: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting tags: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_commit_from_tag(tag_name, repo_name=REPOSITORY_NAME):
    """Get the commit hash from a tag (handles both annotated and lightweight tags)"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Get tag ref to find the commit
    tag_ref = f"refs/tags/{tag_name}"
    refs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?filter={tag_ref}&api-version=7.0"
    
    try:
        response = requests.get(refs_url, headers=headers)
        if response.status_code in [200, 202]:
            refs_data = response.json()
            refs = refs_data.get('value', [])
            
            if refs:
                # Get the object ID from the tag ref
                # This could be either:
                # 1. The commit object ID directly (lightweight tag)
                # 2. The tag object ID (annotated tag) which points to the commit
                object_id = refs[0].get('objectId')
                
                # First, try to get the annotated tag object (if it's an annotated tag)
                annotated_tags_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/annotatedtags/{object_id}?api-version=7.0"
                annotated_response = requests.get(annotated_tags_url, headers=headers)
                
                if annotated_response.status_code == 200:
                    # This is an annotated tag - extract the commit from taggedObject
                    annotated_data = annotated_response.json()
                    tagged_object_id = annotated_data.get('taggedObject', {}).get('objectId')
                    if tagged_object_id:
                        # Verify it's a commit by trying to fetch it
                        commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{tagged_object_id}?api-version=7.0"
                        commit_response = requests.get(commit_url, headers=headers)
                        if commit_response.status_code == 200:
                            print(f"✅ Found commit from annotated tag {tag_name}: {tagged_object_id[:8]}")
                            return tagged_object_id
                
                # If not an annotated tag or API call failed, try to verify if object_id is a commit directly
                commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{object_id}?api-version=7.0"
                commit_response = requests.get(commit_url, headers=headers)
                
                if commit_response.status_code == 200:
                    # This is a lightweight tag pointing directly to a commit
                    print(f"✅ Found commit from lightweight tag {tag_name}: {object_id[:8]}")
                    return object_id
                
                # If object_id is neither an annotated tag nor a commit, we can't determine the commit
                print(f"⚠️  Tag {tag_name} object ID is neither an annotated tag nor a commit, using build's commit as fallback")
                return None
            else:
                print(f"⚠️  Tag {tag_name} not found")
                return None
        else:
            print(f"⚠️  Failed to get tag ref: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️  Error getting commit from tag: {e}")
        import traceback
        traceback.print_exc()
        return None

def increment_tag_version(tag_name):
    """Increment tag version - MUST return vX.Y.Z format (strict semantic versioning)"""
    if not tag_name:
        return "v1.0.0"
    
    # Remove 'v' or 'V' prefix if present
    version = tag_name.lstrip('vV')
    
    try:
        parts = version.split('.')
        
        # Ensure we always have 3 parts (X.Y.Z format)
        if len(parts) >= 3:
            # Has all 3 parts: v1.0.0 -> v1.0.1
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            patch += 1
            new_version = f"v{major}.{minor}.{patch}"
        elif len(parts) == 2:
            # Has 2 parts: v1.0 -> v1.1.0 (add patch version)
            major, minor = int(parts[0]), int(parts[1])
            minor += 1
            new_version = f"v{major}.{minor}.0"
        elif len(parts) == 1:
            # Has 1 part: v1 -> v1.0.1 (add minor and patch)
            major = int(parts[0])
            new_version = f"v{major}.0.1"
        else:
            # Invalid format, default to v1.0.0
            new_version = "v1.0.0"
        
        # Validate format is vX.Y.Z
        if not new_version.startswith('v'):
            new_version = f"v{new_version}"
        
        # Double-check format
        version_parts = new_version.lstrip('v').split('.')
        if len(version_parts) != 3:
            # Force to 3 parts
            major = int(version_parts[0]) if version_parts else 1
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0
            new_version = f"v{major}.{minor}.{patch}"
        
        print(f"✅ Incremented tag: {tag_name} -> {new_version}")
        return new_version
    except Exception as e:
        print(f"⚠️  Error parsing tag version, using default: {e}")
        return "v1.0.0"

def generate_pr_summary(pr_merges):
    """Generate a summary description from PR merges"""
    if not pr_merges:
        return "No PRs in this release"
    
    # Get current date and time
    from datetime import datetime, timezone
    current_time = datetime.now(timezone.utc)
    date_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
    
    summary_lines = []
    summary_lines.append(f"Release Date: {date_time_str}")
    summary_lines.append(f"Release includes {len(pr_merges)} PR(s):\n")
    
    for i, pr in enumerate(pr_merges, 1):
        if pr.get('jira_ticket'):
            summary_lines.append(f"{i}. {pr['jira_ticket']}: {pr['description']} (PR #{pr['pr_number']})")
        else:
            summary_lines.append(f"{i}. {pr['description']} (PR #{pr['pr_number']})")
    
    return "\n".join(summary_lines)

def get_current_user():
    """Get current user information from Azure DevOps"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    try:
        # Get profile information
        profile_url = f"{ORG_URL}/_apis/profile/profiles/me?api-version=7.0"
        response = requests.get(profile_url, headers=headers)
        
        if response.status_code in [200, 202]:
            profile_data = response.json()
            return {
                'id': profile_data.get('id'),
                'displayName': profile_data.get('displayName'),
                'emailAddress': profile_data.get('emailAddress', ''),
                'name': profile_data.get('displayName', 'Unknown User')
            }
        else:
            # Fallback: try to get from commits or use default
            return {
                'id': 'unknown',
                'displayName': 'Deployment Automation',
                'emailAddress': 'deployment@automation',
                'name': 'Deployment Automation'
            }
    except Exception as e:
        print(f"⚠️  Could not get user info: {e}")
        return {
            'id': 'unknown',
            'displayName': 'Deployment Automation',
            'emailAddress': 'deployment@automation',
            'name': 'Deployment Automation'
        }

def create_tag(repo_name, tag_name, commit_hash, description, branch="master"):
    """Create a new annotated tag in the repository with tagger information"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Get current user for tagger information
    user_info = get_current_user()
    tagger_name = user_info.get('displayName', 'Deployment Automation')
    tagger_email = user_info.get('emailAddress', 'deployment@automation')
    
    # Get the commit object ID for the tag
    commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{commit_hash}?api-version=7.0"
    
    try:
        commit_response = requests.get(commit_url, headers=headers)
        if commit_response.status_code != 200:
            print(f"❌ Failed to get commit details: {commit_response.status_code}")
            return None
        
        commit_data = commit_response.json()
        commit_object_id = commit_data.get('commitId')
        
        # Get current timestamp for tag
        from datetime import datetime, timezone
        tag_date = datetime.now(timezone.utc).isoformat()
        
        # Create annotated tag using Azure DevOps Annotated Tags API
        # First, create the annotated tag object
        annotated_tags_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/annotatedtags?api-version=7.0"
        
        tag_object_payload = {
            "name": tag_name,
            "taggedObject": {
                "objectId": commit_object_id
            },
            "message": description,
            "tagger": {
                "name": tagger_name,
                "email": tagger_email,
                "date": tag_date
            }
        }
        
        # Create the annotated tag object
        tag_object_response = requests.post(annotated_tags_url, headers=headers, json=tag_object_payload)
        
        if tag_object_response.status_code in [200, 201]:
            tag_object_data = tag_object_response.json()
            tag_object_id = tag_object_data.get('objectId')
            
            print(f"✅ Annotated tag object created: {tag_object_id[:8]}")
            
            # Now create the ref pointing to the tag object
            tag_ref = f"refs/tags/{tag_name}"
            ref_payload = {
                "name": tag_ref,
                "oldObjectId": "0000000000000000000000000000000000000000",
                "newObjectId": tag_object_id
            }
            
            refs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.0"
            ref_response = requests.post(refs_url, headers=headers, json=[ref_payload])
            
            if ref_response.status_code in [200, 201]:
                print(f"✅ Tag '{tag_name}' created successfully!")
                print(f"   Commit: {commit_hash[:8]}")
                print(f"   Branch: {branch}")
                print(f"   Tagger: {tagger_name} ({tagger_email})")
                print(f"   Description: {description[:100]}..." if len(description) > 100 else f"   Description: {description}")
                
                return {
                    'tag_name': tag_name,
                    'commit_hash': commit_hash,
                    'description': description,
                    'tagger': tagger_name,
                    'tagger_email': tagger_email
                }
            else:
                print(f"⚠️  Tag object created but ref creation failed: {ref_response.status_code}")
                print(f"Response: {ref_response.text}")
                # Tag object exists but ref doesn't - might need manual cleanup
                return None
        else:
            # Fallback to lightweight tag if annotated tag creation fails
            print(f"⚠️  Annotated tag creation failed ({tag_object_response.status_code}), trying lightweight tag...")
            print(f"Response: {tag_object_response.text}")
            
            # Create lightweight tag as fallback
            tag_ref = f"refs/tags/{tag_name}"
            tag_payload = {
                "name": tag_ref,
                "oldObjectId": "0000000000000000000000000000000000000000",
                "newObjectId": commit_object_id
            }
            
            refs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.0"
            response = requests.post(refs_url, headers=headers, json=[tag_payload])
            
            if response.status_code in [200, 201]:
                print(f"✅ Lightweight tag '{tag_name}' created (no tagger info)")
                return {
                    'tag_name': tag_name,
                    'commit_hash': commit_hash,
                    'description': description
                }
            else:
                print(f"❌ Failed to create tag: {response.status_code}")
                print(f"Response: {response.text}")
                return None
            
    except Exception as e:
        print(f"❌ Error creating tag: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_tag_description(repo_name, tag_name, commit_hash, new_description, branch="master"):
    """Update an existing tag's description by creating a new annotated tag object"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Get current user for tagger information
    user_info = get_current_user()
    tagger_name = user_info.get('displayName', 'Deployment Automation')
    tagger_email = user_info.get('emailAddress', 'deployment@automation')
    
    # Get the commit object ID for the tag
    commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{commit_hash}?api-version=7.0"
    
    try:
        commit_response = requests.get(commit_url, headers=headers)
        if commit_response.status_code != 200:
            print(f"❌ Failed to get commit details: {commit_response.status_code}")
            return None
        
        commit_data = commit_response.json()
        commit_object_id = commit_data.get('commitId')
        
        # Get current timestamp for tag
        from datetime import datetime, timezone
        tag_date = datetime.now(timezone.utc).isoformat()
        
        # Get existing tag ref to find old object ID
        tag_ref = f"refs/tags/{tag_name}"
        refs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?filter={tag_ref}&api-version=7.0"
        refs_response = requests.get(refs_url, headers=headers)
        
        old_object_id = "0000000000000000000000000000000000000000"
        if refs_response.status_code == 200:
            refs_data = refs_response.json()
            if refs_data.get('value'):
                old_object_id = refs_data['value'][0].get('objectId', old_object_id)
        
        # Create new annotated tag object with updated description
        annotated_tags_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/annotatedtags?api-version=7.0"
        
        tag_object_payload = {
            "name": tag_name,
            "taggedObject": {
                "objectId": commit_object_id
            },
            "message": new_description,
            "tagger": {
                "name": tagger_name,
                "email": tagger_email,
                "date": tag_date
            }
        }
        
        # Create the new annotated tag object
        tag_object_response = requests.post(annotated_tags_url, headers=headers, json=tag_object_payload)
        
        if tag_object_response.status_code in [200, 201]:
            tag_object_data = tag_object_response.json()
            new_tag_object_id = tag_object_data.get('objectId')
            
            print(f"✅ New annotated tag object created: {new_tag_object_id[:8]}")
            
            # Update the ref to point to the new tag object
            ref_payload = {
                "name": tag_ref,
                "oldObjectId": old_object_id,
                "newObjectId": new_tag_object_id
            }
            
            refs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/refs?api-version=7.0"
            ref_response = requests.post(refs_url, headers=headers, json=[ref_payload])
            
            if ref_response.status_code in [200, 201]:
                print(f"✅ Tag '{tag_name}' description updated successfully!")
                print(f"   Commit: {commit_hash[:8]}")
                print(f"   Updated description: {new_description[:100]}..." if len(new_description) > 100 else f"   Updated description: {new_description}")
                
                return {
                    'tag_name': tag_name,
                    'commit_hash': commit_hash,
                    'description': new_description,
                    'tagger': tagger_name,
                    'tagger_email': tagger_email
                }
            else:
                print(f"⚠️  Tag object created but ref update failed: {ref_response.status_code}")
                print(f"Response: {ref_response.text}")
                return None
        else:
            print(f"❌ Failed to create new tag object: {tag_object_response.status_code}")
            print(f"Response: {tag_object_response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error updating tag: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_release_tag(pr_merges, branch="master", repo_name=REPOSITORY_NAME):
    """Create a new release tag before stage deployment"""
    print("\n🏷️  Creating release tag for STAGE deployment...")
    print(f"   Repository: {repo_name}")
    print(f"   Branch: {branch}")
    
    # Get latest tag
    latest_tag = get_latest_tag(repo_name)
    
    # Increment version
    new_tag_name = increment_tag_version(latest_tag)
    
    # Get the latest commit from master branch
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Get latest commit from branch
    commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
    params = {
        "searchCriteria.itemVersion.version": branch,
        "searchCriteria.itemVersion.versionType": "branch",
        "$top": 1,
        "api-version": "7.0"
    }
    
    try:
        commits_response = requests.get(commits_url, headers=headers, params=params)
        if commits_response.status_code != 200:
            print(f"❌ Failed to get latest commit: {commits_response.status_code}")
            return None
        
        commits_data = commits_response.json()
        commits = commits_data.get('value', [])
        
        if not commits:
            print("❌ No commits found on master branch")
            return None
        
        latest_commit = commits[0]
        commit_hash = latest_commit.get('commitId')
        
        print(f"✅ Found latest commit: {commit_hash[:8]}")
        
        # Generate PR summary
        description = generate_pr_summary(pr_merges)
        
        # Create tag
        tag_result = create_tag(repo_name, new_tag_name, commit_hash, description, branch)
        
        if tag_result:
            print(f"\n✅ Release tag created successfully!")
            print(f"   Tag: {new_tag_name}")
            print(f"   Previous tag: {latest_tag or 'None (first tag)'}")
            return tag_result
        else:
            print("❌ Failed to create release tag")
            return None
            
    except Exception as e:
        print(f"❌ Error creating release tag: {e}")
        import traceback
        traceback.print_exc()
        return None

def verify_commit_on_branch(commit_hash, branch="dev", repo_name=None):
    """Verify if a commit exists on a specific branch by trying to get commits from that commit on the branch"""
    headers = get_azure_devops_headers()
    if not headers:
        return False
    
    # Use configured repository if not specified
    if not repo_name:
        repo_name = REPOSITORY_NAME
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return False
    
    # Normalize branch name
    branch_name = branch.replace("refs/heads/", "")
    
    # Try to get commits from this commit on the branch
    # If the commit exists on the branch, this will return at least the commit itself
    commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
    params = {
        "searchCriteria.fromCommitId": commit_hash,
        "searchCriteria.itemVersion.version": branch_name,
        "searchCriteria.itemVersion.versionType": "branch",
        "$top": 1,
        "api-version": "7.0"
    }
    
    try:
        response = requests.get(commits_url, headers=headers, params=params)
        if response.status_code in [200, 202]:
            commits_data = response.json()
            commits = commits_data.get('value', [])
            # If we get results, the commit exists on this branch
            # (The API returns commits from the specified commit, including the commit itself if it's on the branch)
            if commits:
                # Check if the first commit is our target commit or if it's in the results
                for commit in commits:
                    if commit.get('commitId') == commit_hash:
                        return True
                # If we got results but not our commit, it might still be on the branch (just not in the first result)
                # Try a different approach - check if we can get the commit with branch filter
                return True  # If API returned results, commit likely exists on branch
        return False
    except Exception as e:
        print(f"⚠️  Error verifying commit on branch: {e}")
        return False

def find_commit_on_branch_by_date(target_date, branch="dev", repo_name=None):
    """Find the commit on a branch closest to a target date"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Use configured repository if not specified
    if not repo_name:
        repo_name = REPOSITORY_NAME
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Normalize branch name
    branch_name = branch.replace("refs/heads/", "")
    
    commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
    params = {
        "searchCriteria.itemVersion.version": branch_name,
        "searchCriteria.itemVersion.versionType": "branch",
        "$top": 100,  # Get more commits to find the closest one
        "api-version": "7.0"
    }
    
    try:
        response = requests.get(commits_url, headers=headers, params=params)
        if response.status_code in [200, 202]:
            commits_data = response.json()
            commits = commits_data.get('value', [])
            
            if not commits:
                return None
            
            # Find the commit closest to the target date (before or at the date)
            from datetime import datetime
            # Handle Azure DevOps date format with microseconds and timezone
            if isinstance(target_date, str):
                # Remove microseconds if present (Azure DevOps format: 2025-11-06T15:54:34.9027345+00:00)
                date_str = target_date.replace('Z', '+00:00')
                # Remove microseconds (keep only up to seconds)
                if '.' in date_str and '+' in date_str:
                    parts = date_str.split('.')
                    if len(parts) == 2:
                        seconds_part = parts[0]
                        tz_part = parts[1].split('+')[-1] if '+' in parts[1] else parts[1].split('-')[-1]
                        date_str = f"{seconds_part}+{tz_part}" if '+' in parts[1] else f"{seconds_part}-{tz_part}"
                elif '.' in date_str:
                    date_str = date_str.split('.')[0] + '+00:00'
                target_dt = datetime.fromisoformat(date_str)
            else:
                target_dt = target_date
            
            closest_commit = None
            closest_diff = None
            
            for commit in commits:
                commit_date_str = commit.get('committer', {}).get('date')
                if commit_date_str:
                    # Handle Azure DevOps date format with microseconds
                    date_str = commit_date_str.replace('Z', '+00:00')
                    # Remove microseconds if present
                    if '.' in date_str and '+' in date_str:
                        parts = date_str.split('.')
                        if len(parts) == 2:
                            seconds_part = parts[0]
                            tz_part = parts[1].split('+')[-1] if '+' in parts[1] else parts[1].split('-')[-1]
                            date_str = f"{seconds_part}+{tz_part}" if '+' in parts[1] else f"{seconds_part}-{tz_part}"
                    elif '.' in date_str:
                        date_str = date_str.split('.')[0] + '+00:00'
                    commit_dt = datetime.fromisoformat(date_str)
                    diff = (target_dt - commit_dt).total_seconds()
                    
                    # Prefer commits before or at the target date
                    if diff >= 0:
                        if closest_diff is None or diff < closest_diff:
                            closest_diff = diff
                            closest_commit = commit.get('commitId')
            
            # If no commit before target date, use the oldest commit we found
            if closest_commit is None and commits:
                closest_commit = commits[-1].get('commitId')
            
            if closest_commit:
                print(f"✅ Found commit on {branch_name} closest to build date: {closest_commit[:8]}")
                return closest_commit
            
        return None
    except Exception as e:
        print(f"⚠️  Error finding commit by date: {e}")
        return None

def get_latest_commit_from_branch(branch="dev", repo_name=None):
    """Get the latest commit hash from a branch"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Use configured repository if not specified
    if not repo_name:
        repo_name = REPOSITORY_NAME
    
    repo_id = get_repository_id(repo_name)
    if not repo_id:
        return None
    
    # Normalize branch name
    branch_name = branch.replace("refs/heads/", "")
    
    commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
    params = {
        "searchCriteria.itemVersion.version": branch_name,
        "searchCriteria.itemVersion.versionType": "branch",
        "$top": 1,
        "api-version": "7.0"
    }
    
    try:
        response = requests.get(commits_url, headers=headers, params=params)
        if response.status_code in [200, 202]:
            commits_data = response.json()
            commits = commits_data.get('value', [])
            if commits:
                latest_commit = commits[0].get('commitId')
                print(f"✅ Latest commit from {branch_name}: {latest_commit[:8]}")
                return latest_commit
        return None
    except Exception as e:
        print(f"⚠️  Error getting latest commit: {e}")
        return None

def get_pr_merges_after_commit(commit_hash, branch="dev"):
    """Get PRs merged after a specific commit using Azure DevOps API"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    try:
        print("🔍 Getting repository information...")
        # Use the configured repository name for PR detection
        repo_id = get_repository_id(REPOSITORY_NAME)
        if not repo_id:
            print("❌ Failed to get repository ID")
            return None
        
        # Normalize branch name (remove refs/heads/ if present)
        branch_name = branch.replace("refs/heads/", "")
        
        print(f"🔍 Getting commit details for: {commit_hash[:8]}...")
        commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{commit_hash}?api-version=7.0"
        commit_response = requests.get(commit_url, headers=headers)
        
        if commit_response.status_code != 200:
            print(f"⚠️  Could not get commit details (status: {commit_response.status_code}), trying to get commits from branch...")
            commit_date = None
        else:
            commit_data = commit_response.json()
            commit_date = commit_data.get('committer', {}).get('date')
            if commit_date:
                print(f"✅ Found commit date: {commit_date}")
        
        print(f"🔍 Looking for commits after {commit_hash[:8]} on '{branch_name}' branch...")
        print(f"   Branch filter: {branch_name}")
        print(f"   Commit hash: {commit_hash[:8]}")
        
        # Get baseline commit date first
        baseline_commit_date = commit_date
        if not baseline_commit_date:
            commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{commit_hash}?api-version=7.0"
            commit_response = requests.get(commit_url, headers=headers)
            if commit_response.status_code == 200:
                commit_data = commit_response.json()
                committer = commit_data.get('committer', {})
                baseline_commit_date = committer.get('date')
        
        if not baseline_commit_date:
            print(f"❌ Could not get baseline commit date")
            return None
        
        print(f"   Baseline commit date: {baseline_commit_date}")
        
        # Get all commits from dev branch (without fromCommitId filter, as it's unreliable)
        # We'll filter by date instead
        commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
        params = {
            "searchCriteria.itemVersion.version": branch_name,
            "searchCriteria.itemVersion.versionType": "branch",
            "api-version": "7.0",
            "$top": 100  # Get top 100 commits to ensure we capture all recent PRs
        }
        
        print(f"   API params: branch={branch_name}, top=100 (filtering by date)")
        
        commits_response = requests.get(commits_url, headers=headers, params=params)
        
        if commits_response.status_code != 200:
            print(f"❌ Failed to get commits: {commits_response.status_code}")
            print(f"Response: {commits_response.text}")
            return None
        
        commits_data = commits_response.json()
        commits = commits_data.get('value', [])
        
        # Get the baseline commit date for comparison
        baseline_commit_date = None
        baseline_commit_obj = None
        for c in commits:
            if c.get('commitId', '').startswith(commit_hash) or c.get('commitId') == commit_hash:
                baseline_commit_obj = c
                committer = c.get('committer', {})
                baseline_commit_date = committer.get('date')
                break
        
        if not baseline_commit_date:
            # If we can't find the baseline commit in the results, try to get its date separately
            commit_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits/{commit_hash}?api-version=7.0"
            commit_response = requests.get(commit_url, headers=headers)
            if commit_response.status_code == 200:
                commit_data = commit_response.json()
                committer = commit_data.get('committer', {})
                baseline_commit_date = committer.get('date')
        
        # Filter commits to only include those AFTER the baseline commit
        # We need to compare commit dates to ensure we only get newer commits
        commits_after = []
        if baseline_commit_date:
            from datetime import datetime
            # Parse baseline date
            baseline_dt = datetime.fromisoformat(baseline_commit_date.replace('Z', '+00:00'))
            
            for c in commits:
                commit_id = c.get('commitId', '')
                # Skip the baseline commit itself
                if commit_id.startswith(commit_hash) or commit_id == commit_hash:
                    continue
                
                # Get commit date
                committer = c.get('committer', {})
                commit_date_str = committer.get('date')
                if commit_date_str:
                    # Parse commit date
                    commit_dt = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
                    # Only include commits that are newer than baseline
                    if commit_dt > baseline_dt:
                        commits_after.append(c)
        else:
            # Fallback: exclude baseline commit but include all others (less accurate)
            print(f"⚠️  Could not get baseline commit date, using fallback filtering")
            commits_after = [c for c in commits if not (c.get('commitId', '').startswith(commit_hash) or c.get('commitId') == commit_hash)]
        
        if not commits_after:
            print(f"  ℹ️  Build is from the latest commit. No new PRs merged after build.")
            print(f"  ℹ️  No new changes to deploy since last build.")
            return []
        
        print(f"✅ Found {len(commits_after)} commits after build commit (filtered by date)")
        
        pr_merges = []
        
        for commit in commits_after:
            commit_message = commit.get('comment', '')
            author_info = commit.get('author', {})
            author_name = author_info.get('name', 'Unknown')
            commit_hash_part = commit.get('commitId', '')[:8]
            
            if "Merged PR" in commit_message:
                try:
                    pr_match = commit_message.split("Merged PR ")[1].split(":")[0].strip()
                    if pr_match.isdigit():
                        pr_number = pr_match
                        
                        jira_match = None
                        jira_ticket = None
                        if "ADW-" in commit_message:
                            jira_match = commit_message.split("ADW-")[1].split()[0]
                            jira_ticket = f"ADW-{jira_match}"
                        
                        description = commit_message.split("Merged PR")[1].split(":")[1] if ":" in commit_message.split("Merged PR")[1] else ""
                        if jira_ticket and jira_ticket in description:
                            description = description.replace(jira_ticket, "").strip()
                        if "[Merkle]" in description:
                            description = description.replace("[Merkle]", "").strip()
                        
                        clean_author = author_name.replace("X", "").strip()
                        
                        pr_merges.append({
                            'pr_number': pr_number,
                            'jira_ticket': jira_ticket if jira_match else None,
                            'description': description.strip(),
                            'author': clean_author,
                            'commit_hash': commit_hash_part,
                            'note': 'Merged after build'
                        })
                except Exception as e:
                    print(f"⚠️  Error parsing commit message: {e}")
                    continue
        
        print(f"✅ Found {len(pr_merges)} PR merges after build")
        return pr_merges
        
    except Exception as e:
        print(f"✗ Error getting PR merges from Azure DevOps API: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# TEAMS MESSAGING FUNCTIONS
# ============================================================================

def send_teams_message(webhook_url, message):
    """Send message to Teams channel or Power Automate webhook"""
    
    payload = {}
    headers = {"Content-Type": "application/json"}
    
    # Check if this is the new Power Automate webhook
    if webhook_url == POWER_AUTOMATE_WEBHOOK_URL:
        # This webhook expects a full Adaptive Card payload with an 'attachments' array,
        # as per the user's reference script and the "attachments is Null" error.
        
        # 1. Create the inner Adaptive Card content
        adaptive_card_content = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2", # Using 1.2 for broad compatibility
            "body": [
                {
                    "type": "TextBlock",
                    "text": message,  # This is the full, formatted message string
                    "wrap": True
                }
            ]
        }
        
        # 2. Wrap it in the 'attachments' payload required by the Flow
        #    This structure comes from the user's reference script.
        payload = {
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": adaptive_card_content
                }
            ]
        }
    else:
        # This is the original Teams webhook, which expects a simple text payload
        payload = {
            "text": message
        }
    
    try:
        # Send the request. 
        # We use json=payload, which automatically sets Content-Type
        # and serializes the dict to JSON.
        response = requests.post(webhook_url, json=payload, headers=headers)
        
        # Accept 200 (OK) and 202 (Accepted) as success
        if response.status_code in [200, 202]:
            print("✅ Message sent successfully!")
            return True
        else:
            # Explicitly print the error if it's not a 2xx
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"   Webhook: {webhook_url[:70]}...") 
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        # Catch connection errors, timeouts, etc.
        print(f"❌ Failed to send message due to request exception: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected error
        print(f"❌ Error sending message: {e}")
        return False
    """Send message to Teams channel or Power Automate webhook"""
    
    payload = {}
    
    # Check if this is the new Power Automate webhook
    if webhook_url == POWER_AUTOMATE_WEBHOOK_URL:
        # This webhook expects a full Adaptive Card payload with an 'attachments' array.
        # We will wrap our simple text 'message' into the minimum required
        # Adaptive Card structure to satisfy the flow.
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "type": "AdaptiveCard",
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "version": "1.2",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": message,  # This is your full, formatted message
                                "wrap": True
                            }
                        ]
                    }
                }
            ]
        }
    else:
        # This is the original Teams webhook, which expects {"text": "..."}
        payload = {
            "text": message
        }
    
    try:
        response = requests.post(webhook_url, json=payload)
        
        # Accept 200 (OK) and 202 (Accepted) as success
        if response.status_code in [200, 202]:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"   Webhook: {webhook_url[:70]}...") # Show which webhook failed
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

def send_teams_approval_request(webhook_url, pr_merges, build_info, approver_email=None, pipeline_name="DEV"):
    """Send clean Microsoft Teams approval request"""
    pr_list = ""
    for i, pr in enumerate(pr_merges, 1):
        if pr['jira_ticket']:
            pr_list += f"**{i}. {pr['jira_ticket']}** [Merkle]\n"
            pr_list += f"   {pr['description']}\n"
            pr_list += f"   👤 {pr['author']} (PR {pr['pr_number']})\n\n"
        else:
            pr_list += f"**{i}. [Merkle]**\n"
            pr_list += f"   {pr['description']}\n"
            pr_list += f"   👤 {pr['author']} (PR {pr['pr_number']})\n\n"
    
    # Determine environment name from pipeline
    env_name = pipeline_name.upper() if pipeline_name else "DEV"
    
    approvers = "<at>Paras.Patwal@merkle.com</at> <at>rohith.venati@merkle.com</at>"
    
    teams_payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "0076D7",
        "summary": "Deployment Approval Request",
        "sections": [
            {
                "activityTitle": "🚀 Deployment Bot",
                "activitySubtitle": "Automated Deployment System",
                "text": f"""
🔔 **DEPLOYMENT APPROVAL REQUEST**

**@Paras Patwal @rohith venati** - Please review and approve the deployment to {env_name} environment on Azure DevOps.

**Build Details:**
• **Build Number:** {build_info['build_number']}
• **Build ID:** {build_info['build_id']}
• **Source Commit:** {build_info['source_version'][:8]}
• **Total PRs:** {len(pr_merges)}
• **Estimated Time:** ~30 minutes

**PRs to be deployed:**

{pr_list.strip()}

**Next Steps:**
1. ✅ Approve the deployment on Azure DevOps

**Note:** Please approve this request directly on Azure DevOps pipeline.
                """,
                "markdown": True
            }
        ],
        "potentialAction": [
            {
                "@type": "OpenUri",
                "name": "🔗 Review Build Details",
                "targets": [
                    {
                        "os": "default",
                        "uri": f"https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=teams_payload)
        
        if response.status_code in [200, 202]:
            print("✅ Approval request sent to Teams successfully!")
            print("📋 Users should approve on Azure DevOps")
            print("🔗 Build link is included for review")
            return True
        else:
            print(f"❌ Failed to send approval request: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending approval request: {e}")
        return False

def send_teams_deployment_confirmation(webhook_url, pr_merges, build_info, new_build_info=None):
    """Send deployment confirmation message to Teams"""
    pr_list = ""
    for pr in pr_merges:
        if pr['jira_ticket']:
            pr_list += f"• **{pr['jira_ticket']}** [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
        else:
            pr_list += f"• [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
    
    if new_build_info:
        deployment_message = f"""
🚀 **DEPLOYMENT TO DEV TRIGGERED**

The following merged PRs have been getting deployed to the development environment:

{pr_list}

**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={new_build_info['build_id']}&view=results)
**New Build Number:** {new_build_info['build_number']}
**Estimated Completion Time:** ~30 minutes
        """
    else:
        deployment_message = f"""
🚀 **DEPLOYMENT TO DEV TRIGGERED**

The following merged PRs have been getting deployed to the development environment:

{pr_list}

**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)
**Estimated Completion Time:** ~30 minutes
        """
    
    # Determine which webhook to use based on the status
    if status_type in ["triggered", "succeeded", "failed"]:
        # Send final build statuses (triggered, succeeded, failed) to the new Power Automate webhook
        target_webhook = POWER_AUTOMATE_WEBHOOK_URL
    else:
        # Send in-progress messages to the original Teams webhook
        target_webhook = TEAMS_WEBHOOK_URL
    
    return send_teams_message(target_webhook, status_message.strip())

def send_teams_approved_message(webhook_url, pr_merges, build_info, approver_name=None):
    """Send approved message to Teams"""
    pr_list = ""
    for pr in pr_merges:
        if pr['jira_ticket']:
            pr_list += f"• **{pr['jira_ticket']}** [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
        else:
            pr_list += f"• [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
    
    if approver_name:
        approved_message = f"""
✅ **DEPLOYMENT APPROVED**

@{approver_name} has approved the deployment to DEV environment.

**Approved PRs:**
{pr_list}

**Build Details:**
• Build Number: {build_info['build_number']}
• Build ID: {build_info['build_id']}
• Source Commit: {build_info['source_version'][:8]}
• Total PRs: {len(pr_merges)}

**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

**Next Steps:** Deployment can now proceed to DEV environment.
**Estimated Completion Time:** ~30 minutes
        """
    else:
        approved_message = f"""
✅ **DEPLOYMENT APPROVED**

The deployment to DEV environment has been approved.

**Approved PRs:**
{pr_list}

**Build Details:**
• Build Number: {build_info['build_number']}
• Build ID: {build_info['build_id']}
• Source Commit: {build_info['source_version'][:8]}
• Total PRs: {len(pr_merges)}

**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

**Next Steps:** Deployment can now proceed to DEV environment.
**Estimated Completion Time:** ~30 minutes
        """
    
    # Determine which webhook to use based on the status
    if status_type in ["triggered", "succeeded", "failed"]:
        # Send final build statuses (triggered, succeeded, failed) to the new Power Automate webhook
        target_webhook = POWER_AUTOMATE_WEBHOOK_URL
    else:
        # Send in-progress messages to the original Teams webhook
        target_webhook = TEAMS_WEBHOOK_URL
    
    return send_teams_message(target_webhook, status_message.strip())

def send_teams_build_triggered_message(webhook_url, pr_merges, build_info, new_build_info):
    """Send message when build is triggered after approval"""
    pr_list = ""
    for pr in pr_merges:
        if pr['jira_ticket']:
            pr_list += f"• **{pr['jira_ticket']}** [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
        else:
            pr_list += f"• [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
    
    build_triggered_message = f"""
🚀 **Deployment Bot** 🚀 **BUILD TRIGGERED - DEPLOYMENT IN PROGRESS**

The approved deployment is now being processed.

**Deploying PRs:**
{pr_list}

**Build Information:**
• Original Build: {build_info['build_number']} (ID: {build_info['build_id']})
• New Build: {new_build_info['build_number']} (ID: {new_build_info['build_id']})
• Total PRs: {len(pr_merges)}

**New Build Status:** [View New Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={new_build_info['build_id']}&view=results)

**Estimated Completion Time:** ~30 minutes

✅ Deployment approved and build triggered successfully!
    """
    
    # Determine which webhook to use based on the status
    if status_type in ["triggered", "succeeded", "failed"]:
        # Send final build statuses (triggered, succeeded, failed) to the new Power Automate webhook
        target_webhook = POWER_AUTOMATE_WEBHOOK_URL
    else:
        # Send in-progress messages to the original Teams webhook
        target_webhook = TEAMS_WEBHOOK_URL
    
    return send_teams_message(target_webhook, status_message.strip())

def format_deployment_message_for_teams(pr_merges, build_info, new_build_info=None):
    """Format deployment message for Teams"""
    if not pr_merges:
        message = f"""
🚀 **NO NEW DEPLOYMENT NEEDED**

No new PRs have been merged since the last build.
The current build is up to date with the latest changes.

**Build Details:**
• Build Number: {build_info['build_number']}
• Build ID: {build_info['build_id']}
• Source Commit: {build_info['source_version'][:8]}
• Started: {build_info['start_time']}

**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)
        """
    else:
        message = f"""
🚀 **DEPLOYMENT TO DEV TRIGGERED**

The following merged PRs have been getting deployed to the development environment:

"""
        
        for pr in pr_merges:
            if pr['jira_ticket']:
                message += f"• **{pr['jira_ticket']}** [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
            else:
                message += f"• [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
        
        if new_build_info:
            message += f"""
**New Build:** {new_build_info['build_number']} (ID: {new_build_info['build_id']})
**Build Status:** [View New Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={new_build_info['build_id']}&view=results)
"""
        else:
            message += f"""
**Build Status:** [View Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)
"""
        
        message += f"""
**Estimated Completion Time:** ~30 minutes

**Total PRs in this deployment:** {len(pr_merges)}
        """
    
    return message.strip()

# ============================================================================
# MONITORING FUNCTIONS
# ============================================================================

def check_build_approval_status(build_id):
    """Check if build has been approved (completed successfully)"""
    build_status = get_build_status(build_id)
    if not build_status:
        print(f"❌ Failed to get build status for ID: {build_id}")
        return False, None
    
    status = build_status['status']
    result = build_status.get('result')
    
    print(f"🔍 Build Status Check: {status}, Result: {result}")
    print(f"   Build ID: {build_id}")
    print(f"   Build Number: {build_status.get('build_number', 'N/A')}")
    
    if status == 'completed' and result in ['succeeded', 'partiallySucceeded']:
        print("✅ Build completed successfully!")
        return True, build_status
    elif status == 'completed' and result in ['failed', 'canceled']:
        print(f"❌ Build completed with failure: {result}")
        return False, build_status
    else:
        print(f"⏳ Build still in progress: {status}")
        return None, build_status

def send_deployment_completed_message(pr_merges, build_info, final_build_status):
    """Send deployment completed message to Teams"""
    pr_list = ""
    for pr in pr_merges:
        if pr['jira_ticket']:
            pr_list += f"• **{pr['jira_ticket']}** [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
        else:
            pr_list += f"• [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})\n"
    
    if final_build_status.get('start_time') and final_build_status.get('finish_time'):
        start_time = datetime.fromisoformat(final_build_status['start_time'].replace('Z', '+00:00'))
        finish_time = datetime.fromisoformat(final_build_status['finish_time'].replace('Z', '+00:00'))
        duration = finish_time - start_time
        duration_str = f"{duration.total_seconds() / 60:.1f} minutes"
    else:
        duration_str = "~30 minutes (estimated)"
    
    deployment_completed_message = f"""
✅ **DEPLOYMENT COMPLETED SUCCESSFULLY**

The deployment to DEV environment has been completed.

**Deployed PRs:**
{pr_list}

**Deployment Details:**
• Build Number: {final_build_status['build_number']}
• Build ID: {build_info['build_id']}
• Status: {final_build_status['result'].upper()}
• Duration: {duration_str}
• Completed: {final_build_status.get('finish_time', 'N/A')}

**Build Status:** [View Final Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

🎉 **Deployment to DEV environment is now live!**
    """
    
    # Determine which webhook to use based on the status
    if status_type in ["triggered", "succeeded", "failed"]:
        # Send final build statuses (triggered, succeeded, failed) to the new Power Automate webhook
        target_webhook = POWER_AUTOMATE_WEBHOOK_URL
    else:
        # Send in-progress messages to the original Teams webhook
        target_webhook = TEAMS_WEBHOOK_URL
    
    return send_teams_message(target_webhook, status_message.strip())

def send_pipeline_status_update(pr_merges, build_info, build_status, status_type, pipeline_name="DEPLOYMENT"):
    """Send pipeline status update to Teams"""
    pr_list = ""
    for i, pr in enumerate(pr_merges, 1):
        if pr['jira_ticket']:
            pr_list += f"**{i}. {pr['jira_ticket']}** [Merkle]\n"
            pr_list += f"   {pr['description']}\n"
            pr_list += f"   👤 {pr['author']} (PR {pr['pr_number']})\n\n"
        else:
            pr_list += f"**{i}. [Merkle]**\n"
            pr_list += f"   {pr['description']}\n"
            pr_list += f"   👤 {pr['author']} (PR {pr['pr_number']})\n\n"
    
    if status_type == "triggered":
        status_message = f"""
🚀 **{pipeline_name} PIPELINE TRIGGERED**

The {pipeline_name.lower()} deployment pipeline has been triggered and is now running.

**Deploying PRs:**

{pr_list.strip()}

**Build Details:**
• **Build Number:** {build_status['build_number']}
• **Build ID:** {build_info['build_id']}
• **Status:** {build_status['status'].upper()}
• **Total PRs:** {len(pr_merges)}

**Build Status:** [View Running Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

⏳ **Monitoring deployment progress...**
        """
    elif status_type == "succeeded":
        # Determine environment name from pipeline
        env_name = pipeline_name.upper() if pipeline_name else "DEV"
        
        if build_status.get('result') == 'partiallySucceeded':
            status_title = "✅ **DEV DEPLOYMENT COMPLETED**"
            status_desc = f"The deployment to {env_name} environment has completed with partial success."
            status_note = "⚠️ **Some components may have warnings - check build logs for details.**"
        else:
            status_title = "✅ **DEPLOYMENT SUCCEEDED**"
            status_desc = f"The deployment to {env_name} environment has completed successfully!"
            status_note = f"🎉 **Deployment to {env_name} environment is now live!**"
        
        status_message = f"""
{status_title}

{status_desc}

**Deployed PRs:**

{pr_list.strip()}

**Build Details:**
• **Build Number:** {build_status['build_number']}
• **Build ID:** {build_info['build_id']}
• **Status:** {build_status['result'].upper()}
• **Total PRs:** {len(pr_merges)}

**Build Status:** [View Build Results](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

{status_note}
        """
    elif status_type == "failed":
        # Determine environment name from pipeline
        env_name = pipeline_name.upper() if pipeline_name else "DEV"
        
        status_message = f"""
❌ **DEPLOYMENT FAILED**

The deployment to {env_name} environment has failed.

**Failed PRs:**

{pr_list.strip()}

**Build Details:**
• **Build Number:** {build_status['build_number']}
• **Build ID:** {build_info['build_id']}
• **Status:** {build_status['result'].upper()}
• **Total PRs:** {len(pr_merges)}

**Build Status:** [View Failed Build](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

⚠️ **Please check the build logs for more details.**
        """
    else:  # in_progress
        status_message = f"""
⏳ **DEPLOYMENT IN PROGRESS**

The deployment is still running. Current status update:

**Deploying PRs:**

{pr_list.strip()}

**Build Details:**
• **Build Number:** {build_status['build_number']}
• **Build ID:** {build_info['build_id']}
• **Status:** {build_status['status'].upper()}
• **Total PRs:** {len(pr_merges)}

**Build Status:** [View Build Progress](https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results)

🔄 **Still monitoring...**
        """
    
    # Determine which webhook to use based on the status
    if status_type in ["triggered", "succeeded", "failed"]:
        # Send final build statuses (triggered, succeeded, failed) to the new Power Automate webhook
        target_webhook = POWER_AUTOMATE_WEBHOOK_URL
    else:
        # Send in-progress messages to the original Teams webhook
        target_webhook = TEAMS_WEBHOOK_URL

    return send_teams_message(target_webhook, status_message.strip())

def monitor_deployment_progress(pr_merges, build_info, max_wait_minutes=120, pipeline_name="DEPLOYMENT", branch=None, tag_info=None):
    """Monitor deployment progress with smart intervals and dynamic PR updates"""
    print(f"🔍 Starting deployment monitoring for build {build_info['build_id']}")
    print(f"⏱️  Maximum wait time: {max_wait_minutes} minutes")
    print(f"📊 Initial PRs to monitor: {len(pr_merges)}")
    print(f"🔄 Phase 1: Checking every 30 seconds until build starts running")
    print(f"🔄 Phase 2: Checking every 10 minutes for first 30 minutes, then every 2 minutes until completion")
    if tag_info:
        print(f"🏷️  Tag: {tag_info.get('tag_name', 'N/A')}")
    
    # Get branch - use provided branch or default to DEV branch
    if not branch:
        branch = BRANCH  # Default to "dev" for DEV pipeline
    
    # Store baseline commit for reference
    baseline_commit = build_info.get('baseline_commit') or build_info.get('source_version')
    current_pr_merges = pr_merges.copy() if pr_merges else []
    
    if baseline_commit:
        print(f"   Baseline commit: {baseline_commit[:8] if len(baseline_commit) > 8 else baseline_commit}")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    check_interval_fast = 30
    check_interval_slow = 600  # 10 minutes initially
    check_interval_slow_after_30min = 120  # 2 minutes after 30 minutes in Phase 2
    last_status = None
    triggered_sent = False
    build_is_running = False
    phase2_start_time = None
    phase2_30min_switch_announced = False
    
    while True:
        try:
            elapsed_time = time.time() - start_time
            if elapsed_time > max_wait_seconds:
                print(f"⏰ Maximum wait time ({max_wait_minutes} minutes) exceeded")
                break
            
            elapsed_minutes = elapsed_time / 60
            print(f"\n🔍 Monitoring check #{int(elapsed_time/30) + 1} - {elapsed_minutes:.1f} minutes elapsed")
            
            approval_status, build_status = check_build_approval_status(build_info['build_id'])
            
            if build_status is None:
                print("❌ Failed to get build status, retrying in 30 seconds...")
                time.sleep(30)
                continue
            
            if approval_status is True:
                print("✅ Build completed successfully!")
                print(f"   Build Number: {build_status['build_number']}")
                print(f"   Result: {build_status['result']}")
                print(f"   Duration: {elapsed_time / 60:.1f} minutes")
                print(f"   Final PR count: {len(current_pr_merges)}")
                
                print("📱 Sending deployment succeeded message to Teams...")
                send_pipeline_status_update(current_pr_merges, build_info, build_status, "succeeded", pipeline_name)
                
                return True, build_status
                
            elif approval_status is False:
                print("❌ Build failed or was canceled")
                print(f"   Result: {build_status['result']}")
                print(f"   PR count: {len(current_pr_merges)}")
                
                print("📱 Sending deployment failed message to Teams...")
                send_pipeline_status_update(current_pr_merges, build_info, build_status, "failed", pipeline_name)
                
                return False, build_status
                
            else:
                elapsed_minutes = elapsed_time / 60
                current_status = build_status['status'] if build_status else 'unknown'
            
            if not build_is_running:
                if not triggered_sent and current_status in ['inProgress']:
                    deployment_type = build_status.get('deployment_type', '')
                    
                    # Only send started notification for Full Stack deployments
                    # AND only switch to Phase 2 when the specialized stage is complete if it's a Full Stack deployment
                    should_switch_to_phase2 = False
                    
                    if deployment_type == 'Full Stack':
                        # Check if "AEM deployment - Full Stack" stage is active or completed
                        timeline = get_build_timeline(build_info['build_id'])
                        full_stack_stage_active = is_stage_active_or_completed(timeline, "AEM deployment - Full Stack")
                        
                        if full_stack_stage_active:
                            print("🚀 Full Stack deployment stage in progress/active - sending triggered message...")
                            print(f"   Previous status: {last_status}")
                            print(f"   Current status: {current_status}")
                            print(f"   Deployment Type: {deployment_type}")
                            print(f"   PRs in this deployment: {len(current_pr_merges)}")
                            success = send_pipeline_status_update(current_pr_merges, build_info, build_status, "triggered", pipeline_name)
                            if success:
                                print("✅ Pipeline triggered message sent successfully!")
                            else:
                                print("❌ Failed to send pipeline triggered message")
                            
                            should_switch_to_phase2 = True
                        else:
                            print(f"⏳ Waiting for 'AEM deployment - Full Stack' stage to start before switching phases...")
                    else:
                        # For non-Full Stack or generic deployments, allow standard behavior
                        print(f"ℹ️  Build is running (Type: {deployment_type}) - skipping started notification (only for Full Stack)")
                        should_switch_to_phase2 = True
                    
                    if should_switch_to_phase2:
                        triggered_sent = True
                        build_is_running = True
                        phase2_start_time = time.time()  # Track when Phase 2 starts
                        last_status = current_status
                        print("🔄 Switching to Phase 2: Monitoring every 10 minutes for first 30 minutes, then every 2 minutes")
                else:
                    print(f"⏳ Waiting for build/stage to progress... ({elapsed_minutes:.1f} minutes elapsed)")
                    print(f"   Status: {current_status}")
                    print(f"   Triggered sent: {triggered_sent}")
                    print(f"   Build is running: {build_is_running}")
                    if last_status != current_status:
                        print(f"   Status changed from {last_status} to {current_status}")
                        last_status = current_status
                
                check_interval = check_interval_fast
                
            else:
                # Phase 2: Check if 30 minutes have elapsed since Phase 2 started
                if phase2_start_time is not None:
                    phase2_elapsed_time = time.time() - phase2_start_time
                    phase2_elapsed_minutes = phase2_elapsed_time / 60
                    
                    if phase2_elapsed_minutes >= 30:
                        # After 30 minutes in Phase 2, check every 2 minutes
                        check_interval = check_interval_slow_after_30min
                        if not phase2_30min_switch_announced:
                            print(f"🔄 Phase 2: 30 minutes elapsed - switching to monitoring every 2 minutes")
                            phase2_30min_switch_announced = True
                    else:
                        # First 30 minutes of Phase 2, check every 10 minutes
                        check_interval = check_interval_slow
                else:
                    # Fallback to slow interval if phase2_start_time not set
                    check_interval = check_interval_slow
                
                if last_status != current_status and current_status not in ['inProgress']:
                    print(f"📱 Status changed - sending update to Teams...")
                    print(f"   Old Status: {last_status}")
                    print(f"   New Status: {current_status}")
                    print(f"   Elapsed: {elapsed_minutes:.1f} minutes")
                    if phase2_start_time is not None:
                        phase2_elapsed_minutes = (time.time() - phase2_start_time) / 60
                        print(f"   Phase 2 elapsed: {phase2_elapsed_minutes:.1f} minutes")
                    print(f"   Current PR count: {len(current_pr_merges)}")
                    
                    send_pipeline_status_update(current_pr_merges, build_info, build_status, "in_progress", pipeline_name)
                    last_status = current_status
                else:
                    print(f"⏳ Build still running... ({elapsed_minutes:.1f} minutes elapsed)")
                    if phase2_start_time is not None:
                        phase2_elapsed_minutes = (time.time() - phase2_start_time) / 60
                        print(f"   Phase 2 elapsed: {phase2_elapsed_minutes:.1f} minutes")
                    print(f"   Status: {current_status}")
                    if last_status != current_status:
                        last_status = current_status
        
            if build_is_running:
                # Show the actual wait time based on Phase 2 elapsed time
                if phase2_start_time is not None:
                    phase2_elapsed_minutes = (time.time() - phase2_start_time) / 60
                    if phase2_elapsed_minutes >= 30:
                        print(f"🔄 Waiting 2 minutes before next check...")
                    else:
                        print(f"🔄 Waiting 10 minutes before next check...")
                else:
                    print(f"🔄 Waiting 10 minutes before next check...")
            else:
                print(f"🔄 Waiting 30 seconds before next check...")
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            print(f"   Elapsed time: {elapsed_time / 60:.1f} minutes")
            print(f"   Retrying in 30 seconds...")
            import traceback
            traceback.print_exc()
            time.sleep(30)
            continue  # Continue the loop instead of exiting
    
    print("⏰ Monitoring timeout reached")
    return None, None

def automated_deployment_workflow(pr_merges, build_info, approver_email=None, run_in_background=True, pipeline_name="DEPLOYMENT", branch=None, tag_info=None):
    """Complete automated deployment workflow"""
    print("=== AUTOMATED DEPLOYMENT WORKFLOW ===")
    print(f"🚀 Starting automated deployment for {len(pr_merges)} PRs")
    print(f"📋 Build ID: {build_info['build_id']}")
    print(f"🔢 Build Number: {build_info['build_number']}")
    print(f"🔧 Pipeline: {pipeline_name}")
    if branch:
        print(f"🌿 Branch: {branch}")
    if tag_info:
        print(f"🏷️  Tag: {tag_info.get('tag_name', 'N/A')}")
    print()
    
    # Use the initial PR list throughout the deployment
    current_pr_merges = pr_merges.copy() if pr_merges else []
    
    print(f"📱 Step 1: Sending approval request to Teams with {len(current_pr_merges)} PR(s)...")
    if send_teams_approval_request(TEAMS_WEBHOOK_URL, current_pr_merges, build_info, approver_email, pipeline_name):
        print("✅ Approval request sent successfully!")
    else:
        print("❌ Failed to send approval request")
        return False
    
    if run_in_background:
        print()
        print("🔄 Step 2: Starting background monitoring...")
        print("   • Monitoring will continue in background")
        print("   • Status updates will be posted to Teams automatically")
        print("   • You can continue with other tasks")
        print()
        
        def background_monitoring():
            try:
                print("🔄 Background monitoring thread started...")
                success, final_status = monitor_deployment_progress(current_pr_merges, build_info, pipeline_name=pipeline_name, branch=branch, tag_info=tag_info)
                if success:
                    print("🎉 Background monitoring: Deployment completed successfully!")
                elif success is False:
                    print("❌ Background monitoring: Deployment failed!")
                else:
                    print("⏰ Background monitoring: Deployment timed out!")
            except Exception as e:
                print(f"❌ Background monitoring error: {e}")
                import traceback
                traceback.print_exc()
        
        monitor_thread = threading.Thread(target=background_monitoring, daemon=False)
        monitor_thread.start()
        
        print("✅ Background monitoring started successfully!")
        print("📱 Teams will receive updates automatically as deployment progresses")
        return True
    else:
        print()
        print("⏳ Step 2: Monitoring for approval and deployment progress...")
        print("   (This will automatically send updates to Teams)")
        print()
        
        success, final_status = monitor_deployment_progress(current_pr_merges, build_info, pipeline_name=pipeline_name, branch=branch, tag_info=tag_info)
        
        if success:
            print("🎉 Deployment workflow completed successfully!")
            return True
        elif success is False:
            print("❌ Deployment workflow failed!")
            return False
        else:
            print("⏰ Deployment workflow timed out!")
            return False

# ============================================================================
# MAIN WORKFLOW FUNCTIONS
# ============================================================================

def generate_deployment_message(build_info, pr_merges, new_build_info=None):
    """Generate the deployment message in the requested format"""
    print("\n" + "="*60)
    
    if not pr_merges:
        print("🚀 NO NEW DEPLOYMENT NEEDED")
        print("="*60)
        print("No new PRs have been merged since the last build.")
        print("The current build is up to date with the latest changes.")
        print()
        print("="*60)
    else:
        # Check if this is a custom branch deployment
        is_custom = pr_merges and pr_merges[0].get('jira_ticket') == 'CUSTOM'
        
        if is_custom:
            print("🚀 CUSTOM BRANCH DEPLOYMENT TRIGGERED")
            print("="*60)
            print("A manual deployment has been triggered for a custom branch:")
        else:
            print("🚀 DEPLOYMENT TO DEV TRIGGERED")
            print("="*60)
            print("The following merged PRs have been getting deployed to the development environment:")
        
        print()
        
        for pr in pr_merges:
            if pr['jira_ticket']:
                print(f"{pr['jira_ticket']} [Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})")
            else:
                print(f"[Merkle]: {pr['description']} – {pr['author']} (PR {pr['pr_number']})")
        
        print()
        
        if new_build_info:
            print(f"Build Status: https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={new_build_info['build_id']}&view=results")
            print(f"New Build Number: {new_build_info['build_number']}")
        else:
            print(f"Build Status: https://mpcoderepo.visualstudio.com/DigitalExperience/_build/results?buildId={build_info['build_id']}&view=results")
        
        print("Estimated Completion Time: ~30 minutes")
        print("="*60)
    
    print(f"\n📊 Build Information:")
    print(f"   Build Number: {build_info['build_number']}")
    print(f"   Build ID: {build_info['build_id']}")
    print(f"   Source Commit: {build_info['source_version'][:8]}")
    print(f"   Started: {build_info['start_time']}")
    print(f"   Total PRs in this deployment: {len(pr_merges)}")
    
    if new_build_info:
        print(f"   New Build Triggered: {new_build_info['build_number']} (ID: {new_build_info['build_id']})")

def main_deployment_workflow(custom_branch=None):
    """Main deployment workflow for DEV pipeline - fetches build info, triggers build, sends messages"""
    print("=== DEV Pipeline Deployment Automation ===")
    
    # DEV pipeline configuration
    def_id = BUILD_DEFINITION_ID  # Always 3274 for DEV
    branch = custom_branch or BRANCH  # Use custom branch if provided, otherwise default to "dev"
    pipeline_name = "DEV"
    
    print(f"Using Pipeline: {pipeline_name} (Definition ID: {def_id})")
    print(f"Using Branch: {branch}")
    print()
    
    print("Fetching last build information and PR merges...")
    print()
    
    if custom_branch:
        print(f"🚀 Custom branch provided: {custom_branch}")
        print(f"🔍 Skipping PR checks and triggering build immediately...")
        
        # Get baseline build info for monitoring
        build_info = get_last_build_info(def_id, include_in_progress=False)
        if not build_info:
            build_info = {
                'build_number': 'Initial',
                'build_id': '0',
                'source_version': 'latest',
                'start_time': datetime.now().isoformat()
            }
        
        baseline_commit = build_info['source_version']
        
        # Trigger build immediately
        new_build_info = trigger_new_build(def_id, custom_branch)
        if not new_build_info:
            print("❌ Failed to trigger build for custom branch")
            sys.exit(1)
            
        print(f"✅ Build {new_build_info['build_number']} triggered for branch '{custom_branch}'")
        
        # Create a dummy PR list for the message/monitoring
        pr_merges = [{
            'jira_ticket': 'CUSTOM',
            'description': f'Manual deployment of branch: {custom_branch}',
            'author': 'User',
            'pr_number': 'N/A',
            'commit_hash': 'N/A'
        }]
    else:
        # Get the last successful/completed build to use as baseline
        print("🔍 Checking for last successful build...")
        build_info = get_last_build_info(def_id, include_in_progress=False)
        
        if not build_info:
            print("❌ Failed to get build information")
            sys.exit(1)
        
        print(f"✅ Using last successful build: {build_info['build_number']} (ID: {build_info['build_id']})")
        print(f"   Status: {build_info.get('status', 'completed')}")
        print(f"   Result: {build_info.get('result', 'N/A')}")
        print()
        
        # For DEV pipeline: Find the commit on 'dev' branch that matches the build's deployment time
        # This ensures we use the actual deployed commit, not just the build's source commit
        baseline_commit = build_info['source_version']  # Default: commit from last successful build
        
        print(f"🔍 Finding baseline commit on '{branch}' branch...")
        print(f"   Build commit: {baseline_commit[:8]}")
        
        # First verify if the build commit exists on dev branch
        print(f"   Verifying if build commit {baseline_commit[:8]} exists on '{branch}' branch...")
        commit_exists = verify_commit_on_branch(baseline_commit, branch, REPOSITORY_NAME)
        
        if commit_exists:
            print(f"✅ Build commit {baseline_commit[:8]} EXISTS on '{branch}' branch")
        else:
            print(f"⚠️  Build commit {baseline_commit[:8]} NOT FOUND on '{branch}' branch")
            print(f"   This can happen if the build was from a different branch")
        
        # If build commit exists on dev branch, use it directly (most accurate)
        # If it doesn't exist, check if there are any new commits on dev branch
        if commit_exists:
            print(f"✅ Using build commit {baseline_commit[:8]} directly (exists on '{branch}' branch)")
            print(f"   This is the most accurate baseline for PR detection")
            
            # DEBUG: Check if build commit is the latest on dev branch
            print(f"\n🔍 Checking if build commit is the latest on '{branch}' branch...")
            latest_commit = get_latest_commit_from_branch(branch, REPOSITORY_NAME)
            if latest_commit:
                print(f"   Latest commit on '{branch}' branch: {latest_commit[:8]}")
                print(f"   Build commit: {baseline_commit[:8]}")
                if latest_commit == baseline_commit:
                    print(f"   ✅ Build commit IS the latest on '{branch}' branch - no new PRs to deploy")
                    print()
                    print("="*60)
                    print("🚀 NO NEW DEPLOYMENT NEEDED")
                    print("="*60)
                    print("Build commit is the latest on dev branch.")
                    print("No new PRs to deploy.")
                    print("="*60)
                    sys.exit(0)
                else:
                    print(f"   ⚠️  Build commit is NOT the latest - there are new commits on '{branch}' branch")
        else:
            # Build commit doesn't exist on dev branch - check if there are new commits
            print(f"⚠️  Build commit {baseline_commit[:8]} not found on '{branch}' branch")
            print(f"   This means the build was from a different branch or state")
            print(f"   Checking if there are any new commits on '{branch}' branch...")
            
            # Get latest commit from dev branch to see if there are any new changes
            latest_commit = get_latest_commit_from_branch(branch, REPOSITORY_NAME)
            if latest_commit:
                # Check if there are any commits after the build commit (even if build commit doesn't exist on dev)
                # This will tell us if there are new PRs to deploy
                print(f"   Latest commit on '{branch}' branch: {latest_commit[:8]}")
                print(f"   Since build commit not found on '{branch}' branch, no valid baseline exists")
                print(f"   No new PRs to deploy.")
                print()
                print("="*60)
                print("🚀 NO NEW DEPLOYMENT NEEDED")
                print("="*60)
                print("Build commit not found on dev branch.")
                print("No new PRs to deploy.")
                print("="*60)
                sys.exit(0)
            else:
                print(f"⚠️  Could not get latest commit from '{branch}' branch")
                print(f"   No new PRs to deploy.")
                print()
                print("="*60)
                print("🚀 NO NEW DEPLOYMENT NEEDED")
                print("="*60)
                print("Build commit not found on dev branch.")
                print("No new PRs to deploy.")
                print("="*60)
                sys.exit(0)
        
        print(f"✅ Using build as baseline: {build_info['build_number']} (ID: {build_info['build_id']})")
        print(f"   Source commit: {build_info['source_version'][:8]}")
        print(f"   Baseline commit for PR detection: {baseline_commit[:8]}")
        print(f"   Build status: {build_info.get('status', 'completed')}")
        print(f"   Pipeline: {pipeline_name}")
        print(f"   Branch for PR detection: {branch}")
        print()
        
        print(f"🔍 Checking for PRs merged after commit {baseline_commit[:8]} on '{branch}' branch...")
        pr_merges = get_pr_merges_after_commit(baseline_commit, branch)
        if pr_merges is None:
            print("❌ Failed to get PR merges")
            sys.exit(1)
        
        print(f"✅ Found {len(pr_merges)} PRs merged after build")
        
        # Debug: Show first few PRs to verify they're correct
        if pr_merges:
            print(f"\n📋 First 10 PRs detected (with commit hashes):")
            for i, pr in enumerate(pr_merges[:10], 1):
                print(f"   {i}. PR #{pr['pr_number']}: {pr.get('jira_ticket', 'N/A')} - {pr['description'][:50]}... (commit: {pr['commit_hash']})")
            if len(pr_merges) > 10:
                print(f"   ... and {len(pr_merges) - 10} more PRs")
            
            # Show last few PRs to see the range
            if len(pr_merges) > 10:
                print(f"\n📋 Last 5 PRs detected:")
                for i, pr in enumerate(pr_merges[-5:], len(pr_merges) - 4):
                    print(f"   {i}. PR #{pr['pr_number']}: {pr.get('jira_ticket', 'N/A')} - {pr['description'][:50]}... (commit: {pr['commit_hash']})")
        
        # DEV pipeline doesn't create tags - just trigger build with branch
        new_build_info = None
        if pr_merges:
            print(f"\n🔄 New changes detected! Triggering new build...")
            new_build_info = trigger_new_build(def_id, branch)
            if new_build_info:
                print(f"✅ New build {new_build_info['build_number']} triggered successfully!")
            else:
                print(f"⚠️  Failed to trigger new build, will use existing build link")
    
    generate_deployment_message(build_info, pr_merges, new_build_info)
    
    # Always start monitoring if a new build was triggered, or if there are PRs to deploy
    should_monitor = new_build_info is not None or pr_merges
    
    if should_monitor:
        print(f"\n📱 Starting automated deployment workflow...")
        print("   This will automatically:")
        print("   • Send approval request to Teams")
        print("   • Monitor deployment progress")
        print("   • Post status updates automatically")
        print("   • Notify when deployment completes")
        
        # Determine which build to monitor
        # Store baseline commit for PR detection (use the baseline_commit we determined earlier)
        baseline_commit_for_prs = baseline_commit
        
        if new_build_info:
            print(f"✅ Using NEW build for monitoring: {new_build_info['build_number']} (ID: {new_build_info['build_id']})")
            print(f"   Baseline commit for PR detection: {baseline_commit_for_prs[:8] if baseline_commit_for_prs else 'N/A'}")
            
            print("🔍 Fetching dynamic build details from Azure DevOps...")
            dynamic_build_info = get_build_status_dynamic(new_build_info['build_id'])
            
            if dynamic_build_info:
                current_build_info = {
                    'build_number': new_build_info['build_number'],
                    'build_id': new_build_info['build_id'],
                    'source_version': dynamic_build_info.get('source_version', 'latest'),
                    'start_time': dynamic_build_info.get('start_time', new_build_info.get('start_time')),
                    'result': dynamic_build_info.get('result'),
                    'status': dynamic_build_info.get('status'),
                    'baseline_commit': baseline_commit_for_prs  # Store original baseline for PR detection
                }
                print(f"✅ Dynamic build info retrieved: {current_build_info['source_version'][:8] if current_build_info['source_version'] != 'latest' else 'latest'}")
            else:
                current_build_info = {
                    'build_number': new_build_info['build_number'],
                    'build_id': new_build_info['build_id'],
                    'source_version': 'latest',
                    'start_time': new_build_info.get('start_time', build_info['start_time']),
                    'baseline_commit': baseline_commit_for_prs  # Store original baseline for PR detection
                }
                print("⚠️  Using fallback build info")
        else:
            print(f"✅ Using existing build for monitoring: {build_info['build_number']} (ID: {build_info['build_id']})")
            current_build_info = build_info.copy()
            current_build_info['baseline_commit'] = baseline_commit_for_prs  # Ensure baseline is set
        
        # Use empty list if no PRs (for monitoring purposes)
        prs_for_monitoring = pr_merges if pr_merges else []
        
        print("\n🚀 Launching automated monitoring...")
        
        def run_monitoring():
            """Monitoring thread function - ensures it stays alive and handles errors"""
            try:
                print("🔄 Monitoring thread started...")
                success = automated_deployment_workflow(prs_for_monitoring, current_build_info, approver_email=None, run_in_background=False, pipeline_name=pipeline_name, branch=branch, tag_info=None)
                if success:
                    print("✅ Automated deployment workflow completed successfully!")
                elif success is False:
                    print("❌ Automated deployment workflow failed!")
                else:
                    print("⏰ Automated deployment workflow timed out!")
            except KeyboardInterrupt:
                print("\n⏹️  Monitoring thread interrupted by user")
            except Exception as e:
                print(f"❌ Monitoring thread error: {e}")
                import traceback
                traceback.print_exc()
                print("⚠️  Monitoring thread encountered an error but will continue...")
            finally:
                print("🔄 Monitoring thread finished")
        
        # Create thread with daemon=False so it stays alive even if main exits
        monitor_thread = threading.Thread(target=run_monitoring, daemon=False, name="DeploymentMonitor")
        monitor_thread.start()
        
        print("✅ Monitoring thread started successfully!")
        print("🔄 Background monitoring is running. Main process will keep it alive...")
        print("📱 Monitoring will send Teams messages automatically.")
        print("⏹️  Press Ctrl+C to stop monitoring.")
        print()
        
        # Keep main process alive to ensure thread stays intact
        try:
            while monitor_thread.is_alive():
                time.sleep(10)  # Check every 10 seconds
                # Don't spam console, only log occasionally
                if int(time.time()) % 60 == 0:  # Every minute
                    print(f"🔄 Monitoring active... Build ID: {current_build_info['build_id']}")
            
            print("✅ Monitoring thread completed successfully!")
            print("📱 Main process exiting...")
        except KeyboardInterrupt:
            print("\n⏹️  Interrupted by user - waiting for monitoring thread to finish...")
            # Give thread a moment to clean up
            monitor_thread.join(timeout=5)
            if monitor_thread.is_alive():
                print("⚠️  Monitoring thread still running - it will continue in background")
            else:
                print("✅ Monitoring thread finished cleanly")
            print("✅ Main process exiting...")
    elif not pr_merges and not new_build_info:
        print(f"\n📱 No new PRs to deploy and no build triggered - skipping Teams notification")
    
    if new_build_info:
        print(f"\n🎯 Deployment message generated successfully!")
        print(f"   Based on build: {build_info['build_number']}")
        print(f"   New build triggered: {new_build_info['build_number']}")
        print(f"   PRs included: {len(pr_merges)}")
    else:
        print(f"\n🎯 Deployment message generated successfully!")
        print(f"   Based on build: {build_info['build_number']}")
        print(f"   PRs included: {len(pr_merges)}")

# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    """Main entry point with command-line interface"""
    parser = argparse.ArgumentParser(
        description='DEV Pipeline Deployment Automation Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full DEV pipeline deployment workflow (default)
  python3 deployment_dev.py

  # Send approval request only
  python3 deployment_dev.py --approval --approver-email user@company.com

  # Send deployment confirmation
  python3 deployment_dev.py --deployment

  # Send approved message
  python3 deployment_dev.py --approved --approver-name "John Doe"

  # Send build triggered message
  python3 deployment_dev.py --build-triggered

  # Monitor specific build
  python3 deployment_dev.py --monitor --build-id 123456

  # Test PR detection (uses latest build commit)
  python3 deployment_dev.py --test-prs

  # Test PR detection with specific commit
  python3 deployment_dev.py --test-prs --commit a3cb1499
        """
    )
    
    parser.add_argument('--approval', action='store_true', help='Send approval request to Teams')
    parser.add_argument('--deployment', action='store_true', help='Send deployment confirmation to Teams')
    parser.add_argument('--approved', action='store_true', help='Send approved message to Teams')
    parser.add_argument('--build-triggered', action='store_true', help='Send build triggered message to Teams')
    parser.add_argument('--monitor', action='store_true', help='Monitor deployment progress')
    parser.add_argument('--approver-email', type=str, help='Email of person to tag for approval')
    parser.add_argument('--approver-name', type=str, help='Name of person who approved')
    parser.add_argument('--build-id', type=str, help='Build ID to monitor (for --monitor only)')
    # DEV pipeline script - no pipeline argument needed
    parser.add_argument('--no-background', action='store_true', help='Run monitoring in foreground (blocking)')
    parser.add_argument('--test-prs', action='store_true', help='Test PR detection - shows PRs merged after a commit')
    parser.add_argument('--commit', type=str, help='Commit hash to check PRs after (for --test-prs)')
    parser.add_argument('--branch', type=str, help='Custom branch to deploy or test (source code branch)')
    
    args = parser.parse_args()
    
    # Test PR detection mode
    if args.test_prs:
        print("="*60)
        print("🧪 TESTING PR DETECTION")
        print("="*60)
        
        # DEV pipeline configuration
        def_id = BUILD_DEFINITION_ID  # Always 3274 for DEV
        branch = args.branch or BRANCH  # Use custom branch if provided, otherwise default to "dev"
        pipeline_name = "DEV"
        
        print(f"\n📋 Configuration:")
        print(f"   Pipeline: {pipeline_name}")
        print(f"   Definition ID: {def_id}")
        print(f"   Branch: {branch}")
        
        # Get commit hash
        if args.commit:
            commit_hash = args.commit
            print(f"\n🔍 Using provided commit: {commit_hash[:8]}")
        else:
            # Get latest build to use its commit
            print(f"\n🔍 Getting latest build for {pipeline_name} pipeline...")
            latest_build = get_last_build_info(def_id, include_in_progress=False)
            if not latest_build:
                print("❌ Failed to get latest build")
                sys.exit(1)
            commit_hash = latest_build.get('source_version')
            print(f"✅ Found latest build: {latest_build['build_number']}")
            print(f"   Build ID: {latest_build['build_id']}")
            print(f"   Commit: {commit_hash[:8]}")
        
        print(f"\n" + "="*60)
        print(f"🔍 TEST 1: Checking PRs merged after commit {commit_hash[:8]} on '{branch}' branch...")
        print("="*60)
        
        prs_1 = get_pr_merges_after_commit(commit_hash, branch)
        if prs_1 is None:
            print("❌ Failed to get PRs")
            sys.exit(1)
        
        print(f"\n📊 RESULT 1:")
        print(f"   Found {len(prs_1)} PR(s)")
        for i, pr in enumerate(prs_1, 1):
            if pr.get('jira_ticket'):
                print(f"   {i}. {pr['jira_ticket']}: {pr['description']} (PR #{pr['pr_number']})")
            else:
                print(f"   {i}. {pr['description']} (PR #{pr['pr_number']})")
        
        print(f"\n" + "="*60)
        print(f"🔄 TEST 2: Refreshing PRs (checking again)...")
        print("="*60)
        
        import time
        print("   Waiting 2 seconds...")
        time.sleep(2)
        
        prs_2 = get_pr_merges_after_commit(commit_hash, branch)
        if prs_2 is None:
            print("❌ Failed to refresh PRs")
            sys.exit(1)
        
        print(f"\n📊 RESULT 2:")
        print(f"   Found {len(prs_2)} PR(s)")
        for i, pr in enumerate(prs_2, 1):
            if pr.get('jira_ticket'):
                print(f"   {i}. {pr['jira_ticket']}: {pr['description']} (PR #{pr['pr_number']})")
            else:
                print(f"   {i}. {pr['description']} (PR #{pr['pr_number']})")
        
        print(f"\n" + "="*60)
        print(f"📈 COMPARISON:")
        print("="*60)
        if len(prs_1) == len(prs_2):
            print(f"✅ PR count matches: {len(prs_1)} PRs")
            # Check if PRs are identical
            pr_numbers_1 = {pr['pr_number'] for pr in prs_1}
            pr_numbers_2 = {pr['pr_number'] for pr in prs_2}
            if pr_numbers_1 == pr_numbers_2:
                print("✅ PR list is identical - no new PRs detected")
            else:
                print("⚠️  PR list differs!")
                new_prs = pr_numbers_2 - pr_numbers_1
                removed_prs = pr_numbers_1 - pr_numbers_2
                if new_prs:
                    print(f"   New PRs: {new_prs}")
                if removed_prs:
                    print(f"   Removed PRs: {removed_prs}")
        else:
            print(f"⚠️  PR count changed: {len(prs_1)} → {len(prs_2)}")
            if len(prs_2) > len(prs_1):
                print(f"   ✅ Found {len(prs_2) - len(prs_1)} new PR(s)!")
            else:
                print(f"   ⚠️  PR count decreased (unexpected)")
        
        print(f"\n" + "="*60)
        print(f"✅ Test completed!")
        print("="*60)
        return
    
    # If no specific action, run full workflow
    if not any([args.approval, args.deployment, args.approved, args.build_triggered, args.monitor]):
        main_deployment_workflow(custom_branch=args.branch)
        return
    
    # Sample data for testing individual functions
    sample_pr_merges = [
        {
            'jira_ticket': 'ADW-3088',
            'description': 'Add inline display for PDF and Office documents in mandg.vhost configuration',
            'author': 'Rahate, Gaurav',
            'pr_number': '120290'
        },
        {
            'jira_ticket': 'ADW-1051',
            'description': 'TestCases Updated for the TeaserCardsImpl',
            'author': 'Venati, Rohith',
            'pr_number': '120267'
        },
        {
            'jira_ticket': 'ADW-1632',
            'description': 'Header Fixes',
            'author': 'Kumar, Vignesh',
            'pr_number': '120284'
        }
    ]
    
    sample_build_info = {
        'build_number': '20251009.1',
        'build_id': '1136149',
        'source_version': 'abc123def456',
        'start_time': '2025-01-09T10:30:00Z'
    }
    
    if args.approval:
        print("🔔 Sending deployment approval request to Teams...")
        send_teams_approval_request(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, args.approver_email)
    
    elif args.deployment:
        print("🚀 Sending deployment confirmation to Teams...")
        send_teams_deployment_confirmation(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info)
    
    elif args.approved:
        print("✅ Sending approved message to Teams...")
        send_teams_approved_message(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, args.approver_name)
    
    elif args.build_triggered:
        print("🚀 Sending build triggered message to Teams...")
        new_build_info = {
            'build_number': '20251009.2',
            'build_id': '1136150'
        }
        send_teams_build_triggered_message(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, new_build_info)
    
    elif args.monitor:
        if args.build_id:
            # Get actual build info for the provided build ID
            build_info_dynamic = get_build_status_dynamic(args.build_id)
            if build_info_dynamic:
                build_info = {
                    'build_id': args.build_id,
                    'build_number': build_info_dynamic.get('build_number', 'Unknown'),
                    'source_version': build_info_dynamic.get('source_version', 'unknown')
                }
            else:
                build_info = {
                    'build_id': args.build_id,
                    'build_number': 'Unknown',
                    'source_version': 'unknown'
                }
            
            # DEV pipeline configuration
            def_id = BUILD_DEFINITION_ID  # Always 3274 for DEV
            branch = args.branch or BRANCH  # Use custom branch if provided, otherwise default to "dev"
            pipeline_name = "DEV"
            
            print(f"🔍 Monitoring build {args.build_id}...")
            print(f"   Pipeline: {pipeline_name} (Definition ID: {def_id})")
            print(f"   Branch: {branch}")
            success, status = monitor_deployment_progress(sample_pr_merges, build_info, pipeline_name=pipeline_name, branch=branch)
            if success:
                print("✅ Monitoring completed successfully!")
            else:
                print("❌ Monitoring failed!")
        else:
            print("❌ Please provide --build-id when using --monitor")
            sys.exit(1)

if __name__ == "__main__":
    main()

