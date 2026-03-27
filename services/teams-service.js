const axios = require('axios');
const { getConfig } = require('../config');

function getWebhookUrls() {
  const config = getConfig();
  return {
    teams: config.teams_webhook_url,
    powerAutomate: config.power_automate_webhook_url
  };
}

async function sendMessage(webhookUrl, message) {
  const { powerAutomate: powerAutomateUrl } = getWebhookUrls();
  let payload;

  if (webhookUrl === powerAutomateUrl && powerAutomateUrl) {
    payload = {
      type: 'message',
      attachments: [{
        contentType: 'application/vnd.microsoft.card.adaptive',
        content: {
          type: 'AdaptiveCard',
          $schema: 'http://adaptivecards.io/schemas/adaptive-card.json',
          version: '1.2',
          body: [{ type: 'TextBlock', text: message, wrap: true }]
        }
      }]
    };
  } else {
    payload = { text: message };
  }

  try {
    const response = await axios.post(webhookUrl, payload);
    if (response.status === 200 || response.status === 202) {
      return true;
    }
    console.error(`❌ Failed to send message: ${response.status}`);
    return false;
  } catch (error) {
    console.error(`❌ Error sending message: ${error.message}`);
    return false;
  }
}

async function sendToTeams(message) {
  const { teams } = getWebhookUrls();
  if (!teams) {
    console.warn('⚠️ teams_webhook_url not configured. Skipping Teams notification.');
    return false;
  }
  return sendMessage(teams, message);
}

async function sendToPowerAutomate(message) {
  const { powerAutomate } = getWebhookUrls();
  if (!powerAutomate) {
    console.warn('⚠️ power_automate_webhook_url not configured. Skipping Power Automate notification.');
    return false;
  }
  return sendMessage(powerAutomate, message);
}

async function sendDeploymentNotification({ pipeline, status, buildNumber, buildId, prMerges = [], org, project }) {
  const url = org && project
    ? `${org}/${project}/_build/results?buildId=${buildId}`
    : '';

  let message = '';
  if (status === 'started') {
    message = `🚀 **Deployment Started**\n`;
    message += `Pipeline: ${pipeline}\n`;
    message += `Build: ${buildNumber} (ID: ${buildId})\n`;
    message += `Status: In Progress\n`;
    if (prMerges.length > 0) {
      message += `\n📋 **Changes included (${prMerges.length} PRs):**\n`;
      for (const pr of prMerges) {
        const ticket = pr.jira_ticket ? `${pr.jira_ticket}: ` : '';
        message += `• ${ticket}${pr.description} (PR #${pr.pr_number})\n`;
      }
    }
    if (url) message += `\n🔗 ${url}`;
  } else if (status === 'succeeded') {
    message = `✅ **Deployment Succeeded**\n`;
    message += `Pipeline: ${pipeline}\n`;
    message += `Build: ${buildNumber} (ID: ${buildId})\n`;
    if (prMerges.length > 0) {
      message += `\n📋 **Deployed PRs (${prMerges.length}):**\n`;
      for (const pr of prMerges) {
        const ticket = pr.jira_ticket ? `${pr.jira_ticket}: ` : '';
        message += `• ${ticket}${pr.description} (PR #${pr.pr_number})\n`;
      }
    }
    if (url) message += `\n🔗 ${url}`;
  } else if (status === 'failed') {
    message = `❌ **Deployment Failed**\n`;
    message += `Pipeline: ${pipeline}\n`;
    message += `Build: ${buildNumber} (ID: ${buildId})\n`;
    if (url) message += `\n🔗 ${url}`;
  }

  await Promise.allSettled([
    sendToTeams(message),
    sendToPowerAutomate(message)
  ]);
}

async function sendPrNotification(prData) {
  const message = `🔀 **Pull Request Created**\n` +
    `PR #${prData.pullRequestId}: ${prData.title}\n` +
    `Status: ${prData.status}\n` +
    `${prData.url || ''}`;

  await Promise.allSettled([
    sendToTeams(message),
    sendToPowerAutomate(message)
  ]);
}

module.exports = {
  sendToTeams,
  sendToPowerAutomate,
  sendDeploymentNotification,
  sendPrNotification
};
