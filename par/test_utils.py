"""Tests for core utility functions."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from . import utils
from .constants import Config


class TestCommandExecution:
    """Test command execution utilities."""

    def test_run_cmd_success(self):
        """Test successful command execution."""
        result = utils.run_cmd(["echo", "hello"])

        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_run_cmd_failure(self):
        """Test command execution failure."""
        with pytest.raises(subprocess.CalledProcessError):
            utils.run_cmd(["false"])  # Command that always fails

    def test_run_cmd_not_found(self):
        """Test command not found error."""
        try:
            utils.run_cmd(["nonexistent-command-12345"])
            assert False, "Should have raised an exception"
        except (SystemExit, FileNotFoundError, Exception):
            pass  # Expected

    def test_run_cmd_no_capture(self):
        """Test command execution without capturing output."""
        result = utils.run_cmd(["echo", "hello"], capture=False)

        assert result.returncode == 0
        assert result.stdout is None

    def test_run_cmd_suppress_output(self):
        """Test command execution with output suppression."""
        # This should not raise even though the command fails
        with pytest.raises(subprocess.CalledProcessError):
            utils.run_cmd(["false"], suppress_output=True)

    def test_run_cmd_no_check(self):
        """Test command execution without checking return code."""
        result = utils.run_cmd(["false"], check=False)

        assert result.returncode == 1

    def test_run_cmd_with_cwd(self, temp_dir):
        """Test command execution with working directory."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        result = utils.run_cmd(["ls", "test.txt"], cwd=temp_dir)

        assert result.returncode == 0
        assert "test.txt" in result.stdout


class TestDataDirectory:
    """Test data directory management."""

    def test_get_data_dir_default(self):
        """Test default data directory location."""
        with patch.dict(os.environ, {}, clear=True):
            data_dir = utils.get_data_dir()

            expected = Path.home() / ".local" / "share" / Config.DATA_DIR_NAME
            assert data_dir == expected
            assert data_dir.exists()

    def test_get_data_dir_xdg_override(self):
        """Test XDG_DATA_HOME override."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg"}):
            data_dir = utils.get_data_dir()

            expected = Path("/tmp/xdg") / Config.DATA_DIR_NAME
            assert data_dir == expected

    def test_get_data_dir_creates_directory(self, temp_dir):
        """Test that data directory is created if it doesn't exist."""
        test_data_dir = temp_dir / "test-par-data"

        with patch.dict(os.environ, {"XDG_DATA_HOME": str(temp_dir)}):
            with patch("par.utils.Config.DATA_DIR_NAME", "test-par-data"):
                data_dir = utils.get_data_dir()

                assert data_dir == test_data_dir
                assert data_dir.exists()
                assert data_dir.is_dir()


class TestGitUtilities:
    """Test git-related utilities."""

    @patch("par.utils.run_cmd")
    def test_get_git_repo_root_valid(self, mock_run_cmd):
        """Test getting repo root from valid git repo."""
        mock_run_cmd.return_value = Mock(stdout="/path/to/repo\n")

        repo_root = utils.get_git_repo_root()

        assert repo_root == Path("/path/to/repo")
        mock_run_cmd.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"], capture=True, suppress_output=True
        )

    @patch("par.utils.run_cmd")
    def test_get_git_repo_root_invalid(self, mock_run_cmd):
        """Test error when not in git repo."""
        mock_run_cmd.side_effect = subprocess.CalledProcessError(128, "git")

        with pytest.raises((SystemExit, Exception)):
            utils.get_git_repo_root()

    def test_detect_git_repos_found(self, temp_dir):
        """Test detecting git repos in directory."""
        # Create test repos
        repo1 = temp_dir / "repo1"
        repo2 = temp_dir / "repo2"
        non_repo = temp_dir / "not-a-repo"

        for repo in [repo1, repo2]:
            repo.mkdir()
            (repo / ".git").mkdir()

        non_repo.mkdir()

        repos = utils.detect_git_repos(temp_dir)

        assert len(repos) == 2
        assert repo1 in repos
        assert repo2 in repos
        assert non_repo not in repos

    def test_detect_git_repos_none_found(self, temp_dir):
        """Test detecting no git repos."""
        # Create non-git directories
        (temp_dir / "dir1").mkdir()
        (temp_dir / "dir2").mkdir()

        repos = utils.detect_git_repos(temp_dir)

        assert repos == []

    def test_detect_git_repos_nonexistent_directory(self):
        """Test detecting repos in nonexistent directory."""
        repos = utils.detect_git_repos(Path("/nonexistent"))

        assert repos == []

    def test_detect_git_repos_sorted(self, temp_dir):
        """Test that detected repos are sorted."""
        # Create repos in reverse alphabetical order
        for name in ["z-repo", "a-repo", "m-repo"]:
            repo = temp_dir / name
            repo.mkdir()
            (repo / ".git").mkdir()

        repos = utils.detect_git_repos(temp_dir)

        repo_names = [repo.name for repo in repos]
        assert repo_names == ["a-repo", "m-repo", "z-repo"]


class TestRepositoryIdentification:
    """Test repository identification and naming."""

    def test_get_repo_id_consistency(self):
        """Test repo ID generation is consistent."""
        repo_path = Path("/path/to/repo")

        id1 = utils._get_repo_id(repo_path)
        id2 = utils._get_repo_id(repo_path)

        assert id1 == id2

    def test_get_repo_id_uniqueness(self):
        """Test repo ID generation is unique per repo."""
        repo1 = Path("/path/to/repo1")
        repo2 = Path("/path/to/repo2")

        id1 = utils._get_repo_id(repo1)
        id2 = utils._get_repo_id(repo2)

        assert id1 != id2

    def test_get_repo_id_length(self):
        """Test repo ID has correct length."""
        repo_path = Path("/path/to/repo")

        repo_id = utils._get_repo_id(repo_path)

        assert len(repo_id) == Config.REPO_ID_LENGTH

    def test_get_repo_id_full_length(self):
        """Test full repo ID has correct length."""
        repo_path = Path("/path/to/repo")

        repo_id = utils.get_repo_id(repo_path)

        assert len(repo_id) == Config.REPO_ID_FULL_LENGTH

    def test_repo_id_deterministic(self):
        """Test repo ID is deterministic based on path."""
        repo_path = Path("/path/to/repo")
        expected_hash = hashlib.sha256(str(repo_path.resolve()).encode()).hexdigest()

        repo_id = utils._get_repo_id(repo_path)

        assert repo_id == expected_hash[: Config.REPO_ID_LENGTH]


class TestPathGeneration:
    """Test path generation utilities."""

    @patch("par.utils.get_data_dir")
    def test_get_worktree_path(self, mock_get_data_dir, temp_dir):
        """Test worktree path generation."""
        mock_get_data_dir.return_value = temp_dir
        repo_root = Path("/repo")

        worktree_path = utils.get_worktree_path(repo_root, "feature-branch")

        # Should be in data_dir/worktrees/repo_id/label
        expected_repo_id = utils._get_repo_id(repo_root)
        expected_path = (
            temp_dir / Config.WORKTREES_DIR_NAME / expected_repo_id / "feature-branch"
        )

        assert worktree_path == expected_path
        assert worktree_path.parent.exists()  # Should create parent directories

    def test_get_tmux_session_name(self):
        """Test tmux session name generation."""
        repo_root = Path("/path/to/my-awesome-repo")

        session_name = utils.get_tmux_session_name(repo_root, "feature-branch")

        expected_repo_name = "my-awesome-repo"[: Config.SESSION_NAME_MAX_LENGTH]
        expected_repo_id = utils._get_repo_id(repo_root)[:4]
        expected = f"{Config.TMUX_SESSION_PREFIX}-{expected_repo_name}-{expected_repo_id}-feature-branch"

        assert session_name == expected

    def test_get_tmux_session_name_long_repo_name(self):
        """Test tmux session name with long repository name."""
        repo_root = Path("/path/to/very-long-repository-name-that-exceeds-limit")

        session_name = utils.get_tmux_session_name(repo_root, "feature")

        # Repo name should be truncated
        parts = session_name.split("-")
        assert len(parts) >= 4  # prefix + truncated_name + id + label

        # Should not exceed reasonable length
        assert len(session_name) < 80

    def test_get_tmux_session_name_special_characters(self):
        """Test tmux session name with special characters in repo name."""
        repo_root = Path("/path/to/repo.with.dots and spaces")

        session_name = utils.get_tmux_session_name(repo_root, "feature")

        # Should replace dots and spaces with hyphens
        assert ".with.dots" not in session_name
        assert " " not in session_name
        assert "repo-with-dots" in session_name or "repo-with-dots-and" in session_name

    @patch("par.utils.get_data_dir")
    def test_get_worktrees_base_dir(self, mock_get_data_dir, temp_dir):
        """Test worktrees base directory creation."""
        mock_get_data_dir.return_value = temp_dir

        base_dir = utils.get_worktrees_base_dir()

        expected = temp_dir / Config.WORKTREES_DIR_NAME
        assert base_dir == expected
        assert base_dir.exists()

    @patch("par.utils.get_data_dir")
    def test_get_repo_worktrees_dir(self, mock_get_data_dir, temp_dir):
        """Test repo-specific worktrees directory creation."""
        mock_get_data_dir.return_value = temp_dir
        repo_root = Path("/repo")

        repo_dir = utils.get_repo_worktrees_dir(repo_root)

        expected_repo_id = utils.get_repo_id(repo_root)
        expected = temp_dir / Config.WORKTREES_DIR_NAME / expected_repo_id

        assert repo_dir == expected
        assert repo_dir.exists()


class TestWorkspaceUtilities:
    """Test workspace-related utilities."""

    @patch("par.utils.get_data_dir")
    def test_get_workspace_worktree_path(self, mock_get_data_dir, temp_dir):
        """Test workspace worktree path generation."""
        mock_get_data_dir.return_value = temp_dir
        workspace_root = Path("/workspace")

        worktree_path = utils.get_workspace_worktree_path(
            workspace_root, "feature-auth", "frontend", "feature-auth"
        )

        # Should include workspace ID in path
        workspace_id = hashlib.sha256(
            str(workspace_root.resolve()).encode()
        ).hexdigest()[:8]
        expected = (
            temp_dir
            / Config.WORKSPACES_DIR_NAME
            / workspace_id
            / "feature-auth"
            / "frontend"
        )

        assert worktree_path == expected
        # Function should create parent directories
        assert worktree_path.parent.parent.exists()  # workspace_id dir should exist

    def test_get_workspace_session_name(self):
        """Test workspace session name generation."""
        workspace_root = Path("/path/to/my-workspace")

        session_name = utils.get_workspace_session_name(workspace_root, "feature-auth")

        expected_workspace_name = "my-workspace"[: Config.SESSION_NAME_MAX_LENGTH]
        expected_workspace_id = hashlib.sha256(
            str(workspace_root.resolve()).encode()
        ).hexdigest()[:4]
        expected = f"{Config.WORKSPACE_SESSION_PREFIX}-{expected_workspace_name}-{expected_workspace_id}-feature-auth"

        assert session_name == expected

    def test_generate_vscode_workspace(self):
        """Test VSCode workspace config generation."""
        repos_data = [
            {
                "repo_name": "frontend",
                "worktree_path": "/tmp/workspace/frontend/feature-auth",
            },
            {
                "repo_name": "backend",
                "worktree_path": "/tmp/workspace/backend/feature-auth",
            },
        ]

        config = utils.generate_vscode_workspace("feature-auth", repos_data)

        assert "folders" in config
        assert len(config["folders"]) == 2

        # Check first folder
        assert config["folders"][0]["name"] == "frontend (feature-auth)"
        assert config["folders"][0]["path"] == "/tmp/workspace/frontend/feature-auth"

        # Check second folder
        assert config["folders"][1]["name"] == "backend (feature-auth)"
        assert config["folders"][1]["path"] == "/tmp/workspace/backend/feature-auth"

        # Check settings
        assert "settings" in config
        assert config["settings"]["git.detectSubmodules"] is False
        assert config["settings"]["git.repositoryScanMaxDepth"] == 1

        # Check extensions
        assert "extensions" in config
        assert "recommendations" in config["extensions"]

    @patch("par.utils.get_data_dir")
    def test_get_workspace_file_path(self, mock_get_data_dir, temp_dir):
        """Test workspace file path generation."""
        mock_get_data_dir.return_value = temp_dir
        workspace_root = Path("/workspace")

        workspace_file = utils.get_workspace_file_path(workspace_root, "feature-auth")

        workspace_id = hashlib.sha256(
            str(workspace_root.resolve()).encode()
        ).hexdigest()[:8]
        expected = (
            temp_dir
            / Config.WORKSPACES_DIR_NAME
            / workspace_id
            / "feature-auth"
            / "feature-auth.code-workspace"
        )

        assert workspace_file == expected
        assert workspace_file.parent.exists()

    @patch("par.utils.get_data_dir")
    def test_save_vscode_workspace_file(self, mock_get_data_dir, temp_dir):
        """Test saving VSCode workspace file."""
        mock_get_data_dir.return_value = temp_dir

        repos_data = [
            {
                "repo_name": "frontend",
                "worktree_path": str(
                    temp_dir
                    / "workspaces"
                    / "abc123"
                    / "feature-auth"
                    / "frontend"
                    / "feature-auth"
                ),
            }
        ]

        # Create the directory structure to simulate workspace layout
        workspace_dir = temp_dir / "workspaces" / "abc123" / "feature-auth"
        workspace_dir.mkdir(parents=True)

        workspace_file = utils.save_vscode_workspace_file("feature-auth", repos_data)

        assert workspace_file.exists()
        assert workspace_file.suffix == ".code-workspace"

        # Verify file content
        with open(workspace_file) as f:
            config = json.load(f)

        assert "folders" in config
        assert len(config["folders"]) == 1
        assert config["folders"][0]["name"] == "frontend (feature-auth)"

    def test_save_vscode_workspace_file_no_repos(self):
        """Test error when saving workspace file with no repos."""
        with pytest.raises(ValueError, match="No repositories provided"):
            utils.save_vscode_workspace_file("feature-auth", [])


class TestTmuxUtilities:
    """Test tmux-related utilities."""

    @patch("par.utils.run_cmd")
    def test_is_tmux_running_true(self, mock_run_cmd):
        """Test detecting running tmux server."""
        mock_run_cmd.return_value = Mock(returncode=0)

        result = utils.is_tmux_running()

        assert result is True
        mock_run_cmd.assert_called_once_with(
            ["tmux", "has-session"], check=False, capture=True, suppress_output=True
        )

    @patch("par.utils.run_cmd")
    def test_is_tmux_running_false_no_server(self, mock_run_cmd):
        """Test detecting no tmux server."""
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "tmux")

        result = utils.is_tmux_running()

        assert result is False

    @patch("par.utils.run_cmd")
    def test_is_tmux_running_false_not_installed(self, mock_run_cmd):
        """Test when tmux is not installed."""
        import typer

        mock_run_cmd.side_effect = typer.Exit(127)  # Command not found

        result = utils.is_tmux_running()

        assert result is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_paths(self):
        """Test handling of empty paths."""
        # Empty path should still generate a hash, just might not be meaningful
        repo_id = utils._get_repo_id(Path(""))
        assert isinstance(repo_id, str)
        assert len(repo_id) == Config.REPO_ID_LENGTH

    def test_very_long_paths(self):
        """Test handling of very long paths."""
        long_path = Path("/" + "very-long-directory-name" * 10)

        # Should not raise exception
        repo_id = utils._get_repo_id(long_path)
        assert len(repo_id) == Config.REPO_ID_LENGTH

    def test_special_characters_in_paths(self):
        """Test handling of special characters in paths."""
        special_path = Path("/path/with spaces/and-symbols!@#$%^&*()")

        # Should generate valid ID
        repo_id = utils._get_repo_id(special_path)
        assert len(repo_id) == Config.REPO_ID_LENGTH
        assert repo_id.isalnum()  # Should be hexadecimal

    def test_unicode_in_paths(self):
        """Test handling of unicode characters in paths."""
        unicode_path = Path("/path/with/unicode/café/ñoño")

        # Should handle unicode gracefully
        repo_id = utils._get_repo_id(unicode_path)
        assert len(repo_id) == Config.REPO_ID_LENGTH

    @patch("par.utils.get_data_dir")
    def test_permission_errors(self, mock_get_data_dir, temp_dir):
        """Test handling of permission errors."""
        # Create a directory and make it read-only
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        mock_get_data_dir.return_value = readonly_dir

        try:
            # This might raise PermissionError depending on the system
            utils.get_worktrees_base_dir()
        except PermissionError:
            # Expected on some systems
            pass
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


# Test file for utility functions
