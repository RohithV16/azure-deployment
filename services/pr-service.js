const azureService = require('./azure-service');
const gitService = require('./git-service');
const teamsService = require('./teams-service');
const { getConfig } = require('../config');

function getPrConfig() {
  const config = getConfig();
  return {
    org: config.org,
    project: config.project,
    repoName: config.tag_repo_name,
    jiraBaseUrl: config.jira_base_url
  };
}

function convertApiUrlToWebUrl(apiUrl) {
  if (!apiUrl) return null;
  const { org, project, repoName } = getPrConfig();
  const prIdMatch = apiUrl.match(/\/pull[Rr]equests?\/(\d+)/);
  if (!prIdMatch) return apiUrl;
  const prId = prIdMatch[1];
  return `${org}/${project}/_git/${repoName}/pullrequest/${prId}`;
}

async function createPr({ sourceBranch, targetBranch, workDir, dryRun = false, masterToDev = false }) {
  const { org, project, repoName, jiraBaseUrl } = getPrConfig();
  const branch = sourceBranch || gitService.getCurrentBranch(workDir);
  if (!branch) {
    throw new Error('Could not determine current branch. Use --source to specify.');
  }

  const repoId = await azureService.getRepositoryId(repoName);

  let title, description;

  if (masterToDev) {
    const { jiraBaseUrl } = getPrConfig();
    const jiraTicket = 'ADW-1245';
    title = `${jiraTicket} [Merkle] master ➜ dev`;
    description = generateMasterToDevDescription(jiraTicket, jiraBaseUrl);
  } else {
    const { jiraBaseUrl } = getPrConfig();
    const jiraTicket = gitService.extractJiraTicket(branch);
    if (!jiraTicket) {
      throw new Error(`Could not extract Jira ticket (ADW-XXXX) from branch name: ${branch}`);
    }

    const commits = gitService.getCommits(branch, targetBranch, workDir);
    const fileChanges = gitService.getFileChangesSummary(branch, targetBranch, workDir);

    title = gitService.generatePrTitle(branch, jiraTicket, commits);
    description = gitService.generatePrDescription(jiraTicket, commits, fileChanges, jiraBaseUrl);
  }

  console.log(`\n📋 PR Title: ${title}`);
  console.log(`📝 Target: ${targetBranch}`);
  console.log(`🌿 Source: ${branch}`);

  if (dryRun) {
    console.log('\n--- DRY RUN ---');
    console.log('\nDescription:\n' + description);
    return null;
  }

  // Check for existing PR
  const existingPr = await azureService.checkExistingPr(repoId, branch, targetBranch);
  if (existingPr) {
    const prUrl = convertApiUrlToWebUrl(existingPr.url);
    console.log(`\n✨ An active pull request already exists!`);
    console.log(`   PR ID: ${existingPr.pullRequestId}`);
    console.log(`   URL: ${prUrl}`);
    return existingPr;
  }

  // Check branch is up to date
  const upToDate = gitService.isBranchUpToDate(branch, targetBranch, workDir);
  if (!upToDate) {
    console.log(`\n⚠️  Branch '${branch}' is not up to date with '${targetBranch}'.`);
    console.log('   Attempting to merge...');
    const mergeResult = gitService.attemptMerge(branch, targetBranch, workDir);
    if (!mergeResult.ok) {
      console.log(`❌ ${mergeResult.message}`);
      throw new Error('Branch is not up to date and merge failed. Please resolve manually.');
    }
    console.log(`✅ ${mergeResult.message}`);
  }

  // Create the PR
  const prData = await azureService.createPullRequest(repoId, branch, targetBranch, title, description);

  if (prData) {
    const prId = prData.pullRequestId;
    const prUrl = convertApiUrlToWebUrl(prData.url) || prData.url;

    console.log(`\n✅ Pull request created successfully!`);
    console.log(`   PR ID: ${prId}`);
    console.log(`   Title: ${prData.title}`);
    console.log(`   Status: ${prData.status}`);
    console.log(`   URL: ${prUrl}`);

    // Send notification
    try {
      await teamsService.sendPrNotification(prData);
    } catch (_) {}
  }

  return prData;
}

function generateMasterToDevDescription(ticket, jiraBaseUrl) {
  return `## What does this PR do?\n\nmaster to dev sync\n\n---\n\n## What are the relevant tickets?\n\n[${ticket}](${jiraBaseUrl}/${ticket})\n\n---\n\n## Has the Sonarqube scan for your branch been reviewed to make sure no new issues have been introduced?\n\n- [ ] YES - Sonarqube scan has been reviewed and no new issues have been introduced\n- [ ] NO - Sonarqube scan has NOT been reviewed (explanation required below)\n\n---\n\n## Describe how these changes have been tested\n\nManual testing performed.\n\n---\n\n## Additional Resources / Comments\n\nNone.\n`;
}

module.exports = {
  createPr,
  convertApiUrlToWebUrl
};
