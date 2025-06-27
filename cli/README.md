# MLC Bakery CLI

Command line interface for managing tasks in the MLC Bakery system.

## Installation

The CLI is available after installing the mlcbakery package:

```bash
pip install -e .
# or
poetry install
```

## Usage

The CLI provides several commands for managing tasks:

### Configuration

You can configure the bakery URL and authentication token in two ways:

1. **Environment variables:**
   ```bash
   export BAKERY_URL=http://localhost:8000
   export BAKERY_TOKEN=your_auth_token
   ```

2. **Command line arguments:**
   ```bash
   bakery-cli --url http://localhost:8000 --token your_auth_token [command]
   ```

### Commands

#### Create a Task

Create a new task in the bakery:

```bash
# Using a workflow file
bakery-cli create --collection my-collection --name my-task --workflow-file examples/sample_workflow.json --version 1.0 --description "My workflow task"

# Using inline JSON
bakery-cli create --collection my-collection --name my-task --workflow-json '{"steps": [{"name": "step1", "type": "transform"}]}' --version 1.0
```

#### Get a Task

Retrieve details of an existing task:

```bash
bakery-cli get --collection my-collection --name my-task
```

#### Update a Task

Update an existing task:

```bash
# Update workflow from file
bakery-cli update --collection my-collection --name my-task --workflow-file new_workflow.json --version 1.1

# Update description only
bakery-cli update --collection my-collection --name my-task --description "Updated description"
```

#### List Tasks

List all tasks in the bakery:

```bash
# List all tasks
bakery-cli list

# List with pagination
bakery-cli list --skip 10 --limit 20
```

#### Search Tasks

Search for tasks by query:

```bash
bakery-cli search --query "data processing" --limit 10
```

#### Push a Task

Push a task (create or update if exists):

```bash
bakery-cli push --collection my-collection --name my-task --workflow-file examples/sample_workflow.json --version 1.0 --description "Pushed task"
```

#### Delete a Task

Delete a task:

```bash
# With confirmation prompt
bakery-cli delete --collection my-collection --name my-task

# Force delete without confirmation
bakery-cli delete --collection my-collection --name my-task --force
```

## Workflow Format

Tasks require a workflow definition in JSON format. The workflow can contain any valid JSON structure that defines your task execution logic. Here's an example:

```json
{
  "name": "Data Processing Pipeline",
  "description": "A sample data processing workflow",
  "steps": [
    {
      "name": "data_ingestion",
      "type": "extract",
      "source": "s3://my-bucket/raw-data/",
      "parameters": {
        "format": "csv",
        "encoding": "utf-8"
      }
    },
    {
      "name": "data_cleaning",
      "type": "transform",
      "depends_on": ["data_ingestion"],
      "script": "clean_data.py"
    }
  ],
  "schedule": {
    "cron": "0 2 * * *",
    "timezone": "UTC"
  }
}
```

## Examples

### Creating a Simple Task

1. Create a workflow file:
   ```json
   {
     "steps": [
       {
         "name": "hello_world",
         "type": "script",
         "command": "echo 'Hello, World!'"
       }
     ]
   }
   ```

2. Create the task:
   ```bash
   bakery-cli create --collection examples --name hello-world --workflow-file hello_workflow.json --description "A simple hello world task"
   ```

### Updating an Existing Task

```bash
# Get current task details
bakery-cli get --collection examples --name hello-world

# Update with new version
bakery-cli update --collection examples --name hello-world --version 1.1 --description "Updated hello world task"
```

### Working with Complex Workflows

For complex workflows, it's recommended to use separate JSON files:

```bash
bakery-cli push --collection data-processing --name etl-pipeline --workflow-file workflows/complex_etl.json --version 2.0 --description "Complex ETL pipeline for data processing"
```

## Error Handling

The CLI provides detailed error messages for common issues:

- Missing workflow definition
- Invalid JSON format
- Task not found
- Authentication errors
- Network connectivity issues

## Development

To run the CLI in development mode:

```bash
python cli/bakery_cli.py --help
```

Or use the installed entry point:

```bash
bakery-cli --help
``` 