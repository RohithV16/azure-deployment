# PR Comment Resolver

Lists your active PRs in Azure DevOps, lets you pick one interactively, and resolves all comment threads on it in parallel.

## Usage

```bash
python3 resolve_pr_comments.py
```

### What happens

1. Fetches all active PRs you created
2. Shows an interactive menu (↑/↓ arrows, Enter to select)
3. Fetches all comment threads on the selected PR
4. Resolves every active thread concurrently (5 workers)
5. Displays a live progress bar and summary

## Authentication

Set your Azure DevOps PAT in one of these ways (checked in order):

### Option 1 — Environment variable (recommended)

Create a token at: [https://mpcoderepo.visualstudio.com/_usersSettings/tokens](https://mpcoderepo.visualstudio.com/_usersSettings/tokens)

```bash
export AZURE_DEVOPS_PAT="your-personal-access-token"
```

Add it to `~/.zshrc` or `~/.bash_profile` to make it permanent.

### Option 2 — Hardcoded in the script

Open `resolve_pr_comments.py` and set the `FALLBACK_PAT` variable at the top:

```python
FALLBACK_PAT = "your-personal-access-token"
```

> ⚠️ If you hardcode your PAT, make sure not to commit the file to git!

## Requirements

```
requests>=2.32.5
prompt-toolkit>=3.0.52
term-background>=1.0.5
```

Install with:

```bash
pip3 install -r requirements.txt
```

## How it works

| Step | API call |
|------|----------|
| Get repo ID | `GET /_apis/git/repositories` |
| Get your user ID | `GET /_apis/ConnectionData` |
| List your PRs | `GET /.../pullRequests?creatorId={id}&status=active` |
| Get threads | `GET /.../pullRequests/{id}/threads` |
| Resolve thread | `PATCH /.../threads/{id} {"status": "closed"}` |

Threads are resolved in parallel using `ThreadPoolExecutor` (5 workers by default) with a `requests.Session()` for connection reuse.
