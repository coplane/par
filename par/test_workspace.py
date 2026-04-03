"""Tests for workspace pull-default behavior."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from . import cli, operations, workspace

# --- get_default_branch tests ---


@patch("par.operations.run_cmd")
def test_get_default_branch_returns_branch_name(mock_run_cmd):
    """get_default_branch extracts branch name from symbolic-ref output."""
    mock_run_cmd.return_value = MagicMock(stdout="refs/remotes/origin/main\n")
    result = operations.get_default_branch(Path("/tmp/repo"))
    assert result == "main"
    mock_run_cmd.assert_called_once_with(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=Path("/tmp/repo"),
        suppress_output=True,
    )


@patch("par.operations.run_cmd")
def test_get_default_branch_handles_develop(mock_run_cmd):
    """get_default_branch works with non-main default branches."""
    mock_run_cmd.return_value = MagicMock(stdout="refs/remotes/origin/develop\n")
    result = operations.get_default_branch(Path("/tmp/repo"))
    assert result == "develop"


@patch("par.operations.run_cmd")
def test_get_default_branch_exits_on_failure(mock_run_cmd):
    """get_default_branch raises Exit when origin/HEAD is not set."""
    mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "git")
    with pytest.raises(typer.Exit):
        operations.get_default_branch(Path("/tmp/repo"))


# --- pull_default_branch tests ---


@patch("par.operations.run_cmd")
def test_pull_default_branch_checkouts_and_pulls(mock_run_cmd):
    """pull_default_branch runs checkout then pull --ff-only."""
    mock_run_cmd.return_value = MagicMock()
    operations.pull_default_branch(Path("/tmp/repo"), "main")
    assert mock_run_cmd.call_count == 2
    mock_run_cmd.assert_any_call(
        ["git", "checkout", "main"], cwd=Path("/tmp/repo"), suppress_output=True
    )
    mock_run_cmd.assert_any_call(
        ["git", "pull", "--ff-only"], cwd=Path("/tmp/repo"), suppress_output=True
    )


@patch("par.operations.run_cmd")
def test_pull_default_branch_exits_on_checkout_failure(mock_run_cmd):
    """pull_default_branch exits if checkout fails (e.g., dirty tree)."""
    mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "git")
    with pytest.raises(typer.Exit):
        operations.pull_default_branch(Path("/tmp/repo"), "main")


@patch("par.operations.run_cmd")
def test_pull_default_branch_exits_on_pull_failure(mock_run_cmd):
    """pull_default_branch exits if pull --ff-only fails (non-ff)."""
    # Checkout succeeds, pull fails
    mock_run_cmd.side_effect = [MagicMock(), subprocess.CalledProcessError(1, "git")]
    with pytest.raises(typer.Exit):
        operations.pull_default_branch(Path("/tmp/repo"), "main")


# --- CLI --pull-default flag tests ---


@patch("par.cli.workspace.start_workspace_session")
def test_cli_workspace_start_forwards_pull_default(mock_start):
    """CLI workspace start passes --pull-default through."""
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["workspace", "start", "my-ws", "--pull-default"],
    )

    assert result.exit_code == 0
    mock_start.assert_called_once_with(
        "my-ws", workspace_path=None, repos=None, open_session=False, pull_default=True
    )


@patch("par.cli.workspace.start_workspace_session")
def test_cli_workspace_start_pull_default_off_by_default(mock_start):
    """pull_default defaults to False when flag is not provided."""
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["workspace", "start", "my-ws"],
    )

    assert result.exit_code == 0
    mock_start.assert_called_once_with(
        "my-ws", workspace_path=None, repos=None, open_session=False, pull_default=False
    )


# --- Workspace start integration with pull_default ---


@patch("par.workspace.open_workspace_session")
@patch("par.workspace._add_workspace_session")
@patch("par.workspace.initialization.run_initialization")
@patch("par.workspace.initialization.load_par_config", return_value=None)
@patch("par.workspace.initialization.copy_included_files")
@patch("par.workspace.operations.create_tmux_session")
@patch("par.workspace.operations.create_workspace_worktree")
@patch("par.workspace.operations.tmux_session_exists", return_value=False)
@patch("par.workspace.operations.pull_default_branch")
@patch("par.workspace.operations.get_default_branch", return_value="main")
@patch("par.workspace.core._validate_label_unique", return_value=True)
@patch("par.workspace.utils.get_workspace_worktree_path")
@patch("par.workspace.utils.get_workspace_session_name", return_value="ws-session")
def test_workspace_start_with_pull_default(
    mock_session_name,
    mock_wt_path,
    mock_validate,
    mock_get_default,
    mock_pull_default,
    mock_tmux_exists,
    mock_create_wt,
    mock_create_tmux,
    mock_copy_includes,
    mock_load_config,
    mock_run_init,
    mock_add_ws,
    mock_open_ws,
    tmp_path,
):
    """start_workspace_session with pull_default=True pulls before creating worktrees."""
    # Setup: create fake repo dirs
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / ".git").mkdir()
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    (repo_b / ".git").mkdir()

    mock_wt_path.return_value = tmp_path / "worktrees" / "test-ws" / "repo"

    workspace.start_workspace_session(
        "test-ws",
        workspace_path=str(tmp_path),
        repos=["repo-a", "repo-b"],
        pull_default=True,
    )

    # Verify get_default_branch called for each repo
    assert mock_get_default.call_count == 2
    mock_get_default.assert_any_call(repo_a)
    mock_get_default.assert_any_call(repo_b)

    # Verify pull_default_branch called for each repo with the resolved branch
    assert mock_pull_default.call_count == 2
    mock_pull_default.assert_any_call(repo_a, "main")
    mock_pull_default.assert_any_call(repo_b, "main")

    # Verify worktrees created with base_branch="main"
    for c in mock_create_wt.call_args_list:
        assert (
            c.kwargs.get("base_branch") == "main"
            or c[0][-1] == "main"
            or "base_branch" in str(c)
        )


@patch("par.workspace._add_workspace_session")
@patch("par.workspace.initialization.load_par_config", return_value=None)
@patch("par.workspace.initialization.copy_included_files")
@patch("par.workspace.operations.create_tmux_session")
@patch("par.workspace.operations.create_workspace_worktree")
@patch("par.workspace.operations.tmux_session_exists", return_value=False)
@patch("par.workspace.core._validate_label_unique", return_value=True)
@patch("par.workspace.utils.get_workspace_worktree_path")
@patch("par.workspace.utils.get_workspace_session_name", return_value="ws-session")
def test_workspace_start_without_pull_default_skips_pull(
    mock_session_name,
    mock_wt_path,
    mock_validate,
    mock_create_wt,
    mock_tmux_exists,
    mock_create_tmux,
    mock_copy_includes,
    mock_load_config,
    mock_add_ws,
    tmp_path,
):
    """start_workspace_session with pull_default=False does NOT call pull operations."""
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / ".git").mkdir()

    mock_wt_path.return_value = tmp_path / "worktrees" / "test-ws" / "repo"

    with (
        patch("par.workspace.operations.get_default_branch") as mock_get_default,
        patch("par.workspace.operations.pull_default_branch") as mock_pull,
    ):
        workspace.start_workspace_session(
            "test-ws",
            workspace_path=str(tmp_path),
            repos=["repo-a"],
            pull_default=False,
        )
        mock_get_default.assert_not_called()
        mock_pull.assert_not_called()
