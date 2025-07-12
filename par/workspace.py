"""Workspace management for multi-repository development."""

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import initialization, operations, utils


# Workspace state management
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
        typer.secho(
            "Warning: Workspace state file corrupted. Starting fresh.", fg="yellow"
        )
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


# Workspace operations
def start_workspace_session(
    label: str, repos: Optional[List[str]] = None, open_session: bool = False
):
    """Start a new workspace with multiple repositories."""
    current_dir = Path.cwd()

    # Auto-detect repos if not specified
    if not repos:
        detected_repos = utils.detect_git_repos(current_dir)
        if not detected_repos:
            typer.secho(
                "Error: No git repositories found in current directory.",
                fg="red",
                err=True,
            )
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
                typer.secho(
                    f"Error: Repository '{repo_name}' not found.", fg="red", err=True
                )
                raise typer.Exit(1)
            if not (repo_path / ".git").exists():
                typer.secho(
                    f"Error: '{repo_name}' is not a git repository.", fg="red", err=True
                )
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
        worktree_path = utils.get_workspace_worktree_path(
            current_dir, label, repo_name, label
        )

        # Check for conflicts
        if worktree_path.exists():
            typer.secho(
                f"Error: Worktree path '{worktree_path}' exists.", fg="red", err=True
            )
            raise typer.Exit(1)

        # Create resources
        operations.create_workspace_worktree(repo_path, label, worktree_path)

        # Copy includes for this repository
        config = initialization.load_par_config(repo_path)
        if config:
            initialization.copy_included_files(
                config, repo_path, worktree_path
            )

        repos_data.append(
            {
                "repo_name": repo_name,
                "repo_path": str(repo_path),
                "worktree_path": str(worktree_path),
                "branch_name": label,
            }
        )

    # Create tmux session with multiple panes
    operations.create_workspace_tmux_session(session_name, repos_data)

    # Run initialization for each repository if .par.yaml exists
    has_initialization = False
    for repo_data in repos_data:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        config = initialization.load_par_config(repo_path)
        if config:
            initialization.run_initialization(
                config, session_name, worktree_path, workspace_mode=True
            )
            has_initialization = True

    # Return to workspace root after initialization
    if has_initialization:
        # Calculate the actual workspace root directory (parent of all repo worktrees)
        first_worktree_path = Path(repos_data[0]["worktree_path"])
        workspace_root = first_worktree_path.parent.parent
        operations.send_tmux_keys(session_name, f"cd {workspace_root}")

    # Update state
    workspace_sessions[label] = {
        "session_name": session_name,
        "repos": repos_data,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "workspace_root": str(current_dir),
    }
    _update_workspace_sessions(current_dir, workspace_sessions)

    typer.secho(
        f"Successfully started workspace '{label}' with {len(repos_data)} repositories.",
        fg="bright_green",
        bold=True,
    )
    for repo_data in repos_data:
        typer.echo(f"  {repo_data['repo_name']}: {repo_data['worktree_path']}")
    typer.echo(f"  Session: {session_name}")
    typer.echo(f"To open: par workspace open {label}")

    if open_session:
        open_workspace_session(label)


def list_workspace_sessions():
    """List all workspace sessions for the current directory."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if not workspace_sessions:
        typer.secho("No workspace sessions found for this directory.", fg="yellow")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Repositories", style="green")
    table.add_column("Session", style="blue", no_wrap=True)
    table.add_column("Created", style="dim")

    for label, data in workspace_sessions.items():
        repos = ", ".join([repo["repo_name"] for repo in data["repos"]])
        session_name = data["session_name"]
        created = data.get("created_at", "Unknown")
        if created != "Unknown":
            # Format datetime to be more readable
            try:
                dt = datetime.datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        table.add_row(label, repos, session_name, created)

    console.print(table)


def open_workspace_session(label: str):
    """Open/attach to a specific workspace session."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if label not in workspace_sessions:
        typer.secho(f"Error: Workspace '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_data = workspace_sessions[label]
    session_name = session_data["session_name"]

    # Ensure session exists, recreate if needed
    if not operations.tmux_session_exists(session_name):
        typer.secho(f"Recreating workspace session for '{label}'...", fg="yellow")
        operations.create_workspace_tmux_session(session_name, session_data["repos"])

    operations.open_tmux_session(session_name)


def remove_workspace_session(label: str):
    """Remove a specific workspace session."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if label not in workspace_sessions:
        typer.secho(f"Error: Workspace '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_data = workspace_sessions[label]
    session_name = session_data["session_name"]

    # Kill tmux session
    operations.kill_tmux_session(session_name)

    # Remove worktrees and branches for each repo
    for repo_data in session_data["repos"]:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        branch_name = repo_data["branch_name"]

        operations.remove_workspace_worktree(repo_path, worktree_path)
        operations.delete_workspace_branch(repo_path, branch_name)

    # Remove workspace directory if empty
    if session_data["repos"]:
        first_worktree_path = Path(session_data["repos"][0]["worktree_path"])
        workspace_dir = first_worktree_path.parent.parent
        try:
            workspace_dir.rmdir()  # Only removes if empty
        except OSError:
            pass  # Directory not empty or doesn't exist

    # Update state
    del workspace_sessions[label]
    _update_workspace_sessions(current_dir, workspace_sessions)

    typer.secho(f"Successfully removed workspace '{label}'.", fg="green")


def remove_all_workspace_sessions():
    """Remove all workspace sessions for the current directory."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if not workspace_sessions:
        typer.secho("No workspace sessions to remove.", fg="yellow")
        return

    # Confirm removal
    labels = list(workspace_sessions.keys())
    typer.echo(f"This will remove {len(labels)} workspace sessions:")
    for label in labels:
        typer.echo(f"  - {label}")

    if not typer.confirm("Are you sure?"):
        typer.echo("Cancelled.")
        return

    # Remove each session
    for label in labels:
        try:
            remove_workspace_session(label)
        except typer.Exit:
            # Continue removing other sessions even if one fails
            pass

    typer.secho("All workspace sessions removed.", fg="green")


def open_workspace_in_ide(label: str, ide: str):
    """Open a workspace in the specified IDE."""
    current_dir = Path.cwd()
    workspace_sessions = _get_workspace_sessions(current_dir)

    if label not in workspace_sessions:
        typer.secho(f"Error: Workspace '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    session_data = workspace_sessions[label]
    repos_data = session_data["repos"]

    # Generate and save workspace file
    workspace_file = utils.save_vscode_workspace_file(label, repos_data)

    # Open in specified IDE
    try:
        if ide == "code":
            operations.run_cmd([ide, str(workspace_file)])
            typer.secho(f"Opening workspace '{label}' in VSCode...", fg="green")
        elif ide == "cursor":
            operations.run_cmd([ide, str(workspace_file)])
            typer.secho(f"Opening workspace '{label}' in Cursor...", fg="green")
        else:
            typer.secho(f"Error: Unsupported IDE '{ide}'", fg="red", err=True)
            raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error opening {ide}: {e}", fg="red", err=True)
        typer.echo(f"Make sure {ide} is installed and in your PATH.")
        raise typer.Exit(1)
