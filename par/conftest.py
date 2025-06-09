"""Shared test configuration and fixtures for Par tests."""

import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_git_repo(temp_dir):
    """Create a temporary git repository for testing."""
    repo_dir = temp_dir / "test-repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    (repo_dir / ".git").mkdir()
    (repo_dir / ".git" / "config").write_text("[core]\n    repositoryformatversion = 0\n")
    
    yield repo_dir


@pytest.fixture
def temp_workspace_dir(temp_dir):
    """Create temporary workspace with multiple git repos."""
    workspace_dir = temp_dir / "workspace"
    workspace_dir.mkdir()
    
    # Create multiple git repos
    for repo_name in ["frontend", "backend", "docs"]:
        repo_dir = workspace_dir / repo_name
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        (repo_dir / ".git" / "config").write_text("[core]\n    repositoryformatversion = 0\n")
    
    yield workspace_dir


@pytest.fixture
def isolated_par_data(temp_dir):
    """Isolated Par data directory for testing."""
    par_data_dir = temp_dir / "par"
    par_data_dir.mkdir()
    
    with patch('par.utils.get_data_dir', return_value=par_data_dir):
        yield par_data_dir


@pytest.fixture
def sample_par_config(temp_dir):
    """Sample .par.yaml configuration for testing."""
    config_file = temp_dir / ".par.yaml"
    config_content = {
        "initialization": {
            "commands": [
                {"name": "Install dependencies", "command": "npm install"},
                {"name": "Setup environment", "command": "cp .env.example .env", "condition": "file_exists:.env.example"},
                "echo 'Initialization complete'"
            ]
        }
    }
    
    import yaml
    config_file.write_text(yaml.dump(config_content))
    yield config_file


@pytest.fixture
def mock_tmux():
    """Mock tmux operations for testing."""
    with patch('par.operations._check_tmux') as mock_check, \
         patch('par.operations.tmux_session_exists') as mock_exists, \
         patch('par.operations.create_tmux_session') as mock_create, \
         patch('par.operations.kill_tmux_session') as mock_kill, \
         patch('par.operations.send_tmux_keys') as mock_send, \
         patch('par.operations.open_tmux_session') as mock_open:
        
        # Default behavior: tmux is available and sessions don't exist initially
        mock_check.return_value = None
        mock_exists.return_value = False
        
        yield {
            'check': mock_check,
            'exists': mock_exists,
            'create': mock_create,
            'kill': mock_kill,
            'send': mock_send,
            'open': mock_open
        }


@pytest.fixture
def mock_git():
    """Mock git operations for testing."""
    with patch('par.operations.create_worktree') as mock_create_wt, \
         patch('par.operations.remove_worktree') as mock_remove_wt, \
         patch('par.operations.delete_branch') as mock_delete_branch, \
         patch('par.operations.checkout_worktree') as mock_checkout_wt, \
         patch('par.utils.get_git_repo_root') as mock_repo_root:
        
        # Default behavior
        mock_repo_root.return_value = Path("/tmp/test-repo")
        
        yield {
            'create_worktree': mock_create_wt,
            'remove_worktree': mock_remove_wt,
            'delete_branch': mock_delete_branch,
            'checkout_worktree': mock_checkout_wt,
            'repo_root': mock_repo_root
        }


@pytest.fixture
def sample_session_state():
    """Sample session state data for testing."""
    return {
        "/tmp/test-repo": {
            "session1": {
                "worktree_path": "/tmp/par/worktrees/abc123/session1",
                "tmux_session_name": "par-test-repo-abc1-session1",
                "branch_name": "session1",
                "created_at": "2025-01-01T00:00:00",
                "checkout_type": "new"
            },
            "session2": {
                "worktree_path": "/tmp/par/worktrees/abc123/session2", 
                "tmux_session_name": "par-test-repo-abc1-session2",
                "branch_name": "session2",
                "created_at": "2025-01-01T01:00:00",
                "checkout_type": "checkout"
            }
        }
    }


@pytest.fixture 
def sample_workspace_state():
    """Sample workspace state data for testing."""
    return {
        "/tmp/workspace": {
            "feature-auth": {
                "session_name": "par-ws-workspace-abc1-feature-auth",
                "repos": [
                    {
                        "repo_name": "frontend",
                        "repo_path": "/tmp/workspace/frontend",
                        "worktree_path": "/tmp/par/workspaces/def456/feature-auth/frontend/feature-auth",
                        "branch_name": "feature-auth"
                    },
                    {
                        "repo_name": "backend", 
                        "repo_path": "/tmp/workspace/backend",
                        "worktree_path": "/tmp/par/workspaces/def456/feature-auth/backend/feature-auth",
                        "branch_name": "feature-auth"
                    }
                ],
                "created_at": "2025-01-01T00:00:00",
                "workspace_root": "/tmp/workspace"
            }
        }
    }


@pytest.fixture
def mock_state_files(isolated_par_data, sample_session_state, sample_workspace_state):
    """Create mock state files with sample data."""
    session_file = isolated_par_data / "state.json"
    workspace_file = isolated_par_data / "workspaces.json"
    
    session_file.write_text(json.dumps(sample_session_state, indent=2))
    workspace_file.write_text(json.dumps(sample_workspace_state, indent=2))
    
    yield {
        'session_file': session_file,
        'workspace_file': workspace_file,
        'session_data': sample_session_state,
        'workspace_data': sample_workspace_state
    }


@pytest.fixture
def mock_console():
    """Mock rich console for testing output."""
    with patch('par.core.Console') as mock_console_class, \
         patch('par.workspace.Console') as mock_workspace_console:
        
        mock_instance = Mock()
        mock_console_class.return_value = mock_instance
        mock_workspace_console.return_value = mock_instance
        
        yield mock_instance


@pytest.fixture(autouse=True)
def suppress_typer_output():
    """Suppress typer output during tests."""
    with patch('typer.secho'), \
         patch('typer.echo'), \
         patch('typer.confirm', return_value=True):
        yield


# Test markers for categorizing tests
pytest_plugins = []


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test") 
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on file patterns."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark performance tests
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # Mark unit tests (default for most tests)
        if not any(marker.name in ["integration", "performance"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)