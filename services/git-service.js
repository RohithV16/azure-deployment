const { execSync } = require('child_process');
const path = require('path');

function findGitRoot(startPath) {
  let current = startPath || process.cwd();
  const root = path.parse(current).root;

  while (current !== root) {
    try {
      const gitDir = path.join(current, '.git');
      require('fs').accessSync(gitDir);
      return current;
    } catch (_) {
      current = path.dirname(current);
    }
  }
  return null;
}

function runGit(cmd, workDir) {
  const cwd = workDir || findGitRoot() || process.cwd();
  try {
    return { ok: true, output: execSync(cmd, { cwd, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim() };
  } catch (e) {
    return { ok: false, output: (e.stderr || e.message || '').trim() };
  }
}

function getCurrentBranch(workDir) {
  const r = runGit('git branch --show-current', workDir);
  return r.ok ? r.output : null;
}

function extractJiraTicket(branchName) {
  const match = branchName.match(/ADW-\d+/i);
  return match ? match[0].toUpperCase() : null;
}

function getCommits(sourceBranch, targetBranch, workDir) {
  const commands = [
    `git log --oneline origin/${targetBranch}..HEAD`,
    `git log --oneline ${targetBranch}..HEAD`,
    `git log --oneline origin/${targetBranch}..${sourceBranch}`,
    `git log --oneline ${targetBranch}..${sourceBranch}`
  ];

  for (const cmd of commands) {
    const r = runGit(cmd, workDir);
    if (r.ok && r.output) {
      return r.output.split('\n').filter(Boolean);
    }
  }
  return [];
}

function getFileChangesSummary(sourceBranch, targetBranch, workDir) {
  const commands = [
    `git diff --stat origin/${targetBranch}...HEAD`,
    `git diff --stat ${targetBranch}...HEAD`,
    `git diff --stat origin/${targetBranch}...${sourceBranch}`,
    `git diff --stat ${targetBranch}...${sourceBranch}`
  ];

  for (const cmd of commands) {
    const r = runGit(cmd, workDir);
    if (r.ok && r.output) return r.output;
  }
  return '';
}

function isBranchUpToDate(sourceBranch, targetBranch, workDir) {
  const commands = [
    `git log --oneline ${sourceBranch}..origin/${targetBranch}`,
    `git log --oneline ${sourceBranch}..${targetBranch}`,
    `git log --oneline origin/${sourceBranch}..origin/${targetBranch}`,
    `git log --oneline origin/${sourceBranch}..${targetBranch}`
  ];

  for (const cmd of commands) {
    const r = runGit(cmd, workDir);
    if (r.ok) {
      const commits = r.output ? r.output.split('\n').filter(Boolean) : [];
      return commits.length === 0;
    }
  }
  return true;
}

function checkMergeConflicts(workDir) {
  const r = runGit('git ls-files -u', workDir);
  if (r.ok && r.output) return true;

  const status = runGit('git status --porcelain', workDir);
  if (status.ok) {
    for (const line of status.output.split('\n')) {
      if (line.startsWith('UU ') || line.startsWith('AA ') || line.startsWith('DD ')) return true;
    }
  }
  return false;
}

function attemptMerge(sourceBranch, targetBranch, workDir) {
  // Abort any existing merge
  runGit('git merge --abort', workDir);

  // Checkout source
  const co = runGit(`git checkout ${sourceBranch}`, workDir);
  if (!co.ok) return { ok: false, message: `Failed to checkout ${sourceBranch}: ${co.output}` };

  const mergeTarget = `origin/${targetBranch}`;
  const merge = runGit(`git merge --no-edit --no-ff ${mergeTarget}`, workDir);

  if (merge.ok) {
    if (merge.output.includes('Already up to date')) {
      return { ok: true, message: 'Branch is already up to date (no merge needed)' };
    }
    const push = runGit(`git push origin ${sourceBranch}`, workDir);
    if (push.ok) {
      return { ok: true, message: 'Merge completed successfully and pushed to remote' };
    }
    return { ok: false, message: `Merge completed but push failed: ${push.output}` };
  }

  if (checkMergeConflicts(workDir)) {
    runGit('git merge --abort', workDir);
    return { ok: false, message: 'Merge conflicts detected. Please resolve conflicts manually.' };
  }

  return { ok: false, message: `Merge failed: ${merge.output}` };
}

function generatePrTitle(branchName, jiraTicket, commits) {
  if (!jiraTicket) jiraTicket = 'Unknown';

  let descriptive = '';
  if (branchName.includes(jiraTicket)) {
    descriptive = branchName.split(jiraTicket)[1].replace(/^[-_ ]+/, '').replace(/[-_]+/g, ' ');
    descriptive = descriptive.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  } else if (commits.length > 0) {
    descriptive = commits[0].replace(/^[a-f0-9]+\s+/, '').replace(/ADW-\d+\s*/gi, '').substring(0, 50).trim();
  } else {
    descriptive = 'Changes';
  }

  return `${jiraTicket} [Merkle] ${descriptive}`;
}

function generatePrDescription(jiraTicket, commits, fileChanges, jiraBaseUrl = 'https://mandg.atlassian.net/browse') {
  const summary = generatePrSummary(commits, fileChanges);
  const testingDesc = generateTestingDescription(fileChanges);

  return `## What does this PR do?\n\n${summary}\n\n---\n\n## What are the relevant tickets?\n\n[${jiraTicket}](${jiraBaseUrl}/${jiraTicket})\n\n---\n\n## Has the Sonarqube scan for your branch been reviewed to make sure no new issues have been introduced?\n\n- [ ] YES\n- [ ] NO\n\n## Describe how these changes have been tested\n${testingDesc}\n\n## Additional Resources / Comments\nNone.\n`;
}

function generatePrSummary(commits, fileChanges) {
  if (!commits || commits.length === 0) return 'Updates from current branch';

  const cleaned = [];
  for (const c of commits.slice(0, 5)) {
    let msg = c.replace(/^[a-f0-9]+\s+/, '').replace(/ADW-\d+\s*/gi, '').trim();
    if (msg) cleaned.push(msg);
  }

  if (cleaned.length > 0) {
    let summary = cleaned[0];
    summary = summary.charAt(0).toUpperCase() + summary.slice(1);
    if (!summary.match(/[.!?]$/)) summary += '.';
    return summary;
  }

  if (fileChanges) {
    if (fileChanges.match(/\.java\s/)) return 'Updates Java components and configurations.';
    if (fileChanges.match(/\.xml\s/)) return 'Updates XML configurations.';
    if (fileChanges.match(/\.(js|jsx|ts|tsx)\s/)) return 'Updates JavaScript/TypeScript components.';
  }

  return 'Implements changes as described in the ticket.';
}

function generateTestingDescription(fileChanges) {
  if (!fileChanges) return 'Manual testing performed in AEM author environment.';

  const hasTests = fileChanges.match(/(test|spec)\.(java|js|ts)/i);
  if (hasTests) return 'Unit tests added/updated. Manual testing performed in AEM author environment.';

  return 'Manual testing performed in AEM author environment.';
}

module.exports = {
  findGitRoot,
  runGit,
  getCurrentBranch,
  extractJiraTicket,
  getCommits,
  getFileChangesSummary,
  isBranchUpToDate,
  checkMergeConflicts,
  attemptMerge,
  generatePrTitle,
  generatePrDescription,
  generatePrSummary,
  generateTestingDescription
};
