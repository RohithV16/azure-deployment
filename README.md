# 🚀 Azure Devops Python Scripts

This Python script automates **pull request creation** in **Azure DevOps** using your local Git commits and standardized Merkle PR conventions.  
It extracts the **Jira ticket ID** from your branch name, generates a formatted **title and description**, and can open the PR automatically in your browser.

---

## ⚙️ Setup (One-Time Configuration)

### 1. Get Your Azure DevOps Personal Access Token (PAT)

1. Go to Azure DevOps → User Settings → Personal Access Tokens
2. Create a new token with **Code (Read & Write)** permissions
3. Copy the token (you won't see it again!)

### 2. Configure Environment Variables Permanently on Mac

Open your shell configuration file:

```bash
# For zsh (default on modern macOS)
nano ~/.zshrc

# For bash (older macOS versions)
nano ~/.bash_profile
```

Add these lines at the end of the file:

```bash
# Azure DevOps Configuration
export AZURE_DEVOPS_PAT="your_personal_access_token_here"
export GIT_REPO_PATH="/path/to/your/local/aemaacs-life/repo"
```

Save and exit (`Ctrl + X`, then `Y`, then `Enter`)

Apply the changes:

```bash
# For zsh
source ~/.zshrc

# For bash
source ~/.bash_profile
```

**Verify it worked:**
```bash
echo $AZURE_DEVOPS_PAT
# Should display your token
```

### 3. Install Dependencies

```bash
pip3 install -r requirements.txt
```

**If you get an error**, try:
```bash
pip3 install -r requirements.txt --break-system-packages
```

---

## 🚀 Usage

### Create Pull Request (create_pr.py)

This script **always runs in interactive mode** - it will automatically prompt you to select the target branch.

```bash
# Create PR from current branch (interactive - will prompt for target)
python3 create_pr.py

# Preview PR without creating it
python3 create_pr.py --dry-run

# Create master → dev sync PR
python3 create_pr.py --master-to-dev

# Specify custom repository path
python3 create_pr.py --work-dir /path/to/repo
```

### Pipeline Deployment Automation

Automates deployment to **DEV** (dev branch) and **STAGE** (master branch with release tagging) environments.

```bash
# Run DEV deployment workflow
python3 deployment_dev.py

# Run STAGE deployment workflow
python3 deployment_stage.py
```

### Command Options Reference

**create_pr.py:**
| Option | Description |
|--------|--------------|
| `--work-dir <path>` | Manually specify the Git repository path |
| `--dry-run` | Generate PR title and description only (no creation) |
| `--master-to-dev` | Create master → dev PR with predefined content |

**deployment_dev.py & deployment_stage.py:**
| Option | Description |
|--------|--------------|
| No additional options | Simply run the script to start deployment automation |

---

## 🧰 Troubleshooting

| Issue | Solution |
|-------|----------|
| `AZURE_DEVOPS_PAT not set` | Make sure you added `export AZURE_DEVOPS_PAT="..."` to `~/.zshrc` or `~/.bash_profile` and ran `source ~/.zshrc` |
| Environment variables not persisting | Ensure you edited the correct file (`~/.zshrc` for zsh, `~/.bash_profile` for bash) and restarted your terminal |
| `Could not find git repository` | Set `GIT_REPO_PATH` environment variable or use `--work-dir` option |
| `pip: command not found` | Install pip: `python3 -m ensurepip --upgrade` |
| `ModuleNotFoundError` | Run `pip3 install -r requirements.txt` again |
| `Permission denied` | Use `pip3 install --user -r requirements.txt` |

---

## 💡 Tips

- Branch names should follow: `feature/ADW-XXXX-description`
- Use `--dry-run` to preview PR content before creating
- Interactive mode supports arrow key navigation
- Variables in `~/.zshrc` or `~/.bash_profile` persist permanently across terminal sessions

---

## 🦸 Authors

**Rohith V & Gaurav Rahate**  
Senior AEM Developers — Merkle
