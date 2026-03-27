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

program
  .name('mandg')
  .description('M&G AEM Azure Deployment CLI (Pure JS REST API)')
  .version('3.0.0');

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

// ── DEV Pipeline ──────────────────────────────────────────────────────

program
  .command('dev')
  .description('Trigger DEV pipeline deployment')
  .option('--no-notify', 'Skip Teams/Power Automate notifications')
  .option('--no-pr-detect', 'Skip PR detection')
  .option('--branch <branchname>', 'Feature branch to deploy (optional, omit for interactive selection)')
  .action(async (options) => {
    try {
      const config = getConfig();
      const defId = config.dev_definition_id;
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

      // Trigger build with source branch
      let build = await azureService.triggerBuild(defId, `refs/heads/${branch}`);
      console.log(chalk.green(`✅ Build triggered: ${build.buildNumber} (ID: ${build.id})`));
      console.log(chalk.gray(`🔗 URL: ${build._links?.web?.href || 'N/A'}`));

      // Poll for completion
      let finalBuild = build;
      while (!['completed', 'cancelled'].includes(finalBuild.status)) {
        await new Promise(r => setTimeout(r, 15000));
        finalBuild = await azureService.getBuild(build.id);
      }
      let buildResult = finalBuild.result;

      // Auto-retry on failure
      let retries = 0;
      while (buildResult === 'failed' && retries < 2) {
        console.log(chalk.yellow(`⚠️ Build failed. Retrying in 30s... (${retries + 1}/2)`));
        await new Promise(r => setTimeout(r, 30000));

        build = await azureService.triggerBuild(defId, `refs/heads/${branch}`);
        console.log(chalk.green(`🔄 Retrying build: ${build.buildNumber} (ID: ${build.id})`));

        finalBuild = build;
        while (!['completed', 'cancelled'].includes(finalBuild.status)) {
          await new Promise(r => setTimeout(r, 15000));
          finalBuild = await azureService.getBuild(build.id);
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
    } catch (error) {
      console.error(chalk.red(`❌ Error: ${error.message}`));
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
