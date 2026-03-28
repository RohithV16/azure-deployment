#!/usr/bin/env node

require('dotenv').config();

const { program } = require('commander');
const chalk = require('chalk');
const { getConfig, saveConfig } = require('./config');
const azureService = require('./services/azure-service');
const teamsService = require('./services/teams-service');
const tagService = require('./services/tag-service');
const gitService = require('./services/git-service');
const prService = require('./services/pr-service');
const { runHook } = require('./utils/hooks');

program
  .name('mandg')
  .description('M&G AEM Azure Deployment CLI (Pure JS REST API)')
  .version('3.0.0');

// ── Prerequisite Check ─────────────────────────────────────────────────

program
  .command('check')
  .description('Validate environment, PAT, and permissions before deployment')
  .action(async () => {
    const { getConfig } = require('./config');
    const azureService = require('./services/azure-service');
    
    console.log(chalk.blue('🔍 Running prerequisite checks...\n'));
    
    let allPassed = true;
    
    try {
      const config = getConfig();
      
      if (config.org && config.project) {
        console.log(chalk.green('✅ Config file valid'));
        console.log(chalk.gray(`   Org: ${config.org}`));
        console.log(chalk.gray(`   Project: ${config.project}`));
      } else {
        console.log(chalk.red('❌ Config incomplete'));
        console.log(chalk.yellow('   Run: mandg update --org <url> --project <name>'));
        allPassed = false;
      }
      
      if (config.token) {
        console.log(chalk.green('✅ PAT configured'));
      } else if (process.env.AZURE_DEVOPS_PAT) {
        console.log(chalk.green('✅ PAT from environment'));
      } else {
        console.log(chalk.red('❌ No PAT configured'));
        console.log(chalk.yellow('   Run: mandg update --token <your-pat>'));
        allPassed = false;
      }
      
      if (config.dev_definition_id) {
        console.log(chalk.green(`✅ DEV pipeline ID: ${config.dev_definition_id}`));
      } else {
        console.log(chalk.red('❌ DEV pipeline ID not configured'));
        allPassed = false;
      }
      
      if (config.stage_definition_id) {
        console.log(chalk.green(`✅ STAGE pipeline ID: ${config.stage_definition_id}`));
      } else {
        console.log(chalk.red('❌ STAGE pipeline ID not configured'));
        allPassed = false;
      }
      
      if (allPassed) {
        console.log(chalk.gray('\n   Testing Azure DevOps connection...'));
        const perms = await azureService.checkPermissions();
        
        if (perms.hasBuildAccess) {
          console.log(chalk.green('✅ Azure DevOps connection OK'));
          console.log(chalk.green(`✅ Found ${perms.definitions} pipeline definitions`));
          if (!perms.devDefinitionExists) {
            console.log(chalk.yellow('⚠️  DEV pipeline definition not found'));
          }
          if (!perms.stageDefinitionExists) {
            console.log(chalk.yellow('⚠️  STAGE pipeline definition not found'));
          }
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

// ── Approval Management ───────────────────────────────────────────────

program
  .command('approval')
  .description('Interactive approval/rejection of pending deployments')
  .action(async () => {
    const inquirer = require('inquirer');
    
    try {
      console.log(chalk.blue('📋 Fetching pending approvals...'));
      
      const approvals = await azureService.getPendingApprovals();
      
      if (approvals.length === 0) {
        console.log(chalk.yellow('⚠️  No pending approvals found.'));
        return;
      }
      
      const choices = approvals.map((a, i) => ({
        name: `${i + 1}. ${a.pipeline?.name || 'Pipeline'} | Build #${a.build?.id || '?'} | ${a.status} | by ${a.approver?.displayName || 'unknown'}`,
        value: a
      }));
      
      const { selectedApproval } = await inquirer.prompt([
        {
          type: 'list',
          name: 'selectedApproval',
          message: 'Select a deployment:',
          choices: choices,
          pageSize: 20
        }
      ]);
      
      const { action } = await inquirer.prompt([
        {
          type: 'list',
          name: 'action',
          message: 'Choose action:',
          choices: [
            { name: '[A]pprove', value: 'approve' },
            { name: '[R]eject', value: 'reject' }
          ]
        }
      ]);
      
      const { comment } = await inquirer.prompt([
        {
          type: 'input',
          name: 'comment',
          message: 'Add comment (optional):'
        }
      ]);
      
      if (action === 'approve') {
        await azureService.approveDeployment(selectedApproval.id, comment || undefined);
        console.log(chalk.green(`✅ Approved Build #${selectedApproval.build?.id}`));
      } else {
        await azureService.rejectDeployment(selectedApproval.id, comment || undefined);
        console.log(chalk.red(`❌ Rejected Build #${selectedApproval.build?.id}`));
      }
    } catch (error) {
      console.log(chalk.red(`❌ Error: ${error.message}`));
      process.exit(1);
    }
  });

program
  .command('approve')
  .description('Approve a specific deployment')
  .option('--build <id>', 'Build ID')
  .option('--comment <text>', 'Approval comment')
  .action(async (options) => {
    try {
      if (!options.build) {
        console.log(chalk.red('❌ Build ID required. Use --build <id>'));
        console.log(chalk.gray('Or use "mandg approval" for interactive mode'));
        process.exit(1);
      }
      
      const approvals = await azureService.getPendingApprovals();
      const approval = approvals.find(a => a.build?.id === parseInt(options.build));
      
      if (!approval) {
        console.log(chalk.red(`❌ No pending approval found for Build #${options.build}`));
        process.exit(1);
      }
      
      await azureService.approveDeployment(approval.id, options.comment);
      console.log(chalk.green(`✅ Approved Build #${options.build}`));
    } catch (error) {
      console.log(chalk.red(`❌ Error: ${error.message}`));
      process.exit(1);
    }
  });

program
  .command('reject')
  .description('Reject a specific deployment')
  .option('--build <id>', 'Build ID')
  .option('--comment <text>', 'Rejection reason')
  .action(async (options) => {
    try {
      if (!options.build) {
        console.log(chalk.red('❌ Build ID required. Use --build <id>'));
        console.log(chalk.gray('Or use "mandg approval" for interactive mode'));
        process.exit(1);
      }
      
      const approvals = await azureService.getPendingApprovals();
      const approval = approvals.find(a => a.build?.id === parseInt(options.build));
      
      if (!approval) {
        console.log(chalk.red(`❌ No pending approval found for Build #${options.build}`));
        process.exit(1);
      }
      
      await azureService.rejectDeployment(approval.id, options.comment);
      console.log(chalk.red(`❌ Rejected Build #${options.build}`));
    } catch (error) {
      console.log(chalk.red(`❌ Error: ${error.message}`));
      process.exit(1);
    }
  });

program
  .command('approvals')
  .description('List pending approvals')
  .option('--list', 'List all pending approvals')
  .action(async (options) => {
    try {
      const approvals = await azureService.getPendingApprovals();
      
      if (approvals.length === 0) {
        console.log(chalk.yellow('⚠️  No pending approvals.'));
        return;
      }
      
      console.log(chalk.blue('📋 Pending Approvals:\n'));
      approvals.forEach((a, i) => {
        console.log(`${i + 1}. Build #${a.build?.id} | ${a.pipeline?.name || 'Pipeline'} | by ${a.approver?.displayName || 'unknown'}`);
      });
    } catch (error) {
      console.log(chalk.red(`❌ Error: ${error.message}`));
      process.exit(1);
    }
  });

// ── Configuration ─────────────────────────────────────────────────────

program
  .command('update')
  .description('Update configuration and authentication (PAT)')
  .option('--token <pat>', 'Azure DevOps Personal Access Token (PAT)')
  .option('--org <url>', 'Azure DevOps Organization URL')
  .option('--project <name>', 'Project name')
  .option('--dev-id <id>', 'DEV pipeline definition ID')
  .option('--stage-id <id>', 'STAGE pipeline definition ID')
  .action((options) => {
    const newConfig = {};
    if (options.token) newConfig.token = options.token;
    if (options.org) newConfig.org = options.org;
    if (options.project) newConfig.project = options.project;
    if (options.devId) newConfig.dev_definition_id = options.devId;
    if (options.stageId) newConfig.stage_definition_id = options.stageId;

    if (Object.keys(newConfig).length === 0) {
      console.log(chalk.blue('Current configuration:'));
      const config = getConfig();
      const displayConfig = { ...config };
      if (displayConfig.token) {
        displayConfig.token = displayConfig.token.substring(0, 4) + '...' + displayConfig.token.substring(displayConfig.token.length - 4);
      }
      if (process.env.AZURE_DEVOPS_PAT) {
        displayConfig.env_pat_set = true;
      }
      console.log(JSON.stringify(displayConfig, null, 2));
    } else {
      saveConfig(newConfig);
      console.log(chalk.green('✅ Configuration updated.'));
    }
  });

// ── Secret Rotation ───────────────────────────────────────────────────

program
  .command('rotate-token')
  .description('Rotate Azure DevOps PAT token')
  .option('--old <token>', 'Current PAT token')
  .option('--new <token>', 'New PAT token')
  .action(async (options) => {
    const { getConfig, saveConfig } = require('./config');
    const azureService = require('./services/azure-service');
    
    const currentConfig = getConfig();
    const oldToken = options.old || currentConfig.token;
    const newToken = options.new;
    
    if (!oldToken) {
      console.log(chalk.red('❌ Current token required. Use --old or ensure config has token.'));
      process.exit(1);
    }
    
    if (!newToken) {
      console.log(chalk.red('❌ New token required. Use --new <token>'));
      process.exit(1);
    }
    
    console.log(chalk.blue('🔄 Validating new token...'));
    
    if (oldToken === newToken) {
      console.log(chalk.red('❌ New token must be different from old token'));
      process.exit(1);
    }
    
    try {
      const perms = await azureService.checkPermissions();
      if (!perms.hasBuildAccess) {
        console.log(chalk.red('❌ Current token is invalid: ' + perms.error));
        process.exit(1);
      }
      console.log(chalk.green('✅ Current token validated'));
    } catch (e) {
      console.log(chalk.red('❌ Current token validation failed: ' + e.message));
      process.exit(1);
    }
    
    saveConfig({ token: newToken });
    console.log(chalk.green('✅ Token rotated successfully!'));
  });

// ── DEV Pipeline ──────────────────────────────────────────────────────

program
  .command('dev')
  .description('Trigger DEV pipeline deployment')
  .option('--no-notify', 'Skip Teams/Power Automate notifications')
  .option('--no-pr-detect', 'Skip PR detection')
  .option('--branch <branchname>', 'Feature branch to deploy (optional, omit for interactive selection)')
  .option('--watch', 'Watch for new PR merges and auto-deploy')
  .option('--bg', 'Alias for --watch (background mode)')
  .option('--poll-interval <minutes>', 'Poll interval in minutes (default: 10)', '10')
  .option('--delay <minutes>', 'Delay after PR merge before deploy (default: 5)', '5')
  .action(async (options) => {
    try {
      const config = getConfig();
      const defId = config.dev_definition_id;
      const isWatchMode = options.watch || options.bg;
      const pollIntervalMs = parseInt(options.pollInterval) * 60 * 1000;
      const delayMs = parseInt(options.delay) * 60 * 1000;
      const delayMinutes = parseInt(options.delay);

      if (isWatchMode) {
        const { getState, saveState } = require('./utils/watch-state');
        
        console.log(chalk.blue('🔄 Starting watch mode...'));
        console.log(chalk.gray(`   Poll interval: ${options.pollInterval} min`));
        console.log(chalk.gray(`   Delay after merge: ${options.delay} min`));
        console.log(chalk.yellow('   Press Ctrl+C to stop\n'));
        
        while (true) {
          let state = getState();
          
          try {
            const prs = await azureService.getMergedPRsSince('dev', state.lastPrMergeTime);
            
            if (prs && prs.length > 0) {
              prs.sort((a, b) => new Date(b.mergeDate) - new Date(a.mergeDate));
              
              for (const pr of prs) {
                console.log(chalk.cyan(`📋 New PR merged: #${pr.pullRequestId} - ${pr.title}`));
                
                console.log(chalk.gray(`   Waiting ${delayMinutes} minute(s) before deploy...`));
                for (let i = delayMinutes; i > 0; i--) {
                  await new Promise(r => setTimeout(r, 60000));
                  if (i > 1) console.log(chalk.gray(`   ${i - 1} minute(s) remaining...`));
                }
                
                const build = await azureService.triggerBuild(defId, 'refs/heads/dev');
                console.log(chalk.green(`🚀 Deployment triggered: ${build.buildNumber} (ID: ${build.id})`));
                
                let finalBuild = build;
                let pollCount = 0;
                const MAX_POLLS = 80;
                
                while (!['completed', 'cancelled'].includes(finalBuild.status)) {
                  if (pollCount >= MAX_POLLS) {
                    console.log(chalk.yellow('⚠️  Polling timeout. Build may be stuck.'));
                    break;
                  }
                  await new Promise(r => setTimeout(r, 15000));
                  try {
                    finalBuild = await azureService.getBuild(build.id);
                  } catch (e) {
                    console.log(chalk.yellow(`⚠️  Poll error: ${e.message}`));
                  }
                  pollCount++;
                }
                
                let buildResult = finalBuild.result;
                
                let retries = 0;
                while (buildResult === 'failed' && retries < 2) {
                  await new Promise(r => setTimeout(r, 30000));
                  build = await azureService.triggerBuild(defId, 'refs/heads/dev');
                  finalBuild = build;
                  
                  let retryPollCount = 0;
                  while (!['completed', 'cancelled'].includes(finalBuild.status)) {
                    if (retryPollCount >= MAX_POLLS) break;
                    await new Promise(r => setTimeout(r, 15000));
                    try {
                      finalBuild = await azureService.getBuild(build.id);
                    } catch (e) {}
                    retryPollCount++;
                  }
                  buildResult = finalBuild.result;
                  retries++;
                }
                
                if (options.notify) {
                  await teamsService.sendDeploymentNotification({
                    pipeline: 'DEV',
                    status: buildResult === 'succeeded' ? 'succeeded' : 'failed',
                    buildNumber: finalBuild.buildNumber,
                    buildId: finalBuild.id,
                    prMerges: [],
                    org: config.org,
                    project: config.project
                  });
                }
                
                if (buildResult === 'succeeded') {
                  console.log(chalk.green('✅ Deployment succeeded!'));
                } else {
                  console.log(chalk.red('❌ Deployment failed after retries'));
                }
                
                state.lastPrId = pr.pullRequestId;
                state.lastPrMergeTime = pr.mergeDate;
                state.lastDeployTime = new Date().toISOString();
                saveState(state);
              }
            } else {
              console.log(chalk.gray('🔍 No new PRs found'));
            }
          } catch (e) {
            console.log(chalk.yellow(`⚠️  Error: ${e.message}`));
          }
          
          console.log(chalk.gray(`   Next check in ${options.pollInterval} minute(s)...\n`));
          await new Promise(r => setTimeout(r, pollIntervalMs));
        }
      }
      
      let branch = options.branch || 'dev';

      // If no branch specified, show interactive selection
      if (!options.branch) {
        const inquirer = require('inquirer');
        console.log(chalk.blue('🔍 Fetching branches...'));

        // Get repo ID and branches
        let branches;
        try {
          const repoId = await azureService.getRepositoryId(config.tag_repo_name);
          branches = await azureService.getBranches(repoId);
        } catch (fetchError) {
          throw new Error(`Failed to fetch branches: ${fetchError.message}`);
        }

        const branchChoices = branches
          .filter(b => b.name.startsWith('refs/heads/'))
          .map(b => b.name.replace('refs/heads/', ''))
          .sort();

        if (branchChoices.length === 0) {
          throw new Error('No branches found in the repository.');
        }

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

      console.log(chalk.blue(`🚀 Triggering DEV pipeline (ID: ${defId}, branch: ${branch})...`));

      // Detect PRs merged after last build
      let prMerges = [];
      if (options.prDetect) {
        try {
          const lastBuild = await azureService.getLastBuildInfo(defId, { includeInProgress: false, requireFullstack: true });
          if (lastBuild && lastBuild.source_version) {
            console.log(chalk.gray(`   Last build: ${lastBuild.build_number} (${lastBuild.source_version.substring(0, 8)})`));
            prMerges = await azureService.getPrMergesAfterCommit(lastBuild.source_version, branch);
            if (prMerges.length > 0) {
              console.log(chalk.cyan(`   📋 ${prMerges.length} new PR(s) since last build:`));
              for (const pr of prMerges) {
                const ticket = pr.jira_ticket ? `${pr.jira_ticket}: ` : '';
                console.log(chalk.gray(`      • ${ticket}${pr.description} (PR #${pr.pr_number})`));
              }
            } else {
              console.log(chalk.gray('   No new PRs since last build.'));
            }
          }
        } catch (e) {
          console.log(chalk.yellow(`   ⚠️  Could not detect PRs: ${e.message}`));
        }
      }

      // Run pre-deploy hook
      const hookResult = await runHook('pre-deploy', config, {
        DEPLOY_PIPELINE: 'DEV',
        DEPLOY_BRANCH: branch
      });
      if (hookResult.executed && !hookResult.success) {
        console.log(chalk.yellow(`⚠️  Pre-deploy hook failed (exit ${hookResult.exitCode})`));
      }

      // Trigger build with source branch
      let build = await azureService.triggerBuild(defId, `refs/heads/${branch}`);
      console.log(chalk.green(`✅ Build triggered: ${build.buildNumber} (ID: ${build.id})`));
      console.log(chalk.gray(`🔗 URL: ${build._links?.web?.href || 'N/A'}`));

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

      // Poll for completion
      const MAX_POLLS = 80; // 80 * 15s = 20 min max wait
      let finalBuild = build;
      let pollCount = 0;
      while (!['completed', 'cancelled'].includes(finalBuild.status)) {
        if (pollCount >= MAX_POLLS) {
          console.log(chalk.yellow(`⚠️  Polling timeout after ${MAX_POLLS} attempts (20 min). Build may be stuck.`));
          break;
        }
        await new Promise(r => setTimeout(r, 15000));
        try {
          finalBuild = await azureService.getBuild(build.id);
        } catch (e) {
          console.log(chalk.yellow(`⚠️  Poll error: ${e.message}. Retrying in 15s...`));
          await new Promise(r => setTimeout(r, 15000));
        }
        pollCount++;
      }
      let buildResult = finalBuild.result;

      // Auto-retry on failure
      let retries = 0;
      while (buildResult === 'failed' && retries < 2) {
        await new Promise(r => setTimeout(r, 30000));

        build = await azureService.triggerBuild(defId, `refs/heads/${branch}`);

        finalBuild = build;
        let retryPollCount = 0;
        while (!['completed', 'cancelled'].includes(finalBuild.status)) {
          if (retryPollCount >= MAX_POLLS) {
            console.log(chalk.yellow(`⚠️  Polling timeout after ${MAX_POLLS} attempts (20 min). Build may be stuck.`));
            break;
          }
          await new Promise(r => setTimeout(r, 15000));
          try {
            finalBuild = await azureService.getBuild(build.id);
          } catch (e) {
            console.log(chalk.yellow(`⚠️  Poll error: ${e.message}. Retrying in 15s...`));
            await new Promise(r => setTimeout(r, 15000));
          }
          retryPollCount++;
        }
        buildResult = finalBuild.result;
        retries++;
      }

      // Send notification
      if (options.notify) {
        try {
          await teamsService.sendDeploymentNotification({
            pipeline: 'DEV',
            status: buildResult === 'succeeded' ? 'succeeded' : 'failed',
            buildNumber: finalBuild.buildNumber,
            buildId: finalBuild.id,
            prMerges,
            org: config.org,
            project: config.project
          });
          console.log(chalk.gray('   📨 Notification sent.'));
        } catch (e) {
          console.log(chalk.yellow(`   ⚠️  Notification failed: ${e.message}`));
        }
      }

      // Run post-deploy hook
      await runHook('post-deploy', config, {
        DEPLOY_PIPELINE: 'DEV',
        DEPLOY_BRANCH: branch,
        DEPLOY_STATUS: buildResult || finalBuild.result,
        DEPLOY_BUILD_ID: finalBuild.id
      });
    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Watch Mode ───────────────────────────────────────────────────────

program
  .command('watch')
  .description('Watch for PR merges and auto-deploy to DEV')
  .option('--poll-interval <minutes>', 'Poll interval in minutes (default: 10)', '10')
  .option('--delay <minutes>', 'Delay after PR merge before deploy (default: 5)', '5')
  .option('--no-notify', 'Skip notifications')
  .action(async (options) => {
    const config = getConfig();
    const azureService = require('./services/azure-service');
    const teamsService = require('./services/teams-service');
    const { getState, saveState } = require('./utils/watch-state');
    
    const defId = config.dev_definition_id;
    const pollIntervalMs = parseInt(options.pollInterval) * 60 * 1000;
    const delayMinutes = parseInt(options.delay);
    const isWatchMode = true;
    
    console.log(chalk.blue('🔄 Starting watch mode...'));
    console.log(chalk.gray(`   Poll interval: ${options.pollInterval} min`));
    console.log(chalk.gray(`   Delay after merge: ${options.delay} min`));
    console.log(chalk.yellow('   Press Ctrl+C to stop\n'));
    
    while (true) {
      let state = getState();
      
      try {
        const prs = await azureService.getMergedPRsSince('dev', state.lastPrMergeTime);
        
        if (prs && prs.length > 0) {
          prs.sort((a, b) => new Date(b.mergeDate) - new Date(a.mergeDate));
          
          for (const pr of prs) {
            console.log(chalk.cyan(`📋 New PR merged: #${pr.pullRequestId} - ${pr.title}`));
            
            console.log(chalk.gray(`   Waiting ${delayMinutes} minute(s) before deploy...`));
            for (let i = delayMinutes; i > 0; i--) {
              await new Promise(r => setTimeout(r, 60000));
              if (i > 1) console.log(chalk.gray(`   ${i - 1} minute(s) remaining...`));
            }
            
            const build = await azureService.triggerBuild(defId, 'refs/heads/dev');
            console.log(chalk.green(`🚀 Deployment triggered: ${build.buildNumber} (ID: ${build.id})`));
            
            let finalBuild = build;
            let pollCount = 0;
            const MAX_POLLS = 80;
            
            while (!['completed', 'cancelled'].includes(finalBuild.status)) {
              if (pollCount >= MAX_POLLS) {
                console.log(chalk.yellow('⚠️  Polling timeout. Build may be stuck.'));
                break;
              }
              await new Promise(r => setTimeout(r, 15000));
              try {
                finalBuild = await azureService.getBuild(build.id);
              } catch (e) {
                console.log(chalk.yellow(`⚠️  Poll error: ${e.message}`));
              }
              pollCount++;
            }
            
            let buildResult = finalBuild.result;
            
            let retries = 0;
            while (buildResult === 'failed' && retries < 2) {
              await new Promise(r => setTimeout(r, 30000));
              build = await azureService.triggerBuild(defId, 'refs/heads/dev');
              finalBuild = build;
              
              let retryPollCount = 0;
              while (!['completed', 'cancelled'].includes(finalBuild.status)) {
                if (retryPollCount >= MAX_POLLS) break;
                await new Promise(r => setTimeout(r, 15000));
                try {
                  finalBuild = await azureService.getBuild(build.id);
                } catch (e) {}
                retryPollCount++;
              }
              buildResult = finalBuild.result;
              retries++;
            }
            
            if (options.notify !== false) {
              await teamsService.sendDeploymentNotification({
                pipeline: 'DEV',
                status: buildResult === 'succeeded' ? 'succeeded' : 'failed',
                buildNumber: finalBuild.buildNumber,
                buildId: finalBuild.id,
                prMerges: [],
                org: config.org,
                project: config.project
              });
            }
            
            if (buildResult === 'succeeded') {
              console.log(chalk.green('✅ Deployment succeeded!'));
            } else {
              console.log(chalk.red('❌ Deployment failed after retries'));
            }
            
            state.lastPrId = pr.pullRequestId;
            state.lastPrMergeTime = pr.mergeDate;
            state.lastDeployTime = new Date().toISOString();
            saveState(state);
          }
        } else {
          console.log(chalk.gray('🔍 No new PRs found'));
        }
      } catch (e) {
        console.log(chalk.yellow(`⚠️  Error: ${e.message}`));
      }
      
      console.log(chalk.gray(`   Next check in ${options.pollInterval} minute(s)...\n`));
      await new Promise(r => setTimeout(r, pollIntervalMs));
    }
  });

// ── STAGE Pipeline ────────────────────────────────────────────────────

program
  .command('stage')
  .description('Trigger STAGE pipeline deployment (with release tagging)')
  .option('--no-notify', 'Skip Teams/Power Automate notifications')
  .option('--no-pr-detect', 'Skip PR detection')
  .option('--no-tag', 'Skip release tag creation')
  .option('--branch <name>', 'Branch to deploy from (default: master)', 'master')
  .action(async (options) => {
    try {
      const config = getConfig();
      const defId = config.stage_definition_id;
      const branch = options.branch;

      console.log(chalk.blue(`🚀 Triggering STAGE pipeline (ID: ${defId})...`));

      // Detect PRs merged after last build
      let prMerges = [];
      if (options.prDetect) {
        try {
          const lastBuild = await azureService.getLastBuildInfo(defId, { includeInProgress: false });
          if (lastBuild && lastBuild.source_version) {
            console.log(chalk.gray(`   Last build: ${lastBuild.build_number} (${lastBuild.source_version.substring(0, 8)})`));
            prMerges = await azureService.getPrMergesAfterCommit(lastBuild.source_version, branch);
            if (prMerges.length > 0) {
              console.log(chalk.cyan(`   📋 ${prMerges.length} new PR(s) since last build:`));
              for (const pr of prMerges) {
                const ticket = pr.jira_ticket ? `${pr.jira_ticket}: ` : '';
                console.log(chalk.gray(`      • ${ticket}${pr.description} (PR #${pr.pr_number})`));
              }
            } else {
              console.log(chalk.gray('   No new PRs since last build.'));
            }
          }
        } catch (e) {
          console.log(chalk.yellow(`   ⚠️  Could not detect PRs: ${e.message}`));
        }
      }

      let tagName = null;

      // Create release tag
      if (options.tag) {
        try {
          const tagResult = await tagService.createReleaseTag(prMerges, branch, config.tag_repo_name);
          tagName = tagResult.tag_name;
          console.log(chalk.green(`   🏷️  Tag: ${tagName}`));
        } catch (e) {
          console.log(chalk.yellow(`   ⚠️  Tag creation failed: ${e.message}`));
          console.log(chalk.yellow('   Continuing with branch deployment...'));
        }
      }

      // Determine source ref: tag takes priority
      const sourceRef = tagName ? `refs/tags/${tagName}` : `refs/heads/${branch}`;
      console.log(chalk.gray(`   Source: ${sourceRef}`));

      // Trigger build
      const build = await azureService.triggerBuild(defId, sourceRef);
      console.log(chalk.green(`✅ Build triggered: ${build.buildNumber} (ID: ${build.id})`));
      console.log(chalk.gray(`🔗 URL: ${build._links?.web?.href || 'N/A'}`));

      // Send notification
      if (options.notify) {
        try {
          await teamsService.sendDeploymentNotification({
            pipeline: 'STAGE',
            status: 'started',
            buildNumber: build.buildNumber,
            buildId: build.id,
            prMerges,
            org: config.org,
            project: config.project
          });
          console.log(chalk.gray('   📨 Notification sent.'));
        } catch (e) {
          console.log(chalk.yellow(`   ⚠️  Notification failed: ${e.message}`));
        }
      }
    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Status ─────────────────────────────────────────────────────────────

program
  .command('status')
  .description('Check pipeline status')
  .option('-d, --definition-id <id>', 'Specific Build Definition ID')
  .option('-b, --build-id <id>', 'Specific Build ID')
  .option('--dev', 'Check DEV pipeline')
  .option('--stage', 'Check STAGE pipeline')
  .action(async (options) => {
    try {
      const config = getConfig();
      let defId;

      if (options.definitionId) {
        defId = options.definitionId;
      } else if (options.stage) {
        defId = config.stage_definition_id;
      } else {
        defId = config.dev_definition_id;
      }

      let build;
      if (options.buildId) {
        build = await azureService.getBuild(options.buildId);
      } else {
        console.log(chalk.blue(`🔍 Fetching latest build for definition ${defId}...`));
        const builds = await azureService.getLatestBuilds(defId);
        build = builds[0];
      }

      if (!build) {
        console.log(chalk.yellow('⚠️  No build found.'));
        return;
      }

      const statusIcon = build.status === 'completed'
        ? (build.result === 'succeeded' ? '✅' : '❌')
        : '🔄';

      console.log(`\n${statusIcon} Build ${chalk.bold(build.buildNumber)}`);
      console.log(`Status: ${build.status}`);
      if (build.result) console.log(`Result: ${build.result}`);
      console.log(`Started: ${new Date(build.startTime).toLocaleString()}`);
      console.log(chalk.gray(`🔗 URL: ${build._links?.web?.href || 'N/A'}\n`));

    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Create PR ─────────────────────────────────────────────────────────

program
  .command('create-pr')
  .description('Create a pull request with auto-generated title and description')
  .option('-s, --source <branch>', 'Source branch (default: current branch)')
  .option('-t, --target <branch>', 'Target branch', 'dev')
  .option('-w, --work-dir <path>', 'Git repository working directory')
  .option('--dry-run', 'Generate PR content without creating')
  .option('--master-to-dev', 'Use fixed master-to-dev sync title and description')
  .action(async (options) => {
    try {
      await prService.createPr({
        sourceBranch: options.source,
        targetBranch: options.target,
        workDir: options.workDir,
        dryRun: options.dryRun,
        masterToDev: options.masterToDev
      });
    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Tag ────────────────────────────────────────────────────────────────

program
  .command('tag')
  .description('Manage release tags')
  .option('--create', 'Create a new release tag')
  .option('--latest', 'Show the latest tag')
  .option('--branch <name>', 'Branch to tag from (default: master)', 'master')
  .option('--repo <name>', 'Repository name')
  .action(async (options) => {
    try {
      const config = getConfig();
      const repoName = options.repo || config.tag_repo_name;

      if (options.latest) {
        const latestTag = await azureService.getLatestTag(repoName);
        if (latestTag) {
          console.log(chalk.green(`✅ Latest tag: ${latestTag}`));
          const nextTag = tagService.incrementTagVersion(latestTag);
          console.log(chalk.gray(`   Next would be: ${nextTag}`));
        } else {
          console.log(chalk.yellow('No tags found. Next would be: v1.0.0'));
        }
        return;
      }

      if (options.create) {
        const tagResult = await tagService.createReleaseTag([], options.branch, repoName);
        console.log(chalk.green(`✅ Tag created: ${tagResult.tag_name}`));
        return;
      }

      // Default: show latest
      const latestTag = await azureService.getLatestTag(repoName);
      console.log(latestTag ? chalk.green(`Latest tag: ${latestTag}`) : chalk.yellow('No tags found.'));

    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Commits / PR Info ──────────────────────────────────────────────────

program
  .command('commits')
  .description('Show PRs merged after a specific commit')
  .option('-c, --commit <hash>', 'Commit hash to check from')
  .option('-b, --branch <name>', 'Branch name (default: dev)', 'dev')
  .action(async (options) => {
    try {
      let commitHash = options.commit;

      if (!commitHash) {
        const config = getConfig();
        const defId = config.dev_definition_id;
        console.log(chalk.blue('🔍 Finding last build commit...'));
        const lastBuild = await azureService.getLastBuildInfo(defId, { includeInProgress: false, requireFullstack: true });
        if (!lastBuild) {
          console.log(chalk.yellow('⚠️  No previous build found.'));
          return;
        }
        commitHash = lastBuild.source_version;
        console.log(chalk.gray(`   Last build: ${lastBuild.build_number} (${commitHash.substring(0, 8)})`));
      }

      const prMerges = await azureService.getPrMergesAfterCommit(commitHash, options.branch);

      if (prMerges.length === 0) {
        console.log(chalk.yellow('\nNo new PRs merged after this commit.'));
        return;
      }

      console.log(chalk.cyan(`\n📋 ${prMerges.length} PR(s) merged after ${commitHash.substring(0, 8)}:\n`));
      for (const pr of prMerges) {
        const ticket = pr.jira_ticket ? chalk.yellow(`${pr.jira_ticket}: `) : '';
        console.log(`  • PR #${pr.pr_number} - ${ticket}${pr.description}`);
        console.log(chalk.gray(`    Author: ${pr.author} | Commit: ${pr.commit_hash}`));
      }
      console.log('');
    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
    }
  });

// ── Unknown Command Handler ───────────────────────────────────────────

program.on('command:*', () => {
  console.error(chalk.red('Invalid command: %s\nSee --help for a list of available commands.'), program.args.join(' '));
  process.exit(1);
});

if (!process.argv.slice(2).length) {
  program.outputHelp();
} else {
  program.parse(process.argv);
}
