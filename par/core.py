"""Core business logic for par - simplified from actions.py and manager.py"""

import datetime
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import checkout, initialization, operations, utils, workspace


# Global state management
def _get_global_state_file() -> Path:
    return utils.get_data_dir() / "global_state.json"


def _load_global_state() -> Dict[str, Any]:
    state_file = _get_global_state_file()
    if not state_file.exists():
        # Try to migrate from old state files
        migrated_state = _migrate_legacy_state()
        if migrated_state:
            _save_global_state(migrated_state)
            return migrated_state
        return {"sessions": {}, "workspaces": {}}

    try:
        with open(state_file, "r") as f:
            content = f.read().strip()
            state = json.loads(content) if content else {}
            # Ensure structure exists
            if "sessions" not in state:
                state["sessions"] = {}
            if "workspaces" not in state:
                state["workspaces"] = {}
            return state
    except json.JSONDecodeError:
        typer.secho("Warning: Global state file corrupted. Starting fresh.", fg="yellow")
        return {"sessions": {}, "workspaces": {}}


def _save_global_state(state: Dict[str, Any]):
    state_file = _get_global_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def _update_last_session(label: str):
    """Update the last accessed session in global state."""
    state = _load_global_state()
    # Store the current last_session as previous_session before updating
    current_last = state.get("last_session")
    if current_last and current_last != label:
        state["previous_session"] = current_last
    state["last_session"] = label
    _save_global_state(state)


def _get_previous_session() -> Optional[str]:
    """Get the label of the previous session (for 'par open -' functionality)."""
    state = _load_global_state()
    return state.get("previous_session")


def _resolve_previous_session_label() -> str:
    """Resolve the '-' label to the appropriate session to switch to."""
    previous_session = _get_previous_session()
    if not previous_session:
        typer.secho("Error: No previous session found.", fg="red", err=True)
        raise typer.Exit(1)
    
    # Check if we're already in the previous session
    current_tmux_session = operations.get_current_tmux_session()
    if not current_tmux_session:
        return previous_session
    
    # Find which of our tracked sessions corresponds to the current tmux session
    state = _load_global_state()
    current_par_session = None
    for session_label, session_data in state["sessions"].items():
        if session_data["tmux_session_name"] == current_tmux_session:
            current_par_session = session_label
            break
    
    # If we're already in the "previous" session, go to the last session instead
    if current_par_session == previous_session:
        last_session = state.get("last_session")
        if last_session and last_session != current_par_session:
            return last_session
        else:
            typer.secho("Error: Cannot determine which session to switch to.", fg="red", err=True)
            raise typer.Exit(1)
    
    return previous_session


def _migrate_legacy_state() -> Dict[str, Any]:
    """Migrate from old per-repo state files to global state."""
    legacy_state_file = utils.get_data_dir() / "state.json"
    legacy_workspace_file = utils.get_data_dir() / "workspaces.json"

    migrated = {"sessions": {}, "workspaces": {}}

    # Migrate legacy sessions
    if legacy_state_file.exists():
        try:
            with open(legacy_state_file, "r") as f:
                content = f.read().strip()
                legacy_state = json.loads(content) if content else {}

            for repo_path, repo_sessions in legacy_state.items():
                repo_path_obj = Path(repo_path)
                repo_name = repo_path_obj.name

                for label, session_data in repo_sessions.items():
                    # Create globally unique label if collision
                    global_label = label
                    counter = 1
                    while global_label in migrated["sessions"]:
                        global_label = f"{label}-{repo_name.lower()}-{counter}"
                        counter += 1

                    migrated["sessions"][global_label] = {
                        "label": global_label,
                        "repository_path": repo_path,
                        "repository_name": repo_name,
                        "worktree_path": session_data["worktree_path"],
                        "tmux_session_name": session_data["tmux_session_name"],
                        "branch_name": session_data["branch_name"],
                        "created_at": session_data["created_at"],
                        "session_type": "checkout" if session_data.get("is_checkout") else "session",
                        "checkout_target": session_data.get("checkout_target")
                    }
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Migrate legacy workspaces
    if legacy_workspace_file.exists():
        try:
            with open(legacy_workspace_file, "r") as f:
                content = f.read().strip()
                legacy_workspaces = json.loads(content) if content else {}

            for workspace_root, workspace_sessions in legacy_workspaces.items():
                for label, workspace_data in workspace_sessions.items():
                    # Create globally unique label if collision
                    global_label = label
                    counter = 1
                    while (global_label in migrated["sessions"] or
                           global_label in migrated["workspaces"]):
                        workspace_name = Path(workspace_root).name
                        global_label = f"{label}-{workspace_name.lower()}-{counter}"
                        counter += 1

                    migrated["workspaces"][global_label] = {
                        "label": global_label,
                        "workspace_root": workspace_data["workspace_root"],
                        "session_name": workspace_data["session_name"],
                        "repos": workspace_data["repos"],
                        "created_at": workspace_data["created_at"]
                    }
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # If we migrated anything, backup the old files
    if migrated["sessions"] or migrated["workspaces"]:
        backup_dir = utils.get_data_dir() / "backup"
        backup_dir.mkdir(exist_ok=True)

        if legacy_state_file.exists():
            shutil.copy2(legacy_state_file, backup_dir / "state.json.backup")
        if legacy_workspace_file.exists():
            shutil.copy2(legacy_workspace_file, backup_dir / "workspaces.json.backup")

        typer.secho(f"Migrated legacy state files. Backups saved to {backup_dir}", fg="green")

    return migrated


def _validate_label_unique(label: str) -> bool:
    """Check if a label is globally unique across sessions and workspaces."""
    state = _load_global_state()
    return label not in state["sessions"] and label not in state["workspaces"]


def _get_all_sessions() -> Dict[str, Any]:
    """Get all sessions globally."""
    state = _load_global_state()
    return state["sessions"]


# Workspaces are now stored as sessions with session_type="workspace"


def _add_session(session_data: Dict[str, Any]):
    """Add a session to global state."""
    state = _load_global_state()
    state["sessions"][session_data["label"]] = session_data
    _save_global_state(state)


def _remove_session(label: str):
    """Remove a session from global state."""
    state = _load_global_state()
    if label in state["sessions"]:
        del state["sessions"][label]
        _save_global_state(state)


def _get_session(label: str) -> Optional[Dict[str, Any]]:
    """Get a specific session by label."""
    state = _load_global_state()
    return state["sessions"].get(label)




# Session operations - now globally scoped
def start_session(label: str, repo_path: Optional[str] = None, open_session: bool = False):
    """Start a new git worktree and tmux session."""
    # Validate label is globally unique
    if not _validate_label_unique(label):
        typer.secho(f"Error: Label '{label}' already exists. Labels must be globally unique.", fg="red", err=True)
        raise typer.Exit(1)

    # Resolve repository path
    repo_root = utils.resolve_repository_path(repo_path)
    repo_name = repo_root.name

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
    operations.create_worktree(label, worktree_path, repo_root)
    operations.create_tmux_session(session_name, worktree_path)

    # Run includes and initialization if .par.yaml exists
    config = initialization.load_par_config(repo_root)
    if config:
        initialization.copy_included_files(config, repo_root, worktree_path)
        initialization.run_initialization(config, session_name, worktree_path)

    # Create session data for global state
    session_data = {
        "label": label,
        "repository_path": str(repo_root),
        "repository_name": repo_name,
        "worktree_path": str(worktree_path),
        "tmux_session_name": session_name,
        "branch_name": label,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "session_type": "session"
    }
    _add_session(session_data)

    typer.secho(
        f"Successfully started session '{label}' in {repo_name}.", fg="bright_green", bold=True
    )
    typer.echo(f"  Repository: {repo_root}")
    typer.echo(f"  Worktree: {worktree_path}")
    typer.echo(f"  Branch: {label}")
    typer.echo(f"  Session: {session_name}")

    if open_session:
        typer.echo("Opening session...")
        operations.open_tmux_session(session_name)
        # Track this session as the last opened
        _update_last_session(label)
    else:
        typer.echo(f"To open: par open {label}")


def remove_session(label: str):
    """Remove a session and clean up all resources."""
    session_data = _get_session(label)

    if not session_data:
        typer.secho(f"Error: Session '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_type = session_data.get("session_type", "session")

    # Handle workspace sessions differently
    if session_type == "workspace":
        _remove_workspace_session(session_data)
    else:
        _remove_regular_session(session_data)

    # Remove from global state
    _remove_session(label)

    typer.secho(
        f"Successfully removed {session_type} '{label}'.", fg="bright_green", bold=True
    )


def _remove_regular_session(session_data: Dict[str, Any]):
    """Remove a regular session (not workspace)."""
    # Clean up resources
    operations.kill_tmux_session(session_data["tmux_session_name"])
    repo_root = Path(session_data["repository_path"])
    operations.remove_worktree(Path(session_data["worktree_path"]), repo_root)

    # Only delete branch if it was created by par (not checkout)
    if session_data.get("session_type") != "checkout":
        operations.delete_branch(session_data["branch_name"], repo_root)

    # Remove physical directory if it exists and is managed by par
    worktree_path = Path(session_data["worktree_path"])
    if worktree_path.exists() and utils.get_data_dir() in worktree_path.parents:
        try:
            shutil.rmtree(worktree_path)
        except OSError as e:
            typer.secho(
                f"Warning: Could not remove directory {worktree_path}: {e}", fg="yellow"
            )


def _remove_workspace_session(session_data: Dict[str, Any]):
    """Remove a workspace session and all its repositories."""
    # Kill tmux session
    operations.kill_tmux_session(session_data["tmux_session_name"])

    # Remove worktrees and branches for each repo in the workspace
    repos_data = session_data.get("workspace_repos", [])
    for repo_data in repos_data:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        branch_name = repo_data["branch_name"]

        operations.remove_worktree(worktree_path, repo_path)
        operations.delete_branch(branch_name, repo_path)

    # Remove workspace directory if it exists and is managed by par
    workspace_root = Path(session_data["repository_path"])
    if workspace_root.exists() and utils.get_data_dir() in workspace_root.parents:
        try:
            shutil.rmtree(workspace_root)
        except OSError as e:
            typer.secho(
                f"Warning: Could not remove workspace directory {workspace_root}: {e}", fg="yellow"
            )


def _get_workspace(label: str) -> Optional[Dict[str, Any]]:
    """Get a specific workspace by label."""
    state = _load_global_state()
    return state["workspaces"].get(label)


def remove_all_sessions():
    """Remove all sessions (including workspaces) globally."""
    sessions = _get_all_sessions()

    if not sessions:
        typer.secho("No sessions to remove.", fg="yellow")
        return

    # Separate regular sessions from workspaces for display
    regular_sessions = {k: v for k, v in sessions.items() if v.get("session_type") != "workspace"}
    workspace_sessions = {k: v for k, v in sessions.items() if v.get("session_type") == "workspace"}

    typer.echo(f"This will remove {len(regular_sessions)} sessions and {len(workspace_sessions)} workspaces:")
    for label in regular_sessions:
        typer.echo(f"  Session: {label}")
    for label in workspace_sessions:
        typer.echo(f"  Workspace: {label}")

    typer.confirm(f"Remove all {len(sessions)} items?", abort=True)

    # Remove all sessions (including workspaces)
    for label in list(sessions.keys()):
        session_type = sessions[label].get("session_type", "session")
        typer.echo(f"Removing {session_type} '{label}'...")
        remove_session(label)

    typer.secho("All sessions removed.", fg="bright_green", bold=True)


def send_command(target: str, command: str):
    """Send a command to session(s) (including workspaces)."""
    sessions = _get_all_sessions()

    if target.lower() == "all":
        if not sessions:
            typer.secho("No active sessions.", fg="yellow")
            return

        # Send to all sessions (including workspaces)
        for label, session_data in sessions.items():
            session_name = session_data["tmux_session_name"]
            session_type = session_data.get("session_type", "session")
            typer.echo(f"Sending to {session_type} '{label}'...")
            operations.send_tmux_keys(session_name, command)
    else:
        # Find target session (could be regular session or workspace)
        session_data = sessions.get(target)
        if session_data:
            session_name = session_data["tmux_session_name"]
            session_type = session_data.get("session_type", "session")
            typer.echo(f"Sending to {session_type} '{target}'...")
            operations.send_tmux_keys(session_name, command)
        else:
            typer.secho(f"Error: Session '{target}' not found.", fg="red", err=True)
            raise typer.Exit(1)


def list_sessions():
    """List all sessions and workspaces globally."""
    sessions = _get_all_sessions()

    if not sessions:
        typer.secho("No active sessions or workspaces.", fg="yellow")
        return

    console = Console()
    table = Table(title="Par Development Contexts (Global)")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Type", style="bold blue", no_wrap=True)
    table.add_column("Repository/Workspace", style="green")
    table.add_column("Tmux Session", style="magenta")
    table.add_column("Branch", style="yellow")
    table.add_column("Created", style="dim")

    # Add all sessions (including workspaces)
    for label, data in sorted(sessions.items()):
        session_active = (
            "✅" if operations.tmux_session_exists(data["tmux_session_name"]) else "❌"
        )

        session_type = data.get("session_type", "session")

        if session_type == "workspace":
            # Display workspace info
            workspace_repos = data.get("workspace_repos", [])
            repo_names = [repo["repo_name"] for repo in workspace_repos]
            repo_display = f"workspace ({len(repo_names)} repos: {', '.join(repo_names)})"
        else:
            # Display regular session info
            repo_display = f"{data['repository_name']} ({Path(data['repository_path']).parent.name})"

        table.add_row(
            label,
            session_type.title(),
            repo_display,
            f"{data['tmux_session_name']} ({session_active})",
            data["branch_name"],
            data["created_at"][:16],  # Just date and time
        )

    console.print(table)


def open_session(label: str):
    """Open/attach to a specific session or workspace."""
    # Handle special case for previous session
    if label == "-":
        label = _resolve_previous_session_label()

    # Try sessions first
    session_data = _get_session(label)
    if session_data:
        session_name = session_data["tmux_session_name"]

        if not operations.tmux_session_exists(session_name):
            typer.secho(f"Recreating tmux session '{session_name}'...", fg="yellow")
            operations.create_tmux_session(
                session_name, Path(session_data["worktree_path"])
            )

        operations.open_tmux_session(session_name)
        # Track this session as the last opened
        _update_last_session(label)
        return

    # Try workspaces
    workspace_data = _get_workspace(label)
    if workspace_data:
        workspace.open_workspace_session(label)
        # Track this workspace as the last opened
        _update_last_session(label)
        return

    typer.secho(f"Error: Session or workspace '{label}' not found.", fg="red", err=True)
    raise typer.Exit(1)


def checkout_session(target: str, custom_label: Optional[str] = None, repo_path: Optional[str] = None):
    """Checkout existing branch or PR into new session."""
    try:
        # Parse target to determine branch name and checkout strategy
        branch_name, strategy = checkout.parse_checkout_target(target)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg="red", err=True)
        raise typer.Exit(1)

    # Generate label (custom or derived from branch name)
    label = custom_label or branch_name

    # Validate label is globally unique
    if not _validate_label_unique(label):
        typer.secho(f"Error: Label '{label}' already exists. Labels must be globally unique.", fg="red", err=True)
        raise typer.Exit(1)

    # Resolve repository path
    repo_root = utils.resolve_repository_path(repo_path)
    repo_name = repo_root.name

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
    operations.checkout_worktree(branch_name, worktree_path, strategy, repo_root)
    operations.create_tmux_session(session_name, worktree_path)

    # Run includes and initialization if .par.yaml exists
    config = initialization.load_par_config(repo_root)
    if config:
        initialization.copy_included_files(config, repo_root, worktree_path)
        initialization.run_initialization(
            config, session_name, worktree_path
        )

    # Create session data for global state
    session_data = {
        "label": label,
        "repository_path": str(repo_root),
        "repository_name": repo_name,
        "worktree_path": str(worktree_path),
        "tmux_session_name": session_name,
        "branch_name": branch_name,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "session_type": "checkout",
        "checkout_target": target
    }
    _add_session(session_data)

    typer.secho(
        f"Successfully checked out '{target}' as session '{label}' in {repo_name}.",
        fg="bright_green",
        bold=True,
    )
    typer.echo(f"  Repository: {repo_root}")
    typer.echo(f"  Worktree: {worktree_path}")
    typer.echo(f"  Branch: {branch_name}")
    typer.echo(f"  Session: {session_name}")
    typer.echo(f"To open: par open {label}")


def open_control_center():
    """Create a new 'control-center' tmux session with separate windows for each par session."""

    # Get all sessions from global state (includes both regular sessions and workspaces)
    sessions = _get_all_sessions()

    if not sessions:
        typer.secho("No sessions or workspaces to display.", fg="yellow")
        return

    # Collect all repositories to determine naming strategy
    all_repos = set()

    # Collect repo names from all sessions
    for label, data in sessions.items():
        session_type = data.get("session_type", "session")
        if session_type == "workspace":
            # For workspaces, just add the workspace name
            all_repos.add(f"workspace-{label}")
        else:
            # For regular sessions, use repository name
            all_repos.add(data['repository_name'])

    # Determine if we need to include repo names (more than one unique repo)
    include_repo_name = len(all_repos) > 1

    # Prepare all contexts for control center
    active_contexts = []

    # Process all sessions
    for label, data in sessions.items():
        session_type = data.get("session_type", "session")

        if session_type == "workspace":
            # For workspaces, create single window starting from workspace root
            workspace_root = data["repository_path"]  # This is the workspace root directory
            name = f"workspace-{label}" if include_repo_name else label
            active_contexts.append({
                "name": name,
                "path": workspace_root,
                "type": "workspace"
            })
        else:
            # For regular sessions, create single window
            repo_name = data['repository_name']
            name = f"{repo_name}-{label}" if include_repo_name else label
            active_contexts.append({
                "name": name,
                "path": data["worktree_path"],
                "type": "session"
            })

    operations.open_control_center(active_contexts)
