#!/usr/bin/env python3
"""
Create Pull Request with Auto-Generated Title and Description
Automates creation of a pull request with standardized Merkle PR format following ADW Jira format.
Extracts Jira ticket ID from branch name and generates PR content based on git commits and changes.
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

import subprocess
import re
import sys
import argparse
import os
import requests
import base64
import webbrowser
import random
import time
import term_background
from typing import Optional, Tuple, List
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style

# ============================================================================
# THEME SYSTEM (from pt_theme.py)
# ============================================================================

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Typing Animation
def type_out(text, delay=0.002):
    """Print text with typing animation effect"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

# Random Titles for PR Success
PR_SUCCESS_TITLES = [
    "⚡ CODE LEGEND — PULL REQUEST INITIATED! ⚡",
    "🦸‍♀️ DEPLOYMENT HERO — MISSION UNDERWAY! 🦸‍♀️",
    "🚀 MERGE COMMANDER — OPERATION SUCCESS! 🚀",
    "🔥 BUILD WARRIOR — PR VICTORY UNLOCKED! 🔥",
    "💾 REPO GUARDIAN — CODE DEFENDED! 💾",
    "🌌 MASTER OF MERGES — PORTAL OPENED! 🌌",
    "🧠 SYNCHRONIZATION COMPLETE — CODE HARMONY ACHIEVED 🧠",
    "🎮 GIT HERO — LEVEL UP UNLOCKED! 🎮",
    "💫 COSMIC COMMITTER — MISSION LOG UPDATED 💫",
    "🛠️ REPOSITORY AVENGER — CLEAN CODE DEPLOYED 🛠️",
    "👑 CODE CONQUEROR — BRANCHES UNITED 👑",
    "🧑‍🚀 LAUNCH SEQUENCE COMPLETE — READY FOR REVIEW 🧑‍🚀",
]

# Conflict Message Titles
CONFLICT_TITLES = [
    "⚠️ MERGE CONFLICTS DETECTED — TIME TO PLAY DETECTIVE! 🔍",
    "⚔️ CODE CLASH — RESOLUTION REQUIRED! ⚔️",
    "🔧 MERGE CONFLICTS — YOUR MISSION, SHOULD YOU CHOOSE TO ACCEPT IT 🔧",
    "💥 BRANCH COLLISION — NEEDS YOUR EXPERTISE! 💥",
    "🛡️ CONFLICT ALERT — DEFENDER OF CODE REQUIRED! 🛡️",
]

def get_pr_themes(pr_id, title, status, source, target, pr_link):
    """Generate themed messages for PR success"""
    return [
        f"""{YELLOW}
🔥🦸  {BOLD}AVENGERS INITIATIVE: CODE ASSEMBLE!{RESET}
💥 Another PR lands like Mjölnir striking the repo!
🧪 Mission: {source} ➜ {target}
📋 PR ID: {pr_id} | Title: {title} | Status: {status}
💬 Tony Stark: "Code like you mean it. Review like you own it."
🚀 {pr_link}
💡 Tip: "Whatever it takes... to merge that PR."
""",
        f"""{BLUE}
🌠🛸  {BOLD}STAR WARS: THE CODE AWAKENS{RESET}
🚀 A long time ago, in a repo far, far away…
🎯 Target: {target} | Source: {source}
🆔 PR: {pr_id} | Status: {status}
🧙 Obi-Wan: "Use the Force of clean commits."
✨ {pr_link}
💫 "In the end... the PR merges you."
""",
        f"""{GREEN}
💾🕶️  {BOLD}THE MATRIX: ENTER THE MERGE{RESET}
⛓️ You didn't just push code — you bent Git to your will.
📋 {title} [{source} ➜ {target}]
💬 Morpheus: "There is no spoon. Only the merge."
🧠 Code coverage rising... build stable...
🔗 {pr_link}
🕶️ "Wake up, dev. The repo is real."
""",
        f"""{MAGENTA}
🦇🌃  {BOLD}BATMAN: THE DARK MERGE{RESET}
💻 Gotham Repo: {source} ➜ {target}
🆔 Case File: {pr_id}
🦸 "It's not who I am underneath, but what I merge that defines me."
🔗 {pr_link}
💀 Justice... and clean code.
""",
        f"""{RED}
🍄🎮  {BOLD}SUPER MERGIO BROS!{RESET}
🎯 Source: {source} ➜ {target} | PR ID: {pr_id}
🎉 "It's-a merge time!" 
🏁 Princess Build Success is in another pipeline.
🔗 {pr_link}
⭐ "Let's-a deploy!"
""",
        f"""{CYAN}
🌃⚡  {BOLD}CYBERPUNK 2099: NEON CODE DEPLOY{RESET}
💾 {title}
🧠 {source} ➜ {target} | PR: {pr_id}
👁️ "You don't commit... you inject code into the system."
💫 {pr_link}
🌌 "Wake up, dev. The repo is calling."
""",
        f"""{YELLOW}
💍🧙  {BOLD}LORD OF THE COMMITS{RESET}
🧠 Gandalf: "Fly, you fools... and push to {target}!"
🔥 PR: {pr_id} | {title}
🧿 The Eye of Jenkins sees all...
🌋 {pr_link}
⚔️ "One merge to rule them all."
""",
        f"""{MAGENTA}
☠️⚓  {BOLD}PIRATES OF THE CODEBEAN: MERGE TIDE{RESET}
🏴‍☠️  Source: {source} ➜ {target}
🪙  Treasure Map (PR ID): {pr_id}
🍻  "A smooth merge never made a skilled coder."
🦜 {pr_link}
💀 Yo-ho-ho and a clean build too!
""",
        f"""{GREEN}
💻🕷️  {BOLD}HACKER UNDERGROUND: PROTOCOL INITIATED{RESET}
🧠 Commit Trace: {title}
🕶️ Target Node: {target}
⚡ Merge infiltration complete.
💣 {pr_link}
🕷️ "Hack the code. Free the repo."
""",
        f"""{YELLOW}
🔥💫  {BOLD}DRAGON BALL: MERGE Z!{RESET}
💥 Power level... OVER 9000!
🏆 PR ID: {pr_id} | {source} ➜ {target}
Goku: "This merge… it's destiny."
🌟 {pr_link}
💫 "Merge now… feel the ki!"
""",
        f"""{BLUE}
🚀🌌  {BOLD}NASA MISSION CONTROL{RESET}
🛰️ Launch Sequence: {title}
🌍 From {source} ➜ {target} | PR ID: {pr_id}
🧑‍🚀 Houston: "We have a successful merge."
🔭 {pr_link}
🌠 "Failure is not an option (except in tests)."
""",
        f"""{RED}
🕹️👾  {BOLD}RETRO ARCADE: INSERT MERGE COIN{RESET}
🎮 PR ID: {pr_id} | {source} ➜ {target}
💾 Saving progress...
🏁 Level Complete: {title}
🔗 {pr_link}
🧩 "Achievement Unlocked: Clean Commit."
"""
    ]

def get_conflict_themes(source_branch, target_branch):
    """Generate themed messages for merge conflicts"""
    return [
        f"""{RED}{BOLD}
💥⚔️  THE CLASH OF BRANCHES ⚔️💥
{RESET}{YELLOW}
Looks like {source_branch} and {target_branch} had a disagreement! 😅
{MAGENTA}They're both trying to change the same thing - classic case of "great minds think alike"! 😄
{RESET}{CYAN}
Your branch has merge conflicts with {target_branch} branch.
Don't worry, even the best developers face this! 💪
{RESET}{GREEN}
📋 Here's your mission (should you choose to accept it):
{RESET}
   {GREEN}1.{RESET} Investigate the conflict files (git will tell you which ones)
   {GREEN}2.{RESET} Resolve conflicts like a pro: edit the files and remove conflict markers
   {GREEN}3.{RESET} Stage your resolved files: {CYAN}git add <files>{RESET}
   {GREEN}4.{RESET} Complete the merge: {CYAN}git commit{RESET}
   {GREEN}5.{RESET} Come back and run this script again - we'll be waiting! 🚀
{RESET}{YELLOW}
💡 Pro tip: Use your favorite merge tool or IDE to make conflict resolution easier!
{MAGENTA}🎯 Remember: You've got this! Merge conflicts are just Git's way of saying "Hey, let's talk!" 😊
{RESET}""",
        f"""{MAGENTA}{BOLD}
🛡️ MERGE CONFLICT: THE FINAL BATTLE 🛡️
{RESET}{CYAN}
The forces of {source_branch} and {target_branch} collide!
{RED}Conflict detected in the codebase! ⚠️
{RESET}{YELLOW}
This is your moment to shine, code warrior! 💪
{RESET}{GREEN}
Your quest:
   {GREEN}1.{RESET} Identify the conflict zones
   {GREEN}2.{RESET} Resolve with wisdom and precision
   {GREEN}3.{RESET} Stage your victories: {CYAN}git add <files>{RESET}
   {GREEN}4.{RESET} Seal the merge: {CYAN}git commit{RESET}
   {GREEN}5.{RESET} Return triumphant! 🏆
{RESET}{BLUE}
💫 The merge is strong with this one... once conflicts are resolved!
{RESET}""",
        f"""{YELLOW}{BOLD}
🔧 CODE COLLISION: RESOLUTION REQUIRED 🔧
{RESET}{RED}
⚠️  Merge conflicts between {source_branch} ➜ {target_branch}
{RESET}{CYAN}
Time to put on your detective hat! 🕵️
{RESET}{GREEN}
Mission Brief:
   {GREEN}1.{RESET} Locate conflict markers (<<<<<<, ======, >>>>>>)
   {GREEN}2.{RESET} Choose the best version (or combine them creatively!)
   {GREEN}3.{RESET} Stage resolved files: {CYAN}git add <files>{RESET}
   {GREEN}4.{RESET} Complete merge: {CYAN}git commit{RESET}
   {GREEN}5.{RESET} Run this script again - success awaits! 🚀
{RESET}{MAGENTA}
💡 Remember: Every conflict resolved makes you a better developer!
{RESET}"""
    ]

# ============================================================================
# CONFIGURATION
# ============================================================================

# Azure DevOps configuration
ORG_URL = "https://mpcoderepo.visualstudio.com"
ORG_NAME = "mpcoderepo"
PROJECT = "DigitalExperience"
REPOSITORY_NAME = "aemaacs-life"

# Git repository configuration
# Set this to your local git repository path
# Example: GIT_REPO_PATH = "/Users/rvenat01/Documents/AEM/mandg/aemaacs-life"
GIT_REPO_PATH = "/Users/rvenat01/Documents/AEM/mandg/aemaacs-life"

# Default target branch
DEFAULT_TARGET_BRANCH = "dev"

# Jira base URL
JIRA_BASE_URL = "https://mandg.atlassian.net/browse"

# ============================================================================
# GIT FUNCTIONS
# ============================================================================

def get_git_remote_url(git_root: str) -> Optional[str]:
    """Get the git remote URL for a repository"""
    success, output = run_git_command(["git", "config", "--get", "remote.origin.url"], git_root)
    if success and output:
        return output.strip()
    return None

def find_git_root(start_path: str = None, preferred_repo_name: str = None) -> Optional[str]:
    """Find the git repository root directory, optionally matching a preferred repository name"""
    # First, check if GIT_REPO_PATH is configured
    if GIT_REPO_PATH and os.path.exists(GIT_REPO_PATH):
        git_dir = os.path.join(GIT_REPO_PATH, '.git')
        if os.path.exists(git_dir):
            return GIT_REPO_PATH
    
    if start_path is None:
        start_path = os.getcwd()
    
    current_path = os.path.abspath(start_path)
    matching_repo = None
    found_repos = []
    
    # Check current directory and parent directories
    while True:
        git_dir = os.path.join(current_path, '.git')
        if os.path.exists(git_dir):
            found_repos.append(current_path)
            # If we have a preferred repo name, check if this matches
            if preferred_repo_name:
                # Check directory name
                dir_name = os.path.basename(current_path)
                if dir_name == preferred_repo_name:
                    matching_repo = current_path
                    break
                # Check remote URL
                remote_url = get_git_remote_url(current_path)
                if remote_url and preferred_repo_name in remote_url:
                    matching_repo = current_path
                    break
            else:
                # No preference, return first found
                return current_path
        
        parent = os.path.dirname(current_path)
        if parent == current_path:  # Reached filesystem root
            break
        current_path = parent
    
    # If we found a matching repo, return it
    if matching_repo:
        return matching_repo
    
    # If not found in parents, check common sibling directories
    # Look for git repos in common AEM project locations
    start_abs = os.path.abspath(start_path)
    common_paths = []
    
    # Check if we're in an AEM-related directory structure
    path_parts = start_abs.split(os.sep)
    if 'AEM' in path_parts:
        aem_index = path_parts.index('AEM')
        aem_base = os.sep.join(path_parts[:aem_index + 1])
        
        # If we have a preferred repo name, prioritize it
        if preferred_repo_name:
            # Check direct path: AEM/preferred_repo_name
            preferred_path = os.path.join(aem_base, preferred_repo_name)
            if os.path.exists(preferred_path):
                git_dir = os.path.join(preferred_path, '.git')
                if os.path.exists(git_dir):
                    # Verify it matches by checking remote or directory name
                    remote_url = get_git_remote_url(preferred_path)
                    if remote_url and preferred_repo_name in remote_url:
                        return preferred_path
                    elif os.path.basename(preferred_path) == preferred_repo_name:
                        return preferred_path
            
            # Check nested path: AEM/mandg/preferred_repo_name (common structure)
            mandg_path = os.path.join(aem_base, 'mandg', preferred_repo_name)
            if os.path.exists(mandg_path):
                git_dir = os.path.join(mandg_path, '.git')
                if os.path.exists(git_dir):
                    remote_url = get_git_remote_url(mandg_path)
                    if remote_url and preferred_repo_name in remote_url:
                        return mandg_path
                    elif os.path.basename(mandg_path) == preferred_repo_name:
                        return mandg_path
        
        # Check common project directories
        common_names = ['aemaacs-life', 'mandg', 'Mine', 'aem-project']
        # If preferred_repo_name is in the list, put it first
        if preferred_repo_name and preferred_repo_name in common_names:
            common_names.remove(preferred_repo_name)
            common_names.insert(0, preferred_repo_name)
        
        for name in common_names:
            # Check direct path
            potential_path = os.path.join(aem_base, name)
            if os.path.exists(potential_path):
                git_dir = os.path.join(potential_path, '.git')
                if os.path.exists(git_dir):
                    if preferred_repo_name:
                        # Check if this matches the preferred repo
                        dir_name = os.path.basename(potential_path)
                        if dir_name == preferred_repo_name:
                            return potential_path
                        remote_url = get_git_remote_url(potential_path)
                        if remote_url and preferred_repo_name in remote_url:
                            return potential_path
                    common_paths.append(potential_path)
            
            # Check nested path: AEM/mandg/name
            nested_path = os.path.join(aem_base, 'mandg', name)
            if os.path.exists(nested_path):
                git_dir = os.path.join(nested_path, '.git')
                if os.path.exists(git_dir):
                    if preferred_repo_name:
                        dir_name = os.path.basename(nested_path)
                        if dir_name == preferred_repo_name:
                            return nested_path
                        remote_url = get_git_remote_url(nested_path)
                        if remote_url and preferred_repo_name in remote_url:
                            return nested_path
                    common_paths.append(nested_path)
    
    # Also check environment variable for default git repo
    env_git_repo = os.environ.get('GIT_REPO_PATH')
    if env_git_repo and os.path.exists(env_git_repo):
        git_dir = os.path.join(env_git_repo, '.git')
        if os.path.exists(git_dir):
            if preferred_repo_name:
                dir_name = os.path.basename(env_git_repo)
                if dir_name == preferred_repo_name:
                    return env_git_repo
                remote_url = get_git_remote_url(env_git_repo)
                if remote_url and preferred_repo_name in remote_url:
                    return env_git_repo
            common_paths.append(env_git_repo)
    
    # Return first found git repo (prioritize matching ones if we have a preference)
    if matching_repo:
        return matching_repo
    
    if common_paths:
        return common_paths[0]
    
    if found_repos:
        return found_repos[0]
    
    return None

def run_git_command(command: List[str], work_dir: str = None) -> Tuple[bool, str]:
    """Run a git command and return success status and output"""
    try:
        # If work_dir is not specified, try to find git root
        if work_dir is None:
            work_dir = find_git_root()
        
        result = subprocess.run(
            command,
            cwd=work_dir if work_dir else None,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)

def get_current_branch(work_dir: str = None) -> Optional[str]:
    """Get the current git branch name"""
    success, output = run_git_command(["git", "branch", "--show-current"], work_dir)
    if success and output:
        return output
    return None

def extract_jira_ticket(branch_name: str) -> Optional[str]:
    """Extract Jira ticket ID (e.g., ADW-1495) from branch name"""
    # Pattern to match ADW-XXXX format
    pattern = r'ADW-\d+'
    match = re.search(pattern, branch_name, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

def is_branch_up_to_date(source_branch: str, target_branch: str, work_dir: str = None) -> Tuple[bool, List[str]]:
    """Check if source branch is up to date with target branch.
    Returns (is_up_to_date, list of commits in target that are not in source)"""
    # Try with origin/ prefix first
    commands = [
        ["git", "log", "--oneline", f"{source_branch}..origin/{target_branch}"],
        ["git", "log", "--oneline", f"{source_branch}..{target_branch}"],
        ["git", "log", "--oneline", f"origin/{source_branch}..origin/{target_branch}"],
        ["git", "log", "--oneline", f"origin/{source_branch}..{target_branch}"],
    ]
    
    for cmd in commands:
        success, output = run_git_command(cmd, work_dir)
        if success:
            commits = [line.strip() for line in output.split('\n') if line.strip()]
            # If there are commits, branch is not up to date
            return len(commits) == 0, commits
    
    # If we can't determine, assume it's up to date (fail open)
    return True, []

def check_merge_conflicts(work_dir: str = None) -> bool:
    """Check if there are merge conflicts in the current repository state"""
    # Check for unmerged paths (files with conflicts)
    success, output = run_git_command(["git", "ls-files", "-u"], work_dir)
    if success and output and output.strip():
        return True
    
    # Check git status for merge conflicts
    success, output = run_git_command(["git", "status", "--porcelain"], work_dir)
    if success:
        # Look for conflict markers (UU = unmerged, both modified)
        for line in output.split('\n'):
            if line.startswith('UU ') or line.startswith('AA ') or line.startswith('DD '):
                return True
    
    return False

def is_in_merge_state(work_dir: str = None) -> bool:
    """Check if repository is currently in a merge state"""
    success, output = run_git_command(["git", "status"], work_dir)
    if success:
        return "All conflicts fixed but you are still merging" in output or "You have unmerged paths" in output
    return False

def attempt_merge_commit(source_branch: str, target_branch: str, work_dir: str = None, suppress_output: bool = False) -> Tuple[bool, str]:
    """Attempt to merge target branch into source branch and push changes.
    Returns (success, message)"""
    # Check if already in merge state
    if is_in_merge_state(work_dir):
        # Abort any existing merge first
        if not suppress_output:
            print("   Found existing merge state. Aborting...")
        run_git_command(["git", "merge", "--abort"], work_dir)
    
    # Ensure we're on the source branch
    success, output = run_git_command(["git", "checkout", source_branch], work_dir)
    if not success:
        return False, f"Failed to checkout branch {source_branch}: {output}"
    
    # Try to merge origin/target_branch
    merge_target = f"origin/{target_branch}"
    if not suppress_output:
        print(f"   Attempting to merge {merge_target} into {source_branch}...")
    
    # Use --no-edit to use default merge commit message, --no-ff to always create merge commit
    success, output = run_git_command(
        ["git", "merge", "--no-edit", "--no-ff", merge_target],
        work_dir
    )
    
    if success:
        # Check if merge was already up to date
        if "Already up to date" in output or "is up to date" in output.lower():
            return True, "Branch is already up to date (no merge needed)"
        
        # Merge was successful, now push the changes
        if not suppress_output:
            print(f"   Pushing merged changes to origin/{source_branch}...")
        push_success, push_output = run_git_command(
            ["git", "push", "origin", source_branch],
            work_dir
        )
        
        if push_success:
            return True, "Merge completed successfully and pushed to remote"
        else:
            return False, f"Merge completed but push failed: {push_output}"
    
    # Check if there are conflicts
    if check_merge_conflicts(work_dir) or is_in_merge_state(work_dir):
        # Abort the merge silently if suppressing output
        if not suppress_output:
            print("   Merge conflicts detected. Aborting merge...")
        abort_success, abort_output = run_git_command(["git", "merge", "--abort"], work_dir)
        if not abort_success:
            return False, f"Merge conflicts detected and failed to abort merge: {abort_output}"
        return False, "Merge conflicts detected. Please resolve conflicts manually."
    
    return False, f"Merge failed: {output}"

def get_commits(source_branch: str, target_branch: str, work_dir: str = None) -> List[str]:
    """Get list of commits between target and source branch"""
    # Try with origin/ prefix first
    commands = [
        ["git", "log", "--oneline", f"origin/{target_branch}..HEAD"],
        ["git", "log", "--oneline", f"{target_branch}..HEAD"],
        ["git", "log", "--oneline", f"origin/{target_branch}..{source_branch}"],
        ["git", "log", "--oneline", f"{target_branch}..{source_branch}"],
    ]
    
    for cmd in commands:
        success, output = run_git_command(cmd, work_dir)
        if success and output:
            return [line.strip() for line in output.split('\n') if line.strip()]
    
    return []

def get_file_changes_summary(source_branch: str, target_branch: str, work_dir: str = None) -> str:
    """Get file changes summary using git diff --stat"""
    # Try with origin/ prefix first
    commands = [
        ["git", "diff", "--stat", f"origin/{target_branch}...HEAD"],
        ["git", "diff", "--stat", f"{target_branch}...HEAD"],
        ["git", "diff", "--stat", f"origin/{target_branch}...{source_branch}"],
        ["git", "diff", "--stat", f"{target_branch}...{source_branch}"],
    ]
    
    for cmd in commands:
        success, output = run_git_command(cmd, work_dir)
        if success and output:
            return output
    
    return ""

def generate_pr_title(branch_name: str, jira_ticket: str, commits: List[str]) -> str:
    """Generate PR title in format: ADW-XXXX [Merkle] <Short descriptive title>"""
    # Extract descriptive part from branch name (after ticket ID)
    branch_parts = branch_name.split(jira_ticket, 1)
    if len(branch_parts) > 1:
        descriptive_part = branch_parts[1].strip('-').strip('_').strip()
        # Replace dashes/underscores with spaces and title case
        descriptive_part = descriptive_part.replace('-', ' ').replace('_', ' ')
        # Capitalize first letter of each word
        descriptive_part = ' '.join(word.capitalize() for word in descriptive_part.split())
    else:
        # Fallback: use first commit message if available
        if commits:
            # Take first 50 chars of first commit, remove ticket ID if present
            descriptive_part = commits[0].split(' ', 1)[-1] if len(commits[0].split(' ')) > 1 else commits[0]
            descriptive_part = re.sub(r'ADW-\d+\s*', '', descriptive_part, flags=re.IGNORECASE)
            descriptive_part = descriptive_part[:50].strip()
        else:
            descriptive_part = "Changes"
    
    return f"{jira_ticket} [Merkle] {descriptive_part}"

def get_master_to_dev_description(ticket_number: str = "ADW-1245") -> str:
    """Get PR description for master to dev sync (same as create_pr_master_to_dev.py)"""
    pr_template_path = os.path.join(os.path.dirname(__file__), "pull_request_template.md")
    
    try:
        # Read the template file
        if os.path.exists(pr_template_path):
            with open(pr_template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            # Fallback template if file doesn't exist
            template = """## What does this PR do?

master to dev sync

---

## What are the relevant tickets?

[ADW-XXXX](https://mandg.atlassian.net/browse/ADW-XXXX)

---

## Has the Sonarqube scan for your branch been reviewed to make sure no new issues have been introduced?

- [ ] YES - Sonarqube scan has been reviewed and no new issues have been introduced
- [ ] NO - Sonarqube scan has NOT been reviewed (explanation required below)

---

## Describe how these changes have been tested



---

## Additional Resources / Comments



"""
        
        # Replace ADW-XXXX with the actual ticket number
        template = template.replace("ADW-XXXX", ticket_number)
        
        # Add "master to dev sync" in the "What does this PR do?" section
        # Replace empty section with "master to dev sync"
        if "## What does this PR do?\n\n\n" in template:
            template = template.replace("## What does this PR do?\n\n\n", "## What does this PR do?\n\nmaster to dev sync\n\n")
        elif "## What does this PR do?\n\n" in template:
            # Check if "master to dev sync" is not already there
            if "master to dev sync" not in template:
                # Find the section and add the text
                lines = template.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() == "## What does this PR do?":
                        # Find where the section ends (next non-empty line or next header)
                        j = i + 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        # Insert "master to dev sync" after the header
                        lines.insert(i + 1, "")
                        lines.insert(i + 2, "master to dev sync")
                        template = '\n'.join(lines)
                        break
        
        return template
    except Exception as e:
        print(f"⚠️  Warning: Could not load PR template: {e}")
        # Return a simple fallback description
        return f"""## What does this PR do?

master to dev sync

---

## What are the relevant tickets?

[{ticket_number}](https://mandg.atlassian.net/browse/{ticket_number})

---

## Has the Sonarqube scan for your branch been reviewed to make sure no new issues have been introduced?

- [ ] YES - Sonarqube scan has been reviewed and no new issues have been introduced
- [ ] NO - Sonarqube scan has NOT been reviewed (explanation required below)

---

## Describe how these changes have been tested



---

## Additional Resources / Comments



"""

def generate_pr_description(jira_ticket: str, commits: List[str], file_changes: str) -> str:
    """Generate PR description following the template"""
    # Generate "What does this PR do?" summary
    summary = generate_pr_summary(commits, file_changes)
    
    # Generate testing description
    testing_desc = generate_testing_description(commits, file_changes)
    
    description = f"""## What does this PR do?

{summary}

---

## What are the relevant tickets?

[{jira_ticket}]({JIRA_BASE_URL}/{jira_ticket})

---

## Has the Sonarqube scan for your branch been reviewed to make sure no new issues have been introduced?

- [ ] YES - Sonarqube scan has been reviewed and no new issues have been introduced
- [ ] NO - Sonarqube scan has NOT been reviewed (explanation required below)

## Describe how these changes have been tested
{testing_desc}

## Additional Resources / Comments
None.
"""
    return description

def generate_pr_summary(commits: List[str], file_changes: str) -> str:
    """Generate a one-line summary based on commits and file changes"""
    if not commits:
        return "Updates from current branch"
    
    # Analyze commits to generate summary
    # Remove ticket IDs and common prefixes from commit messages
    cleaned_commits = []
    for commit in commits[:5]:  # Look at first 5 commits
        # Remove hash and ticket ID
        commit_msg = re.sub(r'^[a-f0-9]+\s+', '', commit)
        commit_msg = re.sub(r'ADW-\d+\s*', '', commit_msg, flags=re.IGNORECASE)
        commit_msg = commit_msg.strip()
        if commit_msg:
            cleaned_commits.append(commit_msg)
    
    if cleaned_commits:
        # Use first commit message as base, but make it more descriptive
        first_commit = cleaned_commits[0]
        # Capitalize first letter
        summary = first_commit[0].upper() + first_commit[1:] if len(first_commit) > 1 else first_commit.upper()
        # Ensure it ends with a period
        if not summary.endswith(('.', '!', '?')):
            summary += '.'
        return summary
    
    # Fallback based on file changes
    if file_changes:
        # Count file types changed
        java_files = len(re.findall(r'\.java\s', file_changes))
        xml_files = len(re.findall(r'\.xml\s', file_changes))
        js_files = len(re.findall(r'\.(js|jsx|ts|tsx)\s', file_changes))
        
        if java_files > 0:
            return "Updates Java components and configurations."
        elif xml_files > 0:
            return "Updates XML configurations."
        elif js_files > 0:
            return "Updates JavaScript/TypeScript components."
    
    return "Implements changes as described in the ticket."

def generate_testing_description(commits: List[str], file_changes: str) -> str:
    """Generate testing description based on changes"""
    # Analyze file changes to suggest testing approach
    if not file_changes:
        return "Manual testing performed in AEM author environment."
    
    # Check for test files
    has_tests = bool(re.search(r'(test|spec)\.(java|js|ts)', file_changes, re.IGNORECASE))
    
    # Check for component files
    has_components = bool(re.search(r'\.(java|js|jsx|ts|tsx)', file_changes))
    
    testing_parts = []
    
    if has_tests:
        testing_parts.append("Unit tests added/updated.")
    
    if has_components:
        testing_parts.append("Manual testing performed in AEM author environment.")
    else:
        testing_parts.append("Manual testing performed in AEM author environment.")
    
    return " ".join(testing_parts) if testing_parts else "Manual testing performed in AEM author environment."

def print_conflict_message(source_branch="your branch", target_branch="master"):
    """Print a themed merge conflict message with dynamic content"""
    # Clear screen for better visibility
    os.system('clear' if os.name != 'nt' else 'cls')
    
    # Randomly select a conflict theme
    conflict_themes = get_conflict_themes(source_branch, target_branch)
    chosen_theme = random.choice(conflict_themes)
    chosen_title = random.choice(CONFLICT_TITLES)
    
    # Create animated header
    header = f"""{RED}{BOLD}
{'═' * 72}
       {chosen_title}
{'═' * 72}
{RESET}"""
    
    # Print without delays
    type_out(header, 0.0)
    type_out(chosen_theme, 0.0)
    
    # Footer
    footer = f"""{RED}{BOLD}
{'═' * 72}
{RESET}"""
    print(footer)
    sys.stdout.flush()
    os._exit(1)

def print_superhero_success(pr_id, pr_title, pr_status, source_branch, target_branch, pr_url_web=None):
    """Print a dynamically themed celebratory success message when PR is created"""
    # Randomly select a title and theme
    chosen_title = random.choice(PR_SUCCESS_TITLES)
    themes = get_pr_themes(pr_id, pr_title, pr_status, source_branch, target_branch, pr_url_web or "")
    chosen_theme = random.choice(themes)

    # Create animated header
    header = f"""{CYAN}{BOLD}
{'═' * 72}
       {chosen_title}
{'═' * 72}
{RESET}"""

    # Print without delays
    type_out(header, 0.0)
    type_out(chosen_theme, 0.0)

    # Final message
    if pr_url_web:
        print(f"{GREEN}{BOLD}🌟 Great work, hero! Opening PR in browser... 🌟{RESET}")
        webbrowser.open(pr_url_web)
    else:
        print(f"{GREEN}{BOLD}🌟 Great work, hero! Your PR has been created! 🌟{RESET}")

    sys.stdout.flush()

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
        if response.status_code == 200:
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

def search_work_items(query: str, top: int = 20):
    """Search for work items (tickets) matching the query"""
    headers = get_azure_devops_headers()
    if not headers:
        return []
    
    # Use WIQL (Work Item Query Language) to search for work items
    wiql_url = f"{ORG_URL}/{PROJECT}/_apis/wit/wiql?api-version=7.0"
    
    # Search for work items with ID or title containing the query
    wiql_query = f"SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.TeamProject] = '{PROJECT}' AND ([System.Id] CONTAINS '{query}' OR [System.Title] CONTAINS '{query}') ORDER BY [System.ChangedDate] DESC"
    
    try:
        response = requests.post(wiql_url, headers=headers, json={"query": wiql_query})
        if response.status_code == 200:
            wiql_data = response.json()
            work_items = []
            
            # Get work item IDs
            work_item_ids = [item.get('id') for item in wiql_data.get('workItems', [])[:top]]
            
            if work_item_ids:
                # Get details for these work items
                work_items_url = f"{ORG_URL}/{PROJECT}/_apis/wit/workitems?ids={','.join(map(str, work_item_ids))}&api-version=7.0"
                items_response = requests.get(work_items_url, headers=headers)
                if items_response.status_code == 200:
                    items_data = items_response.json()
                    for item in items_data.get('value', []):
                        item_id = item.get('id')
                        fields = item.get('fields', {})
                        title = fields.get('System.Title', '')
                        work_item_type = fields.get('System.WorkItemType', '')
                        # Extract ticket ID (e.g., ADW-1234)
                        ticket_match = None
                        if title:
                            ticket_match = re.search(r'ADW-\d+', title, re.IGNORECASE)
                        if ticket_match:
                            ticket_id = ticket_match.group(0).upper()
                            work_items.append({
                                'id': ticket_id,
                                'title': title,
                                'type': work_item_type
                            })
                        elif item_id:
                            # Fallback: use work item ID
                            work_items.append({
                                'id': f"WI-{item_id}",
                                'title': title,
                                'type': work_item_type
                            })
            
            return work_items
        return []
    except Exception as e:
        print(f"⚠️  Error searching work items: {e}")
        return []

# ============================================================================
# INTERACTIVE MENU FUNCTIONS
# ============================================================================

def select_from_menu(options: List[str], title: str = "Select an option", default_index: int = 0) -> Optional[str]:
    """Create an interactive menu with arrow key navigation"""
    if not options:
        return None
    
    selected_index = [default_index if 0 <= default_index < len(options) else 0]
    
    def get_formatted_text():
        result = []
        result.append(("class:title", f"\n{title}:\n"))
        result.append(("", "\n"))
        
        for i, option in enumerate(options):
            if i == selected_index[0]:
                result.append(("class:selected", f"  > {option}\n"))
            else:
                result.append(("class:option", f"    {option}\n"))
        
        result.append(("", "\n"))
        result.append(("class:instruction", "  Use ↑/↓ arrows to navigate, Enter to select, Ctrl+C to cancel\n"))
        
        return result
    
    # Create control - FormattedTextControl accepts a callable that returns formatted text
    control = FormattedTextControl(get_formatted_text, show_cursor=False)
    
    # Key bindings
    kb = KeyBindings()
    
    @kb.add('up')
    def move_up(event):
        selected_index[0] = max(0, selected_index[0] - 1)
        # Invalidate and redraw
        event.app.invalidate()
    
    @kb.add('down')
    def move_down(event):
        selected_index[0] = min(len(options) - 1, selected_index[0] + 1)
        # Invalidate and redraw
        event.app.invalidate()
    
    @kb.add('enter')
    def select(event):
        event.app.exit(result=options[selected_index[0]])
    
    @kb.add('c-c')
    def cancel(event):
        event.app.exit(result=None)
    
    is_dark = False
    try:
        if term_background.is_dark_background():
            is_dark = True
    except Exception:
        # Fallback if term_background fails or is not installed
        pass
    # Check the terminal background. Fallback to dark theme if detection fails.
    if is_dark:
        # **Dark Theme:** Light text on dark background
        style = Style([
            # Title: Bright Green text (e.g., #00ff00)
            ('title', 'bold #00ff00'), 
            # Selected: Black text (readable) on Bright Green background
            ('selected', 'bg:#00ff00 #000000 bold'), 
            # Option: White text for visibility
            ('option', '#ffffff'), 
            # Instruction: Gray italic text
            ('instruction', '#888888 italic'),
        ])
    else:
        # **Light Theme:** Dark text on light background
        style = Style([
            # Title: Dark Blue text (e.g., #00008b)
            ('title', 'bold #00008b'), 
            # Selected: White text (readable) on Dark Blue background
            ('selected', 'bg:#00008b #ffffff bold'), 
            # Option: Black text for visibility
            ('option', '#000000'), 
            # Instruction: Dark Gray italic text
            ('instruction', '#444444 italic'),
        ])
    # --- END THEME/STYLE ADJUSTMENT ---
    
    # Layout
    layout = Layout(Window(content=control))
    
    # Application
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
        mouse_support=False
    )
    
    try:
        result = app.run()
        return result
    except KeyboardInterrupt:
        return None

# ============================================================================
# AUTOCOMPLETE CLASSES
# ============================================================================

class TicketCompleter(Completer):
    """Autocomplete completer for ticket numbers"""
    def __init__(self, cache: dict = None):
        self.cache = cache or {}
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.upper()
        
        # If we have cached suggestions, use them
        if text in self.cache:
            for ticket in self.cache[text]:
                yield Completion(ticket['id'], start_position=-len(text), display_meta=ticket.get('title', '')[:50])
        
        # Also provide pattern-based suggestions
        if text.startswith('ADW-'):
            # If it looks like a ticket ID, try to complete it
            if len(text) > 4 and text[4:].isdigit():
                # Already has numbers, just return as is
                pass
            else:
                # Suggest common patterns
                for pattern in ['ADW-', 'ADW-1', 'ADW-12', 'ADW-123']:
                    if pattern.startswith(text):
                        yield Completion(pattern, start_position=-len(text))

def convert_api_url_to_web_url(api_url):
    """Convert Azure DevOps API URL to web URL"""
    if not api_url:
        return None
    # Convert API URL format to web URL format
    if '_apis/git/repositories' in api_url:
        pr_id = None
        if '/pullRequests/' in api_url:
            parts = api_url.split('/pullRequests/')
            if len(parts) > 1:
                pr_id = parts[1].split('?')[0]
        elif '/pullrequests/' in api_url:
            parts = api_url.split('/pullrequests/')
            if len(parts) > 1:
                pr_id = parts[1].split('?')[0]
        
        if pr_id:
            if 'visualstudio.com' in api_url:
                org_match = api_url.split('://')[1].split('.visualstudio.com')[0]
                web_url = f"https://dev.azure.com/{org_match}/{PROJECT}/_git/{REPOSITORY_NAME}/pullrequest/{pr_id}"
            else:
                if 'dev.azure.com' in api_url:
                    org_match = api_url.split('dev.azure.com/')[1].split('/')[0]
                    web_url = f"https://dev.azure.com/{org_match}/{PROJECT}/_git/{REPOSITORY_NAME}/pullrequest/{pr_id}"
                else:
                    base_url = api_url.split('/_apis')[0]
                    web_url = f"{base_url}/{PROJECT}/_git/{REPOSITORY_NAME}/pullrequest/{pr_id}"
            return web_url
    return api_url

def check_existing_pr(repo_id, source_branch, target_branch):
    """Check if there's already an open PR from source to target branch"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Normalize branch names
    source_ref = source_branch if source_branch.startswith("refs/heads/") else f"refs/heads/{source_branch}"
    target_ref = target_branch if target_branch.startswith("refs/heads/") else f"refs/heads/{target_branch}"
    
    prs_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.0&searchCriteria.status=active&searchCriteria.sourceRefName={source_ref}&searchCriteria.targetRefName={target_ref}"
    
    try:
        response = requests.get(prs_url, headers=headers)
        if response.status_code == 200:
            prs_data = response.json()
            prs = prs_data.get('value', [])
            if prs:
                return prs[0]  # Return the first active PR
        return None
    except Exception as e:
        print(f"⚠️  Error checking existing PRs: {e}")
        return None

def create_pull_request(repo_id, source_branch, target_branch, title, description):
    """Create a pull request from source branch to target branch"""
    headers = get_azure_devops_headers()
    if not headers:
        return None
    
    # Normalize branch names
    source_ref = source_branch if source_branch.startswith("refs/heads/") else f"refs/heads/{source_branch}"
    target_ref = target_branch if target_branch.startswith("refs/heads/") else f"refs/heads/{target_branch}"
    
    # Check for existing PR
    existing_pr = check_existing_pr(repo_id, source_branch, target_branch)
    if existing_pr:
        pr_id = existing_pr.get('pullRequestId')
        pr_url_api = existing_pr.get('url', '')
        pr_url_web = convert_api_url_to_web_url(pr_url_api)
        
        # Themed message for existing PR
        existing_pr_titles = [
            "🎯 HEY THERE, SUPERHERO!",
            "✨ ALREADY ON THE CASE!",
            "🦸 PR ALREADY EXISTS!",
            "💫 DUPLICATE DETECTED — BUT YOU'RE COVERED!",
        ]
        chosen_title = random.choice(existing_pr_titles)
        
        header = f"""{YELLOW}{BOLD}
{'═' * 72}
       {chosen_title}
{'═' * 72}
{RESET}"""
        
        message = f"""{CYAN}✨ An active pull request already exists for this branch! ✨{RESET}
{GREEN}   PR ID: {pr_id}{RESET}
"""
        if pr_url_web:
            message += f"{GREEN}   PR URL: {pr_url_web}{RESET}\n"
        else:
            message += f"{GREEN}   PR URL: {pr_url_api}{RESET}\n"
        
        message += f"""{YELLOW}💡 No need to create a duplicate - you're already on the case! 🦸‍♂️{RESET}
"""
        
        type_out(header, 0.0)
        type_out(message, 0.0)
        
        if pr_url_web:
            print(f"{CYAN}🌐 Opening PR in browser...{RESET}")
            webbrowser.open(pr_url_web)
        
        return existing_pr
    
    # Prepare PR payload
    pr_payload = {
        "sourceRefName": source_ref,
        "targetRefName": target_ref,
        "title": title,
        "description": description
    }
    
    # Enable autocomplete for PRs targeting dev branch (same as create_pr_master_to_dev.py)
    if target_branch.lower() == "dev":
        pr_payload["completionOptions"] = {
            "autoCompleteIgnoreConfigIds": []
        }
        print("🔧 Autocomplete enabled for dev target PR")
    
    pr_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/pullrequests?api-version=7.1"
    
    try:
        print(f"🚀 Creating pull request from '{source_branch}' to '{target_branch}'...")
        response = requests.post(pr_url, headers=headers, json=pr_payload)
        
        if response.status_code in [200, 201]:
            pr_data = response.json()
            pr_id = pr_data.get('pullRequestId')
            pr_title = pr_data.get('title')
            pr_status = pr_data.get('status')
            pr_url_api = pr_data.get('url', '')
            pr_url_web = convert_api_url_to_web_url(pr_url_api)
            
            # Print superhero-themed success message
            print_superhero_success(
                pr_id=pr_id,
                pr_title=pr_title,
                pr_status=pr_status,
                source_branch=source_branch,
                target_branch=target_branch,
                pr_url_web=pr_url_web
            )
            
            return pr_data
        else:
            print(f"❌ Failed to create pull request: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating pull request: {e}")
        return None

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to create PR with auto-generated content"""
    parser = argparse.ArgumentParser(
        description='Create a pull request with auto-generated title and description',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create PR from current branch to dev
  python3 create_pr.py

  # Create PR to specific target branch
  python3 create_pr.py --target stage

  # Specify git repository location
  python3 create_pr.py --work-dir /path/to/git/repo

  # Non-interactive: Create PR from master to dev sync (constant title/description)
  python3 create_pr.py --master-to-dev
        """
    )
    
    parser.add_argument(
        '--target',
        type=str,
        default=DEFAULT_TARGET_BRANCH,
        help=f'Target branch name (default: {DEFAULT_TARGET_BRANCH})'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate PR title and description without creating the PR'
    )
    
    parser.add_argument(
        '--work-dir',
        type=str,
        default=None,
        help='Working directory (git repository root). If not specified, will search for git repo.'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Enable interactive mode with autocomplete for branches and tickets'
    )
    
    parser.add_argument(
        '--master-to-dev',
        action='store_true',
        help='Non-interactive mode: Create PR from master to dev sync (uses constant title and description)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    if args.master_to_dev:
        print("Create Pull Request: Master to Dev (Non-Interactive Mode)")
    else:
        print("Create Pull Request with Auto-Generated Content")
    print("=" * 70)
    print()
    
    # Handle master-to-dev non-interactive mode
    if args.master_to_dev:
        # Non-interactive mode: master to dev sync (same as create_pr_master_to_dev.py)
        source_branch = "master"
        target_branch = "dev"
        ticket_number = "ADW-1245"  # Constant ticket number as per create_pr_master_to_dev.py
        
        # Use constant title (same as create_pr_master_to_dev.py)
        pr_title = "ADW-1245 [Merkle] master to dev"
        
        # Generate description (same as create_pr_master_to_dev.py)
        pr_description = get_master_to_dev_description(ticket_number)
        
        print(f"📋 Source branch: {source_branch}")
        print(f"📋 Target branch: {target_branch}")
        print(f"🎫 Jira ticket: {ticket_number}")
        print()
        print("✨ Generating PR content...")
        print()
        
        if args.dry_run:
            print("=" * 70)
            print("PR Title:")
            print("=" * 70)
            print(pr_title)
            print()
            print("=" * 70)
            print("PR Description:")
            print("=" * 70)
            print(pr_description)
            print()
            print("=" * 70)
            print("✅ Dry run complete - PR content generated above")
            print("=" * 70)
            sys.exit(0)
        
        # Validate environment variable
        if not os.environ.get('AZURE_DEVOPS_PAT'):
            print("❌ Error: AZURE_DEVOPS_PAT environment variable not set")
            print("   Please set it using: export AZURE_DEVOPS_PAT='your_token_here'")
            sys.exit(1)
        
        # Get repository ID
        print("🔍 Looking up repository...")
        repo_id = get_repository_id(REPOSITORY_NAME)
        if not repo_id:
            print("❌ Failed to get repository ID. Exiting.")
            sys.exit(1)
        
        print()
        
        # Create pull request
        pr_result = create_pull_request(
            repo_id=repo_id,
            source_branch=source_branch,
            target_branch=target_branch,
            title=pr_title,
            description=pr_description
        )
        
        if pr_result:
            # Superhero message already printed in create_pull_request function
            sys.exit(0)
        else:
            print()
            print("=" * 70)
            print("❌ Failed to create pull request")
            print("=" * 70)
            sys.exit(1)
    
    # Use default repository name
    azure_repo_name = REPOSITORY_NAME
    
    # Find git repository root, prioritizing the one matching Azure DevOps repo name
    if args.work_dir:
        git_root = find_git_root(args.work_dir, azure_repo_name)
        if not git_root:
            print(f"❌ Error: '{args.work_dir}' is not a git repository")
            sys.exit(1)
    else:
        git_root = find_git_root(preferred_repo_name=azure_repo_name)
        if not git_root:
            print("❌ Error: Could not find git repository")
            print()
            print("   Options to fix this:")
            print("   1. Run the script from within your git repository")
            print("   2. Use --work-dir to specify the git repository path:")
            print(f"      python3 create_pr.py --work-dir /path/to/{azure_repo_name}")
            print("   3. Set GIT_REPO_PATH environment variable:")
            print(f"      export GIT_REPO_PATH=/path/to/{azure_repo_name}")
            print()
            print("   The script will also automatically search common AEM project")
            print("   directories if it can't find a git repo in parent directories.")
            sys.exit(1)
    
    print(f"📁 Git repository: {git_root}")
    # Verify we found the right repo
    if azure_repo_name:
        repo_dir_name = os.path.basename(git_root)
        if repo_dir_name != azure_repo_name:
            print(f"⚠️  Warning: Git repo directory name '{repo_dir_name}' doesn't match Azure DevOps repo '{azure_repo_name}'")
            print(f"   Make sure you're using the correct git repository for '{azure_repo_name}'")
    print()
    
    # Get current branch automatically
    source_branch = get_current_branch(git_root)
    if not source_branch:
        print("❌ Error: Could not determine current branch")
        print("   Please ensure you are on a valid git branch")
        sys.exit(1)
    
    print(f"📋 Source branch: {source_branch} (current branch)")
    
    # Always interactive by default (unless --target is explicitly provided)
    target_branch = args.target
    jira_ticket = None
    
    # Check if we should prompt for target branch
    # Prompt if: interactive flag set, OR (running in TTY AND target is default)
    # Note: dry-run mode still allows interactive selection
    should_prompt_target = (
        args.interactive or 
        (sys.stdin.isatty() and args.target == DEFAULT_TARGET_BRANCH)
    )
    
    if should_prompt_target:
        print("\n🔍 Interactive mode - Select target branch:")
        
        # Show menu with dev and master options
        menu_options = ['dev', 'master']
        default_index = 0
        if args.target in menu_options:
            default_index = menu_options.index(args.target)
        
        try:
            print("\n   Use ↑/↓ arrow keys to navigate, Enter to select")
            selected = select_from_menu(
                menu_options,
                title="Select target branch",
                default_index=default_index
            )
            
            if selected:
                target_branch = selected
            else:
                print("\n❌ Cancelled by user")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Cancelled by user")
            sys.exit(1)
    
    print(f"\n📋 Target branch: {target_branch}")
    print()
    
    # Check if source branch is up to date with master when targeting master
    if target_branch.lower() == "master":
        print("🔍 Checking if source branch is up to date with master...")
        # Fetch latest changes from origin to ensure we check against latest master
        print("   Fetching latest changes from origin...")
        run_git_command(["git", "fetch", "origin"], git_root)
        is_up_to_date, missing_commits = is_branch_up_to_date(source_branch, "master", git_root)
        
        if not is_up_to_date and missing_commits:
            print(f"⚠️  Warning: Source branch '{source_branch}' is NOT up to date with master")
            print(f"   Found {len(missing_commits)} commit(s) in master that are not in your branch:")
            for commit in missing_commits[:5]:  # Show first 5 commits
                print(f"     - {commit}")
            if len(missing_commits) > 5:
                print(f"     ... and {len(missing_commits) - 5} more commit(s)")
            print()
            
            # Skip merge in dry-run mode
            if args.dry_run:
                print("   [DRY RUN] Would attempt to merge master into your branch...")
                print("   [DRY RUN] Would push merged changes to remote...")
                print()
            else:
                print("   Attempting to merge master into your branch...")
                print()
                
                # Attempt to merge master into source branch (suppress output to show only red message on conflict)
                merge_success, merge_message = attempt_merge_commit(source_branch, "master", git_root, suppress_output=True)
                
                if merge_success:
                    print(f"   ✅ {merge_message}")
                    print("   Branch is now up to date with master. Proceeding with PR creation...")
                    print()
                else:
                    # Only print meaningful message for conflicts - suppress all other output including commit history
                    if "Merge conflicts detected" in merge_message:
                        print_conflict_message(source_branch, "master")
                    else:
                        print(f"❌ {merge_message}")
                        sys.stdout.flush()
                        os._exit(1)
        else:
            print("✅ Source branch is up to date with master")
            print()
    
    # Extract Jira ticket ID
    jira_ticket = extract_jira_ticket(source_branch)
    if not jira_ticket:
        print("⚠️  Warning: Could not extract Jira ticket ID from branch name")
        print(f"   Branch: {source_branch}")
        print("   Expected format: feature/ADW-XXXX-description or ADW-XXXX-description")
        
        # Interactive mode: prompt for ticket with autocomplete
        if args.interactive or (sys.stdin.isatty() and os.environ.get('AZURE_DEVOPS_PAT')):
            try:
                print("   Loading recent tickets...")
                # Try to get ticket suggestions based on branch name
                ticket_cache = {}
                # Search for tickets if branch name has any numbers
                branch_numbers = re.findall(r'\d+', source_branch)
                if branch_numbers:
                    for num in branch_numbers[:2]:  # Try first 2 number sequences
                        work_items = search_work_items(num, top=10)
                        if work_items:
                            # Cache by partial match
                            for item in work_items:
                                ticket_id = item.get('id', '')
                                if ticket_id.startswith('ADW-'):
                                    partial = ticket_id[:6]  # e.g., "ADW-1"
                                    if partial not in ticket_cache:
                                        ticket_cache[partial] = []
                                    ticket_cache[partial].append(item)
                
                ticket_input = prompt(
                    "Jira ticket number (e.g., ADW-1234): ",
                    completer=TicketCompleter(ticket_cache),
                    history=InMemoryHistory()
                ).strip()
                
                if ticket_input:
                    # Extract ticket ID from input
                    ticket_match = re.search(r'ADW-\d+', ticket_input, re.IGNORECASE)
                    if ticket_match:
                        jira_ticket = ticket_match.group(0).upper()
                    else:
                        jira_ticket = ticket_input.upper()
                else:
                    print("   Using ADW-XXXX as placeholder")
                    jira_ticket = "ADW-XXXX"
            except (EOFError, KeyboardInterrupt):
                print("\n❌ Cancelled by user")
                sys.exit(1)
        elif sys.stdin.isatty():
            # Non-interactive but has TTY - ask to continue
            try:
                response = input("   Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    sys.exit(1)
            except (EOFError, KeyboardInterrupt):
                print("\n   Aborted by user")
                sys.exit(1)
            jira_ticket = "ADW-XXXX"
        else:
            print("   Running in non-interactive mode, using ADW-XXXX as placeholder")
            jira_ticket = "ADW-XXXX"
    
    print(f"🎫 Jira ticket: {jira_ticket}")
    print()
    
    # Get commits
    print("📝 Analyzing commits...")
    commits = get_commits(source_branch, target_branch, git_root)
    print(f"   Found {len(commits)} commit(s)")
    if commits:
        print("   Recent commits:")
        for commit in commits[:3]:
            print(f"     - {commit}")
    print()
    
    # Get file changes
    print("📊 Analyzing file changes...")
    file_changes = get_file_changes_summary(source_branch, target_branch, git_root)
    if file_changes:
        # Count files changed
        file_count = len([line for line in file_changes.split('\n') if line.strip() and '|' in line])
        print(f"   {file_count} file(s) changed")
        print("   Summary:")
        # Show last few lines of diff stat
        for line in file_changes.split('\n')[-5:]:
            if line.strip():
                print(f"     {line}")
    else:
        print("   No file changes detected")
    print()
    
    # Generate PR title and description
    print("✨ Generating PR content...")
    pr_title = generate_pr_title(source_branch, jira_ticket, commits)
    pr_description = generate_pr_description(jira_ticket, commits, file_changes)
    
    print()
    print("=" * 70)
    print("PR Title:")
    print("=" * 70)
    print(pr_title)
    print()
    print("=" * 70)
    print("PR Description:")
    print("=" * 70)
    print(pr_description)
    print()
    
    if args.dry_run:
        print("=" * 70)
        print("✅ Dry run complete - PR content generated above")
        print("=" * 70)
        sys.exit(0)
    
    # Validate environment variable
    if not os.environ.get('AZURE_DEVOPS_PAT'):
        print("❌ Error: AZURE_DEVOPS_PAT environment variable not set")
        print("   Please set it using: export AZURE_DEVOPS_PAT='your_token_here'")
        print()
        print("   Alternatively, you can use the generated content above with MCP tools")
        print("   or manually create the PR in Azure DevOps.")
        sys.exit(1)
    
    # Get repository ID
    print("🔍 Looking up repository...")
    repo_id = get_repository_id(REPOSITORY_NAME)
    if not repo_id:
        print("❌ Failed to get repository ID. Exiting.")
        print()
        print("   You can still use the generated content above to create the PR manually")
        sys.exit(1)
    
    print()
    
    # Create pull request
    pr_result = create_pull_request(
        repo_id=repo_id,
        source_branch=source_branch,
        target_branch=target_branch,
        title=pr_title,
        description=pr_description
    )
    
    if pr_result:
        # Superhero message already printed in create_pull_request function
        sys.exit(0)
    else:
        print()
        print("=" * 70)
        print("❌ Failed to create pull request")
        print("=" * 70)
        print()
        print("   The PR content has been generated above.")
        print("   You can manually create the PR using the title and description shown.")
        sys.exit(1)

if __name__ == "__main__":
    main()

