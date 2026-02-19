"""Tests for par start behavior."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from . import cli, core, operations


@patch("par.cli.core.start_session")
def test_cli_start_forwards_base_branch(mock_start_session):
    """CLI start passes --base through to core.start_session."""
    cli.start(
        label="feature-auth",
        path="/tmp/repo",
        base_branch="develop",
        open_session=True,
    )

    mock_start_session.assert_called_once_with(
        "feature-auth",
        repo_path="/tmp/repo",
        open_session=True,
        base_branch="develop",
    )


@patch("par.cli.core.start_session")
def test_cli_create_alias_forwards_base_branch(mock_start_session):
    """CLI create alias passes args through to core.start_session via start."""
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["create", "feature-auth", "--path", "/tmp/repo", "--base", "develop", "--open"],
    )

    assert result.exit_code == 0
    mock_start_session.assert_called_once_with(
        "feature-auth",
        repo_path="/tmp/repo",
        open_session=True,
        base_branch="develop",
    )


@patch("par.core._add_session")
@patch("par.core.initialization.load_par_config", return_value=None)
@patch("par.core.operations.create_tmux_session")
@patch("par.core.operations.create_worktree")
@patch("par.core.operations.fetch_remote_branch", return_value=False)
@patch("par.core.operations.branch_exists", return_value=False)
@patch("par.core.operations.tmux_session_exists", return_value=False)
@patch("par.core.utils.get_tmux_session_name", return_value="par-repo-1234-feature")
@patch("par.core.utils.get_worktree_path", return_value=Path("/tmp/worktree"))
@patch("par.core.utils.resolve_repository_path", return_value=Path("/tmp/repo"))
@patch("par.core._validate_label_unique", return_value=True)
def test_start_session_passes_base_branch(
    _mock_label_unique,
    _mock_resolve_repo,
    _mock_get_worktree_path,
    _mock_get_tmux_name,
    _mock_tmux_exists,
    _mock_branch_exists,
    _mock_fetch_remote,
    mock_create_worktree,
    _mock_create_tmux,
    _mock_load_config,
    _mock_add_session,
):
    """Core start session forwards base branch to worktree creation."""
    core.start_session("feature-auth", base_branch="develop")

    mock_create_worktree.assert_called_once_with(
        "feature-auth",
        Path("/tmp/worktree"),
        Path("/tmp/repo"),
        base_branch="develop",
        create_branch=True,
    )


@patch("par.operations.run_cmd")
def test_create_worktree_uses_resolved_base_commit(mock_run_cmd):
    """Worktree creation resolves base ref to commit SHA before branching."""
    mock_run_cmd.side_effect = [
        subprocess.CompletedProcess(
            args=["git", "rev-parse"], returncode=0, stdout="abc123\n", stderr=""
        ),
        subprocess.CompletedProcess(
            args=["git", "worktree", "add"], returncode=0, stdout="", stderr=""
        ),
    ]

    operations.create_worktree(
        "feature-auth",
        Path("/tmp/worktree"),
        repo_root=Path("/tmp/repo"),
        base_branch="develop",
    )

    first_call = mock_run_cmd.call_args_list[0]
    assert first_call.args[0] == ["git", "rev-parse", "--verify", "develop^{commit}"]
    assert first_call.kwargs["cwd"] == Path("/tmp/repo")
    assert first_call.kwargs["suppress_output"] is True

    second_call = mock_run_cmd.call_args_list[1]
    assert second_call.args[0] == [
        "git",
        "worktree",
        "add",
        "-b",
        "feature-auth",
        "/tmp/worktree",
        "abc123",
    ]
    assert second_call.kwargs["cwd"] == Path("/tmp/repo")


@patch("par.operations.run_cmd")
def test_create_worktree_without_base_branch(mock_run_cmd):
    """Worktree creation does not resolve base ref when not requested."""
    mock_run_cmd.return_value = subprocess.CompletedProcess(
        args=["git", "worktree", "add"], returncode=0, stdout="", stderr=""
    )

    operations.create_worktree(
        "feature-auth",
        Path("/tmp/worktree"),
        repo_root=Path("/tmp/repo"),
    )

    mock_run_cmd.assert_called_once_with(
        ["git", "worktree", "add", "-b", "feature-auth", "/tmp/worktree"],
        cwd=Path("/tmp/repo"),
    )


@patch("par.operations.run_cmd")
def test_create_worktree_existing_branch(mock_run_cmd):
    """Existing branch uses worktree add without -b."""
    mock_run_cmd.return_value = subprocess.CompletedProcess(
        args=["git", "worktree", "add"], returncode=0, stdout="", stderr=""
    )

    operations.create_worktree(
        "feature-auth",
        Path("/tmp/worktree"),
        repo_root=Path("/tmp/repo"),
        create_branch=False,
    )

    mock_run_cmd.assert_called_once_with(
        ["git", "worktree", "add", "/tmp/worktree", "feature-auth"],
        cwd=Path("/tmp/repo"),
    )


@patch("par.operations.run_cmd")
def test_create_worktree_retries_when_branch_already_exists(mock_run_cmd):
    """If -b fails with 'already exists', retry as checkout existing branch."""
    mock_run_cmd.side_effect = [
        subprocess.CalledProcessError(
            returncode=255,
            cmd=["git", "worktree", "add", "-b", "feature-auth", "/tmp/worktree"],
            stderr="fatal: a branch named 'feature-auth' already exists",
        ),
        subprocess.CompletedProcess(
            args=["git", "worktree", "add"], returncode=0, stdout="", stderr=""
        ),
    ]

    operations.create_worktree(
        "feature-auth",
        Path("/tmp/worktree"),
        repo_root=Path("/tmp/repo"),
        create_branch=True,
    )

    assert mock_run_cmd.call_count == 2
    second_call = mock_run_cmd.call_args_list[1]
    assert second_call.args[0] == [
        "git",
        "worktree",
        "add",
        "/tmp/worktree",
        "feature-auth",
    ]


@patch("par.core._add_session")
@patch("par.core.initialization.load_par_config", return_value=None)
@patch("par.core.operations.create_tmux_session")
@patch("par.core.operations.create_worktree")
@patch("par.core.operations.fetch_remote_branch", return_value=False)
@patch("par.core.operations.branch_exists", return_value=True)
@patch("par.core.operations.tmux_session_exists", return_value=False)
@patch("par.core.utils.get_tmux_session_name", return_value="par-repo-1234-feature")
@patch("par.core.utils.get_worktree_path", return_value=Path("/tmp/worktree"))
@patch("par.core.utils.resolve_repository_path", return_value=Path("/tmp/repo"))
@patch("par.core._validate_label_unique", return_value=True)
def test_start_session_existing_branch_uses_checkout_mode(
    _mock_label_unique,
    _mock_resolve_repo,
    _mock_get_worktree_path,
    _mock_get_tmux_name,
    _mock_tmux_exists,
    _mock_branch_exists,
    _mock_fetch_remote,
    mock_create_worktree,
    _mock_create_tmux,
    _mock_load_config,
    _mock_add_session,
):
    """If label already exists as branch, start checks out that branch in new worktree."""
    core.start_session("feature-auth", base_branch="develop")

    mock_create_worktree.assert_called_once_with(
        "feature-auth",
        Path("/tmp/worktree"),
        Path("/tmp/repo"),
        base_branch=None,
        create_branch=False,
    )


@patch("par.core._add_session")
@patch("par.core.initialization.load_par_config", return_value=None)
@patch("par.core.operations.create_tmux_session")
@patch("par.core.operations.create_worktree")
@patch("par.core.operations.fetch_remote_branch", return_value=True)
@patch("par.core.operations.branch_exists", return_value=False)
@patch("par.core.operations.tmux_session_exists", return_value=False)
@patch("par.core.utils.get_tmux_session_name", return_value="par-repo-1234-feature")
@patch("par.core.utils.get_worktree_path", return_value=Path("/tmp/worktree"))
@patch("par.core.utils.resolve_repository_path", return_value=Path("/tmp/repo"))
@patch("par.core._validate_label_unique", return_value=True)
def test_start_session_existing_remote_branch_fetches_and_checks_out(
    _mock_label_unique,
    _mock_resolve_repo,
    _mock_get_worktree_path,
    _mock_get_tmux_name,
    _mock_tmux_exists,
    _mock_branch_exists,
    _mock_fetch_remote,
    mock_create_worktree,
    _mock_create_tmux,
    _mock_load_config,
    _mock_add_session,
):
    """If label exists on origin, start branches from origin/<label>."""
    core.start_session("feature-auth")

    mock_create_worktree.assert_called_once_with(
        "feature-auth",
        Path("/tmp/worktree"),
        Path("/tmp/repo"),
        base_branch="origin/feature-auth",
        create_branch=True,
    )


@patch("par.operations.run_cmd")
def test_fetch_remote_branch_success(mock_run_cmd):
    """Fetching an existing remote branch returns True."""
    mock_run_cmd.return_value = subprocess.CompletedProcess(
        args=["git", "fetch"], returncode=0, stdout="", stderr=""
    )

    assert operations.fetch_remote_branch("feature-auth", Path("/tmp/repo")) is True
    mock_run_cmd.assert_called_once_with(
        ["git", "fetch", "origin", "feature-auth"],
        cwd=Path("/tmp/repo"),
        suppress_output=True,
    )


@patch("par.operations.run_cmd", side_effect=Exception("missing"))
def test_fetch_remote_branch_missing(_mock_run_cmd):
    """Fetching a missing remote branch returns False."""
    assert operations.fetch_remote_branch("feature-auth", Path("/tmp/repo")) is False
