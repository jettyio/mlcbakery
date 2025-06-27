"""
Test file for task-related functionality in the bakery client.
"""
import json
import pytest
from unittest.mock import Mock, patch
from mlcbakery.bakery_client import Client, BakeryTask


class TestTaskClient:
    """Test cases for task-related client methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = Client(bakery_url="http://test.example.com", token="test_token")
        self.sample_workflow = {
            "steps": [
                {
                    "name": "test_step",
                    "type": "transform",
                    "command": "echo 'test'"
                }
            ]
        }
        
    @patch('mlcbakery.bakery_client.requests.request')
    def test_create_task(self, mock_request):
        """Test creating a new task."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "1",
            "name": "test-task",
            "collection_id": "1",
            "workflow": self.sample_workflow,
            "version": "1.0",
            "description": "Test task",
            "entity_type": "task",
            "created_at": "2024-01-01T00:00:00Z"
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        task = self.client.create_task(
            collection_name="test-collection",
            task_name="test-task",
            workflow=self.sample_workflow,
            params={"version": "1.0", "description": "Test task"}
        )
        
        # Assertions
        assert isinstance(task, BakeryTask)
        assert task.id == "1"
        assert task.name == "test-task"
        assert task.workflow == self.sample_workflow
        assert task.version == "1.0"
        assert task.description == "Test task"
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert "/tasks" in args[1]
        assert kwargs["json"]["name"] == "test-task"
        assert kwargs["json"]["collection_name"] == "test-collection"
        assert kwargs["json"]["workflow"] == self.sample_workflow

    @patch('mlcbakery.bakery_client.requests.request')
    def test_get_task_by_name(self, mock_request):
        """Test getting a task by name."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "1",
            "name": "test-task",
            "collection_id": "1",
            "workflow": self.sample_workflow,
            "version": "1.0",
            "description": "Test task",
            "entity_type": "task",
            "created_at": "2024-01-01T00:00:00Z"
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        task = self.client.get_task_by_name("test-collection", "test-task")
        
        # Assertions
        assert isinstance(task, BakeryTask)
        assert task.id == "1"
        assert task.name == "test-task"
        assert task.workflow == self.sample_workflow
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert "/tasks/test-collection/test-task" in args[1]

    @patch('mlcbakery.bakery_client.requests.request')
    def test_get_task_by_name_not_found(self, mock_request):
        """Test getting a task that doesn't exist."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_request.return_value = mock_response
        
        # Call method
        task = self.client.get_task_by_name("test-collection", "nonexistent-task")
        
        # Should return None for 404
        assert task is None

    @patch('mlcbakery.bakery_client.requests.request')
    def test_update_task(self, mock_request):
        """Test updating an existing task."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "1",
            "name": "test-task",
            "collection_id": "1",
            "workflow": self.sample_workflow,
            "version": "1.1",
            "description": "Updated test task",
            "entity_type": "task",
            "created_at": "2024-01-01T00:00:00Z"
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        params = {"version": "1.1", "description": "Updated test task"}
        task = self.client.update_task("1", params)
        
        # Assertions
        assert isinstance(task, BakeryTask)
        assert task.id == "1"
        assert task.version == "1.1"
        assert task.description == "Updated test task"
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "PUT"
        assert "/tasks/1" in args[1]
        assert kwargs["json"] == params

    @patch('mlcbakery.bakery_client.requests.request')
    def test_list_tasks(self, mock_request):
        """Test listing tasks."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "1",
                "name": "task-1",
                "collection_id": "1",
                "collection_name": "test-collection",
                "workflow": self.sample_workflow,
                "version": "1.0",
                "entity_type": "task",
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "2",
                "name": "task-2",
                "collection_id": "1",
                "collection_name": "test-collection",
                "workflow": self.sample_workflow,
                "version": "1.0",
                "entity_type": "task",
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        tasks = self.client.list_tasks(skip=0, limit=10)
        
        # Assertions
        assert len(tasks) == 2
        assert all(isinstance(task, BakeryTask) for task in tasks)
        assert tasks[0].name == "task-1"
        assert tasks[1].name == "task-2"
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert "/tasks/" in args[1]
        assert kwargs["params"]["skip"] == 0
        assert kwargs["params"]["limit"] == 10

    @patch('mlcbakery.bakery_client.requests.request')
    def test_search_tasks(self, mock_request):
        """Test searching tasks."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "hits": [
                {
                    "document": {
                        "id": "1",
                        "entity_name": "task-1",
                        "collection_name": "test-collection"
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method
        results = self.client.search_tasks("test query", limit=10)
        
        # Assertions
        assert "hits" in results
        assert len(results["hits"]) == 1
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert "/tasks/search" in args[1]
        assert kwargs["params"]["q"] == "test query"
        assert kwargs["params"]["limit"] == 10

    @patch('mlcbakery.bakery_client.requests.request')
    def test_delete_task(self, mock_request):
        """Test deleting a task."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Call method (should not raise exception)
        self.client.delete_task("1")
        
        # Verify request was made correctly
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "DELETE"
        assert "/tasks/1" in args[1]

    @patch.object(Client, 'find_or_create_by_collection_name')
    @patch.object(Client, 'get_task_by_name')
    @patch.object(Client, 'create_task')
    @patch.object(Client, 'update_task')
    def test_push_task_create_new(self, mock_update, mock_create, mock_get, mock_find_collection):
        """Test pushing a task that doesn't exist (creates new)."""
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.id = "1"
        mock_find_collection.return_value = mock_collection
        
        # Mock task doesn't exist
        mock_get.return_value = None
        
        # Mock create response
        mock_task = BakeryTask(
            id="1",
            name="new-task",
            collection_id="1",
            workflow=self.sample_workflow,
            version="1.0"
        )
        mock_create.return_value = mock_task
        mock_get.side_effect = [None, mock_task]  # First call returns None, second returns created task
        
        # Call method
        result = self.client.push_task(
            task_identifier="test-collection/new-task",
            workflow=self.sample_workflow,
            version="1.0",
            description="New task"
        )
        
        # Assertions
        assert result == mock_task
        mock_find_collection.assert_called_once_with("test-collection")
        mock_create.assert_called_once()
        mock_update.assert_not_called()

    @patch.object(Client, 'find_or_create_by_collection_name')
    @patch.object(Client, 'get_task_by_name')
    @patch.object(Client, 'update_task')
    def test_push_task_update_existing(self, mock_update, mock_get, mock_find_collection):
        """Test pushing a task that already exists (updates)."""
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.id = "1"
        mock_find_collection.return_value = mock_collection
        
        # Mock existing task
        existing_task = BakeryTask(
            id="1",
            name="existing-task",
            collection_id="1",
            workflow={"old": "workflow"},
            version="1.0"
        )
        
        # Mock updated task
        updated_task = BakeryTask(
            id="1",
            name="existing-task",
            collection_id="1",
            workflow=self.sample_workflow,
            version="1.1"
        )
        
        mock_get.side_effect = [existing_task, updated_task]  # First call returns existing, second returns updated
        mock_update.return_value = updated_task
        
        # Call method
        result = self.client.push_task(
            task_identifier="test-collection/existing-task",
            workflow=self.sample_workflow,
            version="1.1"
        )
        
        # Assertions
        assert result == updated_task
        mock_find_collection.assert_called_once_with("test-collection")
        mock_update.assert_called_once_with(existing_task.id, {"workflow": self.sample_workflow, "version": "1.1"}) 