#!/usr/bin/env python3
"""
MLC Bakery CLI - Command line interface for MLC Bakery operations
"""
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any

# Add the project root to the path so we can import mlcbakery
sys.path.insert(0, str(Path(__file__).parent.parent))

from mlcbakery.bakery_client import Client, BakeryTask


def create_task_command(args):
    """Create a new task in the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    # Load workflow from file if provided
    workflow = {}
    if args.workflow_file:
        try:
            with open(args.workflow_file, 'r') as f:
                workflow = json.load(f)
        except Exception as e:
            print(f"Error loading workflow file: {e}")
            sys.exit(1)
    elif args.workflow_json:
        try:
            workflow = json.loads(args.workflow_json)
        except Exception as e:
            print(f"Error parsing workflow JSON: {e}")
            sys.exit(1)
    else:
        print("Error: Either --workflow-file or --workflow-json must be provided")
        sys.exit(1)
    
    params = {}
    if args.version:
        params['version'] = args.version
    if args.description:
        params['description'] = args.description
    if args.asset_origin:
        params['asset_origin'] = args.asset_origin
    
    try:
        task = client.create_task(
            collection_name=args.collection,
            task_name=args.name,
            workflow=workflow,
            params=params
        )
        print(f"Task created successfully:")
        print(f"  ID: {task.id}")
        print(f"  Name: {task.name}")
        print(f"  Collection: {args.collection}")
        print(f"  Version: {task.version}")
        if task.description:
            print(f"  Description: {task.description}")
    except Exception as e:
        print(f"Error creating task: {e}")
        sys.exit(1)


def get_task_command(args):
    """Get a task from the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    try:
        task = client.get_task_by_name(
            collection_name=args.collection,
            task_name=args.name
        )
        
        if task is None:
            print(f"Task '{args.collection}/{args.name}' not found")
            sys.exit(1)
        
        print(f"Task Details:")
        print(f"  ID: {task.id}")
        print(f"  Name: {task.name}")
        print(f"  Collection: {task.collection_name or args.collection}")
        print(f"  Version: {task.version}")
        print(f"  Description: {task.description}")
        print(f"  Asset Origin: {task.asset_origin}")
        print(f"  Created At: {task.created_at}")
        print(f"  Workflow:")
        print(json.dumps(task.workflow, indent=2))
        
    except Exception as e:
        print(f"Error getting task: {e}")
        sys.exit(1)


def update_task_command(args):
    """Update an existing task in the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    # First, get the task to find its ID
    try:
        existing_task = client.get_task_by_name(
            collection_name=args.collection,
            task_name=args.name
        )
        
        if existing_task is None:
            print(f"Task '{args.collection}/{args.name}' not found")
            sys.exit(1)
        
    except Exception as e:
        print(f"Error finding task: {e}")
        sys.exit(1)
    
    # Prepare update parameters
    params = {}
    
    if args.workflow_file:
        try:
            with open(args.workflow_file, 'r') as f:
                params['workflow'] = json.load(f)
        except Exception as e:
            print(f"Error loading workflow file: {e}")
            sys.exit(1)
    elif args.workflow_json:
        try:
            params['workflow'] = json.loads(args.workflow_json)
        except Exception as e:
            print(f"Error parsing workflow JSON: {e}")
            sys.exit(1)
    
    if args.version:
        params['version'] = args.version
    if args.description:
        params['description'] = args.description
    if args.asset_origin:
        params['asset_origin'] = args.asset_origin
    
    if not params:
        print("Error: No update parameters provided")
        sys.exit(1)
    
    try:
        updated_task = client.update_task(existing_task.id, params)
        print(f"Task updated successfully:")
        print(f"  ID: {updated_task.id}")
        print(f"  Name: {updated_task.name}")
        print(f"  Collection: {args.collection}")
        print(f"  Version: {updated_task.version}")
        if updated_task.description:
            print(f"  Description: {updated_task.description}")
    except Exception as e:
        print(f"Error updating task: {e}")
        sys.exit(1)


def list_tasks_command(args):
    """List all tasks in the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    try:
        tasks = client.list_tasks(skip=args.skip, limit=args.limit)
        
        if not tasks:
            print("No tasks found")
            return
        
        print(f"Found {len(tasks)} task(s):")
        print("-" * 80)
        
        for task in tasks:
            print(f"ID: {task.id}")
            print(f"Name: {task.name}")
            print(f"Collection: {task.collection_name}")
            print(f"Version: {task.version}")
            print(f"Description: {task.description}")
            print(f"Created: {task.created_at}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error listing tasks: {e}")
        sys.exit(1)


def search_tasks_command(args):
    """Search for tasks in the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    try:
        results = client.search_tasks(query=args.query, limit=args.limit)
        
        if not results:
            print(f"No tasks found matching query: '{args.query}'")
            return
        
        print(f"Search results for '{args.query}':")
        print(json.dumps(results, indent=2))
            
    except Exception as e:
        print(f"Error searching tasks: {e}")
        sys.exit(1)


def push_task_command(args):
    """Push a task to the bakery (create or update)."""
    client = Client(bakery_url=args.url, token=args.token)
    
    # Load workflow from file if provided
    workflow = {}
    if args.workflow_file:
        try:
            with open(args.workflow_file, 'r') as f:
                workflow = json.load(f)
        except Exception as e:
            print(f"Error loading workflow file: {e}")
            sys.exit(1)
    elif args.workflow_json:
        try:
            workflow = json.loads(args.workflow_json)
        except Exception as e:
            print(f"Error parsing workflow JSON: {e}")
            sys.exit(1)
    else:
        print("Error: Either --workflow-file or --workflow-json must be provided")
        sys.exit(1)
    
    task_identifier = f"{args.collection}/{args.name}"
    
    try:
        task = client.push_task(
            task_identifier=task_identifier,
            workflow=workflow,
            version=args.version,
            description=args.description,
            asset_origin=args.asset_origin
        )
        print(f"Task pushed successfully:")
        print(f"  ID: {task.id}")
        print(f"  Name: {task.name}")
        print(f"  Collection: {args.collection}")
        print(f"  Version: {task.version}")
        if task.description:
            print(f"  Description: {task.description}")
    except Exception as e:
        print(f"Error pushing task: {e}")
        sys.exit(1)


def delete_task_command(args):
    """Delete a task from the bakery."""
    client = Client(bakery_url=args.url, token=args.token)
    
    # First, get the task to find its ID
    try:
        existing_task = client.get_task_by_name(
            collection_name=args.collection,
            task_name=args.name
        )
        
        if existing_task is None:
            print(f"Task '{args.collection}/{args.name}' not found")
            sys.exit(1)
        
    except Exception as e:
        print(f"Error finding task: {e}")
        sys.exit(1)
    
    # Confirm deletion if not forced
    if not args.force:
        response = input(f"Are you sure you want to delete task '{args.collection}/{args.name}'? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Deletion cancelled")
            return
    
    try:
        client.delete_task(existing_task.id)
        print(f"Task '{args.collection}/{args.name}' deleted successfully")
    except Exception as e:
        print(f"Error deleting task: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MLC Bakery CLI - Command line interface for task operations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global arguments
    parser.add_argument(
        "--url",
        default=os.getenv("BAKERY_URL", "http://localhost:8000"),
        help="Bakery API URL (default: http://localhost:8000 or BAKERY_URL env var)"
    )
    parser.add_argument(
        "--token",
        default=os.getenv("BAKERY_TOKEN"),
        help="Authentication token (default: BAKERY_TOKEN env var)"
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create task command
    create_parser = subparsers.add_parser("create", help="Create a new task")
    create_parser.add_argument("--collection", required=True, help="Collection name")
    create_parser.add_argument("--name", required=True, help="Task name")
    create_parser.add_argument("--workflow-file", help="Path to JSON file containing workflow definition")
    create_parser.add_argument("--workflow-json", help="Workflow definition as JSON string")
    create_parser.add_argument("--version", help="Task version")
    create_parser.add_argument("--description", help="Task description")
    create_parser.add_argument("--asset-origin", help="Asset origin")
    create_parser.set_defaults(func=create_task_command)
    
    # Get task command
    get_parser = subparsers.add_parser("get", help="Get a task")
    get_parser.add_argument("--collection", required=True, help="Collection name")
    get_parser.add_argument("--name", required=True, help="Task name")
    get_parser.set_defaults(func=get_task_command)
    
    # Update task command
    update_parser = subparsers.add_parser("update", help="Update an existing task")
    update_parser.add_argument("--collection", required=True, help="Collection name")
    update_parser.add_argument("--name", required=True, help="Task name")
    update_parser.add_argument("--workflow-file", help="Path to JSON file containing workflow definition")
    update_parser.add_argument("--workflow-json", help="Workflow definition as JSON string")
    update_parser.add_argument("--version", help="Task version")
    update_parser.add_argument("--description", help="Task description")
    update_parser.add_argument("--asset-origin", help="Asset origin")
    update_parser.set_defaults(func=update_task_command)
    
    # List tasks command
    list_parser = subparsers.add_parser("list", help="List all tasks")
    list_parser.add_argument("--skip", type=int, default=0, help="Number of tasks to skip")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number of tasks to return")
    list_parser.set_defaults(func=list_tasks_command)
    
    # Search tasks command
    search_parser = subparsers.add_parser("search", help="Search for tasks")
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument("--limit", type=int, default=30, help="Maximum number of results")
    search_parser.set_defaults(func=search_tasks_command)
    
    # Push task command
    push_parser = subparsers.add_parser("push", help="Push a task (create or update)")
    push_parser.add_argument("--collection", required=True, help="Collection name")
    push_parser.add_argument("--name", required=True, help="Task name")
    push_parser.add_argument("--workflow-file", help="Path to JSON file containing workflow definition")
    push_parser.add_argument("--workflow-json", help="Workflow definition as JSON string")
    push_parser.add_argument("--version", help="Task version")
    push_parser.add_argument("--description", help="Task description")
    push_parser.add_argument("--asset-origin", help="Asset origin")
    push_parser.set_defaults(func=push_task_command)
    
    # Delete task command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("--collection", required=True, help="Collection name")
    delete_parser.add_argument("--name", required=True, help="Task name")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    delete_parser.set_defaults(func=delete_task_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main() 