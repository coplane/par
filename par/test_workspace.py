"""Tests for workspace management functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from . import workspace


@pytest.fixture
def mock_workspace_state_manager():
    """Mock workspace state manager."""
    with patch("par.workspace.get_workspace_state_manager") as mock:
        state_manager = Mock()
        state_manager.get_scoped_data.return_value = {}
        state_manager.update_scoped_data = Mock()
        mock.return_value = state_manager
        yield state_manager


@pytest.fixture
def sample_workspace_data():
    """Sample workspace data for testing."""
    return {
        "feature-auth": {
            "session_name": "par-ws-workspace-abc1-feature-auth",
            "repos": [
                {
                    "repo_name": "frontend",
                    "repo_path": "/workspace/frontend",
                    "worktree_path": "/tmp/par/workspaces/def456/feature-auth/frontend/feature-auth",
                    "branch_name": "feature-auth",
                },
                {
                    "repo_name": "backend",
                    "repo_path": "/workspace/backend",
                    "worktree_path": "/tmp/par/workspaces/def456/feature-auth/backend/feature-auth",
                    "branch_name": "feature-auth",
                },
            ],
            "created_at": "2025-01-01T00:00:00",
            "workspace_root": "/workspace",
        }
    }


class TestWorkspaceStateManagement:
    """Test workspace state management functions."""

    @patch("pathlib.Path.cwd")
    def test_get_workspace_key(self, mock_cwd):
        """Test workspace key generation."""
        mock_cwd.return_value = Path("/workspace")

        key = workspace._get_workspace_key(Path("/workspace"))

        assert key == "/workspace"

    @patch("pathlib.Path.cwd")
    def test_get_workspace_sessions_empty(self, mock_cwd, mock_workspace_state_manager):
        """Test getting workspace sessions when none exist."""
        mock_cwd.return_value = Path("/workspace")
        mock_workspace_state_manager.get_scoped_data.return_value = {}

        sessions = workspace._get_workspace_sessions(Path("/workspace"))

        assert sessions == {}
        mock_workspace_state_manager.get_scoped_data.assert_called_once_with(
            "/workspace"
        )

    @patch("pathlib.Path.cwd")
    def test_get_workspace_sessions_with_data(
        self, mock_cwd, mock_workspace_state_manager, sample_workspace_data
    ):
        """Test getting existing workspace sessions."""
        mock_cwd.return_value = Path("/workspace")
        mock_workspace_state_manager.get_scoped_data.return_value = (
            sample_workspace_data
        )

        sessions = workspace._get_workspace_sessions(Path("/workspace"))

        assert sessions == sample_workspace_data

    @patch("pathlib.Path.cwd")
    def test_update_workspace_sessions(
        self, mock_cwd, mock_workspace_state_manager, sample_workspace_data
    ):
        """Test updating workspace session data."""
        mock_cwd.return_value = Path("/workspace")

        workspace._update_workspace_sessions(Path("/workspace"), sample_workspace_data)

        mock_workspace_state_manager.update_scoped_data.assert_called_once_with(
            "/workspace", sample_workspace_data
        )


class TestWorkspaceHelperFunctions:
    """Test workspace helper functions."""

    @patch("par.workspace.utils.detect_git_repos")
    def test_prepare_workspace_repos_auto_detect(self, mock_detect_repos):
        """Test repository auto-detection."""
        mock_repos = [Path("/workspace/frontend"), Path("/workspace/backend")]
        mock_detect_repos.return_value = mock_repos

        repo_names, repo_paths = workspace._prepare_workspace_repos(
            None, Path("/workspace")
        )

        assert repo_names == ["frontend", "backend"]
        assert repo_paths == mock_repos
        mock_detect_repos.assert_called_once_with(Path("/workspace"))

    @patch("par.workspace.utils.detect_git_repos")
    def test_prepare_workspace_repos_none_found(self, mock_detect_repos):
        """Test error when no repos are auto-detected."""
        mock_detect_repos.return_value = []

        with pytest.raises((SystemExit, Exception)):
            workspace._prepare_workspace_repos(None, Path("/workspace"))

    def test_prepare_workspace_repos_explicit_valid(self, temp_workspace_dir):
        """Test explicit repository specification with valid repos."""
        repo_names, repo_paths = workspace._prepare_workspace_repos(
            ["frontend", "backend"], temp_workspace_dir
        )

        assert repo_names == ["frontend", "backend"]
        assert len(repo_paths) == 2
        assert all(path.exists() for path in repo_paths)

    def test_prepare_workspace_repos_explicit_missing(self, temp_workspace_dir):
        """Test error when specified repo doesn't exist."""
        with pytest.raises((SystemExit, Exception)):
            workspace._prepare_workspace_repos(
                ["frontend", "nonexistent"], temp_workspace_dir
            )

    def test_prepare_workspace_repos_not_git_repo(self, temp_dir):
        """Test error when specified directory is not a git repo."""
        not_repo = temp_dir / "not-repo"
        not_repo.mkdir()

        with pytest.raises((SystemExit, Exception)):
            workspace._prepare_workspace_repos(["not-repo"], temp_dir)

    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.operations.tmux_session_exists")
    def test_validate_workspace_creation_success(
        self, mock_tmux_exists, mock_get_sessions
    ):
        """Test successful workspace creation validation."""
        mock_get_sessions.return_value = {}
        mock_tmux_exists.return_value = False

        # Should not raise exception
        workspace._validate_workspace_creation(
            "new-workspace", Path("/workspace"), "session-name"
        )

    @patch("par.workspace._get_workspace_sessions")
    def test_validate_workspace_creation_duplicate_label(
        self, mock_get_sessions, sample_workspace_data
    ):
        """Test error when workspace label already exists."""
        mock_get_sessions.return_value = sample_workspace_data

        with pytest.raises((SystemExit, Exception)):
            workspace._validate_workspace_creation(
                "feature-auth", Path("/workspace"), "session-name"
            )

    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.operations.tmux_session_exists")
    def test_validate_workspace_creation_tmux_conflict(
        self, mock_tmux_exists, mock_get_sessions
    ):
        """Test error when tmux session already exists."""
        mock_get_sessions.return_value = {}
        mock_tmux_exists.return_value = True

        with pytest.raises((SystemExit, Exception)):
            workspace._validate_workspace_creation(
                "new-workspace", Path("/workspace"), "existing-session"
            )

    @patch("par.workspace.utils.get_workspace_worktree_path")
    @patch("par.workspace.operations.create_workspace_worktree")
    def test_create_workspace_worktrees_success(
        self, mock_create_worktree, mock_get_path
    ):
        """Test successful workspace worktree creation."""
        mock_get_path.side_effect = (
            lambda workspace_root, label, repo_name, branch: Path(
                f"/tmp/workspaces/{label}/{repo_name}/{branch}"
            )
        )

        repo_names = ["frontend", "backend"]
        repo_paths = [Path("/workspace/frontend"), Path("/workspace/backend")]

        repos_data = workspace._create_workspace_worktrees(
            Path("/workspace"), "feature-auth", repo_names, repo_paths
        )

        assert len(repos_data) == 2
        assert repos_data[0]["repo_name"] == "frontend"
        assert repos_data[1]["repo_name"] == "backend"

        # Should create worktree for each repo
        assert mock_create_worktree.call_count == 2

    @patch("par.workspace.utils.get_workspace_worktree_path")
    def test_create_workspace_worktrees_path_conflict(self, mock_get_path, temp_dir):
        """Test error when worktree path already exists."""
        existing_path = temp_dir / "existing"
        existing_path.mkdir()

        mock_get_path.return_value = existing_path

        repo_names = ["frontend"]
        repo_paths = [Path("/workspace/frontend")]

        with pytest.raises((SystemExit, Exception)):
            workspace._create_workspace_worktrees(
                Path("/workspace"), "feature-auth", repo_names, repo_paths
            )

    @patch("par.workspace.initialization.load_par_config")
    @patch("par.workspace.initialization.run_initialization")
    @patch("par.workspace.operations.send_tmux_keys")
    def test_run_workspace_initialization_with_config(
        self, mock_send_keys, mock_run_init, mock_load_config
    ):
        """Test workspace initialization with .par.yaml config."""
        mock_config = {"initialization": {"commands": ["echo test"]}}
        mock_load_config.return_value = mock_config

        repos_data = [
            {
                "repo_path": "/workspace/frontend",
                "worktree_path": "/tmp/worktree/frontend",
            }
        ]

        has_init = workspace._run_workspace_initialization(repos_data, "session-name")

        assert has_init is True
        mock_run_init.assert_called_once()
        # We no longer send cd command in _run_workspace_initialization
        mock_send_keys.assert_not_called()

    @patch("par.workspace.initialization.load_par_config")
    def test_run_workspace_initialization_no_config(self, mock_load_config):
        """Test workspace initialization with no .par.yaml config."""
        mock_load_config.return_value = None

        repos_data = [
            {
                "repo_path": "/workspace/frontend",
                "worktree_path": "/tmp/worktree/frontend",
            }
        ]

        has_init = workspace._run_workspace_initialization(repos_data, "session-name")

        assert has_init is False

    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace._update_workspace_sessions")
    def test_update_workspace_state(self, mock_update_sessions, mock_get_sessions):
        """Test workspace state update."""
        mock_get_sessions.return_value = {}

        repos_data = [{"repo_name": "frontend", "branch_name": "feature-auth"}]

        workspace._update_workspace_state(
            Path("/workspace"), "feature-auth", repos_data, "session-name"
        )

        # Should call update with proper structure
        mock_update_sessions.assert_called_once()
        call_args = mock_update_sessions.call_args[0]
        assert call_args[0] == Path("/workspace")  # workspace_root

        updated_data = call_args[1]  # sessions data
        assert "feature-auth" in updated_data
        assert updated_data["feature-auth"]["session_name"] == "session-name"
        assert updated_data["feature-auth"]["repos"] == repos_data

    def test_display_workspace_created(self, capsys):
        """Test workspace creation success message display."""
        repos_data = [
            {"repo_name": "frontend", "worktree_path": "/tmp/frontend"},
            {"repo_name": "backend", "worktree_path": "/tmp/backend"},
        ]

        workspace._display_workspace_created("feature-auth", repos_data, "session-name")

        # Should display success message (captured output would be tested in integration tests)


class TestWorkspaceOperations:
    """Test main workspace operations."""

    @patch("par.workspace._prepare_workspace_repos")
    @patch("par.workspace._validate_workspace_creation")
    @patch("par.workspace._create_workspace_worktrees")
    @patch("par.workspace.operations.create_workspace_tmux_session")
    @patch("par.workspace._run_workspace_initialization")
    @patch("par.workspace._update_workspace_state")
    @patch("par.workspace._display_workspace_created")
    @patch("par.workspace.operations.send_tmux_keys")
    @patch("par.workspace.utils.get_workspace_session_name")
    @patch("pathlib.Path.cwd")
    def test_start_workspace_session_success(
        self,
        mock_cwd,
        mock_get_session_name,
        mock_send_keys,
        mock_display,
        mock_update_state,
        mock_run_init,
        mock_create_tmux,
        mock_create_worktrees,
        mock_validate,
        mock_prepare_repos,
    ):
        """Test successful workspace session creation."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_session_name.return_value = "par-ws-workspace-abc1-feature-auth"
        mock_prepare_repos.return_value = (
            ["frontend", "backend"],
            [Path("/workspace/frontend"), Path("/workspace/backend")],
        )
        mock_create_worktrees.return_value = [
            {"repo_name": "frontend", "worktree_path": "/tmp/frontend"},
            {"repo_name": "backend", "worktree_path": "/tmp/backend"},
        ]
        mock_run_init.return_value = False

        workspace.start_workspace_session("feature-auth")

        # Verify all steps were called
        mock_prepare_repos.assert_called_once()
        mock_validate.assert_called_once()
        mock_create_worktrees.assert_called_once()
        mock_create_tmux.assert_called_once()
        mock_run_init.assert_called_once()
        mock_update_state.assert_called_once()
        mock_display.assert_called_once()
        # Should send cd command and welcome message
        assert mock_send_keys.call_count == 2
        # The workspace root is calculated as worktree_path.parent.parent
        # /tmp/frontend -> /tmp -> /
        mock_send_keys.assert_any_call("par-ws-workspace-abc1-feature-auth", "cd /")
        mock_send_keys.assert_any_call("par-ws-workspace-abc1-feature-auth", "par")

    @patch("par.workspace._prepare_workspace_repos")
    @patch("par.workspace._validate_workspace_creation")
    @patch("par.workspace._create_workspace_worktrees")
    @patch("par.workspace.operations.create_workspace_tmux_session")
    @patch("par.workspace._run_workspace_initialization")
    @patch("par.workspace._update_workspace_state")
    @patch("par.workspace._display_workspace_created")
    @patch("par.workspace.operations.send_tmux_keys")
    @patch("par.workspace.open_workspace_session")
    @patch("par.workspace.utils.get_workspace_session_name")
    @patch("pathlib.Path.cwd")
    def test_start_workspace_session_with_open(
        self,
        mock_cwd,
        mock_get_session_name,
        mock_open,
        mock_send_keys,
        mock_display,
        mock_update_state,
        mock_run_init,
        mock_create_tmux,
        mock_create_worktrees,
        mock_validate,
        mock_prepare_repos,
    ):
        """Test workspace session creation with auto-open."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_session_name.return_value = "session-name"
        mock_prepare_repos.return_value = (["frontend"], [Path("/workspace/frontend")])
        mock_create_worktrees.return_value = [
            {"repo_name": "frontend", "worktree_path": "/tmp/frontend"}
        ]
        mock_run_init.return_value = False

        workspace.start_workspace_session("feature-auth", open_session=True)

        # Should open the workspace at the end
        mock_open.assert_called_once_with("feature-auth")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_list_workspace_sessions_empty(self, mock_get_sessions, mock_cwd):
        """Test listing when no workspace sessions exist."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = {}

        # Should not raise exception, just show message
        workspace.list_workspace_sessions()

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.Console")
    def test_list_workspace_sessions_with_data(
        self, mock_console, mock_get_sessions, mock_cwd, sample_workspace_data
    ):
        """Test listing with workspace session data."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data

        workspace.list_workspace_sessions()

        # Should create and print table
        mock_console.return_value.print.assert_called()

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.operations.tmux_session_exists")
    @patch("par.workspace.operations.open_tmux_session")
    def test_open_workspace_session_existing(
        self,
        mock_open_tmux,
        mock_tmux_exists,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test opening existing workspace session."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data
        mock_tmux_exists.return_value = True

        workspace.open_workspace_session("feature-auth")

        mock_open_tmux.assert_called_once_with("par-ws-workspace-abc1-feature-auth")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.operations.tmux_session_exists")
    @patch("par.workspace.operations.create_workspace_tmux_session")
    @patch("par.workspace.operations.open_tmux_session")
    def test_open_workspace_session_recreate(
        self,
        mock_open_tmux,
        mock_create_tmux,
        mock_tmux_exists,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test opening workspace session with recreated tmux session."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data
        mock_tmux_exists.return_value = False  # Session doesn't exist

        workspace.open_workspace_session("feature-auth")

        # Should recreate the session
        repos_data = sample_workspace_data["feature-auth"]["repos"]
        mock_create_tmux.assert_called_once_with(
            "par-ws-workspace-abc1-feature-auth", repos_data
        )
        mock_open_tmux.assert_called_once_with("par-ws-workspace-abc1-feature-auth")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_open_workspace_session_not_found(self, mock_get_sessions, mock_cwd):
        """Test opening non-existent workspace session."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = {}

        with pytest.raises((SystemExit, Exception)):
            workspace.open_workspace_session("nonexistent")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.operations.kill_tmux_session")
    @patch("par.workspace.operations.remove_workspace_worktree")
    @patch("par.workspace.operations.delete_workspace_branch")
    @patch("par.workspace._update_workspace_sessions")
    def test_remove_workspace_session_success(
        self,
        mock_update_sessions,
        mock_delete_branch,
        mock_remove_worktree,
        mock_kill_tmux,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test successful workspace session removal."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data

        workspace.remove_workspace_session("feature-auth")

        # Should kill tmux session
        mock_kill_tmux.assert_called_once_with("par-ws-workspace-abc1-feature-auth")

        # Should remove worktrees and branches for each repo
        assert mock_remove_worktree.call_count == 2
        assert mock_delete_branch.call_count == 2

        # Should update state
        mock_update_sessions.assert_called_once()

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_remove_workspace_session_not_found(self, mock_get_sessions, mock_cwd):
        """Test removing non-existent workspace session."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = {}

        with pytest.raises((SystemExit, Exception)):
            workspace.remove_workspace_session("nonexistent")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.remove_workspace_session")
    @patch("builtins.input", return_value="y")
    def test_remove_all_workspace_sessions_confirmed(
        self,
        mock_input,
        mock_remove_session,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test removing all workspace sessions with confirmation."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data

        workspace.remove_all_workspace_sessions()

        # Should remove the workspace
        mock_remove_session.assert_called_once_with("feature-auth")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("builtins.input", return_value="n")
    def test_remove_all_workspace_sessions_cancelled(
        self, mock_input, mock_get_sessions, mock_cwd, sample_workspace_data
    ):
        """Test cancelling remove all workspace sessions."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data

        # Should not raise exception
        workspace.remove_all_workspace_sessions()

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_remove_all_workspace_sessions_empty(self, mock_get_sessions, mock_cwd):
        """Test removing all when no workspace sessions exist."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = {}

        # Should not raise exception
        workspace.remove_all_workspace_sessions()


class TestWorkspaceIDEIntegration:
    """Test workspace IDE integration."""

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.utils.save_vscode_workspace_file")
    @patch("par.workspace.operations.run_cmd")
    def test_open_workspace_in_vscode(
        self,
        mock_run_cmd,
        mock_save_file,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test opening workspace in VSCode."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data
        mock_save_file.return_value = Path("/tmp/feature-auth.code-workspace")

        workspace.open_workspace_in_ide("feature-auth", "code")

        # Should save workspace file
        repos_data = sample_workspace_data["feature-auth"]["repos"]
        mock_save_file.assert_called_once_with("feature-auth", repos_data)

        # Should open with VSCode
        mock_run_cmd.assert_called_once_with(
            ["code", "/tmp/feature-auth.code-workspace"]
        )

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.utils.save_vscode_workspace_file")
    @patch("par.workspace.operations.run_cmd")
    def test_open_workspace_in_cursor(
        self,
        mock_run_cmd,
        mock_save_file,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test opening workspace in Cursor."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data
        mock_save_file.return_value = Path("/tmp/feature-auth.code-workspace")

        workspace.open_workspace_in_ide("feature-auth", "cursor")

        # Should open with Cursor
        mock_run_cmd.assert_called_once_with(
            ["cursor", "/tmp/feature-auth.code-workspace"]
        )

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_open_workspace_in_ide_not_found(self, mock_get_sessions, mock_cwd):
        """Test opening non-existent workspace in IDE."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = {}

        with pytest.raises((SystemExit, Exception)):
            workspace.open_workspace_in_ide("nonexistent", "code")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    def test_open_workspace_in_unsupported_ide(
        self, mock_get_sessions, mock_cwd, sample_workspace_data
    ):
        """Test opening workspace in unsupported IDE."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data

        with pytest.raises((SystemExit, Exception)):
            workspace.open_workspace_in_ide("feature-auth", "unsupported")

    @patch("pathlib.Path.cwd")
    @patch("par.workspace._get_workspace_sessions")
    @patch("par.workspace.utils.save_vscode_workspace_file")
    @patch("par.workspace.operations.run_cmd")
    def test_open_workspace_in_ide_command_failure(
        self,
        mock_run_cmd,
        mock_save_file,
        mock_get_sessions,
        mock_cwd,
        sample_workspace_data,
    ):
        """Test IDE command failure."""
        mock_cwd.return_value = Path("/workspace")
        mock_get_sessions.return_value = sample_workspace_data
        mock_save_file.return_value = Path("/tmp/feature-auth.code-workspace")
        mock_run_cmd.side_effect = Exception("Command failed")

        with pytest.raises((SystemExit, Exception)):
            workspace.open_workspace_in_ide("feature-auth", "code")


class TestWorkspaceErrorHandling:
    """Test workspace error handling and edge cases."""

    @patch("par.workspace._prepare_workspace_repos")
    def test_start_workspace_session_repo_preparation_failure(self, mock_prepare_repos):
        """Test handling of repository preparation failure."""
        mock_prepare_repos.side_effect = SystemExit(1)

        with pytest.raises((SystemExit, Exception)):
            workspace.start_workspace_session("feature-auth")

    @patch("par.workspace._prepare_workspace_repos")
    @patch("par.workspace._validate_workspace_creation")
    def test_start_workspace_session_validation_failure(
        self, mock_validate, mock_prepare_repos
    ):
        """Test handling of workspace validation failure."""
        mock_prepare_repos.return_value = (["frontend"], [Path("/workspace/frontend")])
        mock_validate.side_effect = SystemExit(1)

        with pytest.raises((SystemExit, Exception)):
            workspace.start_workspace_session("feature-auth")

    @patch("par.workspace._prepare_workspace_repos")
    @patch("par.workspace._validate_workspace_creation")
    @patch("par.workspace._create_workspace_worktrees")
    def test_start_workspace_session_worktree_creation_failure(
        self, mock_create_worktrees, mock_validate, mock_prepare_repos
    ):
        """Test handling of worktree creation failure."""
        mock_prepare_repos.return_value = (["frontend"], [Path("/workspace/frontend")])
        mock_create_worktrees.side_effect = SystemExit(1)

        with pytest.raises((SystemExit, Exception)):
            workspace.start_workspace_session("feature-auth")

    def test_workspace_operations_with_empty_repos_data(self):
        """Test workspace operations with empty repos data."""
        # Most operations should handle empty repos gracefully
        has_init = workspace._run_workspace_initialization([], "session-name")
        assert has_init is False

    def test_workspace_state_update_with_invalid_data(self):
        """Test workspace state update with invalid data."""
        # Should handle gracefully or raise appropriate errors
        try:
            workspace._update_workspace_state(Path("/workspace"), "test", [], "session")
        except Exception as e:
            # Should be a specific, handled exception
            assert isinstance(e, (ValueError, TypeError, SystemExit))


# Test file for workspace management
