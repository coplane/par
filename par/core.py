"""Core business logic for par - simplified from actions.py and manager.py"""

import datetime
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import checkout, initialization, operations, utils


# State management - simplified from SessionManager class
def _get_state_file() -> Path:
    return utils.get_data_dir() / "state.json"


def _load_state() -> Dict[str, Any]:
    state_file = _get_state_file()
    if not state_file.exists():
        return {}

    try:
        with open(state_file, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        typer.secho("Warning: State file corrupted. Starting fresh.", fg="yellow")
        return {}


def _save_state(state: Dict[str, Any]):
    state_file = _get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def _get_repo_key() -> str:
    return str(utils.get_git_repo_root().resolve())


def _get_repo_sessions() -> Dict[str, Any]:
    state = _load_state()
    repo_key = _get_repo_key()
    return state.get(repo_key, {})


def _update_repo_sessions(sessions: Dict[str, Any]):
    state = _load_state()
    repo_key = _get_repo_key()

    if sessions:
        state[repo_key] = sessions
    else:
        state.pop(repo_key, None)  # Remove empty repo entries

    _save_state(state)


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

    # Update state
    sessions[label] = {
        "worktree_path": str(worktree_path),
        "tmux_session_name": session_name,
        "branch_name": label,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _update_repo_sessions(sessions)

    typer.secho(
        f"Successfully started session '{label}'.", fg="bright_green", bold=True
    )
    typer.echo(f"  Worktree: {worktree_path}")
    typer.echo(f"  Branch: {label}")
    typer.echo(f"  Session: {session_name}")

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
    """Send a command to session(s)."""
    sessions = _get_repo_sessions()

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
            typer.secho(f"Error: Session '{target}' not found.", fg="red", err=True)
            raise typer.Exit(1)

        session_name = session_data["tmux_session_name"]
        typer.echo(f"Sending to '{target}'...")
        operations.send_tmux_keys(session_name, command)


def list_sessions():
    """List all sessions for the current repository."""
    sessions = _get_repo_sessions()

    if not sessions:
        typer.secho("No active sessions.", fg="yellow")
        return

    console = Console()
    table = Table(title="Par Sessions")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Tmux Session", style="magenta")
    table.add_column("Branch", style="green")
    table.add_column("Worktree Path", style="blue")
    table.add_column("Created", style="dim")

    for label, data in sorted(sessions.items()):
        session_active = (
            "✅" if operations.tmux_session_exists(data["tmux_session_name"]) else "❌"
        )

        table.add_row(
            label,
            f"{data['tmux_session_name']} ({session_active})",
            data["branch_name"],
            data["worktree_path"],
            data["created_at"][:16],  # Just date and time
        )

    console.print(table)


def open_session(label: str):
    """Open/attach to a specific session."""
    sessions = _get_repo_sessions()
    session_data = sessions.get(label)

    if not session_data:
        typer.secho(f"Error: Session '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_name = session_data["tmux_session_name"]

    if not operations.tmux_session_exists(session_name):
        typer.secho(f"Recreating tmux session '{session_name}'...", fg="yellow")
        operations.create_tmux_session(
            session_name, Path(session_data["worktree_path"])
        )

    operations.open_tmux_session(session_name)


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
        "created_at": datetime.datetime.utcnow().isoformat(),
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
    """Open all sessions in a tiled tmux layout."""
    sessions = _get_repo_sessions()

    if not sessions:
        typer.secho("No sessions to display.", fg="yellow")
        return

    # Ensure all sessions exist
    active_sessions = []
    for label, data in sessions.items():
        session_name = data["tmux_session_name"]
        if not operations.tmux_session_exists(session_name):
            typer.secho(f"Recreating session for '{label}'...", fg="yellow")
            operations.create_tmux_session(session_name, Path(data["worktree_path"]))
        active_sessions.append(data)

    operations.open_control_center(active_sessions)


# Workspace operations
def _get_workspace_state_file() -> Path:
    return utils.get_data_dir() / "workspaces.json"


def _load_workspace_state() -> Dict[str, Any]:
    state_file = _get_workspace_state_file()
    if not state_file.exists():
        return {}

    try:
        with open(state_file, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        typer.secho("Warning: Workspace state file corrupted. Starting fresh.", fg="yellow")
        return {}


def _save_workspace_state(state: Dict[str, Any]):
    state_file = _get_workspace_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def _get_workspace_key(workspace_root: Path) -> str:
    return str(workspace_root.resolve())


def _get_workspace_sessions(workspace_root: Path) -> Dict[str, Any]:
    state = _load_workspace_state()
    workspace_key = _get_workspace_key(workspace_root)
    return state.get(workspace_key, {})


def _update_workspace_sessions(workspace_root: Path, sessions: Dict[str, Any]):
    state = _load_workspace_state()
    workspace_key = _get_workspace_key(workspace_root)

    if sessions:
        state[workspace_key] = sessions
    else:
        state.pop(workspace_key, None)  # Remove empty workspace entries

    _save_workspace_state(state)


def start_workspace_session(label: str, repos: Optional[List[str]] = None, open_session: bool = False):
    """Start a new workspace with multiple repositories."""
    current_dir = Path.cwd()
    
    # Auto-detect repos if not specified
    if not repos:
        detected_repos = utils.detect_git_repos(current_dir)
        if not detected_repos:
            typer.secho("Error: No git repositories found in current directory.", fg="red", err=True)
            typer.echo("Use --repos to specify repositories explicitly.")
            raise typer.Exit(1)
        repo_names = [repo.name for repo in detected_repos]
        repo_paths = detected_repos
    else:
        repo_names = repos
        repo_paths = []
        for repo_name in repos:
            repo_path = current_dir / repo_name
            if not repo_path.exists():
                typer.secho(f"Error: Repository '{repo_name}' not found.", fg="red", err=True)
                raise typer.Exit(1)
            if not (repo_path / ".git").exists():
                typer.secho(f"Error: '{repo_name}' is not a git repository.", fg="red", err=True)
                raise typer.Exit(1)
            repo_paths.append(repo_path)

    # Check if workspace already exists
    workspace_sessions = _get_workspace_sessions(current_dir)
    if label in workspace_sessions:
        typer.secho(f"Error: Workspace '{label}' already exists.", fg="red", err=True)
        raise typer.Exit(1)

    session_name = utils.get_workspace_session_name(current_dir, label)

    # Check for conflicts
    if operations.tmux_session_exists(session_name):
        typer.secho(f"Error: tmux session '{session_name}' exists.", fg="red", err=True)
        raise typer.Exit(1)

    # Create worktrees for each repo
    repos_data = []
    for repo_path, repo_name in zip(repo_paths, repo_names):
        worktree_path = utils.get_workspace_worktree_path(current_dir, label, repo_name, label)
        
        # Check for conflicts
        if worktree_path.exists():
            typer.secho(f"Error: Worktree path '{worktree_path}' exists.", fg="red", err=True)
            raise typer.Exit(1)

        # Create resources
        operations.create_workspace_worktree(repo_path, label, worktree_path)
        
        repos_data.append({
            "repo_name": repo_name,
            "repo_path": str(repo_path),
            "worktree_path": str(worktree_path),
            "branch_name": label,
        })

    # Create tmux session with multiple panes
    operations.create_workspace_tmux_session(session_name, repos_data)

    # Run initialization if .par.yaml exists in workspace root
    config = initialization.load_par_config(current_dir)
    if config:
        initialization.run_initialization(config, session_name, current_dir)

    # Update state
    workspace_sessions[label] = {
        "session_name": session_name,
        "repos": repos_data,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "workspace_root": str(current_dir),
    }
    _update_workspace_sessions(current_dir, workspace_sessions)

    typer.secho(f"Successfully started workspace '{label}' with {len(repos_data)} repositories.", fg="bright_green", bold=True)
    for repo_data in repos_data:
        typer.echo(f"  {repo_data['repo_name']}: {repo_data['worktree_path']}")
    typer.echo(f"  Session: {session_name}")
    
    if open_session:
        typer.echo("Opening workspace...")
        operations.open_tmux_session(session_name)
    else:
        typer.echo(f"To open: par workspace open {label}")


def list_workspace_sessions():
    """List all workspace sessions."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if not workspace_sessions:
        typer.secho("No active workspace sessions.", fg="yellow")
        return

    console = Console()
    table = Table(title="Par Workspace Sessions")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Tmux Session", style="magenta")
    table.add_column("Repositories", style="green")
    table.add_column("Created", style="dim")

    for label, data in sorted(workspace_sessions.items()):
        session_active = (
            "✅" if operations.tmux_session_exists(data["session_name"]) else "❌"
        )
        
        repo_names = [repo["repo_name"] for repo in data["repos"]]
        repo_list = ", ".join(repo_names)

        table.add_row(
            label,
            f"{data['session_name']} ({session_active})",
            repo_list,
            data["created_at"][:16],  # Just date and time
        )

    console.print(table)


def open_workspace_session(label: str):
    """Open/attach to a specific workspace session."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)
    workspace_data = workspace_sessions.get(label)

    if not workspace_data:
        typer.secho(f"Error: Workspace '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_name = workspace_data["session_name"]

    if not operations.tmux_session_exists(session_name):
        typer.secho(f"Recreating workspace session '{session_name}'...", fg="yellow")
        operations.create_workspace_tmux_session(session_name, workspace_data["repos"])

    operations.open_tmux_session(session_name)


def remove_workspace_session(label: str):
    """Remove a workspace session and clean up all resources."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)
    workspace_data = workspace_sessions.get(label)

    if not workspace_data:
        typer.secho(f"Warning: Workspace '{label}' not found in state.", fg="yellow")
        return

    # Clean up resources for each repo
    for repo_data in workspace_data["repos"]:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        branch_name = repo_data["branch_name"]

        # Remove worktree and branch
        operations.remove_workspace_worktree(repo_path, worktree_path)
        operations.delete_workspace_branch(repo_path, branch_name)

        # Remove physical directory if it exists and is managed by par
        if worktree_path.exists() and utils.get_data_dir() in worktree_path.parents:
            try:
                shutil.rmtree(worktree_path)
            except OSError as e:
                typer.secho(f"Warning: Could not remove directory {worktree_path}: {e}", fg="yellow")

    # Kill tmux session
    operations.kill_tmux_session(workspace_data["session_name"])

    # Update state
    del workspace_sessions[label]
    _update_workspace_sessions(current_dir, workspace_sessions)

    typer.secho(f"Successfully removed workspace '{label}'.", fg="bright_green", bold=True)


def remove_all_workspace_sessions():
    """Remove all workspace sessions for the current directory."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if not workspace_sessions:
        typer.secho("No workspace sessions to remove.", fg="yellow")
        return

    typer.confirm(f"Remove all {len(workspace_sessions)} workspace sessions?", abort=True)

    for label in list(workspace_sessions.keys()):
        typer.echo(f"Removing workspace '{label}'...")
        remove_workspace_session(label)

    typer.secho("All workspace sessions removed.", fg="bright_green", bold=True)
