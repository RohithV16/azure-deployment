# Feature Branch Deployment, Auto-Retry & Approval Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add feature branch deployment (with interactive dropdown), auto-retry on build failure (2 retries), and approval workflow (auto-approve if permissions, wait otherwise) to the M&G Azure Deployment CLI.

**Architecture:** 
- Add `--branch` option to dev command only
- Use inquirer for interactive branch selection
- Implement retry logic with 30s delay in cli.js polling loop
- Use Azure DevOps approvals API for workflow

**Tech Stack:** Node.js, inquirer, Azure DevOps REST API

---

## File Structure

- `package.json` - Add inquirer dependency
- `cli.js` - Add --branch option, retry logic, approval workflow
- `services/azure-service.js` - Add getBranches(), approval methods

---

## Task 1: Add inquirer dependency

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Add inquirer to package.json**

```json
"dependencies": {
  "axios": "^1.6.2",
  "chalk": "^4.1.2",
  "commander": "^11.1.0",
  "dotenv": "^16.3.1",
  "execa": "^5.1.1",
  "inquirer": "^8.2.5"
}
```

Run: `npm install inquirer`

- [ ] **Step 2: Stage and commit**

```bash
git add package.json
git commit -m "feat: add inquirer for interactive branch selection"
```

---

## Task 2: Add getBranches method to azure-service.js

**Files:**
- Modify: `services/azure-service.js:1-30`

- [ ] **Step 1: Add getBranches method**

Add after `getRepositoryId()` method (around line 50):

```javascript
async getBranches(repoId) {
  this._refreshConfig();
  try {
    const response = await this.client.get(`/git/repositories/${repoId}/refs?filter=heads/&api-version=7.0`);
    return response.data.value || [];
  } catch (error) {
    this.handleError(error);
  }
}
```

- [ ] **Step 2: Add getRepositories method (for use in branch listing)**

Add around line 45 (before getRepositoryId):

```javascript
async getRepositories() {
  this._refreshConfig();
  try {
    const response = await this.client.get('/git/repositories?api-version=7.0');
    return response.data.value || [];
  } catch (error) {
    this.handleError(error);
  }
}
```

- [ ] **Step 3: Stage and commit**

```bash
git add services/azure-service.js
git commit -m "feat: add getBranches and getRepositories methods"
```

---

## Task 3: Add --branch option to dev command in cli.js

**Files:**
- Modify: `cli.js:56-120`

- [ ] **Step 1: Update dev command definition**

Add option to the dev command (around line 57):

```javascript
program
  .command('dev')
  .description('Trigger DEV pipeline deployment')
  .option('--branch <branchname>', 'Feature branch to deploy (optional, omit for interactive selection)')
  .option('--no-notify', 'Skip Teams/Power Automate notifications')
  .option('--no-pr-detect', 'Skip PR detection')
  .option('--no-tag', 'Skip automatic tagging')
  .action(async (options) => {
```

- [ ] **Step 2: Add branch selection logic**

Replace the dev command action body to include branch handling:

```javascript
.action(async (options) => {
  try {
    const config = getConfig();
    const defId = config.dev_definition_id;
    let branch = options.branch;

    // If no branch specified, show interactive selection
    if (!branch) {
      const chalk = require('chalk');
      const inquirer = require('inquirer');
      
      console.log(chalk.blue('🔍 Fetching branches...'));
      
      // Get repo ID and branches
      const repoId = await azureService.getRepositoryId(config.tag_repo_name);
      const branches = await azureService.getBranches(repoId);
      
      const branchChoices = branches
        .filter(b => b.name.startsWith('refs/heads/'))
        .map(b => b.name.replace('refs/heads/', ''))
        .sort();
      
      const { selectedBranch } = await inquirer.prompt([
        {
          type: 'list',
          name: 'selectedBranch',
          message: 'Select a branch to deploy:',
          choices: branchChoices,
          pageSize: 20
        }
      ]);
      
      branch = selectedBranch;
    }

    // Rest of existing logic, but use branch instead of 'dev'
    // ... (see Task 4)
```

- [ ] **Step 3: Stage and commit**

```bash
git add cli.js
git commit -m "feat: add --branch option with interactive selection to dev command"
```

---

## Task 4: Implement auto-retry on build failure

**Files:**
- Modify: `cli.js:150-220`

- [ ] **Step 1: Add retry constants**

At top of cli.js, add:

```javascript
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 30000;
```

- [ ] **Step 2: Modify build trigger to include retry logic**

After triggering build, instead of just notifying, add polling with retry:

```javascript
// Trigger build
const build = await azureService.triggerBuild(defId, sourceRef);
console.log(chalk.green(`✅ Build triggered: ${build.buildNumber} (ID: ${build.id})`));

// Poll for completion with retry
let finalBuild = build;
let attempts = 0;
let buildResult = null;

while (!['completed', 'cancelled', 'failed'].includes(finalBuild.status) && attempts < 20) {
  await new Promise(r => setTimeout(r, 15000)); // 15s polling
  finalBuild = await azureService.getBuild(build.id);
  attempts++;
}

// Check result - auto-retry on failure
while (buildResult !== 'succeeded' && attempts < MAX_RETRIES + 1) {
  if (buildResult === 'failed') {
    console.log(chalk.yellow(`⚠️ Build failed. Retrying in 30s... (attempt ${attempts}/${MAX_RETRIES})`));
    await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
    const newBuild = await azureService.triggerBuild(defId, sourceRef);
    finalBuild = newBuild;
    attempts++;
  }
  
  // Poll for result
  attempts = 0;
  while (!['completed', 'cancelled'].includes(finalBuild.status) && attempts < 20) {
    await new Promise(r => setTimeout(r, 15000));
    finalBuild = await azureService.getBuild(build.id);
  }
  buildResult = finalBuild.result;
}

// Notify based on final result
if (options.notify) {
  const finalStatus = buildResult === 'succeeded' ? 'succeeded' : 'failed';
  await teamsService.sendDeploymentNotification({
    pipeline: 'DEV',
    status: finalStatus,
    buildNumber: finalBuild.buildNumber,
    buildId: finalBuild.id,
    prMerges,
    org: config.org,
    project: config.project
  });
}
```

- [ ] **Step 3: Stage and commit**

```bash
git add cli.js
git commit -m "feat: add auto-retry (2 attempts, 30s delay) on build failure"
```

---

## Task 5: Implement approval workflow

**Files:**
- Modify: `services/azure-service.js`

- [ ] **Step 1: Add approval-related methods**

Add at end of azure-service.js:

```javascript
// ── Approval Workflow ───────────────────────────────────────────────────

async queryApprovals(buildId) {
  this._refreshConfig();
  try {
    const response = await this.client.post(
      `/pipelines/builds/${buildId}/approvals/query?api-version=7.0`,
      {}
    );
    return response.data.value || [];
  } catch (error) {
    this.handleError(error);
  }
}

async approveBuild(buildId, approvalId) {
  this._refreshConfig();
  try {
    const response = await this.client.patch(
      `/pipelines/approvals/${approvalId}?api-version=7.0`,
      {
        status: 'approved',
        approver: { id: this.token }
      }
    );
    return response.data;
  } catch (error) {
    this.handleError(error);
  }
}

async waitForApproval(buildId, maxWaitMs = 7200000) {
  const startTime = Date.now();
  const pollInterval = 30000; // 30s
  
  while (Date.now() - startTime < maxWaitMs) {
    const approvals = await this.queryApprovals(buildId);
    
    if (approvals.length === 0) {
      // No approvals needed or already approved
      return true;
    }
    
    const pendingApprovals = approvals.filter(a => a.status === 'pending');
    
    if (pendingApprovals.length === 0) {
      // All approvals complete
      return true;
    }
    
    // Check if we can auto-approve
    try {
      for (const approval of pendingApprovals) {
        await this.approveBuild(buildId, approval.id);
      }
      return true;
    } catch (e) {
      // No permission to auto-approve - wait
      console.log('⏳ Waiting for approval...');
    }
    
    await new Promise(r => setTimeout(r, pollInterval));
  }
  
  throw new Error('Approval timeout after 2 hours');
}
```

- [ ] **Step 2: Stage and commit**

```bash
git add services/azure-service.js
git commit -m "feat: add approval workflow methods"
```

---

## Task 6: Hook up approval workflow in CLI

**Files:**
- Modify: `cli.js` (integrate after build trigger)

- [ ] **Step 1: Add approval wait after build trigger**

After triggering build but before notifying, add:

```javascript
// Wait for approval if needed
console.log(chalk.gray('🔄 Checking for approvals...'));
try {
  await azureService.waitForApproval(build.id);
  console.log(chalk.green('✅ Approval granted'));
} catch (e) {
  if (e.message.includes('timeout')) {
    throw new Error('Approval not granted within 2 hours');
  }
  throw e;
}
```

- [ ] **Step 2: Stage and commit**

```bash
git add cli.js
git commit -m "feat: integrate approval workflow in dev deployment"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run syntax check**

```bash
node -c cli.js
node -c services/azure-service.js
```

- [ ] **Step 2: Test help output**

```bash
node cli.js dev --help
```

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
git add .
git commit -m "feat: complete feature branch, retry, and approval workflow"
```

---

## Summary of Commits

1. `feat: add inquirer for interactive branch selection`
2. `feat: add getBranches and getRepositories methods`
3. `feat: add --branch option with interactive selection to dev command`
4. `feat: add auto-retry (2 attempts, 30s delay) on build failure`
5. `feat: add approval workflow methods`
6. `feat: integrate approval workflow in dev deployment`
7. `feat: complete feature branch, retry, and approval workflow`