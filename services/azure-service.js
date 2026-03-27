const axios = require('axios');
const chalk = require('chalk');
const { getConfig } = require('../config');

class AzureService {
  constructor() {
    this._init();
  }

  _init() {
    const config = getConfig();
    this.org = config.org;
    this.project = config.project;
    this.token = config.token;
    this.repoName = config.tag_repo_name || 'aemaacs-life';

    if (this.token) {
      this.headers = {
        'Authorization': `Basic ${Buffer.from(`:${this.token}`).toString('base64')}`,
        'Content-Type': 'application/json'
      };
    } else {
      this.headers = { 'Content-Type': 'application/json' };
    }

    this.client = axios.create({
      baseURL: `${this.org}/${this.project}/_apis`,
      headers: this.headers,
      timeout: 30000
    });
  }

  _refreshConfig() {
    this._init();
  }

  // ── Repository ──────────────────────────────────────────────────────

  async getRepositories() {
    this._refreshConfig();
    try {
      const response = await this.client.get('/git/repositories?api-version=7.0');
      return response.data.value || [];
    } catch (error) {
      this.handleError(error);
    }
  }

  async getRepositoryId(repoName) {
    this._refreshConfig();
    const name = repoName || this.repoName;
    try {
      const response = await this.client.get('/git/repositories?api-version=7.0');
      const repos = response.data.value || [];
      for (const repo of repos) {
        if (repo.name === name) return repo.id;
      }
      throw new Error(`Repository '${name}' not found`);
    } catch (error) {
      this.handleError(error);
    }
  }

  async getBranches(repoId) {
    this._refreshConfig();
    try {
      const response = await this.client.get(`/git/repositories/${repoId}/refs?filter=heads/&api-version=7.0`);
      return response.data.value || [];
    } catch (error) {
      this.handleError(error);
    }
  }

  // ── Builds ──────────────────────────────────────────────────────────

  async triggerBuild(definitionId, sourceRef) {
    this._refreshConfig();
    const payload = {
      definition: { id: parseInt(definitionId) }
    };

    if (sourceRef) {
      payload.sourceBranch = sourceRef;
    }

    try {
      const response = await this.client.post('/build/builds?api-version=7.0', payload);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  async getBuild(buildId) {
    this._refreshConfig();
    try {
      const response = await this.client.get(`/build/builds/${buildId}?api-version=7.0`);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  async getLatestBuilds(definitionId, top = 1, requireFullstack = false) {
    this._refreshConfig();
    const fetchCount = requireFullstack ? 200 : Math.max(top, 10);
    try {
      const response = await this.client.get(
        `/build/builds?definitions=${definitionId}&$top=${fetchCount}&api-version=7.0`
      );
      const builds = response.data.value || [];

      if (requireFullstack) {
        const filtered = builds.filter(b => {
          const result = b.result;
          if (result !== 'succeeded' && result !== 'partiallySucceeded') return false;
          const tp = b.templateParameters || {};
          return tp.deploymentType === 'Full Stack';
        });
        return filtered.slice(0, top);
      }

      return builds.slice(0, top);
    } catch (error) {
      this.handleError(error);
    }
  }

  async getLastBuildInfo(definitionId, { includeInProgress = false, requireFullstack = false } = {}) {
    this._refreshConfig();
    try {
      const response = await this.client.get(
        `/build/builds?definitions=${definitionId}&$top=200&api-version=7.0`
      );
      const builds = response.data.value || [];

      let validBuilds = [];
      let inProgressBuilds = [];

      for (const build of builds) {
        const result = build.result;
        const status = build.status;

        if (result === 'succeeded' || result === 'partiallySucceeded') {
          if (requireFullstack) {
            const tp = build.templateParameters || {};
            if (tp.deploymentType === 'Full Stack') {
              validBuilds.push(build);
            }
          } else {
            validBuilds.push(build);
          }
        }

        if (includeInProgress && (status === 'inProgress' || status === 'notStarted')) {
          inProgressBuilds.push(build);
        }
      }

      if (includeInProgress && inProgressBuilds.length > 0) {
        const b = inProgressBuilds[0];
        return {
          build_number: b.buildNumber,
          build_id: b.id,
          source_version: b.sourceVersion,
          start_time: b.startTime,
          result: b.result,
          status: b.status
        };
      }

      if (validBuilds.length > 0) {
        const b = validBuilds[0];
        return {
          build_number: b.buildNumber,
          build_id: b.id,
          source_version: b.sourceVersion,
          start_time: b.startTime,
          result: b.result,
          status: b.status
        };
      }

      return null;
    } catch (error) {
      this.handleError(error);
    }
  }

  async getBuildTimeline(buildId) {
    this._refreshConfig();
    try {
      const response = await this.client.get(`/build/builds/${buildId}/timeline?api-version=7.0`);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  // ── Tags ────────────────────────────────────────────────────────────

  async getLatestTag(repoName) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId(repoName);
    try {
      const response = await this.client.get(
        `/git/repositories/${repoId}/refs?filter=tags&api-version=7.0`
      );
      const tags = (response.data.value || [])
        .map(t => t.name.replace('refs/tags/', ''))
        .filter(Boolean);

      if (tags.length === 0) return null;

      tags.sort((a, b) => {
        const pa = a.replace(/^v/i, '').split('.').map(Number);
        const pb = b.replace(/^v/i, '').split('.').map(Number);
        for (let i = 0; i < 3; i++) {
          if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) - (pb[i] || 0);
        }
        return 0;
      });

      return tags[tags.length - 1];
    } catch (error) {
      this.handleError(error);
    }
  }

  async getCommitFromTag(tagName, repoName) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId(repoName);
    try {
      const response = await this.client.get(
        `/git/repositories/${repoId}/refs?filter=refs/tags/${tagName}&api-version=7.0`
      );
      const refs = response.data.value || [];
      if (refs.length === 0) return null;

      const objectId = refs[0].objectId;

      // Try annotated tag first
      try {
        const annotated = await this.client.get(
          `/git/repositories/${repoId}/annotatedtags/${objectId}?api-version=7.0`
        );
        const taggedObjectId = annotated.data.taggedObject?.objectId;
        if (taggedObjectId) {
          await this.client.get(`/git/repositories/${repoId}/commits/${taggedObjectId}?api-version=7.0`);
          return taggedObjectId;
        }
      } catch (_) { /* not an annotated tag */ }

      // Try lightweight tag (object is directly the commit)
      try {
        await this.client.get(`/git/repositories/${repoId}/commits/${objectId}?api-version=7.0`);
        return objectId;
      } catch (_) { /* not a commit either */ }

      return null;
    } catch (error) {
      this.handleError(error);
    }
  }

  async createTag(tagName, commitHash, description, repoName) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId(repoName);

    // Resolve commit object ID
    let commitObjectId;
    try {
      const commitResp = await this.client.get(
        `/git/repositories/${repoId}/commits/${commitHash}?api-version=7.0`
      );
      commitObjectId = commitResp.data.commitId;
    } catch (error) {
      throw new Error(`Failed to resolve commit ${commitHash}: ${error.message}`);
    }

    // Try annotated tag first
    try {
      const tagResp = await this.client.post(
        `/git/repositories/${repoId}/annotatedtags?api-version=7.0`,
        {
          name: tagName,
          taggedObject: { objectId: commitObjectId },
          message: description,
          tagger: {
            name: 'Deployment Automation',
            email: 'deployment@automation',
            date: new Date().toISOString()
          }
        }
      );

      const tagObjectId = tagResp.data.objectId;

      // Create the ref pointing to the tag object
      await this.client.post(`/git/repositories/${repoId}/refs?api-version=7.0`, [{
        name: `refs/tags/${tagName}`,
        oldObjectId: '0000000000000000000000000000000000000000',
        newObjectId: tagObjectId
      }]);

      return { tag_name: tagName, commit_hash: commitHash, description };
    } catch (_) {
      // Fallback to lightweight tag
      await this.client.post(`/git/repositories/${repoId}/refs?api-version=7.0`, [{
        name: `refs/tags/${tagName}`,
        oldObjectId: '0000000000000000000000000000000000000000',
        newObjectId: commitObjectId
      }]);

      return { tag_name: tagName, commit_hash: commitHash, description };
    }
  }

  // ── Commits ─────────────────────────────────────────────────────────

  async getLatestCommitFromBranch(branch, repoName) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId(repoName);
    const branchName = branch.replace('refs/heads/', '');
    try {
      const response = await this.client.get(`/git/repositories/${repoId}/commits`, {
        params: {
          'searchCriteria.itemVersion.version': branchName,
          'searchCriteria.itemVersion.versionType': 'branch',
          '$top': 1,
          'api-version': '7.0'
        }
      });
      const commits = response.data.value || [];
      return commits.length > 0 ? commits[0].commitId : null;
    } catch (error) {
      this.handleError(error);
    }
  }

  async getCommit(commitHash, repoName) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId(repoName);
    try {
      const response = await this.client.get(
        `/git/repositories/${repoId}/commits/${commitHash}?api-version=7.0`
      );
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  // ── PR Merges ───────────────────────────────────────────────────────

  async getPrMergesAfterCommit(commitHash, branch) {
    this._refreshConfig();
    const repoId = await this.getRepositoryId();
    const branchName = branch.replace('refs/heads/', '');

    // Get baseline commit date
    let baselineDate;
    try {
      const commitResp = await this.client.get(
        `/git/repositories/${repoId}/commits/${commitHash}?api-version=7.0`
      );
      baselineDate = commitResp.data.committer?.date;
    } catch (_) {}

    if (!baselineDate) {
      throw new Error(`Could not get baseline commit date for ${commitHash}`);
    }

    // Get commits from branch
    const commitsResp = await this.client.get(`/git/repositories/${repoId}/commits`, {
      params: {
        'searchCriteria.itemVersion.version': branchName,
        'searchCriteria.itemVersion.versionType': 'branch',
        'api-version': '7.0',
        '$top': 100
      }
    });

    const commits = commitsResp.data.value || [];
    const baselineDt = new Date(baselineDate);

    const commitsAfter = commits.filter(c => {
      if (c.commitId === commitHash) return false;
      const cd = new Date(c.committer?.date || 0);
      return cd > baselineDt;
    });

    if (commitsAfter.length === 0) return [];

    const prMerges = [];
    for (const commit of commitsAfter) {
      const msg = commit.comment || '';
      const authorName = commit.author?.name || 'Unknown';

      if (!msg.includes('Merged PR')) continue;

      try {
        const prPart = msg.split('Merged PR ')[1];
        const prNumber = prPart.split(':')[0].trim();
        if (!/^\d+$/.test(prNumber)) continue;

        let jiraTicket = null;
        const jiraMatch = msg.match(/ADW-\d+/i);
        if (jiraMatch) jiraTicket = jiraMatch[0].toUpperCase();

        let description = '';
        const afterPr = msg.split('Merged PR')[1];
        if (afterPr && afterPr.includes(':')) {
          description = afterPr.split(':').slice(1).join(':').trim();
        }
        if (jiraTicket) description = description.replace(jiraTicket, '').trim();
        description = description.replace('[Merkle]', '').trim();

        prMerges.push({
          pr_number: prNumber,
          jira_ticket: jiraTicket,
          description: description,
          author: authorName.replace('X', '').trim(),
          commit_hash: commit.commitId.substring(0, 8),
          note: 'Merged after build'
        });
      } catch (_) {}
    }

    return prMerges;
  }

  // ── Pull Requests ───────────────────────────────────────────────────

  async checkExistingPr(repoId, sourceBranch, targetBranch) {
    this._refreshConfig();
    const srcRef = sourceBranch.startsWith('refs/heads/') ? sourceBranch : `refs/heads/${sourceBranch}`;
    const tgtRef = targetBranch.startsWith('refs/heads/') ? targetBranch : `refs/heads/${targetBranch}`;
    try {
      const response = await this.client.get(
        `/git/repositories/${repoId}/pullrequests?api-version=7.0&searchCriteria.status=active&searchCriteria.sourceRefName=${srcRef}&searchCriteria.targetRefName=${tgtRef}`
      );
      const prs = response.data.value || [];
      return prs.length > 0 ? prs[0] : null;
    } catch (error) {
      this.handleError(error);
    }
  }

  async createPullRequest(repoId, sourceBranch, targetBranch, title, description) {
    this._refreshConfig();
    const srcRef = sourceBranch.startsWith('refs/heads/') ? sourceBranch : `refs/heads/${sourceBranch}`;
    const tgtRef = targetBranch.startsWith('refs/heads/') ? targetBranch : `refs/heads/${targetBranch}`;

    const payload = {
      sourceRefName: srcRef,
      targetRefName: tgtRef,
      title,
      description
    };

    if (targetBranch.toLowerCase() === 'dev') {
      payload.completionOptions = { autoCompleteIgnoreConfigIds: [] };
    }

    try {
      const response = await this.client.post(
        `/git/repositories/${repoId}/pullrequests?api-version=7.1`,
        payload
      );
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  // ── Work Items ──────────────────────────────────────────────────────

  async searchWorkItems(query, top = 20) {
    this._refreshConfig();
    try {
      const wiqlResp = await this.client.post('/wit/wiql?api-version=7.0', {
        query: `SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.TeamProject] = '${this.project}' AND ([System.Id] CONTAINS '${query}' OR [System.Title] CONTAINS '${query}') ORDER BY [System.ChangedDate] DESC`
      });

      const ids = (wiqlResp.data.workItems || []).slice(0, top).map(w => w.id);
      if (ids.length === 0) return [];

      const itemsResp = await this.client.get(
        `/wit/workitems?ids=${ids.join(',')}&api-version=7.0`
      );

      return (itemsResp.data.value || []).map(item => {
        const title = item.fields?.['System.Title'] || '';
        const ticketMatch = title.match(/ADW-\d+/i);
        return {
          id: ticketMatch ? ticketMatch[0].toUpperCase() : `WI-${item.id}`,
          title,
          type: item.fields?.['System.WorkItemType'] || ''
        };
      });
    } catch (error) {
      this.handleError(error);
    }
  }

  // ── Profile ─────────────────────────────────────────────────────────

  async getCurrentUser() {
    this._refreshConfig();
    try {
      const profileUrl = `${this.org}/_apis/profile/profiles/me?api-version=7.0`;
      const response = await axios.get(profileUrl, { headers: this.headers });
      return {
        id: response.data.id,
        displayName: response.data.displayName,
        emailAddress: response.data.emailAddress || '',
        name: response.data.displayName || 'Unknown User'
      };
    } catch (_) {
      return {
        id: 'unknown',
        displayName: 'Deployment Automation',
        emailAddress: 'deployment@automation',
        name: 'Deployment Automation'
      };
    }
  }

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

  async approveBuild(approvalId) {
    this._refreshConfig();
    try {
      const response = await this.client.patch(
        `/pipelines/approvals/${approvalId}?api-version=7.0`,
        {
          status: 'approved'
        }
      );
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  async waitForApproval(buildId, maxWaitMs = 7200000) {
    const startTime = Date.now();
    const pollInterval = 30000;
    const timeoutMinutes = Math.round(maxWaitMs / 60000);

    while (Date.now() - startTime < maxWaitMs) {
      const approvals = await this.queryApprovals(buildId);

      if (approvals.length === 0) {
        return true;
      }

      const pendingApprovals = approvals.filter(a => a.status === 'pending');

      if (pendingApprovals.length === 0) {
        return true;
      }

      try {
        for (const approval of pendingApprovals) {
          await this.approveBuild(approval.id);
        }
        return true;
      } catch (e) {
        const status = e.response?.status;
        if (status === 401 || status === 403 || status === 404) {
          throw e;
        }
        console.log(chalk.gray('⏳ Waiting for approval...'));
      }

      await new Promise(r => setTimeout(r, pollInterval));
    }

    throw new Error(`Approval timeout after ${timeoutMinutes} minutes`);
  }

  // ── Error Handling ──────────────────────────────────────────────────

  handleError(error) {
    if (error.response) {
      if (error.response.status === 401) {
        throw new Error('Unauthorized: Please check your PAT token using "mandg update --token"');
      }
      throw new Error(`Azure API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
    }
    throw error;
  }
}

module.exports = new AzureService();
