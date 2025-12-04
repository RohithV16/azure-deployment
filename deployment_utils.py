#!/usr/bin/env python3
"""
Shared Utility Functions for Deployment Scripts
Contains common logic for Azure DevOps interactions, Git operations, and Teams messaging.
"""

import requests
import json
import os
import sys
import base64
import time
import argparse
import threading
from datetime import datetime, timezone

# ============================================================================
# CONFIGURATION
# ============================================================================

# Azure DevOps configuration
ORG_URL = "https://mpcoderepo.visualstudio.com"
PROJECT = "DigitalExperience"
REPOSITORY_NAME = "aemaacs-life"

# Webhook URLs
TEAMS_WEBHOOK_URL = "https://aegisdentsunetwork.webhook.office.com/webhookb2/c448e610-8c38-45ad-a939-db5a4ece46d5@6e8992ec-76d5-4ea5-8eae-b0c5e558749a/IncomingWebhook/0dc0e4fca542427fb3d6a02281a88574/d881b4fa-b65f-4e61-bb1a-b48354c99b1c/V2WHmoL-a3Tw0P84hKNYK4FI_U6TSWBShEDdqyLnsn9p41"
POWER_AUTOMATE_WEBHOOK_URL = "https://default6e8992ec76d54ea58eaeb0c5e55874.9a.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/1c9b143d398747a6892388f31a230f87/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=tzPM2LVcleQ3UCpAWZG46rQ7-3W5qtXOgrTjAHHYIcw"

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
                            # print(f"✅ Found repository: {repo_name} (ID: {repo_id})")
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

def get_last_build_info(definition_id, include_in_progress=False, require_fullstack=False):
    """
    Get the last successful build information from Azure DevOps
    
    Args:
        definition_id (str): The build definition ID
        include_in_progress (bool): Whether to include in-progress builds
        require_fullstack (bool): Whether to filter for 'Full Stack' deployment type (for DEV pipeline)
    """
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    builds_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds?definitions={definition_id}&api-version=7.0&$top=200"
    
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
                    
                    # Collect successful builds
                    if build_result in ['succeeded', 'partiallySucceeded']:
                        # Check templateParameters for deploymentType: Full Stack if required
                        if require_fullstack:
                            template_params = build.get('templateParameters', {})
                            deployment_type = template_params.get('deploymentType', '')
                            
                            if deployment_type == 'Full Stack':
                                valid_builds.append(build)
                            else:
                                # Skip non-fullstack builds
                                pass
                        else:
                            valid_builds.append(build)
                    
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
        # print(f"🔍 Checking build status for ID: {build_id}")
        response = requests.get(build_url, headers=headers)
        
        if response.status_code in [200, 202]:
            build_data = response.json()
            status_info = {
                'status': build_data.get('status'),
                'result': build_data.get('result'),
                'build_number': build_data.get('buildNumber'),
                'finish_time': build_data.get('finishTime'),
                'start_time': build_data.get('startTime')
            }
            # print(f"✅ Build status retrieved: {status_info['status']} - {status_info['result']}")
            return status_info
        else:
            print(f"❌ Failed to get build status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting build status: {e}")
        return None

def trigger_new_build(definition_id, branch=None, tag=None):
    """Trigger a new build for specified definition and branch or tag"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Determine source reference
    if tag:
        # Use tag reference format: refs/tags/tag-name
        source_ref = tag if tag.startswith("refs/tags/") else f"refs/tags/{tag}"
        source_display = tag.replace("refs/tags/", "")
        source_type = "tag"
    else:
        # Get branch
        if not branch:
            print("❌ Branch not specified for build trigger")
            return None
        
        # Ensure branch format is correct
        if not branch.startswith("refs/heads/"):
            source_ref = f"refs/heads/{branch}"
        else:
            source_ref = branch
        source_display = branch.replace("refs/heads/", "")
        source_type = "branch"
    
    build_payload = {
        "definition": {
            "id": int(definition_id)
        },
        "sourceBranch": source_ref
    }
    
    trigger_url = f"{ORG_URL}/{PROJECT}/_apis/build/builds?api-version=7.0"
    
    try:
        pipeline_name = "DEV" if str(definition_id) == "3274" else "STAGE" if str(definition_id) == "3308" else f"Definition {definition_id}"
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

# ============================================================================
# GIT FUNCTIONS
# ============================================================================

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
        
        # print(f"   Baseline commit date: {baseline_commit_date}")
        
        # Get all commits from dev branch (without fromCommitId filter, as it's unreliable)
        # We'll filter by date instead
        commits_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/commits"
        params = {
            "searchCriteria.itemVersion.version": branch_name,
            "searchCriteria.itemVersion.versionType": "branch",
            "api-version": "7.0",
            "$top": 100  # Get top 100 commits to ensure we capture all recent PRs
        }
        
        # print(f"   API params: branch={branch_name}, top=100 (filtering by date)")
        
        commits_response = requests.get(commits_url, headers=headers, params=params)
        
        if commits_response.status_code != 200:
            print(f"❌ Failed to get commits: {commits_response.status_code}")
            print(f"Response: {commits_response.text}")
            return None
        
        commits_data = commits_response.json()
        commits = commits_data.get('value', [])
        
        # Filter commits to only include those AFTER the baseline commit
        # We need to compare commit dates to ensure we only get newer commits
        commits_after = []
        if baseline_commit_date:
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
        # This webhook expects a full Adaptive Card payload with an 'attachments' array
        
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
    
    # Use provided approver email or default list
    # Fixed: Removed hardcoded emails, using a placeholder or argument
    if approver_email:
        approvers_text = f"<at>{approver_email}</at>"
    else:
        # Default placeholder if no specific approver provided
        approvers_text = "Approvers"
    
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

**{approvers_text}** - Please review and approve the deployment to {env_name} environment on Azure DevOps.

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
    
    # Use TEAMS_WEBHOOK_URL for confirmation messages
    return send_teams_message(webhook_url, deployment_message.strip())

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
    
    # Use TEAMS_WEBHOOK_URL for approved messages
    return send_teams_message(webhook_url, approved_message.strip())

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
    
    # Use TEAMS_WEBHOOK_URL for triggered messages
    return send_teams_message(webhook_url, build_triggered_message.strip())

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

def send_deployment_completed_message(pr_merges, build_info, final_build_status, status_type="succeeded"):
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
    
    return send_teams_message(target_webhook, deployment_completed_message.strip())

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
    # Note: BRANCH constant is not available here, so we rely on the passed argument
    if not branch:
        branch = "dev"  # Default fallback
    
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
                    print("🚀 Build is now running - sending triggered message...")
                    print(f"   Previous status: {last_status}")
                    print(f"   Current status: {current_status}")
                    print(f"   PRs in this deployment: {len(current_pr_merges)}")
                    success = send_pipeline_status_update(current_pr_merges, build_info, build_status, "triggered", pipeline_name)
                    if success:
                        print("✅ Pipeline triggered message sent successfully!")
                    else:
                        print("❌ Failed to send pipeline triggered message")
                    triggered_sent = True
                    build_is_running = True
                    phase2_start_time = time.time()  # Track when Phase 2 starts
                    last_status = current_status
                    print("🔄 Switching to Phase 2: Monitoring every 10 minutes for first 30 minutes, then every 2 minutes")
                else:
                    print(f"⏳ Waiting for build to start running... ({elapsed_minutes:.1f} minutes elapsed)")
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
