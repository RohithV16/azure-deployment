# M&G AEM Azure Deployment CLI (`mandg`)

A terminal-only pure JavaScript CLI for managing M&G Azure DevOps deployments via REST API.

## Installation

1. Ensure you have Node.js (v14+) installed.
2. Install package dependencies:
   ```bash
   npm install
   ```
3. Link the command globally:
   ```bash
   npm link
   ```

## Configuration

Update your Azure DevOps Personal Access Token (PAT) and project settings. These are stored locally in your user profile (`~/.azure-deploy-aem.json`).

```bash
# Update PAT
mandg update --token <your_pat_secret>

# Update Org/Project
mandg update --org https://dev.azure.com/your-org --project your-project
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `mandg dev` | Triggers the DEV pipeline deployment. |
| `mandg stage` | Triggers the STAGE pipeline deployment. |
| `mandg status` | Checks the status of the latest build or a specific one. |
| `mandg update` | Update configuration or authentication (PAT). |

### Command Options

#### `status`
- `-d, --definition-id <id>`: Build Definition ID
- `-b, --build-id <id>`: Specific Build ID to check

#### `update`
- `--token <pat>`: Personal Access Token
- `--org <url>`: Organization URL (e.g., https://dev.azure.com/org)
- `--project <name>`: Project name

## Technical Details

This CLI uses the Azure DevOps REST API for all operations. It does not require the Azure CLI or Python to be installed. All authentication is handled via the Personal Access Token (PAT) you provide.
