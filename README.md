# M&G AEM Deployment Tool

A simple tool for managing software releases to Azure Cloud platforms.

---

## What This Tool Does

This tool helps you deploy (release) code changes to different environments without using the web interface. Think of it like having a push-button system for launching updates.

**Three main environments:**
- **DEV** - Testing area for new features (deploy frequently)
- **STAGE** - Pre-release testing (more careful)
- **PRODUCTION** - Live system (most careful)

---

## Getting Started

### Step 1: Install
```bash
npm install
npm link
```

### Step 2: Set Up Your Access
```bash
mandg update --token YOUR_ACCESS_CODE
mandg check
```

Your system is now ready to use!

---

## How to Use - Common Tasks

### Deploy a Feature to Testing
```bash
mandg dev
```
The tool will show you a list of branches to choose from, then deploy your code.

### Deploy to the Pre-Release Environment
```bash
mandg stage
```
This prepares code for final release and creates a version number.

### Check if a Deployment is Complete
```bash
mandg status
```

### Approve or Reject a Deployment
```bash
mandg approval
```
A menu will appear asking if you want to approve or reject.

---

## All Available Commands

| What You Want to Do | Command |
|---|---|
| Deploy to testing | `mandg dev` |
| Deploy to pre-release | `mandg stage` |
| Check deployment status | `mandg status` |
| Watch for PR merges & auto-deploy | `mandg watch` |
| Approve/reject deployment | `mandg approval` |
| Create a pull request | `mandg create-pr` |
| Check system setup | `mandg check` |
| View recent changes | `mandg commits` |
| Manage version tags | `mandg tag` |
| Update settings | `mandg update` |

---

## Key Features Explained

### 1. **Easy Branch Selection**
When you run `mandg dev`, you'll see a dropdown menu of available branches to choose from. Just select the one you want.

### 2. **Automatic Retries**
If something goes wrong, the system automatically tries again (up to 2 times) before giving up.

### 3. **Approval Process**
Some deployments require approval before going live. The tool handles this for you with simple accept/reject options.

### 4. **Watch Mode - Auto-Deploy**
Want the system to automatically deploy when changes are merged?
```bash
mandg watch
# or
mandg dev --watch

# With custom settings
mandg watch --poll-interval 5 --delay 3
```
This keeps watching for new merged changes and deploys them automatically (polls every 10 min, waits 5 min before deploying).

### 5. **Send Notifications**
The tool can automatically notify your team on Microsoft Teams when deployments start, succeed, or fail.

### 6. **Auto-Detection**
The system automatically figures out which changes are included in each deployment.

---

## Setup Options

### Change Your Access Code
```bash
mandg update --token NEW_CODE
```

### Change Your Organization/Project
```bash
mandg update --org https://dev.azure.com/your-org --project your-project
```

### Run Custom Scripts Before/After Deployment
Create a config file at `~/.azure-deploy-aem.json` and add:
```json
{
  "hooks": {
    "before-deploy": "./scripts/pre-deploy.sh",
    "after-deploy": "./scripts/post-deploy.sh"
  }
}
```

---

## Common Deployment Options

### Deploy a Specific Branch
```bash
mandg dev --branch feature/my-feature
```

### Turn Off Notifications for This Deployment
```bash
mandg dev --no-notify
```

### Check a Specific Deployment Status
```bash
mandg status --build 12345
```

---

## Settings Stored Locally

Your configuration is saved in your home folder at `~/.azure-deploy-aem.json`. This includes:
- Your access code
- Organization details
- Notification preferences

---

## Troubleshooting

**"Access code not valid"**
- Get a new access code from your admin
- Update it with: `mandg update --token YOUR_NEW_CODE`

**"System check failed"**
- Run `mandg check` to see what's wrong
- Contact your IT team if issues persist

**"Deployment is taking too long"**
- Check the status with `mandg status`
- Deployments can take 5-30 minutes depending on size

---

## Need Help?

- Run `mandg check` - Verifies everything is set up correctly
- Run `mandg status` - Shows current deployment status
- Contact your team lead or IT support for access issues

---

**Quick Reminder:** Always test your changes in DEV before deploying to STAGE or production!