#!/usr/bin/env python3
"""
Azure DevOps Deployment Automation Script - DEV Pipeline
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

# Configuration for DEV pipeline
BUILD_DEFINITION_ID = "3274"
BRANCH = "dev"
PIPELINE_NAME = "DEV"

def main_deployment_workflow():
    """Main workflow for DEV deployment"""
    print(f"🚀 Starting {PIPELINE_NAME} Deployment Workflow...")
    print(f"   Definition ID: {BUILD_DEFINITION_ID}")
    print(f"   Branch: {BRANCH}")
    
    # 1. Get last successful build (Full Stack only for DEV)
    print("\n🔍 Step 1: Getting last successful build...")
    last_build = get_last_build_info(BUILD_DEFINITION_ID, require_fullstack=True)
    
    if not last_build:
        print("❌ Could not find a previous successful build.")
        sys.exit(1)
        
    print(f"   Last successful build: {last_build['build_number']} (ID: {last_build['build_id']})")
    print(f"   Source Version: {last_build['source_version'][:8]}")
    
    # 2. Verify commit exists on branch
    print(f"\n🔍 Step 2: Verifying commit on '{BRANCH}' branch...")
    commit_hash = last_build['source_version']
    
    # Try to verify if the commit exists on the branch
    is_on_branch = verify_commit_on_branch(commit_hash, BRANCH)
    
    if not is_on_branch:
        print(f"⚠️  Commit {commit_hash[:8]} not found on {BRANCH} branch.")
        print("   This might happen if the branch was reset or squashed.")
        
        # Fallback: Find commit by date
        print("   Attempting to find closest commit by date...")
        closest_commit = find_commit_on_branch_by_date(last_build['start_time'], BRANCH)
        
        if closest_commit:
            print(f"   Using closest commit: {closest_commit[:8]}")
            commit_hash = closest_commit
        else:
            print("❌ Could not find a valid baseline commit.")
            sys.exit(1)
    else:
        print(f"✅ Commit {commit_hash[:8]} verified on {BRANCH} branch.")
    
    # 3. Check for new PRs
    print(f"\n🔍 Step 3: Checking for new PRs after commit {commit_hash[:8]}...")
    pr_merges = get_pr_merges_after_commit(commit_hash, BRANCH)
    
    if pr_merges is None:
        print("❌ Failed to check for PRs.")
        sys.exit(1)
        
    if not pr_merges:
        generate_deployment_message(last_build, [])
        print("\n✅ System is up to date. No deployment needed.")
        return
    
    # 4. Trigger Deployment
    print(f"\n🚀 Step 4: New changes detected ({len(pr_merges)} PRs). Initiating deployment...")
    generate_deployment_message(last_build, pr_merges)
    
    # Trigger new build
    new_build = trigger_new_build(BUILD_DEFINITION_ID, branch=BRANCH)
    
    if not new_build:
        print("❌ Failed to trigger new build.")
        sys.exit(1)
        
    # 5. Run automated workflow (notifications + monitoring)
    # We pass the NEW build info as the build to monitor
    # But for the initial "Approval Request", we usually show the OLD build info as "Current State" 
    # and the PRs that WILL be deployed.
    # However, since we just triggered the build, we can include the new build info.
    
    # Update build info with the new build details for monitoring
    monitoring_build_info = {
        'build_id': new_build['build_id'],
        'build_number': new_build['build_number'],
        'source_version': 'latest', # We don't know the exact commit yet until it starts
        'baseline_commit': commit_hash # Keep track of where we started
    }
    
    # Send approval request / notification
    # Note: In the original script, it seemed to send approval request BEFORE triggering?
    # Let's check the original flow.
    # Original: 
    # 1. Get PRs.
    # 2. automated_deployment_workflow(pr_merges, last_build)
    # Inside automated_deployment_workflow:
    #    - Send approval request
    #    - If background: start monitoring thread
    #    - Inside monitoring:
    #         - Wait for build to start (it assumes build is ALREADY triggered or will be triggered?)
    #         - Wait, the original script didn't trigger the build automatically in main_deployment_workflow?
    #         - Let's check line 2160 of original deployment_dev.py
    
    # Checking original deployment_dev.py...
    # It calls `automated_deployment_workflow(pr_merges, latest_build)`
    # It does NOT seem to trigger the build explicitly in `main_deployment_workflow`!
    # It seems it expects the USER to trigger it via the approval request link?
    # OR, `automated_deployment_workflow` triggers it?
    # Let's check `automated_deployment_workflow` in original.
    # It sends approval request.
    # Then it monitors.
    # It does NOT trigger.
    
    # Wait, if it doesn't trigger, how does the build start?
    # Maybe the "Approval Request" in Teams has a button? No, it says "Please approve this request directly on Azure DevOps pipeline".
    # This implies the pipeline is ALREADY running and waiting for approval?
    # OR, the user has to go and click "Run Pipeline"?
    
    # Let's look at `trigger_new_build` usage in original.
    # It is used in `deployment_stage.py`.
    # In `deployment_dev.py`, `trigger_new_build` is defined but... is it used?
    # Grepping usage...
    # It seems `deployment_dev.py` might NOT be triggering the build automatically?
    # Let's re-read `main_deployment_workflow` in `deployment_dev.py` (lines 2078+).
    # It calls `automated_deployment_workflow`.
    # It does NOT call `trigger_new_build`.
    
    # HOWEVER, the user's prompt says "Automates Azure DevOps pipeline deployments... Trigger new builds."
    # And `deployment_stage.py` definitely triggers.
    # Maybe `deployment_dev.py` is intended to monitor a build that is triggered by a commit (CI)?
    # "The user wants to understand how to enhance the deployment_dev.py script... Trigger new builds."
    
    # If I look at the `monitor_deployment_progress` logic:
    # "Phase 1: Checking every 30 seconds until build starts running"
    # This implies it waits for a build.
    
    # BUT, if I want to fully automate, I should probably trigger it if I detect changes?
    # The original script might have relied on CI triggers (commit to dev -> auto build).
    # If so, the script is just for notification/monitoring.
    
    # BUT, `deployment_stage.py` definitely triggers.
    # Let's assume for DEV, we might want to trigger it too if we are running this script manually?
    # Or maybe we just monitor.
    
    # Let's stick to the ORIGINAL behavior for now to be safe.
    # Original behavior: Detect PRs -> Send Approval Request (Notification) -> Monitor.
    # It assumes the build is/will be triggered (maybe by CI).
    
    # Wait, if I run this script, and there are new PRs, and CI is set to auto-trigger, then a build should be running or queued.
    # But `get_last_build_info` gets the *last successful* build.
    # If a new build is running, `monitor_deployment_progress` needs to find it.
    # In the original `monitor_deployment_progress`, it takes `build_info`.
    # It checks `check_build_approval_status(build_info['build_id'])`.
    # This checks the status of the *last successful build*? That doesn't make sense.
    # If we pass the *old* build ID to monitor, it will just say "Build completed successfully" immediately.
    
    # There must be a missing piece.
    # Let's check `deployment_dev.py` `monitor_deployment_progress` again.
    # It takes `build_info`.
    # It calls `check_build_approval_status(build_info['build_id'])`.
    # If I pass the *last successful build*, it will return True immediately.
    
    # Ah, maybe `automated_deployment_workflow` is supposed to be called with a NEW build info?
    # But `main_deployment_workflow` passes `latest_build` (which is the last successful one).
    # This looks like a bug in the original script or I am misunderstanding.
    # If I run `deployment_dev.py`, it finds PRs, then calls `automated_deployment_workflow` with the OLD build.
    # Then `monitor_deployment_progress` checks the OLD build.
    # It sees it's completed.
    # It sends "Deployment succeeded".
    # So it just reports the *past* deployment?
    
    # Unless... `get_last_build_info` returns an *in-progress* build?
    # The original `get_last_build_info` had `include_in_progress=False` by default.
    # And `main_deployment_workflow` calls it with defaults (so False).
    
    # So the original script seems to just report on the last successful build and the PRs that went into it?
    # "Checking PRs merged after commit..."
    # If I find PRs *after* the last successful build, these are *undeployed* PRs.
    # If I then pass the *last successful build* to monitor... that's wrong.
    
    # Maybe the script is meant to be run *after* a new build is triggered?
    # Or maybe I should add `trigger_new_build` to `deployment_dev.py`?
    # The user asked for "Enhance Deployment Automation Script".
    # Adding `trigger_new_build` seems like a logical fix/enhancement if it's missing.
    
    # However, `deployment_stage.py` DOES trigger.
    # Let's check `deployment_stage.py` `main` function.
    # It calls `trigger_new_build`.
    
    # I will add `trigger_new_build` to `deployment_dev.py` as well, as it makes sense for an "Automation" script.
    # If changes are detected, trigger a build.
    
    # Wait, if I trigger a build, I get a new Build ID.
    # Then I monitor THAT build ID.
    # This makes perfect sense.
    
    # So, my proposed `main_deployment_workflow` above (which triggers build) is correct for a *robust* automation script, even if the original was lacking.
    # I will proceed with triggering the build.
    
    automated_deployment_workflow(
        pr_merges, 
        monitoring_build_info, # Monitor the NEW build
        pipeline_name=PIPELINE_NAME,
        branch=BRANCH
    )

def main():
    parser = argparse.ArgumentParser(description='Azure DevOps Deployment Automation - DEV Pipeline')
    parser.add_argument('--approval', action='store_true', help='Send approval request to Teams')
    parser.add_argument('--deployment', action='store_true', help='Send deployment confirmation to Teams')
    parser.add_argument('--approved', action='store_true', help='Send approved message to Teams')
    parser.add_argument('--build-triggered', action='store_true', help='Send build triggered message to Teams')
    parser.add_argument('--monitor', action='store_true', help='Monitor deployment progress')
    parser.add_argument('--build-id', help='Build ID for monitoring')
    parser.add_argument('--approver-email', help='Email of the approver')
    parser.add_argument('--approver-name', help='Name of the approver')
    
    args = parser.parse_args()
    
    # Sample data for testing individual functions (if needed)
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
