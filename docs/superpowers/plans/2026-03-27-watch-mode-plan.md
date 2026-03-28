# Watch Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add watch mode to `mandg dev` that polls for merged PRs and auto-deploys after delay.

**Architecture:**
- Add `--watch` flag to dev command
- Use Azure DevOps PR API to detect new merges
- Store last deployed PR in local state file
- Reuse existing deployment and retry logic

**Tech Stack:** Node.js, file system (state), Azure DevOps API

---

## File Structure

- `cli.js` - Add watch mode, polling loop
- `services/azure-service.js` - Add method to get merged PRs since timestamp
- `utils/watch-state.js` - New file for state management

---

## Task 1: Add watch-state utility

**Files:**
- Create: `utils/watch-state.js`

- [ ] **Step 1: Create utils directory and watch-state.js**

```javascript
const fs = require('fs');
const path = require('path');
const os = require('os');

const STATE_FILE = path.join(os.homedir(), '.mandg-watch-state.json');

function getState() {
  if (fs.existsSync(STATE_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    } catch (e) {
      return { lastPrId: null, lastPrMergeTime: null };
    }
  }
  return { lastPrId: null, lastPrMergeTime: null };
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

module.exports = {
  getState,
  saveState,
  STATE_FILE
};
```

- [ ] **Step 2: Stage and commit**

```bash
git add utils/watch-state.js
git commit -m "feat: add watch state utility"
```

---

## Task 2: Add getMergedPRs method to azure-service.js

**Files:**
- Modify: `services/azure-service.js`

- [ ] **Step 1: Add getMergedPRsSince method**

Add after existing PR methods (around line 300):

```javascript
async getMergedPRsSince(branch, sinceDate) {
  this._refreshConfig();
  try {
    const repoId = await this.getRepositoryId(this.repoName);
    const response = await this.client.get(
      `/git/repositories/${repoId}/pullRequests?api-version=7.0&searchCriteria.status=completed&searchCriteria.targetRefName=refs/heads/${branch}`
    );
    const prs = response.data.value || [];
    
    // Filter by merge date if provided
    if (sinceDate) {
      const since = new Date(sinceDate);
      return prs.filter(pr => pr.mergeDate && new Date(pr.mergeDate) > since);
    }
    return prs;
  } catch (error) {
    this.handleError(error);
  }
}
```

- [ ] **Step 2: Stage and commit**

```bash
git add services/azure-service.js
git commit -m "feat: add getMergedPRsSince method"
```

---

## Task 3: Add watch mode to dev command

**Files:**
- Modify: `cli.js`

- [ ] **Step 1: Add watch mode options**

Add to dev command options:
```javascript
.option('--watch', 'Watch for new PR merges and auto-deploy')
.option('--bg', 'Alias for --watch')
.option('--poll-interval <minutes>', 'Poll interval in minutes (default: 10)', '10')
.option('--delay <minutes>', 'Delay after PR merge before deploy (default: 5)', '5')
```

- [ ] **Step 2: Add watch mode logic**

In dev command action, after options parsing:

```javascript
const isWatchMode = options.watch || options.bg;
const pollIntervalMs = parseInt(options.pollInterval) * 60 * 1000;
const delayMs = parseInt(options.delay) * 60 * 1000;

if (isWatchMode) {
  const { getState, saveState } = require('./utils/watch-state');
  
  console.log(chalk.blue('🔄 Starting watch mode...'));
  console.log(chalk.gray(`   Poll interval: ${options.pollInterval} min`));
  console.log(chalk.gray(`   Delay after merge: ${options.delay} min`));
  
  while (true) {
    try {
      // Get current merged PRs
      const prs = await azureService.getMergedPRsSince('dev', state.lastPrMergeTime);
      
      if (prs.length > 0) {
        // Sort by merge date (newest first)
        prs.sort((a, b) => new Date(b.mergeDate) - new Date(a.mergeDate));
        
        for (const pr of prs) {
          console.log(chalk.cyan(`📋 New PR merged: #${pr.pullRequestId} - ${pr.title}`));
          
          // Wait delay
          const delayMinutes = parseInt(options.delay);
          for (let i = delayMinutes; i > 0; i--) {
            console.log(chalk.gray(`   Deploying in ${i} minute(s)...`));
            await new Promise(r => setTimeout(r, 60000));
          }
          
          // Trigger deployment (reuse existing logic)
          const branch = 'dev';
          const sourceRef = `refs/heads/${branch}`;
          const build = await azureService.triggerBuild(defId, sourceRef);
          console.log(chalk.green(`🚀 Deployment triggered: ${build.buildNumber}`));
          
          // Poll and retry (existing logic)
          // ... (reuse from Task 4 of previous feature)
          
          // Update state
          const state = getState();
          state.lastPrId = pr.pullRequestId;
          state.lastPrMergeTime = pr.mergeDate;
          state.lastDeployTime = new Date().toISOString();
          saveState(state);
        }
      } else {
        console.log(chalk.gray('🔍 No new PRs found'));
      }
    } catch (e) {
      console.log(chalk.yellow(`⚠️  Error in watch loop: ${e.message}`));
    }
    
    // Wait for next poll
    console.log(chalk.gray(`   Next check in ${options.pollInterval} minutes...`));
    await new Promise(r => setTimeout(r, pollIntervalMs));
  }
}
```

- [ ] **Step 3: Stage and commit**

```bash
git add cli.js
git commit -m "feat: add watch mode for recurring deployments"
```

---

## Task 4: Final verification

- [ ] **Step 1: Run syntax check**

```bash
node -c cli.js
node -c services/azure-service.js
node -c utils/watch-state.js
```

- [ ] **Step 2: Test help output**

```bash
node cli.js dev --help
```

- [ ] **Step 3: Commit any remaining changes**

---

## Summary of Commits

1. `feat: add watch state utility`
2. `feat: add getMergedPRsSince method`
3. `feat: add watch mode for recurring deployments`