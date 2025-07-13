"""Tests for par initialization functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

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


@patch("par.initialization.operations.send_tmux_keys")
def test_run_initialization_string_commands(mock_send_keys):
    """Test running simple string commands."""
    config = {"initialization": {"commands": ["npm install", "echo hello"]}}

    worktree_path = Path("/tmp/test-worktree")
    initialization.run_initialization(config, "test-session", worktree_path)

    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call(
        "test-session", "cd /tmp/test-worktree && npm install"
    )
    mock_send_keys.assert_any_call(
        "test-session", "cd /tmp/test-worktree && echo hello"
    )


@patch("par.initialization.operations.send_tmux_keys")
def test_run_initialization_structured_commands(mock_send_keys):
    """Test running structured commands with names."""
    config = {
        "initialization": {
            "commands": [
                {"name": "Install dependencies", "command": "npm install"},
                {"name": "Start server", "command": "npm start"},
            ]
        }
    }

    worktree_path = Path("/tmp/test-worktree")
    initialization.run_initialization(config, "test-session", worktree_path)

    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call(
        "test-session", "cd /tmp/test-worktree && npm install"
    )
    mock_send_keys.assert_any_call("test-session", "cd /tmp/test-worktree && npm start")


@patch("par.initialization.operations.send_tmux_keys")
def test_run_initialization(mock_send_keys):
    """Test initialization with multiple commands."""
    config = {
        "initialization": {
            "commands": [
                {
                    "name": "Install frontend deps",
                    "command": "cd frontend && npm install",
                },
                {
                    "name": "Install backend deps",
                    "command": "cd backend && pip install -r requirements.txt",
                },
            ]
        }
    }

    worktree_path = Path("/tmp/test-worktree")
    initialization.run_initialization(config, "test-session", worktree_path)

    # Both commands should run (conditions are ignored)
    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call(
        "test-session", "cd /tmp/test-worktree && cd frontend && npm install"
    )
    mock_send_keys.assert_any_call(
        "test-session",
        "cd /tmp/test-worktree && cd backend && pip install -r requirements.txt",
    )


@patch("par.initialization.operations.send_tmux_keys")
def test_run_initialization_no_commands(mock_send_keys):
    """Test with no initialization commands."""
    config = {"other": "settings"}

    worktree_path = Path("/tmp/test-worktree")
    initialization.run_initialization(config, "test-session", worktree_path)

    assert mock_send_keys.call_count == 0


@patch("par.initialization.operations.send_tmux_keys")
def test_run_initialization_invalid_command_config(mock_send_keys):
    """Test handling invalid command configurations."""
    config = {
        "initialization": {
            "commands": [
                "valid command",
                {"name": "Missing command"},  # No command field
                123,  # Invalid type
                {"command": "valid command"},  # Valid
            ]
        }
    }

    worktree_path = Path("/tmp/test-worktree")
    initialization.run_initialization(config, "test-session", worktree_path)

    # Should only run the valid commands
    assert mock_send_keys.call_count == 2
    mock_send_keys.assert_any_call(
        "test-session", "cd /tmp/test-worktree && valid command"
    )


def test_copy_included_files(tmp_path):
    """Files listed under include are copied to the worktree."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    src = repo_root / ".env"
    src.write_text("SECRET=1")

    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()

    config = {"initialization": {"include": [".env"]}}
    initialization.copy_included_files(config, repo_root, worktree_path)

    dest = worktree_path / ".env"
    assert dest.exists() and dest.read_text() == "SECRET=1"
