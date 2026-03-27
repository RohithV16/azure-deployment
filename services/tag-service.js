const azureService = require('./azure-service');

function incrementTagVersion(tagName) {
  if (!tagName) return 'v1.0.0';

  const version = tagName.replace(/^v/i, '');
  const parts = version.split('.').map(Number);

  if (parts.length >= 3) {
    return `v${parts[0]}.${parts[1]}.${(parts[2] || 0) + 1}`;
  } else if (parts.length === 2) {
    return `v${parts[0]}.${(parts[1] || 0) + 1}.0`;
  } else if (parts.length === 1) {
    return `v${parts[0]}.0.1`;
  }

  return 'v1.0.0';
}

function generatePrSummary(prMerges) {
  if (!prMerges || prMerges.length === 0) return 'No PRs in this release';

  const now = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  const lines = [];
  lines.push(`Release Date: ${now}`);
  lines.push(`Release includes ${prMerges.length} PR(s):\n`);

  prMerges.forEach((pr, i) => {
    const num = i + 1;
    if (pr.jira_ticket) {
      lines.push(`${num}. ${pr.jira_ticket}: ${pr.description} (PR #${pr.pr_number})`);
    } else {
      lines.push(`${num}. ${pr.description} (PR #${pr.pr_number})`);
    }
  });

  return lines.join('\n');
}

async function createReleaseTag(prMerges, branch = 'master', repoName) {
  console.log(`\n🏷️  Creating release tag...`);
  console.log(`   Repository: ${repoName || 'default'}`);
  console.log(`   Branch: ${branch}`);

  const latestTag = await azureService.getLatestTag(repoName);
  console.log(`   Latest tag: ${latestTag || 'None (first tag)'}`);

  const newTagName = incrementTagVersion(latestTag);
  console.log(`   New tag: ${newTagName}`);

  const commitHash = await azureService.getLatestCommitFromBranch(branch, repoName);
  if (!commitHash) {
    throw new Error(`No commits found on ${branch} branch`);
  }
  console.log(`   Commit: ${commitHash.substring(0, 8)}`);

  const description = generatePrSummary(prMerges);
  const result = await azureService.createTag(newTagName, commitHash, description, repoName);

  if (result) {
    console.log(`✅ Release tag '${newTagName}' created successfully!`);
    return result;
  }

  throw new Error('Failed to create release tag');
}

module.exports = {
  incrementTagVersion,
  generatePrSummary,
  createReleaseTag
};
