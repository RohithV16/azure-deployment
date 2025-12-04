#!/usr/bin/env python3
"""
Azure DevOps Deployment Automation Script - STAGE Pipeline
"""

import os
import sys
import argparse
import time

# Auto-activate virtual environment if not already active
def activate_virtual_env():
    """Activate virtual environment if not already running in one"""
    # Check if we are already in a venv
    if sys.prefix != sys.base_prefix:
        return

    # Look for venv in common locations
    venv_locations = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv'),
        os.path.join(os.getcwd(), 'venv'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv'),
        os.path.join(os.getcwd(), '.venv')
    ]

    for venv_path in venv_locations:
        if os.path.exists(venv_path):
            activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
            python_bin = os.path.join(venv_path, 'bin', 'python')
            
            if os.path.exists(python_bin):
                # Re-execute the script with the venv python
                os.execv(python_bin, [python_bin] + sys.argv)

activate_virtual_env()

# Import shared utilities
try:
    from deployment_utils import *
except ImportError:
    # If running from a different directory, try to add the script directory to path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from deployment_utils import *

# Configuration for STAGE pipeline
BUILD_DEFINITION_ID = "3308"
BRANCH = "master"
PIPELINE_NAME = "STAGE"

def main_deployment_workflow():
    """Main workflow for STAGE deployment"""
    print(f"🚀 Starting {PIPELINE_NAME} Deployment Workflow...")
    print(f"   Definition ID: {BUILD_DEFINITION_ID}")
    print(f"   Branch: {BRANCH}")
    
    # 1. Get last successful build (No special filter for STAGE)
    print("\n🔍 Step 1: Getting last successful build...")
    last_build = get_last_build_info(BUILD_DEFINITION_ID)
    
    if not last_build:
        print("❌ Could not find a previous successful build.")
        sys.exit(1)
        
    print(f"   Last successful build: {last_build['build_number']} (ID: {last_build['build_id']})")
    print(f"   Source Version: {last_build['source_version'][:8]}")
    
    # 2. Check for new PRs
    print(f"\n🔍 Step 2: Checking for new PRs after commit {last_build['source_version'][:8]}...")
    pr_merges = get_pr_merges_after_commit(last_build['source_version'], BRANCH)
    
    if pr_merges is None:
        print("❌ Failed to check for PRs.")
        sys.exit(1)
        
    if not pr_merges:
        generate_deployment_message(last_build, [])
        print("\n✅ System is up to date. No deployment needed.")
        return
    
    # 3. Create Release Tag
    print(f"\n🏷️  Step 3: Creating release tag for {len(pr_merges)} PRs...")
    tag_result = create_release_tag(pr_merges, branch=BRANCH)
    
    if not tag_result:
        print("❌ Failed to create release tag.")
        sys.exit(1)
        
    tag_name = tag_result['tag_name']
    
    # 4. Trigger Deployment
    print(f"\n🚀 Step 4: Initiating deployment for tag {tag_name}...")
    generate_deployment_message(last_build, pr_merges)
    
    # Trigger new build using the new tag
    new_build = trigger_new_build(BUILD_DEFINITION_ID, tag=f"refs/tags/{tag_name}")
    
    if not new_build:
        print("❌ Failed to trigger new build.")
        sys.exit(1)
        
    # 5. Run automated workflow (notifications + monitoring)
    monitoring_build_info = {
        'build_id': new_build['build_id'],
        'build_number': new_build['build_number'],
        'source_version': tag_result['commit_hash'],
        'baseline_commit': last_build['source_version']
    }
    
    automated_deployment_workflow(
        pr_merges, 
        monitoring_build_info,
        pipeline_name=PIPELINE_NAME,
        branch=BRANCH,
        tag_info=tag_result
    )

def main():
    parser = argparse.ArgumentParser(description='Azure DevOps Deployment Automation - STAGE Pipeline')
    parser.add_argument('--approval', action='store_true', help='Send approval request to Teams')
    parser.add_argument('--deployment', action='store_true', help='Send deployment confirmation to Teams')
    parser.add_argument('--approved', action='store_true', help='Send approved message to Teams')
    parser.add_argument('--build-triggered', action='store_true', help='Send build triggered message to Teams')
    parser.add_argument('--monitor', action='store_true', help='Monitor deployment progress')
    parser.add_argument('--build-id', help='Build ID for monitoring')
    parser.add_argument('--approver-email', help='Email of the approver')
    parser.add_argument('--approver-name', help='Name of the approver')
    
    args = parser.parse_args()
    
    # Sample data for testing individual functions
    sample_pr_merges = [
        {'jira_ticket': 'TEST-123', 'description': 'Test PR', 'author': 'Tester', 'pr_number': '1000'}
    ]
    sample_build_info = {'build_number': '20250101.1', 'build_id': '100000', 'source_version': 'abc1234', 'start_time': '2025-01-01T12:00:00Z'}
    
    if args.approval:
        print("🔔 Sending deployment approval request to Teams...")
        send_teams_approval_request(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, args.approver_email, PIPELINE_NAME)
    
    elif args.deployment:
        print("🚀 Sending deployment confirmation to Teams...")
        send_teams_deployment_confirmation(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info)
    
    elif args.approved:
        print("✅ Sending approved message to Teams...")
        send_teams_approved_message(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, args.approver_name)
    
    elif args.build_triggered:
        print("🚀 Sending build triggered message to Teams...")
        new_build_info = {'build_number': '20250101.2', 'build_id': '100001'}
        send_teams_build_triggered_message(TEAMS_WEBHOOK_URL, sample_pr_merges, sample_build_info, new_build_info)
    
    elif args.monitor:
        if args.build_id:
            # Get actual build info for the provided build ID
            build_info_dynamic = get_build_status_dynamic(args.build_id)
            if build_info_dynamic:
                build_info = build_info_dynamic
            else:
                build_info = {'build_id': args.build_id, 'build_number': 'Unknown', 'source_version': 'unknown'}
            
            print(f"🔍 Monitoring build {args.build_id}...")
            monitor_deployment_progress(sample_pr_merges, build_info, pipeline_name=PIPELINE_NAME, branch=BRANCH)
        else:
            print("❌ Please provide --build-id when using --monitor")
            sys.exit(1)
            
    else:
        # Default: Run full workflow
        main_deployment_workflow()

if __name__ == "__main__":
    main()
