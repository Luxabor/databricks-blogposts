#!/usr/bin/env python3
"""
DLT Serverless Converter - Utility to convert DLT pipelines to serverless compute 
and roll back to previous configurations.
"""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional
from databricks.sdk import AccountClient, WorkspaceClient
from dlt_serverless_converter.utils.budget_policies import generate_budget_policies_from_workspace_pipelines
from dlt_serverless_converter.utils.pipelines import WorkspacePipeline, convert_pipelines_to_serverless, get_workspace_pipelines, load_pipelines_from_file, rollback_pipelines, save_pipelines_to_file
from dlt_serverless_converter.utils.auth import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_common_args(parser):
    """Add common arguments to a parser."""
    parser.add_argument('--dry-run', action='store_true', 
                    help='Preview changes without executing them')
    parser.add_argument('--account-host', default=os.environ.get('DATABRICKS_ACCOUNT_HOST'), 
                    help='Databricks account host URL')
    parser.add_argument('--account-id', default=os.environ.get('DATABRICKS_ACCOUNT_ID'),
                    help='Databricks account ID')
    parser.add_argument('--client-id', default=os.environ.get('DATABRICKS_CLIENT_ID'),
                    help='Databricks client ID')
    parser.add_argument('--client-secret', default=os.environ.get('DATABRICKS_CLIENT_SECRET'),
                    help='Databricks client secret')
    parser.add_argument('--workspace-host', default=os.environ.get('DATABRICKS_WORKSPACE_HOST'),
                    help='Databricks workspace host URL')
    
def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Databricks DLT pipeline serverless converter'
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', 
                                         help='Convert pipelines to serverless compute')
    convert_parser.add_argument('--backup-file', default=None,
                              help='Path to save pipeline backup file (default: auto-generated)')
    #convert_parser.add_argument('--interactive', '-i', action='store_true', help='Interactively select pipelines to convert')
    add_common_args(convert_parser)
    
    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', 
                                          help='Rollback pipelines to a previous state')
    rollback_parser.add_argument('--backup-file', required=True,
                               help='Path to the pipeline backup file to restore from')
    #rollback_parser.add_argument('--interactive', '-i', action='store_true', help='Interactively select pipelines to roll back')
    add_common_args(rollback_parser)
    
    # List command (optional utility to just list pipelines)
    list_parser = subparsers.add_parser('list',
                                      help='List available pipelines without making changes')
    list_parser.add_argument('--output-file', default=None,
                           help='Save pipeline list to a file')
    add_common_args(list_parser)
    
    args = parser.parse_args()
    
    # Validate required command
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    return args


def _get_selected_pipelines(workspace_pipelines: List[WorkspacePipeline]) -> List[WorkspacePipeline]:
    """
    Interactively prompt user to select pipelines for conversion.
    
    Args:
        workspace_pipelines: List of all available pipelines
        
    Returns:
        List of selected pipelines
    """
    if not workspace_pipelines:
        logger.warning("No pipelines found to select from")
        return []
    
    # Display all pipelines with indices
    logger.info("\nAvailable pipelines:")
    # Sort pipelines by name
    workspace_pipelines.sort(key=lambda pipeline: pipeline.pipeline_definition.spec.name)
    
    for idx, pipeline in enumerate(workspace_pipelines, 1):
        p = pipeline.pipeline_definition
        serverless = getattr(p.spec, 'serverless', False)
        serverless_status = "✓ (already serverless)" if serverless else "✗ (cluster compute)"
        tags = p.spec.clusters[0].custom_tags if p.spec.clusters and p.spec.clusters[0].custom_tags else {}
        
        logger.info(f"{idx}. [{serverless_status}] {p.spec.name} (ID: {pipeline.pipeline_id})")
        if tags:
            logger.info(f"   Tags: {tags}")
    
    # Prompt for selection
    logger.info("\nEnter pipeline numbers to convert (e.g., 1,3,5-7) or 'all' for all pipelines:")
    selection = input("> ").strip().lower()
    
    if selection == 'all':
        return workspace_pipelines
    
    selected_indices = []
    selected_pipelines = []
    
    # Parse the selection string (e.g., "1,3,5-7")
    for part in selection.split(','):
        part = part.strip()
        if not part:
            continue
            
        # Handle ranges (e.g., "5-7")
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start < 1 or end > len(workspace_pipelines):
                    logger.warning(f"Range {start}-{end} is out of bounds, skipping")
                    continue
                selected_indices.extend(range(start, end + 1))
            except ValueError:
                logger.warning(f"Invalid range format '{part}', skipping")
                
        # Handle single numbers
        else:
            try:
                idx = int(part)
                if 1 <= idx <= len(workspace_pipelines):
                    selected_indices.append(idx)
                else:
                    logger.warning(f"Index {idx} is out of bounds, skipping")
            except ValueError:
                logger.warning(f"Invalid number '{part}', skipping")
    
    # Remove duplicates and sort
    selected_indices = sorted(set(selected_indices))
    
    # Get the selected pipelines
    for idx in selected_indices:
        selected_pipelines.append(workspace_pipelines[idx - 1])  # Adjust for 0-based indexing
    
    logger.info(f"Selected {len(selected_pipelines)} of {len(workspace_pipelines)} pipelines for conversion")
    return selected_pipelines


def command_convert(args, workspace_client, account_client):
    """Execute the convert command."""
    # Get pipelines from workspace
    logger.info("Retrieving pipelines from workspace...")
    workspace_pipelines = get_workspace_pipelines(workspace_client)
    logger.info(f"Found {len(workspace_pipelines)} pipelines in workspace")
    
    # Prompt for pipeline selection
    workspace_pipelines = _get_selected_pipelines(workspace_pipelines)
    if not workspace_pipelines:
        logger.info("No pipelines selected. Exiting.")
        return
    
    # Save backup before making changes
    backup_file = args.backup_file
    saved_file = save_pipelines_to_file(workspace_pipelines, backup_file)
    logger.info(f"Pipeline backup saved to {saved_file}")
    
    # Generate budget policies if not in dry run mode
    budget_policies = {}
    if not args.dry_run:
        logger.info("Generating budget policies...")
        budget_policies = generate_budget_policies_from_workspace_pipelines(account_client, workspace_client, workspace_pipelines)
        logger.info(f"Generated {len([p for p in budget_policies.values() if p is not None])} budget policies")
    else:
        logger.info("DRY RUN: Would generate budget policies for selected pipelines")
    
    # Execute pipeline conversion
    convert_pipelines_to_serverless(workspace_client, workspace_pipelines, budget_policies, args.dry_run)

def command_rollback(args, workspace_client, _):
    """Execute the rollback command."""
    backup_file = args.backup_file
    logger.info(f"Starting rollback from backup file: {backup_file}")
    
    # Load backed up pipelines
    backed_up_pipelines = load_pipelines_from_file(backup_file)
    logger.info(f"Loaded {len(backed_up_pipelines)} pipeline configurations from backup")

    # Prompt for pipeline selection
    backed_up_pipelines = _get_selected_pipelines(backed_up_pipelines)
    if not backed_up_pipelines:
        logger.info("No pipelines selected for rollback. Exiting.")
        return
    
    logger.info(f"Will roll back {len(backed_up_pipelines)} selected pipelines")
    
    # Execute rollback
    rollback_pipelines(workspace_client, backed_up_pipelines, args.dry_run)

def command_list(args, workspace_client, _):
    """Execute the list command to display pipelines without making changes."""
    logger.info("Listing pipelines in workspace...")
    workspace_pipelines = get_workspace_pipelines(workspace_client)
    
        # Display pipeline information
    logger.info(f"Found {len(workspace_pipelines)} pipelines:")
    for idx, pipeline in enumerate(workspace_pipelines, 1):
        p = pipeline.pipeline_definition
        logger.info(f"{idx}. ID: {pipeline.pipeline_id}, Name: {p.spec.name}")
        if p.spec.clusters and p.spec.clusters[0].custom_tags:
            logger.info(f"   Tags: {p.spec.clusters[0].custom_tags}")
        logger.info(f"   Serverless: {getattr(p.spec, 'serverless', False)}")
    
    # Save list to file if requested
    if args.output_file:
        save_pipelines_to_file(workspace_pipelines, args.output_file)
        logger.info(f"Pipeline list saved to {args.output_file}")
    
    return workspace_pipelines

