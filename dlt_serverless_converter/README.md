# DLT Serverless Converter

A command-line utility for converting Databricks Delta Live Tables (DLT) pipelines from cluster compute to serverless compute with budget policies.

## Features

- **Convert DLT pipelines**: Migrate from classic compute to serverless compute
- **Automatic budget policy creation**: Generate budget policies for each pipeline reflecting existing tags
- **Safe operations**: automatically backup pipeline configurations before making changes
- **Rollback capability**: restore pipelines to previous configurations if needed
- **Pipeline discover**: list pipelines in the Databricks workspace

## How It Works

1. **Pipeline Discovery**: The tool connects to your Databricks workspace and retrieves all pipeline configurations
2. **Backup**: Before making any changes, pipeline definitions are saved to a backup file
3. **Budget Policy**: For each pipeline you can define if you want to associate it to an existing budget policy, create one for each pipeline or leave the pipeline without.
4. **Pipeline Update**: Pipelines are upgraded to use serverless compute
5. **Verification**: Results are logged showing successful and failed conversions

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

# Install the package
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
dlt-serverless-converter convert [--backup-file FILE_PATH] [--budget-policy-id POLICY_ID] [--skip-budget-policy]
```
Parameters:
- --backup-file FILE_PATH - Specify a custom path to save the pipeline backup file (default: auto-generated)
- --budget-policy-id POLICY_ID - Use an existing budget policy ID for all selected pipelines
- --skip-budget-policy - Skip creating or assigning budget policies to the pipelines

When converting Databricks DLT pipelines to serverless compute, the tool offers several alternatives for associating budget policies:

#### Option 1: Automatically Generate Budget Policies
The utility asks if you want to create individual budget policies for each pipeline based on their existing tags and configurations:
- Creates one budget policy per pipeline
- Customizes each policy based on pipeline's tags
- Requires Budget Admin permissions


#### Option 2: Single Shared Budget Policy
Associate all selected pipelines with a single existing budget policy:

```bash
dlt-serverless-converter convert --budget-policy-id POLICY_ID
```
Alternatively, the tool will interactively prompt you to enter a budget policy ID during execution if you don't specify one via command line.

#### Option 3: Skip Budget Policies Entirely
Convert pipelines to serverless compute without any budget policy association.

```bash
dlt-serverless-converter convert --skip-budget-policy
```

### Rollback Changes from a backup file
```bash
dlt-serverless-converter rollback --backup-file FILE_PATH
```