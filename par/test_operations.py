"""Tests for git and tmux operations."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from . import operations


class TestInputValidation:
    """Test input validation functions."""

    def test_validate_session_name_valid(self):
        """Test valid session names pass validation."""
        valid_names = ["test-session", "my_session", "session.1", "a", "long-valid-name"]
        
        for name in valid_names:
            operations._validate_session_name(name)  # Should not raise

    def test_validate_session_name_invalid(self):
        """Test invalid session names raise ValueError."""
        invalid_names = ["", "session with spaces", "session@invalid", "a" * 65]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                operations._validate_session_name(name)

    def test_validate_branch_name_valid(self):
        """Test valid branch names pass validation."""
        valid_names = ["feature-branch", "feature/new-ui", "hotfix_123", "v1.2.3"]
        
        for name in valid_names:
            operations._validate_branch_name(name)  # Should not raise

    def test_validate_branch_name_invalid(self):
        """Test invalid branch names raise ValueError."""
        invalid_names = ["", "branch with spaces", "branch..danger", "a" * 256]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                operations._validate_branch_name(name)

    def test_sanitize_command_valid(self):
        """Test command sanitization."""
        test_cases = [
            ("ls -la", "ls -la"),
            ("echo 'hello world'", "echo 'hello world'"),
            ("normal command", "normal command"),
        ]
        
        for input_cmd, expected in test_cases:
            result = operations._sanitize_command(input_cmd)
            assert result == expected

    def test_sanitize_command_removes_control_chars(self):
        """Test removal of forbidden control characters."""
        test_cases = [
            ("echo 'hello\0world'", "echo 'helloworld'"),
            ("ls\x1b[0m", "ls[0m"),
            ("\0\x1b", ""),
        ]
        
        for input_cmd, expected in test_cases:
            result = operations._sanitize_command(input_cmd)
            assert result == expected

    def test_sanitize_command_length_limit(self):
        """Test command length validation."""
        long_command = "echo " + "a" * 1000
        
        with pytest.raises(ValueError, match="Command too long"):
            operations._sanitize_command(long_command)


class TestTmuxUtilities:
    """Test tmux utility functions."""

    @patch('par.operations.run_cmd')
    def test_check_tmux_available(self, mock_run_cmd):
        """Test tmux availability check when tmux is available."""
        mock_run_cmd.return_value = Mock(returncode=0)
        
        operations._check_tmux()  # Should not raise
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "has-session"], check=False, capture=True, suppress_output=True
        )

    @patch('par.operations.run_cmd')
    def test_check_tmux_unavailable(self, mock_run_cmd):
        """Test tmux availability check when tmux is unavailable."""
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "tmux")
        
        with pytest.raises((SystemExit, Exception)):
            operations._check_tmux()

    @patch('par.operations.run_cmd')
    def test_check_tmux_not_found(self, mock_run_cmd):
        """Test tmux availability check when tmux is not installed."""
        mock_run_cmd.side_effect = FileNotFoundError()
        
        with pytest.raises((SystemExit, Exception)):
            operations._check_tmux()


class TestGitOperations:
    """Test git operations."""

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_create_worktree_success(self, mock_run_cmd, mock_repo_root):
        """Test successful worktree creation."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        operations.create_worktree("feature-branch", worktree_path)
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "add", "-b", "feature-branch", str(worktree_path)],
            cwd=Path("/repo")
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_create_worktree_with_base_branch(self, mock_run_cmd, mock_repo_root):
        """Test worktree creation with base branch."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        operations.create_worktree("feature-branch", worktree_path, "develop")
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "add", "-b", "feature-branch", str(worktree_path), "develop"],
            cwd=Path("/repo")
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_create_worktree_invalid_label(self, mock_run_cmd, mock_repo_root):
        """Test worktree creation with invalid label."""
        with pytest.raises((SystemExit, Exception)):
            operations.create_worktree("invalid label", Path("/tmp/worktree"))

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_create_worktree_failure(self, mock_run_cmd, mock_repo_root):
        """Test worktree creation failure."""
        mock_repo_root.return_value = Path("/repo")
        mock_run_cmd.side_effect = Exception("Git error")
        
        with pytest.raises((SystemExit, Exception)):
            operations.create_worktree("feature-branch", Path("/tmp/worktree"))

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_remove_worktree_success(self, mock_run_cmd, mock_repo_root):
        """Test successful worktree removal."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        operations.remove_worktree(worktree_path)
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=Path("/repo"),
            suppress_output=True
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_remove_worktree_failure_ignored(self, mock_run_cmd, mock_repo_root):
        """Test worktree removal failure is ignored."""
        mock_repo_root.return_value = Path("/repo")
        mock_run_cmd.side_effect = Exception("Worktree doesn't exist")
        
        # Should not raise exception
        operations.remove_worktree(Path("/tmp/worktree"))

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_delete_branch_success(self, mock_run_cmd, mock_repo_root):
        """Test successful branch deletion."""
        mock_repo_root.return_value = Path("/repo")
        
        operations.delete_branch("feature-branch")
        
        mock_run_cmd.assert_called_once_with(
            ["git", "branch", "-D", "feature-branch"],
            cwd=Path("/repo"),
            suppress_output=True
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_delete_branch_invalid_name(self, mock_run_cmd, mock_repo_root):
        """Test branch deletion with invalid name."""
        # Should return early without calling git
        operations.delete_branch("invalid branch")
        
        mock_run_cmd.assert_not_called()

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_delete_branch_failure_ignored(self, mock_run_cmd, mock_repo_root):
        """Test branch deletion failure is ignored."""
        mock_repo_root.return_value = Path("/repo")
        mock_run_cmd.side_effect = Exception("Branch doesn't exist")
        
        # Should not raise exception
        operations.delete_branch("feature-branch")

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_checkout_worktree_existing_branch(self, mock_run_cmd, mock_repo_root):
        """Test checking out existing branch to worktree."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        strategy = Mock()
        strategy.is_pr = False
        strategy.fetch_remote = False
        strategy.ref = "existing-branch"
        
        operations.checkout_worktree("existing-branch", worktree_path, strategy)
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "add", str(worktree_path), "existing-branch"],
            cwd=Path("/repo")
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_checkout_worktree_pr(self, mock_run_cmd, mock_repo_root):
        """Test checking out PR to worktree."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        strategy = Mock()
        strategy.is_pr = True
        strategy.ref = "origin/pull/123/head"
        strategy.remote = "origin"
        
        operations.checkout_worktree("pr/123", worktree_path, strategy)
        
        # Should fetch PR and create worktree from FETCH_HEAD
        assert mock_run_cmd.call_count == 2
        mock_run_cmd.assert_any_call(
            ["git", "fetch", "origin", "pull/123/head"],
            cwd=Path("/repo"),
            suppress_output=True
        )
        mock_run_cmd.assert_any_call(
            ["git", "worktree", "add", str(worktree_path), "FETCH_HEAD"],
            cwd=Path("/repo")
        )

    @patch('par.operations.get_git_repo_root')
    @patch('par.operations.run_cmd')
    def test_checkout_worktree_with_remote_fetch(self, mock_run_cmd, mock_repo_root):
        """Test checking out with remote fetch."""
        mock_repo_root.return_value = Path("/repo")
        worktree_path = Path("/tmp/worktree")
        
        strategy = Mock()
        strategy.is_pr = False
        strategy.fetch_remote = True
        strategy.ref = "remote-branch"
        strategy.remote = "upstream"
        
        operations.checkout_worktree("remote-branch", worktree_path, strategy)
        
        # Should fetch from remote and create worktree
        assert mock_run_cmd.call_count == 2
        mock_run_cmd.assert_any_call(
            ["git", "fetch", "upstream"],
            cwd=Path("/repo"),
            suppress_output=True
        )
        mock_run_cmd.assert_any_call(
            ["git", "worktree", "add", str(worktree_path), "remote-branch"],
            cwd=Path("/repo")
        )


class TestTmuxOperations:
    """Test tmux operations."""

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_tmux_session_exists_true(self, mock_run_cmd, mock_check_tmux):
        """Test detecting existing tmux session."""
        mock_run_cmd.return_value = Mock(returncode=0)
        
        result = operations.tmux_session_exists("test-session")
        
        assert result is True
        mock_run_cmd.assert_called_once_with(
            ["tmux", "has-session", "-t", "test-session"],
            check=False,
            capture=True,
            suppress_output=True
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_tmux_session_exists_false(self, mock_run_cmd, mock_check_tmux):
        """Test detecting non-existent tmux session."""
        mock_run_cmd.return_value = Mock(returncode=1)
        
        result = operations.tmux_session_exists("nonexistent-session")
        
        assert result is False

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_tmux_session_exists_invalid_name(self, mock_run_cmd, mock_check_tmux):
        """Test session existence check with invalid name."""
        result = operations.tmux_session_exists("invalid session")
        
        assert result is False
        mock_run_cmd.assert_not_called()

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_create_tmux_session_success(self, mock_run_cmd, mock_check_tmux):
        """Test successful tmux session creation."""
        worktree_path = Path("/tmp/worktree")
        
        operations.create_tmux_session("test-session", worktree_path)
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "new-session", "-d", "-s", "test-session", "-c", str(worktree_path)]
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_create_tmux_session_invalid_name(self, mock_run_cmd, mock_check_tmux):
        """Test tmux session creation with invalid name."""
        with pytest.raises((SystemExit, Exception)):
            operations.create_tmux_session("invalid session", Path("/tmp/worktree"))
        
        mock_run_cmd.assert_not_called()

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_create_tmux_session_failure(self, mock_run_cmd, mock_check_tmux):
        """Test tmux session creation failure."""
        mock_run_cmd.side_effect = Exception("Session already exists")
        
        with pytest.raises((SystemExit, Exception)):
            operations.create_tmux_session("test-session", Path("/tmp/worktree"))

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_kill_tmux_session_success(self, mock_run_cmd, mock_check_tmux):
        """Test successful tmux session termination."""
        operations.kill_tmux_session("test-session")
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "kill-session", "-t", "test-session"],
            check=False,
            suppress_output=True
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_kill_tmux_session_invalid_name(self, mock_run_cmd, mock_check_tmux):
        """Test killing session with invalid name."""
        operations.kill_tmux_session("invalid session")
        
        mock_run_cmd.assert_not_called()

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_kill_tmux_session_failure_ignored(self, mock_run_cmd, mock_check_tmux):
        """Test tmux session termination failure is ignored."""
        mock_run_cmd.side_effect = Exception("Session doesn't exist")
        
        # Should not raise exception
        operations.kill_tmux_session("test-session")

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_send_tmux_keys_success(self, mock_run_cmd, mock_check_tmux):
        """Test sending keys to tmux session."""
        operations.send_tmux_keys("test-session", "echo hello")
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "send-keys", "-t", "test-session:0", "echo hello", "Enter"]
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_send_tmux_keys_custom_pane(self, mock_run_cmd, mock_check_tmux):
        """Test sending keys to specific pane."""
        operations.send_tmux_keys("test-session", "echo hello", "2")
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "send-keys", "-t", "test-session:2", "echo hello", "Enter"]
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_send_tmux_keys_invalid_session(self, mock_run_cmd, mock_check_tmux):
        """Test sending keys with invalid session name."""
        operations.send_tmux_keys("invalid session", "echo hello")
        
        mock_run_cmd.assert_not_called()

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_send_tmux_keys_invalid_pane(self, mock_run_cmd, mock_check_tmux):
        """Test sending keys with invalid pane."""
        operations.send_tmux_keys("test-session", "echo hello", "invalid")
        
        mock_run_cmd.assert_not_called()

    @patch('par.operations._check_tmux')
    @patch('par.operations.run_cmd')
    def test_send_tmux_keys_sanitizes_command(self, mock_run_cmd, mock_check_tmux):
        """Test command sanitization in send_tmux_keys."""
        operations.send_tmux_keys("test-session", "echo hello\0world")
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "send-keys", "-t", "test-session:0", "echo helloworld", "Enter"]
        )

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    @patch('par.operations.run_cmd')
    def test_open_tmux_session_outside_tmux(self, mock_run_cmd, mock_getenv, mock_check_tmux):
        """Test opening session from outside tmux."""
        mock_getenv.return_value = None  # Not inside tmux
        
        with patch('os.execvp') as mock_execvp:
            operations.open_tmux_session("test-session")
            
            mock_execvp.assert_called_once_with("tmux", ["tmux", "attach-session", "-t", "test-session"])

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    @patch('par.operations.run_cmd')
    def test_open_tmux_session_inside_tmux(self, mock_run_cmd, mock_getenv, mock_check_tmux):
        """Test switching session from inside tmux."""
        mock_getenv.return_value = "tmux-session"  # Inside tmux
        
        operations.open_tmux_session("test-session")
        
        mock_run_cmd.assert_called_once_with(
            ["tmux", "switch-client", "-t", "test-session"]
        )

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    def test_open_tmux_session_invalid_name(self, mock_getenv, mock_check_tmux):
        """Test opening session with invalid name."""
        with pytest.raises((SystemExit, Exception)):
            operations.open_tmux_session("invalid session")


class TestWorkspaceOperations:
    """Test workspace-specific operations."""

    @patch('par.operations.run_cmd')
    def test_create_workspace_worktree_success(self, mock_run_cmd):
        """Test creating worktree for workspace repo."""
        repo_path = Path("/workspace/frontend")
        worktree_path = Path("/tmp/worktree")
        
        operations.create_workspace_worktree(repo_path, "feature-branch", worktree_path)
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "add", "-b", "feature-branch", str(worktree_path)],
            cwd=repo_path
        )

    @patch('par.operations.run_cmd')
    def test_create_workspace_worktree_with_base(self, mock_run_cmd):
        """Test creating workspace worktree with base branch."""
        repo_path = Path("/workspace/frontend")
        worktree_path = Path("/tmp/worktree")
        
        operations.create_workspace_worktree(repo_path, "feature-branch", worktree_path, "develop")
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "add", "-b", "feature-branch", str(worktree_path), "develop"],
            cwd=repo_path
        )

    @patch('par.operations.run_cmd')
    def test_remove_workspace_worktree(self, mock_run_cmd):
        """Test removing workspace worktree."""
        repo_path = Path("/workspace/frontend")
        worktree_path = Path("/tmp/worktree")
        
        operations.remove_workspace_worktree(repo_path, worktree_path)
        
        mock_run_cmd.assert_called_once_with(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repo_path,
            suppress_output=True
        )

    @patch('par.operations.run_cmd')
    def test_delete_workspace_branch(self, mock_run_cmd):
        """Test deleting workspace branch."""
        repo_path = Path("/workspace/frontend")
        
        operations.delete_workspace_branch(repo_path, "feature-branch")
        
        mock_run_cmd.assert_called_once_with(
            ["git", "branch", "-D", "feature-branch"],
            cwd=repo_path,
            suppress_output=True
        )

    @patch('par.operations._check_tmux')
    @patch('par.operations.create_tmux_session')
    def test_create_workspace_tmux_session(self, mock_create_session, mock_check_tmux):
        """Test creating workspace tmux session."""
        repos_data = [
            {"worktree_path": "/tmp/workspace/frontend/feature-branch"},
            {"worktree_path": "/tmp/workspace/backend/feature-branch"}
        ]
        
        operations.create_workspace_tmux_session("workspace-session", repos_data)
        
        # Should create session in workspace root (parent of repo worktrees)
        expected_workspace_root = Path("/tmp/workspace")
        mock_create_session.assert_called_once_with("workspace-session", expected_workspace_root)

    @patch('par.operations._check_tmux')
    def test_create_workspace_tmux_session_no_repos(self, mock_check_tmux):
        """Test creating workspace session with no repos."""
        with pytest.raises((SystemExit, Exception)):
            operations.create_workspace_tmux_session("workspace-session", [])


class TestControlCenter:
    """Test control center functionality."""

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    @patch('par.operations.get_git_repo_root')
    @patch('par.utils.get_tmux_session_name')
    @patch('par.operations.tmux_session_exists')
    @patch('par.operations.create_tmux_session')
    @patch('par.operations.send_tmux_keys')
    @patch('par.operations.run_cmd')
    @patch('par.operations.open_tmux_session')
    def test_open_control_center_success(self, mock_open, mock_run_cmd, mock_send_keys, 
                                       mock_create_session, mock_session_exists, 
                                       mock_get_session_name, mock_repo_root, 
                                       mock_getenv, mock_check_tmux):
        """Test opening control center with sessions."""
        mock_getenv.return_value = None  # Not inside tmux
        mock_repo_root.return_value = Path("/repo")
        mock_get_session_name.return_value = "par-repo-abc1-cc"
        mock_session_exists.return_value = False
        
        sessions_data = [
            {
                "tmux_session_name": "par-repo-abc1-session1",
                "worktree_path": "/tmp/worktree1"
            },
            {
                "tmux_session_name": "par-repo-abc1-session2", 
                "worktree_path": "/tmp/worktree2"
            }
        ]
        
        operations.open_control_center(sessions_data)
        
        # Should create control center session
        mock_create_session.assert_called_once_with("par-repo-abc1-cc", Path("/tmp/worktree1"))
        
        # Should set up panes for each session
        assert mock_send_keys.call_count >= 2
        assert mock_run_cmd.call_count >= 2  # For split-window and select-layout
        
        # Should open the control center
        mock_open.assert_called_once_with("par-repo-abc1-cc")

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    def test_open_control_center_inside_tmux(self, mock_getenv, mock_check_tmux):
        """Test error when opening control center inside tmux."""
        mock_getenv.return_value = "current-session"  # Inside tmux
        
        with pytest.raises((SystemExit, Exception)):
            operations.open_control_center([])

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    def test_open_control_center_no_sessions(self, mock_getenv, mock_check_tmux):
        """Test control center with no sessions."""
        mock_getenv.return_value = None  # Not inside tmux
        
        # Should not raise error, just show message
        operations.open_control_center([])

    @patch('par.operations._check_tmux')
    @patch('os.getenv')
    @patch('par.operations.get_git_repo_root')
    @patch('par.utils.get_tmux_session_name')
    @patch('par.operations.tmux_session_exists')
    @patch('par.operations.open_tmux_session')
    def test_open_control_center_existing(self, mock_open, mock_session_exists,
                                        mock_get_session_name, mock_repo_root,
                                        mock_getenv, mock_check_tmux):
        """Test opening existing control center."""
        mock_getenv.return_value = None  # Not inside tmux
        mock_repo_root.return_value = Path("/repo")
        mock_get_session_name.return_value = "par-repo-abc1-cc"
        mock_session_exists.return_value = True  # Already exists
        
        sessions_data = [{"tmux_session_name": "par-repo-abc1-session1", "worktree_path": "/tmp/worktree1"}]
        
        operations.open_control_center(sessions_data)
        
        # Should attach to existing session
        mock_open.assert_called_once_with("par-repo-abc1-cc")


if __name__ == "__main__":
    print("✅ Git and tmux operations tests defined")
    print("Run with: pytest par/test_operations.py -v")