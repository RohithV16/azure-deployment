# M&G AEM Azure Deployment CLI (`mandg`)

A pure JavaScript CLI for managing Azure DevOps deployments via REST API.

## Installation

```bash
npm install
npm link
```

## Quick Start

```bash
# First-time setup
mandg update --token <your_pat>
mandg check   # Validate configuration
```

## Configuration

Configuration is stored in `~/.azure-deploy-aem.json`.

```bash
# Update PAT
mandg update --token <your_pat>

# Update organization/project
mandg update --org https://dev.azure.com/your-org --project your-project

# Update pipeline IDs
mandg update --dev-id 3274 --stage-id 3308
```

---

## Commands

### Deployment Commands

| Command | Description |
|---------|-------------|
| `mandg dev` | Trigger DEV pipeline deployment |
| `mandg stage` | Trigger STAGE pipeline deployment (with release tagging) |
| `mandg dev --watch` | Watch mode - auto-deploy when PRs merge to dev |
| `mandg check` | Validate environment, PAT, and permissions |

### Pull Request Commands

| Command | Description |
|---------|-------------|
| `mandg create-pr` | Create a pull request with auto-generated title/description |
| `mandg commits` | Show PRs merged after a specific commit |

### Approval Commands

| Command | Description |
|---------|-------------|
| `mandg approval` | Interactive approval/rejection (dropdown) |
| `mandg approve --build <id>` | Approve a specific deployment |
| `mandg reject --build <id>` | Reject a deployment |
| `mandg approvals` | List pending approvals |

### Utility Commands

| Command | Description |
|---------|-------------|
| `mandg status` | Check pipeline/build status |
| `mandg tag` | Manage release tags |
| `mandg rotate-token` | Rotate PAT token securely |
| `mandg update` | Update configuration |

---

## Features

### 1. Feature Branch Deployment
Deploy any feature branch to DEV with interactive branch selection.

```bash
# Interactive mode - select from dropdown
mandg dev

# Direct branch deployment
mandg dev --branch feature/ADW-1234
```

### 2. Auto-Retry on Failure
Failed builds automatically retry up to 2 times with 30-second delays.

### 3. Approval Workflow
- Auto-approve if you have permissions
- Wait for external approval (max 2 hours)
- Interactive approval/rejection via `mandg approval`

### 4. Watch Mode
Automatically deploy when PRs merge to dev branch.

```bash
# Watch for merged PRs (polls every 10 min, waits 5 min before deploy)
mandg dev --watch

# Custom intervals
mandg dev --watch --poll-interval 5 --delay 3
```

### 5. Custom Hooks
Run scripts before/after deployments.

In `~/.azure-deploy-aem.json`:
```json
{
  "hooks": {
    "pre-deploy": "./scripts/pre-deploy.sh",
    "post-deploy": "./scripts/post-deploy.sh"
  }
}
```

Available environment variables:
- `DEPLOY_PIPELINE` - DEV or STAGE
- `DEPLOY_BRANCH` - Branch name
- `DEPLOY_STATUS` - succeeded/failed
- `DEPLOY_BUILD_ID` - Build ID

### 6. Teams Notifications
Automatic notifications on deployment start/success/failure.

### 7. PR Auto-Detection
Automatically detect which PRs are included in deployment.

---

## Command Options

### `dev`
| Option | Description |
|--------|-------------|
| `--branch <name>` | Feature branch to deploy |
| `--watch` | Watch mode for auto-deploy |
| `--poll-interval <min>` | Poll interval (default: 10) |
| `--delay <min>` | Delay after PR merge (default: 5) |
| `--no-notify` | Skip notifications |
| `--no-pr-detect` | Skip PR detection |

### `stage`
| Option | Description |
|--------|-------------|
| `--no-notify` | Skip notifications |
| `--no-pr-detect` | Skip PR detection |
| `--no-tag` | Skip release tag |

### `status`
| Option | Description |
|--------|-------------|
| `-d, --definition-id <id>` | Build Definition ID |
| `-b, --build-id <id>` | Specific Build ID |
| `--dev` | Check DEV pipeline |
| `--stage` | Check STAGE pipeline |

### `create-pr`
| Option | Description |
|--------|-------------|
| `-s, --source <branch>` | Source branch |
| `-t, --target <branch>` | Target branch (default: dev) |
| `--dry-run` | Preview without creating |
| `--master-to-dev` | Master-to-dev sync template |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AZURE_DEVOPS_PAT` | PAT token (alternative to config file) |

---

## Technical Details

- Pure JavaScript/Node.js - no Python required
- Uses Azure DevOps REST API
- Config stored in `~/.azure-deploy-aem.json`
- State files:
  - `~/.mandg-watch-state.json` - Watch mode state
