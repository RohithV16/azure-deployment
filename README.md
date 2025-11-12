# 🚀 Auto Pull Request Creator for Azure DevOps

This Python script automates **pull request creation** in **Azure DevOps** using your local Git commits and standardized Merkle PR conventions.  
It extracts the **Jira ticket ID** from your branch name, generates a formatted **title and description**, and can open the PR automatically in your browser — complete with fun superhero themes.

---

## ✨ Features

- Auto-detects Jira ID from branch name (e.g., `feature/ADW-1234-improve-ui`)
- Generates PR title and description from Git commits and diffs
- Integrates directly with **Azure DevOps REST API**
- Animated success/failure themes (Marvel, Star Wars, Matrix, etc.)
- Merge conflict detection with helpful resolution guidance
- Supports **interactive menus** and autocomplete for ticket IDs
- Works in both **interactive** and **non-interactive** (CI/CD) modes

---

## ⚙️ Environment Setup

You can set up the environment **either using a virtual environment** or **directly (global installation)**.

---

```bash

This guide provides the minimum steps to install and run the **`create_pr.py`** script for automating Azure DevOps pull requests.

---

## Setup

You only need to do this once.

### 1. Set Your Environment Variable

The script requires an **Azure DevOps Personal Access Token (PAT)** to run.

```bash
# Set this in your terminal session
export AZURE_DEVOPS_PAT="your_personal_access_token_here"

# Inside create_pr.py, find this line and change it:
GIT_REPO_PATH = "/path/to/your/local/aemaacs-life/repo"


# For most systems (Linux, Windows)
pip3 install -r requirements.txt

# --- OR ---
# If you are on macOS, you may need the --break-system-packages flag
pip3 install -r requirements.txt --break-system-packages


```

### Basic Command
```bash
python3 create_pr.py

python3 create_pr.py --dry-run

python3 create_pr.py --master-to-dev
```


## 🔧 Troubleshooting During Dependency Installation

| Issue | Possible Cause | Solution |
|--------|----------------|-----------|
| `pip: command not found` | pip not installed | Install pip using `python3 -m ensurepip --upgrade` |
| `ModuleNotFoundError: No module named 'requests'` | Missing dependency | Run `pip install requests` |
| `Permission denied` | Installing globally without permissions | Use `pip install --user <package>` or run in virtualenv |
| `SSL Error / Connection Timeout` | Network proxy or SSL issue | Try `pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host=files.pythonhosted.org requests prompt_toolkit` |
| `python3: command not found` | Python not in PATH | Ensure Python 3 is installed and added to PATH |

---


## 🚀 Usage

Run the script from your project directory (or specify `--work-dir`).


This will:
- Detect your current Git branch  
- Extract the Jira ID from the branch name  
- Generate a formatted PR title and description  
- Create the PR in Azure DevOps (default target: `dev`)

---

### Command Options

| Option | Description |
|--------|--------------|
| `--target <branch>` | Specify target branch (default: `dev`) |
| `--work-dir <path>` | Manually specify the Git repository path |
| `--dry-run` | Generate PR title and description only (no creation) |
| `--interactive` | Enable interactive selection (branch, ticket, etc.) |
| `--master-to-dev` | Create master → dev PR with predefined content |

---

### Example Commands

1. **Create PR from current branch → dev**
   ```bash
   python3 create_pr.py
   ```

2. **Preview PR content without creating it**
   ```bash
   python3 create_pr.py --dry-run
   ```

3. **Master → Dev sync PR**
   ```bash
   python3 create_pr.py --master-to-dev
   ```

4. **Run with interactive prompts**
   ```bash
   python3 create_pr.py --interactive
   ```

5. **Specify custom repository path**
   ```bash
   python3 create_pr.py --work-dir /Users/<username>/Documents/AEM/aemaacs-life
   ```

---

## 🧠 Example Output

```
======================================================================
PR Title:
======================================================================
ADW-1542 [Merkle] Update Asset Upload Logic

======================================================================
PR Description:
======================================================================
## What does this PR do?
Updates JavaScript logic for asset upload validation.

---

## What are the relevant tickets?
[ADW-1542](https://mandg.atlassian.net/browse/ADW-1542)
```

---

## 🧰 Troubleshooting

| Issue | Cause | Solution |
|-------|--------|-----------|
| `AZURE_DEVOPS_PAT not set` | Missing token | Set `AZURE_DEVOPS_PAT` as shown above |
| `Could not find git repository` | Script not in repo path | Use `--work-dir` or export `GIT_REPO_PATH` |
| `prompt_toolkit not found` | Missing dependency | Run `pip install prompt_toolkit` |
| `Failed to create PR` | Invalid PAT or wrong repo | Check PAT permissions and repository name |
| `fatal: not a git repository` | Script not run inside git project | Navigate into your git repo or specify `--work-dir` |

---

## 💡 Tips

- Works best when branch names follow: `feature/ADW-XXXX-description`
- Interactive mode supports arrow key navigation and auto-completion
- You can preview everything with `--dry-run` before pushing

---

## 🦸 Author

**Rohith V && Gaurav Rahate **  
Senior AEM Developer — Merkle  
