"""Git and tmux operations - simplified from git.py and tmux.py"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer

from .checkout import CheckoutStrategy
from .utils import get_git_repo_root, get_tmux_session_name, run_cmd


# Tmux utilities
def _check_tmux():
    """Ensure tmux is available and running."""
    try:
        run_cmd(
            ["tmux", "has-session"], check=False, capture=True, suppress_output=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        typer.secho("Error: tmux not available or not running.", fg="red", err=True)
        raise typer.Exit(1)


def get_current_tmux_session() -> Optional[str]:
    """Get the name of the current tmux session, if inside tmux."""
    if not os.getenv("TMUX"):
        return None
    try:
        result = run_cmd(
            ["tmux", "display-message", "-p", "#S"], 
            capture=True, 
            suppress_output=True
        )
        return result.stdout.strip() if result.stdout else None
    except subprocess.CalledProcessError:
        return None


# Git operations
def create_worktree(label: str, worktree_path: Path, repo_root: Optional[Path] = None, base_branch: Optional[str] = None):
    """Create a new git worktree and branch."""
    if repo_root is None:
        repo_root = get_git_repo_root()

    cmd = ["git", "worktree", "add", "-b", label, str(worktree_path)]
    if base_branch:
        cmd.append(base_branch)

    try:
        run_cmd(cmd, cwd=repo_root)
        typer.secho(f"Created worktree '{label}' at {worktree_path}", fg="green")
    except Exception as e:
        typer.secho(f"Failed to create worktree '{label}': {e}", fg="red", err=True)
        raise typer.Exit(1)


def remove_worktree(worktree_path: Path, repo_root: Optional[Path] = None):
    """Remove a git worktree."""
    if repo_root is None:
        repo_root = get_git_repo_root()

    cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]

    try:
        run_cmd(cmd, cwd=repo_root, suppress_output=True)
        typer.secho(f"Removed worktree at {worktree_path}", fg="green")
    except Exception:
        # Often fails if path doesn't exist - that's OK during cleanup
        pass


def checkout_worktree(
    branch_name: str, worktree_path: Path, strategy: CheckoutStrategy, repo_root: Optional[Path] = None
):
    """Create worktree from existing branch."""
    if repo_root is None:
        repo_root = get_git_repo_root()

    pr_number = ""
    # Handle PR fetching specially
    if strategy.is_pr:
        try:
            # Extract PR number from ref like "origin/pull/123/head"
            pr_number = strategy.ref.split("/")[2]
            typer.secho(f"Fetching PR #{pr_number}...", fg="cyan")

            # Fetch the specific PR ref
            fetch_cmd = ["git", "fetch", strategy.remote, f"pull/{pr_number}/head"]
            run_cmd(fetch_cmd, cwd=repo_root, suppress_output=True)

            # Create worktree directly from FETCH_HEAD (what we just fetched)
            cmd = ["git", "worktree", "add", str(worktree_path), "FETCH_HEAD"]

        except Exception as e:
            typer.secho(f"Failed to fetch PR #{pr_number}: {e}", fg="red", err=True)
            typer.echo(f"Make sure PR #{pr_number} exists and is accessible.")
            raise typer.Exit(1)
    elif strategy.fetch_remote:
        try:
            typer.secho(f"Fetching from remote '{strategy.remote}'...", fg="cyan")
            run_cmd(
                ["git", "fetch", strategy.remote], cwd=repo_root, suppress_output=True
            )
        except Exception as e:
            typer.secho(
                f"Warning: Could not fetch from '{strategy.remote}': {e}", fg="yellow"
            )
            # Continue anyway - the branch might already exist locally

        # Create worktree from existing ref
        cmd = ["git", "worktree", "add", str(worktree_path), strategy.ref]
    else:
        # Create worktree from existing ref
        cmd = ["git", "worktree", "add", str(worktree_path), strategy.ref]

    try:
        run_cmd(cmd, cwd=repo_root)
        if strategy.is_pr:
            typer.secho(f"Checked out PR #{pr_number} to {worktree_path}", fg="green")
        else:
            typer.secho(f"Checked out '{strategy.ref}' to {worktree_path}", fg="green")
    except Exception as e:
        if strategy.is_pr:
            typer.secho(f"Failed to checkout PR #{pr_number}: {e}", fg="red", err=True)
        else:
            typer.secho(f"Failed to checkout '{strategy.ref}': {e}", fg="red", err=True)
        raise typer.Exit(1)


def delete_branch(branch_name: str, repo_root: Optional[Path] = None):
    """Delete a git branch."""
    if repo_root is None:
        repo_root = get_git_repo_root()

    cmd = ["git", "branch", "-D", branch_name]

    try:
        run_cmd(cmd, cwd=repo_root, suppress_output=True)
        typer.secho(f"Deleted branch '{branch_name}'", fg="green")
    except Exception:
        # Often fails if branch doesn't exist - that's OK during cleanup
        pass


# Tmux operations
def tmux_session_exists(session_name: str) -> bool:
    """Check if a tmux session exists."""
    _check_tmux()
    result = run_cmd(
        ["tmux", "has-session", "-t", session_name],
        check=False,
        capture=True,
        suppress_output=True,
    )
    return result.returncode == 0


def create_tmux_session(session_name: str, worktree_path: Path):
    """Create a new detached tmux session."""
    _check_tmux()
    cmd = ["tmux", "new-session", "-d", "-s", session_name, "-c", str(worktree_path)]

    try:
        run_cmd(cmd)
        typer.secho(f"Created tmux session '{session_name}'", fg="green")
    except Exception as e:
        typer.secho(
            f"Failed to create tmux session '{session_name}': {e}", fg="red", err=True
        )
        raise typer.Exit(1)


def kill_tmux_session(session_name: str):
    """Kill a tmux session."""
    _check_tmux()
    cmd = ["tmux", "kill-session", "-t", session_name]

    try:
        run_cmd(cmd, check=False, suppress_output=True)
    except Exception:
        # Session might not exist - that's fine during cleanup
        pass


def send_tmux_keys(session_name: str, command: str, pane: str = "0"):
    """Send keys (command) to a tmux session."""
    _check_tmux()
    target = f"{session_name}:{pane}"
    cmd = ["tmux", "send-keys", "-t", target, command, "Enter"]

    try:
        run_cmd(cmd)
        typer.secho(f"Sent command to session '{session_name}'", fg="cyan")
    except Exception as e:
        typer.secho(f"Failed to send command: {e}", fg="red", err=True)


def open_tmux_session(session_name: str):
    """Attach to or switch to a tmux session."""
    _check_tmux()

    if os.getenv("TMUX"):  # Inside tmux
        typer.echo(f"Switching to session '{session_name}'...")
        run_cmd(["tmux", "switch-client", "-t", session_name])
    else:  # Outside tmux
        typer.echo(f"Attaching to session '{session_name}'...")
        try:
            os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])
        except Exception as e:
            typer.secho(f"Failed to attach to session: {e}", fg="red", err=True)
            raise typer.Exit(1)


def _update_control_center_windows(session_name: str, contexts_data: List[dict]):
    """Update control center windows to match current contexts."""
    # Get current windows in the control center session
    try:
        result = run_cmd([
            "tmux", "list-windows", "-t", session_name, "-F", "#{window_index}:#{window_name}"
        ], capture=True)
        current_windows = {}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                index, name = line.split(':', 1)
                current_windows[name] = int(index)
    except Exception:
        # If we can't get windows, fall back to recreating the session
        run_cmd(["tmux", "kill-session", "-t", session_name], check=False)
        return False

    # Build expected windows from contexts
    expected_windows = {context["name"]: context for context in contexts_data}

    # Remove windows that no longer exist
    for window_name, window_index in current_windows.items():
        if window_name not in expected_windows:
            try:
                run_cmd(["tmux", "kill-window", "-t", f"{session_name}:{window_index}"])
            except Exception:
                pass  # Window might already be gone

    # Add or update windows for current contexts
    existing_names = set(current_windows.keys())
    for i, context in enumerate(contexts_data):
        if context["name"] not in existing_names:
            # Create new window
            run_cmd([
                "tmux", "new-window", "-t", session_name,
                "-n", context["name"], "-c", context["path"]
            ])
        # If window exists, we could update its working directory, but tmux doesn't
        # have a direct command for this. The window will retain its original path.

    # Ensure we have at least one window and select the first one
    if contexts_data:
        run_cmd(["tmux", "select-window", "-t", f"{session_name}:^"], check=False)

    return True


def open_control_center(contexts_data: List[dict]):
    """Create a new 'control-center' tmux session with separate windows for each context."""
    _check_tmux()

    if os.getenv("TMUX"):
        typer.secho(
            "Error: Control center must be run outside tmux.", fg="red", err=True
        )
        raise typer.Exit(1)

    if not contexts_data:
        typer.secho("No sessions to display.", fg="yellow")
        return

    cc_session_name = "control-center"

    # Check if control center already exists
    if tmux_session_exists(cc_session_name):
        typer.secho(
            f"Updating existing control center '{cc_session_name}' with current sessions", fg="cyan"
        )
        if _update_control_center_windows(cc_session_name, contexts_data):
            open_tmux_session(cc_session_name)
            return
        # If update failed, fall through to recreate the session

    # Create new control center session with first context
    first_context = contexts_data[0]
    create_tmux_session(cc_session_name, Path(first_context["path"]))

    # Rename first window
    run_cmd([
        "tmux", "rename-window", "-t", f"{cc_session_name}:0", first_context["name"]
    ])

    # Create additional windows for remaining contexts
    for context in contexts_data[1:]:
        run_cmd([
            "tmux", "new-window", "-t", cc_session_name,
            "-n", context["name"], "-c", context["path"]
        ])

    # Select window 0 before attaching
    run_cmd(["tmux", "select-window", "-t", f"{cc_session_name}:0"])

    typer.secho(f"Created control center with {len(contexts_data)} windows.", fg="green")
    open_tmux_session(cc_session_name)


def create_workspace_worktree(
    repo_path: Path, label: str, worktree_path: Path, base_branch: Optional[str] = None
):
    """Create a new git worktree and branch for a specific repo in workspace."""
    cmd = ["git", "worktree", "add", "-b", label, str(worktree_path)]
    if base_branch:
        cmd.append(base_branch)

    try:
        run_cmd(cmd, cwd=repo_path)
        typer.secho(
            f"Created worktree '{label}' at {worktree_path} for {repo_path.name}",
            fg="green",
        )
    except Exception as e:
        typer.secho(
            f"Failed to create worktree '{label}' for {repo_path.name}: {e}",
            fg="red",
            err=True,
        )
        raise typer.Exit(1)


def remove_workspace_worktree(repo_path: Path, worktree_path: Path):
    """Remove a git worktree for a specific repo in workspace."""
    cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]

    try:
        run_cmd(cmd, cwd=repo_path, suppress_output=True)
        typer.secho(
            f"Removed worktree at {worktree_path} for {repo_path.name}", fg="green"
        )
    except Exception:
        # Often fails if path doesn't exist - that's OK during cleanup
        pass


def delete_workspace_branch(repo_path: Path, branch_name: str):
    """Delete a git branch for a specific repo in workspace."""
    cmd = ["git", "branch", "-D", branch_name]

    try:
        run_cmd(cmd, cwd=repo_path, suppress_output=True)
        typer.secho(f"Deleted branch '{branch_name}' in {repo_path.name}", fg="green")
    except Exception:
        # Often fails if branch doesn't exist - that's OK during cleanup
        pass


def create_workspace_tmux_session(session_name: str, repos_data: List[dict]):
    """Create a workspace tmux session in the workspace root directory."""
    _check_tmux()

    if not repos_data:
        typer.secho("No repos provided for workspace session.", fg="red", err=True)
        raise typer.Exit(1)

    # Get workspace root directory (parent of all repo worktrees)
    first_worktree_path = Path(repos_data[0]["worktree_path"])
    workspace_root = first_worktree_path.parent.parent

    # Create session in workspace root directory
    create_tmux_session(session_name, workspace_root)

    typer.secho(
        f"Created workspace session '{session_name}' in workspace root.", fg="green"
    )
