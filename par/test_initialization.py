"""Tests for par initialization functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from . import initialization


def test_load_par_config_missing_file():
    """Test loading config when .par.yaml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        config = initialization.load_par_config(repo_root)
        assert config is None


def test_load_par_config_valid_yaml():
    """Test loading valid .par.yaml config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        config_file = repo_root / ".par.yaml"
        
        config_content = """
initialization:
  commands:
    - name: "Install deps"
      command: "npm install"
    - "echo hello"
"""
        config_file.write_text(config_content)
        
        config = initialization.load_par_config(repo_root)
        assert config is not None
        assert "initialization" in config
        assert len(config["initialization"]["commands"]) == 2


def test_load_par_config_invalid_yaml():
    """Test loading invalid YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        config_file = repo_root / ".par.yaml"
        
        # Invalid YAML (unclosed bracket)
        config_file.write_text("initialization:\n  commands: [")
        
        config = initialization.load_par_config(repo_root)
        assert config is None


@patch('par.initialization.operations.send_tmux_keys')
def test_run_initialization_string_commands(mock_send_keys):
    """Test running simple string commands."""
    config = {
        "initialization": {
            "commands": [
                "npm install",
                "echo hello"
            ]
        }
    }
    
    initialization.run_initialization(config, "test-session")
    
    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call("test-session", "npm install")
    mock_send_keys.assert_any_call("test-session", "echo hello")


@patch('par.initialization.operations.send_tmux_keys')
def test_run_initialization_structured_commands(mock_send_keys):
    """Test running structured commands with names."""
    config = {
        "initialization": {
            "commands": [
                {
                    "name": "Install dependencies",
                    "command": "npm install"
                },
                {
                    "name": "Start server",
                    "command": "npm start"
                }
            ]
        }
    }
    
    initialization.run_initialization(config, "test-session")
    
    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call("test-session", "npm install")
    mock_send_keys.assert_any_call("test-session", "npm start")


@patch('par.initialization.operations.send_tmux_keys')
def test_run_initialization_with_conditions(mock_send_keys):
    """Test running commands with conditions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test directory to satisfy condition
        test_dir = Path(tmpdir) / "frontend"
        test_dir.mkdir()
        
        with patch('par.initialization.Path') as mock_path:
            mock_path.return_value.is_dir.return_value = True
            
            config = {
                "initialization": {
                    "commands": [
                        {
                            "name": "Install frontend deps",
                            "command": "cd frontend && npm install",
                            "condition": "directory_exists:frontend"
                        },
                        {
                            "name": "Install backend deps", 
                            "command": "cd backend && pip install -r requirements.txt",
                            "condition": "directory_exists:backend"
                        }
                    ]
                }
            }
            
            # Mock only the second condition to fail
            def side_effect(path):
                mock_path_obj = Mock()
                mock_path_obj.is_dir.return_value = path == "frontend"
                return mock_path_obj
                
            mock_path.side_effect = side_effect
            
            initialization.run_initialization(config, "test-session")
            
            # Only first command should run due to condition
            assert mock_send_keys.call_count == 1
            mock_send_keys.assert_called_with("test-session", "cd frontend && npm install")


def test_check_condition_directory_exists():
    """Test directory_exists condition."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test"
        test_dir.mkdir()
        
        with patch('par.initialization.Path') as mock_path:
            mock_path.return_value.is_dir.return_value = True
            result = initialization._check_condition("directory_exists:test")
            assert result is True
            
            mock_path.return_value.is_dir.return_value = False
            result = initialization._check_condition("directory_exists:nonexistent")
            assert result is False


def test_check_condition_file_exists():
    """Test file_exists condition."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        
        with patch('par.initialization.Path') as mock_path:
            mock_path.return_value.is_file.return_value = True
            result = initialization._check_condition("file_exists:test.txt")
            assert result is True
            
            mock_path.return_value.is_file.return_value = False
            result = initialization._check_condition("file_exists:nonexistent.txt")
            assert result is False


@patch.dict('os.environ', {'TEST_VAR': 'value'})
def test_check_condition_env_exists():
    """Test env condition."""
    result = initialization._check_condition("env:TEST_VAR")
    assert result is True
    
    result = initialization._check_condition("env:NONEXISTENT_VAR")
    assert result is False


def test_check_condition_unknown():
    """Test unknown condition type."""
    result = initialization._check_condition("unknown:test")
    assert result is True  # Should default to True


@patch('par.initialization.operations.send_tmux_keys')
def test_run_initialization_no_commands(mock_send_keys):
    """Test with no initialization commands."""
    config = {"other": "settings"}
    
    initialization.run_initialization(config, "test-session")
    
    assert mock_send_keys.call_count == 0


@patch('par.initialization.operations.send_tmux_keys')
def test_run_initialization_invalid_command_config(mock_send_keys):
    """Test handling invalid command configurations."""
    config = {
        "initialization": {
            "commands": [
                "valid command",
                {"name": "Missing command"},  # No command field
                123,  # Invalid type
                {"command": "valid command"}  # Valid
            ]
        }
    }
    
    initialization.run_initialization(config, "test-session")
    
    # Should only run the valid commands
    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call("test-session", "valid command")
    mock_send_keys.assert_any_call("test-session", "valid command")