# DLT Serverless Converter

A command-line utility for converting Databricks Delta Live Tables (DLT) pipelines from cluster compute to serverless compute with budget policies.

## Features

- **Convert DLT pipelines**: Migrate from classic compute to serverless compute
- **Automatic budget policy creation**: Generate budget policies for each pipeline reflecting existing tags
- **Safe operations**: automatically backup pipeline configurations before making changes
- **Rollback capability**: restore pipelines to previous configurations if needed
- **Pipeline discover**: list pipelines in the Databricks workspace

## Prerequisites

- Python 3.8 or higher
- Access to the target Databricks workspaces
- Service principal with the following permissions:
  - Billing Admin, to allow the creation and management of new budget policies
  - Workspace Admin or CAN MANAGE / IS OWNER permissions on the Delta Live Tables pipelines you want to convert

## Installation

```bash
# Clone the repository
git clone ###
cd dlt_serverless_converter

# Install the package in development mode
pip install .
```

## Authentication

The tool supports authentication via environment variables or parameters:

- DATABRICKS_WORKSPACE_HOST, the URL of the workspace where DLT pipelines live
- DATABRICKS_CLIENT_ID, the identifier of the designated Service Principal
- DATABRICKS_CLIENT_SECRET, the secret of the designated Service Principal
- DATABRICKS_ACCOUNT_HOST, the URL to reach the Databricks Account Console (Azure, AWS, GCP)
- DATABRICKS_ACCOUNT_ID, the ID of your Databricks account. You can retrieve it directly from the Account portal.



## Usage

Add the ```--dry-run``` flag to execute the processes in log-only mode.

### List Pipelines

```bash
dlt-serverless-converter list
```

### Convert Pipelines to Serverless

```bash
dlt-serverless-converter convert
```

### Rollback Changes

```bash
dlt-serverless-converter rollback --backup-file <file_location>
```

## How It Works

1. **Pipeline Discovery**: The tool connects to your Databricks workspace and retrieves all pipeline configurations
2. **Backup**: Before making any changes, pipeline definitions are saved to a backup file
3. **Budget Policy Creation**: For each pipeline, a matching budget policy is created
4. **Pipeline Update**: Pipelines are updated to use serverless compute and linked to their budget policies
5. **Verification**: Results are logged showing successful and failed conversions