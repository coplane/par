from pathlib import Path
from typing import Optional

import typer

from .utils import get_git_repo_root, run_cmd


def create_worktree(label: str, worktree_path: Path, base_branch: Optional[str] = None):
    """Creates a new git worktree and a branch with the same name as the label."""
    repo_root = get_git_repo_root()
    cmd = ["git", "worktree", "add", "-b", label, str(worktree_path)]
    if base_branch:  # if you want to branch off a specific commit/branch
        cmd.append(base_branch)

    try:
        run_cmd(cmd, cwd=repo_root)
        typer.secho(
            f"Git worktree '{label}' created at '{worktree_path}' on new branch '{label}'.",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(
            f"Failed to create git worktree '{label}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def remove_worktree(worktree_path: Path, force: bool = True):
    """Removes a git worktree."""
    repo_root = (
        get_git_repo_root()
    )  # Assuming command needs to be run from main repo for context
    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(worktree_path))
    try:
        run_cmd(
            cmd, cwd=repo_root, suppress_output=True
        )  # Suppress git's noisy output on success
        typer.secho(
            f"Git worktree at '{worktree_path}' removed.", fg=typer.colors.GREEN
        )
    except Exception as e:
        # It might fail if the path doesn't exist or isn't a worktree; often ok during cleanup.
        typer.secho(
            f"Note: Could not remove git worktree at '{worktree_path}': {e}",
            fg=typer.colors.YELLOW,
            err=True,
        )


def delete_branch(branch_name: str, force: bool = True):
    """Deletes a git branch."""
    repo_root = get_git_repo_root()
    cmd = ["git", "branch"]
    cmd.append("-D" if force else "-d")
    cmd.append(branch_name)
    try:
        run_cmd(cmd, cwd=repo_root, suppress_output=True)
        typer.secho(f"Git branch '{branch_name}' deleted.", fg=typer.colors.GREEN)
    except Exception as e:
        # It might fail if branch doesn't exist or has unmerged changes (if not force)
        typer.secho(
            f"Note: Could not delete git branch '{branch_name}': {e}",
            fg=typer.colors.YELLOW,
            err=True,
        )
