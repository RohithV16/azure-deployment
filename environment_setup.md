# Prerequisites for Running Deployment Scripts

This document outlines all the requirements and setup steps needed to run the deployment automation scripts.

## Table of Contents

- [System Requirements](#system-requirements)
- [Python Requirements](#python-requirements)
- [Azure DevOps Setup](#azure-devops-setup)
- [Environment Variables](#environment-variables)
- [Installation Steps](#installation-steps)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Operating System
- **macOS**: Fully supported (tested on macOS)
- **Linux**: Should work (Python scripts are cross-platform)
- **Windows**: Should work (may need to adjust shell commands)

### Network Access
- Internet connection required
- Access to Azure DevOps API: `https://mpcoderepo.visualstudio.com`
- Access to Microsoft Teams webhook endpoint

---

## Python Requirements

### Python Version
- **Python 3.7 or higher** is required
- Python 3.8+ recommended

### Check Your Python Version
```bash
python3 --version
```

If Python 3 is not installed:
- **macOS**: Install via Homebrew: `brew install python3`
- **Linux**: Use package manager: `sudo apt-get install python3` (Ubuntu/Debian) or `sudo yum install python3` (RHEL/CentOS)
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

### Python Packages

#### Required External Package
- **`requests`** - HTTP library for API calls

#### Built-in Modules (No Installation Needed)
The following modules are part of Python's standard library:
- `json`
- `os`
- `sys`
- `base64`
- `time`
- `argparse`
- `threading`
- `datetime`

---

## Azure DevOps Setup

### 1. Azure DevOps Access

You need access to:
- **Organization**: `mpcoderepo.visualstudio.com`
- **Project**: `DigitalExperience`
- **Repositories**: Access to the `aemaacs-life` repository

### 2. Personal Access Token (PAT)

You need to create a Personal Access Token with the following permissions:

#### Required Permissions:
- ✅ **Code (read & write)**
  - Used for: Reading repository information, creating tags, detecting PRs
- ✅ **Build (read & execute)**
  - Used for: Triggering builds, monitoring build status
- ✅ **Release (read & write)**
  - Used for: Release management operations

#### How to Create a PAT:

1. Go to Azure DevOps: `https://mpcoderepo.visualstudio.com`
2. Click on your profile picture (top right)
3. Select **"Personal access tokens"**
4. Click **"New Token"**
5. Configure the token:
   - **Name**: `Deployment Scripts` (or any descriptive name)
   - **Organization**: Select your organization
   - **Expiration**: Set appropriate expiration (recommended: 90 days or custom)
   - **Scopes**: Select the following:
     - `Code (read & write)`
     - `Build (read & execute)`
     - `Release (read & write)`
6. Click **"Create"**
7. **IMPORTANT**: Copy the token immediately (you won't be able to see it again)
8. Store it securely

#### Token Security Best Practices:
- ⚠️ **Never commit tokens to version control**
- ⚠️ **Never share tokens in chat or email**
- ✅ Store tokens as environment variables only
- ✅ Use token expiration dates
- ✅ Rotate tokens periodically

---

## Environment Variables

### Required Environment Variable

#### `AZURE_DEVOPS_PAT`
Your Azure DevOps Personal Access Token.

### Setting Environment Variables

#### macOS / Linux (Bash/Zsh)

**Temporary (Current Session Only):**
```bash
export AZURE_DEVOPS_PAT='your_token_here'
```

**Permanent (Persists Across Sessions):**

For **Zsh** (macOS default):
```bash
echo 'export AZURE_DEVOPS_PAT="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

For **Bash**:
```bash
echo 'export AZURE_DEVOPS_PAT="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

#### Windows (PowerShell)

**Temporary (Current Session Only):**
```powershell
$env:AZURE_DEVOPS_PAT = "your_token_here"
```

**Permanent (User-level):**
```powershell
[System.Environment]::SetEnvironmentVariable('AZURE_DEVOPS_PAT', 'your_token_here', 'User')
```

**Permanent (System-level - requires admin):**
```powershell
[System.Environment]::SetEnvironmentVariable('AZURE_DEVOPS_PAT', 'your_token_here', 'Machine')
```

#### Verify Environment Variable is Set

**macOS / Linux:**
```bash
echo $AZURE_DEVOPS_PAT
```

**Windows (PowerShell):**
```powershell
$env:AZURE_DEVOPS_PAT
```

---

## Installation Steps

### Step 1: Clone or Download Scripts

Navigate to the deployment scripts directory:
```bash
cd "/Users/grahat01/Desktop/ Automation/deployment-scripts"
```

Or if using a different location:
```bash
cd /path/to/deployment-scripts
```

### Step 2: Install Python Dependencies

Install the `requests` library:
```bash
pip3 install requests
```

**Note**: If you encounter permission errors, use:
```bash
pip3 install --user requests
```

Or use a virtual environment (recommended):
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install requests
```

### Step 3: Set Environment Variable

Set your Azure DevOps PAT token (see [Environment Variables](#environment-variables) section above).

### Step 4: Make Scripts Executable (Optional, macOS/Linux)

```bash
chmod +x deployment_automation.py
chmod +x deployment_dev.py
chmod +x deployment_stage.py
chmod +x run_deployment_check.command
```

---

## Verification

### Verify Python Installation
```bash
python3 --version
# Should output: Python 3.7.x or higher
```

### Verify Python Packages
```bash
python3 -c "import requests; print(requests.__version__)"
# Should output: requests version number
```

### Verify Environment Variable
```bash
# macOS/Linux
echo $AZURE_DEVOPS_PAT

# Windows (PowerShell)
$env:AZURE_DEVOPS_PAT
```

If the output is empty, the environment variable is not set.

### Test Script Connection

Run a simple test to verify Azure DevOps connection:
```bash
python3 -c "
import os
import requests
import base64

pat = os.environ.get('AZURE_DEVOPS_PAT')
if not pat:
    print('❌ AZURE_DEVOPS_PAT not set')
    exit(1)

pat_encoded = base64.b64encode(f':{pat}'.encode()).decode()
headers = {
    'Authorization': f'Basic {pat_encoded}',
    'Content-Type': 'application/json'
}

url = 'https://mpcoderepo.visualstudio.com/DigitalExperience/_apis/projects?api-version=7.0'
response = requests.get(url, headers=headers)

if response.status_code == 200:
    print('✅ Connection successful!')
else:
    print(f'❌ Connection failed: {response.status_code}')
    print(response.text)
"
```

---

## Troubleshooting

### Issue: Python 3 Not Found

**Error:**
```
python3: command not found
```

**Solution:**
- Install Python 3 (see [Python Requirements](#python-requirements))
- Verify installation: `python3 --version`
- On some systems, Python 3 may be available as `python` instead of `python3`

### Issue: Module 'requests' Not Found

**Error:**
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
pip3 install requests
```

If using a virtual environment, make sure it's activated:
```bash
source venv/bin/activate  # macOS/Linux
pip install requests
```

### Issue: AZURE_DEVOPS_PAT Not Set

**Error:**
```
❌ AZURE_DEVOPS_PAT environment variable not set
```

**Solution:**
1. Verify the environment variable is set:
   ```bash
   echo $AZURE_DEVOPS_PAT  # macOS/Linux
   ```
2. If empty, set it (see [Environment Variables](#environment-variables))
3. If set in `.zshrc` or `.bashrc`, make sure to restart your terminal or run `source ~/.zshrc`

### Issue: Permission Denied

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
- Check file permissions: `ls -l deployment_*.py`
- Make scripts executable: `chmod +x deployment_*.py`
- For pip install issues, use `pip3 install --user requests`

### Issue: Azure DevOps Authentication Failed

**Error:**
```
❌ Failed to get build information
401 Unauthorized
```

**Solution:**
1. Verify your PAT token is correct
2. Check if the token has expired
3. Verify the token has the required permissions (Code read/write, Build read/execute, Release read/write)
4. Regenerate the token if necessary

### Issue: Network Connection Error

**Error:**
```
ConnectionError: Failed to establish connection
```

**Solution:**
1. Check your internet connection
2. Verify you can access `https://mpcoderepo.visualstudio.com` in a browser
3. Check if you're behind a corporate firewall/proxy
4. Verify network settings allow outbound HTTPS connections

### Issue: Repository Not Found

**Error:**
```
❌ Repository 'aemaacs-life' not found
```

**Solution:**
1. Verify you have access to the `DigitalExperience` project
2. Verify the repository name is correct
3. Check your PAT token has Code (read) permissions
4. Verify you're using the correct organization URL

---

## Quick Checklist

Before running the scripts, verify:

- [ ] Python 3.7+ is installed (`python3 --version`)
- [ ] `requests` package is installed (`pip3 install requests`)
- [ ] `AZURE_DEVOPS_PAT` environment variable is set
- [ ] PAT token has required permissions (Code, Build, Release)
- [ ] You have access to Azure DevOps organization and project
- [ ] Network connection is available
- [ ] Scripts are in the correct directory

---

## Next Steps

Once all prerequisites are met, you can:

1. Read the [README.md](README.md) for detailed usage instructions
2. Check [QUICK_START.md](QUICK_START.md) for quick reference
3. Run your first deployment:
   ```bash
   python3 deployment_automation.py --pipeline dev
   ```

---

## Support

If you encounter issues not covered in this document:

1. Check the [README.md](README.md) troubleshooting section
2. Verify all prerequisites are met using the checklist above
3. Contact your team lead or DevOps administrator
4. Check Azure DevOps API documentation: [Azure DevOps REST API](https://docs.microsoft.com/en-us/rest/api/azure/devops/)

---

**Last Updated**: 2024
**Scripts Version**: 1.0

