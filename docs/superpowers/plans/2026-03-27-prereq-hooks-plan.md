# Prerequisite Check, Secret Rotation & Custom Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Add prerequisite check, PAT rotation, and custom hooks to the CLI.

**Tech Stack:** Node.js, spawn, Azure DevOps API

---

## Task 1: Add check-permissions method to azure-service.js

**Files:**
- Modify: `services/azure-service.js`

- [ ] **Step 1: Add checkPermissions method**

```javascript
async checkPermissions() {
  this._refreshConfig();
  try {
    // Test build definitions access
    const buildResp = await this.client.get(`/build/definitions?api-version=7.0`);
    const defs = buildResp.data.value || [];
    
    const devDef = defs.find(d => d.id === parseInt(this.repoName) || d.name.includes('DEV'));
    const stageDef = defs.find(d => d.name.includes('STAGE'));
    
    return {
      hasBuildAccess: true,
      devDefinitionExists: !!devDef,
      stageDefinitionExists: !!stageDef,
      definitions: defs.length
    };
  } catch (error) {
    return { hasBuildAccess: false, error: error.message };
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add services/azure-service.js
git commit -m "feat: add checkPermissions method"
```

---

## Task 2: Add check command to cli.js

**Files:**
- Modify: `cli.js`

- [ ] **Step 1: Add check command before update command**

```javascript
// ── Prerequisite Check ─────────────────────────────────────────────────

program
  .command('check')
  .description('Validate environment, PAT, and permissions before deployment')
  .action(async () => {
    const chalk = require('chalk');
    const { getConfig } = require('./config');
    const azureService = require('./services/azure-service');
    
    console.log(chalk.blue('🔍 Running prerequisite checks...\n'));
    
    let allPassed = true;
    
    // Check 1: Config exists
    try {
      const config = getConfig();
      if (config.org && config.project) {
        console.log(chalk.green('✅ Config file valid'));
      } else {
        console.log(chalk.red('❌ Config incomplete'));
        console.log(chalk.yellow('   Run: mandg update --org <url> --project <name>'));
        allPassed = false;
      }
      
      // Check 2: PAT configured
      if (config.token) {
        console.log(chalk.green('✅ PAT configured'));
      } else if (process.env.AZURE_DEVOPS_PAT) {
        console.log(chalk.green('✅ PAT from environment'));
      } else {
        console.log(chalk.red('❌ No PAT configured'));
        console.log(chalk.yellow('   Run: mandg update --token <your-pat>'));
        allPassed = false;
      }
      
      if (allPassed) {
        // Check 3: Test API connection
        console.log(chalk.gray('   Testing Azure DevOps connection...'));
        const perms = await azureService.checkPermissions();
        
        if (perms.hasBuildAccess) {
          console.log(chalk.green('✅ Azure DevOps connection OK'));
          console.log(chalk.green(`✅ Found ${perms.definitions} pipeline definitions`));
        } else {
          console.log(chalk.red('❌ API connection failed: ' + perms.error));
          allPassed = false;
        }
      }
    } catch (e) {
      console.log(chalk.red('❌ Check failed: ' + e.message));
      allPassed = false;
    }
    
    console.log('');
    if (allPassed) {
      console.log(chalk.green('All checks passed! ✅'));
    } else {
      console.log(chalk.red('Some checks failed. Please fix the issues above.'));
      process.exit(1);
    }
  });
```

- [ ] **Step 2: Commit**

```bash
git add cli.js
git commit -m "feat: add prerequisite check command"
```

---

## Task 3: Add rotate-token command

**Files:**
- Modify: `cli.js`

- [ ] **Step 1: Add rotate-token command**

```javascript
// ── Secret Rotation ───────────────────────────────────────────────────

program
  .command('rotate-token')
  .description('Rotate Azure DevOps PAT token')
  .option('--old <token>', 'Current PAT token')
  .option('--new <token>', 'New PAT token')
  .action(async (options) => {
    const chalk = require('chalk');
    const { getConfig, saveConfig } = require('./config');
    const azureService = require('./services/azure-service');
    
    const currentConfig = getConfig();
    const oldToken = options.old || currentConfig.token;
    const newToken = options.new;
    
    if (!oldToken) {
      console.log(chalk.red('❌ Current token required. Use --old or update config first.'));
      process.exit(1);
    }
    
    if (!newToken) {
      console.log(chalk.red('❌ New token required. Use --new <token>'));
      process.exit(1);
    }
    
    console.log(chalk.blue('🔄 Validating new token...'));
    
    // Test new token by making API call
    const testConfig = { ...currentConfig, token: newToken };
    const testService = new (require('./services/azure-service').default || require('./services/azure-service'))();
    
    try {
      await testService.checkPermissions();
      console.log(chalk.green('✅ New token is valid'));
    } catch (e) {
      console.log(chalk.red('❌ New token is invalid: ' + e.message));
      process.exit(1);
    }
    
    // Save new token
    saveConfig({ token: newToken });
    console.log(chalk.green('✅ Token rotated successfully!'));
  });
```

- [ ] **Step 2: Commit**

```bash
git add cli.js
git commit -m "feat: add rotate-token command"
```

---

## Task 4: Create hooks utility

**Files:**
- Create: `utils/hooks.js`

- [ ] **Step 1: Create hooks.js**

```javascript
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOOK_TIMEOUT = 60000; // 60 seconds

async function runHook(hookName, config, env = {}) {
  const hooks = config.hooks || {};
  const hookPath = hooks[hookName];
  
  if (!hookPath) {
    return { executed: false, skipped: true };
  }
  
  // Resolve path
  const resolvedPath = path.isAbsolute(hookPath) 
    ? hookPath 
    : path.join(os.homedir(), hookPath);
  
  if (!fs.existsSync(resolvedPath)) {
    return { executed: false, error: `Hook script not found: ${resolvedPath}` };
  }
  
  return new Promise((resolve) => {
    const hookEnv = {
      ...process.env,
      DEPLOY_HOOK: hookName,
      ...env
    };
    
    const child = spawn(resolvedPath, [], {
      env: hookEnv,
      stdio: 'inherit'
    });
    
    const timeout = setTimeout(() => {
      child.kill('SIGTERM');
      resolve({ executed: true, error: 'Hook timed out after 60s' });
    }, HOOK_TIMEOUT);
    
    child.on('close', (code) => {
      clearTimeout(timeout);
      resolve({ 
        executed: true, 
        exitCode: code,
        success: code === 0
      });
    });
    
    child.on('error', (err) => {
      clearTimeout(timeout);
      resolve({ executed: true, error: err.message });
    });
  });
}

module.exports = {
  runHook
};
```

- [ ] **Step 2: Commit**

```bash
git add utils/hooks.js
git commit -m "feat: add hooks utility"
```

---

## Task 5: Integrate hooks into dev command

**Files:**
- Modify: `cli.js` (dev command)

- [ ] **Step 1: Add hook execution to dev command**

Import at top:
```javascript
const { runHook } = require('./utils/hooks');
```

Before triggering build:
```javascript
// Run pre-deploy hook
const hookResult = await runHook('pre-deploy', config, {
  DEPLOY_PIPELINE: 'DEV',
  DEPLOY_BRANCH: branch
});
if (hookResult.executed && !hookResult.success) {
  console.log(chalk.yellow(`⚠️  Pre-deploy hook failed (exit ${hookResult.exitCode})`));
}
```

After deployment completes:
```javascript
// Run post-deploy hook
await runHook('post-deploy', config, {
  DEPLOY_PIPELINE: 'DEV',
  DEPLOY_BRANCH: branch,
  DEPLOY_STATUS: buildResult,
  DEPLOY_BUILD_ID: finalBuild.id
});
```

- [ ] **Step 2: Commit**

```bash
git add cli.js
git commit -m "feat: integrate hooks into dev deployment"
```

---

## Task 6: Final verification

- [ ] Run syntax check
- [ ] Test `mandg check --help`
- [ ] Test `mandg rotate-token --help`

---

## Summary

1. `feat: add checkPermissions method`
2. `feat: add prerequisite check command`
3. `feat: add rotate-token command`
4. `feat: add hooks utility`
5. `feat: integrate hooks into dev deployment`