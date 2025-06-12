"""Core business logic for par - simplified from actions.py and manager.py"""

import datetime
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import checkout, initialization, operations, utils
from .constants import SessionStatus
from .state_manager import get_session_state_manager


def _get_repo_key() -> str:
    return str(utils.get_git_repo_root().resolve())


def _get_repo_sessions() -> Dict[str, Any]:
    state_manager = get_session_state_manager()
    repo_key = _get_repo_key()
    return state_manager.get_scoped_data(repo_key)


def _update_repo_sessions(sessions: Dict[str, Any]):
    state_manager = get_session_state_manager()
    repo_key = _get_repo_key()
    state_manager.update_scoped_data(repo_key, sessions)


def _update_session_status(
    label: str, status: str, initialized_at: Optional[str] = None
):
    """Update the status of a specific session."""
    sessions = _get_repo_sessions()
    if label in sessions:
        sessions[label]["status"] = status
        if initialized_at:
            sessions[label]["initialized_at"] = initialized_at
        _update_repo_sessions(sessions)


# Session operations - simplified from actions.py
def start_session(label: str, open_session: bool = False):
    """Start a new git worktree and tmux session."""
    sessions = _get_repo_sessions()

    if label in sessions:
        typer.secho(f"Error: Session '{label}' already exists.", fg="red", err=True)
        raise typer.Exit(1)

    repo_root = utils.get_git_repo_root()
    worktree_path = utils.get_worktree_path(repo_root, label)
    session_name = utils.get_tmux_session_name(repo_root, label)

    # Check for conflicts
    if worktree_path.exists():
        typer.secho(
            f"Error: Worktree path '{worktree_path}' exists.", fg="red", err=True
        )
        raise typer.Exit(1)

    if operations.tmux_session_exists(session_name):
        typer.secho(f"Error: tmux session '{session_name}' exists.", fg="red", err=True)
        raise typer.Exit(1)

    # Create resources
    operations.create_worktree(label, worktree_path)
    operations.create_tmux_session(session_name, worktree_path)

    # Run initialization if .par.yaml exists
    config = initialization.load_par_config(repo_root)
    if config:
        initialization.run_initialization(config, session_name, worktree_path)

    # Update state with status
    sessions[label] = {
        "worktree_path": str(worktree_path),
        "tmux_session_name": session_name,
        "branch_name": label,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "status": SessionStatus.INITIALIZING,
        "initialized_at": None,
    }
    _update_repo_sessions(sessions)

    typer.secho(
        f"Successfully started session '{label}'.", fg="bright_green", bold=True
    )
    typer.echo(f"  Worktree: {worktree_path}")
    typer.echo(f"  Branch: {label}")
    typer.echo(f"  Session: {session_name}")

    # Send welcome message to tmux session
    operations.send_tmux_keys(session_name, "par welcome")

    # Mark session as ready
    _update_session_status(
        label, SessionStatus.READY, datetime.datetime.now(datetime.UTC).isoformat()
    )

    if open_session:
        typer.echo("Opening session...")
        operations.open_tmux_session(session_name)
    else:
        typer.echo(f"To open: par open {label}")


def remove_session(label: str):
    """Remove a session and clean up all resources."""
    sessions = _get_repo_sessions()
    session_data = sessions.get(label)

    if not session_data:
        # Attempt cleanup of stale resources
        typer.secho(f"Warning: Session '{label}' not found in state.", fg="yellow")
        typer.echo("Attempting cleanup of stale artifacts...")
        _cleanup_stale_resources(label)
        return

    # Clean up resources
    operations.kill_tmux_session(session_data["tmux_session_name"])
    operations.remove_worktree(Path(session_data["worktree_path"]))

    # Only delete branch if it was created by par (not checkout)
    if not session_data.get("is_checkout", False):
        operations.delete_branch(session_data["branch_name"])

    # Remove physical directory if it exists and is managed by par
    worktree_path = Path(session_data["worktree_path"])
    if worktree_path.exists() and utils.get_data_dir() in worktree_path.parents:
        try:
            shutil.rmtree(worktree_path)
        except OSError as e:
            typer.secho(
                f"Warning: Could not remove directory {worktree_path}: {e}", fg="yellow"
            )

    # Update state
    del sessions[label]
    _update_repo_sessions(sessions)

    typer.secho(
        f"Successfully removed session '{label}'.", fg="bright_green", bold=True
    )


def _cleanup_stale_resources(label: str):
    """Clean up stale resources that might exist without state."""
    repo_root = utils.get_git_repo_root()
    stale_worktree = utils.get_worktree_path(repo_root, label)
    stale_session = utils.get_tmux_session_name(repo_root, label)

    operations.kill_tmux_session(stale_session)
    operations.remove_worktree(stale_worktree)
    operations.delete_branch(label)

    typer.secho(f"Cleanup attempt for '{label}' finished.", fg="cyan")


def remove_all_sessions():
    """Remove all sessions for the current repository."""
    sessions = _get_repo_sessions()

    if not sessions:
        typer.secho("No sessions to remove.", fg="yellow")
        return

    typer.confirm(f"Remove all {len(sessions)} sessions?", abort=True)

    for label in list(sessions.keys()):
        typer.echo(f"Removing session '{label}'...")
        remove_session(label)

    typer.secho("All sessions removed.", fg="bright_green", bold=True)


def send_command(target: str, command: str):
    """Send a command to session(s) or workspace(s)."""

    # First check if it's a workspace (search ALL workspaces, not just current dir)
    workspace_found = False
    if target.lower() != "all":
        # Search all workspaces across all directories
        state_file = utils.get_data_dir() / "workspaces.json"
        if state_file.exists():
            try:
                import json

                with open(state_file, "r") as f:
                    all_workspaces = json.loads(f.read().strip() or "{}")

                # Search through all workspace directories
                for workspace_root, workspace_data in all_workspaces.items():
                    if target in workspace_data:
                        ws_info = workspace_data[target]
                        session_name = ws_info["session_name"]
                        typer.echo(f"Sending to workspace '{target}'...")
                        operations.send_tmux_keys(session_name, command)
                        typer.secho(
                            f"Sent command to workspace session '{session_name}'",
                            fg="green",
                        )
                        workspace_found = True
                        break
            except Exception:
                # Continue to single-repo logic if workspace search fails
                pass

    if workspace_found:
        return

    # Handle single-repo sessions (requires being in a git repo)
    try:
        sessions = _get_repo_sessions()
    except Exception:
        # Not in a git repo and no workspace found
        typer.secho(
            f"Error: Target '{target}' not found. Not in a git repository and no matching workspace found.",
            fg="red",
            err=True,
        )
        raise typer.Exit(1)

    if target.lower() == "all":
        if not sessions:
            typer.secho("No active sessions.", fg="yellow")
            return

        for session_data in sessions.values():
            session_name = session_data["tmux_session_name"]
            typer.echo(f"Sending to '{session_data.get('label', 'unknown')}'...")
            operations.send_tmux_keys(session_name, command)
    else:
        session_data = sessions.get(target)
        if not session_data:
            typer.secho(
                f"Error: Session or workspace '{target}' not found.", fg="red", err=True
            )
            raise typer.Exit(1)

        session_name = session_data["tmux_session_name"]
        typer.echo(f"Sending to '{target}'...")
        operations.send_tmux_keys(session_name, command)
        typer.secho(f"Sent command to session '{session_name}'", fg="green")


def list_sessions():
    """List all sessions and workspaces for the current repository."""
    from . import workspace

    sessions = _get_repo_sessions()
    current_repo_root = utils.get_git_repo_root()
    current_repo_name = current_repo_root.name

    # Get workspaces that contain this repository
    relevant_workspaces = []
    current_dir = current_repo_root.parent  # Go up to find workspace directories
    workspace_sessions = workspace._get_workspace_sessions(current_dir)

    for ws_label, ws_data in workspace_sessions.items():
        # Check if this workspace contains the current repository
        for repo_data in ws_data.get("repos", []):
            if repo_data["repo_name"] == current_repo_name:
                relevant_workspaces.append((ws_label, ws_data, repo_data))
                break

    if not sessions and not relevant_workspaces:
        typer.secho(
            "No active sessions or workspaces for this repository.", fg="yellow"
        )
        return

    console = Console()
    table = Table(title=f"Par Development Contexts for {current_repo_name}")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Type", style="bold blue", no_wrap=True)
    table.add_column("Tmux Session", style="magenta")
    table.add_column("Branch", style="green")
    table.add_column("Other Repos", style="yellow")
    table.add_column("Created", style="dim")

    # Add single-repo sessions
    for label, data in sorted(sessions.items()):
        session_active = (
            "✅" if operations.tmux_session_exists(data["tmux_session_name"]) else "❌"
        )

        table.add_row(
            label,
            "Session",
            f"{data['tmux_session_name']} ({session_active})",
            data["branch_name"],
            "-",
            data["created_at"][:16],  # Just date and time
        )

    # Add relevant workspaces
    for ws_label, ws_data, repo_data in sorted(relevant_workspaces):
        session_active = (
            "✅" if operations.tmux_session_exists(ws_data["session_name"]) else "❌"
        )

        # Get other repos in this workspace
        other_repos = [
            r["repo_name"]
            for r in ws_data.get("repos", [])
            if r["repo_name"] != current_repo_name
        ]
        other_repos_str = ", ".join(other_repos) if other_repos else "-"

        table.add_row(
            ws_label,
            "Workspace",
            f"{ws_data['session_name']} ({session_active})",
            repo_data["branch_name"],
            other_repos_str,
            ws_data["created_at"][:16],
        )

    console.print(table)


def open_session(label: str):
    """Open/attach to a specific session or workspace."""
    from . import workspace

    # First try single-repo sessions
    sessions = _get_repo_sessions()
    session_data = sessions.get(label)

    if session_data:
        # Handle single-repo session
        session_name = session_data["tmux_session_name"]

        if not operations.tmux_session_exists(session_name):
            typer.secho(f"Recreating tmux session '{session_name}'...", fg="yellow")
            operations.create_tmux_session(
                session_name, Path(session_data["worktree_path"])
            )

        operations.open_tmux_session(session_name)
        return

    # Try workspaces
    current_repo_root = utils.get_git_repo_root()
    current_dir = current_repo_root.parent
    workspace_sessions = workspace._get_workspace_sessions(current_dir)

    if label in workspace_sessions:
        # Handle workspace
        workspace.open_workspace_session(label)
        return

    typer.secho(f"Error: Session or workspace '{label}' not found.", fg="red", err=True)
    raise typer.Exit(1)


def checkout_session(target: str, custom_label: Optional[str] = None):
    """Checkout existing branch or PR into new session."""
    sessions = _get_repo_sessions()

    try:
        # Parse target to determine branch name and checkout strategy
        branch_name, strategy = checkout.parse_checkout_target(target)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg="red", err=True)
        raise typer.Exit(1)

    # Generate label (custom or derived from branch name)
    label = custom_label or branch_name

    if label in sessions:
        typer.secho(f"Error: Session '{label}' already exists.", fg="red", err=True)
        raise typer.Exit(1)

    repo_root = utils.get_git_repo_root()
    worktree_path = utils.get_worktree_path(repo_root, label)
    session_name = utils.get_tmux_session_name(repo_root, label)

    # Check for conflicts
    if worktree_path.exists():
        typer.secho(
            f"Error: Worktree path '{worktree_path}' exists.", fg="red", err=True
        )
        raise typer.Exit(1)

    if operations.tmux_session_exists(session_name):
        typer.secho(f"Error: tmux session '{session_name}' exists.", fg="red", err=True)
        raise typer.Exit(1)

    # Create worktree from existing branch (no new branch creation)
    operations.checkout_worktree(branch_name, worktree_path, strategy)
    operations.create_tmux_session(session_name, worktree_path)

    # Update state
    sessions[label] = {
        "worktree_path": str(worktree_path),
        "tmux_session_name": session_name,
        "branch_name": branch_name,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "checkout_target": target,  # Remember original target
        "is_checkout": True,  # Mark as checkout vs start
    }
    _update_repo_sessions(sessions)

    typer.secho(
        f"Successfully checked out '{target}' as session '{label}'.",
        fg="bright_green",
        bold=True,
    )
    typer.echo(f"  Worktree: {worktree_path}")
    typer.echo(f"  Branch: {branch_name}")
    typer.echo(f"  Session: {session_name}")
    typer.echo(f"To open: par open {label}")


def open_control_center():
    """Open all sessions and workspaces in a tiled tmux layout."""
    from . import workspace

    sessions = _get_repo_sessions()
    current_repo_root = utils.get_git_repo_root()
    current_repo_name = current_repo_root.name

    # Get workspaces that contain this repository
    current_dir = current_repo_root.parent
    workspace_sessions = workspace._get_workspace_sessions(current_dir)
    relevant_workspaces = []

    for ws_label, ws_data in workspace_sessions.items():
        # Check if this workspace contains the current repository
        for repo_data in ws_data.get("repos", []):
            if repo_data["repo_name"] == current_repo_name:
                relevant_workspaces.append((ws_label, ws_data))
                break

    if not sessions and not relevant_workspaces:
        typer.secho("No sessions or workspaces to display.", fg="yellow")
        return

    # Prepare all contexts for control center
    active_contexts = []

    # Add single-repo sessions
    for label, data in sessions.items():
        session_name = data["tmux_session_name"]
        if not operations.tmux_session_exists(session_name):
            typer.secho(f"Recreating session for '{label}'...", fg="yellow")
            operations.create_tmux_session(session_name, Path(data["worktree_path"]))
        active_contexts.append(data)

    # Add workspace sessions
    for ws_label, ws_data in relevant_workspaces:
        session_name = ws_data["session_name"]
        if not operations.tmux_session_exists(session_name):
            typer.secho(
                f"Recreating workspace session for '{ws_label}'...", fg="yellow"
            )
            operations.create_workspace_tmux_session(session_name, ws_data["repos"])

        # Convert workspace data to match session data format for control center
        workspace_context = {
            "tmux_session_name": session_name,
            "worktree_path": ws_data.get("workspace_root", ""),  # Use workspace root
        }
        active_contexts.append(workspace_context)

    operations.open_control_center(active_contexts)
