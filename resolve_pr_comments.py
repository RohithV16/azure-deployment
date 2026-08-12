#!/usr/bin/env python3
"""
Resolve All Comments on a Pull Request
=======================================
Lists your active PRs in Azure DevOps, lets you select one interactively,
and resolves all active comment threads on it in parallel.

Usage:
    python3 resolve_pr_comments.py

Authentication (in order of precedence):
    1. AZURE_DEVOPS_PAT environment variable
    2. FALLBACK_PAT variable below (set it directly in this file)

Requirements:
    - requests
    - prompt_toolkit
    - term-background

Author: Rohith Venati
"""

import sys
import os
import concurrent.futures
import threading

# =============================================================================
# CONFIGURATION — Set your PAT here if not using the environment variable
# =============================================================================
# Priority: AZURE_DEVOPS_PAT env var > FALLBACK_PAT below
# To use this fallback, replace the empty string with your PAT:
#   FALLBACK_PAT = "your-personal-access-token"
# =============================================================================
FALLBACK_PAT = ""

if sys.prefix == sys.base_prefix:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, "venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import requests
import base64
import term_background
from typing import Optional, List, Tuple
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application import Application

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

ORG_URL = "https://mpcoderepo.visualstudio.com"
PROJECT = "DigitalExperience"
REPOSITORY_NAME = "aemaacs-life"
MAX_WORKERS = 5


class ApiClient:
    def __init__(self):
        pat_token = os.environ.get('AZURE_DEVOPS_PAT') or FALLBACK_PAT
        if not pat_token:
            print(f"{RED}❌ No PAT found. Set AZURE_DEVOPS_PAT env var or FALLBACK_PAT in this script.{RESET}")
            sys.exit(1)
        pat_encoded = base64.b64encode(f":{pat_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {pat_encoded}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()

    def get(self, url):
        return self.session.get(url, headers=self.headers)

    def patch(self, url, json):
        return self.session.patch(url, headers=self.headers, json=json)


def get_repository_id(client, repo_name=None):
    repos_url = f"{ORG_URL}/{PROJECT}/_apis/git/repositories?api-version=7.0"
    try:
        response = client.get(repos_url)
        if response.status_code == 200:
            repos_data = response.json()
            if repo_name:
                for repo in repos_data.get('value', []):
                    if repo.get('name') == repo_name:
                        return repo.get('id')
                print(f"{RED}❌ Repository '{repo_name}' not found{RESET}")
                return None
            else:
                return repos_data['value'][0].get('id')
        else:
            print(f"{RED}❌ Failed to get repositories: {response.status_code}{RESET}")
            return None
    except Exception as e:
        print(f"{RED}❌ Error getting repository ID: {e}{RESET}")
        return None


def get_authenticated_user_id(client):
    conn_url = f"{ORG_URL}/_apis/ConnectionData?api-version=7.1-preview.1"
    try:
        response = client.get(conn_url)
        if response.status_code == 200:
            return response.json()['authenticatedUser']['id']
        else:
            print(f"{RED}❌ Failed to get user info: {response.status_code}{RESET}")
            return None
    except Exception as e:
        print(f"{RED}❌ Error getting user info: {e}{RESET}")
        return None


def get_my_prs(client, repo_id, user_id):
    prs_url = (
        f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}/pullrequests"
        f"?api-version=7.0"
        f"&searchCriteria.creatorId={user_id}"
        f"&searchCriteria.status=active"
    )
    try:
        response = client.get(prs_url)
        if response.status_code == 200:
            return response.json().get('value', [])
        else:
            print(f"{RED}❌ Failed to get PRs: {response.status_code}{RESET}")
            return []
    except Exception as e:
        print(f"{RED}❌ Error getting PRs: {e}{RESET}")
        return []


def get_threads(client, repo_id, pr_id):
    threads_url = (
        f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
        f"/pullRequests/{pr_id}/threads?api-version=7.0"
    )
    try:
        response = client.get(threads_url)
        if response.status_code == 200:
            return response.json().get('value', [])
        else:
            print(f"{RED}❌ Failed to get threads for PR #{pr_id}: {response.status_code}{RESET}")
            return []
    except Exception as e:
        print(f"{RED}❌ Error getting threads: {e}{RESET}")
        return []


def resolve_thread(client, repo_id, pr_id, thread_id) -> bool:
    thread_url = (
        f"{ORG_URL}/{PROJECT}/_apis/git/repositories/{repo_id}"
        f"/pullRequests/{pr_id}/threads/{thread_id}?api-version=7.0"
    )
    try:
        response = client.patch(thread_url, {"status": "closed"})
        return response.status_code == 200
    except Exception:
        return False


def resolve_threads_parallel(client, repo_id, pr_id, active_threads) -> Tuple[int, int]:
    total = len(active_threads)
    resolved = [0]
    failed = [0]
    lock = threading.Lock()

    def resolve_one(thread):
        nonlocal resolved, failed
        thread_id = thread.get('id')
        ok = resolve_thread(client, repo_id, pr_id, thread_id)
        with lock:
            if ok:
                resolved[0] += 1
            else:
                failed[0] += 1
            done = resolved[0] + failed[0]
            pct = int(done / total * 100)
            bar_len = 20
            filled = int(bar_len * done / total)
            bar = "▓" * filled + "░" * (bar_len - filled)
            sys.stdout.write(
                f"\r   {bar} {done}/{total}  ({pct}%)  "
                f"{GREEN}{resolved[0]} ok{RESET}"
                f"{f' {RED}{failed[0]} failed{RESET}' if failed[0] else ''}  "
            )
            sys.stdout.flush()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(resolve_one, t) for t in active_threads]
        concurrent.futures.wait(futures)

    print()
    return resolved[0], failed[0]


def select_from_menu(options: List[str], title: str = "Select an option", default_index: int = 0) -> Optional[str]:
    if not options:
        return None
    selected_index = [default_index if 0 <= default_index < len(options) else 0]

    def get_formatted_text():
        result = [("class:title", f"\n{title}:\n"), ("", "\n")]
        for i, option in enumerate(options):
            if i == selected_index[0]:
                result.append(("class:selected", f"  > {option}\n"))
            else:
                result.append(("class:option", f"    {option}\n"))
        result.append(("", "\n"))
        result.append(("class:instruction", "  Use ↑/↓ arrows to navigate, Enter to select, Ctrl+C to cancel\n"))
        return result

    control = FormattedTextControl(get_formatted_text, show_cursor=False)
    kb = KeyBindings()

    @kb.add('up')
    def move_up(event):
        selected_index[0] = max(0, selected_index[0] - 1)
        event.app.invalidate()

    @kb.add('down')
    def move_down(event):
        selected_index[0] = min(len(options) - 1, selected_index[0] + 1)
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
        pass

    if is_dark:
        style = Style([
            ('title', 'bold #00ff00'),
            ('selected', 'bg:#00ff00 #000000 bold'),
            ('option', '#ffffff'),
            ('instruction', '#888888 italic'),
        ])
    else:
        style = Style([
            ('title', 'bold #00008b'),
            ('selected', 'bg:#00008b #ffffff bold'),
            ('option', '#000000'),
            ('instruction', '#444444 italic'),
        ])

    layout = Layout(Window(content=control))
    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False, mouse_support=False)
    try:
        return app.run()
    except KeyboardInterrupt:
        return None


def main():
    print(f"{'=' * 60}{RESET}")
    print(f"{BOLD}   PR Comment Resolver{RESET}")
    print(f"{'=' * 60}{RESET}\n")

    client = ApiClient()

    repo_id = get_repository_id(client, REPOSITORY_NAME)
    if not repo_id:
        sys.exit(1)

    user_id = get_authenticated_user_id(client)
    if not user_id:
        sys.exit(1)

    print(f"{CYAN}🔍 Fetching your active PRs...{RESET}")
    prs = get_my_prs(client, repo_id, user_id)

    if not prs:
        print(f"{YELLOW}⚠️  No active PRs found for your account.{RESET}")
        sys.exit(0)

    pr_labels = []
    for pr in prs:
        pr_id = pr.get('pullRequestId')
        title = pr.get('title', '')
        source = pr.get('sourceRefName', '').replace('refs/heads/', '')
        target = pr.get('targetRefName', '').replace('refs/heads/', '')
        pr_labels.append(f"PR #{pr_id}: {title} ({source} → {target})")

    selected_label = select_from_menu(pr_labels, title="Select a PR to resolve all comments")
    if not selected_label:
        print(f"{YELLOW}⚠️  No PR selected. Exiting.{RESET}")
        sys.exit(0)

    selected_index = pr_labels.index(selected_label)
    selected_pr = prs[selected_index]
    pr_id = selected_pr.get('pullRequestId')
    pr_title = selected_pr.get('title', '')

    print(f"\n{CYAN}📋 Fetching threads for PR #{pr_id}: {pr_title}...{RESET}")
    threads = get_threads(client, repo_id, pr_id)

    active_threads = [t for t in threads if t.get('status') == 'active']
    if not active_threads:
        print(f"{GREEN}✅ No active threads to resolve on PR #{pr_id}.{RESET}")
        sys.exit(0)

    print(f"   Resolving {len(active_threads)} active thread(s) ({MAX_WORKERS} workers)...")

    resolved, failed = resolve_threads_parallel(client, repo_id, pr_id, active_threads)

    print(f"\n{GREEN}{BOLD}✅ Done!{RESET}")
    print(f"{GREEN}   Resolved {resolved} of {len(active_threads)} active thread(s) on PR #{pr_id}.{RESET}")
    if failed:
        print(f"{RED}   Failed to resolve {failed} thread(s).{RESET}")


if __name__ == "__main__":
    main()
