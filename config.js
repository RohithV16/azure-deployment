const fs = require('fs');
const path = require('path');
const os = require('os');

const CONFIG_PATH = path.join(os.homedir(), '.azure-deploy-aem.json');

const DEFAULT_CONFIG = {
  org: 'https://mpcoderepo.visualstudio.com',
  project: 'DigitalExperience',
  dev_definition_id: '3274',
  stage_definition_id: '3308',
  tag_repo_name: 'aemaacs-life',
  jira_base_url: 'https://mandg.atlassian.net/browse',
  teams_webhook_url: 'https://aegisdentsunetwork.webhook.office.com/webhookb2/c448e610-8c38-45ad-a939-db5a4ece46d5@6e8992ec-76d5-4ea5-8eae-b0c5e558749a/IncomingWebhook/0dc0e4fca542427fb3d6a02281a88574/d881b4fa-b65f-4e61-bb1a-b48354c99b1c/V2WHmoL-a3Tw0P84hKNYK4FI_U6TSWBShEDdqyLnsn9p41',
  power_automate_webhook_url: 'https://default6e8992ec76d54ea58eaeb0c5e55874.9a.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/1c9b143d398747a6892388f31a230f87/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=tzPM2LVcleQ3UCpAWZG46rQ7-3W5qtXOgrTjAHHYIcw'
};

function getConfig() {
  if (fs.existsSync(CONFIG_PATH)) {
    try {
      const data = fs.readFileSync(CONFIG_PATH, 'utf8');
      return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
    } catch (e) {
      return DEFAULT_CONFIG;
    }
  }
  return DEFAULT_CONFIG;
}

function saveConfig(newConfig) {
  const currentConfig = getConfig();
  const updatedConfig = { ...currentConfig, ...newConfig };
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(updatedConfig, null, 2));
  return updatedConfig;
}

module.exports = {
  getConfig,
  saveConfig,
  CONFIG_PATH
};
