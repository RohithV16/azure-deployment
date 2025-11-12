# Prerequisites for Running create_pr.py

Quick reference guide for setting up and using the `create_pr.py` script.

## Table of Contents

- [Required Variables](#required-variables)
- [Configuration](#configuration)
- [Commands](#commands)
  - [Install Dependencies](#install-dependencies)
  - [Basic Usage](#basic-usage)
  - [Interactive Autocomplete Features](#interactive-autocomplete-features)
- [Quick Checklist](#quick-checklist)
- [Troubleshooting](#troubleshooting)

---

## Required Variables

### Environment Variable

**`AZURE_DEVOPS_PAT`** - Your Azure DevOps Personal Access Token

**Set it:**
```bash
export AZURE_DEVOPS_PAT='your_token_here'
```

**Verify it's set:**
```bash
echo $AZURE_DEVOPS_PAT
```

---

## Configuration

Edit the configuration section at the top of `create_pr.py`:

```python
# Azure DevOps configuration
ORG_URL = "https://mpcoderepo.visualstudio.com"
ORG_NAME = "mpcoderepo"
PROJECT = "DigitalExperience"
REPOSITORY_NAME = "aemaacs-life"  # Change if using different repo

# Git repository configuration
# Set this to your local git repository path
GIT_REPO_PATH = "/Users/rvenat01/Documents/AEM/mandg/aemaacs-life"  # CHANGE THIS

# Default target branch
DEFAULT_TARGET_BRANCH = "dev"  # Change if your default target is different

# Jira base URL
JIRA_BASE_URL = "https://mandg.atlassian.net/browse"
```

### Required Configuration Changes

1. **`GIT_REPO_PATH`** - Set to your local git repository path
   ```python
   GIT_REPO_PATH = "/path/to/your/git/repository"
   ```

2. **`DEFAULT_TARGET_BRANCH`** (Optional) - Change if default target is not "dev"
   ```python
   DEFAULT_TARGET_BRANCH = "stage"  # or "main", "master", etc.
   ```

3. **`REPOSITORY_NAME`** (Optional) - Change if using different Azure DevOps repository
   ```python
   REPOSITORY_NAME = "your-repo-name"
   ```

---

## Commands

### Install Dependencies

**For macOS (with externally-managed environment):**
```bash
pip3 install --break-system-packages -r requirements.txt
```

**For Linux/other systems:**
```bash
pip3 install -r requirements.txt
```

Or install individually:
```bash
# macOS
pip3 install --break-system-packages requests prompt-toolkit

# Linux/other
pip3 install requests prompt-toolkit
```

**Note:** On macOS with Homebrew Python, you may need to use `--break-system-packages` flag. Alternatively, you can use a virtual environment if preferred.

### Basic Usage

**Create PR from current branch to dev (with autocomplete):**
```bash
python3 create_pr.py
```
*Note: Autocomplete is automatically enabled in interactive terminals*

**Create PR to specific target branch:**
```bash
python3 create_pr.py --target stage
```

**Explicitly enable interactive mode with autocomplete:**
```bash
python3 create_pr.py --interactive
```
*This enables autocomplete prompts for:*
- *Target branch selection (suggestions from Azure DevOps)*
- *Jira ticket number (if not found in branch name)*

**Dry run (preview without creating PR):**
```bash
python3 create_pr.py --dry-run
```

**Specify different repository:**
```bash
python3 create_pr.py --repo my-repo-name
```

**Specify git repository location:**
```bash
python3 create_pr.py --work-dir /path/to/git/repo
```

**Combine options:**
```bash
python3 create_pr.py --target stage --interactive --repo my-repo
```

### Interactive Autocomplete Features

When running in interactive mode (automatic in TTY or with `--interactive` flag):

1. **Target Branch Autocomplete**
   - Type to filter branches from Azure DevOps
   - Press Tab to cycle through suggestions
   - Press Enter to select

2. **Jira Ticket Autocomplete**
   - If ticket ID not found in branch name, you'll be prompted
   - Type partial ticket number (e.g., "ADW-1") to see suggestions
   - Suggestions are fetched from recent work items
   - Press Tab to cycle through suggestions
   - Press Enter to select

**Example Interactive Session:**
```
Target branch [dev]: sta<Tab>
  → stage
  → staging
  → stable
Press Enter to select "stage"

Jira ticket number (e.g., ADW-1234): ADW-1<Tab>
  → ADW-1234: Fix login issue
  → ADW-1456: Update TOC component
  → ADW-1890: Add new feature
Press Enter to select "ADW-1234"
```

### Branch Name Format

The script extracts Jira ticket IDs from branch names. Use this format:
```
feature/ADW-XXXX-description
bugfix/ADW-XXXX-description
defect/ADW-XXXX-description
ADW-XXXX-description
```

**Examples:**
- `feature/ADW-1495-toc-dynamic-variation` ✅
- `bugfix/ADW-1234-fix-login-issue` ✅
- `defect/ADW-4409-toc-publish-issue` ✅
- `develop` ❌ (no ticket ID, will use ADW-XXXX placeholder)

---

## Quick Checklist

Before running `create_pr.py`:

- [ ] Python 3.7+ installed (`python3 --version`)
- [ ] Dependencies installed (`pip3 install --break-system-packages -r requirements.txt` for macOS)
  - [ ] `requests` package
  - [ ] `prompt-toolkit` package (for autocomplete)
- [ ] `AZURE_DEVOPS_PAT` environment variable set
- [ ] `GIT_REPO_PATH` configured in script
- [ ] Git repository cloned locally
- [ ] On a feature branch (not main/master)
- [ ] Branch name includes Jira ticket ID (e.g., `ADW-XXXX`) - *or use interactive mode to enter manually*

---

## Troubleshooting

### AZURE_DEVOPS_PAT Not Set
```bash
export AZURE_DEVOPS_PAT='your_token_here'
```

### Could Not Find Git Repository
Set `GIT_REPO_PATH` in the script configuration or use:
```bash
python3 create_pr.py --work-dir /path/to/git/repo
```

### Module 'requests' or 'prompt_toolkit' Not Found

**For macOS:**
```bash
pip3 install --break-system-packages -r requirements.txt
```

**For Linux/other systems:**
```bash
pip3 install -r requirements.txt
```

Or install individually:
```bash
# macOS
pip3 install --break-system-packages requests prompt-toolkit

# Linux/other
pip3 install requests prompt-toolkit
```

### Autocomplete Not Working
- Ensure `prompt-toolkit` is installed:
  ```bash
  # macOS
  pip3 install --break-system-packages prompt-toolkit
  
  # Linux/other
  pip3 install prompt-toolkit
  ```
- Check that `AZURE_DEVOPS_PAT` is set (required for fetching suggestions)
- Try running with `--interactive` flag explicitly
- In non-interactive environments (scripts/pipes), autocomplete is disabled automatically

### Branch Not Found in Azure DevOps
Push your branch to remote:
```bash
git push origin your-branch-name
```

### No Jira Ticket ID in Branch Name
**Option 1:** Use a branch name that includes a Jira ticket ID:
```bash
git checkout -b feature/ADW-1495-your-description
```

**Option 2:** Use interactive mode - the script will prompt you to enter the ticket number with autocomplete:
```bash
python3 create_pr.py --interactive
```
*The script will search for recent tickets and provide autocomplete suggestions*

---

**Script File**: `create_pr.py`
